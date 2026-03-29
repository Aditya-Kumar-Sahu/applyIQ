from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime

import structlog

from app.core.logging import configure_logging


def _read_log(path: Path) -> str:
    assert path.exists()
    return path.read_text(encoding="utf-8")


def _parse_prefixed_json_line(line: str) -> tuple[str, dict[str, object]]:
    timestamp_prefix, payload = line.split(" ", 1)
    datetime.fromisoformat(timestamp_prefix.replace("Z", "+00:00"))
    return timestamp_prefix, json.loads(payload)


def test_configure_logging_writes_to_rotating_file(tmp_path: Path) -> None:
    configure_logging(
        log_level="DEBUG",
        log_to_file=True,
        log_dir=str(tmp_path),
        log_file_name="service.log",
        log_file_max_bytes=1024,
        log_file_backup_count=2,
    )

    logger = structlog.get_logger("test.logger")
    logger.info("test.logging.file_write", case="basic")

    stdlib_logger = logging.getLogger("test.stdlib")
    stdlib_logger.warning("test.logging.stdlib_message")

    log_path = tmp_path / "service.log"
    content = _read_log(log_path)
    lines = [line for line in content.splitlines() if line.strip()]
    assert len(lines) >= 2

    _, structlog_payload = _parse_prefixed_json_line(lines[-2])
    _, stdlib_payload = _parse_prefixed_json_line(lines[-1])

    assert structlog_payload["event"] == "test.logging.file_write"
    assert structlog_payload["case"] == "basic"
    assert structlog_payload["logger"] == "test.logger"
    assert structlog_payload["level"] == "info"

    assert stdlib_payload["event"] == "test.logging.stdlib_message"
    assert stdlib_payload["logger"] == "test.stdlib"
    assert stdlib_payload["level"] == "warning"


def test_configure_logging_rotates_files(tmp_path: Path) -> None:
    configure_logging(
        log_level="DEBUG",
        log_to_file=True,
        log_dir=str(tmp_path),
        log_file_name="rotate.log",
        log_file_max_bytes=500,
        log_file_backup_count=2,
    )

    logger = structlog.get_logger("test.rotate")
    for index in range(120):
        logger.info("test.logging.rotation", iteration=index, payload="x" * 40)

    rotated_files = sorted(tmp_path.glob("rotate.log*"))
    names = {file.name for file in rotated_files}
    assert "rotate.log" in names
    assert any(name.startswith("rotate.log.") for name in names)
