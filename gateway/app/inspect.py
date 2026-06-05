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
    mode = sys.argv[2] if len(sys.argv) > 3 and sys.argv[2] in ("details", "order", "brand") else None
    place_id = sys.argv[3] if mode else (sys.argv[2] if len(sys.argv) > 2 else None)
    mode_details = mode == "details"
    mode_order = mode == "order"
    mode_brand = mode == "brand"

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

        if mode_brand:
            _inspect_brand(page, settings, diag, place_id)  # place_id holds brandSeq here
        elif not place_id:
            _inspect_home(page, settings, diag)
        elif mode_details:
            _inspect_details(page, settings, diag, place_id)
        elif mode_order:
            _inspect_order(page, settings, diag, place_id)
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


def _inspect_brand(page, settings, diag: Path, brand_seq: str) -> None:
    """Scrape the brand branch list → (지점명, placeSeq) for every branch.
    placeSeq feeds the unified edit URL /brand/biz-edit?placeSeq=..&brandSeq=.."""
    url = f"{settings.smartplace_url}/brand?brandSeq={brand_seq}&menu=branch"
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    mapping: dict[str, str] = {}  # placeSeq -> 지점명
    raw_hrefs: set[str] = set()

    def scrape_current() -> None:
        # For each biz-edit link, walk up to its row and read the 지점명.
        links = page.eval_on_selector_all(
            "a[href*='biz-edit'], a[href*='placeSeq']",
            """els => els.map(a => {
                const href = a.getAttribute('href') || '';
                let row = a.closest('tr') || a.closest('[role=row]') || a.closest('li');
                if (!row) {
                    let p = a;
                    for (let i = 0; i < 8; i++) {
                        p = p && p.parentElement;
                        if (p && (p.innerText || '').includes('79대포')) { row = p; break; }
                    }
                }
                return { href, text: row ? (row.innerText || '').trim() : '' };
            })""",
        )
        for link in links:
            href = link.get("href") or ""
            raw_hrefs.add(href)
            m = re.search(r"placeSeq=(\d+)", href)
            if m:
                nm = re.search(r"79대포[^\n\t]*", link.get("text") or "")
                name = nm.group(0).strip() if nm else (link.get("text") or "")[:30]
                mapping.setdefault(m.group(1), name)

    # Best-effort: bump the per-page selector to 100 so fewer pages to click.
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

    # Numbered pagination: scrape each page, click '다음'/'>' until no more.
    page_no = 1
    while page_no <= 30:
        page.wait_for_timeout(1200)
        before = len(mapping)
        scrape_current()
        target = str(page_no + 1)
        clicked = False
        for sel in (
            f"//a[normalize-space()='{target}']",
            f"//button[normalize-space()='{target}']",
            "button[aria-label*='다음']",
            "a[aria-label*='다음']",
        ):
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
        # stop if the page didn't actually advance (no new links after 1 more scrape)
        scrape_current()
        if len(mapping) == before:
            break
        page_no += 1

    shot = diag / f"brand_{brand_seq}.png"
    page.screenshot(path=str(shot), full_page=True)
    html_path = diag / f"brand_{brand_seq}.html"
    html_path.write_text(page.content())

    # Save the full cross-page mapping to a file so it can be read back wholesale.
    json_path = diag / f"brand_{brand_seq}_places.json"
    json_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2))

    print(f"=== 브랜드 지점 스크랩: brandSeq {brand_seq} ===")
    print(f"placeSeq 추출: {len(mapping)}곳")
    print(f"전체 매핑 저장: {json_path}")
    for seq, name in mapping.items():
        print(f"  placeSeq={seq}   {name}")
    if not mapping:
        print("  (placeSeq 링크 자동추출 실패 — 아래 raw href / 스크린샷 확인)")
        for href in list(raw_hrefs)[:20]:
            print(f"    {href}")
    print(f"\n스크린샷: {shot}")
    print(f"HTML 덤프: {html_path}")


def _inspect_order(page, settings, diag: Path, place_id: str) -> None:
    # Resolve bookingBusinessId, open partner detail, click 순서설정, dump the UI.
    page.goto(f"{settings.smartplace_url}/bizes/place/{place_id}", wait_until="domcontentloaded")
    page.wait_for_timeout(3500)
    m = re.search(r"bookingBusinessId=(\d+)", page.url)
    if not m:
        print(f"⚠️ bookingBusinessId 없음 (placeId={place_id}). 이 매장은 partner 유형이 아닙니다.")
        return
    booking_id = m.group(1)
    page.goto(f"{settings.booking_partner_url}/bizes/{booking_id}/detail", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)

    # dismiss group-account modal
    try:
        btn = page.get_by_role("button", name=re.compile("단체아이디로 계속"))
        if btn.count():
            btn.first.click(timeout=5000)
            page.wait_for_timeout(1000)
    except Exception:
        pass

    page.screenshot(path=str(diag / f"order_before_{booking_id}.png"), full_page=True)

    # Click 순서설정
    clicked = False
    try:
        btn = page.get_by_role("button", name=re.compile("순서설정"))
        if btn.count():
            btn.first.click(timeout=5000)
            page.wait_for_timeout(3000)
            clicked = True
    except Exception:
        pass

    shot = diag / f"order_after_{booking_id}.png"
    page.screenshot(path=str(shot), full_page=True)
    html_path = diag / f"order_{booking_id}.html"
    html_path.write_text(page.content())

    draggable = page.locator("[draggable='true']").count()
    buttons = page.eval_on_selector_all(
        "button",
        "els => els.map(e => (e.innerText||'').trim()).filter(Boolean).slice(0, 40)",
    )
    candidates = page.eval_on_selector_all(
        "button, a, [role=button], [class*='rep'], [class*='Rep'], [class*='대표']",
        """els => els.map(e => ({
              tag: e.tagName,
              cls: (e.className && e.className.toString ? e.className.toString() : ''),
              text: (e.innerText || e.getAttribute('aria-label') || '').trim()
           })).filter(x => /대표|맨\\s*앞|순서|이동|확인|저장|적용/i.test(x.text || x.cls)).slice(0, 30)""",
    )

    print(f"=== 순서설정 진단: bookingBusinessId {booking_id} ===")
    print(f"순서설정 버튼 클릭됨: {clicked}")
    print(f"draggable 요소 개수: {draggable}")
    print(f"버튼 텍스트: {buttons}")
    print("대표/순서 관련 후보:")
    for c in candidates:
        print(f"  <{c['tag'].lower()} class='{c['cls'][:50]}'>  {c['text'][:40]!r}")
    print(f"\n스크린샷(전): order_before_{booking_id}.png")
    print(f"스크린샷(후): {shot}")
    print(f"HTML 덤프: {html_path}")


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
