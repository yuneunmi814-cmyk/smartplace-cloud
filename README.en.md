<p align="right"><a href="README.md">한국어</a> · <b>English</b></p>

# SmartPlace Bulk — Bulk manager for Naver SmartPlace

> An **all-in-one desktop app for managing every Naver SmartPlace branch** — for store owners & franchise HQs.
> Bulk photo/menu · stats & review collection · AI reply drafts · **delivery-app (Baemin/Coupang Eats) P&L statement**, all in one place.

> **Read the [DISCLAIMER](DISCLAIMER.md) before use.**
> This is an unofficial tool, not affiliated with Naver. Automation may conflict with Naver's Terms of Service, and you use it at your own risk. **Only use it on stores you own or manage.**

> Note: [Naver SmartPlace](https://smartplace.naver.com) is South Korea's business-listing platform (the local equivalent of a Google Business Profile), so this tool is primarily useful to businesses operating in Korea.

---

## Preview
<p align="center">
  <img src="docs/screenshot-main.png" width="49%" alt="App main — Naver login → load branches → photo/menu → run" />
  <img src="docs/screenshot-result.png" width="49%" alt="Bulk run — progress and success results" />
</p>

## What it does
Work that used to be done **one store at a time** — now in one place:

**Naver SmartPlace**
- **Bulk main photo** — push a standard image to every branch (set as the main photo)
- **Bulk menu** — unify a standard menu (CSV) across every branch (name, price, description, photo)
- **Stats collection** — gather visits/views/reviews/bookings per branch into CSV (read-only)
- **Review collection** — gather author/rating/content into CSV (read-only)
- **AI reply drafts** — draft owner replies to collected reviews (Claude, *drafts only*)

**Delivery apps**
- **Delivery-app P&L** — Baemin/Coupang Eats/Yogiyo settlement files (.xlsx) → income-statement Excel (pure local calc, no token cost)

**Runs on the customer's PC with the customer's account** → credentials & files never leave the machine (local-first).
(Exception: AI reply drafts send review text to Anthropic using your own API key.)

> **Where do I start?**
> · I just want to **use it** → [Download & install](#download--install) below (no setup, double-click)
> · I want to **run the code or contribute** → [ Run from source in 5 minutes](#run-from-source-in-5-minutes-for-developers--contributors)

## Download & install
[**▶ Download the latest version (Releases)**](../../releases/latest)

| OS | What you get | Guide |
|---|---|---|
| **Windows** | `SmartPlacePhoto-windows.zip` → unzip and run the `.exe` | [Windows guide (KO)](desktop/윈도우_실행가이드.md) |
| **Mac** | Run from source (`run.command`) | [Beginner guide (KO)](desktop/처음하는분_쉬운가이드.md) |

> If Windows shows a "protected your PC" warning → "More info" → "Run anyway" (a normal warning for an unsigned app).

## User manual (by feature)

> No tech skills needed — just follow the on-screen order.
> Naver features (photo/menu/stats/reviews) need **① log in → ② load branches** first.
> The **delivery-app P&L** works without login.

### Common — getting started
1. **Log in to Naver** — `네이버 로그인` button → log in as usual (ID/password/CAPTCHA/2FA). `로그인됨 ` means done (stays logged in next time).
2. **Load branches** — enter the brand number → `지점 불러오기` → all branches appear; check the ones you want.
   > The **brand number (brandSeq)** is the number after `brandSeq=` in your SmartPlace *brand management* page URL.

### Bulk main photo
1. Choose **대표사진 일괄** → 2. `이미지 폴더 선택` (folder of photos) → 3. `실행`.
> The first time, **check just one branch** to test — it posts to the live listing.

### Bulk menu
1. **메뉴 일괄** → 2. `메뉴 양식(CSV) 받기`, fill it in Excel → 3. `작성한 CSV 선택` (+ image folder optional) → 4. optional **replace** checkbox ( deletes existing menus) → 5. `실행`.
```
name,price,description,image,recommended
Crispy Pajeon,6900,Crispy savory pancake,pajeon.jpg,Y
```

### Stats collection (read-only)
** 리포트 수집** → `실행` → gathers visits/views/reviews/bookings → `CSV로 저장`. Doesn't change any store info.

### Review collection (read-only)
** 리뷰 수집** → `실행` → author/rating/content/date → `CSV로 저장`.

### AI reply drafts
1. Collect reviews first → 2. open ` AI 답글 초안`, enter your **Anthropic API key** → 3. optional brand instructions → `AI 답글 초안 생성` → `CSV 저장`.
> **Drafts only** — review and post on Naver yourself. Review text is sent to Anthropic. Get a key at [console.anthropic.com](https://console.anthropic.com).

### Delivery-app P&L (no login)
1. Get **settlement files (.xlsx)** from Baemin/Coupang Eats/Yogiyo → 2. `정산 파일 선택` + tax type → 3. password if the Baemin file is encrypted → 4. optionally enter food/labor/rent/utility costs → 5. `손익계산서 생성` → review → `손익계산서(엑셀) 저장`.
> Pure local calc, **no AI/token cost** — files never leave your PC. (Baemin settlement files are password-protected; Coupang/Yogiyo aren't.)

## Safety & privacy
- The Naver login session is stored **only on the user's PC**; nothing is sent externally.
- To avoid bot detection, branches are processed slowly with gaps in between.
- For limitations and risks, see the [DISCLAIMER](DISCLAIMER.md).

---

## Run from source in 5 minutes (for developers & contributors)

> If you only want the finished app, the [Download & install](#download--install) section above is enough.
> To run the code or contribute, these 3 steps are all you need.

**Prerequisite**: Python 3.12+ only. (We just launch the desktop app — no Node, DB, or cloud needed.)

**① Clone**
```bash
git clone https://github.com/yuneunmi814-cmyk/smartplace-cloud.git
cd smartplace-cloud/desktop
```

**② Run** — whichever is easier:

- **Easiest**: double-click **`run.command` (Mac)** or **`run.bat` (Windows)** in your file explorer → it auto-installs the first time and launches the app.
- ⌨ **Terminal**:
  ```bash
  python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
  pip install -r requirements.txt
  playwright install chromium                          # one-time (the slowest step)
  python app.py
  ```

**③ The app window opens — you're set!** You'll see the 4-step screen (login → branches → task → run).

> To actually post listings you need to **log in with your own Naver account** and a brand you manage.
> (Credentials never leave your PC. The first time, **test with just one branch**.)

<details>
<summary>Troubleshooting</summary>

- No `python3` → install 3.12+ from [python.org](https://www.python.org/downloads/) (on Windows, check "Add to PATH" during install).
- `playwright install` hangs → network. It downloads Chromium (~150 MB), so a slow connection can exceed 5 minutes. Re-run to resume.
- macOS `run.command` says "unidentified developer" → right-click → "Open" once.
</details>

### Running the full cloud stack
Bringing up the backend (FastAPI) + web console (React) + gateway is documented step by step in **[HANDOFF.md](HANDOFF.md)** (Korean).

### Repository layout
```
desktop/   Desktop app (pywebview + Playwright) — the shipped executable ← the quickstart above
gateway/   CLI automation tools (bulk photo/menu, brand scraping)
backend/   FastAPI backend (multi-account, task queue, S3, license/subscription) + tests
web/       React admin console (images, dispatch, license management)
```
Build: `.github/workflows/build-windows-exe.yml` (auto-builds the Windows `.exe` via GitHub Actions).

## Contributing
PRs, issues, docs, and translations are all welcome Please read the **[Contributing guide](CONTRIBUTING.md)** first — it's written to get your first PR merged smoothly.

## License
MIT License — subject to the usage limits in the [DISCLAIMER](DISCLAIMER.md).
