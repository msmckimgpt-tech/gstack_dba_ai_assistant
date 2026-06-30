---
doc_type: REVIEW
feature_id: feature-0014-zero-downtime-deploy
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260630T120000-zero-downtime-deploy
- Related Change: CHG-20260630T120000 (feature-0014 무중단 배포 구조 + deploy-web.sh)
- Reason: `deploy_scope: included` 로 머지마다 web 단일 컨테이너 recreate → Caddy 502 blip 빈발.
  고병렬(5 worktree 동시 머지) 환경에서 사용자 체감 중단을 제거(혹은 최소화)하기 위함.
- Alternatives Considered (설계 워크플로 wf_f176026a 패널·심사 결과):
  - Tier 1(단일 web + Caddy dial-retry): 최저 effort 이나 단일 upstream 이라 retry 가 갈 곳이
    없어 near-zero 도 불확실(judge env_fit 8, zero_downtime 6). host-port 이전은 Tier 2 와
    공유 전제라 Tier 2 직행이 버리는 작업 없음 → **불채택(단독)**.
  - Blue-green by network-alias + caddy reload: alias 토글에 atomic replace 없음, thrash +
    reload 필요로 2-upstream LB 보다 복잡하면서 atomicity 열위(judge total 34) → **불채택**.
  - 오케스트레이터(k8s/Swarm): 단일 WSL2 호스트에 과한 운영부담 + compose 자산 전면 재작성 → **불채택**.
  - **채택: 2-replica Caddy LB 롤링(judge total 41, winner)** — 단일 호스트 compose 에서
    구조적으로 항상 ≥1 healthy upstream 을 보장하는 유일 설계.
- 적대적 검증(9 failure mode) 반영:
  - migration-overlap(HIGH): repo 에 expand/contract 규율 부재(이력상 0009/0015 위반) →
    `bin/migrate-lint.sh`(AST, op.execute 상수 SQL 추적) + CONVENTIONS §12 + deploy-web.sh hard gate.
  - host-port(HIGH): :18080 은 dev 편의가 아니라 feature-0006 테스트 계약 → **Caddy :443 단일화로
    폐기**(사용자 결정), deploy-web.sh `-f docker-compose.yml` only + 호스트포트 부재 단언.
  - deploy-race(HIGH): flock 전체 배포 + origin/main HEAD coalesce(loser 가 최신커밋 누락 안 함)
    + `mkdir -p artifacts/locks` + timeout 시 loser 비-0.
  - caddy-correctness(HIGH): zero-502 의 진짜 lever = dial 실패 retry(passive) — active health 가
    아님. retry-as-primary(lb_try_duration 5s, lb_retries 0) + active는 /livez(DB 무관, 양 replica
    동시 down 방지).
  - unattended-fit(HIGH): §22.12 단일 scoped-sudo 경계(`sudo -E bin/deploy-web.sh`, NOPASSWD wrapper
    한정) + `docker ps` 비대화 preflight + 소유권 정규화. **본 dev 환경(root+NOPASSWD:ALL)은 이
    문제를 은폐**하므로 dry-run 은 운영자 실 호스트 수행(RUNBOOK).
  - tls-sni(MED): 두 replica 공유 cert → correlated 실패. deploy-web.sh TLS preflight(SAN/CA/expiry,
    cert 결함=ABORT(OLD 유지), 이미지 롤백 아님).
  - sse(MED): 클라가 fetch/getReader 라 자동재접속 **없음**(설계의 "reconnect" 표현은 오류) →
    deploy-web.sh pre-drain(대상 replica active_streams==0 대기, /livez 노출). sticky cookie 도 보조.
  - rollback(MED): post-cutover soak(RestartCount/edge 감시) + 자동 롤백 + bad-image vs
    dependency-down 구분(둘 다 503 이면 thrash 금지). 단일 replica 실패 시 fast-path.
  - insight-worker(통과): web 배포는 `--no-deps`+web-a/web-b 만 지정 → worker 무접촉. divergence WARN.
- Risks:
  - 정상상태 +1 컨테이너(~96MB) + active health(/livez) 2s. (mem_limit 1g 내 여유.)
  - **컷오버는 외부영향**(토폴로지/포트/배포 자동화 변경) → 머지·배포는 운영자 confirm 게이트.
  - migrate-lint 는 휴리스틱(보수적 over-flag 가능) — 서명 annotation escape 제공.
- Open Questions: 자산 content-hash fingerprint 를 후속에서 도입할지(현재 sticky LB 로 충분 판단).
- Human Approval Needed: **예 — 이미 PLAN-APPROVED(2026-06-30) 획득**(실행범위 Foundations+Tier2,
  :18080 Caddy 단일화, SSE pre-drain). 단 라이브 머지/배포 컷오버는 RUNBOOK 게이트로 별도 confirm.
- 보안: /livez·/readyz 는 미인증이나 기존 /healthz(TASK-0126)와 동일 수준 정보(git_commit/DB ok)만
  노출(active_streams 카운트 추가 — 비민감). 신규 민감 노출 없음.

## REV-20260630T120500-zero-downtime-panel [AGENT-TEAM: backend+security]
- Related Change: CHG-20260630T120000 (구현 diff 검증 패널 — §18.8)
- Panel: 2 독립 리뷰어 (backend/deploy correctness, security/governance) 가 staged diff 검토.
- Verdict: 보안 PASS(secret/sudo 단일경계/endpoint 노출/TLS preflight 모두 정상, must-fix 없음).
  백엔드 must-fix 2 + should-fix 3 적발 → **전부 반영**:
  - [must] migrate-lint false-negative: `op.execute(sa.text("DROP..."))`·f-string·concat 가 게이트
    통과 → AST 재귀 문자열 수집(`_exec_strings`: Call/JoinedStr/BinOp) + 동적인자 '수동 확인'
    finding. self-test 6/6(텍스트래퍼·f-string 추가), 회귀 0(0009/0015/0023 여전히 적발, baseline PASS).
  - [must] Caddyfile `lb_retries 0` 주석 오인(실제 retry 는 lb_try_duration 구동) → 주석 정정 +
    non-GET mid-request 잔여 창(graceful drain 으로 sub-second) 명시.
  - [should] `worker_divergence_warn` 의 `wsha` 미가드 → 성공 배포가 set -e 로 오실패 → `|| true` 가드.
  - [should] build_image 가 origin/main HEAD checkout 검증 없이 working tree 빌드 → SHA mislabel
    가능 → `resolve_target_sha` 에 HEAD==origin/main assertion(dry-run 은 warn).
  - [should] keep-N prune 가 last-good sha 태그를 지울 수 있음 → `:current`/`:last-good` 안정 태그
    회전 유지 + rollback 이 `:last-good` 태그 사용(prune 내성).
  - [should] :18080 폐기 → feature-0006 AC-0553/0556 정합 → TODOS.md P2 추적 항목 추가.
- Notes(수용): migrate-lint 서명 annotation escape 는 honor-system(§13.2.7 anti-friction, 인가통제
  아님 — 파일 작성자는 이미 신뢰). shutdown 핸들러 주석의 "grace 미설정" 은 stale doc nit(기능 무관).
- Positive 확인: YAML 시퀀스 merge 정확(web-extra 우선), 호스트포트 부재, build-once 핀, SSE 카운터
  try/finally 균형(disconnect 시 aclose 로 해제), /livez(no-DB)·/readyz(DB) 의도대로, flock 전체 직렬화,
  stop_grace 30s 적정(8s finalize + drain).
- Human Approval Needed: 아니오(코드 정합). 단 라이브 컷오버는 RUNBOOK 운영자 게이트.
