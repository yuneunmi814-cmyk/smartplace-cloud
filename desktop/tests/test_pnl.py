"""배달앱 손익계산서 엔진 end-to-end 테스트 (벤더링된 pnl/).

동봉 가짜 샘플(요기요)로 전체 파이프라인을 돌려 핵심 숫자 불변식을 검증한다.
원본 baedal-pnl 의 smoke_test 를 벤더 패키지 기준으로 옮긴 것 — 실데이터 없이
파서·분류·VAT·집계·엑셀 렌더가 안 깨지는지 보장한다."""

from pathlib import Path

import pnl
from pnl.importers.registry import import_file
from pnl.report.aggregate import combine_and_classify
from pnl.report.income_statement import build_income_statement, render_xlsx
from pnl.tax.vat import compute_vat

SAMPLE = str(Path(pnl.__file__).resolve().parent / "_sample" / "_FAKE_yogiyo_sample.xlsx")


# ---- 엔진 불변식 (원본 smoke_test) -----------------------------------------
def test_importer_recognizes_and_balances():
    res = import_file(SAMPLE)
    assert res.platform == "yogiyo"
    assert round(res.payout_reported) == 50580      # 정산입금액 검산
    assert "통과" in res.notes                        # 자동 검산 통과
    assert not res.rows.empty


def test_exempt_operating_profit_equals_payout():
    res = import_file(SAMPLE)
    df, _ = combine_and_classify([res.rows], use_llm=False)   # use_llm=False = 무비용
    ex_df, _ = compute_vat(df.copy(), "exempt")
    ex = build_income_statement(ex_df)
    assert round(ex.revenue) == 73000
    assert round(ex.operating_profit) == 50580       # 면세(총액) 영업이익 = 입금액


def test_vat_identity():
    res = import_file(SAMPLE)
    df, _ = combine_and_classify([res.rows], use_llm=False)
    ex = build_income_statement(compute_vat(df.copy(), "exempt")[0])
    gn_df, vat = compute_vat(df.copy(), "general")
    gn = build_income_statement(gn_df)
    # 면세 영업이익 − 일반 영업이익 = 일반과세 납부세액
    assert round(ex.operating_profit) - round(gn.operating_profit) == round(vat["payable"])
    assert vat["payable"] > 0
    assert len(render_xlsx(gn, vat)) > 1000          # 엑셀 산출물


# ---- 오케스트레이터 (데스크톱 진입점) --------------------------------------
def test_generate_report_end_to_end():
    out = pnl.generate_report([SAMPLE], tax_type="general")
    assert out["period"]                              # 기간 자동 감지
    assert out["lines"]                               # 손익 라인 생성
    assert isinstance(out["operating_profit"], int)
    assert len(out["xlsx_bytes"]) > 1000              # 보고서 바이트
    assert out["xlsx_filename"].endswith(".xlsx")
    assert out["needs_baemin_password"] is False      # 요기요는 암호화 아님
    # use_llm 기본 False → LLM(requests/Ollama) 미사용으로도 완주
