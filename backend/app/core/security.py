from datetime import timedelta
import hashlib
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_db, scope_db
from app.models.entities import User, ApiKey, now

bearer = HTTPBearer(auto_error=False)


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def access_token(user):
    return jwt.encode(
        {
            "sub": user.id,
            "tenant": user.tenant_id,
            "type": "access",
            "ver": user.token_version,
            "exp": now() + timedelta(minutes=15),
        },
        settings.secret_key,
        algorithm="HS256",
    )


class ApiKeyPrincipal:
    auth_type = "api_key"
    role = "api_key"
    token_version = 0
    is_verified = True

    def __init__(self, key: ApiKey):
        self.id = key.id
        self.tenant_id = key.tenant_id
        self.scopes = list(key.scopes or [])
        self.name = key.name
        self.email = f"apikey:{key.id}"


async def user_from_access_token(raw: str, db):
    try:
        payload = jwt.decode(
            raw,
            settings.secret_key,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "tenant", "type"]},
        )
        if payload["type"] != "access":
            raise ValueError()
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    await scope_db(db, payload["tenant"])
    user = await db.scalar(
        select(User).where(User.id == payload["sub"], User.tenant_id == payload["tenant"])
    )
    if not user or payload.get("ver") != user.token_version:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    return user


async def principal_from_api_key(raw: str, db, request: Request | None = None):
    try:
        body = raw[3:] if raw.startswith("sk_") else ""
        tenant_id, _secret = body.split(".", 1)
        if len(tenant_id) != 36:
            raise ValueError()
    except ValueError:
        raise HTTPException(401, "Invalid API key")
    await scope_db(db, tenant_id)
    key = await db.scalar(
        select(ApiKey).where(
            ApiKey.key_hash == digest(raw),
            ApiKey.tenant_id == tenant_id,
            ApiKey.revoked == False,
        )
    )
    if not key:
        raise HTTPException(401, "Invalid API key")
    key.last_used_at = now()
    if request is not None:
        request.state.tenant_id = key.tenant_id
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.set_tag("tenant_id", key.tenant_id)
    return ApiKeyPrincipal(key)


def has_scope(user, *needed):
    if getattr(user, "auth_type", "jwt") != "api_key":
        return True
    scopes = set(getattr(user, "scopes", []) or [])
    if "*" in scopes:
        return True
    return any(item in scopes for item in needed)


def require_scopes(*needed):
    async def dependency(user=Depends(current_user)):
        if not has_scope(user, *needed):
            raise HTTPException(403, "API key lacks the required scope")
        return user

    return dependency


async def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db=Depends(get_db),
):
    if not credentials:
        raise HTTPException(401, "Sign in to continue")
    raw = credentials.credentials
    if raw.startswith("sk_"):
        return await principal_from_api_key(raw, db, request)
    user = await user_from_access_token(raw, db)
    request.state.tenant_id = user.tenant_id
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.set_tag("tenant_id", user.tenant_id)
    return user


async def recruiter(user=Depends(current_user)):
    if user.role not in ("tenant_admin", "recruiter"):
        raise HTTPException(403, "Recruiter access required")
    return user


async def admin(user=Depends(current_user)):
    if user.role != "tenant_admin":
        raise HTTPException(403, "Workspace administrator access required")
    return user


async def candidate(user=Depends(current_user)):
    if user.role != "candidate":
        raise HTTPException(403, "Candidate access required")
    return user


async def super_admin(user=Depends(current_user)):
    if user.role != "super_admin":
        raise HTTPException(403, "Platform administrator access required")
    return user
