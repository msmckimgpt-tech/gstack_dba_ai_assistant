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
- REQ-20260715T140003-console-visibility: 작동 지침 (가이던스 블록·red-team rubric) 과 스킬
  (assistant 도구) 레지스트리, red-team 활동/판정, 메모리 문서 현황을 관리 콘솔에서 read-only
  조회할 수 있다.
- REQ-20260716-console-ia: 위 조회 화면을 성격별로 분리 배치한다 (사용자 요청) — **감사 >
  AI 추론** = red-team 리뷰 활동·판정 + 메모리 노트 현황 (권한 `console.reasoning.read`, 감사
  카테고리); **설정 > 프롬프트 그룹** = 전역 시스템 프롬프트(편집) + 작동 지침(조회) + 스킬(조회)
  (지침/스킬 조회 = `system_prompt.global.read` 재사용). 기본 시스템 프롬프트 fallback 은 전역
  시스템 프롬프트와 중복이라 작동 지침 목록에서 제외 (편집 정본 단일화).

- REQ-20260727-converge-until-resolved: **결함이 해소될 때까지 반복 검증한다** (사용자 결정,
  신뢰성 최우선 DB 작업). ① 수정본 재검증을 추론 강도로 게이팅하지 않는다 (기본 모든 강도).
  ② 재검증이 다시 BLOCK 을 내면 상한 없이 수정→재검증을 반복한다. ③ 그럼에도 결함이 남은 채
  전달되는 경우(사용자 '즉시 답변'·취소·수정 무산출·무진전)는 판정 저장·관리 콘솔·답변 고지의
  3곳에서 **명시적으로 표면화**한다 (결함 잔존의 은폐 금지). 응답 시간 상한은 두지 않으며,
  사용자는 작업 화면의 '즉시 답변'으로 언제든 그 시점 답변을 수령한다.
- REQ-20260728T093528-answer-origin-realign: 자가 검증을 거쳐 전달되는 최종 답변이 **직전 맥락
  (내부 리뷰 결함 목록)이 아니라 사용자의 원 요청에 응답**하도록 한다 (사용자 관측: "처음 요청
  사항의 문맥보다 직전 문맥에 답변하는 듯한 뉘앙스"). 근본 원인은 수정 지시가 초안 생성
  컨텍스트의 **trailing user turn** 이라, 모델의 생성 지점 최근접 맥락이 리뷰 결함 목록이라는
  구조에 있다. ① 수정·재추론 지시의 **맨 끝**에 원 요청 재앵커 블록을 두어 recency 를 반대로
  쓰고, 출력이 "리뷰에 대한 회신"이 아니라 "원 요청에 대한 최종 답변"임을 계약으로 명시한다.
  ② 그래도 남는 메타 프레이밍은 결정론 탐지기가 잡아 **내용 보존 재서술 1회**로 교정한다.
  전 경로 fail-open 이며, 다듬기가 답변을 악화시키면(내용 손실·메타 잔존) 원문을 유지한다.
- REQ-20260729T110000-review-request-context: 리뷰어와 수정 지시가 **현재 턴 발화가 아니라 이
  대화의 실질 요청**을 기준으로 판단하게 한다. ① 리뷰어에 `CONVERSATION REQUEST` 와 **사용자
  첨부 파일 근거**를 제공하고 "짧은 후속 발화 대비 과답변" 을 결함으로 보고하지 못하게 한다.
  ② 재앵커를 [대화 요청 / 직전 발화] 2층으로 나누고, 계약을 **addressing 전용**(다룰 내용을
  좁히지 않음)으로 한정한다. ③ 수정본이 초안 대비 붕괴하면 채택하지 않는다
  (`stop_reason=revise_collapsed`). 근거: 라이브 회귀(§7.4).
- REQ-20260727-reviewer-memory: 리뷰어가 **대화 내부 격리 환경에서 자기 리뷰 이력을 기억**한다 —
  자기가 직전에 지적한 항목과 그에 대해 assistant 가 내놓은 수정본을 이어받아, 해소 여부를
  먼저 판정하고 이미 고쳐진 항목을 다시 보고하지 않는다. 기억 범위는 (a) 현재 답변의 라운드
  이력, (b) 같은 `conversation_id` 의 직전 판정으로 한정한다 — 다른 대화의 내용은 포함하지
  않으며, 초안을 만든 대화 컨텍스트도 여전히 보지 않는다 (fresh-context 불변식 유지).

- REQ-20260716-console-subtabs: 유사 성격 항목을 서브탭으로 묶는다 (사용자 요청) — **감사 그룹**의
  LLM 사용량·AI 운영 현황·AI 추론 3개 탭을 'AI 운영 현황' 단일 탭 + 서브탭 [LLM 사용량 / 운영 현황 /
  추론]으로, **설정 > 프롬프트**의 3항목을 단일 '프롬프트' 항목 + 서브탭 [전역 시스템 프롬프트 /
  작동 지침 / 스킬]으로 통합. 통합 탭은 하위 조회 권한 OR 로 노출하고 서브탭은 각자 권한으로 게이팅.

## 3. In Scope
- `modules/redteam.py` — 리뷰어 프롬프트·오케스트레이션·판정 저장 + **원 요청 재앵커·메타
  프레이밍 탐지·내용 보존 재서술**(`build_request_anchor` / `detect_meta_framing` /
  `build_reanchor_instruction` / `realign_answer`) (feature-0002).
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
- **요청 재앵커 입력**: 대화 실질 요청(`origin_request`→`thread_goal` 폴백) + 이 답변을 촉발한
  사용자 발화(`user_message`) + 대화 목표. 대화 레벨 값은 bounded 발신자에겐 억제 (§7.3·§7.4).
- **리뷰어 근거 입력**: 도구 실행 digest + **사용자 첨부 파일**(매니페스트+발췌, bounded 발신자
  에겐 억제 — §7.4).
- 런타임 설정: `REDTEAM_ENABLED`, `REDTEAM_MAX_REVISIONS`,
  `REDTEAM_REVISE_UNTIL_RESOLVED`, `REDTEAM_VERIFY_MIN_LEVEL`, `REDTEAM_UNRESOLVED_NOTICE`,
  `REDTEAM_HISTORY_CONV_LIMIT`, `REDTEAM_ANSWER_REALIGN`,
  `REDTEAM_NOTES_SESSION_TTL_DAYS`, `REDTEAM_NOTES_PRODUCT_TTL_DAYS`,
  `REDTEAM_NOTES_INJECT_MAX_CHARS`.
- 중단 신호: 사용자 '즉시 답변'(`conversation.finalize.*`) / 요청 취소 — 반복 수정 루프의
  매 라운드에서 확인 (`abort_fn`).
- 환경: `AGENT_REDTEAM_MODEL` (기본 haiku 급 저비용 모델, model_catalog 로 해석).

## 6. Outputs
- (수정되었을 수 있는) 최종 답변 + `agent_runtime.redteam_reviews` 판정 행.
- `/shared/agent-notes/session/<conversation_id>.md`,
  `/shared/agent-notes/product/<product_id>.md`.
- 관리 콘솔 조회 API: `GET /api/admin/reasoning/{guidance,redteam,notes}`.

## 7. Main Flow
1. `_run_agent_core` 가 최종 초안 확정 (`result["answer"]`).
2. 게이트: `REDTEAM_ENABLED=1` 이고 reasoning_level ≥ 일반 → 리뷰 수행. 아니면 원경로.
3. fresh-context 리뷰어 호출 (질문+초안+증거 digest+**자기 리뷰 기억** 전달, 초안 생성 대화
   비전달) → JSON findings (axis / severity BLOCK|WARN / claim / evidence / fix_hint, 상한 5건).
4. BLOCK 존재 → 초안 생성 컨텍스트에 findings 를 주입해 수정 → 재검증. **재검증이 다시 BLOCK 을
   내면 4를 반복한다** (`REDTEAM_REVISE_UNTIL_RESOLVED=1` 기본, 상한 없음). 매 라운드 시작 시
   사용자 '즉시 답변'/취소를 확인하고, 라운드 진행을 activity 로 노출한다.
5. 루프 종료 사유(`stop_reason`)와 미해소 BLOCK 수, 마지막 재검증 findings 를 PG
   `agent_runtime.redteam_reviews` 에 저장 + 세션 노트에 distill 기록. 결함이 남았으면 답변
   말미에 고지를 덧붙인 뒤 저장/전달 (기존 `_save_message`/`_mirror_message` 경로 무변경).
6. ask-worker reaper 가 주기적으로 TTL 초과 노트 파일을 삭제.

### 7.1 루프 종료 사유 (`stop_reason`)
| 값 | 의미 | 결함 잔존 |
|---|---|---|
| `resolved` | 재검증 통과 — 지적 해소 | 아니오 |
| `aborted` | 사용자 '즉시 답변'/취소 | 가능 |
| `no_progress` | 수정본이 직전과 실질 동일 (반복 무의미) | 가능 |
| `revise_collapsed` | 수정본이 최초 초안의 30% 미만으로 축소 — 붕괴 방지로 미채택 (§7.4) | 가능 |
| `revise_failed` | 수정 산출 실패 (fail-open) | 가능 |
| `verify_error` | 재검증 호출 실패 (fail-open) | 미상 |
| `unverified` | `REDTEAM_VERIFY_MIN_LEVEL` 로 재검증을 끈 강도 | 미상 |
| `budget` | `REDTEAM_REVISE_UNTIL_RESOLVED=0` + 수정 상한 도달 | 가능 |
| `backstop` | 하드 안전 상한(기본 50 라운드) 도달 | 가능 |
| `deadline` | `REDTEAM_WALL_BUDGET_SEC` 시간 예산 도달 (기본 0=무제한) | 가능 |
| `abort_check_failed` | 중단 신호를 연속 3회 읽지 못함 (탈출구 불능 → 보수적 종료) | 가능 |
| `downgraded` | BLOCK 이던 축이 최종 판정에서 WARN 으로 남아 pass 처리 | 강등 |
| `review_error` | 최초 리뷰 호출 실패 (리뷰 자체 미수행) | 미상 |

`unverified` / `review_error` / `verify_error` 는 **검증하지 않았음**을 뜻하므로 미해소로 단정하지
않는다 (`unresolved_block_count=0`, 고지 미부착). `REDTEAM_MAX_REVISIONS=0`(수정 차단 스위치)도
고지를 붙이지 않는다 — 운영자가 스위치를 내린 것이 사용자 답변 변조로 이어지면 안 된다.

### 7.2 리뷰어 맥락 기억의 경계 (SECURITY §21 정합)
- 기억 대상은 **자기 리뷰 판정**뿐이다. 초안을 만든 대화 컨텍스트는 여전히 리뷰어에게 가지 않는다
  (fresh-context 불변식).
- 대화 이력은 `conversation_id` 스코프. **`has_restricted_members=true`(공유창 window 격리) 대화는
  조회 자체를 하지 않는다** — `redteam_reviews` 행에 발신자·가시성 정보가 없어 window clip 이
  불가하므로 fail-closed 한다. 조회 실패·대화 메타 부재도 동일하게 차단.
- 기억 블록은 `<<REVIEW_MEMORY>>` sentinel 로 구획되고 내부 자유텍스트는 sentinel 제거 + 개행
  접기를 거친다 (구획 breakout·줄 위조 차단).
- 라운드 이력이 예산을 선점한다 (최근 3라운드). 대화 이력은 남는 예산만 쓴다 — 수렴에 직결하는
  최신 라운드가 cap 에 밀려 잘리면 안 되기 때문이다.

### 7.3 원 요청 재앵커 (answer-origin-realign)

수정(revise)·재추론(rederive) 지시는 초안 생성 컨텍스트의 **trailing user turn** 이다
(`_build_self_review_messages` — 이 위치는 prefill 회귀 방지를 위한 기존 불변식이라 바꾸지
않는다). 따라서 모델의 생성 지점 최근접 맥락이 "내부 리뷰 결함 목록"이고, 산출물이 원 요청이
아니라 **직전 맥락에 응답하는 레지스터**로 기운다. 같은 recency 지렛대를 반대로 쓴다:

| 층 | 수단 | 추가 LLM 호출 |
|---|---|---|
| 1차 (기본) | 지시 **맨 끝**에 원 요청 재앵커 블록 + 출력 계약(메타 표현·직전 맥락 지시어 금지, 구성은 원 요청이 결정) | 0 |
| 2차 (조건부) | 도입부 메타 프레이밍 결정론 탐지 → **내용 보존 재서술 1회** | 탐지 시에만 1 |

- **전달 후 별도 다듬기 패스를 두지 않는다**: 근거 없이 문장만 다듬는 리라이터는 red-team 이
  방금 강제한 grounding·불확실성 고지를 매끄럽게 지워내 정직성을 되돌린다(§16.3). 대신 교정을
  **생성 시점**과 **revise 콜백 내부**에 둔다 — 재서술본도 기존 verify 패스를 그대로 통과하므로
  수렴 불변식이 깨지지 않는다.
- **재서술 폐기 조건 (fail-open)**: 무산출 / 호출 실패 / 원문 대비 60% 미만 길이(내용 손실 의심)
  / 재서술본에도 메타 프레이밍 잔존 → **원문 유지**. 다듬기가 답변을 악화시키는 경로를 결정론적
  으로 닫는다.
- **비용 가드**: 탐지가 없으면 호출 0. 반복 수정 루프에서 **연속 거절 2회**면 그 run 의 잔여
  라운드는 재서술을 시도하지 않는다(성공하면 카운터 리셋).
- **재추론 경로의 base**: 재서술 프롬프트는 그 라운드의 메시지(`_rd_messages`)를 기반으로 한다 —
  재도출이 새로 돌린 도구 결과가 outer 컨텍스트에 없어서, 기본 base 로 재서술하면 모델이
  **낡은 근거** 쪽으로 수치를 되돌릴 수 있다.
- **누출 경계**: 주 앵커인 `user_message` 는 그 발신자 본인의 입력이라 항상 안전하다. 보조 앵커
  `thread_goal` 은 대화의 (가려졌을 수 있는) 첫 요청에서 파생된 자유 텍스트라 window 로 자를 수
  없으므로, bounded 발신자(`_suppress_conversation_context`)에게는 system 프롬프트의
  CONVERSATION CONTEXT 와 **동일하게 억제**한다(`_realign_thread_goal` 정본). 재앵커 블록은
  `<<USER_REQUEST>>` sentinel 로 구획되고 내부 sentinel 이 제거되어 구획 breakout 이 차단된다.

### 7.4 다중 턴 요청 맥락 · 첨부 근거 · 붕괴 가드 (2026-07-29 회귀 교정)

§7.3 초판은 **단일 턴**을 암묵 가정했다 — 재앵커의 "원 요청" 자리에 *현재 턴 발화*를 싣고,
계약이 "답변의 구성·범위·상세도는 원 요청이 결정한다" 고 선언했다. 다중 턴에서 이 가정이
깨지면서 답변이 붕괴했다.

**라이브 근거** (대화 `20260729013313-2211841a`, run #132 — 실측):

| 턴 | 사용자 | 답변 |
|---|---|---|
| 1 | "쿼리 리뷰를 진행해주세요" + 첨부 `*.sql` | 488자 |
| 2 | **"네 맞습니다."** | **152자** ("상세 분석이 필요하시면 말씀해주세요") — 14 라운드 수정 후 `stop=resolved` |
| 3 | "리뷰 진행 및 답변해주세요." | 3,170자 (정상 리뷰) |

리뷰어가 낸 BLOCK 2건이 원인이었다 — 둘 다 **구조적 false positive**:
- `completeness`: "USER QUESTION 에 '네 맞습니다'만 있고 코드 제공 없음. DRAFT 는 긴 리뷰 제공."
  → 리뷰어는 fresh-context 라 대화를 못 보고 **현재 턴 발화만** 받는다.
- `honesty`: "사용자 제출 증거가 없는 SQL 을 검증된 분석인 것처럼 제시."
  → 첨부 본문은 **시스템 프롬프트**로 주입되고 evidence digest 는 **도구 결과만** 담는다.

그리고 이 오판이 **자기 강화**됐다: 모델이 내용을 지울수록 반박할 claim 이 사라져 리뷰어가
통과시킨다 — **축소가 곧 수렴이 되는 퇴행 경로**(14 라운드가 그 gradient descent 의 흔적).

**교정 4축**:

| 축 | 내용 |
|---|---|
| **요청 맥락 (D1)** | `run_review` 가 `CONVERSATION REQUEST`(origin_request→thread_goal→현재 발화 폴백)를 받고, 발화는 `LATEST USER UTTERANCE` 로 라벨된다. 프롬프트가 "짧은 후속 발화 대비 과답변" 보고를 **금지**하고, "삭제로 결함을 해소한 수정본은 REGRESSION 이므로 BLOCK" 을 명시한다. |
| **첨부 근거 (D3)** | evidence digest 에 `USER-ATTACHED FILES` 매니페스트 + 파일당 발췌(1,200자 캡, 절단 표기). 첨부 섹션이 **자기 예산을 선점**해 도구 digest 가 길어도 잘리지 않는다 — 잘리면 그 첨부를 리뷰하는 답변이 다시 '창작'으로 오판된다. |
| **앵커 2층 (D2)** | `[이 대화의 요청 — 답변이 수행해야 할 일]` + `[직전 사용자 발화 — 방금 한 말일 뿐, 답변 범위가 아니다]`. 둘이 실질 동일하면 1층으로 렌더(단일 턴). 계약은 **addressing 전용** — "다룰 내용을 좁히지 않는다 / 초안이 다루던 분석·표·근거를 삭제하지 말 것 / 짧은 확인·동의에 길이를 맞추지 말 것". |
| **붕괴 가드 (D4)** | 수정본이 **최초 초안의 30% 미만**이면 채택하지 않고 `stop_reason=revise_collapsed` 로 종료(직전 답변 유지). 프롬프트 교정이 1차 방어이고 이 가드는 퇴행 경로를 구조적으로 닫는 backstop 이다. |

**붕괴 가드의 의도적 트레이드오프**: 긴 초안이 통째로 근거 없어 "짧고 정직한 답"으로 줄어드는
것이 정당한 경우에도 채택을 막는다. 그 경우 직전 답변이 **미해소 고지와 함께** 전달되므로 결함이
은폐되지는 않는다(§16.3 정직성). 붕괴한 비-답변보다 낫다고 판단했다. 임계 0.30 은 realign 가드
(0.6)보다 훨씬 관대하다 — 막으려는 것은 '축소' 가 아니라 **답변이 답변이기를 그만두는 붕괴**다.

**과교정 가드 (2026-07-29 라이브 A/B 후속)**: 대화 요청을 주면 리뷰어가 **반대 방향**으로
기울 수 있다 — "이전 턴에서 이미 전달한 리뷰를 이 답변이 다시 주지 않았다"(`completeness`
BLOCK). 리뷰어는 이전 턴을 보지 못하므로 구조적으로 알 수 없는 사실이다. 프롬프트에
"CONVERSATION REQUEST 는 이전 턴에서 이미(부분) 답변됐을 수 있고, 짧은 후속 발화에 대한
**타당한 continuation**(다음 단계·실행 가이드·좁힌 조각)은 정상이며, `completeness` 는 답변이
**아무 actionable 도 남기지 않을 때만** 보고" 규칙을 추가했다. 실측: 과교정 **2/3 → 1/4**
(잔여 있음 — §7.4 측정 표 참조). 이 방향의 오판은 답변을 **늘리는** 쪽이라 붕괴 가드와 충돌하지
않으며, 최악이라도 리뷰 내용이 재수록될 뿐 파괴되지 않는다.

**누출 경계**: `conversation_request`·첨부 목록 모두 bounded 발신자(공유창 window 격리)에게는
빈 값이다(`_review_conversation_request` / `_review_attachments` 정본). 그 경우 리뷰어는 종전대로
현재 발화만 보지만 그것은 **기존 동작**이라 회귀가 아니다. fresh-context 불변식과도 충돌하지
않는다 — 전달되는 것은 assistant 의 추론 과정이 아니라 **사용자 자신의 요청문과 첨부**다.

### 7.5 회차 단계 원장 (`redteam_review_rounds`, 2026-07-29)

요약 행(`redteam_reviews`)은 한 답변(run)당 1행이라 **최초 리뷰**(`findings`)와 **마지막
재검증**(`verify_findings`)만 담는다. 그 사이 회차 — 2회차 재검증이 무엇을 지적했고 3회차
수정이 어떤 방식이었는지 — 는 어디에도 남지 않아, 관리 콘솔은 대화의 마지막 리뷰 사항만
보여줄 수밖에 없었다. 신규 원장 테이블이 그 회차 전부를 보존한다.

| `round_index` | `phase` | 내용 |
|---|---|---|
| 0 | `review` | 최초 자가 적대 리뷰 — verdict + findings |
| N | `revise` | N회차 수정 — `revise_method`(rederive/rewrite) · `revise_axis` · `tool_rounds` · `answer_chars` |
| N | `verify` | N회차 재검증 — verdict + findings |

- **폐기 라운드도 남는다**: 채택되지 못한 수정(`revise_failed` / `no_progress` /
  `revise_collapsed`)과 재검증 미수행(`unverified`) · 재검증 실패(`verify_error`)는 `note` 로
  기록된다 — "왜 이 회차가 마지막인가" 가 요약의 `stop_reason`(§7.1)과 원장 양쪽에서 읽힌다.
- **답변 본문 비저장**: 회차별로 길이(`answer_chars`)만 남긴다. `/api/admin/reasoning/notes`
  의 "내용 비반환 · 목록 메타만" 최소 노출 규약과 같은 판단이며, findings 의 claim/evidence
  는 리뷰어가 생성한 지적문이라 기존 노출 범위와 동일하다.
- **쓰기 경로**: 라운드마다 PG 왕복을 만들지 않고 메모리에 누적했다가 종료 시 1회 배치
  INSERT 한다. 요약 행을 **먼저 커밋**한 뒤 그 id 로 append 하므로, 원장 INSERT 가 실패해도
  (0048 미적용 stale agent 이미지) 요약 기록은 회귀 없이 유지된다.
- **읽기 경로 (콘솔)**: `/api/admin/reasoning/redteam` 이 페이징 단위를 **대화**로 바꿨다 —
  대화 keyset = `MAX(id)` DESC(최근 대화 순), 대화 내부는 `id` ASC(진행 순), 대화당 상한
  20건이며 초과분은 `capped` 로 표시한다. 각 리뷰에 회차 원장이 `rounds`(회차 asc)로 동봉되고,
  원장이 없는 이전 기록은 `rounds_available:false` 로 기존 요약 타임라인에 폴백한다.

## 8. Edge Cases
- 리뷰어가 findings 를 과잉 보고 → severity 게이트 (BLOCK 만 수정 유발) + 상한 5건 +
  over-engineering 경계 프롬프트.
- 수정본이 재검증에서 다시 BLOCK → **결함이 해소될 때까지 반복** (기본). 리뷰어는 자기 이전
  지적과 수정본을 기억하므로 해소된 항목을 재보고하지 않고, 여러 라운드를 버틴 결함은
  WARN 으로 강등하도록 프롬프트가 유도한다 (수렴 압력).
- 리뷰어가 매 라운드 새 BLOCK 을 생성하는 병리적 케이스 → 무진전 가드(수정본 동일성) + 하드
  백스톱(기본 50 라운드)에서 결정론적으로 중단하고 `stop_reason` 으로 기록.
- 반복이 길어져 사용자가 기다리기 어려움 → 작업 화면 '즉시 답변' 이 매 라운드 확인되어 그 시점
  최선 답변으로 즉시 종료 (`stop_reason=aborted`).
- 결함이 남은 채 전달 → `unresolved_block_count`/`verify_findings` 기록 + 콘솔 타임라인 ⑤가
  "결함 잔존 상태로 전달"로 표시 + 답변 말미 고지(`REDTEAM_UNRESOLVED_NOTICE`).
- 노트 파일 동시 접근 (드묾 — 대화당 답변 직렬) → 원자적 temp+rename 쓰기.
- 매우 긴 초안/증거 → digest 절단 캡 (리뷰어 입력 상한) 후 리뷰. 리뷰 기억 블록도 별도 캡.
- PG 불가 → 판정 저장 skip (stderr 로그), 대화 기억 조회도 빈 목록, 답변 경로 정상.

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
- AC-20260727T160000-converge-until-resolved-1: 재검증이 BLOCK 을 낸 상태에서 수정 상한(1)을
  넘겨 반복하고, 결함이 해소되면 종료한다 (`stop_reason=resolved`).
- AC-20260727T160000-converge-until-resolved-2: 일반 강도에서도 수정본이 재검증된다
  (`verify_pass=True` 기본).
- AC-20260727T160000-converge-until-resolved-3: `abort_fn`(즉시 답변/취소)이 True 를 내면
  그 시점 최선 답변으로 즉시 종료하고 `stop_reason=aborted` 로 기록한다.
- AC-20260727T160000-converge-until-resolved-4: 수정본이 직전과 실질 동일하면 무진전으로
  중단하고, 하드 백스톱 도달 시 `stop_reason=backstop` 으로 기록한다 (런어웨이 차단).
- AC-20260727T160000-converge-until-resolved-5: 결함이 남은 채 전달되면 답변 말미 고지 +
  `unresolved_block_count`/`verify_findings`/`stop_reason` 기록 + 콘솔 ⑤단계가 "결함 잔존
  상태로 전달"로 표시한다.
- AC-20260727T160100-reviewer-memory-1: 2라운드째 리뷰어 호출에 자기 1라운드 findings 와
  assistant 수정본 발췌가 함께 전달된다.
- AC-20260727T160100-reviewer-memory-2: 대화 기억은 `conversation_id` 스코프로만 조회되며,
  `conversation_id` 부재 또는 `REDTEAM_HISTORY_CONV_LIMIT=0` 이면 조회하지 않는다.
- AC-20260727T160100-reviewer-memory-3: 기억 블록이 `<<REVIEW_MEMORY>>` sentinel 로 구획되고,
  자유텍스트의 sentinel·개행이 제거되어 구획 breakout 과 줄 위조가 차단된다.
- AC-20260727T160100-reviewer-memory-4: `has_restricted_members=true`(공유창 window 격리) 대화
  에서는 대화 기억을 조회하지 않는다 (fail-closed — SECURITY §21).
- AC-20260727T160100-reviewer-memory-5: cap 포화 시에도 최신 라운드 이력이 보존된다.
- AC-20260727T174500-panel-1: `REDTEAM_MAX_REVISIONS=0` 또는 `unverified` 종료에서는 미해소 고지가
  붙지 않고 `unresolved_block_count=0` 이다.
- AC-20260727T174500-panel-2: 사용자가 메인 도구 루프 단계에서 '즉시 답변'을 눌렀으면 red-team
  반복 수정이 즉시 종료된다 (`stop_reason=aborted`).
- AC-20260727T174500-panel-3: 무진전으로 폐기된 라운드의 재도출 도구는 `meta["rederive_steps"]`
  에 포함되지 않으며 `rederive_applied=False` 다.
- AC-20260727T174500-panel-4: rederive 근거가 라운드 간 누적되어 마지막 재검증이 이전 라운드
  근거까지 함께 본다.

## 12. Observability
- 리뷰 LLM 호출은 기존 `_record_llm_usage` 계측 (category=redteam) 으로 ai-ops 에 노출.
- `redteam_reviews` 행: verdict/축별 findings 수/latency_ms/모델/수정 적용 여부 +
  `revision_rounds`(반복 라운드 수) · `stop_reason`(§7.1) · `unresolved_block_count`(전달 시점
  미해소 BLOCK) · `verify_findings`(마지막 재검증이 여전히 문제 삼은 항목).
- `redteam_review_rounds` 행: 회차별 `(round_index, phase)` 판정·수정 방식·도구 라운드·
  답변 길이·폐기 사유(§7.5). 회차 asc 정렬이 콘솔 표시 계약이다.
- 콘솔 "AI 추론" 탭: 최근 활동 + 판정 분포 + **'결함 잔존 전달 (7d)'** 통계 타일. 활동 목록은
  **대화 단위 컨테이너**(최근 대화 순)로 격리되고, 대화 → 리뷰(run) → 회차 단계의 3계층이
  각각 접기/펼치기 된다(기본 접힘 — 스크롤 격리). 리뷰 카드의 요약 타임라인이 ③에 반복 라운드
  수, ④에 미해소 BLOCK 수, ⑤에 "결함 잔존 상태로 전달 (사유)"를 표시하고, 그 아래 회차 목록이
  자가검증·재검증 각 단계의 지적 원문을 진행 순서대로 노출한다. reaper 삭제 건수는 stderr 로그.
- 사용자 화면: 반복 라운드가 activity("결함을 수정하는 중 N회차" / "수정본을 재검증하는 중
  N회차")로 실시간 노출되며, 결함이 남은 채 전달되면 답변 말미에 고지가 붙는다.

## 13. Pre-approved Changes
- 없음 (전역 FIRST_REQUEST.md `deploy_scope: included` 적용 — cycle-final 후 배포 포함)
