---
doc_type: TEST
feature_id: feature-0032-llm-token-budget
status: active
edit_policy: rewrite
source_of_truth: true
---

# Test

## 1. Test Contract

**성공 조건**
1. 사용자 요청 경로가 예산에 **집계되지도 차단되지도** 않는다.
2. fail-open — 상한 0·조회 실패·모듈 부재에서 백그라운드가 계속 돈다.
3. 게이트가 백그라운드 진입점 3곳에서 소진 시 정직한 skip 사유를 돌려주고 본체를 실행하지 않는다.
4. 노드 분석은 **claim 전**에 예산을 본다(집어온 뒤 막으면 attempts 만 소모).
5. 콘솔이 실제로 렌더한다 — API 필드 존재는 노출이 아니다.

**실패 조건(회귀)**
- 집계 SQL 파라미터에서 사용자 경로 task 가 빠지면 실패.
- 예산 소진 상황에서 본체(`_run_*_inner`)가 호출되면 실패.
- `admin.js` 가 `data.llm_token_budget` 를 읽지 않으면 실패.

## 2. 자동 테스트

`unit/feature-0002-agent-core/tests/test_llm_token_budget.py` (신규)

| 축 | 케이스 |
|---|---|
| A 사용자 보호 | 집계 SQL 파라미터 직접 검사 · 제외 목록 계약 · 미지 task 는 백그라운드로 계산 |
| B fail-open | 상한 0(조회조차 안 함) · 조회 실패 허용 · 예외 → `-1` 센티넬 · 경계 양측(999 통과 / 1000 차단) |
| C 게이트 | semantic_cluster·product_classify·node_analysis 각각 소진 시 본체 미실행 + skip 사유, 여유 시 통과 |
| D 캐시 | TTL 안 재조회 0 · `refresh=True` 재조회 · `-1` 미캐시 |
| snapshot | 소진 계약 · 판정 불가 시 `remaining` 키 부재(0 으로 위장하지 않음) · 창 24h |

`unit/feature-0003-agent-web-ui/tests/test_llm_budget_pane.py` (신규)

| 케이스 | 이유 |
|---|---|
| `admin.js` 가 `data.llm_token_budget` 를 읽는다 | T0b 에서 응답만 추가하고 렌더를 빠뜨린 채 "콘솔 노출 완료"로 보고한 전례(§16.7 G3) |
| 면제 안내 문구 존재 | 없으면 운영자가 "분석이 멈췄으니 답변도 멈추겠다"고 오해 |
| "상한 없음" ≠ "조회 불가" | 같은 문구로 뭉뚱그리면 계량 장애가 숨는다 |
| snapshot 키 ↔ 렌더 키 일치 | 필드명 드리프트 차단 |
| 소진이 attention 으로 부상 | 조용한 소진은 "왜 분석이 안 도나"의 답을 늦춘다 |

## 3. 실행

```
COMPOSE_PROJECT_NAME=repo make test
```

## 4. 라이브 검증 (배포 후)

1. 콘솔 `AI 운영 현황` 에 예산 막대가 실제 수치로 표시되는지(PB-0008).
2. `AGENT_BACKGROUND_LLM_TOKEN_CAP_24H` 를 현재 소비보다 **낮게** 내려 게이트 실동작을 관측하고,
   같은 창에서 대화 답변이 정상인지 확인한 뒤 원복 — 이것이 "사용자를 막지 않는다"의 유일한
   라이브 증거다.
3. 워커 로그에 `보류 — 백그라운드 LLM 토큰 예산 소진` 이 뜨는지.
4. claude-corp 사용량 관측(작업 전/후 대조) — `REPORT.md` §관측.
