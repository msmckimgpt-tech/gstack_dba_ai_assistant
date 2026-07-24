---
doc_type: REVIEW
feature_id: feature-0021-redteam-review
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260715-0001
- Related Change: CHG-20260715-0001 (자가 적대 red-team 리뷰 + 메모리 노트 + 콘솔 조회 최초 구현)
- Reason: 사용자 요청 (entry arg-given dispatch) — Claude Code 의 모범 추론 패턴을 실동작·웹
  리서치로 파악해 제품 assistant 에 이식. 리서치 근거·매핑은 DECISIONS ADR-20260715T140000.
  위험도 Major (답변당 리뷰 LLM 호출 = 외부 비용) — plan 표면화 후 진행 (§7.1),
  완화: haiku 급 리뷰어 + 추론 강도 게이팅 + 런타임 on/off + fail-open.
- Alternatives Considered: self-critique 프롬프트 내장(자기 편향 오염 — 기각), 사후 배치
  감사(오답 도달 후 — 기각), DB 기반 메모리(사용자가 임시 파일 명시 요청 — 기각, ANCHOR §2).
- Risks: ① 리뷰어 과잉 지적 → BLOCK 만 수정 유발 + findings ≤5 + over-engineering 경계
  프롬프트. ② 지연 증가 → 낮음 강도 skip·타임아웃 fail-open. ③ 노트 교차 대화 누출 →
  세션 노트 대화 한정 주입 + 제품 노트 claim 비저장 + bounded 발신자 주입 억제
  (ADR-20260715T140002). ④ 신규 권한 catchup 누락 lockout → admin catchup 명시
  (web_context.py). ⑤ 배포 시 stale agent 이미지로 alembic 0042 누락 → 배포 후
  alembic_version 직접 검증 예정 (deploy-migration-stale-agent-image 선례).
- Open Questions: 리뷰 판정 품질 (BLOCK 검출률/오탐률) 은 라이브 축적 후 콘솔 통계로 관찰.
- Human Approval Needed: 없음 (deploy_scope: included — FIRST_REQUEST.md 전역 선언, 자동 배포
  근거 기록. 인증/인가 구조 변경 아님 — 신규 read-only 권한 1건 추가는 비파괴 additive.)

## REV-20260715-0002 [SUBAGENT:general-purpose] — APPROVE-WITH-FIXES (반영 완료)
- Related Change: CHG-20260715-0001
- Reason: §18.8 dispatch — 권한/격리(보안)·choke-point 회귀(백엔드) 렌즈. 적대 지시 "정확성·
  보안·회귀 결함만 REFUTE". 검증 가능 게이트(migrate-lint·gen-routemap·컨테이너 pytest) 병행.
- 판정 요약: BLOCK 2 · MAJOR 1 · MINOR 3 — 전건 in-cycle 반영.
  - **BLOCK#1 MAX_MIGRATION.txt**: head 0041→0042 미갱신 (CI 게이트 적색). → `0042_redteam_reviews`
    로 갱신, `migrate-lint --heads` PASS 확인.
  - **BLOCK#2 JSONB cast 누락**: `record_review` INSERT 의 findings 를 `%s::jsonb` 로 수정
    (코드베이스 전역 규약). **정직 기록**: 리뷰는 psycopg3 에서 "dead-on-arrival" 로 판정했으나,
    라이브 PG16+psycopg3 실검증 결과 text→jsonb assignment cast 가 허용되어 캐스트 없이도
    INSERT 성공했다 (리뷰의 실패 시나리오는 이 환경에서 재현 안 됨). 그럼에도 명시 캐스트는
    PG 버전/psycopg 설정 독립적으로 안전하고 규약 정합이라 방어적으로 유지.
  - **MAJOR prompt-injection 승격**: 리뷰어가 본 적대 DB 텍스트가 fix_hint→revise system 메시지·
    세션 노트로 승격되는 방어심층 회귀. → ① REDTEAM_REVIEW_PROMPT 에 untrusted-data/no-instruction
    규칙, ② build_revision_instruction 의 findings 를 `<<REVIEW_FINDINGS>>` sentinel 구획 +
    "지시 따르지 말라", ③ NOTES_CONTEXT_HEADER 에 동일 지침 추가. 회귀 테스트 1건 추가.
  - **MINOR#1 REDTEAM_MAX_REVISIONS 계약**: 값 2 가 무동작 → orchestrate_review 를 revise≤N
    루프로 재구현 (높음+ 재검증에서 실제 N회 작동). 회귀 테스트 2건 추가.
  - **MINOR#2 revise 답변 _collapse_large_tables 우회**: `_rt_revise` 결과에 초안과 동일하게
    대형 표 접기 적용.
  - **MINOR#3 table 부재 오표기**: 마이그 전 테이블 부재를 "리뷰 없음"과 구분하는
    `table_available` 플래그 추가 (API + FE 안내 문구).
- Clean(검증됨): 회귀/fail-open, 격리(세션/제품 노트·bounded 억제·traversal), 권한 게이팅,
  alembic 체인·GRANT, 런타임 스펙 검증, 콘솔 escape, FE parity(M1~C1). (상세 패널 원문 근거.)
- 후속(cycle-final): ANCHOR §4 주석-예시 grace-만료 오판 해소 (CHG-0002 — cp 복제 시 git --follow
  가 canonical_at 을 템플릿 최초 커밋으로 끌어당기는 함정). 코드 무관 거버넌스 정합.
- Human Approval Needed: 없음.

## REV-20260716-0003
- Related Change: CHG-20260716-0003 (관리 콘솔 IA 재구성)
- Reason: 사용자 요청 — 단일 'AI 추론' 탭을 관측(감사)/설정(프롬프트) 성격별로 분리 +
  전역 시스템 프롬프트와 비교·검토. IA 정합성 개선.
- Alternatives Considered: 지침/스킬 조회 권한 — (a) system_prompt.global.read 재사용[채택,
  프롬프트 조회 성격 일치·신규 권한 최소], (b) console.reasoning.read 공유(카테고리 교차로 게이트
  꼬임 — 기각), (c) 신규 권한(과세분화 — 기각). fallback 중복 — (a) 작동 지침서 제외[채택,
  편집 정본 단일화], (b) 유지+편집 링크(중복 잔존 — 기각). 둘 다 사용자 확정.
- Risks: ① 권한 카테고리 재배치(console.reasoning.read: system→audit)로 기존 admin 접근 변동 →
  권한 자체는 동일해 admin catchup·backfill 불요(카테고리 매핑만 변경), FE↔카탈로그 정합은
  test_permission_dependency_map 이 검증. ② 지침/스킬 조회를 system_prompt.global.read 로 게이트 →
  전역 프롬프트 조회권 보유자가 지침/스킬도 조회(합리적 — 같은 프롬프트 구성 조회). ③ guidance
  엔드포인트 권한 변경 → ROUTEMAP 재생성(CI gate).
- Open Questions: 없음.
- Human Approval Needed: 없음 (read-only 권한 재배치, 비파괴. deploy_scope: included).

## REV-20260716-0004 [SUBAGENT:general-purpose] — APPROVE-WITH-FIXES (반영 완료)
- Related Change: CHG-20260716-0003 (콘솔 IA 재구성)
- Reason: §18.8 dispatch — 권한 카테고리 재배치(인가 표면)·엔드포인트 권한 변경·FE 정합 렌즈.
  적대 지시 "권한 정합(M5)·접근 회귀·엔드포인트 auth·FE 배선 REFUTE".
- 판정: 전 기능 영역(권한맵 M1~M5·접근 회귀·엔드포인트 auth·FE 배선·ROUTEMAP) **CLEAN**,
  BLOCK/MAJOR 0. MINOR 4건(문서/주석 drift)만 — 전건 반영:
  - #1 admin_reasoning.py 모듈 docstring(구 "시스템>AI추론"·"console.reasoning.read") → 감사/설정
    분리·권한 분리로 갱신(ROUTEMAP L0 모듈 설명 정합).
  - #2 admin.html·admin.js 주석의 mountGuidancePanel/mountSkillsPanel → mountGuidanceRegistryPanel.
  - #3 web_context 2072 catchup 주석 "시스템>AI추론" → "감사>AI추론".
  - #4 admin.js 311 주석 "시스템 카테고리 하위" → "감사 카테고리 하위".
- 검증됨(CLEAN): console.reasoning.read DEPS=[console.audit.access, console.access] ↔ web_context
  audit leaves 일치(M5), system 참조 잔재 0; admin 은 audit access+reasoning.read catchup 둘 다 보유
  →탭 노출 무회귀; guidance FE 게이트(system_prompt.global.read)↔백엔드 일치; renderReasoning/
  showGuidanceDetail 시그니처 caller 정합; 설정 프롬프트 3항목(row/article/mounter) 키 일치; ROUTEMAP 재생성.
- Human Approval Needed: 없음.

## REV-20260716-0005 [SUBAGENT:general-purpose] — APPROVE-WITH-FIXES (반영 완료)
- Related Change: CHG-20260716-0004 (콘솔 서브탭 통합)
- Reason: §18.8 dispatch — 서브탭 권한 OR·pane 재조립 회귀·FE 정합 렌즈.
- 판정: 기능(서브탭 게이팅·lazy load·요소 id 바인딩·HTML 균형·권한맵) CLEAN, key-drift 회귀 MAJOR 2
  + MINOR 2 — 전건 반영:
  - **MAJOR#1 대시보드 딥링크 빈 pane**: 서버 위젯이 옛 키(tab:"usage"·"ai-ops")를 보내는데 통합으로
    해당 pane 부재 → switchTab 착지 시 전 pane 비활성=빈 화면. → switchTab 진입부에 레거시 키 별칭
    매핑(usage→usage·ai-ops→ops·reasoning→reasoning) + ai-console 전환 후 `activateAiConsoleSubtab`
    으로 대응 서브탭 활성화(권한 게이팅 반영). 서버 계약(admin_console.py:562/594) 실측 정합 확인.
  - **MAJOR#2 통합 pane 스크롤 유실**: styles.css scroll 그룹이 옛 3키만 열거 → ai-console 미포함
    으로 하단 콘텐츠 잘림·가로 넘침(TASK-0198 회귀). → 그룹에 `data-admin-pane="ai-console"` 대체.
  - **MINOR usage 레이아웃 가드 미연결**: `.admin-pane[data-admin-pane="usage"] .summary-metrics/> *`
    → `.admin-subpane[data-ai-subpane="usage"]` 재타겟.
  - **MINOR(방어) bindPaneSubtabs firstKey undefined**: 보이는 서브탭 0(현재 unreachable)이어도 정적
    is-active 마크업이 미로드로 남지 않게 전 subpane 숨김 fallback 추가.
- 검증됨(CLEAN): 서브탭 권한 게이팅(reasoning-only 사용자 → reasoning 서브탭만·loadReasoning만 호출),
  요소 id 바인딩(initialize 1회·subpane nested 여도 getElementById resolve), adminState 초기화,
  설정 prompts activateSettingsPanel/검색 필터, canSeeTab OR+AND, HTML 균형, permission_dependency_map.
- Human Approval Needed: 없음 (프론트 전용, read-only, 데이터 무변경).

## REV-20260716-0006 [SKIPPED:non-policy-doc]
- Related Change: CHG-20260716-0005 (서브탭 sticky)
- Reason: CSS 전용(.admin-subtabs position:sticky) — 마크업·JS·백엔드·권한·데이터 무변경.
  로직/보안/회귀 표면 없음(순수 시각 고정). §18.8 패널 dispatch 키워드 미매칭. 시각 검증은
  배포 후 PB-0008(sticky 스크롤 동작)로 수행. 따라서 subagent 패널 SKIP.
- Human Approval Needed: 없음.

## REV-20260722-0001 [SKIPPED:additive-runtime-knob]
- Related Change: CHG-20260722-0001 (리뷰어 토큰 할당량 콘솔 설정 신설 + "리뷰 실패" 타임아웃 진단)
- Reason: 사용자 요청 — 콘솔 "리뷰 실패" 표시가 내부 에러인지 의도인지 검토 + 에러면 수정.
  진단 결론: verdict=`error` = 리뷰어 LLM 100% 타임아웃 (라이브 DB 8/8 @ ~25s, fast-fail 0).
  표시·fail-open 은 의도된 설계이나 실패율 ~17% 는 운영 결함(리뷰어 alias 의 고정 thinking 5000
  → 상시 25s). 사용자 결정: 콘솔에서 토큰·타임아웃 튜닝하도록 knob 노출.
- Risk Grade: Minor→Major (additive 런타임 설정 + optional 인자 + 배포 필요). 인증/인가·개인정보·
  파괴적 데이터·마이그레이션 없음.
- Alternatives Considered: (a) thinking-off 전용 리뷰어 alias 신설 — 근본 해결이나 litellm
  라우팅/fallback 변경 폭이 크고 리뷰 품질 trade-off — 기각(사용자 미선택). (b) 타임아웃만
  상향(무배포) — 근본 미해결·답변 지연↑ — 부분책. 사용자가 콘솔 knob 방식(토큰+타임아웃 노출) 선택.
- Risks/Mitigations:
  ① `max_tokens` 를 리뷰어 고정 thinking 예산(5000) 아래로 내리면 Anthropic 호출 400 →
     오히려 "리뷰 실패" 증가. 완화: spec `minimum=6000` 이 UI·clamp 단에서 하한 강제.
  ② 토큰 상향은 호출 지연을 줄이지 않음(지연 주범은 thinking) — 오해 방지 위해 설명에 명시
     ("값을 올려도 지연은 줄지 않습니다 — 지연은 타임아웃으로 조절").
  ③ 하위호환: override None/0 이면 기존 8192 task cap 과 동치 — 무설정 시 byte-동치(무회귀).
- Verification: 자동 87건 통과(test_redteam 36[신규 5]·test_runtime_settings·test_admin_reasoning),
  ruff clean, `REDTEAM_MAX_TOKENS` serialize `redteam` 그룹 노출 확인. 배포 후 PB-0008 로 설정
  패널 "리뷰어 토큰 할당량" 렌더 + 조정 반영 확인 (POST-DEPLOY).
- Subagent Panel: reasoned-skip — additive 런타임 설정 + optional 인자, 보안/인가/데이터/스키마
  표면 없음, §18.8 dispatch 키워드 미매칭. 결정론 로직(override 전달·하한·폴백)은 단위 테스트로 커버.
- Human Approval Needed: 배포 confirm (외부 영향 행동) — 사용자 승인 후 진행.
## REV-20260724T071500-redteam-model-align [SUBAGENT: BLOCK 0 — MAJOR1(effort=low) + MINOR2(doc·forward-caveat) 반영·수용]
- Related Change: CHG-20260724-0001 (리뷰어 모델을 답변 모델에 정합)
- Decision Rationale:
  ① **정합 매핑 수단 = 기존 `conversation_answer_model` 재사용** — 새 매핑 테이블을 만들지 않고,
     사용자 대면 답변이 이미 쓰는 edge-free -chat alias 도출 함수를 재사용한다. 리뷰어 호출도
     동일 Bedrock/OAuth 경로라 alias 정합이 자동 성립하고, 미래 모델 추가 시 단일 SSOT
     (`_CONVERSATION_ANSWER_ALIAS`)만 갱신하면 리뷰어도 따라온다.
  ② **env pin = hard-override 유지** — `AGENT_REDTEAM_MODEL` 설정 시 답변 모델과 무관하게 고정.
     이전 동작(env→litellm 직결)과 동일 의미라 무회귀이자 운영 비용 통제 escape hatch. 미설정이
     기본 = 답변 모델 정합.
  ③ **identity 주입은 선택이 아닌 필수** — sonnet(adaptive)은 OAuth 토큰으로 나갈 때 첫 system
     블록이 Claude Code identity 여야 429 를 안 맞는다(`_call_llm` 은 하고 리뷰어 경로는 안 했음).
     주입 없이 model 만 바꾸면 sonnet 리뷰가 조용히 skip 되는 무동작 버그라, 미러 주입이 정합의 전제.
  ④ **적대 패널 MAJOR 대응(effort=low)** — 리뷰어는 짧은 JSON 판정만 내는 경계 작업인데 sonnet
     기본 effort=high 는 (a) `REDTEAM_TIMEOUT_SEC`(25s) 초과→timeout→error→리뷰 skip
     (CHG-20260722-0001 이 haiku 에서 8/8 100% 타임아웃으로 이미 실측), (b) max_tokens 안 thinking 이
     JSON truncate → 회귀. `output_config.effort=low` 로 지연·truncation·비용을 함께 낮추되 **모델
     tier(정합)는 유지**. 대안 "timeout 상향"은 사용자 지연을 늘려 기각, "리뷰어 haiku 고정"은 사용자
     요청(정합)에 반해 기각. `AGENT_REDTEAM_EFFORT` env 로 조정 가능.
- Subagent Panel (§18.8, general-purpose 적대 리뷰어): **BLOCK 0**. correctness·security·routing 전 축
  반박 시도 결과 크래시/오답전달/400/gemma-leak/무한루프 없음, fail-open 유지, identity 주입이
  injection-defense 무약화 확인.
  - **MAJOR (axis4) 반영**: 리뷰어 timeout/effort 가 haiku 튜닝인데 sonnet-high 에 적용돼 지연+리뷰
    무력화 → effort=low 주입으로 해소(위 ④). MINOR(axis3) truncation 도 동일 수정으로 커버.
  - **MINOR (axis5) 반영**: `REDTEAM_MAX_TOKENS` 콘솔 description 이 "리뷰어=haiku 고정 5000" 라 stale
    → "답변 모델 정합·sonnet adaptive effort=low" 로 정정.
  - **MINOR (axis2) 수용·미수정(설계)**: 미래 adaptive claude(예: sonnet-6)가 `_ADAPTIVE_THINKING_PREFIXES`
    미등록이면 identity 미주입→429→리뷰 skip. 이는 이 diff 가 도입한 게 아니라 model_catalog 의
    기존 H2 유지 위험(신모델 추가 시 prefix 갱신)의 재사용이며 프로덕션 경로와 동형. 단일 SSOT
    (`_ADAPTIVE_THINKING_PREFIXES`)가 이미 있어 신모델 등록 시 함께 갱신하면 자동 정합. fail-open 이라
    안전(오답 아님, error 로 관측). 별도 코드 추가 없이 컨벤션으로 관리.
  - **NOTE (env pin 미검증 escape hatch)**: `AGENT_REDTEAM_MODEL=auto/edge/claude` 오설정 시 리뷰어가
    gemma/400 로 샐 수 있으나 이는 pre-change 와 동일(무회귀), 운영자 명시 오설정 영역이라 미가드.
- Verification: 자동 45건 통과(test_redteam — 기존 36 + 신규 9)·ruff clean(변경 5파일). 전체
  feature-0002+0003 회귀는 llm.py 시그니처 변경 후 재실행(환경 의존 2건 제외 — TEST.md 참조).
  배포 후 라이브 실증(sonnet 대화의 리뷰가 sonnet 으로·effort=low 로 timeout 소멸, admin 'AI 추론'
  탭 model 컬럼에 sonnet 표기)은 POST-DEPLOY.
- Human Approval Needed: 배포 confirm (외부 영향 행동) — 사용자 승인 후 진행.
## REV-20260724-0001 [SUBAGENT:general-purpose] — APPROVE-WITH-FIXES (반영 완료)
- Related Change: CHG-20260724-0002 (BLOCK 검출 후 답변 미수정 전달 근본 원인 수정 — revise/rederive
  재프롬프트 지시 role system→user)
- Related Requirement: 사용자 요청 (entry arg-given dispatch, 2026-07-24) — 콘솔 '추론' 이
  결함 미수정 전달을 보고, 근본 원인 추적·수정.
- Risk Grade: Major (핵심 답변 전달 파이프라인 correctness — revise 경로가 사실상 비동작이던 것을
  정상화). 인증/인가·개인정보·파괴적 데이터·마이그레이션 없음. 프론트·API·스키마·설정 무변경.
- Root-cause 확증 (라이브): redteam_reviews verdict='revise' 42건 중 35건(83%) revision_applied=false
  (매일 일관); 실패 run 전부 revise LLM 호출 completion_tokens=3(빈 응답). trailing `role: system`
  지시가 litellm 에서 top-level system 으로 hoist → 초안 assistant 가 마지막 turn=Anthropic prefill
  → 재작성 대신 이어쓰기 → 완결 초안은 빈 응답 → None→fail-open 미수정 전달. 동일 gateway·모델
  재현으로 prefill 연속(리뷰과정 누설) vs user turn 완결 재작성 대조 확인.
- Subagent Panel: [SUBAGENT:general-purpose] 적대 리뷰 — VERDICT=APPROVE-WITH-FIXES.
  - 확인(결함 없음): (1) Anthropic 메시지 시퀀스 유효(호출 시점 messages 는 절대 assistant 로
    끝나지 않음 — tool-branch 는 assistant(tool_calls)→tool 로 닫히고 최종 텍스트 답변은 messages 에
    미append) → assistant(draft)+user(instruction) 부착이 모든 도달 상태에서 유효 alternation.
    (2) 보안: 지시의 신뢰불가 findings 는 sentinel datamark 로 이미 구획(role 무관) — system→user
    이동은 신뢰불가 콘텐츠가 최고권한 system 채널에서 빠지므로 인젝션 posture 오히려 개선(무회귀).
    (3) rederive 도구 루프: 매 _call_llm 앞이 user/tool turn — 어느 라운드도 trailing assistant
    prefill 아님. (4) fail-open 보존·개선(prefill 연속 답변 대체 class 제거). (5) 회귀 테스트가
    불변식 고정.
  - WARN 1건(반영): closure 가 stale outer `answer` 를 캡처 → REDTEAM_MAX_REVISIONS=2(높음/매우높음)
    2회차 수정이 원 초안(draft A)을 앵커로 findings(draft B 대상)를 수정하는 mis-anchor. 기존 prefill
    결함이 1회차에서 empty→break 로 마스킹했으나 본 수정이 2회차를 도달 가능하게 만들어 노출.
    **수정**: orchestrate_review 가 revise_fn/rederive_fn 을 `(instruction, draft=final_answer)` 로
    호출(콜백 계약 v2) + closure 가 `draft` 인자 사용. 테스트 `drafts_seen==["draft","revised-1"]` 로
    앵커링 고정.
- Verification: 자동 39건 통과(test_self_review_messages 3[신규]·test_redteam 36[콜백 2-arg 계약·
  다회 draft 앵커링 강화 포함]), 결정론 재현(gateway A/B), ruff/py_compile clean. 전체 make test 의
  잔여 실패 5건은 라이브-PG/env 의존 pre-existing flaky(REPORT.md §4/§8 — main 대조 시 실패 셋이
  런마다 상이[2·4·5], revise 경로 무관). 배포 후 라이브 재검증: 신규 revise 의 revision_applied=true
  확인 (POST-DEPLOY).
- Human Approval Needed: 배포 confirm (외부 영향 행동 — 답변 파이프라인 변경) — 사용자 승인 후 진행.
