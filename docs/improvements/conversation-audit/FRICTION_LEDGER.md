# FRICTION_LEDGER — conversation_audit 마찰 원장 (단일 정본)

`/_dqa:conversation_audit` 의 진행 원장(§C5). 항목 = `friction-id` 1개. **content·PII·원본 데이터 값 비전재**(집계 수치·익명 라벨·마스킹만). status 는 측정으로만 `verified` 로 닫힌다(거짓 done 방지). 별도 큐 파일 신설 금지 — 이 파일이 진행 원장.

status enum: `triaged`→`fixed:undeployed`|`fixed:deployed:unverified-live`|`fixed:deployed:verified`|`deferred`|`report-only`|`rejected`|`needs-human`|`blocked:<reason>`|`awaiting-merge:PR#<n>`|`regressed`.

---

## FR-datetime-tz-server-vs-stored — fixed:undeployed (L1 grounding 지침 lever)

- **status**: `fixed:undeployed` — L1 프롬프트 lever(`_DATA_GROUNDING_GUIDANCE` 신설·항상 주입) 출하, 배포 전. 배포 후 시각-필터 질의에서 저장값 TZ 추측 대신 확인·가정 명시 관측 시 `fixed:deployed:unverified-live` 로 전이.
- **source**: DQA 마찰개선사항_20260722_v2.md B-1(라이브 대화 아닌 AI 작업자 집계작업 관측 — provenance 정직 표기). `/_template:entry` 로 검토·개선.
- **last_seen**: 2026-07-22 · **seen_count**: 1 · **seen_distinct_conv**: 1 (FGT 집계 세션)
- **symptom_confidence**: high (작업자 명시 + 데이터 교차검증으로 재현) · **rootcause_confidence**: high (동작 원인 명확 — 프롬프트에 저장값 TZ grounding 부재)
- **suspected_layers**: **L1**(프롬프트 grounding 부재) — 모델이 `@@time_zone`(서버 설정)을 저장값 의미로 오해석
- **증상(signal)**: `I-FALSE` 거짓 확신 — assistant 가 서버 TZ 설정(Asia/Tokyo)만 보고 "저장값=JST → -9h=UTC" 라고 확신 오판. 실제 저장 DATETIME 은 UTC(MySQL DATETIME 은 TZ 미저장) → 집계 기간 9시간 어긋날 뻔(전 시트 오염 위험). 사용자 경고 + 오픈시각↔가입 램프업 정렬 교차검증으로 겨우 정정.
- **confirmed_root_cause(요지)**: 시스템 프롬프트에 "서버 TZ 설정 ≠ 저장값 의미(naive DATETIME 은 TZ 미저장)" grounding 이 없어, 모델이 `@@time_zone`/`NOW() vs UTC_TIMESTAMP()` 를 저장값 기준 TZ 로 오추론. 게임-무관·모든 MySQL datasource 일반.
- **fix**: TASK-20260722-dqa-data-grounding / `feature-0002-agent-core` `_DATA_GROUNDING_GUIDANCE`(타임존 블록: 서버 TZ≠저장값 명시 + 불확실 시 알려진 기준점 데이터 교차검증 + 변환 가정 답변 명시 + 미확정 시 임의 offset 금지). Major(core 시스템 프롬프트). test_gc_dialect_context 3건.
- **필요한 사람 액션(1줄)**: (후속·별도) datasource 메타데이터에 "저장값 기준 TZ" 명시 필드 + 시각-필터 질의 시 자동 표면화(스키마·UI 붙는 큰 lever) — 이번엔 즉효 프롬프트 grounding 만.

## FR-enum-code-hallucination — fixed:undeployed (L1 grounding 지침 lever; D-2 분리저장 동반)

- **status**: `fixed:undeployed` — L1 프롬프트 lever(`_DATA_GROUNDING_GUIDANCE` ENUM·분리저장 블록) 출하, 배포 전.
- **source**: DQA 마찰개선사항_20260722_v2.md D-1(+D-2 분리저장). 라이브 대화 아닌 집계작업 관측(provenance 정직).
- **last_seen**: 2026-07-22 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **symptom_confidence**: high (정본 LogType 사전과 대조로 오류 확정) · **rootcause_confidence**: high
- **suspected_layers**: **L1↔L4**(프롬프트 grounding 부재 + KB ENUM 사전 미매칭 시 폴백 없음)
- **증상(signal)**: `I-FALSE` — CurrencyType 코드를 기억으로 "3=Stamina" 환각(정본 4=스태미너). 코드 오지정 시 완전히 틀린 집계. 병행 D-2: 재화가 Gold/GemV2/Currency 테이블 분리 → "전체 재화" 를 한 테이블만 집계하면 조용한 누락.
- **confirmed_root_cause(요지)**: GLOSSARY & ENUM VALUES 주입 인프라(L1574)는 있으나 미매칭 시 모델이 환각으로 코드↔의미를 지어냄. 프롬프트에 "코드 의미 추측 금지 → 사전/샘플링 grounding 또는 미보유 고백" 지침 부재.
- **fix**: TASK-20260722-dqa-data-grounding / `feature-0002-agent-core` `_DATA_GROUNDING_GUIDANCE`(ENUM 블록: 코드 의미 지어내기 금지 + GLOSSARY & ENUM VALUES·`get_sample_rows`/`GROUP BY` 분포 확인·미보유 고백 / 분리저장 블록: "전체 X" 커버리지 명시). Major(core). test 포함.
- **필요한 사람 액션(1줄)**: (해당 게임 KB 데이터) KR_LIVE 제품 ENUM 사전에 CurrencyType/ChangeReasonType 정본 적재는 데이터 입력(코드 아님) — 지침이 미보유 시 환각 대신 고백을 강제하므로 안전판 확보.

## FR-scratch-result-csv-missing — fixed:undeployed (L7 결과추출 lever)

- **status**: `fixed:undeployed` — scratch_sql 결과 CSV export 구현, 배포 전.
- **source**: DQA 마찰개선사항_20260722_v2.md F-5/C-3.
- **last_seen**: 2026-07-22 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **symptom_confidence**: high · **rootcause_confidence**: high (코드 경로 확정)
- **suspected_layers**: **L7**(결과 추출/다운로드) — scratch 결과가 inline 절단 + `/shared/out` CSV 미export
- **증상(signal)**: `E-AST` 대량 결과 회수 곤란 — cross-DS 병합(scratch_sql) 결과가 미리보기(~200행) 절단 + CSV 미저장 → 수백 행 결과를 사용자가 회수 불가(execute_sql 은 CSV 저장됨과 비대칭).
- **confirmed_root_cause**: `scratch.run_sql` 이 미리보기 상한까지만 fetch 하고 `save_csv` 미호출. execute_sql 은 전체 fetch + save_csv + "CSV 저장:" emit → 웹 `CSV_PATH_RE` 파싱으로 다운로드 링크 생성. scratch 만 그 경로 부재.
- **fix**: TASK-20260722-dqa-scratch-csv-export / 코드 `feature-0002-agent-core`(정본 feature-0022) — `run_sql` export 상한(100000)까지 전체 fetch + `_tool_scratch_sql` save_csv parity. 프론트 무변경(기존 CSV_PATH_RE 재사용). Minor(비파괴 결과추출). test_scratch 3건.
- **필요한 사람 액션(1줄)**: 없음(자기완결) — 배포 후 라이브 e2e(대량 scratch 병합→CSV 다운로드)로 verify.

## FR-nl2sql-schema-discovery-giveup — fixed:deployed:unverified-live (L1+casing 프롬프트 lever; L2 deferred)

- **status**: `fixed:deployed:unverified-live` — **부분 수정**: L1 프롬프트 lever(능동 해석 modality 무관 일반화 → 1:1 도 주입; assume-vs-ask·give-up 금지) + casing 프롬프트 lever(MySQL 식별자 표기 보존·소문자화 금지) 출하·배포. **단 L2 lever(거부/에러 피드백에 교정 힌트 부착)는 미구현 — report-only 유지**(single-conv idiosyncratic·Major, corroboration 임계 미달 → 임계 돌파 시 plan 후 promote). live 재감사 측정 전이라 `unverified-live`(거짓 `verified` 금지).
- **fix(요지)**: TASK-20260629T142624-active-interp-modality / `feature-0002-agent-core` / REV-20260629T142624 (§18.8 AGENT-TEAM 패널, BLOCKER1+MAJOR3 전부 적대검증 REFUTED). PLAN-APPROVED. 가드 경계 불변(advisory 프롬프트 일반화 한정).
- **last_seen**: 2026-06-26 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-94 · **conv(마스킹)**: …91655acc
- **symptom_confidence**: high (명시 신호) · **rootcause_confidence**: med (코드 경로 후보 확정, file:line 단정은 추가조사 필요 → `inconclusive→med`)
- **suspected_layers**: **L2↔L8** (datasource 스키마 dialect/casing + tool 피드백 모순) + **L1** (프롬프트: ambiguous 요청에 assume-vs-ask 정책)
- **증상(signal)**: `E-AST` 과도 재질문·장황 무행동 — NL2SQL assistant 가 turn1 에서 tool 8회(search_tables×4·execute_sql×3·describe_table) 소비 후 스키마를 못 특정해 **포기**, 사용자에게 "스테이지 정의?/기준?/기간?" 대량 재질문. 사용자는 turn2 에서 짧게 재지시(`E-USR` over-spec/좌절 신호).
- **confirmed_root_cause(요지)**: assistant 가 존재하지 않는 스키마명(`dbgame`/`dblog`, 추정 lowercase)을 추측 → `execute_sql` 가 `1049 Unknown database 'dbgame'` 반환·`SCHEMA()=NULL`(기본 DB 미선택). 동시에 `describe_table` 는 같은 경로에 응답을 돌려줘 **tool 간 모순 피드백** → 모델이 자기교정 못 하고 give-up. 재발 메커니즘 = `data/config drift`(datasource↔스키마 바인딩) + `model limit`(거부/에러 피드백에 교정 힌트 부재, L2).
- **corroboration**: 최근 14일 `Unknown database/1049` 시그니처 = **distinct_conv 1** → **idiosyncratic**(임계 미달, 전역수정 자격 없음). 표본 부족.
- **disposition 근거**: 수정 후보가 프롬프트(assume-vs-ask)·tool 거부 피드백(교정 힌트)·datasource 스키마 해소(casing) 로 **Major**(코어 LLM 경로). 단일 대화 + idiosyncratic + Major → `report-only`. 자동 fix-now 금지(저흔적 이탈 예외는 Minor 한정).
- **필요한 사람 액션(1줄)**: ~~(b) 모호 요청에 1회 합리적 가정 후 진행 vs 재질문 기준(L1)~~ **→ 출하**(능동 해석 일반화 + casing 프롬프트, TASK-20260629T142624). **잔여 (a)**: `search_tables`/`describe_table`/`execute_sql` 거부·0행에 **교정 힌트**(올바른 datasource·스키마 casing 후보) 부착(L2 코드 lever) — single-conv idiosyncratic·Major 라 report-only 유지, corroboration 임계 돌파 시 plan 후 재triage. 코드 거주: `feature-0002-agent-core`.

## FR-resultset-table-narration-mismatch — report-only

- **status**: `report-only` · **last_seen**: 2026-06-26 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 · **conv(마스킹)**: …91655acc
- **symptom_confidence**: med-high · **rootcause_confidence**: low (표면 관측, 코드 경로 미추적)
- **suspected_layers**: **L7** (표시·표 렌더 truncation) ↔ **L3** (narration 이 표시 안 된 행을 인용)
- **증상(signal)**: `I-FALSE` 거짓 성공 — turn2 최종답이 표 헤더 "상위 7개" 라 쓰고 **5행만 렌더**, 첨부 CSV 는 "전체 7행", 그런데 서술("주요 발견사항")은 **표에 없는 행**(상위에 안 뜬 고-도전 스테이지)을 핵심 근거로 인용 → 사용자가 보는 표와 서술이 불일치. 추가로 랭킹이 n=1 짜리 0% 행을 통계적 무의미하게 상위 배치. turn2 직후 **user 무응답 종료(`I-SIL` 침묵 이탈)**.
- **disposition 근거**: 단일 대화 표본, 코드 경로 미추적(rootcause low) → `report-only`. 표/서술 정합·min-attempt 임계는 표시 계약(L7) 또는 결과 요약 프롬프트(L1) 결정 필요.
- **필요한 사람 액션(1줄)**: 결과 표 truncation 정책과 narration 의 "표시된 행만 인용" 계약을 정할지 결정(L7/L1). corroboration(표/CSV 행수 불일치 빈도) 미측정 — 정량화 어려움, 추가 신호원 discovery 필요.

## FR-diff-lineno-prefix-leak — fixed:deployed:unverified-live

- **status**: `fixed:deployed:unverified-live` (Minor 수정·테스트 PASS·적대패널 SAFE → **배포 완료** PR #467 머지 main `5942a25` + web 재배포(`/healthz` git_commit=`5942a25` live·서빙 app.js byte-identical main). 다음 audit corroboration(```diff+`\d+→` distinct_conv) 재측정 0 유지 시 `verified`. PB-0008 실 Windows 브라우저 시각검증은 WSL 미실행 — 사용자 확인 권장.)
- **last_seen**: 2026-06-29 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 동기 · **conv(마스킹)**: …356708b8 (topic "계정 연동 및 보상 일괄 수령 쿼리 구성", assistant msg id 4058)
- **symptom_confidence**: high (사용자 명시 보고 `E-USR` + 데이터 재현) · **rootcause_confidence**: high (코드+DB+전사 삼각측량, file:line 확정)
- **suspected_layers**: **L1↔L6**(프롬프트 금지지침 vs 모델 준수 실패)가 **L7**(렌더러)에서 표면화
- **증상(signal)**: assistant 가 ```diff 블록 context 줄에 `45→\t…` 줄번호+화살표 prefix 를 그대로 출력 → 웹 렌더러가 코드 본문으로 표시해 줄 표현 깨짐(변경줄만 표준 `+`/`-`).
- **confirmed_root_cause**: agent_core `_number_file_lines`(feature-0002, TASK-0256e)가 첨부 본문 각 줄에 `<N>→` 줄번호 prefix 주입(의도된 기능). 프롬프트(agent_core.py:770-778)가 "diff 안 `<N>→` 금지" 지시하나 모델이 가끔 context 줄에 복사(model limit). 웹 렌더러 `buildDiffRows`(feature-0003 app.js·share.js)가 누출 미정규화 → `45→` 가 코드로 렌더. 재발경로=model limit → **렌더러를 결정론적 최후 방어선으로 봉인**(모델 누출 무관 매번 차단·기존 저장 메시지도 render-time 정상화).
- **corroboration**: 전체 기간 ```diff 사용 대화 20건 중 누출 1건 → **idiosyncratic**(빈도 임계 미달). 단 **사용자 명시요청 + RC 코드 확정 + 결정론적 저위험 봉인** → fix-now(자기-주입 artifact 정규화라 과적합 아님).
- **fix**: `CHG-20260629T172122-diff-lineno-prefix-leak` (코드 거주 **feature-0003-agent-web-ui**: app.js·share.js `buildDiffRows` 누출 정규화 `/^\s*(\d+)→/` + `tests/verify_diff_lineno_leak.mjs` 30/30 PASS). 위험등급 **Minor**(L7 display-only). 적대패널 `[SUBAGENT:adversarial-correctness]` REFUTED(BLOCKING 0, H2 오매칭=cosmetic NIT).
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260629T172122-diff-lineno-leak
- **deferred(cross-ref)**: agent_core 프롬프트 강화(feature-0002, Major·core LLM 경로) — 별도 batch. 렌더러 봉인이 누출 비가시화하므로 우선순위 낮음.
- **라이브 실측 필요분(§정직)**: 코드/테스트는 "렌더러가 누출 prefix 를 떼고 정상 diff 생성" 증명. "실제 사용자 화면 소멸" 은 배포 후 PB-0008 실 Windows 브라우저 실측분(미수행). 다음 audit 에서 corroboration(```diff+`\d+→` distinct_conv) 재측정 → 0 유지 시 `verified`.

## FR-edge-fallback-conversation-context-loss — fixed:deployed:unverified-live (L6↔L8 라우팅; 대화 답변 edge 폴백 봉인)

- **status**: `fixed:deployed:unverified-live` — 대화 답변(task='agent') 경로에서 edge(gemma) 폴백을 **구조적으로 완전 제거**해 배포. gemma 는 `-chat` 체인에서 도달 불가(config + G5 체인 가드 테스트로 고정). 두 계정 완전 장애 시 gemma 강등 대신 429/401 → 기존 LLM-error 핸들러가 "요청량 한도… 잠시 후 재시도" 정직 실패. **라이브 실측(실제 rate-limit 상황에서 gemma 미개입)은 rate-limit 조건 재현 의존이라 강제 불가** → corroboration 재측정이 0 유지 시 `verified`.
- **fix(요지)**: CHG-20260707T100640-no-edge-conversation-answer / **코드 거주 `feature-0002-agent-core`**(+ config `feature-0007`, 헬퍼 `shared`) / REV-20260707T100640-no-edge-conversation-answer (§18.8 적대 2렌즈 패널 backend/correctness C1~C5 + security/regression/litellm S1~S5 전부 REFUTE→CONFIRMED, NIT→G5 체인 가드 반영). PLAN-APPROVED(사용자 2026-07-07 결정 + 구현+검증+배포). PR #600 merge(main 2d590ce0) → ask-worker+web 재빌드(7381ef3b) + bedrock-gateway 재생성 + live probe(claude-haiku-4-chat→claude, gemma 아님) 확인.
- **last_seen**: 2026-07-06 (마찰 관측일; 수정 후 신규 gemma agent 턴 0) · **seen_count**: 1 · **seen_distinct_conv**: 2
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-117 · **conv(마스킹)**: …9e0883bb (topic "DB 설계 및 JSON 데이터 구성 검토", owner admin)
- **symptom_confidence**: high (사용자 명시 불만 "? 맥락을 잃어버렸나요?" + 데이터 재현) · **rootcause_confidence**: high (코드+DB(llm_usage.resolved_model)+전사 삼각측량, file:line 확정)
- **suspected_layers**: **L6↔L8** (모델 라우팅/폴백 — litellm fallback 체인이 대화 답변까지 로컬 edge 모델에 도달; ctx 4096 이 히스토리 절단)
- **증상(signal)**: `E-USR` 명시 불만 + `E-AST` 맥락 무시 + `I-FALSE` 거짓 성공 — turn2(4341)에서 assistant 가 방금 자기가 쓴 9053자 리뷰(4339)조차 "설계 내용 미명시"라며 무관한 일반론(Orders 테이블·MongoDB) 환각 → 사용자 "? 맥락을 잃어버렸나요?"(4342) → turn3(4343) "이전 대화를 기억한다" 부인하면서도 여전히 맥락 부재.
- **confirmed_root_cause**: turn2~4 가 요청 모델 `claude-haiku-4` 인데 실제 서빙(llm_usage.resolved_model)이 `gemma4:e2b`(로컬 edge-fallback, ctx 4096)로 silent 강등 — prompt_tokens 세 턴 모두 정확히 **4096**(turn1=29K)로 ~30K 토큰 대화 히스토리가 통째로 절단돼 맥락 소실. 원인 체인 = `litellm_config.yaml` fallback `claude-haiku-4 → root → edge-fallback(gemma)`, 두 claude OAuth 계정이 429(오늘 rate-limit 버스트) 시 gemma 우회. 재발 메커니즘 = **infra capacity → degradation 정책**(2026-07-04 "무중단 안전망"이 실제로는 "조용한 파탄"). 봉인 = 대화 답변 전용 edge-free alias(`claude-haiku-4-chat`) + `_call_llm` 라우팅(표면 계약 아닌 라우팅 정책 축소) + 기존 깨끗한-실패 핸들러 재사용.
- **corroboration**: 최근 14일 task='agent' resolved_model gemma = **distinct_conv 2 / 4콜, 전량 2026-07-06(수정 전)**. 총 agent 대화 40 중 ~5%, 오늘 집중(만성 아님·재발경로는 반복 확실). 배포 후 2시간 신규 gemma agent 턴 0. distinct_conv 2>1 이라 순수 idiosyncratic 은 아니나, **근본이 코드/config 정본까지 confirmed(high) + 심각도 최상(대화 파탄·명시 불만·신뢰 상실)** → fix-now(사용자 결정으로 Major promote).
- **disposition 근거**: Major(코어 LLM 경로·가용성 정책, 2026-07-04 결정 함의) → attended human-decision. 사용자가 AskUserQuestion 으로 "gemma 완전 차단·명백한 실패처리" 명시 결정(2026-07-04 무중단 결정을 대화 경로에 한해 override) → PLAN-APPROVED 후 구현+검증+배포.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260707T100640-no-edge-conversation-answer
- **범위 밖(인지)**: context-feeding aux(summary/topic)·prompt_gen·node_analysis 는 여전히 gemma(ctx 4096) 강등 가능 — 사용자가 assistant 답변 경로로 명시 한정. 필요 시 후속 audit.
- **라이브 실측 필요분(§정직)**: 코드/테스트/게이트웨이 probe 는 "대화 답변이 edge-free alias 로만 claude 에 라우팅되고, 실패 시 정직 안내" 증명. "실제 rate-limit 시 gemma 미개입" 은 rate-limit 조건 재현 의존(강제 불가) → 다음 audit 에서 corroboration(task='agent' resolved_model gemma distinct_conv) 재측정 → 0 유지 시 `verified`, 재증가 시 `regressed`.
- **post-deploy 게이트웨이 오류 조사(2026-07-07 별도 investigation, no-op)**: 배포 직후(10:31~10:41 KST) `bedrock-gateway` 로그에 `claude-haiku-4-chat`→`-root` 양쪽 모두 `max_tokens must be greater than thinking.budget_tokens`(400, req `…qkA5N9…`/`…qkBzx…`) 1회 발생(10:37:18) 확인·조사. **근본원인=코드 결함 아님**: 실패 시각 기준 `ask-worker`/`insight-worker` 이미지(10:32:18 재빌드, dangling image 직접 오픈해 확증)가 이미 본 fix 코드 보유 — stale-image 가설 기각. `_call_llm`(유일 caller, `agent_core.py:2665`)은 claude-* 모델에 `max_tokens=20000`(`_CLAUDE_MAX_TOKENS["agent"]`)을 항상 주입해 게이트웨이의 고정 `thinking.budget_tokens=5000`(litellm_config.yaml)과 충돌할 코드 경로 자체가 없음(정적 추적 완료, 호출부 전체 1곳). 게이트웨이에 직접 재현 테스트: `max_tokens≥5000`→200 정상, `max_tokens<5000`→위와 문자열까지 동일한 400 재현. 컨테이너 기동 이후 전체 로그에 이 오류는 이 1회뿐(재발 0). **결론**: 위 "live probe(...) 확인" 절차(앱을 우회해 게이트웨이에 직접 보낸 수동 확인 호출)가 `max_tokens` 미설정/과소 설정으로 보낸 1회성 프로브 아티팩트 — 실 사용자 대화 트래픽 영향 없음(해당 request들에 연계된 실 conversation_id 없음). 코드 수정 불필요, `status`/corroboration 수치 변경 없음.

## FR-readonly-query-shapes-overblock — fixed:deployed:unverified-live (L5 sql_guard shape 과차단; read-only allowlist 정확 확장 + write-node defense)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(전체 회귀 1899 PASS·§18.8 패널 MAJOR1 수정) + **배포 완료**(2026-07-13, PR #761 merge main `9892fc3b` → deploy-web 무중단 web-a/b + ask-worker/insight-worker 재빌드·재생성, 4서비스 GIT_COMMIT=9892fc3b; ask-worker 런타임 실증: UNION·SHOW CREATE TABLE·SHOW VARIABLES 허용 / 데이터수정CTE·UNION-agent_memory분기·SHOW GRANTS 차단 확인; web /healthz=9892fc3b). **라이브 대화 실측 미수행** → `unverified-live`. 다음 audit 에서 "보안 정책상 차단된 SQL" corroboration 재측정(UNION/Show 시그니처 감소) 시 `verified`.
- **fix(요지)**: CHG-20260713T171821-readonly-query-shapes / **코드 거주 `feature-0002-agent-core`** / REV-20260713T171821-readonly-query-shapes (§18.8 적대 3렌즈 패널 security+backend+qa — API 세션한도 조기종료→인라인 자기검증 완료, MAJOR1[데이터수정CTE 우회] 수정, 나머지 REFUTED). 사용자 승인=UNION + 읽기전용 SHOW(AskUserQuestion 2026-07-13).
- **last_seen**: 2026-07-13 · **seen_count**: 1 · **seen_distinct_conv**: 9 (corroboration structural)
- **modality**: 1:1 (추정) · **conv(마스킹)**: topic "동적 쿼리 및 테이블 변경사항 추가 리뷰"(`20260713074503-5cef7aa2`, product 95) 외 8
- **symptom_confidence**: high (사용자 명시 보고 + DB 재현) · **rootcause_confidence**: high (코드+PG agent_runtime 집계+전사 삼각측량)
- **suspected_layers**: **L5**(sql_guard SELECT/CTE-only shape 게이트가 read-only 패턴 과차단) — 실질 보안(쓰기·allowlist·금지함수·multi-statement)과 무관한 shape 가정 오류
- **증상(signal)**: `E-SYS`/`E-USR` — "보안 정책상 차단된 SQL". corroboration(PG core_messages 30일): `only SELECT/CTE allowed, got Union`(8, 최대)·`got Show`(5, SHOW CREATE TABLE/VARIABLES)·parse-fail(12)·multi-statement(4)·MSSQL db_id/db_name(3). 대상 대화 차단 2건 = `SHOW CREATE TABLE gunzgame.attendence`(테이블 변경 리뷰)·`SHOW VARIABLES LIKE 'lower_case_table_names'`.
- **confirmed_root_cause**: `sql_guard.py validate_sql_for_sandbox` shape 게이트가 root=`exp.Select`/`With` 만 허용 → 최상위 UNION(`exp.Union`)·읽기전용 SHOW(`exp.Show`)를 non-SELECT 라는 이유만으로 거부. 이전 describe_routine(FR-show-create-routine-blocked)은 프로시저 subset만 봉인. 재발경로 = model/guard 가정 오류(read-only 패턴을 unsafe 로 오분류).
- **봉인**: shape allowlist 를 read-only 로 정확 확장 — (a) set-op(UNION/INTERSECT/EXCEPT of SELECTs, 분기별 forbidden-schema/lock/into/금지함수 검사 유지) (b) read-only SHOW 화이트리스트(CREATE TABLE/VIEW·COLUMNS·INDEX·TABLE STATUS·VARIABLES/STATUS; GRANTS/DATABASES/PROCESSLIST 계속 차단; PROCEDURE/FUNCTION→describe_routine) + 대상 `.db` allowlist 강제. **부수 하드닝(§18.8 security 패널 MAJOR)**: write/DDL 노드 defense-in-depth — 데이터수정CTE(`WITH c AS (DELETE…) SELECT`)·중첩 write 거부(pre-existing 잠복). sql_guard SELECT-only 의 **실질 보안 불변식 유지**(보안 회귀 0).
- **corroboration**: structural — 30일 9 distinct conv·14건(UNION 8·Show 5 최대 버킷). 전역 수정 자격 충족.
- **disposition 근거**: Critical(sql_guard 허용범위) → attended 승인. structural corroboration + 코드 file:line confirmed + read-only 안전성(per-branch 검사·write-node defense) → fix-now.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260713T171821-readonly-query-shapes
- **범위 밖(deferred, report-only)**: parse-fail(12, sqlglot dialect/파싱 한계 — L2 에러개선 별도 RC)·multi-statement(4, SQLi 방어 의도 유지)·MSSQL db_id/db_name(3, 메타 enumeration 의도 차단). 임계 돌파 시 별도 audit.
- **라이브 실측 필요분(§정직)**: 코드/테스트/런타임 실증은 "UNION·read-only SHOW 통과 + write/DDL·비-readonly SHOW·multi-statement 차단". "실제 대화에서 동적쿼리·테이블변경 리뷰 마찰 소멸" 은 배포 후 라이브 실측분(미수행) → 다음 audit corroboration 재측정.

## FR-show-create-routine-blocked — fixed:deployed:unverified-live (L2 거부 피드백 + capability gap; 전용 도구 봉인)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트 완료(전체 회귀 1868 PASS·§18.8 패널 MAJOR1·MINOR2 수정) + **배포 완료**(2026-07-13, PR #749 merge main `6841eba2` → deploy-web 무중단 web-a/web-b + ask-worker/insight-worker 재빌드·재생성, 4서비스 GIT_COMMIT=6841eba2; ask-worker 런타임 실증 describe_routine∈TOOL_DEFINITIONS·핸들러·`_safe_ident("x\\")=="x"` 확인, web /healthz git_commit=6841eba2). **라이브 대화 실측 미수행** → `unverified-live`. 다음 audit 에서 동일 시나리오(프로시저 정의 요청) 재현/corroboration 재측정 시 `verified`.
- **fix(요지)**: CHG-20260713T140405-describe-routine-tool / **코드 거주 `feature-0002-agent-core`**(+ narration companion `feature-0003`) / REV-20260713T140405-describe-routine-tool (§18.8 적대 3렌즈 패널 security+backend+qa, MAJOR1[백슬래시 인젝션]+MINOR2[파라미터 교차오염·narration fallback] 전건 수정). 사용자 승인 방식=Option 1(전용 도구+유도), AskUserQuestion 2026-07-13.
- **last_seen**: 2026-07-13 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 (추정) · **conv(마스킹)**: topic "재사용 쿼리의 PK 관리 문제 추가 리뷰" (사용자 명시 보고)
- **symptom_confidence**: high (사용자 명시 보고 `E-USR` + 코드 경로 재현) · **rootcause_confidence**: high (코드 file:line 삼각측량 확정)
- **suspected_layers**: **L2**(거부/에러 피드백에 교정 힌트 부재 — 진짜 결함) + capability gap; L5(sql_guard SELECT/CTE-only)은 의도된 기능(F4, 불변)
- **증상(signal)**: `E-USR` — assistant 가 저장 프로시저 로직(PK 관리) 검토를 위해 `execute_sql` 로 `SHOW CREATE PROCEDURE gunzgame.Game_AccountAttendence` 실행 → sql_guard 가 non-SELECT(`exp.Show`)로 거부(`only SELECT/CTE allowed`). 거부 메시지가 `list_schemas/describe_table` 만 안내하고 루틴 정의 조회 경로 미제시 → assistant 막힘.
- **confirmed_root_cause**: (1) L5 `sql_guard.py:~500` SELECT/CTE-only 가 SHOW 를 거부(의도된 보안 기능·유지). (2) **L2**: `tools.py` 거부 hint 가 루틴 정의 경로 미안내 + LLM 노출 도구가 핵심 4개(execute_sql/describe_table/search_tables/get_sample_rows)뿐이라 루틴 본문 조회 수단 부재(`agent_core.py:3634 _run_tool_defs=TOOL_DEFINITIONS`). 접근 권한 자체는 이미 열림(`information_schema.ROUTINES` always-allow) — 막힌 것은 SHOW CREATE 구문형태. 재발 메커니즘 = `model limit`(거부 피드백 교정 힌트) + capability gap.
- **봉인**: 전용 구조화 도구 `describe_routine`(read-only 카탈로그, `_struct_schema_access_error` allowlist 게이트, RO GRANT backstop) + SHOW CREATE 거부 시 L2 유도 힌트. sql_guard SELECT/CTE-only 불변식 미변경(보안 회귀 0). 부수 근본강화: `_safe_ident` 역슬래시 봉인(구조화 도구 전반 MySQL 리터럴 breakout 차단, §18.8 security 패널).
- **corroboration**: 미측정(단일 대화·사용자 명시 보고). **disposition=fix-now** 근거: capability gap 이 **코드 file:line 정본까지 confirmed(rootcause high)** 인 명백한 구조결함 — 빈도 corroboration 없이 fix-now 자격(저흔적/명백결함 예외). 단 위험등급 Major(신규 LLM 노출 도구·정의 표면화) → 사용자 승인(Option 1) 후 구현.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260713T140405-describe-routine
- **라이브 실측 필요분(§정직)**: 코드/테스트는 "describe_routine 이 정의 반환 + SHOW CREATE 유도 + sql_guard 불변" 증명. "실제 대화에서 프로시저 검토 마찰 소멸" 은 배포 후 동일 시나리오(프로시저 정의 요청) 재현/라이브 대화 실측분(미수행). 배포 후 `fixed:deployed:unverified-live`.

## FR-attachment-update-pasted-not-versioned — fixed:deployed:unverified-live (L1 프롬프트 drift+model limit; 첨부 갱신 전달 선호 + 명명 정합 코드-권위 봉인)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(타깃 36 PASS·§18.8 3렌즈 패널 SEC-1[MINOR] 봉인·나머지 REFUTED) + verify-completion + **배포 완료**(2026-07-14, PR #771 merge main `ee4f8de6` → deploy-web 무중단 롤링 web-a/web-b + ask-worker/insight-worker 재빌드·재생성, **4서비스 GIT_COMMIT=ee4f8de6** running/healthy; ask-worker 런타임 실증 A1 SYSTEM_PROMPT attachment-edit 강화·A2 `_ATTACHMENT_DELIVERY_DIRECTIVE` 주입, web-a 런타임 실증 A3 명명 `report_v2.csv`+v3→`report_v3.csv`(이중접미 방지)·safe_ext; web /healthz=ee4f8de6·mysql_ok·pg_ok). **라이브 대화 실측 미수행** → `unverified-live`. 다음 audit 에서 corroboration(갱신요청 대화의 assistant 버전 생성 비율↑·```sql 붙여넣기 distinct_conv↓) 재측정 → 개선 시 `verified`, 재증가 시 `regressed`.
- **fix(요지)**: CHG-20260713T185846-attach-update-versioned / **코드 거주 primary `feature-0002-agent-core`**(프롬프트) + secondary cross-ref `feature-0003-agent-web-ui`(명명 CHG-20260713T185846-attach-filename-consistency) / REV-20260713T185846-attach-update-versioned. Scope A PLAN-APPROVED(AskUserQuestion 2026-07-13). Major(코어 LLM 경로) → PR/deploy confirm.
- **last_seen**: 2026-07-13 · **seen_count**: 1 · **seen_distinct_conv**: 27 (corroboration structural)
- **modality**: 1:1/그룹 혼합(추정) · **product(마스킹)**: 다수 · **conv(마스킹)**: 갱신요청 34대화(masked hash 다수), 대표 실패 …098d425c(붙여넣기)·…282d7382(기능 출하 前 블록 미materialize 경계 아티팩트)
- **symptom_confidence**: high (사용자 명시 지시 `E-USR` + DB 재현) · **rootcause_confidence**: high (코드+PG core_messages/attachments 집계+전사 삼각측량)
- **suspected_layers**: **L1**(프롬프트 합성 — 첨부 전달 지침이 좁게 게이팅·"brand-new SQL" 예외와 경쟁·코드 상수 안이라 운영자 global row drift 에 취약) + **L4/naming**(materialize 명명이 LLM-의존)
- **증상(signal)**: `E-USR` 명시 지시 + `E-AST` — assistant 가 개선안 제안 후 명시적 갱신요청에도 답변에 쿼리를 붙여넣고(```sql) 다운로드 가능한 새 첨부 버전을 안 만듦.
- **confirmed_root_cause**: attachment-edit 전달 메커니즘(TASK-0275/0286, 2026-06-15/16 출하)은 존재하나 (1) SYSTEM_PROMPT [agent_core.py 154-169] 가 "corrected file back" 으로 좁게 게이팅 + "brand-new SQL → ```sql 무방"(:152)·일반 출력 지침과 경쟁 (2) 지침이 코드 상수 안에 있어 운영자 `agent_memory.websystemprompts` global row(9219자, 지침 포함)가 상수를 통째 대체할 때 강도가 drift (3) 명명이 LLM `filename` 생략 시에만 정합(`_next_version_filename`). 재발경로 = `data/config drift`(코드 상수↔운영자 프롬프트) + `model limit`(약한 계약).
- **corroboration**: **structural** — 90일 text/csv 첨부(user) 보유 88대화 중 명시적 갱신요청 34, 그중 assistant 버전 생성 성공 **3(~9%)** vs ```sql 붙여넣기+버전無 **27(~79%)**. assistant 버전 생성 전 기간 **4건뿐**. 기능 출하(06-15/16) 후에도 실패 지속(7월 이후 7대화) → **F3(이미 고쳐짐) 기각**. 전역 수정 자격 충족.
- **봉인**: (A1) SYSTEM_PROMPT 첨부 전달 섹션 강화(명시 갱신요청→attachment-edit 필수·brand-new SQL 예외 배제·filename 생략·미첨부 시 재첨부 요청). (A2) `_ATTACHMENT_DELIVERY_DIRECTIVE` 코드-권위 주입(compose_system_prompt parts, base 뒤 항상 — global row drift 봉인, injection-guard 선례). (A3, feature-0003) `_next_version_filename` idempotent(이중접미 방지) + materialize 명명 코드-권위(`<stem>_v<n>.<src_ext>`, 확장자 부재 시 kind 기반 안전값 강제[SEC-1]). **보안 회귀 0**(materialize 가드·확장자 차단 불변).
- **disposition 근거**: structural corroboration + 코드 file:line confirmed(high) + 저위험 봉인(가드 불변) → fix-now. Major(코어 LLM 경로) → Scope A 사용자 승인 후 구현.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260713T185846-attach-update-versioned
- **범위 밖(deferred/watch)**: text-inline count cap 초과 대화에서 메타엔 뜨나 content 미주입 시 "MUST" 가 fabrication 유도 가능(QA-2 MINOR, pre-existing·라이브-eval 관찰) · directive/base 섹션 중복(drift-seal floor, 동기유지) · version=chain MAX+1(의도).
- **라이브 실측 필요분(§정직)**: 코드/테스트/패널은 "갱신요청→attachment-edit 유도·명명 정합·확장자 안전" 증명. "실제 대화 붙여넣기 감소·버전 생성 비율 상승" 은 배포 후 라이브 실측분(미수행) → 다음 audit corroboration(갱신요청 34대화 대비 assistant 버전 생성 비율·```sql 붙여넣기 distinct_conv) 재측정 → 개선 시 `verified`, 미개선/재증가 시 `regressed`.

## FR-mssql-crossdb-structured-discovery — fixed:deployed:unverified-live (L4↔L8 catalog 스코프 + L1/L2; 구조화 발견 도구 DB(catalog) 인지 봉인)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(전체 회귀 1980 PASS·§18.8 3렌즈 패널 MAJOR3 전건 수정)·라이브 QA 수정 실증 + **배포 완료**(2026-07-14, PR #790 merge main `b364e964` → `deploy-web` 무중단 롤아웃 web-a/web-b + ask-worker/insight-worker 재빌드·gateway reconcile, soak 통과; **4서비스 GIT_COMMIT=b364e964 healthy**; 배포 이미지 baked 코드 end-state 실증 — describe_columns([Shop],T_ItemInfo)=15컬럼·routine cross-DB([Shop].sys.sql_modules)=1345자). **라이브 대화 실측 미수행** → `unverified-live`. 다음 audit corroboration(MSSQL describe_table 빈-헤더율·search_tables 빈결과율 감소) 재측정 시 `verified`.
- **fix(요지)**: CHG-20260714T161500-mssql-crossdb-structured-discovery / **코드 거주 `feature-0002-agent-core`** / REV-20260714T161500-mssql-crossdb-discovery. 사용자 승인=**완전 DB인지**(AskUserQuestion 2026-07-14).
- **last_seen**: 2026-07-14 · **seen_count**: 1 · **seen_distinct_conv**: 11 (MSSQL 60일 describe_table 빈-헤더 기준)
- **modality**: 1:1 (추정) · **product_id(마스킹)**: P-117 외(114/111/91) · **conv(마스킹)**: `20260714065456-d705e0c7`(topic "쿼리 리뷰 — itemBuyOnce→itemBuyLimit", product 117) 외
- **symptom_confidence**: high (사용자 명시 불만 "다시, 제대로 검토해주세요" + DB/라이브 재현) · **rootcause_confidence**: high (코드+PG 대화집계+라이브 QA 서버+전사 4중 삼각측량)
- **suspected_layers**: **L4↔L8**(구조화 발견 도구가 pin 된 primary DB catalog 하나만 조회 — SQL Server INFORMATION_SCHEMA/sys 는 DB별) + **L1**(schema_name 파라미터가 DB 를 스키마로 오인 유도·프롬프트는 DB 목록 주나 도구가 실행 못 함) + **L2**(빈결과에 다른 DB 안내 없어 give-up)
- **증상(signal)**: `E-USR` 명시 불만 + `E-AST` 장황 무행동 — assistant 가 "실제 DB 참조 리뷰" 요청에 `describe_table(schema_name="Shop", ...)`·`search_tables("Item"/"Buy"/…)` 반복 호출 후 전부 빈결과 → "테이블이 생성되지 않은 것으로 보입니다" 오판·포기 → 첨부 파일만으로 리뷰(사용자 "다시, 제대로 검토해주세요").
- **confirmed_root_cause**: SQL Server `INFORMATION_SCHEMA`/`sys` 카탈로그가 **DB(catalog)별**(MySQL 인스턴스-전역 information_schema 와 비대칭)인데, 구조화 발견 8도구가 pin 된 primary DB(`allow_dbs[0]`, SortOrder 첫 DB — product 117=`_INDY_STATISTIC`)만 조회. 제품 데이터는 수십 개 허용 DB(product 117=`Shop`/`9DRAGONS_ITEM`/`CASHITEMDB`… 30여 개, 전부 allowlist·freeform 3-part 도달 가능)에 분산 → primary 밖 객체 발견 불가. assistant 는 DB명을 `schema_name` 에 투입(관측: describe_table 빈-헤더 schema 인자 대부분 DB명). **라이브 QA(mssql-web-qa) 재현**: primary `_INDY_STATISTIC` 에서 `Shop.dbo.T_ItemInfo`(15컬럼)·`L_Item_Buy_Log`(사용자 작업 참조 테이블) 미발견 → `[Shop].INFORMATION_SCHEMA` 3-part 로 발견. 재발경로 = **capability gap**(도구가 가드가 이미 허용한 DB 에 못 닿음).
- **봉인**: 구조화 발견 도구를 **DB(catalog) 인지**로 — `[db].` 3-part 카탈로그 조회(dialects `_cat(db)`) + `search_tables` 대상 DB 미지정 시 허용 DB 전체 검색(per-DB graceful·CAP 40)·DB-qualified 반환 + `database` 툴 파라미터·schema_name↔DB 재해석·`db.schema` 분해 + 빈결과 L2 교정 힌트 + `_MSSQL_DIALECT_GUIDANCE` 다중 DB 지침. **보안 경계 불변**(유효 허용 DB만·시스템 DB/스키마·agent_memory 3중 차단·`_safe_ident`+allowlist). routine 정의는 `[db].sys.sql_modules`(OBJECT_DEFINITION current-DB 스코프 회피).
- **corroboration**: **structural** — MSSQL 60일 29대화 중 describe_table 빈-헤더 11(~38%)·search_tables 빈결과 9, 오늘까지 지속, 4+ product(91/111/114/117). 전역 수정 자격 충족.
- **disposition 근거**: Critical(§12.3 데이터소스 접근 모델) → attended 사람 승인. structural corroboration + 4중 삼각측량 confirmed(high) + 경계-불변 봉인(freeform 도달범위와 동일) → fix-now.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260714T161500-mssql-crossdb-discovery
- **범위 밖(deferred)**: allowlist display 값 `_safe_ident` 미적용(악성 admin config 한정 방어심화, MINOR) · cross-DB 검색 CAP 40 초과 DB(명시 안내·`database` 지정 유도) · describe_columns 스키마 미상 시 동명-다스키마는 이제 eff_schema 해석으로 단일화(dbo 우선).
- **라이브 실측 필요분(§정직)**: 코드/테스트/라이브 QA 는 "cross-DB describe/search/routine 이 다른 허용 DB 객체를 도달"·"시스템 스키마 차단 유지" 증명. "실제 리뷰 대화에서 발견 성공·give-up 소멸" 은 배포 후 실측분 → 다음 audit corroboration(MSSQL describe_table 빈-헤더율·search_tables 빈결과율 감소) 재측정 → 개선 시 `verified`.

## FR-sysvar-select-denylist-overblock — fixed:deployed:unverified-live (L5 sql_guard @@ denylist 과차단; read-only 시스템변수 SELECT 허용)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(가드+cross-db 175 타깃 PASS·전체 회귀 신규 실패 0[4 실패=baseline test debt, stash 대조 실증]·§18.8 3렌즈 패널 전건 REFUTED) + **배포 완료**(2026-07-14, PR #792 merge main `9dce3caa` → `deploy-web` 무중단 롤아웃 web-a/web-b + ask-worker/insight-worker 재빌드·gateway reconcile, soak 통과; **4서비스 GIT_COMMIT=9dce3caa healthy**; 배포본 ask-worker 런타임 가드 실증 — `SELECT @@lower_case_table_names, @@version`=ALLOW / `SET @@GLOBAL.sql_mode`=DENY / tsql `SELECT @@VERSION`=DENY; web /healthz=9dce3caa·mysql_ok·pg_ok). **라이브 대화 실측 미수행** → `unverified-live`. 다음 audit corroboration(`denylist match: @@` distinct_conv) 재측정 0 유지 시 `verified`.
- **fix(요지)**: CHG-20260714T153113-sysvar-select-guard / **코드 거주 `feature-0002-agent-core`** / REV-20260714T153113-sysvar-select-guard (§18.8 security 적대 서브에이전트 5축 REFUTED + backend/qa 인라인 실증 REFUTED). 사용자 승인=**denylist @@ 제거**(AskUserQuestion 2026-07-14). 선행 CHG-20260713T171821-readonly-query-shapes 의 태세 정합 후속.
- **last_seen**: 2026-07-14 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-119 · **conv(마스킹)**: `20260714050748-e6add7f1`(topic "초기화 쿼리 환경 옵션 검토")
- **symptom_confidence**: high (사용자 명시 지시 "환경 옵션 직접 확인 후 판단" + DB 재현) · **rootcause_confidence**: high (코드 file:line + PG core_messages 차단 로그 + 전사 삼각측량)
- **suspected_layers**: **L5**(sql_guard 보조 denylist `@@` 가 read-only 시스템변수 SELECT 를 과차단 — 실질 write/쓰기 보안과 무관한 정보-클래스 태세 불일치)
- **증상(signal)**: `E-SYS`/`E-USR` — assistant 가 `SELECT @@lower_case_table_names, @@version`(단일 read-only SELECT)로 대소문자 옵션을 직접 확인하려다 `denylist match: @@` 차단 → 재시도(SHOW VARIABLES) 없이 "MySQL 설정 확인 불가"로 OS 기본값 추정 대체 → 사용자의 "환경 옵션 직접 확인" 명시 요구 좌절. 거부 힌트도 "단일 SELECT/CTE 만 허용"이라 오도(해당 쿼리는 단일 SELECT).
- **confirmed_root_cause**: `sql_guard.py:123` MySQL `_DENYLIST_PATTERNS` 의 `re.compile(r"@@")` 가 시스템 변수 읽기 SELECT 를 차단. CHG-20260713T171821 로 read-only `SHOW (GLOBAL) VARIABLES/STATUS`(전체 시스템변수 노출)가 사용자 승인하에 허용된 뒤라 그 **부분집합**인 `SELECT @@x` 만 막는 태세 불일치 잔재. 재발경로 = **guard 가정 오류**(read-only 정보-클래스를 unsafe 로 오분류; FR-readonly-query-shapes-overblock 와 동류 L5).
- **봉인**: MySQL denylist 에서 `@@` 제거. **보안 회귀 0**: (1) 정보노출 델타 0(`SHOW GLOBAL VARIABLES` 가 이미 전량 노출) (2) write 경로 0(`SET @@`·`SET @`=`\bSET\s+@` denylist, `SET GLOBAL x`(무-@@)=shape 게이트 `exp.Set` 거부, `:=`=denylist) (3) forbidden-schema/lock/into/write-node/금지함수는 `find_all` 전수 순회로 `@@` 와 독립(UNION/CTE 분기 무영향) (4) **T-SQL denylist `@@` 유지**(MSSQL 메타 열거 차단 태세 불변).
- **corroboration**: 30일 `denylist match: @@` = **distinct_conv 1**(2026-07-14, 어제 readonly-shapes 배포 후 유일 차단) → **idiosyncratic**(빈도 임계 미달). 단 **근본이 코드 file:line confirmed(high) + 명백한 태세 불일치 + 재발경로 확실**(환경옵션 확인은 초기화/DDL 쿼리 리뷰 상시 단계) → 명백한 구조결함 fix-now. 선행 FR-readonly-query-shapes(structural, 9 conv)의 직접 태세 후속.
- **disposition 근거**: Critical(§12.3 sql_guard 허용범위) → attended 사람 승인(AskUserQuestion). 코드 confirmed + read-only 안전성(정보노출 델타 0·write 경로 0) → fix-now.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260714T153113-sysvar-select-guard
- **배포 note(§정직)**: `deploy-web` soak 가 첫 2회 edge /healthz 단발 프로브 window(web-a/web-b 동시 recreate 후 Caddy 재해석 + cutover blip)에서 롤백 판정 → 3회차 배포 시 실시간 edge 프로브로 9dce3caa 가 soak 내내 200(mysql/pg true) 유지 실증 후 성공(transient 확증, 코드 결함 아님 — 런타임 diff 는 sql_guard 7줄뿐이며 /healthz 는 mysql+pg ping 만 검사, sql_guard 미경유).
- **라이브 실측 필요분(§정직)**: 코드/테스트/런타임 가드 실증은 "`SELECT @@x` 허용 + write/tsql 차단 유지" 증명. "실제 대화에서 환경옵션 확인 마찰 소멸" 은 배포 후 라이브 실측분(미수행) → 다음 audit corroboration(`denylist match: @@` distinct_conv) 재측정 → 0 유지 시 `verified`, 재증가 시 `regressed`.

## FR-partial-evidence-false-verification — fixed:deployed:unverified-live (L2/L1 부분 증거 전수 단정 환각; 절단 미리보기 epistemics + byte-bounded 확장 + grounding 계약)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(신규 `test_partial_evidence_grounding.py` 10 PASS + 전체 회귀 feature-0002+0003 EXIT=0·§18.8 3렌즈 패널[API 세션한도→인라인 자기검증] BLOCKING/MAJOR 0) + **배포 완료**(2026-07-14, PR #793 merge main `244e6bec` → `deploy-web` 무중단 web-a/web-b + ask-worker/insight-worker 재빌드·gateway reconcile, soak 통과; **4서비스 GIT_COMMIT=244e6bec healthy**; ask-worker 런타임 실증 — `expand_char_budget`/`_TOOL_PREVIEW_ROWS_MAX` 7건 로드·`_server_variable_redirect` 0건(Lever D 철회 반영)·SYSTEM_PROMPT `PREVIEW-TRUNCATED`/`SERVER OPTIONS` 2건; web /healthz=244e6bec·mysql_ok·pg_ok). **라이브 대화 실측 미수행** → `unverified-live`. 배포 시점 baseline: 30일 절단 노출 8/49 대화·'환각' 명시 2건(90일). 다음 audit corroboration 재측정 감소 시 `verified`.
- **fix(요지)**: CHG-20260714T063200-partial-evidence-grounding / **코드 거주 `feature-0002-agent-core`** / REV-20260714T063200-partial-evidence-grounding. 출하 lever = A(절단 epistemics)+B(byte-bounded 확장)+C(grounding 계약). PLAN-APPROVED A+B+C+D + PR/배포 인가(AskUserQuestion 2026-07-14). Major(코어 LLM 경로).
- **last_seen**: 2026-07-14 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-119 · **conv(마스킹)**: `20260714050748-e6add7f1`(topic "첨부파일과 실제 DB 비교 검증")
- **symptom_confidence**: high (사용자 명시 불만 "답변 내 환각이 극심합니다" `E-USR` + ground truth 첨부 sha256 대조 재현) · **rootcause_confidence**: high (코드+DB(PG core_messages)+전사+첨부 원본 삼각측량, file:line 확정)
- **suspected_layers**: **L2**(도구 피드백 — 절단 미리보기가 자기교정 정보 미동봉, `_format_result_sets`/execute_sql 안내문) + **L1**(프롬프트 — 부재/전수 단정에 근거 계약 부재) + render 표시 캡 구조
- **증상(signal)**: `E-USR` 명시 불만 + `E-AST` 환각(ground-truth 대조) + `I-FALSE` 거짓 성공 — ① `execute_sql` 183행 결과가 50행 미리보기 절단(gunzlog 전량 미열람)됐는데 "전수 검증"처럼 서술 + 첨부에 **실재하는** `TRUNCATE charactermakinglog`(첨부 141행)를 "누락"으로 오진 ② 정정 턴(사용자 "실제 첨부파일을 확인하며 비교")도 61행/50행 절단으로 동일 반복 ③ `@@lower_case_table_names` 거부 후 문서 기본값(0) 추측 → 실측(1) 반대 결론.
- **confirmed_root_cause**: 재발경로 = `model limit`(비결정 LLM 이 절단·차단이라는 부분 증거를 전수로 오단정). 봉인은 (A) 도구 피드백 정형화 — 절단 안내문에 "미열람 행 단정 금지·재조회 유도·CSV 비가독" epistemic 동봉 (B) 표시 캡 구조 보정 — 소형 결과는 char-budget(12,000자)·행 상한(500) 내 전량 표시해 목록 대조가 미리보기 내 종결(광폭/대형은 기존 캡; 웹 UI step 은 CSV 우선 50행 경로라 무영향) (C) 프롬프트 grounding 계약 — SYSTEM_PROMPT 4규칙(절단 epistemics·부재/전수 근거 계약·첨부↔DB 양측 조회·옵션 실측). ③번 @@ 근본은 병렬 세션 CHG-20260714T153113(FR-sysvar-select-denylist-overblock)이 가드-허용으로 처리 → 애초 계획 Lever D(@@ 거부 힌트)는 dead 경로가 되어 **출하 철회**(정직 — dead code 미출하).
- **corroboration**: 30일 절단 노출(`행 중 50행만 표시`) **8/49 대화(~17%)** structural surface; '환각' 명시 불만은 90일 이 대화가 최초(now 2). 절단 자체는 흔하나(structural) "전수 단정 환각"으로 귀결되는 빈도는 저-흔적(명시 불만 희소) — **근본이 코드 file:line confirmed(high) + 재발경로 확실(대형 목록↔첨부 대조는 쿼리 리뷰 상시 단계) + 저위험 봉인(표시 계약·가드 불변)** → 명백한 구조결함 fix-now.
- **disposition 근거**: Major(코어 LLM 프롬프트·도구 피드백; sql_guard 허용범위·RBAC·PII 불변 → Critical 아님) → attended PLAN-APPROVED. 코드 confirmed + 저위험 봉인 → fix-now.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260714T063200-partial-evidence-grounding
- **동시수정 note(§13.1)**: 본 cycle 중 feature-0002 표준 worktree 를 병렬 세션 2건이 순차 머지(MSSQL cross-DB PR #790/#791, sysvar-guard PR #792) → rebase 2회. sysvar-guard 가 같은 대화 …e6add7f1 의 ③번 @@ 근본을 가드-허용으로 처리해 본 Lever D 를 철회(중복 회피·정직). base-drift 는 union merge + Lever D 재평가로 해소, 상호 회귀 0(내 테스트 + MSSQL 테스트 동시 PASS 실측).
- **라이브 실측 필요분(§정직)**: 코드/테스트/런타임 실증은 "절단 시 자기교정 안내·소형 결과 전량 노출·부재/전수 근거 계약·옵션 실측 유도" 증명. "실제 대화에서 부분증거 전수 단정 환각 소멸" 은 배포 후 라이브 실측분(미수행) → 다음 audit corroboration(절단 노출 대화의 후속 '환각'/'다시 확인' 명시 불만 재발) 재측정 → 감소 시 `verified`, 재증가 시 `regressed`.
- **라이브 실측 결과(직접 재현, 2026-07-14)**: 원 마찰 입력(첨부 2개 #528 `GunZ_Init_Query.sql`·#529 `P_gunzgame_Game_CharacterInsert.sql` — conv …e6add7f1, P-119)을 **배포본**(ask-worker `GIT_COMMIT=244e6bec`)의 실 `agent_core` + 실 gunzgame/gunzlog DB 로 격리 재현(write 전면 차단·turn1·max_steps 12, RO). **✓ 원 증상 소멸**: 재현 답변이 첨부 141행 `TRUNCATE charactermakinglog` 를 "✓ TRUNCATE / OK"(실 DB 12행 대조)로 정확 인식 — 원 대화의 "누락 ❌" 오진 재현 안 됨; gunzlog 절단대상 5개 실 DB 행수 grounding(양측 조회) 실증. **✗ 잔존 false-missing 환각 1건**: 재현 답변이 `gunzlog.LoginEventLog`(첨부 **162행에 활성 `TRUNCATE` 실재**·실 DB BASE TABLE 24행)를 "초기화 쿼리에서 언급되지 않은 누락"으로 오판하고 **이미 존재하는 TRUNCATE 추가**를 필수(Critical)로 권장 — 원 마찰과 **동일 계열**(쿼리에 있는 테이블을 '누락'으로 단정)이 다른 테이블에서 재발. (나머지 `errorlog`·`missionfirstdiscover` 2건은 정확 — 쿼리 부재 & DB 존재 대조 확인.) **판정**: 배포 grounding 수정이 원 증상+양측조회는 봉인했으나 **false-missing 계열(model-limit — 소형 인라인 첨부의 스캔 누락)은 미완봉** → `verified` 미충족, `unverified-live` **유지**. 잔존 결함은 CHG-20260714T210000 ③(첨부 섹션 execute_sql 억제 제거)로 **해소되지 않음**(재현에서 grounding 은 이미 활성 — 억제가 원인 아님) → 별도 triage.
- **잔존 false-missing 후속 봉인(2026-07-15, 사용자 결정 arc)**: (1) **case 프롬프트 레버** CHG-20260714T221500(PR #800 merge `244e6bec`→후속 배포 `ee3424c3`) — grounding 계약에 식별자 case-fold 비교 규칙 추가. **재-재현(배포본 ee3424c3) 결과 = 부분작동**: 모델이 case 를 인지하기 시작(diff 에서 `LoginEventLog`→`logineventlog` 정규화 제안)했으나 여전히 요약표에 '누락' 오기재 + `lower_case_table_names` 미실측 → 프롬프트 레버는 model-limit 을 확률적으로만 완화. (2) 사용자 **"코드로 결정론적 봉인"**(Option C, AskUserQuestion) → **결정론 도구** CHG-20260714T233000-attach-table-coverage(PR #803 merge main `3c8e78df`, deploy-web 4서비스 GIT_COMMIT=3c8e78df, ask-worker `check_table_coverage` in TOOL_DEFINITIONS/_TOOL_HANDLERS 런타임 실증). 첨부↔실DB 테이블 커버리지 대조를 모델 추론→코드(조작-동사 대상 추출·case-fold·주석분리·절단캐비엣·USE귀속)로 이관 → 대소문자만 다른 조작(첨부 CamelCase↔DB 소문자)을 코드가 정확 집계해 false-missing 을 프롬프트 준수 무관하게 봉인. §18.8 적대 2렌즈 패널 REV-20260714T233000(BLOCKING2 B1 절단·B2 주석·MAJOR1 M1 이름등장 오집계 전건 재설계 수정·보안 5벡터 REFUTED), 유닛 12 PASS(seal 포함). **status 는 `unverified-live` 유지** — 도구 로직 결정론은 코드+유닛으로 증명됐으나, (a) 모델이 도구를 호출하는지의 end-to-end 라이브 재-재현은 배포 직후 외부 gunzgame DB(`10.120.8.200`) unreachable(err 2003)로 미완(외부 인프라·코드 무관), (b) `verified` 는 이 원장 정의상 다음 audit corroboration(절단 노출 대화의 '환각'/'다시 확인' 재발 감소)으로 닫는다. 외부 DB 복구 시 동일 입력 재-재현으로 결정론 봉인 end-to-end 실증 가능.

## FR-schema-name-case-drift — fixed:deployed:unverified-live (L8↔L4 allowlist 스키마명 대소문자 drift; 런타임 canonicalize + grounding graph 교정 + write-path 정규화)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(신규 `test_schema_name_case_drift.py` 24 + `test_product_databases_case_normalize.py` 2 + 전체 회귀 2113 passed/2 skipped) + §18.8 3렌즈 적대 패널(security REFUTED·backend/qa MAJOR3 봉인)→재검증 READY-TO-SHIP + verify-completion PASS + **배포 완료**(2026-07-15, PR #823 merge main `b3c8cd34` → web-a/b `deploy-web` + ask/insight-worker `--workers-only` 재빌드·gateway reconcile, **4서비스 GIT_COMMIT=b3c8cd34 running/healthy**; healthz ok/mysql_ok/pg_ok). **배포본 런타임 실증**: ask-worker(baked b3c8cd34)의 `_canonical_schema_name` 이 실 mysql-mv-qa-game(10.103.204.59)에서 `dev_1_1_1_20`→`DEV_1_1_1_20` 해소, datasource 프로브 `dev_1_1_1_20`=0테이블 / `DEV_1_1_1_20`=63테이블(fix 0→63). **대화 end-to-end(배포 agent 가 실 대화에서 canonicalize 호출·마찰 소멸) 미수행** → `unverified-live`. 다음 audit corroboration(대상 4 product describe_table 빈-헤더율·search_tables 빈결과율 감소) 재측정 시 `verified`.
- **fix(요지)**: CHG-20260715T082345-schema-name-case-drift / **코드 거주 primary `feature-0002-agent-core`**(런타임 A) + secondary cross-ref `feature-0003-agent-web-ui`(write-path 정규화 B, CHG-20260715T082345-picker-case-preserve) / REV-20260715T082345-schema-name-case-drift. 사용자 승인=**A + B(ingestion)**(AskUserQuestion 2026-07-15). Critical(§12.3 데이터소스 바인딩) → PR/deploy confirm(전건 승인).
- **last_seen**: 2026-07-15 · **seen_count**: 1 · **seen_distinct_conv**: 1(대상) / **config drift**: 85 case-mismatch 중 MySQL 실패클래스 ~18행·4 product(94/97/110/121)·다수 MySQL datasource
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-97 · **conv(마스킹)**: `20260715070720-c202bcf8`("테이블 구조 정합성 검토")
- **symptom_confidence**: high (사용자 명시 보고 + DB/라이브 재현) · **rootcause_confidence**: high (allowlist DB + metadata graph + 전사 + 라이브 datasource 프로브 4중 삼각측량, file:line 확정)
- **suspected_layers**: **L8↔L4**(datasource allowlist 스키마명이 서버 실제 case 와 drift → 데이터 로드 0행) + 부차 **L2**(빈결과에 case 교정 힌트 부재 — give-up)
- **증상(signal)**: `E-USR`(사용자 보고) + `E-SYS`(빈 결과셋 brute-force) + `E-AST`(장황 무행동·첨부만 리뷰) — `describe_table(schema_name="dev_1_1_1_20", datasource="mysql-mv-qa-game")`·`search_tables`·`INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='dev_1_1_1_20'` 반복 → 전부 0행/빈결과(SHOW TABLES sql_guard 차단은 부차) → "테이블 없음" 오판·give-up.
- **confirmed_root_cause**: allowlist `WebProductDatabases.SchemaName` 소문자 저장(`dev_1_1_1_20`; admin manual/admin.js `.toLowerCase()`), 서버 `DEV_1_1_1_20`(대문자, 63테이블). case-sensitive MySQL(lctn=0, Linux)에서 저장 case literal 쿼리 0행. `_datasource_allow_schemas`(agent_core.py:3153)는 저장 case 보존(의도)이라 코드는 옳으나 데이터가 소문자 → grounding·쿼리 잘못된 case. 이전 FR-nl2sql casing 프롬프트 lever(모델 소문자화 금지)로 미해결(데이터 자체 소문자). 재발경로 = **data/config drift**(allowlist casing ≠ 서버 casing) → 코드 권위선 봉인.
- **corroboration**: **structural** — allowlist 205 중 85 case mismatch; MySQL 실패확정 클래스(소문자 stored → 서버 대/혼합) ~18행·4 product·다수 MySQL datasource. (MSSQL 67 = catalog case-insensitive → 무해 거짓양성 기각.)
- **봉인**: (A, feature-0002) execute_tool 단일 choke 라이브 SCHEMATA case-map canonicalize(MySQL·모호 제외·인용 제거·프로브실패 재시도·conn 캐시) + 라우터 refresh_case + `_correct_allow_schemas_case_via_graph`(run-start grounding·전 datasource·live-fixed skip). (B, feature-0003) admin_products write-path 서버-실제-case 정규화(`list_server_databases`·SSRF 선행·degrade-safe). **보안 회귀 0**: 접근 게이트(소문자 allowlist set) 불변 — canonicalize 는 authorize 된 스키마 표기만 서버 실제값으로 교정(경계 무변).
- **disposition 근거**: structural corroboration + 4중 삼각측량 confirmed(high) + 경계-불변 봉인 → fix-now. Critical → attended 승인.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260715T082345-schema-name-case-drift
- **범위 밖(deferred, §정직)**: 단일-ds freeform grounding(활성 drift 제품 0·구조화 arg-canonicalize 봉인) · admin.js `.toLowerCase()` 자체(프론트·visual verification·write-path 정규화가 상쇄) · datasource-scoped picker 실제 case 표시 · 기존 저장 소문자 18행 백필(admin 별도 — A 런타임 + 재저장 write-path 가 점진 seal) · SCHEMATA 프로브 sql_guard/breaker 미경유(security MINOR, 비-경계).
- **라이브 실측 필요분(§정직)**: 코드/테스트/datasource 프로브는 "canonicalize 로직 정확·게이트 불변·0→63 flip". "실제 대화에서 describe/search 가 DEV_1_1_1_20 63테이블 반환·give-up 소멸" 은 배포 후 원 입력 재현분(미수행) → 다음 audit corroboration 재측정.

## FR-procedure-analysis-result-truncated — fixed:deployed:unverified-live (L2 도구결과 전역 4000자 캡; 대형 backstop 상향)

- **status**: `fixed:deployed:unverified-live` — 코드/테스트(신규 `test_tool_result_cap.py` 6 PASS + feature-0002+0003 전체 회귀 exit=0·FAILED/ERROR 0) + §18.8 3렌즈 적대 패널(backend+security+qa) **SHIP**(BLOCKING/MAJOR 0·4 REFUTED·NIT 3 반영) + verify-completion PASS + **배포 완료**(2026-07-24, PR #935 merge main `64daae28` → `deploy-web` 전체 롤아웃, 워커 `a1982ca3`·web `3264cf9d` 재빌드·gateway reconcile·soak 통과; 4서비스 전부 내 머지 64daae28 포함). **ask-worker 런타임 baked 실증**: `AGENT_TOOL_RESULT_MAX_CHARS=100000` 로드·10530자 프로시저(>4000) `_cap_tool_result` **전문 반환·절단 0**(옛 4000 캡이면 잘렸을 입력)·초대형 150k→100k+`(truncated)` note backstop; web-a/web-b docker healthy + baked healthcheck exit=0. **실제 긴 프로시저 describe_routine 라이브 대화 e2e 는 미수행** → `unverified-live`(런타임 baked 실증이 강하게 시사·`_cap_tool_result` 가 describe_routine 출력의 유일 캡). 다음 audit 에서 동일 시나리오 재현/corroboration(도구결과 절단 노출률) 재측정 시 `verified`.
- **fix(요지)**: CHG-20260724T155534-tool-result-cap-raise / **코드 거주 `feature-0002-agent-core`** / REV-20260724T155534-tool-result-cap-raise (subagent a2af724b865cf671a). 사용자 결정=**전 도구 대형 캡**(AskUserQuestion 2026-07-24 — 3안[정의 도구만 무제한/전 도구 무제한/전 도구 대형 캡] 중 도구별 분기 없는 유한 backstop). Major(§12.3 코어 LLM 루프) → 사용자 scope 결정 후 구현 + PR/deploy confirm(전건 승인).
- **last_seen**: 2026-07-24 · **seen_count**: 1 · **seen_distinct_conv**: 1 (사용자 직접 보고)
- **modality**: (사용자 직접 보고 — 대화 미지정) · **conv(마스킹)**: "타임아웃된 프로시저 분석" 사용자 명시 보고
- **symptom_confidence**: high (사용자 명시 보고 `E-USR`) · **rootcause_confidence**: high (코드 file:line 삼각측량 확정)
- **suspected_layers**: **L2**(도구 결과 → LLM 되먹임 전역 4000자 캡이 `describe_routine` 정의 전문 반환을 재절단 — 진짜 결함)
- **증상(signal)**: `E-USR` — assistant 가 긴 저장 프로시저를 추론·내부 도구로 분석할 때 정의 본문이 4000자에서 잘려 한 번에 탐색 불가 → 나머지를 못 채워 반복 재조회·포기(타임아웃).
- **confirmed_root_cause**: `agent_core.py` 도구 루프 3지점(메인 루프·rederive 루프·PG `core_messages` 저장 copy)의 `tool_result[:4000]` 전역 하드캡. `describe_routine`(FR-show-create-routine-blocked, 정의 본문 **전문 반환**)을 재절단해 도구 목적 무력화. 재발경로 = **capability/design gap**(전역 컨텍스트-보호 캡이 정의-반환 도구 목적과 충돌). **describe_routine 개선의 직접 후속 갭.**
- **봉인**: `shared/config.py` `AGENT_TOOL_RESULT_MAX_CHARS`(env override, 기본 **100000**, `cap<=0`=무제한) + `agent_core._cap_tool_result` 헬퍼(초과 시에만 `... (truncated)` note — FR-partial-evidence epistemic 계약 보존). 3지점 상수화. 저장은 PG `agent_runtime.core_messages.content`=text(무제한, overflow 0). **보안 회귀 0**: sql_guard/RBAC/datasource 바인딩/PII/datamark 경계 불변(순수 context-sizing).
- **corroboration**: 미측정(단일·사용자 명시 보고; 외부 게임 datasource 거주 프로시저라 빈도 실측 불가). **disposition=fix-now** 근거: **명백한 구조결함**(코드 file:line confirmed·rootcause high) + describe_routine 개선 직접 후속 갭 — 빈도 corroboration 없이 fix-now 자격(명백결함 예외). Major → 사용자 scope 결정(AskUserQuestion) 후 구현.
- **수용 tradeoff(MINOR, §18.8 패널 by-design)**: 메시지당 컨텍스트/비용 상한 상향(describe_routine 최대 100k·execute_sql 자체 캡 ~12k). 히스토리 reload 는 메시지 수(50) 윈도우라 대형 결과 누적 시 context_length 도달 가능 — 단 `classify_llm_provider_error` context_length 분류(persist_health=False·글로벌 배너 미오염)로 **graceful degradation** + 유한·env 튜닝 가능. 사용자 결정의 명시 수용 범위. 후속 lever(캡 하향/byte-기준 윈도우)는 필요 시 별도.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260724T155534-tool-result-cap-raise
- **라이브 실측 필요분(§정직)**: 코드/테스트/패널/런타임 baked 실증은 "긴 도구 결과가 캡 미만이면 전문 도달·경계·절단 시 note 보존"을 배포본에서 증명. "실제 대화에서 긴 프로시저 describe_routine 분석 마찰 소멸"은 배포 후 라이브 e2e 분(미수행) → 다음 audit corroboration 재측정 → 유지 시 `verified`, 재발 시 `regressed`.

---

### 메타 (이 원장의 첫 기록)

- 첫 audit: 2026-06-29, `/_dqa:conversation_audit account=mckim conversation="게임 스테이지 성공률 통계"` (dogfood 검증 run). 두 마찰 모두 **report-only** — 스킬의 과적합 가드(단일 대화·Major·idiosyncratic → 자동수정 보류)가 의도대로 작동.
- 문서 정합(STATUS·wiki)은 `/_dqa:doc_sync` 위임. 본 원장은 ledger·LEARNINGS 만 관할.

## FR-brandnew-script-attachment-delivery-gap — fixed:undeployed (L2↔L4 capability gap + **L6 실행경로 소유권**; source-less 첨부 생성 경로 + worker-side 후처리)

- **status**: `fixed:undeployed` — 코드/테스트(신규 27 + 회귀, 전체 2369 PASS) + §18.8 AGENT-TEAM 패널(security MAJOR RBAC + backend MINOR 전부 in-cycle 반영) 완료, 배포 전. 배포 후 원 마찰 대화(…f1c535ec) 동일입력 재현으로 거부 소멸 관측 시 `fixed:deployed:unverified-live` → 다음 audit corroboration 재측정 시 `verified`.
- **source**: `/_dqa:conversation_audit` 라이브 대화 직접 탐색(사용자 명시 scope "스크립트 첨부파일 전달 요청" + "assistant 가 '첨부파일' 항목에 실제 쿼리도 생성하도록 구성"). 명시 지시 promote.
- **last_seen**: 2026-07-24 · **seen_count**: 1 · **seen_distinct_conv**: 1(직접 확정) — corroboration 120일 생성물 파일전달 명시요청 distinct_conv 2(오늘 건 포함)
- **modality**: 1:1 동기 · **conv(마스킹)**: …f1c535ec · **msg**: user 1382/1383(중복 재전송 I-INT), assistant 1384(capability-gap 거부)
- **symptom_confidence**: high (사용자 명시 지시 `E-USR` + 중복 재전송 `I-INT` + assistant 거부 `E-AST` 전사 재현) · **rootcause_confidence**: high (코드 file:line + DB 전사 + 프롬프트 삼각측량)
- **suspected_layers**: **L2↔L4**(capability gap — 첨부 생성 경로가 편집(source 필수)만 존재, brand-new root 첨부 생성 코드 부재) + **L1**(프롬프트가 brand-new SQL 을 inline ```sql 로 유도, 첨부 전달은 편집-only 게이팅)
- **증상(signal)**: `E-USR@…f1c535ec#1382` 명시 지시 + over-spec("답변 본문이 아닌") · `I-INT@…f1c535ec#1383` 중복 재전송(마찰) · `E-AST@…f1c535ec#1384` capability-gap 거부(정직한 거부, 환각 아님) — assistant 가 개선 스크립트를 다운로드 첨부로 못 만들고 우회안(빈 파일 첨부 or 본문 재붙여넣기)만 제시.
- **confirmed_root_cause**: 첨부 생성 경로 `_parse_attachment_edit_blocks`(src_id≤0 skip)·`_materialize_assistant_attachment_edits`(source 첨부 로드·버전체이닝 필수)가 **기존 첨부 편집만** 지원 → source(사용자 첨부 파일)가 없으면(예: `describe_routine` 으로 DB 조회·생성한 스크립트) 첨부 전달 불가. 프롬프트(agent_core.py:158 "brand-new SQL → inline ```sql", `_ATTACHMENT_DELIVERY_DIRECTIVE` 편집-only)가 이를 강화. 재발경로 = **capability gap**(기능 부재).
- **corroboration**: 생성물 파일전달 명시요청 = **idiosyncratic**(distinct_conv 2, 저빈도) 이나 **근본이 코드 file:line 으로 confirmed 된 capability gap** → Phase 7 "명백한 구조결함" fix-now(저빈도=저검출성, 저심각도 아님) + 사용자 명시 지시. (리뷰 요청 "첨부 쿼리 리뷰"류 28대화는 편집 경로로 이미 처리 — 별개.)
- **봉인**: (feature-0003 primary) source-less `attachment-new` 경로 — `_attachment_block_spans` 공통 헬퍼(edit/new 공존 경계) + `_parse_attachment_new_blocks` + `_materialize_assistant_attachment_new`(root 첨부 v1·CreatedByRole=assistant, 편집 경로 보안 가드 전부 공유 + **업로드 RBAC 게이트**) + `_strip_attachment_new_blocks` + ask 배선 + app.js 배지/토스트. (feature-0002 cross-ref) `_ATTACHMENT_NEW_DELIVERY_DIRECTIVE` 코드-권위 주입(AUTH-1a) + base 섹션 + inline 예외. **보안 회귀 0**(확장자 allowlist·크기/개수 캡·account/conv scope·업로드 권한 게이트 추가).
- **fix**: CHG-20260724T181106-brandnew-script-attachment / **primary `feature-0003-agent-web-ui`** + secondary cross-ref `feature-0002-agent-core`(CHG-20260724T181106-attach-new-directive) / REVIEW REV-20260724T181106-brandnew-script-attachment. Major(코어 LLM 경로 + 새 첨부 쓰기 경로) → PLAN-APPROVED(AskUserQuestion 2026-07-24) → PR/deploy 별도 confirm.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260724T181106-brandnew-script-attachment
- **라이브 실측 필요분(§정직)**: 코드/테스트/패널은 "attachment-new 경로 동작·보안 가드·프롬프트 주입"을 증명. "실제 대화에서 사용자가 첨부로 받는지" 는 배포 후 라이브 실측분(미수행) → 배포 후 원 마찰 입력(…f1c535ec, "전체 스크립트 개선안을 첨부파일로") 동일 재현 + 다음 audit corroboration(생성물 파일전달 거부 distinct_conv↓) 재측정 → 개선 시 `verified`, 재증가 시 `regressed`.
- **필요한 사람 액션(1줄)**: PR 생성·deploy confirm(Major — override 불가) → 배포 후 POST-DEPLOY PB-0008 라이브 재현 + doc_sync(STATUS/wiki/릴리즈노트 정합).

### 후속 (2026-07-27) — 1차 배포 후 라이브 미동작 → 후처리 소유권 재배치 (2차 수정, 배포 전)

- **재발 관측**: 1차 수정(cdee8f74, 07-24 배포) 후에도 사용자 보고 "첨부파일 생성 기능을 인지하지 못함"(admin 대화 `기능 추가 파일 요청` = 원 대화 …f1c535ec 재사용).
- **실측 판정(중요 — 1차 수정은 절반만 작동)**: assistant 는 `attachment-new` 블록을 **정상 emit**(프롬프트 lever 작동, msg 1389 파서 well-formed open L18/close L328). 그러나 ① 첨부 0건 ② raw 블록이 답변에 노출. MySQL 전체 assistant **root(v1) 첨부 0건**(편집 chain 12건은 정상 — 모두 짧은 run).
- **2차 RC(삼각측량 high)**: 첨부 후처리(materialize+strip)가 **web `/api/ask` 동기 핸들러에만** 존재. 프로덕션은 worker 모드라 답변 생성 주체는 ask-worker 이고 web 은 long-poll 일 뿐 — 장기 run(msg 1388→1389 **11분**) 중 클라이언트/프록시 연결이 끊기면 web 이 후처리 지점에 미도달. worker 는 raw 메시지만 저장. 재발경로 = **아키텍처 소유권 오배치**(편집·신규 경로 공통 잠재 결함이 장기 run 에서 발현).
- **2차 봉인**: 후처리 소유자를 **ask-worker** 로 이전 — `_postprocess_attachment_blocks`(materialize+strip+step) + `run_agent(defer_terminal_status=)` 로 **KV terminal 을 후처리 뒤로 지연**(독자는 KV terminal 을 보고 답변을 읽으므로 이 순서가 노출을 막는 핵심) + `_finalize_deferred_terminal`(finally 보장) + 기동 시 import 워밍업. web 은 **증거 기반 게이트**(블록 잔존 시에만 self-heal)로 전환.
- **fix**: CHG-20260727T105326-worker-attachment-postprocess / **primary `feature-0002-agent-core`** + cross-ref `feature-0003-agent-web-ui`(CHG-20260727T105326-web-postprocess-gate) / REVIEW REV-20260727T105326-worker-attachment-postprocess. Major. PLAN-APPROVED(2026-07-27).
- **§18.8 2라운드**: BLOCKER 2건(web strip 미게이팅 → 블록 삭제 저장으로 **원 결함보다 악화** / KV terminal 이 run_agent 내부라 순서계약 무효) + MAJOR 2 + MINOR 3 + LOW 2 → 전부 in-cycle 반영, 2nd pass 재검증 CLOSED.
- **검증**: pytest **2384 PASS**(신규 12). **라이브 실측은 배포 후**(원 입력 재현 + assistant root 첨부 ≥1 + 워커 로그) — 그 전까지 `fixed:undeployed` 유지(거짓 done 금지).
- **배포 주의(운영)**: web 이 worker 후처리를 전제 → **워커 포함 전체 스코프 배포**(`make deploy-web`). `--web-only` 금지(혼합 창은 증거 기반 게이트가 self-heal 하지만 순서는 지킨다).
- **교훈(LRN 후보)**: "web 동기 핸들러에 붙인 후처리는 worker 실행 모델에서 **연결 수명에 종속**된다 — 답변 완료 시점을 아는 실행 주체가 후처리를 소유해야 하고, 공개 시점(terminal 신호)은 후처리 뒤여야 한다." 1차 수정이 기능은 맞았으나 **실행 경로 소유권**을 놓쳐 라이브에서 0% 동작한 사례.

## FR-false-truncation-belief — fixed:deployed:verified (L2↔L1 허위 절단 인식; 완전성 신호 대칭 + 루틴 정의 offset 페이징)

- **status**: `fixed:deployed:verified` — **라이브 실측 완료(2026-07-28)**. 아래 '라이브 실측' 절 참조. 코드/테스트 + §18.8 적대 3렌즈 패널 완료 + **배포 완료**(2026-07-27, PR #963 merge main `ef24448c` → `make deploy-web` 전체 스코프 무중단 롤아웃: web-a/web-b 롤링 + insight-worker/ask-worker 재빌드 + gateway reconcile, post-cutover soak 90s 통과; **4서비스 GIT_COMMIT=ef24448c**; web `/healthz`=ef24448c·mysql_ok·pg_ok·insight_heartbeat 2s). **배포본 ask-worker 런타임 실측**: 열린 절단신호 목록 부착 True · "침묵 ≠ 완전" 계약 True · 구 `NO MARKER = COMPLETE` 제거 True · 산술 종료조건(`B == T` + 본문 문구 불신) True · auto 창 산정 **99,000**(= 캡 100k − 여유) · 250,000자 정의 머리말 `[정의 구간 0~99000 / 총 250000자 … 마지막 구간: 아니오]` · 전역 캡 통과 후 `offset=` 안내 생존 True · 60,000자 정의 **미분할** True(조각화 회귀 0) · 셀 절단 stats 분리(row=False/cell=True) True · offset 형식오류 명시 True. **라이브 대화 실측 미수행** → `unverified-live`. 다음 audit corroboration(assistant 의 "도구 한계/프리뷰 한계" 시그니처 distinct_conv, 절단 마커 없는 결과 뒤 불완전 주장) 재측정에서 감소 시 `verified`, 재증가 시 `regressed`.
- **source**: `/_dqa:conversation_audit "문서 내부 조회 프로시저 탐색"` 라이브 대화 직접 탐색 + 사용자 명시 지시("'도구 한계' 이슈 해소, `describe_routine` 프로시저 본문을 글자수 제한 없이 조회").
- **last_seen**: 2026-07-27 · **seen_count**: 1 · **seen_distinct_conv**: 1(대상) / 노출면 6대화(CSV 안내문 부착 대화 전량이 실제 절단 없음)
- **modality**: 1:1 동기 · **conv(마스킹)**: `20260727081131-1dc26d26`(topic "문서 내부 조회 프로시저 탐색") · **msg**: assistant 5611·5619
- **symptom_confidence**: high (사용자 명시 지시 `E-USR` + 전사/집계 재현) · **rootcause_confidence**: high (코드 file:line + PG core_messages 전사 + 90일 집계 삼각측량)
- **suspected_layers**: **L2**(도구 결과 피드백 — CSV 안내문이 절단 트리거 어휘를 상시 부착 + 완전성 확인 신호 부재) ↔ **L1**(SYSTEM_PROMPT PREVIEW-TRUNCATED 트리거가 "미리보기" 단어 단독으로 발동)
- **증상(signal)**: `E-USR`(사용자 명시 지시) + `E-AST`(장황 무행동·자기-축소) — 도구는 **절단을 전혀 하지 않았는데**(describe_routine 11건 전부 전문 반환·execute_sql 181행 전량 렌더) assistant 가 "총 181개 프로시저가 발견되었으나 **도구 프리뷰 한계로 전체 목록 확인이 불가능**합니다"(5619)·"⚠️ 불완전한 결과"(5611)라며 분석을 3건으로 축소.
- **거짓양성 정직 기각(F1, 사용자 지목분)**: 사용자가 지목한 "`describe_routine` 본문 글자수 절단" 은 **라이브에서 미발현** — PG 전 기간 describe_routine 결과 33건 중 `AGENT_TOOL_RESULT_MAX_CHARS`(100k) 초과 0건·`(truncated)` note 0건, 대상 대화 최대 6,898자. 절단이 아니라 **절단 오인**이 마찰의 실체였다. 다만 캡이 유한하다는 구조적 gap 은 실재 → 사용자 결정에 따라 캡 완화가 아닌 **offset 페이징**으로 봉인.
- **confirmed_root_cause**: (1) `tools.py` execute_sql/scratch_sql 이 CSV 저장 시 **절단 여부와 무관하게 항상** "핵심 **미리보기**(수 행)만" 안내문을 부착(주석에 "절단 여부와 무관하게 항상 안내" 명시). (2) `agent_core.py` SYSTEM_PROMPT PREVIEW-TRUNCATED 규칙의 트리거가 `"... 행 중 N행만 표시" / "미리보기"` 라 **단어 단독**으로 발동 → 완전한 결과를 절단으로 오인. (3) 절단 경고는 강한 반면 완전 표시엔 `(N 행)` 뿐이라 **완전성 확인 신호가 없어** 오귀속이 교정되지 않음(비대칭). 재발경로 = `model limit` + 도구 피드백 어휘 설계 결함. **FR-partial-evidence-false-verification(2026-07-14) 수정의 2차효과**(절단 epistemic 계약의 역방향 과발동).
- **corroboration**: 90일 — CSV 안내문 노출 6대화가 **전부 실제 절단 없음**(오발동 노출면), 그중 1대화에서 완전성 오귀속 명시 발현("도구 한계"/"프리뷰 한계" 시그니처 distinct_conv 1). 빈도는 **idiosyncratic**(임계 미달)이나, **근본이 코드 file:line 으로 confirmed(high) + 재발경로 확실**(CSV 저장되는 모든 execute_sql 에 트리거 어휘 상시 부착) + **사용자 명시 지시** → Phase 7 "명백한 구조결함" fix-now.
- **봉인(4 lever, §18.8 패널 반영 후 확정)**: (A1) CSV 안내문에서 트리거 어휘 제거(execute_sql·scratch_sql parity). (A2) 절단이 **없을 때** 완전성 명시 — 강한 절단 경고와 대칭. 단 완전성 단정은 **행·셀·export 3축 모두 미절단일 때만**(패널 BLOCKER: `_format_result_sets` 의 셀 100자 절단이 행 플래그에 미집계돼, 3,179자 프로시저 본문을 103자만 보여준 결과에 "절단되지 않았습니다" 가 붙던 **허위 완전성** — 원 마찰의 정반대 방향) + 셀 절단 시 명시 마커 + 0행 대칭 신호. (A3) SYSTEM_PROMPT — 절단 신호를 **열린 집합**으로 두고 완전성 추론을 **침묵 기반 → 긍정 신호 기반**으로 반전(`NO MARKER = COMPLETE` 폐기; 패널이 절단 통지 19곳 census 로 **미매칭 13곳**을 실증 — 닫힌 화이트리스트는 무통지 절단을 "완전" 으로 단정시킨다) + `CHUNKED ROUTINE DEFINITIONS` 종료조건을 **머리말 산술**로(루틴 본문에 "마지막 구간입니다" 를 심어 조기 종료를 유발하는 위조 실증 → 프레임을 본문보다 앞에 두고 `B == T` 로만 종료). (B) `describe_routine(offset)` 문자 페이징 — 창은 **0=auto(= 캡-여유)** 로 잡아 **캡이 어차피 자를 지점부터만** 쪼개고(구 고정 50k 창은 캡 이하 50k~98k 정의까지 불필요하게 조각내 부분 열람 위험을 새로 만들었다), `room<=0`·캡 무제한·음수는 **윈도잉 비활성**(구 `max(1_000, cap-2_000)` 바닥값은 작은 캡에서 조각 꼬리를 잘라 전량 도달 경로를 사망시켰다). offset 형식오류=명시 오류, 범위초과=0 클램프 + 사실 통지(날조된 열람 이력 금지). **보안 회귀 0**(sql_guard·allowlist·`_safe_ident`·RBAC·PII·datamark 경계 불변 — 적대 security 렌즈가 게이트 순서·SQLi·oracle·secret 5축 실측 반증: 차단 스키마는 DB 쿼리 실행 0회).
- **disposition 근거**: Major(§12.3 — 코어 LLM 프롬프트 + 도구 결과 피드백 경로; sql_guard 허용범위·RBAC·PII 불변이라 Critical 아님) → attended. 사용자 AskUserQuestion(2026-07-27)으로 **scope 결정**: 캡 무제한화 제외, 허위 절단 봉인 + offset 페이징. 검증 방식도 사용자 선택(서브에이전트 패널).
- **fix**: CHG-20260727T175800-false-truncation-belief / **코드 거주 `feature-0002-agent-core`**(+ `shared/config.py` 상수) / REV-20260727T175800-false-truncation-belief(§18.8 적대 3렌즈 — BLOCKER 2 / MAJOR 8 / MINOR 7 / NIT 3 → 12건 in-cycle 반영, 4건 정직 이연, 1건 by-design 수용). 신규 `tests/test_false_truncation_belief.py` **23 PASS**(실전형 본문 전량 복원·셀 절단 억제·본문 위조 방어·창 산정 전수 포함) + 컨테이너 `make test` **2,428건 중 2,422 PASS / 4 FAIL(전부 pre-existing 환경 의존 — `git archive HEAD` 무변경 체크아웃에서 동일 실패 재현으로 확증) / 2 skip** + ruff PASS.
- **수용된 트레이드오프(by-design)**: 초대형 정의 페이징에 회차 예산 없음(4MB 루틴 ≈ 42회 호출, 조각이 `role=tool` 히스토리로 이후 턴 재전송). **전량 도달이 사용자 명시 요구**라 강제 상한은 요구 위반 → auto 창·총 문자수 사전 고지·`AGENT_MAX_STEPS` 유한성·음수 kill-switch 로 완화(선행 FR-procedure-analysis-result-truncated 의 동일 축 수용과 정합).
- **라이브 실측(2026-07-28, 배포본 `8db72012` ⊃ `ef24448c`)** — 재현 대화 `20260728012534-a56ec98e`(product 117 WEB_QA / `mssql-web-qa`, model `claude-haiku-4` — 원 대화와 동일 조건), 3 turn:
  - **① 오귀속 소멸(주 판정축)**: 원 마찰 시그니처(`도구 프리뷰 한계`·`프리뷰 한계`·`미리보기 제한`·`도구 한계`·`전체 목록 확인이 불가`·`불완전한 결과`) **3 turn 전부 0건**. 특히 turn2 는 원 시나리오와 동형인 **대량 완전 결과**(테이블 291개 카운트 + 200행 렌더 목록)를 다뤘는데 도구 한계를 지어내지 않고 "291개 전부 나열됨"으로 정상 종결.
  - **② 기전 확인(도구 결과 실물)**: 배포 후 tool 결과에서 신규 완전성 신호 4건 · 0행 대칭 신호 2건 · 셀 절단 마커 3건 · 신규 CSV 안내문(`핵심 몇 행만 인용`) 9건, **구 트리거 어휘(`핵심 미리보기(수 행)만`) 0건**.
  - **③ §18.8 BLOCKER 수정 실증**: msg 5691 — 20행 **완전** 결과인데 셀 13개가 100자에서 잘리자 완전성 단정이 **억제**되고 `(긴 셀 값 13개가 100자에서 잘렸습니다 — … 당신은 보지 못했습니다)` 마커만 부착. 구 코드였다면 "20행 전부입니다 — 절단되지 않았습니다"가 붙었을 입력이다.
  - **④ 진짜 절단은 그대로 경고**: 루틴 482건 목록(msg 5701·5707)은 미리보기 절단 → 기존 epistemic 경고 유지 + 완전성 미부착. 신호 3축(완전/행절단/셀절단)이 라이브에서 정확히 분기함.
  - **⑤ 원 불만 문구 해소**: 사용자 원문 "프로시저 내용이 일부만 나타나고 나머지 내용이 잘렸습니다"(원 대화 msg 5632) 대상인 `MSP_SELECT_COMMENT_LIST` 를 재조회 → **2,386자 전문 수신, 말미 `END` 까지 완결 확인**, 절단 주장 0건.
  - **⑥ corroboration 추이**: 오귀속 시그니처 distinct_conv **배포 전 1 → 배포 후 0**. **분모 정직 표기**: 배포 후 유기 트래픽이 assistant 메시지 23건/대화 4건으로 작아 통계적 확정력은 제한적 — 판정의 결정적 근거는 ⑥이 아니라 **①(동일 시나리오 직접 재현)과 ②③④(기전 실물 확인)** 이다.
  - **⑦ offset 페이징은 실데이터로 미도달(정직)**: 전 기간 `describe_routine` 정의 결과 35건의 **최대 7,732자 · 평균 2,407자**로 auto 창 99,000자에 한참 못 미쳐 `[정의 구간` 머리말 발생 **0건**. 즉 페이징은 라이브에서 관측될 수 없는 조건이며, 동작 자체는 **배포본 직접 호출**로 검증(250,000자 정의 → `[정의 구간 0~99000 / 총 250000자 … 마지막 구간: 아니오]`, 전역 캡 통과 후 `offset=` 안내 생존, 60,000자 정의 미분할). 사용자 요구("캡 초과 범위도 여러 번 호출로 도달")는 **구조적으로 충족**되었고 발현만 데이터 의존.
- **실측 중 관측된 별개 축(신규 friction 으로 분리 기록)**: turn1 에서 모델이 2부분 명명 `INFORMATION_SCHEMA.ROUTINES` (SQL Server 는 현재 DB 한정)로 0행을 받고 **"프로시저 0개 · 전혀 정의되지 않았습니다"라며 부재를 단정**했다(실제 472 PROC + 10 FUNC = 482). 신규 0행 대칭 신호가 부착돼 있었음에도 막지 못했고, turn2 에서 압박하자 "초기 조회에서 오류를 범했습니다"로 자기정정. **본 변경이 유발한 것이 아님을 baseline 대조로 확인** — 배포 전 구간(06-01~07-27) 0행 tool 결과 89건 중 직후 부재 단정 5건(31개 대화)로 **이미 존재하던 실패 모드**이며, 신규 신호는 그 base rate 를 없애기에 불충분했을 뿐이다. → `FR-false-absence-zero-row-catalog-scope` 로 분리.
- **후속 triage(이 cycle 이 도입하지 않은 pre-existing gap — A3 반전으로 무해화되었으나 emitter 미수정)**: ① `graph_navigate` 노드/관계 60개 절단 무통지(`neighborhood()['truncated']` 미노출) ② MSSQL `ROUTINE_DEFINITION` 4000자 카탈로그 폴백 무표식 ③ comment `[:40]`/`[:30]`·EXPLAIN `StmtText[:80]`·sandbox 샘플 `[:77]` 무통지 ④ 답변 collapse 마커 문구를 `전체 N행 중 M행 표시` 로 정합(프론트는 URL 기준 파싱이라 안전 — 실측) ⑤ 절단 통지 emitter 를 단일 헬퍼(SSOT)로 통합 + 프롬프트↔emitter census 정합 테스트.
- **rc_ids**: RC-1(이 audit) · **batch-id**: B-20260727T175800-false-truncation-belief
- **라이브 실측 필요분(§정직)**: 코드/테스트는 "완전한 결과에 완전성 명시·트리거 어휘 부재·절단 시 기존 경고 유지·offset 으로 전량 복원" 을 증명. **"실제 대화에서 assistant 가 없는 도구 한계를 더는 지어내지 않는지" 는 배포 후 라이브 실측분**(미수행) → 배포 후 동일 입력 재현 + 다음 audit corroboration(assistant 의 "도구 한계/프리뷰 한계" 시그니처 distinct_conv, 절단 마커 없는 tool 결과 뒤 불완전 주장) 재측정 → 감소 시 `verified`, 재증가 시 `regressed`.
- **필요한 사람 액션(1줄)**: PR 생성·deploy confirm(Major — override 불가) → 배포 후 라이브 재현 + `/_dqa:doc_sync`(STATUS·wiki 정합).

## FR-false-absence-zero-row-catalog-scope — fixed:deployed:verified (L1↔L4 0행→부재 단정; 루틴 열거 도구 부재 + 카탈로그 스코프 미인지)

- **status**: `fixed:deployed:verified` — **라이브 재실측 완료(2026-07-28)**. 사용자 지시로 근본 규명 후 수정, §18.8 적대 3렌즈 **2라운드** 통과, PR #991 merge main `21b67ade` → `make deploy-web` 전체 스코프(4서비스 GIT_COMMIT=21b67ade, soak 통과, `/healthz` ok). 사용자 **범위 결정: RC-B 포함**(보안 경계 재검토).
- **라이브 재실측(재현 대화 `20260728031510-16927f9b`, product 117 / `claude-haiku-4` — 마찰 대화와 동일 조건, 동일 질문)**:
  - **수정 전**: "masangsoftweb 에는 저장 프로시저가 **전혀 정의되지 않았습니다** / 전체 프로시저 개수 **0개**" (ground truth 482건).
  - **수정 후**: "SELECT 키워드를 포함하는 프로시저: **총 421개**" + 원 대화가 찾았던 **`MSP_SELECT_BOARD_CONTENT`** 를 정의 본문까지 제시(원 사용자 목표 달성). **오귀속·부재 단정 시그니처 각 0건.**
  - **신규 도구 실사용 확인**: `search_routines` 가 루프에서 호출됨(msg 5775~5782) — 빈 결과에는 "이 한 번의 빈 결과로 '루틴이 없다' 고 단정하지 마세요" 부착.
  - **실패 고지 실전 발동(§18.8 MAJOR 수정의 라이브 실증)**: 실행 중 MSSQL 연결이 끊기자(`Not connected to any MS SQL server`) 도구가 "⚠ 다음 DB 는 **조회하지 못했습니다** … 존재/부재는 **미확인**입니다 — 단정하지 마세요. (허용 DB 전부가 조회 실패라 이 검색은 아무것도 확인하지 못했습니다)" 를 냈다. 구 코드였다면 "검색 결과가 없습니다" 로 위장돼 정확히 이 FR 의 오판을 재생산했을 상황이다. 그 run 의 최종 답변도 부재를 지어내지 않고 "탐색을 충분히 진행하지 못했다" 고 정직 보고(`20260728031608-b7832c89`).
  - **배포본 런타임 실측**: `search_routines` 노출 True · 프롬프트 `CATALOG VIEWS ARE PER-DATABASE` True · `sys` 경계 SSOT(대체 관용구 포함) True · `sys.objects`/`sys.partitions` ALLOW · `sys.databases`/`master.sys.objects`/**별칭 그림자**(`FROM sys.objects AS sys CROSS APPLY sys.fn_get_sql(...)`) BLOCK · 사용자 UDF `dbo.dm_calc_total()` ALLOW(과차단 없음).
- **source**: `/_dqa:conversation_audit` FR-false-truncation-belief 사후 라이브 실측(재현 대화 `20260728012534-a56ec98e` turn1).
- **last_seen**: 2026-07-28 · **seen_count**: 1(실측) · **seen_distinct_conv**: 1 / 배포 전 base rate 5건(31개 대화)
- **modality**: 1:1 동기 · **symptom_confidence**: high(실측 재현 + ground truth 대조) · **rootcause_confidence**: medium(2부분 명명 가설은 강하나 코드 fix 미검증)
- **suspected_layers**: **L1**(프롬프트 — 0행을 부재 증거로 승격) + **L2**(도구 피드백이 dialect 스코프 함정을 알려주지 않음)
- **증상(signal)**: `I-FALSE`(허위 부재 단정). SQL Server 에서 `INFORMATION_SCHEMA.ROUTINES` 는 **연결의 현재 DB 한정**인데 모델이 2부분 명명으로 조회 → 0행 → **"masangsoftweb 에는 저장 프로시저가 전혀 정의되지 않았습니다 / 전체 프로시저 개수 0개"** 단정. **ground truth 는 472 PROCEDURE + 10 FUNCTION = 482건**(3부분 명명 `masangsoftweb.INFORMATION_SCHEMA.ROUTINES` 로 확인). 사용자가 되물으니 자기정정.
- **오귀인 방지(중요)**: 이 실패는 **FR-false-truncation-belief 수정이 만든 것이 아니다**. 배포 전 구간(2026-06-01~07-27) 0행 tool 결과 **89건 중 직후 부재 단정 5건 / 31개 대화**로 이미 존재하던 base rate 이며, 신규 0행 대칭 신호(`'없다/누락됐다' 고 단정하기 전에 …확인하세요`)는 그것을 **없애지 못했을 뿐**이다.
- **후보 lever(미채택 — 사람 결정 필요)**: (a) 0행 안내문을 "0행 ≠ 데이터 없음" 우선 프레이밍으로 강화(현 문구는 "이 조건에 맞는 행이 없습니다"가 앞서 완전성 신호로 오독될 여지). (b) dialect 인지 힌트 — SQL Server 에서 메타뷰 2부분 명명 0행 시 "`db.INFORMATION_SCHEMA.X` 3부분 명명으로 교차확인" 안내(`describe_routine` 은 이미 허용 DB 목록을 안내하나 `execute_sql` 0행 경로엔 없음). (c) SYSTEM_PROMPT §ABSENCE 에 "메타뷰 0행은 카탈로그 스코프를 먼저 의심" 규칙 추가.
- **suspected_layers 정정(규명 후)**: 표층은 L1 이지만 실체는 **L4(도구 능력 공백)** 이다 — 루틴을 *열거*하는 구조화 도구가 없어 모델이 카탈로그 SQL 을 손으로 써야 했고, MSSQL 정본 경로(`sys.*`)마저 가드가 닫아 **구조적으로 항상 0행인 쿼리**로 몰렸다.
- **ground truth**: product 117 의 접근 DB 를 `(SortOrder, SchemaName)` 정렬한 첫 항목이 `_INDY_STATISTIC`(SortOrder 10) → 연결은 거기 auto-pin. `masangsoftweb` 은 28개 허용 DB 중 하나라, 그 DB 의 메타뷰 `ROUTINE_CATALOG` 는 절대 `masangsoftweb` 이 될 수 없다. 실제 루틴 수 **472 PROCEDURE + 10 FUNCTION**.
- **계보(중요)**: 프로젝트가 **이미 봉인한 실패 모드의 누락된 형제**다 — `FR-mssql-crossdb-structured-discovery`(2026-07-14)가 "MSSQL 카탈로그 뷰는 DB별 → pin 된 DB만 보고 없음으로 오판"을 **구조화 도구에 한해** 고쳤는데, 루틴 열거는 도구 자체가 없어 freeform 으로 샜다.
- **봉인(5 lever)**: (A) `search_routines` 신설 — 허용 DB 전체 sweep + **정의 본문 검색** + CLR/확장 타입 포함 + keyword 선택(열거) + per-DB 실패·상한 포화 **명시 고지**. (B) freeform `sys` 전면차단 → **DB 스코프 카탈로그 뷰 화이트리스트 21종**(서버 스코프·`synonyms`·`guest`/`db_*`·메타데이터 함수는 계속 차단). (C) MSSQL 프롬프트 `CATALOG VIEWS ARE PER-DATABASE`(2-part + 다른 카탈로그 필터 = 절대 0행, 빈 카탈로그 결과는 스코프의 증거이지 존재의 증거 아님) + `sys` 경계 문구를 화이트리스트 SSOT 로 생성. (D) `_catalog_scope_hint` — **행 수 무관·AST 기반**, 3-part 엔 미부착, 진단 시 완전성 단정 억제. (E) 0행 문구 부재-부정 우선 + 프롬프트 규칙을 메타데이터 맥락으로 한정(정당한 업무 0행 과교정 방지).
- **fix**: CHG-20260728T114459-false-absence-catalog-scope / **코드 거주 `feature-0002-agent-core`**(+ feature-0003 step 서술 1곳) / REV-20260728T114459-false-absence-catalog-scope.
- **후속 triage 진행(별칭 그림자 함수 우회, 2026-07-28)**: 패널이 pre-existing 으로 분리했던 항목을 사용자 지시로 수정 → CHG/REV-20260728T133431-alias-shadowed-function-namespace. **증명 가능한 축 봉인**(table-source 위치 면제 금지 = UDT 메서드가 문법적으로 불가능한 자리의 행집합 유출 / 4·5-part linked server 와 그 경유 M1·`agent_memory` / `Paren`·미지 노드 무판정 통과) + **존재 열거 oracle 차단**(모호 경로의 서버 오류 원문 미노출 — `Msg 916`↔`4121` 차이로 allowlist 밖 객체를 전제조건 없이 열거할 수 있었다). **미해결 잔여**: 스칼라 위치 `alias.col.method()` ↔ `db.schema.func()` 모호성은 SQL 텍스트만으로 해소 불가하고, 면제 제거는 re-gate(7차)가 MAJOR 로 못박은 UDT 메서드 지원 계약을 깬다(CLR 메서드명은 열거 원리 불가). **권위적 경계는 per-DB USER/GRANT** — `bin/datasource-mssql-ro-bootstrap.sql` 이 단일 TARGET_DB 에만 USER 를 만들고 `db_datareader` 를 제거하며 허용 스키마 SELECT-only 로 부여하므로 미허용 DB 에는 principal 자체가 없다. **의존성**: 이 결론은 부트스트랩 준수를 전제 — 수동 `db_datareader`/전역 USER 부여 시 잔여가 실착취로 승격된다(datasource 추가 시 반드시 해당 스크립트로 프로비저닝).
- **잔여 확정 — 서버 이름 해석으로 닫힘(라이브 실증 2026-07-28)**: 스칼라 위치 모호성을 "미해결 잔여" 로 남겼으나, QA SQL Server **2017(14.0.3238.1) Web Edition** 에 직접 프로브해 **착취 불가**로 확정했다. ① 별칭=미존재 DB명 → `Msg 207 Invalid column name 'dbo'` ② 별칭=**실존** DB명(`Shop`/`Web_SR`) → `Msg 207` **①과 완전히 동일** ③ 별칭 없음(동일 3-part) → `Msg 4121 Cannot find … function`. 즉 SQL Server 는 `alias.col.method()` 를 **별칭 우선(컬럼)** 으로 해석하므로 테이블을 DB 명으로 별칭 지어 cross-DB 함수를 부를 수 없고, 오류 문구가 **DB 존재 여부에 불변**이라 열거 oracle 도 성립하지 않는다. → 가드의 스칼라 면제는 서버 동작과 **의미적으로 일치**하며, per-DB GRANT 는 유일 방어선이 아니라 defense-in-depth 로 내려간다. **적대 검증 1R BLOCKER-1 은 게이트 레벨 ALLOW 만 근거로 한 판정이었고(서버 미검증), 이 실증이 그 전제를 반증한다.**
- **부수 철회**: 위 oracle 을 막으려 넣은 서버 오류 원문 은폐(`_sql_error_message`)는 근거를 잃어 **철회**했다 — 얻는 것 없이 `Invalid column name 'dbo'` 같은 자기교정 정보만 가리는 순손실이었다. APPLY(table-source)·4/5-part·`Paren`/미지 노드 봉인은 그대로 유효(그 위치들은 컬럼 해석이 문법적으로 불가해 서버가 반드시 함수로 해석).
- **필요한 사람 액션(1줄)**: PR 생성·deploy confirm(Major + 보안 경계 완화 — override 불가) → 배포 후 동일 질문으로 라이브 재실측.

## FR-model-pick-lost-on-early-cid — fixed:deployed:verified (L7↔L6 조기 cid 전환이 모델 선택 귀속을 유실 → 서버 기본값 강등)

- **status**: `fixed:deployed:verified` (2026-07-29 11:30 전이) — FE 귀속 승계(A) + 표시-집행 정합
  감지(C) 출하 → PR #1032 머지(main `bc920534`) → 배포(web `StartedAt` 11:08:44 KST, edge
  `/healthz` `git_commit=36618965`, 서빙 `app.js?v=7529ce4ce347` 에 4 심볼 baked) → **PB-0008 라이브
  실증 PASS**. 판정은 화면이 아니라 이 항목이 못박은 정본으로 냈다 — `llm_usage` id 69372
  `model=claude-sonnet-4` / `resolved_model=claude-sonnet-4-chat`(강등 0) + `kv model:<acct>` 행
  **생성**(값 `claude-sonnet-4`). 사용자 시나리오 [새 대화 → sonnet 선택 → 첨부 업로드 → 전송] 전
  구간을 3중 계측(요청 본문·경보 채널·상태 스냅샷)으로 재현했고, 결함 전제 상태(`_modelPickedForConvId=""`)
  까지 실제로 통과한 뒤 승계가 성립함을 관측했다(= 경로를 우회한 통과가 아님).
  **잔여(이월)**: 관측 표본 corroboration(30일 non-default 선택 대화의 첫 요청 오전송 3/5) 재측정은
  배포 직후 표본 부재 → 다음 audit. 재증가 시 `regressed` 로 되돌린다.
  근거: `unit/feature-0003-agent-web-ui/docs/test-runs.d/20260729T1130-model-pick-postdeploy.md` ·
  REV-20260729T113000-model-pick-postdeploy.
- **사용자 재보고 귀속(2026-07-29)**: 완료 보고 후 사용자가 "이전과 동일하게 폴백"을 재보고했으나,
  그 재현 대화(…2211841a)의 첫 전송은 **10:33:48** 로 배포 **11:08:44** 보다 35분 앞섰고 배포 후
  신규 대화·첨부는 **0건**이었다 → 구자산 세션 경험(수정 실패 아님). 오히려 같은 오전 대조군
  (…a8b43197 10:30 첨부 5건 = sonnet 정상 / …2211841a 10:33 첨부 1건 = haiku 강등)이 분기점을
  "첨부 유무"가 아니라 **선택→첨부 순서**로 재확인해 아래 root cause 의 경로 특정을 강화한다.
  교훈: 재보고는 **배포 시각과 대조한 뒤** 해석한다(`docs/LEARNINGS.md`).
- **source**: 사용자 명시 호출 `/_dqa:conversation_audit` (2026-07-28) — 지정 대화 2건 + turn 중 추가 관측
  진술("sonnet 모델로 요청한 즉시 haiku 모델로 폴백").
- **last_seen**: 2026-07-28 · **seen_count**: 1 · **seen_distinct_conv**: 4 (지정 2 + 인접 재시도 1 + 사용자 재현 1)
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-117 · **account(마스킹)**: A-10 ·
  **conv(마스킹)**: …f70af5fc(`쿼리 리뷰 : 게시글 기능`) · …d887c4c9(`쿼리 리뷰 : 홈페이지 공지 기능 추가`) ·
  …f434dc11(인접 재시도·대조군) · …18be31a2(사용자 재현)
- **symptom_confidence**: high (사용자 명시 보고 + 라이브 데이터 재현) · **rootcause_confidence**: high
  (코드 file:line + PG 3테이블 + 전사 삼각측량, 대조군으로 경로 분리 확정)
- **suspected_layers**: **L7↔L6** — L7(FE 상태 전환에서 선택 귀속 미이관)이 근본, L6(모델 결정)에서 발현.
  **L6 라우팅 폴백은 아니다**(초기 가설 `refuted` — 아래).
- **증상(signal)**: `E-USR` 명시 불만 + `I-SIL` 재시작 이탈 — 같은 요청을 4개 대화에서 반복 재시도
  (18:32 / 18:37 / 18:39 / 18:55), 중간 sonnet run 은 사용자 취소로 종료. 사용자 표현 "조용히 haiku 로
  변경되며 나머지 작업을 진행".
- **거짓양성 기각(`refuted`)**: ① **LLM 라우팅 폴백 가설 기각** — `llm_usage.model`(요청 alias)이 이미
  `claude-haiku-4` 였다. 폴백이면 `model=sonnet` / `resolved_model=haiku` 로 갈라졌을 것이며, 실제
  `resolved_model` 은 `claude-haiku-4-chat`(정상 해소)이다. 선행 `FR-edge-fallback-conversation-context-loss`
  의 재발이 아니다. ② **sonnet run 취소(`ask_jobs.status=error`, "요청이 취소되었습니다")는 별개 결함이
  아님** — `cancel_requested` KV 가 찍힌 사용자 중단이며, haiku 로 가는 것을 보고 끊은 **결과**다.
- **confirmed_root_cause**: 모델 선택 귀속(`_modelPickedForConvId`)은 선택 시점의 `activeConversationId`
  로 잡혀 새 대화(pending)에서는 빈 문자열이다. **첨부 업로드**가 early-cid 를 발급해 활성 대화를 실 cid
  로 전환(`app.js` lazy→real)하면서 이 귀속을 승계하지 않아, 전송 시 `_shouldSendModelField()` 가 false
  → `askBody.model` 누락 → 서버(`conversations.py` ask)가 `API_DEFAULT_MODEL`(haiku)로 채우고
  `model_explicit=False` 라 KV 저장도 skip. 화면 선택기는 고른 모델을 계속 표시 → **완전한 무음 강등**.
  덧붙여 첫 전송 후 hydration 이 저장값 부재로 선택을 비워 **선택기까지 기본값으로 되돌아간다**(사용자가
  "즉시 폴백"을 화면에서 본 기전). 재발 메커니즘 = **ux contract**(상태 전환 시 귀속 이관 누락).
  결정적 지문: 재현 대화에 `kv model:<acct>` 행 **부재**(미동봉) vs `reasoning_level` 정상 저장(항상
  전송되는 비대칭). 대조군 …f434dc11 — 대화 확정 후 재선택한 2차 요청은 정상 sonnet 전송 + KV 저장.
- **corroboration**: 최근 30일, non-default 모델 선택이 KV 로 확증된 대화 5건 중 **3건이 첫 요청을 사용자
  선택과 다른 모델로 전송**(선택 저장이 첫 job 이후 = 유실 후 재선택 패턴) → **structural**. 초기에 쓴
  거친 프록시("대화 생성↔첫 메시지 gap" 별 model KV 부재율 93% vs 86%)는 **판별력 없음으로 폐기** —
  기본값 실행도 KV 행이 남지 않아 미동봉과 구분되지 않는다(측정 함정 기록).
- **disposition 근거**: Major(§12.3 — 모델 라우팅 입력 + haiku→sonnet 실행 증가라는 외부 비용 방향) →
  attended human-decision. 사용자가 AskUserQuestion 으로 봉인 범위 **A+C** 명시 선택(2026-07-28) →
  PLAN-APPROVED 후 구현·검증.
- **fix**: `CHG-20260728T191126-model-pick-early-cid` / **코드 거주 `feature-0003-agent-web-ui`**
  (`src/static/app.js` — `_adoptComposerModelPickToConv` 승계 2지점 + `_modelSelectionSilentlyDropped`
  표면화) / `REV-20260728T191126-model-pick-early-cid` (§18.8 `contract` 매칭 backend+security+qa
  인라인 적대검증 — S1~S3·C1~C5·Q1~Q2 전건 REFUTED/해소, BLOCKING 0). 서버 무변경.
  테스트 `verify_model_persist.mjs` 32 → **49 PASS**(E/W/S9~S11 신설) · 서버측 pytest 57건 rc=0.
- **rc_ids**: RC-1 · **batch-id**: B-20260728T191126-model-pick-early-cid
- **라이브 실측(2026-07-29 이행 완료)**: 코드/테스트는 "고른 모델이 요청에 실린다 + 미동봉이면
  표면화된다"까지만 증명했고, "실제 대화가 고른 모델로 **실행**됨"은 배포 후에만 반증 가능한 잔여였다.
  → 배포본에서 PB-0008 이행 **PASS**(`REV-20260729T113000-model-pick-postdeploy`). 정본 판정:
  `llm_usage` id 69372 `model=claude-sonnet-4`/`resolved_model=claude-sonnet-4-chat` + `kv model:1` 행
  생성. **잔여는 corroboration 추세 재측정 1건**(30일 오전송 3/5 → 다음 audit; 재증가 시 `regressed`).
- **kv 지문 판독(3분기 — 오독 방지)**: 위 root cause 의 "행 부재" 서술을 정밀화한다. 서버는
  `model_explicit` 일 때만 저장하되 **값이 세션 기본값과 같으면 빈 값으로 지운다**(기본값 이탈만 저장,
  적대 리뷰 C2). 따라서 `kv model:<acct>` 는 — **행 부재 = 미동봉**(이번 결함의 지문) / **빈 값 행 =
  기본값과 같은 모델의 명시 동봉** / **값 있는 행 = 비-기본 모델 명시 동봉**. 재현 대화 …2211841a 에
  두 단계가 모두 남아 있다(10:33 첫 전송 시 행 부재 → 10:59:02 빈 값 행 = hydration 이 선택기를 기본값
  으로 되돌린 뒤 이어 보낸 전송). 빈 값 행을 미동봉으로 읽으면 향후 같은 류를 오진한다.
- **범위 밖(인지)**: 기본값(`API_DEFAULT_MODEL`) 자체와 "'+ 새 대화'는 haiku 로 시작" 정책은 불변 —
  사용자 명시 선택만 보존한다. 그룹 대화의 계정별 모델 스코프도 무변경.

## FR-dataplane-conn-stale-no-reconnect — fixed:deployed:unverified-live (L4↔L8 데이터플레인 연결 재사용에 liveness·재연결 부재)

- **status**: `fixed:deployed:unverified-live` — PR #1036 → main `d2b0e317`, 전체 롤아웃 `50c5a854`
  (web-a/web-b 롤링 + insight-worker/ask-worker + gateway reconcile, soak 통과). 4개 서빙 컨테이너
  전부에서 봉인 심볼·설정 적재 확인.
  **메커니즘은 배포본에서 라이브 실증됨** — 사고와 같은 datasource(`mssql-web-qa`)로 같은 유휴
  (232초)를 재현: 대조(봉인 미경유 원 conn 직접 사용) `DBPROCESS is dead or not enabled` 로 사망,
  봉인 경로는 `dataplane_conn_reconnected` 로그와 함께 자동 재연결되어 쿼리 성공(`재연결됨=True`).
  `verified` 로 닫지 않는 이유(§C5): 배포 후 **실사용자 대화**에 대한 corroboration 재측정
  (끊김 시그니처 distinct_conv 감소)이 아직 남았다 — 다음 audit 이 재측정해 전이시킨다.
  **재진단 금지**: 근본은 확정·봉인됐다. 다음 호출은 corroboration 수치만 갱신할 것.
- **source**: 사용자 명시 호출 — "쿼리 리뷰 : WEB_QA / DB와 연결하지 못하는 이슈".
- **last_seen**: 2026-07-29 · **seen_count**: 3 · **seen_distinct_conv**: 3 (60일)
- **symptom_confidence**: high (사용자 직접 보고 + 전사에 오류 문자열 명시)
  · **rootcause_confidence**: high (코드 + 라이브 재현 실험 + 전사 삼각측량, 대조군 확보)
- **suspected_layers**: **L4↔L8** — 데이터플레인 연결 수명주기(로드 경로)와 datasource/중계장비
  절단 정책(엔진 설정)의 경계. L2 2차 증상(오도하는 거부 피드백) 동반.
- **증상(signal)**: `E-SYS` 도구 실행 오류 반복(허용 DB 28개 전부 `Not connected to any MS SQL
  server`) → `I-FALSE` 답변이 실 DB 대조 없는 정적 분석으로 강등(assistant 가 스스로 "🔴 라이브
  검증 필요" 로 정직 표기). 2차: 부하게이트가 "쿼리를 좁히라" 로 오도해 모델이 ping 쿼리까지 축소.
- **confirmed_root_cause(요지)**: 데이터플레인 연결은 run 시작에 1회 수립되어 그 run 의 모든 도구
  호출에 재사용되는데(`agent_core.run_agent` 단일 경로 / `tools._DatasourceRouter.conn_for` 라우터
  경로), 사용 직전 liveness 검사도 재연결도 없다. 연결이 죽는 두 경로:
  (a) **유휴 사망** — 첫 도구까지 LLM 추론이 수 분(실측 232초. `agent_runtime.steps` 로 run 시작
      10:30:10.7 → 첫 도구 10:34:03.8). 라이브 실험: 대상 datasource 는 60~120초 유휴에 절단
      (t=60 ALIVE → t=120 `DBPROCESS is dead` → t=180 `Not connected…`), 대조 datasource 는 생존.
  (b) **in-run 사망** — 쿼리 타임아웃이 세션을 죽인 뒤(FreeTDS 20003→20047) 4초 만에 온 다음
      도구부터 전부 실패(2026-07-28 관측). 같은 대화의 **다음 run**(새 연결)은 완전 정상.
  죽은 뒤엔 남은 도구 전부가 드라이버 문구로 실패해 사용자 요청이 통째로 무너진다.
- **거짓양성 기각(`refuted`)**: ① `agent_runtime.datasource_health` 는 해당 datasource 를
  **healthy** 로 표시 — 백그라운드 probe 가 매번 **새 연결**을 열기 때문(운영 신호와 실사용 괴리).
  ② 같은 분에 타 제품 대화는 정상 동작(추론 지연 12초) → 전면 장애 반증. ③ TCP 도달·현재 연결
  모두 정상 → 인프라 다운·자격증명 문제 아님. ④ 제품 접근목록은 사고 시각 전후 불변(2026-06-18
  생성) → 설정 변경 기인 아님.
- **corroboration**: structural — 60일 3 대화·3일에 오류 문자열 관측(적은 절대수). 메커니즘 축은
  30일 146 run 중 첫 도구까지 120초 초과 3건(2.1%)이며, 첨부가 큰 쿼리 리뷰 워크로드에 집중된다.
  빈도는 낮으나 Phase 7.4 "명백한 구조결함" 분기 충족(삼각측량 confirmed + 재발경로 infra drift
  + 코드 정본 확정) → 국소-봉인 fix-now.
- **재발경로**: `infra capacity`(중계장비/서버 유휴 절단) + 모델 지연 drift — 둘 다 우리가 통제
  불가 → **코드가 권위선**(재사용 choke-point 의 liveness 계약).
- **fix**: TASK-20260729T110000-dataplane-conn-liveness / `feature-0002-agent-core`
  `CHG-20260729T110000-dataplane-conn-liveness`. Major(코어 데이터플레인 경로) — 사람 승인 완료.
  적대 리뷰 §18.8 3렌즈(codex) CONCERN → 지적 3건 반영(연결 객체 동일성 격리·재연결 후 쿼리 상한
  재적용·end-to-end 테스트), 1건 이월(아래). 테스트 25건 신규.
- **동반 수정**: `_search_tables_mssql` 의 per-DB 실패 삼킴 제거 — 사고 당시 **아무것도 조회하지
  못한 상태를 "검색 결과가 없습니다" 로 위장**해 모델이 테이블 부재를 전제로 리뷰를 진행했다.
  형제 `_search_routines_mssql` 이 이미 받은 하드닝의 대칭 적용(`FR-false-absence-zero-row-catalog-scope`
  와 같은 류가 자매 함수에 남아 있던 것).
- **필요한 사람 액션(1줄)**: 없음 — 배포·라이브 실증 완료. (선택) 대형 첨부 쿼리 리뷰를 실제
  대화에서 1건 돌려 사용자 표면에서도 확인.

## FR-insight-worker-conn-stale — deferred (같은 근본의 배경 스캔 판, 별 cycle)

- **status**: `deferred` — `FR-dataplane-conn-stale-no-reconnect` 의 적대 리뷰(§18.8 QA MAJOR)가
  드러낸 자매 노출면. 사실로 확인했고 **미검증을 완료로 보고하지 않기 위해** 원장에 남긴다.
- **last_seen**: 2026-07-29(코드 독해 기준) · **seen_count**: 0 (라이브 마찰 미관측)
- **rootcause_confidence**: med — 코드 경로는 확정(`modules/insight.py` 가 `connect_with_retry` 로
  만든 `_ds_conn` 을 스캔 내내 직접 재사용, `execute_tool` liveness choke-point 미경유),
  실제 발생 빈도·영향은 미측정.
- **suspected_layers**: L4↔L8 (동일)
- **왜 이번 batch 에 넣지 않았나**: 소비자·실패면·복구정책이 다르다(배경 스캔은 실패를 degraded 로
  기록하고 다음 cadence 에 재시도 — 사용자 요청이 즉시 무너지는 대화 경로와 심각도가 다르다).
  Major 변경의 blast radius 를 한 cycle 에 겹치지 않는다(Phase 7.3 응집 한계).
- **필요한 사람 액션(1줄)**: 별도 cycle 로 insight 스캔 루프에 동일 liveness 계약 적용 여부 판단
  (선행 측정: 스캔 중 `db_failed`/degraded 중 끊김 시그니처 비율).

## FR-ask-orphan-redeploy-dead-air — fixed:undeployed (L4↔인프라 경계; 재배포가 진행 중 답변을 삼키고 회수가 수백초 지연)

- **status**: `fixed:deployed:unverified-live` — **배포 완료**(2026-07-30, PR #1088 merge main
  `76dbfedd` → `deploy-web` 전체 롤아웃: web-a/web-b 무중단 롤링 + insight-worker/ask-worker
  재생성 + gateway reconcile, soak 통과. **4서비스 GIT_COMMIT=76dbfedd healthy**, edge
  `/healthz` ok·mysql_ok·pg_ok). 배포본 런타임 실증: `worker_role=ask_worker`(compose 주입,
  재생성 불변) · `role_prefix=ask-worker[ask_worker]-` · `drain=60` · `role_stale=60` · 봉인 심볼
  6종 적재. **라이브 대화 corroboration 재측정 전** → `unverified-live`.
  후속 `TASK-20260730T172000-dedup-param-cast` 로 봉인 C 활성화(아래 POST-DEPLOY 절).
- **source**: 사용자 명시 호출 `/_dqa:conversation_audit` (2026-07-30) — 지정 대화 "레거시 호환성을
  고려한 실제 DB 기반 쿼리 리뷰", "요청이 도중에 중단된 것으로 추측".
- **last_seen**: 2026-07-30 · **seen_count**: 1 · **seen_distinct_conv**: 8 (60일 고아 재큐 기준)
- **modality**: 그룹 비동기(`is_group=t`) · **product_id(마스킹)**: P-119 · **account(마스킹)**: A-10 ·
  **conv(마스킹)**: …b5f40d99
- **symptom_confidence**: high (사용자 명시 보고 + 라이브 데이터 완전 재현)
  · **rootcause_confidence**: high (코드 file:line + `ask_jobs`/`steps`/`core_messages`/`messages`
  + 컨테이너 타임스탬프 4중 삼각측량)
- **suspected_layers**: **L4↔인프라 경계** — 큐/워커 lifecycle(코드)과 배포 재생성(인프라)의 경계.
  L7 에서 표면화(스피너 8분 고착·사용자 메시지 중복 표시).
- **증상(signal)**: `E-USR` 명시 보고 + `I-INT` 중복 메시지 + `I-FALSE` — job 483 이 15:38 에 답변
  초안까지 만들고 red-team 자가검증 중 15:41:32 에 배포로 죽었고, 회수가 15:49:18 에야 일어났다.
  재실행은 사용자 메시지를 한 번 더 저장한 뒤 LLM timeout 으로 최종 error. **사용자는 14분을
  기다려 중복 메시지와 오류만 받았다.**
- **confirmed_root_cause**: `modules/ask.py` `_worker_id()` 가 `socket.gethostname()`(=컨테이너 id)
  기반이라 컨테이너 **재생성**마다 값이 바뀐다 → `ask_jobs.reclaim_worker_jobs_on_boot` 의
  `claimed_by = worker_id` 정확일치가 **항상 0행**. `bin/deploy-web.sh` 는 워커를
  `--force-recreate` 하므로 **"배포로 죽은 job" 은 자가회수가 구조적으로 불가능**했고, 전역 stale
  sweeper 의 `AGENT_ASK_WORKER_STALE_SEC`(런타임 실측 450s) 창을 통째로 기다렸다. 부수 결함:
  재실행이 `agent_core._save_message(user)` 를 다시 돌아 사용자 메시지를 중복 저장.
  재발경로 = **infra(배포마다 재생성) — 단 우리 통제 안** → 코드가 권위선.
- **corroboration**: **structural** — 60일 고아 재큐 **8건 / 8 distinct_conv**(전체 482 job ·
  209 대화 ≈ 3.8%), 생성→재시작 dead-air **142~1,649초**(중앙값 ~700s), **3건 최종 error**.
  중복 사용자 메시지(연속 동일 user 행) **9건 / 9 distinct_conv**.
- **거짓양성 기각(`refuted`)**: ① 같은 대화 07-29 17:38~17:39 사용자 3건 무응답은 **그룹
  `@assistant` 멘션 게이트**(`conversations.py` `group_requires_mention`, 의도된 동작 F4) — 결함
  아님. ② `FR-dataplane-conn-stale-no-reconnect` 재발 아님(연결 절단 시그니처 부재, 워커 프로세스
  소실이 원인). ③ 진행 중 병렬 cycle(FE 말풍선 `enqpre-run-handoff`, 이미 머지된 llm-timeout)과
  파일 중첩 없음 — F3 중복 기각.
- **봉인**: (A) 종료 시 lease 명시 반납 + 반납 직후 cancel 마킹(겹침 창을 heartbeat 주기 → cancel
  폴링 주기로 축소) (B) worker identity 를 재생성 불변 role 로 분리(`AGENT_WORKER_ROLE` >
  `AGENT_SESSION` > hostname) + `ask-worker[<role>]-` 경계 + 같은 role 의 죽은 이전 인스턴스를
  `ROLE_STALE_SEC`(60s)로 회수(SIGKILL backstop) (C) 재시도에서만 근거 기반 중복 저장 억제.
  **전역 `STALE_SEC` 불변**, cap 회계는 전역 sweep 과 동일, 보안 경계 무변경.
- **disposition 근거**: Major(§12.3 — 코어 워커 lifecycle·동시성) → attended human-decision.
  사용자가 AskUserQuestion 으로 봉인 범위 **A+B+C** 명시 선택(2026-07-30) → PLAN-APPROVED 후 구현.
  structural corroboration + 코드 file:line confirmed(high) → fix-now.
- **fix**: `CHG-20260730T160000-ask-redeploy-handoff` / **코드 거주 `feature-0002-agent-core`**
  (+ `shared/config.py` knob 2종) / `REV-20260730T160000-ask-redeploy-handoff`
  (§18.8.2 제약-없는-채널 우선 → codex 적대 2라운드 backend+security+qa, P1 5건 전건 수정 → P1 0건).
- **rc_ids**: RC-1(회수 지연) · RC-2(중복 저장) · **batch-id**: B-20260730T160000-ask-redeploy-handoff
- **범위 밖(deferred/인지)**: ① 재시도가 1차 시도의 답변 초안·red-team 라운드를 재사용하지 않는다
  (전량 재실행) — 부분 산출 이월은 별 cycle. ② `insight-worker` 도 같은 hostname 기반 식별을 쓰나
  소비자·복구 정책이 다르다(배경 스캔은 다음 cadence 재시도) — 응집 범위 밖. ③ 반납 후 cancel
  마킹이 KV 장애로 실패하면 fencing 이 기존 heartbeat 경로(≤10s)로 복귀(수용, REVIEW 근거 기록).
- **라이브 실측 필요분(§정직)**: 코드/테스트는 "인계 계약이 동작함" 까지만 증명한다. **"실제 대화의
  dead-air 소멸"** 은 배포 후 실측분(미수행) → 다음 audit 이 corroboration(`attempts>1` 재큐의
  생성→재시작 중앙값 · 연속 동일 user 메시지 distinct_conv) 재측정 → 감소 시 `verified`, 재증가 시
  `regressed`.
- **POST-DEPLOY 실측 (2026-07-30, 정직 기록)**:
  - **결함의 심각도가 진단 시점보다 크다**: 회수 창 `AGENT_ASK_WORKER_STALE_SEC` 는
    `AGENT_TIMEOUT_SEC` 파생(`max(timeout×3,…)+180`)이라, 병렬 세션이 timeout 을 90→**900** 으로
    올린 뒤 창이 450s → **2,880s(48분)** 로 함께 커져 있었다. 즉 **LLM 타임아웃을 튜닝하면 고아
    job 의 무응답 상한이 조용히 같이 커지는 결합**이 있다. 본 봉인의 `ROLE_STALE_SEC` 는
    `AGENT_TIMEOUT_SEC` 와 무관한 고정 60s 라 이 결합을 끊는다.
  - **라이브 재현·회복 관측**: 배포 직전 job 485(대상 대화, 15:57 요청)가 16:10 타 세션 배포로
    죽어 **42분 좀비**였고, 전역 sweeper 가 16:59:44 에 회수 → 신규 워커(새 형식
    `ask-worker[ask_worker]-…`)가 17:00:08 claim → **17:02:07 답변 완료**. 사용자 원 요청 해소.
  - **전환기 공백(1회성)**: 구 형식 `claimed_by` 로 claim 된 job 은 새 role 패턴에 매칭되지 않아
    본 봉인이 구제하지 못한다. 이번 배포로 고아가 된 job 488 은 **사용자 승인 하에 1회 수동
    requeue**(sweeper 와 동일 전이, `pending`+`lease_epoch++`) → 신규 워커가 ~0.4s 안에 재claim.
    배포 이후 claim 되는 job 부터 봉인 발효.
  - **봉인 C 는 배포 시점에 무력이었다**: job 485 재시도가 사용자 메시지를 다시 중복 저장
    (6301↔6322). 원인 = 판정 SQL 의 `%(mirror_sender)s IS NULL` 파라미터에 타입 컨텍스트가 없어
    PG 가 쿼리를 거부 → `_read_runtime_pg` 예외 흡수 → fail-open 저장. FakeConn 테스트가 실 SQL 을
    실행하지 않아 못 잡았다(적대 리뷰 P2 로 이미 지적됐던 공백). 수정
    `CHG-20260730T172000-dedup-param-cast`(`::text`/`::bigint` 캐스트 + 실 PG 5케이스 검증).
