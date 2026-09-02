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

import hashlib as _hashlib   # feature-0030 (cyvol): routine refs 서명
import json
import logging
import math
import os
import time as _time  # feature-0026 (M4): sync duration 계측

_log = logging.getLogger("metadata_graph")

GRAPH = "metadata_kb"

# alembic 0025(+0034 Routine, +0054 DbObject) 사전선언 라벨 화이트리스트 (런타임 동적 라벨 생성 금지)
_VLABELS = {"Product", "Datasource", "Schema", "Table", "Column", "GlossaryTerm", "Routine",
            "DbObject"}
_ELABELS = {"USES", "HAS_SCHEMA", "HAS_TABLE", "HAS_COLUMN", "REFERENCES", "RELATED_TERM", "DESCRIBES",
            "HAS_ROUTINE", "ROUTINE_USES",
            # feature-0040: 역할 기반 DB 객체(뷰·트리거·예약작업·별칭·시퀀스)
            "HAS_OBJECT", "OBJECT_USES", "OBJECT_ON"}
# 노드/엣지 속성 화이트리스트 (Cypher SET 대상 — 임의 키 주입 차단)
#  weight/status: feature-0016 강화 상태 투영(REFERENCES 엣지) — UI 가 신뢰/추정/파단을 구분.
#  routine_type/params: 함수·프로시저 노드(graph-funcproc, ADR-016).
#  semantic_cluster_id/label: feature-0016 Phase C(ADR-013 후속) 의미 클러스터 투영 — 프론트 sim-group 서버 신호.
_PROP_KEYS = {"key", "name", "fqn", "scope_key", "description", "source",
              "confidence", "cardinality", "datasource_key", "schema_name",
              "table_name", "column_name", "relation_type", "term",
              "weight", "status", "ordinal", "routine_type", "params",
              "semantic_cluster_id", "semantic_cluster_label", "cross_ds",
              # routine-column-edges(2026-07-28): ROUTINE_USES 가 참조하는 **컬럼** 목록(JSON 문자열
              # `[{"n": 컬럼, "k": "read"|"write"}]`). 프론트가 테이블 펼침 시 이 목록으로 사용선을
              # 컬럼별 분해한다. 값이 없거나 매칭 실패면 기존 테이블-레벨 연결 유지(폴백).
              "ref_columns",
              # feature-0040 db-object-explorer: 역할 기반 DB 객체 노드 속성.
              #   object_role  — view|trigger|schedule|alias|generator (그래프 kind 필터 축)
              #   object_type  — 방언 구체 타입(VIEW/DML_TRIGGER/EVENT/AGENT_JOB/SYNONYM/SEQUENCE)
              #   owner_object — 트리거가 걸린 테이블 · 별칭의 대상 (OBJECT_ON 엣지의 근거)
              #   object_attrs — 역할별 속성 JSON 문자열(시점/이벤트/주기/상태 …). 상세 패널이 그대로
              #                  표시하고 node_analysis payload 가 그대로 싣는다.
              "object_role", "object_type", "owner_object", "object_attrs"}
# 숫자(float) 리터럴로 SET 하는 속성(문자열 인용 금지)
_NUMERIC_PROP_KEYS = {"confidence", "weight"}
# 정수 리터럴로 SET 하는 속성. feature-0016 graphux5: 컬럼 실제 순서(ordinal). Phase C: 의미 클러스터 id.
_INT_PROP_KEYS = {"ordinal", "semantic_cluster_id"}
# None 이 "미설정(skip)"이 아니라 "명시적 clear(= null)"를 의미하는 속성. Phase C: rag_objects 가 클러스터의
# SSOT 라, 테이블이 클러스터에서 이탈(→NULL)하면 그래프 정점의 stale cluster_id 를 반드시 null 로 지워야
# phantom be: 그룹(리뷰 MAJOR-2)이 안 생긴다. sync_table 은 _UNSET 센티넬로 "미전달(보존)"과 "None(clear)"을 구분.
_NULLABLE_PROP_KEYS = {"semantic_cluster_id", "semantic_cluster_label"}
_UNSET = object()   # sync_table cluster 인자 "미전달" 센티넬(≠ 명시 None=clear)

# graph-cap-audit(사용자 결정 2026-07-29): **개수를 줄여 출력하는 것은 최적화가 아니라 데이터 누락
#   (오류)** 이다. 화면 성능은 이미 렌더 계층이 담당한다 — 뷰포트 컬링(§65)·노드 LOD(§67)·컬럼
#   LOD(§61)·레이아웃 위상서명 메모이즈(§73)·라벨 BitmapText(§80)·scene diff 풀(§79). 따라서 조회
#   계층의 cap 은 **비현실 극단 전용 안전 가드**로 성격을 바꾸고(실사용 최대치의 수십 배), 상세 패널
#   목록·그래프 노드가 조용히 부분만 나오지 않게 한다.
#   실측 근거(2026-07-29): 종전 300 에서 `cc_pyron.DT_Character_New` 의 이웃(컬럼 55 + 루틴 33 + …)이
#   절단됐고, 스키마 펼침에서도 719 테이블 스키마가 300 으로 잘렸다.
_NEIGHBOR_NODE_CAP = 20000   # 투영 1회 노드 안전 가드(종전 300 — 실사용 최대 수천, 렌더는 컬링이 담당)
# graph-hop-budget(2026-07-28): cap 절단 시 **무엇을 남길지** 결정하는 우선순위. 종전엔 이웃 해소가
# vertex 라벨 알파벳 순(`Column, Datasource, GlossaryTerm, Product, Routine, Schema, Table`)이라
# **Table 이 맨 뒤** → 2-hop 예산 300 이 "같은 스키마의 형제 Routine"(최대 490개)으로 먼저 소진되고
# 사용자가 2-hop 에서 가장 보고 싶어할 "참조로 이어지는 다른 테이블" 이 우선 탈락했다(실측: 앵커
# masangsoft_documents_20260414 의 2-hop = Routine +258 / Table +0). 절단 순서를 의미 우선순위로 고정한다.
_NEIGHBOR_LABEL_PRIORITY = ("Table", "Column", "Routine", "DbObject", "GlossaryTerm", "Schema",
                            "Datasource", "Product")
# 이웃 엣지 1왕복 fetch 상한. 이 값에 포화하면 우선순위 정렬 *이전* 에 잘린 것이라 절단으로 신고한다
# (graph-hop-budget 적대리뷰 P2 — 종전엔 노드 cap 만 절단으로 봐서 부분 그래프가 truncated=false 였다).
_EDGE_FETCH_CAP = _NEIGHBOR_NODE_CAP * 4
# 관계 이웃 Column 의 **부모 Table 보강 전용 예비 예산**(hop ≥ 2 에서만 차감). 부모가 없으면 프론트가
# 그 컬럼을 렌더에서 드롭하므로(graph-core.js colsByTable), 형제 계층 이웃이 예산을 다 먹고 부모가
# 탈락하면 "참조로 이어지는 테이블" 이 화면에서 사라진다 — HB.3 이 없애려던 실패가 cap 상황에서만
# 되살아나는 우선순위 역전(적대리뷰 P1). 계층 이웃 채우기 전에 이 몫을 떼어 둔다.
_PARENT_BACKFILL_RESERVE = 2000   # graph-cap-audit: 가드 상향에 맞춰 비례 확대(종전 60)
# 관계(의미) 엣지 — "이 노드가 무엇과 실제로 연관되는가". 2-hop 이상에서 예산을 먼저 배정한다.
_REL_ELABELS = frozenset({"REFERENCES", "ROUTINE_USES", "RELATED_TERM", "USES", "DESCRIBES",
                          # feature-0040: OBJECT_USES(정의가 참조) · OBJECT_ON(트리거가 걸린 대상)
                          # 둘 다 **관계** 엣지다 — "이 테이블에 뭐가 걸려 있나" 는 형제 나열이
                          # 아니라 사용자가 2-hop 에서 가장 먼저 보고 싶어하는 정보다.
                          "OBJECT_USES", "OBJECT_ON"})
# 계층(소속) 엣지 — "같은 컨테이너에 들어 있다". 앵커 1-hop 에서는 핵심 정보(컬럼·소속 스키마·직결 루틴)라
# 그대로 수집하되, 2-hop 이상에서는 형제 폭발의 원인이라 관계 이웃을 채운 뒤 남는 예산으로만 채운다.
_HIER_ELABELS = frozenset({"HAS_SCHEMA", "HAS_TABLE", "HAS_COLUMN", "HAS_ROUTINE", "HAS_OBJECT"})
# graph-cap-audit: 검색 결과도 "찾았는데 안 보여주는" 절단은 오류다 — 사용자가 실제로 마주친 화면이
#   `'dk_data_release.Item' — 50건 · 상한(검색어를 좁혀보세요)` 였다(검색어를 좁히라는 요구 자체가
#   도구가 할 일을 사용자에게 미룬 것). 반환은 전량으로 두고, 목록 렌더는 프론트가 그룹 접기·
#   가상 스크롤로 감당한다.
_SEARCH_CAP = 5000         # 검색 결과 반환 안전 가드(종전 80)
# graph-search-content(P2 봉인): Cypher `LIMIT` 절단이 trigram 점수 정렬 **이전**에 일어나므로, 넓힌
# WHERE(이름/FQN/컨텐츠 카테고리/AI 분석)에서 이름-정확 매칭이 스캔 순서상 뒤로 밀리면 반환 cap 에 탈락한다.
# 후보 풀을 반환 limit 보다 넓게(≤ ceiling) 떠서 점수 정렬 후 limit 로 재절단 → 고점수(이름-정확) 매칭 보존.
_SEARCH_FETCH_CEIL = 20000  # graph-cap-audit: 내부 후보 풀 안전 가드(종전 240 — 점수 정렬 전 절단이
                            #   고점수 매칭을 탈락시키던 문제를 풀에서도 제거)
_SYNC_BATCH_LOG = 500      # 동기화 진행 로그 간격
# insight-load-spread: sync_graph 의 batched commit 크기. 이 개수의 MERGE 마다 1회 커밋으로 묶어
# 개별-커밋(autocommit) 시 8K 규모 5.7만 WAL fsync 폭주(30분 cron 스파이크)를 ~100 회로 줄인다.
_SYNC_MERGE_BATCH = max(1, int(os.getenv("AGENT_METADATA_GRAPH_SYNC_BATCH", "500") or "500"))


# ── 연결 헬퍼 — 정본은 `shared/db.py` 의 `_pg_conn_pair_{ro,rw}` ──────────
# 본 모듈을 포함해 8개 KB/그래프 모듈이 같은 구현을 복제하고 있었고, 그 구현은 접속 실패를
# 저하(None) 가 아니라 예외로 전파해 아래 모든 호출부의 `if c is None: return <빈 결과>`
# 계약을 깨뜨렸다(PG 순단 시 500). 얇은 위임만 남겨 정본 1곳에서 계약을 보장한다.
# 위임 형태를 유지하는 이유: 테스트가 모듈 속성(`mg._ro_conn`)을 monkeypatch 한다.
def _rw_conn(conn):
    from shared.db import _pg_conn_pair_rw
    return _pg_conn_pair_rw(conn)


def _ro_conn(conn):
    from shared.db import _pg_conn_pair_ro
    return _pg_conn_pair_ro(conn)


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


def _ref_columns_of(raw):
    """ROUTINE_USES 의 `ref_columns` 속성(JSON 문자열) → [{'n': 컬럼, 'k': 'read'|'write'}] (정제).

    routine-column-edges(2026-07-28). 부재·형식 불일치는 **빈 리스트**로 접어 프론트가 기존
    테이블-레벨 연결로 폴백하게 한다(그래프 응답이 결코 깨지지 않도록 전 구간 방어)."""
    if not raw:
        return []
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for it in data:
        if not isinstance(it, dict):
            continue
        name = str(it.get("n") or "").strip()
        if not name:
            continue
        out.append({"n": name, "k": "write" if it.get("k") == "write" else "read"})
    return out


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
               cluster_id=_UNSET, cluster_label=_UNSET, cache=None) -> None:
    """Schema·Table 노드 + HAS_TABLE 엣지 MERGE.

    description=None 이면 description 속성을 **건드리지 않는다**(rag_objects 노드 투영이 큐레이션
    설명을 덮어쓰지 않도록). 빈 문자열("")은 명시적으로 빈 설명을 set.
    cluster_id/cluster_label(Phase C): 기본 _UNSET=미전달(보존). rag_objects 투영은 **항상 현재값(None 포함)을
    전달** — None 이면 _props_set 이 `= null` 로 clear(테이블이 클러스터에서 이탈 시 stale phantom 그룹 방지,
    리뷰 MAJOR-2). scope_roots/schema_tables 가 RETURN → 프론트 sim-group 서버 신호."""
    fqn = f"{schema}.{table}" if schema else table
    skey = _vkey(scope, schema or "(default)")
    tkey = _vkey(scope, fqn)
    # cyvol: Schema 정점은 테이블마다 재-MERGE 됐다(실측 rag 16,367 + routines 23,053 회 →
    # 실제 distinct 스키마는 ~370). 속성 동일 시 실행 스코프 1회로 축약.
    sprops = {"name": schema or "(default)", "fqn": schema or "(default)", "scope_key": scope}
    if _cache_once(cache, _vmark("Schema", skey, sprops)):
        _merge_vertex(cur, "Schema", skey, sprops)
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


def sync_column(cur, scope, schema, table, column, description="", source="manual", ordinal=None,
                cache=None) -> None:
    """Column 노드 + HAS_COLUMN 엣지 MERGE (Table 선행 가정 또는 동시 MERGE).

    feature-0016 graphux5: ordinal(실제 스키마 컬럼 순서, 1-based) 을 Column 정점 속성으로 투영한다.
    None 이면 SET 생략(기존 ordinal 보존) — _props_set 이 정수 리터럴로 처리(injection-safe)."""
    tfqn = f"{schema}.{table}" if schema else table
    cfqn = f"{tfqn}.{column}"
    tkey = _vkey(scope, tfqn)
    ckey = _vkey(scope, cfqn)
    # cyvol: 소속 Table 정점은 컬럼마다 재-MERGE 됐다(3,135 행 → distinct 테이블 389).
    tprops = {"name": table, "fqn": tfqn, "scope_key": scope,
              "schema_name": schema or "", "table_name": table}
    if _cache_once(cache, _vmark("Table", tkey, tprops)):
        _merge_vertex(cur, "Table", tkey, tprops)
    _merge_vertex(cur, "Column", ckey,
                  {"name": column, "fqn": cfqn, "scope_key": scope,
                   "table_name": table, "column_name": column,
                   "description": description, "source": source, "ordinal": ordinal})
    _merge_edge(cur, "Table", tkey, "HAS_COLUMN", "Column", ckey)


def new_anchor_cache() -> dict:
    """sync 실행 1회용 정점 MERGE 캐시 (feature-0029 churn-e).

    `_anchor_relationship_column` 은 관계마다 Column/Table/Schema 3정점 + 2엣지를 MERGE 해
    관계 1건 = cypher 11회였다. 수십~수백 관계가 **같은 Table/Schema 정점을 공유**하므로
    (예: account.AccountId 를 참조하는 200 관계) 실행 스코프 캐시로 중복을 제거한다 —
    실측상 관계당 cypher 11 → 대개 1~3.

    §18.8 B-1: 종전 구현은 캐시를 **커서 객체 속성**으로 달았는데 `psycopg.Cursor.__slots__`
    가 비어 있어 라이브에서 항상 AttributeError → 캐시가 한 번도 활성화되지 않았다(테스트는
    `__dict__` 를 가진 fake 커서라 통과). 명시 파라미터로 전달해 타입 의존을 제거한다.

    §18.8 B-4: 캐시는 **커밋 확정분만** 담아야 한다. per-row SAVEPOINT 롤백으로 정점이
    사라졌는데 캐시에 남으면 후속 관계가 MERGE 를 건너뛰고, `_merge_edge` 는 정점 부재 시
    에러 없이 0행이라 **엣지가 조용히 소실**된다. 그래서 pending/committed 2단으로 운용한다:
    행 성공 시 `commit_pending`, 실패 시 `drop_pending`, 배치 롤백 시 `reset`.
    """
    return {"committed": set(), "pending": set()}


def anchor_cache_commit_pending(cache) -> None:
    """행 성공 확정 — pending 마크를 committed 로 승격 (feature-0029 churn-e)."""
    if isinstance(cache, dict):
        cache["committed"].update(cache["pending"])
        cache["pending"].clear()


def anchor_cache_drop_pending(cache) -> None:
    """행 실패(SAVEPOINT 롤백) — 그 행이 만든 마크 폐기 → 후속 행이 다시 MERGE."""
    if isinstance(cache, dict):
        cache["pending"].clear()


def anchor_cache_reset(cache) -> None:
    """배치 커밋 실패/step 롤백 — 확정분까지 무효(정점이 실제로 사라졌을 수 있음)."""
    if isinstance(cache, dict):
        cache["committed"].clear()
        cache["pending"].clear()


def _cache_once(cache, mark) -> bool:
    """이 실행에서 (확정 또는 이번 행에서) 이미 처리한 마크면 False. 캐시 미전달=항상 True.

    feature-0030: `_anchor_relationship_column` 안에만 있던 클로저를 모듈 함수로 승격 —
    sync_table/sync_column/sync_routine 이 같은 pending/committed 규약을 공유한다.
    """
    if not isinstance(cache, dict):
        return True
    if mark in cache["committed"] or mark in cache["pending"]:
        return False
    cache["pending"].add(mark)
    return True


def _vmark(label: str, key: str, props: dict) -> tuple:
    """정점 MERGE 중복 제거 마크 — **속성까지** 포함한다 (feature-0030 cyvol).

    같은 Table 정점이라도 단계마다 싣는 속성이 다르다: `_step_rag` 는 semantic_cluster_*,
    `_step_tables` 는 description, `_step_columns`/routine refs 는 이름 3종만 MERGE 한다.
    키만으로 dedup 하면 **먼저 실행된 단계가 뒤 단계의 속성 투영을 삼켜** description·클러스터가
    영구 미반영된다(계층 파괴). 속성을 마크에 넣으면 '같은 정점을 같은 속성으로' 다시 MERGE 하는
    경우에만 생략되므로 단계 간 캐시 공유가 안전해진다.
    """
    return (label, key, tuple(sorted((k, repr(v)) for k, v in (props or {}).items())))


def routine_refs_signature(refs) -> str:
    """routine 참조 목록의 안정 서명 (feature-0030 cyvol).

    `sync_routine` 은 routine 마다 ROUTINE_USES 를 **전량 DELETE 후 재-MERGE** 한다(정의 변경으로
    사라진 참조의 stale-edge 방지). 전량 sync 실측에서 이 패턴이 DELETE 23,053 + 엣지 MERGE 28,034
    = cypher 51,087 회(전체 158,544 의 32%)를 차지했는데, 실제로 참조가 바뀌는 routine 은 하루
    수백 건뿐이다. 서명이 같으면 재작성을 통째로 생략한다.

    정규화는 **엣지를 만드는 요소 전부**(fqn·kind·cross·cols)를 담는다. 엣지 생성 루프가 건너뛰는
    입력(파싱 후 table 이 빈 fqn)도 서명에는 포함되는데, 이는 '실제로는 동일한데 서명이 달라져
    재작성' 방향의 보수적 오차라 누락(재작성이 필요한데 생략)은 발생하지 않는다.

    **routine-column-edges(2026-07-28): `cols` 가 서명에 반드시 포함되어야 한다.** 참조 컬럼은
    `ROUTINE_USES` 의 `ref_columns` 속성으로 투영되므로 엣지 내용의 일부다. 서명이 fqn·kind·cross
    만 담으면 "참조 테이블은 그대로인데 컬럼 정보가 새로 생긴" 기존 routine 전량이 재작성 생략에
    걸려 **`ref_columns` 가 영영 투영되지 않는다**(기능이 조용히 죽는 경로). 이 확장으로 배포 후
    첫 sync 에서 참조를 가진 routine 이 **1회 재작성**되고(그것이 곧 backfill), 이후에는 서명이
    안정되어 cyvol 절감 효과가 그대로 유지된다 — §16.3 blast-radius 게이트 대상이며 규모는
    routine 1회분(실측 계보: DELETE 23,053 + MERGE 28,034)으로 유한하다.

    §18.8 패널: 같은 fqn 이 중복되면 엣지 루프는 **입력 순서상 마지막**이 이깁니다(뒤의 MERGE 가
    relation_type 을 덮어씀). 서명도 같은 규칙으로 접은 뒤 정렬해 **최종 엣지 집합과 1:1** 로 만든다
    — 그냥 정렬만 하면 중복 fqn 의 순서가 바뀔 때 최종 엣지는 달라지는데 서명은 같아진다.
    입력이 dict 가 아니거나(JSON 문자열 등) 손상돼도 예외 없이 처리한다 — 이 함수는 정점 MERGE
    **이전**에 호출되므로, 여기서 raise 하면 종전에는 만들어지던 Routine 정점·HAS_ROUTINE 까지
    잃는다(패널 지적: 실패 지점 이동).
    """
    if isinstance(refs, str):
        try:
            refs = json.loads(refs or "[]")
        except Exception:
            refs = []
    last: dict = {}
    for r in (refs or []):
        if not isinstance(r, dict):
            continue
        fqn = str(r.get("fqn") or "").strip()
        if not fqn:
            continue
        # routine-column-edges: 참조 컬럼(cols)도 엣지 속성(ref_columns)이 되므로 서명에 담는다.
        #   손상 입력은 조용히 무시(이 함수는 절대 raise 하지 않는다 — 위 docstring 참조).
        _cols = r.get("cols")
        _csig = ""
        if isinstance(_cols, list) and _cols:
            _parts = []
            for c in _cols:
                if not isinstance(c, dict):
                    continue
                _n = str(c.get("n") or "").strip()
                if _n:
                    _parts.append(_n + "\x1d" + ("write" if c.get("k") == "write" else "read"))
            _csig = ",".join(sorted(_parts))
        last[fqn] = (str(r.get("kind") or "read"), "1" if r.get("cross") else "", _csig)
    payload = "\x1f".join("\x1e".join((f,) + last[f]) for f in sorted(last))
    return _hashlib.sha1(payload.encode("utf-8", "replace")).hexdigest()


def _anchor_relationship_column(cur, scope, tbl_fqn, col, cache=None) -> str:
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
    def _once(mark) -> bool:
        """이 실행에서 (확정 또는 이번 행에서) 이미 MERGE 했으면 False. 캐시 미전달=항상 True."""
        return _cache_once(cache, mark)

    if _once(("Column", ckey)):
        _merge_vertex(cur, "Column", ckey,
                      {"name": col, "fqn": f"{tbl_fqn}.{col}", "scope_key": scope,
                       "column_name": col})
    if table and schema:
        tkey = _vkey(scope, tbl_fqn)
        skey = _vkey(scope, schema)
        if _once(("Table", tkey)):
            _merge_vertex(cur, "Table", tkey,
                          {"name": table, "fqn": tbl_fqn, "scope_key": scope,
                           "schema_name": schema, "table_name": table})
        if _once(("Schema", skey)):
            _merge_vertex(cur, "Schema", skey,
                          {"name": schema, "fqn": schema, "scope_key": scope})
        if _once(("HAS_TABLE", skey, tkey)):
            _merge_edge(cur, "Schema", skey, "HAS_TABLE", "Table", tkey)
        if _once(("HAS_COLUMN", tkey, ckey)):
            _merge_edge(cur, "Table", tkey, "HAS_COLUMN", "Column", ckey)
    return ckey


def sync_relationship(cur, scope, src_fqn, src_col, tgt_fqn, tgt_col,
                      cardinality="", source="fk_introspect", confidence=1.0,
                      weight=None, status="", tgt_scope=None, cache=None) -> None:
    """REFERENCES 엣지 (Column→Column) MERGE. 양끝 Column 노드 + Table/Schema 앵커링 보장.

    weight/status(feature-0016): 동적 신뢰 가중치·상태(candidate/trusted/broken)를 엣지에 투영해
    UI 가 신뢰 실선 / 추정 점선으로 구분. broken 은 애초에 sync_graph 가 투영에서 제외한다.
    tgt_scope(crossds-rel, ADR-019): 대상 끝점 scope(기본=scope=src). 크로스-ds 관계는 각 끝점을 **자기 scope**
    로 앵커 → _vkey(scope:fqn) 가 서로 다른 namespace 라 자동 분리. tgt_scope != scope 이면 엣지에 cross_ds 속성
    (프론트 교차DB 표식 + node_analysis 완화). neighborhood BFS 는 scope-무관이라 크로스 엣지가 자동 노출."""
    src_scope = scope
    tscope = tgt_scope if tgt_scope is not None else scope
    s_ckey = _anchor_relationship_column(cur, src_scope, src_fqn, src_col, cache=cache)
    t_ckey = _anchor_relationship_column(cur, tscope, tgt_fqn, tgt_col, cache=cache)
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


def routine_expected_edge_count(refs, scope) -> int:
    """refs 가 만들어야 할 ROUTINE_USES 엣지 수 (feature-0030 cyvol).

    엣지 루프와 **같은 필터**(빈 fqn·파싱 후 빈 table 스킵)를 적용하고 tkey 로 중복을 접는다 —
    엣지는 (routine, table) 쌍당 1개라 같은 테이블을 두 번 참조해도 1개다.
    """
    keys = set()
    if isinstance(refs, str):
        try:
            refs = json.loads(refs or "[]")
        except Exception:
            refs = []
    for r in (refs or []):
        if not isinstance(r, dict):
            continue
        tfqn = str(r.get("fqn") or "").strip()
        if not tfqn:
            continue
        parts = [p for p in tfqn.split(".") if p]
        if not parts or not parts[-1]:
            continue
        keys.add(_vkey(scope, tfqn))
    return len(keys)


def _routine_edges_intact(rkey, refs, scope, deg_cache) -> bool:
    """그래프의 실제 ROUTINE_USES 차수가 기대치와 일치하는가 (feature-0030 cyvol, 패널 B3).

    서명이 같아도 **엣지가 실제로 있는지** 확인해야 `--full` 의 재조정 보장이 유지된다.
    `_merge_edge` 는 끝점 정점이 없으면 오류 없이 0행이라, 서명만 신뢰하면 그런 소실이 영구
    고착된다. `deg_cache` 미전달(외부 호출자)이면 검사를 건너뛴다 — 종전 동작.
    """
    if deg_cache is None:
        return True
    try:
        actual = int(str(deg_cache.get(rkey) or 0))
    except (TypeError, ValueError):
        return False   # 판독 불가 → 보수적으로 재작성
    return actual == routine_expected_edge_count(refs, scope)


def sync_routine(cur, scope, schema, name, routine_type="procedure", params="", refs=None,
                 cluster_id=_UNSET, cluster_label=_UNSET, cache=None, sig_cache=None,
                 deg_cache=None) -> None:
    """Routine 노드 + HAS_ROUTINE(Schema→Routine) + ROUTINE_USES(Routine→Table) MERGE (ADR-016).

    key/fqn 은 `schema.name()` — 뒤의 `()` 가 동명 테이블 키(`schema.name`)와의 전역 key 충돌을
    막는 네임스페이스이자 사람이 읽는 함수 표기다. refs = [{fqn:'schema.table', kind:'read|write'}]
    (routine_objects.referenced_tables). 참조 Table 은 최소 MERGE(설명 미설정 — 큐레이션 비파괴)로
    앵커링해 고아 엣지를 막는다(_anchor_relationship_column 동형).
    cluster_id/cluster_label(content-cluster RC3): sync_table 동형 — 기본 _UNSET=미전달(보존),
    routine_objects 투영은 항상 현재값(None 포함)을 전달해 이탈 시 `= null` clear(stale phantom 방지).
    schema_tables 가 RETURN → 프론트 sim-group 이 루틴도 be: 그룹으로 소비."""
    fqn = f"{schema}.{name}()" if schema else f"{name}()"
    skey = _vkey(scope, schema or "(default)")
    rkey = _vkey(scope, fqn)
    sprops = {"name": schema or "(default)", "fqn": schema or "(default)", "scope_key": scope}
    if _cache_once(cache, _vmark("Schema", skey, sprops)):
        _merge_vertex(cur, "Schema", skey, sprops)
    _refs_sig = routine_refs_signature(refs)
    rprops = {"name": name, "fqn": fqn, "scope_key": scope, "schema_name": schema or "",
              "routine_type": routine_type or "procedure", "params": (params or "")[:500],
              "source": "routine_introspect"}
    if cluster_id is not _UNSET:
        rprops["semantic_cluster_id"] = cluster_id      # None → _props_set 이 = null 로 clear
    if cluster_label is not _UNSET:
        rprops["semantic_cluster_label"] = cluster_label
    _merge_vertex(cur, "Routine", rkey, rprops)
    _merge_edge(cur, "Schema", skey, "HAS_ROUTINE", "Routine", rkey)
    # cyvol: 참조가 직전 sync 와 동일하면 아래 DELETE+재MERGE 전체를 생략한다(전량 sync 실측
    # 기준 cypher 51,087 회 = 전체의 32%). `sig_cache.get(rkey)` 가 None(신규 routine·배포 직후·
    # 선조회 실패)이면 hex digest 와 절대 같지 않아 자동으로 miss → 기존 경로.
    #
    # §18.8 패널(MAJOR-1): **이 실행에서 같은 rkey 를 처음 보는 경우에만** 스냅샷을 신뢰한다.
    # 정점 key 는 `scope:schema.name()` 이라 routine_type 이 빠져 있는데 SSOT 유일키는
    # (scope, schema, name, **type**) 이다 — MySQL 은 동명 FUNCTION/PROCEDURE 공존을 허용하므로
    # 두 소스 행이 한 정점을 공유할 수 있다. `_sig_by_key` 는 step 진입 시 1회 스냅샷이고 재작성
    # 후에도 갱신되지 않으므로, 두 번째 행이 stale 항목과 일치해 **재작성을 건너뛰고 첫 행의
    # 엣지를 최종 상태로 남긴다**(종전은 마지막 행 우선으로 결정적). 게다가 sync 마다 어느 행이
    # 이기는지 뒤바뀌어 영구 flip-flop 이 된다. 첫 방문 게이트로 종전 semantics(마지막 행 우선)를
    # 복원한다 — 마크는 cache 의 pending/committed 규약을 그대로 타므로 행 롤백 시 함께 폐기된다.
    _first_visit = _cache_once(cache, ("ROUTINE_REFS", rkey))
    if (_first_visit and sig_cache is not None and sig_cache.get(rkey) == _refs_sig
            and _routine_edges_intact(rkey, refs, scope, deg_cache)):
        return
    # §18.8 패널(MAJOR): 가산적 MERGE 만으로는 정의 변경으로 사라진 참조가 그래프에 영구 잔존
    # (REFERENCES 의 broken stale-edge 클래스 재도입). refs 가 이 routine 의 **전량**이므로
    # 기존 ROUTINE_USES 를 먼저 회수하고 현재 참조만 재-MERGE 한다(멱등·결정적).
    #
    # §18.8 패널(M3): 재작성에 들어가기 전에 서명을 **먼저 지운다**. autocommit(비-owned) 경로엔
    # SAVEPOINT 가 없어 DELETE 가 이미 커밋된 뒤 엣지 MERGE 가 중간에 실패하면 정점에는 **직전
    # 서명이 그대로 남는데**, 참조가 바뀌지 않은 재작성이었다면 그 값이 현재 서명과 같아
    # 이후 모든 sync 가 skip → 부분 엣지가 영구 고착된다. 미리 지우면 실패 시 서명이 없어
    # 다음 sync 가 전량 재작성한다. owned 모드에선 행 SAVEPOINT 가 전체를 되돌려 무해.
    try:
        _cypher(cur, f"MATCH (r:Routine {{key: {_cq(rkey)}}}) REMOVE r.refs_sig RETURN 1", 1)
    except Exception:
        pass   # 라벨/속성 부재 — 아래 재작성이 어차피 진행되고 실패는 호출측 errors 로 집계
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
        # cyvol: 참조 Table 앵커는 28,034 회 MERGE 됐으나 distinct 는 7,331 뿐.
        _tprops = {"name": table, "fqn": tfqn, "scope_key": scope,
                   "schema_name": ".".join(parts[:-1]), "table_name": table}
        if _cache_once(cache, _vmark("Table", tkey, _tprops)):
            _merge_vertex(cur, "Table", tkey, _tprops)
        # §57: SSOT refs 의 cross 플래그(크로스-DB 참조, §56 RC2)를 AGE 엣지 속성으로 투영 —
        #   프론트 크로스 시각 구분(REFERENCES 의 cross_ds='1' 관례와 동일 키, ADR-019 정합).
        # routine-column-edges(2026-07-28): 참조 컬럼 목록(SSOT `cols`)을 JSON 문자열로 동봉 —
        #   프론트가 테이블 펼침 시 사용선을 컬럼별로 분해한다. 값 부재는 곧 "컬럼 미확정" 이라
        #   프론트가 기존 테이블-레벨 연결로 폴백한다(속성 자체가 없으면 SET 생략 = 무회귀).
        _eprops = {"relation_type": (r or {}).get("kind") or "read",
                   **({"cross_ds": "1"} if (r or {}).get("cross") else {})}
        _cols = (r or {}).get("cols")
        if isinstance(_cols, list) and _cols:
            try:
                _eprops["ref_columns"] = json.dumps(_cols, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                pass
        _merge_edge(cur, "Routine", rkey, "ROUTINE_USES", "Table", tkey, _eprops)
    # cyvol: 서명은 엣지 재작성이 **끝난 뒤** 기록한다(위 REMOVE 와 짝) — 엣지보다 먼저 쓰면
    # '서명은 최신, 엣지는 불완전'이 고착된다. 비용은 참조가 바뀐 routine 1건당 1회(하루 수백).
    #
    # §18.8 패널(MAJOR-2): 이 문은 **삼키지 않는다**. 삼키면 PostgreSQL 이 트랜잭션을 aborted 로
    # 둔 채 `_sync_row_guard` 가 `RELEASE SAVEPOINT` 실패까지 삼키고 **성공(True)** 을 반환한다
    # → 카운터는 증가, `errors`/`step_failures` 는 0, 다음 step 의 커밋이 조용히 ROLLBACK 으로
    # 수렴해 **최대 500행이 소실된 채 ok:true + 워터마크 전진**(이 파일 `_run_step` docstring 이
    # 관측 사실로 기록한 그 결함면). 전파하면 행 SAVEPOINT 가 롤백되고 errors 로 집계된다.
    # 이 문이 routine 행의 **마지막** 문이라 뒤에 오류를 드러낼 문이 없다는 점이 핵심이다.
    _cypher(cur, f"MATCH (r:Routine {{key: {_cq(rkey)}}}) "
                 f"SET r.refs_sig = {_cq(_refs_sig)} RETURN 1", 1)


def sync_db_object(cur, scope, schema, name, role, object_type="", owner_object="",
                   attributes=None, refs=None, description="", cache=None) -> None:
    """DbObject 노드 + HAS_OBJECT(Schema→DbObject) + OBJECT_USES/OBJECT_ON MERGE (feature-0040).

    `sync_routine` 의 역할-객체 판이다. 다른 점 셋:

    1. **key 네임스페이스** — `schema.name[role]`. 루틴이 `()` 로 동명 테이블과의 전역 key 충돌을
       피한 것과 같은 이유이되, **역할까지 넣어야 한다**: 같은 스키마에 동명의 뷰와 트리거가
       공존할 수 있고(서로 다른 카탈로그 네임스페이스), 역할이 빠지면 한 정점을 두 SSOT 행이
       공유해 서로의 엣지를 덮어쓴다.

    2. **OBJECT_ON(소유 관계)** — 트리거의 대상 테이블·별칭의 대상 객체는 "참조" 가 아니라
       "여기에 걸려 있다" 이다. OBJECT_USES 와 합치면 "이 테이블에 걸린 트리거" 질문에 답할 수
       없어진다(정의가 그 테이블을 읽기만 하는 다른 객체와 구분 불가).

    3. **refs 서명 최적화 없음** — 루틴은 정의 변경이 드물어 `refs_sig` 로 재작성을 건너뛰지만,
       역할 객체는 전체 수가 루틴보다 훨씬 적어(라이브 관측 기준 스키마당 수~수십) 서명 관리
       비용이 이득을 넘는다. 대신 루틴과 **동일한 DELETE→재MERGE 멱등 규약**은 그대로 지킨다 —
       가산적 MERGE 만 하면 정의 변경으로 사라진 참조가 영구 잔존한다(REFERENCES stale-edge 클래스).
    """
    role = str(role or "").strip()
    fqn = f"{schema}.{name}[{role}]" if schema else f"{name}[{role}]"
    skey = _vkey(scope, schema or "(default)")
    okey = _vkey(scope, fqn)
    sprops = {"name": schema or "(default)", "fqn": schema or "(default)", "scope_key": scope}
    if _cache_once(cache, _vmark("Schema", skey, sprops)):
        _merge_vertex(cur, "Schema", skey, sprops)
    oprops = {"name": name, "fqn": fqn, "scope_key": scope, "schema_name": schema or "",
              "object_role": role, "object_type": str(object_type or "")[:32],
              "owner_object": str(owner_object or "")[:512],
              "source": "db_object_introspect"}
    if description:
        oprops["description"] = str(description)[:2000]
    if isinstance(attributes, dict) and attributes:
        try:
            oprops["object_attrs"] = json.dumps(attributes, ensure_ascii=False,
                                                separators=(",", ":"))[:2000]
        except (TypeError, ValueError):
            pass
    _merge_vertex(cur, "DbObject", okey, oprops)
    _merge_edge(cur, "Schema", skey, "HAS_OBJECT", "DbObject", okey)

    # 멱등 재작성 — 기존 관계 엣지를 회수한 뒤 현재 상태만 재-MERGE(sync_routine 동형).
    for _et in ("OBJECT_USES", "OBJECT_ON"):
        try:
            _cypher(cur, f"MATCH (o:DbObject {{key: {_cq(okey)}}})-[u:{_et}]->() DELETE u RETURN 1", 1)
        except Exception:
            pass   # 라벨 부재(0054 미적용) 등 — MERGE 단계가 실패해 호출측 errors 로 집계된다

    def _anchor_table(tfqn: str) -> str:
        """참조 Table 최소 MERGE(설명 미설정 — 큐레이션 비파괴). 반환 vertex key ('' = 스킵)."""
        tfqn = str(tfqn or "").strip()
        parts = [p for p in tfqn.split(".") if p]
        table = parts[-1] if parts else ""
        if not table:
            return ""
        tkey = _vkey(scope, tfqn)
        _tprops = {"name": table, "fqn": tfqn, "scope_key": scope,
                   "schema_name": ".".join(parts[:-1]), "table_name": table}
        if _cache_once(cache, _vmark("Table", tkey, _tprops)):
            _merge_vertex(cur, "Table", tkey, _tprops)
        return tkey

    # OBJECT_ON — 트리거가 걸린 테이블 / 별칭의 대상. owner 는 스키마 수식이 없는 이름이므로
    # 저장 slot(schema)으로 수식해 Table key 공간과 맞춘다(sync_routine 의 refs fqn 규약 동일).
    owner = str(owner_object or "").strip()
    if owner and role in ("trigger", "alias"):
        # 별칭 대상은 `[db].[schema].[obj]` 3-part 일 수 있다 — 마지막 세그먼트가 객체명이다.
        _own_parts = [p.strip("[]`\"") for p in owner.split(".") if p.strip("[]`\"")]
        _own_leaf = _own_parts[-1] if _own_parts else ""
        if _own_leaf:
            _own_fqn = f"{schema}.{_own_leaf}" if schema else _own_leaf
            _okey_t = _anchor_table(_own_fqn)
            if _okey_t:
                _merge_edge(cur, "DbObject", okey, "OBJECT_ON", "Table", _okey_t,
                            {"relation_type": "owns"})

    for r in (refs or []):
        tfqn = str((r or {}).get("fqn") or "").strip()
        if not tfqn:
            continue
        tkey = _anchor_table(tfqn)
        if not tkey:
            continue
        _eprops = {"relation_type": (r or {}).get("kind") or "read",
                   **({"cross_ds": "1"} if (r or {}).get("cross") else {})}
        _merge_edge(cur, "DbObject", okey, "OBJECT_USES", "Table", tkey, _eprops)


def project_cluster_props(changes, conn=None) -> int:
    """재클러스터 변경분의 semantic_cluster_id/label 을 해당 정점에만 targeted SET (analysis-freshness).

    changes: [{"label": "Table"|"Routine", "key": <graph vertex key>, "cid": int|None, "lab": str|None}].
    30분 incremental sync(cron·flock, §82)는 정본 경로로 유지하되, 재클러스터 직후 결과가 그래프 뷰
    다음 로드부터 보이도록 변경 정점의 두 속성만 즉시 투영한다 — 사용자 리포트(2026-07-23 log_v2):
    'DB 전체 AI 능동 분석' 완료 후에도 컨텐츠 클러스터가 수십 분~시간 단위로 이전 구조로 남던 지연의
    투영 구간 절반을 제거. MATCH(MERGE 아님)라 미투영 정점은 no-op(구조 생성은 sync 정본 소관).
    cid/lab None 은 `= null` clear(_props_set — 이탈 stale phantom 방지). 실패는 행 단위 삼킴(fail-soft)."""
    done = 0
    items = [ch for ch in (changes or [])
             if ch and ch.get("key") and ch.get("label") in ("Table", "Routine")]
    if not items:
        return 0
    c, owned = _rw_conn(conn)
    if c is None:
        return 0
    try:
        cur = c.cursor()
        _set_age_path(cur)
        for ch in items:
            setc = _props_set("t", {"semantic_cluster_id": ch.get("cid"),
                                    "semantic_cluster_label": ch.get("lab")})
            if not setc:
                continue
            # SAVEPOINT 행 격리(§18.8 m1) — 주입 non-autocommit conn 에서 한 행의 실패가 블록
            # 트랜잭션을 aborted 로 남겨 caller 의 후속 statement 를 연쇄 실패시키지 않게
            # (semantic_cluster 루틴 fetch 동형). autocommit 에서는 SAVEPOINT 실패가 무해(삼킴).
            try:
                cur.execute("SAVEPOINT mg_proj_cluster")
            except Exception:
                pass
            try:
                _cypher(cur, f"MATCH (t:{ch['label']} {{key: {_cq(ch['key'])}}}) "
                             f"SET {setc} RETURN 1", 1)
                done += 1
                try:
                    cur.execute("RELEASE SAVEPOINT mg_proj_cluster")
                except Exception:
                    pass
            except Exception as exc:
                try:
                    cur.execute("ROLLBACK TO SAVEPOINT mg_proj_cluster")
                    cur.execute("RELEASE SAVEPOINT mg_proj_cluster")
                except Exception:
                    pass
                _log.debug("project_cluster_props_failed key=%s err=%r", ch.get("key"), exc)
        cur.close()
    except Exception as exc:
        _log.warning("project_cluster_props 실패: %r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return done


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
           # 회수 계측 — 이 값이 계속 0 이고 그래프 GlossaryTerm 수가 kb_glossary 를
           # 넘어서면 회수가 다시 멈춘 것이다(2026-09-02 이전 상태). 증분 실행에서는
           # 회수를 건너뛰므로 그 사실을 `glossary_retract_skipped` 로 남긴다.
           "glossary_retracted": 0, "glossary_retract_skipped": "",
           "glossary_retract_unparsed": 0,
           # feature-0040: 역할 기반 DB 객체(뷰·트리거·예약작업·별칭·시퀀스) 투영 건수.
           # 미리 키를 두어야 0054 미적용 배포에서도 리포트 shape 가 동일하다(소비처 KeyError 방지).
           "db_objects": 0,
           "errors": 0, "step_failures": 0, "since": since, "synced_at": None, "commits": 0}
    _t0 = _time.perf_counter()  # feature-0026 (M4): sync 소요 계측 (cron.log 리포트에 포함)
    c, owned = _rw_conn(conn)
    if c is None:
        return rep
    _pending = [0]
    _err_samples: list = []   # §56 RC1 관측성: per-row 실패 첫 5건(단계: 예외) — 종료 시 warning 1줄
    # cyvol: 정점 MERGE 중복 제거 캐시 — rag/tables/columns/routines 4 단계가 **공유**한다.
    # 마크에 속성을 포함(_vmark)하므로 단계별로 다른 속성을 싣는 Table 정점도 서로를 삼키지
    # 않는다. 관계 단계(_step_relationships)는 feature-0029 의 키-마크 규약을 그대로 쓰는
    # 자체 캐시를 유지한다(마크 형태가 달라 섞이지 않음 — 의도적 분리).
    _vcache = new_anchor_cache()

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
                # cyvol: 커밋 실패로 배치가 통째로 사라졌다 — 확정 마크 무효(위 _run_step 동형).
                anchor_cache_reset(_vcache)
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
            # cyvol: step 롤백은 직전 커밋 이후의 정점 MERGE 를 되돌린다 — 확정 마크까지 무효화
            # 하지 않으면 후속 단계가 MERGE 를 건너뛰고 `_merge_edge` 가 정점 부재로 조용히
            # 0행이 된다(feature-0029 B-4 와 동일 결함면).
            anchor_cache_reset(_vcache)

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
                               cluster_label=(clab if clab else None), cache=_vcache)
                if _sync_row_guard(cur, owned, _err_samples, "rag_table", _row, rep):
                    rep["rag_tables"] += 1
                    anchor_cache_commit_pending(_vcache)   # cyvol: 행 확정 후에만 마크 승격
                    _pending[0] += 1; _tick()
                else:
                    anchor_cache_drop_pending(_vcache)
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
                    sync_table(cur, sc, sch or "", tbl, desc or "", src or "manual", cache=_vcache)
                if _sync_row_guard(cur, owned, _err_samples, "table_desc", _row, rep):
                    rep["tables"] += 1
                    anchor_cache_commit_pending(_vcache)
                    _pending[0] += 1; _tick()
                else:
                    anchor_cache_drop_pending(_vcache)
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
                    sync_column(cur, sc, sch or "", tbl, col, desc or "", src or "manual", ordinal=ordn,
                                cache=_vcache)
                if _sync_row_guard(cur, owned, _err_samples, "column_desc", _row, rep):
                    rep["columns"] += 1
                    anchor_cache_commit_pending(_vcache)
                    _pending[0] += 1; _tick()
                else:
                    anchor_cache_drop_pending(_vcache)
                    rep["errors"] += 1
        _run_step("column_descriptions", _step_columns)
        # 3) table_relationships — broken(파단)은 그래프에서 **삭제**(가산적 MERGE 라 stale 방지,
        #    학습된 '비관계'), 그 외는 weight/status 와 함께 투영. (전량 스캔 후 status 로 분기.)
        # crossds-rel(ADR-019): source/target_datasource_key 도 읽어 크로스-ds 엣지는 각 끝점을 자기 datasource
        #   scope 로 앵커(tgt_scope). 컬럼 부재(마이그 0036 미적용)면 SELECT 실패 → except graceful. intra-ds 는
        #   sds==tds → tgt_scope=sc(기존 동작 완전 보존, 스코프!=ds 인 794 레거시 행도 불변).
        def _step_relationships():
            # churn-e: 이 step 실행 스코프의 정점 MERGE 캐시(§18.8 B-1 — 커서 속성 부착은
            # psycopg Cursor.__slots__ 때문에 라이브에서 항상 실패했다. 명시 전달로 전환).
            _anchor_cache = new_anchor_cache()
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
                                          weight=wgt, status=st or "", tgt_scope=tgt_scope,
                                          cache=_anchor_cache)   # churn-e: 공유 정점 중복 MERGE 제거
                if _sync_row_guard(cur, owned, _err_samples, "relationship", _row, rep):
                    rep["relationships_deleted" if _is_del else "relationships"] += 1
                    # churn-e(§18.8 B-4): 행이 **커밋 확정**된 뒤에만 캐시에 승격한다 —
                    # SAVEPOINT 롤백된 행의 정점을 캐시에 남기면 후속 행이 MERGE 를 건너뛰고
                    # _merge_edge 가 정점 부재로 조용히 0행(엣지 소실)이 된다.
                    anchor_cache_commit_pending(_anchor_cache)
                    _pending[0] += 1
                    _n_before = rep["commits"]
                    _tick()
                    if rep["commits"] == _n_before and _pending[0] == 0:
                        # 커밋 시도가 실패해 롤백된 경우(_tick 이 step_failures 계상) — 확정분 무효.
                        anchor_cache_reset(_anchor_cache)
                else:
                    anchor_cache_drop_pending(_anchor_cache)   # 실패 행의 마크 폐기
                    rep["errors"] += 1
        _run_step("table_relationships", _step_relationships)
        # 3b) routine_objects (함수·프로시저, graph-funcproc ADR-016) — Routine 노드 +
        #     HAS_ROUTINE + 참조 테이블 ROUTINE_USES. 테이블 부재(구 DB·0034 미적용)는 _run_step 이 격리.
        #     content-cluster RC3: 의미 클러스터(semantic_cluster_id/label)도 Routine 정점에 투영 —
        #     컬럼 부재(0040 미적용 창)는 구 SELECT 로 폴백(클러스터만 미투영, step 은 계속).
        def _step_routines():
            _w, _a = _scope_since_where()
            _has_cluster_cols = True
            try:
                cur.execute("SELECT scope_key, schema_name, routine_name, routine_type, params, "
                            "referenced_tables, semantic_cluster_id, semantic_cluster_label "
                            "FROM routine_objects" + _w, _a)
                rows = cur.fetchall()
            except Exception:
                # §18.8 패널 m1: rollback 은 owned(자체 batched tx)일 때만 — 외부 주입 conn 의
                # 미커밋 작업을 무단 파괴하지 않는다(_step_relationships 의 `if owned:` 선례 정합).
                # owned 에서는 _run_step 진입 시 force-커밋이 선행돼 버려지는 것은 aborted 빈 tx 뿐.
                if owned:
                    try:
                        c.rollback()
                    except Exception:
                        pass
                    _pending[0] = 0   # rollback 으로 버려진 미커밋 카운터 정합
                _has_cluster_cols = False
                cur.execute("SELECT scope_key, schema_name, routine_name, routine_type, params, "
                            "referenced_tables FROM routine_objects" + _w, _a)
                rows = [tuple(r) + (None, None) for r in cur.fetchall()]
            # cyvol: Routine 정점의 refs 서명 + 실제 ROUTINE_USES 차수를 **cypher 2회**로 일괄
            # 선조회한다(라이브 실측 23,057 행 / 3.2ms, 차수 19,870 행 / 74ms). routine 마다
            # 전량 DELETE 하던 23,053 회를 대체한다.
            #
            # §18.8 패널(B3/MAJOR-3): 서명만 보면 `--full` 이 문서상 보장하던 **무조건 재조정**이
            # 사라진다 — refs 변경을 동반하지 않은 엣지 소실(`_merge_edge` 는 끝점 정점 부재 시
            # 오류 없이 0행)은 영구 고착되고 운영 탈출구가 없다. 그래서 서명이 같아도 **실제 차수가
            # 기대치와 다르면 재작성**한다. 차수 조회 1회로 그 안전망을 O(1) 에 복원한다(전량
            # 재작성 51,087 회를 되살리지 않는다). 차수는 fqn 기준 distinct 참조 수와 비교한다 —
            # 엣지는 (routine, table) 쌍당 1개이므로 중복 fqn 은 1개로 접힌다.
            _sig_by_key: dict = {}
            _deg_by_key: dict = {}
            # scope 술어는 **각 MATCH 절의 패턴 전체 뒤**에 붙는다. openCypher 의 WHERE 는
            # 패턴 다음에만 올 수 있어서, 종전처럼 노드 패턴 직후에 고정 보간하면 관계 패턴이
            # 있는 쿼리에서 `… WHERE r.scope_key = 'x'-[u:ROUTINE_USES]->() …` 가 되어 PG(AGE)가
            # `syntax error at or near ":"` 로 거부한다 — scope_key 가 None 인 경로만 유효했으므로
            # **모든 per-datasource sync** 의 차수 선조회가 항상 실패했다(2026-07-28 라이브
            # backfill 리포트에서 발견). 정합성은 fail-safe 였지만(빈 차수 dict → 전량 재작성)
            # cyvol 최적화가 스코프 경로에서 통째로 무효였고, 예외 경로의 rollback 도 매번 돌았다.
            # 그래서 술어를 패턴 뒤에 붙이도록 쿼리별로 조립한다.
            _sp = (f" WHERE r.scope_key = {_cq(scope_key)}" if scope_key is not None else "")
            for _q, _sink in (
                    (f"MATCH (r:Routine){_sp} RETURN r.key, r.refs_sig", _sig_by_key),
                    (f"MATCH (r:Routine)-[u:ROUTINE_USES]->(){_sp} "
                     f"RETURN r.key, count(u)", _deg_by_key)):
                try:
                    # 행 shape 를 인덱스로 방어적으로 읽는다 — 튜플 언패킹(`for a, b in …`)은
                    # 하네스·드라이버가 1-튜플을 돌려줄 때 ValueError 로 죽어 아래 rollback 을
                    # 유발했다(feature-0016 test_metadata_graph_load_spread 회귀, 패널 M1).
                    for _row in _cypher(cur, _q, 2):
                        if not _row:
                            continue
                        _kk = _unwrap(_row[0])
                        if _kk:
                            _sink[_kk] = _unwrap(_row[1]) if len(_row) > 1 else None
                except Exception as _exc:
                    # 패널 M2: 종전엔 완전 무음이라 선조회가 영구 실패해도 최적화만 조용히
                    # 무효화됐다. 다른 실패 경로와 동일하게 샘플을 남긴다(비차단 — 빈 dict 는
                    # 전량 재작성 = 종전 동작이라 정합성 영향 없음).
                    _sink.clear()
                    if len(_err_samples) < 5:
                        _err_samples.append(
                            f"routine_prefetch: {type(_exc).__name__} {str(_exc)[:160]}")
                    if owned:
                        try:
                            c.rollback()
                        except Exception:
                            pass
                        _pending[0] = 0
                        anchor_cache_reset(_vcache)
            for sc, sch, name, rtype, params, refs, ccid, clab in rows:
                def _row(sc=sc, sch=sch, name=name, rtype=rtype, params=params, refs=refs,
                         ccid=ccid, clab=clab):
                    if isinstance(refs, str):
                        refs = json.loads(refs or "[]")
                    kw = {}
                    if _has_cluster_cols:
                        kw = {"cluster_id": (int(ccid) if ccid is not None else None),
                              "cluster_label": (clab if clab else None)}
                    sync_routine(cur, sc, sch or "", name, rtype or "procedure",
                                 params or "", refs if isinstance(refs, list) else [],
                                 cache=_vcache, sig_cache=_sig_by_key, deg_cache=_deg_by_key, **kw)
                if _sync_row_guard(cur, owned, _err_samples, "routine", _row, rep):
                    rep["routines"] += 1
                    anchor_cache_commit_pending(_vcache)
                    _pending[0] += 1; _tick()
                else:
                    anchor_cache_drop_pending(_vcache)
                    rep["errors"] += 1
        _run_step("routine_objects", _step_routines)

        # 3c) db_objects (역할 기반 DB 객체, feature-0040) — DbObject 노드 + HAS_OBJECT +
        #     OBJECT_USES(정의 참조) + OBJECT_ON(트리거·별칭의 대상). 테이블 부재(구 DB·0054
        #     미적용)는 _run_step 이 격리한다 — 구 배포에서 이 step 만 skip 되고 나머지는 정상.
        #     routine 과 달리 refs 서명 선조회가 없다(sync_db_object docstring 3번 참조).
        def _step_db_objects():
            _w, _a = _scope_since_where()
            cur.execute("SELECT scope_key, schema_name, object_name, object_role, object_type, "
                        "owner_object, attributes, referenced_tables, description "
                        "FROM db_objects" + _w, _a)
            for sc, sch, name, role, otype, owner, attrs, refs, desc in cur.fetchall():
                def _row(sc=sc, sch=sch, name=name, role=role, otype=otype, owner=owner,
                         attrs=attrs, refs=refs, desc=desc):
                    if isinstance(refs, str):
                        refs = json.loads(refs or "[]")
                    if isinstance(attrs, str):
                        attrs = json.loads(attrs or "{}")
                    sync_db_object(cur, sc, sch or "", name, role,
                                   object_type=otype or "", owner_object=owner or "",
                                   attributes=attrs if isinstance(attrs, dict) else {},
                                   refs=refs if isinstance(refs, list) else [],
                                   description=desc or "", cache=_vcache)
                if _sync_row_guard(cur, owned, _err_samples, "db_object", _row, rep):
                    rep["db_objects"] = int(rep.get("db_objects", 0)) + 1
                    anchor_cache_commit_pending(_vcache)
                    _pending[0] += 1; _tick()
                else:
                    anchor_cache_drop_pending(_vcache)
                    rep["errors"] += 1
        _run_step("db_objects", _step_db_objects)

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

        # 4b) kb_glossary 회수 — **AGE 는 MERGE-only 라 원본이 사라져도 정점이 남는다.**
        #
        # 라이브 실측(2026-09-01~02): 소급 정리로 `kb_glossary` 105행을 지웠는데 그 용어들이
        # 그래프에 그대로 살아 있었다(`트랜잭션`·`복합 인덱스`·`정규화`·`멱등성`). 누적분은
        # 수동 회수했지만, **회수 단계가 없으면 다음 삭제에서 그대로 재발한다** — 청소는
        # 원인 제거가 아니다.
        #
        # ⚠ **증분(`since`) 실행에서는 돌지 않는다.** 증분은 「그 시각 이후 변경분」만 조회하므로
        #   그 결과에 없다는 것이 「DB 에 없다」를 뜻하지 않는다. 전건 조회일 때만 판단할 수 있다.
        # ⚠ scope_key 를 지정한 실행이면 **그 scope 안에서만** 회수한다(다른 scope 는 조회 범위
        #   밖이라 역시 판단 근거가 없다).
        def _step_glossary_retract():
            if since:
                rep["glossary_retract_skipped"] = "incremental"
                return
            _w, _a = _scope_since_where()
            cur.execute("SELECT scope_key, term FROM kb_glossary" + _w, _a)
            live = {_vkey(str(sc), f"term:{t}") for sc, t in cur.fetchall()}
            # 정점 식별자는 `key`(= `_vkey`) 다. 리터럴 이스케이프는 `_cq` 로 통일한다 —
            # 손으로 따옴표를 이어 붙이면 용어에 `'` 가 섞이는 순간 cypher 가 깨진다.
            scope_filter = (f"WHERE g.scope_key = {_cq(str(scope_key))} "
                            if scope_key is not None else "")
            rows = _cypher(cur, "MATCH (g:GlossaryTerm) " + scope_filter + "RETURN g.key", 1)
            # ⚠ **`strip('"')` 로 벗기면 안 된다** (codex 리뷰 P3, 2026-09-02). AGE 는 agtype
            #   문자열을 **JSON 으로 직렬화**해 돌려준다 — 용어에 `"` 나 `\` 가 있으면
            #   `\"`·`\\` 로 이스케이프된 채 온다. 그때 strip 은 원본 키를 복원하지 못하고,
            #   `live` 집합(파이썬 raw 문자열)과 어긋나 **멀쩡한 정점이 stale 로 판정돼 삭제된다.**
            #   실측: `He said "hi"` · `back\slash` 에서 strip 불일치, json.loads 는 일치.
            #   (현재 라이브 용어의 특수문자는 작은따옴표 3건뿐이라 아직 안 터졌을 뿐이다 —
            #    자율수집이 임의 용어를 쓰므로 언제든 들어올 수 있다.)
            stale = []
            for r in (rows or []):
                raw = str(r[0])
                try:
                    key = json.loads(raw)
                except Exception:
                    # 파싱 실패한 키는 **건너뛴다**. 못 읽은 것을 지우는 쪽으로 접으면
                    # 되돌릴 수 없다(회수는 파괴적이다).
                    rep["glossary_retract_unparsed"] = int(
                        rep.get("glossary_retract_unparsed", 0)) + 1
                    continue
                if isinstance(key, str) and key not in live:
                    stale.append(key)
            for k in stale:
                def _row(k=k):
                    _cypher(cur, f"MATCH (g:GlossaryTerm {{key: {_cq(k)}}}) "
                                 "DETACH DELETE g RETURN 1", 1)
                if _sync_row_guard(cur, owned, _err_samples, "glossary_retract", _row, rep):
                    rep["glossary_retracted"] = int(rep.get("glossary_retracted", 0)) + 1
                    _pending[0] += 1; _tick()
                else:
                    rep["errors"] += 1
        _run_step("kb_glossary_retract", _step_glossary_retract)

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
        try:
            rep["duration_ms"] = round((_time.perf_counter() - _t0) * 1000.0, 1)  # feature-0026 (M4)
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
    if len(row) > 8:   # graph-search-content: 컨텐츠 카테고리(의미 클러스터) 라벨 — 검색 매칭·랭킹 노출
        cl = _unwrap(row[8])
        if cl:
            d["cluster_label"] = cl
    return d


def _layout_query_variants(query: str) -> list:
    """hangul-qwerty-search: 검색어 원문 + **반대 자판 변환본**(소문자) 후보 목록.

    사용자가 한/영 전환을 잊고 친 그래프 검색어(`tmzlem` → `스키드`)를 흡수한다. 첫 항목이
    항상 원문이라 후보 1개면 종전 동작과 동일하다. 정본은 `shared/hangul_qwerty.py` —
    프론트(`static/hangul-qwerty.js`)·웹 검색 경로와 같은 매핑표를 쓴다.
    """
    try:
        from shared.hangul_qwerty import search_variants
        out = search_variants(query)
    except Exception:
        out = []
    return out or [str(query or "").lower()]


def _analysis_match_keys(cur, query: str, scope: str | None, limit: int, autocommit: bool = True) -> list:
    """AI 능동 분석 본문(node_analysis_jobs.analysis) 부분일치 → 매칭 node_key 목록.

    analysis 텍스트는 AGE 그래프 정점 속성이 아니라 **같은 agent_kb DB 의 관계형 테이블**에 산다
    (feature-0016 §69/ADR-034 — node_analysis_runs/jobs). 검색 커넥션(_ro_conn)이 그 DB 를 가리키므로
    동일 커서로 조회한다. status='done' 만(진행/실패 잡 제외). scope 지정 시 그 datasource 로 한정.
    전부 bind param(injection-safe). position()=LIKE 와일드카드/ESCAPE 없는 대소문자 무관 부분일치.
    analysis 가 text/json/jsonb 어느 저장형이든 ::text 정규화.

    **graceful-degrade 불변(P4 봉인)**: 권한 부재·컬럼 부재·배포 skew(테이블 미존재) 등으로 실패해도
    호출측 검색 본류(같은 커서의 후속 Cypher)를 죽이지 않고 []를 반환한다. autocommit 커넥션이면 실패 문이
    다음 문을 오염시키지 않아 자연 graceful; **non-autocommit** 커넥션이면 실패가 트랜잭션을 abort 시켜
    후속 Cypher 가 InFailedSqlTransaction 으로 죽으므로, SAVEPOINT 로 감싸 실패 시 ROLLBACK TO SAVEPOINT
    로 트랜잭션을 복원한다(본 모듈 `_ro_conn` 및 현행 두 호출처는 autocommit=True 라 SAVEPOINT 미사용)."""
    keys = []
    if not query or len(query) < 2:   # 1자 질의는 분석 본문 전면 매칭(노이즈·풀스캔) — 스킵.
        return keys
    sp = False
    if not autocommit:
        try:
            cur.execute("SAVEPOINT _amk_sp")
            sp = True
        except Exception:
            sp = False
    try:
        # hangul-qwerty-search: 원문 + 반대 자판 변환본(`rmffhqjf` → `글로벌`) 후보를 OR 로.
        #   후보가 1개면 종전 SQL 과 동치라 회귀 0.
        qvs = _layout_query_variants(query)
        params: list = list(qvs)
        pos_sql = " OR ".join(["position(%s in lower(analysis::text)) > 0"] * len(qvs))
        scope_sql = ""
        if scope:
            scope_sql = " AND scope_key = %s"
            params.append(scope)
        params.append(int(limit))
        cur.execute(
            "SELECT DISTINCT node_key FROM node_analysis_jobs "
            "WHERE status = 'done' AND analysis IS NOT NULL "
            "AND (" + pos_sql + ")" + scope_sql + " "
            "LIMIT %s", tuple(params))
        keys = [r[0] for r in cur.fetchall() if r and r[0]]
        if sp:
            try:
                cur.execute("RELEASE SAVEPOINT _amk_sp")
            except Exception:
                pass
    except Exception as exc:
        if sp:   # non-autocommit: 실패 문이 abort 시킨 트랜잭션을 savepoint 로 복원(후속 Cypher 생존).
            try:
                cur.execute("ROLLBACK TO SAVEPOINT _amk_sp")
            except Exception:
                pass
        _log.debug("analysis_match_keys_failed err=%r", exc)
    return keys


def search_nodes(query: str, limit: int = _SEARCH_CAP, scope: str | None = None, conn=None) -> list:
    """노드 부분일치 검색(대소문자 무관). scope 지정 시 해당 datasource 노드만. 8K 규모 보호 cap.

    매칭 대상(graph-search-content, 사용자 요청 — 기존 이름·FQN 에 컨텐츠 카테고리·AI 분석 추가):
      1. n.name / n.fqn              — 테이블·컬럼·용어·스키마·함수/프로시저 이름(기존)
      2. n.semantic_cluster_label    — 컨텐츠 카테고리(§78~81 컨텐츠 단위 그룹 / sim-group LLM 라벨)
      3. node_analysis_jobs.analysis — AI 능동 분석을 통해 얻은 내용(별도 관계형 테이블, key 합류)
    각 노드에 match_via(name|category|analysis, 다중 가능)를 실어 매칭 근거를 노출(프론트 무해·검증용).
    """
    out = []
    if not query:
        return out
    limit = min(int(limit or 50), _SEARCH_CAP)
    # P2 봉인: 후보 풀은 반환 limit 보다 넓게 뜬다(점수 정렬 후 limit 로 재절단 — 아래). 절단이 정렬 이전인
    #   Cypher LIMIT 의 한계(스캔순서 상위 N 만 남김)를 상쇄해 이름-정확 매칭이 category/analysis 에 밀려 탈락 방지.
    fetch_n = max(limit, min(_SEARCH_FETCH_CEIL, limit * 4))
    c, owned = _ro_conn(conn)
    if c is None:
        return out
    try:
        cur = c.cursor()
        _set_age_path(cur)
        # hangul-qwerty-search: 원문 + 반대 자판 변환본 후보(첫 항목이 원문 — 1개면 종전과 동치).
        qvs = _layout_query_variants(query)
        scope_clause = f" AND n.scope_key = {_cq(scope)}" if scope else ""
        # (3) AI 능동 분석 본문 매칭 → node_key 집합(동일 커넥션·별도 테이블). 아래 Cypher 에 key IN 으로 합류.
        analysis_keys = _analysis_match_keys(cur, query, scope, limit,
                                             autocommit=getattr(c, "autocommit", True))
        analysis_set = set(analysis_keys)
        key_clause = ""
        if analysis_keys:
            lits = ", ".join(_cq(k) for k in analysis_keys)
            key_clause = f" OR n.key IN [{lits}]"
        # (1)+(2) 이름/FQN/컨텐츠 카테고리 라벨 CONTAINS. toLower(null)=null 은 OR 에서 무시(비클러스터 노드 안전).
        #   hangul-qwerty-search: 후보마다 세 필드를 OR 로 편다(후보 1개면 종전 절과 문자열 동치).
        name_clause = " OR ".join(
            f"toLower(n.name) CONTAINS {_cq(v)} OR toLower(n.fqn) CONTAINS {_cq(v)} "
            f"OR toLower(n.semantic_cluster_label) CONTAINS {_cq(v)}"
            for v in qvs
        )
        rows = _cypher(cur,
            f"MATCH (n) WHERE (({name_clause}){key_clause}){scope_clause} "
            f"RETURN label(n), n.key, n.name, n.fqn, n.description, n.source, n.ordinal, "
            f"n.routine_type, n.semantic_cluster_label LIMIT {fetch_n}", 9)
        out = [_node_dict(r) for r in rows]
        # 매칭 근거(match_via) — 이름/카테고리는 반환값에서 재확인, 분석은 key 집합으로 판정.
        #   hangul-qwerty-search: 판정도 후보 집합 기준 — 반대 자판으로 매칭된 노드가
        #   match_via 없이 돌아가면 UI 가 "왜 나왔는지" 를 표시하지 못한다.
        for nd in out:
            via = []
            nm_l = (nd.get("name") or "").lower()
            fq_l = (nd.get("fqn") or "").lower()
            cl_l = (nd.get("cluster_label") or "").lower()
            if any((v in nm_l) or (v in fq_l) for v in qvs):
                via.append("name")
            if any(v in cl_l for v in qvs):
                via.append("category")
            if nd.get("key") in analysis_set:
                via.append("analysis")
            if via:
                nd["match_via"] = via
        # feature-0016 graphux5: pg_trgm 실측 유사도 점수(검색어 대비) 부여 + 내림차순 정렬.
        #   name/fqn/컨텐츠 카테고리 라벨의 최대 유사도를 score(0~1)로 실어 UI 가 "검색어와 얼마나 유사한지"를
        #   표시(요청 항목1). analysis-only 매칭은 짧은 유사도 대상이 없어 score≈0 이나 여전히 결과에 포함·글로우.
        #   값은 전부 파라미터 바인딩(injection-safe). pg_trgm 부재/실패 시 score 없이 원순서 반환(graceful).
        if out:
            try:
                rows_sql, vparams = [], []
                for i, nd in enumerate(out):
                    rows_sql.append("(%s::int, %s, %s, %s)")
                    vparams.extend([i, nd.get("name") or "", nd.get("fqn") or "", nd.get("cluster_label") or ""])
                # hangul-qwerty-search: 점수도 **후보 집합의 최댓값**으로 낸다. 원문만으로
                #   채점하면 반대 자판으로 매칭된 노드가 score≈0 이 되어, 아래 정렬 후
                #   `limit` 재절단에서 통째로 탈락한다 — 매칭은 됐는데 결과에서 사라지는
                #   경로다(codex 적대 리뷰 P2). 후보 1개면 종전 식과 동치.
                score_terms = " , ".join(
                    ["GREATEST(similarity(lower(x.nm), lower(%s)), "
                     "similarity(lower(x.fq), lower(%s)), "
                     "similarity(lower(x.cl), lower(%s)))"] * len(qvs)
                )
                score_params: list = []
                for _v in qvs:
                    score_params.extend([_v, _v, _v])
                cur.execute(
                    "SELECT x.i, GREATEST(" + score_terms + ") AS score "
                    "FROM (VALUES " + ",".join(rows_sql) + ") AS x(i, nm, fq, cl)",
                    tuple(score_params + vparams))
                smap = {int(r[0]): float(r[1]) for r in cur.fetchall()}
                for i, nd in enumerate(out):
                    nd["score"] = round(smap.get(i, 0.0), 4)
                out.sort(key=lambda n: (n.get("score") or 0.0), reverse=True)
            except Exception as exc:
                _log.debug("search_nodes_score_failed err=%r", exc)
        # P2 봉인: 넓게 뜬 후보 풀을 (점수 정렬 후) 반환 limit 로 재절단 — 반환 개수 계약 불변, 고점수 매칭 보존.
        #   score 실패로 정렬 못 했어도 limit 로 절단(기존 동작과 동치 degradation).
        if len(out) > limit:
            out = out[:limit]
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


def scope_roots(scope: str, limit: int = 20000, conn=None) -> dict:
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


def scope_schemas(scope: str, limit: int = 20000, conn=None) -> dict:
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


def schema_tables(scope: str, schema_key: str, limit: int = _NEIGHBOR_NODE_CAP, conn=None) -> dict:
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
            # content-cluster RC3: 의미 클러스터도 RETURN — Table(scope_roots/schema_tables) 동형.
            #   0040 미투영 정점은 속성 부재 → agtype null → cluster_id=None(프론트 affix 폴백, 비차단).
            rrows = _cypher(cur,
                f"MATCH (s:Schema)-[:HAS_ROUTINE]->(r:Routine) "
                f"WHERE s.scope_key = {sc} AND s.key = {sk} "
                f"RETURN r.key, r.name, r.fqn, r.description, r.routine_type, r.params, "
                f"r.semantic_cluster_id, r.semantic_cluster_label "
                f"LIMIT {limit}", 8)
            skey0 = None
            for r in rrows:
                rkey = _unwrap(r[0])
                if not rkey:
                    continue
                if rkey not in nodes:
                    nodes[rkey] = {"label": "Routine", "key": rkey, "name": _unwrap(r[1]),
                                   "fqn": _unwrap(r[2]), "description": _unwrap(r[3]),
                                   "source": "routine_introspect",
                                   "routine_type": _unwrap(r[4]), "params": _unwrap(r[5]),
                                   "cluster_id": _unwrap(r[6]), "cluster_label": _unwrap(r[7])}
                if skey0 is None:
                    skey0 = schema_key
                result["edges"].append({"source": skey0, "target": rkey, "type": "HAS_ROUTINE",
                                        "cardinality": None, "edge_source": None})
            if rrows:
                urows = _cypher(cur,
                    f"MATCH (s:Schema)-[:HAS_ROUTINE]->(r:Routine)-[u:ROUTINE_USES]->(t:Table) "
                    f"WHERE s.scope_key = {sc} AND s.key = {sk} "
                    f"RETURN r.key, t.key, u.relation_type, u.cross_ds, u.ref_columns "
                    f"LIMIT {limit * 4}", 5)
                useen = set()
                for ur in urows:
                    rk = _unwrap(ur[0]); tk = _unwrap(ur[1])
                    if not rk or not tk or (rk, tk) in useen:
                        continue
                    useen.add((rk, tk))
                    # §57: cross_ds 를 클러스터 펼침 경로에도 노출 — 크로스 루틴 참조는 same-scope 라
                    #   neighborhood 가 아닌 이 경로로 흐른다(미노출 시 펼침 경로에서 플래그 소실).
                    # routine-column-edges: 참조 컬럼 목록(JSON 문자열)을 파싱해 동봉 — 프론트가
                    #   테이블 펼침 시 사용선을 컬럼별로 분해한다. 부재·파싱 실패는 키 생략(폴백).
                    _e = {"source": rk, "target": tk, "type": "ROUTINE_USES",
                          "cardinality": None, "edge_source": None,
                          "relation_type": _unwrap(ur[2]) or "read",
                          "cross_ds": _unwrap(ur[3])}
                    _rc = _ref_columns_of(_unwrap(ur[4]))
                    if _rc:
                        _e["ref_columns"] = _rc
                    result["edges"].append(_e)
        except Exception as exc:
            _log.debug("schema_tables_routines_failed err=%r", exc)
        # feature-0040: 스키마의 역할 기반 DB 객체(DbObject) 노드 + 관계 엣지도 함께 반환 —
        #   루틴 블록과 같은 자리에서 같은 방식으로 흐른다(프론트가 kind 필터로 역할별 토글).
        #   라벨 부재(0054 미적용 배포)는 except 로 비차단 — 나머지 노드는 정상 반환된다.
        try:
            orows = _cypher(cur,
                f"MATCH (s:Schema)-[:HAS_OBJECT]->(o:DbObject) "
                f"WHERE s.scope_key = {sc} AND s.key = {sk} "
                f"RETURN o.key, o.name, o.fqn, o.description, o.object_role, o.object_type, "
                f"o.owner_object, o.object_attrs, o.semantic_cluster_id, o.semantic_cluster_label "
                f"LIMIT {limit}", 10)
            okey0 = None
            for r in orows:
                okey = _unwrap(r[0])
                if not okey:
                    continue
                if okey not in nodes:
                    nodes[okey] = {"label": "DbObject", "key": okey, "name": _unwrap(r[1]),
                                   "fqn": _unwrap(r[2]), "description": _unwrap(r[3]),
                                   "source": "db_object_introspect",
                                   "object_role": _unwrap(r[4]), "object_type": _unwrap(r[5]),
                                   "owner_object": _unwrap(r[6]), "object_attrs": _unwrap(r[7]),
                                   "cluster_id": _unwrap(r[8]), "cluster_label": _unwrap(r[9])}
                if okey0 is None:
                    okey0 = schema_key
                result["edges"].append({"source": okey0, "target": okey, "type": "HAS_OBJECT",
                                        "cardinality": None, "edge_source": None})
            if orows:
                # OBJECT_USES(정의 참조)와 OBJECT_ON(트리거·별칭의 대상)을 **한 질의로** 받아
                # 엣지 type 으로 구분한다 — 두 번 왕복하면 스키마 펼침 지연이 두 배가 되고,
                # 프론트는 어차피 type 으로 스타일을 가른다.
                erows = _cypher(cur,
                    f"MATCH (s:Schema)-[:HAS_OBJECT]->(o:DbObject)-[u]->(t:Table) "
                    f"WHERE s.scope_key = {sc} AND s.key = {sk} "
                    f"RETURN o.key, t.key, u.relation_type, u.cross_ds, type(u) "
                    f"LIMIT {limit * 4}", 5)
                oseen = set()
                for er in erows:
                    ok = _unwrap(er[0]); tk = _unwrap(er[1]); et = _unwrap(er[4])
                    if not ok or not tk or et not in ("OBJECT_USES", "OBJECT_ON"):
                        continue
                    if (ok, tk, et) in oseen:
                        continue
                    oseen.add((ok, tk, et))
                    result["edges"].append({
                        "source": ok, "target": tk, "type": et,
                        "cardinality": None, "edge_source": None,
                        "relation_type": _unwrap(er[2]) or ("owns" if et == "OBJECT_ON" else "read"),
                        "cross_ds": _unwrap(er[3])})
        except Exception as exc:
            _log.debug("schema_tables_db_objects_failed err=%r", exc)
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


def schema_table_keys(scope: str, schema_key: str, limit: int = 20000, conn=None) -> list:
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


def schema_db_object_keys(scope: str, schema_key: str, limit: int = 20000, conn=None) -> list:
    """스키마 소속 DbObject(뷰·트리거·예약작업·별칭·시퀀스)의 경량 열거 — 능동 분석 시드용.

    `schema_routine_keys` 의 역할-객체 판. 반환 entry 에 `object_role` 을 포함한다 — 분석 페이로드가
    "이건 트리거다/뷰다" 를 알아야 프롬프트가 역할에 맞는 질문을 던진다(테이블 프롬프트를 트리거에
    그대로 쓰면 컬럼·행수 같은 무의미한 항목을 묻게 된다).

    실패/HAS_OBJECT 라벨 부재(0054 미적용) 시 [] 로 저하(비차단 — 스키마 분석이 자연 저하)."""
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
            f"MATCH (s:Schema)-[:HAS_OBJECT]->(o:DbObject) "
            f"WHERE s.scope_key = {_cq(scope)} AND s.key = {_cq(schema_key)} "
            f"RETURN o.key, o.name, o.fqn, o.object_role LIMIT {limit}", 4)
        for r in rows:
            k = _unwrap(r[0])
            if k:
                out.append({"key": k, "name": _unwrap(r[1]) or k, "fqn": _unwrap(r[2]) or "",
                            "object_role": _unwrap(r[3]) or ""})
        cur.close()
    except Exception as exc:
        _log.debug("schema_db_object_keys_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return out


def schema_routine_keys(scope: str, schema_key: str, limit: int = 20000, conn=None) -> list:
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
    elif label == "DbObject":   # feature-0040: 역할·구체타입·대상·역할별 속성(상세 패널·kind 필터)
        d["object_role"] = props.get("object_role")
        d["object_type"] = props.get("object_type")
        d["owner_object"] = props.get("owner_object")
        d["object_attrs"] = props.get("object_attrs")
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
    상수로 순회(gid 는 정확히 한 라벨 테이블에만 속함).

    **truncated (detail-db-groups, 2026-07-27)**: 이웃 노드가 `_NEIGHBOR_NODE_CAP` 에 걸려 BFS 가
    끊기면 `result["truncated"] = True` 를 세팅한다. 종전엔 이 경로만 플래그를 세팅하지 않아
    (scope_schemas/schema_tables 는 세팅) 상세 패널이 **부분 이웃을 전체로 오인 표시**했다 — 프론트가
    상한 절단을 사용자에게 명시하려면 이 신호가 필요하다(무음 절단 제거).

    **예산 우선순위 (graph-hop-budget, 2026-07-28)**: cap 은 유지하되 *무엇을 남길지* 를 의미로 정한다.
    2-hop 이상에서는 관계 엣지(`_REL_ELABELS`) 이웃에 예산을 먼저 배정하고 계층 엣지(`_HIER_ELABELS`)
    이웃은 남는 예산으로만 채운다. 같은 등급 안에서는 `_NEIGHBOR_LABEL_PRIORITY`(Table > Column >
    Routine > …), tie-break 은 graphid 라 같은 앵커·같은 depth 면 항상 같은 부분집합이 나온다.
    도입 근거(실측): 종전 절단 순서는 vertex 라벨 알파벳 순이라 Table 이 맨 뒤 → 2-hop 예산이 같은
    스키마의 형제 Routine 으로 소진되고 정작 참조로 이어지는 테이블이 탈락, 컬럼 투영 테이블 40개
    표본에서 2-hop 절단 50% · "3-hop 이 2-hop 과 완전 동일" 50% 였다(= 3-hop 선택이 무의미).

    **절단 신호 세분화**: `truncated`(bool, 기존 계약 불변) 외에 `truncated_hop`(몇 번째 hop 에서
    끊겼는지, 1-based / None) · `omitted_nodes`(예산 부족으로 버린 이웃 수 하한) 를 함께 반환한다.
    프론트가 "무엇이 잘렸는지" 를 정확히 말할 수 있어야 절단 경고를 엉뚱한 섹션(앵커 직결 목록은
    1-hop 에서 전량 수집되므로 절단과 무관)에 붙이지 않는다."""
    result = {"nodes": [], "edges": [], "truncated": False,
              "truncated_hop": None, "omitted_nodes": 0,
              # 적대리뷰 R2-c: hop 별로 **새로 들어온 노드 수**. 프론트가 "선택한 깊이가 결과를 바꿨는가" 를
              #   응답 엣지 존재 여부로 추측하면 틀린다(hop 1 에 관계 엣지가 있으면 2-hop 이 아무것도 더하지
              #   못해도 힌트가 숨는다). 확장 실적을 백엔드가 직접 보고한다. expanded_hops[i] = i+1 번째
              #   hop 에서 추가된 노드 수.
              "expanded_hops": [],
              # 적대리뷰 R3-b: hop 별 **신규 엣지 수**. 노드가 안 늘어도 이미 발견된 노드 사이에 엣지가
              #   추가될 수 있으므로(자기참조 컬럼 쌍 등), 노드 델타만으로 "확장할 관계 없음" 을 단정하면
              #   틀린다. 프론트는 노드·엣지 실적이 **모두** 0 이고 절단도 없을 때만 힌트를 띄운다.
              "expanded_hop_edges": []}
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
            if len(seen_nodes) >= _NEIGHBOR_NODE_CAP:
                result["truncated"] = True   # cap 도달로 남은 hop 미탐색 — 부분 이웃임을 프론트에 알린다
                if result["truncated_hop"] is None:
                    result["truncated_hop"] = _hop + 1
                break
            if not frontier:
                break
            _nodes_before_hop = len(seen_nodes)   # 적대리뷰 R2-c: 이번 hop 의 확장 실적 계산 기준점
            _edges_before_hop = len(result["edges"])   # 적대리뷰 R3-b: 엣지 실적도 함께 본다
            farr = _gid_array(frontier)
            # (2) 프론티어에 걸린 엣지를 엣지 라벨 UNION ALL 로 1왕복 수집(방향=start->end 보존).
            #   graph-hop-budget(2026-07-28): **1-hop 은 전 라벨, 2-hop 이상은 관계 엣지만** 따라간다.
            #   계층 엣지(HAS_*)를 2-hop 에서 따라가면 "앵커와 같은 스키마에 있다" 는 이유만으로 형제
            #   수백 개가 쏟아져(실측: 형제 Routine 258 또는 형제 Table 258) cap 300 을 소진하고, 그 결과
            #   ① 정작 참조로 이어지는 노드가 탈락 ② 3-hop 이 2-hop 과 동일해져 선택이 무의미해졌다.
            #   앵커 자신의 컬럼·소속 스키마·직결 루틴은 1-hop 에서 전량 수집되므로 상세 패널 정보는 불변.
            #   (형제 목록 자체가 필요한 화면은 scope_schemas/schema_tables 경로가 담당한다.)
            hop_elabels = elabels if _hop == 0 else [et for et in elabels if et in _REL_ELABELS]
            if not hop_elabels:
                break
            # 적대리뷰 R2-b: 종전엔 UNION ALL 에 `LIMIT` 만 붙여, 포화 시 **어떤 부분집합이 오는지 비결정적**
            #   이었다(ORDER BY 부재 — PG 가 임의 순서 반환 가능). 그러면 "관계 우선 · 결정론적 부분집합"
            #   이라는 본 cycle 의 계약이 정작 예산이 빠듯한 상황에서 거짓이 된다. 항마다 관계/계층 등급을
            #   리터럴로 실어 `ORDER BY prio, s, e` 로 자른다 — 포화해도 관계 엣지가 먼저 살아남고, 같은
            #   입력이면 항상 같은 부분집합이 온다.
            #   적대리뷰 R3-d: `broken`(파단) 행을 **cap 적용 이전** 에 후순위로 밀어야 한다 — Python 쪽
            #     `is_rel` 필터는 LIMIT 이 이미 자른 뒤에 돌기 때문에, stale broken 행이 fetch cap 을 채우면
            #     유효 REFERENCES/ROUTINE_USES 가 아예 고려조차 안 된다. WHERE 로 배제하지 않고 **정렬 키**
            #     로만 내리는 이유: agtype 식이 예상과 다르게 동작해도(NULL 등) 행이 *사라지지는* 않는
            #     fail-safe 방향이기 때문(정렬만 열화). 컨테이너 테스트로는 실 SQL 을 못 돌리므로 안전측 선택.
            #     정렬 키 순서는 `brk` 가 `prio` **앞**이다(R4-b) — 뒤에 두면 broken 관계행(prio 0, brk 1)이
            #     유효 계층행(prio 1, brk 0)을 앞질러 fetch 예산을 먹고, Python 이 곧 버릴 행이 유효 이웃을 가린다.
            #   적대리뷰 R3-a: 포화 판정은 **cap+1 fetch** 로 한다 — 정확히 cap 개일 때는 생략된 행이 있다는
            #     증거가 없는데도 종전 `>= cap` 조건이 절단 경고를 띄웠다(경계에서 거짓 양성).
            _brk = "CASE WHEN properties @> '{\"status\": \"broken\"}'::ag_catalog.agtype THEN 1 ELSE 0 END"
            edge_sql = ("SELECT s, e, p, et FROM (" + " UNION ALL ".join(
                f'SELECT start_id::text AS s, end_id::text AS e, properties::text AS p, \'{et}\' AS et, '
                f'{0 if et in _REL_ELABELS else 1} AS prio, {_brk} AS brk '
                f'FROM metadata_kb."{et}" WHERE start_id = ANY({farr}) OR end_id = ANY({farr})'
                for et in hop_elabels)
                + f") u ORDER BY u.brk, u.prio, u.s, u.e LIMIT {_EDGE_FETCH_CAP + 1}")
            cur.execute(edge_sql)
            _edge_rows = cur.fetchall()
            # graph-hop-budget 적대리뷰 P2: 위 UNION 의 전역 LIMIT 은 **우선순위 정렬 이전**에 잘리므로,
            #   프론티어의 엣지가 LIMIT 을 넘으면 뒤쪽 REFERENCES/ROUTINE_USES 가 조용히 탈락한다. 종전엔
            #   `truncated` 를 노드 cap 도달에만 세팅해 **부분 그래프를 truncated=false 로 반환**했고, 그러면
            #   프론트의 "아래 직접 연결 목록은 전량" 고지가 거짓이 된다. LIMIT 포화를 절단으로 신고한다.
            if len(_edge_rows) > _EDGE_FETCH_CAP:      # cap+1 번째 행이 왔다 = 실제로 더 있다
                _edge_rows = _edge_rows[:_EDGE_FETCH_CAP]
                result["truncated"] = True
                if result["truncated_hop"] is None:
                    result["truncated_hop"] = _hop + 1
            edge_hits = []   # (start_gid, end_gid, etype, cardinality, edge_source, weight, status)
            neigh_gids = set()
            rel_gids = set()    # graph-hop-budget: 관계(의미) 엣지로 도달한 미해소 이웃 — 예산 1순위
            for s, e, pr, et in _edge_rows:
                sg = int(s); eg = int(e); ep = json.loads(pr) if pr else {}
                # weight/status(feature-0016): REFERENCES 엣지 강화상태 투영 — UI 신뢰/추정/파단 구분.
                # relation_type: RELATED_TERM(유사어)·ROUTINE_USES(read/write, graph-funcproc) 공용.
                edge_hits.append((sg, eg, et, ep.get("cardinality"), ep.get("source"),
                                  ep.get("weight"), ep.get("status"), ep.get("relation_type"),
                                  ep.get("cross_ds"),   # crossds-rel: 교차DB 엣지 표식
                                  ep.get("ref_columns")))   # routine-column-edges: 참조 컬럼 목록
                # 적대리뷰 R2-a: `broken`(파단) 엣지는 (4) 에서 버려지므로 그 끝점에 관계 우선권을 주면
                #   **무효 이웃이 cap 을 먹고 유효 테이블·컬럼을 밀어낸다**(sync 창 사이에 stale 로 남는다).
                #   버릴 엣지는 우선순위 풀에서도 빼야 예산 배정이 실제 표시분과 일치한다.
                is_rel = et in _REL_ELABELS and ep.get("status") != "broken"
                if sg not in gid2key:
                    neigh_gids.add(sg)
                    if is_rel:
                        rel_gids.add(sg)
                if eg not in gid2key:
                    neigh_gids.add(eg)
                    if is_rel:
                        rel_gids.add(eg)
            # (3) 신규 이웃 graphid 해소 — vertex 라벨 UNION ALL 로 1왕복.
            #   graph-hop-budget(2026-07-28): 종전엔 fetch 순서(라벨 알파벳 순)대로 cap 까지 채워 절단이
            #   임의였다(Table 이 알파벳 맨 뒤 = 가장 먼저 탈락). 이제 전량 fetch 후 **결정론적 우선순위**
            #   로 정렬해 cap 까지 채운다:
            #     ① 관계 엣지 이웃(rel_gids) 우선, 계층 이웃은 남는 예산 — 1-hop 에서도 적용.
            #     ② 같은 등급 안에서는 _NEIGHBOR_LABEL_PRIORITY (Table > Column > Routine > …).
            #     ③ tie-break = graphid — 같은 앵커·같은 depth 면 항상 같은 부분집합(재현 가능).
            next_frontier = []
            new_col_gids = []   # graph-hop-budget: 이번 hop 에 새로 들어온 Column — (3b) 부모 보강 대상
            if neigh_gids:
                narr = _gid_array(neigh_gids)
                resolve_sql = " UNION ALL ".join(
                    f'SELECT id::text AS gid, properties::text AS p, \'{lbl}\' AS lbl '
                    f'FROM metadata_kb."{lbl}" WHERE id = ANY({narr})'
                    for lbl in vlabels)
                cur.execute(resolve_sql)
                _lbl_rank = {l: i for i, l in enumerate(_NEIGHBOR_LABEL_PRIORITY)}
                cand = []
                for idt, pt, lbl in cur.fetchall():
                    g = int(idt)
                    # 관계 이웃 우선 — 1-hop 에서도 적용된다(테이블 719개 스키마처럼 1-hop 부터 cap 에
                    #   걸리는 앵커에서, 형제 나열보다 실제 참조 관계를 남기는 편이 판독에 유용).
                    tier = 0 if g in rel_gids else 1
                    cand.append((tier, _lbl_rank.get(lbl, len(_lbl_rank)), g, pt, lbl))
                cand.sort(key=lambda x: (x[0], x[1], x[2]))
                # 적대리뷰 P1: hop ≥ 2 에서 관계로 들어올 Column 이 있으면, 다른 이웃이 예산을 다 먹기 전에
                #   (3b) 부모 Table 보강 몫을 떼어 둔다. 안 떼면 cap 상황에서 부모가 탈락해 그 컬럼이 프론트
                #   렌더에서 드롭되고(colsByTable), "참조로 이어지는 테이블" 이 화면에서 사라진다 — HB.3 이
                #   없애려던 실패가 cap 에서만 되살아나는 우선순위 역전.
                #   예약은 **관계 이웃(tier 0)에도 적용**한다 — 실측 홍수는 계층 엣지뿐 아니라 관계 엣지에서도
                #   온다(앵커를 쓰는 Routine 258건이 ROUTINE_USES = 관계 tier). tier 0 을 면제하면 그 홍수가
                #   그대로 부모 몫을 먹어 P1 이 재발한다. 예약량은 **실제 필요량 상한**(관계 Column 후보 수)로
                #   비례 축소해, 부모가 몇 개 안 필요한 경우 예산을 낭비하지 않는다.
                _rel_col_n = sum(1 for c in cand if c[4] == "Column" and c[0] == 0)
                _reserve = (min(_PARENT_BACKFILL_RESERVE, _rel_col_n)
                            if (_hop >= 1 and "HAS_COLUMN" in elabels) else 0)
                _cap = _NEIGHBOR_NODE_CAP - _reserve
                for _i, (_tier, _rank, g, pt, lbl) in enumerate(cand):
                    if len(seen_nodes) >= _cap:
                        result["truncated"] = True   # 해소 중 cap 도달 — 나머지 이웃과 그 엣지는 생략된다
                        if result["truncated_hop"] is None:
                            result["truncated_hop"] = _hop + 1
                        # 이번 hop 에서 예산 부족으로 버린 이웃 수(하한) — 프론트가 "몇 개 생략" 을 말할 근거.
                        result["omitted_nodes"] += len(cand) - _i
                        break
                    props = json.loads(pt); k = props.get("key")
                    if not k:
                        continue
                    gid2key[g] = k
                    if k not in seen_nodes:
                        seen_nodes[k] = _node_from_props(lbl, props)
                        next_frontier.append(g)
                        # 적대리뷰 R4-a: **관계(비-broken)로 도달한** Column 만 부모 보강 대상이다.
                        #   broken 엣지로 들어온 컬럼까지 보강하면, 곧 버려질 관계 때문에 무관한 부모
                        #   Table 과 합성 HAS_COLUMN 엣지가 2-hop 그래프에 등장하고 "관계 없음" 힌트도
                        #   부당하게 억제된다(sync 창 사이). rel_gids 는 이미 broken 을 배제한 집합이다.
                        if lbl == "Column" and g in rel_gids:
                            new_col_gids.append(g)
            # (3b) graph-hop-budget: 관계로 새로 들어온 **Column 의 소속 Table 보강**.
            #   REFERENCES 는 Column↔Column 이라, 참조 대상 컬럼만 넣으면 프론트가 그 컬럼을 렌더에서
            #   드롭한다(graph-core.js 의 colsByTable 은 부모 Table 이 모델에 있을 때만 자식을 담는다) —
            #   즉 "참조로 이어지는 다른 테이블" 이 화면에 나타나지 않는다. 소속 Table 을 HAS_COLUMN
            #   역참조로 해소해 채운다(키 문자열 파싱이 아니라 엣지 역참조 — 테이블명에 dot 이 있어도 정확).
            #   **다음 프론티어에는 넣지 않는다** — 넣으면 그 테이블의 형제 컬럼/루틴이 다시 폭발한다.
            if _hop >= 1 and new_col_gids and "HAS_COLUMN" in elabels:
                carr = _gid_array(new_col_gids)
                # 적대리뷰 R3-c: 예약 예산보다 필요한 부모가 많으면 어느 부모가 살아남는지가 DB 반환 순서에
                #   좌우돼(ORDER BY 부재) 같은 앵커·같은 depth 가 서로 다른 부분그래프를 낸다 — 문서화한
                #   graphid tie-break 계약 위반. 두 쿼리 모두 graphid 순으로 고정한다.
                cur.execute(f'SELECT DISTINCT start_id::text FROM metadata_kb."HAS_COLUMN" '
                            f'WHERE end_id = ANY({carr}) ORDER BY start_id::text')
                parent_gids = [int(r[0]) for r in cur.fetchall() if int(r[0]) not in gid2key]
                if parent_gids:
                    parr = _gid_array(parent_gids)
                    cur.execute(f'SELECT id::text, properties::text FROM metadata_kb."Table" '
                                f'WHERE id = ANY({parr}) ORDER BY id')
                    _prows = cur.fetchall()
                    for _pi, (idt, pt) in enumerate(_prows):
                        if len(seen_nodes) >= _NEIGHBOR_NODE_CAP:
                            # 예약분(_PARENT_BACKFILL_RESERVE)까지 소진 — 남은 부모는 못 넣는다. 그 부모에
                            #   달린 컬럼은 프론트에서 보이지 않으므로 생략 수에 반영해 무음 손실을 없앤다.
                            result["truncated"] = True
                            if result["truncated_hop"] is None:
                                result["truncated_hop"] = _hop + 1
                            result["omitted_nodes"] += len(_prows) - _pi
                            break
                        g = int(idt); props = json.loads(pt); k = props.get("key")
                        if not k:
                            continue
                        gid2key[g] = k
                        if k not in seen_nodes:
                            seen_nodes[k] = _node_from_props("Table", props)
                    # 보강된 부모와 자식 컬럼을 잇는 HAS_COLUMN 엣지도 실어야 프론트가 소속을 안다.
                    cur.execute(f'SELECT start_id::text, end_id::text FROM metadata_kb."HAS_COLUMN" '
                                f'WHERE end_id = ANY({carr})')
                    for s, e in cur.fetchall():
                        edge_hits.append((int(s), int(e), "HAS_COLUMN",
                                          None, None, None, None, None, None, None))
            # (4) 엣지 빌드 — 양 끝점이 해소된 것만, 방향(source=start,target=end) + dedup.
            for sg, eg, et, card, esrc, ewgt, estatus, erel, exds, erc in edge_hits:
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
                _e = {"source": sk, "target": tk, "type": et,
                      "cardinality": card, "edge_source": esrc,
                      "weight": ewgt, "status": estatus,
                      "relation_type": erel,
                      "cross_ds": exds}   # crossds-rel: 프론트 교차DB 엣지 스타일/배지
                _rc = _ref_columns_of(erc)   # routine-column-edges: 컬럼 승격 입력(부재=테이블 폴백)
                if _rc:
                    _e["ref_columns"] = _rc
                result["edges"].append(_e)
            # schema_tables REFERENCES emit 도 cross_ds 를 실어야 하나, 그 경로는 단일 스키마(intra-ds)라 cross_ds 부재(생략 안전).
            # 적대리뷰 R2-c: 이번 hop 이 실제로 노드를 몇 개 늘렸는지 기록 — 0 이면 그 깊이는 결과를 바꾸지
            #   못했다는 뜻이고, 프론트가 그 사실을 사용자에게 정직하게 알린다.
            result["expanded_hops"].append(len(seen_nodes) - _nodes_before_hop)
            result["expanded_hop_edges"].append(len(result["edges"]) - _edges_before_hop)
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
