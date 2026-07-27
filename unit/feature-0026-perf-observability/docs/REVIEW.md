---
doc_type: REVIEW
feature_id: feature-0026-perf-observability
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260727T091500-ai-root-perf-bottleneck-metrics 설계 판단 근거
- Related TASK: feature-0026-perf-observability
- Timestamp: 2026-07-27T09:15:00Z
- 판단 근거:
  - **in-process 집계 채택 / 외부 APM 기각**: ANCHOR §2 — 단일호스트 사내 LAN 규모에서
    Prometheus 류는 표면·비용 과잉. in-process + 스냅샷 CLI 가 최소 침습.
  - **미들웨어는 순수 ASGI**: BaseHTTPMiddleware 는 응답 버퍼링·스트리밍(SSE/long-poll)
    간섭·오버헤드 이슈가 알려져 있어 회피. send 래퍼로 status 만 가로챈다.
  - **버킷 히스토그램(정확 percentile 아님)**: 요청당 O(1)·메모리 유계가 우선.
    p50/p95 는 버킷 상한 보간(보수적) — 필드명 `p50_ms_le/p95_ms_le` 로 의미 명시.
  - **권한 신설 없이 `console.aiops.read` 재사용**: 동일 관측 등급(admin 전용) —
    권한 카탈로그/backfill/콘솔 grid 변경 없이 게이트 확보 (blast radius 최소).
  - **duration_breakdown 은 additive 키만**: 기존 4키(queued/init/inference/total) 소비처
    (FE 툴팁) 불변 — 회귀 0. post-answer 는 저장 시점 제약(답변 mirror 선행)으로 KV 분리.
  - **latency 측정 위치 = create 호출 직전/직후**: `_openai_chat_completion_with_deadline`
    의 기존 측정과 동일 정의(순수 API 왕복) — task 간 비교 가능성 유지.
  - **리스크**: 계측 코드가 핫패스 관통 — 전 구간 try/except fail-open + 단위 테스트로 상쇄.
    사전 승인: deploy_scope: included (전역), UI 표면 0 (PB-0008 비대상).

## REV-20260728T003000-ai-root-perf-bottleneck-metrics [AGENT-TEAM: SHIP-WITH-FIXES]
- **Related Change:** feature-0026 성능 관측 인프라 (CHG-20260727T091500).
- **Panel:** §18.8 3-렌즈 적대 리뷰 (fresh-context) — ①backend/concurrency ②security/authz ③qa/regression skeptic.
- **Trigger:** performance/latency/caching + API/endpoint keyword matched (§18.8 dispatch 표).
- **Verdict:** 초기 BLOCK 3렌즈 전원 → **전 결함 in-cycle 수정 후 SHIP** (BLOCKING 잔여 0).
- **Timestamp:** 2026-07-28T00:30:00Z

### 수용·수정한 결함 (전건 회귀 테스트/검증 동반)
- **[backend F-1, HIGH]** percentile 오버플로 버킷 `float("inf")` → JSONResponse(allow_nan=False)
  직렬화 ValueError 로 admin perf 엔드포인트 영구 500 (long-poll 60s+ 는 일상 트래픽).
  **FIX:** 마지막 경계값 포화(유한) + 버킷 상한 600s 확장 + JSON 직렬화 회귀 테스트.
- **[qa B1]** unhandled 예외 500 이 ServerErrorMiddleware(미들웨어 바깥) 생성이라 error_count
  미계상. **FIX:** await 예외 경로에서 500 계상 후 re-raise(전파 불변) + raise_server_exceptions=False 테스트.
- **[qa B2]** F-1 수정 스테이징 누락 위험. **FIX:** 커밋 직전 전량 재스테이징 절차 확립(본 entry 가 증적).
- **[sec B1]** perf-snapshot MySQL root 비밀번호 argv 노출(-p) — 저장소 기존 C-1 결정(kb-cleanup-mysql.sh)
  회귀 + Warning grep 은폐. **FIX:** MYSQL_PWD env 전환 + Warning 필터 제거.
- **[sec B2 / backend C-3]** pgbouncer 비밀번호 `docker exec -e` argv → sudo auth.log 영구 기록.
  **FIX:** stdin 주입(read -r)으로 전환 + 전 docker 호출 timeout 60 + --days 정수 검증.
- **[sec B3]** pg_stat_statements 원문 SQL 에 평문 role 비밀번호 실재(라이브 실측 — utility 문 비정규화).
  **FIX:** 민감문 배제 필터 + 문자열 리터럴 마스킹 + umask 077/chmod 700 (ADR-0020 digest-first 정합).
- **[sec B4]** Caddy access log 가 share 토큰(무인증 bearer-capability) 전문·쿼리스트링 기록 + SECURITY
  정본 미갱신. **FIX:** request>uri regexp 마스킹 필터(caddy adapt 검증 PASS) + SECURITY.md §27 신설.
- **[sec C1]** _STATS method 축 무유계(비인증 카디널리티 DoS — httptools 는 배포 우연). **FIX:** method
  화이트리스트 정규화 + 2000키 하드 상한 + 테스트.
- **[sec C2]** slow ring 50건 축출(관측 부인). **FIX:** 200 확대 + "증적 아님" docstring 명시.
- **[sec C3]** WEB_PERF_LOG_INTERVAL_SEC kill-switch 미문서화. **FIX:** unit AGENTS.md §9 + SECURITY §27 등재.
- **[backend C-1]** /static(Mount) 가 "(unmatched)" 에 합산. **FIX:** MOUNT_GROUPS prefix 분리 + 테스트.
- **[backend C-2]** send_wrapper 비보호 + status 0 침묵. **FIX:** try/except + aborted_count 분리 + 테스트.
- **[backend C-4]** node-analysis 드레인 tick 마다 timing 파일 무회전 누적. **FIX:** na-only tick 은
  로그 라인만(파일 생략).
- **[backend C-6 / sec 도전②]** "동작 변경 0" 문구 부정확(답변당 KV 1 write + PG conn). **FIX:**
  FUNCTION/REPORT/STATUS "사용자 가시 동작 변경 0" 정정 + KV 게이트를 기존 블록과 정렬(qa C3,
  빈-답변 희석 방지) + 3c 집계 시간창 필터.
- **[qa C1]** shared/db 의 perf_counters 무조건 import — 이미지 skew 부트 실패 위험. **FIX:** try/except
  no-op 스텁 폴백 + 배포 단계 워커 부트 로그 검증 항목.
- **[qa C2]** admin_perf RBAC 무테스트. **FIX:** 403/200 쌍 테스트(저장소 관례 정합).
- **[sec 도전①]** sticky LB 아래 web-b 조회 불가 → 미래 인증 우회 유인. **결정:** 엔드포인트는
  this-replica 진단으로 한정 명시, 전-replica 정본 = perf-snapshot §10 — 우회 표면 신설 금지
  (FUNCTION §7.1 명문화).

### 패널이 결함 없음으로 확증한 것 (반증 시도 후)
- `_rt_ms`/`_KNOWLEDGE_TIMINGS`/`_init_detail` 전 도달 경로 정의 보장(UnboundLocal 없음), llm.py 13곳
  `_lat_t0` try 경계·target 계약 전수 무결, send 래퍼 스트리밍(SSE/long-poll) 무간섭, contextvar
  threadpool 귀속 정상, route 골든 diff 는 신규 route 1건만(무관 drift 0), (unmatched) 그룹화로 raw
  path/URL 비밀 비저장, require_permission 게이트 fail-closed(ai_ops 와 동일 계약), Caddy 쿠키·
  Authorization 기본 REDACTED(실컨테이너 실측), duration_breakdown additive 키의 FE 무영향.
- **Risks:** 배포 시 Caddy 필터 adapt 게이트 통과 확인(사전 로컬 adapt PASS), 워커 부트 로그(qa C1) 확인.
- **Human Approval Needed:** no (Minor·additive 계측·deploy_scope: included 전역 선언 — 배포는 자동 범위).
