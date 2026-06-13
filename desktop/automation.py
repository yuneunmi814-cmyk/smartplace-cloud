"""Naver SmartPlace automation for the desktop beta app.

Distilled from the verified gateway logic (login / brand-scrape / brand biz-edit
upload with the 대표사진 result, wait-for-upload + save + reload verification).

Each customer runs this on THEIR machine with THEIR Naver login — so credentials
and session never leave the device (Local-First), which sidesteps the
datacenter-IP and credential-liability problems of a cloud SaaS.
"""

import csv
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import reports
import reviews

SMARTPLACE = "https://new.smartplace.naver.com"
BOOKING = "https://partner.booking.naver.com"
NAVER_LOGIN = "https://nid.naver.com/nidlogin.login"
AUTH_COOKIES = ("NID_AUT", "NID_SES")
SESSION_FILE = Path.home() / ".smartplace_beta" / "session.json"
DEBUG_DIR = Path.home() / ".smartplace_beta" / "debug"
REPORTS_DEBUG_DIR = Path.home() / ".smartplace_beta" / "reports_debug"
REVIEWS_DEBUG_DIR = Path.home() / ".smartplace_beta" / "reviews_debug"
DATE_RE = re.compile(r"/(20\d{6})_")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


# ---- session ---------------------------------------------------------------

def has_session() -> bool:
    return SESSION_FILE.exists()


def login() -> bool:
    """Opens a real Naver login window. The user logs in (id/pw/captcha/2FA
    themselves). We detect success the moment the Naver auth cookies appear —
    no need to navigate anywhere — then save the session and return True."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(NAVER_LOGIN)

        ok = False
        for _ in range(180):  # poll up to ~6 min while the user logs in
            time.sleep(2)
            try:
                cookies = {c["name"] for c in ctx.cookies()}
            except Exception:
                break  # window/context closed
            if set(AUTH_COOKIES) & cookies:
                ok = True
                break
            if not ctx.pages:  # user closed the window
                break

        if ok:
            # Warm the SmartPlace session so cookies are fully provisioned.
            try:
                page.goto(SMARTPLACE, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
            except Exception:
                pass
            SESSION_FILE.write_text(json.dumps(ctx.storage_state()))
        browser.close()
        return ok


def _new_context(p, browser):
    return browser.new_context(storage_state=json.loads(SESSION_FILE.read_text()))


def _dismiss_modal(page) -> None:
    try:
        btn = page.get_by_role("button", name=re.compile("단체아이디로 계속"))
        if btn.count():
            btn.first.click(timeout=4000)
            page.wait_for_timeout(800)
    except Exception:
        pass


# ---- branch scraping -------------------------------------------------------

def scrape_branches(brand_seq: str) -> list[dict]:
    """Returns [{placeSeq, name}] for every branch of the brand (paginated)."""
    out: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = _new_context(p, browser)
        page = ctx.new_page()
        page.goto(f"{SMARTPLACE}/brand?brandSeq={brand_seq}&menu=branch", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        _dismiss_modal(page)

        # bump per-page to 100 (best effort)
        for sel in ("text=10개씩", "text=20개씩", "text=50개씩"):
            try:
                box = page.locator(sel).first
                if box.count():
                    box.click(timeout=2000)
                    page.wait_for_timeout(800)
                    opt = page.locator("text=100개씩").first
                    if opt.count():
                        opt.click(timeout=2000)
                        page.wait_for_timeout(2000)
                    break
            except Exception:
                pass

        def scrape():
            links = page.eval_on_selector_all(
                "a[href*='biz-edit'], a[href*='placeSeq']",
                # Brand-agnostic: take the link's row container (any franchise),
                # not a brand-name match. placeSeq drives everything; the name is
                # just the row's first line.
                """els => els.map(a => {
                    const href = a.getAttribute('href') || '';
                    const row = a.closest('tr') || a.closest('[role=row]') || a.closest('li') || a.parentElement;
                    return { href, text: row ? (row.innerText||'').trim() : '' };
                })""",
            )
            for link in links:
                m = re.search(r"placeSeq=(\d+)", link.get("href") or "")
                if m:
                    # First non-empty line of the row is the store name (works for
                    # any brand). If blank, the UI falls back to "지점 <placeSeq>".
                    text = (link.get("text") or "").strip()
                    name = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
                    out.setdefault(m.group(1), name)

        page_no = 1
        while page_no <= 30:
            page.wait_for_timeout(1000)
            before = len(out)
            scrape()
            target = str(page_no + 1)
            clicked = False
            for sel in (f"//a[normalize-space()='{target}']", f"//button[normalize-space()='{target}']",
                        "button[aria-label*='다음']", "a[aria-label*='다음']"):
                try:
                    btn = page.locator(sel).last
                    if btn.count() and btn.is_enabled():
                        btn.click(timeout=2500)
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                break
            page.wait_for_timeout(1500)
            scrape()
            if len(out) == before:
                break
            page_no += 1

        browser.close()
    return [{"placeSeq": k, "name": v} for k, v in out.items()]


# ---- image apply -----------------------------------------------------------

def _photo_count(page):
    try:
        loc = page.locator("label[class*='InputImageUpload']").first
        if loc.count():
            m = re.search(r"(\d+)\s*/\s*\d+", loc.inner_text())
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return None


def _debug_dump(page, tag: str) -> str | None:
    """Save a full-page screenshot so a remote user can show exactly what Naver
    rendered when verification failed. Returns the path, or None if it couldn't."""
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        shot = DEBUG_DIR / f"{tag}.png"
        page.screenshot(path=str(shot), full_page=True)
        return str(shot)
    except Exception:
        return None


def _photo_verdict(final: int | None, target: int, saved: bool) -> str | None:
    """Pure decision for whether a photo apply actually succeeded.

    Returns an error message if the upload could NOT be positively confirmed, or
    None if verified. Key rule: an UNREADABLE count (``final is None``) is a
    FAILURE, never a success — that was the original false-"성공" bug."""
    if final is None:
        return (
            "업로드 확인 실패: 저장 후 사진 개수를 읽지 못했습니다. "
            "네이버 화면 구조가 바뀌었을 수 있어요."
        )
    if final < target:
        hint = "" if saved else " '저장하기' 버튼을 찾지 못했습니다(저장 안 됨)."
        return f"저장 미반영 (목표 {target}장, 실제 {final}장).{hint}"
    return None


def _apply_one(ctx, brand_seq: str, place_seq: str, image_paths: list[str]) -> None:
    page = ctx.new_page()
    try:
        page.goto(f"{SMARTPLACE}/brand/biz-edit?placeSeq={place_seq}&menu=basic&brandSeq={brand_seq}",
                  wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        _dismiss_modal(page)

        before = _photo_count(page) or 0
        fi = page.locator("label[class*='InputImageUpload'] input[type=file]").first
        if not fi.count():
            fi = page.locator("input[type=file]").first
        if not fi.count():
            raise RuntimeError("사진 입력칸을 찾지 못했습니다")
        fi.set_input_files(image_paths)

        target = before + len(image_paths)
        for _ in range(120):
            page.wait_for_timeout(1000)
            cur = _photo_count(page)
            if cur is not None and cur >= target:
                break

        for lab in ("확인", "등록", "적용", "완료"):
            btn = page.get_by_role("button", name=lab, exact=True)
            if btn.count():
                btn.first.click(timeout=3000)
                page.wait_for_timeout(2000)
                break
        saved = False
        sv = page.get_by_role("button", name="저장하기", exact=True)
        if sv.count():
            sv.first.click(timeout=5000)
            page.wait_for_timeout(3000)
            saved = True

        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        final = _photo_count(page)

        # Only count this place as a success if the saved photo count actually
        # went up. An unreadable count = we could not confirm = FAILURE.
        # (Previously the check was skipped when final was None, so a broken
        # selector or a silent save failure was wrongly reported as "성공".)
        msg = _photo_verdict(final, target, saved)
        if msg:
            shot = _debug_dump(page, f"photo_{place_seq}_{int(time.time())}")
            raise RuntimeError(msg + (f" (진단 화면 저장됨: {shot})" if shot else ""))
    finally:
        page.close()


def apply_bulk(brand_seq: str, place_seqs: list[str], folder: str, progress_cb) -> dict:
    """Applies all images in `folder` to each placeSeq. Calls
    progress_cb(done, total, place_seq, ok, error) after each."""
    images = sorted(str(p) for p in Path(folder).expanduser().iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not images:
        raise RuntimeError("폴더에 이미지가 없습니다")

    ok_n = 0
    fail = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = _new_context(p, browser)
        if not (set(AUTH_COOKIES) & {c["name"] for c in ctx.cookies()}):
            browser.close()
            raise RuntimeError("세션이 만료되었습니다. 다시 로그인하세요.")
        total = len(place_seqs)
        for i, ps in enumerate(place_seqs, 1):
            err = None
            try:
                _apply_one(ctx, brand_seq, ps, images)
                ok_n += 1
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
                fail.append(ps)
            progress_cb(i, total, ps, err is None, err)
            time.sleep(4)
        SESSION_FILE.write_text(json.dumps(ctx.storage_state()))
        browser.close()
    return {"ok": ok_n, "fail": fail, "images": len(images)}


# ---- menu apply (표준 메뉴 일괄) -------------------------------------------

def parse_menu_csv(path: str) -> list[dict]:
    items: list[dict] = []
    with open(Path(path).expanduser(), newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or row.get("메뉴명") or "").strip()
            if not name:
                continue
            items.append({
                "name": name,
                "price": re.sub(r"[^0-9]", "", row.get("price") or row.get("가격") or ""),
                "desc": (row.get("description") or row.get("설명") or "").strip()[:50],
                "image": (row.get("image") or row.get("이미지") or "").strip(),
                "recommended": (row.get("recommended") or row.get("대표") or "").strip().upper()
                in ("Y", "YES", "TRUE", "1", "대표"),
            })
    return items


def _menu_save(page) -> bool:
    """Click 저장하기. Returns True only if the save button was actually found
    and clicked — callers use this to avoid reporting an unsaved run as success."""
    btn = page.get_by_role("button", name="저장하기", exact=True)
    if btn.count():
        btn.first.click(timeout=6000)
        page.wait_for_timeout(3000)
        return True
    return False


def _menu_delete_all(page) -> None:
    btn = page.locator("button:has-text('순서/삭제')").first
    if btn.count():
        btn.click(timeout=5000)
        page.wait_for_timeout(1500)
    for _ in range(250):
        dels = page.locator("button[class*='btn_delete']")
        if not dels.count():
            dels = page.locator("button:has-text('삭제')")
        if not dels.count():
            break
        try:
            dels.first.click(timeout=4000)
        except Exception:
            break
        page.wait_for_timeout(700)
    _menu_save(page)
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    _dismiss_modal(page)


def _menu_add_one(page, it: dict, image_dir: str | None) -> None:
    page.locator("button:has-text('메뉴 추가')").first.click(timeout=8000)
    page.wait_for_timeout(1500)
    page.locator("input[name='name']").last.fill(it["name"])
    if it["price"]:
        page.locator("input[name='cost']").last.fill(it["price"])
    if it["desc"]:
        page.locator("textarea[name='desc']").last.fill(it["desc"])
    if it["image"] and image_dir:
        img = Path(image_dir).expanduser() / it["image"]
        if img.exists():
            page.locator("input[type=file]").last.set_input_files(str(img))
            page.wait_for_timeout(1500)
    if it["recommended"]:
        try:
            page.get_by_text("대표메뉴로 등록하기").last.click(timeout=2000)
        except Exception:
            pass
    confirmed = False
    for label in ("추가하기", "수정", "확인"):
        b = page.locator(f"button:has-text('{label}')").last
        if b.count():
            b.click(timeout=6000)
            confirmed = True
            break
    if not confirmed:
        raise RuntimeError(f"메뉴 '{it['name']}' 추가(확인) 버튼을 찾지 못했습니다 — 화면 구조가 바뀌었을 수 있어요.")
    page.wait_for_timeout(1500)


def _apply_menu_one(ctx, brand_seq, place_seq, items, image_dir, replace) -> None:
    page = ctx.new_page()
    try:
        page.goto(
            f"{SMARTPLACE}/brand/biz-edit?brandSeq={brand_seq}&detail=biz-edit&menu=price&placeSeq={place_seq}",
            wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        _dismiss_modal(page)
        if replace:
            _menu_delete_all(page)
        for it in items:
            _menu_add_one(page, it, image_dir)
        if not _menu_save(page):
            shot = _debug_dump(page, f"menu_{place_seq}_{int(time.time())}")
            raise RuntimeError(
                "저장 실패: '저장하기' 버튼을 찾지 못했습니다(저장 안 됨)."
                + (f" (진단 화면 저장됨: {shot})" if shot else "")
            )
    finally:
        page.close()


def apply_menu_bulk(brand_seq, place_seqs, csv_path, image_dir, replace, progress_cb) -> dict:
    """표준 메뉴(CSV)를 각 placeSeq에 적용. replace=True면 기존 메뉴 삭제 후 적용."""
    items = parse_menu_csv(csv_path)
    if not items:
        raise RuntimeError("CSV에 메뉴가 없습니다")

    ok_n = 0
    fail = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = _new_context(p, browser)
        if not (set(AUTH_COOKIES) & {c["name"] for c in ctx.cookies()}):
            browser.close()
            raise RuntimeError("세션이 만료되었습니다. 다시 로그인하세요.")
        total = len(place_seqs)
        for i, ps in enumerate(place_seqs, 1):
            err = None
            try:
                _apply_menu_one(ctx, brand_seq, ps, items, image_dir, replace)
                ok_n += 1
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
                fail.append(ps)
            progress_cb(i, total, ps, err is None, err)
            time.sleep(4)
        SESSION_FILE.write_text(json.dumps(ctx.storage_state()))
        browser.close()
    return {"ok": ok_n, "fail": fail, "menus": len(items)}


# ---- branch reports (전 지점 통계 수집, 읽기 전용) -------------------------
#
# ⚠️ 네이버 종속(미확정): 통계 페이지의 정확한 URL과 응답 JSON 필드는 실계정 1회
# 수집으로 확인해야 합니다. 그래서 이 모듈은 (1) 통계 페이지가 부르는 XHR JSON을
# **그대로 캡처**해 reports.extract_metrics 로 지표를 뽑고, (2) 못 뽑으면 원본을
# reports_debug 폴더에 **덤프**합니다(가짜 0 대신 '읽기 실패'로 정직 보고).
# URL/필드를 확정하면 아래 REPORT_URL_CANDIDATES 와 reports.METRIC_FIELDS 만 손보면 됩니다.

REPORT_URL_CANDIDATES = (
    "https://new.smartplace.naver.com/bizes/place/{ps}/reports",
    "https://new.smartplace.naver.com/brand/report?brandSeq={bs}&placeSeq={ps}",
)


def _capture_json(page) -> list[dict]:
    """페이지가 부르는 JSON 응답을 모은다. 핸들러 안에서 body가 없으면 조용히 패스."""
    captured: list[dict] = []

    def on_response(resp):
        try:
            if "json" in (resp.headers.get("content-type") or "").lower():
                captured.append(resp.json())
        except Exception:
            pass

    page.on("response", on_response)
    return captured


def _dump_reports_debug(page, place_seq: str, captured: list[dict]) -> str | None:
    """지표를 못 읽었을 때, 실제 응답·화면을 남겨 매핑을 확정할 수 있게 한다."""
    try:
        REPORTS_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        stem = REPORTS_DEBUG_DIR / f"report_{place_seq}_{int(time.time())}"
        stem.with_suffix(".json").write_text(
            json.dumps(captured, ensure_ascii=False)[:500000], encoding="utf-8")
        page.screenshot(path=str(stem.with_suffix(".png")), full_page=True)
        return str(stem.with_suffix(".json"))
    except Exception:
        return None


def _collect_one(ctx, brand_seq: str, place_seq: str) -> dict:
    page = ctx.new_page()
    captured = _capture_json(page)
    try:
        for tpl in REPORT_URL_CANDIDATES:
            try:
                page.goto(tpl.format(ps=place_seq, bs=brand_seq), wait_until="domcontentloaded")
            except Exception:
                continue
            page.wait_for_timeout(4500)  # let analytics XHRs fire
            _dismiss_modal(page)
            if any(captured):
                break
        metrics = reports.extract_metrics(list(captured))
        if all(v is None for v in metrics.values()):
            _dump_reports_debug(page, place_seq, list(captured))
        try:
            name = page.title() or ""
        except Exception:
            name = ""
        return reports.build_row(name, place_seq, metrics)
    finally:
        page.close()


def collect_reports(brand_seq: str, place_seqs: list[str], progress_cb) -> dict:
    """각 지점의 통계 페이지를 열어 지표(방문·조회·리뷰·예약)를 모은다. 쓰기 없음.
    반환: {rows, summary}. 못 읽은 지점은 '읽기 실패'로 표기(가짜 0 금지)."""
    rows: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = _new_context(p, browser)
        if not (set(AUTH_COOKIES) & {c["name"] for c in ctx.cookies()}):
            browser.close()
            raise RuntimeError("세션이 만료되었습니다. 다시 로그인하세요.")
        total = len(place_seqs)
        for i, ps in enumerate(place_seqs, 1):
            err = None
            try:
                row = _collect_one(ctx, brand_seq, ps)
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
                row = reports.build_row("", ps, {k: None for k in reports.METRIC_FIELDS})
            rows.append(row)
            ok = err is None and row.get("수집상태") != "읽기 실패"
            progress_cb(i, total, ps, ok, err or ("" if ok else "통계를 읽지 못함"))
            time.sleep(2)
        SESSION_FILE.write_text(json.dumps(ctx.storage_state()))
        browser.close()
    return {"rows": rows, "summary": reports.summarize(rows)}


# ---- branch reviews (전 지점 리뷰 수집, 읽기 전용) -------------------------
#
# ⚠️ 통계와 동일: 리뷰 페이지의 정확한 URL/JSON 필드는 실계정 1회 수집으로 확인.
# 못 읽으면 가짜 데이터 대신 '읽기 실패'로 보고하고 reviews_debug에 원본 덤프.

REVIEW_URL_CANDIDATES = (
    "https://new.smartplace.naver.com/bizes/place/{ps}/reviews",
    "https://new.smartplace.naver.com/brand/review?brandSeq={bs}&placeSeq={ps}",
)


def _dump_reviews_debug(page, place_seq: str, captured: list[dict]) -> str | None:
    try:
        REVIEWS_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        stem = REVIEWS_DEBUG_DIR / f"review_{place_seq}_{int(time.time())}"
        stem.with_suffix(".json").write_text(
            json.dumps(captured, ensure_ascii=False)[:500000], encoding="utf-8")
        page.screenshot(path=str(stem.with_suffix(".png")), full_page=True)
        return str(stem.with_suffix(".json"))
    except Exception:
        return None


def _collect_reviews_one(ctx, brand_seq: str, place_seq: str) -> tuple[list[dict], bool]:
    """Returns (reviews, captured_any). captured_any=False면 '읽기 실패'."""
    page = ctx.new_page()
    captured = _capture_json(page)
    try:
        for tpl in REVIEW_URL_CANDIDATES:
            try:
                page.goto(tpl.format(ps=place_seq, bs=brand_seq), wait_until="domcontentloaded")
            except Exception:
                continue
            page.wait_for_timeout(4500)
            _dismiss_modal(page)
            # 리뷰는 스크롤로 더 불러오는 경우가 많아 살짝 내려준다.
            try:
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(2000)
            except Exception:
                pass
            if any(captured):
                break
        try:
            name = page.title() or ""
        except Exception:
            name = ""
        found = reviews.extract_reviews(list(captured))
        if not found and not any(captured):
            _dump_reviews_debug(page, place_seq, list(captured))
        return reviews.build_rows(name, place_seq, found), bool(any(captured))
    finally:
        page.close()


def collect_reviews(brand_seq: str, place_seqs: list[str], progress_cb) -> dict:
    """각 지점의 리뷰를 모은다(읽기 전용). 반환: {rows, summary}.
    통계를 못 읽은 지점은 '읽기 실패'로 집계(가짜 데이터 금지)."""
    rows: list[dict] = []
    failed = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = _new_context(p, browser)
        if not (set(AUTH_COOKIES) & {c["name"] for c in ctx.cookies()}):
            browser.close()
            raise RuntimeError("세션이 만료되었습니다. 다시 로그인하세요.")
        total = len(place_seqs)
        for i, ps in enumerate(place_seqs, 1):
            err = None
            captured_any = False
            try:
                got, captured_any = _collect_reviews_one(ctx, brand_seq, ps)
                rows.extend(got)
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
            if not captured_any and err is None:
                err = "리뷰를 읽지 못함"
            if err:
                failed += 1
            progress_cb(i, total, ps, err is None, err or "")
            time.sleep(2)
        SESSION_FILE.write_text(json.dumps(ctx.storage_state()))
        browser.close()
    return {"rows": rows, "summary": reviews.summarize(rows, len(place_seqs), failed)}
