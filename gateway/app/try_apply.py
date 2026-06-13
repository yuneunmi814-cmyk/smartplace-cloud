"""Test ONE real image apply, headed, so you can watch it happen.

Usage:
    GATEWAY_MOCK=0 GATEWAY_HEADLESS=false \\
        python -m app.try_apply <네이버아이디> <placeId> <이미지경로_또는_URL>

Example (local image):
    GATEWAY_MOCK=0 GATEWAY_HEADLESS=false \\
        python -m app.try_apply <네이버아이디> <placeId> ~/Downloads/test.jpg

This adds ONE photo to that store. The store already has many photos, so it's
safe to try and easy to remove afterwards in the partner center.
"""

import sys

from app.naver import apply_main_image


def main() -> None:
    if len(sys.argv) < 4:
        print("사용법: python -m app.try_apply <네이버아이디> <placeId> <이미지경로_또는_URL>")
        raise SystemExit(1)

    login_id, place_id, image = sys.argv[1], sys.argv[2], sys.argv[3]
    print(f"▶ 적용 시도: login={login_id} place={place_id}")
    print(f"  이미지: {image}")
    try:
        apply_main_image({"loginId": login_id}, place_id, image)
        print("✅ 성공 — 파트너센터에서 사진이 추가되었는지 확인하세요.")
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 실패: {type(exc).__name__}: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
