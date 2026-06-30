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
feature_id: feature-0014-zero-downtime-deploy
linked_unit: unit/feature-0014-zero-downtime-deploy
created: 2026-06-30
sources:
  - ../../unit/feature-0014-zero-downtime-deploy/docs/FUNCTION.md
---

# Feature — 무중단 배포 (zero-downtime deploy)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0014-zero-downtime-deploy/docs/FUNCTION|unit/feature-0014-zero-downtime-deploy/docs/FUNCTION.md]].

## 1. 한 줄 요약

web 을 Caddy LB 뒤 **web-a/web-b 2-replica** 로 두고 **한 번에 하나씩 롤링 재시작**해, 머지마다
일어나는 자동 재배포(deploy_scope: included)에도 사용자 체감 중단(502)이 없게 만든다. 롤아웃은
`bin/deploy-web.sh`(직렬화·검증·자동 롤백) 가 수행한다.

## 2. 상태

- **단계**: review — 코드/정적검증 완료. **라이브 토폴로지 컷오버는 운영자 게이트**(sudoers·dry-run·
  :18080 통지·zero-502 부하검증, [[../../unit/feature-0014-zero-downtime-deploy/docs/RUNBOOK|RUNBOOK.md]]).
- **마지막 갱신**: 2026-06-30
- **AI 작업자**: claude / Human (PLAN-APPROVED 2026-06-30 — Foundations+Tier2, :18080 Caddy 단일화, SSE pre-drain)

## 3. 책임 경계

- **입력**: 배포 트리거(cycle-finalize/수동 `make deploy-web`) · origin/main HEAD · cert(`artifacts/certs`) · scoped NOPASSWD sudoers.
- **출력**: 무중단 web 롤아웃(비-SSE zero-502) · 이미지 태그(`mysql-ai-web:<sha>`/`:last-good`) · 상태파일(`artifacts/deploy`, `artifacts/locks`).
- **side-effect**: 토폴로지 변경(web→web-a/web-b) · :18080 직접 문 폐기(Caddy :443 단일) · 신규 엔드포인트 `/livez`·`/readyz`.

## 4. 관련 정본

- [[../../unit/feature-0014-zero-downtime-deploy/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0014-zero-downtime-deploy/docs/TASK|TASK.md]] — 작업 큐 + PLAN-APPROVED
- [[../../unit/feature-0014-zero-downtime-deploy/docs/RUNBOOK|RUNBOOK.md]] — 운영자 컷오버 절차
- [[../../unit/feature-0014-zero-downtime-deploy/docs/ANCHOR|ANCHOR.md]] — 방향성 stable reference

## 5. 관련 노트

- [[feature-0006-lan-proxy-access]] — Caddy(Caddyfile) LB 토폴로지가 거주
- [[feature-0003-agent-web-ui]] — `/livez`·`/readyz`·SSE 카운터(app.py)
- [[feature-0002-agent-core]] — alembic 마이그레이션(migrate-lint 게이트 대상)
- [[../entities/caddy|Caddy]] — TLS 종단 + 2-upstream LB

## 6. Open questions / 미해결

- 자산 버전 스큐: sticky cookie LB 로 차단. 더 강한 보장(content-hash 파일명)은 후속 선택.
- insight-worker SIGTERM graceful 핸들러 부재 — web 배포는 worker 미접촉이라 무중단엔 무관, quiet-time 재빌드 안전성용 후속.
- feature-0006 AC-0553/0556(:18080) deprecated 표기 후속 doc-sync.

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0014-zero-downtime-deploy/docs/MODIFY.md` 에.

- 2026-06-30: 초안 작성 (feature 신규 생성 동반 — 설계+9 적대적 검증 후 P0~P3 구현 반영).
