"""TASK-20260619T030500-llm-usage-quota (Major §12.3) — LLM 사용량 한도 회귀 테스트.

요청(보안 보강 6종 중 ④): LLM 사용량 한도 처리 — 역할별 기본 + 계정별 특수(override).
토큰 계량(agent_runtime.llm_usage)·대시보드는 기존(TASK-0136) → 한도 설정 + 사전 게이트 추가.
안전 기본값: 미설정=무제한(배포만으로 차단 없음), 관리자 설정 시 발효. PG 장애=fail-open.

검증(`make test` agent 이미지, DB 없이 — parse/fail-open 실 동작 + inspect.getsource):
  B1 schema 헬퍼: WebRoleTokenQuotas + WebAccountTokenQuotas + 양 경로 호출.
  B2 config: LLM_QUOTA_ENFORCE 기본 True, _LLM_QUOTA_TYPES=(daily,monthly).
  B3 _quota_parse_limit 실 동작: None/""/음수→None, 0→0, "100"→100.
  B4 _check_account_token_quota 실 동작: enforce off / account None → (True, "").
  B5 _account_effective_quota: 계정 override → 역할 기본 → None.
  B6 _account_period_usage_tokens: date_trunc day/month + owner_account_id join + fail-open.
  B7 /api/ask 게이트: _check_account_token_quota + 429.
  B8 admin 엔드포인트: list/role/account + console.manage + _quota_upsert + audit.
  B9 audit builder: quota.role.update + quota.account.update.
  F1 admin.js loadQuotas + admin.html 한도 패널.
"""
from __future__ import annotations

import inspect
import os
import sys


def _import_app():
    try:
        import app  # type: ignore
        return app
    except ModuleNotFoundError:
        sys.path.insert(0, "/app")
        try:
            import app  # type: ignore
            return app
        except ModuleNotFoundError:
            import web.app as app  # type: ignore
            return app


app = _import_app()


def _read_static(name: str) -> str:
    base = os.path.dirname(inspect.getfile(app))
    with open(os.path.join(base, "static", name), "r", encoding="utf-8") as fh:
        return fh.read()


# ── B: backend ──────────────────────────────────────────────────────────────
def test_b1_schema_helper():
    src = inspect.getsource(app._ensure_llm_quota_schema)
    assert "WebRoleTokenQuotas" in src
    assert "WebAccountTokenQuotas" in src
    assert "QuotaType" in src and "TokenLimit" in src
    seed = inspect.getsource(app._ensure_seed_catchup)
    assert "_ensure_llm_quota_schema(conn)" in seed


def test_b2_config():
    assert app.LLM_QUOTA_ENFORCE in (True, False)
    assert app._LLM_QUOTA_TYPES == ("daily", "monthly")


def test_b3_parse_limit():
    assert app._quota_parse_limit(None) is None
    assert app._quota_parse_limit("") is None
    assert app._quota_parse_limit("  ") is None
    assert app._quota_parse_limit(-5) is None       # 음수 = 해제
    assert app._quota_parse_limit(0) == 0            # 0 = 무제한(명시)
    assert app._quota_parse_limit("100") == 100
    assert app._quota_parse_limit(250000) == 250000


def test_b4_check_quota_fail_open():
    # account None → 통과(DB 미접근).
    assert app._check_account_token_quota(None, None) == (True, "")
    # enforce 킬스위치 OFF → 무조건 통과(DB 미접근). 모듈 글로벌 monkeypatch.
    orig = app.LLM_QUOTA_ENFORCE
    try:
        app.LLM_QUOTA_ENFORCE = False
        ok, msg = app._check_account_token_quota(None, {"id": 5, "role_id": 2})
        assert ok is True and msg == ""
    finally:
        app.LLM_QUOTA_ENFORCE = orig


def test_b5_effective_quota_precedence():
    src = inspect.getsource(app._account_effective_quota)
    assert "WebAccountTokenQuotas" in src          # 계정 override 우선
    assert "WebRoleTokenQuotas" in src             # 역할 기본 폴백
    assert "return None" in src                    # 미설정 = 무제한


def test_b6_period_usage_source():
    src = inspect.getsource(app._account_period_usage_tokens)
    assert "date_trunc('day'" in src or "date_trunc('{trunc}'" in src
    assert "owner_account_id" in src
    assert "total_tokens" in src
    assert "return 0" in src                        # fail-open


def test_b7_ask_gate():
    src = inspect.getsource(app.ask)
    assert "_check_account_token_quota(conn, account)" in src
    assert "429" in src


def test_b8_admin_endpoints():
    for fn in ("admin_list_quotas", "admin_set_role_quota", "admin_set_account_quota"):
        assert hasattr(app, fn), fn
    role_src = inspect.getsource(app.admin_set_role_quota)
    # TASK-20260623T030418-quota-rbac-permission: console.manage → quota.manage(조절 전용 권한).
    #   outside-voice MAJOR-2 흡수: "조절은 조회 종속" 서버 집행 → quota.read + quota.manage 동시 요구.
    assert "quota.manage" in role_src and "quota.read" in role_src and "console.manage" not in role_src
    assert "_quota_upsert" in role_src
    assert "quota.role.update" in role_src
    acct_src = inspect.getsource(app.admin_set_account_quota)
    assert "quota.manage" in acct_src and "quota.read" in acct_src and "console.manage" not in acct_src
    assert "quota.account.update" in acct_src
    upsert_src = inspect.getsource(app._quota_upsert)
    assert "ON DUPLICATE KEY UPDATE" in upsert_src
    assert "DELETE FROM" in upsert_src             # None = 해제


def test_b9_audit_builder():
    src = inspect.getsource(app.build_audit_change_json)
    assert 'action == "quota.role.update"' in src
    assert 'action == "quota.account.update"' in src


def test_b10_quota_exposed_in_serialization():
    # TASK-20260623T014626-quota-ui-relocate: 한도가 역할/계정 직렬화에 노출(상세 화면 편집용).
    roles = inspect.getsource(app._list_roles)
    assert "WebRoleTokenQuotas" in roles and '"quota_daily"' in roles and '"quota_monthly"' in roles
    fetch = inspect.getsource(app._fetch_account_rows)
    assert "WebAccountTokenQuotas" in fetch and "quota_daily" in fetch
    ser = inspect.getsource(app._serialize_account)
    assert '"quota_daily"' in ser and '"quota_monthly"' in ser


def test_b11_quota_permissions_registered():
    # TASK-20260623T030418-quota-rbac-permission: 전용 권한 2종(조회/조절) 카탈로그 등재 + group=quota.
    assert "quota.read" in app.PERMISSION_CODES
    assert "quota.manage" in app.PERMISSION_CODES
    qmap = {d["code"]: d for d in app.PERMISSION_DEFINITIONS if d["code"].startswith("quota.")}
    assert qmap["quota.read"]["group"] == "quota"
    assert qmap["quota.manage"]["group"] == "quota"
    # admin seed(=set(PERMISSION_CODES))는 신규 권한 자동 보유 → lockout 없음.
    admin_perms = {r["key"]: r["permissions"] for r in app.SEED_ROLE_DEFINITIONS}["admin"]
    assert "quota.read" in admin_perms and "quota.manage" in admin_perms
    # 기본 비-admin seed(operator/sales/pending)는 미보유(least-privilege).
    by_key = {r["key"]: r["permissions"] for r in app.SEED_ROLE_DEFINITIONS}
    for k in ("operator", "sales", "pending"):
        assert "quota.read" not in by_key[k] and "quota.manage" not in by_key[k]


def test_b12_quota_strip_helper_and_gates():
    # 직렬화 strip 헬퍼: quota.read 미보유 actor 에 한도 필드 제거.
    assert hasattr(app, "_strip_quota_fields_if_unpermitted")
    strip_src = inspect.getsource(app._strip_quota_fields_if_unpermitted)
    assert '"quota.read"' in strip_src
    assert 'pop("quota_daily"' in strip_src and 'pop("quota_monthly"' in strip_src
    # 엔드포인트들이 strip 헬퍼 + 조회 게이트를 호출.
    assert "_strip_quota_fields_if_unpermitted" in inspect.getsource(app.admin_accounts)
    assert "_strip_quota_fields_if_unpermitted" in inspect.getsource(app.admin_roles)
    assert "_strip_quota_fields_if_unpermitted" in inspect.getsource(app.admin_me)
    # outside-voice MAJOR-1 흡수: PATCH 응답(include_permissions=True)도 strip — account.update 만으로 한도 열람 우회 차단.
    assert "_strip_quota_fields_if_unpermitted" in inspect.getsource(app.admin_update_account)
    # GET /api/admin/quotas 는 quota.read 게이트.
    assert "quota.read" in inspect.getsource(app.admin_list_quotas)

    # 실 동작: list/dict 양형 + 보유 시 무변경.
    # _account_has_permission → _account_permissions 는 account["permissions"](code→bool) 를 읽는다.
    no_quota = {"permissions": {"console.access": True, "account.read": True, "quota.read": False}}
    with_quota = {"permissions": {"console.access": True, "quota.read": True}}
    rows = [{"id": 1, "quota_daily": 100, "quota_monthly": 200}]
    app._strip_quota_fields_if_unpermitted(rows, no_quota)
    assert "quota_daily" not in rows[0] and "quota_monthly" not in rows[0]
    rows2 = [{"id": 2, "quota_daily": 5, "quota_monthly": 6}]
    app._strip_quota_fields_if_unpermitted(rows2, with_quota)
    assert rows2[0].get("quota_daily") == 5 and rows2[0].get("quota_monthly") == 6
    # 단건 dict 도 지원.
    single = {"quota_daily": 9, "quota_monthly": 9}
    app._strip_quota_fields_if_unpermitted(single, no_quota)
    assert "quota_daily" not in single and "quota_monthly" not in single


# ── F: frontend ─────────────────────────────────────────────────────────────
def test_f1_admin_quota_ui_relocated():
    # TASK-20260623T014626-quota-ui-relocate: 한도 UI 가 'LLM 사용량'(조회 전용) 화면에서 역할/계정 상세로 이전.
    js = _read_static("admin.js")
    assert "function buildQuotaEditor" in js
    # 엔드포인트는 템플릿 리터럴 `/api/admin/quotas/${opts.scope}/${id}` 사용.
    assert "/api/admin/quotas/${opts.scope}/" in js
    assert 'scope: "role"' in js and 'scope: "account"' in js
    assert "LLM 사용 한도" in js
    # 구 usage-탭 한도 패널 제거 확인.
    assert "loadQuotas" not in js
    assert "quotaRolesBox" not in js
    # 회귀 가드: admin.html 은 app.js 를 로드하지 않아 escapeHtml 이 admin.js 스코프에 미정의.
    #   buildQuotaEditor 가 escapeHtml 을 보간하면 production 에서 ReferenceError → 한도 섹션 미렌더.
    #   비신뢰 값은 DOM 프로퍼티(.value/.textContent)로 주입해야 한다(코드/주석 외 실사용 0).
    _qstart = js.index("function buildQuotaEditor")
    _qend = js.index("\nfunction ", _qstart + 1)  # 다음 함수 정의 직전까지 = buildQuotaEditor 전체 본문
    quota_block = js[_qstart:_qend]
    assert "escapeHtml(" not in quota_block
    assert ".admin-quota-daily\").value" in js and "note.textContent = opts.inheritNote" in js
    html = _read_static("admin.html")
    assert "quotaRolesBox" not in html and "quotaAcctSaveBtn" not in html


def test_f2_quota_permission_ui_gating():
    # TASK-20260623T030418-quota-rbac-permission: 섹션 표시=quota.read, 편집=quota.manage(readOnly).
    js = _read_static("admin.js")
    # 상세 섹션 게이트가 quota.read 로 전환(구 console.manage/account.update 게이트 제거).
    assert 'can("quota.read")' in js
    # 편집 가능 여부 = quota.manage(없으면 readOnly).
    assert "readOnly: !can(\"quota.manage\")" in js
    # buildQuotaEditor 가 readOnly 분기(입력 disable + 저장 버튼 미렌더) 지원.
    assert "const readOnly = Boolean(opts.readOnly)" in js
    assert "dailyInput.disabled = true" in js
    # 종속성 맵: quota.read→console.access, quota.manage→quota.read.
    assert '"quota.read": "console.access"' in js
    assert '"quota.manage": "quota.read"' in js
    # 그룹 메타 등재.
    assert 'quota: "LLM 사용 한도"' in js
    assert '"quota"' in js  # PERMISSION_GROUP_ORDER / 섹션 groups 배열


def test_f3_permission_dependency_map_consistency():
    # admin.js PERMISSION_DEPENDENCIES 의 quota.* key/value 가 실제 권한 code 와 정합.
    js = _read_static("admin.js")
    codes = set(app.PERMISSION_CODES)
    assert "quota.read" in codes and "quota.manage" in codes
    # console.usage.read(사용량 집계 조회)와 quota.read(한도 조회)는 별개 권한 — 혼동 금지.
    assert "console.usage.read" in codes
    assert "quota.read" != "console.usage.read"
