from typing import Optional

from pydantic import BaseModel, Field


# ── Auth ──
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    mfa_required: bool
    mfa_setup_required: bool = False
    temp_token: Optional[str] = None  # only set when mfa_required=True
    qr_provisioning_uri: Optional[str] = None  # present only on first-time MFA setup
    # ── Populated only when MFA_REQUIRED=False, so login completes in a
    # single step without a second /auth/mfa/verify round trip. All MFA
    # code paths remain intact and untouched — this is purely additive. ──
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    expires_in_minutes: Optional[int] = None


class MFAVerifyRequest(BaseModel):
    temp_token: str
    code: str = Field(..., min_length=6, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    username: str
    role: str
    expires_in_minutes: int


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str  # admin | manager | viewer


# ── Data ──
class UploadResponse(BaseModel):
    filename: str
    rows: int
    columns: list
    message: str
