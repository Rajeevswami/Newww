from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with Session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def scope_db(db, tenant_id):
    if engine.dialect.name == "postgresql":
        await db.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": tenant_id}
        )
