<p align="right">한국어 · <a href="#contributing-english">English</a></p>

# 기여 가이드 (Contributing)

먼저, 시간 내서 이 프로젝트를 봐주셔서 **감사합니다** 🙌
작은 오타 수정부터 새 기능까지, 모든 기여를 환영합니다. 이 문서는 여러분의 첫 PR이 **막히지 않고 머지되도록** 돕는 안내서입니다.

> 처음이신가요? GitHub에 익숙하지 않아도 괜찮습니다. 아래 순서만 따라오시면 됩니다.

---

## 무엇을 기여할 수 있나요?

코드만 기여가 아닙니다. 다 도움이 됩니다:

- 🐛 **버그 제보** — [이슈](../../issues/new)에 재현 방법을 적어주세요 (OS·단계·기대 결과·실제 결과)
- 📖 **문서 개선** — 오타, 헷갈리는 설명, 번역(특히 영어). 가장 환영하는 첫 기여예요
- ✨ **기능·개선** — 큰 변경은 먼저 이슈로 상의해 주세요 (헛수고 방지)
- 💡 **아이디어·피드백** — [Discussions/이슈]로 편하게

> 💚 **Good first issue** 라벨이 붙은 이슈가 있으면 거기서 시작하기 좋아요.

---

## 5분 개발 환경 세팅

전체 흐름은 [README의 "⚡ 소스에서 5분 실행"](README.md#-소스에서-5분-실행-개발자기여자용)을 그대로 따르면 됩니다. 핵심만:

```bash
git clone https://github.com/yuneunmi814-cmyk/smartplace-cloud.git
cd smartplace-cloud
```

이 저장소는 **모노레포**입니다. 고치려는 부분만 세팅하면 됩니다:

| 폴더 | 무엇 | 빠른 세팅 |
|---|---|---|
| `desktop/` | 데스크톱 앱 (pywebview + Playwright) | `cd desktop && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` |
| `backend/` | FastAPI 백엔드 (+ pytest) | `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt` |
| `gateway/` | CLI 자동화 도구 (+ pytest) | `cd gateway && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt` |
| `web/` | React 관리 콘솔 (Vite) | `cd web && npm install` |

> Windows는 `source .venv/bin/activate` 대신 `.venv\Scripts\activate`.

---

## PR 전에 — 로컬에서 검사 통과시키기 ✅

**CI가 모든 PR에서 아래 3가지를 자동으로 돌립니다.** 올리기 전에 로컬에서 먼저 통과시키면 한 번에 머지됩니다. (건드린 부분만 돌려도 OK)

```bash
# 백엔드를 고쳤다면
cd backend && python -m pytest

# 게이트웨이를 고쳤다면
cd gateway && python -m pytest

# 웹을 고쳤다면
cd web && npm run typecheck && npm run build
```

- **기능을 추가/수정하면 테스트도 같이** 올려주세요. 백엔드는 `backend/tests/`에 예시가 많습니다 (현재 44개 통과 중 — 깨지지 않게).
- 코드 스타일은 **주변 코드와 맞추면** 됩니다. 별도 강제 린터는 없습니다 (Python은 표준 라이브러리 우선, 타입힌트 권장 / 웹은 TypeScript strict).

---

## 브랜치 · 커밋 · PR

1. **브랜치**를 따로 만드세요 (main에 직접 X):
   ```bash
   git checkout -b fix/메뉴-csv-인코딩      # 또는 feat/..., docs/...
   ```
2. **커밋 메시지**는 *무엇을 왜* 바꿨는지 한 줄로. 한국어·영어 모두 좋아요.
   예) `fix: 메뉴 CSV utf-8-sig 누락으로 엑셀 한글 깨짐 수정`
3. **PR**을 `main`으로 올리고, 다음을 적어주세요:
   - 무엇을 바꿨고 **왜** 바꿨는지
   - 관련 이슈 번호 (`Closes #12`)
   - 화면 변경이면 **스크린샷**
4. CI(초록불)와 리뷰를 기다려주세요. 리뷰는 트집이 아니라 **같이 더 좋게** 만드는 과정입니다 🙂

작게 쪼갠 PR일수록 빨리 머지됩니다. 거대한 PR 하나보다 작은 PR 여러 개가 좋아요.

---

## 보안 · 비밀정보

- `.env`, 키, 세션 쿠키(`gateway/sessions/`), `*.db`, `diag/` 는 **절대 커밋 금지** (이미 `.gitignore` 처리됨).
- 라이선스 **개인키**는 서버 `.env`에만 — 코드/PR에 넣지 마세요. (공개키만 앱에 내장)
- 취약점을 발견하면 공개 이슈 대신 **비공개로** 알려주세요 (저장소 Security 탭 또는 메인테이너에게 DM).

---

## ⚠️ 꼭 지켜주세요 — 이 프로젝트의 범위

이 도구는 **본인이 소유·관리하는 매장**의 운영을 돕기 위한 것입니다. 기여 시:

- 네이버 **약관 위반을 조장하거나**, 봇 탐지 회피를 강화하거나, 무리한 대량·고속 실행을 부추기는 변경은 **받지 않습니다.**
- 타인 계정·무단 매장을 대상으로 하는 기능은 범위 밖입니다.
- 자세한 내용은 [DISCLAIMER](DISCLAIMER.md)를 읽어주세요.

서로 존중하며, 친절하게. 모두가 환영받는 커뮤니티를 함께 만들어요. 💚

---

# Contributing (English)

First off — **thank you** for taking the time to look at this project 🙌
Every contribution is welcome, from fixing a typo to adding a feature. This guide exists to make sure your **first PR gets merged smoothly**.

## Ways to contribute
- 🐛 **Report bugs** — open an [issue](../../issues/new) with repro steps (OS, steps, expected vs actual).
- 📖 **Improve docs** — typos, unclear wording, translations (English especially). A great first contribution.
- ✨ **Features / fixes** — for larger changes, please open an issue first so we can align.
- 💡 **Ideas & feedback** — issues/discussions are open.

> Look for the **good first issue** label to get started.

## Dev setup in 5 minutes
Follow [README → "Run from source in 5 minutes"](README.en.md#-run-from-source-in-5-minutes-for-developers--contributors). This is a **monorepo** — only set up the part you're changing:

| Folder | What | Quick setup |
|---|---|---|
| `desktop/` | Desktop app (pywebview + Playwright) | `cd desktop && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` |
| `backend/` | FastAPI backend (+ pytest) | `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt` |
| `gateway/` | CLI automation (+ pytest) | `cd gateway && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt` |
| `web/` | React admin console (Vite) | `cd web && npm install` |

> On Windows use `.venv\Scripts\activate`.

## Before you open a PR ✅
**CI runs these on every PR** — pass them locally first for a one-shot merge (only what you touched is fine):

```bash
cd backend && python -m pytest          # if you changed the backend
cd gateway && python -m pytest          # if you changed the gateway
cd web && npm run typecheck && npm run build   # if you changed the web app
```

- **Add tests with your change.** `backend/tests/` has plenty of examples (44 passing — keep them green).
- Match the surrounding code style. No enforced linter; Python favors the standard library + type hints, the web app uses strict TypeScript.

## Branch · commit · PR
1. Work on a branch (not `main`): `git checkout -b fix/...` / `feat/...` / `docs/...`
2. Write a one-line commit explaining **what & why** (Korean or English both fine).
3. Open the PR against `main` with: what/why, related issue (`Closes #12`), and screenshots for UI changes.
4. Wait for green CI and review — review is collaboration, not criticism 🙂

Small PRs merge faster than one giant PR.

## Security & secrets
- Never commit `.env`, keys, session cookies (`gateway/sessions/`), `*.db`, or `diag/` (already gitignored).
- The license **private key** lives only in the server `.env` — never in code/PRs (the app ships the public key only).
- Found a vulnerability? Report it **privately** (repo Security tab) rather than a public issue.

## ⚠️ Project scope — please respect
This tool helps you manage **stores you own or operate**. We **do not accept** changes that encourage Terms-of-Service violations, strengthen bot-detection evasion, or push aggressive high-volume automation. Features targeting other people's accounts/stores are out of scope. See the [DISCLAIMER](DISCLAIMER.md).

Be kind and respectful — let's build a welcoming community together. 💚
