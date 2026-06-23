"""ITEM-03 (ROADMAP dba-ai-nl2sql): 피드백 → 샘플쿼리 KB 환류 flywheel (코어).

답변 👍/👎 + "샘플로 등록" → sample_feedback(pending) 적재 → (관리콘솔 검수 큐) →
승인 시 sample_queries(approved=true, source_type='feedback')로 승급, 👎는 negative 태깅/거부.

가드(ROADMAP fit-guard): ① **PII 마스킹**(generated_sql 의 SQL literal — kb_scope._mask_prose 재사용)
② 승인 큐 경유(자동학습 금지 — poisoning 방어) ③ ds-scope. RBAC `kb.sample.curate`·audit 는
web 경계(feature-0003 app.py)에서 강제 — 본 코어는 적재/승급 로직 정본(중복 RBAC 판정 안 함).
"""
from __future__ import annotations

import logging

from modules.utils import _normalize_scope_key

_log = logging.getLogger("sample_feedback")


def _mask_sql(sql):
    """generated_sql 의 PII(이메일·RRN·전화·IP·장숫자) 마스킹. kb_scope 미가용 시 원문(best-effort)."""
    try:
        from modules.kb_scope import _mask_prose
        return _mask_prose(str(sql or ""))
    except Exception:
        return str(sql or "")


def record_feedback(conn, scope_key, nl_question, generated_sql, *, vote="up",
                    suggested=False, conversation_id=None, run_id=None, created_by=None) -> None:
    """답변 피드백 적재(status=pending). generated_sql 은 PII 마스킹 후 저장."""
    vote_n = "down" if str(vote).strip().lower() in ("down", "negative", "0", "false") else "up"
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO sample_feedback "
            "(scope_key, conversation_id, run_id, nl_question, generated_sql, vote, suggested, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (_normalize_scope_key(scope_key), conversation_id, run_id,
             str(nl_question).strip(), _mask_sql(generated_sql), vote_n,
             bool(suggested), created_by),
        )
    finally:
        cur.close()


def list_pending_feedback(conn, scope_key=None, limit=50):
    """검수 큐 — pending 피드백. scope_key 지정 시 그 ds 만."""
    cur = conn.cursor()
    try:
        if scope_key:
            cur.execute(
                "SELECT id, scope_key, conversation_id, nl_question, generated_sql, vote, suggested, created_at "
                "FROM sample_feedback WHERE status = 'pending' AND scope_key = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (_normalize_scope_key(scope_key), int(limit)),
            )
        else:
            cur.execute(
                "SELECT id, scope_key, conversation_id, nl_question, generated_sql, vote, suggested, created_at "
                "FROM sample_feedback WHERE status = 'pending' ORDER BY created_at DESC LIMIT %s",
                (int(limit),),
            )
        return list(cur.fetchall() or [])
    finally:
        cur.close()


def promote_feedback(conn, feedback_id, *, approved_by=None, weight=100, domain="",
                     embedding=None) -> "int | None":
    """승인: 👍 피드백을 sample_queries(approved=true, source_type='feedback')로 승급.
    sample_feedback.status=promoted + promoted_sample_id 기록. 👎(down)는 승급 거부(reject 사용).
    반환: 승급된 sample_queries.id (조회 실패/down 이면 None)."""
    from modules.sample_queries import register_sample

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT scope_key, nl_question, generated_sql, vote FROM sample_feedback "
            "WHERE id = %s AND status = 'pending'",
            (int(feedback_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        scope_key, nl_question, generated_sql, vote = row
        if str(vote) == "down":
            # 👎 는 승급 대상 아님 — 승급 거부(None). (negative 신호 기반 자동 가중 강등은 미구현 —
            # PR-B/follow-up. 현재는 poisoning 방어상 down 은 sample_queries 에 반영 안 함.)
            return None
        # 승급: approved=true. embedding 미제공 시 register_sample 내부가 임베딩(Bedrock).
        register_sample(conn, scope_key, nl_question, generated_sql, domain=domain,
                        weight=int(weight), source_type="feedback", approved=True,
                        created_by=approved_by, embedding=embedding)
        cur.execute(
            "SELECT id FROM sample_queries WHERE scope_key = %s AND nl_question = %s",
            (_normalize_scope_key(scope_key), str(nl_question).strip()),
        )
        srow = cur.fetchone()
        sample_id = int(srow[0]) if srow else None
        cur.execute(
            "UPDATE sample_feedback SET status = 'promoted', promoted_sample_id = %s, updated_at = now() "
            "WHERE id = %s",
            (sample_id, int(feedback_id)),
        )
        return sample_id
    finally:
        cur.close()


def reject_feedback(conn, feedback_id) -> None:
    """검수 거부(또는 👎). status=rejected. sample_queries 미반영(poisoning 방어)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE sample_feedback SET status = 'rejected', updated_at = now() "
            "WHERE id = %s AND status = 'pending'",
            (int(feedback_id),),
        )
    finally:
        cur.close()
