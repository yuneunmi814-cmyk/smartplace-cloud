"""표준 메뉴를 전 지점에 일괄 적용.

Usage:
    # 한 곳 테스트:
    GATEWAY_MOCK=0 python -m app.bulk_menu 79daepo 6707 menu.csv --only 4927940
    # 특정 지점들:
    GATEWAY_MOCK=0 python -m app.bulk_menu 79daepo 6707 menu.csv --file diag/brand_6707_targets.json
    # 전체 + 기존 메뉴 교체(통일):
    GATEWAY_MOCK=0 python -m app.bulk_menu 79daepo 6707 menu.csv --replace
    # 메뉴 이미지 폴더:  --image-dir ./menu_images

placeSeq 목록은 diag/brand_{brandSeq}_places.json (app.inspect 로 생성)에서 읽음.
"""

import json
import sys
import time
from pathlib import Path

from app.menu import apply_menu_set, parse_menu_csv


def _arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def main() -> None:
    if len(sys.argv) < 4:
        print("사용법: python -m app.bulk_menu <아이디> <brandSeq> <메뉴CSV> [--only seq] [--file f] [--replace] [--image-dir DIR] [--limit N]")
        raise SystemExit(1)

    login_id, brand_seq, csv_path = sys.argv[1], sys.argv[2], sys.argv[3]
    replace = "--replace" in sys.argv
    image_dir = _arg("--image-dir")
    diag = Path(__file__).resolve().parents[1] / "diag"

    items = parse_menu_csv(csv_path)
    if not items:
        print("❌ CSV에 메뉴가 없습니다.")
        raise SystemExit(1)

    # 대상 placeSeq 결정
    if "--only" in sys.argv:
        seqs = [_arg("--only")]
        names = {}
    else:
        src = Path(_arg("--file")) if "--file" in sys.argv else diag / f"brand_{brand_seq}_places.json"
        if not src.exists():
            print(f"❌ {src} 없음. 먼저: python -m app.inspect {login_id} brand {brand_seq}")
            raise SystemExit(1)
        names = json.loads(src.read_text())
        seqs = list(names.keys())
    if "--limit" in sys.argv:
        seqs = seqs[: int(_arg("--limit"))]

    print(f"메뉴 {len(items)}개를 {len(seqs)}곳에 적용  |  교체모드={replace}")
    for it in items:
        print(f"   - {it['name']}  {it['price']}원" + ("  [대표]" if it["recommended"] else ""))
    try:
        input("계속하려면 Enter, 취소하려면 Ctrl+C ... ")
    except KeyboardInterrupt:
        print("\n취소됨")
        raise SystemExit(0)

    ok, fail = [], []
    for i, seq in enumerate(seqs, 1):
        label = names.get(seq, "")
        print(f"[{i}/{len(seqs)}] {label} ({seq}) ...", end=" ", flush=True)
        try:
            res = apply_menu_set({"loginId": login_id}, seq, brand_seq, items, image_dir, replace)
            print(f"✅ {res['added']}개")
            ok.append(seq)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ {type(exc).__name__}: {str(exc)[:60]}")
            fail.append((seq, str(exc)[:100]))
        time.sleep(4)

    print(f"\n=== 요약: 성공 {len(ok)} / 실패 {len(fail)} / 전체 {len(seqs)} ===")
    for seq, err in fail:
        print(f"  ❌ {seq}: {err}")
    if fail:
        (diag / f"menu_{brand_seq}_failed.json").write_text(
            json.dumps([s for s, _ in fail], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
