"""전 지점 통계(리포트) 수집의 순수 로직 — 브라우저 없이 테스트 가능한 부분.

네이버 스마트플레이스의 '통계' 화면을 지점마다 들어가 손으로 엑셀에 옮기던 일을
한 번에 모으기 위한 모듈입니다. 실제 수집(브라우저 구동)은 automation.py가 하고,
여기서는 **수집된 JSON에서 지표를 뽑고 / CSV로 만들고 / 합계를 내는** 로직만 둡니다.

⚠️ 네이버 종속(아직 미확정): 통계가 어떤 JSON 필드로 오는지는 실계정 1회 수집으로
확인해야 합니다. 그 매핑만 METRIC_FIELDS에서 바꾸면 되도록 설계했습니다."""

from __future__ import annotations

import csv
import io

# 우리가 모으려는 지표(열). 표시 라벨 → 후보 JSON 키들(여러 표기 대비).
# 실계정 수집 후 캡처된 키에 맞춰 이 후보 목록만 보강하면 됩니다.
METRIC_FIELDS: dict[str, tuple[str, ...]] = {
    "방문수": ("visit", "visitCount", "pv", "place_visit", "visitorCount"),
    "조회수": ("view", "viewCount", "inflow", "exposure", "read"),
    "리뷰수": ("review", "reviewCount", "totalReview", "reviewTotal"),
    "예약수": ("booking", "bookingCount", "reservation", "reserveCount"),
}

# 항상 먼저 나오는 식별 열 + 지표 열들.
CSV_COLUMNS: list[str] = ["지점명", "placeSeq", *METRIC_FIELDS.keys(), "수집상태"]


def _find_number(payload: object, keys: tuple[str, ...]) -> int | None:
    """중첩 dict/list 어디에 있든 후보 키 중 첫 숫자값을 찾는다. 못 찾으면 None.
    (네이버 응답 구조가 중첩이라 깊이 탐색이 안전하다.)"""
    if isinstance(payload, dict):
        for k, v in payload.items():
            if k in keys and isinstance(v, (int, float)):
                return int(v)
        for v in payload.values():
            found = _find_number(v, keys)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for v in payload:
            found = _find_number(v, keys)
            if found is not None:
                return found
    return None


def extract_metrics(payloads: list[dict], fields: dict[str, tuple[str, ...]] | None = None) -> dict[str, int | None]:
    """캡처된 JSON 응답들에서 지표를 뽑는다. 각 지표는 못 찾으면 None(= '읽기 실패',
    절대 0으로 위조하지 않음 — 가짜 성공 방지)."""
    fields = fields or METRIC_FIELDS
    out: dict[str, int | None] = {}
    for label, keys in fields.items():
        value = None
        for p in payloads:
            value = _find_number(p, keys)
            if value is not None:
                break
        out[label] = value
    return out


def build_row(name: str, place_seq: str, metrics: dict[str, int | None]) -> dict:
    """한 지점 결과 행. 지표가 하나도 안 잡히면 상태='읽기 실패'로 정직하게 표기."""
    got = sum(1 for v in metrics.values() if v is not None)
    status = "정상" if got == len(METRIC_FIELDS) else ("일부" if got else "읽기 실패")
    row = {"지점명": name or "", "placeSeq": place_seq, "수집상태": status}
    for label in METRIC_FIELDS:
        row[label] = metrics.get(label)
    return row


def to_csv(rows: list[dict]) -> str:
    """엑셀 한글 안 깨지게 utf-8-sig는 파일 저장 측에서. 여기선 CSV 문자열만.
    None 값은 빈 칸으로(0 아님)."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in CSV_COLUMNS})
    return buf.getvalue()


def summarize(rows: list[dict]) -> dict:
    """지점 합계 + 수집 성공/실패 개수. (읽기 실패한 지표는 합계에서 제외)"""
    totals = {label: 0 for label in METRIC_FIELDS}
    for r in rows:
        for label in METRIC_FIELDS:
            v = r.get(label)
            if isinstance(v, int):
                totals[label] += v
    return {
        "지점수": len(rows),
        "읽기실패": sum(1 for r in rows if r.get("수집상태") == "읽기 실패"),
        "합계": totals,
    }
