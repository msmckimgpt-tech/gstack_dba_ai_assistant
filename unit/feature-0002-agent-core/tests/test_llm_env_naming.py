"""TASK-0237 — LLM env 명명 정리 backward-compat 회귀 테스트.

OPENAI_* env 명명(GPT 잔재)을 LLM_* 로 이전하되, 운영 .env 의 구이름
(OPENAI_MODEL=auto 등)을 무중단 fallback 으로 읽어야 한다. 우선순위:
  LLM_MODEL > OPENAI_MODEL > "claude-sonnet-4"
  AGENT_LLM_MAX_RETRIES > AGENT_OPENAI_MAX_RETRIES > 0

config.py 의 소스 선택 술어가 깨지면 배포 끊김(운영 .env 호환 상실) → 회귀 방어.
"""

import importlib
import os
import sys

# conftest 가 src 를 sys.path 에 추가하지만, env 조작 후 reload 가 필요하므로 명시 import.
import shared.config as config


def _reload_config():
    return importlib.reload(config)


def _clear(*keys):
    for k in keys:
        os.environ.pop(k, None)


def test_llm_model_new_name_wins(monkeypatch):
    """LLM_MODEL 이 설정되면 OPENAI_MODEL 보다 우선한다."""
    monkeypatch.setenv("LLM_MODEL", "claude-haiku-4")
    monkeypatch.setenv("OPENAI_MODEL", "auto")
    c = _reload_config()
    assert c.OPENAI_MODEL == "claude-haiku-4"


def test_llm_model_falls_back_to_openai_model(monkeypatch):
    """LLM_MODEL 미설정 시 구이름 OPENAI_MODEL 을 fallback 으로 읽는다(운영 .env 호환)."""
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "auto")
    c = _reload_config()
    assert c.OPENAI_MODEL == "auto"


def test_llm_model_default_when_both_absent(monkeypatch):
    """둘 다 없으면 claude-sonnet-4 기본값."""
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    c = _reload_config()
    assert c.OPENAI_MODEL == "claude-sonnet-4"


def test_max_retries_new_name_wins(monkeypatch):
    """AGENT_LLM_MAX_RETRIES 가 구이름보다 우선."""
    monkeypatch.setenv("AGENT_LLM_MAX_RETRIES", "3")
    monkeypatch.setenv("AGENT_OPENAI_MAX_RETRIES", "1")
    c = _reload_config()
    assert c.AGENT_OPENAI_MAX_RETRIES == 3


def test_max_retries_falls_back_to_old_name(monkeypatch):
    """새 이름 미설정 시 구이름 fallback."""
    monkeypatch.delenv("AGENT_LLM_MAX_RETRIES", raising=False)
    monkeypatch.setenv("AGENT_OPENAI_MAX_RETRIES", "2")
    c = _reload_config()
    assert c.AGENT_OPENAI_MAX_RETRIES == 2


def test_openai_api_base_removed(monkeypatch):
    """TASK-0237: dead env OPENAI_API_BASE 는 config 에서 제거됐다(더 이상 노출 안 함)."""
    c = _reload_config()
    assert not hasattr(c, "OPENAI_API_BASE"), "OPENAI_API_BASE 가 아직 config 에 남아 있음"
    assert "OPENAI_API_BASE" not in getattr(c, "__all__", [])


def teardown_module(module):
    """env 조작이 다른 테스트에 새지 않도록 config 를 깨끗이 reload."""
    _clear("LLM_MODEL", "OPENAI_MODEL", "AGENT_LLM_MAX_RETRIES", "AGENT_OPENAI_MAX_RETRIES")
    importlib.reload(config)
