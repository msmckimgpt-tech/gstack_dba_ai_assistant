---
doc_type: FUNCTION
feature_id: feature-0037-domain-synthesis
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function: 도메인 합성 (L3, lazy)

## 개요

스키마(DB) 하나의 **도메인 개요**를 3~5문장으로 합성해 둔다. 입력은 그 스키마의 **클러스터
요약들**이지 개별 테이블이 아니다 — 이미 한 번 접힌 것을 다시 접는다.

라이브 실측(2026-07-31): 클러스터 요약 **1,006건**이 **120개 스키마**에 걸쳐 있다(평균 8개/스키마).
그래서 "이 DB 가 어떤 도메인인가"를 알려면 여전히 8개를 읽어야 했다. L3 는 그것을 2~3개 축으로 접는다.

## 1. 요청과 생성의 분리 — 이 기능의 설계 전부

두 제약이 얼핏 모순이다:

- **사전 전량 생성 금지**(LazyGraphRAG): 120개를 미리 다 만들면 대부분 아무도 안 읽는다.
- **답변 경로 런타임 합성 금지**(ADR-0034-07): 질문이 들어온 순간 LLM 을 부르면 체감 지연을
  잠식한다(feature-0027 이 -25~35s 를 확보했다).

해법은 **"누가 실제로 찾았는가"를 생성 신호로 쓰는 것**이다:

```
grounding 이 조회 → 없으면 request() 만 (LLM 0, 지연 0)
insight tick 이 요청된 것만 합성 → 다음 질문부터 주입
```

첫 질문은 요약 없이 답하지만, 그 대가로 120번의 헛된 합성을 치르지 않는다. 그리고 **자주 찾히는
도메인이 먼저 채워진다**(`request_count` 우선순위) — 사용이 곧 우선순위다.

## 2. 재생성 판정 — `cluster_set_hash`

그 스키마의 클러스터 요약 집합 지문. **라벨·요약·멤버 수·근거 수**를 모두 넣고 정렬 후 해시한다.

- 라벨 변경 = 클러스터 재구성 → 재생성
- 요약 변경 = L2 갱신 → 재생성
- **카운트 변경 = 커버리지 증가** → 재생성. 근거가 두터워지면 같은 문장이어도 도메인 그림의
  신뢰도가 달라지는데, 이걸 빼면 요약이 영원히 옛 커버리지 기준으로 남는다.

⚠ 해시는 payload cap(25)으로 자르기 **전** 전체 집합(최대 300)으로 계산한다 — 잘린 뒤 해시하면
26번째 이후 클러스터의 변화를 영영 놓친다.

## 3. 비용

| 장치 | 값 |
|---|---|
| pass 당 합성 수 | 3 (L3 는 입력이 커서 작게) |
| payload 그룹 상한 | 25 |
| 상위 게이트 | 백그라운드 토큰 예산(항목마다 재확인) · `acquire("llm")` · kill-switch |
| 실행 조건 | **advisory lock 을 얻은 tick 에서만** — 행 단위 claim 이 없어서 lock 없이 돌면 여러 워커가 같은 스키마를 중복 합성한다 |

호출측 `limit` 은 설정 상한을 넘을 수 없다. 빈약한 응답(30자 미만)은 저장하지 않는다.

## 4. 대기 조회의 인덱스 정합

`pending_schemas` 는 **미생성분을 먼저 별도 쿼리**로 가져온다. 한 쿼리로 합치면
`WHERE requested_at IS NOT NULL` 뿐이라 partial index
(`generated_at IS NULL AND requested_at IS NOT NULL`)가 받지 못하고, 생성된 행이 쌓일수록
요청 이력 전체 스캔에 가까워진다. 남는 여유만큼만 기존 생성분을 재검사한다.

## 5. 프롬프트 — 나열이 아니라 추상화

그룹을 나열하기만 하면 L2 를 반복하는 것이지 새 층이 아니다. 그래서 프롬프트가 명시한다:
*"Do NOT enumerate every group — the value of this text is the ABSTRACTION over them.
If you find yourself listing more than three labels in a row, merge them into an axis."*

커버리지 카운트도 함께 실어, 근거가 적을 때 확신 수위를 낮추게 한다.

## 6. 답변 경로 영향

- 요약이 **있으면**: RO 조회 1회 추가, 쓰기 0.
- 요약이 **없으면**: 요청 UPSERT 1회를 **별도 RW 연결**로. 조회 커넥션은 읽기 전용
  (`agent_kb_ro` = SELECT only)이라 거기서 INSERT 하면 항상 실패한다.
- 실패는 전부 무시 — 요청을 못 남기면 다음 질문이 다시 남긴다.
