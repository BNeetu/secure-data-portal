"""
IP allowlist middleware — rejects any request whose client IP is not in
settings.ALLOWED_IPS (supports single IPs and CIDR ranges).

This is the app-level layer of defense. A reverse-proxy (nginx) config is
also provided in /nginx for a second layer that blocks traffic before it
ever reaches this process.

If ALLOWED_IPS is empty, the middleware is a no-op (open access) — useful
for local development. Always set ALLOWED_IPS in production.
"""
import ipaddress
from typing import Callable

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.audit import log_event


def _get_client_ip(request: Request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # X-Forwarded-For can be a comma-separated chain; first = original client
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _ip_allowed(ip: str, allowlist: list) -> bool:
    if not allowlist:
        return True  # no restriction configured
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError:
        return False

    for entry in allowlist:
        try:
            if "/" in entry:
                if ip_obj in ipaddress.ip_network(entry, strict=False):
                    return True
            else:
                if ip_obj == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            continue
    return False


class IPAllowlistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        # Always allow CORS preflight through (browsers strip these before retry)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Allow health checks through unconditionally (used by load balancers)
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = _get_client_ip(request)
        allowlist = settings.allowed_ips_list

        if not _ip_allowed(client_ip, allowlist):
            log_event(
                event_type="ip_blocked",
                username=None,
                ip=client_ip,
                detail=f"Blocked request to {request.url.path} from disallowed IP",
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Access denied: your IP address is not authorized."},
            )

        request.state.client_ip = client_ip
        return await call_next(request)
