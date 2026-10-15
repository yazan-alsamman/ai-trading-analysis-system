from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("trading", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_serializer="json", result_serializer="json", timezone="UTC")


@celery_app.task(name="ping")
def ping() -> str:
    return "pong"
