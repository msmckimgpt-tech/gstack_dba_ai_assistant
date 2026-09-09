"""TASK-20260909T000000-prompt-autogen-delivery — 위임한 '자동 작성' 결과가 화면에 닿는가.

# 무엇이 깨져 있었나 (라이브 실증 2026-09-08 19:56)

계정 10 이 프로필 '프롬프트 > 내 프롬프트' 의 [자동 작성] 을 눌렀다. 서버는
`GET /api/auth/me/system-prompt/generate/stream` 에 **200 OK** 를 주었고, `WebAiTasks` 에
`j_LO28YKoH0ifGR5E7`(JobKind=prompt_generate, payload `{"scope":"account","scope_id":10}`)가
적재됐으며, 러너가 3초 만에 `submitted` 까지 마쳤다. **서버는 제 할 일을 다 했다.**

그런데 화면에는 아무 일도 일어나지 않았다. 게이트가 닫힌 배포에서 이 요청은 개인 AI 로
위임되고, 그때 서버는 SSE 가 아니라 `{"bridge_pending": true, poll_url, task_id}` JSON 을
준다. 세 자동작성 화면은 전환 이전의 **SSE 전용 파서**로 남아 있어 그 JSON 을 프레임으로
읽다가 `event:`/`data:` 가 없다는 이유로 조용히 버렸다.

# 이 파일이 지키는 것

값이 아니라 **연결**이다. 그 부류는 서버 단위 테스트도 프론트 헬퍼 단위 테스트도 각각
통과한 채로 기능이 0% 가 된다(feature-0043 이 P0-E·P0-U 에서 이미 두 번 겪은 형태). 그래서
여기서는 이음매만 본다 — 서버가 말하는 봉투와 화면이 읽는 봉투가 같은가, 그 봉투를 받을
권한 축이 진입점의 권한 축과 맞는가, 그리고 **실제로 굴렸을 때 결과가 폼에 닿는가**
(마지막 것은 jsdom 하네스가 담당하고 여기서는 그 하네스를 구동한다).
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess

import pytest

from shared import bridge_tasks as bt

_UNITS = pathlib.Path(__file__).resolve().parents[2]
_WEB = _UNITS / "feature-0003-agent-web-ui"
_STATIC = _WEB / "src" / "static"
_ROUTERS = _WEB / "src" / "routers"
_TESTS_WEB = _WEB / "tests"
_RUNNER_HANDLER = _UNITS / "feature-0043-external-llm-bridge" / "src" / "agent" / "handler.py"

_APP_JS = _STATIC / "app.js"
_ADMIN_JS = _STATIC / "admin.js"
_POLL_JS = _STATIC / "console-job-poll.js"
_LLM_STATE_JS = _STATIC / "admin" / "llm-state.js"

_HARNESS = _TESTS_WEB / "verify_prompt_autogen_delivery.mjs"

#: node/jsdom 이 없는 환경에서 하네스를 건너뛸 때, 그 사실이 저장소에 남아 있는지 확인하는 표지.
#: skip 만 하고 지나가면 «검사하지 않았다» 가 «통과했다» 로 보인다.
_CI_GAP_MARKER = "verify_prompt_autogen_delivery.mjs"


def _read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


# ── 러너 실패 대체문: 서버 상수와 러너 정본이 같은 문자열을 말한다 ─────────────────────

def test_runner_degraded_notice_matches_the_runner_source() -> None:
    """서버의 판정 상수는 러너가 **실제로 붙이는** 꼬리표여야 한다.

    두 벌이 갈리면 판정은 조용히 항상 False 가 되고(실패가 성공으로 보임), 그 사실은 어느
    단위 테스트에도 나타나지 않는다 — 판정 함수 자체는 계속 «정상 동작» 하기 때문이다.
    """
    handler = _read(_RUNNER_HANDLER)
    assert bt.RUNNER_DEGRADED_NOTICE in handler, (
        "러너 정본(agent/handler.py)이 더 이상 이 꼬리표를 붙이지 않는다 — "
        f"상수 {bt.RUNNER_DEGRADED_NOTICE!r} 를 러너와 함께 갱신하라")


def test_degraded_reason_extracts_the_cause_and_ignores_normal_answers() -> None:
    degraded = ("AI 가 오류로 끝났습니다(exit 1). 연결된 AI 가 남긴 사유: session limit\n\n"
                + bt.RUNNER_DEGRADED_NOTICE)
    reason = bt.runner_degraded_reason(degraded)
    assert reason is not None
    assert "session limit" in reason
    assert bt.RUNNER_DEGRADED_NOTICE not in reason, "꼬리표가 사용자 안내에 그대로 남았다"

    # 정상 답변은 건드리지 않는다 — 오탐하면 멀쩡한 결과가 폼에 도달하지 못한다.
    assert bt.runner_degraded_reason("당신은 사내 데이터 분석 도우미입니다.") is None
    assert bt.runner_degraded_reason("") is None
    assert bt.runner_degraded_reason(None) is None


def test_degraded_reason_is_bounded() -> None:
    """사유를 통째로 실으면 안내 한 줄이 화면을 밀어낸다."""
    long_reason = "가" * 5000 + "\n\n" + bt.RUNNER_DEGRADED_NOTICE
    reason = bt.runner_degraded_reason(long_reason)
    assert reason is not None and len(reason) <= 400, len(reason or "")


def test_degraded_with_empty_body_still_reports_failure() -> None:
    """사유가 비어도 «실패 아님» 으로 접히지 않는다 — 빈 문자열과 None 은 다른 사실이다."""
    assert bt.runner_degraded_reason(bt.RUNNER_DEGRADED_NOTICE) == ""


# ── 폴링 주소: 진입점의 권한 축과 맞는가 ──────────────────────────────────────────────

def test_poll_url_points_at_the_login_only_route() -> None:
    """위임 응답의 폴링 주소는 **로그인만 요구하는** 경로여야 한다.

    위임을 여는 세 진입점 중 개인 프롬프트 자동작성은 `console.access` 를 요구하지 않는다
    (`JOB_SPECS['prompt_generate']['perms']` 가 비어 있는 것이 그 사실의 기록이다). 관리
    권한이 필요한 주소를 주면 그 사용자는 작업이 정상 적재·완료돼도 결과를 영영 못 받는다.
    """
    from routers._console_jobs import poll_url_for

    assert poll_url_for("j_ABC") == "/api/profile/ai-jobs/j_ABC"
    assert "/api/admin/" not in poll_url_for("j_ABC")


def test_prompt_generate_entrypoint_requires_no_permission() -> None:
    """위 테스트의 **전제**를 함께 잠근다 — 전제가 바뀌면 이 설계도 다시 봐야 한다."""
    assert bt.console_job_perms("prompt_generate") == ()


def test_poll_url_is_escaped() -> None:
    """task id 가 경로 구분자를 품어도 주소를 벗어나지 않는다."""
    from routers._console_jobs import poll_url_for

    assert "/" not in poll_url_for("a/b").rsplit("/", 1)[-1]


def test_delegation_envelope_uses_the_helper_not_a_literal() -> None:
    """봉투를 만드는 곳이 주소를 직접 적으면, 주소를 옮긴 날 한쪽만 바뀐다."""
    src = _read(_ROUTERS / "_console_jobs.py")
    assert "poll_url_for(task_id)" in src
    assert '"poll_url": f"/api/admin/ai-jobs/' not in src


# ── 진행/결과 응답: 두 경로가 같은 계약을 말한다 ──────────────────────────────────────

def _job(**over):
    base = {
        "task_id": "j_X", "job_kind": "prompt_generate", "status": "submitted",
        "origin": "web", "answer": None, "payload": None, "applied_at": object(),
        "apply_error": "", "claimed_by": 10, "claimed_at": None, "account_id": 10,
        "result": "당신은 분석 도우미입니다.",
    }
    base.update(over)
    return base


def test_status_payload_phases() -> None:
    from routers._console_jobs import build_job_status_payload

    assert build_job_status_payload(_job())["phase"] == "done"
    assert build_job_status_payload(
        _job(status="open", claimed_by=None))["phase"] == "waiting"
    assert build_job_status_payload(_job(status="open"))["phase"] == "working"
    assert build_job_status_payload(_job(status="canceled"))["phase"] == "canceled"
    assert build_job_status_payload(
        _job(apply_error="대상 없음"))["phase"] == "apply_failed"


def test_status_payload_marks_runner_failure_as_degraded() -> None:
    """러너가 실패를 안내문으로 대체 제출한 경우, 화면이 그것을 결과로 착각하지 않게 한다.

    상태 자체는 `submitted`·`done` 그대로 둔다 — 러너는 제 할 일(제출)을 했다. 해석만 덧붙인다.
    """
    from routers._console_jobs import build_job_status_payload

    body = ("AI 가 오류로 끝났습니다(exit 1). 사유: limit\n\n" + bt.RUNNER_DEGRADED_NOTICE)
    out = build_job_status_payload(_job(result=body))
    assert out["phase"] == "done"          # 러너는 제출했다
    assert out["degraded"] is True         # 그러나 AI 는 해내지 못했다
    assert "limit" in out["degraded_reason"]

    normal = build_job_status_payload(_job())
    assert normal["degraded"] is False and normal["degraded_reason"] == ""


def test_status_payload_hides_the_body_until_submitted() -> None:
    """진행 중 부분 결과를 흘리면 화면이 그것을 최종으로 읽고 폼에 채운다."""
    from routers._console_jobs import build_job_status_payload

    out = build_job_status_payload(_job(status="open"))
    assert out["result"] is None
    assert out["degraded"] is False, "본문이 없는데 실패로 단정하지 않는다"


def test_both_poll_routes_share_one_assembly() -> None:
    """admin 경로와 profile 경로가 **같은 함수**를 쓴다.

    두 벌로 두면 한쪽만 고쳐지고, 화면은 어느 경로로 물었는지에 따라 다른 사실을 듣는다.
    """
    admin_src = _read(_ROUTERS / "admin_console.py")
    profile_src = _read(_ROUTERS / "profile.py")
    assert "_ai_job_status_response(task_id, account, conn)" in admin_src
    assert "_ai_job_status_response(task_id, account, conn)" in profile_src
    assert "build_job_status_payload" in admin_src


def test_profile_poll_route_is_login_only_and_account_scoped() -> None:
    """신설 경로는 로그인만 요구하되 **자기 계정이 연 작업만** 돌려준다.

    권한을 넓히는 변경이 아니다 — 스코프 술어(`account_id=`)가 admin 경로와 같으므로 이
    라우트가 더 많은 것을 보여 주지 않는다. 그 두 사실이 함께 성립해야 안전하다.
    """
    profile_src = _read(_ROUTERS / "profile.py")
    m = re.search(r'@router\.get\("/api/profile/ai-jobs/\{task_id\}"\)(.*?)(?=\n@router\.)',
                  profile_src, re.S)
    assert m, "프로필 폴링 라우트를 찾지 못했다"
    block = m.group(1)
    assert "app.get_current_account" in block, "로그인 확인이 없다"
    assert "require_permission" not in block, (
        "이 진입점은 로그인만 요구한다 — 권한을 걸면 개인 프롬프트 사용자가 결과를 못 받는다")

    admin_src = _read(_ROUTERS / "admin_console.py")
    assert "load_console_job(conn, str(task_id), account_id=account_id)" in admin_src, (
        "공통 조회가 계정 스코프를 잃었다 — 남의 작업이 보이게 된다")


# ── 프론트 배선: 세 자동작성 화면이 위임 봉투를 읽는다 ────────────────────────────────

_ENTRYPOINTS = [
    ("app.js (프로필 '내 프롬프트')", _APP_JS),
    ("admin.js (역할·제품 프롬프트)", _ADMIN_JS),
]


@pytest.mark.parametrize("label,path", _ENTRYPOINTS, ids=[e[0] for e in _ENTRYPOINTS])
def test_autogen_screens_branch_on_the_delegation_envelope(label: str, path: pathlib.Path) -> None:
    """SSE 파서에 들어가기 **전에** 위임 봉투를 가른다.

    순서가 뒤집히면(스트림을 먼저 읽고 나서 판정) 이 결함이 그대로 재현된다 — 본문을 다 읽은
    뒤에는 이미 프레임이 하나도 없어 «조용한 성공» 으로 끝난다.
    """
    src = _read(path)
    assert "looksDelegatedEnvelope(resp)" in src, f"{label}: 위임 분기가 없다"
    assert "bridge_pending" in src, f"{label}: 위임 봉투 키를 모른다"
    i_branch = src.index("looksDelegatedEnvelope(resp)")
    i_reader = src.index("resp.body.getReader()", i_branch - 4000 if i_branch > 4000 else 0)
    assert i_branch < i_reader, f"{label}: 위임 판정이 스트림 소비보다 뒤에 있다"


@pytest.mark.parametrize("label,path", _ENTRYPOINTS, ids=[e[0] for e in _ENTRYPOINTS])
def test_autogen_screens_import_the_shared_poller(label: str, path: pathlib.Path) -> None:
    """정의가 있어도 **import 하지 않으면** 런타임 ReferenceError 로 기능이 통째로 죽는다.

    ESM 자유변수는 소스만 읽어서는 멀쩡해 보인다 — 그래서 배선 자체를 단정한다.
    """
    src = _read(path)
    m = re.search(r"import\s*\{([^}]*)\}\s*from\s*\"[^\"]*(console-job-poll|llm-state)\.js\?v=",
                  src, re.S)
    assert m, f"{label}: 폴링 헬퍼 import 가 없다"
    names = {n.strip() for n in m.group(1).split(",")}
    assert {"awaitDelegatedResult", "jobPhaseLabel", "looksDelegatedEnvelope"} <= names, names


def test_shared_poller_has_no_admin_dependency() -> None:
    """공용 모듈이 admin 상태를 다시 끌어오면 프로필 화면에서 쓸 수 없게 된다(원래 결함의 뿌리).

    판정은 **import 와 식별자 사용**으로 한다 — 주석은 이 모듈이 왜 옮겨졌는지 설명하며
    `admin.js` 를 언급할 수밖에 없고, 그것을 결함으로 세면 배경을 적을수록 테스트가 실패한다.
    """
    src = _read(_POLL_JS)
    code = re.sub(r"//[^\n]*", "", src)          # 줄 주석 제거(이 파일에 블록 주석은 없다)
    assert "import" not in code, "공용 폴링 헬퍼는 어떤 모듈에도 의존하지 않는다"
    assert "adminState" not in code, "폴링 헬퍼가 관리 콘솔 상태에 다시 묶였다"


def test_llm_state_still_re_exports_for_existing_callers() -> None:
    """`admin/metadata.js` 등 기존 호출부의 import 경로를 깨지 않는다."""
    src = _read(_LLM_STATE_JS)
    assert "console-job-poll.js?v=dev" in src
    for name in ("awaitDelegatedResult", "jobPhaseLabel", "looksDelegatedEnvelope"):
        assert name in src, name
    assert "awaitDelegatedResult" in _read(_STATIC / "admin" / "metadata.js")


def test_poller_stops_on_runner_failure_instead_of_filling_the_form() -> None:
    """서버의 `degraded` 표시를 헬퍼가 실제로 본다 — 안 보면 안내문이 폼을 덮는다."""
    src = _read(_POLL_JS)
    assert "body.degraded === true" in src


# ── 행위: jsdom 위에서 정본을 굴린다 ─────────────────────────────────────────────────

def test_delivery_behaviour_harness() -> None:
    """위 단정들은 «배선이 있는가» 까지다. 결과가 실제로 폼에 닿는지는 굴려 봐야 안다.

    node/jsdom 이 없으면 그 사실이 저장소에 기록돼 있는지 확인한다 — 조용히 skip 하면
    «검사하지 않았다» 가 «통과했다» 로 보인다(feature-0003 의 side-panel 하네스와 같은 규율).
    """
    assert _HARNESS.exists(), "행위 하네스 파일 부재"
    node = shutil.which("node")
    if node:
        proc = subprocess.run(
            [node, str(_HARNESS)], cwd=str(_TESTS_WEB),
            capture_output=True, text=True, timeout=300,
            env={**os.environ, "NODE_OPTIONS": ""},
        )
        if proc.returncode != 2:      # 2 = jsdom 미설치 → 아래 gap 경로로 강등
            assert proc.returncode == 0, (
                f"행위 하네스 FAIL:\n{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}")
            assert "failed" in proc.stdout, "하네스가 집계를 내지 않았다(구동 실패 은폐)"
            return
    docs = _UNITS / "feature-0043-external-llm-bridge" / "docs"
    recorded = any(
        _CI_GAP_MARKER in p.read_text(encoding="utf-8")
        for p in [docs / "REVIEW.md", *sorted((docs / "test-runs.d").glob("*.md"))]
        if p.exists()
    )
    assert recorded, (
        "node/jsdom 부재로 행위 하네스를 돌리지 못했는데 그 gap 이 어디에도 기록돼 있지 않다 — "
        f"REVIEW.md 또는 test-runs.d 에 `{_CI_GAP_MARKER}` 미실행 사유를 남겨라")
