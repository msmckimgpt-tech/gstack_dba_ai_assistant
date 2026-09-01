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

#: 능력 신고 자격을 갖춘 러너의 `RunnerFeatures` 컬럼 값 (caps-trust-gate, 2026-09-01).
#:
#: 이 목록에 `caps_self_report` 가 없으면 서버는 능력 신고를 **화면에 그리지 않는다** —
#: 그것이 이 게이트의 요지다. 아래 대부분의 케이스는 「자격 있는 러너」를 전제하므로 여기서
#: 한 번 정의하고 공유한다(문자열을 케이스마다 적으면 게이트를 켜는 날 절반만 고쳐진다).
_TRUSTED_FEATURES = "console_jobs,caps_self_report"

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
    """`account_runner_profile` 이 읽는 한 줄만 돌려준다.

    ⚠ **행의 컬럼 수는 실제 질의와 맞춰야 한다.** TASK-20260831T100000 에서 그 질의가
    `(RunnerCapabilities,)` → `(RunnerCapabilities, RunnerFeatures, RunnerAgentVersion)` 로
    넓어졌는데, 더블이 1-tuple 을 계속 돌려주자 `row[1]` 이 IndexError 를 냈고 호출측의
    fail-soft 가 그것을 삼켜 **선택기가 조용히 숨겨졌다**. 실패가 조용했다는 것이 요점이다 —
    더블이 실제 질의보다 좁으면 "기능이 없다" 와 구분되지 않는다.
    """

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
        lambda: _FakeConn((json.dumps(_REPORT, ensure_ascii=False), _TRUSTED_FEATURES, "2026.08.31")))
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
    monkeypatch.setattr(appmod, "_connect_memory", lambda: _FakeConn(("[]", "", "")))
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

    monkeypatch.setattr(store, "account_runner_profile", _boom)
    monkeypatch.setattr(
        appmod, "_connect_memory",
        lambda: _FakeConn((json.dumps(_REPORT, ensure_ascii=False), _TRUSTED_FEATURES, "2026.08.31")))
    payload = client.get(ENDPOINT).json()
    assert payload["models"] == [], "조회 실패인데 목록이 채워졌다(추측)"
    assert payload["model_selector"] == "hidden"
    # 조회 실패는 「구 러너」가 **아니다** — 모르는 것을 단정해 갱신 안내를 띄우면, 일시적
    # DB 오류가 멀쩡한 사용자에게 틀린 지시를 준다.
    assert payload["runner_caps_stale"] is False, "조회 실패를 구 러너로 단정했다"


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
    # ⚠ caps_row 는 **3컬럼**이다 (capabilities, features, agent_version). TASK-20260831T100000
    #   에서 `account_runner_profile` 질의가 넓어졌고, 1-tuple 을 주면 `row[1]` 이 IndexError →
    #   호출측 fail-soft 가 삼켜 **선택기가 조용히 숨겨진다**(= 기본값 검사가 전부 None 을 본다).
    monkeypatch.setattr(
        appmod, "_connect_memory",
        lambda: _DefaultsConn(
            (json.dumps(_REPORT, ensure_ascii=False), _TRUSTED_FEATURES, "2026.08.31"),
            defaults_row))


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
        lambda: _FakeConn((json.dumps(_REPORT, ensure_ascii=False), _TRUSTED_FEATURES, "2026.08.31")))
    monkeypatch.setattr(store, "account_bridge_defaults", _boom)
    payload = client.get(ENDPOINT).json()
    assert payload["model_selector"] == "visible", "기본값 실패가 선택기를 통째로 지웠다"
    assert payload["default_model"] == "claude:opus"


# -- 모델 메뉴 그룹 트리 (사용자 결정 2026-08-31) --------------------------------


def test_model_menu_renders_a_group_tree():
    """플랫폼(런타임)별 **머리글 + 하위 항목** 으로 그린다.

    브리지 목록은 여러 CLI 가 섞여 있고 값도 `runtime:model` 이라, flat 목록에서는 어느
    플랫폼의 모델인지 배지 하나로만 구분됐다. 항목이 늘수록 그 구분이 눈에 안 들어온다.
    """
    import pathlib
    js = (pathlib.Path(__file__).resolve().parents[1]
          / "src" / "static" / "app" / "composer.js").read_text(encoding="utf-8")
    fn = js[js.index("function _renderComposerModelMenu("):]
    fn = fn[:fn.index("\nfunction ")]
    assert "composer-model-group-head" in fn, "그룹 머리글을 그리지 않는다"
    # 머리글은 **버튼이 아니다** — 고를 수 없는 것이 고를 수 있게 보이면 안 된다.
    head = fn[fn.index("const head = document.createElement"):]
    head = head[:head.index("menu.appendChild(head)")]
    assert 'createElement("div")' in head, "머리글이 버튼으로 만들어진다(선택 가능해 보인다)"
    assert '"presentation"' in head, "머리글이 메뉴 항목으로 노출된다(키보드 이동에 걸린다)"
    # 그룹이 하나도 없는 카탈로그(서버 LLM 모드)는 종전 flat 렌더 — 머리글 하나뿐인 트리는
    # 들여쓰기만 늘리고 아무것도 나누지 않는다.
    assert "const _grouped = models.some(_groupOf)" in fn, "그룹 유무를 보지 않는다"
    # 트리에서는 배지를 달지 않는다(머리글과 같은 말을 두 번 쓰지 않는다).
    assert "_grouped\n      || (!!group" in fn or "_grouped ||" in fn, (
        "그룹 배지가 머리글과 중복된 채 남는다")


def test_group_head_has_its_own_style():
    """머리글이 항목과 **시각적으로 구분**된다 — 클래스만 있고 스타일이 없으면 같은 줄로 읽힌다."""
    import pathlib
    css = (pathlib.Path(__file__).resolve().parents[1]
           / "src" / "static" / "css" / "chat.css").read_text(encoding="utf-8")
    assert ".composer-model-group-head {" in css, "머리글 스타일이 없다"
    block = css[css.index(".composer-model-group-head {"):]
    block = block[:block.index("}")]
    # 고를 수 없는 줄이라는 신호: 작고 흐리다.
    assert "font-size" in block and "color" in block


# -- 러너 지문 대조 (사용자 제보 2026-08-31: 「재설치했는데 그대로」) ----------------


def test_server_compares_the_deployed_runner_fingerprint():
    """서버가 **자기 배포본**의 지문을 알고, 러너 신고와 대조한다."""
    import routers.ai_tools as ai_tools

    deployed = ai_tools._deployed_runner_build()
    assert deployed, "배포본 지문을 못 읽는다 — 대조 자체가 성립하지 않는다"
    # 같은 지문이면 최신, 다르면 stale. 판정의 유일한 전제는 **배포본 지문을 아는가**다.
    same = ai_tools._runner_update_hint("2026.08.31", ["console_jobs"], deployed)
    diff = ai_tools._runner_update_hint("2026.08.31", ["console_jobs"], "0" * 12)
    assert same["stale_build"] is False and same["current"] is True
    assert diff["stale_build"] is True and diff["current"] is False
    assert diff["reason"], "다르다고만 하고 무엇을 할지 말하지 않는다"


def test_missing_fingerprint_is_stale_not_current():
    """지문 **부재**는 «같음» 이 아니라 «더 오래됨» 이다 (사용자 제보 2026-09-01, 4차 재발).

    종전 계약은 「양쪽을 다 알 때만 판정한다」였고 그래서 지문을 신고하지 않는 러너를
    `current: True` 로 통과시켰다. 그런데 **지문 신고 자체가 배포본의 일부**이므로 신고가
    없다는 것은 그 변경 이전 빌드라는 증거다 — fail-open 이 걸린 모집단이 정확히 「낡은
    러너」였다. 라이브 실측(2026-09-01): `RunnerBuild=''` 러너가 `current=True` 를 받는 동안
    화면에는 그 러너가 내장 표에서 신고한 `gpt-5.1-codex` 가 떠 있었다.
    """
    import routers.ai_tools as ai_tools

    none = ai_tools._runner_update_hint("2026.08.31", ["console_jobs"], "")
    assert none["stale_build"] is True, "지문을 신고하지 않는 구 러너를 최신으로 읽는다"
    assert none["current"] is False
    assert none["reason"], "구버전이라고 하면서 다음 행동을 말하지 않는다"


def test_staleness_predicate_has_exactly_one_home():
    """지문 판정은 **한 함수**뿐이다 — 하트비트와 연결 칩이 같은 것을 부른다 (§16.7 G8-a).

    같은 술어가 두 곳에 복제돼 있었고, 복제는 한쪽만 고쳐지는 순간 갈린다. 갈리면 「칩은
    초록인데 하트비트는 구버전이라 한다」는, 사용자가 어느 쪽도 믿을 수 없는 화면이 된다.
    """
    import pathlib

    import routers.ai_tools as ai_tools

    assert callable(getattr(ai_tools, "runner_build_is_stale", None)), "단일 판정 함수가 없다"
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "src" / "routers" / "oauth_as.py").read_text(encoding="utf-8")
    fn = src[src.index("def connect_status("):]
    fn = fn[:fn.index("\nreturn JSONResponse") if "\nreturn JSONResponse" in fn else len(fn)]
    assert "runner_build_is_stale(" in fn, "연결 칩이 자기 판정을 다시 적는다"
    # 복제의 흔적(직접 비교)이 남아 있으면 두 판정이 다시 갈린다.
    assert "!= _deployed" not in fn, "지문 비교가 이 파일에 다시 적혀 있다"


def test_deployed_fingerprint_unknown_is_not_a_false_alarm(monkeypatch):
    """배포본 지문을 **못 읽으면** 판정하지 않는다 — 모르는 것을 stale 로 부르지 않는다.

    이 방향의 fail-safe 는 위 fail-closed 와 모순되지 않는다: 게이트가 요구하는 것은 「기준을
    아는가」이고, 기준이 없으면 어떤 러너도 구버전으로 단정할 근거가 없다. 이것이 없으면
    파일 권한 하나로 전 사용자에게 거짓 갱신 지시가 나간다.
    """
    import routers.ai_tools as ai_tools

    monkeypatch.setattr(ai_tools, "_deployed_runner_build", lambda: "")
    assert ai_tools.runner_build_is_stale("") is False
    assert ai_tools.runner_build_is_stale("0" * 12) is False


# -- 능력 신고 자격 게이트 (사용자 제보 2026-09-01: 「연결한 AI 에 없는 모델이 뜬다」) ----
#
# 폴백을 제거한 러너를 배포해도 **사용자 머신의 러너를 우리가 갱신할 수는 없다.** 낡은 빌드가
# 자기 소스의 내장 표(`gpt-5.1-codex`)를 계속 신고했고 카탈로그가 그것을 그대로 그렸다.
# 이제 `caps_self_report` 를 신고한 러너의 목록만 화면에 나간다.


def test_untrusted_runner_report_is_not_rendered(client, signed_in, monkeypatch):
    """자격 없는 러너(구 빌드)의 목록은 **화면에 나가지 않는다**.

    저장된 값이 멀쩡한 JSON 이어도 그렇다 — 문제는 모양이 아니라 **출처**다. 그 목록이 AI 의
    응답인지 러너 소스에 적혀 있던 내장 표인지 서버는 구별할 수 없고, 구별할 수 없으면
    「목록의 출처는 연결된 AI」라는 이 기능의 계약이 화면에서 거짓이 된다.
    """
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    monkeypatch.setattr(
        appmod, "_connect_memory",
        # 구 러너: `console_jobs` 만 신고한다(`caps_self_report` 를 모른다).
        lambda: _FakeConn((json.dumps(_REPORT, ensure_ascii=False), "console_jobs", "2026.08.31")))
    payload = client.get(ENDPOINT).json()

    assert payload["models"] == [], "자격 없는 러너의 목록이 화면에 나갔다"
    assert not any("gpt-5.1" in json.dumps(m) for m in payload["models"])
    assert payload["model_selector"] == "hidden"
    assert payload["default_model"] is None, "고를 수 없는데 기본값을 말한다"


def test_untrusted_runner_says_why_and_what_to_do(client, signed_in, monkeypatch):
    """감추기만 하지 않고 **이유와 다음 행동**을 말한다.

    사유 없이 항목만 사라지면 사용자는 기능이 없어진 것으로 읽는다 — 앞선 cycle 이 정확히 그
    마찰(「모델·추론 강도가 안 보인다」)로 되돌아왔다. 상태는 문구가 아니라 **별도 불리언**으로
    준다(프런트가 문구를 파싱하면 문구를 다듬는 날 조용히 어긋난다).
    """
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    monkeypatch.setattr(
        appmod, "_connect_memory",
        lambda: _FakeConn((json.dumps(_REPORT, ensure_ascii=False), "console_jobs", "2026.08.31")))
    payload = client.get(ENDPOINT).json()

    assert payload["runner_caps_stale"] is True, "구 러너라는 사실이 값으로 나가지 않는다"
    assert payload["runner_download_url"].endswith("/static/agent/bridge_agent.py")
    reason = payload["model_selector_reason"]
    assert "다시 실행" in reason, "다음 행동을 말하지 않는다"
    # §16.8 UI copy budget — 안내는 한 문장이다(설명문으로 자라지 않게).
    assert len(reason) <= 80, f"안내가 예산을 넘었다({len(reason)}자)"


def test_no_runner_keeps_the_old_message_not_the_update_notice(client, signed_in, monkeypatch):
    """러너가 **없는** 것과 러너가 **낡은** 것은 다른 사실이다.

    둘을 한 문구로 뭉개면, 러너를 아예 켜지 않은 사람에게 「최신 실행 파일로 다시 실행」이라는
    (그 사람에게는 틀린) 지시가 나간다.
    """
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    payload = client.get(ENDPOINT).json()  # signed_in 기본 커넥션 = 러너 없음
    assert payload["runner_caps_stale"] is False
    assert "다시 실행" not in payload["model_selector_reason"]


def test_trusted_runner_is_unaffected(client, signed_in, monkeypatch):
    """자격 있는 러너는 **종전 그대로** 보인다 (§16.7 G9-c 정상 경로 실측).

    차단 게이트를 신설할 때 「정확히 발동하는가」만 보면, 정상 사용자를 막아 놓고 통과를
    선언하게 된다. 거짓양성의 대가는 정의상 정상 사용자가 치른다.
    """
    monkeypatch.delenv("AGENT_SERVER_LLM_ENABLED", raising=False)
    monkeypatch.setattr(
        appmod, "_connect_memory",
        lambda: _FakeConn((json.dumps(_REPORT, ensure_ascii=False), _TRUSTED_FEATURES, "2026.08.31")))
    payload = client.get(ENDPOINT).json()
    assert payload["model_selector"] == "visible"
    assert payload["runner_caps_stale"] is False
    assert [m["value"] for m in payload["models"]] == [
        "claude:opus", "claude:sonnet", "codex:gpt-5.1-codex"]


def test_gate_lives_in_the_store_so_every_consumer_inherits_it():
    """게이트는 **저장 계층의 관문**에 있다 — 소비처마다 걸지 않는다 (§16.7 G8-a).

    능력 소비처가 셋이다(카탈로그 · 저장 선택 복원 · 얇은 래퍼). 소비처마다 걸면 하나를
    빠뜨리는 순간 그 경로로 낡은 목록이 되살아난다 — 실제로 저장 선택 복원
    (`_bridge_model_offered`)은 카탈로그와 다른 파일에 있어 눈에 잘 띄지 않는다.
    """
    import oauth_store as _st

    # 자격 없는 features 를 준 행은 목록이 비어 나온다.
    class _Cur(_FakeCursor):
        pass

    untrusted = _st.account_runner_profile(
        _Cur((json.dumps(_REPORT, ensure_ascii=False), "console_jobs", "2026.08.31")), 1)
    assert untrusted["capabilities"] == [] and untrusted["caps_trusted"] is False
    assert untrusted["listening"] is True, "능력 게이트가 «연결됨» 까지 껐다"
    assert untrusted["features"] == ["console_jobs"], "능력 게이트가 콘솔 위임 자격까지 껐다"

    trusted = _st.account_runner_profile(
        _Cur((json.dumps(_REPORT, ensure_ascii=False), _TRUSTED_FEATURES, "2026.08.31")), 1)
    assert trusted["caps_trusted"] is True
    assert [r["runtime"] for r in trusted["capabilities"]] == ["claude", "codex"]

    # 얇은 래퍼와 저장 선택 복원이 같은 관문을 지난다.
    assert _st.account_runner_capabilities(
        _Cur((json.dumps(_REPORT, ensure_ascii=False), "console_jobs", "2026.08.31")), 1) == []


def test_connect_status_exposes_staleness_as_a_single_boolean():
    """프런트는 **불리언 하나만** 읽는다 — 판정을 두 벌로 만들지 않는다."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "src" / "routers" / "oauth_as.py").read_text(encoding="utf-8")
    fn = src[src.index("def connect_status("):]
    assert '"runner_stale": runner_stale,' in fn, "연결 상태에 구버전 사실이 없다"
    # 듣고 있을 때만 본다 — 러너가 없으면 지문을 비교할 대상 자체가 없다.
    assert "if listening:" in fn
    # 판정 실패가 **거짓 경고**가 되지 않는다 — 그리고 침묵하되 로그에는 남긴다
    # (완전히 침묵시켰더니 왜 판정이 안 서는지 추적할 수 없었다 — 실측 2026-08-31).
    _exc = fn[fn.index("except Exception:"):]
    _exc = _exc[:_exc.index("return JSONResponse")]
    assert "runner_stale = False" in _exc, "판정 실패가 거짓 경고로 나간다"
    assert "exc_info=True" in _exc, "실패를 완전히 침묵시켜 추적할 수 없다"


def test_chip_shows_a_distinct_state_for_stale_runner():
    """칩이 정상(초록)과 **구분되는** 상태를 보인다 — 색만 같으면 사실이 전달되지 않는다."""
    import pathlib
    base = pathlib.Path(__file__).resolve().parents[1] / "src" / "static"
    js = (base / "app" / "connect-modal.js").read_text(encoding="utf-8")
    assert 'el.dataset.state = "stale"' in js, "구버전 상태가 칩에 없다"
    assert "업데이트 필요" in js
    # 호출부가 서버 값을 실제로 넘긴다(배선 없이 분기만 있으면 영영 안 뜬다).
    assert "!!b.runner_stale" in js, "서버 값이 칩까지 도달하지 않는다"
    css = (base / "css" / "search-audit.css").read_text(encoding="utf-8")
    assert '.ai-conn[data-state="stale"]' in css, "스타일이 없어 정상 상태와 같아 보인다"


def test_frontend_actually_renders_the_hidden_reason():
    """사유가 **화면까지 도달한다** — 서버가 내려보내기만 하고 아무도 안 읽으면 무행위다.

    `model_selector_reason` 은 2026-08-28 부터 응답에 있었지만 **소비처가 0개**였다(실측).
    그래서 선택기가 사라진 화면은 이유를 말하지 못했고, 그 침묵이 앞선 cycle 의 제보
    (「모델·추론 강도가 안 보인다」)를 만들었다. 값의 존재와 도달은 다른 사실이다.
    """
    import pathlib

    base = pathlib.Path(__file__).resolve().parents[1] / "src" / "static"
    js = (base / "app" / "composer.js").read_text(encoding="utf-8")
    assert "composerActionsSelectorNote" in js, "사유를 그리는 코드가 없다"
    fn = js[js.index("function _applyComposerSelectorNote("):]
    fn = fn[:fn.index("\nfunction ")] if "\nfunction " in fn else fn
    assert "model_selector_reason" in fn, "서버 사유를 읽지 않는다(프론트가 문구를 짓는다)"
    # 숨김을 반영하는 경로에서 **실제로 불린다** (정의만 있고 호출이 없으면 영영 안 뜬다).
    apply_fn = js[js.index("function _applyComposerSelectorVisibility("):]
    apply_fn = apply_fn[:apply_fn.index("\n// feature-0043 caps-trust-gate")]
    assert "_applyComposerSelectorNote(" in apply_fn, "사유 갱신이 배선되지 않았다"
    # 보이는 상태에서는 비운다 — 목록이 돌아왔는데 "고를 수 없다" 가 남으면 그 자체가 거짓.
    assert "hidden ?" in fn or "hidden\n" in fn, "보이는 상태에서 사유를 지우지 않는다"
    # DOM 자리와 스타일이 실재한다(클래스만 있고 스타일이 없으면 항목처럼 보인다).
    html = (base / "index.html").read_text(encoding="utf-8")
    assert 'id="composerActionsSelectorNote"' in html, "사유를 담을 자리가 DOM 에 없다"
    css = (base / "css" / "chat.css").read_text(encoding="utf-8")
    assert ".composer-actions-note {" in css, "사유 스타일이 없어 메뉴 항목처럼 보인다"
