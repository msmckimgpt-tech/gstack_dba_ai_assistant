"""feature-0043 — 웹 브리지 대기 작업(`WebAiTasks`)의 **상태 술어 단일 정본**.

## 왜 shared 인가

브리지 task 의 "집을 수 있는가 / 취소됐는가" 는 **두 라우터가 각각 판정한다**:

- `routers/ai_tools.py` — 개인 AI 쪽 표면(`list_open_requests` · `wait_for_request` ·
  `claim_request` · `submit_answer`)
- `routers/conversations.py` — 웹 쪽 표면(`/api/ask` 적재·supersede · `/api/cancel`)

두 곳이 같은 질문에 각자 답하면 언제든 갈리고, **갈리는 순간 느슨한 쪽이 사용자가 보는
진실**이 된다 — 이 feature 는 그 부류의 결함을 이미 한 번 겪었다(P0-R: 연결 판정이 화면과
인증에서 두 벌이라 화면만 "연결 1건" 이라고 말했다).

그래서 술어를 여기 하나로 두고 양쪽이 **불러 쓴다**. 상수만 공유하고 SQL 을 각자 조립하면
같은 실수를 형태만 바꿔 반복하게 된다.

## 무엇을 두지 않는가

DB 커넥션·트랜잭션 관리는 여기 없다. 호출측이 이미 자기 커넥션을 들고 있고(웹 세션 축은
`app.get_conn`, 도구 축은 `Depends(app.get_conn)`), 여기서 커넥션을 새로 열면 같은 요청 안에서
두 트랜잭션이 생겨 방금 쓴 행을 못 보는 창이 열린다.
"""
from __future__ import annotations

import logging
from typing import Any

__all__ = [
    "BRIDGE_CLAIM_LEASE_MIN",
    "CLAIMABLE_SQL",
    "STATUS_OPEN",
    "STATUS_CANCELED",
    "STATUS_SUBMITTED",
    "cancel_bridge_tasks",
    "claim_is_live",
]

#: 점유 lease. 이 시간이 지나도록 제출되지 않은 작업은 **다시 대기열에 나타난다**.
#:
#: 왜 필요한가: 점유는 커밋되는데 그 뒤 어떤 이유로든(러너 강제 종료·머신 절전·`--exec` 타임아웃·
#: 빈 답변으로 건너뜀·프로세스 크래시) 제출이 오지 않으면, lease 가 없는 한 그 질문은 목록에서
#: 영원히 사라진다 — 사용자는 "AI 가 가져갔는데 답이 없다" 는 상태에 갇힌다.
#:
#: 30분: 개인 머신 AI 가 어려운 질문을 붙들 수 있는 현실적 상한이면서, 사용자가 "잊혔나" 하고
#: 다시 물어보기 전에 회수되는 길이.
BRIDGE_CLAIM_LEASE_MIN = 30

#: 상태값. `WebAiTasks.Status` 는 VARCHAR(16) 이라 아래 셋이 모두 들어간다(스키마 변경 불요).
STATUS_OPEN = "open"
STATUS_CANCELED = "canceled"
STATUS_SUBMITTED = "submitted"

#: 점유 가능 조건 — 미점유이거나 lease 가 만료된 것.
#:
#: `list_open_requests` · `wait_for_request` · `claim_request` 가 **같은 술어**를 써야 한다
#: (목록에 보이는데 집으면 409 나는 불일치를 만들지 않는다). 취소 정본도 이 술어로 "되돌릴 수
#: 있는 것"(미점유)과 "협조를 구해야 하는 것"(점유)을 가른다 — 여기가 갈리면 취소한 작업이
#: 대기열에 다시 나타나거나, 되돌릴 수 있는 작업을 취소 표시만 하고 남긴다.
CLAIMABLE_SQL = (
    "(ClaimedBy IS NULL OR ClaimedAt IS NULL "
    f"OR ClaimedAt < DATE_SUB(NOW(), INTERVAL {BRIDGE_CLAIM_LEASE_MIN} MINUTE))"
)


def claim_is_live(claimed_by: Any, claimed_at: Any) -> bool:
    """점유 lease 가 아직 유효한가 — `CLAIMABLE_SQL` 의 **파이썬 쪽 대응**.

    SQL 술어와 파이썬 판정이 다른 값을 보면 "목록엔 없는데 읽기·제출은 되는" 틈이 생긴다.
    같은 상수(`BRIDGE_CLAIM_LEASE_MIN`)를 쓰도록 여기 함께 둔다.

    **판정 불가는 만료로 본다** — `ClaimedAt` 이 NULL 이거나 datetime 이 아니면 점유 시각을
    모르는 것이고, 모르는 채로 "아직 유효하다" 고 우길 근거가 없다. 이 방향은 두 소비처에
    각각 이렇게 작용한다:

    - 읽기 게이트(`read_task_attachment`) — 만료로 보므로 **읽기를 막는다**(안전측).
    - 취소 정본(`cancel_bridge_tasks`) — 미점유로 보므로 행을 **지운다**. 지워도 개인 AI 의
      제출은 404 로 막히므로(409 대신 404 라는 사유 문구 차이뿐) 전달은 어느 쪽이든 차단된다.

    두 방향이 갈리지 않도록 **하나의 의미**만 둔다. 소비처마다 다른 fallback 을 주면
    바로 그 갈림이 이 함수를 만든 이유(술어 이중화)를 되살린다.
    """
    from datetime import datetime, timedelta

    if claimed_by is None or claimed_at is None:
        return False
    if not isinstance(claimed_at, datetime):
        return False
    # DB 는 서버 로컬 NOW() 로 기록한다 — 같은 기준(naive local)으로 비교한다.
    return (datetime.now() - claimed_at) < timedelta(minutes=BRIDGE_CLAIM_LEASE_MIN)


def cancel_bridge_tasks(conn, *, account_id: int, conversation_id: str | None = None,
                        task_id: str | None = None,
                        exclude_task_id: str | None = None) -> dict[str, list[str]]:
    """대기 중인 웹 브리지 task 를 취소한다 — **취소의 단일 정본**.

    `/api/cancel`(중단 버튼) · 재전송 supersede · 적재 롤백이 **모두 이 함수를 부른다**.
    술어가 두 벌이면 "어디서 취소했느냐" 에 따라 결과가 갈린다.

    ## 두 갈래로 처리하는 이유 (사용자 결정 2026-08-28)

    | 대상 | 처리 | 왜 |
    |---|---|---|
    | 미점유(또는 lease 만료) | **DELETE** | 아무도 안 가져갔다 — 없던 일로 만들 수 있다 |
    | 점유됨 | `Status='canceled'` | 남의 머신에서 이미 돌고 있다. 우리에겐 kill 권한이 없다 |

    점유된 것을 지우지 않고 **표시로 남기는** 이유: 지우면 개인 AI 가 나중에 제출할 때
    "없는 task"(404)가 되어 *왜* 실패했는지 알 수 없다. `canceled` 로 남겨야
    `submit_answer` 가 409 + 사유를 돌려줄 수 있고, `wait_for_request` 가 그 id 를 실어
    러너를 **제출 전에** 하차시킬 수 있다.

    ## 스코프

    `account_id` 는 편의가 아니라 **경계**다 — 빼면 남의 대기 질문을 취소할 수 있다.
    `conversation_id` 또는 `task_id` 중 최소 하나가 있어야 한다(둘 다 없으면 그 계정의 전체
    대기열을 지우게 되므로 **아무것도 하지 않고** 빈 결과를 돌려준다).

    Args:
        exclude_task_id: 이 task 만 남긴다. 재전송 supersede 가 **방금 만든 새 task** 를
            자기가 지우지 않도록 쓴다.

    Returns:
        `{"deleted": [task_id...], "canceled": [task_id...]}` — 호출측이 사용자에게
        무엇이 일어났는지 말할 수 있도록 **무엇을 했는지** 돌려준다. 개수만 돌려주면
        "몇 건" 은 알아도 "어느 것" 을 몰라 화면 갱신 대상을 특정하지 못한다.
    """
    log = logging.getLogger(__name__)
    empty: dict[str, list[str]] = {"deleted": [], "canceled": []}
    if not account_id or (not conversation_id and not task_id):
        return empty

    # 값은 **파라미터로** 넘긴다. 지금은 모듈 상수라 주입 위험이 없지만, 값을 f-string 으로
    # SQL 에 박는 습관이 남아 있으면 다음 사람이 같은 자리에 변수를 넣는다.
    where = ["AccountId = %s", "Origin = 'web'", "Status = %s"]
    params: list[Any] = [int(account_id), STATUS_OPEN]
    if conversation_id:
        where.append("ConversationId = %s")
        params.append(str(conversation_id))
    if task_id:
        where.append("TaskId = %s")
        params.append(str(task_id))
    if exclude_task_id:
        where.append("TaskId <> %s")
        params.append(str(exclude_task_id))
    where_sql = " AND ".join(where)

    try:
        cur = conn.cursor()
        try:
            # 대상을 **먼저 확정**한다. DELETE 와 UPDATE 를 각각 조건으로 돌리면 그 사이
            # lease 가 만료되어 같은 행이 양쪽에 걸리거나 어느 쪽에도 안 걸릴 수 있다.
            cur.execute(
                f"SELECT TaskId, ClaimedBy, ClaimedAt FROM WebAiTasks WHERE {where_sql}",
                tuple(params))
            rows = cur.fetchall() or []
            if not rows:
                return empty

            to_delete = [str(r[0]) for r in rows if not claim_is_live(r[1], r[2])]
            to_cancel = [str(r[0]) for r in rows if claim_is_live(r[1], r[2])]

            # ⚠ 위 SELECT 와 아래 쓰기 사이에도 시간이 흐른다. 그 사이 개인 AI 가 `claim_request`
            #   로 집거나 답을 제출할 수 있으므로, **쓰기 문장 자체에 같은 조건을 다시 건다.**
            #   조건 없이 id 목록만으로 쓰면:
            #     · DELETE — 방금 점유된 작업을 지워, 러너의 제출이 404(왜 실패했는지 모름)가 된다.
            #     · UPDATE — 방금 제출된 작업의 `submitted` 를 `canceled` 로 덮어, 이미 화면에
            #       실린 답변이 "취소됨" 으로 뒤집힌다.
            #   `to_delete`/`to_cancel` 분류는 파이썬이 하되 **집행은 SQL 이 확인**한다.
            if to_delete:
                marks = ",".join(["%s"] * len(to_delete))
                cur.execute(
                    f"DELETE FROM WebAiTasks WHERE AccountId = %s AND TaskId IN ({marks}) "
                    f"AND Status = %s AND {CLAIMABLE_SQL}",
                    (int(account_id), *to_delete, STATUS_OPEN))
            if to_cancel:
                marks = ",".join(["%s"] * len(to_cancel))
                cur.execute(
                    "UPDATE WebAiTasks SET Status = %s "
                    f"WHERE AccountId = %s AND TaskId IN ({marks}) AND Status = %s",
                    (STATUS_CANCELED, int(account_id), *to_cancel, STATUS_OPEN))
            conn.commit()
        finally:
            cur.close()
    except Exception as exc:
        # 취소 실패를 삼키면 화면은 "취소했습니다" 라고 말하는데 개인 AI 는 계속 답을 만들고,
        # 그 답이 나중에 대화에 붙는다. 호출측이 사용자에게 알릴 수 있도록 올린다.
        log.error("[bridge] 대기 작업 취소 실패 account=%s conv=%s task=%s: %r",
                  account_id, conversation_id, task_id, exc)
        raise

    if to_delete or to_cancel:
        log.info("[bridge] 대기 작업 취소 account=%s conv=%s — 삭제 %d · 취소표시 %d",
                 account_id, conversation_id, len(to_delete), len(to_cancel))
    return {"deleted": to_delete, "canceled": to_cancel}
