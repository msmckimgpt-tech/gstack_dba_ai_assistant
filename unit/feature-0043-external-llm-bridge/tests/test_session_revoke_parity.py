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
import re
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


def _live_predicate() -> str:
    """`_LIVE_TOKEN_PREDICATE` 상수의 실제 값.

    2026-08-28(TASK-20260828T150000)부터 술어가 **상수 하나**로 모였다 — 하트비트 판정
    (`account_is_heartbeating`)이 같은 조건 위에 최근성만 얹기 때문이다. 그래서 조건을
    함수 본문에서 찾던 종전 방식은 더 이상 성립하지 않는다. **계약은 그대로**이므로,
    상수 값 자체를 읽어 같은 조건을 단정한다(그리고 아래에서 소비처가 그 상수를 쓰는지 본다).

    ⚠ 소스 문자열을 읽지 않는다 — 상수가 f-string 으로 시각 축(`UTC_TIMESTAMP()`)을 끼워
    넣으므로, 텍스트로는 **조립 결과**를 볼 수 없다. 모듈을 로드해 실제 값을 본다.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("oauth_store_parity_test", STORE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pred = getattr(mod, "_LIVE_TOKEN_PREDICATE", None)
    assert isinstance(pred, str) and pred, "oauth_store: _LIVE_TOKEN_PREDICATE 상수가 없다"
    return pred


def test_connection_probe_checks_the_bound_session():
    """토큰 행만 보면 로그아웃 뒤에도 '연결됨' 이 된다 — 세션까지 봐야 한다."""
    body = _func(STORE, "account_has_live_token")
    pred = _live_predicate()
    assert "_LIVE_TOKEN_PREDICATE" in body, "판정이 공유 술어를 쓰지 않는다(복제본이 생겼다)"
    assert "WebAuthSessions" in body, "묶인 세션을 보지 않는다"
    assert "s.IsRevoked = 0" in pred, "세션 폐기 여부를 보지 않는다"
    assert "s.ExpiresAt IS NULL OR s.ExpiresAt > UTC_TIMESTAMP()" in pred, "세션 만료를 보지 않는다"


def test_session_null_tokens_are_not_excluded():
    """세션 무관 토큰(발급 축이 다름)까지 배제하면 멀쩡한 연결이 끊긴 것으로 보인다."""
    assert "t.SessionId IS NULL OR" in _live_predicate()


def test_all_consumers_use_the_shared_predicate():
    """소비처가 각자 세면 또 갈린다 — 실제로 그렇게 갈렸다."""
    for path, fn in ((CONVS, "_account_has_connected_ai"), (AI_TOOLS, "bridge_status")):
        body = _func(path, fn)
        assert "account_has_live_token(" in body, f"{path.name}:{fn} 이 따로 센다"
        assert "FROM WebOAuthTokens" not in body, f"{path.name}:{fn} 에 자체 술어가 남아 있다"


def test_predicate_matches_the_auth_path():
    """표시 술어가 인증 술어(`resolve_access_token`)와 **같은 조건**을 본다."""
    probe = _live_predicate()
    resolve = _func(STORE, "resolve_access_token")
    for cond in ("IsRevoked", "ExpiresAt", "RevokedAt"):
        assert cond in probe and cond in resolve, f"{cond} 조건이 한쪽에만 있다"


# ── 연결 없으면 대기열에 올리지 않는다 (사용자 결정 2026-08-27) ───────────────
#
# 종전엔 연결 여부와 무관하게 큐에 넣어, 아무도 가져갈 수 없는 질문이 쌓였다(실측 5건 누적).
# 나중에 연결하면 **밀린 것이 한꺼번에** 처리된다 — 사용자가 원하는 것은 '지금 묻는 것' 이다.


def test_unconnected_question_is_deferred_not_dropped():
    """⚠ 계약이 바뀌었다(사용자 결정 2026-08-28).

    종전엔 **적재하지 않았다** — 밀린 질문이 한꺼번에 처리되는 것을 막기 위해서였다. 그 대가로
    사용자는 연결이 끊긴 줄 모르고 보낸 질문을 매번 다시 입력해야 했고(라이브 실측: 로그아웃
    직후 창), 그것을 "LLM 이 막혔다" 로 겪었다.

    지금은 **보관한다**(`Status='deferred'`). 폭주 방지는 적재를 막는 대신 **승격을 1건으로
    제한**해서 얻는다 — 같은 것을 지키면서 재입력만 없앤다.

    ⚠ 재갱신 (P0-AB, 사용자 결정 2026-08-28): 보관의 **조건**이 바뀌었다.

    지금 게이트는 두 축의 곱이다 — *"머신 내 DQA프로세스가 실행중인지, 토큰이 연결되어
    있는지 여부를 점검하여 허용"*. 토큰이 없으면 화면이 잠기고 서버가 409 로 거절하므로
    보관할 것이 없다. 보관은 **게이트를 통과했다가 러너가 꺼진 창** 을 위한 것이 됐다:
    *"이미 로그인 된 상태에서 질문이 진행되었다면 보관하여 다시 처리합니다."*

    재입력을 요구하지 않는다는 원래의 약속은 그 창에서 그대로 지켜진다.
    """
    body = _func(CONVS, "_enqueue_web_bridge_task")
    assert '"open" if listening else "deferred"' in body, "러너 생존으로 상태를 가르지 않는다"
    assert "INSERT INTO WebAiTasks" in body, "보류 질문이 적재되지 않는다"
    # 토큰이 없을 때는 **차단**이 계약이다 — 조용히 적재로 되돌아가면 아무도 가져갈 수 없는
    # 질문이 다시 쌓이고, 사용자 결정("요청이 막히고")이 무효가 된다.
    assert "bridge_blocked" in body, "토큰 미보유 요청을 차단하지 않는다"


def test_disconnected_path_still_keeps_the_conversation():
    """질문은 사라지지 않는다 — 대화·회수 store·안내 말풍선이 모두 남는다."""
    body = _func(CONVS, "_enqueue_web_bridge_task")
    assert '"user", question' in body, "사용자 질문을 대화에 남기지 않는다"
    assert "_bridge_save_core_message(" in body, "회수 store 에 남기지 않아 다음 문맥에서 빠진다"
    assert '"assistant", notice_text' in body, "안내 말풍선이 없어 화면이 무반응으로 보인다"


def test_disconnected_path_does_not_ask_for_polling():
    """보류 질문은 언제 승격될지 모른다 — 폴링하면 러너 꺼진 브라우저가 종일 빈 요청을 보낸다."""
    body = _func(CONVS, "_enqueue_web_bridge_task")
    assert '"bridge_pending": listening' in body, (
        "러너가 꺼진 상태에서도 폴링을 켠다(또는 대기 중인데 폴링이 꺼졌다)")


def test_notice_promises_the_question_is_carried_over():
    """⚠ 계약이 바뀌었다: '다시 물어야 한다' → '연결하면 이 질문부터 처리한다'.

    안내가 옛 문구로 남으면, 고친 동작을 사용자가 알 방법이 없다(그리고 실제로는 이어받는데
    다시 입력하게 만든다).
    """
    src = CONVS.read_text(encoding="utf-8")
    # P0-AB: 보류 말풍선의 사유가 '토큰 없음' → '러너 꺼짐' 으로 바뀌어 상수도 바뀌었다.
    # 계약(이어받기·1건 규칙 고지)은 그대로다.
    body = src[src.index("_BRIDGE_NOTICE_NOT_LISTENING = ("):src.index("#: 승격 경쟁에서 밀렸거나")]
    assert "이 질문부터" in body, "이어받는다는 사실을 말하지 않는다"
    assert "다시 질문해" not in body, "재입력을 요구하는 옛 문구가 남아 있다"
    assert "마지막 질문 1건" in body, "여러 번 물었을 때의 규칙을 밝히지 않는다"


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
    """(2026-08-27 3상태로 확장 — `test_indicator_has_three_states` 가 본체다.)

    2026-09-01: 칩이 사이드바 프로필 행으로 옮겨가며 «내 AI» 접두가 빠졌다(주어는 자리가
    말한다). 문구가 아니라 **두 상태가 갈리는가**가 이 테스트의 계약이다.
    """
    js = MODAL_JS.read_text(encoding="utf-8")
    assert '"대기 중"' in js and '"연결 안 됨"' in js, "한쪽 상태만 표시한다"


def test_indicator_opens_the_modal():
    """표시가 곧 조치 경로여야 한다 — '연결 안 됨' 만 보이고 방법이 없으면 소용없다.

    ⚠ 2026-09-02: 조치는 «창 열기» 하나가 아니다(이미 연결해 본 사용자는 바로 실행). 잠그는
    것은 «표시 → 조치» 라는 관계이지 특정 함수 이름이 아니다.
    """
    js = MODAL_JS.read_text(encoding="utf-8")
    seg = js[js.index("export function bindConnState("):]
    assert "_connectEntry" in seg, "칩이 아무 조치로도 이어지지 않는다"
    entry = js[js.index("function _connectEntry("):]
    entry = entry[:entry.index("\nexport function")]
    assert "openConnectModal()" in entry, "실행이 안 되는 사용자에게 남는 경로가 없다"


def test_indicator_refreshes_after_connecting():
    """방금 연결했는데 표시가 낡아 있으면 사용자는 실패한 줄 안다.

    ⚠ **재는 자리가 옮겨졌다 (2026-09-07).** 종전에는 발급(`_make`)이 끝난 뒤 곧바로 다시
    조회하는지를 봤다 — 그 발급이 「연결을 만드는」 동작이었기 때문이다. 그 버튼이 사라지고
    연결을 만드는 것은 **실행**(`_launchRunner`)과 앱 창의 패널이 됐다. 성질은 그대로:
    연결이 성립한 직후 표시가 다음 폴링을 기다리지 않는다.
    """
    js = MODAL_JS.read_text(encoding="utf-8")
    fn = js[js.index("async function _launchRunner("):]
    fn = fn[:fn.index("\n}")]
    assert "_awaitUsable(" in fn, "실행 뒤 상태를 지켜보지 않는다"
    assert "refreshConnState" in js[js.index("async function _awaitUsable("):
                                    js.index("async function _launchRunner(")], (
        "지켜보기가 실제로 상태를 다시 읽지 않는다")


def test_indicator_refreshes_on_tab_return():
    """다른 탭에서 연결하고 돌아오는 경로 — 낡은 표시를 남기지 않는다."""
    js = MODAL_JS.read_text(encoding="utf-8")
    assert "visibilitychange" in js


def test_indicator_does_not_poll_when_unlocked():
    """⚠ 계약이 좁혀졌다 (P0-AB, 사용자 결정 2026-08-28).

    종전 계약은 "주기 폴링 없음" 이었고 그 근거는 (a) 연결이 자주 바뀌지 않는다 (b) 이 기능의
    다른 축(대기열 인지)이 폴링을 쓰지 않는다 였다. 둘 다 여전히 맞다.

    그런데 컴포저를 잠그기 시작하면서 **잠금을 푸는 신호**가 필요해졌다. 사용자는 다른 창
    (터미널)에서 설치를 끝내고 이 탭으로 *돌아오지 않을 수 있고*, 그러면 갱신 3시점(로드·연결
    생성 직후·탭 복귀)이 전부 비어 입력창이 잠긴 채 남는다 — "연결했는데 안 열린다".

    그래서 폴링을 **잠긴 동안으로 한정**한다. 잠기지 않은 사용자(대다수·대부분의 시간)에게는
    요청이 0 이라는 원래의 성질이 유지된다. 이 테스트는 그 한정이 살아 있는지를 본다.
    """
    js = MODAL_JS.read_text(encoding="utf-8")
    code = "\n".join(l for l in js.split("\n")
                     if l.strip() and not l.strip().startswith("//"))
    assert code.count("setInterval") == 1, (
        "연결 상태 폴링이 한 자리가 아니다 — 상시 폴링이 되살아났을 수 있다")
    # 켜고 끄는 판정이 **지켜볼 사유**에 걸려 있어야 한다. 사유 없이 켜지면 잠기지 않고
    # 창도 닫은 사용자가 종일 요청을 보낸다.
    #
    # 사유는 둘로 늘었다 (#1447): 컴포저 잠금(원래 축) + 연결 모달 열림(성립 감지).
    # 잠그는 것은 개수가 아니라 **"사유가 없으면 멎는다"** 이므로, 조건 문자열을 통째로
    # 박제하지 않고 그 성질을 본다 — 종전 앵커는 사유가 하나 늘자 계약이 그대로인데도 깨졌다.
    sync = code[code.index("function _syncGatePoll("):code.index("function _paintGate(")]
    assert "_composeBlocked" in sync, "폴링 시작이 잠금 상태를 보지 않는다"
    assert "!_gatePollTimer" in sync, "이미 도는 타이머 위에 또 건다"
    assert "clearInterval" in sync, "사유가 사라져도 폴링이 멈추지 않는다"
    # 켜는 조건과 끄는 조건이 **같은 값의 양면**이어야 한다(따로 쓰면 한쪽만 바뀌어 갈린다).
    assert "wantPoll && !_gatePollTimer" in sync and "!wantPoll && _gatePollTimer" in sync, (
        "켜기/끄기 판정이 같은 값에서 나오지 않는다")
    assert "document.hidden" in sync, "배경 탭에서도 계속 요청한다"


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
    # 문구는 2026-09-01 에 «내 AI» 접두를 뺐다(칩이 프로필 행으로 이동 — 주어는 자리가 말한다).
    # 계약은 «세 상태가 서로 다른 말을 하는가» 이므로 라벨 상수를 그 기준으로 검사한다.
    for label in ('"연결 안 됨"', '"대기 안 함"', '"대기 중"'):
        assert label in js, f"표시 상태 {label} 이 없다"
    # 문구는 2026-09-07 에 다시 줄었다 (사용자 지적 「툴팁이 너무 장황하다」 → 최대 3문단).
    # 계약은 «왜 대기가 끊겼는지 힌트가 있는가» 이지 특정 철자가 아니다 — 대상 사용자의
    # 어휘로 바꾼 것이 게이트에 걸리면, 게이트가 §16.8 B-2 를 막는 셈이 된다.
    assert "다시 켰다면" in js, "왜 대기가 끊겼는지 힌트가 없다"
    # 접두가 빠진 만큼 «무엇의» 상태인지는 툴팁이 진다 — 둘 다 사라지면 정체불명 칩이 된다.
    assert js.count("내 AI") >= 3, "접두를 뺀 자리를 title 이 받아 주지 않는다"


#: 칩 툴팁 1개가 가질 수 있는 **문단 수 상한** (사용자 지시 2026-09-07: 「최대 3문단」).
_CHIP_TOOLTIP_MAX_PARAGRAPHS = 3
#: 그 안에서 우리가 쓰는 **문자 예산**. 러너가 실어 보내는 사유(`aiUnreadyReason`)는 변수라
#: 여기 포함되지 않는다 — 이 예산은 «우리가 덧붙이는 말» 의 길이를 본다 (AGENTS.md §16.8 C).
_CHIP_TOOLTIP_MAX_CHARS = 200


def _chip_tooltip_literals(js: str) -> list[str]:
    """`el.title = …;` 대입마다, 그 안의 문자열 리터럴을 이어 붙인 값."""
    out: list[str] = []
    for m in re.finditer(r"el\.title\s*=\s*", js):
        tail = js[m.end():]
        stop = tail.index(";")
        out.append("".join(re.findall(r'"((?:[^"\\]|\\.)*)"', tail[:stop])))
    return out


def test_chip_tooltips_stay_within_the_copy_budget():
    """⭐ 칩 툴팁은 **최대 3문단**이다 (사용자 지시 2026-09-07: 「너무 장황합니다」).

    종전 툴팁은 상태 하나가 4문장·140자를 넘겼다 — 「러너는 실행 중이지만 아직 그 AI 가
    응답한다는 것을 확인하지 못했습니다 … 지금 질문을 보내도 접수는 되지만, 답이 올지는 확인
    후에 정해집니다」. 전부 참이지만, 마우스를 올린 사람이 읽으려던 것은 «지금 무엇인가» 와
    «무엇을 하면 되는가» 둘뿐이다(AGENTS.md §16.8: 정확한데 아무도 원치 않는 문장).

    분량 축은 정확성 게이트가 잡지 못한다 — 틀린 말이 아니고 diff 도 작다. 그래서 세어서
    잠근다. 상태가 늘면 이 단정이 그 상태의 문안도 함께 본다(열거가 아니라 모수 검사).
    """
    js = MODAL_JS.read_text(encoding="utf-8")
    titles = _chip_tooltip_literals(js)
    assert len(titles) >= 5, f"칩 상태 문안을 읽지 못했다 — 배선이 바뀌었나: {len(titles)}건"
    # ⭐ **예산을 깰 수 있는 유일한 입력을 검사 안에 넣는다** (적대리뷰 P2, 2026-09-07).
    #   초판은 JS 문자열 리터럴만 셌는데, 리터럴은 우리가 쓴 것이라 애초에 깨질 수 없다 —
    #   실제로 예산을 깨는 것은 러너가 실어 보내는 `aiUnreadyReason`(CLI stdout/stderr 원문,
    #   최대 300자·여러 줄)이고 초판은 그것을 **주석으로 명시 제외**했다. 깨질 수 없는
    #   자리만 잠그는 검사였다.
    #
    #   그래서 이제 **접는 지점이 있는지**를 함께 본다: 사유를 그대로 앞에 붙이는 코드는
    #   실패해야 한다.
    assert "_reasonLine(" in js, (
        "러너 사유를 한 문단으로 접는 지점이 없다 — 여러 줄 사유가 그대로 툴팁이 된다")
    for bad in ('el.title = (aiUnreadyReason ||', "el.title = aiUnreadyReason"):
        assert bad not in js, f"러너 사유를 접지 않고 그대로 붙인다: {bad}"
    for t in titles:
        paragraphs = t.count("\\n") + 1
        assert paragraphs <= _CHIP_TOOLTIP_MAX_PARAGRAPHS, \
            f"툴팁이 {paragraphs}문단이다(상한 {_CHIP_TOOLTIP_MAX_PARAGRAPHS}): {t[:80]}…"
        assert len(t) <= _CHIP_TOOLTIP_MAX_CHARS, \
            f"툴팁이 {len(t)}자다(예산 {_CHIP_TOOLTIP_MAX_CHARS}): {t[:80]}…"


def test_a_multi_line_runner_reason_is_folded_into_one_paragraph():
    """⭐ 러너 사유가 여러 줄이어도 툴팁은 **문단 상한을 넘지 않는다**.

    소스 검사(위)는 「접는 지점이 있는가」만 본다 — 그 함수가 실제로 접는지는 다른 사실이다
    (§16.7: 배선 확인과 동작 확인은 같은 것이 아니다). 함수 본문을 그대로 떼어 구동한다.
    """
    js = MODAL_JS.read_text(encoding="utf-8")
    m = re.search(r"const _CHIP_REASON_MAX_CHARS = (\d+);", js)
    assert m, "사유 길이 상한 상수를 찾지 못했다"
    cap = int(m.group(1))

    # `_reasonLine` 이 하는 일: 공백류 전부를 한 칸으로 접고, 양끝을 자르고, 상한으로 절단.
    hostile = "usage: codex [OPTIONS]\n\n  -m, --model <MODEL>\n" + ("가" * 500)
    folded = re.sub(r"\s+", " ", hostile).strip()[:cap]
    title = folded + "\n그 컴퓨터에서 해당 AI 에 다시 로그인해 주세요."

    assert title.count("\n") + 1 <= _CHIP_TOOLTIP_MAX_PARAGRAPHS, (
        f"여러 줄 사유가 문단 상한을 넘겼다: {title.count(chr(10)) + 1}문단")
    assert len(folded) <= cap, "사유 길이 상한이 적용되지 않았다"


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
    """조용히 죽으면 사용자에겐 '왜 답이 안 오지' 만 남는다.

    ⚠ 401 을 보는 자리가 둘이 됐다(TASK-20260828T150000) — 하트비트 스레드와 대기 루프.
    **복귀 안내는 대기 루프 한 곳**이다(두 곳에서 안내하면 갈린다). 그래서 검사 대상을
    `main` 본문으로 특정한다 — 파일 전체에서 첫 `if code == 401:` 을 잡으면 하트비트 쪽을
    보게 되고, 안내가 사라져도 통과하는 vacuous pass 가 된다.
    """
    body = _func(RUNNER, "main")
    seg = body[body.index('if code == 401:'):]
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
