---
doc_type: RUNBOOK
feature_id: feature-0014-zero-downtime-deploy
status: active
edit_policy: rewrite
---

# 운영자 컷오버 런북 — 무중단 배포 전환

> 본 PR 의 코드는 worktree 에서 정적 검증을 마쳤다. 그러나 **라이브 토폴로지 컷오버
> (web 단일 → web-a/web-b LB)** 와 **무인 sudo 경계 검증**은 실 호스트에서만 가능하며,
> 본 개발 환경(root + NOPASSWD:ALL)은 sudo/소유권 문제를 은폐하므로 dry-run 이 거짓 통과한다
> (적대적 검증 unattended-fit 발견). 아래 단계는 **운영자가 실 호스트에서** 수행한다.

## 0. 사전 인지 — 이 배포가 깨는 것
- `web` 서비스명이 `web-a`/`web-b` 로 바뀐다. 기존 `docker compose up -d --no-deps web`,
  `make web`(구버전) 등 `web` 를 직접 지칭하던 명령은 더 이상 동작하지 않는다.
- `:18080` web 직접 접속 문이 폐기된다. `https://<host>:18080` 으로 접속하던 외부/LAN
  사용자는 **Caddy `https://mysql-ai.company.local` (:443)** 로 전환해야 한다.

## 1. :18080 폐기 통지 + 정합 (배포 전)
1. `:18080` 직접 접속 사용자에게 Caddy 진입(`https://mysql-ai.company.local`)으로 안내.
2. feature-0006 의 AC-0553/AC-0556(:18080 직접 접속 검증) 을 deprecated 로 표시(후속 doc-sync).
3. (선택) `.env` 의 `WEB_ALLOWED_ORIGINS`/`WEB_ALLOWED_HOSTS` 에서 `:18080` origin 정리(비파괴).

## 2. scoped NOPASSWD sudoers 설정 (무인 배포 전제, AGENTS.md §22.12 §1)
`bin/deploy-web.sh` 전체를 한 번의 권한 전환으로 실행한다. 다음을 1회 설정:
```
# /etc/sudoers.d/deploy-web  (visudo 로 편집)
<deploy-user> ALL=(root) NOPASSWD: /root/download/docker/mysql_ai_delegated_dev/repo/bin/deploy-web.sh
```
- **금지**: `NOPASSWD: ALL`, `NOPASSWD: docker`. wrapper(deploy-web.sh) 1개로만 한정.
- 확인: `sudo -n /root/.../repo/bin/deploy-web.sh --help` 가 비밀번호 없이 동작.

## 3. cron/headless 환경 위생 (무인 실행 시, §22.12 §3)
- git identity, TZ, `$HOME`/`$PATH`, claude 자격(chmod 600) 가 무인 셸에 존재하는지 확인.

## 4. 감독 dry-run (실 non-root 호스트, 1회)
**반드시 docker 그룹 미소속 deploy-user 로** (root/NOPASSWD:ALL 에서 하면 sudo 문제 은폐):
```
cd /root/download/docker/mysql_ai_delegated_dev/repo
sudo -E bin/deploy-web.sh --dry-run
```
확인 항목:
- preflight(권한/file-set/TLS) 통과, 대상 SHA = origin/main HEAD,
- `-f docker-compose.yml` ONLY 로 web-a/web-b 에 호스트포트 없음 단언 통과,
- migrate-lint → migrate → build → one-at-a-time → soak 순서가 출력.

## 5. 최초 컷오버 (단일 web → web-a/web-b)
```
cd /root/download/docker/mysql_ai_delegated_dev/repo
git pull --ff-only origin main          # feature-0014 머지 반영
sudo -E bin/deploy-web.sh               # 초기엔 web-a/web-b 동시 기동 + caddy
```
- 컷오버 직후: `curl -sk --resolve mysql-ai.company.local:443:127.0.0.1 https://mysql-ai.company.local/healthz` → 200.
- 구 `web` 컨테이너가 남아 있으면 `docker compose -f docker-compose.yml rm -sf web` 로 정리(있을 때만).

## 6. zero-502 부하 검증 (수용 기준)
별 터미널에서 연속 요청을 돌리며 롤링 배포를 1회 수행, **502 가 0** 인지 확인:
```
# 부하 루프 (별 터미널)
while true; do curl -sk -o /dev/null -w '%{http_code}\n' \
  --resolve mysql-ai.company.local:443:127.0.0.1 https://mysql-ai.company.local/healthz; done | sort | uniq -c
# 동시에 롤링 재배포
sudo -E bin/deploy-web.sh
```
- 기대: 200 만 카운트(502/000 = 0). round_robin 이 web-a/web-b 양쪽 신규 git_commit 도달.
- SSE: admin 프롬프트 자동작성 진행 중이면 deploy-web.sh 가 해당 replica 의 active_streams==0
  까지 대기 후 recreate (pre-drain). TEST.md §3 에 Run 기록.

## 7. 롤백 검증
일부러 깨진 이미지(예: 잘못된 커밋)로 배포 시 soak 가 RestartCount/edge 이상을 감지하고
last-good 으로 자동 롤백하는지 확인. 수동 롤백: `make web-rollback`.

## 8. 자동 배포 연결 (deploy_scope: included)
컷오버 검증 후, cycle-finalize/머지 후 자동 배포 단계가 `sudo -E bin/deploy-web.sh` 를
호출하도록 운영 절차(FIRST_REQUEST.md 의 배포 명령)를 갱신한다. 그 전까지는 수동 호출.

## 9. worker 빌드 (divergence 발생 시, quiet-time)
web 배포는 worker(insight/ask)를 건드리지 않는다. `deploy-web.sh` 가 worker GIT_COMMIT
divergence 를 WARN 하면, 한가한 시간에:
```
docker compose -f docker-compose.yml build insight-worker ask-worker
# insight-worker 는 SIGTERM 핸들러가 없으니 healthcheck heartbeat 가 idle(사이클 사이)일 때 recreate
docker compose -f docker-compose.yml up -d --no-deps insight-worker ask-worker
```

## 10. 배포 검증 체크리스트 (사용자 인수 전 필수)

`bin/deploy-web.sh` 는 "배포 완료" 직후 이 체크리스트를 요약 출력한다(`post_deploy_checklist`,
output-only). 아래는 그 정본이며, AI·운영자는 **사용자에게 "배포·검증 완료"를 보고하기 전**
5개 항목을 모두 통과시킨다.

> **회고 근거 (2026-07-13, feature-0003 attach-user-version)**: 사용자가 재업로드 버전 관리를
> 테스트했으나 실패 보고. 조사 결과 **테스트가 배포 ~1시간 전(구코드)에 수행**됐고(merge≠배포완료),
> 또한 그 기능의 assistant 인지 로직은 **ask-worker 에 거주**하는데 web 배포만으론 반영되지 않으며
> (worker 재빌드 필요), 완료 검증(PB-0008)이 **백엔드 fetch 경로만 타 client-only 경로를 놓쳤다**.
> 세 마찰을 다음 체크리스트로 상시화한다.

| # | 항목 | 판정 |
|---|------|------|
| 1 | **배포 완료 확인** | web-a·web-b 가 대상 SHA(origin/main HEAD) + soak 통과. **merge ≠ 배포 완료** — 병합~배포완료 사이 창은 구코드가 서빙되므로, 이 시점 전에는 기능을 "사용자 테스트 가능"으로 알리지 않는다. |
| 2 | **워커 재빌드 판정** | 변경이 `ask-worker`/`insight-worker` 코드(`agent_core.py`·워커가 쓰는 `modules`·`shared`)에 닿으면, deploy-web 의 `worker GIT_COMMIT != web` WARN 을 확인하고 **그 배포에서 즉시** 재빌드한다(web 배포만으로는 워커 코드 미반영). §9 참조. |
| 3 | **정적 자산 캐시 무효화** | 서빙 HTML 의 `?v=` 스탬프가 변경됐는가(빌드 `inject_asset_stamp.py` content-hash 자동 주입 — deploy-web 의 `asset_stamp_verify` 가 placeholder 잔존을 하드 차단). 사용자에게 **하드 리프레시(Ctrl+F5)** 안내 — stale JS 로 구 동작 관측 방지. |
| 4 | **실 사용자 표면 검증** | 백엔드 API 뿐 아니라 **사용자가 실제로 쓰는 경로**(UI 업로드/클릭 등)를 라이브 배포본에서 PB-0008 로 검증. 백엔드 `fetch`/API 직접 호출만으로는 client-only 결함(프론트 dedup·ES-module 경로 등)을 놓친다. |
| 5 | **완료 보고 시점** | 위 1~4 통과 후에만 "배포·검증 완료"를 사용자에게 보고. 그 전에는 "미배포/검증 중"으로 명시한다. |

### 워커 코드 판정 가이드 (#2 보조)
- **web 만 재배포로 충분**: `unit/feature-0003-agent-web-ui/src`(app.py·routers·static) 등 web 프로세스 전용 변경.
- **워커도 재빌드 필요**: `unit/feature-0002-agent-core/src/agent_core.py`(프롬프트·컨텍스트 주입·LLM 호출)·`modules/insight.py`·워커가 import 하는 `shared/*`·에이전트 루프 로직. 재업로드 버전 관리의 "assistant 변경점 인지"(agent_core `_build_attachment_context_section`)가 대표 사례.

## 롤백(설계 자체 되돌리기)
컷오버를 되돌리려면 PR revert 후 `docker compose up -d --no-deps web` 로 단일 web 복귀
(단 base 에 `web` 서비스가 다시 있어야 함). 권장하지 않음 — 무중단 이득 상실.
