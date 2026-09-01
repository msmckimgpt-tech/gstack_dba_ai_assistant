"""feature-0043 (TASK-20260901T190000) — 남은 AI 기능 3종의 **개인 AI 배선** 계약.

사용자 제보(2026-09-01): *"'그래프 뷰' 내 'AI 능동 분석'에 대한 기능이 막혀있는것으로
확인되었습니다. 서비스 내 AI 관련 모든 작동사항을 다시 활성화 후, 연결한 AI를 통해 작동하도록
배선해주세요."*

## 이 파일이 잠그는 것

배선의 **전 구간**이다 — 어느 한 칸이라도 비면 화면은 "할 수 있다" 고 말하는데 누르면 아무
일도 일어나지 않는다(이 feature 가 P0-M·P0-T 에서 두 번 밟은 함정).

| 칸 | 무엇을 확인하나 |
|---|---|
| 적재 자격 | `JOB_SPECS[...]["wired"]` 가 참인 종류는 **반영 함수가 실재**하는가 |
| 프롬프트 | 위임과 서버 호출이 **같은 조립 함수**를 쓰는가(두 벌이면 한쪽이 낡는다) |
| 게이트 | 게이트가 닫혀도 **위임 가능하면** 분석이 시작되는가 |
| 반영 | 결과가 원래 저장 경로에 들어가고, 늦은 답이 최신 값을 덮지 않는가 |
| 중복 | 결과가 오기 전에 같은 작업을 **다시 사지** 않는가 |
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from shared import bridge_tasks as bt

_REPO = Path(__file__).resolve().parents[3]
_CORE = _REPO / "unit" / "feature-0002-agent-core" / "src"
_WEB = _REPO / "unit" / "feature-0003-agent-web-ui" / "src"


# ── 1. 적재 자격과 반영 함수가 **함께** 선다 ────────────────────────────────────


def _store_routes() -> dict:
    """`_console_jobs._STORE_ROUTES` 를 **소스에서** 읽는다.

    import 하지 않는 이유: 그 모듈은 feature-0003 의 `app` 을 끌어오고, 이 테스트 디렉토리는
    conftest 규약상 그 `src` 를 path 에 올리지 않는다(두 feature 의 `modules` 패키지가 서로를
    가린다). 우리가 확인하려는 것은 **표의 내용**이지 웹 앱의 기동이 아니다.
    """
    src = (_WEB / "routers" / "_console_jobs.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "_STORE_ROUTES":
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "_STORE_ROUTES" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("_STORE_ROUTES 를 찾지 못했다")


def _module_defines(rel_path: str, func_name: str) -> bool:
    """그 모듈이 그 이름의 함수를 **정의하는가** — 소스 AST 로 확인.

    `hasattr` 로 보지 않는 이유: import 는 무거운 의존성을 끌어오고, 우리가 묻는 것은
    「그 함수가 코드에 있는가」이지 「지금 이 환경에서 import 되는가」가 아니다.
    """
    tree = ast.parse((_CORE / rel_path).read_text(encoding="utf-8"))
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func_name
               for n in tree.body)


def test_wired_kinds_have_a_real_reflection_function():
    """`wired: True` 인 자동기입형 종류는 **반영 함수가 실재**한다.

    이 표에 이름만 적고 구현을 두지 않으면 러너가 실제로 그 작업을 가져가 토큰과 시간을 쓰고,
    남는 것은 "제출됐지만 반영 실패" 뿐이다.
    """
    routes = _store_routes()
    missing = []
    for kind, spec in bt.JOB_SPECS.items():
        if not spec.get("wired") or spec.get("apply") != "store":
            continue
        assert kind in routes, f"{kind}: wired=True 인데 자동기입 경로가 없다"
        module_name, func_name = routes[kind]
        rel = module_name.replace(".", "/") + ".py"
        if not _module_defines(rel, func_name):
            missing.append(f"{kind} → {module_name}.{func_name}")
    assert not missing, "wired=True 인데 반영 함수가 없다(부분 배선): " + ", ".join(missing)


def test_graph_node_analysis_is_wired():
    """사용자가 막혔다고 제보한 그 기능이 **실제로 배선됐다**."""
    assert bt.JOB_SPECS["node_analysis"]["wired"] is True
    assert _module_defines("modules/node_analysis.py", "apply_external_node_analysis")


# ── 2. 위임과 서버 호출이 같은 프롬프트를 쓴다 ──────────────────────────────────


def _calls_in(rel_path: str, func_name: str) -> set:
    """그 함수 본문이 부르는 이름들(속성 호출 포함 끝 이름)."""
    tree = ast.parse((_CORE / rel_path).read_text(encoding="utf-8"))
    out: set = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    fn = sub.func
                    if isinstance(fn, ast.Name):
                        out.add(fn.id)
                    elif isinstance(fn, ast.Attribute):
                        out.add(fn.attr)
    return out


def test_server_call_and_delegation_share_the_prompt_builder():
    """노드 분석 프롬프트는 **한 함수**에서 조립된다 — 서버 호출도 위임도 그것을 부른다.

    문자열 검사가 아니라 AST 로 본다: 설명 주석에 함수 이름이 적혀 있으면 문자열 검사는
    거짓 통과(또는 거짓 실패)한다 — 이 feature 가 자가 검증 축에서 실제로 밟은 함정.
    """
    assert "node_analysis_messages" in _calls_in("modules/llm.py", "llm_node_analysis"), (
        "서버 호출이 조립 정본을 부르지 않는다 — 프롬프트가 두 벌이 됐다")
    assert "node_analysis_messages" in _calls_in("modules/node_analysis.py", "_delegate_job"), (
        "위임이 조립 정본을 부르지 않는다 — 같은 분석이 경로에 따라 다른 규칙으로 산출된다")
    assert "table_insight_messages" in _calls_in("modules/llm.py", "llm_table_insight")
    assert "table_insight_messages" in _calls_in("modules/insight.py", "_delegate_table_insight")


def test_delegation_does_not_rewrite_the_flattener():
    """위임 프롬프트 편성(`messages_to_prompt`)도 **한 곳**이다 — 웹과 워커가 같은 것을 쓴다."""
    web_src = (_WEB / "routers" / "_console_jobs.py").read_text(encoding="utf-8")
    assert "messages_to_prompt = _bt_messages_to_prompt" in web_src, (
        "웹이 자기 편성을 되살렸다 — 워커와 갈릴 준비가 끝났다")
    assert callable(bt.messages_to_prompt)


# ── 3. 게이트: 닫혀도 위임 가능하면 시작된다 ────────────────────────────────────


def test_enqueue_gate_passes_when_delegation_is_possible(monkeypatch):
    """서버 LLM 이 닫혀 있어도 **연결된 AI 가 있으면** 분석이 막히지 않는다.

    이것이 사용자 제보의 핵심이다 — 종전에는 게이트가 닫혔다는 이유만으로 적재 전에 거절했다.
    """
    from modules import node_analysis as na

    monkeypatch.setenv("AGENT_SERVER_LLM_ENABLED", "")
    monkeypatch.setattr(na, "delegation_possible", lambda who: True)
    assert na._analysis_gate("someone") == ""

    monkeypatch.setattr(na, "delegation_possible", lambda who: False)
    reason = na._analysis_gate("someone")
    assert reason, "위임할 곳도 없는데 통과시키면 아무도 못 집는 잡이 쌓인다"
    # 사용자가 **스스로 할 수 있는 일**을 안내한다("운영자에게 문의" 로 끝내지 않는다).
    assert "내 AI 연결" in reason


def test_enqueue_gate_passes_when_server_llm_is_open(monkeypatch):
    """게이트를 되돌린 운영(`AGENT_SERVER_LLM_ENABLED=1`)에서는 러너를 묻지도 않는다."""
    from modules import node_analysis as na

    monkeypatch.setenv("AGENT_SERVER_LLM_ENABLED", "1")

    def _boom(_who):
        raise AssertionError("게이트가 열렸는데 러너를 조회했다")

    monkeypatch.setattr(na, "delegation_possible", _boom)
    assert na._analysis_gate("someone") == ""


# ── 4. 반영: 늦은 답이 최신 값을 덮지 않는다 ────────────────────────────────────


class _FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)
        self.executed: list = []
        self._last = None

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))
        if sql.lstrip().upper().startswith("SELECT"):
            self._last = self._rows.pop(0) if self._rows else None

    def fetchone(self):
        return self._last

    def close(self):
        pass


class _FakeConn:
    def __init__(self, cur):
        self._cur = cur

    def cursor(self):
        return self._cur

    def close(self):
        pass


def test_late_answer_does_not_overwrite_a_finished_job(monkeypatch):
    """lease 회수로 이미 상태가 바뀐 잡에는 **쓰지 않는다**.

    덮어쓰면 사용자가 이미 본 최신 분석이 낡은 답으로 되돌아간다. 그런데 그것은 실패도
    아니다(제출은 정상이었다) — 그래서 예외를 올리지 않고 조용히 넘긴다.
    """
    from modules import node_analysis as na

    cur = _FakeCursor([("Table", "t", "db.t", "pending")])
    monkeypatch.setattr(na, "_rw_conn", lambda _c: (_FakeConn(cur), True))
    na.apply_external_node_analysis(
        None, {"job_id": 7, "run_id": "r1"}, {"summary": "새 분석"})
    assert not any(sql.startswith("UPDATE node_analysis_jobs SET status='done'")
                   for sql, _ in cur.executed), "이미 지나간 잡을 덮어썼다"


def test_apply_requires_a_target_row():
    """어디에 쓸지 모르면 **예외로 올린다** — 조용한 성공은 값 없는 '완료' 를 만든다."""
    from modules import node_analysis as na

    with pytest.raises(ValueError):
        na.apply_external_node_analysis(None, {}, {"summary": "x"})
    with pytest.raises(ValueError):
        na.apply_external_node_analysis(None, {"job_id": 1, "run_id": "r"}, "문자열")


def test_cluster_label_apply_refuses_an_empty_result():
    """유효한 라벨이 하나도 없으면 성공으로 접지 않는다 — 다음 pass 가 같은 작업을 또 산다."""
    from modules import semantic_cluster as sc

    with pytest.raises(ValueError):
        sc.apply_external_cluster_labels(
            None, {"entries": [{"idx": 0, "kv_key": "k"}]}, {"labels": []})


def test_insight_apply_requires_kv_key():
    from modules import insight as ins

    with pytest.raises(ValueError):
        ins.apply_external_insight_summary(None, {}, {"summary": "x"})


# ── 5. 중복: 결과가 오기 전에 같은 작업을 다시 사지 않는다 ──────────────────────


def test_batch_delegation_call_sites_pass_a_dedupe_key():
    """배경 배치 적재는 **반드시** `dedupe_key` 를 건다.

    걸지 않으면 결과가 돌아오기 전까지 매 pass 같은 작업을 다시 적재하고, 그 중복은 전부
    실제로 개인 AI 가 처리한다 — 같은 답을 사용자 계정 토큰으로 여러 번 사는 것이다.
    대기열 상한은 폭주만 막을 뿐 중복 자체를 막지 못한다.
    """
    for rel, func in (("modules/semantic_cluster.py", "_delegate_cluster_labels"),
                      ("modules/insight.py", "_delegate_table_insight")):
        tree = ast.parse((_CORE / rel).read_text(encoding="utf-8"))
        found = False
        for node in ast.walk(tree):
            if not (isinstance(node, ast.FunctionDef) and node.name == func):
                continue
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call)
                        and getattr(sub.func, "attr", "") == "enqueue_console_job"):
                    kws = {k.arg for k in sub.keywords}
                    assert "dedupe_key" in kws, f"{rel}:{func} 적재에 dedupe_key 가 없다"
                    found = True
        assert found, f"{rel}:{func} 에서 적재 호출을 찾지 못했다"


def test_dedupe_key_is_stored_where_it_is_looked_up():
    """조회 대상과 저장 대상이 **같은 값**이다 — 따로 두면 중복이 조용히 돌아온다."""
    src = (_REPO / "shared" / "bridge_tasks.py").read_text(encoding="utf-8")
    assert "$.dedupe_key" in src
    assert '"dedupe_key": str(dedupe_key)' in src


# ── 6. 배급 자격 판정이 웹과 워커에서 하나다 ────────────────────────────────────


def test_runner_eligibility_has_a_single_source():
    """웹(`_console_llm`)과 워커(`node_analysis`)가 **같은 판정 함수**를 쓴다.

    두 벌이면 로그아웃한 세션의 러너를 워커만 자격 있다고 보는 창이 열리고, 그 창에서
    적재된 작업은 아무도 집지 않는다(유령 작업).
    """
    web = (_WEB / "routers" / "_console_llm.py").read_text(encoding="utf-8")
    assert "runner_can_take" in web
    assert "runner_can_take" in _calls_in("modules/node_analysis.py", "_delegation_ready")
    # 술어·질의도 shared 하나다.
    assert callable(bt.runner_profile_for_account)
    assert "t.LastHeartbeatAt" in bt.LIVE_TOKEN_PREDICATE or "TokenType" in bt.LIVE_TOKEN_PREDICATE


def test_web_console_only_offers_operator_initiated_kinds():
    """화면이 「맡길 수 있다」고 말하는 목록에 **배경 배치가 섞이지 않는다**.

    배경 배치는 `batch_jobs` 별도 동의를 요구하는데 그 판정은 이 목록을 만들 때 하지 않는다.
    섞으면 화면은 자격을 확인하지 않은 것까지 가능하다고 말한다.
    """
    web = (_WEB / "routers" / "_console_llm.py").read_text(encoding="utf-8")
    tree = ast.parse(web)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "delegable_job_kinds":
            body = ast.dump(node)
            assert "ORIGIN_WEB" in body, "origin 필터가 없다 — 배경 배치가 목록에 샌다"
            break
    else:
        raise AssertionError("delegable_job_kinds 를 찾지 못했다")
