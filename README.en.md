<p align="right"><a href="README.md">한국어</a> · <b>English</b></p>

# 📷 SmartPlace Bulk — Bulk manager for Naver SmartPlace

> A **desktop app for franchise HQs** that registers a **main photo and menu across every branch at once**.
> Log in to Naver → auto-load all branches → apply photos/menus to every store in one run.

> ⚠️ **Read the [DISCLAIMER](DISCLAIMER.md) before use.**
> This is an unofficial tool, not affiliated with Naver. Automation may conflict with Naver's Terms of Service, and you use it at your own risk. **Only use it on stores you own or manage.**

> 🇰🇷 Note: [Naver SmartPlace](https://smartplace.naver.com) is South Korea's business-listing platform (the local equivalent of a Google Business Profile), so this tool is primarily useful to businesses operating in Korea.

---

## Preview
<p align="center">
  <img src="docs/screenshot-main.png" width="49%" alt="App main — Naver login → load branches → photo/menu → run" />
  <img src="docs/screenshot-result.png" width="49%" alt="Bulk run — progress and success results" />
</p>

## What it does
For a franchise with tens to hundreds of branches, work that used to be done **one store at a time** on Naver SmartPlace is done **all at once**:
- 🖼️ **Bulk main photo** — push a standard image to every branch (set as the main photo)
- 🍽️ **Bulk menu** — unify a standard menu (CSV) across every branch (name, price, description, photo)
- 🏷️ Auto-scrape the branch list (all branches under a brand)

**Runs on the customer's PC with the customer's Naver account** → credentials never leave the machine (local-first).

> 🚀 **Where do I start?**
> · I just want to **use it** → [Download & install](#download--install) below (no setup, double-click)
> · I want to **run the code or contribute** → [⚡ Run from source in 5 minutes](#-run-from-source-in-5-minutes-for-developers--contributors)

## Download & install
[**▶ Download the latest version (Releases)**](../../releases/latest)

| OS | What you get | Guide |
|---|---|---|
| **Windows** | `SmartPlacePhoto-windows.zip` → unzip and run the `.exe` | [Windows guide (KO)](desktop/윈도우_실행가이드.md) |
| **Mac** | Run from source (`run.command`) | [Beginner guide (KO)](desktop/처음하는분_쉬운가이드.md) |

> If Windows shows a "protected your PC" warning → "More info" → "Run anyway" (a normal warning for an unsigned app).

## How to use (4 steps)
1. **Log in to Naver** — click the button to open the login window. Log in yourself (incl. CAPTCHA / 2FA).
2. **Load branches** — enter the brand number → all branches appear automatically.
3. **Choose a task** — main photo (folder) or menu (CSV).
4. **Run in bulk** — branches are processed one by one with a progress bar.

Menu CSV format: see [`desktop/menu_template.csv`](desktop/menu_template.csv)
```
name,price,description,image,recommended
Crispy Pajeon,6900,Crispy savory pancake,pajeon.jpg,Y
```

> 💡 The first time, **select just one branch** to test (it really does post to the live listing).

## Safety & privacy
- The Naver login session is stored **only on the user's PC**; nothing is sent externally.
- To avoid bot detection, branches are processed slowly with gaps in between.
- For limitations and risks, see the [DISCLAIMER](DISCLAIMER.md).

---

## ⚡ Run from source in 5 minutes (for developers & contributors)

> If you only want the finished app, the [Download & install](#download--install) section above is enough.
> To run the code or contribute, these 3 steps are all you need.

**Prerequisite**: Python 3.12+ only. (We just launch the desktop app — no Node, DB, or cloud needed.)

**① Clone**
```bash
git clone https://github.com/yuneunmi814-cmyk/smartplace-cloud.git
cd smartplace-cloud/desktop
```

**② Run** — whichever is easier:

- 🖱️ **Easiest**: double-click **`run.command` (Mac)** or **`run.bat` (Windows)** in your file explorer → it auto-installs the first time and launches the app.
- ⌨️ **Terminal**:
  ```bash
  python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
  pip install -r requirements.txt
  playwright install chromium                          # one-time (the slowest step)
  python app.py
  ```

**③ The app window opens — you're set!** 🎉 You'll see the 4-step screen (login → branches → task → run).

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

## License
MIT License — subject to the usage limits in the [DISCLAIMER](DISCLAIMER.md).
