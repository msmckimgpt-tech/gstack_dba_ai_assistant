"""graph-panel-perms (task4, Critical §12.3) — 메타데이터 탭 권한 세분화(B안) 회귀/보안 테스트.

단일 묶음 `kb.ingest.manual` 을 기능별 세부 권한으로 분리(사용자 결정 2026-07-01, B안):
  metadata.glossary.manage / metadata.enum.manage / metadata.table.manage /
  metadata.column.manage / metadata.graph.read

하위호환은 **비파괴·가역** 함의로 보장한다 — DB 마이그레이션 없이, effective permission map
빌더(_apply_permission_overrides)에서 묶음 보유자에게 세부 권한을 자동 부여(개별 DENY 존중).

검증:
  R1  5개 세부 권한이 PERMISSION_DEFINITIONS(group=kb) + PERMISSION_CODES 에 존재.
  R2  admin seed(=set(PERMISSION_CODES)) 포함 / operator·sales·pending 미포함(least-privilege).
  R3  하위호환 함의 — kb.ingest.manual(effective) → 5개 세부 권한 True (비파괴 마이그).
  R4  개별 DENY 오버라이드가 함의보다 우선(least-privilege 존중).
  R5  세부 권한 단독 부여 시 다른 세부 권한/묶음은 미부여(granular 격리).
  R6  레거시 묶음 kb.ingest.manual 은 catalog 에 유지(기존 grant 하위호환).
  R7  서버측 서브탭 RBAC 맵(_METADATA_SUBTAB_PERM_SERVER)이 세부 권한으로 갱신.
  R8  admin.js 프론트 서브탭 권한 맵도 세부 권한으로 갱신(FE/BE 동치).

DB 없이 순수 함수(_apply_permission_overrides)·정적 카탈로그로 검증한다(`make test`, --no-deps).
"""
from __future__ import annotations

import re
from pathlib import Path

import app

NEW_PERMS = [
    "metadata.glossary.manage",
    "metadata.enum.manage",
    "metadata.table.manage",
    "metadata.column.manage",
    "metadata.graph.read",
]

ADMIN_JS = Path(__file__).resolve().parents[1] / "src" / "static" / "admin.js"


# ── R1: 카탈로그 존재 ────────────────────────────────────────────────────────────
def test_r1_new_perms_in_catalog_group_kb():
    for code in NEW_PERMS:
        assert code in app.PERMISSION_CODES, f"{code} 가 PERMISSION_CODES 에 없음"
        assert app.PERMISSION_DEFINITION_MAP[code]["group"] == "kb", f"{code} group != kb"


# ── R2: admin seed 포함 / stock role 미포함 ─────────────────────────────────────────
def test_r2_admin_seed_not_stock_roles():
    admin = next(r for r in app.SEED_ROLE_DEFINITIONS if r.get("key") == "admin")
    for code in NEW_PERMS:
        assert code in set(admin["permissions"]), f"admin seed 에 {code} 누락"
    for key in ("operator", "sales", "pending"):
        role = next((r for r in app.SEED_ROLE_DEFINITIONS if r.get("key") == key), None)
        if role is not None:
            for code in NEW_PERMS:
                assert code not in set(role["permissions"]), f"{key} 는 {code} 미보유(least-privilege)"


# ── R3: 하위호환 함의 (kb.ingest.manual → 세부 권한 전체) ─────────────────────────────
def test_r3_manual_umbrella_implies_all_detail_perms():
    perms = app._apply_permission_overrides({"kb.ingest.manual"})
    assert perms.get("kb.ingest.manual") is True
    for code in NEW_PERMS:
        assert perms.get(code) is True, f"묶음 보유인데 {code} 함의 안 됨(하위호환 깨짐)"


def test_r3b_manual_umbrella_via_account_override_allow():
    # 계정 ALLOW 오버라이드로 묶음을 얻은 경우에도 세부 권한이 함의돼야 한다(effective map 기준).
    perms = app._apply_permission_overrides(set(), {"kb.ingest.manual": app.OVERRIDE_ALLOW})
    for code in NEW_PERMS:
        assert perms.get(code) is True, f"override-allow 묶음인데 {code} 함의 안 됨"


# ── R4: 개별 DENY 오버라이드가 함의보다 우선 ─────────────────────────────────────────
def test_r4_detail_deny_override_beats_implication():
    perms = app._apply_permission_overrides(
        {"kb.ingest.manual"}, {"metadata.graph.read": app.OVERRIDE_DENY}
    )
    assert perms.get("metadata.graph.read") is False, "명시 DENY 가 함의보다 우선해야 함"
    # 나머지 세부 권한은 여전히 함의 True.
    for code in NEW_PERMS:
        if code == "metadata.graph.read":
            continue
        assert perms.get(code) is True, f"{code} 는 DENY 안 됐으므로 여전히 함의 True"


# ── R5: 세부 권한 단독 부여 격리 ────────────────────────────────────────────────────
def test_r5_granular_grant_is_isolated():
    perms = app._apply_permission_overrides({"metadata.glossary.manage"})
    assert perms.get("metadata.glossary.manage") is True
    assert perms.get("metadata.enum.manage") is False, "다른 세부 권한 미부여(격리)"
    assert perms.get("metadata.table.manage") is False
    assert perms.get("metadata.column.manage") is False
    assert perms.get("metadata.graph.read") is False
    # 세부 권한만으론 묶음이 켜지지 않는다(역함의 없음).
    assert perms.get("kb.ingest.manual") is False, "세부 권한이 묶음을 역으로 켜면 안 됨"


# ── R6: 레거시 묶음 catalog 유지 ────────────────────────────────────────────────────
def test_r6_legacy_umbrella_retained_in_catalog():
    assert "kb.ingest.manual" in app.PERMISSION_CODES, "레거시 grant 하위호환 위해 유지"


# ── R7: 서버 서브탭 RBAC 맵 갱신 ────────────────────────────────────────────────────
def test_r7_server_subtab_perm_map_split():
    m = app._METADATA_SUBTAB_PERM_SERVER
    assert m["glossary"] == "metadata.glossary.manage"
    assert m["enums"] == "metadata.enum.manage"
    assert m["tables"] == "metadata.table.manage"
    assert m["columns"] == "metadata.column.manage"
    assert m["samples"] == "kb.sample.curate"  # 불변


# ── R8: 프론트 서브탭 권한 맵도 세부 권한(FE/BE 동치) ────────────────────────────────
def test_r8_frontend_subtab_perm_map_split():
    text = ADMIN_JS.read_text(encoding="utf-8")
    m = re.search(r"const _METADATA_SUBTAB_PERM\s*=\s*\{(.*?)\};", text, re.DOTALL)
    assert m, "_METADATA_SUBTAB_PERM 블록을 admin.js 에서 찾지 못함"
    body = m.group(1)
    # feature-0016 §45: graph 서브탭은 admin.js 에서 제거됨(그래프 뷰=지식베이스 최상위 탭 ADMIN_TAB_PERMISSIONS.graph
    # 으로 이관). _METADATA_SUBTAB_PERM 에서 graph 키가 사라진 것과 정합하도록 기대에서 제외(stale 테스트 정정,
    # share-visibility-window 머지 위생).
    for sub, perm in (("glossary", "metadata.glossary.manage"), ("enums", "metadata.enum.manage"),
                      ("tables", "metadata.table.manage"), ("columns", "metadata.column.manage")):
        assert re.search(rf'{sub}:\s*"{re.escape(perm)}"', body), f"admin.js 서브탭 {sub} → {perm} 미갱신"
