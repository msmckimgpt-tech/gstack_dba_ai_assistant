---
doc_type: TEST
feature_id: feature-0042-analysis-dedup
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope

본 cycle 은 **코드 변경 0건**의 조사·검증 cycle 이다. 검증 대상은 구현물이 아니라 **판정의 근거**다:
등재된 각 항목의 전제가 라이브 실측으로 성립하는지, 그리고 캐싱 전제 3항이 관측 수치로 확정되는지.

제외: 프롬프트 재구성 구현(ITEM-15 미착수) · 캐시 계측 컬럼 신설 · 웹/UI (변경 없음).

## 2. Test Cases

- TEST-20260813T231902-dedup-premise-1: 동명 노드의 분석문이 실제로 동일한가
  (`node_analysis_jobs` done 전량 → `node_name` 별 `count(*)` vs `count(DISTINCT summary)`).
  기대: dedup 전제가 성립하면 distinct 가 현저히 작아야 한다.
- TEST-20260813T231902-cache-below-1: 캐시 하한 미달 프롬프트 + `cache_control` → 무음 실패 재현.
  기대: 에러 없이 `cache_creation_input_tokens == 0` 且 `cache_read_input_tokens == 0`.
- TEST-20260813T231902-cache-above-1: 하한 초과 프롬프트 + `cache_control` → 캐시 발동.
  기대: 1회차 `cache_creation > 0`, 2회차 `cache_read > 0`.
- TEST-20260813T231902-cache-control-1: 하한 초과 + `cache_control` 없음 (대조군).
  기대: 양 필드 모두 0 — 캐시가 프롬프트 길이가 아니라 `cache_control` 로 켜짐을 분리 입증.

## 3. Test Runs

### Run 2026-08-14 · dedup 전제 검증
- Environment: `CLI` (라이브 PG read-only 조회)
- Command: `docker exec repo-postgres-1 psql -U postgres -d agent_kb -Atc "<집계 SQL>"`
- 결과: **FAIL(전제 반증)** — TEST-20260813T231902-dedup-premise-1

  | node_name | jobs | distinct summary | 고유율 |
  |---|---:|---:|---:|
  | AccountId | 261 | 260 | 99.6% |
  | regdate | 193 | 193 | 100% |
  | member_srl | 104 | 104 | 100% |
  | UniqueID | 80 | 80 | 100% |
  | AccountName | 52 | 47 | 90.4% |

  육안 확인: 차이는 LLM 비결정성이 아니라 부모 테이블 맥락이었다 —
  `dbLog.EquipTransform.AccountId`("장비 변환 이벤트를 수행한 플레이어 계정") vs
  `dbLog.Cheat.AccountId`("부정행위 적발 기록을 특정 플레이어 계정과 연결").
  → ITEM-13 기각. 상속은 절감이 아니라 정보 손실.

### Run 2026-08-14 · prompt caching 라이브 프로브
- Environment: `CLI` (컨테이너 `repo-insight-worker-1` → `bedrock-gateway`, `claude-haiku-4-meta`)
- Command: `docker exec -i repo-insight-worker-1 python -` (조건 3 × 호출 2회, `max_tokens=6000`)
- 결과: **PASS** — TEST-...-cache-below-1 / cache-above-1 / cache-control-1 모두 기대와 일치

  | 조건 | prompt | cache_creation | cache_read | 판정 |
  |---|---:|---:|---:|---|
  | A. 433 tok + `cache_control` | 433 / 433 | 0 | 0 | 무음 실패 재현 |
  | B. 4,463 tok + `cache_control` | 4,463 / 4,463 | 4,422 → 0 | 0 → 4,422 | 캐시 발동 |
  | C. 4,463 tok, `cache_control` 없음 | 4,463 / 4,463 | 0 | 0 | 대조군 정상 |

  부수 확인: `max_tokens` 가 alias 의 `thinking.budget_tokens`(5,000) 이하이면 Anthropic 이 400 을
  반환한다(`max_tokens must be greater than thinking.budget_tokens`) — 첫 시도 `max_tokens=32` 가
  전 조건 400 이었고 6,000 으로 올려 해소. 프로브 설계 시 유의점으로 기록한다.

### Run 2026-08-14 · 회귀 영향
- Environment: `CLI`
- 대상: 코드 변경 0건 — 실행 경로 무변경이므로 신규 회귀 테스트 없음.
  변경 파일은 `docs/**` 와 본 unit 문서뿐이며 런타임이 읽지 않는다.

## 4. Coverage Gaps

- **구독 한도 회계 1항 미검증**: 캐시 읽기 0.1× 가 OAuth 구독 사용량 한도에 어떻게 계상되는지는
  `usage`·응답 헤더 어디에도 노출되지 않아 본 프로브로 판정 불가. 장기 관측 과제로 이월(추정 금지).
- **프롬프트 출력 계약 회귀 테스트 0건**: ITEM-15 착수 전 신설이 필요한 안전망.
  현재 `unit/*/tests/` 전수 grep 상 프롬프트 상수·출력 계약을 고정하는 테스트가 없다.
- **분석 품질 검정력 부족**: `node_analysis_verdicts` 140건 · 증거 커버리지 1.3%.
