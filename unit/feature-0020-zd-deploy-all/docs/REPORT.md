---
doc_type: REPORT
feature_id: feature-0020-zd-deploy-all
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
무중단 배포 커버리지 완성 cycle. 기존 feature-0014/0015/0016-zd/0017 이 web 롤링·워커
graceful·PG PAUSE·빌드 게이트를 구축했지만, 워커(insight/ask) **배포 자체**는 수동·무게이트
(WARN-only)였고 bedrock-gateway 재배포는 LLM SPOF, alembic 직접 호출은 stale-image 위험이
남아 있었다. 본 cycle 이 deploy 스파인을 확장해 `make deploy-web`(=deploy-all) 1회로
web·워커·gateway·caddy 전부가 무중단/near-zero 롤아웃되도록 완성.

## 2. Progress
- Planned: —
- In Progress: —
- Done: T1~T8 전체 (gap 분석·구현·적대 패널 반영·PR #780 머지·라이브 배포·POST-DEPLOY 검증 PASS)

## 3. Recent Changes
- CHG-20260714T104500 참조 (MODIFY.md) — deploy-web.sh 워커/gateway phase, compose surge·
  healthcheck 견고화·live-truth 채택, alembic 가드, Makefile 타깃.

## 4. Known Limitations / Out of Scope
- DB 엔진(MySQL/PG) HA·failover·호스트 무중단 — 단일 호스트 SPOF (0015 ANCHOR 유지).
- MySQL 엔진 재시작 near-zero 래퍼 — 앞단 pooler 부재로 구조적 불가 (DDL 은 online-DDL 게이트).
- bedrock-gateway **상시** 2-replica — 메모리 예산 사람 결정 필요 (surge 구조가 밑돌).
- mcp/browser/embed-ollama/minio/pgbouncer 재시작 blip — 내부 보조 도구/드문 이벤트로 수용.

## 5. Risks
- insight-worker `restart: on-failure:3` (live-truth 채택분): 크래시 3회 후 자동재시작 정지 —
  운영자 폭주 억제 의도로 보존. 장기 방치 시 워커 정지 상태가 지속될 수 있어 healthcheck
  모니터링 병행 필요.
- 워커 이미지 핀 전환 첫 배포는 agent last-good 부재(자동 롤백 불가) — 본 cycle POST-DEPLOY
  를 attended 로 수행.
- main worktree 의 미커밋 compose 변경은 본 PR 에 verbatim 포함 — 머지 후 main pull 시
  로컬 diff 가 병합본과 동일해 자연 clean 예상. untracked 잔여물 4건은 별건
  (meta/FOREIGN_CHANGE_ALERT.md pending).

## 6. Follow-ups
- (선택) bedrock-gateway 상시 2-replica — 메모리 헤드룸 확보 시.
- (선택) 워커 divergence 주기 감시 cron (스파인 밖 수동 recreate 드리프트 감지).
- wiki Features 카드 신설·_Index 카운트 반영은 doc_sync 정합 대상(선례) — unit
  WIKI_CARD.md 는 본 cycle 이 작성.

## 7. Git 동기화 결과
- 커밋: 6d7a44d4(rebase 후) → PR #780 → main eaba795a 머지 (2026-07-14)
- verify-completion: PASS (pre-commit, check #9 는 §18.8 패널 entry 로 충족)
- Push / main 병합: 완료 (cycle-finalize --pr 780, merge mutex 경유)
- 충돌 해결: 없음 (origin/main 19커밋 전진분 rebase 무충돌; wiki/hot.md 는 additive 재구성)
- 라이브 배포: `sudo -E bin/deploy-web.sh` exit 0 — web/워커 eaba795a healthy·edge 200·gateway 무접촉 (POST-DEPLOY 상세: docs/test-runs.d/TEST-20260714T104500-zd-deploy-all-5.md)

## 8. 후속 — quiesce 게이트 (CHG-20260812T140000)
- **계기**: conv-audit `FR-llm-transient-failure-kills-run`(2026-08-12 라이브 사고) 대응 중 사용자가
  "배포 이슈의 원인을 근본적으로 해소할 완벽한 무중단 배포 환경" 을 먼저 요구.
- **드러난 사실**: 본 feature 가 완성했다고 선언한 무중단은 **web 에만** 실제 게이트가 있었다.
  워커·gateway 는 `stop_grace_period` 타이머로만 교체됐고, 실측이 그 예산이 분포 안쪽임을 보였다
  — `ask_jobs` 363건 p50 81s · p95 691s · **60초 초과 66%** vs ask-worker drain 60s.
  즉 §1 이 "web 만 완성돼 있었다" 고 지적한 바로 그 gap 이 워커·gateway 안에 **한 층 더** 있었다.
- **해소**: 진행 중 사용자 run(ask_jobs running + web active_streams)이 0 일 때만 교체하는
  fail-closed 게이트. 유휴 98% 환경이라 대부분의 배포는 즉시 통과한다.
- **cross-ref**: 원장 `docs/improvements/conversation-audit/FRICTION_LEDGER.md`
  (`FR-llm-transient-failure-kills-run` — 앱 층 재시도는 feature-0002 가 소유, 배포 층은 여기).

## 9. 후속 — ask-worker surge 교대 (CHG-20260814T120000)
- **계기**: 사용자 요청 "서비스 내 배포를 모두 무중단으로 진행" 이 **부분 완료**로 끝났고
  (web=신 커밋 / ask-worker·ops-scheduler·ext-tool-mcp=구버전), "배포 및 서비스가 중단되는 이슈가
  없도록 환경을 개선" 하라는 후속 지시.
- **드러난 사실**: §8 이 도입한 quiesce 게이트는 **전역 정적**을 요구했고, 그 창이 낮 시간대에는
  열리지 않았다(유입 7~10분 간격 + run p95 691s vs 상한 900s). 즉 무중단은 지켰지만 **배포 완결을
  포기하는** 방식이었고, 순차 롤아웃의 `return 1` 이 그 대가를 무관한 워커에게까지 전가했다.
  §8 의 처방("조용한 시간에 재실행")은 사람이 창을 노려야 한다는 뜻이고, 이번엔 그 사이
  **보안 게이트(attach-provenance-gate)가 라이브에 도달하지 못했다**.
- **해소**: ask-worker 를 큐 소비자로 다시 보고 **받는 쪽을 먼저 세우는** surge 교대로 전환.
  전역 정적 대기가 구조적으로 불필요해져 무중단과 배포 완결이 동시에 성립한다.
  실패 격리 + 컨테이너 실측 완결 판정으로 "부분 완료를 완료로 보고" 하던 경로도 함께 닫았다.
- **부수 소득**: 배포 무중단 불변식을 잠그던 테스트들이 **CI 에서 한 번도 실행되지 않았음**을
  적발(경로 미등재 + py3.11 collection 불가). feature-0014 가 남긴 교훈의 두 번째 형태 —
  등재만으로는 부족하고 실행 경로와 런타임 문법 호환까지 확인해야 한다.
