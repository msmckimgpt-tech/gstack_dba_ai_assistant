"""feature-0043 TASK-20260902T110000 — 콘솔 작업의 모델·추론등급을 계정이 정한다.

이 스위트가 잠그는 것은 두 가지다.

1. **해석 정본**(`shared.bridge_tasks`)의 순수 함수 계약 — 정규화·해석·자격.
2. **배선**: 그 판정이 실제로 claim·적재 게이트·목록 필터에 꽂혀 있는가. 이 feature 가 반복해
   겪은 결함이 「함수는 맞는데 그 자리에 없다」였으므로(P0-T·P0-M), 로직만 검사하면 회귀를
   놓친다. 웹 라우터는 conftest 규약상 여기서 import 할 수 없어 AST/텍스트 층에서 잠근다.

역검증 기준: 아래 테스트들은 이 cycle 이전 코드(`resolve_console_job_request` 부재 ·
`reasoning_level: ""` 고정 · `runner_can_take` 모델 축 없음)에서 전부 실패해야 한다.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from shared import bridge_tasks as bt

_UNIT = pathlib.Path(__file__).resolve().parents[2]
WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
TOOLS_PY = WEB_SRC / "routers" / "ai_tools.py"
PROFILE_PY = WEB_SRC / "routers" / "profile.py"
SCHEMA_PY = WEB_SRC / "routers" / "_bootstrap_schema.py"
CONSOLE_LLM_PY = WEB_SRC / "routers" / "_console_llm.py"
CONSOLE_JOBS_PY = WEB_SRC / "routers" / "_console_jobs.py"
OAUTH_STORE_PY = WEB_SRC / "oauth_store.py"
PROFILE_JS = WEB_SRC / "static" / "app" / "profile.js"
INDEX_HTML = WEB_SRC / "static" / "index.html"
NODE_ANALYSIS_PY = _UNIT / "feature-0002-agent-core" / "src" / "modules" / "node_analysis.py"
CLUSTER_PY = _UNIT / "feature-0002-agent-core" / "src" / "modules" / "semantic_cluster.py"
INSIGHT_PY = _UNIT / "feature-0002-agent-core" / "src" / "modules" / "insight.py"


#: 러너가 하트비트로 신고하는 모양 그대로(라이브 실측 2026-09-02).
CAPS = [
    {"runtime": "claude", "label": "Claude",
     "models": [{"value": "fable", "label": "Fable"}, {"value": "opus", "label": "Opus"},
                {"value": "sonnet", "label": "Sonnet"}, {"value": "haiku", "label": "Haiku"}],
     "efforts": [{"value": "low", "label": "Low"}, {"value": "medium", "label": "Medium"},
                 {"value": "high", "label": "High"}]},
    {"runtime": "codex", "label": "Codex",
     "models": [{"value": "gpt-5.6-luna", "label": "Luna"}],
     "efforts": [{"value": "low", "label": "낮음"}]},
]


def _src(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _func_src(path: pathlib.Path, name: str) -> str:
    text = _src(path)
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{path.name} 에 {name} 가 없다")


# ── 1. 정규화 ────────────────────────────────────────────────────────────────


def test_normalize_keeps_known_kinds_only():
    """모르는 항목 키는 버린다 — 남기면 어느 화면에서도 지울 수 없는 설정이 된다."""
    out = bt.normalize_console_job_prefs(
        {"node_analysis": {"model": "claude:haiku", "effort": "medium"},
         "not_a_job": {"model": "claude:opus"}})
    assert set(out) == {"node_analysis"}
    assert out["node_analysis"] == {"model": "claude:haiku", "effort": "medium"}


def test_normalize_accepts_json_text_and_drops_empty_entries():
    """저장은 문자열로 오간다. 두 축이 모두 빈 항목은 통째로 뺀다(=미설정과 같은 모양)."""
    out = bt.normalize_console_job_prefs(
        '{"node_analysis": {"model": "", "effort": ""}, "cluster_label": {"effort": "low"}}')
    assert out == {"cluster_label": {"effort": "low"}}


@pytest.mark.parametrize("raw", ["", "not json", None, [], 5])
def test_normalize_bad_input_is_empty(raw):
    """깨진 저장값이 예외로 새면 프로필 화면과 배급 판정이 함께 죽는다."""
    assert bt.normalize_console_job_prefs(raw) == {}


# ── 2. 해석 (claim 이 실을 값) ─────────────────────────────────────────────────


def test_resolve_uses_account_choice():
    """고른 모델·등급이 그대로 나간다 — 이 cycle 의 본체."""
    got = bt.resolve_console_job_request(
        "node_analysis", {"node_analysis": {"model": "claude:haiku", "effort": "medium"}}, CAPS)
    assert (got["runtime"], got["model"], got["effort"]) == ("claude", "haiku", "medium")
    assert got["blocked"] is False and got["source"] == "prefs"


def test_resolve_blocks_when_chosen_model_missing():
    """고른 모델이 러너 신고에 없으면 **위임하지 않는다** (사용자 결정 2026-09-02).

    조용히 상위 모델로 갈아타면 사용자는 자기가 고른 것으로 돌았다고 믿는다 — 이 cycle 이
    고치는 결함 그 자체다.
    """
    caps = [{"runtime": "claude", "models": [{"value": "opus"}], "efforts": [{"value": "high"}]}]
    got = bt.resolve_console_job_request(
        "node_analysis", {"node_analysis": {"model": "claude:haiku"}}, caps)
    assert got["blocked"] is True
    assert got["required_model"] == "claude:haiku"
    assert got["model"] != "opus", "거절 대신 상위 모델로 대체하면 안 된다"


def test_resolve_effort_unmet_does_not_block():
    """등급은 실행 가능성을 좌우하지 않는다 — 비워 보내되 미반영 사실은 남긴다."""
    caps = [{"runtime": "claude", "models": [{"value": "haiku"}], "efforts": [{"value": "high"}]}]
    got = bt.resolve_console_job_request(
        "node_analysis", {"node_analysis": {"model": "claude:haiku", "effort": "medium"}}, caps)
    assert got["blocked"] is False and got["effort"] == ""
    assert any("medium" in u for u in got["unmet"])


def test_resolve_unset_account_falls_back_to_light_and_never_blocks():
    """미설정 계정은 종전 그대로 — 새 규칙이 아무것도 고르지 않은 사용자를 막지 않는다."""
    got = bt.resolve_console_job_request("node_analysis", {}, CAPS)
    assert got["blocked"] is False
    assert (got["runtime"], got["model"]) == ("claude", "haiku")
    assert got["source"] == "light"


def test_resolve_unset_with_no_light_match_still_runs():
    """경량 후보조차 없으면 빈 값(러너 기본) — 거절은 «고른 것이 있는데 없을 때»만이다."""
    caps = [{"runtime": "claude", "models": [{"value": "opus"}], "efforts": []}]
    got = bt.resolve_console_job_request("node_analysis", {}, caps)
    assert got["blocked"] is False and got["model"] == ""


def test_resolve_effort_only_choice_is_sent():
    """모델은 자동(경량)이고 등급만 고른 계정도 그 등급이 반영된다."""
    got = bt.resolve_console_job_request(
        "node_analysis", {"node_analysis": {"effort": "low"}}, CAPS)
    assert got["model"] == "haiku" and got["effort"] == "low" and got["blocked"] is False


def test_resolve_requires_runtime_qualified_model():
    """런타임 없는 모델 이름은 쓰지 않는다 — 러너가 자기 런타임과 대조해 떨어뜨린다."""
    got = bt.resolve_console_job_request("node_analysis", {"node_analysis": {"model": "haiku"}}, CAPS)
    assert got["source"] == "light", "런타임 미지정 값은 선택으로 인정하지 않는다"


# ── 3. 자격 (배급 게이트) ─────────────────────────────────────────────────────


_READY = {"listening": True, "features": ["console_jobs", "batch_jobs"],
          "agent_version": "9999.1.1", "capabilities": CAPS}


def test_runner_can_take_without_required_model_is_unchanged():
    """모델 축을 넘기지 않으면 종전 판정 그대로(무회귀)."""
    assert bt.runner_can_take(_READY) is True
    assert bt.runner_can_take(_READY, need_batch=True) is True


def test_runner_can_take_rejects_missing_required_model():
    assert bt.runner_can_take(_READY, required_model="claude:haiku") is True
    assert bt.runner_can_take(_READY, required_model="claude:sol") is False
    assert bt.runner_can_take(_READY, required_model="ollama:haiku") is False


def test_console_job_model_required_reads_only_that_kind():
    prefs = {"node_analysis": {"model": "claude:haiku"}, "cluster_label": {"effort": "low"}}
    assert bt.console_job_model_required("node_analysis", prefs) == "claude:haiku"
    assert bt.console_job_model_required("cluster_label", prefs) == ""
    assert bt.console_job_model_required("insight_summary", prefs) == ""


# ── 4. 배선 — 판정이 실제로 그 자리에 있는가 ──────────────────────────────────


def test_claim_sends_chosen_effort_not_empty_string():
    """claim 응답의 `reasoning_level` 이 **고정 빈 문자열이 아니다**.

    종전 코드는 `"reasoning_level": ""` 를 하드코딩했고, 그래서 실행이 그 머신 CLI 기본값
    (사용자 환경에서 low)을 따랐다 — 제보된 증상의 절반이 이것이다.
    """
    src = _func_src(TOOLS_PY, "_claim_console_job")
    assert '"reasoning_level": ""' not in src, "등급을 여전히 빈 값으로 고정하고 있다"
    assert "_req_effort" in src and "resolve_console_job_request" in src


def test_claim_rejects_blocked_and_releases_claim():
    """고른 모델이 없으면 409 로 거절하고 **점유를 되돌린다**(붙들고 거절하면 30분 잠긴다)."""
    src = _func_src(TOOLS_PY, "_claim_console_job")
    assert 'blocked' in src and "_release_claim(" in src
    assert "409" in src


def test_claim_records_execution_choice_on_task_row():
    """무엇으로 돌렸는지를 작업 행에 남긴다 — 이 결함의 진단을 러너 로그에 의존하지 않게."""
    src = _func_src(TOOLS_PY, "_claim_console_job")
    assert "RequestedRuntime" in src and "RequestedModel" in src and "ReasoningLevel" in src
    assert "UPDATE WebAiTasks" in src


def test_claim_reads_capabilities_of_the_calling_runner():
    """능력을 **이 요청을 보낸 러너**의 것으로 읽는다(세션 결합) — 계정 최신이 아니라.

    거절이 붙은 이상 「A 가 신고한 목록으로 판정해 B 에게 보내는」 어긋남은 멀쩡한 러너를
    막는 장애가 된다. 세션을 못 찾으면 계정 축으로 폴백해야 한다(비결합 토큰 무회귀).
    """
    src = _func_src(TOOLS_PY, "_claim_console_job")
    assert "runner_capabilities_for_session" in src
    assert 'ctx.get("session_id")' in src
    assert "account_runner_capabilities" in src, "세션 미특정 시 폴백이 없다"


def test_session_capabilities_falls_back_to_empty_not_exception():
    """조회 실패·세션 미지정은 **빈 목록**(호출측이 폴백) — 여기서 fail-closed 로 가면
    세션 비결합 토큰의 러너가 아무 작업도 받지 못한다."""
    class _Cur:
        def execute(self, *a, **k):
            raise RuntimeError("db down")

        def fetchone(self):
            return None

    assert bt.runner_capabilities_for_session(_Cur(), 1, "s1") == []
    assert bt.runner_capabilities_for_session(_Cur(), 1, "") == []
    assert bt.runner_capabilities_for_session(_Cur(), 0, "s1") == []


def test_release_claim_covers_batch_tasks():
    """배경 배치는 `AccountId=0` 이라 소유 조건만으로는 자기 점유도 못 되돌린다."""
    src = _func_src(TOOLS_PY, "_release_claim")
    assert "ClaimedBy=%s" in src, "점유자 기준 해제 조건이 없다"


def test_open_requests_filters_blocked_jobs():
    """이미 쌓인 작업도 목록에서 뺀다 — claim 거절만으로는 러너가 공회전한다."""
    text = _src(TOOLS_PY)
    assert "resolve_console_job_request" in text
    assert "_bridge_tasks.resolve_console_job_request" in text


def test_console_llm_state_takes_job_kind_and_has_model_reason():
    """화면이 「왜 못 맡기는지」를 갱신이 아니라 **설정** 으로 말한다."""
    text = _src(CONSOLE_LLM_PY)
    assert "DELEGATION_MODEL_UNAVAILABLE" in text
    src = _func_src(CONSOLE_LLM_PY, "console_llm_state")
    assert "job_kind" in src and "required_model" in src


def test_web_enqueue_passes_job_kind_to_state():
    """적재 게이트가 항목을 넘겨야 «표시는 맡겼다는데 claim 은 거절» 이 생기지 않는다."""
    text = _src(CONSOLE_JOBS_PY)
    assert "console_llm_state(conn, account, job_kind=job_kind)" in text


def test_worker_gates_pass_required_model():
    """워커 3경로가 같은 판정을 쓴다 — 웹만 거절하면 워커가 유령 작업을 쌓는다."""
    assert "console_job_model_required" in _src(NODE_ANALYSIS_PY)
    cluster = _src(CLUSTER_PY)
    assert "console_job_model_required" in cluster
    assert '_batch_consenting_account(mem, "cluster_label")' in cluster
    assert '_batch_consenting_account(mem_conn, "insight_summary")' in _src(INSIGHT_PY)


def test_prefs_query_lives_in_shared_not_duplicated():
    """질의 정본은 `shared` 하나 — 워커는 `oauth_store` 를 import 하지 못한다."""
    assert "def console_job_prefs_for_account" in _src(pathlib.Path(bt.__file__))
    store = _src(OAUTH_STORE_PY)
    assert "bridge_tasks.console_job_prefs_for_account" in store
    assert store.count("SELECT ConsoleJobPrefs") == 0, "저장소에 질의가 두 벌이다"


def test_schema_alter_is_on_fast_path():
    """신규 컬럼이 **기존 운영 DB 에 실제로 생긴다**.

    `BridgeDefaultModel` 이 slow path 에만 있어 라이브에 없던 것이 이 규칙의 근거다
    (라이브 실측 2026-09-02) — 그 둘도 같은 자리로 옮겼는지 함께 잠근다.
    """
    src = _func_src(SCHEMA_PY, "_ensure_bridge_heartbeat_schema")
    for col in ("ConsoleJobPrefs", "BridgeDefaultModel", "BridgeDefaultEffort"):
        assert f"ADD COLUMN {col}" in src, f"{col} 이 fast path 에 없다"


def test_profile_api_is_self_scoped():
    """계정 파라미터가 없다 — 남의 설정을 건드릴 표면 자체를 만들지 않는다."""
    text = _src(PROFILE_PY)
    assert '@router.get("/api/profile/console-jobs")' in text
    assert '@router.put("/api/profile/console-jobs")' in text
    for name in ("get_profile_console_jobs", "put_profile_console_jobs"):
        src = _func_src(PROFILE_PY, name)
        assert 'account.get("id")' in src or '(account or {}).get("id")' in src
        assert "account_id" not in src.split("def ")[0]


def test_profile_tab_is_wired_in_frontend():
    """탭·pane·로더가 함께 있어야 한다 — 하나만 있으면 빈 탭이 열린다."""
    html = _src(INDEX_HTML)
    assert 'data-profile-tab="ai-jobs"' in html and 'data-profile-pane="ai-jobs"' in html
    js = _src(PROFILE_JS)
    assert 'tab === "ai-jobs"' in js and "loadAiJobs" in js
    assert "/api/profile/console-jobs" in js
