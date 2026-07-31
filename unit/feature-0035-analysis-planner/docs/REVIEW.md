---
doc_type: REVIEW
feature_id: feature-0035-analysis-planner
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260731T003000-analysis-planner [CODEX: 반영 완료]

- **Related Change:** feature-0035 결정적 분석 플래너 (CHG-20260731T002000).
- **Panel:** `codex exec` 적대 리뷰(fresh-context, 스테이징 diff 직접 판독).
- **반증 요청 가설:** ① 비용 폭주(cap 우회·반복 시드·스키마 누적) ② 우선순위 정확성(미분석
  판정·스키마 축) ③ insight 스캔 파손 ④ 결정성 ⑤ SQL 정확성.

### codex 지적과 처리

| # | 지적 | 판정 | 조치 |
|---|---|---|---|
| C1 | **후보 조회에 `DISTINCT` 없음** — `rag_objects` 유니크 키에 `conversation_id` 가 포함돼 같은 테이블이 여러 행일 수 있다. 상한 3이 `Orders, Orders, Orders` 가 되어 **실제로는 한 테이블만** 시드된다(커버리지·우선순위 왜곡) | **유효(P1)** | `SELECT DISTINCT` + 회귀 테스트 |
| C2 | **사이클 전역 상한 부재** — "기존 busy/cooldown 가드는 스키마별 중복만 막을 뿐, 여러 스키마·DB 에 걸친 비용 누적은 막지 못한다" | **유효(P1)** | `AGENT_ANALYSIS_COVERAGE_CYCLE_CAP`(기본 9) 신설, insight 가 이미 시드한 몫을 빼고 잔여만 요청. 회귀 테스트 |
| C3 | 관계 점수가 스키마·scope 를 무시해 동명 테이블 점수가 합산된다 | **의도된 근사(P2)** | 유지 + 한계 명시(ADR-0035-06). `table_relationships` 의 schema 는 원본이라 effective schema 와 어긋나고, 잘못 맞추면 **신호가 통째로 0**이 되어 플래너가 이름 순 순회로 퇴화한다. 순위에만 영향을 주는 오차가 훨씬 안전한 실패 방향이다 |
| C4 | 미분석 판정이 `status='done'` 에만 의존 | **허용(P2)** | 그것이 이 시스템에서 "분석됨"의 정의다. 다른 경로로 생긴 분석문은 job 행을 남기므로 실질 누락이 없고, 만약 있더라도 재분석은 refine-not-override 라 파괴적이지 않다 |
| — | SQL injection · 파라미터 바인딩 | **반증됨** | `strpos` + `%s` 바인딩 |
| — | 연결·커서 해제 | **반증됨** | finally 에서 닫힘 |
| — | 예외 전파 | **반증됨** | insight 스캔으로 전파되지 않음 |

### Verdict

SHIP — P1 2건 수정, P2 2건은 근거를 들어 의도된 선택으로 기록.

### 스스로 짚는 점 (반복된 실수)

C2 는 feature-0033 에서 지적받은 것과 **같은 계열**이다 — 그때는 "상한이 스키마 루프마다 적용돼
총량이 곱해진다"였고, 이번에는 "재사용하는 큐잉 경로의 가드가 스키마 단위인데 그 위에 총량
상한이 없다"였다. 이번에 나는 "검증된 경로를 재사용하니 안전하다"고 판단했는데, **그 경로의
가드가 어느 단위인지 확인하지 않은 것**이 실수다. 재사용은 가드의 *범위*까지 확인해야 성립한다.
ADR-0035-04 에 그 교훈을 남겼다.

또한 `LIKE` 와일드카드 함정(`_` → 임의 1문자)은 feature-0034 에서 겪은 것을 이번엔 **구현 중
스스로** 잡았다 — 같은 계열의 반복이 줄어드는 신호로 본다.

### 남긴 리스크

- 관계 점수의 datasource 단위 근사(C3). 스키마별 정확한 점수가 필요해지면
  `table_relationships` 에 effective schema 를 저장하는 별 슬라이스가 필요하다.
- 자격 게이트(`schema_analysis_completed`) 때문에 **사람이 한 번도 전체 분석하지 않은 DB** 는
  자동 확대 대상이 아니다. 의도된 안전장치이지만, 그런 DB 의 커버리지는 여전히 0으로 남는다.
