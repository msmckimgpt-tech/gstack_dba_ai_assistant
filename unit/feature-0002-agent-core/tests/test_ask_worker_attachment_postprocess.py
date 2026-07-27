"""FR-brandnew-script-attachment-delivery-gap 후속(conversation_audit 2026-07-27):
ask-worker 가 답변의 attachment-edit/new 블록을 **직접** materialize + strip 하는 회귀 테스트.

라이브 결함: 첨부 후처리가 web `/api/ask` 동기 핸들러에만 있어, worker 모드 장기 run(관측 11분)
중 클라이언트/프록시 연결이 끊기면 web 이 후처리 지점에 도달하지 못해 **첨부 미생성 + raw 블록이
답변에 그대로 노출**됐다(대화 …f1c535ec msg 1389: attachment-new 블록 emit 됐으나 첨부 0건,
시스템 전체 assistant root 첨부 0건). 답변 완료 시점을 아는 worker 가 후처리를 소유하도록 이전.

검증(DB·MinIO 없이 fake web.app 주입):
  W1  블록 있는 답변 → edits/new materialize 호출 + strip 적용 + 메시지 content 갱신 + result 주입.
  W2  블록 없는 답변 → materialize 미호출(조기 반환, 흔한 경로 비용 0).
  W3  error 있는 result → 후처리 skip(web 경로와 동일 조건).
  W4  materialize 예외 → fail-soft(예외 전파 없음, answer 보존).
  W5  개수 cap 합산 — new 는 remaining_count=CAP-len(edits) 로 호출.
  W6  account 미해소 → skip(권한/소유 불명 상태로 첨부 만들지 않음).
  W7  **순서 계약**: _execute_job 이 finish_ask_job(terminal) **전에** 후처리를 호출한다.
      (terminal 후면 web long-poll 이 raw 블록을 먼저 읽어 노출된다 — 결함 재현 조건.)
  W8  _slim_result 가 첨부 키를 result_json 으로 보존(web 응답 패리티).
"""
from __future__ import annotations

import sys
import types


CAP = 5


class _FakeConn:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _install_fake_web(monkeypatch, *, latest_content, latest_id=77, account=None,
                      edits=None, news=None, raise_on=None):
    """sys.modules 에 fake `web.app` 주입 — _postprocess_attachment_blocks 의 지연 import 대상."""
    calls: dict = {"edits": [], "new": [], "strip_edit": 0, "strip_new": 0, "update": []}
    conn = _FakeConn()

    web_app = types.ModuleType("web.app")
    web_app._ASSISTANT_EDIT_COUNT_CAP = CAP
    web_app._connect_memory = lambda: conn
    web_app._load_account_by_id = lambda c, aid: (
        account if account is not None else {"id": int(aid), "role": {"key": "operator"}}
    )
    web_app._load_latest_assistant_message = lambda c, cid: (
        {"id": latest_id, "content": latest_content}
    )

    def _mat_edits(c, *, account, conversation_id, answer, message_id, request):
        calls["edits"].append({"answer": answer, "message_id": message_id, "request": request})
        if raise_on == "edits":
            raise RuntimeError("boom-edits")
        return list(edits or [])

    def _mat_new(c, *, account, conversation_id, answer, message_id, request, remaining_count):
        calls["new"].append({"answer": answer, "message_id": message_id,
                             "request": request, "remaining_count": remaining_count})
        if raise_on == "new":
            raise RuntimeError("boom-new")
        return list(news or [])

    def _strip_edit(answer, mat):
        calls["strip_edit"] += 1
        return answer.replace("```attachment-edit", "[STRIPPED-EDIT]")

    def _strip_new(answer, mat):
        calls["strip_new"] += 1
        return answer.replace("```attachment-new", "[STRIPPED-NEW]")

    def _update(c, cid, mid, content):
        calls["update"].append({"cid": cid, "mid": mid, "content": content})

    web_app._materialize_assistant_attachment_edits = _mat_edits
    web_app._materialize_assistant_attachment_new = _mat_new
    web_app._strip_attachment_edit_blocks = _strip_edit
    web_app._strip_attachment_new_blocks = _strip_new
    web_app._update_assistant_message_content = _update

    web_pkg = types.ModuleType("web")
    web_pkg.__path__ = []
    web_pkg.app = web_app
    monkeypatch.setitem(sys.modules, "web", web_pkg)
    monkeypatch.setitem(sys.modules, "web.app", web_app)
    return calls, conn


_NEW_BLOCK_ANSWER = (
    "개선안입니다.\n\n"
    '```attachment-new\n{"filename": "improve.sql"}\nSELECT 1;\n```\n\n'
    "## 배포 전 확인\n- 스테이징 검증 필요\n"
)


def test_w1_materializes_and_strips(monkeypatch):
    import modules.ask as ask
    created = [{"id": 900, "original_filename": "improve.sql", "version_number": 1}]
    calls, conn = _install_fake_web(monkeypatch, latest_content=_NEW_BLOCK_ANSWER, news=created)
    result = {"answer": "stale-answer", "conversation_id": "conv-1"}

    ask._postprocess_attachment_blocks("conv-1", 42, result)

    assert len(calls["edits"]) == 1 and len(calls["new"]) == 1
    # materialize 는 **저장된 raw content**(블록 포함)를 대상으로 한다 — result.answer 가 아님.
    assert "```attachment-new" in calls["new"][0]["answer"]
    assert calls["new"][0]["message_id"] == 77
    assert calls["new"][0]["request"] is None      # worker 에는 HTTP 요청 컨텍스트 없음
    # strip 후 content 갱신 + result 반영
    assert calls["strip_edit"] == 1 and calls["strip_new"] == 1
    assert len(calls["update"]) == 1
    assert "[STRIPPED-NEW]" in calls["update"][0]["content"]
    assert "```attachment-new" not in result["answer"]
    assert result["new_attachments"] == created
    assert conn.closed is True                      # 커넥션 누수 없음


def test_w2_no_blocks_skips_materialize(monkeypatch):
    import modules.ask as ask
    calls, conn = _install_fake_web(monkeypatch, latest_content="블록 없는 일반 답변입니다.")
    result = {"answer": "x", "conversation_id": "conv-1"}

    ask._postprocess_attachment_blocks("conv-1", 42, result)

    assert calls["edits"] == [] and calls["new"] == []   # 조기 반환
    assert calls["update"] == []
    assert "new_attachments" not in result


def test_w3_error_result_skips_materialize_but_still_strips(monkeypatch):
    """실패/취소 run: 첨부 생성은 skip 하되 **strip 은 수행**(§18.8 MINOR — 본문 노출 방지 정책).

    취소 시 부분 답변(preserve_reasoning)에 블록이 실려 저장될 수 있는데, web strip 이 worker
    모드에서 게이팅됐으므로 워커가 이 책임을 진다.
    """
    import modules.ask as ask
    calls, _ = _install_fake_web(monkeypatch, latest_content=_NEW_BLOCK_ANSWER)
    result = {"answer": "", "conversation_id": "conv-1", "error": "실행 중 오류"}

    ask._postprocess_attachment_blocks("conv-1", 42, result)

    assert calls["edits"] == [] and calls["new"] == []     # 첨부 생성은 안 함
    assert calls["strip_new"] == 1                          # 그러나 strip 은 수행
    assert len(calls["update"]) == 1                        # 저장 메시지에서 블록 제거
    assert "```attachment-new" not in calls["update"][0]["content"]


def test_w4_materialize_exception_is_fail_soft(monkeypatch):
    import modules.ask as ask
    _install_fake_web(monkeypatch, latest_content=_NEW_BLOCK_ANSWER, raise_on="new")
    result = {"answer": "orig", "conversation_id": "conv-1"}

    ask._postprocess_attachment_blocks("conv-1", 42, result)   # 예외 전파 없어야 함

    assert result["answer"] == "orig"        # 답변 보존(전달 차단 없음)
    assert "new_attachments" not in result


def test_w5_shared_count_cap(monkeypatch):
    import modules.ask as ask
    edits = [{"id": i} for i in range(3)]
    calls, _ = _install_fake_web(monkeypatch, latest_content=_NEW_BLOCK_ANSWER, edits=edits)
    ask._postprocess_attachment_blocks("conv-1", 42, {"answer": "", "conversation_id": "conv-1"})
    assert calls["new"][0]["remaining_count"] == CAP - 3      # 편집과 합산


def test_w6_unresolved_account_skips(monkeypatch):
    import modules.ask as ask
    calls, _ = _install_fake_web(monkeypatch, latest_content=_NEW_BLOCK_ANSWER, account={})
    ask._postprocess_attachment_blocks("conv-1", 0, {"answer": "", "conversation_id": "conv-1"})
    assert calls["edits"] == [] and calls["new"] == []


def test_w7_postprocess_runs_before_terminal_transition(monkeypatch):
    """순서 계약: 후처리 → finish_ask_job(terminal). 역순이면 web long-poll 이 raw 블록을 먼저 읽는다."""
    import modules.ask as ask
    order: list[str] = []

    monkeypatch.setattr(ask, "_postprocess_attachment_blocks",
                        lambda cid, aid, result, run_id="": order.append("postprocess"))
    monkeypatch.setattr(ask.ask_jobs, "set_job_run_id", lambda *a, **k: None)
    monkeypatch.setattr(ask.ask_jobs, "finish_ask_job",
                        lambda *a, **k: (order.append("finish"), True)[1])
    monkeypatch.setattr(ask, "_cleanup_inline_paths", lambda payload: None)
    monkeypatch.setattr(ask, "_heartbeat_loop", lambda *a, **k: None)

    fake_agent = types.ModuleType("agent_core")
    fake_agent.run_agent = lambda **kw: {"answer": "ok", "conversation_id": "conv-1"}
    fake_agent._new_run_id = lambda: "run-1"
    monkeypatch.setitem(sys.modules, "agent_core", fake_agent)

    ask._execute_job(None, {"id": 1, "conversation_id": "conv-1", "lease_epoch": 1,
                            "account_id": 42, "payload": {}, "created_at": None})

    assert order == ["postprocess", "finish"], f"terminal 전 후처리여야 함: {order}"


def test_w9_kv_terminal_written_after_postprocess(monkeypatch):
    """§18.8 BLOCKER: KV terminal(done)은 후처리 **뒤**에 찍혀야 한다.

    web long-poll(/api/ask·/api/ask_result)과 프런트 재조회는 ask_jobs terminal 이 아니라 KV
    last_status 를 보고 저장 메시지를 읽는다. run_agent 가 done 을 미리 찍으면(기존 동작) 후처리
    전 raw 블록이 노출된다 — 이 결함의 재발 방지 계약.
    """
    import modules.ask as ask
    order: list[str] = []

    monkeypatch.setattr(ask, "_postprocess_attachment_blocks",
                        lambda cid, aid, result, run_id="": order.append("postprocess"))
    monkeypatch.setattr(ask, "set_run_status",
                        lambda *a, **k: order.append(f"kv:{a[2] if len(a) > 2 else ''}"))
    monkeypatch.setattr(ask.ask_jobs, "set_job_run_id", lambda *a, **k: None)
    monkeypatch.setattr(ask.ask_jobs, "finish_ask_job",
                        lambda *a, **k: (order.append("job-terminal"), True)[1])
    monkeypatch.setattr(ask, "_cleanup_inline_paths", lambda payload: None)
    monkeypatch.setattr(ask, "_heartbeat_loop", lambda *a, **k: None)

    fake_agent = types.ModuleType("agent_core")
    # defer_terminal_status=True 를 받은 run_agent 는 done 을 찍지 않고 인자를 넘긴다.
    fake_agent.run_agent = lambda **kw: (
        {"answer": "ok", "conversation_id": "conv-1",
         "_deferred_terminal": {"run_id": kw.get("run_id"), "duration_ms": 12}}
        if kw.get("defer_terminal_status") else
        {"answer": "ok", "conversation_id": "conv-1"}
    )
    fake_agent._new_run_id = lambda: "run-1"
    monkeypatch.setitem(sys.modules, "agent_core", fake_agent)

    ask._execute_job(None, {"id": 1, "conversation_id": "conv-1", "lease_epoch": 1,
                            "account_id": 42, "payload": {}, "created_at": None})

    assert order == ["postprocess", "kv:done", "job-terminal"], f"순서 위반: {order}"


def test_w10_worker_requests_deferred_terminal():
    """worker payload→kwargs 가 defer_terminal_status=True 를 요청한다(계약의 발동 조건)."""
    import modules.ask as ask
    kw = ask._payload_to_kwargs({"user_message": "q"}, account_id=1, run_id="r1")
    assert kw["defer_terminal_status"] is True


def test_w11_deferred_terminal_written_even_if_postprocess_raises(monkeypatch):
    """후처리가 예외로 죽어도 KV done 은 반드시 찍힌다(프런트 무한 '처리중' 방지)."""
    import modules.ask as ask
    written: list = []

    def _boom(cid, aid, result, run_id=""):
        raise RuntimeError("postprocess exploded")

    monkeypatch.setattr(ask, "_postprocess_attachment_blocks", _boom)
    monkeypatch.setattr(ask, "set_run_status", lambda *a, **k: written.append(a[2]))
    monkeypatch.setattr(ask.ask_jobs, "set_job_run_id", lambda *a, **k: None)
    monkeypatch.setattr(ask.ask_jobs, "finish_ask_job", lambda *a, **k: True)
    monkeypatch.setattr(ask, "_cleanup_inline_paths", lambda payload: None)
    monkeypatch.setattr(ask, "_heartbeat_loop", lambda *a, **k: None)

    fake_agent = types.ModuleType("agent_core")
    fake_agent.run_agent = lambda **kw: {"answer": "ok", "conversation_id": "conv-1",
                                         "_deferred_terminal": {"run_id": "run-1", "duration_ms": 5}}
    fake_agent._new_run_id = lambda: "run-1"
    monkeypatch.setitem(sys.modules, "agent_core", fake_agent)

    try:
        ask._execute_job(None, {"id": 1, "conversation_id": "conv-1", "lease_epoch": 1,
                                "account_id": 42, "payload": {}, "created_at": None})
    except RuntimeError:
        pass   # 후처리 예외가 새어나오더라도 아래 KV 기록은 이미 보장돼야 함
    assert written == ["done"], f"지연 terminal 미기록: {written}"


def test_w12_finalize_pops_marker_and_skips_on_error():
    """_deferred_terminal 은 기록 후 결과에서 제거(result_json 오염 방지) + error 면 미기록."""
    import modules.ask as ask
    calls: list = []
    orig = ask.set_run_status
    try:
        ask.set_run_status = lambda *a, **k: calls.append(a[2])
        r1 = {"_deferred_terminal": {"run_id": "r", "duration_ms": 1}}
        ask._finalize_deferred_terminal("c", "r", r1)
        assert "_deferred_terminal" not in r1 and calls == ["done"]

        calls.clear()
        r2 = {"error": "실패", "_deferred_terminal": {"run_id": "r"}}
        ask._finalize_deferred_terminal("c", "r", r2)
        # §18.8 LOW: 마커만 버리면 KV 가 processing 에 고착 → error 로라도 반드시 terminal 기록.
        assert calls == ["error"]
        assert "_deferred_terminal" not in r2
    finally:
        ask.set_run_status = orig


def test_w8_slim_result_keeps_attachment_keys():
    import modules.ask as ask
    slim = ask._slim_result({
        "answer": "a", "conversation_id": "c", "error": "",
        "edited_attachments": [{"id": 1}], "new_attachments": [{"id": 2}],
        "dropped_field": "x",
    })
    assert slim["edited_attachments"] == [{"id": 1}]
    assert slim["new_attachments"] == [{"id": 2}]
    assert "dropped_field" not in slim
