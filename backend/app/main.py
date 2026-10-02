"""
Secure Data Portal — FastAPI entrypoint.

Security layers active on every request, in order:
  1. IPAllowlistMiddleware  — rejects disallowed source IPs (app-level; nginx
                               config in /nginx provides a second layer)
  2. CORSMiddleware         — restricts which frontend origins may call the API
  3. Per-route auth deps    — JWT validation + role checks (see core/deps.py)

No database is used anywhere — users live in a JSON file, uploaded data
lives in RAM (see core/data_store.py), and security events are appended to
an audit JSONL file. This matches the "no permanent DB storage" requirement.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.ip_allowlist import IPAllowlistMiddleware
from app.routers import auth, audit, data
from app.utils.watcher import sweep_old_uploads, watch_for_direct_edits


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch background tasks
    watcher_task = asyncio.create_task(watch_for_direct_edits())
    sweeper_task = asyncio.create_task(sweep_old_uploads())
    print(f"[startup] {settings.APP_NAME} running in '{settings.ENV}' mode")
    if settings.allowed_ips_list:
        print(f"[startup] IP allowlist active: {settings.allowed_ips_list}")
    else:
        print("[startup] WARNING: No IP allowlist configured — open to all IPs. Set ALLOWED_IPS in production.")
    yield
    # Shutdown
    watcher_task.cancel()
    sweeper_task.cancel()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# ── Middleware (order matters: outermost added last in Starlette) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(IPAllowlistMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never leak stack traces / internals to the client
    print(f"[error] Unhandled exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. The incident has been logged."},
    )


app.include_router(auth.router)
app.include_router(audit.router)
app.include_router(data.router)


@app.get("/health")
async def health():
    """Unauthenticated health check — exempt from IP allowlist for load balancers."""
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/")
async def root():
    return {
        "message": f"{settings.APP_NAME} API",
        "docs": "/docs",
        "health": "/health",
    }
