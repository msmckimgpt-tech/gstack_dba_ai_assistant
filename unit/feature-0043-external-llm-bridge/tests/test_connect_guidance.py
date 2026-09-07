"""연결 단계 체크리스트 + 클라이언트 우선 안내 (ROADMAP ITEM-03 · ITEM-06).

## 이 스위트가 지키는 것

1. **판정은 서버 한 곳** — 프런트가 곱을 조립하지 않는다(P0-L · P0-R).
2. **연결 축 ≠ AI 축** — 「듣는 중」과 「답할 AI 있음」이 한 줄로 뭉치면 사용자가 서버를 의심한다.
3. **없는 다운로드를 안내하지 않는다** — P0-I 가 세 지점에서 닫은 결함 클래스.
4. **구 서버 안전** — `steps` 를 모르는 응답에서 화면이 「전부 미완」으로 거짓 경보를 내지 않는다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_WEB = _UNIT / "feature-0003-agent-web-ui" / "src"
_STEPS_PY = _WEB / "routers" / "_connect_steps.py"
_OAUTH_AS = _WEB / "routers" / "oauth_as.py"
_JS = _WEB / "static" / "ai-connect.js"
_HTML = _WEB / "static" / "ai-connect.html"
_DISCOVERY = _UNIT / "feature-0043-external-llm-bridge" / "src" / "agent" / "discovery.py"


def _load_steps():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_connect_steps_test", _STEPS_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rows(**kw):
    mod = _load_steps()
    base = dict(connected=False, listening=False, has_caps=False,
                answered=False, client_download=None)
    base.update(kw)
    return mod, {r["key"]: r for r in mod.build_steps(**base)}


# ── 1. 단계 진행 ───────────────────────────────────────────────────────────────

def test_fresh_account_has_nothing_done():
    mod, r = _rows()
    assert [r[k]["state"] for k in ("connected", "listening", "ai", "answered")] \
        == [mod.PENDING] * 4


def test_full_chain_is_all_ok():
    mod, r = _rows(connected=True, listening=True, has_caps=True, answered=True)
    assert all(r[k]["state"] == mod.OK for k in r)
    assert mod.overall(list(r.values())) == "모두 준비되었습니다"


def test_token_alive_but_runner_down_is_fail_not_pending():
    """**재부팅하면 러너만 사라지고 토큰은 남는다.**

    이때 「연결됨」만 보이면 아무도 없는 곳에 질문하게 된다(제보 2026-08-27). `pending`(아직
    안 함)이 아니라 `fail`(했는데 끊김)이어야 사용자가 «다시 실행» 을 떠올린다.
    """
    mod, r = _rows(connected=True, listening=False)
    assert r["connected"]["state"] == mod.OK
    assert r["listening"]["state"] == mod.FAIL
    assert r["listening"]["action"], "다음 행동이 없는 실패 행은 사용자를 막다른 길에 둔다"


def test_not_connected_yet_is_pending_not_fail():
    """아직 시작도 안 한 사람에게 ❌ 를 보이면 «고장» 으로 읽힌다."""
    mod, r = _rows(connected=False)
    assert r["listening"]["state"] == mod.PENDING


# ── 2. 연결 축 ≠ AI 축 (핵심) ─────────────────────────────────────────────────

def test_listening_without_ai_blames_ai_not_the_server():
    """러너는 도는데 AI 가 없을 때 — **서버 연결과 별개임을 문장으로 말한다.**

    이것을 「연결 확인 실패」로 뭉친 것이 실제 제보였다(REQ-20260901-win-ai-detect).
    """
    mod, r = _rows(connected=True, listening=True, has_caps=False)
    assert r["listening"]["state"] == mod.OK, "연결 축은 정상이어야 한다"
    assert r["ai"]["state"] == mod.FAIL, "AI 축만 실패여야 한다"
    assert "별개" in r["ai"]["detail"], (
        "AI 축 실패가 서버 연결과 별개임을 말하지 않는다 — 사용자는 서버를 의심한다")


def test_ai_axis_is_not_judged_before_listening():
    """앞이 막혔는데 뒤를 ❌ 로 그리면 사용자는 이미 지난 단계를 다시 손댄다."""
    mod, r = _rows(connected=True, listening=False)
    assert r["ai"]["state"] == mod.PENDING


def test_overall_reports_the_earliest_problem():
    mod, r = _rows(connected=True, listening=False)
    assert "듣는 중" in mod.overall(list(r.values()))


# ── 3. 없는 다운로드를 안내하지 않는다 (ITEM-06) ───────────────────────────────

def test_no_client_download_no_client_action():
    _, r = _rows(client_download=None)
    assert r["connected"]["action"] is None, (
        "받을 수 없는 프로그램을 안내한다 — 사용자는 안내받은 대로 갔다가 막힌다(P0-I)")


def test_client_download_present_gives_action():
    _, r = _rows(client_download="https://h/static/agent/mysql-ai-client.exe")
    a = r["connected"]["action"]
    assert a and a["href"].endswith(".exe")


def _function_body(src: str, name: str) -> str:
    """`def <name>` 부터 **다음 최상위 정의 직전**까지.

    ⚠ 종전에는 `[\\s\\S]{0,1200}?\\n\\n\\n` 로 잘랐다. 그 상한은 함수가 조금만 길어지면
    매치 자체가 사라져 **단언이 「함수를 찾지 못했다」로 죽는다** — 실제로 그렇게 깨졌다
    (feature-0046 이 이 함수에 릴리스 채널 분기를 더하면서). 검사가 지키려던 성질은 그대로인데
    문자 예산 하나 때문에 게이트가 통째로 무의미해지는 형태라, 경계를 **구조**로 옮긴다.
    """
    start = src.index(f"def {name}")
    tail = src[start:]
    end = re.search(r"\n(?:@|def |class )", tail)
    return tail[:end.start()] if end else tail


def test_server_only_advertises_an_existing_file():
    """`_client_download_url` 은 **실물이 있을 때만** URL 을 낸다.

    배포 파이프라인은 리눅스 도커이고 PyInstaller 는 크로스 컴파일하지 않는다 — 즉 대부분의
    배포에서 `.exe` 는 **없다**. 그 사실이 «값» 으로 나타나야 화면이 거짓말을 하지 않는다.
    """
    body = _function_body(_OAUTH_AS.read_text(encoding="utf-8"), "_client_download_url")
    assert "is_file()" in body, "파일 존재를 확인하지 않고 URL 을 낸다"
    assert "return None" in body, "없을 때 None 을 돌려주는 경로가 없다"
    # feature-0046 client-update-channel: 1순위는 **릴리스 채널**이다. 이미지 안 경로만 보면
    # 그 자리는 라이브에서 영원히 비어 있어(PyInstaller 는 크로스 컴파일 없음) 버튼이 계속
    # 숨는다 — ROADMAP §10.2 가 미해결로 기록한 그 상태다.
    assert "client_release.download_url" in body, "릴리스 채널을 보지 않는다"


# ── 4. 프런트가 판정을 조립하지 않는다 ─────────────────────────────────────────

def _js_code() -> str:
    src = _JS.read_text(encoding="utf-8")
    src = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("//"))
    return re.sub(r"/\*[\s\S]*?\*/", "", src)


def _paint_steps_src() -> str:
    code = _js_code()
    m = re.search(r"function paintSteps\([\s\S]*?\n  \}", code)
    assert m, "paintSteps 를 찾지 못했다"
    return m.group(0)


def test_front_renders_server_steps_and_does_not_recompute():
    """서버가 준 배열을 그대로 쓴다.

    ⚠ **검사를 좁혀야 한다.** 초판은 `"info.steps" in code` 였는데, 그 문자열은
    `info.steps_summary` 에도 들어 있어 **판정을 조립하도록 바꿔도 통과**했다(뮤턴트 M6 생존).
    속성 접근 형태로 못박는다.
    """
    body = _paint_steps_src()
    assert re.search(r"info\.steps\s*\)", body) or re.search(r"info\.steps\s*\|\|", body), (
        "서버가 준 `info.steps` 배열을 쓰지 않는다")
    for forbidden in ("info.connected", "info.listening", "connected &&", "connected&&"):
        assert forbidden not in body, (
            f"프런트가 판정을 조립한다(`{forbidden}`) — 서버와 갈리면 느슨한 쪽이 진실이 된다(P0-R)")


def test_front_hides_checklist_on_old_server():
    """구 서버(이 축을 모른다)에서 **빈 목록을 «전부 미완» 으로 그리지 않는다.**

    ⚠ 초판은 함수 안 아무 데나 `aic-hidden` 이 있으면 통과했다 — 마지막 줄의
    `classList.remove("aic-hidden")` 이 그것을 만족시켜, **가드를 통째로 없애도 통과**했다
    (뮤턴트 M7 생존). 가드의 **세 부품**을 각각 확인한다.
    """
    body = _paint_steps_src()
    assert re.search(r"!rows\b", body), "빈 응답 가드(`!rows`)가 없다"
    assert re.search(r"rows\.length", body), "빈 배열 가드(`rows.length`)가 없다"
    assert 'classList.add("aic-hidden")' in body, (
        "구 서버 응답에서 체크리스트를 **감추는** 경로가 없다 — 멀쩡한 사용자에게 거짓 경보가 된다")


def test_html_has_the_containers_the_js_needs():
    """JS 가 잡는 DOM id 가 HTML 에 실재한다 — 문구 수정이 화면을 죽이지 않게(P0-G 계약)."""
    html = _HTML.read_text(encoding="utf-8")
    for el in ("connectSteps", "stepsList", "stepsSummary",
               "clientFirst", "clientDownload", "clientNote"):
        assert f'id="{el}"' in html, f"HTML 에 #{el} 이 없다 — JS 가 잡을 것이 없다"


def test_smartscreen_warning_is_disclosed_up_front():
    """미서명 배포이므로 **경고가 뜬다는 사실을 미리 말한다** (사용자 결정 2026-09-03).

    말하지 않으면 사용자는 경고를 보고 멈춘다 — 대상이 바로 「경고를 무서워하는 사람」이다.
    """
    code = _js_code()
    assert "추가 정보" in code and "실행" in code, (
        "SmartScreen 경고 통과 방법을 안내하지 않는다")


# ── 5. 러너 안내 (ITEM-06) ────────────────────────────────────────────────────

def _fn_source(path: Path, name: str) -> str:
    """함수 본문을 `ast` 로 뽑는다.

    ⚠ 정규식으로 함수 본문을 자르면 **docstring 안의 빈 줄**에서 끊겨 본문을 거의
    못 읽는다(이 파일 초판이 그랬다). 언어 인지 파서가 있으면 그것을 쓴다.
    """
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.unparse(node)
    raise AssertionError(f"{name} 을 찾지 못했다")


def test_no_ai_message_leads_with_the_client_but_keeps_cli():
    """첫 행동은 연결 프로그램, **CLI 안내는 남긴다**.

    연결 프로그램은 Windows 전용이고 배포 채널이 없는 배포도 있다 — CLI 줄을 지우면 그
    환경에서 막다른 길이 된다(커버리지 과장 금지).
    """
    body = _fn_source(_DISCOVERY, "_no_ai_message")
    assert "연결 프로그램" in body, "안내가 연결 프로그램을 가리키지 않는다"
    assert "_AI_SETUP_URL" in body, "CLI 설치 안내를 지웠다 — Windows 밖 사용자가 막힌다"
    assert body.index("연결 프로그램") < body.index("_AI_SETUP_URL"), (
        "CLI 안내가 연결 프로그램보다 먼저 나온다 — 첫 행동이 다시 터미널이 된다")


def test_no_ai_message_still_lists_searched_dirs():
    """「어디를 봤는지」는 load-bearing 이다 — 설치했는데 PATH 에 없던 실측 사례를 사용자가
    스스로 알아볼 수 있는 유일한 단서다. 새 안내를 넣느라 지우지 않았는지 확인한다."""
    body = _fn_source(_DISCOVERY, "_no_ai_message")
    assert "찾아봤습니다" in body and "_ai_install_dirs" in body
