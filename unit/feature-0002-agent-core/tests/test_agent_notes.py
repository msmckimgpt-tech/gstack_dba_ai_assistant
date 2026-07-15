"""단위 테스트 — [세션, 제품] 자가리뷰·메모리 노트 (feature-0021).

검증 초점:
- 파일 캡(8KB) trim: 최신 항목 우선 보존, 중복 줄 제거.
- 프롬프트 주입 캡(REDTEAM_NOTES_INJECT_MAX_CHARS) + 비활성(0) 시 비주입.
- TTL sweep: mtime 초과 파일만 삭제.
- 격리: 제품 노트에 리뷰 claim(대화 파생 텍스트) 저장 금지 — axis 수준 사실만.

tmp_path 를 NOTES_ROOT 로 monkeypatch — /shared 실볼륨 불필요.
"""
from __future__ import annotations

import os
import time

import shared.runtime_settings as _rts
from modules import agent_notes


def _settings(monkeypatch, **overrides):
    values = {
        "REDTEAM_NOTES_ENABLED": 1,
        "REDTEAM_NOTES_SESSION_TTL_DAYS": 7,
        "REDTEAM_NOTES_PRODUCT_TTL_DAYS": 30,
        "REDTEAM_NOTES_INJECT_MAX_CHARS": 4000,
    }
    values.update(overrides)
    monkeypatch.setattr(_rts, "get_int", lambda key: values.get(key, 0))


def _use_tmp_root(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_notes, "NOTES_ROOT", str(tmp_path))


def test_update_and_load_session_note(monkeypatch, tmp_path):
    _settings(monkeypatch)
    _use_tmp_root(monkeypatch, tmp_path)
    review_meta = {
        "findings": [{"axis": "grounding", "severity": "BLOCK",
                      "claim": "부분 증거 전수 단정", "fix_hint": "표본 기준 명시"}],
        "revision_applied": True,
    }
    steps = [{"tool_name": "execute_sql", "args": {"sql": "SELECT * FROM sales.orders"}}]
    agent_notes.update_notes_after_answer(
        conversation_id="conv-1", product_id=7, steps=steps, review_meta=review_meta)

    ctx = agent_notes.load_notes_context("conv-1", 7)
    assert "SELF-REVIEW NOTES" in ctx
    assert "부분 증거 전수 단정" in ctx           # 세션 노트: claim 포함
    assert "orders" in ctx                        # 테이블 참조 기록

    # 격리: 제품 노트 파일에는 claim(대화 파생 텍스트) 저장 금지 — axis 만.
    ppath = agent_notes.product_note_path(7)
    ptext = open(ppath, encoding="utf-8").read()
    assert "부분 증거 전수 단정" not in ptext
    assert "grounding" in ptext


def test_notes_isolated_per_conversation(monkeypatch, tmp_path):
    _settings(monkeypatch)
    _use_tmp_root(monkeypatch, tmp_path)
    agent_notes.update_notes_after_answer(
        conversation_id="conv-A", product_id=None,
        steps=[{"tool_name": "execute_sql", "args": {"sql": "SELECT * FROM a_table"}}],
        review_meta=None)
    assert "a_table" in agent_notes.load_notes_context("conv-A", None)
    assert agent_notes.load_notes_context("conv-B", None) == ""


def test_inject_cap_and_disable(monkeypatch, tmp_path):
    _settings(monkeypatch, REDTEAM_NOTES_INJECT_MAX_CHARS=100)
    _use_tmp_root(monkeypatch, tmp_path)
    agent_notes.update_notes_after_answer(
        conversation_id="conv-1", product_id=None,
        steps=[{"tool_name": "execute_sql", "args": {"sql": f"SELECT * FROM t{i}"}} for i in range(10)],
        review_meta=None)
    assert len(agent_notes.load_notes_context("conv-1", None)) <= 100

    _settings(monkeypatch, REDTEAM_NOTES_INJECT_MAX_CHARS=0)
    assert agent_notes.load_notes_context("conv-1", None) == ""

    _settings(monkeypatch, REDTEAM_NOTES_ENABLED=0)
    assert agent_notes.load_notes_context("conv-1", None) == ""


def test_file_cap_trims_oldest(monkeypatch, tmp_path):
    _settings(monkeypatch)
    _use_tmp_root(monkeypatch, tmp_path)
    path = str(tmp_path / "session" / "c.md")
    entries = [f"[{i:04d}] " + "x" * 200 for i in range(100)]  # 캡(8KB) 초과 유도
    agent_notes._append_entries(path, "t", entries)
    text = open(path, encoding="utf-8").read()
    assert len(text.encode("utf-8")) <= agent_notes._FILE_CAP_BYTES
    assert "[0099]" in text      # 최신 항목 보존
    assert "[0000]" not in text  # 오래된 항목 trim


def test_append_dedupes(monkeypatch, tmp_path):
    _settings(monkeypatch)
    _use_tmp_root(monkeypatch, tmp_path)
    path = str(tmp_path / "session" / "d.md")
    agent_notes._append_entries(path, "t", ["같은 사실"])
    agent_notes._append_entries(path, "t", ["같은 사실"])
    assert open(path, encoding="utf-8").read().count("같은 사실") == 1


def test_sweep_expired(monkeypatch, tmp_path):
    _settings(monkeypatch, REDTEAM_NOTES_SESSION_TTL_DAYS=7, REDTEAM_NOTES_PRODUCT_TTL_DAYS=30)
    _use_tmp_root(monkeypatch, tmp_path)
    (tmp_path / "session").mkdir()
    (tmp_path / "product").mkdir()
    old_session = tmp_path / "session" / "old.md"
    new_session = tmp_path / "session" / "new.md"
    old_product = tmp_path / "product" / "old.md"
    for f in (old_session, new_session, old_product):
        f.write_text("x", encoding="utf-8")
    now = time.time()
    os.utime(old_session, (now - 8 * 86400, now - 8 * 86400))    # 세션 TTL(7d) 초과
    os.utime(old_product, (now - 10 * 86400, now - 10 * 86400))  # 제품 TTL(30d) 이내

    removed = agent_notes.sweep_expired_notes(now=now)
    assert removed == 1
    assert not old_session.exists()
    assert new_session.exists() and old_product.exists()


def test_safe_ident_sanitized(monkeypatch, tmp_path):
    _use_tmp_root(monkeypatch, tmp_path)
    path = agent_notes.session_note_path("../../etc/passwd")
    assert path is not None
    # 경로 이탈 방지: 구분자('/')가 '_' 로 치환되어 파일명이 session/ 디렉토리를 벗어날 수 없다.
    assert "/" not in os.path.basename(path)[:-3]  # (.md 확장자 제외)
    assert os.path.dirname(path) == os.path.join(str(tmp_path), "session")
    assert os.path.normpath(path).startswith(os.path.join(str(tmp_path), "session"))


def test_update_disabled_writes_nothing(monkeypatch, tmp_path):
    _settings(monkeypatch, REDTEAM_NOTES_ENABLED=0)
    _use_tmp_root(monkeypatch, tmp_path)
    agent_notes.update_notes_after_answer(
        conversation_id="conv-1", product_id=1,
        steps=[{"tool_name": "execute_sql", "args": {"sql": "SELECT 1"}}], review_meta=None)
    assert not (tmp_path / "session").exists()
