"""Live DOM inspector for selector tuning.

Uses the seeded session to open real SmartPlace pages and dump what's actually
there (business ids, buttons, file inputs) + a screenshot, so we can set exact
selectors instead of guessing.

Usage:
    python -m app.inspect <네이버아이디>             # 내 가맹점(placeId) 찾기
    python -m app.inspect <네이버아이디> <place_id>   # 사진 등록 페이지 진단
"""

import json
import re
import sys
from pathlib import Path

from app.config import get_settings
from app.session_store import get_session_store


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python -m app.inspect <네이버아이디> [place_id]")
        raise SystemExit(1)

    login_id = sys.argv[1]
    # Modes:
    #   <login>                  → list places
    #   <login> <placeId>        → booking partner detail (예약 연동된 곳)
    #   <login> details <placeId>→ smartplace details?menu=basic (연동 안 된 곳)
    mode_details = len(sys.argv) > 3 and sys.argv[2] == "details"
    place_id = sys.argv[3] if mode_details else (sys.argv[2] if len(sys.argv) > 2 else None)

    settings = get_settings()
    store = get_session_store()

    state = store.get(login_id)
    if not state:
        print(f"❌ '{login_id}' 세션이 없습니다. 먼저: python -m app.seed_session {login_id}")
        raise SystemExit(1)

    diag = Path(__file__).resolve().parents[1] / "diag"
    diag.mkdir(exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=json.loads(state))
        page = context.new_page()

        if not place_id:
            _inspect_home(page, settings, diag)
        elif mode_details:
            _inspect_details(page, settings, diag, place_id)
        else:
            _inspect_photo(page, settings, diag, place_id)

        browser.close()


def _inspect_home(page, settings, diag: Path) -> None:
    page.goto(f"{settings.smartplace_url}/bizes", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    # The list lazy-loads on scroll. Keep scrolling until the link count stops
    # growing (or we hit the iteration cap).
    last_count = -1
    stable = 0
    for _ in range(60):
        page.evaluate(
            """() => {
                const els = document.querySelectorAll("a[href*='/bizes/place/']");
                if (els.length) els[els.length - 1].scrollIntoView({block: 'end'});
                window.scrollTo(0, document.body.scrollHeight);
            }"""
        )
        page.wait_for_timeout(900)
        count = len(page.query_selector_all("a[href*='/bizes/place/']"))
        if count == last_count:
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
            last_count = count

    shot = diag / "home.png"
    page.screenshot(path=str(shot), full_page=True)

    links = page.eval_on_selector_all(
        "a[href*='/bizes']",
        "els => els.map(e => ({href: e.getAttribute('href'), text: (e.innerText||'').trim()}))",
    )
    seen: set[str] = set()
    found: list[tuple[str, str]] = []
    for link in links:
        m = re.search(r"/bizes/place/(\d+)", link.get("href") or "")
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            found.append((m.group(1), (link.get("text") or "")[:40]))

    print(f"=== 내 가맹점 {len(found)}곳 (placeId  이름) ===")
    for pid, name in found:
        print(f"  {pid}   {name}")
    if not found:
        print("  (place 링크 자동 추출 실패 — 아래 /bizes 링크 목록과 스크린샷을 참고)")
        print("  /bizes 관련 링크:")
        for link in links[:30]:
            print(f"    {link.get('href')}   {(link.get('text') or '')[:30]}")
    print(f"\n스크린샷: {shot}")
    print("현재 URL:", page.url)


def _inspect_details(page, settings, diag: Path, place_id: str) -> None:
    url = f"{settings.smartplace_url}/bizes/place/{place_id}/details?menu=basic"
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)

    shot = diag / f"details_{place_id}.png"
    page.screenshot(path=str(shot), full_page=True)
    html_path = diag / f"details_{place_id}.html"
    html_path.write_text(page.content())

    file_inputs = page.locator("input[type=file]").count()
    buttons = page.eval_on_selector_all(
        "button",
        "els => els.map(e => (e.innerText||'').trim()).filter(Boolean).slice(0, 60)",
    )
    candidates = page.eval_on_selector_all(
        "button, a, [role=button], label",
        """els => els.map(e => ({
              tag: e.tagName,
              cls: (e.className && e.className.toString ? e.className.toString() : ''),
              text: (e.innerText || e.getAttribute('aria-label') || '').trim()
           })).filter(x => /사진|이미지|대표|추가|등록|업로드|photo|image/i.test(x.text || x.cls)).slice(0, 30)""",
    )

    print(f"=== details 페이지 진단: {url} ===")
    print(f"현재 URL: {page.url}")
    print(f"input[type=file] 개수: {file_inputs}")
    print(f"버튼 텍스트({len(buttons)}개): {buttons}")
    print("사진 관련 후보 요소:")
    for c in candidates:
        print(f"  <{c['tag'].lower()} class='{c['cls'][:50]}'>  {c['text'][:40]!r}")
    print(f"\n스크린샷: {shot}")
    print(f"HTML 덤프: {html_path}")


def _inspect_photo(page, settings, diag: Path, place_id: str) -> None:
    # Step 1: open the place to discover its bookingBusinessId.
    page.goto(f"{settings.smartplace_url}/bizes/place/{place_id}", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    m = re.search(r"bookingBusinessId=(\d+)", page.url)
    if not m:
        print(f"⚠️ bookingBusinessId를 못 찾았습니다. 현재 URL: {page.url}")
        page.screenshot(path=str(diag / f"place_{place_id}.png"), full_page=True)
        return
    booking_id = m.group(1)
    print(f"placeId {place_id} → bookingBusinessId {booking_id}")

    # Step 2: open the booking partner detail page (where 대표이미지 lives).
    detail_url = f"{settings.booking_partner_url}/bizes/{booking_id}/detail"
    page.goto(detail_url, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)

    shot = diag / f"detail_{booking_id}.png"
    page.screenshot(path=str(shot), full_page=True)
    html_path = diag / f"detail_{booking_id}.html"
    html_path.write_text(page.content())

    file_inputs = page.locator("input[type=file]").count()
    buttons = page.eval_on_selector_all(
        "button",
        "els => els.map(e => (e.innerText||'').trim()).filter(Boolean).slice(0, 60)",
    )
    # Candidate clickable elements related to photos (with their classes).
    candidates = page.eval_on_selector_all(
        "button, a, [role=button], label",
        """els => els.map(e => ({
              tag: e.tagName,
              cls: (e.className && e.className.toString ? e.className.toString() : ''),
              text: (e.innerText || e.getAttribute('aria-label') || '').trim()
           })).filter(x => /사진|이미지|대표|추가|등록|업로드|photo|image/i.test(x.text || x.cls)).slice(0, 30)""",
    )

    print(f"=== 대표이미지 진단: {detail_url} ===")
    print(f"현재 URL: {page.url}")
    print(f"input[type=file] 개수: {file_inputs}")
    print(f"버튼 텍스트({len(buttons)}개): {buttons}")
    print("사진 관련 후보 요소:")
    for c in candidates:
        print(f"  <{c['tag'].lower()} class='{c['cls'][:50]}'>  {c['text'][:40]!r}")
    print(f"\n스크린샷: {shot}")
    print(f"HTML 덤프: {html_path}")


if __name__ == "__main__":
    main()
