"""Bulk-apply ONE image to many stores by hardcoded placeId list (legacy).

대부분의 경우 brandSeq 기반 `app.bulk_brand`(전 지점 자동, 브랜드 무관)를 쓰세요.
이 스크립트는 placeId 목록을 직접 들고 있을 때만 쓰는 단순판입니다.

Usage:
    GATEWAY_MOCK=0 GATEWAY_HEADLESS=true \\
        python -m app.bulk_apply <네이버아이디> <이미지경로> [--exclude <placeId>,...]

- 매장마다 사진 1장 추가. 실패해도 멈추지 않고 끝까지 진행 → 마지막에 요약.
- 순차 실행(한 곳씩, 사람처럼 간격).
"""

import sys
import time

from app.naver import apply_main_image

# (placeId, 상호명) 예시 — 본인 브랜드 값으로 교체하세요.
# 실제 목록은 `app.inspect` 로 스크랩하거나 `app.bulk_brand`(brandSeq 기반)를 사용.
PLACES: list[tuple[str, str]] = [
    ("0000001", "예시 브랜드 강남점"),
    ("0000002", "예시 브랜드 홍대점"),
    ("0000003", "예시 브랜드 부산서면점"),
]

DEFAULT_EXCLUDE: set[str] = set()


def main() -> None:
    if len(sys.argv) < 3:
        print("사용법: python -m app.bulk_apply <네이버아이디> <이미지경로> [--exclude id,id]")
        raise SystemExit(1)

    login_id, image = sys.argv[1], sys.argv[2]
    exclude = set(DEFAULT_EXCLUDE)
    if "--exclude" in sys.argv:
        exclude |= set(sys.argv[sys.argv.index("--exclude") + 1].split(","))

    targets = [(pid, name) for pid, name in PLACES if pid not in exclude]
    print(f"적용 대상: {len(targets)}곳 (제외 {len(PLACES) - len(targets)}곳)")
    print(f"이미지: {image}")
    try:
        input("계속하려면 Enter, 취소하려면 Ctrl+C ... ")
    except KeyboardInterrupt:
        print("\n취소됨")
        raise SystemExit(0)

    ok: list[str] = []
    fail: list[tuple[str, str]] = []
    for i, (pid, name) in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {name} ({pid}) ...", end=" ", flush=True)
        try:
            apply_main_image({"loginId": login_id}, pid, image)
            print("✅")
            ok.append(name)
        except Exception as exc:  # noqa: BLE001 — keep going on failure
            print(f"❌ {type(exc).__name__}: {str(exc)[:60]}")
            fail.append((name, str(exc)[:100]))
        time.sleep(4)  # human-like pacing between stores

    print("\n=== 요약 ===")
    print(f"성공 {len(ok)} / 실패 {len(fail)} / 전체 {len(targets)}")
    if fail:
        print("실패 목록 (재시도 필요):")
        for name, err in fail:
            print(f"  ❌ {name}: {err}")


if __name__ == "__main__":
    main()
