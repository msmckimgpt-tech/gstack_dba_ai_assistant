"""feature-0013 relationship-diagrams: 테이블 관계(FK·join) 저장소 + 도출 로직.

`table_relationships` 에 (source_table.col → target_table.col) edge 를 적재한다. 이 관계 데이터는
(a) insight worker 의 FK introspection 과 (b) 대화 중 실행된 JOIN 학습으로 채워지고,
`load_relationship_context()` 가 knowledge context 에 주입되어 assistant 의 mermaid 다이어그램
정확도를 높인다.

설계 원칙:
  - ds-scope: scope_key = 활성 datasource(cfg.get_active_datasource()) + 'common' 캐스케이드
    (kb_metadata 동형). 멀티 데이터소스 격리.
  - 연결: shared.db._pg_connect(RW, autocommit) / _pg_connect_ro(RO). PG 미가용·예외 시 no-op —
    **코어 대화/insight 흐름을 절대 차단하지 않는다**(모든 진입점 try/except + 빈 결과 반환).
  - 출처 우선순위: fk_introspect(1.0) > llm_insight(0.6) > conversation(0.4). 높은 confidence 가
    낮은 출처를 덮어쓰되 역방향은 보존.
"""
from __future__ import annotations

import logging
import re

from modules.utils import _normalize_scope_key, _scope_candidates

_log = logging.getLogger("relationships")

# 출처별 기본 confidence
CONFIDENCE = {"fk_introspect": 1.0, "llm_insight": 0.6, "conversation": 0.4}

_INJECT_CAP = 60        # knowledge context 주입 최대 edge 수
_READ_LIMIT = 400       # scope 당 최대 read edge 수
_INTROSPECT_TABLE_CAP = 200  # insight cycle 1회 introspect 최대 테이블 수(과부하 방지)


# ── 연결 헬퍼 (kb_metadata._ro_conn 동형) ────────────────────────────────
def _ro_conn(conn):
    if conn is not None:
        return conn, False
    from shared.db import _pg_available, _pg_connect_ro
    if not _pg_available():
        return None, False
    return _pg_connect_ro(), True


def _rw_conn(conn):
    if conn is not None:
        return conn, False
    from shared.db import _pg_available, _pg_connect
    if not _pg_available():
        return None, False
    return _pg_connect(autocommit=True), True


def _fqn(schema, table) -> str:
    schema = str(schema or "").strip()
    table = str(table or "").strip()
    return f"{schema}.{table}" if schema else table


# ── upsert ──────────────────────────────────────────────────────────────
def upsert_relationship(conn, scope_key, *, src_table, src_column, tgt_table, tgt_column,
                        source, src_schema="", tgt_schema="", datasource_key="",
                        constraint_name="", cardinality="", confidence=None,
                        source_run_id=None) -> bool:
    """관계 1 edge upsert. 성공 True. conn 미지정이면 RW 연결을 열어 사용(autocommit).

    높은 confidence 출처가 낮은 출처를 덮어쓰되 cardinality/constraint/datasource 는 보존적 merge.
    """
    if not (src_table and tgt_table and src_column and tgt_column):
        return False
    if confidence is None:
        confidence = CONFIDENCE.get(source, 0.5)
    c, owned = _rw_conn(conn)
    if c is None:
        return False
    try:
        cur = c.cursor()
        try:
            cur.execute(
                "INSERT INTO table_relationships "
                "(scope_key, datasource_key, source_schema, source_table, source_column, "
                " target_schema, target_table, target_column, source_table_fqn, target_table_fqn, "
                " constraint_name, cardinality, source, confidence, source_run_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (scope_key, source_table_fqn, source_column, target_table_fqn, target_column) "
                "DO UPDATE SET "
                "  constraint_name = COALESCE(NULLIF(EXCLUDED.constraint_name,''), table_relationships.constraint_name), "
                "  cardinality = COALESCE(NULLIF(EXCLUDED.cardinality,''), table_relationships.cardinality), "
                "  datasource_key = COALESCE(NULLIF(EXCLUDED.datasource_key,''), table_relationships.datasource_key), "
                "  source = CASE WHEN EXCLUDED.confidence >= table_relationships.confidence "
                "                THEN EXCLUDED.source ELSE table_relationships.source END, "
                "  confidence = GREATEST(EXCLUDED.confidence, table_relationships.confidence), "
                "  source_run_id = COALESCE(EXCLUDED.source_run_id, table_relationships.source_run_id), "
                "  updated_at = now()",
                (_normalize_scope_key(scope_key), str(datasource_key or ""),
                 str(src_schema or ""), str(src_table), str(src_column),
                 str(tgt_schema or ""), str(tgt_table), str(tgt_column),
                 _fqn(src_schema, src_table), _fqn(tgt_schema, tgt_table),
                 str(constraint_name or ""), str(cardinality or ""),
                 str(source), float(confidence), source_run_id),
            )
            return True
        finally:
            cur.close()
    except Exception as exc:
        _log.debug("relationship_upsert_failed err=%r", exc)
        return False
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass


# ── 읽기 + knowledge context 주입 ────────────────────────────────────────
def _fetch_relationships(conn, scopes):
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT source_table_fqn, source_column, target_table_fqn, target_column, "
            "       cardinality, source, confidence "
            "FROM table_relationships WHERE scope_key = ANY(%s) "
            "ORDER BY confidence DESC, source_table_fqn, target_table_fqn LIMIT %s",
            (list(scopes), _READ_LIMIT),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def load_relationship_context(user_message, scope_key=None, conn=None) -> str:
    """질문에 매칭되는 테이블의 관계 edge 를 ds-scoped 로 읽어 프롬프트 본문 조립.

    매칭: edge 의 source/target 테이블명(FQN 끝 segment)이 질문에 등장(대소문자 무관).
    매칭 0건이면 빈 문자열(섹션 생략). datamark·헤더는 호출측(_build_knowledge_context)이 부여.
    """
    msg = (user_message or "").lower()
    if not msg:
        return ""
    if scope_key is None:
        try:
            from shared import config as _cfg
            scope_key = _cfg.get_active_datasource()
        except Exception:
            scope_key = None
    c = None
    owned = False
    try:
        c, owned = _ro_conn(conn)
        if c is None:
            return ""
        rows = _fetch_relationships(c, _scope_candidates(scope_key))
    except Exception as exc:
        _log.debug("relationship_read_failed err=%r", exc)
        return ""
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return build_relationship_digest(rows, msg)


def _table_leaf(fqn: str) -> str:
    return str(fqn or "").split(".")[-1].lower()


def build_relationship_digest(rows, msg_lower: str = "") -> str:
    """관계 row 목록 → 프롬프트용 텍스트 digest (순수 함수, 단위 테스트 대상).

    rows: (src_fqn, src_col, tgt_fqn, tgt_col, cardinality, source, confidence) 시퀀스.
    msg_lower 가 주어지면 source/target 테이블명이 질문에 등장하는 edge 만 남긴다(빈 문자열이면 전부).
    """
    out = []
    seen = set()
    for r in rows:
        try:
            src_fqn, src_col, tgt_fqn, tgt_col, card, source, conf = (
                r[0], r[1], r[2], r[3], r[4], r[5], r[6])
        except Exception:
            continue
        if msg_lower:
            if _table_leaf(src_fqn) not in msg_lower and _table_leaf(tgt_fqn) not in msg_lower:
                continue
        key = (src_fqn, src_col, tgt_fqn, tgt_col)
        if key in seen:
            continue
        seen.add(key)
        card_s = f" [{card}]" if card else ""
        src_tag = "" if source == "fk_introspect" else f" ({source})"
        out.append(f"- {src_fqn}.{src_col} → {tgt_fqn}.{tgt_col}{card_s}{src_tag}")
        if len(out) >= _INJECT_CAP:
            break
    if not out:
        return ""
    return "\n".join(out)


# ── FK introspection (insight worker 용) ─────────────────────────────────
def introspect_and_store(ds_conn, dialect, schema, tables, *, kb_conn=None, scope_key="common",
                         datasource_key="", source_run_id=None, raw_execute=None) -> int:
    """한 schema 의 테이블들에 대해 dialect FK 쿼리를 실행해 table_relationships 에 적재.

    ds_conn: 데이터소스 연결. dialect: dialects.active() 류(foreign_keys_outgoing 보유).
    raw_execute(conn, sql) -> (result_sets, ...) : tools._raw_execute_sql 동형 콜백(주입 — 순환 import 회피).
    반환: upsert 한 edge 수. 예외는 삼켜서 0 또는 부분 카운트 반환(insight 루프 비차단).
    """
    if raw_execute is None or dialect is None or not tables:
        return 0
    kc, kowned = _rw_conn(kb_conn)
    if kc is None:
        return 0
    n = 0
    try:
        for table in list(tables)[:_INTROSPECT_TABLE_CAP]:
            try:
                sql = dialect.foreign_keys_outgoing(schema, table)
                results, *_ = raw_execute(ds_conn, sql)
                for edge in _rows_from_outgoing(results):
                    if upsert_relationship(
                        kc, scope_key,
                        src_schema=schema, src_table=table, src_column=edge["src_column"],
                        tgt_schema=edge.get("tgt_schema", ""), tgt_table=edge["tgt_table"],
                        tgt_column=edge["tgt_column"], source="fk_introspect",
                        datasource_key=datasource_key, constraint_name=edge.get("constraint_name", ""),
                        source_run_id=source_run_id,
                    ):
                        n += 1
            except Exception as exc:
                _log.debug("introspect_table_failed schema=%s table=%s err=%r", schema, table, exc)
                continue
    finally:
        if kowned and kc is not None:
            try:
                kc.close()
            except Exception:
                pass
    return n


def _rows_from_outgoing(results):
    """dialect.foreign_keys_outgoing 결과 → edge dict 목록.

    MySQL 컬럼순: CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME (dialects.py). MSSQL 도 동일 컬럼순 호환(dialects.py 주석). results 는
    [{columns:[...], rows:[[...]]}] 또는 [(cols, rows)] 형태를 모두 허용(보수적 파싱).
    """
    edges = []
    for rset in _iter_result_sets(results):
        rows = rset.get("rows") or []
        for row in rows:
            try:
                if len(row) < 5:
                    continue
                edges.append({
                    "constraint_name": str(row[0] or ""),
                    "src_column": str(row[1] or ""),
                    "tgt_schema": str(row[2] or ""),
                    "tgt_table": str(row[3] or ""),
                    "tgt_column": str(row[4] or ""),
                })
            except Exception:
                continue
    return [e for e in edges if e["src_column"] and e["tgt_table"] and e["tgt_column"]]


def _iter_result_sets(results):
    """다양한 result-set 표현을 {columns, rows} dict 로 정규화(보수적)."""
    if not results:
        return
    for rset in results:
        if isinstance(rset, dict):
            yield {"columns": rset.get("columns") or [], "rows": rset.get("rows") or []}
        elif isinstance(rset, (list, tuple)) and len(rset) == 2:
            yield {"columns": rset[0] or [], "rows": rset[1] or []}


# ── 대화 학습: 실행된 JOIN 에서 관계 추출 (Phase 3, 순수 파서) ─────────────
_QUOTE_CHARS = "`\"[]"
_QUAL = r'[`"\[\]A-Za-z0-9_$]+'  # 단일 식별자 토큰(따옴표/괄호 포함)


def _unquote(ident: str) -> str:
    s = str(ident or "").strip()
    for ch in _QUOTE_CHARS:
        s = s.replace(ch, "")
    return s.strip()


def _strip_sql_noise(sql: str) -> str:
    """라인/블록 주석 제거 + 공백 단일화 (파서 안정화)."""
    s = str(sql or "")
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.DOTALL)
    s = re.sub(r"--[^\n]*", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


_RESERVED_ALIAS = {"on", "where", "group", "order", "having", "limit", "union",
                   "inner", "left", "right", "outer", "join", "cross", "using",
                   "natural", "straight_join", "select", "and", "or", "window",
                   "fetch", "offset"}
# 예약어를 alias 로 오인하지 않도록 alias group 에 negative lookahead 적용 (안 그러면
# `from orders join ...` 에서 'join' 을 orders 의 alias 로 먹어 다음 테이블을 놓친다).
_ALIAS_GUARD = r"(?!(?:" + "|".join(sorted(_RESERVED_ALIAS)) + r")\b)"
# FROM/JOIN/comma 뒤의 테이블 참조 1건. table 은 1~3 part(db.schema.table) 허용.
_TABLEREF_RE = re.compile(
    r"(?:\bfrom\b\s+|\bjoin\b\s+|,\s*)(" + _QUAL + r"(?:\." + _QUAL + r"){0,2})"
    r"(?:\s+(?:as\s+)?" + _ALIAS_GUARD + r"(" + _QUAL + r"))?",
    re.IGNORECASE,
)
_CLAUSE_BOUNDARY_RE = re.compile(
    r"\b(?:where|group\s+by|order\s+by|having|limit|union|window|fetch|offset)\b",
    re.IGNORECASE,
)


def _from_region(sql_clean: str) -> str:
    """첫 FROM 부터 다음 major clause(WHERE/GROUP BY/…) 직전까지 — 테이블 참조 추출 영역.

    JOIN 과 그 ON 절은 이 영역 안에 포함된다. comma 가 select-list 가 아닌 FROM-list 임을
    보장해 alias map 오염을 줄인다.
    """
    m = re.search(r"\bfrom\b", sql_clean, re.IGNORECASE)
    if not m:
        return ""
    rest = sql_clean[m.start():]
    b = _CLAUSE_BOUNDARY_RE.search(rest)
    return rest[:b.start()] if b else rest


def _alias_map(sql_clean: str) -> dict:
    """FROM 영역에서 {alias_or_table_lower: table_leaf} 매핑 구성.

    table 은 마지막 segment(db.schema.table → table)로 leaf 화. alias 없으면 leaf 자신을 키로.
    """
    amap = {}
    for m in _TABLEREF_RE.finditer(_from_region(sql_clean)):
        tbl_raw = m.group(1)
        alias_raw = m.group(2)
        leaf = _unquote(tbl_raw.split(".")[-1])
        if not leaf or leaf.lower() in _RESERVED_ALIAS:
            continue
        amap[leaf.lower()] = leaf
        if alias_raw:
            alias = _unquote(alias_raw)
            if alias and alias.lower() not in _RESERVED_ALIAS:
                amap[alias.lower()] = leaf
    return amap


_EQ_RE = re.compile(
    r"(" + _QUAL + r")\.(" + _QUAL + r")\s*=\s*(" + _QUAL + r")\.(" + _QUAL + r")"
)


def parse_join_relationships(sql: str) -> list[dict]:
    """실행된 SQL 에서 equi-join edge 후보를 추출(보수적·best-effort, 순수 함수).

    'alias.col = alias.col' 형태(JOIN ON 또는 WHERE)만 추출하고, alias 를 FROM/JOIN 의 테이블로
    해석한다. 같은 테이블 self-eq·해석 실패·단일컬럼/함수 비교는 무시. 무방향 중복 제거.
    반환: [{src_table, src_column, tgt_table, tgt_column}] (테이블=leaf 이름, 스키마 미해석).
    """
    if not sql or not isinstance(sql, str):
        return []
    s = _strip_sql_noise(sql)
    if " join " not in (" " + s.lower() + " ") and "," not in s:
        # JOIN 도 comma-cross-join 도 아니면 관계 신호 약함 — 그래도 WHERE equi 는 시도
        pass
    amap = _alias_map(s)
    if not amap:
        return []
    edges = []
    seen = set()
    for m in _EQ_RE.finditer(s):
        lq, lc, rq, rc = (_unquote(m.group(1)), _unquote(m.group(2)),
                          _unquote(m.group(3)), _unquote(m.group(4)))
        lt = amap.get(lq.lower())
        rt = amap.get(rq.lower())
        if not lt or not rt:
            continue
        if lt.lower() == rt.lower():
            continue
        if not lc or not rc:
            continue
        key = tuple(sorted([f"{lt.lower()}.{lc.lower()}", f"{rt.lower()}.{rc.lower()}"]))
        if key in seen:
            continue
        seen.add(key)
        edges.append({"src_table": lt, "src_column": lc, "tgt_table": rt, "tgt_column": rc})
    return edges


def learn_relationships_from_sql(sql, scope_key=None, *, datasource_key="", source_run_id=None,
                                 conn=None) -> int:
    """실행된 (성공한) SQL 의 JOIN 에서 관계를 학습해 table_relationships 에 upsert(source='conversation').

    confidence 낮음(0.4) — FK introspection(1.0)이 있으면 그쪽이 우선. 예외·PG 미가용 시 0(비차단).
    반환: upsert 한 edge 수.
    """
    edges = parse_join_relationships(sql)
    if not edges:
        return 0
    if scope_key is None:
        try:
            from shared import config as _cfg
            scope_key = _cfg.get_active_datasource()
        except Exception:
            scope_key = None
    c, owned = _rw_conn(conn)
    if c is None:
        return 0
    n = 0
    try:
        for e in edges:
            if upsert_relationship(
                c, scope_key,
                src_table=e["src_table"], src_column=e["src_column"],
                tgt_table=e["tgt_table"], tgt_column=e["tgt_column"],
                source="conversation", datasource_key=datasource_key, source_run_id=source_run_id,
            ):
                n += 1
    except Exception as exc:
        _log.debug("learn_from_sql_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return n
