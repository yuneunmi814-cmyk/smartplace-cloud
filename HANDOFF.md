# 인수인계 가이드 (받는 사람용)

이 문서는 SmartPlace Cloud를 **다른 사람이 자기 컴퓨터에서 돌릴 수 있도록** 하는 단계별 안내입니다.

> ⚠️ 코드에는 **비밀정보가 들어있지 않습니다.** AWS 키·네이버 세션은 받는 사람이 직접 설정합니다.

---

## 0. 받기

GitHub에서:
```bash
git clone https://github.com/yuneunmi814-cmyk/smartplace-cloud.git
cd smartplace-cloud
```
또는 zip 파일을 받았다면 압축 풀고 그 폴더로 이동.

전제: **Python 3.12+**, **Node 20+**, macOS/Linux 권장.

---

## 1. 설치

```bash
# 백엔드
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
deactivate

# 게이트웨이 (네이버 자동화)
cd ../gateway
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
playwright install chromium      # 브라우저 1회 설치
deactivate

# 웹
cd ../web
npm install
```

---

## 2. 설정

### (a) AWS S3 — `backend/.env`
```bash
cd backend && cp .env.example .env
```
`.env` 열어서 채우기:
```
SMARTPLACE_S3_BUCKET=버킷이름
SMARTPLACE_S3_REGION=ap-northeast-2
SMARTPLACE_AWS_ACCESS_KEY_ID=AKIA...
SMARTPLACE_AWS_SECRET_ACCESS_KEY=...
SMARTPLACE_INLINE_DISPATCH=true
SMARTPLACE_NAVER_GATEWAY_URL=http://localhost:8100
SMARTPLACE_NAVER_GATEWAY_KEY=gateway-key-change-me
```
> 새 버킷 만드는 법은 README의 AWS 안내 참고. 또는 넘긴 사람이 키를 **안전하게(채팅·이메일 평문 금지)** 전달.

### (b) 네이버 세션 시드 — 한 번만, 수동 로그인
```bash
cd gateway && source .venv/bin/activate
python -m app.seed_session 79daepo
```
→ 브라우저가 열리면 **직접 네이버 로그인** (아이디·비번·캡차·2차인증 전부 본인이) → 스마트플레이스까지 들어가면 자동 저장.
> 같은 79대포 계정을 쓰려면 그 계정의 **네이버 아이디/비번이 필요**합니다 (넘긴 사람과 협의).

---

## 3. 실행

### A. 웹앱 (가맹점 관리 UI) — 터미널 3개
```bash
# ① 게이트웨이
cd gateway && source .venv/bin/activate
GATEWAY_MOCK=0 GATEWAY_KEY=gateway-key-change-me uvicorn app.main:app --port 8100

# ② 백엔드
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload

# ③ 웹
cd web && npm run dev
```
→ 브라우저 `localhost:5173` → 회원가입(첫 가입=관리자) → 이미지 업로드 → 배포.

가맹점 40곳 자동 등록: `cd backend && python -m scripts.seed_naver 79daepo`

### B. 브랜드 전 지점 일괄 (CLI, 대표사진 등록)
```bash
cd gateway && source .venv/bin/activate

# 1) 전 지점 placeSeq·이름 스크랩 (diag/brand_6707_places.json 생성)
python -m app.inspect 79daepo brand 6707

# 2) 일괄 적용 (이미지 폴더 → 모든 지점). 처음엔 --limit 2 로 테스트 권장
GATEWAY_MOCK=0 python -m app.bulk_brand 79daepo 6707 "이미지폴더경로"

#   특정 지점만:        --file diag/brand_6707_targets.json
#   사진 한도 임박 지점: python -m app.replace_oldest 79daepo 6707 <placeSeq> <폴더> <삭제수>
```
> `6707`은 79대포 브랜드의 brandSeq. 다른 브랜드면 그 값으로 바꾸기.

---

## ⚠️ 넘기는 사람이 결정/전달할 것

| 항목 | 어떻게 |
|---|---|
| **AWS 키** | 받는 사람이 새로 발급하거나, 안전한 채널로 전달 (1Password 등) |
| **네이버 79대포 로그인** | 세션 시드에 필요. 공유 여부는 본사 정책에 따라 결정 |
| **brandSeq / 지점 데이터** | `app.inspect`로 받는 사람이 직접 다시 스크랩 (repo엔 미포함) |

## 보안 메모
- `.env`, `gateway/sessions/`(쿠키), `*.db`, `diag/`는 **git에 안 올라갑니다.** 절대 커밋·공유 금지.
- 네이버 자동화는 이용약관·봇탐지 리스크가 있으니 **본사 직영/통합 브랜딩 목적**으로만, 무리한 대량·고속 실행은 피하세요.
