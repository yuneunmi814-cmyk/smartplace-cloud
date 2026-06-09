"""Regression tests for the upload success/failure decision.

These guard the "reported 성공 but nothing uploaded" bug: when the photo count
cannot be read back after saving, that must be treated as a FAILURE, never a
success. Pure-logic tests — no browser needed."""

import automation
from automation import _photo_verdict, parse_menu_csv


# ---- the bug: unreadable count must NOT be a success -----------------------
def test_unreadable_count_is_failure():
    # final=None happened when Naver's DOM/selector didn't match. The old code
    # skipped the check and reported success. It must now fail.
    msg = _photo_verdict(None, target=3, saved=True)
    assert msg is not None
    assert "확인 실패" in msg


def test_count_below_target_is_failure():
    msg = _photo_verdict(final=1, target=3, saved=True)
    assert msg is not None
    assert "미반영" in msg


def test_missing_save_button_is_hinted():
    # When the 저장하기 button wasn't found, the failure should say so.
    msg = _photo_verdict(final=0, target=2, saved=False)
    assert msg is not None
    assert "저장하기" in msg


def test_count_reached_target_is_success():
    assert _photo_verdict(final=3, target=3, saved=True) is None
    assert _photo_verdict(final=5, target=3, saved=True) is None


# ---- menu CSV parsing (used by the menu-bulk path) -------------------------
def test_parse_menu_csv(tmp_path):
    csv = tmp_path / "menu.csv"
    csv.write_text(
        "name,price,description,recommended\n"
        "빠삭파전,6900,겉바속촉,Y\n"
        ",0,빈줄은무시,N\n"
        "막걸리,9000,시원,no\n",
        encoding="utf-8-sig",
    )
    items = parse_menu_csv(str(csv))
    assert [i["name"] for i in items] == ["빠삭파전", "막걸리"]  # blank-name row dropped
    assert items[0]["price"] == "6900"
    assert items[0]["recommended"] is True
    assert items[1]["recommended"] is False


def test_module_imports_without_browser():
    # Importing the automation module must not require launching a browser.
    assert hasattr(automation, "apply_bulk")
