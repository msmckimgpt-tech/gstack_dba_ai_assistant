"""TASK-0108 Sprint 3 (B: DDL/KB 보강) — Admin-only manual KB ingest.

BRIEFING-attachment-multi-cycle.md §6.3 Sprint 3 Cycle 3 정합. admin 콘솔에서
text/markdown 또는 .sql 첨부를 선택해 `AgentMemoryFactEntries` 의 manual fact
로 등록한다. ScopeKey 단위 격리, 동일 ScopeKey 재ingest 시 기존 active row 는
Weight=0 으로 logical supersede (Status 컬럼 추가 회피, 회귀 0), 새 row 는
Weight=90 (BRIEFING D 의 0.9 scale, 자동 수집 Weight=1 대비 우선) + SourceType='manual'.

ConversationId='__kb_manual__' reserved sentinel — insight_worker 의 `__insight_worker__`
패턴 답습 (manual ingest 는 conv 단위 비귀속, ScopeKey 가 격리 기준).

본문은 `AgentMemoryTexts.TextContent` 에 저장되고 `AgentMemoryFactEntries.TextHash`
외래키로 참조한다 (해시 기반 중복 제거 — `AgentMemoryFacts` VIEW 정합).

AgentMemoryFacts VIEW 의 tie-break (Weight DESC, UpdatedAt DESC, Id DESC) 이
자동으로 active row (Weight=90) 만 노출 — supersede 된 row 는 VIEW 에서 자연 hide.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any


KB_MANUAL_CONVERSATION_ID = "__kb_manual__"
"""Reserved sentinel ConversationId for manual KB ingest fact rows.

insight_worker 의 `__insight_worker__` 패턴 답습. 일반 conversation 영역과 격리.
ScopeKey 가 실 격리 기준이고 본 sentinel 은 group 식별만.
"""

DEFAULT_MANUAL_WEIGHT = 90
"""Default Weight for manual ingest fact (BRIEFING D 의 0.9 scale, INT 컬럼이라 ×100).

자동 수집 fact 의 default Weight=1 대비 90× 우선. AgentMemoryFacts VIEW 의
ORDER BY Weight DESC tie-break 가 active manual fact 를 자연 우선.
"""

DEFAULT_SOURCE_TYPE = "manual"
"""SourceType column value for manual ingest. BRIEFING §6.3 명시."""


def _normalize_fact_text(body: str) -> str:
    """memory.py SHA1 정규화 패턴 답습.

    SHA1(LOWER(TRIM(REGEXP_REPLACE(body, '[[:space:]]+', ' ')))) 의 Python 등가.
    """
    return re.sub(r"\s+", " ", body.lower().strip())


def _compute_text_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _compute_fact_fingerprint(body: str) -> str:
    return hashlib.sha1(_normalize_fact_text(body).encode("utf-8")).hexdigest()


def ingest_manual(
    conn: Any,
    *,
    scope_key: str,
    body: str,
    source_filename: str | None = None,
    source_sha256: str | None = None,
    source_type: str = DEFAULT_SOURCE_TYPE,
    weight: int = DEFAULT_MANUAL_WEIGHT,
) -> dict[str, Any]:
    """첨부 본문을 AgentMemoryFactEntries 의 manual fact 로 등록.

    BRIEFING §6.3 Sprint 3 implementation. 호출자 (endpoint) 는 conn 의 commit
    책임. 본 helper 는 그 안에서 3 statement (INSERT IGNORE Texts + UPDATE
    supersede + INSERT FactEntries) 를 single transaction 으로 처리.

    Args:
        conn: MySQL connection (caller-owned). agent_memory DB.
        scope_key: 격리 기준. FactKey 도 동일 값 사용 (한 ScopeKey = 한 active fact).
            length ≤ 96 (스키마 제약).
        body: ingest 본문 (UTF-8). caller 가 size cap 검증 책임.
        source_filename: WebConversationAttachments.OriginalFilename (provenance).
            저장 안 됨 (D12 audit masking 정책 — raw filename 금지) — 향후 SourceSql
            에 안전 normalized form 저장 가능. 현 cycle 은 audit ChangeJson 에만 사용.
        source_sha256: 첨부 SHA256 (provenance 추적용). SourceRunId 에 저장.
        source_type: AgentMemoryFactEntries.SourceType. default 'manual'.
        weight: AgentMemoryFactEntries.Weight. default 90.

    Returns:
        dict {
            'fact_entry_id': int — 새 row 의 PK Id,
            'text_hash': str — 64자 hex (SHA256 of body),
            'fact_fingerprint': str — 40자 hex (SHA1 of normalized body),
            'superseded_count': int — Weight 0 으로 demote 된 기존 row 수,
            'reactivated': bool — 동일 fingerprint 이전 row 가 있어서 reactivate 됐는지,
        }

    Raises:
        ValueError: scope_key 가 빈 문자열, body 가 빈 문자열, scope_key length > 96.
    """
    if not scope_key or not scope_key.strip():
        raise ValueError("scope_key 필수")
    if not body or not body.strip():
        raise ValueError("body 필수")
    scope_key = scope_key.strip()
    if len(scope_key) > 96:
        raise ValueError(f"scope_key length > 96 (got {len(scope_key)})")

    text_hash = _compute_text_hash(body)
    fact_fingerprint = _compute_fact_fingerprint(body)

    # Step 1: AgentMemoryTexts 멱등 INSERT (동일 TextHash 는 silent skip).
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT IGNORE INTO AgentMemoryTexts (TextHash, TextContent) VALUES (%s, %s)",
            (text_hash, body),
        )

        # Step 2 (B-1 흡수 — REV-20260526-0002): (conv, scope, key) 범위를
        # SELECT ... FOR UPDATE 로 잠금. 동시 ingest 가 둘 다 UPDATE Weight=0
        # 후 둘 다 INSERT Weight=90 하는 race 차단. 본 lock 은 단일 endpoint 안
        # transaction 으로 보호되며 endpoint 가 commit/rollback 책임.
        cur.execute(
            """
SELECT Id, Weight, FactFingerprint
FROM AgentMemoryFactEntries
WHERE ConversationId = %s AND ScopeKey = %s AND FactKey = %s
FOR UPDATE
            """,
            (KB_MANUAL_CONVERSATION_ID, scope_key, scope_key),
        )
        existing_rows = cur.fetchall() or []
        # B-1 / reactivated 명시 계산: 동일 fingerprint 의 기존 row 가 있는지 사전 판정.
        existing_active_ids: list[int] = []
        same_fp_row: tuple | None = None
        for row in existing_rows:
            if isinstance(row, dict):
                row_id = int(row.get("Id") or 0)
                row_weight = int(row.get("Weight") or 0)
                row_fp = str(row.get("FactFingerprint") or "")
            else:
                row_id = int(row[0] or 0)
                row_weight = int(row[1] or 0)
                row_fp = str(row[2] or "")
            if row_weight > 0:
                existing_active_ids.append(row_id)
            if row_fp == fact_fingerprint:
                same_fp_row = (row_id, row_weight, row_fp)
        reactivated = bool(same_fp_row is not None)

        # Step 3: active (Weight>0) row demote → Weight=0. 동일 fp row 가 있으면
        # 그것도 demote 되지만 다음 step 에서 reactivate.
        superseded_count = 0
        if existing_active_ids:
            placeholders = ",".join(["%s"] * len(existing_active_ids))
            cur.execute(
                f"""
UPDATE AgentMemoryFactEntries
SET Weight = 0,
    UpdatedAt = CURRENT_TIMESTAMP(3)
WHERE Id IN ({placeholders})
                """,
                tuple(existing_active_ids),
            )
            superseded_count = int(cur.rowcount or 0)
            # reactivated 면 자기 자신을 1번 demote 했으므로 superseded_count 에서 1 차감.
            if reactivated and same_fp_row is not None and int(same_fp_row[1]) > 0:
                if superseded_count > 0:
                    superseded_count -= 1

        # Step 4: 새 row INSERT — UNIQUE (Conv, Scope, FactKey, FactFingerprint).
        # 동일 fp 의 row 가 있으면 ON DUPLICATE KEY UPDATE 로 reactivate (Weight=90 복원).
        # `Id = LAST_INSERT_ID(Id)` (B-1 Nice-to-have 흡수) 가 ON DUPLICATE 시 기존
        # Id 를 lastrowid 로 노출 — 후속 SELECT 없이 fact_entry_id 즉시 확보.
        source_run_id = (source_sha256 or "")[:64] if source_sha256 else None
        cur.execute(
            """
INSERT INTO AgentMemoryFactEntries
(ConversationId, FactKey, ScopeKey, TextHash, FactFingerprint, Weight,
 SourceType, SourceRunId, CreatedAt, UpdatedAt)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP(3), CURRENT_TIMESTAMP(3))
ON DUPLICATE KEY UPDATE
    Id = LAST_INSERT_ID(Id),
    TextHash = VALUES(TextHash),
    Weight = VALUES(Weight),
    SourceType = VALUES(SourceType),
    SourceRunId = VALUES(SourceRunId),
    UpdatedAt = CURRENT_TIMESTAMP(3)
            """,
            (
                KB_MANUAL_CONVERSATION_ID,
                scope_key,
                scope_key,
                text_hash,
                fact_fingerprint,
                int(weight),
                str(source_type)[:32],
                source_run_id,
            ),
        )
        fact_entry_id = int(cur.lastrowid or 0)
        # `Id = LAST_INSERT_ID(Id)` 패턴이 환경에 따라 fallback 필요 — 명시 SELECT 보강.
        if fact_entry_id == 0 and same_fp_row is not None:
            fact_entry_id = int(same_fp_row[0])
    finally:
        cur.close()

    return {
        "fact_entry_id": fact_entry_id,
        "text_hash": text_hash,
        "fact_fingerprint": fact_fingerprint,
        "superseded_count": superseded_count,
        "reactivated": reactivated,
    }


__all__ = [
    "KB_MANUAL_CONVERSATION_ID",
    "DEFAULT_MANUAL_WEIGHT",
    "DEFAULT_SOURCE_TYPE",
    "ingest_manual",
]
