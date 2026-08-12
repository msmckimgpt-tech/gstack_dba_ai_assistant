---
doc_type: REVIEW
feature_id: feature-0020-zd-deploy-all
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260714T104500-ai-claude-feature-0020-zd-deploy-all
- Date: 2026-07-14
- Scope: REQ-20260714T101500-zd-deploy-all 전체 (배포 인프라 — Major)
- 판단 근거:
  1. **스파인 확장 vs 별도 스크립트**: flock 직렬화·coalesce·빌드 게이트·sudoers 경계 중복과
     migrate→web→worker 순서 보장 파손을 피하기 위해 deploy-web.sh 확장 채택 (ANCHOR §2 Alt-A).
  2. **gateway surge vs 상시 2-replica**: 호스트가 메모리를 조이는 중(라이브 mem_limit 하향
     실측)이고 gateway OOM 이력(2g) 존재 — steady-state 비용 0 인 배포 창 한정 surge 채택.
     상시 HA 는 메모리 예산 사람 결정 필요로 Out of Scope 선언 (ANCHOR §2 Alt-B).
  3. **워커 단일 인스턴스 순차 recreate**: 큐 기반(lease fencing·requeue·멱등 쓰기) +
     graceful SIGTERM(0015)이 이미 사용자 무영향을 보장 — 2-replica 는 동시성 계약 재검증
     위험만 추가 (ANCHOR §2 Alt-C).
  4. **live-truth compose 채택**: main worktree 의 미커밋 compose 튜닝(외부 세션)이 라이브
     컨테이너에 실적용 상태임을 전수 대조(insight env 7종·on-failure:3·mem_limit 3종·
     OLLAMA_NUM_PARALLEL)로 확인 — 커밋하지 않으면 이후 main 기준 배포가 라이브 설정을
     silent revert 하므로 verbatim 채택. §13.2.8 foreign-change alert 에 기록됨
     (meta/FOREIGN_CHANGE_ALERT.md 2026-07-14 entry). "명시 비활성화/운영자 의도 보존"(§13.1)
     에 따라 값 무수정.
  5. **healthcheck timeout 10s→30s**: 라이브 워커 2종 16h unhealthy 의 실측 원인이
     "Health check exceeded timeout (10s)" — probe 스크립트가 DB 연결을 여는 구조라 부하 시
     오탐. 배포 게이트가 health 를 신뢰하려면 선행 견고화 필수. 완화(retries 증가)가 아닌
     timeout 상향인 이유: probe 는 성공하면 수초 내 끝나므로 timeout 상향은 감지 지연을
     최악 +20s 만 늘리고 오탐은 구조적으로 제거.
  6. **발견 결함 동반 수정 (기존 feature-0014 코드)**: (a) TLS preflight 의 caddy rootCA 대조
     가드가 `docker compose ps caddy`(컨테이너 0개여도 exit 0)로 진입해, caddy 미기동 호스트
     에서 부재 컨테이너 exec 파이프라인이 pipefail+set-e 로 **무메시지 exit 1** — cold host
     잠복 버그(worktree dry-run 에서 실측 재현). `ps -q` 비어있음 가드로 수정.
     (b) STATE_FILE 이 dry-run 에서도 실기록(`echo > file` 무가드)되던 결함 — dry-run 후
     실배포가 false no-op 이 될 수 있던 위험. `state_set`(dry-run 무기록)으로 일원화.
- 리스크:
  - 워커 이미지 전환(repo-* → mysql-ai-agent:<sha>) 첫 배포는 last-good 부재 — 실패 시 자동
    롤백 불가(구 컨테이너 유지 안내만). 첫 배포를 본 cycle 의 POST-DEPLOY 로 attended 수행해
    상쇄.
  - surge DNS alias: 신규 요청 흡수는 Docker embedded DNS + 클라이언트(OpenAI SDK) 기본
    connect-retry 에 의존 — in-flight 는 stop_grace 120s drain. "무중단" 은 near-zero
    (PG PAUSE 와 동일 등급) 로 정직 표기.
  - restart: on-failure:3 (insight-worker, live-truth 채택분): 크래시 3회 후 영구 정지 특성 —
    운영자 의도(폭주 억제)로 보존하되 REPORT §Risks 에 표면화.
- 사전 승인 근거: 전역 `deploy_scope: included` (FIRST_REQUEST.md, 2026-06-11 사용자 결정) —
  cycle-final 후 배포까지 사전 승인. 인증/개인정보/파괴적 데이터 변경 없음.

## REV-20260714T111500-ai-claude-feature-0020-zd-deploy-all [SUBAGENT:improve-fit-reviewer(§18.8, 적대 1-round)] — 배포 스파인 확장 적대 검증 (SHIP-WITH-FIXES → 전건 반영)
- Date: 2026-07-14
- 패널: improve-fit-reviewer 1-round (staged 전문 정독 + 라이브 컨테이너 inspect 교차검증 +
  bash -n + compose config ±profile + pin overlay 병합 실측). 판정 SHIP-WITH-FIXES —
  BLOCKING 0 / MAJOR 5 / MINOR 8. 스파인 불변식(flock·≥1 healthy upstream·build→migrate→swap·
  전 recreate --no-deps)·DNS alias 흡수·live-truth verbatim 주장(라이브 inspect 전건 일치)은
  패널이 반증 시도 후 CONFIRMED-정합 판정.
- MAJOR 반영 (전건):
  - M-1 gateway surge 잔존 leak: 무드리프트/미기동 경로에 `sweep_leaked_surge()` — 본체
    healthy 확인 후 고아 surge stop·rm (본체 비정상이면 유일 서빙 가능성 — 유지+경고).
  - M-2 롤백 후 `:current` 태그 미복원(2연속 실패 시 last-good 이 결함 이미지로 오염 — web
    경로는 feature-0014 잠복 동일 결함): 롤백 3경로(auto_rollback·rollback_workers·--rollback)
    성공 직후 `docker tag <repo>:last-good <repo>:current` 로 불변식 복원.
  - M-3 alembic 가드 WARN-continue 가 봉인 대상(silent-miss) 재개방: deploy-web build 게이트와
    동형으로 metadata-race 마커 시에만 관용, 아니면 하드 중단 + GIT_COMMIT 주입(TASK-0126 각인 보존).
  - M-4 `make up` ask-worker 빌드만 하고 미기동(web 이 worker 모드 라이브 실측 — cold up 시
    질문 hang): insight 와 동형 조건 기동 블록(`ENABLE_ASK_WORKER`!=0 기본 기동).
  - M-5 `--workers-only` pending 마이그레이션 무게이트: workers-only/재개 경로에
    `migrate_phase "$AGENT_IMAGE_REPO:$sha"` 추가 — expand 는 구 web 에도 안전(CONVENTIONS §12)
    이라 die 대신 게이트+적용이 정합.
- MINOR 반영: m-1(rollback_workers web_img 인자 정합)·m-2(gateway none-streak 5회 조기 실패)·
  m-3(WORKER_READY_TIMEOUT 240→300s — unhealthy 확정 시각과 경계 동률 false-fail 방지)·
  m-4(no-op 메시지에 이미지-only 드리프트 한계+--force-gateway 힌트)·m-5(첫 배포 실패 복구
  힌트 정정 — 이미지 잔존·base file-set 복귀 명령)·m-6(RUNBOOK 에 on-failure:3 정지 복구 절차)·
  m-7(hot.md 무관 Active Threads 복원 — 정보 손실 방지). m-8 은 정보성(수용 — surge 창 transient
  +2g 는 동반 mem_limit 하향 -4g 로 headroom 개선).
- 재검증: bash -n 2종 PASS + dry-run 4 scope 재실행 전건 exit 0 (workers-only 경로에 migrate
  게이트 발화 확인).
- 인용 무결성: 본 entry 와 반영 diff 는 같은 changeset 에 staged.

## REV-20260714T125800-ai-claude-feature-0020-zd-deploy-all [SKIPPED:post-deploy-docs-only] — 라이브 배포 결과 기록
- Date: 2026-07-14
- Scope: docs-only — POST-DEPLOY 라이브 검증 Run fragment(test-runs.d) + REPORT §2/§7 동기화 결과 기입. 코드 변경 0.
- [SKIPPED] 사유: 산출물이 검증 기록 자체(라이브 배포 exit 0·워커 healthy·edge 200 — 로그/inspect 실측 전사)라 패널 불요. 선례 POST-DEPLOY 기록 커밋 계열(#773 등).

## REV-20260714T130500-ai-claude-feature-0020-zd-deploy-all [SKIPPED:docs-checklist-reconcile] — 직전 docs 커밋 게이트 누락 정합
- Date: 2026-07-14
- Scope: docs-only — TASK 체크박스 완결 + MODIFY CHG entry 보강. 직전 e4a02ec7 커밋 시
  `verify | tail` 파이프가 FAIL exit 을 가려(체인 미중단) check #2/#3 미충족 상태로 커밋된
  것을 새 commit 으로 정합(--amend 금지 준수).
- [SKIPPED] 사유: 체크리스트/기록 정합 자체 — 패널 대상 아님.

## REV-20260812T140000-quiesce-gate [CODEX:full-panel-substitute] — PASS (P1 5건 흡수 후)
- **Trigger**: code change, §18.8 dispatch 표 키워드 **0건 매칭**(배포 절차 shell) → 표 규칙상
  **full panel default**. 다만 본 위임 세션에 "요청 없이 Agent tool 을 호출하지 말라" 는 **상위
  우선순위 하네스 지시**가 있어 §18.8.2 carve-out 에 따라 **제약 없는 채널**(`codex review
  --uncommitted`)로 수행했다. 판정 기준 정본 `docs/CODE_REVIEW.md`(§18.8.1-2).
  **미덮인 도메인 명시(§18.8.2-4 정직)**: ux/design 렌즈는 이 변경에 N/A(사용자 표면 무변경),
  security 렌즈는 codex 판정 + 자체 점검(신규 권한·엔드포인트·자격증명 경로 0, 게이트 쿼리는
  read-only `count(*)`)으로 갈음. `[SKIPPED:tool-restricted:*]` 로 남길 미검증 도메인 없음.
- **1라운드 verdict — P1 5건**: ① inprocess 모드에서 게이트가 아무것도 못 봄(`/api/ask` 는
  ask_jobs 행을 안 만들고 `active_streams` 는 CSV/SSE 전용) ② 한쪽 신호 unknown 을 0 으로 읽음
  ③ 스냅샷 1장 뒤 admission 경합 ④ stale heartbeat 행을 "없음" 으로 단정 ⑤ 롤백 경로 미게이트.
- **사실 확인(추측 아님)**: ①의 전제를 라이브로 검증했다 — `_ACTIVE_STREAMS` 증가 지점은
  `admin_audits.py`(CSV) · `_prompt_context.py`(SSE) **두 곳뿐**이고 `/api/ask` 를 세지 않는다.
  현행 운영 모드는 `worker`(`.env` + 라이브 web-a `printenv` 양쪽 확인)이라 오늘의 게이트는
  유효하지만, 모드가 바뀌면 **조용히 무력화**된다 — 잠복 결함으로 인정.
- **흡수**:
  - ① 실행 모드를 실측해 `worker` 가 아니면 **통과시키지 않는다**(조용한 오판 → 시끄러운 거부).
  - ② `unknown` 은 어떤 조합에서도 조용함이 아니다 — 두 신호는 서로 다른 차원이라 한쪽으로
    다른 쪽을 증명할 수 없다.
  - ③ settle 재확인(기본 3s) 추가로 창을 좁혔다. **완전한 admission barrier 는 아니다** —
    앱측 fence 가 필요해 별 cycle 로 이월하고 잔여 창을 문서에 명시했다(과장 금지).
  - ④ stale 행을 제외하지 않고 **분리 계상 + 차단**, 로그로 구분 표기.
  - ⑤ **부분 수용** — 롤백에 게이트를 걸면 결함 있는 배포가 그대로 남는다(feature-0014 가 엣지
    게이트를 롤백에서 비차단으로 둔 것과 같은 근거: 복구 완주 우선). 대신 **끊고 가는 양을
    관측·보고**하고 최종 요약의 강행 카운터에 반영한다. 침묵만 제거하고 차단은 하지 않는다.
- **자체 적발(패널 이전)**: `web_active_streams_total` 초판이 공용 `replica_active_streams` 를
  썼는데 그 헬퍼는 **조회 실패도 0 으로** 돌려준다 — 조회가 깨진 배포는 항상 '조용함' 으로
  통과했을 것이다. 실패를 비-0 종료로 구분하는 전용 probe 로 교체하고 회귀 테스트를 세웠다.
- **흡수 검증**: 신규/변경 테스트 포함 **26 PASS** · **뮤테이션 16/16 KILLED**(모드 게이트 ·
  unknown 차단 · stale 차단 · settle 재확인 · 롤백 보고 · 전용 probe · 관용 헬퍼 복귀 등).

## REV-20260812T160000-quiesce-postdeploy [SKIPPED:non-policy-doc] — PASS
- **Trigger**: 문서만(배포·실측 기록, 원장 status 전이, LRN 신설). 코드 변경 0 →
  §18.8 dispatch 표 "비정책 doc-only" 행. 선행 코드 cycle 은 `REV-20260812T140000-quiesce-gate`
  에서 codex backend+qa(full-panel 대체 채널)로 P1 5건 흡수 완료.
- 기록에 **통과하지 못한 조건을 함께 남겼다** — 이번 배포는 유휴 상태라 게이트가 즉시 통과했고,
  "바쁠 때 기다렸다 통과하는" 궤적은 미관측이다(과장 금지).

## REV-20260812T200000-quiesce-out-of-band [SKIPPED:live-measurement-driven] — PASS
- **Trigger**: 선행 cycle(`REV-20260812T140000-quiesce-gate`)에서 §18.8 codex backend+qa 패널을
  이미 수행했고, 본 변경은 그 패널이 확립한 **동일 규율의 적용 범위 확장**이다(같은 판정을 배포
  밖 경로에도 적용 + 우회를 관측 가능하게). 새 설계면이 없다.
- **적대 검증 대체 — 라이브 실행이 패널보다 강했다**: 실제 스택에 라이브러리를 source 하는 것만으로
  **결함 3건을 동시에** 적발했다(백틱 명령 치환 / exec 실패 오독 / 보고 변수 미초기화).
  그중 ①은 **이미 머지된 코드의 버그**였고 단위 테스트는 문자열 존재만 봐 통과시키고 있었다 —
  "분기가 라이브에서 처음 발화할 때 드러나는" 부류라 정적 검사로는 잡히지 않았다.
  각 건에 회귀 테스트를 세우고 **뮤테이션 7/7 KILLED** 로 판별력을 확인했다.
- `docs/CODE_REVIEW.md` 위험 축 대조: 무음 절단 0 · fail-open 게이트 0(모든 신규 경로 fail-closed +
  명시 탈출구) · 멱등성(재실행 안전) · 격리 경계 무변경(신규 write 는 append-only 스탬프 로그 1개).
