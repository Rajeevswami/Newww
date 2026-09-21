from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from app.core.database import get_db, scope_db
from app.core.security import super_admin
from app.models.entities import Tenant, User
from app.schemas.requests import PlanInput

router = APIRouter(prefix="/admin", tags=["Platform"])


@router.get("/tenants")
async def list_tenants(user=Depends(super_admin), db=Depends(get_db)):
    tenants = (await db.scalars(select(Tenant).order_by(Tenant.created_at.desc()))).all()
    rows = []
    for tenant in tenants:
        await scope_db(db, tenant.id)
        users = await db.scalar(
            select(func.count()).select_from(User).where(User.tenant_id == tenant.id)
        )
        rows.append(
            {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "plan": tenant.plan,
                "user_count": users or 0,
                "created_at": tenant.created_at,
            }
        )
    await scope_db(db, user.tenant_id)
    return rows


@router.patch("/tenants/{tenant_id}/plan")
async def override_plan(
    tenant_id: str, data: PlanInput, user=Depends(super_admin), db=Depends(get_db)
):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    tenant.plan = data.plan
    return {"id": tenant.id, "slug": tenant.slug, "plan": tenant.plan}
