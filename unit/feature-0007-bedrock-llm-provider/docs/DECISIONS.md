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
- Superseded By:
