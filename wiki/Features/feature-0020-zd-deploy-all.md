---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
feature_id: feature-0020-zd-deploy-all
linked_unit: unit/feature-0020-zd-deploy-all
sources:
  - ../../unit/feature-0020-zd-deploy-all/docs/FUNCTION.md
---

# Feature — 무중단 배포 커버리지 완성 (zd-deploy-all)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0020-zd-deploy-all/docs/FUNCTION|unit/feature-0020-zd-deploy-all/docs/FUNCTION.md]].

## 1. 한 줄 요약

feature-0014(web 롤링)·0015(graceful/DDL)·0016-zd(PG PAUSE)·0017(빌드게이트) 위에, 배포가
필요한 나머지 전부 — 워커(insight/ask) 자동 롤아웃·bedrock-gateway surge 무중단 교체·caddy
이미지 드리프트·alembic stale-image 가드 — 를 같은 deploy 스파인(`bin/deploy-web.sh`)으로 완성.

## 2. 상태

- **단계**: in-progress
- **마지막 갱신**: 2026-07-14 (정본 `feature_status_date` 기준. 2026-08-12 quiesce 게이트 2 cycle(`ed257c1e` 워커·gateway 교체 게이트 · `9f43c3ca` 배포 스파인 밖 재생성 봉인 — `bin/lib/quiesce.sh`·`bin/safe-recreate.sh`·`bin/recreate-audit.sh`)과 2026-08-14 ask-worker surge 교대(`d1501b68`·`d8b44dce`·`7bf71214`)는 머지·배포·실측됐으나 정본 TASK/STATUS 의 상태 전이가 미반영 — feature-cycle 소관)
- **AI 작업자**: ai/claude/feature-0020-zd-deploy-all

## 3. 책임 경계

- 입력: origin/main HEAD (coalesce), `docker-compose.yml` base file-set, deploy state 파일.
- 출력: `mysql-ai-web:<sha>`(web-a/b)·`mysql-ai-agent:<sha>`(insight/ask) 핀 롤아웃,
  (드리프트 시) gateway surge 교체·caddy recreate. `make deploy-all`=`deploy-web`.
- side-effect: `artifacts/deploy/` state(key=value)·last-good 태그 회전·keep-N prune.
- Out of scope: DB HA/엔진 재시작·호스트 무중단(0015 ANCHOR)·gateway 상시 2-replica.

## 4. 관련 정본

- [[../../unit/feature-0020-zd-deploy-all/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0020-zd-deploy-all/docs/TASK|TASK.md]] — 작업 컨텍스트
- [[../../unit/feature-0020-zd-deploy-all/docs/ANCHOR|ANCHOR.md]] — 외부 관점·대안 분기
- [[../../unit/feature-0014-zero-downtime-deploy/docs/RUNBOOK|feature-0014 RUNBOOK.md]] — 배포 운영 절차(§9 개정)

## 5. 관련 노트

- [[feature-0014-zero-downtime-deploy]] · [[feature-0015-zd-hygiene-backup]] ·
  [[feature-0016-zd-pg-pause-caddy]] · [[feature-0017-deploy-build-gate]] — 선행 무중단군

## 6. Open questions / 미해결

- bedrock-gateway 상시 2-replica (메모리 예산 — 사람 결정)
- 첫 배포 이후 agent last-good 축적 → 워커 자동 롤백 경로 라이브 자연 검증

## 7. 변경 이력 (이 카드)

- 2026-07-14: 카드 생성 (feature 신규 — cycle ai/claude/feature-0020-zd-deploy-all)
- 2026-08-17 (doc_sync): **ask-worker surge 교대로 바쁜 시간대 배포 완결**(2026-08-14, `d1501b68`
  → 자가 검증 `7bf71214`) 반영. 전역 quiesce 게이트는 "진행 중 사용자 run 이 **시스템 전체에서 0**"
  을 요구했는데 라이브 실측 유입 간격 7~10분 · run p95 691s 라 낮 시간대에는 상한 900s 안에 그런
  창이 생기지 않았다 → ask-worker 가 배포되지 못했고 순차 롤아웃의 `return 1` 이 사용자 run 과
  **무관한** ops-scheduler·ext-tool-mcp 까지 연쇄로 구버전에 묶었다(2026-08-14 부분 완료 배포).
  ask-worker 는 HTTP 소켓이 아니라 PG 큐 소비자이고 claim 이 `FOR UPDATE SKIP LOCKED` + lease
  fencing 이라 다중 인스턴스가 exactly-once → **"조용해지기를 기다린다" 가 아니라 "받는 쪽을 먼저
  세운다"** 로 전환: surge healthy → 본체 drain(신규 claim 중지 + in-flight 완주) → 본체 교체 →
  surge 정리. `ask-worker-surge` 서비스(profile `deploy-surge` · restart no · 본체 대칭
  stop_grace) · drain 예산 60s→**1800s** / stop_grace 70s→1830s(종전 값은 실측 run 의 66%를 못
  덮었다) · 실패 격리(본체 무접촉 중단 rc 2 는 나머지 워커를 막지 않고 이미지 결함 rc 1 만 롤백) ·
  완결 판정은 **컨테이너 GIT_COMMIT 재판독 후에만** `agent_current` 기록 · liveness 는 role 전역
  KV(surge 공존 창에서 false-pass/false-fail) 대신 컨테이너-local alive 파일 + 메인 루프 분리
  스레드. 부수 발견: CI 와 `make test` 가 pytest 경로를 명시해 **testpaths 의 feature-0014/0020 이
  한 번도 실행되지 않았고** `test_edge_rolling_gate.py` 는 f-string 백슬래시로 py3.11 collection
  불가였다 → 경로 추가 + 3.11 호환 + PyYAML 개발 의존 명시. 자가 검증이 적발한 **관측 결함 2건**이
  이 cycle 의 교훈이다 — D1 `drain_stop_ask` 가 stop **후** `docker compose ps -q`(running 만
  반환)로 재조회해 after 가 항상 0 이었고 "보유 N→0 · 끊긴 run 없음" 이 **어떤 상황에서도 나오는
  문장**이었다(유휴 배포에선 우연히 맞고 바쁜 배포에선 정확히 거짓 안심) → hostname 을 stop
  **전에** 확보 · D2 `ask_surge_cid` 도 `ps -q` 라 "stop 은 됐는데 rm 실패" 형태의 leaked surge 를
  정확히 놓쳤다(다음 `up -d` 로 되살아나 큐에서 다시 일한다) → `ps -aq`. 뮤테이션 11/11 KILLED ·
  feature-0014+0020 101 passed · POST-DEPLOY `73c02c71`(교대 궤적이 설계 순서대로 관측 · 6서비스
  전부 일치 = 종전 'web 만 신 코드' 혼합 미재현 · surge 잔존 0 · 엣지 `no upstreams available` 0 ·
  강행 카운터 0). **정직**: 배포 시점 running=0(유휴)이라 "바쁠 때 기다리지 않고 완결" 궤적은 아직
  **미관측**이고, 내려간 본체는 구 이미지라 구 drain 시맨틱(60s)으로 동작해 신 예산은 다음
  배포부터 적용된다. 정본 `unit/feature-0020-zd-deploy-all/docs/{FUNCTION,MODIFY,TEST}.md` ·
  `bin/deploy-web.sh` · `docker-compose.yml`(ask-worker-surge).
