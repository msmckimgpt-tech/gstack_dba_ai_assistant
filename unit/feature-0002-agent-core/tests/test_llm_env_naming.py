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


# ── feature-0016 node-analysis-haiku: 그래프 관계 분석 전용 모델 ────────────────
def test_node_analysis_model_defaults_to_meta_edge_free(monkeypatch):
    """AGENT_NODE_ANALYSIS_MODEL 미설정 시 **claude-haiku-4-meta** 기본값.

    meta-llm-edge-free(2026-07-30, 사용자 결정 재확인 "로컬LLM은 특수목적 전용, 실제 개발용 작업은
    계정 연결 claude-code"): 종전 기본값 `claude-haiku-4-interactive` 는 litellm fallback 체인이
    **`edge-fallback`(로컬 gemma)로 끝나** 두 claude 계정이 401/429 면 능동 분석·클러스터 라벨이
    조용히 gemma 산출로 바뀌었다(그 산출물은 kv 캐시·시그니처를 통해 **영구히 남는다**).
    대화 답변의 `*-chat` 규약과 동일하게 edge 를 배제한 `-meta` alias(claude-corp → root 2계정)로 이관.
    AGENT_INSIGHT_MODEL=edge 여도 node analysis 는 이 값에 영향받지 않는다(분리 유지)."""
    monkeypatch.delenv("AGENT_NODE_ANALYSIS_MODEL", raising=False)
    monkeypatch.setenv("AGENT_INSIGHT_MODEL", "edge")  # insight 는 gemma 라도
    c = _reload_config()
    assert c.AGENT_NODE_ANALYSIS_MODEL == "claude-haiku-4-meta"   # 능동 분석·라벨은 edge-free meta
    assert c.AGENT_INSIGHT_MODEL == "edge"                        # 공유 안 함(분리 확인)


def test_node_analysis_model_env_override(monkeypatch):
    """운영에서 다른 모델로 바꾸려면 .env AGENT_NODE_ANALYSIS_MODEL override 가 우선."""
    monkeypatch.setenv("AGENT_NODE_ANALYSIS_MODEL", "claude-sonnet-4")
    c = _reload_config()
    assert c.AGENT_NODE_ANALYSIS_MODEL == "claude-sonnet-4"


def test_node_analysis_model_blank_env_falls_back_to_meta(monkeypatch):
    """빈 문자열/공백 override 는 기본값으로 폴백(빈 모델명 라우팅 방지)."""
    monkeypatch.setenv("AGENT_NODE_ANALYSIS_MODEL", "   ")
    c = _reload_config()
    assert c.AGENT_NODE_ANALYSIS_MODEL == "claude-haiku-4-meta"


def test_node_analysis_model_exported(monkeypatch):
    """from shared.config import * 로 llm.py 가 읽을 수 있게 __all__ 에 노출."""
    c = _reload_config()
    assert "AGENT_NODE_ANALYSIS_MODEL" in getattr(c, "__all__", [])


def teardown_module(module):
    """env 조작이 다른 테스트에 새지 않도록 config 를 깨끗이 reload."""
    _clear("LLM_MODEL", "OPENAI_MODEL", "AGENT_LLM_MAX_RETRIES", "AGENT_OPENAI_MAX_RETRIES",
           "AGENT_NODE_ANALYSIS_MODEL", "AGENT_INSIGHT_MODEL")
    importlib.reload(config)
