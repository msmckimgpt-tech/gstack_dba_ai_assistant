---
doc_type: REVIEW
feature_id: feature-0032-llm-token-budget
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260730T073000-llm-token-budget [CODEX: 반영 완료]

- **Related Change:** feature-0032 백그라운드 LLM 토큰 예산 (CHG-20260730T071120).
- **Panel:** `codex exec` 적대 리뷰(fresh-context, 스테이징 diff 직접 판독). 세션 정책상 Agent
  tool 을 쓰지 않으므로 T0·T1 과 동일한 codex CLI 경로.
- **반증 요청 가설:** ① 사용자 요청 경로가 예산에 막히는 경로 ② fail-open 파손 ③ 게이트 배선
  정확성(claim 순서·반환 계약) ④ 캐시 동시성·`-1` 오염 ⑤ 집계 SQL 정확성·풀스캔 ⑥ admin.js
  XSS·NaN·0 나눗셈.

### codex 지적과 처리

| # | 지적 | 판정 | 조치 |
|---|---|---|---|
| C1 | **캐시 갱신 race** — 느린 조회가 나중에 끝나며 더 최신인 결과를 과거 값으로 덮어쓴다. 그러면 최대 TTL(60초) 동안 `allowed()` 가 낮은 소비를 보고 **예산 초과를 허용**한다. 병렬 워커에서 여러 tick 이 동시에 예산을 묻는 것이 정상 경로라 실제로 발생 가능 | **유효(P1)** | single-flight 락 도입 — 조회는 한 번에 하나만 나가고, 진행 중이면 블로킹 없이 직전 캐시를 쓴다. race 를 완화가 아니라 **구조적으로 제거**했고, 부수적으로 thundering herd 도 해소. 회귀 테스트 2건(느린 조회 중 재조회 미발생 · 조회 중 호출이 블로킹되지 않음) |
| C2 | 상한이 0(무제한)이어도 `snapshot()` 이 PG 를 조회 — 상한 비활성 상태에서 PG 장애가 콘솔 지연으로 번진다 | **유효(P2)** | `cap<=0` 이면 즉시 반환(`allowed()` 와 같은 계약). 회귀 테스트 1건 |
| — | 사용자 요청 경로 차단 | **반증됨** | 게이트는 백그라운드 진입점 3곳에만 있고 `task="agent"` 는 통과하지 않는다 |
| — | fail-open | **반증됨** | PG 연결·쿼리 실패 → `-1` → 허용. 모듈 부재도 종전 동작 |
| — | claim 순서 | **반증됨** | 예산 확인이 `_rw_conn()`·claim 보다 앞선다 |
| — | 반환 계약 | **반증됨** | 호출측이 `.get()` 으로 읽어 `skipped` 추가로 깨지는 경로 없음 |
| — | SQL 정확성 | **반증됨** | `task NULL` 은 백그라운드로 포함(보수적) · `SUM` NULL 은 COALESCE · `ix_llm_usage_created` 인덱스 존재(baseline 0001) |
| — | admin.js XSS·0 나눗셈 | **반증됨** | 숫자 필드만 삽입·색상 상수 · 비율은 서버가 `cap>0` 일 때만 계산 |

### Verdict

SHIP — P1 1건·P2 1건 in-cycle 수정, 나머지 6개 가설은 코드 근거로 반증. 수정 후
`COMPOSE_PROJECT_NAME=repo make test` 재실행.

### 남긴 리스크

- 게이트 커버리지 96% — table/account/schema insight 는 계량되지만 차단되지 않는다(ADR-0032-05).
  단일 choke-point 가 생기면 100%로 올릴 수 있다.
- 조회 중 호출은 직전 캐시로 판정하므로 최대 60초의 지연 오차가 남는다. 이는 설계상 허용 범위이며,
  single-flight 는 그 오차가 **덮어쓰기로 확대되지 않도록** 하는 장치다.
