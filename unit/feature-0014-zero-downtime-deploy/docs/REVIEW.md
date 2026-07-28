---
doc_type: REVIEW
feature_id: feature-0014-zero-downtime-deploy
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260713T073141-deploy-verify-checklist [SKIPPED:output-only-script+doc]
- Related Change: CHG-20260713T073141-deploy-verify-checklist (배포 검증 체크리스트 상시화)
- Panel skip 사유(§18.8): 변경은 ① `bin/deploy-web.sh` 의 **output-only** 함수(`post_deploy_checklist`, stderr echo — 배포 판정/제어 흐름·exit code·마이그/롤백/soak 로직 일절 무변경) ② RUNBOOK.md §10 문서 ③ LEARNINGS/FUNCTION/TASK/MODIFY 문서. 실행 로직·스키마·RBAC·엔드포인트 0 → 적대적 코드 검증 실익 낮음.
- 대신 실질 검증: `bash -n bin/deploy-web.sh` PASS(구문) · `post_deploy_checklist` 는 `[ "$DRY_RUN" -eq 1 ] && return 0` 로 dry-run 무출력 · 호출 지점은 성공 배포 종단(`step "배포 완료"` 직후)뿐 · heredoc(`<<'CKL'`)은 변수 확장 없어 injection 표면 없음.
- 근거·회고: feature-0003 attach-user-version 배포 후 사용자 테스트 실패 조사 → 배포 전 테스트(merge≠배포완료)·ask-worker 미반영·백엔드만 검증 3중 마찰. Cross-ref: FUNCTION/TASK/MODIFY-20260713T073141 · docs/LEARNINGS LRN-20260713-0001 · RUNBOOK §10.

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

## REV-20260711T113717-deploy-flake-hardening [SUBAGENT:improve-fit-reviewer(§18.8, 2-round)] — 배포 스파인 flake 하드닝 (preflight 재시도·soak 확증·rollback 회복 대기)
- Related Change: CHG-20260711T113717-deploy-flake-hardening. cycle: ai/claude-corp/feature-0014-deploy-hardening. 승인: 사용자 지시(2026-07-11 "나머지 작업 재개" — 07-11 배포 인시던트 보고에 대한 진행 지시).
- **패널 1차 VERDICT = NOT-SHIP** — 정직 기록: 검증 도중 세션 자신의 사고(`.env*` 임시 복사 정리의 `rm .env.*` 가 tracked 백업까지 삭제 → 복원에 `git checkout -- .` 사용 → 미커밋 하드닝 diff 동반 소실)로 패널이 "대상 소실 + scope 오염(tracked .env* 12종 삭제 동반)"을 적발. 동시에 **MAJOR-2**: worktree dry-run 재현은 결정적 아티팩트(gitignored env 부재)이지 프로덕션 간헐 원인의 재현이 아님 — "원인 식별" 서술은 범주 오류.
- **재구성 + 패널 노트 전건 반영**: ① diff 를 bin/deploy-web.sh 단일 파일로 재구성(scope 오염 해소) ② blip 회복 시 continue 전 RestartCount 재검(crash-loop 감시 공백 봉인) ③ edge_fail_total 누적 카운터(비연속 flapping 무감 해소, env 튜너블 DEPLOY_WEB_EDGE_FLAP_MAX) ④ dependency_down 은 확증 이후 1회 ⑤ 수동 --rollback 경로에도 60s 회복 대기(경로 일관성) ⑥ 문서 서술을 "진단 계측+transient 재시도·원인 미확정"으로 정정 ⑦ cfg_err 3차 stderr 를 미검출 진단에 포함(NIT).
- **패널 2차 VERDICT = SHIP** — 7개 반영 전건 코드 실증 확인: soak 신규 분기 exhaustive(edge_fail 종단값 0|3 증명) · deadline 감시 공백 봉인 · rc 캡처 쌍/mktemp 정리/encounter-지역 변수 무오염 · exit code 계약 보존 · dry-run 무 hang. 잔여 MINOR-1(flap 임계 decay 없음 — env 튜너블로 반영)·NIT-1(3차 stderr 덤프 — 반영) 비차단 2건도 머지 전 반영 완료.
- 검증: bash -n · worktree dry-run — 실패 경로(3회 재시도 + stderr 원인 문자열 + 정직 die)와 happy path(전 env 존재 시 "OK — 두 replica 정의 확인") 양쪽 실증. 라이브 검증 = 머지 후 본 스크립트로 batch4~6 실배포(soak·edge 경로 통과가 곧 실증).
- Human Approval Needed: 아니오 — 사용자 지시로 착수. fail-safe 방향(감지 지연 없이 오탐만 제거), exit 계약 보존, 비파괴.

## REV-20260711T201156-preflight-sigpipe-rootfix [SKIPPED:root-cause-fix-deterministic] — preflight SIGPIPE race 수정
- Related Change: CHG-20260711T201156-preflight-sigpipe-rootfix. 승인: 사용자 잔여작업 재개 지시 + 직전 하드닝 사이클(§18.8 2-round SHIP)의 연장선.
- SKIPPED 사유: 원인이 진단 덤프로 **결정적으로 특정**(bytes=145,878 완전 출력 + rc=0 + 미검출 = SIGPIPE race 외 설명 불가)되고, 수정은 의미-동일 매칭 대체(파이프 제거)뿐. dry-run 양 경로 실증 + 머지 직후 라이브 배포가 최종 검증.
- Human Approval Needed: 아니오 — 게이트 스크립트 결함 수정(fail-safe 방향 불변).

## REV-20260728T014500-zd-stale-closeout [SKIPPED:docs-only stale 판별 — 코드 무변경]
- Related Change: CHG-20260728-0001 (무중단 배포 계열 23건 stale 확정·정리)
- Panel skip 근거: changeset 이 4 feature 의 `docs/TASK.md` + 본 feature 의 MODIFY/REVIEW
  뿐이고 제품 코드·자산·설정 무변경(§18.8 dispatch 비매칭). 새 판단이 아니라 **이미 랜딩된
  작업의 증거를 대조해 체크박스를 닫는** 사무적 정리다.
- 판별 방법 (문서 대조가 아닌 라이브 실측을 택한 이유): TASK.md 항목은 "배포했다"·"검증했다"
  같은 **행위 서술**이라 문서만 봐서는 참·거짓을 가릴 수 없다. 그래서 각 항목이 주장하는
  **결과물이 지금 실재하는지**를 직접 확인했다 — 스크립트 파일 존재, HTTP 응답 코드,
  컨테이너 가동 상태, cron entry 수. `:18080` 폐기처럼 "없어야 정상" 인 항목은 무응답을
  확인했다.
- 남긴 것: 각 feature 에 정형 Completion Checklist 1건씩만 남는다. 이는 feature 가
  `in-progress` 인 한 정상이며, 닫으려면 feature 자체를 done 으로 선언해야 한다 — 그 판단은
  본 cycle 범위 밖(운영 정책 결정).
- Open Questions: 같은 집계에서 **방치 판정된 나머지 13건**은 성격이 달라 닫지 않았다 —
  feature-0012(8건)는 실제 미완 이연 작업(P5b Final·프론트 분할), feature-0011·0010 은 명시적
  후속/비활성 토대, feature-0001/0004/0005 의 "엄격한 시나리오 확정"(각 1건)은 template
  skeleton 정형 항목이다. 이들은 실제 작업이거나 정책 판단이 필요해 별도로 다뤄야 한다.

## REV-20260728T123000-asset-stamp-cache-integrity [SKIPPED:session-policy-no-subagent] — 롤링 배포 캐시 오염 근본 해소
- Date: 2026-07-28 · Session: `ai/claude/feature-0014-asset-stamp-cache-integrity` · CHG-20260728T123000-asset-stamp-cache-integrity
- 리뷰 방식([SKIPPED] 사유): 본 세션 사용자 환경 정책상 **Agent(subagent) tool 미허용** — §18.8 패널 호출 불가. 대체로 자체 적대 검토 H1~H10 을 실측하고 아래에 남긴다.

### 설계 판단
- **왜 "창을 없애기" 가 아니라 "창이 굳지 못하게" 인가**: 롤링 배포에서 두 replica 가 서로 다른 빌드를 이고 있는 구간은 **정의상 존재**한다. 그 구간을 없애려면 (a) 정적 자산을 단일 소스(엣지 file_server + 원자 교체)로 옮기거나 (b) 경로 자체를 content-addressed(`/static/<hash>/…`)로 바꿔야 한다. (a)는 HTML(구 replica) ↔ 자산(신 디렉토리) 스큐를 **반대 방향으로** 만들 뿐이고, (b)는 injector·mount·엣지 라우팅·구버전 보존(retention)까지 건드리는 큰 재설계다. 반면 **"불일치 응답은 캐시에 넣지 않는다"** 는 창의 존재를 인정하되 **영구 피해 경로만 잘라낸다** — 4파일·1불변식으로 같은 보장을 얻는다. (b)는 필요해지면 이 위에 얹을 수 있고, 그 때 본 게이트는 그대로 안전망으로 남는다.
- **왜 엣지가 아니라 upstream 인가**: 엣지는 `?v=` 문자열만 보고 그 값이 *응답한 replica 의 빌드*인지 알 수 없다 — 판정에 필요한 정보(자기 빌드 스탬프)를 가진 주체는 upstream 뿐이다. 엣지에 규칙을 남겨두면 upstream 판정을 덮어써 불변식이 무력화되므로 **제거가 필수**이며, 되살아나면 `test_caddyfile_no_static_cache_override` 가 FAIL 한다(짝 계약을 코드로 고정).
- **왜 JS 가 아니라 CSS·헤더 레벨인가(직전 cycle 과 대칭)**: 상태 소스를 하나로 유지한다. 여기서는 반대로 **헤더 결정 주체를 하나(upstream)로** 모았다 — 엣지·앱 두 곳이 같은 헤더를 다루면 어느 쪽이 이겼는지가 배포 순서에 의존한다.
- **vendor 예외는 의도적 비대칭**: `vendor/g6.min.js?v=5.1.1` 은 사람이 관리하는 **라이브러리 pin** 이지 빌드 해시가 아니다. 빌드 스탬프와 비교하면 항상 불일치가 되어 vendor 캐시를 통째로 잃는다(성능 회귀). 잔여 위험은 "pin bump 와 롤아웃이 겹치는 순간" 뿐이며 빈도가 극히 낮다 — **정직 표기**하고 남긴다.

### 자체 적대 검토 (H1~H10, 전부 실측)
- **H1 사이드카 자기 참조** — 사이드카를 해시 입력에 포함하면 실행마다 스탬프가 바뀌어 롤아웃마다 전 캐시가 깨진다. `iter_files` 에서 제외 + `test_idempotent_stamp_across_reruns` 로 고정(재실행 동일 값 실측).
- **H2 빌드 값 ≠ 런타임 값** — 이게 어긋나면 **모든 자산이 상시 `no-store`**(캐시 전면 상실)다. 통합 테스트가 실 injector 산출 HTML 의 참조 URL 과 사이드카 값이 같은지까지 단정(`/static/admin.js?v={stamp}` in admin.html).
- **H3 mount path 규약** — Starlette 최신 `Mount` 는 `scope["path"]` 를 자르지 않는다. 초판 prefix 판정이 vendor 를 놓쳐 상시 `no-store` 가 될 뻔했고 **통합 테스트가 적발**했다. 세그먼트 검사 + 두 규약 파라미터로 고정. (격리 단위테스트만 있었으면 통과했을 결함 — 접합부 테스트의 값을 실증.)
- **H4 헤더 중복** — StaticFiles 가 이미 `Cache-Control` 을 달았을 때 append 하면 모호한 캐싱이 된다. `_apply_headers` 가 기존 값을 제거 후 삽입, `test_wrapper_replaces_upstream_cache_control_not_appends` 가 단정(다른 헤더 ETag 보존도 함께).
- **H5 304 경로** — 조건부 GET 의 304 에 정책이 안 실리면 이미 캐시된 항목의 freshness 가 갱신되지 않는다. 200·304 양쪽 적용 + 전용 테스트.
- **H6 fail-open** — 사이드카 부재(dev·미주입 빌드)·헤더 조작 예외·비-HTTP scope 전부 원본 통과. 실패 방향이 "캐싱을 잃음"(성능)이지 "오염"(correctness)이 아니다 — 의도된 비대칭.
- **H7 입력 견고성** — `?v=` 중복·깨진 percent-encoding·비-UTF8·5KB 값에서 예외 없음(`test_malformed_query_does_not_raise`). 판정은 allowlist 가 아니라 **"일치할 때만 허용"** 이라 미지 입력은 전부 `no-store` 로 수렴(`test_mismatch_is_the_default_for_unknown_stamps`).
- **H8 성능 회귀** — 정상 상태(스탬프 일치)에서는 종전과 **동일한** `immutable` 이 나간다. 추가 비용은 요청당 쿼리 파싱 1회(문자열)이며 스탬프는 시작 시 1회 로드. 엣지 `header` 지시자 하나가 사라진 만큼 상쇄.
- **H9 이미지 경로 정합** — Dockerfile `--root /app/web/static` == 앱 `STATIC_DIR`(실측 `/app/web/static`), `COPY unit/feature-0003-agent-web-ui/src /app/web` 로 `static_cache.py` 동봉, `/app/web` 이 런타임 sys.path 에 존재(`perf_metrics` 와 동일 기전 — 컨테이너에서 직접 확인). 배포 게이트 `asset_stamp_verify` 는 `*.html/*.js` 만 grep 하므로 사이드카에 영향 없음.
- **H10 엣지 문법** — `caddy validate --adapter caddyfile` 이 `adapted config to JSON` 까지 통과(잔여 에러는 검증 샌드박스의 cert 파일 부재뿐).

### 한계 (정직 표기)
- **롤링 창 자체는 남는다** — 그 구간에 접속한 사용자는 버전이 섞인 페이지를 한 번 볼 수 있다(종전과 동일). 달라진 것은 **그 상태가 캐시에 굳지 않는다**는 점이며, 다음 로드에서 정상 수렴한다. "창 제거" 를 원하면 content-addressed 경로(위 (b))가 후속 과제다.
- **이미 오염된 브라우저는 자동 복구되지 않는다** — 본 변경은 *이후* 오염을 막는다. 기존에 굳은 항목은 그 URL 이 다시 요청될 때까지 그대로다(스탬프가 바뀌면 새 URL 이므로 실질 영향은 소멸). 사용자 안내(Ctrl+F5)는 `deploy-web.sh` 체크리스트 [3] 이 이미 담당.
- **§18.8 패널 미수행** — 세션 정책. 위 H1~H10 이 대체이며, 특히 H3 은 자체 통합 테스트가 잡은 실결함이라 검토가 형식적이지 않았음을 보인다.
- 위험도: **Major(§12.3)** — 엣지 설정 + 전역 캐싱 semantics. 롤백 = 4파일 revert.
- Cross-ref: MODIFY CHG-20260728T123000-asset-stamp-cache-integrity · 선행 사고 관측 `feature-0003/docs/test-runs.d/20260728T113000-graph-noise-reduction.md` · feature-0027 P0-E · AGENTS.md §13.1 v3.35.1 · §13.2.9.
