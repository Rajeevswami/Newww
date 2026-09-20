import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./smarthire.db"
    secret_key: str = ""
    demo_mode: bool = True
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = ""
    redis_url: str = "redis://localhost:6379/0"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@smarthire.example"


settings = Settings()
if settings.environment == "production":
    if len(settings.secret_key) < 32 or settings.demo_mode:
        raise RuntimeError("Production requires a 32+ character SECRET_KEY and DEMO_MODE=false")
    if not settings.database_url.startswith("postgresql+asyncpg:"):
        raise RuntimeError("Production requires PostgreSQL")
    if not settings.openai_api_key or not settings.smtp_host:
        raise RuntimeError(
            "Production requires OPENAI_API_KEY and SMTP_HOST; demo AI and undelivered verification emails are not allowed"
        )
    if not settings.frontend_url.startswith("https://"):
        raise RuntimeError("Production requires HTTPS")
if not settings.secret_key:
    settings.secret_key = secrets.token_urlsafe(48)
