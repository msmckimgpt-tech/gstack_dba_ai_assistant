---
doc_type: ANCHOR
feature_id: feature-0020-zd-deploy-all
created_at: 2026-07-14T01:20:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0020-zd-deploy-all — 무중단 배포 커버리지 완성

## §1. 외부 관점 요약
"web 무중단(0014)·PG PAUSE(0016-zd)까지 있는데 뭐가 더 필요하지? 워커는 백그라운드인데
재시작 좀 되면 어때서?" → 실측 gap: 워커(insight/ask) 코드 배포가 deploy 스파인 밖의
**수동·무게이트** 경로였다(deploy-web 은 WARN 만 — 배포에서 워커 재빌드를 놓치면 워커가
구코드로 계속 도는 실마찰이 2026-07-13 attach-user-version 회고에 기록됨). LLM 단일 관문
bedrock-gateway 는 재배포(이미지/설정 변경, 라이브에서 실제 발생) 창에 대화 요청이 실패하는
SPOF 였고, `alembic-migrate.sh` 직접 호출은 stale 이미지로 head 를 오판할 수 있었다(2026-07-02
마이그 0030 실측 회귀의 잔존 경로). 즉 "배포가 필요한 모든 부분"의 무중단은 web 만 완성돼
있었고, 본 feature 는 나머지를 같은 스파인·같은 패턴(build-once·SHA핀·게이트·last-good)으로
완성한다. 새 인프라를 만들지 않고 검증된 스파인을 확장하는 것이 복잡도의 핵심 절제다.

## §2. 대안 분기
- **Alt-A: 별도 `deploy-backend.sh` 신설.** 페르소나: 관심사 분리 선호. 안 고른 이유: flock
  직렬화·coalesce·빌드 게이트·sudoers 경계를 통째로 중복하고, web/워커 배포가 두 락으로 갈려
  순서 보장(migrate→web→worker)이 깨진다. 스파인 확장이 더 작고 원자적.
- **Alt-B: bedrock-gateway 상시 2-replica.** 페르소나: 상시 HA 선호. 안 고른 이유: 이 호스트는
  메모리를 조이는 중(라이브 mem_limit 하향 튜닝 실측)이고 gateway 는 OOM 이력(2g)까지 있다.
  상시 2번째 replica 는 steady-state 메모리 비용 결정(사람 몫)이 필요 — 배포 창 한정 surge 는
  비용 0 으로 같은 무중단을 준다. 상시 HA 가 필요해지면 surge 구조가 그대로 밑돌이 된다.
- **Alt-C: 워커도 web 처럼 2-replica 롤링.** 안 고른 이유: 2-replica 는 동시성 계약(advisory
  lock·중복 처리)을 새로 검증해야 하는 위험을 추가한다. 같은 결과를 **quiesce 게이트**(진행 중
  사용자 run 이 0 일 때만 교체, CHG-20260812T140000)로 replica 없이 얻는다 — 유휴 98% 환경이라
  대기 비용이 사실상 0 이다.
  ⚠ **정정(2026-08-12, 실측)**: 초판이 적었던 "짧은 단일 재시작이 이미 사용자 무영향" 은
  **사실이 아니었다**. `ask_jobs` 30일 363건 기준 run 은 p50 81s · p95 691s 이고 워커 drain
  예산은 60s — **60초 초과가 66%** 라 매 배포가 진행 중 답변의 다수를 죽였다. 큐 기반 복구는
  '무영향' 이 아니라 '수 분 뒤 재실행' 이었다. 방향(2-replica 미채택)은 유지하되 그 근거를
  "재시작이 무해해서" 에서 "게이트로 재시작 자체를 조용한 순간에 몰아서" 로 바꾼다.
- **Alt-D: MySQL 도 PG 처럼 PAUSE 래퍼.** 안 고른 이유: MySQL 앞단엔 pgbouncer 같은 pooler 가
  없어 동형 구현 불가(구조적). DDL 은 online-DDL 게이트가 기커버, 엔진 재시작은 0015 ANCHOR 가
  범위 밖으로 고정.

## §3. 가정된 사용 시나리오
개발자 PR 이 머지되어 `sudo -E bin/deploy-web.sh` 가 돈다. 사용자는 대화 중이고 insight-worker
는 야간 분석 cycle 중간이다. web 이 롤링 swap 된 뒤, 워커들이 fresh 이미지로 순차 recreate
된다 — insight 는 루프 경계에서 곱게 내려가고, ask-worker 는 **진행 중 run 이 끝난 뒤에만**
교체된다(quiesce 게이트, CHG-20260812T140000). 조용해지지 않으면 배포는 강행하지 않고 중단하며,
구 워커가 계속 서빙한다.
⚠ **정정(2026-08-12)**: 초판은 "in-flight run 은 lease requeue 로 새 컨테이너가 이어받는다" 고
적었으나, requeue 는 **이어받는 것이 아니라 전량 재실행**이다(부분 산출 이월은 미구현 — conv-audit
원장 `FR-ask-orphan-redeploy-dead-air` 범위 밖 ① 로 이월). 사용자에게는 수 분의 dead air 로
나타났다. 그래서 회수에 기대지 않고 **애초에 죽이지 않는** 게이트를 정본으로 둔다. litellm 설정이 바뀐 배포라면 surge replica 가 먼저 떠서 DNS alias 로
합류한 뒤 본체가 재시작되므로, 그 순간 사용자가 보낸 질문의 LLM 호출도 실패하지 않는다.
사용자는 이번에도 배포 사실을 모른다 — 그리고 운영자는 "워커 재빌드 했던가?" 를 더 이상
기억할 필요가 없다.

## §4. 외부 검증 로그 (append-only)
(엔트리 없음)
