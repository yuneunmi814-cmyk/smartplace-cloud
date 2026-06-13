"""AI 답글 초안 생성 — 네이버 스마트플레이스 리뷰에 대한 사장님 답글을 Claude로 초안 작성.

**초안만** 만듭니다. 사람이 검토·수정 후 직접 게시합니다(자동 게시 없음).

설계:
- 모델: claude-opus-4-8 (최신 Claude).
- 공유 system/브랜드 지침은 **prompt caching**(cache_control)으로 리뷰 여러 건에 걸쳐 재사용.
  (Opus 4.8 최소 캐시 프리픽스는 ~4096토큰 — 브랜드 지침이 짧으면 캐시가 안 걸릴 수 있으나
   무해하며, 브랜드 컨텍스트가 길수록 비용을 크게 아낍니다.)
- 리뷰별 1회 호출(인터랙티브 응답성) + 한 건 실패가 배치를 막지 않음.
- 순수 로직(프롬프트 조립·CSV)은 SDK 없이 테스트 가능하도록 anthropic은 지연 import.

API 키는 사용자가 입력합니다. 리뷰 본문이 Anthropic API로 전송된다는 점을 사용자에게 고지하세요.
"""

from __future__ import annotations

import csv
import io

MODEL = "claude-opus-4-8"
MAX_TOKENS = 400  # 답글은 짧음

# 캐시되는 공유 프리픽스(안정적). 브랜드 지침만 뒤에 끼워 넣습니다.
_SYSTEM_BASE = """당신은 네이버 스마트플레이스 고객 리뷰에 대한 **사장님 답글 초안**을 쓰는 도우미입니다.

규칙:
- 한국어로, 정중하고 따뜻하게. 과한 이모지·과장·영업 멘트 금지.
- 별점 4~5: 진심 어린 감사 + 재방문을 가볍게 유도.
- 별점 1~2: 먼저 사과·공감 → 구체적 개선 의지 → (가능하면) 직접 연락 유도. 변명·반박 금지.
- 별점 3 또는 미상: 감사 + 개선 의지를 간단히.
- 리뷰에서 언급된 내용을 최소 1가지 구체적으로 반영(민감정보·개인정보는 다시 적지 말 것).
- 1~3문장, 대략 30~150자. 매장/브랜드명을 모르면 지어내지 말 것.
- **출력은 답글 본문만.** 머리말("답글:")·따옴표·설명·이모지 남발 없이 본문 텍스트만 쓰세요."""


def build_system_blocks(brand_instructions: str = "") -> list[dict]:
    """캐시 가능한 system 블록. 안정적 프리픽스 끝에 cache_control을 둔다.
    같은 브랜드 지침으로 리뷰 여러 건을 처리하면 두 번째 요청부터 캐시 read."""
    text = _SYSTEM_BASE
    brand = (brand_instructions or "").strip()
    if brand:
        text += "\n\n[브랜드 지침]\n" + brand
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def build_user_prompt(review: dict) -> str:
    """리뷰 한 건 → 사용자 메시지(캐시 프리픽스 뒤의 가변 부분)."""
    author = (review.get("작성자") or "익명").strip() or "익명"
    rating = review.get("별점")
    rating_str = f"{rating}/5" if isinstance(rating, (int, float)) else "정보 없음"
    content = (review.get("내용") or "").strip() or "(내용 없음)"
    return (
        "다음 리뷰에 대한 답글 초안을 작성하세요.\n\n"
        f"작성자: {author}\n"
        f"별점: {rating_str}\n"
        "내용:\n"
        f"{content}"
    )


def _extract_text(resp) -> str:
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()


def draft_one(client, review: dict, system_blocks: list[dict], model: str = MODEL) -> str:
    """리뷰 한 건의 답글 초안. system_blocks는 캐시 재사용을 위해 동일 객체를 넘긴다."""
    resp = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system_blocks,
        messages=[{"role": "user", "content": build_user_prompt(review)}],
    )
    return _extract_text(resp)


def draft_replies(api_key: str, reviews: list[dict], *, brand_instructions: str = "",
                  model: str = MODEL, progress_cb=None) -> list[dict]:
    """리뷰 목록 → 각 리뷰에 '답글초안' 필드를 더한 행 목록. 쓰기/게시 없음(초안만).
    한 건이 실패해도 멈추지 않고 '오류' 필드에 사유를 남긴다."""
    import anthropic  # 지연 import: 순수 로직 테스트는 SDK 없이 가능

    if not api_key:
        raise ValueError("Anthropic API 키가 필요합니다.")
    client = anthropic.Anthropic(api_key=api_key)
    system_blocks = build_system_blocks(brand_instructions)

    out: list[dict] = []
    total = len(reviews)
    for i, r in enumerate(reviews, 1):
        err = None
        draft = ""
        try:
            draft = draft_one(client, r, system_blocks, model)
        except Exception as exc:  # noqa: BLE001 — keep going on failure
            err = str(exc)
        out.append({**r, "답글초안": draft, "오류": err or ""})
        if progress_cb:
            progress_cb(i, total, r.get("작성자", ""), err is None, err or "")
    return out


CSV_COLUMNS = ["지점명", "작성자", "별점", "작성일", "내용", "답글초안", "오류"]


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in CSV_COLUMNS})
    return buf.getvalue()
