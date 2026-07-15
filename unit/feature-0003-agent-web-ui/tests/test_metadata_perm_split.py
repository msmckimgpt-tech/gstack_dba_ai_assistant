"""graph-panel-perms (task4, Critical §12.3) — 메타데이터 탭 권한 세분화(B안) 회귀/보안 테스트.

단일 묶음 `kb.ingest.manual` 을 기능별 세부 권한으로 분리(사용자 결정 2026-07-01, B안):
  metadata.glossary.manage / metadata.enum.manage / metadata.table.manage /
  metadata.column.manage / metadata.graph.read

하위호환은 **비파괴·가역** 함의로 보장한다 — DB 마이그레이션 없이, effective permission map
빌더(_apply_permission_overrides)에서 묶음 보유자에게 세부 권한을 자동 부여(개별 DENY 존중).

graph-perm-split(Critical §12.3, 2026-07-13): 그래프 뷰가 별도 최상위 탭으로 분리됨에 따라
metadata.graph.read 를 묶음 함의(_METADATA_MANUAL_IMPLIES)에서 제거 — 묶음이 함의하는 것은 편집 4종뿐.
기존 묶음 보유자의 그래프 접근은 _backfill_graph_perm_split_v1(1회 멱등 backfill)로 보존(B안).

검증:
  R1  5개 세부 권한이 PERMISSION_DEFINITIONS(group=kb) + PERMISSION_CODES 에 존재(graph.read 포함).
  R2  admin seed(=set(PERMISSION_CODES)) 포함 / operator·sales·pending 미포함(least-privilege).
  R3  하위호환 함의 — kb.ingest.manual(effective) → 편집 4종 True (비파괴 마이그).
  R3c graph-perm-split — 묶음은 metadata.graph.read 를 함의하지 않는다(권한 분리).
  R3d graph.read 단독 부여는 독립(묶음/편집 권한 미부여).
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

# graph-perm-split(Critical §12.3, 2026-07-13): 그래프 뷰가 별도 최상위 탭으로 분리됨에 따라
#   metadata.graph.read 를 묶음 함의(_METADATA_MANUAL_IMPLIES)에서 제거. 묶음이 함의하는 것은 편집 4종뿐이다.
#   graph.read 는 여전히 카탈로그(group=kb)·admin seed 에 존재하나, 묶음과 독립적으로 부여된다.
EDIT_PERMS = [
    "metadata.glossary.manage",
    "metadata.enum.manage",
    "metadata.table.manage",
    "metadata.column.manage",
]
GRAPH_PERM = "metadata.graph.read"
# R1/R2 는 5종 전체(카탈로그 존재·admin seed) 를 커버 — graph.read 는 분리 후에도 catalog/admin seed 에 유지.
NEW_PERMS = EDIT_PERMS + [GRAPH_PERM]

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


# ── R3: 하위호환 함의 (kb.ingest.manual → 편집 4종) ─────────────────────────────────
def test_r3_manual_umbrella_implies_edit_perms():
    perms = app._apply_permission_overrides({"kb.ingest.manual"})
    assert perms.get("kb.ingest.manual") is True
    for code in EDIT_PERMS:
        assert perms.get(code) is True, f"묶음 보유인데 {code} 함의 안 됨(하위호환 깨짐)"


def test_r3b_manual_umbrella_via_account_override_allow():
    # 계정 ALLOW 오버라이드로 묶음을 얻은 경우에도 편집 4종이 함의돼야 한다(effective map 기준).
    perms = app._apply_permission_overrides(set(), {"kb.ingest.manual": app.OVERRIDE_ALLOW})
    for code in EDIT_PERMS:
        assert perms.get(code) is True, f"override-allow 묶음인데 {code} 함의 안 됨"


# ── R3c: graph-perm-split — 묶음은 그래프 뷰 조회를 함의하지 않는다(권한 분리) ──────────────
def test_r3c_manual_umbrella_does_not_imply_graph():
    """graph-perm-split(Critical §12.3, 2026-07-13): 그래프 뷰가 별도 최상위 탭으로 분리됨에 따라
    '메타데이터 관리' 묶음(kb.ingest.manual)은 더 이상 그래프 뷰 조회(metadata.graph.read)를 함의하지 않는다.
    묶음만 보유한 principal 은 그래프 뷰 접근을 갖지 않는다(명시 부여 필요)."""
    perms = app._apply_permission_overrides({"kb.ingest.manual"})
    assert perms.get("metadata.graph.read") is False, \
        "묶음이 그래프 뷰를 함의하면 분리 실패(권한이 메타데이터 관리에서 안 떨어짐)"
    # 계정 ALLOW 오버라이드로 묶음을 얻어도 함의 안 됨.
    perms_ovr = app._apply_permission_overrides(set(), {"kb.ingest.manual": app.OVERRIDE_ALLOW})
    assert perms_ovr.get("metadata.graph.read") is False, "override-allow 묶음도 그래프 함의 안 함"
    assert GRAPH_PERM not in app._METADATA_MANUAL_IMPLIES, \
        "metadata.graph.read 가 _METADATA_MANUAL_IMPLIES 에 남아 있음(분리 회귀)"


def test_r3d_graph_grant_is_independent():
    """graph.read 를 명시 부여하면 그래프만 켜지고 묶음/편집 권한은 미부여(독립 권한)."""
    perms = app._apply_permission_overrides({"metadata.graph.read"})
    assert perms.get("metadata.graph.read") is True
    assert perms.get("kb.ingest.manual") is False, "그래프 권한이 묶음을 역으로 켜면 안 됨"
    for code in EDIT_PERMS:
        assert perms.get(code) is False, f"그래프 권한 단독인데 {code} 부여됨(격리 위반)"


# ── R4: 개별 DENY 오버라이드가 함의보다 우선 (편집 권한 기준) ─────────────────────────────
def test_r4_detail_deny_override_beats_implication():
    perms = app._apply_permission_overrides(
        {"kb.ingest.manual"}, {"metadata.column.manage": app.OVERRIDE_DENY}
    )
    assert perms.get("metadata.column.manage") is False, "명시 DENY 가 함의보다 우선해야 함"
    # 나머지 편집 권한은 여전히 함의 True.
    for code in EDIT_PERMS:
        if code == "metadata.column.manage":
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
    # perm-atomic-split(2026-07-15): 서브탭 진입(가시성) 게이트 = 조회(read) 원자 단위.
    m = app._METADATA_SUBTAB_PERM_SERVER
    assert m["glossary"] == "metadata.glossary.read"
    assert m["enums"] == "metadata.enum.read"
    assert m["tables"] == "metadata.table.read"
    assert m["columns"] == "metadata.column.read"
    assert m["samples"] == "kb.sample.curate"


def test_r8_frontend_subtab_perm_map_split():
    text = ADMIN_JS.read_text(encoding="utf-8")
    m = re.search(r"const _METADATA_SUBTAB_PERM\s*=\s*\{(.*?)\};", text, re.DOTALL)
    assert m, "_METADATA_SUBTAB_PERM 블록을 admin.js 에서 찾지 못함"
    body = m.group(1)
    # feature-0016 §45: graph 서브탭은 admin.js 에서 제거됨(그래프 뷰=지식베이스 최상위 탭 ADMIN_TAB_PERMISSIONS.graph
    # 으로 이관). _METADATA_SUBTAB_PERM 에서 graph 키가 사라진 것과 정합하도록 기대에서 제외(stale 테스트 정정,
    # share-visibility-window 머지 위생).
    for sub, perm in (("glossary", "metadata.glossary.read"), ("enums", "metadata.enum.read"),
                      ("tables", "metadata.table.read"), ("columns", "metadata.column.read")):
        assert re.search(rf'{sub}:\s*"{re.escape(perm)}"', body), f"admin.js 서브탭 {sub} → {perm} 미갱신"


# ── graph-analyze-perm(Critical §12.3, 2026-07-14): AI 능동 분석 실행 하위 권한 분리 ──────────────
def test_graph_analyze_in_catalog_group_kb():
    assert "metadata.graph.analyze" in app.PERMISSION_CODES, "metadata.graph.analyze 가 PERMISSION_CODES 에 없음"
    assert app.PERMISSION_DEFINITION_MAP["metadata.graph.analyze"]["group"] == "kb", "graph.analyze group != kb"


def test_graph_analyze_admin_seed_not_stock():
    admin = next(r for r in app.SEED_ROLE_DEFINITIONS if r.get("key") == "admin")
    assert "metadata.graph.analyze" in set(admin["permissions"]), "admin seed 에 metadata.graph.analyze 누락"
    for key in ("operator", "sales", "pending"):
        role = next((r for r in app.SEED_ROLE_DEFINITIONS if r.get("key") == key), None)
        if role is not None:
            assert "metadata.graph.analyze" not in set(role["permissions"]), \
                f"{key} 는 metadata.graph.analyze 미보유(least-privilege — 실행은 명시 부여)"


def test_graph_read_alone_does_not_grant_analyze():
    """graph-analyze-perm 핵심 계약(A안 least-privilege): 그래프 뷰 조회(metadata.graph.read)만 보유해도
    AI 능동 분석 실행(metadata.graph.analyze)은 부여되지 않는다 — 함의/역함의 없음. graph.read 만 있는
    사용자는 프론트에서 능동 분석 버튼/메뉴를 못 본다(백엔드도 403). 실행은 명시 부여 필요."""
    perms = app._apply_permission_overrides({"metadata.graph.read"})
    assert perms.get("metadata.graph.read") is True
    assert perms.get("metadata.graph.analyze") is False, \
        "graph.read 만으로 graph.analyze 가 켜지면 분리 실패(실행 권한이 조회에 딸려옴)"


def test_graph_analyze_grant_is_independent():
    """graph.analyze 를 명시 부여하면 실행만 켜지고 조회(graph.read)를 역으로 켜지 않는다(격리)."""
    perms = app._apply_permission_overrides({"metadata.graph.analyze"})
    assert perms.get("metadata.graph.analyze") is True
    assert perms.get("metadata.graph.read") is False, "실행 권한이 조회를 역으로 켜면 안 됨(역함의 없음)"


def test_graph_analyze_admin_catchup_present():
    """기존 배포 admin lockout 방지: _ensure_seed_roles admin catchup 소스에 metadata.graph.analyze 포함
    (신규 권한은 role 생성 seed 로만 부여돼 기존 admin row 미적용 — catchup 없으면 능동 분석 버튼 상실)."""
    import inspect
    src = inspect.getsource(app._ensure_seed_roles)
    assert '"metadata.graph.analyze"' in src, \
        "_ensure_seed_roles admin catchup 에 metadata.graph.analyze 누락(기존 admin lockout 위험)"


_GRAPH_CTX = Path(__file__).resolve().parents[1] / "src" / "static" / "graph" / "graph-ctxmenu.js"


def test_graph_analyze_fe_gate_split():
    """graph-analyze-perm(보안리뷰 MEDIUM 수정): 프론트 게이트 분리 — 결과 조회는 graph.read(항상), 실행 버튼만
    graph.analyze. graph.read-only 뷰어도 상세 패널에서 기존 AI 분석 결과를 열람해야 한다(graph.read 설명 계약
    "결과·진행 상태 열람"·백엔드 GET /graph/analyze/node 도 graph.read). 실행 컨트롤(버튼·popover)만 _canAnalyze 게이트."""
    text = _GRAPH_CTX.read_text(encoding="utf-8")
    # 실행 버튼(metaGraphAiBtn)은 _canAnalyze 삼항으로 게이트(미보유 시 미렌더).
    assert re.search(r"_canAnalyze\s*\?[^\n]*metaGraphAiBtn", text), \
        "실행 버튼 metaGraphAiBtn 이 _canAnalyze 게이트 밖(무권한자에게 노출 위험)"
    # 실행 컨트롤 바인딩은 _canAnalyze 게이트.
    assert "if (_canAnalyze) _metaGraphBindAiPopover" in text, \
        "실행 컨트롤 바인딩(_metaGraphBindAiPopover)이 _canAnalyze 게이트 밖"
    # 결과 로드(_metaGraphLoadNodeAnalysis)는 무조건 호출 — view-only 결과 열람 보장(실행 게이트에 갇히면 안 됨).
    assert "_metaGraphLoadNodeAnalysis(self.key)" in text, "노드 분석 결과 로드 호출 부재"
    assert "if (_canAnalyze) _metaGraphLoadNodeAnalysis" not in text, \
        "결과 로드가 실행 권한(_canAnalyze) 게이트에 갇힘 — graph.read-only 뷰어가 결과를 못 봄(계약 위반)"


# ── R9/R10: perm-atomic-split(2026-07-15) — transitive 묶음 함의 + 레거시 숨김 parity ──
def test_r9_bundle_implies_atomic_transitive():
    """묶음 보유 → 원자 단위 transitive 함의: kb.ingest.manual → manage 4종 → 각 read/create/update/delete.
    개별 DENY 오버라이드는 함의보다 우선(least-privilege)."""
    perms = app._apply_permission_overrides({"kb.ingest.manual"})
    for ent in ("glossary", "enum", "table", "column"):
        assert perms.get(f"metadata.{ent}.manage") is True
        for act in ("read", "create", "update", "delete"):
            assert perms.get(f"metadata.{ent}.{act}") is True, f"{ent}.{act} transitive 함의 실패"
    # manage 단독 → 그 사전의 원자만(격리)
    perms2 = app._apply_permission_overrides({"metadata.glossary.manage"})
    for act in ("read", "create", "update", "delete"):
        assert perms2.get(f"metadata.glossary.{act}") is True
    assert perms2.get("metadata.enum.read") is False, "타 사전으로 함의 누출"
    # product/datasource 묶음 → 원자(+read/test 포함)
    perms3 = app._apply_permission_overrides({"product.manage", "datasource.manage"})
    for c in ("product.read", "product.create", "product.update", "product.delete",
              "datasource.read", "datasource.create", "datasource.update", "datasource.delete", "datasource.test"):
        assert perms3.get(c) is True, f"{c} 묶음 함의 실패"
    # DENY 우선: 묶음 보유 + 원자 DENY → 그 원자만 False (transitive 경유에도 존중)
    perms4 = app._apply_permission_overrides({"kb.ingest.manual"}, {"metadata.glossary.delete": "deny"})
    assert perms4.get("metadata.glossary.delete") is False, "DENY 가 transitive 함의에 밀림"
    assert perms4.get("metadata.glossary.update") is True


def test_r10_legacy_bundle_hidden_parity():
    """레거시 묶음 숨김 목록이 backend(web_context.LEGACY_BUNDLE_PERMISSIONS)·admin.js·app.js 3자 동치."""
    import web_context
    backend = set(web_context.LEGACY_BUNDLE_PERMISSIONS)
    # 함의 맵의 모든 묶음 키 = 숨김 목록 (숨기지 않은 묶음이 남으면 '통합 항목 잔존')
    assert backend == set(web_context._PERMISSION_BUNDLE_IMPLIES.keys())
    for fname in ("admin.js", "app.js"):
        text = (ADMIN_JS.parent / fname).read_text(encoding="utf-8")
        m = re.search(r"LEGACY_BUNDLE_PERMISSIONS = new Set\(\[(.*?)\]\)", text, re.DOTALL)
        assert m, f"{fname} 에 LEGACY_BUNDLE_PERMISSIONS 부재"
        fe = set(re.findall(r'"([^"]+)"', m.group(1)))
        assert fe == backend, f"{fname} 숨김 목록 불일치: {fe ^ backend}"
    # 모든 묶음 코드는 catalog 에 유효(기존 grant 하위호환) + FE 종속 트리에는 부재
    for code in backend:
        assert code in app.PERMISSION_CODES, f"{code} catalog 이탈"
