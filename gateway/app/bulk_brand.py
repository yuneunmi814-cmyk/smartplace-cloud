"""Set ONE image as 대표(representative) across brand branches via the unified
brand biz-edit route. Works for ALL franchise branches (placeSeq + brandSeq).

placeSeq 목록은 `diag/brand_{brandSeq}_places.json`(app.inspect 로 생성)에서 읽습니다.

Usage:
    # 한 곳만 테스트 (브라우저 보면서):
    GATEWAY_MOCK=0 GATEWAY_HEADLESS=false \\
        python -m app.bulk_brand 79daepo 6707 <이미지경로> --only 4927940

    # 전체 실행 (헤드리스):
    GATEWAY_MOCK=0 python -m app.bulk_brand 79daepo 6707 <이미지경로>

    # 처음 N곳만:
    GATEWAY_MOCK=0 python -m app.bulk_brand 79daepo 6707 <이미지경로> --limit 5
"""

import json
import sys
import time
from pathlib import Path

from app.naver import apply_brand_image


def main() -> None:
    if len(sys.argv) < 4:
        print("사용법: python -m app.bulk_brand <아이디> <brandSeq> <이미지경로> [--only placeSeq] [--limit N]")
        raise SystemExit(1)

    login_id, brand_seq, image = sys.argv[1], sys.argv[2], sys.argv[3]
    # image may be a single file OR a folder (uploads all images in it, sorted;
    # the first becomes 대표).
    img_path = Path(image).expanduser()
    if img_path.is_dir():
        exts = {".jpg", ".jpeg", ".png", ".webp"}
        images = sorted(str(p) for p in img_path.iterdir() if p.suffix.lower() in exts)
        if not images:
            print(f"❌ 폴더에 이미지가 없습니다: {img_path}")
            raise SystemExit(1)
    else:
        images = [str(img_path)]
    diag = Path(__file__).resolve().parents[1] / "diag"
    json_path = diag / f"brand_{brand_seq}_places.json"
    if not json_path.exists():
        print(f"❌ {json_path} 없음. 먼저: python -m app.inspect {login_id} brand {brand_seq}")
        raise SystemExit(1)

    mapping: dict[str, str] = json.loads(json_path.read_text())
    seqs = list(mapping.keys())

    # --file <path>: only the placeSeq listed in this JSON (list or {seq: name}).
    if "--file" in sys.argv:
        target_path = Path(sys.argv[sys.argv.index("--file") + 1])
        targets = json.loads(target_path.read_text())
        seqs = list(targets.keys()) if isinstance(targets, dict) else [str(s) for s in targets]
    if "--only" in sys.argv:
        seqs = [sys.argv[sys.argv.index("--only") + 1]]
    if "--limit" in sys.argv:
        seqs = seqs[: int(sys.argv[sys.argv.index("--limit") + 1])]

    names = mapping  # for display

    print(f"적용 대상: {len(seqs)}곳  /  brandSeq={brand_seq}  /  이미지 {len(images)}장")
    for im in images:
        print(f"   - {Path(im).name}")
    try:
        input("계속하려면 Enter, 취소하려면 Ctrl+C ... ")
    except KeyboardInterrupt:
        print("\n취소됨")
        raise SystemExit(0)

    ok: list[str] = []
    fail: list[tuple[str, str]] = []
    for i, seq in enumerate(seqs, 1):
        label = names.get(seq, "")
        print(f"[{i}/{len(seqs)}] {label} (placeSeq={seq}) ...", end=" ", flush=True)
        try:
            apply_brand_image({"loginId": login_id}, seq, brand_seq, images)
            print("✅")
            ok.append(seq)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ {type(exc).__name__}: {str(exc)[:60]}")
            fail.append((seq, str(exc)[:100]))
        time.sleep(5)  # pacing to reduce bot-detection

    print(f"\n=== 요약: 성공 {len(ok)} / 실패 {len(fail)} / 전체 {len(seqs)} ===")
    for seq, err in fail:
        print(f"  ❌ {seq}: {err}")
    if fail:
        failed_path = diag / f"brand_{brand_seq}_failed.json"
        failed_path.write_text(json.dumps([s for s, _ in fail], ensure_ascii=False, indent=2))
        print(f"실패 목록 저장: {failed_path} (나중에 재시도용)")


if __name__ == "__main__":
    main()
