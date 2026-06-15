"""권한 점진적 세분화(progressive disclosure) 회귀 테스트.

admin.js 의 `PERMISSION_DEPENDENCIES`(child -> 선행 parent) 맵을 파싱해
백엔드 `app.PERMISSION_DEFINITIONS` 의 권한 code 와 정합성을 검증하고,
가시성 알고리즘(JS 의 _applyPermissionDisclosure)을 Python 으로 포팅해
핵심 불변식(비파괴 / 마스터 게이트 / own→any 종속)을 검증한다.

검증 대상:
  M1  맵 파싱 — 25개 이상 엔트리, child/parent 모두 실제 권한 code.
  M2  비순환 — 모든 체인이 루트로 종료(self-loop / cycle 없음).
  M3  마스터 게이트 — account.read / role.read / audit.read.own /
        system_prompt.global.read 의 부모 = console.access. console.access 는
        키가 아님(루트).
  M4  own→any — `.any`(전체) 대화 권한은 대응 `.own`(내) 권한을 부모로 둔다.
  V1  비파괴 — 임의 checked 집합에서 checked 권한은 항상 visible(부여된 권한 미숨김).
  V2  마스터 게이트 OFF — checked=∅ 이면 관리 권한 section 의 비루트 권한 전부 hidden,
        console.access 만 visible(계정·역할 등 그룹이 통째 접힘).
  V3  중간 게이트 — console.access ON·account.read OFF → account.read visible,
        account.update hidden.
  V4  orphan 체인 — account.delete 만 checked → account.delete·account.read·
        console.access 전부 visible(조상 강제 노출), account.update hidden.

`make test`(agent 이미지, --no-deps)에서 DB 없이 정적 파싱으로 실행된다.
"""
from __future__ import annotations

import re
from pathlib import Path

import app

ADMIN_JS = Path(__file__).resolve().parents[1] / "src" / "static" / "admin.js"
STYLES_CSS = Path(__file__).resolve().parents[1] / "src" / "static" / "styles.css"
VALID_CODES = set(app.PERMISSION_CODES)


# ── 파서 ────────────────────────────────────────────────────────────────────────
def _parse_dependencies() -> dict[str, str]:
    text = ADMIN_JS.read_text(encoding="utf-8")
    m = re.search(r"const PERMISSION_DEPENDENCIES\s*=\s*\{(.*?)\n\};", text, re.DOTALL)
    assert m, "PERMISSION_DEPENDENCIES 블록을 admin.js 에서 찾지 못함"
    body = m.group(1)
    pairs = re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', body)
    deps: dict[str, str] = {}
    for child, parent in pairs:
        assert child not in deps, f"중복 child key: {child}"
        deps[child] = parent
    return deps


DEPS = _parse_dependencies()


# ── 가시성 알고리즘 포팅 (admin.js _applyPermissionDisclosure, checkbox mode) ─────
def compute_visibility(checked: set[str], all_codes: set[str]) -> dict[str, bool]:
    def is_explicit(c: str) -> bool:
        return c in checked

    def gate_satisfied(c: str) -> bool:
        return c in checked

    force: set[str] = set()
    for c in all_codes:
        if not is_explicit(c):
            continue
        cur: str | None = c
        seen: set[str] = set()
        while cur and cur not in seen:
            force.add(cur)
            seen.add(cur)
            cur = DEPS.get(cur)

    cache: dict[str, bool] = {}

    def visible(c: str) -> bool:
        if c in cache:
            return cache[c]
        cache[c] = False  # 사이클 방어
        parent = DEPS.get(c)
        if parent is None:
            v = True
        elif c in force:
            v = True
        elif parent not in all_codes:
            v = True
        else:
            v = gate_satisfied(parent) and visible(parent)
        cache[c] = v
        return v

    return {c: visible(c) for c in all_codes}


# ── 가시성 (override mode: gate=허용, explicit=허용·거부) ──────────────────────────
def compute_visibility_override(state: dict[str, str], all_codes: set[str]) -> dict[str, bool]:
    def is_explicit(c: str) -> bool:
        return state.get(c, "inherit") in ("allow", "deny")

    def gate_satisfied(c: str) -> bool:
        return state.get(c, "inherit") == "allow"

    force: set[str] = set()
    for c in all_codes:
        if not is_explicit(c):
            continue
        cur: str | None = c
        seen: set[str] = set()
        while cur and cur not in seen:
            force.add(cur)
            seen.add(cur)
            cur = DEPS.get(cur)

    cache: dict[str, bool] = {}

    def visible(c: str) -> bool:
        if c in cache:
            return cache[c]
        cache[c] = False
        parent = DEPS.get(c)
        if parent is None:
            v = True
        elif c in force:
            v = True
        elif parent not in all_codes:
            v = True
        else:
            v = gate_satisfied(parent) and visible(parent)
        cache[c] = v
        return v

    return {c: visible(c) for c in all_codes}


# ── M: 맵 정합 ──────────────────────────────────────────────────────────────────
def test_m1_map_parsed_and_codes_valid():
    assert len(DEPS) >= 25, f"엔트리 부족: {len(DEPS)}"
    for child, parent in DEPS.items():
        assert child in VALID_CODES, f"child 가 실제 권한 code 아님: {child}"
        assert parent in VALID_CODES, f"parent 가 실제 권한 code 아님: {parent}"
        assert child != parent, f"self-loop: {child}"


def test_m2_acyclic_terminates_at_root():
    for start in DEPS:
        cur: str | None = start
        seen: set[str] = set()
        while cur is not None:
            assert cur not in seen, f"cycle 감지: {start} 체인에 {cur} 재방문"
            seen.add(cur)
            cur = DEPS.get(cur)
        # 루트(DEPS 에 없는 code)로 종료됨


def test_m3_master_gate_console_access():
    for base in ("account.read", "role.read", "audit.read.own", "system_prompt.global.read"):
        assert DEPS.get(base) == "console.access", f"{base} 의 부모가 console.access 아님"
    assert "console.access" not in DEPS, "console.access 는 루트여야 함(키가 되면 안 됨)"


def test_m4_own_to_any_dependency():
    any_codes = [c for c in VALID_CODES if c.startswith("conversation.") and c.endswith(".any")]
    assert any_codes, "conversation .any 권한이 카탈로그에 없음"
    for code in any_codes:
        own = code[: -len(".any")] + ".own"
        if own in VALID_CODES:  # own 짝이 있는 경우만 종속 강제
            assert DEPS.get(code) == own, f"{code} 의 부모가 {own} 아님 (실제 {DEPS.get(code)})"


# ── V: 가시성 불변식 ────────────────────────────────────────────────────────────
def test_v1_non_destructive_checked_always_visible():
    all_codes = set(VALID_CODES)
    # 모든 단일 체크 — 부여된 권한은 항상 visible
    for code in all_codes:
        vis = compute_visibility({code}, all_codes)
        assert vis[code], f"단일 체크된 {code} 가 숨겨짐 — 비파괴 위반"
    # 대표 조합 몇 개
    for combo in (
        {"account.delete", "role.permission.manage"},
        {"audit.purge"},
        {"conversation.read.any"},
        {"system_prompt.global.write"},
        all_codes,  # 전부 체크
    ):
        vis = compute_visibility(combo, all_codes)
        for code in combo:
            assert vis[code], f"체크된 {code} 가 숨겨짐(조합 {sorted(combo)[:3]}…) — 비파괴 위반"


def test_v2_master_gate_off_collapses_manage_section():
    all_codes = set(VALID_CODES)
    vis = compute_visibility(set(), all_codes)
    assert vis["console.access"], "console.access(루트)는 항상 visible"
    # 관리 권한 비루트 권한은 전부 hidden
    for code in (
        "console.manage", "console.usage.read", "insight.reset",
        "account.read", "account.update", "account.delete",
        "role.read", "role.create", "role.permission.manage",
        "audit.read.own", "audit.read.any", "audit.purge",
        "system_prompt.global.read", "system_prompt.global.write",
    ):
        assert not vis[code], f"게이트 OFF 인데 {code} 가 보임"
    # 운영 권한 루트(.own / create 등)는 게이트 없이 visible
    for code in ("conversation.create", "conversation.list.own", "conversation.read.own", "product.manage"):
        assert vis[code], f"운영 루트 {code} 가 숨겨짐"
    # 운영 .any 는 .own 게이트 OFF 라 hidden
    assert not vis["conversation.read.any"], "read.own OFF 인데 read.any 가 보임"


def test_v3_intermediate_gate_account_read():
    all_codes = set(VALID_CODES)
    vis = compute_visibility({"console.access"}, all_codes)
    assert vis["account.read"], "console.access ON 이면 account.read(그룹 base) 노출"
    assert not vis["account.update"], "account.read OFF 인데 account.update 가 보임"
    assert vis["role.read"], "console.access ON 이면 role.read 노출"


def test_v4_orphan_chain_force_visible():
    all_codes = set(VALID_CODES)
    # account.delete 만 부여 — 조상 체인 전부 강제 노출, 형제는 숨김
    vis = compute_visibility({"account.delete"}, all_codes)
    assert vis["account.delete"], "부여된 account.delete 가 숨겨짐"
    assert vis["account.read"], "조상 account.read 가 숨겨짐(orphan 체인 노출 실패)"
    assert vis["console.access"], "조상 console.access 가 숨겨짐"
    assert not vis["account.update"], "형제 account.update 는 게이트 OFF 라 숨겨져야 함"


# ── V(override): 계정 override 모드 가시성 불변식 ─────────────────────────────────
def test_v5_override_non_destructive_explicit_always_visible():
    all_codes = set(VALID_CODES)
    # 단일 허용 / 단일 거부 — 명시 설정된 override 는 항상 visible(비파괴)
    for code in all_codes:
        for verb in ("allow", "deny"):
            vis = compute_visibility_override({code: verb}, all_codes)
            assert vis[code], f"override {verb} 인 {code} 가 숨겨짐 — 비파괴 위반"


def test_v6_override_gate_allow_reveals_children():
    all_codes = set(VALID_CODES)
    # 게이트 inherit(기본) — inherit 자식 접힘, 명시 거부 자식은 노출(비파괴)
    vis = compute_visibility_override({"account.delete": "deny"}, all_codes)
    assert vis["account.delete"], "거부 override account.delete 가 숨겨짐"
    assert vis["account.read"], "조상 account.read 가 숨겨짐"
    assert vis["console.access"], "조상 console.access 가 숨겨짐"
    assert not vis["account.update"], "inherit 인 account.update 는 접혀야 함"
    # 게이트 허용 → 그 자식(base)이 노출. account.read 허용 → account.update 노출 대상
    vis2 = compute_visibility_override({"console.access": "allow", "account.read": "allow"}, all_codes)
    assert vis2["account.read"], "console.access 허용 시 account.read 노출"
    assert vis2["account.update"], "account.read 허용 시 account.update 노출"


# ── C: CSS 계약 — [hidden] 강제 display:none (TASK-0258 핫픽스 회귀 가드) ──────────
def test_c1_hidden_rows_force_display_none():
    """`.permission-toggle-card{display:flex}` 등 author display 규칙이 UA `[hidden]{display:none}`
    를 override 해 JS 의 `el.hidden=true` 가 무력화되던 버그(PB-0008 실브라우저 검출, jsdom 미검출)의
    회귀 가드. styles.css 가 disclosure 숨김 대상에 display:none !important 를 강제하는지 검증한다."""
    css = STYLES_CSS.read_text(encoding="utf-8")
    # `[data-perm-code][hidden]` 셀렉터 + 같은 규칙 블록에 display:none !important 가 있어야 한다.
    m = re.search(
        r"\[data-perm-code\]\[hidden\][^{]*\{[^}]*display\s*:\s*none\s*!important",
        css,
        re.DOTALL,
    )
    assert m, "styles.css 에 `[data-perm-code][hidden] { display: none !important }` 규칙 부재 — hidden row 가 실브라우저에서 안 숨겨짐(TASK-0258 회귀)"
    # section/group 도 동일 강제 규칙에 포함돼야 한다.
    assert ".permission-group[hidden]" in css, ".permission-group[hidden] 강제 규칙 부재"
    assert ".permission-section[hidden]" in css, ".permission-section[hidden] 강제 규칙 부재"
