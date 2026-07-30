"""feature-0034 (initpro): init_ms 프롤로그 계측 + 잔차 노출 회귀 잠금.

계측 동기(7일 실측 2026-07-30): feature-0026 의 `init_detail` 은 `history_load` **이후**만
담았고, 함수 진입~그 지점 사이 266 줄(메모리 DB 준비·datasource resolve·데이터플레인 연결)은
통짜였다. 그 결과 `init_ms` 평균 4,921ms 중 설명분이 750ms 뿐 — **4,171ms(85%) 미귀속**.
워커 직접 계측에서 데이터플레인 `connect_with_retry` 만 1,447ms 로 나왔다.

**feature-0031 에서 얻은 교훈을 적용한다**: 잔차 키(`init_other_ms`)를 반드시 노출한다.
직전 cycle 에서 "미귀속 33초" 를 쫓다 실제로는 red-team 이었음이 드러났는데, 그 판정이
가능했던 이유가 잔차를 명시했기 때문이다. 노출하지 않으면 다음 블라인드스팟이 또 숨는다.
"""
import re
from pathlib import Path

import agent_core as A


# ── 잔차 계산 ────────────────────────────────────────────────────────────────
def test_residual_is_init_minus_measured_leaves():
    d = A._build_init_detail(10_000.0, {"mem_setup_ms": 100.0, "ds_resolve_ms": 50.0,
                                        "dataplane_connect_ms": 1_400.0, "history_load_ms": 50.0})
    assert d["init_other_ms"] == 8_400.0
    assert d["mem_setup_ms"] == 100.0 and d["dataplane_connect_ms"] == 1_400.0


def test_knowledge_total_not_double_counted():
    """`knowledge_total_ms` 는 knowledge 하위 항목의 롤업이라 잔차에서 빼면 **이중 계상**된다.

    실측 확인: query_embed 6676.4 + table_insights 28.0 + relationships 69.2 + glossary 57.7
    + example_queries 10.2 + table_col_desc 2.0 ≈ knowledge_total 6924.5."""
    leaves = {"query_embed_ms": 600.0, "table_insights_ms": 30.0, "knowledge_total_ms": 640.0}
    d = A._build_init_detail(1_000.0, leaves)
    # leaf 630 과 롤업 640 을 **둘 다** 빼면 잔차가 꺼진다. `max(leaf, 롤업)`=640 만 뺀다 —
    # 롤업이 knowledge 구간의 정본이고 leaf 는 그 분할이다(실측 오차 ≤0.3ms).
    assert d["init_other_ms"] == 360.0, "롤업 키가 잔차에서 이중 계상됐다"
    assert d["knowledge_total_ms"] == 640.0, "롤업 키 자체는 보존해야 한다(표시용)"


def test_negative_residual_clamped_with_numeric_signal():
    """조용한 0 은 '전부 설명됨'으로 오독된다 — 신호를 남기되 **수치**여야 한다.

    §18.8 패널 MAJOR-1(라이브 재현): `bin/perf-snapshot.sh` §3b 는
    `jsonb_each_text(init_detail)` 로 **모든** 키를 `::float` 캐스트한다. bool 을 하나라도
    넣으면 `invalid input syntax for type double precision: "true"` 로 그 섹션이 통째로 죽는다
    — 클램프가 뭔가 알리려는 순간에 관측이 꺼지는 최악의 실패."""
    d = A._build_init_detail(100.0, {"mem_setup_ms": 500.0})
    assert d["init_other_ms"] == 0.0
    assert d["init_residual_neg_ms"] == 400.0
    for k, v in d.items():
        assert isinstance(v, (int, float)) and not isinstance(v, bool), \
            f"{k}={v!r} 가 비수치 — §3b 의 jsonb_each_text ::float 캐스트를 깨뜨린다"


def test_knowledge_uses_max_of_leaves_and_rollup():
    """§18.8 패널 MAJOR-3: 롤업은 **무조건** 기록되지만 leaf 는 `_build_knowledge_context` 가
    예외로 죽으면 하나도 안 온다. 그때 롤업만 제외하면 knowledge 구간 전체(실측 최대
    6,924ms — 평균 init_ms 보다 크다)가 잔차로 흘러 '미귀속이 크다'는 거짓 신호가 된다."""
    leaves_ok = {"query_embed_ms": 600.0, "table_insights_ms": 40.0, "knowledge_total_ms": 640.0}
    leaves_gone = {"knowledge_total_ms": 640.0}
    assert A._build_init_detail(1_000.0, leaves_ok)["init_other_ms"] == 360.0
    assert A._build_init_detail(1_000.0, leaves_gone)["init_other_ms"] == 360.0, \
        "leaf 부재 시 롤업이 대신 잡히지 않아 knowledge 시간이 잔차로 샜다"


def test_builder_is_idempotent():
    """§18.8 패널 MINOR-3: 자기 출력에 재적용해도 잔차가 붕괴하지 않는다."""
    once = A._build_init_detail(1_000.0, {"mem_setup_ms": 100.0})
    twice = A._build_init_detail(1_000.0, once)
    assert twice["init_other_ms"] == once["init_other_ms"] == 900.0


def test_unreadable_values_do_not_break_the_breakdown():
    d = A._build_init_detail(1_000.0, {"mem_setup_ms": "nope", "ds_resolve_ms": 100.0})
    assert d["init_other_ms"] == 900.0, "판독 불가 항목은 건너뛰고 나머지로 잔차를 낸다"


def test_unreadable_init_ms_keeps_leaves_drops_residual():
    d = A._build_init_detail(None, {"mem_setup_ms": 100.0})
    assert d["mem_setup_ms"] == 100.0
    assert "init_other_ms" not in d


def test_empty_detail_yields_nothing():
    assert A._build_init_detail(1_000.0, {}) == {}
    assert A._build_init_detail(1_000.0, None) == {}


# ── 배선 계약 (직전 cycle 에서 배선 미검증으로 변이 5종이 생존했던 교훈) ──────
_SRC = Path(A.__file__).read_text(encoding="utf-8")


def test_accumulator_declared_at_function_entry_not_later():
    """`_init_detail` 선언이 프롤로그보다 **앞**에 있어야 한다.

    feature-0026 은 `history_load` 직전에 선언했는데, 거기 두면 프롤로그 계측치가 빈 dict 로
    덮여 통째로 사라진다. 진입부(`agent_entry_perf` 직후) 단 한 곳에서만 선언한다."""
    i_entry = _SRC.index("agent_entry_perf = time.perf_counter()")
    i_decl = _SRC.index("_init_detail: dict[str, Any] = {}")
    i_mem = _SRC.index('_init_detail["mem_setup_ms"]')
    assert i_entry < i_decl < i_mem, "선언이 프롤로그 계측보다 뒤에 있다"
    # §18.8 패널 MAJOR-5: 종전엔 이 한 가지 철자만 셌더니 `_init_detail = {}` 나
    # `_init_detail.clear()` 로 같은 파괴를 하는 변이가 **생존**했다. 재바인딩/비우기 형태를
    # 모두 금지한다(키 쓰기 `_init_detail["k"] = …` 만 허용).
    rebinds = re.findall(r"_init_detail\s*(?::\s*dict\[str, Any\])?\s*=\s*(?!=)", _SRC)
    assert len(rebinds) == 1, f"_init_detail 재바인딩 {len(rebinds)}회 — 앞선 계측이 덮인다"
    assert ".clear()" not in _SRC.split("_init_detail")[1][:40], "_init_detail.clear() 금지"
    assert "_init_detail.clear()" not in _SRC, "_init_detail.clear() 는 프롤로그 계측을 지운다"


def test_prologue_spans_are_wired():
    for key in ("mem_setup_ms", "ds_resolve_ms", "dataplane_connect_ms"):
        assert f'_init_detail["{key}"]' in _SRC, f"{key} 배선 소실"


def test_dataplane_recorded_on_all_three_branches():
    """§18.8 패널 MAJOR-5/MINOR-1: eval·멀티·단일 **세 경로 모두** 기록해야 한다.
    한 곳만 빠져도 그 경로 답변이 '연결 0ms' 로 §3b-0 평균에 섞인다."""
    assert _SRC.count('_init_detail["dataplane_connect_ms"]') == 3, \
        "데이터플레인 기록 지점이 3개(eval·멀티·단일)가 아니다"
    assert _SRC.count("_dp_t0 = time.perf_counter()") == 3


def test_dp_timer_starts_before_the_connect_on_single_path():
    """§18.8 패널 MAJOR-5: `_dp_t0` 를 connect **뒤**로 옮기는 변이가 생존했다 —
    헤드라인 1,447ms 가 ~0 으로 읽히고 폴백 경로에선 UnboundLocalError 로 run 이 죽는다."""
    i_t0 = _SRC.index("_dp_t0 = time.perf_counter()   # initpro: 데이터플레인 연결(단일 경로")
    i_connect = _SRC.index("db_conn = _reconnect_dataplane()", i_t0)
    assert i_t0 < i_connect


def test_mem_setup_recorded_inside_the_try():
    """`mem_setup_ms` 기록이 try 밖으로 나가면 예외 경로에서 UnboundLocalError 또는
    계측 누락이 된다 — try 블록 들여쓰기(8칸) 안에 있어야 한다."""
    m = re.search(r"\n(\s+)_init_detail\[\"mem_setup_ms\"\]", _SRC)
    assert m and len(m.group(1)) == 8, "mem_setup_ms 기록이 try 블록 안에 없다"


def test_rollup_set_is_exactly_knowledge_total():
    """§18.8 패널 MAJOR-5: 롤업 집합에 임의 키를 추가하는 변이가 생존했다 — 그 키가
    잔차에서 빠져 미귀속이 과대보고된다."""
    assert A._INIT_KNOWLEDGE_ROLLUP == "knowledge_total_ms"
    assert "system_prompt_ms" not in A._INIT_KNOWLEDGE_LEAVES
    assert "history_load_ms" not in A._INIT_KNOWLEDGE_LEAVES
    assert "mem_setup_ms" not in A._INIT_KNOWLEDGE_LEAVES


def test_attachment_is_not_guarded_off():
    """§18.8 패널 MAJOR-5: `if _init_detail and False:` 로 부착을 꺼도 통과했다.
    조건은 `if _init_detail:` 정확히 그것이어야 한다."""
    m = re.search(r"\n\s+if _init_detail:\n\s+_ans_breakdown\[\"init_detail\"\] = _build_init_detail\(", _SRC)
    assert m, "부착 조건이 변형됐거나 빌더 호출과 인접하지 않다"


def test_dataplane_timing_covers_fallback_path_too():
    """단일 경로는 1차 연결 실패 시 `database=None` 폴백을 시도한다. 계측 종료점이 폴백
    **뒤**에 있어야 실제로 쓴 시간이 잡힌다 — try 안에 두면 폴백 시간이 잔차로 샌다."""
    i_t0 = _SRC.index("_dp_t0 = time.perf_counter()   # initpro: 데이터플레인 연결(단일 경로")
    i_fallback = _SRC.index("db_conn = connect_with_retry(database=None, autocommit=True, datasource=_ds)", i_t0)
    i_record = _SRC.index('_init_detail["dataplane_connect_ms"]', i_fallback)
    assert i_t0 < i_fallback < i_record


def test_breakdown_attaches_via_builder_not_raw_dict():
    """`_ans_breakdown["init_detail"]` 는 빌더를 거쳐야 잔차 키가 붙는다 — 원 dict 를 그대로
    실으면 `init_other_ms` 가 없어 블라인드스팟이 다시 숨는다."""
    assert re.search(r'_ans_breakdown\["init_detail"\] = _build_init_detail\(', _SRC), \
        "빌더를 거치지 않고 원 dict 를 싣고 있다"
