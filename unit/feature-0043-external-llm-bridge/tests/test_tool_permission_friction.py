"""feature-0043 — 「도구 사용 승인을 사용자에게 요구하는」 답변을 없앤다.

## 무엇이 있었나 (라이브 제보 2026-08-28)

웹 대화창의 assistant 가 두 턴 연속 이렇게 답했다:

    첨부 파일 접근 권한이 필요합니다.
    웹 인터페이스의 권한 승인 대화에서 `mcp__mysql-ai__read_task_attachment` 도구 사용을
    승인해주신 후 "권한 승인했습니다" 라고 말씀해주세요.

그 사용자는 승인할 방법도, 승인해야 할 이유도 없었다. **승인 대화 자체가 존재하지 않는다** —
러너는 다른 머신의 헤드리스 CLI 이고, 웹 사용자는 그 프로세스에 접근할 수단이 없다.

## 진짜 원인은 권한이 아니라 자격증명 경합이었다

실측(`claude -p` 직접 구동): MCP 도구는 **권한 프롬프트 없이 호출됐고**, 돌아온 것은
`HTTP 401 유효하지 않거나 만료된 토큰입니다` 였다. 러너는 프롬프트에 이 task 에 결속된
토큰을 실어 보내는데, 같은 머신의 CLI 에 같은 서비스의 MCP 서버가 상주 설정돼 있으면
(`~/.claude.json` 의 별개 `mat_` 토큰) 모델은 그 도구를 먼저 집는다. 그 토큰이 만료된
순간 조사가 통째로 401 이 되고, 모델은 401 을 「권한이 없다」로 읽어 **승인 요청**을 만든다.

그래서 이 스위트는 두 층을 각각 잠근다:

1. **실행 측** — claude 는 `--strict-mcp-config` 로 불러 경합하는 두 번째 인증 표면을
   아예 없앤다. 이것은 권한을 낮추는 것이 **아니라 좁히는 것**이라, 파일 상단 보안 계약
   (「네 런타임의 권한 설정이 마지막 방어선」)과 정합한다.
2. **프롬프트 측** — 도구가 실패해도 승인을 요구하지 말고 실패 사실을 적으라고 못 박는다.
   `--strict-mcp-config` 가 없는 런타임(codex 등)에서는 이쪽이 유일한 방어선이다.

계약은 **동작으로** 잠근다 — `build_cmd` 와 `compose_prompt` 는 순수 함수라 실제로 돌릴
수 있고, 돌린 결과가 계약이다.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_UNIT = Path(__file__).resolve().parents[2]
_RUNNER = _UNIT / "feature-0043-external-llm-bridge" / "src" / "bridge_agent.py"

#: 러너가 **절대 넣지 않는** 플래그. 넣는 순간 러너를 띄운 사람의 마지막 방어선을 제품이
#: 임의로 내리는 것이고, 그것은 이 파일 상단 보안 계약을 파기한다.
_FORBIDDEN_FLAGS = (
    "--dangerously-skip-permissions",
    "bypassPermissions",
    "--permission-mode",
    "--allowedTools",
    "--allowed-tools",
)


def _load_runner():
    spec = importlib.util.spec_from_file_location("_runner_perm_friction", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeApi:
    """`compose_prompt` 가 쓰는 것은 이 둘뿐이다 — 네트워크를 띄우지 않는다."""

    base = "https://example.invalid"
    token = "tok_TESTONLY_0123456789"  # verify-secret-allow: 테스트 더미(발급된 적 없는 형식)


def _prompt(mod, **task) -> str:
    base = {"task_id": "t_test", "question": "이 테이블 구조를 알려줘"}
    base.update(task)
    return mod.compose_prompt(_FakeApi(), base)


# ── 실행 측: 경합하는 인증 표면을 끊는다 ─────────────────────────────────────


def test_claude_is_invoked_with_strict_mcp_config():
    """claude 호출에는 `--strict-mcp-config` 가 **실제로 실린다**.

    표를 읽는 것이 아니라 `build_cmd` 를 돌려서 확인한다 — 표에만 있고 명령 조립에서
    떨어져 나가면 라이브에서는 그대로 재발하고, 표 검사는 그것을 못 본다.
    """
    mod = _load_runner()
    cmd = mod.build_cmd("claude", "질문")
    assert "--strict-mcp-config" in cmd, (
        f"claude 호출에서 MCP 배제 플래그가 빠졌다 — 상주 MCP 토큰과 경합한다: {cmd}")


def test_strict_mcp_config_survives_model_and_effort_selection():
    """사용자가 웹에서 모델·등급을 고른 경로에서도 플래그가 살아남는다.

    `build_cmd` 는 플래그를 `{prompt}` **앞**에 끼워 넣는다. 그 삽입이 base argv 를 덮어쓰면
    모델을 고른 사용자에게만 재발하는, 화면에서는 구분되지 않는 실패가 된다.
    """
    mod = _load_runner()
    cmd = mod.build_cmd("claude", "질문", "opus", "max")
    assert "--strict-mcp-config" in cmd
    assert cmd[-1] == "질문", f"프롬프트가 마지막이 아니다: {cmd}"
    assert cmd.index("--strict-mcp-config") < cmd.index("질문"), (
        f"플래그가 프롬프트 뒤에 붙어 질문의 일부로 먹힌다: {cmd}")
    assert "--model" in cmd and "opus" in cmd, f"모델 지정이 사라졌다: {cmd}"


def test_no_mcp_config_is_supplied_so_the_server_set_is_empty():
    """`--mcp-config` 를 함께 주지 않는다 — 그래야 MCP 서버가 **0개**가 된다.

    `--strict-mcp-config` 는 "`--mcp-config` 로 준 것만 쓴다" 는 뜻이므로, 설정 파일을 함께
    주면 배제가 아니라 **교체**가 된다. 실측(2026-08-28): 플래그만 준 `claude -p` 는
    `mcp__mysql-ai__` 도구가 하나도 없다고 답했다.
    """
    mod = _load_runner()
    cmd = mod.build_cmd("claude", "질문", "opus", "max")
    assert "--mcp-config" not in cmd, f"MCP 설정을 다시 실어 배제가 무력해졌다: {cmd}"


def test_runner_never_lowers_the_operators_permission_settings():
    """어떤 런타임의 호출 형태에도 권한 우회 플래그가 없다 (보안 계약 회귀 잠금).

    `--strict-mcp-config` 를 넣은 김에 권한도 열어 두면 증상은 같이 사라지지만, 그때 사라지는
    것은 러너를 띄운 사람의 마지막 방어선이다. 그 둘은 반대 방향의 변경이다 — 하나는 표면을
    좁히고 하나는 넓힌다.
    """
    mod = _load_runner()
    for name, spec in mod._RUNTIME_SPECS.items():
        argv = " ".join(str(a) for a in (spec.get("argv") or []))
        for bad in _FORBIDDEN_FLAGS:
            assert bad not in argv, f"{name}: 권한 우회/조작 플래그가 들어갔다 — {bad}"


# ── 프롬프트 측: 실행 불가능한 지시를 답으로 내지 않는다 ─────────────────────


def test_prompt_forbids_asking_the_user_to_approve_tools():
    """프롬프트가 「사용자에게 승인을 요구하지 마라」를 명시한다.

    이것이 `--strict-mcp-config` 가 없는 런타임(codex 등)의 유일한 방어선이고, claude 에서도
    401 이 아닌 다른 실패(타임아웃·5xx)를 승인 요청으로 오역하는 것을 막는다.
    """
    mod = _load_runner()
    p = _prompt(mod)
    assert "승인" in p and "요구하지 마라" in p, (
        "승인 요구 금지 계약이 프롬프트에서 사라졌다 — 라이브에서 그대로 재발한다")
    assert "접근할 수 없" in p, (
        "왜 요구하면 안 되는지(사용자가 승인 절차에 접근 불가)가 빠졌다 — 이유 없는 금지는 약하다")


def test_prompt_tells_the_ai_what_to_do_when_a_tool_fails():
    """금지만으로는 부족하다 — **대신 무엇을 할지**를 준다.

    「승인을 요청하지 마라」만 있으면 모델은 침묵하거나 조사를 지어낸다. 실패 사실을 적고
    확인한 범위까지 답하라는 지시가 그 자리를 채운다.
    """
    mod = _load_runner()
    p = _prompt(mod)
    assert "401" in p, "어떤 실패를 말하는지가 구체적이지 않다"
    assert "확인한 범위까지" in p, "실패 시의 대체 행동이 지정되지 않았다"


def test_prompt_declares_its_token_the_only_credential():
    """상주 MCP 토큰 등 **다른 경로의 자격증명**을 쓰지 말라고 못 박는다.

    같은 서비스의 MCP 토큰은 이 task 와 무관한 계정일 수 있다 — 만료가 아니라 *유효한*
    다른 계정 토큰이면 증상 없이 남의 데이터로 답하게 된다. 만료보다 이쪽이 더 나쁘다.
    """
    mod = _load_runner()
    p = _prompt(mod)
    assert "유일한 자격증명" in p, "토큰 단일화 계약이 프롬프트에서 사라졌다"
    assert "무관한 계정" in p, "교차 계정 위험이 프롬프트에 드러나지 않는다"


def test_contract_is_present_regardless_of_attachments_or_context():
    """첨부·이전 대화 유무와 무관하게 계약이 실린다.

    라이브 실패는 **첨부가 있는** 질문에서 났다. 계약이 조건부 블록 안에 들어가면 그 조건이
    아닌 경로에서 조용히 빠지고, 그 빠짐은 화면에서 구분되지 않는다.
    """
    mod = _load_runner()
    cases = [
        {},
        {"attachments": [{"filename": "a.sql", "attachment_id": 7}]},
        {"conversation_context": "이전 대화 내용"},
        {"system_prompt": "운영자 지침"},
        {"scope": {"product_name": "GZ", "datasources": ["gunzgame"]}},
    ]
    for task in cases:
        p = _prompt(mod, **task)
        assert "요구하지 마라" in p, f"이 조합에서 계약이 빠졌다: {sorted(task)}"
        assert "유일한 자격증명" in p, f"이 조합에서 토큰 단일화가 빠졌다: {sorted(task)}"


@pytest.mark.parametrize("runtime", ["claude", "codex", "gemini"])
def test_prompt_contract_is_runtime_agnostic(runtime):
    """프롬프트 계약은 런타임을 가리지 않는다.

    `compose_prompt` 는 런타임을 인자로 받지 않으므로 이 성질은 구조적으로 보장되지만,
    누군가 런타임별 분기를 넣는 순간 codex 사용자에게만 재발하는 형태가 된다. 그 변경이
    일어나면 여기서 걸린다.
    """
    mod = _load_runner()
    assert runtime in mod._RUNTIME_SPECS
    assert "요구하지 마라" in _prompt(mod)


# ── codex 적대 리뷰 조치 (REV-20260828T171500) ───────────────────────────────
#
# 위 계약들은 **기본 경로**만 잠갔다. codex 가 그 바깥의 네 구멍을 지목했다 — 학습 플래그로
# 배제를 되돌리는 경로(P1-1) · `--cmd` 경로(P1-2) · 다른 MCP 까지 죽는 부작용(P1-3) ·
# 프롬프트 계약이 집행이 아니라는 사실(P1-4). 아래는 그 넷의 회귀다.


@pytest.mark.parametrize("flag", [
    ["--mcp-config", "{model}"],            # 방금 없앤 MCP 표면을 되살린다
    ["--strict-mcp-config", "{model}"],     # 같은 축의 반대편
    ["--permission-mode", "{model}"],       # 값에 bypassPermissions 를 담을 수 있다
    ["--dangerously-skip-permissions={model}"],
    ["--allowedTools", "{model}"],
    ["--disallowed-tools", "{model}"],
    ["--settings", "{model}"],
    ["--add-dir", "{model}"],
    ["--append-system-prompt", "{model}"],
    ["-c", "mcp_servers={model}"],          # 값 자리에 숨는 형태(codex 의 config override 축)
    ["-s", "sandbox_permissions={model}"],
])
def test_learned_flags_cannot_reopen_what_we_closed(flag):
    """AI 가 답한 플래그로 **배제·권한 축을 되열 수 없다** (codex P1-1).

    기존 방어(토큰 2개 · 치환자 1개 · 옵션 시작)는 형태만 본다. `["--mcp-config", "{model}"]`
    는 그 셋을 전부 만족하면서 우리가 방금 없앤 표면을 되살린다 — 형태가 아니라 **축**을
    봐야 잡힌다.
    """
    mod = _load_runner()
    assert mod._coerce_flag(flag, "{model}") is None, f"위험 축의 플래그가 통과했다: {flag}"


@pytest.mark.parametrize("flag,ph", [
    (["--model", "{model}"], "{model}"),
    (["-m", "{model}"], "{model}"),
    (["--model={model}"], "{model}"),
    (["--effort", "{effort}"], "{effort}"),
    (["-c", "model_reasoning_effort={effort}"], "{effort}"),   # codex 의 정당한 형태
])
def test_legitimate_flags_still_pass(flag, ph):
    """금지 목록이 **정당한 플래그를 잡아먹지 않는다**.

    이 단언이 없으면 금지 조각을 넓히다가 codex 의 `-c model_reasoning_effort=` 같은 실존
    형태를 조용히 죽일 수 있고, 그러면 추론등급 선택이 통째로 사라진다.
    """
    mod = _load_runner()
    assert mod._coerce_flag(flag, ph) == flag, f"정당한 플래그가 거부됐다: {flag}"


def test_custom_cmd_calling_claude_without_isolation_is_warned():
    """`--cmd 'claude … -p {prompt}'` 는 배제가 빠진다 — 조용히 두지 않는다 (codex P1-2).

    명령을 자동으로 고치지는 않는다(사용자가 통째로 준 것이다). 대신 **말한다** — 조용하면
    그 사용자만 원인 모를 재발을 겪는다.
    """
    mod = _load_runner()
    mod._custom_cmd_warned = False
    assert mod._warn_custom_cmd_without_mcp_isolation(
        ["claude", "--model", "opus", "-p", "Q"]) is True
    # 두 번째부터는 조용하다(질문마다 같은 줄을 찍지 않는다).
    assert mod._warn_custom_cmd_without_mcp_isolation(["claude", "-p", "Q"]) is False


def test_custom_cmd_warning_does_not_misfire():
    """이미 배제가 있거나, claude 가 아닌 CLI 면 경고하지 않는다."""
    mod = _load_runner()
    mod._custom_cmd_warned = False
    assert mod._warn_custom_cmd_without_mcp_isolation(
        ["claude", "-p", "--strict-mcp-config", "Q"]) is False
    mod._custom_cmd_warned = False
    assert mod._warn_custom_cmd_without_mcp_isolation(["codex", "exec", "Q"]) is False
    mod._custom_cmd_warned = False
    # 경로로 준 경우도 claude 로 알아본다.
    assert mod._warn_custom_cmd_without_mcp_isolation(
        ["/usr/local/bin/claude", "-p", "Q"]) is True


def test_keep_mcp_env_is_an_available_escape_hatch():
    """다른 MCP 서버를 쓰던 사용자가 되돌릴 자리가 있다 (codex P1-3).

    `--strict-mcp-config` 는 mysql-ai 만이 아니라 그 사람이 붙여 둔 **모든** MCP 를 끈다.
    기본은 배제(사용자 결정)지만, 그것이 유일한 선택지면 GitHub·사내 검색 MCP 를 쓰던 사람은
    기능을 잃는다.
    """
    mod = _load_runner()
    assert hasattr(mod, "_KEEP_MCP"), "탈출구 자체가 없다"
    src = _RUNNER.read_text(encoding="utf-8")
    assert "BRIDGE_KEEP_MCP" in src, "탈출구가 환경변수로 노출되지 않는다"
    # 기본값(미설정)에서는 배제가 걸려 있어야 한다 — 탈출구가 기본이 되면 조치가 무의미하다.
    assert mod._KEEP_MCP is False
    assert "--strict-mcp-config" in mod.build_cmd("claude", "Q")


@pytest.mark.parametrize("answer", [
    "첨부 파일 접근 권한이 필요합니다. 웹 인터페이스에서 권한을 승인해주시면 진행하겠습니다.",
    "mcp__mysql-ai__read_task_attachment 도구 사용을 승인해주신 후 다시 말씀해주세요.",
    "권한 승인 대화에서 승인해 주세요.",
    "Please approve the tool use and try again.",
])
def test_approval_requesting_answers_are_annotated(answer):
    """프롬프트 계약을 따르지 않은 답이 **그대로 나가지 않는다** (codex P1-4).

    계약은 지시이지 집행이 아니다. 라이브에서 실제로 나갔던 두 문장을 그대로 넣어 잡히는지
    본다 — 이 테스트의 입력은 가공된 예시가 아니라 **제보된 원문**이다.
    """
    mod = _load_runner()
    out, hit = mod.annotate_approval_request(answer)
    assert hit is True, f"승인 요구를 놓쳤다: {answer!r}"
    assert "승인 절차가 없고" in out, "사용자에게 「할 일이 없다」를 말하지 않는다"
    assert out.startswith(answer.rstrip()[:20]), "원 답변이 훼손됐다 — 더하기만 해야 한다"


@pytest.mark.parametrize("answer", [
    "결재 승인 테이블은 `Approvals` 이고 승인자 컬럼은 `ApproverId` 입니다.",
    "이 프로시저는 승인 요청 처리에서 강제 폐쇄로 용도가 변경되었습니다.",
    "조회 결과 3건이 확인되었습니다.",
    "",
])
def test_normal_answers_are_left_alone(answer):
    """결재·승인 **도메인**의 정상 답변에는 손대지 않는다.

    오탐이 잦으면 이 안내가 소음이 되고, 소음이 된 안내는 읽히지 않는다.
    """
    mod = _load_runner()
    out, hit = mod.annotate_approval_request(answer)
    assert hit is False, f"정상 답변을 승인 요구로 오인했다: {answer!r}"
    assert out == answer, "손대지 않아야 할 답변이 바뀌었다"


def test_handle_one_actually_wires_the_annotation():
    """`annotate_approval_request` 가 **제출 경로에 배선돼 있다**.

    함수만 있고 아무도 부르지 않으면 이 조치는 존재하지 않는 것과 같다. 그리고 제목 분리
    **뒤**여야 한다 — 앞이면 이 안내 줄이 마지막이 되어 제목 규약 위치를 밀어낸다.
    """
    src = _RUNNER.read_text(encoding="utf-8")
    body = src[src.index("def handle_one("):]
    body = body[:body.index("\ndef ")]
    assert "annotate_approval_request(" in body, "제출 경로가 감지를 부르지 않는다"
    assert body.index("split_title(") < body.index("annotate_approval_request("), (
        "제목 분리보다 앞서 붙어 제목 규약 위치를 밀어낸다")


def test_strict_mcp_support_check_prefers_the_loud_failure():
    """지원 확인이 **실패**하면 플래그를 남긴다 (codex P2-2).

    잘못 남기면 첫 질문에서 즉시·시끄럽게 실패해 고칠 수 있다. 잘못 빼면 원 결함이 조용히
    돌아와 아무도 모른다. 두 오류의 값이 다르므로 드러나는 쪽을 고른다.
    """
    mod = _load_runner()
    # 존재하지 않는 실행 파일 → 확인 불가 → 플래그 유지(True) + 표 불변
    assert mod._ensure_strict_mcp_supported("claude", exe="__no_such_cli__") is True
    assert "--strict-mcp-config" in mod._RUNTIME_SPECS["claude"]["argv"]
    # claude 가 아닌 런타임에는 애초에 해당 없음
    assert mod._ensure_strict_mcp_supported("codex") is False
