from __future__ import annotations

from app.worker import celery_app


@celery_app.task(name="applyiq.pipeline.start")
def run_pipeline_start_task(payload: dict) -> dict:
    return payload
