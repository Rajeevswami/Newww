import smtplib
from email.message import EmailMessage
from celery import Celery
from app.core.config import settings

celery = Celery("smarthire", broker=settings.redis_url)


@celery.task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def send_email(address: str, subject: str, body: str):
    if not settings.smtp_host:
        raise RuntimeError("SMTP is not configured")
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = settings.email_from, address, subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
