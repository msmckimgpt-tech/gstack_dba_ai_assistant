---
doc_type: TEST
feature_id: feature-0045-zd-bridge-continuity
status: active
edit_policy: append-only
source_of_truth: true
---

# Test

## 1. Strategy

이 기능의 결함은 **조용하다** — 배포는 성공으로 끝나고, 끊긴 것은 사용자의 AI 연결뿐이다.
그래서 텍스트 단정만으로 만족하지 않고 **원문을 실행**해 게이트의 실제 행동을 본다
(`if false;` 나 상수 치환 같은 무력화는 문자열 검사로 잡히지 않는다).

계약을 네 층으로 나눈다:

| 파일 | 무엇을 지키나 |
|---|---|
| `test_bridge_drain.py` | 대기/작업의 **구분** — 합치면 배포가 멈추거나 질문이 죽는다 |
| `test_bridge_deploy_gate.py` | 스파인이 실제로 **기다리는가**(실행 검증) |
| `test_mcp_replica_topology.py` | MCP 표면이 배포를 견디는 구조인가 |
| `test_internal_endpoints.py` | 배포 제어 창구의 **경계**와 **의미** |

## 2. Cases

- 대기·작업 카운터 분리 / 예외 시 감소 / snapshot 단일 출처
- 드레인 멱등 · 해제 복구
- 미들웨어: 도구 호출 계상 · 대기 경로 제외 · 비-도구 경로 무접촉
- 드레인 중 신규 도구 호출 503 + `X-Bridge-Draining` · 대기 경로는 200 유지
- `predrain`: in-flight 대기(3회 폴링) · 대기(waiters)는 즉시 통과 · 강행 기록 · probe 실패 대체
- 드레인 probe 가 `/livez` 미사용 · recreate 실패 시 해제 · 롤링 전 청소
- 회수: 강행 시에만 · grace 창 · `ClaimedBy` 보존
- MCP: 2 replica 동일 정의 · 구 서비스 부재 · stateless · stop_grace > 중계 상한 ·
  엣지 2-upstream · active health 부재 · 어댑터 드레인 재라우팅
- quiesce: 브리지 축 포함 · `unknown` ≠ 조용함 · 브리지 운영에서 영구 차단 없음 ·
  `server_llm_blocked` 기본값(미설정 = 차단) 5케이스

## 3. Runs

### Run 2026-08-27 (Environment: repo-pytest)
- Command: `python3 -m pytest unit/feature-0045-zd-bridge-continuity/tests/ -q`
- Result: **60 passed** (적대 검증 반영 후 — 회귀 가드 10건 + vacuous pass 해소 3건 포함)
- 회귀: `unit/feature-0014-zero-downtime-deploy/tests/`,
  `unit/feature-0020-zd-deploy-all/tests/`, `unit/feature-0041-external-ai-tool-surface/tests/`,
  `unit/feature-0043-external-llm-bridge/tests/` 각각 PASS(개별 실행)

> `test_llm_gate.py` 3건은 feature-0041/0043 스위트를 **함께** 돌릴 때만 실패한다. 원인은
> `modules` 네임스페이스가 feature-0003/0002 사이에서 갈리는 기존 환경 특성이며, `main`
> 에서도 동일하게 재현된다(내 변경 이전 상태에서 확인). 정본 판정은 컨테이너 `make test`.

### Run <TBD> (Environment: live-deploy)
- 배포 로그의 `bridge_continuity_summary` 가 "끊김 0" 을 보고하는지
- 배포 중 개인 AI 의 `wait_for_request` 가 오류 없이 교대하는지

### 검증이 놓쳤던 것 (REV-20260827-0001)

초판 46건은 전부 green 이었는데 P1 6건이 살아 있었다. 세 가지가 **문자열 검사**였기 때문이다:

| 놓친 것 | 왜 통과했나 | 지금은 |
|---|---|---|
| `stateless_http` 가 v2 생성자에 없음 | `assert "stateless_http=True" in src` | `_server_kwargs()` **실행** + 설치 SDK 시그니처 대조 |
| `server_llm_blocked` 항상 unknown | 스텁이 `printf`(exit 0) 라 `printenv` 의 exit 1 경로 미실행 | exec 실패/미설정 sentinel **양측** 케이스 |
| fallback 이 fail-open 헬퍼 사용 | 스텁이 그 헬퍼를 0 으로 덮음 | strict 스텁 2케이스(조용함 / 관측 불가) |

교훈은 하나다 — **"그 이름이 소스에 있다" 와 "그 배선이 런타임에 작동한다" 는 다른 사실이다.**

## 4. Coverage Notes

- **미작성**: 실제 두 replica 를 띄운 상태의 통합 롤링 e2e. 컨테이너 오케스트레이션이 필요해
  단위 층에서 재현하지 않고, 라이브 배포의 `bridge_continuity_summary` 로 대체 관측한다.
- 드레인 중 Caddy 가 실제로 2초 안에 후보를 빼는지는 Caddy 동작이라 여기서 검증하지 않는다
  (설정값 `health_interval 2s` · `health_fails 1` 은 feature-0014 테스트가 잠근다).
