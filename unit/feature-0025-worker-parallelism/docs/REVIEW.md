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
