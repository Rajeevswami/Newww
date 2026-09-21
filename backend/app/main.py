from contextlib import asynccontextmanager
import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.database import engine
from app.models.entities import Base
from app.api import admin, auth, billing, core
from app.services.seed import seed_demo


def _sentry_before_send(event, hint):
    request = event.get("request") or {}
    headers = request.get("headers") or {}
    for key in list(headers):
        if str(key).lower() in {"authorization", "cookie"}:
            headers[key] = "[redacted]"
    request["headers"] = headers
    event["request"] = request
    if "user" in event and isinstance(event["user"], dict):
        event["user"].pop("email", None)
    return event


if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        send_default_pii=False,
        before_send=_sentry_before_send,
    )


@asynccontextmanager
async def lifespan(app):
    if settings.environment != "production":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    if settings.demo_mode:
        await seed_demo()
    try:
        from app.ai.vectors import ensure_collections

        ensure_collections()
    except Exception:
        if settings.environment == "production":
            raise
    yield
    await engine.dispose()


app = FastAPI(
    title="SmartHire AI",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        if settings.sentry_dsn:
            sentry_sdk.set_tag("tenant_id", getattr(request.state, "tenant_id", None))
            sentry_sdk.capture_exception()
        raise
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


Instrumentator(excluded_handlers=["/api/metrics", "/api/health"]).instrument(app).expose(
    app, endpoint="/api/metrics", include_in_schema=False
)

for router in (auth.router, core.router, billing.router, admin.router):
    app.include_router(router, prefix="/api")


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "demo": settings.demo_mode,
        "ai_mode": "OpenAI" if settings.openai_api_key else "Demo",
    }
