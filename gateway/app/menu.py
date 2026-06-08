"""표준 메뉴 일괄 적용 (프랜차이즈 전 지점 메뉴 통일).

메뉴 탭(menu=price)에서 메뉴를 추가/교체합니다. 폼 셀렉터는 실제 DOM에서 확인:
  input[name=name]  메뉴명 / input[name=cost] 가격 / textarea[name=desc] 설명
  input[type=file]  메뉴 이미지 / '대표메뉴로 등록하기' 체크 / '추가하기' → '저장하기'
삭제: '순서/삭제' → 항목별 '삭제'(class*=btn_delete) → '저장하기'

CSV 컬럼: name, price, description, image(선택), recommended(Y/N, 선택)
"""

import csv
import json
import re
from pathlib import Path

from app.config import get_settings
from app.naver import (
    AUTH_COOKIES,
    CaptchaRequired,
    GatewayError,
    _build_context,
    _dismiss_group_modal,
    store,
)

settings = get_settings()


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


def apply_menu_set(credential: dict, place_seq: str, brand_seq: str, items: list[dict],
                   image_dir: str | None = None, replace: bool = False) -> dict:
    """한 지점에 메뉴 세트를 적용. replace=True면 기존 메뉴 전부 삭제 후 추가."""
    if settings.mock:
        return {"added": len(items)}
    login_id = credential.get("loginId")
    if not login_id:
        raise GatewayError("credential must contain loginId")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=settings.headless,
                                    args=["--disable-blink-features=AutomationControlled"])
        try:
            ctx = _build_context(p, browser, login_id, credential.get("loginPw"))
            if not (set(AUTH_COOKIES) & {c["name"] for c in ctx.cookies()}):
                raise CaptchaRequired("세션이 만료되었습니다. 다시 로그인하세요.")
            page = ctx.new_page()
            page.goto(
                f"{settings.smartplace_url}/brand/biz-edit"
                f"?brandSeq={brand_seq}&detail=biz-edit&menu=price&placeSeq={place_seq}",
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(5000)
            _dismiss_group_modal(page)

            if replace:
                _delete_all_menus(page)

            added = 0
            for it in items:
                _add_one_menu(page, it, image_dir)
                added += 1
            _save_menu(page)
            store.put(login_id, json.dumps(ctx.storage_state()))
            return {"added": added}
        finally:
            browser.close()


def _add_one_menu(page, it: dict, image_dir: str | None) -> None:
    page.locator("button:has-text('메뉴 추가')").first.click(timeout=8000)
    page.wait_for_timeout(1500)
    # The open form's fields are the most recently rendered ones (.last).
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
    page.locator("button:has-text('추가하기')").last.click(timeout=6000)
    page.wait_for_timeout(1500)


def _delete_all_menus(page) -> None:
    btn = page.locator("button:has-text('순서/삭제')").first
    if btn.count():
        btn.click(timeout=5000)
        page.wait_for_timeout(1500)
    for _ in range(250):  # delete one at a time; DOM shrinks each click
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
    _save_menu(page)
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    _dismiss_group_modal(page)


def _save_menu(page) -> None:
    btn = page.get_by_role("button", name="저장하기", exact=True)
    if btn.count():
        btn.first.click(timeout=6000)
        page.wait_for_timeout(3000)
