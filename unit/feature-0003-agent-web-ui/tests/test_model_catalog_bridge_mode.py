"""feature-0043 P0-Z3 — 브리지 모드의 모델 카탈로그 **반환값** 계약.

## 왜 반환값인가

같은 계약을 소스 문자열로도 잠갔지만(`feature-0043/tests/test_ux_parity.py`), 문자열 검사는
`if not server_llm_enabled():` 를 `if server_llm_enabled():` 로 뒤집는 **조건 반전**을 못 잡는다
(`shared/llm_gate.py` 의 이중 계약 주석 §2 가 지목한 바로 그 사각). 여기서는 실제 응답을 본다.

## 삼중 계약 (P0-T 의 이중 계약을 확장)

| 상태 | 응답 |
|---|---|
| 차단 + 러너 신고 **없음** | 목록 비고 `"hidden"` — P0-T 동작 그대로 |
| 차단 + 러너 신고 **있음** | 신고 목록 + `"visible"` + `model_selector_source: "runner"` |
| 해제(`AGENT_SERVER_LLM_ENABLED=1`) | 종전 서버 카탈로그 복원 + `"visible"` |

셋을 함께 검사해야 하는 이유: 첫 줄만 보면 "선택기 영구 제거" 뮤턴트가, 둘째 줄만 보면
"러너가 없는데도 선택기 노출" 이, 셋째 줄만 보면 "되돌릴 수 없는 전환" 이 각각 살아남는다.

## 미인증 응답은 불변

익명에게는 종전대로 빈 카탈로그만 나간다 — 게이트 상태라는 운영 사실조차 싣지 않는다
(routers/system.py 의 api-exposure-hardening 과 같은 방향).
"""
from __future__ import annotations

import json

import pytest

import app as appmod
import oauth_store as store

ENDPOINT = "/api/api-vault/options"

#: 러너가 실제로 신고하는 모양(= `bridge_agent.detect_runtimes()` 의 반환).
_REPORT = [
    {"runtime": "claude", "label": "Claude",
     "models": [{"value": "opus", "label": "Opus"}, {"value": "sonnet", "label": "Sonnet"}],
     "efforts": [{"value": "low", "label": "낮음"}, {"value": "xhigh", "label": "매우높음"}]},
    {"runtime": "codex", "label": "Codex",
     "models": [{"value": "gpt-5.1-codex", "label": "GPT-5.1 Codex"}],
     "efforts": [{"value": "high", "label": "높음"}]},
]


class _FakeCursor:
    """`account_runner_capabilities` 가 읽는 한 줄만 돌려준다."""

    def __init__(self, row):
        self._row = row

    def execute(self, *_args, **_kwargs) -> None:
        return None

    def fetchone(self):
        return self._row

    def close(self) -> None:
        return None


class _FakeConn:
    """카탈로그 핸들러가 쓰는 것은 `close()` 와 (브리지 모드에서) `cursor()` 뿐이다."""

    def __init__(self, caps_row=None):
        self._caps_row = caps_row

    def cursor(self):
        return _FakeCursor(self._caps_row)

    def close(self) -> None:
        return None


@pytest.fixture
def signed_in(monkeypatch):
    """이 핸들러는 DI seam 이 아니라 `app._get_authenticated_account(conn, request)` 를 직접 쓴다.

    그래서 conftest 의 `as_account`(dependency_overrides)로는 인증이 서지 않는다 — 여기서
    커넥션·인증·권한필터 세 지점을 직접 대역으로 바꾼다. 권한 필터는 통과시켜(목록 불변)
    **게이트 분기만** 관측 대상으로 남긴다.

    기본 커넥션은 **신고 없음**(러너 미연결)이다 — 신고를 세우는 테스트가 직접 갈아 끼운다.
    """
    monkeypatch.setattr(appmod, "_connect_memory", lambda: _FakeConn(None))
    monkeypatch.setattr(appmod, "_get_authenticated_account",
                        lambda conn, request: {"id": 1, "username": "tester", "permissions": {}})
    monkeypatch.setattr(appmod, "_filter_models_for_account_access",
                        lambda account, models, conn=None: list(models))


def test_blocked_gate_without_a_runner_hides_selector(client, signed_in, monkeypatch):
    """차단 + 러너 신고 없음 — 목록이 비고 숨김 신호가 실린다 (P0-T 동작 유지).

    이것이 P0-Z3 의 안전판이다: 고를 주체가 없으면 조작면도 없다. 러너 미연결·구 러너·
    `--cmd` 직접 지정이 전부 이 경로로 모인다.
    """
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    payload = client.get(ENDPOINT).json()
    assert payload["models"] == [], "고를 주체가 없는데 목록이 나간다"
    assert payload["model_selector"] == "hidden", (
        "숨김 신호가 없다 — 프론트는 빈 목록을 '로딩 중' 으로 읽어 사용자에게 영원한 스피너를 보인다")
    assert payload["server_llm_enabled"] is False
    assert payload["default_model"] is None, "고를 수 없는데 기본값을 말하면 화면이 그것을 표시한다"


def test_blocked_gate_with_a_runner_offers_what_the_runner_reported(
        client, signed_in, monkeypatch):
    """차단 + 러너 신고 있음 — **신고 그대로** 목록이 되고 선택기가 보인다 (P0-Z3 의 요지).

    값에 런타임이 접두되는 것이 계약이다(`claude:opus`). 한 머신에 여러 CLI 가 있을 때
    모델 이름만으로는 어느 것인지 정해지지 않고, 그 모호함이 러너에서 잘못된 실행이 된다.
    """
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    monkeypatch.setattr(
        appmod, "_connect_memory",
        lambda: _FakeConn((json.dumps(_REPORT, ensure_ascii=False),)))
    payload = client.get(ENDPOINT).json()

    assert payload["model_selector"] == "visible", "신고가 있는데 선택기가 숨겨진다"
    assert payload["model_selector_source"] == "runner", (
        "출처가 명시되지 않으면 프론트가 카탈로그 모양을 보고 추측하게 된다")
    assert [m["value"] for m in payload["models"]] == [
        "claude:opus", "claude:sonnet", "codex:gpt-5.1-codex"], (
        "값에 런타임이 접두되지 않는다 — 러너가 어느 CLI 로 실행할지 알 수 없다")
    # 그룹은 화면의 배지가 된다(런타임 라벨).
    assert {m["group"] for m in payload["models"]} == {"Claude", "Codex"}
    # 추론등급은 런타임마다 다르다 — 하나로 합치면 codex 에 없는 `xhigh` 가 뜬다.
    assert payload["reasoning_levels_by_runtime"]["claude"] == _REPORT[0]["efforts"]
    assert payload["reasoning_levels_by_runtime"]["codex"] == _REPORT[1]["efforts"]
    # 기본값은 **신고 목록 안**이어야 한다 (codex REV-20260828T170000 P1-2).
    # `None` 이면 프론트가 서버 기본값(haiku)으로 폴백하고, 사용자가 선택기를 건드리지 않고
    # 보낸 첫 질문에 그 alias 가 실려 굳는다 — 러너는 모르는 이름이라 버린다.
    assert payload["default_model"] == "claude:opus", (
        "기본 모델이 신고 목록에서 나오지 않는다 — 서버 alias 폴백 경로가 살아 있다")
    # 서버는 여전히 자기 모델을 부르지 않는다(이 응답이 그 사실을 바꾸지 않는다).
    assert payload["server_llm_enabled"] is False


def test_blocked_gate_with_an_empty_report_still_hides(client, signed_in, monkeypatch):
    """신고했지만 **고를 것이 없다**(빈 배열) — 숨김.

    `None`(신고 없음)과 `[]`(고를 것 없음)은 저장 계층에서 다른 사실이지만, 화면에서는 둘 다
    "선택기를 띄울 수 없다" 로 수렴해야 한다. 빈 목록으로 선택기를 띄우면 사용자는 빈 메뉴를 연다.
    """
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    monkeypatch.setattr(appmod, "_connect_memory", lambda: _FakeConn(("[]",)))
    payload = client.get(ENDPOINT).json()
    assert payload["models"] == []
    assert payload["model_selector"] == "hidden"


def test_blocked_gate_does_not_guess_when_the_report_is_unreadable(
        client, signed_in, monkeypatch):
    """능력 조회가 실패하면 **추측하지 않는다** — 빈 목록 + 숨김.

    권한 필터 실패는 fail-soft 로 전체 목록을 주지만(부트스트랩 경로), 러너 능력은 다르다:
    여기서 추측한 이름은 그 러너에 없을 수 있고, 고른 순간 반영되지 않는다.
    """
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(store, "account_runner_capabilities", _boom)
    monkeypatch.setattr(
        appmod, "_connect_memory",
        lambda: _FakeConn((json.dumps(_REPORT, ensure_ascii=False),)))
    payload = client.get(ENDPOINT).json()
    assert payload["models"] == [], "조회 실패인데 목록이 채워졌다(추측)"
    assert payload["model_selector"] == "hidden"


def test_reopened_gate_restores_selector(client, signed_in, monkeypatch):
    """게이트를 되돌리면 카탈로그가 **복원된다** — 이 전환은 제거가 아니라 조건부 숨김이다."""
    monkeypatch.setenv("AGENT_SERVER_LLM_ENABLED", "1")
    payload = client.get(ENDPOINT).json()
    assert payload["model_selector"] == "visible"
    assert payload["server_llm_enabled"] is True
    assert payload["default_model"], "복원 경로에서 기본 모델이 비었다"
    assert payload["models"], "복원 경로에서 목록이 비었다"


def test_anonymous_response_unchanged(client, monkeypatch):
    """미인증은 게이트 상태와 무관하게 빈 카탈로그 — 운영 사실을 익명에게 싣지 않는다."""
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    monkeypatch.setattr(appmod, "_connect_memory", lambda: _FakeConn())
    monkeypatch.setattr(appmod, "_get_authenticated_account", lambda conn, request: None)
    payload = client.get(ENDPOINT).json()
    assert payload == {"default_model": None, "models": []}


# -- 계정 기본값 (2026-08-31, 사용자 결정: 계정 기본값 + 대화별 override) ----------
#
# 대화별 저장만 있을 때는 새 대화를 열 때마다 목록 첫 항목으로 되돌아가, 사용자가 매번 다시
# 골라야 했다. 계정 기본값이 그 시작점을 정한다 — 단, **지금 신고된 목록 안에 있을 때만**.


class _DefaultsCursor(_FakeCursor):
    """능력 조회와 기본값 조회가 **같은 커서**를 쓴다 — SQL 로 갈라 각자의 행을 준다."""

    def __init__(self, caps_row, defaults_row):
        super().__init__(caps_row)
        self._defaults_row = defaults_row
        self._want = "caps"

    def execute(self, sql, *_args, **_kwargs) -> None:
        self._want = "defaults" if "BridgeDefaultModel" in str(sql) else "caps"

    def fetchone(self):
        return self._defaults_row if self._want == "defaults" else self._row


class _DefaultsConn(_FakeConn):
    def __init__(self, caps_row, defaults_row):
        super().__init__(caps_row)
        self._defaults_row = defaults_row

    def cursor(self):
        return _DefaultsCursor(self._caps_row, self._defaults_row)


def _with_defaults(monkeypatch, defaults_row):
    monkeypatch.setattr(
        appmod, "_connect_memory",
        lambda: _DefaultsConn((json.dumps(_REPORT, ensure_ascii=False),), defaults_row))


def test_account_default_becomes_the_starting_pick(client, signed_in, monkeypatch):
    """저장된 계정 기본값이 목록 첫 항목을 **대신한다**."""
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    _with_defaults(monkeypatch, ("codex:gpt-5.1-codex", "high"))
    payload = client.get(ENDPOINT).json()
    assert payload["default_model"] == "codex:gpt-5.1-codex"
    assert payload["default_reasoning_level"] == "high"


def test_stale_account_default_falls_back_to_the_offered_list(client, signed_in, monkeypatch):
    """러너를 바꿔 그 모델이 사라졌으면 **첫 항목으로 떨어진다**.

    대조 없이 내려보내면 화면은 "고를 수 없는 것이 선택돼 있는" 상태가 되고, 그 값으로 보낸
    질문은 러너가 버린다 — P0-T 가 지운 바로 그 형태다.
    """
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    _with_defaults(monkeypatch, ("gemini:gemini-2.5-pro", "ultra"))
    payload = client.get(ENDPOINT).json()
    assert payload["default_model"] == "claude:opus", "신고 밖 기본값이 그대로 나갔다"
    assert payload["default_reasoning_level"] == "", "신고 밖 등급이 그대로 나갔다"


def test_effort_default_is_checked_against_the_picked_runtime(client, signed_in, monkeypatch):
    """등급은 **고른 모델의 런타임** 목록으로 대조한다 — claude 의 `xhigh` 는 codex 에 없다."""
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    # 모델은 codex 인데 등급은 claude 어휘(`xhigh`) → 등급만 탈락한다.
    _with_defaults(monkeypatch, ("codex:gpt-5.1-codex", "xhigh"))
    payload = client.get(ENDPOINT).json()
    assert payload["default_model"] == "codex:gpt-5.1-codex"
    assert payload["default_reasoning_level"] == "", "다른 런타임의 등급이 통과했다"
    # 같은 런타임의 등급이면 그대로 선다.
    _with_defaults(monkeypatch, ("claude:opus", "xhigh"))
    assert client.get(ENDPOINT).json()["default_reasoning_level"] == "xhigh"


def test_defaults_failure_does_not_empty_the_catalog(client, signed_in, monkeypatch):
    """기본값 조회가 실패해도 **목록은 살아 있다** — 편의 기능이 선택기를 지우지 않는다."""
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)

    def _boom(*_a, **_k):
        raise RuntimeError("column missing")

    monkeypatch.setattr(
        appmod, "_connect_memory",
        lambda: _FakeConn((json.dumps(_REPORT, ensure_ascii=False),)))
    monkeypatch.setattr(store, "account_bridge_defaults", _boom)
    payload = client.get(ENDPOINT).json()
    assert payload["model_selector"] == "visible", "기본값 실패가 선택기를 통째로 지웠다"
    assert payload["default_model"] == "claude:opus"
