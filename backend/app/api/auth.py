from datetime import timedelta
import secrets
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.concurrency import run_in_threadpool
from app.models.entities import User, Tenant, RefreshToken, ActionToken, AuditLog, now
from app.core.database import get_db, scope_db
from app.core.config import settings
from app.core.security import access_token, digest, hash_password, verify_password, current_user
from app.schemas.requests import Login, Signup, EmailInput, TokenInput, ResetInput
from app.tasks.email import send_email

router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url if settings.environment == "production" else "memory://",
)


def user_json(user, tenant):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_verified": user.is_verified,
        "tenant": {"id": tenant.id, "name": tenant.name, "slug": tenant.slug, "plan": tenant.plan},
    }


async def session_response(db, user, response):
    raw = jwt.encode(
        {
            "sub": user.id,
            "tenant": user.tenant_id,
            "nonce": secrets.token_urlsafe(32),
            "type": "refresh",
            "exp": now() + timedelta(days=7),
        },
        settings.secret_key,
        algorithm="HS256",
    )
    db.add(
        RefreshToken(
            tenant_id=user.tenant_id,
            user_id=user.id,
            token_hash=digest(raw),
            expires_at=now() + timedelta(days=7),
        )
    )
    response.set_cookie(
        "refresh_token",
        raw,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        max_age=604800,
        path="/api/auth",
    )
    tenant = await db.get(Tenant, user.tenant_id)
    return {
        "access_token": access_token(user),
        "user": user_json(user, tenant),
        "demo": settings.demo_mode,
        "ai_mode": "OpenAI" if settings.openai_api_key else "Demo",
    }


async def make_action(db, user, purpose):
    raw = jwt.encode(
        {
            "sub": user.id,
            "tenant": user.tenant_id,
            "nonce": secrets.token_urlsafe(32),
            "type": purpose,
            "exp": now() + timedelta(hours=1),
        },
        settings.secret_key,
        algorithm="HS256",
    )
    db.add(
        ActionToken(
            tenant_id=user.tenant_id,
            user_id=user.id,
            purpose=purpose,
            token_hash=digest(raw),
            expires_at=now() + timedelta(hours=1),
        )
    )
    if settings.smtp_host:
        send_email.delay(
            user.email,
            f"SmartHire: {purpose}",
            f"{settings.frontend_url}/?action={purpose}&token={raw}",
        )
    return raw


@router.post("/signup", status_code=201)
@limiter.limit("5/minute")
async def signup(request: Request, data: Signup, response: Response, db=Depends(get_db)):
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == data.workspace))
    if data.role == "tenant_admin":
        if tenant:
            raise HTTPException(409, "This workspace URL is already taken")
        if not data.company.strip():
            raise HTTPException(422, "Company name is required")
        tenant = Tenant(name=data.company, slug=data.workspace)
        db.add(tenant)
        await db.flush()
    elif not tenant:
        raise HTTPException(404, "Workspace not found. Ask your recruiter for the workspace slug.")
    await scope_db(db, tenant.id)
    user = User(
        tenant_id=tenant.id,
        name=data.name,
        email=data.email.lower(),
        hashed_password=await run_in_threadpool(hash_password, data.password),
        role=data.role,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(409, "An account with this email already exists")
    token = await make_action(db, user, "verify")
    result = await session_response(db, user, response)
    if settings.demo_mode:
        result["verification_token"] = token
    return result


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, data: Login, response: Response, db=Depends(get_db)):
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == data.workspace))
    if not tenant:
        raise HTTPException(401, "Invalid workspace, email, or password")
    await scope_db(db, tenant.id)
    user = await db.scalar(
        select(User).where(User.tenant_id == tenant.id, User.email == data.email.lower())
    )
    if not user or not await run_in_threadpool(
        verify_password, data.password, user.hashed_password
    ):
        raise HTTPException(401, "Invalid workspace, email, or password")
    db.add(AuditLog(tenant_id=user.tenant_id, user_id=user.id, action="auth.login"))
    return await session_response(db, user, response)


def decode_context(raw, kind):
    try:
        data = jwt.decode(
            raw,
            settings.secret_key,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "tenant", "type"]},
        )
        if data["type"] != kind:
            raise ValueError()
        return data
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "Invalid or expired token")


@router.post("/refresh")
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db=Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(401, "No active session")
    context = decode_context(refresh_token, "refresh")
    await scope_db(db, context["tenant"])
    row = (
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == digest(refresh_token),
                RefreshToken.tenant_id == context["tenant"],
                RefreshToken.revoked == False,
                RefreshToken.expires_at > now(),
            )
            .values(revoked=True)
            .returning(RefreshToken.user_id)
        )
    ).first()
    if not row:
        raise HTTPException(401, "Refresh token already used or revoked")
    user = await db.scalar(
        select(User).where(User.id == row[0], User.tenant_id == context["tenant"])
    )
    if not user:
        raise HTTPException(401, "Account not found")
    return await session_response(db, user, response)


@router.post("/logout")
async def logout(response: Response, user=Depends(current_user), db=Depends(get_db)):
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.tenant_id == user.tenant_id)
        .values(revoked=True)
    )
    user.token_version += 1
    response.delete_cookie("refresh_token", path="/api/auth")
    return {"ok": True}


@router.get("/me")
async def me(user=Depends(current_user), db=Depends(get_db)):
    return user_json(user, await db.get(Tenant, user.tenant_id))


@router.post("/demo")
@limiter.limit("30/minute")
async def demo(request: Request, response: Response, role: str = "recruiter", db=Depends(get_db)):
    if not settings.demo_mode:
        raise HTTPException(404, "Not found")
    if role not in ("recruiter", "candidate"):
        raise HTTPException(422, "Choose recruiter or candidate")
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == "acme"))
    await scope_db(db, tenant.id)
    user = await db.scalar(
        select(User).where(
            User.tenant_id == tenant.id,
            User.email == ("alex@acme.design" if role == "recruiter" else "sarah.chen@example.com"),
        )
    )
    return await session_response(db, user, response)


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot(request: Request, data: EmailInput, db=Depends(get_db)):
    result = {"message": "If that account exists, a reset link has been sent."}
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == data.workspace))
    if tenant:
        await scope_db(db, tenant.id)
        user = await db.scalar(
            select(User).where(User.email == data.email.lower(), User.tenant_id == tenant.id)
        )
        if user:
            token = await make_action(db, user, "reset")
            if settings.demo_mode:
                result["reset_token"] = token
    return result


async def consume_action(db, raw, purpose):
    context = decode_context(raw, purpose)
    await scope_db(db, context["tenant"])
    row = (
        await db.execute(
            update(ActionToken)
            .where(
                ActionToken.tenant_id == context["tenant"],
                ActionToken.token_hash == digest(raw),
                ActionToken.purpose == purpose,
                ActionToken.used == False,
                ActionToken.expires_at > now(),
            )
            .values(used=True)
            .returning(ActionToken.user_id)
        )
    ).first()
    if not row:
        raise HTTPException(400, "This link was already used or has expired")
    return await db.scalar(
        select(User).where(User.id == row[0], User.tenant_id == context["tenant"])
    )


@router.post("/verify-email")
async def verify_email(data: TokenInput, db=Depends(get_db)):
    user = await consume_action(db, data.token, "verify")
    user.is_verified = True
    return {"message": "Email verified"}


@router.post("/reset-password")
async def reset_password(data: ResetInput, db=Depends(get_db)):
    user = await consume_action(db, data.token, "reset")
    user.hashed_password = await run_in_threadpool(hash_password, data.password)
    user.token_version += 1
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.tenant_id == user.tenant_id)
        .values(revoked=True)
    )
    return {"message": "Password reset. You can now sign in."}
