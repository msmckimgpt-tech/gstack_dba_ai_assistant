"""공유 대화(그룹) 첨부 참조 스코프의 판정 정본 — 그룹 여부 + 공유창 window 게이트.

feature-0009 CSO F1(그룹 첨부 LLM 주입을 발신자-한정으로 차단)을 **대화 스코프 + 공유창
window 정합**으로 대체할 때, 그 판정을 web(feature-0003 `_resolve_conversation_attachment_scope`)
과 agent_core(feature-0002 `_build_attachment_context_section`) **양쪽이 같은 규칙**으로 쓰도록
단일 정본을 둔다. 두 곳이 각자 구현하면 한쪽만 완화됐을 때 경계가 조용히 갈린다.

**그룹 여부까지 이 함수가 판정한다**(§18.8 적대 리뷰 [P1]). 호출측이 `_is_group_conversation()`
으로 먼저 게이팅하면, 그 함수가 PG 오류 시 `False` 를 돌려주는 순간 window 게이트를 **통째로
건너뛰고 대화 전체로 열린다** — 판정 실패가 가장 넓은 스코프로 귀결되는 fail-open 이다. 그래서
멤버 수·소유자·window 를 **한 쿼리에서 함께** 읽고, 하나라도 확인 못 하면 좁은 쪽으로 간다.

── 왜 "첨부 created_at 을 window 경계와 직접 비교" 하지 않는가 ────────────────────────
첨부는 표시 메시지에 바인딩되지 않는다(`WebAttachmentDerivedMessages` 는 첨부에서 *파생된*
메시지용이고, 업로드 메시지와의 연결이 아니다). 그래서 첨부의 window 귀속을 판정할 축은
`CreatedAt` 뿐인데, 이 값은 표시/코어 메시지의 `created_at` 과 **같은 시간축이 아니다**:
라이브 실측(2026-08-13) 기준 첨부는 로컬시각이 UTC 로 라벨링돼 저장돼 메시지보다 미래로
찍힌다(관측 +9h). 이 상태에서 시각 비교로 window 를 자르면 하한에서는 가려야 할 첨부를
열고 상한에서는 열어야 할 첨부를 가린다 — 두 방향 모두 틀린다.

그래서 시각 대신 **은닉 구간의 실재 여부**로 게이트한다(= `_msg_outside_window` 와 동형인
메시지 id/joined_at 기준, 시간축 왜곡의 영향을 받지 않음). 이 발신자가 대화의 표시 메시지를
하나도 빠짐없이 볼 수 있으면 첨부를 가릴 근거가 없다 → 대화 전체. 하나라도 가려져 있으면
그 구간에 어떤 첨부가 속하는지 판정할 수단이 없다 → **fail-closed**(종전 CSO F1 동작).

첨부 CreatedAt 의 시간축 왜곡 자체는 별도 결함이다(fork 의 `_attachment_outside_window`
도 같은 축을 쓴다). 그것이 해소되면 "은닉 있으면 sender-only" 를 "은닉 구간에 속한 첨부만
제외" 로 정밀화할 수 있다 — 그때까지는 좁은 쪽이 정답이다.
"""

from __future__ import annotations

import logging
import os

_LOG = logging.getLogger(__name__)

# 판정 결과 — caller 가 bool 로만 쓰지 않도록 이름을 준다.
SCOPE_CONVERSATION = "conversation"   # 대화 전체 첨부 참조 가능
SCOPE_SENDER_ONLY = "sender-only"     # 발신자 본인 첨부만 (fail-closed / 종전 CSO F1)

# 그룹 여부(멤버 수) + 소유자 + 발신자 window + **ceiling 뒤 은닉 표시 메시지 수** 를 1 쿼리로.
#
# hidden_after_ceiling 은 `_msg_outside_window`(feature-0003 _conv_store.py)의 은닉 조건 중
# ceiling 축과 동형이다: 가시범위 = [floor, ceiling] ∪ [joined, ∞) 이므로, ceiling 을 넘고
# joined 이전인 표시 메시지가 은닉 대상이다.
#
# floor 축은 **세지 않는다** — 아래 판정에서 floor 가 설정돼 있으면 무조건 좁히기 때문이다.
# 그 이유는 두 가지다: (a) floor 이전 구간의 첨부 귀속을 시간축으로 판정할 수 없고,
# (b) `_msg_outside_window` 는 floor 가 있을 때 assistant 답변의 recall 태그
# (`recall_full` / `recall_floor_created_at < floor_ca`)로도 메시지를 숨기는데, 그 축까지
# SQL 로 재현하면 두 구현이 갈릴 위험이 실익보다 크다(§18.8 적대 리뷰 [P2]).
_PG_ATTACH_WINDOW_GATE = """
SELECT (c.owner_account_id = %(account_id)s)              AS is_owner,
       (SELECT count(*) FROM agent_runtime.conversation_members cm
         WHERE cm.conversation_id = c.conversation_id)    AS member_count,
       m.role,
       m.visible_floor_message_id,
       m.visible_ceiling_message_id,
       (SELECT count(*)
          FROM agent_runtime.messages d
         WHERE d.conversation_id = c.conversation_id
           AND m.visible_ceiling_message_id IS NOT NULL
           AND d.id > m.visible_ceiling_message_id
           AND (m.joined_at IS NULL OR d.created_at < m.joined_at)
       )                                                  AS hidden_after_ceiling
  FROM agent_runtime.core_conversations c
  LEFT JOIN agent_runtime.conversation_members m
         ON m.conversation_id = c.conversation_id AND m.account_id = %(account_id)s
 WHERE c.conversation_id = %(conversation_id)s
 LIMIT 1
"""


def _runtime_backend_is_pg() -> bool:
    """공유창 window·멤버십은 PG 런타임에서만 생성된다(feature-0003 `_runtime_backend_is_pg` 동형)."""
    return os.environ.get("AGENT_RUNTIME_READ_BACKEND", "").strip().lower() == "postgres"


def group_attachment_scope(conversation_id: str | None, account_id: int | None) -> str:
    """이 발신자의 첨부 참조 스코프를 판정한다(그룹 여부 판정 포함).

    Returns: `SCOPE_CONVERSATION`(대화 전체) | `SCOPE_SENDER_ONLY`(본인 첨부만).

    판정 순서:
      - 비-PG 백엔드            : CONVERSATION — 멤버십·window 가 존재할 수 없다(1:1 과 동치).
      - 대화/발신자 미식별       : SENDER_ONLY — 판정 근거 없음(시스템·CLI 호출 포함).
      - `visible_*` 컬럼 부재    : CONVERSATION — pre-migration, windowed 멤버 생성 불가(안전).
      - 대화 row 없음            : SENDER_ONLY — fail-closed.
      - 멤버 ≤ 1                 : CONVERSATION — 그룹이 아니다(1:1·fork·이어받기 무회귀).
      - 소유자                   : CONVERSATION — 본인 대화에 정당한 전체 접근.
      - 멤버 행 없음(비-owner)    : SENDER_ONLY — 그룹인데 멤버가 아니다(누락·불일치 포함, fail-closed).
      - floor 설정               : SENDER_ONLY — 과거 구간이 가려진 멤버(위 SQL 주석의 (a)(b)).
      - ceiling 설정 + 은닉 > 0   : SENDER_ONLY — 가려진 표시 메시지가 실재한다.
      - 그 외                    : CONVERSATION — 가릴 근거가 없다.
      - PG 조회 실패/그 외 예외   : SENDER_ONLY — fail-closed.
    """
    if not conversation_id or not account_id:
        return SCOPE_SENDER_ONLY
    if not _runtime_backend_is_pg():
        return SCOPE_CONVERSATION
    try:
        from shared.db import _pg_connect
    except Exception:  # noqa: BLE001 — import 실패는 런타임 구성 문제, 좁은 쪽으로.
        return SCOPE_SENDER_ONLY
    try:
        pg = _pg_connect()
    except Exception:  # noqa: BLE001
        _LOG.warning("group_attachment_scope: PG 연결 실패 → sender-only(fail-closed)", exc_info=True)
        return SCOPE_SENDER_ONLY
    try:
        with pg.cursor() as cur:
            cur.execute(
                _PG_ATTACH_WINDOW_GATE,
                {"conversation_id": str(conversation_id), "account_id": int(account_id)},
            )
            row = cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        if getattr(exc, "sqlstate", None) == "42703":  # UndefinedColumn — pre-migration
            return SCOPE_CONVERSATION
        _LOG.warning("group_attachment_scope: window 조회 실패 → sender-only(fail-closed)", exc_info=True)
        return SCOPE_SENDER_ONLY
    finally:
        try:
            pg.close()
        except Exception:  # noqa: BLE001
            pass

    if row is None:
        return SCOPE_SENDER_ONLY
    is_owner, member_count, role, floor_id, ceil_id, hidden_after_ceiling = (
        row[0], row[1], row[2], row[3], row[4], row[5],
    )
    try:
        members = int(member_count or 0)
    except (TypeError, ValueError):
        return SCOPE_SENDER_ONLY
    if members <= 1:
        return SCOPE_CONVERSATION  # 그룹이 아니다 — 종전 대화 스코프(TASK-0284) 그대로.
    if is_owner:
        return SCOPE_CONVERSATION
    if role is None:
        # 그룹인데 이 발신자의 멤버 행이 없다. 멤버십 게이트는 호출자 책임이지만, 여기서
        # 스코프를 넓히면 그 게이트의 구멍이 곧 첨부 노출이 된다 — 좁은 쪽으로 간다.
        return SCOPE_SENDER_ONLY
    if role == "owner":
        return SCOPE_CONVERSATION
    if floor_id is not None:
        return SCOPE_SENDER_ONLY
    if ceil_id is None:
        return SCOPE_CONVERSATION  # 경계 미설정 full 멤버.
    try:
        hidden = int(hidden_after_ceiling or 0)
    except (TypeError, ValueError):
        return SCOPE_SENDER_ONLY
    return SCOPE_SENDER_ONLY if hidden > 0 else SCOPE_CONVERSATION


def group_attachment_is_sender_only(conversation_id: str | None, account_id: int | None) -> bool:
    """`group_attachment_scope` 의 bool 판. caller 가 종전 `sender_scope` 자리에 그대로 쓴다."""
    return group_attachment_scope(conversation_id, account_id) == SCOPE_SENDER_ONLY
