"""Bulk-apply ONE image to many 79대포 stores (store type auto-detected).

Usage:
    GATEWAY_MOCK=0 GATEWAY_HEADLESS=true \\
        python -m app.bulk_apply <네이버아이디> <이미지경로> [--exclude 11360248,...]

- 옥계점(11360248)은 기본 제외. 방이점은 운영자 권한이라 목록에 없음.
- 매장마다 사진 1장 추가. 실패해도 멈추지 않고 끝까지 진행 → 마지막에 요약.
- 순차 실행(한 곳씩). 38곳이면 대략 30~50분 걸립니다.
"""

import sys
import time

from app.naver import apply_main_image

# placeId, 상호명 — gateway/app/inspect 로 수집.
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

DEFAULT_EXCLUDE = {"11360248"}  # 옥계점


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
