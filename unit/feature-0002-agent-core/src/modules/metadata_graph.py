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
import os

_log = logging.getLogger("metadata_graph")

GRAPH = "metadata_kb"

# alembic 0025(+0034 Routine) 사전선언 라벨 화이트리스트 (런타임 동적 라벨 생성 금지)
_VLABELS = {"Product", "Datasource", "Schema", "Table", "Column", "GlossaryTerm", "Routine"}
_ELABELS = {"USES", "HAS_SCHEMA", "HAS_TABLE", "HAS_COLUMN", "REFERENCES", "RELATED_TERM", "DESCRIBES",
            "HAS_ROUTINE", "ROUTINE_USES"}
# 노드/엣지 속성 화이트리스트 (Cypher SET 대상 — 임의 키 주입 차단)
#  weight/status: feature-0016 강화 상태 투영(REFERENCES 엣지) — UI 가 신뢰/추정/파단을 구분.
#  routine_type/params: 함수·프로시저 노드(graph-funcproc, ADR-016).
#  semantic_cluster_id/label: feature-0016 Phase C(ADR-013 후속) 의미 클러스터 투영 — 프론트 sim-group 서버 신호.
_PROP_KEYS = {"key", "name", "fqn", "scope_key", "description", "source",
              "confidence", "cardinality", "datasource_key", "schema_name",
              "table_name", "column_name", "relation_type", "term",
              "weight", "status", "ordinal", "routine_type", "params",
              "semantic_cluster_id", "semantic_cluster_label", "cross_ds"}
# 숫자(float) 리터럴로 SET 하는 속성(문자열 인용 금지)
_NUMERIC_PROP_KEYS = {"confidence", "weight"}
# 정수 리터럴로 SET 하는 속성. feature-0016 graphux5: 컬럼 실제 순서(ordinal). Phase C: 의미 클러스터 id.
_INT_PROP_KEYS = {"ordinal", "semantic_cluster_id"}
# None 이 "미설정(skip)"이 아니라 "명시적 clear(= null)"를 의미하는 속성. Phase C: rag_objects 가 클러스터의
# SSOT 라, 테이블이 클러스터에서 이탈(→NULL)하면 그래프 정점의 stale cluster_id 를 반드시 null 로 지워야
# phantom be: 그룹(리뷰 MAJOR-2)이 안 생긴다. sync_table 은 _UNSET 센티넬로 "미전달(보존)"과 "None(clear)"을 구분.
_NULLABLE_PROP_KEYS = {"semantic_cluster_id", "semantic_cluster_label"}
_UNSET = object()   # sync_table cluster 인자 "미전달" 센티넬(≠ 명시 None=clear)

_NEIGHBOR_NODE_CAP = 300   # 투영 1회 최대 노드 수 (8K 규모 보호)
_SEARCH_CAP = 80           # 검색 결과 최대 노드 수
_SYNC_BATCH_LOG = 500      # 동기화 진행 로그 간격
# insight-load-spread: sync_graph 의 batched commit 크기. 이 개수의 MERGE 마다 1회 커밋으로 묶어
# 개별-커밋(autocommit) 시 8K 규모 5.7만 WAL fsync 폭주(30분 cron 스파이크)를 ~100 회로 줄인다.
_SYNC_MERGE_BATCH = max(1, int(os.getenv("AGENT_METADATA_GRAPH_SYNC_BATCH", "500") or "500"))


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
        if k in _NULLABLE_PROP_KEYS and v is None:
            parts.append(f"{var}.{k} = null")   # 명시적 clear(un-cluster 반영 — MAJOR-2). AGE 는 =null 로 속성 제거.
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
def sync_table(cur, scope, schema, table, description=None, source="manual",
               cluster_id=_UNSET, cluster_label=_UNSET) -> None:
    """Schema·Table 노드 + HAS_TABLE 엣지 MERGE.

    description=None 이면 description 속성을 **건드리지 않는다**(rag_objects 노드 투영이 큐레이션
    설명을 덮어쓰지 않도록). 빈 문자열("")은 명시적으로 빈 설명을 set.
    cluster_id/cluster_label(Phase C): 기본 _UNSET=미전달(보존). rag_objects 투영은 **항상 현재값(None 포함)을
    전달** — None 이면 _props_set 이 `= null` 로 clear(테이블이 클러스터에서 이탈 시 stale phantom 그룹 방지,
    리뷰 MAJOR-2). scope_roots/schema_tables 가 RETURN → 프론트 sim-group 서버 신호."""
    fqn = f"{schema}.{table}" if schema else table
    skey = _vkey(scope, schema or "(default)")
    tkey = _vkey(scope, fqn)
    _merge_vertex(cur, "Schema", skey,
                  {"name": schema or "(default)", "fqn": schema or "(default)", "scope_key": scope})
    tprops = {"name": table, "fqn": fqn, "scope_key": scope,
              "schema_name": schema or "", "table_name": table, "source": source}
    if description is not None:
        tprops["description"] = description
    if cluster_id is not _UNSET:
        tprops["semantic_cluster_id"] = cluster_id      # None → _props_set 이 = null 로 clear
    if cluster_label is not _UNSET:
        tprops["semantic_cluster_label"] = cluster_label
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
                      weight=None, status="", tgt_scope=None) -> None:
    """REFERENCES 엣지 (Column→Column) MERGE. 양끝 Column 노드 + Table/Schema 앵커링 보장.

    weight/status(feature-0016): 동적 신뢰 가중치·상태(candidate/trusted/broken)를 엣지에 투영해
    UI 가 신뢰 실선 / 추정 점선으로 구분. broken 은 애초에 sync_graph 가 투영에서 제외한다.
    tgt_scope(crossds-rel, ADR-019): 대상 끝점 scope(기본=scope=src). 크로스-ds 관계는 각 끝점을 **자기 scope**
    로 앵커 → _vkey(scope:fqn) 가 서로 다른 namespace 라 자동 분리. tgt_scope != scope 이면 엣지에 cross_ds 속성
    (프론트 교차DB 표식 + node_analysis 완화). neighborhood BFS 는 scope-무관이라 크로스 엣지가 자동 노출."""
    src_scope = scope
    tscope = tgt_scope if tgt_scope is not None else scope
    s_ckey = _anchor_relationship_column(cur, src_scope, src_fqn, src_col)
    t_ckey = _anchor_relationship_column(cur, tscope, tgt_fqn, tgt_col)
    eprops = {"cardinality": cardinality, "source": source, "confidence": confidence}
    if weight is not None:
        eprops["weight"] = weight
    if status:
        eprops["status"] = status
    if tscope != src_scope:
        eprops["cross_ds"] = "1"   # 교차 데이터소스 엣지(프론트 표식·node_analysis 완화)
    _merge_edge(cur, "Column", s_ckey, "REFERENCES", "Column", t_ckey, eprops)


def delete_relationship(cur, scope, src_fqn, src_col, tgt_fqn, tgt_col, tgt_scope=None) -> None:
    """REFERENCES 엣지 삭제 — broken(파단) 관계를 그래프에서 제거해 SSOT 와 정합(feature-0016).

    MERGE 는 가산적이라, candidate/trusted 로 투영됐던 엣지가 이후 broken 으로 감쇠해도 그래프에
    stale 하게 남는다(backend 패널 MAJOR). sync_graph 가 broken 행마다 이 함수를 호출해 회수한다.
    노드는 남기고 엣지만 삭제(다른 관계가 그 컬럼을 참조할 수 있음). 멱등(없으면 no-op).
    tgt_scope(crossds-rel): 크로스-ds broken 엣지를 올바른 namespace 에서 제거(기본=scope)."""
    tscope = tgt_scope if tgt_scope is not None else scope
    s_ckey = _vkey(scope, f"{src_fqn}.{src_col}")
    t_ckey = _vkey(tscope, f"{tgt_fqn}.{tgt_col}")
    q = (f"MATCH (a:Column {{key: {_cq(s_ckey)}}})-[r:REFERENCES]->(b:Column {{key: {_cq(t_ckey)}}}) "
         f"DELETE r RETURN 1")
    _cypher(cur, q, 1)


def sync_routine(cur, scope, schema, name, routine_type="procedure", params="", refs=None) -> None:
    """Routine 노드 + HAS_ROUTINE(Schema→Routine) + ROUTINE_USES(Routine→Table) MERGE (ADR-016).

    key/fqn 은 `schema.name()` — 뒤의 `()` 가 동명 테이블 키(`schema.name`)와의 전역 key 충돌을
    막는 네임스페이스이자 사람이 읽는 함수 표기다. refs = [{fqn:'schema.table', kind:'read|write'}]
    (routine_objects.referenced_tables). 참조 Table 은 최소 MERGE(설명 미설정 — 큐레이션 비파괴)로
    앵커링해 고아 엣지를 막는다(_anchor_relationship_column 동형)."""
    fqn = f"{schema}.{name}()" if schema else f"{name}()"
    skey = _vkey(scope, schema or "(default)")
    rkey = _vkey(scope, fqn)
    _merge_vertex(cur, "Schema", skey,
                  {"name": schema or "(default)", "fqn": schema or "(default)", "scope_key": scope})
    _merge_vertex(cur, "Routine", rkey,
                  {"name": name, "fqn": fqn, "scope_key": scope, "schema_name": schema or "",
                   "routine_type": routine_type or "procedure", "params": (params or "")[:500],
                   "source": "routine_introspect"})
    _merge_edge(cur, "Schema", skey, "HAS_ROUTINE", "Routine", rkey)
    # §18.8 패널(MAJOR): 가산적 MERGE 만으로는 정의 변경으로 사라진 참조가 그래프에 영구 잔존
    # (REFERENCES 의 broken stale-edge 클래스 재도입). refs 가 이 routine 의 **전량**이므로
    # 기존 ROUTINE_USES 를 먼저 회수하고 현재 참조만 재-MERGE 한다(멱등·결정적).
    try:
        _cypher(cur, f"MATCH (r:Routine {{key: {_cq(rkey)}}})-[u:ROUTINE_USES]->() DELETE u RETURN 1", 1)
    except Exception:
        pass   # 라벨 부재(0034 미적용) 등 — MERGE 단계가 어차피 실패해 호출측 errors 로 집계
    for r in (refs or []):
        tfqn = str((r or {}).get("fqn") or "").strip()
        if not tfqn:
            continue
        parts = [p for p in tfqn.split(".") if p]
        table = parts[-1] if parts else ""
        if not table:
            continue
        tkey = _vkey(scope, tfqn)
        _merge_vertex(cur, "Table", tkey,
                      {"name": table, "fqn": tfqn, "scope_key": scope,
                       "schema_name": ".".join(parts[:-1]), "table_name": table})
        # §57: SSOT refs 의 cross 플래그(크로스-DB 참조, §56 RC2)를 AGE 엣지 속성으로 투영 —
        #   프론트 크로스 시각 구분(REFERENCES 의 cross_ds='1' 관례와 동일 키, ADR-019 정합).
        _merge_edge(cur, "Routine", rkey, "ROUTINE_USES", "Table", tkey,
                    {"relation_type": (r or {}).get("kind") or "read",
                     **({"cross_ds": "1"} if (r or {}).get("cross") else {})})


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
def _sync_row_guard(cur, owned, samples, label, fn, rep=None) -> bool:
    """sync_graph per-row 실행 가드 (§56 RC1 근본수정 — batched tx 오염 연쇄 차단).

    owned(batched 트랜잭션) 모드에서 각 행을 SAVEPOINT 로 격리한다. 종전에는 한 행의 실패가
    트랜잭션을 aborted 로 만들어 **이후 전 행이 InFailedSqlTransaction 으로 연쇄 실패**하고,
    그 배치의 커밋이 롤백으로 수렴해 **성공분까지 소실**됐다 (라이브 실측: routine 백필 직후
    full sync errors 18,698 — 단건 재현은 전행 성공 = 불량 행 0, 전부 연쇄). 실패 행은 첫
    5건을 samples 에 채집(관측성 — 어떤 행이 최초 오염원인지 프로덕션 로그로 식별).

    §18.8 패널(§56) 보강 2건:
      - **SAVEPOINT 확립 실패 = 트랜잭션 무결성 실패** — per-row 데이터 오류(errors, 워터마크
        비차단)로 오분류하지 않고 rep.step_failures 로 계상 + fn 미실행 후 False. tx 소생은
        다음 step 가드(_run_step 의 force-tick→rollback)가 담당(가드 내 rollback 은 호출측
        _pending 과 어긋나 배치 정합을 깨므로 하지 않는다).
      - **실패 행 ROLLBACK TO 후 RELEASE** — 실패 서브트랜잭션이 열린 채 누적되면 배치(≤500행)
        내 subtransaction >64 에서 PG suboverflow 성능 절벽(특히 replica). 해제로 상수 유지.
    반환: 성공 여부. autocommit(비-owned) 모드는 SAVEPOINT 불요(기존 동작)."""
    if owned:
        try:
            cur.execute("SAVEPOINT sg_row")
        except Exception as sp_exc:
            if isinstance(rep, dict):
                rep["step_failures"] = int(rep.get("step_failures", 0)) + 1
            if len(samples) < 5:
                samples.append(f"{label}:savepoint: {type(sp_exc).__name__} {str(sp_exc)[:160]}")
            return False
    try:
        fn()
        if owned:
            try:
                cur.execute("RELEASE SAVEPOINT sg_row")
            except Exception:
                pass
        return True
    except Exception as exc:
        if owned:
            try:
                cur.execute("ROLLBACK TO SAVEPOINT sg_row")
                cur.execute("RELEASE SAVEPOINT sg_row")
            except Exception:
                pass
        if len(samples) < 5:
            samples.append(f"{label}: {type(exc).__name__} {str(exc)[:160]}")
        return False


def sync_graph(conn=None, scope_key=None, since=None) -> dict:
    """관계형 SSOT 를 읽어 metadata_kb 그래프로 투영. 반환: 카운트 telemetry.

    멱등(MERGE) — 반복 호출 안전. 예외는 삼키고 부분 카운트 반환(비차단).
    scope_key=None 이면 모든 scope 동기화.

    insight-load-spread (부하 분산):
      - **batched commit**: 과거엔 _rw_conn(autocommit=True)로 노드/엣지마다 개별 커밋 → 8K 규모에서
        매 sync 5.7만 WAL fsync 폭주(30분 cron 스파이크)를 유발했다. _SYNC_MERGE_BATCH(기본 500)개마다
        1회 커밋으로 묶어 fsync 를 ~100 회로 줄인다(정합성 불변 — 여전히 전량 MERGE, 트랜잭션 경계만 묶음).
      - **since(증분)**: 지정 시 updated_at > since 인 변경분만 MERGE → 변경 없는 cycle 은 거의 no-op
        (MERGE 실행 CPU + AGE 처리 절감). 파단(broken) 관계 삭제는 status 변경이 updated_at 을 올려
        incremental·full 모두 delete_relationship 으로 반영된다. 단 **dropped 테이블/컬럼 노드 자체의
        prune** 은 예나 지금이나 sync_graph 범위 밖(가산적 재생성 투영 — pre-existing; full 도 노드 prune 안 함).
        워터마크 관리는 호출측(CLI)이 담당하고, synced_at(이번 sync 서버시각)을 반환해 다음 워터마크로 쓴다.
        owned=False(외부 conn 주입) 시엔 트랜잭션 경계를 호출측이 소유하므로 batching 을 적용하지 않는다.
    """
    rep = {"rag_tables": 0, "tables": 0, "columns": 0, "relationships": 0,
           "relationships_deleted": 0, "glossary": 0, "glossary_relations": 0, "routines": 0,
           "errors": 0, "step_failures": 0, "since": since, "synced_at": None, "commits": 0}
    c, owned = _rw_conn(conn)
    if c is None:
        return rep
    _pending = [0]
    _err_samples: list = []   # §56 RC1 관측성: per-row 실패 첫 5건(단계: 예외) — 종료 시 warning 1줄

    def _tick(force=False):
        # batched commit — owned(자체 생성) 연결일 때만 트랜잭션 경계를 관리한다.
        if not owned:
            return
        if force or _pending[0] >= _SYNC_MERGE_BATCH:
            try:
                c.commit()
                if _pending[0]:
                    rep["commits"] += 1
            except Exception as exc:
                # §18.8 패널(§56): 커밋 실패 = 배치(≤500행) 소실 — per-row errors 가 아닌
                # **step_failures(트랜잭션 무결성)** 로 계상해 워터마크 전진을 차단하고,
                # rollback 으로 tx 를 소생시켜 다음 배치를 살린다(카운터는 이미 가산된 소실
                # 배치만큼 과대일 수 있음 — bounded, 샘플 로그로 식별 가능).
                rep["step_failures"] += 1
                if len(_err_samples) < 5:
                    _err_samples.append(f"commit: {type(exc).__name__} {str(exc)[:160]}")
                try:
                    c.rollback()
                except Exception:
                    pass
            _pending[0] = 0

    def _scope_since_where():
        # scope_key + since(updated_at) 를 합친 WHERE 절과 args (updated_at 컬럼 보유 테이블 공용).
        conds, args = [], []
        if scope_key is not None:
            conds.append("scope_key = %s"); args.append(scope_key)
        if since:
            conds.append("updated_at > %s"); args.append(since)
        w = (" WHERE " + " AND ".join(conds)) if conds else ""
        return w, tuple(args)

    def _run_step(label, fn):
        """step 실행 가드(§18.8 패널 — §56): 종전엔 step-level 실패가 (a) rollback 없이 tx 를
        aborted 로 남겨 **후속 step 전부 연쇄 사망**(3b 만 복구 보유), (b) 최종 커밋이 aborted tx
        에서 조용히 ROLLBACK 으로 수렴해 직전 커밋 이후 **성공 행이 카운터만 남기고 소실**됐다.
        진입 전 선행 성공분 강제 커밋(소급 소실 차단) → 실행 → 실패 시 step_failures(워터마크
        차단 축) + rollback(오염 전파 차단) + pending 리셋 + 샘플. per-row 실패는 _sync_row_guard 소관."""
        _tick(force=True)
        try:
            fn()
        except Exception as exc:
            rep["step_failures"] += 1
            if len(_err_samples) < 5:
                _err_samples.append(f"step:{label}: {type(exc).__name__} {str(exc)[:160]}")
            if owned:
                try:
                    c.rollback()
                except Exception:
                    pass
            _pending[0] = 0

    try:
        cur = c.cursor()
        _set_age_path(cur)
        _ensure_graph_indexes(cur)   # 성능 인덱스 보장(이웃 조회 60x) — drop_graph 재생성 생존
        try:
            cur.execute("SELECT now()")   # 다음 워터마크(이번 sync 서버시각) — batching 트랜잭션 시작 전 고정
            rep["synced_at"] = str(cur.fetchone()[0])
        except Exception:
            pass
        if owned:
            c.autocommit = False   # batched 트랜잭션 시작 (인덱스 DDL·now() 커밋 이후)

        # 0) rag_objects (auto-discovered 스키마/테이블) → datasource_key 별 노드 베이스.
        #    각 데이터소스가 그래프를 갖게 하는 핵심(table_descriptions 는 1개 ds 만 커버).
        #    description=None → 큐레이션 설명을 덮어쓰지 않음(아래 1·2 단계가 layering). 먼저 실행.
        #    **MSSQL 'dbo' 보정**: rag_objects.schema_name 은 MSSQL 에서 리터럴 'dbo'(기본 스키마)라
        #    DB 차원이 소실되고 다중 DB 동명 테이블(예: 23개 DB 의 dbo.T_ErrorLog)이 한 노드로 충돌한다.
        #    DB명은 object_key(`<ds>:db.dbo.table`)에 있으므로 그걸 파싱해 DB명을 스키마(클러스터)로 사용.
        def _step_rag():
            rag_conds = ["object_type = 'table'", "datasource_key <> ''", "table_name <> ''"]
            rag_args = []
            if scope_key is not None:
                rag_conds.append("datasource_key = %s"); rag_args.append(scope_key)
            if since:
                rag_conds.append("updated_at > %s"); rag_args.append(since)
            # Phase C: 의미 클러스터(semantic_cluster_id/label)도 투영 — Table 정점에 실어 scope_roots/schema_tables 가 RETURN.
            #   컬럼 부재(마이그 0035 미적용 구 DB)면 SELECT 실패 → _run_step 이 step_failures+rollback 으로 격리.
            cur.execute("SELECT datasource_key, schema_name, table_name, object_key, "
                        "semantic_cluster_id, semantic_cluster_label "
                        "FROM rag_objects WHERE " + " AND ".join(rag_conds), tuple(rag_args))
            for ds, sch, tbl, okey, ccid, clab in cur.fetchall():
                def _row(ds=ds, sch=sch, tbl=tbl, okey=okey, ccid=ccid, clab=clab):
                    eff_sch, eff_tbl = _rag_effective(ds, okey, sch, tbl)
                    sync_table(cur, ds, eff_sch, eff_tbl, description=None, source="insight",
                               cluster_id=(int(ccid) if ccid is not None else None),
                               cluster_label=(clab if clab else None))
                if _sync_row_guard(cur, owned, _err_samples, "rag_table", _row, rep):
                    rep["rag_tables"] += 1; _pending[0] += 1; _tick()
                else:
                    rep["errors"] += 1
        _run_step("rag_objects", _step_rag)

        # 1) table_descriptions — §18.8 패널(§56): 종전 무가드(step 실패가 바깥 except 로 직행해
        # sync 전체 무산 + step_failures 미집계) → _run_step 격리.
        def _step_tables():
            _w, _a = _scope_since_where()
            cur.execute("SELECT scope_key, schema_name, table_name, description, source "
                        "FROM table_descriptions" + _w, _a)
            for sc, sch, tbl, desc, src in cur.fetchall():
                def _row(sc=sc, sch=sch, tbl=tbl, desc=desc, src=src):
                    sync_table(cur, sc, sch or "", tbl, desc or "", src or "manual")
                if _sync_row_guard(cur, owned, _err_samples, "table_desc", _row, rep):
                    rep["tables"] += 1; _pending[0] += 1; _tick()
                else:
                    rep["errors"] += 1
        _run_step("table_descriptions", _step_tables)
        # 2) column_descriptions (feature-0016 graphux5: ordinal 투영 — 그래프 컬럼 세로 정렬용)
        #    ordinal 컬럼 부재(마이그 미적용 구 DB) 등 SELECT 실패는 graceful — 다른 단계(관계/용어) 계속.
        def _step_columns():
            _w, _a = _scope_since_where()
            cur.execute("SELECT scope_key, schema_name, table_name, column_name, description, source, ordinal "
                        "FROM column_descriptions" + _w, _a)
            for sc, sch, tbl, col, desc, src, ordn in cur.fetchall():
                def _row(sc=sc, sch=sch, tbl=tbl, col=col, desc=desc, src=src, ordn=ordn):
                    sync_column(cur, sc, sch or "", tbl, col, desc or "", src or "manual", ordinal=ordn)
                if _sync_row_guard(cur, owned, _err_samples, "column_desc", _row, rep):
                    rep["columns"] += 1; _pending[0] += 1; _tick()
                else:
                    rep["errors"] += 1
        _run_step("column_descriptions", _step_columns)
        # 3) table_relationships — broken(파단)은 그래프에서 **삭제**(가산적 MERGE 라 stale 방지,
        #    학습된 '비관계'), 그 외는 weight/status 와 함께 투영. (전량 스캔 후 status 로 분기.)
        # crossds-rel(ADR-019): source/target_datasource_key 도 읽어 크로스-ds 엣지는 각 끝점을 자기 datasource
        #   scope 로 앵커(tgt_scope). 컬럼 부재(마이그 0036 미적용)면 SELECT 실패 → except graceful. intra-ds 는
        #   sds==tds → tgt_scope=sc(기존 동작 완전 보존, 스코프!=ds 인 794 레거시 행도 불변).
        def _step_relationships():
            _w, _a = _scope_since_where()
            try:
                cur.execute("SELECT scope_key, source_table_fqn, source_column, target_table_fqn, "
                            "target_column, cardinality, source, confidence, weight, status, "
                            "source_datasource_key, target_datasource_key "
                            "FROM table_relationships" + _w, _a)
                rel_rows = cur.fetchall()
            except Exception:
                # 0036 미적용 구 DB — ds 컬럼 없이 재조회(하위호환, 전부 intra-ds 취급).
                # §18.8 패널(§56, 잠복결함 동반수정): owned 모드에선 첫 SELECT 실패가 tx 를 abort
                # 시켜 재조회도 InFailedSqlTransaction 으로 죽던 것 — rollback 으로 소생 후 재조회.
                if owned:
                    try:
                        c.rollback()
                    except Exception:
                        pass
                    _pending[0] = 0
                cur.execute("SELECT scope_key, source_table_fqn, source_column, target_table_fqn, "
                            "target_column, cardinality, source, confidence, weight, status "
                            "FROM table_relationships" + _w, _a)
                rel_rows = [tuple(r) + ("", "") for r in cur.fetchall()]
            for sc, sfqn, scol, tfqn, tcol, card, src, conf, wgt, st, sds, tds in rel_rows:
                _is_del = (st == "broken")

                def _row(sc=sc, sfqn=sfqn, scol=scol, tfqn=tfqn, tcol=tcol, card=card,
                         src=src, conf=conf, wgt=wgt, st=st, sds=sds, tds=tds):
                    tgt_scope = tds if (sds and tds and sds != tds) else sc
                    if st == "broken":
                        delete_relationship(cur, sc, sfqn, scol, tfqn, tcol, tgt_scope=tgt_scope)
                    else:
                        sync_relationship(cur, sc, sfqn, scol, tfqn, tcol, card or "",
                                          src or "fk_introspect", conf if conf is not None else 1.0,
                                          weight=wgt, status=st or "", tgt_scope=tgt_scope)
                if _sync_row_guard(cur, owned, _err_samples, "relationship", _row, rep):
                    rep["relationships_deleted" if _is_del else "relationships"] += 1
                    _pending[0] += 1; _tick()
                else:
                    rep["errors"] += 1
        _run_step("table_relationships", _step_relationships)
        # 3b) routine_objects (함수·프로시저, graph-funcproc ADR-016) — Routine 노드 +
        #     HAS_ROUTINE + 참조 테이블 ROUTINE_USES. 테이블 부재(구 DB·0034 미적용)는 _run_step 이 격리.
        def _step_routines():
            _w, _a = _scope_since_where()
            cur.execute("SELECT scope_key, schema_name, routine_name, routine_type, params, "
                        "referenced_tables FROM routine_objects" + _w, _a)
            for sc, sch, name, rtype, params, refs in cur.fetchall():
                def _row(sc=sc, sch=sch, name=name, rtype=rtype, params=params, refs=refs):
                    if isinstance(refs, str):
                        refs = json.loads(refs or "[]")
                    sync_routine(cur, sc, sch or "", name, rtype or "procedure",
                                 params or "", refs if isinstance(refs, list) else [])
                if _sync_row_guard(cur, owned, _err_samples, "routine", _row, rep):
                    rep["routines"] += 1; _pending[0] += 1; _tick()
                else:
                    rep["errors"] += 1
        _run_step("routine_objects", _step_routines)

        # 4) kb_glossary
        def _step_glossary():
            _w, _a = _scope_since_where()
            cur.execute("SELECT scope_key, term, definition, source "
                        "FROM kb_glossary" + _w, _a)
            for sc, term, defn, src in cur.fetchall():
                def _row(sc=sc, term=term, defn=defn, src=src):
                    sync_glossary_term(cur, sc, term, defn or "", src or "manual")
                if _sync_row_guard(cur, owned, _err_samples, "glossary", _row, rep):
                    rep["glossary"] += 1; _pending[0] += 1; _tick()
                else:
                    rep["errors"] += 1
        _run_step("kb_glossary", _step_glossary)

        # 5) glossary_relations (term id → term 매핑) — updated_at 부재(created_at only) + 소규모라
        #    증분 대상에서 제외하고 항상 full 투영(작아서 batching 만으로 충분).
        def _step_glossary_rel():
            cur.execute(
                "SELECT g1.scope_key, g1.term, g2.term, gr.relation_type "
                "FROM glossary_relations gr "
                "JOIN kb_glossary g1 ON g1.id = gr.from_id "
                "JOIN kb_glossary g2 ON g2.id = gr.to_id")
            for sc, ft, tt, rt in cur.fetchall():
                def _row(sc=sc, ft=ft, tt=tt, rt=rt):
                    sync_glossary_relation(cur, sc, ft, tt, rt or "similar")
                if _sync_row_guard(cur, owned, _err_samples, "glossary_rel", _row, rep):
                    rep["glossary_relations"] += 1; _pending[0] += 1; _tick()
                else:
                    rep["errors"] += 1
        _run_step("glossary_relations", _step_glossary_rel)
        _tick(force=True)   # 잔여분 최종 커밋
        if rep["errors"] or rep["step_failures"]:
            # §56 RC1 관측성: 침묵 누적되던 per-row 오류의 정체를 프로덕션 로그로 노출(첫 5건 샘플).
            _log.warning("sync_graph partial: errors=%s step_failures=%s samples=%s",
                         rep["errors"], rep["step_failures"], _err_samples)
        cur.close()
    except Exception as exc:
        _log.warning("sync_graph_failed err=%r", exc)
        rep["errors"] += 1
        # §18.8 패널(§56): 치명 실패(스캔 전면 중단)는 **step_failures 로도 계상** — 워터마크 게이트가
        # step_failures 만 보므로, 여기 미집계면 죽은 sync 뒤에도 워터마크가 전진해 그 창의 변경분이
        # 증분 경로에서 영구 누락된다(다음 --full 까지). errors 는 가시성용으로 병행 유지.
        rep["step_failures"] += 1
        if owned:
            try:
                c.rollback()
            except Exception:
                pass
    finally:
        if owned:
            try:
                c.autocommit = True   # autocommit 복원(연결 close 안전)
            except Exception:
                pass
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return rep


# ── 증분 sync 워터마크 (insight-load-spread) ──────────────────────────────
# 직전 성공 sync 의 서버시각을 agent_runtime.kv 에 저장해, 다음 --incremental 호출이 그 이후 변경분만
# MERGE 하게 한다(cron 30분마다 전량 5.7만 MERGE 를 도는 CPU 낭비 차단). scope 별 독립 워터마크.
# 실패는 graceful(None → full sync 로 안전 폴백). 삭제/파단 반영은 주기 full sync(--full)가 담당.
_SYNC_WM_CONV = "__metadata_graph_sync__"


def get_sync_watermark(scope_key=None, conn=None):
    """직전 성공 sync 서버시각(ISO text) 조회. 없거나 실패면 None(→ full). agent_runtime.kv PK(conv,key)."""
    key = "watermark:" + (scope_key or "__all__")
    c, owned = _ro_conn(conn)
    if c is None:
        return None
    try:
        cur = c.cursor()
        try:
            cur.execute("SELECT value FROM agent_runtime.kv WHERE conversation_id = %s AND key = %s",
                        (_SYNC_WM_CONV, key))
            row = cur.fetchone()
            return row[0] if row and row[0] else None
        finally:
            cur.close()
    except Exception:
        return None
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass


def set_sync_watermark(ts, scope_key=None, conn=None) -> None:
    """sync 워터마크 저장(다음 --incremental 의 since). 실패 graceful(다음 full). ts 는 sync_graph.synced_at."""
    if not ts:
        return
    key = "watermark:" + (scope_key or "__all__")
    c, owned = _rw_conn(conn)
    if c is None:
        return
    try:
        cur = c.cursor()
        try:
            cur.execute(
                "INSERT INTO agent_runtime.kv (conversation_id, key, value, updated_at) "
                "VALUES (%s, %s, %s, now()) "
                "ON CONFLICT (conversation_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
                (_SYNC_WM_CONV, key, str(ts)))
        finally:
            cur.close()
    except Exception:
        pass
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass


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
    d = {"label": _unwrap(row[0]), "key": _unwrap(row[1]), "name": _unwrap(row[2]),
         "fqn": _unwrap(row[3]), "description": _unwrap(row[4]), "source": _unwrap(row[5]),
         "ordinal": _as_int(_unwrap(row[6]))}
    if len(row) > 7:   # graph-funcproc: 함수·프로시저 구분(FE ƒ/⚙ 표기)
        d["routine_type"] = _unwrap(row[7])
    return d


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
            f"RETURN label(n), n.key, n.name, n.fqn, n.description, n.source, n.ordinal, "
            f"n.routine_type LIMIT {limit}", 8)
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
            f"RETURN s.key, s.name, s.fqn, t.key, t.name, t.fqn, t.description, t.source, "
            f"t.semantic_cluster_id, t.semantic_cluster_label "
            f"LIMIT {limit}", 10)
        nodes = {}
        for r in rows:
            skey = _unwrap(r[0]); tkey = _unwrap(r[3])
            if skey and skey not in nodes:
                nodes[skey] = {"label": "Schema", "key": skey, "name": _unwrap(r[1]),
                               "fqn": _unwrap(r[2]), "description": None, "source": None}
            if tkey and tkey not in nodes:
                nodes[tkey] = {"label": "Table", "key": tkey, "name": _unwrap(r[4]),
                               "fqn": _unwrap(r[5]), "description": _unwrap(r[6]), "source": _unwrap(r[7]),
                               "cluster_id": _unwrap(r[8]), "cluster_label": _unwrap(r[9])}
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


def scope_schemas(scope: str, limit: int = 500, conn=None) -> dict:
    """데이터소스(scope) 진입 그래프 **경량판** — Schema 노드 + per-schema 테이블 수(graph-initview).

    초기 진입 뷰가 테이블 낱개 대신 스키마 카드만 그리도록 한다(8K 규모에서 전체-fit 줌아웃 방지).
    각 Schema 노드에 `table_count`(cap 무관 실 카운트)를 붙여 UI 배지·lazy 로드 판단에 쓴다.
    스키마 수 ≪ 테이블 수라 통상 전수 표시되며, cap(500) 초과는 `truncated: true` 로 명시한다.
    """
    result = {"nodes": [], "edges": [], "truncated": False}
    if not scope:
        return result
    limit = max(1, min(int(limit or 500), 500))
    c, owned = _ro_conn(conn)
    if c is None:
        return result
    try:
        cur = c.cursor()
        _set_age_path(cur)
        sc = _cq(scope)
        srows = _cypher(cur,
            f"MATCH (s:Schema) WHERE s.scope_key = {sc} "
            f"RETURN s.key, s.name, s.fqn LIMIT {limit + 1}", 3)
        if len(srows) > limit:
            result["truncated"] = True
            srows = srows[:limit]
        nodes = {}
        for r in srows:
            skey = _unwrap(r[0])
            if skey and skey not in nodes:
                nodes[skey] = {"label": "Schema", "key": skey, "name": _unwrap(r[1]),
                               "fqn": _unwrap(r[2]), "description": None, "source": None,
                               "table_count": None}
        if nodes:
            try:
                crows = _cypher(cur,
                    f"MATCH (s:Schema)-[:HAS_TABLE]->(t:Table) WHERE s.scope_key = {sc} "
                    f"RETURN s.key, count(t)", 2)
                # 집계 성공 시에만 0 기본값(테이블 없는 스키마=0) — 실패 시 None 유지(아래 except).
                for v in nodes.values():
                    v["table_count"] = 0
                for r in crows:
                    skey = _unwrap(r[0])
                    cnt = _as_int(_unwrap(r[1]))
                    if skey in nodes and cnt is not None:
                        nodes[skey]["table_count"] = cnt
            except Exception as exc:
                # 집계 실패는 **배지 없는 카드**(table_count=None)로 강등(스키마 목록 자체는 유지) —
                # 0 으로 두면 UI 가 '테이블 0' 배지를 그려 빈 스키마와 구분 불가(2차 검증 V-H).
                for v in nodes.values():
                    v["table_count"] = None
                _log.debug("scope_schemas_count_failed err=%r", exc)
        # §57(사용자 요구 ①): 접힌 카드 초기 뷰에도 연결 구조가 보이도록 **스키마-쌍 집계 엣지**
        #   (SCHEMA_REF — HAS_* 가 아니라 프론트 ingest 통과)를 동봉한다. 구현 노트: Schema↔Schema
        #   멀티-hop cypher 집계는 AGE 플래너가 최악 82s(라이브 실측)라 기각 — **1-hop 전량 스캔
        #   (실측 0.2s) 후 키 스키마-세그먼트 Python 집계**로 대체(키 규약 `scope:schema.rest`,
        #   _vkey/_anchor 가 보장). REFERENCES(broken 제외)+ROUTINE_USES 무향 합산, count DESC
        #   cap 400(카드 n² 폭주 차단). 실패는 엣지 없는 기존 응답으로 강등(카드 목록 유지).
        if nodes:
            try:
                pfx = f"{scope}:"

                def _seg(key):
                    # 'scope:schema.rest…' → 스키마 세그먼트. 타 scope/세그먼트 없음(스키마-레벨 키)은 None.
                    k = str(key or "")
                    if not k.startswith(pfx):
                        return None
                    rest = k[len(pfx):]
                    dot = rest.find(".")
                    return rest[:dot] if dot > 0 else None

                pair = {}   # (a_key,b_key) 정렬쌍 -> {"ref": n, "use": n}

                def _acc(rows, kind):
                    for r in rows:
                        sa = _seg(_unwrap(r[0])); sb = _seg(_unwrap(r[1]))
                        if not sa or not sb or sa == sb:
                            continue
                        a, b = f"{scope}:{sa}", f"{scope}:{sb}"
                        k = (a, b) if a <= b else (b, a)
                        d = pair.setdefault(k, {"ref": 0, "use": 0})
                        d[kind] += 1
                try:
                    _acc(_cypher(cur,
                        f"MATCH (c1:Column)-[r:REFERENCES]->(c2:Column) "
                        f"WHERE c1.scope_key = {sc} AND (r.status IS NULL OR r.status <> 'broken') "
                        f"RETURN c1.key, c2.key", 2), "ref")
                except Exception as exc:
                    _log.debug("scope_schemas_ref_agg_failed err=%r", exc)
                try:
                    _acc(_cypher(cur,
                        f"MATCH (r0:Routine)-[u:ROUTINE_USES]->(t:Table) "
                        f"WHERE r0.scope_key = {sc} "
                        f"RETURN r0.key, t.key", 2), "use")
                except Exception as exc:
                    _log.debug("scope_schemas_use_agg_failed err=%r", exc)
                ranked = sorted(pair.items(), key=lambda kv: -(kv[1]["ref"] + kv[1]["use"]))
                cap = 400
                if len(ranked) > cap:
                    result["truncated"] = True
                    ranked = ranked[:cap]
                for (a, b), d in ranked:
                    if a in nodes and b in nodes:
                        result["edges"].append({
                            "source": a, "target": b, "type": "SCHEMA_REF",
                            "count": d["ref"] + d["use"],
                            "ref_count": d["ref"], "use_count": d["use"]})
            except Exception as exc:
                _log.debug("scope_schemas_pair_agg_failed err=%r", exc)
        result["nodes"] = list(nodes.values())
        cur.close()
    except Exception as exc:
        _log.debug("scope_schemas_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return result


def schema_tables(scope: str, schema_key: str, limit: int = 300, conn=None) -> dict:
    """지정 스키마의 Table 서브그래프(per-schema lazy 로드, graph-initview).

    스키마 카드 클릭 시 그 스키마의 테이블만 로드해 초기 뷰 노드 폭증을 막는다.
    cap(_NEIGHBOR_NODE_CAP) 초과 스키마는 `truncated: true` 로 부분 표시를 명시한다.
    """
    result = {"nodes": [], "edges": [], "truncated": False}
    if not scope or not schema_key:
        return result
    limit = max(1, min(int(limit or 300), _NEIGHBOR_NODE_CAP))
    c, owned = _ro_conn(conn)
    if c is None:
        return result
    try:
        cur = c.cursor()
        _set_age_path(cur)
        sc = _cq(scope)
        sk = _cq(schema_key)
        rows = _cypher(cur,
            f"MATCH (s:Schema)-[:HAS_TABLE]->(t:Table) "
            f"WHERE s.scope_key = {sc} AND s.key = {sk} "
            f"RETURN s.key, s.name, s.fqn, t.key, t.name, t.fqn, t.description, t.source, "
            f"t.semantic_cluster_id, t.semantic_cluster_label "
            f"LIMIT {limit + 1}", 10)
        if len(rows) > limit:
            result["truncated"] = True
            rows = rows[:limit]
        nodes = {}
        for r in rows:
            skey = _unwrap(r[0]); tkey = _unwrap(r[3])
            if skey and skey not in nodes:
                nodes[skey] = {"label": "Schema", "key": skey, "name": _unwrap(r[1]),
                               "fqn": _unwrap(r[2]), "description": None, "source": None}
            if tkey and tkey not in nodes:
                nodes[tkey] = {"label": "Table", "key": tkey, "name": _unwrap(r[4]),
                               "fqn": _unwrap(r[5]), "description": _unwrap(r[6]), "source": _unwrap(r[7]),
                               "cluster_id": _unwrap(r[8]), "cluster_label": _unwrap(r[9])}
            if skey and tkey:
                result["edges"].append({"source": skey, "target": tkey, "type": "HAS_TABLE",
                                        "cardinality": None, "edge_source": None})
        # graph-reltrace ①: 스키마 내 컬럼에서 나가는 REFERENCES 엣지도 함께 반환한다.
        #   기존에는 schema_tables 가 HAS_TABLE 만 줘서, 스키마를 펼쳐도(테이블 접힘) 관계 엣지가
        #   모델에 없어 "테이블 더블클릭 전까지 관계 미표시" 였다. 여기서 Column→Column REFERENCES 를
        #   실어 주면 프론트가 컬럼 키에서 소속 테이블을 도출해 **접힌 테이블 간 관계**를 그린다.
        #   FK(status NULL) 포함, broken 만 제외(sync 삭제 + 감쇠 창 방어). 캡으로 폭주 차단.
        try:
            edge_cap = min(limit * 4, _NEIGHBOR_NODE_CAP * 4)
            erows = _cypher(cur,
                f"MATCH (s:Schema)-[:HAS_TABLE]->(:Table)-[:HAS_COLUMN]->(c:Column)"
                f"-[r:REFERENCES]->(c2:Column) "
                f"WHERE s.scope_key = {sc} AND s.key = {sk} "
                f"AND (r.status IS NULL OR r.status <> 'broken') "
                f"RETURN c.key, c2.key, r.status, r.weight, r.source, r.cardinality "
                f"LIMIT {edge_cap}", 6)
            eseen = set()
            for er in erows:
                cs = _unwrap(er[0]); ct = _unwrap(er[1])
                if not cs or not ct:
                    continue
                ekey = (cs, ct)
                if ekey in eseen:
                    continue
                eseen.add(ekey)
                result["edges"].append({
                    "source": cs, "target": ct, "type": "REFERENCES",
                    "cardinality": _unwrap(er[5]), "edge_source": _unwrap(er[4]),
                    "weight": _unwrap(er[3]), "status": _unwrap(er[2]),
                })
        except Exception as exc:
            _log.debug("schema_tables_refs_failed err=%r", exc)   # 관계 부재는 비차단(테이블은 이미 반환)
        # graph-funcproc(ADR-016): 스키마의 함수·프로시저(Routine) 노드 + 참조 테이블 엣지도 함께 반환 —
        #   클러스터 펼침 시 테이블과 나란히 ƒ/⚙ 칩으로 렌더된다. 라벨 부재(0034 미적용)는 비차단.
        try:
            rrows = _cypher(cur,
                f"MATCH (s:Schema)-[:HAS_ROUTINE]->(r:Routine) "
                f"WHERE s.scope_key = {sc} AND s.key = {sk} "
                f"RETURN r.key, r.name, r.fqn, r.description, r.routine_type, r.params "
                f"LIMIT {limit}", 6)
            skey0 = None
            for r in rrows:
                rkey = _unwrap(r[0])
                if not rkey:
                    continue
                if rkey not in nodes:
                    nodes[rkey] = {"label": "Routine", "key": rkey, "name": _unwrap(r[1]),
                                   "fqn": _unwrap(r[2]), "description": _unwrap(r[3]),
                                   "source": "routine_introspect",
                                   "routine_type": _unwrap(r[4]), "params": _unwrap(r[5])}
                if skey0 is None:
                    skey0 = schema_key
                result["edges"].append({"source": skey0, "target": rkey, "type": "HAS_ROUTINE",
                                        "cardinality": None, "edge_source": None})
            if rrows:
                urows = _cypher(cur,
                    f"MATCH (s:Schema)-[:HAS_ROUTINE]->(r:Routine)-[u:ROUTINE_USES]->(t:Table) "
                    f"WHERE s.scope_key = {sc} AND s.key = {sk} "
                    f"RETURN r.key, t.key, u.relation_type, u.cross_ds LIMIT {limit * 4}", 4)
                useen = set()
                for ur in urows:
                    rk = _unwrap(ur[0]); tk = _unwrap(ur[1])
                    if not rk or not tk or (rk, tk) in useen:
                        continue
                    useen.add((rk, tk))
                    # §57: cross_ds 를 클러스터 펼침 경로에도 노출 — 크로스 루틴 참조는 same-scope 라
                    #   neighborhood 가 아닌 이 경로로 흐른다(미노출 시 펼침 경로에서 플래그 소실).
                    result["edges"].append({"source": rk, "target": tk, "type": "ROUTINE_USES",
                                            "cardinality": None, "edge_source": None,
                                            "relation_type": _unwrap(ur[2]) or "read",
                                            "cross_ds": _unwrap(ur[3])})
        except Exception as exc:
            _log.debug("schema_tables_routines_failed err=%r", exc)
        result["nodes"] = list(nodes.values())
        cur.close()
    except Exception as exc:
        _log.debug("schema_tables_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return result


def schema_table_keys(scope: str, schema_key: str, limit: int = 2000, conn=None) -> list:
    """스키마 소속 Table 의 {key,name,fqn} 경량 열거 — DB(스키마) 단위 능동 분석 시드용(§53).

    schema_tables() 와 달리 엣지/설명 없이 키만 뽑아 cap 을 크게 잡는다(전 테이블 집계·시드 상한은
    caller 의 비용 가드가 결정). 실패 시 [] (비차단)."""
    out = []
    if not scope or not schema_key:
        return out
    try:
        limit = max(1, min(int(limit or 2000), 5000))
    except (TypeError, ValueError):
        limit = 2000
    c, owned = _ro_conn(conn)
    if c is None:
        return out
    try:
        cur = c.cursor()
        _set_age_path(cur)
        rows = _cypher(cur,
            f"MATCH (s:Schema)-[:HAS_TABLE]->(t:Table) "
            f"WHERE s.scope_key = {_cq(scope)} AND s.key = {_cq(schema_key)} "
            f"RETURN t.key, t.name, t.fqn LIMIT {limit}", 3)
        for r in rows:
            k = _unwrap(r[0])
            if k:
                out.append({"key": k, "name": _unwrap(r[1]) or k, "fqn": _unwrap(r[2]) or ""})
        cur.close()
    except Exception as exc:
        _log.debug("schema_table_keys_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return out


def schema_routine_keys(scope: str, schema_key: str, limit: int = 2000, conn=None) -> list:
    """스키마 소속 Routine(함수·프로시저)의 {key,name,fqn} 경량 열거 — DB(스키마) 단위 능동 분석
    시드용(§54). schema_table_keys 의 Routine 판. 실패/HAS_ROUTINE 라벨 부재(0034 미적용) 시
    [] 로 저하(비차단 — 스키마 분석이 테이블-only 로 자연 저하)."""
    out = []
    if not scope or not schema_key:
        return out
    try:
        limit = max(1, min(int(limit or 2000), 5000))
    except (TypeError, ValueError):
        limit = 2000
    c, owned = _ro_conn(conn)
    if c is None:
        return out
    try:
        cur = c.cursor()
        _set_age_path(cur)
        rows = _cypher(cur,
            f"MATCH (s:Schema)-[:HAS_ROUTINE]->(r:Routine) "
            f"WHERE s.scope_key = {_cq(scope)} AND s.key = {_cq(schema_key)} "
            f"RETURN r.key, r.name, r.fqn LIMIT {limit}", 3)
        for r in rows:
            k = _unwrap(r[0])
            if k:
                out.append({"key": k, "name": _unwrap(r[1]) or k, "fqn": _unwrap(r[2]) or ""})
        cur.close()
    except Exception as exc:
        _log.debug("schema_routine_keys_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return out


def _node_from_props(label: str, props: dict) -> dict:
    """라벨 테이블 properties(dict) → 노드 dict. _node_dict 와 동일 shape."""
    d = {"label": label, "key": props.get("key"), "name": props.get("name"),
         "fqn": props.get("fqn"), "description": props.get("description"),
         "source": props.get("source"), "ordinal": _as_int(props.get("ordinal"))}
    if label == "Routine":   # graph-funcproc: 함수/프로시저 구분 + 파라미터(상세 패널 표시)
        d["routine_type"] = props.get("routine_type")
        d["params"] = props.get("params")
    return d


def _gid_array(gids) -> str:
    """graphid 정수 목록 → `ARRAY['<int>'::ag_catalog.graphid, ...]` SQL 리터럴.
    gids 는 전부 DB 에서 온 정수라 int() 검증만으로 injection-safe(문자열 보간 없음)."""
    return "ARRAY[" + ", ".join(f"'{int(g)}'::ag_catalog.graphid" for g in gids) + "]"


def _existing_labels(cur, labels) -> list:
    """화이트리스트 라벨 중 **라벨 테이블이 실존하는 것만**(to_regclass) — 정렬 순서 보존.

    §18.8 패널(MAJOR): neighborhood 의 UNION ALL raw SQL 은 나열된 전 라벨 테이블을 하드 참조한다 —
    신규 라벨(예: Routine, alembic 0034) 미적용 DB 에서 UndefinedTable 로 **전체 쿼리가 실패**해
    모든 이웃 조회가 빈 결과가 되는 배포 skew 창(stale 이미지 사례 실재)을 여기서 차단한다.
    labels 는 상수 화이트리스트(_VLABELS/_ELABELS)라 보간 injection-safe."""
    names = sorted(labels)
    try:
        checks = ", ".join(f"to_regclass('metadata_kb.\"{l}\"')" for l in names)
        cur.execute(f"SELECT {checks}")
        row = cur.fetchone() or ()
        out = [l for l, reg in zip(names, row) if reg is not None]
        return out if out else names   # 전부 미검출(권한 등 이상)이면 종전 동작 보존
    except Exception:
        return names


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
        # 라벨 테이블 실존 필터(§18.8 MAJOR — 0034 미적용 skew 창에서 전체 이웃 조회 붕괴 방지)
        vlabels = _existing_labels(cur, _VLABELS)   # 결정적 순서(내부 sorted)
        elabels = _existing_labels(cur, _ELABELS)
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
                # relation_type: RELATED_TERM(유사어)·ROUTINE_USES(read/write, graph-funcproc) 공용.
                edge_hits.append((sg, eg, et, ep.get("cardinality"), ep.get("source"),
                                  ep.get("weight"), ep.get("status"), ep.get("relation_type"),
                                  ep.get("cross_ds")))   # crossds-rel: 교차DB 엣지 표식
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
            for sg, eg, et, card, esrc, ewgt, estatus, erel, exds in edge_hits:
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
                                        "weight": ewgt, "status": estatus,
                                        "relation_type": erel,
                                        "cross_ds": exds})   # crossds-rel: 프론트 교차DB 엣지 스타일/배지
            # schema_tables REFERENCES emit 도 cross_ds 를 실어야 하나, 그 경로는 단일 스키마(intra-ds)라 cross_ds 부재(생략 안전).
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
