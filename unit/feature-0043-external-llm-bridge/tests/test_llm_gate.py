"""feature-0043 Step A — 서버 계정 LLM fail-closed 게이트 회귀 (AC-1 · AC-2 · AC-7 · AC-8).

이 스위트가 방어하는 것은 "차단이 **기본값**이고, 그 차단이 **실제 호출 경로 위에** 있다" 는 두 가지다.
전자만 보면 게이트 함수가 잘 동작해도 아무도 그것을 부르지 않는 배선 끊김을 놓친다 — 그래서
`_get_llm_client()` 가 None 을 반환할 때 **게이트를 경유했다는 사실**까지 단정한다
(자격증명 부재로 우연히 None 인 것과 구분되지 않으면 vacuous pass 가 된다).
"""
from __future__ import annotations

import pathlib
import re

import pytest

from shared import llm_gate

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
LITELLM_CFG = (
    REPO_ROOT
    / "unit"
    / "feature-0007-bedrock-llm-provider"
    / "src"
    / "config"
    / "litellm_config.yaml"
)

#: 전환 이전에 대화·보조·배치 경로가 쓰던 alias. 하나라도 살아 있으면 서버 계정이 새어 나간다.
ACCOUNT_ALIASES = [
    "claude-opus-5",
    "claude-opus-5-chat",
    "claude-opus-5-chat-root",
    "claude-sonnet-4",
    "claude-sonnet-4-chat",
    "claude-sonnet-4-chat-root",
    "claude-haiku-4",
    "claude-haiku-4-root",
    "claude-haiku-4-interactive",
    "claude-haiku-4-interactive-root",
    "claude-haiku-4-meta",
    "claude-haiku-4-meta-root",
    "claude-haiku-4-chat",
    "claude-haiku-4-chat-root",
]


@pytest.fixture(autouse=True)
def _clean_gate_env(monkeypatch):
    monkeypatch.delenv(llm_gate.SERVER_LLM_ENABLED_ENV, raising=False)
    llm_gate.reset_gate_cache_for_tests()
    yield
    llm_gate.reset_gate_cache_for_tests()


# ── AC-1: 게이트 기본값과 배선 ────────────────────────────────────────────────


def test_gate_default_is_blocked():
    """env 가 없으면 차단이다 — 설정 누락이 '열림' 으로 실패하지 않는다."""
    assert llm_gate.server_llm_enabled() is False


@pytest.mark.parametrize("val", ["1", "true", "TRUE", "yes", "on", " 1 "])
def test_gate_opens_on_truthy(monkeypatch, val):
    monkeypatch.setenv(llm_gate.SERVER_LLM_ENABLED_ENV, val)
    assert llm_gate.server_llm_enabled() is True


@pytest.mark.parametrize("val", ["", "0", "false", "no", "off", "maybe"])
def test_gate_stays_closed_on_non_truthy(monkeypatch, val):
    monkeypatch.setenv(llm_gate.SERVER_LLM_ENABLED_ENV, val)
    assert llm_gate.server_llm_enabled() is False


def test_get_llm_client_blocked_for_every_alias(monkeypatch):
    """AC-1 — 차단 상태에서 어떤 alias 로도 클라이언트가 나오지 않는다.

    단순히 `is None` 만 보면 자격증명 부재로 인한 None 과 구분되지 않으므로,
    **게이트 경유 사실**(`note_server_llm_blocked` 호출)을 함께 단정한다.
    """
    from modules import llm as llm_mod

    seen: list[str] = []
    monkeypatch.setattr(llm_mod, "note_server_llm_blocked", lambda caller: seen.append(caller))

    for alias in ACCOUNT_ALIASES:
        assert llm_mod._get_llm_client(model=alias) is None, f"{alias} 로 클라이언트가 생성됐다"

    assert len(seen) == len(ACCOUNT_ALIASES), "일부 alias 가 게이트를 경유하지 않았다"
    assert set(seen) == {"modules.llm._get_llm_client"}


def test_gate_open_does_not_short_circuit(monkeypatch):
    """뮤테이션 역검증 — 게이트를 열면 그 차단 경로를 타지 않는다.

    (자격증명이 없는 테스트 환경이라 결과는 여전히 None 일 수 있다. 여기서 단정하는 것은
    '게이트가 원인이 아니게 된다' 는 것 — 이게 성립해야 위 테스트가 게이트를 실제로 측정한 것이다.)
    """
    from modules import llm as llm_mod

    monkeypatch.setenv(llm_gate.SERVER_LLM_ENABLED_ENV, "1")
    seen: list[str] = []
    monkeypatch.setattr(llm_mod, "note_server_llm_blocked", lambda caller: seen.append(caller))

    llm_mod._get_llm_client(model="claude-haiku-4-chat")

    assert seen == [], "게이트가 열렸는데도 차단 경로를 탔다"


def test_agent_core_direct_client_path_is_gated():
    """`agent_core._run_agent_core` 도 게이트를 참조한다 — chokepoint 우회 경로 backstop.

    이 함수는 `modules.llm._get_llm_client` 를 타지 않고 `OpenAI(...)` 를 직접 만든다.
    게이트가 **그 생성부보다 앞에** 있어야 의미가 있으므로 순서까지 단정한다 — 뒤에 있으면
    클라이언트가 이미 만들어진 뒤라 차단이 늦다.
    """
    import inspect

    import agent_core

    src = inspect.getsource(agent_core._run_agent_core)
    assert "_server_llm_enabled()" in src, "_run_agent_core 가 게이트를 호출하지 않는다"
    assert "_server_llm_blocked_message()" in src, "차단 사유가 사용자 대면 결과에 실리지 않는다"

    gate_at = src.index("_server_llm_enabled()")
    client_at = src.index("client = OpenAI(")
    assert gate_at < client_at, "게이트가 클라이언트 생성부보다 뒤에 있다"


# ── AC-8: 정직한 실패 ────────────────────────────────────────────────────────


def test_blocked_call_is_logged(caplog):
    """무음 실패 금지 — 차단은 사유와 함께 로그에 남는다."""
    with caplog.at_level("WARNING", logger="shared.llm_gate"):
        llm_gate.note_server_llm_blocked("test.caller")
    assert "test.caller" in caplog.text
    assert "차단" in caplog.text


def test_blocked_log_is_throttled_per_caller(caplog):
    """같은 지점의 반복 차단은 60초 throttle — 진단을 가리는 로그 폭주를 막는다."""
    with caplog.at_level("WARNING", logger="shared.llm_gate"):
        for _ in range(5):
            llm_gate.note_server_llm_blocked("loop.caller")
    assert caplog.text.count("loop.caller") == 1


def test_blocked_message_is_user_facing():
    """사용자에게 그대로 노출해도 되는 문구 — 내부 식별자(alias·env 이름)를 담지 않는다."""
    msg = llm_gate.server_llm_blocked_message()
    assert msg and len(msg) > 20
    for internal in ("ANTHROPIC_API_KEY", "AGENT_SERVER_LLM_ENABLED", "claude-haiku", "litellm"):
        assert internal not in msg, f"내부 식별자 {internal} 가 사용자 대면 문구에 노출됐다"


# ── AC-2 / AC-7: 설정 자물쇠 ─────────────────────────────────────────────────


def _active_lines() -> list[str]:
    text = LITELLM_CFG.read_text(encoding="utf-8")
    return [ln for ln in text.split("\n") if ln.strip() and not ln.strip().startswith("#")]


def test_litellm_config_has_no_active_account_credential():
    """AC-2 — 계정 자격증명을 참조하는 **비주석** 라인이 0건이다."""
    offenders = [
        ln for ln in _active_lines()
        if "os.environ/ANTHROPIC_API_KEY" in ln
    ]
    assert offenders == [], f"활성 계정 alias 잔존: {offenders}"


def test_litellm_config_has_no_active_chat_alias():
    """대화·보조·배치 alias 가 전부 주석 상태다."""
    active_models = [
        m.group(1)
        for m in (re.match(r"^\s*-\s*model_name:\s*(\S+)", ln) for ln in _active_lines())
        if m
    ]
    leaked = [name for name in active_models if name in ACCOUNT_ALIASES]
    assert leaked == [], f"활성 chat alias 잔존: {leaked}"


def test_litellm_config_has_no_local_embedding_alias():
    """AC-7 **SUPERSEDED** (2026-09-07, local-llm-decommission) — 로컬 임베딩 alias 도 없다.

    종전 계약(AC-7, feature-0043 2026-08-26): `titan-embed`(→ 로컬 Ollama bge-m3)는 계정과
    무관하므로 **살아 있어야 한다** — "사용자가 요청한 것은 '계정 사용 차단' 이지 '임베딩 중단'
    이 아니다" 는 경계 고정이었다.

    그 경계가 사용자 결정으로 이동했다: **"로컬 LLM 은 더 이상 사용하지 않는다"(2026-09-07)** —
    계정 축이 아니라 *로컬 실행* 축의 결정이므로 임베딩도 포함된다. 따라서 백엔드
    `embed-ollama` 서비스와 이 alias 를 함께 제거했다.

    KB 검색은 죽지 않는다 — `kb_retrieval` 이 "쿼리 임베딩 미설정/실패 시 pg_trgm fallback"
    (2-tier, 롤백 안전)을 이미 구현하고 있어 **벡터 축만 강등**된다. 기존 임베딩
    (texts 154,365행)은 삭제하지 않았으므로 제공자 복구 시 그대로 재사용된다.
    """
    active_models = [
        m.group(1)
        for m in (re.match(r"^\s*-\s*model_name:\s*(\S+)", ln) for ln in _active_lines())
        if m
    ]
    assert "titan-embed" not in active_models, (
        "titan-embed alias 가 되살아났다 — 백엔드(embed-ollama)를 실제로 복원했다면 이 테스트도 "
        "함께 되돌릴 것(docstring 의 supersede 경위 참조)"
    )


def test_litellm_config_still_parses():
    """주석 처리 후에도 유효한 YAML 이고 필수 키가 살아 있다.

    ⚠ 종전 단언은 `assert doc.get("model_list")` — 즉 **비어 있지 않음**이었고 사유는
    "model_list 가 비었다 — 게이트웨이 기동 실패" 였다. 그 사유는 **가정이었고 실측으로
    반증됐다** (2026-09-07): `ghcr.io/berriai/litellm:main-stable` 을 `model_list: []` 로
    직접 기동해 `Application startup complete` + `/health/liveliness` 200 +
    `/health/readiness` 200 을 확인했다. 활성 모델 0개는 기동 실패 사유가 아니다.

    그래서 단언을 "비어 있지 않음" → **"키가 존재하고 리스트 타입"** 으로 옮긴다.
    지키려는 것은 `model_list:` 를 통째로 지워 YAML `null` 이 되는 상태(그건 파서 층에서
    다르게 취급될 수 있다)이지, 항목 수가 아니다. 항목 수 계약은 위
    `test_litellm_config_has_no_local_embedding_alias` 와 chat alias 테스트가 담당한다.
    """
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load(LITELLM_CFG.read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    assert "model_list" in doc, "model_list 키가 통째로 사라졌다 — YAML null 회귀"
    assert isinstance(doc["model_list"], list), (
        f"model_list 가 리스트가 아니다: {type(doc['model_list']).__name__} "
        "(빈 키로 두면 None 이 된다 — `model_list: []` 로 명시할 것)"
    )
    assert doc.get("general_settings", {}).get("master_key")


def test_litellm_config_documents_rollback():
    """되돌리기 절차가 파일 안에 남아 있다 — 주석 해제로 복구 가능함을 사람이 읽을 수 있어야 한다."""
    text = LITELLM_CFG.read_text(encoding="utf-8")
    assert "되돌리기" in text
    assert llm_gate.SERVER_LLM_ENABLED_ENV in text
