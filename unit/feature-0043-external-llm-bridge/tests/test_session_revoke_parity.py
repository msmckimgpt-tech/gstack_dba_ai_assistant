"""로그아웃하면 AI 연결도 죽는가 — **인증과 표시가 같은 답을 하는가** (사용자 제보 2026-08-27).

## 무슨 일이 있었나

    로그아웃 → 세션 revoke → 인증은 401 로 막힘 → **그런데 화면은 "연결됨"**

라이브 데이터로 확인한 갈림:

    구 술어(토큰 행만 본다)      → 연결 1건
    신 술어(묶인 세션까지 본다)  → 연결 0건

원인 둘이 겹쳤다.

1. `revoke_for_session` 은 "웹 로그아웃 시 그 세션에서 파생된 토큰을 함께 죽인다" 는 목적으로
   **이미 있었는데 아무도 부르지 않았다**(테스트만 호출). 정의와 호출이 갈리면 그 함수는
   없는 것과 같다.
2. 화면의 연결 판정이 인증 판정과 **다른 술어**였다. 같은 질문에 두 개의 답이 있으면 언제든
   갈리고, 갈리는 순간 **느슨한 쪽이 사용자가 보는 진실**이 된다.
"""
from __future__ import annotations

import ast
import pathlib

_UNIT = pathlib.Path(__file__).resolve().parents[2]
WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
STORE = WEB_SRC / "oauth_store.py"
AUTH = WEB_SRC / "routers" / "auth.py"
CONVS = WEB_SRC / "routers" / "conversations.py"
AI_TOOLS = WEB_SRC / "routers" / "ai_tools.py"


def _func(path: pathlib.Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"{path.name}: {name} 없음")


# ── ① 로그아웃이 토큰까지 죽인다 ──────────────────────────────────────────────


def test_logout_propagates_revocation_to_tokens():
    """세션만 죽이면 토큰 행은 살아 있는 것처럼 남아 화면이 오판한다."""
    body = _func(AUTH, "auth_logout")
    assert "revoke_for_session(" in body, (
        "로그아웃이 파생 토큰을 죽이지 않는다 — 화면이 죽은 연결을 '연결됨' 으로 센다")
    assert "IsRevoked = 1" in body, "세션 revoke 자체가 사라졌다"


def test_logout_commits():
    """커밋하지 않으면 revoke 가 롤백돼 아무 일도 일어나지 않는다."""
    body = _func(AUTH, "auth_logout")
    assert "conn.commit()" in body


def test_revoke_helper_is_actually_called_somewhere():
    """정의만 있고 호출이 없으면 그 함수는 **없는 것과 같다**.

    이 테스트가 잡으려는 것은 구현이 아니라 **배선**이다 — 실제로 그 형태로 방치돼 있었다.
    """
    callers = []
    for path in (_UNIT).rglob("*.py"):
        if "/tests/" in str(path) or path.name == "oauth_store.py":
            continue
        try:
            src = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if "revoke_for_session(" in src:
            callers.append(path.name)
    assert callers, "revoke_for_session 을 부르는 제품 코드가 없다(테스트만 호출)"


# ── ② 인증과 표시가 같은 술어 ─────────────────────────────────────────────────


def test_single_source_for_connection_state():
    """연결 판정이 **한 함수**로 모인다."""
    assert "def account_has_live_token(" in STORE.read_text(encoding="utf-8")


def test_connection_probe_checks_the_bound_session():
    """토큰 행만 보면 로그아웃 뒤에도 '연결됨' 이 된다 — 세션까지 봐야 한다."""
    body = _func(STORE, "account_has_live_token")
    assert "WebAuthSessions" in body, "묶인 세션을 보지 않는다"
    assert "IsRevoked = 0" in body, "세션 폐기 여부를 보지 않는다"
    assert "s.ExpiresAt IS NULL OR s.ExpiresAt > NOW()" in body, "세션 만료를 보지 않는다"


def test_session_null_tokens_are_not_excluded():
    """세션 무관 토큰(발급 축이 다름)까지 배제하면 멀쩡한 연결이 끊긴 것으로 보인다."""
    body = _func(STORE, "account_has_live_token")
    assert "t.SessionId IS NULL OR" in body


def test_all_consumers_use_the_shared_predicate():
    """소비처가 각자 세면 또 갈린다 — 실제로 그렇게 갈렸다."""
    for path, fn in ((CONVS, "_account_has_connected_ai"), (AI_TOOLS, "bridge_status")):
        body = _func(path, fn)
        assert "account_has_live_token(" in body, f"{path.name}:{fn} 이 따로 센다"
        assert "FROM WebOAuthTokens" not in body, f"{path.name}:{fn} 에 자체 술어가 남아 있다"


def test_predicate_matches_the_auth_path():
    """표시 술어가 인증 술어(`resolve_access_token`)와 **같은 조건**을 본다."""
    probe = _func(STORE, "account_has_live_token")
    resolve = _func(STORE, "resolve_access_token")
    for cond in ("IsRevoked", "ExpiresAt", "RevokedAt"):
        assert cond in probe and cond in resolve, f"{cond} 조건이 한쪽에만 있다"


# ── 연결 없으면 대기열에 올리지 않는다 (사용자 결정 2026-08-27) ───────────────
#
# 종전엔 연결 여부와 무관하게 큐에 넣어, 아무도 가져갈 수 없는 질문이 쌓였다(실측 5건 누적).
# 나중에 연결하면 **밀린 것이 한꺼번에** 처리된다 — 사용자가 원하는 것은 '지금 묻는 것' 이다.


def test_no_enqueue_when_disconnected():
    body = _func(CONVS, "_enqueue_web_bridge_task")
    assert "if not connected:" in body, "연결 여부와 무관하게 적재한다"
    head = body[:body.index("if not connected:")]
    assert "INSERT INTO WebAiTasks" not in head, "적재가 판정보다 먼저 일어난다"


def test_disconnected_path_still_keeps_the_conversation():
    """질문은 사라지지 않는다 — 다음 요청 때 **이전 문맥으로 함께** 간다."""
    body = _func(CONVS, "_enqueue_web_bridge_task")
    seg = body[body.index("if not connected:"):body.index("# ① 대기 작업 적재")]
    assert '"user", question' in seg, "사용자 질문을 대화에 남기지 않는다"
    assert "_bridge_save_core_message(" in seg, "회수 store 에 남기지 않아 다음 문맥에서 빠진다"
    assert '"assistant", notice_text' in seg, "안내 말풍선이 없어 화면이 무반응으로 보인다"


def test_disconnected_path_does_not_ask_for_polling():
    """없는 task 를 폴링하면 404 만 쌓인다."""
    body = _func(CONVS, "_enqueue_web_bridge_task")
    seg = body[body.index("if not connected:"):body.index("# ① 대기 작업 적재")]
    assert '"bridge_pending": False' in seg
    assert '"bridge_queued": False' in seg


def test_notice_tells_user_to_ask_again():
    """'저장해 두었습니다' 는 이제 거짓이다 — 큐에 없으므로 **다시 물어야** 한다."""
    src = CONVS.read_text(encoding="utf-8")
    body = src[src.index("_BRIDGE_NOTICE_NOT_CONNECTED = ("):src.index("#: 이미 연결한 계정")]
    assert "다시 질문해" in body, "재요청이 필요하다는 사실을 말하지 않는다"
    assert "대기열에 저장" not in body, "큐에 넣지 않는데 넣었다고 말한다"


def test_frontend_handles_the_not_queued_branch():
    js = (WEB_SRC / "static" / "app" / "composer.js").read_text(encoding="utf-8")
    assert "bridge_queued === false" in js, "미적재 응답을 '응답을 갱신했습니다' 로 오인한다"
    assert "if (!queued) return true;" in js, "없는 task 를 폴링한다"


# ── 연결 상태 상시 표시 (사용자 제보 2026-08-27) ─────────────────────────────
#
# "웹브라우저 내 화면에서는 연결여부에 대한 메세지가 없어 연결이 1차적으로 완수되었는지
# 확인되지 않습니다." — 종전엔 **질문을 보내야만** 안내 말풍선으로 간접 확인됐다.
# 순서가 거꾸로다: 연결 여부는 **묻기 전에** 알아야 한다.

MODAL_JS = WEB_SRC / "static" / "app" / "connect-modal.js"
INDEX = WEB_SRC / "static" / "index.html"
APP_JS = WEB_SRC / "static" / "app.js"
OAUTH = WEB_SRC / "routers" / "oauth_as.py"


def test_status_endpoint_reports_connection():
    body = _func(OAUTH, "connect_status")
    assert '"connected"' in body, "연결 여부를 알려주지 않는다"


def test_status_uses_the_shared_predicate():
    """표시와 인증이 또 갈리지 않게 — 같은 함수를 쓴다."""
    body = _func(OAUTH, "connect_status")
    assert "account_has_live_token(" in body, "따로 세면 로그아웃 뒤에도 '연결됨' 이 된다"


def test_status_probe_fails_open():
    body = _func(OAUTH, "connect_status")
    tail = body[body.index("except Exception"):]
    assert "connected = True" in tail, "조회 실패 시 '연결 없음' 으로 단정하면 거짓 경보"


def test_indicator_exists_and_is_wired():
    assert 'id="aiConnState"' in INDEX.read_text(encoding="utf-8"), "표시 요소가 없다"
    app = APP_JS.read_text(encoding="utf-8")
    assert "bindConnState()" in app, "표시가 배선되지 않았다(요소만 있고 안 그린다)"


def test_indicator_shows_both_states():
    """(2026-08-27 3상태로 확장 — `test_indicator_has_three_states` 가 본체다.)"""
    js = MODAL_JS.read_text(encoding="utf-8")
    assert "내 AI 대기 중" in js and "내 AI 연결 안 됨" in js, "한쪽 상태만 표시한다"


def test_indicator_opens_the_modal():
    """표시가 곧 조치 경로여야 한다 — '연결 안 됨' 만 보이고 방법이 없으면 소용없다."""
    js = MODAL_JS.read_text(encoding="utf-8")
    seg = js[js.index("export function bindConnState("):]
    assert "openConnectModal()" in seg


def test_indicator_refreshes_after_connecting():
    """방금 연결했는데 표시가 낡아 있으면 사용자는 실패한 줄 안다."""
    js = MODAL_JS.read_text(encoding="utf-8")
    make = js[js.index("async function _make("):js.index("async function _copy(")]
    assert "refreshConnState()" in make


def test_indicator_refreshes_on_tab_return():
    """다른 탭에서 연결하고 돌아오는 경로 — 낡은 표시를 남기지 않는다."""
    js = MODAL_JS.read_text(encoding="utf-8")
    assert "visibilitychange" in js


def test_indicator_does_not_poll():
    """연결은 자주 바뀌지 않는다. 주기 폴링은 이 기능 전체의 원칙과도 어긋난다."""
    js = MODAL_JS.read_text(encoding="utf-8")
    code = "\n".join(l for l in js.split("\n")
                     if l.strip() and not l.strip().startswith("//"))
    assert "setInterval" not in code, "연결 상태를 주기 폴링한다"


def test_indicator_hides_rather_than_lying():
    """조회 실패·미로그인은 **표시하지 않는다** — 틀린 상태를 보이느니 침묵이 낫다."""
    js = MODAL_JS.read_text(encoding="utf-8")
    body = js[js.index("export async function refreshConnState("):js.index("export function bindConnState(")]
    assert 'classList.add("hidden")' in body


# ══════════════════════════════════════════════════════════════════════════════
# 상주 러너를 기본 경로로 · 재시작 대응 (사용자 결정 2026-08-27)
#
# 실측: AI 가 wait_for_request 를 10분간 반복하다(1회=도구 호출 1회) 질문을 **받은 직후**
# 루프가 끝났다. claim 하지 않아 task 는 방치됐다. 대화형 세션은 턴 예산이 있고, 대기가 그것을
# 태운다. 러너는 예산이 없는 일반 프로세스라 그 일이 없다.
# ══════════════════════════════════════════════════════════════════════════════

AI_TOOLS_P = WEB_SRC / "routers" / "ai_tools.py"
RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"


def test_listening_is_measured_not_assumed():
    """'토큰 있음' 과 '지금 듣고 있음' 은 다른 사실이다 — 재부팅하면 러너만 사라진다."""
    body = _func(AI_TOOLS_P, "account_is_listening")
    assert "wait_for_request" in body, "대기 호출 이력을 보지 않는다(추측이 된다)"
    assert "tool_call_usage" in body, "관측이 아니라 다른 데서 만들어낸다"


def test_listening_fails_closed():
    """조회 실패를 '대기 중' 으로 넘기면 헛되이 기다리게 된다 — 연결 판정과 방향이 반대다."""
    body = _func(AI_TOOLS_P, "account_is_listening")
    tail = body[body.index("except Exception"):]
    assert "return False" in tail


def test_status_exposes_listening_separately():
    for path, fn in ((WEB_SRC / "routers" / "oauth_as.py", "connect_status"),
                     (AI_TOOLS_P, "bridge_status")):
        body = _func(path, fn)
        assert "listening" in body, f"{path.name}:{fn} 이 대기 여부를 알리지 않는다"


def test_phase_distinguishes_connected_but_idle():
    """'연결됐지만 아무도 안 듣는' 국면이 존재하고, **모든 소비처가 같은 판정**을 쓴다.

    2026-08-28 병합: 국면 판정이 `bridge_status` 본문에서 `_bridge_phase` 로 올라갔다.
    소비처가 폴링(`bridge_status`)과 스트리밍(`_bridge_stream_snapshot`) 둘이 되었기 때문이다 —
    각자 조합하면 전송 방식에 따라 화면이 달라져 SSE→폴링 폴백이 곧 UX 회귀가 된다.
    그래서 여기서는 **판정의 존재**와 **두 소비처의 위임**을 함께 단정한다.
    """
    decide = _func(AI_TOOLS_P, "_bridge_phase")
    assert "not_listening" in decide, "'연결됐지만 아무도 안 듣는' 국면이 없다"
    assert "not_connected" in decide, "연결 자체가 없는 국면과 구분되지 않는다"
    for consumer in ("bridge_status", "_bridge_stream_snapshot"):
        body = _func(AI_TOOLS_P, consumer)
        assert "_bridge_phase(" in body, f"{consumer} 이 국면을 자체 조합한다"
        assert "listening" in body, f"{consumer} 이 대기 여부를 판정에 넘기지 않는다"


def test_indicator_has_three_states():
    js = MODAL_JS.read_text(encoding="utf-8")
    for label in ("내 AI 연결 안 됨", "AI 대기 안 함", "내 AI 대기 중"):
        assert label in js, f"표시 상태 '{label}' 이 없다"
    assert "머신을 재시작했다면" in js, "왜 대기가 끊겼는지 힌트가 없다"


# ── 러너 재시작 대응 ─────────────────────────────────────────────────────────


def test_runner_saves_config_for_restart():
    """다시 챙길 것이 많을수록 **아무도 다시 띄우지 않는다**."""
    src = RUNNER.read_text(encoding="utf-8")
    assert "--resume" in src
    assert "def save_conf(" in src and "def load_conf(" in src


def test_runner_never_persists_the_token():
    """토큰은 비밀이고 어차피 세션과 함께 죽는다 — 파일에 남길 이유가 없다."""
    body = _func(RUNNER, "save_conf")
    assert '"token"' not in body and "token=" not in body, "설정 파일에 토큰을 저장한다"
    assert "0o600" in body, "설정 파일 권한을 좁히지 않는다"


def test_runner_tells_how_to_come_back_on_401():
    """조용히 죽으면 사용자에겐 '왜 답이 안 오지' 만 남는다."""
    src = RUNNER.read_text(encoding="utf-8")
    seg = src[src.index('if code == 401:'):]
    assert "--resume" in seg[:800], "다시 띄우는 정확한 명령을 주지 않는다"


def test_handoff_makes_the_runner_the_first_step():
    """지시문이 러너를 **필수 1단계**로 둔다(선택 부록이 아니라)."""
    body = _func(WEB_SRC / "routers" / "oauth_as.py", "compose_connect_handoff")
    assert "상주 러너 (필수)" in body
    assert body.index("상주 러너") < body.index("wait_for_request 를 직접"), (
        "직접 대기가 러너보다 앞에 온다 — 사용자는 앞의 것을 고른다")
    assert "턴 예산" in body, "왜 러너여야 하는지 근거가 없다(다음 사람이 되돌린다)"
    assert "--resume" in body, "재시작 복귀 경로가 지시문에 없다"


def test_handoff_warns_about_receiving_without_claiming():
    """받아 놓고 멈추면 그 질문은 방치된다 — 실제로 그렇게 됐다."""
    body = _func(WEB_SRC / "routers" / "oauth_as.py", "compose_connect_handoff")
    assert "받아 놓고 멈추면" in body
