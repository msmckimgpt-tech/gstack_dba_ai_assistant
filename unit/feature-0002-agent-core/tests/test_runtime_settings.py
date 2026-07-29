"""feature-0018 runtime-settings — 레지스트리·resolver·스냅샷·검증 단위 테스트.

DB 불요(순수). 스냅샷 파일 I/O 는 tmp_path 로 격리한다. config.py 의 restart-mode 반영은
서브프로세스로 검증(모듈 전역 오염·재로딩 부작용 회피).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from shared import runtime_settings as rs


@pytest.fixture
def snap(tmp_path, monkeypatch):
    """격리된 스냅샷 경로 + 캐시 리셋 픽스처. write(dict) 로 override 를 쓴다."""
    path = tmp_path / "runtime_settings.json"
    monkeypatch.setenv("RUNTIME_SETTINGS_SNAPSHOT_PATH", str(path))
    monkeypatch.delenv("RUNTIME_SETTINGS_DISABLED", raising=False)
    # 리터럴-기본값 경로를 결정적으로 하려면 배포 env 변수를 비운다(운영 .env=300 오염 방지).
    for _k in ("AGENT_TIMEOUT_SEC", "MCP_TIMEOUT_SEC", "AGENT_DB_CONNECT_TIMEOUT_SEC"):
        monkeypatch.delenv(_k, raising=False)
    # 캐시 초기화(다른 테스트가 남긴 상태 격리).
    rs._cache["overrides"] = None
    rs._cache["loaded_at"] = 0.0
    rs._cache["frozen"] = None

    def _write(overrides):
        rs.write_snapshot(overrides)

    return _write


# ── 레지스트리 ──────────────────────────────────────────────────────────────
def test_registry_has_timeouts_and_model_budgets():
    reg = rs.serialize_registry({})
    assert len(reg["timeouts"]) >= 20, "현재 구성된 timeout 을 모두 등록해야 한다"
    # budget 계열(Haiku 등) thinking 모델마다 예산 항목이 자동 생성된다.
    keys = {m["key"] for m in reg["model_thinking_budgets"]}
    assert "model_thinking_budget:claude-haiku-4" in keys
    # sonnet-reasoning-budget-guide(2026-07-24): adaptive(Sonnet 5)는 effort 로 제어 →
    # 죽은 budget 스펙 미생성(admin UI 는 guide-note). adaptive_models 로 표면화.
    assert "model_thinking_budget:claude-sonnet-4" not in keys
    assert "claude-sonnet-4" in reg["adaptive_models"]
    assert "claude-haiku-4" not in reg["adaptive_models"]
    # opus5-model(2026-07-27): Opus 5 도 adaptive → 죽은 budget 스펙 미생성 + adaptive_models 표면화.
    # (신규 모델이 budget 스펙을 달고 들어오면 저장해도 무효과인 죽은 슬라이더가 다시 생긴다.)
    assert "model_thinking_budget:claude-opus-5" not in keys
    assert "claude-opus-5" in reg["adaptive_models"]
    # 총 출력(①)은 adaptive 도 live 로 읽히므로 모델별 스펙이 있어야 한다.
    assert "agent_max_output:claude-opus-5" in {m["key"] for m in reg["agent_max_outputs"]}


def test_flagship_timeout_is_live_mode():
    spec = rs.spec_for("AGENT_TIMEOUT_SEC")
    assert spec is not None and spec["apply_mode"] == "live"
    assert rs.spec_for("MCP_TIMEOUT_SEC")["apply_mode"] == "live"
    # 저수준 커넥션 timeout 은 restart 여야 한다(라이브 변경 위험 회피).
    assert rs.spec_for("AGENT_DB_CONNECT_TIMEOUT_SEC")["apply_mode"] == "restart"


def test_defaults_match_known_config_values():
    # config.py env 기본값과 동일해야 byte-동치가 보장된다(대표값 점검).
    assert rs.spec_for("AGENT_TIMEOUT_SEC")["default"] == 60
    assert rs.spec_for("MCP_TIMEOUT_SEC")["default"] == 20
    assert rs.spec_for("AGENT_DB_CONNECT_TIMEOUT_SEC")["default"] == 10


# ── resolver: get_int / clamp / override ────────────────────────────────────
def test_get_int_returns_default_without_snapshot(snap):
    assert rs.get_int("AGENT_TIMEOUT_SEC") == 60


def test_get_int_applies_override(snap):
    snap({"AGENT_TIMEOUT_SEC": 120})
    assert rs.get_int("AGENT_TIMEOUT_SEC") == 120


def test_get_int_env_fallback_when_no_override(snap, monkeypatch):
    # 회귀 가드(BLOCKING): 운영 .env(AGENT_TIMEOUT_SEC=300) 를 존중해야 한다. override 없으면
    # 스펙 리터럴(60) 이 아니라 env(300) 를 반환 — 그렇지 않으면 라이브 실행 timeout 이 300→60 회귀.
    monkeypatch.setenv("AGENT_TIMEOUT_SEC", "300")
    snap({})  # override 없음
    assert rs.get_int("AGENT_TIMEOUT_SEC") == 300


def test_get_int_override_beats_env(snap, monkeypatch):
    monkeypatch.setenv("AGENT_TIMEOUT_SEC", "300")
    snap({"AGENT_TIMEOUT_SEC": 90})
    assert rs.get_int("AGENT_TIMEOUT_SEC") == 90  # console override 가 env 를 이긴다


def test_serialize_default_reflects_env_baseline(snap, monkeypatch):
    monkeypatch.setenv("AGENT_TIMEOUT_SEC", "300")
    reg = rs.serialize_registry({})
    row = next(r for r in reg["timeouts"] if r["key"] == "AGENT_TIMEOUT_SEC")
    # default(초기화 기준) = env 배포값, code_default = 스펙 리터럴.
    assert row["default"] == 300 and row["code_default"] == 60 and row["effective"] == 300


def test_get_int_clamps_out_of_range(snap):
    snap({"AGENT_TIMEOUT_SEC": 10**9})
    assert rs.get_int("AGENT_TIMEOUT_SEC") == rs.spec_for("AGENT_TIMEOUT_SEC")["maximum"]
    snap({"AGENT_TIMEOUT_SEC": 1})  # below min 5
    assert rs.get_int("AGENT_TIMEOUT_SEC") == rs.spec_for("AGENT_TIMEOUT_SEC")["minimum"]


def test_disabled_killswitch_ignores_override(snap, monkeypatch):
    snap({"AGENT_TIMEOUT_SEC": 120})
    monkeypatch.setenv("RUNTIME_SETTINGS_DISABLED", "1")
    rs.invalidate_cache()
    assert rs.get_int("AGENT_TIMEOUT_SEC") == 60


# ── startup_int (config.py restart 경로 mechanism) ──────────────────────────
def test_startup_int_frozen_reads_snapshot(snap):
    snap({"AGENT_DB_CONNECT_TIMEOUT_SEC": 25})
    assert rs.startup_int("AGENT_DB_CONNECT_TIMEOUT_SEC", 10) == 25


def test_startup_int_falls_back_to_env_default(snap):
    # override 미설정 → env_default 그대로(byte-동치 보장).
    assert rs.startup_int("AGENT_DB_CONNECT_TIMEOUT_SEC", 10) == 10


def test_startup_int_unregistered_key_returns_env_default(snap):
    snap({"NOT_A_REAL_KEY": 5})
    assert rs.startup_int("NOT_A_REAL_KEY", 99) == 99


# ── model thinking budget override (B1 무회귀) ──────────────────────────────
def test_model_budget_override_none_without_setting(snap):
    # budget 계열(haiku) 미설정 → None → _call_llm 이 주입 안 함 → 모델 config 기본값 유지(B1).
    assert rs.model_thinking_budget_override("claude-haiku-4") is None


def test_model_budget_override_applies_and_clamps(snap):
    snap({"model_thinking_budget:claude-haiku-4": 9000})
    assert rs.model_thinking_budget_override("claude-haiku-4") == 9000
    snap({"model_thinking_budget:claude-haiku-4": 10**6})
    _max = rs.spec_for("model_thinking_budget:claude-haiku-4")["maximum"]
    assert _max == 62976  # haiku native(64000) - 1024
    assert rs.model_thinking_budget_override("claude-haiku-4") == _max  # native cap
    snap({"model_thinking_budget:claude-haiku-4": 10})
    assert rs.model_thinking_budget_override("claude-haiku-4") == 1024  # min (Anthropic)


def test_model_budget_override_adaptive_sonnet_is_dead(snap):
    # sonnet-reasoning-budget-guide(2026-07-24): adaptive(Sonnet 5)는 budget 스펙이 제거돼
    # 스냅샷에 값이 있어도 override 는 항상 None(effort 로 제어 — 죽은 컨트롤 봉인).
    assert rs.spec_for("model_thinking_budget:claude-sonnet-4") is None
    snap({"model_thinking_budget:claude-sonnet-4": 9000})
    assert rs.model_thinking_budget_override("claude-sonnet-4") is None


def test_model_budget_override_unknown_model_none(snap):
    snap({"model_thinking_budget:gpt-hypothetical": 5000})
    assert rs.model_thinking_budget_override("gpt-hypothetical") is None


# ── validate_value (endpoint PUT) ───────────────────────────────────────────
def test_validate_accepts_in_range():
    ok, val, err = rs.validate_value("AGENT_TIMEOUT_SEC", "90")
    assert ok and val == 90 and err is None


def test_validate_rejects_out_of_range():
    ok, val, err = rs.validate_value("AGENT_TIMEOUT_SEC", 2)
    assert not ok and val is None and "범위" in err


def test_validate_rejects_non_integer():
    ok, val, err = rs.validate_value("AGENT_TIMEOUT_SEC", "abc")
    assert not ok and "정수" in err


def test_validate_rejects_unregistered_key():
    ok, val, err = rs.validate_value("BOGUS_KEY", 5)
    assert not ok


def test_validate_rejects_bool():
    # bool 은 int 서브클래스지만 명시적으로 거부(오입력 방지).
    ok, val, err = rs.validate_value("AGENT_TIMEOUT_SEC", True)
    assert not ok


# ── 스냅샷 I/O ──────────────────────────────────────────────────────────────
def test_write_snapshot_roundtrip(snap, tmp_path):
    snap({"AGENT_TIMEOUT_SEC": 77})
    path = os.environ["RUNTIME_SETTINGS_SNAPSHOT_PATH"]
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["overrides"]["AGENT_TIMEOUT_SEC"] == 77


def test_missing_snapshot_is_fail_open(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_SETTINGS_SNAPSHOT_PATH", str(tmp_path / "nope.json"))
    # override 부재 시 baseline 은 **배포 env 우선**이 설계된 동작이다(_baseline_int docstring —
    # 운영 .env 의 AGENT_TIMEOUT_SEC=300 을 존중해야 config.py 와 byte-동치). 여기서 검증할 것은
    # "스냅샷 부재 → 폴백" 이므로 env 를 걷어내 스펙 리터럴 기준으로 본다. (종전엔 env 를 그대로
    # 둔 채 60 을 요구해, .env 를 상속하는 컨테이너 테스트 환경에서 상시 FAIL 이었다.)
    monkeypatch.delenv("AGENT_TIMEOUT_SEC", raising=False)
    rs.invalidate_cache()
    rs._cache["frozen"] = None
    assert rs.get_int("AGENT_TIMEOUT_SEC") == 60  # 부재 → 기본값


def test_serialize_timeout_row_shape(snap):
    # 렌더-임계 계약(적대 QA MEDIUM): timeout 행이 프론트가 읽는 필드를 모두 담아야 한다.
    reg = rs.serialize_registry({})
    row = next(r for r in reg["timeouts"] if r["key"] == "AGENT_TIMEOUT_SEC")
    for f in ("key", "category", "label", "description", "unit", "default", "code_default",
              "minimum", "maximum", "apply_mode", "effective", "has_override"):
        assert f in row, f"timeout row missing render field: {f}"


def test_serialize_model_row_shape(snap):
    reg = rs.serialize_registry({})
    # sonnet-reasoning-budget-guide: adaptive sonnet 제거 → budget 계열(haiku) 행으로 shape 검증.
    row = next(r for r in reg["model_thinking_budgets"] if r["model"] == "claude-haiku-4")
    for f in ("key", "model", "label", "default", "code_default", "minimum", "maximum",
              "apply_mode", "effective", "has_override", "default_known"):
        assert f in row, f"model row missing render field: {f}"
    assert row["default_known"] is True and row["default"] == 5000


def test_get_int_unregistered_ignores_snapshot_override(snap):
    # 방어(적대 security LOW): 미등록 키의 스냅샷 값은 신뢰하지 않는다.
    snap({"TOTALLY_UNREGISTERED_KEY": 12345})
    assert rs.get_int("TOTALLY_UNREGISTERED_KEY") == 0


def test_controlplane_connect_min_floor():
    # 가용성 foot-gun 방지(적대 security LOW): 컨트롤플레인 연결 timeout 최소 3초.
    assert rs.spec_for("AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC")["minimum"] == 3


def test_serialize_registry_marks_override(snap):
    reg = rs.serialize_registry({"AGENT_TIMEOUT_SEC": 111})
    row = next(r for r in reg["timeouts"] if r["key"] == "AGENT_TIMEOUT_SEC")
    assert row["has_override"] is True and row["effective"] == 111 and row["override_value"] == 111
    other = next(r for r in reg["timeouts"] if r["key"] == "MCP_TIMEOUT_SEC")
    assert other["has_override"] is False and other["effective"] == other["default"]


# ── config.py restart-mode 반영 (서브프로세스 — 모듈 재로딩 부작용 격리) ──────
def test_config_applies_restart_override_at_import(tmp_path):
    """config.py 가 import 시 스냅샷의 restart-mode override 를 상수에 반영하는지 검증."""
    snap_path = tmp_path / "rs.json"
    snap_path.write_text(json.dumps({"overrides": {"AGENT_DB_CONNECT_TIMEOUT_SEC": 27}}), encoding="utf-8")
    env = dict(os.environ)
    env["RUNTIME_SETTINGS_SNAPSHOT_PATH"] = str(snap_path)
    # 오버라이드 우선순위가 env 위임보다 위임 결과를 이겨야 하므로 env 는 미설정으로 둔다.
    env.pop("AGENT_DB_CONNECT_TIMEOUT_SEC", None)
    code = (
        "import shared.config as c; "
        "assert c.AGENT_DB_CONNECT_TIMEOUT_SEC == 27, c.AGENT_DB_CONNECT_TIMEOUT_SEC; "
        "print('OK')"
    )
    try:
        out = subprocess.run(
            [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60,
        )
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"config import subprocess unavailable: {exc}")
    if out.returncode != 0:
        # 런타임 의존(mysql.connector/rich/openai) 부재 환경이면 skip, 그 외는 실패.
        if "ModuleNotFoundError" in out.stderr or "ImportError" in out.stderr:
            pytest.skip(f"config deps unavailable: {out.stderr.strip().splitlines()[-1:]}" )
        raise AssertionError(f"config restart-apply failed:\nSTDOUT={out.stdout}\nSTDERR={out.stderr}")
    assert "OK" in out.stdout


# ── feature-0018 reasoning-budgets: 추론 강도별 예산 ──────────────────────────
def test_reasoning_budget_specs_low_high_max_normal_excluded(snap):
    reg = rs.serialize_registry({})
    rb = reg["reasoning_budgets"]
    # sonnet-reasoning-budget-guide(2026-07-24): adaptive(Sonnet 5)는 effort 로 제어 → budget 스펙
    # 미생성. budget 계열(haiku)만 남는다: 레벨 {low,high,max}, haiku × 3 = 3행. normal 제외(B1).
    assert {r["level"] for r in rb} == {"low", "high", "max"}
    assert {r["model"] for r in rb} == {"claude-haiku-4"}
    assert "claude-sonnet-4" not in {r["model"] for r in rb}
    assert len(rb) == 3
    # base default 는 모델 무관(low2000/high10000/max16000).
    by = {r["level"]: r for r in rb}
    assert by["low"]["default"] == 2000 and by["high"]["default"] == 10000 and by["max"]["default"] == 16000
    assert all(r["apply_mode"] == "live" and r["unit"] == "tokens" for r in rb)


def test_reasoning_budget_override_none_without_setting(snap):
    assert rs.reasoning_budget_override("claude-haiku-4", "high") is None
    assert rs.reasoning_budget_override("claude-haiku-4", "normal") is None   # 미등록(B1)
    assert rs.reasoning_budget_override("claude-haiku-4", "") is None
    assert rs.reasoning_budget_override("", "high") is None


def test_reasoning_budget_override_applies_and_clamps(snap):
    snap({"reasoning_budget:claude-haiku-4:high": 12000})
    assert rs.reasoning_budget_override("claude-haiku-4", "high") == 12000
    assert rs.reasoning_budget_override("claude-haiku-4", "HIGH") == 12000  # 대소문자 정규화
    snap({"reasoning_budget:claude-haiku-4:high": 10 ** 6})
    _max = rs.spec_for("reasoning_budget:claude-haiku-4:high")["maximum"]
    assert _max == 62976  # haiku native(64000) - 1024
    assert rs.reasoning_budget_override("claude-haiku-4", "high") == _max   # native cap
    snap({"reasoning_budget:claude-haiku-4:high": 10})
    assert rs.reasoning_budget_override("claude-haiku-4", "high") == 1024   # min(Anthropic)


def test_reasoning_budget_adaptive_sonnet_is_dead(snap):
    # sonnet-reasoning-budget-guide(2026-07-24): adaptive(Sonnet 5)는 reasoning_budget 스펙이
    # 제거돼 스냅샷에 값이 있어도 override 항상 None(effort 로 제어 — 죽은 컨트롤). haiku(budget)는
    # 독립적으로 적용된다(모델별 분리 계약 유지).
    snap({"reasoning_budget:claude-sonnet-4:max": 60000, "reasoning_budget:claude-haiku-4:max": 20000})
    assert rs.reasoning_budget_override("claude-sonnet-4", "max") is None   # 죽음(스펙 제거)
    assert rs.reasoning_budget_override("claude-haiku-4", "max") == 20000   # budget 계열은 유효


def test_reasoning_budget_validate_and_reset_registered(snap):
    ok, val, _ = rs.validate_value("reasoning_budget:claude-haiku-4:low", "2500"); assert ok and val == 2500
    ok, _, _ = rs.validate_value("reasoning_budget:claude-haiku-4:low", "500"); assert not ok  # < min 1024
    # sonnet-reasoning-budget-guide: adaptive sonnet 예산 스펙 제거 → 미등록(guide-note 전환).
    assert rs.spec_for("reasoning_budget:claude-sonnet-4:max") is None
    assert rs.spec_for("reasoning_budget:claude-sonnet-4:normal") is None    # normal 미등록
    assert rs.spec_for("reasoning_budget:high") is None    # 구 스킴(모델 없음) 미등록


# ── reasoning-budget-per-model: 모델별 총 출력(agent_max_output) ──────────────
def test_agent_max_output_registry_and_natives(snap):
    reg = rs.serialize_registry({})
    keys = {r["key"]: r for r in reg["agent_max_outputs"]}
    assert "agent_max_output:claude-sonnet-4" in keys
    assert "agent_max_output:claude-haiku-4" in keys
    assert keys["agent_max_output:claude-sonnet-4"]["maximum"] == 128000  # native
    assert keys["agent_max_output:claude-haiku-4"]["maximum"] == 64000
    assert keys["agent_max_output:claude-sonnet-4"]["default"] == 40000
    assert keys["agent_max_output:claude-haiku-4"]["default"] == 24000


def test_agent_max_output_override_and_clamp(snap):
    assert rs.agent_max_output("claude-sonnet-4") == 40000  # default(override 없음)
    snap({"agent_max_output:claude-sonnet-4": 100000})
    assert rs.agent_max_output("claude-sonnet-4") == 100000
    snap({"agent_max_output:claude-sonnet-4": 10 ** 7})
    assert rs.agent_max_output("claude-sonnet-4") == 128000  # native clamp
    snap({"agent_max_output:claude-sonnet-4": 100})
    assert rs.agent_max_output("claude-sonnet-4") == 4096     # min clamp


def test_serialize_reasoning_row_has_model_and_level(snap):
    reg = rs.serialize_registry({})
    # sonnet-reasoning-budget-guide: adaptive sonnet 제거 → budget 계열(haiku) 행으로 shape 검증.
    row = next(r for r in reg["reasoning_budgets"] if r["key"] == "reasoning_budget:claude-haiku-4:max")
    for f in ("key", "model", "level", "label", "default", "minimum", "maximum",
              "apply_mode", "effective", "has_override", "default_known"):
        assert f in row, f"reasoning row missing render field: {f}"
    assert row["model"] == "claude-haiku-4" and row["level"] == "max"


def test_old_reasoning_key_ignored_backward_compat(snap):
    # 구 스킴 override(reasoning_budget:{level})는 신 스킴에서 무시(fail-safe).
    snap({"reasoning_budget:max": 12000})
    assert rs.reasoning_budget_override("claude-sonnet-4", "max") is None
    assert rs.reasoning_budget_override("claude-haiku-4", "max") is None
