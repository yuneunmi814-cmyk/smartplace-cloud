"""Naver SmartPlace / Booking automation for the gateway.

Stores fall into TWO photo-registration flows (auto-detected by placeId):

  A) Booking-integrated stores  (have a bookingBusinessId)
     placeId → new.smartplace.naver.com/bizes/place/{placeId}  (redirects w/ ?bookingBusinessId=)
            → partner.booking.naver.com/bizes/{bid}/detail
            → label '사진추가', input[type=file], verify '전체 사진보기 (총 N)'

  B) Non-integrated stores
     placeId → new.smartplace.naver.com/bizes/place/{placeId}/details?menu=basic
            → label[class*=InputImageUpload] input[type=file] '사진 등록 (N/120)'
            → '저장하기', verify (N/120)

Selectors avoid hashed CSS-module suffixes (which change on deploy); we match by
stable text / class-prefix. Login uses a human-seeded session (app.seed_session).
"""

import json
import re
import tempfile

import httpx

from app.config import get_settings
from app.session_store import get_session_store

settings = get_settings()
store = get_session_store()
AUTH_COOKIES = ("NID_AUT", "NID_SES")


class GatewayError(Exception):
    pass


class CaptchaRequired(GatewayError):
    pass


def apply_main_image(credential: dict, place_id: str, image_url: str) -> None:
    if settings.mock:
        return

    login_id = credential.get("loginId")
    if not login_id:
        raise GatewayError("credential must contain loginId (matching a seeded session)")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=settings.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            context = _build_context(p, browser, login_id, credential.get("loginPw"))
            _apply(context, place_id, image_url)
            store.put(login_id, json.dumps(context.storage_state()))
        finally:
            browser.close()


def _build_context(p, browser, login_id: str, login_pw):
    cached = store.get(login_id)
    if cached:
        return browser.new_context(storage_state=json.loads(cached))
    if settings.allow_password_login and login_pw:
        context = browser.new_context()
        _login(context.new_page(), login_id, login_pw)
        return context
    raise CaptchaRequired(f"'{login_id}' 세션이 없습니다. 먼저: python -m app.seed_session {login_id}")


def _login(page, login_id: str, login_pw: str) -> None:
    page.goto(settings.naver_login_url)
    page.fill("#id", login_id)
    page.fill("#pw", login_pw)
    page.click("button[type=submit], #log\\.login")
    try:
        page.wait_for_url("**smartplace.naver.com**", timeout=settings.login_timeout_ms)
    except Exception:
        pass
    if not (set(AUTH_COOKIES) & {c["name"] for c in page.context.cookies()}):
        raise CaptchaRequired("로그인에 추가 인증이 필요합니다. seed_session으로 처리하세요.")


# ---- flow selection --------------------------------------------------------

def _apply(context, place_id: str, image_url: str) -> None:
    page = context.new_page()

    if not (set(AUTH_COOKIES) & {c["name"] for c in context.cookies()}):
        raise CaptchaRequired("세션이 만료되었습니다. seed_session을 다시 실행하세요.")

    booking_id = _try_booking_id(page, place_id)
    image_path = _download(image_url)
    if booking_id:
        _apply_partner(page, booking_id, image_path)
    else:
        _apply_details(page, place_id, image_path)


def _try_booking_id(page, place_id: str) -> str | None:
    page.goto(f"{settings.smartplace_url}/bizes/place/{place_id}", wait_until="domcontentloaded")
    page.wait_for_timeout(3500)
    m = re.search(r"bookingBusinessId=(\d+)", page.url)
    return m.group(1) if m else None


# ---- flow A: booking partner center ----------------------------------------

def _apply_partner(page, booking_id: str, image_path: str) -> None:
    page.goto(f"{settings.booking_partner_url}/bizes/{booking_id}/detail", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    _dismiss_group_modal(page)

    before = _count(page, re.compile("전체 사진보기"), r"총\s*(\d+)")

    file_input = page.locator("input[type=file]").first
    if not file_input.count():
        raise GatewayError("파일 입력칸을 찾지 못했습니다 (partner).")
    file_input.set_input_files(image_path)
    page.wait_for_timeout(3000)
    _click_confirm(page)
    _save(page, "저장")

    after = _count(page, re.compile("전체 사진보기"), r"총\s*(\d+)")
    _verify(before, after)


# ---- flow B: smartplace details --------------------------------------------

def _apply_details(page, place_id: str, image_path: str) -> None:
    page.goto(
        f"{settings.smartplace_url}/bizes/place/{place_id}/details?menu=basic",
        wait_until="domcontentloaded",
    )
    page.wait_for_timeout(5000)
    _dismiss_group_modal(page)

    before = _details_count(page)

    file_input = page.locator("label[class*='InputImageUpload'] input[type=file]").first
    if not file_input.count():
        file_input = page.locator("input[type=file]").first
    if not file_input.count():
        raise GatewayError("파일 입력칸을 찾지 못했습니다 (details).")
    file_input.set_input_files(image_path)
    page.wait_for_timeout(3000)
    _click_confirm(page)
    _save(page, "저장하기")

    after = _details_count(page)
    _verify(before, after)


def _details_count(page) -> int | None:
    try:
        loc = page.locator("label[class*='InputImageUpload']").first
        if loc.count():
            m = re.search(r"(\d+)\s*/\s*\d+", loc.inner_text())
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return None


# ---- shared helpers --------------------------------------------------------

def _dismiss_group_modal(page) -> None:
    try:
        btn = page.get_by_role("button", name=re.compile("단체아이디로 계속"))
        if btn.count():
            btn.first.click(timeout=5000)
            page.wait_for_timeout(1000)
    except Exception:
        pass


def _click_confirm(page) -> None:
    for label in ("확인", "등록", "적용", "완료"):
        try:
            btn = page.get_by_role("button", name=label, exact=True)
            if btn.count():
                btn.first.click(timeout=3000)
                page.wait_for_timeout(2000)
                return
        except Exception:
            continue


def _save(page, name: str) -> None:
    try:
        btn = page.get_by_role("button", name=name, exact=True)
        if btn.count():
            btn.first.click(timeout=5000)
            page.wait_for_timeout(3000)
    except Exception:
        pass


def _count(page, name_re, value_re: str) -> int | None:
    try:
        btn = page.get_by_role("button", name=name_re)
        if btn.count():
            m = re.search(value_re, btn.first.inner_text())
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return None


def _verify(before: int | None, after: int | None) -> None:
    if before is not None and after is not None and after <= before:
        raise GatewayError(f"사진이 추가되지 않았습니다 (이전 {before} → 이후 {after}).")


def _download(url: str) -> str:
    if not url.startswith("http"):
        return url
    resp = httpx.get(url, timeout=30, follow_redirects=True)
    if resp.status_code >= 400:
        raise GatewayError(f"이미지 다운로드 실패: {resp.status_code}")
    suffix = ".png" if "png" in resp.headers.get("content-type", "") else ".jpg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(resp.content)
    tmp.close()
    return tmp.name
