"""
Authentication endpoints.

Login flow:
  1. POST /auth/login          → checks username + password
                                  → if correct: issues a short-lived `temp_token`
                                  → if user has no TOTP secret confirmed yet: returns
                                    qr_provisioning_uri so the frontend can show a QR code
  2. POST /auth/mfa/verify      → checks the 6-digit TOTP code against temp_token's user
                                  → issues real access_token + refresh_token on success
  3. POST /auth/refresh         → exchanges a valid refresh_token for a new access_token
  4. POST /auth/logout          → client discards tokens; we just log the event
                                   (stateless JWTs — true server-side revocation would need
                                    a blocklist store, noted as a future enhancement)
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError

from app.core.audit import log_event
from app.core.config import settings
from app.core.deps import get_current_user, require_role
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_totp_secret,
    get_totp_uri,
    hash_password,
    validate_password_strength,
    verify_password,
    verify_totp,
)
from app.core.user_store import (
    create_user,
    get_user,
    is_locked,
    list_users,
    record_failed_attempt,
    reset_failed_attempts,
    update_user,
)
from app.schemas import (
    ChangePasswordRequest,
    CreateUserRequest,
    LoginRequest,
    LoginResponse,
    MFAVerifyRequest,
    RefreshRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return getattr(request.state, "client_ip", request.client.host if request.client else "unknown")


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request):
    ip = _client_ip(request)
    user = get_user(payload.username)

    # Always do a dummy hash comparison even if user doesn't exist —
    # prevents timing attacks that reveal whether a username is valid.
    if not user:
        verify_password(payload.password, "$2b$12$invalidinvalidinvalidinvalidinvalidinvalidinvalidinv")
        log_event("login_failed", payload.username, ip, "Unknown username", success=False)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    if is_locked(user):
        log_event("login_failed", payload.username, ip, "Account locked", success=False)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked due to repeated failed attempts. Try again after {settings.ACCOUNT_LOCKOUT_MINUTES} minutes.",
        )

    if not verify_password(payload.password, user["password_hash"]):
        attempts = record_failed_attempt(payload.username)
        remaining = max(0, settings.MAX_FAILED_LOGIN_ATTEMPTS - attempts)
        log_event("login_failed", payload.username, ip, f"Wrong password (attempt {attempts})", success=False)

        if remaining == 0:
            log_event("account_locked", payload.username, ip, "Max failed attempts reached", success=False)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked after {settings.MAX_FAILED_LOGIN_ATTEMPTS} failed attempts. Try again in {settings.ACCOUNT_LOCKOUT_MINUTES} minutes.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid username or password. {remaining} attempt(s) remaining before lockout.",
        )

    # ── MFA temporarily disabled (settings.MFA_REQUIRED = False) ──────────
    # Skip the temp_token/QR/second-step flow entirely and log the user in
    # immediately with real tokens. The full MFA implementation below is
    # left completely intact — flipping MFA_REQUIRED back to True in
    # config.py re-enables it with no other code changes needed.
    if not settings.MFA_REQUIRED:
        reset_failed_attempts(payload.username)
        log_event("login_success", payload.username, ip, "Login OK (MFA disabled)", success=True)

        access_token = create_access_token({"sub": user["username"], "role": user["role"]})
        refresh_token = create_refresh_token({"sub": user["username"]})

        return LoginResponse(
            mfa_required=False,
            access_token=access_token,
            refresh_token=refresh_token,
            username=user["username"],
            role=user["role"],
            expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )

    # Password correct — issue a short-lived temp token to complete MFA
    temp_token = create_access_token({"sub": user["username"], "stage": "mfa_pending"}, expires_minutes=5)

    mfa_setup_required = not user.get("mfa_verified", False)
    qr_uri = None
    if mfa_setup_required:
        qr_uri = get_totp_uri(user["username"], user["totp_secret"])

    log_event("login_password_ok", payload.username, ip, "Password verified, awaiting MFA", success=True)

    return LoginResponse(
        mfa_required=True,
        mfa_setup_required=mfa_setup_required,
        temp_token=temp_token,
        qr_provisioning_uri=qr_uri,
    )


@router.post("/mfa/verify", response_model=TokenResponse)
async def verify_mfa(payload: MFAVerifyRequest, request: Request):
    ip = _client_ip(request)
    try:
        claims = decode_token(payload.temp_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired, please log in again")

    if claims.get("stage") != "mfa_pending":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session state")

    username = claims.get("sub")
    user = get_user(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not verify_totp(user["totp_secret"], payload.code):
        log_event("mfa_failed", username, ip, "Invalid TOTP code", success=False)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication code")

    # Mark MFA as confirmed on first successful verification
    if not user.get("mfa_verified", False):
        update_user(username, mfa_verified=True)

    reset_failed_attempts(username)
    log_event("login_success", username, ip, "MFA verified", success=True)

    access_token = create_access_token({"sub": username, "role": user["role"]})
    refresh_token = create_refresh_token({"sub": username})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        username=username,
        role=user["role"],
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, request: Request):
    ip = _client_ip(request)
    try:
        claims = decode_token(payload.refresh_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired, please log in again")

    if claims.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    username = claims.get("sub")
    user = get_user(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_access = create_access_token({"sub": username, "role": user["role"]})
    new_refresh = create_refresh_token({"sub": username})
    log_event("token_refreshed", username, ip, "Access token refreshed", success=True)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        username=username,
        role=user["role"],
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@router.post("/logout")
async def logout(request: Request, user: dict = Depends(get_current_user)):
    ip = _client_ip(request)
    log_event("logout", user["username"], ip, "User logged out", success=True)
    return {"message": "Logged out successfully"}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "username": user["username"],
        "role": user["role"],
        "last_login": user.get("last_login"),
        "mfa_enabled": user.get("mfa_enabled", True),
    }


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    ip = _client_ip(request)
    if not verify_password(payload.current_password, user["password_hash"]):
        log_event("password_change_failed", user["username"], ip, "Wrong current password", success=False)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

    err = validate_password_strength(payload.new_password)
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    update_user(user["username"], password_hash=hash_password(payload.new_password))
    log_event("password_changed", user["username"], ip, "Password changed successfully", success=True)
    return {"message": "Password changed successfully"}


# ── Admin-only user management ──
@router.post("/users", dependencies=[Depends(require_role("admin"))])
async def create_new_user(payload: CreateUserRequest, request: Request, admin: dict = Depends(get_current_user)):
    if payload.role not in ("admin", "manager", "viewer"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be admin, manager, or viewer")

    err = validate_password_strength(payload.password)
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    if get_user(payload.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    secret = generate_totp_secret()
    create_user(payload.username, hash_password(payload.password), payload.role, secret)
    log_event("user_created", admin["username"], _client_ip(request), f"Created user '{payload.username}' with role '{payload.role}'", success=True)
    return {"message": f"User '{payload.username}' created successfully"}


@router.get("/users", dependencies=[Depends(require_role("admin"))])
async def get_all_users():
    users = list_users()
    return [
        {
            "username": u["username"],
            "role": u["role"],
            "last_login": u.get("last_login"),
            "mfa_verified": u.get("mfa_verified", False),
            "locked": is_locked(u),
            "failed_attempts": u.get("failed_attempts", 0),
            "created_at": u.get("created_at"),
        }
        for u in users
    ]


@router.post("/users/{username}/unlock", dependencies=[Depends(require_role("admin"))])
async def unlock_user(username: str, request: Request, admin: dict = Depends(get_current_user)):
    target = get_user(username)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    update_user(username, failed_attempts=0, locked_until=None)
    log_event("user_unlocked", admin["username"], _client_ip(request), f"Unlocked user '{username}'", success=True)
    return {"message": f"User '{username}' unlocked"}
