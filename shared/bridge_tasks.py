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
    # ── 러너 자격 판정 — 웹과 워커가 함께 읽는다 (TASK-20260901T190000) ──
    "SQL_NOW",
    "LIVE_TOKEN_PREDICATE",
    "RUNNER_HEARTBEAT_WINDOW_SEC",
    "parse_runner_features",
    "runner_profile_for_account",
    "runner_can_take",
    "version_at_least",
    "FORMAT_NOTE",
    "messages_to_prompt",
    "JOB_SPECS",
    "job_spec",
    "job_label",
    "BATCH_JOB_KINDS",
    "CONSOLE_JOB_LIGHT_MODELS",
    "pick_console_job_model",
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
        # TASK-20260901T190000 — 전 구간이 섰다: 적재(`node_analysis._delegate_job`) ·
        # 프롬프트(`llm.node_analysis_messages`, 서버 호출과 같은 정본) ·
        # 반영(`node_analysis.apply_external_node_analysis`).
        "wired": True,
    },
    "prompt_generate": {
        "label": "시스템 프롬프트 자동작성",
        "origin": ORIGIN_WEB, "response": "text", "apply": "review",
        "wired": True,
    },
    "insight_summary": {
        # 이름을 좁혔다(TASK-20260901T190000): 배선된 것은 **테이블 인사이트**다. 스키마·계정
        # 인사이트는 아직 서버 경로뿐이고, 넓은 이름을 두면 `wired: True` 가 그것들까지
        # 배선됐다고 말하게 된다 — 이 레지스트리가 금지하는 부분 배선의 전형이다.
        "label": "테이블 인사이트 배치",
        "origin": ORIGIN_BATCH, "response": "json", "apply": "store",
        # 적재(`insight._delegate_table_insight`) · 프롬프트(`llm.table_insight_messages`,
        # 서버 호출과 같은 정본) · 반영(`insight.apply_external_insight_summary` → 기존
        # KV 이음매 → 다음 cycle 의 상속 경로가 발행).
        "wired": True,
    },
    "cluster_label": {
        "label": "클러스터 라벨링",
        "origin": ORIGIN_BATCH, "response": "json", "apply": "store",
        # TASK-20260901T190000 — 적재(`semantic_cluster._delegate_cluster_labels`) ·
        # 프롬프트(`_cluster_label_messages`, `llm.CLUSTER_LABEL_PROMPT` 그대로) ·
        # 반영(`semantic_cluster.apply_external_cluster_labels` → 기존 kv 캐시).
        "wired": True,
    },
    # red-team 은 대기열에 따로 적재되지 않는다 — **답변한 그 러너**가 자기 답변을 검증해
    # `submit_answer` 에 함께 싣는다(사용자 결정 2026-08-31: "요청 당시의 호출자가 스스로의
    # 대화내역을 알 수 있으므로"). 별도 task 로 만들면 그 AI 가 자기 답변의 맥락을 잃고,
    # 검증을 위해 대화를 한 번 더 넘겨야 한다.
}

#: 워커가 여는 종류(배급 자격이 `batch_jobs` 동의를 추가로 요구한다).
BATCH_JOB_KINDS = tuple(k for k, v in JOB_SPECS.items() if v["origin"] == ORIGIN_BATCH)


#: 콘솔·배경 작업에 쓸 **경량 모델** 선호 (사용자 결정 2026-09-01).
#:
#: > "관리 콘솔에서 이용될 모델은 모두 경량 모델로 구성해주세요. claude는 haiku, codex는 luna
#: >  모델과 같은 경량 모델로 작동해야 합니다."
#:
#: ## 왜 콘솔 작업만인가
#:
#: 콘솔 작업은 **기계적 산출물**이다 — 테이블 설명 한 줄, 프롬프트 초안, 클러스터 라벨.
#: 대화 답변처럼 사용자가 읽고 판단할 추론이 아니다. 그런데 그 호출은 **사용자 개인 계정의
#: 토큰**을 태운다. 남의 자원을 우리가 쓰는 자리에서 상위 모델을 기본으로 두는 것은 근거가 없다.
#: 대화 축은 건드리지 않는다 — 그건 사용자가 화면에서 직접 고른 값이다.
#:
#: ## 값은 **후보**이지 지시가 아니다
#:
#: 여기 적힌 문자열은 러너가 신고한 모델 이름과 **부분일치로 대조**할 후보다. 대조에 실패하면
#: 아무 것도 보내지 않고 러너 기본값에 맡긴다 — 없는 모델 이름을 지어 보내면 러너가 그 값을
#: 인자로 넘겨 실행이 실패한다(P0-T 가 겪은 형태). **우리가 아는 이름이 아니라 그 러너가
#: 고를 수 있다고 말한 이름만** 나간다.
#:
#: 순서가 선호도다(앞이 더 가볍다).
CONSOLE_JOB_LIGHT_MODELS: dict[str, tuple[str, ...]] = {
    "claude": ("haiku",),
    "codex": ("luna", "mini"),
    # 로컬 런타임은 모델 이름 규약이 제각각이라 후보를 적지 않는다 — 대조 실패로 떨어져
    # 러너 기본값을 쓴다(그쪽은 애초에 자기 머신 자원이라 과금 축이 다르다).
}


def pick_console_job_model(capabilities: Any) -> tuple[str, str]:
    """러너 신고 목록에서 콘솔 작업용 **경량 (런타임, 모델)** 을 고른다. 없으면 `("", "")`.

    Args:
        capabilities: 러너가 하트비트로 신고한 목록.
            `[{"runtime": "claude", "models": [{"value": "haiku", ...}, ...]}, ...]`

    ## 왜 런타임까지 함께 돌려주는가

    모델 이름은 런타임에 종속이다(`haiku` 는 claude 의 것이다). 모델만 보내면 러너는 그것을
    **자기 현재 런타임**의 목록과 대조하고, 다르면 「미반영」으로 떨어뜨린다. 둘을 함께 보내야
    러너가 그 런타임으로 옮겨 실행한다.

    ## 순서

    **러너가 신고한 순서**를 따른다 — 그 순서가 그 머신의 선호다. 우리가 런타임 간 우열을
    정하면 `--ai` 로 제한한 사용자의 의도를 서버가 넘어선다.
    """
    if not isinstance(capabilities, list):
        return "", ""
    for entry in capabilities:
        if not isinstance(entry, dict):
            continue
        runtime = str(entry.get("runtime") or "").strip()
        wanted = CONSOLE_JOB_LIGHT_MODELS.get(runtime)
        if not runtime or not wanted:
            continue
        values = [str((m or {}).get("value") or "") if isinstance(m, dict) else str(m or "")
                  for m in (entry.get("models") or [])]
        values = [v for v in values if v]
        for needle in wanted:
            for value in values:
                # 부분일치 — 신고 값은 런타임마다 형태가 다르다(`haiku` vs `gpt-5.6-luna`).
                # 완전일치를 요구하면 이름 규약이 바뀌는 날 조용히 대조에 실패한다.
                if needle.lower() in value.lower():
                    return runtime, value
    return "", ""


# ── 「이 계정에 지금 일을 줄 수 있는 러너가 있는가」 — 웹과 **워커**가 함께 읽는 판정 ────
#
# 종전에 이 판정은 웹 프로세스에만 있었다(`oauth_store.account_runner_profile` +
# `_console_llm._classify`). 그런데 그래프 능동 분석·인사이트 배치를 위임하려면 **insight-worker**
# 가 같은 질문에 답해야 한다 — 그쪽은 다른 컨테이너라 `oauth_store` 를 import 하지 못한다.
#
# 그래서 질의와 술어를 여기로 올린다. 워커 쪽에 술어를 **다시 적으면** 로그아웃한 세션의 러너를
# 워커만 자격 있다고 보는 창이 열리고, 그 창에서 적재된 작업은 아무도 집지 않는다.
# `oauth_store` 는 이 상수를 그대로 재수출해 종전 호출부를 유지한다.

#: ⚠ SQL 의 현재 시각은 `UTC_TIMESTAMP()` 다 — `NOW()` 가 아니다. 만료 시각은 파이썬이 UTC 로
#: 넣는데 컨테이너 TZ 는 `Asia/Seoul` 이라 `NOW()` 와는 9시간이 어긋난다(라이브 실측 2026-08-28).
SQL_NOW = "UTC_TIMESTAMP()"

#: 살아 있는 access token 의 조건 — 토큰 미폐기·미만료 + (세션 결합이면) 세션 실재·미폐기·미만료.
#: 별칭 계약: 토큰 테이블 `t`, 세션 테이블 `s` 로 조인해 두고 쓴다.
LIVE_TOKEN_PREDICATE = (
    "t.TokenType = 'access' AND t.RevokedAt IS NULL "
    f"AND (t.ExpiresAt IS NULL OR t.ExpiresAt > {SQL_NOW}) "
    "AND (t.SessionId IS NULL OR "
    "     (s.Id IS NOT NULL AND s.IsRevoked = 0 "
    f"      AND (s.ExpiresAt IS NULL OR s.ExpiresAt > {SQL_NOW})))"
)

#: 하트비트 신선도 창(초). 러너 주기(30초)의 3배 — 한 번 놓친 신호는 흡수된다.
#: `oauth_store.HEARTBEAT_WINDOW_SEC` 와 같은 값이어야 하며 계약 테스트가 그것을 대조한다.
RUNNER_HEARTBEAT_WINDOW_SEC = 90


#: 러너 신고 목록의 모양 제한. 이 값은 클라이언트가 준 것이고 화면·SQL 로 흘러간다.
RUNNER_FEATURES_MAX = 12
RUNNER_FEATURE_MAX_LEN = 32


def parse_runner_features(raw: Any) -> list[str]:
    """저장된 CSV 를 기능 이름 목록으로 — **읽기·쓰기·자격판정이 같은 정규화를 쓴다**.

    한쪽만 소문자화하거나 공백을 다르게 다루면 `"Console_Jobs"` 를 신고한 러너가 배급에서
    빠진다. 그 실패는 조용하다(작업이 그냥 안 간다) — 그래서 정규화를 한 함수에 둔다.
    `oauth_store.parse_runner_features` 는 이 함수를 그대로 재수출한다.
    """
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        raw = ",".join(str(x or "") for x in raw)
    out: list[str] = []
    for part in str(raw).split(","):
        name = part.strip().lower()
        # 이름처럼 생긴 것만 받는다. 이 값은 SQL LIKE 나 화면 표시로 흘러가므로, 모양을
        # 여기서 잠근다(P0-Z4 의 "요구는 정확히, 수용은 관대하게" 중 모양 축).
        if not name or len(name) > RUNNER_FEATURE_MAX_LEN:
            continue
        if not all(c.isalnum() or c in "_-" for c in name):
            continue
        if name not in out:
            out.append(name)
        if len(out) >= RUNNER_FEATURES_MAX:
            break
    return out


def runner_profile_for_account(cur, account_id: Any, *,
                               window_sec: int | None = None) -> dict[str, Any]:
    """이 계정의 **지금 듣고 있는** 러너 한 대의 프로필. 없으면 전부 빈 값 + `listening=False`.

    능력(`capabilities`)과 기능(`features`)을 **한 질의로** 읽는다 — 따로 읽으면 두 질의 사이에
    하트비트가 도착해 "A 머신의 모델 목록 + B 머신의 기능" 이라는 실재하지 않는 조합이 나온다.

    러너가 여럿이면 **가장 최근에 말한 것** 하나를 쓴다(합치지 않는다 — 합친 목록에서 고른
    모델이 실제로 가져가는 러너에 없을 수 있다).
    """
    empty = {"capabilities": [], "features": [], "agent_version": "", "listening": False}
    try:
        aid = int(account_id or 0)
    except (TypeError, ValueError):
        aid = 0
    if not aid:
        return empty
    window = int(window_sec if window_sec is not None else RUNNER_HEARTBEAT_WINDOW_SEC)
    cur.execute(
        "SELECT t.RunnerCapabilities, t.RunnerFeatures, t.RunnerAgentVersion "
        "FROM WebOAuthTokens t "
        "LEFT JOIN WebAuthSessions s ON s.Id = t.SessionId "
        f"WHERE t.AccountId = %s AND {LIVE_TOKEN_PREDICATE} "
        "  AND t.LastHeartbeatAt IS NOT NULL "
        f"  AND t.LastHeartbeatAt > DATE_SUB({SQL_NOW}, INTERVAL %s SECOND) "
        "ORDER BY t.LastHeartbeatAt DESC LIMIT 1",
        (aid, window))
    row = cur.fetchone()
    if not row:
        return empty
    caps: list = []
    if row[0]:
        try:
            parsed = json.loads(row[0])
        except (TypeError, ValueError):
            parsed = None   # 저장 값이 깨졌다 — 빈 목록(선택기만 숨고 답변 경로는 멀쩡하다)
        if isinstance(parsed, list):
            caps = parsed
    return {
        "capabilities": caps,
        "features": parse_runner_features(row[1]),
        "agent_version": str(row[2] or "").strip(),
        "listening": True,
    }


def version_at_least(actual: Any, minimum: str) -> bool:
    """`actual >= minimum` 을 점(.) 구분 정수 튜플로 비교한다.

    **판정 불가는 False**(=구버전 취급)로 본다. 버전을 모르는 러너에 콘솔 작업을 주면
    프레이밍이 어긋나 산출물이 조용히 망가지는데, 그 실패는 사용자에게 "AI 가 이상한 답을
    했다" 로만 보인다. 모르는 채로 "충족한다" 고 우길 근거가 없다.

    자릿수가 다르면 짧은 쪽을 0 으로 채운다(`2026.9` vs `2026.9.1`).
    """
    def _parts(v: Any) -> list[int] | None:
        s = str(v or "").strip()
        if not s:
            return None
        out: list[int] = []
        for chunk in s.split("."):
            chunk = chunk.strip()
            if not chunk.isdigit():
                return None
            out.append(int(chunk))
        return out or None

    got, want = _parts(actual), _parts(minimum)
    if got is None or want is None:
        return False
    width = max(len(got), len(want))
    got += [0] * (width - len(got))
    want += [0] * (width - len(want))
    return got >= want


def runner_can_take(profile: Any, *, need_batch: bool = False) -> bool:
    """이 러너에게 콘솔·배경 작업을 **줘도 되는가**. 판정 순서가 곧 의미다.

    기능 신고가 1차 자격이고 버전이 2차다 — 기능만 보면 신고 형식이 바뀐 뒤에도 구 러너가
    자격을 유지한다. `need_batch` 는 배경 배치의 **별도 동의**까지 요구한다.

    ⚠ 이 함수는 **사유를 말하지 않는다**. 화면은 왜 안 되는지를 말해야 하므로
    `_console_llm._classify` 가 같은 순서로 사유까지 낸다 — 그쪽이 이 함수를 부르고,
    계약 테스트가 두 판정이 갈리지 않음을 대조한다.
    """
    if not isinstance(profile, dict) or not profile.get("listening"):
        return False
    features = profile.get("features") or []
    if RUNNER_FEATURE_CONSOLE_JOBS not in features:
        return False
    if not version_at_least(profile.get("agent_version"), RUNNER_MIN_AGENT_VERSION):
        return False
    if need_batch and RUNNER_FEATURE_BATCH_JOBS not in features:
        return False
    return True


#: 출력 형식 지시. 러너는 자기 CLI 의 stdout 만 돌려주므로, 형식을 프롬프트로 못박지 않으면
#: 머리말·맺음말이 섞여 파서가 빈 결과를 낸다. 관대한 수용(`extract_json_object`)은 그 다음
#: 방어선이지 이것의 대체가 아니다 — 요구는 정확히, 수용은 관대하게(P0-Z4).
FORMAT_NOTE = {
    "json": ("답변은 **JSON 하나만** 출력하라. 코드펜스·머리말·맺음말 없이 객체 또는 배열만."),
    "text": ("답변 본문만 출력하라. 머리말·맺음말·따옴표 감싸기 없이."),
}


def messages_to_prompt(messages: Any, response_format: str = "text") -> str:
    """`messages` 를 러너가 받을 단일 프롬프트로 편다.

    system 은 앞에, user/assistant 는 순서대로. 역할 라벨을 남기는 이유: 조립부가 system 에
    제약(길이·금지어·스키마)을 넣는 경우가 있어, 평문으로 뭉개면 그 제약이 본문과 구분되지
    않아 모델이 지시가 아니라 참고로 읽는다.
    """
    # 두 목록으로 나눠 담고 마지막에 잇는다.
    #
    # 한 목록에 담으며 system 을 `insert(계산된 위치)` 하는 방식도 같은 결과를 내지만,
    # 그 위치 계산이 **왜 옳은지**를 읽는 사람이 매번 재구성해야 한다. 「system 먼저」는
    # 이 함수의 계약이므로 자료구조가 그것을 말하게 둔다 — 리팩터가 순서를 조용히 뒤집는
    # 부류의 사고를 구조로 막는다(러너가 지침을 맨 앞에 두는 이유와 같은 축, P0-P).
    systems: list[str] = []
    others: list[str] = []
    for m in (messages or []):
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "user").lower()
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            systems.append(f"── 지침 ──\n{content}\n── 지침 끝 ──")
        else:
            others.append(content)
    note = FORMAT_NOTE.get(str(response_format or "text"), FORMAT_NOTE["text"])
    return "\n\n".join([*systems, *others, note])


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


def open_job_exists(conn, job_kind: str, dedupe_key: str) -> bool:
    """같은 일이 **이미 대기·처리 중인가** (TASK-20260901T190000).

    배경 배치는 워커 루프가 주기적으로 도는데, 위임한 결과가 아직 안 왔으면 그 pass 도
    "아직 값이 없다" 로 판단해 **같은 작업을 다시 적재한다**. 그렇게 쌓인 중복은 전부 실제로
    개인 AI 가 처리하고 — 즉 **같은 답을 사용자 계정 토큰으로 여러 번 산다**.

    대기열 상한(`BATCH_PENDING_MAX`)은 폭주만 막을 뿐 중복 자체를 막지 못한다. 그래서 적재
    전에 같은 `dedupe_key` 의 미완 작업이 있는지 본다(`open` = 대기 · 점유 중 포함).

    ⚠ 조회 실패는 **False**(적재 진행)로 떨어진다. 여기서 fail-closed 하면 일시적 DB 오류가
    배경 처리를 통째로 멈추는데, 그 대가는 최악의 경우 중복 1건이다 — 방향이 반대다.
    """
    key = str(dedupe_key or "").strip()
    if not key:
        return False
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM WebAiTasks "
            "WHERE Kind = %s AND JobKind = %s AND Status = %s "
            "  AND JSON_UNQUOTE(JSON_EXTRACT(JobPayload, '$.dedupe_key')) = %s LIMIT 1",
            (KIND_JOB, str(job_kind), STATUS_OPEN, key))
        return cur.fetchone() is not None
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "[console-job] 중복 확인 실패 kind=%s key=%s: %r", job_kind, key, exc)
        return False
    finally:
        cur.close()


def enqueue_console_job(conn, *, account_id: int, job_kind: str, prompt: str,
                        payload: Any = None, product_id: Any = None,
                        datasource_key: str | None = None,
                        dedupe_key: str | None = None) -> str:
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

    if dedupe_key:
        # 같은 일을 두 번 사지 않는다. `payload` 에 키를 접어 넣어 **조회 대상과 저장 대상이
        # 같은 값**이 되게 한다 — 따로 두면 한쪽만 갱신되는 날 중복이 조용히 돌아온다.
        if open_job_exists(conn, job_kind, dedupe_key):
            raise ConsoleJobRejected(
                f"{spec['label']}: 같은 작업이 이미 대기 중입니다(중복 적재 안 함).")
        payload = {**(payload if isinstance(payload, dict) else {"value": payload}),
                   "dedupe_key": str(dedupe_key)}

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
