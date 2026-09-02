"""feature-0043 — 웹 요청의 (모델·추론등급) 이 **무엇으로** 굳는가.

## 무엇을 잠그는가 (라이브 실측 2026-08-31)

`WebAiTasks` 의 오늘자 두 건이 이렇게 적재돼 있었다:

    #69, #70:  RequestedRuntime=NULL  RequestedModel='claude-haiku-4'  ReasoningLevel=NULL

`claude-haiku-4` 는 **서버 내부 alias** 다. 러너의 CLI 는 그 이름을 모르고, 받으면 버린 뒤
기본 모델로 답한다 — 그리고 답변 끝에 "요청하신 모델 claude-haiku-4 는 이 AI 에서 쓸 수 없어
기본 설정으로 답했습니다" 라는 **거짓 고지**를 붙인다(사용자는 그런 모델을 고른 적이 없다).
같은 대화의 8/28 건(#62·#65~68)은 `claude`/`sonnet`/`high` 로 정상 적재됐다.

원인은 두 줄 사이의 틈이다:

    model = str(data.get("model", "") or API_DEFAULT_MODEL).strip()   # ← 폴백이 여기서 일어나고
    ...
    requested_model=model,                                            # ← 여기는 그걸 모른다

`_enqueue_web_bridge_task` 위의 주석은 "선택기가 숨겨진 상태에서는 프론트가 값을 싣지 않으므로
여기로도 오지 않는다" 고 단언하지만, **서버 폴백이 그 사이를 메운다**. 계약을 지키는 것은 주석이
아니라 `model_explicit` 을 보는 것이다.

## 왜 AST 인가

같은 계약을 문자열로도 볼 수 있지만, 문자열 검사는 `model if model_explicit else None` 을
`model if not model_explicit else None` 으로 뒤집는 **조건 반전**을 못 잡는다(그리고 그 반전은
"명시했을 때만 버리는" 정확히 반대 동작을 만든다). 여기서는 호출 인자의 구조를 본다.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_UNIT = pathlib.Path(__file__).resolve().parents[2]
_CONV = _UNIT / "feature-0003-agent-web-ui" / "src" / "routers" / "conversations.py"
_SYSTEM = _UNIT / "feature-0003-agent-web-ui" / "src" / "routers" / "system.py"
_STORE = _UNIT / "feature-0003-agent-web-ui" / "src" / "oauth_store.py"
_SCHEMA = _UNIT / "feature-0003-agent-web-ui" / "src" / "routers" / "_bootstrap_schema.py"


def _bridge_enqueue_call() -> ast.Call:
    """`_enqueue_web_bridge_task(...)` 호출 노드. 없으면 그 자체가 실패다."""
    tree = ast.parse(_CONV.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_enqueue_web_bridge_task"):
            return node
    pytest.fail("브리지 적재 호출을 찾지 못했다 — 이 스위트가 지키려는 경로가 사라졌다")


def _kw(call: ast.Call, name: str) -> ast.expr:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    pytest.fail(f"{name} 인자가 없다")


def test_unspecified_model_is_passed_as_unspecified():
    """프론트가 고르지 않은 요청은 **무지정으로** 넘어간다 — 서버 alias 로 채워지지 않는다.

    구조를 정확히 본다: `model if model_explicit else None`. 조건이 뒤집히면(`not
    model_explicit`) 명시한 값만 버리는 정반대 동작이 되고, 그것도 통과시키지 않는다.
    """
    value = _kw(_bridge_enqueue_call(), "requested_model")
    assert isinstance(value, ast.IfExp), (
        "요청 모델이 조건 없이 넘어간다 — 서버 기본값(claude-haiku-4)이 그대로 굳는다")
    assert isinstance(value.test, ast.Name) and value.test.id == "model_explicit", (
        f"명시 여부가 아닌 것으로 가른다: {ast.dump(value.test)}")
    assert isinstance(value.body, ast.Name) and value.body.id == "model", (
        "명시했을 때 넘기는 값이 `model` 이 아니다")
    assert isinstance(value.orelse, ast.Constant) and value.orelse.value is None, (
        "무지정일 때 None 이 아닌 값을 넘긴다 — 고르지 않은 값이 그 질문에 굳는다")


def test_model_explicit_means_the_client_actually_sent_it():
    """`model_explicit` 이 **원본 요청 본문**을 본다.

    이 플래그가 `model`(폴백된 값)에서 파생되면 항상 참이 되어 위 분기가 무의미해진다.
    """
    src = _CONV.read_text(encoding="utf-8")
    line = next(ln for ln in src.splitlines() if ln.strip().startswith("model_explicit ="))
    assert 'data.get("model"' in line, f"명시 판정이 요청 본문을 보지 않는다: {line.strip()}"


def test_reasoning_level_has_no_default_fallback():
    """추론등급은 **부재를 기본값으로 채우지 않는다**(모델 축과 달리 원래부터 그렇다).

    채우면 선택기를 건드리지 않은 사용자의 요청에 등급이 실려, 러너가 그 값으로 실행한다.
    """
    src = _CONV.read_text(encoding="utf-8")
    assert 'reasoning_level = normalize_reasoning_level(data.get("reasoning_level"))' in src
    # 브리지 어휘 경로도 부재면 None 이다(러너의 `medium`·`xhigh` 를 살리되 없는 값은 안 만든다).
    assert '_raw_level if _BRIDGE_LEVEL_RE.match(_raw_level) else None' in src


# ── 계정 기본값: 저장은 명시만, 사용은 대조 후 ──────────────────────────────────


def test_account_defaults_are_saved_from_explicit_picks_only():
    """계정 기본값도 **명시 선택만** 기록한다.

    폴백 값까지 저장하면 사용자가 고른 적 없는 값이 계정 기본값으로 굳고, 그 뒤의 모든 새
    대화가 그것으로 시작한다 — 질문 단위 오염(위)보다 오래 남는다.
    """
    src = _CONV.read_text(encoding="utf-8")
    assert "_defaults_model = model if model_explicit else None" in src, (
        "계정 기본값이 폴백된 모델까지 저장한다")
    assert "set_account_bridge_defaults(" in src


def test_account_defaults_never_widen_the_offered_list():
    """저장된 기본값은 **지금 신고된 목록 안에 있을 때만** 쓰인다.

    대조 없이 내려보내면 러너를 바꾼 사용자가 "고를 수 없는 것이 선택돼 있는" 화면을 보고,
    그 값으로 보낸 질문은 러너가 버린다.
    """
    src = _SYSTEM.read_text(encoding="utf-8")
    body = src[src.index("def get_api_vault_options("):]
    assert "account_bridge_model in _offered_values" in body, "기본 모델을 목록과 대조하지 않는다"
    # 등급은 **고른 모델의 런타임** 목록으로 본다 — claude 의 `xhigh` 는 codex 에 없다.
    assert "reasoning_by_runtime.get(_rt)" in body, "등급을 런타임과 무관하게 통과시킨다"


def test_defaults_lookup_failure_cannot_empty_the_catalog():
    """기본값 조회 실패가 **러너 목록까지** 비우지 않는다.

    바깥 except 로 흘리면 그쪽이 `runner_caps` 를 비워 선택기가 통째로 사라진다 — 시작점을
    정해 주는 편의 기능 하나가 목록 전체를 지우는 형태다(실제로 그렇게 짜여 있었다).
    """
    src = _SYSTEM.read_text(encoding="utf-8")
    body = src[src.index("def get_api_vault_options("):]
    # 앵커는 능력을 읽는 호출이다. caps-trust-gate(2026-09-01)에서 `account_runner_capabilities`
    # → `account_runner_profile` 로 바뀌었다 — 목록만이 아니라 **자격**(`caps_trusted`)까지
    # 같은 행에서 읽어야 「비었다」의 이유를 잃지 않기 때문이다.
    seg = body[body.index("account_runner_profile("):body.index("if not authenticated")]
    assert seg.count("try:") >= 1 and "account_bridge_model, account_bridge_effort = \"\", \"\"" in seg, (
        "기본값 조회가 자기 실패를 삼키지 않는다")


def test_account_default_columns_are_created_idempotently():
    """컬럼이 없는 배포에서도 부트스트랩이 만든다(그리고 두 번 돌아도 안전하다)."""
    src = _SCHEMA.read_text(encoding="utf-8")
    for col in ("BridgeDefaultModel", "BridgeDefaultEffort"):
        assert f"ALTER TABLE WebAccounts ADD COLUMN {col}" in src, f"{col} 이 스키마에 없다"


def test_defaults_writer_leaves_untouched_axes_alone():
    """한 축만 바꾼 요청이 다른 축의 기본값을 **지우지 않는다**.

    지우면 사용자는 모델을 고른 대가로 등급 기본값을 잃는다.
    """
    src = _STORE.read_text(encoding="utf-8")
    fn = src[src.index("def set_account_bridge_defaults("):]
    fn = fn[:fn.index("\ndef ")]
    assert "if model is not None:" in fn and "if effort is not None:" in fn, (
        "None 인 축을 건너뛰지 않는다 — 한쪽 갱신이 다른 쪽을 지운다")
    assert "if not sets:" in fn, "바꿀 것이 없는데도 UPDATE 를 던진다"
