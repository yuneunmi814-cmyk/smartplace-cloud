# SmartPlace Naver Gateway

워커가 호출하는 **네이버 자동화 마이크로서비스**. 계약을 받아 내부에서 ID/PW 로그인 → 대표사진 등록을 수행합니다.

```
POST /places/{place_id}/main-image
Authorization: Bearer <GATEWAY_KEY>
X-Naver-Account-Token: <복호화된 자격증명>   # JSON {"loginId","loginPw"}
body: { "imageUrl": "<S3 presigned URL>" }
→ 200 {ok:true} | 423 캡차필요 | 502 실패
```

## 모드

| 모드 | 설정 | 용도 |
|---|---|---|
| **MOCK** (기본) | `GATEWAY_MOCK=1` | 브라우저 없이 200 반환. 배선/CI 테스트 |
| **REAL** | `GATEWAY_MOCK=0` | 실제 Playwright로 네이버 자동화 |

## 실행

```bash
cd gateway
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest                      # mock 테스트

# 실제 모드 (브라우저 필요)
playwright install chromium
GATEWAY_MOCK=0 GATEWAY_KEY=<worker와 동일> uvicorn app.main:app --port 8000
```

또는 docker compose의 `gateway` 서비스로 함께 기동됩니다.

## ⚠️ 운영 주의 (반드시 읽기)

- 네이버는 이 작업의 **공식 API가 없어** 실제 웹 UI를 자동화합니다.
- **ID/PW 로그인은 캡차·2차 인증·봇 탐지에 막힐 수 있습니다.** 막히면 `423 Locked`(`CaptchaRequired`)를 반환하고, 워커는 실패로 기록 후 재시도합니다.
  - 권장: 최초 1회 **수동 로그인으로 세션을 시드**한 뒤 `session_store`가 쿠키를 재사용하도록 운영. (자동 우회 금지)
- `app/naver.py`의 `SELECTORS`는 **라이브 검증 전 추정값**입니다. 실제 SmartPlace DOM에서 확인 후 수정하세요.
- 자격증명은 백엔드에서 **AES-256 암호화**되어 전달되며, 게이트웨이 메모리에서만 복호화됩니다. 디스크에 평문 저장하지 않습니다.

## 셀렉터 튜닝 절차

1. `GATEWAY_HEADLESS=false GATEWAY_MOCK=0`으로 띄워 브라우저를 눈으로 보며 진행
2. 로그인/사진추가/파일input/등록 버튼의 실제 셀렉터 확인
3. `app/naver.py`의 `SELECTORS` 갱신 → 재기동
