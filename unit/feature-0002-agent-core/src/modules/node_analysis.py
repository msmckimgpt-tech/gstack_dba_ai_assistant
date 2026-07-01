"""feature-0016 graphux5: 그래프 노드 AI 능동 분석 — 재귀 탐색 + 백그라운드 처리.

관리콘솔 그래프뷰 상세 패널의 "AI 능동 분석" 버튼이 `enqueue_analysis()` 로 run 을 만들고 루트 노드를
pending 잡으로 넣는다. insight-worker 틱이 `process_pending()` 으로 pending 잡을 소량씩 소비하며(부하
분산), 노드마다 이웃 컨텍스트를 모아 LLM 분석문을 생성·저장하고, 방문하지 않은 이웃을 (예산 내)
pending 으로 재큐한다 — 이렇게 **선택 노드에서 시작해 관련 노드를 재귀적으로 탐색**한다.

설계 원칙 (metadata_graph.py 동형):
  - 저장소 = agent_kb PG 의 node_analysis_runs / node_analysis_jobs (alembic 0028, relevance 0029).
  - 연결은 shared.db._pg_connect(RW). PG 미가용·예외 시 no-op — 코어 흐름 절대 비차단.
  - **비용 경계(사용자 결정 2026-07-01)**: run 마다 depth_budget/node_budget 로 재귀를 캡하고,
    UNIQUE(run_id,node_key) 로 dedupe 한다. "관련된 모든 노드"의 무한 확장(LLM 비용 폭증) 방지.
  - 그래프 컨텍스트/이웃은 metadata_graph.neighborhood(depth=1) 재사용.
  - **앵커-상대 관련도(node-analysis-anchor, 2026-07-01)**: 재귀는 방문 노드의 인접성이 아니라
    **원래 분석 대상(루트=anchor)** 과의 관련도로 이웃을 게이트·우선순위화한다. 허브(일반 컬럼 UniqueID·
    부모 Schema)를 새 중심으로 무관 노드까지 fan-out 하던 문제를 차단한다. 루트 직속 컬럼은 기본 분석
    (게이트 면제), 그 외는 관련도 임계 이상만 재귀(깊을수록 임계 상향), relevance 로 우선순위 정렬.
"""
from __future__ import annotations

import json
import logging
import re
import uuid

from shared import config as _cfg

_log = logging.getLogger("node_analysis")


# ── 앵커-상대 관련도 (feature-0016 node-analysis-anchor) ──────────────────────
# 일반어(도메인 식별력 없는 토큰) — 이름이 이것만 겹치는 이웃은 "단순히 컬럼 명칭이 같은" 경우라
# 관련도로 인정하지 않는다(사용자 요구). id/uniqueid/seq/regdate 등 관용 컬럼명·구조어 위주.
_GENERIC_TOKENS = frozenset({
    "id", "uid", "uuid", "guid", "seq", "seqno", "no", "num", "idx", "index",
    "key", "pk", "fk", "ref", "code", "type", "kind", "status", "state", "flag",
    "yn", "use", "used", "enable", "enabled", "active", "value", "val", "data",
    "info", "count", "cnt", "sum", "total", "amount", "qty", "date", "datetime",
    "time", "timestamp", "ts", "created", "updated", "modified", "deleted",
    "createdat", "updatedat", "createddate", "regdate", "reg", "mod", "del",
    "insert", "update", "order", "ordinal", "sort", "unique", "uniqueid", "row",
    "rownum", "version", "ver", "rev", "desc", "description", "comment", "memo",
    "note", "table", "column", "schema", "db", "database", "common", "dbo",
    "tbl", "col", "name", "title", "label", "text", "str", "int", "bigint",
    # camelCase 접속·전치사 조각(CreatedAt/UpdatedBy/BasedOn 등) — 도메인 식별력 없음.
    "at", "by", "on", "of", "to", "in", "for", "and", "or", "with", "from", "per", "is", "as",
    # 한글 일반어·구조어(이 Korean-first 스키마의 설명·명칭에 흔한 boilerplate) — 라틴 목록과 동형.
    #  이것을 빼지 않으면 설명 겹침 booster 가 "게임/정의/테이블" 같은 일반어만으로 content 를 조작(M1 재발).
    "테이블", "컬럼", "정의", "정보", "코드", "상태", "이름", "데이터", "목록", "관리",
    "사용", "여부", "순서", "번호", "유형", "종류", "생성", "수정", "삭제", "일시",
    "게임", "기본", "설정", "내용", "대상", "처리", "결과", "항목", "구분", "시간",
    "날짜", "등록", "요청", "응답", "시스템", "서버", "사용자", "유저", "기록", "로그",
    "값", "필드", "속성", "관련", "전체", "해당", "각각",
})

_TOKEN_SPLIT = re.compile(r"[^0-9A-Za-z가-힣]+")
_CAMEL_SPLIT = re.compile(
    r"(?<=[a-z0-9])(?=[A-Z])"          # camelCase (rewardItem)
    r"|(?<=[A-Z])(?=[A-Z][a-z])"       # ACRONYM+Word (HTTPServer)
    r"|(?<=[가-힣])(?=[A-Za-z0-9])"     # 한글→라틴/숫자 (업적Achievement)
    r"|(?<=[A-Za-z0-9])(?=[가-힣])"     # 라틴/숫자→한글 (Achievement업적)
)
_HANGUL = re.compile(r"[가-힣]")


def _has_hangul(s) -> bool:
    return bool(_HANGUL.search(s or ""))


def _split_tokens(text) -> list:
    """텍스트를 snake/camel/한글↔라틴/구분자 기준으로 분해 + 끝자리 숫자 제거한 소문자 토큰 리스트."""
    out = []
    for part in _TOKEN_SPLIT.split(str(text or "")):
        if not part:
            continue
        for sub in _CAMEL_SPLIT.split(part):
            s = sub.strip().lower()
            if not s:
                continue
            out.append(s)
            s2 = s.rstrip("0123456789")   # col1 → col
            if s2 and s2 != s:
                out.append(s2)
    return out


def _meaningful_tokens(*texts) -> set:
    """일반어·1글자 토큰을 뺀 '식별력 있는' 토큰 집합. 도메인 연관성 비교용."""
    toks = set()
    for text in texts:
        for t in _split_tokens(text):
            if len(t) < 2 or t in _GENERIC_TOKENS:
                continue
            toks.add(t)
    return toks


def _hangul_partial_overlap(a_tokens: set, n_tokens: set) -> bool:
    """한글 합성어 부분 연관(형태소 분석 부재 보정): 업적 ⊂ 업적보상 처럼 어근이 **접두/접미** 일치.

    라틴 부분일치(log ⊂ login)는 오연관이 잦아 한글에만 적용하되, 한글도 **임의 부분문자열은 금지**하고
    접두/접미 경계만 인정한다 — 그렇지 않으면 회원 ⊂ 비회원구매(반대 의미)·업적 ⊂ 기업적자(무관) 같은
    중간삽입 오매칭이 발생(재검증 지적). 한글 합성어는 어근이 보통 접두/접미이므로 이 경계로 정밀도 확보."""
    ah = [t for t in a_tokens if len(t) >= 2 and _has_hangul(t)]
    nh = [t for t in n_tokens if len(t) >= 2 and _has_hangul(t)]
    for at in ah:
        for nt in nh:
            if at == nt:
                continue
            short, long = (at, nt) if len(at) <= len(nt) else (nt, at)
            if long.startswith(short) or long.endswith(short):
                return True
    return False


def _scope_of(key: str) -> str:
    return (key or "").split(":", 1)[0]


def _table_fqn(label: str, fqn: str) -> str:
    """노드의 소속 테이블 fqn. Column 이면 마지막 세그먼트(컬럼명) 제거, Table 이면 그대로."""
    fqn = fqn or ""
    if label == "Column":
        return fqn.rsplit(".", 1)[0] if "." in fqn else ""
    if label == "Table":
        return fqn
    return ""


def _build_anchor(root_key: str, root_label: str, root_name: str, root_desc: str = "") -> dict:
    """원래 분석 대상(루트) 서술자 — 이웃 관련도 채점의 기준. 그래프 미발견 시에도 run 행 값으로 구성."""
    fqn = root_key.split(":", 1)[1] if ":" in root_key else root_key
    tbl = _table_fqn(root_label, fqn)
    last_seg = fqn.rsplit(".", 1)[-1] if fqn else ""
    return {
        "key": root_key,
        "scope": _scope_of(root_key),
        "label": root_label or "",
        "table_fqn": tbl,
        "tokens": _meaningful_tokens(root_name, last_seg, tbl),
        "desc_tokens": _meaningful_tokens(root_desc),
    }


def _relevance(node: dict, meta: dict, anchor: dict) -> float:
    """후보 이웃 node 의 '원래 루트(anchor)' 와의 관련도(0~1). 인접성이 아니라 **루트 기준** 채점.

    핵심 원칙(사용자 요구): **내용(도메인) 연관이 전혀 없으면 재귀 대상 아님.** 같은 제품(scope)·신뢰
    REFERENCES 같은 구조 신호만으로는 통과하지 못한다 — 반드시 아래 content 신호(테이블 서브트리·이름/
    설명 토큰·용어) 중 하나가 있어야 하고, 구조 신호는 그 위에 **부스터**로만 작용한다.
    """
    meta = meta or {}
    label = node.get("label") or ""
    # Schema 는 형제 테이블 전량 fan-out 허브 → 확장 대상에서 제외(옵션으로만 허용).
    if label == "Schema" and not getattr(_cfg, "AGENT_NODE_ANALYSIS_EXPAND_SCHEMA", False):
        return 0.0
    # 파단(broken) 엣지로만 닿는 이웃은 신뢰할 수 없는 관계 → 제외.
    #   (belt-and-suspenders: neighborhood() 가 이미 broken 엣지를 투영 제외하지만 방어적으로 유지.)
    if meta.get("status") == "broken":
        return 0.0

    # ── content(도메인 연관) 신호 — 0 이면 '단순 명칭·구조 링크' 로 보고 제외 ──────────────
    content = 0.0
    # 1) 루트 테이블 서브트리(같은 테이블 소속) — 가장 강한 "대상 엔티티" 연관.
    n_table = _table_fqn(label, node.get("fqn") or "")
    if anchor["table_fqn"] and n_table and n_table == anchor["table_fqn"]:
        content += 0.6
    # 2) 이름 토큰 겹침(일반어 제외) — "Achievement" 등 도메인 명칭 연관 + 한글 합성어 부분 연관.
    n_tokens = _meaningful_tokens(node.get("name"), node.get("fqn"))
    a_tokens = anchor.get("tokens") or set()
    if a_tokens and n_tokens:
        overlap = len(n_tokens & a_tokens)
        if overlap:
            content += min(0.45, 0.30 * overlap)
        elif _hangul_partial_overlap(a_tokens, n_tokens):
            content += 0.22
    # 3) 설명 내용 겹침 — 상위 객체 속성/컨텐츠 연관.
    if anchor.get("desc_tokens") and node.get("description"):
        inter = len(_meaningful_tokens(node.get("description")) & anchor["desc_tokens"])
        if inter:
            content += min(0.25, 0.06 * inter)
    # 4) 관련 용어(GlossaryTerm) 는 그 자체가 도메인 개념 앵커 — content 로 인정.
    if label == "GlossaryTerm":
        content += 0.18

    if content <= 0.0:
        return 0.0   # 내용 연관 전무 → 신뢰/제품만으론 재귀 제외(M1: 단순 명칭·구조 링크 배제)

    score = content
    # 5) REFERENCES 신뢰도(ADR-002 weight/status) — **부스터**: 이미 연관 있는 노드를 강화만.
    w = meta.get("weight")
    if meta.get("status") == "trusted" or (isinstance(w, (int, float)) and w >= 0.85):
        score += 0.15

    # 제품 경계: 같은 제품이면 소폭 가산, 다른 제품이면 강한 감쇠(교차-제품 확장 억제).
    if _scope_of(node.get("key") or "") == anchor["scope"]:
        score += 0.08
    else:
        score *= max(0.0, float(getattr(_cfg, "AGENT_NODE_ANALYSIS_CROSS_SCOPE_FACTOR", 0.25)))

    return max(0.0, min(1.0, score))


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
    # 이웃별 엣지 메타(관련도 채점용): {key: {kind, weight, status, child}}.
    #   child=True → node_key(현재 노드)의 직속 HAS_COLUMN 자식(=하위 컬럼). 우선순위: 신뢰 REFERENCES > child > 그 외.
    neighbor_meta: dict = {}

    def _record(k, kind, weight=None, status=None, child=False):
        if not k or k == node_key:
            return
        cur = neighbor_meta.get(k)
        if cur is None:
            neighbor_meta[k] = {"kind": kind, "weight": weight, "status": status, "child": child}
            return
        cur["child"] = cur["child"] or child
        if weight is not None and cur.get("weight") is None:
            cur["weight"] = weight
        if status and not cur.get("status"):
            cur["status"] = status

    for e in edges:
        et = e.get("type")
        src, tgt = e.get("source"), e.get("target")
        if et == "HAS_COLUMN" and src == node_key:
            t = by_key.get(tgt)
            if t:
                columns.append(t)
            _record(tgt, "column", child=True)
        elif et == "REFERENCES":
            references.append({"from": src, "to": tgt, "cardinality": e.get("cardinality"),
                               "weight": e.get("weight"), "status": e.get("status")})
            other_key = tgt if src == node_key else (src if tgt == node_key else None)
            if other_key:
                _record(other_key, "reference", weight=e.get("weight"), status=e.get("status"))
        elif et in ("RELATED_TERM", "DESCRIBES"):
            _record(tgt if src == node_key else src, "term")
        else:  # HAS_TABLE, HAS_SCHEMA, USES 등 구조 엣지
            _record(tgt if src == node_key else src, "structural")
    for n in nodes:
        k = n.get("key")
        if k == node_key:
            continue
        if n.get("label") == "GlossaryTerm":
            related_terms.append(n)
            _record(k, "term")
        elif n not in columns:
            other.append(n)
            neighbor_meta.setdefault(k, {"kind": "other", "weight": None, "status": None, "child": False})
    return {"root": root, "neighbors": [n for n in nodes if n.get("key") != node_key],
            "columns": columns, "references": references, "related_terms": related_terms,
            "other": other, "neighbor_meta": neighbor_meta}


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
            "(run_id, scope_key, node_key, node_label, node_name, node_fqn, depth, relevance, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,0,1.0,'pending') "
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
        #   anchor(node-analysis-anchor): 같은 depth 안에서는 **relevance DESC** — 원래 대상과 관련 높은
        #   노드부터 예산을 소비한다(사용자 "낮은 우선순위로 판단" 요구의 영속 구현, ix_..._claim_priority).
        #   공정성 주의(M2): root 는 전부 depth 0·relevance 1.0 이라 tie→created_at ASC(FIFO) — **root
        #   starvation 무회귀**. 단 depth>=1 은 run 간에도 relevance 우선(FIFO 아님)이라, 관련도 높은 잡이
        #   많은 대형 run 이 신규 run 의 저관련 깊은 잡보다 먼저 소비될 수 있다(예산 캡·BATCH 로 지연만,
        #   영구 기아 아님. root 는 즉시 진행 표시). 엄격 per-run 공정성 필요 시 round-robin 후속.
        cur.execute(
            "UPDATE node_analysis_jobs SET status='running' WHERE id IN ("
            "  SELECT id FROM node_analysis_jobs WHERE status='pending' "
            "  ORDER BY depth ASC, relevance DESC, created_at ASC LIMIT %s FOR UPDATE SKIP LOCKED) "
            "RETURNING id, run_id, scope_key, node_key, node_label, node_name, node_fqn, depth",
            (max_nodes,))
        claimed = cur.fetchall()
        rep["claimed"] = len(claimed)
        touched_runs = set()
        anchors: dict = {}   # run_id -> anchor 서술자(틱 내 캐시, run 당 1회 그래프 조회)
        for jid, run_id, scope_key, node_key, node_label, node_name, node_fqn, depth in claimed:
            touched_runs.add(run_id)
            anchor = _load_anchor(c, cur, run_id, anchors)
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
                # 이웃 재큐 (예산 내) — 성공/실패 무관(그래프 구조는 분석 성공과 독립).
                #   anchor(원래 루트) 관련도로 게이트·우선순위화 — 허브 fan-out 억제.
                rep["enqueued"] += _enqueue_neighbors(c, cur, run_id, scope_key, ctx, depth, anchor)
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


def _load_anchor(c, cur, run_id: str, cache: dict) -> dict:
    """run 의 원래 루트 서술자(anchor)를 로드·캐시. 관련도 채점 기준. 실패 시에도 최소 서술자 반환.

    루트 설명은 그래프에서 run 당 1회만 조회(틱 캐시)해 비용을 제한한다. 그래프 미발견 시 run 행 값만으로 구성."""
    if run_id in cache:
        return cache[run_id]
    anchor = None
    try:
        cur.execute("SELECT root_key, root_label, root_name FROM node_analysis_runs WHERE run_id=%s",
                    (run_id,))
        r = cur.fetchone()
        if r:
            root_key, root_label, root_name = r[0], (r[1] or ""), (r[2] or "")
            root_desc = ""
            try:
                rnode = (_fetch_context(root_key, c).get("root")) or {}
                root_desc = rnode.get("description") or ""
            except Exception:
                pass
            anchor = _build_anchor(root_key, root_label, root_name, root_desc)
    except Exception as exc:
        _log.debug("load_anchor_failed err=%r", exc)
    cache[run_id] = anchor
    return anchor


def _score_candidates(ctx: dict, cur_depth: int, anchor: dict) -> list:
    """이웃 후보를 (relevance, node) 로 채점·게이트·정렬(내림차순)한다.

    - cur_depth==0 의 직속 컬럼(=원래 대상의 하위 컬럼)은 relevance=1.0 으로 **무조건 통과**(기본 분석).
    - 그 외는 앵커(원래 루트) 상대 관련도로 채점, 이웃 깊이가 깊을수록 임계 상향 → 허브 재탐색 억제.
    - 임계 미달·Schema 허브·파단 엣지는 제외(재귀 낮은 우선순위 = 탈락).
    """
    if not anchor:   # 앵커 로드 실패(드묾) → 보수적 게이팅(하위 컬럼만 통과, fan-out 억제).
        anchor = {"key": "", "scope": "", "label": "", "table_fqn": "",
                  "tokens": set(), "desc_tokens": set()}
    meta_map = ctx.get("neighbor_meta") or {}
    neighbor_depth = cur_depth + 1
    # 임계: 이웃 depth 가 깊을수록 상향(허브 재탐색 억제). depth 1 은 MIN, depth>=2 는 _DEEP 에서
    #   깊이당 추가 가산(MAX_DEPTH=5 등 깊은 예산에서도 "깊을수록 상향" 유지, M3). 상한 0.7.
    min_val = float(getattr(_cfg, "AGENT_NODE_ANALYSIS_RELEVANCE_MIN", 0.18))
    deep_val = float(getattr(_cfg, "AGENT_NODE_ANALYSIS_RELEVANCE_MIN_DEEP", 0.34))
    if neighbor_depth <= 1:
        min_rel = min_val
    else:
        min_rel = min(0.7, deep_val + 0.06 * (neighbor_depth - 2))
    kept = []
    for n in (ctx.get("neighbors") or []):
        k = n.get("key")
        if not k:
            continue
        meta = meta_map.get(k) or {}
        if cur_depth == 0 and meta.get("child"):
            rel = 1.0                    # 원래 대상의 직속 하위 컬럼 → 기본 분석
        else:
            rel = _relevance(n, meta, anchor)
            if rel < min_rel:
                continue                 # 관련도 미달 → 재귀 제외
        kept.append((rel, n))
    # 관련도 높은 순 — 예산 우선 소비. 동점(특히 하위 컬럼 1.0)은 ordinal→name 으로 **결정적** 정렬:
    #   예산 절단 시 어느 컬럼이 분석되는지 재현 가능 + 컬럼은 ordinal 순 우선(M5).
    def _tiebreak(node):
        ordv = node.get("ordinal")
        ordv = ordv if isinstance(ordv, int) else 10_000
        # key 를 마지막 성분으로 — 동명(다른 스키마/제품) 노드도 전순서 결정(DB row order 비의존).
        return (ordv, str(node.get("name") or ""), str(node.get("key") or ""))
    kept.sort(key=lambda t: (-t[0], _tiebreak(t[1])))
    return kept


def _enqueue_neighbors(c, cur, run_id: str, scope_key: str, ctx: dict, cur_depth: int,
                       anchor: dict) -> int:
    """cur_depth 노드의 이웃을 **앵커 관련도로 게이트·우선순위화**해 pending 재큐(dedupe + 예산 캡).

    반환: 실제 삽입 수. anchor(원래 루트 서술자) 기준으로 채점해, 방문 노드가 허브여도 무관 노드로
    fan-out 하지 않고 원래 대상과 연관 높은 이웃만 관련도 순으로 재큐한다.

    fix(medium): 예산 read-modify-write 를 run 행 `FOR UPDATE` 로 원자화한다 — 다중 워커/replica 가 같은
    run 을 동시 처리해도 node_budget 을 초과 enqueue(LLM 비용 초과)하지 않도록 직렬화. LLM 호출은 이
    트랜잭션 밖(호출측)이라 락 보유 시간은 짧다. autocommit 연결에서도 c.transaction() 이 블록 트랜잭션을 연다."""
    sk = (scope_key or "common")[:96]
    inserted = 0
    candidates = _score_candidates(ctx, cur_depth, anchor)
    if not candidates:
        return 0
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
            for rel, n in candidates:
                if remaining <= 0:
                    break
                k = n.get("key")
                cur.execute(
                    "INSERT INTO node_analysis_jobs "
                    "(run_id, scope_key, node_key, node_label, node_name, node_fqn, depth, relevance, status) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending') "
                    "ON CONFLICT (run_id, node_key) DO NOTHING RETURNING id",
                    (run_id, sk, k, (n.get("label") or "")[:32],
                     (n.get("name") or k)[:512], (n.get("fqn") or ""), cur_depth + 1,
                     round(float(rel), 4)))
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
        # 항목별 상세 리스트(진행 패널 표시분) — 분석중→완료→깊이·관련도 순, UI 표시분만 cap(패널은 running+최근 done 만 노출).
        #   relevance 도 함께 노출 — UI 가 "원래 대상과의 관련도" 로 우선순위를 표시할 수 있게(node-analysis-anchor).
        cur.execute("SELECT node_key, node_label, node_name, node_fqn, status, depth, relevance "
                    "FROM node_analysis_jobs WHERE run_id=%s "
                    "ORDER BY (status='running') DESC, (status='done') DESC, depth ASC, relevance DESC, node_name ASC "
                    "LIMIT 80", (run_id,))
        jobs = [{"node_key": row[0], "node_label": row[1], "node_name": row[2],
                 "node_fqn": row[3], "status": row[4], "depth": row[5],
                 "relevance": round(float(row[6]), 4) if row[6] is not None else None}
                for row in cur.fetchall()]
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


def get_scope_analysis_status(scope_key: str, node_keys=None, conn=None) -> dict | None:
    """스코프 내 노드들의 최신 분석 상태를 **일괄** 집계 — 그래프 초기 렌더/검색/확장 시
    마커(보라 '분석됨'·주황 '분석중')를 노드 클릭 없이 즉시 적용하기 위함.

    반환 {done_keys:[...], running_keys:[...]}:
      - done_keys    = 완료(done) 잡이 하나라도 있는 node_key
      - running_keys = done 은 없고 pending/running 잡이 있는 node_key
    node_keys 지정 시 그 부분집합만 조회(대형 그래프 payload 축소). PG 미가용/예외 → None(코어 비차단)."""
    c, owned = _rw_conn(conn)
    if c is None:
        return None
    try:
        cur = c.cursor()
        params = [scope_key or "common"]
        where = "scope_key=%s"
        keys = [k for k in (node_keys or []) if k]
        if keys:
            where += " AND node_key = ANY(%s)"
            params.append(keys)
        cur.execute(
            "SELECT node_key, "
            "bool_or(status='done') AS has_done, "
            "bool_or(status IN ('pending','running')) AS has_active "
            "FROM node_analysis_jobs WHERE " + where + " GROUP BY node_key",
            tuple(params))
        done_keys, running_keys = [], []
        for k, has_done, has_active in cur.fetchall():
            if has_done:
                done_keys.append(k)
            elif has_active:
                running_keys.append(k)
        cur.close()
        return {"done_keys": done_keys, "running_keys": running_keys}
    except Exception as exc:
        _log.debug("get_scope_analysis_status_failed err=%r", exc)
        return None
    finally:
        if owned and c is not None:
            try:
                c.close()
            except Exception:
                pass
