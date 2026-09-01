"""feature-0043 — **고아 점유 회수** + **무진행 국면** (TASK-20260901T140000).

## 무엇이 고장나 있었나 (라이브 실측 2026-09-01, 대화 `20260901030637-95dc8844`)

브리지 lease 는 도구 호출마다 갱신된다(`_renew_claim_lease`) — "진행하고 있으니 살아 있다".
그런데 러너 **프로세스가 사라지는** 순간 그 갱신값이 그대로 남아 최대 30분짜리 사각지대가
된다: task 는 `Status='open' · ClaimedBy=<계정>` 이라 `CLAIMABLE_SQL` 을 통과하지 못해
대기 목록에서 사라지고, **재기동한 같은 러너조차** 자기가 두고 온 작업을 되찾지 못한다.
화면은 그 30분을 「처리 중」으로 그린다.

    12:07:26  전달 (claude·sonnet·xhigh)
    12:13:20  마지막 도구 호출 (14회 · 354초 — 정상 속도)
    12:13~16  러너 재설치·재기동 → 자식 프로세스 사망, 점유는 서버에 그대로
    12:43:20  lease 만료 → 재배달 → **조사를 처음부터 재실행**
    12:47:47  토큰 만료로 러너 종료 → **또 고아**
    13:34:23  사용자가 포기하고 재전송 → 새 task 가 **80초 만에 종결**

**사용자 대기 87분.** 그중 60분 이상은 질문이 아무에게도 보이지 않던 시간이고, 사용자에게는
그것이 「추론 과정이 너무 길어진다」로 보였다. (⚠ 87분을 끝낸 그 80초가 낸 것은 리뷰가 아니라
**거부 답변**이었다 — 별건 결함이며 이 파일의 계약 대상이 아니다.)

## 이 파일이 고정하는 두 계약

1. **회수** — 러너가 「이 인스턴스는 죽었다」를 신고하면 그 인스턴스가 점유한 미제출 작업만
   즉시 놓인다. 놓는 범위가 넓어지면(계정 단위 등) 살아서 일하는 다른 러너의 작업을 뺏고,
   좁아지면(제출까지 끝난 것 포함) 이미 답한 질문이 다시 배달된다.
2. **표시** — 점유돼 있어도 **진행 신호가 끊기면** 국면이 `working` 이 아니라 `stalled` 다.
   「가져갔다」와 「진행하고 있다」는 다른 사실이고, 둘을 합쳐 놓았던 것이 87분의 절반이다.
"""
from __future__ import annotations

import ast
import pathlib
import sys

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_REPO = _UNIT.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from shared.bridge_tasks import (  # noqa: E402
    BRIDGE_CLAIM_LEASE_MIN,
    BRIDGE_NO_PROGRESS_SEC,
    RUNNER_INSTANCE_SEP,
    STATUS_OPEN,
    claimed_client_value,
    instance_of_claimed_client,
    release_runner_instance_claims,
)

WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
AI_TOOLS = WEB_SRC / "routers" / "ai_tools.py"
COMPOSER_JS = WEB_SRC / "static" / "app" / "composer.js"
RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"


# ── ClaimedClient 합성·해석 ────────────────────────────────────────────────────


def test_claimed_client_carries_instance():
    v = claimed_client_value("console-manual", "abc123")
    assert v == f"console-manual{RUNNER_INSTANCE_SEP}abc123"
    assert instance_of_claimed_client(v) == "abc123"


def test_claimed_client_without_instance_is_unchanged():
    """인스턴스를 신고하지 않는 **구 러너**는 종전 값 그대로여야 한다.

    여기서 접미가 붙으면 취소 통보의 점유자 대조(`SUBSTRING_INDEX`)가 아니라 **다른 축**
    (구 러너 호환 경로)이 깨진다. 회수가 안 되는 것은 종전 동작이지만, 값이 바뀌는 것은
    회귀다.
    """
    assert claimed_client_value("console-manual", None) == "console-manual"
    assert claimed_client_value("console-manual", "") == "console-manual"
    assert instance_of_claimed_client("console-manual") == ""


@pytest.mark.parametrize("bad", ["a b", "a%b", "a_b", "a#b", "../x", "한글"])
def test_non_alphanumeric_instance_is_ignored(bad):
    """인스턴스는 `LIKE` 패턴에도 들어간다 — 메타문자가 통과하면 **범위가 넓어진다**."""
    assert claimed_client_value("cli", bad) == "cli"


def test_claimed_client_fits_column_and_keeps_instance():
    """`ClaimedClient` 는 VARCHAR(64). 잘릴 때 **인스턴스 쪽을 지킨다**.

    앞자리(client_id)는 표시용이라 잘려도 기능이 죽지 않지만, 인스턴스가 잘리면 회수가
    통째로 죽는다 — 그리고 그 죽음은 30분 뒤에야 증상으로 나타난다.
    """
    v = claimed_client_value("x" * 80, "deadbeef1234")
    assert len(v) <= 64
    assert instance_of_claimed_client(v) == "deadbeef1234"


# ── 회수 SQL 의 경계 ───────────────────────────────────────────────────────────


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _FakeConn:
    def __init__(self, rows):
        self.cur = _FakeCursor(rows)
        self.committed = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True


def test_release_scopes_to_claimer_open_and_unsubmitted():
    conn = _FakeConn([("t_a",), ("t_b",)])
    out = release_runner_instance_claims(conn, account_id=10, instances=["inst1"])
    assert out == ["t_a", "t_b"]
    assert conn.committed, "회수가 커밋되지 않으면 다음 대기 조회가 옛 스냅샷을 본다"

    select_sql, select_params = conn.cur.calls[0]
    # 점유자 경계 — 질문 소유 계정이 아니라 **내가 집은 것**. 배치 작업은 소유 계정이 없다.
    assert "ClaimedBy = %s" in select_sql
    assert "AccountId" not in select_sql
    # 확정 불변 — 제출까지 끝낸 것은 되살리지 않는다.
    assert "SubmittedAt IS NULL" in select_sql
    assert "Status = %s" in select_sql
    assert select_params[0] == 10 and select_params[1] == STATUS_OPEN
    assert select_params[2] == f"%{RUNNER_INSTANCE_SEP}inst1"

    update_sql, _ = conn.cur.calls[1]
    # 상태는 그대로 둔다 — 취소가 아니라 **다시 집어야 하는 것**이다.
    assert "SET ClaimedBy = NULL, ClaimedAt = NULL, ClaimedClient = NULL" in update_sql
    assert "Status" not in update_sql.split("WHERE", 1)[1]


def test_release_is_noop_without_valid_instance():
    """빈·비영숫자 신고로 **SQL 을 한 줄도 쏘지 않는다**.

    여기서 빈 목록이 「전부」로 번역되면 그 순간 계정의 진행 중 작업이 통째로 대기열로
    돌아간다 — 회수가 아니라 사고다.
    """
    for instances in ([], None, [""], ["a b"], ["%"]):
        conn = _FakeConn([("t_x",)])
        assert release_runner_instance_claims(conn, account_id=10, instances=instances) == []
        assert conn.cur.calls == []


def test_release_is_noop_without_account():
    conn = _FakeConn([("t_x",)])
    assert release_runner_instance_claims(conn, account_id=0, instances=["inst1"]) == []
    assert conn.cur.calls == []


def test_release_skips_update_when_nothing_matched():
    conn = _FakeConn([])
    assert release_runner_instance_claims(conn, account_id=10, instances=["inst1"]) == []
    assert len(conn.cur.calls) == 1, "매칭이 0건인데 UPDATE 를 쏘면 무조건절 사고의 씨앗이 된다"


# ── 국면 판정 — 「가져갔다」 vs 「진행하고 있다」 ─────────────────────────────────


def _load_bridge_phase():
    """`ai_tools._bridge_phase` 를 **소스에서 떼어 내** 단독 실행한다.

    모듈 전체 import 는 FastAPI·DB·app 을 요구해 단위 실행이 불가능하다. 이 함수는 순수
    분기라 그 자리에서 실행할 수 있고, 그렇게 해야 표(국면 전이)를 실제로 재는 테스트가
    된다 — 소스 문자열 검사만으로는 「분기를 넣었다」는 알아도 「분기가 성립한다」는 모른다.
    """
    text = AI_TOOLS.read_text(encoding="utf-8")
    tree = ast.parse(text)
    src = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_bridge_phase":
            src = ast.get_source_segment(text, node)
            break
    assert src, "_bridge_phase 를 찾지 못했다"
    ns: dict = {
        "Any": object,
        "_STATUS_CANCELED": "canceled",
        "_STATUS_EXPIRED": "expired",
        "_STATUS_DEFERRED": "deferred",
        "_BRIDGE_DELIVER_GRACE_SEC": 30,
        "_BRIDGE_NO_PROGRESS_SEC": BRIDGE_NO_PROGRESS_SEC,
    }
    exec(compile(ast.parse(src), "<phase>", "exec"), ns)  # noqa: S102
    return ns["_bridge_phase"]


def test_phase_working_while_progress_is_fresh():
    phase = _load_bridge_phase()
    assert phase("open", 10, False, True, claimed_age_sec=5.0) == "working"
    assert phase("open", 10, False, True,
                 claimed_age_sec=BRIDGE_NO_PROGRESS_SEC - 1) == "working"


def test_phase_stalled_when_progress_signal_is_old():
    phase = _load_bridge_phase()
    assert phase("open", 10, False, True,
                 claimed_age_sec=BRIDGE_NO_PROGRESS_SEC + 1) == "stalled"


def test_phase_stays_working_when_age_unknown():
    """관측하지 못한 것을 「멈췄다」로 단정하지 않는다 (`listening` 기본값 True 와 같은 방향)."""
    phase = _load_bridge_phase()
    assert phase("open", 10, False, True, claimed_age_sec=None) == "working"


def test_terminal_phases_win_over_stalled():
    """종결이 무진행보다 앞선다 — 끝난 것을 「멈췄다」고 말하면 사용자는 오지 않을 답을 기다린다."""
    phase = _load_bridge_phase()
    old = BRIDGE_NO_PROGRESS_SEC * 10
    assert phase("canceled", 10, False, True, claimed_age_sec=old) == "canceled"
    assert phase("expired", 10, False, True, claimed_age_sec=old) == "expired"
    assert phase("submitted", 10, True, True, delivered=True,
                 submitted_age_sec=1.0, claimed_age_sec=old) == "done"


def test_no_progress_threshold_sits_between_normal_gap_and_lease():
    """임계는 **정상 무도구 구간의 최대치보다 크고 lease 보다 작아야** 한다.

    - 아래로 내려가면: 마지막 도구 뒤 답변을 쓰는 정상 구간(라이브 실측 최대 621초)이
      「멈춤」으로 오표시된다.
    - 위로 올라가면: lease 만료(=회수)가 먼저 일어나 사용자는 **경고를 보기 전에** 재조사를
      겪는다 — 알려 줄 기회 자체가 사라진다.
    """
    assert BRIDGE_NO_PROGRESS_SEC > 621
    assert BRIDGE_NO_PROGRESS_SEC < BRIDGE_CLAIM_LEASE_MIN * 60


# ── 배선 — 판정만 있고 전달이 없으면 화면에 아무 일도 일어나지 않는다 ──────────────


def test_both_phase_call_sites_pass_claimed_age():
    """폴링(`bridge_status`)과 스트리밍(`_bridge_stream_snapshot`)이 **같은 인자**를 넘긴다.

    한쪽만 넘기면 SSE 실패로 폴링에 폴백하는 순간 국면이 달라진다 — 이 파일이 계속 막아 온
    「전송 방식이 화면을 바꾼다」 부류다.
    """
    text = AI_TOOLS.read_text(encoding="utf-8")
    # 두 호출부 — 스트리밍(`row[4]`)과 폴링(미리 계산한 `_poll_claimed_age`).
    assert "claimed_age_sec=_claimed_age" in text
    assert "claimed_age_sec=_poll_claimed_age" in text
    assert "_announce_no_progress(_phase," in text
    assert "_announce_no_progress(_poll_phase," in text


def test_claim_request_records_runner_instance():
    text = AI_TOOLS.read_text(encoding="utf-8")
    assert '_claimed_client_value(ctx.get("client_id"), body.get("runner_instance"))' in text


def test_cancel_notify_matches_client_prefix_not_whole_value():
    """취소 통보의 점유자 대조가 **앞자리 비교**여야 한다.

    `ClaimedClient` 에 인스턴스가 붙은 뒤로 전량 일치는 한 건도 매칭하지 못한다 — 취소를
    눌러도 러너가 계속 태우는 종전 결함이 그대로 되돌아온다.
    """
    text = AI_TOOLS.read_text(encoding="utf-8")
    assert "SUBSTRING_INDEX(ClaimedClient, '#', 1) = %s" in text


def test_heartbeat_accepts_death_report_and_reports_back():
    text = AI_TOOLS.read_text(encoding="utf-8")
    assert '(payload or {}).get("released_instances")' in text
    assert '"released_claims": released_claims' in text


def test_runner_wires_instance_axis():
    src = RUNNER.read_text(encoding="utf-8")
    # 기동: 발급 + 직전 회수
    assert "def init_runner_instance()" in src
    assert "init_runner_instance()" in src.split("def init_runner_instance()", 1)[1]
    # 점유에 새긴다
    assert '"runner_instance": _RUNNER_INSTANCE' in src
    # 기동 첫 신호에 직전 인스턴스를 싣고, 닿을 때까지 재시도한다
    assert "released_instances=_pending_release" in src
    # 종료 세 갈래를 한 출구로
    assert "atexit.register(release_own_claims_on_exit)" in src
    assert "_signal.SIGTERM" in src


def test_save_conf_preserves_instance():
    """`save_conf` 는 파일을 통째로 다시 쓴다 — 여기서 이어 나르지 않으면 회수가 조용히 죽는다."""
    src = RUNNER.read_text(encoding="utf-8")
    body = src.split("def save_conf(", 1)[1].split("\ndef ", 1)[0]
    assert 'payload["runner_instance"]' in body


def test_frontend_reacts_to_stalled_phase():
    js = COMPOSER_JS.read_text(encoding="utf-8")
    branch = js.split('phase === "stalled"', 1)
    assert len(branch) == 2, "stalled 국면에 화면이 반응하지 않는다"
    tail = branch[1].split("} else if", 1)[0]
    # 서버가 말풍선 본문을 바꿔 두므로 **이력을 다시 읽어야** 그것이 보인다.
    assert "loadHistory(" in tail
    # 종결로 다루면 안 된다 — 러너가 다시 켜지면 답이 온다.
    assert "_forgetPendingBridgeTask" not in tail


# ── 자체 적대 검증에서 잡힌 것들 (P1 4건) ─────────────────────────────────────
#
# 「인스턴스 축을 새긴다」는 결정이 `ClaimedClient` 의 **값 형식**을 바꿨고, 그 값을 전량
# 일치로 비교하던 소비처가 세 곳 있었다. 형식만 바꾸고 두면 러너의 제출·첨부 읽기·취소
# 통보가 모두 조용히 죽는다 — 「배선은 넣었는데 신호가 도달하지 않는」 부류의 정확한 사례다.


def test_claimed_client_matches_tolerates_instance_suffix():
    from shared.bridge_tasks import claimed_client_matches

    assert claimed_client_matches("console-manual#abc123", "console-manual")
    assert claimed_client_matches("console-manual", "console-manual")
    # 컬럼 추가 이전 점유(NULL)는 대조 근거가 없다 — 종전 규약대로 통과.
    assert claimed_client_matches(None, "console-manual")
    # 다른 세션은 여전히 막힌다(경계가 느슨해지지 않았다).
    assert not claimed_client_matches("other-cli#abc123", "console-manual")


def test_submit_and_attachment_read_use_prefix_comparison():
    """제출·첨부 읽기의 점유자 경계가 **인스턴스 접미를 견딘다**.

    전량 일치로 남으면: 제출은 rowcount 0 → 「점유자가 아니다」(조사를 끝낸 답변이 버려진다),
    첨부 읽기는 409 → 「다른 세션이 점유 중」(첨부가 붙은 질문은 그 자리에서 죽는다).
    """
    text = AI_TOOLS.read_text(encoding="utf-8")
    # 제출 — SQL 안이라 파이썬으로 끌어올 수 없다(원자적 UPDATE 조건).
    assert "SUBSTRING_INDEX(ClaimedClient, '#', 1) = %s)))" in text
    # 첨부 읽기 — 파이썬 술어. 전량 비교 잔재가 남아 있지 않아야 한다.
    assert "_claimed_client_matches(claimed_client, ctx.get(\"client_id\"))" in text
    assert 'str(claimed_client) != str(ctx.get("client_id")' not in text


def test_no_progress_announcement_is_bounded():
    """고지가 **매 tick 열리지 않고**, lease 를 넘긴 경과는 말하지 않는다.

    - SSE tick 은 1초다. 프로세스 지역 가드가 없으면 무진행 30분에 PG 커넥션 1,800회.
    - 배포 시 점유 회수는 `ClaimedAt` 을 24시간 과거로 민다 → 그 창에서 고지하면 화면에
      「1440분째」가 뜬다(관측이 아니라 날조).
    """
    text = AI_TOOLS.read_text(encoding="utf-8")
    body = text.split("def _announce_no_progress(", 1)[1].split("\ndef ", 1)[0]
    assert "_NO_PROGRESS_ANNOUNCED" in body, "매 tick 재시도 가드가 없다"
    assert "_BRIDGE_CLAIM_LEASE_MIN * 60" in body, "lease 초과 경과 상한이 없다"
    # 시도 기록이 **갱신보다 먼저** 여야 한다 — 실패가 반복되는 상황이 곧 커넥션이 비싼 상황이다.
    assert body.index("_NO_PROGRESS_ANNOUNCED.add(") < body.index("_mark_bridge_no_progress(")


def test_reclaim_clears_the_announced_marker():
    """재점유하면 무진행 고지를 **다시 할 수 있어야** 한다.

    표지가 남으면 두 번째로 멈췄을 때 화면이 「조사·작성 중」에 다시 박제된다 — 이 cycle 이
    없애려던 바로 그 상태다(라이브에서 실제로 두 번 이어졌다).
    """
    text = AI_TOOLS.read_text(encoding="utf-8")
    body = text.split("def _mark_bridge_working(", 1)[1].split("\ndef ", 1)[0]
    assert "_NO_PROGRESS_ANNOUNCED.discard(" in body
