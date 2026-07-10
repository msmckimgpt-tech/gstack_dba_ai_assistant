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
# TASK-0264: forceVisible 제거 — 게이트 체인이 충족돼야만 노출(부여 여부 무관). 부여된 권한의
# 도달성은 _refreshGroupDisclosure 의 그룹 비숨김 + "더 보기 · N개 부여됨" (DOM 계층, 본 포팅 범위 밖).
def compute_visibility(checked: set[str], all_codes: set[str]) -> dict[str, bool]:
    def gate_satisfied(c: str) -> bool:
        return c in checked

    cache: dict[str, bool] = {}

    def visible(c: str) -> bool:
        if c in cache:
            return cache[c]
        cache[c] = False  # 사이클 방어
        parent = DEPS.get(c)
        if parent is None:
            v = True
        elif parent not in all_codes:
            v = True
        else:
            v = gate_satisfied(parent) and visible(parent)
        cache[c] = v
        return v

    return {c: visible(c) for c in all_codes}


# ── 가시성 (override mode) — TASK-0264 forceVisible 제거 + TASK-0270 상속(허용) 게이트 ──
#   gate_satisfied = "허용" 또는 ("상속"이면서 역할이 그 권한을 부여 = inherited 에 포함 → 상속(허용)).
def compute_visibility_override(
    state: dict[str, str], all_codes: set[str], inherited: set[str] | None = None
) -> dict[str, bool]:
    inh = inherited or set()

    def gate_satisfied(c: str) -> bool:
        s = state.get(c, "inherit")
        return s == "allow" or (s == "inherit" and c in inh)

    cache: dict[str, bool] = {}

    def visible(c: str) -> bool:
        if c in cache:
            return cache[c]
        cache[c] = False
        parent = DEPS.get(c)
        if parent is None:
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


def test_m4_conversation_list_gate():
    # TASK-0269: 대화 own/any 그룹 분리 + "목록 조회" 게이트.
    #   전체 대화(.any) 동작 권한은 conversation.list.any 를, 내 대화 동작 권한은 conversation.list.own 을 부모로 둔다.
    #   create / list.own / list.any 는 루트(부모 없음).
    for root in ("conversation.create", "conversation.list.own", "conversation.list.any"):
        assert DEPS.get(root) is None, f"{root} 는 루트(부모 없음)여야 함 (실제 {DEPS.get(root)})"
    for code in VALID_CODES:
        if not code.startswith("conversation."):
            continue
        if code in ("conversation.create", "conversation.list.own", "conversation.list.any"):
            continue
        gate = "conversation.list.any" if code.endswith(".any") else "conversation.list.own"
        assert DEPS.get(code) == gate, f"{code} 의 게이트가 {gate} 아님 (실제 {DEPS.get(code)})"


# ── V: 가시성 불변식 (TASK-0264 — 게이트 체인 충족 시에만 노출, 부여 무관) ──────────
def test_v1_visible_iff_gate_chain_satisfied():
    all_codes = set(VALID_CODES)
    # 자기 전 조상 체인을 모두 체크하면 노출(게이트 충족).
    for code in all_codes:
        chain: set[str] = set()
        cur: str | None = DEPS.get(code)
        while cur is not None:
            chain.add(cur)
            cur = DEPS.get(cur)
        vis = compute_visibility(chain, all_codes)  # code 자신은 체크 안 해도, 조상 체인만 충족하면 노출
        assert vis[code], f"게이트 체인 충족인데 {code} 가 숨겨짐"
    # 루트(부모 없음)는 항상 노출.
    roots = [c for c in all_codes if DEPS.get(c) is None]
    vis0 = compute_visibility(set(), all_codes)
    for code in roots:
        assert vis0[code], f"루트 {code} 가 빈 상태에서 숨겨짐"
    # 게이트 미충족이면 *체크된* 세부 권한도 숨김(forceVisible 제거 — 도달성은 DOM 그룹/더보기 계층 담당).
    vis1 = compute_visibility({"account.delete"}, all_codes)
    assert not vis1["account.delete"], "게이트(account.read·console.access) OFF 인데 체크된 account.delete 가 노출됨 — 단순화 위반"


def test_v2_master_gate_off_collapses_manage_section():
    all_codes = set(VALID_CODES)
    vis = compute_visibility(set(), all_codes)
    assert vis["console.access"], "console.access(루트)는 항상 visible"
    # 관리 권한 비루트 권한은 전부 hidden
    # TASK-0288: datasource.read/manage·product.read/manage·system_prompt.manage.role.any 추가 —
    #   데이터소스/제품 관리 그룹이 관리 권한 section 으로 이동, console.access 마스터 게이트 하위로 종속.
    for code in (
        "console.manage", "console.usage.read", "console.aiops.read", "insight.reset",
        "account.read", "account.update", "account.delete",
        "role.read", "role.create", "role.permission.manage",
        "datasource.read", "datasource.manage",
        "product.read", "product.manage", "system_prompt.manage.role.any",
        "audit.read.own", "audit.read.any", "audit.purge",
        "system_prompt.global.read", "system_prompt.global.write",
    ):
        assert not vis[code], f"게이트 OFF 인데 {code} 가 보임"
    # 운영 권한 루트(TASK-0269: create / list.own / list.any)는 게이트 없이 visible.
    # TASK-0288: product.manage 는 운영 루트가 아님 — 제품 관리(product.read 게이트, console.access 하위)로 이동.
    for code in ("conversation.create", "conversation.list.own", "conversation.list.any"):
        assert vis[code], f"운영 루트 {code} 가 숨겨짐"
    # 동작 권한은 "목록 조회" 게이트 OFF 라 hidden (read.own→list.own, read.any→list.any)
    assert not vis["conversation.read.own"], "list.own OFF 인데 read.own 가 보임"
    assert not vis["conversation.read.any"], "list.any OFF 인데 read.any 가 보임"


def test_v3_intermediate_gate_account_read():
    all_codes = set(VALID_CODES)
    vis = compute_visibility({"console.access"}, all_codes)
    assert vis["account.read"], "console.access ON 이면 account.read(그룹 base) 노출"
    assert not vis["account.update"], "account.read OFF 인데 account.update 가 보임"
    assert vis["role.read"], "console.access ON 이면 role.read 노출"


def test_v4_granted_detail_collapsed_when_gate_off():
    all_codes = set(VALID_CODES)
    # account.delete 만 부여(게이트 OFF) — 부여됐어도 게이트 미충족이라 숨김(TASK-0264 핵심).
    vis = compute_visibility({"account.delete"}, all_codes)
    assert not vis["account.delete"], "게이트 OFF 인데 부여된 account.delete 가 노출됨 — 단순화 위반"
    assert not vis["account.read"], "게이트(console.access) OFF 라 account.read 도 숨김"
    assert vis["console.access"], "console.access(루트)는 항상 노출"
    assert not vis["account.update"], "형제 account.update 도 게이트 OFF 라 숨김"
    # 게이트 체인을 충족하면 도달(노출).
    vis2 = compute_visibility({"console.access", "account.read", "account.delete"}, all_codes)
    assert vis2["account.delete"], "게이트 체인 충족 시 account.delete 노출"
    assert vis2["account.read"] and vis2["console.access"], "충족된 게이트들도 노출"


# ── V(override): 계정 override 모드 가시성 불변식 (TASK-0264) ──────────────────────
def test_v5_override_root_visible_detail_gate_off_hidden():
    all_codes = set(VALID_CODES)
    roots = [c for c in all_codes if DEPS.get(c) is None]
    # 루트(부모 없음)는 빈 상태에서도 노출.
    vis0 = compute_visibility_override({}, all_codes)
    for code in roots:
        assert vis0[code], f"override 루트 {code} 가 숨겨짐"
    # 게이트 미충족이면 명시 허용·거부한 세부 권한도 숨김(forceVisible 제거).
    for verb in ("allow", "deny"):
        vis = compute_visibility_override({"account.delete": verb}, all_codes)
        assert not vis["account.delete"], f"게이트 OFF 인데 override {verb} account.delete 노출됨"


def test_v6_override_gate_allow_reveals_children():
    all_codes = set(VALID_CODES)
    # 게이트 inherit/거부(기본) — 세부 자식 접힘(허용 아님).
    vis = compute_visibility_override({"account.delete": "deny"}, all_codes)
    assert not vis["account.delete"], "게이트 미충족(inherit)인데 deny account.delete 노출됨"
    assert not vis["account.read"], "게이트(console.access) 미허용이라 account.read 도 접힘"
    assert vis["console.access"], "console.access(루트)는 노출"
    # 게이트 허용 체인 → 자식 노출. console.access·account.read 허용 → account.update 노출.
    vis2 = compute_visibility_override({"console.access": "allow", "account.read": "allow"}, all_codes)
    assert vis2["account.read"], "console.access 허용 시 account.read 노출"
    assert vis2["account.update"], "account.read 허용 시 account.update 노출"
    # 게이트 거부는 자식을 열지 않음(허용만).
    vis3 = compute_visibility_override({"console.access": "allow", "account.read": "deny"}, all_codes)
    assert not vis3["account.update"], "account.read=거부 면 account.update 안 열림"


def test_v7_override_inherit_allow_gate_reveals_children():
    # TASK-0270: 계정 override 게이트는 "허용" 뿐 아니라 "상속(허용)"(상속 + 역할이 부여)에도 펼친다.
    all_codes = set(VALID_CODES)
    # console.access·account.read 가 override "상속"이고 역할이 둘 다 부여(inherited) → account.update 노출.
    inherited = {"console.access", "account.read"}
    vis = compute_visibility_override({}, all_codes, inherited)  # 모든 값 기본 "상속"
    assert vis["account.read"], "console.access 상속(허용) 시 account.read 노출"
    assert vis["account.update"], "account.read 상속(허용) 시 account.update 노출"
    # 역할이 부여 안 함(inherited 비어있음) → 상속(거부) → 안 펼침.
    vis_none = compute_visibility_override({}, all_codes, set())
    assert not vis_none["account.read"], "역할 미부여 상속(거부)면 account.read 안 노출"
    assert not vis_none["account.update"], "역할 미부여면 account.update 안 노출"
    # 명시 "거부"는 역할이 부여(inherited)해도 게이트 OFF — 거부가 상속을 이긴다.
    vis_deny = compute_visibility_override({"account.read": "deny"}, all_codes, {"console.access", "account.read"})
    assert not vis_deny["account.update"], "account.read=거부면 역할이 부여해도 account.update 안 열림"
    # "허용"은 inherited 무관하게 펼침.
    vis_allow = compute_visibility_override(
        {"console.access": "allow", "account.read": "allow"}, all_codes, set()
    )
    assert vis_allow["account.update"], "허용 게이트는 inherited 무관 펼침"


# ── C: CSS 계약 — [hidden] 강제 display:none (TASK-0258/0264 핫픽스 회귀 가드) ──────
def test_c1_hidden_rows_force_display_none():
    """`.permission-toggle-card{display:flex}` / `.override-field`(.field{display:flex}) 등 author display
    규칙이 UA `[hidden]{display:none}` 를 override 해 JS 의 `el.hidden=true` 가 무력화되던 버그(PB-0008
    실브라우저 검출, jsdom 미검출)의 회귀 가드. styles.css 가 disclosure 숨김 대상에 display:none !important
    를 강제하는지 + 셀렉터가 컨테이너(.permission-grid/.override-grid) 무관(unscoped)인지 검증한다."""
    css = STYLES_CSS.read_text(encoding="utf-8")
    # `[data-perm-code][hidden]` 셀렉터 + 같은 규칙 블록에 display:none !important 가 있어야 한다.
    m = re.search(
        r"([^{}]*\[data-perm-code\]\[hidden\][^{]*)\{([^}]*display\s*:\s*none\s*!important[^}]*)\}",
        css,
        re.DOTALL,
    )
    assert m, "styles.css 에 `[data-perm-code][hidden] { display: none !important }` 규칙 부재 — hidden row 가 실브라우저에서 안 숨겨짐(TASK-0258 회귀)"
    # 셀렉터 목록 중 `[data-perm-code][hidden]` 가 컨테이너 prefix 없이(unscoped) 존재해야 한다 —
    # `.permission-grid` 한정이면 계정 override 편집기(.override-grid)를 놓침(TASK-0264 회귀).
    selectors = [s.strip() for s in m.group(1).split(",")]
    assert "[data-perm-code][hidden]" in selectors, (
        f"`[data-perm-code][hidden]` 가 컨테이너 무관 셀렉터로 존재하지 않음(스코프됨: {selectors}) — "
        "override-grid 행이 실브라우저에서 안 숨겨짐(TASK-0264 회귀)"
    )
    # section/group 도 동일 강제 규칙에 포함돼야 한다.
    assert ".permission-group[hidden]" in css, ".permission-group[hidden] 강제 규칙 부재"
    assert ".permission-section[hidden]" in css, ".permission-section[hidden] 강제 규칙 부재"


# ── T: 트리 정렬 (TASK-0267 — _orderItemsAsTree 포팅) ──────────────────────────────
def _order_items_as_tree(group_codes: list[str]) -> list[tuple[str, int]]:
    """admin.js _orderItemsAsTree 포팅 — 그룹 내 코드를 (code, depth) 트리 DFS 순서로."""
    in_group = set(group_codes)
    children: dict[str, list[str]] = {}
    roots: list[str] = []
    for code in group_codes:  # 카탈로그 순서 유지
        parent = DEPS.get(code)
        if parent and parent in in_group:
            children.setdefault(parent, []).append(code)
        else:
            roots.append(code)  # 부모 없음 / 부모가 다른 그룹 → 그룹 내 루트(depth 0)
    out: list[tuple[str, int]] = []
    seen: set[str] = set()

    def visit(code: str, depth: int) -> None:
        if code in seen:
            return
        seen.add(code)
        out.append((code, depth))
        for ch in children.get(code, []):
            visit(ch, depth + 1)

    for r in roots:
        visit(r, 0)
    for code in group_codes:  # 누락 안전망
        if code not in seen:
            seen.add(code)
            out.append((code, 0))
    return out


def _group_of(code: str) -> str:
    return app.PERMISSION_DEFINITION_MAP[code]["group"]


def test_t1_tree_order_parent_before_child_and_depth():
    # 정적 권한을 그룹별로 카탈로그 순서대로 모은다(렌더 입력과 동일).
    groups: dict[str, list[str]] = {}
    for code in app.PERMISSION_CODES:
        groups.setdefault(_group_of(code), []).append(code)
    for group, codes in groups.items():
        order = _order_items_as_tree(codes)
        assert len(order) == len(codes), f"{group}: 트리 정렬이 항목을 누락/중복 ({len(order)} vs {len(codes)})"
        assert {c for c, _ in order} == set(codes), f"{group}: 트리 정렬 코드 집합 불일치"
        pos = {c: i for i, (c, _) in enumerate(order)}
        depth = {c: d for c, d in order}
        for code in codes:
            parent = DEPS.get(code)
            if parent and parent in set(codes):
                # 그룹 내 부모는 자식보다 앞 + depth = 부모+1
                assert pos[parent] < pos[code], f"{group}: 부모 {parent} 가 자식 {code} 뒤"
                assert depth[code] == depth[parent] + 1, f"{group}: {code} depth 가 부모+1 아님"
            else:
                # 그룹 내 루트(부모 없음 / 부모 다른 그룹)는 depth 0
                assert depth[code] == 0, f"{group}: 루트 {code} depth 가 0 아님(부모={parent})"


def test_t2_conversation_groups_split_and_list_gate_nesting():
    # TASK-0269: 대화 권한이 conversation_own / conversation_any 두 그룹으로 분리되고,
    #   각 그룹에서 "목록 조회"(list)가 depth 0 게이트, 동작 권한은 depth 1 로 그 아래 중첩된다.
    own_codes = [c for c in app.PERMISSION_CODES if _group_of(c) == "conversation_own"]
    any_codes = [c for c in app.PERMISSION_CODES if _group_of(c) == "conversation_any"]
    assert own_codes, "conversation_own 그룹이 비었음(분리 실패)"
    assert any_codes, "conversation_any 그룹이 비었음(분리 실패)"
    # 분리 정합: .any 는 conversation_any, 나머지는 conversation_own
    for c in own_codes:
        assert not c.endswith(".any"), f"{c} 가 conversation_own 인데 .any 임"
    for c in any_codes:
        assert c.endswith(".any"), f"{c} 가 conversation_any 인데 .any 아님"
    # 각 그룹 트리: list 가 depth 0, 동작 권한이 depth 1
    for group_codes, gate in ((own_codes, "conversation.list.own"), (any_codes, "conversation.list.any")):
        order = _order_items_as_tree(group_codes)
        depth = {c: d for c, d in order}
        pos = {c: i for i, (c, _) in enumerate(order)}
        assert depth[gate] == 0, f"{gate} 가 depth 0(게이트 루트) 아님"
        for code in group_codes:
            if DEPS.get(code) == gate:
                assert depth[code] == 1, f"{code} 가 depth 1(게이트 자식) 아님"
                assert pos[gate] < pos[code], f"게이트 {gate} 가 {code} 뒤"


def test_t3_account_read_is_group_root_depth0():
    # account.read 는 부모(console.access)가 다른 그룹(console)이라 account 그룹 내 루트(depth 0).
    acct = [c for c in app.PERMISSION_CODES if _group_of(c) == "account"]
    depth = {c: d for c, d in _order_items_as_tree(acct)}
    assert depth["account.read"] == 0, "account.read 는 그룹 내 루트(depth 0)여야 함"
    assert depth["account.update"] == 1, "account.update 는 account.read 의 자식(depth 1)"


def test_t4_grid_list_is_single_column_not_grid():
    """트리 레이아웃: .permission-grid-list 는 단일 열(flex column) — 2열 grid(자식 숨김 시 가로 reflow
    뒤틀림)가 아니어야 한다 + depth 들여쓰기 규칙 존재."""
    css = STYLES_CSS.read_text(encoding="utf-8")
    # 줄 시작 앵커 — `.permission-group .permission-grid-list`(padding 규칙) 가 아닌 standalone 규칙.
    m = re.search(r"(?m)^\.permission-grid-list\s*\{([^}]*)\}", css)
    assert m, ".permission-grid-list standalone 규칙 부재"
    body = m.group(1)
    assert "flex" in body and "column" in body, ".permission-grid-list 가 flex column(단일 열) 아님 — 뒤틀림 회귀"
    assert "grid-template-columns" not in body, ".permission-grid-list 가 여전히 2열 grid(뒤틀림 원인)"
    assert '[data-perm-depth="1"]' in css, "depth 1 들여쓰기 규칙 부재 — 트리 위계 미표현"


def test_t5_metadata_group_gate_hierarchy():
    """metadata-perm-hier: 메타데이터(kb 그룹) 종속 정합화 pin. 다른 관리 그룹(account.read→account.*,
    quota.read→quota.manage)처럼 "그룹 게이트 → 세부" 2단 계층이어야 한다. 묶음 `kb.ingest.manual` 이
    게이트(→console.access), 세부 5개 metadata.* 는 묶음 아래(→kb.ingest.manual). flat 회귀 방지."""
    _META5 = (
        "metadata.glossary.manage", "metadata.enum.manage", "metadata.table.manage",
        "metadata.column.manage", "metadata.graph.read",
    )
    assert DEPS.get("kb.ingest.manual") == "console.access", "묶음 kb.ingest.manual 게이트가 console.access 아님"
    for m in _META5:
        assert DEPS.get(m) == "kb.ingest.manual", f"{m} 부모가 kb.ingest.manual 아님(평면 회귀)"
    # kb 그룹 트리 depth: 묶음=0(그룹 루트), 세부 metadata.*=1(묶음 자식)
    kb_codes = [c for c in app.PERMISSION_CODES if _group_of(c) == "kb"]
    tree = dict(_order_items_as_tree(kb_codes))
    assert tree.get("kb.ingest.manual") == 0, "kb.ingest.manual 이 그룹 루트(depth 0) 아님"
    for m in _META5:
        assert tree.get(m) == 1, f"{m} 이 묶음 아래(depth 1) 아님 — 계층 회귀"


def test_t6_metadata_reachable_when_gate_off():
    """B안 개별 부여 보존: 게이트(kb.ingest.manual) OFF 여도 개별 metadata.* 는 도달 가능해야 한다.
    console.access ON·kb.ingest.manual OFF → metadata.* 는 hidden(progressive disclosure 정상)이지만,
    kb 그룹은 루트 권한(kb.ingest.manual 게이트 자체 + kb.sample.curate 등)이 항상 보여 '더 보기' 탈출구가
    보장 → 통째 숨지 않는다(unreachable 아님)."""
    all_codes = set(app.PERMISSION_CODES)
    vis = compute_visibility({"console.access"}, all_codes)  # 묶음 미체크
    assert vis["metadata.glossary.manage"] is False, "게이트 OFF 인데 metadata 노출됨(계층 미작동)"
    assert vis["kb.ingest.manual"] is True, "그룹 게이트(묶음)가 루트인데 hidden — 도달 레버 소실"
    kb_codes = [c for c in app.PERMISSION_CODES if _group_of(c) == "kb"]
    kb_roots = [c for c in kb_codes if DEPS.get(c) not in set(kb_codes)]
    assert kb_roots, "kb 그룹에 루트 권한 없음 — '더 보기' 탈출구 부재 위험"
