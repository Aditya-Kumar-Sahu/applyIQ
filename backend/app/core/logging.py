from __future__ import annotations

import logging

import structlog


def configure_logging(log_level: str) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO), format="%(message)s")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            timestamper,
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
