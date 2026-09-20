"""Initial workspace schema with forced PostgreSQL row-level security."""

from alembic import op
from app.models.entities import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    if bind.dialect.name == "postgresql":
        for table in Base.metadata.sorted_tables:
            if "tenant_id" in table.columns:
                # Identifiers come exclusively from internal model metadata, never user input.
                name = table.name
                op.execute(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY')
                op.execute(f'ALTER TABLE "{name}" FORCE ROW LEVEL SECURITY')
                op.execute(
                    f'''CREATE POLICY tenant_isolation ON "{name}" USING (tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (tenant_id = current_setting('app.tenant_id', true))'''
                )


def downgrade():
    Base.metadata.drop_all(op.get_bind())
