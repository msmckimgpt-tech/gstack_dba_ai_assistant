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

---

### 메타 (이 원장의 첫 기록)

- 첫 audit: 2026-06-29, `/_dqa:conversation_audit account=mckim conversation="게임 스테이지 성공률 통계"` (dogfood 검증 run). 두 마찰 모두 **report-only** — 스킬의 과적합 가드(단일 대화·Major·idiosyncratic → 자동수정 보류)가 의도대로 작동.
- 문서 정합(STATUS·wiki)은 `/_dqa:doc_sync` 위임. 본 원장은 ledger·LEARNINGS 만 관할.
