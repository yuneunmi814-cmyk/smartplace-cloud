"""Register a Naver account + a set of places for the first (admin) user.

The credential stored is just {"loginId": ...} — the gateway uses a human-seeded
session (app.seed_session), so no password is needed here. Token is AES-encrypted.

PLACES below is EXAMPLE data — replace it with your brand's places (scrape them
via the app's "지점 불러오기" or gateway `app.inspect`).

Usage (from backend/ with .venv active):
    python -m scripts.seed_naver <네이버아이디> [별칭]
"""

import json
import sys

from sqlalchemy import select

from app.core.crypto import encrypt
from app.core.database import Base, SessionLocal, engine
from app.models import NaverAccount, Place, User

# (placeId, 상호명) 예시 — 본인 브랜드 값으로 교체하세요.
# 실제 값은 gateway 의 inspect 로 라이브 스크랩해서 채웁니다:
#   python -m app.inspect <네이버아이디> brand <brandSeq>
# 또는 데스크톱/웹 앱의 "지점 불러오기"로 받은 목록을 사용하세요.
PLACES: list[tuple[str, str]] = [
    ("0000001", "예시 브랜드 강남점"),
    ("0000002", "예시 브랜드 홍대점"),
    ("0000003", "예시 브랜드 부산서면점"),
]


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python -m scripts.seed_naver <네이버아이디> [별칭]")
        raise SystemExit(1)
    login_id = sys.argv[1]
    alias = sys.argv[2] if len(sys.argv) > 2 else "본사"

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
