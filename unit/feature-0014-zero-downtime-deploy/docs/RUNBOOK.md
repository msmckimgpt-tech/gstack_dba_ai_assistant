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

## 롤백(설계 자체 되돌리기)
컷오버를 되돌리려면 PR revert 후 `docker compose up -d --no-deps web` 로 단일 web 복귀
(단 base 에 `web` 서비스가 다시 있어야 함). 권장하지 않음 — 무중단 이득 상실.
