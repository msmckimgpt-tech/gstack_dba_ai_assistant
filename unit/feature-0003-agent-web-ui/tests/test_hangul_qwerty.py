"""hangul-qwerty-search: 한/영 자판 교차 검색 — 서버측 회귀 잠금.

프론트 정본(`src/static/hangul-qwerty.js`)의 대응 하네스는 `tests/verify_hangul_qwerty.mjs`
이며, **아래 CASES 표는 그 하네스의 표와 같은 값**이다(한쪽만 고치는 drift 가 이 결함의
재발 기전 — mjs 하네스 (C) 축이 두 정본의 매핑표를 파일 단위로 대조한다).

검증 축:
  (A) 두벌식 변환 정확성(왕복) — 사용자 보고 예시 4건 포함.
  (B) `search_variants` 후보 계약(첫 항목 원문 · 중복 없음 · 빈 입력 = 후보 없음).
  (C) SQL 조립 계약 — 후보가 1개면 종전 SQL 과 **문자열 동치**(회귀 0)이고, 2개면
      플레이스홀더 수와 파라미터 수가 정확히 맞는다(바인딩 어긋남 = 500).
  (D) 검색 경로 통합 — 보관 대화/감사 필터가 반대 자판 후보를 WHERE 에 싣는다.
"""
from __future__ import annotations

import os
import sys

import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
for _p in (_SRC, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.hangul_qwerty import (  # noqa: E402
    hangul_to_qwerty,
    matches_search_query,
    qwerty_to_hangul,
    search_variants,
)

# mjs 하네스와 동일한 케이스 표(값 동기 필수).
CASES = [
    ("ㅎㅋ", "gz"),                 # 자모만(미완성 조합) — 사용자 예시
    ("ㅈ듀", "web"),                # 자모 + 음절 혼합 — 사용자 예시
    ("글로벌", "rmffhqjf"),          # 받침 이월 — 사용자 예시
    ("스키드", "tmzlem"),            # 받침 이월 연속 — 사용자 예시
    ("안녕하세요", "dkssudgktpdy"),
    ("까치", "Rkcl"),               # 쌍자음(Shift)
    ("닭", "ekfr"),                 # 겹받침 ㄺ
    ("값", "rkqt"),                 # 겹받침 ㅄ
    ("의외", "dmldhl"),             # 복합모음 ㅢ/ㅚ
    ("뷁", "qnpfr"),                # 복합모음 ㅞ + 겹받침 ㄺ
    ("웹", "dnpq"),
    ("제품", "wpvna"),
    ("관리", "rhksfl"),
]


@pytest.mark.parametrize("ko,en", CASES)
def test_a_hangul_to_qwerty(ko: str, en: str) -> None:
    assert hangul_to_qwerty(ko) == en


@pytest.mark.parametrize("ko,en", CASES)
def test_a_qwerty_to_hangul(ko: str, en: str) -> None:
    assert qwerty_to_hangul(en) == ko


def test_a_non_keyboard_chars_pass_through() -> None:
    # 숫자·기호·공백은 조합을 끊고 그대로 통과 — 혼합 검색어가 깨지지 않는다.
    assert qwerty_to_hangul("_1 ") == "_1 "
    assert qwerty_to_hangul("rk-2") == "가-2"
    assert hangul_to_qwerty("가-2") == "rk-2"


def test_b_variants_contract() -> None:
    assert search_variants("") == []
    assert search_variants(None) == []
    v = search_variants("ㅎㅋ")
    assert v[0] == "ㅎㅋ" and "gz" in v
    v2 = search_variants("Web")
    assert v2[0] == "web"                    # 원문은 소문자 정규화
    assert len(set(v2)) == len(v2)           # 중복 없음
    assert len(search_variants("12-34")) == 1  # 변환 대상 없으면 후보 1개


def test_b_short_variant_is_dropped() -> None:
    """짧은 후보는 원래 맞던 검색을 오염시킨다 — `dk` → `아` 는 "글로벌 라이브" 까지 잡았다."""
    assert search_variants("dk") == ["dk"]          # 1자 변환 후보 미채택
    assert search_variants("a") == ["a"]
    # 반대 방향 — 1자 원문 `가` 가 `rk` 로 확장되면 marketing·worker 가 잡힌다(codex P2).
    assert search_variants("가") == ["가"]
    assert "gz" in search_variants("ㅎㅋ")           # 2자 이상은 채택(요청 예시 전부 해당)


def test_b_matches_search_query() -> None:
    assert matches_search_query("MV_QA 제품", "mv_qa")          # 원문 매칭 보존
    assert matches_search_query("글로벌 서비스", "rmffhqjf")     # 영문 오타 → 한글
    assert matches_search_query("gz-prod", "ㅎㅋ")               # 한글 오타 → 영문
    assert not matches_search_query("글로벌", "zzzz")
    assert matches_search_query("무엇이든", "")                  # 빈 검색어 = 전체 통과


def test_c_like_patterns_and_clause_single_variant_is_byte_equivalent() -> None:
    """후보가 1개인 검색어는 종전 SQL 과 문자열 동치 — 회귀 0의 기계 단언."""
    from routers._conv_store import _like_any_clause, _search_like_patterns

    pats = _search_like_patterns("12-34")           # 변환 후보 없음 → 1개
    assert pats == ["%12-34%"]
    assert _like_any_clause("c.topic", len(pats)) == "(c.topic LIKE %s ESCAPE '!')"
    assert _like_any_clause("c.topic", len(pats), "ILIKE") == "(c.topic ILIKE %s ESCAPE '!')"


def test_c_like_clause_placeholder_count_matches_params() -> None:
    from routers._conv_store import _like_any_clause, _search_like_patterns

    pats = _search_like_patterns("rmffhqjf")        # 원문 + '글로벌'
    assert len(pats) == 2 and "%글로벌%" in pats
    clause = _like_any_clause("m.content", len(pats), "ILIKE")
    assert clause.count("%s") == len(pats)          # 바인딩 수 = 후보 수
    assert clause.startswith("(") and clause.endswith(")")
    assert " OR " in clause


def test_c_like_escape_applied_per_variant() -> None:
    """SECURITY §8.3 — `%`/`_`/`!` 는 각 후보에서 리터럴로 escape 된다."""
    from routers._conv_store import _search_like_patterns

    pats = _search_like_patterns("a%b_c!d")
    assert pats[0] == "%a!%b!_c!!d%"


def test_d_archive_search_likes_carries_alternate_layout() -> None:
    from routers.admin_conversations import _archive_search_likes

    likes = _archive_search_likes("rmffhqjf")
    assert likes[0] == "%rmffhqjf%"
    assert "%글로벌%" in likes
    # 변환 대상이 없으면 후보 1개.
    assert _archive_search_likes("12-34") == ["%12-34%"]
    # SECURITY §8.3 — `%`/`_`/`!` 는 **각 후보에서** 리터럴로 escape (codex P2 반영).
    esc = _archive_search_likes("a%b_c")
    assert esc[0] == "%a!%b!_c%"
    assert all(("!%" in p and "!_" in p) for p in esc), esc


def test_d_audit_filter_where_expands_variants() -> None:
    """감사 로그 q 필터 — ActionCode/ResourceId 는 영문 코드라 한글 오타 흡수가 특히 유효."""
    from routers._audit_infra import _audit_compose_where

    where, args = _audit_compose_where(scope="any", account_id=1, params={"q": "ㅁㅅㅅㅁ초"})
    assert where.count("%s") == len(args)
    assert any("attach" in str(a) for a in args), args


def test_d_audit_filter_single_variant_unchanged() -> None:
    from routers._audit_infra import _audit_compose_where

    where, args = _audit_compose_where(scope="any", account_id=1, params={"q": "12-34"})
    assert "(ActionCode LIKE %s ESCAPE '!' OR ResourceId LIKE %s ESCAPE '!')" in where
    assert args == ["%12-34%", "%12-34%"]


def test_d_audit_filter_escapes_like_metachars() -> None:
    """SECURITY §8.3 — 종전 감사 필터는 escape 가 없어 `%` 가 와일드카드로 샜다 (codex P2)."""
    from routers._audit_infra import _audit_compose_where

    _where, args = _audit_compose_where(scope="any", account_id=1, params={"q": "a%b_c"})
    assert args[0] == "%a!%b!_c%"
    assert all(("!%" in a and "!_" in a) for a in args), args
    assert _where.count("%s") == len(args)          # 플레이스홀더 = 파라미터


def test_d_graph_search_variants_helper() -> None:
    """그래프 검색(feature-0002 metadata_graph)도 같은 정본 매핑표를 쓴다."""
    sys.path.insert(0, os.path.join(_REPO, "unit", "feature-0002-agent-core", "src"))
    from modules.metadata_graph import _layout_query_variants

    v = _layout_query_variants("tmzlem")
    assert v[0] == "tmzlem" and "스키드" in v
    assert _layout_query_variants("") == [""]   # 빈 입력도 폴백 1개(호출부 무해)
