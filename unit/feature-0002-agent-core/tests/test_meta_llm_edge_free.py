"""meta-llm-edge-free (2026-07-30) — 개발용 메타데이터 LLM 이 로컬 모델로 강등되지 않음을 잠근다.

사용자 결정 재확인: "로컬LLM은 특수목적으로만 사용하고(야간, 업무 외 탐색) 실제 개발용 작업은 계정으로
연결된 claude-code 를 사용한다."

결함이었던 것: AI 능동 분석(`node_analysis`)·컨텐츠 클러스터 라벨(`cluster_label`)이 쓰는
`claude-haiku-4-interactive` 의 litellm fallback 체인이 **`edge-fallback`(로컬 gemma)로 끝났다**.
두 claude 계정이 401/429 면 그 산출물이 조용히 gemma 산출로 바뀌는데, 이 산출물은 **영구히 남는다**
(라벨은 kv 캐시 재사용 · 분석문은 시그니처에 섞여 클러스터 구조까지 오염). 라이브 실측으로 오염은
아직 없었으나(cluster_label 1,810회 전부 claude · node_analysis 의 edge 519회는 라우팅 분리 결정
2026-07-04 이전인 07-02), 구조적 경로가 열려 있었다.

규약: 대화 답변의 `*-chat`(2026-07-07 FR-edge-fallback)과 **동일** — 2계정까지만, edge 배제, 실패는 실패로.
배경 insight 배치의 야간·주말 gemma 강등은 **유지**(그것이 사용자가 말한 "특수목적").
"""
import pathlib

import pytest

yaml = pytest.importorskip("yaml")

# tests → feature-0002-agent-core → unit  (parents[2] = unit/)
CFG = pathlib.Path(__file__).resolve().parents[2] / \
    "feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml"


def _cfg():
    if not CFG.exists():
        pytest.skip(f"litellm config 부재: {CFG}")
    return yaml.safe_load(CFG.read_text())


def _fallbacks(d):
    out = {}
    for k in d:
        if isinstance(d[k], dict) and "fallbacks" in d[k]:
            for f in d[k]["fallbacks"] or []:
                out.update(f)
    return out


def _names(d):
    return [m["model_name"] for m in d.get("model_list", [])]


def test_meta_alias_registered_with_two_claude_accounts():
    d = _cfg()
    names = _names(d)
    assert "claude-haiku-4-meta" in names and "claude-haiku-4-meta-root" in names
    by = {m["model_name"]: m["litellm_params"] for m in d["model_list"]}
    # 두 별칭 모두 Anthropic 직결(로컬 게이트웨이 아님) + 서로 다른 계정 키
    for n in ("claude-haiku-4-meta", "claude-haiku-4-meta-root"):
        assert str(by[n]["model"]).startswith("anthropic/"), (n, by[n]["model"])
    assert by["claude-haiku-4-meta"]["api_key"] != by["claude-haiku-4-meta-root"]["api_key"]


def test_meta_chain_has_no_edge_fallback():
    """핵심 회귀 잠금: meta 체인 어디에도 edge/local 이 없어야 한다."""
    fb = _fallbacks(_cfg())
    chain = fb.get("claude-haiku-4-meta")
    assert chain == ["claude-haiku-4-meta-root"], chain
    # root 는 더 이상 폴백하지 않는다(실패는 실패로 — 호출측 fail-soft)
    assert fb.get("claude-haiku-4-meta-root") in (None, []), fb.get("claude-haiku-4-meta-root")
    for target in (chain or []):
        assert "edge" not in target and "local" not in target, target


def test_node_analysis_and_cluster_label_route_to_meta_alias():
    """능동 분석·클러스터 라벨의 모델 기본값이 edge-free meta alias 여야 한다."""
    import os
    if os.getenv("AGENT_NODE_ANALYSIS_MODEL"):
        pytest.skip("환경변수 override 존재 — 기본값 검증 대상 아님")
    from shared import config as _c
    assert _c.AGENT_NODE_ANALYSIS_MODEL == "claude-haiku-4-meta"
    # llm_cluster_label 이 같은 설정을 따라간다(별도 상수로 갈라지지 않음)
    import inspect

    from modules import llm as _llm
    src = inspect.getsource(_llm.llm_cluster_label)
    assert "AGENT_NODE_ANALYSIS_MODEL" in src


def test_background_insight_keeps_offhours_edge_downgrade():
    """사용자가 말한 '특수목적(야간·업무 외 탐색)' 은 그대로 유지 — 과잉 차단 금지."""
    fb = _fallbacks(_cfg())
    assert "edge-fallback" in (fb.get("claude-haiku-4") or []), \
        "배경 insight 배치의 off-hours gemma 강등은 2026-07-04 결정대로 유지된다"
    from shared import config as _c
    assert (_c.AGENT_INSIGHT_OFFHOURS_MODEL or "").strip(), "off-hours 모델 선언 유지"


def test_conversation_answer_chain_unchanged():
    """대화 답변의 edge-free 규약(2026-07-07)은 불변 — 본 변경이 건드리지 않았다."""
    fb = _fallbacks(_cfg())
    assert fb.get("claude-haiku-4-chat") == ["claude-haiku-4-chat-root"]
    for k, v in fb.items():
        if k.endswith("-chat") or k.endswith("-chat-root"):
            assert not any("edge" in x for x in (v or [])), (k, v)
