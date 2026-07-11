"""TASK-0300 (REQ-0287, 인가 §12.3) — privilege escalation 방지 backend 가드 순수 단위 테스트.

관리 콘솔 > 계정/역할 권한 편집에서 편집 주체(admin)가 **본인이 보유하지 않은 권한**을 부여·설정
하지 못하게 하는 `_enforce_override_self_scope` / `_enforce_role_permission_self_scope` 의 로직을
검증한다.

app.py 는 FastAPI / modules.* 의존성 때문에 bare import 가 안 되므로, `ast` 로 해당 helper 의
**실제 소스 본문**만 추출해 최소 stub(`_account_permissions`) 위에서 exec 한 뒤 직접 호출한다.
즉 re-implementation 이 아니라 정본 코드를 그대로 실행한다 — 로직 drift 시 본 테스트가 깨진다.

실행:
    python3 unit/feature-0003-agent-web-ui/tests/test_perm_self_scope.py
(pytest 도 가능: 함수명 test_* 자동 수집.)
"""
from __future__ import annotations

import ast
import os
import sys
from typing import Any, Iterable

# ITEM-10 p14: _enforce_* 2종은 routers/(admin_accounts·admin_roles) 로 이동 — 다중 파일 스캔.
_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
_SRC_FILES = (
    os.path.join(_SRC_DIR, "app.py"),
    os.path.join(_SRC_DIR, "routers", "admin_accounts.py"),
    os.path.join(_SRC_DIR, "routers", "admin_roles.py"),
)
_TARGETS = (
    "_actor_editable_permission_codes",
    "_enforce_override_self_scope",
    "_enforce_role_permission_self_scope",
    "_role_grant_excess_for_actor",
)


class _AppProxy:
    """이동된 helper 의 `app.X` 동적 참조를 테스트 ns 로 위임하는 최소 shim."""

    def __init__(self, ns: dict[str, Any]) -> None:
        self._ns = ns

    def __getattr__(self, name: str) -> Any:
        try:
            return self._ns[name]
        except KeyError:
            raise AttributeError(name) from None


def _load_targets() -> dict[str, Any]:
    """src 에서 대상 helper 함수의 실제 소스를 추출해 최소 namespace 에서 exec."""
    wanted: dict[str, ast.FunctionDef] = {}
    for path in _SRC_FILES:
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in _TARGETS:
                wanted.setdefault(node.name, node)
    missing = [name for name in _TARGETS if name not in wanted]
    if missing:
        raise AssertionError(f"src 에서 helper 를 찾지 못함: {missing}")
    module = ast.Module(body=[wanted[name] for name in _TARGETS], type_ignores=[])
    ast.fix_missing_locations(module)
    # `_account_permissions` 는 cached `permissions` map 을 그대로 반환 (app.py cached branch).
    ns: dict[str, Any] = {
        "Any": Any,
        "Iterable": Iterable,
        "_account_permissions": lambda account: dict((account or {}).get("permissions") or {}),
    }
    ns["app"] = _AppProxy(ns)
    exec(compile(module, _SRC_FILES[0], "exec"), ns)  # noqa: S102 — 정본 소스 실행(테스트 격리)
    return ns


_NS = _load_targets()
_editable = _NS["_actor_editable_permission_codes"]
_enforce_override = _NS["_enforce_override_self_scope"]
_enforce_role = _NS["_enforce_role_permission_self_scope"]
_role_excess = _NS["_role_grant_excess_for_actor"]


def _actor(*held: str) -> dict[str, Any]:
    """held 권한은 True, 비-held 잡음은 False 인 effective permission map 을 가진 actor."""
    perms = {code: True for code in held}
    perms.update({"_noise.denied": False})  # False 값은 editable 에서 제외되어야 함
    return {"id": 1, "permissions": perms}


# ── _actor_editable_permission_codes ────────────────────────────────────────

def test_editable_excludes_false_values():
    assert _editable(_actor("a", "b")) == {"a", "b"}
    assert _editable({"permissions": {}}) == set()
    assert _editable(None) == set()


# ── _enforce_override_self_scope ─────────────────────────────────────────────

def test_override_allow_within_scope_ok():
    merged = _enforce_override(_actor("a", "b"), {"a": "allow"}, {})
    assert merged == {"a": "allow"}


def test_override_allow_outside_scope_blocked():
    try:
        _enforce_override(_actor("a"), {"b": "allow"}, {})
    except ValueError as exc:
        assert "b" in str(exc)
    else:
        raise AssertionError("미보유 권한 allow 가 차단되지 않음 (escalation)")


def test_override_deny_outside_scope_also_blocked():
    # 요구사항: 미보유 권한은 allow·deny 모두 불가(완전 숨김·차단).
    try:
        _enforce_override(_actor("a"), {"b": "deny"}, {})
    except ValueError as exc:
        assert "b" in str(exc)
    else:
        raise AssertionError("미보유 권한 deny 가 차단되지 않음")


def test_override_preserves_out_of_scope_existing():
    # c 는 actor 가 보유하지 않은 권한이고 target 에 이미 allow override 존재 → 보존돼야 함.
    merged = _enforce_override(_actor("a"), {"a": "deny"}, {"c": "allow"})
    assert merged == {"c": "allow", "a": "deny"}


def test_override_in_scope_inherit_removes():
    # a 는 보유 권한. 기존 allow 였으나 이번 제출에서 빠짐(inherit) → 제거. c(범위 밖)는 보존.
    merged = _enforce_override(_actor("a"), {}, {"a": "allow", "c": "deny"})
    assert merged == {"c": "deny"}


def test_override_empty_actor_blocks_any_set():
    try:
        _enforce_override(_actor(), {"a": "allow"}, {})
    except ValueError:
        pass
    else:
        raise AssertionError("무권한 actor 가 권한을 설정할 수 있었음")


# ── _enforce_role_permission_self_scope ──────────────────────────────────────

def test_role_add_within_scope_ok():
    merged = _enforce_role(_actor("a", "b"), {"a", "b"}, {"a"})
    assert merged == {"a", "b"}


def test_role_add_outside_scope_blocked():
    try:
        _enforce_role(_actor("a"), {"a", "x"}, {"a"})
    except ValueError as exc:
        assert "x" in str(exc)
    else:
        raise AssertionError("미보유 권한을 역할에 신규 부여 차단 실패 (escalation)")


def test_role_preserves_out_of_scope_existing():
    # hi 는 actor 미보유지만 역할에 이미 부여돼 있음 → 제출에서 빠져도 보존(임의 회수 불가).
    merged = _enforce_role(_actor("a"), set(), {"a", "hi"})
    assert merged == {"hi"}


def test_role_remove_in_scope_allowed():
    # a, b 모두 보유. 현재 {a,b}, 제출 {a} → b 제거 허용(본인 보유 권한이므로).
    merged = _enforce_role(_actor("a", "b"), {"a"}, {"a", "b"})
    assert merged == {"a"}


def test_role_create_outside_scope_blocked():
    # 신규 역할 생성(admin_create_role): current=빈 집합 → 부여 권한 전부 self-scope 검사.
    try:
        _enforce_role(_actor("a"), {"a", "x"}, set())
    except ValueError as exc:
        assert "x" in str(exc)
    else:
        raise AssertionError("신규 역할 생성 시 미보유 권한 부여가 차단되지 않음")


def test_role_create_within_scope_ok():
    merged = _enforce_role(_actor("a", "b"), {"a", "b"}, set())
    assert merged == {"a", "b"}


def test_role_existing_unheld_kept_even_when_resubmitted():
    # hi 가 current 에 있으면 submitted 에 다시 들어와도 added 가 아니므로 허용 + 보존.
    merged = _enforce_role(_actor("a"), {"a", "hi"}, {"a", "hi"})
    assert merged == {"a", "hi"}


# ── _role_grant_excess_for_actor (역할 배정 escalation 가드) ──────────────────

def test_role_assign_within_scope_no_excess():
    # 배정 역할 권한 {a,b} ⊆ actor {a,b,c} → 초과 0 → 배정 가능.
    assert _role_excess(_actor("a", "b", "c"), {"a", "b"}) == []


def test_role_assign_exceeds_blocked():
    # 배정 역할이 actor 미보유 x 를 가짐 → 초과 [x] → 배정 차단.
    assert _role_excess(_actor("a"), {"a", "x"}) == ["x"]


def test_role_assign_empty_role_ok():
    assert _role_excess(_actor("a"), set()) == []
    assert _role_excess(_actor("a"), None) == []


def test_role_assign_empty_actor_blocks_nonempty_role():
    assert _role_excess(_actor(), {"a"}) == ["a"]


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL {fn.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
