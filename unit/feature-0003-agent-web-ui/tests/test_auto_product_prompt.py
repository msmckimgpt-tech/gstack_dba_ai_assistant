"""TASK-0309 — insight 분석률 95% 도달 시 제품 프롬프트 무인 자동완성(1회성) 회귀 테스트.

요청(2026-06-25): 관리 콘솔 > 제품의 각 제품에서 '제품 프롬프트'가 아직 입력되지 않은 항목을
대상으로, 분석률(coverage pct)이 임계(기본 95%)를 넘는 순간 자체적으로 프롬프트를 자동완성·저장.
단 1회성 — insight 초기화로 분석률이 다시 내려갔다 재상승해도 재실행하지 않는다.

검증:
  T1  분석률 < 임계 → 자동완성 안 함, 마커 미설정.
  T2  분석률 >= 임계 + 프롬프트 미입력 → 1회 자동완성·저장·마커 설정. 재sweep 시 재실행 안 함.
  T3  insight 초기화 시뮬(프롬프트 비움 + 재상승) → 마커 보유로 재실행 안 함 (1회성 핵심).
  T4  프롬프트가 이미 입력된 제품 → 분석률 무관 자동완성 안 함(마커 미설정 유지).
  T5  분석률 None(측정 불가) → 자동완성 안 함.
  T6  pct == 임계값(95.0) → 자동완성 수행(>= 비교, 경계 포함).
  T7  다제품 혼재 → 적격(미입력+>=임계+마커없음)만 생성.
  T8  _collect_product_prompt_context 인증 게이트가 코어 위임 전 차단/통과.
  T9  저장은 명시 tx(autocommit=False→복원) + commit (적대리뷰 B1).
  T10 마커 UPDATE 실패 시 rollback → 프롬프트 미저장·마커 NULL (B1 — 1회성 불변식 부분실패 보호).
  T11 LLM 실패 제품은 backoff 로 다음 cycle 재호출 안 함 (적대리뷰 M1 비용 누수).
  T12 cycle 당 생성 상한 (적대리뷰 M2 비용 버스트 분산).

`make test`(agent 이미지, --no-deps)에서 DB 없이 fake/monkeypatch 로 실행된다.
"""
from __future__ import annotations

import app


# ── Fakes ───────────────────────────────────────────────────────────────────────

class _FakeLLMResp:
    def __init__(self, content, finish_reason="stop"):
        msg = type("M", (), {"content": content})()
        self.choices = [type("C", (), {"message": msg, "finish_reason": finish_reason})()]


class _FakeCompletions:
    def __init__(self, outer):
        self._o = outer

    def create(self, **kwargs):
        self._o.calls += 1
        if self._o.fail:
            raise RuntimeError("simulated LLM failure")
        return _FakeLLMResp(self._o.content, self._o.finish_reason)


class _FakeLLMClient:
    def __init__(self, content="자동 생성된 시스템 프롬프트 본문", finish_reason="stop", fail=False):
        self.content = content
        self.finish_reason = finish_reason
        self.fail = fail
        self.calls = 0
        self.chat = type("Chat", (), {"completions": _FakeCompletions(self)})()


class _FakeMemCursor:
    """sweep/autonomous-gen 이 쓰는 WebProducts 마커 SQL 만 store dict 로 해석.

    write(upsert/마커)는 conn 의 pending 버퍼에 적재 → commit 시 store 반영, rollback 시 폐기
    (실제 명시 tx 의 원자성을 모델링 — B1 회귀 검출).
    """

    def __init__(self, conn):
        self._conn = conn
        self._store = conn._store
        self._row = None
        self._rows = []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        p = params or ()
        if "SELECT Id FROM WebProducts WHERE AutoPromptGeneratedAt IS NULL" in s:
            self._rows = [(pid,) for pid in sorted(self._store) if self._store[pid]["marker"] is None]
        elif "SELECT AutoPromptGeneratedAt FROM WebProducts WHERE Id" in s:
            pid = int(p[0])
            self._row = (self._store[pid]["marker"],)
        elif "UPDATE WebProducts SET AutoPromptGeneratedAt" in s:
            pid = int(p[0])
            if self._conn.fail_on_marker_update:
                raise RuntimeError("simulated marker UPDATE failure")
            self._conn._pending_marker[pid] = "2026-06-25 00:00:00"
        else:
            self._row = None
            self._rows = []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows

    def close(self):
        return None


class _FakeMemConn:
    def __init__(self, store):
        self._store = store
        self._autocommit = True
        self.autocommit_history = []
        self.commit_count = 0
        self.rollback_count = 0
        self.fail_on_marker_update = False
        self._pending_prompt = {}   # pid -> content (upsert)
        self._pending_marker = {}   # pid -> ts

    @property
    def autocommit(self):
        return self._autocommit

    @autocommit.setter
    def autocommit(self, v):
        self._autocommit = v
        self.autocommit_history.append(v)

    def cursor(self, *a, **k):
        return _FakeMemCursor(self)

    def commit(self):
        self.commit_count += 1
        for pid, content in self._pending_prompt.items():
            self._store[pid]["prompt"] = content
        for pid, ts in self._pending_marker.items():
            self._store[pid]["marker"] = ts
        self._pending_prompt = {}
        self._pending_marker = {}

    def rollback(self):
        self.rollback_count += 1
        self._pending_prompt = {}
        self._pending_marker = {}

    def close(self):
        return None


def _install(monkeypatch, *, store, pct_by_pid, llm=None, fail_marker=False):
    """sweep 의존성 일괄 monkeypatch. 반환 (llm, conns) — conns 는 생성된 FakeMemConn 기록."""
    llm = llm or _FakeLLMClient()
    conns: list = []

    def _make_conn():
        c = _FakeMemConn(store)
        c.fail_on_marker_update = fail_marker
        conns.append(c)
        return c

    monkeypatch.setattr(app, "_connect_memory", _make_conn)
    monkeypatch.setattr(
        app, "_list_products",
        lambda conn, include_inactive=False: [
            {"id": pid, "datasource_key": None} for pid in sorted(store)
        ],
    )
    monkeypatch.setattr(
        app, "_product_prompt_present",
        lambda conn, pid: bool(str(store[int(pid)]["prompt"]).strip()),
    )
    monkeypatch.setattr(
        app, "_compute_product_insight_coverage",
        lambda conn, product: {"pct": pct_by_pid.get(int(product["id"]))},
    )
    monkeypatch.setattr(app, "_insight_cov_cache_get", lambda key: None)
    monkeypatch.setattr(app, "_insight_cov_cache_put", lambda key, val: None)

    def _fake_assemble(product_id):
        return None, {
            "openai_client": llm,
            "create_kwargs": {"model": "x", "messages": [], "timeout": 90},
            "llm_model": "x",
            "max_tokens": 100,
            "meta_base": {"grounded": True},
        }

    monkeypatch.setattr(app, "_assemble_product_prompt_llm_request", _fake_assemble)

    def _fake_upsert(conn, *, scope, content, product_id=None, role_id=None,
                     account_id=None, updated_by_account_id=None):
        conn._pending_prompt[int(product_id)] = content  # tx pending — commit 시 store 반영
        return 1

    monkeypatch.setattr(app, "_upsert_system_prompt", _fake_upsert)
    monkeypatch.setattr(app, "record_audit_event", lambda *a, **k: None)
    monkeypatch.setattr(app, "_AUTO_PROMPT_COVERAGE_THRESHOLD", 95.0)
    monkeypatch.setattr(app, "_AUTO_PROMPT_MAX_PER_CYCLE", 0)       # 무제한(cap 테스트만 override)
    monkeypatch.setattr(app, "_AUTO_PROMPT_FAIL_BACKOFF_SEC", 3600)
    app._AUTO_PROMPT_FAIL_UNTIL.clear()                            # 테스트 간 backoff 격리
    return llm, conns


# ── Tests ───────────────────────────────────────────────────────────────────────

def test_below_threshold_no_generation(monkeypatch):
    store = {1: {"marker": None, "prompt": ""}}
    llm, _ = _install(monkeypatch, store=store, pct_by_pid={1: 80.0})
    stats = app._auto_prompt_sweep_once()
    assert llm.calls == 0
    assert store[1]["prompt"] == ""
    assert store[1]["marker"] is None
    assert stats["generated"] == 0


def test_crosses_threshold_generates_once(monkeypatch):
    store = {1: {"marker": None, "prompt": ""}}
    llm, _ = _install(monkeypatch, store=store, pct_by_pid={1: 96.0})
    s1 = app._auto_prompt_sweep_once()
    assert s1["generated"] == 1
    assert store[1]["prompt"]                # 저장됨
    assert store[1]["marker"] is not None    # 1회성 마커 설정
    assert llm.calls == 1
    s2 = app._auto_prompt_sweep_once()       # 재sweep — 마커 보유 → 후보 제외
    assert s2["scanned"] == 0
    assert llm.calls == 1


def test_reset_then_reclimb_no_regeneration(monkeypatch):
    """1회성 핵심: 자동완성 후 insight 초기화(프롬프트 비움 + 분석률 재상승)해도 재실행 안 함."""
    store = {1: {"marker": None, "prompt": ""}}
    llm, _ = _install(monkeypatch, store=store, pct_by_pid={1: 99.0})
    app._auto_prompt_sweep_once()
    assert llm.calls == 1 and store[1]["marker"] is not None
    store[1]["prompt"] = ""                  # insight 초기화 시뮬: 프롬프트 비움(분석률 재상승 유지)
    s = app._auto_prompt_sweep_once()
    assert s["scanned"] == 0                 # 마커 보유 → 후보 제외
    assert llm.calls == 1                     # 재생성 없음
    assert store[1]["prompt"] == ""


def test_existing_prompt_skipped(monkeypatch):
    store = {1: {"marker": None, "prompt": "관리자가 직접 입력한 프롬프트"}}
    llm, _ = _install(monkeypatch, store=store, pct_by_pid={1: 99.0})
    s = app._auto_prompt_sweep_once()
    assert llm.calls == 0
    assert store[1]["marker"] is None        # 자동완성 대상 아님 → 마커 미설정
    assert s["skipped"] == 1


def test_none_pct_skipped(monkeypatch):
    store = {1: {"marker": None, "prompt": ""}}
    llm, _ = _install(monkeypatch, store=store, pct_by_pid={1: None})
    s = app._auto_prompt_sweep_once()
    assert llm.calls == 0
    assert store[1]["marker"] is None


def test_threshold_boundary_inclusive(monkeypatch):
    """pct == 임계값(95.0) → 자동완성 수행(>= 비교, 경계 포함)."""
    store = {1: {"marker": None, "prompt": ""}}
    llm, _ = _install(monkeypatch, store=store, pct_by_pid={1: 95.0})
    s = app._auto_prompt_sweep_once()
    assert s["generated"] == 1
    assert llm.calls == 1


def test_multi_product_only_eligible_generate(monkeypatch):
    store = {
        1: {"marker": None, "prompt": ""},                 # 미입력 + 96% → 대상
        2: {"marker": None, "prompt": "수동"},             # 프롬프트 존재 → 제외
        3: {"marker": None, "prompt": ""},                 # 미입력 + 50% → 제외
        4: {"marker": "2026-01-01", "prompt": ""},         # 마커 보유 → 후보 제외
    }
    llm, _ = _install(monkeypatch, store=store, pct_by_pid={1: 96.0, 2: 99.0, 3: 50.0, 4: 99.0})
    s = app._auto_prompt_sweep_once()
    assert s["generated"] == 1
    assert store[1]["marker"] is not None and store[1]["prompt"]
    assert store[2]["marker"] is None
    assert store[3]["marker"] is None
    assert store[4]["prompt"] == ""
    assert llm.calls == 1


def test_collect_context_auth_gate(monkeypatch):
    """리팩터 검증: _collect_product_prompt_context 가 인증 후에만 코어로 위임."""
    import asyncio

    called = {"assemble": 0}
    monkeypatch.setattr(app, "_connect_memory", lambda: _FakeMemConn({}))

    def _fake_assemble(pid):
        called["assemble"] += 1
        return None, {"ok": True}

    monkeypatch.setattr(app, "_assemble_product_prompt_llm_request", _fake_assemble)

    monkeypatch.setattr(app, "_require_account", lambda request, conn: (None, "ERR"))
    err, ctx = asyncio.run(app._collect_product_prompt_context(1, object()))
    assert err == "ERR" and ctx is None and called["assemble"] == 0

    monkeypatch.setattr(app, "_require_account", lambda request, conn: ({"id": 1}, None))
    monkeypatch.setattr(app, "_account_has_permission", lambda account, perm: True)
    err2, ctx2 = asyncio.run(app._collect_product_prompt_context(1, object()))
    assert err2 is None and ctx2 == {"ok": True} and called["assemble"] == 1


def test_save_uses_explicit_transaction(monkeypatch):
    """B1: 저장은 autocommit=False 명시 tx 로 진입 후 복원 + commit."""
    store = {1: {"marker": None, "prompt": ""}}
    llm, conns = _install(monkeypatch, store=store, pct_by_pid={1: 96.0})
    app._auto_prompt_sweep_once()
    auto_conn = conns[-1]                     # autonomous-gen conn (마지막 생성)
    assert auto_conn.autocommit_history == [False, True]  # tx 진입 False → finally 복원 True
    assert auto_conn.commit_count == 1
    assert auto_conn.rollback_count == 0
    assert store[1]["prompt"] and store[1]["marker"] is not None


def test_marker_update_failure_rolls_back(monkeypatch):
    """B1 핵심: 마커 UPDATE 실패 시 rollback → 프롬프트 미저장·마커 NULL (부분 commit 없음)."""
    store = {1: {"marker": None, "prompt": ""}}
    llm, conns = _install(monkeypatch, store=store, pct_by_pid={1: 96.0}, fail_marker=True)
    s = app._auto_prompt_sweep_once()
    assert store[1]["prompt"] == ""           # upsert 가 commit 안 됨(rollback)
    assert store[1]["marker"] is None         # 마커도 미설정 → 1회성 불변식 유지(다음 기회 재시도)
    auto_conn = conns[-1]
    assert auto_conn.rollback_count >= 1
    assert auto_conn.commit_count == 0
    assert auto_conn.autocommit_history[-1] is True  # finally 복원
    assert s["errors"] == 1


def test_llm_failure_backoff(monkeypatch):
    """M1: LLM 실패 제품은 backoff 로 다음 cycle 재호출 안 함(비용 누수 차단)."""
    store = {1: {"marker": None, "prompt": ""}}
    failing = _FakeLLMClient(fail=True)
    llm, _ = _install(monkeypatch, store=store, pct_by_pid={1: 96.0}, llm=failing)
    s1 = app._auto_prompt_sweep_once()
    assert s1["errors"] == 1 and failing.calls == 1
    assert store[1]["marker"] is None         # 실패 → 마커 미설정
    s2 = app._auto_prompt_sweep_once()        # 즉시 재sweep — backoff 창 안이라 LLM 미호출
    assert failing.calls == 1                 # 재호출 안 됨
    assert s2["skipped"] == 1


def test_max_per_cycle_cap(monkeypatch):
    """M2: cycle 당 생성 상한 — 적격 다수여도 상한까지만 생성(나머지는 다음 cycle)."""
    store = {pid: {"marker": None, "prompt": ""} for pid in (1, 2, 3, 4, 5)}
    llm, _ = _install(monkeypatch, store=store, pct_by_pid={pid: 99.0 for pid in store})
    monkeypatch.setattr(app, "_AUTO_PROMPT_MAX_PER_CYCLE", 2)
    s = app._auto_prompt_sweep_once()
    assert s["generated"] == 2
    assert llm.calls == 2
    marked = sum(1 for pid in store if store[pid]["marker"] is not None)
    assert marked == 2                        # 나머지 3건은 다음 cycle
