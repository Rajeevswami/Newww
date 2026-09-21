"""API keys with RLS, resume status, and nullable match scores."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    if "api_keys" not in tables:
        op.create_table(
            "api_keys",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False
            ),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("key_hash", sa.String(length=64), nullable=False, unique=True),
            sa.Column("scopes", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
        op.create_index("ix_api_keys_tenant_id_id", "api_keys", ["tenant_id", "id"])
    resume_columns = {column["name"] for column in inspector.get_columns("resumes")}
    if "status" not in resume_columns:
        op.add_column(
            "resumes",
            sa.Column("status", sa.String(length=20), nullable=False, server_default="ready"),
        )
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE applications ALTER COLUMN match_score DROP NOT NULL")
        op.execute('ALTER TABLE "api_keys" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "api_keys" FORCE ROW LEVEL SECURITY')
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE tablename = 'api_keys' AND policyname = 'tenant_isolation'
                ) THEN
                    CREATE POLICY tenant_isolation ON "api_keys"
                    USING (tenant_id = current_setting('app.tenant_id', true))
                    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
                END IF;
            END $$;
            """
        )


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "api_keys" in inspector.get_table_names():
        op.drop_table("api_keys")
