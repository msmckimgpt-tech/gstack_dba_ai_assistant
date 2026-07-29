"""feature-0031 (infdetail): inference_ms 내부 분해 회귀 잠금.

계측 동기(7일 실측 2026-07-29): 답변 지연의 최대 구간인 inference 가 평균 142.9초인데
`llm_usage` 로 귀속되는 LLM 시간은 109.9초(4.3 호출)뿐이고 **33.0초(23%)가 미귀속**이었다.
feature-0026 이 init_ms 를 init_detail 로 쪼갠 뒤에도 가장 큰 단계만 블랙박스로 남아 있어
다음 개선 대상을 고를 근거가 없었다. 잔차(other_ms)를 명시적으로 노출하는 것이 이 계측의 핵심.

**§18.8 QA 패널 반영**: 초안 테스트는 `_build_inference_detail`(순수 빌더)만 호출해
**누산 배선이 0% 검증**이었고, 5개 변이(누산 호출 삭제·도구 계측 제거·키 상한 제거·
redteam 미차감·영속 차단)가 전부 생존했다. 누산기를 모듈 함수로 승격해 배선 계약을 직접 잠근다.
"""
import re
from pathlib import Path

import agent_core as A


def _acc(llm_ms=0.0, llm_calls=0, tool_ms=0.0, tool_calls=0):
    return {"llm_ms": llm_ms, "llm_calls": llm_calls,
            "tool_ms": tool_ms, "tool_calls": tool_calls}


# ── 잔차 계산 ────────────────────────────────────────────────────────────────
def test_residual_excludes_llm_tool_and_redteam():
    """other_ms = inference − redteam − llm − tool.

    redteam 을 빼지 않으면 red-team 자가 리뷰의 LLM 시간(실측상 wall 의 95~98%)이 통째로
    잔차로 잡혀 '오케스트레이션이 느리다'는 정반대 결론이 나온다."""
    d = A._build_inference_detail(100_000.0, 40_000.0, _acc(llm_ms=30_000.0, llm_calls=3,
                                                            tool_ms=20_000.0, tool_calls=2), {}, {})
    assert d["other_ms"] == 10_000.0
    assert (d["llm_ms"], d["llm_calls"], d["tool_ms"], d["tool_calls"]) == (30_000.0, 3, 20_000.0, 2)
    assert "residual_clamped" not in d


def test_negative_residual_is_clamped_and_flagged():
    """계측 중첩·오차로 잔차가 음수면 0 으로 클램프하되 **플래그를 남긴다** —
    조용히 0 을 쓰면 '전부 설명됨'으로 오독된다."""
    d = A._build_inference_detail(10_000.0, 0.0, _acc(llm_ms=9_000.0, tool_ms=5_000.0), {}, {})
    assert d["other_ms"] == 0.0
    assert d["residual_clamped"] is True


def test_tool_top_ranked_and_capped():
    """도구별 소요는 ms 내림차순 상위 6개만 — 무제한이면 meta_json 이 비대해진다."""
    tool_ms = {f"t{i}": float(i) * 100 for i in range(1, 10)}
    tool_n = {f"t{i}": i for i in range(1, 10)}
    d = A._build_inference_detail(60_000.0, 0.0, _acc(tool_ms=4_500.0, tool_calls=45), tool_ms, tool_n)
    top = d["tool_top"]
    assert len(top) == 6
    assert list(top.keys())[0] == "t9", "ms 내림차순이 아니다"
    assert top["t9"] == {"ms": 900.0, "n": 9}
    assert "t1" not in top and "t3" not in top


def test_malformed_inference_ms_keeps_counters_drops_residual():
    """inference_ms 가 판독 불가여도 **누산치는 살린다** — 잔차만 포기한다."""
    d = A._build_inference_detail("nope", 0.0, _acc(llm_ms=1_000.0, llm_calls=1), {}, {})
    assert d["llm_ms"] == 1_000.0 and d["llm_calls"] == 1
    assert "other_ms" not in d


def test_none_accumulator_yields_nothing_but_zeroed_one_still_reports():
    """None/비-dict 만 빈 결과다.

    §18.8 패널 MINOR-6: 실제 경로의 누산기는 `new_inference_acc()` 로 항상 4키가 채워져 있어
    '아무것도 안 돌면 키를 안 만든다' 는 초안 주장은 거짓이었다. 0 으로 채워진 누산기는
    **정상적으로 보고**돼야 한다 — 그래야 'LLM 0회인데 inference 가 길다'가 드러난다."""
    assert A._build_inference_detail(1000.0, 0.0, None, {}, {}) == {}
    assert A._build_inference_detail(1000.0, 0.0, "nope", {}, {}) == {}
    z = A._build_inference_detail(1000.0, 0.0, A.new_inference_acc(), {}, {})
    assert z["llm_calls"] == 0 and z["other_ms"] == 1000.0


# ── 누산 배선 계약 (패널 MAJOR-5: 초안은 전부 미검증이었다) ───────────────────
def test_acc_llm_counts_call_and_adds_provider_ms():
    acc = A.new_inference_acc()
    A.inference_acc_llm(acc, 1500.0)
    A.inference_acc_llm(acc, 500.5)
    assert acc["llm_calls"] == 2 and acc["llm_ms"] == 2000.5


def test_acc_llm_none_counts_call_but_not_time():
    """provider 창을 못 읽으면(None) **시간은 더하지 않는다** — 없는 값을 0 으로 더하면
    llm_ms 가 조용히 과소평가되고 잔차가 그만큼 부풀려진다. 호출 수는 올려야
    llm_usage 건수 대조로 누락을 식별할 수 있다."""
    acc = A.new_inference_acc()
    A.inference_acc_llm(acc, None)
    assert acc["llm_calls"] == 1 and acc["llm_ms"] == 0.0


def test_acc_tool_accumulates_total_and_per_tool():
    acc, tms, tn = A.new_inference_acc(), {}, {}
    A.inference_acc_tool(acc, tms, tn, "execute_sql", 120.0)
    A.inference_acc_tool(acc, tms, tn, "execute_sql", 80.0)
    A.inference_acc_tool(acc, tms, tn, "list_tables", 5.0)
    assert acc["tool_calls"] == 3 and acc["tool_ms"] == 205.0
    assert tms == {"execute_sql": 200.0, "list_tables": 5.0}
    assert tn == {"execute_sql": 2, "list_tables": 1}


def test_acc_tool_key_strips_control_chars_and_caps_length():
    """도구명은 **모델이 정하는 값**이고 이 계측이 그것을 처음으로 meta_json 의 JSON 키로
    싣는다. NUL 이 섞이면 PG jsonb 캐스트가 실패하는데 `_mirror_message` 가 예외를 삼켜
    **답변 행 자체가 조용히 사라진다**(패널 MINOR-3, 라이브 PG 재현). 제어문자를 제거한다."""
    acc, tms, tn = A.new_inference_acc(), {}, {}
    A.inference_acc_tool(acc, tms, tn, "bad\x00name\x1f", 1.0)
    key = next(iter(tms))
    assert "\x00" not in key and "\x1f" not in key
    assert key == "badname"
    A.inference_acc_tool(acc, tms, tn, "x" * 100, 1.0)
    assert max(len(k) for k in tms) <= A._INF_TOOL_KEY_MAX
    A.inference_acc_tool(acc, tms, tn, "\x00\x00", 1.0)
    assert "?" in tms, "제어문자만 남는 이름은 placeholder 로 대체돼야 한다(빈 키 금지)"


def test_acc_tool_ignores_unreadable_duration():
    """소요를 못 읽으면 호출 수까지 오염시키지 않는다."""
    acc, tms, tn = A.new_inference_acc(), {}, {}
    A.inference_acc_tool(acc, tms, tn, "t", None)
    assert acc["tool_calls"] == 0 and tms == {}


# ── 소스 계약 (배선 자체를 잠근다 — 패널이 생존시킨 변이 대응) ────────────────
_SRC = Path(A.__file__).read_text(encoding="utf-8")


def test_main_loop_wires_both_accumulators():
    """누산 호출이 메인 루프에 실제로 존재한다 — 삭제하면 계측이 통째로 죽는데
    빌더 테스트만으로는 초록으로 통과했다(패널 MAJOR-5)."""
    assert "_inf_add_llm(_LLM_LAST_PROVIDER_MS.get())" in _SRC, "LLM 누산 배선 소실"
    # 도구 누산은 `execute_tool` 호출을 감싼 **try/finally 안**에 있어야 한다 — 예외로 빠져나가도
    # 소요를 잃지 않기 위해서다(실패한 SQL 도 시간을 쓴다). `re.S` 로 느슨히 보면
    # `if True:/if False:` 로 바꿔치기해도 통과하므로 두 줄을 **인접 블록으로** 고정한다.
    m = re.search(
        r"\n(\s+)try:\n\s+tool_result = execute_tool\(db_conn, tool_name, tool_args\)\n"
        r"\1finally:\n(?:\s*#.*\n)*\s+try:\n\s+_inf_add_tool\(tool_name,",
        _SRC)
    assert m, "도구 누산이 execute_tool 의 try/finally 밖으로 나갔다(예외 경로 소요 유실)"


def test_llm_accumulation_is_in_success_branch_not_try_body():
    """누산은 `else:`(성공 분기)에 있어야 한다. `try` 본문에 두면 여기서 난 예외가
    LLM 오류 `except` 로 잡혀 **성공한 라운드가 provider 오류로 둔갑하고 run 이 중단**된다
    (패널 MINOR-1) — 계측이 답변을 깨는 것은 금지."""
    i_try = _SRC.index("response_message = _call_llm(")
    i_exc = _SRC.index("error_msg = f\"LLM 호출 오류: {e}\"")
    i_acc = _SRC.index("_inf_add_llm(_LLM_LAST_PROVIDER_MS.get())")
    assert i_acc > i_exc > i_try, "누산이 try 본문(예외 경로 앞)에 있다"


def test_provider_ms_is_measured_around_create_only():
    """`llm_ms` 는 **순수 provider 왕복**이어야 한다. `_call_llm` 전체를 재면 그 안의
    오케스트레이션(첨부 인라인 로드·messages 재조립·runtime_settings DB 읽기·llm_usage
    INSERT)이 llm_ms 로 청구돼 **잔차가 찾으려던 시간이 사라진다**(패널 MAJOR-3)."""
    i_t0 = _SRC.index("_aiops_t0 = time.perf_counter_ns()")
    i_create = _SRC.index("response = client.chat.completions.create(**kwargs)")
    i_set = _SRC.index("_LLM_LAST_PROVIDER_MS.set((time.perf_counter_ns() - _aiops_t0)")
    i_usage = _SRC.index("_record_llm_usage(model, \"agent\", response,")
    assert i_t0 < i_create < i_set < i_usage, "provider 창이 create 바깥으로 넓어졌다"


def test_reset_before_each_round_prevents_stale_reuse():
    """라운드 진입 시 None 리셋 — 없으면 실패한 호출이 **직전 라운드 왕복 시간을 재사용**한다."""
    assert "_LLM_LAST_PROVIDER_MS.set(None)" in _SRC


def test_persisted_breakdown_subtracts_redteam():
    """영속되는 쪽(`_ans_breakdown`)이 `_rt_ms` 를 실제로 넘긴다 — 0 으로 바꿔도
    초안 테스트는 초록이었다(패널 MAJOR-5)."""
    assert "_build_inference_detail(\n                    _ans_breakdown.get(\"inference_ms\"), _rt_ms," in _SRC


def test_final_breakdown_has_no_inference_detail():
    """`_final_breakdown` 에는 분해를 싣지 않는다(패널 MAJOR-1/2).

    ① `_slim_result` allowlist 가 `duration_breakdown` 을 떨어뜨리고 비정상 경로 mirror 는
    meta 를 안 실어 **어디에도 영속되지 않는 죽은 코드**였다. ② `break` 로 나온 정상 경로도
    이 줄을 지나는데 그 시점 now_perf 는 메시지 저장·큐레이션(25~35초) 뒤라 잔차가 범벅이 된다."""
    tail = _SRC[_SRC.index("_final_breakdown = _compute_duration_breakdown"):]
    assert "_final_breakdown[\"inference_detail\"]" not in tail
