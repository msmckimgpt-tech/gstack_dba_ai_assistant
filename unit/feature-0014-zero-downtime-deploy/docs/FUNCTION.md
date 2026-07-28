---
doc_type: FUNCTION
feature_id: feature-0014-zero-downtime-deploy
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary
web 서비스를 **무중단(zero-downtime)** 으로 재배포하는 구조를 도입한다. 현재 배포
(`docker compose up -d --no-deps web`)는 단일 web 컨테이너를 recreate 하므로 Caddy 가
그 gap 동안 502 를 반환한다. `deploy_scope: included` 로 머지마다 자동 배포되는 고병렬
환경에서 이 blip 이 빈발한다. 본 기능은 Caddy 뒤에 **2개의 web replica(web-a/web-b)** 를
두고 **한 번에 하나씩 롤링 재시작**하여 항상 ≥1 healthy upstream 을 유지하는 토폴로지와,
그 롤아웃을 안전하게 수행하는 배포 스파인(`bin/deploy-web.sh`)을 구성한다.

본 기능은 단일 호스트 Docker Compose(오케스트레이터 없음) + Caddy + FastAPI 환경에 맞춘다.

## 2. Goal
- REQ-20260630T120000-zero-downtime-web: web 재배포 시 비-스트리밍 경로(주 채팅 `/api/ask`
  포함)에 대해 사용자 체감 중단 0(zero-502)을 달성한다.
- REQ-20260630T120001-safe-unattended-deploy: `deploy_scope: included` 자동 배포 경로에서
  고병렬(동시 머지) 상황에도 안전하게(직렬화·롤백·검증) 무인 배포가 가능하다.
- REQ-20260630T120002-migration-safety: 두 web 버전이 공유 DB 에 잠시 공존하는 롤아웃
  창에서 스키마 비호환(expand/contract 위반)을 게이트로 차단한다.
- REQ-20260713T073141-deploy-verify-checklist (**Minor §12.3** — 문서 + output-only 스크립트,
  배포 로직 무변경): 배포 후 사용자 인수 전 검증을 5항목 체크리스트로 상시화한다 —
  ① 배포 완료(merge≠배포완료) ② 워커 재빌드 판정(deploy-web 은 web 만 재배포) ③ 정적 자산
  캐시 무효화(하드 리프레시) ④ 실 사용자 표면(UI 경로) PB-0008 검증 ⑤ 통과 후에만 완료 보고.
  `bin/deploy-web.sh` 가 "배포 완료" 직후 `post_deploy_checklist` 로 요약 출력하고(output-only),
  정본은 RUNBOOK.md §10. 근거: 2026-07-13 feature-0003 attach-user-version 회고(배포 전 테스트·
  워커 미반영·백엔드만 검증 3중 마찰). AC-DVC-1 ~ AC-DVC-3.
  - AC-DVC-1: `bin/deploy-web.sh` 에 `post_deploy_checklist()` 가 존재하고 성공 배포 완료 직후
    호출된다(dry-run 은 skip). 5항목을 stderr 로 출력하며 **배포 판정/제어 흐름에 영향 없다**(output-only, `bash -n` PASS).
  - AC-DVC-2: RUNBOOK.md §10 에 5항목 체크리스트(판정 기준 표) + 워커 코드 판정 가이드(#2 보조)가 문서화된다.
  - AC-DVC-3: LEARNINGS.md 에 회고(LRN)가 기록되어 후속 세션이 동일 마찰을 반복하지 않는다.

## 3. In Scope
- Caddy 2-upstream 로드밸런싱 + active health + dial-retry 토폴로지 (Caddyfile).
- `web` → `web-a`/`web-b` compose 분할 (동일 이미지/cert/healthcheck).
- 배포 스파인 `bin/deploy-web.sh`: flock 직렬화·origin/main coalesce, scoped-sudo 단일 경계,
  프로덕션 file-set 격리, TLS preflight, build-once tag-by-commit + last-good,
  migrate 순서 소유, one-at-a-time 롤링, post-cutover soak + 자동 롤백.
- 마이그레이션 안전 게이트 `bin/migrate-lint.sh` + CONVENTIONS expand/contract 규칙.
- `/readyz`(심층) + `/livez`(no-DB) probe + active-stream 카운터 (app.py).
- SSE pre-drain 게이트, 정적 자산 content-hash fingerprint.
- `:18080` web 직접 접속 문 **폐기** → 모든 외부/LAN 접속 Caddy `:443` 단일화.
- cycle-finalize 자동 배포 단계를 deploy-web.sh 로 전환.

## 4. Out of Scope
- 오케스트레이터(Swarm/k8s) 도입.
- DB(MySQL/PG) 자체의 HA/replica 무중단 (KB replica 는 feature-0002 T5 별건).
- worker(ask-worker/insight-worker) 의 무중단 재시작 — web 롤아웃은 `--no-deps`+web 만
  지정하여 worker 를 건드리지 않음. worker GIT_COMMIT divergence 는 WARN + quiet-time 재빌드.
- insight-worker graceful SIGTERM 핸들러 추가 (별건 — web 배포가 worker 를 죽이지 않으므로
  무중단에 불필요).

## 5. Inputs
- 배포 트리거: cycle-finalize(PR 머지 후, deploy_scope: included) 또는 수동 `make web`.
- `origin/main` HEAD commit (배포 대상 — caller worktree commit 아님, coalesce).
- env: `WEB_PUBLIC_HOST`, cert(`artifacts/certs/<host>/{fullchain,privkey}.pem`, `rootCA.pem`).
- scoped NOPASSWD sudoers (wrapper 한정) — 무인 배포 전제.

## 6. Outputs
- Caddy 를 통한 무중단 web 롤아웃 (비-SSE zero-502).
- 이미지 태그: `mysql-ai-web:<git_commit>` / `:last-good` / `:current` (keep-3).
- 상태 파일: `artifacts/locks/deploy-web.lock`, `artifacts/deploy/deploy-web.state`,
  `deploy-web.last-good`.
- 배포/롤백 로그 + REPORT.md 기록.

## 7. Main Flow
1. cycle-finalize 또는 수동 호출 → `sudo -E bin/deploy-web.sh`.
2. flock 획득(전체 배포 감쌈) → `git fetch` → 배포 대상 = `origin/main` HEAD 로 coalesce.
3. 프로덕션 file-set 격리 단언 + TLS preflight + migrate-lint + sudo/ownership preflight.
4. build-once(tag by commit) → migrate(expand) → 양 replica 가 아직 OLD 인지 확인.
5. one-at-a-time: 대상 replica pre-drain(상대 healthy 확인 + active-stream 종료 대기) →
   Caddy rotation 제거 → SIGTERM/recreate → `/readyz`+git_commit 게이트 → 다음 replica.
6. post-cutover soak(60~120s, RestartCount/edge 감시) → 통과 시 OLD 이미지 정리, 실패 시
   last-good 자동 롤백.
7. flock 해제 + REPORT 기록.

## 정적 자산 캐시 무결성 (asset-stamp-cache-integrity, 2026-07-28)

무중단 롤링 배포의 **부수 효과 하나가 사용자 브라우저에 영구 잔존**할 수 있었다. 본 절이 그
경로를 봉인한다.

**REQ-20260728-asset-stamp-cache-integrity** (사용자 지시 — 직전 graph-noise-reduction 배포에서
"서버는 신 코드를 서빙하는데 브라우저만 구버전 렌더" 실측 후 근본 해소 요청, **Major §12.3** —
엣지 설정 + 전역 캐싱 semantics; 데이터·스키마·API 무변경):

- **불변식(AC-ASCI-1)**: 정적 자산 응답이 `Cache-Control: …immutable` 로 표시되려면
  **응답한 replica 의 빌드 스탬프 == 요청 URL 의 `?v=`** 여야 한다. 불일치 응답은 `no-store`
  (+ 관측용 `X-Asset-Stamp: mismatch`). → 버전이 어긋난 응답은 **애초에 캐시에 들어가지 못한다**.
- **AC-ASCI-2 (빌드 스탬프 출처)**: `scripts/inject_asset_stamp.py` 가 주입한 content-hash 를
  `<static>/.asset-stamp` 사이드카로 기록한다. 사이드카는 해시 입력·재작성 대상에서 제외되어
  멱등성을 유지한다(자기 참조 시 롤아웃마다 전 캐시 무효화).
- **AC-ASCI-3 (판정 주체 = upstream)**: 판정은 `web/static_cache.StaticCacheHeadersMiddleware`
  (순수 ASGI 래퍼, `/static` mount 를 감쌈)가 수행한다. **엣지(Caddy)는 `/static` 에
  `Cache-Control` 을 강제하지 않는다** — 엣지는 `?v=` 값이 *응답한 replica 의 빌드*인지 알 수 없고,
  강제하면 upstream 판정을 덮어써 불변식이 무력화된다.
- **AC-ASCI-4 (기존 동작 보존)**: `?v=` 없는 자산은 종전 ETag/304 조건부 GET, `vendor/**` 의
  라이브러리 pin(`?v=5.1.1`)은 종전 `immutable`(빌드 해시와 다른 버전 축 — 비교하면 상시 불일치가
  되어 vendor 캐시를 통째로 잃는다).
- **AC-ASCI-5 (fail-safe 방향)**: 사이드카 부재(dev·미주입 빌드)·판정 예외·비-HTTP scope 는
  헤더 미설정으로 통과한다 — 실패 방향이 "캐싱 상실"(성능)이지 "오염"(correctness)이 아니다.

**배경(왜 필요한가)**: 정적 파일은 각 replica 로컬 FS 에서 **경로만으로** 서빙된다(쿼리스트링은
파일 조회에 무관). 롤링 창에서 sticky(`lb_policy cookie weblb`)로 고정된 replica 가 recreate 되면
LB 가 클라이언트를 재배정하고, 그 순간 **구 replica 가 `?v=<신 스탬프>` 요청에 구 바이트로 200
응답**할 수 있다. 종전 엣지 규칙은 `?v=` 의 존재만 보고 `immutable` 을 부여했으므로 그 응답이
**1년 고착**됐다(ES module 진입점이 굳으면 import 체인 전체가 구버전).

**한계(정직 표기)**: 롤링 창 자체는 남는다 — 창 안에서 버전이 섞인 페이지를 한 번 볼 수 있고,
달라진 것은 그 상태가 캐시에 굳지 않는다는 점이다(다음 로드에서 수렴). 창까지 없애려면
content-addressed 경로(`/static/<hash>/…` + 구버전 retention)가 필요하며 후속 과제다.

## Pre-approved Changes
- deploy_scope: included (전역 FIRST_REQUEST.md 상속) — cycle-final 후 자동 배포.
- reachability_scope: included — 본 기능은 bring-up/도달성이 완료 기준의 핵심이므로,
  완료 시 공개 entry-point(`https://WEB_PUBLIC_HOST/healthz`) end-to-end 도달성 검증 포함.
- release_notes_scope: included — 배포 구조 변경이므로 릴리즈노트 동반.

> **주의 — 라이브 검증 한계**: 실제 롤링 배포의 zero-502 부하 테스트와 non-root WSL2 호스트
> dry-run 은 **운영자가 실 호스트에서 수행**해야 한다. 본 개발 환경(root + NOPASSWD:ALL)은
> sudo/소유권 경계 문제를 은폐하므로 dry-run 이 거짓 통과한다 (적대적 검증 unattended-fit 발견).
