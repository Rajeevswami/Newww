import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-only-key-not-for-production-use-12345"
os.environ["DEMO_MODE"] = "true"
os.environ["OPENAI_API_KEY"] = ""
os.environ["ENVIRONMENT"] = "development"
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import engine
from app.models.entities import Base
from app.services.seed import seed_demo
from app.api.auth import limiter

limiter.enabled = False


@pytest_asyncio.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await seed_demo()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await engine.dispose()


async def demo(client, role="recruiter"):
    response = await client.post("/api/auth/demo", params={"role": role})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
