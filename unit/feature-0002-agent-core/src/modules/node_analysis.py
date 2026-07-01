"""feature-0016 graphux5: 그래프 노드 AI 능동 분석 — 재귀 탐색 + 백그라운드 처리.

관리콘솔 그래프뷰 상세 패널의 "AI 능동 분석" 버튼이 `enqueue_analysis()` 로 run 을 만들고 루트 노드를
pending 잡으로 넣는다. insight-worker 틱이 `process_pending()` 으로 pending 잡을 소량씩 소비하며(부하
분산), 노드마다 이웃 컨텍스트를 모아 LLM 분석문을 생성·저장하고, 방문하지 않은 이웃을 (예산 내)
pending 으로 재큐한다 — 이렇게 **선택 노드에서 시작해 관련 노드를 재귀적으로 탐색**한다.

설계 원칙 (metadata_graph.py 동형):
  - 저장소 = agent_kb PG 의 node_analysis_runs / node_analysis_jobs (alembic 0028).
  - 연결은 shared.db._pg_connect(RW). PG 미가용·예외 시 no-op — 코어 흐름 절대 비차단.
  - **비용 경계(사용자 결정 2026-07-01)**: run 마다 depth_budget/node_budget 로 재귀를 캡하고,
    UNIQUE(run_id,node_key) 로 dedupe 한다. "관련된 모든 노드"의 무한 확장(LLM 비용 폭증) 방지.
  - 그래프 컨텍스트/이웃은 metadata_graph.neighborhood(depth=1) 재사용.
"""
from __future__ import annotations

import json
import logging
import uuid

from shared import config as _cfg

_log = logging.getLogger("node_analysis")


# ── 연결 헬퍼 ────────────────────────────────────────────────────────────────
def _rw_conn(conn):
    if conn is not None:
        return conn, False
    from shared.db import _pg_available, _pg_connect
    if not _pg_available():
        return None, False
    return _pg_connect(autocommit=True), True


def _clamp(v, lo, hi, default):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(n, hi))


def _new_run_id() -> str:
    return uuid.uuid4().hex


# ── 그래프 컨텍스트 수집 (neighborhood 재사용) ────────────────────────────────
def _fetch_context(node_key: str, conn):
    """node_key 중심 1-hop {root, neighbors[], columns[], references[], related_terms[]}.

    root 미발견(그래프에 없는 노드) 시 root=None. worker/enqueue 공용.
    """
    from modules import metadata_graph as _mg
    data = _mg.neighborhood(node_key, depth=1, conn=conn) or {"nodes": [], "edges": []}
    nodes = data.get("nodes") or []
    edges = data.get("edges") or []
    root = None
    for n in nodes:
        if n.get("key") == node_key:
            root = n
            break
    by_key = {n.get("key"): n for n in nodes if n.get("key")}
    columns, references, related_terms, other = [], [], [], []
    for e in edges:
        et = e.get("type")
        if et == "HAS_COLUMN" and e.get("source") == node_key:
            tgt = by_key.get(e.get("target"))
            if tgt:
                columns.append(tgt)
        elif et == "REFERENCES":
            references.append({"from": e.get("source"), "to": e.get("target"),
                               "cardinality": e.get("cardinality")})
    for n in nodes:
        k = n.get("key")
        if k == node_key:
            continue
        if n.get("label") == "GlossaryTerm":
            related_terms.append(n)
        elif n not in columns:
            other.append(n)
    return {"root": root, "neighbors": [n for n in nodes if n.get("key") != node_key],
            "columns": columns, "references": references, "related_terms": related_terms,
            "other": other}


def _build_payload(node: dict, ctx: dict) -> dict:
    """LLM 입력 payload (NODE_ANALYSIS_PROMPT 계약). 이웃 리스트는 cap 으로 토큰 보호."""
    def _names(items, n):
        out = []
        for it in items[:n]:
            nm = it.get("name") or it.get("fqn") or it.get("key")
            desc = (it.get("description") or "").strip()
            out.append({"name": nm, "description": desc[:200]} if desc else {"name": nm})
        return out
    return {
        "label": node.get("label") or "",
        "name": node.get("name") or node.get("fqn") or node.get("key") or "",
        "fqn": node.get("fqn") or "",
        "description": (node.get("description") or "")[:1000],
        "scope_key": (node.get("key") or "").split(":", 1)[0] if node.get("key") else "",
        "neighbors": {
            "columns": _names(ctx.get("columns") or [], 40),
            "references": (ctx.get("references") or [])[:30],
            "related_terms": _names(ctx.get("related_terms") or [], 20),
            "other": _names(ctx.get("other") or [], 20),
        },
    }


# ── enqueue (웹 트리거) ──────────────────────────────────────────────────────
def enqueue_analysis(scope_key: str, node_key: str, depth_budget=None, node_budget=None,
                     requested_by=None, conn=None) -> dict:
    """루트 노드로 분석 run 생성 + 루트 pending 잡 삽입. 반환 {ok, run_id, status, reason?}.

    같은 (scope_key, root_key) 로 진행 중(status='running') run 이 있으면 그 run_id 를 재사용(중복 방지).
    """
    if not _cfg_enabled():
        return {"ok": False, "reason": "disabled"}
    if not node_key:
        return {"ok": False, "reason": "node_key 필수"}
    depth_budget = _clamp(depth_budget if depth_budget is not None else _cfg.AGENT_NODE_ANALYSIS_DEFAULT_DEPTH,
                          1, _cfg.AGENT_NODE_ANALYSIS_MAX_DEPTH, _cfg.AGENT_NODE_ANALYSIS_DEFAULT_DEPTH)
    node_budget = _clamp(node_budget if node_budget is not None else _cfg.AGENT_NODE_ANALYSIS_DEFAULT_BUDGET,
                         1, _cfg.AGENT_NODE_ANALYSIS_MAX_BUDGET, _cfg.AGENT_NODE_ANALYSIS_DEFAULT_BUDGET)
    sk = (scope_key or "common")[:96]   # fix(low): scope_key 길이 초과 insert 오류 방지
    lease = max(60, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_LEASE_SEC", 900)))
    c, owned = _rw_conn(conn)
    if c is None:
        return {"ok": False, "reason": "PG 미가용"}
    try:
        cur = c.cursor()
        # 진행 중 run 재사용 (중복 트리거 방지). fix(high): updated_at 이 lease 이내인 run 만 재사용 —
        #   워커 크래시로 갇힌(stale) run 을 영구 재사용해 재트리거 불가에 빠지지 않게 한다(reaper 와 함께).
        cur.execute("SELECT run_id FROM node_analysis_runs "
                    "WHERE scope_key=%s AND root_key=%s AND status='running' "
                    "AND updated_at > now() - make_interval(secs => %s) "
                    "ORDER BY created_at DESC LIMIT 1", (sk, node_key, lease))
        row = cur.fetchone()
        if row:
            cur.close()
            return {"ok": True, "run_id": row[0], "status": "running", "reused": True}
        # 루트 노드 props 확보 (그래프에서)
        ctx = _fetch_context(node_key, c)
        root = ctx.get("root") or {"label": "", "name": node_key, "fqn": ""}
        run_id = _new_run_id()
        cur.execute(
            "INSERT INTO node_analysis_runs "
            "(run_id, scope_key, root_key, root_label, root_name, depth_budget, node_budget, "
            " status, enqueued, done, failed, requested_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,'running',1,0,0,%s)",
            (run_id, sk, node_key, (root.get("label") or "")[:32],
             (root.get("name") or node_key)[:512], depth_budget, node_budget,
             (requested_by or None)))
        cur.execute(
            "INSERT INTO node_analysis_jobs "
            "(run_id, scope_key, node_key, node_label, node_name, node_fqn, depth, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,0,'pending') "
            "ON CONFLICT (run_id, node_key) DO NOTHING",
            (run_id, sk, node_key, (root.get("label") or "")[:32],
             (root.get("name") or node_key)[:512], (root.get("fqn") or "")))
        cur.close()
        _log.info("node_analysis enqueue run=%s root=%s depth=%s budget=%s",
                  run_id, node_key, depth_budget, node_budget)
        return {"ok": True, "run_id": run_id, "status": "running"}
    except Exception as exc:
        _log.warning("enqueue_analysis_failed err=%r", exc)
        return {"ok": False, "reason": "enqueue 실패"}
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass


def _cfg_enabled() -> bool:
    return bool(getattr(_cfg, "AGENT_NODE_ANALYSIS_ENABLED", True))


# ── worker step (insight-worker 틱) ──────────────────────────────────────────
def process_pending(max_nodes=None, conn=None) -> dict:
    """pending 잡을 FIFO 로 최대 max_nodes 개 처리(claim→분석→저장→이웃 재큐). 반환 telemetry.

    각 잡은 독립 try/except — 1개 실패가 배치를 중단하지 않는다. run 의 pending/running 이 모두
    소진되면 run.status 를 done(1개 이상 성공) 또는 failed(전부 실패) 로 마감."""
    rep = {"claimed": 0, "done": 0, "failed": 0, "enqueued": 0}
    if not _cfg_enabled():
        return rep
    max_nodes = _clamp(max_nodes if max_nodes is not None else _cfg.AGENT_NODE_ANALYSIS_BATCH_PER_TICK,
                       1, 64, 4)
    c, owned = _rw_conn(conn)
    if c is None:
        return rep
    from modules import llm as _llm
    try:
        cur = c.cursor()
        # fix(high): stale 'running' reclaim — 워커 크래시/SIGTERM 으로 running 에 갇힌 잡을 lease 초과 시
        #   pending 으로 되돌린다. 없으면 run 이 finalize(SELECT COUNT status IN pending/running = 0) 되지
        #   못해 영구 'running' + enqueue dedup 이 그 run 을 계속 재사용 → 재트리거 영구 불가.
        lease = max(60, int(getattr(_cfg, "AGENT_NODE_ANALYSIS_LEASE_SEC", 900)))
        try:
            cur.execute("UPDATE node_analysis_jobs SET status='pending' "
                        "WHERE status='running' AND updated_at < now() - make_interval(secs => %s)",
                        (lease,))
        except Exception:
            pass
        # claim (원자적 단일 statement — autocommit 안전).
        #   fairness fix: **depth ASC 우선** 정렬 — 모든 run 의 root(depth 0)/얕은 노드를 먼저 처리한다.
        #   과거 created_at-only FIFO 는 대형 run(예: 124노드)의 깊은 recursion 잡이 앞줄을 독점해, 이후
        #   트리거된 단일노드 run 의 root 조차 처리 못 하고 사용자 화면이 오래 0% 에 머물렀다(starvation).
        #   depth 우선이면 새 run 의 root 가 즉시 처리돼 done>0(진행 표시)로 빠르게 전환된다.
        cur.execute(
            "UPDATE node_analysis_jobs SET status='running' WHERE id IN ("
            "  SELECT id FROM node_analysis_jobs WHERE status='pending' "
            "  ORDER BY depth ASC, created_at ASC LIMIT %s FOR UPDATE SKIP LOCKED) "
            "RETURNING id, run_id, scope_key, node_key, node_label, node_name, node_fqn, depth",
            (max_nodes,))
        claimed = cur.fetchall()
        rep["claimed"] = len(claimed)
        touched_runs = set()
        for jid, run_id, scope_key, node_key, node_label, node_name, node_fqn, depth in claimed:
            touched_runs.add(run_id)
            try:
                ctx = _fetch_context(node_key, c)
                root = ctx.get("root") or {"label": node_label, "name": node_name,
                                           "fqn": node_fqn, "key": node_key}
                payload = _build_payload(root, ctx)
                obj = _llm.llm_node_analysis(payload)
                if isinstance(obj, dict):
                    analysis_text = json.dumps({
                        "summary": str(obj.get("summary") or "").strip(),
                        "relationships": str(obj.get("relationships") or "").strip(),
                        "usage": str(obj.get("usage") or "").strip(),
                        "caveats": str(obj.get("caveats") or "").strip(),
                    }, ensure_ascii=False)
                    model = getattr(_cfg, "AGENT_INSIGHT_MODEL", None) or getattr(_cfg, "OPENAI_MODEL", None)
                    cur.execute("UPDATE node_analysis_jobs SET status='done', analysis=%s, model=%s, error=NULL "
                                "WHERE id=%s", (analysis_text, (str(model)[:128] if model else None), jid))
                    cur.execute("UPDATE node_analysis_runs SET done = done + 1 WHERE run_id=%s", (run_id,))
                    rep["done"] += 1
                else:
                    cur.execute("UPDATE node_analysis_jobs SET status='failed', error=%s WHERE id=%s",
                                ("LLM 분석 실패(빈 응답/파싱)", jid))
                    cur.execute("UPDATE node_analysis_runs SET failed = failed + 1 WHERE run_id=%s", (run_id,))
                    rep["failed"] += 1
                # 이웃 재큐 (예산 내) — 성공/실패 무관(그래프 구조는 분석 성공과 독립)
                rep["enqueued"] += _enqueue_neighbors(c, cur, run_id, scope_key, ctx, depth)
            except Exception as exc:
                _log.warning("node_analysis job=%s 처리 실패 err=%r", jid, exc)
                try:
                    cur.execute("UPDATE node_analysis_jobs SET status='failed', error=%s WHERE id=%s",
                                (str(exc)[:500], jid))
                    cur.execute("UPDATE node_analysis_runs SET failed = failed + 1 WHERE run_id=%s", (run_id,))
                    rep["failed"] += 1
                except Exception:
                    pass
        # run 마감 판정
        for run_id in touched_runs:
            try:
                cur.execute("SELECT COUNT(*) FROM node_analysis_jobs "
                            "WHERE run_id=%s AND status IN ('pending','running')", (run_id,))
                remaining = int((cur.fetchone() or [0])[0])
                if remaining == 0:
                    cur.execute("SELECT done, failed FROM node_analysis_runs WHERE run_id=%s", (run_id,))
                    r = cur.fetchone() or (0, 0)
                    final = "done" if int(r[0]) > 0 else "failed"
                    cur.execute("UPDATE node_analysis_runs SET status=%s WHERE run_id=%s AND status='running'",
                                (final, run_id))
            except Exception:
                pass
        cur.close()
    except Exception as exc:
        _log.warning("process_pending_failed err=%r", exc)
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
    return rep


def _enqueue_neighbors(c, cur, run_id: str, scope_key: str, ctx: dict, cur_depth: int) -> int:
    """cur_depth 노드의 이웃을 pending 으로 재큐(dedupe + 예산 캡). 반환: 실제 삽입 수.

    fix(medium): 예산 read-modify-write 를 run 행 `FOR UPDATE` 로 원자화한다 — 다중 워커/replica 가 같은
    run 을 동시 처리해도 node_budget 을 초과 enqueue(LLM 비용 초과)하지 않도록 직렬화. LLM 호출은 이
    트랜잭션 밖(호출측)이라 락 보유 시간은 짧다. autocommit 연결에서도 c.transaction() 이 블록 트랜잭션을 연다."""
    sk = (scope_key or "common")[:96]
    inserted = 0
    try:
        with c.transaction():
            cur.execute("SELECT depth_budget, node_budget, enqueued FROM node_analysis_runs "
                        "WHERE run_id=%s FOR UPDATE", (run_id,))
            row = cur.fetchone()
            if not row:
                return 0
            depth_budget, node_budget, enqueued = int(row[0]), int(row[1]), int(row[2])
            if cur_depth + 1 > depth_budget:
                return 0
            remaining = node_budget - enqueued
            if remaining <= 0:
                return 0
            for n in (ctx.get("neighbors") or []):
                if remaining <= 0:
                    break
                k = n.get("key")
                if not k:
                    continue
                cur.execute(
                    "INSERT INTO node_analysis_jobs "
                    "(run_id, scope_key, node_key, node_label, node_name, node_fqn, depth, status) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,'pending') "
                    "ON CONFLICT (run_id, node_key) DO NOTHING RETURNING id",
                    (run_id, sk, k, (n.get("label") or "")[:32],
                     (n.get("name") or k)[:512], (n.get("fqn") or ""), cur_depth + 1))
                if cur.fetchone():
                    inserted += 1
                    remaining -= 1
            if inserted:
                cur.execute("UPDATE node_analysis_runs SET enqueued = enqueued + %s WHERE run_id=%s",
                            (inserted, run_id))
    except Exception as exc:
        _log.debug("enqueue_neighbors_failed err=%r", exc)
        return 0
    return inserted


# ── 조회 API (웹 폴링/상세 패널) ─────────────────────────────────────────────
def get_run_status(run_id: str, conn=None) -> dict | None:
    if not run_id:
        return None
    c, owned = _rw_conn(conn)
    if c is None:
        return None
    try:
        cur = c.cursor()
        cur.execute("SELECT run_id, scope_key, root_key, root_name, depth_budget, node_budget, "
                    "status, enqueued, done, failed FROM node_analysis_runs WHERE run_id=%s", (run_id,))
        r = cur.fetchone()
        if not r:
            cur.close()
            return None
        # 그래프 마커용 완료/진행 키는 **전량(cap 없이)** 조회 — node_budget 최대 1000 이라도 마커 누락 방지.
        #   키만 가져와 페이로드 작음(review fix: LIMIT 400 이 done_keys/running_keys 를 절단해 tail 노드 미표시).
        cur.execute("SELECT node_key, status FROM node_analysis_jobs "
                    "WHERE run_id=%s AND status IN ('done','running')", (run_id,))
        done_keys, running_keys = [], []
        for k, s in cur.fetchall():
            (done_keys if s == "done" else running_keys).append(k)
        # 항목별 상세 리스트(진행 패널 표시분) — 분석중→완료→깊이 순, UI 표시분만 cap(패널은 running+최근 done 만 노출).
        cur.execute("SELECT node_key, node_label, node_name, node_fqn, status, depth "
                    "FROM node_analysis_jobs WHERE run_id=%s "
                    "ORDER BY (status='running') DESC, (status='done') DESC, depth ASC, node_name ASC "
                    "LIMIT 80", (run_id,))
        jobs = [{"node_key": row[0], "node_label": row[1], "node_name": row[2],
                 "node_fqn": row[3], "status": row[4], "depth": row[5]} for row in cur.fetchall()]
        cur.close()
        return {"run_id": r[0], "scope_key": r[1], "root_key": r[2], "root_name": r[3],
                "depth_budget": r[4], "node_budget": r[5], "status": r[6],
                "enqueued": r[7], "done": r[8], "failed": r[9],
                "done_keys": done_keys, "running_keys": running_keys, "jobs": jobs}
    except Exception as exc:
        _log.debug("get_run_status_failed err=%r", exc)
        return None
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass


def get_node_analysis(scope_key: str, node_key: str, conn=None) -> dict | None:
    """노드의 최신 분석 상태/결과 (상세 패널). done 이 있으면 그 analysis, 없으면 최신 상태만."""
    if not node_key:
        return None
    c, owned = _rw_conn(conn)
    if c is None:
        return None
    try:
        cur = c.cursor()
        cur.execute("SELECT status, analysis, model, updated_at, run_id FROM node_analysis_jobs "
                    "WHERE scope_key=%s AND node_key=%s "
                    "ORDER BY (status='done') DESC, updated_at DESC LIMIT 1",
                    (scope_key or "common", node_key))
        r = cur.fetchone()
        cur.close()
        if not r:
            return {"status": "none", "analysis": None}
        analysis = None
        if r[1]:
            try:
                analysis = json.loads(r[1])
            except Exception:
                analysis = {"summary": str(r[1])}
        return {"status": r[0], "analysis": analysis, "model": r[2],
                "updated_at": r[3].isoformat() if r[3] else None, "run_id": r[4]}
    except Exception as exc:
        _log.debug("get_node_analysis_failed err=%r", exc)
        return None
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
