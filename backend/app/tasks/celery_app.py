from celery import Celery
from app.core.config import settings

celery = Celery("smarthire", broker=settings.redis_url)
celery.conf.include = ["app.tasks.email", "app.tasks.ai"]
celery.conf.task_always_eager = settings.celery_eager
celery.conf.task_eager_propagates = True
