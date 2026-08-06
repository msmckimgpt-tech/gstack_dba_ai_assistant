"""feature-0037-domain-synthesis — L3 도메인 합성(lazy) 단위 테스트.

**핵심 명제**: 사전 전량 생성도, 답변 경로 런타임 합성도 하지 않는다.
두 제약을 동시에 지키기 위해 **요청과 생성을 분리**한다 — grounding 이 요청만 남기고
insight tick 이 합성한다.

검증 축:
  A(lazy): 요청되지 않은 스키마는 합성하지 않는다. 요청은 LLM 을 부르지 않는다.
  B(재생성): 입력(클러스터 요약 집합)이 그대로면 다시 만들지 않고, 바뀌면 만든다.
  C(비용): pass 상한 · 인자 우회 불가 · 예산 게이트 · 빈약 응답 미저장.
  D(정직성): 커버리지 카운트 전달·저장.
  E(격리): savepoint · 예외 미전파 · RO/RW 분리.
"""
import pathlib

import pytest

from modules import domain_synthesis as ds

_CLUSTER_CTX = (pathlib.Path(__file__).resolve().parents[1] / "src" / "modules"
                / "cluster_context.py")
_INSIGHT = (pathlib.Path(__file__).resolve().parents[1] / "src" / "modules" / "insight.py")


class _Cur:
    def __init__(self, pending=None, inputs=None, loaded=None, generated=None,
                 live=None, live_routine=None):
        self.calls = []
        # live / live_routine = 현재 살아있는 라벨을 **저장처별로** 나눠 준다. 클러스터링은 라벨을
        #   kind 에 따라 다른 테이블에 역기록한다(table→rag_objects, routine→routine_objects).
        #   두 축을 분리해야 "루틴으로만 이뤄진 클러스터"를 픽스처로 표현할 수 있다 — 하나로 뭉치면
        #   "rag 만이 정본"이라는 잘못된 전제를 테스트가 그대로 복제한다(적대 패널 지적).
        self._live = live
        self._live_routine = live_routine
        # pending = 미생성분(partial index 경로), generated = 이미 만들어진 것의 재검사분
        self._pending = pending if pending is not None else [("ds1", "mydb", None)]
        self._generated = generated if generated is not None else []
        self._inputs = inputs if inputs is not None else [
            ("결제 기록", "결제와 환불을 다룬다.", 20, 8),
            ("아이템 정의", "아이템 마스터를 담는다.", 15, 3)]
        self._loaded = loaded
        self._last = None
        self._last_all = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        if "SAVEPOINT" in sql.upper():
            return
        if "generated_at IS NULL AND requested_at IS NOT NULL" in sql:
            self._last_all = self._pending
        elif "generated_at IS NOT NULL AND requested_at IS NOT NULL" in sql:
            self._last_all = self._generated
        elif "FROM domain_summaries" in sql:
            self._last = self._loaded
        elif "FROM rag_objects" in sql:
            # live_cluster_labels 가 읽는 현재 라벨. (object_key, schema_name, label) 형태이고
            #   effective_schema(scope, object_key, schema) == schema 여야 채택된다.
            scope = (params or ("ds1", "mydb", ""))[0]
            schema = (params or ("ds1", "mydb", ""))[1]
            labels = self._live if self._live is not None else [r[0] for r in self._inputs]
            self._last_all = [(f"{scope}:{schema}.dbo.t{i}", "dbo", lab)
                              for i, lab in enumerate(labels)]
        elif "FROM routine_objects" in sql:
            self._last_all = [(lab,) for lab in (self._live_routine or [])]
        elif "FROM cluster_summaries" in sql:
            self._last_all = self._inputs
        else:
            self._last, self._last_all = None, []

    def fetchone(self):
        return self._last

    def fetchall(self):
        return self._last_all

    def close(self):
        pass


class _Conn:
    def __init__(self, **kw):
        self.cur = _Cur(**kw)

    def cursor(self):
        return self.cur


def _run(monkeypatch, conn, llm_result, *, cap=3, budget=True):
    import modules.llm as _llm
    monkeypatch.setattr(_llm, "llm_domain_summary",
                        lambda p, scope_key=None: llm_result, raising=False)
    import shared.llm_budget as lb
    monkeypatch.setattr(lb, "allowed", lambda conn=None: budget)
    stored = []
    monkeypatch.setattr(ds, "store", lambda *a: (stored.append(a), True)[1])
    monkeypatch.setattr(ds, "enabled", lambda: True)
    monkeypatch.setattr(ds, "max_per_pass", lambda: cap)
    rep = ds.run_synthesis_pass(conn)
    return rep, stored


# ── A: lazy ─────────────────────────────────────────────────────────────────
def test_request_does_not_call_llm():
    """요청은 기록일 뿐 — 답변 경로에서 LLM 을 부르면 체감 지연을 잠식한다(ADR-0034-07)."""
    cur = _Cur()
    assert ds.request(cur, "ds1", "mydb") is True
    sqls = [c[0] for c in cur.calls]
    assert any("INSERT INTO domain_summaries" in s for s in sqls)
    assert any("request_count = domain_summaries.request_count + 1" in s for s in sqls)


def test_request_preserves_first_requested_at():
    """요청 시각은 첫 요청을 유지한다 — 대기 순서(오래 기다린 것 우선)가 흔들리면 안 된다."""
    cur = _Cur()
    ds.request(cur, "ds1", "mydb")
    sql = [c[0] for c in cur.calls if "INSERT INTO domain_summaries" in c[0]][0]
    assert "COALESCE(domain_summaries.requested_at, now())" in sql


def test_pending_only_returns_requested():
    """요청되지 않은 스키마는 합성 대상이 아니다 — 120개를 미리 만들지 않는다."""
    cur = _Cur()
    ds.pending_schemas(cur, 3)
    sql, _p = [c for c in cur.calls if "FROM domain_summaries" in c[0]][0]
    assert "requested_at IS NOT NULL" in sql
    assert "generated_at IS NULL" in sql            # 미생성분을 먼저(partial index 적중)
    assert "request_count DESC" in sql              # 자주 찾힌 것 우선


def test_no_requests_skips_pass(monkeypatch):
    rep, stored = _run(monkeypatch, _Conn(pending=[]), {"summary": "x" * 50})
    assert rep["skipped"] == "no_requests" and stored == []


def test_no_cluster_inputs_skips_schema(monkeypatch):
    """클러스터 요약이 아직 없으면 합성할 재료가 없다."""
    rep, stored = _run(monkeypatch, _Conn(inputs=[]), {"summary": "x" * 50})
    assert rep["synthesized"] == 0 and stored == []


# ── B: 재생성 ───────────────────────────────────────────────────────────────
def test_unchanged_inputs_are_not_resynthesized(monkeypatch):
    inputs = [("A", "요약 A", 5, 2)]
    h = ds.cluster_set_hash(inputs)
    conn = _Conn(pending=[("ds1", "mydb", h)], inputs=inputs)
    rep, stored = _run(monkeypatch, conn, {"summary": "x" * 50})
    assert rep["synthesized"] == 0 and stored == []


def test_changed_inputs_trigger_resynthesis(monkeypatch):
    conn = _Conn(pending=[("ds1", "mydb", "OLDHASH")])
    rep, stored = _run(monkeypatch, conn, {"summary": "충분히 긴 한국어 도메인 요약 문장이다. 축이 셋이다."})
    assert rep["synthesized"] == 1 and stored


def test_cluster_set_hash_is_order_independent():
    a = [("A", "요약 A", 1, 1), ("B", "요약 B", 2, 2)]
    assert ds.cluster_set_hash(a) == ds.cluster_set_hash(list(reversed(a)))


def test_cluster_set_hash_changes_with_summary():
    """요약이 갱신되면 도메인 요약도 낡은 것이다."""
    assert ds.cluster_set_hash([("A", "v1", 1, 1)]) != ds.cluster_set_hash([("A", "v2", 1, 1)])


def test_cluster_set_hash_changes_with_label():
    """클러스터가 재구성되면(라벨 변경) 역시 낡은 것이다."""
    assert ds.cluster_set_hash([("A", "s", 1, 1)]) != ds.cluster_set_hash([("B", "s", 1, 1)])


def test_cluster_set_hash_empty():
    assert ds.cluster_set_hash([]) == "" and ds.cluster_set_hash(None) == ""


# ── C: 비용 ─────────────────────────────────────────────────────────────────
def test_pass_cap_limits_synthesis(monkeypatch):
    pending = [("ds1", f"db{i}", "OLD") for i in range(10)]
    rep, stored = _run(monkeypatch, _Conn(pending=pending),
                       {"summary": "충분히 긴 한국어 도메인 요약 문장이다. 축이 셋이다."}, cap=2)
    assert rep["synthesized"] == 2 and len(stored) == 2


def test_caller_limit_cannot_exceed_configured(monkeypatch):
    import modules.llm as _llm
    monkeypatch.setattr(_llm, "llm_domain_summary",
                        lambda p, scope_key=None: {"summary": "이 DB 는 결제와 아이템 정의를 담당한다. 축은 정의·거래·이력 셋이다. 결제 기록부터 보면 된다."},
                        raising=False)
    import shared.llm_budget as lb
    monkeypatch.setattr(lb, "allowed", lambda conn=None: True)
    monkeypatch.setattr(ds, "store", lambda *a: True)
    monkeypatch.setattr(ds, "enabled", lambda: True)
    monkeypatch.setattr(ds, "max_per_pass", lambda: 1)
    pending = [("ds1", f"db{i}", "OLD") for i in range(5)]
    rep = ds.run_synthesis_pass(_Conn(pending=pending), limit=99)
    assert rep["synthesized"] == 1


def test_budget_blocks_pass(monkeypatch):
    rep, stored = _run(monkeypatch, _Conn(), {"summary": "x" * 50}, budget=False)
    assert rep["skipped"] == "llm_token_budget" and stored == []


def test_thin_response_is_not_stored(monkeypatch):
    rep, stored = _run(monkeypatch, _Conn(), {"summary": "짧다"})
    assert rep["synthesized"] == 0 and stored == []


def test_disabled_and_zero_cap(monkeypatch):
    monkeypatch.setattr(ds, "enabled", lambda: False)
    assert ds.run_synthesis_pass(_Conn())["skipped"] == "disabled"
    monkeypatch.setattr(ds, "enabled", lambda: True)
    monkeypatch.setattr(ds, "max_per_pass", lambda: 0)
    assert ds.run_synthesis_pass(_Conn())["skipped"] == "cap_zero"


def test_defaults_off_when_config_unreadable(monkeypatch):
    import shared.runtime_settings as rts
    monkeypatch.setattr(rts, "get_int", lambda k: (_ for _ in ()).throw(RuntimeError("no cfg")))
    import shared.config as cfg
    monkeypatch.delattr(cfg, "AGENT_DOMAIN_SUMMARY_ENABLED", raising=False)
    assert ds.enabled() is False


def test_budget_module_absence_stops_pass():
    """예산을 못 읽으면 중단 — feature-0036 과 같은 원칙(모르면 지출하지 않는다)."""
    import inspect
    src = inspect.getsource(ds.run_synthesis_pass)
    assert 'rep["skipped"] = "budget_unavailable"' in src
    assert "_lb = None" not in src and "_rb = None" not in src


# ── D: 정직성 ───────────────────────────────────────────────────────────────
def test_payload_carries_coverage_counts():
    rows = [("A", "요약 A", 20, 3), ("B", "요약 B", 10, 0)]
    p = ds.build_payload("ds1", "mydb", rows)
    assert p["cluster_count"] == 2 and p["member_count"] == 30 and p["analyzed_count"] == 3


def test_payload_skips_empty_groups():
    rows = [("", "요약", 1, 1), ("A", "", 1, 1), ("B", "요약 B", 2, 1)]
    p = ds.build_payload("ds1", "mydb", rows)
    assert [g["label"] for g in p["groups"]] == ["B"]


def test_inputs_are_deterministically_ordered():
    cur = _Cur()
    ds.cluster_inputs(cur, "ds1", "mydb")
    sql, _p = [c for c in cur.calls if "cluster_summaries" in c[0]][0]
    assert "ORDER BY analyzed_count DESC, member_count DESC, label" in sql


def test_prompt_demands_abstraction_not_enumeration():
    """그룹을 나열하기만 하면 L2 를 반복하는 것이지 새 층이 아니다."""
    src = (pathlib.Path(__file__).resolve().parents[1] / "src" / "modules"
           / "llm.py").read_text(encoding="utf-8")
    idx = src.index("DOMAIN_SUMMARY_PROMPT")
    body = src[idx:idx + 3000]
    assert "Do NOT enumerate every group" in body
    assert "ABSTRACTION" in body
    assert "analyzed_count" in body


# ── E: 격리·배선 ────────────────────────────────────────────────────────────
def test_queries_use_savepoint():
    cur = _Cur()
    ds.pending_schemas(cur, 3)
    assert any("SAVEPOINT" in c[0].upper() for c in cur.calls)
    cur2 = _Cur()
    ds.load(cur2, "ds1", "mydb")
    assert any("SAVEPOINT" in c[0].upper() for c in cur2.calls)


def test_pass_absorbs_exceptions(monkeypatch):
    class _Boom(_Conn):
        def cursor(self):
            raise RuntimeError("pg down")

    monkeypatch.setattr(ds, "enabled", lambda: True)
    monkeypatch.setattr(ds, "max_per_pass", lambda: 3)
    import shared.llm_budget as lb
    monkeypatch.setattr(lb, "allowed", lambda conn=None: True)
    assert ds.run_synthesis_pass(_Boom())["synthesized"] == 0


def test_load_returns_empty_on_failure():
    class _Boom(_Cur):
        def execute(self, sql, params=None):
            if "domain_summaries" in sql:
                raise RuntimeError("no table")
            super().execute(sql, params)

    assert ds.load(_Boom(), "ds1", "mydb") == {}


def test_request_returns_false_on_failure():
    class _Boom(_Cur):
        def execute(self, sql, params=None):
            raise RuntimeError("read-only")

    assert ds.request(_Boom(), "ds1", "mydb") is False


def test_grounding_records_request_on_separate_rw_connection():
    """조회 커넥션은 읽기 전용(agent_kb_ro = SELECT only)이라 거기서 INSERT 하면 항상 실패한다."""
    src = _CLUSTER_CTX.read_text(encoding="utf-8")
    assert "_record_request" in src
    idx = src.index("def _record_request")
    body = src[idx:idx + 1200]
    assert "_pg_connect()" in body and "읽기 전용" in body


def test_grounding_does_not_synthesize_inline():
    """답변 경로에서 합성하면 체감 지연을 잠식한다 — 요청만 남긴다."""
    src = _CLUSTER_CTX.read_text(encoding="utf-8")
    assert "run_synthesis_pass" not in src
    assert "llm_domain_summary" not in src


def test_insight_runs_synthesis_pass():
    """호출이 존재하고 **예외 흡수 안에** 있어야 한다(어떤 실패도 insight cycle 을 막지 않는다).

    ⚠ 판정은 AST 포함관계로 한다 — 종전의 "뒤 400자 안에 except 가 있다"는 호출부 주석이
    길어지기만 해도 깨지는 근사였고, 실제로 2026-08-06 에 거짓 실패했다."""
    import ast

    src = _INSIGHT.read_text(encoding="utf-8")
    assert "run_synthesis_pass()" in src
    guarded = [
        ast.unparse(n) for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.Try) and any(
            isinstance(h.type, ast.Name) and h.type.id == "Exception" for h in n.handlers)
    ]
    assert any("run_synthesis_pass()" in g for g in guarded), \
        "합성 pass 호출이 예외 흡수 밖에 있다"


# ── codex 리뷰 회귀 방지 ─────────────────────────────────────────────────────
def test_hash_reflects_coverage_counts():
    """커버리지가 늘어 근거가 두터워지면 같은 라벨·요약이어도 도메인 그림의 신뢰도가 달라진다.
    카운트를 해시에 넣지 않으면 요약이 영원히 옛 커버리지 기준으로 남는다(codex)."""
    a = [("A", "요약", 10, 2)]
    b = [("A", "요약", 10, 8)]      # 근거만 증가
    c = [("A", "요약", 20, 2)]      # 멤버만 증가
    assert ds.cluster_set_hash(a) != ds.cluster_set_hash(b)
    assert ds.cluster_set_hash(a) != ds.cluster_set_hash(c)


def test_hash_scan_cap_exceeds_payload_cap():
    """payload cap 으로 자른 뒤 해시하면 상한 밖 클러스터의 변화를 영영 놓친다(codex)."""
    assert ds._HASH_SCAN_CAP > ds._GROUP_CAP


def test_inputs_query_uses_hash_scan_cap():
    cur = _Cur()
    ds.cluster_inputs(cur, "ds1", "mydb")
    _sql, params = [c for c in cur.calls if "cluster_summaries" in c[0]][0]
    assert ds._HASH_SCAN_CAP in params


def test_payload_caps_groups_but_counts_all():
    """싣는 그룹은 25개로 자르되 커버리지 합계는 전체 기준 — 그러지 않으면 '8개 중 3개 근거'가
    실제보다 작아 보인다."""
    rows = [(f"L{i}", f"요약 {i}", 10, 2) for i in range(40)]
    p = ds.build_payload("ds1", "mydb", rows)
    assert len(p["groups"]) == ds._GROUP_CAP
    assert p["cluster_count"] == 40
    assert p["member_count"] == 400 and p["analyzed_count"] == 80


def test_pending_query_hits_the_partial_index_first():
    """한 쿼리로 합치면 partial index 가 받지 못해 요청 이력 전체 스캔에 가까워진다(codex P2)."""
    cur = _Cur()
    ds.pending_schemas(cur, 3)
    sqls = [c[0] for c in cur.calls if "FROM domain_summaries" in c[0]]
    assert any("generated_at IS NULL AND requested_at IS NOT NULL" in s for s in sqls)


def test_insight_synthesis_runs_only_under_advisory_lock():
    """lock 없이 돌면 여러 워커가 같은 스키마를 동시에 합성해 LLM 호출이 중복된다(codex P2).

    ⚠ 단정은 **AST 로 포함관계**를 본다 — 종전의 "앞 800자 안에 `if lock_acquired:` 가 있다" 는
    이웃 코드가 사이에 끼기만 해도 깨지는(그리고 lock 밖으로 나가도 통과할 수 있는) 취약한 근사였다.
    실제로 2026-08-05 에 판정 pass 를 같은 lock 블록 안으로 옮기자 거짓 실패했다."""
    import ast

    src = _INSIGHT.read_text(encoding="utf-8")
    guarded = [
        ast.unparse(n)
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.If) and ast.unparse(n.test).strip() == "lock_acquired"
    ]
    assert any("run_synthesis_pass()" in g for g in guarded), \
        "domain_synthesis pass 가 advisory lock 블록 밖에 있다"


def test_attempted_counts_calls_even_when_nothing_is_stored(monkeypatch):
    """LLM 을 태웠으면 센다 — **저장되지 않아도**.

    `synthesized`(저장 성공)만 세면 "콜만 태우고 산출 0" 인 pass 가 통째로 무음이 된다. 그 대표
    경로가 빈약한 응답(30자 미만)이다. 증가문을 `len(summary) < 30` 뒤로 옮기는 변이는 순서만
    보는 소스 검사(call < attempt < store)를 **통과하면서** 이 계약을 정확히 파괴하므로,
    여기서는 소스가 아니라 **동작**을 본다(적대 패널 변이 M4 생존 대응)."""
    rep, stored = _run(monkeypatch, _Conn(), {"summary": "짧음"})   # 30자 미만 → 저장 안 함
    assert rep["synthesized"] == 0 and stored == []
    assert rep["attempted"] == 1, "콜을 태웠는데 attempted 에 남지 않았다"


def test_synthesis_telemetry_reaches_the_operator_payload():
    """계측은 **allow-list 에 등재돼야** 운영자에게 도달한다.

    `scan_report["domain_synthesis"]` 는 dict 라 `_telemetry_sweep` 의 스칼라 필터가 통째로 버린다.
    이 워커에서 "계측을 만들고 payload 에 안 실어 무음"이 반복된 네 번째 사례였다."""
    src = _INSIGHT.read_text(encoding="utf-8")
    for key in ("domain_synthesis_ran", "domain_synthesis_synthesized",
                "domain_synthesis_attempted"):
        assert key in src, f"{key} 가 payload allow-list 에 없다 — 계측이 도달하지 않는다"


def test_pass_is_recorded_even_when_all_counters_are_zero():
    """카운터가 0 이어도 **돌았다는 사실**은 남아야 한다.

    lazy 생성이라 0 인 tick 이 대부분이다. 0 을 안 싣는 게이트는 "요청이 없어 조용한 tick" 과
    "배선이 죽어 조용한 tick" 을 같은 무음으로 만든다 — 그러면 이 pass 의 사망을 영영 못 본다.
    `ran=1` 이 sweep 의 truthy 필터를 통과하는 유일한 증거다."""
    src = _INSIGHT.read_text(encoding="utf-8")
    idx = src.index('scan_report["domain_synthesis"] = _ds_rep')
    gate = src[max(0, idx - 400):idx]
    assert "if _ds_rep:" in gate, "카운터 조건이 걸린 게이트는 0 인 tick 을 통째로 버린다"
    assert '"domain_synthesis_ran": 1' in src


# ── 현재 유효성 필터 (2026-08-06 라벨 네임스페이스 cycle) ─────────────────────
def test_dead_clusters_are_excluded_from_l3_inputs():
    """이미 없어진 클러스터의 요약은 도메인 합성 재료에서 뺀다.

    `cluster_summaries` 는 member_set_hash 별로 누적되므로 클러스터가 재구성돼도 옛 행이 남는다.
    그것을 입력으로 쓰면 도메인 요약이 죽은 클러스터를 재료로 만들어지고, cluster_count/
    member_count 가 부풀려진 채 `_domain_line` 으로 **사용자 답변 프롬프트에 그대로 실린다**.
    라이브 실측(2026-08-06): `atum2_db_1` 은 90행(멤버 887) 중 현재 유효가 17행(멤버 196) —
    81%가 죽은 클러스터였다."""
    cur = _Cur(inputs=[("살아있음", "요약 A", 10, 5), ("사라짐", "요약 B", 99, 40)],
               live=["살아있음"])
    got = ds.cluster_inputs(cur, "ds1", "mydb")
    assert [r[0] for r in got] == ["살아있음"]


def test_all_labels_alive_keeps_everything():
    """정합 상태에서는 아무것도 버리지 않는다(과잉 필터 방지)."""
    cur = _Cur(inputs=[("A", "요약 A", 10, 5), ("B", "요약 B", 9, 4)])
    assert len(ds.cluster_inputs(cur, "ds1", "mydb")) == 2


def test_live_label_lookup_failure_skips_synthesis(monkeypatch):
    """현재 라벨을 못 읽으면 **합성하지 않는다**(부풀려진 재료로 만드느니 건너뛴다).

    요청은 남아 있으므로 다음 pass 가 재시도한다 — 판정 실패를 침묵으로 처리하는 feature-0036 의
    계약과 같은 방향이다."""
    monkeypatch.setattr(ds, "live_cluster_labels", lambda *a: None)
    assert ds.cluster_inputs(_Cur(), "ds1", "mydb") == []


def test_live_labels_join_uses_effective_schema():
    """조인 키는 `effective_schema` 를 거쳐야 한다.

    MSSQL 은 `rag_objects.schema_name` 이 리터럴 'dbo' 라 DB 차원이 소실된다 — 그대로 비교하면
    한 건도 매칭되지 않아 **모든 요약이 죽은 것으로 판정**되고 L3 가 통째로 멈춘다."""
    import inspect
    src = inspect.getsource(ds.live_cluster_labels)
    assert "effective_schema" in src
    cur = _Cur(inputs=[("A", "요약", 5, 1)])
    assert ds.live_cluster_labels(cur, "ds1", "mydb") == {"A"}
    sql = [c[0] for c in cur.calls if "FROM rag_objects" in c[0]][0]
    # SQL 은 후보만 좁힌다(정확 판정은 파이썬) — object_key 접두로 스키마 단위 선별.
    assert "object_key LIKE" in sql and "datasource_key=%s" in sql


def test_routine_only_clusters_count_as_alive():
    """루틴(프로시저)으로만 이뤄진 클러스터도 살아있다.

    라벨 역기록은 kind 로 갈린다 — 테이블은 `rag_objects`, 루틴은 `routine_objects`. rag 만 보면
    그런 클러스터가 통째로 죽은 것으로 판정된다. 라이브 실측(2026-08-06): rag 만 보면 사망 933행
    이지만 루틴을 합치면 **63행(3.4%)** 이고, 버려질 뻔한 933행 중 870행이 살아있는 루틴
    클러스터였다(MSSQL 은 루틴이 압도적: `atum2_db_1` 루틴 865 vs 테이블 115)."""
    cur = _Cur(inputs=[("테이블 묶음", "요약 A", 10, 5), ("펫 시스템", "프로시저 묶음", 17, 2)],
               live=["테이블 묶음"], live_routine=["펫 시스템"])
    got = ds.cluster_inputs(cur, "ds1", "mydb")
    assert sorted(r[0] for r in got) == ["테이블 묶음", "펫 시스템"]


def test_live_labels_union_both_member_stores():
    cur = _Cur(inputs=[("A", "요약", 5, 1)], live=["A"], live_routine=["B"])
    assert ds.live_cluster_labels(cur, "ds1", "mydb") == {"A", "B"}
    tables = [c[0] for c in cur.calls if "FROM " in c[0]]
    assert any("FROM rag_objects" in t for t in tables)
    assert any("FROM routine_objects" in t for t in tables)


def test_empty_live_labels_are_logged_not_silent(caplog):
    """현재 라벨이 0 이면 건너뛰되 **로그를 남긴다**.

    조용히 continue 하면 그 스키마가 pass cap 을 계속 물어 뒤의 요청까지 굶는다(head-of-line).
    telemetry 는 `ran=1, attempted=0` 이라 무음과 구별되지 않는다."""
    import logging
    cur = _Cur(inputs=[("A", "요약", 5, 1)], live=[], live_routine=[])
    with caplog.at_level(logging.INFO):
        assert ds.cluster_inputs(cur, "ds1", "mydb") == []
    assert any("현재 클러스터 라벨 없음" in r.message for r in caplog.records)
