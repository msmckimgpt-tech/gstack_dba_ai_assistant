"""change-reanalysis (2026-07-27, 사용자 요청) 단위 테스트 — 구조 변동 시 AI 자동 재귀 분석.

요청: "'DB 전체 AI 능동 분석'이 이루어진 DB 에서 구조 변동(테이블·컬럼·프로시저·함수)이
insight-worker 로 감지되면, 사용자의 별도 분석 실행 없이 해당 노드가 재귀 분석된다."

이 경로는 **사람 confirm 게이트 없이 외부 LLM 비용을 쓴다**. 그래서 테스트의 무게중심은
"감지되면 돈다" 보다 **"돌면 안 될 때 안 돈다"**(오탐·폭주 봉인) 에 있다.

검증 축 (DB/AGE/datasource 불요 — fake·monkeypatch):
  node_analysis.enqueue_change_analysis
    - 자격 게이트: 'DB 전체 분석'(root_label='Schema', status='done' + **과반 성공**) 이력이 없으면
      ineligible 이며 **AGE 그래프를 조회하지 않는다**(미자격 스키마의 변동이 매 tick 그래프를
      긁지 않게 하는 순서 계약). scope 는 원형·소문자 둘 다 매칭(.env 레거시 라벨).
    - 쿨다운 / 진행 중 자동 run(busy — append 하지 않는다) / 그래프 미투영 노드 제외 / cap 절단.
    - 신규 run: root_key=<schema_key>#auto(사용자 수동 run 과 분리) · root_label='SchemaAuto' ·
      시드 잡은 §55 규약(depth=0 + anchor_key=자기 자신) · enqueued 는 INSERT 시점 확정값.
    - 시드 1행 INSERT 예외가 배치 전체를 죽이지 않고, 회계는 실제 삽입분으로 보정된다.
    - CAP=0 은 라이브 정지 스위치(완전 비활성).
  insight 구조 스냅샷(`na_struct_snap:*`)
    - 첫 관측은 baseline 확립만(후보 0) — 전량 신규 오탐 차단.
    - 신규·변경만 후보, **시드된 노드만** 스냅샷 전진(미시드는 다음 사이클 재시도), 삭제는 즉시 제거.
    - 관측하지 못한 축(루틴 introspect 미발화·cap 절단·MSSQL·테이블 지문 실패)은 스냅샷 보존,
      그 축이 처음 켜지는 사이클은 축 baseline 확립만.
    - 스냅샷 키는 실 스키마(probe_schema)까지 분리 — MSSQL 의 DB명 라벨 공유로 인한 전량 진동 차단.
    - shadow 모드는 enqueue·스냅샷 전진 없이 후보만 계측.
    - report 계측은 int 카운터만(datasource 순회 합산 규약).
  routines.introspect_and_store(inventory_sink=...) — 완전 스캔일 때만 루틴 전량 인벤토리 노출.
"""
import pytest

from modules import node_analysis as na
from modules import metadata_graph as mg
from modules import insight as ins
from modules import routines as rt
from shared import runtime_settings as _rs


class FakeCursor:
    """패턴 → 응답 매핑 fake. rows 는 (SQL 부분문자열 → fetchone 결과) dict."""

    def __init__(self, rows=None, rowcount=1):
        self.rows = rows or {}
        self.executed = []
        self.rowcount = rowcount
        self._last = None
        self.fail_on = None          # (부분문자열, 파라미터 조건) 매칭 시 예외

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.executed.append((flat, params))
        self._last = None
        if self.fail_on and self.fail_on(flat, params):
            raise RuntimeError("row insert failed")
        for pat, row in self.rows.items():
            if pat in flat:
                self._last = row
                break

    def fetchone(self):
        return self._last

    def fetchall(self):
        if self._last is None:
            return []
        return self._last if isinstance(self._last, list) else [self._last]

    def close(self):
        pass


class FakeConn:
    def __init__(self, cursor):
        self._cur = cursor
        self.closed = False

    def cursor(self):
        return self._cur

    def close(self):
        self.closed = True


def _cfg():
    from shared import config as _c
    return _c


@pytest.fixture(autouse=True)
def _fresh(monkeypatch, tmp_path):
    # refine 컬럼 probe 캐시 리셋(0038 적용 가정 = anchor_key/pass_no 사용 경로).
    monkeypatch.setattr(na, "_REFINE_COLS", {"ok": True, "warned": False})
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_ENABLED", True, raising=False)
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE", True, raising=False)
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE_MODE", "1", raising=False)
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP", 50, raising=False)
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_AUTO_CHANGE_COOLDOWN_SEC", 1800, raising=False)
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_AUTO_EXPAND_FACTOR", 4, raising=False)
    monkeypatch.setattr(ins, "AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE", True, raising=False)
    monkeypatch.setattr(ins, "AGENT_INSIGHT_TABLE_GROUPING_ENABLED", True, raising=False)
    # ⚠️ `na.auto_setting_int` 는 **patch 하지 않는다**(적대 리뷰 재검증 qa Q1): 그것을 config 직독
    #   lambda 로 갈아끼우면 `runtime_settings.get_int` 경로가 한 번도 실행되지 않아, 라이브 정지
    #   스위치(관리 콘솔 override → CAP)가 검증되지 않은 채 "검증 완료" 로 보고된다. 대신 스냅샷
    #   경로를 tmp 로 격리해 **실경로를 그대로 태우고**, override 가 없으면 spec default(=config 기본값)
    #   가 나오게 둔다.
    monkeypatch.setenv("RUNTIME_SETTINGS_SNAPSHOT_PATH", str(tmp_path / "runtime_settings.json"))
    monkeypatch.delenv("RUNTIME_SETTINGS_DISABLED", raising=False)
    for _k in ("AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP", "AGENT_NODE_ANALYSIS_AUTO_CHANGE_COOLDOWN_SEC"):
        monkeypatch.delenv(_k, raising=False)
    _rs._cache["overrides"] = None
    _rs._cache["loaded_at"] = 0.0
    _rs._cache["frozen"] = None
    ins._LAST_AUTO_REANALYSIS_STATUS.clear()


def _live_override(overrides: dict):
    """관리 콘솔 저장과 동일 경로 — 스냅샷 파일에 override 를 심고 TTL 캐시를 만료시킨다."""
    _rs.write_snapshot(overrides)
    _rs._cache["overrides"] = None
    _rs._cache["loaded_at"] = 0.0


_SCOPE = "ds-prod"
_SCHEMA_KEY = f"{_SCOPE}:log_v2"
_T1 = f"{_SCOPE}:log_v2.player_log"
_T2 = f"{_SCOPE}:log_v2.item_log"
_R1 = f"{_SCOPE}:log_v2.sp_purge_log()"


def _graph(monkeypatch, table_keys=(), routine_keys=()):
    calls = {"table": 0, "routine": 0}

    def _tables(scope, schema_key, limit=2000, conn=None):
        calls["table"] += 1
        return [{"key": k, "name": k.rsplit(".", 1)[-1], "fqn": k.split(":", 1)[1]} for k in table_keys]

    def _routines(scope, schema_key, limit=2000, conn=None):
        calls["routine"] += 1
        return [{"key": k, "name": k.rsplit(".", 1)[-1], "fqn": k.split(":", 1)[1]} for k in routine_keys]

    monkeypatch.setattr(mg, "schema_table_keys", _tables)
    monkeypatch.setattr(mg, "schema_routine_keys", _routines)
    return calls


def _conn(monkeypatch, cur):
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (FakeConn(cur), False))


def _sql_of(cur, needle):
    return [(s, p) for s, p in cur.executed if needle in s]


def _eligible_rows(**extra):
    rows = {"root_label='Schema' AND status='done'": (1,)}
    rows.update(extra)
    return rows


# ── enqueue_change_analysis ────────────────────────────────────────────────
def test_disabled_switch_is_noop(monkeypatch):
    monkeypatch.setattr(_cfg(), "AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE", False, raising=False)
    calls = _graph(monkeypatch, table_keys=[_T1])
    rep = na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1])
    assert rep["status"] == "disabled"
    assert calls["table"] == 0


def test_cap_zero_is_live_kill_switch(monkeypatch):
    """CAP=0 은 **관리 콘솔 override 만으로**(재배포 없이) 즉시 정지 — 자격 조회조차 하지 않는다.

    `auto_setting_int` 를 patch 하지 않고 `runtime_settings` 스냅샷 실경로를 태운다. config 상수는
    50 그대로임을 함께 단언해, env 가 아니라 **live override 가 이겼음**을 고정한다(qa Q1)."""
    _live_override({"AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP": 0})
    assert _cfg().AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP == 50   # env/config 는 불변
    assert na.auto_cap_value() == 0                           # 실경로가 override 를 읽는다
    cur = FakeCursor(rows=_eligible_rows())
    _conn(monkeypatch, cur)
    calls = _graph(monkeypatch, table_keys=[_T1])
    rep = na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1])
    assert rep["status"] == "disabled"
    assert calls["table"] == 0
    assert not _sql_of(cur, "INSERT INTO node_analysis_runs")


def test_live_override_can_raise_cap_above_config(monkeypatch):
    """역방향 — override 가 config 를 이긴다(정지뿐 아니라 조절도 라이브)."""
    _live_override({"AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP": 200})
    assert na.auto_cap_value() == 200
    cur = FakeCursor(rows=_eligible_rows())
    _conn(monkeypatch, cur)
    _graph(monkeypatch, table_keys=[_T1, _T2])
    rep = na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1, _T2])
    assert rep["capped"] is False and rep["seeded"] == 2


def test_cap_minus_one_is_shadow_and_gated_inside_enqueue(monkeypatch):
    """shadow 는 **enqueue 안에서** 판정한다 — 호출자 규율에 맡기면 다른 진입점이 우회한다(C3).
    라이브 전환이 가능해야 배포 후 규모 측정→정상 전환에 재배포가 필요 없다."""
    _live_override({"AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP": na.AUTO_CAP_SHADOW})
    assert na.auto_shadow_mode() is True
    cur = FakeCursor(rows=_eligible_rows())
    _conn(monkeypatch, cur)
    calls = _graph(monkeypatch, table_keys=[_T1])
    rep = na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1])
    assert rep["status"] == "shadow" and rep["seeded_keys"] == []
    assert calls["table"] == 0
    assert not _sql_of(cur, "INSERT INTO node_analysis_runs")


def test_cooldown_override_is_live(monkeypatch):
    cur = FakeCursor(rows=_eligible_rows(**{"AND created_at > now()": (1,)}))
    _conn(monkeypatch, cur)
    _graph(monkeypatch, table_keys=[_T1])
    _live_override({"AGENT_NODE_ANALYSIS_AUTO_CHANGE_COOLDOWN_SEC": 60})
    na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1])
    cd = _sql_of(cur, "AND created_at > now()")
    assert cd and cd[0][1][2] == 60      # 콘솔 값이 쿼리 파라미터로 실제 전달된다


def test_ineligible_schema_skips_graph_lookup(monkeypatch):
    """DB 전체 분석 이력이 없으면 ineligible — AGE 조회조차 하지 않는다(비용 순서 계약)."""
    cur = FakeCursor(rows={})           # 자격 쿼리 결과 없음
    _conn(monkeypatch, cur)
    calls = _graph(monkeypatch, table_keys=[_T1])
    rep = na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1])
    assert rep["status"] == "ineligible"
    assert rep["seeded"] == 0
    assert calls["table"] == 0 and calls["routine"] == 0
    assert not _sql_of(cur, "INSERT INTO node_analysis_runs")


class RunRowCursor(FakeCursor):
    """자격 쿼리를 **행 판정으로 실제 평가**하는 fake (qa Q3a).

    부분문자열 assertion 만 두면 `AND (done*2 >= enqueued OR TRUE)` 같은 무력화 변형이 그대로
    통과한다 — 과반 조건의 회귀 방어가 사라진다. 여기서는 후보 run 행에 조건을 직접 적용한다."""

    def __init__(self, runs):
        super().__init__()
        self.runs = runs          # [(scope_key, root_key, root_label, status, done, enqueued)]

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.executed.append((flat, params))
        self._last = None
        if "FROM node_analysis_runs" not in flat or "root_label='Schema'" not in flat:
            return
        sk1, sk2, rk1, rk2 = params[0], params[1], params[2], params[3]
        for scope, root, label, status, done, enq in self.runs:
            if (scope in (sk1, sk2) and root in (rk1, rk2) and label == "Schema"
                    and status == "done" and done > 0 and done * 2 >= enq):
                self._last = (1,)
                return


def test_eligibility_rejects_barely_done_run(monkeypatch):
    """run 마감이 done>0 만으로도 'done' 이라, 과반 조건이 없으면 1/500 성공 run 이
    영구 자동 지출 자격을 만든다. 문자열이 아니라 **행 판정**으로 고정한다."""
    cur = RunRowCursor([(_SCOPE, _SCHEMA_KEY, "Schema", "done", 1, 500)])
    _conn(monkeypatch, cur)
    assert na.schema_analysis_completed(_SCOPE, _SCHEMA_KEY) is False
    cur = RunRowCursor([(_SCOPE, _SCHEMA_KEY, "Schema", "done", 260, 500)])
    _conn(monkeypatch, cur)
    assert na.schema_analysis_completed(_SCOPE, _SCHEMA_KEY) is True


def test_eligibility_ignores_auto_runs(monkeypatch):
    """자동 run 이 자격을 만들면 자기 자신이 자격을 낳는 순환이 된다."""
    cur = RunRowCursor([(_SCOPE, na.auto_root_key(_SCHEMA_KEY), "SchemaAuto", "done", 50, 50)])
    _conn(monkeypatch, cur)
    assert na.schema_analysis_completed(_SCOPE, _SCHEMA_KEY) is False


def test_eligibility_matches_scope_and_root_key_case_variants(monkeypatch):
    """수동 기록 경로는 scope 를 소문자화하는데 `.env` 레거시는 라벨 원형을 쓴다. **root_key 는 그
    scope 를 품은 파생**이라 같은 방어가 없으면 한 글자 차이로 기능이 침묵 사망한다(qa Q3b)."""
    cur = RunRowCursor([("kr_live", "kr_live:log_v2", "Schema", "done", 10, 10)])
    _conn(monkeypatch, cur)
    assert na.schema_analysis_completed("KR_LIVE", "KR_LIVE:log_v2") is True
    sql, params = _sql_of(cur, "FROM node_analysis_runs")[0]
    assert "scope_key IN (%s, %s)" in sql and "root_key IN (%s, %s)" in sql
    assert params[0] == "KR_LIVE" and params[1] == "kr_live"
    assert params[2] == "KR_LIVE:log_v2" and params[3] == "kr_live:log_v2"


def test_enqueue_normalizes_scope_like_manual_router(monkeypatch):
    """수동 라우터가 `.strip().lower()` 로 적재하므로 자동도 같은 축이어야 `only_missing` 중복
    제거가 성립한다 — 축이 갈리면 사용자가 방금 비용을 낸 노드를 자동이 재시드한다(재검증 C1)."""
    cur = FakeCursor(rows=_eligible_rows())
    _conn(monkeypatch, cur)
    _graph(monkeypatch, table_keys=[f"KR_LIVE:log_v2.t1"])
    na.enqueue_change_analysis("KR_LIVE", "KR_LIVE:log_v2", ["KR_LIVE:log_v2.t1"])
    runs = _sql_of(cur, "INSERT INTO node_analysis_runs")
    assert runs and runs[0][1][1] == "kr_live"
    jobs = _sql_of(cur, "INSERT INTO node_analysis_jobs")
    assert jobs and jobs[0][1][1] == "kr_live"


def test_cooldown_blocks_new_run(monkeypatch):
    cur = FakeCursor(rows=_eligible_rows(**{"AND created_at > now()": (1,)}))
    _conn(monkeypatch, cur)
    calls = _graph(monkeypatch, table_keys=[_T1])
    rep = na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1])
    assert rep["status"] == "cooldown"
    assert calls["table"] == 0                    # 쿨다운도 그래프 조회 전에 판정
    assert not _sql_of(cur, "INSERT INTO node_analysis_runs")


def test_running_auto_run_is_busy_not_appended(monkeypatch):
    """진행 중 run 에 append 하면 run 이 영구 'running' 이라 쿨다운이 한 번도 발동하지 못하고
    사이클마다 cap 만큼 시드가 유입된다(무제한 증식). 아무것도 하지 않고 다음 사이클에 재시도한다."""
    cur = FakeCursor(rows=_eligible_rows(
        **{"SELECT run_id, root_label FROM node_analysis_runs": ("run-live", "SchemaAuto")}))
    _conn(monkeypatch, cur)
    calls = _graph(monkeypatch, table_keys=[_T1])
    rep = na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1])
    assert rep["status"] == "busy" and rep["run_id"] == "run-live"
    assert rep["seeded"] == 0 and rep["seeded_keys"] == []
    assert calls["table"] == 0                                     # 그래프도 긁지 않는다
    assert not _sql_of(cur, "INSERT INTO node_analysis_runs")
    assert not _sql_of(cur, "INSERT INTO node_analysis_jobs")


def test_running_manual_run_also_blocks_auto(monkeypatch):
    """사용자가 방금 승인해 도는 '전체 분석' 위에 승인 없는 두 번째 분석을 겹치면 같은 노드가
    두 run 에서 동시 분석돼 LLM 이 이중 지출되고 refine 세대가 경합한다(qa C2)."""
    cur = FakeCursor(rows=_eligible_rows(
        **{"SELECT run_id, root_label FROM node_analysis_runs": ("run-manual", "Schema")}))
    _conn(monkeypatch, cur)
    calls = _graph(monkeypatch, table_keys=[_T1])
    rep = na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1])
    assert rep["status"] == "busy" and rep["run_id"] == "run-manual"
    assert "사용자" in rep["reason"]
    assert calls["table"] == 0
    assert not _sql_of(cur, "INSERT INTO node_analysis_runs")
    # busy 조회가 자동·수동 root_key 를 모두 대상으로 해야 한다.
    sel = _sql_of(cur, "SELECT run_id, root_label FROM node_analysis_runs")[0]
    assert "root_key IN (%s, %s)" in sel[0]
    assert sel[1][1] == na.auto_root_key(_SCHEMA_KEY) and sel[1][2] == _SCHEMA_KEY


def test_cap_zero_pauses_pending_auto_jobs(monkeypatch):
    """CAP=0 이 **신규 트리거만** 막으면 이미 큐잉된 자동 잡이 node_budget 을 끝까지 소진한다 —
    "폭주 시 즉시 정지" 라는 운영 기대와 어긋난다(재검증 C2). 보류(삭제 아님)로 되돌릴 수 있어야."""
    cur = FakeCursor()
    _conn(monkeypatch, cur)
    monkeypatch.setattr(na, "_refine_cols_ok", lambda c: True)
    na.process_pending(max_nodes=5)
    claim = _sql_of(cur, "UPDATE node_analysis_jobs SET status='running'")
    assert claim and "SchemaAuto" not in claim[0][0]      # 정상: 기존 claim 과 byte-동치

    _live_override({"AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP": 0})
    cur2 = FakeCursor()
    _conn(monkeypatch, cur2)
    na.process_pending(max_nodes=5)
    claim2 = _sql_of(cur2, "UPDATE node_analysis_jobs SET status='running'")
    assert claim2 and "root_label = 'SchemaAuto'" in claim2[0][0]


def test_nodes_missing_in_graph_are_not_seeded(monkeypatch):
    cur = FakeCursor(rows=_eligible_rows())
    _conn(monkeypatch, cur)
    _graph(monkeypatch, table_keys=[])            # 아직 AGE 투영 전
    rep = na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1, _T2])
    assert rep["status"] == "noop"
    assert rep["skipped_missing"] == 2
    assert rep["seeded_keys"] == []
    assert not _sql_of(cur, "INSERT INTO node_analysis_runs")


def test_new_auto_run_seeds_with_self_anchor(monkeypatch):
    cur = FakeCursor(rows=_eligible_rows())
    _conn(monkeypatch, cur)
    _graph(monkeypatch, table_keys=[_T1, _T2], routine_keys=[_R1])
    rep = na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1, _R1])
    assert rep["status"] == "running" and rep["ok"] is True
    assert rep["seeded"] == 2 and set(rep["seeded_keys"]) == {_T1, _R1}

    runs = _sql_of(cur, "INSERT INTO node_analysis_runs")
    assert len(runs) == 1
    params = runs[0][1]
    assert params[2] == f"{_SCHEMA_KEY}#auto"     # 사용자 수동 run(root_key=schema_key)과 분리
    assert params[3] == "SchemaAuto"
    # enqueued 는 INSERT 시점 확정값 — autocommit 이라 'enqueued=0 커밋 후 절대값 SET' 이면
    # 그 사이 _enqueue_neighbors 의 증분이 덮어써져 예산 회계가 깨진다.
    assert params[7] == 2
    assert not _sql_of(cur, "SET enqueued = %s")
    jobs = _sql_of(cur, "INSERT INTO node_analysis_jobs")
    assert len(jobs) == 2
    for sql, jparams in jobs:
        assert "anchor_key" in sql and ",0,1.0,'pending'" in sql   # depth=0 + per-seed 앵커
        assert jparams[-1] == jparams[2]                            # anchor_key == node_key
    labels = {p[3] for _, p in jobs}
    assert labels == {"Table", "Routine"}


def test_cap_truncates_seeds(monkeypatch):
    _live_override({"AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP": 1})
    cur = FakeCursor(rows=_eligible_rows())
    _conn(monkeypatch, cur)
    _graph(monkeypatch, table_keys=[_T1, _T2])
    rep = na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1, _T2])
    assert rep["capped"] is True
    assert rep["seeded"] == 1
    assert len(_sql_of(cur, "INSERT INTO node_analysis_jobs")) == 1


def test_seed_row_exception_does_not_abort_batch(monkeypatch):
    """한 행의 INSERT 예외가 배치를 중단시키면 시드 0 인 'running' run 이 남아 이후 트리거를 막는다."""
    cur = FakeCursor(rows=_eligible_rows())
    cur.fail_on = lambda sql, params: ("INSERT INTO node_analysis_jobs" in sql
                                       and params and params[2] == _T1)
    _conn(monkeypatch, cur)
    _graph(monkeypatch, table_keys=[_T1, _T2])
    rep = na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1, _T2])
    assert rep["status"] == "running"
    assert rep["seeded"] == 1 and rep["seeded_keys"] == [_T2]
    # 회계 보정은 증분식(race-safe)이어야 한다.
    fix = _sql_of(cur, "SET enqueued = enqueued - %s")
    assert len(fix) == 1 and fix[0][1][0] == 1


def test_all_seeds_failing_cleans_up_run(monkeypatch):
    """시드가 하나도 안 들어간 run 은 영구 'running' 으로 남아 busy/cooldown 을 점유한다."""
    cur = FakeCursor(rows=_eligible_rows())
    cur.fail_on = lambda sql, params: "INSERT INTO node_analysis_jobs" in sql
    _conn(monkeypatch, cur)
    _graph(monkeypatch, table_keys=[_T1])
    rep = na.enqueue_change_analysis(_SCOPE, _SCHEMA_KEY, [_T1])
    assert rep["status"] == "noop"
    assert _sql_of(cur, "DELETE FROM node_analysis_runs")


def test_schema_analysis_completed_failclosed(monkeypatch):
    monkeypatch.setattr(na, "_rw_conn", lambda conn: (None, False))
    assert na.schema_analysis_completed(_SCOPE, _SCHEMA_KEY) is False


def test_schema_analysis_completed_true(monkeypatch):
    cur = FakeCursor(rows=_eligible_rows())
    _conn(monkeypatch, cur)
    assert na.schema_analysis_completed(_SCOPE, _SCHEMA_KEY) is True


# ── insight 구조 스냅샷 ────────────────────────────────────────────────────
def _kv(monkeypatch, initial=None, save_fails=False, eligible=True):
    """insight KV fake — 구조 스냅샷 저장소. 자격 게이트는 기본 통과로 둔다(개별 테스트가 뒤집는다)."""
    store = dict(initial or {})

    def _save(conn, cid, k, v):
        if save_fails:
            raise RuntimeError("kv write denied")
        store[k] = v

    monkeypatch.setattr(ins, "load_memory_kv", lambda conn, cid, k: store.get(k))
    monkeypatch.setattr(ins, "save_memory_kv", _save)
    monkeypatch.setattr(na, "schema_analysis_completed",
                        lambda scope, schema_key, conn=None: eligible)
    return store


def _enqueue_spy(monkeypatch, seeded_keys=(), status="running", skipped_missing=0):
    calls = []

    def _fake(scope, schema_key, node_keys, **kw):
        calls.append(list(node_keys))
        return {"ok": True, "status": status, "run_id": "r1",
                "seeded": len(seeded_keys), "seeded_keys": list(seeded_keys),
                "skipped_missing": skipped_missing, "capped": False}

    monkeypatch.setattr(na, "enqueue_change_analysis", _fake)
    return calls


def _snap(store, probe_schema="log_v2", label="log_v2", scope=_SCOPE):
    import json
    raw = store.get(ins._auto_snapshot_key(scope, label, probe_schema))
    return json.loads(raw) if raw else None


def _run(store_conn=None, *, scope=_SCOPE, label="log_v2", probe="log_v2",
         tables=None, routines=None, include_tables=True, include_routines=True, report=None):
    ins._auto_reanalyze_structure_changes(
        store_conn, scope, label, probe_schema=probe,
        current_table_fps=tables, routine_inventory=routines,
        include_tables=include_tables, include_routines=include_routines, report=report)


def test_first_scan_establishes_baseline_without_candidates(monkeypatch):
    """첫 관측을 '변경'으로 읽으면 이미 분석된 DB 전량이 승인 없는 재분석 대상이 된다."""
    store = _kv(monkeypatch)
    calls = _enqueue_spy(monkeypatch)
    report = {}
    _run(tables={"player_log": "fp1", "item_log": "fp2"}, routines={"sp_a": "h1"}, report=report)
    assert calls == []
    snap = _snap(store)
    assert snap["t"] == {"player_log": "fp1", "item_log": "fp2"}
    assert snap["r"] == {"sp_a": "h1"} and snap["tb"] == 1 and snap["rb"] == 1
    assert report.get("auto_reanalysis_candidates", 0) == 0


def test_detects_new_and_changed_only(monkeypatch):
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={"kept": "fp-keep", "changed": "fp-old"}, routines={"sp_a": "h1"})
    calls = _enqueue_spy(monkeypatch, seeded_keys=[f"{_SCOPE}:log_v2.changed",
                                                   f"{_SCOPE}:log_v2.added",
                                                   f"{_SCOPE}:log_v2.sp_a()"])
    report = {}
    _run(tables={"kept": "fp-keep", "changed": "fp-new", "added": "fp-add"},
         routines={"sp_a": "h2"}, report=report)
    assert len(calls) == 1
    assert set(calls[0]) == {f"{_SCOPE}:log_v2.changed", f"{_SCOPE}:log_v2.added",
                             f"{_SCOPE}:log_v2.sp_a()"}
    assert report["auto_reanalysis_candidates"] == 3
    assert report["auto_reanalysis_seeded"] == 3
    assert report["auto_reanalysis_runs"] == 1


def test_only_seeded_nodes_advance_snapshot(monkeypatch):
    """미시드(그래프 미투영·cap 절단) 노드는 스냅샷에 남지 않아 다음 사이클에 재시도된다."""
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a", "b": "fp-b"}, include_routines=False)
    _enqueue_spy(monkeypatch, seeded_keys=[f"{_SCOPE}:log_v2.a"])
    _run(tables={"a": "fp-a2", "b": "fp-b2"}, include_routines=False)
    snap = _snap(store)
    assert snap["t"]["a"] == "fp-a2"        # 시드 성공 → 전진
    assert snap["t"]["b"] == "fp-b"         # 미시드 → 이전 지문 유지(재시도)


def test_deleted_tables_are_removed_from_snapshot(monkeypatch):
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a", "gone": "fp-g"}, include_routines=False)
    calls = _enqueue_spy(monkeypatch, seeded_keys=[])
    _run(tables={"a": "fp-a"}, include_routines=False)
    assert calls == []                       # 삭제는 분석 대상 노드가 없어 후보 아님
    assert _snap(store)["t"] == {"a": "fp-a"}


def test_axis_off_preserves_snapshot(monkeypatch):
    """루틴 introspect 가 이번 사이클에 안 돌았는데 축을 켠 채 빈 인벤토리를 넘기면
    전량이 '삭제 → 다음 사이클 신규' 로 진동한다."""
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a"}, routines={"sp_a": "h1"})
    calls = _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a"}, routines=None, include_routines=False)
    assert calls == []
    assert _snap(store)["r"] == {"sp_a": "h1"}      # 축 보존


def test_axis_newly_enabled_only_establishes_baseline(monkeypatch):
    """관측 공백(축 off) 뒤 축이 처음 켜지면 그 축은 baseline 확립만 — 전량 신규 오탐 차단."""
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a"}, include_routines=False)       # 루틴 축 미확립 상태로 baseline
    assert _snap(store)["rb"] == 0
    calls = _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a"}, routines={"sp_a": "h1", "sp_b": "h2"})
    assert calls == []                                        # 루틴 전량이 후보가 되지 않는다
    snap = _snap(store)
    assert snap["r"] == {"sp_a": "h1", "sp_b": "h2"} and snap["rb"] == 1
    # 다음 사이클부터는 정상 감지
    calls = _enqueue_spy(monkeypatch, seeded_keys=[f"{_SCOPE}:log_v2.sp_a()"])
    _run(tables={"a": "fp-a"}, routines={"sp_a": "h1-changed", "sp_b": "h2"})
    assert calls == [[f"{_SCOPE}:log_v2.sp_a()"]]


def test_snapshot_key_separates_probe_schemas(monkeypatch):
    """MSSQL 은 저장 라벨이 DB명이라 여러 실 스키마가 라벨을 공유한다 — 대조 축이 섞이면
    스키마 A 순회가 B 를 '삭제', B 순회가 A 를 '신규' 로 읽어 매 사이클 전량 진동한다."""
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(label="salesdb", probe="dbo", tables={"a": "fp-a"}, include_routines=False)
    calls = _enqueue_spy(monkeypatch)
    _run(label="salesdb", probe="staging", tables={"z": "fp-z"}, include_routines=False)
    assert calls == []                       # 서로 다른 baseline — 오탐 0
    assert _snap(store, probe_schema="dbo", label="salesdb")["t"] == {"a": "fp-a"}
    assert _snap(store, probe_schema="staging", label="salesdb")["t"] == {"z": "fp-z"}


def test_shadow_status_measures_without_advancing_snapshot(monkeypatch):
    """shadow 판정은 enqueue 안에 있고, 호출자는 `status='shadow'`(seeded 0)를 그대로 받아
    '미전진 = 계측만' 이 된다 — 별도 분기 없이 성립하는지 확인."""
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a"}, include_routines=False)
    calls = _enqueue_spy(monkeypatch, seeded_keys=[], status="shadow")
    report = {}
    _run(tables={"a": "fp-changed"}, include_routines=False, report=report)
    assert calls == [[f"{_SCOPE}:log_v2.a"]]              # 후보는 산출됨
    assert report["auto_reanalysis_candidates"] == 1      # 규모는 관측됨
    assert _snap(store)["t"] == {"a": "fp-a"}             # 스냅샷 전진 없음(비용 0)


def test_ineligible_schema_writes_no_snapshot(monkeypatch):
    """자동 재분석이 영원히 발동할 수 없는 스키마의 스냅샷 blob 까지 적재하면, 그것이 스캔마다
    KV 전량 덤프 경로에 올라타 대역·커넥션을 먹는다(재검증 B3)."""
    store = _kv(monkeypatch, eligible=False)
    calls = _enqueue_spy(monkeypatch)
    report = {}
    _run(tables={"a": "fp-a"}, include_routines=False, report=report)
    assert calls == [] and store == {}
    assert report["auto_reanalysis_blocked"] == 1


def test_table_wipe_is_treated_as_failed_observation(monkeypatch):
    """`information_schema.TABLES` 는 권한 필터 결과라 계정 교체·GRANT 축소·복원 창에서 예외 없이
    0행을 돌려준다. 그 한 사이클을 '전부 삭제' 로 읽으면 스냅샷이 비고, 복귀 사이클에 무변경
    테이블 전량이 '신규' 로 폭발한다 — 1차 리뷰 B1(승인 없는 대량 지출)의 재진입(B2/Q2)."""
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a", "b": "fp-b", "c": "fp-c"}, include_routines=False)
    # 테이블 0 분기 호출부와 **동일한 인자** — 방어가 helper 안에 있어야 두 호출부 모두 안전하다.
    calls = _enqueue_spy(monkeypatch)
    report = {}
    _run(tables={}, include_tables=True, include_routines=False, report=report)
    assert calls == []
    assert _snap(store)["t"] == {"a": "fp-a", "b": "fp-b", "c": "fp-c"}   # 보존
    assert report["auto_reanalysis_axis_dropped"] == 1                   # 무음이 아니다
    # 복귀 사이클: 구조가 그대로면 후보 0 이어야 한다(이것이 폭발 여부의 실제 판정).
    calls = _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a", "b": "fp-b", "c": "fp-c"}, include_routines=False)
    assert calls == []


def test_majority_table_loss_is_also_untrusted(monkeypatch):
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={f"t{i}": f"fp{i}" for i in range(10)}, include_routines=False)
    calls = _enqueue_spy(monkeypatch)
    _run(tables={"t0": "fp0", "t1": "fp1"}, include_routines=False)   # 8/10 소실
    assert calls == []
    assert len(_snap(store)["t"]) == 10


def test_small_deletion_still_reflected(monkeypatch):
    """과반 미만 삭제는 정상 반영 — 방어가 삭제 감지를 죽이지 않는다."""
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={f"t{i}": f"fp{i}" for i in range(10)}, include_routines=False)
    _enqueue_spy(monkeypatch)
    _run(tables={f"t{i}": f"fp{i}" for i in range(9)}, include_routines=False)
    assert "t9" not in _snap(store)["t"] and len(_snap(store)["t"]) == 9


def test_identical_shard_creation_is_absorbed_not_analyzed(monkeypatch):
    """날짜/번호 샤드는 매일 생기지만 직전 샤드와 구조가 동일해 분석 가치가 0 이다. 이 제품은
    2026-07-03 사용자 결정으로 '동일 구조 샤드는 대표 1개만 LLM' 을 이미 확정했는데, 자동 경로가
    이름만 보고 '구조 변동' 으로 승격하면 **승인 없이 그 결정을 되돌리고 수렴하지도 않는다**(B1)."""
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={"daily_rank_20260726": "fpX", "other": "fpO"}, include_routines=False)
    calls = _enqueue_spy(monkeypatch)
    report = {}
    _run(tables={"daily_rank_20260726": "fpX", "other": "fpO",
                 "daily_rank_20260727": "fpX"},          # 새 샤드 — 구조 동일
         include_routines=False, report=report)
    assert calls == []                                    # LLM 시드 0
    assert report["auto_reanalysis_absorbed"] == 1
    # 흡수분은 즉시 스냅샷에 반영돼야 매 사이클 재탐지되지 않는다.
    assert _snap(store)["t"]["daily_rank_20260727"] == "fpX"
    calls = _enqueue_spy(monkeypatch)
    _run(tables={"daily_rank_20260726": "fpX", "other": "fpO", "daily_rank_20260727": "fpX"},
         include_routines=False)
    assert calls == []


def test_shard_with_different_structure_is_still_analyzed(monkeypatch):
    """구조가 실제로 다른 신규 테이블은 흡수하지 않는다(흡수가 감지를 삼키면 기능이 죽는다)."""
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={"daily_rank_20260726": "fpX"}, include_routines=False)
    calls = _enqueue_spy(monkeypatch, seeded_keys=[f"{_SCOPE}:log_v2.daily_rank_20260727"])
    _run(tables={"daily_rank_20260726": "fpX", "daily_rank_20260727": "fpY"},
         include_routines=False)
    assert calls == [[f"{_SCOPE}:log_v2.daily_rank_20260727"]]


def test_existing_table_change_is_never_absorbed(monkeypatch):
    """기존 테이블의 fp 변화(진짜 구조 변경)는 그룹과 무관하게 항상 후보."""
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={"daily_rank_20260726": "fpX", "daily_rank_20260727": "fpX"},
         include_routines=False)
    calls = _enqueue_spy(monkeypatch, seeded_keys=[f"{_SCOPE}:log_v2.daily_rank_20260727"])
    _run(tables={"daily_rank_20260726": "fpX", "daily_rank_20260727": "fpZ"},
         include_routines=False)
    assert calls == [[f"{_SCOPE}:log_v2.daily_rank_20260727"]]


def test_axes_are_interleaved_before_cap(monkeypatch):
    """cap 절단은 리스트 앞에서부터라, 테이블을 전부 앞에 두면 테이블 후보가 상시 cap 을 채우는
    DB 에서 루틴 축이 영구 기아가 된다(B4) — 사용자 요청 3축 중 하나가 실동작하지 않는다."""
    _kv(monkeypatch)
    calls = _enqueue_spy(monkeypatch)
    _run(tables={f"t{i}": f"fp{i}" for i in range(5)}, routines={"sp_a": "h1"})
    calls = _enqueue_spy(monkeypatch)
    _run(tables={f"t{i}": f"fp{i}-new" for i in range(5)}, routines={"sp_a": "h2"})
    assert calls, "후보가 있어야 한다"
    ordered = calls[0]
    assert ordered[1].endswith("sp_a()"), f"루틴이 앞쪽에 인터리브돼야 한다: {ordered[:3]}"


def test_snapshot_save_failure_is_swallowed(monkeypatch):
    """KV 쓰기가 계속 실패하면 같은 노드가 쿨다운 주기마다 영구 재분석된다 — 최소한 스캔을
    죽이지 않고, 실패가 로그에 남아야 한다(qa C3)."""
    _kv(monkeypatch, save_fails=True)
    calls = _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a"}, include_routines=False)    # baseline 저장 실패
    assert calls == []                                     # 예외가 새어나가지 않는다


def test_corrupt_snapshot_degrades_to_baseline(monkeypatch):
    """파손 스냅샷은 baseline 재확립(후보 0)으로 안전 저하 — 오탐보다 낫다."""
    key = ins._auto_snapshot_key(_SCOPE, "log_v2", "log_v2")
    store = _kv(monkeypatch, initial={key: "{not-json"})
    calls = _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a"}, include_routines=False)
    assert calls == []
    assert _snap(store)["t"] == {"a": "fp-a"}


def test_legacy_snapshot_without_axis_flags(monkeypatch):
    """플래그가 없던 스냅샷은 '내용이 있으면 확립' 으로 추론 — 뒤집히면 축 전량 오탐이 된다."""
    key = ins._auto_snapshot_key(_SCOPE, "log_v2", "log_v2")
    store = _kv(monkeypatch, initial={key: '{"t":{"a":"fp-a"},"r":{}}'})
    calls = _enqueue_spy(monkeypatch, seeded_keys=[f"{_SCOPE}:log_v2.a"])
    _run(tables={"a": "fp-changed"}, include_routines=False)
    assert calls == [[f"{_SCOPE}:log_v2.a"]]      # t 축은 확립됨으로 추론 → 정상 감지


def test_multiple_datasources_keep_separate_snapshots(monkeypatch):
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(scope="ds-a", tables={"t": "fp1"}, include_routines=False)
    calls = _enqueue_spy(monkeypatch)
    _run(scope="ds-b", tables={"t": "fp2"}, include_routines=False)
    assert calls == []                                     # 서로 다른 baseline
    assert _snap(store, scope="ds-a")["t"] == {"t": "fp1"}
    assert _snap(store, scope="ds-b")["t"] == {"t": "fp2"}


def test_report_counters_are_summable_ints(monkeypatch):
    """report 는 datasource 순회마다 int 합산·그 외 덮어쓰기로 병합된다 — dict 를 담으면
    마지막 datasource 것만 남아 관측이 소실된다."""
    _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a"}, include_routines=False)
    _enqueue_spy(monkeypatch, seeded_keys=[], status="cooldown")
    report = {}
    _run(tables={"a": "fp-b"}, include_routines=False, report=report)
    assert report["auto_reanalysis_blocked"] == 1
    assert all(isinstance(v, int) for v in report.values())


def test_enqueue_failure_is_swallowed_and_snapshot_frozen(monkeypatch):
    store = _kv(monkeypatch)
    _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a"}, include_routines=False)

    def _boom(*a, **k):
        raise RuntimeError("pg down")

    monkeypatch.setattr(na, "enqueue_change_analysis", _boom)
    _run(tables={"a": "fp-changed"}, include_routines=False)   # 예외를 흡수(스캔 비차단)
    assert _snap(store)["t"] == {"a": "fp-a"}                  # 미전진 → 다음 사이클 재시도


def test_switch_off_skips_trigger(monkeypatch):
    monkeypatch.setattr(ins, "AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE", False, raising=False)
    store = _kv(monkeypatch)
    calls = _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a"}, include_routines=False)
    assert calls == [] and store == {}


def test_no_observable_axis_is_noop(monkeypatch):
    store = _kv(monkeypatch)
    calls = _enqueue_spy(monkeypatch)
    _run(tables={"a": "fp-a"}, include_tables=False, include_routines=False)
    assert calls == [] and store == {}


def test_missing_scope_skips_trigger(monkeypatch):
    """scope 가 비면 그래프 노드 key 를 확정할 수 없다(호출부는 'common' 으로 폴백)."""
    store = _kv(monkeypatch)
    calls = _enqueue_spy(monkeypatch)
    _run(scope="", tables={"a": "fp-a"}, include_routines=False)
    assert calls == [] and store == {}


# ── routines.inventory_sink ────────────────────────────────────────────────
def _routine_rows(n=2):
    return [{"name": f"sp_{i}", "rtype": "procedure", "definition": f"SELECT {i}"}
            for i in range(n)]


def _routine_env(monkeypatch, cur, rows=None):
    monkeypatch.setattr(rt, "_fetch_routines", lambda db_conn, schema: rows or _routine_rows())
    monkeypatch.setattr(rt, "_fetch_params", lambda db_conn, schema: ({}, {}))
    monkeypatch.setattr(rt, "_external_tables_for", lambda kc, dsk: {})
    monkeypatch.setattr(rt, "_rw_conn", lambda kb_conn: (FakeConn(cur), False))


def test_inventory_sink_collects_full_scan(monkeypatch):
    """스냅샷 대조 입력은 '변경분'이 아니라 **전량**이어야 한다(전량이라야 삭제·무변경이 구분된다)."""
    cur = FakeCursor(rowcount=0)          # 전부 무변경 upsert
    _routine_env(monkeypatch, cur)
    sink = {}
    n = rt.introspect_and_store(object(), "log_v2", ["player_log"], scope_key=_SCOPE,
                                store_schema="log_v2", prune=False, inventory_sink=sink)
    assert n == 0                          # 무변경은 반환 카운트에 미집계(기존 규약 불변)
    assert set(sink["routines"]) == {"sp_0", "sp_1"}
    assert all(v for v in sink["routines"].values())


def test_inventory_sink_absent_on_truncation(monkeypatch):
    """cap 절단분을 전량으로 오인하면 절단 밖 루틴이 매 사이클 삭제→신규로 진동한다."""
    cur = FakeCursor()
    _routine_env(monkeypatch, cur, rows=_routine_rows(3))
    sink = {}
    rt.introspect_and_store(object(), "log_v2", [], scope_key=_SCOPE,
                            store_schema="log_v2", prune=False, cap=2, inventory_sink=sink)
    assert "routines" not in sink          # 키 부재 = 인벤토리 신뢰 불가 신호


def test_inventory_survives_row_upsert_failure(monkeypatch):
    """일부 행의 upsert 예외로 인벤토리가 갉이면 그 루틴이 다음 사이클에 '신규'로 오탐된다."""
    cur = FakeCursor()
    cur.fail_on = lambda sql, params: ("INSERT INTO routine_objects" in sql
                                       and params and params[3] == "sp_1")
    _routine_env(monkeypatch, cur)
    sink = {}
    rt.introspect_and_store(object(), "log_v2", [], scope_key=_SCOPE,
                            store_schema="log_v2", prune=False, inventory_sink=sink)
    assert set(sink["routines"]) == {"sp_0", "sp_1"}


def test_inventory_sink_optional(monkeypatch):
    """sink 미전달(기존 호출자)은 반환형·동작 불변."""
    cur = FakeCursor()
    _routine_env(monkeypatch, cur)
    assert rt.introspect_and_store(object(), "log_v2", [], scope_key=_SCOPE,
                                   store_schema="log_v2", prune=False) == 2


# ── telemetry 도달 보장 (역전된 규약) ──────────────────────────────────────
#   배경: payload 가 명시 allow-list 이던 동안 등재를 빠뜨린 계측은 조용히 사라졌다. 이 cycle 은
#   그 위험을 1라운드에 진단해 4키를 등재해 놓고도 2라운드 추가분 2키의 등재를 빠뜨려 7일간
#   무음이었고, 같은 파일에 고아 카운터가 6개 더 있었다. 그래서 규약을 뒤집었다 — 기록된 스칼라는
#   기본 도달하고, 빼야 할 것만 deny-list 에 명시한다(`_telemetry_sweep`).
#
#   이전 버전의 이 테스트는 **소스 텍스트**에 두 정규식을 걸어 "기록 키 ⊆ 등재 키" 를 봤는데,
#   적대 리뷰가 mutation 3종으로 실측한 결과 ① 등재 줄 삭제만 FAIL 이고 ② 주석 처리 ③ 지역변수로
#   이동은 **PASS** 했다(②③ 은 이 파일의 실제 관용구다). 즉 "파일 어딘가에 두 문자열이 함께
#   존재함" 을 검사할 뿐이어서 거짓 안심을 줬다. 아래는 텍스트가 아니라 **동작**을 검사한다.
def test_sweep_delivers_any_recorded_scalar():
    """기록된 스칼라는 등재 없이도 payload 에 도달한다 — 이것이 새 규약의 본체다."""
    payload = {"run_id": "r1", "status": "ok"}
    scan_report = {"brand_new_counter_never_registered": 7, "another_flag": True,
                   "float_metric": 1.5}
    ins._telemetry_sweep(payload, scan_report)
    assert payload["brand_new_counter_never_registered"] == 7
    assert payload["another_flag"] is True
    assert payload["float_metric"] == 1.5


def test_sweep_never_overwrites_explicit_entries():
    """명시 등재가 항상 우선 — sweep 이 가공된 값을 덮어써선 안 된다."""
    payload = {"auto_reanalysis_candidates": 0}
    ins._telemetry_sweep(payload, {"auto_reanalysis_candidates": 99})
    assert payload["auto_reanalysis_candidates"] == 0


def test_sweep_skips_non_scalars_and_falsy():
    """dict/list 는 datasource 순회 병합에서 마지막 것만 남아 관측을 왜곡하므로 흘리지 않는다.
    0/False 는 로그 크기 억제를 위해 생략 — 0 이어도 보여야 하는 지표는 명시 등재한다."""
    payload = {}
    ins._telemetry_sweep(payload, {"a_dict": {"x": 1}, "a_list": [1], "a_str": "s",
                                   "zero": 0, "false_flag": False, "kept": 3})
    assert payload == {"kept": 3}


def test_sweep_honors_deny_list():
    payload = {}
    ins._telemetry_sweep(payload, {"scan_started": True, "kept": 1})
    assert "scan_started" not in payload and payload["kept"] == 1
    assert "scan_started" in ins._TELEMETRY_SWEEP_DENY


def test_previously_orphaned_counters_now_reach_payload():
    """적대 리뷰가 실측한 고아 카운터 — 그 중 넷은 FUNCTION.md 가 '관측된다'고 선언한 것들이다.
    `insight_llm_calls` 는 LLM 호출 수(비용 신호), `tables_fanout` 은 2026-07-03 샤드 그룹화
    결정이 실제로 LLM 을 아끼는지의 유일한 수치다."""
    orphans = {"coverage_seeded": 3, "relationships_introspected": 5,
               "relationships_inferred": 2, "routines_introspected": 4,
               "insight_llm_calls": 11, "tables_fanout": 6}
    payload = {}
    ins._telemetry_sweep(payload, dict(orphans))
    assert payload == orphans


def test_core_auto_reanalysis_counters_stay_explicit():
    """0 이어도 항상 보여야 하는 핵심 지표는 sweep(truthy-only)에 맡기지 않고 명시 등재한다 —
    `candidates=0` 은 "안 돌았다" 자체가 POST-DEPLOY 판정 근거이므로 키가 없으면 안 된다."""
    import re
    from pathlib import Path
    src = Path(ins.__file__).read_text(encoding="utf-8")
    explicit = set(re.findall(r'"(auto_reanalysis_\w+)":\s*int\(scan_report\.get\(', src))
    for key in ("auto_reanalysis_candidates", "auto_reanalysis_seeded",
                "auto_reanalysis_runs", "auto_reanalysis_blocked"):
        assert key in explicit, f"{key} 는 0 이어도 노출돼야 하므로 명시 등재를 유지할 것"
