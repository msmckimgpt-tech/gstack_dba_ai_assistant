"""ITEM-10 — 용어사전(kb_glossary) + ENUM 코드사전(enum_dictionary) 단위 테스트.

LLM·라이브DB 무관: FakeConn 으로 upsert SQL·ds-scoped read·질문 매칭·프롬프트 조립 검증.
측정(ENUM 정확도 수치)은 bedrock-auth 복구 후 ITEM-01 harness 로(별도).
"""
from modules import kb_glossary as G


class _FakeCursor:
    def __init__(self, state):
        self._state = state
        self._rows = []

    def execute(self, sql, params=None):
        self._state["captured"].append((sql, params))
        if "kb_glossary" in sql and sql.strip().upper().startswith("SELECT"):
            self._rows = self._state["glossary"]
        elif "enum_dictionary" in sql and sql.strip().upper().startswith("SELECT"):
            self._rows = self._state["enums"]
        else:
            self._rows = []

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _FakeConn:
    def __init__(self, glossary=(), enums=()):
        self.state = {"captured": [], "glossary": list(glossary), "enums": list(enums)}

    def cursor(self):
        return _FakeCursor(self.state)

    @property
    def captured(self):
        return self.state["captured"]


# ── upsert SQL ──────────────────────────────────────────────────────────────
def test_upsert_glossary_term_sql():
    # 0021: 역할 차원 추가 — UNIQUE(scope_key, role_key, term), role_key 기본 '*'(공용), source 기본 'manual'.
    conn = _FakeConn()
    G.upsert_glossary_term(conn, "ds:sales", "MAU", "월간 활성 사용자")
    sql, params = conn.captured[-1]
    assert "INSERT INTO kb_glossary" in sql
    assert "ON CONFLICT (scope_key, role_key, term)" in sql
    # params: (scope_key, role_key, term, definition, source)
    assert params[1] == "*" and params[2] == "MAU" and params[3] == "월간 활성 사용자"
    assert params[4] == "manual"


def test_upsert_glossary_term_role_scoped_sql():
    # 역할 지정 시 role_key 가 정규화(소문자)되어 들어간다.
    conn = _FakeConn()
    G.upsert_glossary_term(conn, "ds:sales", "리드", "영업 잠재고객", role_key="Sales", source="auto")
    _, params = conn.captured[-1]
    assert params[1] == "sales" and params[2] == "리드" and params[4] == "auto"


def test_upsert_enum_entry_sql():
    conn = _FakeConn()
    G.upsert_enum_entry(conn, "ds:sales", "orders", "status", "P", "결제대기", schema_name="public")
    sql, params = conn.captured[-1]
    assert "INSERT INTO enum_dictionary" in sql
    assert "ON CONFLICT (scope_key, schema_name, table_name, column_name, code)" in sql
    assert params[2] == "orders" and params[3] == "status" and params[4] == "P" and params[5] == "결제대기"


# ── ds-scoped read + 매칭 + 조립 ─────────────────────────────────────────────
def test_load_injects_matched_term_and_enum():
    conn = _FakeConn(
        glossary=[("status", "주문 처리 상태")],
        enums=[("orders", "status", "P", "결제대기"), ("orders", "status", "D", "배송완료")],
    )
    out = G.load_glossary_enum_context("최근 status 별 주문 건수", scope_key="ds:sales", conn=conn)
    assert "용어:" in out and "status: 주문 처리 상태" in out
    assert "ENUM 코드" in out
    assert "orders.status:" in out
    assert "P=결제대기" in out and "D=배송완료" in out


def test_read_sql_is_ds_scoped():
    conn = _FakeConn(glossary=[("status", "x")], enums=[])
    G.load_glossary_enum_context("status", scope_key="ds:sales", conn=conn)
    # 두 read SQL 모두 scope_key = ANY(%s) 로 ds 격리. scopes 에 'common' 캐스케이드 포함.
    reads = [(sql, p) for (sql, p) in conn.captured if sql.strip().upper().startswith("SELECT")]
    assert reads, "read SQL 미발생"
    for sql, params in reads:
        assert "scope_key = ANY(%s)" in sql
        assert "common" in params[0]  # _scope_candidates 캐스케이드


def test_non_matching_returns_empty():
    conn = _FakeConn(glossary=[("status", "x")], enums=[("orders", "status", "P", "결제대기")])
    # 질문에 term/column/table 미등장 → 주입 없음.
    assert G.load_glossary_enum_context("오늘 날씨 알려줘", scope_key="ds:sales", conn=conn) == ""


def test_empty_message_returns_empty():
    conn = _FakeConn(glossary=[("status", "x")])
    assert G.load_glossary_enum_context("", scope_key="ds:sales", conn=conn) == ""


def test_enum_matched_by_table_name():
    conn = _FakeConn(glossary=[], enums=[("invoices", "kind", "A", "정기")])
    out = G.load_glossary_enum_context("invoices 테이블 분석", scope_key="ds:fin", conn=conn)
    assert "invoices.kind:" in out and "A=정기" in out


# ── ds 격리 (REV BLOCKER B1 회귀) ────────────────────────────────────────────
def test_scope_excludes_other_datasource():
    from modules.utils import _normalize_scope_key
    conn = _FakeConn(glossary=[("status", "x")], enums=[])
    G.load_glossary_enum_context("status", scope_key="ds:sales", conn=conn)
    reads = [p for (sql, p) in conn.captured if sql.strip().upper().startswith("SELECT")]
    assert reads
    scopes = reads[0][0]
    assert _normalize_scope_key("ds:sales") in scopes       # 활성 ds 포함
    assert "common" in scopes                                # 공용 캐스케이드
    assert _normalize_scope_key("ds:fin") not in scopes      # 타 ds 미요청(격리)


def test_default_scope_derives_from_active_product():
    # metadata-product-scope: 운영 경로에서 scope_key 미지정 → cfg.get_active_product_scope() 로 도출.
    # (종전엔 활성 datasource 였다 — 제품이 N개 DS 에 걸치면 등록분이 1/N 질의에서만 주입되던 결함.)
    from shared import config as cfg
    from modules.utils import _normalize_scope_key
    _prev_legacy = getattr(cfg, "AGENT_KB_LEGACY_DS_SCOPE_READ", True)
    cfg.AGENT_KB_LEGACY_DS_SCOPE_READ = False   # contract 상태(이관 완료 후) 계약을 고정
    cfg.set_active_product("KR_LIVE")
    cfg.set_active_datasource("mysql-an1-auth")   # 활성 DS 는 달라도 제품 축이 우선
    try:
        conn = _FakeConn(glossary=[("status", "x")], enums=[])
        G.load_glossary_enum_context("status", conn=conn)  # scope 미지정 = 운영 호출 형태
        reads = [p for (sql, p) in conn.captured if sql.strip().upper().startswith("SELECT")]
        scopes = reads[0][0]
        assert _normalize_scope_key("product.kr_live") in scopes   # 활성 제품이 scope 에 반영
        assert "mysql-an1-auth" not in scopes                      # datasource 축은 더 이상 쓰지 않는다
        assert scopes != ["common", ""]                            # 'common' 만으로 폴백되지 않음
    finally:
        cfg.AGENT_KB_LEGACY_DS_SCOPE_READ = _prev_legacy
        cfg.set_active_product(None)
        cfg.set_active_datasource(None)


def test_product_scope_spans_all_datasources_of_product():
    """1제품↔N데이터소스 회귀 가드 — 같은 제품이면 활성 datasource 가 무엇이든 같은 scope 를 읽는다.
    (라이브 실측: KR_LIVE 용어 85건이 7개 DS 중 auth 에만 등록돼 나머지 6개 질의에서 미주입이었다.)"""
    from shared import config as cfg
    from modules.utils import _normalize_scope_key
    _prev_legacy = getattr(cfg, "AGENT_KB_LEGACY_DS_SCOPE_READ", True)
    cfg.AGENT_KB_LEGACY_DS_SCOPE_READ = False   # contract 상태 계약(expand 꼬리는 별 테스트가 검증)
    seen = []
    for ds in ("mysql-an1-auth", "mysql-an1-player", "mysql-an1-logdb"):
        cfg.set_active_product("KR_LIVE")
        cfg.set_active_datasource(ds)
        try:
            conn = _FakeConn(glossary=[("status", "x")], enums=[])
            G.load_glossary_enum_context("status", conn=conn)
            reads = [p for (sql, p) in conn.captured if sql.strip().upper().startswith("SELECT")]
            seen.append(tuple(reads[0][0]))
        finally:
            cfg.set_active_product(None)
            cfg.set_active_datasource(None)
    cfg.AGENT_KB_LEGACY_DS_SCOPE_READ = _prev_legacy
    assert len(set(seen)) == 1, f"제품이 같으면 DS 와 무관하게 동일 scope 여야 한다: {seen}"
    assert _normalize_scope_key("product.kr_live") in seen[0]


# ── 0021: 역할 차원 read 격리 ─────────────────────────────────────────────────
def test_role_scoped_read_sql():
    # role_key 지정 시 read SQL 에 role_key = ANY(%s) 추가 + [그 역할, '*'(공용)] 캐스케이드.
    conn = _FakeConn(glossary=[("status", "x")], enums=[])
    G.load_glossary_enum_context("status", scope_key="ds:sales", conn=conn, role_key="Operator")
    gloss_reads = [(sql, p) for (sql, p) in conn.captured
                   if sql.strip().upper().startswith("SELECT") and "kb_glossary" in sql]
    assert gloss_reads, "glossary read SQL 미발생"
    sql, params = gloss_reads[0]
    assert "role_key = ANY(%s)" in sql
    roles = params[1]
    assert "operator" in roles and "*" in roles   # 정규화(소문자) + 공용 캐스케이드


def test_role_none_read_keeps_legacy_sql():
    # role_key 미지정(하위호환) → role 절 없음(기존 SQL 그대로).
    conn = _FakeConn(glossary=[("status", "x")], enums=[])
    G.load_glossary_enum_context("status", scope_key="ds:sales", conn=conn)
    gloss_reads = [sql for (sql, p) in conn.captured
                   if sql.strip().upper().startswith("SELECT") and "kb_glossary" in sql]
    assert gloss_reads and "role_key" not in gloss_reads[0]


# ── 0021: 검토 큐 + 하이브리드 자동승급 ──────────────────────────────────────────
class _ScriptedCursor:
    def __init__(self, state):
        self._state = state
        self.rowcount = state.get("rowcount", 1)

    def execute(self, sql, params=None):
        self._state["captured"].append((sql, params))
        self.rowcount = self._state.get("rowcount", 1)

    def fetchone(self):
        q = self._state["fetchone_queue"]
        return q.pop(0) if q else None

    def fetchall(self):
        return self._state.get("rows", [])

    def close(self):
        pass


class _ScriptedConn:
    def __init__(self, fetchone_queue=None, rowcount=1):
        self.state = {"captured": [], "fetchone_queue": list(fetchone_queue or []), "rowcount": rowcount}

    def cursor(self):
        return _ScriptedCursor(self.state)

    @property
    def captured(self):
        return self.state["captured"]


def test_record_glossary_suggestion_sql():
    conn = _ScriptedConn(rowcount=1)
    ok = G.record_glossary_suggestion(conn, "common", "*", "리드", "영업 잠재고객", confidence=0.6)
    assert ok is True
    sql, params = conn.captured[-1]
    assert "INSERT INTO glossary_feedback" in sql
    assert "ON CONFLICT (scope_key, role_key, term)" in sql
    # 거부/승급된 행은 재제안돼도 되살아나지 않는다(WHERE pending).
    assert "WHERE glossary_feedback.status = 'pending'" in sql
    assert "pending" in params   # status 파라미터


def test_auto_promote_high_confidence_registers():
    # confidence ≥ threshold → kb_glossary 자동 등록(source='auto') + glossary_feedback(auto_promoted).
    #
    # 0057 로 선검사가 둘 늘었다 — fetchone_queue:
    #   [_settled_feedback_status=None(신규), find_glossary_duplicate=None(중복 없음),
    #    _insert_glossary_auto RETURNING=(123,)]
    # 그리고 scope 는 **제품 scope** 여야 한다: 'common' 을 주면 0057 의 「귀속처 없는 제품 용어는
    # 자동승급하지 않는다」 가드에 걸려 pending 이 된다(전역 사전 오염 방지 — 의도된 동작).
    conn = _ScriptedConn(fetchone_queue=[None, None, (123,)], rowcount=1)
    res = G.auto_promote_or_queue(conn, "product.sales", "리드", "영업 잠재고객",
                                  confidence=0.95, threshold=0.85)
    assert res == "auto_promoted"
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO kb_glossary" in joined and "'auto'" in joined
    fb = [(sql, p) for (sql, p) in conn.captured if "glossary_feedback" in sql and "INSERT" in sql]
    assert fb and "auto_promoted" in fb[-1][1]


def test_auto_promote_low_confidence_queues_pending():
    conn = _ScriptedConn(rowcount=1)   # _feedback_status fetchone → None(신규)
    res = G.auto_promote_or_queue(conn, "common", "모호용어", "불확실 정의",
                                  confidence=0.4, threshold=0.85)
    assert res == "pending"
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO kb_glossary" not in joined   # 라이브 미반영
    assert "INSERT INTO glossary_feedback" in joined


def test_auto_promote_skips_rejected_term():
    # REV-20260629 BLOCKER 회귀: 과거 거부된 용어가 고신뢰로 재추론돼도 라이브 kb_glossary 에
    # 재유입되면 안 된다(poisoning 방어). 판정 이력 있음 → kb_glossary INSERT 미발생.
    #
    # 0057: 선검사가 `_settled_feedback_status` 로 바뀌며 **scope 를 넘어** 본다 —
    # 반환이 `(status, scope_key)` 2-튜플이다. 제품 A 에서 거부한 용어가 제품 B 에서
    # 되살아나던 구멍을 그 확장이 닫는다(아래 test_auto_promote_skips_rejected_cross_scope).
    conn = _ScriptedConn(fetchone_queue=[("rejected", "common")], rowcount=1)
    res = G.auto_promote_or_queue(conn, "common", "거부된용어", "재유입 시도 정의",
                                  confidence=0.99, threshold=0.85)
    assert res == "skipped"
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO kb_glossary" not in joined        # 라이브 재유입 차단
    assert "INSERT INTO glossary_feedback" not in joined  # 큐 재적재도 안 함


def test_auto_promote_skips_rejected_cross_scope():
    """0057 신규 — 다른 제품에서 거부된 용어도 재유입되지 않는다.

    ⚠ **결과(`skipped`)만 보면 이 테스트는 아무것도 검사하지 않는다.** `_ScriptedConn` 은 어떤
    SQL 이든 큐의 다음 값을 돌려주므로, 조회가 단일 scope 로 좁혀져 있어도(=0057 이전 동작)
    이 fake 는 여전히 'rejected' 를 답한다 — 뮤테이션 실증에서 실제로 그렇게 살아남았다.
    그래서 **조회가 나간 scope 집합**을 파라미터로 직접 단언한다.
    """
    conn = _ScriptedConn(fetchone_queue=[("rejected", "product.other")], rowcount=1)
    res = G.auto_promote_or_queue(conn, "product.sales", "거부된용어", "재유입 시도 정의",
                                  confidence=0.99, threshold=0.85)
    assert res == "skipped"
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO kb_glossary" not in joined
    settled = [(s, p) for (s, p) in conn.captured
               if "FROM glossary_feedback" in s and "status = ANY" in s]
    assert settled, "판정 이력 선검사가 수행되지 않았다"
    scopes = settled[0][1][0]
    assert "product.sales" in scopes and G.GLOBAL_SCOPE in scopes, (
        f"판정 이력 조회가 scope 를 넘지 않는다(scopes={scopes!r}) — "
        "제품 A 에서 거부한 용어가 제품 B 에서 되살아난다")
    # 표기변형까지 접어야 `멱등성` ↔ `멱등성(Idempotency)` 재유입도 막힌다.
    assert settled[0][1][3] == G.normalize_term_surface("거부된용어")


def test_auto_promote_skips_already_promoted():
    # 이미 등록(promoted/auto_promoted)된 용어는 중복 자동 INSERT 안 함.
    conn = _ScriptedConn(fetchone_queue=[("auto_promoted", "common")], rowcount=1)
    res = G.auto_promote_or_queue(conn, "common", "기존용어", "정의",
                                  confidence=0.99, threshold=0.85)
    assert res == "skipped"
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO kb_glossary" not in joined


def test_reject_auto_promoted_reverts_live_term():
    # auto_promoted 거부 → 자동 추가된 source='auto' 행 회수 + status='rejected'.
    conn = _ScriptedConn(fetchone_queue=[("auto_promoted", 55)], rowcount=1)
    G.reject_glossary_feedback(conn, 7)
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "DELETE FROM kb_glossary" in joined and "source = 'auto'" in joined
    assert "status='rejected'" in joined


def test_reject_pending_no_live_delete():
    conn = _ScriptedConn(fetchone_queue=[("pending", None)], rowcount=1)
    G.reject_glossary_feedback(conn, 9)
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "DELETE FROM kb_glossary" not in joined
    assert "status='rejected'" in joined


def test_promote_glossary_feedback_inserts_and_marks():
    # pending → kb_glossary upsert(source='manual') + feedback status='promoted'.
    # 0057: 큐 행에서 `term_tier` 도 함께 읽어 그대로 옮긴다(판정과 등록이 갈리지 않게).
    conn = _ScriptedConn(fetchone_queue=[("common", "*", "리드", "정의", "org"), (321,)],
                         rowcount=1)
    gid = G.promote_glossary_feedback(conn, 3, approved_by="curator")
    assert gid == 321
    joined = " ".join(sql for (sql, _) in conn.captured)
    assert "INSERT INTO kb_glossary" in joined and "'manual'" in joined
    assert "status='promoted'" in joined
    ins = [(s, p) for (s, p) in conn.captured if "INSERT INTO kb_glossary" in s]
    assert ins[-1][1][-1] == "org", "큐의 term_tier 가 등록 행으로 옮겨지지 않았다"


def test_promote_glossary_feedback_accepts_skipped_general():
    """0057 신규 — 범용 판정으로 제외된 후보도 관리자가 되살릴 수 있어야 한다.

    되살릴 경로가 없으면 결정적 목록의 오분류가 그대로 영구 삭제가 된다.
    """
    conn = _ScriptedConn(fetchone_queue=[("common", "*", "튜닝인덱스", "정의", "general"), (9,)],
                         rowcount=1)
    assert G.promote_glossary_feedback(conn, 5) == 9
    sel = [s for (s, _) in conn.captured if "FROM glossary_feedback" in s]
    assert sel and "skipped_general" in str(conn.captured[0][1]), \
        "승급 조회가 skipped_general 을 대상에 넣지 않았다"


# ── 0021: 유사어 관계 ────────────────────────────────────────────────────────
def test_add_glossary_relation_sql():
    conn = _ScriptedConn(rowcount=1)
    G.add_glossary_relation(conn, 1, 2, "synonym", created_by="curator")
    sql, params = conn.captured[-1]
    assert "INSERT INTO glossary_relations" in sql
    assert "ON CONFLICT (from_id, to_id, relation_type) DO NOTHING" in sql
    assert params[0] == 1 and params[1] == 2 and params[2] == "synonym"


# ── metadata-product-scope: 제품 스코프 키 규약 ──────────────────────────────
def test_product_scope_key_normalization():
    """`product.<ProductKey>` 규약 — 소문자 정규화 + 중복 접두 방지 + 빈값 None.

    `:` 대신 `.` 를 구분자로 쓰는 이유: `_sanitize_key_part` 가 허용하는 문자는 [A-Za-z0-9_.-] 라
    `product:kr_live` 는 `product_kr_live` 로 뭉개진다(스코프 키가 조용히 어긋남)."""
    from shared import config as cfg
    from modules.utils import _normalize_scope_key
    assert cfg.product_scope_key("KR_LIVE") == "product.kr_live"
    assert cfg.product_scope_key("product.kr_live") == "product.kr_live"   # 재적용 무해(멱등)
    assert cfg.product_scope_key("") is None and cfg.product_scope_key(None) is None
    assert cfg.is_product_scope("product.kr_live") is True
    assert cfg.is_product_scope("mysql-06656002eda6") is False
    # 정규화를 통과해도 형태가 보존돼야 한다(sanitize 로 뭉개지면 read/write 축이 어긋난다).
    assert _normalize_scope_key("product.kr_live") == "product.kr_live"


def test_active_product_context_isolated_from_datasource():
    """제품 컨텍스트는 datasource 컨텍스트와 별 축 — 한쪽 해제가 다른 쪽을 건드리지 않는다."""
    from shared import config as cfg
    cfg.set_active_product("MV_QA")
    cfg.set_active_datasource("mysql-a4f572f222a2")
    try:
        assert cfg.get_active_product_scope() == "product.mv_qa"
        cfg.set_active_datasource(None)
        assert cfg.get_active_product_scope() == "product.mv_qa", "DS 해제가 제품 축을 지우면 안 된다"
    finally:
        cfg.set_active_product(None)
        cfg.set_active_datasource(None)
    assert cfg.get_active_product_scope() is None


def test_kb_scope_candidates_falls_back_to_common_without_product():
    """제품 미지정(제품 없는 1:1/CLI) → 공용 사전만. datasource 로 새지 않는다."""
    from shared import config as cfg
    from modules.utils import _kb_scope_candidates
    _prev_legacy = getattr(cfg, "AGENT_KB_LEGACY_DS_SCOPE_READ", True)
    cfg.AGENT_KB_LEGACY_DS_SCOPE_READ = False   # contract 상태 계약
    cfg.set_active_product(None)
    cfg.set_active_datasource("mysql-deadbeef")
    try:
        scopes = _kb_scope_candidates()
        assert scopes[0] == "common"
        assert "mysql-deadbeef" not in scopes
    finally:
        cfg.AGENT_KB_LEGACY_DS_SCOPE_READ = _prev_legacy
        cfg.set_active_datasource(None)


def test_legacy_ds_scope_read_tail_during_migration_window():
    """expand/contract — 배포↔이관 창에서 레거시 datasource-scope 행이 계속 읽혀야 한다.

    제품 스코프만 읽으면 이관 전까지 기존 등록 메타데이터가 통째로 사라진다(codex review P1).
    이관 완료 후 AGENT_KB_LEGACY_DS_SCOPE_READ=0 으로 contract 하면 꼬리가 사라진다."""
    from shared import config as cfg
    from modules.utils import _kb_scope_candidates, _normalize_scope_key
    prev = getattr(cfg, "AGENT_KB_LEGACY_DS_SCOPE_READ", True)
    cfg.set_active_product("KR_LIVE")
    cfg.set_active_datasource("mysql-an1-auth")
    try:
        cfg.AGENT_KB_LEGACY_DS_SCOPE_READ = True
        scopes = _kb_scope_candidates()
        assert scopes[0] == _normalize_scope_key("product.kr_live")   # 제품이 1순위
        assert "mysql-an1-auth" in scopes                              # 레거시 꼬리(expand)
        assert "common" in scopes

        cfg.AGENT_KB_LEGACY_DS_SCOPE_READ = False                      # contract
        scopes2 = _kb_scope_candidates()
        assert "mysql-an1-auth" not in scopes2, "contract 후 datasource 축은 사라져야 한다"
        assert scopes2[0] == _normalize_scope_key("product.kr_live")
    finally:
        cfg.AGENT_KB_LEGACY_DS_SCOPE_READ = prev
        cfg.set_active_product(None)
        cfg.set_active_datasource(None)


def test_explicit_scope_key_has_no_legacy_tail():
    """admin 경로(명시 scope_key)는 레거시 꼬리를 붙이지 않는다 — 편집/삭제가 정확히 그 scope 만."""
    from shared import config as cfg
    from modules.utils import _kb_scope_candidates
    prev = getattr(cfg, "AGENT_KB_LEGACY_DS_SCOPE_READ", True)
    cfg.set_active_datasource("mysql-an1-auth")
    try:
        cfg.AGENT_KB_LEGACY_DS_SCOPE_READ = True
        scopes = _kb_scope_candidates("product.mv_qa")
        assert "mysql-an1-auth" not in scopes
    finally:
        cfg.AGENT_KB_LEGACY_DS_SCOPE_READ = prev
        cfg.set_active_datasource(None)


def test_product_scope_unresolved_signal_distinct_from_absent():
    """'제품 없음'과 '제품 있는데 해소 실패'는 구별돼야 한다(자율수집 fail-closed 근거)."""
    from shared import config as cfg
    cfg.set_active_product(None)
    try:
        assert cfg.is_product_scope_unresolved() is False
        cfg.set_active_product(None, unresolved=True)
        assert cfg.is_product_scope_unresolved() is True
        assert cfg.get_active_product_scope() is None
    finally:
        cfg.set_active_product(None)
    assert cfg.is_product_scope_unresolved() is False
