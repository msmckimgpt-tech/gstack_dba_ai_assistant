"""feature-0043 — **연결되지 않으면 요청도 입력도 막힌다** (P0-AB) + **원클릭 연결** (P0-AC).

## 사용자 결정 (2026-08-28)

> [assistant 요청, 브릿지 연결] 을 각각 구분해주세요.
> 브릿지가 연결된 상태가 아니라면 요청이 막히고 브릿지 연결 가이드가 곧바로 제공되도록
> 구성해주세요. 요청이 막힘에 따라 메세지 박스 내 상호작용도 진행되지 않도록 처리해주세요.
> (연결 완수 후 활성화)
>
> 허용 기준: "웹브라우저에서 접속 시, 머신 내 DQA프로세스가 실행중인지, 토큰이 연결되어
> 있는지 여부를 점검하여 허용합니다."
>
> …LLM에 요청함에 따라 구축하는 방식이 모두 달라 사용자의 경험이 일정하지 않은 이슈가
> 확인되었습니다. → **원클릭 명령**. 다만 "웹브라우저 내에서 해당 프로세스를 실행시킬 수
> 있어야 하며, 해당 실행도 원클릭 명령으로 이루어져야 합니다."

## 이 파일이 지키는 것

종전 구조에서 두 관심사는 **한 덩어리**였다 — 연결 안내가 대화 말풍선으로 오고, 연결은
질문을 보내야만 필요성이 드러나고, 연결 수단은 "AI 에게 지시문을 붙여넣기" 였다. 그래서
"요청" 과 "연결" 이 서로의 진입점이었다. 여기서 고정하는 것은 그 분리다:

    요청 경로   ─ 게이트를 통과해야만 열린다 (화면 잠금 + 서버 409)
    연결 경로   ─ 대화 밖의 독립 흐름 (패널 → 모달 → 명령 한 줄 → 러너)

계약은 **소스 검사**로 고정한다 — 이 모듈들은 DB·FastAPI·브라우저를 요구해 단위 실행이
불가능하고, 형제 테스트들이 같은 방식을 쓴다. 소스 검사의 한계(배선을 보지만 동작을 보지
못한다)는 알고 있으며, 동작은 PB-0008 실 브라우저 검증이 맡는다.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_REPO = _UNIT.parent

WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
CONVS = WEB_SRC / "routers" / "conversations.py"
OAUTH_AS = WEB_SRC / "routers" / "oauth_as.py"
MODAL_JS = WEB_SRC / "static" / "app" / "connect-modal.js"
COMPOSER_JS = WEB_SRC / "static" / "app" / "composer.js"
APP_JS = WEB_SRC / "static" / "app.js"
INDEX_HTML = WEB_SRC / "static" / "index.html"
CSS = WEB_SRC / "static" / "css" / "search-audit.css"
SETUP_SH_SRC = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.sh"
SETUP_PS_SRC = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_setup.ps1"
SETUP_SH_SERVED = WEB_SRC / "static" / "agent" / "bridge_setup.sh"
SETUP_PS_SERVED = WEB_SRC / "static" / "agent" / "bridge_setup.ps1"


def _func_source(path: pathlib.Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{path.name}: 함수 {name} 를 찾지 못했다")


def _strip_js_comments(js: str) -> str:
    """줄 주석을 걷어낸 코드. 주석에 적힌 설명이 계약 검사를 통과시키지 않도록."""
    return "\n".join(l for l in js.split("\n")
                     if l.strip() and not l.strip().startswith("//"))


# ══════════════════════════════════════════════════════════════════════════════
# P0-AB ① 게이트는 **두 축의 곱**이고, 판정은 서버 한 곳에서 난다
# ══════════════════════════════════════════════════════════════════════════════


def test_gate_requires_both_token_and_running_process():
    """사용자가 정한 허용 조건은 곱이다 — 토큰만으로도, 프로세스만으로도 열리지 않는다."""
    src = _func_source(OAUTH_AS, "connect_status")
    assert '"compose_blocked"' in src, "잠금 판정을 응답에 싣지 않는다 — 프런트가 조립하게 된다"
    assert "connected and listening" in src, (
        "두 축의 곱이 아니다 — 한쪽만 보면 아무도 듣지 않는 곳에 질문하게 된다")


def test_gate_does_not_fire_when_server_llm_is_open():
    """게이트를 되돌린 운영에서 잠그면 **멀쩡한 서비스의 입력창이 잠긴다.**

    브리지는 서버 LLM 이 잠겼을 때의 답변 경로다. 열려 있으면 개인 AI 연결은 선택 사항이고,
    그때 "아무도 연결하지 않았다" 는 잠금 사유가 되지 않는다.
    """
    src = _func_source(OAUTH_AS, "connect_status")
    assert "_bridge_mode()" in src, "브리지 적용 여부를 보지 않고 잠근다"
    mode = _func_source(OAUTH_AS, "_bridge_mode")
    assert "server_llm_enabled" in mode, (
        "게이트 상태를 정본(shared.llm_gate) 대신 여기서 다시 해석한다 — 두 벌이 되면 갈린다")
    assert "return False" in mode, "조회 실패 시 잠근다 — 확신 없이 서비스를 세운다"


def test_frontend_does_not_recompose_the_judgment():
    """프런트가 `connected && listening` 을 다시 조립하면 판정이 두 벌이 된다.

    P0-R 에서 이미 겪었다 — 같은 질문에 두 개의 답이 있으면 언젠가 갈리고, **갈리는 순간
    느슨한 쪽이 사용자가 보는 진실**이 된다.
    """
    code = _strip_js_comments(MODAL_JS.read_text(encoding="utf-8"))
    assert "compose_blocked" in code, "서버 판정을 읽지 않는다"
    assert "connected && listening" not in code, "프런트가 잠금 판정을 자체 조립한다"
    assert "b.connected && b.listening" not in code, "프런트가 잠금 판정을 자체 조립한다"


def test_lock_defaults_to_open_before_the_first_probe():
    """첫 조회 전에 잠그면 페이지를 열 때마다 입력창이 한 번씩 잠겼다 풀린다."""
    code = _strip_js_comments(MODAL_JS.read_text(encoding="utf-8"))
    assert "let _composeBlocked = false;" in code, "잠금 초기값이 '잠김' 이다"


def test_probe_failure_keeps_the_previous_judgment():
    """조회 실패로 잠그면 일시 장애가 서비스 정지가 되고, 풀면 장애가 우회 수단이 된다."""
    js = MODAL_JS.read_text(encoding="utf-8")
    body = js[js.index("export async function refreshConnState("):
              js.index("export function bindConnState(")]
    catch = body[body.index("} catch"):]
    assert "_paintGate" not in catch, "조회 실패 경로가 잠금 상태를 흔든다"


# ══════════════════════════════════════════════════════════════════════════════
# P0-AB ② 서버는 **집행**한다 — 화면 잠금은 표시일 뿐이다
# ══════════════════════════════════════════════════════════════════════════════


def test_server_rejects_when_no_token_and_stores_nothing():
    """낡은 탭·직접 호출이 게이트를 우회하지 못한다. 그리고 **아무것도 남기지 않는다.**

    거절하면서 질문이나 안내를 대화에 저장하면, 새로고침에 사라지는 유령 말풍선이 된다.
    """
    src = _func_source(CONVS, "_enqueue_web_bridge_task")
    head = src[:src.index('status = "open" if listening else "deferred"')]
    assert "if not connected:" in head, "토큰 미보유 요청을 차단하지 않는다"
    assert '"bridge_blocked": True' in head, "프런트가 '고장' 과 '연결 필요' 를 구분할 수 없다"
    assert '"_http_status": 409' in head, "상태 불일치를 500(고장)으로 보고한다"
    assert "INSERT INTO" not in head, "차단 경로가 대기 작업을 만든다"
    assert "_conv_add_message" not in head, "차단 경로가 대화에 말풍선을 남긴다"


def test_block_response_carries_the_axes_to_the_frontend():
    """`_json_error` 는 `{"error": …}` 뿐이라, 그대로 쓰면 연결 패널을 열 근거가 없다."""
    src = CONVS.read_text(encoding="utf-8")
    assert 'agent_result.get("bridge_blocked")' in src, "차단 분기를 응답 조립이 무시한다"
    branch = src[src.index('if agent_result.get("bridge_blocked"):'):]
    branch = branch[:branch.index("# worker mode 의 빠른 실패")]
    assert '"bridge_blocked": True' in branch
    assert '"bridge_connected"' in branch and '"bridge_listening"' in branch, (
        "어느 축이 비었는지 알리지 않아 안내 문구를 고를 수 없다")


def test_gate_check_reuses_the_listening_predicate():
    """대기 판정이 두 벌이면 화면과 서버가 갈린다 — 그때 느슨한 쪽이 진실이 된다."""
    src = _func_source(CONVS, "_account_ai_is_listening")
    assert "account_is_listening" in src, "대기 판정을 여기서 새로 만든다"
    assert "return False" in src, (
        "조회 실패를 '대기 중' 으로 본다 — 아무도 안 가져갈 질문이 대기열에 남는다")


# ══════════════════════════════════════════════════════════════════════════════
# P0-AB ③ 메시지 박스 상호작용이 실제로 멈춘다 (연결 완수 후 활성화)
# ══════════════════════════════════════════════════════════════════════════════


def test_composer_input_is_disabled_while_blocked():
    code = _strip_js_comments(COMPOSER_JS.read_text(encoding="utf-8"))
    assert "const bridgeBlocked = isComposeBlocked();" in code, "컴포저가 게이트를 읽지 않는다"
    assert "const composerLocked = isBlocked || bridgeBlocked;" in code
    assert "promptInputEl.disabled = composerLocked;" in code, "입력창이 잠기지 않는다"


def test_composer_side_controls_are_locked_too():
    """입력창만 막으면 파일을 붙여 놓고 보내지 못하는 상태가 되어 '고장' 으로 읽힌다."""
    code = _strip_js_comments(COMPOSER_JS.read_text(encoding="utf-8"))
    assert 'classList.toggle("is-bridge-locked", bridgeBlocked)' in code, (
        "첨부·모델·추론 등 부속 조작이 잠기지 않는다")
    css = CSS.read_text(encoding="utf-8")
    assert ".composer-wrap.is-bridge-locked" in css, "잠금 클래스에 스타일이 없다"
    assert "pointer-events: none" in css[css.index(".composer-wrap.is-bridge-locked"):], (
        "시각적으로만 흐리고 클릭은 통과시킨다")
    # 잠금을 푸는 유일한 버튼까지 막으면 사용자가 빠져나올 길이 없다.
    assert ":not(.composer-gate-btn)" in css, "연결 버튼까지 함께 잠근다 — 탈출구가 사라진다"


def test_send_path_guards_even_if_the_lock_lags():
    """잠금은 표시다 — Ctrl+Enter 경쟁·프로그램 호출은 별도로 막아야 한다."""
    src = COMPOSER_JS.read_text(encoding="utf-8")
    send = src[src.index("async function sendPrompt("):]
    send = send[:send.index("state.composerAttachments.uploadingCount > 0")]
    assert "isComposeBlocked()" in send, "전송 경로에 가드가 없다"
    # 입력을 지우면 연결 뒤 다시 써야 한다 — P0-X 가 없앤 마찰이 되살아난다.
    assert 'promptInputEl.value = ""' not in send, "차단하면서 사용자가 쓴 문장을 지운다"


def test_rejected_send_restores_the_input_and_removes_the_ghost_bubble():
    """409 를 일반 실패로 처리하면 유령 말풍선이 남고 사용자는 고장으로 읽는다."""
    src = COMPOSER_JS.read_text(encoding="utf-8")
    branch = src[src.index("error.status === 409 && error.payload && error.payload.bridge_blocked"):]
    branch = branch[:branch.index("gc-share-group-sync")]
    assert "filter((m) => m !== optimisticUserMessage)" in branch, (
        "서버가 저장하지 않은 질문이 화면에 남는다 — 새로고침에 사라지는 유령이 된다")
    assert "promptInputEl.value = message" in branch, "입력을 되돌려 주지 않아 재입력을 요구한다"
    assert "refreshConnState()" in branch, "잠금·안내를 즉시 맞추지 않는다"


def test_unlock_triggers_a_rerender():
    """상태를 바꾼 쪽이 렌더를 책임진다(P0-V).

    잠금이 풀린 순간에 아무도 다시 그리지 않으면 입력창이 잠긴 채 박제된다 — 연결을 마쳤는데
    쓸 수 없는 상태가 되고, 그것이 정확히 P0-V 가 라이브에서 겪은 결함의 형태다.
    """
    modal = _strip_js_comments(MODAL_JS.read_text(encoding="utf-8"))
    assert "export function onComposeGateChange(" in modal, "잠금 변화를 알릴 경로가 없다"
    assert "for (const fn of _gateListeners)" in modal, "구독자를 부르지 않는다"
    app = _strip_js_comments(APP_JS.read_text(encoding="utf-8"))
    # 콜백이 async 로 바뀌었다 (2026-08-31): 잠금 해제 시 **카탈로그를 먼저 다시 받고**
    # 그 뒤에 그린다 — 안 그러면 모델·추론 강도 항목이 옛 목록(빈 목록)으로 남아 사용자가
    # 새로고침해야 보였다. 계약은 그대로다 — 게이트가 바뀌면 다시 그린다.
    #
    # 2026-09-02 (TASK-20260902T140200): 핸들러가 **명명 함수로 추출**됐다 — 같은 절차를
    # 능력 목록 변화(`onCapsChange`)도 쓰기 때문이다(절차를 두 벌로 두면 한쪽만 고쳐지는
    # 날 경로에 따라 다른 화면이 나온다). 그래서 이 검사는 **인라인 형태를 전제하지 않고**
    # 등록된 핸들러를 이름으로 따라가 그 본문을 본다. 계약(카탈로그 → 렌더 순서)은 불변이다.
    _reg = app[app.index("onComposeGateChange("):]
    _arg = _reg[len("onComposeGateChange("):_reg.index(")")].strip()
    if _arg.isidentifier():
        # 명명 함수 — 그 정의를 찾아 본문을 본다.
        _def = app.index(f"function {_arg}(")
        _cb = app[_def:]
        _cb = _cb[:_cb.index("\n}\n") + 2]
    else:
        # 인라인 화살표 — 종전 형태도 계속 통과시킨다(형태가 계약은 아니다).
        _cb = _reg[:_reg.index("});")]
    assert "renderComposer()" in _cb, "잠금이 풀려도 컴포저를 다시 그리지 않는다"
    assert "loadVaultOptions()" in _cb, (
        "잠금이 풀렸는데 모델 카탈로그를 다시 받지 않는다 — 선택기가 빈 채로 남는다")
    assert _cb.index("loadVaultOptions()") < _cb.index("renderComposer()"), (
        "옛 목록으로 그린 뒤에 카탈로그를 받는다(순서가 반대다)")


# ══════════════════════════════════════════════════════════════════════════════
# P0-AB ④ 가이드는 **곧바로** 온다 — 그리고 사유별로 다른 말을 한다
# ══════════════════════════════════════════════════════════════════════════════


def test_guide_panel_exists_next_to_the_composer():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="composerGate"' in html, "잠금 안내 패널이 없다"
    assert 'id="composerGateBtn"' in html, "조치 경로가 없다 — 잠금이 고장과 구분되지 않는다"
    # 패널은 컴포저 안에, 그리고 **입력창보다 위**에 있어야 한다. 아래에 두면 사용자는 잠긴
    # 입력창을 먼저 만나 고장으로 읽은 뒤에야 사유를 본다(실 브라우저 실측 2026-08-28).
    assert html.index('class="composer-wrap"') < html.index('id="composerGate"')
    assert html.index('id="composerGate"') < html.index('id="promptInput"'), (
        "안내가 입력창 아래에 있다 — 사유보다 잠금을 먼저 만난다")


def test_connection_chip_is_free_of_the_footer_collapse_rule():
    """칩을 넣은 것과 칩이 보이는 것은 다른 사실이다 (실 브라우저 실측 2026-08-28).

    종전엔 칩이 `.composer-footer` 안에 있어, status·hint 가 비고 provider 상태점이 숨겨지는
    **평상시 화면**에서 footer 와 함께 통째로 접혔다. 그래서 접힘 조건에 칩을 넣어 예외를 뒀다.

    2026-09-01 제보로 칩을 사이드바 프로필 행으로 옮기며 그 종속 자체를 끊었다. 이제 남은 계약은
    반대 방향이다 — 접힘 조건에 `.ai-conn` 이 **남아 있으면 안 된다**. footer 안에 없는 요소를
    찾는 `:has()` 는 영영 거짓이라 규칙이 매칭되지 않고, 빈 footer 한 줄이 입력창 아래에 상시
    남는다(사용자가 지적한 "불필요한 여백" 이 정확히 그 줄이다).
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert (html.index('class="sidebar-profile"')
            < html.index('id="aiConnState"')
            < html.index('class="composer-footer"')), (
        "칩이 사이드바 프로필 행에 없다 — 컴포저로 돌아가면 여백 문제도 함께 돌아온다")

    css = (WEB_SRC / "static" / "css" / "chat.css").read_text(encoding="utf-8")
    line = [l for l in css.split("\n") if l.startswith(".composer-footer:has(")]
    assert line, "footer 접힘 규칙을 찾지 못했다"
    assert ".ai-conn" not in line[0], (
        "footer 밖으로 나간 칩을 접힘 조건이 아직 찾는다 — 조건이 영영 거짓이라 빈 줄이 남는다")

    # 칩이 프로필 행 «여백» 에 얹히는 근거. 이 규칙이 없으면 칩은 프로필 버튼 아래로 흘러
    # 사이드바 하단에 한 줄을 새로 만든다 — 여백을 옮겨 심는 것에 지나지 않는다.
    prof = (WEB_SRC / "static" / "css" / "profile.css").read_text(encoding="utf-8")
    assert ".sidebar-profile > .ai-conn" in prof, "프로필 행 배치 규칙이 없다"

    # 자리가 모자랄 때의 계약: **이름을 뭉개지 않고 칩이 다음 줄로 내려간다.**
    # 그 판단은 폭 임계값이 아니라 실제 계정 이름 길이가 한다 — 같은 252px 사이드바라도
    # `admin` 은 여백이 119px 남고 `bootstrap_admin` 은 10px 밖에 안 남는다(실측 2026-09-01).
    # 두 축이 다 필요하다: wrap 이 없으면 칩이 밀려 나가고, trigger 가 shrink 하면
    # wrap 대신 이름이 잘린다.
    row = prof[prof.index(".sidebar-profile {"):prof.index(".profile-avatar {")]
    assert "flex-wrap: wrap" in row, (
        "자리가 없을 때 칩이 다음 줄로 내려갈 길이 없다 — 사이드바는 180px 까지 좁아진다")
    assert "flex: 1 0 auto" in row, (
        ".profile-trigger 가 shrink 한다 — 칩이 들어올 자리를 계정 이름에서 빼앗아 "
        "다음 줄로 내려가는 대신 이름이 잘린다")


def test_guide_distinguishes_missing_token_from_stopped_process():
    """사용자가 할 일이 다르다 — 하나로 뭉치면 이미 연결한 사람에게 처음부터 하라고 말한다."""
    modal = MODAL_JS.read_text(encoding="utf-8")
    paint = modal[modal.index("function _paintGate("):modal.index("function _paintConn(")]
    assert "body.connected !== true" in paint, "두 상태를 구분하지 않는다"
    assert "연결되어 있지 않습니다" in paint and "실행 중이 아닙니다" in paint, (
        "사유별 안내가 없다")
    assert "내 AI 실행하기" in paint, "러너만 꺼진 사용자에게 실행 경로를 주지 않는다"


def test_gate_button_opens_the_connect_modal():
    """안내 버튼이 **조치로 이어진다**.

    ⚠ 2026-09-02 부터 그 조치는 «무조건 창 열기» 가 아니다 — 이미 연결해 본 사용자에게는 바로
    실행을 쏘고, 실패했을 때·이력이 없을 때만 창으로 간다(사용자 요청: 접근성). 그래서 이
    계약은 **버튼이 그 단일 진입점으로 간다**는 것과, **그 진입점이 창으로 떨어질 수 있다**는
    것을 잠근다. 리터럴 `openConnectModal()` 을 이 자리에서 요구하면 개선을 되돌리라는 게이트가
    된다(그 함수 이름은 계약이 아니라 구현 세부다).
    """
    code = _strip_js_comments(MODAL_JS.read_text(encoding="utf-8"))
    bind = code[code.index("export function bindConnState("):]
    assert "composerGateBtn" in bind and "_connectEntry" in bind, (
        "안내 버튼이 연결 흐름으로 이어지지 않는다")
    entry = code[code.index("function _connectEntry("):]
    entry = entry[:entry.index("\nexport function")]
    assert "openConnectModal()" in entry, "막다른 길이 된다 — 창으로 떨어질 경로가 없다"


def test_send_button_tooltip_prioritises_the_bridge_reason():
    """권한 안내가 앞서면 사용자는 관리자에게 문의하러 간다 — 실제로 할 일은 연결이다."""
    code = _strip_js_comments(COMPOSER_JS.read_text(encoding="utf-8"))
    tip = code[code.index("sendBtn.title = bridgeBlocked"):]
    tip = tip[:tip.index("conversation.ask") + 20]
    assert tip.index("연결되어 있지 않습니다") < tip.index("conversation.ask")


# ══════════════════════════════════════════════════════════════════════════════
# P0-AC 원클릭 연결 — LLM 해석층을 걷어낸다
# ══════════════════════════════════════════════════════════════════════════════


def test_launch_commands_are_composed_by_the_server():
    """무결성 값(CA 지문·체크섬)은 **서버 사실**이다 — 화면이 조립하면 영원히 빠진다."""
    src = _func_source(OAUTH_AS, "compose_launch_commands")
    assert "_ca_fingerprint()" in src and "_runner_checksum()" in src, (
        "대조 값 없이 스크립트를 실행시킨다 — 사회공학과 구분되지 않는다(P0-W)")
    assert "BRIDGE_CA_SHA256" in src and "BRIDGE_AGENT_SHA256" in src, (
        "대조 값이 명령에 실리지 않아 스크립트가 검증할 수 없다")
    assert '"protocol"' in src, "브라우저에서 실행할 경로가 없다"


def test_launch_commands_reach_the_client():
    src = _func_source(OAUTH_AS, "connect_issue_token")
    assert "compose_launch_commands(" in src, "발급 응답에 원클릭 명령이 없다"
    code = _strip_js_comments(MODAL_JS.read_text(encoding="utf-8"))
    assert "body.launch" in code, "화면이 서버 명령을 읽지 않는다"


def test_frontend_never_assembles_the_command_itself():
    """자체 조립본은 서버 문안이 개정돼도 갱신되지 않는다 — P0-X 가 실제로 겪은 결함이다."""
    code = _strip_js_comments(MODAL_JS.read_text(encoding="utf-8"))
    for leak in ("BRIDGE_TOKEN=", "bridge_setup.sh", "mcpServers", "dqa-connect://"):
        assert leak not in code, f"프런트가 명령을 자체 조립한다({leak}) — 서버 개정이 도달하지 않는다"


# ⚠ 삭제됨: `test_missing_checksum_omits_verification_instead_of_failing_closed`
#
# 그 테스트는 "체크섬이 없으면 대조 줄을 빼고 그대로 실행한다" 를 계약으로 고정했다. 근거는
# "빈 값과 비교하면 항상 불일치라 정상 사용자가 막힌다" 였고 그 관찰은 맞았지만 **결론이
# 틀렸다** — 체크섬은 평문 HTTP 로 받는 것을 정당화하는 유일한 근거이므로, 값이 없을 때
# 지워야 할 것은 *대조* 가 아니라 *평문 경로* 다(codex 적대 리뷰 P1).
# 대체 계약: `test_plaintext_path_closes_without_a_checksum`.


def test_edge_serves_the_setup_script_over_plain_http():
    """설치 스크립트도 CA 와 **같은 부트스트랩 데드락**에 걸린다 (실 브라우저 실측 2026-08-28).

    스크립트가 하는 첫 일이 사내 CA 를 받아 신뢰시키는 것인데, 스크립트 자신을 https 로만 주면
    CA 가 없는 머신은 그것부터 받을 수 없다. 엣지는 `/trust/*` 만 평문으로 열어 두었으므로,
    이 두 파일을 명시적으로 더한다 — `/static/*` 를 통째로 열면 앱 자산 전체가 평문 경로를
    갖는다.
    """
    caddyfile = (_REPO / "unit" / "feature-0006-lan-proxy-access" / "src" / "caddy" / "Caddyfile")
    text = caddyfile.read_text(encoding="utf-8")
    http_block = text[text.index("http://{$WEB_PUBLIC_HOST}"):text.index("https://{$WEB_PUBLIC_HOST}")]
    assert "/static/agent/bridge_setup.sh" in http_block, (
        "설치 스크립트가 평문 경로에 없다 — CA 없는 머신은 받을 수 없다(부트스트랩 데드락)")
    assert "/static/agent/bridge_setup.ps1" in http_block
    assert "path /static/*" not in http_block, "정적 자산 전체를 평문으로 연다 — 예외가 너무 넓다"


def test_setup_scripts_verify_before_running():
    """대조 없이 받은 스크립트를 실행하면 이 경로가 곧 공격 경로가 된다."""
    sh = SETUP_SH_SRC.read_text(encoding="utf-8")
    assert "BRIDGE_CA_SHA256" in sh and "BRIDGE_AGENT_SHA256" in sh
    assert "PEM_cert_to_DER_cert" in sh, (
        "PEM 텍스트를 해싱한다 — 서버(`_ca_fingerprint`)·openssl 과 기준이 달라 항상 불일치한다")
    assert sh.count("die \"CA 지문이 다릅니다.") == 1, "지문 불일치에서 멈추지 않는다"
    ps = SETUP_PS_SRC.read_text(encoding="utf-8")
    assert "cert.RawData" in ps, "Windows 판이 DER 기준을 쓰지 않는다 — OS 마다 결과가 갈린다"
    assert "CA 지문이 다릅니다" in ps


def test_setup_scripts_say_when_they_skip_verification():
    """조용히 건너뛰면 사용자는 검증된 줄 안다."""
    for path in (SETUP_SH_SRC, SETUP_PS_SRC):
        text = path.read_text(encoding="utf-8")
        assert "대조를 건너뜁니다" in text, f"{path.name}: 대조 생략을 알리지 않는다"


def test_setup_scripts_register_the_scheme_handler():
    """브라우저는 프로세스를 못 띄운다 — 스킴 등록이 '웹에서 원클릭' 의 유일한 구현 수단이다."""
    sh = SETUP_SH_SRC.read_text(encoding="utf-8")
    assert "x-scheme-handler/$DQA_SCHEME" in sh, "Linux 핸들러 등록이 없다"
    assert "CFBundleURLSchemes" in sh, "macOS 핸들러 등록이 없다"
    ps = SETUP_PS_SRC.read_text(encoding="utf-8")
    assert "HKCU:\\Software\\Classes\\$DqaScheme" in ps, "Windows 핸들러 등록이 없다"
    assert "HKLM" not in ps, "관리자 권한이 필요한 위치에 등록한다 — 사용자 계정 밖으로 나간다"


def test_handler_registration_failure_does_not_block_connection():
    """등록은 편의다 — 여기서 멈추면 러너를 띄울 수 있는 사용자까지 연결하지 못한다.
    다만 조용히 실패해서도 안 된다(버튼을 눌러 보고 고장으로 읽는다).
    """
    for path in (SETUP_SH_SRC, SETUP_PS_SRC):
        text = path.read_text(encoding="utf-8")
        assert "핸들러를 등록하지 못했습니다" in text, f"{path.name}: 등록 실패를 말하지 않는다"
        assert "연결 자체에는 영향 없음" in text, f"{path.name}: 실패의 범위를 밝히지 않는다"


def test_launch_button_is_hidden_without_a_protocol_url():
    """없는데 보이면 누른 뒤 아무 일도 일어나지 않고, 그것을 고장으로 읽는다.

    ⚠ 조건이 **넓어졌다**(2026-09-04): 연결 프로그램이 연 앱 창 안에서도 감춘다 — 그 창에서는
    프로그램이 이미 실행 중이라 눌러도 아무 일이 없다. 지키는 성질(없으면 감춘다)은 그대로이고,
    「없다」의 경우가 하나 늘었을 뿐이다. 그래서 문자열 전체가 아니라 **그 조건이 살아 있는지**를
    단정한다.
    """
    code = _strip_js_comments(MODAL_JS.read_text(encoding="utf-8"))
    line = next((l for l in code.splitlines()
                 if "launchBtn.hidden" in l and "_launch" in l), None)
    assert line, "프로토콜 유무로 노출을 정하는 자리가 사라졌다"
    assert "!(_launch && _launch.protocol)" in line, line.strip()


def test_closing_the_modal_drops_the_token_bearing_command():
    """지시문만 지우고 명령을 남기면 '닫으면 다시 볼 수 없다' 가 절반만 참이 된다."""
    js = MODAL_JS.read_text(encoding="utf-8")
    close = js[js.index("export function closeConnectModal("):js.index("async function _make(")]
    assert "_launch = null;" in close, "토큰이 실린 명령이 메모리에 남는다"
    assert 'cmd.textContent = ""' in close, "토큰이 실린 명령이 DOM 에 남는다"


@pytest.mark.parametrize("pair", [
    (SETUP_SH_SRC, SETUP_SH_SERVED),
    (SETUP_PS_SRC, SETUP_PS_SERVED),
])
def test_served_setup_script_matches_the_source(pair):
    """정본과 배포본이 갈리면 사용자가 받는 것과 우리가 테스트한 것이 달라진다.

    러너(`bridge_agent.py`)가 이미 이 계약을 갖고 있고(`test_bridge_agent_sync`), 설치
    스크립트도 같은 이유로 같은 계약이 필요하다 — 오히려 이쪽이 먼저 실행된다.
    """
    src, served = pair
    assert served.exists(), f"{served.name} 이 서빙 경로에 없다 — 사용자가 받을 수 없다"
    assert src.read_bytes() == served.read_bytes(), (
        f"{src.name}: 정본과 배포본이 다르다 — 서버가 알려 준 체크섬도 함께 갈린다")


def test_modal_puts_the_command_before_the_ai_instruction():
    """AI 지시문이 기본 경로로 남아 있으면 '설치 결과가 매번 다르다' 가 그대로 재발한다."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    body = html[html.index('id="connectModalResult"'):html.index("connect-modal-note")]
    assert body.index('id="connectModalCmd"') < body.index('id="connectModalText"'), (
        "AI 지시문이 명령보다 앞에 온다")
    assert "<details" in body, "AI 지시문이 접히지 않아 두 경로가 같은 무게로 보인다"
    assert "설치 결과가 달라질 수 있습니다" in body, (
        "보조 경로의 성질(결과가 갈린다)을 밝히지 않는다")


# ══════════════════════════════════════════════════════════════════════════════
# codex 적대 리뷰 회귀 방어 (REV-20260828T240000 — P1 4 · P2 6)
#
# 전부 "계약은 적었는데 코드가 그만큼은 아니었던" 부류다. 소스 검사로 고정한다.
# ══════════════════════════════════════════════════════════════════════════════


def test_gate_fires_before_any_write():
    """[P1] "차단하면 아무것도 남기지 않는다" 가 절반만 참이었다.

    브리지 분기 안에서 거절하면 그 지점은 **대화 생성·제품 설정·모델 KV 저장이 이미 끝난 뒤**다.
    말풍선은 안 남지만 빈 대화가 사이드바에 남는다 — 사용자에겐 "보내지도 못했는데 새 대화가
    생겼다" 로 보인다. 판정을 쓰기 시작 전으로 올려야 계약이 통째로 참이 된다.
    """
    src = _func_source(CONVS, "ask")
    gate = src.index('"bridge_blocked": True')
    create = src.index("_resolve_conversation_for_account(")
    assert gate < create, (
        "연결 게이트가 대화 생성보다 뒤에 있다 — 차단해도 빈 대화가 남는다")
    # 권한 검사보다는 뒤여야 한다(권한 없는 요청에 연결 안내를 하면 엉뚱한 길로 보낸다).
    assert src.index('"conversation.ask"') < gate


def test_connected_helper_documents_its_new_load():
    """[P1] fail-open 헬퍼가 이제 **차단 게이트**를 떠받친다.

    종전 docstring 은 "안내 문구를 고르는 데만 쓴다 — 권한 판정이 아니다" 였다. 그 서술을 그대로
    두면 다음 사람이 "안내용이니까" 라며 더 느슨하게 고친다. 방향(fail-open)은 유지하되
    **왜 그 방향인지**가 문서에 있어야 한다.
    """
    src = _func_source(CONVS, "_account_has_connected_ai")
    assert "용도가 넓어졌다" in src, "낡은 서술이 그대로다 — 지금은 게이트가 이 값을 읽는다"
    assert "차단 게이트" in src, "이 값이 무엇을 떠받치는지 적지 않았다"
    assert "덜 나쁜가" in src, "fail-open 방향의 근거가 없다"
    assert "return True" in src, "방향이 뒤집혔다 — 일시적 DB 오류가 서비스 정지가 된다"


def test_plaintext_path_closes_without_a_checksum():
    """[P1] 체크섬은 **평문 HTTP 를 정당화하는 유일한 근거**다.

    값이 없는데 평문 경로를 그대로 주면 남는 것은 "모르는 주소에서 받은 스크립트를 검증 없이
    실행" 이고, 그 스크립트가 하는 첫 일이 CA 신뢰라 바꿔치기당하면 이후 https·토큰까지 넘어간다.
    """
    src = _func_source(OAUTH_AS, "compose_launch_commands")
    assert "sh_verifiable = bool(sh_sha)" in src, "검증 가능 여부를 판정하지 않는다"
    assert "if (host and sh_verifiable) else sh_url" in src, (
        "체크섬이 없어도 평문 URL 을 준다 — 검증 없는 실행 경로가 열린다")
    assert "if (host and ps_verifiable) else ps_url" in src


def test_posix_command_works_without_sha256sum():
    """[P2] macOS 기본 설치에는 `sha256sum` 이 없다(`shasum` 뿐) — 그 사용자에겐 명령이 통째로 실패."""
    src = _func_source(OAUTH_AS, "compose_launch_commands")
    assert "shasum -a 256 bridge_setup.sh" in src, "macOS 폴백이 없다"


def test_setup_scripts_stop_when_the_fingerprint_is_missing():
    """[P1] "경고 후 진행" 은 경고가 아니라 승인이다.

    이 CA 는 평문 HTTP 로 받았고 다음 단계에서 신뢰시킨다. 대조 없이 진행하면 바꿔치기를
    알 수 없다. 막다른 길로 두지 않되(명시 우회 제공) 기본값이 방어를 끄지는 않게 한다.
    """
    for path, escape in ((SETUP_SH_SRC, "BRIDGE_ALLOW_UNVERIFIED"),
                         (SETUP_PS_SRC, "BRIDGE_ALLOW_UNVERIFIED")):
        text = path.read_text(encoding="utf-8")
        assert "CA 지문을 받지 못해 대조할 수 없습니다" in text, (
            f"{path.name}: 지문이 없어도 그냥 진행한다")
        assert escape in text, f"{path.name}: 우회 경로가 없어 막다른 길이 된다"


def test_scheme_handler_validates_before_killing():
    """[P2] 이 스킴은 **아무 웹페이지나 열 수 있다.**

    토큰 확인 전에 pkill 하면, 임의 사이트가 쓰레기 토큰으로 URL 을 열게 하는 것만으로 정상
    러너를 끌 수 있다. 순서가 계약이다 — 먼저 검증, 그다음 교체.
    """
    sh = SETUP_SH_SRC.read_text(encoding="utf-8")
    launcher = sh[sh.index("cat > \"$LAUNCH_SH\""):sh.index("register_handler()")]
    # 주석에도 `pkill` 이 등장한다(왜 순서를 뒤집었는지 적어 두었다). 순서 계약은 **코드**의
    # 것이므로 주석 줄을 걷어내고 본다 — 안 그러면 설명글이 검사 결과를 바꾼다.
    launcher = "\n".join(l for l in launcher.split("\n") if not l.strip().startswith("#"))
    assert launcher.index("mat_*") < launcher.index("pkill"), "검증 전에 러너를 죽인다"
    assert launcher.index("--check") < launcher.index("pkill"), (
        "토큰 유효성 확인 전에 러너를 죽인다")
    ps = SETUP_PS_SRC.read_text(encoding="utf-8")
    # 슬라이스 끝은 **핸들러 등록 시작**이다. `try {` 로 자르면 파일 앞쪽(CA 수신)의 것이
    # 먼저 걸려 슬라이스가 비고, 그러면 이 검사가 조용히 무의미해진다.
    launcher_ps = ps[ps.index("$LaunchPs = Join-Path"):ps.index('$key = "HKCU:')]
    assert launcher_ps.index("notlike 'mat_*'") < launcher_ps.index("Stop-Process")


def test_status_refresh_ignores_out_of_order_responses():
    """[P2] 겹친 조회가 역순 도착하면 낡은 '열림' 이 최신 잠금을 덮고, 폴링 타이머까지 멈춘다.

    ⚠ 조기 반환에 **값이 붙었다** (`return null;`, 2026-08-31). `refreshConnState` 가 읽은
    값을 돌려주게 되면서다 — `[내 AI 실행]` 이 「요청했다」가 아니라 「대기 중이 됐다」로
    판정하려면 이 함수의 결과를 봐야 하고, 호출부가 따로 `fetch` 하면 세대 번호가 우회된다.
    낡은 응답에 `null` 을 주는 것이 계약의 일부다 — 「모른다」를 「대기 안 함」으로 바꿔
    돌려주면 성공하는 중인 사용자에게 실패라고 말하게 된다.
    """
    code = _strip_js_comments(MODAL_JS.read_text(encoding="utf-8"))
    assert "let _connSeq = 0;" in code, "세대 번호가 없다"
    assert "const seq = ++_connSeq;" in code
    assert "if (seq !== _connSeq) return null;" in code, "낡은 응답을 그대로 반영한다"


def test_drop_upload_respects_the_lock():
    """[P2] 드래그-드롭은 포인터 이벤트가 아니라 `pointer-events: none` 가드를 지나간다."""
    src = COMPOSER_JS.read_text(encoding="utf-8")
    drop = src[src.index('chatPane.addEventListener("drop"'):]
    drop = drop[:drop.index("_uploadComposerAttachments(files)")]
    assert "isComposeBlocked()" in drop, "잠긴 화면에 파일을 끌어다 놓으면 업로드된다"


def test_blocked_send_cleans_up_lazy_create_state():
    """[P2] 서버가 대화를 만들지 않았으므로(게이트가 생성 앞) 낙관 sentinel 을 걷어야 한다.

    두면 사이드바에 영영 열 수 없는 유령 "새 대화" 가 남고, 다음 전송이 그 sentinel 로 간다.
    """
    src = COMPOSER_JS.read_text(encoding="utf-8")
    branch = src[src.index("error.status === 409 && error.payload && error.payload.bridge_blocked"):]
    branch = branch[:branch.index("gc-share-group-sync")]
    assert "state.pendingNewConversation = false" in branch, "lazy-create 잔재를 정리하지 않는다"
    assert "pendingConversationEntries.delete" in branch
    # 사용자가 그 사이 새로 입력한 경우에도 원문을 잃었다는 사실은 알려야 한다.
    assert "그대로 두었습니다" in branch, "덮어쓰지 않는 경우 아무 말도 하지 않는다"


def test_standalone_connect_page_shows_the_one_click_command():
    """[P2] P0-X 가 "표시하는 화면 **전부**" 라고 못박은 그 drift 가 재발했다.

    링크를 새 탭으로 연 사용자는 원클릭 명령을 아예 만나지 못하고 AI 지시문만 받았다.
    """
    js = (WEB_SRC / "static" / "ai-connect.js").read_text(encoding="utf-8")
    assert "r.body.launch" in js, "단독 페이지가 서버의 원클릭 명령을 무시한다"
    assert "launch[osTab]" in js, "명령을 표시하지 않는다"
    html = (WEB_SRC / "static" / "ai-connect.html").read_text(encoding="utf-8")
    assert 'id="launchCmd"' in html and 'id="copyCmd"' in html
    # 모달과 같은 위계여야 한다 — 명령이 먼저, 지시문은 접힌 보조.
    assert html.index('id="launchCmd"') < html.index('id="handoffText"')
    assert "<details" in html
    # 자체 조립 금지(P0-X): 무결성 값은 서버만 안다.
    for leak in ("BRIDGE_TOKEN=", "bridge_setup.sh", "mcpServers"):
        assert leak not in js, f"단독 페이지가 명령을 자체 조립한다({leak})"
