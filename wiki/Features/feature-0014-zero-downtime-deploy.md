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
- 2026-08-12 (doc_sync): 08-11 `20260811T1557-edge-rolling-gate` 반영 — 롤링이 **엣지 관점에서는** 무중단이 아니던 근본 결함 수정. 게이트가 컨테이너 내부 `/readyz`(앱이 떴다)까지만 보고 **엣지가 그 replica 를 다시 LB 후보로 쓰는지는 보지 않아**, Caddy 가 실패한 upstream 을 `fail_duration`(30s) 동안 후보에서 빼는 사이 실측 10초 간격 롤링이 다음 replica 를 내려 available upstream 이 0 이 됐다(라이브 6시간 창 실측: `no upstreams available` 71건 · 전면 503 창 6회 × 12~17초 · 503 duration 전부 5.01s = `lb_try_duration` 소진 · 그 창에서 active health 는 양 replica 모두 `host is up` = passive 격리가 유일 원인 · 503 종료 시각이 매 창 "먼저 내린 replica 첫 실패 + 30s" 와 일치). `bin/deploy-web.sh` 에 `wait_edge_available`/`edge_upstream_fails`/`edge_peer_live`/`caddy_fail_duration_s` 를 신설해 판정을 2축(Caddy admin API 의 upstream별 `fails==0` + Caddy 컨테이너에서 그 replica `/livez` 실도달 = active health probe 동일 조건)으로 두고, 배선을 2층(recreate 말미 선제 대기 = 비차단·롤백 경로 보호 / predrain 3조건 fail-closed = 상대 존재·ready·엣지 복귀, 미충족 시 **배포 중단**하고 기존 replica 가 계속 서빙)으로 깔았다. `Caddyfile` 값은 원복이다 — 초안의 `fail_duration` 3s 인하는 실장애 격리를 함께 약화시켜 철회하고 롤링과의 결합 계약만 주석으로 고정했다(30s 유지). `tests/test_edge_rolling_gate.py` 39건 신설 + `pyproject` testpaths 등재(그동안 이 디렉토리는 수집 대상이 아니어서 **배포 스파인 불변식 테스트가 0건**이었다) · 뮤테이션 17종 전건 KILLED · codex 적대 리뷰 5라운드(5R P1 1건은 성립 전제를 실측 반박 후 근거 기록 + 전제 테스트 잠금으로 수용). **POST-DEPLOY 실증(2026-08-11 17:30~17:35 배포 창)**: `no upstreams available` **0건**(수정 전 동일 규모 창 8건 · 12:40 배포는 111요청 중 503×8·502×1·끊김×1 로 전면 503 13초) · 배포 창 요청 172건 전부 200 · 게이트 실발동 로그 확인("web-b 엣지 passive fails=1 격리 해제 대기" 반복 후 "복귀 확인(fails=0 + Caddy→web-b /livez 200)") · `Caddyfile` 변경 동반 caddy recreate 창에서도 5xx 0. 위 §2 상태·`maturity` 는 이번 창 근거만으로 재판정하지 않았다(정본 `feature_status` 소관). 요지+포인터만(SSOT) — 정본 `unit/feature-0014-zero-downtime-deploy/docs/{TASK,MODIFY,REPORT}.md`.
