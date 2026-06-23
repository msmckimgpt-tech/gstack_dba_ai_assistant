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
    assert "console.manage" in role_src
    assert "_quota_upsert" in role_src
    assert "quota.role.update" in role_src
    acct_src = inspect.getsource(app.admin_set_account_quota)
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
