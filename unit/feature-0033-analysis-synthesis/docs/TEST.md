---
doc_type: TEST
feature_id: feature-0033-analysis-synthesis
status: active
edit_policy: rewrite
source_of_truth: true
---

# Test

## 1. Test Contract

1. **캐시 3중 계약** — 멤버셋·L1·L0 지문이 모두 같을 때만 적중, 하나라도 다르면 재생성.
2. **정렬 결정성** — 입력 순서가 달라도 같은 지문(정렬 누락 시 캐시가 매번 미스).
3. **비용 유계** — 상한은 **pass 전체** 기준, 배치 ≤6, 토큰 예산을 배치마다 재확인.
4. **시그니처 미유입** — 요약이 클러스터링 시그니처에 들어가지 않음(순환 차단).
5. **정직성** — `member_count`/`analyzed_count` 를 payload·저장 양쪽에 전달.
6. **실패 격리** — 조회·적재 실패가 호출측 트랜잭션을 오염시키지 않음.

## 2. 자동 테스트 — `tests/test_cluster_summary.py`

| 축 | 케이스 |
|---|---|
| A 캐시 | 3중 일치 시 재생성 0 · L1 만 변경 → 재생성 · L0 만 변경 → 재생성 · 멤버셋 변경 → 재생성 · 조회 실패 → 전량 미스 |
| B 정렬 | 순서 무관 동일 지문 · 내용 변경 시 상이 · 빈 입력 = 빈 문자열 · **길이 프리픽스 단사성**(`["a\nb","c"]` ≠ `["a","b\nc"]`) |
| C 비용 | pass 상한 · **schema 루프 잔여 전달**(remaining=2/0) · 배치 크기 · 큰 클러스터 우선 · LLM 실패 시 부분 성공 · 빈약 응답 미저장 · 정지 스위치 · **토큰 예산 배치별 재확인** |
| D 불변식 | 시그니처 빌더 소스에 요약 참조 부재 · 인자에도 부재 |
| E 정직성 | 커버리지 카운트 payload·저장 전달 · 멤버/분석문 cap |
| F 실패격리 | 조회·적재가 SAVEPOINT 사용 · 저장 실패는 made 로 세지 않음 · 증거 키 casefold |

## 3. 실행

```
COMPOSE_PROJECT_NAME=repo make test
```

## 4. 라이브 검증 (배포 후)

1. `alembic_version` = `0051_cluster_summaries` 직접 확인 + GRANT 확인.
2. insight-worker 로그에서 클러스터 pass 후 `cluster_summaries` 행 증가 관측
   (pass 당 최대 40행 — 한 번에 818개가 생기면 상한이 깨진 것이다).
3. 생성된 요약 표본을 직접 읽어 (a) 멤버 나열이 아닌 도메인 서술인지, (b) 입력에 없는 테이블을
   지어내지 않았는지 확인.
4. `analyzed_count < member_count` 인 클러스터의 요약이 과잉 단정하지 않는지 확인.
5. 토큰 예산 소비 증가분이 pass 당 상한과 정합하는지(`llm_usage` task=`cluster_summary`).

## 5. 이번 cycle 의 실행 환경 제약 (정직하게)

`COMPOSE_PROJECT_NAME=repo make test`(정식 경로)를 **끝내 실행하지 못했다** — WSL DNS 가 전면
실패해 docker hub·pypi 어느 쪽에도 닿지 못했다(`auth.docker.io ... i/o timeout`,
`pypi.org ... Temporary failure in name resolution`). 코드와 무관한 환경 장애다.

대신 로컬 python 으로 같은 격리 env 를 주고 실행했다:

| 대상 | 결과 |
|---|---|
| `unit/feature-0002-agent-core/tests` 전체 | **FAILED 0** (psycopg 부재분은 skip) |
| `unit/feature-0033` 신규 `test_cluster_summary.py` | **25 passed** |
| `unit/feature-0023-conversation-api-access/tests` | FAILED 0 |
| `unit/feature-0003-agent-web-ui/tests` | `test_share_redaction_invariant.py` 만 실패 — **psycopg 부재로 인한 알려진 환경성 실패**(main baseline 에서도 동일, feature-0031 TEST.md §5 에 기록됨). 그 외 통과 |
| `ruff check` | All checks passed |

즉 **정식 게이트는 CI(GitHub Actions)** 다. 컨테이너 경로를 대체했다고 주장하지 않는다 —
로컬 실행은 psycopg 의존 경로를 건너뛰므로 커버리지가 좁다. PR 의 CI 결과를 최종 근거로 삼는다.
