"""Real database-level isolation check. Requires an isolated, migrated PostgreSQL DB.
Unlike application tests, deliberately issues an unscoped SELECT under a non-owner.
"""

import asyncio
import os
import asyncpg


async def main():
    conn = await asyncpg.connect(os.environ["RLS_DATABASE_URL"])
    transaction = conn.transaction()
    await transaction.start()
    try:
        await conn.execute("CREATE ROLE smarthire_rls_test NOLOGIN NOSUPERUSER NOBYPASSRLS")
        await conn.execute("GRANT USAGE ON SCHEMA public TO smarthire_rls_test")
        await conn.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO smarthire_rls_test"
        )
        for tenant in ("tenant-a", "tenant-b"):
            await conn.execute(
                "INSERT INTO tenants(id,name,slug,plan,created_at) VALUES ($1,$1,$1,'Free',now())",
                tenant,
            )
            await conn.execute(
                "INSERT INTO users(id,tenant_id,name,email,hashed_password,role,is_verified,token_version,created_at) VALUES($1,$2,'Test','test@example.com','unused','candidate',true,0,now())",
                "user-" + tenant,
                tenant,
            )
        await conn.execute("SET LOCAL ROLE smarthire_rls_test")
        assert await conn.fetchval("SELECT count(*) FROM users") == 0, (
            "Unset context must deny all rows"
        )
        await conn.execute("SELECT set_config('app.tenant_id', 'tenant-a', true)")
        rows = await conn.fetch("SELECT id,tenant_id FROM users")
        assert len(rows) == 1 and rows[0]["tenant_id"] == "tenant-a"
        assert await conn.fetchval("SELECT count(*) FROM users WHERE tenant_id='tenant-b'") == 0
        result = await conn.execute("UPDATE users SET name='Attack' WHERE tenant_id='tenant-b'")
        assert result == "UPDATE 0"
        savepoint = conn.transaction()
        await savepoint.start()
        try:
            await conn.execute(
                "INSERT INTO users(id,tenant_id,name,email,hashed_password,role,is_verified,token_version,created_at) VALUES('attack','tenant-b','Test','attack@example.com','unused','candidate',true,0,now())"
            )
            raise AssertionError("Cross-tenant INSERT must fail")
        except asyncpg.InsufficientPrivilegeError:
            await savepoint.rollback()
        await conn.execute("SELECT set_config('app.tenant_id', 'tenant-b', true)")
        rows = await conn.fetch("SELECT id,tenant_id FROM users")
        assert len(rows) == 1 and rows[0]["tenant_id"] == "tenant-b"
        print("PASS: PostgreSQL RLS denies unset context, cross-tenant reads, updates, and inserts")
    finally:
        await transaction.rollback()
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
