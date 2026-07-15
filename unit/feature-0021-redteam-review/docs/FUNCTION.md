---
doc_type: FUNCTION
feature_id: feature-0021-redteam-review
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
서비스 내 assistant 가 답변을 사용자에게 전달하기 **전에**, Claude Code 의 모범적 추론
패턴 (fresh-context 적대 리뷰 · find→verify 2단계 · effort scaling · 결정론적
오케스트레이션 · auto-memory · progressive disclosure) 을 이식한 **자가 적대
red-team review** 를 내부 수행하는 기능. 보조 구조로 (a) [세션, 제품] 별 자가리뷰·메모리
임시 문서 (TTL 만료 정리), (b) 작동 지침/스킬 레지스트리의 관리 콘솔 조회, (c) 추론
강도 연동 오케스트레이션과 런타임 설정을 함께 구성한다. cross-cut — 코드 거주:
feature-0002 (코어·워커), feature-0003 (관리 콘솔), shared (설정 레지스트리).

## 2. Goal
- REQ-20260715T140000-redteam-selfreview: assistant 최종 답변 초안에 대해, 초안 생성
  컨텍스트와 분리된 fresh-context 리뷰어 LLM 이 5축 rubric (grounding / SQL 정확성 /
  권한·누출 / 완전성 / 정직성) 으로 적대적 리뷰를 수행하고, BLOCK 결함 발견 시 제한
  횟수 내 수정 후 전달한다. 리뷰 실패는 fail-open (답변 전달을 막지 않음).
- REQ-20260715T140001-orchestration: 리뷰 깊이는 대화별 추론 강도 (낮음/일반/높음/매우높음)
  와 런타임 설정으로 결정론적으로 게이팅된다 (낮음=skip, 일반=리뷰 1패스 + BLOCK 시
  1회 수정, 높음=리뷰→수정→재검증, 매우높음=심화 예산).
- REQ-20260715T140002-memory-notes: [세션(대화), 제품] 2계층 자가리뷰·메모리 문서를
  `/shared/agent-notes/` 임시 파일로 축적·프롬프트 참조하고, TTL 만료 시 주기적으로
  정리한다 (세션 기본 7일, 제품 기본 30일). 대화 격리를 보존한다.
- REQ-20260715T140003-console-visibility: 작동 지침 (시스템 프롬프트·가이던스 블록·
  red-team rubric) 과 스킬 (assistant 도구) 레지스트리, red-team 활동/판정, 메모리
  문서 현황을 관리 콘솔에서 read-only 조회할 수 있다 (신규 권한 `console.reasoning.read`).

## 3. In Scope
- `modules/redteam.py` — 리뷰어 프롬프트·오케스트레이션·판정 저장 (feature-0002).
- `modules/agent_notes.py` — 세션/제품 노트 기록·주입·TTL sweep (feature-0002).
- `modules/guidance_registry.py` — 지침/스킬 메타 레지스트리 (progressive disclosure).
- `agent_core.py` choke-point 훅 (답변 확정 직후, 저장 직전) + 노트 프롬프트 주입.
- `shared/runtime_settings.py` REDTEAM_* 설정 스펙 + 관리 콘솔 설정 패널.
- alembic 0042 `agent_runtime.redteam_reviews` (additive, 비파괴).
- `routers/admin_reasoning.py` + 관리 콘솔 "AI 추론" 탭 (feature-0003).

## 4. Out of Scope
- 사용자 대화 화면의 리뷰 결과 노출 (배지 등) — 후속 기능.
- 리뷰어의 SQL 재실행 (증거는 이미 실행된 도구 결과 digest 로 한정 — 비용/부작용 회피).
- 에러/취소/max-steps 종단 답변의 리뷰 (사실 주장 없는 안내문 — 리뷰 무의미).
- 제품 노트의 LLM 요약 승급 (v1 은 결정론적 distill 만).
- 지침의 콘솔 **편집** (조회만 — 편집은 WebSystemPrompts 기존 경로 유지).

## 5. Inputs
- 답변 초안 (`result["answer"]`), 사용자 질문, 도구 실행 digest (SQL·행수·도구 요약),
  modality (그룹 여부), reasoning_level, product_id.
- 런타임 설정: `REDTEAM_ENABLED`, `REDTEAM_MAX_REVISIONS`,
  `REDTEAM_NOTES_SESSION_TTL_DAYS`, `REDTEAM_NOTES_PRODUCT_TTL_DAYS`,
  `REDTEAM_NOTES_INJECT_MAX_CHARS`.
- 환경: `AGENT_REDTEAM_MODEL` (기본 haiku 급 저비용 모델, model_catalog 로 해석).

## 6. Outputs
- (수정되었을 수 있는) 최종 답변 + `agent_runtime.redteam_reviews` 판정 행.
- `/shared/agent-notes/session/<conversation_id>.md`,
  `/shared/agent-notes/product/<product_id>.md`.
- 관리 콘솔 조회 API: `GET /api/admin/reasoning/{guidance,redteam,notes}`.

## 7. Main Flow
1. `_run_agent_core` 가 최종 초안 확정 (`result["answer"]`).
2. 게이트: `REDTEAM_ENABLED=1` 이고 reasoning_level ≥ 일반 → 리뷰 수행. 아니면 원경로.
3. fresh-context 리뷰어 호출 (질문+초안+증거 digest 만 전달, 초안 생성 대화 비전달) →
   JSON findings (axis / severity BLOCK|WARN / claim / evidence / fix_hint, 상한 5건).
4. BLOCK 존재 → 초안 생성 컨텍스트에 findings 를 주입해 1회 수정 → (높음 이상) 재검증
   1회. 수정 상한 도달 시 마지막 수정본 채택.
5. 판정을 PG `agent_runtime.redteam_reviews` 에 저장 + 세션 노트에 distill 기록 →
   답변 저장/전달 (기존 `_save_message`/`_mirror_message` 경로 무변경).
6. ask-worker reaper 가 주기적으로 TTL 초과 노트 파일을 삭제.

## 8. Edge Cases
- 리뷰어가 findings 를 과잉 보고 → severity 게이트 (BLOCK 만 수정 유발) + 상한 5건 +
  over-engineering 경계 프롬프트.
- 수정본이 재검증에서 다시 BLOCK → 수정 상한(기본 1회)에서 중단, WARN 으로 강등 기록.
- 노트 파일 동시 접근 (드묾 — 대화당 답변 직렬) → 원자적 temp+rename 쓰기.
- 매우 긴 초안/증거 → digest 절단 캡 (리뷰어 입력 상한) 후 리뷰.
- PG 불가 → 판정 저장 skip (stderr 로그), 답변 경로 정상.

## 9. Error Handling
- 리뷰어 호출 실패/타임아웃/JSON 파싱 실패 → **fail-open**: 원 초안 그대로 전달,
  판정은 verdict=`error` 로 기록 시도. 답변 경로에 예외 전파 금지.
- 노트 파일 I/O 실패 → 조용히 skip (stderr 로그만).
- 콘솔 API 는 PG 불가 시 partial degrade (ai-ops 패턴, HTTP 200 + `pg_available:false`).

## 10. Dependencies
### 내부 기능 의존성
- feature-0002-agent-core (답변 파이프라인·ask-worker·alembic) — 코드 거주
- feature-0003-agent-web-ui (관리 콘솔·권한 카탈로그·감사) — 코드 거주
- feature-0018 런타임 설정 (shared/runtime_settings.py 레지스트리 재사용)
- feature-0007 bedrock-llm-provider (리뷰어 LLM 호출 경로)

### 외부 의존성
- AWS Bedrock (Claude) — 리뷰어 LLM 호출 (기존 gateway 경유)
- PostgreSQL `agent_runtime` — 판정 저장

### shared 모듈 의존성
- `shared/runtime_settings.py` (REDTEAM_* 스펙), `shared/model_catalog.py` (모델 해석)

## 11. Acceptance Criteria
- AC-20260715T140000-redteam-selfreview-1: 일반 강도 이상 답변에서 리뷰어가 호출되고
  판정이 `redteam_reviews` 에 기록된다.
- AC-20260715T140000-redteam-selfreview-2: BLOCK findings 발생 시 수정본이 전달되고
  applied_revision=true 로 기록된다.
- AC-20260715T140000-redteam-selfreview-3: 리뷰어 예외 시 원 답변이 그대로 전달된다
  (fail-open, 단위 테스트).
- AC-20260715T140001-orchestration-1: 낮음 강도 또는 REDTEAM_ENABLED=0 이면 리뷰 LLM
  호출이 발생하지 않는다 (기존 경로 회귀 0).
- AC-20260715T140002-memory-notes-1: 답변 후 세션 노트가 갱신되고, 다음 답변 프롬프트에
  캡 이내로 주입된다.
- AC-20260715T140002-memory-notes-2: TTL 초과 노트가 reaper sweep 에서 삭제된다.
- AC-20260715T140003-console-visibility-1: `console.reasoning.read` 보유 admin 이
  지침/스킬 목록·상세, red-team 활동, 노트 현황을 조회할 수 있고 무권한은 403.

## 12. Observability
- 리뷰 LLM 호출은 기존 `_record_llm_usage` 계측 (category=redteam) 으로 ai-ops 에 노출.
- `redteam_reviews` 행: verdict/축별 findings 수/latency_ms/모델/수정 적용 여부.
- 콘솔 "AI 추론" 탭: 최근 활동 + 판정 분포. reaper 삭제 건수는 stderr 로그.

## 13. Pre-approved Changes
- 없음 (전역 FIRST_REQUEST.md `deploy_scope: included` 적용 — cycle-final 후 배포 포함)
