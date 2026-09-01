"""연결은 **명시적으로 끊을 때만** 끊긴다 — 하트비트 축 (TASK-20260828T150000).

## 무엇이 문제였나

브리지 연결의 수명은 토큰 하나에 못박혀 있었다. 콘솔 발급 `mat_` 토큰은 **발급 시점부터 최대
12시간**이고 refresh 가 없다. 그래서 이런 일이 일어났다:

    사용자는 로그아웃하지 않았다 · 브라우저도 열려 있다 · 러너도 멀쩡히 돈다
        → 그런데 12시간이 되면 `wait_for_request` 가 401 → 러너가 그 자리에서 종료
        → 사용자는 "왜 답이 안 오지" 만 남는다

세션도 같은 형태였다. 로그인 시점부터 14일 **고정**이라(슬라이딩 없음) 매일 쓰는 사람도 14일째에
로그아웃당했고, 그 세션에 묶인 브리지 토큰까지 함께 죽었다.

사용자 결정(2026-08-28): **끊는 것은 명시적 해제뿐** — 러너 종료 · 웹 로그아웃. 브라우저 종료는
해제가 아니다(러너가 살아 있으면 계속 처리한다).

## 이 스위트가 잠그는 것

| 축 | 계약 |
|---|---|
| 유지 | 하트비트가 도착하면 토큰 만료가 **뒤로 밀린다** |
| 해제 ①(로그아웃) | 세션이 죽으면 하트비트는 **되살리지 못한다**(UPDATE 조차 안 나간다) |
| 해제 ②(러너 종료) | 신호가 끊기면 창 밖에서 '대기 안 함' 이 되고 결국 만료된다 |
| 역전 금지 | 연장은 만료를 **앞당기지 않는다**(GREATEST) · 세션 수명을 **넘지 않는다**(LEAST) |
| 표시 정확도 | 러너가 **일하는 중**에도 '대기 중' 이다(하트비트 축) |
| 세션 | 활동이 있으면 밀리되 **절대 상한**이 있다 |

소스 문자열만 보지 않는다 — `heartbeat()` 와 러너 루프는 **가짜 커서·가짜 Api 로 실제 구동**한다.
"그 줄이 있는가" 와 "그 코드가 그렇게 도는가" 는 다른 사실이고, 이 저장소는 그 차이로 여러 번
vacuous pass 를 겪었다.
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import threading
from datetime import datetime, timedelta

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
STORE_PY = WEB_SRC / "oauth_store.py"
AI_TOOLS_PY = WEB_SRC / "routers" / "ai_tools.py"
WEB_CONTEXT_PY = WEB_SRC / "web_context.py"
BOOTSTRAP_PY = WEB_SRC / "routers" / "_bootstrap_schema.py"
RUNNER_PY = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"
SERVED_RUNNER_PY = WEB_SRC / "static" / "agent" / "bridge_agent.py"


def _load(path: pathlib.Path, name: str):
    """단일 파일 모듈을 **sys.path 오염 없이** 로드한다.

    이 저장소에는 top-level `modules` 패키지가 두 곳(feature-0002·0003)에 있어, 경로를 꽂는
    방식으로 로드하면 먼저 온 쪽이 다른 쪽을 세션 내내 가린다(conftest 가 경계하는 그것).
    `oauth_store` 와 러너는 둘 다 stdlib 전용이라 파일 위치만으로 로드된다.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _func(path: pathlib.Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"{path.name}: {name} 없음")


# ── 가짜 커서 — SQL 을 삼키지 않고 **모아 둔다** ────────────────────────────────


class FakeCursor:
    """`execute` 호출을 순서대로 기록하고, 미리 준 행을 순서대로 돌려준다.

    행을 큐로 두는 이유: `heartbeat()` 는 SELECT(토큰 해석) → UPDATE(연장) 두 번 실행하고,
    그 사이의 **분기**가 이 스위트의 관심사다. 행 하나만 주면 두 번째 execute 가 첫 행을 다시
    보게 되어 없는 분기를 통과시킨다.
    """

    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.executed: list[tuple[str, tuple]] = []
        self._last = None

    def execute(self, sql, params=None):
        self.executed.append((" ".join(str(sql).split()), tuple(params or ())))
        self._last = self.rows.pop(0) if self.rows else None

    def fetchone(self):
        return self._last

    def close(self):
        pass

    # 편의 — 어떤 문장이 나갔는가
    def sql_at(self, i: int) -> str:
        return self.executed[i][0]

    def has_update(self) -> bool:
        return any(s.upper().startswith("UPDATE") for s, _ in self.executed)


_LIVE_SESSION_EXPIRY = datetime.utcnow() + timedelta(days=7)


def _token_row(*, kind="access", revoked=None, expires=None,
               session_id=3, sess_revoked=0, sess_expires=_LIVE_SESSION_EXPIRY):
    """`resolve_access_token` 이 읽는 9열 행.

    (TokenType, ClientId, AccountId, SessionId, Scopes, ExpiresAt, RevokedAt,
     s.IsRevoked, s.ExpiresAt)
    """
    return (kind, "console", 7, session_id, "data.read",
            expires if expires is not None else datetime.utcnow() + timedelta(hours=1),
            revoked, sess_revoked, sess_expires)


@pytest.fixture(scope="module")
def store():
    return _load(STORE_PY, "oauth_store_hb_test")


@pytest.fixture(scope="module")
def runner():
    return _load(RUNNER_PY, "bridge_agent_hb_test")


# ── ① 유지 — 살아 있는 신호는 수명을 민다 ─────────────────────────────────────


def test_heartbeat_extends_a_live_token(store):
    """하트비트 1회 = 만료를 다시 미는 UPDATE 1회. **이것이 '끊기지 않는다' 의 실체다.**"""
    cur = FakeCursor([_token_row()])
    out = store.heartbeat(cur, "mat_live")

    assert out is not None, "유효 토큰인데 하트비트가 거절됐다"
    assert cur.has_update(), "연장 UPDATE 가 나가지 않았다 — 신호만 받고 수명은 그대로다"
    upd = cur.sql_at(1)
    assert "LastHeartbeatAt = UTC_TIMESTAMP()" in upd, "생존 시각이 기록되지 않으면 '대기 중' 판정이 못 쓴다"
    assert "ExpiresAt" in upd, "만료를 밀지 않으면 12시간 벽이 그대로 남는다"
    assert out["expires_in"] == store.HEARTBEAT_EXTEND_SEC
    assert out["interval_sec"] == store.HEARTBEAT_INTERVAL_SEC


def test_heartbeat_never_shortens_and_never_outlives_the_session(store):
    """두 방향의 역전을 SQL 이 직접 막는다.

    - `GREATEST` 없이 쓰면 **신호를 보낼수록 수명이 짧아진다**(더 먼 만료를 앞당긴다).
    - `LEAST(…, s.ExpiresAt)` 없이 쓰면 세션은 끝났는데 토큰만 사는 창이 생긴다 — 그것이
      정확히 P0-R 에서 사용자가 겪은 결함(죽은 연결을 '연결됨' 으로 안내)의 재발이다.
    """
    cur = FakeCursor([_token_row()])
    store.heartbeat(cur, "mat_live")
    upd = cur.sql_at(1)
    assert "GREATEST" in upd, "만료가 앞당겨질 수 있다(신호가 수명을 깎는다)"
    assert "LEAST" in upd and "s.ExpiresAt" in upd, "연장이 세션 수명을 넘어설 수 있다"


def test_heartbeat_targets_only_the_calling_token(store):
    """연장 대상은 **그 토큰 한 행**이다 — 계정의 다른 토큰까지 밀면 폐기가 무의미해진다."""
    cur = FakeCursor([_token_row()])
    store.heartbeat(cur, "mat_live")
    upd = cur.sql_at(1)
    assert "t.TokenHash = %s" in upd
    assert "t.RevokedAt IS NULL" in upd, "폐기된 토큰이 되살아난다"


# ── ② 해제 — 로그아웃은 하트비트보다 세다 ─────────────────────────────────────


@pytest.mark.parametrize("row, why", [
    (_token_row(sess_revoked=1), "로그아웃(세션 revoke)"),
    (_token_row(sess_expires=datetime.utcnow() - timedelta(minutes=1)), "세션 만료"),
    (_token_row(revoked=datetime.utcnow()), "토큰 폐기"),
    (_token_row(expires=datetime.utcnow() - timedelta(minutes=1)), "토큰 만료"),
    (_token_row(kind="refresh"), "access 가 아님"),
])
def test_heartbeat_cannot_resurrect_a_dead_connection(store, row, why):
    """명시적 해제는 하트비트가 되돌리지 못한다. **UPDATE 자체가 나가지 않는다.**

    여기가 뚫리면 "로그아웃했는데 내 AI 가 계속 붙어 있다" 가 된다 — 연결 유지 기능이
    권한 회수를 무력화하는 형태이므로, 이 스위트에서 가장 비싼 계약이다.
    """
    cur = FakeCursor([row])
    assert store.heartbeat(cur, "mat_x") is None, f"{why} 인데 하트비트가 통과했다"
    assert not cur.has_update(), f"{why} 인데 연장 UPDATE 가 나갔다"


def test_heartbeat_update_also_guards_expiry(store):
    """`resolve` 통과와 UPDATE 사이에 만료가 지나면 `GREATEST` 가 **죽은 토큰을 되살린다**.

    좁지만 실재하는 창이라, 같은 조건을 UPDATE 의 WHERE 에도 건다(폐기는 이미 걸려 있었다).
    """
    cur = FakeCursor([_token_row()])
    store.heartbeat(cur, "mat_live")
    upd = cur.sql_at(1)
    assert "t.ExpiresAt IS NULL OR t.ExpiresAt > UTC_TIMESTAMP()" in upd, (
        "만료 조건이 UPDATE 에 없다 — 경합 창에서 만료된 토큰의 수명이 미래로 밀린다")


def test_heartbeat_update_reuses_the_auth_predicate(store):
    """WHERE 가 인증과 **같은 술어**를 쓴다 (codex P1).

    resolve 통과와 UPDATE 사이에 로그아웃이 일어나는 창이 있다. 술어를 재사용하면 그 창에서
    세션 폐기·세션 만료·토큰 만료가 **한꺼번에** 막힌다 — 조건을 손으로 나열하면 언젠가 하나가
    빠지고, 빠진 그 하나가 정확히 회수(revocation)를 무력화한다.
    """
    cur = FakeCursor([_token_row()])
    store.heartbeat(cur, "mat_live")
    upd = cur.sql_at(1)
    # 커서가 공백을 정규화해 모으므로 상수도 같게 접어서 비교한다(문자열 동치가 목적이 아니다).
    assert " ".join(store._LIVE_TOKEN_PREDICATE.split()) in upd, (
        "UPDATE 가 자체 조건을 나열한다(술어 복제)")
    assert "s.IsRevoked = 0" in upd, "경합 창에서 로그아웃된 세션의 토큰이 연장된다"


def test_heartbeat_never_creates_an_immortal_token(store):
    """`GREATEST(NULL, x)` = NULL — 만료 없는 행을 하트비트가 **영구 토큰으로 굳힌다** (codex P1).

    스키마는 NOT NULL 이지만 술어가 `IS NULL` 을 허용하는 형태라 두 가정이 갈려 있었다.
    한쪽만 맞다고 믿지 않고 SQL 이 직접 막는다.
    """
    cur = FakeCursor([_token_row()])
    store.heartbeat(cur, "mat_live")
    upd = cur.sql_at(1)
    assert "COALESCE(t.ExpiresAt" in upd, "NULL 만료가 하트비트 뒤에도 NULL 로 남는다"
    assert "s.ExpiresAt IS NULL" in upd, "세션 만료가 NULL 이면 LEAST 가 전체를 NULL 로 만든다"


def test_heartbeat_throttles_writes(store):
    """같은 토큰이 초당 수백 번 와도 행을 다시 쓰지 않는다 (codex P2 — 쓰기 증폭)."""
    cur = FakeCursor([_token_row()])
    store.heartbeat(cur, "mat_live")
    upd, params = cur.executed[1]
    assert "t.LastHeartbeatAt <= DATE_SUB(UTC_TIMESTAMP(), INTERVAL %s SECOND)" in upd
    assert params[-1] == store.HEARTBEAT_MIN_WRITE_SEC
    # 정상 주기가 throttle 에 걸리면 연장이 아예 안 된다 — 반드시 주기보다 짧아야 한다.
    assert store.HEARTBEAT_MIN_WRITE_SEC < store.HEARTBEAT_INTERVAL_SEC


def test_heartbeat_reports_whether_it_actually_extended(store):
    """성공을 가장하지 않는다 (codex P2). 다만 `extended=False` 로 인증을 실패시키지는 않는다 —
    throttle 때문에 0행은 정상 상황이고, 그것으로 401 을 내면 러너가 멀쩡한데 죽는다."""

    class _Rc(FakeCursor):
        rowcount = 0

    out = store.heartbeat(_Rc([_token_row()]), "mat_live")
    assert out is not None, "0행이 인증 실패로 승격됐다(러너가 멀쩡한데 죽는다)"
    assert out["extended"] is False, "쓰이지 않았는데 연장됐다고 보고한다"

    class _Unknown(FakeCursor):
        rowcount = -1        # 드라이버가 지원하지 않을 때

    assert store.heartbeat(_Unknown([_token_row()]), "mat_live")["extended"] is True


def test_sql_time_axis_is_utc_not_local(store):
    """⚠ 시간 축 회귀 방지 (라이브 실측 2026-08-28).

    만료 시각은 파이썬이 `_utcnow()` 로 **UTC** 를 넣는데, 컨테이너 TZ 는 `Asia/Seoul` 이라
    MySQL `NOW()` 는 **KST 벽시계**다. 라이브 증거: 콘솔 토큰의 `CreatedAt`(DEFAULT=KST) →
    `ExpiresAt`(파이썬=UTC) 간격이 **180분**으로 저장돼 있었다 — 의도한 12시간 − 9시간.

    그 갈림의 결과가 정확히 P0-R 의 형태였다: 발급 3시간 뒤부터 **화면은 '연결 안 됨'**
    (SQL 이 KST 로 비교) **인데 인증은 통과**(파이썬이 UTC 로 비교). 여기서는 엄격한 쪽이
    화면이라, 사용자가 멀쩡한 연결을 끊긴 것으로 봤다.
    """
    src = STORE_PY.read_text(encoding="utf-8")
    # 술어·연장·최근성 전부 UTC 축. **실제로 조립된 SQL** 을 본다 — 소스에는 상수 이름만
    # 있으므로(`{_SQL_NOW}`) 문자열 검사로는 축이 뒤집혀도 보이지 않는다.
    assert "UTC_TIMESTAMP()" in store._LIVE_TOKEN_PREDICATE
    hb = FakeCursor([_token_row()])
    store.heartbeat(hb, "mat_live")
    assert "UTC_TIMESTAMP()" in hb.sql_at(1), "연장이 로컬 시각으로 계산된다(9시간 어긋난다)"
    assert "NOW()" not in hb.sql_at(1).replace("UTC_TIMESTAMP()", ""), (
        "연장 SQL 에 로컬 `NOW()` 가 남아 있다")
    hbq = FakeCursor([(1,)])
    store.account_is_heartbeating(hbq, 7)
    assert "UTC_TIMESTAMP()" in hbq.executed[0][0], "최근성 판정이 로컬 시각을 쓴다"
    # 벌거벗은 `NOW()` 가 시간 **비교·계산**에 쓰이면 축이 다시 갈린다.
    # (`RevokedAt = NOW()` 처럼 값이 NULL 여부로만 쓰이는 자리는 이 계약의 대상이 아니다.)
    for marker in ("ExpiresAt > NOW()", "DATE_ADD(NOW()", "DATE_SUB(NOW()"):
        assert marker not in src, f"로컬 시각으로 만료를 다룬다: {marker}"


def test_session_slide_uses_the_utc_axis():
    """세션 `ExpiresAt` 도 파이썬이 UTC 로 넣는다 — 로컬로 밀면 9시간을 덤으로 준다."""
    body = _func(WEB_CONTEXT_PY, "_get_authenticated_account")
    assert "DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s DAY)" in body
    assert "DATE_ADD(NOW()" not in body, "슬라이딩이 로컬 시각을 쓴다"


def test_heartbeat_uses_the_same_resolver_as_authentication(store):
    """유효성 판정을 새로 쓰지 않는다 — 따로 세면 **로그아웃을 무시하는 뒷문**이 생긴다."""
    body = _func(STORE_PY, "heartbeat")
    assert "resolve_access_token(" in body, (
        "하트비트가 자체 술어로 판정한다 — 인증 축과 갈리는 순간 느슨한 쪽이 진실이 된다")


# ── ③ 표시 — 일하는 중에도 '대기 중' ─────────────────────────────────────────


def test_listening_window_is_a_multiple_of_the_interval(store):
    """한 번 놓친 신호(순단·배포 교대)를 끊김으로 오판하지 않을 만큼만 넓다."""
    assert store.HEARTBEAT_WINDOW_SEC == 3 * store.HEARTBEAT_INTERVAL_SEC
    assert store.HEARTBEAT_INTERVAL_SEC < store.HEARTBEAT_WINDOW_SEC < store.HEARTBEAT_EXTEND_SEC


def test_heartbeating_predicate_requires_both_liveness_and_recency(store):
    """'토큰이 있다' 와 '지금 듣고 있다' 는 다른 사실이다 — 둘을 **함께** 요구한다."""
    cur = FakeCursor([(1,)])
    assert store.account_is_heartbeating(cur, 7) is True
    sql, params = cur.executed[0]
    assert "LastHeartbeatAt IS NOT NULL" in sql
    assert "DATE_SUB(UTC_TIMESTAMP(), INTERVAL %s SECOND)" in sql, "최근성 없이 세면 죽은 러너가 살아 있다"
    # 살아 있는 토큰 술어를 함께 건다(세션 결합이면 세션 실재까지).
    assert "t.RevokedAt IS NULL" in sql and "s.IsRevoked = 0" in sql
    assert params[-1] == store.HEARTBEAT_WINDOW_SEC


def test_heartbeating_window_boundary_both_sides(store):
    """경계 양측(G4) — 창 안이면 True, 밖이면 False. 판정은 **행의 유무**로 나온다."""
    inside = FakeCursor([(1,)])          # 창 안: 행이 있다
    outside = FakeCursor([])             # 창 밖: 행이 없다
    assert store.account_is_heartbeating(inside, 7) is True
    assert store.account_is_heartbeating(outside, 7) is False
    # 창 길이를 호출측이 좁힐 수 있어야 한다(운영 조정 여지) — 값이 SQL 로 실제 전달되는가.
    narrow = FakeCursor([(1,)])
    store.account_is_heartbeating(narrow, 7, 10)
    assert narrow.executed[0][1][-1] == 10


def test_no_account_is_never_listening(store):
    """계정이 없으면 조회조차 하지 않는다(미로그인 화면에서 '연결됨' 이 뜨지 않게)."""
    cur = FakeCursor([(1,)])
    assert store.account_is_heartbeating(cur, 0) is False
    assert cur.executed == []


def test_live_token_and_heartbeat_share_one_predicate(store):
    """두 판정이 **같은 술어 상수**를 쓴다 — 두 벌이면 언제든 갈린다(P0-R 의 교훈)."""
    src = STORE_PY.read_text(encoding="utf-8")
    assert "_LIVE_TOKEN_PREDICATE" in src
    for name in ("account_has_live_token", "account_is_heartbeating"):
        assert "_LIVE_TOKEN_PREDICATE" in _func(STORE_PY, name), (
            f"{name} 이 술어를 자체 복제한다")


def test_listening_checks_heartbeat_before_the_ledger():
    """`account_is_listening` 이 하트비트 축을 **먼저** 본다.

    원장(`wait_for_request` 최근성)만 보던 종전 판정은 러너가 **일하는 중**이면 거짓이 됐다 —
    러너는 빈 워커 자리를 잡아야 대기하러 가므로, 긴 조사(최대 1700초) 동안 대기 호출이 없다.
    """
    body = _func(AI_TOOLS_PY, "account_is_listening")
    assert "_account_is_heartbeating(" in body, "하트비트 축이 판정에 들어가 있지 않다"
    # ⚠ docstring 을 걷어내고 본다 — 설명에 도구 이름이 먼저 나온다고 해서 코드가 그 순서로
    #   도는 것은 아니다(문서를 검사하고 동작을 검사했다고 믿는 것이 이 저장소의 반복 함정).
    code = "\n".join(ln for ln in body.splitlines()
                     if not ln.strip().startswith(("#", '"""', "|", "-")))
    code = code[code.index("if not account_id"):]
    hb = code.index("_account_is_heartbeating(")
    ledger = code.index("wait_for_request")
    assert hb < ledger, "원장을 먼저 보면 일하는 중인 러너를 '대기 안 함' 으로 그린다"


def test_listening_still_falls_back_to_the_ledger():
    """하트비트를 모르는 **구 러너·등록형 MCP 클라이언트**를 끊지 않는다(무회귀)."""
    body = _func(AI_TOOLS_PY, "account_is_listening")
    assert "tool_call_usage" in body and "wait_for_request" in body


# ── ④ 엔드포인트 배선 ────────────────────────────────────────────────────────


def test_heartbeat_endpoint_exists_and_uses_the_token_auth():
    """도구 표면과 **같은 토큰 해석기**를 쓴다 — 인증 축이 갈리면 한쪽만 로그아웃을 반영한다."""
    src = AI_TOOLS_PY.read_text(encoding="utf-8")
    assert '@router.post("/api/ai/bridge_heartbeat")' in src, "하트비트 경로가 없다"
    body = _func(AI_TOOLS_PY, "bridge_heartbeat")
    assert "Depends(require_ai_token)" in body
    assert "_store.heartbeat(" in body, "엔드포인트가 저장 계층을 부르지 않는다(장식)"


def test_heartbeat_is_not_an_exposed_tool():
    """도구 목록에 넣지 않는다 — P0-I 의 '노출 = 가이드 = capabilities' 수 대조가 흔들린다.

    그리고 조사 도구 목록에 생존 신호가 끼면 AI 에게 "이걸 호출해 조사하라" 는 잘못된 신호가 된다.
    """
    src = AI_TOOLS_PY.read_text(encoding="utf-8")
    for marker in ("P0_TOOLS = frozenset({", "P1_TOOLS = frozenset({"):
        block = src[src.index(marker):src.index(marker) + 400]
        assert "bridge_heartbeat" not in block


def test_heartbeat_is_not_written_to_the_investigation_ledger():
    """30초마다 오는 신호가 원장에 쌓이면 사용자의 **조사 내역**이 그것으로 뒤덮인다(P0-N)."""
    body = _func(AI_TOOLS_PY, "bridge_heartbeat")
    assert "_ledger.record(" not in body


def test_heartbeat_failure_does_not_kill_the_connection():
    """기록 실패로 401 을 내면 **연결을 지키려는 신호가 연결을 끊는 장치**가 된다."""
    body = _func(AI_TOOLS_PY, "bridge_heartbeat")
    assert "except Exception" in body
    assert '"ok": False' in body, "실패를 성공으로 위장하거나, 반대로 러너를 죽이거나 둘 중 하나다"


# ── ⑤ 러너 — 신호는 **일하는 중에도** 나간다 ─────────────────────────────────


def test_runner_heartbeat_thread_actually_loops(runner):
    """가짜 Api 로 **실제 구동**한다 — "스레드를 만든다" 는 소스 단정으로는 루프가 도는지 모른다."""
    calls: list[float] = []
    stop = threading.Event()

    class _Api:
        # `*args/**kwargs` 로 받는다 — 실물 서명이 늘어날 때(runtimes·
        # released_instances) 더블만 낡아 스레드가 TypeError 로 죽고, 그 죽음이
        # 이 파일이 아니라 **뒤에 도는 다른 테스트**의 실패로 나타난다
        # (TASK-20260901T140000 에서 실제로 겪었다).
        def heartbeat(self, *args, **kwargs):
            calls.append(0.0)
            if len(calls) >= 3:
                stop.set()
            return {"interval_sec": 0.001}

    runner._HEARTBEAT_MIN_INTERVAL_SEC = 0.001   # 테스트 시간 압축(하한 자체는 별도 단정)
    t = runner.start_heartbeat(_Api(), stop)
    t.join(timeout=5.0)
    assert len(calls) >= 3, "하트비트가 한 번만 나가고 멈춘다 — 연결이 유지되지 않는다"
    assert t.daemon, "데몬이 아니면 러너 종료가 이 스레드에 매달린다"


def test_runner_heartbeat_survives_failures(runner):
    """서버가 배포로 잠깐 사라지는 것과 토큰 폐기는 다른 사건이다. 전자로 죽으면 배포마다 재기동."""
    seen: list[str] = []
    stop = threading.Event()

    class _Api:
        # `*args/**kwargs` 로 받는다 — 실물 서명이 늘어날 때(runtimes·
        # released_instances) 더블만 낡아 스레드가 TypeError 로 죽고, 그 죽음이
        # 이 파일이 아니라 **뒤에 도는 다른 테스트**의 실패로 나타난다
        # (TASK-20260901T140000 에서 실제로 겪었다).
        def heartbeat(self, *args, **kwargs):
            seen.append("call")
            if len(seen) == 1:
                return {"_http": 0, "_failed": True, "error": "connection refused"}
            if len(seen) == 2:
                return {"_http": 401, "error": "unauthorized"}
            stop.set()
            return {"interval_sec": 0.001}

    # 실패 응답에는 `interval_sec` 이 없다 — 그때 쓰이는 것은 **기본 주기**다. 둘 다 줄여야
    # 이 스위트가 실패 경로의 재시도를 실제로 관측한다(기본값을 안 줄이면 30초를 기다리게 된다).
    runner._HEARTBEAT_MIN_INTERVAL_SEC = 0.001
    runner._HEARTBEAT_INTERVAL_SEC = 0.001
    t = runner.start_heartbeat(_Api(), stop)
    t.join(timeout=5.0)
    assert len(seen) >= 3, "실패(연결 끊김·401) 후 스레드가 멈췄다 — 복구 경로가 없다"


def test_runner_heartbeat_interval_has_a_floor(runner):
    """서버가 0 을 주면 신호가 폭주한다 — 하한이 그것을 막는다(값은 서버가, 안전은 우리가)."""
    src = RUNNER_PY.read_text(encoding="utf-8")
    assert "_HEARTBEAT_MIN_INTERVAL_SEC" in src
    body = _func(RUNNER_PY, "start_heartbeat")
    assert "max(_HEARTBEAT_MIN_INTERVAL_SEC" in body
    assert "stop.wait(" in body, "sleep 으로 자면 종료가 최대 한 주기 늦어진다"


def test_runner_starts_heartbeat_before_waiting():
    """배선 — `main` 이 실제로 띄운다. 정의만 있고 호출이 없으면 그 함수는 없는 것과 같다."""
    body = _func(RUNNER_PY, "main")
    assert "start_heartbeat(" in body
    assert body.index("start_heartbeat(") < body.index("while True:"), (
        "대기 루프에 들어간 뒤에 띄우면 첫 대기 동안은 신호가 없다")


def test_runner_heartbeat_path_matches_the_server_route(runner):
    """러너가 부르는 경로와 서버가 여는 경로가 **같은 문자열**이어야 한다(둘이 갈리면 404)."""
    assert "/api/ai/bridge_heartbeat" in _func(RUNNER_PY, "heartbeat")
    assert '"/api/ai/bridge_heartbeat"' in AI_TOOLS_PY.read_text(encoding="utf-8")


def test_runner_security_contract_declares_the_new_egress():
    """"나가는 곳" 목록에 없는 통신을 하면 그 문서는 거짓이 된다 — 신뢰 계약의 핵심."""
    head = RUNNER_PY.read_text(encoding="utf-8")[:6000]
    assert "bridge_heartbeat" in head, "보안 계약이 하트비트 통신을 밝히지 않는다"


# ── ⑥ 로그아웃하면 러너도 **스스로** 끝난다 (사용자 요구 2026-08-28) ──────────
#
# > "웹브라우저 내 로그아웃 + 모든 요청사항이 완료되어 유휴상태가 확인된다면 더 이상
# >  사용되지 않을 브릿지 프로세스도 안전하게 종료될 수 있도록"
#
# 로그아웃 뒤의 러너는 질문을 가져올 수도, 답을 제출할 수도 없다(둘 다 401). 남겨 두면
# 사용자 머신에 **아무 일도 하지 않는 프로세스**가 계속 뜬다.


def test_shutdown_is_immediate_when_idle(runner):
    """유휴면 기다릴 것이 없다 — 곧바로 끝난다."""
    active = runner.ActiveTasks()
    cancels = runner.CancelRegistry()
    assert runner.shutdown_after_drain(active, cancels, grace_sec=30.0) is True
    assert cancels.is_canceled("anything") is False, "유휴인데 취소를 만들었다"


def test_shutdown_waits_for_inflight_then_exits(runner):
    """진행 중이면 **끝나기를 기다린다** — 곧 끝날 일을 중간에 끊지 않는다."""
    active = runner.ActiveTasks()
    cancels = runner.CancelRegistry()
    active.enter("t_busy")

    def _finish():
        active.leave("t_busy")

    threading.Timer(0.05, _finish).start()
    assert runner.shutdown_after_drain(active, cancels, grace_sec=5.0) is True, (
        "완료를 기다리지 않고 나갔다")
    assert active.count() == 0


def test_shutdown_cancels_what_outlives_the_grace(runner):
    """유예가 지나면 **중단시킨다** — 아무도 볼 수 없는 답을 위해 개인 계정 토큰이 타지 않게."""
    active = runner.ActiveTasks()
    cancels = runner.CancelRegistry()
    active.enter("t_long")
    assert runner.shutdown_after_drain(active, cancels, grace_sec=0.05) is False
    assert cancels.is_canceled("t_long"), (
        "유예를 넘긴 작업이 취소되지 않는다 — 자식 AI 프로세스가 계속 돈다")


def test_wait_idle_respects_the_deadline_across_wakeups(runner):
    """유예는 **절대 시각**이다. 깨어날 때마다 다시 주면 유예가 사실상 무한이 된다."""
    import time as _t

    active = runner.ActiveTasks()
    active.enter("t_forever")

    def _churn():
        # 다른 task 가 들락거리며 조건변수를 계속 깨운다(재계산이 없으면 영원히 기다린다).
        for i in range(20):
            active.enter(f"t_{i}")
            active.leave(f"t_{i}")
            _t.sleep(0.01)

    threading.Thread(target=_churn, daemon=True).start()
    started = _t.monotonic()
    assert active.wait_idle(0.2) is False
    assert _t.monotonic() - started < 3.0, "유예가 깨어남마다 갱신돼 늘어난다"


def test_main_drains_before_exiting_on_401():
    """배선 — `main` 의 401 분기가 종료 절차를 **실제로 부른다**(정의만 있으면 없는 것과 같다)."""
    body = _func(RUNNER_PY, "main")
    seg = body[body.index("if code == 401:"):]
    assert "shutdown_after_drain(" in seg[:900], "401 에서 진행 중 작업을 두고 나간다"
    assert "heartbeat_stop.set()" in seg[:900], (
        "죽은 토큰으로 30초마다 계속 두드린다(종료 중인데 신호가 남는다)")


def test_active_task_is_registered_before_the_thread_starts():
    """스레드 안에서 등록하면 그 창에서 종료 절차가 **유휴로 오판**한다(방금 점유한 일을 버린다)."""
    body = _func(RUNNER_PY, "main")
    assert "active.enter(task_id)" in body
    assert body.index("active.enter(task_id)") < body.index("threading.Thread(target=_work"), (
        "등록이 스레드 시작 뒤에 온다 — 경합 창이 열린다")
    assert "active.leave(tid)" in body, "완료 시 원장에서 빠지지 않으면 영원히 유휴가 아니다"


def test_shutdown_grace_is_configurable_and_bounded():
    """유예는 조정 가능해야 하고(환경마다 조사 길이가 다르다), 무한이면 '안전한 종료' 가 아니다."""
    src = RUNNER_PY.read_text(encoding="utf-8")
    assert "BRIDGE_SHUTDOWN_GRACE_SEC" in src, "운영자가 조정할 수 없다"
    body = _func(RUNNER_PY, "shutdown_after_drain")
    assert "wait_idle(" in body and "cancels.add_many(" in body


def test_served_runner_matches_canonical_after_this_change():
    """배포본이 갈리면 사용자가 받는 것과 우리가 테스트한 것이 달라진다."""
    import hashlib
    assert hashlib.sha256(SERVED_RUNNER_PY.read_bytes()).hexdigest() == \
        hashlib.sha256(RUNNER_PY.read_bytes()).hexdigest()


# ── ⑥ 웹 세션 — 활동이 있으면 밀되, 상한이 있다 ───────────────────────────────


def test_session_expiry_slides_on_activity():
    """14일 **고정**이던 것이 활동 기준으로 밀린다 — 세션이 죽으면 브리지 토큰도 함께 죽는다."""
    src = WEB_CONTEXT_PY.read_text(encoding="utf-8")
    assert "AUTH_SESSION_MAX_DAYS" in src
    body = _func(WEB_CONTEXT_PY, "_get_authenticated_account")
    assert "ExpiresAt = GREATEST(" in body, "만료를 밀지 않으면 로그인 14일째에 연결이 끊긴다"
    assert "LEAST(DATE_ADD(COALESCE(CreatedAt, UTC_TIMESTAMP())" in body, (
        "절대 상한이 없으면 세션이 영원히 살고, CreatedAt 이 비면 UPDATE 가 통째로 실패한다")


def test_session_absolute_cap_is_not_below_the_idle_window():
    """상한이 무활동 창보다 짧으면 슬라이딩이 애초에 작동하지 않는다(값을 **실제로 계산**한다)."""
    import os as _os

    src = WEB_CONTEXT_PY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    ns: dict = {"os": _os, "max": max, "int": int}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and node.targets
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in ("AUTH_SESSION_DAYS", "AUTH_SESSION_MAX_DAYS")):
            exec(compile(ast.Module([node], []), "<web_context>", "exec"), ns)  # noqa: S102
    assert "AUTH_SESSION_MAX_DAYS" in ns, "절대 상한 상수가 없다"
    assert ns["AUTH_SESSION_MAX_DAYS"] >= ns["AUTH_SESSION_DAYS"] >= 1


def test_session_touch_still_throttled():
    """폴링 트래픽이 이 UPDATE 를 매 요청 실행하면 세션 행이 뜨거워진다(feature-0028 회귀)."""
    body = _func(WEB_CONTEXT_PY, "_get_authenticated_account")
    assert "_session_touch_due(" in body


# ── ⑦ 스키마 — 컬럼이 양 경로에서 보장된다 ────────────────────────────────────


def test_heartbeat_column_is_ensured_on_both_bootstrap_paths():
    """운영 재기동은 slow path 를 타지 않는다 — 한쪽만 두면 'Unknown column' 이 배포 후에 난다."""
    src = BOOTSTRAP_PY.read_text(encoding="utf-8")
    assert "LastHeartbeatAt" in _func(BOOTSTRAP_PY, "_ensure_bridge_heartbeat_schema")
    assert "_ensure_bridge_heartbeat_schema(conn)" in _func(BOOTSTRAP_PY, "_ensure_seed_catchup")
    assert "app._ensure_bridge_heartbeat_schema(conn)" in src, "slow path 호출이 없다"


def test_heartbeat_schema_failure_does_not_abort_catchup():
    """ALTER 실패가 예외로 올라오면 무관한 seed 들이 통째로 abort 된다(webperm 사례와 동형)."""
    body = _func(BOOTSTRAP_PY, "_ensure_bridge_heartbeat_schema")
    assert "except Exception" in body and "pass" in body
