"""OAuth frontier identity 관문(cc-identity-chokepoint 2026-08-25) 회귀 고정.

배경 — 이 결함은 **두 번 발생했다**:
  · 2026-07-24 최초 봉인: frontier 모델(Sonnet 5·Opus 5)은 Anthropic 이 system 첫 블록에
    Claude Code identity 를 요구하며, 없으면 429(rate_limit 로 위장된 identity 게이트)로 거부한다.
    그때는 주입을 **호출측 3곳**(대화·redteam·probe)에 개별로 넣어 해소했다.
  · 2026-08-25 재발: 개별 주입이라 그 3곳 밖의 경로는 계속 무방비였다. 라이브 대화가
    5분간 18회 재시도 끝에 실패했고, 사용자에게는 무관한 데이터소스 안내가 나갔다.

그래서 이 스위트는 "함수가 옳게 동작하는가"(계약)뿐 아니라 **"provider 로 나가는 지점이
그 함수를 실제로 거치는가"(배선)** 를 AST 로 강제한다 — 배선이 끊긴 채 헬퍼만 옳으면
헬퍼 단위 테스트는 전부 통과하면서 라이브는 다시 429 가 된다(그것이 재발의 실제 모습이었다).
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from shared.model_catalog import (
    OAUTH_FRONTIER_IDENTITY,
    ensure_oauth_frontier_identity,
    requires_oauth_frontier_identity,
)
from modules.llm import prepare_provider_messages

FRONTIER = "claude-sonnet-4-chat"   # adaptive 계열 → identity 요구
BUDGET = "claude-haiku-4"           # budget 계열 → 미요구

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
_LLM_PY = _SRC / "modules" / "llm.py"
_AGENT_PY = _SRC / "agent_core.py"


# ── 1. identity 문자열·판정 계약 ──────────────────────────────────────────────

def test_identity_string_is_exact():
    # Anthropic 게이트는 **정확 일치**를 본다. 오타·재작성은 곧 429 다.
    assert OAUTH_FRONTIER_IDENTITY == "You are Claude Code, Anthropic's official CLI for Claude."


def test_requires_identity_splits_frontier_from_budget():
    assert requires_oauth_frontier_identity(FRONTIER) is True
    assert requires_oauth_frontier_identity(BUDGET) is False


# ── 2. ensure_oauth_frontier_identity 계약 ────────────────────────────────────

def test_injects_identity_as_first_message_for_frontier():
    msgs = [{"role": "system", "content": "제품 프롬프트"},
            {"role": "user", "content": "질문"}]
    out = ensure_oauth_frontier_identity(msgs, FRONTIER)
    assert out[0] == {"role": "system", "content": OAUTH_FRONTIER_IDENTITY}
    # 제품 프롬프트는 **별도 메시지로 뒤에** 남는다 — 한 문자열로 병합하면 게이트를 통과하지 못한다.
    assert out[1]["content"] == "제품 프롬프트"
    assert len(out) == 3


def test_is_idempotent_so_caller_and_chokepoint_can_both_run():
    msgs = [{"role": "system", "content": "제품 프롬프트"}]
    once = ensure_oauth_frontier_identity(msgs, FRONTIER)
    twice = ensure_oauth_frontier_identity(once, FRONTIER)
    assert twice is once, "이미 주입된 배열은 동일 객체로 반환되어야 한다(중복 주입 금지)"
    assert sum(1 for m in twice if m.get("content") == OAUTH_FRONTIER_IDENTITY) == 1


def test_does_not_mutate_caller_list():
    msgs = [{"role": "system", "content": "제품 프롬프트"}]
    ensure_oauth_frontier_identity(msgs, FRONTIER)
    assert len(msgs) == 1, "호출측 배열을 in-place 오염시키면 재시도 경로에서 중복 주입된다"


def test_budget_model_and_empty_pass_through_unchanged():
    msgs = [{"role": "system", "content": "제품 프롬프트"}]
    assert ensure_oauth_frontier_identity(msgs, BUDGET) is msgs
    assert ensure_oauth_frontier_identity([], FRONTIER) == []
    assert ensure_oauth_frontier_identity(None, FRONTIER) is None


# ── 3. 관문의 결과 계약 (identity 첫 메시지 · 캐시는 마지막 system) ───────────
#
# 주의(정직 표기): 두 정규화의 **적용 순서**는 결과에 영향이 없다 — identity 는 맨 앞,
# 캐시는 마지막 system 에 붙어 서로 간섭하지 않는다. 순서를 뒤집는 뮤턴트(M3)는 동치
# 뮤턴트라 생존하며, 이를 잡겠다고 인위적 단언을 만들지 않았다. 잠가야 할 것은 순서가
# 아니라 **둘 다 누락 없이 적용되는가**(§4 배선 검사)다.

def test_prepare_puts_identity_first_and_cache_breakpoint_last():
    msgs = [{"role": "system", "content": "제품 프롬프트 " * 500},  # 캐시 임계 초과용
            {"role": "user", "content": "질문"}]
    out = prepare_provider_messages(msgs, FRONTIER)
    assert out[0]["content"] == OAUTH_FRONTIER_IDENTITY, "identity 가 첫 메시지여야 한다"
    # 캐시 브레이크포인트는 **마지막 system** 에 걸려야 identity 까지 한 접두로 캐시된다.
    last_sys = max(i for i, m in enumerate(out) if m.get("role") == "system")
    blocks = out[last_sys]["content"]
    assert isinstance(blocks, list) and blocks[-1].get("cache_control"), \
        "마지막 system 에 cache_control 이 붙어야 한다"
    assert last_sys > 0, "캐시 지점이 identity(0번)보다 뒤여야 접두에 identity 가 포함된다"


def test_prepare_is_noop_for_budget_model():
    msgs = [{"role": "system", "content": "짧은 프롬프트"}, {"role": "user", "content": "q"}]
    out = prepare_provider_messages(msgs, BUDGET)
    assert not any(m.get("content") == OAUTH_FRONTIER_IDENTITY for m in out)


# ── 4. 배선 강제 (AST) — 재발 방지의 핵심 ─────────────────────────────────────
#
# 재발 형태는 "헬퍼는 멀쩡한데 새 경로가 그것을 안 부름" 이었다. 따라서 헬퍼 호출 여부를
# 구조적으로 잠근다: 캐시만 단독으로 거는 지점 = identity 를 빠뜨린 지점이다.
#
# ⚠ 이 검사의 한계(정직 표기 — 완벽하다고 주장하지 않는다): AST 정적 검사는 **흔한 실수
# 형태**(관문 누락 · 반환값 버림 · 관문 뒤 원본으로 덮어쓰기)를 잡는다. 값이 여러 함수·
# 자료구조를 건너 흐르는 정교한 우회까지 잡지는 못한다(적대 리뷰가 실제로 그런 변이를
# 만들어 보였다). 그런 경우의 최종 안전망은 정적 검사가 아니라 **배포 후 라이브 실측**이다.
# 그래도 이 검사가 있어야 하는 이유: 2회의 실제 재발은 전부 여기서 잡히는 단순 누락이었다.

# provider 요청을 조립하는 파일 전수 — 새 파일이 생기면 여기에 추가한다.
_WIRED_FILES = [
    _SRC / "modules" / "llm.py",
    _SRC / "agent_core.py",
    _SRC / "modules" / "llm_provider_health.py",
    _SRC.parents[1] / "feature-0003-agent-web-ui" / "src" / "routers" / "_prompt_context.py",
    _SRC.parents[1] / "feature-0003-agent-web-ui" / "src" / "routers" / "admin_metadata.py",
]

def _calls_named(tree: ast.AST, name: str) -> list[ast.Call]:
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name]


def _provider_create_calls(tree: ast.AST) -> list[ast.Call]:
    """`*.chat.completions.create(...)` 호출 전부 — provider 로 실제로 나가는 지점."""
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "create"]


def _is_gateway_call(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "prepare_provider_messages")


def _assign_targets(node: ast.AST) -> list[ast.expr]:
    """`x = …` 와 `x: T = …` 를 함께 다룬다(주석 대입을 빠뜨리면 검사가 조용히 뚫린다)."""
    if isinstance(node, ast.Assign):
        return list(node.targets)
    if isinstance(node, ast.AnnAssign) and node.value is not None:
        return [node.target]
    return []


def _names_assigned_from_gateway(tree: ast.AST) -> set[str]:
    """관문 호출 결과가 대입된 변수명 — 그 변수를 통해서만 messages 가 흘러가야 한다."""
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Assign, ast.AnnAssign)) and _is_gateway_call(getattr(n, "value", None)):
            out.update(t.id for t in _assign_targets(n) if isinstance(t, ast.Name))
    return out


def _messages_sinks(tree: ast.AST):
    """요청으로 흘러가는 messages 지점 전부 — (lineno, 값 노드).

    두 형태를 모두 본다: dict 리터럴의 `"messages": X` 와 첨자 대입 `kwargs["messages"] = X`.
    후자는 적대 리뷰가 지목한 우회 형태(관문을 부른 뒤 원본으로 되돌리기)의 통로다.
    """
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if isinstance(k, ast.Constant) and k.value == "messages":
                    out.append((k.lineno, v))
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                        and t.slice.value == "messages"):
                    out.append((n.lineno, n.value))
    return out


def _gateway_overwritten_after_assignment(tree: ast.AST) -> list[int]:
    """관문 결과를 받은 변수를 **그 뒤에** 관문 아닌 값으로 덮어쓴 지점.

    적대 리뷰 지적: `x = prepare_provider_messages(x, m)` 뒤에 `x = <원본>` 을 두면
    변수명만 보는 검사는 통과하지만 identity 는 사라진다.
    """
    offenders: list[int] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        first_gateway: dict[str, int] = {}
        for n in ast.walk(fn):
            if isinstance(n, (ast.Assign, ast.AnnAssign)) and _is_gateway_call(getattr(n, "value", None)):
                for t in _assign_targets(n):
                    if isinstance(t, ast.Name):
                        first_gateway.setdefault(t.id, n.lineno)
        for n in ast.walk(fn):
            if not isinstance(n, (ast.Assign, ast.AnnAssign)):
                continue
            if _is_gateway_call(getattr(n, "value", None)):
                continue
            for t in _assign_targets(n):
                if (isinstance(t, ast.Name) and t.id in first_gateway
                        and n.lineno > first_gateway[t.id]):
                    offenders.append(n.lineno)
    return offenders


@pytest.mark.parametrize("path", [_LLM_PY, _AGENT_PY], ids=["llm.py", "agent_core.py"])
def test_no_direct_prompt_cache_call_outside_the_chokepoint(path: pathlib.Path):
    """`_apply_prompt_cache` 직접 호출 금지 — 관문(prepare_provider_messages) 내부만 예외.

    캐시를 직접 걸 수 있으면 identity 를 빼놓고 provider 로 나가는 경로가 다시 생긴다.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    allowed: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "prepare_provider_messages":
            allowed = {id(c) for c in _calls_named(node, "_apply_prompt_cache")}
    offenders = [n.lineno for n in _calls_named(tree, "_apply_prompt_cache") if id(n) not in allowed]
    assert not offenders, (
        f"{path.name}: _apply_prompt_cache 직접 호출 {offenders} — "
        "prepare_provider_messages 관문을 쓰라(identity 주입 누락 = 라이브 429)"
    )


def test_every_provider_call_in_llm_py_routes_through_the_chokepoint():
    """`llm.py` 의 **모든** provider 호출이 관문을 거친다 — 한 곳이라도 빠지면 실패.

    이 검사가 본 스위트의 핵심이다. 초판은 `_apply_prompt_cache` 직접 호출만 막았는데,
    그것은 **애초에 캐시를 쓰지 않던 직접 SDK 호출**(당시 15곳)을 전혀 보지 못했다 —
    적대 리뷰(codex, 2026-08-25)가 "관문이라 선언했지만 16곳 중 15곳이 우회" 로 적발했다.
    그래서 판정 기준을 '캐시 호출 유무'가 아니라 **provider 호출 지점 전수**로 바꾼다.
    """
    tree = ast.parse(_LLM_PY.read_text(encoding="utf-8"))
    offenders = []
    for call in _provider_create_calls(tree):
        kw = {k.arg: k for k in call.keywords if k.arg}
        m = kw.get("messages")
        if m is None:
            continue  # **kwargs 전개형은 아래 agent_core 검사가 담당
        if not _is_gateway_call(m.value):
            offenders.append(call.lineno)
    assert not offenders, (
        f"llm.py: 관문을 거치지 않는 provider 호출 {sorted(offenders)} — "
        "messages=prepare_provider_messages(...) 로 감싸라(frontier 라우팅 시 라이브 429)"
    )


def test_conversation_path_feeds_gateway_result_into_the_request():
    """대화 답변 경로: 관문 **결과가 실제 요청 messages 로 흘러가는지** 까지 확인한다.

    호출만 세면 `prepare_provider_messages(...)` 를 부르고 결과를 버려도 통과한다(적대 리뷰 지적).
    그래서 관문 결과가 대입된 변수명을 모으고, 요청 dict 의 `"messages"` 가 그 변수인지 본다.
    """
    tree = ast.parse(_AGENT_PY.read_text(encoding="utf-8"))
    gateway_names = _names_assigned_from_gateway(tree)
    assert gateway_names, "agent_core 에 관문 호출 결과를 받는 대입이 없다(결과를 버리고 있다)"

    fed = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == "messages":
                fed.append(isinstance(value, ast.Name) and value.id in gateway_names
                           or _is_gateway_call(value))
    assert fed, "agent_core 요청 dict 에 'messages' 키가 없다 — 검사 대상 소실"
    assert all(fed), (
        "agent_core 요청의 'messages' 가 관문 결과가 아니다 — "
        "관문을 부르고 결과를 버리면 identity 없이 나간다"
    )


def test_deadline_chokepoint_routes_through_the_chokepoint():
    """보조 호출 chokepoint(_openai_chat_completion_with_deadline)도 관문을 거친다."""
    tree = ast.parse(_LLM_PY.read_text(encoding="utf-8"))
    target = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef)
                   and n.name == "_openai_chat_completion_with_deadline"), None)
    assert target is not None, "chokepoint 함수가 사라졌다 — 배선 검사 대상 소실"
    assert _calls_named(target, "prepare_provider_messages"), \
        "_openai_chat_completion_with_deadline 이 관문을 거치지 않는다"


def test_gateway_result_is_never_discarded():
    """관문 호출을 값 버리는 표현식 문으로 두지 않는다 — 호출은 했는데 결과를 안 쓰는 형태 차단."""
    for path in _WIRED_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        discarded = [n.lineno for n in ast.walk(tree)
                     if isinstance(n, ast.Expr) and _is_gateway_call(n.value)]
        assert not discarded, f"{path.name}: 관문 반환값을 버리는 호출 {discarded}"


@pytest.mark.parametrize("path", _WIRED_FILES, ids=lambda p: p.name)
def test_every_messages_sink_carries_gateway_result(path: pathlib.Path):
    """요청으로 흘러가는 모든 `messages` 가 관문 결과다 — dict 리터럴과 첨자 대입 양쪽.

    적대 리뷰가 지목한 `create_kwargs["messages"] = messages`(관문 되돌리기) 형태를 잡는다.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    gateway_names = _names_assigned_from_gateway(tree)
    offenders = [
        lineno for lineno, value in _messages_sinks(tree)
        if not (_is_gateway_call(value)
                or (isinstance(value, ast.Name) and value.id in gateway_names))
    ]
    assert not offenders, (
        f"{path.name}: 관문을 거치지 않은 messages 대입 {sorted(offenders)} — "
        "prepare_provider_messages(...) 결과를 넣어라"
    )


@pytest.mark.parametrize("path", _WIRED_FILES, ids=lambda p: p.name)
def test_gateway_result_is_not_overwritten(path: pathlib.Path):
    """관문 결과를 받은 변수를 그 뒤에 원본으로 덮어쓰지 않는다(적대 리뷰 지목 형태)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = _gateway_overwritten_after_assignment(tree)
    assert not offenders, (
        f"{path.name}: 관문 결과 변수를 이후에 덮어씀 {sorted(offenders)} — identity 가 사라진다"
    )
