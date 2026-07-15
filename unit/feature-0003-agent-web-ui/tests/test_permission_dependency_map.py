"""권한 점진적 세분화(progressive disclosure) 회귀 테스트.

admin.js 의 `PERMISSION_DEPENDENCIES`(child -> 선행 parent) 맵을 파싱해
백엔드 `app.PERMISSION_DEFINITIONS` 의 권한 code 와 정합성을 검증하고,
가시성 알고리즘(JS 의 _applyPermissionDisclosure)을 Python 으로 포팅해
핵심 불변식(비파괴 / 마스터 게이트 / own→any 종속)을 검증한다.

검증 대상:
  M1  맵 파싱 — 25개 이상 엔트리, child/parent 모두 실제 권한 code.
  M2  비순환 — 모든 체인이 루트로 종료(self-loop / cycle 없음).
  M3  마스터 게이트 + 카테고리 접근(perm-category-hier, Critical §12.3, 사용자 승인 A안 2026-07-14) —
        console.access 하위에 카테고리 접근 5종(console.{account,product,audit,kb,system}.access),
        각 카테고리의 탭 조회 base(account.read/role.read/audit.read.own/...)는 소속 카테고리
        접근을 부모로 둔다. console.access 는 키가 아님(루트).
  M4  own→any — `.any`(전체) 대화 권한은 대응 `.own`(내) 권한을 부모로 둔다.
        (예외: conversation.archive.read.any 는 감사 카테고리 탭 권한 — console.audit.access 하위.)
  M5  카테고리-하위 정합 — web_context._CONSOLE_CATEGORY_ACCESS_LEAVES 의 모든 세부 권한의
        조상 체인이 그 카테고리의 접근 권한을 경유한다(백엔드 backfill 맵 ↔ FE 종속 맵 동치).
  V1  비파괴 — 임의 checked 집합에서 checked 권한은 항상 visible(부여된 권한 미숨김).
  V2  마스터 게이트 OFF — checked=∅ 이면 관리 권한 section 의 비루트 권한 전부 hidden,
        console.access 만 visible(계정·역할 등 그룹이 통째 접힘).
  V3  중간 게이트 — console.access·console.account.access ON·account.read OFF →
        account.read visible, account.update hidden.
  V4  orphan 체인 — account.delete 만 checked → 게이트 미충족이라 hidden(단순화 계약).

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


_CATEGORY_ACCESS = (
    "console.account.access", "console.product.access", "console.audit.access",
    "console.kb.access", "console.system.access",
)

# perm-atomic-split(2026-07-15): 레거시 묶음 — 실 grid 는 LEGACY_BUNDLE_PERMISSIONS 로 렌더 전
# 제거하므로 가시성/트리 검증에서도 제외한다(admin.js·web_context.LEGACY_BUNDLE_PERMISSIONS parity).
_LEGACY_BUNDLES = {
    "kb.ingest.manual",
    "metadata.glossary.manage", "metadata.enum.manage", "metadata.table.manage", "metadata.column.manage",
    "product.manage", "datasource.manage",
}


def test_m3_master_gate_and_category_access():
    # perm-category-hier(Critical §12.3, 2026-07-14): console.access 하위에 카테고리 접근 5종,
    #   각 카테고리의 탭 조회 base 는 소속 카테고리 접근을 부모로 둔다.
    for access in _CATEGORY_ACCESS:
        assert DEPS.get(access) == "console.access", f"{access} 의 부모가 console.access 아님"
    for base, access in (
        ("account.read", "console.account.access"),
        ("role.read", "console.account.access"),
        ("quota.read", "console.account.access"),
        ("product.read", "console.product.access"),
        ("datasource.read", "console.product.access"),
        ("audit.read.own", "console.audit.access"),
        ("conversation.archive.read.any", "console.audit.access"),
        ("console.usage.read", "console.audit.access"),
        ("console.aiops.read", "console.audit.access"),
        # perm-atomic-split: 사전 4종 조회(read)가 서브탭 게이트 — 카테고리 접근 하위.
        ("metadata.glossary.read", "console.kb.access"),
        ("metadata.enum.read", "console.kb.access"),
        ("metadata.table.read", "console.kb.access"),
        ("metadata.column.read", "console.kb.access"),
        ("metadata.graph.read", "console.kb.access"),
        ("kb.sample.curate", "console.kb.access"),
        # 검수(승급·거부 단일)는 원본 사전 조회 하위(사용자 지시 2026-07-15).
        ("kb.glossary.curate", "metadata.glossary.read"),
        ("kb.enum.curate", "metadata.enum.read"),
        ("system_prompt.global.read", "console.system.access"),
        ("system.runtime.read", "console.system.access"),
    ):
        assert DEPS.get(base) == access, f"{base} 의 부모가 {access} 아님 (실제 {DEPS.get(base)})"
    # perm-atomic-split: 원자 CRUD — 각 사전/엔티티의 추가·수정·삭제(·테스트)는 조회(read) 하위.
    for ent, acts in (
        ("metadata.glossary", ("create", "update", "delete")),
        ("metadata.enum", ("create", "update", "delete")),
        ("metadata.table", ("create", "update", "delete")),
        ("metadata.column", ("create", "update", "delete")),
        ("product", ("create", "update", "delete")),
        ("datasource", ("create", "update", "delete", "test")),
    ):
        for act in acts:
            assert DEPS.get(f"{ent}.{act}") == f"{ent}.read", f"{ent}.{act} 부모가 {ent}.read 아님"
    # 레거시 묶음은 grid 미표시 — 종속 트리에서 제외(키로 존재하면 안 됨).
    for legacy in _LEGACY_BUNDLES:
        assert legacy not in DEPS, f"레거시 묶음 {legacy} 가 종속 트리에 잔존"
    # 작동 권한 오배치 정정: insight.reset 은 제품 카테고리의 작동 권한(product.read 하위).
    assert DEPS.get("insight.reset") == "product.read", "insight.reset 부모가 product.read 아님"
    # 시스템 카테고리: runtime write 는 read 선행(기존 미선언 루트였던 것을 정합).
    assert DEPS.get("system.runtime.write") == "system.runtime.read", "system.runtime.write 종속 누락"
    assert "console.access" not in DEPS, "console.access 는 루트여야 함(키가 되면 안 됨)"


def test_m4_conversation_list_gate():
    # TASK-0269 + perm-category-hier: 대화 own/any 그룹 분리 + "목록 조회"(카테고리 접근=조회) 게이트.
    #   전체 대화(.any) 동작 권한은 conversation.list.any 를, 내 대화 동작 권한은 conversation.list.own 을 부모로 둔다.
    #   list.own / list.any 는 루트(부모 없음). create 는 동작 권한 — list.own 하위(perm-category-hier 정합).
    for root in ("conversation.list.own", "conversation.list.any"):
        assert DEPS.get(root) is None, f"{root} 는 루트(부모 없음)여야 함 (실제 {DEPS.get(root)})"
    assert DEPS.get("conversation.create") == "conversation.list.own", \
        "conversation.create 는 내 대화 목록 조회(접근 게이트) 하위여야 함"
    for code in VALID_CODES:
        if not code.startswith("conversation."):
            continue
        if code in ("conversation.create", "conversation.list.own", "conversation.list.any"):
            continue
        if code == "conversation.archive.read.any":
            # perm-category-hier: 보관 대화 조회는 감사 카테고리 탭 권한(console.audit.access 하위).
            continue
        gate = "conversation.list.any" if code.endswith(".any") else "conversation.list.own"
        assert DEPS.get(code) == gate, f"{code} 의 게이트가 {gate} 아님 (실제 {DEPS.get(code)})"


def test_m5_backend_category_leaves_map_coherent():
    # perm-category-hier: 백엔드 backfill 맵(_CONSOLE_CATEGORY_ACCESS_LEAVES)과 FE 종속 맵 동치 —
    #   각 카테고리의 모든 세부 권한의 조상 체인이 그 카테고리의 접근 권한을 경유해야 한다.
    import web_context

    leaves_map = web_context._CONSOLE_CATEGORY_ACCESS_LEAVES
    assert set(leaves_map.keys()) == set(_CATEGORY_ACCESS), "카테고리 접근 5종 키 불일치"
    for access, leaves in leaves_map.items():
        assert access in VALID_CODES, f"{access} 가 카탈로그에 없음"
        for leaf in leaves:
            assert leaf in VALID_CODES, f"{leaf} 가 카탈로그에 없음"
            chain = []
            cur = DEPS.get(leaf)
            while cur is not None:
                chain.append(cur)
                cur = DEPS.get(cur)
            assert access in chain, f"{leaf} 의 조상 체인에 {access} 부재 (체인={chain})"
    # 관리 콘솔 마스터 게이트 경유: 접근 5종의 조상 = console.access.
    for access in _CATEGORY_ACCESS:
        assert DEPS.get(access) == "console.access"


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
        "datasource.read", "datasource.create", "datasource.update", "datasource.delete", "datasource.test",
        "product.read", "product.create", "product.update", "product.delete", "system_prompt.manage.role.any",
        "metadata.glossary.read", "metadata.glossary.create", "kb.glossary.curate",
        "audit.read.own", "audit.read.any", "audit.purge",
        "system_prompt.global.read", "system_prompt.global.write",
    ):
        assert not vis[code], f"게이트 OFF 인데 {code} 가 보임"
    # 레거시 묶음은 실 grid 에서 렌더 자체가 제외 — 가시성 검증 대상 아님(_LEGACY_BUNDLES).
    # 운영 권한 루트(TASK-0269 + perm-category-hier: list.own / list.any)는 게이트 없이 visible.
    # create 는 perm-category-hier 에서 list.own 하위 동작 권한으로 정합 — 루트 아님.
    for code in ("conversation.list.own", "conversation.list.any"):
        assert vis[code], f"운영 루트 {code} 가 숨겨짐"
    assert not vis["conversation.create"], "list.own OFF 인데 create 가 보임(접근 게이트 미작동)"
    # 동작 권한은 "목록 조회" 게이트 OFF 라 hidden (read.own→list.own, read.any→list.any)
    assert not vis["conversation.read.own"], "list.own OFF 인데 read.own 가 보임"
    assert not vis["conversation.read.any"], "list.any OFF 인데 read.any 가 보임"
    # perm-category-hier: 카테고리 접근 5종도 비루트(console.access 하위)라 hidden.
    for code in _CATEGORY_ACCESS:
        assert not vis[code], f"마스터 게이트 OFF 인데 {code} 가 보임"


def test_v3_intermediate_gate_account_read():
    all_codes = set(VALID_CODES)
    # perm-category-hier: 카테고리 접근이 중간 게이트 — console.access 만 켜면 카테고리 접근만 노출.
    vis0 = compute_visibility({"console.access"}, all_codes)
    assert vis0["console.account.access"], "console.access ON 이면 계정 카테고리 접근 노출"
    assert not vis0["account.read"], "console.account.access OFF 인데 account.read 가 보임"
    vis = compute_visibility({"console.access", "console.account.access"}, all_codes)
    assert vis["account.read"], "카테고리 접근 ON 이면 account.read(탭 base) 노출"
    assert not vis["account.update"], "account.read OFF 인데 account.update 가 보임"
    assert vis["role.read"], "카테고리 접근 ON 이면 role.read 노출"
    assert vis["quota.read"], "카테고리 접근 ON 이면 quota.read 노출"


def test_v4_granted_detail_collapsed_when_gate_off():
    all_codes = set(VALID_CODES)
    # account.delete 만 부여(게이트 OFF) — 부여됐어도 게이트 미충족이라 숨김(TASK-0264 핵심).
    vis = compute_visibility({"account.delete"}, all_codes)
    assert not vis["account.delete"], "게이트 OFF 인데 부여된 account.delete 가 노출됨 — 단순화 위반"
    assert not vis["account.read"], "게이트(console.access) OFF 라 account.read 도 숨김"
    assert vis["console.access"], "console.access(루트)는 항상 노출"
    assert not vis["account.update"], "형제 account.update 도 게이트 OFF 라 숨김"
    # 게이트 체인을 충족하면 도달(노출) — perm-category-hier: 체인에 카테고리 접근 포함.
    vis2 = compute_visibility(
        {"console.access", "console.account.access", "account.read", "account.delete"}, all_codes
    )
    assert vis2["account.delete"], "게이트 체인 충족 시 account.delete 노출"
    assert vis2["account.read"] and vis2["console.access"], "충족된 게이트들도 노출"
    assert vis2["console.account.access"], "충족된 카테고리 접근도 노출"


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
    # 게이트 허용 체인 → 자식 노출. console.access·카테고리 접근·account.read 허용 → account.update 노출.
    vis2 = compute_visibility_override(
        {"console.access": "allow", "console.account.access": "allow", "account.read": "allow"}, all_codes
    )
    assert vis2["account.read"], "카테고리 접근 허용 시 account.read 노출"
    assert vis2["account.update"], "account.read 허용 시 account.update 노출"
    # 게이트 거부는 자식을 열지 않음(허용만).
    vis3 = compute_visibility_override(
        {"console.access": "allow", "console.account.access": "allow", "account.read": "deny"}, all_codes
    )
    assert not vis3["account.update"], "account.read=거부 면 account.update 안 열림"


def test_v7_override_inherit_allow_gate_reveals_children():
    # TASK-0270: 계정 override 게이트는 "허용" 뿐 아니라 "상속(허용)"(상속 + 역할이 부여)에도 펼친다.
    all_codes = set(VALID_CODES)
    # console.access·카테고리 접근·account.read 가 override "상속"이고 역할이 셋 다 부여(inherited)
    # → account.update 노출.
    inherited = {"console.access", "console.account.access", "account.read"}
    vis = compute_visibility_override({}, all_codes, inherited)  # 모든 값 기본 "상속"
    assert vis["account.read"], "카테고리 접근 상속(허용) 시 account.read 노출"
    assert vis["account.update"], "account.read 상속(허용) 시 account.update 노출"
    # 역할이 부여 안 함(inherited 비어있음) → 상속(거부) → 안 펼침.
    vis_none = compute_visibility_override({}, all_codes, set())
    assert not vis_none["account.read"], "역할 미부여 상속(거부)면 account.read 안 노출"
    assert not vis_none["account.update"], "역할 미부여면 account.update 안 노출"
    # 명시 "거부"는 역할이 부여(inherited)해도 게이트 OFF — 거부가 상속을 이긴다.
    vis_deny = compute_visibility_override(
        {"account.read": "deny"}, all_codes,
        {"console.access", "console.account.access", "account.read"},
    )
    assert not vis_deny["account.update"], "account.read=거부면 역할이 부여해도 account.update 안 열림"
    # "허용"은 inherited 무관하게 펼침.
    vis_allow = compute_visibility_override(
        {"console.access": "allow", "console.account.access": "allow", "account.read": "allow"},
        all_codes, set(),
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


def test_t3_account_category_access_is_group_root_depth0():
    # perm-category-hier: account 그룹 내 루트는 카테고리 접근(console.account.access, 부모=다른 그룹
    # console 의 console.access). account.read 는 그 자식(depth 1), 세부 권한은 depth 2.
    acct = [c for c in app.PERMISSION_CODES if _group_of(c) == "account"]
    depth = {c: d for c, d in _order_items_as_tree(acct)}
    assert depth["console.account.access"] == 0, "console.account.access 가 그룹 내 루트(depth 0)여야 함"
    assert depth["account.read"] == 1, "account.read 는 카테고리 접근의 자식(depth 1)"
    assert depth["account.update"] == 2, "account.update 는 account.read 의 자식(depth 2)"


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
    """perm-atomic-split(2026-07-15): 지식베이스(kb 그룹) 원자 트리 pin.
    console.kb.access(그룹 루트) → 사전 4종 조회(read, depth1) → 각 추가/수정/삭제(depth2) +
    검수(승급·거부 단일, glossary/enum 은 원본 사전 read 하위 depth2 — 사용자 지시) +
    그래프 조회(depth1) → 능동 분석 실행(depth2). 레거시 묶음은 grid 미표시(트리 제외)."""
    assert DEPS.get("console.kb.access") == "console.access", "console.kb.access 부모가 console.access 아님"
    for ent in ("glossary", "enum", "table", "column"):
        assert DEPS.get(f"metadata.{ent}.read") == "console.kb.access", f"{ent}.read 부모가 카테고리 접근 아님"
        for act in ("create", "update", "delete"):
            assert DEPS.get(f"metadata.{ent}.{act}") == f"metadata.{ent}.read", f"{ent}.{act} 부모가 read 아님"
    assert DEPS.get("kb.glossary.curate") == "metadata.glossary.read", "용어 검수가 원본 사전 read 하위 아님"
    assert DEPS.get("kb.enum.curate") == "metadata.enum.read", "ENUM 검수가 원본 사전 read 하위 아님"
    assert DEPS.get("kb.sample.curate") == "console.kb.access", "샘플 검수(원본 조회 단위 없음)가 카테고리 직속 아님"
    assert DEPS.get("metadata.graph.read") == "console.kb.access"
    assert DEPS.get("metadata.graph.analyze") == "metadata.graph.read"
    # kb 그룹 트리 depth(레거시 묶음 필터 후): 카테고리 접근=0, read/graph.read/sample.curate=1, 원자·검수·analyze=2.
    kb_codes = [c for c in app.PERMISSION_CODES if _group_of(c) == "kb" and c not in _LEGACY_BUNDLES]
    tree = dict(_order_items_as_tree(kb_codes))
    assert tree.get("console.kb.access") == 0
    for ent in ("glossary", "enum", "table", "column"):
        assert tree.get(f"metadata.{ent}.read") == 1, f"{ent}.read depth1 아님"
        for act in ("create", "update", "delete"):
            assert tree.get(f"metadata.{ent}.{act}") == 2, f"{ent}.{act} depth2 아님"
    assert tree.get("kb.glossary.curate") == 2 and tree.get("kb.enum.curate") == 2
    assert tree.get("kb.sample.curate") == 1
    assert tree.get("metadata.graph.read") == 1 and tree.get("metadata.graph.analyze") == 2


def test_t6_metadata_reachable_when_gate_off():
    """원자 분리 후 도달성: 카테고리 접근 ON·사전 read OFF → 원자(추가/수정/삭제)·검수는 hidden
    (progressive disclosure)이지만, read 게이트 자체(그룹 depth1 루트들)는 노출돼 '더 보기' 복원
    레버가 보장된다. read ON 이면 원자 노출."""
    all_codes = set(app.PERMISSION_CODES)
    vis = compute_visibility({"console.access", "console.kb.access"}, all_codes)  # read 미체크
    assert vis["metadata.glossary.read"] is True, "read 게이트가 hidden — 복원 레버 소실"
    assert vis["metadata.glossary.create"] is False, "read OFF 인데 create 노출(계층 미작동)"
    assert vis["kb.glossary.curate"] is False, "read OFF 인데 검수 노출(원본 종속 미작동)"
    vis2 = compute_visibility({"console.access", "console.kb.access", "metadata.glossary.read"}, all_codes)
    assert vis2["metadata.glossary.create"] and vis2["metadata.glossary.update"] and vis2["metadata.glossary.delete"]
    assert vis2["kb.glossary.curate"], "read ON 인데 검수 hidden"
    kb_codes = [c for c in app.PERMISSION_CODES if _group_of(c) == "kb" and c not in _LEGACY_BUNDLES]
    kb_roots = [c for c in kb_codes if DEPS.get(c) not in set(kb_codes)]
    assert "console.kb.access" in kb_roots, "카테고리 접근이 kb 그룹 루트가 아님"
