"""Seed a Naver session by logging in MANUALLY, once.

A real browser opens. You log in by hand — captcha, 2-step verification, and
security modules all work because a human is driving. When SmartPlace becomes
reachable, the session (cookies) is saved and the gateway reuses it for
automated image applies.

Usage:
    python -m app.seed_session <네이버_아이디>

Re-run whenever the session expires (gateway returns 423 / "세션이 없습니다").
"""

import json
import sys

from app.config import get_settings
from app.session_store import get_session_store

AUTH_COOKIES = {"NID_AUT", "NID_SES"}


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python -m app.seed_session <네이버_아이디>")
        raise SystemExit(1)

    login_id = sys.argv[1]
    settings = get_settings()
    store = get_session_store()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(settings.naver_login_url)

        print("=" * 60)
        print("브라우저에서 직접 네이버에 로그인하세요.")
        print("(아이디·비밀번호·캡차·2차인증 모두 본인이 직접 입력)")
        print("로그인 후 스마트플레이스 화면까지 들어가면 자동으로 감지합니다…")
        print("=" * 60)

        try:
            page.wait_for_url("**smartplace.naver.com**", timeout=settings.login_timeout_ms)
        except Exception:
            pass

        cookies = {c["name"] for c in context.cookies()}
        if not (AUTH_COOKIES & cookies):
            print("⚠️  로그인이 확인되지 않았습니다.")
            print("    네이버 로그인 후 https://new.smartplace.naver.com 까지 접속한 뒤 다시 실행하세요.")
            browser.close()
            raise SystemExit(1)

        store.put(login_id, json.dumps(context.storage_state()))
        print(f"✅ 세션 저장 완료: {login_id}")
        print("   이제 게이트웨이(GATEWAY_MOCK=0)가 이 세션으로 이미지를 등록합니다.")
        browser.close()


if __name__ == "__main__":
    main()
