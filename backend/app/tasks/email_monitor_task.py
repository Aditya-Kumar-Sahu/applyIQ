from __future__ import annotations

from app.worker import celery_app


@celery_app.task(name="applyiq.email-monitor.sync")
def run_email_monitor_task(payload: dict) -> dict:
    return payload
