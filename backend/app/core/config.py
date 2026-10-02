"""
Central configuration — everything environment-specific lives here.
Loaded from `.env` (see .env.example for all available keys).
"""
import os
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    # ── App ──
    APP_NAME: str = "Secure Data Portal"
    ENV: str = "development"  # development | production

    # ── JWT / Sessions ──
    JWT_SECRET: str = "CHANGE_ME_IN_PRODUCTION_32_CHAR_MIN"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours = working session ceiling
    SESSION_IDLE_TIMEOUT_MINUTES: int = 15      # auto-logout after inactivity

    # ── Login security ──
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15
    MIN_PASSWORD_LENGTH: int = 12

    # ── MFA ──
    MFA_ISSUER_NAME: str = "SecureDataPortal"
    MFA_REQUIRED: bool = False  # 2FA temporarily disabled — set True to re-enable

    # ── IP Allowlist ──
    # Comma-separated list of allowed IPs/CIDRs, e.g. "203.0.113.5,10.0.0.0/24"
    # Leave empty ("") to disable IP restriction (NOT recommended in production).
    ALLOWED_IPS: str = ""
    TRUST_PROXY_HEADERS: bool = True  # trust X-Forwarded-For (set False if no reverse proxy)

    # ── CORS ──
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # ── File upload ──
    MAX_UPLOAD_SIZE_MB: int = 25
    UPLOAD_RETENTION_HOURS: int = 24  # auto-delete uploaded files after this long
    UPLOAD_DIR: str = str(BASE_DIR / "app" / "data" / "uploads")

    # ── User store ──
    USERS_FILE: str = str(BASE_DIR / "app" / "data" / "users.json")
    AUDIT_LOG_FILE: str = str(BASE_DIR / "app" / "data" / "audit_log.jsonl")

    @property
    def allowed_ips_list(self) -> List[str]:
        return [ip.strip() for ip in self.ALLOWED_IPS.split(",") if ip.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
