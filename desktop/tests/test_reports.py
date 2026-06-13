"""Pure-logic tests for branch report collection (no browser)."""

import reports
from reports import build_row, extract_metrics, summarize, to_csv


# ---- metric extraction from captured JSON ----------------------------------
def test_extract_finds_nested_numbers():
    payloads = [
        {"data": {"summary": {"visitCount": 120, "reviewCount": 8}}},
        {"result": [{"bookingCount": 3}]},
    ]
    m = extract_metrics(payloads)
    assert m["방문수"] == 120
    assert m["리뷰수"] == 8
    assert m["예약수"] == 3
    # 조회수 후보 키가 없으니 None — 0이 아니라 None이어야 한다(가짜 0 금지)
    assert m["조회수"] is None


def test_extract_all_missing_is_none_not_zero():
    m = extract_metrics([{"unrelated": {"foo": 1}}])
    assert set(m.values()) == {None}


def test_extract_ignores_nonnumeric():
    m = extract_metrics([{"visitCount": "n/a", "reviewCount": 5}])
    assert m["방문수"] is None      # 문자열은 숫자로 인정 안 함
    assert m["리뷰수"] == 5


# ---- row + status honesty --------------------------------------------------
def test_row_status_reflects_read_success():
    full = build_row("79대포 강남", "111", {"방문수": 1, "조회수": 2, "리뷰수": 3, "예약수": 4})
    assert full["수집상태"] == "정상"
    partial = build_row("79대포 홍대", "222", {"방문수": 1, "조회수": None, "리뷰수": None, "예약수": None})
    assert partial["수집상태"] == "일부"
    none = build_row("79대포 부산", "333", {"방문수": None, "조회수": None, "리뷰수": None, "예약수": None})
    assert none["수집상태"] == "읽기 실패"


# ---- CSV (None -> blank, never 0) ------------------------------------------
def test_csv_blanks_none_not_zero():
    rows = [build_row("A", "1", {"방문수": 10, "조회수": None, "리뷰수": 2, "예약수": None})]
    out = to_csv(rows)
    lines = out.strip().splitlines()
    assert lines[0].split(",")[:2] == ["지점명", "placeSeq"]
    # 조회수/예약수는 빈 칸이어야(0이면 가짜 데이터)
    cells = lines[1].split(",")
    header = lines[0].split(",")
    row = dict(zip(header, cells))
    assert row["방문수"] == "10"
    assert row["조회수"] == ""
    assert row["예약수"] == ""


def test_summarize_excludes_failed_reads():
    rows = [
        build_row("A", "1", {"방문수": 10, "조회수": 5, "리뷰수": 1, "예약수": 0}),
        build_row("B", "2", {"방문수": None, "조회수": None, "리뷰수": None, "예약수": None}),
    ]
    s = summarize(rows)
    assert s["지점수"] == 2
    assert s["읽기실패"] == 1
    assert s["합계"]["방문수"] == 10   # 실패 지점은 합계에 안 들어감


def test_columns_stable():
    assert reports.CSV_COLUMNS[:2] == ["지점명", "placeSeq"]
    assert "수집상태" in reports.CSV_COLUMNS
