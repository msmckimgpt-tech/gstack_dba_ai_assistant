"""provider 요청 **본문** 위생 — 전송 계층 파라미터를 body 에 싣지 않는다.

conv-audit FR-body-timeout-poisons-provider-request(2026-08-26, 라이브 장애):
`agent_core._call_llm` 이 `extra_body={"timeout": …}` 로 per-attempt 상한을 요청 **본문**에
실었다. 구 게이트웨이는 이 필드를 무시해 무해했지만, litellm 1.98.0 은 요청에 timeout 이
있으면 내부 마커 `client_side_timeout` 을 심고(클라이언트가 짧은 timeout 으로 deployment
cooldown 을 유발하는 것을 막는 방어) 그 마커가 Anthropic 요청 body 에서 제거되지 않은 채
전달돼 **400 `client_side_timeout: Extra inputs are not permitted`** 가 된다. 1차와 폴백이
같은 body 를 쓰므로 전 경로가 죽어 대화가 전면 실패했다.

`timeout` 은 **전송 계층** 값이다 — OpenAI SDK 의 request option(`create(timeout=…)`)이나
클라이언트 생성 인자로 주는 것이 정상이고, `extra_body`(= JSON 본문)에 넣으면 provider 가
모르는 필드가 되거나 게이트웨이 방어 로직을 건드린다. 이 스위트는 그 구분을 구조적으로 잠근다.

정직 표기: 헤더 전환(`x-litellm-timeout`)은 해법이 아니다 — litellm 은 body 든 헤더든 같은
마커를 심는다. 요청에 timeout 을 싣지 않는 것이 유일한 회피다.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
_WEB_SRC = _SRC.parents[1] / "feature-0003-agent-web-ui" / "src"

# provider 요청을 조립하는 파일 전수(관문 스위트 `_WIRED_FILES` 와 같은 집합).
_REQUEST_BUILDERS = [
    _SRC / "agent_core.py",
    _SRC / "modules" / "llm.py",
    _SRC / "modules" / "llm_provider_health.py",
    _SRC / "modules" / "redteam.py",
    _WEB_SRC / "routers" / "_prompt_context.py",
    _WEB_SRC / "routers" / "admin_metadata.py",
]

# 요청 **본문**에 실리면 안 되는 전송 계층 키. provider 스펙 밖 필드이거나 게이트웨이가
# 가로채 내부 마커로 바꾸는 것들이다.
_TRANSPORT_KEYS = {"timeout", "request_timeout", "stream_timeout", "client_side_timeout"}


def _existing(paths):
    return [p for p in paths if p.exists()]


def _dicts_assigned_to_extra_body(tree: ast.AST) -> list[tuple[int, ast.Dict]]:
    """`extra_body` 로 흘러가는 dict 리터럴을 모은다.

    네 형태를 본다(적대 리뷰 2026-08-26 지적으로 뒤 두 개를 추가):
      · `extra_body={...}` / `"extra_body": {...}`                  → 인라인
      · `x = {...}` 뒤 `kwargs["extra_body"] = x` / `extra_body=x`  → 변수 경유
      · `kwargs["extra_body"] = {...}`                              → 첨자 대입에 리터럴 직접
      · `_extra_body.update({...})`                                 → 사후 병합

    ⚠ 한계(정직 표기): 정적 검사라 값이 여러 함수를 건너 흐르거나 동적으로 조립되는 형태까지
    잡지는 못한다. 실제 재발은 위 네 형태 중 하나로 나타났고, 최종 안전망은 라이브 검증이다.
    """
    found: list[tuple[int, ast.Dict]] = []
    # 인라인 형태
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            for kw in n.keywords:
                if kw.arg == "extra_body" and isinstance(kw.value, ast.Dict):
                    found.append((kw.value.lineno, kw.value))
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if isinstance(k, ast.Constant) and k.value == "extra_body" and isinstance(v, ast.Dict):
                    found.append((v.lineno, v))
    # 첨자 대입에 dict 리터럴을 **직접** 넣는 형태: kwargs["extra_body"] = {...}
    #   (적대 리뷰 2026-08-26 지적 — 초판은 우변이 Name 인 경우만 봐서 이 형태를 놓쳤다.)
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                        and t.slice.value == "extra_body" and isinstance(n.value, ast.Dict)):
                    found.append((n.value.lineno, n.value))
    # 변수 경유: extra_body 로 쓰이는 이름을 모은 뒤, 그 이름에 대입된 dict 리터럴을 수집
    names: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            for kw in n.keywords:
                if kw.arg == "extra_body" and isinstance(kw.value, ast.Name):
                    names.add(kw.value.id)
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                        and t.slice.value == "extra_body" and isinstance(n.value, ast.Name)):
                    names.add(n.value.id)
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if (isinstance(k, ast.Constant) and k.value == "extra_body"
                        and isinstance(v, ast.Name)):
                    names.add(v.id)
    # 변수 경유 + `.update({...})` 로 사후 병합하는 형태도 같은 dict 로 취급한다.
    if names:
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "update" and isinstance(n.func.value, ast.Name)
                    and n.func.value.id in names | {"extra_body", "_extra_body"}):
                for a in n.args:
                    if isinstance(a, ast.Dict):
                        found.append((a.lineno, a))
    if names:
        for n in ast.walk(tree):
            targets = []
            if isinstance(n, ast.Assign):
                targets = n.targets
            elif isinstance(n, ast.AnnAssign) and n.value is not None:
                targets = [n.target]
            value = getattr(n, "value", None)
            if isinstance(value, ast.Dict):
                for t in targets:
                    if isinstance(t, ast.Name) and t.id in names:
                        found.append((value.lineno, value))
    return found


@pytest.mark.parametrize("path", _existing(_REQUEST_BUILDERS), ids=lambda p: p.name)
def test_extra_body_never_carries_transport_keys(path: pathlib.Path):
    """`extra_body` dict 리터럴에 전송 계층 키가 없어야 한다 — 있으면 provider 400 을 부른다."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for lineno, d in _dicts_assigned_to_extra_body(tree):
        for k in d.keys:
            if isinstance(k, ast.Constant) and k.value in _TRANSPORT_KEYS:
                offenders.append(f"L{lineno}:{k.value}")
    assert not offenders, (
        f"{path.name}: extra_body 에 전송 계층 키 {sorted(set(offenders))} — 요청 본문이 아니라 "
        "request option(create(timeout=…))이나 클라이언트 생성 인자로 전달하라. "
        "본문에 실으면 게이트웨이가 client_side_timeout 마커를 심어 provider 400 이 된다."
    )


@pytest.mark.parametrize("path", _existing(_REQUEST_BUILDERS), ids=lambda p: p.name)
def test_no_subscript_assignment_of_transport_keys_into_extra_body(path: pathlib.Path):
    """`_extra_body["timeout"] = …` 같은 사후 주입도 막는다(리터럴 검사만으로는 뚫린다)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {"extra_body", "_extra_body"}
    offenders: list[str] = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Assign):
            continue
        for t in n.targets:
            if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                    and t.value.id in names and isinstance(t.slice, ast.Constant)
                    and t.slice.value in _TRANSPORT_KEYS):
                offenders.append(f"L{n.lineno}:{t.slice.value}")
    assert not offenders, (
        f"{path.name}: extra_body 에 전송 계층 키 사후 주입 {sorted(set(offenders))}"
    )
