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

import json
import logging
import secrets
from typing import Any

__all__ = [
    "BRIDGE_CLAIM_LEASE_MIN",
    "CLAIMABLE_SQL",
    "DEFERRED_MAX_AGE_HOURS",
    "STATUS_OPEN",
    "STATUS_CANCELED",
    "STATUS_DEFERRED",
    "STATUS_EXPIRED",
    "STATUS_SUBMITTED",
    "CANCELABLE_STATUSES",
    "cancel_bridge_tasks",
    "claim_is_live",
    "promote_latest_deferred",
    # ── 러너 인스턴스 축 · 고아 점유 회수 (TASK-20260901T140000) ──
    "RUNNER_INSTANCE_SEP",
    "RUNNER_INSTANCE_MAX_CHARS",
    "BRIDGE_NO_PROGRESS_SEC",
    "claimed_client_value",
    "instance_of_claimed_client",
    "client_of_claimed_client",
    "claimed_client_matches",
    "release_runner_instance_claims",
    # ── 콘솔 작업 위임 (TASK-20260831T100000) ──
    "KIND_CHAT",
    "KIND_JOB",
    "ORIGIN_WEB",
    "ORIGIN_EXTERNAL",
    "ORIGIN_BATCH",
    "RUNNER_FEATURE_CONSOLE_JOBS",
    "RUNNER_FEATURE_BATCH_JOBS",
    "RUNNER_FEATURE_SELF_REVIEW",
    "RUNNER_MIN_AGENT_VERSION",
    "JOB_SPECS",
    "job_spec",
    "job_label",
    "BATCH_JOB_KINDS",
    "BATCH_PENDING_MAX",
    "BATCH_TASK_MAX_AGE_MIN",
    "CONSOLE_PROMPT_MAX_CHARS",
    "ConsoleJobRejected",
    "enqueue_console_job",
    "expire_stale_batch_jobs",
    "load_console_job",
    "mark_console_job_applied",
    "store_console_job_result",
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

#: 상태값. `WebAiTasks.Status` 는 VARCHAR(16) 이라 아래 다섯이 모두 들어간다(스키마 변경 불요).
STATUS_OPEN = "open"
STATUS_CANCELED = "canceled"
STATUS_SUBMITTED = "submitted"

#: AI 가 연결되지 않은 상태에서 들어온 질문. **대기열에는 보이지 않는다** — 도구 표면은
#: `Status='open'` 만 보므로, 연결 없는 동안 쌓여도 나중에 한꺼번에 처리되지 않는다.
#: 연결이 성립하면 `promote_latest_deferred` 가 가장 최근 1건만 `open` 으로 올린다.
STATUS_DEFERRED = "deferred"

#: 승격 경쟁에서 밀린 보류 질문(또는 너무 오래된 것). 되살아나지 않는다.
STATUS_EXPIRED = "expired"

#: 사용자 취소·supersede 의 대상 상태. 보류 질문도 포함해야 한다 — 빼면 새 질문을 보내도
#: 이전 보류 질문이 남아, 연결되는 순간 **엉뚱한 옛 질문**이 승격된다.
CANCELABLE_STATUSES = (STATUS_OPEN, STATUS_DEFERRED)

#: 보류 질문의 유효 기간. 이보다 오래된 것은 승격하지 않고 만료시킨다.
#:
#: 왜 상한이 필요한가: 사용자가 사흘 전에 던져 두고 잊은 질문이 오늘 연결하는 순간 답변으로
#: 되돌아오면, 그것은 "이어받기" 가 아니라 **기억에 없는 응답**이다. 24시간은 "같은 작업 흐름
#: 안" 이라고 볼 수 있는 현실적 경계다(로그아웃→재로그인 창은 분 단위라 넉넉히 덮인다).
DEFERRED_MAX_AGE_HOURS = 24

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


# ── 러너 인스턴스 축 · 고아 점유 회수 (TASK-20260901T140000) ─────────────────────
#
# ## 왜 lease 만으로는 부족한가 (라이브 실측 2026-09-01, 대화 20260901030637-95dc8844)
#
# lease 는 도구 호출마다 갱신된다(`_renew_claim_lease`) — "진행하고 있으니 살아 있다".
# 그런데 러너 **프로세스가 사라지는** 순간, 그 갱신값이 그대로 남아 **최대 30분짜리
# 사각지대**가 된다: task 는 `Status='open' · ClaimedBy=<계정>` 이라 `CLAIMABLE_SQL` 을
# 통과하지 못해 `wait_for_request` 목록에서 사라지고, 재기동한 **같은 러너조차** 자기가
# 두고 온 작업을 되찾지 못한다. 화면은 그 30분을 「처리 중」으로 그린다.
#
# 실측 타임라인(러너 재설치 → 재기동):
#   12:07:26 전달 → 12:13:20 마지막 도구(14회, 정상) → 러너 재기동 → **12:43:20 까지 무진행**
#   → lease 만료로 재배달 → 조사 처음부터 재실행 → 12:47:47 토큰 만료로 러너 종료 → **또 고아**
#   → 13:34 사용자가 포기하고 재전송 → 새 task 가 **80초 만에 종결**. **사용자 대기 87분.**
#   (⚠ 그 80초가 낸 것은 리뷰가 아니라 **거부 답변**이었다 — 별건 결함. 여기서 고치는 것은
#    「질문이 아무에게도 보이지 않는 30분」 이지 그 답변의 내용이 아니다.)
#
# ## 해법 — "이 인스턴스는 더 이상 살아 있지 않다" 를 러너가 말한다
#
# 러너 프로세스는 기동할 때마다 **고유 instance** 를 발급하고 로컬 설정에 남긴다. 재기동한
# 러너는 직전 instance 를 읽어 서버에 "그건 죽었다" 고 신고하고, 서버는 그 instance 가 점유한
# 미제출 task 를 즉시 놓아준다 — 30분이 **다음 하트비트까지**(≤30초)로 줄어든다.
#
# ## 왜 계정 단위 일괄 해제가 아닌가
#
# 한 계정에 러너가 둘 이상 붙어 있을 수 있다(사무실 PC + 노트북). 계정 단위로 쓸어 버리면
# **살아서 일하는 다른 러너의 작업**까지 대기열로 돌려보내 중복 조사를 만든다. instance 는
# 그 러너의 **로컬 설정에만** 있으므로, 남의 instance 를 신고할 방법 자체가 없다 — 경계가
# 데이터 구조로 서 있다.
#
# 남는 경계 사례: 한 머신에서 설정 파일을 공유한 채 러너를 둘 띄우면 뒤에 뜬 쪽이 앞의
# instance 를 "직전 것" 으로 오인해 해제할 수 있다. 그때의 최악은 **그 task 가 다시 대기열로
# 가 중복 조사 1회**이고, 중복 제출은 `submit_answer` 의 확정 불변(첫 제출만)이 막는다 —
# 지금의 "30분 공백 + 재조사" 보다 명백히 낫다. 설치 경로(`bridge_setup`)는 머신당 러너 1개를
# 전제하므로 이 경우는 문서화된 시나리오가 아니다.

#: `ClaimedClient` 에 토큰 client 와 러너 instance 를 함께 적을 때의 구분자.
#: 본문에 나올 수 없는 글자여야 한다 — `client_id` 는 사람이 정하는 이름이라 `-`·`_` 를 쓴다.
RUNNER_INSTANCE_SEP = "#"

#: instance 문자열 상한. `ClaimedClient` 는 VARCHAR(64) 이고 앞에 client_id 가 붙는다.
RUNNER_INSTANCE_MAX_CHARS = 16

#: 「점유돼 있는데 진행이 없다」 를 화면이 말하기 시작하는 경계(초).
#:
#: `ClaimedAt` 은 도구 호출마다 갱신되므로 "마지막 진행 이후" 를 그대로 재는 값이다. 임계는
#: **정상적인 무도구 구간의 최대치보다 커야** 한다 — 마지막 도구 뒤 답변을 쓰는 구간이 그것이고,
#: 라이브 실측(2026-08-31~09-01 브리지 run 15건)의 최대가 621초였다. 900초는 그 위이면서
#: lease(30분)보다 아래라, 사용자는 **회수가 일어나기 전에** 무진행을 알게 된다.
#:
#: 이 값은 **표시 경계**이지 종료 조건이 아니다 — 넘어도 task 는 그대로 살아 있고, 오탐 비용은
#: 안내 한 줄이다(살아 있는 러너를 끊지 않는다).
BRIDGE_NO_PROGRESS_SEC = 900


def claimed_client_value(client_id: Any, runner_instance: Any) -> str | None:
    """`ClaimedClient` 에 적을 값 — `<client_id>#<instance>`.

    instance 가 없으면 종전과 같이 `client_id` 만 돌려준다(구 러너 호환 — 신고하지 않는
    러너의 점유는 인스턴스 축을 갖지 않을 뿐 나머지 동작은 그대로다).

    `client_id` 가 길면 **instance 쪽을 지킨다**: 잘려서 사라지는 순간 회수가 통째로 죽지만,
    client_id 는 표시용이라 잘려도 기능이 죽지 않는다.
    """
    inst = _sanitize_instance(runner_instance)
    cid = str(client_id or "").strip()
    if not inst:
        return cid or None
    if not cid:
        return f"{RUNNER_INSTANCE_SEP}{inst}"
    room = 64 - len(inst) - len(RUNNER_INSTANCE_SEP)
    return f"{cid[:max(0, room)]}{RUNNER_INSTANCE_SEP}{inst}"


def instance_of_claimed_client(claimed_client: Any) -> str:
    """`ClaimedClient` 에서 러너 instance 만 꺼낸다. 없으면 빈 문자열."""
    raw = str(claimed_client or "")
    if RUNNER_INSTANCE_SEP not in raw:
        return ""
    return raw.rsplit(RUNNER_INSTANCE_SEP, 1)[1].strip()


def client_of_claimed_client(claimed_client: Any) -> str:
    """`ClaimedClient` 에서 **앞자리(토큰 client)** 만 꺼낸다. 구분자가 없으면 전체."""
    return str(claimed_client or "").split(RUNNER_INSTANCE_SEP, 1)[0]


def claimed_client_matches(claimed_client: Any, client_id: Any) -> bool:
    """이 점유가 **이 토큰 client 의 것**인가 — 점유자 경계의 단일 술어.

    ## 왜 함수인가 (TASK-20260901T140000)

    인스턴스 축을 새기면서 `ClaimedClient` 의 값 형식이 `<client_id>` → `<client_id>#<instance>`
    로 넓어졌다. 이 값을 **전량 일치로 비교하던 소비처가 세 곳**이었고(제출 · 첨부 읽기 ·
    취소 통보), 형식만 바꾸고 그대로 두면 인스턴스를 신고하는 러너의 제출이 「점유자가
    아니다」로 거절되고 첨부 읽기가 「다른 세션이 점유 중」으로 막힌다 — **조사를 끝낸 답변이
    통째로 버려지는** 형태다. 자체 적대 검증에서 실제로 그 두 곳이 잡혔다.

    그래서 비교를 여기 하나로 둔다. SQL 안에서 같은 판정이 필요한 자리는
    `SUBSTRING_INDEX(ClaimedClient, '#', 1) = %s` 로 **같은 의미**를 쓴다(그쪽은 파이썬으로
    끌어올 수 없다 — 원자적 UPDATE 조건이어야 TOCTOU 창이 없다).

    `None` 은 **통과**다: 컬럼 추가 이전에 점유된 행이라 세션을 대조할 근거가 없다(종전 규약).
    """
    if claimed_client is None:
        return True
    return client_of_claimed_client(claimed_client) == str(client_id or "")


def _sanitize_instance(value: Any) -> str:
    """instance 로 받아들일 수 있는 형태로 정규화. 아니면 빈 문자열.

    영숫자만 허용한다 — 이 값은 `LIKE` 패턴과 `ClaimedClient` 양쪽에 들어가므로 `%`·`_`·
    구분자가 섞이면 **의도하지 않은 범위**를 지운다. 러너가 만드는 값은 `token_hex` 라
    이 제한에 자연히 맞고, 맞지 않는 값은 인스턴스 축이 없는 것으로 취급한다(무시가 안전).
    """
    raw = str(value or "").strip()
    if not raw or not raw.isalnum() or not raw.isascii():
        return ""
    return raw[:RUNNER_INSTANCE_MAX_CHARS]


def release_runner_instance_claims(conn, *, account_id: int,
                                   instances: "list[str] | tuple[str, ...]") -> list[str]:
    """죽었다고 신고된 러너 instance 들의 **미제출 점유를 놓아준다**. 반환 = 해제한 task_id 들.

    무엇을 하지 않는가: `Status` 를 바꾸지 않는다. 이 작업은 취소된 것이 아니라 **다시 집어야
    하는 것**이므로 `open` 그대로 두고 점유만 비운다 — 그 순간 `CLAIMABLE_SQL` 을 통과해
    `wait_for_request` 목록에 되돌아온다.

    `SubmittedAt IS NULL` 을 조건에 두는 이유: 제출까지 끝낸 뒤 종료한 러너의 흔적을 되살려
    **이미 답한 질문을 다시 배달**하지 않기 위해서다(확정 불변).

    경계는 `ClaimedBy = account_id` — **"내가 점유한 것"** 이다. 질문의 소유 계정(`AccountId`)
    이 아니라 점유자를 보는 이유: 배경 배치 작업은 소유 계정이 없고(`AccountId=0`,
    TASK-20260831T100000) 점유자만 있다. `AccountId` 로 닫으면 그 작업들이 회수에서 통째로
    빠져 종전의 사각지대가 배치 축에만 남는다. 점유자 조건은 그보다 **좁은** 경계이기도 하다 —
    남의 계정이 점유한 것은 어차피 걸리지 않는다.

    실패는 흡수하지 않는다: 호출측(하트비트)이 예외를 잡아 로그만 남기고 계속 간다. 회수가
    실패해도 최악은 종전 동작(lease 만료 대기)이라 연결 자체를 끊을 이유가 없다.
    """
    log = logging.getLogger(__name__)
    wanted = [i for i in (_sanitize_instance(x) for x in (instances or [])) if i]
    if not account_id or not wanted:
        return []
    # instance 는 `_sanitize_instance` 로 영숫자만 남았으므로 LIKE 메타문자가 없다. 그래도
    # 값은 **파라미터로** 넘긴다 — f-string 으로 SQL 에 박는 습관이 남으면 다음 사람이 같은
    # 자리에 사용자 입력을 넣는다.
    like_clause = " OR ".join(["ClaimedClient LIKE %s"] * len(wanted))
    params: list[Any] = [f"%{RUNNER_INSTANCE_SEP}{i}" for i in wanted]
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT TaskId FROM WebAiTasks "
            "WHERE ClaimedBy = %s AND Status = %s AND SubmittedAt IS NULL "
            "  AND (" + like_clause + ")",
            (int(account_id), STATUS_OPEN, *params))
        released = [str(r[0]) for r in (cur.fetchall() or [])]
        if not released:
            return []
        cur.execute(
            "UPDATE WebAiTasks SET ClaimedBy = NULL, ClaimedAt = NULL, ClaimedClient = NULL "
            "WHERE TaskId IN (" + ",".join(["%s"] * len(released)) + ")",
            tuple(released))
        conn.commit()
    finally:
        try:
            cur.close()
        except Exception:
            pass
    log.info("[bridge] 고아 점유 회수 account=%s instances=%s tasks=%s",
             account_id, wanted, released)
    return released


# ── 콘솔 작업 위임 (TASK-20260831T100000, console-llm-parity) ───────────────────────
#
# 관리 콘솔의 LLM 기능도 개인 AI 가 처리한다. 대화 브리지와 **같은 테이블·같은 점유 술어**를
# 쓰되 `Kind` 로 갈린다 — 나누면 lease·취소·원장이 두 벌이 되고, 그 다섯 중 하나만 갈려도
# "목록엔 없는데 제출은 되는" 부류의 결함이 되돌아온다.

#: `WebAiTasks.Kind` — 무엇을 하는 작업인가. `Origin`(누가 열었나)과 **직교**한다.
KIND_CHAT = "chat"
KIND_JOB = "job"

#: `WebAiTasks.Origin` — 누가 열었나. 종전 두 값에 배치 축이 더해진다.
ORIGIN_WEB = "web"
ORIGIN_EXTERNAL = "external"
#: 워커가 연 배경 작업. 특정 사용자의 질문이 아니므로 계정 스코프로 닫히지 않고,
#: **권한 + 기능 신고**로 닫힌다(배급 자격은 `ai_tools` 가 집행).
ORIGIN_BATCH = "batch"

#: 러너가 하트비트에 싣는 기능 이름. **이 값이 배급 자격이다.**
#:
#: 왜 자격이 필요한가: 콘솔 작업을 모르는 러너가 그것을 집으면 대화용 프레이밍(「너는 사내 DB
#: 질의 어시스턴트다」 · 제목 마커)으로 감싸 JSON 산출물을 망친다. 그 실패는 조용하다 —
#: 답은 오는데 내용이 규약을 벗어나 있고, 파서는 빈 결과를 돌려준다.
RUNNER_FEATURE_CONSOLE_JOBS = "console_jobs"
#: 배경 배치까지 받겠다는 **별도 동의**. 콘솔 작업 능력과 나누는 이유: 배치는 그 사람이 요청한
#: 적 없는 일이고 자기 계정 토큰을 태운다. 능력이 있다고 동의한 것으로 보면 안 된다.
RUNNER_FEATURE_BATCH_JOBS = "batch_jobs"

#: 답변 초안을 **자기 스스로 5축 검증**할 수 있다는 신고 (TASK-20260901T110000).
#:
#: 자격이 아니라 **관측 축**이다 — 이 기능이 없어도 답변은 정상적으로 오고 제출도 받는다.
#: 신고를 받는 이유는 콘솔이 「검증 결과가 없다」를 두 가지로 갈라 말할 수 있어야 하기
#: 때문이다: (a) 러너가 검증할 줄 모른다(구버전 — 조치=갱신), (b) 검증했는데 결과가
#: 비었다(판정 자체가 pass). 합치면 운영자는 전자를 후자로 읽고 "다들 통과하네" 로 끝낸다.
RUNNER_FEATURE_SELF_REVIEW = "self_review"

#: 이 버전 미만의 러너에는 콘솔 작업을 주지 않고 **갱신을 지시한다**(사용자 결정 2026-08-31).
#: 기능 신고가 1차 자격이고 버전은 2차다 — 기능만 보면 신고 형식이 바뀐 뒤에도 구 러너가
#: 자격을 유지한다.
RUNNER_MIN_AGENT_VERSION = "2026.08.31"

#: 배치 대기열 상한. 배급 가능한 러너가 없어도 워커는 계속 도므로, 상한이 없으면 아무도 못
#: 집는 작업이 무한히 쌓인다(P0-S 가 대화 축에서 이미 고친 형태).
BATCH_PENDING_MAX = 24
#: 배치 작업의 유효 기간(분). 넘으면 만료 — 배경 산출물은 재생성 가능하므로 오래된 요청을
#: 붙들고 있을 이유가 없고, 붙들면 화면의 "대기 중" 이 영구 고착된다.
BATCH_TASK_MAX_AGE_MIN = 180


#: 콘솔 작업 종류 레지스트리 — **한 곳에서 정의하고 모두가 읽는다.**
#:
#: 각 항목:
#:   label       : 사람이 읽는 이름(화면·원장 공용). 두 곳이 각자 지으면 반드시 갈린다.
#:   origin      : 이 종류를 누가 여는가 (`web`=관리자 조작 / `batch`=워커).
#:   response    : 'text' | 'json'. 러너 프롬프트의 출력 규약과 회수 파서를 함께 정한다.
#:   apply       : 산출물이 도달할 곳. 'review'=사람이 검토 후 저장(폼에 채움) /
#:                 'store'=기존 저장 경로에 자동 기입.
#:   wired       : **이 종류의 전 구간(적재 호출부 · 프롬프트 조립 · 산출물 반영)이 실제로
#:                 존재하는가.** False 면 `enqueue_console_job` 이 거절하고, 관리 콘솔은 그
#:                 종류의 조작면을 "위임 불가" 로 표시한다.
#:
#:                 ⚠ **부분 배선을 True 로 적지 않는다.** 이 feature 가 P0-M·P0-T 에서 두 번
#:                 밟은 함정이 정확히 그것이다 — 화면은 "할 수 있다" 고 말하는데 실행 경로가
#:                 없어, 사용자가 누르면 아무 일도 일어나지 않거나 조용히 다른 것이 된다.
#:                 전 구간이 서기 전까지는 False 가 **정직한 값**이고, 그 상태에서 화면은
#:                 사유와 함께 비활성으로 보인다.
#:
#: `apply` 를 종류마다 굳히는 이유(사용자 결정 2026-08-31 "자율적으로 입력"): 전환은 **기존
#: 경로의 쓰기 의미를 보존**해야 한다. 메타데이터 자동완성은 원래 검토형이었고 배치는 원래
#: 자동기입형이었다 — 위임하면서 한쪽으로 통일하면 그 자체가 사용감 회귀다.
JOB_SPECS: dict[str, dict[str, Any]] = {
    "metadata_suggest": {
        "label": "메타데이터 자동완성(단건)",
        # ⚠ **text 다.** 기존 프롬프트(`_metadata_suggest_messages`)가 "설명 본문만 출력하고
        #   머리말·따옴표를 붙이지 마세요" 를 지시한다 — 서버가 그 텍스트를
        #   `{target, suggestion}` 봉투로 감쌀 뿐이다. json 으로 잡으면 위임 프롬프트가
        #   조립부와 **모순된 형식**을 요구하고, 그 모순은 AI 가 무엇을 내든 한쪽이 틀린다.
        "origin": ORIGIN_WEB, "response": "text", "apply": "review",
        "wired": True,
    },
    "metadata_bulk": {
        "label": "메타데이터 자동완성(일괄)",
        "origin": ORIGIN_WEB, "response": "json", "apply": "review",
        "wired": True,
    },
    "node_analysis": {
        "label": "그래프 AI 능동 분석",
        "origin": ORIGIN_WEB, "response": "json", "apply": "store",
        "wired": False,
    },
    "prompt_generate": {
        "label": "시스템 프롬프트 자동작성",
        "origin": ORIGIN_WEB, "response": "text", "apply": "review",
        "wired": True,
    },
    "insight_summary": {
        "label": "인사이트 배치",
        "origin": ORIGIN_BATCH, "response": "json", "apply": "store",
        "wired": False,
    },
    "cluster_label": {
        "label": "클러스터 라벨링",
        "origin": ORIGIN_BATCH, "response": "json", "apply": "store",
        "wired": False,
    },
    # red-team 은 대기열에 따로 적재되지 않는다 — **답변한 그 러너**가 자기 답변을 검증해
    # `submit_answer` 에 함께 싣는다(사용자 결정 2026-08-31: "요청 당시의 호출자가 스스로의
    # 대화내역을 알 수 있으므로"). 별도 task 로 만들면 그 AI 가 자기 답변의 맥락을 잃고,
    # 검증을 위해 대화를 한 번 더 넘겨야 한다.
}

#: 워커가 여는 종류(배급 자격이 `batch_jobs` 동의를 추가로 요구한다).
BATCH_JOB_KINDS = tuple(k for k, v in JOB_SPECS.items() if v["origin"] == ORIGIN_BATCH)


def job_spec(job_kind: Any) -> dict[str, Any] | None:
    """등록된 작업 종류의 명세. 모르는 값은 `None` — 호출측이 **거절**한다.

    관대하게 기본값을 주지 않는 이유: 여기서 추측하면 모르는 종류가 'text/review' 로 조용히
    처리되어, 산출물이 어디에도 도달하지 않은 채 "제출됨" 으로 남는다.
    """
    return JOB_SPECS.get(str(job_kind or "").strip())


def job_label(job_kind: Any) -> str:
    """화면·원장 공용 이름. 미등록이면 원본 문자열(빈 값이면 '콘솔 작업')."""
    spec = job_spec(job_kind)
    if spec:
        return spec["label"]
    return str(job_kind or "").strip() or "콘솔 작업"


#: 작업 프롬프트 상한. `Question` 은 대화 축에서 4000자로 잘라 넣는데, 콘솔 작업은 스키마
#: 골격이 실려 훨씬 길다(일괄 자동완성은 테이블 수십 개). `Question` 컬럼은 TEXT 라 64KB 를
#: 담지만, 그 전부를 개인 AI 에게 보내면 그쪽 컨텍스트가 먼저 터진다 — 적재 시점에 자른다.
CONSOLE_PROMPT_MAX_CHARS = 24_000


class ConsoleJobRejected(Exception):
    """작업을 적재하지 **않았다**. 호출측이 사용자에게 사유를 그대로 말할 수 있게 예외로 올린다.

    조용히 `None` 을 돌려주지 않는 이유: 적재 실패가 "성공했지만 결과가 아직" 과 구분되지
    않으면, 화면은 오지 않을 결과를 무한히 기다린다(이 feature 가 P0-F 에서 겪은 형태).
    """


def enqueue_console_job(conn, *, account_id: int, job_kind: str, prompt: str,
                        payload: Any = None, product_id: Any = None,
                        datasource_key: str | None = None) -> str:
    """관리 콘솔·배경 작업을 개인 AI 가 가져갈 **대기 작업**으로 적재한다. 반환 = `task_id`.

    ## 대화 브리지와 같은 테이블을 쓰는 이유

    점유(`CLAIMABLE_SQL`)·lease·취소·원장·각인이 전부 `WebAiTasks` 위에 있다. 별도 테이블을
    만들면 그 다섯이 두 벌이 되고, 하나만 갈려도 "목록엔 없는데 제출은 되는" 부류의 결함이
    되돌아온다. 갈리는 축은 `Kind` 하나로 좁힌다.

    ## 배치는 상한과 만료를 갖는다

    관리자 작업은 사람이 눌러서 생기므로 저절로 멈춘다. 배치는 워커가 계속 돌아서 **배급
    가능한 러너가 없어도 무한히 쌓인다** — P0-S 가 대화 축에서 고친 형태 그대로다. 그래서
    적재 전에 오래된 것을 만료시키고 대기 수에 상한을 건다.

    Raises:
        ConsoleJobRejected: 모르는 작업 종류 · 배치 대기 상한 초과. **적재하지 않았음**이
            확실하므로 호출측은 종전 경로로 폴백하거나 사용자에게 사유를 말하면 된다.
        Exception: DB 오류는 그대로 올린다(삼키면 화면이 오지 않을 결과를 기다린다).
    """
    log = logging.getLogger(__name__)
    spec = job_spec(job_kind)
    if spec is None:
        # 모르는 종류를 관대하게 받으면 산출물이 어디에도 도달하지 않은 채 "제출됨" 으로 남는다.
        raise ConsoleJobRejected(f"등록되지 않은 콘솔 작업 종류입니다: {job_kind!r}")
    if not spec.get("wired"):
        # 반영될 곳이 없는 작업을 대기열에 넣지 않는다. 넣으면 개인 AI 가 실제로 그것을
        # 가져가 토큰과 시간을 쓰고, 남는 것은 "제출됐지만 반영 실패" 뿐이다 —
        # P0-S 가 대화 축에서 세운 규율("아무도 못 집는 작업을 쌓지 않는다")의 반영 축 버전.
        raise ConsoleJobRejected(
            f"{spec['label']}은(는) 아직 위임 배선이 완성되지 않았습니다.")
    origin = spec["origin"]
    text = str(prompt or "").strip()
    if not text:
        raise ConsoleJobRejected("작업 프롬프트가 비어 있습니다.")
    if origin == ORIGIN_WEB and not account_id:
        # 관리자 작업은 **그 사람의** AI 가 처리한다(계정 스코프가 곧 배급 경계).
        raise ConsoleJobRejected("작업을 요청한 계정을 알 수 없습니다.")

    cur = conn.cursor()
    try:
        if origin == ORIGIN_BATCH:
            expire_stale_batch_jobs(conn, cur=cur)
            cur.execute(
                "SELECT COUNT(*) FROM WebAiTasks "
                "WHERE Kind = %s AND Origin = %s AND JobKind = %s AND Status = %s",
                (KIND_JOB, ORIGIN_BATCH, job_kind, STATUS_OPEN))
            pending = int((cur.fetchone() or [0])[0] or 0)
            if pending >= BATCH_PENDING_MAX:
                # 조용히 넘기지 않는다 — 워커 로그에 남아야 "왜 배치가 안 도나" 를 추적한다.
                raise ConsoleJobRejected(
                    f"배치 대기열이 가득 찼습니다({pending}/{BATCH_PENDING_MAX}) — "
                    "가져가는 러너가 없거나 처리가 밀려 있습니다.")

        task_id = "j_" + secrets.token_urlsafe(12)
        cur.execute(
            "INSERT INTO WebAiTasks (TaskId, AccountId, Question, Status, Origin, "
            "Kind, JobKind, JobPayload, ProductId, DatasourceKey) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (task_id,
             # 배치는 소유 계정이 없다(워커가 열었다). 0 을 넣어 "아무의 것도 아님" 을
             # 명시한다 — NULL 로 두면 계정 스코프 질의가 조용히 이 행을 포함할 수 있다.
             int(account_id or 0),
             text[:CONSOLE_PROMPT_MAX_CHARS],
             STATUS_OPEN, origin, KIND_JOB, job_kind,
             json.dumps(payload, ensure_ascii=False) if payload is not None else None,
             int(product_id) if product_id else None,
             (str(datasource_key or "").strip()[:128] or None)))
        conn.commit()
    finally:
        cur.close()
    log.info("[console-job] 적재 kind=%s origin=%s account=%s task=%s",
             job_kind, origin, account_id, task_id)
    return task_id


def expire_stale_batch_jobs(conn, *, cur=None) -> int:
    """가져가지 않은 채 오래된 **배치** 작업을 만료시킨다. 반환 = 만료 건수.

    관리자 작업은 만료시키지 않는다 — 사람이 화면 앞에서 기다리고 있으므로, 사라지면
    "눌렀는데 아무 일도 없었다" 가 된다. 배치 산출물은 재생성 가능하므로 오래된 요청을
    붙들 이유가 없고, 붙들면 화면의 "대기 중" 이 영구 고착된다.

    점유된 것은 건드리지 않는다(`ClaimedBy IS NULL`) — 남의 머신에서 돌고 있을 수 있다.
    """
    own = cur is None
    c = conn.cursor() if own else cur
    try:
        c.execute(
            "UPDATE WebAiTasks SET Status = %s "
            "WHERE Kind = %s AND Origin = %s AND Status = %s AND ClaimedBy IS NULL "
            f"  AND CreatedAt < DATE_SUB(NOW(), INTERVAL {BATCH_TASK_MAX_AGE_MIN} MINUTE)",
            (STATUS_EXPIRED, KIND_JOB, ORIGIN_BATCH, STATUS_OPEN))
        n = int(c.rowcount or 0)
        if own:
            conn.commit()
    finally:
        if own:
            c.close()
    if n:
        logging.getLogger(__name__).info("[console-job] 배치 작업 만료 %d건", n)
    return n


def load_console_job(conn, task_id: str, *, account_id: int | None = None) -> dict | None:
    """콘솔 작업 1건. `account_id` 를 주면 **그 계정이 요청한 것만** 돌려준다(스코프 경계).

    없거나 스코프 밖이면 `None` — 둘을 구분하지 않는다. 구분하면 남의 task id 존재 여부를
    응답 차이로 알아낼 수 있다(0041 의 `missing_task_and_out_of_scope_are_indistinguishable`
    계약과 동형).
    """
    where = "TaskId = %s AND Kind = %s"
    params: list[Any] = [str(task_id), KIND_JOB]
    if account_id is not None:
        where += " AND AccountId = %s"
        params.append(int(account_id))
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT TaskId, JobKind, Status, Origin, Answer, JobPayload, "
            "       JobAppliedAt, JobApplyError, ClaimedBy, ClaimedAt, AccountId, JobResult "
            f"FROM WebAiTasks WHERE {where} LIMIT 1", tuple(params))
        row = cur.fetchone()
    finally:
        cur.close()
    if row is None:
        return None
    return {
        "task_id": str(row[0] or ""), "job_kind": str(row[1] or ""),
        "status": str(row[2] or ""), "origin": str(row[3] or ""),
        "answer": row[4], "payload": row[5],
        "applied_at": row[6], "apply_error": str(row[7] or ""),
        "claimed_by": row[8], "claimed_at": row[9], "account_id": int(row[10] or 0),
        # 화면이 읽을 **원문**. `answer`(각인본)와 다른 소비처다 — 섞으면 래퍼가 폼에 들어간다.
        "result": row[11],
    }


def store_console_job_result(conn, task_id: str, result: str) -> None:
    """화면이 읽을 **원문**을 보존한다 (각인 래퍼 없음).

    `Answer`(각인본)를 화면에 그대로 주면 래퍼가 폼 입력란에 들어간다 — 대화 경로가 원문을
    대화에 따로 저장하는 것과 같은 이유로 저장본을 나눈다.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE WebAiTasks SET JobResult = %s WHERE TaskId = %s AND Kind = %s",
            (str(result or ""), str(task_id), KIND_JOB))
        conn.commit()
    finally:
        cur.close()


def mark_console_job_applied(conn, task_id: str, error: str = "") -> None:
    """산출물이 기존 저장 경로에 **실제로 반영됐는지**를 기록한다.

    `SubmittedAt`(제출됨)과 나누는 이유: 합치면 write-through 가 실패해도 화면은 "적용됨"
    이라 말한다. `Delivered` 를 `Status` 와 나눈 것과 같은 규율이다 — 두 사실은 따로 틀린다.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE WebAiTasks SET JobAppliedAt = NOW(), JobApplyError = %s "
            "WHERE TaskId = %s AND Kind = %s",
            ((str(error).strip()[:255] or None), str(task_id), KIND_JOB))
        conn.commit()
    finally:
        cur.close()


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
    # 보류(`deferred`) 도 취소 대상이다 — 빼면 새 질문을 보내도 옛 보류 질문이 남아,
    # 연결되는 순간 그쪽이 승격된다(사용자가 방금 고쳐 물은 질문 대신).
    where = ["AccountId = %s", "Origin = 'web'",
             "Status IN (" + ",".join(["%s"] * len(CANCELABLE_STATUSES)) + ")"]
    params: list[Any] = [int(account_id), *CANCELABLE_STATUSES]
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
            # ⚠ **DML 이 실제로 바꾼 것만 돌려준다** (codex P1-1, 2026-08-28).
            #
            # 위 SELECT 로 분류한 뒤 쓰기 사이에 러너가 claim 하거나 답을 제출하면, 재확인
            # 조건에 걸려 DELETE/UPDATE 가 **0행**이 된다. 그런데 종전에는 미리 계산한
            # `to_delete`/`to_cancel` 을 그대로 돌려줬다 — 호출측은 그 id 로 말풍선을 "취소됨"
            # 으로 바꾸고, task 는 멀쩡히 살아 있어 잠시 뒤 **취소 안내 아래에 답변이 붙는다.**
            # 사용자 결정(409 거절 + 대화 미전달)의 정반대이며, 재확인 조건을 넣은 바로 그
            # 수정이 만든 회귀다(조건은 맞았고 **반환값이 따라오지 않았다**).
            #
            # 그래서 각 id 를 **한 건씩** 쓰고 `rowcount` 로 확인한다. IN(...) 일괄 쓰기는
            # "몇 건 바뀌었나" 만 주고 "어느 것이 바뀌었나" 를 주지 않는다 — 여기서 필요한
            # 것은 후자다.
            confirmed_deleted: list[str] = []
            confirmed_canceled: list[str] = []
            status_marks = ",".join(["%s"] * len(CANCELABLE_STATUSES))
            for tid in to_delete:
                # 보류 질문도 지운다(점유될 수 없으므로 항상 이 갈래로 온다).
                cur.execute(
                    f"DELETE FROM WebAiTasks WHERE AccountId = %s AND TaskId = %s "
                    f"AND Status IN ({status_marks}) AND {CLAIMABLE_SQL}",
                    (int(account_id), tid, *CANCELABLE_STATUSES))
                if int(cur.rowcount or 0):
                    confirmed_deleted.append(tid)
                    continue
                # 지우지 못했다 = 그 사이 누가 집었다. **놓아주지 않고** 취소로 승격한다 —
                # 여기서 포기하면 사용자는 중단을 눌렀는데 답변이 그대로 온다.
                cur.execute(
                    "UPDATE WebAiTasks SET Status = %s "
                    "WHERE AccountId = %s AND TaskId = %s AND Status = %s",
                    (STATUS_CANCELED, int(account_id), tid, STATUS_OPEN))
                if int(cur.rowcount or 0):
                    confirmed_canceled.append(tid)
                # 둘 다 0행 = 이미 제출까지 끝났다. 취소할 것이 없으므로 **보고하지 않는다**
                # (보고하면 화면이 완료된 답변을 '취소됨' 으로 덮는다).
            for tid in to_cancel:
                cur.execute(
                    "UPDATE WebAiTasks SET Status = %s "
                    "WHERE AccountId = %s AND TaskId = %s AND Status = %s",
                    (STATUS_CANCELED, int(account_id), tid, STATUS_OPEN))
                if int(cur.rowcount or 0):
                    confirmed_canceled.append(tid)
            to_delete, to_cancel = confirmed_deleted, confirmed_canceled
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


def promote_latest_deferred(conn, *, account_id: int) -> tuple[str, list[str]]:
    """연결이 성립한 계정의 **보류 질문 중 가장 최근 1건만** 대기열에 올린다.

    반환: `(승격된 task_id 또는 "", 만료시킨 task_id 목록)`.

    ## 왜 1건인가 (사용자 결정 2026-08-28)

    연결이 끊긴 줄 모르고 보낸 질문을 매번 다시 입력하게 두는 것은 마찰이다. 그렇다고 쌓인 것을
    전부 처리하면 예전 결함으로 되돌아간다 — 연결하는 순간 밀린 질문이 한꺼번에 답을 쏟아낸다
    (실측: 같은 질문 5건 누적). 사용자가 그 순간 원하는 것은 **마지막으로 물은 것**이다.

    나머지는 지우지 않고 `expired` 로 남긴다. 지우면 그 질문의 대기 말풍선이 무엇을 가리키는지
    영영 알 수 없어, 화면에 "연결하면 처리합니다" 가 박제된 채 남는다. 상태로 남겨야 호출측이
    그 말풍선을 "처리되지 않음" 으로 정정할 수 있다.

    ## 경계

    - `account_id` 는 편의가 아니라 경계다. 없으면 아무것도 하지 않는다.
    - 승격은 `Status='deferred'` 조건을 **UPDATE 문 안에** 두어 원자적이다 — 두 세션이 동시에
      연결해도 한 번만 승격된다(두 번 승격되면 같은 질문이 두 번 답변된다).
    - 실패는 삼킨다. 승격은 편의 기능이고, 여기서 예외를 올리면 **도구 호출 자체가 실패**한다.
    """
    log = logging.getLogger(__name__)
    if not account_id:
        return "", []
    try:
        cur = conn.cursor()
        try:
            # 오래된 것은 승격 후보에서 먼저 제외한다 — "기억에 없는 응답" 방지.
            cur.execute(
                "SELECT TaskId, CreatedAt FROM WebAiTasks "
                "WHERE AccountId = %s AND Origin = 'web' AND Status = %s "
                f"  AND CreatedAt > DATE_SUB(NOW(), INTERVAL {DEFERRED_MAX_AGE_HOURS} HOUR) "
                "ORDER BY CreatedAt DESC, Id DESC LIMIT 1",
                (int(account_id), STATUS_DEFERRED))
            row = cur.fetchone()
            target = str(row[0]) if row else ""

            # 만료 대상을 **미리 읽어 둔다** — 아래 UPDATE 가 상태를 바꾸고 나면 "무엇이
            # 만료됐는지" 를 되물을 수 없다(호출측이 그 말풍선을 정정해야 한다).
            cur.execute(
                "SELECT TaskId FROM WebAiTasks "
                "WHERE AccountId = %s AND Origin = 'web' AND Status = %s AND TaskId <> %s",
                (int(account_id), STATUS_DEFERRED, target))
            candidates = [str(r[0]) for r in (cur.fetchall() or [])]

            # ★ 승격과 만료를 **한 문장**으로 처리한다(codex REV-20260828T070000 P1).
            #
            # 나눠 쓰면 요청 커넥션이 autocommit 이라 각 문장이 즉시 확정되고, 두 세션이 동시에
            # 연결할 때 **서로 다른 행을 각자 승격**할 수 있다(A 는 T2 를, B 는 T1 을) — 그러면
            # "최근 1건" 약속이 깨져 두 질문이 모두 답변된다.
            #
            # 이 문장은 그 계정의 보류 **전부**를 한 번에 소진한다. 먼저 커밋한 쪽이 전부
            # 가져가므로, 뒤이은 실행은 `Status = deferred` 에 걸리는 행이 0 이라 아무 일도
            # 일어나지 않는다(중복 승격 없음).
            cur.execute(
                "UPDATE WebAiTasks "
                "SET Status = CASE WHEN TaskId = %s THEN %s ELSE %s END "
                "WHERE AccountId = %s AND Origin = 'web' AND Status = %s",
                (target, STATUS_OPEN, STATUS_EXPIRED,
                 int(account_id), STATUS_DEFERRED))
            changed = int(cur.rowcount or 0)
            conn.commit()
            # 이 실행이 실제로 바꾼 것이 없으면(=경쟁에서 졌으면) 승격도 만료도 내 것이 아니다.
            promoted = target if (changed and target) else ""
            expired = candidates if changed else []
        finally:
            cur.close()
    except Exception as exc:
        log.warning("[bridge] 보류 질문 승격 실패 account=%s: %r", account_id, exc)
        return "", []

    if promoted or expired:
        log.info("[bridge] 보류 질문 승격 account=%s — 승격 %s · 만료 %d",
                 account_id, promoted or "(없음)", len(expired))
    return promoted, expired
