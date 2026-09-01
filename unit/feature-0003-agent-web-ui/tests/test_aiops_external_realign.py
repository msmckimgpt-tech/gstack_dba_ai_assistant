"""feature-0043 TASK-20260901T110000 — 'AI 운영 현황' 을 외부AI 운영축으로 재편.

## 무엇이 문제였나

서버 계정 LLM 이 차단된 뒤 이 탭의 거의 모든 수치가 `agent_runtime.llm_usage` 를 출처로
삼고 있었다. 그 원장에는 새 행이 쌓이지 않으므로 화면이 0 으로 수렴했고, 그 0 은
**"아무도 AI 를 안 쓴다"** 로 읽혔다 — 실제로는 우리가 세지 않는 곳(각자의 개인 AI)에서
쓰고 있었고, 우리 쪽에 남는 활동은 도구 호출과 브리지 작업이었다.

`LLM 제공자` 축은 더 나빴다. 아무도 그 경로를 쓰지 않는데 그 축의 `degraded` 가 종합 배너의
worst-of 에 참여해, **쓰지 않는 provider 의 제한 하나가 화면 전체를 '저하' 로 물들이고**
운영자가 실제로 봐야 할 브리지 신호를 같은 색으로 덮었다.

## 이 스위트가 잠그는 것

| 축 | 계약 |
|---|---|
| 롤업 | 차단 배포에서 provider 축은 `na`(롤업 제외) — 다만 원본 상태는 계속 실린다 |
| 커버리지 | 차단 배포는 **하지 않는 일**을 '계측됨' 으로 나열하지 않는다 |
| 러너 명부 | 계정별 상태를 준다(수만으로는 "왜 안 되나" 에 답할 수 없다) |
| 자가 검증 | 원장 미준비(`available:false`)와 0건을 **가르고**, 서버 이력과 합산하지 않는다 |
| 도구 사용량 | 질의 하나가 실패해도 나머지가 남는다(부분 degrade) |
| 작업 원장 | 목록에 답변 **본문을 싣지 않는다**(각인 블록 유출 방지) |
| 서브탭 | 재편된 4탭 + 옛 deep-link 가 빈 pane 에 착지하지 않는다 |
"""
from __future__ import annotations

import json
import pathlib
import re

import app
from routers import ai_ops

_WEB = pathlib.Path(__file__).resolve().parents[1] / "src"
ADMIN_HTML = _WEB / "static" / "admin.html"
ADMIN_JS = _WEB / "static" / "admin.js"
AIOPS_JS = _WEB / "static" / "admin" / "aiops.js"
TASKS_JS = _WEB / "static" / "admin" / "tasks.js"
TOOLS_JS = _WEB / "static" / "admin" / "tools.js"


class _FakeRequest:
    def __init__(self, **params):
        self.query_params = {k: str(v) for k, v in params.items() if v is not None}


def _body(resp):
    return json.loads(resp.body)


def _patch_axes(monkeypatch, *, blocked: bool, provider_state="ok"):
    monkeypatch.setattr(app, "_read_llm_provider_status", lambda: {"state": provider_state})
    monkeypatch.setattr(app, "_read_llm_provider_status_admin",
                        lambda: {"state": provider_state, "server_llm_blocked": blocked})
    monkeypatch.setattr(app, "_is_worker_mode", lambda: False)
    monkeypatch.setattr(app, "_insight_worker_liveness",
                        lambda conn: {"alive": True, "age_sec": 5, "status": "ok"})
    monkeypatch.setattr(app, "_read_insight_datasource_health",
                        lambda: {"ds": {"status": "ok", "scan_outcome": "ok"}})
    monkeypatch.setattr("shared.llm_gate.server_llm_enabled", lambda: not blocked, raising=False)


def _no_pg(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("pg down")
    monkeypatch.setattr("shared.db._pg_connect_ro", _boom, raising=False)


# ── ① provider 축 — 쓰지 않는 축이 배너를 물들이지 않는다 ────────────────────


def test_blocked_provider_axis_leaves_the_rollup(monkeypatch):
    """차단 배포에서 provider 가 `degraded` 여도 **종합 상태는 물들지 않는다**.

    아무도 그 경로를 쓰지 않으므로 서비스에 아무 일도 일어나지 않는다 — 그런데 종전에는
    그 색이 브리지 신호를 덮었다.
    """
    _patch_axes(monkeypatch, blocked=True, provider_state="restricted")
    _no_pg(monkeypatch)
    body = _body(ai_ops.admin_ai_ops(_FakeRequest(days=7), account={"id": 1}, conn=None))
    prov = next(a for a in body["axes"] if a["key"] == "provider")
    assert prov["state"] == "na", "차단 중인데 롤업에 참여한다"
    # **감추지는 않는다** — 게이트를 되돌리는 날 되살아날 제한이라 원본은 계속 보인다.
    assert prov["raw_state"] == "degraded"
    assert prov["server_llm_blocked"] is True
    assert body["server_llm_blocked"] is True


def test_open_gate_provider_axis_still_counts(monkeypatch):
    """게이트가 열린 배포에서는 종전 그대로 — 이 변경이 정상 운영의 관제를 무르게 하지 않는다."""
    _patch_axes(monkeypatch, blocked=False, provider_state="restricted")
    _no_pg(monkeypatch)
    body = _body(ai_ops.admin_ai_ops(_FakeRequest(days=7), account={"id": 1}, conn=None))
    prov = next(a for a in body["axes"] if a["key"] == "provider")
    assert prov["state"] == "degraded"
    assert body["banner"]["state"] == "degraded"
    assert body["server_llm_blocked"] is False


# ── ② 커버리지 — 하지 않는 일을 '계측됨' 으로 나열하지 않는다 ────────────────


def test_coverage_switches_with_the_gate(monkeypatch):
    """커버리지 표의 목적은 정직 노출이다 — 그 자리에서 거짓을 말하면 표 자체가 무의미하다."""
    _no_pg(monkeypatch)
    _patch_axes(monkeypatch, blocked=True)
    blocked = _body(ai_ops.admin_ai_ops(_FakeRequest(days=7), account={"id": 1}, conn=None))
    joined = " ".join(blocked["coverage"]["instrumented"])
    assert "에이전트 추론" not in joined, "서버가 하지 않는 일을 '계측됨' 으로 나열했다"
    assert "도구 호출" in joined and "브리지 작업" in joined
    # 토큰·비용이 0 인 것이 아니라 **우리가 세는 축이 아님**을 말해야 한다.
    assert "0 이 아니라" in blocked["coverage"]["note"]

    _patch_axes(monkeypatch, blocked=False)
    opened = _body(ai_ops.admin_ai_ops(_FakeRequest(days=7), account={"id": 1}, conn=None))
    assert "에이전트 추론" in " ".join(opened["coverage"]["instrumented"])


# ── ③ 러너 명부 — 수가 아니라 "누가 왜 못 받는가" ────────────────────────────


class _RosterCur:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        self._sql = " ".join(str(sql).split())

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return None

    def close(self):
        pass


class _RosterConn:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self, *a, **k):
        return _RosterCur(self.rows)

    def close(self):
        pass


def _roster_rows():
    """(AccountId, Username, LastHeartbeatAt, age, Features, Version, Build, Caps)"""
    return [
        (1, "alice", None, 20, "console_jobs,self_review", "2026.09.01", "aaaaaaaaaaaa",
         '[{"runtime":"claude","models":[{"value":"opus"},{"value":"sonnet"}]}]'),
        (2, "bob", None, 9999, "console_jobs", "2026.08.31", "bbbbbbbbbbbb", None),
        (3, "carol", None, 15, "console_jobs", "2026.08.31", "cccccccccccc", None),
    ]


def test_runner_roster_separates_the_four_causes(monkeypatch):
    """네 상태는 **조치가 다르다** — 한 칸으로 합치면 운영자가 무엇을 시켜야 할지 모른다."""
    monkeypatch.setattr("routers.ai_tools._deployed_runner_build", lambda: "aaaaaaaaaaaa",
                        raising=False)
    out = ai_ops._runner_roster(_RosterConn(_roster_rows()))
    assert out["available"] is True
    by = {r["username"]: r for r in out["items"]}
    # ① 수신 중 · 검증 가능 · 배포본과 같은 지문
    assert by["alice"]["listening"] and by["alice"]["self_review_capable"]
    assert by["alice"]["stale_build"] is False
    assert by["alice"]["model_count"] == 2
    # ② 하트비트가 창 밖 — "연결은 했고 지금 프로세스가 없다"
    assert by["bob"]["listening"] is False
    # ③ 수신 중인데 검증 미신고 — 갱신 유도 대상
    assert by["carol"]["listening"] and by["carol"]["self_review_capable"] is False
    # ④ 배포본과 다른 지문
    assert by["carol"]["stale_build"] is True


def test_runner_roster_does_not_guess_stale_when_build_unknown(monkeypatch):
    """지문을 모르면 **대조하지 않는다** — 모르는 것을 stale 로 적으면 멀쩡한 러너에게
    재설치를 시킨다."""
    monkeypatch.setattr("routers.ai_tools._deployed_runner_build", lambda: "", raising=False)
    out = ai_ops._runner_roster(_RosterConn(_roster_rows()))
    assert all(r["stale_build"] is False for r in out["items"])


def test_runner_roster_reports_unavailable_not_empty():
    """DB 가 없으면 「러너 0대」가 아니라 「조회 불가」다 — 전자는 장애 선언이고 후자는 사실이다."""
    out = ai_ops._runner_roster(None)
    assert out["available"] is False and out["items"] == []
    assert out.get("reason")


# ── ④ 자가 검증 집계 — 미준비와 0건을 가른다 ────────────────────────────────


def test_self_review_stats_unavailable_is_not_zero(monkeypatch):
    """컬럼 부재(마이그 대기)를 0 으로 접으면 「검증이 하나도 없다」로 읽힌다 —
    그것은 마이그레이션 상태가 아니라 운영 상태에 대한 거짓말이다."""
    _no_pg(monkeypatch)
    out = ai_ops._self_review_stats(7)
    assert out["available"] is False and out.get("reason")


class _SRCur:
    """첫 질의=요약, 둘째=축별 분포."""
    def __init__(self):
        self.n = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.n += 1
        self._sql = " ".join(str(sql).split())

    def fetchone(self):
        return (10, 7, 3, 4, 5)

    def fetchall(self):
        return [("sql", "BLOCK", 3), ("honesty", "WARN", 5), ("grounding", "BLOCK", 1)]

    def close(self):
        pass


class _SRConn:
    def __init__(self):
        self.cur = _SRCur()

    def cursor(self, *a, **k):
        return self.cur

    def close(self):
        pass


def test_self_review_stats_filters_to_external_only(monkeypatch):
    """서버 이력과 합치면 "검증이 줄고 있다" 는 착시가 생긴다 — 실제로는 주체가 바뀐 것뿐이다."""
    conn = _SRConn()
    monkeypatch.setattr("shared.db._pg_connect_ro", lambda *a, **k: conn, raising=False)
    out = ai_ops._self_review_stats(7)
    assert out["available"] is True
    assert out["reviews"] == 10 and out["revise_count"] == 3
    assert "source = 'external'" in conn.cur._sql, "서버 이력이 섞였다"
    axes = {a["axis"]: a for a in out["by_axis"]}
    assert axes["sql"]["block"] == 3 and axes["honesty"]["warn"] == 5
    # 축 라벨은 서버가 붙인다 — 프론트에 표를 두면 축을 늘리는 날 화면만 낡는다.
    assert axes["sql"]["label"] and axes["sql"]["label"] != "sql"


# ── ⑤ 도구 사용량 — 부분 degrade ────────────────────────────────────────────


def test_tool_usage_pg_unavailable_is_200(monkeypatch):
    """관측 조회가 콘솔을 깨면 본말전도다(같은 파일의 ai-ops 규약 답습)."""
    _no_pg(monkeypatch)
    body = _body(ai_ops.admin_ai_ops_tools(_FakeRequest(days=7), account={"id": 1}))
    assert body["pg_available"] is False
    assert body["by_tool"] == [] and body["totals"] == {}


class _PartialCur:
    """두 번째 질의부터 실패시켜, **하나가 죽어도 나머지가 남는지** 본다."""
    def __init__(self):
        self.n = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.n += 1
        if self.n >= 2:
            raise RuntimeError("column missing")

    def fetchall(self):
        return [(5, 100, 2048, 2, 3, 1)]

    def close(self):
        pass


class _PartialConn:
    def cursor(self, *a, **k):
        return _PartialCur()

    def rollback(self):
        pass

    def close(self):
        pass


def test_tool_usage_one_failing_query_does_not_kill_the_rest(monkeypatch):
    """질의 하나가 실패해도 나머지는 보여 준다 — 실패한 트랜잭션 정리(rollback)가 없으면
    뒤따르는 질의가 전부 25P02 로 죽는다."""
    monkeypatch.setattr("shared.db._pg_connect_ro", lambda *a, **k: _PartialConn(), raising=False)
    monkeypatch.setattr(app, "_connect_memory", lambda: (_ for _ in ()).throw(RuntimeError("no db")),
                        raising=False)
    body = _body(ai_ops.admin_ai_ops_tools(_FakeRequest(days=7), account={"id": 1}))
    assert body["pg_available"] is True
    assert body["totals"]["calls"] == 5, "첫 질의 결과가 사라졌다"
    assert body["by_tool"] == []


def test_tool_usage_days_is_clamped(monkeypatch):
    """범위를 받지 않은 값이 SQL 문자열에 들어간다 — 상한이 없으면 원장 전체를 훑는다."""
    _no_pg(monkeypatch)
    for given, want in ((0, 1), (9999, 90), ("bogus", 7)):
        body = _body(ai_ops.admin_ai_ops_tools(_FakeRequest(days=given), account={"id": 1}))
        assert body["window_days"] == want


# ── ⑥ 작업 원장 — 목록에 본문을 싣지 않는다 ─────────────────────────────────


def test_task_ledger_never_ships_the_answer_body():
    """목록에 답변 본문을 실으면 각인(⟦UNTRUSTED-DATA⟧) 블록이 목록 응답으로 흘러 나가고,
    한 페이지가 수 MB 가 된다. 본문은 상세 엔드포인트만 준다."""
    src = (_WEB / "routers" / "ai_ops.py").read_text(encoding="utf-8")
    handler = src.split("def admin_ai_ops_tasks")[1].split("\ndef ")[0]
    assert "t.Answer IS NOT NULL" in handler, "보존 여부만 봐야 한다"
    assert re.search(r"SELECT[^\"]*\bt\.Answer\b(?!\s+IS)", handler) is None, (
        "본문 컬럼을 SELECT 했다")
    assert "question_head" in handler and "[:160]" in handler, "질문도 머리만 실어야 한다"


def test_task_ledger_separates_owner_and_worker():
    """관리자 작업은 둘이 같지만 배치는 다르다(워커가 열고 아무 러너나 집는다) —
    합치면 "내가 시킨 적 없는 작업이 내 이름으로" 또는 그 반대가 된다."""
    src = (_WEB / "routers" / "ai_ops.py").read_text(encoding="utf-8")
    handler = src.split("def admin_ai_ops_tasks")[1].split("\ndef ")[0]
    assert "owner.Id  = t.AccountId" in handler and "worker.Id = t.ClaimedBy" in handler


def test_task_ledger_filters_are_bound_not_interpolated():
    """필터 값을 문자열로 이어 붙이면 주입면이 되고, allowlist 로 막으면 `bridge_tasks` 가
    종류를 늘리는 날 이 필터만 낡아 새 종류가 조회되지 않는다."""
    src = (_WEB / "routers" / "ai_ops.py").read_text(encoding="utf-8")
    handler = src.split("def admin_ai_ops_tasks")[1].split("\ndef ")[0]
    assert 'where.append(f"t.{col} = %s")' in handler
    assert "params.append(val[:32])" in handler


def test_task_ledger_review_absent_key_is_omitted():
    """붙지 않은 것과 `verdict='pass'` 는 다른 사실이다 — 빈 dict 로 채우면 화면이 그것을
    통과로 그릴 여지가 생긴다."""
    items = [{"task_id": "t1"}, {"task_id": "t2"}]
    ai_ops._attach_reviews(items)      # PG 없음 → 조용히 반환
    assert "review" not in items[0] and "review" not in items[1]


# ── ⑦ 화면 — 서브탭 재편 · deep-link 하위호환 ───────────────────────────────


def test_subtabs_are_the_external_ai_axes():
    html = ADMIN_HTML.read_text(encoding="utf-8")
    keys = re.findall(r'data-ai-subtab="([^"]+)"', html)
    assert keys == ["ops", "tasks", "tools", "archive"], f"서브탭이 재편되지 않았다: {keys}"
    panes = re.findall(r'data-ai-subpane="([^"]+)"', html)
    assert set(panes) == set(keys), f"pane 과 탭이 어긋난다: {panes}"
    # 첫 화면이 '운영 현황' 이어야 한다 — 종전 첫 화면(LLM 사용량)은 이제 늘 0 이다.
    assert 'data-ai-subtab="ops" role="tab"' in html
    assert re.search(r'class="admin-subtab is-active" data-ai-subtab="ops"', html)


def test_archive_holds_the_pre_transition_metrics():
    """전환 이전 지표는 **지우지 않되** 기본 진입에서 뺀다."""
    html = ADMIN_HTML.read_text(encoding="utf-8")
    archive = html.split('data-ai-subpane="archive"')[1].split('</section>')[0]
    for anchor in ("usageSummary", "usageDayChart", "reasoningBody", "archiveActivityBody"):
        assert anchor in archive, f"{anchor} 가 기록 탭 안에 없다"
    assert "전환 이전" in archive, "기록임을 명시하는 라벨이 없다"


def test_legacy_deep_links_do_not_land_on_an_empty_pane():
    """서버·대시보드 위젯이 보내는 옛 키(`usage`/`reasoning`/`exttasks`)를 흡수하지 않으면
    그 deep-link 는 빈 pane 에 착지한다(feature-0021 적대검증 MAJOR#1 과 같은 형태)."""
    js = ADMIN_JS.read_text(encoding="utf-8")
    alias = js.split("_AI_SUBTAB_ALIAS = {")[1].split("};")[0]
    html_keys = set(re.findall(r'data-ai-subtab="([^"]+)"', ADMIN_HTML.read_text(encoding="utf-8")))
    for legacy in ("usage", "reasoning", "exttasks", "ai-ops"):
        m = re.search(rf'"?{re.escape(legacy)}"?\s*:\s*"([^"]+)"', alias)
        assert m, f"옛 키 {legacy} 의 별칭이 없다"
        assert m.group(1) in html_keys, f"{legacy} → {m.group(1)} 는 존재하지 않는 서브탭이다"


def test_subtab_alias_is_used_by_both_entry_points():
    """`switchTab` 만 고치면 그쪽으로 오지 않는 호출부(`usage.js` 의 그래프 네비게이션)가
    조용히 아무것도 하지 않는다."""
    js = ADMIN_JS.read_text(encoding="utf-8")
    activate = js.split("export function activateAiConsoleSubtab")[1].split("\n}")[0]
    assert "_AI_SUBTAB_ALIAS[sub]" in activate, "서브탭 진입점이 별칭 표를 읽지 않는다"


def test_ops_pane_hides_llm_usage_kpis_when_blocked():
    """차단 배포에서 0 인 타일을 맨 앞에 두면 첫인상이 '아무 일도 없는 서비스' 가 된다."""
    js = AIOPS_JS.read_text(encoding="utf-8")
    assert "const serverLlm = data.server_llm_blocked !== true;" in js, (
        "축 순서를 뒤져 판정하면 순서를 바꾸는 날 조용히 뒤집힌다")
    render = js.split("function renderAiOps")[1].split("\n/**")[0]
    assert "serverLlm" in render and "24시간 활동" in render
    # 브리지·자가검증 KPI 가 종전 KPI 보다 **앞**에 온다(순서가 곧 우선순위다).
    assert render.index("bridgeKpis(") < render.index('kpi("워커 정상"')
    assert render.index("selfReviewKpi(") < render.index('kpi("워커 정상"')


def test_server_activity_renderer_is_shared_by_both_places():
    """게이트가 열린 배포는 '운영 현황' 이, 닫힌 배포는 '기록' 이 그린다 — 두 벌로 두면
    사람이 잘 가지 않는 '기록' 쪽이 먼저 낡고 아무도 눈치채지 못한다."""
    js = AIOPS_JS.read_text(encoding="utf-8")
    assert js.count("serverActivityHtml(") >= 3, "정의 1 + 호출 2(운영 현황·기록)"
    assert "export async function loadArchiveServerActivity" in js


def test_tools_pane_counts_calls_not_tokens():
    """이 화면이 존재하는 이유가 그것이다 — 토큰 축은 외부AI 트래픽에 대해 항상 0 이다."""
    js = TOOLS_JS.read_text(encoding="utf-8")
    assert "/api/admin/ai-ops/tools" in js
    for word in ("호출", "행수", "바이트"):
        assert word in js
    assert "토큰" in js and "잡히지 않습니다" in js, "토큰이 왜 없는지 화면이 말해야 한다"


def test_task_pane_distinguishes_missing_review_from_pass():
    """검증하지 않은 답변을 '통과' 로 그리면, 이 축을 만든 이유를 화면에서 되풀이하게 된다."""
    js = TASKS_JS.read_text(encoding="utf-8")
    fn = js.split("function reviewCell")[1].split("\nfunction ")[0]
    assert "if (!rv)" in fn and "—" in fn, "검증 없음을 별도 상태로 그리지 않는다"
    assert '"통과"' in fn
