from datetime import timedelta
import hashlib
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_db, scope_db
from app.models.entities import User, now

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


async def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db=Depends(get_db),
):
    if not credentials:
        raise HTTPException(401, "Sign in to continue")
    try:
        payload = jwt.decode(
            credentials.credentials,
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
    request.state.tenant_id = user.tenant_id
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
