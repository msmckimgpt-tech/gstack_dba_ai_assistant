"""feature-0043 전환 판정 — 서버 계정 alias 가 활성인가, 그리고 전환 상태의 대체 계약.

## 왜 필요한가

`test_llm_edge_free_routing` · `test_meta_llm_edge_free` ·
`test_conversation_answer_no_edge_alias` 는 **"계정 alias 체인이 존재하고, 그 체인이 로컬
gemma 로 흘러가지 않는다"** 를 잠근다(2026-07-30 라이브 장애의 회귀 방어). feature-0043
전환(2026-08-26)으로 그 체인 자체가 `litellm_config.yaml` 에서 주석 처리되면서, 전제가
사라진 상태로 기존 단정이 실패한다.

## 왜 skip 하지 않는가

`pytest.skip` 으로 넘기면 그 계약은 **전환된 환경에서 영원히 검사되지 않는다** — 되돌린 뒤에도
누가 skip 조건을 잘못 건드리면 조용히 통과한다(vacuous pass). 대신 **계약을 둘로 나눈다**:

- alias 활성(전환 전 / 되돌림 후) → 기존 edge-free 계약을 그대로 검사한다.
- alias 비활성(전환 상태)      → `assert_no_active_account_routing()` 이 "활성 체인이 정말로
  0 이다" 를 실질 단정한다. 누가 `fallbacks` 만 되살리면 여기서 잡힌다.

어느 쪽이든 무언가를 실제로 검사하며, 되돌리는 순간 원래 방어가 자동 복원된다.
"""
from __future__ import annotations

from typing import Any

__all__ = ["account_aliases_active", "assert_no_active_account_routing", "transition_contract_holds"]

_ACCOUNT_KEY_TOKENS = ("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY_ROOT")


def account_aliases_active(cfg: dict[str, Any]) -> bool:
    """서버 보유 계정(claude-corp/root) 자격증명을 쓰는 활성 deployment 가 있는가."""
    for entry in (cfg.get("model_list") or []):
        params = entry.get("litellm_params") or {}
        api_key = str(params.get("api_key") or "")
        if any(tok in api_key for tok in _ACCOUNT_KEY_TOKENS):
            return True
    return False


def assert_no_active_account_routing(cfg: dict[str, Any]) -> None:
    """전환 상태의 대체 계약 — 계정 라우팅이 **정말로** 남아 있지 않다.

    alias 만 주석하고 `fallbacks` 를 남기면 litellm 이 미정의 대상으로 라우팅을 시도해
    진단하기 어려운 실패가 된다. 둘이 함께 꺼져 있어야 한다.
    """
    settings = cfg.get("litellm_settings") or {}
    assert not (settings.get("fallbacks") or []), (
        "계정 alias 는 비활성인데 fallback 체인이 남아 있다 — "
        "litellm_config.yaml 의 fallbacks 도 함께 주석해야 한다"
    )
    names = [str(m.get("model_name") or "") for m in (cfg.get("model_list") or [])]
    leaked = [n for n in names if n.startswith("claude-")]
    assert leaked == [], f"계정 chat alias 가 활성으로 남아 있다: {leaked}"


def transition_contract_holds(cfg: dict[str, Any]) -> bool:
    """전환 상태면 대체 계약을 단정하고 True. 아니면 False(호출측이 기존 검사를 이어간다)."""
    if account_aliases_active(cfg):
        return False
    assert_no_active_account_routing(cfg)
    return True
