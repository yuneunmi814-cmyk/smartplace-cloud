"""SmartPlace Bulk (베타) — 데스크톱 앱.

네이티브 창(pywebview)에서 UI를 띄우고, 버튼을 누르면 automation.py(Playwright)가
실제 네이버 작업을 수행합니다. 특정 브랜드에 종속되지 않습니다(브랜드 번호 입력식).

실행:  python app.py
"""

import json
import os
import threading
from pathlib import Path

import webview

import automation
import license as licensing

window = None

# 라이선스 강제 여부. 기본 off → 현재 베타는 지금처럼 그대로 동작.
# 빌링이 라이브되면 SMARTPLACE_LICENSE_ENFORCE=1 로 켜면 미인증 시 실행이 막힘.
ENFORCE_LICENSE = os.environ.get("SMARTPLACE_LICENSE_ENFORCE", "0") == "1"
LICENSE_SERVER = os.environ.get("SMARTPLACE_LICENSE_SERVER", licensing.DEFAULT_SERVER)

# 메뉴 CSV 양식 (엑셀에서 채워서 업로드). utf-8-sig = 엑셀 한글 깨짐 방지.
MENU_TEMPLATE = (
    "name,price,description,image,recommended\n"
    "빠삭파전,6900,겉바속촉 빠삭파전,,Y\n"
    "생크림막걸리,9000,부드럽고 시원한 막걸리,,N\n"
    "소곱창전골,8900,가성비 좋은 소곱창전골,,N\n"
)


class Api:
    # ---- 라이선스 ----------------------------------------------------------
    def license_status(self) -> dict:
        s = licensing.status(server=LICENSE_SERVER)
        s["enforced"] = ENFORCE_LICENSE
        return s

    def activate_license(self, key: str) -> dict:
        s = licensing.status((key or "").strip(), server=LICENSE_SERVER)
        s["enforced"] = ENFORCE_LICENSE
        return s

    def _licensed(self) -> bool:
        """강제 모드일 때만 검사. 미강제면 항상 통과(베타)."""
        if not ENFORCE_LICENSE:
            return True
        return licensing.status(server=LICENSE_SERVER).get("licensed", False)

    def has_session(self) -> dict:
        return {"ok": automation.has_session()}

    def login(self) -> dict:
        try:
            return {"ok": automation.login()}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def scrape(self, brand_seq: str) -> dict:
        try:
            return {"branches": automation.scrape_branches(brand_seq.strip())}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def pick_folder(self) -> dict:
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        return {"folder": result[0] if result else None}

    def pick_csv(self) -> dict:
        result = window.create_file_dialog(
            webview.OPEN_DIALOG, file_types=("CSV 파일 (*.csv)", "모든 파일 (*.*)"))
        return {"path": result[0] if result else None}

    def save_template(self) -> dict:
        dest = window.create_file_dialog(webview.SAVE_DIALOG, save_filename="메뉴양식.csv")
        if not dest:
            return {"saved": None}
        path = dest if isinstance(dest, str) else dest[0]
        Path(path).write_text(MENU_TEMPLATE, encoding="utf-8-sig")
        return {"saved": path}

    def _run_bg(self, fn, done="onDone"):
        def run():
            def cb(done_, total, ps, ok, err):
                window.evaluate_js(
                    f"window.onProgress({done_},{total},{json.dumps(ps)},"
                    f"{str(bool(ok)).lower()},{json.dumps(err or '')})"
                )
            try:
                res = fn(cb)
                window.evaluate_js(f"window.{done}({json.dumps(res, ensure_ascii=False)})")
            except Exception as exc:  # noqa: BLE001
                window.evaluate_js(f"window.onError({json.dumps(str(exc))})")
        threading.Thread(target=run, daemon=True).start()
        return {"started": True}

    def apply(self, brand_seq: str, place_seqs: list, folder: str) -> dict:
        if not self._licensed():
            return {"error": "라이선스가 필요합니다. 상단에서 라이선스 키를 활성화하세요."}
        return self._run_bg(
            lambda cb: automation.apply_bulk(brand_seq.strip(), [str(s) for s in place_seqs], folder, cb))

    def apply_menu(self, brand_seq: str, place_seqs: list, csv_path: str,
                   image_dir: str, replace: bool) -> dict:
        if not self._licensed():
            return {"error": "라이선스가 필요합니다. 상단에서 라이선스 키를 활성화하세요."}
        return self._run_bg(
            lambda cb: automation.apply_menu_bulk(
                brand_seq.strip(), [str(s) for s in place_seqs],
                csv_path, image_dir or None, bool(replace), cb))

    def collect_reports(self, brand_seq: str, place_seqs: list) -> dict:
        """전 지점 통계 수집(읽기 전용). 결과는 window.onReportDone 으로."""
        if not self._licensed():
            return {"error": "라이선스가 필요합니다. 상단에서 라이선스 키를 활성화하세요."}
        return self._run_bg(
            lambda cb: automation.collect_reports(brand_seq.strip(), [str(s) for s in place_seqs], cb),
            done="onReportDone")

    def save_report_csv(self, rows: list) -> dict:
        import reports
        dest = window.create_file_dialog(webview.SAVE_DIALOG, save_filename="전지점_통계.csv")
        if not dest:
            return {"saved": None}
        path = dest if isinstance(dest, str) else dest[0]
        # utf-8-sig = 엑셀에서 한글 안 깨짐.
        Path(path).write_text(reports.to_csv(rows or []), encoding="utf-8-sig")
        return {"saved": path}

    def collect_reviews(self, brand_seq: str, place_seqs: list) -> dict:
        """전 지점 리뷰 수집(읽기 전용). 결과는 window.onReviewDone 으로."""
        if not self._licensed():
            return {"error": "라이선스가 필요합니다. 상단에서 라이선스 키를 활성화하세요."}
        return self._run_bg(
            lambda cb: automation.collect_reviews(brand_seq.strip(), [str(s) for s in place_seqs], cb),
            done="onReviewDone")

    def save_reviews_csv(self, rows: list) -> dict:
        import reviews
        dest = window.create_file_dialog(webview.SAVE_DIALOG, save_filename="전지점_리뷰.csv")
        if not dest:
            return {"saved": None}
        path = dest if isinstance(dest, str) else dest[0]
        Path(path).write_text(reviews.to_csv(rows or []), encoding="utf-8-sig")
        return {"saved": path}


def main() -> None:
    global window
    window = webview.create_window(
        "SmartPlace Bulk (베타)",
        "ui/index.html",
        js_api=Api(),
        width=920,
        height=760,
        min_size=(760, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
