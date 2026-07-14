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
- In Progress: T8 라이브 배포 + POST-DEPLOY 검증 (cycle-finalize 후)
- Done: T1~T6 (gap 분석·compose·스파인 확장·alembic 가드·Makefile·검증·문서)

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
- 커밋: (cycle-final 시 기록)
- verify-completion: (pre-commit 시 기록)
- Push / main 병합: (cycle-finalize 시 기록)
