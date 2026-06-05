"""Delete the oldest N photos, then add new images (brand biz-edit page).

For branches at/near the 120-photo limit. Photo upload date is parsed from the
image URL (.../20230808_.../), so 'oldest' is identified precisely. Deletes are
staged and only committed on 저장하기, so a failure before save commits nothing.

Usage:
    GATEWAY_MOCK=0 python -m app.replace_oldest <아이디> <brandSeq> <placeSeq> <이미지폴더> <삭제수>
"""

import json
import re
import sys
from pathlib import Path

from app.config import get_settings
from app.session_store import get_session_store

DATE_RE = re.compile(r"/(20\d{6})_")


def main() -> None:
    if len(sys.argv) < 6:
        print("사용법: python -m app.replace_oldest <아이디> <brandSeq> <placeSeq> <이미지폴더> <삭제수>")
        raise SystemExit(1)
    login_id, brand_seq, place_seq, folder, n_str = sys.argv[1:6]
    delete_n = int(n_str)

    s = get_settings()
    store = get_session_store()
    state = store.get(login_id)
    if not state:
        print(f"❌ '{login_id}' 세션 없음. seed_session 먼저.")
        raise SystemExit(1)

    exts = {".jpg", ".jpeg", ".png", ".webp"}
    images = sorted(str(p) for p in Path(folder).expanduser().iterdir() if p.suffix.lower() in exts)
    if not images:
        print("❌ 폴더에 이미지 없음")
        raise SystemExit(1)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(storage_state=json.loads(state))
        pg = ctx.new_page()
        pg.goto(f"{s.smartplace_url}/brand/biz-edit?placeSeq={place_seq}&menu=basic&brandSeq={brand_seq}")
        pg.wait_for_timeout(6000)
        try:
            btn = pg.get_by_role("button", name=re.compile("단체아이디로 계속"))
            if btn.count():
                btn.first.click(timeout=4000)
                pg.wait_for_timeout(800)
        except Exception:
            pass

        def count():
            loc = pg.locator("label[class*='InputImageUpload']").first
            if not loc.count():
                return None
            m = re.search(r"(\d+)\s*/\s*\d+", loc.inner_text())
            return int(m.group(1)) if m else None

        print(f"현재 사진: {count()}장")

        # Delete the oldest `delete_n` (re-query each loop; DOM reorders).
        for k in range(delete_n):
            srcs = pg.locator("img[src*='ldb-phinf']").evaluate_all(
                "els => els.map(e => e.getAttribute('src'))"
            )
            dates = [(DATE_RE.search(x or "") or [None, "99999999"])[1] for x in srcs]
            if not dates:
                break
            idx = dates.index(min(dates))
            print(f"  삭제 {k + 1}/{delete_n}: 업로드일 {min(dates)}")
            pg.locator("button[class*='InputImageUpload_img_close']").nth(idx).click(timeout=4000)
            pg.wait_for_timeout(1200)

        print(f"삭제 후(미저장): {count()}장")

        # Add new images.
        fi = pg.locator("label[class*='InputImageUpload'] input[type=file]").first
        fi.set_input_files(images)
        pg.wait_for_timeout(2000 + 1500 * len(images))
        for lab in ("확인", "등록", "적용", "완료"):
            bb = pg.get_by_role("button", name=lab, exact=True)
            if bb.count():
                bb.first.click(timeout=3000)
                pg.wait_for_timeout(2000)
                break
        print(f"추가 후(미저장): {count()}장 / 새 이미지 {len(images)}장")

        # Commit.
        sv = pg.get_by_role("button", name="저장하기", exact=True)
        if sv.count():
            sv.first.click(timeout=5000)
            pg.wait_for_timeout(3000)
        print(f"✅ 저장 완료. 최종: {count()}장")
        store.put(login_id, json.dumps(ctx.storage_state()))
        b.close()


if __name__ == "__main__":
    main()
