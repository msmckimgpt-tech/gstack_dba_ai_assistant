---
doc_type: FEATURE_DECISIONS
feature_id: feature-0021-redteam-review
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-20260715T140000-claude-code-pattern-mapping
- Status: accepted
- Date: 2026-07-15
- Context: 사용자 요청 — "claude-code 에서 모범적인 추론 과정을 통해 작동하는 것과 유사한
  형태" 로 서비스 assistant 의 자가 적대 리뷰를 구성. 실동작·웹 리서치로 Claude Code 메커니즘
  을 파악한 결과 (code.claude.com/docs how-claude-code-works·best-practices, anthropic.com/
  engineering multi-agent-research-system, 하네스 실동작 introspection):
  ① agentic loop = gather context → take action → **verify results** (verify-before-done),
  ② 적대 리뷰 = fresh-context 리뷰어(작업을 만든 에이전트가 채점하지 않음) + find→verify
  2단계 + "정확성 영향 결함만, 불확실하면 미보고" over-engineering 경계,
  ③ effort scaling (단순 작업 저비용·복잡 작업 심화 — 명시 가이드라인),
  ④ 오케스트레이션 제어 흐름은 모델 기억이 아닌 결정론 코드/스크립트에,
  ⑤ 토큰 결핍 대응 = auto-memory (인덱스+사실 파일·캡·TTL)·progressive disclosure (스킬은
  이름+설명만 상시 로드)·서브에이전트 컨텍스트 격리,
  ⑥ 결정론 가드레일(hook)과 모델 판단의 분리.
- Decision: 제품 이식 매핑 —
  ①→ 답변 choke-point (`agent_core.py` `result["answer"]` 확정 직후) 리뷰 패스,
  ②→ `modules/redteam.py` 리뷰어는 질문+초안+증거 digest 만 수신(초안 생성 대화 비전달),
  5축 rubric (grounding/sql/permission/completeness/honesty), BLOCK 만 수정 유발, findings ≤5,
  ③→ 추론 강도 게이팅 (낮음=skip / 일반=find 1패스 / 높음·매우높음=find→revise→verify),
  ④→ `orchestrate_review` 결정론 파이프라인 + REDTEAM_* 런타임 설정 (수정 상한 구조적 차단),
  ⑤→ `/shared/agent-notes/{session,product}` 캡·TTL 노트 + `guidance_registry` 목록=메타만,
  ⑥→ sql_guard 등 기존 결정론 게이트 무변경 — red-team 은 그 위의 의미 계층만 담당.
- Consequences: 답변당 리뷰 비용 추가 (haiku 급, 게이팅으로 제한). 리뷰는 fail-open —
  가용성 손실 없음. 판정이 `agent_runtime.redteam_reviews` 에 축적되어 콘솔 관측 가능.
- Supersedes: 없음
- Superseded By: 없음

## ADR-20260715T140001-reviewer-model-and-failopen
- Status: accepted
- Date: 2026-07-15
- Context: 리뷰어 모델·실패 정책. 대안 — (a) 본 답변과 동일 모델 (품질↑ 비용↑),
  (b) 저비용 haiku 급 (관계 분석 전용 haiku 분리 선례), (c) 리뷰 실패 시 답변 보류(fail-closed).
- Decision: 기본 `AGENT_REDTEAM_MODEL=claude-haiku-4-chat` (edge-free 대화 alias — gemma 강등
  차단 FR-edge-fallback 선례 정합, env 로 교체 가능). 실패는 **전 경로 fail-open** — 리뷰/저장/
  노트의 어떤 예외도 답변 전달을 막지 않는다 (리뷰는 품질 향상 계층이지 가용성 게이트가 아님).
  usage 는 task="redteam" 으로 계측해 ai-ops 에서 비용 분리 관측.
- Consequences: 저비용 리뷰어의 검출력 한계는 높음/매우높음 강도의 verify 재검증으로 보완.
  fail-closed 미채택으로 리뷰 인프라 장애가 서비스 장애로 전파되지 않음.
- Supersedes: 없음
- Superseded By: 없음

## ADR-20260715T140002-notes-file-based-isolation
- Status: accepted
- Date: 2026-07-15
- Context: [세션, 제품] 메모리 문서 저장소 — 사용자가 "임시 파일 + 만료 정리" 를 명시 요청.
  대안: DB 테이블(스케일아웃 유리) vs /shared 파일(요청 부합·reaper 선례). 공유 대화
  visibility window (SECURITY §21) 와의 상호작용, 교차 대화 누출이 위험 축.
- Decision: `/shared/agent-notes/{session,product}/` 파일 (원자적 temp+rename, 파일 캡 8KB
  최신 우선 trim, ask-worker reaper mtime TTL). 격리 3중 장치 — ① 세션 노트는 해당
  conversation_id 프롬프트에만 주입, ② 제품 노트에는 리뷰 claim(대화 파생 텍스트) 저장 금지
  (테이블 참조·axis 수준 사실만 — 결정론 distill, LLM 요약 없음), ③ 공유 대화 bounded 발신자
  요청에는 origin/thread_goal 과 동일 사유로 노트 주입 자체를 억제
  (`_suppress_conversation_context` 재사용 — window 로 자를 수 없는 자유 텍스트).
- Consequences: 다중 호스트 스케일아웃 시 DB 승급 필요 (후속 분기 — ANCHOR §2 Alt-C 명시).
  노트는 힌트 계층 — NOTES_CONTEXT_HEADER 가 "증거로 인용 금지" 를 강제해 노트 오염이
  사실 주장으로 승격되는 것을 차단 (redteam grounding 축이 2차 방어).
- Supersedes: 없음
- Superseded By: 없음
