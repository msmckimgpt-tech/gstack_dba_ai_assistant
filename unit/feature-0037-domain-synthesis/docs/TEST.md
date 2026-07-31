---
doc_type: TEST
feature_id: feature-0037-domain-synthesis
status: active
edit_policy: rewrite
source_of_truth: true
---

# Test

## 1. Test Contract

1. **lazy** — 요청되지 않은 스키마는 합성하지 않고, 요청은 LLM 을 부르지 않는다.
2. **재생성** — 입력이 그대로면 미합성, 바뀌면 합성. 카운트 변화·cap 밖 변화도 감지.
3. **비용** — pass 상한·인자 우회 불가·예산 게이트·빈약 응답 미저장·lock 아래에서만.
4. **정직성** — 커버리지 카운트를 전체 기준으로 전달.
5. **격리** — savepoint·예외 미전파·RO/RW 분리.

## 2. 자동 테스트 — `tests/test_domain_synthesis.py` (30건)

| 축 | 케이스 |
|---|---|
| A lazy | 요청이 LLM 미호출 · 첫 요청 시각 보존 · 요청된 것만 조회 · 요청 없으면 skip · 입력 없으면 skip |
| B 재생성 | 입력 불변 시 미합성 · 변경 시 합성 · 해시 순서 무관 · 요약/라벨/**카운트** 변화 감지 · 빈 입력 |
| C 비용 | pass 상한 · **인자 우회 불가** · 예산 차단 · 빈약 응답 미저장 · 스위치/cap 0 · 설정 불가 시 비활성 · 예산 모듈 부재 시 중단 · **lock 게이트** |
| D 정직성 | payload 카운트 · 빈 그룹 제외 · 결정적 정렬 · **cap 은 자르되 카운트는 전체** · 프롬프트가 추상화 요구 |
| E 격리 | savepoint · 예외 흡수 · load/request 실패 · **RW 분리** · grounding 인라인 합성 부재 · insight 배선 |
| F 인덱스 | 미생성분이 partial index 조건으로 먼저 조회 · `_HASH_SCAN_CAP > _GROUP_CAP` |

## 3. 실행

```
COMPOSE_PROJECT_NAME=repo make test
```

## 4. 라이브 검증 (배포 후)

1. `alembic_version` = `0053_domain_summaries` + GRANT 확인.
2. 요약이 없는 스키마의 테이블명을 포함해 질문 → `domain_summaries` 에 `requested_at` 이
   남는지(생성은 아직 없어야 한다).
3. insight tick 후 `도메인 합성 완료 …` 로그 + `generated_at` 채워짐 확인.
4. 같은 질문 재실행 → 답변 컨텍스트에 `[<schema> 전체] (그룹 N개 · 멤버 M개 중 K개 근거) …`
   가 실리는지.
5. 합성된 요약 표본 판독 — 그룹을 나열만 하지 않고 **축으로 접었는지**.
