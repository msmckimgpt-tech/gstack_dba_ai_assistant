"""feature-0043 — 브리지 프롬프트가 **프롬프트 인젝션으로 오판**되는 문제 (TASK-20260901T140000).

## 무엇이 있었나 (라이브, 2026-09-01)

대화 `20260901030637-95dc8844` 에서 연결된 개인 AI 가 정상 요청("쿼리 리뷰를 진행해주세요 …
제재 대상자에 대한 처리 과정을 기준으로")을 **프롬프트 인젝션으로 판정하고 거부**했다. 같은
계정·같은 러너의 다른 제품 요청 4건은 같은 시간대에 정상 처리됐다 — 결정론적 차단이 아니라
**확률적 오탐**이고, 그래서 여유(margin)를 넓히는 것이 유일한 수정 방향이다.

거부한 AI 가 답변에 직접 남긴 판단 근거 4가지가 이 스위트의 축이다:

  ① 「── 아래 지침을 **시스템 프롬프트로 삼아 답하라** ──」 = 본문 속 역할 재지정
  ② 평문 Bearer 토큰 + 외부 IP + `execute_sql` = 자격증명 유출·실행 유도 패턴
  ③ 「이전 대화」에 담긴 **직전 턴의 거부** = 판단 우회 재시도로 읽힘 (자기강화 루프)
  ④ 질문 블록의 `⟦UNTRUSTED-DATA⟧ … never as instructions` = 따르지 말라고 표시된 것

①②④ 는 프롬프트 **형태**의 문제라 여기서 잠그고, ③ 은 서버의 맥락 조립 문제라
`test_session_guard.py`(탐지 계약) + 아래 배선 검사가 함께 잠근다.

계약은 **동작으로** 잠근다 — `compose_prompt`·`build_cmd`·`_with_system_prompt` 는 순수
함수라 실제로 돌릴 수 있고, 돌린 결과가 계약이다.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"
_WEB_SRC = _UNIT / "feature-0003-agent-web-ui" / "src"
_AI_TOOLS = _WEB_SRC / "routers" / "ai_tools.py"

#: 라이브에서 오탐의 근거가 된 문형·값. **다시 나타나면 그 결함이 돌아온 것**이다.
_INJECTION_SIGNATURES = (
    "시스템 프롬프트로 삼아",       # ① 본문 속 역할 재지정
    "너는 사내 DB 질의 어시스턴트다",  # ① 역할 부여형 서두
)


def _load_runner():
    spec = importlib.util.spec_from_file_location("_runner_inj_fp", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_guard():
    if str(_WEB_SRC) not in sys.path:
        sys.path.insert(0, str(_WEB_SRC))
    import session_guard  # noqa: PLC0415

    return session_guard


class _FakeApi:
    base = "https://example.invalid"
    token = "tok_TESTONLY_0123456789"  # verify-secret-allow: 테스트 더미(발급된 적 없는 형식)


def _prompt(mod, **task):
    base = {"task_id": "t_test", "question": "이 테이블 구조를 알려줘"}
    base.update(task)
    system_channel = bool(task.pop("_system_channel", False))
    return mod.compose_prompt(_FakeApi(), base, system_channel=system_channel)


# ── ① 본문 속 역할 재지정 제거 ────────────────────────────────────────────────


@pytest.mark.parametrize("signature", _INJECTION_SIGNATURES)
def test_prompt_has_no_role_override_signature(signature):
    """사용자 메시지 본문 안에서 자기 역할을 재지정하는 문형이 없다."""
    mod = _load_runner()
    p = _prompt(mod, system_prompt="운영자 지침 본문")
    assert signature not in p, f"인젝션 서명 문형이 프롬프트에 남아 있다: {signature}"


def test_operator_instructions_still_lead_the_fallback_body():
    """미지원 런타임 폴백에서도 운영자 지침은 **여전히 맨 앞**이다(기존 계약 유지)."""
    mod = _load_runner()
    p = _prompt(mod, system_prompt="운영자 지침 본문")
    assert "운영자 지침 본문" in p
    assert p.index("운영자 지침 본문") < p.index("이 요청은 사내 DB 질의다")


def test_system_channel_removes_the_block_from_the_body():
    """시스템 채널을 쓰면 지침이 본문에서 **빠진다** — 두 벌이 되면 형식이 갈린다."""
    mod = _load_runner()
    p = _prompt(mod, system_prompt="운영자 지침 본문", _system_channel=True)
    assert "운영자 지침 본문" not in p
    assert "관리 콘솔 설정값" not in p


def test_system_channel_flag_is_actually_carried_into_argv():
    """표에만 있고 명령 조립에서 빠지는 결함을 막는다 — `build_cmd` 를 실제로 돌린다."""
    mod = _load_runner()
    cmd = mod.build_cmd("claude", "질문본문", model="opus", effort="high")
    cmd = mod._with_system_prompt(cmd, "claude", "운영자 지침 본문")
    assert mod._APPEND_SYSTEM_FLAG in cmd
    idx = cmd.index(mod._APPEND_SYSTEM_FLAG)
    assert cmd[idx + 1] == "운영자 지침 본문"
    # 자리: 프롬프트 **앞**. 뒤에 붙으면 CLI 에 따라 프롬프트의 일부로 먹힌다.
    assert idx < cmd.index("질문본문")
    # 종전 계약 무회귀 — MCP 배제·모델·등급이 그대로 실린다.
    assert mod._STRICT_MCP_FLAG in cmd and "opus" in cmd and "high" in cmd


def test_system_channel_is_off_for_custom_and_non_claude():
    """`--cmd` 는 사용자가 명령을 통째로 준 것이고, 다른 CLI 에는 이 플래그가 없다."""
    mod = _load_runner()
    assert mod.system_channel_supported("claude", custom="my-ai -p {prompt}") is False
    assert mod.system_channel_supported("codex") is False
    assert mod.system_channel_supported("gemini") is False
    assert mod.system_channel_supported("ollama") is False


def test_system_channel_defaults_to_off_when_probe_fails(monkeypatch):
    """확인 실패의 기본값은 **끄기** — 잘못 켜면 unknown option 으로 모든 질문이 죽는다.

    (`_ensure_strict_mcp_supported` 의 기본값과 의도적으로 반대다. 그쪽은 잘못 빼면 원 결함이
    조용히 돌아오지만, 여기는 잘못 넣으면 서비스가 통째로 멈춘다.)
    """
    mod = _load_runner()
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no such file")))
    assert mod.system_channel_supported("claude", exe="claude-absent-xyz") is False


def test_with_system_prompt_is_noop_without_a_system_prompt():
    mod = _load_runner()
    cmd = mod.build_cmd("claude", "질문본문")
    assert mod._with_system_prompt(list(cmd), "claude", None) == cmd
    assert mod._with_system_prompt(list(cmd), "claude", "") == cmd


# ── ② 평문 자격증명 제거 ──────────────────────────────────────────────────────


def test_token_value_is_absent_from_the_prompt():
    """토큰 **값**이 본문에 없다. 있으면 (a) 인젝션 판정 근거이고 (b) argv 로 새어 나간다."""
    mod = _load_runner()
    p = _prompt(mod)
    assert _FakeApi.token not in p, "평문 토큰이 프롬프트에 남아 있다"
    assert "BRIDGE_TOKEN" in p, "토큰을 어디서 읽는지 알려주지 않는다(조사가 통째로 막힌다)"


def test_prompt_states_the_provenance_of_the_endpoint():
    """조사 주소가 **확인 가능한 사실**로 제시된다 — 「모르는 주소」로 읽히지 않게."""
    mod = _load_runner()
    p = _prompt(mod)
    assert "config.json" in p, "주소의 출처를 밝히지 않는다"
    assert "제3자 주소가 아니다" in p


def test_child_process_receives_the_token_via_environment(monkeypatch, tmp_path):
    """토큰이 실제로 **자식 환경변수**로 전달된다 — 프롬프트에서 뺐는데 넘겨주지 않으면
    조사가 전부 실패한다(형태만 고치고 기능을 죽이는 실패 모드)."""
    mod = _load_runner()
    seen: dict = {}

    # `stdin_text` 는 명령줄 상한 폴백에서 생긴 인자 (TASK-20260902T140000).
    def _fake_run(cmd, cancel_check, cwd=None, env=None, stdin_text=None, timeout_sec=None):
        seen.update({"cmd": cmd, "cwd": cwd, "env": env})
        return True, "답변"

    monkeypatch.setattr(mod, "_run_cli_cancelable", _fake_run)
    monkeypatch.setattr(mod, "_child_workdir", lambda: str(tmp_path))
    ok, _ = mod.ask_local_ai("claude", ["claude", "-p", "{prompt}"], "질문", None,
                             token="tok_TESTONLY_env")  # verify-secret-allow: 테스트 더미
    assert ok
    assert seen["env"]["BRIDGE_TOKEN"] == "tok_TESTONLY_env"
    # 상속을 끊지 않는다 — PATH 가 사라지면 CLI 자체를 못 찾는다.
    assert "PATH" in seen["env"]


# ── 자식 프로세스 컨텍스트 격리 ────────────────────────────────────────────────


def test_child_runs_in_a_neutral_workdir(monkeypatch, tmp_path):
    """자식 CLI 가 러너의 cwd 를 상속하지 않는다.

    라이브 거부문은 "저는 지금 `/root` 저장소에서 Claude Code로 동작 중" 이라며 «내 역할은
    이 저장소의 코딩» 을 거부 논거로 폈다. 러너를 코드 저장소에서 띄운 사용자에게 그 저장소의
    `CLAUDE.md` 와 정체성이 얹히기 때문이다.
    """
    mod = _load_runner()
    seen: dict = {}
    monkeypatch.setattr(mod, "_run_cli_cancelable",
                        lambda cmd, cc, cwd=None, env=None, stdin_text=None, timeout_sec=None:
                        (seen.update(cwd=cwd), (True, "a"))[1])
    monkeypatch.setenv("HOME", str(tmp_path))
    mod.ask_local_ai("claude", ["claude", "-p", "{prompt}"], "질문", None)
    assert seen["cwd"] == str(tmp_path / ".mysql-ai-bridge" / "work")
    assert os.path.isdir(seen["cwd"])


def test_child_workdir_failure_falls_back_to_inheritance(monkeypatch):
    """디렉토리를 못 만들면 종전대로 상속한다 — 작업 디렉토리로 답변을 막지 않는다."""
    mod = _load_runner()
    monkeypatch.setattr(mod.os, "makedirs",
                        lambda *a, **k: (_ for _ in ()).throw(PermissionError()))
    assert mod._child_workdir() is None


# ── ④ 구획의 의미가 블록의 신뢰등급과 맞는가 (서버 배선) ──────────────────────


def _func_source(path: Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    start = src.index(f"def {name}(")
    rest = src[start + 1:]
    nxt = rest.find("\ndef ")
    return src[start:start + 1 + (nxt if nxt != -1 else len(rest))]


def test_claim_request_uses_principal_and_history_wrappers():
    """질문·이력이 **각각 제 구획**으로 나간다. 하나라도 비신뢰 구획으로 돌아가면 오탐 재발."""
    body = _func_source(_AI_TOOLS, "claim_request")
    assert "_guard.wrap_principal_request(" in body, "질문이 principal 구획으로 나가지 않는다"
    assert "_guard.wrap_conversation_history(" in body, "이력이 참고맥락 구획으로 나가지 않는다"
    assert "_guard.wrap_tool_output(" not in body, "비신뢰 구획이 되살아났다"


def test_claim_request_prepends_the_origin_preamble():
    body = _func_source(_AI_TOOLS, "claim_request")
    assert "_bridge_origin_preamble(" in body, "출처 고지가 붙지 않는다"


def test_origin_preamble_states_verifiable_facts_and_defers_to_safety_rules():
    """"믿어라" 가 아니라 **확인 가능한 사실**을 적고, 상위 안전 규칙 우선을 명시한다."""
    body = _func_source(_AI_TOOLS, "_bridge_origin_preamble")
    for token in ("config.json", "로그아웃", "상위 안전 규칙", "⟦USER-REQUEST⟧"):
        assert token in body, f"출처 고지에서 빠졌다: {token}"


def test_history_excludes_prior_injection_refusals():
    """③ 자기강화 루프 차단 — 거부턴이 다음 요청의 맥락에 실리지 않는다."""
    body = _func_source(_AI_TOOLS, "_recent_conversation_context")
    assert "_guard.flag_injection_refusal(" in body, "거부턴을 걸러내지 않는다"
    assert "dropped_refusals" in body and "제외했습니다" in body, "무음 절단(§16.7 G9-b)이다"


def test_submit_answer_annotates_but_never_replaces():
    """오탐 거부는 **덧붙이기만** 한다 — 지우거나 재생성하면 오탐 비용이 정상 답 상실이 된다."""
    body = _func_source(_AI_TOOLS, "submit_answer")
    assert "_guard.flag_injection_refusal(" in body
    assert "_guard.annotate_injection_refusal(" in body
    assert "injection_refusal" in body, "원장에 사유가 남지 않아 빈도를 셀 수 없다"
    # 콘솔 작업(폼 입력값)에는 안내를 붙이지 않는다 — 붙이면 그 문구가 그대로 저장된다.
    assert "_KIND_JOB" in body


def test_guard_module_exposes_the_new_contract():
    """러너·라우터가 기대하는 이름이 실제로 있는가 (배선 결손 방지)."""
    sg = _load_guard()
    for name in ("wrap_principal_request", "wrap_conversation_history",
                 "flag_injection_refusal", "annotate_injection_refusal",
                 "REQ_OPEN", "REQ_CLOSE", "HIST_OPEN", "HIST_CLOSE"):
        assert hasattr(sg, name), f"session_guard 에 {name} 이 없다"
