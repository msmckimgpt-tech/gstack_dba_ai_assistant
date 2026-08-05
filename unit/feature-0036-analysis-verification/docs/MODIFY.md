---
doc_type: MODIFY
feature_id: feature-0036-analysis-verification
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260731T121000 분석문 사실성 판정층 신규 (Minor, 백그라운드)

- **무엇:** 노드 분석문을 L0 통계 증거와 대조해 supported/contradicted/unverifiable 로 판정하고
  근거 한 문장과 함께 `node_analysis_verdicts` 에 저장한다.
- **왜:** 생성된 분석문의 사실성을 아무도 확인하지 않았다. 그것이 L2 요약의 입력이 되고 대화
  답변에 주입되므로, 아래층의 오류가 위로 전파되며 더 그럴듯해진다.

### 변경 파일

| 파일 | 변경 |
|---|---|
| `alembic/versions/20260731_0052_analysis_verdicts.py` | **신규** — CHECK 제약(3 verdict)·GRANT·인덱스 |
| `src/modules/analysis_verify.py` | **신규** — 대상 선정·증거 조립·판정·저장·정직성 방어 |
| `src/modules/llm.py` | `ANALYSIS_VERIFY_PROMPT` + `llm_verify_analysis` |
| `src/modules/insight.py` | 분석 tick 직전 판정 pass(자체 PG 연결) |
| `shared/config.py` · `shared/runtime_settings.py` | knob 2종(live) |
| `tests/test_analysis_verify.py` | **신규** 38건 |
| `tests/test_worker_parallelism.py` | `PERF_KEYS` +2 |

### 위험과 완화

| 위험 | 완화 |
|---|---|
| **잘못된 확인 도장** | 전 실패 경로에서 행 미생성. 테스트 절반이 이 축 |
| 근거 없는 판정 | `reason` 빈 값이면 기록하지 않음 |
| 잘못된 대조 대상 | node_key ↔ (scope,schema,table) 조인 + `error IS NULL` 이중 확인 |
| 재판정 누락 | 이전 판정 해시를 조회해 비교, 노드당 1행 유지 |
| 비용 폭주 | pass 상한 + 인자 우회 차단 + 항목별 예산 재확인 + 1건 1콜 |
| 워커 파손 | savepoint · `cursor()` try 안 · 전 경로 예외 흡수 |

### 배포 scope
워커(insight-worker) + web(설정). `make deploy-all`.

## CHG-20260805T143000 판정 순환 수정 — 대상은 노드당 최신 분석문 1건 (Minor, 백그라운드)

- **무엇:** `pending_targets` 를 `DISTINCT ON (scope_key, node_key)` 로 좁혀 노드당 최신 분석문
  1건만 판정 대상으로 삼는다. 바깥 정렬 첫 키는 "한 번도 판정된 적 없는 노드 우선". telemetry 에
  `rejudged` 를 분리했다.
- **왜:** 저장은 노드당 1행인데(ADR-0036-04) 대상 선정은 행 단위여서 판정이 **무한 순환**했다.
  라이브 7일 실측 — `analysis_verify` 7,896콜(배경 LLM 호출의 62.8%·토큰 38.3%)인데 대상 노드는
  91개, 판정 행 수는 91개 고정(노드당 평균 87회 재판정, 정보 증가 0).

### 변경 파일

| 파일 | 변경 |
|---|---|
| `src/modules/analysis_verify.py` | 대상 쿼리 `DISTINCT ON` + 미판정 우선 정렬 · `rejudged` telemetry |
| `tests/test_analysis_verify.py` | +4건 (순환 방지 SQL 계약 · 미판정 우선 · rejudged 계수) |
| `unit/feature-0036-*/docs/{FUNCTION,DECISIONS,TASK,REPORT}.md` | ADR-0036-08 및 서술 반영 |
| `docs/LEARNINGS.md` | LRN-20260805-0001 (선정 단위 ≠ 저장 단위 → 무한 순환) |

### 위험과 완화

| 위험 | 완화 |
|---|---|
| 최신 세대만 보게 되어 과거 세대 판정 누락 | 저장이 노드당 1행이라 과거 세대 판정은 애초에 보존되지 않았다 — 손실 없음 |
| `DISTINCT ON` 서브쿼리로 계획 변화 | 라이브 실측 92행 반환(= distinct 노드 수), 기존 인덱스로 즉시 반환 |
| 미판정 우선 정렬이 stage 우선순위를 밀어냄 | 미판정 집합 안에서는 기존대로 stage DESC — 순서만 계층화 |
| 순환 재발 | telemetry `rejudged` + 로그. pass 마다 cap 을 채우면 신호 |

### 배포 scope
워커(insight-worker). `make deploy-all` (web 무변경이나 스파인 일관 배포).

## CHG-20260805T190000 판정 결과를 노드 상세 패널에 노출 (Minor, 사용자 대면)

- **무엇:** `get_node_analysis` 응답에 `verdict`(판정·근거·증거 stage·시각)를 싣고, 그래프 뷰 노드
  상세의 AI 박스에 배지 + 근거 한 줄을 렌더한다. **해시가 일치할 때만** 싣는다.
- **왜:** 판정층은 출하됐지만 `node_analysis_verdicts` 를 읽는 코드가 0곳이었다 — ANCHOR §3 이
  그리는 장면("분석문 옆에 `contradicted` 와 근거 한 줄")이 없어 이 층의 산출이 아무 데도 닿지
  않았다. 순환 수정(CHG-20260805T143000)으로 비용은 90% 줄었지만 효용은 여전히 0이었다.

### 변경 파일

| 파일 | 변경 |
|---|---|
| `feature-0002/src/modules/node_analysis.py` | `_verdict_for` 신규(해시 일치 조회·savepoint·fail-soft) + `get_node_analysis` 응답에 `verdict` |
| `feature-0003/src/static/graph/graph-ctxmenu.js` | 노드 상세 AI 박스에 판정 배지 + 근거 한 줄 |
| `feature-0002/tests/test_node_verdict_surfacing.py` | **신규** 8건 (해시 정합·격리·프론트 계약) |

### 위험과 완화

| 위험 | 완화 |
|---|---|
| **엉뚱한 문장에 확인 도장** | 조회 WHERE 에 현재 분석문 해시 — 불일치는 0행. 그 축만 테스트 3건 |
| 상세 패널 파손(신규 테이블 부재 창) | savepoint + 예외 흡수 → 판정만 사라지고 패널은 정상 |
| `reason` 주입(LLM 산출 문자열) | 기존 `esc()` 로 이스케이프, 테스트로 고정 |
| 역할 칩과 색 혼동 | 판정은 테두리형(모순만 채움) — 채움형 역할 칩과 계열 분리 |

### 배포 scope
web + 워커(백엔드 모듈 공용). `make deploy-all`.
