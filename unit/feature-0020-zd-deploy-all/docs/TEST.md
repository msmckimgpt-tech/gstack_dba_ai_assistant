---
doc_type: TEST
feature_id: feature-0020-zd-deploy-all
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- deploy 스파인 확장(워커 롤아웃·gateway surge·caddy 이미지 드리프트·scope 플래그)의
  정적 검증(bash -n)·dry-run 전 경로·compose config 정합(±deploy-surge profile)·pin overlay 병합.
- 라이브 재배포 검증(§16.3 deploy-backed 완료 기준): cycle-finalize 후 main 에서
  `sudo -E bin/deploy-web.sh` 실배포 — web soak·워커 healthy·gateway 무접촉/교체.
- 제외: 웹/UI 표면 없음 — **Windows-browser 검증 N/A (UI 표면 없는 배포 인프라 변경,
  §15.4.1 예외 사유 명시)**. MySQL/PG 엔진 재시작·HA (out of scope).

## 2. Test Cases
- TEST-20260714T104500-zd-deploy-all-1: `bash -n` deploy-web.sh·alembic-migrate.sh 구문 PASS.
- TEST-20260714T104500-zd-deploy-all-2: `docker compose -f docker-compose.yml config -q`
  (base) + `--profile deploy-surge` 모두 PASS, surge 서비스가 base 에서 비활성.
- TEST-20260714T104500-zd-deploy-all-3: pin overlay(web+agent 4핀) 병합 시 insight-worker 에
  `image: mysql-ai-agent:*` 적용 확인.
- TEST-20260714T104500-zd-deploy-all-4: dry-run 4 scope(기본/--workers-only/--web-only/
  --rollback) exit 0 + phase 로그(워커 롤아웃·gateway reconcile·state 무기록) 확인.
- TEST-20260714T104500-zd-deploy-all-5 (라이브, POST-DEPLOY): 실배포 1회 — web-a/b 대상 SHA
  soak PASS, insight/ask `mysql-ai-agent:<sha>` healthy, gateway 드리프트 판정 정상,
  edge /healthz 200 유지.

## 3. Test Run History

### Run 2026-07-14 (구현 cycle, worktree)
- Environment: CLI
- Scope: TEST-…-1 ~ TEST-…-4
- Result:
  - bash -n 2종 PASS.
  - compose config base/±surge-profile PASS (`BASE OK`/`SURGE PROFILE OK`).
  - pin overlay 병합 확인 — merged config 의 insight-worker 에 `image: mysql-ai-agent:test`.
  - dry-run: 기본 scope EXIT=0 (web build→agent build→migrate 게이트→롤링→caddy reconcile→
    soak→워커 롤아웃→gateway reconcile 전 phase 발화), --workers-only EXIT=0 (web 단계 skip),
    --web-only EXIT=0, --rollback EXIT=0 (web 핀 last-good + state 기록 dry 로깅).
  - 발견·수정: TLS preflight caddy 대조 무메시지 사망(cold host 잠복, `ps -q` 가드로 수정) /
    STATE_FILE dry-run 실기록(state_set 무기록화) — REVIEW.md 근거 6.
- Verdict: PASS (정적·dry-run 범위)

<!-- 라이브 Run 은 test-runs.d/ fragment 로 기록 (§5.3) -->

## 4. Untested Areas
- 워커 롤아웃 실패 → agent last-good 자동 롤백 경로: 첫 배포는 last-good 부재라 라이브 재현
  불가(의도적 미주입 실패 실험은 라이브 위험) — dry-run·코드 리뷰로 확인, 차후 배포에서 자연 검증.
- gateway surge 실교체: 본 cycle 은 gateway 드리프트가 없어 무접촉 경로만 라이브 검증
  (교체 경로는 --force-gateway 로 유도 가능하나 라이브 LLM 창 리스크로 보류 — 다음 gateway
  설정 변경 배포에서 자연 검증).
