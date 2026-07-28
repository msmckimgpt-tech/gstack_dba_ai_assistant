"""feature-0029 (graph churn) — sync churn 근절 계약 테스트.

라이브 근거(2026-07-28 실측): incremental sync 가 30분마다 관계 수백~수천 건을 재투영하고
(관계 1건 = AGE cypher 11회, duration 은 churn 행 수에 선형 — 무변경 cycle 18ms vs 1,453행
36초), 최근 2h 갱신 2,832행 중 ~1,796행(63%)이 **값 무변경**이었다. 원인 3종의 계약을 잠근다:
(a) 값이 안 바뀌면 updated_at 미전진 · (b) status 히스테리시스(왕복 차단) ·
(c) 프로브가 broken 을 부활시키지 않음 · (e) 정점 MERGE 중복 제거.
"""

from __future__ import annotations

from modules import relationships as R
from modules import metadata_graph as MG


# ── (b) 히스테리시스: trusted↔candidate·broken↔candidate 왕복 차단 ──────────────
def test_trusted_survives_single_negative():
    """종전엔 승격·강등 임계가 같은 0.85 라 trusted 최저점에서 음성 1회로 즉시 강등됐다
    (라이브: guildjoin.GuildId→guild.GuildId 신호 145회 왕복)."""
    w, pos, neg, st = R.next_reinforcement_state(0.86, 5, 1, "trusted", "inferred", False)
    assert st == "trusted", "음성 1회(-0.14)로는 trusted 를 못 깬다(0.86-0.14=0.72 > _TRUST_EXIT)"
    assert w < 0.86
    # 연속 2회면 강등 (자기교정 방향성 보존)
    w2, _, _, st2 = R.next_reinforcement_state(w, pos, neg, st, "inferred", False)
    assert st2 == "candidate" and w2 < w


def test_broken_does_not_revive_on_single_positive():
    """broken 은 _BREAK_EXIT(0.30) 이상이어야 candidate 로 부활 — 양성 1회로는 안 된다."""
    w, _, _, st = R.next_reinforcement_state(0.12, 0, 3, "broken", "inferred", True)
    assert st == "broken", f"0.12+0.15*0.88={w:.3f} < 0.30 이면 broken 유지"
    # 충분히 회복하면 부활
    for _ in range(6):
        w, _, _, st = R.next_reinforcement_state(w, 0, 3, st, "inferred", True)
    assert st in ("candidate", "trusted") and w >= R._BREAK_EXIT


def test_candidate_transitions_unchanged():
    """candidate 의 승격/파단 규칙은 종전과 동일(회귀 없음)."""
    _, _, _, st_up = R.next_reinforcement_state(0.90, 5, 0, "candidate", "inferred", True)
    assert st_up == "trusted"
    _, _, _, st_dn = R.next_reinforcement_state(0.20, 1, 5, "candidate", "inferred", False)
    assert st_dn == "broken"


def test_fk_source_still_authoritative():
    """FK/manual 권위 경로는 히스테리시스와 무관하게 trusted 고정(불변)."""
    w, _, _, st = R.next_reinforcement_state(0.1, 0, 9, "broken", "fk_introspect", False)
    assert (w, st) == (1.0, "trusted")


def test_hysteresis_band_invariants():
    """임계 밴드가 실제로 왕복을 막는 폭인지(코드 상수 자체를 잠금)."""
    assert R._TRUST_EXIT < R._TRUST_CEIL and R._BREAK_FLOOR < R._BREAK_EXIT
    assert R._TRUST_CEIL - R._TRUST_EXIT > R._NEG_STEP, "음성 1회로 trusted 가 깨지면 밴드가 무의미"
    assert R._BREAK_EXIT > R._BREAK_FLOOR + R._POS_STEP * (1 - R._BREAK_FLOOR) * 0.5


# ── (a) 값 무변경 시 updated_at 미전진 ────────────────────────────────────────
class _Cur:
    def __init__(self, rows):
        self.rows = rows
        self.executed: list = []

    def execute(self, sql, params=None):
        self.executed.append((" ".join(str(sql).split()), params))

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class _Conn:
    def __init__(self, rows):
        self.cur = _Cur(rows)

    def cursor(self):
        return self.cur


def _signal(monkeypatch, rows, positive):
    conn = _Conn(rows)
    monkeypatch.setattr(R, "_rw_conn", lambda c: (conn, False))
    R.apply_relationship_signal(conn, "ds1", "a", "id", "b", "id", positive)
    return [e[0] for e in conn.cur.executed if e[0].startswith("UPDATE")]


def test_signal_update_delegates_updated_at_to_trigger(monkeypatch):
    """§18.8 B-2: `updated_at` 정책은 **트리거 단일 정본**(alembic 0046) — 파이썬은 조건
    분기를 두지 않는다(BEFORE UPDATE 트리거가 항상 최종 승자라 무효였다). UPDATE 문은
    항상 `updated_at=now()` 를 포함하고, 실제 전진 여부는 트리거의 to_jsonb diff 가 정한다."""
    rows = [(1, 1.0, 3, 0, "trusted", "fk_introspect")]
    ups = _signal(monkeypatch, rows, True)
    assert ups and "updated_at=now()" in ups[0] and "last_validated_at=now()" in ups[0]
    assert "_graph_changed" not in ups[0]


def test_trigger_excludes_non_projected_columns():
    """§18.8 B-2/B-3 회귀 잠금: 트리거 diff 제외 목록이 그래프 **비투영 컬럼 전량**을 담는다.
    신호 카운터가 빠지면 신호 1건마다 updated_at 이 밀려 churn 의 54%가 그대로 남는다."""
    from pathlib import Path
    import modules.relationships as _R
    mig = (Path(_R.__file__).resolve().parents[2] / "alembic" / "versions"
           / "20260728_0046_relationship_updated_at_if_changed.py").read_text(encoding="utf-8")
    for col in ("updated_at", "last_validated_at", "positive_signals",
                "negative_signals", "source_run_id"):
        assert f"- '{col}'" in mig, f"트리거 diff 제외 목록에 {col} 누락"
    assert "set_updated_at_if_changed" in mig and "lock_timeout" in mig


def test_upsert_has_no_duplicate_updated_at_policy():
    """§18.8 B-2 도전 수용: 불변식은 한 곳(트리거)에만 — upsert 의 하드코딩 CASE 는 제거됐다."""
    import inspect
    src = inspect.getsource(_R_upsert_source())
    assert "updated_at = now()" in src
    assert "ELSE table_relationships.updated_at END" not in src, "파이썬 측 중복 정책 잔존"


def _R_upsert_source():
    return R.upsert_relationship


def test_probe_path_excludes_broken_rows(monkeypatch):
    """(c) allow_revive=False 면 SELECT 에 status<>'broken' 가드가 붙는다."""
    conn = _Conn([])
    monkeypatch.setattr(R, "_rw_conn", lambda c: (conn, False))
    R.apply_relationship_signal(conn, "ds1", "a", "id", "b", "id", True, allow_revive=False)
    sels = [e[0] for e in conn.cur.executed if e[0].startswith("SELECT")]
    assert sels and "status <> 'broken'" in sels[0]
    conn2 = _Conn([])
    monkeypatch.setattr(R, "_rw_conn", lambda c: (conn2, False))
    R.apply_relationship_signal(conn2, "ds1", "a", "id", "b", "id", True)  # 기본 True
    sels2 = [e[0] for e in conn2.cur.executed if e[0].startswith("SELECT")]
    assert sels2 and "status <> 'broken'" not in sels2[0]


def test_probe_call_sites_use_allow_revive_false():
    """소스 잠금: 프로브 3 write-back 이 전부 allow_revive=False (부활 경로 봉인)."""
    import inspect
    src = inspect.getsource(R.probe_and_reinforce)
    assert src.count("allow_revive=False") == 3
    assert "apply_relationship_signal" in src


# ── (e) 정점 MERGE 중복 제거 (파라미터 캐시 — §18.8 B-1/B-4) ─────────────────
class _GCur:
    """_merge_vertex/_merge_edge 호출을 세는 fake 커서."""


class _SlotsCur:
    """§18.8 B-1 회귀 잠금: 라이브 psycopg.Cursor 처럼 **속성 부착이 불가능한** 커서.
    종전 구현(커서에 캐시 부착)은 이 타입에서 캐시가 영구 비활성이었는데 fake 커서
    테스트만으로는 드러나지 않았다."""
    __slots__ = ()


def _count_merges(monkeypatch):
    calls: list = []
    monkeypatch.setattr(MG, "_merge_vertex", lambda cur, label, key, props: calls.append(("v", label, key)))
    monkeypatch.setattr(MG, "_merge_edge", lambda cur, sl, sk, et, tl, tk, props=None: calls.append(("e", et, sk, tk)))
    return calls


def test_anchor_dedupes_shared_vertices(monkeypatch):
    calls = _count_merges(monkeypatch)
    cache = MG.new_anchor_cache()
    for col in ("a_id", "b_id", "c_id"):
        MG._anchor_relationship_column(_GCur(), "ds1", "app.orders", col, cache=cache)
    assert len([c for c in calls if c[:2] == ("v", "Table")]) == 1
    assert len([c for c in calls if c[:2] == ("v", "Schema")]) == 1
    assert len([c for c in calls if c[0] == "e" and c[1] == "HAS_TABLE"]) == 1
    assert len([c for c in calls if c[:2] == ("v", "Column")]) == 3


def test_anchor_cache_works_with_slotted_cursor(monkeypatch):
    """§18.8 B-1: 캐시는 커서 타입과 무관해야 한다(psycopg Cursor.__slots__ == ())."""
    calls = _count_merges(monkeypatch)
    cache = MG.new_anchor_cache()
    for col in ("a_id", "b_id"):
        MG._anchor_relationship_column(_SlotsCur(), "ds1", "app.orders", col, cache=cache)
    assert len([c for c in calls if c[:2] == ("v", "Table")]) == 1, "슬롯 커서에서도 캐시 유효"


def test_anchor_without_cache_is_legacy_behavior(monkeypatch):
    calls = _count_merges(monkeypatch)
    for col in ("a_id", "b_id"):
        MG._anchor_relationship_column(_GCur(), "ds1", "app.orders", col)  # cache 미전달
    assert len([c for c in calls if c[:2] == ("v", "Table")]) == 2, "캐시 없으면 종전 동작"


def test_anchor_cache_pending_dropped_on_row_failure(monkeypatch):
    """§18.8 B-4: 행 실패(SAVEPOINT 롤백) 시 그 행의 마크를 폐기 — 후속 행이 다시 MERGE 한다.
    (폐기하지 않으면 롤백으로 사라진 정점을 캐시가 '있다'고 속여 엣지가 조용히 소실된다.)"""
    calls = _count_merges(monkeypatch)
    cache = MG.new_anchor_cache()
    MG._anchor_relationship_column(_GCur(), "ds1", "app.orders", "a_id", cache=cache)
    MG.anchor_cache_drop_pending(cache)          # 행 실패
    MG._anchor_relationship_column(_GCur(), "ds1", "app.orders", "b_id", cache=cache)
    assert len([c for c in calls if c[:2] == ("v", "Table")]) == 2, "실패 행 마크는 재사용 금지"
    # 성공 확정분은 재사용된다
    MG.anchor_cache_commit_pending(cache)
    MG._anchor_relationship_column(_GCur(), "ds1", "app.orders", "c_id", cache=cache)
    assert len([c for c in calls if c[:2] == ("v", "Table")]) == 2


def test_anchor_cache_reset_clears_committed(monkeypatch):
    """배치 커밋 실패 → 확정분까지 무효(정점이 실제로 사라졌을 수 있음)."""
    calls = _count_merges(monkeypatch)
    cache = MG.new_anchor_cache()
    MG._anchor_relationship_column(_GCur(), "ds1", "app.orders", "a_id", cache=cache)
    MG.anchor_cache_commit_pending(cache)
    MG.anchor_cache_reset(cache)
    MG._anchor_relationship_column(_GCur(), "ds1", "app.orders", "b_id", cache=cache)
    assert len([c for c in calls if c[:2] == ("v", "Table")]) == 2


def test_sync_step_wires_cache():
    """소스 잠금: 관계 step 이 캐시를 생성해 sync_relationship 에 관통시키고,
    성공/실패/롤백 경로에 각각 commit/drop/reset 을 건다."""
    import inspect
    src = inspect.getsource(MG.sync_graph)
    assert "new_anchor_cache()" in src and "cache=_anchor_cache" in src
    assert "anchor_cache_commit_pending" in src and "anchor_cache_drop_pending" in src
    assert "anchor_cache_reset" in src
