"""feature-0027 (P0-A) — run_post_answer_curation + 경로 배선 계약 테스트.

배경: topic/용어/ENUM 부가 LLM 3건이 KV terminal *전* 직렬 실행돼 답변 체감 지연에
+25~35s(feature-0026 S9 실측). §18.8 패널(backend/qa) 흡수 후 계약:
1. 패키지 None/비정상 → no-op. 함수 내부 `_writes_allowed` 재검증 실패(삭제 요청) → 무기록
   (backend B1 — 삭제 후 topic/제안 부활 차단).
2. 실행 시 3함수 호출 + datasource ContextVar = 패키지 캡처값 + cfg run/conv 전역 귀속
   (backend C1) + KV last_post_answer_ms 기록.
3. 종료/실패 시 datasource·전역을 **이전 값으로 복원**(None 강제 아님 — in-process 인라인
   호출이 run 도중이므로) + 예외 무전파.
4. 배선(소스 잠금): worker=finish_ask_job 후 실행·사전 pop / in-core=defer 분기(worker 패키지
   vs in-process 인라인) + 비성공 종결 패키지 폐기 (fail-open 이 배선 소실을 은폐하지 못하게).
"""

from __future__ import annotations

import agent_core
from shared import config as cfg


def _patch(monkeypatch, calls, fail_topic=False, writes_allowed=True):
    def _topic(conn, cid, um, ans, hl):
        calls.append(("topic", cfg.get_active_datasource(), cfg.CURRENT_RUN_ID, hl))
        if fail_topic:
            raise RuntimeError("boom")

    monkeypatch.setattr(agent_core, "_writes_allowed", lambda conn, cid: writes_allowed)
    monkeypatch.setattr(agent_core, "_try_update_topic", _topic)
    monkeypatch.setattr(agent_core, "_glossary_autopropose",
                        lambda cid, um, ans, rid: calls.append(("glossary", cfg.get_active_datasource())))
    monkeypatch.setattr(agent_core, "_enum_autopropose",
                        lambda cid, um, ans, rid: calls.append(("enum", cfg.get_active_datasource())))
    monkeypatch.setattr(agent_core, "save_memory_kv",
                        lambda conn, cid, k, v: calls.append(("kv", k, v)))


def _payload(**over):
    p = {"conversation_id": "cid-1", "user_message": "u", "answer": "a",
         "history_len": 3, "run_id": "run-77",
         "datasource_key": "ds-alpha", "datasource_engine": "mssql",
         "datasource_default_db": "gamedb"}
    p.update(over)
    return p


def test_noop_on_none_and_invalid(monkeypatch):
    calls: list = []
    _patch(monkeypatch, calls)
    agent_core.run_post_answer_curation(None)
    agent_core.run_post_answer_curation("not-a-dict")
    agent_core.run_post_answer_curation({"conversation_id": ""})
    assert calls == []


def test_writes_allowed_recheck_blocks_after_delete(monkeypatch):
    # §18.8 backend B1/qa C2: 실행 시점 삭제 재검증 — False 면 topic/제안/KV 전부 무기록.
    calls: list = []
    _patch(monkeypatch, calls, writes_allowed=False)
    agent_core.run_post_answer_curation(_payload())
    assert calls == []
    assert cfg.get_active_datasource() is None  # 컨텍스트 복원(사전값 None)


def test_runs_all_three_with_captured_context_and_attribution(monkeypatch):
    calls: list = []
    _patch(monkeypatch, calls)
    cfg.set_active_datasource(None)
    monkeypatch.setattr(cfg, "CURRENT_RUN_ID", "other-run", raising=False)
    monkeypatch.setattr(cfg, "MEMORY_CONVERSATION_ID", "other-conv", raising=False)
    agent_core.run_post_answer_curation(_payload())
    kinds = [c[0] for c in calls]
    assert kinds[:3] == ["topic", "glossary", "enum"]
    assert all(c[1] == "ds-alpha" for c in calls[:3])  # datasource 캡처 컨텍스트
    assert calls[0][2] == "run-77"  # §18.8 backend C1: usage 귀속 전역 = 패키지 run_id
    assert calls[0][3] == 3
    kv = [c for c in calls if c[0] == "kv"]
    assert kv and kv[0][1] == "last_post_answer_ms" and float(kv[0][2]) >= 0.0
    # 종료 후 이전 값 복원
    assert cfg.get_active_datasource() is None
    assert cfg.CURRENT_RUN_ID == "other-run"
    assert cfg.MEMORY_CONVERSATION_ID == "other-conv"


def test_restores_previous_datasource_context(monkeypatch):
    # in-process 인라인 호출(run 도중) — None 강제 리셋이 아니라 이전 컨텍스트 복원이어야 한다.
    calls: list = []
    _patch(monkeypatch, calls)
    cfg.set_active_datasource("ds-before", engine="mysql", default_db="beforedb")
    try:
        agent_core.run_post_answer_curation(_payload())
        assert cfg.get_active_datasource() == "ds-before"
        assert cfg.get_active_default_db() == "beforedb"
    finally:
        cfg.set_active_datasource(None)


def test_context_reset_and_no_raise_on_failure(monkeypatch):
    calls: list = []
    _patch(monkeypatch, calls, fail_topic=True)
    cfg.set_active_datasource(None)
    agent_core.run_post_answer_curation(_payload())  # 예외 무전파
    assert cfg.get_active_datasource() is None


# ── §18.8 qa C4/backend B2·C2: 배선·게이트 소스 잠금 (fail-open 은폐 방지) ─────────
def test_wiring_order_locked_in_source():
    import inspect
    from pathlib import Path

    core_src = inspect.getsource(agent_core._run_agent_core)
    asm_idx = core_src.index('_cur_pkg = {')
    gate_idx = core_src.rindex("if answer and _writes_allowed(mem_conn, cid):", 0, asm_idx)
    assert asm_idx - gate_idx < 600, "패키지 조립은 answer+_writes_allowed 게이트 직하"
    # 경로 분기: worker=패키지 / in-process=인라인 즉시(§18.8 backend B2 — done 후 실행 금지)
    defer_idx = core_src.index('if defer_terminal_status:', asm_idx)
    pkg_idx = core_src.index('result["_post_answer_curation"] = _cur_pkg', defer_idx)
    inline_idx = core_src.index('run_post_answer_curation(_cur_pkg)', pkg_idx)
    assert defer_idx < pkg_idx < inline_idx
    # in-core 에 done-후 실행 경로가 없다 (B2 재개방 방지)
    assert 'run_post_answer_curation(result.pop' not in core_src
    # 비성공 종결 패키지 폐기 (backend B1)
    assert 'result.pop("_post_answer_curation", None)' in core_src

    ask_src = (Path(agent_core.__file__).parent / "modules" / "ask.py").read_text(encoding="utf-8")
    pop_idx = ask_src.index('_curation_pkg = result.pop("_post_answer_curation"')
    fin_idx = ask_src.index("finish_ask_job(conn, job_id, lease, status")
    wcur_idx = ask_src.index("run_post_answer_curation(_curation_pkg)")
    assert pop_idx < fin_idx < wcur_idx, "worker 큐레이션은 job terminal 전이(finish) 후"
    assert "from agent_core import run_post_answer_curation" in ask_src
    assert hasattr(agent_core, "run_post_answer_curation")  # rename 가드


def test_knowledge_context_shares_single_ro_conn(monkeypatch):
    """(P0-D) grounding 3개 로더가 동일 conn 객체를 받고, 그 conn 의 close 는 정확히
    1회(소유=호출측). `_pg_connect_ro` 는 호출마다 새 객체를 반환하게 스텁 — 같은 객체를
    재반환하면 env 플래그(예: account recall)로 열리는 *다른* 소비자의 owned-close 가 공유
    conn 카운트에 오염된다(전체 스위트에서만 실패하던 픽스처 결함의 교훈). 임베딩/recall
    경로는 플래그 off 로 결정화(컨테이너 .env 무관)."""
    import shared.db as sdb
    import shared.config as scfg

    class _RoConn:
        def __init__(self):
            self.closed = 0

        def close(self):
            self.closed += 1

    conns: list = []

    def _mk(*a, **k):
        c = _RoConn()
        conns.append(c)
        return c

    seen: list = []
    monkeypatch.setattr(sdb, "_pg_available", lambda: True)
    monkeypatch.setattr(sdb, "_pg_connect_ro", _mk)
    monkeypatch.setattr(scfg, "AGENT_SAMPLE_QUERIES_ENABLED", False, raising=False)
    monkeypatch.setattr(scfg, "AGENT_ACCOUNT_INSIGHT_RECALL", False, raising=False)
    monkeypatch.setattr(agent_core, "_load_schema_list", lambda conn: "")
    monkeypatch.setattr(agent_core, "_load_relevant_table_insights", lambda conn, um: "")
    import modules.kb_glossary as kg
    import modules.kb_metadata as km
    import modules.relationships as rel
    monkeypatch.setattr(kg, "load_glossary_enum_context",
                        lambda um, conn=None, **k: seen.append(("glossary", conn)) or "")
    monkeypatch.setattr(km, "load_table_column_descriptions",
                        lambda um, conn=None, **k: seen.append(("tabcol", conn)) or "")
    monkeypatch.setattr(rel, "load_relationship_context",
                        lambda um, conn=None, **k: seen.append(("rel", conn)) or "")
    agent_core._build_knowledge_context(None, "질문", [], account_id=None, conversation_id=None)
    assert [x[0] for x in seen] == ["glossary", "tabcol", "rel"]
    shared_conn = seen[0][1]
    assert shared_conn is conns[0] and all(x[1] is shared_conn for x in seen)
    assert shared_conn.closed == 1, "공유 conn close 는 호출측 1회"
