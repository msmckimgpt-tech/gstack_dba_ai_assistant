---
doc_type: FEATURE_DECISIONS
feature_id: feature-0007-bedrock-llm-provider
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-001
- Status:
- Date:
- Context:
- Decision:
- Consequences:
- Supersedes:
- Superseded By:

## ADR-002 — 용도별 모델 라우팅 분리 (interactive vs insight-batch)
- Status: Accepted
- Date: 2026-07-04
- Context: insight-worker 가 주말/야간 내내 로컬 gemma 로만 작동하고 정상 모델로 복귀하지
  않는 현상이 보고됨. 근본 원인은 `refresh-claude-oauth-token.sh` cron 이 **평일 10~19시만**
  실행되어, 주말/야간에는 bedrock-gateway 의 OAuth 토큰이 만료된 채 방치 → litellm 이 두 claude
  계정 모두 401 → edge-fallback(gemma) 로 강등, cron 이 다음 평일까지 안 돌아 계속 gemma.
  진단 중 (a) 대화(assistant 요청)는 원래 로컬 gemma(`auto`/`core`)로 작동 중이었고, (b) litellm
  fallback 체인에 `claude-haiku-4-root` 실패 시 edge 에 도달 못 하는 결함(`No fallback model group
  found for claude-haiku-4-root`)이 있었음.
- Decision (사용자 결정 2026-07-04):
  1. **사람 실시간 호출(assistant 대화 메인+보조 전 단계, AI 능동 분석 node_analysis)** 은 항상
     claude-haiku 로 작동한다 → 전용 litellm alias `claude-haiku-4-interactive`(+`-root`) 신설,
     fallback `interactive → interactive-root → edge`(두 계정 완전 장애 시에만 gemma). `.env` 의
     대화/분석 모델을 모두 이 alias 로 재배치. `AGENT_NODE_ANALYSIS_MODEL` 기본값도 interactive 로.
  2. **백그라운드 insight 배치(schema/table/account)** 는 평일 근무시간엔 claude-haiku-4, 야간·주말엔
     gemma(edge)로 강등해 비용을 절감한다 → 강등을 litellm(토큰 만료 의존)이 아니라 애플리케이션
     `llm._effective_insight_model()` 이 **시각 기반**으로 결정(토큰이 24/7 유효해도 insight 만 강등).
  3. litellm fallback 체인 결함 수정: `claude-haiku-4-root`·`claude-haiku-4-interactive-root` 도 명시
     fallback 키로 등록해 두 계정 장애 시 gemma 도달 보장.
  4. 사람 호출을 주말/야간에도 claude 로 유지하려면 토큰이 24/7 유효해야 하므로 `refresh-claude-oauth-token.sh`
     및 keepalive cron 을 평일한정 → 24/7 로 확장(운영: crontab). credentials 는 keepalive 가 CLI 실행으로
     refreshToken 자동 갱신 → 능동 갱신 스크립트 불필요.
- Consequences: 대화가 24/7 claude-haiku 로 작동(품질↑, claude 사용량·비용↑ — 사용자 수용). insight 는
  평일 주간만 claude 라 주말/야간 절감 유지. off-hours 경계는 `.env`(`AGENT_INSIGHT_BUSINESS_*`)로 조정 가능.
  단위 회귀: `tests/test_insight_offhours_routing.py`(시각 경계·주말) + `test_llm_env_naming.py`(interactive 기본값).
- Supersedes: feature-0016 node-analysis-haiku 의 `AGENT_NODE_ANALYSIS_MODEL=claude-haiku-4` 기본값을
  `claude-haiku-4-interactive` 로 갱신.
- Superseded By: **ADR-003 (2026-07-30)** — 결정 1의 `→ edge` 종단과 결정 2(야간·주말 gemma 강등),
  결정 3(gemma 도달 보장)이 폐지됐다. 결정 4(토큰 24/7 갱신)와 용도별 alias 분리 자체는 유효하다.

## ADR-003 — 자동 로컬 LLM(gemma/edge) 강등 경로 전면 폐지
- Status: Accepted
- Date: 2026-07-30
- Context: 2026-07-30 18:00:27 에 `bedrock-gateway` 컨테이너가 재생성된 직후, 컨테이너의 외부 DNS
  해석이 18:00:38~18:34:04(약 34분) 동안 실패했다(`api.anthropic.com`·`raw.githubusercontent.com`
  모두 `Temporary failure in name resolution`). 두 OAuth 계정은 **정상**(만료 미도래·429 0건)이었고
  문제는 도달성이었다. 그 34분간 `claude-haiku-4-interactive` 체인이 끝의 `edge-fallback` 으로 흘러
  대화 보조 단계 전체가 gemma 로 서빙됐고, 사용자에게는 "모든 LLM 요청이 edge 로 호출된다" 로 관측됐다.
  edge 를 이미 배제한 `*-chat`(2026-07-07)·`*-meta`(2026-07-30 오전)는 같은 장애에서 500 으로 실패했다 —
  두 규약의 거동 차이가 한 사건 안에서 대조군으로 드러났다.
  ADR-002(2026-07-04)는 "사람 호출은 항상 claude, 배경 배치는 야간·주말 gemma" 로 **부분적** 강등만
  남겼으나, (a) `-interactive` 체인의 `→ edge` 종단이 남아 있었고 (b) 사용자 인식("로컬 LLM 은 더 이상
  쓰지 않도록 구성했다")과 실제 구성 사이에 gap 이 있었다.
- Decision (사용자 결정 2026-07-30): **자동으로 로컬 LLM 이 서빙되는 경로를 전부 없앤다.**
  1. litellm `fallbacks` 에서 `edge-fallback` 참조를 **전량 제거** — `claude-haiku-4` 와
     `claude-haiku-4-interactive` 는 각각 `-root` 까지 2계정 체인이고 그 root 가 종단이다
     (`*-chat` 규약과 동일: 두 계정 실패 시 429/401 을 그대로 올려 정직하게 실패).
  2. 앱 층의 시각 기반 강등(`_effective_insight_model`)도 **기본 비활성** —
     `AGENT_INSIGHT_OFFHOURS_MODEL` 기본값을 `"edge"` 에서 빈 값으로 바꾼다. ADR-002 결정 2 폐지.
  3. **로직·정의는 보존한다** — `edge-fallback` deployment 정의와 강등 함수는 남기되 참조·기본값을
     끊는다. 되돌리려면 config 한 줄이면 되고, 그 행위가 사용자 결정 override 임을 주석으로 못박는다.
- Alternatives considered:
  - **(A) DNS 만 고치고 edge 는 유지**: 이번 촉발 조건은 사라지지만 "두 계정 장애 시 조용한 gemma 강등"
    이라는 구조는 남는다. 사용자 요청의 본질(로컬 LLM 미사용)을 충족하지 못해 불채택.
  - **(B) `-interactive` 만 edge-free, 배경 배치는 유지**: 오전의 `-meta` 결정과 같은 선(비용 절감 유지).
    사용자에게 명시 확인한 결과 **전면 제거**를 선택 → 불채택.
  - **(C) `edge-fallback` deployment 자체 삭제**: 참조가 0이면 라우팅되지 않으므로 삭제의 추가 이득이
    없고, 되돌리기만 어려워진다 → 불채택(정의 보존).
- Consequences:
  - 모든 LLM 경로가 claude 2계정 체인으로 통일된다. "조용히 품질이 무너진 산출물" 이 사라진다.
  - **안전망 부재의 비용**: 두 계정이 모두 실패·도달 불가한 창에서는 해당 기능이 **실패**한다. 이번
    사건 같은 게이트웨이 DNS 단절이 재발하면 그 창은 곧 전면 중단이다 → **DNS 안정화가 후속 필수 과제**
    (REPORT §8). 이 trade-off 는 사용자가 인지한 상태의 선택이다.
  - 배경 insight 배치가 야간·주말에도 claude 를 쓰므로 계정 사용량(5h rolling window) 소진이 빨라진다.
  - 회귀 잠금: `unit/feature-0002-agent-core/tests/test_llm_edge_free_routing.py`(5건). 신규 alias 추가
    시에도 "폴백 대상에 edge/local/gemma 토큰 없음" 이 전수 검사된다.
- Supersedes: ADR-002 결정 1의 `→ edge` 종단 · 결정 2(야간·주말 gemma 강등) · 결정 3(gemma 도달 보장).
  ADR-002 의 용도별 alias 분리와 결정 4(토큰 24/7 갱신)는 유효하다.
- Superseded By:
