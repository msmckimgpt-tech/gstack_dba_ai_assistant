"""계정 스코프 cross-conversation 인사이트 회상 (TASK-20260617T082131, Phase 1 shadow).

설계 정본: unit/feature-0002-agent-core/docs/DESIGN-account-insight-recall.md

목적: 새 대화 시작 시 같은 owner_account_id 의 과거 대화 맥락을 의미적으로(어렴풋이)
회상해 LLM 컨텍스트에 주입하되 계정 경계는 절대 격리. 기존 pgvector 회상 엔진
(_load_rag_documents_for_request_pg)을 재사용하고, 회상 모집단(conversation_ids)만
계정 소유 대화로 확장한다 — 신규 테이블/컬럼 0.

Phase 1 범위: 회상 *경로* + shadow(log-only). 실제 LLM 주입(INJECT)은 G1(fork 표식)·
G3(PII 마스커) 완료 후 별 cycle. 두 flag(RECALL/INJECT) 기본 OFF.

보안 가드(설계 §4):
- G2(본 Phase 구현): owner_account_id 일치 + NOT NULL + archived 제외 + 현재 대화 제외
  + __global__/세션샤드 sentinel 제외. account_id 는 ask job claim 시 결정된 신뢰 값
  (클라이언트 payload 위조 불가).
- 본 모듈은 _global_fact_conversation_ids / cross_session_anchor 헬퍼를 import 하지 않는다
  (설계 §4 G2 — 워커샤드/전역 공유 스코프 재사용 금지).
"""
import logging
from typing import Any, Optional

from shared.config import (
    AGENT_ACCOUNT_INSIGHT_RECALL,
    AGENT_ACCOUNT_INSIGHT_INJECT,
    AGENT_ACCOUNT_INSIGHT_MAX_CONVS,
    AGENT_ACCOUNT_INSIGHT_TOP_K,
    AGENT_ACCOUNT_INSIGHT_MIN_SIM,
)

logger = logging.getLogger("agent_core.account_recall")

__all__ = [
    "_account_recall_opted_out",
    "_load_account_scoped_conv_ids",
    "recall_account_conv_facts",
]

# G3: 회상은 **account_insight**(insight worker 가 PII-free 로 추출한 메타 인사이트) 만 대상.
# user_confirm(자유 Q/A prose=PII 위험) 등 다른 source_type 은 회상하지 않는다. 이게 PII
# 차단의 1차 방어이고, 주입 직전 _mask_prose 가 2차 방어.
_ACCOUNT_INSIGHT_SOURCE_TYPE = "account_insight"
# opt-out 은 agent_runtime.kv 의 `__account__:<id>` / `account_insight_recall_optout` 로 저장.
_OPTOUT_CONV_PREFIX = "__account__:"
_OPTOUT_KEY = "account_insight_recall_optout"

# G2: cross-conversation 회상은 진짜 계정 소유 대화만. __global__ / __global__:session:*
# sentinel 은 owner_account_id 가 NULL 이라 SQL 필터에서 이미 빠지지만, 회상 모집단에
# sentinel 이 섞이지 않도록 Python 단에서도 방어심층으로 한 번 더 배제한다.
_GLOBAL_SENTINEL_PREFIX = "__global__"


def _load_account_scoped_conv_ids(
    account_id: Optional[int],
    exclude_conversation_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[str]:
    """계정이 소유한 과거 대화 conversation_id 목록 (최근순).

    보안 가드 G2: owner_account_id 일치 + NOT NULL + archived 제외 + 현재 대화 제외 +
    __global__ sentinel 제외. PG 전용(recall 은 PG 필수, fail-closed) —
    _pg_connect_ro(agent_kb_ro least-privilege) 사용. PG 미가용/예외 시 [] 반환(회상 없음, 안전).
    """
    try:
        aid = int(account_id)
    except (TypeError, ValueError):
        return []
    if aid <= 0:
        return []
    try:
        cap = int(limit) if limit is not None else int(AGENT_ACCOUNT_INSIGHT_MAX_CONVS)
    except (TypeError, ValueError):
        cap = 20
    if cap <= 0:
        return []

    from shared.db import _pg_available, _pg_connect_ro
    if not _pg_available():
        return []

    exclude = str(exclude_conversation_id or "").strip()
    conn = None
    try:
        conn = _pg_connect_ro()
        if conn is None:
            return []
        with conn.cursor() as cur:
            # ADR-0027: 전역 search_path 없음 → schema-qualified. owner_account_id = <양수>
            # 조건이 NULL-owner sentinel(__global__ 등)을 이미 배제하나 IS NOT NULL 을 명시해
            # 의도를 못박는다.
            cur.execute(
                """
SELECT conversation_id
FROM agent_runtime.core_conversations
WHERE owner_account_id = %s
  AND owner_account_id IS NOT NULL
  AND archived_at IS NULL
  AND forked_from_conversation_id IS NULL
  AND conversation_id <> %s
ORDER BY updated_at DESC
LIMIT %s
                """,
                (aid, exclude, cap),
            )
            rows = cur.fetchall() or []
        out: list[str] = []
        for row in rows:
            if not row:
                continue
            cid = str(row[0] or "").strip()
            # 방어심층: sentinel 접두 제외 (SQL 에서 이미 빠지나 이중 가드).
            if cid and cid != exclude and not cid.startswith(_GLOBAL_SENTINEL_PREFIX):
                out.append(cid)
        return out
    except Exception as e:  # noqa: BLE001 — 회상 실패는 답변을 막지 않는다(fail-soft).
        logger.warning("account_recall_conv_ids_failed", extra={"error": str(e)[:200]})
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


_QVEC_UNSET = object()  # "벡터 미제공 → 직접 임베딩" 과 "None 전달 → 임베딩 skip" 구분 sentinel


def recall_account_conv_facts(
    account_id: Optional[int],
    query_text: str,
    exclude_conversation_id: Optional[str] = None,
    query_vector: Any = _QVEC_UNSET,
) -> list[dict[str, Any]]:
    """계정 과거 대화의 PII-free 인사이트(account_insight)를 의미 회상.

    RECALL flag OFF / 빈 질의 / opt-out / conv_ids 없음 → [] (no-op·fail-soft).
    경로: 계정 소유·비-fork conv_ids 도출(G1/G2) → 쿼리 임베딩 → **벡터-only**
    `search_rag_documents_vector`(trigram fallback 미사용 = min_sim 척도 혼동 회피) →
    source_type=account_insight allowlist(G3) + cosine min_sim + conv_id 재검증(G4) + top-K →
    각 text _mask_prose(G3 2차). INJECT flag 는 caller 가 주입 여부 결정(OFF=shadow).
    반환 row shape = _normalize_rag_doc_rows (text/source_type/conversation_id/ft_score ...).
    """
    if not AGENT_ACCOUNT_INSIGHT_RECALL:
        return []
    q = " ".join(str(query_text or "").split()).strip()
    if not q:
        return []
    if _account_recall_opted_out(account_id):
        return []

    conv_ids = _load_account_scoped_conv_ids(account_id, exclude_conversation_id)
    if not conv_ids:
        return []
    conv_id_set = set(conv_ids)

    try:
        from shared.db import _pg_available, _pg_connect_ro
        from .kb_retrieval import _embed_query_vector, _normalize_rag_doc_rows
        from .kb_backend import PgKbBackend
        from .kb_scope import _mask_prose
        from .utils import _scope_candidates
    except Exception as e:  # noqa: BLE001
        logger.warning("account_recall_import_failed", extra={"error": str(e)[:200]})
        return []

    if not _pg_available():
        return []
    # 벡터-only fail-closed: 쿼리 임베딩 실패 시 회상 0 (trigram 으로 안 떨어진다).
    # CHG-20260625: query_vector 를 넘기면 재사용(_build_knowledge_context 가 1회 계산해
    # few-shot 과 공유 — 준비 단계 중복 임베딩 제거). 미지정 시에만 직접 임베딩하되
    # 상호작용 fast-fail timeout 적용.
    if query_vector is _QVEC_UNSET:
        from shared.config import AGENT_KB_QUERY_EMBED_TIMEOUT_SEC
        qvec = _embed_query_vector(q, timeout_sec=AGENT_KB_QUERY_EMBED_TIMEOUT_SEC)
    else:
        qvec = query_vector
    if not qvec:
        return []

    conn = None
    try:
        conn = _pg_connect_ro()
        if conn is None:
            return []
        vrows = PgKbBackend().search_rag_documents_vector(
            conn,
            conversation_ids=conv_ids,
            query_vector=qvec,
            scope_keys=_scope_candidates(),
            limit=max(10, int(AGENT_ACCOUNT_INSIGHT_TOP_K) * 5),
        )
        rows = _normalize_rag_doc_rows(vrows or [])
    except Exception as e:  # noqa: BLE001 — fail-soft.
        logger.warning("account_recall_vector_failed", extra={"error": str(e)[:200]})
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    try:
        min_sim = float(AGENT_ACCOUNT_INSIGHT_MIN_SIM)
    except (TypeError, ValueError):
        min_sim = 0.0
    try:
        top_k = int(AGENT_ACCOUNT_INSIGHT_TOP_K)
    except (TypeError, ValueError):
        top_k = 3

    out: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        # G3: account_insight 만(PII-free 추출본). user_confirm 등 prose 는 회상 안 함.
        if str(r.get("source_type") or "") != _ACCOUNT_INSIGHT_SOURCE_TYPE:
            continue
        # G4 방어심층: 회상 row 의 conversation_id 는 반드시 계정 소유 집합 안.
        if str(r.get("conversation_id") or "") not in conv_id_set:
            continue
        if float(r.get("ft_score") or 0.0) < min_sim:
            continue
        # G3 2차 방어: 주입 텍스트 값-패턴 PII 마스킹.
        r["text"] = _mask_prose(str(r.get("text") or ""))
        out.append(r)
        if len(out) >= max(0, top_k):
            break

    logger.info(
        "account_recall",
        extra={
            "account_id": aid_safe(account_id),
            "conv_count": len(conv_ids),
            "candidates": len(rows),
            "recalled": len(out),
            "inject": bool(AGENT_ACCOUNT_INSIGHT_INJECT),
        },
    )
    return out


def _account_recall_opted_out(account_id: Optional[int]) -> bool:
    """계정이 인사이트 회상을 opt-out 했는지 (agent_runtime.kv `__account__:<id>`).

    프라이버시: "내 과거 대화 맥락이 새 대화에 새는 게 싫다" 를 끌 수 있게 한다.
    값이 truthy('1'/'true'/'yes') 면 opt-out. 조회 실패/미설정 → False(회상 허용, fail-open
    은 기능 기본이 opt-in[flag OFF]이므로 안전)."""
    try:
        aid = int(account_id)
    except (TypeError, ValueError):
        return False
    if aid <= 0:
        return False
    from shared.db import _pg_available, _pg_connect_ro
    if not _pg_available():
        return False
    conn = None
    try:
        conn = _pg_connect_ro()
        if conn is None:
            return False
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM agent_runtime.kv WHERE conversation_id = %s AND key = %s LIMIT 1",
                (f"{_OPTOUT_CONV_PREFIX}{aid}", _OPTOUT_KEY),
            )
            row = cur.fetchone()
        val = str((row or [None])[0] or "").strip().lower()
        return val in ("1", "true", "yes")
    except Exception:
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def aid_safe(account_id: Optional[int]) -> Optional[int]:
    """로깅용 account_id 안전 변환 (실패 시 None)."""
    try:
        return int(account_id)
    except (TypeError, ValueError):
        return None
