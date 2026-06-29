# FRICTION_LEDGER — conversation_audit 마찰 원장 (단일 정본)

`/_dqa:conversation_audit` 의 진행 원장(§C5). 항목 = `friction-id` 1개. **content·PII·원본 데이터 값 비전재**(집계 수치·익명 라벨·마스킹만). status 는 측정으로만 `verified` 로 닫힌다(거짓 done 방지). 별도 큐 파일 신설 금지 — 이 파일이 진행 원장.

status enum: `triaged`→`fixed:undeployed`|`fixed:deployed:unverified-live`|`fixed:deployed:verified`|`deferred`|`report-only`|`rejected`|`needs-human`|`blocked:<reason>`|`awaiting-merge:PR#<n>`|`regressed`.

---

## FR-nl2sql-schema-discovery-giveup — report-only (human-decision)

- **status**: `report-only` (Major 수정 후보 — 단일 대화·idiosyncratic corroboration 으로 자동 promote 보류, 사람 plan 필요)
- **last_seen**: 2026-06-26 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 동기 · **product_id(마스킹)**: P-94 · **conv(마스킹)**: …91655acc
- **symptom_confidence**: high (명시 신호) · **rootcause_confidence**: med (코드 경로 후보 확정, file:line 단정은 추가조사 필요 → `inconclusive→med`)
- **suspected_layers**: **L2↔L8** (datasource 스키마 dialect/casing + tool 피드백 모순) + **L1** (프롬프트: ambiguous 요청에 assume-vs-ask 정책)
- **증상(signal)**: `E-AST` 과도 재질문·장황 무행동 — NL2SQL assistant 가 turn1 에서 tool 8회(search_tables×4·execute_sql×3·describe_table) 소비 후 스키마를 못 특정해 **포기**, 사용자에게 "스테이지 정의?/기준?/기간?" 대량 재질문. 사용자는 turn2 에서 짧게 재지시(`E-USR` over-spec/좌절 신호).
- **confirmed_root_cause(요지)**: assistant 가 존재하지 않는 스키마명(`dbgame`/`dblog`, 추정 lowercase)을 추측 → `execute_sql` 가 `1049 Unknown database 'dbgame'` 반환·`SCHEMA()=NULL`(기본 DB 미선택). 동시에 `describe_table` 는 같은 경로에 응답을 돌려줘 **tool 간 모순 피드백** → 모델이 자기교정 못 하고 give-up. 재발 메커니즘 = `data/config drift`(datasource↔스키마 바인딩) + `model limit`(거부/에러 피드백에 교정 힌트 부재, L2).
- **corroboration**: 최근 14일 `Unknown database/1049` 시그니처 = **distinct_conv 1** → **idiosyncratic**(임계 미달, 전역수정 자격 없음). 표본 부족.
- **disposition 근거**: 수정 후보가 프롬프트(assume-vs-ask)·tool 거부 피드백(교정 힌트)·datasource 스키마 해소(casing) 로 **Major**(코어 LLM 경로). 단일 대화 + idiosyncratic + Major → `report-only`. 자동 fix-now 금지(저흔적 이탈 예외는 Minor 한정).
- **필요한 사람 액션(1줄)**: NL2SQL assistant 의 스키마 discovery 실패 처리 정책 결정 — (a) `search_tables`/`describe_table`/`execute_sql` 거부·0행에 **교정 힌트**(올바른 datasource·스키마 casing 후보) 부착(L2), (b) 모호 요청에 1회 합리적 가정 후 진행 vs 재질문 기준(L1). 코드 거주: `feature-0002-agent-core`. corroboration 이 임계 돌파하면 재triage.

## FR-resultset-table-narration-mismatch — report-only

- **status**: `report-only` · **last_seen**: 2026-06-26 · **seen_count**: 1 · **seen_distinct_conv**: 1
- **modality**: 1:1 · **conv(마스킹)**: …91655acc
- **symptom_confidence**: med-high · **rootcause_confidence**: low (표면 관측, 코드 경로 미추적)
- **suspected_layers**: **L7** (표시·표 렌더 truncation) ↔ **L3** (narration 이 표시 안 된 행을 인용)
- **증상(signal)**: `I-FALSE` 거짓 성공 — turn2 최종답이 표 헤더 "상위 7개" 라 쓰고 **5행만 렌더**, 첨부 CSV 는 "전체 7행", 그런데 서술("주요 발견사항")은 **표에 없는 행**(상위에 안 뜬 고-도전 스테이지)을 핵심 근거로 인용 → 사용자가 보는 표와 서술이 불일치. 추가로 랭킹이 n=1 짜리 0% 행을 통계적 무의미하게 상위 배치. turn2 직후 **user 무응답 종료(`I-SIL` 침묵 이탈)**.
- **disposition 근거**: 단일 대화 표본, 코드 경로 미추적(rootcause low) → `report-only`. 표/서술 정합·min-attempt 임계는 표시 계약(L7) 또는 결과 요약 프롬프트(L1) 결정 필요.
- **필요한 사람 액션(1줄)**: 결과 표 truncation 정책과 narration 의 "표시된 행만 인용" 계약을 정할지 결정(L7/L1). corroboration(표/CSV 행수 불일치 빈도) 미측정 — 정량화 어려움, 추가 신호원 discovery 필요.

## FR-diff-lineno-prefix-leak — fixed:undeployed → (배포 후 fixed:deployed:unverified-live)

- **status**: `fixed:undeployed` (Minor 수정 완료·테스트 PASS·적대패널 SAFE / 배포 전. 배포 후 `fixed:deployed:unverified-live`, 다음 audit corroboration 재측정으로 `verified`)
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

---

### 메타 (이 원장의 첫 기록)

- 첫 audit: 2026-06-29, `/_dqa:conversation_audit account=mckim conversation="게임 스테이지 성공률 통계"` (dogfood 검증 run). 두 마찰 모두 **report-only** — 스킬의 과적합 가드(단일 대화·Major·idiosyncratic → 자동수정 보류)가 의도대로 작동.
- 문서 정합(STATUS·wiki)은 `/_dqa:doc_sync` 위임. 본 원장은 ledger·LEARNINGS 만 관할.
