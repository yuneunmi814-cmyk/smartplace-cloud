from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.models import AuditLog, Task, User
from app.schemas import AuditLogRes, OkRes, StatsRes, UserRes
from app.services import audit

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
admin_only = require_role("admin")


class RoleUpdateReq(BaseModel):
    role: str  # admin | user


@router.get("/users", response_model=list[UserRes])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(admin_only)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)).all())


@router.post("/users/{user_id}/approve", response_model=OkRes)
def approve_user(
    user_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_only)
) -> OkRes:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
    user.status = "approved"
    db.commit()
    audit.record(
        db, actor_user_id=admin.id, action="user.approve", target_type="user", target_id=user_id
    )
    return OkRes(ok=True)


@router.patch("/users/{user_id}/role", response_model=OkRes)
def set_role(
    user_id: int,
    body: RoleUpdateReq,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
) -> OkRes:
    if body.role not in ("admin", "user"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="잘못된 역할입니다.")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
    user.role = body.role
    db.commit()
    audit.record(
        db,
        actor_user_id=admin.id,
        action="user.set_role",
        target_type="user",
        target_id=user_id,
        detail={"role": body.role},
    )
    return OkRes(ok=True)


@router.get("/audit", response_model=list[AuditLogRes])
def list_audit(
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
    limit: int = 100,
) -> list[AuditLogRes]:
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()
    return [
        AuditLogRes(
            id=r.id,
            actorUserId=r.actor_user_id,
            action=r.action,
            targetType=r.target_type,
            targetId=r.target_id,
            detail=r.detail,
            createdAt=r.created_at,
        )
        for r in rows
    ]


@router.get("/stats", response_model=StatsRes)
def stats(db: Session = Depends(get_db), _admin: User = Depends(admin_only)) -> StatsRes:
    total = db.scalar(select(func.count()).select_from(Task)) or 0
    success = db.scalar(select(func.count()).where(Task.status == "success")) or 0
    pending = (
        db.scalar(select(func.count()).where(Task.status.in_(("pending", "queued", "running")))) or 0
    )
    users = db.scalar(select(func.count()).select_from(User)) or 0
    rate = 1.0 if total == 0 else round(success / total, 3)
    return StatsRes(totalTasks=total, successRate=rate, pendingTasks=pending, users=users)
