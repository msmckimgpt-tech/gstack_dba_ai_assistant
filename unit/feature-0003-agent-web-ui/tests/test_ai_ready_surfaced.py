"""화면의 「준비됨」은 **「답할 수 있음」**으로만 성립한다 (TASK-20260903T180000).

## 이 파일이 고정하는 라이브 결함 (사용자 지적 2026-09-03)

> 「claude 재인증이 필요하다면, 사실상 지금 claude 가 정상적으로 작동하지 않는 상태라는것
>  아닌가요? 그렇다면 DQA 에서는 정상 상태가 아니라 미연결 상태로 나타나야 합니다.」

라이브 상태: 러너는 30초마다 멀쩡히 하트비트를 보내고(`listening=true`), 그 머신의 `claude`
는 `oauth/token 400` 으로 응답하지 않았다. 화면은 **「내 AI 대기 중」** 을 계속 띄웠고
사용자는 답이 오지 않는 곳에 질문을 보냈다.

## 이 세션의 결함 네 건이 모두 같은 부류였다

| 회차 | 화면이 말한 것 | 실제 |
|---|---|---|
| ① | 답변 말풍선에 `[WinError 206]` | 답변이 아님 |
| ② | 「연결됨」 | 240초간 아무것도 못 함 |
| ③ | (대기) | 150초 뒤에야 사유 |
| ④ | **「내 AI 대기 중」** | 답할 수 없음 |

근본은 화면의 「준비됨」이 **「답할 수 있음」이 아니라 「하트비트가 살아있음」에서 파생**된다는
것이다. 그 대리 지표를 준비됨으로 렌더하는 구조가 거짓을 반복 생산했다.

## 잠그는 것

1. 러너 신고(`ai_ready`)가 **토큰 행에 저장**되고 **`connect_status` 로 노출**된다.
2. **tri-state 보존** — `None`(구 러너·컬럼 부재)을 `false` 로 접지 않는다. 접으면 구 러너
   사용자 전원이 미연결로 보인다(`RunnerBuild` 가 이미 겪은 함정).
3. 화면이 `=== false` 일 때만 미연결로 그린다.
4. 저장은 **throttle 을 타지 않는다** — 「답할 수 없다」 전이가 늦으면 그 창에서 사용자가
   또 「준비됨」을 보고 질문한다.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"


# ── 1. 스키마: fast path 에 있어야 기존 운영 DB 에 생긴다 ─────────────────────

def test_columns_are_added_on_the_fast_path():
    """`RunnerAiReady` ALTER 가 **fast path** 함수 안에 있는가.

    slow path 전용이면 기존 운영 DB 에는 컬럼이 생기지 않고, 읽기가 예외를 삼켜 **조용히
    「모른다」** 로 동작한다 — 「테스트 전통과 + 기능 영구 폴백」(`BridgeDefaultModel` 선례).
    """
    src = (_SRC / "routers" / "_bootstrap_schema.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
              and n.name == "_ensure_bridge_heartbeat_schema")
    body = ast.get_source_segment(src, fn) or ""
    for col in ("RunnerAiReady", "RunnerAiUnreadyReason"):
        assert f"ADD COLUMN {col}" in body, (
            f"{col} ALTER 가 fast path(`_ensure_bridge_heartbeat_schema`)에 없다 — "
            "기존 운영 DB 에 컬럼이 생기지 않아 기능이 영구히 폴백한다")


def test_columns_are_nullable_tri_state():
    """`NOT NULL DEFAULT 0` 이면 구 러너 사용자 전원이 즉시 미연결로 보인다."""
    src = (_SRC / "routers" / "_bootstrap_schema.py").read_text(encoding="utf-8")
    line = next(l for l in src.splitlines() if "ADD COLUMN RunnerAiReady" in l)
    assert "NULL" in line and "NOT NULL" not in line, (
        f"tri-state 가 아니다 — 「모른다」를 표현할 수 없다: {line.strip()}")


# ── 2. 저장: throttle 을 타지 않는다 ─────────────────────────────────────────

def test_ai_health_setter_is_not_throttled():
    """AI 건강은 `CapabilitiesAt` throttle 을 **공유하지 않는다**.

    공유하면 「답할 수 없다」 전이가 최대 `HEARTBEAT_MIN_WRITE_SEC` 늦게 화면에 도달하고,
    그 창에서 사용자는 또 「준비됨」을 보고 질문한다 — 이 cycle 이 없애려는 바로 그 상태다.
    """
    src = (_SRC / "oauth_store.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "set_runner_ai_health")
    body = ast.get_source_segment(src, fn) or ""
    assert "CapabilitiesAt" not in body, "AI 건강 저장이 능력 throttle 을 탄다"
    assert "HEARTBEAT_MIN_WRITE_SEC" not in body, "AI 건강 저장에 최소 간격이 걸려 있다"


def test_setter_ignores_unreported_health():
    """`ai_ready=None`(구 러너)이면 **아무것도 쓰지 않는다**."""
    import oauth_store

    calls = []

    class _Cur:
        rowcount = 1

        def execute(self, *a, **k):
            calls.append(a)

    assert oauth_store.set_runner_ai_health(_Cur(), "mat_x", None, "") is False
    assert calls == [], "신고하지 않은 러너의 상태를 새겼다 — 구 러너가 미연결로 보인다"


def test_setter_writes_when_reported():
    """신고했으면 쓴다 — 그리고 사유도 함께 나른다."""
    import oauth_store

    seen = {}

    class _Cur:
        rowcount = 1

        def execute(self, sql, params=None):
            seen["sql"] = sql
            seen["params"] = params

    assert oauth_store.set_runner_ai_health(_Cur(), "mat_x", False, "응답 없음") is True
    assert "RunnerAiReady" in seen["sql"] and "RunnerAiUnreadyReason" in seen["sql"]
    assert 0 in (seen["params"] or ()), f"false 가 0 으로 새겨지지 않았다: {seen['params']}"
    assert "응답 없음" in (seen["params"] or ()), "사유가 유실됐다"


# ── 3. 읽기·노출: tri-state 가 응답까지 보존되는가 ───────────────────────────

def test_reader_returns_none_when_unknown():
    """조회 실패·미신고는 **`None`** 이다 — `False` 로 접으면 멀쩡한 사용자를 막는다."""
    import oauth_store

    class _Boom:
        def execute(self, *a, **k):
            raise RuntimeError("컬럼 없음")

    assert oauth_store.account_ai_health(_Boom(), 7)[0] is None

    class _NoRow:
        def execute(self, *a, **k):
            pass

        def fetchone(self):
            return None

    assert oauth_store.account_ai_health(_NoRow(), 7)[0] is None

    class _NullFlag:
        def execute(self, *a, **k):
            pass

        def fetchone(self):
            return (None, None)

    assert oauth_store.account_ai_health(_NullFlag(), 7)[0] is None, (
        "러너가 신고하지 않은 상태(NULL)를 「답할 수 없다」로 읽었다")


def test_connect_status_exposes_the_axis_without_flattening():
    """응답이 `ai_ready` 를 **접지 않고** 싣는가 (`bool()` 로 눌러 담으면 tri-state 소멸)."""
    src = (_SRC / "routers" / "oauth_as.py").read_text(encoding="utf-8")
    assert '"ai_ready": ai_ready,' in src, "connect_status 가 이 축을 노출하지 않는다"
    assert '"ai_ready": bool(' not in src, (
        "`bool()` 로 눌러 담았다 — 「모른다」가 「답할 수 없다」로 바뀐다")
    assert '"ai_unready_reason": ai_unready_reason,' in src, "사유가 화면에 도달하지 않는다"


def test_ai_health_read_is_not_inside_the_stale_verdict_branch():
    """이 조회를 **낡음 판정 갈래 안에 두지 않는다**.

    그 갈래는 「판정 호출이 자기 갈래의 마지막이어야 한다」로 잠겨 있다
    (`test_staleness_predicate_has_exactly_one_home`) — 뒤에 무엇이든 오면 판정을 덮을 수 있는
    모양이 된다. 초판에서 실제로 그 자리에 넣었다가 그 테스트가 잡았고, 이 단정은 같은 실수를
    다시 하지 않게 한다.
    """
    src = (_SRC / "routers" / "oauth_as.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
              and n.name == "connect_status")
    for node in ast.walk(fn):
        if not isinstance(node, ast.Try):
            continue
        seg = ast.get_source_segment(src, node) or ""
        if "runner_build_is_stale" in seg:
            assert "account_ai_health" not in seg, (
                "AI 건강 조회가 낡음 판정 갈래 안에 있다 — 판정을 덮는 모양이 된다")


# ── 4. 화면: `=== false` 로만 미연결로 그린다 ────────────────────────────────

def test_frontend_uses_strict_false_only():
    """`undefined`/`null`(모른다)을 미연결로 그리면 구 러너 사용자 전원이 막힌다."""
    js = (_SRC / "static" / "app" / "connect-modal.js").read_text(encoding="utf-8")
    body = "\n".join(l for l in js.splitlines() if not l.strip().startswith("//"))
    assert "aiReady === false" in body, (
        "화면이 엄격 비교를 쓰지 않는다 — 「모른다」가 미연결로 그려진다")
    assert "if (!aiReady)" not in body and "!aiReady)" not in body, (
        "truthy 판정을 쓴다 — `undefined` 가 미연결이 된다")


def test_frontend_shows_the_reason_and_ranks_above_stale():
    """사유를 보여 주고, **낡음보다 먼저** 그린다(무거운 사실이 먼저)."""
    js = (_SRC / "static" / "app" / "connect-modal.js").read_text(encoding="utf-8")
    assert "aiUnreadyReason" in js, "사유가 화면에 쓰이지 않는다 — 사용자는 이유를 모른다"
    i_ai = js.index("aiReady === false")
    i_stale = js.index("} else if (runnerStale) {")
    assert i_ai < i_stale, (
        "낡음(답은 온다)이 답할 수 없음(답이 오지 않는다)보다 먼저 그려진다")


def test_the_branch_is_not_a_dead_guard():
    """분기 조건에 **아무것도 덧대지 않는다** — 죽은 가드를 막는다.

    ⚠ 위 두 단정(문자열 존재·위치)만으로는 `aiReady === false && false` 가 **통과한다**
    (뮤테이션 I7 실측 생존). 조건이 그대로 있고 자리도 그대로인데 분기는 영영 실행되지 않아
    화면은 종전처럼 「대기 중」을 띄운다 — 이 저장소가 반복해 겪은 「죽은 가드」다.

    그래서 조건절을 **정확히** 잠그고, 그 갈래가 실제로 이 상태를 그리는지(문구 대입)까지 본다.

    ⚠ 한계(정직): 이것은 여전히 **구조 단정**이다. 더 강한 형태는 node 하네스로 `_paintConn`
    을 실제 호출해 `textContent` 를 보는 것이며, 그쪽이 리팩터에도 견딘다. 지금은 그 부재를
    이 주석으로 남긴다 — 조건 표현이 바뀌면 이 단정이 깨지고, 그때 행위 단정으로 올린다.
    """
    js = (_SRC / "static" / "app" / "connect-modal.js").read_text(encoding="utf-8")
    lines = [l.strip() for l in js.splitlines()]
    assert "} else if (aiReady === false) {" in lines, (
        "분기 조건이 정확히 `aiReady === false` 가 아니다 — 덧댄 항이 분기를 죽일 수 있다")
    i = lines.index("} else if (aiReady === false) {")
    body = "\n".join(lines[i:i + 24])
    assert '"답할 수 없음"' in body, "그 갈래가 이 상태를 그리지 않는다 — 조건만 남은 가드다"
    assert "aiUnreadyReason" in body, "그 갈래가 사유를 쓰지 않는다"


def test_modal_success_does_not_accept_an_unusable_runner():
    """연결 모달이 「답할 수 없는 러너」를 **완료로 읽지 않는다**.

    읽으면 사용자는 「연결됐다」는 확인을 받고 질문을 보낸다 — 이 cycle 의 요지 그대로다.
    """
    js = (_SRC / "static" / "app" / "connect-modal.js").read_text(encoding="utf-8")
    body = "\n".join(l for l in js.splitlines() if not l.strip().startswith("//"))
    assert "b.ai_ready !== false" in body, (
        "모달 성공 판정이 이 축을 보지 않는다 — 답할 수 없는 러너를 연결 완료로 읽는다")
