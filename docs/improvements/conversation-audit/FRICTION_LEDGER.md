# FRICTION_LEDGER — conversation_audit 마찰 원장 (단일 정본)

`/_dqa:conversation_audit` 의 진행 원장(§C5). 항목 = `friction-id` 1개. **content·PII·원본 데이터 값 비전재**(집계 수치·익명 라벨·마스킹만). status 는 측정으로만 `verified` 로 닫힌다(거짓 done 방지). 별도 큐 파일 신설 금지 — 이 파일이 진행 원장.

status enum: `triaged`→`fixed:undeployed`|`fixed:deployed:unverified-live`|`fixed:deployed:verified`|`deferred`|`report-only`|`rejected`|`needs-human`|`blocked:<reason>`|`awaiting-merge:PR#<n>`|`regressed`.

---

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

## FR-mssql-crossdb-structured-discovery — fixed:undeployed (L4↔L8 catalog 스코프 + L1/L2; 구조화 발견 도구 DB(catalog) 인지 봉인)

- **status**: `fixed:undeployed` — 코드/테스트(전체 회귀 1980 PASS·§18.8 3렌즈 패널 MAJOR3 전건 수정)·라이브 QA 수정 실증 완료. **배포 대기**(ask-worker+web 재빌드). 배포 후 `fixed:deployed:unverified-live`, 다음 audit corroboration(MSSQL describe_table 빈-헤더율 감소) 재측정 시 `verified`.
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

---

### 메타 (이 원장의 첫 기록)

- 첫 audit: 2026-06-29, `/_dqa:conversation_audit account=mckim conversation="게임 스테이지 성공률 통계"` (dogfood 검증 run). 두 마찰 모두 **report-only** — 스킬의 과적합 가드(단일 대화·Major·idiosyncratic → 자동수정 보류)가 의도대로 작동.
- 문서 정합(STATUS·wiki)은 `/_dqa:doc_sync` 위임. 본 원장은 ledger·LEARNINGS 만 관할.
