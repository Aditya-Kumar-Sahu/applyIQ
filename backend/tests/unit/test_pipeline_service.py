from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import anyio

from app.core.config import Settings
from app.schemas.pipeline import PipelineApplicationItem, PipelineResultsData
from app.services.cover_letter_service import CoverLetterService
from app.services.pipeline_service import PipelineService


class _FakeDatabase:
    def __init__(self) -> None:
        self.sessions: list[object] = []

    def session(self):
        database = self

        class _SessionContext:
            async def __aenter__(self):
                session = object()
                database.sessions.append(session)
                return session

            async def __aexit__(self, exc_type, exc, tb):
                return None

        return _SessionContext()


def test_pipeline_status_stream_opens_a_fresh_session_per_poll(monkeypatch) -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6390/0",
        jwt_secret_key="test-jwt-secret-key-with-32-characters",
        fernet_secret_key="wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID=",
        encryption_pepper="pepper-for-tests",
    )

    service = PipelineService(
        graph_runner=object(),
        encryption_service=object(),
        cover_letter_service=CoverLetterService(),
        settings=settings,
    )
    database = _FakeDatabase()
    user = SimpleNamespace(id="user-1")
    responses = iter(("running", "complete"))

    async def fake_get_results(*, session, user, run_id):
        status = next(responses)
        return PipelineResultsData(
            run_id=run_id,
            status=status,
            current_node="approval_gate_node",
            jobs_found=1,
            jobs_matched=1,
            applications_submitted=0,
            started_at=datetime.now(UTC),
            completed_at=None if status != "complete" else datetime.now(UTC),
            applications=[
                PipelineApplicationItem(
                    id="application-1",
                    job_id="job-1",
                    title="ML Engineer",
                    company_name="ApplyIQ",
                    match_score=0.95,
                    cover_letter_text="Cover letter",
                    tone="formal",
                    word_count=120,
                    cover_letter_version=1,
                    status="pending_approval",
                )
            ],
        )

    monkeypatch.setattr(service, "get_results", fake_get_results)

    async def exercise() -> tuple[list[str], list[object]]:
        events: list[str] = []
        async for event in service.stream_status_events(
            database=database,
            user=user,
            run_id="run-1",
            poll_interval_seconds=0,
        ):
            events.append(event)
        return events, database.sessions

    events, sessions = anyio.run(exercise)

    assert len(events) == 2
    assert len(sessions) == 2
    assert sessions[0] != sessions[1]