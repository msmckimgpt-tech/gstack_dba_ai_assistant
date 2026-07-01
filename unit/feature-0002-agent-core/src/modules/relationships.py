"""feature-0013/0016 relationship-diagrams: 테이블 관계(FK·join·추론) 저장소 + 도출·강화 로직.

`table_relationships` 에 (source_table.col → target_table.col) edge 를 적재한다. 이 관계 데이터는
(a) insight worker 의 FK introspection, (b) 대화 중 실행된 JOIN 학습, (c) **FK 미선언 관계의 휴리스틱
추론**(feature-0016 implicit-edges) 으로 채워지고, `load_relationship_context()` 가 knowledge context
에 주입되어 assistant 의 SQL·다이어그램 정확도를 높인다.

feature-0016 implicit-edges (2026-07-01): FK 로 직접 확인되지 않는 **암묵 JOIN 관계**를 명명 규칙으로
추론(source='inferred')해 연결점을 만들되, 그 연결이 정말 올바른지 **항상 검증**한다:
  - 실제 JOIN 사용 성공(대화) + 실데이터 겹침 프로브(insight) = **양성 신호** → weight↑
  - 실데이터 겹침 0 = **음성 신호** → weight↓ (음성이 더 빠르게 깎이는 비대칭)
  - weight ≤ floor → status='broken'(context·그래프에서 제외, 학습된 '비관계')
  - weight ≥ ceil + 양성 누적 → status='trusted'(신뢰 관계로 재구성)
  - FK(fk_introspect)는 권위적 — 강등 없이 항상 trusted.

설계 원칙:
  - ds-scope: scope_key = 활성 datasource(cfg.get_active_datasource()) + 'common' 캐스케이드
    (kb_metadata 동형). 멀티 데이터소스 격리.
  - 연결: shared.db._pg_connect(RW, autocommit) / _pg_connect_ro(RO). PG 미가용·예외 시 no-op —
    **코어 대화/insight 흐름을 절대 차단하지 않는다**(모든 진입점 try/except + 빈 결과 반환).
  - 정적 confidence(출처 prior)와 동적 weight(관찰/프로브로 갱신)를 분리. read·주입·그래프는 weight 기준.
  - 출처 우선순위: fk_introspect(1.0) > llm_insight(0.6) > conversation(0.4) > inferred(0.3).
"""
from __future__ import annotations

import logging
import re

from modules.utils import _normalize_scope_key, _scope_candidates

_log = logging.getLogger("relationships")

# 출처별 기본 confidence(정적 prior) 및 초기 weight
CONFIDENCE = {"fk_introspect": 1.0, "llm_insight": 0.6, "conversation": 0.4, "inferred": 0.3}
# 즉시 신뢰(권위적)하는 출처 — 나머지는 candidate 로 시작해 강화·검증을 거친다.
_TRUSTED_SOURCES = {"fk_introspect"}

# ── 강화(reinforcement) 파라미터 (feature-0016) ───────────────────────────
# 비대칭 불변식: **모든 동작 구간에서 1회 음성 감쇠 > 1회 양성 상승** 이어야 틀린 관계가 확실히 끊어진다.
#   양성 상승 up(w) = POS_STEP·(1-w) 는 w=BREAK_FLOOR 에서 최대(= POS_STEP·(1-FLOOR) = 0.1275).
#   음성은 **고정 감산** NEG_STEP(= 0.14) 이라 up 최댓값보다 항상 크다 → down>up 전 구간 보장.
#   (초기 곱셈 감쇠 `w*(1-0.34)` 는 추론 시작 weight 0.30 부근 [0.15,0.306] 에서 down<up 으로 역전돼
#    틀린 엣지가 오히려 상승하는 결함이 있었다 — backend 패널 MAJOR. 고정 감산으로 해소.)
_TRUST_CEIL = 0.85          # weight 이 이 이상 + 양성 누적이면 trusted 승격
_BREAK_FLOOR = 0.15         # weight 이 이 이하이면 broken 파단
_POS_STEP = 0.15            # 양성: weight += POS_STEP*(1-weight) (1.0 로 점근 상승 — 신뢰는 천천히)
_NEG_STEP = 0.14            # 음성: weight -= NEG_STEP (고정 감산 — up 최댓값 0.1275 보다 커 항상 더 빠르게 깎임)
_MIN_POS_FOR_TRUST = 2      # trusted 승격에 필요한 최소 누적 양성 신호 수
_PROBE_POS_RATE = 0.5       # 프로브 겹침률 ≥ 이 값이면 양성, == 0 이면 음성, 그 사이는 중립
_PROBE_MIN_SAMPLE = 5       # 음성 판정에 필요한 최소 샘플 수(빈/희소 컬럼 오판 방지)

_INJECT_CAP = 60        # knowledge context 주입 최대 edge 수
_READ_LIMIT = 400       # scope 당 최대 read edge 수
_INTROSPECT_TABLE_CAP = 200  # insight cycle 1회 introspect 최대 테이블 수(과부하 방지)
_INFER_CAP = 400        # 1회 추론 최대 후보 edge 수(8K 규모 폭주 방지)


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

    weight/status(feature-0016 강화상태)는 **재upsert 로 리셋하지 않는다** — 반복 추론이 이미
    파단(broken)된 edge 를 되살리거나 강화된 weight 를 초기화하면 자기교정 루프가 무의미해진다.
    예외: 권위적 출처(fk_introspect)로 재확인되면 weight=1.0·trusted 로 승격(진짜 FK 확인).
    """
    if not (src_table and tgt_table and src_column and tgt_column):
        return False
    if confidence is None:
        confidence = CONFIDENCE.get(source, 0.5)
    init_weight = float(confidence)
    init_status = "trusted" if source in _TRUSTED_SOURCES else "candidate"
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
                " constraint_name, cardinality, source, confidence, weight, status, source_run_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (scope_key, source_table_fqn, source_column, target_table_fqn, target_column) "
                "DO UPDATE SET "
                "  constraint_name = COALESCE(NULLIF(EXCLUDED.constraint_name,''), table_relationships.constraint_name), "
                "  cardinality = COALESCE(NULLIF(EXCLUDED.cardinality,''), table_relationships.cardinality), "
                "  datasource_key = COALESCE(NULLIF(EXCLUDED.datasource_key,''), table_relationships.datasource_key), "
                "  source = CASE WHEN EXCLUDED.confidence >= table_relationships.confidence "
                "                THEN EXCLUDED.source ELSE table_relationships.source END, "
                "  confidence = GREATEST(EXCLUDED.confidence, table_relationships.confidence), "
                # 강화상태 보존 — 권위적 출처(FK)로 재확인될 때만 신뢰 승격 + weight 회복 + 음성카운터 리셋.
                "  weight = CASE WHEN EXCLUDED.source = 'fk_introspect' THEN 1.0 "
                "                ELSE table_relationships.weight END, "
                "  status = CASE WHEN EXCLUDED.source = 'fk_introspect' THEN 'trusted' "
                "                ELSE table_relationships.status END, "
                "  negative_signals = CASE WHEN EXCLUDED.source = 'fk_introspect' THEN 0 "
                "                          ELSE table_relationships.negative_signals END, "
                "  source_run_id = COALESCE(EXCLUDED.source_run_id, table_relationships.source_run_id), "
                "  updated_at = now()",
                (_normalize_scope_key(scope_key), str(datasource_key or ""),
                 str(src_schema or ""), str(src_table), str(src_column),
                 str(tgt_schema or ""), str(tgt_table), str(tgt_column),
                 _fqn(src_schema, src_table), _fqn(tgt_schema, tgt_table),
                 str(constraint_name or ""), str(cardinality or ""),
                 str(source), float(confidence), init_weight, init_status, source_run_id),
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
        # broken(파단) edge 는 주입 대상에서 제외 — 학습된 '비관계'. weight 내림차순(신뢰 우선).
        cur.execute(
            "SELECT source_table_fqn, source_column, target_table_fqn, target_column, "
            "       cardinality, source, confidence, weight, status "
            "FROM table_relationships WHERE scope_key = ANY(%s) AND status <> 'broken' "
            "ORDER BY weight DESC, confidence DESC, source_table_fqn, target_table_fqn LIMIT %s",
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

    rows: (src_fqn, src_col, tgt_fqn, tgt_col, cardinality, source, confidence[, weight, status]) 시퀀스.
    weight/status 는 선택(feature-0016) — 있으면 AI 가 신뢰 수준을 구분하도록 태그를 덧붙인다:
      - candidate / source='inferred'  → `[추정 w=0.30]` (검증 전 — 조심해서 사용)
      - trusted(비-FK)                 → `[신뢰]`
      - fk_introspect                  → 태그 없음(권위적)
    broken 은 애초에 _fetch_relationships 가 제외하므로 여기 도달하지 않는다(직접 호출 시엔 표시).
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
        weight = r[7] if len(r) > 7 else None
        status = r[8] if len(r) > 8 else None
        if status == "broken":     # 직접 호출 방어 — 파단 관계는 주입 금지
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
        trust_s = ""
        if source != "fk_introspect" and status is not None:
            if status == "candidate" or source == "inferred":
                try:
                    trust_s = f" [추정 w={float(weight):.2f}]" if weight is not None else " [추정]"
                except (TypeError, ValueError):
                    trust_s = " [추정]"
            elif status == "trusted":
                trust_s = " [신뢰]"
        out.append(f"- {src_fqn}.{src_col} → {tgt_fqn}.{tgt_col}{card_s}{src_tag}{trust_s}")
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

    feature-0016: 성공한 JOIN 은 그 관계가 실제로 쓰였다는 **양성 신호**이므로, upsert 와 함께 동일
    (무방향) 관계의 기존 edge(특히 암묵 추론 edge)를 강화한다 — AI 사용이 곧 검증. 반환: upsert 한 edge 수.
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
            # 사용 성공 = 양성 신호 → 동일 관계(추론 포함)의 weight 강화. 실패해도 비차단.
            try:
                apply_relationship_signal(c, scope_key, e["src_table"], e["src_column"],
                                          e["tgt_table"], e["tgt_column"], True)
            except Exception:
                pass
    except Exception as exc:
        _log.debug("learn_from_sql_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return n


# ══════════════════════════════════════════════════════════════════════════
# feature-0016 implicit-edges: 강화(reinforcement) 엔진 + 암묵 관계 추론 + 능동 프로브
# ══════════════════════════════════════════════════════════════════════════

# ── 강화 상태 전이 (순수 함수 — 단위 테스트 대상) ─────────────────────────
def next_reinforcement_state(weight, positive_signals, negative_signals, status, source, positive):
    """강화 신호 1건 적용 후의 (weight, positive_signals, negative_signals, status) — 순수 함수.

    FK(fk_introspect)는 권위적 — weight/status 불변(1.0/trusted 유지, 신호만 카운트).
    양성: weight += POS_STEP*(1-weight) (1.0 으로 점근 상승). 음성: weight -= NEG_STEP (고정 감산 —
    up 최댓값보다 커 **전 구간에서 양성보다 빠르게 감쇠**, 틀린 관계 확실 파단).
    전이: weight ≤ floor → broken. weight ≥ ceil 이고 양성 누적 ≥ MIN_POS → trusted. 그 외 candidate.
    """
    try:
        w = float(weight)
    except (TypeError, ValueError):
        w = CONFIDENCE.get(source, 0.5)
    pos = int(positive_signals or 0)
    neg = int(negative_signals or 0)
    if source == "fk_introspect":
        if positive:
            pos += 1
        else:
            neg += 1
        return 1.0, pos, neg, "trusted"
    if positive:
        w = min(1.0, w + _POS_STEP * (1.0 - w))
        pos += 1
    else:
        w = max(0.0, w - _NEG_STEP)
        neg += 1
    if w <= _BREAK_FLOOR:
        st = "broken"
    elif w >= _TRUST_CEIL and pos >= _MIN_POS_FOR_TRUST:
        st = "trusted"
    else:
        st = "candidate"
    return w, pos, neg, st


def apply_relationship_signal(conn, scope_key, a_table, a_col, b_table, b_col, positive) -> int:
    """(a_table.a_col ↔ b_table.b_col) 무방향 관계에 강화/감쇠 신호 1건 적용. 반환: 갱신된 row 수.

    테이블은 leaf 이름으로 매칭(대화 파서는 스키마 미해석, 추론 edge 는 스키마 보유 — leaf 로 정합).
    같은 무방향 관계의 여러 저장 방향(추론 A→B + 대화 B→A)을 모두 갱신. 예외·PG 미가용 시 0(비차단).
    """
    if not (a_table and a_col and b_table and b_col):
        return 0
    scopes = list(_scope_candidates(_normalize_scope_key(scope_key)))
    c, owned = _rw_conn(conn)
    if c is None:
        return 0
    n = 0
    try:
        cur = c.cursor()
        # **원자성**: SELECT … FOR UPDATE + UPDATE 를 한 트랜잭션으로 묶어 cross-process
        # (insight 프로브 ↔ ask-worker 대화학습) lost-update 를 제거. autocommit conn 이라
        # 명시 BEGIN/COMMIT 로 짧은 트랜잭션을 연다. 실패 시 ROLLBACK(부분 갱신 없음).
        try:
            cur.execute("BEGIN")
            cur.execute(
                "SELECT id, weight, positive_signals, negative_signals, status, source "
                "FROM table_relationships WHERE scope_key = ANY(%s) AND ("
                "  (lower(source_table)=lower(%s) AND lower(source_column)=lower(%s) "
                "   AND lower(target_table)=lower(%s) AND lower(target_column)=lower(%s)) OR "
                "  (lower(source_table)=lower(%s) AND lower(source_column)=lower(%s) "
                "   AND lower(target_table)=lower(%s) AND lower(target_column)=lower(%s))) "
                "FOR UPDATE",
                (scopes, a_table, a_col, b_table, b_col, b_table, b_col, a_table, a_col),
            )
            for rid, w, pos, neg, st, src in (cur.fetchall() or []):
                nw, npos, nneg, nst = next_reinforcement_state(w, pos, neg, st, src, positive)
                cur.execute(
                    "UPDATE table_relationships SET weight=%s, positive_signals=%s, "
                    "negative_signals=%s, status=%s, last_validated_at=now(), updated_at=now() "
                    "WHERE id=%s",
                    (float(nw), int(npos), int(nneg), str(nst), rid),
                )
                n += 1
            cur.execute("COMMIT")
        except Exception:
            try:
                cur.execute("ROLLBACK")
            except Exception:
                pass
            n = 0
            raise
        finally:
            cur.close()
    except Exception as exc:
        _log.debug("apply_signal_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return n


# ── 암묵 관계 추론 (FK 미선언 보완 — 명명 규칙 휴리스틱) ─────────────────────
_TABLE_PREFIXES = ("t_", "tb_", "tbl_", "m_", "d_", "f_")   # 게임 DB 흔한 테이블 접두
# 헝가리안(소문자 접두 + 대문자 시작) 은 **대소문자 민감** — 전역 re.I 를 쓰면 [A-Z] 가 소문자까지
# 먹어 'customer_id'→'ustomer' 로 오파싱된다. 접미만 scoped (?i:...) 로 대소문자 무시.
_HUNGARIAN_RE = re.compile(r'^[nsbifgluc]([A-Z]\w*?)_?((?i:id|sn|no|seq|key|code|uid))$')
_KEY_COL_RE = re.compile(r'^(.+?)_?(id|sn|no|seq|key|code|uid)$', re.I)
# 접미 제거 뒤 base 가 이 집합이면 테이블 지시성이 약해 제외(범용 키).
_GENERIC_BASES = {"", "p", "s", "c", "t", "the", "row", "my", "his"}
# heuristic-2(공유 키 컬럼) 대상에서 제외할 범용 컬럼(테이블 지시성 없음).
_GENERIC_KEY_COLS = {"id", "no", "seq", "sn", "uid", "key", "code", "idx", "num",
                     "rownum", "rowid", "regdate", "createdate", "updatedate"}
_SHARED_KEY_MAX_OWNERS = 8   # 이보다 많은 테이블이 공유하는 키는 범용 차원 — pairwise 추론 제외


def _norm_table_token(name):
    """테이블명 → 매칭용 토큰(소문자, 흔한 접두 제거, 후행 복수 s 제거)."""
    s = str(name or "").strip().lower()
    for p in _TABLE_PREFIXES:
        if s.startswith(p) and len(s) > len(p) + 1:
            s = s[len(p):]
            break
    if len(s) > 3 and s.endswith("s"):
        s = s[:-1]
    return s


def _col_key_base(col):
    """컬럼명이 키 형태면 접미 제거·정규화한 base 반환, 아니면 None.

    'customer_id'→'customer', 'AccountSN'→'account', 'nItemNo'→'item'(헝가리안 n 제거).
    """
    s = str(col or "").strip()
    if not s:
        return None
    m = _HUNGARIAN_RE.match(s)
    if m and len(m.group(1)) >= 2:
        return _norm_table_token(m.group(1))
    m = _KEY_COL_RE.match(s)
    if m and len(m.group(1)) >= 2:
        return _norm_table_token(m.group(1))
    return None


def infer_implicit_relationships(schema, tables_columns, *, cap=_INFER_CAP):
    """FK 미선언 스키마에서 명명 규칙으로 암묵 관계 후보를 추론(순수 함수, best-effort).

    tables_columns: {table_name: [column_name, ...]}.
    반환: [{src_schema, src_table, src_column, tgt_schema, tgt_table, tgt_column, heuristic, confidence}]
    후보일 뿐 — 정확도는 프로브·사용 강화가 사후 보정한다(candidate 로 시작). 무방향 dedup.
    """
    if not tables_columns:
        return []
    schema = str(schema or "")
    token_to_tables = {}
    tbl_cols = {}
    for tbl, cols in tables_columns.items():
        cl = [str(c).strip() for c in (cols or []) if str(c).strip()]
        tbl_cols[tbl] = cl
        token_to_tables.setdefault(_norm_table_token(tbl), []).append(tbl)

    def _pk_like(tbl, base):
        cols = tbl_cols.get(tbl, [])
        lc = {c.lower(): c for c in cols}
        cands = [f"{base}_id", f"{base}id", "id", f"{base}_no", f"{base}no",
                 f"{base}_sn", f"{base}sn", f"{base}_seq", "seq", f"{base}_key"]
        for cand in cands:
            if cand.lower() in lc:
                return lc[cand.lower()]
        for c in cols:              # base 를 가리키는 키 형태 컬럼 fallback
            if _col_key_base(c) == base:
                return c
        return None

    edges = []
    seen = set()

    def _add(st, sc, tt, tc, heur, conf):
        if st.lower() == tt.lower():
            return
        key = tuple(sorted([f"{st.lower()}.{sc.lower()}", f"{tt.lower()}.{tc.lower()}"]))
        if key in seen:
            return
        seen.add(key)
        edges.append({"src_schema": schema, "src_table": st, "src_column": sc,
                      "tgt_schema": schema, "tgt_table": tt, "tgt_column": tc,
                      "heuristic": heur, "confidence": conf})

    # heuristic-1: <base>_id 컬럼 → base 이름 테이블의 PK (테이블명 매칭 = 강한 신호)
    for tbl, cols in tbl_cols.items():
        for col in cols:
            base = _col_key_base(col)
            if not base or base in _GENERIC_BASES:
                continue
            targets = [t for t in token_to_tables.get(base, []) if t.lower() != tbl.lower()]
            if len(targets) != 1:      # 애매(0개 또는 다중) → heuristic-1 제외
                continue
            tcol = _pk_like(targets[0], base)
            if tcol:
                _add(tbl, col, targets[0], tcol, "name_fk", round(CONFIDENCE["inferred"] + 0.05, 4))
            if len(edges) >= cap:
                return edges

    # heuristic-2: 접두 있는 키 컬럼이 소수 테이블에 공유 → 후보 join (약한 신호)
    col_owners = {}
    for tbl, cols in tbl_cols.items():
        for col in cols:
            cl = col.lower()
            if cl in _GENERIC_KEY_COLS or _col_key_base(col) is None:
                continue
            col_owners.setdefault(cl, []).append((tbl, col))
    for cl, owners in col_owners.items():
        if len(owners) < 2 or len(owners) > _SHARED_KEY_MAX_OWNERS:
            continue    # 1개=관계아님, 과다=범용 차원(특정 FK 아님)
        for i in range(len(owners)):
            for j in range(i + 1, len(owners)):
                (ta, ca), (tb, cb) = owners[i], owners[j]
                _add(ta, ca, tb, cb, "shared_key", round(CONFIDENCE["inferred"] - 0.05, 4))
                if len(edges) >= cap:
                    return edges
    return edges


def store_inferred_relationships(conn, scope_key, schema, tables_columns, *,
                                 datasource_key="", source_run_id=None, cap=_INFER_CAP) -> int:
    """추론 후보를 table_relationships 에 upsert(source='inferred', status=candidate). 반환: upsert 수.

    이미 존재(FK·대화·기존 추론)하는 관계는 upsert on-conflict 가 강화상태를 보존(파단 부활 없음).
    cap: 1회 추론 상한(insight 워커가 AGENT_RELATIONSHIP_INFER_CAP 을 관통).
    """
    edges = infer_implicit_relationships(schema, tables_columns, cap=int(cap) if cap else _INFER_CAP)
    if not edges:
        return 0
    c, owned = _rw_conn(conn)
    if c is None:
        return 0
    n = 0
    try:
        for e in edges:
            if upsert_relationship(
                c, scope_key,
                src_schema=e["src_schema"], src_table=e["src_table"], src_column=e["src_column"],
                tgt_schema=e["tgt_schema"], tgt_table=e["tgt_table"], tgt_column=e["tgt_column"],
                source="inferred", datasource_key=datasource_key,
                confidence=e["confidence"], source_run_id=source_run_id,
            ):
                n += 1
    except Exception as exc:
        _log.debug("store_inferred_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return n


# ── 능동 프로브 (실데이터 겹침으로 candidate 검증) ─────────────────────────
def _parse_probe_counts(results):
    """프로브 result → (sampled, matched). 첫 행 두 컬럼(COUNT, SUM(EXISTS))."""
    for rset in _iter_result_sets(results):
        rows = rset.get("rows") or []
        if rows and len(rows[0]) >= 2:
            try:
                return int(rows[0][0] or 0), int(rows[0][1] or 0)
            except (TypeError, ValueError):
                return 0, 0
    return 0, 0


def fetch_probe_candidates(conn, scope_key, limit):
    """검증 대상(candidate) edge 목록. 오래 검증 안 된 것·weight 낮은 것 우선.

    반환: [(id, src_schema, src_table, src_column, tgt_schema, tgt_table, tgt_column), ...]
    """
    scopes = list(_scope_candidates(_normalize_scope_key(scope_key)))
    c, owned = _ro_conn(conn)
    if c is None:
        return []
    try:
        cur = c.cursor()
        try:
            cur.execute(
                "SELECT id, source_schema, source_table, source_column, "
                "       target_schema, target_table, target_column "
                "FROM table_relationships "
                "WHERE scope_key = ANY(%s) AND status = 'candidate' "
                "  AND source IN ('inferred', 'conversation', 'llm_insight') "
                "ORDER BY last_validated_at ASC NULLS FIRST, weight ASC LIMIT %s",
                (scopes, int(limit)),
            )
            return cur.fetchall() or []
        finally:
            cur.close()
    except Exception as exc:
        _log.debug("fetch_probe_candidates_failed err=%r", exc)
        return []
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass


def classify_probe(sampled, matched):
    """프로브 카운트 → 신호. 'positive' | 'negative' | 'neutral' (순수 함수).

    겹침률 ≥ _PROBE_POS_RATE → positive. 률 0 이고 표본 ≥ _PROBE_MIN_SAMPLE → negative. 그 외 neutral.
    """
    try:
        sampled = int(sampled)
        matched = int(matched)
    except (TypeError, ValueError):
        return "neutral"
    if sampled <= 0:
        return "neutral"
    rate = matched / float(sampled)
    if rate >= _PROBE_POS_RATE:
        return "positive"
    if matched == 0 and sampled >= _PROBE_MIN_SAMPLE:
        return "negative"
    return "neutral"


def probe_and_reinforce(ds_conn, dialect, scope_key, *, kb_conn=None, raw_execute=None,
                        sample=50, cap=40, timeout_ms=0) -> dict:
    """candidate edge 를 실데이터 겹침 프로브로 검증해 강화/감쇠 (insight worker 용).

    각 edge: src 컬럼 표본 sample개 중 tgt 컬럼에 존재(EXISTS)하는 비율 = 겹침률(classify_probe).
    ds_conn 에서 프로브 SQL(read-only) 실행, 강화는 kb_conn(관계형 SSOT)에 기록. 전부 guarded(비차단).
    timeout_ms: 프로브 statement 시간 상한(운영 DB 폭주 차단 — MySQL MAX_EXECUTION_TIME / MSSQL LOCK_TIMEOUT).
    반환: {"probed", "positive", "negative", "neutral"}.
    """
    rep = {"probed": 0, "positive": 0, "negative": 0, "neutral": 0}
    if (raw_execute is None or dialect is None
            or not hasattr(dialect, "probe_relationship_overlap")):
        return rep
    cands = fetch_probe_candidates(kb_conn, scope_key, cap)
    if not cands:
        return rep
    kc, kowned = _rw_conn(kb_conn)
    if kc is None:
        return rep
    try:
        for (rid, ssch, stbl, scol, tsch, ttbl, tcol) in cands:
            try:
                sql = dialect.probe_relationship_overlap(
                    ssch or "", stbl, scol, tsch or "", ttbl, tcol, int(sample),
                    timeout_ms=int(timeout_ms))
                results, *_ = raw_execute(ds_conn, sql)
                sampled, matched = _parse_probe_counts(results)
                rep["probed"] += 1
                verdict = classify_probe(sampled, matched)
                if verdict == "positive":
                    apply_relationship_signal(kc, scope_key, stbl, scol, ttbl, tcol, True)
                    rep["positive"] += 1
                elif verdict == "negative":
                    apply_relationship_signal(kc, scope_key, stbl, scol, ttbl, tcol, False)
                    rep["negative"] += 1
                else:
                    rep["neutral"] += 1
            except Exception as exc:
                _log.debug("probe_edge_failed id=%s err=%r", rid, exc)
                continue
    finally:
        if kowned and kc is not None:
            try:
                kc.close()
            except Exception:
                pass
    return rep
