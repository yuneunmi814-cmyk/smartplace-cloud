from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_approved_user
from app.models import NaverAccount, Place, User
from app.schemas import PlaceRes

router = APIRouter(prefix="/api/v1/places", tags=["places"])


class PlaceCreateReq(BaseModel):
    accountId: int
    placeId: str
    businessName: str


def _owned_account(db: Session, account_id: int, user: User) -> NaverAccount:
    account = db.get(NaverAccount, account_id)
    if not account or account.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="계정을 찾을 수 없습니다.")
    return account


@router.post("", response_model=PlaceRes, status_code=status.HTTP_201_CREATED)
def create_place(
    body: PlaceCreateReq,
    db: Session = Depends(get_db),
    user: User = Depends(get_approved_user),
) -> PlaceRes:
    _owned_account(db, body.accountId, user)
    place = Place(account_id=body.accountId, place_id=body.placeId, business_name=body.businessName)
    db.add(place)
    db.commit()
    db.refresh(place)
    return PlaceRes(
        id=place.id, accountId=place.account_id, placeId=place.place_id, businessName=place.business_name
    )


@router.get("", response_model=list[PlaceRes])
def list_places(
    db: Session = Depends(get_db),
    user: User = Depends(get_approved_user),
) -> list[PlaceRes]:
    rows = db.scalars(
        select(Place)
        .join(NaverAccount, NaverAccount.id == Place.account_id)
        .where(NaverAccount.user_id == user.id)
        .order_by(Place.business_name)
    ).all()
    return [
        PlaceRes(id=p.id, accountId=p.account_id, placeId=p.place_id, businessName=p.business_name)
        for p in rows
    ]
