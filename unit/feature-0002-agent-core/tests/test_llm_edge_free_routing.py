"""llm-edge-free-routing (2026-07-30) — 자동 gemma(edge) 강등 경로가 **전무**함을 잠근다.

사용자 결정(2026-07-30): "더 이상 로컬 LLM 을 사용하지 않는다." 2026-07-04 의
llm-routing-interactive-split(배경 배치는 야간·주말 gemma 로 강등해 비용 절감)을 override 한다.

무엇이 결함이었나 — 라이브 실측(2026-07-30):
  · 18:00:27 bedrock-gateway 컨테이너 재생성 → 18:00:38~18:34:04 동안 컨테이너의 외부 DNS 해석이
    통째로 실패(`api.anthropic.com` / `raw.githubusercontent.com` 모두 `Temporary failure in name
    resolution`). 계정 quota·토큰 문제가 아니라 **도달성** 장애였다.
  · 그 34분간 `claude-haiku-4-interactive` 체인(= `.env` 의 OPENAI_MODEL + AGENT_*_MODEL 10종이
    가리키는 alias)이 끝의 `edge-fallback` 으로 흘러 **대화 보조 단계 전체가 gemma 로 서빙**됐다.
    edge 가 없는 `*-chat`·`*-meta` 는 500 으로 정직하게 실패했다 — 대조가 곧 이 테스트의 근거다.

계약 (두 층 모두):
  1. litellm fallback 체인 어디에도 `edge-fallback` 참조가 없다 (게이트웨이 층).
  2. `AGENT_INSIGHT_OFFHOURS_MODEL` 기본값이 빈 값이라 시각 기반 강등이 비활성이다 (앱 층).

강등 로직은 보존한다(운영자가 명시적으로 되돌릴 수 있게) — 이 테스트가 잠그는 것은
"기본 배포에서 자동으로 로컬 LLM 이 서빙되지 않는다" 이다.

⚠ local-llm-decommission (2026-09-07): `edge-fallback` **deployment 정의도 제거**됐다.
종전에는 "참조 0건이지만 정의는 되돌리기용으로 보존" 이 계약이었으나, 사용자 결정으로
local_llm 프로젝트 자체가 폐기(컨테이너 제거 + 모델 16GB 삭제)돼 그 정의의 `api_base` 가
가리키는 local-llm-gateway 가 존재하지 않는다. 즉 "복구 가능한 정의" 라는 전제가 소멸했다.
따라서 아래 `test_edge_deployment_absent` 는 **정의의 부재**를 잠근다 — 되살리려면
provider 복원(모델 재다운로드 ~16GB)이 선행되며, 그때 이 테스트를 함께 되돌린다.
"""
from _alias_transition import transition_contract_holds  # feature-0043: 전환 상태 대체 계약
import pathlib

import pytest

yaml = pytest.importorskip("yaml")

# tests → feature-0002-agent-core → unit  (parents[2] = unit/)
CFG = pathlib.Path(__file__).resolve().parents[2] / \
    "feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml"

_LOCAL_TOKENS = ("edge", "local", "gemma")


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


def test_no_fallback_chain_references_edge():
    """핵심 잠금 — 어떤 alias 의 폴백 대상에도 로컬 모델이 없다(신규 alias 추가 시에도 유지).

    이름 토큰(edge/local/gemma)만 보지 않는다 — `ollama-fallback` 처럼 토큰을 피한 로컬
    deployment 가 통과할 수 있기 때문이다. **폴백 대상의 실 provider 를 확인**한다:
    대상이 model_list 에 실재하고 그 `litellm_params.model` 이 `anthropic/` 이어야 한다
    (`openai/…` + 로컬 `api_base` 조합이 곧 로컬 게이트웨이 경유다).
    """
    # feature-0043(external-llm-bridge): 서버 계정 alias 가 주석 처리된 전환 상태에서는
    # 이 계약의 전제(체인 존재)가 없다. 그때는 대체 계약 — 활성 계정 라우팅이 0 이라는 것 —
    # 을 단정하고 종료한다(skip 아님). 주석을 해제해 되돌리면 아래 원 계약이 자동 복원된다.
    if transition_contract_holds(_cfg()):
        return
    d = _cfg()
    fb = _fallbacks(d)
    assert fb, "fallbacks 파싱 실패 — litellm_settings.fallbacks 위치를 확인할 것"
    by_name = {m["model_name"]: (m.get("litellm_params") or {}) for m in d.get("model_list", [])}

    name_offenders = [
        (src, tgt)
        for src, targets in fb.items()
        for tgt in (targets or [])
        if any(tok in str(tgt).lower() for tok in _LOCAL_TOKENS)
    ]
    assert not name_offenders, f"로컬 LLM 폴백 잔존(이름): {name_offenders}"

    for src, targets in fb.items():
        for tgt in (targets or []):
            params = by_name.get(tgt)
            assert params is not None, f"dangling fallback: {src} → {tgt} (model_list 에 없음)"
            model = str(params.get("model", ""))
            assert model.startswith("anthropic/"), \
                f"비-Anthropic 폴백 대상: {src} → {tgt} (model={model!r})"
            assert not params.get("api_base"), \
                f"폴백 대상이 별도 api_base 를 가짐(로컬 게이트웨이 의심): {src} → {tgt}"


def test_insight_and_interactive_chains_end_at_root():
    """두 계정까지만 — root 는 체인 종단(폴백 미등록)이라 실패가 실패로 올라간다."""
    # feature-0043(external-llm-bridge): 서버 계정 alias 가 주석 처리된 전환 상태에서는
    # 이 계약의 전제(체인 존재)가 없다. 그때는 대체 계약 — 활성 계정 라우팅이 0 이라는 것 —
    # 을 단정하고 종료한다(skip 아님). 주석을 해제해 되돌리면 아래 원 계약이 자동 복원된다.
    if transition_contract_holds(_cfg()):
        return
    fb = _fallbacks(_cfg())
    assert fb.get("claude-haiku-4") == ["claude-haiku-4-root"], fb.get("claude-haiku-4")
    assert fb.get("claude-haiku-4-interactive") == ["claude-haiku-4-interactive-root"], \
        fb.get("claude-haiku-4-interactive")
    for terminal in ("claude-haiku-4-root", "claude-haiku-4-interactive-root"):
        assert fb.get(terminal) in (None, []), (terminal, fb.get(terminal))


def test_edge_deployment_absent():
    """local-llm-decommission(2026-09-07) — edge-fallback 은 정의도 참조도 0건이어야 한다.

    종전 계약은 "정의는 되돌리기용으로 보존 + 참조 0" 이었다. 그 전제(정의만 살려 두면
    `fallbacks` 한 줄로 복구 가능)가 사용자 결정으로 소멸했다 — local_llm 프로젝트가 폐기돼
    `api_base: http://local-llm-gateway:8080/v1` 가 도달 불가다. 도달 불가 백엔드를 가리키는
    정의를 남기면 "복구 가능" 이라는 거짓 신호를 준다.

    ⚠ 전환 상태(feature-0043)에서 조기 return 하지 **않는다**. 이 단언은 계정 alias 활성
    여부와 무관하게 성립해야 하며, 조기 return 을 두면 전환 상태에서 영원히 검사되지 않는
    vacuous pass 가 된다(_alias_transition 모듈 docstring 의 논지와 동일).
    """
    d = _cfg()
    names = [str(m.get("model_name") or "") for m in (d.get("model_list") or [])]
    assert "edge-fallback" not in names, (
        "edge-fallback deployment 정의가 되살아났다 — local_llm provider 를 실제로 복원했다면 "
        "이 테스트도 함께 되돌릴 것(모듈 docstring 참조)"
    )
    referenced = {t for targets in _fallbacks(d).values() for t in (targets or [])}
    assert "edge-fallback" not in referenced, "정의가 없는데 라우팅 참조가 남아 있다 — dangling fallback"


def test_no_local_backend_api_base_in_model_list():
    """어떤 활성 deployment 도 로컬 백엔드(api_base)를 가리키지 않는다.

    이름 토큰(edge/local/gemma)을 피한 로컬 deployment 를 잡는 축이다 —
    `titan-embed` → `ollama/bge-m3` @ `http://embed-ollama:11434` 가 정확히 그 형태였고
    (이름에 로컬 토큰이 없다) 2026-09-07 에 제거됐다.
    """
    d = _cfg()
    offenders = []
    for m in (d.get("model_list") or []):
        params = m.get("litellm_params") or {}
        model = str(params.get("model") or "")
        api_base = str(params.get("api_base") or "")
        if model.startswith("ollama/") or "local-llm" in api_base or "embed-ollama" in api_base:
            offenders.append((m.get("model_name"), model, api_base))
    assert offenders == [], f"로컬 백엔드를 가리키는 활성 deployment 잔존: {offenders}"


def test_offhours_downgrade_disabled_in_effective_config():
    """앱 층 — **실효 설정**이 로컬 모델로 강등하지 않는다.

    ⚠ 이 테스트는 env override 가 있어도 skip 하지 않는다. 기본값만 검사하고 override 를
    skip 하면, 정작 운영 환경(`.env` 에 `AGENT_INSIGHT_OFFHOURS_MODEL=edge` 가 남은 상태)에서
    **통과해 버리는 vacuous pass** 가 된다 — 잠그려는 계약이 정확히 그 환경의 거동이다.
    따라서 (a) 미설정이면 기본값이 빈 값인지, (b) 설정돼 있으면 그 값이 로컬 모델이 아닌지를
    검사한다. 운영자가 claude alias 로 명시 지정하는 것은 허용(강등이 아니므로).
    """
    from shared import config as _c
    effective = (_c.AGENT_INSIGHT_OFFHOURS_MODEL or "").strip().lower()
    if effective == "":
        return  # 강등 비활성 — 계약 충족
    # 토큰 blocklist(edge/local/gemma)는 `ollama`·`mistral` 같은 다른 로컬 모델명을 놓친다.
    # allowlist 로 뒤집는다 — 값을 채울 거면 claude alias 여야 한다(그 외는 전부 거부).
    assert effective.startswith("claude"), (
        f"off-hours 강등 대상이 claude alias 가 아니다: {effective!r}. "
        "2026-07-30 사용자 결정(로컬 LLM 미사용) 위반 — 운영 .env 를 비울 것."
    )
    assert not any(tok in effective for tok in _LOCAL_TOKENS), \
        f"claude 접두를 달았으나 로컬 토큰 포함: {effective!r}"


def test_effective_insight_model_stays_claude_across_the_clock(monkeypatch):
    """강등 비활성 상태에서는 야간·주말·근무시간 어느 시각이든 base(claude)를 반환한다."""
    from datetime import datetime, timezone

    from modules import llm

    monkeypatch.setattr(llm, "AGENT_INSIGHT_MODEL", "claude-haiku-4", raising=False)
    monkeypatch.setattr(llm, "AGENT_INSIGHT_OFFHOURS_MODEL", "", raising=False)
    monkeypatch.setattr(llm, "AGENT_INSIGHT_BUSINESS_START_HOUR", 10, raising=False)
    monkeypatch.setattr(llm, "AGENT_INSIGHT_BUSINESS_END_HOUR", 19, raising=False)
    monkeypatch.setattr(llm, "AGENT_INSIGHT_BUSINESS_TZ_OFFSET_HOURS", 9, raising=False)

    # 경계 양측(G4): 근무시간 안(화 14:00 KST) · 직후(화 19:00 KST) · 심야(수 03:00 KST) · 주말(토 14:00 KST)
    for y, mo, d, h in ((2026, 7, 7, 5), (2026, 7, 7, 10), (2026, 7, 7, 18), (2026, 7, 4, 5)):
        assert llm._effective_insight_model(
            datetime(y, mo, d, h, tzinfo=timezone.utc)
        ) == "claude-haiku-4", (y, mo, d, h)
