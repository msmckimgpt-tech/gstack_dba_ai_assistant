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

from .config import (
    AGENT_ACCOUNT_INSIGHT_RECALL,
    AGENT_ACCOUNT_INSIGHT_INJECT,
    AGENT_ACCOUNT_INSIGHT_MAX_CONVS,
    AGENT_ACCOUNT_INSIGHT_TOP_K,
    AGENT_ACCOUNT_INSIGHT_MIN_SIM,
)

logger = logging.getLogger("agent_core.account_recall")

__all__ = [
    "_load_account_scoped_conv_ids",
    "recall_account_conv_facts",
]

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

    from .db import _pg_available, _pg_connect_ro
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


def recall_account_conv_facts(
    account_id: Optional[int],
    query_text: str,
    exclude_conversation_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """계정 과거 대화 fact 를 의미 회상 (Phase 1 shadow).

    RECALL flag OFF 면 [] (no-op). 도출된 account conv_ids 를 기존 PG 벡터 회상
    (_load_rag_documents_for_request_pg)에 주입한 뒤 유사도 임계 + top-K 로 노이즈를
    억제한다. INJECT flag 는 caller 가 본 결과를 실제 LLM 컨텍스트에 넣을지 결정하며,
    OFF 면 shadow(반환만, caller 가 주입 안 함). 반환 row shape 은 _normalize_rag_doc_rows
    동일(conversation_id/fact_key/content/ft_score ...).
    """
    if not AGENT_ACCOUNT_INSIGHT_RECALL:
        return []
    q = " ".join(str(query_text or "").split()).strip()
    if not q:
        return []

    conv_ids = _load_account_scoped_conv_ids(account_id, exclude_conversation_id)
    if not conv_ids:
        return []

    try:
        from .kb_retrieval import _load_rag_documents_for_request_pg
        from .utils import _scope_candidates
        rows = _load_rag_documents_for_request_pg(conv_ids, q, _scope_candidates())
    except Exception as e:  # noqa: BLE001 — fail-soft.
        logger.warning("account_recall_vector_failed", extra={"error": str(e)[:200]})
        return []
    rows = rows or []

    try:
        min_sim = float(AGENT_ACCOUNT_INSIGHT_MIN_SIM)
    except (TypeError, ValueError):
        min_sim = 0.0
    try:
        top_k = int(AGENT_ACCOUNT_INSIGHT_TOP_K)
    except (TypeError, ValueError):
        top_k = 3

    filtered = [r for r in rows if float(r.get("ft_score") or 0.0) >= min_sim]
    out = filtered[: max(0, top_k)]

    logger.info(
        "account_recall_shadow",
        extra={
            "account_id": aid_safe(account_id),
            "conv_count": len(conv_ids),
            "candidates": len(rows),
            "recalled": len(out),
            "inject": bool(AGENT_ACCOUNT_INSIGHT_INJECT),
        },
    )
    return out


def aid_safe(account_id: Optional[int]) -> Optional[int]:
    """로깅용 account_id 안전 변환 (실패 시 None)."""
    try:
        return int(account_id)
    except (TypeError, ValueError):
        return None
