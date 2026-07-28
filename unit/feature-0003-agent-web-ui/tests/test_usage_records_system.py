"""usage-records-system(2026-07-28) — '사용 기록' 목록의 시스템·자율 사용분 편입.

배경: 차트 클릭 드릴다운이 대화 귀속분(INNER JOIN core_conversations + owner NOT NULL)만
보여줘, 라이브 실측 기준 전체 토큰의 약 49%(insight 워커 노드/테이블 분석, 콘텐츠 그룹 라벨,
ask 워커 용어/ENUM 후보 등)가 목록에서 사라졌다. "(시스템)" 역할 클릭은 빈 목록이었다.

검증 대상(`make test` agent 이미지, DB 없이 fake cursor/monkeypatch):
  S1  여집합 정의 — 시스템 질의 WHERE 가 (매칭 대화 없음 OR owner NULL) 를 강제해 대화 목록
      (joinable AND owner NOT NULL)과 정확히 상보. 누락·중복 계상 없음.
  S2  (task, target, actor) fold — 같은 키의 여러 모델 행이 calls/tokens/cost 로 합산되고
      models[] 분해가 보존된다. task_label 은 taxonomy 로 한글화.
  S3  차원 필터 정합 — model(canonical family)·day_label 이 대화 목록과 동일 규칙으로 WHERE 에
      들어간다(같은 막대 클릭 시 두 목록의 합 = 막대 수치).
  S4  target 파싱 — schema / schema.table / schema.table.column / schema.routine() 4형식.
  S5  데이터소스 해소 — 후보 1개면 scope_key 확정, 2개 이상이면 scope_ambiguous(추측 금지),
      0개면 둘 다 비움. 해소 질의 실패는 목록을 깨뜨리지 않는다(fail-soft).
  S6  nav 서술자 — task→화면 SSOT(USAGE_TASK_NAV) 반영, 미등록 task 는 AI 운영 현황 폴백.
  N1  핸들러 라우팅 — 모델/일자 클릭은 대화+시스템, "(시스템)" 역할은 시스템만,
      계정/일반 역할 클릭은 시스템 제외(귀속 오도 방지).
  N2  시스템 질의 실패가 대화 목록(기존 기능)을 깨뜨리지 않는다(부분 저하).
  T1  taxonomy — 라이브에 존재하던 미등록 4 task 가 편입되어 사람이 읽는 라벨을 갖는다.
"""
from __future__ import annotations

import json

import app
from routers import admin_usage
from shared.model_catalog import (
    USAGE_TASK_NAV,
    canonical_usage_model_sql,
    taxonomy_for,
    usage_nav_path_label,
    usage_task_nav,
)


class _FakeDt:
    """isoformat() + 비교 지원(실제 timestamptz 처럼 max()/'>' 동작)."""
    def __init__(self, s):
        self._s = s

    def isoformat(self):
        return self._s

    def __gt__(self, other):
        return self._s > getattr(other, "_s", other)

    def __eq__(self, other):
        return self._s == getattr(other, "_s", other)

    def __hash__(self):
        return hash(self._s)


class _FakeCursor:
    """실행된 (sql, params) 를 sink 에 기록하고, 질의 차수별 rows 를 돌려준다.

    시스템 기록 경로는 [0] 집계 질의 → [1] 데이터소스 해소 질의 순으로 2회 실행되므로
    rows_seq 로 차수별 응답을 지정한다(단일 리스트를 주면 첫 질의에만 쓰고 이후는 빈 결과).
    """
    def __init__(self, rows_seq, sink):
        self._rows_seq = rows_seq
        self._sink = sink
        self._cur = []

    def execute(self, sql, params=None):
        idx = len(self._sink)
        self._sink.append((sql, params))
        self._cur = self._rows_seq[idx] if idx < len(self._rows_seq) else []

    def fetchall(self):
        return self._cur

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        return None


class _FakePG:
    def __init__(self, rows_seq, sink):
        self._rows_seq = rows_seq
        self._sink = sink
        self.rolled_back = False

    def cursor(self, *a, **k):
        return _FakeCursor(self._rows_seq, self._sink)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        return None


def _sys_row(task, target, actor, model, calls, tok, pt, ct, last="2026-07-20T10:00:00Z",
             conv_exists=False):
    # 컬럼 순서: task, target, actor(conversation_id), m, calls, tok, pt, ct, last_used, conv_exists
    return (task, target, actor, model, calls, tok, pt, ct, _FakeDt(last), conv_exists)


# ── S1: 여집합 정의(대화 목록과 상보) ─────────────────────────────────────────

def test_s1_complement_of_conversation_list():
    sink = []
    app._query_usage_system_records(_FakePG([[]], sink), days=30, model=None,
                                    day_label=None, gran="day")
    sql, params = sink[0]
    # 대화 목록이 쓰는 INNER JOIN 대신 LEFT JOIN + '대화 없음 OR owner NULL' 여집합.
    assert "LEFT JOIN agent_runtime.core_conversations" in sql
    assert "(c.conversation_id IS NULL OR c.owner_account_id IS NULL)" in sql
    # 대화 목록의 필터를 그대로 들고오면 여집합이 깨진다 — 회귀 가드.
    assert "u.conversation_id IS NOT NULL" not in sql
    assert "30 days" in params


def test_s1b_interval_cast_not_bare_param():
    """PG 는 `interval $1`(파라미터) 문법 불허 → `%s::interval` 캐스트(대화 목록과 동일 규약)."""
    sink = []
    app._query_usage_system_records(_FakePG([[]], sink), days=7, model=None,
                                    day_label=None, gran="day")
    sql, _ = sink[0]
    assert "%s::interval" in sql
    assert "interval %s" not in sql


# ── S2: (task, target, actor) fold ────────────────────────────────────────────

def test_s2_fold_by_task_target_actor():
    sink = []
    rows = [
        _sys_row("node_analysis", "log_v2.tf_info_table", "__insight_worker__", "claude-haiku-4", 3, 300, 200, 100),
        _sys_row("node_analysis", "log_v2.tf_info_table", "__insight_worker__", "claude-sonnet-4", 2, 200, 150, 50),
        _sys_row("node_analysis", "log_v2.other_table", "__insight_worker__", "claude-haiku-4", 1, 50, 40, 10),
        _sys_row("glossary_suggest", "", "__ask_worker__", "claude-haiku-4", 4, 400, 300, 100),
    ]
    pg = _FakePG([rows, []], sink)
    items, truncated = app._query_usage_system_records(pg, days=30, model=None,
                                                       day_label=None, gran="day")
    assert truncated is False
    by_key = {(i["task"], i["target"]): i for i in items}
    a = by_key[("node_analysis", "log_v2.tf_info_table")]
    assert a["calls"] == 5 and a["total_tokens"] == 500      # 두 모델 행 합산
    assert a["prompt_tokens"] == 350 and a["completion_tokens"] == 150
    assert len(a["models"]) == 2                              # 모델 분해 보존
    assert a["actor"] == "__insight_worker__"
    assert a["task_label"] == "그래프 노드 분석"              # taxonomy 한글 라벨
    # target 없는 작업도 1행으로 남는다(대상 미기록 = None, 목록에서 사라지지 않음).
    g = by_key[("glossary_suggest", None)]
    assert g["calls"] == 4 and g["target"] is None
    assert g["task_label"] == "용어사전 후보"
    # 토큰 큰 순 정렬(대화 목록과 동일 규칙).
    assert [i["total_tokens"] for i in items] == sorted((i["total_tokens"] for i in items), reverse=True)


def test_s2b_no_secret_leak():
    """반환 키 화이트리스트 — 접속정보/비밀번호 계열이 섞이지 않는다."""
    sink = []
    rows = [_sys_row("table_insight", "dbo.Users", "__insight_worker__", "claude-haiku-4", 1, 10, 8, 2)]
    items, _ = app._query_usage_system_records(_FakePG([rows, []], sink), days=30, model=None,
                                               day_label=None, gran="day")
    allowed = {"task", "task_label", "category", "target", "actor", "conversation_id", "calls",
               "total_tokens", "prompt_tokens", "completion_tokens", "cost_usd", "models",
               "last_used_at", "scope_key", "scope_ambiguous", "nav"}
    assert set(items[0].keys()) == allowed
    for bad in ("host", "password", "user", "dsn"):
        assert bad not in items[0]


def test_s2c_conversation_link_only_for_existing_non_sentinel():
    """대화 링크는 **실재하는 비-sentinel 대화**에만 — 깨진 링크 금지.

    ① sentinel(__insight_worker__ 등) → 대화가 아님 → 링크 없음
    ② 삭제·미기록 id(conv_exists=False) → 열면 404 → 링크 없음(프론트가 '삭제된 대화' 표기)
    ③ 소유 계정만 없는 실재 대화 → 링크 부여(그러지 않으면 주체 열에 raw hex 노출 —
       PB-0008 라이브 캡처에서 포착된 케이스)
    """
    sink = []
    rows = [
        _sys_row("node_analysis", "s.t", "__insight_worker__", "claude-haiku-4", 1, 10, 8, 2,
                 conv_exists=False),
        _sys_row("classify", "", "20260723095346-63c7cb0a", "claude-haiku-4", 1, 15, 12, 3,
                 conv_exists=False),   # 삭제된 대화
        _sys_row("prompt_gen", "", "20260326033537-5a6699ff", "claude-haiku-4", 1, 20, 15, 5,
                 conv_exists=True),    # 소유자 없는 실재 대화
    ]
    items, _ = app._query_usage_system_records(_FakePG([rows, []], sink), days=30, model=None,
                                               day_label=None, gran="day")
    by_task = {i["task"]: i for i in items}
    assert by_task["node_analysis"]["conversation_id"] is None
    assert by_task["classify"]["conversation_id"] is None
    assert by_task["classify"]["actor"] == "20260723095346-63c7cb0a"   # 원 id 는 보존(표시용)
    assert by_task["prompt_gen"]["conversation_id"] == "20260326033537-5a6699ff"
    # 존재 판정은 SQL 에서 온다 — 집계 질의가 conv_exists 를 함께 뽑는지 회귀 가드.
    assert "bool_or(c.conversation_id IS NOT NULL)" in sink[0][0]


# ── S3: 차원 필터 정합(차트 ↔ 목록) ──────────────────────────────────────────

def test_s3_model_filter_uses_canonical_family():
    sink = []
    app._query_usage_system_records(_FakePG([[]], sink), days=7, model="claude-haiku-4",
                                    day_label=None, gran="day")
    sql, params = sink[0]
    assert canonical_usage_model_sql("COALESCE(u.resolved_model, u.model)") + " = %s" in sql
    assert "claude-haiku-4" in params


def test_s3b_day_filter_matches_chart_bucket(monkeypatch):
    sink = []
    monkeypatch.setattr(app, "_usage_bucket_match_sql",
                        lambda gran: ("to_char(date_trunc('day', u.created_at), 'YYYY-MM-DD')", "YYYY-MM-DD"))
    app._query_usage_system_records(_FakePG([[]], sink), days=30, model=None,
                                    day_label="2026-07-20", gran="day")
    sql, params = sink[0]
    assert "to_char(date_trunc('day', u.created_at), 'YYYY-MM-DD') = %s" in sql
    assert "2026-07-20" in params


# ── S4: target 파싱 ──────────────────────────────────────────────────────────

def test_s4_target_parts():
    f = app._usage_target_parts
    assert f("log_v2") == ("log_v2", None)                                   # 스키마 분석
    assert f("gunzgame.account") == ("gunzgame", "account")                  # 테이블 분석
    assert f("log_v2.tf_log_08.RoomID") == ("log_v2", "tf_log_08")           # 컬럼 노드 → 테이블까지
    assert f("dbGame.usp_mod_player()") == ("dbGame", "usp_mod_player")      # 루틴 노드
    assert f("") == (None, None) and f(None) == (None, None)


# ── S5: 데이터소스 해소 ──────────────────────────────────────────────────────

def test_s5_scope_unique_ambiguous_and_missing():
    sink = []
    rows = [
        _sys_row("table_insight", "schA.tbl1", "__insight_worker__", "claude-haiku-4", 1, 100, 80, 20),
        _sys_row("table_insight", "schB.tbl2", "__insight_worker__", "claude-haiku-4", 1, 90, 70, 20),
        _sys_row("table_insight", "schC.tbl3", "__insight_worker__", "claude-haiku-4", 1, 80, 60, 20),
    ]
    # 해소 질의 결과: (schema_name, table_name, ds)
    resolve_rows = [
        ("schA", "tbl1", "mysql-aaa"),                 # 유일 → 확정
        ("schB", "tbl2", "mysql-bbb"),                 # 두 데이터소스에 동명 객체 → 모호
        ("schB", "tbl2", "mssql-ccc"),
        # schC 는 결과 없음 → 미해소
    ]
    items, _ = app._query_usage_system_records(_FakePG([rows, resolve_rows], sink),
                                               days=30, model=None, day_label=None, gran="day")
    by_t = {i["target"]: i for i in items}
    assert by_t["schA.tbl1"]["scope_key"] == "mysql-aaa"
    assert by_t["schA.tbl1"]["scope_ambiguous"] is False
    assert by_t["schB.tbl2"]["scope_key"] is None           # 추측으로 하나 고르지 않는다
    assert by_t["schB.tbl2"]["scope_ambiguous"] is True
    # 모호 신호는 nav 에도 실려야 한다 — 프론트 이동 UI 가 nav 만 읽으므로 누락 시 안내가
    # 조용히 사라진다(라이브 PB-0008 에서 실제로 포착된 결함의 회귀 가드).
    assert by_t["schB.tbl2"]["nav"]["scope_ambiguous"] is True
    assert by_t["schA.tbl1"]["nav"]["scope_ambiguous"] is False
    assert by_t["schC.tbl3"]["scope_key"] is None
    assert by_t["schC.tbl3"]["scope_ambiguous"] is False
    # 해소 질의는 스키마 IN 으로 제한(전수 스캔 금지) + 3 소스 union.
    resolve_sql, resolve_params = sink[1]
    assert "table_descriptions" in resolve_sql and "routine_objects" in resolve_sql and "rag_objects" in resolve_sql
    assert "scha" in [str(p).lower() for p in resolve_params]


def test_s5b_scope_resolve_failure_is_soft(monkeypatch):
    """해소 질의가 실패해도 목록 자체는 반환된다(표시·이동 보조 정보일 뿐)."""
    sink = []
    rows = [_sys_row("table_insight", "schA.tbl1", "__insight_worker__", "claude-haiku-4", 1, 100, 80, 20)]

    class _BoomCursor(_FakeCursor):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if "rag_objects" in sql:
                raise RuntimeError("resolve boom")

    class _BoomPG(_FakePG):
        def cursor(self, *a, **k):
            return _BoomCursor(self._rows_seq, self._sink)

    pg = _BoomPG([rows, []], sink)
    items, _ = app._query_usage_system_records(pg, days=30, model=None, day_label=None, gran="day")
    assert len(items) == 1 and items[0]["scope_key"] is None
    assert pg.rolled_back is True                 # abort 트랜잭션 정리
    assert items[0]["nav"]["screen"] == "metadata"  # 이동은 화면까지 유지


def test_s5c_object_level_beats_schema_level():
    """같은 스키마가 여러 데이터소스에 있어도 객체(테이블)까지 맞으면 유일 해소된다."""
    sink = []
    rows = [_sys_row("table_insight", "shared_sch.only_here", "__insight_worker__", "claude-haiku-4", 1, 10, 8, 2)]
    resolve_rows = [
        ("shared_sch", "only_here", "mysql-aaa"),
        ("shared_sch", "other_tbl", "mssql-bbb"),   # 스키마 단위로는 모호하지만 객체는 유일
    ]
    items, _ = app._query_usage_system_records(_FakePG([rows, resolve_rows], sink),
                                               days=30, model=None, day_label=None, gran="day")
    assert items[0]["scope_key"] == "mysql-aaa" and items[0]["scope_ambiguous"] is False


# ── S6: nav 서술자 ───────────────────────────────────────────────────────────

def test_s6_nav_from_registry_and_fallback():
    nav = app._usage_system_nav({"task": "table_insight", "target": "dbo.Users", "scope_key": "mssql-x"})
    assert nav["screen"] == "metadata" and nav["subtab"] == "tables"
    assert nav["scope_key"] == "mssql-x" and nav["search"] == "Users"
    assert nav["path_label"] == "메타데이터 > 테이블 설명"
    assert nav["scope_ambiguous"] is False
    assert "target_kind" not in nav                 # 내부 분기 키는 응답에 싣지 않는다
    # 데이터소스형 target 은 scope_hint 로 넘겨 프론트가 라벨↔scope_key 를 해소한다.
    nav2 = app._usage_system_nav({"task": "cluster_label", "target": "mssql-qa-idc", "scope_key": None})
    assert nav2["screen"] == "graph" and nav2["scope_hint"] == "mssql-qa-idc" and nav2["search"] is None
    # 미등록 task → AI 운영 현황 > 운영 현황 폴백('클릭해도 아무 일 없음' 방지).
    nav3 = app._usage_system_nav({"task": "brand_new_task", "target": None, "scope_key": None})
    assert nav3["screen"] == "ai-console" and nav3["subtab"] == "ops"
    assert usage_nav_path_label("ai-console", "ops") == "AI 운영 현황 > 운영 현황"


def test_s6b_nav_registry_shape():
    """USAGE_TASK_NAV 항목 불변식 — 필수 키 + 알려진 target_kind (오타 방치 차단)."""
    for task, meta in USAGE_TASK_NAV.items():
        assert set(meta.keys()) == {"screen", "subtab", "target_kind"}, task
        assert meta["target_kind"] in {"object", "schema", "datasource", "none"}, task
        assert usage_nav_path_label(meta["screen"], meta["subtab"]), task  # 라벨맵에 등록됨
        assert usage_task_nav(task)["screen"] == meta["screen"]


# ── N1/N2: 핸들러 라우팅 ─────────────────────────────────────────────────────

class _Req:
    def __init__(self, qp=None):
        self.query_params = qp or {}


class _Conn:
    def cursor(self, *a, **k):
        return _FakeCursor([], [])

    def close(self):
        return None


def _body(resp):
    return json.loads(resp.body)


def _admin_actor():
    return {"id": 1, "permissions": {"console.usage.read": True, "conversation.list.any": True}}


def _stub_pg(monkeypatch):
    monkeypatch.setattr("shared.db._pg_connect", lambda: _FakePG([[]], []))


def test_n1_model_click_returns_both(monkeypatch):
    actor = _admin_actor()
    calls = {}
    _stub_pg(monkeypatch)
    monkeypatch.setattr(app, "_query_usage_conversations",
                        lambda *a, **k: ([{"conversation_id": "c1", "total_tokens": 5}], False))
    monkeypatch.setattr(app, "_query_usage_system_records",
                        lambda *a, **k: (calls.setdefault("sys", True), ([{"task": "node_analysis", "total_tokens": 9}], False))[1])
    monkeypatch.setattr(app, "_enrich_usage_conv_owner_meta", lambda conn, items: None)
    resp = admin_usage.admin_usage_conversations(
        _Req({"model": "claude-haiku-4"}), account=actor, conn=_Conn())
    body = _body(resp)
    assert len(body["items"]) == 1 and len(body["system_items"]) == 1
    assert calls.get("sys") is True


def test_n1b_system_role_returns_system_only(monkeypatch):
    """A2 회귀 수정 — 종전엔 items=[] 만 반환하고 끝났다(전체 토큰 절반이 열람 불가)."""
    actor = _admin_actor()
    _stub_pg(monkeypatch)
    monkeypatch.setattr(app, "_usage_account_ids_for_role", lambda conn, rk: None)  # 시스템
    monkeypatch.setattr(app, "_query_usage_conversations",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("대화 질의를 돌면 안 됨")))
    monkeypatch.setattr(app, "_query_usage_system_records",
                        lambda *a, **k: ([{"task": "cluster_label", "total_tokens": 7}], False))
    monkeypatch.setattr(app, "_enrich_usage_conv_owner_meta", lambda conn, items: None)
    resp = admin_usage.admin_usage_conversations(_Req({"role": "(시스템)"}), account=actor, conn=_Conn())
    body = _body(resp)
    assert body["items"] == [] and body["truncated"] is False
    assert len(body["system_items"]) == 1 and body["system_items"][0]["task"] == "cluster_label"


def test_n1c_account_click_excludes_system(monkeypatch):
    """계정/일반 역할 클릭에 시스템 사용분을 섞으면 그 계정 몫으로 오도된다 — 의도적 제외."""
    actor = _admin_actor()
    _stub_pg(monkeypatch)
    monkeypatch.setattr(app, "_query_usage_conversations", lambda *a, **k: ([], False))
    monkeypatch.setattr(app, "_query_usage_system_records",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("시스템 질의를 돌면 안 됨")))
    monkeypatch.setattr(app, "_enrich_usage_conv_owner_meta", lambda conn, items: None)
    body = _body(admin_usage.admin_usage_conversations(_Req({"account_id": "42"}), account=actor, conn=_Conn()))
    assert body["system_items"] == [] and body["system_truncated"] is False
    monkeypatch.setattr(app, "_usage_account_ids_for_role", lambda conn, rk: [7])
    body2 = _body(admin_usage.admin_usage_conversations(_Req({"role": "운영자"}), account=actor, conn=_Conn()))
    assert body2["system_items"] == []


def test_n2_system_query_failure_keeps_conversations(monkeypatch):
    """시스템 질의 실패가 기존 대화 목록을 깨뜨리지 않는다(부분 저하)."""
    actor = _admin_actor()
    _stub_pg(monkeypatch)
    monkeypatch.setattr(app, "_query_usage_conversations",
                        lambda *a, **k: ([{"conversation_id": "c1", "total_tokens": 5}], False))
    monkeypatch.setattr(app, "_query_usage_system_records",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(app, "_enrich_usage_conv_owner_meta", lambda conn, items: None)
    resp = admin_usage.admin_usage_conversations(_Req(), account=actor, conn=_Conn())
    assert resp.status_code == 200
    body = _body(resp)
    assert len(body["items"]) == 1 and body["system_items"] == []


def test_n2b_permission_gate_unchanged(monkeypatch):
    """신규 RBAC 0 — 기존 2-perm 게이트가 시스템 기록에도 그대로 적용된다."""
    _stub_pg(monkeypatch)
    no_usage = {"id": 1, "permissions": {"conversation.list.any": True}}
    assert admin_usage.admin_usage_conversations(_Req(), account=no_usage, conn=_Conn()).status_code == 403
    no_list = {"id": 1, "permissions": {"console.usage.read": True}}
    assert admin_usage.admin_usage_conversations(_Req(), account=no_list, conn=_Conn()).status_code == 403


# ── T1: taxonomy 편입 ────────────────────────────────────────────────────────

def test_t1_live_tasks_now_labeled():
    """라이브 llm_usage 에 있으나 미등록이던 4 task — 목록이 raw 문자열을 노출하지 않도록 편입."""
    for task, label in (("redteam", "답변 적대 검증"), ("enum_suggest", "ENUM 코드 후보"),
                        ("cluster_label", "콘텐츠 그룹 라벨"), ("product_classify", "제품 분류 제안")):
        tx = taxonomy_for(task)
        assert tx["label"] == label
        assert tx["category"] != "ai.other.unmapped", task
