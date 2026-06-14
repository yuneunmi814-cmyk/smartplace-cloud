# `pnl/` — 배달앱 손익계산서 엔진 (벤더링)

별도 레포 **baedal-pnl**(배민/쿠팡이츠/요기요 정산 .xlsx → 손익계산서)의 계산 엔진을
SmartPlace Bulk 데스크톱 앱에 **복사(vendoring)** 한 것입니다.

- `importers/` — 플랫폼별 파서(`identify()`/`extract()`) + 레지스트리. 배민은 암호화(`msoffcrypto`).
- `classify/` — 항목명 → 계정과목 **규칙 분류**(`rules.py`). `llm.py`는 선택 폴백(Ollama, 기본 미사용).
- `report/` — 기간·플랫폼 통합(`aggregate.py`) + 손익계산서 계산·엑셀 렌더(`income_statement.py`).
- `tax/vat.py` — 과세유형(일반/간이/면세)별 VAT 처리.
- `manual/inputs.py` — 식자재·인건비 등 수기입력.
- `__init__.py` — 데스크톱용 오케스트레이터 `generate_report(...)` (원본 FastAPI `main.py` 대체).

## 원칙
- **숫자는 결정론적 코드로** — `use_llm=False`(기본)면 LLM/API 호출 0, 순수 로컬 계산(토큰비용 없음).
- **입력 = 업로드** — 사장님이 받은 정산 파일을 올림(스크랩 아님 → 약관·셀렉터 취약성 없음).

## 동기화
원본이 갱신되면 `app/{importers,classify,report,tax,manual}` 를 다시 복사하면 됩니다
(모든 import가 상대경로라 무수정 동작). 엔진을 직접 수정하면 원본과 디버전 주의.

테스트: `desktop/tests/test_pnl.py` (요기요 가짜 샘플로 end-to-end 검증).
