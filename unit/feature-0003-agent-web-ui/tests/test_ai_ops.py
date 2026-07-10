"""TASK-AIOPS — AI 운영 관제 패널 (관리 콘솔 > 감사 > AI 운영 현황) 회귀/보안 테스트.

검증 대상(`make test` agent 이미지, DB 없이 monkeypatch/fake 로 실행):
  T1  taxonomy self-surface — 등록 task 는 카테고리 매핑, 미등록/오타/None 은 ai.other.unmapped.
  T2  상태 축 임계 — ask-worker age 밴드(정상/저하/중단) + inprocess N/A(롤업 제외).
  T3  datasource 축 매핑 — ok/unstable/circuit_open → 정상/저하/중단 worst-of.
  T4  worst-of 배너 + PG 미가용 부분 degrade(200 유지, pg_available=False, banner=축 기반).
  T5  PG 가용(빈 결과) — 배너 정상, categories 빈, ask-worker na 롤업 제외.
  A1  권한 — console.aiops.read 없으면 403(TestClient require_permission).
  R1  _record_llm_usage latency_ms — 미전달=NULL(agent-core 11경로 byte-동치), 명시값 전달.
  R2  usage 없음(스트리밍 include_usage 미지원 등) → INSERT 미실행(정직 스킵).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import app
from routers import ai_ops
from shared.model_catalog import taxonomy_for, ai_categories, TASK_TAXONOMY


class _FakeRequest:
    def __init__(self, days=None):
        self.query_params = {} if days is None else {"days": str(days)}


def _body(resp):
    return json.loads(resp.body)


# ── T1: taxonomy self-surface ────────────────────────────────────────────────
def test_taxonomy_known_tasks_map_to_categories():
    assert taxonomy_for("agent")["category"] == "ai.reasoning.agent"
    assert taxonomy_for("prompt_gen")["category"] == "ai.prompt.autogen"
    assert taxonomy_for("metadata_summary")["category"] == "ai.metadata.autocomplete"
    # 라벨 보존
    assert taxonomy_for("node_analysis")["label"] == "그래프 노드 분석"
    # 등록된 모든 task 의 category 는 ai_categories() 라벨맵에 존재(고아 카테고리 없음)
    labels = ai_categories()
    for t, meta in TASK_TAXONOMY.items():
        assert meta["category"] in labels, f"{t} 의 category 가 라벨맵에 없음"


def test_taxonomy_unmapped_self_surface():
    # 미등록/오타/None/공백 → ai.other.unmapped, 원본 task 라벨 보존(운영자 식별용)
    assert taxonomy_for("brand_new_ai_task")["category"] == "ai.other.unmapped"
    assert taxonomy_for("brand_new_ai_task")["label"] == "brand_new_ai_task"
    assert taxonomy_for(None)["category"] == "ai.other.unmapped"
    assert taxonomy_for("")["category"] == "ai.other.unmapped"


# ── T2: ask-worker 축 임계 + inprocess N/A ───────────────────────────────────
def test_ask_worker_axis_inprocess_is_na(monkeypatch):
    monkeypatch.setattr(app, "_is_worker_mode", lambda: False)
    ax = ai_ops._ask_worker_axis(conn=None)
    assert ax["state"] == "na", "inprocess 모드는 N/A 여야 함(롤업 제외)"


def test_ask_worker_axis_age_bands(monkeypatch):
    monkeypatch.setattr(app, "_is_worker_mode", lambda: True)
    monkeypatch.setattr(app, "_ask_worker_age_sec", lambda conn: 10)
    assert ai_ops._ask_worker_axis(None)["state"] == "ok"
    monkeypatch.setattr(app, "_ask_worker_age_sec", lambda conn: 90)
    assert ai_ops._ask_worker_axis(None)["state"] == "degraded"
    monkeypatch.setattr(app, "_ask_worker_age_sec", lambda conn: 300)
    assert ai_ops._ask_worker_axis(None)["state"] == "down"
    monkeypatch.setattr(app, "_ask_worker_age_sec", lambda conn: None)
    assert ai_ops._ask_worker_axis(None)["state"] == "down", "heartbeat 부재 → 중단"


# ── T3: datasource 축 매핑 ───────────────────────────────────────────────────
def test_datasource_axis_worst_of(monkeypatch):
    monkeypatch.setattr(app, "_read_insight_datasource_health", lambda: {
        "ds_ok": {"status": "ok", "scan_outcome": "ok"},
        "ds_bad": {"status": "unstable", "scan_outcome": "error"},
    })
    assert ai_ops._datasource_axis()["state"] == "degraded"
    monkeypatch.setattr(app, "_read_insight_datasource_health", lambda: {
        "ds_ok": {"status": "ok", "scan_outcome": "ok"},
        "ds_dead": {"status": "ok", "scan_outcome": "circuit_open"},
    })
    assert ai_ops._datasource_axis()["state"] == "down"
    monkeypatch.setattr(app, "_read_insight_datasource_health", lambda: {})
    assert ai_ops._datasource_axis()["state"] == "unknown", "스캔 이력 없음/PG 미가용 → unknown"


# ── 공용: 축 소스 monkeypatch (건강한 기본값) ────────────────────────────────
def _patch_axes_healthy(monkeypatch, *, worker_mode=False):
    monkeypatch.setattr(app, "_read_llm_provider_status", lambda: {"state": "ok"})
    monkeypatch.setattr(app, "_is_worker_mode", lambda: worker_mode)
    monkeypatch.setattr(app, "_ask_worker_age_sec", lambda conn: 5)
    monkeypatch.setattr(app, "_insight_worker_liveness", lambda conn: {"alive": True, "age_sec": 5, "status": "ok"})
    monkeypatch.setattr(app, "_read_insight_datasource_health", lambda: {"ds": {"status": "ok", "scan_outcome": "ok"}})


# ── T4: PG 미가용 → 부분 degrade(200) ────────────────────────────────────────
def test_handler_pg_unavailable_partial_degrade(monkeypatch):
    _patch_axes_healthy(monkeypatch, worker_mode=False)  # inprocess → ask-worker na

    def _boom(*a, **k):
        raise RuntimeError("pg down")

    monkeypatch.setattr("shared.db._pg_connect_ro", _boom, raising=False)
    body = _body(ai_ops.admin_ai_ops(_FakeRequest(7), account={"id": 1}, conn=None))

    assert body["pg_available"] is False
    assert body["categories"] == []
    # provider ok + insight ok + datasource ok, ask-worker na 제외 → 배너 정상
    assert body["banner"]["state"] == "ok"
    ask = next(a for a in body["axes"] if a["key"] == "ask_worker")
    assert ask["state"] == "na"
    # PG 미가용은 Attention 에 표면화(은폐 금지)
    assert any("PG" in x["label"] or "미가용" in x["label"] for x in body["attention"])


# ── T5: PG 가용(빈 결과) → 배너 정상, categories 빈 ──────────────────────────
class _EmptyCur:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None): return None
    def fetchall(self): return []
    def fetchone(self): return None
    def close(self): return None


class _EmptyConn:
    def cursor(self, *a, **k): return _EmptyCur()
    def close(self): return None


def test_handler_pg_available_empty(monkeypatch):
    _patch_axes_healthy(monkeypatch, worker_mode=True)  # worker mode + age 5 → ask ok
    monkeypatch.setattr("shared.db._pg_connect_ro", lambda *a, **k: _EmptyConn(), raising=False)
    body = _body(ai_ops.admin_ai_ops(_FakeRequest(7), account={"id": 1}, conn=None))

    assert body["pg_available"] is True
    assert body["categories"] == []
    assert body["banner"]["state"] == "ok"
    # worker mode + 정상 age → ask-worker ok(롤업 포함)
    ask = next(a for a in body["axes"] if a["key"] == "ask_worker")
    assert ask["state"] == "ok"
    assert body["kpis"]["workers_total"] == 2  # ask + insight 둘 다 롤업 대상


# ── A1: 권한 403 (TestClient require_permission) ─────────────────────────────
def test_ai_ops_requires_permission(client, as_account):
    as_account(perms={"console.access": True})  # console.aiops.read 없음
    resp = client.get("/api/admin/ai-ops")
    assert resp.status_code == 403


# ── R1/R2: _record_llm_usage latency_ms (byte-동치 NULL + 명시값 + usage 스킵) ─
class _CaptureCur:
    def __init__(self, sink): self.sink = sink
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None): self.sink.append((sql, params))


class _CaptureConn:
    def __init__(self, sink): self.sink = sink
    def cursor(self, *a, **k): return _CaptureCur(self.sink)
    def commit(self): return None
    def close(self): return None


def _resp(pt=10, ct=5, tt=15, model="claude-haiku-4"):
    return SimpleNamespace(usage=SimpleNamespace(prompt_tokens=pt, completion_tokens=ct, total_tokens=tt), model=model)


def test_record_llm_usage_latency_column(monkeypatch):
    import modules.llm as llm
    import modules.runtime_backend as rb
    sink: list = []
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: _CaptureConn(sink))

    # 미전달 → latency_ms=NULL 및 step_gap_ms=NULL (미측정=NULL). 0033: 컬럼 순서 (…, target,
    #   latency_ms, step_gap_ms) — latency=params[-2], step_gap=params[-1] (신규 컬럼 맨 끝 additive).
    llm._record_llm_usage("claude-haiku-4", "agent", _resp())
    assert len(sink) == 1
    sql, params = sink[0]
    assert "latency_ms" in sql and "step_gap_ms" in sql
    assert params[-2] is None, "latency 미전달 시 NULL"
    assert params[-1] is None, "step_gap 미전달 시 NULL"

    # 명시값 → 그대로 전달 (latency=params[-2], step_gap=params[-1])
    sink.clear()
    llm._record_llm_usage("claude-haiku-4", "agent", _resp(), latency_ms=123, step_gap_ms=1300)
    assert sink[0][1][-2] == 123    # latency_ms(전체 왕복)
    assert sink[0][1][-1] == 1300   # step_gap_ms(단계 간 간격)


def test_record_llm_usage_skips_without_usage(monkeypatch):
    import modules.llm as llm
    import modules.runtime_backend as rb
    sink: list = []
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: _CaptureConn(sink))
    # usage 없음(스트리밍 include_usage 미지원 등) → INSERT 미실행(정직 스킵)
    llm._record_llm_usage("m", "prompt_gen", SimpleNamespace(usage=None, model="m"), latency_ms=50)
    assert sink == []


class _ColAbsentCur:
    """지정 컬럼이 스키마에 없다고 시뮬레이션 — 그 컬럼명을 포함한 INSERT 는 매번 예외(0033 3단 cascade 검증)."""
    def __init__(self, sink, absent_col): self.sink = sink; self.absent = absent_col
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None):
        if self.absent in sql:
            raise RuntimeError(f'column "{self.absent}" does not exist')
        self.sink.append((sql, params))


class _ColAbsentConn:
    def __init__(self, sink, absent_col):
        self.sink = sink; self.rolled_back = 0; self._cur = _ColAbsentCur(sink, absent_col)
    def cursor(self, *a, **k): return self._cur
    def commit(self): return None
    def rollback(self): self.rolled_back += 1
    def close(self): return None


def test_record_llm_usage_step_gap_column_absent_fallback(monkeypatch):
    # 0033: step_gap_ms 컬럼 부재(0033 미적용, 0032 target 은 적용 — agent image stale 등) →
    # step_gap 포함 INSERT 실패 → rollback → (target, latency_ms) 로 폴백해 usage 행 보존.
    import modules.llm as llm
    import modules.runtime_backend as rb
    sink: list = []
    conn = _ColAbsentConn(sink, "step_gap_ms")
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: conn)
    llm._record_llm_usage("claude-haiku-4", "agent", _resp(),
                          target="public.users", latency_ms=42, step_gap_ms=1300)
    assert conn.rolled_back == 1              # step_gap 포함 INSERT 1회 실패 → rollback
    assert len(sink) == 1
    sql, params = sink[0]
    assert "step_gap_ms" not in sql and "target" in sql   # 폴백 = (…, target, latency_ms)
    assert params[-1] == 42                    # latency 마지막(step_gap 없는 폴백)


def test_record_llm_usage_target_column_absent_fallback(monkeypatch):
    # 0032: target 컬럼 부재(마이그 미적용) → target 포함 INSERT 전부(step_gap·target 2단) 실패 →
    # 최소 base(latency) 로 폴백해 usage 행 보존(계측 무중단).
    import modules.llm as llm
    import modules.runtime_backend as rb
    sink: list = []
    conn = _ColAbsentConn(sink, "target")
    monkeypatch.setattr(rb, "_get_pg_runtime_conn", lambda: conn)
    llm._record_llm_usage("claude-haiku-4", "table_insight", _resp(),
                          target="public.users", latency_ms=42, step_gap_ms=1300)
    assert conn.rolled_back == 2              # step_gap-포함 + target-포함 INSERT 2회 실패
    assert len(sink) == 1
    sql, params = sink[0]
    assert "target" not in sql and "step_gap_ms" not in sql   # 폴백 = base 컬럼
    assert params[4] == "table_insight"       # task 보존
    assert params[-1] == 42                    # latency 마지막 위치 보존


# ── 활동 feed 페이징(TASK-AIOPS-paging): cursor keyset + next_cursor + 엔드포인트 degrade/권한 ─
import datetime as _dt


def _act_rows(n, start_id):
    # TASK-20260702-audit-nav-ux: SELECT 컬럼 확장 반영 —
    # (id, task, model, resolved_model, total, prompt, completion, latency, created_at, run_id, conversation_id)
    # conversation_id 는 짝수 index 만 부여(연결 대화 있음/없음 두 경로 모두 커버).
    # 0032(TASK-20260703-aiops-target): 12번째 컬럼 target 추가 — 짝수 index 만 대상 부여(대상 있음/없음 두 경로).
    return [(start_id - i, "agent", "claude-haiku-4", "claude-haiku-4-served", 100, 60, 40, 12,
             _dt.datetime(2026, 7, 2, 0, 0, i % 60),
             "run-" + str(start_id - i), ("conv-" + str(start_id - i)) if (i % 2 == 0) else None,
             ("public.tbl_" + str(start_id - i)) if (i % 2 == 0) else None)
            for i in range(n)]


class _PlainCur:
    def __init__(self, rows): self._rows = rows; self.sql = None; self.params = None
    def execute(self, sql, params=None): self.sql = sql; self.params = params
    def fetchall(self): return self._rows


class _CtxCur(_PlainCur):
    def __enter__(self): return self
    def __exit__(self, *a): return False


class _RowConn:
    def __init__(self, rows): self._cur = _CtxCur(rows)
    def cursor(self, *a, **k): return self._cur
    def close(self): return None


class _ReqQ:
    def __init__(self, **params): self.query_params = {k: str(v) for k, v in params.items()}


def test_query_activity_no_cursor_has_more():
    from routers.ai_ops import _query_activity
    cur = _PlainCur(_act_rows(4, 100))  # limit=3, 4 rows → has_more
    items, nxt = _query_activity(cur, taxonomy_for, limit=3)
    assert len(items) == 3
    assert nxt == items[-1]["id"]                  # has_more → next_cursor = 마지막 id
    assert {"id", "latency_ms", "cost_usd", "label"} <= set(items[0].keys())
    # TASK-20260702-audit-nav-ux: 상세 확장용 additive 필드 노출 + 서빙/요청 모델 분리.
    assert {"req_model", "resolved_model", "prompt_tokens", "completion_tokens",
            "run_id", "conversation_id"} <= set(items[0].keys())
    assert items[0]["model"] == "claude-haiku-4-served"     # 행 표시=서빙(resolved) 우선
    assert items[0]["req_model"] == "claude-haiku-4"        # 요청 별칭 별도 보존
    assert items[0]["prompt_tokens"] == 60 and items[0]["completion_tokens"] == 40
    assert items[0]["run_id"] == "run-100" and items[0]["conversation_id"] == "conv-100"
    assert items[1]["conversation_id"] is None              # 홀수 index=대화 미귀속(정직 안내 경로)
    # 0032: 인사이트 분석 대상(target) 컬럼이 SELECT 되고 item 으로 통과 — 짝수=대상 있음, 홀수=None.
    assert ", target" in cur.sql
    assert items[0]["target"] == "public.tbl_100"
    assert items[1]["target"] is None
    assert "WHERE id <" not in cur.sql             # cursor 미지정 → WHERE 없음
    assert "ORDER BY id DESC" in cur.sql


def test_query_activity_with_cursor_no_more():
    from routers.ai_ops import _query_activity
    cur = _PlainCur(_act_rows(3, 50))              # limit=3, 3 rows → no has_more
    items, nxt = _query_activity(cur, taxonomy_for, cursor=97, limit=3)
    assert len(items) == 3 and nxt is None
    assert "WHERE id < %s" in cur.sql
    assert cur.params[0] == 97 and cur.params[1] == 4   # (cursor, limit+1)


class _NoTargetCur(_PlainCur):
    """0032: target 컬럼 부재(마이그 미적용/agent image stale) 시뮬레이션 —
    SELECT 에 ', target' 포함 첫 실행은 UndefinedColumn 흉내로 예외, 재실행(base 컬럼)은 통과.
    _query_activity 의 자가치유 폴백(rollback → base 컬럼 재조회)을 검증한다."""
    def __init__(self, rows):
        super().__init__(rows)
        self.connection = self       # cur.connection.rollback() 대상
        self._raised = False
    def execute(self, sql, params=None):
        if ", target" in sql and not self._raised:
            self._raised = True
            raise RuntimeError('column "target" does not exist')
        super().execute(sql, params)
    def rollback(self):
        return None


def test_query_activity_target_column_absent_fallback():
    from routers.ai_ops import _query_activity
    cur = _NoTargetCur(_act_rows(3, 80))           # rows 는 target 포함이나 SELECT 는 폴백돼야 함
    items, nxt = _query_activity(cur, taxonomy_for, limit=3)
    assert len(items) == 3                         # 폴백해도 피드는 살아있음(usage 계측 무중단)
    assert all(it["target"] is None for it in items)   # target 컬럼 부재 → 전부 None(가드)
    assert ", target" not in cur.sql               # 최종 실행 SQL = base 컬럼(폴백 성공)


def test_activity_endpoint_with_data(monkeypatch):
    monkeypatch.setattr("shared.db._pg_connect_ro", lambda *a, **k: _RowConn(_act_rows(4, 200)), raising=False)
    body = _body(ai_ops.admin_ai_ops_activity(_ReqQ(limit=3, cursor=500), account={"id": 1}, conn=None))
    assert body["pg_available"] is True
    assert len(body["items"]) == 3
    assert body["next_cursor"] == body["items"][-1]["id"]


def test_activity_endpoint_pg_degrade(monkeypatch):
    def _boom(*a, **k): raise RuntimeError("pg down")
    monkeypatch.setattr("shared.db._pg_connect_ro", _boom, raising=False)
    body = _body(ai_ops.admin_ai_ops_activity(_ReqQ(), account={"id": 1}, conn=None))
    assert body["pg_available"] is False and body["items"] == [] and body["next_cursor"] is None


def test_activity_endpoint_requires_permission(client, as_account):
    as_account(perms={"console.access": True})  # console.aiops.read 없음
    resp = client.get("/api/admin/ai-ops/activity")
    assert resp.status_code == 403
