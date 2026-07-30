---
doc_type: REVIEW
feature_id: feature-0025-worker-parallelism
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260724T053235-worker-parallelism [AGENT-TEAM: SHIP]
- **Related Change:** feature-0025 워커 성능·병렬 처리 런타임 설정 (CHG-20260724T053235).
- **Panel:** §18.8 2-렌즈 적대 리뷰 (fresh-context) — ①backend/concurrency 렌즈 ②regression/byte-동치 skeptic 렌즈.
- **Verdict:** SHIP (BLOCKING 0). MAJOR 2 in-cycle 수정, MINOR 3 수정/문서화, 테스트 결함 1 수정.
- **CONFIRMED (양 렌즈 합치):** concurrency==1 경로 byte-동치(gather→llm→persist 인터리브·예외/카운터/UPDATE 순서
  보존), 병렬 스레드 안전(LLM 만 병렬·DB/공유상태 단일 스레드), ask claim `SKIP LOCKED`+lease fencing·전용 conn
  분리, live get_int TTL(10s) hot-path 무부담, 레지스트리/clamp/apply_mode(ASK_CONCURRENCY=restart 타당), PG
  primary/replica max_connections 정합.

### 수용·수정한 결함
- **MAJOR-1 (concurrency 동시성 렌즈):** 병렬 graceful shutdown 이 `join(timeout=2.0)` 로 in-flight job 을 2초에
  유기 → 직렬(stop_grace_period 70s 완주) 대비 회귀(orphan→~18분 재큐·중복 LLM 비용). **FIX:** 공유 deadline
  (65s, compose stop_grace_period 70s 예산) join 으로 executor 가 현재 job 을 grace 창 안에 완주(ask.py).
- **MAJOR-2 (양 렌즈, FINDING-A):** 신규 `AGENT_ASK_WORKER_IDLE_POLL_MS` 가 기존 `AGENT_ASK_WORKER_IDLE_POLL_SEC`
  env 를 조용히 무력화(현재 배포는 0.5s→0.5s byte-동치이나 SEC 튜닝 배포엔 회귀). **FIX:** `_current_idle_poll()`
  이 콘솔 MS override 있을 때만 신규 accessor 사용, 없으면 legacy SEC env 존중 폴백(ask.py) + 존재신호 테스트.
- **MINOR-1 (concurrency):** node_analysis 주석 "pgbouncer fan-out 없음"은 부정확 — LLM 단계 usage 회계가
  호출당 단명 PG 연결을 병렬 생성. **FIX:** 주석 정정(짧은 점유·§82 장기 lock-wait 와 구분 명시).
- **MINOR-2 (concurrency):** compose 자원 산정 "ask≤8×2conn=16" 과소계상(coordinator·per-call memory/usage·
  insight 병렬·web inprocess·(user,db)쌍당 풀). **FIX:** compose 주석 정정 + 라이브 실측 권장.
- **MINOR-3 (concurrency):** 병렬 ask 가 프로세스 전역 `cfg.CURRENT_RUN_ID` race 재도입(과금/계측 오귀속 —
  라우팅은 명시 conversation_id 라 안전). **FIX:** ask.py caveat 주석 + DECISIONS ADR-0025-03 명시.
- **FINDING-B (skeptic):** 테스트가 리터럴로만 byte-동치 주장(config 실측 미대조). **FIX:** shared.config import
  대조로 노출 knob spec-config 드리프트 강제(test_exposed_knob_defaults_track_config).
- **FINDING-C / conc>1 뉘앙스 (양 렌즈, LOW opt-in):** conc>1 시 node_analysis 틱-내 형제 컨텍스트 축소·
  cluster_label 배치 실패 비중단. conc==1 무영향. **문서화:** DECISIONS ADR-0025-02, FUNCTION.md.

- **Risks:** 병렬 활성(override≥2) 시 pgbouncer 풀·Bedrock 429 부하 실증 필요 → 배포 후 PB-0008 + 운영 현황 관측.
- **Open Questions:** run_agent run_id 전역→인자 전환(정밀 귀속), docker replicas 자동스케일 — 별도 initiative 이연.
- **Human Approval Needed:** PLAN-APPROVED (AskUserQuestion "전체 + 인프라 여력"). 배포는 별도 confirm.

## REV-20260730T125000-ai-claude-feature-0025-worker-resource-isolation [CODEX:worker-resource-isolation] — PASS
- Related TASK: feature-0025-worker-parallelism (T0 공유 자원 격리·계측)
- Source: codex exec 0.146.0 (`-s read-only`, `model_reasoning_effort=high`, 대상 `git diff --cached`) — 2 라운드(초기 + 수정 재검증)
- Trigger: performance/성능·caching/캐싱 keyword matched (backend/qa 렌즈). 채널 선택 근거 = AGENTS.md §18.8.2 — 세션 Agent-tool 제약과 무관한 경량 채널 우선.
- Timestamp: 2026-07-30T13:05:00+09:00
- Verdict: PASS (재검증 P1 0건 — 초기 P1 2·P2 2·P3 1 + 재검증 P2 2·NEW P2 2 전건 in-cycle 수정)
- Critical issue (해소됨): P1-a 게이트 없는 상한 knob = 거짓 컨트롤(PG/DS) → knob 제거·`RESOURCES=("llm",)`·회귀 단정 / P1-b LLM 예산이 semantic_cluster 직렬 경로·product_classify 에서 우회(기본 설정에서 무효) → 양쪽 배선 / P2-b terminal budget 이 generic 분기로 fall-through 해 attempts 이중 증가·error_kind 덮어쓰기(실버그) → 분기 완결+return
- Artifact: unit/feature-0025-worker-parallelism/docs/reviews/2026-07-30T12-50-00-codex.md
- Human Approval Needed: no (PLAN-APPROVED 2026-07-30 범위 내 · 배포는 별도 confirm)
- 판단 근거 요약: ① 게이트 없는 knob 을 노출하지 않는다는 규약을 ADR-0025-06 으로 승격(이 repo 가 `attachment.execute_sql_on.*` 를 같은 이유로 제거한 선례) ② 게이트는 호출측 명시 — 커넥션 헬퍼에 넣으면 web 요청 경로가 백그라운드 예산에 걸린다(ADR-0025-05) ③ 예산 거절은 실패가 아니라 순번 대기이나 **연속** 거절은 terminal 로 표면화해야 한다(무기한 pending 이 run 을 영구 running 으로 만들어 사용자 재트리거를 막는다)

## REV-20260730T143000-ai-claude-feature-0025-worker-ds-budget [CODEX:worker-ds-budget] — PASS
- Related TASK: feature-0025-worker-parallelism (T0b 커넥션 축 게이트 + 콘솔 노출)
- Source: codex exec 0.146.0 (`-s read-only`, `model_reasoning_effort=high`, 대상 `git diff --cached`)
- Trigger: performance/성능 + UI/화면 keyword matched (backend·qa·ux 렌즈). 채널 근거 = AGENTS.md §18.8.2 경량 경로.
- Timestamp: 2026-07-30T14:45:00+09:00
- Verdict: PASS (P1 3·P2 1 **전건 in-cycle 수정**, 각 수정에 회귀 단정 추가)
- Critical issue (해소됨):
  ① **`ds` 슬롯 누수** — `_ds_cm.__enter__()` 후 `connect()` 를 `try` **밖**에서 호출해, 연결 수립이
     예외를 내면 반납이 보장되지 않아 슬롯이 영구 누수(이후 introspect 전부 거절). → connect 를 try
     안으로 이동 + `except` fail-soft. 회귀 2건(connect 예외·쿼리 예외) 추가.
  ② **NaN/Infinity 가 500 유발** — 비표준 JSON 이라 `JSONResponse` 직렬화가 `ValueError`. 관측 조회가
     콘솔을 깨는 fail-open 위반. → `_safe_int`/`_safe_float`(`math.isfinite`) 경계 변환 + `allow_nan=False`
     직렬화 단정.
  ③ **콘솔 노출이 실제로 안 됨** — `worker_resources` 를 응답에만 추가하고 `admin.js` 렌더가 없었다.
     §16.7 G3(주장한 affordance 의 배선 실측) 위반이며, 내가 "콘솔 노출 완료" 로 보고한 것도 오보였다.
     → `admin.js` AI 운영 현황 pane 에 '워커 공유 자원' 표 렌더 추가(거절 0 회색 / 거절 적색+거절률 /
     stale·분석정지 표식). 웹 자산 변경이 생겼으므로 PB-0008 을 POST-DEPLOY 항목으로 등재.
  ④ (P2) **symlink 추종** — 공유 볼륨은 다른 컨테이너도 쓴다. → `islink` 스킵 + `realpath` 의 부모가
     스냅샷 디렉토리인지 재확인(디렉토리 이탈 차단) + 회귀 단정.
- Clean 판정(codex): task 게이트의 concurrency==1 동작·monkeypatch 해석·kill-switch 보존 / 재진입·
  self-deadlock 없음 / 기본값 byte-equivalence.
- Artifact: (본 index entry 가 findings 전문을 담는다 — codex 출력 4항목이 위 ①~④ 와 1:1)
- Human Approval Needed: no (PLAN-APPROVED 범위 · 배포는 deploy_scope: included)

## REV-20260730T152000-ai-claude-feature-0025-worker-snapshot-identity [CODEX:worker-snapshot-identity] — PASS
- Related TASK: feature-0025-worker-parallelism (T0c 스냅샷 identity 안정화 — T0b 결함 수정)
- Source: codex exec 0.146.0 (`-s read-only`, `model_reasoning_effort=high`, 대상 `git diff --cached`)
- Trigger: performance/성능 keyword + 파일 삭제 경로 신설(qa 렌즈). 채널 근거 = AGENTS.md §18.8.2.
- Timestamp: 2026-07-30T15:35:00+09:00
- Verdict: PASS (P1 0 · P2 2 전건 in-cycle 수정)
- Findings:
  ① **P2 reaper TOCTOU/mtime 오판** — 24h 임계가 정당한 장기 pause 워커를 죽은 것으로 오판할 수
     있고, `stat` 후 그 워커가 되살아나 `os.replace` 하면 최신 파일을 지우는 race 가 있다.
     → 임계를 **7일**로 상향(오판 삭제 vs 회수 지연의 **비대칭** — 전자는 살아 있는 워커를 콘솔에서
     지우고 후자는 유령 1줄이 더 남을 뿐) + **unlink 직전 mtime 재확인**으로 TOCTOU 창 축소.
     완전 제거는 불가하지만(원자 조건부 삭제 없음) 삭제돼도 다음 flush 가 재생성해 **자기복구**
     되므로 최악이 "한 주기 표시 누락" 이다. clock skew 는 이 배치에선 무효 — 모든 워커가 같은
     호스트 볼륨에 쓰므로 mtime 이 단일 파일시스템 시계다(주석 명시).
  ② **P2 mtime 동률 시 비결정적** — tie-break 가 없어 `glob` 순서에 따라 상한 밖 파일이 달라진다.
     → `key=(-mtime, path)` 결정적 정렬 + 동률 3파일 반복 호출 단정.
- Clean 판정(codex): **identity OK** — compose 실측으로 `insight_worker`(`docker-compose.yml:366`)·
  `ask_worker`(`:414`) 가 서로 다름을 확인(같은 값이면 서로의 스냅샷을 덮어썼을 것). **fail-open OK** —
  flush·reaper·worker tick·콘솔 파일 처리 전 경로에서 예외 흡수.
- 잔여(수용): 외부에서 같은 서비스를 `scale` 하면 복제본이 같은 `AGENT_SESSION` 을 공유해 스냅샷을
  덮어쓴다. 현 배치는 워커를 scale 하지 않으며, 필요해지면 `AGENT_WORKER_ROLE` 명시 주입으로 해소한다.
- Human Approval Needed: no
