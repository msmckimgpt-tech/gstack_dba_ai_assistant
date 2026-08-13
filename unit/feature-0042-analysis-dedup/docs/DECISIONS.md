---
doc_type: FEATURE_DECISIONS
feature_id: feature-0042-analysis-dedup
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-001 — 등재 항목은 착수 직전에 전제를 실측으로 재검사한다
- Status: accepted
- Date: 2026-08-14
- Context: ITEM-13 은 "형제 노드는 같은 분석을 받는다"는 전제 위에 등재됐고, 그 근거는 이름 중복률
  69.3% 였다. 착수 직후 내용 중복률을 재보니 사실상 0 이었다(`AccountId` 261잡 → distinct 260).
  등재 근거와 실제 전제가 다른 지표였던 것이다.
- Decision: 등재는 착수 허가가 아니다. **구현 첫 커밋 전에 그 항목의 전제를 직접 측정**하고,
  반증되면 구현하지 않고 기각으로 전환한다. 기각 시 반증 데이터를 ROADMAP 항목 안에
  `rejected_because` 로 남겨 같은 근거로 재등재되지 않게 한다.
- Consequences: 착수 초반에 폐기되는 항목이 생긴다(비용). 대신 반증된 전제 위에 코드가 쌓이는 것을
  막는다 — 이 경우 형제 상속이 부모 테이블 맥락을 통째로 지웠을 것이다.
- Supersedes: 없음
- Superseded By: 없음

## ADR-002 — 지표를 인용할 때 "무엇의" 중복률인지 명시한다
- Status: accepted
- Date: 2026-08-14
- Context: "중복률 69.3%"는 참이지만 **이름의** 중복률이었다. dedup 의 타당성이 걸린 것은
  **내용의** 중복률이고 그 값은 ≈0 이었다. 두 지표가 같은 단어로 불려 판단이 뒤집혔다.
- Decision: 절감·중복·커버리지 류 지표는 측정 대상을 지표명에 포함해 기록한다
  (`이름 중복률` / `내용 중복률` / `증거 커버리지`). ROADMAP `why` 에 지표를 쓸 때도 동일.
- Consequences: 서술이 길어진다. 대신 지표가 다른 결론의 근거로 전용되는 것을 막는다.
- Supersedes: 없음
- Superseded By: 없음

## ADR-003 — 캐싱 전제는 코드 변경 전에 라이브 프로브로 확정한다
- Status: accepted
- Date: 2026-08-14
- Context: prompt caching 은 최소 prefix 미달 시 **에러 없이 무시**된다(Haiku 4.5 = 4,096 토큰).
  즉 코드에 `cache_control` 을 넣고 배포해도 "적용됐다"는 신호와 "무시됐다"는 신호가 구분되지 않는다.
  더해 이 프로젝트는 litellm(OpenAI 규약) 경유라 passthrough 여부 자체가 미지였다.
- Decision: 하한 미달·하한 초과·`cache_control` 없음 **3조건 대조**로 프로브하고, 각 조건 2회
  호출해 write→read 전이를 관측한다. 관측 불가 항목(구독 한도 회계)은 추정하지 않고 미확정으로 남긴다.
- Consequences: 프로브 1회(6콜) 비용. 대신 ITEM-15 의 방향이 "축소"에서 "캐시 가능 재구성"으로
  반전됐다 — 프로브 없이 착수했다면 프롬프트를 줄여 캐시를 영구히 불가능하게 만들었을 것이다.
- Supersedes: 없음
- Superseded By: 없음
