"""feature-0043 — 연결 화면 1단계의 기본 OS 탭은 **마지막으로 연결됐던 OS** 다.

## 무엇을 고쳤는가 (사용자 제보 2026-09-01)

    "명령문이 처음 선택된 os가, 실행중인 os가 아니라 마지막으로 연결되었던 os를 기준으로"
    "현재는 주로 linux(wsl) 내 명령문을 사용하고 있지만 windows가 항상 기본적으로 선택된 상태"

종전 기본값은 `navigator.platform` 이었다. 그것은 **브라우저가 도는 OS** 이고, 러너는 다른 곳에서
돈다 — WSL 안에서 러너를 띄우는 사용자는 Windows 브라우저로 화면을 보므로 판정이 **구조적으로**
틀렸다(운이 나쁜 게 아니라 매번 틀린다).

그래서 판정 근거를 추측에서 **관측**으로 옮긴다: 러너가 하트비트에 자기 명령 계열을 신고하고
(`agent_os`), 서버가 그것을 계정에 새기며(`WebAccounts.BridgeLastOs`), 화면은 그 값을 기본 탭으로
쓴다. PowerShell 명령으로 다시 등록하면 그 러너의 신고가 `windows` 라 화면도 따라 바뀐다.

## 무엇을 잠그는가

1. **정규화가 닫힌 집합** — 러너가 준 문자열이 화면의 키로 쓰이므로, 표 밖 값이 통과하면 화면은
   존재하지 않는 명령을 고르려다 빈 칸을 그린다.
2. **모르는 값이 기존 값을 지우지 않는다** — 구 러너(신고 없음)의 하트비트가 NULL 로 밀면, 구·신
   러너를 오가는 사용자는 매번 다른 기본값을 본다. 「신고 없음」은 「windows 가 아니다」가 아니다.
3. **값이 같으면 쓰지 않는다** — 하트비트는 30초마다 온다. 가드가 없으면 이 편의 기능 하나가
   계정 테이블에 상시 쓰기를 만든다.
4. **신선도 술어를 얹지 않는다** — 이 화면을 여는 순간은 대개 연결이 끊긴 뒤다. `listening` 을
   조건으로 걸면 정작 필요할 때 항상 빈 값이 된다.
5. **화면이 서버 값을 추측보다 먼저 쓴다** — 두 표시면(단독 페이지·대화 모달) 모두.
6. **사용자가 누른 탭을 늦게 온 응답이 덮지 않는다** — 손 밑에서 바뀌면 방금 고른 것과 다른
   명령을 복사하게 된다.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_WEB = _UNIT / "feature-0003-agent-web-ui" / "src"
_STORE_PATH = _WEB / "oauth_store.py"
_OAUTH_AS = _WEB / "routers" / "oauth_as.py"
_AI_TOOLS = _WEB / "routers" / "ai_tools.py"
_SCHEMA = _WEB / "routers" / "_bootstrap_schema.py"
_PAGE_JS = _WEB / "static" / "ai-connect.js"
_MODAL_JS = _WEB / "static" / "app" / "connect-modal.js"
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"


@pytest.fixture(scope="module")
def store():
    """`oauth_store` 를 앱 부팅 없이 단독 import 한다 (다른 러너 테스트와 같은 방식)."""
    if str(_WEB) not in sys.path:
        sys.path.insert(0, str(_WEB))
    spec = importlib.util.spec_from_file_location("oauth_store_os_default", _STORE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class _Cur:
    """UPDATE 를 세는 최소 커서.

    `rowcounts` 는 `execute` 순서대로 소비된다 — 두 단계(토큰 행 → 계정) 중 어디서 멈추는지를
    시험하려면 단계마다 다른 결과를 줘야 한다.
    """

    def __init__(self, *, row=None, rowcounts=(1, 1), raise_at=None):
        self.row = row
        self.raise_at = raise_at        # None | 0-based execute 순번
        self._rowcounts = list(rowcounts)
        self.executed: list[tuple[str, tuple]] = []
        self.rowcount = 1

    def execute(self, sql, params=()):
        n = len(self.executed)
        if self.raise_at is not None and n == self.raise_at:
            raise RuntimeError("Unknown column")
        self.executed.append((sql, tuple(params)))
        self.rowcount = self._rowcounts[n] if n < len(self._rowcounts) else 0

    def fetchone(self):
        return self.row


_TOKEN = "mat_live_token"


# ── 1. 정규화는 닫힌 집합 ────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("posix", "posix"),
    ("windows", "windows"),
    ("  Windows  ", "windows"),   # 러너가 준 값이므로 공백·대소문자는 접는다
    ("linux", ""),               # 표에 없는 이름 — 화면의 키가 아니다
    ("darwin", ""),
    ("nt", ""),
    ("", ""),
    (None, ""),
    (123, ""),
])
def test_normalize_bridge_os_is_a_closed_set(store, raw, expected):
    assert store.normalize_bridge_os(raw) == expected


def test_families_match_the_launch_command_keys(store):
    """정규화 표의 이름이 서버가 만드는 명령의 키와 **같아야** 한다.

    갈리면 화면은 서버가 준 적 없는 키를 조회해 빈 명령을 그린다 — 그리고 그 빈 칸은 고장으로
    읽힌다. 두 곳을 같은 어휘로 묶어 둔다.
    """
    src = _OAUTH_AS.read_text(encoding="utf-8")
    body = src[src.index("def compose_launch_commands("):]
    body = body[:body.index("\ndef ")]
    for fam in store.BRIDGE_OS_FAMILIES:
        assert f'"{fam}"' in body, f"{fam} 이 launch 명령의 키에 없다"


# ── 2·3. 쓰기 규율 — 연결 사건일 때만, 살아 있는 토큰으로만 ────────────────

def test_unknown_os_never_overwrites_a_known_one(store):
    """구 러너(신고 없음)의 하트비트가 기존 값을 지우지 않는다."""
    for unknown in ("", None, "linux", "  "):
        cur = _Cur()
        assert store.set_account_bridge_os(cur, _TOKEN, 7, unknown) is False
        assert cur.executed == [], f"{unknown!r} 로 UPDATE 가 나갔다 — 기존 값이 지워진다"


def test_token_row_is_written_first_and_gated_on_a_live_token(store):
    """1단계는 **살아 있는 토큰**의 행에만 쓴다 (codex P2-5).

    로그아웃과 경합해 최종 401 을 받는 요청이, 토큰보다 오래 사는 계정 필드를 바꾸면 안 된다.
    """
    cur = _Cur()
    assert store.set_account_bridge_os(cur, _TOKEN, 7, "posix") is True
    first_sql, first_params = cur.executed[0]
    assert "UPDATE WebOAuthTokens" in first_sql and "t.RunnerOs = %s" in first_sql
    assert store._LIVE_TOKEN_PREDICATE in first_sql, "토큰 생존 술어가 없다 — 신고만 통과하는 뒷문"
    assert "NOT (t.RunnerOs <=> %s)" in first_sql, "NULL-safe 가드가 없다 (첫 신고가 걸러진다)"
    assert first_params[0] == "posix" and first_params[1] == store.token_hash(_TOKEN)
    # 2단계 — 계정 반영
    second_sql, second_params = cur.executed[1]
    assert "UPDATE WebAccounts SET BridgeLastOs" in second_sql
    assert second_params == ("posix", 7, "posix")


def test_same_runner_repeating_itself_is_not_a_connection_event(store):
    """토큰 행이 이미 같은 계열이면 계정은 **건드리지 않는다**.

    이 한 겹이 없으면 같은 계정에 두 러너(WSL·Windows)가 붙었을 때 30초마다 값이 뒤집히고,
    「마지막으로 연결된」이 「마지막으로 도착한 하트비트」가 된다 (codex P1-2). PowerShell 로
    다시 등록해도 옆에 살아 있는 WSL 러너가 되돌린다.
    """
    cur = _Cur(rowcounts=(0, 1))     # 토큰 행 no-op
    assert store.set_account_bridge_os(cur, _TOKEN, 7, "posix") is False
    assert len(cur.executed) == 1, "계정 UPDATE 가 나갔다 — 두 러너가 서로를 덮는다"


def test_account_write_is_guarded_too(store):
    cur = _Cur(rowcounts=(1, 0))
    assert store.set_account_bridge_os(cur, _TOKEN, 7, "windows") is False
    _sql, params = cur.executed[1]
    assert params == ("windows", 7, "windows")


def test_write_failure_is_swallowed_at_either_step(store):
    """컬럼이 없는 배포에서 하트비트가 죽지 않는다 — 이건 화면 기본값 편의다."""
    assert store.set_account_bridge_os(_Cur(raise_at=0), _TOKEN, 7, "windows") is False
    assert store.set_account_bridge_os(_Cur(raise_at=1), _TOKEN, 7, "windows") is False


def test_no_token_or_no_account_no_write(store):
    for tok, acct in ((_TOKEN, 0), ("", 7)):
        cur = _Cur()
        assert store.set_account_bridge_os(cur, tok, acct, "windows") is False
        assert cur.executed == []


# ── 4. 읽기는 신선도를 묻지 않는다 ──────────────────────────────────────────

def test_read_returns_last_value_without_liveness_predicate(store):
    """「지금 듣고 있는가」가 아니라 「마지막으로 무엇이었나」를 묻는다."""
    cur = _Cur(row=("windows",))
    assert store.account_bridge_os(cur, 7) == "windows"
    sql, _params = cur.executed[0]
    assert "LastHeartbeatAt" not in sql, (
        "신선도 술어를 얹었다 — 연결이 끊긴 뒤(=이 화면을 여는 때) 항상 빈 값이 된다")


def test_read_normalizes_and_tolerates_missing_column(store):
    assert store.account_bridge_os(_Cur(row=("LINUX",)), 7) == ""   # 표 밖 값은 「모른다」
    assert store.account_bridge_os(_Cur(row=None), 7) == ""
    assert store.account_bridge_os(_Cur(raise_at=0), 7) == ""
    assert store.account_bridge_os(_Cur(row=("posix",)), 0) == ""


# ── 5. 배선 ────────────────────────────────────────────────────────────────

def test_schema_adds_the_columns_where_existing_deployments_reach_them():
    """ALTER 가 **fast path 에서도 불리는** 함수 안에 있어야 한다 (codex P1-1).

    기존 운영 DB 는 `_runtime_tables_available()` 이 참이라 `_ensure_seed_catchup()` 만 돌고
    slow path(`_ensure_web_tables`)를 타지 않는다. 거기에만 두면 컬럼이 **신규 설치에만** 생기고,
    운영에서는 읽기·쓰기가 Unknown column 을 조용히 삼켜 기능이 영구히 폴백으로 남는다
    (같은 함정에 이미 걸려 있는 선례: `BridgeDefaultModel`).
    """
    src = _SCHEMA.read_text(encoding="utf-8")
    fn = src[src.index("def _ensure_bridge_heartbeat_schema("):]
    fn = fn[:fn.index("\ndef ")]
    for ddl in ("ALTER TABLE WebOAuthTokens ADD COLUMN RunnerOs",
                "ALTER TABLE WebAccounts ADD COLUMN BridgeLastOs"):
        assert ddl in fn, f"{ddl} 이 fast-path 보정 함수 밖에 있다"
    catchup = src[src.index("def _ensure_seed_catchup("):]
    catchup = catchup[:catchup.index("\ndef ")]
    assert "_ensure_bridge_heartbeat_schema(conn)" in catchup, (
        "fast path 가 그 함수를 부르지 않는다 — 기존 배포에 컬럼이 생기지 않는다")


def test_runner_reports_its_command_family():
    src = _RUNNER.read_text(encoding="utf-8")
    fn = src[src.index("def _self_os("):]
    fn = fn[:fn.index("\n\n\n")]
    # `os.name` 이어야 한다 — 우리가 가르는 것은 배포판이 아니라 **어느 명령문이 통하는가** 이고,
    # 그 축에서 WSL 은 리눅스다. `sys.platform` 으로 바꾸면 WSL 이 여전히 linux 로 나오긴 하나
    # 판정 축이 흐려진다(cygwin·msys 가 posix 명령을 쓰면서 win 문자열을 낸다).
    assert 'os.name == "nt"' in fn and '"windows"' in fn and '"posix"' in fn
    assert 'body["agent_os"] = _self_os()' in src, "하트비트가 계열을 싣지 않는다"


def test_heartbeat_persists_the_reported_os():
    src = _AI_TOOLS.read_text(encoding="utf-8")
    assert 'agent_os = str((payload or {}).get("agent_os") or "").strip()' in src
    assert "_store.set_account_bridge_os(cur, _bearer(request), account_id, agent_os)" in src
    # 기록 실패가 연결 유지 신호를 죽이지 않는다.
    seg = src[src.index("_store.set_account_bridge_os("):]
    assert "except Exception" in seg[:400], "OS 기록 실패가 하트비트를 실패시킨다"


def test_status_and_token_responses_carry_last_os():
    src = _OAUTH_AS.read_text(encoding="utf-8")
    assert '"last_os": last_os' in src, "상태 응답에 마지막 OS 가 없다"
    assert src.count('"last_os": last_os') >= 2, (
        "발급 응답에도 실어야 한다 — 명령을 그리는 바로 그 응답이 어느 탭을 보일지도 답한다")
    assert "_store.account_bridge_os(" in src


# ── 6. 화면 — 아는 사실이 추측을 이긴다 ─────────────────────────────────────

def test_page_prefers_server_value_over_browser_guess():
    src = _PAGE_JS.read_text(encoding="utf-8")
    assert "function adoptLastOs(" in src
    assert "adoptLastOs(info && info.last_os, 1)" in src, "상태 조회 값을 반영하지 않는다"
    assert "adoptLastOs(r.body && r.body.last_os, 2)" in src, "발급 응답 값을 반영하지 않는다"
    # 추측은 남되 **폴백**이어야 한다.
    assert "navigator.platform" in src


def test_page_pins_the_tab_once_the_user_picks():
    src = _PAGE_JS.read_text(encoding="utf-8")
    assert src.count("osTabPinned = true") == 2, "탭 두 개 중 한쪽이 선택을 고정하지 않는다"
    fn = src[src.index("function adoptLastOs("):]
    fn = fn[:fn.index("\n  }")]
    assert "if (osTabPinned) { return; }" in fn, "늦게 온 서버 값이 사용자의 선택을 덮는다"


def test_modal_prefers_server_value_over_browser_guess():
    src = _MODAL_JS.read_text(encoding="utf-8")
    assert "_osTab = _lastOs || (/win/i.test(" in src, (
        "모달이 여전히 브라우저 OS 를 먼저 쓴다")
    assert "_adoptLastOs(b.last_os)" in src, "상태 조회 값을 받지 않는다"
    assert "_adoptLastOs(body.last_os)" in src, "발급 응답 값을 받지 않는다"


def test_modal_pins_the_tab_once_the_user_picks():
    src = _MODAL_JS.read_text(encoding="utf-8")
    assert src.count("_osTabPinned = true") == 2
    assert "_osTabPinned = false" in src, "창을 다시 열 때 고정이 풀리지 않는다"
    fn = src[src.index("function _adoptLastOs("):]
    fn = fn[:fn.index("\n}")]
    assert "!_osTabPinned" in fn, "늦게 온 서버 값이 사용자의 선택을 덮는다"
    assert 'v !== "posix" && v !== "windows"' in fn, (
        "「모른다」를 posix 로 굳힌다 — 한 번도 연결한 적 없는 Windows 사용자가 틀린 명령을 본다")


def test_modal_discards_a_late_token_response_from_another_window():
    """발급 응답에도 **창 세대 검사**가 있어야 한다 (codex P1-3).

    A 창에서 발급 중 닫고 B 창을 다시 열면, A 의 응답이 B 의 토큰·명령을 덮어쓴다. 닫힌 채로
    도착하면 close 가 지운 bearer 명령이 숨은 DOM 에 되살아난다 — "닫으면 다시 볼 수 없습니다"
    가 거짓이 되는 경로다. 상태 조회는 이미 같은 검사를 하고 있었고 발급만 빠져 있었다.
    """
    src = _MODAL_JS.read_text(encoding="utf-8")
    fn = src[src.index("async function _make("):]
    fn = fn[:fn.index("\n}")]
    assert "const epochAtStart = _modalEpoch;" in fn, "발급 출발 시점의 창 세대를 잡지 않는다"
    assert fn.count("epochAtStart !== _modalEpoch") >= 2, (
        "성공·실패 두 경로 모두에서 낡은 응답을 버려야 한다")
    # 세대 검사가 **토큰·명령을 그리기 전**에 와야 한다 — 뒤에 두면 이미 덮은 뒤다.
    assert fn.index("epochAtStart !== _modalEpoch") < fn.index("_launch = (body.launch")


def test_page_orders_status_and_token_responses():
    """늦게 온 **상태 조회**가 이미 그려진 발급 응답의 탭을 덮지 않는다 (codex P2-4)."""
    src = _PAGE_JS.read_text(encoding="utf-8")
    fn = src[src.index("function adoptLastOs("):]
    fn = fn[:fn.index("\n  }")]
    assert "if (r < osRank) { return; }" in fn, "근거 등급 비교가 없다 — 도착 순서가 결과를 정한다"
    assert "adoptLastOs(info && info.last_os, 1)" in src   # 상태 조회
    assert "adoptLastOs(r.body && r.body.last_os, 2)" in src   # 발급 응답이 더 높다
