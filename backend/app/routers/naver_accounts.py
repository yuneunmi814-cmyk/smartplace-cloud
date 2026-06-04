from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import encrypt
from app.core.database import get_db
from app.core.security import get_approved_user
from app.models import NaverAccount, User
from app.schemas import NaverAccountCreateReq, NaverAccountRes, OkRes
from app.services import audit

router = APIRouter(prefix="/api/v1/naver-accounts", tags=["naver-accounts"])


@router.post("", response_model=NaverAccountRes, status_code=status.HTTP_201_CREATED)
def link_account(
    body: NaverAccountCreateReq,
    db: Session = Depends(get_db),
    user: User = Depends(get_approved_user),
) -> NaverAccountRes:
    # Store a credential blob (AES-256-GCM). For ID/PW we keep a JSON object the
    # gateway can parse; otherwise the opaque token string.
    import json

    if body.loginId and body.loginPw:
        credential = json.dumps({"loginId": body.loginId, "loginPw": body.loginPw})
    else:
        credential = body.token or ""

    account = NaverAccount(
        user_id=user.id,
        alias=body.alias,
        encrypted_token=encrypt(credential),  # AES-256-GCM
        status="connected",
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    audit.record(
        db,
        actor_user_id=user.id,
        action="naver_account.link",
        target_type="naver_account",
        target_id=account.id,
        detail={"alias": account.alias},
    )
    return NaverAccountRes(
        id=account.id, alias=account.alias, status=account.status, createdAt=account.created_at
    )


@router.get("", response_model=list[NaverAccountRes])
def list_accounts(
    db: Session = Depends(get_db),
    user: User = Depends(get_approved_user),
) -> list[NaverAccountRes]:
    rows = db.scalars(
        select(NaverAccount).where(NaverAccount.user_id == user.id).order_by(NaverAccount.id)
    ).all()
    return [
        NaverAccountRes(id=a.id, alias=a.alias, status=a.status, createdAt=a.created_at)
        for a in rows
    ]


@router.delete("/{account_id}", response_model=OkRes)
def unlink_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_approved_user),
) -> OkRes:
    account = db.get(NaverAccount, account_id)
    if not account or account.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계정을 찾을 수 없습니다.")
    db.delete(account)
    db.commit()
    audit.record(
        db,
        actor_user_id=user.id,
        action="naver_account.unlink",
        target_type="naver_account",
        target_id=account_id,
    )
    return OkRes(ok=True)
