"""model-access-rbac (2026-07-28, Critical §12.3) — 계정/역할별 LLM 모델 사용 권한 단위 테스트.

사용자 요청("R2 도 계정/역할 별 권한 범위를 구성")으로 도입한 동적 RBAC 축.
`product.access.<key>` 와 동일 패턴(`WebPermissions` IsDynamic=1 / GroupName='model_access')이며
본 테스트는 **인가 결정의 불변식**을 고정한다:

  G1  코드 namespace — `model_permission_code` / `is_model_permission_code`.
  G2  `_account_has_model_access` 판정표 5분기 (핵심: row 등록 + 미보유 → **False** fail-closed).
  G3  부트스트랩 지연(권한 row 미등록) → 통과 + WARNING. "게이트 미설치"를 전원차단으로
      해석하면 신규 배포 첫 요청부터 모든 대화가 403 이 되는 더 큰 사고가 된다.
  G4  `conn=None` 우회 차단 — row 등록 여부를 확인할 수 없으면 미보유는 False.
  G5  `_filter_models_for_account_access` — 필터 + "전부 차단이면 원본 유지"(표시 관대·집행 엄격).
  G6  API 토큰(feature-0023) scope 면제 — 이미 발급된 토큰(Scopes='conversation.')이 죽지 않되,
      서비스 계정 권한이 없으면 여전히 차단된다.
  G7  `_ensure_model_access_permissions` — **신규 row 만** 전 역할 grant. 기존 row 는 grant 미변경
      (매 부트스트랩 re-grant 하면 관리자의 해제를 조용히 되살려 기능 자체가 무력화된다).
  G8  프론트 parity — admin.js / app.js 가 백엔드 GroupName 과 같은 그룹 키를 쓴다.

실행:
    python3 -m pytest unit/feature-0003-agent-web-ui/tests/test_model_access_rbac.py
"""
from __future__ import annotations

import os
import re
import sys

import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import web_context as wc  # noqa: E402
from shared.model_catalog import (  # noqa: E402
    API_DEFAULT_MODEL,
    MODEL_ACCESS_PERMISSION_GROUP,
    MODEL_ACCESS_PERMISSION_PREFIX,
    PUBLIC_API_MODEL_OPTIONS,
    is_model_permission_code,
    model_permission_code,
)

_STATIC = os.path.join(os.path.dirname(__file__), "..", "src", "static")


# ── 테스트 더블: 권한 row 등록 여부만 답하는 최소 conn ─────────────────────────────
class _Cur:
    def __init__(self, registered_codes, *, raise_on_execute=False):
        self._registered = set(registered_codes or ())
        self._raise = raise_on_execute
        self._row = None

    def execute(self, sql, params=None):
        if self._raise:
            raise RuntimeError("db down")
        code = (params or (None,))[0]
        self._row = (1,) if code in self._registered else None

    def fetchone(self):
        return self._row

    def close(self):
        pass


class _Conn:
    """`SELECT 1 FROM WebPermissions WHERE Code=%s` 만 답하는 fake."""

    def __init__(self, registered_codes=(), *, raise_on_execute=False):
        self._registered = registered_codes
        self._raise = raise_on_execute

    def cursor(self, *a, **kw):
        return _Cur(self._registered, raise_on_execute=self._raise)


def _acct(perms=None, **extra):
    a = {"id": 7, "Id": 7, "username": "tester", "permissions": dict(perms or {})}
    a.update(extra)
    return a


_OPUS = "claude-opus-5"
_HAIKU = "claude-haiku-4"
_OPUS_CODE = model_permission_code(_OPUS)
_HAIKU_CODE = model_permission_code(_HAIKU)


# ── G1: 코드 namespace ────────────────────────────────────────────────────────
def test_g1_model_permission_code_namespace():
    assert _OPUS_CODE == "model.access.claude-opus-5"
    assert _HAIKU_CODE == "model.access.claude-haiku-4"
    assert MODEL_ACCESS_PERMISSION_PREFIX == "model.access."
    assert MODEL_ACCESS_PERMISSION_GROUP == "model_access"
    # 빈 값은 빈 코드 — permissions.get("") 로 조용히 True 가 나오는 경로를 만들지 않는다.
    assert model_permission_code("") == ""
    assert model_permission_code(None) == ""
    assert is_model_permission_code(_OPUS_CODE) is True
    assert is_model_permission_code("product.access.kr") is False
    assert is_model_permission_code("conversation.ask") is False
    assert is_model_permission_code(None) is False
    # 카탈로그 전 모델이 코드로 매핑돼야 한다(신규 모델 추가 시 누락 감지).
    for item in PUBLIC_API_MODEL_OPTIONS:
        assert model_permission_code(item["value"]).startswith(MODEL_ACCESS_PERMISSION_PREFIX)


# ── G2: 판정표 — 보유/미보유 ──────────────────────────────────────────────────
def test_g2_granted_allows():
    acct = _acct({_OPUS_CODE: True})
    assert wc._account_has_model_access(acct, _OPUS, conn=_Conn([_OPUS_CODE])) is True


def test_g2_registered_but_not_granted_denies_fail_closed():
    """핵심 불변식 — 관리자가 해제한 모델은 차단된다(권한 row 는 등록된 상태)."""
    acct = _acct({_HAIKU_CODE: True})  # haiku 만 보유, opus 해제됨
    conn = _Conn([_OPUS_CODE, _HAIKU_CODE])
    assert wc._account_has_model_access(acct, _OPUS, conn=conn) is False
    assert wc._account_has_model_access(acct, _HAIKU, conn=conn) is True


def test_g2_explicit_false_override_denies():
    """계정 override 로 '거부'(False) 가 박힌 경우도 차단 — .get 이 False 를 반환."""
    acct = _acct({_OPUS_CODE: False})
    assert wc._account_has_model_access(acct, _OPUS, conn=_Conn([_OPUS_CODE])) is False


def test_g2_no_account_denies():
    assert wc._account_has_model_access(None, _OPUS, conn=_Conn([_OPUS_CODE])) is False


def test_g2_empty_model_denies():
    acct = _acct({_OPUS_CODE: True})
    assert wc._account_has_model_access(acct, "", conn=_Conn([_OPUS_CODE])) is False
    assert wc._account_has_model_access(acct, None, conn=_Conn([_OPUS_CODE])) is False


def test_g2_uncatalogued_model_is_not_this_gates_business():
    """카탈로그 밖 model 은 본 게이트 대상 아님 → True.

    허용 여부는 `_is_allowed_api_model`(400) 이 판정하는 별 축이다. 여기서 False 를 주면 같은
    실패가 400/403 두 갈래로 갈려 진단이 흐려진다(축 분리 계약).
    """
    acct = _acct({})
    assert wc._account_has_model_access(acct, "gpt-9-turbo", conn=_Conn([])) is True
    assert wc._account_has_model_access(acct, "edge", conn=_Conn([])) is True


# ── G3: 부트스트랩 지연 (권한 row 미등록) ─────────────────────────────────────
def test_g3_unregistered_permission_row_passes_with_warning(caplog):
    """seed 전 창에서 strict-deny 하면 전 대화 403 — 통과시키되 WARNING 을 남긴다."""
    acct = _acct({})
    with caplog.at_level("WARNING"):
        assert wc._account_has_model_access(acct, _OPUS, conn=_Conn([])) is True
    assert any("model-access" in r.message or "model-access" in r.getMessage()
               for r in caplog.records), "게이트 미설치 통과가 조용히 일어나면 안 된다"


def test_g3_db_error_passes_with_warning(caplog):
    """등록 여부 조회 실패 → 미설치일 수도 있으니 통과 + WARNING(조용한 전원차단 금지)."""
    acct = _acct({})
    with caplog.at_level("WARNING"):
        assert wc._account_has_model_access(acct, _OPUS, conn=_Conn([], raise_on_execute=True)) is True
    assert caplog.records, "DB 오류 통과가 무기록이면 안 된다"


# ── G4: conn=None 우회 차단 ───────────────────────────────────────────────────
def test_g4_conn_none_denies_when_not_granted():
    """row 등록 여부를 확인할 수 없으면 미보유는 거부 — conn 없이 호출해 게이트를 우회 못 한다."""
    acct = _acct({})
    assert wc._account_has_model_access(acct, _OPUS, conn=None) is False
    # 보유하고 있으면 conn 없이도 통과(등록 여부를 볼 필요가 없다).
    assert wc._account_has_model_access(_acct({_OPUS_CODE: True}), _OPUS, conn=None) is True


# ── G5: 카탈로그 표시 필터 ────────────────────────────────────────────────────
def _catalog():
    return [dict(m) for m in PUBLIC_API_MODEL_OPTIONS]


def test_g5_filter_removes_unpermitted_models():
    acct = _acct({_HAIKU_CODE: True})
    conn = _Conn([model_permission_code(m["value"]) for m in PUBLIC_API_MODEL_OPTIONS])
    out = wc._filter_models_for_account_access(acct, _catalog(), conn=conn)
    values = [m["value"] for m in out]
    assert _HAIKU in values
    assert _OPUS not in values


def test_g5_filter_keeps_original_when_everything_denied(caplog):
    """전부 차단이면 원본 유지 + WARNING — 빈 선택기로 원인 불명 상태를 만들지 않는다.

    집행은 `/api/ask` 게이트가 담당하므로 표시만 관대(display-permissive · backend-enforced).
    """
    acct = _acct({})
    conn = _Conn([model_permission_code(m["value"]) for m in PUBLIC_API_MODEL_OPTIONS])
    with caplog.at_level("WARNING"):
        out = wc._filter_models_for_account_access(acct, _catalog(), conn=conn)
    assert [m["value"] for m in out] == [m["value"] for m in PUBLIC_API_MODEL_OPTIONS]
    assert caplog.records


def test_g5_filter_noop_without_account_or_models():
    assert wc._filter_models_for_account_access(None, _catalog()) == _catalog()
    assert wc._filter_models_for_account_access(_acct({}), []) == []


# ── G6: API 토큰 scope 면제 (feature-0023 무회귀) ──────────────────────────────
def test_g6_api_token_model_access_is_scope_exempt():
    """이미 발급된 토큰(Scopes='conversation.')이 모델 권한을 잃지 않는다.

    면제하지 않으면 scope 문자열에 model.access. 가 없는 모든 기존 토큰이 /api/ask 403 으로
    죽는다(feature-0023 외부 AI 경로 파손). scope 는 '동작' 축, 모델은 '계정 역할' 축.
    """
    acct = _acct(
        {"conversation.ask": True, _HAIKU_CODE: True, _OPUS_CODE: True},
        _auth_via="api_token",
        _token_scopes=["conversation."],
    )
    perms = wc._account_permissions(acct)
    assert perms["conversation.ask"] is True
    assert perms[_HAIKU_CODE] is True, "scope 면제 실패 — 기존 토큰이 모델 권한을 잃는다"
    assert perms[_OPUS_CODE] is True


def test_g6_api_token_still_bounded_by_account_permissions():
    """면제는 scope 축만 — 서비스 계정 역할이 모델을 보유하지 않으면 토큰도 못 쓴다."""
    acct = _acct(
        {"conversation.ask": True, _HAIKU_CODE: True, _OPUS_CODE: False},
        _auth_via="api_token",
        _token_scopes=["conversation."],
    )
    perms = wc._account_permissions(acct)
    assert perms[_HAIKU_CODE] is True
    assert perms[_OPUS_CODE] is False, "계정 미보유 모델이 토큰에서 살아나면 안 된다"


def test_g6_api_token_hard_denylist_still_absolute():
    """모델 면제가 절대 denylist(관리/교차계정)를 흔들지 않는다."""
    acct = _acct(
        {"console.access": True, "conversation.list.any": True, _OPUS_CODE: True},
        _auth_via="api_token",
        _token_scopes=None,  # 안전 기본 allowlist
    )
    perms = wc._account_permissions(acct)
    assert perms["console.access"] is False
    assert perms["conversation.list.any"] is False
    assert perms[_OPUS_CODE] is True  # 모델은 면제 대상


def test_g6_non_token_account_unaffected():
    acct = _acct({_OPUS_CODE: True, "console.access": True})
    perms = wc._account_permissions(acct)
    assert perms[_OPUS_CODE] is True and perms["console.access"] is True


# ── G7: 부트스트랩 seeder — 신규 row 만 전 역할 grant ─────────────────────────
class _SeedCur:
    """INSERT IGNORE rowcount / SELECT Id 를 흉내내는 fake cursor."""

    def __init__(self, state):
        self.st = state
        self.rowcount = 0
        self._row = None

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split())
        # model-access-seed-fix(2026-07-28): ★ placeholder/param **arity 단정**.
        # 이 fake 가 arity 를 검증하지 않아, placeholder 5개에 파라미터 4개를 넘긴 버그가 단위
        # 테스트를 통과하고 라이브에서 `ProgrammingError: Not enough parameters` 로 터졌다
        # (부트스트랩 seed 단계 skip → 권한 row 미생성 → 기능 조용한 미적용). 실 드라이버가
        # 하는 검사를 더블도 하게 만들어 같은 계열 결함이 다시 새지 않게 한다.
        n_ph = s.count("%s")
        n_pa = 0 if params is None else len(params)
        assert n_ph == n_pa, (
            f"SQL placeholder({n_ph}) != params({n_pa}) — 실 mysql 드라이버는 "
            f"ProgrammingError 를 던진다. SQL: {s[:120]}"
        )
        if s.startswith("INSERT IGNORE INTO WebPermissions"):
            code = params[0]
            if code in self.st["existing_codes"]:
                self.rowcount = 0            # 이미 존재 → 신규 아님
            else:
                self.st["existing_codes"].add(code)
                self.st["inserted_codes"].append(code)
                self.rowcount = 1
        elif s.startswith("SELECT Id FROM WebPermissions"):
            code = params[0]
            self._row = (abs(hash(code)) % 100000 + 1,) if code in self.st["existing_codes"] else None
        elif s.startswith("INSERT IGNORE INTO WebRolePermissions"):
            pid = params[0]
            self.st["granted_permission_ids"].append(pid)
            self.rowcount = self.st["role_count"]
        else:
            self.rowcount = 0

    def fetchone(self):
        return self._row

    def close(self):
        pass


class _SeedConn:
    def __init__(self, existing_codes=(), role_count=3):
        self.state = {
            "existing_codes": set(existing_codes),
            "inserted_codes": [],
            "granted_permission_ids": [],
            "role_count": role_count,
        }

    def cursor(self, *a, **kw):
        return _SeedCur(self.state)


def _seeder():
    sys.path.insert(0, _SRC) if _SRC not in sys.path else None
    from routers import _bootstrap_schema  # noqa: PLC0415
    return _bootstrap_schema._ensure_model_access_permissions


def test_g7_first_bootstrap_seeds_and_grants_all_roles():
    seed = _seeder()
    conn = _SeedConn(existing_codes=(), role_count=4)
    added = seed(conn)
    expected_codes = [model_permission_code(m["value"]) for m in PUBLIC_API_MODEL_OPTIONS]
    assert sorted(conn.state["inserted_codes"]) == sorted(expected_codes)
    # 신규 row 마다 grant 1회 — 사용자 결정 "전부 기본 부여"(무회귀).
    assert len(conn.state["granted_permission_ids"]) == len(expected_codes)
    assert added == len(expected_codes) * (1 + 4)  # perm row + role grants


def test_g7_second_bootstrap_does_not_regrant():
    """★ 핵심 회귀 가드 — 재기동이 관리자의 해제를 되살리면 기능 자체가 무의미해진다."""
    seed = _seeder()
    existing = [model_permission_code(m["value"]) for m in PUBLIC_API_MODEL_OPTIONS]
    conn = _SeedConn(existing_codes=existing, role_count=4)
    added = seed(conn)
    assert conn.state["inserted_codes"] == []
    assert conn.state["granted_permission_ids"] == [], (
        "기존 권한 row 에 re-grant 가 발생했다 — 다음 배포가 관리자의 모델 해제를 무효화한다"
    )
    assert added == 0


def test_g7_newly_added_model_gets_granted_only_for_itself():
    """모델을 나중에 추가하면 그 모델만 신규 grant(같은 정책 일관 적용)."""
    seed = _seeder()
    existing = [
        model_permission_code(m["value"])
        for m in PUBLIC_API_MODEL_OPTIONS
        if m["value"] != _OPUS
    ]
    conn = _SeedConn(existing_codes=existing, role_count=2)
    seed(conn)
    assert conn.state["inserted_codes"] == [_OPUS_CODE]
    assert len(conn.state["granted_permission_ids"]) == 1


# ── G8: 프론트 parity (백엔드 GroupName ↔ admin.js / app.js) ───────────────────
def _read_static(name):
    with open(os.path.join(_STATIC, name), encoding="utf-8") as fh:
        return fh.read()


@pytest.mark.parametrize("fname", ["admin.js", "app.js"])
def test_g8_frontend_group_key_parity(fname):
    src = _read_static(fname)
    assert f'"{MODEL_ACCESS_PERMISSION_GROUP}"' in src or f"{MODEL_ACCESS_PERMISSION_GROUP}:" in src, (
        f"{fname} 에 백엔드 GroupName '{MODEL_ACCESS_PERMISSION_GROUP}' 매핑이 없다 → 권한 grid 에서 '기타' 로 떨어진다"
    )
    # 운영 권한(operate) section 에 포함돼야 한다(관리 권한이 아님 — 작업 화면에서 쓰는 권한).
    m = re.search(r'id:\s*"operate".*?groups:\s*\[([^\]]*)\]', src, re.S)
    assert m and MODEL_ACCESS_PERMISSION_GROUP in m.group(1), (
        f"{fname} operate section 에 {MODEL_ACCESS_PERMISSION_GROUP} 누락"
    )


def test_g8_admin_grid_does_not_exclude_model_access_as_dynamic():
    """excludeDynamic 은 product_access 전용으로 좁혀져야 한다 — 아니면 모델 row 가 grid 에서 사라진다."""
    src = _read_static("admin.js")
    assert 'excludeDynamic && permission.is_dynamic && permission.group === "product_access"' in src, (
        "excludeDynamic 이 is_dynamic 전체를 제외하면 model.access.* 가 권한 grid 에 렌더되지 않는다"
    )


def test_g8_app_js_maps_model_access_prefix():
    """app.js 는 prefix 추론(head='model')이 라벨 맵에 없어 '기타'로 떨어지므로 명시 매핑 필수."""
    src = _read_static("app.js")
    assert 'startsWith("model.access.")' in src


# ── 기본 모델은 여전히 haiku (비용 회귀 가드) ──────────────────────────────────
def test_default_model_unchanged():
    assert API_DEFAULT_MODEL == "claude-haiku-4"


# ── G9: seed SQL arity + 컬럼 길이 클립 (model-access-seed-fix 2026-07-28) ─────
def test_g9_seed_clips_label_and_description_to_column_limits(monkeypatch):
    """Label VARCHAR(128) / Description VARCHAR(255) 초과 시 1406 으로 seed 단계가 죽는다.

    `_ensure_permission_catalog` 가 graph-perm-split 배포에서 같은 fragility 를 실측하고 남긴
    경고와 동일 축 — 모델 label 이 길어져도 부트스트랩이 무너지지 않게 클립을 계약으로 고정한다.
    """
    from shared import model_catalog as mc

    long_label = "X" * 400
    fake_catalog = ({"value": "claude-verylong-1", "label": long_label},)
    monkeypatch.setattr(mc, "PUBLIC_API_MODEL_OPTIONS", fake_catalog, raising=True)

    captured = {}

    class _Cap:
        rowcount = 1

        def execute(self, sql, params=None):
            s2 = " ".join(str(sql).split())
            # arity 는 위 _SeedCur 와 동일하게 여기서도 단정.
            assert s2.count("%s") == (0 if params is None else len(params))
            if s2.startswith("INSERT IGNORE INTO WebPermissions"):
                captured["label"] = params[1]
                captured["desc"] = params[2]
                captured["is_dynamic"] = params[4]

        def fetchone(self):
            return (1,)

        def close(self):
            pass

    class _C:
        def cursor(self, *a, **kw):
            return _Cap()

    _seeder()(_C())
    assert len(captured["label"]) <= 128, "Label 이 컬럼 길이를 초과하면 1406 으로 seed 가 죽는다"
    assert len(captured["desc"]) <= 255, "Description 이 컬럼 길이를 초과하면 1406 으로 seed 가 죽는다"
    assert captured["is_dynamic"] == 1, "IsDynamic 이 바인딩되지 않으면 동적 권한으로 인식되지 않는다"
