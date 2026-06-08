"""79대포 사진관리 (베타) — 데스크톱 앱.

네이티브 창(pywebview)에서 UI를 띄우고, 버튼을 누르면 automation.py(Playwright)가
실제 네이버 작업을 수행합니다.

실행:  python app.py
"""

import json
import threading

import webview

import automation

window = None


class Api:
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

    def _run_bg(self, fn):
        def run():
            def cb(done, total, ps, ok, err):
                window.evaluate_js(
                    f"window.onProgress({done},{total},{json.dumps(ps)},"
                    f"{str(bool(ok)).lower()},{json.dumps(err or '')})"
                )
            try:
                res = fn(cb)
                window.evaluate_js(f"window.onDone({json.dumps(res)})")
            except Exception as exc:  # noqa: BLE001
                window.evaluate_js(f"window.onError({json.dumps(str(exc))})")
        threading.Thread(target=run, daemon=True).start()
        return {"started": True}

    def apply(self, brand_seq: str, place_seqs: list, folder: str) -> dict:
        return self._run_bg(
            lambda cb: automation.apply_bulk(brand_seq.strip(), [str(s) for s in place_seqs], folder, cb))

    def apply_menu(self, brand_seq: str, place_seqs: list, csv_path: str,
                   image_dir: str, replace: bool) -> dict:
        return self._run_bg(
            lambda cb: automation.apply_menu_bulk(
                brand_seq.strip(), [str(s) for s in place_seqs],
                csv_path, image_dir or None, bool(replace), cb))


def main() -> None:
    global window
    window = webview.create_window(
        "79대포 사진관리 (베타)",
        "ui/index.html",
        js_api=Api(),
        width=920,
        height=760,
        min_size=(760, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
