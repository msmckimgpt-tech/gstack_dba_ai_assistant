---
run_at: 2026-07-14T12:55:00+09:00
session: ai/claude/feature-0020-zd-deploy-all (claude-session-2811850)
scope: TEST-20260714T104500-zd-deploy-all-5 (라이브 POST-DEPLOY)
verdict: PASS
---

# Run 2026-07-14 — 라이브 전체 롤아웃 (main eaba795a, PR #780 머지 직후)

- Environment: CLI (배포 인프라 — UI 표면 없음)
- 명령: `sudo -E bin/deploy-web.sh` (main worktree, scope=all) — exit 0
- 결과:
  - web 이미지·agent 이미지 build-once PASS (snap-docker metadata-race 2건 모두 게이트가 양성 무시 — 이미지+GIT_COMMIT 정합 확인 경로 실동작).
  - migrate 게이트+적용(image=mysql-ai-web:eaba795a) PASS.
  - web-a/web-b one-at-a-time 롤링(pre-drain 포함) → soak 90s PASS. edge `/healthz` 200 (Caddy 경유).
  - **워커 롤아웃 완료**: insight-worker·ask-worker = `mysql-ai-agent:eaba795a` **healthy** + GIT_COMMIT 게이트 일치 — 배포 전 16h unhealthy(hc timeout 오탐)이던 두 워커가 신규 컨테이너에서 healthy 로 회복(timeout 30s 견고화 유효).
  - gateway reconcile: 드리프트 없음 — 무접촉(blip 0), `gateway_config_sha` state 최초 기록.
  - state: `current=eaba795a` / `agent_current=eaba795a` (key=value 다중 state 실동작).
  - live-truth env 보존 확인: 재생성된 insight-worker 에 AGENT_DISABLE_AUTO_RETRY=1·TICK_SEC=60·PROBE_WORKERS=1·restart on-failure:3 유지(커밋된 compose 로부터 — silent revert 없음).
  - secret 주입: insight-worker 에 KEK/PASSWORD 계열 env 12건 확인.
- 잔여(자연 검증 대기): 워커 실패→last-good 롤백 경로(이번이 첫 핀 배포라 last-good 는 이제부터 축적), gateway surge 실교체(다음 gateway 설정/이미지 변경 배포에서 발동).
