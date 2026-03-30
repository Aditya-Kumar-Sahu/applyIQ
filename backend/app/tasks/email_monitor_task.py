from __future__ import annotations

import anyio
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import DatabaseManager
from app.core.security import EncryptionService
from app.models.user import User
from app.services.email_monitor_service import EmailMonitorService
from app.worker import celery_app


async def _poll_all_users() -> dict:
    settings = get_settings()
    database = DatabaseManager(settings.database_url)
    encryption_service = EncryptionService(
        fernet_secret_key=settings.fernet_secret_key,
        encryption_pepper=settings.encryption_pepper,
    )
    service = EmailMonitorService()
    total_processed = 0
    total_notifications = 0
    polled_users = 0

    try:
        async with database.session() as session:
            users = list(await session.scalars(select(User).where(User.is_active.is_(True))))
            for user in users:
                try:
                    result = await service.poll_inbox_with_stats(
                        session=session,
                        user=user,
                        encryption_service=encryption_service,
                        settings=settings,
                    )
                    if result.polled:
                        polled_users += 1
                    total_processed += result.processed_messages
                    total_notifications += len(result.notifications.items)
                except Exception:
                    await session.rollback()
                    continue
        return {
            "polled_users": polled_users,
            "processed_messages": total_processed,
            "matched_notifications": total_notifications,
        }
    finally:
        await database.dispose()


@celery_app.task(name="applyiq.email-monitor.poll_all_users")
def poll_all_users() -> dict:
    return anyio.run(_poll_all_users)


run_email_monitor_task = poll_all_users
