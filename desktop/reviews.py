"""전 지점 리뷰 수집의 순수 로직 — 브라우저 없이 테스트 가능한 부분.

운영자가 지점마다 들어가 새 리뷰를 확인하던 일을 한곳에 모으기 위한 모듈입니다.
실제 수집(브라우저)은 automation.py가 하고, 여기서는 **캡처된 JSON에서 리뷰를 뽑고
/ 중복 제거 / CSV로 만들고 / 요약**하는 로직만 둡니다.

⚠️ 네이버 종속(미확정): 리뷰가 어떤 JSON 필드로 오는지는 실계정 1회 수집으로 확인.
그 매핑만 REVIEW_FIELDS에서 바꾸면 됩니다. 못 읽으면 가짜 데이터 대신 '읽기 실패'."""

from __future__ import annotations

import csv
import io

# 리뷰 한 건의 필드 → 후보 JSON 키들(여러 표기 대비). 실데이터 확인 후 보강.
REVIEW_FIELDS: dict[str, tuple[str, ...]] = {
    "작성자": ("author", "nickname", "writer", "userName", "name"),
    "별점": ("rating", "score", "star", "starRating"),
    "작성일": ("date", "created", "createdAt", "writeDate", "visitDate", "visited"),
    "내용": ("content", "body", "text", "reviewBody", "comment", "review"),
}

CSV_COLUMNS = ["지점명", "placeSeq", "작성자", "별점", "작성일", "내용"]


def _first(d: dict, keys: tuple[str, ...]):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return None


def _as_review(d: dict, fields: dict[str, tuple[str, ...]]) -> dict | None:
    """dict가 리뷰처럼 보이면(내용 또는 별점 보유) 정규화해 반환, 아니면 None."""
    content = _first(d, fields["내용"])
    rating = _first(d, fields["별점"])
    if content is None and rating is None:
        return None
    return {
        "작성자": str(_first(d, fields["작성자"]) or "").strip(),
        "별점": rating if isinstance(rating, (int, float)) else "",
        "작성일": str(_first(d, fields["작성일"]) or "").strip(),
        "내용": str(content).strip()[:300] if content is not None else "",
    }


def extract_reviews(payloads: list, fields: dict[str, tuple[str, ...]] | None = None) -> list[dict]:
    """캡처된 JSON(중첩 가능) 어디에 있든 리뷰처럼 보이는 dict를 모은다.
    (작성자, 내용, 작성일)로 중복 제거. 못 찾으면 빈 리스트(가짜 생성 안 함)."""
    fields = fields or REVIEW_FIELDS
    found: list[dict] = []
    seen: set = set()

    def walk(node):
        if isinstance(node, dict):
            r = _as_review(node, fields)
            if r and (r["내용"] or r["작성자"]):
                key = (r["작성자"], r["내용"], r["작성일"])
                if key not in seen:
                    seen.add(key)
                    found.append(r)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for p in payloads:
        walk(p)
    return found


def build_rows(place_name: str, place_seq: str, reviews: list[dict]) -> list[dict]:
    return [{"지점명": place_name or "", "placeSeq": place_seq, **r} for r in reviews]


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in CSV_COLUMNS})
    return buf.getvalue()


def summarize(rows: list[dict], branch_count: int, failed_count: int) -> dict:
    """총 리뷰수 / 지점수 / 읽기 실패 지점수 / 평균 별점(숫자 별점만)."""
    ratings = [r["별점"] for r in rows if isinstance(r.get("별점"), (int, float))]
    avg = round(sum(ratings) / len(ratings), 2) if ratings else None
    return {
        "리뷰수": len(rows),
        "지점수": branch_count,
        "읽기실패": failed_count,
        "평균별점": avg,
    }
