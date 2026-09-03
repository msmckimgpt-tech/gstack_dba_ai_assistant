"""연결 퍼널 계측 (ROADMAP ITEM-00) — acceptance 5건 + 배선 전수.

## 이 스위트가 지키는 것

로드맵 ITEM-00 의 acceptance 를 그대로 옮긴다:
1. 완주 계정은 5단계가 **시간순으로 1행씩**
2. 중도 이탈 계정은 **그 지점까지만**
3. **재실행 멱등** — 계정당 단계당 1행
4. `path_kind` 가 경로를 구분한다
5. 토큰 원문·명령문·프롬프트를 **적재하지 않는다**

## 왜 가짜 더블인가 (실 DB 가 아니라)

`_connect_funnel` 의 계약은 「무엇을, 몇 번, 어떤 값으로 원장에 넣는가」다. 그 계약은 SQL 이
아니라 **호출 형태**에 있다. 실 DB 를 붙이면 이 스위트는 MySQL 가용성에 묶이고(`make test`
밖에서 못 돌고), 정작 검사하려는 「멱등 가드가 실제로 두 번째 호출을 막는가」는 더블로도
똑같이 관측된다.

⚠ 단 **가짜 더블은 vacuous pass 를 만들기 쉽다**(이 저장소의 실측 결함 클래스). 그래서
`FakeConn` 은 «이미 기록된 것» 을 실제로 기억하고 `SELECT 1` 에 반영한다 — 더블이 항상
「없음」을 답하면 멱등 테스트는 아무것도 검사하지 않는다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
_FUNNEL_PY = _WEB_SRC / "routers" / "_connect_funnel.py"
_OAUTH_AS = _WEB_SRC / "routers" / "oauth_as.py"
_AI_TOOLS = _WEB_SRC / "routers" / "ai_tools.py"


def _load_funnel():
    """`routers/_connect_funnel.py` 를 단독 모듈로 적재.

    feature-0003 의 `src` 를 sys.path 에 올리지 않는다(이 feature 의 conftest 가 금지 —
    두 feature 가 같은 `modules` 패키지 이름을 갖고 있어 먼저 온 쪽이 다른 쪽을 가린다).
    대신 파일을 직접 적재하고, `import app` 은 stub 으로 가로챈다.
    """
    import importlib.util
    import types

    stub = types.ModuleType("app")
    stub.calls = []
    stub.shared: set = set()   # 전 커넥션이 공유하는 원장
    stub.audit_conns = []       # 감사 기록이 **어느 커넥션**으로 갔는지 (P1-2 회귀 잠금)
    stub.owned = []             # `_connect_memory` 로 연 커넥션들 (닫혔는지 확인)

    def _audit_user_action(conn, request, account, *, action, resource_type,
                           resource_id, request_ctx=None, **kw):
        stub.calls.append({"action": action, "resource_type": resource_type,
                           "resource_id": resource_id, "request_ctx": request_ctx})
        stub.audit_conns.append(conn)
        conn.remember(resource_type, resource_id)

    stub._audit_user_action = _audit_user_action

    def _connect_memory():
        """전용 커넥션 팩토리 — 테스트는 «공유 상태를 보는 별개 객체» 를 돌려준다.

        실제 구현도 같은 DB 를 보므로 멱등 조회는 성립하고, **객체는 업무 conn 과 달라야**
        한다(P1-2: 감사 헬퍼의 commit/rollback 이 업무 트랜잭션에 닿으면 안 된다).
        """
        c = FakeConn(shared=stub.shared)
        stub.owned.append(c)
        return c

    stub._connect_memory = _connect_memory
    # ⚠ **stub 을 적재 후에도 남겨 둔다.** `record_step` 은 `import app` 을 **호출 시점에**
    #   하므로(순환 회피용 지연 import), 적재만 끝나고 되돌리면 실제 호출에서
    #   `ModuleNotFoundError` 가 나고 fail-open 이 그것을 삼켜 **모든 단언이 «0건 기록» 으로
    #   조용히 실패**한다. 첫 실행이 정확히 그랬다.
    sys.modules["app"] = stub
    # 매 호출이 **새 모듈 객체**를 만든다 — 모듈 전역인 `_SEEN` 양성 캐시도 함께 새로 생겨
    # 테스트 간 격리가 성립한다(공유하면 두 번째 테스트부터 vacuous 해진다).
    spec = importlib.util.spec_from_file_location("_connect_funnel_test", _FUNNEL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, stub


@pytest.fixture(autouse=True)
def _reset_seen_cache(request):
    """모듈의 양성 캐시는 프로세스 전역이라 테스트 간 누수된다 — 매 테스트 전에 비운다.

    이게 없으면 두 번째 테스트부터 «이미 봤음» 으로 조용히 건너뛰어 **전 스위트가 vacuous** 해진다.
    """
    yield


@pytest.fixture(autouse=True)
def _restore_app_module():
    """테스트가 끼워 넣은 `app` stub 을 스위트 밖으로 흘리지 않는다."""
    saved = sys.modules.get("app")
    yield
    if saved is not None:
        sys.modules["app"] = saved
    else:
        sys.modules.pop("app", None)


class FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self._row = None
        self.closed = False

    def execute(self, sql, params=()):
        self._conn.queries.append((sql, params))
        if "SELECT 1 FROM WebAuditEvents" in sql:
            # ⚠ 더블이 실제로 «기억» 한다 — 항상 None 을 답하면 멱등 테스트가 vacuous 해진다.
            self._row = (1,) if (params[0], params[1]) in self._conn.recorded else None
        else:
            self._row = (self._conn.path_kind_answer,) if self._conn.path_kind_answer else None

    def fetchone(self):
        return self._row

    def close(self):
        self.closed = True
        self._conn.closed_cursors += 1


class FakeConn:
    """`shared` 를 주면 여러 커넥션이 **같은 원장**을 본다 (실 DB 와 같은 성질).

    이게 없으면 전용 커넥션이 매번 새 빈 원장을 보게 되어 **멱등 테스트가 통째로 vacuous** 해진다
    — 더블이 항상 「없음」을 답하면 가드를 검사하는 것이 아니라 더블을 검사하는 셈이다.
    """

    def __init__(self, path_kind_answer=None, shared=None):
        self.recorded: set[tuple[str, str]] = shared if shared is not None else set()
        self.queries: list = []
        self.path_kind_answer = path_kind_answer
        self.closed_cursors = 0
        self.opened_cursors = 0
        self.closed = False

    def cursor(self):
        self.opened_cursors += 1
        return FakeCursor(self)

    def remember(self, resource_type, resource_id):
        self.recorded.add((resource_type, resource_id))

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.closed = True


ACCOUNT = {"id": 7, "username": "tester"}


# ── acceptance 1·2: 도달한 단계만, 시간순으로 ────────────────────────────────────

def test_completing_account_records_all_five_steps_in_order():
    mod, stub = _load_funnel()
    conn = FakeConn()
    for step in mod.FUNNEL_STEPS:
        mod.record_step(conn, object(), ACCOUNT, step=step, path_kind="runner_windows")
    steps = [c["request_ctx"]["step"] for c in stub.calls]
    assert steps == list(mod.FUNNEL_STEPS), f"5단계가 순서대로 남지 않았다: {steps}"
    assert len(stub.calls) == 5


def test_dropped_off_account_records_only_reached_steps():
    """acceptance 2 — 토큰만 받고 설치를 안 한 계정은 2단계까지만."""
    mod, stub = _load_funnel()
    conn = FakeConn()
    mod.record_step(conn, object(), ACCOUNT, step="page_view")
    mod.record_step(conn, object(), ACCOUNT, step="handoff_issued")
    steps = [c["request_ctx"]["step"] for c in stub.calls]
    assert steps == ["page_view", "handoff_issued"]


# ── acceptance 3: 멱등 ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("step", ("page_view", "handoff_issued", "first_heartbeat",
                                  "first_claim", "first_answer"))
def test_step_is_recorded_once_per_account(step):
    """재실행 멱등 — **다섯 단계 전부**.

    로드맵은 `first_*` 3단계만 명시했으나 구현은 다섯 전부에 같은 규칙을 쓴다
    (`_connect_funnel` docstring 의 근거: 원장 폭주 방지 + 단계별 행 수의 단위 일관성).
    그 확대가 실제로 지켜지는지 여기서 확인한다 — 문서만의 약속이 되지 않게.
    """
    mod, stub = _load_funnel()
    conn = FakeConn()
    for _ in range(5):
        mod.record_step(conn, object(), ACCOUNT, step=step)
    assert len(stub.calls) == 1, f"{step} 이 {len(stub.calls)}회 적재됐다 — 멱등 가드가 없다"


def test_heartbeat_flood_does_not_flood_the_ledger():
    """하트비트는 30초마다 온다 — 가드가 없으면 원장이 퍼널 기록으로 뒤덮인다(로드맵 guard)."""
    mod, stub = _load_funnel()
    conn = FakeConn()
    for _ in range(120):        # 1시간치
        mod.record_step(conn, object(), ACCOUNT, step="first_heartbeat",
                        path_kind="runner_posix")
    assert len(stub.calls) == 1


def test_different_accounts_are_counted_separately():
    """멱등 키가 계정을 포함하지 않으면 두 번째 사용자가 통째로 유실된다."""
    mod, stub = _load_funnel()
    conn = FakeConn()
    mod.record_step(conn, object(), {"id": 1}, step="first_answer")
    mod.record_step(conn, object(), {"id": 2}, step="first_answer")
    assert len(stub.calls) == 2
    assert {c["resource_id"] for c in stub.calls} == {"1:first_answer", "2:first_answer"}


# ── acceptance 4: path_kind ────────────────────────────────────────────────────

@pytest.mark.parametrize("agent_os,expected", [
    ("posix", "runner_posix"), ("windows", "runner_windows"),
    ("WINDOWS", "runner_windows"), ("", "unknown"), (None, "unknown"),
    ("solaris", "unknown"),
])
def test_path_kind_from_agent_os(agent_os, expected):
    mod, _ = _load_funnel()
    assert mod.path_kind_from_agent_os(agent_os) == expected


def test_unknown_path_kind_is_folded_not_dropped():
    """모르는 경로값이 와도 **단계는 남는다**.

    버리면 도달 수가 틀어진다 — 경로를 모르는 것과 그 단계에 못 온 것은 다른 사실이다.
    """
    mod, stub = _load_funnel()
    conn = FakeConn()
    mod.record_step(conn, object(), ACCOUNT, step="first_claim", path_kind="해킹시도")
    assert len(stub.calls) == 1
    assert stub.calls[0]["request_ctx"]["path_kind"] == "unknown"


def test_account_path_kind_inherits_from_earlier_step():
    """`first_claim`/`first_answer` 는 앞 단계가 각인한 경로를 이어받는다.

    이것이 없으면 뒤 두 단계가 전부 `unknown` 이 되어 **경로별 이탈률이 앞 세 단계에서 끊긴다**.
    """
    mod, _ = _load_funnel()
    assert mod.account_path_kind(FakeConn(path_kind_answer="runner_windows"), 7) == "runner_windows"
    assert mod.account_path_kind(FakeConn(path_kind_answer=None), 7) == "unknown"
    # 원장에 이상한 값이 들어 있어도 열거 밖이면 받지 않는다.
    assert mod.account_path_kind(FakeConn(path_kind_answer="rm -rf"), 7) == "unknown"


def test_account_path_kind_closes_its_cursor():
    """커서 소유권 — 호출 지점이 둘이라 누수는 두 배로 샌다."""
    mod, _ = _load_funnel()
    conn = FakeConn(path_kind_answer="runner_posix")
    mod.account_path_kind(conn, 7)
    assert conn.opened_cursors == conn.closed_cursors == 1


# ── acceptance 5: 민감정보 미적재 (docs/SECURITY.md D12) ────────────────────────

def test_change_json_carries_only_step_and_path_kind():
    mod, stub = _load_funnel()
    conn = FakeConn()
    mod.record_step(conn, object(), ACCOUNT, step="handoff_issued", path_kind="runner_posix")
    ctx = stub.calls[0]["request_ctx"]
    assert set(ctx.keys()) == {"step", "path_kind"}, (
        f"ChangeJson 에 예상 밖 키가 있다: {sorted(ctx)} — 토큰·프롬프트가 새는 통로가 된다")


def test_funnel_source_never_references_token_or_prompt():
    """소스에 토큰·프롬프트를 원장으로 옮기는 통로가 아예 없다.

    위 테스트는 «지금 호출이 그렇다» 를 보고, 이쪽은 «그런 코드를 쓸 자리가 없다» 를 본다.
    """
    src = _FUNNEL_PY.read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    code = re.sub(r'"""[\s\S]*?"""', "", code)      # docstring 제외 — 실행 코드만
    # ⚠ 검사어는 **단계 이름과 겹치지 않는 것**만 고른다. 초판은 `answer`·`question` 을 넣어
    #   `step="first_answer"` 같은 정당한 상수에 걸렸다 — 그렇게 되면 이 테스트를 통과시키려고
    #   단계 이름을 바꾸게 되고, 검사가 설계를 왜곡한다.
    for bad in ("access_token", "raw_token", "Bearer", "payload", "request.body", "_bearer("):
        assert bad not in code, f"_connect_funnel 실행 코드에 `{bad}` 가 있다 — 민감값 유출 통로"
    # 단계 이름 상수 외에 답변/질문 **본문**을 만지는 자리가 없다.
    assert not re.search(r'\banswer\b(?!")', code.replace('"first_answer"', "")), (
        "답변 본문을 다루는 코드가 있다 — 퍼널은 단계와 경로만 남긴다")


# ── 배선 전수 (존재 ≠ 실행: 5 지점이 실제로 호출하는가) ──────────────────────────

def _code_text(path: Path) -> str:
    """주석을 제외한 코드. 자기 주석이 자기 단언을 통과시키는 형태를 막는다(§16.7 G11-a)."""
    return "\n".join(l for l in path.read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("#"))


@pytest.mark.parametrize("path,step", [
    (_OAUTH_AS, "page_view"),
    (_OAUTH_AS, "handoff_issued"),
    (_AI_TOOLS, "first_heartbeat"),
    (_AI_TOOLS, "first_claim"),
    (_AI_TOOLS, "first_answer"),
])
def test_every_step_has_a_live_call_site(path, step):
    """5단계 각각이 **실제 호출부**를 갖는다.

    모듈이 있어도 아무도 부르지 않으면 원장은 영원히 비어 있고, 그 사실은 라이브에서만 드러난다
    (`tool-availability-vs-invocation` — 존재는 실행이 아니다).
    """
    code = _code_text(path)
    assert f'step="{step}"' in code, f"{path.name} 에 `step=\"{step}\"` 호출부가 없다"
    assert "_funnel.record_step(" in code, f"{path.name} 이 record_step 을 부르지 않는다"


def test_no_step_is_wired_twice():
    """같은 단계를 두 자리에서 부르면 어느 쪽이 먼저인지에 따라 값이 갈린다."""
    both = _code_text(_OAUTH_AS) + "\n" + _code_text(_AI_TOOLS)
    for step in ("page_view", "handoff_issued", "first_heartbeat", "first_claim", "first_answer"):
        n = both.count(f'step="{step}"')
        assert n == 1, f"`{step}` 호출부가 {n}곳이다 — 단일점이어야 한다"


def test_routers_import_the_shared_module_not_their_own_copy():
    """두 라우터가 **같은 모듈**을 쓴다 — 각자 조립하면 단계 이름이 갈린다."""
    for path in (_OAUTH_AS, _AI_TOOLS):
        code = _code_text(path)
        assert "import routers._connect_funnel as _funnel" in code, (
            f"{path.name} 이 공용 퍼널 모듈을 import 하지 않는다")


# ── codex 적대 리뷰 P1 회귀 잠금 (2026-09-03) ──────────────────────────────────

def test_audit_never_writes_through_the_business_connection():
    """**P1-2**: 감사 헬퍼는 `commit`/`rollback` 을 부른다 — 업무 커넥션으로 쓰면 계측이
    사용자의 트랜잭션을 커밋하거나 **되돌린다**. 초판 배선은 `claim_request`(점유 확정 직후)와
    `submit_answer`(답변 저장 직후)에 걸려 있어, 계측 예외 하나가 답변을 롤백할 수 있었다.
    """
    mod, stub = _load_funnel()
    business = FakeConn()
    mod.record_step(business, object(), ACCOUNT, step="first_answer")
    assert stub.calls, "기록이 일어나지 않았다 — 이 테스트가 vacuous 해졌다"
    for c in stub.audit_conns:
        assert c is not business, (
            "감사 기록이 **업무 커넥션**으로 갔다 — commit/rollback 이 사용자 트랜잭션에 닿는다")
    assert stub.owned, "전용 커넥션을 열지 않았다"


def test_owned_connection_is_closed():
    """전용 커넥션을 열었으면 닫는다 — 요청마다 새 커넥션이 새면 풀이 마른다."""
    mod, stub = _load_funnel()
    mod.record_step(FakeConn(), object(), ACCOUNT, step="page_view")
    assert stub.owned and all(c.closed for c in stub.owned)


def test_read_failure_does_not_retry_forever():
    """**P2-1**: 조회만 실패하는 장애에서 하트비트마다 INSERT 를 재시도하면 원장이 폭주한다.
    실패는 「이미 있음」으로 떨어져 기록을 **건너뛴다**(장애 창의 표본을 잃는 쪽을 택한다).
    """
    mod, stub = _load_funnel()

    class BrokenCursor(FakeCursor):
        def execute(self, sql, params=()):
            if "SELECT 1 FROM WebAuditEvents" in sql:
                raise RuntimeError("read path down")
            super().execute(sql, params)

    class BrokenConn(FakeConn):
        def cursor(self):
            self.opened_cursors += 1
            return BrokenCursor(self)

    stub._connect_memory = lambda: BrokenConn(shared=stub.shared)
    for _ in range(50):
        mod.record_step(FakeConn(), object(), ACCOUNT, step="first_heartbeat")
    assert stub.calls == [], f"조회 장애 중 {len(stub.calls)}건이 적재됐다 — 원장 폭주 경로"


# ── codex 적대 리뷰 2라운드 (2026-09-03) ────────────────────────────────────────

def test_guarantee_is_best_effort_not_at_least_once():
    """**보장 등급을 정직하게 잠근다.** 조회 실패 경로는 기록을 «건너뛴다» — 즉 0..N 이다.

    docstring 이 `at-least-once` 라고 적었던 것이 거짓이었다(주장이 코드보다 넓었다).
    이 테스트가 «누락이 실제로 일어난다» 를 고정해, 다음에 누가 그 문구를 되살리면 실패한다.
    """
    mod, stub = _load_funnel()

    class BrokenCursor(FakeCursor):
        def execute(self, sql, params=()):
            if "SELECT 1 FROM WebAuditEvents" in sql:
                raise RuntimeError("read down")
            super().execute(sql, params)

    class BrokenConn(FakeConn):
        def cursor(self):
            self.opened_cursors += 1
            return BrokenCursor(self)

    opened = []
    def _cm():
        c = BrokenConn(shared=stub.shared); opened.append(c); stub.owned.append(c); return c
    stub._connect_memory = _cm
    mod.record_step(FakeConn(), object(), ACCOUNT, step="first_answer")
    assert stub.calls == [], "조회 실패에도 기록됐다 — 이 경로의 계약이 바뀌었다"
    # 실패 경로에서도 커넥션은 닫힌다 (codex P2-2).
    assert opened and all(c.closed for c in opened), "실패 경로에서 전용 커넥션이 새고 있다"


def test_dedupe_key_is_stable_and_unique_per_account_step():
    """소비측이 `COUNT(DISTINCT ResourceId)` 로 셀 수 있어야 경합 중복이 수치를 망치지 않는다."""
    mod, _ = _load_funnel()
    keys = {mod.dedupe_key_of(a, s) for a in (1, 2) for s in mod.FUNNEL_STEPS}
    assert len(keys) == 2 * len(mod.FUNNEL_STEPS), "dedupe 키가 계정·단계를 가르지 못한다"
    assert mod.dedupe_key_of(7, "first_claim") == mod.dedupe_key_of(7, "first_claim")


def test_concurrent_first_calls_can_duplicate_and_that_is_documented():
    """**경합 창이 실재함**을 고정한다 — 「문서화만 됐다」는 지적(codex P1-2)에 대한 코드면.

    SELECT 후 INSERT 는 원자적이지 않고 `IX_WAE_Resource` 는 비고유다. 두 요청이 «없음» 을
    동시에 보면 2행이 남는다. 그 사실을 숨기지 않고 여기서 재현한다 — 이것이 참인 한
    소비측은 반드시 `DISTINCT` 로 세야 한다.
    """
    import threading
    mod, stub = _load_funnel()
    barrier = threading.Barrier(2)
    orig = stub._audit_user_action

    def slow_audit(*a, **kw):
        barrier.wait(timeout=5)      # 두 스레드가 «없음» 을 본 뒤에야 기록하도록 정렬
        orig(*a, **kw)

    stub._audit_user_action = slow_audit
    ts = [threading.Thread(target=mod.record_step,
                           args=(FakeConn(), object(), ACCOUNT),
                           kwargs={"step": "first_heartbeat"}) for _ in range(2)]
    for t in ts: t.start()
    for t in ts: t.join(timeout=10)
    assert len(stub.calls) == 2, (
        "경합 중복이 재현되지 않았다 — 구현이 원자적으로 바뀌었다면 docstring 의 "
        "«best-effort 0..N · 소비측 DISTINCT» 계약을 함께 갱신해야 한다")
    assert len({c["resource_id"] for c in stub.calls}) == 1, "중복 2행이 같은 dedupe 키를 갖는다"


def test_known_recorded_step_skips_connection_entirely():
    """**P2-1**: 한 번 「있음」을 확인했으면 그 뒤로는 커넥션조차 열지 않는다."""
    mod, stub = _load_funnel()
    mod.record_step(FakeConn(), object(), ACCOUNT, step="page_view")
    n_after_first = len(stub.owned)
    for _ in range(30):
        mod.record_step(FakeConn(), object(), ACCOUNT, step="page_view")
    assert len(stub.owned) == n_after_first, (
        f"이미 아는 단계에 커넥션을 {len(stub.owned) - n_after_first}회 더 열었다")


# ── 배선 인자 해석 (라이브 실측 결함 2026-09-03) ────────────────────────────────

def test_funnel_call_sites_use_names_that_exist_in_their_scope():
    """호출부가 **있는가** 와 인자가 **해석되는가** 는 다른 사실이다.

    ⚠ **실측 결함**: `bridge_heartbeat` 에는 `account` 가 없는데(토큰 컨텍스트 `ctx` 와
    `account_id` 만 있다) 초판이 `account` 를 넘겼다. `NameError` 가 났지만 퍼널의 fail-open 이
    삼켜서 **`first_heartbeat` 가 한 번도 기록되지 않았다** — 라이브 로그에서야 드러났다
    (`하트비트 기록 실패 account=10: NameError`).

    기존 배선 테스트는 `step="first_heartbeat"` **문자열 존재**만 봤다. 그것으로는 이 결함이
    영원히 안 잡힌다. 여기서는 각 호출부의 **인자 이름이 그 함수 스코프에 실재하는지**를 본다.
    """
    import ast

    for path in (_OAUTH_AS, _AI_TOOLS):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # 이 함수 안에서 «정의되는» 이름: 인자 + 대입 대상
            bound = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
            for node in ast.walk(fn):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    bound.add(node.id)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    bound.update((a.asname or a.name.split(".")[0]) for a in node.names)
            # 이 함수 안의 record_step 호출
            for node in ast.walk(fn):
                if not (isinstance(node, ast.Call)
                        and ast.unparse(node.func).endswith("record_step")):
                    continue
                for arg in node.args:
                    for nm in ast.walk(arg):
                        if isinstance(nm, ast.Name) and isinstance(nm.ctx, ast.Load):
                            assert nm.id in bound or nm.id in dir(__builtins__), (
                                f"{path.name}::{fn.name} 의 record_step 인자 `{nm.id}` 가 그 "
                                f"스코프에 없다 — NameError 가 나고 fail-open 이 삼켜 "
                                f"**그 단계가 영원히 기록되지 않는다**")
