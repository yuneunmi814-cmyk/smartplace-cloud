# 79대포 사진관리 (베타) — 데스크톱 앱

네이티브 앱 창에서 **네이버 로그인 → 지점 자동 불러오기 → 이미지 일괄 등록**까지.
고객 PC에서 고객 네이버로 돌아가므로(Local-First) 자격증명·세션이 PC를 떠나지 않습니다.

## 실행 (개발/베타)
```bash
cd desktop
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python app.py
```
또는 macOS에서 **`run.command` 더블클릭** (처음엔 자동 설치 후 실행).

## 화면 흐름
1. **네이버 로그인** — 버튼 누르면 로그인 창. 직접 로그인(캡차·2차인증 포함) → 세션 저장(`~/.smartplace_beta/`)
2. **지점 불러오기** — 브랜드 번호(brandSeq, 79대포=6707) 입력 → 전 지점 자동 스크랩
3. **이미지 폴더 선택** — 올릴 사진들이 든 폴더
4. **등록 실행** — 선택 지점에 일괄 등록 + 진행률 (대표사진으로 설정)

## 구성
- `automation.py` — Playwright 자동화(로그인·스크랩·등록). 클라우드 게이트웨이에서 검증된 로직
- `app.py` — pywebview 네이티브 창 + JS↔Python 브릿지
- `ui/index.html` — 화면(UI)

## 다음 단계 (정식 출시용)
- **PyInstaller**로 `.app`/`.exe` 패키징 (Chromium 동봉)
- 라이선스 키 검증 + 결제(구독) 연동 — `cloud/backend`에 뼈대 있음
- brandSeq 자동 감지(로그인 후 브랜드 자동 인식)
- ⚠️ **정식 판매 전 네이버 약관 법무 검토 필수**
