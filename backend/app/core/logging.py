from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog


def _render_with_timestamp_prefix(_: Any, __: str, event_dict: dict[str, Any]) -> str:
    prefix_timestamp = str(event_dict.pop("timestamp", "")).strip()
    if not prefix_timestamp:
        prefix_timestamp = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(event_dict, ensure_ascii=True)
    return f"{prefix_timestamp} {payload}"


def _add_logger_name(logger: Any, _: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    logger_name = None
    if logger is not None:
        logger_name = getattr(logger, "name", None)
    if logger_name is None:
        record = event_dict.get("_record")
        logger_name = getattr(record, "name", None)
    event_dict.setdefault("logger", logger_name or "root")
    return event_dict


def configure_logging(
    *,
    log_level: str,
    log_to_file: bool,
    log_dir: str,
    log_file_name: str,
    log_file_max_bytes: int,
    log_file_backup_count: int,
) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    resolved_level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        timestamper,
        structlog.stdlib.add_log_level,
        _add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
        _render_with_timestamp_prefix,
    ]

    processor_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=[
            timestamper,
            structlog.stdlib.add_log_level,
            _add_logger_name,
        ],
        processors=shared_processors,
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(resolved_level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(processor_formatter)
    console_handler.setLevel(resolved_level)
    root_logger.addHandler(console_handler)

    if log_to_file:
        target_dir = Path(log_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=target_dir / log_file_name,
            maxBytes=max(log_file_max_bytes, 1024),
            backupCount=max(log_file_backup_count, 1),
            encoding="utf-8",
        )
        file_handler.setFormatter(processor_formatter)
        file_handler.setLevel(resolved_level)
        root_logger.addHandler(file_handler)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
