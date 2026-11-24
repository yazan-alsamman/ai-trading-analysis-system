"""Notification tasks on the ``notifications`` queue (consumed by the ``worker`` service).

- ``notifications.send``: a chunk of deliveries (retries are scheduled by the service).
- ``notifications.fanout``: splits a big batch (one signal, many users) into send chunks.
- ``notifications.digests`` (beat, every minute): digests of held deliveries whose quiet hours
  or hourly cap ended, and deliveries held by an open circuit going back to the queue.
- ``notifications.sweep`` (beat, every minute): deliveries whose send task was lost go back to
  the queue (``service.sweep_stuck``).
- ``notifications.cleanup`` (beat, daily): inbox retention.
- ``notifications.broadcast``: an admin broadcast, in batches.
"""

import logging
import uuid

from app.models.notification import Severity
from app.models.user import UserRole
from app.notifications import service
from app.social import notify as social_notify
from app.tasks import celery_app
from app.tasks.signals import run_async

logger = logging.getLogger(__name__)


@celery_app.task(name="notifications.send", acks_late=True, reject_on_worker_lost=True)
def send(delivery_ids: list[str]) -> dict:
    """``acks_late``: a delivery lost with its worker is sent by the redelivered task; the row
    lock and the ``pending`` check make that safe."""
    ids = [uuid.UUID(i) for i in delivery_ids]
    return run_async(lambda factory, redis: service.send_deliveries(factory, redis, ids))


@celery_app.task(name="notifications.fanout")
def fanout(delivery_ids: list[str]) -> int:
    """Split a big batch into ``notifications.send`` chunks."""
    return service.send_chunks(delivery_ids)


@celery_app.task(name="notifications.digests")
def digests() -> dict:
    async def go(factory, redis):
        released = await service.release_circuit_holds(factory)
        counts = await service.send_digests(factory, redis)
        return {**counts, "released": released}

    result = run_async(go)
    if any(result.values()):
        logger.info("notifications.digests %s", result)
    return result


@celery_app.task(name="notifications.sweep", ignore_result=True)
def sweep() -> dict:
    """Pending deliveries no task will send (a crash after the producer's commit, a lost retry):
    enqueued again (the send claim makes a duplicate a no-op), or skipped when older than
    ``NOTIFICATION_SWEEP_MAX_AGE_SECONDS``."""
    swept = run_async(lambda factory, _redis: service.sweep_stuck(factory))
    logger.info("notifications.sweep requeued=%d expired=%d", len(swept.requeued), swept.expired)
    return {"requeued": len(swept.requeued), "expired": swept.expired}


@celery_app.task(name="notifications.cleanup")
def cleanup() -> int:
    deleted = run_async(lambda factory, _redis: service.cleanup(factory))
    logger.info("notifications.cleanup deleted=%d", deleted)
    return deleted


@celery_app.task(name="notifications.new_post")
def new_post(post_id: str) -> int:
    """``new_post`` notifications for every follower of the author, in batches."""
    count = run_async(
        lambda factory, redis: social_notify.fanout_new_post(factory, redis, uuid.UUID(post_id))
    )
    logger.info("notifications.new_post %s followers=%d", post_id, count)
    return count


@celery_app.task(name="notifications.broadcast")
def broadcast(
    broadcast_id: str, title: str, body: str, severity: str, roles: list[str] | None
) -> int:
    count = run_async(
        lambda factory, redis: service.broadcast(
            factory,
            redis,
            uuid.UUID(broadcast_id),
            title,
            body,
            Severity(severity),
            [UserRole(r) for r in roles] if roles else None,
        )
    )
    logger.info("notifications.broadcast %s recipients=%d", broadcast_id, count)
    return count
