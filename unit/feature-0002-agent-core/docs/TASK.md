---
doc_type: TASK
feature_id: feature-0002-agent-core
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## TASK-20260807T130000-redteam-abortable-review — 자가 검증 대기 구간의 사용자 탈출구 복구 (Major §12.3)

`/_dqa:conversation_audit` 라이브 진단(FR-redteam-first-pass-unabortable). 대화 `…226e27aa`
에서 답변 본문은 **9.6초**에 완성됐는데 리뷰어 호출이 `REDTEAM_TIMEOUT_SEC`(운영 300초)까지
무응답이라 전달이 **312초** 지연됐고, 그 구간에는 취소·'즉시 답변' 체크도 진행 표시 갱신도
없어 사용자에게는 "응답이 멈춘" 것으로 보였다. 신규 사용자의 첫 인사 턴이었고 대화는 2메시지로
종료됐다.

- [x] 근본 확정 — `orchestrate_review` 의 `abort_fn` 은 **반복 수정 루프에만** 걸려 있었다.
      최초 검증 패스와 재검증 호출은 상한까지 블로킹하며 어떤 신호도 보지 않았다
      (`agent_core.py:6473` 이후 다음 취소 체크는 6631줄 = 재도출 내부)
- [x] corroboration(30일) — red-team 이 총 응답시간의 과반인 턴 **52건** · 120초 초과
      **19턴/15대화** · 리뷰 error **12/247**. 성공 리뷰의 정상 지연은 p50 20초(14일 209건)라
      300초 대기는 분포 밖
- [x] 봉인 — 리뷰어 대기를 폴링으로 전환(`_await_review_interruptible`), 최초·재검증 **양쪽**
      배선, 진행 표시 주기 갱신, 중단 유예로 판정 손실 방지
- [x] **§18.8 적대 검증(backend + qa, codex 는 quota 소진 — 미검증을 검증으로 보고하지 않음)** —
      **BLOCKING 3 · MAJOR 12 전건 흡수**, MINOR 12 중 8 흡수·4 는 선재/범위 밖 명시.
      핵심 흡수: ① 출하 상수 미잠금(폴링 1s→300s 뮤턴트가 전 스위트 통과 = 원 인시던트 재현)
      ② 대기 포기가 리뷰어 상한과 무관해도 통과 ③ 재검증 중단이 '검증하지 않은 결함' 고지를
      사용자 답변에 찍음 ④ 사용자 중단이 콘솔에서 "리뷰 수행 실패"로 표시되고 리뷰어 오류율을
      부풀림(admin.js cross-ref) ⑤ abort 폴링이 메모리 DB 왕복 ~300배 증폭
- [x] 테스트 — 신규 **25**건(출하 상수 계약 3 + 헬퍼 14 + orchestrate 배선 8) · 기존 red-team 127 PASS
- [x] verify-completion PASS → PR #1195 → main `6b0f50c0` 머지 → **배포 완료**
      (`make deploy-web` 전체 스코프, 5서비스 GIT_COMMIT=`6b0f50c0` running/healthy,
      배포본 런타임 실증 7항목 True, web /healthz ok)
- [ ] 라이브 대화 실측(대기 중 버튼 즉시 반응 · 진행 표시 갱신 · 콘솔 중단 표시 PB-0008 ·
      `redteam_ms>120초` 비율 추이) — 다음 audit 의 corroboration 재측정 대상

## TASK-20260806T170000-label-namespace — 라벨 네임스페이스: 죽은 클러스터 배제·스키마 표기·결정적 매칭 (Minor §12.3)

직전 cycle 의 적대 검증이 지목한 "진짜 원인"을 실측으로 확정하고 수정한다.

- [x] 운영 현황 재실측 — `analysis_verify` 는 배포 후 48콜/34대상(1.4회)로 정상, 판정 행 95→112
      (24시간 창에 배포 전 순환 구간이 섞여 4.9회로 보이던 것은 착시)
- [x] orphan 실측 — **2회 정정**. ① SQL 직접 조인은 키 불일치로 74.2% 허수(schema_name 의 의미가
      두 테이블에서 다르다) ② `rag_objects` 만 본 50.6% 도 오류 — 라벨 역기록이 멤버 종류로 갈린다
      (테이블→rag_objects, 루틴→routine_objects). **정확값 3.4%(63/1844)**, `atum2_db_1` 유효
      84행/770멤버. 초판이 버리려던 933행 중 870행(93%)이 살아있는 루틴 클러스터였다
- [x] 영향 경로 확정 — **L3 입력이 전량을 읽어 오염**(저장 90/887 ↔ 실제 84/770) → 그 수치가 답변
      프롬프트에 실림. 답변 경로에도 동명 다중행 문제가 남아 있으나(12그룹) 별도 cycle 범위
- [x] 수정 ①②③ + 테스트 8건
- [ ] 적대 검증 → verify → PR → 머지 → 배포 → 라이브 재합성 확인

## TASK-20260806T110000-aiops-hygiene — AI 운영 현황 실측 후속: stale 클러스터 요약 차단 + 도메인 합성 계측 도달 (Minor §12.3)

사용자 요청("AI 운영 현황 전반 실측 후 유사 이슈 검토")으로 16개 task 를 실측한 결과, 선행
cycle(feature-0036 판정 순환)과 **같은 계열의 결함 2건**을 찾았다.

- [x] 전반 실측 — task 별 호출·대상 반복도·산출 대비·실패·taxonomy 정합. `cluster_*` 의 높은
      반복도는 배치 때문이며 낭비가 아님을 확인(초기 신호 오독 정정), taxonomy 미분류 0건
- [x] ~~stale 소비 차단~~ — **적대 검증에서 반증되어 철회**. 다중행의 상당수가 "버전"이 아니라
      동시 생존하는 다른 클러스터(라벨 충돌)였고, 최신 1건으로 좁히면 79-멤버 클러스터 설명이
      사라지는 **내용 손실**이 발생한다. 정합 편차 339→645(1.9배 악화) 실측. 상세는 MODIFY.md
      CHG-20260806T110000 "철회한 변경" 절 — 진짜 원인(라벨 네임스페이스·크로스-스키마 재사용)은
      별도 cycle 범위
- [x] **계측 도달** — `domain_synthesis` 계측이 dict 라 sweep 이 버려 무음이었다(이 워커 네 번째
      재발). payload allow-list 등재 + `attempted` 추가(콜만 태우고 산출 0인 pass 관측)
- [x] 테스트 — attempted 를 **동작으로** 단정(소스 순서 검사는 변이를 통과시켰다) · payload 도달 ·
      0-tick 기록 · insight 호출 예외흡수 AST 판정(윈도우 근사가 주석 길이에 깨지던 것 교체)
- [ ] verify → PR → 머지 → 배포 → 라이브 확인

**이번 cycle 제외**: `shared/model_catalog.py` 유령 taxonomy 2건(`metadata_summary`·
`metadata_prompt_gen` — 호출부 없음·전체 기간 사용 0건)은 §13.2.2 F2 단일 mutator 대상이고
`ai/claude/feature-0003-usage-records` 가 편집 중이라 그 세션 머지 후 처리한다(화면 영향 없음).

**정정**: 실측 1차 보고에서 "`domain_summaries` 소비처 0곳"이라 했으나 **오류**다. 테이블명으로만
grep 해 모듈 경유 호출을 놓쳤다 — `cluster_context._domain_line` 이 `domain_synthesis.load()` 로
읽어 답변 근거 한 줄로 주입한다(설계대로 배선됨). 5행 전부 합성 완료·대기 0.

## TASK-20260804T0630-summary-bootstrap-deadlock — 요약 미보유 대화가 PG 읽기 실패로 오판되던 부트스트랩 교착 (Major §12.3 — 선행 cycle 의 writer 복구를 실효 0 으로 만들던 직접 원인)

- 출처: 선행 cycle `TASK-20260804T0454-summary-writer-wiring` 의 **배포 후 라이브 실증**에서 발견.
  writer 를 복구하고 `c4701a17` 로 web·ask-worker·insight-worker·ops-scheduler 전량 배포한 뒤
  배포본에서 `refresh_conversation_summary()` 를 실호출했으나 `saved=False`, `agent_runtime.summary`
  여전히 **0행**. 로그: `load_memory_context: PG partial failure (summary=False msgs=True kv=True),
  falling back to MySQL`.
- **근본 원인**: `_read_runtime_pg` 의 호출 계약은 "`None` = 읽기 실패"인데
  `PgRuntimeBackend.load_summary` 가 **행 없음도 `None`** 으로 돌려줬다. 두 사건이 구분되지 않아
  **요약이 아직 없는 대화 전부**가 PG 읽기 실패로 분류되고, 큐레이션 훅은 conn=None 으로 호출하므로
  MySQL 폴백에서 예외 → 요약 미저장.
  → **요약이 없으니 읽기가 실패하고, 실패하니 첫 요약을 영원히 못 쓰는 교착.** 선행 cycle 의 writer
  복구가 코드상 옳았음에도 라이브에서 실효 0 이던 직접 원인이다.
- **왜 단위 테스트가 못 잡았나(정직 표기)**: 선행 cycle 의 테스트는 `load_memory_context` 를 통째로
  스텁했다. 그 함수의 **PG/MySQL 분기 자체**가 결함 지점이라 스텁이 결함을 덮었다. 배포 후 실호출
  검증이 아니었으면 "고쳤다" 고 보고한 채 라이브는 그대로였을 사안.
- [x] `modules/runtime_backend.py`: `load_summary` 반환을 `Optional[str]` → `str` 로, 행 없음/NULL 은
      **`''`**. 실패 신호(`None`)와 데이터 부재를 분리. 하위 소비처 정합 확인(MySQL 폴백도 falsy 로
      넘기고 `_build_summary_payload` 는 `summary or ""`).
- [x] `modules/memory.py`: `load_memory_context` 의 `is not None` 검사에 계약 주석 명시(코드 무변경).
- [x] `tests/test_summary_bootstrap_deadlock.py`(5) 신규 — 반환 계약 3 + PG 경로 통과(conn=None 으로
      폴백 진입 시 AttributeError 라 통과 자체가 증거) + **진짜 실패는 여전히 폴백**(규약 무디게
      만들지 않았음). 결함 재주입 **역검증** 확인(2건 FAIL).
- [x] `make test` 전량 exit 0 · verify-completion PASS · codex 적대 리뷰(P1 0/P2 1 흡수) ·
      PR #1138 머지(`fba8ee9f`) · 전체 롤아웃 배포(web·워커 전량 `fba8ee9f`).
- [x] **라이브 재실증 PASS**: 배포본 ask-worker 에서 `refresh_conversation_summary()` 실호출 →
      `saved=True`(12.7s), `agent_runtime.summary` **0행 → 1행**, 저장 본문 육안 확인.
      자동작성 `meta.summary_count` 가 account·role 양쪽에서 **0 → 1**(종전 상시 0).

## TASK-20260804T0454-summary-writer-wiring — 대화 요약(`agent_runtime.summary`) writer 배선 복구 (cross-feature: 코드 거주=feature-0002, 소비=feature-0003 프롬프트 자동작성 / Major §12.3 — ask 당 외부 LLM 1회 추가)

- 출처: `/_template:entry` — "각 사용자 별 시스템 프롬프트 자동 생성(개인·계정·역할)의 배선이
  끊긴 부분을 전역 점검 후 수정". 정본 cycle 은 feature-0003 `TASK-20260804T0454-prompt-autogen-wiring`.
- **결함**: `modules/llm.py` 의 `_refresh_summary_after_step` / `_refresh_summary_after_ask` 는
  **호출자가 0** 이다. 유일 호출자였던 `agent_cli.py` 가 "죽은 코드" 로 삭제되며(`68ed7a76`,
  2026-06-02) 함께 끊겼고, `agent_core.py` 는 애초에 요약을 쓰지 않았다. `save_memory_summary()`
  미실행 → **`agent_runtime.summary` 0행**(라이브 대화 296건). 두 함수 안의 타 모듈 심볼
  (`log_timing`/`load_memory_context`/`save_memory_summary`/`_record_step_summary`/
  `sanitize_user_text`/`_near_run_deadline`)은 `llm.py` 가 하나도 import 하지 않아 **호출 즉시
  NameError** 이기도 했다 — 호출자 0 이라 테스트에도 안 잡혔다(§gate-hidden-call-test-blindspot).
- **영향**: `agent_runtime.summary` 를 읽는 소비처가 조용히 빈 신호를 받았다 —
  ① feature-0003 의 제품·역할·개인 시스템 프롬프트 자동작성("실제 분석 사례 요약" 블록 항상 미생성,
  `meta.summary_count` 항상 0), ② `insight.run_account_insight_pass`(이미 LEFT JOIN 으로 우회 중이며
  주석에 "이 배포처럼 요약 쓰기가 비어도" 라고 단절을 기록해 뒀다 — 인지됐으나 미복구).
  `load_memory_context` 의 summary 축은 agent 루프에서 쓰이지 않아 답변 품질 회귀는 없었다.
- **수정**: `_summary_deps()`(심볼 지연 해소) + `refresh_conversation_summary()` 신설,
  `agent_core.run_post_answer_curation()` 에서 호출. 답변 확정 + (worker 경로) job terminal 이후라
  **사용자 대기시간 증가 0**, 빈도 ask 당 1회. 게이트는 기존 `AGENT_SUMMARY_REFRESH`(운영 .env 에
  이미 1) — 설정은 ON 인데 코드 경로가 없던 상태의 해소이므로 새 스위치를 만들지 않는다.
  사용자 결정(AskUserQuestion 2026-08-04): "복구 + 기존 env 게이트 유지".
- [x] `modules/llm.py` · `agent_core.py` 수정 + `tests/test_summary_writer_wiring.py`(8) 신규 —
      **배선 가드**(run_post_answer_curation 이 요약 갱신을 호출하는지)가 load-bearing.
- [x] `make test` 회귀 exit 0 · 배포(web + 워커 전량) 완료. **단, 배포 직후 실증에서 실효 0 확인** —
      요약 미보유 대화를 PG 읽기 실패로 오판하는 부트스트랩 교착이 별도로 있었다
      (`TASK-20260804T0630-summary-bootstrap-deadlock`). 그 수정(PR #1138, `fba8ee9f`) 후
      **라이브 실증 PASS**: summary 0행 → 1행, `meta.summary_count` 0 → 1.

## TASK-20260803T190000-precondition-verified-or-unknown (current cycle) — 리뷰가 조회한 적 없는 객체의 라이브 상태를 단정하던 결함 봉인 + 상시 감지기 (Major §12.3 — core 시스템 프롬프트)
- 출처: `/_dqa:conversation_audit` PB-0008 라이브 육안검증 중 발견(`FR-review-precondition-assumed-not-verified`). 사용자 지시("잔여 항목도 작업을 진행해주세요") + 범위 승인 **A+C**(AskUserQuestion 2026-08-03).
- **corroboration(신규 측정, 90일)**: `.sql` 첨부 대화 87건에서 객체 상태 단정 **90건 중 43건(47.8%)**이 그 대화의 어떤 도구 결과에도 그 객체명이 없었다. `미확인` 표기는 **0건**. 관측 구간이 2026-05-28~08-03 에 걸쳐 있다.
- **귀속 정정(중요)**: 앞선 보고에서 이를 "내가 만든 계약 결함" 으로 단정했으나 **틀렸다**. 측정 결과 이 행동은 시간-방향 계약(2026-07-30 출하) **이전부터 광범위**했다. 정확한 진단은 — (1) **오래된 구조적 공백**: 상태 단정에 대해 객체별 검증을 요구하는 규칙이 없었고 `미확인` 이 출력 값으로 제시된 적이 없다(90일 0건). (2) **내 계약의 기여**: `적용 전제` 절을 만들라는 지시가 그 단정에 **표 형태의 눈에 띄는 자리**를 줬고 "stated as fact" 문구가 확정 압력을 더했다. 원인이 아니라 **가중 요인**이다.
- **실질 손해(라이브)**: 재현 대화가 약 **148만 행 실존** 테이블을 "현재 미존재" 로 적고(조회 0건) 그 결과 대용량 테이블에 3중 복합 PK 를 추가하는 마이그레이션 리스크를 통째로 놓쳤다.
- **해결(A)**: `_ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE` 의 "stated as fact" 제거 → **"모든 행은 검증된 사실이거나 `미확인`"**. `미확인` 을 1급 출력 값으로 승격. 권한거부·스코프경고·미조회 ⇒ 미확인(부재 아님). **0행은 범위 조건부** — 정확한 식별자 + 도구가 자기 커버리지를 명시한 경우에만 그 범위 내 부재로 말하고 범위를 함께 적는다(과교정 방지). 첨부의 `CREATE TABLE IF NOT EXISTS` 는 현재 존재 여부의 증거가 아님. **미확인은 공짜가 아님** — 결정이 걸린 객체는 최소 1회 조회 시도 의무(`verify > 미확인 > guess`). SYSTEM_PROMPT 미러도 동일 3요소로 정합.
- **해결(C)**: `bin/measure-precondition-grounding.py` 신설 — 상태 단정 ↔ 도구 호출 대조를 재현 가능하게 측정하는 **스크린**(지표 아님). RO 트랜잭션 + statement_timeout + `ON_ERROR_STOP` + 빈 결과 fail-closed.

### §1.1 Implementation
- `src/agent_core.py`: `_ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE` 전제-절 규칙 재작성(5개 하위 규칙) + SYSTEM_PROMPT 미러 동기화.
- `bin/measure-precondition-grounding.py`(신규): 답변별 객체 상태 단정 추출 → 대화 tool 결과 대조 → 미검증 비율·`미확인` 객체 수·지목 대화 목록. 오탐/누락을 docstring 과 CLI 출력에 명시.
- `tests/test_review_proposed_change_framing.py`: 계약 5건 추가(검증-또는-미확인·미확인 매핑·0행 범위조건·미확인 남발 방지·미러 정합).
- `tests/test_precondition_grounding_detector.py`(신규 10건): 감지기 집계 계약 + fail-closed + RO/타임아웃 + '하한' 오표기 금지.

### §1.2 Completion Checklist
- [x] corroboration 선측정(90일 47.8% · `미확인` 0건) — 원장이 요구한 선행 단계
- [x] 계약 재작성(A) + SYSTEM_PROMPT 미러 정합
- [x] 감지기(C) + 감지기 자체 회귀 테스트 10건
- [x] feature-0002 전체 2399 passed / 31 skipped / 0 failed
- [x] §18.8 codex 적대 **3라운드** — R1 [P1]1+[P2]3 → R2 [P1]2+[P2]3 → R3 [P1]**0**+[P2]1 → 전건 수정(마지막은 **성공 신호가 영원히 0** 이던 감지기 결함)
- [x] **배포 완료**(2026-08-03, PR #1126 merge main `99d09137`, 4서비스 healthy) + 배포본 런타임 실증 **계약 9요소 전부 LIVE** + 라이브 composed(19,764자) 도달. 1차 배포는 insight-worker 헬스 미도달(일시적 datasource `probe-tcp timeout`, 내 코드 무관)로 워커 롤백 → 자체 회복 후 재실행 RC=0
- [ ] **재측정으로 완료 판정**: 배포 직후 스냅샷 47.8% / `미확인` **2개**(0→2, 첫 사용). 90일 창은 과거 대화 지배 → 새 리뷰 대화 축적 후 `--days 30` 재측정에서 비율 감소 + 미확인 증가면 `verified`

## TASK-20260731T030000-grounding-authority-directive — 운영자 프롬프트가 삼킨 grounding 봉인을 코드 권위선으로 복구 + 라이브 모순 제거 (Major §12.3 — core 시스템 프롬프트)
- 출처: `/_dqa:conversation_audit "SQL 쿼리 코드 리뷰"` 후속 — 선행 cycle(TASK-20260730T190000) **배포 검증 중 부수 발견**된 `FR-operator-global-prompt-shadows-code-seals`. 사용자 지시("후속 이슈가 있다면 해당 부분도 적용을 검토해주세요") + 범위 승인 **A+B**(AskUserQuestion 2026-07-31).
- **근본원인(구조)**: `compose_system_prompt` 은 운영자 `WebSystemPrompts` scope='global' row 가 있으면 **코드 상수 `SYSTEM_PROMPT` 를 통째로 대체**한다. 라이브 row = 9,219자(15,978 bytes) / UpdatedAt **2026-06-18**, 코드 상수 = 21,594자 → 그 날짜 이후 **본문에만** 추가된 grounding 규칙이 프로덕션에 존재하지 않았다. 코드-append guidance 상수(16,825자)에도 없어 보완 경로가 없었다.
- **부재 확정 5종(배포본 실측)**: 첨부↔실DB 양측 조회(FR-partial-evidence) · 0행≠부재(FR-false-absence) · 절단 통지/완전성 신호(FR-false-truncation) · 식별자 대소문자(FR-schema-name-case-drift) · `check_table_coverage` 유도.
- **더 나쁜 것(활성 모순)**: 라이브 row 의 `## 첨부 파일` 절에 REQ-20260714-attach-review-grounding 이 **환각 유발로 판정해 코드에서 제거한 두 지시**가 한국어로 살아 있었다 — "명시 요청 없이 execute_sql 을 돌리지 마십시오" + "첨부 지침이 일반 조회 지침보다 우선합니다". 당시 §18.8 패널이 MAJOR 로 못박은 실패 모드("정적본을 남기면 takes precedence 가 verify 를 이긴다")가 그대로 라이브 상태였고, **이것이 선행 cycle 이 진단한 A/B 대조쌍(도구 0회 ↔ 12회)의 실제 기전**이다(정적 억제 vs 동적 검증이 한 프롬프트 안에서 정면 충돌).
- **왜 운영자 row 를 코드 상수로 덮어쓰지 않는가**: 그 row 는 stale 사본이 아니라 **한국어 재작성 + 코드에 없는 운영자 고유 정책**(보안 경계·민감 데이터 마스킹·재식별 방지·데이터소스 선택)을 담고 있다 — 덮어쓰면 PII 정책이 소실된다. `compose` 를 replace→merge 로 바꾸는 안도 배제(영문 원본과 한국어 재작성이 양쪽 다 실려 중복·모순 확대).
- **해결(A+B)**: (A) `_GROUNDING_AUTHORITY_DIRECTIVE` 신설 — 5종 규칙 + **좁은 override**(첨부 검토 맥락 한정) + 보안·프라이버시 carve-out. `compose_system_prompt` **반환 직전**(운영자 product/role/account scope prompt 와 첨부 섹션보다 뒤)에 append 해 last-writer 확정. (B) 라이브 운영자 row 에서 **문제의 두 줄만** 교정(운영자 고유 정책 전량 보존·백업 후).

### §1.1 Implementation
- `src/agent_core.py`: `_GROUNDING_AUTHORITY_DIRECTIVE` 상수 + `compose_system_prompt` 반환 직전 append 1줄(초기 `parts` 목록 **아님** — §18.8 R2 P2).
- `tests/test_grounding_authority_directive.py` 신규 18건: 상수·5종 seal 본문·좁은 override·carve-out 7종·활성 조건 범위·운영자 row 대체 재현 하네스 자체 검증·last-writer(scope prompt 뒤·프롬프트 말미)·**census 2종**(9 seal 이 code-append 영역에 존재 + composed 도달 + 작동 조항).
- 라이브 데이터(코드 아님): 운영자 global row id=20 교정 2줄. 백업 `artifacts/websystemprompts-global-backup-20260803T032541Z.txt`.

### §1.2 Completion Checklist
- [x] `_GROUNDING_AUTHORITY_DIRECTIVE` 신설 + 반환 직전 append(last-writer)
- [x] 라이브 운영자 row 교정(B) — 백업 후 2줄만, 운영자 고유 정책 보존 실증
- [x] 신규 18건 PASS · feature-0002 전체 2377 passed/31 skipped/0 failed
- [x] §18.8 적대 리뷰 — §18.8.2 제약-없는-채널 우선 → **codex 3라운드**(R1 P1 1건+P2 4건 → R2 P1 폐쇄·P2 3건 → R3 신규 P1/결함 0·P2 1건) **전건 수정** → REV-20260731T030000-grounding-authority-directive
- [x] **배포 완료 + 라이브 census 재측정 통과**(2026-07-31, PR #1114 merge main `954adc87` → `make deploy-web` 전체 스코프, soak 통과, 4서비스 GIT_COMMIT=954adc87 healthy). 배포본 ask-worker 실 `agent_memory` compose 결과 **13,604자 → 17,830자**, **필수 seal 9종 전량 LIVE**(수정 전 부재 5종 전부 도달 전환) · 억제/첨부우선 지시 0 · carve-out·보안우선 문구 LIVE · 운영자 마스킹 정책 보존 · composed 가 계약으로 끝남(last-writer)

## TASK-20260730T190000-review-proposed-change-framing — 쿼리 리뷰가 '곧 적용될 구조'가 아니라 '현재 DB'를 기준으로 불평하던 프레임 봉인 + 루틴 본문 매칭 스니펫 (Major §12.3 — core 시스템 프롬프트·도구 피드백)
- 출처: `/_dqa:conversation_audit "SQL 쿼리 코드 리뷰"` (2026-07-30, 사용자 명시 호출). 마찰 2건 제기 — ① 리뷰가 항상 현재 DB 기준으로 "불평하듯" 주의사항을 전달 ② 특정 내용을 포함하는 함수/프로시저 탐색(scan) 도구 부재.
- **마찰 ② 는 정직 기각(F3)**: `search_routines`(FR-false-absence-zero-row-catalog-scope, 2026-07-28 배포 PR #991)가 이미 **이름 + 정의 본문 + 주석**을 검색한다. 제기된 그 대화(`…a2efa955`)에서 실제로 동작했다 — msg 6317 이 keyword `Log_AccountUpdateCash` 로 **이름에 그 문자열이 없는 호출자 4개**(`Game_BuyCashItem_Steam`·`Game_ConvertCash`·`Game_GiftCashItem_Steam`·`Steam_AccountChargeCash`)를 찾아냈다(본문 검색이 아니면 불가). 30일 사용량 23회 / 7 대화. → 도구 신설 대신 **체감 갭(매칭 위치 미표시)** 만 개선(사용자 결정, AskUserQuestion 2026-07-30).
- **근본원인(L1 프롬프트 합성, 마찰 ①)**: SYSTEM_PROMPT §ATTACHED FILES(agent_core.py:119-124)와 첨부 주입 INSTRUCTION(agent_core.py:~1272)이 "첨부 vs 실 DB 주장은 반드시 라이브 검증" 만 정하고 **그 차이의 해석(시간 방향)** 은 정하지 않는다. 여기에 누적된 부재·완전성 grounding(FR-partial-evidence·FR-false-absence·FR-false-truncation)이 "존재 여부" 를 극도로 부각시켜, 모델의 기본 프레임이 **라이브 DB=정본 스펙 / 첨부=그에 미달하는 후보** 로 굳었다. 변경이 스스로 만들어내는 차이(아직 없는 테이블·컬럼·루틴, 스크립트가 추가할 PK, 바뀐 시그니처)가 전부 결함·경고로 보고된다.
- **라이브 증거(A/B 대조쌍)**: 동일 5개 파일(sha256 일치)·동일 요청문("첨부파일의 쿼리 리뷰를 진행해주세요.")이 3분 간격 두 대화로 갈렸다 — `…4348bc34`(16:43, 도구 0회)는 논리·성능·보안·운영 축의 코드 리뷰, `…a2efa955`(16:46, 도구 12회)는 "배포 순서 의존성(가장 중요)" + "테이블은 **아직 존재하지 않습니다**" + "ServerID 컬럼도 PK도 **전혀 없습니다**". 즉 프레임이 계약 부재로 **모델 재량**에 맡겨져 있었다. 다른 대화 `…b5f40d99` 는 미적용 마이그레이션을 두고 "동적 ALTER 로직이 **실제로 실행되지 않았거나 실패한 상태**입니다" 라는 허위 결함 단정(`I-FALSE`)까지 냈다.
- **corroboration(structural)**: 60일 SQL 첨부 대화 96건 중 **12 distinct_conv** 의 장문 답변이 현재-DB 부재 프레이밍을 담는다(≈12.5%). `…b5f40d99` 는 답변 4건이 "예상 구조 vs 실제 구조" 표로 미배포 상태를 🔴 결함·"데이터 무결성 위험"으로 채점.
- **해결(A+B+C, 사용자 승인)**: (A) 시간 방향 계약을 **코드 권위선**으로 항상 주입 — 라이브 DB=BEFORE / 첨부 세트=AFTER, 변경이 도입하는 차이는 '적용 전제'이지 결함 아님. (B) 출력 구조 계약 — 전제는 별도 1개 절, 심각도 배지(🔴/🟡)는 **적용 후에도 남는** 결함에만. (C) 도구 L2 짝 — 미발견 오류/빈 결과에 분류 교정 힌트(적용 전제 ↔ 진짜 선행 누락 ↔ 권한·스코프·오타 **3분기**). 라이브 대조 강제는 **약화하지 않는다**(선행 봉인 보존, 회귀 테스트로 고정).

### §1.1 Implementation
- `src/agent_core.py`: `_ATTACHMENT_REVIEW_TEMPORAL_DIRECTIVE` 상수 신설 + `compose_system_prompt` `parts` 에 always-append(base=운영자 global row 대체 뒤 — AUTH-1a 코드 권위선); SYSTEM_PROMPT §ATTACHED FILES 미러 1줄; `_build_attachment_context_section` INSTRUCTION 에 시간 방향 포인터.
- `src/modules/tools.py`: `_MISSING_OBJECT_ERROR_PAT`/`_PROPOSED_CHANGE_HINT`/`_proposed_change_hint()` 신설 → `_tool_execute_sql` 오류 경로 · `_tool_describe_table` 컬럼 0행 · `_tool_describe_routine` 정의 0행 3지점 부착; `_routine_snippet_cell()` + `_NO_BODY_MATCH_CELL`/`_NO_BODY_MATCH_NOTE` 로 search_routines 표에 '본문 매칭 위치' 컬럼(MySQL·MSSQL 양 경로) + 도구 설명 갱신.
- `src/modules/dialects.py`: MySQL `search_routines` 에 `MATCH_SNIPPET`(LOCATE/SUBSTRING/GREATEST) · MSSQL 에 `MATCH_SNIPPET`(CHARINDEX/SUBSTRING) 4번째 컬럼; keyword 미지정(전체 열거)은 상수 `''`; base 컬럼 계약 docstring 갱신(caller 는 `len(row) > 3` 방어적 판독 — 3컬럼 하위호환).
- `tests/test_review_proposed_change_framing.py`: 신규 27건(계약 본문·코드 권위선 실증·회귀 방지·힌트 3분기·잡음 0·스니펫 정규화/하위호환/양 dialect).

### §1.2 Completion Checklist
- [x] L1 시간 방향 계약(A) + 출력 구조 계약(B) + L2 도구 힌트(C) 구현
- [x] search_routines 매칭 스니펫(MySQL+MSSQL) — 사용자 승인 항목
- [x] 신규 테스트 27 PASS · feature-0002 로컬 2114 passed/30 skipped · `make test`(3 feature + ruff) **RC=0 4회 연속**
- [x] §18.8 적대 리뷰 — §18.8.2 제약-없는-채널 우선 → codex 3렌즈(security/backend/regression) **[P1] 0건**, [P2] 4건 중 2건 흡수·2건 근거 기록 → REV-20260730T190000-review-proposed-change-framing
- [x] 배포 완료(2026-07-31, PR #1102 merge main `2ecfe4b5` → `make deploy-web` 전체 스코프, soak 통과, **4서비스 GIT_COMMIT=2ecfe4b5 healthy**, edge `/healthz` ok) + 배포본 런타임 실증(계약·L2 힌트·스니펫 심볼 13종) + **라이브 compose 경로 실증**(실 `agent_memory` 연결 `compose_system_prompt` 결과 13,604자에 계약 도달 — 운영자 global row 대체 조건에서도 존속 = AUTH-1a 검증)
- [x] **라이브 대화 실측 완료(2026-08-03, PB-0008 Windows-browser)** — 실제 Windows Chrome 으로 새 대화·제품 119·**원본 5파일 재업로드(sha256 5/5 일치)**·동일 요청문·`#sendBtn` 실제 클릭. 재현 대화 `20260803081201-969946a2`. **프레이밍 축 PASS**: 도입부 "실제 DB 현황(BEFORE)과 비교" 명시 · `📊 적용 전제` 단일 절 분리 · 미배포 상태에 🔴 배지 **부재**(전부 ✅) · 배지는 적용 후 결함에만 · 배포 순서는 말미 Q&A 강등. `search_routines` 본문 매칭 스니펫 라이브 정상. 증적 `docs/test-runs.d/20260803T1720-review-framing-live-pb0008.md` + PNG 2장
- [ ] **잔여(별 항목)**: 같은 답변에 미검증 부재 단정 1건(`ConcurrentUsers5Rocks_gunz … 현재 미존재` — ground truth 는 약 148만 행 실존, 조회 도구 호출 0건) → 원장 `FR-review-precondition-assumed-not-verified`(triaged). corroboration 선측정 후 수정 방향 결정 필요
- **부수 발견(별 트랙, 원장 `FR-operator-global-prompt-shadows-code-seals`)**: 배포 검증 중 운영자 `WebSystemPrompts` global row(15,978자·2026-06-18)가 코드 상수 `SYSTEM_PROMPT`(20,575자)를 통째 대체해 **2026-06-18 이후 SYSTEM_PROMPT 본문에만 추가된 규칙 7종이 라이브 미도달**임을 실측. 본 cycle 은 계약을 `parts` always-append 로 넣어 영향 없음(설계 검증). `needs-human` — 사람 결정 필요.

## TASK-20260722-dqa-data-grounding — 데이터 의미 grounding 지침: 저장값 타임존·ENUM 코드·분리저장 추측 금지 (Major §12.3 — core 시스템 프롬프트·정확성; DQA 마찰 B-1/D-1/D-2)
- 출처: `/_template:entry` DQA_assistant_마찰개선사항_20260722_v2.md 검토·개선 (2026-07-22, 사용자 명시). FGT 통계 집계를 DQA 로 수행하며 관측된 **정확성 결함**을 서비스 grounding 지침으로 해소.
- **근본원인(관측)**: LLM 이 데이터의 "표기"와 "의미"를 혼동해 조용히 틀린 집계를 냄.
  - **B-1(★최우선)**: DB 서버 TZ 설정(`@@time_zone`=Asia/Tokyo)만 보고 "저장값은 JST → -9h=UTC" 라고 확신 오판. 실제 저장 DATETIME 값은 UTC(MySQL DATETIME 은 TZ 미저장) → 집계 기간 전체가 9시간 어긋나 전 시트 오염 위험(본건은 사용자 경고·데이터 교차검증으로 겨우 정정).
  - **D-1**: CurrencyType 코드를 기억으로 "3=Stamina" 환각(정본 4=스태미너). KB 용어사전/ENUM 사전(GLOSSARY & ENUM VALUES 주입)·샘플링으로 grounding 해야 함.
  - **D-2**: 재화가 Gold/GemV2/Currency 로 테이블 분리 저장 → "전체 재화" 를 한 테이블만 집계하면 조용한 누락.
- **해결(항상 주입 grounding 블록)**: 능동 해석(식별자/스키마 발견)과 별개 축(값의 "의미") 으로 분리한 `_DATA_GROUNDING_GUIDANCE` 신설. (a) 서버 TZ 설정 ≠ 저장값 의미 명시 + 불확실 시 알려진 기준점 데이터 교차검증·가정 명시, (b) 코드/ENUM 의미 추측 금지 + GLOSSARY & ENUM VALUES·샘플링 grounding·미보유 고백, (c) 분리·중복 저장 시 커버리지 명시. 게임-무관 일반 지침이라 모든 datasource 에 적용.

### §1.1 Implementation
- `src/agent_core.py`: `_DATA_GROUNDING_GUIDANCE` 상수 신설 + `_run_agent_core` compose 에서 `_ACTIVE_INTERPRETATION_GUIDANCE` 직후 무조건(그룹 if-블록 밖) 주입 — 1:1·그룹 공통, base/product 프롬프트 뒤 last-writer 로 권위화.
- `src/modules/guidance_registry.py`: `data-grounding` 지침 항목 등록(관리 콘솔 작동지침 목록 노출).
- `tests/test_gc_dialect_context.py`: 지침 본문(타임존·DATETIME·GLOSSARY·분리)·무조건 주입 위치(그룹 if 밖)·레지스트리 등록 3건.

### §1.2 Completion Checklist
- [x] `_DATA_GROUNDING_GUIDANCE` 신설 + 무조건 주입(_ACTIVE_INTERPRETATION 직후) + guidance_registry 등록
- [x] test_gc_dialect_context.py 3건 + test_scratch.py 3건 + py_compile 통과 · 로컬 변경-특화 38 PASS · 인접스위트 회귀 0
- [x] §18.8 적대 리뷰(backend/correctness + security 2 렌즈) SHIP-WITH-FIXES → backend PLAUSIBLE(save_csv 실패 시 거짓 CSV 링크) 흡수 + TIMESTAMP/DATETIME 정밀도 nit 반영 → REV-20260722T034138-dqa-data-grounding-and-scratch-csv
- [x] make test(컨테이너) — 잔여 실패는 기존 비결정 flake(postgres-replica --no-deps + 순서-의존 runtime_settings/attachment; clean main 기준선도 다른 15건 실패) · 변경-특화 테스트 양쪽 부재 = 회귀 0
- [ ] 배포(web+worker 재빌드, deploy_scope: included) 후 라이브: 시각 필터 질의에서 저장값 TZ 추측 대신 확인·가정 명시 관측 / 대량 scratch→CSV 다운로드

## TASK-20260722-dqa-scratch-csv-export — scratch_sql 결과 CSV export (Minor §12.3 — 비파괴 결과추출; DQA 마찰 F-5; 코드 feature-0002 거주·정본 feature-0022)
- 출처: 위 동일 DQA 마찰 문서 F-5/C-3. scratch 병합 결과가 inline(~200행) 절단 + `/shared/out` CSV 미export → 대량 cross-DS 병합 결과 회수 곤란.
- **해결**: `scratch.run_sql` 을 export 상한(`AGENT_SCRATCH_MAX_RESULT_ROWS`, 기본 100000)까지 전체 fetch 하도록 바꾸고, `_tool_scratch_sql` 이 execute_sql 과 동일하게 `save_csv("scratch_resultset1", …)` 로 CSV 저장 + "CSV 저장: <path>" emit. 웹 UI 는 기존 `CSV_PATH_RE` 로 그 경로를 파싱해 다운로드 링크 생성(추가 프론트 변경 불필요). 미리보기는 execute_sql 표 포매터(50/adaptive)로 절단 + 미열람 행 단정 금지 안내.
- 상세 정본: `unit/feature-0022-agent-scratch-workspace/docs/TASK.md`.

## TASK-20260716-redteam-axis-rederive (current cycle) — 자가검증 BLOCK 축 인지 재도출: 텍스트 다듬기만 하던 revise 를 sql/max-completeness 는 도구 재추론으로 승격 (Major §12.3 — core 답변 파이프라인·LLM 비용/지연)
- 출처: `/_template:entry "서비스 내 assistant가 요청을 수행할 때, 자가 검증을 통한 BLOCK 이 확인되었지만 별도의 재추론을 진행하지 않고, 이미 구성된 답변을 바탕으로 다듬는 행위만 진행 후 제출하는듯한 현황"` (2026-07-16, 사용자 명시). 구성 승인 = **세 요소 모두 취하되 completeness 재도출은 '매우 높음(max)'에서만** (AskUserQuestion 3-round, 2026-07-16).
- **근본원인(코드 확정)**: red-team 자가검증(feature-0021)이 `BLOCK`(verdict="revise")을 확정하면 `orchestrate_review`가 caller 의 `revise_fn`을 호출 → 그 실체 `agent_core._rt_revise`는 `_call_llm(..., tools 인자 없음)` **단발 completion**. 즉 (a) 도구 접근 없음 + (b) `build_revision_instruction`이 "증거 밖 신규 사실 추가 금지" 명시 + (c) evidence digest 1회 고정 재사용 → 구조적으로 **재추론 불가, 텍스트 다듬기만**. grounding/permission/honesty BLOCK은 다듬기가 정답이나, `sql`(틀린 쿼리)·일부 `completeness`(빠뜨린 조회)는 새 근거 없이는 못 고쳐 헤징 강등/미해소/근거없는 정정으로 귀결.
- **해결(축 인지 라우팅)**: BLOCK 축에 따라 수정 경로 분기. `sql`(항상)·`completeness`(ordinal≥REDTEAM_REDERIVE_COMPLETENESS_MIN_LEVEL, 기본 3=매우높음)는 **도구 허용 재추론**(`rederive_fn`=`_rt_rederive`)으로 승격 — execute_sql 등을 상한 내 재호출해 근거 재수집 후 재도출, 새 근거로 evidence 재계산해 verify 최신 검증. 나머지 축·재추론 무산출은 기존 텍스트 재작성으로 폴백. 전 경로 fail-open 불변.

### §1.1 Implementation
- `src/modules/redteam.py`: `_REDERIVE_ALWAYS_AXES=("sql",)`·`_REDERIVE_LEVEL_GATED_AXES=("completeness",)`; `_rederive_enabled`/`_rederive_eligible_axes(ordinal)`/`_block_rederive_axes`; `build_rederive_instruction`(도구 재호출 허용·인젝션 sentinel 유지); `orchestrate_review`에 `rederive_fn` 파라미터 + 축 라우팅 루프 + evidence 재계산; `record_review` + meta 에 `rederive_applied/tool_rounds/axis`.
- `src/agent_core.py`: `_rt_rederive` — `_run_tool_defs`+`execute_tool` 재사용 상한 도구 루프(REDTEAM_REDERIVE_MAX_TOOL_ROUNDS, 마지막 라운드 tools=None 확정, 라운드당 도구 3개, `_datamark_untrusted`+4000자 truncation 미러, build_evidence_digest 호환 step 생성), fail-open; `orchestrate_review` 호출에 `rederive_fn=_rt_rederive` 배선.
- `shared/runtime_settings.py`: `REDTEAM_REDERIVE_ENABLED`(기본1)·`REDTEAM_REDERIVE_MAX_TOOL_ROUNDS`(기본3)·`REDTEAM_REDERIVE_COMPLETENESS_MIN_LEVEL`(기본3=max) live 설정.
- `alembic/versions/20260716_0043_redteam_rederive_columns.py` + `MAX_MIGRATION.txt` + `src/scripts/agent_runtime_schema.sql` 미러: redteam_reviews 에 `rederive_applied/tool_rounds/axis` 컬럼(additive expand-safe, GRANT 불필요=ADD COLUMN 상속).
- `tests/test_redteam.py`: 축별 라우팅·completeness max 게이팅·evidence 재계산·rederive disabled/무산출 폴백·인젝션 sentinel 9건 추가.

### §1.2 Completion Checklist
- [x] redteam.py 축 인지 라우팅 + evidence 재계산 + record_review/meta 확장
- [x] agent_core.py `_rt_rederive` 상한 도구 루프(보안 datamark/truncation/cap 미러) + 배선
- [x] runtime_settings 3개 live 설정 (completeness=max 게이트)
- [x] migration 0043 + schema.sql 미러 + MAX_MIGRATION 범프 (additive expand-safe)
- [x] test_redteam.py 확장 — 로컬 30 PASS, 전체 스위트(0002+0003) **2145 passed, 2 skipped, RC=0 회귀 0**(기존 agent 이미지+worktree 마운트, `.env`-less worktree 는 make test dc-build "invalid proto" → 이미지 재사용 정본 경로)
- [x] py_compile(redteam/agent_core/runtime_settings) 통과
- [x] §18.8 적대 리뷰(backend+security) SHIP-WITH-FIXES → B1(sentinel breakout)·W1(재도출 SQL 추적성)·W2(취소 존중) 흡수, W3 수용 → REV-20260716T075345-redteam-axis-rederive
- [ ] 배포(web+worker 재빌드) 후 라이브 실증: 높음/매우높음 대화에서 sql BLOCK 시 redteam_reviews.rederive_applied=true·tool_rounds>0 관측

## TASK-20260716-graph-search-content-match (current cycle) — 그래프 뷰 검색 매칭 확장: 컨텐츠 카테고리 + AI 능동 분석 본문 (Minor §12.3 — 비파괴·읽기전용 검색 쿼리 확장·내부 API)
- 출처: `/_template:entry "그래프 뷰 내부에서 검색을 진행할 때, '테이블, 컬럼, 용어' 뿐만 아니라, 컨텐츠 카테고리 및 AI 능동 분석을 통해 얻은 내용 또한 매칭될 수 있도록 구성해주세요."` (2026-07-16, 사용자 명시).
- **교차 feature**: 그래프 뷰 기능 정본 = feature-0016-metadata-graph. 코드 거주 = feature-0002-agent-core `modules/metadata_graph.py`(검색은 서버사이드 `search_nodes` 가 정본, 프론트 `_metaGraphSearch` 는 반환 노드 렌더·글로우만 담당). 본 cycle 은 코드 거주 feature(0002)에 기록, 추적은 feature-0016 TASK/REPORT 에 cross-ref.
- **배경**: 관리 콘솔 그래프 뷰 검색은 `/api/admin/metadata/graph?q=` → `search_nodes()` Cypher `MATCH (n) WHERE toLower(n.name) CONTAINS q OR toLower(n.fqn) CONTAINS q` 로 **이름/FQN 만** 매칭(테이블·컬럼·용어·스키마·함수/프로시저 이름이 잡히던 이유 = 모든 label 의 name/fqn CONTAINS). 컨텐츠 카테고리(§78~81 컨텐츠 단위 그룹 = `semantic_cluster_label`)·AI 능동 분석 본문(`node_analysis_jobs.analysis`)은 매칭 대상이 아니었다.
- **프론트 무수정 근거**: 프론트는 백엔드 반환 노드를 label 별로 분류·카드 badge·앰버 글로우만 얹는다(임의 매칭 노드 처리 가능). 활성 병렬 세션(`feature-0003-graph-cluster-detail-collapse`)이 `graph-ctxmenu.js` 편집 중이라 백엔드 단독 변경으로 스코프 충돌 회피.

### §1.1 Implementation Plan
- `src/modules/metadata_graph.py`:
  - `search_nodes` Cypher WHERE 에 `toLower(n.semantic_cluster_label) CONTAINS {ql}` 추가(컨텐츠 카테고리, AGE 노드 프로퍼티 — `toLower(null)`=null 은 OR 무시로 비클러스터 노드 안전). RETURN 9컬럼(+`semantic_cluster_label`), `_node_dict` row[8]→`cluster_label`(존재 시).
  - 신규 `_analysis_match_keys(cur, query, scope, limit)`: 같은 agent_kb 커넥션으로 `node_analysis_jobs`(AGE 정점 아닌 관계형 테이블) `status='done' AND position(%s in lower(analysis::text))>0` 부분일치 → 매칭 `node_key` 집합. bind param(injection-safe)·scope 조건부·1자 질의 스킵·권한/부재/실패 graceful []. 결과를 Cypher `n.key IN [...]`(`_cq` 인용) 로 합류.
  - 각 노드 `match_via`(name|category|analysis 다중) 부여(프론트 무해·관측/검증용). pg_trgm score 계산에 `similarity(cluster_label,q)` 추가(카테고리 매칭 랭킹 보정).
- `tests/test_graph_search_content.py`(신규): SQL/Cypher 합성·match_via·scope 격리·graceful·회귀 7건.

### §1.2 Completion Checklist
- [x] `search_nodes` Cypher WHERE: `semantic_cluster_label` CONTAINS 추가 + 분석 key `n.key IN [...]` 합류 + RETURN 9컬럼
- [x] `_analysis_match_keys` 헬퍼: node_analysis_jobs status='done' position() 부분일치·scope 조건부·bind param·1자 스킵·graceful
- [x] `_node_dict` row[8]=cluster_label + `match_via` 근거 + score 에 cluster_label similarity 반영
- [x] `tests/test_graph_search_content.py` 7 PASS + 기존 metadata_graph/semantic_cluster/funcproc/routine 테스트 회귀 0(로컬 PYTHONPATH)
- [x] §18.8 적대 리뷰(backend+security — query/schema 키워드, 인젝션·NULL 3치·scope 격리·RO 권한 렌즈)
- [ ] 배포(web 재빌드) 후 라이브 `/api/admin/metadata/graph?q=<카테고리/분석어>` 매칭 실증 + feature-0016 cross-ref 기록

## TASK-20260715-llm-probe-thinking-budget (current cycle) — LLM 헬스 probe 오탐: stale "요청량 한도/사용량 소진" 배너 고착 해소 (Major §12.3 — LLM 라우팅·외부 비용)
- 출처: `/_template:entry "assistant 내부 인사이트·답변 시 claude-corp 계정 사용량 소진 메시지 — 실제 허용량 남아있음, 원인 파악·수정"` (2026-07-15, 사용자 명시). 수정방식 승인 = **유효 probe(Option A)** (AskUserQuestion 2026-07-15).
- **근본원인(재현 확정)**: active health probe `probe_provider`(web `/api/llm/health` 60s 폴링)가 `OPENAI_MODEL`(=`claude-haiku-4-interactive`)로 `max_tokens=1` ping → 이 alias 는 litellm config `thinking.budget_tokens:5000` 강제 → Anthropic `max_tokens>budget_tokens` 위반 → 항상 400 → `classify_llm_provider_error`=None → probe 가 OK/restricted 어느 것도 기록 못 함. 배너 clear 자동경로(probe) 무력화 → 순간 429 로 찍힌 sticky `restricted` 가 계정 회복 후에도 성공 답변 전까지 stale 고착.
- **봉인**: probe 를 valid ping 으로 — thinking 강제 alias(claude-*)면 최소 budget(1024) override + max_tokens>budget → 성공 시 `record_provider_ok` 가 배너 정상 해소. 비-thinking(로컬 gemma)은 max_tokens=1 유지.

### §1.2 Completion Checklist
- [x] `src/modules/llm_provider_health.py`: `_PROBE_THINKING_BUDGET`=1024 상수 + `probe_provider` valid-ping 분기(thinking override+max_tokens>budget / 비-thinking max_tokens=1)
- [x] `probe_provider` recovery-only gate: 비-force 는 restricted 일 때만 실제 ping, ok/unknown cached 반환(5h 윈도우 재고정 방지 — 적대 리뷰 CONCERN 흡수)
- [x] `tests/test_llm_provider_health.py`: valid-ping 2건 + recovery-only gate 4건 — 파일 **37 passed**(RC=0)
- [x] classify 실제 실행으로 400→None 재현 + `_call_llm` thinking override 메커니즘(test_reasoning_effort) 정합 확인
- [x] `docs/FUNCTION.md` probe 서술 갱신 · `docs/MODIFY.md` CHG-20260715-llm-probe-thinking-budget
- [x] §18.8 적대 리뷰(backend) SHIP-WITH-FIXES→CONCERN 흡수 — REV-20260715T120000-llm-probe-thinking-budget
- [ ] 배포(web 재빌드) 후 라이브 `/api/llm/health` probe 성공(OK 기록) + stale 배너 해소 실증
 — MSSQL 구조화 발견 도구 DB(catalog) 인지: cross-DB 검색·describe (Critical §12.3, conversation_audit FR-mssql-crossdb-structured-discovery)
- 출처: `/_dqa:conversation_audit "코드 재검토 요청 — assistant 가 SQL Server 내부 관련 객체를 못 찾음(실제로는 있는데도)"` (2026-07-14, 사용자 명시). 승인=**완전 DB인지**(AskUserQuestion 2026-07-14).
- **근본원인(삼각측량 high — 코드+PG 대화집계+라이브 QA 서버+전사)**: SQL Server `INFORMATION_SCHEMA`/`sys` 는 **DB(catalog)별**(MySQL 인스턴스-전역 information_schema 와 비대칭)인데, 구조화 발견 도구가 pin 된 primary DB(`allow_dbs[0]`) 하나만 조회 → 제품 데이터가 분산된 다른 허용 DB(product 117 `Shop`·`CASHITEMDB` 등 30여 개)의 객체를 "없음"으로 오판·give-up. `schema_name` 이 DB 를 스키마로 오인(관측: describe_table 빈-헤더 schema 인자 대부분 DB명). **corroboration structural**: MSSQL 29대화 중 11(~38%) describe_table 빈-헤더·9 search_tables 빈결과, 오늘까지. 대상 대화 `20260714065456-d705e0c7`(product 117, `Shop.dbo.T_ItemInfo`/`L_Item_Buy_Log` 미발견→포기→"다시, 제대로 검토해주세요"). 라이브 재현/수정검증(mssql-web-qa): primary `_INDY_STATISTIC` 에서 미발견 → `[Shop].INFORMATION_SCHEMA` 3-part 로 15컬럼·`L_Item_Buy_Log` 발견.
- **재발경로/봉인**: capability gap(도구가 freeform 이 이미 도달하는 허용 DB 에 못 닿음) → 구조화 발견 도구를 **DB(catalog) 인지**로. `[db].` 3-part 카탈로그 조회 + `search_tables` 대상 DB 미지정 시 허용 DB 전체 검색(DB-qualified) + 빈결과 L2 교정 힌트. 보안 경계 불변(유효 허용 DB만·시스템/내부 DB·시스템 스키마 차단·`_safe_ident`+allowlist 이중).

### §1.1 Implementation Plan
- `src/modules/dialects.py`: MSSQLDialect 전 발견 메서드에 `db` 파라미터 + `_cat(db)` 3-part 접두(sys/INFORMATION_SCHEMA); describe_columns 스키마 필터 조건부; routine OBJECT_ID 3-part. base/MySQL 은 `db=""` 무시(골든 회귀 0).
- `src/modules/tools.py`: `_mssql_active`/`_mssql_effective_allow_dbs`/`_mssql_resolve_catalog`/`_mssql_resolve_table_schema`/`_mssql_struct_target`/`_mssql_crossdb_hint` + 8개 구조화 핸들러 catalog-aware + `search_tables` cross-DB(per-DB graceful·CAP 40) + TOOL_DEFINITIONS `database` 파라미터.
- `src/agent_core.py`: `_MSSQL_DIALECT_GUIDANCE` 다중 DB 발견 지침(L1 정합).
- `tests/test_mssql_crossdb_discovery.py`(신규).

### §1.2 Completion Checklist
- [x] dialects.py: MSSQLDialect `db` catalog 접두(11 메서드) + describe_columns 조건부 스키마 필터 + base/MySQL `db=""` 무시(골든)
- [x] tools.py: catalog resolver/헬퍼 5종 + 8 핸들러 catalog-aware + search_tables cross-DB + `database` 툴 파라미터 + L2 교정 힌트
- [x] agent_core.py: `_MSSQL_DIALECT_GUIDANCE` 다중 DB 발견 지침
- [x] tests/test_mssql_crossdb_discovery.py(33) + 전체 회귀 **1967 passed/2 skipped/0 failed(RC=0)**
- [x] 라이브 QA(mssql-web-qa) 수정 검증: describe_columns([Shop],T_ItemInfo)=15컬럼·search_tables('Buy',Shop)=L_Item_Buy_Log 발견
- [x] §18.8 적대 패널(security+backend+qa) — REV-20260714T161500(MAJOR3 전건 수정·재검증). **배포 완료**(PR #790 merge b364e964 → deploy-web 4서비스 재빌드·soak 통과·baked end-state 실증, CHG-20260714T171000-mssql-crossdb-deploy). 라이브 대화 corroboration 재측정 → FRICTION_LEDGER `verified`(다음 audit)

## TASK-20260713T171821-readonly-query-shapes (current cycle) — read-only 쿼리 shape 과차단 보정: 최상위 UNION + 읽기전용 SHOW (Critical §12.3, conversation_audit FR-readonly-query-shapes-overblock)
- 출처: `/_dqa:conversation_audit "동적 쿼리 및 테이블 변경사항 추가 리뷰"` (2026-07-13, 사용자 명시 — "여전히 유사한 이슈… '보안 정책상 차단된 SQL' 이 발생하지 않고 정상 조회"). 사용자 승인 방식=**UNION + 읽기전용 SHOW**(AskUserQuestion 2026-07-13).
- **근본원인(삼각측량 high, 코드+DB(PG agent_runtime)+전사)**: **L5 — sql_guard `validate_sql_for_sandbox` 의 SELECT/CTE-only shape 게이트가 read-only 패턴을 과차단**. 대상 대화(`20260713074503-5cef7aa2`) 차단 2건 = `SHOW CREATE TABLE gunzgame.attendence`("CharacterID 추가 여부"=테이블 변경 리뷰) + `SHOW VARIABLES LIKE 'lower_case_table_names'`(config). **corroboration structural**: 최근 30일 "보안 정책상 차단된 SQL" = 9 distinct conv·14건 — `UNION`(8, 최대)·`Show`(5)·parse-fail(12)·multi-statement(4)·MSSQL db_id/db_name(3).
- **재발경로/봉인**: read-only shape 과차단(guard 가정 오류) → **shape allowlist 를 read-only 패턴으로 정확히 확장**(쓰기·allowlist·금지함수·multi-statement 불변). 이전 describe_routine 은 프로시저 subset만 봉인 → 이번은 UNION + 테이블/뷰/config SHOW 로 확장.

### §2.1 Implementation Plan
- `unit/feature-0002-agent-core/src/modules/sql_guard.py`:
  - `_READONLY_SHOW_KINDS`(화이트리스트: CREATE TABLE/VIEW·COLUMNS·INDEX·TABLE STATUS·VARIABLES/STATUS — **PROCEDURE/FUNCTION 제외**=describe_routine 담당) + `_show_kind`/`_show_target_db`/`_validate_readonly_show` 헬퍼.
  - `validate_sql_for_sandbox` shape 게이트: (a) `exp.Show`→`_validate_readonly_show`(종류 화이트리스트 + 대상 `.db` forbidden 차단) (b) `exp.SetOperation`(UNION/INTERSECT/EXCEPT) 허용 (c) lock/into 검사를 **모든 SELECT 분기**(`root.find_all(Select)`)에 적용. 기존 4-part/forbidden-schema/forbidden-function 검사는 이미 find_all 로 union 분기 전수 순회(불변).
  - `collect_schema_refs`: SHOW `.db` 를 schemas 에 수집 → tools `_freeform_sql_access_error` 가 SHOW 대상에도 제품 allowlist 강제.
- `unit/feature-0002-agent-core/src/modules/tools.py`: `_dialect_correction_hint` 의 stale "최상위 UNION 불가" 힌트 제거(UNION 이제 허용 — 오정보 방지).
- **검증**: `tests/test_readonly_query_shapes.py`(신규) — UNION 허용·분기별 보안 불변식·read-only SHOW 허용·forbidden/비-readonly SHOW 차단·collect_schema_refs SHOW .db·데이터수정CTE 거부·기존 불변식 회귀. 전체 회귀 pytest.
- **위험등급 Critical**(sql_guard 허용범위). ANCHOR §1~§3(core/web-ui 분리·모듈 배치) 무충돌.

### §2.2 Completion Checklist
- [x] sql_guard: set-op(UNION/INTERSECT/EXCEPT) shape 허용 + read-only SHOW 화이트리스트 + `_validate_readonly_show`/`_show_kind`/`_show_target_db` + collect_schema_refs SHOW `.db`
- [x] sql_guard: lock/into 를 모든 SELECT 분기에 적용 + **write-node defense-in-depth**(`_find_write_node` — 데이터수정CTE/중첩 write 거부, §18.8 security 패널 MAJOR 흡수)
- [x] tools.py: stale "최상위 UNION 불가" 힌트 제거
- [x] tests/test_readonly_query_shapes.py 신규 + test_gc_dialect_context UNION 단언 갱신 + 전체 회귀 pytest **1899 PASS(RC=0)**
- [x] §18.8 적대 패널(security+backend+qa; 세션한도 조기종료→인라인 자기검증) — MAJOR1(데이터수정CTE) 수정, 나머지 REFUTED. REV-20260713T171821
- [x] cycle-finalize(PR #761 merge main 9892fc3b) + 배포(ask-worker/insight-worker 재빌드·재생성 + web-a/b deploy-web, 4서비스 GIT_COMMIT=9892fc3b, 런타임 가드 동작 실증 PASS)
- [x] FRICTION_LEDGER FR-readonly-query-shapes-overblock 생성(fixed:deployed:unverified-live)
- [ ] 라이브 대화 실측(동적쿼리·테이블변경 리뷰 정상 조회) — 다음 audit corroboration 재측정 시 verified

## TASK-20260713T140405-describe-routine-tool — 저장 프로시저/함수 정의 조회 도구 신설 (Major §12.3, conversation_audit FR-show-create-routine-blocked)
- 출처: `/_dqa:conversation_audit` (2026-07-13, 사용자 명시 호출). 대화 "재사용 쿼리의 PK 관리 문제 추가 리뷰" 에서 assistant 가 저장 프로시저 로직을 검토하려 `SHOW CREATE PROCEDURE gunzgame.Game_AccountAttendence` 를 `execute_sql` 로 실행했으나 보안 가드에 차단됨(사용자 보고). 사용자 승인 방식=**Option 1**(전용 도구 + 유도, AskUserQuestion 2026-07-13).
- **근본원인(삼각측량, rootcause_confidence high)**:
  - L5(가드): `sql_guard.validate_sql_for_sandbox` 가 `execute_sql` 을 단일 SELECT/CTE 로만 허용(`sql_guard.py:~500` `only SELECT/CTE allowed`) → `SHOW CREATE PROCEDURE`(sqlglot `exp.Show`)는 거부. **이 SELECT-only 불변식은 의도된 핵심 보안 기능(F4) — 유지**.
  - L2(진짜 결함): 거부 메시지가 `list_schemas/describe_table` 만 안내하고 **프로시저/함수 정의를 볼 경로를 전혀 알려주지 않음**(tools.py 거부 hint). LLM 노출 도구는 핵심 4개(execute_sql/describe_table/search_tables/get_sample_rows, `agent_core.py:3634 _run_tool_defs=TOOL_DEFINITIONS`)뿐이라 루틴 본문 조회 수단 부재.
  - 접근 권한 자체는 이미 열림: `information_schema` 는 항상-허용(`_whitelist_violation`)이라 `SELECT … FROM information_schema.ROUTINES` 는 지금도 통과. 막힌 것은 **구문 형태(SHOW CREATE)** 뿐. 실제 정의 열람 가부는 datasource RO 계정 GRANT 가 최종 backstop(권한 없으면 NULL — 정보 누출 아님).
- **재발경로/봉인**: `model limit`(거부 피드백에 교정 힌트 부재, L2) + capability gap → **전용 구조화 도구로 봉인**. sql_guard SELECT/CTE-only 불변식 미변경(보안 회귀 0).

### §2.1 Implementation Plan
- **파일 경로 + symbol:**
  - `unit/feature-0002-agent-core/src/modules/dialects.py`: `Dialect.routine_definition/routine_parameters`(base NotImplementedError) + MySQLDialect/MSSQLDialect 구현. 컬럼 계약(엔진 무관): 정의=ROUTINE_NAME/ROUTINE_TYPE/DATA_TYPE/ROUTINE_COMMENT/ROUTINE_DEFINITION, 파라미터=ORDINAL_POSITION/PARAMETER_NAME/PARAMETER_MODE/DATA_TYPE. MySQL=information_schema.ROUTINES/PARAMETERS, MSSQL=INFORMATION_SCHEMA.ROUTINES + OBJECT_DEFINITION(4000자 절단 회피).
  - `unit/feature-0002-agent-core/src/modules/tools.py`: `_tool_describe_routine`(structured 도구 패턴 — `_safe_ident` 정제 + `_struct_schema_access_error` allowlist 게이트 + `_raw_execute_sql`) · `_TOOL_HANDLERS["describe_routine"]` · **핵심 `TOOL_DEFINITIONS`(LLM 실노출)** 에 도구 정의 추가(4→5) · `_routine_introspection_redirect` L2 힌트 + `_tool_execute_sql` 거부 메시지 말미 append · `import re`.
  - `unit/feature-0002-agent-core/src/agent_core.py`(§18.8 qa 패널 반영): `_derive_step_work`/`_derive_step_reason` describe_routine 케이스(런타임 narration fallback 일관성).
  - `unit/feature-0003-agent-web-ui/src/routers/_conv_store.py`(companion, cross-ref only): `_derive_step_work` 에 describe_routine narration 라벨(graceful fallback 존재).
- **§18.8 적대 패널(security+backend+qa)**: MAJOR 1(`_safe_ident` 역슬래시 미제거 → MySQL 리터럴 breakout, pre-existing 공유 사인 → `\` strip 근본 봉인)·MINOR 2(동명 proc+func 파라미터 교차오염 → ROUTINE_TYPE 필터 / narration fallback → agent_core 케이스) 전건 수정. 나머지 REFUTED(safe/correct). 상세 REV-20260713T140405.
- **검증**: `tests/test_describe_routine_tool.py`(신규) — 보안 불변식 보존(sql_guard 여전히 SHOW CREATE 거부) + L2 힌트 + 도구 등록(핵심 세트) + dialect SQL + 도구 동작(happy/not-found/무권한/필수인자/내부스키마 차단) + 백슬래시 strip + 동명 proc+func 파라미터 격리. 전체 회귀 pytest RC=0.

### §2.2 Completion Checklist
- [x] dialects.py routine_definition/routine_parameters (MySQL+MSSQL, ROUTINE_TYPE 파라미터 격리 컬럼)
- [x] tools.py `_tool_describe_routine` + `_TOOL_HANDLERS` + 핵심 `TOOL_DEFINITIONS`(4→5) + L2 유도 힌트 + `_safe_ident` 역슬래시 strip
- [x] agent_core.py narration fallback(_derive_step_work/_derive_step_reason) + feature-0003 narration 라벨(companion)
- [x] tests/test_describe_routine_tool.py 신규 + 전체 회귀 pytest RC=0(1868 PASS) + 보안 가드 3파일 재통과
- [x] §18.8 적대 패널(security+backend+qa) — MAJOR1·MINOR2 수정, REV-20260713T140405
- [x] cycle-finalize(PR #749 merge main 6841eba2) + 영향 서비스 재빌드 배포(ask-worker/insight-worker/web-a/web-b, 4서비스 GIT_COMMIT=6841eba2, 런타임 실증 PASS)
- [x] FRICTION_LEDGER FR-show-create-routine-blocked → fixed:deployed:unverified-live
- [ ] 라이브 대화 실측(프로시저 정의 요청 재현) — 다음 audit 에서 corroboration 재측정 시 verified
- **위험등급 Major**: 신규 LLM 노출 도구가 루틴 정의(로직)를 표면화 — DB GRANT 가 최종 인가 경계. sql_guard·allowlist·RBAC 불변. ANCHOR §1~§3(core/web-ui 분리·모듈 배치) 무충돌.

## TASK-20260710-mssql-auth-cooldown — MSSQL insight 순회 인증실패 조기 skip + cooldown (Minor §12.3, feature-0002 주관, codex 디스크 I/O 장애조사 트랙 B)
- 출처: `/_template:entry`(2026-07-10). codex 가 감지한 WSL 디스크 I/O 장애(F: VHDX 쓰기 18~37MB/s 지속, insight-worker 중단 시 0.13~0.38MB/s 로 정상화) 조사. **근본 원인**: MSSQL datasource `mssql-qa-idc`(scope=`mssql-06656002eda6` = engine+host+port 해시, DB별 아님)의 로그인 `mckim` 인증/권한 실패(MSSQL 18456 "Login failed")가 `WebProductDatabases` 등록 DB(cc_test_20260625, dk_game_release_235~242_20260625, dk_game_release_luanna_20260625) 수만큼 반복 재연결·로그·후속 I/O 유발. conn_health network circuit-breaker 는 auth 를 **의도적으로 제외**(shared/db.py `_is_connect_breaker_failure` — 한 계정 자격오류가 datasource 를 unstable 로 오판하지 않게)해, 첫 DB 18456 뒤에도 나머지 DB 를 계속 시도한다.
- **운영 조치 분리(저장소 세션 범위 밖, 검토항목)**: WebDatasources `mssql-qa-idc` InsightEnabled=0, SQL Server login `mckim` 존재/잠금/기본DB 확인, 대상 DB 별 `mckim` USER+db_datareader GRANT(bin/datasource-mssql-ro-bootstrap-multidb.sql), registry 연결정보 UI/API 갱신 — 프로덕션 DB·암호화 registry 접근 필요라 운영자 수행. 본 cycle 은 코드 개선(재시도 억제)만 담당.

### §2.1 Implementation Plan
- **파일 경로 + symbol:**
  - `shared/config.py`: `AGENT_INSIGHT_AUTH_COOLDOWN_SEC` 신규(`__all__` 등록 + 정의, 기본 600s=10분).
  - `unit/feature-0002-agent-core/src/modules/insight.py`:
    - module-level `_DS_AUTH_COOLDOWN: dict[str,float]` + 헬퍼 `_ds_auth_cooldown_active/_set/_clear` (`_LAST_DS_SCAN_STATUS` 대칭).
    - `run_insight_cycle` datasource 루프(`for _ds_key,_ds_coords`) 진입부: cooldown active scope 통째 skip(`continue`) + health `perm_failed` 기록 + `db_skipped_auth` telemetry.
    - DB 순회 루프(`for _db_name` → `enumerate`) except: 첫 perm_failed(`_is_perm`) 시 cooldown set + 나머지 DB `break`(cycle 내 skip) + 남은 수 `db_skipped_auth` 집계.
    - else(성공) 블록: `_ds_auth_cooldown_clear`(정상 복귀 시 즉시 해제 — 운영자 GRANT 수정 후 자동 복구).
    - scan_report 템플릿 `db_skipped_auth: 0` + heartbeat KV `insight_worker_last_db_skipped_auth` 노출.
    - 진단 힌트(2483/2504 stale) 정정: 단일 `-bootstrap.sql` → 다중 DB `-bootstrap-multidb.sql` 병기.
  - `unit/feature-0002-agent-core/tests/test_mssql_auth_cooldown.py`: 회귀 테스트 신규.
- **접근:** conn_health 는 미변경(auth 제외 설계 의도 보존) — network backoff 와 분리된 별도 cooldown 을 insight 레벨에 둔다. auth_failed 를 PG/관리콘솔 status 로 도입하지 않고 scan_outcome=perm_failed 재사용 + telemetry 카운터로 관측성 확보(파급 최소).
- **완료 판정 기준(acceptance):**
  - AC1: 같은 scope 10 DB 중 첫 DB 18456 발생 시 실제 connect 시도는 1회만(나머지 9 DB skip).
  - AC2: 다음 cycle 에서 cooldown 만료 전까지 그 scope 는 connect 0회(진입부 통째 skip).
  - AC3: cooldown 만료 후 재시도 1회 허용(자동 복구). 스캔 성공 시 cooldown 즉시 해제.
  - AC4: `AGENT_INSIGHT_AUTH_COOLDOWN_SEC=0` 이면 cooldown 비활성(기존 동작), cycle 내 skip(break)은 유지.
  - AC5: `py_compile` 통과 + 회귀 테스트 pass + 기존 insight 테스트 회귀 0.
- **위험도:** Minor(내부 워커 순회 로직, 비파괴, 외부 I/O 비용 감소 방향). 사용자 요청으로 진행.

### 완료 체크리스트
- [x] `shared/config.py`: `AGENT_INSIGHT_AUTH_COOLDOWN_SEC`(기본 600s) 신규 + `__all__` 등록.
- [x] `insight.py`: module-level `_DS_AUTH_COOLDOWN` + 헬퍼(`_ds_auth_cooldown_active/set/clear`) — monotonic·자동만료, `_LAST_DS_SCAN_STATUS` 대칭.
- [x] `insight.py`: datasource 루프 진입부 cooldown gate(active scope `continue` + health perm_failed + `db_skipped_auth`).
- [x] `insight.py`: DB 순회(`for _db_name`→`enumerate`) except 첫 perm_failed 시 cooldown set + `_auth_break` 로 나머지 DB `break`(남은 수 `db_skipped_auth`).
- [x] `insight.py`: 성공(else) 시 `_ds_auth_cooldown_clear` + heartbeat KV `insight_worker_last_db_skipped_auth` + 진단 힌트 stale 정정(-bootstrap.sql → -bootstrap-multidb.sql 병기).
- [x] 회귀 테스트 `tests/test_mssql_auth_cooldown.py` + 기존 insight/mssql/datasource 8파일 회귀 0 + py_compile PASS.
- [x] §18.8 적대 리뷰(SUBAGENT adversarial-backend-correctness) — HIGH 2 + MEDIUM 2 + LOW 2 **실증** 전건 흡수: **HIGH-1** cooldown 키 scope_key(host:port 해시, login 제외)→**datasource label** 로 변경(같은 host:port 다른 계정 연쇄차단 방지 — anti-contamination 불변식 복원). **HIGH-2** break/cooldown 트리거를 `_is_login_failure`(18456)로 한정(916/229/297 은 해당 DB 만 실패로 계속 — 커버리지 회귀 방지). 후속: 916 실제 메시지가 "login failed" 텍스트 포함 → `_is_login_failure` 를 **error number 18456 우선**으로 정밀화. MEDIUM-3(복구 문서정정)·LOW-5(cooldown prune)·LOW-6(gate discovery 뒤 이동, telemetry 정확화) 흡수. REV-20260710T191159-mssql-auth-cooldown. 테스트 8→**11**(HIGH-1/HIGH-2/prune 추가), 합계 **98 PASS 회귀 0**.
- [ ] verify-completion → commit → 배포(insight-worker 재기동, 백엔드라 PB-0008 비대상).

## TASK-20260703-insight-table-grouping — insight-worker 동일구조 테이블 그룹화(대표 1회 분석 + 형제 전파) (Major §12.3, 사용자 요청, feature-0016 metadata 효율 교차) — code+unit done
- 출처: `/_template:entry`(2026-07-03). 사용자 관측 — "AI 운영 현황"의 "테이블 분석"이 날짜/번호 suffix 만 다른 동일구조 샤드(`web_ranking.daily_league_ranking_1_20250727`, `_20250726` …, `web_statistics.DayuPoint_20260211`, `_20260210` …)를 **각각 개별 LLM(claude-haiku) 분석**해 비효율. 요청: "유사한 형식의 구조는 일반적 분류로 구분해 한 번에 처리". PLAN-APPROVED(AskUserQuestion — 접근 A+B 결합, worktree+plan).
- 근본원인: `_scan_instance_schema_insights`(insight.py) 가 테이블마다 `llm_table_insight` 1회 호출. `table_insight:` fact 키가 테이블명별 유니크라 동일 지문(`_compute_table_fingerprint` = 컬럼명+타입 해시)이어도 각 샤드가 `artifact_missing` 로 개별 LLM. 지문은 변경감지에만 쓰이고 그룹화 미사용. 분석문(`_format_table_insight_text`)은 **구조(컬럼)에서만** 파생 → 샤드끼리 사실상 동일(테이블명은 prefix 한 줄만).
- [x] `shared/config.py`: `AGENT_INSIGHT_TABLE_GROUPING_ENABLED`(기본 on)·`AGENT_INSIGHT_TABLE_GROUP_MIN_MEMBERS`(2)·`AGENT_INSIGHT_TABLE_GROUP_FANOUT_MAX`(200) 신규 + `__all__` 등록(star-export NameError 방지 — feature-0016 config `__all__` 누락 선례 반영).
- [x] `insight.py` 순수 헬퍼: `_table_base_stem`(후행 날짜/번호/백업 suffix 반복 strip, 최소 2글자 보존)·`_table_group_sig`·`_build_table_groups`(그룹 키=(base_stem, fingerprint) — 지문=구조 동일, base_stem=이름-family 동일 **둘 다** 요구 → 구조만 우연히 같고 도메인 다른 테이블 오합침 방지)·`_group_insight_kv_key`/`_load_group_insight_kv`/`_save_group_insight_kv`(대표 분석 dict 를 `table_group_insight:<fp>:<stem>` KV 캐시 — fp 변경 시 키 자기무효화).
- [x] `insight.py` 발행 단일화: `_publish_table_insight`(렌더→publish→verify→fp저장→refresh→telemetry) 헬퍼로 대표·형제 경로 통합(발행 로직 drift 방지, 기존 경로 verbatim 추출).
- [x] `_scan_instance_schema_insights` 통합: 대표 분석 확보 순서 = cycle cache → KV 상속(이전 cycle 대표, LLM 0) → LLM(대표만, KV 시드). 이어서 같은 그룹 ready(미완/변경/refresh) 형제에게 LLM 없이 fan-out(대표 분석 dict + 대표 컬럼 재사용 — 동일 지문이라 컬럼 동일). per-table `table_insight` fact 유지 → grounding(NL→SQL) 무회귀. B-라벨: `source_meta.table_family`(base_stem·members·via) + telemetry `insight_via` + report `insight_llm_calls`/`tables_fanout`. `made_progress` 에 fan-out 포함(무진전 오판 backoff 방지).
- [x] 무회귀 게이트: grouping off → 기존 동작 그대로. 싱글턴/그룹 미형성 → 기존 per-table LLM. 지문 변경 → 새 sig → fresh LLM. 다른 도메인 동일구조 → 다른 base_stem → 미병합.
- [x] 단위 테스트 `tests/test_insight_table_grouping.py` +16(stem strip 6·그룹 서명/구조가드/도메인가드 5·KV 상속 roundtrip/무효화 3·포매터 방어 2). 로컬 PASS. 기존 insight 계열 79 PASS(회귀 0), config star-export PASS. **컨테이너 `make test` PASS(ruff All checks passed, exit 0)** — 리뷰 수정 후 재실행 포함.
- [x] §18.8 적대적 backend/correctness 트레이스(REV-20260703-insight-table-grouping) — CHANGES-REQUESTED → **확정버그 2(BUG1 cross-schema fan-out 무력화·BUG2 repair 이중처리) + actionable 우려 2(P1 대표 샤드명 날짜누출→family 패턴명 일반화·P2 malformed dict KV wedge→성공후 저장+포매터 방어) 전건 흡수** → SHIP-WITH-FIXES. 나머지 refuted/residual.
- [ ] verify-completion(§16.3) → commit → cycle-final → 배포(deploy_scope: included — insight-worker 재기동, 백엔드 변경이라 PB-0008 시각검증 대상 아님).
- Cross-ref: feature-0016-metadata-graph(8,122 테이블 컨텍스트 효율 비전 정합, node_analysis 그래프 버튼 트리거는 별도 예산 시스템이라 범위 밖). 근거: `docs/FUNCTION.md:203`(~11s/LLM 호출·3000-테이블 DB 완주 12~26h 병목).

## TASK-20260629T142624-active-interp-modality — 능동해석 지침 modality-무관 일반화 + MySQL casing (Major §12.3, conversation_audit FR-nl2sql 후속) — done
- 출처: `/_dqa:conversation_audit` 가 라이브 1:1 conv …91655acc 를 감사해 마찰 `FR-nl2sql-schema-discovery-giveup` 적발 — assistant 가 스키마 `dbGame`→`dbgame` 소문자화→`1049 Unknown database`→8 tool 후 give-up·대량 재질문. 근본원인: (a) 능동해석 지침이 그룹대화에만 주입돼 1:1 무방비, (b) MySQL 식별자 case-sensitivity 안내 부재. PLAN-APPROVED.
- [x] `_GROUP_CONVERSATION_GUIDANCE` 의 modality-무관 본문(능동 해석·합리적 추정·스키마 발견·데이터소스 일관성·give-up 금지)을 `_ACTIVE_INTERPRETATION_GUIDANCE` 로 분리, `_run_agent_core` 에서 그룹 조건(`if _group_sender_labels`) **밖에서 무조건 주입**(1:1·그룹 모두). 그룹 블록엔 다자-특화(발신자 라벨·사람-사람 맥락)만 잔존 + 능동 해석 절 cross-ref.
- [x] `_MYSQL_DIALECT_GUIDANCE` 에 식별자 case-sensitivity 블록 추가(Linux MySQL 대소문자 구분, 도구 보고 표기 보존·소문자화 금지, 오류코드 `1049`/`1146`, `SCHEMA()=NULL` 시 명시 qualify).
- [x] 회귀 테스트 `tests/test_gc_dialect_context.py` +5(modality-무관 단언·group multiparty-only·1:1 무조건 주입 indent·split de-dup 전체 잠금). gc 9 PASS, prompt/dialect/group/reflection 광역 회귀 0, py_compile PASS.
- [x] §18.8 full 패널(AGENT-TEAM 3렌즈: qa·회귀·정합성 / security·over-reach / rootcause-completeness) — BLOCKER1+MAJOR3 전부 적대검증 **REFUTED**(scope·정책 정합), PASS-WITH-NITS. → REV-20260629T142624.
- follow-up(별도 human-plan, ledger re-triage 시): L2 에러피드백 교정힌트(`_classify_sql_error` 1049 분류 + `_sql_reflection_nudge` casing 힌트 + 휴면 `_mcp_auto_retry` 배선), MySQL exact-case DB grounding 비대칭 대칭화(MSSQL 패턴 차용).

## TASK-20260629T022055-feedback-id-space — 피드백 고유성 키에 message_id_space 추가 데이터 계층 (Major §12.3, feature-0003 주관 — 데이터 계층 교차) — done
- 출처: 사용자 요청 — 선행 TASK-20260629T014345-feedback-unique-vote 적대 리뷰의 H5(b)(message_id 두 id 공간 모호성) 잔여 한계 완수. 데이터 계층(컬럼·인덱스·코어 UPSERT)이 feature-0002 거주라 교차 기록.
- [x] **alembic 0022**(`20260629_0022_sample_feedback_id_space.py`, down_revision 0021): `message_id_space varchar(16) NOT NULL DEFAULT 'display'` 추가 + 3-col 부분 UNIQUE **신규명** `ux_sample_feedback_user_msg_space_vote (created_by, message_id, message_id_space)` (구 2-col `ux_sample_feedback_user_msg_vote` DROP — same-name no-op trap 회피). 기존 행 default 'display' 무손실.
- [x] `src/modules/sample_feedback.py` `record_feedback`: `message_id_space` 인자(정규화 display|core) + INSERT/ON CONFLICT 3-col `(created_by, message_id, message_id_space)`.
- [x] 부트스트랩 `src/scripts/agent_kb_schema.sql` 미러(구 인덱스 DROP + 신규명 3-col + 컬럼).
- [x] FUNCTION.md AC 갱신(0021 한계 해소 + 신규 AC).
- [x] 테스트: `test_sample_flywheel.py` 13/13(masks_pii param 위치 보정 + 3-col ON CONFLICT + id_space 전달 단언). py_compile PASS.
- [x] self-review(H5(b) closure) — REV-20260629T022055-feedback-id-space. (선행 cycle 적대 리뷰가 결함·설계 이미 도출.)
- [ ] verify-completion → 머지·push → 배포(0022 적용).
- Cross-ref: feature-0003 TASK/CHG/REV-20260629T022055-feedback-id-space / 선행 TASK-20260629T014345-feedback-unique-vote.

## TASK-20260629T014345-feedback-unique-vote — 답변당 사용자별 고유 피드백 데이터 계층 (Major §12.3, feature-0003 주관 — 데이터 계층 교차) — done
- 출처: `/_template:entry` dispatch(feature-0003 주관). 사용자 보고: assistant 답변 피드백(👍/👎) 새로고침·전환 후 중복 부여 가능 → 답변당 고유 피드백만 가능해야 함. 데이터 계층(테이블·코어 적재)이 feature-0002 거주라 교차 변경 기록.
- [x] **alembic 0021**(`20260629_0021_sample_feedback_unique_vote.py`, down_revision 0020): `sample_feedback.message_id bigint` + 부분 UNIQUE `ux_sample_feedback_user_msg_vote (created_by, message_id) WHERE message_id IS NOT NULL AND created_by IS NOT NULL AND suggested=false`. 기존 행 NULL → 술어 제외(무손실·멱등). chain linear 단일 head.
- [x] `src/modules/sample_feedback.py` `record_feedback`: `message_id` 인자 + INSERT→UPSERT(`ON CONFLICT … DO UPDATE`)+`RETURNING id`(lastval 부정확 회피). status·suggested·promoted_sample_id 미변경(검수 lifecycle 보존). "샘플 등록"(suggested=true)은 술어 제외 → 매번 INSERT 보존.
- [x] FUNCTION.md REQ-20260623-1621 에 고유성 불변식(AC) 추가.
- [x] 테스트: `test_sample_flywheel.py` 15/15(masks_pii param 보정+ON CONFLICT/DO UPDATE/RETURNING 단언+신규 vote-UPSERT 키). py_compile PASS.
- [x] §18.8 적대 backend 리뷰(H1~H7) VERDICT FIX-NEEDED — H5(b) 두 id 공간(표시 store vs core_messages) 수용·문서화(첨부 영속 공유 선재 특성, 정상 경로 완전 강제), 나머지 REFUTED. REV-20260629T014345-feedback-unique-vote.
- [x] **배포 정합 follow-up(CHG-20260629T0210-feedback-unique-vote-bootstrap-sql)**: 0021 변경을 boot 정본 `src/scripts/agent_kb_schema.sql`(=`_ensure_pg_schema()` 가 매 boot idempotent 적용, agent_core.py:3960)에도 미러. **누락 시 배포에서 message_id/인덱스 미생성 → record_feedback 의 `ON CONFLICT (created_by, message_id) WHERE …` 가 매칭 인덱스 부재로 런타임 에러(피드백 전건 실패)**. alembic 은 versioned-history 이고 실 배포 스키마는 부트스트랩 SQL 이 적용(0014/0017 선례 동일 — 양쪽 미러 필수). main 31aa67a 머지 후 적발·보완.
- Cross-ref: feature-0003 TASK/CHG/REV-20260629T014345-feedback-unique-vote.
## TASK-20260629-glossary-conv-autoreg — 용어사전 대화 자율등록 코어 (Major §12.3, cross-feature 0002+0003, 상세는 feature-0003 TASK, ADR-20260629T101500)
- 출처: `/_template:entry`(2026-06-29). 코어 측 산출물(web/UI 는 feature-0003):
- [x] **마이그레이션 0023**(`alembic/versions/20260629_0023_glossary_role_autoreg.py`): kb_glossary.role_key/source ADD + UNIQUE(scope_key, role_key, term) 재정의, glossary_feedback(검토 큐: pending/auto_promoted/promoted/rejected)·glossary_relations(synonym/similar/see_also) CREATE + 인덱스/트리거/GRANT(agent_kb_rw/ro). 기존 행 role_key='*'·source='manual' backfill(동작 불변). 단일 head 검증 PASS.
- [x] **kb_glossary.py 확장**: role-scoped read(`load_glossary_enum_context(role_key=)` → [역할,'*'] 격리, role_key=None 하위호환), 하이브리드 자동승급(`auto_promote_or_queue`·`record_glossary_suggestion`·`promote/reject_glossary_feedback`·되돌리기), 유사어(`add/list/delete_glossary_relation`·`get_glossary_term`), 대화 추론(`infer_terminology_suggestions`). upsert/update/list 에 role_key·source 반영.
- [x] **llm.py**: `llm_glossary_suggest`(GLOSSARY_SUGGEST_PROMPT, 요약 티어, soft-fail) — Q&A → [{term,definition,confidence}].
- [x] **agent_core hook**: `_glossary_autopropose`(run_agent 답변 직후) — best-effort, AGENT_GLOSSARY_AUTOPROPOSE 게이트, role_key='*' 기본, ask 경로 비차단.
- [x] **shared/config.py**: AGENT_GLOSSARY_AUTOPROPOSE·SUGGEST_MODEL·AUTOPROMOTE_THRESHOLD(0.85)·SUGGEST_MAX(5) + __all__.
- [x] 테스트 `test_kb_glossary_enum.py` 19건 PASS(역할 read 격리·하이브리드 분기·거부 되돌리기·관계 SQL). ruff·py_compile PASS.

## TASK-20260625T164701-ds-conn-circuit-msg (current cycle) — datasource 회로차단 사용자 안내 문구 분리 (Minor §12.3, cross-feature feature-0002 주관) — done
- 출처: 사용자 보고(2026-06-25) "WEB_QA 데이터소스 연결 불안정/오류 메시지 개선". `DatasourceCircuitOpen` 회로차단(일시 지연 격리·자동복구)이 "DB 연결 실패/불안정/차단" 으로 노출돼 서비스 고장으로 오인. 사용자 결정: 톤=투명형, 용어="데이터소스". 원본 entry 세션 중단(API Overloaded) → resume 로 재개.
- [x] `shared/db.py` `DatasourceCircuitOpen.user_message()` 신설(사용자 화면 전용, 기술 `str(e)` 분리·미변경).
- [x] `agent_core` 멀티 primary·단일 fallback except 2곳 + `tools.execute_tool` 1곳 `isinstance`/`except DatasourceCircuitOpen` 분기로 안내 문구 노출(circuit 외 기존 문구 유지).
- [x] main drift 흡수: 재개 시 worktree 를 현재 main 으로 ff-merge(`df97f47`/TASK-0011-9 db import `modules.db`→`shared.db` 마이그레이션·`modules/db.py` 삭제 반영) 후 `shared.db` 경로 기준 재적용.
- [x] §18.8 적대 패널(6축 REFUTE) BLOCKING 0 — REV-20260625T164701-ds-conn-circuit-msg. py_compile + ruff All passed + 회귀 153 PASS.
- [x] docs: MODIFY CHG-20260625T164701 · FUNCTION ds-conn-circuit-msg · REVIEW REV-20260625T164701 · REPORT Recent Changes.
- [ ] verify PASS → commit → push → PR → merge → deploy(deploy_scope: included, ask-worker/web 재빌드) → smoke.

## TASK-20260623T191241-item05-hybrid-search (current cycle) — ITEM-05 하이브리드 검색 (벡터+키워드 score fusion) (Major §12.3, ROADMAP dba-ai-nl2sql)
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-23 -->
- 출처: ROADMAP dba-ai-nl2sql ITEM-05(P2 Major). depends_on ITEM-01(eval harness). 현 2-tier fallback(벡터 OR trigram)을 단일 fusion 랭킹으로. PLAN-APPROVED(+ KB retrieval eval set 구축).

### §2.1 Implementation Plan
- **영향 파일**: `modules/kb_retrieval.py`(`_load_rag_documents_for_request_pg` 분기 + `_fuse_rag_documents` 신규) · `modules/config.py`(AGENT_KB_HYBRID_ENABLED/ALPHA/BETA/NORMALIZE) · `tests/test_hybrid_search.py`(신규) · `tests/eval/kb_eval/*`(retrieval eval 자산 신규) · `Makefile`(kb-retrieval-eval 타깃).
- **접근**: gate ON(기본) + qvec 존재 시 vector(cosine)+trigram(pg_trgm) **둘 다** 수행 → (conversation_id, fact_key) union 병합 → score = α·vec_sim + β·trigram_sim → 내림차순 → `_normalize_rag_doc_rows`. **폴백 보존**: qvec None→trigram-only, vec·trg 둘 다 0→trigram-only fall-through. gate OFF→기존 2-tier 그대로(롤백 안전).
- **위험도**: Major(핵심 KB read 랭킹 경로 + 측정 게이트). 단, env gate + 폴백 보존으로 blast 격리.
- **acceptance**: AC-a fusion 점수 결합·정렬·한쪽매칭·qvec None·gate off 단위검증. AC-b retrieval A/B(fusion vs 2-tier) 라이브 측정·회귀 없음. AC-c verify PASS·인접 회귀 0.
- [x] `_fuse_rag_documents` + gate 분기(폴백 보존) + config 4종(ENABLED/ALPHA/BETA/NORMALIZE).
- [x] **스케일 정규화(NORMALIZE, 기본 ON)**: 측정상 bge-m3 cosine(~0.4~0.8)과 한국어 pg_trgm sim(~0.01~0.2)은 척도가 달라 raw 가중합이 vec 에 지배(벡터-only 와 사실상 동일) — query-단위 min-max([0,1]) 후 가중합으로 α/β 가 실제 의도대로 두 신호를 섞도록. OFF=raw(롤백/비교).
- [x] 단위 `tests/test_hybrid_search.py` 11개(fusion 결합·정렬·union 병합키·vec-only·trg-only·정규화 ON/OFF 대조·both-empty 폴백·qvec None→trigram·gate off 2종 + **REV-MAJOR 회귀: same-factkey/다른-content 비병합 2건 분리**) 통과 + py_compile.
- [x] KB retrieval eval set: `tests/eval/kb_eval/{provision_kb.py,golden_retrieval.yaml,retrieval_eval.py,__init__.py}` — evalkb scope 격리(운영 KB 무오염, --purge 정리) 12 docs(핵심 8 + distractor 4, bge-m3 1024 임베딩) + 7 질문 ground-truth + precision/recall@k + MRR A/B 리포트. `make kb-retrieval-eval`.
- [x] **라이브 A/B 측정(bge-m3, k=3)**: fusion vs 2-tier — mean_precision 0.4286=0.4286, mean_recall 0.9286=0.9286, mean_f1 0.5714=0.5714, MRR 1.0=1.0 (Δ 전부 +0.0000). **verdict NEUTRAL(회귀 없음)**. 정규화 ON 은 하위 순위(2~3위 distractor)를 재랭킹하나, bge-m3 가 이미 MRR=1.0 로 정답을 1위에 두어 headline 지표 상승 헤드룸 없음. raw(NORMALIZE=0)도 동일 NEUTRAL. **유의 상승 미관측 — 강한 임베더가 깨끗한 합성 KB 에서 retrieval 을 포화. fusion 은 키워드-recall 보험으로 비회귀 안전.** (은폐 없이 그대로 보고; REPORT.md 상세.)
- [x] **적대 backend 리뷰**(REV-20260623T191241-item05-hybrid-search, SHIP-WITH-FIXES): MAJOR(병합키가 schema unique `(conv,fact)` 와 어긋나 동일 factkey·다른 content 정답 유실) + MINOR-1(trigram 무관 distractor 정규화 부풀림) + MINOR-2(span-0 ft_score 0 처리) **전부 흡수**. fix: 병합키 `(conv,fact,content)`+max 누적 · `AGENT_KB_HYBRID_TRIGRAM_FLOOR`=0.05 · span-0 raw fallback. 회귀 테스트 +1.
- [x] **가치 입증 측정(사용자 "가치 입증 후 마감" 지시)** — 적대적 corpus 로 fusion lift 입증 시도: `tests/eval/kb_eval/{provision_kb_adv.py,golden_retrieval_adv.yaml,retrieval_eval_adv.py}` (evalkb_adv 격리, 24 docs/12 질문 = rare-token·opaque-code·검증된 vector-miss 3 tier, 정답에만 rare exact token + token-없는 의미-유사 distractor). **A/B + 파라미터 sweep(NORM on/off × α/β 7조합) 결과: 모든 지표 +0.0000(MRR 1.0 both) — lift 반증(REFUTED)**. 근본 원인(격리 cosine 실측): bge-m3 가 subword/char 인지라 질문의 rare token 이 정답 doc cosine 도 함께 끌어올려(벡터·trigram 同방향 합의) fusion 이 바꿀 top rank 없음 — fusion-favorable 과 vector-miss 가 양립 불가. fusion 의 retrieval 정확도 가치는 **임베더-장애/미임베딩 폴백**(이미 qvec None 폴백 커버)에 국한. (REPORT.md 상세; 은폐 없이 기록.)
- [x] **마감 결정(사용자 2026-06-24): gated-OFF dormant + done**. `AGENT_KB_HYBRID_ENABLED` 기본 `1`→`0` 전환(운영 거동 불변 — 2-tier 유지). fusion 코드·eval 자산은 비회귀 안전 + 임베더-장애 폴백 보험으로 dormant 보존. 실가치 재측정은 라이브 운영 질의 로그(임베더 실패 케이스) 필요 — ITEM-12 튜닝 근거는 현 corpus 론 없음.
- [x] verify PASS. worktree `ai/claude/feature-0002-agent-core`. ROADMAP ITEM-05 → done(반증·gated-OFF 명시).

## TASK-20260623T163242-sample-embed-dim-1024 (current cycle) — ITEM-02 sample_queries 임베딩 차원 1536→1024 정렬 (fix, Minor §12.3)
- 출처: ITEM-02 PR-A 후속 fix. titan-embed/경로B(로컬 1024) 검토 중 발견 — 0014 가 sample_queries.embedding 을 vector(1536) 로 만들었으나 실제 임베딩 모델은 1024-dim(AGENT_KB_EMBEDDING_DIM=1024, texts 정본=alembic 0001 vector(1024)). 1024 벡터 INSERT 시 차원 불일치 런타임 실패. 사용자 결정(2026-06-23): 지금 1024 정렬.
- [x] 마이그 0015(sample_queries.embedding 1536→1024, DROP+ADD 빈컬럼 안전, ivfflat 재생성) + schema.sql sample_queries 1024 + config 기본 1024 정렬.
- [x] 라이브 pg16 적용 + 1024 register(list)→search retrieval sim=1.0 정합 검증. 단위 test_sample_flywheel 12 회귀 0(FakeConn dim-agnostic). py_compile.
- [x] 적대 backend 리뷰 REV-20260623T163242 **SHIP**(마이그 정합·다운그레이드 대칭·blast 0; config 기본은 informational). NIT(docstring) 흡수.
- [ ] **flag(범위 밖)**: texts schema.sql:68 + kb_backend.py:940 의 stale `vector(1536)` 주석(정본 alembic 0001 = 1024). texts 는 라이브/정본 1024 라 동작 무관하나 fresh-install bootstrap 정합 위해 별도 cleanup 권장.
- verify PASS. worktree `ai/claude/feature-0002-agent-core`.

## TASK-20260623T151643-self-reflection (current cycle) — ITEM-07 Self-Reflection 자가수정 루프 (Major §12.3, ROADMAP dba-ai-nl2sql)
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-23 -->
- 출처: ROADMAP ITEM-07. chat 의존(임베딩 무관). PLAN-APPROVED.

### §2.1 Implementation Plan
- **영향 파일**: `agent_core.py`(helper `_is_fixable_sql_error`/`_classify_sql_error`/`_sql_reflection_nudge` + tool 루프 훅 + per-run `reflection_count`) · `config.py`(AGENT_SELF_REFLECTION_ENABLED/MAX).
- **접근**: tool 루프에서 `execute_sql` 가 **수정 가능한** 실패(`오류:`/`SQL 실행 오류:`/`도구 실행 오류`) 반환 시, cap(N≤2~3) 미만이면 구조화 정정 넛지(에러 분류+원 SQL+표적 힌트)를 tool 결과에 동봉. 보안 가드 차단은 제외(우회 유도 금지). max_steps·circuit-breaker 중첩으로 폭주 차단. env gate(A/B·롤백).
- **위험도**: Major(핵심 run 루프 제어흐름 + 에러시 프롬프트 동봉) + 보안(guard 제외).
- **acceptance**: AC-a 에러 시 ≤cap 넛지 후 중단(폭주 없음, 단위). AC-b(측정) harness on/off 회복률 — **보류**(describe-first agent 가 단순 fixture 에서 거의 에러 안 남 → 1차 실패 부재; 에러유발 production traffic/error-injection 모드 필요). AC-c guard 제외(보안). AC-d verify PASS.
- [x] config 플래그 + helper 3종 + tool 루프 훅(가드 제외·cap·gate) + per-run 카운터.
- [x] 단위 `test_self_reflection.py` 7(분류/넛지/guard 제외/**실제 'SQL 실행 오류:' shape**/cap 표기/truncate) 통과 + prompt-injection 회귀 10 통과 + py_compile.
- [x] 적대 backend+security 리뷰 REV-20260623T151643 — **MAJOR(M1: 실제 'SQL 실행 오류:' prefix 미매칭→near-inert) 흡수** + M2(테스트 보강)·N1(guard 토큰)·N2(분류 순서) 흡수.
- [x] 라이브 관찰: describe-first agent 가 `amount`→`total` 을 **에러 없이** 교정(645.00 정답) → reflection 은 백스톱(단순 fixture 미발동).
- [ ] **AC-b 정량 회복률 보류** — 에러유발 golden Q/error-injection harness 모드 필요(follow-up). 메커니즘은 단위검증 + 실제 에러 경로 매칭 확정.
- verify PASS. worktree `ai/claude/feature-0002-agent-core`.

## TASK-20260623T145444-sample-flywheel-core (current cycle) — ITEM-02+03 샘플쿼리 flywheel PR-A 코어 (Major §12.3, ROADMAP dba-ai-nl2sql)
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-23 -->
- 출처: ROADMAP ITEM-02(저장소)+ITEM-03(피드백 flywheel) 결합. 사용자 지시 "성장 루프까지 앞당김". 순차 2-PR 중 **PR-A(feature-0002 코어)**. PR-B(feature-0003 웹 UI/RBAC/audit)는 후속.

### §2.1 Implementation Plan
- **영향 파일**: `agent_kb_schema.sql`+`alembic 0014`(sample_queries/sample_feedback) · `modules/sample_queries.py`(신규) · `modules/sample_feedback.py`(신규) · `agent_core.py`(EXAMPLE QUERIES 주입) · `config.py`(AGENT_SAMPLE_QUERIES_ENABLED).
- **symbol**: `sample_queries.{register_sample,search_samples,load_example_queries_context,validate_sample_sql}` · `sample_feedback.{record_feedback,promote_feedback,reject_feedback}`.
- **접근**: ds-scoped sample_queries(임베딩 vector(1536)) approved∧active cosine top-K(weight 가중) → `## EXAMPLE QUERIES` few-shot 주입(예시-only 펜스). sample_feedback 은 👍/👎/등록 원천 → 승인 큐 → promote_feedback 로 approved 승급(자동학습 금지). flywheel-ready 필드(source_type/status/weight/last_validated_at) + 신선도 validate_sample_sql.
- **위험도**: **Major** + 보안 표면(PII 마스킹·injection-only).
- **acceptance**: AC-a 등록→유사질문 approved∧active top-K 주입(단위·ds격리·미승인/stale 비주입·weight). AC-b 피드백 PII 마스킹 적재→promote→approved 승급(코어 로직 단위). AC-c injection-only(샘플 실행 금지 펜스). **AC-d(측정) 보류** — titan-embed(임베딩) 다운으로 라이브 retrieval/A/B 불가(복구 후). AC-e verify PASS.
- [x] 스키마 sample_queries/sample_feedback + alembic 0014 + 라이브 pg16 dry-run(테이블·ivfflat·cosine sim=1·upsert·GRANT, ROLLBACK).
- [x] sample_queries.py(register `%s::vector`·search approved∧active∧weighted·load·validate) + sample_feedback.py(record PII-mask·promote·reject) + agent_core EXAMPLE QUERIES 주입(gate·datamark·예시-only) + config flag.
- [x] 단위 `test_sample_flywheel.py` 12(등록/검색 SQL/주입/PII/승급/거부/신선도) 통과 + py_compile + **라이브 register(list 임베딩)→search retrieval sim=1.0 검증**(::vector BLOCKER 흡수).
- [x] 적대 backend+security 리뷰 REV-20260623T145444 — **BLOCKER(embedding ::vector 누락) 흡수** + MINOR 정정.
- [ ] **AC-d A/B 측정 보류** — titan-embed 401 AUTH-DOWN(chat 만 복구). 임베딩 복구 후 `make eval` 샘플 off/on. **PR-B(웹 UI/RBAC/audit) + 임베딩 클러스터(05/06/12)도 복구 후.**
- verify PASS. worktree `ai/claude/feature-0002-agent-core`.

## TASK-20260623T105344-kb-glossary-enum (current cycle) — ITEM-10 용어사전 + ENUM 코드사전 (Major §12.3, ROADMAP dba-ai-nl2sql)
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-23 -->
- 출처: `docs/improvements/dba-ai-nl2sql/ROADMAP.md` ITEM-10. `/_dqa:improve_cycle` 드레인 — Major plan-review 승인 후 **구조부**(저장+읽기+주입) 구현. 측정(ENUM 정확도)은 bedrock-auth 복구 후 보류.

### §2.1 Implementation Plan
- **영향 파일**: `src/scripts/agent_kb_schema.sql`(+kb_glossary/enum_dictionary +GRANT), `alembic/versions/20260623_0013_*`(마이그), `src/modules/kb_glossary.py`(신규), `src/agent_core.py`(`_build_knowledge_context` 주입), 테스트.
- **symbol**: `kb_glossary.{upsert_glossary_term,upsert_enum_entry,load_glossary_enum_context}` · `_build_knowledge_context`.
- **접근**: agent_kb(PG)에 ds-scoped(scope_key) 용어/ENUM 저장 → 질문/스키마 매칭 시 `_build_knowledge_context` 가 datamark+펜스로 주입. scope 는 활성 datasource(`get_active_datasource`)로 도출(격리).
- **위험도**: **Major** — 신규 PG 테이블+마이그 + 프롬프트 경로 주입.
- **acceptance**: AC-10a 용어/ENUM upsert 후 ds-scoped read 매칭(scope 격리, FakeConn 단위) · AC-10b 관련 질문에서 프롬프트 datamark 주입(문자열 단위) · AC-10c verify PASS+회귀0 · AC-10d(보류) ITEM-01 harness 로 ENUM 정확도 측정 — bedrock-auth 복구 후.
- [x] 스키마 kb_glossary/enum_dictionary(scope_key 컨벤션·인덱스·트리거·GRANT) + alembic 0013(head 0012→0013, 멱등) + 라이브 pg16 트랜잭션 dry-run(CREATE/index/trigger/GRANT/upsert/scoped-read → ROLLBACK) 검증.
- [x] `kb_glossary.py` upsert(RW)+ds-scoped read(RO, get_active_datasource scope) + `_build_knowledge_context` 주입(datamark, 미매칭/미가용 "").
- [x] 단위 `test_kb_glossary_enum.py` 9(upsert SQL/매칭/조립/**ds 격리**/운영 default scope/미매칭·빈) + KB 회귀(read_backend·ingest) 26 통과. py_compile.
- [x] 적대 backend 리뷰 REV-20260623T105344 — **BLOCKER B1 흡수**(scope 를 CURRENT_FACT_SCOPE_KEY→get_active_datasource 로 수정: 미수정 시 ds-scoped 죽거나 cross-ds 누수) + M1(운영-path 테스트)·Mi2(_ro_conn try) 흡수.
- [ ] write-path(admin 편집 UI) + 반자동 ENUM 추출(describe/sample) = ITEM-11 follow-up. ENUM 정확도 측정 = bedrock 복구 후.
- verify-completion PASS. worktree `ai/claude/feature-0002-agent-core`(base 147d040).

## TASK-20260623T101031-ds-business-context (current cycle) — ITEM-04 데이터소스 비즈니스 컨텍스트 필드 (Minor §12.3, ROADMAP dba-ai-nl2sql)
- 출처: `docs/improvements/dba-ai-nl2sql/ROADMAP.md` ITEM-04(P1, feature-0002-agent-core primary, feature-0003 schema cross-ref). `/_dqa:improve_cycle` 드레인 — Minor 자율 진행.
- what: `WebDatasources` 에 `Description`(TEXT)·`DomainTags`(VARCHAR plaintext) 추가 → registry 병합(`_row_to_ds`) → 멀티DS 그라운딩 프롬프트 주입(어느 datasource 가 무슨 사업데이터인지 LLM 라우팅 그라운딩).
- acceptance: AC-1640 멀티DS 질문에서 datasource 설명이 그라운딩 프롬프트에 노출 · AC-1641 단일DS 제품 무영향 · AC-1642 구 스키마 graceful(컬럼 부재 시 None/[]) · AC-1643 verify-completion PASS.
- [x] feature-0002: `datasources._db_datasource`(Description/DomainTags SELECT + 구 스키마 legacy 폴백, fresh-cursor·진단로그) + `_row_to_ds`(매핑, len-가드 graceful) + `tools._DatasourceRouter.describe()`(노출, 좌표/비밀 비노출) + `agent_core._format_multi_ds_grounding()`(헬퍼 추출·설명/도메인 주입).
- [x] feature-0003 (schema cross-ref): `app.py` WebDatasources CREATE + 멱등 ALTER 로 Description/DomainTags 컬럼(InsightEnabled 선례 미러).
- [x] 단위테스트 `test_datasource_business_context.py` 7(매핑/graceful/describe 비밀비노출/그라운딩 설명노출/단일DS 빈문자열/설명생략) + multi_datasource 회귀 36 = 43 통과. py_compile.
- [x] 적대 backend 리뷰 REV-20260623T101031 **SHIP**(BLOCKER/MAJOR 0; MINOR 진단로그 흡수).
- [ ] **write-path(admin UI/API 로 Description/DomainTags 편집) follow-up** → ITEM-11(거버넌스 포탈, 메타데이터 편집 허브)에서. 현재는 nullable·SQL 로 설정 가능, read-side graceful.
- verify-completion PASS. worktree `ai/claude/feature-0002-agent-core`.

## TASK-20260619T172843-eval-harness (current cycle) — ITEM-01 NL→SQL 평가 harness (Major §12.3, ROADMAP dba-ai-nl2sql)
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-19 -->
- 출처: `docs/improvements/dba-ai-nl2sql/ROADMAP.md` ITEM-01(P0 측정기반, feature-0002-agent-core). `/_dqa:improve_cycle` 드레인 — Major 항목 plan-review 사용자 승인 후 구현.

### §2.1 Implementation Plan
- **영향 파일**: `src/agent_core.py`(`run_agent`/`_run_agent_core` — `eval_datasource` None-gated seam), `tests/eval/*`(신규 harness), `Makefile`(`eval` 타깃).
- **symbol**: `run_agent(eval_datasource=…)` · `_run_agent_core(eval_datasource=…)` · `tests/eval/{runner,metrics.result_equiv,fixture_provision.ensure_fixture}`.
- **접근**: golden 질문(≥20) → 실제 파이프라인(temp-0 결정 경로) → 생성SQL 수집 → fixture 에 생성SQL·정답SQL 실행 후 **execution-accuracy**(결과셋 set 동치, LLM 무관 결정적) + retrieval P/R(ground-truth 있을 때) → 타임스탬프 회귀 리포트(`artifacts/.../eval/`).
- **acceptance**: AC-1601 golden≥20 · AC-1602 `make eval` 가 retrieval/generation 수치+리포트 산출 · AC-1603 지표 *계산*은 결정적(정규화 set-동치 백본, LLM 무관); end-to-end 2회 동일은 temp-0 SQL 생성이 동일할 때(provider bit-결정 아님 — best-effort) · AC-1604 가드(fixture-only datasource · actual=agent CSV[sql_guard+allowlist 샌드박스]이라 harness 는 생성SQL 재실행 안 함 · expected_sql read-only insurance · judge cap) · AC-1605 verify-completion PASS.
- **위험도**: **Major** — 신규 offline harness + 핵심 run 경로에 None-gated seam(운영 0 변경) + eval 시 외부 LLM 비용(judge cap).
- [x] fixture 스키마+시드(결정적 합성 e-commerce, prod 무관/PII 없음) + golden 24문항(`expected_sql` ground-truth 라이브 검산 일치).
- [x] `tests/eval/{fixture_provision,metrics,runner,test_eval_harness}.py` + `run_agent` `eval_datasource` seam(None-gated, product/registry 라우팅 우회·운영 동작 0 변경).
- [x] `make eval` 타깃(라이브 스택 네트워크 + `AGENT_MULTI_DATASOURCE_ENABLED=1`) + pytest 스모크 11/11 통과(정규화/equiv/retrieval P·R/read-only 가드/golden 무결성).
- [x] fixture 멱등 provision + harness end-to-end 실행 + 리포트(JSON+MD)+직전대비 회귀 산출 확인.
- [ ] **measured generation accuracy 보류** — 스택 전반 Bedrock 인증 다운(2026-06-19 IAM 제거, 게이트웨이 401 "Unable to locate credentials"). 자격증명 복구 후 `make eval` 로 AC-1602/1603 라이브 수치 산출. harness 는 결함 없이 실패를 정직 보고(0.0).
- verify-completion(코드 게이트) PASS. worktree `ai/claude/feature-0002-agent-core`(base e1cf077).

## TASK-0304 (current cycle) — 무거운 쿼리 사전 감지 → LLM 이 더 가벼운 쿼리로 재작성해 목적 달성 (Major §12.3, REQ-20260618-0304)
- 사용자 요청: "차단하기보다, LLM 이 무거운 쿼리를 미리 감지해 되도록 부하 적은 쿼리 구성으로 목적을 달성하도록 동작". (TASK-0299 SHOWPLAN 부하추정 활용 — gate=하드차단/warn=사후경고 둘 다 의도와 불일치.)
- 결정(AskUserQuestion): "가로채고 LLM 재작성" — 무거운 원본은 실행 전 가로채되 LLM 이 tool 루프에서 더 가벼운 쿼리로 재작성→목적 달성. 최종 사용자엔 차단 미노출(효율적 답변만).
- [x] (AC-0578) agent_core.py SYSTEM_PROMPT 에 "QUERY LOAD — STAY LIGHT" 섹션: ⓐ 처음부터 효율적 쿼리(필요 컬럼만·WHERE 한정·서버측 집계·표본 LIMIT/TOP) ⓑ 큰 조회 전 explain_query 자가확인 ⓒ 게이트가 무거운 쿼리 표시 시 confirm_heavy 강행 금지·더 가벼운 동등 쿼리로 재작성 ⓓ confirm_heavy=최후수단.
- [x] (AC-0578) tools.py gate 메시지 reframe: "차단" 톤 → "실행하지 않았습니다 + 더 가벼운 쿼리로 재구성해 다시 실행" 코칭(재작성 우선·confirm_heavy 후순위). execute_sql/confirm_heavy 도구 description 동반 정렬.
- [x] 테스트: `test_gate_message_coaches_rewrite_not_block`(재구성·실행안함·최후수단 단언) + 기존 게이트 토큰("무거운 쿼리"/"confirm_heavy=true") 보존 회귀 0.
- [ ] make test 컨테이너 회귀 0 + ruff.
- [ ] outside-voice 리뷰(프롬프트 회귀·게이트 의미) + verify-completion.
- [ ] 머지→배포 3이미지 + 라이브 WebSystemPrompts global row 갱신 + AGENT_QUERY_GUARD_MODE=gate 활성. CHG/REV-20260618-0318.

## TASK-20260617T100524-ai-claude-account-insight-kv-source (current cycle) — 인사이트 추출 소스 kv 보강 (Major §12.3, 보안경계 불변)
- 배포 준비 중 발견: 이 배포는 `agent_runtime.summary` 0행(요약 쓰기 cutover 결함)이나 `agent_runtime.kv` 에 origin_request(79)/thread_goal(79)/topic(99) 존재 → 추출 pass 가 summary 필수 JOIN 이라 후보 0건(기능 무동작).
- [x] `run_account_insight_pass` 후보 쿼리 `JOIN summary`→`LEFT JOIN summary`(필수 제거) + per-conv **summary+kv 합산 신호** 게이트(≥MIN_SUMMARY_LEN)·합산 fingerprint. summary 비어도 kv 신호로 동작. 보안 가드(G1~G4·allowlist·PII)·source_type(account_insight, 전역 미공유) 불변.
- [x] 테스트 +1(kv-only 추출 happy-path, summary 빈 대화→account_insight 저장 검증) = 15. py_compile + feature-0002 회귀 0.
- worktree `ai/claude/account-insight-kv-source`(base eb9f986). 후속: 배포 + 실제 대화 e2e 검증.
## TASK-20260617T095122-ai-claude-account-insight-complete (current cycle) — 계정 인사이트 회상 완성 B′ (Major §12.3, 보안경계)
- TASK-...082131(Phase 1 shadow) 의 완성. outside-voice 2-lens(보안+제품가치) 재검토 → **Phase 1 만으론 목표 미달**(회상 모집단=전역 DB 스키마 지식, summary 미임베딩, user_confirm PII) + BLOCKER 발견 → B′ 적용. 정본 [DESIGN-account-insight-recall.md](DESIGN-account-insight-recall.md) §10.
- [x] **BLOCKER-A**: `_build_knowledge_context` content→text 키(INJECT 무동작 버그) + 주입 블록 "참고 데이터, 지시 아님" 펜싱(프롬프트 인젝션 완화).
- [x] **account_insight 추출 pass**: insight worker `run_account_insight_pass` — owner·비-fork·비-archived 대화 summary+kv → `llm_account_insight`(PII-free 프롬프트) → `source_type=account_insight` fact(대화-로컬, 전역 미공유) → 기존 임베딩 파이프라인. fingerprint 재추출 회피. flag `AGENT_ACCOUNT_INSIGHT_EXTRACT`(OFF).
- [x] **회상 개선**: account_insight allowlist(G3 1차, user_confirm 제외) + `_mask_prose`(G3 2차) + **벡터-only fail-closed**(min_sim 척도 혼동 버그 수정, MIN_SIM 0.75→0.55) + G4(conv_id 집합 재검증) + per-account opt-out(`__account__:<id>` kv).
- [x] **G1 fork 배제**: `core_conversations.forked_from_conversation_id`(alembic 0010 + 부트스트랩 멱등 ALTER) + fork 시점 `_mark_conversation_forked`(app.py) + 추출·회상 양쪽 `IS NULL`.
- [x] 테스트 14(account 격리·G1 SQL·G3 allowlist·G4·벡터-only·opt-out·_mask_prose·추출 가드) + feature-0002 회귀 0(2 skip) + py_compile.
- [x] outside-voice 2-lens SHIP-WITH-FIXES 흡수(REV-20260617T095122).
- **활성화 canary**: EXTRACT→RECALL(shadow)→INJECT 순, 전부 default OFF. 부수 R4/R5 별도.
- worktree `ai/claude/account-insight-complete`(base fe8b8a4).

## TASK-20260617T082131-ai-claude-account-insight-recall (이전 cycle) — 계정 스코프 cross-conversation 인사이트 회상 Phase 1 shadow (Major §12.3, 보안경계)
- 사용자 요청: "새 대화를 시작하면 기존 대화에서 진행한 사용자 인사이트가 누락됨 → 세션 간 문맥/인사이트를 어렴풋이라도 이어받도록". (특정 명칭 기억이 아니라 문맥 영속화.)
- 설계 정본: [DESIGN-account-insight-recall.md](DESIGN-account-insight-recall.md). outside-voice 2명(보안 NOT-SHIP→가드 시 SHIP-WITH-FIXES / 정합성 SOUND-WITH-FIXES) 검증 완료.
- 근본: 회상 scope 가 `conversation_id = ANY({현재,워커샤드,__global__})` 뿐 → 계정 타 대화 배제. `core_conversations.owner_account_id`(idx 존재)로 account→conv_ids 도출해 기존 pgvector 회상에 주입하면 신규 테이블 0 으로 해결. 임베딩 1536/text-embedding-3-small, 동일 DB agent_kb cross-schema JOIN(ADR-0027 schema-qualified).
- **Phase 1 (본 cycle, shadow·flag default OFF)**:
  - [x] `modules/account_recall.py` — `_load_account_scoped_conv_ids`(G2: owner NOT NULL·archived 제외·현재대화 제외·`__global__` deny) + `recall_account_conv_facts`(기존 벡터 회상 재사용, shadow).
  - [x] `_build_knowledge_context` account_id/conversation_id optional 파라미터 + shadow 호출(default no-op, INJECT flag OFF). 호출부(run loop) 전파.
  - [x] config flags 5종 전부 default OFF (`AGENT_ACCOUNT_INSIGHT_RECALL/INJECT/MAX_CONVS/TOP_K/MIN_SIM`) + `__all__`.
  - [x] 단위 테스트 10 (계정 격리·owner NULL 제외·현재대화 제외·`__global__` 제외·account 무효·PG 미가용·flag OFF no-op·min_sim/top_k·exclude 전파). 로컬 pytest 10/10 + feature-0002 전체 회귀 0(2 skip) + py_compile.
  - [x] kb_backend.py stale 주석 정정(vector(1024) Titan v2 → 1536 text-embedding-3-small).
  - [x] outside-voice 2-lens(보안+정합성) SHIP-WITH-FIXES 흡수(REV-20260617T082131): 신규테이블 0 단순화·G1~G4 가드·dim 1536 정정.
- **INJECT 활성화는 본 cycle 범위 밖** — G1(fork 표식)·G3(PII 값-패턴 마스커) 완료 후 별 cycle. 부수발견 R4(`_mask_rows` 호출처 0건)·R5(convo_search 계정 스코핑) 별도 처리 후보.
- worktree `ai/claude/account-insight-recall`(base 3c6ba13).

## TASK-0299 (current cycle) — MSSQL 사전 부하추정 (SET SHOWPLAN_ALL) — MySQL EXPLAIN 등가 (Major §12.3, REQ-20260617-0299)
- 사용자 요청: "assistant 요청 시 datasource 가 MSSQL 일 경우 쿼리 실행 부하 조치를 어떻게 구성했는지" → MySQL 은 EXPLAIN 으로 부하 예측하는데 MSSQL 은 미구현(`supports_load_estimate=False`, gate=일괄 차단/warn·off=무방어)임을 확인 → "MSSQL 에서도 부하 추정으로 효율적 쿼리 작동" 구현 요청. DESIGN-multi-datasource §11 M-4 의 SHOWPLAN 후속(P6 이월분).
- 근본: MSSQL 은 EXPLAIN 구문이 없음 → `SET SHOWPLAN_ALL ON` 으로 본 쿼리를 실행하지 않고 추정 실행계획을 받아 예상 처리 행수 산출(MySQL EXPLAIN 등가).
- [x] (AC-0562) dialects.py: `MSSQLDialect.supports_load_estimate=True` + `_showplan` runner(ON→sql 미실행→`finally` OFF, 세션 poison 방지 Codex-7) + `estimate_load_rows`(EstimateRows×EstimateExecutions 최대) + `gate_fail_closed_on_estimate_error=True`(M-4). MySQL EXPLAIN 파싱은 dialect 로 이관만(골든 0).
- [x] (AC-0562) tools.py: `_estimate_explain_rows` 엔진무관 wrapper(dialect 에 실행 콜백 주입, 계층 보존) + 게이트 `must_estimate` 재구조화 — 추정 실패 fail-closed 는 confirm_heavy 무관(Codex-6), 추정 성공 known-heavy 만 confirm override.
- [x] (AC-0563) tools.py `_tool_explain_query` MSSQL SHOWPLAN plan 요약 표시(`_format_mssql_showplan`) + 도구 description/프롬프트 엔진중립화.
- [x] (AC-0563) `bin/datasource-mssql-ro-bootstrap{,-multidb}.sql` 에 `GRANT SHOWPLAN`(데이터 비노출·추정 plan 만 → 최소권한 RO 양립) + 검증 라인.
- [x] 테스트: 신규 `test_mssql_load_estimate.py` 19 + 골든 `test_query_guard.py` 16 회귀 0 + 기존 `test_mssql_security_boundary.py`/`test_multi_datasource.py` 계약·golden 갱신. 로컬 PYTHONPATH 전 스위트 PASS(2 skip).
- [ ] make test 컨테이너 회귀 0 + ruff clean.
- [ ] outside-voice 적대 코드리뷰(세션 poison/fail-closed 우회/cross-engine 격리) 흡수.
- [ ] 머지(PR) → agent-core 3 이미지(web/ask-worker/insight-worker) 재배포. CHG/REV-20260617-0310.

## TASK-0289 (current cycle) — 수행시간 end-to-end 집계 + 내부 동작(activity) step + 큐 대기 단축 (feature-0003 TASK-0289 의 agent-core 면, Major §12.3)
- 사용자 보고(feature-0003 TASK-0289): 실측 45초인데 화면엔 25초 표시(내부 동작 집계 숨겨짐) + 내부 동작(단계별 DB동작 외) 미표현. agent-core 가 수행시간 측정·step 기록의 근원.
- 근본원인: 표시 `duration_ms` 가 `run_start`(모든 초기화 이후) 기준 → LLM 루프만 집계. step 은 tool 호출만 기록(activity 없음). worker 큐 유휴 폴링 tick 1~2s.
- [x] (P1) `_compute_duration_breakdown(queued_ms, agent_entry_perf, run_start, now_perf)` → `{queued/init/inference/total}`. `_run_agent_core` 진입 `agent_entry_perf` + `queued_ms_seed` 파라미터(run_agent→_run_agent_core 전파). 표시·KV·meta `duration_ms`=total, meta `duration_breakdown` 동봉.
- [x] (P1) worker(`modules/ask.py`)가 `ask_jobs.claim_ask_job` created_at(RETURNING 추가, len-guard)로 큐 대기 산출 → `queued_ms_seed`.
- [x] (P2) `_emit_activity` nested helper(맥락 로드/분석 준비/추론 라운드/결과 정리) `action='activity'`·`tool=''` step + `emit_index` 통합 step_index(tool step 도 emit_index 사용). `_writes_allowed`/예외 안전 skip.
- [x] (P4) `AGENT_ASK_WORKER_IDLE_POLL_SEC`(float, 0.5) 유휴 claim 폴링 분리 — `tick_sec`(reconnect) 불변.
- [x] 테스트: test_duration_breakdown.py 3 + test_ask_jobs.py created_at 2 + feature-0002 전체 회귀 0(2 skip) + py_compile.
- [x] outside-voice 적대 코드리뷰 흡수(REV-20260616-0302) — **SHIP(BLOCKER 0)**: emit_index 정합·TASK-0241 clobber 불변·queued_ms tz-safe(timestamptz)·_emit_activity 안전·activity 헬퍼 격리 전부 confirmed.
- [x] 머지(PR #288 → main 4178cf7) → ask-worker 재빌드(agent_core baked, repo-ask-worker-1 Up + `_compute_duration_breakdown`/`IDLE_POLL=0.5` 실측) → feature-0003 TASK-0289 PB-0008 PASS 와 함께 마감. CHG/REV-20260616-0302.

## 0. TASK-0255 (current cycle) — insight 연결 탄력성 (R1 로그 edge-trigger / R2 PG datasource_health / R3 control-plane bounded timeout)
- [x] **조사**: 급성 병목(연결대기 starvation)은 TASK-0247/0250 으로 이미 해소 — 라이브 실측 cycle ~2.6s(불안정 DS 7개+에도 fast-fail). 잔존 3건 발견.
- [x] **R1**: scan_failed 로그 edge-trigger(`_LAST_DS_SCAN_STATUS` + `_ds_scan_status_changed`, registry 동기 prune) — 상태 전이 시에만 WARNING(매-cycle 도배 ~20만 줄/2일 제거). `DatasourceCircuitOpen` 을 `_is_perm` 보다 먼저 분기.
- [x] **R2**: `agent_runtime.datasource_health` PG 영속(alembic `0006` + 부트스트랩 §6c + **명시 GRANT**) + `_persist_datasource_health`(soft, registry prune) + web `admin_list_datasources` `insight_health` 첨부 + admin.js "인사이트 스캔 상태" 행 → **연결불안정 vs 권한실패 구분**. 자격증명 비영속.
- [x] **R3**: control-plane bounded connect timeout(`AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC`=10, `_controlplane_connect_timeout` — MySQL control-plane(db.py) + KB PG(_pg_connect/_ro)). breaker 미적용(timeout 만). R3a cold-window 미채택.
- [x] 테스트 19개(`test_task0255_*`) + `make test` GREEN(ruff pass); **5-lens adversarial review SHIP_WITH_FIXES** — BLOCKER 5건 환각 기각, M-2(자격증명 로그)·M-1(메모리 prune)·MINOR 반영.
- [x] main 머지(PR #208, `a410986`) → agent/insight-worker/ask-worker/web 재배포 + PG 마이그 `0006`(superuser GRANT) → **런타임 검증 PASS**: 로그 도배 멈춤(24초 7→7), datasource_health 8행(불안정7 `circuit_open`/정상1 `ok`), 자격증명 컬럼 0, `_controlplane_connect_timeout()=10` baked, heartbeat status=ok ~2.67s. **PB-0008 PASS**(불안정/정상 "인사이트 스캔 상태" 구분 실증, feature-0003 TEST.md §4).

## 1. Current Status
- State: **TASK-0250 (연결 health 모니터 — background 사전판정으로 불안정 datasource 격리 완성) 구현 완료, 리뷰·배포 진행** — 신규 `modules/conn_health.py` 가 2단 probe(TCP 선검사+실제 DB connect+SELECT 1)로 per-datasource 연결 상태를 미리 유지, agent(`connect_with_retry` gate)·관리콘솔(사전계산 conn_status)이 즉시 읽어 한 datasource 불안정이 정상 datasource 요청을 막지 않음. 구 TASK-0247 in-process breaker 흡수·대체 (cycle: TASK-0250)
- State(이전): **TASK-0247 (데이터플레인 연결 격리 — bounded connect timeout + in-process breaker) 완료** [TASK-0250 으로 진화·대체]
- State(이전): **TASK-0230 (멀티 datasource 1:N — 제품 1개 ↔ 여러 datasource 참조) 완료** — 제품이 여러 datasource 에 바인딩될 수 있고, assistant 가 한 질문에서 tool 의 `datasource` 인자로 대상을 골라 datasource 별 (연결·allowlist·dialect) 격리 컨텍스트로 조회한다 + 제품 프롬프트 자동작성이 모든 바인딩 datasource 의 DB 를 인지 (cycle: TASK-0230)
- Owner: AI (본 cycle: agent_core `conn_health.py`(신규)/`db.py`(gate)/`config.py`/`datasources.py`/`ask.py`/`insight.py` + feature-0003 admin 표시)
- Priority: high
- Last Updated: 2026-06-16

## 1.1 Current Cycle
- [x] TASK-0290 (Minor §12.3 — conn-tristate TCP 선검사 timeout 2000→5000ms). 사용자 보고: "관리 콘솔 > 데이터소스 의 mysql-mv-qa-* 버튼이 연결 안 됨처럼 보이나 실제론 ~1700ms 느린 연결 → 빨강(불안정)으로 표시되어야". **라이브 진단(repo-web-1, docker exec probe 재현 + HTTP conn_status)**: 백엔드 classify 양호 — mv-qa 3개 TCP 193~195ms + DB 1749~1766ms → `classify`=unstable(빨강) 정확, 현재 HTTP `/api/admin/datasources` conn_status 도 unstable. 사용자가 본 회색은 **web 재시작 콜드 스타트(07:47Z) thundering herd 의 일시 TCP timeout→down 오판**(이후 복구). mysql-kr-an2-* 7개는 TCP 2003~2237ms(2000ms 임계 초과)→down 이며 5s 로도 timeout+DB errno=2003=**진짜 도달불가**(down 정확, 수정 대상 아님). **산출**: config.py `AGENT_CONN_TCP_TIMEOUT_MS` 기본 2000→5000 — 콜드/원거리 RTT spike 흡수해 연결 가능한 느린 서버를 unstable(빨강) 유지, 죽은 서버는 timeout 무관/5s timeout→down 정확. 30s 는 죽은서버 7개×워커4 점유로 모니터 라운드 지연(성능이슈) 기각, 5s 채택(사용자 "성능 이슈면 5초"). REV-20260616-0299 [SELF] Panel SKIPPED(보안/RBAC 무관 timeout 상향). 배포 web+ask-worker+insight-worker 재빌드(config = agent-core 3 이미지 baked). worktree `ai/claude/conn-tcp-timeout`.
  - [x] 배포·라이브 검증 PASS — 콜드 스타트(컨테이너 재시작) 후 HTTP conn_status: mysql-mv-qa-* **unstable**(빨강, 1744~1793ms)/mysql-kr-an2-* **down**(5s timeout errno=2003 진짜 도달불가, 정확)/gz-qa-kr healthy. 구 2000ms 의 콜드 down 오판 제거 실증(TEST.md TASK-0290, CHG-20260616-0300).
- [x] TASK-0250 (REQ-20260612-0250, **Major §12.3** — 연결 health 모니터: 불안정 datasource 격리를 background 사전판정으로 완성). 사용자 후속 보고(TASK-0247 배포 후에도 "한 연결 실패 시 정상도 대기") + 설계 제안(queue·timeout 100ms→×2→10s). **진단**: breaker 가 3 요청 실패 후 open(그 전 각 요청 10s×retry 점유) + 관리콘솔 연결확인이 `probe_datasource` 직접(breaker 미적용)+4-cap 세마포어+8s. **사용자 확정(AskUserQuestion 2회)**: 둘 다 적용 + 구조 AI 검토 → **Connection Health Monitor**(상태만, warm 연결 X). **산출**: ① `conn_health.py` background 모니터(daemon scheduler+worker pool+queue) **2단 probe**(TCP 100ms 선검사 + 실제 DB connect+SELECT 1 적응형 1s→10s), 성공 healthy/실패 unstable backoff. ② `connect_with_retry` 가 `should_fast_fail` gate + `record_foreground_result` 피드백(복구는 background → half-open trial 불요). ③ 관리콘솔 `admin_list_datasources` 사전계산 `conn_status` + admin.js 세마포어 lazy probe 폐기→즉시 표시. ④ ask-worker/web/insight-worker 각자 모니터 기동. 구 breaker 흡수(db.py 내부 제거, dead config 정리). **outside-voice 2-pass NOT-SHIP→SHIP-WITH-FIXES**(REV-20260612-0250: B1 TCP≠DB→2단 probe·B2·M1 dead config·M2 pool 기아·M3 SSRF rebinding[`_is_blocked_target`]·m1/m2/m3 흡수). **검증**: 신규 `test_conn_health.py` 21 PASS + make test 컨테이너 회귀 0 + ruff clean. flag `AGENT_CONN_HEALTH_ENABLED` 기본 ON. ANCHOR §1~§3 충돌 없음. worktree `ai/claude/conn-health-monitor`. 동시세션 0248·0249 선점→§13.1 재번호 0250.
- [x] TASK-0247 (REQ-20260612-0247, **Major §12.3** — 데이터소스 연결 불안정의 blast radius 를 각 연결별로 격리). 사용자 보고: "관리 콘솔에서 데이터소스 연결이 하나라도 불안정하면 제품 화면에서 나머지 정상 연결까지 결과가 느림 → 연결 이슈 범위를 각 연결별로 격리". **근본 원인**: data-plane 연결의 `connection_timeout`(MySQL)/`login_timeout`(MSSQL)이 쿼리 예산 `AGENT_TIMEOUT_SEC`(운영 300s)를 재사용 → 불안정 연결 1회 시도가 최대 300s 블록 + `connect_with_retry`×3 → ~900s. 운영 `AGENT_ASK_EXECUTION_MODE=worker` + 단일 ask-worker 직렬 처리 → 불안정 datasource 바인딩 job 1건이 worker 를 점유 → 정상 datasource 제품 job 큐 대기. **산출(db.py + config.py)**: ① `AGENT_DB_CONNECT_TIMEOUT_SEC`(기본 10s, `_dataplane_connect_timeout()`)로 연결 수립 상한을 쿼리 예산에서 분리(MySQL `connection_timeout`·MSSQL `login_timeout`; MSSQL 쿼리 `timeout` 은 `AGENT_TIMEOUT_SEC` 유지). control-plane(`datasource=None`) 미적용. ② per-datasource circuit breaker — `scope_key`(엔진+host+port) 기준 in-memory(`_BREAKER_STATE`+`threading.Lock`). **게이트(`_breaker_admit`)·실패기록을 `connect_with_retry` 경계에서 요청당 1회**(모든 런타임 datasource 연결이 이 경유 — false-open 증폭 차단, THRESHOLD=실패한 요청 수). 연속 `AGENT_DB_BREAKER_FAIL_THRESHOLD`(3) 회 **연결 수립 실패**(`_is_connect_breaker_failure` — connect-stage 만, deadlock 1205·인증 1045 제외) → open → `AGENT_DB_BREAKER_COOLDOWN_SEC`(30s) 동안 `DatasourceCircuitOpen` 즉시 raise(실제 connect 미호출). 쿨다운 후 **정확히 1개** half-open trial(`half_open_at` 토큰, 락 내 단일성·stale 회수) 성공 close/실패 re-open/비-연결실패 토큰해제. ③ `connect_with_retry` admit raise 로 breaker-open 재시도 0. 부기는 `_breaker_safe` 격리. tool 경로(`execute_tool`)는 기존 `conn_for` try/except 로 per-datasource 에러 surface(타 datasource 무영향). **outside-voice 2-pass 적대 리뷰 NOT-SHIP→흡수→SHIP-WITH-FIXES**(REV-20260612-0247: B1 thundering herd·B2 stuck-open·M1 retry 증폭·M4 분류오염·m1 누수·m2 노출·잔여 흡수). **검증**: 신규 `test_db_circuit_breaker.py` **22**(8스레드 단일trial 동시성 포함) + **make test 컨테이너 회귀 0** + ruff clean. 사용자 확정(AskUserQuestion): Breaker + timeout 분리. flag `AGENT_DB_BREAKER_ENABLED` 기본 ON. ANCHOR §1~§3 충돌 없음(런타임 신뢰성 개선·모듈 경계 무변경). worktree `ai/claude/ds-connect-isolation`(base f9d8207). 동시세션 `task0244-ds-picker-status` 가 TASK-0244 선점 → §13.1 재번호 0244→0247 (동시세션이 0244·0245·0246 선점).
- [x] TASK-0230 (REQ-20260611-0230, **Critical §12.3** — 멀티 datasource 1:N: 제품 ↔ 여러 datasource 참조 [cross-feature, agent-core 측]). 사용자 요청: "assistant 가 답변하려면 여러 데이터소스·DB 에 접근해야 하는데 단일 datasource 만 가능 → 관리 콘솔 > 제품 > 데이터소스에서 여러 데이터소스도 참조하도록". 기존 멀티 datasource(TASK-0185~0226)는 product↔datasource **1:1**(WebProducts.DatasourceKey 단일 컬럼)이었다. **agent-core 산출**: ① `agent_core._resolve_product_datasources`(복수) — ≥2 바인딩 시 datasource 별 dict(`_label`/`_allow_schemas`/`_is_primary`) 반환, 0~1 은 [](기존 `_resolve_product_datasource` 단일 경로 보존=동작 0 변경). `_product_datasource_keys`(join 우선·primary 폴백), `_datasource_allow_schemas`(차원 격리, **fail-closed** — 차원 컬럼 부재 시 [] 반환해 전체목록 broadcast 교차노출 차단, REV-0230 MAJOR-2). ② `tools.py` `_DatasourceRouter` — run-scoped 라벨→{ds, lazy conn} 맵 + `activate(label)` 이 그 datasource 의 allowlist·engine·default_db ContextVar 를 **단일 단위로** 활성화(보안 게이트 기준). `execute_tool` 이 tool 인자 `datasource` 로 대상 선택→`conn_for`+`activate` **동일 라벨 lockstep**(연결↔allowlist 불일치 창 없음)→handler→primary 복원. 미바인딩 라벨 거부. `build_tool_definitions_for_datasources`(각 도구에 datasource enum 주입, 원본 불변 깊은복사). `set/get/reset_active_ds_router`(ContextVar, finally reset). ③ run-loop 통합 — ≥2 면 라우터 등록 + 다중연결 lazy(primary 즉시) + grounding 에 "ACCESSIBLE DATASOURCES"(라벨·엔진·접근DB, 좌표/비번 비노출) 주입(사용자 요청: 어시스턴트가 접근 가능 datasource DB 인지) + finally `close_all`+reset. ④ `insight.py` `_discover_mssql_databases` — datasource 차원(WebProductDatabases.DatasourceKey) 우선 + primary/join 바인딩 union 폴백. **검증**: 신규 `test_product_multi_datasource.py` 15(라우터 격리·lockstep·fail-closed·enum 주입·단일경로 무변경) + feature-0003 `test_product_multi_datasource_api.py` 7 + make test 컨테이너 **회귀 0**(F/E 0) + ruff clean. **outside-voice 적대적 보안 리뷰(REV-20260611-0230) BLOCKER 0** — 핵심 격리 HOLD(연결·allowlist·engine 단일 라벨 활성·tool 순차·게이트는 항상 활성 datasource 것). MAJOR-1(migration loud+검증)·MAJOR-2(allow_schemas fail-closed)·MAJOR-3(resolve 실패 silent 강등 금지) 흡수. flag `AGENT_MULTI_DATASOURCE_ENABLED` OFF + 단일 바인딩 = 동작 0 변경. worktree `ai/claude/product-multi-datasource`(base e93b181). [[feedback_outside_voice_for_rbac]] 정합.
- [x] TASK-0226 (REQ-20260611-0226, **Major §12.3** — MSSQL insight-worker per-DB 스캔 커버리지: 권한 이슈로 탐색 불가한 DB 해소 + 가시화). 사용자 요청: "제품에서 선택된 `접근 가능 데이터베이스` 를 대상으로 스캔하되, 각 DB 연결 중 권한 이슈로 탐색이 불가능한 부분을 해소". **근본 원인**: insight-worker 는 [`_discover_mssql_databases`](../src/modules/insight.py)로 datasource 에 바인딩된 제품들의 접근가능 DB(`WebProductDatabases`) union 을 올바르게 발견하지만, 그 각 DB 로 `connect_with_retry(database=db)` 재연결 시 RO 로그인이 **단일 DB 에만** USER/GRANT 돼 있으면(기존 `bin/datasource-mssql-ro-bootstrap.sql` 은 단일 `TARGET_DB` 템플릿) 'Login failed'(18456)/'Cannot open database'(916) 로 막혀 `run_insight_cycle` 의 per-DB `except` 가 **조용히 skip** → 등록 DB 중 일부만 인사이트 생성되고 운영자에게 누락이 안 보였다. **산출**: ① `modules/insight.py` — `scan_report` 에 `db_targets`(발견 DB 수)/`db_failed`(연결·스캔 실패 수) 누적 + per-DB `except` 에서 권한거부 패턴(login failed/cannot open database/permission/denied/18456/916/229/297) 감지 시 진단 힌트(부트스트랩 SQL 재실행 안내) 로깅 + `db_failed>0` 면 status='degraded'(publish_failed 와 동일 가시화 정책) + heartbeat KV(`insight_worker_last_db_targets`/`_db_failed`) + payload 노출. ② `bin/datasource-mssql-ro-bootstrap-multidb.sql` 신규 — 한 공유 RO 로그인을 제품 접근가능 DB **전체**에 USER+db_datareader 멱등 부트스트랩(커서 순회, QUOTENAME 인젝션 차단, 시스템 DB 제외, 쓰기역할 제거 hardening, 0단계 서버 전역 prereq 검증). 기존 단일-DB 스키마 GRANT-only 템플릿과 **상호 배타**(보안 trade-off 사용자 명시 승인 — schema 격리 대신 DB 단위 db_datareader). ③ 발견 로직·런타임 allowlist(tools.py 3-part catalog 대조)는 **이미 데이터소스/제품 접근가능 DB 기준**이라 변경 불요(확인). **검증**: pytest 신규 `test_mssql_perdb_coverage.py` 8 + 관련 회귀(three_tier/degraded_backoff/security_boundary/multi_datasource) 131 PASS, 회귀 0 + py_compile. **MySQL 단일 datasource(db_targets=0) 동작 0 변경.** worktree `ai/claude/mssql-perdb-grant-coverage`(base 14334ab). ANCHOR §1~§3 충돌 없음(LLM 재생성 순서 무관 — 발견 커버리지·권한·가시화만).
- [x] TASK-0223 (REQ-20260611-0223, **Major §12.3** — MSSQL database-aware 3계층 insight + 제품 프롬프트 자동작성 실데이터 정합 [feature-0003 주관, agent-core 교차변경]). MSSQL 은 database.schema.table 3계층인데 insight-worker 가 `dbo` 단일 DB 만 스캔 + fact_key 에 database 누락 → 제품 등록 DB(`dk_data_release` 등)와 매칭 불가였다. **agent-core 산출**: ① `config.py` `_ACTIVE_DATABASE` ContextVar + `set_active_database`/`get_active_database` + `ds_object_suffix`(active database 있으면 3계층 `{db}.{schema}.{table}`, 없으면 2계층 — `ds_fact_key` 시그니처 불변=write·read-back·grounding 3자 정합 보존; set_active_datasource 가 datasource 전환 시 database 리셋). ② `insight.py` MSSQL multi-database 스캔(`_discover_mssql_databases` 제품 등록 DB 기반, DB별 `connect_with_retry(database=db)` 재연결 + `set_active_database`, 권한밖 DB 연결실패 격리) + suffix 조립부 전수 `ds_object_suffix` 치환(table_insight/schema_insight/table_fp/schema_fp/*_refresh_at) + `_build_insight_object_maps`/read-back 을 `object_key`(database 포함 유일) 키로 전환(cross-DB 동일 `dbo.<table>` 충돌 livelock 방지). ③ `utils.py` `_infer_rag_object_from_fact` 3계층(database.schema.table) 파싱 + object_key 에 database 접두(유일성). ④ `schema.py` bootstrap 2곳 `ds_object_suffix` 치환(2계층 누락 수정). ⑤ `agent_core.py` `_insight_object_group` — grounding(`_load_schema_list`) grouping 을 MySQL=schema/MSSQL=database.schema 로 정합(table_insight↔schema_insight desc 매칭). **검증**: pytest 444 passed/2 skipped(신규 `test_mssql_three_tier_insight.py` 13, 회귀 0) + 라이브(MSSQL 제품 60테이블 grounded, ask-worker grounding 정상). 적대적 리뷰 4결함 수정(REV-20260611-0223). worktree `ai/claude/feature-0003-agent-web-ui`(base c769612). **MySQL 2계층 byte-identical(active_database=None) — 회귀 0.** 잔재: 구형식 2계층 fact_key(키 마이그레이션 진행 중).
- [x] TASK-0208 (**Minor §12.3** — "전체 N행 미리보기" 오링크: 비-결과 분석표 false-positive). `_collapse_large_tables`→`_match_csv_for_table` 의 컬럼수 폴백(2순위)이 LLM 이 손으로 쓴 분석·요약 표(쿼리 결과 아님)에도 컬럼수만 우연히 같은 무관 CSV 를 붙여, 클릭 시 frontend 값 가드가 "결과 파일이 미리보기와 일치하지 않아…" 422 토스트로 거부하던 오링크. **수정**: 표에 식별 토큰이 **있는데도 어느 CSV 와도 overlap 0** 이면(=쿼리 결과 아님의 음성 증거) 폴백 미적용·링크 생략. 폴백은 식별 토큰이 **아예 없는** 측정값-전용 표에만 한정(TASK-0174 회귀 보존). 회귀 테스트 2(분석표 링크 생략 + 다중표 used[] 슬롯 보존), 수정 전 코드에서 신규 테스트 실패 교차검증. outside-voice 적대 리뷰 SHIP-WITH-NITS(BLOCKER 0, REV-20260611-0208). 순수 백엔드(app.js 무변경)→CHECK#13 N/A. worktree `ai/claude/preview-link-nonresult`(base 4c34363). 잔여=ask-worker 재배포.
- [x] TASK-0193 (REQ-20260610-0193, **Major §12.3** — 멀티 datasource Stage 2 P5: Dialect 어댑터). tools.py introspection/sample SQL 을 engine 별 dialect 로 추상화. **산출**: `modules/dialects.py`(MySQLDialect 골든 그대로 + MSSQLDialect 동일 컬럼순서 T-SQL) + tools.py 8사이트 `_dialects.active()` 치환 + config `_ACTIVE_DATASOURCE_ENGINE`+set_active_datasource(engine=) + agent_core run-wide 엔진(run_agent finally 해제). **outside-voice SHIP-able BLOCKER 0**(REV-20260610-0193): MySQL 골든 byte-identical·MSSQL 컬럼순서·P3 격리 유지. MAJOR M1(ContextVar finally 예외안전) 흡수, MINOR m3(시스템스키마 필터 MySQL방언)=P6 이월. make test **318 passed**(신규 6, 회귀 0)+ruff clean. **보안 게이트는 MySQL 방언 — P6 전 MSSQL 활성화 금지(shadow).** worktree `ai/claude/multi-datasource-p5-dialect`(base 36bf285). 잔여=P6 보안·P7 통합+재게이트.
- [x] TASK-0192 (REQ-20260610-0192, **Major §12.3** — 멀티 datasource Stage 2 P4: MSSQL 드라이버 + 연결 디스패치). engine='mssql' datasource 연결 인프라(방언/보안 P5/P6 이월). **산출**: requirements `pymssql>=2.2.0`+sqlglot `<28` pin / db.py `_pymssql` import + `_connect_mssql`(1433, M-1) + connect() engine 디스패치 / `_collect_cursor_result` 크로스엔진(`description`, mysql 등가) / probe engine 분기. make test **312 passed**(신규 P4 5, 회귀 0)+ruff clean, pymssql-2.3.13 설치 확인. REV-20260610-0192 [SKIPPED:driver-infra](보안 표면 0, MSSQL 보안=P6·종합 outside-voice=P7). flag OFF shadow. worktree `ai/claude/multi-datasource-p4-mssql`(base 2646cbb). 잔여=P5 Dialect·P6 보안·P7 통합+재게이트.
- [x] TASK-0191 (REQ-20260610-0191, **Major §12.3** — 멀티 datasource P3: insight_worker per-datasource). insight fact 키를 datasource 차원으로 분리해 grounding 교차노출 차단(Codex-3) + worker datasource 순회. flag OFF=무접두 동작 0 변경. **산출**: config ContextVar+ds_fact_key/like/strip/scope_name(write·read-back·grounding 3자 정합 단일소유=livelock 방지) / insight.py 키빌드 18곳 치환+datasource 순회(연결실패 격리·스캔KV scope·scan_report 누적) / agent_core grounding ds 필터(not_like + set_active_datasource 직전·finally 해제) + M2 MySQL fallback 가드. **outside-voice subagent SHIP-ABLE BLOCKER 0**(REV-20260610-0191): livelock PASS(동일변수)·보안 PASS(PG ds-스코프)·flag OFF PASS. MAJOR(scan_report 누적)·M2 흡수, MINOR(kb_retrieval=기존 결함) 이월. make test **307 passed**(신규 4, 회귀 0)+ruff clean. worktree `ai/claude/multi-datasource-p3`(base 6449b75). 잔여=Stage 2 MSSQL.
- [x] TASK-0190 (REQ-20260610-0190, **Major §12.3** — 멀티 datasource P2: multi-MySQL Web UI). P1 의 admin datasource API 를 관리 콘솔 UI 로 노출 + 연결테스트 + 대화 datasource 라벨. **산출**: `db.probe_datasource`(flag 무관 연결테스트, errno-only 비유출) + `POST /api/admin/datasources/{key}/test`(console.access, 등록 키만→SSRF 불가) + `_list_products` datasource_key 노출 + admin.js(loadAdminData datasources fetch + renderProductDetail datasource select·연결테스트, console.manage 게이트) + app.js(product 배지) + CSS + 캐시버스터. make test **302 passed**(신규 probe 2, 회귀 0)+ruff clean+node --check. **outside-voice subagent 보안 리뷰 PASS-WITH-NITS BLOCKER 0**(REV-20260610-0190): SSRF 구조차단·errno-only·authz 정상, MINOR 2 수용. 권한 카탈로그 신규 0. cross-feature(0002 probe+0003 UI). worktree `ai/claude/multi-datasource-p2`(base f299125). 잔여(P3): insight per-datasource.
- [x] TASK-0187 (REQ-20260610-0187, **Critical §12.3** — 멀티 datasource P1: multi-MySQL 레지스트리 + 연결 디스패치 + 보안경계). ADR-CORE-0003 의 Stage 1 첫 구현. assistant 가 product 별 다른 MySQL datasource 분석. flag `AGENT_MULTI_DATASOURCE_ENABLED` 기본 OFF → 동작 0 변경. **구현 개선**: 기존 `WebProducts` 에 `DatasourceKey` 바인딩 → product RBAC·allowlist 자동 재사용(대화→product→datasource), 별도 테이블·PG 마이그레이션 0. **산출**: config `DATASOURCES`(.env named credential, 좌표·비밀번호 DB/payload 비저장)+flag+마스킹 / `db.connect(datasource=)` flag-게이트 라우팅 / `agent_core._resolve_product_datasource` 단일 chokepoint(in-process+ask-worker) / web admin list·set 엔드포인트(console.manage·audit). insight 는 P3 이월. **보안경계(security-first)**: datasource 접근=product.access(연결 전 enforce), allowlist 자동 datasource-scope. **outside-voice 적대적 보안 리뷰(REV-20260610-0187 SUBAGENT, Codex /tmp 오류→subagent fallback, NEEDS-TWEAK BLOCKER 0) M-1/M-2/N-2 흡수**: default_db allowlist 우회→database=None(M-1), 미등록 키 fail-open→fail-closed(M-2), DS_USER root 폴백 금지(N-2). make test **297 passed/2 skipped**(신규 15, 회귀 0)+ruff clean. RBAC 카탈로그 신규 0. 잔여(P2): CRUD UI·선택기. worktree `ai/claude/multi-datasource-p1`(base ea0746b). [[feedback_outside_voice_for_rbac]] 정합.
- [x] TASK-0185 (REQ-20260610-0185, **design-only** — 멀티 datasource 롤아웃 시퀀싱 결정 기록). TASK-0183 plan-eng-review/Codex 가 남긴 미해결 결정 3건(§4 Q6/Q7/Q8)을 사용자 결정으로 확정. **(Q6/Q8) multi-MySQL 먼저** — Stage 1(P1~P3) MySQL 전용, MSSQL 은 Stage 2(P4~P7, RBAC outside-voice 재게이트). **(Q7) 보안경계 연결과 동시** — datasource RBAC + datasource-스코프 allowlist + per-datasource RO 자격증명이 P1 에(flag≠권한검사, Codex-4). 반영: DESIGN §4 resolved + §5 Stage 1/2 재구성 + §10 갱신 + ADR-CORE-0003. 잔여(Stage 2): §4 Q1~Q5. REV-20260610-0185 [SKIPPED:decision-recording]. 코드/RBAC/스키마 mutation 0. worktree `ai/claude/multi-datasource-decisions`(base b4e52b5). 동시세션 TASK-0184 충돌→0185.
- [x] TASK-0183 (REQ-20260610-0183, **Critical §12.3 — design-only** — 멀티 datasource 설계 2차 검토: plan-eng-review + Codex cross-model). TASK-0182 설계의 엔지니어링 매니저 4섹션 리뷰 + **Codex cross-model outside voice**(REJECT, BLOCKER 4+MAJOR 5) 수행 후 발견을 DESIGN 에 직접 반영. **신규 핵심**: (Codex-2 보안결함 정정) `db_datareader+DENY` 가 allowlist 와 양립불가 → **전용 role 에 허용 view/object 만 GRANT SELECT** 본문 정정. (Codex-1) AST 추출도 무자격/view/ownership chaining 우회 → `datasource_id+catalog+schema+object`. (Codex-3) insight 격리가 fingerprint 키에만 → fact 스코프 교차노출. (Codex-4) 보안경계 P1 뒤늦음. (Codex-6) confirm_heavy LLM 자기우회 + fetchall 무제한. Claude eng: 단일 canonical AST(A2/C1)·pool cap·insight stagger. **반영**: DESIGN §1·§3.2·§3.3·§3.4·§3.6·§4 정정 + §10 신설 + GSTACK REVIEW REPORT. **미해결(구현 착수 시)**: P1 시퀀싱(사용자 보류)·보안경계 P1 전진·scope 정당화 — §4 Q6/Q7/Q8. 코드/RBAC/스키마/시크릿 mutation 0 — 문서만. worktree `ai/claude/multi-datasource-eng-review`(base e5a4591). [[feedback_outside_voice_for_rbac]] 정합.
- [x] TASK-0182 (REQ-20260610-0182, **Critical §12.3 — design-only** — 멀티 datasource(MySQL·MSSQL) 데이터평면 설계). 사용자 질문("assistant·insight_worker 가 단일 MySQL 만 바라보는데 여러 엔진의 DB 를 바라보게 가능?")의 타당성·범위 규명(AskUserQuestion: 범위=멀티 datasource 동시, 엔진=MySQL·MSSQL) 후 **설계 문서만** 산출. **산출**: `docs/DESIGN-multi-datasource.md`(3계층 결합 규명 + datasource 레지스트리·드라이버 디스패치·Dialect 인터페이스·보안게이트 멀티방언·LLM grounding·insight per-datasource·RBAC/시크릿·P0~P6 롤아웃) + ADR-CORE-0002(A 네이티브 dialect-adapter 채택, dbhub MCP 기각) + **outside-voice 적대적 설계 리뷰 REV-20260610-0182**(NEEDS-TWEAK, BLOCKER 3+MAJOR 4 — "sqlglot dialect 주입만으로 가드" 전제 거짓 규명: 진짜 격리는 tools.py 정규식 allowlist[MSSQL 식별자 우회 B-1]+RO GRANT[MSSQL 등가 미설계 B-2]+T-SQL 위험구문 커버 0[B-3]). 전 발견을 DESIGN §2.3.1/§3.2~3.4/§3.6/§4/§5/§9 에 design-fold. **구현 이월**(자체 다중 cycle + plan-eng-review + RBAC outside-voice). 코드/RBAC/스키마/시크릿/엔드포인트 mutation 0 — 문서만. worktree `ai/claude/multi-datasource-design`(base 308c6f2). [[feedback_outside_voice_for_rbac]] 정합.
- [x] TASK-0172 (REQ-20260609-0172, **Major §12.3** — 무거운 쿼리 자가규제: EXPLAIN 사전 게이팅 + per-query cap). 라이브 인시던트("분기 대화 처리중 단계 안 진행" = 5~6분 대용량 집계 쿼리; ask-worker 는 정상 완주, frozen step 착시 + collateral 포화)의 자가규제 대응. **방향 전환 이력**: 사용자가 self-interrupt(mid-query KILL)를 요청 → outside-voice 설계리뷰가 RECONSIDER("LLM 판단만" 내부모순 + 단일 db_conn KILL 후 깨짐 + LLM 자발중단 의존 + agent_ro processlist 관측불가) → 사용자 결정으로 **EXPLAIN 사전게이팅+cap 으로 전환**(self-interrupt 보류, DESIGN-self-interrupt.md §10~§11). **산출**: `modules/tools.py`(`_estimate_explain_rows` rows×filtered/100 추정 + `_apply_query_cap` MAX_EXECUTION_TIME + `_tool_execute_sql` gate/warn/off 분기 + `confirm_heavy` override) + `modules/config.py`(`AGENT_QUERY_GUARD_MODE`/`_EXPLAIN_ROWS_WARN`/`_MAX_EXECUTION_MS`). flag 기본 off=무변경, canary off→warn→gate. outside-voice 2회(설계 RECONSIDER + diff FIX-BEFORE-ENABLING-GATE, M1/M2/m3/m4 흡수, REV-20260609-0172). make test 회귀 0(신규 test_query_guard 15). worktree `ai/claude/self-interrupt`. **이월**: 정상 무거운 쿼리의 UX·collateral 포화는 replica 라우팅(인프라).
- [x] TASK-0169 (REQ-20260609-0168, **Critical §12.3** — out-of-process ask-worker 실행모델, agent-core 측). 정본 plan/checklist 은 feature-0003 TASK-0169(§2.1 PLAN-APPROVED). agent-core 산출: `alembic/versions/20260609_0003_ask_jobs.py`(큐 테이블) + `modules/ask_jobs.py`(단일문 atomic claim B2 / 단일문 slot enforce M5 / lease fencing B3 / stale sweep / cancel-pending / active_inline_paths / 멱등 `_ensure_ask_jobs`) + `modules/ask.py`(`run_ask_worker_loop` — 시간기반 heartbeat 스레드로 긴 LLM step false-positive requeue 차단, lease 박탈 시 KV cancel fencing, 고아 inline reaper 활성 job 제외, boot self-reclaim, SIGTERM graceful) + `scripts/healthcheck_ask_worker.py` + `agent_core.py`(`run_agent`/`_run_agent_core` optional `run_id`, `--ask-worker` dispatch) + `config.py`(`AGENT_ASK_*`, stale 기본값을 run_timeout+180 으로 동적 산출 — make test 가 AGENT_TIMEOUT_SEC=300 환경 false-positive 포착·수정) + `memory.py`(`set_run_status` run_id→status M4, `_clear_cancel_request` run_id-scoped MJ-2). 테스트 3파일(test_ask_jobs/test_ask_worker/test_clear_cancel_runid). make test 244 pass·회귀 0. **outside-voice 적대적 리뷰 흡수**(REV-20260609-0168). worktree `ai/claude/ask-worker`.
- [x] TASK-0163 (REQ-20260609-0163, **Major §12.3** — LLM 사용량 회계 복구: 메인 추론 계측 + 실제 모델 해소 + 계정별/역할별 집계). **증상(사용자 보고)**: 관리 콘솔 > 감사 > LLM 사용량에서 모델별이 `edge`·`시스템`만 보이고 claude 계열·계정별·역할별 집계가 없음. **라이브 진단(PG `agent_runtime.llm_usage` 19,602행, 06-02~06-08)**: 전부 `model='edge'`, task=table_insight(16594)/schema_insight(2958)/topic(27)/classify(23) — insight worker + 보조뿐, 99.7%가 `conversation_id='__insight_worker__'`(owner NULL→계정별 표 `(시스템)`). **사용자 대화 메인 추론 LLM 호출이 단 1건도 기록 안 됨.** **근본 원인 3**: (RC1 핵심) 메인 agentic loop 호출 `_call_llm`(agent_core.py:1699, 호출처 2007 단일)이 `client.chat.completions.create()` 의 `.choices[0].message` 만 반환하고 `response.usage` 를 버려 `_record_llm_usage` chokepoint 를 우회 → 메인 추론(최대 토큰)이 회계 누락(계정별/역할별이 비던 진짜 이유). classify(`llm_classify_origin_shift`)/topic(`llm_generate_topic`)만 llm.py 경유로 기록. `llm.py:llm_plan` 은 죽은 코드(호출처 0). (RC2) `_record_llm_usage` 가 요청 별칭(`edge`/`core`/`auto`)만 `model` 에 저장, 실제 서빙 모델(`resp.model`, LiteLLM proxy 가 별칭→Bedrock model 해소) 미기록 → claude 식별 불가. (RC3) `admin_llm_usage` 에 by_role 부재 + 계정 숫자 ID. 역할은 MySQL(`WebAccounts.RoleId`→`WebRoles.Name`), usage 는 PG → cross-DB. **산출**: (1) alembic `0002_llm_usage_resolved_model`(down_revision 0001_baseline, `ADD COLUMN IF NOT EXISTS resolved_model varchar(128)`, 멱등 offline SQL) + bootstrap `agent_runtime_schema.sql` parity(백필 불요, NULL 허용). (2) `_record_llm_usage` 가 `served=str(getattr(resp,"model",""))[:128] or None` 을 `resolved_model` 컬럼에 INSERT(best-effort·per-call conn 불변). (3) `_call_llm` 이 응답 직후 `_record_llm_usage(model, "agent", response, conversation_id, run_id)` 호출(self-guard 위 try/except 이중) + `agent_core` import 에 `_record_llm_usage` 추가. **race 수정(outside-voice B1)**: `/api/ask` 는 agent 를 in-process(`asyncio.to_thread`)로 실행([[TASK-0159]])하므로 cfg 전역(MEMORY_CONVERSATION_ID/CURRENT_RUN_ID)은 동시 ask(WEB_PARALLEL_LIMIT) 간 덮어써져 토큰이 잘못된 계정/역할에 귀속될 수 있음(메인 추론=최대 토큰이라 노출 큼). 따라서 `_record_llm_usage`/`_call_llm` 에 `conversation_id`/`run_id` optional 인자 추가 → 메인 추론은 `run_agent` 의 정확한 cid/run_id 를 **명시 인자**로 전달(thread 격리·race-free). helper(classify/topic 등 소량 호출)는 미전달=cfg 전역 fallback(기존 동작 유지·follow-up). 초기 안에 있던 `cfg.MEMORY_CONVERSATION_ID=cid` 직접 set 은 race window 확대라 제거. (4) `admin_llm_usage`: by_model `COALESCE(resolved_model, model)` 집계(model+resolved_model 둘 다 노출), by_account 를 이미 열린 MySQL conn 으로 `WebAccounts LEFT JOIN WebRoles` username·role enrich(MySQL conn 추가 개방 0), `_aggregate_usage_by_role` 순수 헬퍼 Python 폴딩(account None→`(시스템)`, role None→`(역할 없음)`, total_tokens desc), 응답에 `by_role`. 권한 `console.usage.read`(admin) **무변경 — RBAC 카탈로그 0**. (5) admin.html 역할별 표(#usageByRole) + admin.js `tbl(rows,cols)` fmt 에 row 전달, by_role 렌더·계정 username·역할·모델 `별칭 → 해소` 표시, 캐시버스터 `?v=20260609-usage-roles`. (6) `tests/test_llm_usage_record.py`(7: resolved_model/명시 인자 우선/cfg fallback/cfg 귀속/None/no-op/PG 실패 삼킴) + `tests/test_call_llm_records_agent_task.py`(2: agent task+명시 conv/run 기록/실패 비전파). **검증**: make test(컨테이너) **215 passed/5 skipped**(신규 9 PASS, 회귀 0) + ruff All passed + py_compile/node --check + **outside-voice 적대적 diff 리뷰 NEEDS-TWEAK→PASS, BLOCKER 1 흡수(REV-20260609-0163)**. RBAC/secret/endpoint 신규 0, 스키마 additive only. **한계(문서화)**: 계측은 앞으로의 호출만(과거 19,602행 소급 불가), claude 물리 모델 구분은 LiteLLM 이 `response.model` 에 별칭 반환 시 제한적(실 claude 사용 후 검증, 필요 시 feature-0007 LiteLLM config follow-up). worktree `ai/claude/llm-usage-metering`(base 353f062). cross-feature(feature-0002 계측/마이그레이션/테스트 + feature-0003 엔드포인트/프론트).
- [x] TASK-0160 (REQ-20260608-0160, **Major §12.3** — 중단 run 의 고아 tool_use → LLM payload 400 방지). **증상(사용자 보고)**: 웹 DBA 챗 재질의 시 `LLM 호출 오류: Error code: 400 ... BedrockException ... messages.N: tool_use ids were found without tool_result blocks immediately after: tooluse_... Each tool_use block must have a corresponding tool_result block`. **근본 원인**: `/api/ask` 는 agent 를 web 프로세스 안 in-process(`asyncio.to_thread`)로 실행([[TASK-0159]]). web 재배포가 ask 를 `execute_sql` 도중 죽이면 assistant 의 `tool_use` 블록만 `core_messages` 에 저장되고 대응 `tool_result`(tool role) 전에 종료 → 재생성 시 그 고아 tool_use 가 LLM payload 에 실려 Anthropic/Bedrock 이 400 거부 → 대화 영구 사용불가. `_normalize_history_rows` 에 페어링 가드가 있었으나 **미완성** — assistant(tool_calls)를 먼저 `normalized` 에 append 한 뒤 다음 행이 tool 이 아니면 `pending_tool_ids.clear()` 만 하고 이미 추가된 고아 assistant 를 회수하지 못함. **수정(agent_core.py `_normalize_history_rows` 단일 함수)**: assistant(tool_calls) 턴을 버퍼링(`pending_assistant`+`pending_tool_ids`+`pending_tool_rows`)해 턴 종료(다음 비-tool 행/다음 tool_use assistant/EOF) 시 `_flush()` 가 **모든 tool_use id 해소 시에만 commit, 하나라도 미해소면 턴 전체(assistant+부분 tool 결과) drop**. 매칭 없는 고아 tool 행도 drop(기존 유지). 윈도우 경계(`_assemble_core_messages` 의 `normalized[-max:]`) 절단 고아도 함께 무해화. **즉시 해소**: 라이브 대화 `20260608025216-3014b095` 의 고아 msg 1147(+에러버블 1184) 삭제(전수 점검 잔존 고아 0). **회귀 테스트**: `tests/test_history_tooluse_sanitize.py` 6 case(고아 턴/부분 턴/EOF 경계/고아 tool 행/유효 멀티턴/마커 보존) PASS. 검증: py_compile / pytest 6 passed / verify-completion / REV-20260608-0160. RBAC/schema/secret/endpoint 무변경, 단일 함수 read 경로 정합화.

- [x] TASK-0151 (REQ-20260605-0151, **Major §12.3** — DB 조회 사용자 경험 개선: 환각·반복질문·첨부무시·사고미확장 해소). **증상(사용자 보고 6건)**: ① 한 번에 요청 미인지 ② 앞서 말한 내용을 반복 질문 ③ 복잡한 요청은 사용자가 다 설명해야 함 ④ 제안 쿼리/결과가 실제 DB와 다름(환각) ⑤ 쿼리 리뷰용 파일을 첨부해도 자기 DB 기준으로만 답함 ⑥ 시킨 대로만 하고 스스로 사고를 확장 안 함. **라이브 규명(3 subagent + 직접 검증)**: (③④ root cause) `_load_schema_list`/`_load_relevant_table_insights`(="KNOWN SCHEMAS authoritative" grounding 주입원)가 05-27 cutover 로 DROP 된 MySQL `AgentMemoryFactEntries`/`AgentMemoryTexts` 만 조회 → 예외 삼킴 → **grounding 이 항상 비어버림**. 실데이터는 PG `public.fact_entries`(table_insight 765 + schema_insight 15)에 실재하나 사용자 경로에 한 번도 주입 안 됨. 게다가 base SYSTEM_PROMPT 이 "이 (빈) 섹션을 primary 로 쓰고 search/verify 하지 말고 바로 SQL 써라" → grounding 0 상태에서 테이블/컬럼 환각. (② root cause) `_assemble_core_messages` 의 50-메시지 윈도우를 tool 결과가 ~62% 점유 → 초기 user 의도 탈락 + `_should_refresh_origin_request` 가 인사/메타를 origin 으로 고정/오분류. (⑤) 배선은 정상이나 prompt 가 "내 DB 조회"만 강제 + 첨부 리뷰 의도 분기 부재 + text cap(20) `ORDER BY Id ASC` 로 최신 첨부 무음 누락. (①⑥) clarification 도구 부재 + prompt 가 탐색/검증/사고확장을 구조적으로 억제("answer, not explore / limited step budget / verify 금지"). **산출 4건**: (FIX1) `agent_core._global_insight_rows_pg`/`_extract_schema_desc`/`_kb_read_is_pg` 신규 + `_load_schema_list`/`_load_relevant_table_insights` 가 `AGENT_KB_READ_BACKEND=postgres` 시 PG(`_pg_connect_ro`) 정본 조회, 미가용/예외 시 MySQL fallback 보존. (FIX2) base SYSTEM_PROMPT 전면 개편 — grounding 부재/불일치 시 search/describe 발견 의무 + "테이블/컬럼 추측 금지" + 0-rows/에러 환각 가드 + 첨부 리뷰 우선순위 분기 + 사고확장/애매 시 가정명시 후 되묻기, well-grounded 정상 케이스 1-call 효율 유지(코드 상수 + 라이브 `WebSystemPrompts` global row 동시 갱신). (FIX3) `_assemble_core_messages` 가 윈도우 밖 standalone user 메시지를 최대 8개 보존(재정규화로 orphan tool 제거) + `domain._is_low_information_request` 로 인사/메타 origin 고정 차단. (FIX4) `_build_attachment_context_section` text INSTRUCTION 에 리뷰 우선순위 명시 + app.py `_prepare_text_inline_attachments` `ORDER BY Id ASC`→`DESC`(+reverse) 로 cap 초과 시 최신 첨부 보존. **검증**: ruff(All passed) + pytest **189 passed/2 skipped**(신규 `test_db_query_ux.py` 12건, 회귀 0) + 라이브 PG SQL 3종 실데이터 반환 확인 + outside-voice 적대적 diff 리뷰. 변경 파일 3(agent_core.py / domain.py / app.py) + 테스트 1. RBAC/schema/secret/endpoint 무변경.
- [x] TASK-0147 (REQ-20260604-0147, **Major §12.3** — insight worker degraded read-back backoff = livelock 재발 방지). TASK-0145/0146 이 read-back 2경로를 PG 로 고쳤으나, **PG 가 다운되면** 두 read-back 이 (DROP 된) MySQL fallback 으로 떨어져 다시 전부 missing/changed 오판 → 무한 재생성(livelock) 재발 가능(현 fallback 은 빈 결과 + 1회 warn 뿐). 방어 가드 추가: (1) `insight._insight_readback_degraded()` — read backend 가 postgres 인데 `_pg_available()` 실패 또는 `_pg_connect_ro()+SELECT 1` probe 실패면 True(MySQL 모드면 항상 False — live mem_conn 사용이라 불일치 없음). (2) `run_insight_cycle` 이 lock 획득 후 degraded 면 scan/generate skip + status=`degraded_readback`(`should_log` 통과로 가시화). (3) `run_insight_worker_loop` 이 cycle status 가 `degraded_readback`/`error` 면 짧은 tick(8s) 대신 `AGENT_INSIGHT_WORKER_DEGRADED_BACKOFF_SEC`(기본 300s) backoff — PG 복구 대기, 무의미한 재시도(livelock 동력) 정지. **검증**: ruff PASS + pytest **177 passed/2 skipped**(신규 `test_insight_degraded_backoff.py` 4건) + 라이브 functional(PG up→False, `_pg_available=False`→True). **outside-voice 불요**(REV-20260604-0147 [SKIPPED] — RBAC/schema/secret/endpoint 무변경, read 경로 방어 가드 only, REV-0145 의 이미 리뷰된 패턴 연장).
- [x] TASK-0145 (REQ-20260604-0145, **Major §12.3** — insight worker livelock 근본 수정 + 운영 하드닝). **증상**: 본 프로젝트를 오래 실행하면 머신 전체가 점점 느려짐(최근 2개월 주기 확인). **근본 원인**: insight worker(`run_insight_worker_loop`, tick=8s)의 영속 검증 read-back `_load_insight_artifact_states` 가 05-27 cutover 로 DROP 된 MySQL `AgentMemory*` 테이블(존재하지 않음)을 조회 → 예외가 `except: rows=[]` 로 **조용히 삼켜져** 4파트(fact/text/rag_document/rag_object) 전부 missing 으로 오판 → `artifact_missing` 영구 유지 → 매 8s 동일 객체 무한 재생성(**livelock**). 그러나 쓰기 정본은 PG(`public.fact_entries` 780·`rag_documents` 19695 실재). **라이브 근거**: 당일 432 cycle / generate_insight **6721건 전부 verify=partial_persist, 성공 0**(agent_memory 123회·global_db 117회 등 동일객체 반복). 이 무한 LLM(edge=ollama, CPU-bound) 호출이 ~3코어 연속 점유(6h 에 CPU 17h) + insight_route.log 최대 1GB/일 + postgres/pgbouncer json 로그 90MB/6h → WSL2 page cache/vmmem 무한 팽창으로 머신 progressive slowdown. **산출**: (A 근본) `modules/insight.py` — `_load_insight_artifact_states_pg()` 신규(PG `fact_entries`/`rag_documents`/`rag_objects`+`texts` join, `_pg_connect_ro()` least-priv) + `_load_insight_artifact_states` 가 `AGENT_KB_READ_BACKEND=postgres` 시 PG read-back 분기(PG 미가용 시 MySQL fallback) + 공유 row-처리 헬퍼 5종(`_apply_insight_*_rows`/`_build_insight_object_maps`) 추출 + 삼켜지던 예외 가시화(`_warn_insight_readback_failed`). `modules/kb_scope.py` — `_scope_filter_sql_pg`(snake_case `scope_key`) + **`_load_kv_prefix_map` PG 분기**(동일 cutover 잔재의 두 번째 면 — fingerprint/refresh_at 맵을 MySQL `AgentMemoryKv`(DROP됨)가 아니라 PG `agent_runtime.kv` 에서 읽도록 `load_memory_kv` 와 동형으로 라우팅). **두 read-back 불일치**: (1) artifact 영속 검증(reason `artifact_missing`) + (2) fingerprint 변경 감지(reason `fingerprint_changed`) — 둘 다 PG 로 고쳐야 무한 재생성이 완전히 멈춘다(1번만 고치면 reason 이 `fingerprint_changed` 로 바뀌며 재생성 지속, 라이브로 확인됨). (B 하드닝) `docker-compose.yml` — 15개 서비스 전부 로그 로테이션(json-file max-size 20m/max-file 5) + mem_limit/pids_limit(현재 사용량 대비 넉넉 — runaway 만 차단, mem_limit 은 page cache 까지 cgroup 귀속해 WSL2 vmmem 상한). `config.py`/`utils.py` — `AGENT_LOG_MAX_BYTES`(기본 50MB) + `append_log_line` 크기 회전. `bin/gc.sh` — 로그 day-dir retention(기본 14d). **검증**: py_compile + ruff(All checks passed) + pytest **173 passed/2 skipped**(baseline 동일, 회귀 0) + 라이브 functional(수정 모듈 컨테이너 import → 재생성 반복 3키 전부 `complete=True/missing=[]`, OLD 코드는 `complete=False`+4파트 missing) + 라이브 SQL(4파트 PG 실재 확인). **outside-voice review (general-purpose subagent, REV-20260604-0145) Verdict PASS — BLOCKER 0**(컬럼 매핑·scope NULL 처리·커넥션 close·false-positive 위험 전부 확인). **이월(TODOS)**: PG 다운 시 degraded read-back 에서 재생성 backoff(현재 로깅만), 별도 compose 프로젝트(local-llm/ollama·mysql-lts)의 리소스 제한.

- [x] TASK-0123 (REQ-20260528-T1T5, **Major §12.3** — Postgres KB 성능 최적화 T1~T5 로드맵 + PgBouncer/Replica 전체 활성화). **산출 9건**: (a) `modules/knowledge.py` — `_load_top_facts_pg()` 신규 (DISTINCT ON + ANY(array) 단일 쿼리, N+1 제거) + `_build_knowledge_payload()` PG fast path 분기 + `_acquire_advisory_lock_pg()` / `_release_advisory_lock_pg()` (pg_try_advisory_lock(hashtext)) + `_is_refresh_due()` PG 무효화 플래그 연동. (b) `modules/db.py` — `_pg_connect_ro()` replica 라우팅 + `_pg_mark_kb_invalidation()` UPSERT + pg_notify + `_pg_check_kb_invalidation()` 조회. (c) `modules/config.py` — `AGENT_KB_PG_HOST_RO` / `AGENT_KB_PG_PORT_RO` 추가. (d) `modules/kb_backend.py` — `_DualWriteMirror._mirror()` fact write 후 `_pg_mark_kb_invalidation()` 호출. (e) `modules/memory.py` — `_ensure_pg_schema()` pg_matviews UNION (MV 감지 버그 수정). (f) `src/scripts/agent_kb_schema.sql` — pg_stat_statements + MATERIALIZED VIEW (CONCURRENTLY, 고유 인덱스) + JSONB + GIN + autovacuum + kb_invalidations + kb_slow_queries view + partial ivfflat index + GIN 인덱스 순서 버그 수정 (TEXT→JSONB DO block 이후로 이동). (g) `docker-compose.yml` — PgBouncer transaction-mode sidecar + PostgreSQL 14 파라미터 튜닝 + postgres-replica (streaming async, profile:replica) + postgres-replica-init entrypoint list 형식 수정 + replica max_connections 50→100. (h) `.env` — `AGENT_KB_PG_HOST=pgbouncer` + `AGENT_KB_PG_HOST_RO=postgres-replica` + `AGENT_KB_PG_USER_RO` / `AGENT_KB_PG_PASSWORD_RO` 추가. (i) `docs/ARCHITECTURE.md` §7 신규 (T1~T5 최적화 레이어) + wiki 3건 갱신 (Data-Flow.md / kb-postgres-pgvector.md / hot.md). **활성화 과정 발견/수정 3건**: (1) pgbouncer `AUTH_TYPE=md5` → `scram-sha-256` (userlist 평문 저장으로 PostgreSQL SCRAM 정합), (2) agent_kb_rw 비밀번호 scram-sha-256 재설정 (md5 임시 우회 제거), (3) pg_hba.conf `host replication all all scram-sha-256` 추가 (replica pg_basebackup 허용). **검증**: T1(DISTINCT ON fact_entries 780행 조회 OK) + T2(MV 780행 0.062ms) + T3(PgBouncer → postgres 172.18.0.7 PASS) + T4(kb_invalidations UPSERT 0.098ms) + T5(postgres-replica is_in_recovery=True 172.18.0.12, WAL async streaming). **outside-voice 불요** (RBAC role 변경 없음, endpoint 변경 없음, 기존 agent_kb_rw/ro role 재사용).

- [x] TASK-0120 (풀 테스트 수행 — 서비스 전체 버그 제거). 모든 명세 기능에 대한 풀 테스트 진행 + 발견 오류 전부 수정. **수정 파일 7건**: agent_core.py + llm.py (SyntaxWarning 이스케이프 시퀀스 2건), kb_backfill.py (TABLE_MAPPING[texts] id_col/select_cols 수정 + _insert_pg_batch row[1:] 통일), kb_backend.py (_DualWriteMirror 클래스 신규 + _dual_write_kb 인스턴스 + 6 mirror method), runtime_backend.py (AGENT_RUNTIME_DUAL_WRITE + RuntimeBackend ABC + MysqlRuntimeBackend + PgRuntimeBackend 10 read method + _dual_write_runtime_mirror), utils.py (_text_store_insert → _dual_write_kb.upsert_text 연동), memory.py (save_memory_kv → _dual_write_runtime_mirror 연동). pytest 결과: 146 PASS, 2 SKIP, 0 FAIL (feature-0002 전체).

- [x] TASK-0119 (REQ-20260527-AR-M5, **Major §12.3** — MySQL agent_runtime 6 테이블 DROP, outside-voice 필수). Phase 2 AR-M5: MySQL `agent_memory` DB 의 agent_runtime 6 테이블 cleanup 스크립트. **본 cycle 산출 3건**: (a) `bin/runtime-cleanup-mysql.sh` 신규 — Stage A/B/C 3단계 cleanup 정책 (ADR-0028), --dry-run/--backup-only/--confirm 3 mode, 4 gate (AGENT_RUNTIME_READ_BACKEND=postgres + dual_write 대소문자 정규화 차단 + --cutover-date 14-day window + TTY double-confirm), mysqldump backup (gzip+sha256+integrity, backtick-anchored CREATE TABLE 검증), 6 테이블 DROP FK convention 순서, ERR trap. (b) `tests/test_runtime_m5_cleanup.py` 신규 (16 test) — script 존재/syntax/dry-run/DROP 순서 + confirm 거부 + mode 중복 거부 + 4 gate 검증 + ADR-0028 문서화 확인. (c) `docs/DECISIONS.md` ADR-0028 신규 (Stage A/B/C + DROP 순서 + confirm string + 대안 폐기). **outside-voice review (REV-20260527-0009, SUBAGENT) Verdict NEEDS-FIX → PASS**: C-1(MYSQL_PWD cmdline→env) + M-1(dual_write 대소문자) + M-2(Stage 5 rollback hint + ERR trap) + M-3(grep backtick-anchor + 50-line threshold) + N-1/N-2/N-3 모두 본 cycle 내 반영. pytest 16/16 PASS (신규) + 131/131 PASS (전체, pre-existing 8 failure 제외).

- [x] TASK-0118 (REQ-20260527-AR-M4, **Major §12.3** — cutover read path, outside-voice 필수). Phase 2 AR-M4: `AGENT_RUNTIME_READ_BACKEND=postgres` env 도입 + PgRuntimeBackend 9 read method + fail-soft dispatcher + memory.py 7 read 분기 + agent_core.py 3 read 분기. **본 cycle 산출 5건**: (a) `modules/runtime_backend.py` 수정 — `AGENT_RUNTIME_READ_BACKEND` env var + `_PG_LOAD_KV/ALL/BY_KEY_VALUE/SUMMARY/MESSAGES/STEPS/CORE_MESSAGES` + `_PG_LIST_CONVERSATIONS` + `_PG_GET_CONV_MESSAGES_FULL` 9 SQL 상수 + `PgRuntimeBackend` 9 read method (load_kv/all/by_key_value/summary/messages/steps/core_messages/list_conversations/get_conv_messages_full) + `_get_pg_runtime_conn_ro()` (_pg_connect_ro 우선, 실패 시 _pg_connect fallback) + `_read_runtime_pg(method_name, **kwargs)` dispatcher (fail-soft: None 반환 on no-postgres env / conn None / unknown method / exception). (b) `modules/memory.py` 수정 — 7 read 함수 PG 분기 추가 (load_memory_kv / load_memory_kv_all / load_memory_context / load_recent_steps / list_conversations / list_processing_conversation_ids / list_delete_requested_conversation_ids) + `_assemble_steps()` helper 추출 (MySQL+PG 공유). (c) `agent_core.py` 수정 — `_assemble_core_messages()` helper 추출 + `_load_conversation_messages` PG 분기 (tool_calls JSONB→json.dumps 재직렬화) + `list_all_conversations` PG 분기 (3-tuple→dict 변환) + `get_conversation_messages` PG 분기 (timestamptz→isoformat). (d) `tests/test_runtime_read_backend.py` 신규 (23 test) — _read_runtime_pg routing 5건 / PgRuntimeBackend 9 method SQL 검증 / memory.py PG 분기 4건 / agent_core.py PG 분기 4건. (e) `bin/runtime-cutover-readiness.sh` 신규 (7 gate: dual-write 활성/row count/ANCHOR/unit test/PG read test/env 정합/backfill state). **web UI app.py 제외**: feature-0003 `_list_conversations` 는 MySQL `Accounts` cross-DB JOIN 의존 — AR-M4b 또는 Phase 3 별도 cycle 지정. ADR-0027 addendum 신규. **outside-voice review (REV-20260527-0008, SUBAGENT)** Verdict PASS. pytest 23/23 PASS (신규) + 122/122 PASS (전체, pre-existing 2 failure 제외). 다음 cycle: AR-M5 (MySQL 6 table DROP).

- [x] TASK-0117 (REQ-20260527-AR-M3, **Minor §12.3** — backfill ETL, 신규 파일만). Phase 2 AR-M3: MySQL agent_memory → Postgres agent_runtime 6 테이블 초기 backfill ETL. **본 cycle 산출 3건**: (a) `scripts/runtime_backfill.py` 신규 (~280 LOC, kb_backfill.py 패턴 답습) — `TABLE_ORDER` (FK 의존성 순서: core_conversations → core_messages → messages → steps → summary → kv) + `TABLE_MAPPING` (6 entry, id_col/offset_pk/since_col/jsonb_indices 이분법) + `_iter_mysql_rows()` (offset_pk=True→OFFSET pagination, False→Id>last_id) + `_build_insert_sql()` (jsonb_indices 기반 `%s::jsonb` cast) + `_insert_pg_batch()` (has_id→row[1:] skip, offset_pk→row 전체) + `backfill_table()` + `main()`. 멱등: upsert 테이블(conversations/kv/summary)은 ON CONFLICT DO NOTHING. append-only(core_messages/messages/steps)는 state file last_checkpoint 재개 기반. `--since AGENT_RUNTIME_DUAL_WRITE_START_TS` filter. (b) `bin/runtime-backfill.sh` 신규 — docker exec wrapper (kb-backfill.sh 패턴, `/shared` state dir). (c) `tests/test_runtime_backfill.py` 신규 (19 test) — TABLE_ORDER/MAPPING 정합 / state roundtrip / corrupted state / build_insert_sql (ON CONFLICT / jsonb cast / append-only) / _insert_pg_batch dry-run / kv full-row / core_messages id skip / steps id skip / empty rows / main smoke / single table / failure→1. **outside-voice 불요** (신규 파일만, 기존 caller 수정 0건, RBAC 무변경, write path 무변경). pytest 19/19 PASS (신규) + 101/103 PASS (전체, pre-existing 2 failure 제외). 다음 cycle: AR-M4 (cutover read path — AGENT_RUNTIME_READ_BACKEND env 분기 + PgRuntimeBackend read method).

- [x] TASK-0116 (REQ-20260527-AR-M2-d, **Minor §12.3** — xmax pg_branch tagging, code mutation 비파괴). Phase 2 AR-M2-d: PgRuntimeBackend `_execute_upsert_with_branch()` 헬퍼 + UPSERT 3개 SQL에 `RETURNING (xmax = 0) AS pg_inserted` 절 추가 + `_rt_pg_op_local` thread-local pg_branch 기록. 3 upsert (save_conversation/save_kv/save_memory_summary) → `_execute_upsert_with_branch` 호출. insert 3개 (save_core_message/save_memory_message/save_memory_step) → pg_branch=None. **outside-voice 불요** (기존 caller 수정 없음, KB M2-d 답습). pytest 82/82 PASS.

- [x] TASK-0115 (REQ-20260527-AR-M2-c, **Minor §12.3** — audit helper + verify/stress 스크립트, code mutation 비파괴). Phase 2 AR-M2-c: `_log_runtime_write_audit()` helper + `_build_runtime_audit_resource_id()` + `_RT_AUDIT_ACTION_MAP` + `_dual_write_runtime_mirror` 내 audit 호출 (mirror 성공 후) + `bin/runtime-dual-write-verify.sh` (~155 LOC, --counts/--audit-sla/--all 3 mode) + `bin/runtime-dual-write-stress.sh` (~80 LOC). `AGENT_RUNTIME_AUDIT_ENABLED=False` 기본값 (opt-in). 검증: verify.sh --counts PASS (PG=0 예상, dual-write 비활성). **outside-voice review (general-purpose, REV-20260527-0006) Verdict PASS (minor note 3개 non-blocking)**. pytest 82/82 PASS.

- [x] TASK-0114 (REQ-20260527-AR-M2-b, **Major §12.3** — method body 구현 + caller 수정, outside-voice 필수). Phase 2 AR-M2-b: `PgRuntimeBackend` 6 method 실제 구현 + `_dual_write_runtime_mirror` connection 내부화 + `memory.py` / `agent_core.py` caller mirror callsite 추가. **본 cycle 산출 4건**: (a) `modules/runtime_backend.py` 수정 (~170 LOC 추가) — 6 SQL 상수 (`_PG_UPSERT_CONVERSATION` / `_PG_INSERT_CORE_MESSAGE` / `_PG_UPSERT_KV` / `_PG_INSERT_MEMORY_MESSAGE` / `_PG_INSERT_STEP` / `_PG_UPSERT_SUMMARY`) + `PgRuntimeBackend` 6 method body + `_get_pg_runtime_conn()` + `_dual_write_runtime_mirror(method_name, **kwargs)` (pg_conn_factory 파라미터 제거 — connection 내부화) + connection 실패 이중 try/except (conn open 단계 + method 호출 단계 각각 PG_REQUIRED 분기). `tool_calls::jsonb` 캐스트 (ADR-0027 C2 정합, outside-voice 지적 반영). (b) `modules/memory.py` 수정 (+4 mirror callsite) — `save_memory_message` / `save_memory_kv` / `save_memory_summary` / `save_memory_step` 각 MySQL write 후 `_dual_write_runtime_mirror()` 호출. (c) `agent_core.py` 수정 (+3 mirror callsite) — `_save_message` / `_ensure_conversation` / `_update_conversation_topic` 각 MySQL write 후 `_dual_write_runtime_mirror()` 호출. (d) `tests/test_dual_write_runtime.py` 신규 (13 test, FakeConn/FakeCursor 패턴) — 12개 시나리오 (no-op / pg unavailable / UPSERT SQL / RETURNING id / 14-column INSERT / UPSERT summary / UPSERT conversation / jsonb cast / non-fatal / fatal / conn.close() 안전성 / memory.py caller 연동). `tests/test_anchor_invariant_runtime.py` 수정 (M2-b API 변경 반영: PgRuntimeBackend 구현 완료 assertion + mirror 시그니처 monkeypatch 패턴 업데이트). **outside-voice review (general-purpose subagent, `REV-20260527-0005`) Verdict NEEDS-FIX — tool_calls::jsonb 캐스트 누락 본 cycle 내 반영 완료**. pytest 23/23 PASS (runtime test files) + 82/82 PASS (전체 suite, pre-existing 2 failure 제외). 다음 cycle: AR-M2-c (cross-DB audit `bin/runtime-dual-write-verify.sh` + stress test).

- [x] TASK-0113 (REQ-20260527-AR-M2-a, **Minor §12.3** — ABC + skeleton, code mutation 비파괴). Phase 2 AR-M2-a: `RuntimeBackend` ABC + `MysqlRuntimeBackend` + `PgRuntimeBackend` skeleton + `_dual_write_runtime_mirror` entry point + test scenario catalog. **본 cycle 산출 2건**: (a) `modules/runtime_backend.py` 신규 (~220 LOC, kb_backend.py M2-a 패턴 답습) — 6 abstract method (save_conversation / save_core_message / save_kv / save_memory_message / save_memory_step / save_memory_summary) + MysqlRuntimeBackend (NotImplementedError skeleton) + PgRuntimeBackend (NotImplementedError skeleton) + _dual_write_runtime_mirror (AGENT_RUNTIME_DUAL_WRITE=0 default, no-op) + thread-safe singleton. (b) `tests/test_anchor_invariant_runtime.py` 신규 (10 test) — 6 시나리오 카탈로그 (RT-S1~RT-S6) + ABC 구조 확인 (import / 6 abstract method / NotImplementedError) + dual-write mirror 동작 (no-op / non-fatal / fatal 분기). **outside-voice 불요** (code mutation 비파괴 — 신규 파일만, 기존 caller 0 수정, RBAC 무변경, AGENT_RUNTIME_DUAL_WRITE default False). 다음 cycle: AR-M2-b (6 method body 구현 + caller mirror 추가 — outside-voice 필수).

- [x] TASK-0112 (REQ-20260527-AR-M1, **Major §12.3** — schema DDL + RBAC grant, outside-voice 필수). Phase 2 AR-M1: 6 agent runtime 테이블 DDL 정본 작성 + Postgres `agent_kb.agent_runtime` schema 적용 + ADR-0027 + schema compare 검증 도구. **본 cycle 산출 4건**: (a) `unit/feature-0002-agent-core/src/scripts/agent_runtime_schema.sql` 신규 (~140 LOC) — CREATE SCHEMA IF NOT EXISTS 방어 guard + set_updated_at() trigger 함수 + 6 테이블 (core_conversations / core_messages / kv / messages / steps / summary) + 인덱스 + trigger + GRANT. C1 흡수: kv FK 의도적 생략 주석 명시 (`__global__` sentinel 1588건). C2 흡수: messages.meta_json → jsonb. N5 흡수: CREATE SCHEMA IF NOT EXISTS 방어 guard. (b) Postgres `agent_kb.agent_runtime` schema 에 DDL apply 완료 (6 테이블 CREATE 확인). (c) `bin/agent-runtime-schema-compare.sh` 신규 (~120 LOC, kb-schema-compare.sh 패턴 답습) — 6 테이블 MySQL↔Postgres 컬럼 정합 비교, PASS 확인. (d) `docs/DECISIONS.md` ADR-0027 신규 (agent_runtime schema 설계 결정 — PK 전략 / FK 정책 / kv __global__ 의도적 생략 / meta_json jsonb / search_path 전역 변경 없음 / 인덱스 전략 / RBAC grant / Alternatives 검토). **outside-voice review (backend+qa subagent, `REV-20260527-0003`) Verdict PASS — Critical 2 (C1/C2) 본 cycle 내 반영**. 다음 cycle: AR-M2-a (`modules/runtime_backend.py` 신규 — Postgres write path dual-write).

- [x] TASK-0111 (REQ-20260527-AR-M0, **Minor §12.3** — Postgres 인프라, 비파괴 추가). Phase 2 AR-M0: `agent_kb` DB 안 `agent_runtime` schema 신설 + role grant + docs. **본 cycle 산출 3건**: (a) `bin/agent-runtime-bootstrap.sh` 신규 (~110 LOC, kb-pg-role-bootstrap.sh 패턴 답습) — 4 mode (all/--create-schema/--grant-roles/--check), wrapper path auto-detect, docker exec repo-postgres-1, 멱등 (CREATE IF NOT EXISTS). agent_runtime schema CREATE + agent_kb_rw/ro 에 USAGE + DEFAULT PRIVILEGES grant. (b) `docs/SECURITY.md` §10 신규 — agent_runtime Postgres schema RBAC 정책 (schema 설계 원칙 + role 권한 표 + 운영 절차 + ADR 참조). (c) 이관 plan §7 진행 기록 AR-M0 entry + migration plan AR-M0 task 완료 마킹. **schema 실제 적용**: `agent_kb.agent_runtime` schema CREATE 완료 (has_schema_privilege(agent_kb_rw, agent_runtime, USAGE)=t / agent_kb_ro=t). **T3 결정**: search_path 전역 변경 없음 — AR-M1 SQL 에서 schema-qualified (`agent_runtime.core_conversations` 등) 명시. **outside-voice 불요** (기존 role 재사용, 신규 role 신설 없음, DDL = schema 1개 CREATE, AR-M1 에서 outside-voice 필수). 다음 cycle: AR-M1 DDL + RBAC (6 runtime 테이블 DDL + ADR-0026 + outside-voice 필수).

- [x] TASK-0110 (REQ-20260527-AR-M-1, **Minor §12.3** — read-only baseline 측정). Phase 2 AR-M-1: 6 agent runtime 테이블 (AgentCoreConversations/AgentCoreMessages/AgentMemoryKv/AgentMemoryMessages/AgentMemorySteps/AgentMemorySummary) 의 사전 baseline 측정. **본 cycle 산출 2건**: (a) `bin/agent-runtime-measure-baseline.sh` 신규 (~190 LOC, kb-measure-baseline.sh 패턴 답습) — 5 mode (--rows/--schema/--callsites/--fk/--kv/--all), wrapper path 자동 detect, docker exec repo-mysql-1 직접 호출. (b) `artifacts/shared/agent-runtime-baseline-2026-05-27.json` — 6 테이블 exact row count (총 2676 row: Conversations 33 / Messages 392 / Kv 1987 / MemoryMessages 123 / Steps 141 / Summary 0) + insert rate (messages ~9.5/day / memory_messages ~3.0/day / steps ~3.4/day) + callsite 인벤토리 (feature-0002 core 54건 / feature-0003 web 105건) + FK 분석 (explicit FK 0, application-level implicit FK 확인) + KV scoping (__global__ 1588건 / conversation-scoped 399건). **outside-voice 불요** (read-only, code mutation 0건, RBAC 변경 0건). 다음 cycle: AR-M0 (Postgres agent_runtime schema CREATE + agent-runtime-bootstrap.sh).

- [x] TASK-0109 (REQ-20260526-0109, **Minor §12.3** — plan-only, project-level cross-cutting migration plan 문서 등록). 사용자 결정 (2026-05-26): agent_memory MySQL DB 의 모든 테이블 (agent\* 11개 + web\* 18개) 을 PostgreSQL 영역으로 이관 + 최종 agent_memory MySQL DB 자체 deprecation. agent\* 11개 → agent_kb DB 안 새 schema `agent_runtime` 신설. **본 cycle 산출 2건**: (a) `docs/MIGRATION_AGENT_MEMORY_TO_PG.md` 신규 (project-level cross-cutting plan 정본 — Phase 1 KB 5 정본 cleanup 마무리 + Phase 2 AR-M-1~M5 6 runtime 테이블 이관 cycle + Phase 3 18 web\* 별 DB outline + Phase 4 agent_memory DB deprecation). 기존 KB plan (TASK-0015 §2.1) 의 multi-cycle 구조 답습 — 각 sub-phase = 별 ai/\* worktree + 별 PR + 별 verify-completion. (b) `unit/feature-0002-agent-core/docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT}.md` append. **본 turn 의 deliverable 은 plan 문서 등록 + docs append 까지** — 실 implementation 0건 (RBAC/schema/code mutation 없음). **outside-voice review SKIPPED** (`REV-20260526-0003 [SKIPPED:plan-only-no-code-no-rbac-no-schema]`) — 사용자 메모 `feedback_outside_voice_for_rbac.md` 정합 (RBAC catalog 변경 없음, code path 변경 없음, schema mutation 없음). 신규 세션 진입 시 본 plan 문서의 Phase 2 AR-M-1 (baseline 측정) 부터 작업 시작 권장.

- [x] TASK-0026 (REQ-20260526-0001, **Major §12.3** — RBAC role 분리 인지 변경 + DDL credential path 도입). 직전 배포 (main = f03c270) production 검증 중 `repo-memory-init-1` 컨테이너가 exit 1 (`KB Postgres schema 적용 실패 (AGENT_KB_PG_REQUIRED=1): attempted relative import with no known parent package`) 로 재현된 증상의 정식 fix. **본 cycle 산출 6건**: (a) `unit/feature-0002-agent-core/src/Dockerfile` — `COPY .../src/scripts /app/scripts` 추가 (kb_backfill.py 등 ship), (b) `agent_core.py:init_memory()` — relative `from .modules.*` → absolute `from modules.*` (entry point `python /app/agent_core.py` 가 `__package__=None` 이라 relative 실패), (c) `modules/memory.py:_ensure_pg_schema()` — DDL 을 별 superuser connection 으로 분리 (agent_kb_rw 는 DML 전용 — DDL 권한 없음). `AGENT_KB_PG_SUPERUSER*` 1순위 + `AGENT_KB_PG_USER`/`PASSWORD` legacy fallback (B-1 흡수). schema 누락 시 RuntimeError + actionable hint (B-2 흡수 — silent PASS 차단). `try/except ImportError` 의 `e.name` 검사로 fallback 범위 좁힘 (B-3 흡수 — `.db` 내부 실제 ImportError 까지 덮지 않음), (d) `scripts/kb_backfill.py` — `AgentMemoryTexts` PK = `TextHash` (char 64) 반영해 texts 만 OFFSET pagination 으로 전환 (~800 행 frozen 가정 + 주석 명시). 다른 테이블은 Id-based cursor pagination 유지 (회귀 0), (e) `.env.example` — `AGENT_KB_PG_SUPERUSER` / `AGENT_KB_PG_SUPERPASSWORD` / `AGENT_KB_PG_SUPERUSER_HOST` 3 변수 신규 + bootstrap.sh 와의 정합 주석, (f) `unit/feature-0002-agent-core/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` append. **outside-voice review (Codex `codex-cli 0.130.0`, `REV-20260526-0001`) Verdict BLOCK + Critical 3 본 cycle 내 반영 완료** (B-1 superuser env name divergence → fallback / B-2 검증 fail-loud / B-3 ImportError fallback 좁히기). Nice-to-have 2 (.env.example + kb_backfill.py frozen 주석) 동반 흡수. **본 turn 의 deliverable 은 6 산출 + Critical 3 흡수까지**. Runtime 재검증 (production stack `docker compose -p kb-fix-verify` isolated 또는 본 main stack 에 fix 이미지 재빌드 → memory-init exit 0 확인) 은 commit/PR/머지 후 사용자 turn 책임.

- [x] TASK-0025 (REQ-20260522-0007, **Major §12.3** — RBAC 영향 cycle, 데이터 손실 boundary) §2.1 PLAN-APPROVED 의 **M5 phase (Cleanup — MySQL KB 5 정본 deprecation)** 실행. M4 cutover 후 MySQL KB 5 정본 (`AgentMemoryFacts` VIEW + 4 base table) 의 deprecation 절차 명문화 + cleanup script + ADR-0025 (14-day monitoring + Stage A/B/C boundary + `I_UNDERSTAND_DATA_LOSS` confirm). **본 cycle 산출 4건**: (a) `bin/kb-cleanup-mysql.sh` (~250 LOC) — 3 mode (dry-run / backup-only / confirm), mysqldump backup (VIEW DDL 포함 + utf8mb4 + hex-blob), backup integrity verify (gzip -t + line count + per-table CREATE TABLE/VIEW 존재 assertion), SHA256 sidecar + chmod 0600, 14-day window enforce (`--cutover-date YYYY-MM-DD`), AGENT_KB_DUAL_WRITE=0 sentinel 강제, TTY interactive double-confirm (또는 `KB_M5_RUN_FROM_HUMAN_SHELL=1`), env fallback (shell 우선, .env 보조), 후 DROP 검증, (b) `docs/DECISIONS.md` ADR-0025 (M5 cleanup 정책 + 14-day window + Stage A/B/C 정량화 + Alternative 검토 + 후속 액션), (c) `modules/kb_backend.py` 의 `_DualWriteMirror` class docstring 에 DEPRECATION NOTICE 추가 (코드 삭제는 M5-implementation cycle 책임), (d) `tests/test_m5_cleanup.py` 11 unit test (script exists/syntax/dry-run/wrong confirm 거부/mode 중복 거부/missing arg 거부/dual_write sentinel/cutover-date 누락/14-day 미달/deprecation notice/ADR-0025 정합). **outside-voice review (Plan subagent, `REV-20260522-0013`) Verdict FAIL + Blocker 5 + Critical 4 본 cycle 내 반영 완료** (B-1 VIEW DDL 포함 / B-2 backup integrity verify / B-3 AGENT_KB_DUAL_WRITE=0 sentinel / B-4 14-day window runtime enforce / B-5 mode 중복 + missing arg 거부 / B-6 TTY interactive confirm / B-7 env fallback / B-8 chmod 0600 + SHA256). C-1~C-7 nice-to-have 일부 흡수 (utf8mb4 + hex-blob + MYSQL_PWD env). **본 turn 의 deliverable 은 4 산출 + Blocker 5 + Critical 4 흡수까지**. **M5-implementation cycle (별 cycle, 사용자 결정)** 책임: `_DualWriteMirror` module + 5 caller mirror call site 코드 삭제.

- [x] TASK-0024 (REQ-20260522-0006, **Major §12.3**) — M4 cutover read path + pg_trgm + AGENT_KB_READ_BACKEND routing + cutover readiness + REV-20260522-0012 Critical 4 흡수. **done in commit 351e35b**.

- [x] TASK-0023 (REQ-20260522-0005, **Minor §12.3** — RBAC 무변경, 데이터 이전 작업) — M3 backfill ETL + embedding worker, **done in commit 957be67**.

- [x] TASK-0022 (REQ-20260522-0002, **Major §12.3**) — M2-d pg_branch xmax + S2/S4/S5/S6 + tagging coverage gate + Nice-to-have 7 + REV-20260522-0010 Critical 6 흡수. **done in commit bc3fa81**.

- [x] TASK-0101 (REQ-20260522-0004, **Minor §12.3** — backlog closure batch, cross-feature docs). 본 세션 (TASK-0098 ship + TASK-0100 hot-fix 후) 의 잔여 backlog 항목 일괄 closure. (a) **feature-0002**: TASK-0010 (작업 브랜치 commit 후 clean integration worktree cherry-pick/push) + TASK-0011 (원본 워크트리 더티 동일성 재확인) → 과거 작업 흐름의 마무리 docs, 코드 작업 자체는 이미 완료. (b) **feature-0001 / 0004 / 0005 / 0006**: TASK-0004 (엄격한 시나리오 정의) → placeholder. (c) **feature-0005**: TASK-0005 (MCP 서비스 기동 검증) → 본 cycle 실 환경 검증. (d) **feature-0003**: TASK-0072 → main 의 TASK-0099 closure 재확인.
- [x] TASK-0100 (REQ-20260522-0003, **Minor §12.3** — multipart UploadFile 의존성 hot-fix). `python-multipart>=0.0.9` 한 줄 추가 → web container 안정.
- [x] fix/query-result-string-truncation (Minor §12.3) — render.py CSV 기반 `preview_table` 구성.
- [x] TASK-0021 (REQ-20260522-0001, **Major §12.3**) — M2-c cross-DB audit explicit + SLA verify body + stress.sh body + S1/N1/N2 실 구현 + REV-20260521-0009 Critical 6 흡수. **done in commit 7540e17**.

## 1.2 Implementation Plan (TASK-0026 — KB Postgres bootstrap fix 본 cycle)

영향 파일 (본 cycle, code + env + docs):
- `unit/feature-0002-agent-core/src/Dockerfile` (+1 LOC) — `COPY .../src/scripts /app/scripts` 추가. agent image 가 kb_backfill.py / kb_embedding_worker.py / agent_kb_schema.sql 을 ship.
- `unit/feature-0002-agent-core/src/agent_core.py` (+/- 2 LOC, line 2016 / 2018) — `from .modules.db import _pg_available` → `from modules.db import _pg_available`, 동일하게 `.modules.memory` → `modules.memory`. entry point `python /app/agent_core.py` 직접 실행이라 `__package__ = None` → relative import 실패.
- `unit/feature-0002-agent-core/src/modules/memory.py` (+45 LOC, 1410-1462 + 1564-1582) — `_ensure_pg_schema()` 의 DDL 분리. (i) `try/except ImportError` 의 `e.name` 검사로 fallback 범위 좁힘 (B-3). (ii) `AGENT_KB_PG_SUPERUSER` / `AGENT_KB_PG_SUPERPASSWORD` 1순위, unset 시 `AGENT_KB_PG_USER` / `AGENT_KB_PG_PASSWORD` legacy fallback (B-1). (iii) superuser conninfo + autocommit + `cur.execute(schema_sql)`. SUPERPASSWORD 없으면 DDL skip (bootstrap.sh `--apply-schema` 가 사전 적용했다는 가정). (iv) return dict 직전에 `expected_tables` / `missing_extensions` / `view_present` 검증 — 누락 시 RuntimeError + actionable hint (B-2 — silent PASS 차단).
- `unit/feature-0002-agent-core/src/scripts/kb_backfill.py` (+45 LOC) — `AgentMemoryTexts` PK = `TextHash` (char 64) 인지 반영. `TABLE_MAPPING["texts"]` 에 `text_hash_pk: True` flag + `id_col: TextHash` + `select_cols` 에서 `Id` 제거. `_iter_mysql_rows()` 가 `text_hash_pk` 분기에서 OFFSET pagination (~800 행, 성능 충분). `_insert_pg_batch()` 가 `text_hash_pk` 시 `row` 전체 INSERT (다른 테이블은 `row[1:]` 로 Id skip). frozen 가정 주석 추가 (Nice-to-have).
- `.env.example` (+11 LOC) — `AGENT_KB_PG_SUPERUSER` / `AGENT_KB_PG_SUPERPASSWORD` / `AGENT_KB_PG_SUPERUSER_HOST` 3 변수 + bootstrap.sh 정합 주석 (Nice-to-have).
- `unit/feature-0002-agent-core/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`: REQ-20260526-0001 + TASK-0026 + CHG-20260526-0001 + REV-20260526-0001 + REPORT Summary 1줄.

접근 방법:
1. **Bug root cause**: production 의 memory-init container 가 `python /app/agent_core.py` (절대 path 실행) 로 띄워지는데, `from .modules.db import _pg_available` 의 relative import 가 `__package__ = None` 환경에서 `ImportError: attempted relative import with no known parent package` 로 실패. `AGENT_KB_PG_REQUIRED=1` 의 fail-loud 분기가 작동해 sys.exit(1). 따라서 production 의 KB Postgres schema 가 이미 적용된 상태에서도 검증 단계까지 못 가서 init 실패.
2. **Fix path A (relative→absolute)**: agent_core.py 의 2개 import 만 absolute 로. memory.py 등 라이브러리 모듈은 양쪽 import 컨텍스트 (relative 또는 absolute) 가능하도록 try/except 패턴 유지하되, `e.name` 검사로 진짜 ImportError 가리지 않게.
3. **Fix path B (DDL/role 분리)**: `agent_kb_rw` 가 DML 전용임을 인지해 DDL 은 별 superuser conn 사용. SUPERPASSWORD unset 일 때는 bootstrap.sh 가 이미 적용했다는 가정으로 skip + 검증만 수행.
4. **Fix path C (fail-loud)**: 검증 단계가 silent PASS 되지 않도록 expected schema 정합 검사 + actionable hint.
5. **Fix path D (kb_backfill PK)**: 별 issue 지만 production runtime 에 영향. M3 backfill 이 future cycle 에서 호출될 때 정상 작동하도록.

**Outside-voice review**: 호출 ✓ (사용자 args 명시 + RBAC role 분리 인지 변경 = `feedback_outside_voice_for_rbac.md` 정책 정합). Codex `codex-cli 0.130.0`, `REV-20260526-0001`. Verdict **BLOCK** → **PASS 전환** (Critical 3 본 cycle 흡수 + Nice-to-have 2 동반 흡수).

**Runtime 검증 (사용자 운영 turn 책임)**:
1. PR squash merge + main pull --ff-only 후 main = f03c270 + 본 cycle commit.
2. production stack `docker compose build memory-init` 또는 `agent` (공유 image).
3. `docker compose up -d memory-init` → exit 0 확인 + 로그에 `KB Postgres schema 적용 완료: tables=[fact_entries, rag_documents, rag_objects, texts], view=True, extensions=[pg_trgm, vector], grants=...` 출력 확인.
4. 추가 회귀: `make ask` 등 agent 호출 시 KB read path 정상 작동 확인.
5. 만약 production 의 schema 가 부재이면 RuntimeError + actionable hint 출력 — 사용자가 `bin/kb-pg-role-bootstrap.sh --apply-schema` 사전 실행 후 재시도.

위험도: **Major §12.3** — RBAC role 분리 인지 변경 (DDL = superuser, DML = agent_kb_rw) + 4 code 파일 + ENTRYPOINT import path 변경. Pre-approved Changes (§2.1 PLAN-APPROVED 의 M2~M5 phase 가 KB Postgres bootstrap path 정합 보장 — 본 fix 는 그 path 의 implementation defect 수정).

## 1.3 Implementation Plan (TASK-0023 — M3 Backfill ETL + embedding worker, done — 보존)

영향 파일 (본 cycle, ETL + embedding + test):
- `unit/feature-0002-agent-core/src/scripts/kb_backfill.py` (신규 ~280 LOC) — TABLE_MAPPING (4 table) + load_state/save_state + open_mysql_conn/open_pg_conn (기존 modules/db.py 재사용) + _iter_mysql_rows paginate + _insert_pg_batch ON CONFLICT DO NOTHING + backfill_table progress logging + main() argparse (--table/--since/--batch-size/--dry-run/--reset-state).
- `unit/feature-0002-agent-core/src/scripts/kb_embedding_worker.py` (신규 ~190 LOC) — get_settings (config.py 의 5 env 변수) + open_pg_conn + call_openai_embeddings (retry + timeout) + count_pending/fetch_pending_batch/update_embeddings + estimate_cost_usd (model 별 가격 추정) + main() argparse + dry-run cost estimation.
- `bin/kb-backfill.sh` (신규 ~45 LOC) — docker exec agent + AGENT_KB_BACKFILL_STATE_DIR=/shared.
- `bin/kb-embedding-worker.sh` (신규 ~25 LOC) — docker exec agent + arg passthrough.
- `unit/feature-0002-agent-core/src/modules/config.py` (+~15 LOC) — AGENT_KB_EMBEDDING_MODEL (text-embedding-3-small default) + DIM (1536) + BATCH_SIZE (100) + TIMEOUT_SEC (60) + MAX_ATTEMPTS (3) + EXPORT_VARS 등록.
- `tests/test_kb_backfill.py` (신규 ~125 LOC) — 4 unit test (TABLE_MAPPING 정합 / state roundtrip / dry-run no-op / main smoke).
- `tests/test_kb_embedding_worker.py` (신규 ~140 LOC) — 6 unit test (cost estimation 3 model + length mismatch + UPDATE SQL emit + dry-run no-OpenAI).
- `docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md`: cycle 등록 + 본 entry + Summary.

접근 방법:
1. TABLE_MAPPING — 4 table 의 mysql → pg 컬럼 명명 (SnakeCase 적용, KB_PG_DIALECT_NOTES.md 정합) + ON CONFLICT clause (texts/fact_entries 는 DO NOTHING, rag_documents/rag_objects 는 ON CONFLICT...DO NOTHING — backfill 은 멱등 진입이므로 DO UPDATE 불필요).
2. backfill state file — artifacts/shared/kb-backfill-state.json (host mount /shared).
3. dry-run path — `_insert_pg_batch` 가 INSERT 안 함, len(rows) 반환. SELECT 만.
4. embedding batch — OpenAI text-embedding-3-small 의 input=list batch (~100 text per API call).
5. dry-run cost — sample batch 1회 fetch + 평균 char count × pending → cost USD 추정.
6. test — FakeConn / FakeCursor 패턴, monkeypatch 으로 실 DB/API 우회.

**Outside-voice review**: SKIPPED — 본 cycle 의 ETL 은 RBAC 변경 없음 (agent_kb_rw role 의 기존 INSERT 권한 활용), endpoint 변경 없음, audit 변경 없음. 사용자 메모 `feedback_outside_voice_for_rbac.md` 정책 정합.

**Runtime 검증 deferral (사용자 / M4 별 cycle 책임)**:
1. main worktree `git pull --ff-only` + agent container 가동 확인.
2. `bin/kb-backfill.sh --dry-run` → 분모 정의 (총 row count + 4 table 별 last_id).
3. `bin/kb-backfill.sh --since $KB_DUAL_WRITE_START_TS` → 실제 ETL 진행.
4. `bin/kb-embedding-worker.sh --dry-run` → cost 추정 (M-1 baseline ~800 texts ≈ USD <0.05).
5. `bin/kb-embedding-worker.sh` → 실 OpenAI 호출.
6. `bin/kb-dual-write-verify.sh --counts --since $KB_DUAL_WRITE_START_TS` → 4 table row count 일치.

위험도: **Minor §12.3** — 데이터 이전 작업, RBAC / endpoint / audit 변경 없음. PLAN-APPROVED 범위 (§2.1.3 M3 phase).

## 1.3 Implementation Plan (TASK-0022 — M2-d pg_branch + S2-S6 + delete/prune SLA + Nice-to-have, done — 보존)

영향 파일 (본 cycle, instrumentation + tooling + test):
- `unit/feature-0002-agent-core/src/modules/kb_backend.py` (+~120 LOC) — 3 UPSERT SQL 에 `RETURNING id, (xmax = 0) AS pg_inserted` + `_pg_op_local` threading.local + `_get_last_pg_branch()` / `_clear_pg_branch()` helpers + `_execute_returning_id()` branch 캡쳐 (insert/update) + delete/prune/upsert_text 의 branch 라벨 + `_log_kb_write_audit(pg_branch=...)` 시그니처 + ChangeJson `pg_branch` 필드 + `_MIRROR_METRICS` + `get_mirror_metrics()` / `reset_mirror_metrics()` + `_DualWriteMirror._mirror()` 의 timing.
- `bin/kb-dual-write-verify.sh` (+~70 LOC) — `verify_audit_sla_delete_prune()` 신규 (JSON_UNQUOTE(JSON_EXTRACT(ChangeJson, '$.pg_branch')) 기반) + `--audit-sla-delete-prune` mode + `--since` ISO 8601 validation (C-4) + stderr suppress 일부 제거 (C-7).
- `bin/kb-dual-write-stress.sh` (+~30 LOC) — `--keep-agent-container` (C-2: docker exec agent 재사용) + `--log-dir` (C-3: per-step log file) + `step_log()` helper.
- `unit/feature-0002-agent-core/tests/test_anchor_invariant_postgres.py` (+~150 LOC) — `_setup_mock_mirror_env()` 공통 fixture (C-5 `_BACKENDS_CACHE` finalize) + S2 (rag_objs INSERT SQL 캡쳐 + category COALESCE NULLIF) + S4 (scope_key=sales_q4 보존 검증) + S5 (SQL template category COALESCE NULLIF assertion) + S6 (agent_kb_schema.sql VIEW DDL DISTINCT ON + tie-break 정합).
- `unit/feature-0002-agent-core/tests/test_dual_write_mirror.py` (+~80 LOC) — Test 11 pg_branch insert/update (FakeCursor fetchone 가 (id, pg_inserted) tuple) + Test 12 metrics counter (3 mirror call → calls_total=3, calls_by_method 정합, audit_calls_total=3).
- `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md`: cycle 등록 + outside-voice REV-20260522-0010 entry (계획) + 본 cycle 산출 기록.

접근 방법:
1. PG SQL 3 UPSERT 에 `RETURNING id, (xmax = 0) AS pg_inserted` 적용 — xmax = 0 은 INSERT, xmax != 0 은 UPDATE (PostgreSQL 의 row-level TX id semantics).
2. `_pg_op_local` threading.local + `_clear_pg_branch()` (mirror 진입 시 reset) + `_get_last_pg_branch()` (audit 호출 시 read).
3. `_execute_returning_id()` 의 row 가 length>=2 시 branch 캡쳐. delete/prune/upsert_text 는 method body 에서 branch 라벨 직접 set.
4. `_log_kb_write_audit()` 시그니처 `pg_branch` 추가 + ChangeJson 에 기록.
5. `_MIRROR_METRICS` dict + 4 metric (calls_total, calls_by_method, latency_ms_total/max, audit_calls/failures) + `_MIRROR_METRICS_LOCK` thread safety.
6. `_DualWriteMirror._mirror()` 의 진입/실패/성공 path 모두 `_record_mirror_latency()` 호출 + audit failure flag.
7. `bin/kb-dual-write-verify.sh` 의 `verify_audit_sla_delete_prune()` — JSON_EXTRACT 로 pg_branch 카운트.
8. `--since` ISO 8601 정규식 검증.
9. `bin/kb-dual-write-stress.sh` 의 `--keep-agent-container` 모드 — docker ps 로 agent service running 검출 시 docker exec 재사용. `--log-dir` per-step log file (각 step 의 timestamp + status).
10. S2/S4/S5/S6 mock-pattern 실 구현. S3 은 schema 정합 assertion 만 + skip 유지.
11. Test 11/12 — pg_branch + metrics 단위 검증.

**Runtime 검증 deferral (M3 별 cycle / 추후 책임)**:
1. `bin/kb-dual-write-verify.sh audit-sla-delete-prune --since <ISO>` 실 측정 (pg_branch tagging 활성 후 windowing)
2. `--keep-agent-container` 모드의 실 latency 개선 정량 측정 (M2-c default ~12분 → 예상 ~3분)
3. process-level latency baseline measurement: `get_mirror_metrics()` 의 production-like sampling

위험도: **Major (§12.3 — RBAC 동반 변경)**. PLAN-APPROVED 범위 + 사용자 "이번 세션에서 남은 cycle 모두 완수" 명시 + outside-voice review 호출 + Nice-to-have 7건 흡수 + S2/S4/S5/S6 실 구현.

## 1.3 Implementation Plan (TASK-0021 — M2-c cross-DB audit + SLA + invariant test, done — 보존)

영향 파일 (본 cycle, audit + tooling + test):
- `unit/feature-0002-agent-core/src/modules/kb_backend.py` (+~155 LOC, 919 → ~1075 LOC) — `_log_kb_write_audit()` helper + `_KB_AUDIT_ACTION_MAP` (6 method → ActionCode/ResourceType) + `_KB_AUDIT_SENSITIVE_KEYS` (text_content/source_sql 제외) + `_build_audit_resource_id()` composite builder (REV-20260521-0009 B-5 — conv|scope|key|... 식별 정밀화) + `_DualWriteMirror._mirror()` 의 audit explicit call (성공 후 best-effort) + `_BACKENDS_LOCK` thread-safe double-checked locking (REV-20260520-0008 Nice-to-have) + `threading` import + ChangeJson 16KB 캡 (REV-20260521-0009 B-6) + `pg_op_kind` tagging (REV-20260521-0009 B-1 — write/delete/prune 분리 기반).
- `bin/kb-dual-write-verify.sh` (+~125 LOC) — `verify_counts()` 본문 (4 테이블 pair count diff) + `verify_content_hash()` 본문 (rag_documents content_hash CONCAT identity 비교) + `verify_audit_sla()` 본문 (GREATEST(created_at, updated_at) PG denominator + write-only audit numerator + over-count fail-loud + zero-denominator INCONCLUSIVE exit 2, REV-20260521-0009 B-1/C-8 흡수).
- `bin/kb-dual-write-stress.sh` (+~40 LOC) — `trigger_insight_cycles()` + `trigger_ask_iterations()` 실 호출 구현 (docker exec insight-worker / docker compose run --rm agent) + FAILURES counter + exit code propagation.
- `unit/feature-0002-agent-core/tests/test_anchor_invariant_postgres.py` (+~290 LOC) — S1 (RagDocuments missing) 실 구현 (FakeConn + FakeCursor SQL 캡쳐 + monkeypatch `_log_kb_write_audit` 우회) + N1 (LLM call zero) 실 구현 (`modules.llm` 의 `_get_openai_client` / `_openai_chat_completion_with_deadline` / `llm_*` prefix + `OpenAI` 모두 monkeypatch tripwire, REV-20260521-0009 B-2 흡수; prune signature `keep_limit=` 정정 + DELETE SQL assertion, REV-20260521-0009 B-3 흡수) + N2 (TRUNCATE denied) env-gated (`AGENT_KB_PG_INTEGRATION_TEST=1`) + S2-S6 skip 유지 (M2-d 위임).
- `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md`: cycle 등록 + outside-voice REV-20260521-0009 entry + 본 cycle 산출 기록 + Critical 5 흡수 명시 + Nice-to-have 8 → M2-d.

접근 방법:
1. WebAuditEvents schema 파악 (Id/ActorAccountId/ActorRoleId/ActorType='system'/TargetAccountId/SessionId/ActionCode/ResourceType/ResourceId/ChangeJson/MaskedFields/RemoteAddr/UserAgent/RequestId/OccurredAt).
2. kb_backend.py 에 `_log_kb_write_audit()` 추가 — connect_with_retry(database=MEMORY_DB, autocommit=True, attempts=1, REV-20260521-0009 B-4) + ActorType='system' INSERT + ChangeJson 직렬화 (sensitive 제외) + 16KB 캡 + composite ResourceId.
3. `_DualWriteMirror._mirror()` 에 audit explicit call 통합 — mirror 성공 후 try/except 안에서 silent log 패턴.
4. `bin/kb-dual-write-verify.sh` 의 3 함수 본문 — counts/content-hash/audit-sla.
5. `bin/kb-dual-write-stress.sh` 본문 — docker exec + docker compose run + FAILURES counter.
6. `tests/test_anchor_invariant_postgres.py` 의 S1 + N1 + N2 실 구현.
7. Outside-voice review (Plan subagent, REV-20260521-0009) 호출. NEEDS-TWEAK Verdict + Critical 5 본 cycle 내 반영:
   - **B-1**: verify_audit_sla() 분모 GREATEST(created_at, updated_at) + write-only numerator + over-count fail-loud + zero-denom INCONCLUSIVE
   - **B-2**: N1 LLM tripwire 를 `modules.llm` 의 entry point (`_get_openai_client` / `_openai_chat_completion_with_deadline` / `llm_*` / `OpenAI`) 로 정정 + smoke assertion (적어도 1 patch 설치)
   - **B-3**: prune `keep_limit=` 정정 + 6 method SQL 발행 assertion
   - **B-4**: `connect_with_retry(attempts=1)` — best-effort
   - **B-5**: ResourceId composite (conv|scope|fact_key|... 정확 식별)
   - **B-6**: ChangeJson 16KB 캡

**Runtime 검증 deferral (M2-d 별 cycle 의 사용자 책임)**:
1. main worktree `git pull --ff-only`
2. `.env` 의 `AGENT_KB_PG_REQUIRED=1` 활성 환경
3. `bin/kb-dual-write-stress.sh --insight-cycles 3 --ask-iterations 5` 실 실행
4. `bin/kb-dual-write-verify.sh audit-sla --since <ISO>` → miss_ppm ≤ 1000 검증
5. S2-S6 invariant fixture 실 구현 (실 Postgres + insight worker 통합)
6. Latency baseline production-like 측정 (REPORT.md §4 risk log 0번 entry)

위험도: **Major (§12.3 — RBAC 동반 변경)**. PLAN-APPROVED 범위 + 사용자 "다음 Phase도 진행" 명시 + outside-voice review 호출 + Critical 5 본 cycle 흡수.

## 1.3 Implementation Plan (TASK-0019 — M2-a dual-write 준비, done — 보존, summary)

본 §1.3 의 deliverable 요약:
- `docs/KB_PG_DIALECT_NOTES.md` (~200 LOC) + ADR-0024 (Sprint 4 namespace 격리) ✓
- `agent_core.py:init_memory()` 확장 + `memory.py:_ensure_pg_schema()` grants 검증 + `kb_backend.py` ABC + skeleton + Postgres SQL 템플릿 ✓
- `bin/kb-dual-write-{verify,stress}.sh` skeleton + `tests/test_anchor_invariant_postgres.py` 6 시나리오 catalog ✓
- `docker-compose.yml memory-init.depends_on postgres` (Critical) + `.env.example` (`AGENT_KB_PG_REQUIRED` + `KB_DUAL_WRITE_START_TS`) ✓
- M1 outside-voice review (`REV-20260520-0005`) 의 4 Blocker 모두 해소 + outside-voice (`REV-20260520-0007`) Verdict NEEDS-TWEAK + Critical 4 + Blocker 3 본 cycle 내 반영 ✓
- commit `8dc6d8c` + push + main ff-merge ✓

## 1.4 Implementation Plan (TASK-0018 — M1 Postgres DDL + RBAC role, done — 보존, summary)

본 §1.3 의 deliverable 요약:
- `agent_kb_schema.sql` (241 LOC) + `bin/kb-pg-role-bootstrap.sh` (200 LOC) + `bin/kb-schema-compare.sh` (157 LOC) + `_ensure_pg_schema()` + ADR-0021 (2-layer hybrid) ✓
- outside-voice review (Plan subagent, `REV-20260520-0005`) Verdict NEEDS-TWEAK + 4 Critical 본 cycle 내 반영 ✓
- commit `8152ce9` + push + main ff-merge ✓ (squashed M1 + renumber fixup)

## 1.5 Implementation Plan (TASK-0017 — M0 인프라 도입, done — 보존, summary)

영향 파일 (본 cycle, schema 정의 + script + ADR 만, 실 DB 적용 없음):
- `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (신규, ~241 LOC) — 5 KB 테이블 (`fact_entries` / `texts` / `rag_documents` / `rag_objects`) + VIEW (`agent_memory_facts`) + index (covering + ivfflat for `texts.embedding`) + role grant `DO $$` block. dialect 변환 (PascalCase → snake_case, AUTO_INCREMENT → IDENTITY, ON UPDATE → trigger, FULLTEXT → pg_trgm GIN). pgvector + pg_trgm extension 활성화.
- `bin/kb-pg-role-bootstrap.sh` (신규, ~200 LOC) — `agent_kb` database + `agent_kb_rw` / `agent_kb_ro` role 생성 + schema sql 적용. 4 mode + rotate-password. **outside-voice Critical #1 반영**: `change_me_*` literal fallback fail-loud (`AGENT_KB_BOOTSTRAP_ALLOW_WEAK_PW=1` 명시 confirm 필요).
- `bin/kb-schema-compare.sh` (신규, ~157 LOC) — MySQL ↔ Postgres information_schema.columns 비교, snake_case ↔ PascalCase normalization, missing column 검출.
- `unit/feature-0002-agent-core/src/modules/memory.py` — `_ensure_pg_schema()` 함수 추가 (~100 LOC). M2 dual-write 진입 시 호출 entry. psycopg fail-soft + tables/view/extensions 존재 검증 query.
- `docs/DECISIONS.md` — ADR-0021 신규 (KB Postgres 분리 후 RBAC catalog 재정의). 2-layer hybrid model. **outside-voice Critical #2~#4 반영**: `kb.mutate.any` 명명 일관성 / cross-DB audit SLA ≤ 0.1% / password rotation graceful degradation / dynamic grant blindspot cycle 명시.
- `.env.example` — `AGENT_KB_PG_RW_PASSWORD` + `AGENT_KB_PG_RO_PASSWORD` 2 변수 추가 (outside-voice Critical #1).
- `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT,FUNCTION}.md` — cycle 등록 + 결과 기록 + FUNCTION §10 의 KB DB 스키마 표 갱신 (5 테이블 명 확정).

접근 방법:
1. **MySQL schema 입수** — 5 테이블의 `SHOW CREATE TABLE` 출력 분석. 컬럼 / 타입 / nullable / default / index / unique 정확 파악.
2. **Postgres DDL 작성** — dialect 변환 매핑 적용. embedding 컬럼은 `texts.embedding vector(1536)` 만 (Blocker B-4 결정). VIEW 는 `DISTINCT ON` 패턴 (MySQL correlated subquery 등가).
3. **Role 권한 모델 설계** — 2-layer hybrid (connection-level Postgres role + application-level catalog). `agent_kb_rw` (CRUD) / `agent_kb_ro` (SELECT) 분리. `DO $$` guard 로 schema sql 의 grant block 멱등.
4. **Bootstrap script** — 4 mode (`--create-db` / `--create-roles` / `--apply-schema` / `--all`) + `--rotate-password`. weak password fail-loud (ADR-0021 §Decision Layer 1 의 보안 요구사항).
5. **schema-compare script** — M1 cycle 의 검증 게이트. MySQL ↔ Postgres 컬럼 정합 자동 확인.
6. **`_ensure_pg_schema()`** — M2 dual-write 진입 entry point. M1 에서는 정의만, 호출 없음.
7. **ADR-0021 작성** — 결정 / Consequences / Alternatives / 후속 액션 4 섹션.
8. **Outside-voice review (Plan subagent) 호출** — 사용자 메모리 정책 `feedback_outside_voice_for_rbac.md` 적용. NEEDS-TWEAK Verdict + 4 Critical 본 cycle 내 반영.

**Runtime 검증 deferral (사용자 별 turn)**:
1. main worktree 의 `make start` 로 postgres 컨테이너 가동 (이전 cycle 의 deferral 도 포함)
2. `.env` 의 `AGENT_KB_PG_RW_PASSWORD` / `AGENT_KB_PG_RO_PASSWORD` 값 설정 (또는 weak password 우회 시 `AGENT_KB_BOOTSTRAP_ALLOW_WEAK_PW=1`)
3. `bin/kb-pg-role-bootstrap.sh --all` 실행 — database 생성 + role 신설 + schema 적용
4. `bin/kb-schema-compare.sh` PASS 확인 — 4 테이블 컬럼 정합
5. `psql -U agent_kb_rw -d agent_kb -c "INSERT INTO fact_entries (conversation_id, fact_key, fact_fingerprint) VALUES ('__test__', 'test', 'abc');"` smoke (M2 dual-write 검증 사전 점검)

위험도: **Major (§12.3 — RBAC role 신설 = 인증/인가 변경)**. PLAN-APPROVED 범위 + 사람 confirm 권장 (사용자 "다음 Cycle 이어서 진행" = 진행 의도 표명) + outside-voice review 필수 (메모리 정책).

## 1.6 Implementation Plan (TASK-0016 — M-1 baseline 측정, done — 보존, summary)

영향 파일 (본 cycle, 비파괴 추가만):
- `docker-compose.yml` — `postgres` 서비스 신규 (pgvector/pgvector:pg16, dbnet, healthcheck `pg_isready`, `../artifacts/postgres-data` 볼륨, port `${AGENT_KB_PG_PORT:-5432}`). **agent depends_on 에는 추가 안 함** — M0 는 standalone (Section F-4 권고).
- `.env.example` — `AGENT_KB_PG_*` 17 변수 신설 (§2.1.4 전체). connection 6 + read backend + dual-write + embedding 5 + ANN 4.
- `unit/feature-0002-agent-core/src/requirements.txt` — `psycopg[binary]>=3.1` + `pgvector>=0.2.4` 추가.
- `unit/feature-0002-agent-core/src/modules/config.py` — `AGENT_KB_PG_HOST` / `PORT` / `DB` / `USER` / `PASSWORD` / `SSLMODE` / `_ENABLED` + `AGENT_KB_READ_BACKEND` / `AGENT_KB_DUAL_WRITE` 9 export.
- `unit/feature-0002-agent-core/src/modules/db.py` — psycopg optional import (fail-soft) + `_pg_available()` + `_pg_connect(database=None, autocommit=True)` 추가. 기존 mysql.connector 경로 무영향.
- `bin/kb-pg-healthcheck.sh` (신규, 177 LOC) — 4 mode: `--container` / `--connect` / `--pg-connect` / `--extension`. `--all` 합본. `COMPOSE_PROJECT_NAME=repo` 강제 + main worktree `.env` fallback.
- `bin/kb-measure-baseline.sh` — `--latency` mode 추가 (5/5 보완). 5 시나리오 × N 회 (default 3, `--latency-n 10` 권장) wall-clock 측정. `docker compose -f <main compose> -p repo run --rm agent "<question>"` 호출.
- `unit/feature-0002-agent-core/docs/{TASK,REVIEW,MODIFY,REPORT}.md` — cycle 등록 + 결과 기록.

접근 방법:
1. **docker-compose `postgres` 서비스 추가** — standalone (agent depends_on 비추가). volume `postgres-data`, port `${AGENT_KB_PG_PORT}:5432`, healthcheck `pg_isready`. dbnet 만 (llm-shared / replica-net 비포함).
2. **`.env.example` AGENT_KB_PG_* 17 변수 추가** — §2.1.4 전체. 값은 빈 string (사용자가 `.env` 에서 채움).
3. **requirements.txt** — psycopg[binary]>=3.1 + pgvector>=0.2.4. Docker image 재빌드 시 자동 설치.
4. **config.py + db.py** — psycopg fail-soft import (M0~M1 환경에서 컨테이너 미가동 시 graceful). `_pg_available()` 가 None 체크 + env 변수 검사. `_pg_connect()` 는 RuntimeError 로 fail-loud (caller fallback 신호).
5. **bin/kb-pg-healthcheck.sh** — 4 stage: container running → psql SELECT 1 → pgvector extension available → agent `_pg_connect()` smoke. M0 runtime 검증 게이트.
6. **bin/kb-measure-baseline.sh --latency** — M-1 cycle 의 deferral (Blocker B-2 1/5) 보완. 측정 가능 상태 (script implementation) 까지 본 cycle. 실 측정은 사용자가 별 turn 에서 `bin/kb-measure-baseline.sh --latency --latency-n 10` 호출.

**Runtime 검증 deferral (사용자 별 turn)**: 본 cycle 의 코드·설정 변경 commit 후, 사용자가 main worktree 의 `chore/template-v3.9.0-upgrade` 작업 마무리 + `git pull --ff-only` + `.env` 의 `AGENT_KB_PG_*` 변수 값 채움 (host=postgres, port=5432, db=agent_kb, user=postgres, password=change_me_pg, sslmode=prefer) + `make start` 재기동 → `bin/kb-pg-healthcheck.sh --all` PASS 확인 → `bin/kb-measure-baseline.sh --latency --latency-n 10` 실행 → JSON artifact 갱신 (TASK-0017 measurement_ready 마감). 본 검증 단계는 외부 LLM API 호출 + docker 환경 의존성 큰 작업으로 자동 진행이 어려움.

검증 (본 turn): `python3 -m py_compile config.py db.py` PASS + `bash -n` syntax check PASS + `docker compose config` syntax OK (warning 만 .env 부재 — 본 worktree 의 .env 가 git 추적 외라 정상).

위험도: Minor (비파괴 추가). PLAN-APPROVED 범위 + outside-voice F-4 권고 정합 ("agent depends_on 비추가" 로 startup ordering 영향 0).

## 1.7 Implementation Plan (TASK-0015, done — 보존, summary)

본 §1.5 의 정본 plan 은 §2.1 (PLAN-APPROVED) 로 승격됨. TASK-0015 cycle 의 deliverable 요약:
- §2.1 multi-cycle plan 정본 작성 ✓
- outside-voice review (Plan subagent NEEDS-TWEAK + 11 Blocker) ✓
- §2.1.11 추적 표 ✓
- PLAN-APPROVED 마커 (2026-05-20 by ms.mckim.gpt@gmail.com) ✓
- commit `6ac2288` + push + main ff-merge ✓

## 1.8 Implementation Plan (TASK-0014 / TASK-0013, done — 보존, summary)

본 §1.6 는 historical TASK plan summary. 상세 본문은 git history (commit `6ac2288` 이전의 TASK.md) 참조.

- **TASK-0014** (REQ-20260515-0003, Minor §12.3): `compose_system_prompt()` 의 Account scope 가 공통 + Product 전용 누적 (Role scope 와 동일 패턴) 으로 정정. `src/agent_core.py` + `tests/test_compose_system_prompt.py` 3건 통과.
- **TASK-0013** (REQ-20260515-0002, Minor §12.3): `compose_system_prompt()` 의 Role scope 의 `ProductId IS NULL` 공통 prompt 를 fallback 이 아니라 누적 적용으로 전환. `src/agent_core.py` + `tests/test_compose_system_prompt.py` 2건 통과.

## 2. Implementation Plan

### 2.1 Plan — KB 정본 MySQL → Postgres pgvector 마이그레이션 (multi-cycle, plan-review)

> **Status**: ✓ **PLAN-APPROVED (2026-05-20 by ms.mckim.gpt@gmail.com)** — 본 §2.1 직후의 PLAN-APPROVED 마커 참조. M-1 cycle 부터 Execute 진입 가능.
> **Outside-voice review**: ✓ 완료 — Plan subagent (`REV-20260520-0002`) 가 **NEEDS-TWEAK** verdict + 11 Blocker / 5 Nice-to-have 식별. 본 §2.1 본문과 §2.1.11 에 NEEDS-TWEAK 적용 결과 반영.
> **Execute 진입 조건**: ✓ 충족됨 — `<!-- PLAN-APPROVED by ... on 2026-05-20 -->` 마커가 본 §2.1 직후에 부여됨.
> **위험도**: Critical (§12.3 — 롤백 어려운 마이그레이션 + RBAC catalog 신설 가능성 + 정책 §11.3·§14.1·§15.6·§15.7 변경 동반).
> **Cycle scope**: 본 §2.1 은 multi-cycle plan 이며 각 phase (M-1 → M0 → M1 → M2 → M3 → M4 → M5) 가 별 cycle (별 ai/* worktree + 별 PR + 별 verify-completion) 로 실행된다.
> **사용자 직접 확인 대기**: D-1 Sequencing 의 권장 default 는 Sprint 4 plan 의 D RAG schema 가 본 plan 의 `rag_documents` / `rag_objects` 와 공유 가능한지 여부에 따라 분기된다 (§2.1.1 D-1 / §2.1.7 Open Q #1+#8 / §2.1.11 Blocker B-1).

#### 2.1.0 배경 (Why)

현재 `agent_memory` DB (MySQL 8.0) 가 보유하는 KB 정본 5종은 다음과 같다.

| 정본 | 역할 | 현재 크기 추정 | 핵심 query 시그니처 |
|---|---|---|---|
| `AgentMemoryFacts` (VIEW) | `FactEntries` 의 합성 view (knowledge.py:697 주석 — "FactEntries 기반 VIEW로 전환됨, 별도 INSERT 불필요") | view (저장 0) | `SELECT ... FROM AgentMemoryFacts WHERE ConversationId IN ('__global__', :cid) AND FactKey ...` |
| `AgentMemoryFactEntries` | fact 정본 (`schema_insight:*`, `table_insight:*`, 대화별 fact, ScopeKey 인덱싱) | REPORT.md 기준선: `table_insight` fact 28→30 (확장 진행 중). 전체는 `incomplete table 126` + 누적 schema_insight 포함 수백~수천 row 예상 | INSERT/DELETE/SELECT — knowledge.py:598, 633, 761~905; insight.py:160 |
| `AgentMemoryTexts` | `TextHash → TextContent` 정규화 저장 (FactEntries / RagDocs / RagObjects 가 공통 참조) | 정규화로 중복 제거된 텍스트 본문 | utils.py:957~964 INSERT IGNORE INTO `AgentMemoryTexts` |
| `AgentMemoryRagDocuments` | FactEntries 기반 backfill, `ConversationId × ScopeKey × FactKey × ContentHash` UNIQUE | insight.py:200 cycle 후 `28 → 56` row | memory.py:202~219, 692~714; utils.py:1179; insight.py:200 |
| `AgentMemoryRagObjects` | FactEntries 기반 backfill + `CategoryDomain` / `CategoryEventType` / `CategoryMetricFamily` 컬럼 (D0~D3 라우팅의 §15.6 카테고리 기초) | insight.py:244 cycle 후 `28 → 30` row | memory.py:226~250, 723~766; utils.py:1230; insight.py:244, 288 |

KB 근거 패키지 구성 (AGENTS.md §11.3·§15.6) 의 현재 query path 는 다음 7개 모듈에 분산되어 있다 — `modules/memory.py` (1,366 LOC), `modules/knowledge.py` (3,153 LOC), `modules/insight.py` (1,410 LOC), `modules/schema.py` (1,426 LOC), `modules/planner.py` + `modules/utils.py` + `agent_core.py`. 총 7,500+ LOC 의 raw SQL (mysql.connector cursor 기반) 가 영향 범위.

**개선 동기**:
1. MySQL FULLTEXT + LIKE 기반 검색은 §15.6 §1) 의 coverage 기반 검색·§15.7 P2 의 metric/조인/검증상태 구조화 + §4) 의 카테고리 + Depth 라우팅 (D0→D1→D2→D3) 을 의미 거리 (embedding similarity) 로 표현하기 어렵다. pgvector 의 `ivfflat` / `hnsw` ANN index 가 자연 대응.
2. RAG 의 `ScopeKey × FactKey × ContentHash` unique 키 검색은 transactional 정합성과 별개로, embedding 기반 ANN 가 §11.3 의 "근거 충족 시 메타탐색 건너뛰기" 판정을 더 견고하게 만든다.
3. fact / RAG / Text / Object 4종 완전성 검사 (insight.py 의 repair_from_fact 루프) 는 새 storage 에서도 ANCHOR §3 invariant 로 보존되어야 한다.
4. 직전 세션의 multi-cycle plan 의 Sprint 4 (D RAG, PGVector 도입) 와 동일 Postgres 인프라를 공유할 수 있으면 도입 비용 1회.

**비-동기 (이 plan 이 다루지 않는 것)**:
- 응답 latency 개선 자체는 1차 목표가 아니다 (pgvector ANN 이 MySQL covering index 보다 느릴 가능성도 있으며, plan 수립 단계에서는 가정하지 않는다).
- LLM 모델 / SQL composer / planner 정책 변경 (별 cycle).
- agent_memory DB 의 비-KB 테이블 (`AgentMemoryConversations`, `AgentMemoryMessages`, `AgentMemorySteps`, `agentmemorykv`) 은 본 마이그레이션 범위 외 — MySQL 유지. KB 만 분리.

#### 2.1.1 결정 매트릭스

본 plan 이 PLAN-APPROVED 받기 위해 사용자가 명시적으로 확정해야 할 결정 3개. outside-voice review (Codex) 호출의 1차 입력이다.

**D-1. Sequencing (직전 multi-cycle plan 의 Sprint 4 D RAG 와의 선후 관계)**

| Option | 정의 | Pros | Cons | Recommendation |
|---|---|---|---|---|
| **A. 선행 (권장)** | 본 마이그레이션 (M0~M5) 이 Sprint 4 보다 먼저 진행 → Sprint 4 의 D RAG 는 본 마이그레이션이 구축한 pgvector 인프라 baseline 위에 D-only feature 만 얹는다. | 인프라 도입 1회로 통일. Sprint 4 의 D RAG 가 pgvector ANN 을 자연스럽게 사용 가능. KB cutover 후 새 D RAG 도 즉시 새 storage 에 작성. | 본 마이그레이션 phase M0~M5 가 critical path. Sprint 4 의 D RAG 가 본 마이그레이션 cutover (M4) 까지 대기. | **선행 (M0~M2 까지)** + **M3~M5 는 Sprint 4 와 병행** — M2 dual-write 단계 도달 후 Sprint 4 가 새 D RAG 를 pgvector 측에 직접 작성하기 시작. M3 backfill ETL 과 Sprint 4 가 동시 진행. M4 cutover 는 Sprint 4 D RAG 검증 + 본 마이그레이션 검증의 AND. |
| **B. 병행** | 본 마이그레이션과 Sprint 4 가 처음부터 같은 phase 로 진행. | 일정 단축 가능. | dual-write 로직 + D RAG 신규 schema + 5종 정본 이전 schema 가 동시에 변하므로 schema 충돌 가능성 + verify-completion 검증 어려움 + rollback 매트릭스 폭발. | (비권장) |
| **C. 후행** | Sprint 4 (D RAG, PGVector 도입) 가 먼저 완료 → Sprint 4 가 구축한 pgvector 인프라 위에 본 마이그레이션이 KB 5종 이전. | Sprint 4 의 D RAG 가 안정화된 후 KB 이전이라 risk 분산. | pgvector 인프라가 D RAG 만의 용도로 1차 도입되어, 후속 KB 이전 시 schema 명명·tablespace·index 정책 재논의 필요. 인프라 1차 도입 시점의 설계가 D RAG-only 가정으로 굳어질 risk. | (사용자 결정 필요 — outside-voice review 가 Sprint 4 schema 단순도 판정에 따라 전환 권유 가능) |

> **권장 default**: A (선행 + M3~M5 와 Sprint 4 병행).

**D-2. Topology (단일 Postgres cluster vs 별 인스턴스)**

| Option | 정의 | Pros | Cons | Recommendation |
|---|---|---|---|---|
| **A. 단일 cluster + 별 database (권장)** | 1 Postgres 인스턴스 안에 `agent_kb` database 신설. Sprint 4 의 D RAG 와 동일 인스턴스 안 별 database (예: `agent_drag`) 또는 schema (`agent_kb.kb`, `agent_drag.drag`) 분리. | 운영 부담 1 인스턴스. 백업·관측 통합. 인스턴스 내 vector index 메모리 공유. docker-compose 의 `postgres` 서비스 단일. | DB-level 권한 격리는 가능하나 cluster-level fault 가 양 도메인 동시 영향. shared-buffer 경합. | **A 권장** — KB + D RAG 둘 다 read-heavy + 같은 agent 프로세스가 접근하므로 cluster 분리 이득보다 운영 단순성 이득이 크다. |
| **B. 별 인스턴스** | KB 용 `agent_kb_pg` + D RAG 용 `agent_drag_pg` 2 개 Postgres 인스턴스. | 완전 격리. 한쪽 fault 가 다른 쪽 무영향. 메모리·index 독립. | 운영 부담 2배. docker-compose 서비스 2개. 백업·관측·credential 별도. cluster 간 cross-query 불가. | (비권장 — 본 plan 규모에서) |

> **권장 default**: A. schema-level 분리는 추후 ADR 로 결정 가능.

**D-3. Module rewrite strategy (raw psycopg vs SQLAlchemy ORM)**

| Option | 정의 | Pros | Cons | Recommendation |
|---|---|---|---|---|
| **A. raw psycopg3 + pgvector extension (권장)** | 현재 `mysql.connector` cursor 패턴을 그대로 psycopg3 cursor 로 교체. pgvector 의 native `vector` 타입은 psycopg3 의 `register_vector()` adapter 로 처리. | 현재 7,500+ LOC 의 raw SQL 패턴 보존. 마이그레이션 risk 최소화. SQL 한 줄 한 줄을 그대로 대응 변환 가능. | ORM 의 schema migration / typed model 이득 없음. raw SQL 의 dialect 차이 (e.g., `INSERT ... ON DUPLICATE KEY UPDATE` → `INSERT ... ON CONFLICT DO UPDATE`) 를 모든 INSERT/UPDATE 위치에서 수동 변환. | **A 권장** — 본 마이그레이션의 1차 목표는 정본 위치 이전이지 ORM 도입이 아니다. ORM 도입은 별 ADR. |
| **B. SQLAlchemy 2.x + pgvector dialect** | knowledge/insight/memory/schema 모듈을 ORM 모델 + session 패턴으로 재작성. | typed model + migration tool (Alembic) + cross-DB portability. | 7,500+ LOC 의 raw SQL 의도가 ORM expression 으로 1:1 대응 안 됨. 마이그레이션 + ORM 도입 동시 진행은 risk 폭발. cycle 분리 필요. | (별 ADR / 별 cycle) |

> **권장 default**: A (raw psycopg3 + pgvector adapter).

#### 2.1.2 영향 파일 (Execute 단계 — phase M0~M5 의 union)

**Source code (agent-core)**:
- `unit/feature-0002-agent-core/src/modules/memory.py` (1,366 LOC) — CREATE TABLE + ALTER + backfill (lines 202~766). Postgres DDL 로 dialect 변환 + `vector(N)` 컬럼 추가 + `ivfflat` / `hnsw` index 정의.
- `unit/feature-0002-agent-core/src/modules/knowledge.py` (3,153 LOC) — FactEntries CRUD (598, 633, 761~905). 모든 query path 의 dialect 변환 + connection helper 분기.
- `unit/feature-0002-agent-core/src/modules/insight.py` (1,410 LOC) — fact / RAG 4종 완전성 검사 + repair_from_fact (160, 200, 244, 288). ANCHOR §3 invariant 의 정본 구현 위치. 새 storage 에서도 동일 흐름 보존 검증.
- `unit/feature-0002-agent-core/src/modules/schema.py` (1,426 LOC) — `AgentMemoryFacts` (VIEW) / FactEntries 직접 조회 (198, 253, 265). VIEW 정의 자체를 Postgres 로 재작성.
- `unit/feature-0002-agent-core/src/modules/planner.py` — FactEntries 기반 plan 입력 (241, 256).
- `unit/feature-0002-agent-core/src/modules/utils.py` — TextHash 저장 (957~964) + RAG INSERT (1179, 1230) + `_load_rag_documents_for_request` / `_load_rag_objects_for_request` / `_filter_rag_objects_for_depth` 등 D0~D3 라우팅의 핵심 helper.
- `unit/feature-0002-agent-core/src/agent_core.py` — `_build_knowledge_context()` (232) + FactEntries / Texts JOIN (273, 293, 357). KB 조회 진입점.
- `unit/feature-0002-agent-core/src/modules/db.py` — connection factory. **psycopg3 connection helper 추가** + 기존 mysql.connector 와 공존 (M2 dual-write 단계).

**Infra**:
- `docker-compose.yml` — `postgres` 서비스 추가 (image: `pgvector/pgvector:pg16` 또는 `ankane/pgvector`). `agent` 컨테이너의 `depends_on` 확장. credential / port (5432 host-side) 정의.
- `docker-compose.override.yml.example` — 로컬 dev / WSL 대응 환경변수 예시.
- `.env.example` — 신규 변수 (§2.1.4 참조).

**Tests**:
- `unit/feature-0002-agent-core/tests/test_pgvector_migration.py` (신규) — dual-write 정합성 + fact-우선 복구 invariant + RagObjects category 보존 + D0~D3 라우팅 회귀.
- `unit/feature-0002-agent-core/tests/test_compose_system_prompt.py` — 회귀 검증 (KB 변경이 system prompt 조립에 영향 없음 확인).

**Policy docs (META path — §18.4 META mode 적용)**:
- `AGENTS.md §11.3` — "관련 질문에서 먼저 `AgentMemoryFactEntries` 근거를 조회한다" → "관련 질문에서 먼저 `agent_kb.fact_entries` (Postgres pgvector) 근거를 조회한다. 조회 path 는 `modules/knowledge.py:_load_kb_entries()` 가 단일 진입점." 형태로 갱신.
- `AGENTS.md §14.1` — 신규 변수 그룹 추가 (`AGENT_KB_PG_*`, `AGENT_KB_READ_BACKEND`, `AGENT_KB_DUAL_WRITE`, `AGENT_KB_EMBEDDING_*`, `AGENT_KB_ANN_*`).
- `AGENTS.md §15.6` — §1) 완전 구축 레이어의 저장소 명 변경 (`AgentMemoryFactEntries` → `agent_kb.fact_entries`). §4) 카테고리 + Depth 라우팅의 D0~D3 가 pgvector ANN similarity threshold 로 표현되는 방식 명시.
- `AGENTS.md §15.7` — 구현 로드맵의 P1/P2 항목을 pgvector 컨텍스트로 갱신.
- `unit/feature-0002-agent-core/docs/FUNCTION.md` — §10 Dependencies 의 `Memory DB 스키마 (agent_memory)` 표에 Postgres `agent_kb` 추가 + `AgentMemoryFactEntries` 행 deprecated 표시.
- `unit/feature-0002-agent-core/docs/INSIGHTS.md` — §4 아키텍처 개요 다이어그램 갱신 (MEMORY DB 박스 안의 FactEntries / Texts 가 Postgres 박스로 이동).
- `unit/feature-0002-agent-core/docs/ANCHOR.md §1·§3` — §1 외부 관점에 "왜 KB 가 별도 Postgres 인스턴스인가?" 추가. §3 가정된 사용 시나리오는 저장소 이름만 변경, fact-우선 복구 invariant 동일.
- `unit/feature-0002-agent-core/docs/AGENT_CORE_INTERNALS.md` — `_build_knowledge_context()` 의 새 query path 반영.
- `docs/DECISIONS.md` — 신규 ADR (예: ADR-0022 "KB 정본 Postgres pgvector 이전") + topology / sequencing / module rewrite 의 3-D 결정 근거.
- `docs/CONVENTIONS.md` — Postgres 명명 규칙 (snake_case) vs MySQL (PascalCase) 매핑 표 추가.
- `docs/SECURITY.md` — Postgres credential 관리 + RBAC catalog hook (`kb.read.any` / `kb.write.any` 신설 가능성, §2.1.5 참조).
- `docs/STATUS.md` — feature-0002 상태에 "KB Postgres 이전 (TASK-0015 계열, multi-cycle)" 표시.
- `docs/CODEBASE_MAP.md` — `agent_kb_schema.sql` (신규) + `bin/kb-backfill.sh` (신규) 등록.

**Tooling (신규)**:
- `bin/kb-backfill.sh` — MySQL → Postgres 초기 backfill ETL (M3 단계). 멱등 + resumable + progress 로그.
- `bin/kb-dual-write-verify.sh` — M2 dual-write 단계의 row count + content hash 정합 검증.
- `bin/kb-cutover-readiness.sh` — M4 cutover 진입 전 게이트 (모든 검증 PASS 시에만 cutover 허용).
- `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (신규) — Postgres DDL 정본.

#### 2.1.3 Phase 분해 (M-1 ~ M5)

각 phase 는 별 cycle (별 worktree + 별 PR + 별 verify-completion + REPORT.md 갱신) 로 진행한다. phase 간 인계는 본 §2.1 + 각 cycle 의 TASK.md §1.2 (cycle-specific plan) 가 정본.

**M-1 — 사전 baseline 측정 (Blocker B-2 — outside-voice NEEDS-TWEAK)**
- 목적: M0 인프라 도입 전, 현재 KB 의 정량 상태를 측정해 후속 phase 의 회귀 판정 기반을 확보. plan 의 가정 (row 수 / latency / EXPLAIN) 이 추정에 그치지 않도록 측정 산출물로 대체.
- 산출:
  - `bin/kb-measure-baseline.sh` (신규) — 다음 5종 측정 1회 실행:
    1. **Row count**: `SELECT COUNT(*)` 5종 (`AgentMemoryFactEntries` + `AgentMemoryTexts` + `AgentMemoryRagDocuments` + `AgentMemoryRagObjects` + `AgentMemoryFacts` (VIEW)).
    2. **`make ask` latency baseline**: 아래 5종 시나리오의 p50/p99 (각 시나리오 N=10 회 반복) — Blocker B-10 의 구체 catalog 항목.
       - **S1 단순**: "최근 7일간 가입한 사용자 수를 알려줘"
       - **S2 follow-up**: S1 후속으로 "그 중 PaymentMethod 가 카드인 비율은?"
       - **S3 모호**: "최근에 trend 가 어떻게 되고 있어?" (객체 미지정)
       - **S4 메타탐색**: "users 관련 테이블이 뭐가 있어?" (search_tables trigger 의도)
       - **S5 복구**: insight 가 누락된 테이블에 대해 ask 후 fact-우선 복구 path 진입 확인 — `insight_route.log` 에 `repair_from_fact` 흐름 기록 여부.
    3. **EXPLAIN baseline**: 주요 KB query 5건의 `EXPLAIN FORMAT=JSON` (MySQL) 출력 보관 — knowledge.py:761~905 의 핵심 SELECT 5건.
    4. **비-KB JOIN audit** (Open Q #9): `AgentMemoryConversations` / `AgentMemoryMessages` / `AgentMemorySteps` 가 KB 5종과 cross-table JOIN 하는 코드 위치 grep — 결과 0건이 예상이나 확인 필수.
    5. **현재 RBAC catalog 의 KB 접근 패턴 audit** (Blocker B-8): `unit/feature-0003-agent-web-ui/src/app.py:PERMISSION_DEFINITIONS` 의 `kb.*` / `memory.*` 항목 카운트 + agent-core 의 mysql_connector 접근 path 정리.
  - `artifacts/shared/kb-baseline-2026-05-20.json` — 측정 결과 정본 (M4 cutover gate 의 비교 대상).
- 검증: 위 5종 모두 실행 + JSON 저장 + REPORT.md 에 핵심 수치 요약 추가.
- 위험도: Minor (read-only 측정).
- 사람 승인: 불요 (PLAN-APPROVED 범위).

**M0 — 인프라 도입 (Sprint 4 와 공유 가능)**
- 목적: `pgvector/pgvector:pg16` docker-compose 서비스 추가 + agent 컨테이너의 connection helper 추가 (read-only test connection).
- 산출: `docker-compose.yml` 의 `postgres` 서비스, `.env.example` 의 `AGENT_KB_PG_*` 변수, `modules/db.py` 의 `_pg_connect()` helper, `bin/kb-pg-healthcheck.sh`.
- 검증: `make start` 후 agent 컨테이너에서 `_pg_connect()` 가 `SELECT 1` 통과. 기존 MySQL 흐름 무영향 (regression check).
- 위험도: Minor (비파괴 추가).
- 사람 승인: 불요 (Pre-approved Changes 후보 — 사용자 PLAN-APPROVED 마커가 본 M0 ~ M5 모두를 사전 승인).
- D-1 결정에 따라 Sprint 4 와 동시 진행 가능 — 단 schema namespace 충돌 회피 (Sprint 4 는 `agent_drag` database, KB 는 `agent_kb` database).

**M1 — Postgres DDL + Postgres role 신설 + 빈 schema 배치**
- 목적: `agent_kb` database + 5종 table (`facts`, `fact_entries`, `texts`, `rag_documents`, `rag_objects`) 의 Postgres DDL 작성. `vector(N)` 컬럼 + `ivfflat` / `hnsw` index 추가. `agent_kb_rw` / `agent_kb_ro` Postgres role 신설.
- 산출: `agent_kb_schema.sql` (DDL 정본) + `modules/memory.py` 의 `_ensure_pg_schema()` 함수 + `bin/kb-pg-role-bootstrap.sh` (Postgres role 신설 스크립트). embedding 저장 위치 결정 (Blocker B-4): **`texts.embedding` (TextHash 별 단일 embedding)** — TextHash 정규화 시점에 1회 embed → 동일 TextHash 의 다른 fact_entries / rag_documents / rag_objects row 가 재embed 비용 없이 vector 참조. `fact_entries.embedding` / `rag_objects.embedding` 컬럼은 없음 (Texts → 5종 JOIN 시 자연 참조).
- 검증: schema 적용 후 `\d+ agent_kb.fact_entries` + `\d+ agent_kb.texts` 가 모든 컬럼 + index 출력. MySQL 측 schema 와 컬럼 정합성 (이름 / 타입 / nullable / default) 비교 표 (`bin/kb-schema-compare.sh` 신규 임시 도구). `AgentMemoryFacts` VIEW 의 Postgres 측 정의 명시 (Blocker — Open Q #10).
- 위험도: **Major (Minor → Major 격상, Blocker B-8)** — Postgres role 신설 = 인증/인가 구조 변경 (§12.3). 단순 schema 배치 자체는 비파괴이나 role 권한 모델은 §12.1 사람 승인 대상.
- 사람 승인: **필수** — M1 cycle 의 PR 머지 전 사용자 confirm + `docs/SECURITY.md §RBAC` 갱신 + 본 plan §2.1.5 의 ADR-0021 작성 시작 (M4 cutover 전 완료 필수, Blocker B-9).
- D-3 dialect 변환 카탈로그 (Nice-to-have) 도 M1 산출에 포함 권장 — `bin/kb-dialect-audit.sh` 로 `ON DUPLICATE KEY UPDATE` / `INSERT IGNORE` / `TIMESTAMP(3) ON UPDATE` / `cursor.execute(multi=True)` 의 발생 위치 카운트.

**M2 — Dual-write phase (Blocker B-3 — fail rate 분모 정의 + synthetic load)**
- 목적: KB 정본 INSERT/UPDATE/DELETE 가 MySQL + Postgres 양쪽 동시 적용. read 는 MySQL only (지금까지 정본). `KbBackend` 추상화 인터페이스 도입 (4종 sub-backend: `FactEntriesBackend` + `RagDocumentsBackend` + `RagObjectsBackend` + `TextsBackend` — Section C 권고).
- 산출: `modules/knowledge.py`, `modules/insight.py`, `modules/utils.py` 의 write path 에 `_dual_write_kb()` 래퍼 추가. `unit/feature-0002-agent-core/src/modules/kb_backend.py` (신규) — `KbBackend` ABC + `MysqlKbBackend` + `PgKbBackend` 분리. embedding 컬럼은 M2 에서는 `texts.embedding` 만 NULL 로 작성 (M3 에서 backfill 시 일괄 embedding 생성).
- 검증 게이트:
  - **fail rate 분모 정의 (Blocker B-3)**: 비교 대상은 "M2 시작 이후 새로 INSERT 된 row" 만 (M-1 baseline 시점의 ContentHash 기준 backfill 미완료 row 는 분모 제외). `bin/kb-dual-write-verify.sh --since 2026-MM-DD` 형식의 timestamp filter 도입.
  - **Synthetic write load (Blocker B-3)**: 1주일 wait 대신 1주일 + synthetic load. `bin/kb-dual-write-stress.sh` (신규) 가 강제 insight cycle 3회 + ask 5종 시나리오 5회 = 약 50건 새 write 강제 trigger. 통계적 power 확보.
  - **Partial failure 시나리오 (Section C 권고)**: cross-DB tx 불가 → fact_entries INSERT 성공 + rag_documents INSERT 실패 의 partial failure 처리 명시. 정합 검증의 분모 정의 시점에 partial failure row 는 별도 카운트 → REPORT.md 에 분리 보고.
  - **ANCHOR §3 invariant 시나리오 6종 (Blocker B-7)**: `tests/test_anchor_invariant_postgres.py` (신규) — §2.1.6 의 6종 시나리오 통과. M2 → M3 진입 전 PASS 필수.
- 위험도: Major (write path 침습, rollback 가능하나 데이터 정합 risk).
- 사람 승인: PLAN-APPROVED 범위 (Pre-approved Changes 의 "비파괴적 추가").
- ANCHOR §3 invariant: fact-우선 복구 흐름 (insight.py 의 `repair_from_fact`) 이 M2 단계에서는 여전히 MySQL FactEntries 를 source 로 읽지만, write 는 양쪽으로 — Postgres 측 fact_entries 의 정합이 M2 검증의 1차 게이트. "repair_from_fact path 진입 시 LLM 호출 0건" assertion 도 M2 게이트에 포함 (negative assertion, Section C 권고).

**M3 — Backfill ETL + embedding 일괄 생성**
- 목적: M2 시작 시점 이전의 MySQL FactEntries / RagDocuments / RagObjects / Texts 의 모든 row 를 Postgres 로 backfill. 동시에 `texts.embedding` 컬럼의 embedding 을 일괄 생성 (OpenAI `text-embedding-3-small` default, 또는 로컬 모델 — §2.1.4 의 `AGENT_KB_EMBEDDING_MODEL` toggle). M1 결정에 따라 embedding 은 TextHash 별 단일 — 동일 TextHash 의 fact_entries / rag_documents / rag_objects 가 자연 참조 (Blocker B-4).
- 산출: `bin/kb-backfill.sh` — resumable + progress 로그 + chunked PK pagination + idempotency. **Idempotency 키 (Section B 권고)**: 자연키 (Conv × Scope × FactKey × Fingerprint) 기반의 `ON CONFLICT (conv_id, scope_key, fact_key, fingerprint) DO NOTHING` — Postgres 측 SERIAL id 와 무관. **Resume 전략 (Section B 권고)**: embedding API 부분 실패 시 `embedding IS NULL AND text_hash IS NOT NULL` row 만 재처리 + per-row try/except + retry queue + `AGENT_KB_EMBEDDING_MAX_ATTEMPTS=3`.
- 검증: backfill 완료 후 양쪽 row count 일치 + 모든 Postgres `texts` row 의 `embedding IS NOT NULL` + `bin/kb-dual-write-verify.sh` 100% 정합 (M-1 baseline 의 row count + M2 dual-write 의 새 row 합산).
- 위험도: Major (대용량 데이터 이동 + 외부 embedding API 호출 비용).
- Embedding cost 추정 (outside-voice review Section E #4): M-1 baseline 의 `texts` row 수 측정 후 정확 추정 가능. row 수 ~수천 가정 시 `text-embedding-3-small` USD 0.02/1M tokens × 평균 500 tokens/row ≈ USD 0.01~0.5. **plan 의 "USD <100" estimate 는 over-budgeted** 이나 §12.1 외부 비용 조항의 confirm trigger 는 유지 (보수적).
- 사람 승인: PLAN-APPROVED 범위. 단 M-1 baseline 측정 후 cost estimate 가 USD 100 초과로 판명되면 별도 사람 confirm.

**M4 — Cutover (read path 전환)**
- 목적: read path (knowledge.py 의 `_load_kb_entries`, utils.py 의 `_load_rag_documents_for_request` / `_load_rag_objects_for_request` 등) 를 Postgres 로 전환. MySQL 측은 read-only mode 진입.
- 산출: read helper 의 모든 query path 가 `_pg_connect()` 사용. `AGENT_KB_READ_BACKEND=postgres` 환경변수 (M4 진입 시 1, M5 까지 유지).
- 검증 게이트 (`bin/kb-cutover-readiness.sh`):
  - backfill 완료 + dual-write 1주일 정합 fail rate < 0.01% (B-3 분모 정의 적용)
  - ANCHOR §3 invariant 시나리오 6종 (§2.1.6) PASS — 자동화 (`tests/test_anchor_invariant_postgres.py`)
  - **`make ask` 회귀 5종 catalog (Blocker B-10)** PASS — M-1 의 S1~S5 시나리오 (동일 질문, expected 답변 정확성 + insight_route.log path).
  - **Latency 정량 임계 (Blocker B-6)** — M-1 baseline 대비 p99 latency 증가 **50% 이내**. 50% 초과 시 cutover 차단. 임계 초과 사유가 pgvector ANN tuning (probes / lists) 으로 해결 가능하면 M3 으로 복귀 후 재진입.
  - **EXPLAIN ANALYZE 비교 (Open Q #13)** — 주요 query 5건의 Postgres `EXPLAIN ANALYZE` 결과가 ivfflat/hnsw index 사용 확인 (Seq Scan 아님).
  - **ADR-0021 작성 완료 (Blocker B-9)** — `docs/DECISIONS.md` 에 ADR-0021 (KB Postgres 분리 후 RBAC catalog 재정의) entry 가 본 cycle 시작 전 완료.
- 위험도: **Critical** — rollback path 가 명확하지 않은 시점. read backend 전환은 in-place 이므로 cutover 자체는 빠르나 회귀 시 영향 큼.
- 사람 승인: 필수 (별도 confirm + REPORT.md 에 cutover 결정 기록).
- **Rollback window 3단계 (Blocker B-5)**:
  - **Stage A (cutover 직후 ~ M4 cycle 종료 전)**: `AGENT_KB_READ_BACKEND=mysql` 환경변수 1줄 변경 + agent 컨테이너 재기동 — full rollback. MySQL 측 정합이 dual-write 로 보존되어 있음.
  - **Stage B (M4 종료 ~ M5 진입 전)**: dual-write 유지 + read 만 Postgres. rollback 시 MySQL 측 데이터 정합이 여전히 보존되므로 1줄 변경으로 rollback 가능. M5 진입 전까지가 안전 window.
  - **Stage C (M5 cleanup 후)**: MySQL DROP TABLE 완료 → **rollback = 데이터 손실** (M5 의 mysqldump 보관 ETL 역방향 복원 필요). 따라서 M5 진입 결정은 별 cycle 의 PLAN-APPROVED + 사람 confirm.

**M5 — Cleanup (MySQL KB 정본 제거)**
- 목적: M4 cutover 후 2주일 무회귀 확인 후 MySQL 측 KB 5종 정본 drop (또는 read-only deprecated 상태로 유지). dual-write 로직 제거.
- 산출: `modules/knowledge.py`, `modules/insight.py` 의 `_dual_write_kb()` 호출 제거 + MySQL DDL drop (`DROP TABLE AgentMemoryFactEntries` 등).
- 검증: `make ask` 5종 회귀 + 정책 doc (§11.3, §14.1, §15.6, §15.7) 의 최종 갱신 (MySQL 측 KB 정본 참조 제거).
- 위험도: **Critical** — DROP TABLE 은 §12 의 "파괴적 데이터 변경" 에 해당. 사람 승인 필수.
- 사람 승인: 필수 (§12.1 BLOCKED: awaiting-human-approval).
- rollback: backfill 의 역방향 ETL 필요 — drop 전 mysqldump 보관 권장 (M5 의 사전 단계로 dump artifact 보관).

#### 2.1.4 환경변수 신설 (§14.1 갱신 대상)

```bash
# Postgres KB connection (M0~M5 전반)
AGENT_KB_PG_HOST=postgres
AGENT_KB_PG_PORT=5432
AGENT_KB_PG_DB=agent_kb
AGENT_KB_PG_USER=agent_kb_rw
AGENT_KB_PG_PASSWORD=<secret>
AGENT_KB_PG_SSLMODE=prefer

# Read backend 전환 (M4 cutover)
AGENT_KB_READ_BACKEND=mysql   # M0~M3: mysql, M4~M5: postgres
AGENT_KB_DUAL_WRITE=0         # M0~M1: 0, M2~M5 진입까지: 1, M5 후: 0

# Embedding 관리 (M3 backfill + 이후 incremental)
AGENT_KB_EMBEDDING_MODEL=text-embedding-3-small
AGENT_KB_EMBEDDING_DIM=1536
AGENT_KB_EMBEDDING_BATCH_SIZE=50
AGENT_KB_EMBEDDING_TIMEOUT_SEC=30

# ANN index (M1 schema + M4 query)
AGENT_KB_ANN_INDEX_TYPE=ivfflat   # or hnsw
AGENT_KB_ANN_LISTS=100            # ivfflat lists 파라미터
AGENT_KB_ANN_PROBE=10             # query 시 probe 개수
AGENT_KB_ANN_RECALL_TARGET=0.95   # SLA — recall 측정 시 임계
```

기존 `AGENT_KB_*` 변수 (예: `AGENT_KB_COVERAGE_MODE`, `AGENT_KB_REQUIRE_EVIDENCE`, `AGENT_KB_PREFETCH_ON_ASK`) 는 backend 와 무관하게 유지된다.

#### 2.1.5 RBAC catalog hook (별 cycle — outside-voice review 필수)

본 plan 은 RBAC catalog 신설 자체를 포함하지 않는다 (별 ADR + 별 cycle). 다만 본 마이그레이션이 RBAC 의 hook point 를 변경할 가능성이 있으므로 plan-review 단계에서 outside-voice 가 다음 3개 항목을 검증해야 한다.

1. **Storage 권한 매핑** — 현재 RBAC catalog (있다면 `docs/SECURITY.md` 의 RBAC 표 참조) 의 `kb.*` 또는 `memory.*` 권한이 MySQL connection 단위로 정의되어 있는지. Postgres 분리 후 `agent_kb_rw` / `agent_kb_ro` 두 role 신설 필요 가능성.
2. **`kb.read.any` / `kb.write.any` 의 의미 변화** — 사용자 메시지가 명시한 "storage 이전 후 재정의" — 본 plan 의 outside-voice review 가 이 catalog 항목의 정의가 MySQL 의 row-level vs Postgres 의 schema-level 권한 모델 사이에서 어떻게 mapping 되는지 확인.
3. **정적 catalog blindspot** — 메모리 정책 (`feedback_outside_voice_for_rbac.md`) 이 명시한 정적 catalog 의 blindspot. outside-voice review 가 dynamic grant 흐름까지 검토.

본 §2.1.5 의 결과는 outside-voice review 결과 (§2.1.7) 와 합쳐 별 ADR (예: ADR-0021 "KB Postgres 분리 후 RBAC catalog 재정의") 에 정본 기록.

#### 2.1.6 ANCHOR §3 invariant 보존 검증

ANCHOR.md §3 의 가정된 사용 시나리오:
> insight-worker의 기존 복구 로직을 건드려야 할 때: 새 AI 세션이 REPORT.md를 읽으면 `fact/RAG/Text/Object 4종 완전성 확인 → 기존 fact 기반 복구 가능 시 즉시 복구 → 복구 불가 시에만 LLM 재생성` 순서가 명시되어 있다. 이 순서를 뒤집으면 LLM 호출 비용이 폭발한다.

**보존 방법**:
1. `modules/insight.py` 의 `_check_artifact_completeness()` + `_repair_from_fact()` 흐름은 storage 추상화 (`KbBackend` 인터페이스, M2 도입) 뒤에서 동일하게 작동.
2. M2 dual-write phase 의 검증 항목에 "fact 기반 복구 시나리오 1건 (`test_artifact_repair_postgres.py`)" 추가 — Postgres 측 fact_entries 에서 RagDocuments 가 누락된 row 를 인위적으로 만든 후, repair 흐름이 정상 동작하는지 확인.
3. M4 cutover 직전 게이트 (`bin/kb-cutover-readiness.sh`) 에 "fact-우선 복구 시나리오 PASS" 를 명시 게이트 항목으로 추가.
4. ANCHOR.md §3 의 본문은 변경 없음. §1 의 외부 관점에 "왜 KB 가 별도 Postgres 인스턴스인가?" 추가 — M0 cycle 에서 함께 갱신.

#### 2.1.7 Open Questions (outside-voice review 가 답해야 할 항목)

1. **D-1 Sequencing** — 권장 default (A: 선행 + M3~M5 와 Sprint 4 병행) 가 Sprint 4 의 D RAG schema 복잡도와 정합한가? Sprint 4 의 D RAG 가 본 plan 의 `agent_kb.rag_objects` 와 schema 공유 가능한가, 별 namespace 인가?
2. **D-2 Topology** — 단일 cluster + 별 database 권장 default 가 prod / dev / WSL 환경 차이에서 안정적인가? docker-compose 의 메모리 footprint 추정.
3. **D-3 Module rewrite** — raw psycopg3 + pgvector adapter 권장 default 가 7,500+ LOC raw SQL 의 dialect 변환 비용을 충분히 커버하는가? 자동 dialect 변환 도구 (예: `pgloader` 의 SQL 변환) 의 사용 가능성.
4. **Embedding cost** — M3 backfill 의 OpenAI embedding 호출 비용 추정 (현재 KB row 추정 ~수천 ~ 수만). 로컬 모델 (예: `sentence-transformers/all-MiniLM-L6-v2`) 대안.
5. **RBAC catalog** — §2.1.5 의 3개 항목. 정적 catalog 의 blindspot 검토.
6. **`ivfflat` vs `hnsw` index** — RAG row 수 + 쿼리 패턴 (D0~D3 라우팅의 selectivity) 기준으로 어느 index 가 적합한가? `AGENT_KB_ANN_INDEX_TYPE` default 결정.
7. **Cutover rollback path** — M4 cutover 후 회귀 발견 시 `AGENT_KB_READ_BACKEND=mysql` 1줄 변경으로 충분한가? dual-write 가 M5 까지 유지되므로 데이터 정합은 보존되나, 어느 시점부터 MySQL 측 정합이 손상되기 시작하는가?
8. **Sprint 4 D RAG 와의 schema 공유** — 직전 multi-cycle plan 의 Sprint 4 가 정의한 D RAG schema 가 본 plan 의 `rag_documents` / `rag_objects` 와 어떻게 다른가? 본 cycle 에서는 Sprint 4 plan 정본을 확인할 수 없음 — outside-voice review 가 사용자에게 직접 확인 요청.

#### 2.1.8 검증 체크리스트 (각 phase 종료 시점)

각 phase 별 별도 verify-completion 호출. 5종 정본 + ANCHOR §3 invariant 가 모든 phase 의 공통 검증 항목.

| Phase | 검증 항목 | 게이트 |
|---|---|---|
| M0 | docker-compose `postgres` 서비스 healthy + `_pg_connect()` PASS + 기존 MySQL 흐름 무영향 | `make ask` 회귀 5종 PASS |
| M1 | Postgres DDL 적용 + schema-compare 결과 컬럼 정합 일치 | `bin/kb-schema-compare.sh` exit 0 |
| M2 | dual-write 1주일 fail rate < 0.01% + ANCHOR §3 invariant 시나리오 PASS | `bin/kb-dual-write-verify.sh` 7일 누적 PASS |
| M3 | backfill 완료 + 양쪽 row count 일치 + 모든 Postgres row 의 `embedding IS NOT NULL` + embedding cost 기록 | `bin/kb-backfill.sh --verify` exit 0 |
| M4 | cutover readiness 게이트 PASS + `make ask` 회귀 5종 PASS + ANCHOR §3 invariant 시나리오 PASS | `bin/kb-cutover-readiness.sh` exit 0 + 사람 승인 |
| M5 | 2주일 무회귀 + MySQL drop 전 dump 보관 + 정책 doc 최종 갱신 | 사람 승인 + REPORT.md cutover 결정 기록 |

#### 2.1.9 위험도 (§12.3) — phase 별 (outside-voice NEEDS-TWEAK 반영)

| Phase | 위험도 | 사람 승인 |
|---|---|---|
| M-1 | Minor (read-only baseline 측정) | 불요 (PLAN-APPROVED 범위) |
| M0 | Minor (비파괴 추가 — docker-compose + connection helper) | 불요 (PLAN-APPROVED 범위) |
| M1 | **Major (Postgres role 신설 = 인증/인가 변경, Blocker B-8)** | **필수** — `agent_kb_rw` / `agent_kb_ro` role 권한 모델은 §12.1 사람 승인 대상 + ADR-0021 작성 시작 |
| M2 | Major (write path 침습 + KbBackend 추상화 도입) | PLAN-APPROVED 범위 (Pre-approved Changes — 비파괴적 추가) |
| M3 | Major (대용량 데이터 이동 + 외부 embedding cost) | PLAN-APPROVED 범위 + embedding cost > USD 100 시 별도 confirm (M-1 baseline 후 정확 추정) |
| M4 | Critical (read backend 전환 + ADR-0021 게이트) | 필수 — 별도 confirm + REPORT.md cutover 결정 기록 + ADR-0021 작성 완료 + latency 임계 PASS |
| M5 | Critical (파괴적 데이터 변경 — DROP TABLE) | 필수 — §12.1 BLOCKED: awaiting-human-approval + mysqldump 보관 ETL 사전 완료 |

#### 2.1.10 outside-voice review 호출 시점 + 방식

본 cycle (TASK-0015, plan 작성) 단계에서 1회 ✓ **완료** — `REVIEW.md REV-20260520-0002` 정본:
- 호출 channel: Plan subagent (Software architect agent) — `feedback_outside_voice_for_rbac.md` 정책의 "Codex/subagent 외부 시각 항상 호출" 충족.
- 입력: 본 §2.1 전체 + REVIEW.md `REV-20260520-0001` 의 trade-off 기록 + ANCHOR §3 invariant + 관련 src 모듈.
- 검증 결과: **NEEDS-TWEAK** — 11 Blocker + 5 Nice-to-have. 본 §2.1 본문에 반영 완료 (§2.1.11 추적 표 참조).
- Verdict 변환: 11 Blocker 가 §2.1 본문 또는 §2.1.11 의 명시 게이트 항목으로 반영되어 PLAN-APPROVED 진행 가능 상태로 전환.

추가 호출 시점 (Execute 단계):
- **M2 → M3 진입 직전**: dual-write 정합성 시나리오 + KbBackend 추상화 인터페이스 catalog 검토 — 별 cycle 의 plan-review 에 다시 outside-voice.
- **M3 → M4 진입 직전**: cutover readiness 게이트 검토 — Critical 진입이라 outside-voice 필수. ADR-0021 작성 완료 검증 포함.

#### 2.1.11 Outside-voice NEEDS-TWEAK 반영 추적

`REV-20260520-0002` 의 11 Blocker 가 §2.1 본문 어디에 반영되었는지 추적. 사용자 PLAN-APPROVED 마커 부여 전 각 항목 확인 권장.

| ID | Blocker | 반영 위치 | 반영 방식 |
|---|---|---|---|
| **B-1** | D-1 Sequencing 조건부 default (Sprint 4 schema 확인 분기) | §2.1 status / §2.1.1 D-1 표 / §2.1.7 Open Q #1+#8 / §7 Next Action | 사용자 직접 확인 항목 — Sprint 4 D RAG schema 가 KB rag_objects 와 공유 가능 여부 명시 확인 후 A/C 분기. PLAN-APPROVED 마커 시점에 사용자가 답변. |
| **B-2** | M0 이전 baseline 측정 phase 추가 (row count + latency + EXPLAIN + 비-KB JOIN audit + RBAC audit) | §2.1.3 신규 **M-1** phase | M0 이전 별 cycle 로 추가. 5종 측정 + JSON artifact 보관. M4 cutover gate 의 비교 대상. |
| **B-3** | M2 검증 정합 정의 (fail rate 분모 + synthetic load) | §2.1.3 M2 검증 게이트 | "M2 시작 이후 새 row 만 분모" + `bin/kb-dual-write-stress.sh` synthetic load (강제 insight 3회 + ask 5회). |
| **B-4** | M3 embedding 저장 schema 결정 | §2.1.3 M1 산출 / M3 목적 | **`texts.embedding` (TextHash 별 단일)** 채택. `fact_entries.embedding` / `rag_objects.embedding` 컬럼 없음. 동일 TextHash 의 다른 row 재embed 불요. |
| **B-5** | M4 rollback window 3단계 명시 | §2.1.3 M4 Rollback window | Stage A (cutover 직후) / Stage B (M5 진입 전) / Stage C (M5 cleanup 후) 의 rollback 가능성 차별. |
| **B-6** | M4 latency 정량 임계 | §2.1.3 M4 검증 게이트 | M-1 baseline 대비 p99 latency 증가 50% 이내. 초과 시 cutover 차단. |
| **B-7** | ANCHOR §3 invariant 시나리오 6종 catalog | §2.1.6 보존 방법 + M2 게이트 + `tests/test_anchor_invariant_postgres.py` | 시나리오 카탈로그 6종 자동화 + LLM 호출 0건 negative assertion. |
| **B-8** | RBAC role 신설 위험도 격상 + 사람 승인 | §2.1.9 위험도 표 M1 (Minor → Major) + §2.1.3 M1 사람 승인 | M1 의 `agent_kb_rw` / `agent_kb_ro` 신설 = 인증/인가 변경 → 사람 confirm 필수. |
| **B-9** | ADR-0021 (RBAC catalog 재정의) 작성을 M4 cutover 전 게이트 명시 | §2.1.3 M1 + M4 + §2.1.5 | M1 cycle 에서 ADR-0021 작성 시작 + M4 cutover gate 의 명시 항목. |
| **B-10** | `make ask` 5종 시나리오 구체 catalog | §2.1.3 M-1 (S1~S5 명시) + M4 게이트 | S1 단순 / S2 follow-up / S3 모호 / S4 메타탐색 / S5 복구 — 각 N=10 회 반복 + 정확성 + insight_route.log path 확인. |
| **B-11** | 정책 doc 갱신 목록 보강 | §2.1.2 영향 파일 (Policy docs) | `docs/ARCHITECTURE.md` + `docs/LEARNINGS.md` + `FUNCTION.md §10` (Postgres 16 + pgvector extension 외부 의존성) 추가 필요. **본 plan 의 §2.1.2 Policy docs 목록을 사용자가 확인 시점에 인지 + 별 cycle 의 META commit 에 반영.** |

§2.1.7 Open Questions 의 추가 항목 (outside-voice 가 식별):
- **#9 — 비-KB JOIN audit**: KB 테이블과 `AgentMemoryConversations` / `AgentMemoryMessages` / `AgentMemorySteps` 의 cross-table JOIN 가능성. M-1 phase 의 audit 항목으로 흡수.
- **#10 — `AgentMemoryFacts` VIEW 의 Postgres 정의**: M1 phase 의 `agent_kb_schema.sql` 에 명시 항목으로 흡수.
- **#11 — embedding 모델 vendor lock-in fallback**: 모델 교체 시 dim 변경 + backfill 재실행 전략. Nice-to-have (별 ADR).
- **#12 — Latency baseline 측정**: M-1 phase 에 흡수.
- **#13 — EXPLAIN ANALYZE 검증**: M4 cutover gate 의 명시 항목으로 흡수.

Nice-to-have (PLAN-APPROVED 후 별 cycle / 별 ADR — 본 §2.1 의 게이트 항목 아님):
- D-3 dialect 변환 카탈로그 (M1 산출 권장)
- M5.5 post-cleanup canary 1주일
- EXPLAIN ANALYZE 비교 자동화 (M4 gate 의 수동 검증을 M5 후 자동화)
- embedding 모델 vendor lock-in fallback (Open Q #11)
- transactional partial failure 정책 (Section C 권고, M2 보강 가능)

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 -->
<!-- Sprint 4 D RAG schema 확인 (Blocker B-1) 는 M1 cycle 진입 전 별도 확인 필수 -->
<!-- M1 (RBAC role 신설), M4 (cutover), M5 (DROP TABLE) 은 각 phase 진입 시점에 별도 사람 confirm 유효 -->

### 2.2 Previous Plan — insight-worker 4종 완전성 + repair_from_fact + log 재편 (완료, 보존)

본 §2.2 는 TASK-0001~0009 의 historical plan 이다. 본 cycle (TASK-0015) 와 무관하며 historical reference 로 보존된다.

- **영향받는 파일:** `unit/feature-0002-agent-core/src/modules/insight.py`, `unit/feature-0002-agent-core/src/modules/utils.py`, `unit/feature-0002-agent-core/docs/TASK.md`, `unit/feature-0002-agent-core/docs/REPORT.md`, `unit/feature-0002-agent-core/docs/MODIFY.md`, `unit/feature-0002-agent-core/docs/TEST.md`, `AGENTS.md`
- **접근 방법:** 현재 worker 후보 선정 로직에 `4종 아티팩트 완전성 검사`를 추가해 `fingerprint` 만 남고 실제 insight 데이터가 누락된 객체를 다시 처리한다. 이미 fact 텍스트가 남아 있는 경우에는 기존 fact 기반으로 RAG/Text/Object 를 즉시 복구하고, 복구 불가 시에만 LLM 재생성을 수행한다. 로그는 `/shared/logs/YYYY-MM-DD/` 구조로 재정렬하고, 오래된 일자 디렉토리는 `archive/YYYY-MM-DD.tar.gz` 로 압축한다.
- **기준선:** `table_fp:*` `154`, `table_insight` fact `28`, `table_insight` RAG object `28`, fact 자체가 없는 incomplete table `126`, `insight_worker.log` 루트 평면 누적, `insight_route.log` 부재
- **위험도:** Major
- **완료 cycle**: TASK-0001 ~ TASK-0009 (TASK-0010, TASK-0011 은 commit/push 마무리만 남음 — §3 Task Queue 참조). 본 plan 의 정본 invariant 가 ANCHOR.md §3 으로 승격됨.

## 3. Task Queue
- [x] TASK-0001 원본 더티 워크트리 상태 기록 및 보존 전략 확정
- [x] TASK-0002 별도 worktree와 내부 작업 브랜치 생성
- [x] TASK-0003 누락 원인 재현과 기준선 수치 확인
- [x] TASK-0004 로그 유틸을 일자 디렉토리 + 7일 후 tar.gz 보관 구조로 개편
- [x] TASK-0005 insight 후보 선정에 아티팩트 완전성 검사 추가
- [x] TASK-0006 기존 fact 기반 복구 + 복구 실패 시 LLM 재생성 경로 추가
- [x] TASK-0007 worker 상세 추적 로그에 실제 참조 schema/table/column 기록 추가
- [x] TASK-0008 실제 insight cycle 실행 후 누락 복구/로그 생성 검증
- [x] TASK-0009 REPORT/MODIFY/TEST/AGENTS 문서 갱신
- [x] TASK-0010 작업 브랜치 commit 후 clean integration worktree에서 cherry-pick/push
- [x] TASK-0011 원본 워크트리 더티 상태 동일성 재확인
- [x] TASK-0012 ANCHOR.md §1-§3 작성 (template v3.2.0-rc.1 external anchor 도입)
- [x] TASK-0013 Role scope 시스템 프롬프트 공통 누적 적용
- [x] TASK-0014 Account scope 누적 + Product → Role → Account 순서 정정
- [x] TASK-0015 (Critical §12.3) KB 정본 MySQL → Postgres pgvector 마이그레이션 plan 정본 작성 + outside-voice review + PLAN-APPROVED 마커 (commit `6ac2288`)
- [x] TASK-0016 (Minor §12.3) M-1 사전 baseline 측정 4/5 + `bin/kb-measure-baseline.sh` 신규 + `artifacts/shared/kb-baseline-2026-05-20.json` 정본 (commit `8db796c`)
- [x] TASK-0017 (Minor §12.3) M0 인프라 도입 — docker-compose `postgres` 서비스 + `.env.example` AGENT_KB_PG_* + requirements.txt psycopg + db.py `_pg_connect()` + `bin/kb-pg-healthcheck.sh` + `bin/kb-measure-baseline.sh --latency` mode (commit `63f5833`)
- [x] TASK-0018 (Major §12.3) M1 Postgres DDL + RBAC role 신설 + ADR-0021 (commit `8152ce9`)
- [x] TASK-0019 (Major §12.3) M2-a dual-write 준비 — KbBackend ABC + skeleton + Blocker 1-4 해소 (commit `8dc6d8c`)
- [ ] TASK-0020 (Major §12.3, **본 cycle**) M2-b dual-write 본 구현 — KbBackend method body 12 + `_DualWriteMirror` helper + caller 5 위치 mirror 호출 + 10 unit test + outside-voice REV-20260520-0008 Critical 6 / Blocker 2 본 cycle 내 반영. M2-c (cross-DB audit explicit call + 7-day SLA + invariant test fixture) 별 cycle 위임.

## 4. In Progress
- TASK-0020 M2-b dual-write 본 구현 — method body + caller 5 + 10 unit test + Critical/Blocker 반영 완료, M2-c cycle (cross-DB audit + 7-day SLA + invariant test fixture) 대기.
- TASK-0010 작업 브랜치 commit 및 integration 반영 준비 (historical, 본 cycle 과 별개)

## 5. Blocked
- 없음 (TASK-0015 PLAN-APPROVED 마커 부여 완료, 본 cycle 의 outside-voice REV-20260520-0008 Critical 6 + Blocker 2 본 cycle 내 반영 완료).

## 6. Done
- TASK-0001 ~ TASK-0009
- TASK-0012, TASK-0013, TASK-0014
- TASK-0015 (commit `6ac2288` + main ff-merge 2026-05-20)
- TASK-0016 (commit `8db796c` + main ff-merge 2026-05-20)
- TASK-0017 (commit `63f5833` + main ff-merge 2026-05-20)
- TASK-0018 (commit `8152ce9` + main ff-merge 2026-05-20)
- TASK-0019 (commit `8dc6d8c` + main ff-merge 2026-05-21)

## 7. Next Action
1. (본 cycle) verify-completion PASS + commit + push + main ff-merge + worktree cleanup.
2. (사용자 별 turn — TASK-0017 / 0018 / 0019 / 0020 통합 runtime 검증):
   - main worktree 에서 `git pull --ff-only` (origin/main 의 본 cycle commit 흡수)
   - `.env` 의 `AGENT_KB_PG_*` 8 변수 채움 (HOST/PORT/DB/USER/PASSWORD/SSLMODE + RW/RO PASSWORD + AGENT_KB_PG_REQUIRED + KB_DUAL_WRITE_START_TS)
   - `make start` 재기동 → postgres 컨테이너 가동 + memory-init `_ensure_pg_schema()` 자동 호출 + `grants_present` 검증 PASS
   - `bin/kb-pg-healthcheck.sh --all` + `bin/kb-pg-role-bootstrap.sh --all` + `bin/kb-schema-compare.sh` PASS (TASK-0017/0018 통합 검증)
   - `AGENT_KB_PG_USER=agent_kb_rw` 전환 + agent 재기동 → fact write 시 `_DualWriteMirror` 가 양쪽 INSERT
3. (**M2-c cycle**, 별 worktree) Cross-DB audit + 7-day SLA + integration test fixture:
   - `_DualWriteMirror._mirror()` 안에서 mirror 성공 시 `WebAuditEvents` audit row INSERT (ActionCode `kb.write.mirror`)
   - `bin/kb-dual-write-verify.sh --audit-sla` 본문 구현 + miss_rate ≤ 0.1% target 검증
   - `bin/kb-dual-write-stress.sh --insight-cycles 3 --ask-iterations 10` 7-day stress run
   - `tests/test_anchor_invariant_postgres.py` 의 6 시나리오 + 2 negative assertion fixture/assertion 실 구현 (S1-S6 + N1 LLM 0건 + N2 TRUNCATE)
   - Nice-to-have 5건 (LC_COLLATE / tsvector simple / `_BACKENDS_CACHE` thread-safe lock / psycopg autocommit docstring / MysqlKbBackend caller drift 방지)
4. (별 cycle, M2~M4 사이) `PERMISSION_DEFINITIONS` 의 `kb.*` 4 항목 추가 (`kb.read.own` / `kb.read.any` / `kb.mutate.any` / `kb.export`) + `docs/SECURITY.md` 갱신.
5. (별 cycle, M2~M4 사이) **Dynamic grant blindspot cycle** (ADR-0021 §후속 액션) — `WebPermissions IsDynamic=1` 패턴의 `kb.*` 적용 검증.
6. (별 cycle, M3) Backfill ETL + embedding 일괄 생성 — `bin/kb-backfill.sh` + `texts.embedding` (Blocker B-4 결정). Embedding cost USD <0.01 추정 (M-1 baseline 기준).
7. (별 cycle, M4) Cutover — read backend 전환 + FULLTEXT → pg_trgm rewrite + EXPLAIN ANALYZE 비교 게이트 + ADR-0021 의 §후속 액션 게이트 항목 모두 완료 확인.

## 8. Completion Checklist (TASK-0020 — M2-b dual-write 본 구현 cycle)
- [ ] `unit/feature-0002-agent-core/src/modules/kb_backend.py` rewrite (~780 LOC: ABC + `prune_fact_entries_keep_top` 보강 + MysqlKbBackend 6 method body + PgKbBackend 6 method body + `_DualWriteMirror` helper + `_dual_write_kb` singleton + `_BACKENDS_CACHE` process-level cache)
- [ ] Caller 5 위치 mirror 호출 (utils.py:957 _text_store_insert + utils.py:1179 RagDoc + utils.py:1230 RagObj + knowledge.py:633 _publish_fact + knowledge.py:598 _prune_fact_entries_for_key)
- [ ] `unit/feature-0002-agent-core/tests/test_dual_write_mirror.py` 신규 (10 unit test: no-op / silent log / fail-loud / 성공 / ABC / cache / set_text_embedding / MysqlKbBackend / caller integration / caplog)
- [ ] `unit/feature-0002-agent-core/tests/conftest.py` 신규 (sys.path 통합)
- [ ] `docs/DECISIONS.md` ADR-0021 §Consequences 보강 (Cross-DB audit M2-c cycle 책임)
- [ ] Outside-voice review (Plan subagent, `REV-20260520-0008`) 호출 + Verdict NEEDS-TWEAK + Critical 6 / Blocker 2 본 cycle 내 반영:
  - [ ] Critical 1+2+3: caller 4 위치 silent/fail-loud pattern 통일 (knowledge.py:677-696 dead try/except 제거 + `_prune_fact_entries_for_key` 광역 swallow 분리)
  - [ ] Critical 4: REPORT.md §4 risk log 0번 entry (latency baseline 측정 M2-c 책임)
  - [ ] Critical 5: test isolation (conftest.py + dual import path 제거)
  - [ ] Critical 6: caller actual call test (Test 9 `_text_store_insert` + mock cursor + spy mirror)
  - [ ] Blocker 7+8: ADR-0021 §Consequences M2-c cycle 책임 명시
- [ ] py_compile (kb_backend.py + knowledge.py + utils.py) PASS + bash -n + test compile PASS
- [ ] `bin/verify-completion.sh --pre-commit feature-0002-agent-core` PASS
- [ ] Git 커밋 (`Task-Cycle: feature-0002-agent-core` trailer) + push + main ff-merge + worktree cleanup

## 9. Completion Checklist (TASK-0019, TASK-0018, TASK-0017, TASK-0016, TASK-0015 — done, 보존)
TASK-0019 (M2-a):
- [x] KbBackend ABC + skeleton + Postgres SQL 템플릿 + Blocker 1-4 해소 + Critical 4 / Blocker 3 본 cycle 내 반영
- [x] verify-completion PASS (10/10) + commit `8dc6d8c` + push + main ff-merge

TASK-0016, TASK-0015, TASK-0017, TASK-0018 (보존):
TASK-0016 (M-1 baseline 측정):
- [x] `bin/kb-measure-baseline.sh` 신규 + 4/5 측정 + JSON artifact + REPORT/MODIFY/REVIEW 갱신
- [x] verify-completion PASS (10/10) + commit `8db796c` + push + ff-merge

TASK-0015 (plan-review):
- [x] §2.1 plan 정본 작성 완료
- [x] REVIEW.md `REV-20260520-0001` + `REV-20260520-0002 [SUBAGENT:Plan-subagent]`
- [x] MODIFY.md `CHG-20260520-0001`
- [x] REPORT.md §1·§4·§7 plan-review 상태 표면화 + PLAN-APPROVED 후 갱신
- [x] outside-voice review (Plan subagent, NEEDS-TWEAK + 11 Blocker 반영)
- [x] PLAN-APPROVED 마커 부여 (ms.mckim.gpt@gmail.com on 2026-05-20)
- [x] verify-completion PASS (10/10 checks)
- [x] commit `6ac2288` + push + main ff-merge + worktree cleanup

### AR-M4-read — PgRuntimeBackend read 메서드 구현 (2026-05-27)
- [x] `PgRuntimeBackend` 에 10개 read 메서드 추가 — SQL 상수 이미 정의됨 (CHG-20260527-AR-M4-read): load_kv / load_kv_all / load_kv_by_key / load_kv_by_key_value / load_summary / load_messages / load_steps / list_conversations / load_core_messages / get_conv_messages_full. MySQL fallback 제거로 인해 `agent_memory.agentmemorykv` 없음 오류 해소.

### TASK-0121 — AR-M5 PG cutover 잔존 MySQL 쿼리 차단 (2026-05-27)
- [x] `delete_conversation`: `_pg_delete_conversation()` 신규 — PG agent_runtime + public KB 테이블 삭제 + MySQL try/except 보호
- [x] verify-completion PASS + commit + push + main ff-merge

### TASK-0121 — delete_conversation + ask_status 500 오류 수정 (2026-05-27)
- [x] memory.py `delete_conversation`: `_pg_delete_conversation()` 헬퍼 추가 (CHG-20260527-CONV-DELETE-PG)
  - PG: agent_runtime.kv 수동 + core_conversations CASCADE + public KB 3테이블
  - MySQL DELETE: try/except 보호 (테이블 DROP 후 silent fail)
- [x] app.py `_load_latest_assistant_message`: PG routing 추가 (CHG-20260527-ASK-STATUS-PG)
  - agent_runtime.messages WHERE role='assistant' ORDER BY id DESC LIMIT 50
  - JSONB dict → json.dumps() 직렬화 → 기존 json.loads() 루프 호환
- [x] py_compile 양 파일 구문 확인 OK
- [x] feature-0002 pytest 146 PASS / 2 SKIP 유지 확인
- [x] Docker 재빌드 + 재배포 (web + insight-worker)
- [x] 기능 검증: ask_status 200 + delete_conversation 200 확인 (실서비스)
- [x] verify-completion + 커밋 + push + main ff-merge

### TASK-0174 — "전체 N행 미리보기" 링크 오정렬 수정 (2026-06-09)
- [x] 근본: `_collapse_large_tables` 위치-인덱스 매칭 → 값 토큰 overlap + 컬럼수 폴백 매칭으로 교체 (`_distinctive_tokens`/`_md_table_body_cells`/`_md_table_col_count`/`_csv_signatures`/`_match_csv_for_table`). 형태 불일치 보조쿼리(MIN/MAX) CSV 배제.
- [x] 회귀 테스트 `tests/test_collapse_table_csv_match.py` (값매칭·무매칭생략·형태폴백·토큰필터 4종)
- [x] make test 컨테이너 PASS (0 fail) + ruff PASS
- [x] §18.8 검증 패널(SUBAGENT) → REV-20260609-0173, MAJOR 2건(측정값-only 표 링크소실/JS 오탐) FIX-FIRST 반영(컬럼수 폴백 + JS 임계≥2)
- [x] verify-completion PASS(9 checks) → 커밋 → push → main ff-merge(2b4da2a) → 재배포(web+ask-worker, healthz git_commit 일치·베이킹/서빙 확인) → 라이브 PB-0008 무회귀 확인 (collapse+링크 경로는 LLM 렌더 비결정성으로 온디맨드 재현 불가 — 회귀테스트가 결정적 증거)

### TASK-0175 — 실행 단계 reason(왜) derived fallback (2026-06-09)
- [x] **Minor §12.3** — 사용자 "각 단계 근거가 화면에 안 보인다" 재보고. 라이브 진단: 모든 step `work_source='derived'`·`reason_text=''`. 근본 ① SYSTEM_PROMPT 가 LLM 에 tool_notes(work/reason) 방출 미지시 → reason 미생성, ② reason 에 derived fallback 부재(work 와 달리). CHG-0173 프런트는 빈 reason 미표시라 표시할 데이터 자체가 없었음. (CHG-20260609-0175)
- [x] `_derive_step_reason(tool_name, args)` 신규 — `_derive_step_work` 대칭, tool 목적별 결정적 근거(execute_sql 은 집계/조회 분기). 미지원 tool=`""`.
- [x] 루프 배선: work 파생 직후 reason 도 비면 파생 + `reason_source='derived'`. LLM 참값 비덮어쓰기 가드.
- [x] 회귀 테스트 `tests/test_derive_step_reason.py` 4종(전 tool 비빔·집계vs조회·미지원 빈값·대소문자/None 방어). make test 컨테이너 **269 passed/2 skipped**(회귀 0). outside-voice [SKIPPED:display-metadata] (REV-20260609-0175).
- [ ] verify-completion PASS → 커밋 → push → main ff-merge → **재배포(ask-worker+web — 실행모드=worker 라 agent 루프는 ask-worker 컨테이너)** → 라이브 ask 후 step reason 노출 확인

### TASK-0177 — 실행 단계 근거를 LLM 이 실제 맥락으로 생성 (SYSTEM_PROMPT tool_notes 지시) (2026-06-10)
- [x] **Major §12.3** — 사용자 원의도: derived 템플릿이 아니라 **LLM 이 질문 맥락에 맞춘 실제 근거**. 근본 공백(SYSTEM_PROMPT 가 tool_notes 미지시)을 메움. TASK-0175 derived 는 비순응 안전망으로 유지. (CHG-20260610-0177)
- [x] `SYSTEM_PROMPT` 에 `## STEP NARRATION (tool_notes)` 섹션 — tool 호출 턴마다 content 에 `{"tool_notes":[{work,reason}]}` 방출(call 당 1 entry 동순서), reason 은 사용자 목표에 비춘 구체 근거. tool call 없는 턴엔 JSON 금지. OUTPUT 보강.
- [x] **B1 sanitizer**(outside-voice BLOCKER): `_strip_leaked_tool_notes` + 최종답변 배선 — 누수된 envelope 결정적 제거(통째면 빈문자열→재요청 루프). 프롬프트 억제 + 백엔드 fail-closed 이중.
- [x] 프롬프트 보강: M1 "i번째 note↔i번째 call(병렬 포함)", m1 따옴표 escape, m2 "tool call 없는 모든 턴".
- [x] 회귀 테스트 `tests/test_tool_notes_prompt.py` 9종(프롬프트 지시 존재·파서 라운드트립[멀티/펜스/패딩/절단]·sanitizer 4). make test 컨테이너 **278 passed/2 skipped**(회귀 0). py_compile OK.
- [x] outside-voice 적대적 리뷰 NEEDS-TWEAK→FIXED, BLOCKER 1 흡수 + MAJOR 3 반영/위임 (REV-20260610-0177).
- [ ] verify-completion → 커밋 → push → main ff-merge → **재배포(ask-worker+web) + 라이브 `WebSystemPrompts` global row 새 상수로 갱신**(GLOBAL row 가 상수 대체) → **카나리아: `reason_source='llm'` 비율 실측(M2) + 최종답변 JSON 누수 0 + 근거 맥락성 확인**

### TASK-0178 — 단계 근거를 LLM 이 생성: tool 인자(reason/work)로 전환 (2026-06-10)
- [x] **Major §12.3** — TASK-0177(content tool_notes) 전달 메커니즘 수정. **라이브 확정**: 0177 배포 후 카나리아 전 step `reason_source=derived`, core_messages content=`{"tool_notes":[{"work":"","reason":""}]}` → **Bedrock gateway 가 tool_use 턴 text content strip**(REV-0177 M2 실현). (CHG-20260610-0178)
- [x] tools.py: 전 도구 스키마에 optional `reason`/`work` 주입(`_inject_step_narration_params`, properties 맨 앞=think-first, required 제외). reason 설명=질문 맥락 구체 근거.
- [x] agent_core: 루프에서 `tool_args.pop("work"/"reason")` 추출(실행/저장 전 제거) + 우선순위 arg→content→derived. SYSTEM_PROMPT 를 "tool 인자 reason/work 채워라"로 교체.
- [x] 회귀 테스트 `tests/test_step_narration_params.py` 4(전 도구 주입·core 공유·think-first 순서·핸들러 추가인자 무해) + `test_tool_notes_prompt.py` 프롬프트 테스트 갱신. make test **282 passed/2 skipped**(회귀 0).
- [x] **머지 전 라이브 probe 카나리아 PASS**: worktree 배포+row 갱신 후 2 ask → **5 step 전부 `reason_source='llm'`**, 근거 질문 맥락 직결, 누수 0, 답변 정확. (REV-20260610-0178)
- [ ] verify-completion → 커밋 → push → main ff-merge → 머지판 재배포(GIT_COMMIT 정상 각인) → 최종 카나리아 재확인

### TASK-0196 — convo_search 도구 AR-M5 cutover 라우팅 누락 복구 (2026-06-10)
- [x] **Minor §12.3** (에이전트 도구 읽기경로 라우팅, RBAC·스키마·파괴 0) — 사용자 요청("mysql→PG 이관 미완으로 작동 안 하는 부분 검토")의 전 서비스 스윕 산물. web 3건은 feature-0003 TASK-0196. (CHG-20260610-0196)
- [x] **결함**: `convo_search`(LOCAL agent tool — 다른 대화 기록을 메시지/요약/주제로 검색)가 `modules/file_ops.py` 에서 PG 경로 전무한 채 삭제된 MySQL `AgentMemoryMessages`/`AgentMemorySummary`/`AgentMemoryKv` 3개를 `try/finally`(except 없음)로 조회 → 에이전트가 도구 호출 시 첫 쿼리에서 **throw**(도구 기능 사망). 정적 스윕(file_ops 가 `_pg_connect`/`agent_runtime`/`AGENT_RUNTIME_READ_BACKEND` 전혀 import 안 함)으로 확정.
- [x] **수정** ([src/modules/file_ops.py](../src/modules/file_ops.py)): `AGENT_RUNTIME_READ_BACKEND == "postgres"` 일 때 PG `agent_runtime.messages`/`summary`/`kv` 로 라우팅. ILIKE = MySQL utf8mb4_unicode_ci case-insensitive 패리티. PG `kv.key`/`value`(비예약어) unquoted, `include_current` 필터·`_format_row`(conv_id,role,content,created_at,source) 컬럼순서 동일. legacy MySQL else 보존.
- [x] 회귀 테스트 `tests/test_convo_search_pg_routing.py`(PG 라우팅 + 전달된 MySQL conn 미사용 가드 + 3 소스 모두 검색 + current 대화 제외). make test(컨테이너 pytest+ruff) exit=0(0002+0003 전체 회귀 0).
- [x] outside-voice 적대적 백엔드/QA 검토 SHIP(MAJOR 0) — REV-20260610-0196.
- [ ] verify-completion → main ff-merge → agent-core 서비스(ask-worker/insight-worker/web) 재배포 → 라이브 에이전트 convo_search 호출 검증.

### TASK-0200 — convo_search LIKE 메타문자 이스케이프 하드닝 (2026-06-10)
- [x] **Minor §12.3** (도구 읽기경로 하드닝, RBAC·스키마·계약 무변경) — REV-20260610-0196 이 지적한 MINOR 잔존의 실행. `convo_search` 가 `like_pattern = f"%{pattern}%"` 로 사용자 질의를 LIKE/ILIKE 패턴에 직접 끼워 `%`/`_` 가 와일드카드로 처리("100%"/"table_name" 등 오작동·과다매칭). `_collect_matched_excerpts` 와 동일하게 메타문자(`!`,`%`,`_`) 이스케이프(`!` 먼저 → `%`/`_`) + `ESCAPE '!'` 동반. 빈 질의는 전체 매칭(`%`, ESCAPE 없음) 유지. (CHG-20260610-0200) (#2 발췌 정렬은 web, feature-0003 TASK-0200.)
- [x] PG 분기(content/summary/value ILIKE) + MySQL legacy 분기(Content/Summary/`Value` LIKE) 6절 모두 `{like_escape}` 적용. like_pattern·like_escape 양 분기 공유(단일 소유).
- [x] 회귀 테스트 `tests/test_convo_search_pg_routing.py` 2 추가(메타문자→`%100!%!_x!!%`+ESCAPE 동반 / 빈 질의→`%`+ESCAPE 없음). make test exit=0(0002+0003 전체 회귀 0), ruff clean.
- [x] outside-voice [SKIPPED:minor-escaping-implements-REV-0196] (REV-20260610-0200).
- [ ] verify-completion → main ff-merge → agent-core 서비스 재배포 → 라이브 convo_search 메타문자 질의 검증.

### TASK-0201 — 멀티 datasource Stage 2 P6: MSSQL 보안경계 + 실 인스턴스 검증 (2026-06-10)
- [x] **Major §12.3** (멀티엔진 보안경계 — RBAC/데이터격리 면, outside-voice 필수). DESIGN-multi-datasource.md §3.4/§10/§11.
- [x] **축1 AST allowlist** (Codex-1): `_extract_sql_schema_refs` 정규식 → `sql_guard.collect_schema_refs`(활성 dialect 파싱). `_collect_table_refs` 가 `.catalog/.db/.name`(unquoted) 사용 → 대괄호/3-part/ANSI/백틱 우회(B-1) 봉쇄. 무자격 fail-closed + catalog cross-DB 차단(`_freeform_sql_access_error`). 레거시 단일 MySQL 무자격 허용(골든).
- [x] **축3 sql_guard dialect** (B-3): `validate_sql_for_sandbox(..., dialect=)` + sqlglot tsql 파싱. T-SQL denylist(xp_cmdshell/OPENROWSET/OPENQUERY/OPENDATASOURCE/WAITFOR/EXEC/sp_executesql/SELECT INTO/@@) + dialect 금지함수. into 이중차단(denylist+AST).
- [x] **m3 dialect 시스템/메타데이터 스키마**: Dialect 단일소유(A2/C1). MSSQL sys/INFORMATION_SCHEMA/guest/db_* 제외(dbo 유지), 항상허용=sys/INFORMATION_SCHEMA.
- [x] **M-4 부하게이트 fail-closed**: `Dialect.supports_load_estimate`(MSSQL=False) → gate 모드 사전차단. MySQL 골든(fail-open) 유지.
- [x] **Codex-6 confirm_heavy 비-LLM**: `AGENT_QUERY_CONFIRM_HEAVY_TRUST_LLM`(기본 true=현행, false=모델 자기우회 차단). UI 승인 P7 이월.
- [x] **Codex-2 GRANT 모델**: `bin/datasource-mssql-ro-bootstrap.sql` — db_datareader 금지, 전용 role 에 허용스키마만 GRANT SELECT, 0단계 서버 prereq(xp_cmdshell/cross-DB chaining/Ad Hoc Distributed Queries OFF) 검증. `sqlcmd -b` 필수.
- [x] **Codex-5/7 결정**: AST 재직렬화 미채택(원문실행 유지+denylist+pin, 잔존위험 명시) / 세션reset 아키텍처 해소(MSSQL fresh connect, MySQL pool_reset_session).
- [x] **§3.5 grounding 방언 주입**: 활성 엔진 mssql 이면 `_MSSQL_DIALECT_GUIDANCE`(TOP/대괄호/스키마명시/cross-DB금지/T-SQL함수) system prompt 주입.
- [x] 회귀 테스트 `tests/test_mssql_security_boundary.py`(dialect 매트릭스·B-1 우회·정책·M-4·Codex-6). 전체 스위트 RC=0(0002+0003 회귀 0), ruff 통과.
- [x] **실 MSSQL 검증**(사용자 Windows `172.28.64.1:14330`, dk_data_release): 최소권한 RO 생성 후 도구 전부 동작 + 보안경계 6/6 차단 + 2축 방어 실증(앱+DB GRANT). P5 dialect 버그 4건 수정(DMV 권한→sys.partitions / DB 고정 / row 컬럼 / index·FK dialect). 서버 xp_cmdshell ON 발견(앱·GRANT 로 무력화, 운영자 OFF 권고).
- [x] **outside-voice 적대적 보안 재게이트(MANDATORY)** REV-20260610-0201: 1차 REJECT(실 인스턴스 데이터 탈취 재현) → B1(BLOCKER 구조화도구 `]` 2차 SQLi)·M1(MAJOR sys 항상허용 유출)·M2(MAJOR gate confirm_heavy 우회) 수정 → 2차 **SHIP**. 라이브 재검증 PASS, 회귀테스트 추가, 전체 스위트 RC=0.
- [ ] 커밋 → main ff-merge → P6 배포(agent/ask-worker/insight-worker/web) → winsql datasource 등록+product 바인딩 → 라이브 assistant·insight-worker 검증.

### TASK-0203 — 멀티 datasource Stage 2 P7: insight-worker MSSQL dialect-화 (2026-06-11)
- [x] **Major §12.3** (insight 엔진 분기 — 데이터격리 무변경, 핑거프린트 livelock 면 주의). DESIGN §12.
- [x] **컬럼 핑거프린트 dialect projection**: `Dialect.fingerprint_column_projection()` (MySQL 골든 / MSSQL `CHARACTER_MAXIMUM_LENGTH`·KEY 상수 — SQL Server INFORMATION_SCHEMA 엔 COLUMN_TYPE/COLUMN_KEY 부재). insight.py 의 single/batch 컬럼 핑거프린트가 사용. FROM/WHERE 공통(ANSI) 유지·parameterized.
- [x] **engine-passing 버그 수정**: `run_insight_cycle` 의 `set_active_datasource(_ds_key)` → `engine=_ds_coords.get("engine")` (dialects.active() mysql 오인 차단).
- [x] **livelock 방지 확인**: write·read-back 동일 set_active_datasource(engine) 컨텍스트 → 동일 projection. 라이브 단일≡배치 해시 동일·결정성 STABLE.
- [x] 회귀테스트 `test_multi_datasource.py` 3종(MySQL projection 골든 / MSSQL MySQL-only 컬럼 부재 / active 엔진 분기). 전체 스위트 RC=0, ruff clean.
- [x] **실 MSSQL 검증**(dk_data_release CI): 컬럼/스키마/배치 핑거프린트 전부 동작(COLUMN_TYPE 실패 해소).
- [x] outside-voice 적대적 리뷰 REV-20260611-0203 (livelock 중심) **SHIP**(BLOCKER0·MAJOR0). MINOR 3 후속.
- [x] **라이브 cycle 검증 중 2 버그 발견·수정(P3 이래 잠복, 실 datasource 연결로만 노출)**: ① insight.py 의 `connect_with_retry` 가 `from .config import *` 로 **`modules.utils` 구버전**(datasource 인자 없음)에 바인딩 → winsql 순회가 매 cycle `TypeError` → **`modules.db` 의 datasource 지원판 명시 사용**(`_db.connect_with_retry`). ② per-datasource isolation 핸들러가 `logging.getLogger` 쓰는데 insight.py 가 **`logging` 미import**(config `__all__` 제외) → datasource 예외 시 핸들러가 NameError 로 재폭발(격리 실패) → `import logging` 추가. 둘 다 단일 MySQL 시절엔 미발현.
- [x] 라이브 LLM 인사이트 생성 검증: winsql `dbo.Item` payload → `llm_table_insight`(edge/로컬 게이트웨이) 정상 dict 산출(domain/summary/key_columns, 5.8s).
- [x] **sweep 3차(라이브 cycle 추가 발견)**: ③ `schema.py` `load_known_schemas` 가 백틱 인용 `information_schema.SCHEMATA`(MSSQL `Incorrect syntax near '`'`) → `_dialects.active().list_schema_names()`(MySQL 골든 동치/MSSQL sys.schemas)로 교체. ④ datasource 순회가 dialect 시스템 스키마(MSSQL guest/db_*)를 못 걸러 RO-거부 노이즈 → `_dialects.active().system_schemas()` 로 datasource 경로 필터(MySQL 경로 미변경). 라이브: `load_known_schemas(winsql)` → 필터 후 `['dbo','dev50']`.
- [ ] 커밋 → main ff-merge → insight-worker 재배포 → 라이브 winsql 인사이트 생성·publish 관측.
- [ ] (P7 잔여·후속) UI engine 배지 + MINOR-1 CS-collation 대문자 통일.

### TASK-0219 — datasource-aware rag_objects + 엔드포인트-해시 스코핑 (2026-06-11)
- [x] **문제 1 (RAG 구조 불일치)**: ds-스코프 fact 키 `{source}:ds:{ds}:{suffix}` 가 도입됐으나 `utils._infer_rag_object_from_fact` 가 `ds:winsql:dbo` → schema `dswinsqldbo`(쓰레기)로 망가뜨려 **ds rag_objects 0건**(ds rag_documents 1753건 존재에도). rag_objects 에 datasource 컬럼·검색 ds-필터 부재.
- [x] **문제 2 (스코프 키 불안정)**: 동시 TASK-0216/0218 로 `DatasourceKey` 가 admin rename 가능한 단순 라벨이 됨(`_generate_datasource_key`=엔진+호스트+포트 SHA-256). 라벨로 스코핑하면 rename 시 누적 insight 가 고아.
- [x] **파서 수정**: `:ds:{key}:` 접두 분리 → schema/table 정규화(`dbo`/`T_ItemLog`) + datasource_key 추출 + object_key 에 ds 접두(`{hash}:dbo.t`)로 cross-ds 유일성(UNIQUE `(conv,scope,type,object_key)` 불변). 6-tuple 반환.
- [x] **스키마**: `rag_objects.datasource_key VARCHAR(64)` 컬럼 + 필터 인덱스(alembic `0004_rag_objects_datasource`, ADD COLUMN, 무손실). 라이브 적용(0003→0004).
- [x] **쓰기/검색**: `upsert_rag_object`(base/MySQL/PG/Dual) datasource_key 전달 + `_PG_UPSERT_RAG_OBJECT` 컬럼/DO UPDATE. `search_rag_objects` 가 `get_active_datasource()` 로 ds-필터(`ds_fact_like` 동형 심층방어).
- [x] **엔드포인트-해시 스코핑**: `datasources.compute_scope_key/scope_key`(web `_generate_datasource_key` 동일 공식) — fact/RAG 스코핑 식별자를 라벨이 아닌 **engine+host+port 해시**로 고정. agent_core ask 경로 + insight 루프의 `set_active_datasource` 가 scope_key(해시) 사용 → 라벨 rename 에도 누적 지식 불변. 격리 모델 무변경(per-datasource, 엔드포인트=신원).
- [x] **jsonb ON CONFLICT 버그 수정(잠재)**: `category_join_hints_json`(jsonb) 의 `NULLIF(EXCLUDED.., '')` 가 ''를 jsonb 캐스팅하려다 **모든 rag_object conflict-갱신 실패**("invalid input syntax for type json") → NULLIF 제거(COALESCE, 호출부 None 전달). varchar category_* 는 NULLIF 유지. S5 invariant 정정.
- [x] **재키잉 스크립트**(`scripts/rekey_datasource_facts.py`): 옛 라벨(`main_mysql`/`winsql`/`mssql_local`) fact_entries/rag_documents 를 라이브 레지스트리 엔드포인트 해시로 재키잉(per-row `_fit_fact_key_storage` 절단 정합 + 병합) + rag_objects 재생성. 멱등·--dry-run·멀티-같은엔진 가드.
- [x] **회귀테스트**: `test_infer_rag_object_datasource_scoped`(ds 분리) + `test_scope_key_is_endpoint_hash_and_label_agnostic`(엔드포인트 해시·라벨독립). 호스트 391 passed, 컨테이너 make test RC=0.
- [x] **외부시각 적대적 리뷰(격리 경계)**: SHIP — 데이터 유출/격리 붕괴 BLOCKER 없음. 동일-엔드포인트·상이-경계 datasource 의 insight 병합은 비표준 구성·메타데이터 한정·4중 backstop(product 바인딩+allowlist+AST+RO-GRANT). Q4 멀티-같은엔진 재키잉 가드 반영.
- [x] **배포·라이브검증**(main dc3f0b0): web/ask-worker/insight-worker/agent 재빌드 + 마이그 적용 + 재키잉/백필. 검증: ds rag_objects 342(mysql-ddae8975d793=179 / mssql-f82c51b3425f=163), schema 망가짐 0(`dbo` 깨끗), no-ds 객체 788 NULL 보존, 제품1/7/8→mysql해시·90/91→mssql해시 resolve, retrieval ds-필터(active=mssql)→mssql 객체만 165(유출0).

### TASK-0256 — assistant 답변 diff 블록: SYSTEM_PROMPT diff 출력 지침 (2026-06-15)
- 목표: 첨부파일/사용자 쿼리 리뷰·편집 응답에서 변경(수정 SQL·편집본)을 markdown ```diff 블록으로 제시하도록 base SYSTEM_PROMPT 가 지시.
- [x] SYSTEM_PROMPT OUTPUT 섹션 뒤 "## SHOWING CHANGES — USE A MARKDOWN DIFF BLOCK" 추가 (리뷰/편집 한정, 신규 SQL 작성은 ```sql 유지)
- [x] test_compose_system_prompt: SYSTEM_PROMPT 가 ```diff·DIFF BLOCK 포함 + OUTPUT 이후 위치 검증 (4 passed)
- [x] 라이브 WebSystemPrompts global row 갱신 — 적용완료(5799→6837자, 마커 검증 True, 컨테이너 백업 /tmp/task0256_global_prompt_backup.txt)
- [x] ask-worker 재배포(main 2befd37) + SYSTEM_PROMPT diff 지침 baked 검증

### TASK-0256e — 첨부파일 diff 줄번호 추적 (실제 파일 줄번호 기반 헌크 헤더) (2026-06-15)
- 사용자 보고: 첨부 파일 리뷰 diff 의 줄번호가 항상 1부터(또는 없이) — 실제 파일 줄 미추적.
- 근본원인: `_build_attachment_context_section` 이 첨부 본문을 줄번호 없이 raw 주입 → 모델이 실제 줄 모름 → `@@` 헌크 헤더 못 만듦 → 렌더러(buildDiffRows)는 헌크 없으면 1부터.
- [x] `_number_file_lines(content)`: 각 줄 `<N>→` prefix(우측정렬, prompt 사본만, 원본 무변경 — SQL추출 경로 무영향)
- [x] 본문 주입에 적용 + "LINE NUMBERS & DIFFS" instruction(실제 줄번호로 `@@ -N,M +N,M @@` 작성, prefix 코드 미포함)
- [x] test_attachment_line_numbers(5) + 렌더 폐루프 node 확인(`@@ -49` → gutter 49/50/51) + py_compile
- [x] ask-worker 재배포(main 63f4a5a) + baked 확인 + **라이브 LLM probe PASS**: 줄번호 첨부 → 모델 `@@ -4,2 +4,4 @@`(실제 줄번호) 헌크 출력·prefix 코드 미포함(TEST.md)

### TASK-0284 — 첨부 LLM 주입 스코프 conversation 통일 + 파일명 지칭 (Critical §12.3, 2026-06-16, feature-0003 주관)
- (feature-0003 TASK-0284 의 agent-core 측 변경) 첨부 LLM 컨텍스트 주입을 AccountId → ConversationId 스코프로 통일 + assistant 가 첨부를 파일명으로 지칭하도록.
- [x] `_build_attachment_context_section` 에 `conversation_id` 인자 추가 + PG/MySQL WHERE 를 conversation 우선 스코프(account 폴백, `_scope_by_conv`)로. 대화 접근권은 caller(app.py ask) 게이트.
- [x] `compose_system_prompt` + `_run_agent_core`(2610 호출부) conversation_id 전파
- [x] (이슈3) 첨부 포맷 파일명 우선: 목록 `- file "..." (attachment_id=..)`, csv/xlsx sandbox 라벨 `file "..."`, ATTACHED FILES 섹션에 "REFER TO ATTACHMENTS BY FILENAME" 지침
- [x] test_attachment_idor.py +4(conversation 스코프·account 폴백·파일명 우선) + make test 전체 회귀 0
- [ ] ask-worker 재빌드(agent_core baked) → 라이브 검증 — feature-0003 TASK-0284 와 함께 마감

### TASK-20260619T014034 — LLM provider 외부요인 제한(자격증명 만료) 명시 표면화 (Major §12.3, agent-core 면, 2026-06-19)
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-19 -->
- 목표: Bedrock 등 외부 provider 장애(특히 AWS 키/자격증명 만료)로 LLM 응답이 막힐 때, 현재 raw 예외(`LLM 호출 오류: ExpiredToken`)/일반 에러로만 노출되던 것을 서비스 사용자가 여러 surface 로 명시 확인하도록. 사용자 결정: 범위=외부요인 제한(사용량/쿼리부하 아님), UI=인라인+패널+컴포저+툴팁 직/간접 다중, 감지=hybrid(passive+probe).
- [x] 신규 `modules/llm_provider_health.py`: `classify_llm_provider_error`(예외→{kind,provider,message,retryable,error_tag}, credential_expired/auth_invalid/throttled/unavailable/not_configured/unknown) + PG upsert/read(`agent_runtime.llm_provider_health`) + active `probe_provider`(max_tokens=1, TTL throttle).
- [x] agent_core: LLM 호출 예외 경로(`_call_llm` 2931)에서 분류→친화 메시지 치환 + passive `record_provider_restricted`; 성공 시 `record_provider_ok`(run 당 1회, try/except/else); 무자격증명(2568)→not_configured; `result["llm_restriction"]` 필드.
- [x] 스키마: `agent_runtime_schema.sql` §6e bootstrap DDL + alembic `0011_llm_provider_health`(GRANT 포함 — 0006 DEPLOY TRAP 동형). 자격증명 비영속(state/kind/message/error_tag(클래스명만)/source/since 만).
- [x] (feature-0003) app.py: `_read_llm_provider_status` + `GET /api/llm/health`(인증 게이트·probe) + `/api/session`·`_build_ask_status_snapshot` 에 `llm_provider_status` 동봉.
- [x] (feature-0003) 프론트 4 surface: 컴포저 상단 배너 + footer 상태점/툴팁 + 대화 인라인 notice + 실행단계 패널 노트 + send title(indirect). `/api/llm/health` 폴링(60s)+로드 직후 probe+'다시 확인' force. 캐시버스터 bump.
- [x] 검증: `test_llm_provider_health.py` 14(분류·자격증명 비유출·폴백·not_configured) + `verify_llm_restriction_surface.mjs` 35(정적+jsdom 4-surface 토글) + feature-0002 전체 pytest 회귀 0(2 skip) + py_compile + node --check.
- [x] 적대 코드리뷰(outside voice, secret leakage/probe auth·cost/agent_core else/PG 폴백) → REV-20260619-0311.
- [ ] 배포: ask-worker + web 재빌드(agent_core·app.py baked) + 마이그 0011 적용 → 라이브 검증(restricted 주입 PB-0008 Windows-browser 4-surface, 실 키만료 e2e 는 운영 의존).

### TASK-20260619T033714-prompt-injection-defense — AI 프롬프트 인젝션 방지 (datamarking + 명령-계층) (REQ-20260619-0328, AC-0600~0603, Major §12.3, 2026-06-19)
- 사용자 요청(보안 보강 6종 중 ⑤): AI 프롬프트 인젝션 방지. 강한 방어(SQL guard·tool/schema allowlist·datasource 격리)는 기존 → 빈틈=비신뢰 콘텐츠 무구획 연결.
- [x] spotlighting/datamarking: `_datamark_untrusted(content,label)`(sentinel `⟦UNTRUSTED-DATA⟧`/`⟦/⟧` 구획 + 콘텐츠 내 sentinel strip=닫는 마커 위조/breakout 차단) + `_INJECTION_GUARD_NOTICE`(명령-계층 고지: 마커 사이는 데이터일 뿐·"이전 지시 무시"/"시스템 프롬프트 출력" 류 결코 따르지 말 것).
- [x] guard notice 를 `compose_system_prompt` 출력 base 직후 **코드-주입**(global row 운영자 커스터마이즈 무관 effective).
- [x] 적용: 첨부 파일 본문(줄번호 유지)·샘플 데이터(셀)·과거 대화 recall datamark.
- [x] outside-voice 적대 리뷰 **SHIP-WITH-FIXES**(BLOCKER 0). **MAJOR 흡수**: ①guard notice 가 "쿼리 실행 결과" 보호 광고하나 execute_sql tool 결과 미-datamark(최대 벡터)→`_run_agent_core` tool_msg content datamark ②KB schema_list/table_insights "authoritative/trust" 단정+미-datamark→datamark+설명문 비신뢰 명시. **MINOR 흡수**: 과대표현(무력화→best-effort 확률적 완화·보장 아님 명시). **수용**: fence breakout(이미 `_number_file_lines` 줄prefix 로 ``` 비-줄머리화 완화)·proximity·i18n·history 과거 raw.
- [x] 검증: `tests/test_prompt_injection_defense.py` 10/10(B1 datamark strip 실 동작·B1b breakout 차단·B7 tool·B8 KB + inspect.getsource) + make test 회귀 0(사전존재 product-delete 2건 제외) + py_compile.
- [ ] 머지 → 배포(**web + ask-worker 재빌드** — agent_core 변경) → 라이브(첨부/결과 인젝션 시도 무시 확인) → 마감.

### TASK-0305 — insight-worker "제품 DB 파악 진전 없음" 병목 진단·수정 (Major §12.3, 2026-06-23)
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-23 (scope: Minor RC2/RC5 + Major RC3) -->
- 사용자 보고: insight-worker 가 제품의 DB 를 파악하는데 진전이 없는 것처럼 나타남. 다중 가설 + 적대적 검증 진단.
- 진단(2축 분리): **축 A 커버리지** = 39 catalog DB 중 28개가 RO 로그인 per-DB GRANT 누락(권한 18456/916)으로 영구 스캔 실패 → status=degraded 고정, 완료율 정체. **운영(GRANT)이 1차 해결** — 코드 아님. **축 B 처리량** = 살아있는 11개 DB 조차 신규 통찰 0 (RC3 force_scan latch + RC2 fingerprint churn).
- [x] **RC2 (Minor)**: `_compute_schema_fingerprint`/`_compute_table_fingerprint`/`_compute_table_fingerprints_batch` 에 casefold 를 **해시 VALUE 한정** 적용 — MSSQL information_schema 케이스 진동(TF_ErrorLog↔tf_errorlog)에 의한 schema fingerprint churn(11초 LLM 무의미 재생성, ~132s/day) 제거. 키 생성(ds_fact_key/ds_object_suffix) 불변 → TASK-0220 정합 보존.
- [x] **RC3 (Major)**: `_scan_instance_schema_insights` 진전 기반 backoff — 무경계 `_detect_pending_insight_repairs` 가 budget(15s) 닿지 못하는 미완성 artifact tail 을 pending 으로 영구 집계 → force_scan 매 8s tick 영구 latch(도달가능 DB 의 수천 테이블 fingerprint 스캔 spin) 차단. pending-only 무진전 스캔이면 `_set_repair_backoff`(per-scope KV, 최소 60s, 기본 RESCAN_SEC=3600). missing(새 스키마)·rescan interval 경과·진전 시는 그대로 스캔(건강한 처리량 보존). ANCHOR §3 repair→generate 순서 무손상.
- [x] **RC5 (Minor)**: cycle summary 에 db_failed 사유 분포(`db_failed_perm`/`circuit`/`other`) 노출 + db_failed 가 비-MSSQL datasource 실패도 집계(과거 `_is_mssql_ds` 게이트 제거) + 비-MSSQL ds db_targets 집계. → 28개 중 perm(GRANT) vs network 분리를 **로그만으로 특정** 가능(관측성 공백 해소). 부수: 비-MSSQL ds 실패도 degraded 승격(의도된 가시화).
- [x] 단위테스트 `tests/test_task0305_insight_bottleneck.py` 8개(RC2 케이스 불변·실변경 감지·키 보존 / RC3 backoff set·clear·만료·최소바닥) + feature-0002 회귀 0(사전존재 `test_db_query_ux::test_assemble_core_messages` 1건은 agent_core 무관 결함, 본 작업 범위 밖). py_compile.
- [x] 적대 코드리뷰(backend+qa outside voice) → REV-20260623T061043-insight-bottleneck **ACCEPT**(6 검증항목 반증 실패, BLOCKER 0).
- [x] **배포(sudo, 2026-06-23)**: 스택 가동 중 확인 → `sudo docker compose build/up insight-worker` 재빌드·재시작, 컨테이너 내부 새 코드 검증, 워커 healthy 복귀.
- [x] **🔴 축 A 정정 — GRANT 아님, 네트워크 단절**: 배포된 RC5 가 라이브 확정 — `db_failed: 38, perm: 0, circuit: 38, other: 0` + datasource_health down 12개 전부 `circuit_open/timeout`. 실패 100% 네트워크 도달 불가, 권한 0. **GRANT 비적용**(원인 아님 + timeout 서버 접속 불가). 사전 "perm/GRANT 28건" 은 RC5 부재로 인한 오진(배포로 정정). 영향: `mysql-kr-an2-*` 7·`mysql-mv-qa-*` 3·`mssql-web-qa`·`mysql-web-global-qa` 등. **실제 조치 = 네트워크/인프라 도달성 복구**(코드·DB 권한 영역 밖). 상세: REPORT.md "라이브 배포 검증 + 정정" + LRN-20260623-0002.
- [x] **🟠 RC2 cutover 사고 + backfill 완화**: casefold 가 기존 8,833 fingerprint 무효화 → reachable ~1,979 LLM 재생성 폭주. fingerprint backfill(새-해시 fp 3,917 table+205 schema, LLM 0)로 완화 — 10/10 fp 일치 검증, tables_generated 0 복귀, health 회복, 통찰 무손실. 교훈 LRN-20260623-0001(fp 알고리즘 변경은 backfill 동반 필수).
- [x] **RC4 (구조적 throughput) 전용 조사 — 결론: document-only, 코드 변경 0**: 적대 검증 3각 수렴. binding constraint = **단일 프로세스 직렬 블로킹 LLM(~11s) × DB-cycle 공유 budget(15s) → DB당 cycle당 ~2건** (의도된 self-throttle, 과거 livelock 방어 TASK-0145/0146 — 버그 아님). TABLE_LIMIT/MAX_SCHEMAS 는 budget 가 먼저 끊어 non-binding. 안전한 코드 win 없음(병렬화=high-risk livelock 재발·Bedrock 과부하; fingerprint 게이팅=테스트 게이트 필요). 튜닝 레버(BUDGET_SEC/TICK_SEC/MAX_SCHEMAS·TABLE_LIMIT) 전부 라이브 부하 데이터 없이 기본값 변경 금지 → REPORT/FUNCTION 에 레버·trade-off·카나리 계획 문서화. 다음 단계: GRANT 후 1~2일 라이브 텔레메트리(tables_generated/cycle·LLM duration_ms·gateway 큐잉) 수집 → 단일 datasource 카나리로 BUDGET 데이터기반 조정.
- [x] **agent_core 회귀정정 (drive-by, TASK-0305 검증 중 발견)**: `test_db_query_ux::test_assemble_core_messages_under_budget_unchanged` 가 base 에서도 실패 — 원인은 코드 버그가 아니라 **feature-0009 의 `_merge_consecutive_user_messages`(Bedrock role-교대 제약 대응, 연속 user 턴 `\n\n` 병합) 도입 후 낡은 테스트**. 코드 정상 → 테스트를 현행 동작에 맞춤(병합 검증) + 원 의도(under-budget pass-through)를 role-교대 fixture 로 보존. 13/13 통과.
- [x] ~~배포·GRANT 차단~~ → sudo 로 해소(위 2줄): 배포 완료, GRANT 는 라이브 검증으로 "네트워크 단절(비적용)" 확정. 잔여 = 인프라 네트워크 복구(코드 영역 밖).

### TASK-0306 — 마이그레이션 split-brain 해소 + 재발 방지 hygiene (Major §12.3, 2026-06-23)
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-23 (insight 내부 진단 후속 "HIGH 포함 전부") -->
- 발견(TASK-0305 후속 내부 진단): 라이브 `alembic_version=0012` 인데 코드 head=0015 split-brain. 부트스트랩(`_ensure_pg_schema`)이 0014/0015 shape 는 만들었으나 0013 의 `kb_glossary`/`enum_dictionary` 부재 → ITEM-10 용어/ENUM 사전이 `agent_core` `except` 에 삼켜져 **silent dead**. 추가로 revision id `0015_...`(34자) > `alembic_version.version_num VARCHAR(32)` → 기록 불가 latent 버그.
- [x] **라이브 DB 정합(sudo, 비파괴)**: 0013 UPGRADE_SQL(kb_glossary+enum_dictionary CREATE+index+trigger+GRANT, 멱등) 을 postgres superuser 로 적용 → `version_num` 컬럼 32→128 확장 → `alembic_version` 0012→0015 stamp(0013 적용·0014/0015 shape 기존이라 파괴적 0015 DROP+ADD 실행 안 함). 검증: 테이블·RW/RO GRANT 확인, `load_glossary_enum_context` 예외 없이 동작(기능 복구), `upgrade head` no-op.
- [x] **재발 방지 코드(이 PR)**: ① `src/scripts/agent_kb_schema.sql` texts.embedding `vector(1536)`→`vector(1024)`(fresh-install 차원 불일치 해저드 제거; baseline 0001/live 정합). ② alembic `0015` UPGRADE_SQL 멱등 가드(이미 vector(1024)면 skip → DROP+ADD 데이터손실 위험 제거, fresh-install 정렬은 보존). ③ `bin/alembic-migrate.sh` alembic_version `VARCHAR(32)`→`VARCHAR(128)`(+ALTER, 긴 revision id 기록 가능). ④ `kb_backend.py:940` stale 1536 주석 정정.
- [x] 검증: 0015 py_compile + alembic-migrate.sh bash -n + 적대 backend 리뷰(REV-20260623T180000) **ACCEPT-WITH-NITS**(라이브 PG 실측: format_type='vector(1024)' 가드 정확·체인 선형·varchar 확장 안전; NIT 2건 LOW 문서drift). 마이그/차원/스크립트는 라이브 dry-run(rollback) 확인.
- [x] 교훈 `docs/LEARNINGS.md` LRN-20260623-0003(부트스트랩↔alembic split-brain + revision-id 길이) 기록.
- [ ] 후속(범위 밖·doc-sync): wiki `nl2sql-flywheel.md`·`docs/STATUS.md` 의 sample_queries 임베딩 1536 서술 1024 로 갱신.
- [x] texts.embedding 백필 + 자동화 → TASK-0307 로 분리 진행(사용자 "백필+자동화" 승인).

### TASK-0307 — texts 임베딩 백필 + 자동 백필 데몬 (Major §12.3, 2026-06-23)
<!-- PLAN-APPROVED by ms.mckim.gpt on 2026-06-23 ("백필 + 자동화 (권장)") -->
- 발견(TASK-0305 후속 진단 MEDIUM): `kb_embedding_worker` 에 스케줄러/호출처가 없어 신규 texts 가 영구 NULL embedding → `texts` 41,076 중 40,200(98%) 미임베딩, 06-17 이후 정체. provider(titan-embed via bedrock-gateway, 1024-dim)는 정상. grounding 은 trigram 폴백 동작하나 의미검색 recall 저하·확대.
- [x] **1회 백필(운영, sudo)**: dry-run 확인(40,200행, ~$0.40) 후 `kb_embedding_worker` 실행. titan-embed 가 batch 100당 ~25초로 느려 전수 소진은 수 시간 → 아래 자동 데몬이 이어받아 자율 처리(별도 babysit 불요).
- [x] **자동화(코드)**: `kb_embedding_worker.run_embedding_pass(max_rows)` 추가(기존 batch 함수 재사용, fail-soft dict 반환). insight-worker 가 **별도 데몬 스레드**(`_embedding_backfill_loop`/`_start_embedding_backfill_thread`, conn_health 모니터와 동형)로 `AGENT_KB_EMBEDDING_INTERVAL_SEC`(60s)마다 `AGENT_KB_EMBEDDING_BATCH_MAX_ROWS`(100) 임베딩. **tick(스캔) 루프 비블로킹** — titan-embed 가 batch당 수십 초라 per-tick 동기 호출하면 본업 블로킹(REV F1). `AGENT_KB_EMBEDDING_AUTO=0` 비활성. config 3 knob + __all__.
- [x] 검증: py_compile(insight/config/kb_embedding_worker) + run_embedding_pass import/early-return 라이브 확인 + 적대 backend 리뷰 2회(F1 REQUEST-CHANGES→데몬 분리 재설계→**ACCEPT-WITH-NITS**, REV-20260623T190000; 라이브 임베딩 레이턴시 실측·스레드 안전성 확인).
- [ ] 배포: insight-worker 재빌드·재시작(데몬 스레드 활성). **1회 백필 완료/중단 후 배포**(동시 중복 F2 회피 — 재시작이 수동 backfill 종료). 배포 후 검증: 로그 `embedding_backfill processed=...` + texts NULL 감소.
- 참고: redeploy 중 in-flight pass 유실은 resumable(WHERE embedding IS NULL)이라 무해(REV N1). HNSW per-row autocommit 비용(REV N3/F3)은 기존 CLI 동작·범위 밖.

### kb-pg-superuser-host — KB-PG DDL superuser pgbouncer 우회 (deploy infra, Minor §12.3, 2026-06-25)
- [x] `make up` memory-init `FATAL: bouncer config error` 해소: `_ensure_pg_schema`(memory.py:854) superuser DDL 이 `AGENT_KB_PG_SUPERUSER_HOST` 미설정 시 pgbouncer 상속 → superuser 인증 불가(userlist=agent_kb_rw only). `.env.example` 에 `AGENT_KB_PG_SUPERUSER_HOST=postgres`(직결) + 주석. 런타임 `.env` 동일 적용 후 `make up` **exit 0** 검증. (CHG/REV-20260625T012217-kb-pg-superuser-host)

### limit-subject-msg — 요청량 한도 도달 주체 구분 + 서비스 한도 메시지 provider명 제거 (Minor §12.3, 2026-06-25)
- 사용자 요청(/_template:entry): "① 요청량 한도 도달 시 주체 구분(계정 당 한도 / 서비스 자체 한도), ② 서비스 한도 도달 메시지에서 AWS Bedrock 언급 제거 — 서비스 자체의 한도 도달임을 명시."
- 등급: **Minor §12.3** — 사용자 노출 메시지 문구만. 분류 kind/HTTP code(429)/retryable/error_tag/응답 shape 무변경, 로직·RBAC·스키마·엔드포인트 0.
- 진단: 두 "요청량 한도" surface 존재 — (계정) `app.py:_check_account_token_quota` 토큰 사용 한도 초과(429), (서비스) `llm_provider_health.py:_build_restriction` KIND_THROTTLED(provider throttle/429). 후자가 `plabel`("AWS Bedrock")을 메시지에 노출 + 양쪽 모두 주체 미명시.
- [x] **(서비스) `modules/llm_provider_health.py` KIND_THROTTLED 메시지**: `f"{plabel} 요청량 한도..."` → `"서비스 자체의 요청량 한도에 도달했습니다. 잠시 후 다시 시도해 주세요."`. provider명(AWS Bedrock 등) 비노출 + "서비스 자체" 명시. credential/auth/unavailable kind 는 관리자 진단용 provider 라벨 유지(범위 밖).
- [x] **회귀 테스트**: `tests/test_llm_provider_health.py::test_throttled_message_is_service_level_without_provider_name` 추가 — message 에 "Bedrock" 부재 + "서비스" 포함 단언. 기존 throttle 테스트(kind/retryable) 무회귀.
- [x] **(계정, cross-ref feature-0003)**: `app.py` 계정 토큰 한도 초과 메시지에 "계정의 ..." 주체 명시(정본 = feature-0003 CHG/REV-20260625T045450-limit-subject-msg).
- [x] 검증: py_compile(llm_provider_health) + `pytest test_llm_provider_health.py` **19/19 PASS**(신규 1 포함) + 렌더 확인(throttle="서비스 자체의 요청량 한도...", credential=provider명 유지).
- [x] 리뷰(REVIEW REV-20260625T045450-limit-subject-msg [SKIPPED:message-text-only-no-logic]): 메시지 문구만·계약 무변경·테스트 추가 → 적대 패널 불요(§18.4 경량 cycle).
- [ ] verify-completion → commit/push → (PR·머지·배포는 사용자 confirm) → 마감.
### init-embedding-latency — "준비(init)" 4s→50s 회귀 해소 (Major §12.3, cross-feature 0002·0007, 2026-06-25)
사용자 보고: LLM 응답의 "준비" 단계만 4초→50초 (대기·추론 정상). 근본원인 적대검증·라이브 실측으로 3축 확정.
- [x] **근본원인 규명(라이브 실측)**: "준비(init)"=`_build_knowledge_context` grounding 임베딩 구간. ① 2026-06-23 `litellm_config.yaml` 이 `titan-embed` 를 Bedrock Titan→**공유 Ollama bge-m3**(`ollama-edge`)로 전환(AWS 자격 제거 부수효과). ② 공유 Ollama `OLLAMA_MAX_LOADED_MODELS=1` → 타 서비스 chat 모델이 bge-m3 를 축출 → 매 호출 cold 재로딩 **실측 27~37초**(warm 시 0.13초). ③ init 이 동일 질문을 sample_queries(few-shot)+account_recall 에서 **2회 중복 임베딩**(캐싱 없음) → ~50초.
- [x] **인프라 fix**: 전용 `embed-ollama` 서비스 신설(`docker-compose.yml`) — bge-m3 단독 상주(`OLLAMA_MAX_LOADED_MODELS=1`+`KEEP_ALIVE=-1`, WSL GPU 패스스루, 전용 named volume). `litellm_config.yaml` `titan-embed` api_base→`embed-ollama:11434`. 라이브 검증: `ollama ps` bge-m3 **100% GPU·UNTIL=Forever**, titan-embed gateway 경유 **0.13~0.53초**(전 17~37초).
- [x] **코드 fix(재발 방지)**: ① `_build_knowledge_context` 질의 임베딩 **1회 계산→공유**(`_shared_qvec`), 두 기능 OFF 면 skip. ② `sample_queries`/`account_recall` `query_vector` 인자 + sentinel(`_QVEC_UNSET`) 백워드호환. ③ `_embed_query_vector(timeout_sec=)` + 신규 `AGENT_KB_QUERY_EMBED_TIMEOUT_SEC=20`(상호작용 fast-fail — 기존 300초 블로킹 제거, 실패 시 trigram graceful degrade).
- [x] **검증**: GPU 실효성 실측(bge-m3 1.2GB·100% GPU·warm 0.13s, GTX 1660 SUPER 6GB 충분) + 단위테스트(account_recall·sample_flywheel mock 시그니처 갱신, 통과; attachment_idor 4건은 사전존재 실패·무관) + 적대 backend 패널 **ACCEPT-WITH-NITS**(REV-20260625T035655: 캐싱·sentinel·ds-scope·timeout 정확, cosine(raw,norm)=1.000000, 전용 cold-load 3.63s<20s). chat(추론) 경로 무영향 확인.
- [x] **배포(라이브)**: embed-ollama up + bge-m3 pull + gateway 재시작(litellm repoint) + ask-worker/insight-worker/web `--no-cache` 재빌드·재생성(새 코드 baked). 라이브 임베딩 0.13초 복귀 확인.
- [ ] 후속(NIT·범위 밖): ① `kb_retrieval.py:458` agent-run RAG 경로는 timeout 300초 유지(준비 단계 아님 — 일관성 위해 후속 검토). ② gateway→embed-ollama `depends_on` 부재(최초 cold-boot pull 동안 grounding 일시 graceful-skip — 1회성·무해, 추가 시 gateway 기동 지연 trade-off). ③ 주석의 "AGENT_TIMEOUT_SEC(300s)" 는 `.env` 운영값(코드 기본 60s). ④ Bedrock Titan 자격 복구 시 litellm 토글 후 embed-ollama 비활성화 가능.

### insight-load-spread — insight/graph 부하 분산 (TASK-0308, Major §12.3, cross-feature 0002·0016, 2026-07-03)
- [x] **근본원인 조사**: insight.py·relationships.py·metadata_graph.py 정독 + Explore 2 fan-out + 라이브 실측(그래프 57,000+ 요소, circuit_open 38 = 네트워크 단절, probe_edge dblog/timeout/definer 반복). 4축 확정.
- [x] **축② probe 격리**(relationships.py): `_PROBE_MISSING_OBJECT_RE`+`unknown database` → 없는 DB negative 파단; transient `_backoff_validated`(last_validated_at 미래로 누적 backoff); `fetch_probe_candidates` backoff-window(`<= now()`) 제외. env `AGENT_RELATIONSHIP_PROBE_FAIL_BACKOFF_SEC`(3600).
- [x] **축① scan skip**(insight.py): datasource 순회 `conn_health.should_fast_fail`(DOWN 확정) skip + circuit_open health 기록. telemetry `db_skipped_circuit`.
- [x] **축③ graph sync batched+incremental**(metadata_graph.py, sync CLI): `_SYNC_MERGE_BATCH`(500) 커밋(fsync 5.7만→~114), `since`=updated_at watermark(agent_runtime.kv), CLI `--incremental`/`--full`.
- [x] **축④ 부하 분산**(bin, .env.example): cron 30분 `--incremental` + 04:17 `--full` 이중, wrapper 인자 pass-through, jitter/knob 문서화.
- [x] **검증**: 신규 단위 10(relationships 6 + metadata_graph 4) + 기존 회귀 0(test_relationships 57·units 10·insight health 66) + AST/`bash -n`. 적대 backend+qa 패널(REVIEW REV-20260703T093000-insight-load-spread).
- [ ] **배포(승인 필요)**: agent 이미지 재빌드 + insight-worker/local-llm-edge 재기동 + `sudo bin/install-metadata-graph-sync-cron.sh` 재설치. 라이브 검증 docker stats/WALSync/probe_edge 로그.
- [ ] verify-completion → commit/push → (PR·머지·배포 confirm) → 마감.

### insight-heartbeat-liveness — healthcheck false-negative 해소 (Minor §12.3, 2026-07-03)
- [x] **진단**: "AI 운영 현황" insight-worker 중단(unhealthy) 표시 but 실제 claude 로 활발 작동 → healthcheck 가 `insight_worker_last_cycle_at`(cycle 완료 시각)만 봐 9.4분+ 긴 cycle 을 stale→unhealthy 오판(false-negative).
- [x] **수정**(insight.py): `_touch_worker_heartbeat_progress`(30s throttle) 신규 + 스키마·테이블 순회에 삽입 → 진행 중 heartbeat 갱신. status 미변경, hang 탐지 보존.
- [x] **검증**: 신규 test 2 + insight 회귀 0(12 PASS) + AST OK. 경량 cycle SKIPPED 리뷰.
- [ ] **배포**: agent 이미지 재빌드 + insight-worker 재기동 → docker inspect healthy 확인.

### no-edge-conversation-answer — 대화 답변 edge(gemma) 폴백 완전 차단 (Major §12.3, 2026-07-07, conversation_audit FR-edge-fallback-conversation-context-loss)
- 진단 대상 대화: conv …9e0883bb "DB 설계 및 JSON 데이터 구성 검토"(owner admin, 1:1). content/PII 비전재.
- [x] **진단**: turn2~4 resolved_model=`gemma4:e2b`(edge-fallback, ctx 4096)로 silent 강등 → prompt_tokens 4096 고정, ~30K 히스토리 절단 → 맥락 완전 소실("? 맥락을 잃어버렸나요?" 명시 불만 + 자기 리뷰 부재 환각 + 거짓 부인). 코드+DB(llm_usage)+전사 삼각측량 high.
- [x] **사용자 결정**: 대화 답변에 gemma 개입 완전 차단·fallback 미구성·명백한 실패처리(2026-07-07 override).
- [x] **수정**: `_call_llm` → `conversation_answer_model()` 로 claude-haiku-4→claude-haiku-4-chat(edge-free) 라우팅 + shared 헬퍼 + litellm_config -chat/-chat-root deployment·fallback(edge 없음). 실패 시 기존 LLM-error 핸들러가 정직 안내.
- [x] **검증**: 신규 test 4 PASS + feature-0002 회귀 0 + py_compile·YAML OK. route-parity 실패=환경(clean main 동일) 확인.
- [ ] **배포(승인 필요, Major override 불가)**: ask-worker+web 재빌드 + bedrock-gateway 재생성. 배포 후 healthz + corroboration(task='agent' gemma 분포 0) 라이브 재측정.
- [ ] verify-completion → 적대 패널 → commit/push → (PR·머지·배포 confirm) → 마감.

### bedrock-chat-alias-probe-artifact-investigation — post-deploy 게이트웨이 400 1회성 오류 조사 (no-op, 2026-07-07, CHG-20260707T100640 후속)
- [x] **진단**: `bedrock-gateway` 로그의 `claude-haiku-4-chat`/`-root` `max_tokens must be greater than thinking.budget_tokens`(400, 10:37:18) 오류를 배포 타이밍 재구성·실행 이미지 직접 확인·정적 코드 추적·게이트웨이 라이브 재현으로 근본원인 규명.
- [x] **결론**: 코드 결함 아님 — `_call_llm`(유일 caller)은 claude-* 모델에 항상 `max_tokens=20000` 주입해 이 오류 경로에 도달 불가. FRICTION_LEDGER 의 post-deploy "live probe" 절차가 만든 1회성 아티팩트(재발 0, 실 트래픽 영향 없음). 코드 수정 불필요.
- [x] **기록**: `docs/improvements/conversation-audit/FRICTION_LEDGER.md` FR-edge-fallback-conversation-context-loss addendum + `unit/feature-0002-agent-core/docs/REPORT.md` 신규 절 + MODIFY.md CHG-20260707T134500 항목.

## 20260710T2325-alembic-multihead-gate — 병렬 마이그레이션 번호 경합 CI 게이트 (parallel-work-structure ITEM-02)

> 신규 최상위 섹션 헤더 timestamp 형식 = AGENTS.md §13.1 2026-07-10 개정(ADR-20260710T231146-parallel-id-hygiene)의 첫 적용 표본.

- [x] `bin/migrate-lint.sh` — head 단일성/파일명 4자리 번호 중복/`MAX_MIGRATION.txt` 정합 정적 검사(`--heads` 모드 신설 + diff/`--all` 모드에도 상시 편입, 라이브 DB 불필요) + self-test 4 케이스 추가(총 10).
- [x] `unit/feature-0002-agent-core/alembic/versions/MAX_MIGRATION.txt` 신설 — 의도적 충돌 파일(django-linear-migrations 패턴, RESEARCH W-005): 최신 head 1줄, 신규 마이그레이션·re-parent 시 동반 갱신(lint 강제).
- [x] `bin/alembic-reparent.sh` 신설 — 파일명 번호·revision·down_revision(현 head) 3곳 원자 치환 + MAX 갱신 + lint 재검. guard: origin/main 미머지 자기 브랜치 파일만(머지된 revision 재번호 금지 — 라이브 stamp 파손 방지).
- [x] `.github/workflows/ci.yml` test job "Migration gate" 스텝 추가(`--self-test` + `--heads`, 머지 게이트).
- [x] `docs/MIGRATIONS.md` 규약 절 추가(3중 장치 + 해소 절차).
- [x] acceptance (a)(b)(c)(e) 실증 — TEST.md §3 Run 기록 참조. (d) CI 스텝 실행은 본 cycle PR checks 로 확인.

## 20260711T1203-docs-archive — MODIFY/REVIEW §5.5 아카이빙 (사용자 지시 2026-07-11 "정책문서 분리/세분화")
- [x] MODIFY 124→15건(+본 엔트리)·REVIEW 109→15건 이관, 무손실 md5 증명, 상단 링크+REPORT 압축 정보(§5.5). feature-0003 선례(CHG-20260711T115053) 동일 계보.

## 20260713T1858-attach-update-versioned — 첨부 파일 갱신: 명시적 갱신요청 → 새 첨부 버전 전달 (conversation_audit FR-attachment-update-pasted-not-versioned, Major)
> `/_dqa:conversation_audit "첨부파일 갱신"`. friction-id=FR-attachment-update-pasted-not-versioned. 진단 대화(마스킹): 갱신요청 34대화 중 성공 3·붙여넣기 실패 27(structural). 코드 거주 primary=feature-0002(프롬프트), secondary cross-ref=feature-0003(파일명 정규화).
- [x] A1 — SYSTEM_PROMPT "DELIVERING THE EDITED FILE" 섹션 강화(명시적 갱신요청→attachment-edit 필수·brand-new SQL 예외 배제·filename 생략 유도·미첨부 시 재첨부 요청).
- [x] A2 — `_ATTACHMENT_DELIVERY_DIRECTIVE` 코드-권위 주입(compose_system_prompt parts, global row 무관 항상 effective, AUTH-1a drift 봉인).
- [x] A3(cross-ref feature-0003) — `_next_version_filename` idempotent(_v<n> 이중접미 방지) + materialize 명명 코드-권위(`<stem>_v<n>.<src-ext>`, LLM 명명 무관·확장자 강제). 명칭 정합 코드 보장.
- [x] unit docs: MODIFY(CHG-20260713T185846-attach-update-versioned) + 본 TASK + REPORT cross-ref. feature-0003 MODIFY 동반.
- [x] 검증: 단위테스트 신규 6종(directive 항상 주입·global override 존속·명명 idempotent·LLM명명 정규화·SEC-1 안전확장자) 타깃 36 PASS(내 diff 신규 실패 0; 전체 스위트 pre-existing 11 실패=b2e86880 baseline test debt, 첨부·내 diff 무관).
- [x] §18.8 적대 패널(full panel default — 프롬프트 code change·표 키워드 미매칭): security+backend+qa 3렌즈. SEC-1(MINOR 확장자승격 회귀) 봉인, 나머지 REFUTED → REVIEW REV-20260713T185846.
- [x] verify-completion(feature-0002) PASS → commit(f5e4b69b)/push → PR #771 merge(main ee4f8de6) → 배포(4서비스 ee4f8de6·런타임 실증·/healthz) → 원장 fixed:deployed:unverified-live(CHG-20260714T031500-attach-update-deploy).
- [ ] commit/push(auto-sync) → PR·머지·배포(Major=confirm) → 배포검증(worker+web 재빌드) → 원장 갱신.
- [ ] 라이브 실측(배포 후 corroboration 재측정: 갱신요청 대화의 assistant 버전 생성 비율 상승·```sql 붙여넣기 감소)는 다음 audit 분리분(코드/테스트만으로 마찰 소멸 단정 금지).
## 20260714T1531-sysvar-select-guard — MySQL 시스템 변수 읽기(@@) denylist 과차단 해소 (conversation_audit FR-sysvar-select-denylist-overblock, Critical)
> `/_dqa:conversation_audit "초기화 쿼리 환경 옵션 검토"`. friction-id=FR-sysvar-select-denylist-overblock. 진단 대화(마스킹): …e6add7f1 — 사용자가 "환경 옵션 직접 확인 후 판단" 명시 지시 → `SELECT @@lower_case_table_names, @@version`(단일 read-only SELECT)이 `denylist match: @@` 로 차단 → assistant 가 OS 기본값 추정으로 대체("MySQL 설정 확인 불가" 명시). 어제 출하한 read-only SHOW VARIABLES/STATUS 화이트리스트(FR-readonly-query-shapes)와 동일 정보 클래스라 태세 불일치.
- [x] `src/modules/sql_guard.py` — `_DENYLIST_PATTERNS`(MySQL)에서 `@@` 패턴 제거(사유 주석 부착). T-SQL denylist 의 `@@` 는 유지(MSSQL 메타 열거 차단 태세 불변). 쓰기 경로(`SET @@`/`SET @`/`:=`)는 기존 denylist+shape 게이트가 계속 차단.
- [x] `tests/test_readonly_query_shapes.py` §5b — sysvar SELECT 허용 3케이스(session/GLOBAL/sql_mode) + 쓰기 경로 차단 3케이스 + tsql `@@` 차단 유지 1케이스.
- [x] 사용자 승인: AskUserQuestion 2026-07-14 "제거 진행"(Critical §12.3 — sql_guard 허용범위).
- [x] §13.1 동시수정 기록: `.worktrees/feature-0002-agent-core`(branch ai/claude/feature-0002-agent-core)를 병렬 세션(FR-partial-evidence-false-verification 작업, tools.py/agent_core.py)이 점유 중이라 본 작업은 별도 worktree `feature-0002-sysvar-guard`(branch ai/claude/feature-0002-sysvar-guard)로 격리. 파일 교집합 0(sql_guard.py/test_readonly_query_shapes.py vs tools.py/agent_core.py).
- [ ] 검증: 타깃 가드 테스트 4파일 PASS(사전 실행) + 전체 회귀 + §18.8 적대 패널(security+backend+qa) + verify-completion.
- [ ] commit/push(auto-sync) → PR·머지·배포(Critical=confirm) → 배포검증 → 원장 갱신(docs-only 후속).
## 20260714T0632-partial-evidence-grounding — 부분 증거(절단 미리보기·차단 옵션조회) 전수 단정 환각 봉인 (conversation_audit FR-partial-evidence-false-verification, Major)
> `/_dqa:conversation_audit "첨부파일과 실제 DB 비교 검증"`. friction-id=FR-partial-evidence-false-verification. 진단 대화(마스킹) …e6add7f1: 사용자 명시 불만 "답변 내 환각이 극심합니다"(90일 내 최초 '환각' 명시). ground truth(첨부 sha256 대조)로 3중 환각 확증 — ① 183행 중 50행 절단 미리보기(gunzlog 전량 미열람)를 전수 검증처럼 서술 + 첨부 141행에 실재하는 TRUNCATE 를 "누락" 오진 ② 정정 답변도 61행 중 50행으로 동일 반복 ③ `SELECT @@lower_case_table_names` 거부 후 기본값 추측 → 대소문자 반대 결론(실측 1). corroboration: 30d 절단 노출 8/46 대화(17%, structural surface). 코드 거주=feature-0002.
- [x] A(L2) — `tools.py` execute_sql 절단 안내문에 epistemic 자기교정 지침(미열람 행 존재/부재/개수/완전성 단정 금지·좁혀 재조회 유도·CSV 는 모델 비가독 명시). `_format_result_sets` 절단 마커에도 "미열람·단정 금지" 부기.
- [x] B(구조) — `_format_result_sets` char-budget 확장(expand_rows=500·expand_char_budget=12,000): 소형 결과는 캡 너머 전부 표시(183행 목록 대조가 미리보기 안에서 종결), 광폭/대형 결과는 기존 50행 캡 유지(컨텍스트 보호 불변). stats out-param 으로 정직한 표시 행수 안내.
- [x] C(L1) — SYSTEM_PROMPT "HANDLING RESULTS — NEVER FABRICATE" 확장 4규칙: PREVIEW-TRUNCATED epistemics · ABSENCE/COMPLETENESS 완전 근거 계약(불가 시 "미확인" 명시) · 첨부↔DB 비교는 양측 조회 선행(describe_table/describe_routine) · SERVER OPTIONS 기본값 추측 금지(실제 값 조회 — `@@var`/SHOW VARIABLES).
- [~] ~~D(L2) — @@ denylist 거부 SHOW VARIABLES 힌트~~ **제거(rebase 재평가)**: 애초 진단의 ③번(@@lower_case_table_names 거부)을 **병렬 세션 CHG-20260714T153113-sysvar-select-guard(FR-sysvar-select-denylist-overblock)가 MySQL `@@` denylist 를 아예 제거**해 `SELECT @@var` 가 통과하게 되면서 "거부 시 힌트"는 dead 경로가 됨 → `_server_variable_redirect` 삭제. ③번은 그 가드 허용 + 본 C(L1) "실제 값 조회" 계약으로 커버(정직 — dead code 미출하). 회귀 가드 `test_server_variable_redirect_removed`.
- [x] 검증: `tests/test_partial_evidence_grounding.py` 신규 11 PASS(확장/캡 유지/500 상한/legacy 캡/절단 안내/@@ 힌트·MSSQL 제외·프롬프트 계약) + 전체 회귀 pytest EXIT=0(feature-0002+0003).
- [ ] §18.8 적대 패널(full panel default — 프롬프트·도구 피드백 code change) → REVIEW entry.
- [ ] verify-completion(feature-0002) → commit/push(auto-sync) → PR·머지·배포(Major=confirm 완료: PLAN-APPROVED A+B+C+D + PR/배포 인가, AskUserQuestion 2026-07-14) → 배포검증(4서비스) → 원장 갱신.
- [ ] 라이브 실측(배포 후 corroboration 재측정: 절단 노출 대화의 환각/정정요구 재발 0 확인)은 다음 audit 분리분(코드/테스트만으로 마찰 소멸 단정 금지).
## 20260714T-attach-review-grounding — 첨부-답변 정합성 실데이터 감사 후속: 첨부섹션 grounding 모순 제거 + LLM 오류 분류 확장 (Major)
> 계기: 실런타임 데이터 감사(PG agent_runtime.core_attachments 411첨부/81대화 + MinIO 대조). 결론 — 토큰-초과 에러 0건(전 첨부 소형, text 최대 12.7KB)이라 "토큰-초과 대응"은 현 마찰 미해소. 실제 정합성 실패의 진짜 축은 ① ingest/kind 라우팅(대체로 해소) ② 접근·세션창(보안 민감·deferred) ③ 환각(grounding) ④ 모델 alias/오류 표면화. 본 cycle 은 ③(모순 제거 부분)·④ 착수.
- [x] ③ grounding(모순 제거·최소): `agent_core.py` `_build_attachment_context_section` 첨부 INSTRUCTION 에서 전역 규칙과 모순되던 "do NOT run execute_sql ... unless the user explicitly asks" 억제 문구 제거 → 순수 코드리뷰는 DB 불필요 유지, 실 DB 상태 주장은 전역 규칙("COMPARING an attachment against the live DB", 병합 PR #793 FR-partial-evidence)에 위임. **중복 아님**: 전역 grounding 은 이미 있으나 첨부 섹션이 이를 무력화하던 latent 모순을 봉인.
- [x] ④ LLM 오류 분류 확장: `llm_provider_health.py` `classify_llm_provider_error` 에 `bad_model`(litellm "Invalid model name passed in model=auto/core/edge"·OpenAI model_not_found)·`context_length`(Anthropic/Bedrock/OpenAI 컨텍스트 초과 표현 통합) 버킷 추가 → raw 400 덤프 대신 친절 한국어 메시지. 요청-레벨 오류라 글로벌 provider health 미오염(`persist_health=False` + 기존 confirmed=False skip 이중 안전망). `agent_core.py` 호출부에 persist_health 게이트.
- [x] 검증: 신규 테스트 `test_attach_grounding.py`(5) + `test_llm_provider_health.py` 확장(8: bad_model/context_length/persist_health/순서/회귀) 로컬 PASS. feature-0002 전체 회귀 로컬 EXIT=0(신규 실패 0).
- [x] §13.1 동시수정 기록: REGISTRY 활성 `ai/claude/feature-0002-agent-core`(worktree feature-0002-agent-core)가 agent_core.py 를 점유 이력(FR-partial-evidence, 현재는 병합됨 PR #793). 본 변경은 그 병합분 위(base 57f21121)에서 **상보적**(전역 규칙 위임)이며 편집 라인(첨부 섹션 ~L854 / 오류분류 caller ~L3956)은 전역 규칙(L103)과 비겹침. 머지 시 재확인.
- [x] §18.8 적대 패널(프롬프트·오류경로 code change) → REV-20260714T210000 (fresh 2렌즈 SUBAGENT: MAJOR1[정적 억제 잔존]·MINOR2 전건 수정).
- [ ] verify-completion(feature-0002) → commit/push(auto-sync) → PR·머지·배포(deploy_scope: included) → 배포검증.
- [ ] deferred(별도 cycle 문서화): ④ 근본(`model=auto/core/edge` alias 누출 추적) · ① text-inline 회귀테스트 · ② 접근·세션창(share-window 보안 민감).
## 20260714T221500-attach-case-insensitive-grounding — 라이브 실측 잔존 false-missing 봉인 (Major, CHG-20260714T210000 과 함께 배포)
> 계기: FR-partial-evidence 라이브 실측(배포본 244e6bec 직접 재현). 원 증상(charactermakinglog 오진) 소멸 확인했으나 잔존 false-missing 1건 발견 — `gunzlog.LoginEventLog`(첨부 162행 활성 TRUNCATE 실재·활성 131개 중 유일 CamelCase)를 "쿼리에 없는 누락"으로 오판. 근본 = 실 DB(lower_case_table_names=1) 소문자명 vs 첨부 CamelCase 를 모델이 대소문자 구분 비교. 사용자 "잔존 먼저 조사·수정 후 함께 배포" 선택(AskUserQuestion 2026-07-14).
- [x] 근본원인 규명: LoginEventLog=유일 CamelCase=유일 false-missing 상관 + SYSTEM_PROMPT 에 식별자 case-fold 비교 지침 부재 확인(L102~104 · L250-251 은 표기보존=쿼리작성용).
- [x] 수정: `agent_core.py` SYSTEM_PROMPT grounding 계약에 "IDENTIFIER CASE" 규칙 추가(case-insensitive 매칭·case-only≠absence·absence 단정 전 case-folded 검색/probe). 프롬프트 레버(모델 추론 대조라 코드 lever 부재).
- [x] 테스트: `test_attach_grounding.py` +3(규칙 존재·근본 명시·case-fold 검색 요구) = 파일 8 PASS. 로컬 36 PASS.
- [x] §18.8 적대 패널(프롬프트 grounding code change) → REVIEW REV-20260714T221500 (+ Cycle B REV-20260714T210000 동반 기록).
- [x] `make test` 전체 회귀: cycle 자체 테스트 전부 PASS(로컬 41)·무관 4건 pre-existing/환경(신규 회귀 0, 연역+경험 확정).
- [ ] verify-completion(feature-0002) → commit/push → PR → merge → 배포(deploy_scope: included, Cycle B ③④ + 본 case-fix 함께) → 배포검증(4서비스 GIT_COMMIT) → 라이브 재-재현 LoginEventLog 오판 소멸 확인 → 원장 반영.
## 20260714T233000-attach-table-coverage — 라이브 실측 잔존 결정론적 코드 봉인 (Major, 사용자=Option C "코드로 결정론적 봉인")
> 계기: CHG-20260714T221500(case 프롬프트 레버) 배포(ee3424c3) 후 라이브 재-재현에서 잔존 확인 — 모델이 case 인지는 하나 여전히 LoginEventLog '누락' 오기재 + lcase 미실측 정규화 제안(프롬프트 레버=확률적 완화 한계). 사용자 "코드로 결정론적 봉인" 선택(AskUserQuestion 2026-07-14).
- [x] 근본: 첨부↔DB 테이블 대조가 모델 추론이라 대소문자 비결정 → 코드로 이관.
- [x] 신규 tool `check_table_coverage`(tools.py): DB 테이블명 정본 기준으로 첨부가 그 테이블을 **조작(TRUNCATE/DELETE/DROP/…)** 하는지 대소문자 무시 판정(`_operated_tables`). 주석 분리(`_split_sql_active_comment`), truncated 캐비엇, USE 스키마 귀속. deferred import 첨부 로더, `_struct_schema_access_error` 게이트, TOOL_DEFINITIONS+_TOOL_HANDLERS 등록.
- [x] agent_core: SYSTEM_PROMPT 라우팅(커버리지 비교→도구, truncated 면 미확인) + reason/work narration.
- [x] §18.8 적대 2렌즈 패널(REV-20260714T233000): BLOCKING2(B1 절단·B2 주석)·MAJOR1(M1 이름 등장 오집계)·MINOR2 적발 → 조작-동사 추출+주석분리+절단캐비엇+USE귀속 전면 재설계 봉인. 보안 5벡터 REFUTED.
- [x] 테스트 `test_check_table_coverage.py` 12 PASS(seal + B1/B2/M1/m1 회귀 + 헬퍼). `make test` 신규 회귀 0(pre-existing 4건 무관·flaky 1건 재실행시 소멸).
- [x] verify-completion → commit/push → PR #803 merge(main 3c8e78df) → 배포(4서비스 3c8e78df·tool live) → 라이브 재-재현은 외부 gunzgame DB unreachable(err 2003)로 미완(외부 인프라).
## 20260715T104500-friction-ledger-reconcile — FR-partial-evidence 원장 arc 정합 (docs-only, 코드 0)
- [x] FRICTION_LEDGER FR-partial-evidence 엔트리에 후속 봉인 arc(case 레버 부분작동→결정론 도구 배포 3c8e78df) + status `unverified-live` 유지 근거 반영. CHG-20260715T104500 · REV-20260715T104500 [SKIPPED].
## 20260715T050000-conv-alias-leak-guard — 대화 답변 model alias 누출(Bedrock 400) 봉인 (deferred ④, Major)
> 계기: 첨부-답변 정합성 실데이터 감사(deferred 축 ④). 실관측 — 다수 대화·`__ask_worker__` 에 `LLM 호출 오류: Error code: 400 ... Invalid model name passed in model=auto/core/edge/claude`. 선행(CHG-20260714T210000)의 friendly-message(bad_model) 계층은 표면만 완화, 근본(내부 alias 가 Bedrock 프록시로 raw 전달)은 미해소. 서브에이전트 근본 추적으로 누출 경로·choke-point 확정.
- [x] RC 확정: 대화 답변 경로(`_call_llm`)는 고정 Bedrock 클라이언트로 나가고 tier-resolve 안 함(FR-edge-fallback: 대화는 gemma 강등 금지). `conversation_answer_model()`이 미매핑 alias 를 identity 통과 → 로컬 게이트웨이 alias(auto/edge/core/code)·bare 'claude' 가 Bedrock 프록시로 새어 400. 운영 `.env` `OPENAI_MODEL=auto` 가 대표 트리거.
- [x] fix(choke-point): `shared/model_catalog.py` `conversation_answer_model()` — 로컬 alias(`is_local_llm_model`)·bare 'claude' 를 대화 기본 chat(`claude-haiku-4-chat`)로 fail-loud(warn log) 해소. 등록 Claude(claude-sonnet-4)·이미 해소된 chat alias 는 identity(무회귀). **`_call_llm` tier-resolve 미러링은 명시적 거부**(대화를 gemma 로 강등 — FR-edge-fallback 위반).
- [x] 검증: `tests/test_conversation_answer_no_edge_alias.py` 확장 — 기존 `edge→edge` identity 기대(옛 버그 인코딩)를 새 계약으로 갱신 + G2b(누출 alias→chat 파라메트릭)·G6(해소 대상 litellm 등록명 invariant)·G7(`_call_llm` 아웃바운드 chat)·G8(패널 회귀: 예산 outbound 기준·max_tokens>5000). 파일 15 PASS. feature-0002+0003 회귀: 신규 실패 0(test_share_redaction_invariant 7건은 base main 에서도 동일 실패=pre-existing, 내 diff 미참조).
- [x] §13.2.2 F2: shared/ 단일-mutator = 본 cycle(ai/claude/conv-alias-leak-guard). 편집 `shared/model_catalog.py`(1함수)+`src/agent_core.py`(_call_llm budget 산정), 병렬 shared mutator 없음(REGISTRY 확인).
- [x] §18.8 적대 패널(security+backend/routing 통합 6축) → **CONFIRMED-DEFECT#1**(초기 fix 가 outbound 만 해소하고 max_tokens 를 원본 기준 산정→ -chat 고정 thinking budget 5000 대비 2048<5000 2차 400) **수정 완료**(`_call_llm` budget_model 도입 + G8 회귀) + 5축 REFUTED + 2 PLAUSIBLE-RISK 수용. → REV-20260715T050000-conv-alias-leak-guard.
- [x] verify-completion(feature-0002) PASS → PR #807 병합(main 91280bb2) → 배포(4서비스 91280bb2·soak 통과) → 배포본 grep 실증. **Cycle A 완료.**
## 20260715T060000-attach-inline-honesty — text-inline 회귀테스트 + 첨부 cap-note 정직화 (deferred ①+②-backend, Minor)
> 계기: 첨부-답변 정합성 실데이터 감사의 deferred 축 ①(text-inline 회귀테스트 부재)+②-backend(cap 초과 text 파일 노트가 MinIO 장애로 오귀속). ② 서브에이전트 진단: share-window 는 라이브-ask 첨부 경로에 없음(비보안) → 마찰은 프론트 라벨 비대칭(Cycle C)+backend cap-note. 본 cycle 은 ① + ②-backend.
- [x] ① text-inline 회귀테스트 신설: `tests/test_attach_inline_honesty.py` — text kind 첨부 content 가 sandbox 아닌 **인라인**으로 주입됨을 `_build_attachment_context_section` 출력으로 검증(과거 2026-05 다수 대화의 "sandbox ingest 대기" 오라우팅 회귀 방지). `_load_attachment_inline_texts` monkeypatch.
- [x] ②-backend cap-note 정직화: `src/agent_core.py` `_build_attachment_context_section` — 인라인 map 에 없는 text 파일 노트 `(content unavailable — check MinIO connectivity)` → 정직 노트. **원인 미단정**(cap 초과 or 일시 판독불가) + 회복경로(재첨부) + `len>0`(cap 귀속) vs `len==0`(판독실패 가능·cap 귀속 안 함) 분기. 기존 문구가 모델의 MinIO 장애 fabrication 유발(관측 대화 20260615061233·FRICTION_LEDGER text-inline count cap).
- [x] 검증: 신규 4 PASS(text 인라인·content_len·len==0 note·len>0 count). 다른 테스트의 옛 노트 문자열 참조 0(grep). feature-0002 전체 회귀 신규 실패 0.
- [x] §18.8 적대 패널(프롬프트 note code change) → **CONFIRMED-DEFECT ×3 수정**(거짓 회복경로 파일명→재첨부·"size cap" 오기 삭제·len==0 진단역전 교정) + 3축 REFUTED. → REV-20260715T060000-attach-inline-honesty.
- [ ] verify-completion → commit/push(auto-sync) → PR·머지·배포(deploy_scope: included) → 배포검증.
- [ ] ②-frontend(app.js staged-flush 라벨 대칭)은 Cycle C 로 분리(웹 자산 변경 → visual verification 필요).

## 20260715T082345-schema-name-case-drift — 스키마명 서버-실제-case 해소 (A 런타임 canonicalize+grounding, Critical)
> 계기: `/_dqa:conversation_audit` "테이블 구조 정합성 검토"(product 97 대화 20260715070720-c202bcf8). allowlist(WebProductDatabases.SchemaName)가 서버 실제 case 와 다르게 소문자 저장(서버 `DEV_1_1_1_20` ↔ 저장 `dev_1_1_1_20`) → case-sensitive MySQL(lctn=0)에서 describe_table/search_tables/INFORMATION_SCHEMA 전부 0행 → assistant '테이블 없음' 오판·give-up. structural: 205 allowlist 중 85 case mismatch(MySQL 실패클래스 ~18, product 94/97/110/121). graph(동기 snapshot) ground truth = DEV_1_1_1_20 63테이블.
- [x] A tools.py: `_mysql_schema_case_map`(라이브 INFORMATION_SCHEMA.SCHEMATA·conn 캐시·모호 제외) + `_canonical_schema_name` + `_canonicalize_schema_args_mysql`. `execute_tool` 단일 choke 에서 schema_name 정규화(라우터·비라우터, MySQL 한정·MSSQL no-op). `_DatasourceRouter.refresh_case` 로 `_allow_schemas`(grounding/DISPLAY) 실제 case refresh.
- [x] A agent_core.py: 멀티-ds primary 연결 직후 refresh_case → run-start grounding 실제 case.
- [x] B(cross-ref feature-0003) admin_products.py `admin_update_product_databases` write-path 서버-실제-case 정규화(`list_server_databases`·SSRF 선행·degrade-safe·MySQL only·모호 제외). admin.js `.toLowerCase()`/수기 입력 무관 backend chokepoint. (초기 admin_console picker 후보는 패널 재진단으로 wrong-endpoint·admin.js 무효화 확인 → 원복.)
- [x] 단위테스트: `tests/test_schema_name_case_drift.py`(15) + feature-0003 `tests/test_available_databases_case.py`(2). 보안 불변식(canonicalize 가 allowlist 게이트 판정 무변·미허용 스키마 확장 0) 포함.
- [x] 전체 회귀: feature-0002+0003 **2107 passed, 2 skipped**(EXIT=0). 보안·멀티ds 회귀(sql_trust_boundary·mssql_security_boundary·multi_datasource·product_multi_datasource·mssql_crossdb·datasource_registry) 무회귀.
- [x] §18.8 적대 패널(security+backend+qa — datasource 접근 경계) → REV-20260715T082345-schema-name-case-drift.
- [ ] verify-completion → commit/push(auto-sync) → PR·머지(Critical=confirm)·배포(4서비스, Critical=confirm)·배포검증.
- [ ] 라이브 재현(Phase 11b): 배포 후 원 마찰(P97 대화) 재현 — describe_table/search_tables 가 DEV_1_1_1_20 63테이블 반환·give-up 소멸 실측(unverified-live).
- [ ] deferred(§정직·백필=admin): 기존 18 MySQL drift 행 백필(A 런타임이 seal 이므로 hygiene) · 외부-datasource picker 는 control-plane conn 조회 한계(datasource-scoped picker 후속).

## 20260715T2347-probe-throttle-monotonic-flake — LLM 헬스 probe throttle 이 갓-부팅 워커/러너에서 첫 probe 를 spurious throttle (CI flake + 잠복 프로덕션 버그) (Minor §12.3 — feature-0002 agent-core, 백엔드 단건조건. /_template:entry arg-given dispatch)

- 계기: 별개 PR(#832 graph-edge-drag-perf, 프론트 전용)의 CI 가 무관한 `test_probe_pings_when_restricted_for_recovery` 로 red. 같은 base #831 은 green → flaky. 사용자 결정: flake 먼저 수정.
- 근본원인: `probe_provider` throttle 게이트 `if now - float(_PROBE_STATE["ts"]) < min_gap`(now=`time.monotonic()`=부팅 이후 절대초, min_gap=force면 5·아니면 TTL 60). 초기/미-probe `ts=0.0` 이면 `now - 0 = now`. **갓-부팅 러너/워커에서 `monotonic() < min_gap`** 이면 `now < 60` → 첫 probe 가 spurious throttle. force=False+restricted 테스트만 실패(0 ping, 기대 1); 러너 uptime 이 60 을 넘었는지에 따라 통과/실패가 갈리는 flake. **잠복 프로덕션 버그**: 갓-부팅 web 워커의 첫 restricted-복구 probe 가 누락될 수 있음(자동복구 지연).
- 수정: [x] `llm_provider_health.py` throttle 판정에 `last_ts > 0.0 and` 가드 추가 — `ts=0.0`(미-probe 센티넬)은 monotonic 절대값 무관하게 throttle 되지 않음(첫 probe 항상 허용). 실제 스탬프(ts>0) 이후에만 TTL/5s throttle 적용(정상 동작 불변). 테스트 무의존 수정(테스트가 ts 를 리셋하지 않아도 결정적).
- 검증: [x] `test_llm_provider_health.py` 39 PASS(신규 회귀 잠금 2: ts=0.0 센티넬 non-throttle·최근 ts throttle 유지) · [x] **flake 조건 재현**(monotonic=10<60·ts=0.0·restricted → 수정본 복구 ping 1회, 구코드는 0) · [ ] verify-completion → PR·머지(→ #832 CI green 재개).
- worktree `ai/claude/feature-0002-probe-throttle-monotonic-flake`(base main 2188fb34). REV/CHG/TEST-20260715T234757-probe-throttle-monotonic-flake.

## 20260722T050006-branch-chain-race — 재답변(reanswer) 브랜치 체이닝 동시성 경합으로 내 메시지가 화면에서 사라짐 (Major §12.3, PLAN-APPROVED — 코어 write 경로, cross-cut 정본 feature-0019-message-editing. /_template:entry arg-given dispatch)

- [x] 진단(사용자 신고 + 라이브 데이터 확정): 브랜치 대화 `20260722015229-79da15cb` 에서 '요청사항 수정(재답변)' 후 **보낸 user 메시지가 로그에서 사라지고 assistant 답변만 쌓임**. 근본원인: 새 메시지 parent 를 대화-공유 포인터 `active_leaf`(core)/`active_display_leaf`(display)를 **매 write 마다 재-read**해 결정 → 동시 재답변 setup/overlap 으로 리셋되면 최종 답변이 그 턴 user 의 **형제**로 붙어(자식 아님) active-path 걷기에서 user 누락. display 트리 실측: 답변 1300 parent=1270(분기점) ← user 1299 형제. core 도 5243→5091 등 4행 오염.
- [x] 결정(사용자 승인, AskUserQuestion): per-run thread-local 커서로 한 run 안 write 를 이어붙여 active_leaf 리셋과 무관하게 체인 무결. 비분기 대화는 기존 경로 그대로(INV-1). + 이미 오염된 대화 데이터 복구 + 배포.
- [x] 구현(3 파일): `runtime_backend.py` run-cursor API(`branch_run_begin/end/active`·`branch_chain_get/set`, thread-local) · `agent_core.py` `_save_message`(core) 커서 체인 + `_run_agent_core` begin(has_branches)/teardown end() · `memory.py` `save_memory_message`(display) 커서 체인. 커서 활성 시 첫 write 만 active_leaf 1회 read, 이후 run 커서에 이어붙임 + leaf 전진. `branch_run_active()`=false(비분기·비-run 호출) 면 완전 기존 경로.
- [x] 단위 테스트(`tests/test_branch_chain_race.py`, 4 PASS): ①active_leaf 리셋에도 답변→user 체인 ②멀티스텝(user→step→step→답변) run 내 체인 ③비분기 무영향(parent None·leaf 미전진, INV-1) ④teardown 커서 해제(스레드 재사용 leak 방지).
- [x] 회귀: `py_compile` 3파일 OK · feature-0002 전체 pytest **PASS**(agent 이미지 마운트, 2 skip·0 fail). `make test` 는 이 환경 docker build 인프라 실패(`invalid proto:`)로 미실행 — 마운트 우회.
- [x] §18.8 적대적 리뷰(subagent, general-purpose) 완료: SHIP-WITH-FIXES — [1] teardown 예외-비안전 needs-fix 반영(end()→run_agent finally + entry 무조건 리셋), 6축 not-a-defect. 리뷰 권고 테스트 2종(core-store·leak 봉인) 추가 → 단위 6 PASS. REV-20260722T050006-branch-chain-race.
- [x] 배포(무중단, deploy-all, 2026-07-22): PR #874 머지 → main **5a32a480** → `sudo -E bin/deploy-web.sh`(web-a/b 롤링 soak PASS + insight-worker·ask-worker `mysql-ai-agent:5a32a480` 롤아웃 healthy + gateway 무드리프트). 워커 코드 변경이라 전체 스코프.
- [x] 데이터 복구(POST-DEPLOY, 2026-07-22): 대화 `20260722015229-79da15cb` 오염 5행 재링크 — 트랜잭션 `UPDATE 1`(display 1300→1299) + `UPDATE 4`(core 5188→5187·5190→5189·5198→5197·5243→5242) COMMIT(dry-run count 일치). 복구 후 active-path=`1269→1270→1299→1300→1311→1312`(사라졌던 user 1299 복귀)·오염 잔존 0·**`/api/history` 6 메시지 반환에 "로그 흐름만…" 포함**(UI 렌더 경로 실검증). 오염 범위=이 대화 1건뿐(전수 탐지).
## 20260722T033854-enum-schema-grounding — ENUM 자동등록 schema-grounding 게이트 (환각 DB/테이블 차단, Major §12.3 — /_template:entry arg-given dispatch)
> 계기: 메타데이터 거버넌스 UI "ENUM 검토 큐"에 `scope: mysql-kr-an1-auth`(auth 데이터소스) 기준으로 존재하지 않는 `dbLog` DB + 이 scope 에 없는 게임 재화 `Currency` 테이블(골드/젬/스태미너)이 자동등록(`자동 등록됨`)됨. 정상 `dbAuth.AccountBasicInfo.CountryCode` 와 혼재. RC: 대화 자율수집(`_enum_autopropose`)이 LLM 이 답변 프로즈에서 뽑은 (schema, table, column) 을 실제 스키마 카탈로그 대조 없이 verbatim 등록(`kb_glossary.auto_promote_or_queue_enum` 가드는 비어있음만 검사). auth scope 는 `dbAuth` 계열만 보유하는데 게임 재화 질문에 LLM 이 `dbLog.Currency`/bare `Currency` 를 환각.
- [x] 예방 게이트: `agent_core._enum_autopropose` 에 schema-grounding 추가 — scope 의 `table_insight` fact 카탈로그(agent 가 LLM 에 주입하는 grounding 정본, `cfg.ds_fact_like` 로 활성 datasource 한정)로 (schema, table) 인덱스 1회 구성 후, 카탈로그에 명백히 부재한 제안은 등록·큐잉 skip(reject)+`enum_autopropose_skip_ungrounded` 로깅. 카탈로그 미가용/빈 scope → fail-open(기존 동작 보존, false-reject 방지).
- [x] 순수 판정 로직(SQL-free)은 `kb_glossary.build_known_table_index`/`is_enum_grounded` 로 분리(코어 SQL-only 계약 유지·단위테스트 용이). MySQL(`schema.table`)·MSSQL(`db.schema.table`→enum `db.table`) 양 계층 대조 + 대소문자 무시(schema-name case drift 대비).
- [x] config flag `AGENT_ENUM_SCHEMA_GROUNDING`(기본 on) 신설 — 필요 시 게이트 비활성.
- [x] 소급 정리: `kb_glossary.sweep_ungrounded_enum`(source='auto' 삭제 + feedback pending/auto_promoted→rejected, 수동 큐레이션 보존) + 운영자용 `scripts/enum_grounding_sweep.py`(dry-run 기본, `--execute`). 라이브 prod 실행은 배포 후 운영자 단계(여기선 로직만 검증).
- [x] 단위테스트: `tests/test_kb_enum_grounding.py` 13 PASS — 정규화 전개·판정(재현 시나리오 dbLog/bare Currency 차단·정상 dbAuth 통과·fail-open·대소문자)·sweep(none-idx no-op·dry-run 무변경·execute DELETE+UPDATE·grounded 무변경). 기존 enum/glossary 35 PASS + feature-0002 전체 회귀 신규 실패 0. ruff clean.
- [x] §18.8 적대 패널(backend+security+qa — 자동등록 grounding·scope 격리) → **BLOCKER 0 · MAJOR 1(sweep common-scope 오조회)+MINOR 2(read-backend 결합·빈-set footgun) 수정 · QA wiring 테스트 신설** → REV-20260722T033854-enum-schema-grounding.
- [x] 자가수리(self-heal, 사용자 추가 요청): insight-worker tick 이 스키마 스캔 직후 활성 scope 의 '없는 DB(schema)' enum 을 소급 회수 — `insight._enum_self_heal` + `else` 블록 배선(카탈로그 refresh 직후·scope 유효·기본 MySQL 커버). 검증 기준 = 워커가 방금 로드한 **완전한** 실제 스키마 목록(`_scan_schemas`=load_known_schemas) → `kb_glossary.sweep_unknown_schema_enum`(schema_name ∉ 실제목록 제거). config flag `AGENT_ENUM_SELF_HEAL`(기본 on). ask-worker 경로는 예방 게이트(_enum_autopropose)로 이미 커버.
- [x] self-heal 적대 패널(backend+security+qa, 2 라운드 — 파괴적 자동 DELETE): Round1 **BLOCKER 1 + MAJOR 2** → 안전 재설계로 Round2 **RESOLVED** — ① 부분 카탈로그 false-deletion → table_insight 점진 카탈로그 대신 **완전한 실제 스키마 목록**(load_known_schemas) 기준 schema-존재 검증(bare-schema 미터치·MySQL allowlist·MSSQL 제외)으로 원천 차단 ② 매 8s 낭비/파괴 반복 → `scan_started` 게이트 ③ grounding decoupling → `AGENT_ENUM_SCHEMA_GROUNDING`+`AGENT_ENUM_SELF_HEAL` 결합. Round2 잔여 **MINOR-A(권한회수/부분조회 축소 오삭제)** → **catalog-shrink 가드**(스키마 부재 2회 연속 관측 시에만 삭제, per-scope KV persistence) 봉인 + NIT-C/D 정리. → REV-20260722T033854(self-heal 라운드).
- [x] self-heal 테스트: `test_enum_self_heal.py`(13: 게이트 결합·scanned·engine allowlist·fail-open·dedup·예외·shrink-가드) + `sweep_unknown_schema_enum`(confirm/빈-schema 포함). 총 신규 **37 PASS** · feature-0002 전체 회귀 신규 실패 0 · ruff clean.
- [ ] verify-completion → PR·머지 → 배포(make deploy-web) → 라이브 검증(기존 dbLog.* 정리 실증 + self-heal 동작). ①즉시 정리=`scripts/enum_grounding_sweep.py` 운영자 실행 ②지속 self-heal=insight tick 자동.
- worktree `ai/claude/enum-schema-grounding`(base main 66a48870). commit 87b06a1f(예방 게이트) + self-heal(후속).

## TASK-20260724T054326-timeout-console-sync — LLM upstream 타임아웃 ↔ 관리 콘솔 AGENT_TIMEOUT_SEC(live) 요청 단위 동기화 (Major §12.3 — hot-path LLM 호출·타임아웃; /_template:entry saga 6층·cross-feature primary=feature-0002+feature-0007)
> 계기(사용자): "`request_timeout` 또한 `설정 > 실행 타임아웃 > 에이전트/쿼리 실행 타임아웃` 설정값과 동기화되도록 구성". 선행 llm-timeout-align 이 gateway request_timeout 을 정적 300 으로 올렸으나 gateway 는 별도 프로세스라 콘솔 live 변경을 추종 못 하는 drift 잔존.

### §1.2 Completion Checklist
- [x] 진단(라이브 결정 실험): litellm 이 요청 body `timeout` 을 per-attempt upstream 타임아웃으로 존중 확인(body=5→408·=200→200 @11.7s) → 앱이 요청마다 live 값 body 전달이 유일한 실동기화 수단.
- [x] `_call_llm`: extra_body 항상 `{"timeout": live AGENT_TIMEOUT_SEC}` 초기화 + thinking(budget)/output_config(effort) 병합(이전 조건부 세팅 대체).
- [x] ask() client(`OpenAI(timeout=)`)·run 예산(`AGENT_TIMEOUT_SEC*3`) → 정적 import 상수 대신 live `_rts.get_int` 로 전환(콘솔 상향 시 조기컷 gap 봉인).
- [x] feature-0007 litellm_config.yaml `request_timeout: 300` 주석 갱신(값 무변경, body timeout 미전달 경로 fallback 명문화).
- [x] 테스트: reasoning_effort `_xb()` 헬퍼 + body-timeout 상시검증 + 신규 sync 2건 · conversation_answer G8b timeout 병존/누출가드 · feature-0002+0003 전체 pytest RC=0(신규 실패 0).
- [x] §18.8 적대 리뷰(general-purpose 1렌즈 7공격각) → **SHIP**(BLOCKER/MAJOR 0), NIT 2·3(주석 정확성) 반영, Finding 1(콘솔 3600 상향 시 serial worker 점유 확대) by-design 수용 → REV-20260724T054326-timeout-console-sync.
- [x] FUNCTION.md(LLM 타임아웃 콘솔 동기화 항목)·MODIFY.md·REVIEW.md 기록.
- [ ] verify-completion → PR·머지 → 배포(`sudo -E bin/deploy-web.sh`, gateway+worker reconcile) → 라이브 검증(콘솔 AGENT_TIMEOUT_SEC 변경 → gateway 실제 요청 타임아웃 추종 + sonnet 대화 정상 + edge ping 1회).
- worktree `ai/claude/feature-0007-timeout-console-sync`(base main 6c5afe7c).

## TASK-20260724T155534-tool-result-cap-raise — 도구 결과 4000자 하드캡 → 대형 설정 backstop (프로시저 정의 절단 해소, Major §12.3; /_dqa:conversation_audit FR-procedure-analysis-result-truncated)
> 계기(사용자): "assistant 가 추론·내부 도구로 프로시저를 분석할 때 텍스트가 길면 잘려 한 번에 탐색 불가 — 반환 문자열 길이 제한 제거". describe_routine 은 정의를 전문 반환하나 에이전트 루프의 전역 4000자 캡이 재절단해 도구 목적 무력화.

### §1.2 Completion Checklist
- [x] 진단: 근본 = `agent_core.py` 도구 루프 3지점(메인 루프·rederive 루프·저장 copy)의 `tool_result[:4000]` 전역 하드캡. describe_routine(CHG-20260713T140405) 정의 전문 반환을 재절단. rootcause high(코드 file:line 확정).
- [x] 결정(AskUserQuestion 2026-07-24): 3안 중 **전 도구 대형 캡**(도구별 분기 없음·유한 backstop 유지) 선택.
- [x] `shared/config.py` `AGENT_TOOL_RESULT_MAX_CHARS`(env override, 기본 100000, `__all__` 등록).
- [x] `agent_core._cap_tool_result` 헬퍼(초과 시에만 `... (truncated)` note — FR-partial-evidence 계약 보존; `cap<=0`=무제한) + 3지점 치환. 저장 copy 는 PG text(무제한) 이라 overflow 없음.
- [x] 단위테스트 `tests/test_tool_result_cap.py` 6건(기본 캡≥100k·프로시저-크기 전문 통과·초과 절단+note·경계·무제한 sentinel·짧은 결과 무변경).
- [ ] verify-completion → §18.8 적대 패널(backend+qa) → PR·머지 → 배포(영향 서비스 ask-worker/insight-worker/web 재빌드) → 라이브 실측(긴 프로시저 describe_routine 전문 도달).
- worktree `ai/root/feature-0002-agent-core`(base main 3d228632).

## TASK-20260724T085937-sonnet-reasoning-budget-guide (test-only) — adaptive sonnet 죽은 budget 스펙 제거 대응 테스트 갱신 (정본 feature-0003+shared)
- [x] `tests/test_runtime_settings.py` sonnet budget 단정 → haiku 전환 + adaptive dead(override None)·adaptive_models 신규 단정. agent_max_output sonnet 유지.
- [x] 전체 pytest(0002+0003) RC=0. 정본 리뷰=feature-0003 REV-20260724T085937.

### TASK-20260727T105326-worker-attachment-postprocess — 첨부 후처리 소유자를 ask-worker 로 이전 (Major §12.3, 2026-07-27, primary feature-0002 + cross-ref feature-0003)
`/_dqa:conversation_audit` 후속 — FR-brandnew-script-attachment-delivery-gap 이 배포됐는데도 라이브에서 첨부가 생성되지 않는다는 사용자 보고(admin `기능 추가 파일 요청`). 실측(대화 …f1c535ec msg 1389, 배포 후 생성): assistant 는 `attachment-new` 블록을 **정상 emit**(프롬프트 수정 작동)했으나 첨부 0건 + raw 블록 노출. RC=첨부 후처리(materialize+strip)가 web `/api/ask` 동기 핸들러에만 있어, worker 모드 장기 run(11분) 중 연결이 끊기면 후처리 지점에 미도달. 시스템 전체 assistant root 첨부 0건으로 교차확인.

#### 완료 체크리스트
- [x] 재진단: 삼각측량(코드 경로 + PG 메시지 raw 블록 잔존 + MySQL 첨부 0건 + 11분 소요) rootcause_confidence high
- [x] Fix(feature-0002): `_postprocess_attachment_blocks`(worker 소유 materialize+strip) + `_finalize_deferred_terminal` + `run_agent(defer_terminal_status=)` + `_warm_attachment_postprocess_deps` + step 기록 패리티
- [x] Fix(feature-0003 cross-ref): web 후처리 4곳 **증거 기반** 게이팅(`_raw_block_left`) + worker 결과 forwarding + `_update_assistant_message_content` bool 반환
- [x] §18.8 적대 패널 2라운드(backend+concurrency) — BLOCKER 2건(web strip 미게이팅 파괴적 회귀 / KV terminal 이 run_agent 내부라 순서계약 무효)·MAJOR 2건·MINOR 3건·LOW 2건 전부 반영, 재검증에서 CLOSED 확인
- [x] 단위테스트: worker 후처리 12건(순서계약·defer terminal·fail-soft·cap·RBAC) + web 게이팅 계약 — 전체 2384 PASS/0 FAIL
- [ ] verify-completion → commit → PR/deploy(**워커 우선 전체 스코프 배포 필수**) → POST-DEPLOY 라이브 재현
정본 rationale=REVIEW REV-20260727T105326-worker-attachment-postprocess, 변경이력=MODIFY CHG-20260727T105326-worker-attachment-postprocess.

### TASK-20260727T175800-false-truncation-belief — 허위 절단 인식 봉인 + 루틴 정의 offset 이어읽기 (Major §12.3, 2026-07-27)
`/_dqa:conversation_audit "문서 내부 조회 프로시저 탐색"` — 사용자 지목("`describe_routine` 도구 한계로 프로시저 본문이 잘림")을 데이터로 검증한 결과 **절단은 실제로 없었고**(대상 대화 describe_routine 11건 전부 전문 반환·execute_sql 181행 전량 렌더), assistant 가 **없는 도구 한계를 지어내** 분석을 3건으로 축소한 것이 진짜 마찰이었다. RC=CSV 안내문의 "미리보기" 어휘가 SYSTEM_PROMPT 절단 트리거와 충돌 + 완전성 확인 신호 부재(비대칭). 사용자 결정(AskUserQuestion): 캡 무제한화 제외, 허위 절단 봉인 + offset 페이징으로 초대형 정의 전량 도달.

#### 완료 체크리스트
- [x] 진단 삼각측량(코드 file:line + PG core_messages 전사/집계 + 대화 재구성) — rootcause_confidence high, 사용자 지목분은 미발현으로 정직 기각
- [x] A1 CSV 안내문 트리거 어휘 제거(execute_sql·scratch_sql parity)
- [x] A2 절단 없는 결과에 완전성 명시 + "도구 한계 주장 금지" — **행·셀·export 3축 미절단일 때만** 단정(§18.8 BLOCKER: 셀 100자 절단이 행 플래그에 미집계돼 허위 완전성) + 셀 절단 마커 + 0행 대칭 신호
- [x] A3 SYSTEM_PROMPT: 절단 신호 **열린 집합** + 완전성은 **긍정 신호로만**(`침묵 ≠ 완전`, `NO MARKER = COMPLETE` 폐기 — 무통지 절단 13곳을 프롬프트 레벨에서 일괄 무해화) + `CHUNKED ROUTINE DEFINITIONS` 산술 종료조건(본문 위조 방어)
- [x] B `describe_routine(offset)` 문자 이어읽기 + `_routine_chunk_limit`(**0=auto = 캡-여유**로 캡 이하 정의 조각화 회귀 제거 / `room<=0`·캡무제한·음수=윈도잉 비활성 — 구 `max(1_000, cap-2_000)` 바닥값이 작은 캡에서 이어읽기 안내를 잘라 전량 도달 경로를 지우던 실패 봉인) + 권위 산술 머리말 + offset 형식오류 명시·범위초과 클램프
- [x] 단위테스트 `tests/test_false_truncation_belief.py` **23건**(완전성 대칭·트리거 어휘 부재·절단 시 기존 경고 유지·**셀 절단 억제 + stats out-param**·0행 대칭·**scratch parity 3건(실제 핸들러 호출)**·프롬프트 열린집합/부정단정·산술 종료조건·**창 산정 전수 테이블**·캡 이하 미분할·캡 통과 후 offset 안내 생존·**실전형 본문(빈 줄·SQL 펜스) 전량 복원**·**본문 위조 방어**·범위초과 클램프·형식오류 명시·병리적 값 예외 비노출·핸들러 배선·TOOL_DEFINITIONS) + `test_partial_evidence_grounding.py` 계약 반영 2건
- [x] §18.8 적대 3렌즈 패널(security/backend/qa) — BLOCKER 2 / MAJOR 8 / MINOR 7 / NIT 3 중 12건 in-cycle 반영, 4건 정직 이연, 1건 by-design 수용 → REV-20260727T175800-false-truncation-belief
- [x] 컨테이너 `make test` 회귀 **2,428건 중 2,422 PASS / 4 FAIL(전부 pre-existing 환경의존 — `git archive HEAD` 무변경 체크아웃 동일 실패로 확증) / 2 skip** + ruff PASS
- [x] verify-completion PASS → PR #963 머지(main `ef24448c`) → **배포 완료**(`make deploy-web` 전체 스코프: web-a/web-b 롤링 + ask/insight-worker 재빌드 + gateway reconcile, soak 90s 통과, 4서비스 GIT_COMMIT=ef24448c, `/healthz` ok) → 배포본 런타임 실측 9항 확인(auto 창 99,000 · 초대형 머리말 · offset 안내 캡 생존 · 캡 이하 미분할 · 셀 절단 stats 분리 · 프롬프트 신규 계약 4항)
- [x] **라이브 대화 실측 완료(2026-07-28)** — 재현 대화 `20260728012534-a56ec98e`(product 117 / `claude-haiku-4`, 원 대화 동일 조건) 3 turn: 오귀속 시그니처 **0건**(대량 완전 결과 291행 카운트 + 200행 렌더 turn 포함) · 셀 절단 시 완전성 억제 + 마커 실증(20행 완전 + 13셀 절단) · 진짜 절단(루틴 482건 목록)엔 기존 경고 유지 · 구 트리거 어휘 0건/신규 안내문 9건 · 원 불만 대상 `MSP_SELECT_COMMENT_LIST` 2,386자 전문 수신(`END` 완결). corroboration distinct_conv 1→0(분모 23 assistant msg/4 conv 로 작음 — 판정 근거는 직접 재현+기전). offset 페이징은 실데이터 미도달(정의 35건 max 7,732자 « 창 99,000) → 배포본 직접 호출로 검증. 원장 `fixed:deployed:verified` 전이.
- worktree `ai/root/feature-0002-agent-core`(base main cdf4acf1) → 후속 원장 전이 cycle `ai/claude-corp/feature-0002-agent-core`(base main ef24448c).
정본 rationale=REVIEW REV-20260727T175800-false-truncation-belief, 변경이력=MODIFY CHG-20260727T175800-false-truncation-belief.

### TASK-20260728T114459-false-absence-catalog-scope — 0행→허위 부재 봉인: 루틴 열거 도구 + 카탈로그 스코프 인지 (Major §12.3, 2026-07-28)
FR-false-truncation-belief 라이브 실측 중 관측된 별개 축을 사용자 지시로 근본 규명·수정. 모델이 `masangsoftweb` 에 "프로시저 0개" 를 단정했으나 실제 **482건**. 원인은 "모델이 쿼리를 잘못 씀" 이 아니라 **구조적으로 항상 0행인 쿼리로 몰리는 경로**였다 — 루틴 열거 도구 부재(RC-A) + MSSQL 정본 경로 차단(RC-B) + 메타뷰 카탈로그 스코프 grounding 공백(RC-C) + 0행 스코프 진단 부재(RC-D) + 0행→부재 단정(RC-E). 사용자 범위 결정: **RC-B 포함**(보안 경계 재검토).

#### 완료 체크리스트
- [x] 근본원인 5층 규명 + ground truth 대조(`WebProductDatabases` pin=`_INDY_STATISTIC`, 루틴 472+10)
- [x] 선행 봉인 계보 확인 — `FR-mssql-crossdb-structured-discovery` 의 **누락된 형제**임을 확정
- [x] A: `search_routines` 신설(cross-DB sweep·본문 검색·CLR/확장 타입 포함·keyword 선택·실패/포화 명시 고지)
- [x] B: `sys` 전면차단 → DB 스코프 카탈로그 뷰 화이트리스트 21종(서버 스코프·`synonyms`·`guest`/`db_*`·메타데이터 함수는 계속 차단)
- [x] C: MSSQL 프롬프트 `CATALOG VIEWS ARE PER-DATABASE` + `sys` 경계 문구 SSOT 생성
- [x] D: `_catalog_scope_hint` — AST 기반·행수 무관·3-part 제외·진단 시 완전성 억제
- [x] E: 0행 문구 부재-부정 우선 + `ZERO ROWS IS NOT ABSENCE` 를 메타데이터 맥락으로 한정(과교정 방지)
- [x] §18.8 적대 3렌즈 패널 **1라운드**: BLOCKER 3 / MAJOR 9 / MINOR 8 → 전건 반영(TVF piggyback·agent_memory 누출·COUNT 형태 미개입·pin DB AttributeError 등)
- [x] 신규 `tests/test_false_absence_catalog_scope.py` **34건**(패널이 뚫은 경로 전부 회귀 가드) + 기존 보안 테스트 강화
- [x] §18.8 **2라운드** security 재검증(1R 봉인 불완전 = 별칭 그림자 재적발 → 재수정 후 실증 CLOSED) → verify-completion PASS → PR #991 머지(main `21b67ade`) → 전체 스코프 배포(soak 통과) → **라이브 재실측 완료**: 동일 질문에 "총 421개" + `MSP_SELECT_BOARD_CONTENT` 본문 제시, 오귀속·부재 단정 0건, `search_routines` 실사용, 연결 장애 시 실패 고지 실전 발동
- worktree `ai/claude-corp/feature-0002-agent-core`.
정본 rationale=REVIEW REV-20260728T114459-false-absence-catalog-scope, 변경이력=MODIFY CHG-20260728T114459-false-absence-catalog-scope.

## TASK-20260728T124500-llm-usage-target-scope — llm_usage 데이터소스 차원 컬럼 추가 (사용 기록 귀속 근본 해소, Major §12.3)

**요청 (사용자, 2026-07-28)**: 직전 cycle(usage-records-system)이 후속 과제로 남긴
"`llm_usage` 에 데이터소스 차원 컬럼 추가를 통한 근본 해소" 를 진행한다.

### 문제

0032 의 `target`(schema / schema.table / 노드 FQN)에는 **데이터소스 차원이 없다**. 관리 콘솔
'사용 기록' 드릴다운이 시스템 사용분의 대상 화면으로 이동할 때 어느 데이터소스인지 알아야 하는데,
직전 cycle 은 `table_descriptions` ∪ `routine_objects` ∪ `rag_objects` union 으로 **역해소**했다.
라이브 실측 8,399 distinct target 중 상당수가 dev/qa 동명 스키마 때문에 후보 2+ 로 **구조적 모호**
(추측 금지 정책상 "화면까지만 이동" 저하), 게다가 역해소는 조회 시점 메타데이터 적재 상태에
의존해 시간이 지나면 답이 달라진다. **기록 시점에 아는 값을 그때 저장**하는 것이 정본 해법.

### 2.1 Implementation Plan

- alembic `0047_llm_usage_target_scope` — `target_scope VARCHAR(96)` additive nullable
  (`rag_objects.scope_key` 와 동일 폭·의미 공간). 부트스트랩 DDL parity.
- `modules/llm.py` — `_record_llm_usage(target_scope=...)` + **명시 인자 → ContextVar 폴백**.
  INSERT 폴백을 4단 **사다리**로 재정리(중첩 try 3중 → 후보 리스트 루프).
- `llm_{schema,table}_insight` · `llm_node_analysis` · `llm_product_classify` ·
  `llm_cluster_label` 에 `scope_key` kwarg 추가(프롬프트 payload 는 **무변경** — 모델 입력·
  캐시 키에 영향 0).
- **병렬 스레드 3경로 명시 전달** — `node_analysis._run_llm`(w["scope_key"]) ·
  `semantic_cluster` 직렬/병렬(`datasource_key`) · `product_classify`(`scope`).
  ContextVar 는 스레드로 전파되지 않아 여기서만 ambient 가 실패한다.
- `routers/admin_usage.py` — **2단 폴백**: 기록값 우선, 없으면(legacy) 종전 역해소.
  fold 키에 scope 포함(같은 target·다른 데이터소스 = 별 행). 컬럼 부재 시 자가치유 재조회.

**완료 판정 기준**: ① 신규 insight/cluster/product 호출이 `target_scope` 를 채운다
② 같은 `schema.table` 이 데이터소스별로 분리된 행으로 보인다 ③ legacy 행은 종전 동작 유지
④ 마이그 미적용·구 이미지에서도 계측·조회가 죽지 않는다(양방향 자가치유) ⑤ 회귀 0.

**위험도: Major** — 마이그레이션 동반(단 expand-only additive nullable, 롤백 안전) + 계측
chokepoint 변경. 파괴적 변경·인증 변경·RBAC 변경 없음.

### 진행

- [x] 마이그 0047 + 부트스트랩 DDL parity + `migrate-lint` expand-safe PASS
- [x] `_record_llm_usage` target_scope(명시→ContextVar) + 4단 사다리
- [x] llm_* 5종 pass-through + 병렬 3경로 명시 전달
- [x] 웹 2단 폴백(기록값 우선 / legacy 역해소) + 컬럼 부재 자가치유
- [x] 단위 2,719 PASS · ruff clean (테스트 더블 arity 7건·인덱스 단정 4건 정합)
- [x] POST-DEPLOY — 마이그 적용 확인 + 신규 행 target_scope 채움 실증 + 콘솔 이동 정확도
      (배포본 `754263ab`: alembic head 0047 · 컬럼 생성 · 명시/ContextVar 양 경로 기록 · API
      `scope_source="recorded"` · 같은 target 의 데이터소스별 행 분리 라이브 확증 —
      REV/CHG-20260728T124500-llm-usage-target-scope-postverify)
### TASK-20260728T133431-alias-shadowed-function-namespace — 별칭 그림자 함수 우회 봉인 (Major §12.3, 2026-07-28)
FR-false-absence 패널이 pre-existing 으로 분리 기록한 항목을 사용자 지시로 후속 수정. `X.Y.f()` 의 자격 함수호출 ↔ UDT 메서드 문법 동일성 때문에 DB 명을 테이블 별칭으로 선언하면 catalog allowlist 가 무력화됐다.

#### 완료 체크리스트
- [x] 근본원인 규명 — 같은 Dot 워커가 두 의미를 겸용해 구조적으로 구별 불가
- [x] 1차 시도(이름/토큰 목록) 실패 확인 — 공격자 0비용 + 정상 29건 과차단·오보
- [x] 2차 시도(caller "아는 DB" 대조) 실패 확인 — 논리 반전(`_bad ⊆ allow_set`)으로 미허용 DB 전부 통과
- [x] 최종: table-source 면제 금지 + 체인 2토큰 상한 + 전 토큰 보호 + 미지 노드 fail-closed + 열거 oracle 차단 + 오보 제거
- [x] re-gate(7차) UDT 계약 유지(CLR 메서드명은 열거 원리 불가) · re-gate(3차) 4-part 계약 유지
- [x] §18.8 적대 security 2라운드 — 1R BLOCKER 2 / MAJOR 3 / MINOR 3, 2R 이 1차·2차 시도의 실패를 각각 재적발
- [x] 회귀 가드를 **유효 T-SQL exploit 형상**으로 교체(종전 2회는 실패 변종을 assert 해 오인증)
- [x] 컨테이너 `make test` 2,725건 중 2,719 PASS / 4 FAIL(전부 pre-existing 환경 의존) / 2 skip · ruff PASS
- [ ] verify-completion → PR·머지 → 배포 → 배포본 런타임 경계 실측
- [x] **cyvol**: 그래프 sync cypher 호출량 귀속 실측(전량 1회 = 158,544 회 / PG 867초, wall 의 75%)
- [x] **cyvol W1**: anchor 캐시를 sync_table/column/routine 으로 확장 — 속성 포함 마크로 단계 간 속성 계층 보존
- [x] **cyvol W2**: ROUTINE_USES 전량 DELETE+재MERGE 를 refs 서명 비교로 조건부화(선조회 cypher 1회/3.2ms)
- [x] **cyvol**: 회귀 테스트 11건 + 역검증 4축(되돌려 실패 확인)
- [x] **cyvol**: §18.8 적대 패널 2렌즈 — 결함 8건 흡수(MAJOR-1 flip-flop · MAJOR-2 무음 행소실 · B3 재조정 상실 · M3 부분엣지 고착 · M1 교차 feature 회귀 · M2 무음 · MINOR-1/2)
- [x] **cyvol**: QA 패널 변이 28중 17 생존 → harness 를 sync_graph end-to-end 로 교체, 최종 31건 · 역검증 16종 생존 0
- [ ] **cyvol**: 머지 → 배포 → 전량 sync 전후 실측
- [x] **infdetail**: 다음 병목 후보 3종 측정 — red-team(95~98% LLM=대상아님) · 큐대기(배포실패 창) · PG(40분 8.0초=병목아님)
- [x] **infdetail**: inference 142.9s 중 LLM 109.9s / **33.0s(23%) 미귀속** 확인 → 하위 분해 부재가 원인
- [x] **infdetail**: `duration_breakdown.inference_detail`(llm/tool/tool_top/other_ms) + perf-snapshot §3b-2·§3b-3 + 테스트 7건·역검증 5종
- [ ] **infdetail**: 패널 → 머지 → 배포 → 수집된 other_ms 로 33초 정체 규명 후 개선 착수
- [x] **잔여 확정(2026-07-28 라이브 실증)**: QA SQL Server 2017 프로브로 스칼라 위치 모호성이 **착취 불가**임을 확인(별칭 우선 해석, 오류 문구 DB 존재 불변) → 열거 oracle 부재도 확정되어 오류 원문 은폐를 **철회**. CHG-20260728T150510.
정본 rationale=REVIEW REV-20260728T133431-alias-shadowed-function-namespace, 변경이력=MODIFY CHG-20260728T133431-alias-shadowed-function-namespace.

## TASK-20260728T175400-cyvol-scope-prefetch-fix — cyvol 차수 선조회 cypher 조립 결함 수정 (Minor §12.3, 최적화 복구 · feature-0030)

### 배경 (라이브 발견)
routine-column-edges POST-DEPLOY 의 `bin/routine-backfill.sh` 리포트에
`routine_prefetch: SyntaxError syntax error at or near ":"` 6건. cyvol 선조회가 scope 술어를
노드 패턴 직후에 고정 보간해, 관계 패턴이 있는 **차수 쿼리**에서 `WHERE` 가 패턴 중간에 들어갔다.
`scope_key is None` 경로만 유효했으므로 **모든 per-datasource sync** 가 도입 이래 항상 실패.

정합성은 fail-safe(빈 차수 dict → 전량 재작성 = 최적화 이전 동작)였고, 손실은 ① 스코프 sync 의
cyvol W2 감축(실측 전체의 32%) ② B3 재조정 안전망의 차수 판정 ③ 매 스코프 sync 1회 불필요한
`rollback()` + `anchor_cache_reset()`.

### 진행
- [x] 결함 재현 테스트 3건 선작성 → **수정 전 2 FAIL** 확인(기존 32건은 통과 = 기존 스위트 사각 실증)
- [x] 하네스 보강 `_assert_cypher_parses` — mock 이 PG 대신 malformed cypher 거부(관측 장비 수정)
- [x] `metadata_graph.py` scope 술어를 쿼리별로 **패턴 뒤**에 조립 + 근거 주석
- [x] 라이브 PG/AGE ground-truth — 수정 전 형태 `syntax error at or near ":"` 재현 / 수정 후 행 반환
- [x] 회귀 — 대상 3파일 86 PASS · feature-0002 전체 스위트 main 기준선 대조 실패 차집합 **양방향 0**
- [x] 문서 — CHG/REV/Run fragment/FUNCTION 갱신
- [ ] POST-DEPLOY: 워커 이미지 재배포 → 스코프 sync 리포트에서 `routine_prefetch` 오류 소실 재확인

### 범위 외 (기록만, §8.1)
같은 backfill 리포트의 `rag_table`/`relationship` step `Entity failed to be updated: 3` ·
`DeadlockDetected` 는 별개 클래스 — 본 cycle 에서 다루지 않는다.

### 정본
rationale=REVIEW `REV-20260728T175400-cyvol-scope-prefetch-fix` ·
변경이력=MODIFY `CHG-20260728T175400-cyvol-scope-prefetch-fix` ·
Run=`docs/test-runs.d/20260728T175400-cyvol-scope-prefetch-fix.md` ·
도입 cycle=`CHG-20260728T163000-graph-cypher-volume`.

## TASK-20260728T182000-cyvol-scope-prefetch-postdeploy — cyvol scope-prefetch 수정 POST-DEPLOY 재확인 (종결)

`TASK-20260728T175400-cyvol-scope-prefetch-fix` 의 잔여 항목("배포 → 스코프 sync 오류 소실 재확인")
완결. 코드·자산 변경 0.

### 진행
- [x] 배포 — PR #1022 → main `44fe939d`, 전체 롤아웃(web 롤링 + 워커 + gateway), soak 통과.
      web-a/web-b/ask-worker/insight-worker 전부 `44fe939d`
- [x] 오류 소실 — 스코프 backfill 리포트 `errors=6` → **`errors: []`** · 워커 로그 해당 문자열 **0회**
- [x] 데이터 무손상 — mysql-local scope `ROUTINE_USES` 601 / `ref_columns` 370
- [x] 멱등 — 스코프 backfill 연속 2회 `with_cols` 257 불변
- [x] 커버리지 실측(귀속 분리 표기) — cols 5,807 → 7,377 · AGE `ref_columns` 2,725 → 9,269 · scope 5 → 8
- [x] 미해결 관측 기록 — `introspect_and_store` 예외 삼킴에 의한 **부분 성공 무음** 후보(§8.1, 미수정)

### 정본
rationale=REVIEW `REV-20260728T182000-cyvol-scope-prefetch-postdeploy` ·
변경이력=MODIFY `CHG-20260728T182000-cyvol-scope-prefetch-postdeploy` ·
Run=`docs/test-runs.d/20260728T182000-cyvol-scope-prefetch-postdeploy.md`.

## TASK-20260729T110000-dataplane-conn-liveness — 데이터플레인 연결 유휴/타임아웃 사망 재연결 봉인

`/_dqa:conversation_audit` 진단(friction-id `FR-dataplane-conn-stale-no-reconnect`). 사용자 보고:
"쿼리 리뷰 : WEB_QA — DB와 연결하지 못하는 이슈". 대화 `20260729013000-a8b43197`(제품 117) ·
선행 관측 `20260728031510-16927f9b`. 코드 거주 = 본 feature.

run 시작에 수립한 데이터플레인 연결이 그 run 의 모든 tool 호출에 재사용되는데 liveness 검사도
재연결도 없어, (a) 첫 tool 까지 LLM 추론 유휴(실측 232초) 또는 (b) 쿼리 타임아웃으로 세션이
죽으면 남은 tool 전부가 드라이버 문구로 실패하고 요청이 통째로 무너졌다.

### 진행
- [x] 근본 확정 — 코드(run 1회 수립·재사용) + 라이브 실험(대상 datasource 는 60~120초 유휴에
      절단, 대조 datasource 는 생존; 사망 순간 `DBPROCESS is dead` → 이후 `Not connected…`) +
      전사(두 대화의 오류 문자열이 그 순서 그대로) 삼각측량
- [x] 거짓양성 기각 — datasource_health 는 healthy(백그라운드 probe 는 매번 새 연결) · 동시각
      타 제품 대화 정상 동작 · TCP 도달 정상 → 인프라 장애·권한 문제 아님
- [x] 봉인 — 사용 직전 liveness ping + **같은 좌표** 재연결(`_ensure_live_conn`), 라우터 캐시
      갱신, 단일 경로 소유권 holder(`_DataplaneConn`), 끊김 관측 시 임계 무시 ping(`_mark_conn_suspect`)
- [x] 실패 문장 자체는 재시도 안 함 — 타임아웃으로 죽은 무거운 쿼리 재실행 방지(부하 2배 회피)
- [x] 정직 문구 — 끊김 오류를 "쿼리를 좁혀라" 가 아니라 "연결이 끊겼다·그대로 재시도" 로.
      부하게이트 추정 실패도 원인을 liveness 로 구분
- [x] `search_tables` MSSQL cross-DB per-DB 실패 삼킴 제거(형제 `search_routines` 와 대칭) —
      사고 당시 아무것도 조회 못 한 상태를 "검색 결과가 없습니다" 로 위장하던 경로
- [x] 테스트 21건 신규(`test_dataplane_conn_liveness.py`) · 컨테이너 전체 스위트 신규 실패 0
      (잔여 15건은 main 과 동일한 환경성 baseline)
- [ ] 배포 후 라이브 실측 — 동일 재현(대형 첨부 리뷰로 수 분 추론 → 첫 도구 성공) + 원장 재측정

### 정본
rationale=REVIEW `REV-20260729T110000-dataplane-conn-liveness` ·
변경이력=MODIFY `CHG-20260729T110000-dataplane-conn-liveness` ·
원장=`docs/improvements/conversation-audit/FRICTION_LEDGER.md`.

## TASK-20260729T160000-test-live-pg-isolation — `make test` 가 라이브 Postgres 를 실제로 읽던 근본 원인 차단 (기준선 13건 실패 해소)

사용자 보고: "다른 AI 작업자가 『make test 결과 — main 기준선과 동일한 13건 실패』 같은 이슈를
지속적으로 확인하고 있다. 근본 원인을 수정하라." 실제로 여러 cycle 의 TASK/REVIEW/MODIFY 가
"잔여 N건은 main 과 동일한 환경성 baseline" 을 서로 다른 N(4·8·13·15)으로 반복 기록해 왔고,
그 대조 작업 자체가 매 cycle 의 고정 비용이었다.

### 근본 원인 (한 줄)

테스트 컨테이너가 **운영 `.env` 를 통째로 상속**해 라우팅 스위치가 `postgres` 인 채 돌았고,
`--no-deps` 는 의존 서비스를 기동만 안 할 뿐 compose 네트워크를 끊지 않아 **이미 떠 있는
pgbouncer/replica 에 그대로 도달**했다. MySQL 은 `DB_PORT=1` 로 막혀 있었으나 PG 는 열려 있었다.

그 결과 세 가지가 동시에 일어났다:
1. 테스트가 주입한 fake connection 이 **무시되고** 코드가 라이브 PG 를 실제 조회 → 라이브에는
   테스트가 꾸민 행이 없어 0행 → 빈 섹션 → attachment 계열 **13건 실패**.
2. 반대로 *라이브 PG 가 살아 있을 때만* 통과하던 테스트 2건이 존재 → 실패 집합이 인프라 기동
   상태·cutover 설정에 따라 요동 → 세션마다 다른 N.
3. `PATCH /api/conversations/{cid}/product` 테스트가 **라이브 Postgres 에 UPDATE 를 실행**.

### 진행
- [x] 재현·확정 — main 에서 13건 재현(3파일: `test_attach_inline_honesty` 4 ·
      `test_attachment_idor` 4 · `test_attachment_user_version_context` 5). 단독 실행에서도
      동일 실패 → 순서-의존 flake 가 아님을 먼저 배제. traceback 이 `_pg_connect_ro` 까지
      내려가 라이브 PG 실접속을 직접 확인
- [x] 대조 실험 — 라우팅만 mysql 로 돌리면 13건 소멸 / PG 포트만 막으면 13건 소멸 + 라이브 PG
      의존 2건 노출(`test_routine_dbanalysis` · `test_item11_batch8_update_conv_product`).
      두 실험이 같은 원인을 양방향으로 지목
- [x] 하네스 격리 완결 — `Makefile` `TEST_ISOLATION_ENV` 에 PG 포트 차단 + 라우팅 중립화 추가.
      이전 주석의 "PG 는 의도적으로 두지 않는다(일부 테스트가 라이브 PG 읽기에 의존)" 유보를
      그 의존 2건과 함께 해소
- [x] 하네스 밖에서도 성립 — 저장소 루트 `conftest.py` 신설(2중 방어). 로컬 `pytest` 직접 실행도
      결정적. 라이브 통합 점검은 `AGENT_TEST_ALLOW_LIVE_BACKENDS=1` 로 opt-in
- [x] **프로덕션 결함 동반 수정** — 위 2건 중 `test_routine_dbanalysis` 실패는 테스트 문제가
      아니라 코드 결함이었다: `_ro_conn`/`_rw_conn` 이 접속 실패를 저하(None)가 아니라 예외로
      전파해, 호출부 20여 곳의 `if c is None: return <빈 결과>` 계약과 자기 docstring("실패 시
      [] 로 저하")을 동시에 위반. PG 순단 시 그래프 검색·이웃조회·스키마 시드가 500 이 된다.
      `shared/db.py` 에 정본 헬퍼를 두고 8개 모듈의 동일 복제 11곳을 위임으로 단일화
- [x] 검증 — `make test` 신규 실패 0. 전체 **2976 passed · 2 skipped · 0 failed** (2회 연속 동일).
      이전 기준선 13건이 0건으로

### 정본
rationale=REVIEW `REV-20260729T160000-test-live-pg-isolation` ·
변경이력=MODIFY `CHG-20260729T160000-test-live-pg-isolation` ·
Run 기록=`docs/test-runs.d/20260729T160000-test-live-pg-isolation.md`.

### 커밋 전 재검토 (사용자 요청)
- [x] **초안 회귀 1건 시정** — 쓰기 경로(`_rw_conn`)까지 저하시킨 것이 `sync_graph` 실패를
      cron exit 0(성공)으로 위장. RW 는 접속 실패 전파(기존 동작)로 원복, RO 만 저하.
      상세 = REVIEW `커밋 전 자체 재검토에서 잡은 회귀`
- [x] **루트 conftest 단독 효력 실증** — Makefile 격리를 뺀 컨테이너(`AGENT_KB_PG_PORT=5432` ·
      라우팅 `postgres` 확인)에서 문제 5파일 49 passed → 2중 방어 실효 확인
- [x] 재검증 — `make test` exit 0 · 신규 실패 0

### POST-DEPLOY 라이브 실증 (TASK-20260729T183000-test-live-pg-isolation-postdeploy)
배포 `c16e3a84` (web-a·web-b·insight-worker·ask-worker 전량, soak 통과) 후 `repo-web-a-1` 에서 실측:
- [x] 헬퍼 배포 확인 — `_pg_conn_pair_{ro,rw}` 존재 · `_pg_available()=True`
- [x] 정상 경로 — RO 연결 성공(`owned=True`) · `SELECT 1` 응답 · 그래프 읽기 3건 반환
- [x] **RO 저하 계약** — `AGENT_KB_PG_PORT{,_RO}=1` 프로세스로 재현 시 `(None, False)` 반환 +
      `pg ro connect failed — 저하(None) 로 계속: …Connection refused` warning 1줄 (silent 아님)
- [x] **RW 전파 계약** — 같은 조건에서 `OperationalError` 전파 확인(저하 안 함) → `sync_graph` 가
      실패를 `ok=True`/exit 0 으로 위장하는 경로 없음
- 검증 방법 주의: `os.environ` 변경 + `importlib.reload` 는 무효(`shared.config` 가 import 시점
      상수를 굳힘) — **프로세스 env**(`docker exec -e`)로 재현해야 한다. 첫 시도가 이 함정에 걸렸다.

## TASK-20260730T160000-ask-redeploy-handoff — 재배포가 진행 중 답변을 삼키던 dead-air 봉인

출처: `/_dqa:conversation_audit` (사용자 명시 호출) — 그룹 대화 "레거시 호환성을 고려한 실제 DB
기반 쿼리 리뷰"(`20260729074446-b5f40d99`)에서 "요청이 도중에 중단"된 원인 진단.
마찰 원장 `docs/improvements/conversation-audit/FRICTION_LEDGER.md` `FR-ask-orphan-redeploy-dead-air`.

- [x] 진단 — 4중 삼각측량(`ask_jobs` + `steps` + `core_messages`/`messages` + 컨테이너
      타임스탬프). job 483 은 15:38 에 답변 초안까지 만들고 red-team 자가검증 중이던 15:41:32 에
      배포(`--force-recreate ask-worker`)로 죽었고, 회수가 **15:49:18** 에야 일어났다(dead-air
      약 8분). 재실행은 사용자 메시지를 한 번 더 저장한 뒤 LLM timeout 으로 최종 error —
      사용자는 14분을 기다려 중복 메시지와 오류만 받았다.
- [x] 근본 확정 — `_worker_id()` 가 `gethostname()`(=컨테이너 id) 기반이라 **재생성 후
      `reclaim_worker_jobs_on_boot` 의 자기-이름 일치가 항상 0행**. 배포는 언제나 재생성이므로
      "배포로 죽은 job 은 자가회수 대상이 될 수 없는" 구조. 고아는 전역 stale 창(런타임 실측
      450s)을 통째로 대기.
- [x] corroboration(60일, PG 정본) — 고아 재큐 **8건 / 8대화**(전체 482 job·209 대화), 생성→
      재시작 dead-air **142~1,649초**, 3건 최종 error. 중복 사용자 메시지 **9건 / 9대화**.
      → structural.
- [x] 거짓양성 기각 — 같은 대화 07-29 17:38~17:39 사용자 3건 무응답은 **그룹 @assistant 멘션
      게이트**(의도된 동작, `conversations.py` `group_requires_mention`) → 결함 아님.
      `FR-dataplane-conn-stale-no-reconnect` 재발도 아님(연결 절단 시그니처 부재).
- [x] 봉인 A — 종료 시 lease 명시 반납(`release_worker_jobs_on_shutdown` + drain 종료 경로 +
      SIGTERM 타이머). 새 인스턴스가 ~idle_poll(0.5s) 안에 재claim.
- [x] 봉인 B — worker identity 를 재생성 불변 role(`AGENT_WORKER_ROLE` > `AGENT_SESSION` >
      hostname, feature-0025 T0c 선례)로 분리 + 같은 role 의 죽은 이전 인스턴스를 짧은 창
      (`AGENT_ASK_WORKER_ROLE_STALE_SEC`, 기본 60s)으로 회수. SIGKILL/OOM backstop.
- [x] 봉인 C — 재시도(attempts>1)에서만 job 수명(`created_at`) 이후 동일 사용자 메시지 존재를
      확인해 중복 저장 억제. 무조건 skip 이 아니라 **근거 기반** — 1차 시도가 저장 전에 죽었으면
      요청문이 유실되므로.
- [x] 검증 — 신규 `tests/test_ask_redeploy_handoff.py` **17 PASS**, 전체 회귀 `make test`
      **EXIT=0 · 신규 실패 0**, ruff clean.
- [ ] 라이브 실측(배포 후) — 다음 audit 에서 corroboration 재측정: `attempts>1` 재큐의
      dead-air 중앙값 감소 + 연속 동일 user 메시지 distinct_conv 감소.

### 범위 밖(인지)
- 전역 `AGENT_ASK_WORKER_STALE_SEC`(450s)는 **불변** — cross-role false-positive 회수 방지용
  보수 창. role-scoped 짧은 창이 그 역할을 대체하지 않고 보완한다.
- 재시도가 1차 시도의 답변 초안·red-team 라운드를 재사용하지는 않는다(전량 재실행). 부분 산출
  이월은 별 cycle 판단 대상.
- `insight-worker` 도 같은 `gethostname()` 기반 식별을 쓰나 소비자·복구 정책이 다르다(배경
  스캔은 다음 cadence 재시도) — 이번 batch 응집 범위 밖.

### 정본
rationale=REVIEW `REV-20260730T160000-ask-redeploy-handoff` ·
변경이력=MODIFY `CHG-20260730T160000-ask-redeploy-handoff`.

### Requested Scope (요청 범위 자기-열거) — TASK-20260730T160000-ask-redeploy-handoff

원 요청: `/_dqa:conversation_audit "레거시 호환성을 고려한 실제 DB 기반 쿼리 리뷰" — 요청이
도중에 중단된 것으로 추측. 원인 파악 + 해소 방안 + 예방작업까지`.

- [x] `원인 파악` — 산출물: 본 TASK 진단 섹션 + 원장 `FR-ask-orphan-redeploy-dead-air` ·
      배선 확인: 라이브 PG(RO replica) 4중 삼각측량 — `ask_jobs`(job 483 attempts=2/lease_epoch=3),
      `steps`(attempt-1 run `…b733e9fe` 15:36:42~15:41:32), `core_messages`/`messages`(중복 user
      행 6290/6299 · 미러 1737/1740), 컨테이너 타임스탬프(ask-worker 재생성 15:40:29).
- [x] `해소 방안` — 산출물: `CHG-20260730T160000-ask-redeploy-handoff` 봉인 A/B/C ·
      배선 확인: 신규 23 PASS + 전체 회귀 `make test` EXIT=0(2회) + codex 적대 리뷰 2라운드 P1 0건.
- [x] `예방작업(재발 봉인)` — 산출물: 코드 권위 계약 3종(종료 시 lease 반납 · role 기반 회수 ·
      재시도 중복 저장 억제) + 회귀 테스트로 고정 + `FUNCTION.md` 계약 문서화 ·
      배선 확인: `AGENT_ASK_WORKER_DRAIN_SEC`/`ROLE_STALE_SEC` knob 및 cap 회계 불변식 테스트.
- [ ] `라이브 실측(배포 후)` — 산출물: 다음 audit 의 corroboration 재측정 ·
      배선 확인: **미수행**(배포 후에만 가능). 코드/테스트는 "인계 계약이 동작함" 까지만 증명하고,
      "실제 대화에서 dead-air 소멸" 은 배포 후 실측분으로 분리 표기한다.

**주장 affordance 실측 (G3)**: 본 변경은 사용자 표면에 새 affordance 를 주장하지 않는다
(워커 내부 회수 계약 + 중복 저장 억제). → `해당 없음`.

## TASK-20260730T172000-dedup-param-cast — POST-DEPLOY 실측: 중복 억제(봉인 C)가 무력이었다

선행 `TASK-20260730T160000-ask-redeploy-handoff` 의 배포 후 라이브 검증에서 잡힌 결함.
**미검증을 완료로 보고하지 않기 위해 결함과 경위를 그대로 남긴다.**

- [x] 관측 — 배포본(`76dbfedd`)에서 job 485 가 실제로 requeue·재실행됐고(전역 sweeper 16:59:44
      → 신규 워커 17:00:08 claim → 17:02:07 done, **사용자 원 요청 답변 완료**), 그런데
      `core_messages` 에 사용자 메시지가 **다시 중복 저장**됐다(6301 ↔ 6322, md5 동일·sender 동일).
- [x] 근본 — 표시 store 판정 SQL 의 `%(mirror_sender)s IS NULL` 이 **타입 컨텍스트가 없어**
      PostgreSQL 이 `could not determine data type of parameter $4` 로 **쿼리 자체를 거부**.
      `_read_runtime_pg` 가 예외를 흡수해 `None` → 헬퍼가 `{}` → 호출부가 fail-open 으로 저장.
      즉 core 판정까지 함께 죽어 봉인 C 가 통째로 inert 였다. 배포본 컨테이너에서 직접 재현
      (`runtime_read_pg_fallback: method=user_message_persisted_since error=could not determine…`).
- [x] 왜 테스트가 못 잡았나 — 신규 스위트는 FakeConn 기반이라 **실 SQL 을 실행하지 않는다**.
      선행 cycle 의 적대 리뷰가 P2 로 정확히 지적("실 PG 미사용")했고 그때는 근거와 함께
      수용했는데, 첫 라이브 노출에서 바로 발현했다.
- [x] 수정 — `%(mirror_sender)s::text` · `%(sender_account_id)s::bigint` 캐스트. 캐스트 존재를
      문자열로 고정하는 회귀 테스트 추가(FakeConn 층에서 가능한 유일한 자동 방어선).
- [x] 검증 — **실 PostgreSQL 직접 실행 5케이스**(배포본 워커 컨테이너 → RO 연결):
      core hit=True / core 다른 sender=False / disp 그룹 hit=True / disp 그룹 다른 sender=False /
      disp 1:1 NULL hit=True. + 전체 회귀 `make test` EXIT=0 · ruff clean.
- [ ] 라이브 실측(재배포 후) — 다음 재시도에서 사용자 메시지 중복이 실제로 사라지는지.

### Requested Scope (요청 범위 자기-열거) — TASK-20260730T172000-dedup-param-cast
- [x] `봉인 C 무력화 원인 규명` — 산출물: 본 섹션 · 배선 확인: 배포본 컨테이너 재현 로그.
- [x] `수정` — 산출물: `CHG-20260730T172000-dedup-param-cast` · 배선 확인: 실 PG 5케이스 + 회귀 EXIT=0.
- [ ] `라이브 실측` — **미수행**(다음 재시도 발생 시). 정직 분리 표기.

**주장 affordance 실측 (G3)**: 사용자 표면 affordance 주장 없음 → `해당 없음`.

### 정본
rationale=REVIEW `REV-20260730T172000-dedup-param-cast` ·
변경이력=MODIFY `CHG-20260730T172000-dedup-param-cast`.
- [x] **initpro**: feature-0031 계측이 "inference 미귀속 33초" 가설을 **반증**(other_ms=235ms/1.6%, 33초는 red-team)
- [x] **initpro**: 새 블라인드스팟 실측 — init_ms 4,921ms 중 설명분 750ms, **4,171ms(85%) 미귀속**
- [x] **initpro**: 프롤로그 3구간(mem_setup·ds_resolve·dataplane_connect) + 잔차 `init_other_ms` + perf-snapshot §3b-0
- [x] **initpro**: 테스트 10건 + 역검증 5종(롤업 이중계상·클램프 플래그·빌더 우회·재선언·폴백 계측) 생존 0
- [ ] **initpro**: 적대 패널 → 머지 → 배포 → 수집된 init_other_ms 로 개선 대상 확정
- [x] **qembed-vis**: feature-0034 계측이 init 의 87%=query_embed 를 지목 → 추적 결과 **타임아웃 후 무음 강등**(20,587ms ≈ 타임아웃 20s)
- [x] **qembed-vis**: warm 실측 p50 206ms / p90 215ms / max 429ms(47 표본) — 두 체제만 존재, 중간 없음
- [x] **qembed-vis**: `query_embed_ok`(수치 1/0) 신설 + 잔차 leaf 제외 + 시도와 동일 게이트, perf-snapshot §3b-1
- [x] **qembed-vis**: 타임아웃 20→5s(warm p90 23배 여유) — 남는 불확실성(5~20s 체제 미관측) 명시
- [x] **qembed-vis**: 테스트 6건 + 역검증 4종(bool 화·잔차 leaf 포함·게이트 제거·타임아웃 원복) 생존 0
- [ ] **qembed-vis**: 적대 패널 → 머지 → 배포 → 강등율 관측


## TASK-20260731T184300-loadgate-blind-coaching — 부하게이트가 재작성 방향을 못 줘 추론이 정체되던 마찰 봉인

`/_dqa:conversation_audit` 단건 — 사용자 지목 대화(`에러로그 분석 및 원인 대안 제시` 계열,
conversation `20260731021152-36a7790b`, 105 메시지)에서 **6연속 `execute_sql` 차단**을 관측.
원장 `docs/improvements/conversation-audit/FRICTION_LEDGER.md` → `FR-loadgate-blind-coaching`.

- [x] 신호 — 명시 `E-SYS`(도구 거부 반복 6회) + `E-USR`(사용자 직접 불만: "블로킹이 너무 심하게
      나타난다"). 차단 메시지 6건 모두 동일 문구, 모델은 매번 형태만 바꿔 재제출.
- [x] 삼각측량 — ⓐ 코드: `tools.py` gate 분기가 정적 문구 반환 · `dialects.py` 는 `rows×filtered`
      곱만 사용, ⓑ **라이브 EXPLAIN 실측**(product 7 데이터소스, 읽기 전용): `SELECT * FROM
      tf_log_05_item LIMIT 5` → rows=13,903,018·filtered=100 → est 13.9M → 차단(**실제 5행**),
      `WHERE LogTime >= …` → est **1**(파티션 4/26 프루닝) → 통과, ⓒ 전사: 6회 차단 후 다른 접근으로 우회.
- [x] 근본 2건 — **RC-1(L2 거부 피드백)**: EXPLAIN 이 이미 아는 "왜 무거운가"(접근형태·미사용
      인덱스·스캔 파티션)를 버리고 일반론만 반환 → 모델이 **이미 한 조언**을 재수신 → 재작성 루프.
      **RC-2(L5 추정)**: `EXPLAIN.rows` 는 LIMIT 미반영 스캔 상한인데 이를 "예상 처리 행수"로 사용.
- [x] 거짓양성 기각(정직) — 사용자가 지목한 "LIMIT 1인데 차단" 그 쿼리는 `COUNT(*)`·`AVG()` 집계라
      **LIMIT 과 무관하게 전체 스캔이 맞다**(가드 판정 정당). 전체 차단 25건 중 **24건이 집계** —
      "가드가 과차단한다"는 표면 가설은 데이터로 `refuted`. 진짜 결함은 거부 *자체*가 아니라 거부
      *피드백*(F4 위치 재지정)과, 별개로 실재하는 순수 LIMIT 오판(1건 관측·실측 재현).
- [x] corroboration = **structural** — 30일 distinct_conv **10** / 대화 129건의 7.8%,
      차단 23건 / `execute_sql` 386건의 **6.0%**(전체 기간 12 대화·25건).
- [x] 수정 — AC-0604(진단 코칭·반복 시 confirm_heavy 승격) + AC-0605(조기 종료 보장 형태 한정
      `min(est, n+offset)` 보정). 게이트 메커니즘·임계·fail-closed 규칙 불변.
- [x] 검증(코드/테스트) — 신규 `tests/test_query_guard_coaching.py` **19건** PASS(오탐 방지 8건:
      WHERE/집계/filesort/조인/서브쿼리·CTE/DERIVED/문자열 리터럴 LIMIT/하향-전용) + 기존
      `test_query_guard.py`·`test_mssql_load_estimate.py` 35건 PASS(스텁 진입점 이동 반영).
- [x] 검증(dogfood, 라이브 계획 주입) — 라이브 EXPLAIN 4건을 새 코드로 판정: 순수 LIMIT 2건
      13.9M/30.5M → **5/3 로 보정 PASS**, 집계·인덱스미사용 2건 **차단 유지 + 진단 문구 부착** 확인.
- [x] §18.8 적대 패널(codex 3렌즈) — **[P1] 2건으로 출하 차단 판정을 받았고 둘 다 재현했다**:
      주석 속 가짜 LIMIT(`-- LIMIT 5`)과 `SQL_CALC_FOUND_ROWS`/`DISTINCTROW` 가 **실제 전체 스캔을
      게이트로 통과**시켰다 — 내가 막으려던 부하 회귀를 내가 만들고 있었다. [P2] 5건([P2] worst
      선택·거짓 탈출구 안내·카운터 과발동·MSSQL 폴백 잠식·죽은 스텁) + [P3] 2건 포함 **9건 전부
      흡수**(1건은 코드가 아니라 문서를 정정). 역검증 재현 **생존 0**, 테스트 19 → **31건**,
      feature 전체 **2360 passed / 30 skipped**.
- [x] 배포 — PR #1112 merge main `97af7d27` → `make deploy-web` 전체 스코프. **4서비스
      GIT_COMMIT=97af7d27 healthy**(web-a·web-b·ask-worker·insight-worker), soak 통과.
      **1차 시도는 부분 실패**: insight-worker 가 300s 내 healthy 미도달 → 워커군 last-good 롤백
      (web 만 신코드). 원인은 이번 변경이 아니라 기동 직후 외부 datasource 다수 도달 불가로 헬스체크
      지연 — 안정 후 멱등 재실행으로 성공. `make` 종료코드가 파이프에 가려 0 으로 보인 점도 기록.
- [x] 배포본 런타임 실증(ask-worker, 라이브 EXPLAIN) — 마찰 재현 케이스 `SELECT * FROM
      tf_log_05_item LIMIT 5` 가 **est 13,891,780 → 5 로 보정되어 PASS**(종전 차단), 전역 집계는
      **차단 유지 + 진단·approx_rows 대안 부착**, P1 회귀 케이스(`-- LIMIT 5` 주석 위장)는 **차단 유지**.
- [ ] 라이브 대화 실측 — 실제 사용자 대화에서 차단 빈도가 줄고 재작성이 성공하는지. 다음 audit 의
      corroboration 재측정으로 확인(그 전까지 원장 status = `fixed:deployed:unverified-live`).

### Requested Scope (요청 범위 자기-열거) — TASK-20260731T184300-loadgate-blind-coaching
- [x] `"무거운 쿼리" 블로킹 원인 파악` — 산출물: 본 섹션 근본 2건 + 거짓양성 기각 · 배선 확인:
      라이브 EXPLAIN 실측표(대화 전사 6건 ↔ 실행계획 대조).
- [x] `목적 수행을 위한 이슈 해소` — 산출물: `CHG-20260731T184300-loadgate-blind-coaching`
      (AC-0604/AC-0605) · 배선 확인: 신규 **31** + feature 전체 2360 PASS, 라이브 계획 dogfood 4건,
      §18.8 패널 [P1] 2건 흡수 후 역검증 생존 0.
- [x] `배포 + 배포본 코드 동작 실증` — 산출물: 4서비스 `97af7d27` healthy · 배선 확인: ask-worker
      라이브 EXPLAIN 3케이스(보정 PASS / 차단+진단 / P1 회귀 없음).
- [ ] `라이브 대화 소멸 확인` — **미수행**(실사용 대화 축적 후 다음 audit corroboration). 정직 분리 표기.

**주장 affordance 실측 (G3)**: 사용자 표면 affordance 주장 없음(도구 결과 문자열 = LLM 대면) → `해당 없음`.

### 정본
rationale=REVIEW `REV-20260731T184300-loadgate-blind-coaching` ·
변경이력=MODIFY `CHG-20260731T184300-loadgate-blind-coaching` ·
마찰원장=`docs/improvements/conversation-audit/FRICTION_LEDGER.md` `FR-loadgate-blind-coaching`.

## TASK-20260731T203000-loadgate-postdeploy — 배포 결과·배포본 실증 기록 (문서만)

- [x] 배포 — PR #1112 → main `97af7d27`, `make deploy-web` 전체 스코프, 4서비스 healthy.
- [x] 1차 시도 부분 실패 기록 — insight-worker healthy 미도달 → 워커군 롤백(ask-worker 구코드
      잔존 = 마찰 수정 라이브 미도달). 원인은 외부 datasource 도달 불가로 인한 헬스체크 지연,
      멱등 재실행으로 해소. `make` 종료코드 파이프 가림도 기록.
- [x] 배포본 런타임 실증 — ask-worker 라이브 EXPLAIN 3케이스 통과(보정 PASS · 차단+진단 · P1 회귀 없음).
- [ ] 라이브 대화 실측 — 다음 audit corroboration 재측정분(미수행, 정직 분리).

### Requested Scope (요청 범위 자기-열거) — TASK-20260731T203000-loadgate-postdeploy
- [x] `배포 결과 기록` — 산출물: 원장 status `fixed:deployed:unverified-live` · 배선 확인: 4서비스 GIT_COMMIT.
- [x] `배포본 동작 실증` — 산출물: 본 섹션 실증 3케이스 · 배선 확인: ask-worker 컨테이너 직접 실행.
- [ ] `라이브 대화 소멸` — **미수행**(다음 audit). 정직 분리 표기.

**주장 affordance 실측 (G3)**: 사용자 표면 affordance 주장 없음 → `해당 없음`.

### 정본
rationale=REVIEW `REV-20260731T203000-loadgate-postdeploy` ·
변경이력=MODIFY `CHG-20260731T203000-loadgate-postdeploy`.

## TASK-20260803T170000-loadgate-replay-verify — 라이브 재현 A/B 검증 (문서만)

사용자 요청 "관련된 대화를 재현하며 해당 이슈가 해소되었는지 검증" 에 대한 실측.

- [x] BEFORE 기준선 — 원 대화 `…36a7790b`: 차단 **6회**, 진단 문구 **0/6**, 조사 무산.
- [x] 재현 실행 — 배포본 ask-worker(`97af7d27`)에서 **같은 조사**(1062 PK 중복 · 1264 범위 초과
      원인 규명)를 콘솔 경로로 실행(라이브 사용자 대화 테이블 미오염). 17 steps · 6,078자 답변.
- [x] AFTER 측정 — 차단 4회, **진단 4/4(100%)**, 전역집계 고지 3, `approx_rows` 안내 2,
      **escalation 2회 설계대로 발동**, 차단 직후 또 차단 4→2, **조사 목적 완수**.
- [x] 재작성 궤적 확인 — 진단 수신 후 대상을 `TF_ErrorLog` 로 전환 + `LIMIT` 축소 → 성공,
      재차단 후 `BETWEEN … LIMIT 20` 으로 범위 축소 → 성공 → 실데이터 조회로 답변 완성.
- [x] 한정 기록(정직) — RC-2(LIMIT 보정)는 이 재현에서 **미발동**(모델이 순수 LIMIT 조회를 내지
      않음; 그 레버는 배포본 직접 실측에서 확인) · 콘솔 경로 부작용으로 `scratch_import` 1회 거부 ·
      **모집단 빈도 감소는 미측정**(배포 직후 표본 부재 → 다음 audit corroboration).
- [x] 원장 status — `fixed:deployed:unverified-live` → **`fixed:deployed:verified`**(근거는 통제된
      A/B 재현까지로 한정 표기).

### Requested Scope (요청 범위 자기-열거) — TASK-20260803T170000-loadgate-replay-verify
- [x] `관련 대화 재현` — 산출물: 배포본 재현 실행(17 steps) · 배선 확인: `__ask_worker__` id 6587~6622 도구 흐름.
- [x] `이슈 해소 검증` — 산출물: BEFORE/AFTER 대조표(원장) · 배선 확인: 차단 문구 특성 집계 SQL + 재작성 궤적 tool_calls.
- [x] `정직한 한정 표기` — 산출물: 미발동 레버·미측정 축 명시.

**주장 affordance 실측 (G3)**: 사용자 표면 affordance 주장 없음 → `해당 없음`.

### 정본
rationale=REVIEW `REV-20260803T170000-loadgate-replay-verify` ·
변경이력=MODIFY `CHG-20260803T170000-loadgate-replay-verify` ·
마찰원장=`FR-loadgate-blind-coaching`.

## TASK-20260805T1600 — 첨부 변경 사실 코드-권위 봉인 (conversation_audit `FR-attachment-change-false-absence`)

- [x] 마찰 진단 — 대화 `…2dce99c7`(fork, admin, product 119) 답변이 "새로 첨부되거나 변경된 파일이
      없습니다" 단정. DB 실측: v2 갱신 8 · 신규 4 · 이월 1 = 13(assistant 가 나열한 13과 일치).
- [x] 컨텍스트 정상 전달 **입증**(거짓 원인 배제) — 배포본 ask-worker 재구성: `★신규` 12 · `🔄v2` 8 ·
      본문 13건 인라인 · FILE UPDATES diff 8건, 섹션 38,013자. `ask_jobs.payload.new_attachment_ids`
      12건 정상. 토큰 정합(재구성 66,131 vs 실제 91,054)으로 섹션 부재 시나리오 기각.
- [x] 근본 확정 — 부재 단정을 막는 **코드-권위 규칙 부재**(기존 봉인 `FR-false-absence-zero-row` ·
      LIVE-DB GROUNDING 은 **DB 축 전용**) + 표식이 72k자 프롬프트 **중간**(offset 25,840)에만 존재.
- [x] A — `compose_system_prompt` 말미 코드-권위 사실 블록(`_build_attachment_authority_directive`).
- [x] C — 사용자 턴 매니페스트 한 줄(`_build_attachment_turn_manifest`, LLM 전달용 한정).
- [x] B — red-team 리뷰어 능동 검출(`build_attachment_change_facts` + 프롬프트 BLOCK 규칙, find/verify 양 패스).
- [x] 단일 사실 채널(`_ATTACHMENT_TURN_FACTS_CTX`) — compose 첫 문장 클리어로 교차-대화 오염 차단.
- [x] 보안 흡수 — 권위 블록 비신뢰 파일명 평탄화(`_flatten_untrusted_name`).
- [x] 테스트 18건 + `make test` 전량 exit 0 + ruff clean.
- [x] dogfood(배포 전 최대치) — 실패 대화 데이터로 실측: 사실 8/4/1 정확 · 권위 블록 offset
      68,005/69,813(**최종 위치**, LIVE-DB GROUNDING 63,854 뒤) · 기존 표식 회귀 0.
- [x] §18.8 backend/qa 적대 패널(사용자 승인 후 호출) — **BLOCK** 판정, [P1] 5 · [P2] 8 **전건 흡수**:
      부정 분기 제거(클라이언트 신호를 store 권위로 단정하던 구조) · 리뷰어 블록 무음 절단 제거 ·
      diff 미렌더 파일 분리 · 내용 동일 결론 금지 해제 · 배선 seam 테스트 신설.
- [x] 뮤테이션 역검증 8종 전건 KILLED(m1 A삭제·m2 위치이동·m4 C합치기·m5 verify패스·m6 bounded게이트·
      m10 0행경로·m11 부정단정·m12 무음절단) — 초판은 이 중 6종이 전부 생존했다.
- [x] 재-dogfood — 사실 8/0/4/1 · A 블록 최종 위치(49,741/51,707, LIVE-DB GROUNDING 45,590 뒤) ·
      기존 표식 회귀 0(★신규 12·🔄v2 8·diff헤더 8) · A 블록 1,968자.
- [x] 배포 완료(2026-08-05) — PR #1155 merge main `70df13a3` → `make deploy-web` 전체 스코프,
      soak 90s 통과·롤백 0. 4서비스 healthy(워커 `70df13a3` · web `8b46bdec`, 후자는 전자의 후손이라
      본 변경 포함 — `merge-base --is-ancestor` 확인).
- [x] 배포본 런타임 실증 — ask-worker 에서 실패 대화 데이터로 `compose_system_prompt` 실행:
      사실 8/0/4/1 · `## ATTACHMENT SET` 이 `## LIVE-DB GROUNDING` 뒤 최종 위치 · 부정 단정 침묵 계약
      True(A·B) · 리뷰어 floor 규칙 True / 대칭 BLOCK 제거 True. web /healthz ok·mysql_ok·pg_ok.
- [ ] 라이브 실측(사용자 대화) — 같은 시나리오에서 부재 단정이 사라지는지 + 리뷰어 BLOCK 발동 여부 +
      권위 블록이 평가 품질을 누르지 않는지. 다음 audit 의 corroboration 대상.

### Requested Scope (요청 범위 자기-열거) — TASK-20260805T1600
- [x] `첨부 v2 갱신을 assistant 가 인식하지 못하는 이슈 개선` — 산출물: A+C+B 3축 봉인 ·
      배선 확인: dogfood 실측(권위 블록 최종 위치 + 사실 8/4/1) · 리뷰어 사실 블록 초안 앞 주입 테스트.
- [x] `admin 계정 / fork 대화 한정 확인` — 산출물: fork 10건 중 v2 재업로드 3건 대조
      (`…774ada22`·`…72c11c4b` 는 정상 인식 → 결정적 파손 아닌 **비결정 실패**로 정직 표기).

**주장 affordance 실측 (G3)**: 사용자 표면 affordance 주장 없음(전부 LLM 컨텍스트 내부) → `해당 없음`.

### 정본
rationale=REVIEW `REV-20260805T160000-attach-change-false-absence` ·
변경이력=MODIFY `CHG-20260805T160000-attach-change-false-absence` ·
마찰원장=`FR-attachment-change-false-absence`.

## TASK-20260805T1900 — `read_attachment` 완전성 계약 (conversation_audit `FR-read-attachment-preview-looks-partial`)

- [x] 사용자 보고 검증 — 대화 `…843232a3` step 6~8 실측: **전부 전문 수신**(1~42/42 · 1~32/32 ·
      1~28/28, tool 메시지 1,485·692·1,213자, 절단 마커 0). 보고된 건은 **표시 오인**이 맞다.
- [x] 표시 경로 특정 — 단계 보기 사이드 패널(`app.js` `_renderStepSidePanelBody`)이 `rs.preview`
      (500자 캡)를 절단 표시 없이 `<pre>` 렌더. 본문 채팅의 `buildStepBlocks` 는 non-SQL 스텝을
      `work — reason` 한 줄로만 그려 여기서는 안 보인다.
- [x] 실재 결함 분리 — 라이브 41회 / 8대화 중 절단 2회, **둘 다 모델의 `max_lines` 자기 제한**
      (3, 250). 그중 `SP_LOG_SCHEDULE_improved_v2.sql`(327줄 중 250줄)은 **이어 읽지 않음**.
      시스템 기본 600줄 캡 발동 **0회**.
- [x] 문구 — 전문/부분 헤더 분기(`start_line>1` 은 전문 아님).
- [x] 이어읽기 MUST 계약 + 남은 줄 수 + 미이어읽기 시 범위 명시 의무 + 도구 description 보강.
- [x] 표시 — `preview_truncated`/`preview_full_chars` 플래그(캡 상향 아님) + 패널 발췌 주석(feature-0003).
- [x] §18.8 backend+qa 패널 — **BLOCK**, [P1] 2 · [P2] 9 · [P3] 6 **전건 흡수**.
      초판 테스트가 `read_attachment_content` 를 통째로 stub 해 실 슬라이싱을 안 태웠고, 그 사각에
      **문자 상한 경로의 정량화된 허위**(남은 줄 수 오보 → 이어읽기 구멍)와 **패널 주석의 모델
      수신분 단정**(진짜 미열람 단계를 안심 문구로 덮음)이 있었다.
- [x] 테스트 재작성 — **실 함수 경유 17건** + headless JS 17 assert.
      **구코드 대비 12/17 FAIL**(초판 5/9) 로 판별력 확인.
- [x] 정정 2건(§2.5) — "CI 가 JS 를 검증하지 않는다"(오류: headless 29건 관행 존재) ·
      표시 캡 유지 사유(오류: 도구별 분기 가능 → 실제 사유는 폴링 반복 전송).
- [x] 배포 완료(2026-08-06) — PR #1161 merge main `2cab05f3` → `make deploy-web` 전체 스코프,
      soak 통과·롤백 0, 4서비스 healthy. 배포본 런타임 실증(전문/문자상한/EOF초과/플래그) 완료.
      1차 시도는 로그 경로 부재로 `make` 미실행 → 서비스별 GIT_COMMIT 으로 발견·재실행(정직 기록).
- [ ] 라이브 실측 — 절단 발생 시 모델이 실제로 이어 읽는지 + 패널 주석 실 대화 화면 배치.

### Requested Scope (요청 범위 자기-열거) — TASK-20260805T1900
- [x] `웹 표시 간소화인지 실제 미열람인지 검토` — 산출물: 실측 대조표(전문 수신 3건 + 표시 500자 캡) ·
      배선 확인: `steps.result_summary_json` vs `core_messages` role=tool 길이 대조.
- [x] `이어읽기 계약까지 강화` — 산출물: MUST 계약·남은 줄 수·description 보강 · 배선 확인: 뮤테이션 4종.

**주장 affordance 실측 (G3)**: 사용자 표면 affordance 주장 = 단계 보기 패널의 "발췌" 주석.
로직은 headless JS 로 고정(주석 유무·폴백·문구 금지어·표 분기 포함)했고, **실 브라우저 렌더는
배포 후 확인**(미실측).

### 정본
rationale=REVIEW `REV-20260805T190000-read-attach-completeness` ·
변경이력=MODIFY `CHG-20260805T190000-read-attach-completeness` ·
마찰원장=`FR-read-attachment-preview-looks-partial`.

## TASK-20260806T1600 — 첨부 전달 구조 개선 (conversation_audit `FR-attach-delivery-truncated-by-output-cap`)

- [x] 진단 — 대화 `…1d8ed346`: 첨부 6건 중 갱신본 **1건**, 답변은 "6개 전부 갱신".
      `completion_tokens=100,000`(상한 정확 도달), 답변 말미 raw SQL 중간 절단.
      `finish_reason` 은 코드 전체에서 **한 번도 읽지 않음**. red-team 은 materialize **이전**에
      돌아 실제 전달 결과를 구조적으로 볼 수 없음. `_ASSISTANT_EDIT_COUNT_CAP=5` 로 6건은 애초 초과.
- [x] 방향 전환(사용자 지시) — 증상 대응(A 감지·B 리뷰·C 순서)이 전부 "전달 payload 가 답변 출력
      예산을 공유한다" 는 전제를 남긴다는 지적을 수용, **구조 개선**으로 재설계.
- [x] ① `update_attachment` 도구 — 파일당 독립 출력 창 + 성공/실패 피드백 + 스코프·가드 공유.
- [x] ② `patch`(unified diff) 전달 — fail-closed 적용기(`modules/patch_apply.py`).
- [x] ③ `finish_reason` 절단 감지 + 사용자 경고 + red-team 사실(구조 개선과 무관하게 필요).
- [x] red-team `DELIVERY FACTS` — 허위 완료 선언 `honesty` BLOCK 규칙(floor 프레이밍으로 오탐 가드).
- [x] §18.8 security + backend/qa 패널 — **BLOCK**, [P1] 4 · [P2] 9 · [P3] 6 **전건 흡수**.
      가장 중요한 건 **도구로 만든 첨부가 다운로드 칩에 안 나오던 것**(message_id 미바인딩) —
      기능 무효이자 새 허위 완료 채널이었다.
- [x] 테스트 56건(33+23) + **뮤테이션 9/9 KILLED** + 전량 회귀 실패 0.
- [x] 배포 완료(2026-08-06) — PR #1178 merge main `d04ab2f2` → `make deploy-web` 전체 스코프,
      soak 통과·롤백 0, 4서비스 healthy. 병렬 세션 머지로 rebase 1회 후 정본 회귀 재실행 실패 0.
- [x] 배포본 런타임 실증 — 도구 노출·라우팅·바인더 적재·절단 latch·패치 정상적용 ·
      **잘린 패치 거부**·**문맥 없는 삽입 거부**(둘 다 패널 P1 재현 입력)·DELIVERY FACTS floor.
- [x] 라이브 실측 완료(2026-08-07, PB-0008) — 도구 채택 4/4 · 완주 4/4 · **칩 4/4 렌더**(패널 P1) ·
      패치 1회차 4/4 · **completion_tokens 분리 1,973 확증**. 원장 → `fixed:deployed:verified`.
      증거: `docs/test-runs.d/REV-20260807T130000-attach-delivery-live.md`.
- [ ] 미실측 잔여 — `read_attachment` 완전성 계약(모델 미호출로 관측 불가 → 인라인 상한 초과
      첨부로 도구 경로 강제하는 실측 설계 필요) · DELIVERY FACTS BLOCK 경로(happy path 라 미발생).
- [ ] 부수 발견 2건 처리 방향 결정 — `FR-redteam-attach-excerpt-cap-false-grounding-block` ·
      `FR-datasource-eager-connect-blocks-datasource-free-turn`(둘 다 원장 `triaged`, 미착수).

### Requested Scope (요청 범위 자기-열거) — TASK-20260806T1600
- [x] `assistant 및 red-team 이 해당 이슈를 포착하도록 개선` — 산출물: 도구 성공/실패 피드백(assistant)
      + DELIVERY FACTS BLOCK 규칙(red-team) · 배선 확인: execute_tool 라우팅 테스트 · 리뷰어 주입 테스트.
- [x] `completion_tokens 과 별개로 작동` — 산출물: 파일당 독립 턴 전달 + 패치로 토큰 급감 ·
      배선 확인: 전달 id → message_id 바인딩 → 칩 노출 경로 고정(워커·web 양쪽).

**주장 affordance 실측 (G3)**: 사용자 표면 affordance 주장 = "다운로드 칩으로 받습니다".
패널이 이 주장이 **거짓이었음**을 잡아냈고(바인딩 부재) 수정했다. 실 브라우저 칩 렌더는 배포 후 확인.

### 정본
rationale=REVIEW `REV-20260806T160000-attach-delivery-tool` ·
변경이력=MODIFY `CHG-20260806T160000-attach-delivery-tool` ·
마찰원장=`FR-attach-delivery-truncated-by-output-cap`.

## TASK-20260807T160000 리뷰어 첨부 발췌 앵커링 (FR-redteam-attach-excerpt-cap-false-grounding-block)
- [x] 발췌를 head-only → 초안 인용 구간 앵커(`_draft_probes`/`_select_excerpt_spans`), 예산 불변
- [x] 절단 표기를 구조적 coverage(SHOWN/NOT SHOWN 줄 범위 + "unknown, not absent")로 교체
- [x] 줄 세기 규약 통일 — 말미 개행이 유령 줄을 만들어 없는 구간을 미표시로 보고하던 것 교정
- [x] 리뷰어 규칙 확장(부분 발췌 · no tool runs) + 과교정 방지(모순 주장은 여전히 BLOCK)
- [x] `orchestrate_review` 3지점 draft 배선 + **수정본 채택 후 재앵커**(비수렴 차단)
- [x] 테스트 27건 · 뮤테이션 12/12 KILLED · 전량 회귀 · ruff · 배포본 재현
- [x] §18.8 적대 패널(backend·qa) — **BLOCKING 4 · MAJOR 4 · MINOR 7 전건 흡수**
      (예산 소멸 · char↔line 허위 · 총예산이 FULL 라벨을 거짓말로 · ALSO ATTACHED 날조 보호)
- [x] 패널이 잡은 거짓 문서 주장 2건 정정(예산 불변 · 회귀 없음)
- [x] 배포 완료(2026-08-11) — PR #1196 merge main `4c7a8f27`, soak 통과, 4서비스 healthy.
      rebase 1회 후 전량 회귀·뮤테이션 재실행(23/23 KILLED).
- [x] 배포본 런타임 실증 — 꼬리 근거 3형태 도달 · 예산 소진 · 허위 완전성 0 · 거짓 FULL 0 ·
      면책 경계 4종 탑재.
- [ ] 라이브 실측 — 정확한 답변에서 경고 배너가 실제로 사라지는지(다음 실사용 턴).

## TASK-20260811T110000 라이브 실측 후속 — 발췌 예산 결함 2건 (FR-redteam-attach-excerpt-cap-false-grounding-block)
- [x] 라이브 실측(원 대화 동일 시나리오 반복) — BEFORE/AFTER 대조로 배포본 결함 2건 적발
- [x] 결함1 겹치는 창 예산 이중과금 → 병합 union 기준 회계 + head 연장 수렴 루프
- [x] 결함2 입력 순서 고정 → 관련성 정렬 + 지분 비례 축소(floor·오버헤드 선공제)
- [x] 부수: 1-pass 적재가 매니페스트를 절단에 삼켜 파일이 증발 → 2-pass 적재
- [x] 신규 5건 포함 44건 · 뮤테이션 18/18 KILLED · 전량 회귀 · ruff
- [ ] 배포 + **라이브 재측정**(같은 대화에서 BLOCK 이 실제로 사라지는지)
