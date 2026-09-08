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
                      edits=None, news=None, raise_on=None, skip_reasons=None, bound=None):
    """sys.modules 에 fake `web.app` 주입 — _postprocess_attachment_blocks 의 지연 import 대상."""
    calls: dict = {"edits": [], "new": [], "strip_edit": 0, "strip_new": 0, "update": [], "bind": []}
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

    def _mat_edits(c, *, account, conversation_id, answer, message_id, request, skipped=None):
        calls["edits"].append({"answer": answer, "message_id": message_id, "request": request,
                               "skipped_passed": skipped is not None})
        if raise_on == "edits":
            raise RuntimeError("boom-edits")
        # FR-failed-attachment-edit-silently-stripped: 저장 가드가 거부한 블록의 사유를
        # 호출측이 실제로 받아 쓰는지 재현한다.
        if skipped is not None:
            skipped.extend(list(skip_reasons or []))
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
        # 운영 계약은 **bool 반환**이다(영속 성공 여부). None 을 돌려주면 호출자가
        # `answer_persisted=False` 로 보고 result 사본 교체를 건너뛰어, 그 경로를 검사하는
        # 단언이 조용히 vacuous 해진다(codex P2, 2026-08-28).
        return True

    web_app._materialize_assistant_attachment_edits = _mat_edits
    web_app._materialize_assistant_attachment_new = _mat_new
    web_app._strip_attachment_edit_blocks = _strip_edit
    web_app._strip_attachment_new_blocks = _strip_new
    def _bind(c, *, conversation_id, account_id, attachment_ids, message_id):
        # codex R8 [P2]: 이 함수가 fake 에 **없으면** 후처리가 항상 예외 경로를 타서, 도구 전달분이
        # `edited` 에 실제로 합쳐지는 상황이 재현되지 않는다 — 그러면 `_block_edited_n` 을 되돌려도
        # 테스트가 통과한다(vacuous). 성공 경로를 재현한다.
        calls["bind"].append({"ids": list(attachment_ids), "message_id": message_id})
        return list(bound if bound is not None else [{"id": i} for i in attachment_ids])

    web_app._bind_tool_delivered_attachments = _bind
    web_app._update_assistant_message_content = _update

    # 후처리 시퀀스 자체는 **정본**(`shared/attachment_write.py`)이고, worker 는 그것을
    # `web.app` 을 통해 부른다(feature-0043 — 브리지 경로와 한 벌). fake 에 이름만 얹으면
    # 시퀀스가 가짜가 되므로, **진짜 함수에 위 stub 원시연산을 물려** 준다. 그래서 아래
    # 단언들은 여전히 실제 조립(순서·cap 합산·미전달 계수·strip 정책)을 검증한다.
    from shared.attachment_write import apply_assistant_attachment_blocks as _real_apply

    web_app._apply_assistant_attachment_blocks = (
        lambda c, **kw: _real_apply(c, ops=web_app, **kw))

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
    # 영속 성공 시 result 사본도 정리본으로 바뀐다. **초기값에 fence 가 없으므로**
    # "fence 없음" 만 보면 아무 일도 안 일어난 세계가 통과한다 — 치환 마커를 확인한다.
    assert result["answer"] != "stale-answer", "result 사본이 교체되지 않았다"
    assert "[STRIPPED-NEW]" in result["answer"]
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

    # fail-soft 의 뜻: **예외가 전파되지 않고 전달이 막히지 않는다**. 답변 문자열이 그대로
    # 남는다는 뜻은 아니다 — strip 은 materialize 성패와 무관하게 수행되므로(파일 전문이
    # 채팅에 쏟아지는 것을 막는 원 정책) 저장된 메시지는 정리본이 되고, result 사본도 그것을
    # 따라가야 ops view 와 어긋나지 않는다.
    assert "new_attachments" not in result
    assert "```attachment-new" not in result["answer"], "실패 경로에서 원문 블록이 남았다"
    assert "[STRIPPED-NEW]" in result["answer"]
    assert "첨부 전달 실패" in result["answer"], "만들지 못한 사실을 답변이 말하지 않는다"


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


# ── FR-failed-attachment-edit-silently-stripped (conversation_audit 2026-08-26) ──────────
#
# 저장 가드(소유권·kind·용량)가 거부한 `attachment-edit` 블록은 **사유 없이** 답변에서 제거돼
# 왔다. 본문에 이미 쓰인 "갱신했습니다" 문장은 남아, 사용자는 파일을 못 받았는데 성공으로 읽는다.
# materialize 는 이미 `skipped` 로 사람이 읽을 수 있는 사유를 돌려주는데 이 경로가 버리고 있었다.


def test_skipped_reasons_are_passed_and_surfaced(monkeypatch):
    """거부 사유를 받아 **답변에 명시**한다 — strip 은 유지하되 침묵하지 않는다."""
    calls, conn = _install_fake_web(
        monkeypatch,
        latest_content="파일을 갱신했습니다.\n```attachment-edit\n{\"source_attachment_id\": 9}\nx\n```",
        edits=[], skip_reasons=["attachment_id=9: 이 대화에서 당신이 갱신할 수 있는 첨부가 아닙니다."],
    )
    from modules.ask import _postprocess_attachment_blocks
    result = {"answer": "파일을 갱신했습니다."}
    _postprocess_attachment_blocks("conv-x", 10, result, "run-1")

    assert calls["edits"] and calls["edits"][0]["skipped_passed"] is True, "skipped 를 넘겨야 사유를 얻는다"
    saved = calls["update"][-1]["content"] if calls["update"] else result.get("answer", "")
    assert "첨부 전달 실패" in saved
    assert "갱신할 수 있는 첨부가 아닙니다" in saved
    assert "갱신했다는 서술이 있어도" in saved, "본문의 거짓 성공 주장을 정정해야 한다"


def test_no_note_when_nothing_was_skipped(monkeypatch):
    """정상 전달에는 경고 문단이 붙지 않는다(과잉 노이즈 0)."""
    calls, conn = _install_fake_web(
        monkeypatch,
        latest_content="갱신본입니다.\n```attachment-edit\n{\"source_attachment_id\": 9}\nx\n```",
        edits=[{"id": 1}], skip_reasons=[],
    )
    from modules.ask import _postprocess_attachment_blocks
    result = {"answer": "갱신본입니다."}
    _postprocess_attachment_blocks("conv-x", 10, result, "run-1")
    saved = calls["update"][-1]["content"] if calls["update"] else result.get("answer", "")
    assert "첨부 전달 실패" not in saved


def test_undelivered_blocks_without_reason_are_still_surfaced(monkeypatch):
    """§18.8 codex 라운드 6 [P1] — `skipped` 에 안 남는 실패도 거짓 성공으로 끝나면 안 된다.

    materialize 는 저장 가드 거부만 `skipped` 로 남긴다. 파싱 실패(malformed header)·개수 캡 초과·
    storage import 실패는 기록 없이 사라지는데 strip 은 fence 를 **전부** 지운다. 그래서 사유 장부를
    믿지 않고 **결과를 직접 센다** — 블록 수 대비 실제 생성 수.
    """
    body = ("두 파일 모두 갱신했습니다.\n"
            "```attachment-edit\n{\"source_attachment_id\": 1}\na\n```\n"
            "```attachment-edit\n{\"source_attachment_id\": 2}\nb\n```")
    calls, conn = _install_fake_web(
        monkeypatch, latest_content=body,
        edits=[{"id": 11}],          # 2개 블록 중 1개만 생성 — 나머지는 사유 없이 사라짐
        skip_reasons=[],
    )
    from modules.ask import _postprocess_attachment_blocks
    result = {"answer": body}
    _postprocess_attachment_blocks("conv-x", 10, result, "run-1")
    saved = calls["update"][-1]["content"] if calls["update"] else result.get("answer", "")
    assert "첨부 전달 실패" in saved
    assert "사유 미상 1건" in saved
    assert "갱신했다는 서술이 있어도" in saved


def test_undelivered_attachment_new_blocks_are_surfaced(monkeypatch):
    """`attachment-new` 축도 같은 방식으로 덮인다(편집 경로 전용 장부에 의존하지 않는다)."""
    body = "파일을 만들었습니다.\n```attachment-new\n{\"filename\": \"a.sql\"}\nx\n```"
    calls, conn = _install_fake_web(monkeypatch, latest_content=body, news=[], skip_reasons=[])
    from modules.ask import _postprocess_attachment_blocks
    result = {"answer": body}
    _postprocess_attachment_blocks("conv-x", 10, result, "run-1")
    saved = calls["update"][-1]["content"] if calls["update"] else result.get("answer", "")
    assert "첨부 전달 실패" in saved and "사유 미상 1건" in saved


def test_quoted_fence_example_does_not_trigger_false_failure(monkeypatch):
    """거짓 양성 축 ① — 답변이 **예시로 인용한** fence 는 블록이 아니다.

    단순 substring 카운트면 정상 전달에도 "첨부 전달 실패" 가 붙는다(사용자를 헷갈리게 하는
    오정보). 줄머리 fence 만 센다.
    """
    body = ("형식은 다음과 같습니다:\n"
            "    ```attachment-edit\n"
            "    {\"source_attachment_id\": 1}\n"
            "    ```\n"
            "실제 전달은 도구로 했습니다.")
    calls, conn = _install_fake_web(monkeypatch, latest_content=body,
                                    edits=[], news=[], skip_reasons=[])
    from modules.ask import _postprocess_attachment_blocks
    result = {"answer": body}
    _postprocess_attachment_blocks("conv-x", 10, result, "run-1")
    saved = calls["update"][-1]["content"] if calls["update"] else result.get("answer", "")
    assert "첨부 전달 실패" not in saved


def test_failed_run_does_not_add_delivery_failure_note(monkeypatch):
    """거짓 양성 축 ② — 실패/취소 run 은 materialize 를 건너뛰도록 설계돼 있고 오류가 이미 표면화된다."""
    body = "갱신했습니다.\n```attachment-edit\n{\"source_attachment_id\": 1}\na\n```"
    calls, conn = _install_fake_web(monkeypatch, latest_content=body, edits=[], skip_reasons=[])
    from modules.ask import _postprocess_attachment_blocks
    result = {"answer": body, "error": "cancelled"}
    _postprocess_attachment_blocks("conv-x", 10, result, "run-1")
    saved = calls["update"][-1]["content"] if calls["update"] else result.get("answer", "")
    assert "첨부 전달 실패" not in saved
    # codex R7 [P2]: 경고 부재만 보면 취소 경로 회귀를 못 잡는다 — 설계 계약 전부를 단언한다.
    assert calls["edits"] == [] and calls["new"] == [], "실패 run 은 materialize 를 건너뛴다"
    assert "```attachment-edit" not in saved, "실패 run 이라도 strip 은 수행한다(본문 노출 방지)"


def test_tool_delivery_does_not_mask_a_failed_block(monkeypatch):
    """codex R7 [P1] — 도구 전달분이 블록 실패를 **상쇄**하면 안 된다.

    `edited` 에는 도구 전달분이 합쳐진다. 그 합본으로 fence 대비 미전달을 계산하면
    "도구로 1건 전달 + 블록 1건 실패" 가 0 으로 상쇄돼 경고가 사라진다.
    """
    body = "갱신했습니다.\n```attachment-edit\n{\"source_attachment_id\": 1}\na\n```"
    calls, conn = _install_fake_web(monkeypatch, latest_content=body,
                                    edits=[], skip_reasons=[])   # 블록 경로는 0건 생성
    from modules.ask import _postprocess_attachment_blocks
    # 도구로 1건 전달됨 → _bind_tool_delivered_attachments 가 1건을 돌려준다
    result = {"answer": body, "tool_delivered_attachment_ids": [55]}
    _postprocess_attachment_blocks("conv-x", 10, result, "run-1")
    assert calls["bind"] and calls["bind"][0]["ids"] == [55], "도구 전달분이 실제로 합쳐지는 경로여야 함"
    saved = calls["update"][-1]["content"] if calls["update"] else result.get("answer", "")
    assert "첨부 전달 실패" in saved, "도구 전달분이 블록 실패를 가리면 안 된다"
    assert "사유 미상 1건" in saved


def test_fence_inside_outer_markdown_fence_is_not_counted(monkeypatch):
    """codex R7 [P2] — 바깥 fence 안에서 **열 0** 으로 인용한 fence 도 블록이 아니다."""
    body = ("형식 예시:\n"
            "```markdown\n"
            "```attachment-edit\n"
            "{\"source_attachment_id\": 1}\n"
            "```\n"
            "```\n"
            "실제 전달은 없었습니다.")
    calls, conn = _install_fake_web(monkeypatch, latest_content=body,
                                    edits=[], news=[], skip_reasons=[])
    from modules.ask import _postprocess_attachment_blocks
    result = {"answer": body}
    _postprocess_attachment_blocks("conv-x", 10, result, "run-1")
    saved = calls["update"][-1]["content"] if calls["update"] else result.get("answer", "")
    assert "첨부 전달 실패" not in saved


def test_tilde_and_wide_fences_are_tracked(monkeypatch):
    """codex R8 [P2] C — `~~~` 과 4-backtick fence 안의 인용도 블록이 아니다."""
    body = ("~~~markdown\n```attachment-edit\n{\"source_attachment_id\": 1}\n```\n~~~\n"
            "````text\n```attachment-new\n{\"filename\": \"a.sql\"}\n```\n````\n실제 전달 없음.")
    calls, conn = _install_fake_web(monkeypatch, latest_content=body,
                                    edits=[], news=[], skip_reasons=[])
    from modules.ask import _postprocess_attachment_blocks
    result = {"answer": body}
    _postprocess_attachment_blocks("conv-x", 10, result, "run-1")
    saved = calls["update"][-1]["content"] if calls["update"] else result.get("answer", "")
    assert "첨부 전달 실패" not in saved


def test_successful_file_only_result_preserves_empty_answer(monkeypatch):
    import modules.ask as ask
    raw = '```attachment-new\n{"filename":"x.sql"}\nSELECT 1;\n```'
    _install_fake_web(monkeypatch, latest_content=raw)
    fake = sys.modules['web.app']
    fake._apply_assistant_attachment_blocks = lambda *a, **kw: {
        'answer': '', 'answer_persisted': True, 'created': [{'id': 1}], 'edited': [],
    }
    result = {'answer': raw, 'conversation_id': 'conv-1'}
    ask._postprocess_attachment_blocks('conv-1', 42, result)
    assert result['answer'] == ''
    assert result['new_attachments'] == [{'id': 1}]
