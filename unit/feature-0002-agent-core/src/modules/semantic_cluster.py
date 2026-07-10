"""feature-0016 Phase C (ADR-013 후속): 메타데이터 객체(테이블) 의미 임베딩·클러스터링.

ADR-013 의 프론트 affix 휴리스틱을 대체·보강하는 **서버측 의미 클러스터**. 테이블별 시그니처 텍스트
(테이블명+설명+컬럼명+역할/도메인)를 기존 `texts` 저장소에 적재하면(dedup by sha256) 기존 embedding
데몬(kb_embedding_worker)이 bge-m3 1024d 로 자동 임베딩한다. 여기서는 (1) 시그니처 백필과 (2) scope 별
kNN+union-find 클러스터링만 수행하고, 결과(semantic_cluster_id/label)를 rag_objects 에 역기록한다.

설계 원칙(metadata_graph.py·relationships.py 동형):
  - 연결: shared.db._pg_connect(autocommit) RW / _pg_connect_ro() RO. PG 미가용·예외 시 no-op(비차단).
  - 의존성: numpy 만(pgvector 하드 dep 으로 이미 존재). sklearn/scipy 불요.
  - MSSQL DB-distinct: 시그니처 텍스트에 object_key 유래 effective schema(DB명)를 포함 → 다중 DB 동명
    테이블(dbo.T)의 시그니처·해시가 DB별로 구분(verify MAJOR — 다중 DB 오염 차단).
  - chaining 억제: 노드당 kNN 이웃 상한(MAX_DEGREE)로 단일연결 폭주 방지(verify MAJOR).
  - 멱등·결정론: signature_text_hash 는 시그니처의 sha256(변경 없으면 no-op). cluster_id 는 멤버 min(object_key)
    순 결정 배정. 재실행 시 임베딩 불변이면 동일 결과.
"""
from __future__ import annotations

import logging

from shared import config as _cfg
from .utils import _text_hash, _text_store_insert

_log = logging.getLogger("semantic_cluster")


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
def build_table_signature_text(eff_schema, table_name, description, columns, entity_type, domain) -> str:
    """테이블 시그니처 = 이름 + 설명 + 역할/도메인 + 정렬 컬럼명. 결정론(해시 안정) — DB-distinct(eff_schema 포함)."""
    cols = ", ".join(columns or [])
    return (
        f"table: {eff_schema}.{table_name}\n"
        f"description: {str(description or '').strip()}\n"
        f"role: {str(entity_type or '').strip()} domain: {str(domain or '').strip()}\n"
        f"columns: {cols}"
    )


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


# ── (1) 시그니처 백필 ──────────────────────────────────────────────────────
def run_signature_backfill_pass(max_rows=None, conn=None) -> dict:
    """object_type='table' rag_objects 행의 시그니처 텍스트를 texts 에 적재하고 signature_text_hash 를 set.

    변경 감지: 새로 계산한 sha256 이 저장된 signature_text_hash 와 다를 때만 texts upsert + UPDATE(멱등).
    texts 적재분은 기존 embedding 데몬이 임베딩(신규 embedding 호출 없음). fail-soft, 부분 카운트 반환."""
    rep = {"processed": 0, "changed": 0, "failed": 0, "error": None, "remaining": 0}
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
            # 미처리 행 우선 + 그 다음 최근 변경분(설명 갱신 시 updated_at 전진 → 변경감지 재계산) 순.
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
        for (rid, scope, dsk, sch, tbl, okey, cur_hash, etype, domain) in rows:
            rep["processed"] += 1
            try:
                eff = _effective_schema(dsk, okey, sch)
                cols = _fetch_columns(cur, scope, sch, tbl)
                desc = _fetch_table_desc(cur, scope, sch, tbl)
                sig = build_table_signature_text(eff, tbl, desc, cols, etype, domain)
                # 리뷰 MAJOR-1: _text_store_insert 가 내부에서 sig.strip() 후 해시하므로 write-key 도 반드시
                #   strip 후 해시해야 texts join-key 와 일치한다(컬럼 없는 테이블의 trailing space 로 divergence → 영구 미클러스터 방지).
                h = _text_hash(sig.strip())
                if h == (cur_hash or "").strip():
                    continue   # 변경 없음 — no-op
                _text_store_insert(None, sig)   # texts upsert(dedup, 내부 strip → _text_hash(sig.strip())==h) → embedding 데몬이 임베딩
                cur.execute("UPDATE rag_objects SET signature_text_hash = %s WHERE id = %s", (h, rid))
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
        if rep["changed"] or rep["remaining"]:
            _log.info("signature_backfill processed=%s changed=%s failed=%s remaining=%s",
                      rep["processed"], rep["changed"], rep["failed"], rep["remaining"])
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


# ── (2) 클러스터링 ─────────────────────────────────────────────────────────
def _cluster_edges(embeddings) -> list:
    """임베딩 리스트 → 무향 kNN 엣지 [(i,j)]. numpy(소형) 또는 pgvector-less 순수 numpy kNN(대형은 caller 가 분기).

    단일연결 chaining 억제: 노드당 상위 MAX_DEGREE 이웃만(코사인 τ 이상). L2 정규화 후 내적 = 코사인.
    """
    n = len(embeddings)
    if n < 2:
        return []
    tau = float(_cfg.AGENT_METADATA_CLUSTER_SIM_THRESHOLD)
    max_deg = max(1, int(_cfg.AGENT_METADATA_CLUSTER_MAX_DEGREE))
    try:
        import numpy as np
    except Exception:
        return []   # numpy 부재(이론상 없음) — 클러스터링 skip(프론트 affix 폴백)
    X = np.asarray(embeddings, dtype=np.float32)
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    X = X / norms
    S = X @ X.T                      # 코사인 유사도 행렬 (N×N)
    np.fill_diagonal(S, -1.0)        # 자기 자신 제외
    edges = set()
    for i in range(n):
        row = S[i]
        # 노드 i 의 상위 max_deg 이웃 중 τ 이상만(chaining 억제 + O(N) per-row).
        k = min(max_deg, n - 1)
        if k <= 0:
            continue
        idx = np.argpartition(row, -k)[-k:]
        for j in idx:
            j = int(j)
            if j == i:
                continue
            if float(row[j]) >= tau:
                a, b = (i, j) if i < j else (j, i)
                edges.add((a, b))
    return list(edges)


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


def run_semantic_cluster_pass(scope_key, datasource_key, conn=None) -> dict:
    """한 scope(scope_key, datasource_key)의 table 객체를 임베딩 유사도로 클러스터링 → rag_objects 역기록.

    (1) signature_text_hash→texts join 으로 임베딩 보유 table 후보 fetch. (2) kNN 엣지 + union-find.
    (3) size ≥ MIN_SIZE component → cluster_id(멤버 min(object_key) 순) + commonAffix 라벨. 싱글턴/미충족 → NULL.
    (4) 변경분만 UPDATE(멱등). fail-soft."""
    rep = {"scope": scope_key, "objects": 0, "clusters": 0, "updated": 0, "error": None}
    c, owned = _rw_conn(conn)
    if c is None:
        return rep
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT o.id, o.object_key, o.table_name, t.embedding, o.semantic_cluster_id, o.semantic_cluster_label "
            "FROM rag_objects o JOIN texts t ON o.signature_text_hash = t.text_hash "
            "WHERE o.object_type = 'table' AND o.scope_key = %s AND o.datasource_key = %s "
            "AND o.signature_text_hash IS NOT NULL AND t.embedding IS NOT NULL",
            (scope_key, datasource_key),
        )
        rows = cur.fetchall()
        rep["objects"] = len(rows)
        if len(rows) < max(2, int(_cfg.AGENT_METADATA_CLUSTER_MIN_SIZE)):
            cur.close()
            return rep
        ids, okeys, names, embs, cur_cid, cur_lab = [], [], [], [], [], []
        for (rid, okey, tbl, emb, ccid, clab) in rows:
            # pgvector embedding 은 str '[...]' 또는 list 로 올 수 있음 — 파싱.
            vec = emb
            if isinstance(emb, str):
                try:
                    vec = [float(x) for x in emb.strip("[]").split(",") if x.strip()]
                except Exception:
                    continue
            if not vec:
                continue
            ids.append(rid); okeys.append(okey or ""); names.append(tbl or ""); embs.append(vec)
            cur_cid.append(ccid); cur_lab.append(clab)
        if len(embs) < 2:
            cur.close()
            return rep
        # 리뷰 MINOR-3: numpy N×N 코사인 행렬 메모리 가드 — 초대형 scope(N > FULLMATRIX_MAX_N)는 클러스터링 skip
        #   (float32 N×N: 2000²=16MB, 8000²=256MB → OOM 위험). skip 시 그 scope 는 프론트 affix 폴백. 로그로 관측.
        maxn = int(_cfg.AGENT_METADATA_CLUSTER_FULLMATRIX_MAX_N)
        if len(embs) > maxn:
            _log.info("semantic_cluster skip(scope=%s): N=%s > FULLMATRIX_MAX_N=%s (affix 폴백)", scope_key, len(embs), maxn)
            rep["error"] = f"scope too large (N={len(embs)} > {maxn}) — clustering skipped"
            cur.close()
            return rep
        edges = _cluster_edges(embs)
        roots = _union_find(len(embs), edges)
        # component → 멤버 인덱스
        comp = {}
        for i, r in enumerate(roots):
            comp.setdefault(r, []).append(i)
        min_size = max(2, int(_cfg.AGENT_METADATA_CLUSTER_MIN_SIZE))
        # cluster_id 결정 배정: component 를 멤버 min(object_key) 로 정렬 → 안정 id.
        valid = [(min(okeys[i] for i in members), members) for members in comp.values() if len(members) >= min_size]
        valid.sort(key=lambda x: x[0])
        assign = {}   # index → (cid, label)
        for cid, (_key, members) in enumerate(valid):
            label = _label_cluster([names[i] for i in members])
            for i in members:
                assign[i] = (cid, label)
        rep["clusters"] = len(valid)
        # 역기록: 변경분만 UPDATE (싱글턴/미클러스터 → NULL 로 되돌림).
        for i in range(len(ids)):
            new_cid, new_lab = assign.get(i, (None, None))
            if new_cid == cur_cid[i] and (new_lab or None) == (cur_lab[i] or None):
                continue
            cur.execute(
                "UPDATE rag_objects SET semantic_cluster_id = %s, semantic_cluster_label = %s WHERE id = %s",
                (new_cid, new_lab, ids[i]),
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


def _cadence_mark(cur, key) -> None:
    try:
        cur.execute(
            "INSERT INTO agent_runtime.kv (conversation_id, key, value, updated_at) "
            "VALUES (%s, %s, %s, now()) "
            "ON CONFLICT (conversation_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
            (_CLUSTER_KV_CONV, key, "1"),
        )
    except Exception:
        pass


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
