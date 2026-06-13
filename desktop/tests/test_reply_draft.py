"""Pure-logic tests for AI reply drafting (no Anthropic SDK, no network)."""

import reply_draft
from reply_draft import build_system_blocks, build_user_prompt, draft_one, to_csv


# ---- system blocks (cached prefix) -----------------------------------------
def test_system_block_has_cache_control():
    blocks = build_system_blocks()
    assert len(blocks) == 1
    assert blocks[0]["type"] == "text"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "답글" in blocks[0]["text"]


def test_brand_instructions_appended():
    blocks = build_system_blocks("우리는 '79대포' 입니다. 항상 '대포가족'이라 부릅니다.")
    assert "브랜드 지침" in blocks[0]["text"]
    assert "대포가족" in blocks[0]["text"]


def test_blank_brand_no_section():
    assert "브랜드 지침" not in build_system_blocks("   ")[0]["text"]


# ---- user prompt (per-review, after the cached prefix) ---------------------
def test_user_prompt_includes_fields():
    p = build_user_prompt({"작성자": "홍길동", "별점": 5, "내용": "국물이 끝내줘요"})
    assert "홍길동" in p
    assert "5/5" in p
    assert "국물이 끝내줘요" in p


def test_user_prompt_handles_missing():
    p = build_user_prompt({"작성자": "", "별점": "", "내용": ""})
    assert "익명" in p
    assert "정보 없음" in p
    assert "(내용 없음)" in p


# ---- draft_one with a fake client (no network) -----------------------------
class _FakeBlock:
    type = "text"
    def __init__(self, text):
        self.text = text


class _FakeResp:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _FakeMessages:
    def __init__(self, recorder):
        self._rec = recorder
    def create(self, **kwargs):
        self._rec.append(kwargs)
        return _FakeResp("  소중한 리뷰 감사합니다! 또 들러주세요.  ")


class _FakeClient:
    def __init__(self):
        self.calls = []
        self.messages = _FakeMessages(self.calls)


def test_draft_one_uses_model_system_and_trims():
    client = _FakeClient()
    blocks = build_system_blocks("브랜드")
    out = draft_one(client, {"작성자": "kim", "별점": 4, "내용": "좋아요"}, blocks)
    assert out == "소중한 리뷰 감사합니다! 또 들러주세요."  # trimmed
    sent = client.calls[0]
    assert sent["model"] == reply_draft.MODEL == "claude-opus-4-8"
    assert sent["system"] is blocks                      # same object → cache reuse
    assert sent["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "좋아요" in sent["messages"][0]["content"]


# ---- CSV -------------------------------------------------------------------
def test_to_csv_columns_and_blanks():
    rows = [{"지점명": "강남점", "작성자": "kim", "별점": 5, "작성일": "2026-06-08",
             "내용": "맛있어요", "답글초안": "감사합니다", "오류": None}]
    out = to_csv(rows)
    header, line = out.strip().splitlines()
    row = dict(zip(header.split(","), line.split(",")))
    assert row["답글초안"] == "감사합니다"
    assert row["오류"] == ""   # None → blank
