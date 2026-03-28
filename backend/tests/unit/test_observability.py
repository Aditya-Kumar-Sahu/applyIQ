from __future__ import annotations

from app.core.config import Settings
from app.core.observability import configure_observability


def test_configure_observability_is_noop_without_dsn(monkeypatch) -> None:
    called = {"value": False}

    def fake_init(*args, **kwargs):  # noqa: ANN002, ANN003
        called["value"] = True

    monkeypatch.setattr("app.core.observability.sentry_sdk.init", fake_init)
    configure_observability(Settings(sentry_dsn_backend=None))
    assert called["value"] is False


def test_configure_observability_initializes_sentry_when_dsn_present(monkeypatch) -> None:
    captured = {"dsn": None}

    def fake_init(*args, **kwargs):  # noqa: ANN002, ANN003
        captured["dsn"] = kwargs.get("dsn")

    monkeypatch.setattr("app.core.observability.sentry_sdk.init", fake_init)
    configure_observability(Settings(sentry_dsn_backend="https://public@example.ingest.sentry.io/1"))
    assert captured["dsn"] == "https://public@example.ingest.sentry.io/1"
