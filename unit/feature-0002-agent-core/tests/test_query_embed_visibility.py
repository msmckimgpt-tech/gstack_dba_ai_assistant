"""feature-0035 (qembed-vis): 질의 임베딩 강등 가시화 + 타임아웃 재조정 회귀 잠금.

라이브 실측(2026-07-31): 임베딩 백엔드가 대량 백필(시그니처 전수 재계산 48,226건)로 포화된
창에서 답변 2건이 각각 20,587ms·20,022ms 를 쓰고 **타임아웃 → trigram 폴백** 했다. warm 은
p50 206ms / p90 215ms / max 429ms(47 표본). 즉 20s 타임아웃은 성공을 건지는 값이 아니라
실패를 늦게 확인하는 값이었고, 그 사이 **강등이 완전히 무음**이라 2주간 드러나지 않았다.
"""
import json
import re
from pathlib import Path

import agent_core as A


_SRC = Path(A.__file__).read_text(encoding="utf-8")


def _publish(kt: dict) -> dict:
    """`_build_knowledge_context` 말미의 발행 필터를 그대로 재현 — 소스에서 추출해 실행한다.

    §18.8 패널 BLOCKER-1: 종전 테스트는 전부 소스 문자열 검색이라 **발행 단계에서 값이
    버려지는 것**을 못 봤다. 필터 표현식을 소스에서 뽑아 실제로 평가해 그 계층을 잠근다."""
    m = re.search(r"_KNOWLEDGE_TIMINGS\.set\(\{\s*(k: v for k, v in _kt\.items\(\) if [^}]+?)\s*\}\)", _SRC, re.S)
    assert m, "발행 필터를 소스에서 찾지 못했다(리팩터링 시 이 테스트를 갱신할 것)"
    return eval("{" + m.group(1) + "}",  # noqa: S307 — 소스에서 추출한 자기 코드
                {"_INIT_DERIVED_KEYS": A._INIT_DERIVED_KEYS}, {"_kt": kt})


def test_degraded_flag_survives_the_publication_filter():
    """**강등(0.0)이 발행 필터를 통과해야 한다.**

    §18.8 패널 BLOCKER-1(런타임 실증): 발행부의 `v >= 0.1` 은 소요 잡음 제거용인데, 상태
    플래그 0.0 이 여기 걸려 **탈락**했다. 성공(1.0)만 통과하니 대시보드가 언제나 "강등 0%"
    라는 거짓 안심을 보고했다 — 종전의 무음보다 나쁘다(운영자가 신호가 있다고 믿는다).
    게다가 키의 '존재' 가 성공을 뜻하게 돼 시도-안-함과 강등을 구분하려던 게이트가 무효화된다."""
    pub_ok = _publish({"glossary_ms": 5.1, "query_embed_ok": 1.0})
    pub_bad = _publish({"glossary_ms": 5.1, "query_embed_ok": 0.0})
    assert pub_ok.get("query_embed_ok") == 1.0
    assert "query_embed_ok" in pub_bad, "강등(0.0)이 발행 필터에서 탈락 — 거짓 안심 보고"
    assert pub_bad["query_embed_ok"] == 0.0
    # 소요 잡음 제거는 그대로 살아 있어야 한다(플래그만 예외).
    assert "tiny_ms" not in _publish({"tiny_ms": 0.05, "query_embed_ok": 0.0})


def test_ok_flag_is_numeric_and_json_safe():
    """§3b 는 `jsonb_each_text(init_detail)` 로 **전 키**를 `::float` 캐스트한다 — bool/문자열이면
    `invalid input syntax` 로 섹션이 통째로 죽는다(feature-0034 패널 MAJOR-1 라이브 재현).
    소스 문자열이 아니라 **직렬화 후 타입**으로 확인한다(패널 MINOR-5: 종전 테스트는 정확한
    소스 철자를 요구해 무해한 리팩터링에도 깨지면서 정작 실제 타입은 안 봤다)."""
    for v in (1.0, 0.0):
        d = A._build_init_detail(1_000.0, {"mem_setup_ms": 100.0, "query_embed_ok": v})
        rt = json.loads(json.dumps(d))
        got = rt["query_embed_ok"]
        assert isinstance(got, (int, float)) and not isinstance(got, bool), \
            f"query_embed_ok 가 {type(got).__name__} — ::float 캐스트를 깨뜨린다"
        assert float(got) == v


def test_ok_flag_excluded_from_residual_leaves():
    """플래그는 소요(ms)가 아니므로 잔차 leaf 에서 빼야 한다 — 안 빼면 잔차가 1ms 어긋난다."""
    assert "query_embed_ok" in A._INIT_DERIVED_KEYS
    with_flag = A._build_init_detail(1_000.0, {"mem_setup_ms": 100.0, "query_embed_ok": 1.0})
    without = A._build_init_detail(1_000.0, {"mem_setup_ms": 100.0})
    assert with_flag["init_other_ms"] == without["init_other_ms"] == 900.0


def test_ok_flag_recorded_after_attempt_and_before_publication():
    """순서: 임베딩 시도 → 플래그 기록 → 발행.

    §18.8 패널 MAJOR-3: 종전엔 앞의 두 위치만 비교해, 발행문을 그 사이로 옮기는 변이가
    **생존**했다(플래그가 영원히 breakdown 에 도달 못 함). 세 지점을 모두 순서로 잠근다."""
    i_embed = _SRC.index("_shared_qvec = _embed_query_vector(")
    i_flag = _SRC.index('_kt["query_embed_ok"]')
    i_pub = _SRC.index("_KNOWLEDGE_TIMINGS.set(")
    assert i_embed < i_flag < i_pub, "발행이 플래그 기록보다 앞에 있다 — 플래그가 유실된다"


def test_flag_gated_on_same_condition_as_the_attempt():
    """임베딩을 **시도조차 안 한** 경우(빈 질문·양 기능 OFF)는 강등이 아니다 — 키를 남기면
    강등율이 과대보고된다. 시도 조건(`_SQ_EN or _AR_EN`)과 동일 게이트여야 한다."""
    seg = _SRC[_SRC.index('_kt_mark("query_embed_ms")'):]
    seg = seg[:seg.index('_kt["query_embed_ok"]') + 200]
    assert "(_SQ_EN or _AR_EN)" in seg, "시도 조건과 다른 게이트로 기록하고 있다"


def test_query_embed_timeout_covers_largest_real_input():
    """타임아웃은 **실제 최대 입력**을 정상 백엔드에서 처리할 여유가 있어야 한다.

    §18.8 패널 MAJOR-1: 초안의 5s 는 16자 질의만 재고 정한 값이라 반증됐다 — 지연은 입력
    길이에 비례한다(재현: 5,712자 4,172ms; 패널은 6KB 3.7~5.4s). 라이브 90일 최대 사용자
    메시지가 5,996자라 5s 는 경계였다(패널 6KB 3회 중 1회 폴백). 관측된 최대-실입력 지연
    ~5.4s 의 2배 이상을 요구한다."""
    from shared import config as cfg
    OBSERVED_MAX_REAL_INPUT_SEC = 5.4   # 5,996자(라이브 최대) 근방 실측 상한
    assert cfg.AGENT_KB_QUERY_EMBED_TIMEOUT_SEC >= OBSERVED_MAX_REAL_INPUT_SEC * 2, \
        "최대 실입력 지연의 2배 미만 — 정상 백엔드에서도 불필요한 강등이 난다"
    assert cfg.AGENT_KB_QUERY_EMBED_TIMEOUT_SEC < 20, \
        "20s 는 포화 시 완료되지도 않으면서 낭비만 크다(재조정 이유가 사라짐)"


def test_console_spec_default_matches_code_default():
    """§18.8 패널 MAJOR-2: spec 기본값이 코드와 어긋나면 콘솔이 구값을 표시하고,
    운영자가 '초기화' 를 누르면 그 구값이 override 로 기록돼 **변경이 조용히 되돌아간다**.
    실제로 초안은 코드 5 / 콘솔 20 이었다."""
    from shared import config as cfg
    from shared import runtime_settings as rs
    spec = rs.spec_for("AGENT_KB_QUERY_EMBED_TIMEOUT_SEC")
    assert spec, "콘솔 spec 에 이 키가 없다"
    assert spec["default"] == cfg.AGENT_KB_QUERY_EMBED_TIMEOUT_SEC, \
        f"콘솔 spec {spec['default']} != 코드 {cfg.AGENT_KB_QUERY_EMBED_TIMEOUT_SEC}"
    # 하한은 llm.py 의 `max(5, …)` 바닥 이상이어야 한다 — 미만이면 무음 불일치.
    assert spec["minimum"] >= 5, "콘솔 하한이 llm.py 의 실효 바닥(5)보다 낮다"


def test_snapshot_section_consumes_the_flag():
    """§18.8 패널 MAJOR-3: §3b-1 을 통째로 지우는 변이가 생존했다 — 플래그의 유일한
    소비처가 사라져도 아무도 몰랐다."""
    snap = (Path(A.__file__).resolve().parents[3] / "bin" / "perf-snapshot.sh").read_text(encoding="utf-8")
    assert "query_embed_ok" in snap, "perf-snapshot 이 플래그를 더는 읽지 않는다"
    assert "3b-1" in snap


def test_config_records_the_input_length_dependence():
    """근거를 코드에 남긴다 — 특히 **입력 길이 의존성**. 초안이 이걸 빠뜨려 5s 로 잘못
    정했으므로, 다음 조정자가 같은 실수를 하지 않도록 명시한다."""
    cfg_src = (Path(A.__file__).resolve().parents[3] / "shared" / "config.py").read_text(encoding="utf-8")
    assert "입력\n#   길이에 비례" in cfg_src or "입력 길이에 비례" in cfg_src
    assert "5,996자" in cfg_src, "라이브 최대 입력 근거가 없다"
