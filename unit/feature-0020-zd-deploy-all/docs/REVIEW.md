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
