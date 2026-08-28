"""FR-attach-delivery-truncated-by-output-cap — 첨부 전달의 구조 개선 회귀 테스트.

관측(conversation_audit 2026-08-06, 대화 `…1d8ed346`): 답변이 "6개 파일을 전부 갱신했습니다" 라고
했는데 실제 생성된 새 버전은 **1건**이었다. `completion_tokens = 100,000`(출력 상한 정확히 도달) —
모델이 요약을 먼저 쓰고 파일 전문 6개를 이어 붙이다 상한에서 잘렸고, 완성된 `attachment-edit`
블록은 첫 파일 하나뿐이었다. 서두의 "전부 갱신" 은 잘리기 **전**에 쓰여 그대로 남았다.

근본은 "절단을 감지하지 못한 것"이 아니라 **전달 payload 가 답변의 출력 예산을 공유하는 구조**다.
파일이 늘면 서로를 밀어낸다. 그래서 봉인은 3층이다:
  ① `update_attachment` 도구 — 파일마다 **독립 턴의 출력 창** + 성공/실패 즉시 반환(L2 자기교정)
  ② `patch`(unified diff) 전달 — 전문 재작성 대비 토큰 급감(이번 건의 실제 변경은 몇 줄이었다)
  ③ `finish_reason` 절단 감지 — 도구 인자 자체도 잘릴 수 있으므로 구조 개선과 무관하게 필요

이 파일은 ①③과 그 경계(권한·상한·실패 사유)를 고정한다. ②의 적용 규칙은 `test_patch_apply.py`.
"""
from __future__ import annotations

import agent_core
import modules.tools as tools

_ROWS = [
    {"id": 31, "filename": "a.sql", "kind": "text", "object_key": "k/31",
     "status": "uploaded", "meta_json": None},
    {"id": 32, "filename": "b.sql", "kind": "text", "object_key": "k/32",
     "status": "uploaded", "meta_json": None},
]
_SRC = b"USE Log_v2;\nSELECT 1;\n"


class _FakeWeb:
    """web.app 대역 — materialize 를 호출했는지/무엇으로 호출했는지 관측한다."""

    def __init__(self, *, created=None, skip_reason=None, account=True):
        self.calls: list[dict] = []
        self._created = created
        self._skip = skip_reason
        self._account = account

    def _connect_memory(self):
        class _C:
            def close(self_inner):
                pass
        return _C()

    def _load_account_by_id(self, conn, aid):
        return {"id": aid} if self._account else None

    def _materialize_assistant_attachment_edits(self, conn, *, account, conversation_id,
                                                blocks=None, skipped=None, request=None, **kw):
        self.calls.append({"account": account, "conversation_id": conversation_id,
                           "blocks": blocks})
        if self._skip is not None and skipped is not None:
            skipped.append(self._skip)
            return []
        if self._created is not None:
            return self._created
        blk = (blocks or [{}])[0]
        return [{"id": 900, "original_filename": "a_v2.sql", "version_number": 2,
                 "content_len": len(blk.get("content") or "")}]


def _setup(monkeypatch, *, web=None, body=_SRC, account_id=7, conv="conv-x"):
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: list(_ROWS))
    monkeypatch.setattr(agent_core, "_load_attachment_bytes", lambda k: body)
    agent_core._ACTIVE_ACCOUNT_ID_CTX.set(account_id)
    agent_core._ATTACHMENT_UPDATES_DONE_CTX.set(0)
    import shared.config as cfg
    cfg.set_active_conversation_id(conv)
    w = web or _FakeWeb()
    import sys
    monkeypatch.setitem(sys.modules, "web.app", w)
    monkeypatch.setitem(sys.modules, "web", type(sys)("web"))
    sys.modules["web"].app = w
    return w


# ── ① 도구 경로: 성공과 그 되먹임 ───────────────────────────────────────────


def test_content_delivery_succeeds_and_reports_back(monkeypatch):
    """성공 응답에 **새 버전 번호와 누적 전달 건수**가 담긴다 — 모델이 그것만 근거로 주장한다."""
    w = _setup(monkeypatch)
    out = tools._tool_update_attachment(None, {"filename": "a.sql", "content": "NEW BODY"})
    assert "전달 완료" in out and "a_v2.sql" in out and "v2" in out
    assert "지금까지 전달한 파일: 1건" in out
    assert "전달 완료 응답을 받은 파일만" in out
    assert w.calls[0]["blocks"][0]["source_attachment_id"] == 31
    assert w.calls[0]["blocks"][0]["content"] == "NEW BODY"


def test_patch_delivery_applies_to_current_body(monkeypatch):
    """patch 경로는 **현재 원본**에 적용한 결과를 materialize 로 넘긴다(전문 재작성 불필요)."""
    w = _setup(monkeypatch)
    out = tools._tool_update_attachment(None, {
        "filename": "a.sql", "patch": "@@ -1,1 +1,1 @@\n-USE Log_v2;\n+USE log_v2;"})
    assert "전달 완료" in out
    assert w.calls[0]["blocks"][0]["content"].startswith("USE log_v2;")


def test_delivery_counter_increments_across_calls(monkeypatch):
    _setup(monkeypatch)
    tools._tool_update_attachment(None, {"filename": "a.sql", "content": "X"})
    out2 = tools._tool_update_attachment(None, {"filename": "b.sql", "content": "Y"})
    assert "지금까지 전달한 파일: 2건" in out2
    assert int(agent_core._ATTACHMENT_UPDATES_DONE_CTX.get()) == 2


def test_counter_not_incremented_on_failure(monkeypatch):
    """실패는 세지 않는다 — 세면 리뷰어에게 넘기는 delivered 사실 자체가 거짓이 된다."""
    _setup(monkeypatch, web=_FakeWeb(skip_reason="attachment_id=31: 삭제된 첨부입니다."))
    tools._tool_update_attachment(None, {"filename": "a.sql", "content": "X"})
    assert int(agent_core._ATTACHMENT_UPDATES_DONE_CTX.get()) == 0


# ── ① 실패는 반드시 "전달 안 됨" 을 명시 ────────────────────────────────────


def test_failure_result_forbids_claiming_delivery(monkeypatch):
    """모델이 실패를 성공으로 오인하면 이 마찰이 그대로 재발한다."""
    _setup(monkeypatch, web=_FakeWeb(skip_reason="attachment_id=31: kind=xlsx 는 갱신할 수 없습니다."))
    out = tools._tool_update_attachment(None, {"filename": "a.sql", "content": "X"})
    assert out.startswith("오류:")
    assert "kind=xlsx" in out, "materialize 의 skip 사유가 그대로 모델에게 전달되어야 한다"
    assert "이 파일은 전달되지 않았습니다" in out
    assert "갱신했다고 말하지 마십시오" in out


def test_patch_failure_offers_content_fallback(monkeypatch):
    _setup(monkeypatch)
    out = tools._tool_update_attachment(None, {
        "filename": "a.sql", "patch": "@@ -1,1 +1,1 @@\n-NOT PRESENT;\n+x;"})
    assert out.startswith("오류:") and "content 로 전문을 보내도" in out


def test_noop_patch_is_rejected(monkeypatch):
    """내용이 안 바뀌는 패치로 버전을 올리면 '갱신했다' 가 사실상 거짓이 된다."""
    _setup(monkeypatch)
    res = agent_core.update_attachment_content(
        filename="a.sql", patch="@@ -1,1 +1,1 @@\n-USE Log_v2;\n+USE Log_v2;")
    assert res["ok"] is False and "바뀌지 않습니다" in res["error"]


# ── ① 권한·인자 경계 ────────────────────────────────────────────────────────


def test_rejects_id_outside_scope(monkeypatch):
    """스코프(= web ask 가 해소한 집합) 밖 id 는 이름을 알아도 갱신 불가."""
    _setup(monkeypatch)
    res = agent_core.update_attachment_content(attachment_id=999, content="X")
    assert res["ok"] is False and "갱신할 수 있는 첨부가 아닙니다" in res["error"]


def test_requires_account_context(monkeypatch):
    """계정 컨텍스트가 없으면 fail-closed — 소유권 가드가 AccountId 기준이다."""
    _setup(monkeypatch, account_id=0)
    res = agent_core.update_attachment_content(filename="a.sql", content="X")
    assert res["ok"] is False and "요청 계정" in res["error"]


def test_requires_conversation_context(monkeypatch):
    _setup(monkeypatch, conv="")
    res = agent_core.update_attachment_content(filename="a.sql", content="X")
    assert res["ok"] is False and "대화 컨텍스트" in res["error"]


def test_rejects_both_patch_and_content(monkeypatch):
    _setup(monkeypatch)
    res = agent_core.update_attachment_content(filename="a.sql", patch="@@ -1 +1 @@\n-a\n+b", content="X")
    assert res["ok"] is False and "동시에 지정할 수 없습니다" in res["error"]


def test_rejects_neither_patch_nor_content(monkeypatch):
    _setup(monkeypatch)
    res = agent_core.update_attachment_content(filename="a.sql")
    assert res["ok"] is False and "하나를 반드시 지정" in res["error"]


def test_ambiguous_partial_filename_is_rejected(monkeypatch):
    """부분 일치가 여럿이면 엉뚱한 파일을 갱신할 수 있다 — 추측 금지."""
    monkeypatch.setattr(agent_core, "_load_scoped_attachment_rows", lambda: [
        {"id": 1, "filename": "x_01.sql", "kind": "text", "object_key": "k", "status": "uploaded"},
        {"id": 2, "filename": "x_02.sql", "kind": "text", "object_key": "k", "status": "uploaded"},
    ])
    agent_core._ACTIVE_ACCOUNT_ID_CTX.set(7)
    res = agent_core.update_attachment_content(filename="x_0", content="X")
    assert res["ok"] is False and "여러 첨부와 부분 일치" in res["error"]


def test_run_cap_stops_runaway(monkeypatch):
    _setup(monkeypatch)
    agent_core._ATTACHMENT_UPDATES_DONE_CTX.set(agent_core._ATTACHMENT_UPDATE_RUN_CAP)
    res = agent_core.update_attachment_content(filename="a.sql", content="X")
    assert res["ok"] is False and "상한" in res["error"]
    assert "다음 턴에 이어서" in res["error"], "막다른 길이 아니라 회복 경로를 줘야 한다"


def test_size_cap_enforced(monkeypatch):
    _setup(monkeypatch)
    res = agent_core.update_attachment_content(
        filename="a.sql", content="X" * (agent_core._ATTACHMENT_UPDATE_SIZE_CAP + 1))
    assert res["ok"] is False and "상한" in res["error"]


# ── 도구 정의 ───────────────────────────────────────────────────────────────


def test_tool_def_present_and_gated():
    defs = [d for d in tools._ATTACHMENT_TOOL_DEFS if d["function"]["name"] == "update_attachment"]
    assert len(defs) == 1
    desc = defs[0]["function"]["description"]
    assert "파일마다 한 번씩 호출" in desc
    assert "patch" in desc and "권장" in desc
    assert "성공 응답을 받은 파일만" in desc, "성공 확인 없이 주장하지 말라는 계약이 핵심"
    # 첨부가 없는 대화에는 노출되지 않는다(기존 게이트 공유).
    base = [{"type": "function", "function": {"name": "execute_sql"}}]
    assert all(d["function"]["name"] != "update_attachment"
               for d in tools.with_attachment_tools(base, False))
    assert any(d["function"]["name"] == "update_attachment"
               for d in tools.with_attachment_tools(base, True))


def test_tool_is_datasource_free():
    """데이터소스 연결 없이 동작해야 한다 — 첨부 갱신은 데이터소스와 무관하다."""
    assert "update_attachment" in tools._DATASOURCE_FREE_TOOLS


# ── ③ 절단 감지 ─────────────────────────────────────────────────────────────


def test_truncation_flag_reads_finish_reason():
    agent_core._LLM_LAST_FINISH_REASON_CTX.set("length")
    assert agent_core.last_answer_was_truncated() is True
    agent_core._LLM_LAST_FINISH_REASON_CTX.set("stop")
    assert agent_core.last_answer_was_truncated() is False
    agent_core._LLM_LAST_FINISH_REASON_CTX.set(None)
    assert agent_core.last_answer_was_truncated() is False


def test_truncation_notice_text_is_actionable():
    """경고는 (a) 잘렸다는 사실 (b) 파일 누락 가능성 (c) 칩이 정본 (d) 회복 방법을 담아야 한다."""
    n = agent_core._TRUNCATED_ANSWER_NOTICE
    assert "출력 한도" in n and "잘렸습니다" in n
    assert "누락" in n
    assert "다운로드 칩" in n and "칩이 정확" in n
    assert "계속" in n


# ── 프롬프트 계약 ───────────────────────────────────────────────────────────


def test_delivery_directive_prefers_tool_and_forbids_unverified_claims():
    d = agent_core._ATTACHMENT_DELIVERY_DIRECTIVE
    assert "update_attachment" in d and "one call per file" in d
    assert "NEVER claim a file was updated unless you received a success result" in d
    assert "summary LAST" in d, "요약을 먼저 쓰면 절단 시 허위 완료 선언이 남는다"
    # 블록 경로는 폴백으로 남아 있어야 한다(도구 미노출 대화 무회귀).
    assert "attachment-edit" in d


# ── red-team: 허위 완료 선언 대조 ───────────────────────────────────────────


def test_redteam_delivery_facts_block():
    from modules import redteam
    out = redteam.build_delivery_facts({"delivered": 1, "truncated": True})
    assert "DELIVERY FACTS" in out
    assert "update_attachment tool so far: 1" in out
    assert "CUT OFF at the output limit" in out


def test_redteam_delivery_facts_silent_when_nothing_to_judge():
    """전달도 절단도 없으면 판정 축이 없다 — 빈 블록은 오탐만 만든다."""
    from modules import redteam
    assert redteam.build_delivery_facts({"delivered": 0, "truncated": False}) == ""
    assert redteam.build_delivery_facts(None) == ""


def test_redteam_prompt_has_false_completion_rule():
    from modules import redteam
    p = redteam.REDTEAM_REVIEW_PROMPT
    assert "DELIVERY FACTS" in p
    assert "BLOCK on `honesty`" in p
    # 이번 마찰의 정확한 형태를 규칙에 박아 둔다.
    assert "모두 갱신했습니다" in p
    # 오탐 가드: 리뷰/제안만 한 파일을 전달로 세지 않는다.
    assert "recommended changes for are NOT deliveries" in p


def test_redteam_run_review_carries_delivery_facts(monkeypatch):
    from modules import redteam
    import modules.llm as _llm

    class _M:
        def __init__(self, c): self.content = c
    class _C:
        def __init__(self, c): self.message = _M(c)
    class _R:
        def __init__(self, c): self.choices = [_C(c)]

    cap: dict = {}
    monkeypatch.setattr(_llm, "_openai_chat_completion_with_deadline",
                        lambda client, model, messages, **kw: (cap.update(messages=messages),
                                                               _R('{"verdict":"pass","findings":[]}'))[1])
    redteam.run_review("q", "DRAFT", "digest",
                       delivery_facts="DELIVERY FACTS (application-computed, authoritative):\n- x")
    blk = cap["messages"][-1]["content"]
    assert "DELIVERY FACTS" in blk
    assert blk.index("DELIVERY FACTS") < blk.index("DRAFT"), "초안 앞에 실려야 대조가 성립"


def test_redteam_orchestrate_forwards_delivery_facts(monkeypatch):
    from modules import redteam
    monkeypatch.setattr(redteam, "review_plan",
                        lambda lvl: {"timeout_sec": 5, "verify_pass": False, "max_revisions": 0,
                                     "revise_until_resolved": False})
    monkeypatch.setattr(redteam, "record_review", lambda **kw: None)
    monkeypatch.setattr(redteam, "recent_conversation_reviews", lambda *a, **kw: [])
    cap: dict = {}
    monkeypatch.setattr(redteam, "run_review",
                        lambda *a, **kw: (cap.update(kw), {"verdict": "pass", "findings": []})[1])
    redteam.orchestrate_review(
        question="q", draft_answer="d", steps=[], executed_sql="",
        conversation_id="c", run_id="r", reasoning_level="normal", is_group=False,
        delivery_facts={"delivered": 1, "truncated": True})
    assert "update_attachment tool so far: 1" in (cap.get("delivery_facts") or "")


# ── §18.8 흡수: 패널이 "뮤턴트 생존" 으로 실증한 배선 seam ──────────────────


def test_execute_tool_routes_update_attachment(monkeypatch):
    """§18.8 [P2] — `_TOOL_HANDLERS` 에서 키를 지워도 39건이 전부 통과했다.

    모든 테스트가 핸들러를 직접 불러서, 라우팅이 끊기면 기능이 죽는데 스위트는 초록이었다.
    """
    _setup(monkeypatch)
    out = tools.execute_tool(None, "update_attachment", {"filename": "a.sql", "content": "X"})
    assert "전달 완료" in out
    assert "알 수 없는 도구" not in out


def test_materialize_signature_contract():
    """§18.8 [P2] — `_FakeWeb` 은 `**kw` 를 삼켜 실제 시그니처 변경을 못 잡는다.

    도구가 넘기는 키워드가 실 함수에 그대로 bind 되는지 **실 함수 시그니처**로 검사한다.
    """
    import inspect
    import app as webapp  # 운영 경로(web.app)와 동일하게 패키지 진입점을 통해 얻는다
    sig = inspect.signature(webapp._materialize_assistant_attachment_edits)
    # 도구 경로가 쓰는 호출 형태가 실제로 bind 되어야 한다.
    sig.bind(object(), account={}, conversation_id="c",
             blocks=[{"source_attachment_id": 1, "filename": None, "content": "x"}],
             skipped=[], request=None)
    # 기존 블록 경로도 계속 bind 되어야 한다(무회귀).
    sig.bind(object(), account={}, conversation_id="c", answer="a", message_id=1, request=None)


def test_bind_tool_delivered_attachments_signature_contract():
    """칩 바인딩 함수의 호출 형태 — 워커/웹 두 후처리가 같은 키워드를 쓴다."""
    import inspect
    import app as webapp
    inspect.signature(webapp._bind_tool_delivered_attachments).bind(
        object(), conversation_id="c", account_id=1, attachment_ids=[1, 2], message_id=5)


def test_worker_postprocess_binds_tool_deliveries():
    """§18.8 [P1] — 도구 전달분이 있으면 워커가 **조기 반환하지 않고** 바인딩해야 칩이 뜬다.

    feature-0043(2026-08-28) 이후 조립 자체는 `shared/attachment_write.py` 정본에 있고 워커는
    그것을 부른다(브리지 경로와 한 벌). 계약은 그대로이므로 **두 곳에서** 확인한다 —
    워커가 도구 전달분을 정본에 넘기는가, 정본이 조기 반환을 통과한 뒤 바인딩해 합치는가.
    한쪽만 보면 배선이 끊겨도, 조립이 무너져도 통과한다.
    """
    import inspect
    from modules import ask as ask_mod
    from shared import attachment_write as aw

    # ① 워커: 도구 전달분을 읽어 정본에 넘긴다.
    src = inspect.getsource(ask_mod)
    i_ids = src.find('result.get("tool_delivered_attachment_ids")')
    i_early = src.find('return  # 블록도 도구 전달도 없음')
    i_pass = src.find("tool_attachment_ids=_tool_ids")
    assert i_ids > 0 and i_early > i_ids, "조기 반환 판정이 도구 전달분을 고려해야 한다"
    assert i_pass > i_early, "조기 반환을 통과한 뒤 도구 전달분을 후처리에 넘겨야 한다"

    # ② 정본: 자체 조기 반환도 도구 전달분을 고려하고, 바인딩 결과를 edited 에 합친다.
    core = inspect.getsource(aw.apply_assistant_attachment_blocks)
    i_core_early = core.find("if not tool_ids and (")
    i_bind = core.find("_bind_tool_delivered_attachments(")
    assert i_core_early > 0 and i_bind > i_core_early, \
        "정본의 조기 반환이 도구 전달분을 고려하고, 그 뒤 바인딩이 일어나야 한다"
    assert "edited = list(bound) + list(edited)" in core, "응답 shape 에 합쳐져야 칩·토스트가 뜬다"


def test_truncation_latched_before_review():
    """§18.8 [P1] — red-team revise 가 finish_reason 을 덮어 경고가 사라지던 경로.

    초안 확정 시점에 latch 하고, **수정본이 채택될 때만** 재판정해야 한다.
    """
    import inspect
    src = inspect.getsource(agent_core._run_agent_core)
    i_latch = src.find("_draft_truncated = last_answer_was_truncated()")
    i_review = src.find("_redteam.orchestrate_review(")
    i_use = src.find("if _draft_truncated and _TRUNCATED_ANSWER_NOTICE")
    assert 0 < i_latch < i_review, "latch 가 리뷰보다 앞서야 한다"
    assert i_use > i_review, "경고 부착은 리뷰 이후(리뷰가 지우지 못하게)"
    # 채택 시 재판정.
    assert src.count("_draft_truncated = last_answer_was_truncated()") == 2
    assert "last_answer_was_truncated() and _TRUNCATED_ANSWER_NOTICE" not in src, \
        "리뷰 이후 ctx 를 다시 읽으면 안 된다(그 값은 revise 호출로 덮인다)"


def test_delivered_ids_exposed_for_binding():
    """도구 전달 id 가 result 로 나가야 후처리가 바인딩할 수 있다."""
    import inspect
    src = inspect.getsource(agent_core._run_agent_core)
    assert 'result["tool_delivered_attachment_ids"] = _delivered_ids' in src


def test_delivery_facts_are_framed_as_floor():
    """§18.8 [P2] — 블록 경로 전달은 리뷰 시점에 아직 materialize 되지 않는다.

    `delivered` 를 총량으로 읽히게 두면 **정직한 답변을 BLOCK** 한다(혼합 턴).
    """
    from modules import redteam
    out = redteam.build_delivery_facts({"delivered": 1, "truncated": False})
    assert "floor" in out
    assert "NOT counted here" in out
    p = redteam.REDTEAM_REVIEW_PROMPT
    assert "FLOOR, not a total" in p
    assert "no `attachment-edit` block covering the difference" in p


def test_tool_errors_do_not_leak_exception_text(monkeypatch):
    """§18.8 [P2] CODE_REVIEW §2.7 — 예외 원문(호스트·경로)이 모델·저장 메시지로 새면 안 된다."""
    class _Boom:
        def _connect_memory(self):
            raise RuntimeError("mysql://secret-host:3306 connect failed /var/lib/x")

    _setup(monkeypatch, web=_Boom())
    out = tools._tool_update_attachment(None, {"filename": "a.sql", "content": "X"})
    assert "secret-host" not in out and "/var/lib" not in out
    assert "이 파일은 전달되지 않았습니다" in out
