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
maturity: minimal
ai_generated: true
feature_id: feature-0015-zd-hygiene-backup
linked_unit: unit/feature-0015-zd-hygiene-backup
created: 2026-06-30
sources:
  - ../../unit/feature-0015-zd-hygiene-backup/docs/FUNCTION.md
---

# Feature — 무중단 위생 + 백업 (zero-downtime hygiene & backup)

> 정본은 [[../../unit/feature-0015-zd-hygiene-backup/docs/FUNCTION|FUNCTION.md]].

## 1. 한 줄 요약
feature-0014(web 무중단) 후속. 무중단 feasibility 분석(wf_1d634d33)이 도출한 "저비용·고효과" 3항목 —
① insight-worker graceful shutdown, ② MySQL online-DDL 강제, ⑤ 백업 복원 리허설+cron — 을 구현해
백엔드/DB 계층의 무중단 위생과 데이터 보존을 보강.

## 2. 상태
- **단계**: review — 코드/정적검증 완료. 배포(insight recreate + cron 설치)는 main repo 에서 수행.
- **마지막 갱신**: 2026-06-30
- **AI 작업자**: claude / Human (PLAN-APPROVED 2026-06-30 "①+②+⑤")

## 3. 책임 경계
- **입력**: SIGTERM(insight) / 신규 MySQL ALTER(lint) / 최신 백업(restore-rehearsal).
- **출력**: insight graceful 종료 / online-DDL 강제·차단 / throwaway DB 복원검증·cron 항목.
- **side-effect**: insight-worker stop_grace_period 30s / 신규 bin 스크립트 3종 / crontab 항목(설치 시).

## 4. 관련 정본
- [[../../unit/feature-0015-zd-hygiene-backup/docs/FUNCTION|FUNCTION.md]] · [[../../unit/feature-0015-zd-hygiene-backup/docs/TASK|TASK.md]] · [[../../unit/feature-0015-zd-hygiene-backup/docs/ANCHOR|ANCHOR.md]]

## 5. 관련 노트
- [[feature-0014-zero-downtime-deploy]] — web 무중단(본 feature 의 모태)
- [[feature-0002-agent-core]] — insight-worker 코드 거주
- [[feature-0001-platform-runtime]] — MySQL/백업 운영 자산

## 6. Open questions / 후속
- ③ pgbouncer PAUSE 래퍼, PG WAL/PITR, bedrock-gateway 2-replica — feasibility 분석의 "투자" 항목.
- DB 엔진/호스트 무중단은 단일 호스트 SPOF 라 범위 밖(HA 는 1인 내부도구엔 over-engineering).

## 7. 변경 이력 (이 카드)
- 2026-06-30: 초안(feature 신규 — ①②⑤ 구현 반영).
