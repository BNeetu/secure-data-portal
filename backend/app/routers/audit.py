from fastapi import APIRouter, Depends

from app.core.audit import read_events
from app.core.deps import require_role

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", dependencies=[Depends(require_role("admin"))])
async def get_audit_log(limit: int = 200):
    return {"events": read_events(limit=limit)}
