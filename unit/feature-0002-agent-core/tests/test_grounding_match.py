"""2026-09-01 — grounding 매칭: 한도가 «매칭 후보»에 걸리고, 판정이 «낱말»로 이뤄진다.

## 이 테스트가 잠그는 사고 2건 (GZ_QA_G 라이브 실측)

배포본에서 실제 GZ_QA_G task 로 `get_task_context` 를 돌려 확인한 것들이다.

### ① 짧은 용어가 상시 탈락했다

`_fetch_glossary` 가 `ORDER BY length(term) DESC LIMIT 200` 으로 **scope 전체**를 잘라 읽고
Python 이 그 안에서 매칭했다. GZ_QA_G 읽기 캐스케이드는 239행이라 **39행이 항상 밖**이었고,
길이 내림차순이라 잘리는 쪽은 언제나 가장 짧은 것 —
`AID`·`CCU`·`CID`·`PvE`·`재화`·`캐시`·`드롭`·`업적`·`복합키`·`선택도` …
DBA 질문에서 제일 자주 쓰는 약어가 구조적으로 제외됐다. 로그도 note 도 없었다.
(모듈 docstring 이 「follow-up: SQL-side 매칭」으로 예고해 둔 바로 그 조건이 충족됐다.)

### ② 부분 문자열 매칭이 남의 제품 항목을 끌어왔다

판정이 `str(term).lower() in msg` 였다. GZ_QA_G 질문의 `BillingType` 이 **DK온라인** ENUM 의
컬럼명 `Type` 에 걸려, 그 제품 전용 코드 설명이 GZ_QA_G 프롬프트에 실렸다.
「제품 고유 내용이 특정 scope 를 넘어 동작한다」는 원 요청의 마찰이 ENUM 축에서 재현된 것이다.
"""
from __future__ import annotations

from modules import kb_glossary as G


# ── ② 낱말 경계 ───────────────────────────────────────────────────────────────
def test_ascii_identifier_needs_word_boundary():
    """식별자에 영숫자가 붙어 있으면 그 이름의 **일부**이지 그 이름이 아니다."""
    assert not G.term_occurs_as_word("Type", "billingsummary 의 billingtype 은?")
    assert not G.term_occurs_as_word("CID", "acidity 컬럼 의미가 뭐야")
    assert not G.term_occurs_as_word("PvE", "pverr 로그가 쌓이는데")
    assert not G.term_occurs_as_word("AID", "raidlog 테이블 구조")
    # 정상 등장은 살아야 한다 — 경계를 좁히다 진짜 매칭을 잃으면 고친 게 아니다.
    assert G.term_occurs_as_word("Type", "type 컬럼 알려줘")
    assert G.term_occurs_as_word("PvE", "pve 매칭 로그")
    assert G.term_occurs_as_word("BillingType", "billingsummary 의 billingtype 은?")


def test_korean_particle_suffix_is_allowed():
    """뒤에 붙는 한글은 **조사**다 — 막으면 정상 표현이 전부 깨진다.

    이게 경계 규칙을 비대칭으로 둔 이유다. `파티셔닝 키도`·`증분 복제와`·`재화를` 는
    모두 조사가 붙은 정상 등장이다.
    """
    assert G.term_occurs_as_word("파티셔닝 키", "파티셔닝 키도 설명해주세요")
    assert G.term_occurs_as_word("증분 복제", "증분 복제와 차이는?")
    assert G.term_occurs_as_word("재화", "재화를 정산해줘")
    assert G.term_occurs_as_word("캐시", "캐시가 부족합니다")


def test_korean_prefix_boundary_blocks_compound():
    """앞에 한글이 붙으면 다른 낱말이다 — 오탐은 이 방향에서 난다."""
    assert not G.term_occurs_as_word("재화", "아이템 소재화 처리 절차")
    assert not G.term_occurs_as_word("업적", "기업적 관점에서 보면")


def test_mixed_and_punctuation_boundaries():
    """구분자(`.`·공백)는 경계다 — 정규화된 FQN 안의 이름도 매칭돼야 한다."""
    assert G.term_occurs_as_word("steam_billing_log", "billing_web.steam_billing_log 조회")
    assert G.term_occurs_as_word("config", "config는 어디에")      # 영숫자 끝 + 한글 조사
    assert G.term_occurs_as_word("동적 SQL", "동적 sql을 써도 되나")  # 한글 시작 + 영숫자 끝 + 조사
    assert not G.term_occurs_as_word("SQL", "mysqld 프로세스")      # 영숫자로 둘러싸임


def test_empty_inputs_are_not_matches():
    for t, m in [("", "무엇이든"), ("용어", ""), (None, "무엇이든"), ("용어", None)]:
        assert not G.term_occurs_as_word(t, m or "")


# ── ① 한도는 «매칭 후보»에 걸린다 ──────────────────────────────────────────────

def _where_of(sql: str) -> str:
    """SQL 에서 WHERE ~ ORDER BY 사이를 떼어낸다(연접항 집합 단언용)."""
    body = sql.split(" WHERE ", 1)[1]
    return body.split(" ORDER BY ", 1)[0]


class _Cur:
    def __init__(self, state):
        self._s = state

    def execute(self, sql, params=None):
        self._s["sql"].append((sql, params))

    def fetchall(self):
        return self._s["rows"]

    def close(self):
        pass


class _Conn:
    def __init__(self, rows=()):
        self.state = {"sql": [], "rows": list(rows)}

    def cursor(self):
        return _Cur(self.state)


def test_glossary_query_filters_by_message_in_sql():
    """질문을 주면 **SQL 이 후보를 좁힌다** — 그래야 LIMIT 이 전체가 아니라 후보에 걸린다.

    ⚠ 반환값만 보면 이 계약은 검사되지 않는다(대역은 SQL 무관하게 같은 행을 준다).
      실제로 실린 **SQL 술어와 파라미터**를 단언한다.
    """
    conn = _Conn()
    G._fetch_glossary(conn, ["product.gz_qa_g", "common"], message="AID 가 뭐야")
    sql, params = conn.state["sql"][0]
    # ⚠ 「술어가 들어 있다」만 보면 `(position(...) > 0 OR TRUE)` 같은 **동어반복 약화**가
    #   그대로 통과한다(2026-09-01 뮤테이션에서 실증). 연접항 **집합**을 단언한다.
    conjuncts = {c.strip() for c in _where_of(sql).split(" AND ")}
    assert conjuncts == {"scope_key = ANY(%s)", "position(lower(term) in %s) > 0"}, (
        f"WHERE 연접항이 기대와 다르다(술어가 약화됐을 수 있다): {conjuncts!r}")
    assert "aid 가 뭐야" in params, "소문자화된 질문이 파라미터로 실리지 않았다"
    assert params[-1] == G._GLOSSARY_READ_LIMIT


def test_enum_query_filters_by_message_in_sql():
    conn = _Conn()
    G._fetch_enums(conn, ["product.gz_qa_g", "common"], message="status 코드")
    sql, params = conn.state["sql"][0]
    conjuncts = {c.strip() for c in _where_of(sql).split(" AND ")}
    assert conjuncts == {
        "scope_key = ANY(%s)",
        "(position(lower(column_name) in %s) > 0  OR position(lower(table_name) in %s) > 0)",
    }, f"WHERE 연접항이 기대와 다르다: {conjuncts!r}"
    assert params.count("status 코드") == 2


def test_no_message_keeps_full_read_backward_compatible():
    """`message` 미지정은 종전대로 전체 읽기 — 다른 호출부를 깨지 않는다."""
    conn = _Conn()
    G._fetch_glossary(conn, ["common"])
    sql, _ = conn.state["sql"][0]
    assert "position(" not in sql


def test_limit_hit_is_logged_not_silent(caplog):
    """한도에 닿으면 **말한다**. 무음 절단이 이 결함을 오래 안 보이게 한 원인이다(§16.7 G9-b)."""
    rows = [(f"term{i}", "d") for i in range(G._GLOSSARY_READ_LIMIT)]
    conn = _Conn(rows)
    with caplog.at_level("WARNING", logger="kb_glossary"):
        G._fetch_glossary(conn, ["common"], message="term1")
    assert any("glossary_read_limit_hit" in r.message for r in caplog.records), \
        "한도 도달이 조용히 지나갔다"


def test_loader_passes_message_down(monkeypatch):
    """`load_glossary_enum_context` 가 질문을 **두 fetch 에 모두** 넘긴다(배선).

    헬퍼가 옳아도 진입점이 안 넘기면 한도는 그대로 scope 전체에 걸린다.
    """
    seen = {}

    def _spy_gloss(c, s, message=None, role_key=None):
        seen["g"] = message
        return []

    def _spy_enum(c, s, message=None):
        seen["e"] = message
        return []

    monkeypatch.setattr(G, "_ro_conn", lambda conn: (_Conn(), True))
    monkeypatch.setattr(G, "_fetch_glossary", _spy_gloss)
    monkeypatch.setattr(G, "_fetch_enums", _spy_enum)
    G.load_glossary_enum_context("Status 코드 알려줘", scope_key="product.gz_qa_g")
    assert seen.get("g") == "status 코드 알려줘", f"용어 fetch 에 질문 미전달: {seen!r}"
    assert seen.get("e") == "status 코드 알려줘", f"ENUM fetch 에 질문 미전달: {seen!r}"


# ── 배선 — 경계 판정이 **진입점에서** 실제로 쓰이는가 ─────────────────────────
#
# ⚠ 위 경계 테스트들은 `term_occurs_as_word` 를 **직접** 부른다. 그래서
#   `load_glossary_enum_context` 안의 판정을 부분일치로 되돌리는 뮤턴트가 **살아남았다**
#   (2026-09-01 실증, 이 세션에서 세 번째 같은 형태). 헬퍼가 옳은 것과 진입점이 그걸 쓰는 것은
#   서로를 대신하지 못한다.
class _LoaderConn:
    """`_fetch_*` 가 돌려줄 행을 직접 스크립팅 — SQL 은 보지 않고 **출력**만 본다."""

    def __init__(self, glossary=(), enums=()):
        self.g, self.e = list(glossary), list(enums)


def _wire_loader(monkeypatch, glossary, enums):
    monkeypatch.setattr(G, "_ro_conn", lambda conn: (object(), False))
    monkeypatch.setattr(G, "_fetch_glossary",
                        lambda c, s, message=None, role_key=None: list(glossary))
    monkeypatch.setattr(G, "_fetch_enums", lambda c, s, message=None: list(enums))


def test_loader_excludes_substring_false_positive_enum(monkeypatch):
    """진입점이 조립한 본문에 **남의 제품 ENUM 이 들어오지 않는다**.

    라이브 재현: GZ_QA_G 질문의 `BillingType` 이 DK온라인 ENUM 컬럼 `Type` 에 부분일치해
    그 제품 전용 코드 설명이 GZ_QA_G 프롬프트에 실렸다.
    """
    _wire_loader(monkeypatch, glossary=[], enums=[
        ("Achievement", "Type", "1", "[DK온라인] 특수 업적"),          # 오탐 후보
        ("billingsummary", "BillingType", "Payment", "결제"),          # 정탐
    ])
    out = G.load_glossary_enum_context("billingsummary 의 BillingType 은?",
                                       scope_key="product.gz_qa_g")
    assert "BillingType" in out and "결제" in out, "정상 매칭까지 잃었다"
    assert "DK온라인" not in out and "Achievement" not in out, (
        f"부분일치로 남의 제품 ENUM 이 실렸다:\n{out}")


def test_loader_excludes_substring_false_positive_term(monkeypatch):
    """용어 축도 같다 — `소재화` 안의 `재화` 를 끌어오지 않는다."""
    _wire_loader(monkeypatch, glossary=[("재화", "게임 내 통화"),
                                        ("소재", "제작 재료")], enums=[])
    out = G.load_glossary_enum_context("아이템 소재화 처리 절차", scope_key="product.gz_qa_g")
    assert "게임 내 통화" not in out, f"«소재화» 안의 «재화» 가 매칭됐다:\n{out}"


def test_loader_keeps_korean_particle_match(monkeypatch):
    """경계를 좁히다 조사가 붙은 정상 등장을 잃지 않는다(회귀 방향)."""
    _wire_loader(monkeypatch, glossary=[("파티셔닝 키", "분할 기준 컬럼")], enums=[])
    out = G.load_glossary_enum_context("파티셔닝 키도 설명해주세요", scope_key="product.gz_qa_g")
    assert "분할 기준 컬럼" in out, f"조사가 붙자 매칭을 잃었다:\n{out}"
