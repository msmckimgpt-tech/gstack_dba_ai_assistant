"""feature-0016 metadata-graph: 관계형 메타데이터 → Apache AGE `metadata_kb` 그래프 동기화 + 투영.

관계형 테이블(table_descriptions·column_descriptions·table_relationships·kb_glossary·
glossary_relations)을 SSOT 로 두고, 본 모듈이 AGE property-graph 로 **투영(projection)** 한다.
UI(Cytoscape) 와 AI(knowledge context) 가 같은 그래프를 공유해 정합을 보장한다(FUNCTION.md §4).

그래프 모델 (alembic 0025 에서 라벨 사전선언):
  vertex: Product · Datasource · Schema · Table · Column · GlossaryTerm
  edge  : USES · HAS_SCHEMA · HAS_TABLE · HAS_COLUMN · REFERENCES · RELATED_TERM · DESCRIBES

설계 원칙 (relationships.py 동형):
  - 연결: shared.db._pg_connect(autocommit) RW / _pg_connect_ro() RO. PG 미가용·예외 시 no-op —
    코어 흐름 절대 비차단(모든 진입점 try/except).
  - **shared_preload_libraries='age' 의존**: 앱 role 은 LOAD 불가 → 연결마다 `_set_age_path()` 로
    search_path 만 설정(Phase 0/1a 검증).
  - 멱등: 노드/엣지 MERGE(stable `key` 속성). rebuild 는 drop 후 재생성 아니라 MERGE 누적(비파괴).
  - 8K 테이블 규모: 투영은 검색·k-hop 이웃 한정(전체 덤프 금지, cap 강제).
  - Cypher injection 방어: 모든 값 리터럴은 `_cq()` 이스케이프, 라벨/속성키는 화이트리스트.
"""
from __future__ import annotations

import json
import logging
import math

_log = logging.getLogger("metadata_graph")

GRAPH = "metadata_kb"

# alembic 0025 사전선언 라벨 화이트리스트 (런타임 동적 라벨 생성 금지)
_VLABELS = {"Product", "Datasource", "Schema", "Table", "Column", "GlossaryTerm"}
_ELABELS = {"USES", "HAS_SCHEMA", "HAS_TABLE", "HAS_COLUMN", "REFERENCES", "RELATED_TERM", "DESCRIBES"}
# 노드/엣지 속성 화이트리스트 (Cypher SET 대상 — 임의 키 주입 차단)
#  weight/status: feature-0016 강화 상태 투영(REFERENCES 엣지) — UI 가 신뢰/추정/파단을 구분.
_PROP_KEYS = {"key", "name", "fqn", "scope_key", "description", "source",
              "confidence", "cardinality", "datasource_key", "schema_name",
              "table_name", "column_name", "relation_type", "term",
              "weight", "status", "ordinal"}
# 숫자(float) 리터럴로 SET 하는 속성(문자열 인용 금지)
_NUMERIC_PROP_KEYS = {"confidence", "weight"}
# 정수 리터럴로 SET 하는 속성. feature-0016 graphux5: 컬럼 실제 순서(ordinal).
_INT_PROP_KEYS = {"ordinal"}

_NEIGHBOR_NODE_CAP = 300   # 투영 1회 최대 노드 수 (8K 규모 보호)
_SEARCH_CAP = 80           # 검색 결과 최대 노드 수
_SYNC_BATCH_LOG = 500      # 동기화 진행 로그 간격


# ── 연결 헬퍼 (relationships.py 동형) ─────────────────────────────────────
def _rw_conn(conn):
    if conn is not None:
        return conn, False
    from shared.db import _pg_available, _pg_connect
    if not _pg_available():
        return None, False
    return _pg_connect(autocommit=True), True


def _ro_conn(conn):
    if conn is not None:
        return conn, False
    from shared.db import _pg_available, _pg_connect_ro
    if not _pg_available():
        return None, False
    return _pg_connect_ro(), True


def _set_age_path(cur) -> None:
    """AGE 세션 준비. shared_preload_libraries='age' 전제 — LOAD 불필요(앱 role 은 LOAD 불가)."""
    cur.execute('SET search_path = ag_catalog, "$user", public')


def _ensure_graph_indexes(cur) -> None:
    """AGE metadata_kb 그래프 성능 인덱스(멱등). **없으면 이웃 조회가 전 엣지/노드 Seq Scan 으로
    수초~수십초**(검증: Table depth1 9.4s → 인덱스 후 0.15s, 60x). drop_graph 재생성 후 라벨 테이블이
    새로 만들어지므로 sync 마다 보장한다.
      - vertex: GIN(properties) — `{key:'X'}`(@> containment) 앵커 조회 가속.
      - edge  : btree(start_id)·btree(end_id) — (a)-[r]-(b) traversal 을 vertex id 로 가속(핵심).
    각 CREATE 는 IF NOT EXISTS + try/except(라벨 부재·권한 등 graceful)."""
    for lbl in _VLABELS:
        try:
            cur.execute(f'CREATE INDEX IF NOT EXISTS "ix_mkb_{lbl.lower()}_props" '
                        f'ON metadata_kb."{lbl}" USING gin (properties)')
        except Exception:
            pass
    for lbl in _ELABELS:
        for col, sfx in (("start_id", "start"), ("end_id", "end")):
            try:
                cur.execute(f'CREATE INDEX IF NOT EXISTS "ix_mkb_{lbl.lower()}_{sfx}" '
                            f'ON metadata_kb."{lbl}" ({col})')
            except Exception:
                pass


# ── Cypher 안전 리터럴 ────────────────────────────────────────────────────
def _cq(val) -> str:
    """Python 값 → 안전한 단일인용 Cypher 문자열 리터럴 (injection 방어)."""
    s = "" if val is None else str(val)
    s = (s.replace("\\", "\\\\").replace("'", "\\'")
          .replace("\n", "\\n").replace("\r", "").replace("\t", " "))
    return "'" + s + "'"


def _props_set(var: str, props: dict) -> str:
    """props dict → 'var.k = lit, ...' (화이트리스트 키만). confidence/weight 는 float, ordinal 은 정수 리터럴."""
    parts = []
    for k, v in props.items():
        if k not in _PROP_KEYS:
            continue
        if k in _NUMERIC_PROP_KEYS:
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(fv):   # nan/inf 는 유효 Cypher 숫자 리터럴 아님(M1)
                continue
            parts.append(f"{var}.{k} = {fv}")
        elif k in _INT_PROP_KEYS:
            if v is None:
                continue                # None ordinal 은 미설정(SET 생략 — 기존값 보존)
            try:
                iv = int(v)
            except (TypeError, ValueError):
                continue
            parts.append(f"{var}.{k} = {iv}")   # 정수 리터럴(따옴표 없음, 값이 int() 검증됨 = injection-safe)
        else:
            parts.append(f"{var}.{k} = {_cq(v)}")
    return ", ".join(parts)


def _cypher(cur, query: str, ncols: int):
    """cypher() 실행 + fetchall. ncols = RETURN 컬럼 수(agtype). 실패 시 예외 전파(호출측 try).

    **pgbouncer transaction-mode 안전**: `cypher`·`agtype` 를 모두 `ag_catalog.` 로 정규화해
    세션 search_path 에 의존하지 않는다(SET search_path 가 풀링 트랜잭션 간 유지 안 될 수 있음).

    **injection 방어 (B1)**: Cypher 본문을 dollar-quote 로 감쌀 때, query 에 존재하지 않음이 보장되는
    동적 태그(`$mdgq…$`)를 사용한다. 정적 `$$` 는 값에 `$$` 가 섞이면 breakout → (바인드 파라미터
    없는 execute = simple protocol 이라) 다중 statement SQL 인젝션이 가능했다. 값 내부는 `_cq` 가
    single-quote 이스케이프하고, 본문 전체는 이 태그가 외곽 SQL 탈출을 막는다(이중 방어).
    """
    cols = ", ".join(f"c{i} ag_catalog.agtype" for i in range(ncols))
    tag = "mdgq"
    while f"${tag}$" in query:
        tag += "z"
    dq = f"${tag}$"
    cur.execute(f"SELECT * FROM ag_catalog.cypher('{GRAPH}', {dq} {query} {dq}) AS ({cols})")
    return cur.fetchall()


def _unwrap(agt):
    """agtype 스칼라 → python. 문자열은 JSON 디코드(이스케이프·유니코드 정확), 'null' → None (M3)."""
    if agt is None:
        return None
    s = str(agt)
    if s == "null":
        return None
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            return json.loads(s)   # \n·\t·\uXXXX·\" 등 JSON 이스케이프 정확 처리
        except Exception:
            return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return s


# ── 그래프 쓰기 (MERGE — 멱등) ────────────────────────────────────────────
def _merge_vertex(cur, label: str, key: str, props: dict) -> None:
    if label not in _VLABELS or not key:
        return
    setc = _props_set("n", {**props, "key": key})
    q = f"MERGE (n:{label} {{key: {_cq(key)}}})"
    if setc:
        q += f" SET {setc}"
    q += " RETURN n.key"
    _cypher(cur, q, 1)


def _merge_edge(cur, src_label: str, src_key: str, etype: str,
                dst_label: str, dst_key: str, props: dict | None = None) -> None:
    if (src_label not in _VLABELS or dst_label not in _VLABELS
            or etype not in _ELABELS or not src_key or not dst_key):
        return
    q = (f"MATCH (a:{src_label} {{key: {_cq(src_key)}}}), "
         f"(b:{dst_label} {{key: {_cq(dst_key)}}}) "
         f"MERGE (a)-[r:{etype}]->(b)")
    if props:
        setc = _props_set("r", props)
        if setc:
            q += f" SET {setc}"
    q += " RETURN 1"
    _cypher(cur, q, 1)


# ── key 규약: scope:fqn (scope 격리) ──────────────────────────────────────
def _vkey(scope: str, fqn: str) -> str:
    return f"{scope or 'common'}:{fqn}"


def _rag_effective(ds, object_key, schema_name, table_name):
    """rag_objects 행 → (효과적 스키마=클러스터 카테고리, 테이블명).

    MSSQL 은 schema_name 이 리터럴 'dbo'(기본 스키마)라 DB 차원이 소실되고 다중 DB 동명 테이블이
    충돌한다. 정규화된 DB명은 object_key(`<ds>:db.dbo.table` = 3+ 세그먼트)에 있으므로 DB명을 스키마로 쓴다.
    MySQL 은 object_key 가 `<ds>:db.table`(2 세그먼트)이라 schema_name(=DB)과 동일 → 변화 없음.
    파싱 불가 시 schema_name/table_name 으로 fallback.
    """
    ok = object_key or ""
    pref = f"{ds or ''}:"
    if ok.startswith(pref):
        ok = ok[len(pref):]
    parts = [p for p in ok.split(".") if p] if ok else []
    if len(parts) >= 3:
        return parts[0], parts[-1]          # db.schema.table → (db, table) — 중간 'dbo' 제거
    if len(parts) == 2:
        return parts[0], parts[1]           # db.table
    return (schema_name or ""), table_name


# ── 고수준 동기화 (관계형 → 그래프) ───────────────────────────────────────
def sync_table(cur, scope, schema, table, description=None, source="manual") -> None:
    """Schema·Table 노드 + HAS_TABLE 엣지 MERGE.

    description=None 이면 description 속성을 **건드리지 않는다**(rag_objects 노드 투영이 큐레이션
    설명을 덮어쓰지 않도록). 빈 문자열("")은 명시적으로 빈 설명을 set."""
    fqn = f"{schema}.{table}" if schema else table
    skey = _vkey(scope, schema or "(default)")
    tkey = _vkey(scope, fqn)
    _merge_vertex(cur, "Schema", skey,
                  {"name": schema or "(default)", "fqn": schema or "(default)", "scope_key": scope})
    tprops = {"name": table, "fqn": fqn, "scope_key": scope,
              "schema_name": schema or "", "table_name": table, "source": source}
    if description is not None:
        tprops["description"] = description
    _merge_vertex(cur, "Table", tkey, tprops)
    _merge_edge(cur, "Schema", skey, "HAS_TABLE", "Table", tkey)


def sync_column(cur, scope, schema, table, column, description="", source="manual", ordinal=None) -> None:
    """Column 노드 + HAS_COLUMN 엣지 MERGE (Table 선행 가정 또는 동시 MERGE).

    feature-0016 graphux5: ordinal(실제 스키마 컬럼 순서, 1-based) 을 Column 정점 속성으로 투영한다.
    None 이면 SET 생략(기존 ordinal 보존) — _props_set 이 정수 리터럴로 처리(injection-safe)."""
    tfqn = f"{schema}.{table}" if schema else table
    cfqn = f"{tfqn}.{column}"
    tkey = _vkey(scope, tfqn)
    ckey = _vkey(scope, cfqn)
    _merge_vertex(cur, "Table", tkey,
                  {"name": table, "fqn": tfqn, "scope_key": scope,
                   "schema_name": schema or "", "table_name": table})
    _merge_vertex(cur, "Column", ckey,
                  {"name": column, "fqn": cfqn, "scope_key": scope,
                   "table_name": table, "column_name": column,
                   "description": description, "source": source, "ordinal": ordinal})
    _merge_edge(cur, "Table", tkey, "HAS_COLUMN", "Column", ckey)


def _anchor_relationship_column(cur, scope, tbl_fqn, col) -> str:
    """REFERENCES 끝점 Column 을 소속 Table(·Schema)에 앵커링하고 Column key 반환 (rel-selfheal).

    과거에는 Column 정점만 MERGE 해, 미큐레이션 컬럼(HAS_COLUMN 부재)이 **고아 노드**로 떠서
    그래프 뷰에서 추정 점선이 실 테이블에 붙지 않았다. 테이블 fqn(`db.table`)에서 Table·Schema 를
    유도해 HAS_TABLE/HAS_COLUMN 체인을 보장한다. description/source/ordinal 은 건드리지 않아
    (SET 생략) 큐레이션·rag 투영과 비파괴 공존한다. fqn 에 스키마 세그먼트가 없으면(레거시
    ''-slot) 종전과 같이 Column 만 MERGE — 잘못된 Table 키 생성을 피한다.
    """
    ckey = _vkey(scope, f"{tbl_fqn}.{col}")
    parts = [p for p in str(tbl_fqn or "").split(".") if p]
    table = parts[-1] if parts else ""
    schema = ".".join(parts[:-1]) if len(parts) >= 2 else ""
    _merge_vertex(cur, "Column", ckey,
                  {"name": col, "fqn": f"{tbl_fqn}.{col}", "scope_key": scope,
                   "column_name": col})
    if table and schema:
        tkey = _vkey(scope, tbl_fqn)
        skey = _vkey(scope, schema)
        _merge_vertex(cur, "Table", tkey,
                      {"name": table, "fqn": tbl_fqn, "scope_key": scope,
                       "schema_name": schema, "table_name": table})
        _merge_vertex(cur, "Schema", skey,
                      {"name": schema, "fqn": schema, "scope_key": scope})
        _merge_edge(cur, "Schema", skey, "HAS_TABLE", "Table", tkey)
        _merge_edge(cur, "Table", tkey, "HAS_COLUMN", "Column", ckey)
    return ckey


def sync_relationship(cur, scope, src_fqn, src_col, tgt_fqn, tgt_col,
                      cardinality="", source="fk_introspect", confidence=1.0,
                      weight=None, status="") -> None:
    """REFERENCES 엣지 (Column→Column) MERGE. 양끝 Column 노드 + Table/Schema 앵커링 보장.

    weight/status(feature-0016): 동적 신뢰 가중치·상태(candidate/trusted/broken)를 엣지에 투영해
    UI 가 신뢰 실선 / 추정 점선으로 구분. broken 은 애초에 sync_graph 가 투영에서 제외한다.
    """
    s_ckey = _anchor_relationship_column(cur, scope, src_fqn, src_col)
    t_ckey = _anchor_relationship_column(cur, scope, tgt_fqn, tgt_col)
    eprops = {"cardinality": cardinality, "source": source, "confidence": confidence}
    if weight is not None:
        eprops["weight"] = weight
    if status:
        eprops["status"] = status
    _merge_edge(cur, "Column", s_ckey, "REFERENCES", "Column", t_ckey, eprops)


def delete_relationship(cur, scope, src_fqn, src_col, tgt_fqn, tgt_col) -> None:
    """REFERENCES 엣지 삭제 — broken(파단) 관계를 그래프에서 제거해 SSOT 와 정합(feature-0016).

    MERGE 는 가산적이라, candidate/trusted 로 투영됐던 엣지가 이후 broken 으로 감쇠해도 그래프에
    stale 하게 남는다(backend 패널 MAJOR). sync_graph 가 broken 행마다 이 함수를 호출해 회수한다.
    노드는 남기고 엣지만 삭제(다른 관계가 그 컬럼을 참조할 수 있음). 멱등(없으면 no-op)."""
    s_ckey = _vkey(scope, f"{src_fqn}.{src_col}")
    t_ckey = _vkey(scope, f"{tgt_fqn}.{tgt_col}")
    q = (f"MATCH (a:Column {{key: {_cq(s_ckey)}}})-[r:REFERENCES]->(b:Column {{key: {_cq(t_ckey)}}}) "
         f"DELETE r RETURN 1")
    _cypher(cur, q, 1)


def sync_glossary_term(cur, scope, term, definition="", source="manual") -> None:
    gkey = _vkey(scope, f"term:{term}")
    _merge_vertex(cur, "GlossaryTerm", gkey,
                  {"name": term, "term": term, "fqn": term, "scope_key": scope,
                   "description": definition, "source": source})


def sync_glossary_relation(cur, scope, from_term, to_term, relation_type="similar") -> None:
    _merge_edge(cur, "GlossaryTerm", _vkey(scope, f"term:{from_term}"),
                "RELATED_TERM", "GlossaryTerm", _vkey(scope, f"term:{to_term}"),
                {"relation_type": relation_type})


# ── 전체 동기화 (관계형 테이블 → 그래프) ──────────────────────────────────
def sync_graph(conn=None, scope_key=None) -> dict:
    """관계형 SSOT 를 읽어 metadata_kb 그래프로 투영. 반환: 카운트 telemetry.

    멱등(MERGE) — 반복 호출 안전. 예외는 삼키고 부분 카운트 반환(비차단).
    scope_key=None 이면 모든 scope 동기화.
    """
    rep = {"rag_tables": 0, "tables": 0, "columns": 0, "relationships": 0,
           "relationships_deleted": 0, "glossary": 0, "glossary_relations": 0, "errors": 0}
    c, owned = _rw_conn(conn)
    if c is None:
        return rep
    try:
        cur = c.cursor()
        _set_age_path(cur)
        _ensure_graph_indexes(cur)   # 성능 인덱스 보장(이웃 조회 60x) — drop_graph 재생성 생존
        scope_filter = "" if scope_key is None else "WHERE scope_key = %s"
        sf_args = () if scope_key is None else (scope_key,)

        # 0) rag_objects (auto-discovered 스키마/테이블) → datasource_key 별 노드 베이스.
        #    각 데이터소스가 그래프를 갖게 하는 핵심(table_descriptions 는 1개 ds 만 커버).
        #    description=None → 큐레이션 설명을 덮어쓰지 않음(아래 1·2 단계가 layering). 먼저 실행.
        #    **MSSQL 'dbo' 보정**: rag_objects.schema_name 은 MSSQL 에서 리터럴 'dbo'(기본 스키마)라
        #    DB 차원이 소실되고 다중 DB 동명 테이블(예: 23개 DB 의 dbo.T_ErrorLog)이 한 노드로 충돌한다.
        #    DB명은 object_key(`<ds>:db.dbo.table`)에 있으므로 그걸 파싱해 DB명을 스키마(클러스터)로 사용.
        try:
            rag_where = "object_type = 'table' AND datasource_key <> '' AND table_name <> ''"
            rag_args = ()
            if scope_key is not None:
                rag_where += " AND datasource_key = %s"
                rag_args = (scope_key,)
            cur.execute(f"SELECT datasource_key, schema_name, table_name, object_key "
                        f"FROM rag_objects WHERE {rag_where}", rag_args)
            for ds, sch, tbl, okey in cur.fetchall():
                try:
                    eff_sch, eff_tbl = _rag_effective(ds, okey, sch, tbl)
                    sync_table(cur, ds, eff_sch, eff_tbl, description=None, source="insight")
                    rep["rag_tables"] += 1
                except Exception:
                    rep["errors"] += 1
        except Exception:
            pass  # rag_objects 부재(구버전)·조회 실패 — graceful(다른 단계 계속)

        # 1) table_descriptions
        cur.execute(f"SELECT scope_key, schema_name, table_name, description, source "
                    f"FROM table_descriptions {scope_filter}", sf_args)
        for sc, sch, tbl, desc, src in cur.fetchall():
            try:
                sync_table(cur, sc, sch or "", tbl, desc or "", src or "manual")
                rep["tables"] += 1
            except Exception:
                rep["errors"] += 1
        # 2) column_descriptions (feature-0016 graphux5: ordinal 투영 — 그래프 컬럼 세로 정렬용)
        #    ordinal 컬럼 부재(마이그 미적용 구 DB) 등 SELECT 실패는 graceful — 다른 단계(관계/용어) 계속.
        try:
            cur.execute(f"SELECT scope_key, schema_name, table_name, column_name, description, source, ordinal "
                        f"FROM column_descriptions {scope_filter}", sf_args)
            for sc, sch, tbl, col, desc, src, ordn in cur.fetchall():
                try:
                    sync_column(cur, sc, sch or "", tbl, col, desc or "", src or "manual", ordinal=ordn)
                    rep["columns"] += 1
                except Exception:
                    rep["errors"] += 1
        except Exception:
            pass  # column_descriptions 조회 실패(구 DB·권한) — 비차단(다음 단계 계속)
        # 3) table_relationships — broken(파단)은 그래프에서 **삭제**(가산적 MERGE 라 stale 방지,
        #    학습된 '비관계'), 그 외는 weight/status 와 함께 투영. (전량 스캔 후 status 로 분기.)
        rel_where = "" if scope_key is None else "WHERE scope_key = %s"
        cur.execute(f"SELECT scope_key, source_table_fqn, source_column, target_table_fqn, "
                    f"target_column, cardinality, source, confidence, weight, status "
                    f"FROM table_relationships {rel_where}", sf_args)
        for sc, sfqn, scol, tfqn, tcol, card, src, conf, wgt, st in cur.fetchall():
            try:
                if st == "broken":
                    delete_relationship(cur, sc, sfqn, scol, tfqn, tcol)
                    rep["relationships_deleted"] += 1
                else:
                    sync_relationship(cur, sc, sfqn, scol, tfqn, tcol, card or "",
                                      src or "fk_introspect", conf if conf is not None else 1.0,
                                      weight=wgt, status=st or "")
                    rep["relationships"] += 1
            except Exception:
                rep["errors"] += 1
        # 4) kb_glossary
        try:
            cur.execute(f"SELECT scope_key, term, definition, source "
                        f"FROM kb_glossary {scope_filter}", sf_args)
            for sc, term, defn, src in cur.fetchall():
                try:
                    sync_glossary_term(cur, sc, term, defn or "", src or "manual")
                    rep["glossary"] += 1
                except Exception:
                    rep["errors"] += 1
        except Exception:
            pass  # kb_glossary 없을 수 있음
        # 5) glossary_relations (term id → term 매핑)
        try:
            cur.execute(
                "SELECT g1.scope_key, g1.term, g2.term, gr.relation_type "
                "FROM glossary_relations gr "
                "JOIN kb_glossary g1 ON g1.id = gr.from_id "
                "JOIN kb_glossary g2 ON g2.id = gr.to_id")
            for sc, ft, tt, rt in cur.fetchall():
                try:
                    sync_glossary_relation(cur, sc, ft, tt, rt or "similar")
                    rep["glossary_relations"] += 1
                except Exception:
                    rep["errors"] += 1
        except Exception:
            pass
        cur.close()
    except Exception as exc:
        _log.warning("sync_graph_failed err=%r", exc)
        rep["errors"] += 1
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return rep


# ── 투영 (그래프 → {nodes, edges}) ───────────────────────────────────────
def _as_int(v):
    """agtype/JSON 스칼라 → int | None (ordinal 정규화). 실패 시 None."""
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _node_dict(row):
    return {"label": _unwrap(row[0]), "key": _unwrap(row[1]), "name": _unwrap(row[2]),
            "fqn": _unwrap(row[3]), "description": _unwrap(row[4]), "source": _unwrap(row[5]),
            "ordinal": _as_int(_unwrap(row[6]))}


def search_nodes(query: str, limit: int = 50, scope: str | None = None, conn=None) -> list:
    """이름/FQN 부분일치 노드 검색(대소문자 무관). scope 지정 시 해당 datasource 노드만. 8K 규모 보호 cap."""
    out = []
    if not query:
        return out
    limit = min(int(limit or 50), _SEARCH_CAP)
    c, owned = _ro_conn(conn)
    if c is None:
        return out
    try:
        cur = c.cursor()
        _set_age_path(cur)
        ql = _cq(query.lower())
        scope_clause = f" AND n.scope_key = {_cq(scope)}" if scope else ""
        rows = _cypher(cur,
            f"MATCH (n) WHERE (toLower(n.name) CONTAINS {ql} OR toLower(n.fqn) CONTAINS {ql}){scope_clause} "
            f"RETURN label(n), n.key, n.name, n.fqn, n.description, n.source, n.ordinal LIMIT {limit}", 7)
        out = [_node_dict(r) for r in rows]
        # feature-0016 graphux5: pg_trgm 실측 유사도 점수(검색어 대비) 부여 + 내림차순 정렬.
        #   Cypher CONTAINS 로 얻은 후보의 name/fqn 에 pg_trgm similarity() 를 1왕복으로 계산해 score(0~1)
        #   를 각 노드에 실어 UI 가 "검색어와 얼마나 유사한지"를 명시 표시하게 한다(요청 항목1). 값은 전부
        #   파라미터 바인딩(injection-safe). pg_trgm 부재/실패 시 score 없이 원순서 반환(graceful).
        if out:
            try:
                rows_sql, vparams = [], []
                for i, nd in enumerate(out):
                    rows_sql.append("(%s::int, %s, %s)")
                    vparams.extend([i, nd.get("name") or "", nd.get("fqn") or ""])
                cur.execute(
                    "SELECT x.i, GREATEST(similarity(lower(x.nm), lower(%s)), "
                    "                     similarity(lower(x.fq), lower(%s))) AS score "
                    "FROM (VALUES " + ",".join(rows_sql) + ") AS x(i, nm, fq)",
                    tuple([query, query] + vparams))
                smap = {int(r[0]): float(r[1]) for r in cur.fetchall()}
                for i, nd in enumerate(out):
                    nd["score"] = round(smap.get(i, 0.0), 4)
                out.sort(key=lambda n: (n.get("score") or 0.0), reverse=True)
            except Exception as exc:
                _log.debug("search_nodes_score_failed err=%r", exc)
        cur.close()
    except Exception as exc:
        _log.debug("search_nodes_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return out


def scope_roots(scope: str, limit: int = 200, conn=None) -> dict:
    """데이터소스(scope) 진입 그래프 — Schema -[:HAS_TABLE]-> Table 서브그래프(cap 적용).

    그래프뷰에서 datasource 선택 시 검색 없이 '이 데이터소스의 그래프'를 즉시 보여준다.
    cap 초과 datasource 는 부분 표시(나머지는 검색·이웃확장). 빈 datasource 는 {nodes:[],edges:[]}.
    """
    result = {"nodes": [], "edges": []}
    if not scope:
        return result
    limit = min(int(limit or 200), _NEIGHBOR_NODE_CAP)
    c, owned = _ro_conn(conn)
    if c is None:
        return result
    try:
        cur = c.cursor()
        _set_age_path(cur)
        sc = _cq(scope)
        rows = _cypher(cur,
            f"MATCH (s:Schema)-[:HAS_TABLE]->(t:Table) WHERE s.scope_key = {sc} "
            f"RETURN s.key, s.name, s.fqn, t.key, t.name, t.fqn, t.description, t.source "
            f"LIMIT {limit}", 8)
        nodes = {}
        for r in rows:
            skey = _unwrap(r[0]); tkey = _unwrap(r[3])
            if skey and skey not in nodes:
                nodes[skey] = {"label": "Schema", "key": skey, "name": _unwrap(r[1]),
                               "fqn": _unwrap(r[2]), "description": None, "source": None}
            if tkey and tkey not in nodes:
                nodes[tkey] = {"label": "Table", "key": tkey, "name": _unwrap(r[4]),
                               "fqn": _unwrap(r[5]), "description": _unwrap(r[6]), "source": _unwrap(r[7])}
            if skey and tkey:
                result["edges"].append({"source": skey, "target": tkey, "type": "HAS_TABLE",
                                        "cardinality": None, "edge_source": None})
        # 테이블이 없는 datasource 도 Schema 만이라도 보여줌
        if not nodes:
            srows = _cypher(cur,
                f"MATCH (s:Schema) WHERE s.scope_key = {sc} "
                f"RETURN s.key, s.name, s.fqn LIMIT {limit}", 3)
            for r in srows:
                skey = _unwrap(r[0])
                if skey:
                    nodes[skey] = {"label": "Schema", "key": skey, "name": _unwrap(r[1]),
                                   "fqn": _unwrap(r[2]), "description": None, "source": None}
        result["nodes"] = list(nodes.values())
        cur.close()
    except Exception as exc:
        _log.debug("scope_roots_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return result


def _node_from_props(label: str, props: dict) -> dict:
    """라벨 테이블 properties(dict) → 노드 dict. _node_dict 와 동일 shape."""
    return {"label": label, "key": props.get("key"), "name": props.get("name"),
            "fqn": props.get("fqn"), "description": props.get("description"),
            "source": props.get("source"), "ordinal": _as_int(props.get("ordinal"))}


def _gid_array(gids) -> str:
    """graphid 정수 목록 → `ARRAY['<int>'::ag_catalog.graphid, ...]` SQL 리터럴.
    gids 는 전부 DB 에서 온 정수라 int() 검증만으로 injection-safe(문자열 보간 없음)."""
    return "ARRAY[" + ", ".join(f"'{int(g)}'::ag_catalog.graphid" for g in gids) + "]"


def neighborhood(node_key: str, depth: int = 1, conn=None) -> dict:
    """node_key 중심 k-hop 이웃 {nodes, edges}. 방향 보존 BFS + node cap(8K 규모 보호).

    **성능**: Cypher `MATCH (a)-[r]-(b) WHERE a.key IN [...]` 는 GIN 미활용(vertex 라벨 전체
    Seq Scan, 측정 332ms/hop) + startNode/endNode 방향보존 시 3.5x 악화 + UNWIND `{key:k}`(변수
    containment)는 GIN 미계획으로 hang. 그래서 AGE Cypher 플래너를 우회한 **raw graphid id-bound
    SQL** 로 재작성: (1) key→graphid = `properties @> {"key":..}`(GIN, 파라미터화 injection-safe),
    (2) 이웃 = 엣지 라벨 테이블 `start_id/end_id = ANY(frontier)`(ix_mkb_*_start/end btree),
    (3) 해소 = vertex 라벨 테이블 `id = ANY(gids)`(pk). 측정 45ms(112엣지) vs Cypher 332ms.
    **방향**: start_id=source, end_id=target 로 물리적 저장 방향 보존(무방향 -[r]- 의 프론티어 기준
    역전·역중복 버그 제거). ag_catalog.ag_label 은 앱 role 권한 없음 → 라벨명은 _VLABELS/_ELABELS
    상수로 순회(gid 는 정확히 한 라벨 테이블에만 속함)."""
    result = {"nodes": [], "edges": []}
    if not node_key:
        return result
    depth = max(1, min(int(depth or 1), 3))
    c, owned = _ro_conn(conn)
    if c is None:
        return result
    try:
        cur = c.cursor()
        _set_age_path(cur)
        seen_nodes = {}    # key -> node dict
        gid2key = {}       # graphid(int) -> key
        vlabels = sorted(_VLABELS)   # 결정적 순서
        elabels = sorted(_ELABELS)
        # (1) 시작 노드: vertex 라벨 UNION ALL 을 GIN containment 로 1왕복 조회(파라미터화 = injection-safe).
        #     key 는 라벨 전역 유일(ds:db / ds:db.table / ds:db.table.col)이라 최대 1개 매칭.
        key_param = json.dumps({"key": node_key})
        start_sql = " UNION ALL ".join(
            f'SELECT id::text AS gid, properties::text AS props, \'{lbl}\' AS lbl '
            f'FROM metadata_kb."{lbl}" WHERE properties @> %s::ag_catalog.agtype'
            for lbl in vlabels) + " LIMIT 1"
        cur.execute(start_sql, tuple([key_param] * len(vlabels)))
        srow = cur.fetchone()
        if not srow:
            cur.close()
            return result
        sg0 = int(srow[0]); sprops = json.loads(srow[1]); slbl = srow[2]
        skey = sprops.get("key") or node_key
        seen_nodes[skey] = _node_from_props(slbl, sprops)
        gid2key[sg0] = skey
        frontier = [sg0]
        seen_edges = set()
        for _hop in range(depth):
            if not frontier or len(seen_nodes) >= _NEIGHBOR_NODE_CAP:
                break
            farr = _gid_array(frontier)
            # (2) 프론티어에 걸린 엣지를 엣지 라벨 UNION ALL 로 1왕복 수집(방향=start->end 보존).
            edge_sql = " UNION ALL ".join(
                f'SELECT start_id::text AS s, end_id::text AS e, properties::text AS p, \'{et}\' AS et '
                f'FROM metadata_kb."{et}" WHERE start_id = ANY({farr}) OR end_id = ANY({farr})'
                for et in elabels) + f" LIMIT {_NEIGHBOR_NODE_CAP * 4}"
            cur.execute(edge_sql)
            edge_hits = []   # (start_gid, end_gid, etype, cardinality, edge_source, weight, status)
            neigh_gids = set()
            for s, e, pr, et in cur.fetchall():
                sg = int(s); eg = int(e); ep = json.loads(pr) if pr else {}
                # weight/status(feature-0016): REFERENCES 엣지 강화상태 투영 — UI 신뢰/추정/파단 구분.
                edge_hits.append((sg, eg, et, ep.get("cardinality"), ep.get("source"),
                                  ep.get("weight"), ep.get("status")))
                if sg not in gid2key:
                    neigh_gids.add(sg)
                if eg not in gid2key:
                    neigh_gids.add(eg)
            # (3) 신규 이웃 graphid 해소 — vertex 라벨 UNION ALL 로 1왕복. cap 도달 시 중단.
            next_frontier = []
            if neigh_gids:
                narr = _gid_array(neigh_gids)
                resolve_sql = " UNION ALL ".join(
                    f'SELECT id::text AS gid, properties::text AS p, \'{lbl}\' AS lbl '
                    f'FROM metadata_kb."{lbl}" WHERE id = ANY({narr})'
                    for lbl in vlabels)
                cur.execute(resolve_sql)
                for idt, pt, lbl in cur.fetchall():
                    if len(seen_nodes) >= _NEIGHBOR_NODE_CAP:
                        break
                    g = int(idt); props = json.loads(pt); k = props.get("key")
                    if not k:
                        continue
                    gid2key[g] = k
                    if k not in seen_nodes:
                        seen_nodes[k] = _node_from_props(lbl, props)
                        next_frontier.append(g)
            # (4) 엣지 빌드 — 양 끝점이 해소된 것만, 방향(source=start,target=end) + dedup.
            for sg, eg, et, card, esrc, ewgt, estatus in edge_hits:
                sk = gid2key.get(sg); tk = gid2key.get(eg)
                if not sk or not tk:   # cap 로 미해소된 이웃과의 엣지는 생략
                    continue
                ekey = (sg, et, eg)
                if ekey in seen_edges:
                    continue
                # broken(feature-0016)은 sync 가 삭제하지만 감쇠~다음 sync 창 방어로 이웃 투영에서도 제외.
                if estatus == "broken":
                    continue
                seen_edges.add(ekey)
                result["edges"].append({"source": sk, "target": tk, "type": et,
                                        "cardinality": card, "edge_source": esrc,
                                        "weight": ewgt, "status": estatus})
            frontier = next_frontier
        result["nodes"] = list(seen_nodes.values())
        cur.close()
    except Exception as exc:
        _log.debug("neighborhood_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return result
