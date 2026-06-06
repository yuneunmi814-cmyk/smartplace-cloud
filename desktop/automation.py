"""Naver SmartPlace automation for the desktop beta app.

Distilled from the verified gateway logic (login / brand-scrape / brand biz-edit
upload with the 대표사진 result, wait-for-upload + save + reload verification).

Each customer runs this on THEIR machine with THEIR Naver login — so credentials
and session never leave the device (Local-First), which sidesteps the
datacenter-IP and credential-liability problems of a cloud SaaS.
"""

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SMARTPLACE = "https://new.smartplace.naver.com"
BOOKING = "https://partner.booking.naver.com"
NAVER_LOGIN = "https://nid.naver.com/nidlogin.login"
AUTH_COOKIES = ("NID_AUT", "NID_SES")
SESSION_FILE = Path.home() / ".smartplace_beta" / "session.json"
DATE_RE = re.compile(r"/(20\d{6})_")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


# ---- session ---------------------------------------------------------------

def has_session() -> bool:
    return SESSION_FILE.exists()


def login() -> bool:
    """Opens a real Naver login window. The user logs in (id/pw/captcha/2FA
    themselves). On reaching SmartPlace we save the session and return True."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(NAVER_LOGIN)
        try:
            page.wait_for_url("**smartplace.naver.com**", timeout=180000)
        except Exception:
            pass
        ok = bool(set(AUTH_COOKIES) & {c["name"] for c in ctx.cookies()})
        if ok:
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
                """els => els.map(a => {
                    const href = a.getAttribute('href') || '';
                    let row = a.closest('tr') || a.closest('[role=row]') || a.closest('li');
                    if (!row) { let q=a; for(let i=0;i<8;i++){ q=q&&q.parentElement; if(q&&(q.innerText||'').includes('대포')){row=q;break;} } }
                    return { href, text: row ? (row.innerText||'').trim() : '' };
                })""",
            )
            for link in links:
                m = re.search(r"placeSeq=(\d+)", link.get("href") or "")
                if m:
                    nm = re.search(r"\S*대포[^\n\t]*", link.get("text") or "")
                    out.setdefault(m.group(1), nm.group(0).strip() if nm else "")

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
        sv = page.get_by_role("button", name="저장하기", exact=True)
        if sv.count():
            sv.first.click(timeout=5000)
            page.wait_for_timeout(3000)

        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        final = _photo_count(page)
        if final is not None and final < target:
            raise RuntimeError(f"저장 미반영 (목표 {target}, 실제 {final})")
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
