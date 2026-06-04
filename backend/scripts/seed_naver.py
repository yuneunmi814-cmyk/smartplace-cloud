"""Register the Naver account + all 79대포 places for the first (admin) user.

The credential stored is just {"loginId": ...} — the gateway uses a human-seeded
session (app.seed_session), so no password is needed here. Token is AES-encrypted.

Usage (from backend/ with .venv active):
    python -m scripts.seed_naver 79daepo
"""

import json
import sys

from sqlalchemy import select

from app.core.crypto import encrypt
from app.core.database import Base, SessionLocal, engine
from app.models import NaverAccount, Place, User

# placeId, business name — captured live via gateway/app/inspect.
PLACES: list[tuple[str, str]] = [
    ("9846575", "79대포 수완점"),
    ("4927940", "79대포 목포옥암점"),
    ("11868848", "79대포 수원영화점"),
    ("11868859", "79대포 미사강변점"),
    ("3148134", "79대포 안양메가트리아점"),
    ("11360248", "79대포 옥계점"),
    ("10320883", "79대포 천안청당점"),
    ("10488128", "79대포 아산신창점"),
    ("9364682", "79대포 구로개봉점"),
    ("11811011", "79대포 강릉교동점"),
    ("11819236", "79대포 서재점"),
    ("11536904", "79대포 송도이편한세상점"),
    ("11231123", "79대포 양학점"),
    ("11528484", "79대포 운천점"),
    ("8885433", "79대포 광주양산점"),
    ("11360197", "79대포 숭실대점"),
    ("11694735", "79대포 창원중앙힐스테이트점"),
    ("11695897", "79대포 여수여서점"),
    ("4974949", "79대포 광양광영점"),
    ("3779872", "79대포 익산모현점"),
    ("7096346", "79대포 화성수원대점"),
    ("3308436", "79대포 율량1호점"),
    ("5582510", "79대포 서산대산점"),
    ("7045544", "79대포 김천신음점"),
    ("11594338", "79대포 광주신창점"),
    ("11582979", "79대포 평택칠원점"),
    ("3472894", "79대포 청주지웰시티점"),
    ("3718321", "79대포 신중동점"),
    ("8209359", "79대포 서울석촌점"),
    ("9843346", "79대포 인천가좌점"),
    ("10056990", "79대포 광주하남2지구점"),
    ("10400677", "79대포 평촌엘프라우드점"),
    ("10526052", "79대포 남해점"),
    ("11051881", "79대포 영동점"),
    ("11272126", "79대포 보령시청점"),
    ("11417501", "79대포 시화로데오점"),
    ("9765034", "79대포 부천원미점"),
    ("11185532", "79대포 가능역점"),
    ("9526880", "79대포 시흥장곡점"),
    ("9976791", "79대포 김포감정점"),
]


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python -m scripts.seed_naver <네이버아이디>  (예: 79daepo)")
        raise SystemExit(1)
    login_id = sys.argv[1]
    alias = sys.argv[2] if len(sys.argv) > 2 else "79대포 본사"

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.scalar(select(User).order_by(User.id))
        if not user:
            print("❌ 사용자가 없습니다. 먼저 웹에서 회원가입(첫 가입=관리자) 하세요.")
            raise SystemExit(1)

        account = db.scalar(
            select(NaverAccount).where(
                NaverAccount.user_id == user.id, NaverAccount.alias == alias
            )
        )
        if not account:
            account = NaverAccount(
                user_id=user.id,
                alias=alias,
                encrypted_token=encrypt(json.dumps({"loginId": login_id})),
                status="connected",
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            print(f"✅ 네이버 계정 연동 생성: {alias} (loginId={login_id}, account_id={account.id})")
        else:
            print(f"• 기존 계정 사용: {alias} (account_id={account.id})")

        existing = {
            p.place_id
            for p in db.scalars(select(Place).where(Place.account_id == account.id)).all()
        }
        added = 0
        for place_id, name in PLACES:
            if place_id in existing:
                continue
            db.add(Place(account_id=account.id, place_id=place_id, business_name=name))
            added += 1
        db.commit()
        print(f"✅ 가맹점 등록: 신규 {added}곳 (전체 {len(PLACES)}곳)")
        print(f"   사용자: {user.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
