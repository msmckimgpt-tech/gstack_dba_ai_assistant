"""0057 — 용어 통용범위(term_tier) 축 + 중복 억제 단위 테스트.

## 무엇을 지키는 테스트인가

사용자 신고(2026-09-01): 「관리 콘솔 > 메타데이터 > 용어 사전」에 **일반적인 DB 용어**(복제
이벤트·Online DDL·시점 복구)가 특정 제품 scope 로 제한 등록되고, 같은 개념이 제품마다 중복
등록된다.

근본 원인은 **축의 비대칭**이었다 — 읽기는 `[제품, common]` 2단인데 쓰기는 제품 하나뿐이라
전역 티어가 쓰기에 없었고, 프롬프트가 confidence 를 「명확성 AND **재사용성**」으로 정의해
**범용일수록 점수가 올라 가장 좁은 scope 에 자동등록**됐다.

아래 테스트는 그 두 가지가 다시 열리지 않게 잠근다. **행위**를 검사한다(소스 문자열이 아니라)
— 가짜 커넥션에 실제로 어떤 SQL·파라미터가 갔는지, 라우터가 무엇을 반환했는지로 판정한다
(AGENTS.md §16.7 G11 — 소스 텍스트 단언은 자기 주석이 자기 단언을 통과시킨다).
"""
from modules import kb_glossary as G


# ── 가짜 커넥션 — 쿼리 종류별로 라우팅한다 ────────────────────────────────────────
#
# 단순히 "SELECT 면 이 행" 이 아니라 **대상 테이블별로** 답을 갈라야 한다. 이 cycle 의 라우터는
# `glossary_feedback`(판정 이력) 과 `kb_glossary`(중복) 를 **둘 다** 조회하고 그 두 답이 서로
# 다른 분기를 만들기 때문에, 한 벌로 답하면 테스트가 분기를 구별하지 못한다.
class _FakeCursor:
    def __init__(self, state):
        self._state = state
        self._rows = []
        self._one = None

    def execute(self, sql, params=None):
        self._state["captured"].append((sql, params))
        up = sql.strip().upper()
        self._one, self._rows = None, []
        # ⚠ ENUM 분기를 **먼저** 본다 — `ENUM_FEEDBACK` 은 `GLOSSARY_FEEDBACK` 을 포함하지
        #   않지만, 두 축이 같은 상태 키(`settled`/`duplicate`)를 공유하므로 라우팅을 한
        #   곳에 모아 두 축의 테스트가 같은 fake 를 쓰게 한다(대역이 갈리면 한쪽만 검사된다).
        if up.startswith("SELECT") and "ENUM_FEEDBACK" in up:
            self._one = self._state.get("settled")
        elif up.startswith("INSERT INTO ENUM_DICTIONARY"):
            self._state["inserted"].append(params)
            self._one = (self._state["next_id"],)
        elif up.startswith("SELECT") and "ENUM_DICTIONARY" in up:
            self._one = self._state.get("duplicate")
        elif up.startswith("INSERT INTO ENUM_FEEDBACK"):
            self._state["queued"].append(params)
        elif up.startswith("SELECT") and "GLOSSARY_FEEDBACK" in up:
            self._one = self._state.get("settled")
        elif up.startswith("SELECT") and "KB_GLOSSARY" in up:
            self._one = self._state.get("duplicate")
        elif up.startswith("INSERT INTO KB_GLOSSARY"):
            self._state["inserted"].append(params)
            self._one = (self._state["next_id"],)
        elif up.startswith("INSERT INTO GLOSSARY_FEEDBACK"):
            self._state["queued"].append(params)

    @property
    def rowcount(self):
        return 1

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _FakeConn:
    def __init__(self, *, settled=None, duplicate=None, next_id=101):
        self.state = {"captured": [], "inserted": [], "queued": [],
                      "settled": settled, "duplicate": duplicate, "next_id": next_id}

    def cursor(self):
        return _FakeCursor(self.state)

    def _sql_hits(self, needle):
        return [c for c in self.state["captured"] if needle.upper() in c[0].upper()]


# ── 표면형 정규화 — 표기변형을 한 키로 접는다 ─────────────────────────────────────
def test_normalize_term_surface_folds_variants():
    """라이브에서 실제로 별 행이 됐던 변형들이 같은 키로 접혀야 한다.

    `멱등성` 한 개념이 7행(4 scope)까지 불어난 것이 이 함수가 없던 결과다.
    """
    assert (G.normalize_term_surface("멱등성")
            == G.normalize_term_surface("멱등성 (Idempotency)")
            == G.normalize_term_surface("멱등성(idempotent)"))
    assert (G.normalize_term_surface("복합 PK")
            == G.normalize_term_surface("복합 PK (Composite Primary Key)"))
    assert (G.normalize_term_surface("CTE(공통 테이블 표현식)")
            == G.normalize_term_surface("CTE (Common Table Expression)"))
    assert G.normalize_term_surface("user_id") == G.normalize_term_surface("userID")
    # 전각 괄호도 같은 규칙 — 한국어 입력에서 흔하다.
    assert G.normalize_term_surface("배치 크기（BatchSize）") == G.normalize_term_surface("배치 크기")


def test_normalize_term_surface_keeps_distinct_terms_distinct():
    """접기가 과하면 서로 다른 용어가 한 행으로 합쳐진다 — 그 방향도 막는다."""
    assert G.normalize_term_surface("튜닝인덱스") != G.normalize_term_surface("인덱스")
    assert G.normalize_term_surface("LogType") != G.normalize_term_surface("LogTime")


# ── 결정적 강등 — 사용자가 지적한 3종이 반드시 general 이어야 한다 ────────────────
def test_reported_general_terms_are_demoted_even_when_llm_says_product():
    """사용자 신고 예시 3종 + 라이브 오등록분. **LLM 이 product 라 해도** general 로 내린다.

    프롬프트만 고치면 같은 실수가 다시 통과한다 — 재발 클래스는 구조 가드로 잠근다
    (AGENTS.md §16.7 G10).
    """
    for term in ("복제 이벤트", "Online DDL", "시점 복구",
                 "트랜잭션", "트랜잭션 롤백", "복합 인덱스 (Composite Index)",
                 "CTE(공통 테이블 표현식)", "실행 계획 (EXPLAIN)", "B-tree 인덱스",
                 "암묵적 커밋", "증분 복제", "information_schema", "멱등성(Idempotency)"):
        tier, reason = G.classify_term_tier(term, G.TIER_PRODUCT)
        assert tier == G.TIER_GENERAL, f"{term!r} 이(가) general 로 판정되지 않았다 ({reason})"


def test_bare_sql_keywords_are_general():
    for term in ("SELECT", "LEFT JOIN", "ORDER BY", "ALTER TABLE"):
        assert G.classify_term_tier(term, G.TIER_PRODUCT)[0] == G.TIER_GENERAL


def test_product_specific_terms_are_not_demoted():
    """오강등 방지 — 라이브의 실제 제품 고유 용어가 general 로 떨어지면 사전이 비어 간다.

    특히 `튜닝인덱스`·`인덱스 비중` 은 '인덱스' 부분일치로 걸면 잃는다. 그래서 판정은
    **정규화 전체일치**여야 한다.
    """
    for term in ("튜닝인덱스", "인덱스 비중", "in_weapontuning_index (튜닝인덱스)",
                 "SponsorCode", "CharacterID", "characterbounty", "활성 후원",
                 "TF_Raw_JSON", "SteamOrderID", "아이템 마스터 데이터", "WorldID",
                 "CCU (동시접속자수)", "sp_InsertSteamBillingLog"):
        tier, reason = G.classify_term_tier(term, G.TIER_PRODUCT)
        assert tier == G.TIER_PRODUCT, f"{term!r} 이(가) 잘못 강등됐다 ({reason})"


def test_llm_tier_is_used_when_lexicon_is_silent():
    assert G.classify_term_tier("사내 표준 코드체계", G.TIER_ORG)[0] == G.TIER_ORG
    # 판정 불가는 **가장 좁은 범위**로 접는다 — 잘못해서 전역에 넣는 쪽이 피해가 크다.
    assert G.classify_term_tier("사내 표준 코드체계", None)[0] == G.TIER_PRODUCT
    assert G.classify_term_tier("사내 표준 코드체계", "garbage")[0] == G.TIER_PRODUCT


def test_scope_for_tier_routes_org_and_general_to_global():
    assert G.scope_for_tier(G.TIER_PRODUCT, "product.gz_qa_g") == "product.gz_qa_g"
    assert G.scope_for_tier(G.TIER_ORG, "product.gz_qa_g") == G.GLOBAL_SCOPE
    assert G.scope_for_tier(G.TIER_GENERAL, "product.gz_qa_g") == G.GLOBAL_SCOPE


# ── 라우터 — 이 cycle 의 핵심 계약 ────────────────────────────────────────────────
def test_general_term_is_not_written_to_glossary_but_is_recorded():
    """범용 용어는 **사전에 쓰이지 않고**, 그 사실은 큐에 남는다.

    조용히 버리면 「요즘 등록될 용어가 없다」와 구별되지 않고 오분류를 되돌릴 수도 없다.
    """
    conn = _FakeConn()
    out = G.auto_promote_or_queue(
        conn, "product.gz_qa_g", "복제 이벤트", "복제가 전파하는 변경 이벤트.",
        confidence=0.99, term_tier=G.TIER_PRODUCT)
    assert out == G.STATUS_SKIPPED_GENERAL
    assert conn.state["inserted"] == [], "범용 용어가 kb_glossary 에 기록됐다"
    assert len(conn.state["queued"]) == 1
    q = conn.state["queued"][0]
    assert q[0] == G.GLOBAL_SCOPE, "범용 후보는 제품마다 중복 기록되지 않게 전역 scope 에 남긴다"
    assert q[5] == G.STATUS_SKIPPED_GENERAL
    assert q[10] == G.TIER_GENERAL


def test_org_term_goes_to_global_scope_and_never_auto_promotes():
    """전역 후보는 confidence 가 아무리 높아도 **검토 큐**를 거친다.

    전역 사전은 모든 제품 프롬프트에 주입되므로 blast radius 가 제품의 N배다 —
    「고신뢰=자동등록」을 더 넓은 면에 반복하면 지금 고치는 실수를 규모만 키워 재현한다.
    """
    conn = _FakeConn()
    out = G.auto_promote_or_queue(
        conn, "product.gz_qa_g", "사내 표준 코드체계", "전사 공통 코드 부여 규칙.",
        confidence=0.99, term_tier=G.TIER_ORG)
    assert out == "pending"
    assert conn.state["inserted"] == [], "전역 후보가 자동 등록됐다"
    q = conn.state["queued"][0]
    assert q[0] == G.GLOBAL_SCOPE and q[5] == "pending" and q[10] == G.TIER_ORG


def test_product_term_auto_promotes_into_product_scope():
    conn = _FakeConn()
    out = G.auto_promote_or_queue(
        conn, "product.gz_qa_g", "SponsorCode", "크리에이터 후원 코드.",
        confidence=0.95, term_tier=G.TIER_PRODUCT)
    assert out == "auto_promoted"
    # `_insert_glossary_auto` 파라미터: (scope, role, term, definition, term_tier)
    # — `source` 는 SQL 리터럴 `'auto'` 라 바인딩에 없다.
    ins = conn.state["inserted"][0]
    assert ins[0] == "product.gz_qa_g" and ins[2] == "SponsorCode"
    assert ins[4] == G.TIER_PRODUCT


def test_product_term_without_resolved_product_is_queued_not_auto_promoted():
    """제품이 해소되지 않은 대화(제품 없는 1:1·CLI)에서 온 «제품 고유» 후보.

    그대로 자동승급하면 제품 용어가 **전역 사전에** 앉아, 지금 고치는 오염을 반대 방향으로
    재현한다.
    """
    conn = _FakeConn()
    out = G.auto_promote_or_queue(
        conn, G.GLOBAL_SCOPE, "SponsorCode", "크리에이터 후원 코드.",
        confidence=0.99, term_tier=G.TIER_PRODUCT)
    assert out == "pending"
    assert conn.state["inserted"] == []


def test_duplicate_across_scope_is_suppressed():
    """전역에 이미 있는 용어는 제품 scope 에 다시 등록되지 않는다.

    종전 억제는 `(scope, role, term)` 정확일치뿐이라 제품마다 같은 용어가 새로 생겼다.
    """
    dup = (7, G.GLOBAL_SCOPE, "*", "멱등성", "같은 요청 반복이 같은 결과", "manual", G.TIER_ORG)
    conn = _FakeConn(duplicate=dup)
    out = G.auto_promote_or_queue(
        conn, "product.gz_qa_g", "재시도 안전성", "여러 번 호출해도 결과가 같은 성질.",
        confidence=0.99, term_tier=G.TIER_PRODUCT)
    assert out == "duplicate"
    assert conn.state["inserted"] == [] and conn.state["queued"] == []


def test_settled_verdict_in_another_scope_blocks_reproposal():
    """제품 A 에서 거부한 용어가 제품 B 에서 되살아나지 않는다.

    REV-20260629 이 닫은 poisoning 구멍의 **scope 축 확장** — 그때는 같은 scope 안에서만
    막혀서, 다른 제품에서 같은 용어가 다시 자동등록됐다.
    """
    conn = _FakeConn(settled=("rejected", "product.mv"))
    out = G.auto_promote_or_queue(
        conn, "product.gz_qa_g", "잘못된 용어", "정의.",
        confidence=0.99, term_tier=G.TIER_PRODUCT)
    assert out == "skipped"
    assert conn.state["inserted"] == [] and conn.state["queued"] == []


def test_duplicate_lookup_uses_normalized_surface_and_includes_global_scope():
    """중복 조회가 **정규화 표면형**으로, **전역을 포함해** 나가는지 SQL 파라미터로 확인한다."""
    conn = _FakeConn()
    # ⚠ 범용 목록에 없는 용어여야 한다 — general 은 중복 조회 **전에** 반환되므로
    #   `복합 PK` 같은 걸 쓰면 이 테스트가 아무것도 검사하지 않는다(vacuous pass).
    term = "후원 정산 배치 (Sponsor Settlement)"
    G.auto_promote_or_queue(conn, "product.gz_qa_g", term, "후원 정산을 집계하는 배치.",
                            confidence=0.5, term_tier=G.TIER_ORG)
    # 파라미터: (scope_list, roles, surface, GLOBAL, lower(term))
    hits = [c for c in conn.state["captured"]
            if "FROM kb_glossary" in c[0] and "regexp_replace" in c[0]]
    assert hits, "표기변형 중복 조회가 수행되지 않았다"
    _, params = hits[-1]
    assert G.GLOBAL_SCOPE in params[0]
    assert params[2] == G.normalize_term_surface(term)


# ── 후보 정규화 — 서버 LLM 과 브리지 러너가 **같은 필터**를 탄다 ───────────────────
def test_normalize_suggestion_items_enforces_whitelist():
    items = G.normalize_suggestion_items([
        {"term": "정상", "definition": "정의", "tier": "org", "confidence": 0.7},
        {"term": "티어없음", "definition": "정의"},
        {"term": "이상한티어", "definition": "정의", "tier": "GLOBAL"},
        {"term": "", "definition": "빈 용어"},
        {"term": "정의없음", "definition": ""},
        {"term": "x" * 129, "definition": "너무 긴 용어"},
        "문자열은 항목이 아니다",
        {"term": "신뢰도이상", "definition": "정의", "confidence": 7.5},
    ], max_terms=10)
    got = {i["term"]: i for i in items}
    assert set(got) == {"정상", "티어없음", "이상한티어", "신뢰도이상"}
    assert got["정상"]["term_tier"] == G.TIER_ORG
    # 미지정·미지원 값은 **가장 좁은 범위**로 접는다.
    assert got["티어없음"]["term_tier"] == G.TIER_PRODUCT
    assert got["이상한티어"]["term_tier"] == G.TIER_PRODUCT
    assert got["신뢰도이상"]["confidence"] == 1.0


def test_normalize_suggestion_items_respects_max():
    items = G.normalize_suggestion_items(
        [{"term": f"t{i}", "definition": "d"} for i in range(20)], max_terms=3)
    assert len(items) == 3


def test_normalize_suggestion_items_caps_definition_length():
    """러너는 통제 밖 LLM 이다 — 문서 한 편을 정의로 보내는 것을 막는다."""
    items = G.normalize_suggestion_items(
        [{"term": "t", "definition": "x" * 5000}], max_terms=5)
    assert len(items[0]["definition"]) == 2000


# ── F5 (2026-09-01): ENUM 판정 이력도 scope 를 넘는다 ────────────────────────────
def test_enum_settled_verdict_crosses_scope():
    """제품 A 에서 거부한 ENUM 코드가 제품 B 에서 되살아나지 않는다.

    ⚠ 결과(`skipped`)만 보면 이 테스트는 아무것도 검사하지 않는다 — fake 는 어떤 SQL 에든
    같은 값을 돌려주므로 조회가 단일 scope 여도 통과한다(용어 축에서 실제로 그렇게 살아남은
    뮤턴트가 있었다). **조회에 실린 scope 집합**을 파라미터로 직접 단언한다.
    """
    conn = _FakeConn(settled=("rejected", "product.other"))
    out = G.auto_promote_or_queue_enum(
        conn, "product.sales", "dbo", "T_Order", "status", "9", "취소됨",
        confidence=0.99, threshold=0.9)
    assert out == "skipped"
    assert conn.state["inserted"] == [] and conn.state["queued"] == []
    hits = [c for c in conn.state["captured"]
            if "FROM enum_feedback" in c[0] and "status = ANY" in c[0]]
    assert hits, "ENUM 판정 이력 선검사가 수행되지 않았다"
    scopes = hits[0][1][0]
    assert "product.sales" in scopes and G.GLOBAL_SCOPE in scopes, (
        f"판정 이력 조회가 scope 를 넘지 않는다(scopes={scopes!r})")


def test_enum_new_candidate_auto_promotes():
    """판정 이력이 없으면 종전대로 임계 기반 자동승급 — 가드 추가가 정상 경로를 막지 않는다."""
    conn = _FakeConn(settled=None)
    out = G.auto_promote_or_queue_enum(
        conn, "product.sales", "dbo", "T_Order", "status", "1", "대기",
        confidence=0.95, threshold=0.9)
    assert out == "auto_promoted"
    assert conn.state["inserted"], "정상 후보가 enum_dictionary 에 기록되지 않았다"


def test_settled_enum_helper_self_defends_when_caller_omits_global():
    """헬퍼 **자신이** 전역 scope 를 보장한다 — 호출부가 빠뜨려도.

    ⚠ 이 테스트가 없으면 헬퍼 안의 `if GLOBAL_SCOPE not in scope_list: append` 는 **등가
    뮤턴트**가 된다(유일 호출부가 이미 `common` 을 넘기므로 지워도 결과가 같다, 2026-09-01
    뮤테이션 라운드에서 실증). 그 줄이 방어로서 의미를 가지려면 호출부 없이도 검사돼야 한다 —
    안 그러면 두 번째 호출부가 생기는 날 조용히 자기 scope 에 갇힌다.
    """
    conn = _FakeConn(settled=("rejected", "common"))
    out = G._settled_enum_status(conn, ["product.sales"], "dbo", "T_Order", "status", "9")
    assert out == ("rejected", "common")
    hits = [c for c in conn.state["captured"] if "FROM enum_feedback" in c[0]]
    assert hits and G.GLOBAL_SCOPE in hits[0][1][0], (
        f"호출부가 전역을 빠뜨리자 헬퍼도 전역을 안 봤다(scopes={hits[0][1][0]!r})")


def test_settled_enum_helper_dedupes_scope_list():
    """`sk == common` 인 호출부가 `['common','common']` 을 만들지 않는다."""
    conn = _FakeConn(settled=None)
    G._settled_enum_status(conn, ["common", "common", "COMMON"], "dbo", "T", "c", "1")
    hits = [c for c in conn.state["captured"] if "FROM enum_feedback" in c[0]]
    scopes = hits[0][1][0]
    assert scopes == [G.GLOBAL_SCOPE], f"scope 목록에 중복이 남았다: {scopes!r}"
