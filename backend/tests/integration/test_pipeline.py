from __future__ import annotations

from io import BytesIO
from pathlib import Path

import anyio
from docx import Document
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.base import Base


def test_pipeline_start_pause_edit_approve_and_complete(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'pipeline.db'}",
        redis_url="redis://localhost:6395/0",
        jwt_secret_key="test-jwt-secret-key-with-32-characters",
        fernet_secret_key="wWKJg6WVKwwhFVWG2yt30YIOCwVDDDeWGPAHDLcGRID=",
        encryption_pepper="pepper-for-tests",
    )

    async def healthy_reporter() -> dict[str, str]:
        return {"status": "ok", "db": "up", "redis": "up"}

    app = create_app(settings=settings, health_reporter=healthy_reporter)

    with TestClient(app) as client:
        anyio.run(_create_all_tables, app.state.database.engine)
        _register_and_prepare_resume(client)

        start_response = client.post(
            "/api/v1/pipeline/start",
            json={
                "target_role": "ML Engineer",
                "location": "Remote",
                "limit_per_source": 10,
                "sources": ["linkedin", "indeed", "remotive"],
            },
        )

        assert start_response.status_code == 202
        start_payload = start_response.json()["data"]
        assert start_payload["status"] == "paused_at_gate"
        assert start_payload["current_node"] == "approval_gate_node"
        assert start_payload["pending_approvals_count"] == 5

        run_id = start_payload["run_id"]

        status_response = client.get(f"/api/v1/pipeline/{run_id}/status")

        assert status_response.status_code == 200
        assert status_response.headers["content-type"].startswith("text/event-stream")
        assert "approval_gate_node" in status_response.text

        results_response = client.get(f"/api/v1/pipeline/{run_id}/results")

        assert results_response.status_code == 200
        results_payload = results_response.json()["data"]
        assert results_payload["status"] == "paused_at_gate"
        assert len(results_payload["applications"]) == 5

        application_id = results_payload["applications"][0]["id"]
        rejected_application_id = results_payload["applications"][1]["id"]

        edit_response = client.put(
            f"/api/v1/pipeline/{run_id}/application/{application_id}/cover-letter",
            json={"cover_letter_text": "A sharper, edited cover letter for the approval gate."},
        )

        assert edit_response.status_code == 200
        assert edit_response.json()["data"]["cover_letter_version"] == 2

        reject_response = client.post(
            f"/api/v1/pipeline/{run_id}/reject",
            json={"application_ids": [rejected_application_id]},
        )

        assert reject_response.status_code == 200
        assert reject_response.json()["data"]["rejected_count"] == 1

        approve_response = client.post(
            f"/api/v1/pipeline/{run_id}/approve",
            json={"application_ids": [application_id]},
        )

        assert approve_response.status_code == 200
        approve_payload = approve_response.json()["data"]
        assert approve_payload["status"] == "complete"
        assert approve_payload["applications_submitted"] == 1

        completed_results = client.get(f"/api/v1/pipeline/{run_id}/results")

        assert completed_results.status_code == 200
        completed_payload = completed_results.json()["data"]
        assert completed_payload["status"] == "complete"
        assert any(app["status"] == "approved" for app in completed_payload["applications"])
        assert any(app["status"] == "rejected" for app in completed_payload["applications"])


async def _create_all_tables(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


def _register_and_prepare_resume(client: TestClient) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "pipeline-user@example.com",
            "password": "SuperSecret123!",
            "full_name": "Pipeline User",
        },
    )

    assert register_response.status_code == 201

    upload_response = client.post(
        "/api/v1/resume/upload",
        files={
            "file": (
                "resume.docx",
                _build_resume_docx(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert upload_response.status_code == 201

    preferences_response = client.put(
        "/api/v1/resume/preferences",
        json={
            "target_roles": ["ML Engineer", "AI Engineer"],
            "preferred_locations": ["Remote", "Bengaluru"],
            "remote_preference": "remote",
            "salary_min": 2500000,
            "salary_max": 4000000,
            "currency": "INR",
            "excluded_companies": [],
            "seniority_level": "senior",
            "is_active": True,
        },
    )

    assert preferences_response.status_code == 200


def _build_resume_docx() -> bytes:
    document = Document()
    document.add_paragraph("Pipeline User")
    document.add_paragraph("pipeline-user@example.com")
    document.add_paragraph("Senior ML Engineer")
    document.add_paragraph("Skills: Python, FastAPI, PostgreSQL, Docker, LangGraph")
    document.add_paragraph("Experience")
    document.add_paragraph("Acme AI | Senior ML Engineer | 2021-Present")
    document.add_paragraph("Built an automation pipeline that reduced review time by 42 percent.")
    document.add_paragraph("Education")
    document.add_paragraph("B.Tech Computer Science | ABC University | 2020")

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
