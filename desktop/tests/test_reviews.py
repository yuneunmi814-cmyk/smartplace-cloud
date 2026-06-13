"""Pure-logic tests for review collection (no browser)."""

import reviews
from reviews import build_rows, extract_reviews, summarize, to_csv


def test_extract_nested_review_list():
    payloads = [{
        "data": {"reviews": [
            {"author": "kim", "rating": 5, "content": "맛있어요", "date": "2026-06-01"},
            {"nickname": "lee", "score": 3, "body": "보통", "createdAt": "2026-06-02"},
        ]}
    }]
    out = extract_reviews(payloads)
    assert len(out) == 2
    assert out[0]["작성자"] == "kim"
    assert out[0]["별점"] == 5
    assert out[0]["내용"] == "맛있어요"
    assert out[1]["작성자"] == "lee"
    assert out[1]["별점"] == 3


def test_extract_dedupes():
    one = {"author": "kim", "rating": 5, "content": "굿", "date": "2026-06-01"}
    out = extract_reviews([{"a": [one]}, {"b": {"c": one}}])
    assert len(out) == 1  # 같은 (작성자,내용,작성일)은 한 번만


def test_extract_ignores_non_reviews():
    # 내용/별점 둘 다 없는 dict는 리뷰가 아님
    out = extract_reviews([{"place": {"id": 1, "name": "강남점", "phone": "02-x"}}])
    assert out == []


def test_extract_none_when_empty():
    assert extract_reviews([]) == []
    assert extract_reviews([{"unrelated": 1}]) == []


def test_to_csv_blanks_missing():
    reviews_list = [{"작성자": "kim", "별점": "", "작성일": "", "내용": "굿"}]
    rows = build_rows("강남점", "111", reviews_list)
    out = to_csv(rows)
    header, line = out.strip().splitlines()
    row = dict(zip(header.split(","), line.split(",")))
    assert row["지점명"] == "강남점"
    assert row["placeSeq"] == "111"
    assert row["별점"] == ""        # 빈 별점은 빈 칸(0 아님)
    assert row["내용"] == "굿"


def test_summarize_avg_rating_and_failures():
    rows = (
        build_rows("A", "1", [{"작성자": "x", "별점": 5, "작성일": "", "내용": "a"},
                              {"작성자": "y", "별점": 3, "작성일": "", "내용": "b"}])
        + build_rows("B", "2", [{"작성자": "z", "별점": "", "작성일": "", "내용": "c"}])
    )
    s = summarize(rows, branch_count=3, failed_count=1)
    assert s["리뷰수"] == 3
    assert s["지점수"] == 3
    assert s["읽기실패"] == 1
    assert s["평균별점"] == 4.0   # (5+3)/2, 별점 없는 건 평균 제외


def test_content_truncated():
    long = "가" * 500
    out = extract_reviews([{"r": [{"content": long, "rating": 4}]}])
    assert len(out[0]["내용"]) == 300
