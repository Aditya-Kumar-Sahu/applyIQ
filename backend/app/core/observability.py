from __future__ import annotations

import asyncio
import re
from typing import Any, Callable, TypeVar

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from prometheus_client import Counter, Histogram

# --- Python 3.12+ Compatibility Fix for OTEL ---
import sys
from types import ModuleType

try:
    import pkg_resources
except ImportError:
    pkg_resources = ModuleType("pkg_resources")
    sys.modules["pkg_resources"] = pkg_resources

# Ensure all attributes required by OTEL instrumentors are present
for attr in ["Distribution", "DistributionNotFound", "RequirementParseError", "VersionConflict"]:
    if not hasattr(pkg_resources, attr):
        class MockAttr(Exception): pass
        setattr(pkg_resources, attr, MockAttr)

if not hasattr(pkg_resources, "get_distribution"):
    pkg_resources.get_distribution = lambda x: None

if not hasattr(pkg_resources, "parse_requirements"):
    pkg_resources.parse_requirements = lambda x: []
# -----------------------------------------------

from opentelemetry import trace, context
from opentelemetry.sdk.trace import TracerProvider, Span
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor

from app.core.config import Settings


T = TypeVar("T")

# --- Custom Metrics ---
SCRAPER_REQUESTS_TOTAL = Counter(
    "scraper_requests_total",
    "Total number of scraper requests",
    ["source", "status"]
)

SCRAPER_DURATION_SECONDS = Histogram(
    "scraper_duration_seconds",
    "Time spent scraping jobs",
    ["source"],
    buckets=(1, 5, 10, 30, 60, 120, 300)
)

LLM_TOKEN_USAGE_TOTAL = Counter(
    "llm_token_usage_total",
    "Total number of tokens used per model",
    ["model", "type"] # type: prompt, completion
)
# ----------------------

# --- PII Redaction ---
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_SENSITIVE_FIELDS = {
    "resume_profile", "cover_letter_text", "raw_text", 
    "parsed_profile", "access_token", "refresh_token"
}

def scrub_pii(data: Any) -> Any:
    if isinstance(data, str):
        return _EMAIL_RE.sub("[REDACTED_EMAIL]", data)
    if isinstance(data, dict):
        return {
            k: ("[REDACTED_FIELD]" if k in _SENSITIVE_FIELDS else scrub_pii(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [scrub_pii(v) for v in data]
    return data

def set_scrubbed_attribute(span: Span, key: str, value: Any) -> None:
    scrubbed = scrub_pii(value)
    if not isinstance(scrubbed, (str, bool, int, float)):
        import json
        scrubbed = str(scrubbed)
    span.set_attribute(key, scrubbed)
# ---------------------

def configure_observability(settings: Settings, app: Any = None) -> None:
    # 1. Sentry (Error Tracking Only)
    if settings.sentry_dsn_backend:
        sentry_sdk.init(
            dsn=settings.sentry_dsn_backend,
            environment=settings.environment,
            release=settings.release_version,
            traces_sample_rate=0.0, # Handled by OTEL
            integrations=[
                FastApiIntegration(),
                CeleryIntegration(propagate_traces=False) # Handled by OTEL
            ],
            send_default_pii=False,
        )

    # 2. OpenTelemetry (Tracing)
    resource = Resource.create({
        "service.name": settings.project_slug,
        "environment": settings.environment,
    })
    
    provider = TracerProvider(resource=resource)
    
    # Configure OTLP Exporter with timeout
    exporter = OTLPSpanExporter(timeout=5)
    
    # Non-blocking batch processor with explicit performance tuning
    processor = BatchSpanProcessor(
        exporter,
        schedule_delay_millis=5000, # 5s delay to batch spans
        max_export_batch_size=512,
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # 3. Auto-Instrumentation
    if app:
        FastAPIInstrumentor().instrument_app(app)
    
    CeleryInstrumentor().instrument()


async def otel_anyio_run(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """
    Wraps anyio.run to propagate OTEL context into the new event loop.
    """
    import anyio
    
    # Capture current context
    current_ctx = context.get_current()
    
    async def _wrapped():
        # Attach context to new event loop thread
        token = context.attach(current_ctx)
        try:
            return await func(*args, **kwargs)
        finally:
            context.detach(token)
            
    return await anyio.run(_wrapped)
