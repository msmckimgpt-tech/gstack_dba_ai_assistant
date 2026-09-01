"""feature-0043 — **낡은 러너가 최신 러너의 질문을 가로채는** 결함 (TASK-20260901T173000).

## 라이브에서 무슨 일이 있었나 (2026-09-01)

바로 앞 cycle(`TASK-20260901T160000`)이 「실패 사유가 사용자에게 도달하지 않는」 결함을 고쳐
배포했고, 사용자는 안내대로 웹 화면의 **「연결 준비」로 최신 러너를 다시 연결**했다. 그런데
같은 증상이 그대로 재발했다.

원인은 러너가 **둘** 떠 있었다는 것이다 — 같은 계정(`account 10`)에:

| 러너 | 지문 | 상태 |
|---|---|---|
| 새로 연결한 러너 (17:19:51 대기 시작) | `d0ac1263d454` = 배포본 | 최신 |
| 이전 세션이 남긴 러너 (15:42~) | `0a4ba732366c` | **옛 코드** |

17:20:03 질문을 **옛 러너가 먼저 집어** 5초 만에 옛 동작으로 답했다. 점유는 선착순 원자
UPDATE 라 「누가 먼저 폴링했는가」가 승자를 정하고, 서버는 그 러너가 낡았다는 사실을
(`runner_update.stale_build`) **알면서도 말만 하고 내줬다.**

사용자 입장에서 이것은 «고쳤다는데 그대로» 이고, 화면 어디에도 러너가 둘이라는 사실이 없다.
안내는 지켰는데 결과가 같으니, 다음에 그 사람이 안내를 믿을 이유도 사라진다.

## 왜 서버에서만 막을 수 있나

낡은 러너는 **정의상 우리 새 코드를 갖고 있지 않다.** 러너측에 「낡으면 집지 마라」를 넣어도
지금 문제를 일으키는 그 프로세스에는 영원히 닿지 않는다. 서버 판정만이 러너 갱신 없이
즉시 발효한다.

## 왜 «절대» 가 아니라 «상대» 판정인가

배포 직후에는 **모든** 사용자의 러너가 배포본과 다르다. 「낡았으면 거절」을 절대 규칙으로
두면 매 배포가 전 사용자 서비스 중단이 된다. 그래서 **같은 계정에 최신 러너가 실제로 듣고
있을 때만** 양보시킨다 — 단독 러너는 낡았어도 종전대로 일한다.
"""
from __future__ import annotations

import pathlib
import re
import sys

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_REPO = _UNIT.parent
_WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
for _p in (str(_REPO), str(_WEB_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

AI_TOOLS = _WEB_SRC / "routers" / "ai_tools.py"

DEPLOYED = "d0ac1263d454"
STALE = "0a4ba732366c"


def _store():
    import oauth_store  # noqa: PLC0415

    return oauth_store


class _Cur:
    """`stale_runner_must_yield` 가 쏘는 두 질의에만 답하는 최소 더블.

    ⚠ `%s` 개수와 넘어온 파라미터 개수를 **매 실행 검증**한다. 이 검증이 없으면 arity 가
    어긋난 질의가 조용히 «조건 불일치» 로 떨어져, 실제로는 판정이 죽었는데 테스트는
    「양보 안 함」을 정상으로 읽는다(이 저장소가 이미 겪은 함정).
    """

    def __init__(self, mine: str | None, peer_rows: list):
        self.mine, self.peer_rows = mine, peer_rows
        self.queries: list[tuple[str, tuple]] = []
        self._row = None

    def execute(self, sql, params=()):
        assert sql.count("%s") == len(params), (
            f"파라미터 개수 불일치: %s {sql.count('%s')}개 vs 인자 {len(params)}개")
        self.queries.append((sql, tuple(params)))
        if "t.TokenHash = %s" in sql and "AccountId" not in sql:
            self._row = (self.mine,) if self.mine is not None else None
        else:
            self._row = self.peer_rows[0] if self.peer_rows else None

    def fetchone(self):
        return self._row

    def close(self):
        pass


def _yield_to(mine, peers, deployed=DEPLOYED, token="tok"):
    return _store().stale_runner_must_yield(_Cur(mine, peers), token, 10, deployed)


# ── 판정 ──────────────────────────────────────────────────────────────────────


def test_live_case_stale_runner_yields_to_fresh_peer():
    """라이브 재현: 옛 러너 + 같은 계정의 최신 러너 → 양보한다."""
    assert _yield_to(STALE, [(1,)]) == STALE


def test_lone_stale_runner_keeps_working():
    """최신 러너가 **없으면** 낡아도 계속 일한다 — 배포 직후 전 사용자 중단 방지."""
    assert _yield_to(STALE, []) == ""


def test_fresh_runner_never_yields():
    assert _yield_to(DEPLOYED, [(1,)]) == ""


def test_no_fingerprint_reported_is_not_a_verdict():
    """지문을 신고하지 않는 구 러너는 «다르다» 고 말할 근거가 없다(fail-open)."""
    assert _yield_to("", [(1,)]) == ""
    assert _yield_to(None, [(1,)]) == ""


def test_unknown_deployed_build_is_not_a_verdict():
    assert _yield_to(STALE, [(1,)], deployed="") == ""


def test_missing_token_or_account_is_not_a_verdict():
    st = _store()
    assert st.stale_runner_must_yield(_Cur(STALE, [(1,)]), "", 10, DEPLOYED) == ""
    assert st.stale_runner_must_yield(_Cur(STALE, [(1,)]), "tok", 0, DEPLOYED) == ""


# ── 최신 러너 후보의 자격 (굶기지 않기 위한 자물쇠) ────────────────────────────


def test_peer_lookup_excludes_self_and_requires_live_fresh_heartbeat():
    """비교 대상은 **남**이고, 살아 있고, 하트비트가 창 안이어야 한다.

    셋 중 하나라도 빠지면 죽은 행 하나가 멀쩡한 러너를 영구히 굶긴다.
    """
    cur = _Cur(STALE, [(1,)])
    _store().stale_runner_must_yield(cur, "tok", 10, DEPLOYED)
    peer_sql = cur.queries[-1][0]
    assert "t.TokenHash <> %s" in peer_sql, "자기 자신을 «다른 러너» 로 셌다"
    assert "t.RunnerBuild = %s" in peer_sql, "배포본과 같은 지문만 세야 한다"
    assert "LastHeartbeatAt IS NOT NULL" in peer_sql and "DATE_SUB" in peer_sql, \
        "하트비트 신선도를 보지 않으면 죽은 행이 후보가 된다"
    assert "_LIVE" not in peer_sql and "RevokedAt IS NULL" in peer_sql, \
        "폐기·만료 토큰이 후보에서 빠지지 않는다"


def test_verdict_uses_the_same_live_predicate_as_auth():
    """양쪽 질의가 인증과 **같은 술어**를 쓴다 — 따로 세면 느슨한 쪽이 진실이 된다."""
    src = (_WEB_SRC / "oauth_store.py").read_text(encoding="utf-8")
    body = src.split("def stale_runner_must_yield", 1)[1].split("\ndef ", 1)[0]
    assert body.count("{_LIVE_TOKEN_PREDICATE}") == 2


# ── 배선 (억제 3지점 + 집행 1지점) ────────────────────────────────────────────


def _fn(name: str) -> str:
    src = AI_TOOLS.read_text(encoding="utf-8")
    body = src.split(f"def {name}(", 1)[1]
    return body.split("\n@router.", 1)[0]


def test_claim_request_enforces_the_yield():
    """**집행은 claim 이다** — 러너는 다른 경로로 알아낸 task_id 로 곧장 claim 할 수 있다."""
    body = _fn("claim_request")
    assert "_stale_runner_yield_to(" in body, "집행 지점에 판정이 없다"
    i_gate = body.index("_stale_runner_yield_to(")
    i_update = body.index("UPDATE WebAiTasks SET ClaimedBy")
    assert i_gate < i_update, "판정이 점유 UPDATE 뒤에 있으면 이미 뺏긴 뒤다"
    assert "409" in body[i_gate:i_update]


def test_list_and_wait_suppress_work_for_a_yielding_runner():
    """목록·대기도 비운다 — 안 그러면 낡은 러너가 집었다 409 받으며 계정 상한을 태운다."""
    assert "_stale_runner_yield_to(" in _fn("list_open_requests")
    wait = _fn("wait_for_request")
    assert "_wait_yield_to" in wait
    assert "found = [] if _wait_yield_to else" in wait, "대기 루프가 일감을 계속 보여준다"


def test_wait_does_not_busy_loop_the_yielding_runner():
    """대기에서 **즉시 반환하지 않는다** — 낡은 러너는 즉시 재호출이 정상 동작이다.

    즉시 반환하면 옛 러너를 막으려던 조치가 초당 수십 회 서버를 때리는 장치가 된다.
    """
    wait = _fn("wait_for_request")
    head = wait[:wait.index("with _drain.waiting()")]
    assert "_stale_runner_yield_to(" in head, "판정이 대기 시작 전에 없다"
    assert not re.search(r"if _wait_yield_to:\s*\n\s*return", head), \
        "양보 판정 직후 즉시 반환 — busy-loop 를 만든다"


def test_cancel_notice_still_reaches_a_yielding_runner():
    """취소 통보는 막지 않는다 — 이미 집어 둔 작업을 끊는 신호는 낡은 러너에도 필요하다."""
    wait = _fn("wait_for_request")
    # ⚠ 주석은 제외한다 — 설명문에 이름이 등장하는 것과 **코드가 그 이름으로 분기하는 것**은
    #   다르다(주석을 세면 이 단언은 문구 편집으로 깨지거나 통과한다).
    code = "\n".join(ln for ln in wait.splitlines() if not ln.lstrip().startswith("#"))
    _anchor = "found = [] if _wait_yield_to else"
    tail = code[code.index(_anchor) + len(_anchor):]   # 억제 줄 **자신은** 제외하고 그 뒤만
    between = tail[:tail.index("SELECT TaskId FROM WebAiTasks")]
    assert "_wait_yield_to" not in between, \
        "억제와 취소 조회 사이에 양보 분기가 끼어 취소 통보가 끊긴다"
    assert not re.search(r"canceled\s*=\s*\[\]\s*if\s*_wait_yield_to", tail), \
        "취소 목록까지 양보 판정으로 비웠다 — 사용자가 누른 중단이 그 러너에 닿지 않는다"


def test_notice_is_single_sourced():
    """러너·사람이 읽는 문장이 한 곳에서 나온다 — 두 벌이면 하나만 고쳐진다."""
    src = AI_TOOLS.read_text(encoding="utf-8")
    assert src.count("def _stale_runner_notice(") == 1
    assert src.count("_stale_runner_notice(") >= 4  # 정의 1 + 호출 3 이상


def test_verdict_failure_falls_open():
    """판정이 실패하면 **양보 없음**으로 떨어진다 — 잘못 양보시키면 멀쩡한 러너가 굶는다."""
    body = AI_TOOLS.read_text(encoding="utf-8").split(
        "def _stale_runner_yield_to(", 1)[1].split("\n\n\n", 1)[0]
    assert "except Exception" in body
    tail = body[body.index("except Exception"):]
    assert 'return ""' in tail, "실패가 «양보» 로 떨어지면 안 된다"


# ── 러너 자가 종료 (사용자 결정 2026-09-01) ───────────────────────────────────

RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"


def test_server_reports_superseded_separately_from_stale_build():
    """`superseded` 는 `stale_build` 와 **다른 필드**다.

    합치면 배포 직후 단독 러너까지 스스로 종료해 전 사용자 서비스가 끊긴다 —
    `stale_build` 는 혼자여도 참이고, 그때는 계속 일해야 한다.
    """
    src = AI_TOOLS.read_text(encoding="utf-8")
    hb = src.split("def bridge_heartbeat(", 1)[1].split("\n@router.", 1)[0]
    assert '"superseded": bool(_superseded_by)' in hb
    assert "_stale_runner_yield_to(" in hb, "판정 없이 필드만 만들면 항상 False 다"
    i_hb = hb.index("_stale_runner_yield_to(")
    i_out = hb.index('"superseded"')
    assert i_hb < i_out


def test_superseded_verdict_is_account_scoped():
    """계정이 다르면 판정 대상이 아니다 — 여러 계정 러너 병존은 허용(사용자 결정)."""
    body = (_WEB_SRC / "oauth_store.py").read_text(encoding="utf-8").split(
        "def stale_runner_must_yield", 1)[1].split("\ndef ", 1)[0]
    assert "t.AccountId = %s" in body, "계정 경계 없이 남의 러너를 후보로 센다"


def test_runner_retires_when_superseded():
    """러너가 신호를 받으면 **하던 일을 마치고** 종료한다."""
    src = RUNNER.read_text(encoding="utf-8")
    hb = src.split("def start_heartbeat(", 1)[1].split("\ndef ", 1)[0]
    assert '_u.get("superseded")' in hb and "_SUPERSEDED.set()" in hb, \
        "하트비트가 신호를 세우지 않는다"
    main = src.split("def main(", 1)[1]
    assert "_SUPERSEDED.is_set()" in main, "대기 루프가 신호를 보지 않는다"
    gate = main.index("_SUPERSEDED.is_set()")
    assert "shutdown_after_drain(" in main[gate:gate + 800], \
        "진행 중 작업을 마치지 않고 죽는다(답변 유실)"


def test_runner_retires_before_pulling_more_work():
    """물러남 판정이 **대기 호출 앞**에 있다 — 뒤면 옛 답을 한 번 더 낸다."""
    main = RUNNER.read_text(encoding="utf-8").split("def main(", 1)[1]
    assert main.index("_SUPERSEDED.is_set()") < main.index('api.call("wait_for_request"')


def test_runner_does_not_kill_itself_on_stale_build_alone():
    """`stale_build` 만으로는 죽지 않는다 — 단독 러너는 낡아도 계속 일한다."""
    hb = RUNNER.read_text(encoding="utf-8").split(
        "def start_heartbeat(", 1)[1].split("\ndef ", 1)[0]
    stale_branch = hb.split('_u.get("stale_build")', 1)[1][:600]
    assert "_SUPERSEDED.set()" not in stale_branch


def test_served_runner_matches_canonical():
    import hashlib

    served = _UNIT / "feature-0003-agent-web-ui" / "src" / "static" / "agent" / "bridge_agent.py"
    assert hashlib.sha256(served.read_bytes()).hexdigest() == \
        hashlib.sha256(RUNNER.read_bytes()).hexdigest()
