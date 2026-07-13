"""feature-0016 Phase C (ADR-013 후속) + content-cluster (TASK 20260713T1059): 메타데이터 객체
(테이블 + 함수·프로시저) 의미 임베딩·클러스터링.

ADR-013 의 프론트 affix 휴리스틱을 대체·보강하는 **서버측 의미 클러스터**. 객체별 시그니처 텍스트를
기존 `texts` 저장소에 적재하면(dedup by sha256) 기존 embedding 데몬(kb_embedding_worker)이 bge-m3
1024d 로 자동 임베딩한다. 여기서는 (1) 시그니처 백필과 (2) 클러스터링만 수행하고, 결과
(semantic_cluster_id/label)를 rag_objects·routine_objects 에 역기록한다.

content-cluster 재작업(RC1~RC5 진단, unit TASK 20260713T1059):
  - **DB(effective schema) 단위 분할 클러스터링**: 종전 (scope, datasource) 전역 단위는 표시 단위
    (그래프 스키마 클러스터 내부 sim-group)와 불일치 + 대형 ds(7,055 테이블)가 FULLMATRIX_MAX_N 에
    걸려 통째 skip 됐다(RC2). DB 별로 나누면 N 이 수백 수준이라 실동작한다. cluster id 는
    스키마-로컬 순번(§18.8 패널 m5 — 프론트 그룹 키가 스키마 네임스페이스라 전역 유일성 불필요,
    전역 순번은 스키마 간 id-shift churn 유발).
  - **루틴(함수·프로시저) 합동 편입**(RC3): routine_objects 도 시그니처(이름+파라미터+반환형+참조
    테이블+능동 분석문) 임베딩 → 같은 DB 의 테이블과 **하나의 id 공간**에서 합동 클러스터링 —
    루틴이 자기가 만지는 테이블과 같은 컨텐츠 그룹으로 묶인다(alembic 0040).
  - **능동 분석문(node_analysis) 시그니처 주입**(RC4): 'AI 능동 분석' 완료 노드는 분석 summary+usage
    를 시그니처에 포함 — 분석 실행 → 해시 변경 → 재임베딩 → 재클러스터의 인과가 성립한다.
    analysis 줄은 **비어있지 않을 때만 append** — 미분석 객체의 해시는 불변(재임베딩 blast-radius 를
    분석 보유분으로 한정, AGENTS §12.3 2차-효과 비용).
  - **LLM 컨텐츠 라벨**(RC5): 클러스터 라벨을 이름 affix 스템 대신 멤버 이름+분석 요약 기반 한국어
    컨텐츠 명(예: "몬스터 스폰")으로 — llm.llm_cluster_label(fail-soft, kv 캐시 멤버셋-해시 키,
    AGENT_METADATA_CLUSTER_LABEL_LLM 게이트). 실패/비활성 시 affix 폴백.

설계 원칙(metadata_graph.py·relationships.py 동형):
  - 연결: shared.db._pg_connect(autocommit) RW / _pg_connect_ro() RO. PG 미가용·예외 시 no-op(비차단).
  - 의존성: numpy (requirements 하드 dep — RC1: 종전 requirements 부재로 전면 무산, 부재 시 1회
    WARNING fail-loud).
  - MSSQL DB-distinct: 시그니처 텍스트에 object_key 유래 effective schema(DB명)를 포함 → 다중 DB 동명
    테이블(dbo.T)의 시그니처·해시가 DB별로 구분(verify MAJOR — 다중 DB 오염 차단).
  - chaining 억제: 노드당 kNN 이웃 상한(MAX_DEGREE)로 단일연결 폭주 방지(verify MAJOR).
  - 멱등·결정론: signature_text_hash 는 시그니처의 sha256(변경 없으면 no-op). cluster_id 는 스키마
    사전순 → 멤버 min(key) 순 스키마-로컬 결정 배정. 재실행 시 임베딩 불변이면 동일 결과(LLM 라벨은
    표시 전용 + 멤버셋-해시 kv 캐시라 멤버 불변이면 재호출 없이 동일).
"""
from __future__ import annotations

import hashlib
import json
import logging

from shared import config as _cfg
from .utils import _text_hash, _text_store_insert

_log = logging.getLogger("semantic_cluster")

_NUMPY_WARNED = {"done": False}
_ROUTINE_COLS_WARNED = {"done": False}


# ── 연결 헬퍼 (metadata_graph.py 동형) ─────────────────────────────────────
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


def _effective_schema(datasource_key, object_key, schema_name):
    """object_key(`<ds>:db.dbo.table` = 3+ 세그먼트)에서 effective schema(=DB명)를 유도.

    MSSQL 은 schema_name 이 리터럴 'dbo'라 DB 차원이 소실 → object_key 의 DB명을 쓴다(metadata_graph._rag_effective 동형).
    MySQL 은 object_key `<ds>:db.table`(2 세그먼트)이라 schema_name 과 동일. 파싱 불가 시 schema_name fallback.
    """
    ok = object_key or ""
    pref = f"{datasource_key or ''}:"
    if ok.startswith(pref):
        ok = ok[len(pref):]
    parts = [p for p in ok.split(".") if p] if ok else []
    if len(parts) >= 3:
        return parts[0]          # db.schema.table → db
    if len(parts) == 2:
        return parts[0]          # db.table → db
    return schema_name or ""


# ── 시그니처 텍스트 (결정론) ───────────────────────────────────────────────
_ANALYSIS_SIG_MAX = 400   # 시그니처에 넣는 분석문(summary+usage) 상한 — 임베딩 토큰 보호


def build_table_signature_text(eff_schema, table_name, description, columns, entity_type, domain,
                               analysis="") -> str:
    """테이블 시그니처 = 이름 + 설명 + 역할/도메인 + 정렬 컬럼명 (+ 능동 분석문). 결정론(해시 안정) — DB-distinct.

    analysis(content-cluster RC4): node_analysis 최신 done 의 summary+usage. **비어있지 않을 때만**
    줄을 추가한다 — 미분석 테이블의 시그니처·해시는 종전과 byte-동일(재임베딩 무발생, 무회귀)."""
    cols = ", ".join(columns or [])
    sig = (
        f"table: {eff_schema}.{table_name}\n"
        f"description: {str(description or '').strip()}\n"
        f"role: {str(entity_type or '').strip()} domain: {str(domain or '').strip()}\n"
        f"columns: {cols}"
    )
    a = str(analysis or "").strip()
    if a:
        sig += f"\nanalysis: {a[:_ANALYSIS_SIG_MAX]}"
    return sig


def build_routine_signature_text(eff_schema, name, routine_type, params, returns, touches,
                                 analysis="") -> str:
    """루틴 시그니처 = 이름 + 유형 + 파라미터 + 반환형 + 참조 테이블(read/write) (+ 능동 분석문).

    touches = routine_objects.referenced_tables ([{fqn, kind}]) — introspect 순서 그대로(결정론:
    routines.py 가 정의 파싱 순으로 저장·IS DISTINCT FROM 가드로 불변). 컨텐츠 신호의 핵심은
    참조 테이블(같은 컨텐츠의 테이블과 어휘 공유)과 분석문이다(RC3·RC4)."""
    tparts = []
    for t in (touches or []):
        fqn = str((t or {}).get("fqn") or "").strip()
        if not fqn:
            continue
        tparts.append(f"{str((t or {}).get('kind') or 'read').strip()} {fqn}")
    sig = (
        f"routine: {eff_schema}.{name}()\n"
        f"type: {str(routine_type or 'procedure').strip()}\n"
        f"params: {str(params or '').strip()}\n"
        f"returns: {str(returns or '').strip()}\n"
        f"touches: {', '.join(tparts)}"
    )
    a = str(analysis or "").strip()
    if a:
        sig += f"\nanalysis: {a[:_ANALYSIS_SIG_MAX]}"
    return sig


def _fetch_columns(cur, scope_key, schema_name, table_name) -> list:
    """(scope_key, schema_name, table_name) 의 컬럼명(ordinal 순). rag_objects 와 동일 키로 소싱(정합)."""
    try:
        cur.execute(
            "SELECT column_name FROM column_descriptions "
            "WHERE scope_key = %s AND schema_name = %s AND table_name = %s "
            "ORDER BY ordinal NULLS LAST, column_name",
            (scope_key, schema_name or "", table_name),
        )
        return [str(r[0]) for r in cur.fetchall() if r and r[0]]
    except Exception:
        return []


def _fetch_table_desc(cur, scope_key, schema_name, table_name) -> str:
    try:
        cur.execute(
            "SELECT description FROM table_descriptions "
            "WHERE scope_key = %s AND schema_name = %s AND table_name = %s LIMIT 1",
            (scope_key, schema_name or "", table_name),
        )
        r = cur.fetchone()
        return str(r[0]) if r and r[0] else ""
    except Exception:
        return ""


def _fetch_analysis_text(cur, scope_key, datasource_key, node_key) -> str:
    """node_analysis_jobs 최신 done 분석의 summary+usage — 시그니처의 컨텐츠 신호(RC4).

    node_key = 그래프 노드 키(`<ds>:<eff_schema>.<name>` / Routine 은 `...()`) —
    cc_data_main 실측 테이블 255/255·루틴 300/300 매칭(ix_node_analysis_jobs_node_lookup).
    **scope 차원(§18.8 패널 n4 — 라이브 확증)**: node_analysis_jobs.scope_key 는 웹 트리거가
    datasource_key 를 넣는다(라이브 실측 — rag 의 'common' 과 다름; 'common' 필터는 매칭 0).
    양쪽 값 모두 인정(ANY) — 인덱스 (scope_key,node_key,status) 2-probe. 동률 tie-break 는
    id DESC(패널 n2 — updated_at 동률 시 비결정 픽 방지). 분석 부재/파싱 실패 → ""(시그니처 불변). fail-soft."""
    scopes = sorted({s for s in (str(scope_key or ""), str(datasource_key or "")) if s})
    if not scopes:
        return ""
    try:
        cur.execute(
            "SELECT analysis FROM node_analysis_jobs "
            "WHERE scope_key = ANY(%s) AND node_key = %s AND status = 'done' AND analysis IS NOT NULL "
            "ORDER BY updated_at DESC, id DESC LIMIT 1",
            (scopes, node_key),
        )
        r = cur.fetchone()
        if not r or not r[0]:
            return ""
        obj = r[0]
        if isinstance(obj, (str, bytes)):
            obj = json.loads(obj)
        if not isinstance(obj, dict):
            return ""
        parts = [str(obj.get("summary") or "").strip(), str(obj.get("usage") or "").strip()]
        return " ".join(p for p in parts if p)[:_ANALYSIS_SIG_MAX]
    except Exception:
        return ""


# ── (1) 시그니처 백필 ──────────────────────────────────────────────────────
def run_signature_backfill_pass(max_rows=None, conn=None) -> dict:
    """rag_objects(table) + routine_objects 행의 시그니처 텍스트를 texts 에 적재하고 signature_text_hash 를 set.

    변경 감지: 새로 계산한 sha256 이 저장된 signature_text_hash 와 다를 때만 texts upsert + UPDATE(멱등).
    texts 적재분은 기존 embedding 데몬이 임베딩(신규 embedding 호출 없음). fail-soft, 부분 카운트 반환.
    max_rows 는 kind 별(테이블/루틴) 각각 적용 — 기존 배치 상한 의미 보존."""
    rep = {"processed": 0, "changed": 0, "failed": 0, "error": None, "remaining": 0,
           "analysis_fresh": 0,
           "routine_processed": 0, "routine_changed": 0, "routine_failed": 0, "routine_remaining": 0,
           "routine_analysis_fresh": 0}
    c, owned = _rw_conn(conn)
    if c is None:
        return rep
    try:
        cur = c.cursor()
        limit = ""
        args = ["table"]
        if max_rows and int(max_rows) > 0:
            # §55 D(REQ-20260706 ④) 정체 근본수정: 기존 `updated_at DESC LIMIT N` 은 **미처리
            # (hash NULL) 행을 우선하지 않아**, 이미 처리된 최신 N 행을 매 pass 재스캔·no-op 하며
            # 백로그가 영구 미소진됐다(라이브 실측 2026-07-06: 16,023 중 497=3% 에서 정체).
            # 미처리 행 우선 + 그 다음 최근 변경분(설명·분석 갱신 시 updated_at 전진 → 변경감지 재계산) 순.
            limit = (" ORDER BY (signature_text_hash IS NULL OR signature_text_hash = '') DESC, "
                     "updated_at DESC NULLS LAST LIMIT %s")
            args.append(int(max_rows))
        cur.execute(
            "SELECT id, scope_key, datasource_key, schema_name, table_name, object_key, "
            "signature_text_hash, category_entity_type, category_domain "
            "FROM rag_objects WHERE object_type = %s AND table_name <> ''" + limit,
            tuple(args),
        )
        rows = cur.fetchall()
        # §18.8 패널 M1(RC4 도달성): 분석이 새로 완료돼도 rag 행 updated_at 은 전진하지 않아,
        # 백로그 0 정상 상태에서 top-N 창 밖의 분석-보유 행이 영구히 구 시그니처로 남는다.
        # 최신 done 분석(j.updated_at)이 행(o.updated_at)보다 새 행을 표적 선별해 합류시키고,
        # 처리 시 updated_at 을 명시 touch 해 조건을 해소한다(멱등 — 다음 pass 재선별 없음).
        fresh_ids = set()
        try:
            cur.execute("SAVEPOINT sc_fresh_tbl")
        except Exception:
            pass
        try:
            cur.execute(
                "SELECT id, scope_key, datasource_key, schema_name, table_name, object_key, "
                "signature_text_hash, category_entity_type, category_domain "
                "FROM rag_objects o WHERE o.object_type = 'table' AND o.table_name <> '' "
                "AND o.datasource_key <> '' AND EXISTS (SELECT 1 FROM node_analysis_jobs j "
                "WHERE j.scope_key = ANY(ARRAY[o.scope_key, o.datasource_key]) AND j.status = 'done' "
                "AND j.node_key = o.datasource_key || ':' || "
                "split_part(replace(o.object_key, o.datasource_key || ':', ''), '.', 1) "
                "|| '.' || o.table_name AND j.updated_at > o.updated_at) LIMIT %s",
                (int(max_rows) if (max_rows and int(max_rows) > 0) else 500,),
            )
            seen = {r[0] for r in rows}
            fresh_rows = [r for r in cur.fetchall() if r[0] not in seen]
            fresh_ids = {r[0] for r in fresh_rows}
            rep["analysis_fresh"] = len(fresh_ids)
            rows = list(rows) + fresh_rows
            try:
                cur.execute("RELEASE SAVEPOINT sc_fresh_tbl")
            except Exception:
                pass
        except Exception:
            # node_analysis 미구성 환경 — 표적 선별만 생략(주 백필 불변). SAVEPOINT 로 tx 오염 차단.
            try:
                cur.execute("ROLLBACK TO SAVEPOINT sc_fresh_tbl")
                cur.execute("RELEASE SAVEPOINT sc_fresh_tbl")
            except Exception:
                pass
        for (rid, scope, dsk, sch, tbl, okey, cur_hash, etype, domain) in rows:
            rep["processed"] += 1
            try:
                eff = _effective_schema(dsk, okey, sch)
                cols = _fetch_columns(cur, scope, sch, tbl)
                desc = _fetch_table_desc(cur, scope, sch, tbl)
                # content-cluster RC4: 그래프 노드 키(`<ds>:<eff>.<table>`)로 최신 done 분석문 소싱.
                ana = _fetch_analysis_text(cur, scope, dsk, f"{dsk}:{eff}.{tbl}") if dsk else ""
                sig = build_table_signature_text(eff, tbl, desc, cols, etype, domain, analysis=ana)
                # 리뷰 MAJOR-1: _text_store_insert 가 내부에서 sig.strip() 후 해시하므로 write-key 도 반드시
                #   strip 후 해시해야 texts join-key 와 일치한다(컬럼 없는 테이블의 trailing space 로 divergence → 영구 미클러스터 방지).
                h = _text_hash(sig.strip())
                if h == (cur_hash or "").strip():
                    if rid in fresh_ids:
                        # M1: 분석은 새로우나 시그니처 불변(요약 동일) — touch 로 표적 조건 해소(재선별 차단).
                        cur.execute("UPDATE rag_objects SET updated_at = now() WHERE id = %s", (rid,))
                    continue   # 변경 없음 — no-op
                _text_store_insert(None, sig)   # texts upsert(dedup, 내부 strip → _text_hash(sig.strip())==h) → embedding 데몬이 임베딩
                cur.execute("UPDATE rag_objects SET signature_text_hash = %s, updated_at = now() "
                            "WHERE id = %s", (h, rid))
                rep["changed"] += 1
            except Exception as exc:
                rep["failed"] += 1
                rep["error"] = str(exc)[:200]
        # §55 D 관측성: 잔여 미처리(hash 미설정) 카운트 — 진행이 로그에서 단조 감소로 보이게(정체 재발 감지).
        try:
            cur.execute("SELECT COUNT(*) FROM rag_objects WHERE object_type = %s AND table_name <> '' "
                        "AND (signature_text_hash IS NULL OR signature_text_hash = '')", ("table",))
            rep["remaining"] = int((cur.fetchone() or [0])[0])
        except Exception:
            pass
        # content-cluster RC3: 루틴(함수·프로시저) 시그니처 백필 — 0040 미적용 창은 1회 경고 후 skip.
        _routine_signature_backfill(cur, rep, max_rows)
        if rep["changed"] or rep["remaining"] or rep["routine_changed"] or rep["routine_remaining"]:
            _log.info("signature_backfill processed=%s changed=%s failed=%s remaining=%s "
                      "routine_processed=%s routine_changed=%s routine_failed=%s routine_remaining=%s",
                      rep["processed"], rep["changed"], rep["failed"], rep["remaining"],
                      rep["routine_processed"], rep["routine_changed"], rep["routine_failed"],
                      rep["routine_remaining"])
        cur.close()
    except Exception as exc:
        _log.warning("signature_backfill 실패: %r", exc)
        rep["error"] = str(exc)[:200]
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return rep


def _routine_signature_backfill(cur, rep, max_rows) -> None:
    """routine_objects 시그니처 백필(테이블 패스와 동형 — 미처리 우선·변경감지·멱등, RC3).

    컬럼 부재(alembic 0040 미적용 창)는 전체 backfill 을 죽이지 않고 1회 WARNING 후 skip.
    SAVEPOINT 격리 — caller 가 non-autocommit conn 을 주입해도 실패 SELECT 가 tx 를 aborted 로
    남기지 않게(클러스터 pass 의 routine fetch 와 동형·라이브 프로브 적발). fail-soft."""
    try:
        cur.execute("SAVEPOINT sc_routine_backfill")
    except Exception:
        pass
    try:
        limit = ""
        args = []
        if max_rows and int(max_rows) > 0:
            limit = (" ORDER BY (signature_text_hash IS NULL OR signature_text_hash = '') DESC, "
                     "updated_at DESC NULLS LAST LIMIT %s")
            args.append(int(max_rows))
        cur.execute(
            "SELECT id, scope_key, datasource_key, schema_name, routine_name, routine_type, "
            "params, returns, referenced_tables, signature_text_hash "
            "FROM routine_objects WHERE routine_name <> ''" + limit,
            tuple(args),
        )
        rows = cur.fetchall()
        # §18.8 패널 M1(RC4 도달성) — 테이블 패스 동형: 최신 done 분석이 행보다 새 루틴을 표적 합류.
        #   (외곽 sc_routine_backfill SAVEPOINT 가 아직 열려 있어 실패 시 아래 except 로 합류·격리.)
        fresh_ids = set()
        cur.execute(
            "SELECT id, scope_key, datasource_key, schema_name, routine_name, routine_type, "
            "params, returns, referenced_tables, signature_text_hash "
            "FROM routine_objects r WHERE r.routine_name <> '' AND r.datasource_key <> '' "
            "AND EXISTS (SELECT 1 FROM node_analysis_jobs j "
            "WHERE j.scope_key = ANY(ARRAY[r.scope_key, r.datasource_key]) AND j.status = 'done' "
            "AND j.node_key = r.datasource_key || ':' || r.schema_name || '.' || r.routine_name || '()' "
            "AND j.updated_at > r.updated_at) LIMIT %s",
            (int(max_rows) if (max_rows and int(max_rows) > 0) else 500,),
        )
        seen = {r[0] for r in rows}
        fresh_rows = [r for r in cur.fetchall() if r[0] not in seen]
        fresh_ids = {r[0] for r in fresh_rows}
        rep["routine_analysis_fresh"] = len(fresh_ids)
        rows = list(rows) + fresh_rows
        try:
            cur.execute("RELEASE SAVEPOINT sc_routine_backfill")
        except Exception:
            pass
    except Exception as exc:
        try:
            cur.execute("ROLLBACK TO SAVEPOINT sc_routine_backfill")
            cur.execute("RELEASE SAVEPOINT sc_routine_backfill")   # 패널 n3: 실패 서브tx 잔존 방지
        except Exception:
            pass
        if not _ROUTINE_COLS_WARNED["done"]:
            _ROUTINE_COLS_WARNED["done"] = True
            _log.warning("routine 시그니처 백필 skip(0040 미적용 창?): %r", exc)
        return
    for (rid, scope, dsk, sch, name, rtype, params, returns, refs, cur_hash) in rows:
        rep["routine_processed"] += 1
        try:
            if isinstance(refs, (str, bytes)):
                refs = json.loads(refs or "[]")
            touches = refs if isinstance(refs, list) else []
            # routine_objects.schema_name 은 그래프 스키마 라벨(MSSQL=DB명 lower, §56·§58)과 동일 —
            # effective schema 재유도 불요, node_key 도 같은 라벨로 조립.
            ana = _fetch_analysis_text(cur, scope, dsk, f"{dsk}:{sch}.{name}()") if dsk else ""
            sig = build_routine_signature_text(sch or "", name, rtype, params, returns, touches,
                                               analysis=ana)
            h = _text_hash(sig.strip())
            if h == (cur_hash or "").strip():
                if rid in fresh_ids:
                    cur.execute("UPDATE routine_objects SET updated_at = now() WHERE id = %s", (rid,))
                continue
            _text_store_insert(None, sig)
            cur.execute("UPDATE routine_objects SET signature_text_hash = %s, updated_at = now() "
                        "WHERE id = %s", (h, rid))
            rep["routine_changed"] += 1
        except Exception as exc:
            rep["routine_failed"] += 1
            rep["error"] = str(exc)[:200]
    try:
        cur.execute("SELECT COUNT(*) FROM routine_objects WHERE routine_name <> '' "
                    "AND (signature_text_hash IS NULL OR signature_text_hash = '')")
        rep["routine_remaining"] = int((cur.fetchone() or [0])[0])
    except Exception:
        pass


# ── (2) 클러스터링 ─────────────────────────────────────────────────────────
def _cluster_edges(embeddings, tau=None) -> list:
    """임베딩 리스트 → 무향 **mutual-kNN** 엣지 [(i,j)]. numpy N×N 코사인(대형 스키마는 caller 가 N 가드 분기).

    단일연결 chaining 억제 2중: ① 노드당 상위 MAX_DEGREE 이웃 중 τ 이상 ② **상호(mutual) top-k 만
    엣지 채택** — 라이브 프로브(2026-07-13)에서 단방향 kNN + union-find 가 cc_data_main 255 테이블을
    단일 254-멤버 blob 으로 연쇄 병합(시그니처 boilerplate 공유로 baseline 유사도가 높음)한 것의 1차
    방어. 잔여 거대 컴포넌트는 _adaptive_components 의 τ-상승 재분할이 2차 방어. L2 정규화 후 내적 = 코사인.
    """
    n = len(embeddings)
    if n < 2:
        return []
    if tau is None:
        tau = float(_cfg.AGENT_METADATA_CLUSTER_SIM_THRESHOLD)
    max_deg = max(1, int(_cfg.AGENT_METADATA_CLUSTER_MAX_DEGREE))
    try:
        import numpy as np
    except Exception:
        # content-cluster RC1 fail-loud: 종전 silent [] 반환이 "cadence 는 돌지만 클러스터 0건" 을
        # 은폐했다(라이브 실측 2026-07-13 — requirements 에 numpy 자체가 없었음). 1회 WARNING.
        if not _NUMPY_WARNED["done"]:
            _NUMPY_WARNED["done"] = True
            _log.warning("numpy 미설치 — 의미 클러스터링 전면 무산(affix 폴백). "
                         "requirements.txt(numpy) / 이미지 재빌드를 확인하라.")
        return []
    X = np.asarray(embeddings, dtype=np.float32)
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    X = X / norms
    S = X @ X.T                      # 코사인 유사도 행렬 (N×N)
    np.fill_diagonal(S, -1.0)        # 자기 자신 제외
    k = min(max_deg, n - 1)
    if k <= 0:
        return []
    topk = []                        # 노드별 top-k 이웃 집합(τ 이상만)
    for i in range(n):
        row = S[i]
        idx = np.argpartition(row, -k)[-k:]
        topk.append({int(j) for j in idx if int(j) != i and float(row[int(j)]) >= tau})
    edges = []
    for i in range(n):
        for j in topk[i]:
            if j > i and i in topk[j]:   # mutual — 양방향 top-k 일 때만(비대칭 허브 연쇄 차단)
                edges.append((i, j))
    return edges


def _adaptive_components(embs, member_idx, tau, cap, *, step=0.02, ceiling=0.98) -> list:
    """거대 컴포넌트 적응 재분할(divisive) — 컴포넌트가 cap 초과면 τ 를 올려 그 멤버들만 재클러스터.

    라이브 프로브 적발: 같은 DB 테이블은 시그니처 구조 공유로 baseline 코사인이 높아 base τ 에서
    스키마 전체가 한 blob 이 된다(cc_data_main 254/255 — 밴드로 무용). τ 를 step 씩 올리며 재귀
    분할하고, ceiling 에서도 안 쪼개지는 컴포넌트는 진성 동질(샤드 등)로 보고 수용. 결정론(입력
    순서·τ 시퀀스 고정). 반환: member_idx(원본 인덱스) 의 부분집합 리스트."""
    if len(member_idx) < 2:
        return [list(member_idx)]
    sub = [embs[i] for i in member_idx]
    roots = _union_find(len(sub), _cluster_edges(sub, tau=tau))
    comp = {}
    for local_i, r in enumerate(roots):
        comp.setdefault(r, []).append(member_idx[local_i])
    out = []
    for members in comp.values():
        if len(members) > cap and tau + step <= ceiling:
            out.extend(_adaptive_components(embs, members, round(tau + step, 4), cap,
                                            step=step, ceiling=ceiling))
        else:
            out.append(members)
    return out


def _union_find(n, edges) -> list:
    """union-find → 각 노드의 component 대표(root) 리스트."""
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return [find(i) for i in range(n)]


def _label_cluster(names) -> str:
    """commonAffix 서버 포트(admin.js _metaSimFamilies 동형): 최장 공통 접두/접미(≥4자) 스템, 없으면 최빈 토큰/최단명."""
    def norm(s):
        s = str(s or "").strip().lower()
        return s[5:] if s.startswith("view_") else s
    ms = [norm(x) for x in names if x]
    if not ms:
        return ""
    # 최장 공통 접두
    pre = ms[0]
    for s in ms[1:]:
        i = 0
        while i < len(pre) and i < len(s) and pre[i] == s[i]:
            i += 1
        pre = pre[:i]
        if not pre:
            break
    # 최장 공통 접미
    suf = ms[0]
    for s in ms[1:]:
        i = 0
        while i < len(suf) and i < len(s) and suf[-1 - i] == s[-1 - i]:
            i += 1
        suf = suf[len(suf) - i:] if i else ""
        if not suf:
            break
    cand = pre if len(pre) >= len(suf) else suf
    if len(cand) >= 4:
        lab = (cand + "…") if cand == pre else ("…" + cand)
        return lab[:128]
    # 폴백: 최빈 ≥4자 토큰(구분자 분할), 없으면 최단 멤버명
    from collections import Counter
    toks = Counter()
    import re as _re
    for s in ms:
        for t in _re.split(r"[^a-z0-9]+", s):
            if len(t) >= 4:
                toks[t] += 1
    if toks:
        return toks.most_common(1)[0][0][:128]
    return min(ms, key=len)[:128]


# ── LLM 컨텐츠 라벨 (content-cluster RC5, fail-soft) ───────────────────────
_LABEL_MAX_CHARS = 32          # 클러스터 라벨 표시 상한(그룹 헤더 칩 폭 규율 — DB 컬럼 128 캡과 별개)
_LABEL_MEMBERS_CAP = 12        # LLM 입력 멤버명 상한(클러스터당)
_LABEL_ANALYSES_CAP = 5        # LLM 입력 분석 요약 상한(클러스터당)
_LABEL_CLUSTERS_PER_CALL = 40  # 호출당 클러스터 배치 상한(토큰 보호)


def _member_set_hash(keys) -> str:
    return hashlib.sha256("\n".join(sorted(str(k) for k in keys)).encode("utf-8")).hexdigest()[:16]


def _kv_get(cur, key) -> str:
    try:
        cur.execute("SELECT value FROM agent_runtime.kv WHERE conversation_id = %s AND key = %s",
                    (_CLUSTER_KV_CONV, key))
        r = cur.fetchone()
        return str(r[0]) if r and r[0] else ""
    except Exception:
        return ""


def _valid_label(lab) -> str:
    """LLM 라벨 위생: 한 줄·공백정리·상한 절단. 부적합 → ""(affix 폴백)."""
    s = " ".join(str(lab or "").split()).strip()
    if not s or len(s) < 2:
        return ""
    return s[:_LABEL_MAX_CHARS]


def _label_ns_hash(datasource_key, eff_schema) -> str:
    """kv 캐시 key 네임스페이스 고정폭 해시(패널 m3) — ds(≤64)+schema(≤256) 원문 조합은 kv.key
    varchar(128)을 초과해 INSERT silent-fail → 캐시 부전 → 매 pass LLM 재호출 누수가 가능했다."""
    return hashlib.sha256(f"{datasource_key}\x1f{eff_schema}".encode("utf-8")).hexdigest()[:12]


def _llm_content_labels(cur, datasource_key, eff_schema, clusters, fetch_summaries=None) -> dict:
    """클러스터별 한국어 컨텐츠 라벨 — kv 캐시(멤버셋 해시) 우선, 미스만 llm.llm_cluster_label 배치 호출.

    clusters: [{"idx": <로컬 idx>, "keys": [...], "names": [...]}] — 분석 요약은 **캐시-미스
    클러스터에 한해** fetch_summaries(cl) 콜백으로 lazy 수집(패널 m2 — 게이트 OFF/전량 캐시 적중 시
    per-member 점조회 0). 반환 {idx: label}. 게이트 OFF/LLM 실패/부적합 라벨 → 해당 idx 미포함
    (caller 가 affix 폴백). 비용 유계: DB 당 캐시-미스 클러스터만, 호출당 40 클러스터 배치. fail-soft."""
    out = {}
    if not getattr(_cfg, "AGENT_METADATA_CLUSTER_LABEL_LLM", True):
        return out
    ns = _label_ns_hash(datasource_key, eff_schema)
    misses = []
    for cl in clusters:
        kv_key = f"label:{ns}:{_member_set_hash(cl['keys'])}"
        cached = _valid_label(_kv_get(cur, kv_key))
        if cached:
            out[cl["idx"]] = cached
        else:
            misses.append((cl, kv_key))
    if not misses:
        return out
    try:
        from . import llm as _llm
    except Exception:
        return out
    for start in range(0, len(misses), _LABEL_CLUSTERS_PER_CALL):
        batch = misses[start:start + _LABEL_CLUSTERS_PER_CALL]
        for (cl, _k) in batch:
            if "summaries" not in cl:
                try:
                    cl["summaries"] = list(fetch_summaries(cl)) if fetch_summaries else []
                except Exception:
                    cl["summaries"] = []
        payload = {
            "task": "cluster_label",
            "datasource": datasource_key,
            "schema": eff_schema,
            "clusters": [
                {"idx": cl["idx"],
                 "members": [str(n)[:80] for n in cl["names"][:_LABEL_MEMBERS_CAP]],
                 "analyses": [str(s)[:160] for s in (cl.get("summaries") or [])[:_LABEL_ANALYSES_CAP]]}
                for (cl, _k) in batch
            ],
        }
        try:
            res = _llm.llm_cluster_label(payload)
        except Exception as exc:
            _log.warning("llm_cluster_label 실패(affix 폴백): %r", exc)
            return out
        labels = (res or {}).get("labels") if isinstance(res, dict) else None
        if not isinstance(labels, list):
            return out
        got = {}
        for item in labels:
            if not isinstance(item, dict):
                continue
            lab = _valid_label(item.get("label"))
            try:
                idx = int(item.get("idx"))
            except Exception:
                continue
            if lab:
                got[idx] = lab
        for (cl, kv_key) in batch:
            lab = got.get(cl["idx"])
            if lab:
                out[cl["idx"]] = lab
                _kv_put(cur, kv_key, lab)   # 멤버셋 불변이면 다음 pass 는 캐시 적중(재호출 0)
    return out


def _parse_embedding(emb):
    """pgvector embedding — str '[...]' 또는 list. 파싱 실패/빈 값 → None(해당 행 제외).

    패널 m4(메모리): 가능하면 float32 ndarray 로 즉시 변환 — 대형 ds(7k×1024d)에서 Python float
    리스트(~230MB transient)를 ~29MB 로 줄인다(insight-worker mem_limit 1g headroom). numpy 부재
    시 리스트 유지(클러스터링은 어차피 _cluster_edges 에서 무산·경고)."""
    if isinstance(emb, str):
        try:
            vec = [float(x) for x in emb.strip("[]").split(",") if x.strip()]
        except Exception:
            return None
    else:
        vec = emb
    if vec is None or len(vec) == 0:
        return None
    try:
        import numpy as np
        return np.asarray(vec, dtype=np.float32)
    except Exception:
        return vec


def run_semantic_cluster_pass(scope_key, datasource_key, conn=None) -> dict:
    """한 scope(scope_key, datasource_key)의 테이블+루틴을 **DB(effective schema) 단위로 분할**
    클러스터링 → rag_objects·routine_objects 역기록.

    (1) 시그니처 임베딩 보유 객체 fetch(테이블 + 루틴 합동, RC3). (2) effective schema 별 그룹 →
    그룹별 kNN + union-find — N > FULLMATRIX_MAX_N 인 **스키마만** skip(종전 ds-전역 skip 의 RC2 를
    국소화: 표시 단위인 스키마 클러스터와 계산 단위 정합). (3) size ≥ MIN_SIZE component →
    cluster_id(스키마-로컬 순번 — 사전순 스키마 → 멤버 min(key) 순 결정 배정; 프론트 그룹 키가 스키마 네임스페이스라 전역 유일성 불필요) + 라벨(LLM 컨텐츠
    라벨 → affix 폴백, RC5). 싱글턴/미충족 → NULL. (4) 변경분만 UPDATE(멱등). skip 스키마의 기존
    배정은 보존. fail-soft."""
    rep = {"scope": scope_key, "objects": 0, "clusters": 0, "updated": 0,
           "schemas": 0, "skipped_schemas": 0, "error": None}
    c, owned = _rw_conn(conn)
    if c is None:
        return rep
    try:
        cur = c.cursor()
        items = []   # {kind, id, key, name, emb, cur_cid, cur_lab, schema}
        cur.execute(
            "SELECT o.id, o.object_key, o.table_name, t.embedding, o.semantic_cluster_id, "
            "o.semantic_cluster_label, o.schema_name "
            "FROM rag_objects o JOIN texts t ON o.signature_text_hash = t.text_hash "
            "WHERE o.object_type = 'table' AND o.scope_key = %s AND o.datasource_key = %s "
            "AND o.signature_text_hash IS NOT NULL AND t.embedding IS NOT NULL",
            (scope_key, datasource_key),
        )
        for (rid, okey, tbl, emb, ccid, clab, sch) in cur.fetchall():
            vec = _parse_embedding(emb)
            if vec is None:
                continue
            eff = _effective_schema(datasource_key, okey, sch)
            items.append({"kind": "table", "id": rid, "key": okey or "", "name": tbl or "",
                          "emb": vec, "cur_cid": ccid, "cur_lab": clab, "schema": eff})
        # 루틴 합동 편입(RC3) — 0040 미적용 창/컬럼 부재는 1회 경고 후 테이블만 클러스터.
        # SAVEPOINT 격리(라이브 프로브 적발): caller 가 non-autocommit conn 을 주입하면 실패 SELECT 가
        # 트랜잭션을 aborted 로 남겨 이후 UPDATE 전부 InFailedSqlTransaction 으로 연쇄 실패한다.
        # autocommit(기본 경로)에서는 SAVEPOINT 자체가 실패하지만 무해(try 로 삼킴 — 동작 종전과 동일).
        try:
            cur.execute("SAVEPOINT sc_routine_fetch")
        except Exception:
            pass
        try:
            # h1(라이브 실증 적발): routine_objects.scope_key 는 datasource_key(node_analysis_jobs
            # 와 동일 비대칭 — n4 클래스)라 'common' 스코프 필터는 0-match(루틴 전량 미합류).
            # datasource_key 등가가 실질 파티션이므로 scope 필터를 제거한다(백필 쿼리와 동형).
            cur.execute(
                "SELECT r.id, r.schema_name, r.routine_name, t.embedding, r.semantic_cluster_id, "
                "r.semantic_cluster_label "
                "FROM routine_objects r JOIN texts t ON r.signature_text_hash = t.text_hash "
                "WHERE r.datasource_key = %s "
                "AND r.signature_text_hash IS NOT NULL AND t.embedding IS NOT NULL",
                (datasource_key,),
            )
            for (rid, sch, name, emb, ccid, clab) in cur.fetchall():
                vec = _parse_embedding(emb)
                if vec is None:
                    continue
                items.append({"kind": "routine", "id": rid,
                              "key": f"{datasource_key}:{sch}.{name}()", "name": f"{name}()",
                              "emb": vec, "cur_cid": ccid, "cur_lab": clab, "schema": sch or ""})
            try:
                cur.execute("RELEASE SAVEPOINT sc_routine_fetch")
            except Exception:
                pass
        except Exception as exc:
            try:
                cur.execute("ROLLBACK TO SAVEPOINT sc_routine_fetch")
                cur.execute("RELEASE SAVEPOINT sc_routine_fetch")   # 패널 n3: 실패 서브tx 잔존 방지
            except Exception:
                pass
            if not _ROUTINE_COLS_WARNED["done"]:
                _ROUTINE_COLS_WARNED["done"] = True
                _log.warning("routine 클러스터 fetch skip(0040 미적용 창?): %r", exc)
        rep["objects"] = len(items)
        min_size = max(2, int(_cfg.AGENT_METADATA_CLUSTER_MIN_SIZE))
        if len(items) < min_size:
            cur.close()
            return rep
        # ── DB(effective schema) 단위 분할 (RC2) ──
        by_schema = {}
        for i, it in enumerate(items):
            by_schema.setdefault(it["schema"], []).append(i)
        maxn = int(_cfg.AGENT_METADATA_CLUSTER_FULLMATRIX_MAX_N)
        assign = {}          # 전역 item index → (cid, label)
        total_clusters = 0
        skipped_idx = set()  # skip 스키마 멤버(기존 배정 보존)
        # 스키마 순회는 사전순(lexicographic — 패널 n1 표기 정정) 결정론. cluster id 는 **스키마-로컬
        # 순번**(패널 m5): 프론트 그룹 키가 스키마 네임스페이스(nsKey)라 전역 유일성이 불필요하고,
        # 전역 순번은 앞 스키마의 증감이 뒤 전체 id 를 shift 시켜 대량 UPDATE·재투영 churn 을 만든다.
        for eff in sorted(by_schema.keys()):
            idxs = by_schema[eff]
            rep["schemas"] += 1
            if len(idxs) < min_size:
                continue   # 미달 스키마 → 전원 미클러스터(NULL 회수 대상)
            if len(idxs) > maxn:
                # 단일 DB 가 초대형인 예외만 skip — float32 N×N 메모리 가드(리뷰 MINOR-3)는 유지하되
                # 종전 ds-전역 통째 skip 을 스키마 국소로 좁힌다(RC2).
                _log.info("semantic_cluster skip(schema=%s:%s): N=%s > FULLMATRIX_MAX_N=%s (affix 폴백)",
                          datasource_key, eff, len(idxs), maxn)
                rep["skipped_schemas"] += 1
                skipped_idx.update(idxs)
                continue
            # mutual-kNN + 거대 컴포넌트 적응 재분할(τ 상승) — 라이브 프로브에서 base τ 단일연결이
            # 스키마 전체(254/255)를 한 blob 으로 만들던 chaining 의 방어(상세 _adaptive_components).
            cap = max(min_size, int(getattr(_cfg, "AGENT_METADATA_CLUSTER_MAX_SIZE", 40)))
            base_tau = float(_cfg.AGENT_METADATA_CLUSTER_SIM_THRESHOLD)
            embs_all = [it["emb"] for it in items]
            comps = _adaptive_components(embs_all, idxs, base_tau, cap)
            valid = [(min(items[i]["key"] for i in members), members)
                     for members in comps if len(members) >= min_size]
            valid.sort(key=lambda x: x[0])
            # 라벨: affix 기본 + LLM 컨텐츠 라벨(캐시·fail-soft) override — 분석 요약은 캐시-미스
            # 클러스터에 한해 lazy 수집(패널 m2: 게이트 OFF/전량 적중 시 per-member 점조회 0).
            label_inputs = []
            for local_idx, (_key, members) in enumerate(valid):
                label_inputs.append({"idx": local_idx, "_members": members, "_eff": eff,
                                     "keys": [items[i]["key"] for i in members],
                                     "names": [items[i]["name"] for i in members]})

            def _summaries_for(cl):
                summaries = []
                for i in cl.get("_members") or []:
                    if len(summaries) >= _LABEL_ANALYSES_CAP:
                        break
                    nk = (items[i]["key"] if items[i]["kind"] == "routine"
                          else f"{datasource_key}:{cl.get('_eff')}.{items[i]['name']}")
                    s = _fetch_analysis_text(cur, scope_key, datasource_key, nk)
                    if s:
                        summaries.append(s)
                return summaries
            llm_labels = _llm_content_labels(cur, datasource_key, eff, label_inputs,
                                             fetch_summaries=_summaries_for)
            for local_idx, (_key, members) in enumerate(valid):
                label = llm_labels.get(local_idx) or _label_cluster([items[i]["name"] for i in members])
                for i in members:
                    assign[i] = (local_idx, label)   # 스키마-로컬 id(m5)
            total_clusters += len(valid)
        rep["clusters"] = total_clusters
        # 역기록: 변경분만 UPDATE (싱글턴/미클러스터 → NULL 회수, skip 스키마는 보존).
        for i, it in enumerate(items):
            if i in skipped_idx:
                continue
            new_cid, new_lab = assign.get(i, (None, None))
            if new_cid == it["cur_cid"] and (new_lab or None) == (it["cur_lab"] or None):
                continue
            table = "rag_objects" if it["kind"] == "table" else "routine_objects"
            cur.execute(
                f"UPDATE {table} SET semantic_cluster_id = %s, semantic_cluster_label = %s WHERE id = %s",
                (new_cid, new_lab, it["id"]),
            )
            rep["updated"] += 1
        cur.close()
    except Exception as exc:
        _log.warning("semantic_cluster_pass(%s) 실패: %r", scope_key, exc)
        rep["error"] = str(exc)[:200]
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return rep


# ── cadence (PG agent_runtime.kv — metadata_graph watermark 동형) ──────────
_CLUSTER_KV_CONV = "__semantic_cluster__"


def _cadence_due(cur, key, sec) -> bool:
    """scope 재클러스터가 due 한지(최근 sec 초 내 실행 기록 없으면 due). kv 부재/실패 → due(안전: 실행)."""
    try:
        cur.execute(
            "SELECT 1 FROM agent_runtime.kv WHERE conversation_id = %s AND key = %s "
            "AND updated_at > now() - make_interval(secs => %s)",
            (_CLUSTER_KV_CONV, key, int(sec)),
        )
        return cur.fetchone() is None
    except Exception:
        return True


def _kv_put(cur, key, value) -> None:
    try:
        cur.execute(
            "INSERT INTO agent_runtime.kv (conversation_id, key, value, updated_at) "
            "VALUES (%s, %s, %s, now()) "
            "ON CONFLICT (conversation_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
            (_CLUSTER_KV_CONV, key, str(value)[:256]),
        )
    except Exception:
        pass


def _cadence_mark(cur, key) -> None:
    _kv_put(cur, key, "1")


def run_cluster_maintenance(conn=None) -> dict:
    """Phase C 유지보수 1회: (1) 시그니처 백필 + (2) scope 별 cadence-gated 클러스터링. 단일 RW conn 재사용.

    embedding 은 별도 embedding 데몬이 처리(여기 없음). fail-soft. insight-worker 데몬 스레드가 주기 호출."""
    rep = {"signature": None, "scopes": 0, "clustered": 0, "updated": 0}
    c, owned = _rw_conn(conn)
    if c is None:
        return rep
    try:
        rep["signature"] = run_signature_backfill_pass(
            max_rows=_cfg.AGENT_METADATA_CLUSTER_SIG_BATCH_MAX_ROWS, conn=c)
        scopes = list_cluster_scopes(conn=c)
        rep["scopes"] = len(scopes)
        rsec = int(_cfg.AGENT_METADATA_CLUSTER_RECOMPUTE_SEC)
        cur = c.cursor()
        try:
            for (scope, dsk) in scopes:
                key = f"cluster_at:{scope}:{dsk}"
                if not _cadence_due(cur, key, rsec):
                    continue
                r = run_semantic_cluster_pass(scope, dsk, conn=c)
                _cadence_mark(cur, key)
                rep["updated"] += int(r.get("updated") or 0)
                if r.get("clusters"):
                    rep["clustered"] += 1
        finally:
            cur.close()
    except Exception as exc:
        _log.warning("run_cluster_maintenance 실패: %r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return rep


def list_cluster_scopes(conn=None) -> list:
    """클러스터 대상 (scope_key, datasource_key) 쌍 — table 객체가 있는 scope. verify MINOR: run_insight_cycle 의
    단일-ds 스키마 루프 대신 rag_objects 에서 직접 enumerate(전 scope 커버)."""
    out = []
    c, owned = _ro_conn(conn)
    if c is None:
        return out
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT DISTINCT scope_key, datasource_key FROM rag_objects "
            "WHERE object_type = 'table' AND datasource_key <> ''"
        )
        out = [(str(r[0]), str(r[1])) for r in cur.fetchall() if r and r[0] is not None]
        cur.close()
    except Exception as exc:
        _log.warning("list_cluster_scopes 실패: %r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return out
