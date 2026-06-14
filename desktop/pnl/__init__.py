"""배달앱 손익계산서 엔진 — SmartPlace Bulk에 벤더링.

원본: 별도 레포 `baedal-pnl`(github.com/yuneunmi814-cmyk 추정). app/{importers,classify,
report,tax,manual} 서브패키지를 그대로 복사(상대 import라 무수정 동작)하고, FastAPI 웹
계층(main.py) 대신 데스크톱용 얇은 오케스트레이터만 새로 둔다.

핵심: **숫자는 결정론적 코드로**(LLM 불필요 — use_llm 기본 False면 규칙분류 + 기타비용
폴백). 입력은 사장님이 받은 정산 .xlsx **업로드**(스크랩 아님 → 약관·취약성 없음).
"""

from __future__ import annotations

from pathlib import Path

from .importers.baemin import BaeminPasswordRequired
from .importers.registry import import_file
from .manual.inputs import ManualInputs
from .report.aggregate import combine_and_classify
from .report.income_statement import as_lines, build_income_statement, render_xlsx
from .tax.vat import compute_vat

_MANUAL_FIELDS = (
    "food_cost", "labor", "rent", "utilities", "other_sga",
    "other_income", "interest_expense", "income_tax",
)


def generate_report(
    file_paths: list[str],
    *,
    baemin_password: str | None = None,
    tax_type: str = "general",        # general | simplified | exempt
    period: str = "",
    manual: dict | None = None,       # 식자재·인건비·임대료 등 수기입력(원)
    use_llm: bool = False,            # 기본 False = 무비용(규칙 분류 + 기타비용 폴백)
) -> dict:
    """배민/쿠팡이츠/요기요 정산 xlsx → 손익계산서. (main.py::generate 미러)

    반환: lines/net_income/operating_profit/warnings/unresolved/period/
    needs_baemin_password + xlsx_bytes(바이트) + xlsx_filename."""
    manual = manual or {}
    frames, warnings, payout_reported = [], [], 0.0
    detected_period = period
    needs_baemin_password = False

    for path in file_paths:
        name = Path(path).name
        try:
            res = import_file(path, baemin_password or None)
            frames.append(res.rows)
            payout_reported += res.payout_reported
            if res.period and not detected_period:
                detected_period = res.period
            if res.notes:
                warnings.append(f"[{name}] {res.notes}")
        except BaeminPasswordRequired as exc:
            needs_baemin_password = True
            warnings.append(f"[{name}] 🔒 {exc}")
        except Exception as exc:  # noqa: BLE001 — 한 파일 실패가 전체를 막지 않게
            warnings.append(f"[{name}] 처리 실패: {exc}")

    m = ManualInputs(period=detected_period,
                     **{k: float(manual.get(k, 0) or 0) for k in _MANUAL_FIELDS})
    frames.append(m.to_rows())

    df, unresolved = combine_and_classify(frames, use_llm=use_llm)

    # 검증용: 면세(총액) 기준 영업이익 ↔ 파일 입금액
    gross_df, _ = compute_vat(df.copy(), "exempt")
    gross_stmt = build_income_statement(gross_df, period=detected_period)

    # 과세유형별 VAT 처리 후 손익
    adj_df, vat_summary = compute_vat(df, tax_type)
    stmt = build_income_statement(adj_df, period=detected_period)

    if payout_reported:
        platform_op = (gross_stmt.revenue
                       - sum(v for k, v in gross_stmt.sga_detail.items()
                             if k in ("지급수수료", "운반비", "광고선전비", "판매촉진비")))
        diff = round(platform_op - payout_reported)
        stmt.warnings.append(
            f"플랫폼 정산입금액(파일) {payout_reported:,.0f}원 ↔ "
            f"플랫폼기여 영업이익(총액) {platform_op:,.0f}원 (차이 {diff:,.0f}원, VAT·만나서결제 등)")
    if unresolved:
        stmt.warnings.append(
            "규칙 미매칭(검토→rules 승격 권장): " + ", ".join(unresolved[:20]))
    stmt.warnings.extend(warnings)

    return {
        "needs_baemin_password": needs_baemin_password,
        "tax_type": tax_type,
        "vat_summary": vat_summary,
        "period": stmt.period,
        "lines": [{"label": label, "amount": round(amt), "level": lvl}
                  for label, amt, lvl in as_lines(stmt)],
        "net_income": round(stmt.net_income),
        "operating_profit": round(stmt.operating_profit),
        "unresolved": unresolved,
        "warnings": stmt.warnings,
        "xlsx_bytes": render_xlsx(stmt, vat_summary),
        "xlsx_filename": f"손익계산서_{stmt.period or 'output'}.xlsx",
    }
