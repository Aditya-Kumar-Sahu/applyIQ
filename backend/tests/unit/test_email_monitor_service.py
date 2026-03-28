from __future__ import annotations

from app.services.email_monitor_service import EmailMonitorService


def test_email_classifier_maps_recruiter_messages_to_statuses() -> None:
    service = EmailMonitorService()

    assert (
        service.classify_message(
            subject="Interview availability for Company 1",
            body="We would love to schedule an interview next week.",
        )
        == "interview_request"
    )
    assert (
        service.classify_message(
            subject="Update on your application",
            body="We regret to inform you that we will not be moving forward.",
        )
        == "rejection"
    )
    assert (
        service.classify_message(
            subject="Offer details",
            body="We are excited to extend an offer for the role.",
        )
        == "offer"
    )
