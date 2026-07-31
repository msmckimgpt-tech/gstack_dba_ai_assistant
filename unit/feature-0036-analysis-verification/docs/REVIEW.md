---
doc_type: REVIEW
feature_id: feature-0036-analysis-verification
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260731T122000-analysis-verification [CODEX: 반영 완료]

- **Related Change:** feature-0036 분석문 사실성 판정층 (CHG-20260731T121000).
- **Panel:** `codex exec` 적대 리뷰(fresh-context, 스테이징 diff 직접 판독).
- **반증 요청 가설:** ① 판정 실패가 "검증됨"으로 기록되는 경로 ② 잘못된 대조(조인 어긋남·실패한
  증거) ③ 비용 폭주 ④ 워커 파손 ⑤ 판정 행 무한 증식.

### codex 지적과 처리

| # | 지적 | 판정 | 조치 |
|---|---|---|---|
| C1 | **`c` 미정의** — insight 배선이 그 스코프에 없는 변수를 넘겨 판정 pass 가 **아예 동작하지 않는다** | **유효(P1)** | `run_verification_pass(conn=None)` 로 바꿔 자체 agent_kb 연결을 열게 함(`process_pending` 과 동형). insight 는 인자 없이 호출. 회귀 테스트 2건 |
| C2 | **재판정 안 됨** — 저장 PK 는 `(scope, node, analysis_hash)` 인데 대상 조회는 해시를 비교하지 않고 "판정 행이 있으면 제외" 한다. **문서에 적은 '분석 갱신 시 자연히 미검증' 계약과 정반대** | **유효(P1)** | LEFT JOIN 으로 이전 판정 해시를 가져와 파이썬에서 비교. 저장 시 같은 노드의 다른 해시 행을 삭제해 **노드당 1행** 유지(무한 증식·중복 판정도 함께 해소) |
| C3 | **증거 error race** — 대상 조회는 `m.error IS NULL` 을 보지만 evidence 재조회는 보지 않아, 두 쿼리 사이에 수집 실패가 기록되면 **실패한 통계로 판정**한다 | **유효(P1)** | evidence 조회에도 `error IS NULL` |
| C4 | **근거 없이 `supported` 저장** — `{"verdict":"supported"}` 만 와도 기록된다. 프롬프트는 reason 을 필수로 요구하는데 코드가 강제하지 않는다 | **유효(P1)** | `reason` 이 비면 판정을 버린다. 재확인할 수 없는 확인 도장이 이 층의 최악의 실패다 |
| C5 | 동시 워커 중복 판정(claim/lock 없음) | **허용(P2)** | insight tick 은 advisory lock 아래 돌고, 중복이 나도 upsert 라 데이터는 일관된다. 낭비는 pass 상한(20)으로 유계다. claim 도입은 복잡도 대비 이득이 작다 |
| C6 | 예산 모듈 import 실패 시 fail-open + `limit` 인자가 상한 우회 | **유효(P2)** | 둘 다 수정 — 예산 모듈 부재는 **중단**(ADR-0036-02), `limit` 은 `min(configured, limit)` |

### Verdict

SHIP — P1 4건·P2 1건 수정, P2 1건은 근거를 들어 허용으로 기록.

### 스스로 짚는 점

C1 은 **배선이 통째로 죽어 있었다**. 테스트 38건이 모듈 내부를 촘촘히 덮었지만 `insight.py` 의
호출 한 줄이 정의되지 않은 변수를 쓴다는 사실은 잡지 못했다 — 모듈 테스트가 배선을 보증하지
않는다. 이후 `test_insight_calls_pass_without_undefined_variable` 로 그 축을 추가했다.

그리고 `cursor()` 를 try 밖에 두는 실수를 **네 번째** 반복했다(feature-0031·0033·0034·0036).
이번엔 자체 테스트가 먼저 잡았지만, 이 패턴은 이제 체크리스트에 넣을 만하다:
**자원 획득(connect/cursor)은 언제나 try 안**.

### 남긴 리스크

- 판정 대상이 현재 7건 수준이다(증거 커버리지 제약). 플래너(feature-0035)가 커버리지를 채운
  뒤에야 이 층이 실질 값을 한다.
- 판정 결과의 콘솔 표시·grounding 반영은 후속 범위다. 지금은 저장까지.
