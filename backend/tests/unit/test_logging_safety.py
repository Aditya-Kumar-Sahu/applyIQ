from __future__ import annotations

from app.core.logging_safety import bytes_snapshot, sanitize_for_logging, text_snapshot


def test_sanitize_for_logging_redacts_sensitive_keys() -> None:
    payload = {
        "username": "user@example.com",
        "password": "super-secret",
        "nested": {
            "api_key": "abc123",
            "token_value": "def456",
        },
    }

    sanitized = sanitize_for_logging(payload)

    assert sanitized["username"] == "user@example.com"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["nested"]["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["token_value"] == "[REDACTED]"


def test_text_snapshot_reports_hash_preview_and_length() -> None:
    value = "sample text for snapshot"
    snapshot = text_snapshot(value)

    assert snapshot["length"] == len(value)
    assert isinstance(snapshot["sha256"], str)
    assert len(snapshot["sha256"]) == 16
    assert snapshot["preview"].startswith("sample text")


def test_bytes_snapshot_reports_size_and_hash() -> None:
    value = b"binary-content"
    snapshot = bytes_snapshot(value)

    assert snapshot["size"] == len(value)
    assert isinstance(snapshot["sha256"], str)
    assert len(snapshot["sha256"]) == 16
