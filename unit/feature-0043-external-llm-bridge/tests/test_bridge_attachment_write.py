"""브리지 경로의 **첨부 쓰기**(수정→새 버전 / 신규 생성) 회귀.

## 무엇을 지키는가

기존 서비스에서 assistant 는 답변에 ```` ```attachment-edit ```` / ```` ```attachment-new ````
블록을 실어 파일을 만들 수 있었다. 브리지 경로에는 그 후처리가 통째로 없어, 개인 AI 가
관례대로 블록을 만들어도 **파일은 생기지 않고 원문 diff 만 채팅에 남았다**(라이브 실측
2026-08-28, 첨부 1246 sample.sql — 답변은 "수정했습니다" 인데 버전은 v1 그대로).

여기서 검사하는 것은 세 가지다:

1. **배선** — 브리지 전달 경로가 첨부 후처리를 실제로 부르는가(헬퍼가 옳게 동작하는지만
   보면, 아무도 그것을 부르지 않는 세계가 통과한다).
2. **한 벌** — worker 경로와 브리지가 **같은 함수**를 쓰는가. 구현이 갈리면 저장 가드도
   갈리고, 느슨한 쪽이 사용자가 보는 진실이 된다.
3. **거짓 성공 금지** — 블록이 있었는데 파일이 안 생기면 답변이 그 사실을 말하는가.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_WEB = _ROOT / "unit" / "feature-0003-agent-web-ui" / "src"
AI_TOOLS = _WEB / "routers" / "ai_tools.py"
CONVERSATIONS = _WEB / "routers" / "conversations.py"
APP = _WEB / "app.py"
ASK = _ROOT / "unit" / "feature-0002-agent-core" / "src" / "modules" / "ask.py"


def _src(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _code_only(text: str) -> str:
    """주석·독스트링을 뺀 코드만. 주석 문구가 계약을 통과시키는 것을 막는다."""
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body[0].value.value = ""
    return "\n".join(
        ln for ln in ast.unparse(tree).splitlines() if not ln.lstrip().startswith("#"))


def _func_body(text: str, name: str) -> str:
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.unparse(node)
    raise AssertionError(f"{name} 를 찾지 못했다")


# ── 1. 배선 ────────────────────────────────────────────────────────────────

def test_bridge_delivery_calls_attachment_postprocess():
    """답변 전달 경로가 첨부 후처리를 **실제로 부른다**.

    헬퍼만 테스트하면 "아무도 부르지 않는 세계" 가 통과한다 — 이 저장소가 반복해서 겪은
    사각이다(배선 끊기 뮤턴트만 검출되는 테스트).
    """
    body = _code_only(_func_body(_src(AI_TOOLS), "_deliver_web_bridge_answer"))
    assert "_materialize_bridge_attachments(" in body, (
        "브리지 전달 경로가 첨부 후처리를 부르지 않는다 — 개인 AI 가 만든 attachment-edit "
        "블록이 파일이 되지 않고 원문이 채팅에 남는다")


def test_bridge_postprocess_runs_after_message_saved():
    """후처리는 **메시지 저장 뒤**에 온다 — message_id 가 있어야 첨부가 말풍선에 바인딩된다.

    ⚠ `"save_memory_message"` 의 첫 위치로 재면 **import 문**을 저장으로 오인한다(codex P2) —
    실제 저장 호출을 지워도 import 만 남으면 통과한다. message_id 를 만드는 **호출**을 본다.
    """
    body = _code_only(_func_body(_src(AI_TOOLS), "_deliver_web_bridge_answer"))
    i_att = body.index("_materialize_bridge_attachments(")
    i_saves = [body.index(c) for c in ("_replace_bridge_placeholder(", "_save_msg(")
               if c in body]
    assert i_saves, "message_id 를 만드는 저장 호출이 없다"
    assert max(i_saves) < i_att, "첨부 후처리가 메시지 저장보다 앞선다 — message_id 바인딩 불가"


def test_bridge_recall_store_gets_cleaned_answer():
    """회수 store 에는 **정리본**이 들어간다.

    원문 블록이 회수본에 남으면 다음 턴 LLM 컨텍스트에 파일 전문이 통째로 다시 실린다
    (표시본은 strip 됐는데 회수본만 부풀어 있는 상태).
    """
    body = _code_only(_func_body(_src(AI_TOOLS), "_deliver_web_bridge_answer"))
    m = re.search(r"_save_message\((.*?)\)\n", body, re.S)
    assert m, "core store 저장 호출을 찾지 못했다"
    assert "_clean" in m.group(1), (
        "회수 store 에 원문(answer)을 그대로 넣는다 — 첨부 블록이 다음 턴 컨텍스트에 재유입된다")


# ── 2. 한 벌인가 ───────────────────────────────────────────────────────────

def test_worker_and_bridge_share_one_implementation():
    """worker(`modules/ask.py`)와 브리지가 **같은 함수**를 쓴다."""
    ask_body = _code_only(_func_body(_src(ASK), "_postprocess_attachment_blocks"))
    assert "_apply_assistant_attachment_blocks(" in ask_body, (
        "worker 경로가 공용 정본을 쓰지 않는다 — 구현이 갈리면 저장 가드도 갈린다")

    bridge_body = _code_only(_func_body(_src(AI_TOOLS), "_materialize_bridge_attachments"))
    assert "_apply_assistant_attachment_blocks(" in bridge_body, (
        "브리지가 공용 정본을 쓰지 않는다")


def test_no_second_materialize_implementation_in_bridge():
    """브리지가 materialize/strip 을 **직접** 부르지 않는다 — 부르면 그게 두 번째 구현이다."""
    bridge_body = _code_only(_func_body(_src(AI_TOOLS), "_materialize_bridge_attachments"))
    for banned in ("_materialize_assistant_attachment_edits",
                   "_materialize_assistant_attachment_new",
                   "_strip_attachment_edit_blocks",
                   "_strip_attachment_new_blocks"):
        assert banned not in bridge_body, (
            f"브리지가 {banned} 를 직접 부른다 — 저장 가드가 두 벌이 된다")


def test_shared_helper_is_exported_from_app():
    """공용 정본이 `app.X` 로 노출된다 — 두 경로 모두 그 이름으로 부른다."""
    src = _src(APP)
    assert "_apply_assistant_attachment_blocks" in src, "app 에서 공용 정본을 export 하지 않는다"


# ── 3. 거짓 성공 금지 ──────────────────────────────────────────────────────

class _Ops:
    """후처리 정본이 쓰는 원시연산 6종의 stub — 저장·MinIO 없이 조립만 시험한다."""

    _ASSISTANT_EDIT_COUNT_CAP = 5

    def __init__(self, *, edits=(), news=(), skipped=(), persisted=True):
        self._edits, self._news, self._skipped = list(edits), list(news), list(skipped)
        self._persisted = persisted
        self.calls = {"edits": 0, "new": 0, "update": 0, "remaining": None}

    def _materialize_assistant_attachment_edits(self, conn, *, account, conversation_id,
                                                answer, message_id, request, skipped=None):
        self.calls["edits"] += 1
        if skipped is not None:
            skipped.extend(self._skipped)
        return list(self._edits)

    def _materialize_assistant_attachment_new(self, conn, *, account, conversation_id,
                                              answer, message_id, request, remaining_count):
        self.calls["new"] += 1
        self.calls["remaining"] = remaining_count
        return list(self._news)

    def _bind_tool_delivered_attachments(self, conn, *, conversation_id, account_id,
                                         attachment_ids, message_id):
        return [{"id": int(i)} for i in attachment_ids]

    @staticmethod
    def _strip_attachment_edit_blocks(answer, materialized):
        return answer.replace("```attachment-edit", "[STRIPPED-EDIT]")

    @staticmethod
    def _strip_attachment_new_blocks(answer, materialized):
        return answer.replace("```attachment-new", "[STRIPPED-NEW]")

    def _update_assistant_message_content(self, conn, cid, mid, content):
        self.calls["update"] += 1
        return self._persisted

    # 실 파서(`_attachment_*_block_spans`)와 **같은 판정**: `strip().startswith` — 들여쓴 것도
    # 인용 안의 것도 블록으로 연다. 정본이 fence 계수 대신 이 값을 분모로 쓰는지 확인한다.
    @staticmethod
    def _attachment_edit_block_spans(answer):
        return [(0, 0, "", "") for ln in (answer or "").splitlines()
                if ln.strip().startswith("```attachment-edit")]

    @staticmethod
    def _attachment_new_block_spans(answer):
        return [(0, 0, "", "") for ln in (answer or "").splitlines()
                if ln.strip().startswith("```attachment-new")]


def _apply(**kw):
    from shared.attachment_write import apply_assistant_attachment_blocks
    ops = kw.pop("ops")
    kw.setdefault("account", {"id": 1})
    kw.setdefault("conversation_id", "c1")
    kw.setdefault("message_id", 7)
    return apply_assistant_attachment_blocks(None, ops=ops, **kw)


def test_fence_count_ignores_quoted_examples():
    """답변이 **예시로 인용한** fence 는 블록으로 세지 않는다.

    단순 substring 카운트를 쓰면 정상 전달에도 "전달 실패" 문단이 붙는다(거짓 경고).
    """
    from shared.attachment_write import count_attachment_block_fences as count

    assert count("```attachment-edit\n{}\nx\n```") == (1, 0)
    assert count("```attachment-new\n{}\nx\n```") == (0, 1)
    # 바깥 fence 안의 인용 — 블록이 아니다
    assert count("````markdown\n```attachment-edit\n{}\n```\n````") == (0, 0)
    # 들여쓴 것도 블록이 아니다
    assert count("    ```attachment-edit\n    {}\n    ```") == (0, 0)
    assert count("본문에 attachment-edit 라는 단어만 있음") == (0, 0)


def test_undelivered_blocks_are_disclosed():
    """블록은 있는데 파일이 안 생기면 **답변이 그 사실을 말한다**.

    본문의 "수정했습니다" 를 고쳐 쓸 수는 없지만, 덧붙는 고지가 그 주장을 정정한다.
    이것이 없으면 사용자는 받지 못한 파일을 받은 줄 안다(거짓 성공).
    """
    ops = _Ops(skipped=["attachment_id=1: 이 대화의 첨부가 아닙니다."])
    out = _apply(ops=ops,
                 answer='고쳤습니다.\n```attachment-edit\n{"source_attachment_id": 1}\nSELECT 1;\n```')

    assert out["undelivered"] == 1
    assert "첨부 전달 실패" in out["answer"], "미전달인데 답변이 조용하다 — 거짓 성공"
    assert "이 대화의 첨부가 아닙니다" in out["answer"], "사유를 알고도 버렸다"
    assert out["edited"] == [] and out["created"] == []


def test_undelivered_without_reason_still_counted():
    """사유를 모르는 미전달(파싱 실패·캡 초과·저장 계층 오류)도 **건수는** 밝힌다."""
    ops = _Ops()   # skipped 없음 = 사유 미상
    out = _apply(ops=ops, answer='```attachment-new\n{"filename":"a.sql"}\nx\n```')
    assert out["undelivered"] == 1
    assert "사유 미상 1건" in out["answer"]


def test_partial_success_is_not_silenced():
    """2건 중 1건만 만들어져도 **모자란 1건**을 고지한다.

    "하나라도 만들었으면 성공" 으로 보면 부분 실패가 통째로 묻힌다.
    """
    ops = _Ops(edits=[{"id": 900, "original_filename": "a.sql", "version_number": 2}])
    answer = ('```attachment-edit\n{"source_attachment_id": 1}\nA\n```\n'
              '```attachment-edit\n{"source_attachment_id": 2}\nB\n```')
    out = _apply(ops=ops, answer=answer)
    assert out["undelivered"] == 1
    assert "첨부 전달 실패" in out["answer"]


def test_tool_delivery_does_not_mask_a_failed_block():
    """도구 전달분이 블록 실패를 **상쇄하지 못한다**.

    합본으로 세면 "도구로 1건 전달 + 블록 1건 실패" 가 0 이 되어 경고가 사라진다.
    """
    ops = _Ops()   # 블록 경로 0건
    out = _apply(ops=ops, tool_attachment_ids=[555],
                 answer='```attachment-edit\n{"source_attachment_id": 1}\nA\n```')
    assert out["undelivered"] == 1, "도구 전달분이 블록 실패를 가렸다"
    assert any(int(a.get("id") or 0) == 555 for a in out["edited"]), "도구 전달분 미바인딩"


def test_count_cap_is_shared_between_edit_and_new():
    """개수 상한은 edit·new 가 **합산**한다 — new 의 remaining 은 CAP - len(edits)."""
    ops = _Ops(edits=[{"id": i} for i in range(3)],
               news=[{"id": 900, "original_filename": "a.sql"}])
    _apply(ops=ops, answer='```attachment-edit\n{"source_attachment_id":1}\nA\n```\n'
                           '```attachment-new\n{"filename":"a.sql"}\nB\n```')
    assert ops.calls["remaining"] == 2, "cap 이 경로별로 따로 세어진다"


def test_answer_persisted_flag_gates_caller_copy():
    """content 갱신이 실패하면 `answer_persisted=False` — 호출자가 자기 사본을 안 바꾼다.

    이게 없으면 DB 메시지는 원문인데 ops view·회수본만 정리본이 되어 둘이 갈린다.
    """
    ops = _Ops(persisted=False)
    out = _apply(ops=ops, answer='```attachment-new\n{}\nx\n```')
    assert out["changed"] is True
    assert out["answer_persisted"] is False


def test_failed_run_skips_materialize_but_still_strips():
    """실패·취소 run 은 첨부를 만들지 않되 **strip 은 한다**.

    실패했다고 파일 전문을 채팅에 쏟아 두지 않는다. 그리고 미전달 고지도 붙이지 않는다 —
    이미 오류가 표면화돼 있어 같은 사실을 두 번 다르게 말하게 된다.
    """
    ops = _Ops()
    out = _apply(ops=ops, failed=True,
                 answer='```attachment-edit\n{"source_attachment_id": 1}\nx\n```')

    assert ops.calls["edits"] == 0, "실패 run 에서 materialize 를 시도했다"
    assert "[STRIPPED-EDIT]" in out["answer"], "실패 run 에서 strip 을 건너뛰었다"
    assert "첨부 전달 실패" not in out["answer"], "실패 run 에 미전달 고지까지 겹쳤다"


def test_no_blocks_is_free():
    """블록도 도구 전달분도 없으면 아무 것도 하지 않는다(흔한 경로 비용 0)."""
    ops = _Ops()
    out = _apply(ops=ops, answer="그냥 답변")
    assert ops.calls["edits"] == 0 and ops.calls["new"] == 0
    assert out["changed"] is False and out["answer"] == "그냥 답변"


# ── 4. 개인 AI 쪽 안내 중복 금지 ───────────────────────────────────────────

def test_runner_prompt_does_not_duplicate_write_convention():
    """러너 프롬프트가 첨부 쓰기 규약을 **다시 적지 않는다**.

    규약은 `system_prompt`(agent_core base)가 이미 싣고 온다. 여기 또 적으면 두 벌이 되고,
    형식이 갈리는 순간 서버 파서가 아는 쪽만 파일이 된다.
    """
    agent = _ROOT / "unit" / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"
    body = _code_only(_func_body(_src(agent), "compose_prompt"))
    assert "attachment-edit" not in body and "attachment-new" not in body, (
        "러너 프롬프트가 첨부 쓰기 규약을 중복 정의한다 — system_prompt 와 갈릴 수 있다")


# ── 5. codex 적대 리뷰 조치 회귀 (2026-08-28) ─────────────────────────────

def test_block_only_answer_does_not_resurrect_raw_body():
    """블록 **하나로만** 이뤄진 답변에서 원문이 되살아나지 않는다 (codex P1).

    종전 strip 은 `stripped or answer` 였다 — 설명 없이 파일만 준 답변은 strip 결과가 비어
    **원문이 그대로 돌아왔다**. materialize 가 실패했거나 `failed=True` 라 건너뛴 run 에서는
    안내 문구도 안 붙으므로, 그 자리에 파일 전문이 채팅에 굳는다.
    """
    import ast as _ast
    src = _src(CONVERSATIONS)
    tree = _ast.parse(src)
    for name in ("_strip_attachment_edit_blocks", "_strip_attachment_new_blocks"):
        fn = next(n for n in _ast.walk(tree)
                  if isinstance(n, _ast.FunctionDef) and n.name == name)
        body = _code_only(_ast.unparse(fn))
        assert "return stripped or answer" not in body, (
            f"{name} 이 빈 strip 결과에서 원문을 되살린다 — 파일 전문이 채팅에 남는다")


def test_persist_checks_rowcount():
    """content 갱신은 **행 수**를 본다 (codex P1).

    예외만 없으면 True 였다 — 0행을 갱신하고도 "영속됐다" 고 답하면, 그 말을 믿은 호출자가
    회수 store·result_json 만 정리본으로 바꿔 화면과 갈린다.
    """
    import ast as _ast
    fn = next(n for n in _ast.walk(_ast.parse(_src(CONVERSATIONS)))
              if isinstance(n, _ast.FunctionDef)
              and n.name == "_update_assistant_message_content")

    # `rowcount` 가 **본문 어딘가에** 있는지로는 부족하다 — 값을 읽어 두고 무시해도 통과한다.
    # 모든 `return True` 가 **행 수 판정 안에** 있어야 한다(백엔드 2경로 각각).
    guarded, bare = 0, 0
    for node in _ast.walk(fn):
        if isinstance(node, _ast.If):
            test = _ast.unparse(node.test)
            if "rows" not in test:
                continue
            for st in node.body:
                if isinstance(st, _ast.Return) and getattr(st.value, "value", None) is True:
                    guarded += 1
    for node in _ast.walk(fn):
        if isinstance(node, _ast.Return) and getattr(node.value, "value", None) is True:
            bare += 1
    assert guarded == bare == 2, (
        f"행 수 판정 밖의 성공 반환이 있다 (guarded={guarded}, total_true={bare}) — "
        "0행을 갱신하고도 '영속됐다' 고 답하면 화면과 회수본이 갈린다")
    assert "rowcount" in _code_only(_ast.unparse(fn)), "행 수를 읽지 않는다"


def test_done_waits_briefly_for_delivery():
    """제출 직후 **아직 대화에 실리지 않았으면** 잠깐은 `working` 이다 (codex P1).

    `Status='submitted'` 는 말풍선 저장·첨부 materialize 보다 **먼저** 커밋된다(재제출 차단이
    그 커밋에 걸려 있다). 그 사이에 `done` 을 내보내면 프런트가 이력을 다시 읽고 스트림을
    닫는데, 그때 대화에는 대기 말풍선밖에 없어 새로고침 전까지 굳는다.

    다만 **영원히 기다리지는 않는다** — 전달이 진짜 실패하면 유예 후 `done` 으로 보내
    `delivered=false` 안내가 뜨게 한다(도는 화면보다 정직하다).
    """
    import importlib.util
    import sys
    import types

    if "app" not in sys.modules:
        sys.modules["app"] = types.ModuleType("app")
    src = _src(AI_TOOLS)
    tree = ast.parse(src)
    ns: dict = {"Any": object, "_STATUS_CANCELED": "canceled", "_STATUS_EXPIRED": "expired",
                "_STATUS_DEFERRED": "deferred"}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("_bridge_phase", "_age_sec"):
            exec(compile(ast.Module([node], []), "<phase>", "exec"), ns)
        elif isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == \
                "_BRIDGE_DELIVER_GRACE_SEC":
            exec(compile(ast.Module([node], []), "<grace>", "exec"), ns)
    phase = ns["_bridge_phase"]
    grace = ns["_BRIDGE_DELIVER_GRACE_SEC"]

    # 제출 직후 · 미전달 → 아직 처리 중
    assert phase("submitted", "me", True, True, delivered=False, submitted_age_sec=0.5) == "working"
    # 유예를 넘겼으면 종결 — 프런트가 delivered=false 를 알린다
    assert phase("submitted", "me", True, True, delivered=False,
                 submitted_age_sec=grace + 1) == "done"
    # 전달까지 끝났으면 즉시 종결
    assert phase("submitted", "me", True, True, delivered=True, submitted_age_sec=0.1) == "done"
    # 나이를 모르면 유예를 적용하지 않는다(기존 동작 보존)
    assert phase("submitted", "me", True, True, delivered=False, submitted_age_sec=None) == "done"
    # 취소는 여전히 맨 앞
    assert phase("canceled", "me", True, True, delivered=False, submitted_age_sec=0.1) == "canceled"


def test_phase_call_sites_pass_delivery_state():
    """폴링·스트리밍 **둘 다** 전달 상태를 넘긴다 — 한쪽만 넘기면 전송 방식에 따라 화면이 갈린다."""
    src = _code_only(_src(AI_TOOLS))
    # 정의부(`def _bridge_phase(...)`)는 호출부가 아니다 — 제외하지 않으면 시그니처의 기본값이
    # 단언을 통과시켜 **호출부를 하나도 안 보고도** green 이 된다.
    calls = [m.group(0) for m in re.finditer(r"(?<!def )_bridge_phase\((?:[^()]|\([^()]*\))*\)", src)]
    assert len(calls) >= 2, f"_bridge_phase 호출부를 찾지 못했다: {len(calls)}"
    for c in calls:
        assert "delivered=" in c and "submitted_age_sec=" in c, (
            f"전달 상태를 넘기지 않는 호출부가 있다: {c[:90]}")


def test_undelivered_uses_parser_not_fence_semantics():
    """미전달 계수의 분모는 **파서가 열려는 블록 수**다 (codex P1).

    fence 계수기는 들여쓴 fence 를 "예시" 로 보고 세지 않지만, 실제 파서는
    `strip().startswith` 라 그것도 materialize 한다. 분모를 fence 로 두면 저장이 실패해도
    미전달 0 이 되어 **답변이 아무 말도 하지 않는다**(거짓 성공의 재발).
    """
    from shared.attachment_write import count_attachment_block_fences

    indented = '    ```attachment-edit\n    {"source_attachment_id": 1}\n    x\n    ```'
    assert count_attachment_block_fences(indented) == (0, 0)   # markdown 의미론

    ops = _Ops()          # 파서 판정: 1건 열림, materialize 결과 0건
    out = _apply(ops=ops, answer=indented)
    assert out["undelivered"] == 1, "파서가 열려는 블록을 분모에서 빠뜨렸다"
    assert "첨부 전달 실패" in out["answer"]


def test_fence_fallback_when_parser_unavailable():
    """파서를 부를 수 없으면 fence 계수로 물러난다 — **과대계상은 하지 않는다**."""
    class _NoParser(_Ops):
        _attachment_edit_block_spans = None    # 호출 시 TypeError
        _attachment_new_block_spans = None

    ops = _NoParser()
    out = _apply(ops=ops,
                 answer='```attachment-edit\n{"source_attachment_id": 1}\nx\n```')
    assert out["undelivered"] == 1             # fence 로도 1건은 잡힌다
    # 인용 예시는 fence 계수가 0 → 거짓 실패 문구를 만들지 않는다
    out2 = _apply(ops=_NoParser(),
                  answer='````markdown\n```attachment-edit\n{}\n```\n````')
    assert out2["undelivered"] == 0
