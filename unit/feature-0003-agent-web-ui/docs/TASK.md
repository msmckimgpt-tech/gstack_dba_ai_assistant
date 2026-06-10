---
doc_type: TASK
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: in_progress
- Owner: AI
- Priority: minor (TASK-0124 RBAC 권한 정합 + TASK-0125 UX 2차 보완 — ux-compact-redesign 병합)
- Last Updated: 2026-06-10 (TASK-0184 계정 drill-down + 프로필 사용내역 차트 + 내 활동기록 제거; TASK-0181 역할/계정 모델 stacked + 요청 수; TASK-0180 카테고리별 행 레이아웃; TASK-0179 차트 grid; TASK-0178 여백 컴팩트화; TASK-0177 상세표 비용컬럼+디자인 정렬; TASK-0176 역할/계정별 비용 차트; TASK-0167 작은화면 잘림)

## 2. Task Queue

### TASK-0181 LLM 사용량 역할/계정 차트 모델별 stacked + 상세 표 요청(메시지) 수 (2026-06-10)
- [x] **Minor §12.3** — 사용자 요청. **A**: 역할별·계정별 [토큰|비용] 막대를 모델별 누적(stacked)으로 분해. 백엔드 by_account 에 `models:[{model,total_tokens,cost_usd}]` 보존 + `_aggregate_usage_by_role` 가 역할별 models 합산. 프론트 전역 `modelColor`(일별/도넛/stacked 색 일관) + `renderStackedHBar`. **B**: 요청 수=`count(distinct run_id)`(run=conversation 단위, NULL 제외) 를 totals/by_model/by_account/by_role 에 `requests` 추가. 요약 '요청' 카드 + 상세 표 '요청' 컬럼(호출=LLM 호출, 요청=사용자 메시지). 권한/스키마 신규 0. 캐시버스터 `?v=20260610-usage-stacked`. node --check/py_compile + make test 282 passed/5 skipped(회귀 0). REV-20260610-0181 [SKIPPED:read-agg]. 동시세션→0181. worktree `ai/claude/usage-model-stacked`.

### TASK-0180 LLM 사용량 차트 카테고리별 행 레이아웃 + 일별 폭 채움 + 상세 표 여백 (2026-06-10)
- [x] **Minor §12.3** — 사용자 피드백(몰아넣기 불쾌 + 상세 표 여백). 명시적 행 구조: ① 시간별 토큰(flex4):모델별 비중(flex1)=4:1, ② 역할별[토큰|비용], ③ 계정별[토큰|비용](`.admin-usage-row` 1:1, wrap). grid(charts/span2) 폐기. 일별 차트 SVG viewBox W=`el.clientWidth`(폴백 760)·H 200 고정 → 넓은 카드 가로 채움(막대 cap 64). 상세 표 카드화(`.admin-usage-table-card`, max-width:none width:100%) + 모델별 full·역할별|계정별 2열. 권한/스키마/백엔드 무변경. 캐시버스터 `?v=20260610-usage-rows`. node --check PASS. REV-20260610-0180 [SKIPPED:css-layout]. 동시세션→0180. worktree `ai/claude/usage-row-layout`.

### TASK-0179 LLM 사용량 차트 넓은 화면 가로 여백 해소 (CSS grid) (2026-06-10)
- [x] **Minor §12.3** — 사용자 보고(넓은 모니터 가로 여백 과다). 차트 6개를 `.admin-usage-charts` grid(`auto-fill minmax(400px,1fr)`)로 다열 배치 — 넓은 화면 채움·좁으면 wrap(860px↓ 1열). 일별=`.admin-usage-span2`(2칸)+SVG max-width 1000. 도넛/역할별/계정별/비용2 각 1칸. h3/h4 카드 내부로. 권한/스키마/백엔드 무변경(순수 레이아웃). 캐시버스터 `?v=20260610-usage-grid`. node --check PASS. REV-20260610-0179 [SKIPPED:css-layout]. 동시세션→0179. worktree `ai/claude/usage-grid-layout`.

### TASK-0178 LLM 사용량 화면 여백 컴팩트화 (CSS/SVG) (2026-06-10)
- [x] **Minor §12.3** — 사용자 보고(불필요한 여백 과다). TASK-0177 디자인 정렬에서 카드·섹션·차트 패딩이 누적된 것을 축소. styles.css: `.admin-usage-card` 16/18→12/14, `.admin-usage-section` mt 20→12, `.admin-usage-metric` 패딩 11/14·strong 19·span mb 4, usage `.summary-metrics` gap 10·mt 0, row gap 12. admin.js: 일별 차트 H 252→196(pT 10·pB 26), HBar margin 6. 권한/스키마/백엔드 무변경(순수 spacing). 캐시버스터 `?v=20260610-usage-compact`. node --check PASS. REV-20260610-0178 [SKIPPED:css-spacing]. 동시세션 다수→0178. worktree `ai/claude/usage-spacing-compact`.

### TASK-0177 LLM 사용량 상세 표 추정 비용 컬럼 + gstack 디자인 관점 정렬 (2026-06-10)
- [x] **Minor §12.3** — 사용자 요청(차트·상세 표 비용 일치 + gstack 디자인 리뷰 자율 적용). **A**: 역할별·계정별 상세 표에 추정 비용 컬럼 추가(by_role/by_account 의 cost_usd=TASK-0176, 백엔드 무변경) + tbl 헬퍼 `align:'right'` → 숫자 컬럼 우측정렬·tabular-nums. **B(디자인)**: general-purpose subagent 의 gstack `/design-review` 적대적 리뷰 수령 후 적용 — 요약 `.metric-card`/`.summary-metrics` 통일, 임의 hex→디자인 토큰(`--text*`/`--border*`), 차트 `.admin-usage-card` surface 구획, 8px spacing 클래스(`.admin-usage-section/h3/h4`), h2→h3→h4 위계, `.admin-usage-table`(hover·우측정렬·토큰 border), 툴팁 `.admin-usage-tooltip`(토큰화). 차트 팔레트는 유지. styles.css(admin-usage-* 신규) + admin.html(클래스化) + admin.js(요약/표/툴팁/SVG fill 토큰). 캐시버스터 `?v=20260610-usage-design`. 권한/엔드포인트/스키마/백엔드 신규 0. node --check PASS. REV-20260610-0177 [SKIPPED:frontend-design] + design subagent 리뷰 반영(High3+Med4+Low). Windows-browser(PB-0008) 검증 배포 후. worktree `ai/claude/usage-cost-tables-design`. 동시세션 다수→0177.

### TASK-0176 LLM 사용량 역할별·계정별 추정 비용 차트 (2026-06-09)
- [x] **Minor §12.3** — 사용자 요청. 토큰 가로 막대(역할별/계정별) 외에 **추정 비용** 가로 막대 추가. **백엔드**: `admin_llm_usage` by_account 를 `owner_account_id` 단일 GROUP BY → 계정 × `COALESCE(resolved_model,model)` 분해로 변경(비용은 모델별 단가라 모델 분해 필수) + Python 계정별 fold(`_estimate_llm_cost_usd` 모델별 합=`cost_usd`). `_aggregate_usage_by_role` 가 enrich 된 by_account 의 cost_usd 를 역할별 재합산 → `by_role[].cost_usd`. **프론트(의존성 0 SVG)**: `renderHBar(el, rows, valueFmt)` 에 valueFmt 인자 추가(usd) + 역할별/계정별 추정 비용 차트(`#usageRoleCostChart`/`#usageAccountCostChart`, 비용 0 행 제외, hover usd 툴팁). admin.html "추정 비용" 섹션(2열). 캐시버스터 `?v=20260609-usage-cost`. 권한/엔드포인트/스키마/시크릿 신규 0(기존 컬럼 read + TASK-0166 단가 상수 재사용). node --check/py_compile + make test 269 passed/5 skipped(회귀 0). REV-20260609-0176 [SKIPPED:frontend-viz]. 동시세션 0168~0175 선점→0176 재번호. worktree `ai/claude/usage-cost-by-role-account`.

### TASK-0167 관리 콘솔 작은 화면 세로 잘림 수정 (CSS) (2026-06-09)
- [x] **Minor §12.3** — 사용자 보고: 웹브라우저 화면이 작을 때 화면 전체가 안 나오고 잘림. **근본 원인**: `.admin-shell`·`.admin-workspace` 가 `height:100vh; overflow:hidden` 인데 `.admin-pane` 중 dashboard 만 `overflow-y:auto` 보유, usage pane 누락 → 차트(0165/0166)·표로 길어진 usage pane 이 작은 화면에서 세로 스크롤 불가로 하단 잘림(다른 pane 은 내부 `admin-list` 스크롤이라 무관). **수정**: `styles.css` dashboard overflow 규칙에 `[data-admin-pane="usage"].is-active` 셀렉터 추가(dashboard 와 동일 패턴) + admin.html styles.css 캐시버스터 `?v=20260609-usage-overflow`. 권한/엔드포인트/스키마/JS/HTML 구조 무변경 — CSS 셀렉터 1개. REV-20260609-0167 [SKIPPED:css-only]. worktree `ai/claude/usage-overflow-fix`(base main).

### TASK-0166 LLM 사용량 차트 고도화 — 계정별 차트·hover 툴팁·막대 값·시간단위·추가지표 (2026-06-09)
- [x] **Minor §12.3** — TASK-0165 후속(사용자 지적 누락 항목). **백엔드 `admin_llm_usage`**: ① `granularity`(hour/day/week/month) — `date_trunc` 단위 화이트리스트(`_USAGE_GRAN`)로만 삽입(인젝션 차단), bucket 포맷 + 막대 상한. by_day/by_day_model bucket 집계(서브쿼리로 동일 버킷 집합 보장). ② by_model/by_day prompt/completion 분해. ③ `_estimate_llm_cost_usd`+`_LLM_PRICE_USD_PER_1M`(claude 근사, 로컬=0) 모델별·총 추정 비용. 응답 `granularity`/`cost_usd` 추가. **프론트(의존성 0 SVG)**: ① 계정별 가로 막대(`#usageAccountChart`) 신규(역할별 대칭). ② 커스텀 hover 툴팁(`data-tip`+`bindTip`, `<title>` 대체) 전 차트 — 값/비중/호출/비용. ③ 막대 위 총합 값 라벨. ④ 집계단위 드롭다운(`#usageGranSel`) + 기간(1일/1년 추가). ⑤ 요약 추정비용 카드 + 모델별 표 prompt/completion·비용 컬럼. 권한/엔드포인트/스키마/시크릿 신규 0. 캐시버스터 `?v=20260609-usage-charts2`. node --check/py_compile + make test 218 passed/5 skipped(회귀 0). REV-20260609-0166 [SKIPPED:frontend-viz]. **한계**: 비용은 공시가 근사 추정(로컬=$0). Windows-browser(PB-0008) 검증 배포 후. worktree `ai/claude/usage-charts-v2`(base main).

### TASK-0165 LLM 사용량 화면 차트화 (상용 AI 사용량 대시보드 참조) (2026-06-09)
- [x] **Minor §12.3** — TASK-0163 후속(사용자 요청: "상용 ai 제공 서비스의 구조를 참조하여 차트 형식으로"). 표 위주 화면을 Anthropic Console / OpenAI Usage 류로 시각화. **백엔드**: `admin_llm_usage` 에 `by_day_model`(일별 × `COALESCE(resolved_model, model)` 토큰 합) 집계 추가 — 기존 컬럼만(비파괴 read, 스키마 0). **프론트(의존성 0 순수 SVG)**: admin.js ① `renderStacked`(일별 토큰 모델별 누적 세로 막대 + 날짜축 + 범례), ② `renderDonut`(모델별 비중 도넛 + % 범례, 실제 서빙 모델 라벨), ③ `renderHBar`(역할별 가로 막대). 색상 팔레트 `colorMapFor`(로컬/시스템=회색). admin.html usage pane 에 차트 컨테이너(#usageDayChart/#usageModelChart/#usageRoleChart) + 기존 표는 `<details>` 접이식 보존. CDN 미사용(정적자산 baked·WSL 내부 — Chart.js 등 외부 의존 회피). 캐시버스터 `?v=20260609-usage-charts`. 권한/엔드포인트/스키마/시크릿 신규 0. node --check/py_compile PASS. REV-20260609-0165 [SKIPPED:frontend-viz]. Windows-browser(PB-0008) 라이브 screenshot 검증 완료(배포 후). 동시 세션이 TASK-0164(SIGTERM)를 먼저 머지(a207bb4)해 번호 충돌 → 0164→0165 재부여 + main 위로 rebase. worktree `ai/claude/llm-usage-metering`(TASK-0163 연장).

### TASK-0164 이월 처리 — SIGTERM graceful finalizer + RBAC catalog prune + out-of-process 설계 (2026-06-09)

- [x] TASK-0169 (REQ-20260609-0168, **Critical §12.3** — out-of-process ask-worker 실행모델 / ADR-WEB-0004 B). TASK-0159/0160/0164 의 이월 B 구현. `/api/ask` 의 in-process(`asyncio.to_thread`) 실행을 전용 `ask-worker` 로 분리(ask_jobs 큐 claim·실행) → web 재배포/SIGTERM 이 in-flight run 을 죽이지 않음(orphan 구조 제거). **flag `AGENT_ASK_EXECUTION_MODE`(기본 inprocess) 라 본 배포 자체로는 동작 무변경(shadow)**, cutover 는 env 전환. **web 측(app.py)**: `_dispatch_ask_run`(inprocess|worker 분기) + readiness gate(503) + 단일문 slot enforce + 내부 attach loop + `result_json` 응답 shape 패리티 + backstop ownership-aware(B1, 0159/0164 가 worker run skip) + cancel-pending(2g) + 첨부 temp `/shared`(M6). **agent-core 측(feature-0002 CHG-0168)**: `ask_jobs` 마이그레이션·`ask_jobs.py`(atomic claim/lease fencing/sweep)·`ask.py`(worker loop·시간기반 heartbeat·reaper)·`--ask-worker`·healthcheck·config·`set_run_status` 순서(M4). docker-compose `ask-worker` 서비스(stop_grace 70s). **outside-voice 적대적 리뷰 2회(설계 전 + diff) — BLOCKER 3 + MAJOR 4 흡수, 구현 BL-1/MJ-1/MJ-2 추가 수정**(REV-20260609-0168). make test 244 pass(회귀 0)·신규 테스트 3파일·py_compile·ruff clean. PLAN-APPROVED(§2.1, 2026-06-09). worktree `ai/claude/ask-worker`(base 2ad6d03, 동시세션 0166/0167 점유로 0168 재배정). **이월(cutover 게이트)**: 마이그레이션 라이브 적용 → worker=on shadow → 점진 cutover, PB-0008 Windows-browser + 부하·web 재배포 중 run 생존 실측, on_event→lifespan 마이그레이션.
- [x] TASK-0164 (REQ-20260609-0164, **Major §12.3** — run 생명주기 + RBAC catalog delete). in-process(`asyncio.to_thread`) ask 실행이 web 재배포로 orphan("처리중" 고착)을 만드는 근본을 종료 시점에 차단(A) + cosmetic 정리 + 구조적 정답 설계(B, 이월). **A1**: `@app.on_event("shutdown")` finalizer 가 이 프로세스 in-flight run(`>= _PROCESS_BOOT_UTC`)을 error 로 마킹(부팅 reconciliation 의 대칭 역, race 가드 + 8s 소프트캡 + 단일 connect)(AC-0322). **A2**: `_prune_orphaned_permission_catalog` 가 완전 폐기 권한(suggestions.read·execute_sql_on.*)의 고아 WebPermissions 행을 0-참조 가드 하에 DELETE(AC-0323). **A3**: 빈 attachment 그룹 키 = LEAVE(forward-compat). **B**: `DESIGN-ask-worker.md`(ask-worker + ask_jobs 큐 + 롤아웃 플래그) 설계만, 구현 이월(AC-0324, ADR-WEB-0004). 신규 단위테스트 3(`test_shutdown_finalizer.py`) + 전체 pytest 통과(회귀 0) + py_compile. **outside-voice 적대적 리뷰 PASS-WITH-NITS, BLOCKER 0**(REV-20260609-0164, NIT 2건 흡수). 동시 세션 TASK-0162/0163 점유로 0164 재배정, base bf0a61f. **이월**: out-of-process 구현(B), set_run_status 4-conn(기존 helper), on_event→lifespan 마이그레이션.

### TASK-0163 LLM 사용량 admin 계정별/역할별 집계 + 모델 해소 표시 (2026-06-09, cross-feature — 주관 feature-0002)
- [x] **Major §12.3** — 관리 콘솔 > 감사 > LLM 사용량의 모델별/계정별/역할별 집계 복구. 본 feature 면은 **엔드포인트 + 프론트**: `admin_llm_usage`(GET /api/admin/usage) 가 by_model 을 `COALESCE(resolved_model, model)` 로 집계(요청 별칭+실제 모델 둘 다 노출), by_account 를 이미 열린 MySQL conn 으로 `WebAccounts LEFT JOIN WebRoles ON r.Id=a.RoleId` 로 username·role enrich(추가 conn 개방 0), 신규 순수 헬퍼 `_aggregate_usage_by_role`(account None→`(시스템)`, role None→`(역할 없음)`, total_tokens desc) Python 폴딩 후 응답에 `by_role` 추가. 프론트 `admin.html` 역할별 표(#usageByRole) + `admin.js loadUsage` 가 `tbl(rows,cols)` fmt 에 row 전달, by_role 렌더·계정 username·역할 컬럼·모델 `별칭 → 해소` 표시, 캐시버스터 `?v=20260609-usage-roles`. 권한 `console.usage.read`(admin) **무변경 — RBAC 카탈로그/엔드포인트 신규 0**. 계측·마이그레이션(`resolved_model` 컬럼)·RC1 race 수정은 feature-0002 주관([[feature-0002-agent-core/docs/TASK.md]] TASK-0163, REV-20260609-0163). 검증: make test 215 passed/5 skipped + node --check + outside-voice 적대적 diff 리뷰 PASS(BLOCKER 1 흡수).

### TASK-0162 진행중("작업 중") 말풍선 생명주기 수정 — 대화 전환 누출 + 새로고침 경과시간 초기화 (2026-06-08)

- [x] TASK-0162 (REQ-20260608-0162, **Minor §12.3** — frontend SPA + thin read-only backend 필드). 사용자 보고 2건: (A) 요청 처리 중 다른 대화로 전환하면 직전 작업의 "작업 중" 말풍선이 전환한 대화에 나타남. (B) 새로고침 시 말풍선 경과시간이 0 으로 초기화됨.
  - **근본 원인 A**: `selectConversation` 이 직전 대화의 `state.pendingBubble` 을 `_savedPendingBubbles` 에 스냅샷 저장만 하고 `state.pendingBubble` 을 비우지 않아, 전환 후 `loadHistory→renderMessages` 가 잔존 말풍선을 새 대화 하단에 렌더. (이미 `beginPendingConversation` 은 `stopProgressPolling({reset:true})` 로 분리하는데 `selectConversation` 만 누락.)
  - **근본 원인 B**: 새로고침 시 `loadHistory`(및 `initializeWorkspace` resume 경로)가 말풍선을 `startedAt: Date.now()` 로 재생성 → 실제 run 시작이 아니라 새로고침 시각 기준이라 elapsed 리셋. 서버는 KV `last_status_at`(processing 전이 시 1회만 기록 = run 시작 시각)을 갖고 있으나 `/api/history` 가 반환하지 않아 클라가 알 수 없었음.
  - **수정**: (1) `selectConversation` 스냅샷 저장 직후 `stopProgressPolling({reset:true})` 로 진행 상태(말풍선+polling+elapsed timer) 분리. (2) 백엔드 `/api/history` 가 processing 시 `last_run_started_at`(=KV `last_status_at`) 반환. (3) 프론트 `loadHistory` + `initializeWorkspace` resume 경로가 `Date.now()` 대신 서버 시각(`last_run_started_at` / `ask_status.status_at`)을 `startedAt` 기준점으로 사용(파싱 불가 시 `Date.now()` 폴백). (4) 인접 엣지(리뷰 Nit): loadHistory 가 비-processing 확정 시 `_savedPendingBubbles[cid]` 폐기 → 전환 후 완료된 대화로 복귀 시 stale 말풍선 부활 차단. (5) 정적자산 `?v=` 캐시버스터 task-0156→task-0162 bump(app.js·styles.css).
  - **tz 안전**: 클라 elapsed 는 `new Date("…+00:00").getTime()` 절대 epoch − `Date.now()` 절대 epoch 이라 브라우저 타임존 무관. TASK-0159 의 server-side PG `timestamptz` naive 변환 버그와 무관(이 경로는 `_parse_kv_timestamp` 미사용).
  - **검증**: node --check PASS / py_compile PASS. 적대적 subagent diff 리뷰 REV-20260608-0162 **APPROVE-WITH-NITS, BLOCKER 0** (Nit 2건 본 cycle 반영, Nit 3 실질 window 0 note-only). PB-0008 Windows-browser 라이브 게이트는 배포 후 수행.

### TASK-0161 RBAC 카탈로그 정리 + 죽은 코드 제거 (TASK-0158 Tier 3 종결) (2026-06-08)

- [x] TASK-0161 (REQ-20260608-0161, **Major §12.3** — RBAC 권한 모델 변경 + 죽은 코드). TASK-0158 Tier 3 결정 항목을 권장 방향대로 처리. (1) **거짓 컨트롤 권한 제거** `attachment.execute_sql_on.own/.any`(enforce 0, 관리 그리드 무동작 체크박스) — 정의·시드·catchup 제거 + `_cleanup_deprecated_role_permissions` removals 로 DB 행 멱등 정리 + app.js map 제거. 실제 게이트(allowlist+attachment_reader+sql_guard) 무변경, 런타임 동작 0(교차계정 이미 차단)(AC-0315). (2) **죽은 중복 제거** — `POST /api/list_conversations`(호출자 0, 내부 PG 메서드명과 무관) + `#composerAttachments`/`Pills` DOM·잔여참조·고아 `_toggleAttachmentPill` + `#tabCountAudits` stale 뱃지(AC-0316). (3) **`upload.any` 유지+문서화**(실제 enforce, 의도적 UI 미노출)(AC-0317). **outside-voice 적대적 RBAC 리뷰 PASS-WITH-NITS, BLOCKER 0**(REV-20260608-0161, NIT 2건 본 cycle 흡수). py_compile/node --check PASS. 동시 세션 TASK-0160(agent_core tool_use fix) 점유로 0160→0161 재배정, base a4a2d28 rebase. **이월(별 cycle)**: in-process(to_thread) 실행모델 구조적 재설계(TASK-0159 이월과 동일), attachment 빈 그룹 키 정리(무해).

### TASK-0159 고아 run 무한 폴링 수정 — PG timestamptz stale 회귀 + 부팅 reconciliation (2026-06-08)

- [x] TASK-0159 (REQ-20260608-0159, **Major §12.3** — 런타임 run 생명주기/데이터 경로). 사용자 보고: 웹 DBA 챗 요청이 "오랜 시간 안 끝남". 진단: `/api/ask` 는 agent 를 `asyncio.to_thread` 로 web 프로세스 안에서 in-process 실행 → web 재배포(14:37 컨테이너 재생성 — 병행 TASK-0158 세션의 배포로 추정)가 in-flight run(`f47482aa`)을 죽여 `set_run_status("done")` 미도달 → KV `last_status='processing'` 영구 고착 → 프런트엔드 `/api/ask_result`·`/api/progress` 무한 폴링(+ 신규 질의 409 차단), 최종 답변 미합성. **추가 결함**: 20분 stale 자동복구가 안 터짐 — `_last_step_at_for_run`(PG 경로)이 `timestamptz`(KST aware)를 UTC 변환 없이 `replace(tzinfo=None)` 해 KST wall-clock 을 UTC 로 오인 → `_compute_display_status` 의 `datetime.utcnow()` 비교에서 elapsed 음수 → stale 영구 거짓 (CHG-20260527-0001 cutover 회귀). **수정(app.py 단일 파일)**: (1) `_last_step_at_for_run` aware→`astimezone(timezone.utc).replace(tzinfo=None)` 변환(naive 통과), (2) `@app.on_event("startup")` `_reconcile_orphaned_runs_on_startup` — in-process 모델상 새 프로세스엔 살아있는 run 이 없으므로 부팅 전 시각의 `last_status='processing'` 고아를 `error` 로 일괄 정리(daemon thread + `last_status_at >= _PROCESS_BOOT_UTC` race 가드, boot 시각 초 절삭), (3) `set_run_status` import. **즉시 해소**: 라이브 PG KV 의 고아 run f47482aa 를 `error` 로 표시(스피너 해제 + 409 해제). **회귀 테스트**: `tests/test_orphan_run_stale_recovery.py` 6 case (tz 변환·stale 판정·boot-guard) PASS. **이월(후속 TASK)**: SIGTERM graceful finalizer + in-process→out-of-process 실행모델 재설계. 검증: py_compile PASS / pytest 6 passed / verify-completion PASS / REV-20260608-0159 APPROVE-WITH-NITS(BLOCKER 0). **병행 충돌 메모**: 본 cycle 중 다른 세션이 TASK-0158(진입점 Tier1·2, frontend-only)을 main 에 연속 병합 → 본 작업을 0159 로 재배정, app.py 무충돌(그쪽은 app.js/admin.js/index.html/styles.css)로 rebase.

### TASK-0158 "진입점 없는 기능" 전수조사 후 진입점 구성 (2026-06-08, 완료 — Tier1·2 + PB-0008 검증)

- [x] TASK-0158 (REQ-20260608-0158, **Minor §12.3** — frontend-only). 사용자 요청: TASK-0157 과 동일 클래스(구현 완료·진입점 부재) 기능 전수조사 후 순서대로 진입점 구성. design.md 9섹션 형식 적용(`docs/DESIGN-entry-points.md`). repo-level 전수조사 결과는 `TODOS.md` 에 기록.
  - **Tier 1 (완료)**: [x] 즉시답변 — `#finalizeBtn` 고아 제거 + composer `#composerFinalizeBtn` 신설(AC-0308). [x] 공유 링크 관리 — ··· 메뉴 "공유 관리" + `openShareManager` 모달(목록+취소, `GET shares`/`DELETE share`)(AC-0309). [x] scopeAll — attach 패널 `#composerAttachmentsScopeAll` 체크박스(핸들러·백엔드 기존, 마크업만 신설)(AC-0310). node --check PASS. REV-20260608-0158 [SKIPPED:frontend-only-no-new-rbac-no-schema-no-secret].
  - **Tier 2 (완료)**: [x] audit.purge 버튼(dry-run 미리보기+typed-confirm, `#auditPurgeBtn`/`openAuditPurgeModal`)(AC-0311). [x] 내 활동기록 profile 탭(`data-profile-tab="audits"`/`loadProfileAudits`, `/api/profile/audits`)(AC-0312). [x] 감사 필터 facet 드롭다운(datalist+`loadAuditFacets`)(AC-0313). [x] attachment-grants 대시보드 카드(`#dashboardGrantHealth`/`loadGrantHealth`)(AC-0314). admin.html/admin.js + index.html/app.js + styles.css. node --check PASS(app.js·admin.js).
  - **Tier 3 (진입점 아님 — 결정/정리)**: [ ] `attachment.execute_sql_on.*` 미적용 권한(enforce or remove, RBAC 변경→outside-voice) [ ] `conversation.attachment.upload.any`(product 결정) [ ] 죽은 중복 정리.
  - **PB-0008 Windows-browser 완료 게이트**: [x] 실제 Windows Chrome 검증 **PASS(39/39 step)** — 7개 진입점 전부 live 동작 확인(finalize morph·공유관리 모달·scopeAll·내활동기록·grant카드·audit.purge 모달·facet `{res:9,actor:5}`). 시나리오 `tests/win-browser-task0158.scenario.json`, 증거 스크린샷 10장(`/tmp/win-browser-shots/task0158/`), 상세 TEST.md §4.

### TASK-0157 요청 중단(interrupt) 진입점 복구 (2026-06-08)

- [x] TASK-0157 (REQ-20260608-0157, **Minor §12.3** — frontend-only). 사용자 보고: 요청 후 "중단" 기능이 UI에 안 나타나고 진입 경로가 없음. /investigate 근본 원인: 중단/즉시 답변 버튼이 커밋 `4ba71f5` 의 영구 숨김(`style="display:none"`) `#progressCard` 안에 고아로 남아 `renderProgress()` 의 `classList.remove("hidden")` 가 인라인 style 에 가려 무효 → 정상 동작 중 취소 진입점 0개. 백엔드 `/api/cancel`·에이전트 루프 폴링·RBAC 는 정상. **수정(ChatGPT 패턴)**: `renderComposer()` 가 처리 중 `#sendBtn` 을 "중단" 버튼으로 모핑(stop 아이콘 + `.is-stop` 위험색 + native disabled 해제) + click 핸들러 busy→`cancelCurrentRun()` 분기 + hover 툴팁 숨김 + 중단 권한 access-blocked 반영(AC-0306/0307). 변경 2파일(app.js/styles.css). node --check PASS. **이월**: finalize 진입점 미노출(동일 근본 원인, 사용자가 단일-버튼 send-morph 선택으로 본 cycle 범위 밖). REV-20260608-0157 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret].

### TASK-0151 첨부 text inline cap 정렬 버그 수정 (2026-06-05)

- [x] TASK-0151 (REQ-20260605-0151, **Major §12.3** — DB 조회 UX 개선의 web 면). `_prepare_text_inline_attachments` 의 SELECT 정렬 `ORDER BY Id ASC LIMIT %s` → `ORDER BY Id DESC LIMIT %s` + 선별 후 `inline_entries.reverse()`. text 첨부가 count cap(20) 초과 시 이전엔 가장 오래된 20개만 inline 주입되고 방금 첨부한 최신 파일이 조용히 누락됐던 것을, 최신 cap개 보존 후 표시 순서를 시간순으로 복원하도록 수정. AccountId IDOR 스코프·size cap 무변경. agent_core 의 첨부 리뷰 우선순위 prompt 개편(feature-0002 TASK-0151)과 한 쌍. outside-voice 적대적 diff 리뷰 ACCEPTED (REV-20260605-0151, BLOCKER 0).

### TASK-0124 관리 콘솔 RBAC 권한 정합 및 폐기 권한 정리 (2026-05-28)

- [x] TASK-0124 (REQ-20260528-0124, **Minor** §12.3 — RBAC 시드 롤 정합 + 폐기 권한 DB 정리). 사용자 직접 요청: (1) `sales` 롤이 `conversation.create` + `conversation.ask` 를 보유하면서 `conversation.delete.own` 이 없어 자신의 대화를 삭제할 수 없는 구조적 비정합. (2) `conversation.suggestions.read` 가 `conversation.ask` 와 항상 함께 부여되는 종속 권한 — 단독 실효성 없는 zombie 권한. (3) `pending` 롤의 `conversation.file.read.own` — "승인 전 조회 전용" 의미와 파일 다운로드 혼재. **수정**: (a) `SEED_ROLE_DEFINITIONS` 의 `sales` 에 `conversation.delete.own` 추가. (b) `conversation.suggestions.read` 를 `PERMISSION_DEFINITIONS` + 모든 시드 롤에서 제거, suggestions endpoint 게이트를 `conversation.ask` 로 변경, `_legacy_permission_codes_from_row` 에서 제거. (c) `pending` 의 `conversation.file.read.own` 제거. (d) `_ensure_seed_roles()` 의 catchup_codes 에 `conversation.delete.own` 추가 (sales 기존 계정 반영). (e) `_cleanup_deprecated_role_permissions(conn)` 신규 함수 — `DELETE FROM WebRolePermissions` 로 폐기 권한을 기존 롤 rows 에서 멱등 제거. (f) `docs/STATUS.md` 변경 이력 2건 추가. 신규 RBAC 권한 코드 추가 없음 / DB 스키마 변경 없음 / secret handling 없음 → outside-voice review SKIPPED.

### TASK-0108 Sprint 3 — Admin-only manual KB ingest (B: DDL/KB 보강) (2026-05-26) — ⚠ 제거됨 (2026-05-27)

> **REQ-20260527-0001 — 설계 결함으로 제거**: (1) KB 등록 목록이 대화 첨부(`WebConversationAttachments`)에 의존 — 관리 영역이 사용자 대화에 기생하는 구조로 독립성 원칙 위반. (2) Weight=90 manual fact 가 DB 스키마 변경 시 오래된 정보를 자동 수집(Weight=1)보다 우선 참조 — 스키마 오염 위험. 재설계 시 별 cycle 로 진행.
> **제거 범위**: `admin.html` KB 등록 탭/pane, `admin.js` kbIngest 상태·함수 221 LOC, `app.py` `attachment.kb.write.any` RBAC 정의 + admin seed grant + `GET /api/admin/attachments` + `POST /api/admin/attachments/kb-ingest` 두 endpoint. `kb_ingest.py` 모듈 + `test_kb_ingest*.py` 는 보존 (재설계 시 재활용 가능).

- [x] TASK-0108 (REQ-20260526-0108, **Major** §12.3 — RBAC 신규 코드 1개 + 신규 admin endpoint + AgentMemoryFactEntries manual ingest path 신설). **2026-05-27 UI/endpoint 제거 (REQ-20260527-0001).** BRIEFING-attachment-multi-cycle.md §6.3 Sprint 3 Cycle 3 (B: DDL/KB 보강, Major, ~1주). TASK-0094 PLAN-APPROVED (2026-05-21) 의 multi-cycle plan 안 sprint 3 implementation. **본 cycle 산출 (예정)**: (a) `app.py` PERMISSION_DEFINITIONS 에 `attachment.kb.write.any` (admin only) 1 코드 + role grants 4 catchup (admin/dba 만), (b) `unit/feature-0002-agent-core/src/modules/kb_ingest.py` 신규 — 첨부 본문 → AgentMemoryTexts INSERT + AgentMemoryFactEntries INSERT 의 멱등 path. ConversationId='__kb_manual__' reserved sentinel + FactKey=ScopeKey 자체 + Weight=90 (BRIEFING D 의 0.9 scale, manual fact 우선) + SourceType='manual' + FactFingerprint=SHA1(normalized body). 동일 (conv, scope, key) 기존 active row (Weight>0) UPDATE Weight=0 으로 logical supersede (Status 컬럼 추가 회피, 회귀 0), (c) `app.py` `POST /api/admin/attachments/kb-ingest` 신규 endpoint — RBAC gate `attachment.kb.write.any` + body `{attachment_id, scope_key, source_type='manual', weight=90}` validation + storage_minio 본문 fetch + kb_ingest.ingest_manual() 호출 + audit `attachment.kb.ingest` dispatch + 응답 `{fact_entry_id, scope_key, text_hash, superseded_count}`, (d) `admin.html` "스키마 정의서 KB 등록" pane (kind=text/markdown 또는 .sql ext 표기 첨부 list + ScopeKey 입력 + preview + ingest 버튼), (e) `admin.js` pane 이벤트 핸들러, (f) `repo/AGENTS.md` §11.3 확장 — "manual ingest fact 의 SourceType='manual', Weight=90 (= BRIEFING 의 0.9 scale, 자동 수집 Weight=1 대비 우선)", (g) tests — `unit/feature-0003-agent-web-ui/tests/test_kb_ingest_rbac.py` (RBAC matrix 4 case + ScopeKey 충돌 superseded + audit dispatch) + `unit/feature-0002-agent-core/tests/test_kb_ingest.py` (module unit test). **outside-voice review (Codex) 호출** — RBAC 신규 코드 + audit + ScopeKey supersede semantics = 사용자 메모 `feedback_outside_voice_for_rbac.md` 정합. **본 turn 의 deliverable 은 backend (a~c) + frontend (d~e) + AGENTS.md (f) + tests (g) + docs + Codex review + commit/PR/merge**. base = main HEAD (5448611 — KB Postgres bootstrap fix 흡수 후, `_pg_available()` true 환경 자연).

### TASK-0107 첨부 내용 LLM 직접 인지 + drag&drop UX 확장 (2026-05-22)

- [x] TASK-0107 (REQ-20260522-0107, **Major** §12.3 — LLM 동작 변경 + sandbox SQL 동선 + UI 진입점 확장). 사용자 직접 보고 2건. **(1) 파일 첨부 후 LLM 이 "실제 내용을 직접 볼 수 없습니다" 응답** — TASK-0094 의 sandbox ingest 파이프라인 (`sandbox_ingest.ingest_attachment` + `agent_attachment_<sha256>` schema + WebConversationAttachments.MetaJson `sandbox_table_name`) 정의는 있었으나 **caller 가 ship 안 됨** (REVIEW.md 1465 의 미해결 항목). 결과: MetaJson 에 sandbox_table_name 미기록 → `_build_attachment_context_section` 의 ATTACHED FILES 영역이 schema 명을 noindict → LLM 의 SQL tool 이 SELECT 시도하지 않고 사용자에게 텍스트 복붙 요청. **수정 (3-phase)**: Phase A (활성화) — `app.py` 의 upload endpoint (`POST /api/conversations/{cid}/attachments`) 의 audit dispatch 직후 `threading.Thread(target=_ingest_attachment_background, daemon=True)` spawn (kind=csv|xlsx 한정). 신규 helper `_ingest_attachment_background` 가 storage_minio 로 bytes 받기 → `CREATE SCHEMA IF NOT EXISTS agent_attachment_<sha256(cid)[:32]>` (root user 단일-user MVP — 4-user 분리 grant 는 후속 cycle) → `_open_memory_connection(database=schema_name)` 으로 sandbox conn → `sandbox_ingest.ingest_attachment` 호출 → MetaJson 에 `sandbox_schema_name` + `sandbox_table_name` (csv) 또는 `sheets[]` (xlsx) 기록 + UploadStatus='ingested'. 실패 시 `_mark_ingest_failed` 가 UploadStatus='failed' + MetaJson.degraded_reason 기록. `db.py` 의 `connect()` 에 `agent_attachment_*` schema 패턴 매칭 → **primary 라우팅 강제** (replica latency / 미배포 환경에서도 즉시 SELECT 가능). Phase B (LLM 인지) — `agent_core.py` 의 `_build_attachment_context_section` 전면 강화: metadata + sandbox_table_specs 수집 + each table 의 `information_schema.columns` SELECT (column 명 + data_type) + `SELECT * FROM <schema>.<table> LIMIT 5` sample rows 출력 (markdown 표, 80자 cell truncate, pipe escape, table cap 20). 명시 INSTRUCTION 추가 — "When the user asks about an attached file's contents, first try to answer from the sample rows above. If more data is needed, call execute_sql against the sandbox table … Do NOT ask the user to paste the file contents — the data is already accessible." UploadStatus='uploaded' (ingest 미완 또는 'failed') 분기는 별도 안내. **(2) drag&drop UX + 새 대화 시 첨부 차단** — composer-wrap 만 drop zone 이라 chat 영역 대부분에서 drop 미발동 + 사용자가 새 대화 진입 직후 (pendingSentinel 미발급 시점) 첨부 시도 시 "대화 컨텍스트 미정" toast 로 차단. **수정**: index.html 에 chat-pane 자식으로 `#chatDropOverlay` (점선 border + 아이콘 카드) 추가, styles.css 에 `.chat-drop-overlay` (absolute inset 0 + backdrop-filter blur + fade-in animation) + `.chat-pane { position: relative }` 추가. app.js `_bindComposerAttachmentEvents` 에 chat-pane scope drag/drop 핸들러 + `_isFileDrag()` types Files guard + dragCounter 중첩 추적 + window dragend / drop 시 reset (drop miss 방어) + chat-pane 밖 drop 시 브라우저 기본 동작 (파일 새 탭 열기) preventDefault. `_uploadComposerAttachment` 진입 시 컨텍스트 미정 (activeConversationId 없음 + pendingSentinel 없음) 검출 시 `conversation.create` 권한 검증 후 자동으로 pendingNewConversation=true + `_newPendingSentinel()` 발급 + 모든 render 호출 — 기존 lazy-create path 재사용. py_compile + node --check PASS. backend RBAC / DB schema / endpoint contract / D11 consent / D13 server-side bytes 전 무변경. 4-user 분리 grant model (BRIEFING D2/D15) 은 후속 cycle (.env 비밀번호 미설정 → 단일-user MVP 채택). 본 cycle worktree `ai/claude/0107-attachment-content`.

### TASK-0106 첨부 모듈 import 경로 + lazy-create 첨부 staging (2026-05-22)

- [x] TASK-0106 (REQ-20260522-0106, **Major** §12.3 — 외부 storage 통합 + 사용자 노출 첨부 동선 회복). 사용자 직접 보고 2건: (1) 웹 첨부 업로드 시 `Error: storage 모듈 import 실패: cannot import name 'storage_minio' from 'modules' (/app/modules/__init__.py)` toast — backend `/app/modules` 는 feature-0002-agent-core 의 unified namespace (14 module cross-injection) 인 반면 `storage_minio.py` 는 feature-0003-agent-web-ui 의 module 로 Dockerfile 이 `/app/web/modules/` 로 copy. `app.py` 의 `from modules import storage_minio` (3 callsite: vision inline `_prepare_vision_inline_images` L6044, upload endpoint L7555, metadata endpoint L7771) + `from modules import sandbox_schema` (L11862) 가 잘못된 namespace 검색 → `from web.modules import …` 으로 교체. feature-0002-agent-core/src/modules/attachment_reconciliation.py 의 `_delete_minio_object()` (worker 환경 host dev sibling path fallback 보존) 에는 `from web.modules import storage_minio` 우선 시도 + ImportError 시 기존 sys.path 삽입 fallback 의 dual-mode 보강. (2) "+ 새 대화" 클릭 후 첫 메시지 전송 전엔 첨부 불가 — `_uploadComposerAttachment` 의 `if (isLazy)` 조기 차단 toast. lazy-create 패턴 (TASK-0048) 의 부수 효과로 cid 미발급 = `/api/conversations/{cid}/attachments` 호출 불가. **수정 (Option A — client-side staging)**: lazy 분기에서 즉시 차단 대신 pendingSentinel bucket 에 status=`staged` + `_localFile=File` 로 보관, `sendPrompt()` 의 lazy-create path 가 staged 첨부 ≥1 감지 시 `/api/new_conversation` 으로 cid 즉시 발급 → `_flushStagedAttachmentsToCid(earlyCid, pendingKey)` 신규 helper 가 staged 일괄 업로드 → askBody 를 `lazy_create=true` (legacy) 에서 `conversation_id=earlyCid` (즉시-cid 모드) 로 전환 + `attachment_ids` 에 union. staged 가 0 인 lazy-create 는 기존 lazy_create=true 단일 호출 보존 (TASK-0048 정신). pill rendering 에 `data-staged="true"` 속성 + "(첫 메시지와 함께 업로드)" tooltip 추가. `_toggleAttachmentPill` 에 staged 토글 = remove (실수 클릭 시 재선택 부자연스러움 회피). py_compile + node --check PASS. backend / RBAC / DB schema / endpoint contract 무변경. 본 cycle worktree `ai/claude/0106-attachment-fix`. cache-bust 갱신 필요 (live deploy 후 별 commit).

### TASK-0105 Profile Drawer '내 감사 로그' 탭 제거 (2026-05-22)

- [x] TASK-0105 (REQ-20260522-0008, **Minor** §12.3 — UI 노출 범위 축소). 사용자 직접 요청 — 일반 사용자에게 Profile Drawer 내 '내 감사 로그' 탭이 노출되어선 안 됨. TASK-0089 가 추가한 탭 버튼 (`profileAuditTab`, `data-profile-tab="audit"`) + drawer 패널 (`data-profile-pane="audit"`) + JS 로직 일체 (`_profileAuditEscapeHtml` / `_profileAuditFormatDt` / `_profileAuditHasReadPermission` / `updateProfileAuditTabVisibility` / `_profileAuditReadFilters` / `_profileAuditClearFilters` / `loadProfileAuditList` / `renderProfileAuditList` / `renderProfileAuditDetail` / `attachProfileAuditHandlers` + state.profileAudit 초기값) + CSS (`profile-audit-*` 전체 블록) 를 index.html / app.js / styles.css 에서 제거. backend `/api/profile/audits` endpoint 및 admin 콘솔 '감사 로그' 탭 무변경. node --check + py_compile PASS. cache-bust: 기존 `v=20260522-task-0098-perms` 유지 (frontend 파일 재배포 시 갱신 권장). 본 cycle worktree `ai/claude/0105/remove-audit-tab`.

### TASK-0104 외부 노출 web 컨테이너 HTTPS 종단 활성화 (2026-05-22)

- [x] TASK-0104 (REQ-20260522-0007, **Major** §12.3 — 외부 사용자 전원 영향 + 자격증명 처리 동선의 secure-channel 요건 충족). 외부 사용자가 `https://112.185.196.20:18080/` 로 접속할 수 없던 이슈 수정. **근본 원인**: `repo/.env` 는 `ENABLE_WEB_TLS=1` 로 설정되었고 `docker-compose.yml` 의 web entrypoint 에는 TLS 분기가 있으나, `docker-compose.override.yml` (gitignored, dev 용 template) 가 entrypoint 를 평문 HTTP uvicorn 으로 강제 override 하고 있었음 — TASK-0103 에서 secure-context guard 는 추가했지만 secure channel 자체가 비활성. **수정**: `docker-compose.override.yml` 의 web entrypoint 를 `--ssl-keyfile /certs/mysql-ai.company.local/privkey.pem --ssl-certfile /certs/mysql-ai.company.local/fullchain.pem` 포함한 HTTPS 종단으로 교체. 기존 인증서 (`../artifacts/certs/mysql-ai.company.local/`) 는 SAN 에 `IP Address:112.185.196.20` 이미 포함되어 있어 재발급 불필요. `docker-compose.override.yml.example` 에는 Variant A (local dev plain HTTP) / Variant B (외부 노출 HTTPS, 본 cycle default) 두 형태를 주석으로 명시. 호스트 포트 18080 매핑 그대로 — same-port HTTPS 전환. **외부 영향**: 기존 HTTP 18080 사용자는 모두 HTTPS 로 전환 필요 (TLS 종단 교체이므로 동일 포트의 HTTP 동시 제공 안 됨). **검증**: `sudo docker compose up -d web` 후 `curl -sk https://112.185.196.20:18080/` → HTTP 200 + `<title>DQA — Database Query Assistant</title>` 응답. 컨테이너 로그 `Uvicorn running on https://0.0.0.0:8000`. backend / RBAC / endpoint contract / DB schema / WebCrypto 클라이언트 코드 무변경. 근본 해결 완료로 TASK-0103 의 "blocked banner" 는 외부 IP HTTP 접속자에게도 자동 안내됨 (HTTP 18080 자체가 끊겨 사용자는 즉시 HTTPS 로 이전).

### TASK-0103 API Vault secure context 사전 차단 + UX 안내 (2026-05-22)

- [x] TASK-0103 (REQ-20260522-0006, **Major** §12.3 — 외부 사용자 전원 영향 + 자격증명 처리 동선). 외부 사용자가 `http://112.185.196.20:18080/` 로 접속하여 OpenAI API Key 입력 시 모호한 toast 만 출력되며 저장 안 되던 이슈 수정. **근본 원인**: WebCrypto SubtleCrypto (`window.crypto.subtle`) 는 secure context (HTTPS / localhost) 에서만 정의됨. 외부 IP 의 HTTP 접속 시 `undefined` → `encryptPlainApiKey()` 의 `crypto.subtle.importKey(...)` 가 `Cannot read properties of undefined (reading 'importKey')` throw → catch 블록에서 noisy toast 만 출력, 저장 실패. 서버는 `requires_secure_context: True` 를 내려줬지만 클라이언트가 활용 안 함. **수정**: (1) `isVaultCryptoAvailable()` helper (`window.isSecureContext && window.crypto?.subtle`). (2) `updateVaultReadiness()` `blocked` 신규 상태 — 빨간 banner + 한국어 사유 안내 (`public_url` 이 https 면 보안 주소 표기). (3) `syncVaultSteps()` 가 `cryptoOk = false` 시 모든 step disable + saveVaultBtn 차단. (4) `encryptPlainApiKey()` 진입 시점에 명시적 throw — UI 우회 시도도 안전 차단. (5) styles.css 에 `vault-banner[data-state="blocked"]` 빨간 톤 추가. cache-bust `v=20260522-vault-secure-context`. backend / RBAC / endpoint contract / DB schema / 암호화 알고리즘 (PBKDF2 + AES-GCM) 무변경. `docker compose build web` + `up -d --no-deps web` 으로 배포. 근본 해결 (HTTPS 종단점 추가) 은 후속 인프라 cycle 로 분리.

### TASK-0102 topbar 관리 콘솔 버튼 role fallback gate (2026-05-22)

- [ ] TASK-0102 (REQ-20260522-0005, **Minor** §12.3 — topbar `관리 콘솔` 버튼 role 기반 fallback gate). 테스트 결과 `sales` 역할 사용자에게 topbar 관리 콘솔 버튼이 노출되는 현상 확인. **근본 원인**: TASK-0100 에서 추가한 `console_access` 플래그가 구버전 서버(미재시작) 또는 캐시된 응답에서 `undefined` 로 오는 경우, 기존 `Boolean(undefined)` = `false` 는 정상이나, 서버가 TASK-0100 이전 코드를 실행 중이면 `canOpenAdminConsole() → can("console.access") → Boolean(state.user)` 경로로 항상 `true`. **수정**: `console_access` 가 서버 응답에 포함된 경우 그것을 사용, 없으면 `role.key === "admin"` 으로 fallback — role 필드는 TASK-0098 이전부터 항상 직렬화되므로 버전 무관하게 존재. app.js, index.html(cache-bust) 변경. backend / RBAC / DB / endpoint 무변경.

### TASK-0100 관리 콘솔 버튼 RBAC gate 수정 (2026-05-22)

- [x] TASK-0100 (REQ-20260522-0004, **Minor** §12.3 — `관리 콘솔` 버튼 노출 조건 수정). "admin" 역할 이외의 사용자에게 `관리 콘솔` 버튼이 노출되는 이슈 수정. **근본 원인**: TASK-0098 에서 frontend `can()` 함수를 `Boolean(state.user)` 로 단순화하면서, `canOpenAdminConsole()` 도 로그인한 모든 사용자에게 `true` 반환 → 버튼 노출. **수정**: `_serialize_account()` 에 `console_access: bool` 최소 플래그 추가 (`_account_has_permission(account, "console.access")` 기반). `canOpenAdminConsole()` 이 `Boolean(state.user?.console_access)` 을 검사하도록 변경. TASK-0098 의 "permissions 전체 노출 차단" 설계를 유지하면서 UI gate 에 필요한 최소 정보만 전달. backend / RBAC catalog / DB schema / endpoint contract 무변경. py_compile + node --check PASS. cache-bust `v=20260522-console-access-gate`.

### TASK-0099 Audit subsystem followup backlog 사후 tracker hygiene (2026-05-22)

- [x] TASK-0099 (REQ-20260522-0003, **Minor** §12.3 — docs-only tracker hygiene). TASK-0073 audit subsystem followup backlog 8 entries (TASK-0086~0093) 8/8 완료 후 정리 cycle. TASK.md 의 stale `[ ]` 체크박스 2건 close: (1) line 152 TASK-0072 (main 통합 `f298f90` + hotfix bundle TASK-0074~0080 모두 deployed but 상태 `outside-voice-review` 미갱신), (2) TASK-0073 line 2767 `AGENT_AUDIT_ENABLED=0 + AGENT_MODE=prod` startup fail-closed acceptance (TASK-0092 V1-V3 fail-closed scenario 가 정확히 검증 → close). 추가로 STATUS.md feature-0003 row 에 audit followup backlog 8/8 완료 marker append. docs-only — 코드 / RBAC / 스키마 / endpoint 변경 0. outside voice trigger 미해당 (audit/RBAC 표면 변경 없음). 본 cycle CHG-20260522-0003, REV-20260522-0003 [SKIPPED:doc-only-tracker-hygiene] on `ai/claude/feature-0003-agent-web-ui` worktree.

### TASK-0073 Audit subsystem followup backlog (2026-05-20)

본 worktree (`ai/claude/0086/audit-followup`) 는 TASK-0073 의 후속 cycle 들을 등재한다. 본 cycle 작업자는 아래 6 entries 중 하나 이상을 선택해 plan-eng-review / plan-ceo-review / outside voice 후 진행. 각 entry 는 별 cycle (별 PLAN-APPROVED marker + 별 CHG/REV) 로 분리한다.

- [x] TASK-0086 (REQ-20260520-0001, **Major** §12.3 — `WebAccountActivity` legacy table DROP + dual write 종료). **DROP 완료 (2026-05-20)**. backup `artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql` (11,950 bytes, 74 row, digest `a09e7898d1ce88711f7a850ab5fbcc91`) + scratch restore rehearsal PASS + 1:1 정합 (legacy=74, mirror=74) + 사용자 명시 ack. Codex outside voice review 5 findings + 2 minimum-fix 흡수 후 v2 redesign (helper Option B 명시 제거 / dispatcher-only smoke / mysqldump 옵션 보강 / scratch restore / rollback 2 시나리오). 코드: `_log_search_activity()` legacy INSERT 제거 + `_ensure_web_account_activity_schema()` 호출×2+정의 제거 + `_migrate_web_account_activity_to_audit()` rollback window 보존 + test_audit_migration.py M3 제거. 본 cycle CHG-20260520-0005, REV-20260520-0005 on `ai/claude/0086/legacy-drop` worktree.
- [x] TASK-0087 (REQ-20260520-0002, **Major** §12.3 — 외부 LAN trust 강화, feature-0006 + feature-0003 협업). Caddy `header_up X-Forwarded-For {client_ip}` 정규화 + `_get_client_ip()` 조건부 trust (env `WEB_TRUSTED_PROXIES`) + malformed XFF token IP 검증 + mode-aware fail-loud (prod/staging `RuntimeError`, dev/test stderr WARNING) + proxy mode + empty env regression 경고. Codex outside voice review 5 Major + 1 Minor 흡수 후 v2 redesign (RFC1918 default 사용자 명시 결정 유지 + Caddy XFF 정규화로 multi-hop 차단). `docs/SECURITY.md §9.7` 갱신. 본 cycle CHG-20260520-0010, REV-20260520-0010 on `ai/claude/0087-lan-trust-hardening` worktree.
- [x] TASK-0088 (REQ-20260520-0003, Minor §12.3 — `slow_query_log` 통합 **ADR-0020 Decoupled 채택**). TASK-0073 Codex C1 lock-in 의 별 cycle 분리 → 최종 ADR. **Option C — Decoupled** 채택, slow_query_log 와 WebAuditEvents 통합 안 함. 주 근거 = raw SQL text PII 차단 (PasswordHash/Token/API key/임시 비밀번호/raw LLM prompt literal). 운영 성능 관측 = `performance_schema`/`sys` digest views (1차) + slow_query_log incident enable (2차). Codex outside voice 5 critical findings + 2 minimum-fix 흡수 후 v2 redesign (current state framing 정정 + Option A/B reject 재작성 + PS digest-first 권유 + SaaS trigger 명확화). 본 cycle CHG-20260520-0007, REV-20260520-0007 on `ai/claude/0088/slow-query-log-adr` worktree. docs only.
- [x] TASK-0089 (REQ-20260520-0004, Minor §12.3 — 작업 화면 audit drawer UX). profile drawer 5번째 탭 "내 감사 로그" 신설 + 신규 backend endpoint `/api/profile/audits` + `/api/profile/audits/{event_id}` (scope=own 강제). Codex outside voice review 5 critical findings + 2 minimum-fix 흡수 후 v2 redesign: (1) `/admin/` endpoint 의미 mismatch → 별 `/api/profile/audits` 신설 (Codex C1), (2) backend scope="own" 강제 — `.any` 보유자도 본인 row만 (Codex C2), (3) CSV export/purge drawer 미노출 (Codex C3 — admin 한정), (4) drawer 폭 390px 1-column + inline detail expand + ChangeJson 수평 스크롤 (Codex C4), (5) tab visibility = audit.read.own || audit.read.any + 403 graceful (Codex C5). 본 cycle CHG-20260520-0009, REV-20260520-0009 on `ai/claude/0089-audit-drawer-ux` worktree.
- [x] TASK-0090 (REQ-20260520-0005, Minor §12.3 — CSV streaming export). `/api/admin/audits/export.csv` 의 hard cap 50k row 제거 + `StreamingResponse` + keyset cursor pagination 전환. Codex outside voice review 5 critical findings + 2 minimum-fix 흡수 후 v2 redesign: (1) sync generator + streaming-only conn (Codex C1 — async event loop blocking 회피), (2) max_id high-water mark (Codex C2 — long transaction 회피), (3) chunk_size 500 + 64KiB byte-threshold flush (Codex minimum-fix), (4) try/finally cleanup (Codex C5 — client disconnect cursor/conn 누설 차단), (5) export self-audit start + complete/aborted (Codex C4 — DoS 운영 제어), (6) hard cap 50k 제거 + SECURITY.md §9.5 갱신. 본 cycle CHG-20260520-0008, REV-20260520-0008 on `ai/claude/0090-csv-streaming-export` worktree.
- [x] TASK-0091 (REQ-20260520-0006, ~~Minor~~ **Major** §12.3 — PATCH admin/products audit before-state full snapshot + audit integrity fix). TASK-0073 Phase A5 의 `admin.product.update` audit 의 before-state 가 `{id, product_key}` 만 → full snapshot 으로 확장 + Codex outside voice 5 findings 흡수. **scope 확장 (Minor→Major)**: Codex C2 가 `admin_update_product()` 의 `autocommit=True` default + UPDATE 즉시 commit + audit 실패 시 rollback 가능 0 인 **audit integrity 결함** 노출. 본 cycle 일괄 fix: (1) `_audit_product_snapshot()` 신규 helper (single-row + SELECT FOR UPDATE + system_prompt summary only, SECURITY §9.2 정합), (2) endpoint 명시 transaction (autocommit=False + commit + finally autocommit=True), (3) `_AUDIT_BUILDER_PRODUCT_FIELDS` 확장 (`+is_default`, `+sort_order`, `+system_prompt_summary` / `-databases`, `-system_prompt` full), (4) `default_cleared_product_ids` side effect 기록, (5) sentinel smoke PASS (SENTINEL `TASK-0091-SENTINEL` ChangeJson 부재 확인, system_prompt content drop). 본 cycle CHG-20260520-0006, REV-20260520-0006 on `ai/claude/0091/product-audit-snapshot` worktree.
- [x] TASK-0092 (REQ-20260520-0007, Minor §12.3 — `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` startup fail-closed 검증). TASK-0073 Phase E 의 사용자 위임 항목 1 건. **7 vector matrix PASS (7/7)** — V1~V3 fail-closed + V4 dev bypass + V5 positive control + V6 strict-string-equality (Codex C3) + V7 default. Codex outside voice review 5 findings + 2 minimum-fix 흡수 후 v2 redesign 적용 (`docker run --entrypoint python --no-deps` + `import web.app` + stderr 3 substring 검증 + TEST.md **§4** append). 본 cycle CHG-20260520-0004, REV-20260520-0004 on `ai/claude/0092/audit-prod-fail-closed` worktree.
- [x] TASK-0093 (REQ-20260520-0008, Minor §12.3 — `bin/verify-completion.sh check_12` audit endpoint routing 정적 검사). TASK-0073 Phase E hotfix (CHG-20260520-0001) 의 routing 회귀 fragility 보강. Codex outside voice review 5 findings 흡수 후 plan v2 redesign (SKIP→FAIL structural / inline 4-path→auto-discovery static GET / `/purge` method-aware 제외 / helper split + fixture test / `9 checks`→`10 checks` footer). Phase A~D 모두 검증 PASS (production positive + 5 fixture negative + 5 other-feature SKIP). 본 cycle CHG-20260520-0003, REV-20260520-0003 on `ai/claude/0086/audit-followup` worktree.
- [x] TASK-0098 (REQ-20260522-0002, **Critical** §12.3 — Profile Drawer 탭 재구성 + 권한 정보 API 단위 차단). 사용자 직접 요청 (2026-05-21). Profile Drawer 탭 5 → 4 = `[프롬프트, 보안 및 계정, API Vault, 내 감사 로그(gated)]` (보안+계정 통합 + "활동 정보" 최상단). "권한 현황" 패널 = 운영자 전용 정보 분류 → UI + `/api/auth/me` 양쪽 차단. `/api/admin/me` 신규 endpoint 분리 (console.access gate, Codex F1 blocker fix). `_serialize_account(account, *, include_permissions: bool = False)` 시그너처 + 7 self callsite 자동 permissions 제거 + admin 3 callsite 명시 보존. frontend `can()` = `Boolean(state.user)` 단순화 ("표시 허용 + 실행은 backend 403 fallback" 패턴, Codex F5). `apiFetch` 403 공통 toast. backend 일반 사용자 경로 403 메시지 5 패턴 9 callsite normalize. admin.js `/api/auth/me` → `/api/admin/me` 전환. TASK-0089 audit 탭 보존. tests/test_admin_me_rbac.py 4 + tests/test_auth_me_rbac.py 5 시나리오 신규. Codex outside voice 6 findings 흡수. **PR #49 multi-race rebase**: 본 cycle 원래 4 commit (base 8888130) 가 main stale 진행 (#45/#47/#48/#50/#52/#61 + DQA 브랜딩 + TASK-0095/0096 v2) 흡수 후 main HEAD 20f0344 위 단일 squash commit. ID reassign: TASK-0094→TASK-0098 / REQ-20260521-0001→REQ-20260522-0002 / AC-0199~0207→AC-0226~0234 / CHG·REV-0001~0004→CHG·REV-20260522-0002 / cache-bust `v=20260522-task-0098-perms`. backup branch `backup/profile-tabs-restructure-pre-rebase`. worktree `ai/claude/profile-tabs-restructure`.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-21 (TASK-0098 ex-0094/0096, Critical §12.3 — Profile Drawer + permission API 차단 + Codex outside voice 6 findings 흡수. multi-race rebase 시점 ID reassign + squash 재적용.) -->

- [x] TASK-0095 (REQ-20260521-0003, **Major** §12.3 — GLOBAL system prompt layer + 신규 `설정` 탭). 사용자 직접 요청 — "현재 서비스 사용자의 시스템 프롬프트 누적 구조에서, 최상위 전역 프롬프트도 구성해주세요." 4 layer (BASE → Product → Role → Account) 의 BASE 가 코드 상수 hard-code 라 운영자 수정 불가하던 구조를 5 layer (GLOBAL → Product → Role → Account, BASE = code constant fallback) 로 확장. WebSystemPrompts schema 무변경 (Scope VARCHAR(16) 가 이미 'global' 수용). RBAC 2 권한 신설 (`system_prompt.global.read/.write`, group=`settings`, admin auto-grant). 관리 콘솔 sidebar 에 신규 `설정` 탭 + 확장 가능한 `admin-settings-section` sub-section 패턴 도입 — 차후 운영 항목 추가 시 동일 패턴으로 sub-section 누적. AC-0011 갱신 + AC-0199 ~ AC-0204 신설. 본 cycle CHG-20260521-0003, REV-20260521-0003 on `ai/claude/global-system-prompt` worktree. **Follow-up** (CHG-20260521-0004, REV-20260521-0004): live deploy 후 사용자 검증 진행 중 발견 — `_ensure_seed_catchup` (fast path) 에 `_ensure_seed_global_system_prompt` 호출 누락. 1줄 hot-fix.
- [x] TASK-0097 (REQ-20260522-0001, **Minor** §12.3 — DQA 브랜딩 적용). 사용자 요청: 웹브라우저 출력 시 'MySQL AI' 제거, DQA (Database Query Assistant) 로 명명, 로고 신설. `index.html` · `admin.html` title/brand-name/auth-title → DQA 전면 교체. `logo-dqa.svg` 신설 (48×48 primary #2563eb, DB 실린더+돋보기 조합). `.auth-logo` / `.brand-icon` CSS background → transparent (SVG 배경 직접 표시). Minor §12.3 — 정적 자산 변경만, backend/RBAC/DB/endpoint 무영향. AC-0219~AC-0222 FUNCTION.md 등재. CHG-20260522-0001, REV-20260522-0001 on `issue/58-dqa-rebrand` branch.
- [x] TASK-0096 (REQ-20260521-0004, **Minor** §12.3 — `설정` pane 을 계정/역할/제품 과 동일한 list-detail 패턴으로 정렬). 사용자 직접 요청 v1 — "`설정` 탭 내부 화면을 `계정`, `역할`, `제품` 과 같이 패널을 분리해줄 수 있을까요?" → 1차로 좌측 sub-sidebar + 우측 panel 의 2-column 패턴으로 전환 (CHG-20260521-0005). 사용자 v2 후속 피드백 — "계정, 역할, 제품 탭과 일관된 디자인이 아닌것으로 확인되었습니다. 검색창을 포함하여, 해당 탭들과 일관된 디자인으로 구성해주세요." → 기존 sub-sidebar 클래스 (`admin-settings-shell/-nav/-nav-*`) 제거, 계정/역할/제품 의 5단 구조 (`admin-list-detail` + `admin-list-col` (검색창 + section-label + `admin-list` rows) + `admin-detail-col` (panel)) 채택. nav row 는 `.admin-list-row.admin-list-row--nav` 변형 (체크박스 슬롯 hidden). 검색 필터는 row 의 `data-settings-keywords` + `data-settings-group` + textContent 합치기 substring 매칭. 새 항목 추가 절차 = `<button class="admin-list-row admin-list-row--nav" data-settings-tab="X" data-settings-group="..." data-settings-keywords="...">` + `<article class="admin-settings-panel" data-settings-panel="X">` + `SETTINGS_PANEL_MOUNTERS` 등록 3 단계. UI restructure only — 데이터/API/권한 무영향. AC-0210 갱신. 본 cycle CHG-20260521-0005 (v1) + CHG-20260521-0006 (v2) , REV-20260521-0005 + REV-20260521-0006 on `ai/claude/global-system-prompt` worktree.

### TASK-0094 (REQ-20260521-0001, **Critical** §12.3 — 첨부 multi-cycle A+B+C+D) (2026-05-21)

본 cycle 의 정본 BRIEFING 은 [BRIEFING-attachment-multi-cycle.md](./BRIEFING-attachment-multi-cycle.md) (Revision 2). Codex outside-voice review 2 회 (REV-20260520-0001 1차 + REV-20260521-0002 2차) 흡수 후 결정 D1~D21 21 건 확정. 본 worktree (`ai/claude/0087/attachment-briefing` — git worktree 이름이 0087 로 박혀 있지만 본 cycle 의 작업 번호는 TASK-0094) 의 commit 으로 lock-in. Sprint 1 implementation 은 별 worktree `ai/claude/0094/sprint-1-foundation-csv` (또는 호환을 위해 `ai/claude/0087/sprint-1-foundation-csv` 도 허용 — §15 cleanup 조건 R-F10 준수) 에서 진행.

**Sprint 분할** (BRIEFING §6):

- [x] **Sprint 0 (cycle cleanup)** — BRIEFING Revision 2 lock-in (PR #40 merged) + AGENTS.md §16.5 Step 6 사후 동기화 결과 REPORT.md 기록 (CHG-20260521-0002). 본 cycle 종료 후 worktree cleanup (§15 R-F10).
- **Sprint 1** — Cycle 0 (Foundation: MinIO compose, multipart upload, `WebConversationAttachments`, RBAC 4 codes, D11 consent infra) + Cycle 1 (A: CSV/Excel ingest, sandbox schema, attachment_maintainer/writer/reader/cleanup MySQL users, **D14 SQL allowlist guard ship 조건**) — Critical, 3~3.5 주. D18 단일 통합 gate. worktree `ai/claude/0094/sprint-1-foundation-csv`.
  - [x] **Phase 1 (Pre-flight)** — ADR-0022 (MinIO 도입) + ADR-0023 (sandbox schema + D15 maintenance path 분리) + ADR-0025 (PGVector 사전 선언, Sprint 4 prerequisite) `docs/DECISIONS.md` 등재. docker-compose.yml `minio` + `minio-init` service 추가. `.env.example` 16 변수 (MINIO_ROOT_USER/PW + MINIO_APP_ACCESS_KEY/SECRET + endpoint/bucket/TTL + 호스트 port 2 + browser redirect + ATTACHMENT_MAX_BYTES_* 3 + ATTACHMENT_AUDIT_HMAC_KEY + SANDBOX_SQL_* 2). `unit/feature-0003-agent-web-ui/src/scripts/minio-init.sh` 부트스트랩 (idempotent bucket + bucket-scoped policy + app key). feature-0001-platform-runtime ANCHOR §1 갱신 (MinIO/Postgres 같은 비-MySQL service 의 platform 책임 명시). 2026-05-21.
  - [x] **Phase 2 (Cycle 0 schema)** — `WebConversationAttachments` + `WebAccountConsents` + `WebAttachmentDerivedMessages` (D19) + `WebConversationAttachmentProviderFiles` (D13) + `WebShareLinks.PolicyVersion` (R-F7) + `WebConversationAttachmentsSandboxSchemas` mapping table. 6 `_ensure_*_schema` / `_ensure_*_column` helper 신설. `_ensure_seed_catchup` (fast path) + `_ensure_web_tables` (slow path) 양쪽 호출 등록. py_compile PASS. 2026-05-21.
  - [x] **Phase 3 (Cycle 0 RBAC)** — `conversation.attachment.upload/read.{own,any}` 4 코드 (group=conversation) `PERMISSION_DEFINITIONS` 추가 + `SEED_ROLE_DEFINITIONS` admin/operator/sales/pending 갱신 (admin=all, operator/sales=upload+read own, pending=read.own만 — D21/R-F14) + `_ensure_seed_roles` admin/operator/sales/dba/pending 5 catchup 갱신 (§5.2 6 checklist 1~5) + app.js label/description map (checklist 6) — backend group=conversation 이므로 attachment group 신설은 Phase 12 SQL guard 의 attachment.execute_sql_on.* 시점에. admin.js 는 backend `/api/admin/permissions` label 직접 사용 — 별 map 없음. py_compile PASS. 2026-05-21.
  - [x] **Phase 4 (Cycle 0 storage)** — `storage_minio.py` wrapper (boto3 + retry + signed URL + smoke test) + D20 dual-key rotation runbook (`RUNBOOK-minio-key-rotation.md`). boto3>=1.34.0 / botocore>=1.34.0 requirements 추가. modules/__init__.py + storage_minio.py 약 350 lines (idempotent client cache + get_storage_config + safe_filename + make_object_key + put/get/delete/signed URL + bucket_exists + run_smoke_test + reset_client_cache + CLI smoke entry). py_compile PASS + 모듈 import smoke 통과. D13 (외부 LLM signed URL 송신 금지) 정합 — `generate_presigned_get()` docstring 에 사내망 다운로드 전용 명시 + `get_object_bytes()` 의 외부 provider 송신 경로 권장. 2026-05-21.
  - [x] **Phase 5 (Cycle 0 upload API)** — 6 endpoint (POST/GET/GET-by-id/DELETE attachment + POST/DELETE consent) + audit 4 ActionCode (`attachment.upload`/`.delete`/`.consent.grant`/`.consent.revoke`) + `build_audit_change_json` case 4 추가 + D7 MIME allowlist + D8 size cap (per_file/conv/account env-driven) + D12 HMAC/extension/size bucket helper + D13 외부 LLM signed URL 송신 금지 정합 (`_serialize_attachment_for_api` 의 signed_url 옵션) + D21 pending bytes deny enforcement (`_account_is_pending` + bytes_access_denied 마커) + RBAC 검증 (`_account_can_access_attachment` 신규 helper). FastAPI UploadFile/File/Form import. py_compile PASS. 2026-05-22.
  - [x] **Phase 6 (Cycle 0 composer UI)** — paperclip + hidden file input + drag-drop overlay (composer-wrap) + attachment pills (status badges: uploading / ready / failed / deselected) + selected toggle + "이 대화의 모든 첨부 사용" scope-all checkbox + D16 attachment selection snapshot (`_composerAttachmentSnapshot` 가 sendPrompt 시점 추출 → askBody.attachment_ids/scope_all 명시 전송) + R-F5 lazy-create 분리 (snapshot key = pending sentinel or conv id) + selectConversation 진입 시 `_loadConversationAttachments(cid)` ground truth 동기화. state.composerAttachments 신규 (byConv / uploadingCount / nextLocalId). app.js JS syntax PASS (node Function check). styles.css 약 130 lines (pill / drop-overlay / paperclip btn). index.html 약 25 lines (composer-attachments + composer-drop-overlay + attach-btn + file input). 2026-05-22.
  - [x] **Phase 7 (Cycle 0 consent)** — D11 + R-F2 grouped batch modal (provider × 3 group: 텍스트/이미지/인덱싱) + revoke flow + GET /api/account/consents 신규 + Profile Drawer "보안 및 계정" 탭 안 consent section. 2026-05-22.
  - [x] **Phase 8 (Cycle 0 share)** — D9 share redact + R-F7 기존 token 자동 redact + PolicyVersion 활성 + share.policy.redact_applied audit case + INSERT PolicyVersion=CURRENT 명시. SHARE_POLICY_VERSION_CURRENT=2 상수. 2026-05-22.
  - [x] **Phase 9 (Cycle 0 lifecycle)** — feature-0002-agent-core/src/modules/attachment_reconciliation.py 신규 (run_once + get_attachment_lifecycle_state + 4 종 SLA 처리). F1 4 state (active/delete_pending+restorable_until/purge_in_progress/erased) _serialize_attachment_for_api 갱신. R-Claim6 tombstone (NOT NULL ConversationId 유지) + F12 pseudonymous event id. 2026-05-22.
  - [x] **Phase 10 (Cycle 1 sandbox)** — .env.example 에 4 MySQL user credentials (maintainer/writer/reader/cleanup) + sandbox_schema.py (sandbox_schema_name_for + ensure_sandbox_schema_via_maintainer R-Claim4 최소권한 (CREATE/ALTER/INSERT/SELECT) + detect_grant_drift + drop_sandbox_schema_via_cleanup) + GET /api/admin/health/attachment-grants R-F4 endpoint. 2026-05-22.
  - [x] **Phase 11 (Cycle 1 ingest)** — feature-0002-agent-core/src/modules/sandbox_ingest.py 신규 (ingest_csv + ingest_xlsx + ingest_attachment, chardet/openpyxl 사용, encoding detect + delimiter detect + sharedStrings/cell/row/col cap + formula stripping + timeout). agent_core.compose_system_prompt 에 _build_attachment_context_section append (env ATTACHMENT_IDS 통해). /api/ask 가 attachment_ids 를 env 로 전달. requirements.txt chardet/openpyxl 추가. 2026-05-22.
  - [x] **Phase 12 (Cycle 1 SQL guard + Sprint 1 Ship)** — sql_guard.py (sqlglot AST shape allowlist, single SELECT/CTE, FOR UPDATE/LOCK/EXPLAIN ANALYZE/SLEEP/BENCHMARK/INTO OUTFILE/LOAD_FILE/information_schema/mysql/performance_schema/sys 거부 + 보조 denylist). attachment.execute_sql_on.{own,any} 2 RBAC (group=attachment) + sales/operator/admin catchup. audit ActionCode 3 (attachment.sandbox.sql_exec/.sql_denied/.scope.all) + build_audit_change_json case. PERMISSION_GROUP_ORDER + WORK_SCREEN/ADMIN_PERMISSION_SECTIONS attachment 그룹 추가. CONVENTIONS.md §10.6 9 group 갱신. **Sprint 1 Ship 완료**. 2026-05-22.
- [x] **Sprint 2 (Cycle 2 Vision Ship — 2026-05-22)** — claude-sonnet-4 / claude-haiku-4 vision flag (`supports_vision`) + `messages_for_provider()` transient content-array (DB string contract 유지) + agent_core image loader (env `ATTACHMENT_IMAGE_INLINE_PATH` 기반, cross-feature import 회피) + `/api/ask` 의 `_prepare_vision_inline_images()` (D11 consent gate, size cap 5MB / count cap 5, 임시 file lifecycle) + `attachment.vision.invoke` audit ActionCode (D12 정합 — raw filename/bytes/object_key 미노출) + D9 share redact 자동 cover (`MetaJson.attachment_derived=true` + `derivation_type="vision_analysis"`) + D19 `WebAttachmentDerivedMessages` join INSERT. feature-0007 (bedrock) 머지 위에서 LiteLLM proxy auto-normalize 활용 — backend 는 OpenAI Chat Completions `image_url` content-array 만 작성, proxy 가 Anthropic Vision spec 으로 변환. **R-F13 provider Files API lifecycle 은 SKIPPED** — 본 cycle 은 base64 inline only (provider 측 잔존 0, Files API 미사용). 14 unit test pass (S2.2 8 + S2.3 6). codex review SKIPPED (사용자 결정 2026-05-22). AC-0280~0285. CHG-20260522-0007. REV-20260522-0014/0015.
- [ ] **Sprint 3** — Cycle 3 (B: DDL/KB 보강, admin-only KB ingest, AgentMemory FactEntries pipe, `attachment.kb.write.any`) — Major, 1 주.
- [ ] **Sprint 4** — Cycle 4 (D: PDF/MD RAG, PGVector dev 단계 도입, chunking + retrieval, **D17 + R-F6 partial_indexed retrieval policy**) — Critical, 3~4 주.

**핵심 결정 21 건** (BRIEFING §2.1 + §2.2 + §17):

D1 S3-compat MinIO / D2 동일 cluster + 별 schema / D3 PGVector / D4 A+B+C+D 전부 4 sprint / D5 Codex review 동반 / D6 lifecycle 4 종 + tombstone + 4 state UX + pseudonymous event id / D7 MIME allowlist / D8 size cap / D9 share derived redact + 기존 token 자동 redact + policy version / D10 PGVector 단계적 / D11 consent provider×class×purpose + grouped modal + provider files lifecycle / D12 audit HMAC + 카테고리 + pseudonym / D13 외부 LLM bytes 서버 read + Files API lifecycle / **D14 sandbox SQL AST allowlist** / D15 wildcard grant 금지 + writer 최소권한 + drift health endpoint / D16 attachment_ids selected-only + lazy-create snapshot / D17 UploadStatus 7 값 + retrieval policy / **D18 단일 통합 PLAN gate 유지** / **D19 `WebAttachmentDerivedMessages` join table** / **D20 MinIO dual-key rotation runbook** / **D21 pending role metadata-only**.

본 cycle 은 PLAN-APPROVED marker 부여 후 Sprint 1 worktree 분리 + implementation 진입. 외부 영향 (PR / 외부 시스템 알림) 은 별도 confirm.

본 backlog 는 본 worktree 의 commit 으로 lock-in. 신규 세션이 본 worktree 에서 진입 (`/_template:entry`) 후 task 선택 + `/plan-eng-review` / `/autoplan` 등 호출.

### TASK-0095 (REQ-20260521-0002, **Major** §12.3 — GLOBAL system prompt layer + 신규 `설정` 탭) (2026-05-21)

본 worktree (`ai/claude/global-system-prompt`) 의 cycle. 사용자 직접 요청 — "현재 서비스 사용자의 시스템 프롬프트 누적 구조에서, 최상위 전역 프롬프트도 구성해주세요. Product / Role / Account 에 기본적으로 처음 누적되어 요청사항에 적용될 부분입니다." `agent_core.py` 의 `SYSTEM_PROMPT` 상수 본문을 DB 화 (BASE 자체를 운영자가 재배포 없이 수정 가능) + 신규 `설정` 탭 신설 (확장성 — 차후 다른 운영 항목 추가 대비) + 그 안에 sub-section "전역 시스템 프롬프트" 마운트.

**누적 순서** (최종): GLOBAL → PRODUCT → ROLE(공통+Product별) → ACCOUNT(공통+Product별).

**핵심 결정** (사용자 in-cycle):
- D1 — BASE 본문을 DB row (`scope='global'`, ProductId/RoleId/AccountId 모두 NULL) 1행으로 이전. 코드 상수 `SYSTEM_PROMPT` 는 bootstrap fallback 으로 유지 (DB row 부재 / mem_conn None / SQL exception 시 안전망).
- D2 — RBAC 신규 2건: `system_prompt.global.read`, `system_prompt.global.write`. admin only auto-grant (다른 role 은 admin override).
- D3 — admin endpoint scope allowlist 에 `'global'` 추가. global scope 는 product_id/role_id/account_id 무시 (force NULL).
- D4 — 신규 admin UI 탭 `설정` (data-admin-tab="settings") + 내부 sub-section 패턴 (`admin-settings-section` data-settings-section). 첫 sub-section = 전역 시스템 프롬프트 (`buildSystemPromptEditor({scope:'global'})`). product/role/account select 미표시.
- D5 — Bootstrap seed: 신규 deploy 시 `_ensure_web_system_prompts_schema()` 다음에 `_seed_global_system_prompt()` 가 idempotent INSERT (row 부재 시에만, SYSTEM_PROMPT 코드 상수 본문). 이후 admin 수정이 우선 — UPDATE 안 함.
- D6 — Audit: `admin.system_prompt.update` builder 의 기존 `request_ctx['scope']` reference 자연 흡수, resource_id pattern `global:0:0:0`.

**Phase 분할**:
- Phase A — `agent_core.py compose_system_prompt()` 첫 부분 GLOBAL fetch + fallback 추가.
- Phase B — `app.py` WebSystemPrompts schema (Scope enum 확장 — VARCHAR 라 추가 변경 0, 단 _seed_global helper 신설), `_load_system_prompt`/`_upsert_system_prompt` 는 scope str 만 받으므로 무변경.
- Phase C — RBAC 2건 추가 (PERMISSION_DEFINITIONS) + admin role catchup 2 codes.
- Phase D — admin endpoint scope allowlist 확장 (GET/PUT 양쪽) + 권한 검사 분기 (`system_prompt.global.read/write`).
- Phase E — admin.html 에 `<button data-admin-tab="settings">설정</button>` + `<section data-admin-pane="settings">` + admin.js 의 settings pane 핸들러 + `buildSystemPromptEditor({scope:'global'})` 마운트. `buildSystemPromptEditor` 가 scope='global' 일 때 product select hide.
- Phase F — docs (FUNCTION.md system prompt assembly 5 layer 갱신, MODIFY.md CHG-20260521-0003, REVIEW.md REV-20260521-0003, REPORT.md §1 sticky note).
- Phase G — verify-completion.sh `--pre-commit feature-0003-agent-web-ui` + commit + main fast-forward.

**Affected files** (estimate 8): agent_core.py / app.py / admin.html / admin.js / FUNCTION.md / MODIFY.md / REVIEW.md / REPORT.md.

**Risk**: Major §12.3 — 모든 LLM 응답에 영향 (GLOBAL 이 모든 conversation 의 첫 system message). DB row 비정상 시 fallback 상수 보존으로 zero-data state 방지. Audit hook 자연 흡수 (builder 변경 0).

본 cycle 은 PLAN-APPROVED marker 부여 후 즉시 Phase A 진입. 외부 영향 (PR / 배포) 은 별도 confirm.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-21 (TASK-0095, Major §12.3 — GLOBAL system prompt layer 신설. agent_core.py SYSTEM_PROMPT 상수 본문 → WebSystemPrompts scope='global' 1 row DB 화 + 코드 상수 fallback 유지. RBAC 2건 (`system_prompt.global.read/.write`) admin only. 신규 `설정` 탭 + 내부 sub-section 확장성 패턴. compose_system_prompt() 가 GLOBAL 을 가장 먼저 누적. worktree ai/claude/global-system-prompt 에서 진행, 별도 commit 후 main fast-forward.) -->

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-21 (TASK-0094, Critical §12.3 — 첨부 multi-cycle A CSV ingest + B DDL/KB + C Vision + D PDF RAG 4 sprint 분리. D1~D21 21 결정 확정 (D14 SQL allowlist guard 통과를 Sprint 1 ship 조건). Codex outside-voice review 2 회 흡수 (REV-20260520-0001 1차 17 Valid + REV-20260521-0002 2차 Critical 3 / Major 11 / Minor 2 → F8 만 사용자 명시 거부, 위험 격리는 D14 + R-Claim4 + R-F4 + D20 조합으로 충족). BRIEFING-attachment-multi-cycle.md Revision 2. worktree ai/claude/0087/attachment-briefing (git worktree 명 유지, 본 cycle TASK-0094) 별도 commit. Sprint 1 implementation 은 별 worktree 분리.) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0085, Minor §12.3 — lazy-create 사이드바 optimistic pending entry (multi-pending sentinel-keyed Map + click swap to sentinel context), "+ 새 대화 송신 직후 다른 대화 전환 시 새 대화 entry 가 사이드바에서 잠시 사라지는" UX 회귀 fix + 사용자 의도 "작업 step 현황의 출력" 지원. worktree ai/claude/0083/pending-list-entry 별도 commit) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0084, Minor §12.3 — D2Coding 우선 monospace stack 으로 전역 통일 재시도. 사용자 후속 요청 "D2Coding 폰트를 우선해줄 수 있을까요?" + AskUserQuestion 응답 "본문 + 코드 모두 (전역 monospace 통일 부활)". CHG-0013 monospace 시도 → CHG-0014 sans-serif 환원 → CHG-0015 D2Coding 우선 부활. worktree ai/claude/task-0084-d2coding 별도 commit) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0083, Minor §12.3 — :root 의 --font 토큰을 한글 가독성 우선 system-ui sans-serif stack 으로 갱신, --mono 는 원래 stack 유지. 사용자 첫 요청 (monospace 통일, CHG-0013 — a7b7ded 흡수) 후 가독성 피드백 받고 sans-serif 환원. worktree ai/claude/task-0083 별도 commit) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0082, Minor §12.3 — lazy-create unique sentinel design (state.pendingSentinel + _newPendingSentinel + closure-aware cleanup), 첫 in-flight 중 + 새 대화 클릭 시 input 비활성 회귀 fix + TASK-0081 stale 가드 자연 흡수) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0081, Minor §12.3 — beginPendingConversation stale flag 회복 가드 + sendPrompt catch 분기 pendingNewConversation cleanup, 두 번째 새 대화 send 차단 회귀 fix) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0080, Minor §12.3 — _collect_matched_excerpts AgentMemoryMessages UNION AgentCoreMessages, snippet 부재 회귀 차단) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0079, Minor §12.3 — .chat-pane flex 1 1 auto + min-height 0 layout hotfix, TASK-0066 cascade 잔여 결함) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0078, Minor §12.3 — search modal 3 항목 추가 hotfix of TASK-0077: mouseup race 보강 + preset 텍스트 축약 + snippet line-based clip) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0077, Minor §12.3 — search modal 5 항목 hotfix bundle of TASK-0072/0076: min 2 char + 소유자 facet 제거 + 기간 preset + mouseup race + snippet 본문 excerpt) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0076, Minor §12.3 — search modal UX 3 결함 hotfix bundle of TASK-0072: facet 동작 + 키보드 scroll + 매칭 message jump) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0075, Minor §12.3 — TASK-0072 + TASK-0074 HTTP smoke 실행 결과 §4 기록, append-only) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0074, Minor §12.3 — search modal 색상 가독성 hotfix of TASK-0072, light theme 토큰 정합) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0073, Critical §12.3 — 모든 계정 행위 audit 기능 + 관리 콘솔 조회, CEO review 9 + Codex outside voice 14 findings + redesign 흡수) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0072, Critical §12.3 — 타 계정 대화 검색·필터 + outside voice 보강) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0071, Minor §12.3 — shell grid row hotfix) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0070, Minor §12.3 — admin list-detail grid row hotfix) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0069, Minor §12.3 — admin workspace flex hotfix) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0068, Minor §12.3 — admin layout 정합) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0067, Minor §12.3 — 제품 칩 composer 이전) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0066, Minor §12.3 — UI layout 재구조화) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0065, Minor §12.3 — UI 정리 follow-up) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0063, Major §12.3) -->
<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-15 -->
- [x] TASK-0085 (REQ-20260519-0014, Minor §12.3 — lazy-create 사이드바 optimistic pending entry) 사용자 직접 요청 — "+ 새 대화 에서 요청을 보내면, 해당 대화가 사용자 입장에서(웹브라우저에서) 즉시 활성화된 대화 객체로 받아들이도록 구성" + "현재는 + 새 대화 에서 요청 후 다른 대화로 전환할 때, 이전에 요청한 신규 대화가 잠시동안 목록에서 사라지는 이슈" + click UX 결정 "대화 내부 진입도 가능하도록 구성해주세요. 작업 step 현황의 출력을 위해서입니다". 원인: TASK-0048 lazy-create 패턴에서 frontend 가 backend `/api/ask` 응답 도착 전까지 conversation_id 미발급 → `state.conversations` (사이드바 list) 에 신규 entry 없음 → 사용자가 다른 대화로 전환 시 `appendPendingItem` placeholder + backend list 둘 다 새 entry 없음 → 사이드바 완전 소실 구간 발생. Design: multi-pending sentinel-keyed `state.pendingConversationEntries` Map 추가. lazy-create 진입 시 entry add + 사이드바 즉시 표시. closure-aware cleanup (성공·실패 모두 자기 sentinel entry 만 remove — TASK-0082 unique sentinel design 정합). 신규 `appendInFlightPendingItems()` + `_switchToPendingConversationContext(entry)` helper. 응답 도착 + refreshWorkspace 시점에 실 cid entry 등재 → optimistic entry 자연 swap. 클릭 시 sentinel 컨텍스트로 swap + pendingBubble 복원 → 응답 도착 시 closure 일치로 자동 cid binding + startProgressPolling 시작. multi-pending 동시 진행 시 각 sentinel 분리 보존. 변경 5 영역 (state field line 120 추가, sendPrompt 진입 line 3596 + success line 3685 + catch line 3705, renderConversationList line 1209~1450 의 hasPending split + appendInFlightPendingItems + combinedPrepend, `_switchToPendingConversationContext` helper line 3100~). cache-bust `v=20260519-unique-sentinel` → `v=20260519-pending-entries`. backend / RBAC / endpoint / audit / DB 무변경. node --check PASS. 회귀 시나리오 5 종 (송신 직후 다른 대화 전환 → entry 사이드바 지속 표시 / 응답 도착 → 자동 cleanup + 실 cid 등재 / catch → "전송 실패" 3 s 후 cleanup / pending entry click → 컨텍스트 swap + pendingBubble 복원 + 자동 cid binding / multi-pending 분리 보존). worktree `ai/claude/0083/pending-list-entry` 격리 → main ff-merge.
- [x] TASK-0084 (REQ-20260519-0013, Minor §12.3 — D2Coding 우선 monospace stack 으로 전역 통일 재시도) 사용자 후속 요청 "D2Coding 폰트를 우선해줄 수 있을까요?" + AskUserQuestion 응답 "본문 + 코드 모두 (전역 monospace 통일 부활)". 흐름: CHG-0013 monospace 시도 → CHG-0014 한글 가독성 호소로 sans-serif 환원 → CHG-0015 D2Coding (NAVER 한글 monospace 가독성 검증) 우선으로 monospace 통일 부활. `:root` 의 `--font` / `--mono` 두 토큰을 단일 D2Coding 우선 monospace stack 으로 통합 (`"D2Coding", "D2Coding ligature", "Cascadia Code", "SFMono-Regular", Consolas, "Noto Sans Mono CJK KR", ui-monospace, Menlo, monospace`) + `--font: var(--mono)` 참조. admin.html cache-bust `v=20260519-cjk-readable` → `v=20260519-d2coding-mono`. index.html cache-bust 미갱신 (TASK-0083 과 동일 — 사용자 main wt revert 의도 존중). CHG-0015 / REV-0011 / AC-0187 등록. main wt 가 다른 AI 작업자의 merge conflict (UU) 상태로 멈춰 있어 worktree `ai/claude/task-0084-d2coding` 별도 commit + main fast-forward push.
- [x] TASK-0083 (REQ-20260519-0011 + REQ-20260519-0012, Minor §12.3 — web UI typography stack 갱신: 한글 가독성 우선 system-ui sans-serif) 사용자 두 번 요청 — (1) 첫 요청 "프로젝트로 실행되는 웹브라우저 내에서 출력되는 폰트를 monospace로 변경하여 문자열 길이와 실제 표현되는 위치가 정합" → 본 cycle 의 첫 시도로 `:root` 의 `--font` / `--mono` 를 monospace stack 으로 통합 (CHG-0013 — 다른 AI 작업자의 a7b7ded commit 에 docs 변경만 흡수됨, src 변경은 본 worktree 로 분리). (2) 사용자 후속 보고 "한글 기준으로 눈이 아픕니다… 한글 기준으로 가장 범용성있는 폰트로 다시 설정해주세요" → 본 cycle 의 최종 결정으로 monospace 통합 방향 폐기 + `--font` 를 한글 친화 sans-serif stack 으로 변경 (`system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", "맑은 고딕", "Helvetica Neue", Arial, sans-serif`). `--mono` 는 원래 stack 복원 (`"Cascadia Code", "SFMono-Regular", Consolas, monospace`), `var(--mono)` 명시 사용처 (코드/로그 영역) 는 monospace 유지. admin.html cache-bust `v=20260518-shell-grid-rows` → `v=20260519-cjk-readable`. index.html cache-bust 미갱신 (사용자 main wt revert 의도 존중 — 사용자 hard refresh 권장). CHG-0014 / REV-0010 동시 기록. 다른 AI 작업자의 main wt 영역과 격리된 worktree `ai/claude/task-0083` 에서 commit + main fast-forward push.
- [x] TASK-0082 (REQ-20260519-0010, Minor §12.3 — lazy-create unique sentinel design) 사용자 직접 보고 followup of TASK-0081 — "대화 요청을 보낸 후, + 새 대화 버튼을 클릭한 후에도 요청 텍스트 입력칸이 활성화되지 않는 이슈". 원인 (TASK-0081 보다 근본): 글로벌 단일 `PENDING_CONV_SENTINEL = "__pending__"` 토큰이 첫 lazy-create in-flight 시 busyConversations 에 점유 → 두 번째 + 새 대화 진입 후에도 `isCurrentConvBusy()` 가 same sentinel 검사로 true 반환 → `renderComposer()` 가 `promptInputEl.disabled = true` 그대로 → input 활성화 안 됨. 추가로 TASK-0081 의 guard 분기는 첫 대화 in-flight 중 + 새 대화 클릭 시 early return + renderComposer 미호출이라 input.disabled state 가 갱신되지 않는 부수 결함도 발생. Design: 각 lazy-create 진입마다 unique sentinel 부여 (`state.pendingSentinel` + `_newPendingSentinel()` helper). closure 로 각 sendPrompt 가 자기 sentinel 만 cleanup → 두 번째 대화 컨텍스트의 state 보존. TASK-0081 의 stale flag 회복 가드는 본 design 에서 자동 흡수 (각 호출이 새 sentinel reset). 변경 5 군데 (state 정의 line 115, helper line 156 부근, isCurrentConvBusy line 333~339, beginPendingConversation line 2993~3014, sendPrompt busyKey line 3458~3475 + success cleanup line 3522~3539 + catch cleanup line 3537~3551). cache-bust `v=20260519-pending-recovery` → `v=20260519-unique-sentinel`. backend / RBAC / endpoint / audit / DB 무변경. node --check PASS. 회귀 시나리오 4 종 (in-flight 중 + 새 대화 → input 활성화 + 두 번째 send 정상 / catch 후 + 새 대화 → 정상 / 응답 후 + 새 대화 → 정상 / pending bubble error 표시 보존).
- [x] TASK-0081 (REQ-20260519-0009, Minor §12.3 — `beginPendingConversation` stale flag 회복 가드 + `sendPrompt` catch 분기 `pendingNewConversation` cleanup) 사용자 직접 보고 — 웹 UI 에서 새 conversation 만들고 첫 요청 송신 후, 다시 "+ 새 대화" 로 별개 conversation 진입해 send 시도하면 두 번째 send (요청 UI 버튼, Ctrl+Enter) 가 무동작. 원인: `app.js` 의 (a) `beginPendingConversation()` 의 early return 가드가 `state.pendingNewConversation === true` 만 검사 — 첫 lazy-create send 가 catch 분기 (network/timeout) 로 종료된 경우 flag cleanup 누락 → stale state → 두 번째 "+ 새 대화" 클릭이 입력란 포커스만 잡고 return → `state.activeConversationId = ""` reset 도 안 됨 → `sendPrompt()` 의 `isCurrentConvBusy()` 가 `pendingNewConversation=true && busyConversations.has(sentinel)` 검사에서 sentinel 잔존 여부와 무관하게 새 대화 진입 가드에 막힘. (b) catch 분기 (line 3536 부근) 가 `state.pendingNewConversation` 을 cleanup 하지 않음. Fix 2 군데 — (a) `beginPendingConversation()` 의 가드 조건을 `pendingNewConversation && busyConversations.has(PENDING_CONV_SENTINEL)` 로 좁힘 → 첫 send 가 실제 in-flight 일 때만 진입 보류, stale state 면 통과해 정상 reset 흐름으로 진입. (b) `sendPrompt()` catch 의 isLazyCreate 분기 진입 시점에 `state.pendingNewConversation = false` 명시 cleanup. backend / RBAC / endpoint / audit / DB 무변경. node --check PASS. cache-bust `v=20260519-chat-pane-flex` → `v=20260519-pending-recovery`. 회귀 시나리오 5 종: ①정상 첫 송신 후 두 번째 새 대화 진입 + send → 통과 (sentinel 잔존 0, guard 통과), ②첫 송신 timeout 에러 후 두 번째 새 대화 → catch 의 `pendingNewConversation=false` cleanup + 새 진입 정상, ③첫 송신 in-flight 중 사용자가 "+ 새 대화" 클릭 → guard 가 sentinel 존재 검사로 진입 보류 (의도적 — 같은 sentinel 중복 race 방지), ④AC-0077 의 pending bubble error 표시는 cleanup 과 무관 (`state.pendingBubble` 별도 state), ⑤AC-0072~0077 lazy-create 정상 흐름 무영향 (success path 의 line 3522 `pendingNewConversation = false` 그대로 유지).
- [x] TASK-0080 (REQ-20260519-0008, Minor §12.3 — `_collect_matched_excerpts` 의 AgentMemoryMessages + AgentCoreMessages UNION) TASK-0077 의 followup. 사용자 직접 확인 — `excerpt 의 AgentCoreMessages 포함 (UNION)` 미해결. TASK-0072 `_list_conversations` search EXISTS subquery 는 두 table 모두 검사하나 TASK-0077 의 excerpt 추출은 `AgentMemoryMessages` 한정이라 *core 에만 message 있는 conv* 는 search 결과 list 에 포함되어도 snippet 비어 있던 회귀. Fix: backend `_collect_matched_excerpts` 의 SELECT 를 UNION ALL 로 두 table 모두 매칭 message 후보 모음 → `ROW_NUMBER() OVER (PARTITION BY cid ORDER BY msg_id DESC)` 으로 conv 별 더 최근 매칭 1건 선택. msg_id 의 두 table namespace 차이는 더 큰 id = 더 최근 (시간 monotonic) 가정. `ConversationId` 의 collation mismatch 회피 위해 `COLLATE utf8mb4_unicode_ci` 통일. cache-bust `v=20260519-snippet-line` → `v=20260519-chat-pane-flex`. RBAC / audit / endpoint contract / line-based clip 로직 무변경.
- [x] TASK-0079 (REQ-20260519-0007, Minor §12.3 — `.chat-pane` flex layout hotfix, TASK-0066 cascade 잔여 결함) 사용자 screenshot 보고 — 짧은 대화 + 큰 viewport 조합에서 composer 아래로 viewport bottom 까지 회색 빈 영역 노출. 원인: `.chat-pane { display: flex; flex-direction: column; overflow: hidden; background: var(--bg); }` 만 정의 + `flex: 1` 누락 → `.chat-column` flex container 안에서 자식 max-content 만 차지. `.messages-wrap { flex: 1 }` 이 chat-pane 안에서 grow 하려면 chat-pane 자체가 column 의 남은 영역 차지 필요. TASK-0066 ChatGPT 패턴 layout 재구조화 시점 누락 (TASK-0068~0071 cascade hotfix chain 은 admin 영역만 다뤘고 작업 화면의 chat-pane 은 미적용). Fix: `.chat-pane` 에 `flex: 1 1 auto; min-height: 0` 추가 (CSS 2 line). 다른 속성 무변경. backend / RBAC / endpoint / JS 무변경. node --check / py_compile 대상 변경 없음.
- [x] TASK-0078 (REQ-20260519-0006, Minor §12.3 — search modal 3 항목 추가 hotfix of TASK-0077) 사용자 직접 테스트 보고 3 항목: (1) **mouseup race 보강** — TASK-0077 의 mousedown-only 추적이 부족한 edge case 발견. modal 바깥 mousedown → modal 안 mouseup 일 때도 close 됨 (click 의 target 이 mousedown + mouseup 의 공통 ancestor 인 overlay 가 되는 경우). Fix: `state.searchModal.mouseupOnOverlay` 도 추가 추적, `overlay.click` 시 `mousedownOnOverlay + mouseupOnOverlay + ev.target === overlay` 3 개 모두 true 일 때만 close. 즉 의도적인 backdrop click (양 끝점 모두 backdrop) 만 close 트리거. (2) **preset 텍스트 "부터" 제거** — "1시간 전부터" → "1시간 전" 5 버튼 모두. 사용자 결정 (버튼 크기 간소화 / 접근성). data-preset-hours 데이터 속성 무변경. (3) **snippet 본문 발췌 line 출력** — TASK-0077 의 `_collect_matched_excerpts` 가 매칭 위치 ±40 char clip 으로 multi-line 의 일부만 cut 됐었음. Fix: 매칭 위치의 line 경계 (`\n` 직후 ~ `\n` 직전) 를 찾아 *line 전체* 를 excerpt 로 반환. line 이 매우 길 경우 (>220 char) 만 매칭 위치 ±60 char clip + "…". `.search-snippet` CSS 의 `-webkit-line-clamp` 2 → 3 + `line-height: 1.45` + `max-height: 4.6em` 으로 시각 line clip 도 완화. backend / RBAC / audit / endpoint contract 무변경. cache-bust `v=20260519-search-presets` → `v=20260519-snippet-line` (styles.css + app.js). py_compile + node --check PASS + make web 재배포.
- [x] TASK-0077 (REQ-20260519-0005, Minor §12.3 — search modal 5 항목 hotfix bundle of TASK-0072/0076) 사용자 직접 테스트 보고 5 항목 모두 반영: (1) **min char 3 → 2** — backend `_normalize_search_query` 의 raw-len gate 3 → 2 (한국어 grapheme 2 char 도 의미 있는 검색어). frontend `runSearchQuery` / `_searchHighlight` / `renderSearchModalResults` empty state / `_jumpToSearchMatchedMessage` 모두 정합 갱신. (2) **소유자 facet 제거** — DOM (`#searchFacetOwner`, `#searchOwnerPopover`, `#searchOwnerList`) + JS (`_loadOwnerAccountsForSearch` / `_openOwnerPopover` / `state.searchModal.owner_id` / `owner_username` / `ownerAccountsCache`) 전부 제거. backend `_list_conversations` 의 `owner_id` 파라미터 자체는 호환 위해 유지 (다른 caller 영향 0) — frontend 가 쿼리에 안 보냄. (3) **기간 preset 5 종** — popover 안 preset row 신설 (1시간/1일/1주/1개월/1년 전부터 지금까지). click 시 from/to 자동 채움 + popover input sync + 적용 + runSearchQuery. preset hours 는 `data-preset-hours` 데이터 속성 (1/24/168/720/8760). (4) **mouseup race fix** — backdrop close 가 사용자 modal 안 text drag → backdrop 위 mouseup 시 trigger 되던 문제. `overlay.mousedown` 시 `state.searchModal.mousedownOnOverlay = (ev.target === overlay)` 기록, `overlay.click` 시 `mousedownOnOverlay && ev.target === overlay` 둘 다 true 일 때만 close. (5) **snippet 본문 excerpt** — backend `_collect_matched_excerpts(conn, conv_ids, q)` helper 신설 (MySQL 8.0 `ROW_NUMBER() OVER (PARTITION BY ConversationId ORDER BY Id DESC)` 으로 conv 별 최근 매칭 message 1건, content 의 매칭 위치 ±40 char clip + "…" prefix/suffix). endpoint 가 `matched_excerpts: {conv_id: "...본문..."}` 응답에 첨부. frontend `runSearchQuery` 가 state 에 캐시, `renderSearchModalResults` 의 snippet 영역이 topic 대신 excerpt + `_searchHighlight` highlight. cache-bust `v=20260519-search-facets` → `v=20260519-search-presets`. backend matched_excerpts 는 본 cycle 의 신규 PII 표면 *아님* — TASK-0072 의 snippet opt-in chip + WebAccountActivity audit 정책 그대로. py_compile + node --check PASS + make web 재배포 OK.
- [x] TASK-0076 (REQ-20260519-0004, Minor §12.3 — search modal UX 3 결함 hotfix bundle of TASK-0072) 사용자 직접 테스트 보고 3 항목: (1) facet click 무동작 (소유자/제품/기간) — 본 cycle: 제품 facet 은 사용자 명시 결정 ("대화 중 product 변경 가능 → 필터 대상 부적합") 으로 DOM 제거, 소유자 facet 은 `/api/admin/accounts` 캐시 + popover (.any 한정), 기간 facet 은 `<input type="date">` from~to popover + 적용/지우기. backend `_list_conversations` 가 `owner_id`/`date_from`/`date_to` 파라미터 이미 지원 (Phase A1) — frontend popover 만 신설. (2) ArrowUp/Down 시 화면 범위 초과 시 scroll 미동작 — active row 의 `scrollIntoView({block:'nearest'})` ArrowDown/ArrowUp 핸들러 + Enter 동일 적용. (3) 검색 결과 click 시 conv 전환은 OK 이나 매칭 message bubble 로 jump 안 함 — result click / Enter 시 `state.searchModal.pendingJumpQuery = q` + `pendingJumpConvId` 저장, `selectConversation` 끝 (loadHistory + renderMessages 직후) 에 `_jumpToSearchMatchedMessage()` 호출, `messageLogEl` 의 `.message` 중 textContent.toLowerCase().includes(needle) 첫 매칭 row 로 `scrollIntoView({behavior:'smooth', block:'center'})` + `is-search-matched` class 1.8 s pulse animation. backend / RBAC / audit / endpoint 무변경. cache-bust `v=20260519-modal-contrast` → `v=20260519-search-facets`.
- [x] TASK-0075 (REQ-20260519-0003, Minor §12.3 — TASK-0072 + TASK-0074 HTTP smoke 실행 결과 기록) `bootstrap_admin` 1 토큰만 사용한 ad-hoc curl 실행 결과 6/8 PASS (S2 .any cross-account, S4 cursor disjoint, S5 invalid q→400, S6 rate limit 11th→429, S7 DDL idempotent, S8 audit SHA-256 INSERT). S1 (.own no leak) / S3 (byte-equal owner_id) 는 operator (`review_user01`) pw 미보유로 skip — `_list_conversations` 의 has_any 분기 + endpoint 의 effective_owner_id 강제 overwrite 코드 review 로 검증됨. `docs/TEST.md §4 Test Run History` 에 append. backend / RBAC / endpoint / audit 무변경.
- [x] TASK-0074 (REQ-20260519-0002, Minor §12.3 — search modal 색상 가독성 hotfix of TASK-0072) 사용자 screenshot 보고: TASK-0072 의 Spotlight modal 이 light theme (`--bg #f4f4f5` / `--surface #ffffff` / `--text #18181b`) 환경에서 어두운 배경 + 검은 텍스트로 노출 — "사용자가 이용할 수 없을 정도의 색상 구성". 원인: modal CSS 가 미정의 var (`--text-primary`, `--bg-elev`) 의 hardcode dark fallback (`#1f2429`) 으로 배경을 잡았고, 텍스트는 site 의 `--text` (zinc-900) inherit → 어두운 배경 위 검은 텍스트 = 가독성 0. Fix: modal block ~100 줄을 site 의 기존 토큰 (`--surface`, `--text`, `--text-2`, `--text-muted`, `--border`, `--primary`, `--primary-soft`, `--bg`) 으로 일관 적용. backdrop 의 dark overlay (`rgba(15, 23, 42, 0.48)`) 는 modal pop 강조 유지. snippet 배경 = `--bg`, result row hover/active = `--primary-soft`, owner badge = bg + border + color triple, highlight bg `#fde68a` + bold (light theme contrast). RBAC / endpoint / audit / backend 무변경. cache-bust `v=20260518-conv-search` → `v=20260519-modal-contrast` (styles.css + app.js 양쪽). 검증: make web 재배포 + 컨테이너 12 초 후 healthy. node --check / py_compile 대상 변경 없음.
- [x] TASK-0073 (REQ-20260519-0001, **Critical** §12.3 — 모든 계정 행위 audit + 관리 콘솔 조회) 본 cycle Phase A1~D 완료, Phase E 외부 영향 검증은 사용자 위임 (sandbox SSH 인증 차단). CHG-20260519-0017~0025, REV-20260519-0013~0021. 8 commit (`bf21886` A1 / `88d6fa4` A2 / `2e45cb4` A3 / `e21ab15` A4 / `4ed5f0d` A5 / `5f42ba6` A6 / `c801104` B / `2ddf9b5` C / `58c32e9` D) on `ai/claude/0073/agent-audit` worktree. sub-progress:
  - [x] Phase A0 — DDL + bootstrap (`_ensure_web_audit_events_schema` + WebAuditEvents 14 columns + 5 indexes + fast/slow path hook). CHG-20260519-0003. 2026-05-19. py_compile PASS.
  - [x] Phase A1 — dispatcher + `AGENT_AUDIT_ENABLED` gate (CHG-20260519-0017, 2026-05-19, py_compile + bash -n PASS; verify-completion check_11_audit_dispatcher 신설)
  - [x] Phase A2 — WebAccountActivity 흡수 + migration helper (CHG-20260519-0018, 2026-05-19, py_compile PASS; idempotent SQL marker `RequestId='account-activity:<id>'` + dual write `_log_search_activity`)
  - [x] Phase A3 — RBAC catalog +4 + dba seed + permission group `audit` (CHG-20260519-0019, 2026-05-19, py_compile PASS; SEED + 4 catchup loop admin/operator/sales/dba/pending 자동 backfill)
  - [x] Phase A4 — 5 audit endpoint + chunked purge (CHG-20260519-0020, 2026-05-19, py_compile PASS; .own SQL filter Actor OR Target + 50k CSV hard cap + 1000-row chunked purge w/ idempotency_key 30s deadline)
  - [x] Phase A5 — admin 11 endpoint hook (Same tx) + ActionCode 별 build_audit_change_json builder (CHG-20260519-0021, 2026-05-19, py_compile PASS; 11 endpoint = update/delete/password-reset/role CRUD/product CRUD/databases.update/system_prompt.update — plan 의 "13" elastic 표현, 11 이 admin mutation 전부; E5 product delete cascade lock 순서 정합)
  - [x] Phase A6 — user 5 endpoint hook (fail-open) + anonymous share view (CHG-20260519-0022, 2026-05-19, py_compile PASS; _audit_user_action helper + ActorType='anonymous' for public share view + token_prefix 8 char redact)
  - [x] Phase B — 3 test 파일 신설 (CHG-20260519-0023, 2026-05-19, py_compile PASS; test_audit_dispatcher 7 시나리오 + test_audit_rbac 10 시나리오 + test_audit_migration 3 시나리오; 실 실행은 컨테이너 환경 + admin/operator 자격 필요, Phase E 위임)
  - [x] Phase C — Frontend (admin 탭 + filter + detail pane + CSV) (CHG-20260519-0024, 2026-05-19, node --check PASS; admin.html 새 탭 + filter row 7항목 + list-detail / admin.js loadAuditList + render + escape HTML / styles.css 10+ class / app.js + admin.js PERMISSION_GROUP_ORDER 'audit' + cache-bust v=20260519-audit-tab 4 곳)
  - [x] Phase D — 프로젝트 수준 docs (SECURITY §9 + DECISIONS ADR-0019 + ARCHITECTURE §4·§6 + CONVENTIONS §10.6 + STATUS feature-0003 row + REPORT §1 + TEST §2.1) (CHG-20260519-0025, 2026-05-19; SECURITY §8 은 TASK-0072 점유 → §9 신설로 정합 + plan 본문 의도 보존)
  - [x] Phase E — verify-completion + Completion Checklist + 최종 commit (CHG-20260519-0026, 2026-05-19; 본 cycle TASK-0073 [x] 마킹). 외부 영향 (make web 재배포 + browser headless smoke + AGENT_AUDIT_ENABLED=0/prod startup fail 검증 + WebAccountActivity migration SQL count 검증) 은 sandbox SSH 인증 차단으로 사용자 위임 — 8 commit 모두 `ai/claude/0073/agent-audit` worktree 의 local 누적.

  사용자 in-cycle 결정 (CEO review 9 항목 + Codex outside voice 14 findings 흡수 후 Major redesign): Mode=HOLD SCOPE, Scope=Approach B (admin + 대화·SQL·share·search), Storage=DB-only (`WebAuditEvents` 365일 retention + chunked PK purge), Hook=Web-ui split (admin 13 endpoint = direct dispatcher + Same tx / user 4 endpoint = best-effort delegate + fail-open, TASK-0072 패턴 답습), MySQL log=별 cycle 분리 (slow_query_log 본 cycle 제외), RBAC=`audit.read.own` + `audit.read.any` + `audit.export` + `audit.purge` 4건 (.own 은 dba 포함 모든 role 자동 grant, .any 는 admin/dba) + permission group `audit` 신규 + CONVENTIONS.md §10.6 동시 갱신, Tx=split (admin Same tx fail-safe / user fail-open), Masking=Action-specific allowlist builder (raw request 검증 X, ActionCode 별 명시 화이트리스트, free-text PII explicit redact/hash), Flag=`AGENT_AUDIT_ENABLED` prod (`AGENT_MODE!=dev/test`) startup fail-closed + dev/test toggle, WebAccountActivity 흡수 (TASK-0072 PIPA §29 1년 retention inherit, ActionCode `conversation.search.any` / `conversation.snippet.any` mapping, `_log_search_activity` 는 새 dispatcher 의 user best-effort path 로 wrap). 상세 plan 은 §2.1 Implementation Plan (TASK-0073). **상태**: `approved-after-outside-voice` — CEO review 9 decision 확정 → Codex outside voice 14 findings + 6 minimum-fix dispatch → 9 decision 중 5 reset (Storage·MySQL log·Hook·Tx·Masking) → redesign 사용자 확정 (2026-05-19). **사용자 메모리**: `feedback_outside_voice_for_rbac` 정책 강제 적용 (Critical RBAC + audit 표면 신설).
- [x] TASK-0072 (REQ-20260518-0010, **Critical** §12.3 — 타 계정 대화 검색·필터) **DEPLOYED**. 사용자 in-cycle 결정 3 항목 ((1) 권한 = 기존 `conversation.list.any` 재활용, (2) 검색 범위 = 제목 + 계정명 + 메시지 본문, (3) UI = Spotlight modal Cmd/Ctrl+K) 합의 후 outside voice 3 review (security FIX-FIRST / adversarial Blocker + 3 sub-spec + 6 risk / ux NEEDS-TWEAK) 모두 흡수. 3 sub-spec (SQL composition order strict / hidden_ids SQL push / Python re-sort 삭제 + SQL ORDER BY 단일화) + 안전망 (LIKE ESCAPE '!' + min 3 char + LIMIT 50 + rate 10/min + max_execution_time 3s + DeletedAt + collation audit + owner.Username .any 한정) + audit (SHA-256 hash, 평문 X, PIPA §29) + cursor pagination 적용. 상세 plan-review 는 §2.1 Implementation Plan (TASK-0072) PLAN-APPROVED 마커. **Main 통합 commits**: `f298f90` (feat TASK-0072 본체) + Post-deploy hotfix bundle `e7fd926` (TASK-0074 light theme) / `c803134` (TASK-0076 search modal UX 3) / `cfbb8c5` (TASK-0077 5 hotfix) / `1e2e52d` (TASK-0078 3 hotfix) / `e7b9805` (TASK-0079+0080 flex + UNION). 본 closure 는 TASK-0099 (audit followup backlog tracker hygiene) cycle 에서 수행 (2026-05-22).
- [x] TASK-0071 (REQ-20260518-0009, Minor §12.3 — shell grid row hotfix, cascade root of TASK-0068~0070) 사용자 3 차 screenshot 보고: dashboard pane 처럼 list-detail 사용 안 하는 화면에서 큰 viewport + 짧은 content 조합 시 sidebar / commit-bar 가 viewport 의 약 70% 위치까지만 차지 + 그 아래 회색 빈 영역. 원인: `.app-shell` / `.admin-shell` 의 `display: grid; height: 100vh` 만 정의 + `grid-template-rows` 미정의 → default `auto` → row track height = 자식 max-content. grid container 100vh 와 track height 의 mismatch 시 track 아래 빈 영역. 이전 cycle 의 fix 들은 column 안의 stretch chain 만 해결, column 의 height 결정 layer (grid track) 미처리 = cascade 의 root. Fix: `.app-shell` 과 `.admin-shell` 양쪽에 `grid-template-rows: minmax(0, 1fr)` 추가 (2 줄, 동일 패턴 일관성). 검증: 1320x900 viewport 에서 admin-shell h=900, column h=900, commit-bar bottom=900 (viewport bottom 정확히 sticky). screenshot 첨부. cache-bust `v=20260518-shell-grid-rows` (admin.html / index.html 양쪽 동일).
- [x] TASK-0070 (REQ-20260518-0008, Minor §12.3 — admin list-detail grid row hotfix of TASK-0069) 사용자 2 차 screenshot 보고: `역할` / `제품` 등 항목이 적은 pane 에서 큰 viewport (height 800+) 의 경우 list-col / detail-col box 가 viewport 의 일부만 차지하고 그 아래 회색 빈 영역. 항목이 많은 `계정` (26 row) 또는 좁은 화면에서는 content 가 row 채워 정상. 원인: `.admin-list-detail` 의 grid-template-rows 미정의 → default auto → row height = content. align-items: stretch 는 row 내부 column 분배만 담당 — row 자체 height 결정 X. Fix: `grid-template-rows: minmax(0, 1fr)` 추가 (1 줄). 검증: 큰 viewport (1320x900) 에서 listDetail h=682, listCol/detailCol h=682 (이전 ~200), cbar viewport bottom sticky. screenshot 첨부. cache-bust `v=20260518-admin-list-rows`.
- [x] TASK-0069 (REQ-20260518-0007, Minor §12.3 — admin workspace flex hotfix of TASK-0068) 사용자 screenshot 보고: admin `역할 관리` (및 다른 list-detail pane) 에서 commit-bar 가 workspace content 바로 아래에 좁게 위치하고 그 아래로 큰 회색 빈 영역. 원인: TASK-0068 에서 commit-bar 를 admin-shell grid → admin-column flex column item 으로 이전한 후 `.admin-workspace` 의 `flex: 1` 명시 누락 → flex column 안에서 workspace 가 자기 content 만큼만 차지. Fix: `.admin-workspace` 에 `flex: 1 1 auto` 추가 (1 줄). 다른 속성 무변경. 검증: DOM `wsBottom=659 / cbarTop=659 / commitBarAtBottom=true / workspaceTouchesCommitBar=true` → list-detail 이 column 의 남은 height 전부 차지 + commit-bar viewport bottom sticky. screenshot 첨부. cache-bust `v=20260518-admin-workspace-flex`.
- [x] TASK-0068 (REQ-20260518-0006, Minor §12.3 — 관리 콘솔 layout 정합 + 미사용 버튼 정리) TASK-0066 / 0067 follow-up. 사용자 명시 — 관리 콘솔의 사이드바 구성을 작업 화면과 동일하게 (ChatGPT 패턴, sidebar 전체 height + admin-column) 정렬. 사용자 직접 테스트에서 거의 사용 안 되는 `새로고침` / `로그아웃` 버튼 제거. `.admin-shell` grid 가 2-row → 2-column (sidebar 220 | admin-column 1fr). `.admin-body` wrapper 폐기. `.sidebar-brand` (작업 화면과 동일 brand "MySQL AI") 가 `.admin-sidebar` 의 첫 영역. `.admin-column` (flex column) 안에 topbar (관리 콘솔 제목 좌측 정렬 + 부제 + "작업 화면" 버튼 우측) + workspace + commit-bar. `#refreshAdminBtn` / `#adminLogoutBtn` element + JS click handler 모두 제거 — 로그아웃은 작업 화면 프로필 drawer 에서 가능 (기능 손실 없음). 검증: DOM `refreshBtnPresent=false / logoutBtnPresent=false / backBtnPresent=true / brandInSidebar=true / adminColumnPresent=true / gridCols="220px 1060px"`. backend / RBAC / endpoint / 데이터 무변경. cache-bust `v=20260518-admin-layout`.
- [x] TASK-0067 (REQ-20260518-0005, Minor §12.3 — 제품 칩 composer 이전 + native select → custom drop-up dropdown) TASK-0066 follow-up. 사용자 명시 — ChatGPT 의 모델 선택 UI 패턴으로 제품 칩을 사이드바 → composer 의 textarea 우측 (sendBtn 직전) 으로 이전. 클릭 시 drop-up dropdown 으로 옵션 표시. 사이드바도 채팅 영역처럼 확장 효과. `.sidebar-head .product-chip-wrap` 제거, `.composer-box` 안에 `.composer-product-chip-wrap` (button#productChip + #productDropupMenu) 신설. 기존 native `<select id="productSelect">` 제거 → custom button + custom menu (drop-up 보장 위해). renderProductChip 재작성 + renderProductDropupMenu / buildProductDropupItem / openProductDropup / closeProductDropup 신설. backend endpoint `PATCH /api/conversations/{cid}/product` 호출 / setActiveProduct 본체 / RBAC / 데이터 영역 무변경. 검증: DOM `chipInComposer=true`, 기존 native select 부재, sidebar-head 가 "새 대화" 만, chip click → menu 4 items (auto + KR + MV + GZ_KR) 표시 + `dropUp=true` (menuY < chipY), KR item click → chip label "KR" + toast "제품을 킹스레이드로 바꿨어요" 정상. cache-bust `v=20260518-product-composer`.
- [x] TASK-0066 (REQ-20260518-0004, Minor §12.3 — ChatGPT 패턴 layout 재구조화) TASK-0065 follow-up. 헤더 4 버튼 제거로 비어 보이던 `.chat-header` 와 `.topbar` (관리 콘솔) 영역을 통합. 사용자 결정 (in-cycle 명시): topbar 에 대화 제목 통합 + 좌측 정렬 (중앙 정렬 금지) + brand `[MA] MySQL AI` 를 sidebar 영역으로 이전 (ChatGPT UI 패턴). `.app-shell` grid 를 row 2개 → column 2개 (sidebar | chat-column) 로 단순화. `.app-body` wrapper 폐기. `.sidebar-brand` 신설 (sidebar 첫 영역, height = topbar-h 로 baseline 정렬). `.chat-column` 신설 (topbar + chat-pane wrapper). `.chat-header` 폐기 — 채팅 영역 확장. `.topbar-info` (제목/부제 좌측 정렬) + `.topbar-tools` (loadMoreBtn) + `.topbar-end` (관리 콘솔 우측). 반응형 mobile (max-width: 680px) 분기도 정렬. JS 변경 0 — 모든 element ID 보존. backend / RBAC / endpoint / 데이터 영역 무변경. 검증: DOM `.app-shell.gridTemplateColumns = "252px 1028px"`, `.sidebar-brand` mount, `.topbar.height = 52px`, 기존 `.chat-header` DOM 부재. browser screenshot 으로 ChatGPT 패턴 정확 구현 확인.
- [x] TASK-0065 (REQ-20260518-0003, Minor §12.3 — UI 정리 follow-up of TASK-0063) 사용자 직접 테스트 피드백 3 항목: (1) 헤더의 "대화 복사 / 공유 / 제목 변경 / 삭제" 4 버튼이 좌측 conv-item "···" menu 와 중복 → 헤더에서 제거 (cancel/finalize 만 유지). (2) "···" trigger 우측 상단 위치가 conv-item 의 "내/sales" badge 와 시각 충돌 → 우측 하단 (`bottom: 6px; right: 6px`) 으로 이전, `.conv-item` 에 `padding-right: 32px` 보정. (3) 캘린더 시간 이동 trigger 가 분기선 click 인데 사용자가 분기선까지 미리 scroll 해야 하는 불편 → Slack 패턴으로 분기선에 `position: sticky; top: 0` 적용 — 현재 시야의 날짜 그룹 헤더가 항상 messageLog 상단에 stick. hover affordance 는 기존 색상 변경 유지 + box-shadow 로 elevation 강화. backend / RBAC / endpoint 변경 0. 검증: node --check + make web 재배포 + browser headless smoke (헤더 4 버튼 부재 / trigger DOM position 확인 / `scrollTop = 600` 시 sticky 분기선 viewport 상단 stay screenshot).
- [x] TASK-0063 (REQ-20260518-0001, **Major** §12.3 — RBAC catalog 확장 2 + 신규 endpoint 1 + 파괴적 액션 menu 통합) 작업 화면 대화 항목별 "···" menu (복사 / 공유 / 제목 변경 / 삭제) + 캘린더 시간 이동을 채팅 로그 날짜 분기선 click trigger 로 이전. ChatGPT / Slack UX 패턴. 사용자 in-cycle 결정 4 항목: (1) 복사 = full self-fork (`_fork_conversation_impl` 재활용), (2) 신규 권한 `conversation.duplicate.own/.any` 분리 추가, (3) 헤더 share 유지 (dual entry), (4) 헤더 calendar 제거 + 분기선 단일 trigger + popover header ‹ › « » nav (« » 는 데이터 1년 이상일 때만). Codex outside voice review 10 risk 보강 (catchup loop 일반화, share-token bypass 차단 = read-gate 명시, 404 metadata leak 차단, .any superset semantics, frontend hide-vs-disable = rename/delete pattern 채택, PERMISSION_LABELS/DESCRIPTIONS/requiredPermissionsFor 3 곳 갱신, grapheme-safe 사본 제목). Catchup 순서 fix — `_ensure_seed_catchup` 의 `_ensure_permission_catalog` 호출을 `_ensure_seed_roles` 앞으로 이동 (기존 순서는 _permission_id_map 이 신규 권한 id=0 받아 admin/operator/sales catchup skip). 검증: py_compile + node --check + make web 재배포 + DB 직접 grant 확인 (admin .any+.own / operator .own / sales .own) + browser headless smoke (menu 4 항목 + 분기선 click → popover anchored + 월 nav 동작).
- [x] TASK-0062 (REQ-20260515-0011 / REQ-20260515-0012, Minor §12.3) GOAL 2026-05-15 후속: (1) 내 대화 다중선택 UX 개선 — `.conv-item-checkbox` DOM 제거, Ctrl/Shift modifier 만 다중 선택 허용, 2 개 이상 선택 시에만 bulk bar 표시, 일반 click 은 단일 선택 + `state.conversationSelected.clear()`. (2) Point rail dot 위치를 `messageLog.scrollHeight` 기준 비례 분포로 재배치 — `.message-point-rail` 이 `position: relative`, dot 이 `position: absolute; top: <pct>%; transform: translate(-50%, -50%)`. `layoutMessagePointRail()` 헬퍼가 `renderMessagePointRail` + resize 에서 재계산. 검증: node --check 통과, make web 재배포, browser smoke (single click → 다중 선택 해제 / Ctrl click 2개 → bulk bar 표시 / point rail dot 의 top% 가 message scrollHeight 비례). cache-bust `v=20260515-task-0062`.
- [x] TASK-0061 (REQ-20260515-0003 ~ REQ-20260515-0010, **Major** §12.3 — UI 상태 / auth(비밀번호 초기화) / 파괴적 데이터(bulk delete) 일괄 변경) GOAL.md 8 항목 합본 cycle. **/qa round 2 심층 검증 완료 (2026-05-15, CHG-20260515-0004)** — Phase 4 Point rail dot click smooth scroll + active dot id 갱신, Phase 5 캘린더 월 이동 + day click → 시각 list 모두 정상. Phase 3/6/8 destructive endpoints 는 운영 환경 사용자 명시 시점에 실 호출 검증 권고. round 2 신규 이슈 0 건. 답변 버블 내부 실시간 step 진행 (Phase 1) + 신규 대화 첫 요청 polling 즉시 연결 (Phase 2) + processing 만료 감지 + 붉은 badge (Phase 3) + 우측 Point rail (Phase 4) + 캘린더/시각 이동 (Phase 5) + 관리자 비밀번호 초기화 (Phase 6) + admin select-all 현재 페이지 fix (Phase 7) + 내 대화 Ctrl/Shift bulk delete (Phase 8). 상세 plan-review 는 §2.1 Implementation Plan (TASK-0061). **사용자 승인 요청 시점**: §2.1 Plan 확정 후 Phase 6 (Critical 분면 — 비밀번호 초기화, 인증 모델 영향) 진입 전. Phase 1~5, 7, 8 (Major) 는 plan-review 통과 후 Execute.
- [x] TASK-0060 (REQ-20260515-0002, Minor §12.3) Product별 접근 가능 DB의 실제 스키마/데이터를 분석해 Product scope 시스템 프롬프트를 작성하고, Role detail 의 `전 Product 공통` 프롬프트를 역할명에 맞게 채움. 분석 대상: `KR(킹스레이드)` 접근 DB `dbgame,dblog,dbauth`, `MV(마이크로볼츠)` 접근 DB `account_db,dev_1_1_1_20,have_00,log_v2,global_db`. `log_v2`는 DB는 존재하지만 테이블 0개로 확인. 실제 DB에는 product prompt 2건 + role 공통 prompt 5건(`pending/operator/admin/sales/dba`) upsert 완료. runtime 의 누적 적용은 feature-0002 `compose_system_prompt()` 수정으로 보장.
- [x] TASK-0059 (REQ-20260515-0001, **Major** §12.3 — 사용자 대화 routing 데이터 영역, 인증/인가 모델 무변경) "새 대화" 버튼 누른 후 첫 메시지를 보내도 backend 가 직전 active 대화에 메시지를 추가하는 lazy-create routing 결함 수정. 사용자가 신규 대화 의도로 보낸 첫 메시지가 잘못된 대화 컨텍스트로 귀속되어 발견. **근본 원인**: frontend `beginPendingConversation()` 이 `state.activeConversationId=""` 로 두고 backend row 를 lazy 생성 위임하나 (TASK-0048 정책), `/api/ask` 의 빈 `conversation_id` 경로가 `_resolve_conversation_for_account` → `_repair_current_conversation` 으로 폴백해 `account.last_conversation_id` (직전 대화) 를 반환. frontend 의 "pending = 신규 의도" 가 backend 로 전달되지 않아 "session 초기화 후 직전 대화 이어받기" 와 구분 불가. **Fix Phase A**: frontend `sendPrompt()` 가 `isLazyCreate=true` 일 때 `askBody.lazy_create = true` 를 추가. **Phase B**: backend `_resolve_conversation_for_account(..., force_new=False)` kwarg 추가, `_repair_current_conversation` 의 기존 `force_new` 파라미터로 위임. `/api/ask` 의 빈 `request_conversation_id` 경로에서 `data.get("lazy_create")` 가 truthy 이면 `force_new=True` 호출. **Phase C**: frontend `loadConversations()` 의 `state.activeConversationId` 덮어쓰기에 `!state.pendingNewConversation` 가드 추가 — pending 모드 race 시 직전 대화로 복귀 차단. **Phase D**: MODIFY.md CHG-20260515-0001 + REVIEW.md REV-20260515-0001 기록.

### 2.1 Implementation Plan (TASK-0169)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 **Critical** 등급 (agent 실행 경계·동시성·크래시 시맨틱 변경) 변경 계획이다. **상태**: `approved-after-outside-voice`. DESIGN-ask-worker.md (ADR-WEB-0004 의 B) 를 정본으로, out-of-process `ask-worker` 실행모델을 구현해 web 재배포/SIGTERM 이 in-flight run 을 죽이는 구조적 한계(TASK-0159/0160/0164 의 양끝 backstop 으로만 완화됐던)를 제거한다. feature-0003(web) + feature-0002(agent-core) 양면. 전 경로 `AGENT_ASK_EXECUTION_MODE` flag 기본 `inprocess` 로 격리 — 기본 동작 무변경.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-06-09 (TASK-0169 ask-worker out-of-process 실행모델, Critical 등급, outside-voice 적대적 리뷰 8건(BLOCKER 3 + MAJOR 4 + MINOR n) 흡수, flag 기본 inprocess shadow→cutover) -->

#### outside-voice 적대적 리뷰가 흡수한 8건 (DESIGN §4 → 하드닝)

DESIGN-ask-worker.md 는 위험을 §4 에 나열했으나 hard 한 것을 해결하지 않음 → 적대적 리뷰(general-purpose subagent, RBAC/런타임 경계 — feedback_outside_voice_for_rbac 정책)가 "as written 구현 불가" 판정. 흡수 결정:

| # | 발견 (severity) | 하드닝 결정 |
|---|---|---|
| B1 | TASK-0159/0164 backstop 이 ownership-blind → 매 web 재배포마다 live worker run 을 error 오염. DESIGN §2.7 의 "no-op 격하" 는 실제로 active corruptor (BLOCKER) | 두 hook 을 **ownership-aware**: worker mode 일 때 `ask_jobs` 가 claimed/running 인 conversation skip |
| B2 | `_pg_connect` autocommit=True 에서 `SELECT FOR UPDATE SKIP LOCKED`+별도 `UPDATE` → 락 미유지, double-claim (BLOCKER) | **단일문 atomic claim**: `UPDATE … WHERE id=(SELECT … FOR UPDATE SKIP LOCKED ORDER BY created_at LIMIT 1) RETURNING` |
| B3 | heartbeat-stale requeue 가 살아있는 느린 worker 와 경합 → 같은 run_id 동시 double-run, steps/core_messages 오염(TASK-0160 류 Bedrock 400) (BLOCKER) | **lease_epoch fencing**(재claim 시 ++; worker 가 주기적 재확인해 빼앗겼으면 중단) + stale 임계 ≥ run_timeout+margin + 긴 LLM step **내부** heartbeat |
| M4 | `set_run_status` 가 3~5 독립 autocommit tx → torn state, 2-writer 시 Frankenstein (MAJOR) | run_id→status 기록 순서 보장 + `ask_jobs.status` ops 권위 / KV terminal mirror + lease fencing 으로 2-writer 차단 |
| M5 | slot COUNT TOCTOU + stuck-running 영구 계정 DoS (MAJOR) | **단일문 enforce** (`INSERT…SELECT…WHERE count<limit RETURNING`, rowcount=0→429) + **stale-aware count**(heartbeat-stale running 제외) |
| M6 | temp 파일 GC 주인 없음 + requeue 시 read-after-delete + `/tmp`→`/shared` + replica 파일명 충돌(TASK-0154 류) (MAJOR) | `/shared` + **uuid 파일명** + **terminal 시에만** cleanup + 고아 reaper(worker tick) + inline reader `/tmp` 가정 감사 |
| M7 | 60s long-poll cap 이 180~1200s run 못 덮음 + error shape drift + no-worker 무한 hang (MAJOR) | 내부 attach 를 run_timeout 까지 loop(영속 conn) + **`result_json` 영속화로 응답 shape 패리티** + **worker readiness gate**(heartbeat 신선 검사, 부재 시 503/fallback) |
| 기타 | pending job cancel 유실, heartbeat conn churn, attempts-cap→무한 requeue, worker SIGTERM/stop_grace 부재 (MINOR) | cancel 을 `ask_jobs.status='canceled'` 도 set / worker 영속 conn / cap 도달 시 terminal error / worker SIGTERM handler(claimed job clean requeue) + compose `stop_grace_period: 70s` |

#### 검증된 payload 계약 (grounding 정정)

호출 함수는 `agent_core.run_agent` (app.py:7586 `from agent_core import run_agent as _run_agent_core` — inner `_run_agent_core` 아님). enqueue payload(jsonb) = run_agent kwargs 12개: `user_message, conversation_id, model, product_id, role_id, account_id, allowed_schemas, product_mode, attachment_ids, new_attachment_ids, image_inline_path, text_inline_path`. (`conv_file`=account_id 에서 재계산, `temperature`=내부 재계산, `api_key`=무시, `output_mode`="json" 고정.)

#### 컴포넌트

1. **`agent_runtime.ask_jobs` 테이블** — alembic `0003_ask_jobs`(권위) + `_ensure_ask_jobs()` IF NOT EXISTS fast-path(동일 DDL). 컬럼: `id, conversation_id, run_id, account_id, status(pending/claimed/running/done/error/canceled), claimed_by, claimed_at, started_at, finished_at, attempts, lease_epoch, heartbeat_at, created_at, payload jsonb, result_json jsonb`. 인덱스 `(status,created_at)`,`(account_id,status)`,`(heartbeat_at)`. mode=worker 인데 table 부재면 fail-loud.
2. **`ask-worker` 서비스** (insight-worker 템플릿) — `<<: *agent-common`, `entrypoint: --ask-worker`, `restart: unless-stopped`, `stop_grace_period: 70s`, heartbeat KV `ask_worker_last_cycle_at` + `scripts/healthcheck_ask_worker.py`(`ASK_WORKER_HEARTBEAT_MAX_AGE_SEC`). agent_core.py main() `--ask-worker` → `modules/ask.py::run_ask_worker_loop()`. SIGTERM handler: claimed job clean requeue(lease++).
3. **claim/실행 루프** — 단일문 atomic claim(B2) → `run_agent(**payload)` → terminal 시 `result_json`+`set_run_status` → temp cleanup(terminal only). 매 step+긴 LLM call 내부 heartbeat(영속 conn). lease 주기 재확인.
4. **stale sweeper** — `status='running' AND heartbeat_at < now-임계(≥run_timeout+margin)` → requeue(lease++,attempts++) 또는 cap 도달 시 terminal error+set_run_status('error').
5. **`/api/ask` worker mode** — 검증/conversation·product·role 해석 무변경 → readiness gate → 단일문 slot enforce → enqueue → 내부 ask_result attach loop(run_timeout 까지) → `result_json` 으로 기존 응답 shape 반환. inprocess mode 는 현행 to_thread(+0164 finalizer) 보존.
6. **backstop ownership-aware(B1)** — TASK-0159 boot reconcile + 0164 SIGTERM finalizer 가 worker mode 에서 `ask_jobs` claimed/running conversation skip.
7. **cancel/finalize** — KV 플래그 폴링 무변경 + cancel 은 pending/claimed `ask_jobs.status='canceled'` 도 set.

#### 롤아웃
`AGENT_ASK_EXECUTION_MODE=inprocess(기본)|worker`. shadow(worker 가동) → 점진 cutover → env 한 번에 rollback. inprocess 경로 + 0164 finalizer 는 worker 프로덕션 검증까지 보존.

#### 검증
- 단위: atomic claim race(동시 N worker 중 1), lease fencing(빼앗긴 worker write no-op), stale sweeper requeue/error/cap, slot 단일문 429 TOCTOU, payload round-trip, readiness gate, cancel-pending.
- 통합: enqueue→worker→KV/steps→attach shape 패리티; **web 재배포 중 worker run 생존**(핵심 B1); worker 크래시→requeue 1회만; cancel/finalize.
- 게이트: `make test`(컨테이너 pytest 회귀 0) + py_compile + **outside-voice /codex diff 리뷰**(merge 전).
- 라이브: PB-0008 Windows-browser(ask 전체 흐름) + 부하(백프레셔) + worker=on 재배포 실측(0164 finalizer 거의 미발동 확인).

#### 영향 파일
- feature-0002: `agent_core.py`(--ask-worker dispatch + run_agent heartbeat/lease), `modules/ask.py`(신규 worker loop/claim/sweeper/reaper/cancel-pending), `modules/memory.py`(set_run_status 순서 M4, ask_jobs 헬퍼), `alembic/versions/0003_ask_jobs*.py`(신규), `scripts/healthcheck_ask_worker.py`(신규), docs(FUNCTION/TASK/MODIFY/REVIEW/MIGRATIONS).
- feature-0003: `src/app.py`(/api/ask worker 경로 + readiness gate + slot 단일문 + 내부 attach + _ensure_ask_jobs + backstop ownership-aware + temp /shared/uuid/terminal cleanup), docs(FUNCTION/TASK/MODIFY/REVIEW).
- repo: `docker-compose.yml`(ask-worker 서비스), `.env*`(AGENT_ASK_EXECUTION_MODE 등 신규 env 문서화).

---

### 2.1 Implementation Plan (TASK-0073)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Critical 등급 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-19 에 CEO review 9 trade-off 결정 → Codex outside voice 14 findings + 6 minimum-fix → 9 decision 중 5 reset (Major redesign) → redesign 최종 확정. CEO review · outside voice · redesign 의 결정을 모두 plan 에 흡수.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0073 Phase A0~F 일괄, Critical 등급 audit 표면 신설 + WebAccountActivity 흡수 + RBAC 4건 .own/.any + Tx split + Allowlist builder + AGENT_AUDIT_ENABLED prod fail-closed) -->

#### 사용자 in-cycle 결정 (CEO review 9 항목, redesign 후)

| 결정 | 채택안 | 근거 |
|---|---|---|
| Mode | HOLD SCOPE | 단일 cycle bulletproof. 추가 expansion 다음 cycle |
| Scope (Approach) | B (Balanced) + WebAccountActivity 흡수 | admin + 대화·SQL·share·search 행위 추적. PIPA §29 1년 retention inherit |
| Storage | DB-only — `WebAuditEvents` (365일 retention + chunked PK purge) | mysql 단일 layer · 트랜잭션 정합 · admin UI filter 즉시 활용 |
| Hook 위치 | Web-ui split — admin endpoint = direct dispatcher (Same tx), user endpoint = best-effort delegate (fail-open) | TASK-0072 fail-open 패턴 답습 + `/api/ask` long-running deadlock 회피 |
| MySQL log | 별 cycle 분리 (slow_query_log 본 cycle 제외) | `slow_query_log` = mysql server log (file) — DB-only 와 모순 / retention·RBAC 미적용 (Codex C1) |
| RBAC | `audit.read.own` (모든 role dba 포함 auto-grant) + `audit.read.any` (admin/dba .any superset) + `audit.export` + `audit.purge` 4건 + permission group `audit` 신규 + CONVENTIONS.md §10.6 동시 갱신 | 기존 `.own/.any` 패턴 정합 (Codex C8) · dba seed 누락 차단 (Codex C9) · misc fallback 차단 (Codex C10) |
| Tx 정책 | Tx split — admin Same tx (정합성 우선 fail-safe) / user fail-open best-effort | `/api/ask` 별 thread/connection + LLM long-running lock contention 회피 (Codex C3, C4) |
| Masking | Action-specific allowlist builder | dispatcher 가 raw request 검증 X. ActionCode 별 명시 `build_change_json(action, actor_ctx, request_ctx, response_ctx)` 화이트리스트 only insert. free-text PII (sql/description/system_prompt/message/result) explicit redact/hash. DoS 차단 (Codex C6) |
| Feature flag | `AGENT_AUDIT_ENABLED` prod (`AGENT_MODE!=dev/test`) startup fail-closed + dev/test toggle | flag bypass surface 차단 (Codex C5) · prod 에서 audit off = 시작 차단 |

#### outside voice 종합 결정 (Codex)

Codex outside voice (read-only sandbox, model_reasoning_effort=high, 5분 timeout) 가 14 findings + 6 minimum-fix requirements + 5 deadlock scenarios 도출. 본 plan 의 9 CEO decision 중 5 개 (Storage·MySQL log·Hook·Tx·Masking 의 5 domain) 가 직접 reset 됨.

| # | finding | 처리 |
|---|---|---|
| C1 | DB-only + slow_query_log 통합 모순 | slow_query_log 별 cycle 분리 |
| C2 | `WebAccountActivity` (TASK-0072) 이미 존재 | 흡수: ActionCode mapping + 기존 row migration + `_log_search_activity` wrap |
| C3 | Same tx + autocommit=True + agent_core 별 connection | Tx split — admin = Same tx / user = fail-open |
| C4 | `/api/ask` Same tx deadlock (LLM 실행 동안 lock hold) | user endpoint Same tx 제외 |
| C5 | `AGENT_AUDIT_ENABLED=0` bypass surface | prod startup fail-closed + dev/test only toggle |
| C6 | Hybrid masking unknown raise = DoS + free-text PII 미차단 | Action-specific allowlist builder (raw 검증 X) |
| C7 | `.self` 정의 미결 (Actor vs Target vs Resource owner) | eng review lock-in (SECURITY.md §8) |
| C8 | RBAC `.self/.read` vs 기존 `.own/.any` 불일치 | `.own/.any` 로 재정렬 |
| C9 | dba role seed/catchup 누락 | dba 명시 auto-grant + `_ensure_seed_catchup` hydrate 보강 |
| C10 | permission group `audit` 추가 시 misc fallback | CONVENTIONS.md §10.6 동시 갱신 |
| C11 | TASK-0058 share anonymous path 누락 가능 | eng review lock-in (`/api/public/share/{token}` view + fork audit) |
| C12 | `_get_client_ip` (app.py:560) X-Forwarded-For trust 약함 | eng review lock-in (Caddy XFF strip/set 검증) |
| C13 | purge self-audit idempotency / rollback / 재시도 | eng review lock-in |
| C14 | 365일 retention + Phase 2 partitioning deferrable + range delete 충돌 | chunked PK purge 본 cycle 필수 |

#### Must-fix 5 (Codex minimum-fix, 본 cycle 강제)

1. **WebAccountActivity 흡수** — Phase A2 migration. 기존 row → `WebAuditEvents` 의 ActionCode `conversation.search.any` / `conversation.snippet.any` 변환 + RemoteAddr/UserAgent NULL (TASK-0072 schema 에는 부재). `_log_search_activity` 는 새 dispatcher 의 user best-effort path 로 wrap (signature transparent 보존). 기존 `WebAccountActivity` DROP 은 별 cycle (data 보존 backup 후).
2. **`.own/.any` RBAC + .own SQL filter** — `audit.read.own` (dba 포함 모든 role auto-grant), `audit.read.any` (admin/dba .any superset), `audit.export` (admin/dba), `audit.purge` (admin only). `.own` SQL filter: `WHERE ActorAccountId = :session_account_id` 강제. TASK-0058 share read-gate 패턴 답습 (read-gate 먼저 = 404 metadata leak 차단 + `.any` superset semantics).
3. **Action-specific allowlist builder** — dispatcher 는 raw request 검증 X. 각 ActionCode 별 `build_change_json(action: str, actor: dict, request_ctx: dict, response_ctx: dict) -> dict` 명시 화이트리스트. unknown action / field 는 builder 단계에서 raise (dispatcher 단계 X). free-text PII (sql/description/system_prompt/message/result/temporary_password/Token/SessionTokenHash/PasswordHash/API key cipher) explicit redact/hash. SECURITY.md §8 의 sensitive field catalog 가 builder source-of-truth.
4. **`AGENT_AUDIT_ENABLED` prod fail-closed** — startup 시 `AGENT_MODE` 와 `AGENT_AUDIT_ENABLED` 동시 check. prod (`AGENT_MODE` 가 `dev` / `test` 가 아닐 때) 에서 `AGENT_AUDIT_ENABLED!=1` 이면 시스템 시작 차단 + stderr `[FATAL] AUDIT REQUIRED IN PROD — set AGENT_AUDIT_ENABLED=1`. dev/test 만 toggle 허용. flag state changes 는 audit row 불가 (env 변경은 DB mutation 아님) → startup stderr log 만.
5. **Tx split — admin Same tx + user fail-open** — admin 13 endpoint (account update / role create-update-delete / permission grant / product CRUD / password-reset / account delete) = dispatcher direct call, business tx 에 audit INSERT 포함 (audit fail = rollback). user 4 endpoint (`/api/ask`, `/api/conversations/{cid}/share` POST·DELETE, `/api/public/share/{token}/fork` POST, `/api/conversations` search snippet) = best-effort delegate (TASK-0072 `_log_search_activity` 패턴), audit fail = stderr only, main flow 진행. dispatcher SPOF mitigation: verify-completion.sh check + 100% test coverage on dispatcher.

#### Additional risk 9 (Codex C7-C14, eng review lock-in)

1. `audit.read.own` 의 self 정의 (ActorAccountId vs TargetAccountId) — SECURITY.md §8 명시 (admin 의 password-reset target=user 이벤트가 user 자기 audit 에 보이는지)
2. ChangeJson HTML escape on admin UI detail pane (TASK-0058 share.html `<pre>` 패턴 답습)
3. `_get_client_ip` (app.py:560) trust 패턴 검토 + Caddy XFF strip/set 설정 확인 (feature-0006-lan-proxy-access)
4. purge self-audit + idempotency key + chunked PK cursor 재시작 가능
5. chunked purge `ORDER BY Id LIMIT N` 본 cycle 필수 (Phase 2 deferrable 아님)
6. ChangeJson schema hybrid (indexed columns `ActionCode`/`ResourceType`/`ResourceId`/`OccurredAt` + JSON column `ChangeJson`/`MaskedFields`)
7. dispatcher SPOF — verify-completion.sh check + 100% test coverage
8. decorator pattern `@audit_action("admin.account.update")` for hook site DRY (선택)
9. test infra (`feature-0003-agent-web-ui/tests/`) 보강 — masking builder + RBAC .own enforcement + WebAccountActivity migration smoke

#### 영향 파일 (최종, slow_query_log 제외 + WebAccountActivity migration 추가 = 13 파일)

Backend:
- [src/app.py](../src/app.py) —
  - Phase A0: `_ensure_web_audit_events_schema(conn)` 신설 (DDL: `Id BIGINT PK, ActorAccountId, ActorRoleId, SessionId, ActionCode VARCHAR(64), ResourceType VARCHAR(32), ResourceId VARCHAR(64), ChangeJson JSON, MaskedFields JSON, RemoteAddr VARCHAR(64), UserAgent VARCHAR(255), RequestId VARCHAR(64), OccurredAt TIMESTAMP(3); INDEX (ActorAccountId, OccurredAt) / (ActionCode, OccurredAt) / (ResourceType, ResourceId)`). `_ensure_seed_catchup` hydrate.
  - Phase A1: `record_audit_event(conn, actor, action, resource_type, resource_id, change_json, masked_fields)` dispatcher + `AGENT_AUDIT_ENABLED` startup fail-closed gate (`AGENT_MODE` check) + `_get_client_ip` 재사용.
  - Phase A2: WebAccountActivity migration helper — 기존 row → WebAuditEvents transform (ActionCode `conversation.search.any` / `conversation.snippet.any`, ActorAccountId=AccountId, ResourceType=`conversation`, ResourceId=TargetOwnerId, ChangeJson=`{query_hash, matched_count}`, OccurredAt=CreatedAt, RemoteAddr/UserAgent NULL). `_log_search_activity` 는 새 dispatcher 의 user best-effort path 로 wrap (transparent signature 보존, 호출처 변경 X).
  - Phase A3: `PERMISSION_DEFINITIONS` +4 (`audit.read.own` / `audit.read.any` / `audit.export` / `audit.purge`) + dba role 자동 grant + `_ensure_seed_catchup` 의 `_ensure_permission_catalog` 호출 순서 강제 (TASK-0063 회귀 fix 패턴 답습).
  - Phase A4: 5 endpoint 신설 (`GET /api/admin/audits` filter/cursor, `GET /api/admin/audits/{id}`, `GET /api/admin/audits/export.csv`, `GET /api/admin/audits/actors`, `GET /api/admin/audits/resources`) + `_require_permission` + `.own` SQL filter (`WHERE ActorAccountId=session_account_id`) 강제 + chunked purge `POST /api/admin/audits/purge` (`audit.purge` gate, `ORDER BY Id LIMIT N` cursor, idempotency key, self-audit row).
  - Phase A5: admin 13 mutation endpoint hook (direct dispatcher call, Same tx). ActionCode 별 `build_change_json` allowlist (`admin.account.update`, `admin.account.delete`, `admin.account.password-reset`, `admin.role.create/update/delete`, `admin.role.permission.grant/revoke`, `admin.account.permission.override`, `admin.product.create/update/delete` 등 13).
  - Phase A6: user 4 endpoint hook (best-effort delegate, fail-open). `/api/ask` (ActionCode `conversation.ask`), `/api/conversations/{cid}/share` POST/DELETE (`conversation.share.create` / `conversation.share.revoke`), `/api/public/share/{token}/fork` (`share.fork`), `/api/conversations` search snippet (TASK-0072 `_log_search_activity` wrap 통한 통합).

Frontend:
- [src/static/admin.html](../src/static/admin.html) — 신규 탭 "감사 로그" (Roles 다음 / Products 사이) + filter row (기간 datepicker / 액션 dropdown / actor search / resource search / action group chip) + list-detail pane + ChangeJson diff viewer (`<pre>` HTML escape). `.admin-shell` grid TASK-0071 패턴 (`grid-template-rows: minmax(0, 1fr)`) 답습.
- [src/static/admin.js](../src/static/admin.js) — `ADMIN_AUDIT_*` state + `renderAuditList()` + `renderAuditDetail()` (ChangeJson HTML escape via `<pre>`) + filter handlers + CSV export button (`audit.export` gate, hide-vs-disable=hide TASK-0052 패턴) + Section permission `audit` group rendering (CONVENTIONS.md §10.6 신규 group 의 admin section "관리" 우선 노출).
- [src/static/styles.css](../src/static/styles.css) — `.admin-audit-*` ~10 클래스 + `.admin-audit-diff` token + `.admin-audit-masked` placeholder style + cache-bust `v=20260519-audit-tab`. `.admin-list-detail` 의 grid row contract 답습.
- [src/static/app.js](../src/static/app.js) — `PERMISSION_GROUP_ORDER` 에 `audit` 추가 + `WORK_SCREEN_PERMISSION_SECTIONS` 의 management section 에 `audit.read.own` 만 placeholder 노출 (작업 화면에 self-audit 진입점 본 cycle scope 외, placeholder only).

문서:
- `docs/FUNCTION.md` — REQ-20260519-0001 + AC 12~15개 (audit dispatcher / RBAC 4 / .own filter / masking allowlist / `AGENT_AUDIT_ENABLED` prod gate / WebAccountActivity migration / chunked purge / slow_query_log Phase 2 분리).
- `docs/TASK.md` — 본 §2.1 + Task Queue entry + Completion Checklist.
- `docs/MODIFY.md` — Phase A0~F 별 CHG-20260519-0001 entry.
- `docs/REVIEW.md` — CEO review 9 decision 결정 근거 + Codex 14 findings 흡수 이력 + Must-fix 5 + Additional risk 9 + redesign trace.
- `docs/REPORT.md` — Phase 별 변경 요약 + git 동기화 결과 (§16.5 Step 6).
- `docs/TEST.md` — TEST 케이스 정의 (§2 rewrite): dispatcher unit + masking allowlist + RBAC `.own` enforcement + WebAccountActivity migration smoke + `AGENT_AUDIT_ENABLED` prod fail-closed + chunked purge + admin UI smoke.

프로젝트 수준:
- `repo/docs/SECURITY.md` §8 신설 — Audit subsystem 정책: Sensitive field catalog (source-of-truth) + Action-specific allowlist policy + `.own/.any` self 정의 + `audit.purge` self-audit + chunked PK 정책 + `AGENT_AUDIT_ENABLED` prod fail-closed gate. TASK-0072 PIPA §29 1년 retention inherit 명시.
- `repo/docs/DECISIONS.md` ADR-0019 신설 — Audit subsystem 도입 결정 근거: Approach B 선택 / WebAccountActivity 흡수 / Tx split / Allowlist builder / CEO review + Codex outside voice 흡수.
- `repo/docs/ARCHITECTURE.md` §4 (기능 맵 — 책임 영역) + §6 (의존성 맵) — dispatcher cross-feature dependency 표시.
- `repo/docs/CONVENTIONS.md` §10.6 — permission group `audit` 신규 + 작업 화면 / admin 콘솔 section 배치 갱신 (admin 콘솔 management section 의 audit.read.any/.export/.purge 우선 / 작업 화면 management section 의 audit.read.own placeholder).
- `repo/docs/STATUS.md` — feature-0003-agent-web-ui row 갱신 (TASK-0073 entry).

#### Phase 순서 (최종)

1. **Phase A0 — WebAuditEvents DDL** — `_ensure_web_audit_events_schema` + `_ensure_seed_catchup` hydrate. py_compile + 컨테이너 재시작으로 DDL 적용 확인.
2. **Phase A1 — dispatcher + `AGENT_AUDIT_ENABLED` gate** — `record_audit_event(...)` + startup fail-closed gate. py_compile.
3. **Phase A2 — WebAccountActivity 흡수 + migration helper** — 기존 row transform + `_log_search_activity` wrap. data 보존 (기존 table drop 은 별 cycle).
4. **Phase A3 — RBAC catalog +4 + permission group `audit` + CONVENTIONS.md §10.6** — `PERMISSION_DEFINITIONS` +4 + dba 명시 auto-grant + hydrate 순서 강제 + admin.js + app.js section rendering. py_compile + node --check.
5. **Phase A4 — 5 audit endpoint + chunked purge** — `_require_permission` + `.own` SQL filter + chunked PK cursor + self-audit row. py_compile.
6. **Phase A5 — admin 13 endpoint hook (Same tx)** — direct dispatcher + ActionCode 별 `build_change_json` allowlist. py_compile + HTTP smoke.
7. **Phase A6 — user 4 endpoint hook (fail-open)** — `/api/ask` + share + search 의 4 hook. py_compile.
8. **Phase B — HTTP smoke 8 시나리오** — `tests/test_audit_dispatcher.py` + `tests/test_audit_rbac.py`: (1) admin update → audit row + Same tx rollback, (2) `/api/ask` → user fail-open silent, (3) `.own` actor=self → 본인 row 만, (4) `.own` actor=other → 403 byte-equal, (5) `.any` actor=any → 전체, (6) `.export` CSV + masked, (7) `.purge` chunked + self-audit row, (8) `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` → startup fail.
9. **Phase C — Frontend** — admin.html 탭 + admin.js 렌더 + styles.css + cache-bust. node --check.
10. **Phase D — 프로젝트 수준 docs** — SECURITY §8 + DECISIONS ADR-0019 + ARCHITECTURE §4 + CONVENTIONS §10.6 + STATUS 일괄.
11. **Phase E — verify-completion + commit** — `make web` 재배포 + browser smoke (admin 탭 진입 / filter / detail pane / CSV export gated / 새 admin action audit 검증) + `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` + 사용자 명시 commit confirm.
12. **Phase F — /plan-eng-review 후속 lock-in** — Additional risk 9 (Codex C7-C14) lock-in. Phase F 결과 적용은 별 commit (필요 시 follow-up TASK).

#### 위험도 평가 (최종)

| 영역 | 위험도 | 보강 |
|---|---|---|
| RBAC bypass (.own ↔ .any) | Critical | TASK-0058 share read-gate 패턴 + Phase B smoke 8 시나리오 + 404/403 byte-equal |
| PII leak (ChangeJson masking) | Critical | Action-specific allowlist builder (raw 검증 X) + SECURITY.md §8 sensitive field catalog + admin UI HTML escape |
| Tx atomicity (admin Same tx) | Major | dispatcher SPOF = verify-completion.sh check + 100% test coverage + builder explicit raise on unknown action |
| `/api/ask` deadlock | Critical | user endpoint fail-open + TASK-0072 `_log_search_activity` 패턴 답습 + Same tx 제외 |
| Feature flag bypass | Major | `AGENT_AUDIT_ENABLED` prod startup fail-closed + dev/test only toggle |
| WebAccountActivity 흡수 | Major | migration data 보존 (기존 table drop 별 cycle backup 후) + dual source 일시 공존 → 단일 source 전환 |
| RBAC hydrate 순서 | Major | TASK-0063 회귀 fix 패턴 답습 (`_ensure_permission_catalog` 가 `_ensure_seed_roles` 앞) |
| 365일 chunked purge | Major | `ORDER BY Id LIMIT N` cursor 재시작 가능 + idempotency key + `audit.purge` self-audit |
| 회귀 (TASK-0072 search) | Minor | `_log_search_activity` wrap 시 호출처 signature 보존 (transparent wrap) |
| 회귀 (admin layout) | Minor | `.admin-shell` / `.admin-list-detail` grid row contract TASK-0071 패턴 답습 |

**전체 등급**: Critical (audit 표면 신설 + RBAC 4 catalog 확장 + Tx split + PII masking allowlist + dispatcher SPOF + WebAccountActivity 흡수).

#### 검증 계획

각 Phase 종료 후:
- (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
- (b) `node --check unit/feature-0003-agent-web-ui/src/static/{admin,app}.js`

전체 완료 후:
- (c) Phase B 의 HTTP smoke 8 시나리오 (`tests/test_audit_*.py`)
- (d) `make web` 재배포 + browser smoke (admin 탭 / filter / detail pane / CSV export gated / 새 admin action 발생 시 audit row 검증)
- (e) `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui`
- (f) `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` 시작 시 fail-closed 검증
- (g) WebAccountActivity 기존 row 가 WebAuditEvents 에 migration 됐는지 SQL count 확인

#### outside voice 결과 요약 (REVIEW.md 정본)

Codex outside voice (read-only sandbox, model_reasoning_effort=high, 5분 timeout):
- 14 findings + 6 minimum-fix requirements + 5 deadlock scenarios 도출
- 본 plan 의 9 CEO decision 중 5 reset (Storage·MySQL log·Hook·Tx·Masking 의 5 domain)
- TASK-0072 `WebAccountActivity` 발견 — 직전 검토 보고가 놓친 결손, 본 plan 의 WebAuditEvents 가 superset 으로 흡수
- 5 minimum-fix 모두 redesign 에 흡수
- 9 additional risk 는 eng review lock-in (Phase F)

REVIEW.md REV-20260519-0001 에 각 finding + minimum-fix + redesign 흡수 이력 + 결정 근거 기록 예정 (Phase D).

#### Eng review lock-in (E1-E9, 2026-05-19)

본 plan 의 Additional risk 9 (Codex C7-C14) + 5 deadlock scenarios + 추가 eng items 를 architecture-level 로 lock-in. `/plan-eng-review` 호출 결과. 사용자 결정 2 항목 (E1, E4) + 나머지 7 항목 prose lock-in.

**E1 — `audit.read.own` self 정의 (사용자 결정: B — Actor OR Target)**
- `WebAuditEvents` 에 `TargetAccountId BIGINT NULL` indexed column 추가. SQL filter: `WHERE ActorAccountId = :self OR TargetAccountId = :self`.
- self-audit valid use case 충족: "내 비밀번호 누가 reset / 내 권한 누가 grant / 내 대화 누가 공유" 등 admin actor + user target 이벤트가 user 본인 audit 에 노출. 보안 가시성 정합.

**E2 — ChangeJson schema hybrid 확정**
- Schema: `Id BIGINT PK AUTO_INCREMENT, ActorAccountId BIGINT NULL, ActorRoleId BIGINT NULL, ActorType VARCHAR(16) NOT NULL DEFAULT 'account', TargetAccountId BIGINT NULL, SessionId VARCHAR(64) NULL, ActionCode VARCHAR(64) NOT NULL, ResourceType VARCHAR(32) NOT NULL, ResourceId VARCHAR(64) NULL, ChangeJson JSON NULL, MaskedFields JSON NULL, RemoteAddr VARCHAR(64) NULL, UserAgent VARCHAR(255) NULL, RequestId VARCHAR(64) NULL, OccurredAt TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP(3)`.
- 5 secondary indexes: `(ActorAccountId, OccurredAt)`, `(TargetAccountId, OccurredAt)`, `(ActionCode, OccurredAt)`, `(ResourceType, ResourceId)`, `(ActorType, OccurredAt)`.
- MySQL 8.0 generated column 본 case 불필요 (위 indexed columns 으로 모든 filter 충분).

**E3 — RemoteAddr spoof risk (`_get_client_ip` app.py:560)**
- 본 cycle 변경 없음. 기존 `_get_client_ip` reuse (사내 LAN + Caddy reverse proxy 전제).
- `docs/SECURITY.md §8` 에 명시: "외부 LAN 노출 시 Caddy `trust_forwarded_for` 또는 별 trusted_proxies 설정 후속 cycle 필요. feature-0006-lan-proxy-access 위임".
- TASK-0058 share 의 사내 IP 가정과 동일 trade-off.

**E4 — Anonymous share path audit (사용자 결정: B — 포함 + `ActorType` column)**
- `ActorType VARCHAR(16) NOT NULL DEFAULT 'account'` 컬럼 enum: `"account"` / `"anonymous"` / `"system"`.
- anonymous view (`GET /api/public/share/{token}`): ActorType="anonymous", ActorAccountId NULL, ResourceType="share", ResourceId=share_id, ChangeJson `{"share_token_prefix": "abc...8자", "view_count_after": N, "remote_addr": "x.x.x.x"}` (token 전체 X — fragment 만, PII 차단).
- anonymous fork (`POST /api/public/share/{token}/fork`): TASK-0058 의 fork 가 이미 `_require_account` 필수이므로 ActorType="account" + ChangeJson 에 fork source share_token_prefix 명시.
- `(ActorType, OccurredAt)` index 로 외부 access 만 filter 가능.

**E5 — Same tx admin endpoint deadlock 시나리오 (Codex 5 lock 순서)**
- 본 mutation row lock 먼저 → audit INSERT (PK auto-increment + secondary index update, contention 작음).
- product delete cascade: WebSystemPrompts → WebProductDatabases → WebRolePermissions → WebAccountPermissionOverrides → WebPermissions → WebProducts 순서. audit builder 도 같은 순서로 조회 (역순 X). cascade 끝 → audit INSERT.
- role/account permission 변경: `_ensure_permission_catalog` snapshot 읽기 + audit INSERT 같은 tx (READ COMMITTED isolation, snapshot drift 허용).
- share revoke: TASK-0058 의 race-free UPDATE 패턴 + audit INSERT 같은 tx.
- bulk delete: 입력 PK 정렬 후 처리 → 두 동시 요청이 같은 PK 순서로 lock → deadlock 회피.

**E6 — Decorator vs explicit dispatcher call: explicit 확정**
- decorator 는 magic hiding (actor capture / ChangeJson builder / masked_fields 가 endpoint 마다 다름).
- 17 endpoint (admin 13 + user 4) 마다 explicit `record_audit_event(conn, actor, action, ...)` 호출 + builder.
- ChangeJson builders 는 `src/audit_builders.py` (별 module) 또는 `app.py` 내 helper 섹션. 각 builder 가 `docs/SECURITY.md §8` sensitive field catalog 참조.

**E7 — Dispatcher SPOF 차단**
- `bin/verify-completion.sh` 의 check 에 `from app import record_audit_event` import 가능성 + ENV `AGENT_AUDIT_ENABLED` validation 추가 (Phase A1 의 verify-completion 보강).
- 100% test coverage on dispatcher (Phase B 의 `tests/test_audit_dispatcher.py`).
- startup gate: `AGENT_AUDIT_ENABLED=1` + `AGENT_MODE` check.

**E8 — Purge atomicity + chunked PK loop**

```python
def purge_audit_events(conn, cutoff_dt, actor, chunk_size=1000):
    total_deleted = 0
    first_iter = True
    started_at = now()
    idempotency_key = hash((cutoff_dt, started_at.replace(second=0, microsecond=0)))
    while True:
        with conn.begin_transaction():  # each chunk = separate tx
            rows = SELECT Id FROM WebAuditEvents WHERE OccurredAt < cutoff ORDER BY Id LIMIT chunk_size
            if not rows: break
            DELETE FROM WebAuditEvents WHERE Id IN rows
            if first_iter:
                record_audit_event(conn, actor=actor, action="audit.purge.start",
                                   resource_type="audit_range", resource_id=None,
                                   change_json={"cutoff": cutoff_dt, "chunk_size": chunk_size,
                                                "started_at": started_at,
                                                "idempotency_key": idempotency_key})
                first_iter = False
            total_deleted += len(rows)
    record_audit_event(conn, actor=actor, action="audit.purge.complete",
                       resource_type="audit_range", resource_id=None,
                       change_json={"cutoff": cutoff_dt, "total_deleted": total_deleted,
                                    "idempotency_key": idempotency_key})
```

- 각 chunk = 별 tx (Long Running Transaction 회피). `audit.purge.start` + `audit.purge.complete` 두 self-audit event. `idempotency_key = hash(cutoff, started_at_minute)` (1 분 내 중복 purge 차단).

**E9 — dba role seed/catchup 보강**
- `SEED_ROLE_DEFINITIONS` (app.py:356) 의 모든 role (pending/operator/sales/admin/dba) 의 `permissions` set 에 `audit.read.own` 추가.
- `_ensure_seed_catchup` (app.py:2516) 의 backfill loop 가 dba 도 포함. 현재 admin/operator/sales catchup 만 한다면 dba 추가 (Phase A3 실행 시 `_ensure_seed_roles` 본문 확인 + 보강).

#### Phase B 시나리오 확장 8 → 10 (E1 B + E4 B 결정 반영)

추가 시나리오:
- **(3a)** admin 의 password-reset 후 user 가 `/api/admin/audits` 본인 audit 조회 → admin event (actor=admin, target=user) 가 본인 audit 에 보임 (E1 B 의 핵심 검증).
- **(9)** anonymous share view → audit row 생성 (ActorType="anonymous", ActorAccountId NULL, share_token_prefix 만 — token 전체 X).
- **(10)** `/api/admin/audits?actor_type=anonymous` filter → anonymous 만 조회 가능 (audit.read.any 필요).

#### Test infra 보강

- `unit/feature-0003-agent-web-ui/tests/test_audit_dispatcher.py` — `record_audit_event` + `AGENT_AUDIT_ENABLED` gate + ChangeJson builders unit tests (TASK-0072 `test_search_rbac.py` 패턴 답습).
- `unit/feature-0003-agent-web-ui/tests/test_audit_rbac.py` — 10 HTTP smoke 시나리오 (urllib + 직접 DB seed).
- `unit/feature-0003-agent-web-ui/tests/test_audit_migration.py` — `WebAccountActivity` → `WebAuditEvents` migration smoke.

#### Acceptance criteria (Phase A0 ready to start)

Phase A0 실행 직전 다음이 모두 명확:
- [x] `WebAuditEvents` DDL 완전 명세 (14 columns + 5 indexes, ActorType + TargetAccountId 포함)
- [x] Dispatcher signature 확정 (`record_audit_event(conn, actor, action, resource_type, resource_id, change_json, masked_fields)`)
- [x] ChangeJson builder 명세 위치 (`audit_builders.py` 또는 app.py 내 섹션, sensitive field catalog 참조)
- [x] `AGENT_AUDIT_ENABLED` gate logic (prod startup fail-closed + dev/test toggle)
- [x] Action-specific allowlist masking 정책 (raw 검증 X, builder 화이트리스트)
- [x] Same tx (admin) / fail-open (user) 분기 + Same tx lock 순서 (E5)
- [x] Purge chunked PK loop logic (E8 의 Python 의사코드)
- [x] RBAC catalog 4건 + dba 포함 모든 role auto-grant + permission group `audit`
- [x] `WebAccountActivity` → `WebAuditEvents` migration logic
- [x] Test scenarios 13+ (Phase B 10 HTTP + dispatcher unit + migration + builders)
- [x] CONVENTIONS.md §10.6 audit group 추가 정책
- [x] SECURITY.md §8 sensitive field catalog 구조 + RemoteAddr spoof note

**0 모호성**. Phase A0 (DDL) → A6 (user endpoint hook) → B (tests) → C (frontend) → D (project docs) → E (verify + commit) 순서대로 구현 가능.

#### Eng review 결과 요약 (REVIEW.md REV-20260519-0002 정본)

`/plan-eng-review` cycle:
- 9 architectural findings (E1-E9) lock-in: E1, E4 사용자 결정 / E2, E3, E5-E9 prose lock-in
- 30 test paths coverage diagram (Phase B 10 + dispatcher unit + migration + builders)
- 5 deadlock scenarios (Codex) lock 순서 명세
- 0 critical 미해결 — Phase A0 진입 가능

REVIEW.md REV-20260519-0002 에 각 finding + decision + 근거 기록 예정 (Phase D).

---

### 2.2 Implementation Plan (TASK-0093)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Minor 등급 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high) → 5 findings + 2 minimum-fix → v2 redesign → 사용자 confirm 진행. TASK-0073 Phase E hotfix (CHG-20260520-0001) 의 routing 회귀 fragility 를 정적 검사로 영구 차단.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0093 Phase A~F 일괄, Minor 등급 verify-completion check_12 신설 + outside voice 5 findings 흡수 + helper split + fixture-based negative test) -->

#### 요지

`bin/verify-completion.sh` 에 `check_12_audit_endpoint_routing()` 신설 + helper `_check_audit_routing_order()` 분리. feature-0003-agent-web-ui 의 `src/app.py` 내 `@app.get("/api/admin/audits/{event_id}")` line number 가 정적 GET sibling endpoint (auto-discovery 패턴 — `@app.get("/api/admin/audits/<non-{>")`) 의 max line number 보다 **뒤** 인지 정적 grep 검증. FAIL 시 actionable hint 출력. `/purge` 는 method-aware POST 라 GET path collision 위험 0 — sibling list 자동 제외.

#### 현 상태 (검증)

production app.py line 9356 list / 9410 export.csv / 9482 actors / 9522 resources / 9560 purge (POST) / **9732 `/{event_id}`** — hotfix 적용 완료, 정적 GET sibling max=9522 < 9732. positive PASS 조건 충족.

#### Codex outside voice review 흡수 (5 findings + 2 minimum-fix)

| # | finding | 흡수 결정 |
|---|---|---|
| C1 | SKIP 정책 오류 — event_id 또는 sibling 부재 시 silent PASS 는 회귀 방지 게이트 의도 모순. APIRouter 분리·prefix 변경·route 삭제가 silent pass | ACCEPT → SKIP 정책 변경 (feature_id != feature-0003 만 SKIP, 나머지 분기 FAIL "manual review required") |
| C2 | grep 패턴 fragility (multi-line decorator / single quote / @router.get / prefix router / trailing slash) | ACCEPT (C1 과 통합) — structural change 미검출 시 FAIL 처리로 보강. AST 파서까지는 안 감 (Minor scope) |
| C3 | `/purge` 의 method-aware mismatch — POST 라 GET `/{event_id}` 와 collision 0. FAIL hint 의 "purge would route" 표현 부정확 | ACCEPT → `/purge` 는 sibling list 에서 자동 제외 (auto-discovery 패턴이 `@app.get(...)` 만 매치) |
| C4 | Inline 4 hardcoded sibling list 는 new static GET (e.g., `/stats`) 추가 시 stale | ACCEPT → auto-discovery (`@app.get("/api/admin/audits/<non-{>")` 패턴 자동 수집) |
| C5 | Negative test 의 production app.py 임시 이동 위험 — dirty worktree / hook / 중간 실패 | ACCEPT → temp fixture 5 scenario + helper split (`_check_audit_routing_order(app_path)` pure helper). production app.py 절대 미수정 |

추가:
- footer line "9 checks" → "10 checks: 7 pilot + worktree binding + repo immutability + audit endpoint routing" 명시화 (Codex 직접 권장).
- META mode footer ("checks #10, #11 always run") 갱신 불필요 — check_12 는 feature-specific 라 META mode 에서 의도적으로 skip.

#### 영향 파일 (1 code + 5 docs)

Backend (정책 인프라):
- `bin/verify-completion.sh` — `check_12_audit_endpoint_routing()` 함수 신설 + `_check_audit_routing_order()` pure helper split + main() 호출 추가 + footer 2 라인 갱신 (line 1126·1129). META mode footer (line 1084·1091·1094) 는 그대로.

문서:
- `unit/feature-0003-agent-web-ui/docs/TASK.md` — 본 §2.2 + TASK-0093 [ ]→[x]
- `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — CHG-20260520-0003 entry (head prepend)
- `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260520-0003 entry (head prepend, outside voice 흡수 이력)
- `unit/feature-0003-agent-web-ui/docs/REPORT.md` — Phase 별 변경 요약 + git 동기화 결과
- `unit/feature-0003-agent-web-ui/docs/TEST.md` — TEST 케이스 정의 (positive / 5 negative fixture / SKIP other-feature)

#### check_12 spec (v2, 본 cycle 채택)

```bash
check_12_audit_endpoint_routing() {
  local fdir="$1"
  local feature_id="$2"
  local app_path="${fdir}/src/app.py"

  [ "$feature_id" = "feature-0003-agent-web-ui" ] || return 0  # SKIP — non-target

  if [ ! -f "$app_path" ]; then
    log_check 12 FAIL "audit endpoint routing order" \
      "expected app.py at ${app_path} but file is missing — audit feature removed or restructured"
    return 1
  fi

  _check_audit_routing_order "$app_path"
}
```

`_check_audit_routing_order()` pure helper 가 file path 받아 routing order 검사. Phase C fixture 테스트 진입점. production app.py 외에도 임의 fixture 파일로 호출 가능. `set -euo pipefail` 환경이라 grep no-match (exit 1) 시 `|| true` fallback 처리.

#### Phase 순서

1. **Phase A** — check_12 + helper split + main() 호출 + footer 2 라인 갱신. `bash -n` syntax check PASS.
2. **Phase B** — production positive: helper wrapper 로 production app.py 호출 → `CHECK#12 PASS audit endpoint routing order` PASS. (verify-completion.sh main mode 는 META mode 분기에서 check_12 skip — 정합).
3. **Phase C** — 5 fixture negative test:
   - `valid.py` (정합 ordering) → **PASS**
   - `wrong_order.py` (event_id BEFORE static siblings) → FAIL ordering + line-number hint
   - `no_detail.py` (detail endpoint 부재) → FAIL "detail endpoint missing — possible route removal or refactor"
   - `no_siblings.py` (정적 GET sibling 부재) → FAIL "no static GET siblings — audit route layout changed"
   - `refactored.py` (APIRouter prefix) → FAIL "routes not found in expected form — manual review required"
4. **Phase D** — 5 other-feature SKIP: feature-0001 / 0002 / 0004 / 0005 / 0006 호출 → silent return 0 (rc=0, no output). 회귀 없음.
5. **Phase E** — docs 5 갱신 (본 §2.2 + MODIFY + REVIEW + REPORT + TEST).
6. **Phase F** — 최종 verify-completion 호출 (META mode 가정 PASS) + git status + 권장 commit 메시지 + 사용자 명시 commit confirm.

#### 위험도 평가 (§12.3) — Minor

| 영역 | 위험도 | 보강 |
|---|---|---|
| verify-completion.sh 정책 인프라 변경 | Minor | `bash -n` syntax + production positive + 5 fixture negative + 5 other-feature SKIP 양방향 검증 |
| feature-0003 hardcode | Minor | `feature_id` 검사 SKIP 분기. 일반화는 별 cycle (다른 feature 에 동일 패턴 발견 시) |
| structural change false-pass | **차단 (v1→v2)** | C1 흡수: SKIP→FAIL "manual review required" 로 강제. APIRouter 분리·prefix 변경·route 삭제 모두 LOUD FAIL |
| sibling list staleness | **차단 (v1→v2)** | C4 흡수: auto-discovery 패턴 (`@app.get("/api/admin/audits/<non-{>")` 자동 수집). new static GET 자동 catch |
| method-aware accuracy | **정확 (v1→v2)** | C3 흡수: GET-only sibling 자동 검출. POST (`/purge`) 자연 제외, hint 정확 |
| negative test 안전성 | **안전 (v1→v2)** | C5 흡수: temp fixture + helper split. production app.py 절대 미수정 |
| set -euo pipefail + grep no-match | **차단 (in-cycle fix)** | helper 내 `grep ... || true` fallback. log_check 호출 보장 |

**전체 등급**: Minor — verify-completion.sh 의 read-only 정적 grep 검사 신설. 영향 범위: 정책 인프라 단일 파일 + 정책 인프라가 잡는 회귀 1건. runtime side-effect 0.

#### 검증 계획

각 Phase 종료 후:
- (a) `bash -n bin/verify-completion.sh` syntax check
- (b) helper wrapper 호출 (production positive)
- (c) 5 fixture (negative)
- (d) 5 other-feature (SKIP)

전체 완료 후:
- (e) META mode `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` PASS (META mode 라 check_12 자동 skip, 다른 check 정합 검증)
- (f) git status 정합 + 권장 commit 메시지 표시 + 사용자 명시 commit confirm

#### outside voice 결과 요약 (REVIEW.md REV-20260520-0003 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, ~5분 실행, 132,668 tokens):
- 5 findings + 2 minimum-fix recommendations 도출
- 본 plan 의 5 finding 모두 ACCEPT → v2 redesign 흡수
- footer line 표현 수정 권장 흡수 (`9 checks` → `10 checks`)
- 본 사용자 정책 (`feedback_outside_voice_for_rbac`) 적용 — RBAC catalog 변경 없음에도 audit 표면 회귀 방어 정책으로 outside voice 호출. Minor 등급이지만 보안 표면 자체 점검 가치 인정.

REVIEW.md REV-20260520-0003 에 각 finding + 흡수 결정 + 근거 기록.

---

### 2.3 Implementation Plan (TASK-0092)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Minor 등급 검증 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, ~5분, 490,891 tokens) → 5 findings + 2 minimum-fix → v2 redesign → 사용자 confirm 진행. TASK-0073 Phase E 의 사용자 위임 항목 1 건 해소 — sandbox SSH 인증 차단 환경 해소 + docker/compose 가용 확인 (Docker 29.3.1 + Compose v5.1.1).

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0092 Phase A0~E 일괄, Minor 등급 audit prod gate fail-closed 7 vector matrix 검증 + Codex outside voice 5 findings 흡수) -->

#### 요지

`_enforce_audit_prod_gate()` (app.py:76-94) 의 startup fail-closed 정합성을 **7 vector matrix** 로 live container spawn 검증. `docker run --rm --entrypoint python repo-web:latest -c "import web.app"` 형태로 module load 시점에 gate trigger. exit code + stderr 3 substring 검증 + Traceback 부재 확인.

#### Codex outside voice review 흡수 (5 findings + 2 minimum-fix)

| # | finding | 흡수 결정 |
|---|---|---|
| C1 | 테스트 명령 오류 — Dockerfile 이 web UI 를 `/app/web/` 에 복사 (line 23). `python -c "import app"` 는 `ModuleNotFoundError`. uvicorn entrypoint 우회도 불명확 | **ACCEPT** → `--entrypoint python` + `import web.app` 으로 정정 |
| C2 | `depends_on: mysql` + `.env` + shared volume + 다른 worktree compose project 와 엮일 위험 | **ACCEPT** → `--no-deps` + `docker run` 직접 호출 (compose 우회). `.env` 부재라 inline `-e` 만 사용 |
| C3 | flag parsing 계약 비어있음 — `"true"`/`"yes"`/`"01"` 모두 disabled. 운영자 trap 가능 | **ACCEPT** → V6 추가 (`AGENT_AUDIT_ENABLED=true` + prod → exit 1 negative 검증). SECURITY.md §8 strict-string-equality 계약 명시 별 cycle 후속 권고 |
| C4 | stderr 검증 강화 — prefix-only 약함, full byte-equal 너무 strict | **ACCEPT** → 3 substring (`[FATAL] AUDIT REQUIRED IN PROD` + `set AGENT_AUDIT_ENABLED=1` + `TASK-0073 Phase A1`) + Traceback 부재 검증 |
| C5 | 문서 append 위치 오류 — TEST.md §3 = Test Cases 정의, §4 = Test Run History | **ACCEPT** → **§4** 에 append (기존 format 답습) |

추가 흡수: `repo-web:latest` image 이미 build 됨 — build 부담 0. compose 우회로 multi-worktree 충돌 회피.

#### 7 vector matrix v2

| # | AGENT_AUDIT_ENABLED | AGENT_MODE | 기대 결과 |
|---|---|---|---|
| V1 | `0` | `prod` | exit 1 + stderr `[FATAL] ... AGENT_MODE=prod` (target fail-closed) |
| V2 | `0` | unset | exit 1 + stderr `[FATAL] ... AGENT_MODE=(unset → prod)` (default prod 정합) |
| V3 | `0` | `staging` | exit 1 + stderr `[FATAL] ... AGENT_MODE=staging` (non-dev/test 정합) |
| V4 | `0` | `dev` | exit 0 + stdout `IMPORTED OK` (dev/test bypass 허용) |
| V5 | `1` | `prod` | exit 0 + stdout `IMPORTED OK` (positive control) |
| **V6** (Codex C3) | `true` | `prod` | exit 1 + stderr `[FATAL] ... AGENT_MODE=prod` (strict-string-equality 계약) |
| **V7** | unset | unset | exit 0 + stdout `IMPORTED OK` (default `1` + default prod 정상) |

#### 영향 파일 (docs only, 5 파일)

- `unit/feature-0003-agent-web-ui/docs/TEST.md` — **§4** Test Run History 에 본 cycle 7 vector 결과 append
- `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0092 [ ]→[x] + 본 §2.3 plan
- `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — CHG-20260520-0004 entry
- `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260520-0004 [AGENT-TEAM:codex-outside-voice]
- `unit/feature-0003-agent-web-ui/docs/REPORT.md` — §1 Summary 갱신

#### Phase 순서

1. **Phase A0** — `.env` / image 가용성 확인. `repo-web:latest` 존재 확인 (435MB). `.env` 부재 — inline `-e` 만 사용 (compose 우회).
2. **Phase A** — 7 vector spawn (`docker run --rm --entrypoint python repo-web:latest -c "import web.app"`). 각 vector 의 stderr + rc capture.
3. **Phase B** — rc match + stderr 3 substring 모두 포함 + Traceback 부재 검증. PASS vector 는 `[FATAL]` 부재 + `IMPORTED OK` 정합.
4. **Phase C** — TEST.md §4 + 4 docs 갱신.
5. **Phase D** — verify-completion PASS + commit.
6. **Phase E** — issue + push + PR + merge + cleanup (cycle-finalize 패턴, TASK-0093 cycle 답습).

#### 위험도 평가 (§12.3) — **Minor**

| 영역 | 위험도 | 보강 |
|---|---|---|
| docker spawn 부수효과 | Minor | `--rm` 즉시 cleanup, image 이미 build, `--no-deps` mysql 우회 |
| 7 vector 결과 unexpected | Minor | 본 PR 의 핵심 가치 — fail-closed 가정과 실제 동작 일치 검증 |
| `.env` 부재 → compose fail | **차단 (in-cycle fix)** | docker run 직접 호출 (compose 우회). inline `-e` 만 사용 |
| Code 변경 0 | **N/A** | docs append only |
| multi-worktree 충돌 | Minor | `docker run` 직접 호출 (compose project 격리 불필요) |
| 운영자 trap (`"true"` fail-closed) | Minor | V6 검증으로 명시화. SECURITY.md §8 계약 별 cycle 후속 |

**전체 등급**: Minor — 비파괴 검증 작업, code 변경 0, docs append only. audit subsystem 보안 표면 자체 검증 → outside voice review 가치 (`feedback_outside_voice_for_rbac` user policy 정합).

#### 검증 결과 (Phase A~B 실행 후)

**7 vector PASS (7/7)**. 모든 FAIL vector 가 rc=1 + stderr 3 substring + Traceback 부재. PASS vector 는 stdout `IMPORTED OK` + stderr `[FATAL]` 부재. live container spawn 으로 코드 path 정합성 + 메시지 정확성 + dev/test bypass 정합성 모두 확인. TEST.md §4 의 본 cycle entry (2026-05-20) 참조.

#### outside voice 결과 요약 (REVIEW.md REV-20260520-0004 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, ~5분 실행, 490,891 tokens):
- 5 critical findings + 2 minimum-fix recommendations 도출
- 본 plan 의 5 finding 모두 ACCEPT → v2 redesign 흡수
- 7 vector matrix (v1 5 → v2 7 vectors) 로 확장
- 본 사용자 정책 (`feedback_outside_voice_for_rbac`) 적용 — RBAC catalog 변경 없음에도 audit subsystem 보안 표면 자체 검증 가치로 outside voice 호출.

REVIEW.md REV-20260520-0004 에 각 finding + 흡수 결정 + 근거 기록.

---

### 2.4 Implementation Plan (TASK-0086)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 **Major 등급 파괴적 DROP** 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, ~5분, 398,567 tokens) → 5 findings + 2 minimum-fix → v2 redesign → 사용자 confirm → backup 검증 → DROP ack 진행. TASK-0073 Phase A2 의 dual write 종료 + 일시 공존된 `WebAccountActivity` legacy table 제거.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0086 Phase A0~J 일괄, Major 등급 WebAccountActivity DROP + dual write 종료 + Codex outside voice 5 findings 흡수) -->

#### 요지

`_log_search_activity()` 의 dual write 패턴 (legacy WebAccountActivity INSERT + dispatcher mirror) 을 dispatcher only 로 단일화 + legacy table DROP. backup + scratch restore rehearsal + 1:1 정합 (legacy=74, mirror=74) + 사용자 명시 ack 후 진행. rollback 1~2 cycle window 위해 `_migrate_web_account_activity_to_audit()` helper 만 보존 (table-absent silent skip).

#### baseline 검증 (Phase A 완료)

| 항목 | 값 |
|---|---|
| WebAccountActivity row count | 74 (id 1~74, MatchedCount sum=502) |
| WebAuditEvents `conversation.search.body` mirror count | 74 (1:1 정합) |
| 초기 흡수 (RequestId='account-activity:<id>') | 68 row (TASK-0073 Phase A2 의 1회 호출) |
| dual write 추가 (RequestId=NULL, `_legacy_source="WebAccountActivity"`) | 6 row (id 132~137 in WebAuditEvents) |
| Backup file | `artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql` (11,950 bytes) |
| Row digest | `a09e7898d1ce88711f7a850ab5fbcc91` |
| File digest (md5) | `f4163df9dc1b7ac81ae4c463a0f35e98` |
| Scratch restore rehearsal | PASS (별 schema import → digest match ✓) |
| mysqldump options | `--single-transaction --quick --set-charset --create-options --add-drop-table --triggers --hex-blob --no-tablespaces` (Codex C4) |

#### Codex outside voice review 흡수 (5 findings + 2 minimum-fix)

| # | finding | 흡수 결정 |
|---|---|---|
| **C1** | Option A (graceful skip) 불가능 — `_ensure_web_account_activity_schema()` 가 line 2979 + 3130 에서 계속 호출. DROP 후 재기동 시 table 다시 생성 | **ACCEPT** → helper Option B 채택 — 호출 + 정의 모두 명시 제거. migration helper 만 rollback window 보존 |
| **C2** | dispatcher-only 전환 = mirror 실패가 곧 감사 누락. record_audit_event 는 fail-open. legacy INSERT 제거 후 mirror = primary | **ACCEPT** → Phase D+E lightweight smoke (host-mounted code + docker run import). 이전 6 row (id 69~74) 가 mirror 와 1:1 정합 입증 → mirror 작동성 확인. tests/test_audit_migration.py M3 제거 |
| **C3** | "single tx DROP" 표현 잘못됨 — MySQL DDL 은 implicit commit | **ACCEPT** → "DROP TABLE single statement" 표현으로 정정 |
| **C4** | Backup 검증 약함 — row count 부족. mysqldump 옵션 보강 + scratch restore rehearsal 필수 | **ACCEPT** → mysqldump 8 옵션 명시 + scratch restore + canonical digest |
| **C5** | Rollback 정의 불완전 — backup restore = legacy table 만. code revert 필요 | **ACCEPT** → rollback runbook 2 시나리오 분리 (DB restore only / code revert + DB restore) |

추가 흡수:
- function rename `_log_search_activity()` → 보류 (caller 안정성 우위, 별 cycle).
- PR title: `chore(feature-0003): retire WebAccountActivity legacy audit table` (refactor 아닌 운영 DB DROP).

#### 영향 파일 (code 1 + tests 1 + docs 5 + artifacts 1 backup)

Backend:
- `unit/feature-0003-agent-web-ui/src/app.py`:
  - `_log_search_activity()` (line 2566~): legacy INSERT 블록 제거 (이전 line 2589-2615). dispatcher mirror 만 primary path. docstring 갱신 (TASK-0086 marker).
  - `_ensure_web_account_activity_schema()` (이전 line 2537-2563): 함수 정의 제거 (dead code).
  - `_ensure_web_account_activity_schema()` 호출 2 사이트 (line ~2978, ~3128) 제거.
  - `_migrate_web_account_activity_to_audit()`: 함수 본체 + table-absent skip check 보존. docstring 갱신 (TASK-0086 rollback window 명시).

Tests:
- `unit/feature-0003-agent-web-ui/tests/test_audit_migration.py`:
  - 모듈 docstring 갱신 (3→2 시나리오, TASK-0086 marker).
  - `m3_log_search_activity_dual_write()` 함수 제거 (Codex C2 minimum-fix).
  - `main()` 의 M3 호출 제거.

문서:
- `docs/SECURITY.md` §9.8 — "별 cycle DROP" → "DROP 완료 (2026-05-20)" 갱신 + 8 step 절차 명시 + backup file + rollback 2 시나리오 cross-reference.
- `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0086 [ ]→[x] + 본 §2.4 plan + Completion Checklist.
- `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — CHG-20260520-0005 entry.
- `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260520-0005 [AGENT-TEAM:codex-outside-voice].
- `unit/feature-0003-agent-web-ui/docs/REPORT.md` — §1 Summary 갱신 + 1.archived TASK-0092 보존.
- `unit/feature-0003-agent-web-ui/docs/TEST.md` — §4 본 cycle backup + DROP 검증 결과 prepend.

Backup:
- `artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql` (11,950 bytes).

#### Phase 순서 (Codex 7 step 정합)

1. **Phase A** — mysqldump backup (8 옵션) + scratch restore rehearsal (별 schema import + digest match) + 1:1 정합 검증 (74=74). **완료**.
2. **Phase B** — 사용자 명시 ack (DROP 실행 직전). **완료**.
3. **Phase C** — code 변경 3:
   - `_log_search_activity()` 의 legacy INSERT 블록 제거 (line 2589-2615 → 함수 docstring 갱신 + dispatcher mirror 만 유지).
   - `_ensure_web_account_activity_schema()` 호출 제거 (이전 line 2979 + 3130, 2 사이트) + 함수 정의 제거.
   - `_migrate_web_account_activity_to_audit()` 보존 (table-absent skip + docstring rollback window 명시).
   - py_compile PASS. **완료**.
4. **Phase D+E** — lightweight smoke: `docker run --rm --entrypoint python -v <wt-src>:/app/web repo-web:latest -c "import web.app"`. import OK + `_ensure_web_account_activity_schema` 부재 확인 + `_migrate_web_account_activity_to_audit` 존재 확인. **완료**.
5. **Phase F** — `docker exec repo-mysql-1 mysql ... -e "DROP TABLE IF EXISTS WebAccountActivity"`. **완료**.
6. **Phase G** — `SHOW TABLES LIKE 'WebAccountActivity'` = 0 + mirror row 74 보존 확인. **완료**.
7. **Phase H** — docs 5 + tests 1 갱신. **완료** (본 §2.4 + SECURITY §9.8 + MODIFY + REVIEW + REPORT + TEST + test_audit_migration.py M3 제거).
8. **Phase I** — verify-completion PASS + commit. **본 단계 진행 중**.
9. **Phase J** — issue + push + PR + merge + cleanup (cycle-finalize 패턴, TASK-0093/0092 cycle 답습).

#### 위험도 평가 (§12.3) — **Major** (파괴적 DROP, backup + ack 가 mitigation)

| 영역 | 위험도 | 보강 |
|---|---|---|
| WebAccountActivity 데이터 영구 손실 | **Critical → Major (backup 후)** | mysqldump 8 옵션 + scratch restore rehearsal + digest match + 사용자 명시 ack (Phase B) |
| dual write 제거 후 회귀 | Major | 이전 6 row (id 69~74) 의 mirror 1:1 정합 입증 (dual_write_only=NULL marker + ChangeJson._legacy_source) + Phase D+E lightweight smoke |
| helper Option B 명시 제거 | Major (v1→v2) | C1 분석으로 Option A 불가능 확정. helper 호출 + 정의 모두 제거. migration helper 만 보존 (rollback window) |
| MySQL DDL atomicity 오해 | Minor (v1→v2 정정) | "single tx" → "single statement" 표현 정정. DDL implicit commit 명시 |
| Backup 검증 약함 | **차단 (v1→v2)** | C4 흡수 — mysqldump 8 옵션 + scratch restore rehearsal + canonical digest. 단 row count 만 의존 X |
| Rollback 시나리오 모호 | **차단 (v1→v2)** | C5 흡수 — 2 시나리오 분리 (DB restore only / code revert + DB restore). 본 plan + SECURITY §9.8 cross-reference |

**전체 등급**: Major (파괴적 DROP + dual write 제거 + helper 처리 + 5 step 일괄). backup + 사용자 ack + scratch restore 가 핵심 risk mitigation. rollback 가능성 확보.

#### Rollback runbook (2 시나리오)

**시나리오 1 — DB restore only**:
- 코드는 그대로 (TASK-0086 후 상태), table 만 복구.
- `docker exec -i repo-mysql-1 mysql -uroot -p<PWD> agent_memory < /root/download/docker/mysql_ai_delegated_dev/artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql`.
- 결과: WebAccountActivity 가 다시 존재. `_migrate_web_account_activity_to_audit()` 의 SHOW TABLES check 가 true 됨 → 다음 fast-path catchup 시 idempotent skip (이미 마이그레이션된 row 는 RequestId marker 로 NOT EXISTS).
- **한계**: 새 search 호출은 dispatcher only (코드 변경 안 됨) → table 이 다시 비어가는 상태로 회귀. read-only 보존용.

**시나리오 2 — code revert + DB restore** (완전 rollback):
- `git revert <CHG-20260520-0005 commit>` + `docker compose restart web` + DB restore.
- dual write 부활 + WebAccountActivity 새 row 도 들어감 + mirror 도 들어감.
- 완전 회복 시 사용.

#### 검증 결과 (Phase A~G 실행 후, 2026-05-20)

- backup integrity: scratch restore digest match (`a09e7898d1ce88711f7a850ab5fbcc91`) ✓
- 1:1 정합: legacy 74 = mirror 74 ✓
- DROP 결과: `tables_remaining` = 0 (정합) ✓
- mirror 보존: WebAuditEvents `conversation.search.body` = 74 row 변동 없음 ✓
- py_compile: PASS ✓
- lightweight import smoke: PASS (helper 함수 정의 제거 + migration helper 보존 확인) ✓

#### outside voice 결과 요약 (REVIEW.md REV-20260520-0005 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, ~5분, 398,567 tokens):
- 5 critical findings + 2 minimum-fix recommendations 도출
- 본 plan 의 5 finding 모두 ACCEPT → v2 redesign 흡수
- Major + 파괴적 DROP 의무 outside voice (`feedback_outside_voice_for_rbac` user policy)

REVIEW.md REV-20260520-0005 에 각 finding + 흡수 결정 + 근거 기록.

---

### 2.5 Implementation Plan (TASK-0091)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 **~~Minor~~→Major 등급 audit integrity fix** 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, ~5분, 687,409 tokens) → 5 critical findings + 2 minimum-fix → v2 redesign (scope 확장 — audit integrity fix 포함) → 사용자 confirm 진행. TASK-0073 Phase A5 의 admin.product.update audit 정합성 강화 + autocommit/transaction 결함 fix.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0091 Phase A~F 일괄, ~~Minor~~→Major audit integrity fix + before/after full snapshot + Codex outside voice 5 findings 흡수) -->

#### 요지

`admin.product.update` audit 의 before/after = `{id, product_key}` 만 (2 field) → full row snapshot 으로 확장. Codex outside voice 가 추가로 **audit integrity 결함** (autocommit=True default + UPDATE 즉시 commit + audit 실패 시 rollback 가능 0) 발견 — 본 cycle 일괄 fix.

#### Codex outside voice review 흡수 (5 findings)

| # | Codex Finding | 흡수 |
|---|---|---|
| **C1** | `system_prompt.content` full 저장 = SECURITY.md §9.2 위반 (full content 금지, `content_len_*` + preview 만). 기존 `admin.system_prompt.update` builder 가 이미 정합 패턴 (`content_full` masked) | **ACCEPT** → snapshot 에 `system_prompt_summary = {present, content_len, updated_at}` 만, content 본문 제외 |
| **C2** | `admin_update_product()` 가 **same tx audit 아님** — autocommit=True default + UPDATE 즉시 commit + audit fail 시 rollback 가능 0. **Minor 아닌 audit integrity 결함** | **ACCEPT (scope 확장)** → `conn.autocommit=False` + `SELECT FOR UPDATE` + commit + finally autocommit=True |
| **C3** | `_list_products()` 기반 snapshot 과잉 (전체 list scan + FOR UPDATE 불가). databases/system_prompt 별 endpoint = 별 audit | **ACCEPT** → single-row `SELECT FOR UPDATE`. `databases` 제외 (별 endpoint `admin.product.databases.update` 의 audit 으로 분리) |
| **C4** | `sort_order` / `is_default` 누락 = **현재 결함**. endpoint 가 갱신하는데 allowlist 빠짐. `is_default=true` side effect 도 기록 권장 | **ACCEPT** → allowlist 에 `sort_order` + `is_default` 추가 + `default_cleared_product_ids` extra_change_json |
| **C5** | Rollback 설명 낙관적 — full prompt 가 ChangeJson 들어가면 code revert 만으로 복구 안 됨 | **자동 해소** (C1 ACCEPT 로 system_prompt content 가 애초에 안 들어감) |

#### 영향 파일 (code 1 + docs 6)

Backend:
- `unit/feature-0003-agent-web-ui/src/app.py`:
  - **신규 helper `_audit_product_snapshot(conn, product_id)`** (~line 2127): single-row WebProducts snapshot + `SELECT ... FOR UPDATE` + `system_prompt_summary` (content 제외). `databases` 제외 (Codex C3).
  - **`admin_update_product()` endpoint 갱신** (line 8328~): `conn.autocommit=False` + before snapshot + UPDATE + `default_cleared_product_ids` 캡처 + after snapshot + audit + commit + `finally autocommit=True` (Codex C2).
  - **`_AUDIT_BUILDER_PRODUCT_FIELDS` 확장** (line 8862): 7 → 8 field. `+is_default`, `+sort_order`, `+system_prompt_summary` / `-databases`, `-system_prompt`.
  - **builder branch `admin.product.update` 갱신** (line 8966~): `default_cleared_product_ids` 키 명시 처리.

문서:
- `unit/feature-0003-agent-web-ui/docs/TASK.md` §2.5 본 plan + TASK-0091 [x]
- `unit/feature-0003-agent-web-ui/docs/MODIFY.md` CHG-20260520-0006
- `unit/feature-0003-agent-web-ui/docs/REVIEW.md` REV-20260520-0006
- `unit/feature-0003-agent-web-ui/docs/REPORT.md` §1 Summary
- `unit/feature-0003-agent-web-ui/docs/TEST.md` §4 sentinel + delta smoke 결과
- `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` AC-0192

#### Phase 순서

1. **Phase A** — `_audit_product_snapshot()` helper 신설. **완료**.
2. **Phase B** — endpoint 명시 transaction + before/after snapshot. **완료**.
3. **Phase B-2** — `_AUDIT_BUILDER_PRODUCT_FIELDS` 확장 + builder branch `default_cleared_product_ids` 처리. **완료**.
4. **Phase C** — py_compile + sentinel smoke. **PASS** — SENTINEL `TASK-0091-SENTINEL-...` ChangeJson 부재 ✓ / `should_not_leak` (databases) 부재 ✓ / sort_order 100→50 ✓ / is_default False→True ✓ / `default_cleared_product_ids: [5,9]` ✓ / `system_prompt_summary` 정합 ✓.
5. **Phase D** — docs 6 갱신. **본 단계 진행 중**.
6. **Phase E** — verify-completion PASS + commit.
7. **Phase F** — cycle-finalize (issue + push + PR + merge + cleanup).

#### 위험도 (§12.3) — **Major** (Minor→Major scope 확장)

| 영역 | 위험도 | 보강 |
|---|---|---|
| `system_prompt.content` PII 노출 | **차단 (Codex C1)** | `system_prompt_summary` only (present/content_len/updated_at). full content drop sentinel test PASS |
| `admin_update_product()` autocommit integrity | **차단 (Codex C2)** | 명시 transaction (autocommit=False + commit + finally autocommit=True). audit 실패 시 UPDATE rollback 가능 |
| Concurrent PATCH race | **차단 (Codex C2)** | `SELECT ... FOR UPDATE` row lock |
| allowlist 누락 (sort_order/is_default) | **차단 (Codex C4)** | allowlist 확장. before/after delta 정합 |
| `is_default=true` side effect 추적 | **차단 (Codex C4)** | `default_cleared_product_ids` extra ChangeJson |
| `databases` audit noise | **차단 (Codex C3)** | allowlist 제외. 별 endpoint audit 으로 분리 |
| Rollback risk | **자동 해소** | C1 ACCEPT 로 content full drop — 별 redact SQL 불필요 |

**전체 등급**: ~~Minor~~ → **Major** (audit integrity fix scope 확장). 단 사용자 영향 0 (audit row 정확성만), DB schema 변경 0.

#### 검증 결과 (Phase C 실행 후)

- `python3 -m py_compile app.py` → PASS
- sentinel smoke (`docker run --rm --entrypoint python -v <src>:/app/web repo-web:latest -c "..."`):
  - `'TASK-0091-SENTINEL' in body: False` ✓ (system_prompt full content drop)
  - `'should_not_leak' in body: False` ✓ (databases drop)
  - `sort_order before=100 after=50` ✓
  - `is_default before=False after=True` ✓
  - `default_cleared_product_ids: [5, 9]` ✓
  - `system_prompt_summary: {present: True, content_len: 1234/2000, updated_at: '2026-05-20'}` ✓

#### outside voice 결과 요약 (REVIEW.md REV-20260520-0006 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, ~5분, 687,409 tokens):
- 5 critical findings 도출, 2 minimum-fix 권고
- 본 plan 의 5 findings 모두 ACCEPT → v2 redesign (scope Minor→Major 확장)
- `feedback_outside_voice_for_rbac` user policy 적용 — audit 표면 직접 변경

REVIEW.md REV-20260520-0006 에 각 finding + 흡수 결정 + 근거 기록.

---

### 2.6 Implementation Plan (TASK-0088)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 **Minor 등급 docs-only ADR 결정** 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, 390,785 tokens) → 5 critical findings + 2 minimum-fix → v2 redesign → 사용자 confirm 진행. ADR-0019 의 Codex C1 lock-in 최종 결론.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0088 docs-only, ADR-0020 Decoupled 채택 + Codex outside voice 5 findings 흡수) -->

#### 요지

`slow_query_log` 와 `WebAuditEvents` 의 통합 가능성 — ADR-0019 (audit subsystem) 의 별 cycle 분리 lock-in 최종 결론. **Option C — Decoupled 채택**. 주 근거 = raw SQL text PII 차단.

#### Codex outside voice review 흡수 (5 findings)

| # | Finding | 흡수 |
|---|---|---|
| C1 | 현재 mysql conf 에 `slow_query_log` 설정 부재 (MySQL 8.0 default disabled). framing "현재 통합" → "**향후** 통합 여부" 정정 | **ACCEPT** → Context 에 current state 명시 |
| C2 | Option C 의 **주 근거가 PII 차단** (raw SQL = PasswordHash/Token/API key/임시 비밀번호/raw LLM prompt literal) 이어야. "의도 mismatch" 추상적 | **ACCEPT** → Decision 1순위 근거 = raw SQL text PII 차단 |
| C3 | Option A reject 사유 부정확 — retention/RBAC 정합 trivial. 진짜 사유 = semantic pollution + raw SQL PII + ChangeJson 비대화 + actor/target 의미 부재 + 고빈도 audit table 오염 | **ACCEPT** → Option A reject 재작성 (4 구체 사유) |
| C4 | Option B reject 약함. 구체 사유 = raw SQL exfiltration 표면 + mount/rotation/race + 대용량 파일 DoS + `audit.read.any` 권한 의미 오염 + MySQL `TABLE` log destination 우회 | **ACCEPT** → Option B reject 재작성 (5 구체 사유) |
| C5 | performance_schema 빠짐. MySQL 8.0 의 `events_statements_summary_by_digest` digest 집계 1차 도구 | **ACCEPT** → Consequences 에 PS digest-first 권유 (1차), slow_query_log incident enable (2차) |

#### 영향 파일 (docs only, 7 파일)

- `docs/DECISIONS.md` — ADR-0020 신설 (ADR-0019 Consequences 다음). ADR-0019 의 "별 cycle 분리" 라인 cross-reference 추가.
- `docs/SECURITY.md §9.9` — ADR-0020 cross-reference (slow_query_log = 민감 로그, admin UI/ChangeJson 복제 금지).
- `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0088 [x] + 본 §2.6 plan.
- `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — CHG-20260520-0007.
- `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260520-0007.
- `unit/feature-0003-agent-web-ui/docs/REPORT.md` — §1 Summary.
- `unit/feature-0003-agent-web-ui/docs/TEST.md` — §4 본 cycle 결과 (docs only, ADR review trace).

#### Phase 순서

1. **Phase A** — `docs/DECISIONS.md` ADR-0020 작성. **완료**.
2. **Phase B** — `docs/SECURITY.md §9.9` cross-reference + docs 5 갱신. **완료**.
3. **Phase C** — verify-completion + commit.
4. **Phase D** — cycle-finalize (issue + push + PR + merge + cleanup).

#### 위험도 (§12.3) — **Minor**

docs only, code 변경 0, DB schema 변경 0, runtime side-effect 0. ADR 자체가 future trigger condition 만 명시 — 현재 운영 영향 0.

#### Decision 핵심 (Option C — Decoupled)

- **slow_query_log 와 WebAuditEvents 통합 안 함**.
- **운영 성능 관측**: `performance_schema` / `sys` digest views (1차) + slow_query_log incident enable (2차).
- **slow_query_log raw SQL = 민감 로그**. WebAuditEvents / ChangeJson / admin UI 에 복제 금지.
- **외부 SaaS / multi-tenant trigger**: `performance-log.read` permission 신설 + raw SQL redaction/sampling + threat model ADR 선행.

#### outside voice 결과 (REVIEW.md REV-20260520-0007 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, 390,785 tokens):
- 5 critical findings 도출, 2 minimum-fix 권고
- 본 ADR 의 5 findings 모두 ACCEPT → v2 redesign
- `feedback_outside_voice_for_rbac` user policy 적용 — ADR 자체가 audit 정책 표면 영향

---

### 2.7 Implementation Plan (TASK-0090)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 **Minor 등급 backend code 변경** 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, 550,870 tokens) → 5 critical findings + 2 minimum-fix → v2 redesign → 사용자 confirm 진행.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0090 Phase A~D 일괄, Minor backend code + Codex outside voice 5 findings 흡수) -->

#### 요지

`/api/admin/audits/export.csv` 의 hard cap 50k row + `cur.fetchall()` buffer + `io.StringIO()` 전체 메모리 로드를 **StreamingResponse + sync generator + keyset cursor pagination** 으로 전환. large fleet (100k+) memory footprint 안전 + export self-audit + try/finally cleanup.

#### Codex outside voice review 흡수 (5 findings)

| # | Finding | 흡수 |
|---|---|---|
| **C1** | async generator + sync mysql.connector = event loop blocking. StreamingResponse 는 sync iterator 도 받음 (iterate_in_threadpool). endpoint conn close 가 generator 보다 먼저 실행 → streaming-only conn 필요 | **ACCEPT** → `def csv_iter()` sync generator + 별 streaming conn (generator 내부 finally cleanup) |
| **C2** | consistent snapshot 은 long transaction 부담. audit append-only → `MAX(Id)` high-water mark 권장 | **ACCEPT** → 시작 시 `SELECT MAX(Id) FROM WebAuditEvents{where}` 잡고 모든 page `Id <= max_id AND Id < cursor_id` |
| **C3** | keyset + filter 정합 OK, 단 query plan 미보장. EXPLAIN FORMAT=JSON 권장 | **ACCEPT** → TEST.md 에 representative filters EXPLAIN 기록 (live mysql 실행 가능 시 future cycle, 본 cycle 은 코드 변경만) |
| **C4** | 50k cap 제거 = DoS/계약 변경. SECURITY 갱신 + export self-audit + 동시 실행 제한 | **ACCEPT (부분)** → cap 제거 + SECURITY §9.5 갱신 + export self-audit (start + complete/aborted). 동시 실행 제한은 multi-worker semaphore 정합 → 별 cycle followup |
| **C5** | cleanup generator try/finally — client disconnect / timeout 시 cursor/conn 누설 | **ACCEPT** → generator 내부 try/finally (cursor.close + conn.close + complete audit) |

추가 흡수 (minimum-fix 2):
- chunk_size **1000→500** (안전 마진)
- 1 row yield 대신 **64KiB byte-threshold flush**
- CRLF 유지, BOM 추가 안 함

#### 영향 파일 (code 1 + docs 6)

- `unit/feature-0003-agent-web-ui/src/app.py`:
  - `StreamingResponse` import 추가 (line 28).
  - 신규 helper `_audit_export_filter_hash(params)` (~line 9466) — filter PII 회피용 sha256[:16] hash.
  - 신규 const `_AUDIT_EXPORT_CHUNK_SIZE = 500`, `_AUDIT_EXPORT_FLUSH_BYTES = 65536`.
  - `export_audit_events_csv` endpoint 전면 재작성 (line 9476~9683): 2-phase (짧은 auth conn + max_id capture + start audit → sync generator with streaming-only conn + chunked SELECT + byte-threshold flush + try/finally + complete audit).
- 문서:
  - `docs/SECURITY.md §9.5`: `audit.export` permission 설명 갱신 (hard cap 50k 제거 + StreamingResponse + max_id high-water + self-audit).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: §2.7 본 plan + TASK-0090 [x].
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: CHG-20260520-0008.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260520-0008.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md`: §4 본 cycle 결과.
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0193.

#### Phase 순서

1. **Phase A** — endpoint 재작성 + StreamingResponse import. **완료**.
2. **Phase B** — py_compile PASS + lightweight smoke (host-mounted code + docker run): `_AUDIT_EXPORT_CHUNK_SIZE=500`, `_AUDIT_EXPORT_FLUSH_BYTES=65536`, helper 존재, `StreamingResponse` import, filter_hash deterministic. **완료**.
3. **Phase C** — docs 6 갱신. **본 단계 진행 중**.
4. **Phase D** — verify-completion + commit + cycle-finalize (issue + push + PR + merge + cleanup).

#### 위험도 (§12.3) — **Minor**

backend code 1 endpoint, runtime 영향 audit subsystem only, contract 변경 = hard cap 50k 제거 (응답 형식 CSV 동일). live PATCH runtime smoke = PR merge 후 사용자 위임.

#### Recommended future cycle (Codex C4 followup)

- 동시 export 제한 (multi-worker semaphore 정합 검토)
- representative filters EXPLAIN FORMAT=JSON 분석 (live mysql)

#### outside voice 결과 (REVIEW.md REV-20260520-0008 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, 550,870 tokens):
- 5 critical findings + 2 minimum-fix recommendations
- 5 findings 모두 ACCEPT → v2 redesign
- C4 부분 흡수 — 동시 실행 제한은 별 cycle (multi-worker semaphore)

---

### 2.8 Implementation Plan (TASK-0089)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 **Minor 등급 frontend + backend 2 endpoint 추가** 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-20 에 plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, 829,505 tokens) → 5 critical findings + 2 minimum-fix → v2 redesign (scope 확장 — backend endpoint 2 신설) → 사용자 confirm 진행.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20 (TASK-0089 Phase A~G, Minor backend 2 endpoint + frontend 3 + Codex 5 findings 흡수) -->

#### 요지

profile drawer 5번째 탭 "내 감사 로그" 신설. 본인 audit row (Actor or Target = self) 표시. backend 신규 endpoint 2 — `/api/profile/audits` + `/api/profile/audits/{event_id}` — `scope="own"` 강제 (Codex C2). CSV export / purge 는 admin 한정 미노출.

#### Codex outside voice 5 findings 흡수

| # | Finding | 흡수 |
|---|---|---|
| **C1** | `/api/admin/audits` URL 의미 mismatch — `.own` 호출 가능하나 `/admin/` 이 drawer 와 부합 안 함 | **ACCEPT** → 신규 `/api/profile/audits` + `/api/profile/audits/{id}` |
| **C2** | `_audit_resolve_read_scope()` `.any` > `.own` 우선 — frontend `scope=own` 만으로 부족, backend 강제 필요 | **ACCEPT** → backend `scope="own"` 강제 (`_audit_compose_where(scope="own", ...)`). `.any` 보유자도 본인만 |
| **C3** | CSV export drawer 제외 — export endpoint `scope="any"` 고정, drawer 노출 시 전체 CSV 유출 | **ACCEPT** → drawer 에 export/purge 미노출 |
| **C4** | drawer 폭 390px 에 2-column 안 맞음 + ChangeJson 가독성 | **ACCEPT** → 1-column list + inline detail expand + `<pre>` overflow:auto 수평 스크롤 |
| **C5** | 권한 race — backend OK, frontend 처리 필요 (403 → "권한 없음", tab gate) | **ACCEPT** → `updateProfileAuditTabVisibility()` + 403 graceful state.profileAudit.forbidden |

추가: mini filter = `action_code` + `from_at` + `to_at` (3 필드). actor_id / actor_type 제거 (본인 한정 무의미).

#### 영향 파일 (code 4 + docs 6)

Backend:
- `unit/feature-0003-agent-web-ui/src/app.py`: 신규 endpoint 2 (`list_profile_audit_events`, `get_profile_audit_event`) — 기존 helper (`_audit_parse_filter_params`, `_audit_compose_where`, `_audit_row_to_dict`, `_audit_build_self_filter_sql`) 재사용.

Frontend:
- `unit/feature-0003-agent-web-ui/src/static/index.html`: drawer-tab "내 감사 로그" + drawer-pane (filter row mini + 1-column list + pagination + inline detail). cache-bust `v=20260520-profile-audit`.
- `unit/feature-0003-agent-web-ui/src/static/app.js`: `state.profileAudit` + helper (`_profileAuditEscapeHtml`, `_profileAuditFormatDt`, `_profileAuditHasReadPermission`, `updateProfileAuditTabVisibility`, `_profileAuditReadFilters`, `_profileAuditClearFilters`) + loader (`loadProfileAuditList`) + renderer (`renderProfileAuditList`, `renderProfileAuditDetail`) + handlers (`attachProfileAuditHandlers`). tab click handler 의 audit branch + `renderProfile()` 의 tab visibility wire.
- `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.profile-audit-*` ~15 클래스 (filter / row / detail / `<pre>` 수평 스크롤).

문서: TASK §2.8 + MODIFY CHG-20260520-0009 + REVIEW REV-20260520-0009 + REPORT §1 + TEST §4 + FUNCTION AC-0194.

#### Phase 순서

1. **Phase A** — backend endpoint 2 신설. **완료**.
2. **Phase B** — index.html drawer-tab + drawer-pane. **완료**.
3. **Phase C** — app.js state + helper + loader + renderer + handlers + tab wire. **완료**.
4. **Phase D** — styles.css. **완료**.
5. **Phase E** — py_compile + node --check + routing smoke. **PASS** (`/api/profile/audits` + `/api/profile/audits/{event_id}` 등록 확인). **완료**.
6. **Phase F** — docs 6 + FUNCTION AC-0194. **본 단계 진행 중**.
7. **Phase G** — verify-completion + commit + cycle-finalize.

#### 위험도 (§12.3) — **Minor**

backend code 2 endpoint (helper 재사용) + frontend 3 + docs 6. runtime 영향 audit subsystem only. live browser smoke = PR merge 후 사용자.

#### outside voice 결과 (REVIEW.md REV-20260520-0009 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, 829,505 tokens):
- 5 critical findings + 2 minimum-fix recommendations
- 5 findings 모두 ACCEPT → v2 redesign (frontend only → backend endpoint 2 추가)

---

### 2.9 Implementation Plan (TASK-0087)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Major 등급 (보안 표면 + multi-feature) 변경 계획이다. **상태**: `approved-after-outside-voice`. TASK-0073 Eng review E3 의 deferred 항목 (TASK-0058 share 사내 IP 가정과 동일 trade-off) 을 명시적 정책 + 코드로 lock-in. Plan v1 (RFC1918 trust + silent skip) → Codex outside voice review 6 findings (Major 5 + Minor 1) → Plan v2 (Caddy XFF 정규화 + mode-aware fail-loud + XFF IP 검증) 흡수.

#### 사용자 in-cycle 결정 (3 항목)

| 결정 | 채택안 | 근거 |
|---|---|---|
| Plan v2 흡수 범위 | 전부 흡수 + docker-compose port mapping 변경은 별 cycle | 본 worktree 컨테이너는 테스트 후 정리. 외부 접속 경로 유지 필요. Codex 권고 "port mapping 변경" 은 사용자 환경 외 별 사이클에서 검토 |
| `WEB_TRUSTED_PROXIES` default 권장값 | RFC1918 전체 (`10.0.0.0/8,172.16.0.0/12,192.168.0.0/16`) | 사내 LAN dev/staging 전제. Codex 가 "RFC1918 전체 = 사내 클라이언트 spoof 위험" Major 지적했으나 사용자 명시 결정으로 채택. SECURITY.md §9.7 에 trade-off 명시 |
| malformed env 동작 | prod/staging fail-loud (`RuntimeError`) + dev/test stderr WARNING | Codex 권고 그대로. mode-aware — 운영자 인지 보장 + dev/test fixture/CI 부담 완화 |

#### Phase 분해 (A → E)

- **Phase A** — Caddy XFF 정규화 (feature-0006-lan-proxy-access)
  - `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` 의 `reverse_proxy web:8000` 블록에 `header_up X-Forwarded-For {client_ip}` 추가. Caddy 가 받은 임의 XFF 를 본인이 본 TCP peer IP 로 덮어쓴다. 단일 hop 정규화 → multi-hop / spoof 차단.
- **Phase B** — `_get_client_ip()` 조건부 trust (feature-0003-agent-web-ui)
  - `app.py` 의 imports 에 `ipaddress`, `sys` 추가
  - `_parse_trusted_proxies(raw)` helper: 콤마 분리 + `ipaddress.ip_network(token, strict=False)` 파싱. invalid 토큰은 `AGENT_MODE in {prod, staging}` 에서는 `RuntimeError` startup, dev/test 에서는 stderr WARNING + skip
  - module-level `WEB_TRUSTED_PROXIES = _parse_trusted_proxies(os.getenv("WEB_TRUSTED_PROXIES", ""))`
  - `ENABLE_WEB_TLS_PROXY=1` + `WEB_TRUSTED_PROXIES` empty → prod/staging RuntimeError, dev/test stderr WARNING (PIPA §29 audit 품질 회귀 경고)
  - `_is_trusted_proxy(host)` helper: host 가 `WEB_TRUSTED_PROXIES` CIDR 화이트리스트 안인지 검증
  - `_get_client_ip(request)` 재작성: direct_ip 가 trusted proxy 일 때만 XFF 첫 토큰 사용 + `ipaddress.ip_address(first)` 파싱 실패 시 direct_ip fallback. 그 외 모두 direct_ip 반환
- **Phase C** — `docs/SECURITY.md §9.7` 갱신
  - 기존 "deferred to feature-0006" 마커를 8 bullet (Caddy XFF 정규화 / 조건부 trust / XFF token 검증 / RFC1918 사용자 명시 결정 trade-off / mode-aware fail-loud / proxy mode + empty / schema 호환 / share token 미래 결합) 정책으로 교체
- **Phase D** — docs (양 feature)
  - feature-0003: TASK.md TASK-0087 checkbox close + §2.9 (본 plan), MODIFY CHG-20260520-0010, REVIEW REV-20260520-0010, REPORT §1 cycle entry, TEST §4 8 시나리오, FUNCTION AC-0205~0207
  - feature-0006: TASK.md TASK-0006 신규 entry + Task Queue, MODIFY CHG-20260520-0010 (Caddy XFF 정규화 dual ownership), REVIEW REV-20260520-0010, REPORT §1 entry, TEST §2 Caddyfile validate 시나리오, FUNCTION AC-0004
- **Phase E** — verify-completion + commit + cycle-finalize
  - `bin/verify-completion.sh` 10 checks PASS (특히 #6 ANCHOR + #7 audit endpoint routing + #10 worktree binding)
  - commit + push + PR + main merge + worktree cleanup

#### Test 시나리오 (Codex 권장 8건)

TEST.md §4 에 추가:
1. trusted_proxy + valid XFF → XFF 첫 토큰 반환
2. trusted_proxy + invalid XFF (`garbage`) → direct_ip fallback
3. trusted_proxy + XFF 첫 항목 빈 문자열 → direct_ip fallback
4. untrusted direct_ip + XFF → direct_ip 반환 (spoof 차단)
5. IPv6 direct_ip (trusted) + IPv6 XFF → XFF 첫 토큰
6. invalid env CIDR + `AGENT_MODE=prod` → `RuntimeError` startup
7. empty env + `ENABLE_WEB_TLS_PROXY=1` + `AGENT_MODE=prod` → `RuntimeError` startup
8. `caddy validate` 가 Caddyfile 통과 + `header_up X-Forwarded-For {client_ip}` 인식

#### outside voice 결과 (REVIEW.md REV-20260520-0010 정본)

Codex outside voice (consult mode, model_reasoning_effort=high, 228,107 tokens):
- 6 findings (Major 5 + Minor 1) — Verdict: **NEEDS_REVISION**
- Major 1 (RFC1918 전체 trust 위험): **사용자 명시 거부** — RFC1918 default 유지. trade-off 는 SECURITY.md §9.7 에 명시
- Major 2 (Caddy 문법 부정확) → 흡수: `reverse_proxy` 안의 `trusted_proxies` 대신 `header_up X-Forwarded-For {client_ip}` 로 단일 hop 정규화 (더 안전한 대안)
- Major 3 (Caddy `private_ranges` global trust 위험) → 흡수: global trusted_proxies 추가 안 함 (Major 2 와 동일 결정)
- Major 4 (malformed XFF IP 검증 누락) → 흡수: `ipaddress.ip_address(first)` 검증 후 반환, 실패 시 direct_ip fallback
- Major 5 (malformed env silent skip) → 흡수: mode-aware (prod/staging RuntimeError + dev/test WARNING)
- Minor 1 (silent regression warning) → 흡수: proxy mode + empty env 조합에 RuntimeError + WARNING

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-21 (TASK-0087 Phase A~E 일괄, Major 등급 보안 표면 + multi-feature, Codex outside voice 5 Major + 1 Minor 흡수) -->

---

### 2.1 Implementation Plan (TASK-0072)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Critical 등급 변경 계획이다. **상태**: `approved-after-outside-voice`. 사용자가 2026-05-18 에 Plan 구조 + 권장안 3 항목 (권한·검색 범위·UI 위치) 일괄 승인 → outside voice 3 개 (adversarial / security / ux) dispatch → 종합 후 사용자 추가 결정 3 항목 (UI 위치 재결정·D1·본문 열람 정책) 반영. D1/D2/D3 + 4 must-fix + 3 sub-spec + 6 risk 모두 plan 에 흡수.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-18 (TASK-0072 Phase A0~E 일괄, Critical 등급 PII 표면 신설 + WebAccountActivity DDL 포함) -->

#### 사용자 in-cycle 결정 (5 항목)

| 결정 | 채택안 | 근거 |
|---|---|---|
| 권한 모델 | 기존 `conversation.list.any` 재활용 | 신규 catalog 없이 빠르게 진입. `.own` only 는 본인 대화 내 검색만 |
| 검색 범위 | 제목 + 계정명 + 메시지 본문 | SQL/결과셋은 list 단계 제외 — PII 노출 면적 최소 |
| UI 위치 (재결정) | **Spotlight modal pattern (Cmd/Ctrl+K)** | UX BLOCKER — 252px 사이드바에 chip 4개 fit 불가. 사용자 명시 변형: brand 가 아니라 "+ 새 대화" 영역 우측 같은 높이에 돋보기 icon. modal overlay 로 full search UI |
| D1 본문 search index | **A: LIKE + 강한 안전망** | 한국어 FULLTEXT 는 `ngram` parser + `innodb_ft_min_token_size` 튜닝 필수 → Critical migration. 신규 PII 표면과 interleave 회피. FULLTEXT 는 별 cycle 분리. min 3 char + LIMIT 50 + per-account rate 10/min + max_execution_time 3s |
| 본문 열람 정책 | **`.any` 보유자 = 검색 매칭 + snippet 모두 허용, audit log 수반** | admin/operator 의 감사 needs 우선. `WebAccountActivity` 신설로 PIPA §29 준거 (접근기록 보관) |

#### outside voice 종합 결정 (D2 / D3 — 의견 일치)

| # | 결정 | 근거 |
|---|---|---|
| D2 | **A: snippet 항상 OFF + chip opt-in** | security + adversarial 일치 — `.any` 보유자 기본 ON 시 user interaction 전에 snippet leak. opt-in chip 클릭 자체도 audit log 대상 (의도 추적 가능) |
| D3 | **B: cursor `(updated_at DESC, conversation_id DESC)`** | offset 은 기존 `app.py:2849` LIMIT 200 + `2967-2971` Python re-sort 와 incoherent — page 2 가 stale subset 반환. cursor 가 안전 |

#### adversarial 3 sub-spec (Phase A 진입 차단 → 반영 후 진입)

기존 `_list_conversations` 의 코드 패턴이 search 와 호환되지 않으므로 다음 3 sub-spec 을 Phase A 에서 반드시 동시 적용:

1. **SQL composition order** — `owner_id = self` 가 q / owner_id / product_id 보다 **항상 먼저** AND. `.any` 미보유자 코드패스 에서도 owner_id WHERE 가 q 매칭보다 우선 (q 의 결과가 owner_id 매칭 *교집합* 으로 strict 적용). 응답 byte-equal (404 vs 403 metadata leak 차단).
2. **`hidden_ids` SQL push** — Python post-filter (`app.py:2855-2866`) 폐기, `c.conversation_id NOT IN (…)` 으로 SQL 내 이전. LIMIT 50 과 호환.
3. **Python re-sort 삭제** (`app.py:2967-2971`) — SQL `ORDER BY c.updated_at DESC, c.conversation_id DESC` 단일화. cursor pagination 정합.

#### Must-fix 4 (security + adversarial)

1. **Audit log 신설** — `WebAccountActivity` 테이블 (`id, account_id, action, target_owner_id, query_hash, matched_count, ts`). `.any` 보유자가 본문 search 실행 / snippet chip 활성화 시 INSERT. query 평문 X — SHA-256 hash 만.
2. **SQL escape 명시** — `LIKE %s ESCAPE '!'` 형식. `%`, `_`, `!` 3 문자 escape (default `\\` ESCAPE 의 NO_BACKSLASH_ESCAPES sql_mode 회귀 차단).
3. **Per-account rate limit** — in-process token bucket 10 req/min for body-search requests. `max_execution_time=3000ms` 동시 적용.
4. **본문 검색 min 3 char + length cap 200** — escape 후 의미 literal char ≥ 2 추가 gate (`q="%%"` post-escape 0 char 차단). 한글 grapheme 기준 `len(q.strip())`.

#### Additional risk 6 (adversarial)

1. **`WebAccounts.DeletedAt` 필터 누락** — 현재 `app.py:2842` LEFT JOIN 이 DeletedAt 미체크. 삭제 user 본문 search 시 username verbatim leak. `AND owner.DeletedAt IS NULL` 추가 (또는 `(deleted user)` 명시 렌더).
2. **Collation 일치 audit** — `AgentMemoryMessages.Content` + `AgentCoreMessages.content` 가 `utf8mb4_unicode_ci` 인지 Phase A 시작 시 확인. mismatch 시 풀스캔.
3. **Account-name search `.any` 한정** — `.own` 사용자 q="kim" 의 경우 owner.Username 매칭은 본인 conv 만 (owner_id WHERE 이미 강제). 정상.
4. **`q="%%"` post-escape 0 char 차단** — must-fix #4 와 통합.
5. **404 vs 403 byte-equal response** — must-fix #1 의 SQL composition order + 동일 empty result shape 보장.
6. **`share.js` 회귀 가드** — `share.html` / `share.js` (TASK-0058 Phase D) 가 신규 searchbar/modal 코드 import 안 함. modal element 는 `index.html` 에만 mount.

#### 영향 파일 (최종)

Backend:
- [src/app.py](../src/app.py) — Phase A0 (`WebAccountActivity` 테이블 신설 + `_ensure_web_tables` 추가), Phase A1 (`_list_conversations()` 확장 + 3 sub-spec 적용 + cursor pagination + ESCAPE 절 + min 3 char gate + rate limit + audit insert), Phase A2 (`/api/conversations` query param 수신 + `_log_search_activity` helper + `max_execution_time` SET SESSION).

Frontend:
- [src/static/app.js](../src/static/app.js) — Phase C1 (`state.searchModal: {open, q, owner_id, product_id, date_from, date_to, snippet_opt_in, cursor}` + `openSearchModal()` / `closeSearchModal()` + Cmd/Ctrl+K 단축키 + Esc handler + 300ms 디바운스 + cursor pagination), Phase C2 (`loadConversations()` 가 `search` mode 시 modal 결과 영역에 렌더, sidebar conv-list 는 unchanged).
- [src/static/index.html](../src/static/index.html) — `.sidebar-head` 의 "+ 새 대화" button 우측에 같은 높이 `#openSearchBtn` (돋보기 icon, aria-label="대화 검색 (Ctrl+K)"). `#searchModalOverlay` modal element (input + 4 facet + result list).
- [src/static/styles.css](../src/static/styles.css) — `.sidebar-head` flex 조정 (new + search 2 button row, gap), `.search-modal-overlay` / `.search-modal` / `.search-modal-input` / `.search-modal-facets` / `.search-modal-result-list` / `.search-snippet` / `.search-snippet-hl` / `--search-highlight-bg` 토큰 ~12 개. cache-bust `v=20260518-conv-search`.

문서:
- `docs/FUNCTION.md` — REQ-20260518-0010 + AC 8~10 개 (audit log + RBAC gate + cursor + Cmd/Ctrl+K + Esc 정책 포함).
- `docs/TASK.md` — 본 §2.1 + Task Queue entry + Completion Checklist.
- `docs/MODIFY.md` — Phase 별 CHG entry (6 phase).
- `docs/REVIEW.md` — outside voice 3 개 verdict 요약 + D1~D3 결정 근거 + 사용자 in-cycle 결정 5 항목 + Adversarial 3 sub-spec 흡수 이력 + Must-fix 4 + Additional risk 6 + 본 plan 의 변경 이력.
- `docs/REPORT.md` — Phase 별 변경 요약 + git 동기화 결과.
- `docs/TEST.md` — TEST 케이스 정의 (§2 rewrite) — Phase B 의 4 토큰 cross-account smoke + audit log assert + ESCAPE 절 SQL injection probe + cursor pagination 정합 + min 3 char gate + rate limit 11번째 요청 429.
- 프로젝트 수준: `repo/docs/SECURITY.md` §7 (anonymous endpoint allowlist) 아래 §8 cross-account search policy 신설 + `WebAccountActivity` audit 정책, `repo/docs/STATUS.md` feature-0003 row 갱신.

#### Phase 순서 (최종)

1. **Phase A0 — WebAccountActivity DDL** — `_ensure_web_tables` 에 `CREATE TABLE IF NOT EXISTS WebAccountActivity` 추가 + `_log_search_activity(conn, account_id, action, target_owner_id, query, matched_count)` helper. py_compile + 컨테이너 재시작으로 DDL 적용 확인.
2. **Phase A1 — `_list_conversations` 확장** — 3 sub-spec 적용 (SQL composition order / hidden_ids SQL push / Python re-sort 삭제) + 새 파라미터 `q, owner_id, product_id, date_from, date_to, cursor` + ESCAPE 절 + min 3 char gate + DeletedAt 필터 + collation audit. py_compile.
3. **Phase A2 — `/api/conversations` query param + rate limit** — endpoint 가 query param 수신, body search 시 rate limit 확인 후 `_log_search_activity` 호출. `max_execution_time` SET SESSION. py_compile + HTTP curl smoke.
4. **Phase B — HTTP smoke 6 시나리오** — `tests/test_search_rbac.py` 신설: (1) `.own` only + q=상대 키워드 → 본인 매칭만, (2) `.any` + 동일 q → 전체 매칭, (3) `.own` + owner_id=상대 → response byte-equal with owner_id=999999, (4) cursor 페이지 2 가 페이지 1 과 disjoint, (5) `q="%%"` → 400 reject, (6) rate limit 11번째 → 429.
5. **Phase C — Frontend** — Spotlight modal + 돋보기 icon + Cmd/Ctrl+K + Esc + 300ms 디바운스 + cursor pagination + snippet opt-in chip + a11y (aria-live, focus trap, Tab order). node --check.
6. **Phase D — 문서 + SECURITY policy + STATUS** — FUNCTION / MODIFY / REVIEW / REPORT / TEST 일괄.
7. **Phase E — verify-completion + commit** — `make web` 재배포 + browser smoke (Cmd+K open / q="test" 입력 / Esc close / snippet chip toggle) + `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` + 사용자 명시 commit confirm 후 진행.

#### 위험도 평가 (재평가)

| 영역 | 위험도 | 보강 |
|---|---|---|
| RBAC bypass | Critical | 3 sub-spec 강제 (SQL composition order / hidden_ids SQL push / re-sort 삭제) + Phase B 6 시나리오 smoke + 404/403 byte-equal |
| PII leak (snippet + cross-account body) | Critical | snippet opt-in 기본 OFF + WebAccountActivity audit + SHA-256 hash + `.any` 한정 |
| SQL injection | Major | bound param + `ESCAPE '!'` 명시 + escape 후 의미 char ≥ 2 추가 gate |
| 성능 회귀 (LIKE full scan) | Major | LIMIT 50 + min 3 char + per-account rate 10/min + max_execution_time 3s + collation audit + FULLTEXT 별 cycle |
| 회귀 (기존 `.own` 사용자) | Minor | 빈 query 일 때 기존 동작 100% 유지 (early return) |
| WebAccountActivity DDL | Major | `_ensure_web_tables` idempotent + `CREATE TABLE IF NOT EXISTS` + index `(account_id, ts)` 만 |
| share-link 회귀 | Minor | `share.js` 신규 import 없음 (Phase C 가드) |

**전체 등급**: Critical (PII 표면 신설 + DDL 1 + RBAC scope 확장 효과).

#### 검증 계획

각 Phase 종료 후:
- (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
- (b) `node --check unit/feature-0003-agent-web-ui/src/static/app.js`

전체 완료 후:
- (c) Phase B 의 HTTP smoke 6 시나리오 (`tests/test_search_rbac.py`)
- (d) `make web` — 컨테이너 재배포 + browser smoke (Cmd+K / Esc / snippet toggle / cursor 페이지 / 0 match empty state)
- (e) `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui`

#### outside voice 결과 요약 (REVIEW.md 정본)

3 review verdict:
- **Security**: FIX-FIRST → 4 must-fix (audit log / ESCAPE / FULLTEXT or LIKE 안전망 / rate limit) 흡수
- **Adversarial**: Blocker (3 sub-spec) + D1 A + D2 A + D3 B + 6 risk → 모두 흡수
- **UX**: NEEDS-TWEAK (사이드바 fit 불가) → Spotlight modal 패턴으로 UI 위치 재결정 → 사용자 변형 채택 ("+ 새 대화" 우측 돋보기 icon)

REVIEW.md REV-20260518-0010 에 각 review 의 전체 verdict + plan 흡수 이력 + 결정 근거 기록.

---

### 2.1 Implementation Plan (TASK-0061)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Major 등급 변경 계획이다. **상태**: `approved`. 사용자가 2026-05-15 에 Phase 1~8 일괄 승인 + 비밀번호 초기화 권장안 (MustChangePassword + 임시비번 1회 표시 + 세션 revoke + self-reset 금지) 채택을 명시했다. 사용자의 명료화: "관리자 계정의 비밀번호 초기화가 아닌, 관리자 주관으로 특정 계정의 비밀번호를 초기화 하는 기능" — AC-0093 (self-reset 거부) 의도와 정합.

<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-15 (TASK-0061 Phase 1~8 일괄, Phase 6 Critical 분면 포함) -->

#### 영향 파일 요약

Backend:
- [src/app.py](../src/app.py) — Phase 3 (`_compute_display_status` + WEB_PROGRESS_STALE_TIMEOUT_SECONDS env + `/api/progress` / `/api/ask_status` / `/api/ask_result` / `_list_conversations` 일관 반영), Phase 5 (`/api/history_dates` 가 `AgentMemoryMessages` 기준으로 SELECT 변경), Phase 6 (`WebAccounts.MustChangePassword` ALTER + `_ensure_web_tables` / `_ensure_seed_catchup` idempotent helper + `POST /api/admin/accounts/{account_id}/password-reset` endpoint + `/api/auth/login` 응답에 `must_change_password` 추가 + `/api/auth/me` PATCH 가 비밀번호 변경 성공 시 `MustChangePassword=0`), Phase 8 (`_delete_conversation_impl` helper 추출 + `POST /api/delete_conversations` endpoint).

Frontend:
- [src/static/app.js](../src/static/app.js) — Phase 1 (`state.pendingBubble` + `renderPendingAssistantBubble()` + `applyProgressPayload()` 가 pending bubble 동시 갱신 + elapsed timer interval + `renderMessages()` 가 pending state 가 있으면 사용자 message + pending bubble 즉시 prepend), Phase 2 (`sendPrompt()` lazy-create 분기에서 pending bubble 진입 + `/api/ask` 응답 직후 polling start), Phase 3 (`renderConversationList()` 가 `display_status === "stale_error"` 시 `.is-stale-error` dot 사용 + tooltip), Phase 4 (`#messagePointRail` 컨테이너 + `renderMessagePointRail()` + scroll/click handler), Phase 5 (`historyCalendarBtn` + popover + `/api/history_dates` 호출 + `/api/history_anchor` jump), Phase 6 (`/api/auth/login` 응답에서 `must_change_password` 처리 — 강제 modal), Phase 8 (`state.conversationSelected: Set<string>` + `state.conversationLastClickIdx` + `conv-item-checkbox` 추가 + Ctrl/Shift click handler + `.conv-bulk-bar`).
- [src/static/admin.js](../src/static/admin.js) — Phase 6 (Account detail 에 `adminPasswordResetBtn` + modal 표시 + 임시 비밀번호 복사 액션), Phase 7 (accountSelectAll change handler 가 `filteredAccounts()` 의 `accountPage` slice 만 대상으로 변경 + `updateAccountSelectAllCheckbox()` 도 동일 helper 사용 + Roles/Products select-all 도 동일 정책 정합화).
- [src/static/index.html](../src/static/index.html) — Phase 4 (`#messagePointRail` 컨테이너), Phase 5 (`historyCalendarBtn` + popover container), 그 외 ID 추가.
- [src/static/admin.html](../src/static/admin.html) — Phase 6 (Account detail 의 `adminPasswordResetBtn` slot — `renderAccountDetail()` 에서 동적 mount 도 가능하지만 cache-bust 위치 정의).
- [src/static/styles.css](../src/static/styles.css) — Phase 1 (`.message.is-pending` + spinner + elapsed + step list 토큰), Phase 3 (`.conv-dot.is-stale-error` red 토큰), Phase 4 (`.message-point-rail` + `.message-point-dot`), Phase 5 (`.history-calendar-popover` + grid), Phase 6 (`.admin-password-reset-modal` + `.temp-password-display`), Phase 8 (`.conv-item-checkbox` + `.conv-bulk-bar`).

문서:
- `docs/FUNCTION.md` — 본 commit 에 REQ-20260515-0003 ~ 0010 + AC-0070 ~ AC-0107 이미 추가됨.
- `docs/TASK.md` — 본 §2.1 + Task Queue entry + Completion Checklist.
- `docs/MODIFY.md` — Phase 별 CHG entry (8 phase).
- `docs/REVIEW.md` — Phase 1 (호환 차원에서 `#progressCard` 유지 결정), Phase 3 (env 기본값 20 분 결정 근거 — 장시간 SQL/LLM 작업 고려), Phase 6 (1 회 표시 / 평문 저장 금지 / MustChangePassword 강제 / 세션 revoke / self-reset 금지 보안 정책 결정), Phase 7 (bulk delete partial success + ≥10 typed-confirm 결정), Phase 8 (bulk delete partial success 채택, rollback 미선택 사유).
- `docs/REPORT.md` — Phase 별 변경 요약 + git 동기화 결과 (§16.5 Step 6).
- `docs/TEST.md` — TEST 케이스 정의 (§2) rewrite + 실행 결과 (§3) append.
- 프로젝트 수준: `repo/.env.example` — `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` 추가, `repo/docs/STATUS.md` feature-0003 row 갱신, `repo/docs/SECURITY.md` 비밀번호 초기화 정책 1 줄 추가.

#### 접근 방법 (Phase 순서)

순서는 의존성 최소화 + 빠른 검증 가능성 기준으로 정렬했다. 각 Phase 끝마다 python compile + node --check 가능하도록 분할.

1. **Phase 3 (backend stale 감지) 먼저** — 가장 자족적인 backend 변경. helper + env 추가 + 3 endpoint 응답 + conversation list status. 검증: `/api/progress` HTTP 응답에 stale 가 정확히 들어가는지.
2. **Phase 1 (답변 버블 live progress)** — frontend 핵심. `state.pendingBubble` 자료구조 + render + applyProgressPayload 갱신 + elapsed timer + `renderMessages()` 분기. Phase 3 의 status 가 stale 일 때 pending bubble 에서도 오류 영역 노출.
3. **Phase 2 (신규 대화 첫 polling)** — Phase 1 의존. lazy-create 분기에서 pending bubble 진입 + `/api/ask` 응답 직후 polling start. 회귀: 기존 대화 ask 흐름은 변경 없음.
4. **Phase 4 (Point rail)** — Phase 1 의 message rendering 위에 build. scroll observer + click handler.
5. **Phase 5 (캘린더)** — Phase 4 와 무관. backend `/api/history_dates` 의 source table 변경 + frontend popover. timezone 은 server 의 DATE() 그대로 (UTC).
6. **Phase 7 (admin select-all fix)** — 자족적인 frontend bug fix. 그 다음 Phase 6 (Critical) 직전에 끊어서 사용자 confirm 요청.
7. **Phase 8 (bulk delete)** — backend helper + endpoint + frontend selection state + UI. 단건 endpoint 와 동일 가드 재사용.
8. **🛑 Phase 6 (비밀번호 초기화 — Critical confirm) 직전 STOP** — DB schema 변경 (`MustChangePassword`) + 인증 응답 contract 변경 + 임시 비밀번호 노출. 사용자 명시 confirm 받은 후 Execute.

#### 위험도 평가 (§12.3)

| Phase | 변경 영역 | 위험도 | 사전 승인 |
|------|-----------|--------|----------|
| Phase 1 | frontend UI 상태 추가 | Minor | plan-review 만 |
| Phase 2 | frontend lazy-create UX | Minor | plan-review 만 |
| Phase 3 | backend status helper + env | Major (운영 환경변수 + 표시 정책) | plan-review |
| Phase 4 | frontend UI 추가 | Minor | plan-review 만 |
| Phase 5 | backend SELECT source 변경 | Minor | plan-review (회귀 가능성) |
| Phase 6 | **인증 모델 + 비밀번호 + 세션 revoke** | **Critical** | **사용자 명시 confirm** |
| Phase 7 | frontend bug fix | Minor | plan-review 만 |
| Phase 8 | **파괴적 데이터 일괄 삭제 + 신규 endpoint** | **Major** | plan-review (cross-account leak 위험 없음 — owner 가드 보존) |

**전체 등급**: Major (Phase 1~5, 7, 8 은 plan-review 마커 부여로 Execute. Phase 6 는 별도 Critical confirm).

#### 검증 계획

각 Phase 종료 후:
- (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
- (b) `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
- (c) `node --check unit/feature-0003-agent-web-ui/src/static/admin.js`

전체 완료 후:
- (d) `make web` — 컨테이너 재배포
- (e) browser 검증 (gstack `/browse` 또는 make browser-*) — 8 시나리오 (GOAL.md §5 필수 브라우저 확인 8 항목) 실측 + screenshot 첨부.
- (f) `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui`

#### 미결정 사항의 결정 (GOAL.md §7)

| 항목 | 결정 | 사유 |
|------|------|------|
| 비밀번호 초기화: MustChangePassword vs 임시비번+revoke only | **MustChangePassword 채택** | GOAL.md 권장 + 보안 우위. 1 회 임시 비밀번호 + 세션 revoke + 다음 로그인 시 강제 변경 |
| `#progressCard` 유지 vs 축소 | **유지** | 호환성. 사용자별 collapsed 상태는 localStorage 보존 |
| bulk delete partial vs rollback | **partial success + 결과 요약** | admin bulk UX 일관성 (AC-0035 와 정합) |
| stale 만료시간 기본값 | **1200 sec (20 분)** | 장시간 SQL/LLM 작업 고려한 보수적 기본값. env 로 override 가능 |

#### 사용자 승인 마커

Phase 1~5, 7, 8 (Major) 진행 승인 시 본 plan 의 PLAN-APPROVED 마커는 §2 Task Queue 의 기존 마커를 재사용한다 (사용자가 이미 GOAL.md 의 진행 의도를 명시함). Phase 6 (Critical) 진입 직전 별도 마커:
```md
<!-- PLAN-APPROVED-PHASE-6 by <user> on YYYY-MM-DD -->
```

### 2.1 Implementation Plan (TASK-0060)

영향 파일 / 데이터:
- `agent_memory.WebSystemPrompts` — Product prompt 2건, Role 공통 prompt 5건 upsert
- `../feature-0002-agent-core/src/agent_core.py` — Role 공통 prompt 누적 적용
- `../feature-0002-agent-core/tests/test_compose_system_prompt.py` — 누적 적용 회귀 테스트
- `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md` 및 feature-0002 문서

접근 방법:
1. `WebProducts`와 `WebProductDatabases`에서 Product별 접근 DB 목록을 확인한다.
2. 각 접근 DB에 대해 `information_schema.TABLES/COLUMNS`와 제한적 집계 쿼리로 테이블 수, 주요 테이블, 시간 범위, 민감 컬럼 성격을 확인한다.
3. 확인한 사실만 Product scope 시스템 프롬프트에 반영한다. 비밀번호/토큰/기기 식별자 등 민감 컬럼은 원문 노출 금지 지침으로 명시한다.
4. Role `pending/operator/admin/sales/dba`의 `ProductId IS NULL` prompt 를 역할명에 맞게 작성한다.
5. runtime 조립은 feature-0002에서 `전 Product 공통` Role prompt 누적 방식으로 수정하고 테스트한다.

위험도: Minor — 비파괴 데이터 upsert + LLM 입력 패키징 수정. 인증/인가 catalog, DB schema, 삭제/파괴 작업 없음.

### 2.1 Implementation Plan (TASK-0059)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Major 등급 변경 계획이다. 사용자 승인 (2026-05-15) 으로 진행.

**영향 파일**:
- [src/static/app.js](../src/static/app.js) — `sendPrompt()` askBody 에 `lazy_create` hint (lazy 경로 한정), `loadConversations()` 의 active id 덮어쓰기에 pending 가드
- [src/app.py](../src/app.py) — `_resolve_conversation_for_account` 시그니처에 `force_new=False` kwarg 추가, `/api/ask` 의 빈 `request_conversation_id` 경로가 `lazy_create` body hint 를 `force_new=True` 로 위임

**접근 방법**:
1. Frontend `sendPrompt()` 의 askBody 구성 시 `isLazyCreate` 일 때만 `lazy_create: true` 를 추가 (기존 대화 ask 에는 추가 안 함 — 의미 변경 0).
2. Frontend `loadConversations()` 가 `state.pendingNewConversation` true 일 때는 `state.activeConversationId` 를 덮어쓰지 않음 — 사이드바 리스트와 backend `current` 는 갱신하되 active id 보존.
3. Backend `_resolve_conversation_for_account` 에 `force_new=False` kwarg 추가. requested_id 가 truthy 이면 기존 동작 (force_new 무시), 빈 문자열이면 `_repair_current_conversation(..., force_new=force_new)` 로 위임. `_repair_current_conversation` 은 기존에 `force_new=True` 시 visible fallback 차단 + 새 cid 생성 로직을 이미 가짐 — body 변경 없음.
4. `/api/ask` 의 빈 `request_conversation_id` 경로에서 `lazy_create_requested = bool(data.get("lazy_create"))` 추출 후 `_resolve_conversation_for_account(..., create_if_missing=True, force_new=lazy_create_requested)` 호출. hint 없는 legacy client (예: 첫 로그인 후 직전 대화 자동 이어받기 흐름) 는 force_new=False → 기존 동작 유지.

**위험도**: **Major** §12.3 — 사용자 대화 routing 데이터 영역. 인증/인가 catalog·endpoint guard·owner check 무변경. `_account_can_access_conversation` / `_conversation_owned_by_account` 검사는 기존 그대로 유지되며 force_new 경로는 새 cid 를 생성하므로 owner 가 즉시 본 계정으로 assign 됨 (`_assign_conversation_owner(force=True)`). cross-account leak 가능성 없음.

**검증**:
- (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
- (b) `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
- (c) `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui`

- [x] TASK-0058 (REQ-20260514-0001, **Critical** §12.3 — 인증/인가·개인정보·외부 공개 범위 변경) 대화 공유 링크 기능 도입. anonymous 접근 가능한 read-only view + 로그인 viewer 의 fork. 사용자 결정 6 항목 (외부 anonymous 허용 / 무기한 + revoke / read+fork / full+anchored / `conversation.share.create` 신설 / 메시지+SQL+결과셋 노출) 와 codex outside voice review 의 blindspot 보강 (B1 메시지 테이블 이중성 — AnchorMessageId 는 `AgentMemoryMessages.Id` 기준 inclusive `Id <= anchor`, B2 `_optional_account` 헬퍼 신설, R4 `_fork_conversation_impl` 추출로 share-grant 가 read-gate 우회, R6 revoke+view race-free 단일 UPDATE, R7 file attachment 자동 hide, R8 token 충돌 retry, R10 share.html FileResponse mount) 반영. **Phase A**: `PERMISSION_DEFINITIONS` 에 `conversation.share.create` 추가 (catalog 33→34, group=conversation), `SEED_ROLE_DEFINITIONS` operator/sales 에 grant + admin 보정 list 에 추가, `WebConversationShares` 테이블 신설, `_ensure_web_conversation_shares_schema(conn)` helper 가 slow path + fast path 양쪽 idempotent 호출, fast path catchup 에 `_ensure_permission_catalog(conn)` 추가로 신규 권한 hydrate. **Phase B**: `_optional_account` + `_fork_conversation_impl` 헬퍼 + 5 endpoint (POST/GET share[s], DELETE share, GET/POST public/share/{token}[/fork]). Token = `secrets.token_urlsafe(32)`. `/share/{token}` FileResponse route. **Phase C**: 헤더 `shareConversationBtn` (gated by `conversation.share.create`) + 메시지 hover "여기까지 공유" + `createConversationShare` 함수 (clipboard copy + toast). 권한 label/description 매핑 추가 → CONVENTIONS.md §10.6 conversation section 에 자동 합류. **Phase D**: `share.html` / `share.css` / `share.js` 신규 정적 파일 — anonymous accessible read-only view (메시지 + SQL `<pre>` + 결과셋 `<table>`), 로그인 + can_fork 시 "내 계정에서 fork" 버튼. **Phase E**: 본 entry + FUNCTION.md REQ-20260514-0001 (AC-0053~AC-0060), MODIFY.md / REVIEW.md, project-level [`docs/SECURITY.md`](../../../docs/SECURITY.md) 에 anonymous endpoint 2 곳 명시 + 외부 배포 시 IP 제한/비밀번호 보호 후속 cycle 권장, STATUS.md feature-0003 row 갱신.

### 2.1 Implementation Plan (TASK-0058)

영향 파일:
- `unit/feature-0003-agent-web-ui/src/app.py` (RBAC catalog + 부트스트랩 schema helpers + 5 endpoint + helper refactor)
- `unit/feature-0003-agent-web-ui/src/static/app.js` (헤더 share 버튼 + 메시지 hover share + `createConversationShare` + 권한 매핑)
- `unit/feature-0003-agent-web-ui/src/static/index.html` (헤더 share 버튼 1줄)
- `unit/feature-0003-agent-web-ui/src/static/share.html` / `share.css` / `share.js` (신규 anonymous view)
- `unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW}.md` + `docs/{STATUS,SECURITY}.md`

접근 방법: A=infra/RBAC catalog, B=Backend 5 endpoint + helper refactor, C=Frontend logged-in, D=Anonymous view, E=Docs. Phase 별 비파괴 추가이므로 각자 verify 가능. Token = 256-bit URL-safe, UNIQUE 충돌 retry loop. revoke + view 카운터는 동일 UPDATE 로 race-free.

위험도 평가: **Critical** §12.3 — 인증/인가 catalog 확장 + anonymous public endpoint 2 곳 신설 + SQL 결과셋 외부 노출. SECURITY.md §3 의 3 항목 동시 변경. 사용자가 사내 IP 가정으로 anonymous 허용 결정. 외부 배포 전 IP 제한/비밀번호 보호 후속 cycle 필요.

- [x] TASK-0056 (REQ-20260512-0002, **Major** §12.3 — frontend 권한 정렬 + project-level 컨벤션 1 절) 작업 화면·관리 콘솔 권한 정렬을 화면 맥락별로 분리. 두 화면이 같은 `console→account→role→conversation→[product]→misc` 순서를 공유해 admin 메타권한이 두 곳 모두 위에 노출되던 UX 회귀 fix. (1) [docs/CONVENTIONS.md §10.6](../../../docs/CONVENTIONS.md) 화면별 권한 섹션·정렬 정책 신설 — 작업 화면 = "운영→관리→기타", 관리 콘솔 = "관리→운영→기타" 2단 section. (2) **admin.js**: `ADMIN_PERMISSION_SECTIONS` 상수 + `sectionedGroupedPermissions` 함수 + `renderPermissionGrid` 가 outer section header (`.permission-section`) 로 inner group `<details>` 들을 감싸도록 수정. (3) **app.js**: `PERMISSION_GROUP_ORDER` 에 `product` 추가 (누락 fix), `PERMISSION_GROUP_LABELS.product`, `WORK_SCREEN_PERMISSION_SECTIONS` 상수, `permissionGroupOf()` 가 `system_prompt.` 를 product 로 매핑, `PERMISSION_LABELS/_DESCRIPTIONS` 에 `product.manage` / `system_prompt.manage.role.any` 추가, `buildPermissionPills` 가 2단 묶음 (`.perm-section-meta`) 으로 렌더 + 빈 section 자동 hide. (4) **styles.css**: `.perm-section-meta*` 5 클래스 + `.permission-section*` 5 클래스 + section 간 gap 중첩 제거. (5) cache-bust `v=20260512-perm-sections`. DB schema / backend RBAC catalog / endpoint guard / system prompt assembly 변경 0 — 인가 모델 무영향. node --check 양 파일 통과.
- [x] TASK-0055 (REQ-20260512-0001, **Major** §12.3 — admin console UI 정합 컨벤션 정립 + 코드 통일, 사용자 명시 AI 자율 commit/push) 관리 콘솔 카테고리별 다중선택 UX 정합 컨벤션 도입. 사용자 보고: "계정=우상단 / 역할=좌하단 / 제품=다중선택 부재" 의 카테고리 간 일관성 결여. 본 cycle = **정책 + gstack design 외부 시각 + Core+keyboard+advanced 코드 통일 합본**. (1) [docs/CONVENTIONS.md §10](../../../docs/CONVENTIONS.md) 프로젝트 수준 정책 신설 — 다중선택 적용 룰, DOM anchor 표준, 자료구조 invariant, 단위 어휘, 신규 카테고리 체크리스트. (2) [DESIGN.md](./DESIGN.md) 신규 — feature-local 상세 명세 (HTML 구조, CSS 토큰, Set/invariant, runtime assertion, §5 컴포넌트 set, §6 cross-page banner, §7 typed-confirm, §8 RBAC partial-fail UI, §9 keyboard map, §10 a11y, §11 렌더 cycle, §12 Products 마이그레이션). (3) **admin.html / styles.css / admin.js 코드 통일**: Accounts bulk bar 헤더 우상단 → list 직하단 sticky 이전 (DOM anchor 표준), Products multi-select 신설 (`productSelected: Set<number>`, row checkbox, select-all, bulk bar, cross-page banner), keyboard 단축키 (shift-click range + Esc 선택 해제), cross-page banner (Stripe pattern), confirm typed-confirmation (≥10 건 danger), RBAC partial-fail toast (skipped count chip), runtime assertion (`assertBulkBarContract`), a11y 강화 (`role="toolbar"`, `aria-live="polite"`, `role="grid"`, `aria-multiselectable`, checkbox `aria-label`). 외부 design 시각 (general-purpose subagent + worker-design 차용 framework) 으로 v0.1 → v0.2 흡수 (5 gap + a11y + token + keyboard map + 모던 레퍼런스 거부 근거).
- [x] TASK-0054 (REQ-20260508-0001) PR 흐름으로 main 동기화 — feat/adopt-external-anchor-v3.2.0-rc → main (PR #2, merge `eafe4c2`, 72 commits, conflict 10 files §3.2/§16.6 자율 해결) + issue/1-github-bootstrap → main (PR #3, merge `3fd4272`, self-hosted runner + 로컬 claude CLI 전환). 머지 후 main 의 ai-* 워크플로 self-hosted 정렬 확인.
- [x] TASK-0053 (REQ-20260506-0006, **Major** §12.3 — UX + 정책 토글, AI 자율 commit/push) 신규 제품 default 정책 토글 + 권한 grid 의 product sub-catalog + Role/Account detail 의 product-카드 통합 — TASK-0052 완료 직후 사용자 follow-up. **Phase A** (사용자 in-cycle 설계 전환 2026-05-06: 정책 주체 Role → Product): `WebProducts.DefaultRoleAccess TINYINT(1) NOT NULL DEFAULT 1` 컬럼 신설 (이전 시도였던 `WebRoles.DefaultProductAccess` 는 deprecated). POST/PATCH `/api/admin/products` 가 `default_role_access` body 수용, true=모든 role 자동 grant, false=명시 grant 만. admin UI 토글은 Product detail 에 위치 — Role detail 에서는 제거. **Phase B**: admin.js 의 권한 grid 가 `groupedPermissions({excludeDynamic: true})` 로 dynamic `product.access.*` 를 grid 에서 분리, 정적 `product.manage` 등만 남기고 동적은 product subcatalog 카드로 이전. **Phase C**: Role detail 의 system prompt editor 가 product 별 collapsible card list 로 재구성 — 각 카드에 access 토글 + role-scope prompt textarea + 마지막에 "전 Product 공통" generic card. Account detail 에는 product 별 override (allow/deny/inherit) flat card list.
- [x] TASK-0052 (REQ-20260506-0005, **Critical** 등급 §12.3 — 인증/인가 구조 변경) 계정·역할 → 제품 권한 상속/override 모델 도입 — TASK-0051 분리분 C5. `/plan-eng-review` + Codex outside voice 통합 plan 은 [BRIEFING-c5-permission-product-access.md](./BRIEFING-c5-permission-product-access.md). **Phase 1A** (RBAC engine catalog 인자화 — commit 4dd1d0a) → **Phase 1B** (catalog DB-driven + product 권한 backfill + 명시적 트랜잭션 + caller-update — 본 cycle) → **Phase 1C** (G1-G8 8 endpoint guards + admin_update_account RoleId 보존 pre-existing 버그 fix) → **Phase 1D** (admin UI PERMISSION_GROUP_ORDER 'product' 그룹 추가) → **Phase 2** (HTTP smoke 6/6 P0 직접 검증 + lifecycle T13/T16 + cascade 검증). 사용자 명시 AI 자율 commit/push 권한 (2026-05-06).
- [x] TASK-0051 (REQ-20260506-0004) 관리 콘솔 일괄 저장 정책 회복 + 메타데이터 4 스키마 항상 노출 + DB 목록 라이브 enum — `프롬프트 저장` / `제품 정보 저장` / `DB 목록 저장` 3 버튼 제거 후 footer `모두 적용` 단일 commit 흐름으로 통합, 메타데이터 4 종(`information_schema`/`mysql`/`sys`/`performance_schema`) 을 회색 disabled chip 으로 강제 노출(REV-20260422-0006 정책 시각화), 자유 텍스트 chip 입력을 `GET /api/admin/databases/available` 라이브 enum 기반 picker 로 교체. C5 (제품 권한 상속/override) 는 다음 cycle 로 분리(plan-eng-review 후 진행).
- [x] TASK-0050 (REQ-20260506-0003) `make web` 의 docker compose v5.1.1 + buildx v0.31.1 provenance metadata file race 우회 — Makefile 에 `dc-build SERVICE=...` reusable 가드 타깃 추가, `web` 타깃을 `dc-build SERVICE=web` + `up -d --no-build web` 로 분리. race 한정 무시 (image 빌드 OK + 로그에 `compose-build-metadataFile` 포함 시에만 EXIT=0 정규화).
- [x] TASK-0049 (REQ-20260506-0002) 누적된 빈 대화 일괄 정리 — `bin/cleanup-empty-conversations.sh` (dry-run 기본 + `--execute`, processing 보호 + 최근 N분 보호 + owner-account 옵션) 추가, 운영 데이터에 1회 적용 (88 → 46 conversations, 42개 정리).
- [x] TASK-0048 (REQ-20260506-0001) "새 대화" 생성 시점 lazy 화 — 버튼 클릭 시 client-side pending state 만 표시하고, 첫 메시지 전송 시 `/api/ask` 의 lazy creation path 가 실제 row 를 만들도록 전환. 신규 빈 대화 누적 방지. **CHG-20260506-0024 후속 fix**: backend `_repair_current_conversation` 의 `create_if_missing=_account_has_permission(...)` 자동 생성 분기 5 곳 (`_build_conversations_payload`, `/api/session`, `/api/history`, `/api/delete_conversation` 의 pending/일반 두 케이스) 을 모두 비활성화. 사용자 보고 회귀 "대화 삭제 시 새 대화가 그대로 남는 이슈" 의 근본 원인을 fix — delete 응답 `current` 가 backend 에서 자동 생성된 새 cid 였던 것을 빈 문자열로 정정.
- [x] TASK-0047 Product Selector + Auto 모드 진입 UX (사이드바 chip, `product_mode` 컬럼, `PATCH /api/conversations/{cid}/product`, "상품"→"제품" 일괄 치환) — agent team 4 + Codex CLI 교차검증 합의안
- [x] TASK-0046 API Vault 패널 Linear Wizard 재설계 + 단일 진입점 destructive (REQ-20260425-0001)
- [x] TASK-0045 ANCHOR.md §1-§3 작성 (template v3.2.0-rc.1 external anchor 도입)
- [x] TASK-0044 사업팀(Sales) role + role-scope system prompt + 복제 DB 접속 envelope + Product whitelist 사업팀 접근 runbook — Approach A wedge pilot infrastructure
- [x] TASK-0041 클라이언트 타임아웃 시 대화 지속(Attach/Resume) — `/api/ask_status` + `/api/ask_result` long-poll + 브라우저 UX 다이얼로그 + runner attach 분기
- [x] TASK-0040 schema whitelist 정규식 context-aware 수정 (TASK-0036 회귀 — alias.column 오탐으로 합법 SQL 이 차단되는 블로커 제거)
- [ ] TASK-0034 복잡 QA 성능 테스트 (local LLM 5 직렬 + 상용 API gpt-5.4-mini 5 병렬, 최대 20턴, 실제 DB 결과 대조 검증)
- [x] TASK-0039 메타데이터 스키마(sys/mysql/information_schema/performance_schema) Product whitelist bypass 정책 도입
- [x] TASK-0038 agent_core OpenAI 호출 무제한 대기 방지 + test runner/서버 타임아웃 정렬 (TASK-0034 Q4/Q5 실패 원인 1+2 대응)
- [x] TASK-0037 진행 상황 폴링 루프 중복/축적 방지 리팩터 리뷰 및 문서화 (TASK-0036 부수 변경)
- [x] TASK-0036 시스템 프롬프트 Depth (Product/Role/Account) + Product 단위 DB 접근 관리
- [x] TASK-0035 대화 탭 내 계정 구분 하이라이트/정렬 + 대화/말풍선 fork 기능
- [x] TASK-0033 결과셋 말풍선 단일 스크롤 + RowCount + 첫 행/열 freeze
- [x] TASK-0032 권한 안내 UX (툴팁 서술화 + 차단 시 필요 권한 안내)
- [x] TASK-0001 Web UI 코드 이관
- [x] TASK-0002 정적 자산 이관
- [x] TASK-0003 agent 이미지 복사 경로 반영
- [x] TASK-0004 엄격한 Web UI 검증 시나리오 정의
- [x] TASK-0005 모던 UI/UX 전면 리디자인
- [x] TASK-0006 기존 사용자 식별 UI 추가
- [x] TASK-0007 키워드 학습 구조 추가
- [x] TASK-0008 로그인 버튼 브라우저 호환성 버그 수정
- [x] TASK-0009 작업 중심 콘솔 UI 재개편
- [x] TASK-0010 계정/비밀번호 기반 인증 모델 도입
- [x] TASK-0011 pending/operator/admin 권한 체계와 관리자 화면 도입
- [x] TASK-0012 대화 소유권을 계정 기준으로 전환
- [x] TASK-0013 상단 상태/키워드 관리/시간 이동 등 불필요한 UI 제거
- [x] TASK-0014 로컬 LLM false-ready 방지
- [x] TASK-0015 성공 사례 기반 UI/UX 전면 개편 (App-Shell 레이아웃)
- [x] TASK-0016 AI 작업자용 UI/UX 정책 지침 문서화
- [x] TASK-0017 프로필 드로어, 병렬 대화 지원, Admin 콘솔 개편
- [x] TASK-0018 프로필 드로어 탭 구조화, API Vault 통합, 버그 수정, 탑바 정리
- [x] TASK-0019 로컬 LLM 런타임 복구 및 alias 모델 준비
- [x] TASK-0020 내장 Local LLM 제거 및 외부 provider 참조 전환
- [x] TASK-0021 쿼리 결과셋 인라인 표시 복원
- [x] TASK-0022 Progress Strip 드롭다운 구조화 (단계 누적에 따른 채팅 영역 축소 해소)
- [x] TASK-0023 Planner 자율성 개선 (휴리스틱 없이 불필요 탐색 축소)
- [x] TASK-0024 Role/권한 구조를 RBAC + account override 모델로 재설계
- [x] TASK-0025 SQL 결과셋 Navigator(말풍선 내 스텝 탐색) 도입
- [x] TASK-0026 긴 SQL 쿼리 수평 확장 방지 (SQL 포매팅 + wrap)
- [x] TASK-0027 RBAC 세분화 반영 — Profile 권한 그룹화 + 관리 콘솔 UX 재설계
- [x] TASK-0028 Insight 시스템 및 agent-core 내부 설계 문서화
- [x] TASK-0029 관리 콘솔 재구조화 (탭 + 마스터-디테일 + 일괄 commit)
- [x] TASK-0030 assistant 말풍선 고정 폭 + 결과셋 내부 스크롤 + 펼침 스크롤 앵커
- [x] TASK-0031 관리 콘솔 내부 스크롤 정리 (페이지네이션·액션 버튼 상시 노출)

## 2.1 Implementation Plan (TASK-0052)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute + §12.3 Critical 등급 (인증/인가 구조 변경) 변경 계획이다. `/plan-eng-review` (Section 1~4) + Codex outside voice (gpt-5.5, reasoning=high) 통합 후 사용자 승인 (2026-05-06) 으로 진행. 4 phase 분할 → **본 turn 은 Phase 1A 만**.

<!-- PLAN-APPROVED by user on 2026-05-06 -->

전체 plan: [BRIEFING-c5-permission-product-access.md](./BRIEFING-c5-permission-product-access.md). 본 §2.1 은 그 briefing 의 Phase 1A 슬라이스만 record.

### Phase 1A — RBAC engine catalog 인자화 (본 turn)

**목표**: Codex Claim 1 이 지적한 정적 PERMISSION_CODES 가정 (5 hot path hardwired) 을 catalog 인자 받는 형태로 refactor. **동작 변경 0**, deploy 안전성 극대화.

**영향 파일**:
- [src/app.py](../src/app.py) — `Iterable` import 추가, `_resolve_permission_catalog(conn=None)` 헬퍼 신설, 5 함수 (`_empty_permission_map`, `_apply_permission_overrides`, `_validate_permission_codes`, `_normalize_override_payload`, `_permission_catalog_payload`) 시그니처 확장 (catalog_codes/catalog_map/catalog kwarg 추가, 기본값 None = 정적 PERMISSION_CODES 사용 → 기존 동작 유지). `/api/admin/permissions` 엔드포인트가 plumbing 검증 경로 (`_resolve_permission_catalog(conn) → _permission_catalog_payload(catalog=...)`) 를 거치도록 단일 위치 전환.

**접근 방법**:
1. `_resolve_permission_catalog(conn=None)` 추가 — Phase 1A 시점은 정적 `(PERMISSION_DEFINITIONS, PERMISSION_CODES, PERMISSION_DEFINITION_MAP)` 그대로 반환. Phase 1B 가 conn 으로 WebPermissions union 하도록 body 만 교체.
2. 5 함수의 시그니처에 `*` 강제 keyword + catalog 인자 추가. `None` 이면 기존 정적 사용 (모든 기존 callsite 가 None 인자로 호출되어 회귀 0).
3. `/api/admin/permissions` 1 곳만 새 plumbing 으로 전환 — 정적 결과와 동일함을 HTTP smoke 로 검증.
4. 다른 callsite (account list, role detail 의 `_apply_permission_overrides` 등) 는 Phase 1B 에서 동적 catalog 도입 시 caller-update.

**위험도**: Low — 모든 기본값이 backward-compat. 단일 deploy.

**검증 (완료)**:
- (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과
- (b) `make web` 컨테이너 재배포 성공 (`repo-web-1 Recreated/Started`)
- (c) 컨테이너 in-place 코드 검사: `_resolve_permission_catalog` / `catalog_codes` 키워드 17 hits — 신규 헬퍼 deploy 확인
- (d) bootstrap_admin 로그인 + `/api/admin/permissions` HTTP 200 + 33 codes 정상 (이전 catalog 와 동일)

**Phase 1A 종료 후 후속 phase (별 cycle)**:
- Phase 1B: WebPermissions IsDynamic/ProductId 컬럼 추가 + product 권한 backfill SQL + `_resolve_permission_catalog(conn)` body 를 DB query 로 교체 + 다른 callsite caller-update
- Phase 1C: 8 endpoint guard 도입 (G1-G8 — briefing §3.4)
- Phase 1D: admin UI PERMISSION_GROUP_ORDER 'product' 추가
- Phase 2: 운영 검증

## 2.1.archived Implementation Plan (TASK-0051)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute 프로토콜에 따른 **Major** 등급 변경 계획이다. 사용자가 2026-05-06 직접 진행 지시(§3.1 우선순위 1) + `[A → B → C → D]` 범위 한정으로 인계됐다. C5 (제품 권한 상속/override) 는 분리되어 다음 cycle 의 plan-eng-review 후 진행한다.

<!-- PLAN-APPROVED by user on 2026-05-06 -->

### 영향 파일
- [src/static/admin.js](../src/static/admin.js) — 핵심. 3 개 인라인 save 버튼 제거 + pending 상태 4 종 추가(`productMeta`, `productDatabases`, `systemPrompts`) + `applyAllPending()` 6 단계로 확장 + `pendingChangeCount()` / `refreshPendingUI()` / dashboard pending 카드 갱신. `renderProductDetail()` 의 chip wrap 에 메타데이터 4 종 locked chip 강제 prepend(× 버튼 없음, `is-locked` 클래스). chip 자유 텍스트 입력을 `<select>` picker 로 교체 — `loadAdminData` 에서 `/api/admin/databases/available` 동시 호출, 메타데이터 4 종 / 이미 등록된 chip / 내부 차단 (`agent_memory`) 은 옵션에서 제외. `buildSystemPromptEditor` 의 saveBtn/clearBtn 제거 + textarea 변경 핸들러로 pending 등록 + 안내 메시지 ("변경사항은 하단 '모두 적용' 으로 저장됩니다").
- [src/static/admin.html](../src/static/admin.html) — markup 변경 없음. cache-bust query string `v=20260506-batch-commit` 로 갱신 (admin.js / styles.css 양쪽).
- [src/static/styles.css](../src/static/styles.css) — `.admin-chip.is-locked` (회색 + cursor:not-allowed + opacity 0.55), `.admin-chip-locked-hint` 토큰 사용, `.admin-db-picker-row` (select + 추가 버튼 정렬) 추가. 토큰만 사용하고 hardcoded 색상 금지.
- [src/app.py](../src/app.py) — `GET /api/admin/databases/available` 신규 엔드포인트 추가. `_open_memory_connection(database=None)` 으로 `SHOW DATABASES` 실행, 결과를 `metadata_schemas`(고정 4 종 + 실제 존재 여부 marker) 와 `user_schemas`(메타 4 + `agent_memory` + `MEMORY_DB` 제외) 로 분리. 권한: `console.access`. 검증: schema name regex `^[a-z_][a-z0-9_]{0,63}$` 매칭 만 반환.

### 접근 방법
1. **Backend `/api/admin/databases/available`** 추가 — read-only enumeration. 권한이 약하면 (`console.access` 만) Product 관리자가 아니어도 목록 조회는 가능 (옵션 채우기 용도). 실제 등록은 `product.manage` 권한이 필요한 `PUT /api/admin/products/{id}/databases` 로만.
2. **Frontend pending 흐름 통합**:
   - `adminState.pending` 에 `productMeta: Map<productId, patch>`, `productDatabases: Map<productId, draft[]>`, `systemPrompts: Map<key, {scope, productId, roleId, accountId, content}>` (key = `${scope}:${productId||0}:${roleId||0}:${accountId||0}`) 추가.
   - `setProductMetaPending(id, patch)`, `setProductDatabasesPending(id, draft)`, `setSystemPromptPending(args)` 헬퍼 추가. 모두 immediate API 호출 안 함.
   - `pendingChangeCount()` 에 신규 3 buckets 합산.
   - `applyAllPending()` 에 6 번째~8 번째 단계 추가: 제품 메타 PATCH → 제품 DB PUT → 시스템 프롬프트 PUT (productMeta → productDatabases 순서, 둘 다 같은 product 면 메타 먼저).
   - `cancelAllPending()` 에 신규 buckets clear 추가. `loadAdminData()` 에 stale entry GC 추가 (제품 삭제 시 정리).
   - `refreshPendingUI()` 의 `commitBarDetail` 에 신규 카테고리 항목 추가.
   - Dashboard pending 카드(`renderDashboard` / `dashboardPendingList`) 에도 신규 카테고리 노출.
3. **renderProductDetail (제품 정보 저장 버튼 제거)** — name/desc/active/default/sort 입력 변경 핸들러를 `setProductMetaPending(productId, {field: value})` 로 변경. `saveMetaBtn` 삭제. 입력 disabled 는 `!canManage` 그대로 유지.
4. **renderProductDetail (DB 목록 저장 버튼 제거 + metadata locked chip + picker)**:
   - `redrawChips()` 시작 부분에 메타데이터 4 종을 `<span class="admin-chip is-locked"><span>information_schema</span> <small>항상 접근</small></span>` 형태로 forEach 강제 prepend. × 버튼 없음. `draft` 배열에는 메타 4 종이 들어있더라도 화면 상 user chip 영역에서 제외하여 중복 노출 방지 (단, draft 정합성 유지를 위해 user chip 만 표시).
   - 자유 텍스트 input + 추가 버튼을 `<select>` picker + `+ 추가` 버튼으로 교체. `<select>` 옵션은 `adminState.availableDatabases` (loadAdminData 에서 채움) 에서 메타 4 종 / 이미 draft 에 있는 schema / `agent_memory` / `MEMORY_DB` 제외. 옵션 0개면 "(추가 가능한 DB 없음)" 빈 옵션 표시.
   - `+ 추가` 버튼 클릭 시 draft 에 push + `setProductDatabasesPending(productId, draft)` + `redrawChips()` + picker 옵션 갱신.
   - chip × 버튼 클릭 시도 동일하게 `setProductDatabasesPending` 으로 pending 등록.
   - `saveDbBtn` 삭제. 안내 텍스트(dbHint) 마지막에 "메타데이터 4 종은 정책상 항상 접근 가능하며 변경할 수 없습니다." 한 줄 추가.
5. **buildSystemPromptEditor**:
   - `saveBtn` / `clearBtn` 제거 후, textarea `input` 이벤트로 `setSystemPromptPending({scope, productId: resolveProductId(), roleId, accountId, content: textarea.value})` 호출.
   - 빈 문자열 입력은 그대로 pending 으로 들어가고 apply 시 `PUT /api/admin/system-prompts` body content="" 가 삭제 경로로 처리됨 (기존 backend 동작 활용).
   - textarea 위에 안내 한 줄 ("변경사항은 하단 '모두 적용' 버튼으로 일괄 저장됩니다") 추가.
   - `productSelect` 변경 시 pending 의 key 가 바뀌므로, change 이벤트에서 `refresh()` 만 하고 textarea 값은 비우지 않는다 (사용자 의도 보존). Pending 에 같은 key 가 이미 있으면 textarea 에 그 content 를 채움.
6. **app.py `GET /api/admin/databases/available`** — `_account_has_permission(account, "console.access")` 검사 후 `_open_memory_connection(database=None)` → `SHOW DATABASES` → 결과를 `_METADATA_SCHEMAS = {"information_schema","mysql","sys","performance_schema"}` 와 `_INTERNAL_SCHEMAS = {MEMORY_DB.lower(), "agent_memory"}` 로 분류. user_schemas 에는 메타·내부·정규식 위반 제외 후 정렬해 반환. metadata_schemas 는 항상 고정 4 종 (실제 존재 여부 `present: bool` 표기).
7. **Cache-bust** — admin.html 의 `styles.css?v=…` 와 `admin.js?v=…` 두 줄을 `v=20260506-batch-commit` 으로 갱신.

### 위험도
- **Major** (§12.3) — 다파일 변경(FE 3 + BE 1), 권한 모델 변경 없음, 외부 계약·비용 영향 없음, 기존 정책(REV-20260422-0006 메타 bypass) 의 시각화일 뿐 동작 변경 아님. `agent_memory` 차단 정책 그대로 유지. 회귀 위험 영역: applyAllPending 6 → 8 단계 확장, dashboard pending 카드 새 카테고리.
- **C5 (계정·역할 → 제품 권한 상속/override)** 는 본 cycle 에서 분리. 사유: 신규 테이블(`WebRoleProductAccess`, `WebAccountProductAccessOverrides`) 마이그레이션 + `compose_system_prompt` 의 product 조회 경로 영향 + RBAC override 모델 (TASK-0024) 과의 충돌 검토 필요. 다음 cycle 진입 전 `/plan-eng-review` 권고.

### 검증 계획 (D 단계)
- a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` — syntax
- b) `make web` 재빌드 + `docker logs web` healthy 확인
- c) UX 회귀: `/admin` 진입 → 제품 탭 → 메타 4 chip 회색 표시 / × 없음 확인 / picker 옵션에 메타 4 미포함 확인 / 사용자 schema 추가·제거 시 footer 카운트 증감 / `모두 적용` 클릭 시 PATCH + PUT 순차 호출. 역할 탭 → 권한 grid 변경 + 시스템 프롬프트 textarea 변경 → footer 일괄 적용 동작.
- d) `GET /api/admin/databases/available` 직접 호출로 metadata 4 종 + user_schemas 정렬 + agent_memory 제외 확인.
- e) `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` PASS.

### 후속
- C5 분리 권고를 본 plan + `docs/REPORT.md §후속 작업` 에 기록.
- ANCHOR.md §3 의 "Role/Product 권한 부여" 시나리오 묘사가 본 변경으로 시각화되어 강화됨 — §3 본문 보강 여부는 §4 (cycle 종료 시 human 검증) 에서 판단.

## 2.1.archived Implementation Plan (TASK-0048)

본 plan 은 AGENTS.md §7.1 Plan-Review-Execute 프로토콜에 따른 Major 등급 변경 계획이다. 사용자가 2026-05-06 직접 진행 지시 (§3.1 우선순위 1) 를 한 상태에서 `<!-- PLAN-APPROVED by user on 2026-05-06 -->` 마커로 인계된다.

### 영향 파일
- [src/app.py](../src/app.py) — `/api/ask` body 에 optional `product_mode` / `product_id` hint 수용. 기존 `request_conversation_id` 이 비어 있어 `_resolve_conversation_for_account(create_if_missing=True)` 로 lazy 생성되는 분기에서, 새 cid 직후 `AgentCoreConversations.product_id/product_mode` 를 hint 값으로 셋업하고 `_save_account_product_pref` 도 호출. `request_conversation_id` 가 명시된 경로(기존 대화에 ask) 에서는 hint 를 무시한다 (대화의 product 변경은 `PATCH /api/conversations/{cid}/product` 가 단독 진실 — TASK-0047 의 race guard 와 충돌 방지).
- [src/static/app.js](../src/static/app.js) — `state.pendingNewConversation: boolean` 도입. `createConversation()` 의 동작은 보존(다른 호출처에서 직접 호출 가능) 하되, `newConversationBtn` 핸들러는 새 함수 `beginPendingConversation()` 으로 교체. `sendPrompt()` 가 pending 상태일 때 `/api/ask` body 에 `product_mode` / `product_id` 를 첨부하고 응답의 `conversation_id` 를 채택. `renderConversationList()` 에 pending placeholder (`is-pending` 클래스, 클릭 비활성, "내 대화" 그룹 상단) 추가. `selectConversation()` 은 pending 모드를 자동 종료. `isCurrentConvBusy()` / progress polling 은 pending 동안 cid sentinel `__pending__` 를 사용해 빈 cid 와 충돌하지 않도록 한다.
- [src/static/index.html](../src/static/index.html) — markup 변경 없음. cache-bust query string `v=20260506-pending-conv` 로 갱신.
- [src/static/styles.css](../src/static/styles.css) — `.conv-item.is-pending` 1 selector 추가 (border-dashed + faded text + cursor:default). 토큰만 사용.

### 접근 방법
1. **Frontend pending state 도입** — `state.pendingNewConversation` 플래그와 sentinel cid `__pending__` 도입. 새 대화 버튼 클릭 시 `beginPendingConversation()` 호출:
   - `state.activeConversationId = ""`, `state.pendingNewConversation = true`, `state.messages = []`
   - `renderConversationList()` (placeholder 표시), `renderConversationHeader()` ("새 대화" 표기), `renderComposer()` (활성), `stopProgressPolling({reset:true})`
   - product chip 은 `state.productMode/pinnedProductId` 를 그대로 유지 (cid 가 없어도 localStorage 미러로 의도 보존, `setActiveProduct` 의 cid-없음 분기 활용)
2. **사이드바 placeholder** — `renderConversationList()` 의 "내 대화" 섹션 렌더 직전에 pending 모드면 가상 항목을 prepend. 클래스: `conv-item is-own is-active is-pending`. 텍스트: "새 대화 (작성 중)" + 부제 "첫 메시지를 입력하세요". 클릭 핸들러 없음.
3. **sendPrompt() 변경** — pending 모드면:
   - body 에 `conversation_id: ""` + `product_mode: state.productMode` + `product_id: state.pinnedProductId || null` 첨부
   - `targetConvId` sentinel 로 `__pending__` 사용하여 `state.busyConversations.add("__pending__")` 처리
   - `progress polling 시작 시 cid 가 비어있으므로 startProgressPolling 호출은 ask 응답으로 cid 를 받은 후로 미룸
   - ask 응답에서 `payload.conversation_id` 받으면 `state.activeConversationId = payload.conversation_id`, `state.pendingNewConversation = false`, busy sentinel 해제, `refreshWorkspace(payload.conversation_id)`
   - ask 가 timeout/네트워크 오류로 실패 — 이 경우 backend 가 이미 cid 를 만들었을 수 있으나 client 가 cid 를 모름 → 사용자에게 "다시 시도하거나 사이드바 새로고침으로 복구" 안내 토스트. attach/resume 다이얼로그는 cid 가 있을 때만 의미가 있어 pending 모드에서는 비활성. 복구 경로: 사용자가 사이드바 새로고침(또는 `loadConversations` 재호출) 으로 새 대화를 보고 그 cid 로 ask 를 다시 보낸다.
4. **Backend `/api/ask` 보강** — `data.get("product_mode")` / `data.get("product_id")` 를 normalize. lazy 생성 분기에서 cid 만든 직후:
   ```python
   if hint_mode in ("auto", "pinned"):
       cur = conn.cursor()
       cur.execute(
           "UPDATE AgentCoreConversations SET product_id = %s, product_mode = %s "
           "WHERE conversation_id = %s",
           (hint_pid, hint_mode, conv_id),
       )
       cur.close()
       _save_account_product_pref(conn, int(account["id"]), mode=hint_mode, pinned_id=hint_pid)
   ```
   기존 대화 경로 (`request_conversation_id` 명시) 는 hint 무시. lazy 분기 이후 line 3886~ 의 `if conv_id:` block 이 새 row 의 `product_mode` 를 다시 읽어 정상 동작한다.

### 위험도 평가 (§12.3)
- **Major** — backend API contract 확장 + frontend state 흐름 변경. 단:
  - Schema/auth/마이그레이션 변경 없음 → Critical 아님
  - 외부 비용 영향 없음
  - 기존 호출자(테스트 러너, 직접 `/api/new_conversation` 사용) 는 backward-compatible 동작 유지
  - 회귀 surface: TASK-0041 attach/resume (cid 가 있을 때만 attach 가능), TASK-0047 product chip race guard (pending 동안 cid 없으니 PATCH 미동작 — `setActiveProduct` 의 cid-없음 분기 활용), 사이드바 그룹 렌더링.

### 사람 승인
<!-- PLAN-APPROVED by user on 2026-05-06 -->

## 3. In Progress
- TASK-0034 복잡 QA 성능 테스트 — 현재 구성된 assistant(agent-core + web UI)의 복잡 질의 대응력을 측정해 이후 개선 포인트를 도출한다. Q1/Q2/Q3 검증 완료, **Q4/Q5 재수행 완료 (2026-04-22: Q4 7 턴 stopped-by-heuristic 1171s / Q5 5 턴 stopped-by-heuristic 251s, 전 턴 HTTP 200)** — TASK-0040/0041 선행 완료 후 블로커 해제. 현재 남은 일은 turn-by-turn 실제 답변과 truth query 대조 검증 + `TASK-0034-REPORT.md` / LEARNINGS 추가 정리.

## 3.1 Recently Done
- TASK-0061 (2026-05-15 마감, REQ-20260515-0003~0010, **Major** §12.3 — Phase 6 Critical 분면 포함, 사용자 일괄 승인): GOAL.md 8 항목 합본 cycle. (Phase 1+2) 답변 버블 내부 실시간 step 진행 + 신규 대화 첫 요청 즉시 polling 연결 — `state.pendingBubble` + `renderPendingAssistantBubble` + elapsed timer + `applyProgressPayload` 동기화 + `sendPrompt` lazy-create 분기에서 cid 발급 즉시 `startProgressPolling`. (Phase 3) `_compute_display_status` + `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` + 일관 stale 반영 (/api/progress, ask_status, ask_result, list_conversations) + frontend `.conv-dot.is-stale-error` + toast. (Phase 4) `#messagePointRail` + scroll observer + click jump. (Phase 5) `/api/history_dates` AgentMemoryMessages 정본 + 캘린더 popover. (Phase 6 Critical) `WebAccounts.MustChangePassword` ALTER + `POST /api/admin/accounts/{id}/password-reset` (self-reset 거부) + 임시 비번 1회 표시 + 세션 revoke + 강제 변경 modal. (Phase 7) `currentPageAccounts()` helper 로 select-all 현재 페이지만 토글. (Phase 8) Ctrl/Shift 다중 선택 + `_delete_conversation_impl` helper 추출 + `POST /api/delete_conversations` partial success + ≥10 typed-confirm. 변경 파일: `app.py`, `app.js`, `admin.js`, `index.html`, `admin.html`, `styles.css`, `.env.example`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md`. cache-bust `v=20260515-task-0061`. 검증: python compile / node --check / make web / browser smoke (DOM 5 신규 element + login + bulk bar + 캘린더 popover + display_status + history_dates + delete_conversations + pending bubble + admin currentPageAccounts/select-all + reset btn) 모두 통과.

- TASK-0050 (2026-05-06 마감): `make web` 이 docker compose v5.1.1 + buildx v0.31.1 의 provenance metadata file race 로 EXIT=1 종료되던 문제 우회. 환경 진단으로 `#15 exporting to image` 까지 정상 빌드 후 `#16 resolving provenance for metadata file` 직후 `open /tmp/.tmp-compose-build-metadataFile-<UUID>.json<NNNN>: no such file or directory` 메시지로 종료되는 패턴을 확인 (random suffix mismatch — compose 본체 회귀). `--provenance=false`, `BUILDX_NO_DEFAULT_ATTESTATIONS=1`, `COMPOSE_BAKE=true/false` 모두 효과 없음. Makefile 에 `dc-build SERVICE=...` reusable 가드 타깃을 추가하고 `web` 타깃을 `dc-build SERVICE=web` + `up -d --no-build web` 로 분리. 가드는 build 명령 로그를 임시파일에 캡처해 EXIT≠0 + 로그에 `compose-build-metadataFile` 문자열 포함 시에만 EXIT=0 으로 정규화 (다른 빌드 오류는 그대로 전파). 향후 compose 또는 buildx 가 fix 되면 가드는 자연스럽게 일반 build 경로로 흐름. 검증: `make web` EXIT=0, `[make] note: ...provenance metadata file race 우회...` 로그, `Container repo-web-1 Recreate/Recreated/Started`, `docker exec repo-web-1 grep -n PENDING_CONV_SENTINEL /app/web/static/app.js` 으로 새 코드 반영 확인. 학습 기록: `docs/LEARNINGS.md` LRN-20260506-0001 quirk.

- TASK-0049 (2026-05-06 마감, REQ-20260506-0002): TASK-0048 lazy 화 이전에 누적된 빈 대화 row 들을 일회성으로 정리. `bin/cleanup-empty-conversations.sh` 추가 — dry-run 기본 + `--execute` 명시 시에만 DELETE, `AgentMemoryKv.last_status='processing'` 인 대화 보호 (실행 중 ask race), `c.created_at < NOW() - INTERVAL <keep-recent-min> MINUTE` (default 5분) 으로 방금 만들어진 placeholder 폴백/in-flight 보호, `--owner-account-id <N>` 으로 계정 한정 가능. SQL 주입 방지를 위해 owner_id/keep_recent_min 모두 정수 정규식 검증 후 인터폴레이션, AgentCoreConversations 와 AgentMemoryMessages 의 collation 차이를 `COLLATE utf8mb4_unicode_ci` 명시 변환으로 해결. 운영 데이터에 적용: 88 conversations / 42 empty / 46 non-empty → 46 conversations / 0 empty / 46 non-empty (5분 보호로 방금 만든 backward-compat 검증 row 1개 포함 정리). 정리된 빈 대화 42개의 owner 분포는 admin (id=1) 다수, 그 외 일부 사용자. 본 TASK 는 destructive 변경(§12.1) 이지만 사용자 2026-05-06 명시 진행 지시에 따라 §3.1 우선순위 1 적용. 추후 정리는 동일 스크립트 재실행으로 idempotent 하게 가능.

- TASK-0048 (2026-05-06 마감, REQ-20260506-0001): "새 대화" 버튼이 즉시 `POST /api/new_conversation` 을 호출하지 않도록 client-side pending state 로 전환했다. 사이드바 "내 대화" 그룹 상단에 `conv-item is-own is-active is-pending` placeholder ("새 대화 (작성 중)" / 부제 "첫 메시지를 입력하세요") 가 표시되고 헤더 + composer 가 활성화. 첫 메시지 전송 시 `sendPrompt()` 가 `/api/ask` body 에 `conversation_id: ""` + `product_mode` + `product_id` (사용자 직전 의도) 를 첨부해 호출하면 backend `/api/ask` 의 `_resolve_conversation_for_account(create_if_missing=True)` 직후 hint 를 `AgentCoreConversations.product_id/product_mode` 에 셋업 + `_save_account_product_pref` 호출로 `WebAccounts.ProductPref*` 미러까지 갱신한다. 응답의 `conversation_id` 를 client 가 채택하고 placeholder 가 사라진다. 빈 대화 누적이 신규 row 측에서 차단된다. PATCH race 가드(TASK-0047 AC-0013) 와 attach/resume(TASK-0041 AC-0018) 는 cid 가 있을 때만 의미가 있어 lazy 분기에서 의도적으로 비활성화 — pending 단계 ask 실패는 "다시 시도하거나 사이드바 새로고침" 안내 토스트로 fallback. 변경 파일: `src/app.py` (lazy 분기에 hint 적용 + `_save_account_product_pref`), `src/static/app.js` (`state.pendingNewConversation`, `PENDING_CONV_SENTINEL`, `beginPendingConversation`, `renderConversationList` placeholder + `prependFn`, `renderConversationHeader` pending 표시, `selectConversation` 자동 종료, `sendPrompt` lazy create 분기, `handleLogout` cleanup, 새 대화 버튼 핸들러 교체), `src/static/index.html` (cache-bust `v=20260506-pending-conv`), `src/static/styles.css` (`.conv-item.is-pending` 1 selector 그룹). 검증: `python3 -m py_compile`, `node --check` 모두 통과, `make web` 으로 컨테이너 재기동 후 새 코드 반영 확인 (`docker exec` grep), `/api/new_conversation` backward-compat 정상 (delta=1 정상 row), `/api/ask` invalid (no API key) 시 lazy create 발생 0건 (input validation 후 lazy create 가 일어나므로 안전). 학습 기록: `docs/LEARNINGS.md` LRN-20260506-0014 pattern.

- TASK-0047 (2026-04-29 마감, agent team 4 합의 + Codex CLI 교차검증 — 사람 검토 없이 진행됨):
  사용자가 진입(로그인 직후) 또는 진행 중 대화에서 대상 **제품(Product)** 을 명시 선택할 수 있도록
  사이드바 헤더에 제품 칩(`#productChip` + `<select id="productSelect">`) 을 도입했다. 칩에는
  caption "이 대화의 제품" 을 함께 두어 대화 단위 상태(전역 계정 설정이 아님) 임을 명시한다 (Codex
  R-06 가드). `auto` 옵션은 일반 대화 모드로, 본 MVP 에서는 LLM resolver 가 들어가기 전이므로
  `[AUTO MODE]` 한 줄을 시스템 프롬프트에 inject 하고 product 한정 PRODUCT/role/account prompt 와
  `allowed_schemas` 를 모두 끈다(빈 리스트로 메타 4 스키마만 허용). 데이터 모델은 새 컬럼 2 개로
  분리: `AgentCoreConversations.product_mode VARCHAR(8) NOT NULL DEFAULT 'pinned'` + `WebAccounts.ProductPrefMode`/`WebAccounts.ProductPrefPinnedId`. NULL=auto 의미 변경을
  피하기 위해 명시 컬럼을 신설했다 (Backend Engineer 합의). 신규 API
  `PATCH /api/conversations/{cid}/product { mode, product_id }` 는 (1) 권한
  (`conversation.ask` + 소유자), (2) 진행 중 ask race 가드(`AgentMemoryKv.last_status='processing'`
  이면 409), (3) pinned 모드는 활성 product 검증 후 `WebAccounts` 의 직전 선호도 동시 갱신.
  `/api/session` 응답에 `product_pref` (mode, pinned_id, fallback_reason) +
  `conversation_product` (product_id, product_mode, product_key, product_name) 추가. Frontend 는
  `state.productMode` / `state.pinnedProductId` / `state.activeProductId` 3-필드 분리(의도/핀/서버 결과)
  로 race 회피, optimistic update + PATCH + localStorage 미러 (`mad.productPref.v1`), 진행 중 ask
  동안 `<select>` disabled + tooltip. 코드 중복 방지를 위해 `renderProductOptions(selectEl, {includeAuto, selected})`
  factory 를 추출해 drawer 의 `promptProductSelect` 도 같은 옵션 모델을 공유하게 했다 (FE
  Architect 합의). pinned product 가 비활성/제거된 경우 `_load_account_product_pref` 가 자동으로
  auto 로 강등하고 `pref.fallback_reason='pinned_inactive'` 를 클라이언트에 알려 토스트로 안내한다
  (Codex R-04 가드). 사용자 가시 한글 라벨 "상품" → "제품" 일괄 치환 (`app.py`, `index.html`, `app.js`,
  `admin.html`, `admin.js`); 코드 식별자 `Product`/`product_id`/`WebProducts`/`ProductKey` 는 그대로.
  검증: (1) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과,
  (2) `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py` 통과,
  (3) `node --check src/static/app.js` 통과, (4) in-process `compose_system_prompt(None,...)` /
  fake-conn `compose_system_prompt(...,product_mode='auto')` 검증 — auto 분기는 `[AUTO MODE]` 라인을
  포함하고 pinned 분기는 포함하지 않음. 후속 검증 항목(LLM resolver, PATCH race 강화, Playwright 4 specs,
  BroadcastChannel, mobile bottomsheet, 다국어, 운영 모니터링)은 별도 브리핑 [`docs/BRIEFING-product-selector-v1.md`](./BRIEFING-product-selector-v1.md)
  에 16 개 위험 항목(R-01..R-16) + 5 개 사람 확인 결정 사항(D-01..D-05) 으로 정리. **본 turn 은
  사용자 검토 없이 agent team(UX/FE Architect/BE Engineer/QA-Flow Validator) 4 인 합의 + Codex CLI
  교차검증으로 진행됐다 — 운영 반영 전 D-01..D-05 사람 결정과 R-01..R-16 검증이 필요하다.**

- TASK-0044 (2026-04-23 마감): Approach A wedge (office-hours 2026-04-23 세션에서 승인 — 사업팀 통계/단순 데이터 자가서비스) pilot 인프라 추가. (1) `SEED_ROLE_DEFINITIONS` 에 RoleKey=`sales` / Name=`사업팀` entry 를 추가해 부트스트랩 시 자동 생성되고, 권한은 대화 생성/질의/조회/파일조회/이름변경/취소/즉시답변(own 범위) 9 개로 operator 에서 `conversation.delete.own` 을 제거한 subset — 사업팀 pilot 은 자기 대화 흐름은 조작할 수 있지만 과거 요청 기록의 삭제는 불가. (2) 신규 `SEED_ROLE_SYSTEM_PROMPTS` + `_ensure_seed_role_system_prompts(conn)` 부트스트랩 단계를 추가해 sales role 에 역할 범위(`WebSystemPrompts.Scope='role', RoleKey=sales, ProductId=NULL`) system prompt 를 1 회 upsert 한다 — 관리 콘솔에서 덮어쓴 값은 존중(존재 시 skip). prompt 본문은 "단순 조회 → 문장 / 집계 → 결과셋 표 / ad-hoc 분석 → DBA 팀 이관 안내 후 대화 종료 / DB 쓰기 쿼리는 항상 거부" 4 지침. `compose_system_prompt` (agent_core) 가 기존 로직대로 `## ROLE GUIDANCE (sales)` 블록으로 주입한다. (3) `modules/config.py` 에 `REPLICA_DB_HOST` / `REPLICA_DB_PORT` / `REPLICA_DB_USER` / `REPLICA_DB_PASSWORD` / `REPLICA_DB_ENABLED` env 5 개 추가 + `modules/db.py::connect()` 에 라우팅 — `REPLICA_DB_HOST` 가 세팅되어 있고 요청된 `database` 가 `MEMORY_DB`(=agent_memory) 가 아니면 복제 인스턴스로 접속, 아니면 기존 primary. memory DB 연결은 항상 primary 로 남아 대화/세션/권한 정본이 보존된다. `.env.example` 에 4 개 placeholder 추가, 실제 값은 `.env` 또는 docker-compose secret 으로만 주입한다(commit 금지). (4) Product 단위 접근 DB 화이트리스트 조정은 **런타임 체크가 아닌 관리 콘솔 runbook** 으로 정리 — 사업팀 pilot 에게 서빙할 Product 는 KR 의 기본값(`dbgame`/`dblog`/`dbauth`) 을 admin 이 관리 콘솔 `상품 (Products)` 탭에서 `dbauth` 를 제거하거나, 별도 Product(예: `KR-Sales`={dbgame,dblog}) 를 신규 생성해 사업팀 대화를 routing 하는 방식 중 조직 정책에 맞게 선택한다. 현재 seed 는 호환성을 위해 변경하지 않음(기존 KR 을 그대로 쓰는 DBA 워크플로우 영향 없음). (5) 사업팀 pilot 계정 자체는 코드가 자동 생성하지 않고 admin 이 관리 콘솔에서 수동 발급 — `.env.example` 에 `WEB_PILOT_SALES_USERNAMES=` placeholder 주석으로 치환 예시(`sales_lee,sales_kim,sales_park`) 기록. 검증: (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py unit/feature-0002-agent-core/src/modules/config.py unit/feature-0002-agent-core/src/modules/db.py` 통과, (b) `docker compose up -d --build web` 후 `/api/session` HTTP 200 OK, (c) `/api/admin/roles` 응답에 `{"role_key":"sales","name":"사업팀", permissions:[9 codes] }` 포함, (d) `WebSystemPrompts.Scope='role' AND RoleId=<sales_role_id> AND ProductId IS NULL` 1 row 존재하고 content 가 4 지침 문자열로 저장됨. 범위: 애플리케이션 코드 3 파일 약 70 줄, `.env.example` 6 줄, 문서 4 파일. `agent_core` 경로 재빌드(`depends_on` 체인) 는 모두 `modules/db.py` 변경 때문에 필요하다.
- TASK-0041 (2026-04-22 마감): 클라이언트 타임아웃 시 대화 지속(Attach/Resume) 경로를 구축. 에이전트 작업자 스레드는 `asyncio.to_thread` 로 HTTP 연결과 독립 실행되므로 클라이언트(httpx/브라우저/프록시) 가 ReadTimeout 으로 끊겨도 서버는 완료까지 계속 진행한다. 이 결과를 회수할 read-only 경로가 없어 결과가 유실되던 문제를 해결. 서버에는 `_ASK_TERMINAL_STATUSES={done,error,canceled}` 상수와 `_load_run_meta_kv` + `_build_ask_status_snapshot` 헬퍼, 그리고 `GET /api/ask_status` (1-shot 스냅샷, `conversation.read.own/any` gated) 와 `GET /api/ask_result?wait<=60` (long-poll, `deadline/0.5s` interval, terminal 시 assistant 전문 반환) 2 엔드포인트를 추가. 브라우저에는 `ASK_ATTACH_POLL_WAIT_SEC=45`/`ASK_ATTACH_MAX_TOTAL_SEC=1800` 상수와 `fetchAskStatus` / `showTimeoutRecoveryDialog`(3 버튼 모달 + Escape dismiss, 인라인 스타일) / `attachAndWaitForResult` long-poll 루프를 추가하고, `sendPrompt()` 의 `/api/ask` 호출 실패 시 is_processing=true 이면 다이얼로그 → 선택에 따라 `/api/cancel`·`/api/finalize` + attach, `initializeWorkspace()` 말미에는 페이지 로드 시 auto-attach. 테스트 러너에는 `ATTACH_TIMEOUT_SEC=960.0`/`ATTACH_POLL_WAIT_SEC=45` 상수와 `_attach_run(client,cid,message,t0)` 함수를 추가해 기존 `httpx.ReadTimeout` 분기를 `{"error":"client-read-timeout"}` 반환 대신 ask_status → ask_result long-poll 로 정상 복구하고 turn dict 에 `attached_after_timeout=True` + `attach_verdict` 기록. `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT=6) 과 분리되어 attach 가 새 실행을 시작시키지 않는 안전 속성을 보장한다. 검증: py_compile 3 파일 + `node --check app.js` 통과, `make web` 재빌드 후 새 이미지 반영, 엔드포인트 401 라우팅 확인, terminal 상태 스냅샷 38ms, Q4 7 턴 + Q5 5 턴 전부 HTTP 200 으로 완료 (단일 턴이 960s 를 넘지 않아 attach 는 실제 발동되지 않았지만 safety net 인프라는 검증됨).
- TASK-0040 (2026-04-22 마감): SQL schema whitelist 정규식을 context-aware 2 단계 스캐너로 재작성해 `alias.column` 오탐 회귀를 제거했다. 기존 `_SCHEMA_TABLE_REF_RE = r"\`?([A-Za-z_]\w*)\`?\s*\.\s*\`?([A-Za-z_]\w*)\`?"` 는 SQL 문맥 구분 없이 전체에서 `x.y` 를 찾았고, SELECT/WHERE/ON 절의 alias.column 토큰이 schema 후보로 수집되어 Q4 재수행이 모든 턴 `BLOCKED_SCHEMAS=bb,be` 로 실패했다. `_TABLE_LIST_RE` (FROM/JOIN 뒤 다음 절 키워드 직전까지의 테이블 리스트 구간을 slice, IGNORECASE|DOTALL) + `_INNER_REF_RE` (그 slice 내부에서만 `schema.table` 추출) 2 단계로 재작성. SELECT 절의 alias.column 은 FROM/JOIN slice 바깥이라 더 이상 매칭되지 않는다. 검증: in-process 15 테스트 케이스(단일 FROM / FROM+WHERE alias.col / FROM+JOIN+alias.col ON / 혼합 / 백틱 / subquery / 비허용 schema 차단 / SELECT alias.col 무시 / semicolon terminator / UNION 경계 / whitespace DOTALL / dedup) 전부 expected 일치, Q4-like SQL 이 `{dblog}` 만 추출되고 `_whitelist_violation` 이 `{dbauth,dbgame,dblog}` whitelist 에서 None 반환, 비허용 `dbstat.foo` 는 계속 차단. 후속 TASK-0034 Q4/Q5 재수행이 전 턴 HTTP 200 으로 완료됨.
- TASK-0039 (2026-04-22 마감): Product 단위 DB whitelist 를 적용하면서 **메타데이터 4 스키마**(`information_schema`, `sys`, `mysql`, `performance_schema`) 만은 Product 접근 DB 목록에 등록 여부와 무관하게 agent tools 가 **항상 조회 가능** 하도록 정책을 재정의했다. 사용자 지시 2026-04-22: "assistant 가 스키마 구조를 찾지 못하는 이슈를 방지". 이는 TASK-0036 의 REV-20260421-0005 결정(메타데이터도 기본 차단) 을 일부 완화하는 방향이며, **`agent_memory` 는 여전히 whitelist 로 차단 유지**(에이전트 자신의 메모리/세션/계정 데이터 노출 방지). 변경: [tools.py:24-28](../../feature-0002-agent-core/src/modules/tools.py#L24-L28) 의 `_SYSTEM_SCHEMAS` frozenset 을 `_METADATA_SCHEMAS`(4 종) 와 `_INTERNAL_SCHEMAS`(1 종, `agent_memory`) 두 frozenset 으로 분리하고 `_SYSTEM_SCHEMAS` 는 union 으로 유지(기존 `_is_user_schema`/`search_tables` 의 UX-레벨 필터 동작 보존). [tools.py:78-94](../../feature-0002-agent-core/src/modules/tools.py#L78-L94) 의 `_whitelist_violation` 은 기존 `{information_schema}` bypass 대신 `_METADATA_SCHEMAS` 전체(4 종) 를 bypass 하고, `agent_memory` 는 여전히 `blocked` 로 떨어지도록 했다. 에러 메시지에 "메타데이터 스키마는 항상 접근 가능" 안내 한 줄을 추가해 agent 가 잘못된 참조를 메타데이터로 리디렉션하지 않도록 유도. 검증: (a) `python3 -m py_compile unit/feature-0002-agent-core/src/modules/tools.py` 통과, (b) 컨테이너 재빌드 후 `docker compose exec web python -c "..."` in-process 호출로 `set_active_schema_allowlist(['dbgame'])` 설정 상태에서 `_whitelist_violation({'mysql'})` / `{'sys'}` / `{'performance_schema'}` / `{'information_schema'}` 가 모두 `None` 반환, `{'agent_memory'}` 는 `오류:` 문자열 반환, `{'dbstat'}` (임의의 비허용 user schema) 은 차단. (c) 실사용 스모크: Product=KR 로그인 + 새 대화 + `/api/ask` 로 "dbgame 스키마에 있는 테이블 수를 information_schema 로 세어봐" → whitelist bypass 로 information_schema 접근 허용, tool step 정상 완료. 범위: 본 TASK 는 whitelist 정책 bypass 목록 조정에 국한. `list_schemas` 결과에 메타데이터 스키마를 노출할지는 UX 결정이라 현 상태(숨김) 유지.

- TASK-0038 (2026-04-22 마감): TASK-0034 Q4/Q5 실패 원인 분석([TASK-0038 상세 설계](#task-0038-상세-설계-2026-04-22) 참조)에서 확인된 근본 원인 1(agent_core 의 `OpenAI(**client_kwargs)` 가 `timeout`/`max_retries` 파라미터 없이 초기화돼 LLM 호출이 무한 대기할 수 있음) 과 근본 원인 2(러너 `ASK_TIMEOUT_SEC=600s` < 서버 `run_timeout_sec=900s` 로 클라이언트가 서버보다 먼저 포기해 좀비 에이전트 스레드가 발생) 를 대응했다. (1) [agent_core.py:1134](../../feature-0002-agent-core/src/agent_core.py#L1134) 의 `client = OpenAI(**client_kwargs)` 를 `OpenAI(**client_kwargs, timeout=max(5,int(AGENT_TIMEOUT_SEC)), max_retries=max(0,int(AGENT_OPENAI_MAX_RETRIES)))` 로 확장하고 import 에 `AGENT_OPENAI_MAX_RETRIES` 를 추가. OpenAI Python SDK v1.x 의 client-level `timeout` 은 내부 httpx 에 그대로 적용되므로 `chat.completions.create` 개별 호출마다 wall-clock 상한이 보장된다. `max_retries` 는 이미 `AGENT_OPENAI_MAX_RETRIES=0` (config 기본값) 이므로 SDK 내부 재시도로 budget 이 배수로 늘어나지 않는다. (2) `task0034_runner.py:52` `ASK_TIMEOUT_SEC=600.0` 을 `960.0` 으로 인상(서버 `run_timeout_sec=max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)=max(900,180)=900` 보다 60s 여유). 이제 서버가 먼저 자기-타임아웃으로 실패 응답을 돌려주고, 클라이언트는 그 응답을 받은 뒤 다음 턴으로 넘어간다 — 좀비 스레드 창이 사라진다. 검증: (a) `python3 -m py_compile src/agent_core.py tests/task0034_runner.py` 통과, (b) `docker compose up -d --build web` 후 bootstrap_admin 로그인 + `/api/session` 200 OK + `/api/new_conversation` 후 간단 질의가 정상 응답, (c) agent_core 내부 LLM 호출이 AGENT_TIMEOUT_SEC(=.env 값 300s) 초과 시 `openai.APITimeoutError` 를 던지고 `_call_llm` caller 에서 step error 로 흡수되는 경로를 `grep` 으로 재확인. 범위: 본 TASK 는 근본 원인 1+2 만 다루고, 3(질문 follow_up 강화) 과 4(러너 격리/쿨다운) 는 TASK-0034 재실행 단계에서 별도 처리한다.
- TASK-0037 (2026-04-22 마감): `/api/progress` 폴링 루프를 `setInterval` 고정 주기에서 **순번(progressPollSeq) 기반 `setTimeout` 체인 + AbortController + 적응형 주기** 로 전환한 TASK-0036 부수 변경을 사후 리뷰/검증/문서화한다. 문제: `/api/ask` 한 턴이 수분까지 걸리는 실사용 워크로드(TASK-0034 에서 평균 ~3분/턴 관측) 에서 1500ms 고정 `setInterval` 폴링은 (1) 이전 요청이 끝나기 전에 다음 요청이 발행돼 **in-flight 요청 쌓임**, (2) 탭 전환/대화 변경/로그아웃 시 발행된 요청을 취소할 경로가 없어 서버에 **스텁 요청이 계속 도착**, (3) 서버는 `_load_steps_for_run` 이 전체 step 을 파이썬으로 로드해 `after_step` 필터를 코드로 걸던 경로였고, (4) 탭이 배경화되어도 그대로 1500ms 주기로 폴링을 지속해 배터리/네트워크를 불필요하게 소모했다. 조치 (이미 27127b9 커밋에 반영됨): 서버는 `_load_progress_status(conn, cid)` 단일 커서로 `(status, status_at, run_id)` 를 반환하도록 분리하고, `_load_steps_for_run(after_step=0)` 으로 SQL 레이어 필터를 밀어넣었으며, `/api/progress` 에 `client_run_id` 쿼리 파라미터를 추가해 클라이언트가 들고 있는 run_id 가 서버 최신 run_id 와 불일치하면 `after_step` 을 0 으로 리셋해 새 run 전체를 다시 흘려보내도록 했다. 클라이언트는 상수 `PROGRESS_FETCH_TIMEOUT_MS=4000`, `PROGRESS_POLL_ACTIVE_MS=1200`, `PROGRESS_POLL_IDLE_MS=3000`, `PROGRESS_POLL_HIDDEN_MS=10000`, `PROGRESS_POLL_ERROR_MS=8000` 5개를 도입하고, state 에 `progressPollInFlight`/`progressPollSeq`/`progressAbortController`/`progressErrorCount` 을 추가했다. `setInterval` → `setTimeout` 단일 체인(`scheduleProgressPolling(delayMs, seq)`) 으로 전환해 각 poll 이 응답하고 나서 다음 poll 을 예약하는 구조가 되었고, `pollProgress(seq)` 은 `seq !== state.progressPollSeq || progressPollInFlight` 이면 즉시 return 해 중복 실행을 차단한다. 매 요청마다 `AbortController` 를 생성해 `state.progressAbortController` 에 보관하고 `stopProgressPolling({abort:true})` 이나 `controller.abort()` 타임아웃(4초) 에서 in-flight 요청을 즉시 취소한다. 적응형 주기: 응답에 step 이 있으면 1.2s(ACTIVE), 없으면 3s(IDLE), `document.hidden` 이면 최소 10s(HIDDEN), 연속 오류 3회 미만까지는 8s(ERROR) 간격으로 재시도하되 3회 이상은 아예 재스케줄링하지 않는다. 검증: (1) `grep -c "setInterval" src/static/app.js` = 0 으로 기존 폴링 루프가 모두 제거됨, (2) 적응형 상수 5개 모두 `scheduleProgressPolling`/`pollProgress` 에서 실제 참조됨, (3) 서버 `/api/progress` 는 `client_run_id` 가 없거나 불일치 시 `after_step` 을 0 으로 리셋하는 조건을 실제로 가진다(`app.py:4405`), (4) 브라우저에서 `/api/progress` 응답 status 가 `processing` 이외 값이 되면 `stopProgressPolling({abort:false})` + `refreshWorkspace(cid)` 호출로 폴링이 즉시 멈추고 최종 workspace 가 재로드된다. 영향: TASK-0034 복잡 QA 테스트 중 상용 API 응답이 5분 이상 걸리는 상황에서도 브라우저 열린 탭에서 요청이 쌓이지 않고, 탭 전환 시 자동으로 저속 모드로 내려간다.
- TASK-0036 (2026-04-21 마감): System Prompt Depth 가 Product → Role → Account 3 계층 체인으로 동작하고, Product 단위 접근 DB 화이트리스트가 agent tools 레벨에서 강제된다. `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` 3 신규 테이블 + `AgentCoreConversations.product_id` 컬럼을 추가했고, `product.manage` / `system_prompt.manage.role.any` 2 개 permission 을 `admin` 역할에 기본 부여했다. seed 로 ProductKey=`KR` + DB(`dbgame`/`dblog`/`dbauth`) 가 자동 생성된다. `agent_core.compose_system_prompt(mem_conn, product_id, role_id, account_id)` 가 base prompt 뒤로 `## PRODUCT CONTEXT` / `## ROLE GUIDANCE` / `## ACCOUNT PREFERENCES` 블록을 순차 append 하고, `tools.set_active_schema_allowlist()` 가 execute_sql/describe_schema 등 모든 도구의 스키마 참조를 검사한다. 관리 콘솔은 `상품 카테고리` 구분 그룹 아래 `상품 (Products)` 탭이 추가되어 Product CRUD + 접근 DB chip 편집 + Product scope prompt 편집을, Roles detail 은 Role scope prompt 편집기(Product 드롭다운 포함) 를, 프로필 드로우의 새 `프롬프트` 탭은 Account scope prompt 편집기를 각각 제공한다. 검증: (1) `docker compose up -d --build web` → bootstrap_admin 로그인 → `/api/admin/products` → KR seed 확인, (2) `PUT /api/admin/products/1/databases` 로 dblog 제거/복원 왕복 OK, (3) `PUT /api/admin/system-prompts` (product scope) → `compose_system_prompt(conn, product_id=1, role_id=3, account_id=1)` 출력에 `## PRODUCT CONTEXT (KR)` 블록이 추가됨을 in-container 직접 확인, (4) whitelist=`{dbgame,dblog,dbauth}` 설정 후 `execute_sql("SELECT 1 FROM mysql.user")` 및 `describe_schema("mysql")` 이 `오류: 접근이 허용되지 않은 스키마 참조: mysql` 반환, `describe_schema("dbgame")` 은 정상 동작. 부수 수정: `_runtime_tables_available` 의 probe list 에 신규 3 테이블을 포함해 기존 배포에서 schema 마이그레이션이 자동 트리거되게 했고, `_whitelist_violation` 이 `_SYSTEM_SCHEMAS` 를 예외 처리하던 우회 경로를 제거해 `mysql`/`performance_schema`/`sys`/`agent_memory` 가 더 이상 whitelist 를 건너뛰지 않게 했다 (security hardening).

### TASK-0040 상세 설계 (2026-04-22)
- 문제/목적 (TASK-0034 Q4 재수행 중 2026-04-22 관찰): Q4 재수행 3 턴이 모두 `오류: 접근이 허용되지 않은 스키마 참조: bb, be. 현재 Product 에 허용된 스키마: dbauth, dbgame, dblog` 에러로 종료됐다. 실제 SQL 은 `SELECT ... FROM dblog.battlebegin bb JOIN dblog.battleend be ON be.AcntNo = bb.AcntNo ... WHERE bb.BattleType = 'CROSSROUTE' AND be.Star >= 3 ...` 형태로 `dblog` 만 참조하고 `bb`/`be` 는 테이블 별칭(alias) 이었다. 원인은 TASK-0036 에서 도입한 [tools.py:65-80](../../feature-0002-agent-core/src/modules/tools.py#L65-L80) 의 `_extract_sql_schema_refs` 정규식 `r"`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\.\s*`?([A-Za-z_][A-Za-z0-9_]*)`?"` 이 WHERE/SELECT 절의 `alias.column` 토큰까지 `schema.table` 로 수집한 뒤 [tools.py:83-105](../../feature-0002-agent-core/src/modules/tools.py#L83-L105) `_whitelist_violation` 이 allowlist(`{dbauth,dbgame,dblog}` + 메타데이터 4 종) 에 없다는 이유로 `bb`/`be` 를 차단하는 회귀다.
- 현황/환경 분석 (코드 기준):
  1. [tools.py:65-80](../../feature-0002-agent-core/src/modules/tools.py#L65-L80) `_extract_sql_schema_refs` — module-level lazy compile, finditer 로 전체 SQL 을 훑는다. 컨텍스트 구분이 없어 `WHERE bb.BattleType = 'X'` / `SELECT be.Star, be.Time` / `ORDER BY bb.StartTime` 등 alias.column 이 모두 매칭된다.
  2. 이 함수의 소비자는 [tools.py `_tool_execute_sql` / `_tool_explain_query`](../../feature-0002-agent-core/src/modules/tools.py#L83-L105) 의 `_whitelist_violation(refs)` 단일 경로. `describe_schema` / `describe_table` / `search_tables` / `get_sample_rows` / `get_table_indexes` / `get_foreign_keys` / `list_schemas` 는 이미 `{ schema_arg }` 1 건만 전달하므로 영향이 없다.
  3. MySQL 문법상 `schema.table` 을 쓸 수 있는 위치는 **FROM 절 / JOIN 절 / DELETE FROM / INSERT INTO / UPDATE / CREATE TABLE `s`.`t` / ALTER TABLE / TRUNCATE / INDEX reference** 등 DDL/DML 대상 지정 구간이다. agent 는 `execute_sql` 이 read-only SELECT 전용이므로 실사용 범위는 **FROM {schema}.{table} [alias]**, **JOIN {schema}.{table} [alias]**, **FROM/JOIN 연속 comma list `{s1}.{t1}, {s2}.{t2}`** 3 가지로 좁혀진다.
  4. WHERE/SELECT/GROUP BY/ORDER BY/ON 조건에 나오는 `x.y` 는 반드시 alias 또는 unqualified table → column 참조로, schema 의미가 없다. 따라서 "`FROM`/`JOIN`/`,` 직후에 위치한 `x.y`" 만 `schema.table` 로 간주하면 오탐이 제거된다.
  5. Edge case:
     - 중첩 서브쿼리 `FROM (SELECT ... ) t1 JOIN dblog.battlebegin bb ...` — `JOIN dblog.battlebegin` 은 여전히 매칭. 서브쿼리 내부의 `FROM dbgame.items` 도 독립적으로 매칭. 이상 없음.
     - `INSERT INTO` / `UPDATE` / `DELETE FROM` — read-only 전제라 발생하지 않지만, 보수적으로 `FROM|JOIN|,` 만 보되 향후 필요 시 확장 가능하게 둔다.
     - 백틱 `` FROM `dblog`.`battlebegin` `` — 공백/백틱 허용.
     - 대소문자 `from`/`From`/`FROM` — `IGNORECASE` 필요.
     - 주석 `/* ... */`, 문자열 리터럴 `'dblog.table'` 내부 — 현재 구현도 별도 처리 없음(기존 과탐/과누락 동등). 범위 외.
  6. test runner 의 기존 실패 아티팩트는 `tests/task0034_runs/api-Q4.failed.whitelist_regex.20260422.json` 으로 보관 중 (2026-04-22 세션 내 이동).
- 설계 (실구현 기준):
  1. **1 차안의 한계** — `FROM|JOIN|,` 세 가지 prefix 만 정규식으로 요구하는 방안은 `SELECT bb.BattleType, be.Star FROM dblog.t bb JOIN dblog.u be ON ...` 같은 SQL 에서 SELECT 절의 `, be.Star` 를 comma-join 으로 오탐해 `be` 가 schema 로 추출되는 새 회귀를 만든다(실제 테스트 2026-04-22 에서 확인). SELECT 절 쉼표와 FROM 절 쉼표를 단일 정규식만으로는 구분할 수 없다.
  2. **2 단계 스캐너로 확정** — [tools.py:65-99](../../feature-0002-agent-core/src/modules/tools.py#L65-L99) 를 table-list 구간 슬라이스 + 내부 schema.table 추출 2 단계로 재구현.
     ```python
     _TABLE_LIST_RE = _re.compile(
         r"\b(?:FROM|JOIN)\b(.*?)"
         r"(?=\bON\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b"
         r"|\bLIMIT\b|\bUNION\b|\bJOIN\b|\bFROM\b|;|\)|$)",
         _re.IGNORECASE | _re.DOTALL,
     )
     _INNER_REF_RE = _re.compile(
         r"`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\.\s*`?([A-Za-z_][A-Za-z0-9_]*)`?",
     )
     # 1) FROM|JOIN 키워드 뒤 table-list 구간을 모두 잘라낸 뒤
     # 2) 그 내부에서만 schema.table 을 반복 추출
     ```
     - 바깥 정규식이 `FROM`/`JOIN` 뒤 table-list 구간을 lookahead terminator 로 경계 설정: `ON` / `WHERE` / `GROUP BY` / `ORDER BY` / `HAVING` / `LIMIT` / `UNION` / 다음 `FROM`·`JOIN` / `;` / `)` / EOS.
     - 안쪽 정규식은 그 구간 안에서만 동작하므로 SELECT/WHERE/ON/ORDER/GROUP 절의 `alias.column` 은 애초에 스캔 영역 밖.
     - FROM 뒤 comma join(`FROM a.x, b.y`) 은 자연스럽게 수용됨 — 콤마가 같은 FROM 슬라이스 내부이므로 두 스키마 모두 `_INNER_REF_RE` 에 매칭.
     - 대소문자 무시(`IGNORECASE`), 다중 라인 쿼리(`DOTALL`) 수용.
  3. **테스트 매트릭스 (15 케이스)** — in-process 호출로 다음 기대치를 모두 확인한다. (TASK-0040 구현 직후 실제 실행 결과 포함)
     - `SELECT bb.BattleType FROM dblog.battlebegin bb JOIN dblog.battleend be ON be.AcntNo = bb.AcntNo` → `{dblog}` ✓ (기존 오탐: `{dblog, bb, be}`)
     - `SELECT * FROM dbgame.items i WHERE i.type='x'` → `{dbgame}` ✓
     - `SELECT * FROM dblog.battlebegin bb, dblog.battleend be WHERE bb.Id = be.Id` (comma join) → `{dblog}` ✓
     - `` SELECT * FROM `dblog`.`battlebegin` bb `` (백틱) → `{dblog}` ✓
     - `SELECT * FROM (SELECT 1 AS x) t JOIN dbgame.items i ON i.id=t.x` (서브쿼리) → `{dbgame}` ✓
     - `select * from dblog.t` (lower) → `{dblog}` ✓
     - `SELECT 1` (no FROM) → `∅` ✓
     - `SELECT bb.x FROM bb` (alias only) → `∅` ✓
     - `SELECT * FROM dbstat.foo` (비허용 스키마) → `{dbstat}` → 차단 ✓
     - `SELECT bb.BattleType, be.Star FROM dblog.battlebegin bb JOIN dblog.battleend be ON be.AcntNo = bb.AcntNo WHERE bb.BattleType = 'CROSSROUTE' AND be.Star >= 3` (Q4-like) → `{dblog}` ✓
     - `SELECT * FROM dbgame.t INNER JOIN dblog.u ON t.a=u.a LEFT JOIN dbauth.v ON v.a=t.a` (3-way JOIN) → `{dbgame, dblog, dbauth}` ✓
     - `SELECT * FROM a.x, b.y WHERE 1=1` (2-way comma join) → `{a, b}` ✓
     - `SELECT * FROM dblog.orders o GROUP BY o.user ORDER BY o.date` (GROUP/ORDER terminators) → `{dblog}` ✓
     - `SELECT col1, col2, tbl.col3 FROM sch.tbl tbl WHERE tbl.x > 5 ORDER BY tbl.y` (SELECT 절 쉼표 + alias 함정) → `{sch}` ✓
     - `WITH x AS (SELECT * FROM a.b) SELECT * FROM x` (CTE) → `{a}` ✓
     - 보안 비회귀: `SELECT * FROM dblog.t LEFT JOIN dbstat.u ON t.a=u.a` → `{dblog, dbstat}` → whitelist 차단 ✓
  3. **범위 제한** — 코드 변경은 `unit/feature-0002-agent-core/src/modules/tools.py` 1 파일 약 5 줄. tool 시그니처·호출처·기타 모듈 수정 없음. `execute_sql` 외 tool 은 호출 인자 레벨에서 schema 가 이미 들어오므로 정규식과 독립이다.
  4. **회귀 방어** — 기존 TASK-0036 원안(REV-20260421-0004) 의 "모듈 전역 + finally" 패턴은 변경하지 않는다. Product whitelist 로 차단해야 하는 비허용 user schema (예: `SELECT * FROM dbstat.foo`) 는 새 정규식에서도 `FROM dbstat.foo` 매칭으로 포착되어 여전히 차단된다.
- 검증:
  1. `python3 -m py_compile unit/feature-0002-agent-core/src/modules/tools.py` 문법.
  2. `docker compose up -d --build --force-recreate web` 후 위 테스트 매트릭스 8 케이스 in-process 호출 통과.
  3. `_whitelist_violation({'dblog', 'bb'})` → 기존 블로킹 메시지 반환, `_whitelist_violation({'dblog'})` + `set_active_schema_allowlist(['dbauth','dbgame','dblog'])` → `None`. 즉 정규식 출력이 올바르면 `_whitelist_violation` 은 변경 없이 통과/차단 판정이 정상.
  4. `python3 tests/task0034_runner.py --target api --only Q4,Q5` — TASK-0041 완료 후 최종 재수행. 이 시점에서는 whitelist regression 가 제거된 상태에서 Q4/Q5 가 전 턴 정상 응답/도구 호출을 수행하는지를 1 차 smoke 로 본다 (정답 내용 검증은 TASK-0034 보고서 업데이트 단계에서).
- 완료 조건:
  - TASK.md §2 / §3 업데이트 + TASK-0040 상세 설계 블록
  - tools.py 정규식 교체 + in-process 8 케이스 테스트 통과
  - Q4 재수행에서 whitelist 위반이 더 이상 발생하지 않음 확인 (최소 1 턴 정상 tool 호출 성공)
  - MODIFY.md 에 CHG-20260422-0013 append
  - REVIEW.md 는 추가 불필요(REV-20260421-0004 의 결정 틀 유지, 정규식 세부는 코드 주석 + 본 설계 블록으로 충분)
  - LEARNINGS.md 에 `LRN-20260422-0012 SQL 텍스트 스캔은 컨텍스트 조건(FROM|JOIN|,) 없이는 alias.column 과 schema.table 을 구분할 수 없다` append
  - REPORT.md §3 에 TASK-0040 한 줄 추가

### TASK-0041 상세 설계 (2026-04-22)
- 문제/목적 (사용자 지시 2026-04-22): 상용 API `gpt-5.4-mini` 가 복잡 질의에 응답하는 데 최대 15 분 이상 소요되는 실사용 워크로드에서, 서버 `run_timeout_sec=900s` 이전이라도 **(a) 브라우저 탭 닫힘/새로고침**, **(b) 테스트 러너 httpx `ReadTimeout` (960s)**, **(c) 네트워크 일시 단절** 같은 사유로 클라이언트 연결이 끊겨도 agent 스레드는 `asyncio.to_thread(_run_agent_core, ...)` 의 worker 에서 계속 실행된다. 그러나 현재 웹 UI 와 test runner 는 끊어진 요청에 대해 "실패" 상태만 보이고 `AgentMemoryKv.last_status` / `AgentMemoryMessages.assistant` 에 뒤늦게 기록되는 결과를 회수할 공식 경로가 없다. 사용자 입장에서는 "이미 시작된 턴을 계속 기다릴지 / 즉시 포기할지" 를 다시 선택할 수 있어야 하고, 테스트 러너 입장에서는 timeout 직후 동일 대화의 결과를 폴링해 최종 응답이 도착하면 이후 턴을 정상 진행해야 한다.
- 현황/환경 분석 (코드 기준):
  1. [app.py `/api/ask`](../src/app.py#L3520) 는 `asyncio.to_thread(_run_agent_core, ...)` 로 agent 를 돌리고, 완료되면 `AgentMemoryKv.set_run_status('done'|'error'|'canceled', run_id=...)` + `AgentMemorySteps` + `AgentMemoryMessages` 에 persistence 가 이뤄진다(실제 상태값 참조: [agent_core.py:1542](../../feature-0002-agent-core/src/agent_core.py#L1542) `done` / L1537 `error` / L1524 `canceled`, `processing` 이 running). HTTP 응답이 나가기 전에 client 가 끊겨도 to_thread 는 cancel 되지 않으므로 최종 결과는 DB 에 저장된다(검증: `finally` 블록 + `set_run_status('done', ...)` 순서).
  2. [app.py `/api/progress`](../src/app.py#L4381) 는 이미 `(status, status_at, run_id, steps, step_count)` 를 반환한다. 그러나 `steps` 만 내려가고, 최종 `assistant` 메시지(`_load_latest_assistant_message`) 나 `last_error` / `last_duration_ms` 는 별도 응답에 없어 브라우저는 `/api/history` 를 재-GET 해 메시지 목록을 다시 당겨야 한다. Test runner 에는 이 경로가 구성돼 있지 않다.
  3. [app.py `/api/cancel`](../src/app.py#L4296), [app.py `/api/finalize`](../src/app.py#L4338) 는 `AgentMemoryKv.mark_cancel_requested` / `mark_finalize_requested` 로 **KV 플래그만 세팅** 하고 agent loop 가 step 경계마다 플래그를 체크해 self-terminate 하는 패턴이다. 본 TASK 는 이 기존 신호 경로를 유지·활용한다(새 플래그 없음).
  4. [memory.py `set_run_status`](../../feature-0002-agent-core/src/modules/memory.py#L920~L1030) 에 `last_status` / `last_status_run_id` / `last_status_at` / `last_duration_ms` / `last_error` 5 키가 이미 persist 된다. `is_processing_conversation(cid)` 헬퍼도 존재. 새 테이블/컬럼 추가 없이 status 를 읽을 재료가 전부 있다.
  5. [task0034_runner.py:186-204](../tests/task0034_runner.py#L186-L204) 의 httpx.ReadTimeout 브랜치는 현재 `{"error": "client-read-timeout"}` 턴을 추가하고 즉시 다음 턴으로 넘어간다 — 실행 중이던 agent 는 서버에서 계속 돌고, 완료 후에도 runner 는 조회하지 않는다.
  6. [app.py WEB_PARALLEL_LIMIT=6](../src/app.py) — 계정당 동시 `/api/ask` 슬롯은 6. attach/resume 엔드포인트는 read-only 이므로 이 슬롯을 점유하지 않아야 한다(중요 설계 제약).
- 설계:
  1. **신규 엔드포인트 `GET /api/ask_status`** — read-only 스냅샷. Query: `conversation_id`. 응답:
     ```json
     {
       "conversation_id": "20260422-...",
       "is_processing": true|false,
       "status": "processing|done|error|canceled|(empty)",
       "status_at": "2026-04-22T01:23:45Z",
       "run_id": "...",
       "step_count": 7,
       "duration_ms": 123456,
       "error": null | "...",
       "has_answer": true|false,    // latest assistant message at or after run_id 존재 여부
       "answer_preview": null | "첫 160자 미리보기 ..."
     }
     ```
     내부 구현은 기존 `_load_progress_status(conn, cid)` + `_load_step_count_for_run` + `_load_latest_assistant_message(conn, cid, role='assistant')` 헬퍼를 재사용하며, 슬롯 카운터는 건드리지 않는다. 권한: 해당 대화에 대한 `conversation.read.own/any`.
  2. **신규 엔드포인트 `GET /api/ask_result`** — long-poll. Query: `conversation_id`, `run_id`(optional — 특정 run 지정), `wait`(초, 기본 30, 최대 60). 로직:
     - `t0 = time.monotonic()` 시점의 status 를 `_load_progress_status` 로 읽는다.
     - `run_id` 가 명시된 경우: 서버의 `last_status_run_id` 가 그 run_id 이고 status ∈ {done, error, canceled} 이면 즉시 200 반환.
     - `run_id` 미지정: 현재 status 가 terminal 이면 즉시 반환.
     - 그 외에는 `await asyncio.sleep(0.5)` 루프를 돌며 최대 `wait` 초 동안 polling. 매 반복마다 status 재조회. Terminal 상태 진입 시 즉시 반환.
     - 타임아웃까지 terminal 도달 안 하면 `{"timeout": true, "status": "processing", "run_id": "...", "step_count": N}` 반환.
     - Terminal 도달 시 응답에 `{"status": "...", "run_id": "...", "duration_ms": ..., "error": ..., "assistant": {"message_id": 123, "content": "...", "meta": {...}, "steps_count": N}}` 포함. `assistant.content` 는 full. 권한은 위와 동일.
     - 슬롯 카운터 미점유 확인: `/api/ask` 의 `async with _acquire_account_slot(...)` 블록 외부에서 실행.
     - 내부 구현은 `asyncio.sleep` 기반 polling 이라 background task 추가 없음 → 복잡도 최소.
  3. **브라우저 UX (`src/static/app.js`)** —
     - `sendPrompt()` 내부에서 `fetch('/api/ask', ...)` 의 AbortController `timeoutMs = PROGRESS_MAX_SESSION_MS (예: 900_000ms)` 로 기본값 조정. 기존보다 길게.
     - `fetch` 가 `AbortError` / `TypeError: Failed to fetch` / HTTP 504/502 로 떨어지면 `/api/ask_status?conversation_id=CID` 를 호출해 `is_processing=true` 가 돌아올 때 **다이얼로그 `showTimeoutRecoveryDialog(conversation_id, run_id)`** 를 띄운다. 버튼: `[ 계속 기다리기 ]` / `[ 즉시 답변 ]` / `[ 요청 취소 ]`.
       - **계속 기다리기**: `/api/ask_result?conversation_id=...&run_id=...&wait=60` 을 background 에서 polling. terminal 반환 시 `refreshWorkspace(cid)` + 토스트. UI 에는 기존 progress polling 루프가 계속 동작(TASK-0037 의 `scheduleProgressPolling`).
       - **즉시 답변**: `POST /api/finalize` (기존 기능) → 이후 terminal 도달까지 `/api/ask_result` long-poll.
       - **요청 취소**: `POST /api/cancel` (기존) → 이후 terminal 도달까지 `/api/ask_result` long-poll 후 cancelled 결과 반영.
     - 페이지 로드(bootstrap) 또는 대화 전환 시, 선택된 대화의 `/api/ask_status` 를 1 회 호출해 `is_processing=true` 면 자동으로 attach mode 에 들어간다(브라우저를 껐다 켜도 이전 턴을 이어서 관찰).
     - 기존 `PROGRESS_POLL_*` 상수와 충돌하지 않도록 `/api/ask_result` 호출은 **별도 single-flight in-flight 플래그** (`state.resultWaitInFlight` Set by conversation_id) 로 관리.
  4. **Test runner (`tests/task0034_runner.py`) attach/resume** —
     - 현재 `httpx.ReadTimeout` 브랜치를 `{"error": "client-read-timeout", "attached": true}` 기록으로 남기되, 즉시 다음 턴으로 넘어가지 않고 아래 루프로 전환:
       - `attach_deadline = time.monotonic() + ATTACH_TIMEOUT_SEC` (기본 900.0, .env override `TASK0034_ATTACH_TIMEOUT_SEC`).
       - 루프: `resp = await client.get('/api/ask_result', params={'conversation_id': cid, 'run_id': rid, 'wait': 45})`. terminal 응답이면 기록 후 루프 종료. `{timeout: true}` 면 계속. `attach_deadline` 초과 또는 HTTP 오류 2 회 연속 시 fallback 으로 `{"error": "attach-timeout"}` 기록 후 다음 턴 진행.
       - `run_id` 는 timeout 직후 `/api/ask_status` 1 회 호출로 획득해 고정. 그래야 같은 대화의 "다음 run" 이 아니라 현재 돌던 run 의 결과만 기다린다.
     - 성공적으로 attach 된 경우 turn 객체에 `status="succeeded-via-attach"` + `attached_after_timeout=true` + 원본 steps/assistant 를 삽입해 이후 truth 대조 단계가 일반 턴과 동일하게 동작하도록 한다.
  5. **에러/보안 고려**:
     - `/api/ask_status`, `/api/ask_result` 모두 **read-only**. write 경로 없음. `mark_cancel_requested` / `mark_finalize_requested` 는 기존 `/api/cancel` / `/api/finalize` 를 그대로 사용 — 본 TASK 에서 새 side-effect 경로 도입 금지.
     - 슬롯 카운터 비점유: attach/resume 은 별도 계정에서도 호출 가능하지만 `conversation.read.*` 권한 만으로 충분. `/api/ask` 는 여전히 `conversation.ask` 소유자 제한 유지.
     - long-poll `wait` 상한 60 초로 한정해 느린 로드밸런서/ingress 타임아웃과 충돌 방지.
  6. **범위 제한**:
     - 서버 변경은 `src/app.py` 에 2 개 엔드포인트 + 기존 헬퍼 재사용(새 SQL/테이블/마이그레이션 없음).
     - 브라우저 변경은 `src/static/app.js` + `src/static/index.html` 의 다이얼로그 마크업 + `src/static/styles.css` 의 다이얼로그 스타일.
     - Test runner 변경은 `tests/task0034_runner.py` 의 ReadTimeout 브랜치 확장 + `ATTACH_TIMEOUT_SEC` 상수 추가.
     - 기존 `/api/cancel` / `/api/finalize` / `/api/progress` / `/api/ask` 시그니처는 변경하지 않는다.
- 검증:
  1. **문법**: `python3 -m py_compile src/app.py tests/task0034_runner.py`, `node --check src/static/app.js`.
  2. **컨테이너 재빌드**: `docker compose up -d --build --force-recreate web`.
  3. **단순 동작**: bootstrap_admin 로그인 → 새 대화 → 빠른 질의(`/api/ask`, 5초 완료) 실행 중에 `curl .../api/ask_status?conversation_id=...` 가 `is_processing=true|false` 및 terminal `status` 를 반환.
  4. **long-poll**: `curl .../api/ask_result?conversation_id=...&wait=5` 가 이미 terminal 이면 즉시 200, processing 이면 5 초 `{timeout:true}` 반환.
  5. **브라우저**: 일부러 `/api/ask` 를 AbortController 로 2 초 뒤 중단 → 다이얼로그 출현 → `계속 기다리기` 클릭 → agent 완료 후 메시지가 UI 에 주입.
  6. **Runner attach**: `ASK_TIMEOUT_SEC=10.0` 로 일시 축소한 후 `--only Q4` 로 돌려 runner 가 timeout → attach → 최종 turn 기록까지 이동하는지 확인. 정상 확인 후 960s 로 원복.
  7. **TASK-0034 재수행**: TASK-0040 선 완료 + 본 TASK 완료 상태에서 `python3 tests/task0034_runner.py --target api --only Q4,Q5` 를 돌려 whitelist regression + timeout attach 두 경로 모두 정상 동작함을 입증.
- 완료 조건:
  - TASK.md §2 / §3 / TASK-0041 상세 설계
  - app.py `/api/ask_status` + `/api/ask_result` 추가, 문법·컨테이너 재빌드 통과
  - app.js 다이얼로그 + attach polling + bootstrap attach 연결
  - index.html / styles.css 다이얼로그 마크업·스타일
  - task0034_runner.py attach 분기
  - 검증 항목 1-7 모두 통과
  - MODIFY.md 에 CHG-20260422-0014 append
  - REVIEW.md 에 REV-20260422-0007 append (장기 실행 에이전트에 대한 read-only attach/resume 패턴 채택 이유)
  - FUNCTION.md 의 API 목록에 `/api/ask_status`, `/api/ask_result` 추가
  - REPORT.md §3 에 TASK-0041 한 줄 추가
  - LEARNINGS.md 에 `LRN-20260422-0013 장기 실행 worker 는 client disconnect 과 agent finalize 경로가 독립적이어야 한다` append

### TASK-0039 상세 설계 (2026-04-22)
- 문제/목적 (사용자 지시 2026-04-22): TASK-0036 이 `_whitelist_violation` 에서 `_SYSTEM_SCHEMAS` 통째 bypass 를 제거하면서 `mysql` / `performance_schema` / `sys` 를 기본 차단했지만, 실사용 중 "assistant 가 Product DB 의 테이블 구조를 찾지 못하는" 문제가 발견됐다. 원인: agent 가 본능적으로 `information_schema.TABLES` 외에 `sys.schema_table_statistics`, `performance_schema.tables`, 드물게 `mysql.*` 을 함께 조회해 교차 검증하려 하는데 이들이 전부 차단되면 재시도 루프에 빠지거나 `describe_schema` 만 반복하게 된다. 사용자는 메타데이터 4 종을 **Product 설정에 명시하지 않아도 항상 접근 가능** 하게 해달라고 요청했다. **`agent_memory` 는 예외** — 여기엔 다른 계정의 대화 내용, 세션, 권한 override 가 담겨 있어 여전히 차단 유지.
- 현황/환경 분석 (코드 기준):
  1. [tools.py:25-28](../../feature-0002-agent-core/src/modules/tools.py#L25-L28) `_SYSTEM_SCHEMAS` 는 `{information_schema, mysql, performance_schema, sys, agent_memory}` 5 종 frozenset. 이 집합은 두 용도로 쓰인다:
     - [tools.py:51-57](../../feature-0002-agent-core/src/modules/tools.py#L51-L57) `_is_user_schema(name)` — `list_schemas` 결과 post-filter 와 `search_tables` 의 `sys_exclude` 조건에서 "사용자 스키마가 아님" 판정. UX 용도.
     - [tools.py:78-94](../../feature-0002-agent-core/src/modules/tools.py#L78-L94) `_whitelist_violation(refs)` — agent tool 레벨 접근 차단 결정. Security 용도.
  2. 현재 `_whitelist_violation` 은 `allowed = _ACTIVE_SCHEMA_ALLOWLIST | {information_schema}` 로 **information_schema 1 종만** bypass. 나머지 `sys`/`mysql`/`performance_schema`/`agent_memory` 는 whitelist 에 명시적으로 등록하지 않으면 차단.
  3. `_is_user_schema` 는 `_SYSTEM_SCHEMAS` 에 포함된 스키마를 전부 "사용자 스키마 아님" 으로 판정해 `list_schemas` 결과에서 숨기는 UX 동작을 한다. 이건 사용자의 요청 의도("목록 내 유무와 관계없이 **접근** 가능") 와 무관하게 유지해도 된다 — agent 는 `describe_schema('information_schema')` / `execute_sql("SELECT ... FROM information_schema...")` 로 명시 호출이 가능하고, `list_schemas` 결과에 카탈로그 스키마를 섞어 보여주는 건 오히려 탐색 노이즈.
  4. [tools.py:451](../../feature-0002-agent-core/src/modules/tools.py#L451) `search_tables` 의 `sys_exclude` 도 `_SYSTEM_SCHEMAS` 전체를 WHERE NOT IN 으로 제외 — 키워드 검색이 메타데이터 테이블을 섞어 반환하면 결과가 지저분해지므로 이 동작도 유지.
- 설계:
  1. **스키마 상수를 두 카테고리로 분리** — [tools.py:24-28](../../feature-0002-agent-core/src/modules/tools.py#L24-L28):
     ```python
     # 메타데이터 스키마 — Product whitelist 와 무관하게 agent tools 가 항상 접근 가능.
     # DB 구조 탐색(정의·통계·런타임 메트릭) 에 필요해 기본 허용한다.
     _METADATA_SCHEMAS = frozenset({"information_schema", "mysql", "performance_schema", "sys"})
     # 에이전트 내부 스키마 — whitelist 로 차단 유지. 타 계정 대화/세션/권한 데이터 보호.
     _INTERNAL_SCHEMAS = frozenset({"agent_memory"})
     # 기존 호환: list_schemas/search_tables 의 "사용자 스키마 아님" 판정에 사용.
     _SYSTEM_SCHEMAS = _METADATA_SCHEMAS | _INTERNAL_SCHEMAS
     ```
  2. **`_whitelist_violation` bypass 집합 교체** — [tools.py:78-94](../../feature-0002-agent-core/src/modules/tools.py#L78-L94):
     - `allowed = set(_ACTIVE_SCHEMA_ALLOWLIST) | {"information_schema"}` → `allowed = set(_ACTIVE_SCHEMA_ALLOWLIST) | _METADATA_SCHEMAS`
     - 결과: agent 가 `execute_sql("SELECT ... FROM mysql.user")`, `describe_schema("sys")`, `describe_table("performance_schema", "tables")` 류 호출을 시도하면 Product 설정과 무관하게 통과.
     - `agent_memory` 는 `_METADATA_SCHEMAS` 에 없으므로 기존처럼 차단.
     - 비허용 user schema (예: 임의의 `dbstat`) 도 기존처럼 차단.
     - 에러 메시지에 "메타데이터 스키마(`information_schema`/`sys`/`mysql`/`performance_schema`) 는 항상 접근 가능" 한 줄을 덧붙여, LLM 이 차단된 user schema 를 메타데이터 쿼리로 리디렉션할 수 있는 힌트 제공.
  3. **`_is_user_schema` / `search_tables` 는 그대로 유지** — `list_schemas` 결과에 메타데이터 4 종 노출 여부는 UX 결정 영역이고 현재는 숨김이 더 자연스럽다. agent 는 시스템 프롬프트의 KNOWN SCHEMAS 힌트 없이도 `execute_sql` 로 `information_schema.TABLES` 를 직접 조회할 수 있어 구조 탐색에 문제가 없다.
- 보안 고려 (REV-20260422-0006 으로 문서화):
  1. `mysql.user` 등이 bypass 경로를 타게 되지만, **DB 커넥터가 사용하는 MySQL 계정에 `mysql.*` SELECT 권한이 없으면 실행 단계에서 차단** 된다. whitelist 는 tool-레벨 1 차 방어이고 MySQL GRANT 가 2 차 방어로 남는다.
  2. `performance_schema` / `sys` 는 민감도 낮음(런타임 stat + 뷰).
  3. `information_schema` 는 원래부터 허용돼 있었다.
  4. 이 완화는 **현 리포의 agent read-only SQL 특성** 을 전제로 한다. write 가능 계정을 agent 가 쓰게 된다면 이 결정을 재검토해야 한다.
- 검증:
  1. `python3 -m py_compile unit/feature-0002-agent-core/src/modules/tools.py` → 문법.
  2. `docker compose up -d --build web` 후 컨테이너 내부에서 직접 호출:
     ```python
     from modules.tools import set_active_schema_allowlist, _whitelist_violation
     set_active_schema_allowlist(["dbgame"])
     assert _whitelist_violation({"mysql"}) is None
     assert _whitelist_violation({"sys"}) is None
     assert _whitelist_violation({"performance_schema"}) is None
     assert _whitelist_violation({"information_schema"}) is None
     assert _whitelist_violation({"dbgame"}) is None
     assert "agent_memory" in (_whitelist_violation({"agent_memory"}) or "")
     assert "dbstat" in (_whitelist_violation({"dbstat"}) or "")
     ```
  3. 실사용 스모크: bootstrap_admin 로그인 → 새 대화(Product=KR) → `/api/ask` 로 "information_schema 에서 dbgame 의 테이블 개수" → 성공 응답.
  4. 회귀 방어: whitelist 미설정 상태(`_ACTIVE_SCHEMA_ALLOWLIST is None`) 에서는 `_whitelist_violation` 이 즉시 `None` 반환하는 경로가 유지됨(코드 L80-L81).
- 범위 제한:
  - 코드 변경은 `unit/feature-0002-agent-core/src/modules/tools.py` 한 파일(약 10 줄).
  - `_is_user_schema` / `search_tables` / `list_schemas` UX 동작은 손대지 않는다.
  - 시스템 프롬프트의 "KNOWN SCHEMAS" 블록 포맷도 손대지 않는다 — agent 가 이미 information_schema 경로를 잘 찾는다.
- 완료 조건:
  - TASK.md §2 / §3.1 / 상세 설계 블록 추가
  - tools.py 반영 + in-process 테스트 통과
  - MODIFY.md 에 `CHG-20260422-0012` append
  - REVIEW.md 에 `REV-20260422-0006` append (REV-20260421-0005 supersede 관계 명시)
  - FUNCTION.md AC-0010 보강
  - REPORT.md §3 에 TASK-0039 한 줄 추가
  - git commit + push

### TASK-0038 상세 설계 (2026-04-22)
- 문제/목적 (사용자 지시 2026-04-22, TASK-0034 Q4/Q5 원인 분석 후): Q4 conversation `20260421084441-6b71b1b1` 은 대화 생성(17:44:41) → step 1 `execute_sql` 실패(17:44:46) → step 2/3 `describe_table` 완료(17:44:48) 후 10분 공백 후 클라이언트 600s read-timeout 으로 종료됐다. DB 에는 `assistant` 메시지가 0 건, run_id 가 1 개만 존재해 **turn 1 의 agent 가 LLM 호출 단계에서 무한 대기** 한 것으로 판정됐다. 그 사이 클라이언트는 먼저 포기했지만 서버 thread pool 은 해당 스레드를 계속 물고 있어 Q4 turn 2 는 persist 이전에 풀 경쟁에 막혔고, Q5 는 60s 안에 `/api/auth/login` ConnectTimeout 으로 실패했다.
- 현황/환경 분석 (코드 기준):
  1. `agent_core.py:1134` `client = OpenAI(**client_kwargs)` — OpenAI Python SDK v1 은 `timeout` 인자가 없으면 내부 httpx 기본(연결당 10 분 수준) 을 쓰되, 실제로는 서버가 SSE 스트림을 끊지 않는 한 무한 대기한다. `chat.completions.create(...)` 호출([L999](../../feature-0002-agent-core/src/agent_core.py#L999)) 도 per-request timeout 을 지정하지 않는다.
  2. `modules/llm.py` 는 이미 `_get_openai_client(timeout_sec=...)` 헬퍼에서 `timeout + max_retries + ThreadPoolExecutor wall-clock deadline` 패턴을 구현해 뒀다([llm.py:482~529](../../feature-0002-agent-core/src/modules/llm.py#L482)) — 동일한 상한 개념을 `agent_core.py` 의 메인 루프 클라이언트에도 적용하기만 하면 된다. 최소 변경 원칙으로 `modules/llm.py` 를 통째 재사용하는 대신 `OpenAI(...)` 초기화에 `timeout`/`max_retries` 만 얹는 것으로 제한한다.
  3. `modules/config.py:283` `AGENT_OPENAI_MAX_RETRIES=int(os.getenv("AGENT_OPENAI_MAX_RETRIES","0"))` 는 이미 존재하므로 환경변수 계약을 깨지 않는다. `.env` 에는 기본값 미설정 → 0 (재시도 비활성).
  4. `agent_core.py:1255~1258` `run_timeout_sec = max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)`. `.env` 에는 `AGENT_TIMEOUT_SEC=300, AGENT_EARLY_FINALIZE_MS=180000` 이므로 `run_timeout_sec = max(900, 180) = 900s` 고정.
  5. 러너 `task0034_runner.py:52` `ASK_TIMEOUT_SEC=600.0` → httpx client 의 per-request timeout. 600 < 900 이므로 클라이언트가 항상 서버보다 먼저 포기한다.
- 설계:
  1. **agent_core `OpenAI` 초기화에 timeout/max_retries 반영** — [`agent_core.py:26~32`](../../feature-0002-agent-core/src/agent_core.py#L26) 의 `from modules.config import` 에 `AGENT_OPENAI_MAX_RETRIES` 를 추가. [L1134](../../feature-0002-agent-core/src/agent_core.py#L1134) `client = OpenAI(**client_kwargs)` 를 `OpenAI(**client_kwargs, timeout=max(5, int(AGENT_TIMEOUT_SEC)), max_retries=max(0, int(AGENT_OPENAI_MAX_RETRIES)))` 로 확장. 개별 `chat.completions.create` 호출은 그대로 두되, client-level timeout 이 httpx transport 에 상속되므로 모든 호출에 wall-clock 상한이 걸린다.
  2. **test runner ASK_TIMEOUT_SEC 인상** — `tests/task0034_runner.py:52` `ASK_TIMEOUT_SEC = 600.0` 을 `ASK_TIMEOUT_SEC = 960.0` 으로 변경. 주석으로 "`> run_timeout_sec=900`" 근거를 명시. 다른 타임아웃(`httpx.AsyncClient(timeout=60.0)` 기본값) 은 fast endpoint 전용이므로 손대지 않는다.
  3. **환경변수 override 경로는 유지** — `AGENT_TIMEOUT_SEC` / `AGENT_OPENAI_MAX_RETRIES` 모두 `os.getenv` 로 오버라이드 가능. 운영에서 더 짧게(예: 90s) 조이고 싶으면 .env 만 바꾸면 된다.
- 검증:
  1. `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/tests/task0034_runner.py` → 문법 체크.
  2. `grep -nE "OpenAI\(.*timeout" unit/feature-0002-agent-core/src/agent_core.py` 가 L1134 를 반환하는지 확인.
  3. `grep -n "ASK_TIMEOUT_SEC" unit/feature-0003-agent-web-ui/tests/task0034_runner.py` 에서 960.0 확인.
  4. `docker compose up -d --build web` → 신규 이미지 기동, `/api/session` 200 OK, bootstrap_admin 로그인 성공, `/api/new_conversation` + `/api/ask` 로 짧은 질의("SHOW DATABASES;" 수준) 가 정상 응답하는지 in-host curl 로 확인.
  5. 의도적 timeout 유발: 로컬 환경에서 AGENT_TIMEOUT_SEC=3 + 긴 질의로 `openai.APITimeoutError` 가 step error 로 흡수되는지 (기존 `try/except Exception` 경로가 삼키는지) 확인 — 단, prod .env 에 영향이 없도록 임시 override 만 사용.
- 범위 제한:
  - 코드 변경은 `agent_core.py`(2줄: import + OpenAI() 확장) 와 `task0034_runner.py`(1줄) 로 제한.
  - 원인 분석 3(질문 follow_up trigger 확장) / 4(러너 격리/쿨다운) 는 본 TASK 범위 외. TASK-0034 재실행 단계에서 별도 처리.
  - `modules/llm.py` 의 `_openai_chat_completion_with_deadline` 패턴 통합 리팩터는 위험도/변경폭이 커 별도 TASK 로 분리.
- 완료 조건:
  - TASK.md §2 / §3.1 / 상세 설계 블록 추가
  - agent_core.py + task0034_runner.py 반영
  - `docker compose up -d --build web` 후 `/api/session` probe 통과
  - MODIFY.md 에 `CHG-20260422-0011` append
  - REPORT.md §3 에 TASK-0038 한 줄 추가
  - git commit + push

### TASK-0037 상세 설계 (2026-04-22)
- 문제/목적 (사용자 보고 2026-04-22 01:07 KST): TASK-0034 복잡 QA 성능 테스트(상용 API gpt-5.4-mini, 대화당 ~3분/턴) 를 돌리면서 브라우저 탭을 열어두면 `/api/progress` 요청이 지속적으로 쌓이는 현상이 관찰됐다. 이 "폴링이 끝없이 요구되는" 증상은 다른 작업자 AI 가 TASK-0036 PR 에 같이 묶어 해결(27127b9)한 상태라, 본 세션에서는 **수정 내용을 리뷰하고 설계·학습 문서에 반영**하는 것이 목표다.
- 현황/환경 분석 (수정 전 코드 기준):
  1. `src/static/app.js` 의 폴링 루프는 `setInterval(pollProgress, 1500)` 단일 `state.progressPoller` 핸들로 동작했다. `pollProgress()` 는 fetch 후 await 하는데, `/api/progress` 응답이 느리면 다음 `setInterval` tick 이 먼저 발화해 **동시 in-flight 요청이 1 을 넘길 수 있는 구조**.
  2. 대화 전환/로그아웃 시 `stopProgressPolling()` 이 `clearInterval` 만 호출하고 이미 발행된 fetch 를 취소하지 않아, 서버 측에는 **스텁 요청이 뒤늦게 계속 도착**.
  3. `/api/progress` 핸들러는 `_load_steps_for_run(conn, cid, run_id)` 로 **해당 run 의 전체 step 을 매번 파이썬 메모리로 로드**하고 `[s for s in all_steps if step_index > after_step]` 로 필터링했다. 서버 `AgentMemorySteps` 가 쌓이는 장기 대화일수록 폴링 비용이 O(N) 으로 증가.
  4. 서버는 `after_step` 만 받고 `client_run_id` 는 없어서, **클라이언트가 들고 있는 run_id 가 서버 최신 run_id 와 달라도** 서버가 그것을 감지할 수 없었다. 결과: 새 run 이 시작됐는데 클라이언트는 과거 run 의 `after_step` 을 계속 들고 와 **신규 step 0..K 를 놓침**.
  5. `document.hidden` 상태(탭 전환) 에서도 1500ms 주기가 그대로 유지 — 탭이 백그라운드여도 매초 한 번 네트워크/CPU 를 쓴다.
- 설계 (TASK-0036 시점에 실제 적용된 구조, 본 TASK-0037 은 이를 검토·문서화):
  1. **클라이언트 상태 모델 확장** — `state` 에 `progressPollInFlight:boolean`, `progressPollSeq:number`, `progressAbortController:AbortController`, `progressErrorCount:number` 추가. 기존 `progressPoller`(timer handle), `progressSteps`(누적 step 캐시), `progressRunId`(현재 추적 중인 run), `progressAfterStep`(다음 폴링의 after_step 값) 와 결합해 **폴링 생명주기** 를 정확히 모델링.
  2. **`setInterval` → 순번 기반 `setTimeout` 체인** — `scheduleProgressPolling(delayMs, seq)` 는 `clearProgressPollTimer()` 후 `setTimeout(() => pollProgress(seq).catch(()=>{}), nextDelay)` 단 하나만 예약. `pollProgress(seq)` 는 실행 시작 때 `seq !== state.progressPollSeq || progressPollInFlight` 이면 즉시 return, 끝날 때 다시 `scheduleProgressPolling(nextDelay, seq)` 로 다음 한 번을 예약한다. 즉 타임라인 상 항상 `[fetch] → [응답] → [다음 fetch 예약]` 순차 체인 구조가 보장되어 **in-flight 요청 수 ≤ 1** 가 코드로 강제됨.
  3. **AbortController 기반 취소 경로** — 매 poll 마다 `new AbortController()` 를 `state.progressAbortController` 에 저장하고 fetch 에 signal 로 전달. `stopProgressPolling({abort:true})` 는 이를 `.abort()` 호출해 in-flight fetch 를 즉시 끊는다. 추가로 `setTimeout(() => controller.abort(), PROGRESS_FETCH_TIMEOUT_MS=4000)` 로 서버 응답 지연 상한도 보장.
  4. **적응형 폴링 주기** — `PROGRESS_POLL_ACTIVE_MS=1200ms`(신규 step 스트리밍 중), `PROGRESS_POLL_IDLE_MS=3000ms`(기본), `PROGRESS_POLL_HIDDEN_MS=10000ms`(탭 배경화), `PROGRESS_POLL_ERROR_MS=8000ms`(에러 후). `scheduleProgressPolling(delayMs)` 진입부에서 `document.hidden` 이면 `Math.max(delayMs, PROGRESS_POLL_HIDDEN_MS)` 로 하한을 올려, 어떤 경로로 빠른 delay 가 들어와도 탭이 숨겨져 있으면 자동 감속.
  5. **에러 백오프 + 포기 조건** — `progressErrorCount` 를 각 예외 경로(fetch 에러/timeout) 마다 증가시키고, 3회 미만이면 `PROGRESS_POLL_ERROR_MS=8000` 으로 재시도하되 3회 이상이면 아예 재스케줄링하지 않는다(`shouldSchedule = errorCount < 3`).
  6. **서버 `/api/progress` 최적화** — `_load_progress_status(conn, cid)` 로 `(status, status_at, run_id)` 를 단일 커서에서 반환. `_load_steps_for_run(..., after_step=0)` 은 `after_step > 0` 이면 SQL `WHERE step_index > %s` 조건을 직접 걸어 **DB 에서 바로 필터링** (python 측 list comprehension 제거). 핸들러는 async → sync 로 바뀌고(블로킹 mysql 호출과 단순 수식 뿐이라 이벤트 루프 점유 이득 없음), `client_run_id` 가 없거나 서버 최신 run_id 와 다르면 `next_after_step = 0` 으로 리셋해 응답에 해당 run 의 모든 step 을 담아 되돌려준다 — 클라이언트가 `applyProgressPayload` 에서 `runId !== state.progressRunId` 를 감지해 캐시를 새 run 으로 교체.
  7. **라이프사이클 API 일관화** — `startProgressPolling({reset=false, runId=""})` 은 이전 체인을 `stopProgressPolling({reset:false, abort:true})` 로 끊고 `progressPollSeq` 를 한 칸 올린 뒤 `scheduleProgressPolling(0, seq)` 로 즉시 첫 poll 을 예약한다. `stopProgressPolling({reset, abort})` 은 `reset=true` 일 때 `resetProgressTracking()` 을 호출해 캐시/run_id/after_step 을 0으로 복원 — 대화 전환/로그아웃/새 대화 생성 등 "새로 시작해야 하는" 경로에서 명시적으로 reset 을 지정.
- 검증 (코드 리뷰 + 정적 확인 — 이미 커밋된 변경이므로 신규 runtime 배포 불필요):
  1. `grep -c "setInterval" src/static/app.js` = 0. 기존 고정 주기 루프가 폴링 경로에 남아있지 않음.
  2. `grep -nE "PROGRESS_POLL_(ACTIVE|IDLE|HIDDEN|ERROR)_MS|PROGRESS_FETCH_TIMEOUT_MS" src/static/app.js` 로 5 개 상수(lines 67-71) 모두 선언 확인, `scheduleProgressPolling`/`pollProgress` 본문에서 실제 참조.
  3. `progressPollSeq` 증가 지점(3곳): `stopProgressPolling()`, `startProgressPolling()`, `applyProgressPayload()` 계열 콜러에서 새 run 감지 시. 각 poll 은 `seq !== state.progressPollSeq` 로 자신이 구버전인지 체크.
  4. `AbortController` 배치: `pollProgress` 는 `controller = new AbortController()`, `timeoutId = setTimeout(controller.abort, 4000)`, `fetch(url, {signal: controller.signal})`, `finally` 에서 `clearTimeout(timeoutId)` + `state.progressAbortController = null if matches controller`.
  5. 서버 측 `/api/progress` (app.py:4381~4426) 가 `client_run_id` 파라미터를 선언하고 `if not run_id or str(client_run_id or "").strip() != run_id: next_after_step = 0` 조건을 가진다 (line 4405-4406).
  6. 사용자 수신 상태 플로우: `status != 'processing'` 이면 `stopProgressPolling({abort:false})` + `refreshWorkspace(cid)` 호출 — 즉 서버가 done/failed 를 돌려주는 순간 클라이언트 폴링이 종료되고 workspace 가 최종 상태로 refresh 된다.
- 영향/후속:
  1. TASK-0034 같이 턴당 수분 걸리는 워크로드에서도 브라우저에서 `/api/progress` 요청이 쌓이지 않는다. 서버 측 로그/DB/네트워크 부하가 선형에서 상수 시간대로 감소.
  2. 현재는 LEARNINGS.md 에 폴링 패턴 학습 기록이 없다. 본 TASK 로 `LRN-20260422-0011 장시간 작업 폴링은 setInterval 이 아니라 순번 기반 setTimeout 체인 + AbortController + document.hidden 감지가 기본` 을 추가.
  3. TASK-0036 MODIFY 항목(CHG-20260421-0009) 에는 폴링 리팩터가 언급되지 않았다. 본 TASK 에서 별도 CHG 로 분리하지 않고 CHG-20260421-0009 Notes 에 한 줄을 보강하는 대신, 문서화 목적이므로 `CHG-20260422-0010` 으로 따로 기록하는 것이 다른 feature/에이전트 가 "폴링 개선" 키워드로 검색할 때 발견 가능성이 높다 — 따라서 별도 CHG 로 분리.
- 범위 제한:
  - 신규 코드 변경 없음(이미 27127b9 에 반영됨).
  - 문서 갱신만 수행: `docs/TASK.md`(본 항목 + 체크리스트), `docs/MODIFY.md`(CHG-20260422-0010), `docs/LEARNINGS.md`(LRN 추가), `docs/REPORT.md`(검증 결과 한 줄).
- 완료 조건:
  - TASK.md §2 Task Queue 에 TASK-0037 `[x]` 가 올라가고 §3.1 Recently Done 에 본 요약이 들어간다.
  - LEARNINGS.md 에 폴링 패턴 LRN 항목이 추가된다.
  - MODIFY.md 에 CHG-20260422-0010 문서화 전용 엔트리가 append 된다.
  - git commit + push 가 완료된다.

### TASK-0036 상세 설계 (2026-04-21)
- 문제/목적 (사용자 요청 2026-04-21):
  1. 현재 `SYSTEM_PROMPT` 는 `agent_core.py:70` 에 하드코딩되어 있고, 조직/도메인/사용자별 맞춤 지침을 주입할 방법이 없다. 운영 중 "이 Role 은 이렇게 답하게 해달라", "특정 계정은 본인 전용 스타일 지침을 추가하고 싶다" 같은 요구가 반복된다.
  2. 현재 agent 는 `DB_CONNECT_DB` 로 default schema 만 고정되어 있고 `_SYSTEM_SCHEMAS` 외의 모든 user schema 에 무차별로 접근한다. 실제로는 서비스 경계(국가/팀/도메인) 단위로 "이 Product 는 이 DB 세트만 본다" 로 묶어야 한다.
  3. 현재는 Product 가 하나지만(초기 값으로 `KR` 부여, 접근 DB: `dbgame`/`dblog`/`dbauth`), 이후 다른 Product 가 추가될 것이므로 **Role/Account 와 대등한 위상의 정본 테이블** 로 관리해야 한다.
- 현황/환경 분석 (출발점 근거):
  1. `SYSTEM_PROMPT` ([agent_core.py:70](../../feature-0002-agent-core/src/agent_core.py#L70)) 는 `run_agent` ([agent_core.py:935](../../feature-0002-agent-core/src/agent_core.py#L935)) 안 `system_content = SYSTEM_PROMPT` ([L1090](../../feature-0002-agent-core/src/agent_core.py#L1090)) 에서 origin_request/thread_goal/knowledge_ctx 와 합쳐진다. `run_agent` 호출은 web 측 `app.py` 가 in-process 로 수행 ([app.py:3260](../src/app.py#L3260)) 하므로 kwarg 추가가 쉽다.
  2. RBAC 정본은 `WebPermissions` / `WebRoles` / `WebRolePermissions` / `WebAccountPermissionOverrides` 이고 account ↔ role 은 `WebAccounts.RoleId` 이다 ([app.py:1477~1570](../src/app.py#L1477)). Product 는 이 구조와 대등하게 `WebProducts` / `WebProductDatabases` (+ 계정/대화별 Product 참조) 를 추가하면 자연스럽다.
  3. 도구 구현 `tools.py` ([feature-0002-agent-core/src/modules/tools.py:23](../../feature-0002-agent-core/src/modules/tools.py#L23)) 의 `_SYSTEM_SCHEMAS` + `_is_user_schema` 만으로 스키마 필터가 결정된다. 여기에 **실행 시점 whitelist** 를 추가하고 execute_sql 에서 `schema`.`table` 참조를 검사하면 접근 제한이 가능하다.
  4. admin console 은 "대시보드/계정/역할" 3 탭 ([admin.html:24~36](../src/static/admin.html#L24)) 이고, 4 번째 탭 "상품" 추가가 자연스럽다. 프로필 드로우는 "계정/보안/API Vault" 3 탭 ([index.html:187~189](../src/static/index.html#L187)) 이고 여기에 "프롬프트" 탭 추가.
  5. 대화의 Product 결정: `AgentCoreConversations` 에 `product_id` 컬럼 추가. 새 대화는 계정의 default product (추후 account-level 선택 가능) 로 고정. fork 시 원본 product_id 를 그대로 상속.

- 설계 (Plan-Review-Execute, 위험도: Moderate — 신규 테이블 3개 + permission 2개 + admin/prompt API + UI 2곳 + agent_core signature 확장):

  A. DB 스키마 (`_ensure_web_tables` 확장)
     ```
     WebProducts (
       Id BIGINT AUTO_INCREMENT PK,
       ProductKey VARCHAR(32) UNIQUE NOT NULL,   -- 'KR', 'JP', ...
       Name VARCHAR(128) NOT NULL,
       Description VARCHAR(255) DEFAULT '',
       IsActive TINYINT(1) DEFAULT 1,
       IsDefault TINYINT(1) DEFAULT 0,           -- 대화 생성 시 기본 product
       SortOrder INT DEFAULT 100,
       CreatedAt/UpdatedAt
     )
     WebProductDatabases (
       ProductId BIGINT NOT NULL,
       SchemaName VARCHAR(64) NOT NULL,
       Description VARCHAR(255) DEFAULT '',
       SortOrder INT DEFAULT 100,
       CreatedAt,
       PRIMARY KEY (ProductId, SchemaName)
     )
     WebSystemPrompts (
       Id BIGINT AUTO_INCREMENT PK,
       Scope ENUM('product','role','account') NOT NULL,
       ProductId BIGINT NULL,                    -- scope=product: 필수, role/account: nullable(=범용)
       RoleId BIGINT NULL,                       -- scope=role 만 사용
       AccountId BIGINT NULL,                    -- scope=account 만 사용
       Content MEDIUMTEXT NOT NULL,
       UpdatedAt, UpdatedByAccountId,
       UNIQUE KEY UX_Scope (Scope, ProductId, RoleId, AccountId)
     )
     AgentCoreConversations.product_id BIGINT NULL   -- 대화가 속한 Product
     ```
     - seed (`_ensure_seed_products`): ProductKey=`KR`, Name=`Korea`, IsDefault=1, IsActive=1. 연결 DB: `dbgame`, `dblog`, `dbauth`.

  B. Permission 추가 (PERMISSION_DEFINITIONS)
     - `product.manage` (그룹: `관리`) — Product/ProductDatabases CRUD + Product scope prompt 쓰기. 기본으로 admin role 에 부여.
     - `system_prompt.manage.role.any` (그룹: `관리`) — Role scope prompt 쓰기. admin role 에 부여.
     - Account scope prompt 는 본인 자신은 언제나 읽기/쓰기 가능 (별도 permission 불요). 다른 계정의 account scope prompt 는 `system_prompt.manage.role.any` 가 있어야 관리 가능 (감사성 측면).
     - Product 자체 조회(`products.read`)는 "로그인한 모든 계정"에 기본 허용 — 대화 생성 시 product 선택/표시를 위해 필요. 따라서 세션 payload 에 products 목록만 내려주고 별도 permission 체크는 생략한다. CUD 는 `product.manage` 로만 가드.

  C. 시스템 프롬프트 조립 함수 (`agent_core.py`)
     - 신규 함수 `compose_system_prompt(mem_conn, *, product_id, role_id, account_id) -> str`:
       ```
       [BASE SYSTEM_PROMPT]
       (product prompt 있으면) "\n\n## PRODUCT CONTEXT ({product_key})\n{content}"
       (role prompt 있으면)    "\n\n## ROLE GUIDANCE ({role_key})\n{content}"
       (account prompt 있으면) "\n\n## ACCOUNT PREFERENCES\n{content}"
       ```
     - role/account scope prompt 는 `ProductId=NULL`(전 Product 공통) 과 `ProductId=X`(해당 product 전용) 둘 다 가능. product-specific 이 있으면 그걸 쓰고 없으면 generic fallback.
     - Product 가 없거나 prompt 가 비어 있으면 기존 동작(base prompt 만) 과 동일.
     - `run_agent` 는 신규 kwargs `product_id: int | None = None`, `role_id: int | None = None`, `account_id: int | None = None` 을 받아 `system_content = compose_system_prompt(...)` 을 사용. 이어서 기존 `CONVERSATION CONTEXT` + `knowledge_ctx` 를 현재 순서 그대로 뒤에 붙인다.

  D. DB 접근 whitelist (tools.py)
     - 모듈 전역 `_ACTIVE_SCHEMA_ALLOWLIST: set[str] | None = None` 추가. `None` 이면 기존 동작(모든 user schema), set 이면 whitelist 필터 적용.
     - `_is_user_schema` 는 유지하고, whitelist 가 set 이면 그 추가 조건으로 AND 필터. `_tool_list_schemas` / `_tool_describe_schema` / `_tool_describe_table` / `_tool_search_tables` / `_tool_execute_sql` 모두 반영.
     - execute_sql 은 SQL 에서 ``\`schema\`.\`table\``` 또는 `schema.table` 패턴을 정규식으로 추출해 whitelist 밖 스키마가 있으면 즉시 에러(`"접근이 허용되지 않은 스키마: X"`).
     - `run_agent` 는 `allowed_schemas: list[str] | None` kwarg 를 추가로 받아, 실행 시작 시 `tools.set_active_schema_allowlist(...)` 로 세팅하고 종료 시 `None` 으로 복원(try/finally).

  E. app.py 계약
     - 신규 헬퍼: `_get_product_for_conversation(conn, conversation_id)` — `AgentCoreConversations.product_id` 를 읽어 없으면 default product 로 fallback.
     - 새 대화 생성 (`/api/new_conversation`, `/api/fork_conversation`, 자동 생성): `product_id` = request body 의 `product_id` (optional) → fallback 으로 `account` 의 해당 Product (향후) → fallback 으로 default product.
     - `/api/ask` 는 대화의 product_id 를 조회 → 해당 product 의 DB schema 리스트 조회 → `run_agent(..., product_id=pid, role_id=rid, account_id=aid, allowed_schemas=schemas)` 로 전달.
     - 신규 admin API:
       - `GET /api/admin/products` — 목록 (`product.manage` 없이도 읽기 허용 = 공용 카탈로그)
       - `POST /api/admin/products` body: `{product_key, name, description?, is_active?, is_default?, sort_order?}` (`product.manage`)
       - `PATCH /api/admin/products/{id}` — 같은 필드 (`product.manage`)
       - `DELETE /api/admin/products/{id}` — 해당 product 를 쓰는 대화가 있으면 거부 (`product.manage`)
       - `GET /api/admin/products/{id}/databases` — 스키마 목록
       - `PUT /api/admin/products/{id}/databases` body: `{databases: [{schema_name, description?, sort_order?}, ...]}` — 전체 교체 (`product.manage`)
       - `GET /api/admin/system-prompts?scope=product|role|account&product_id=&role_id=&account_id=` — 해당 스코프 리스트
       - `PUT /api/admin/system-prompts` body: `{scope, product_id?, role_id?, account_id?, content}` — upsert. scope=role 은 `system_prompt.manage.role.any`, scope=account 는 본인이 아니면 `system_prompt.manage.role.any` 필요.
       - `DELETE /api/admin/system-prompts/{id}` — 같은 권한 규칙.
     - 신규 self API:
       - `GET /api/auth/me/system-prompts` — 본인의 account scope prompt 목록 (product_id 별)
       - `PUT /api/auth/me/system-prompt` body: `{product_id?, content}` — 본인 upsert (본인 계정 대상은 권한 불요).
     - 세션 응답 (`/api/auth/me`) 에 `products: [{id, product_key, name, is_default}]` 를 추가해 프론트가 드롭다운/라벨에 사용.

  F. UI — admin console
     - 탭 추가 `상품` (admin.html): 대시보드/계정/역할 다음에 배치. 좌측 list + 우측 detail 패턴으로 구성 (기존 Role 관리와 같은 layout 재사용).
     - Detail 구성:
       1. 기본 정보 섹션 (ProductKey/Name/Description/IsActive/IsDefault/SortOrder)
       2. **접근 DB** 섹션 — "계정 카테고리와 별개" 라는 사용자 요구에 따라 구분선 + 명시적 헤더 (`접근 가능 DB 스키마`) 로 그룹화. 해당 product 에 등록된 schema 를 chip 으로 보여주고, 텍스트 입력 + `추가` 버튼 + 각 chip 옆 `×` 삭제.
       3. **시스템 프롬프트** 섹션 (Product scope) — textarea + 저장. scope=product, ProductId=현재 product 로 upsert.
     - Role detail 에도 **시스템 프롬프트** 섹션 추가:
       - Product 드롭다운 (첫 항목 `(전 Product 공통)`, 그 아래 구분선 후 Product 목록) + textarea + 저장. 저장 시 scope=role, RoleId=현재 role, ProductId=(선택값 or NULL).
     - Products 탭은 `product.manage` 가 없으면 read-only 상태(수정/삭제 버튼 disable + 저장시 에러 토스트)로 보인다. 어떤 계정도 product 목록 자체는 볼 수 있어야 profile 화면에서 product 별 prompt 를 지정할 수 있다.

  G. UI — 프로필 드로우
     - 드로우 탭에 `프롬프트` 추가 (계정/보안/API Vault/프롬프트).
     - 내부: Product 드롭다운 (`(전 Product 공통)` 기본값 + 각 Product) + textarea + 저장 + 초기화. 저장 시 `PUT /api/auth/me/system-prompt`.
     - 프로필 탭에서 product 선택을 바꾸면 해당 product scope 의 현재 prompt 를 다시 불러온다.

  H. 대화/Agent 연결
     - `/api/new_conversation` 과 `/api/fork_conversation` 은 생성/복제 시 `AgentCoreConversations.product_id` 에 값을 기록. 기본값은 (body.product_id || account.default_product_id || global default product).
     - `/api/ask` 는 conversation.product_id 를 조회해 `product_id` + `allowed_schemas` + `role_id` + `account_id` 를 `run_agent` 에 넘긴다.
     - `run_agent` 는 `allowed_schemas` 를 tools 전역에 set/clear 하고, `compose_system_prompt` 결과로 system message 를 만든 뒤 기존 흐름대로 진행.

- 검증 계획:
  1. `python3 -m py_compile` 로 agent_core.py / app.py / tools.py 문법 확인.
  2. 컨테이너 재빌드 (`make web`, `make agent`) 후 bootstrap_admin 로그인 → `/api/admin/products` GET → KR seed 확인 → `/api/admin/products/{kr_id}/databases` GET → `dbgame,dblog,dbauth` 3건 확인.
  3. `PUT /api/admin/system-prompts` 로 Product scope prompt 생성 → Role scope prompt 생성 → 본인 account scope prompt 생성.
  4. `/api/ask` 로 질의 → agent 가 받은 system message 에 `## PRODUCT CONTEXT (KR)` / `## ROLE GUIDANCE (admin)` / `## ACCOUNT PREFERENCES` 가 순서대로 주입되었는지 agent 응답의 steps 로그에서 확인.
  5. whitelist 밖 schema (e.g. `mysql.user`) 를 execute_sql 로 호출했을 때 거부되는지 확인.
  6. 브라우저 수동: admin 의 Products 탭 + Roles detail 의 prompt 영역 + 프로필의 프롬프트 탭이 모두 렌더되는지 확인.

- 비-목적 (Out of Scope):
  - Product 별 계정 멤버십 ACL (`WebAccountProducts`). 이번은 모든 계정이 모든 active product 접근 가능한 MVP.
  - Product 별 RBAC override 매트릭스. 현재 permission 체계는 RBAC 만 쓰고, "이 Role 이 이 Product 에서만 유효" 같은 scoping 은 별 과제로 둠.
  - `_tool_execute_sql` SQL parsing 정확도: quoted identifier 가 아닌 서브쿼리 내부 복잡 참조는 표면적 regex 로만 검사. full sqlparse 도입은 후속 과제.

- TASK-0035 (2026-04-21 마감): 사이드바가 `내 대화` / `타 계정 대화 (N)` 섹션으로 분할 노출되고 내 대화는 좌측 primary 컬러 바 + 틴트, 타 계정 대화는 owner 뱃지 강조로 구분된다. 말풍선의 user 메시지도 `is-own-message` / `is-other-message` 로 톤이 분리되며, meta 라벨은 `나 (<username>)` 또는 `<owner_username>` 을 표시한다. `POST /api/fork_conversation` 이 `conversation.create` + `read.own/any` 권한에 맞춰 원본 topic 과 메시지(internal 제외)를 새 대화로 복제하며, 복제본 topic 에는 `[Fork]` 접두사를 붙인다. 헤더 `대화 복사` 버튼은 전체 복제, 말풍선 hover 액션 `여기서 분기` 는 부분 복제(`from_message_id` 지정) 를 수행한다. 검증: `docker compose run --rm -T web python -m py_compile src/app.py` OK, 브라우저 스크립트 `curl -sk ... /api/fork_conversation` 로 전체 복제 6건/부분 복제 3건(source 20260421075518-571abdb6) 모두 HTTP 200 반환, 새 conversation_id 20260421082459-c039abbd / 20260421082523-d9fbb21b 에 topic `[Fork] ...` 접두어와 MetaJson 내 `forked_from_message_id` 저장 확인.

### TASK-0035 상세 설계 (2026-04-21)
- 문제/목적 (사용자 요청 2026-04-21):
  1. 사이드바 대화 목록에서 자신의 대화인지, 타 계정 대화인지 **한눈에 구분이 안 된다**. 현재는 `conv-item-meta` 마지막에 작은 회색 글자로 `owner_username` 만 표시되어, admin 으로 로그인해 전체 대화를 볼 때 본인 대화가 파묻힌다.
  2. 타 계정 대화는 조회만 가능하고 composer 가 잠겨 있어(`renderComposer` 의 `!isOwnConversation(...)` 분기), **타 계정 대화를 그대로 이어서 질의할 수 없다**. 따라서 "이 대화의 지금까지 맥락을 가져와서 내 대화로 이어서 질문" 하는 경로가 필요하다.
  3. 동일한 요구가 자기 대화 내에서도 발생 — 특정 중간 응답(가설/분기점)에서부터 다른 방향으로 실험해 보고 싶을 때 **현재 대화를 오염시키지 않고** 그 지점까지 복제한 새 대화가 있으면 안전하다.
- 현황/환경 분석 (출발점 근거):
  1. `_list_conversations` ([app.py:1629](../src/app.py#L1629)) 는 `owner_account_id`, `owner_username`, `last_activity_at` 을 모두 반환하지만, 프론트엔드 `renderConversationList` ([static/app.js:588](../src/static/app.js#L588)) 는 단일 리스트로 `owner_username` 만 소극적으로 덧붙인다.
  2. `isOwnConversation` ([static/app.js:319](../src/static/app.js#L319)) 이 `Number(conversation.owner_account_id) === Number(state.user.id)` 기준으로 소유 판정 로직을 이미 갖고 있어, 하이라이트/정렬 로직에서 재사용 가능하다.
  3. `renderMessages` ([static/app.js:1153](../src/static/app.js#L1153)) 는 role 만으로 "사용자 / Assistant" 를 표시한다. `user` 메시지는 현재 대화 소유자가 보낸 것이므로, 대화 소유자가 현재 계정이면 "나 (<username>)", 아니면 `owner_username` 으로 라벨링하면 정보량이 크게 올라간다.
  4. `/api/new_conversation` ([app.py:3171](../src/app.py#L3171)) 는 빈 대화만 만든다. 메시지 복사는 별도 API 가 필요하다.
  5. `AgentMemoryMessages` 는 `(ConversationId, Role, Content, CreatedAt, MetaJson)` 스키마이고, `memory.py` 의 insert 문 ([memory.py:867](../../feature-0002-agent-core/src/modules/memory.py#L867)) 은 CreatedAt 을 DEFAULT CURRENT_TIMESTAMP 에 의존한다. fork 시에는 **원본 CreatedAt 을 보존** 해야 원본과 동일한 시계열로 재생된다 → 별도 insert 쿼리(CreatedAt 포함) 를 API 레벨에서 직접 발행.
  6. `_get_history` ([app.py:2343](../src/app.py#L2343)) 와 `_is_internal_message` 는 internal 플래그가 붙은 시스템 메시지를 표시에서 제거한다. fork 에서는 **표시되는 메시지만** 복사해 새 대화를 "깨끗하게" 시작할 수 있도록 한다.
- 설계 (Plan-Review-Execute, 위험도: Minor — UI 레이어 추가 + 신규 API 1개, 기존 스키마/권한 체계 변경 없음):
  A. 사이드바 구분/정렬 (프론트엔드)
     - `renderConversationList` 를 **own-first 그룹핑** 으로 재구성: `state.conversations` 을 `isOwnConversation(item)` 으로 파티션 → `own` 블록 + `others` 블록. 각 블록은 기존 ORDER(`updated_at DESC`) 를 그대로 따른다.
     - 각 블록 앞에 `.conv-group-title` (섹션 헤더) 을 삽입: "내 대화" / "타 계정 대화 (<count>)". 타 계정 블록은 item 이 1건 이상일 때만 노출.
     - `conv-item` 에 `is-own` / `is-other` 클래스 추가. 활성 하이라이트(`is-active`) 와 독립적.
     - CSS (`styles.css`):
       * `.conv-item.is-own` → `border-left: 3px solid var(--primary)`(내 대화 좌측 컬러 바) + 약한 `background` 틴트.
       * `.conv-item.is-other` → `border-left: 3px solid transparent` + `.conv-item-meta` 의 owner_username 을 bold/색 강조(`var(--text-2)`) 처리.
       * `.conv-item.is-own .conv-owner` 는 "나" 로 라벨, `.conv-item.is-other .conv-owner` 는 `owner_username` 을 그대로 노출.
       * `.conv-group-title` → 11px, uppercase, letter-spacing 0.06em, muted 톤.
  B. 말풍선 소유자 라벨/하이라이트 (프론트엔드)
     - `renderMessages` 에서 현재 대화를 `currentConversation()` 로 잡아 `isOwn = isOwnConversation(conversation)`, `ownerLabel = conversation.owner_username || "사용자"` 를 계산.
     - user 메시지 meta 라인: `isOwn ? "나 (" + state.user.username + ")" : ownerLabel` → 기존 "사용자" 라벨 교체.
     - user 메시지 row 에 `is-own-message` 또는 `is-other-message` 클래스 부여.
     - CSS: `is-own-message .message-bubble` → 기존 primary 톤 유지(현 상태), `is-other-message .message-bubble` → 중성 grey 톤(`--bg`, border `var(--border)`) 으로 색상 분리해 "내가 보낸 글" 과 혼동 방지. assistant 말풍선은 계정과 무관하므로 변경 없음.
  C. 대화 fork API (백엔드)
     - 신규 엔드포인트 `POST /api/fork_conversation` ([app.py:3171](../src/app.py#L3171) 근처, `new_conversation` 바로 아래 배치):
       ```
       request body: {
         source_conversation_id: str (required),
         from_message_id: int | null   // 이 ID 까지(포함) 복사. null/누락 시 전체 복사.
       }
       response: { conversation_id: str, copied: int, source: str }
       ```
     - 권한:
       * 현재 계정이 `conversation.create` 를 가져야 한다 (not owned).
       * 원본 대화에 대해 `_account_can_access_conversation(conn, account, source, "conversation.read.own", "conversation.read.any")` 가 True 이어야 한다.
     - 절차:
       1. 원본 존재/권한 검증. 실패 시 404/403.
       2. `agent_core.create_new_conversation(conv_file=_account_conv_file(id))` 로 새 cid 발급 + `_assign_conversation_owner(conn, cid, account_id, force=True)`.
       3. topic 복사: 원본 topic 조회 후 `_set_conversation_topic(conn, cid, "[Fork] " + original_topic)`. (기존 `rename_conversation_title` 의 topic 쓰기 경로를 재사용한다.)
       4. `AgentMemoryMessages` 에서 `ConversationId = source` AND (`from_message_id` 있으면 `Id <= from_message_id`) 조건으로 Role/Content/CreatedAt/MetaJson 을 ORDER BY Id ASC 로 가져와, 새 cid 로 **원본 CreatedAt 을 그대로 유지한 채** 재삽입. `_is_internal_message` 가 True 인 row 는 skip (internal=True 인 시스템 메모는 fork 대상 아님).
       5. MetaJson 에 `forked_from_conversation_id`, `forked_from_message_id`(또는 null) 를 추가해 추적성 보존.
       6. `_set_account_current_conversation(conn, account_id, cid)` 로 새 대화를 활성화 후 JSON 응답.
     - 실패/롤백: 중간 예외 시 이미 생성된 새 대화는 `delete_conversation_records(conn, cid)` 로 정리 후 500.
  D. 대화 fork UI (프론트엔드)
     - 헤더 버튼: `index.html` `chat-header-tools` 에 `<button id="forkConversationBtn">대화 복사</button>` 추가. 활성 대화가 있고 `conversation.create` 권한이 있으면 visible, 없으면 `is-access-blocked`.
     - 말풍선 단위 fork: `renderMessages` 에서 각 message row 에 `message-actions` 액션 바를 생성하고 `여기서 새 대화로 분기` 버튼을 둔다. 호버 시 opacity 가 올라오는 pattern (기존 hover 스타일 참고). click → `forkConversation(from_message_id=message.id)`.
     - 공통 함수:
       ```js
       async function forkConversation({ fromMessageId = null } = {}) {
         const src = state.activeConversationId;
         if (!src) return;
         if (!can("conversation.create")) { showPermissionDeniedToast("conversation.create"); return; }
         const payload = await apiFetch("/api/fork_conversation", {
           method: "POST",
           body: JSON.stringify({ source_conversation_id: src, from_message_id: fromMessageId }),
         });
         showToast(fromMessageId ? "선택한 지점까지 새 대화로 복제했습니다." : "대화를 새 대화로 복제했습니다.");
         await refreshWorkspace(payload.conversation_id || "");
       }
       ```
     - 비-own 대화에서도 `conversation.create` 만 있으면 fork 가 허용되므로, 기존 "읽기 전용 대화" 문구 아래에 "대화 복사" 버튼을 강조 노출한다 (read-only UX 의 탈출구 제공).
- 테스트/검증:
  1. `python3 -m py_compile repo/unit/feature-0003-agent-web-ui/src/app.py` 로 문법/import 점검.
  2. 브라우저 수동 검증: 로그인 → 내 대화/타 계정 대화가 섹션 분리 + 하이라이트로 구분되는지 확인. admin 계정에서 본인 대화가 상단으로 정렬되는지 확인.
  3. fork 수동 검증:
     - 자기 대화에서 "대화 복사" → 새 대화 cid 반환 + 사이드바 "내 대화" 블록에 추가됨.
     - 타 계정 대화에서 특정 assistant 말풍선의 "여기서 분기" → 해당 말풍선 id 까지 복사된 새 대화가 나에게 생성됨.
     - 새 대화의 topic 이 `[Fork] ...` 로 표시되는지 확인.
     - 새 대화에서 composer 가 열려 추가 ask 가 가능한지 확인.
  4. 권한 분기 검증: `conversation.create` 가 없는 viewer 계정에서 fork 버튼이 `is-access-blocked` 로 표시되고 클릭 시 토스트만 뜨는지.
- 비-목적(Out of Scope):
  - 메시지 meta 의 steps/csv/sql 아티팩트 복제. (MetaJson 은 그대로 복제되지만, `/shared/...` 에 있는 CSV 파일은 그대로 원본 경로를 참조한다. 파일 접근은 `conversation.file.read.*` 권한과 `_account_can_access_conversation` 으로 여전히 통제되므로 fork 소유자가 원본 파일에 대한 접근 권한을 갖고 있지 않으면 링크 클릭 시 403 을 받는다. 이 범위는 현 작업에서 변경하지 않는다.)
  - 실시간 동기화(원본 대화가 뒤에 더 쌓여도 fork 된 대화에는 반영되지 않음 — snapshot 시맨틱 유지).
  - agent-core 내부 `ConversationState` 마이그레이션(대화별 run state 는 새 대화에서 깨끗하게 시작).

### TASK-0034 상세 설계
- 문제/목적 (사용자 요청 2026-04-21):
  - 현재 구성된 assistant (RBAC/SQL agent/Insight/Local+API LLM) 가 실제로 **복잡한 도메인 질의** 에서 얼마나 정확한 답을 내놓는지 체계적으로 확인하고, 이후 개선 이슈의 근거로 쓰고자 함.
  - 정확한 답변을 위해 **한 대화 안에서 최대 20회 까지 질의를 이어간다** (= 사용자 역할을 하는 테스트 러너가 추가 질문/구체화 요청으로 agent 를 보조) 는 가정으로 진행.
  - 구성: **local LLM 5 대화 (성능 한계 → 직렬)** + **상용 API 5 대화 (모델 = gpt-5 mini → 이 저장소의 `gpt-5.4-mini`, 병렬 가능)**.
  - API 키는 `.env` 의 `OPENAI_API_KEY` 재사용 승인됨.
  - **실제 DB 데이터와 정확히 일치하는지 별도 검증**: 같은 질문을 사람이 직접 MySQL 쿼리로 풀어서 그 결과를 assistant 의 최종 답변과 1:1 대조한다.
  - 기본 예시 3 개는 주어졌고, 더 복잡한 변주도 가능하면 포함한다.
- 기준 예시 질문 (사용자 제공):
  1. dblog 에서 **영웅스킬 업그레이드의 가장 대중적인 테크트리** 를 영웅별 및 테크트리별로 집계.
  2. dblog 에서 **전투시작 관련 테이블 통계** — 전투시작 구성 영웅 중 가장 많이 사용된 50종의 참여 횟수/채택률.
  3. 한정가챠 — **유저가 특정 상품일 때만 시도하고 나머지는 만료** 시키는 패턴을 근거로, "가치가 높은 상품" 이 무엇인지 집계 (이진 플래그 기반).
- 원인/환경 분석 (본 작업의 출발점):
  1. `/api/ask` 가 commercial 모델 사용 시 클라이언트 측에서 **PBKDF2-HMAC-SHA256(100000 iter, 32byte) + AES-GCM, `v1:<salt_b64>:<iv_b64>:<ct_b64>`** 포맷으로 암호화된 API key 를 요구 ([app.py:1003](../src/app.py#L1003) `_decrypt_api_key`). 즉 브라우저 없이 curl 로만 commercial 테스트를 하려면 동일 포맷의 암호 헬퍼가 별도로 필요하다.
  2. Local LLM 경로는 `model ∈ {"auto","edge","core","code"}` 이고 API key 를 요구하지 않는다 ([model_catalog.py](../../feature-0002-agent-core/src/modules/model_catalog.py)). Local LLM 은 `local-llm-gateway:8080/v1` 단일 프로세스라 병렬 대화가 큐 경합으로 느려지므로 **직렬** 지시가 적절하다.
  3. 기본 인증은 HttpOnly 세션 쿠키이므로 `/api/auth/login` → 쿠키 jar 저장 → `/api/ask` 재사용 흐름을 그대로 쓸 수 있다. `bootstrap_admin` 은 RoleId=3 (admin) 으로 `conversation.ask`/`conversation.create`/`conversation.read.any`/`conversation.file.read.any` 등 필요한 권한을 모두 보유(확인됨 `SELECT ... webrolepermissions WHERE RoleId=3 AND Code LIKE 'conversation%'`).
  4. DB 스키마 사전 조사:
     - `dblog.battlebegin` (533k rows). `MyHeroInfo` 컬럼이 JSON 배열 `[{Index, Level, Star, Skill:[5 levels], Equip..., Transcend...}, ...]` — **질문 1 (영웅스킬 테크트리) + 질문 2 (영웅 사용 빈도) 의 공통 자원**.
     - `dblog.battleend` (555k rows). `Win/Star/PlayTime` 포함 — BattleType 별 성과 지표 확장 가능.
     - `dblog.equipoptionupgrade` (8.7k rows). `OptionIndex, OptionStep` — "장비 옵션 업그레이드 테크트리" 로 해석할 여지 있으나 질문 1 의 본질은 MyHeroInfo.Skill[] 분포.
     - `dblog.equipgacharecord` (165 rows). `HighGachaCategory` 는 comma-separated 카테고리(`"25,71,13,2"`) 와 클래스명(`"NewHero"`, `"Wizard"` 등) 이 섞여 저장되어 있음. 행 수가 매우 적지만 질문 3 이 요구하는 "이진 플래그 기반 한정가챠 가치 판별" 의 뚜렷한 resource — assistant 의 희소 데이터 해석력 테스트에 오히려 적합.
     - 추가 대형 테이블: `dblog.currency` (2.84M), `dblog.equipget` (1.8M), `dblog.equipremove` (1.6M), `dblog.gold` (899k), `dblog.battlebeginaffixv2` (562k), `dblog.battleendaffixv2` (511k), `dblog.gemv2` (308k). 이들은 추가 복잡 질의(재화 유출입/장비 수명주기/전투 affix 영향) 에 쓸 수 있음.
- 5 개 복잡 질문 설계 (local LLM 5 대화 × 상용 API 5 대화 공통, 동일 질문 쌍으로 두 경로를 비교):
  1. **Q1 영웅스킬 업그레이드 테크트리 랭킹** — dblog 기준, 영웅(Index)별로 [Skill1, Skill2, Skill3, Skill4, Skill5] 레벨 조합(= "테크트리") 의 등장 빈도를 집계해 영웅별 상위 5 테크트리(+테크트리별 전체 상위 20) 를 리스트업. 데이터 소스: `battlebegin.MyHeroInfo` 배열을 JSON 풀어서 집계. (battlebegin 한 row 당 여러 hero 가 들어 있음에 주의 — assistant 가 스스로 풀어내는지 관찰 포인트.)
  2. **Q2 전투시작 영웅 사용 Top 50** — `battlebegin.MyHeroInfo` 를 펼쳐 hero Index 별 등장 수(= 참여 횟수) 와 채택률(= 등장 수 / 전체 battlebegin 행 수) 을 계산. 전체 영웅 종 수와 rank, 채택률 소수점 2자리 보고.
  3. **Q3 한정가챠 가치 품목 판별** — `equipgacharecord` 에서 (a) 유저가 실제로 **가챠를 진행한 행위** 와 (b) 만료/미진행 으로 보이는 **카테고리 노출 기록** 을 구분하고, 진행 행위가 많았던 카테고리(또는 코드) ↔ 일반 노출뿐이었던 카테고리 간 차이를 도출. 카테고리가 comma-separated 이므로 "이진 플래그" 해석을 assistant 가 잡아내는지가 관건.
  4. **Q4 BattleType 별 승률 × 평균 플레이타임** — `battlebegin` ↔ `battleend` 를 (AccountId, Time window) 로 매칭하여 BattleType 별 전투 수 / 승률 (`SUM(Win) / COUNT(*)`) / 평균 PlayTime / 평균 Star 를 도출, 상위 10 BattleType 랭킹. JOIN 정의가 애매하므로 assistant 의 스키마 탐색/LIMIT 프로빙 능력 관찰.
  5. **Q5 영웅 레벨/스타 분포로 본 "육성 된 메타 영웅" Top 20** — 각 영웅 Index 에 대해, 전투에 투입된 **최고 Level**, **평균 Level**, **Star ≥ 2 비율**, **총 등장 수** 를 계산해 "많이 나오면서 평균 레벨/스타도 높은" 영웅 Top 20. rank 산식은 assistant 가 합리적으로 제시하게 두고 검증 시 동일 산식을 사람 쿼리로 재현해 비교.
  - 모든 5 질문은 두 모델 경로에서 동일하게 사용 → 같은 질문에 대한 local vs API 응답 품질 비교 가능.
- 대화 프로토콜 (1 질문 → 1 "대화" 단위, 최대 20 turn):
  - **turn 1**: 주 질문을 그대로 던진다.
  - **turn 2~N**: assistant 가 부분 답/진행 중/스키마 탐색 중이면 러너가 보조 프롬프트 ("스키마를 먼저 확인해주세요", "JSON 안의 Skill 배열을 풀어서 집계해주세요", "가능하면 영웅별 Top 5 로 잘라주세요", "각 수치에 대해 어떤 쿼리를 썼는지 같이 보여주세요") 를 순차 제공.
  - 종료 조건 (다음 중 하나):
    a. assistant 가 명확한 최종 답 (표/CSV + 요약) 을 내고 러너가 "이제 충분합니다" 판단.
    b. 20 turn 도달.
    c. `/api/ask` 가 인증 만료/서버 500 반환 → turn 간격 유지를 위해 재로그인 1 회 시도 후 실패하면 종료.
  - 대화 1 건당 메타: `{model, conversation_id, turns: [{user, assistant_answer, sql_list, csv_preview, elapsed_s}], final_verdict}`.
- 테스트 하니스 설계:
  - 위치: `/root/download/docker/mysql_ai_delegated_dev/repo/unit/feature-0003-agent-web-ui/tests/task0034_runner.py` (신규, 테스트 전용). 실제 배포 코드가 아님.
  - 의존: `httpx`, `cryptography` (PBKDF2 + AESGCM). 두 라이브러리는 repo web 이미지에 이미 포함됨 — host 의 `python3 -m pip` 대신 `docker compose run --rm -T web python` 으로 실행해도 되고, host 에 이미 설치되어 있으면 host 에서 바로 실행 가능 (둘 다 시도 가능하도록 설계).
  - 주요 함수:
    ```python
    def encrypt_api_key(plain: str, passphrase: str) -> str:
        # salt(16B rand) + iv(12B rand) + PBKDF2HMAC-SHA256(iter=100_000, len=32)
        # → AESGCM encrypt → "v1:<b64 salt>:<b64 iv>:<b64 ct>"
    def login(client, username, password) -> None                 # POST /api/auth/login
    def new_conversation(client, model) -> dict                   # POST /api/new_conversation
    def ask(client, message, model, conversation_id,
            api_key_cipher=None, api_key_passphrase=None,
            timeout=600) -> dict                                   # POST /api/ask
    def run_conversation(question, model, api_key, max_turns=20) -> dict
    ```
  - 상용 API 경로: `ask()` 호출 시 매 턴마다 암호화된 cipher + 새 passphrase 같이 전송 (서버 측 복호화 → upstream OpenAI 호출).
  - Local LLM 경로: `api_key_cipher=None`, `model ∈ {"core","edge","auto"}`. 본 테스트는 `core` 고정 (agent 기본 권장).
  - 실행 전략:
    - 상용 5 대화: `asyncio.gather` 5 병렬 (`gpt-5.4-mini`).
    - Local 5 대화: `for` 루프 직렬 (`core`).
  - 결과 저장: `/root/download/docker/mysql_ai_delegated_dev/repo/unit/feature-0003-agent-web-ui/tests/task0034_runs/{local|api}-{qid}.json` — 각 대화의 전체 turn 로그 + 최종 답변 + 모든 SQL + CSV preview path 포함.
- DB 대조 검증 설계:
  - 질문별 **사람 정답 쿼리** 를 별도 파일 `tests/task0034_truth.sql` 에 기록 (Q1~Q5). 예:
    ```sql
    -- Q2 (참고): hero 사용 Top 50
    SELECT h.hero_index, COUNT(*) AS appearances,
           ROUND(COUNT(*) / (SELECT COUNT(*) FROM dblog.battlebegin WHERE MyHeroInfo IS NOT NULL) * 100, 2) AS adoption_pct
    FROM dblog.battlebegin b,
         JSON_TABLE(b.MyHeroInfo, '$[*]' COLUMNS (hero_index INT PATH '$.Index')) h
    WHERE b.MyHeroInfo IS NOT NULL AND b.MyHeroInfo <> ''
    GROUP BY h.hero_index
    ORDER BY appearances DESC
    LIMIT 50;
    ```
  - 검증 스크립트 `tests/task0034_verify.py`: assistant 가 낸 최종 Top-N 리스트 vs truth 쿼리 결과를 **(key, count) tuple set 비교 + rank 순서 비교** 로 확인. 일치율 % 와 불일치 항목 diff 출력.
  - 모호한 질문(Q3, Q5) 은 "논리적으로 맞는 범위" 를 기준으로 판정 기록 (완전 일치 가능 여부를 리포트에 명시).
- 결과 리포트:
  - `tests/TASK-0034-REPORT.md` — 질문별로 (a) assistant 최종 답변 요약, (b) 사람 truth 결과, (c) 일치/불일치, (d) 몇 턴 만에 수렴, (e) 관찰된 개선 포인트.
  - LEARNINGS 는 (**LRN-20260421-0010**) "복잡 QA 에서 agent 가 어디에서 막히거나 무한 재시도하는지, 어떤 휴리스틱을 추가하면 턴 수를 줄일 수 있는지" 한 줄 패턴으로 정리.
- 범위 제한:
  - 프로덕션 UI/백엔드 코드 변경 **금지**. 오직 테스트 하니스 신규 파일 추가 + 결과 문서만.
  - 결과 저장 CSV 원본 (agent 가 `/data/artifacts` 에 남기는 실제 파일) 은 repo 에 체크인하지 않음 — 로그 JSON 의 `preview` 10 행만 커밋.
  - `.env` 의 실제 API key 는 **절대 로그에 남기지 않는다**. 러너가 키를 메모리에 로드해서 암호화·전송 후 즉시 해제.
  - 본 테스트 실행 중 agent 가 만든 대화/메타데이터(webaccounts/conversations) 는 정리하지 않고 남겨 둠 — 사용자가 이후 UI 로 참고 가능.
- 검증 기준 (본 TASK 자체의 완료 조건):
  1. local 5 + API 5 총 10 대화가 실제로 실행되어 JSON 로그로 남았다.
  2. 각 대화의 turn 수 / 최종 답변 / SQL 목록 / 경과 시간이 로그에서 읽힌다.
  3. 5 질문 각각에 대해 DB truth 쿼리를 사람이 돌려본 결과와 assistant 답변을 비교한 diff 가 REPORT.md 에 기록되었다.
  4. LEARNINGS.md 에 이번 실험에서 발견된 구조적 개선점(LRN 항목 신규) 이 추가되었다.
  5. 커밋/푸시까지 완료.

### TASK-0033 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - 말풍선 안의 `실행 단계 및 쿼리 결과 보기` 를 펼치면 **바깥 채팅 로그(`.messages`) 스크롤 + 말풍선 상세 본문(`.message-details-body`) 스크롤** 두 개가 중첩되어, 사용자가 대화 전체를 마우스 휠로 훑을 때 경계에서 "턱턱" 끊기는 느낌이 난다.
  - 사용자 요청: **바깥 스크롤(= 말풍선 body cap)은 최대한 나타나지 않도록** 본문을 확장해달라.
  - 결과셋의 행/열이 많을 때 (특히 열이 10개 이상) 어느 행/열을 보고 있는지 **위치 파악이 어렵다**. 기본적으로 RowCount(행 번호) 컬럼이 있어야 하고, 1행(헤더)/1열(번호)은 스크롤해도 **틀 고정(freeze)** 되어야 한다.
- 원인:
  1. [styles.css:849-859](../src/static/styles.css#L849-L859) `.message-details-body { max-height: min(60vh, 520px); overflow: auto; overscroll-behavior: contain; padding-right: 4px; }` — TASK-0030 에서 말풍선 폭/스크롤 격리 목적으로 넣었지만, 내부의 `.sql-block`/`.result-table-wrap` 가 이미 각자 cap 을 가지므로 바깥 body cap 은 **중복 방어**. 중복된 cap 때문에 같은 콘텐츠에 대해 스크롤 컨테이너가 2개 생기고, 마우스 휠이 경계를 넘을 때마다 어느 컨테이너가 휠을 소비할지 바뀌어 "턱턱" 멈춤이 발생.
  2. [styles.css:913-920](../src/static/styles.css#L913-L920) `.result-table-wrap { ...; overscroll-behavior: contain; max-height: 320px; }` + [styles.css:907-909](../src/static/styles.css#L907-L909) `.sql-block { ...; overscroll-behavior: contain; max-height: 240px; }` — `overscroll-behavior: contain` 은 자식이 경계에 도달해도 휠을 부모로 **전파하지 않는다**. 그래서 테이블/SQL 내부 스크롤이 바닥/천장에 닿으면 `.messages` 로 올라가지 못하고 그대로 멈춤 — 이것도 "턱턱" 느낌의 큰 원인.
  3. [app.js:734-781](../src/static/app.js#L734-L781) `buildResultTable()` — 데이터 컬럼만 그대로 th/td 로 렌더. RowCount 컬럼 없음. thead th / 첫 컬럼 td 모두 `position: static` 이라 내부 스크롤 시 헤더/첫 열이 함께 밀려 보이지 않게 됨.
  4. [app.js:801-825](../src/static/app.js#L801-L825) `loadFullCsvIntoTable()` — 전체 데이터 로드 시에도 `header.forEach` / `body.forEach` 만 사용, RowCount 를 따로 추가하지 않음.
- 목표:
  1. 말풍선 상세 본문(`.message-details-body`) 의 수직 스크롤 컨테이너를 **제거** — 본문이 콘텐츠 높이만큼 자연스럽게 자라고, 전역 세로 스크롤은 채팅 로그(`.messages`) 하나로 통일. 같은 말풍선 안에 스크롤바 2개가 동시에 뜨는 상황을 근본 제거.
  2. 결과 테이블/SQL 블록은 여전히 **자체 내부 스크롤**을 가지지만, 내부가 경계에 닿으면 `.messages` 로 휠이 **전파**되어 끊김 없이 상하 흐름이 이어져야 한다.
  3. 모든 결과 테이블에 **RowCount 컬럼**(첫 컬럼 `#`) 이 항상 포함되어, 스크롤 중에도 몇 번째 행인지 바로 알 수 있다.
  4. 결과 테이블의 **첫 행(헤더) + 첫 열(#)** 은 내부 스크롤 동안 고정되어 보인다(Excel 의 `Freeze first row + first column` 과 동일한 개념).
  5. "전체 데이터 보기" 로 CSV 전체를 로드해도 동일하게 RowCount + freeze 가 유지된다.
- 접근:
  1. **`.message-details-body` 단일화** — `max-height`, `overflow`, `overscroll-behavior`, `padding-right` 제거. 말풍선 본문은 자연스럽게 자라고, 채팅 로그(`.messages`) 가 유일한 세로 스크롤 컨테이너가 된다. TASK-0030 의 scroll anchor(summary 클릭 시 `messageLogEl.scrollTop` 보정) 은 그대로 동작 — 애초에 `messageLogEl` 기준으로 측정하므로 inner cap 유무와 무관.
  2. **내부 컨테이너 휠 전파 허용** — `.result-table-wrap`, `.sql-block` 의 `overscroll-behavior: contain` 제거. 스크롤 자체는 남기되 경계에서 부모(.messages)로 휠이 넘어가게 한다. 내부 max-height 은 조금 넉넉히 — `.result-table-wrap { max-height: min(60vh, 460px) }`, `.sql-block { max-height: min(40vh, 320px) }` 로 상향(사용자의 "최대한 바깥 스크롤이 나타나지 않도록 확장" 요청 반영).
  3. **`buildResultTable()` 에 RowCount 삽입** — thead 에 `<th class="col-rownum">#</th>` prepend, tbody 의 각 tr 에 `<td class="col-rownum">{i+1}</td>` prepend. 데이터 컬럼 카운트는 그대로 `columns.length` 로 유지(meta 의 `N열` 문구 영향 없음).
  4. **sticky freeze CSS**:
     ```css
     .result-table { border-collapse: separate; border-spacing: 0; }
     .result-table thead th {
       position: sticky; top: 0; z-index: 2;
       background: var(--bg);
       box-shadow: inset 0 -1px 0 var(--border);
     }
     .result-table th.col-rownum,
     .result-table td.col-rownum {
       position: sticky; left: 0; z-index: 1;
       background: var(--bg);
       color: var(--text-muted);
       font-variant-numeric: tabular-nums;
       text-align: right;
       min-width: 40px;
       width: 40px;
       box-shadow: inset -1px 0 0 var(--border);
     }
     .result-table thead th.col-rownum { z-index: 3; }  /* corner: 두 축 모두 최상위 */
     ```
     `border-collapse: separate` 는 sticky 셀에 border 가 제대로 그려지도록 필요 — box-shadow 로 border 대체.
  5. **`loadFullCsvIntoTable()` 동일 패턴 적용** — thead 재구성 시 `#` 먼저, tbody 재구성 시 각 tr 에 `i+1` 먼저.
  6. 기존 `result-table th:last-child, td:last-child { border-right: none }` 는 유지(마지막 데이터 컬럼의 우측 border 제거). sticky 코너가 배경색과 일치해 content 가 뒤쪽으로 비치지 않도록 `background: var(--bg)` 확인.
- 범위 제한:
  - backend API / `preview_table` 응답 스키마 변경 없음. RowCount 는 순수 클라이언트 가상 컬럼.
  - Navigator(`sql-navigator`) 구조/키보드 로직 변경 없음.
  - 말풍선 폭 정책(TASK-0030) 변경 없음.
  - SQL 블록 구조(pre tag) 변경 없음 — 기존 `formatSqlForDisplay()` / pre-wrap 유지.
- 검증 기준:
  1. 쿼리 결과 ≥ 20행을 포함한 말풍선을 펼쳤을 때 `.message-details-body` 에 scrollbar 가 나타나지 않는다(`overflow` 제거 확인).
  2. 결과 테이블 영역에서 세로 스크롤 시 헤더 row 가 상단에 고정되어 보인다 (`getComputedStyle(thead th).position === 'sticky'`).
  3. 가로 스크롤 시 `#` 컬럼이 좌측에 고정되어 보인다 (`getComputedStyle(td.col-rownum).position === 'sticky'`).
  4. 결과 테이블 내부에서 세로로 스크롤하다 바닥/천장에 닿으면 `.messages` 로 휠이 전파되어 채팅 전체 스크롤이 이어진다(overscroll-behavior 제거 효과).
  5. "전체 데이터 보기" 클릭 후에도 #/sticky 동작 유지.
  6. 단일 말풍선 내부에 세로 스크롤바는 최대 1개(= 결과 테이블)만 동시 존재. `.message-details-body` / `.sql-block` (SQL 이 짧을 때) 에는 스크롤바 없음.
  7. 브라우저 자동화로 위 2/3/6 을 `eval` 로 확인 + 스크린샷 캡처.

### TASK-0032 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - 작업 화면에서 사용자가 특정 동작(대화 생성/제목 변경/삭제/중단/즉시답변/요청 전송)을 시도했을 때 권한이 없으면 버튼이 **아예 숨겨지거나 조용히 무시되어** 사용자는 "어떤 권한"이 필요한지 알 수 없다. 결과적으로 관리자에게 "그냥 권한 다 줘 주세요" 같은 불필요·과도한 요청이 반복된다.
  - Profile > 계정 탭의 권한 pill 에 마우스를 올리면 툴팁에 **영문 권한 id 만 노출**([app.js:387](../src/static/app.js#L387) `item.title = code`)되어, `conversation.rename.own` 같은 코드를 일반 사용자가 해석할 수 없다.
  - 원인:
    1. [app.js:340-393](../src/static/app.js#L340-L393) `buildPermissionPills()` — `item.title = code` 한 줄. 서술 맵 부재.
    2. [app.js:1102-1105](../src/static/app.js#L1102-L1105) `renderComposer()` 에서 cancel/finalize/rename/delete 버튼을 `classList.toggle("hidden", !canX)` 로 처리 — 권한이 없으면 버튼 자체가 사라져 "이 동작이 있다"는 정보조차 사라짐.
    3. [app.js:1250](../src/static/app.js#L1250), [app.js:1258](../src/static/app.js#L1258), [app.js:1272](../src/static/app.js#L1272), [app.js:1304](../src/static/app.js#L1304), [app.js:1313](../src/static/app.js#L1313), [app.js:1323](../src/static/app.js#L1323) — 각 action 함수가 `if (!canX(...)) return;` 로 **조용히** 리턴. 사용자 피드백 없음.
    4. [app.js:548](../src/static/app.js#L548), [app.js:1088](../src/static/app.js#L1088) `renderAccessNotice()` / `renderComposer()` 안내 문구가 "대화 요청 실행 권한이 없습니다" 까지만 말하고 **어떤 permission code 를 요청해야 하는지 명시하지 않는다**.
- 목표:
  1. Profile > 계정 권한 pill hover 툴팁이 "이 권한이 실제로 어떤 동작을 허용하는지" 한국어 서술 문장 + 권한 코드를 모두 보여준다.
  2. 사용자가 차단된 동작을 시도했을 때(버튼 클릭 / 전송 / 단축키), **필요 권한 이름 + 관리자 요청 문구** 가 포함된 토스트가 즉시 노출된다.
  3. 버튼 가림 정책 변경: context 상 의미있는 상태(대화 선택됨 / 처리 중)에서는 **권한이 없어도 버튼을 유지**하되 `aria-disabled="true"` + 희미한 스타일로 "존재는 하지만 현재 계정으로는 실행 불가"임을 암시. 툴팁에도 필요 권한을 명시.
  4. 조회 전용 / 복구 가능 상태 안내 문구(`accessNoticeEl`, `composerHintEl`)에도 필요한 권한 코드를 명시.
  5. 기존에 자연스레 숨겨야 할 경우(대화 미선택 상태의 제목 변경 버튼 등)는 그대로 숨김 유지 — context 상 의미가 없기 때문.
- 접근:
  1. **권한 서술 맵 추가 ([app.js:97](../src/static/app.js#L97) 부근)**:
     ```js
     const PERMISSION_DESCRIPTIONS = {
       "console.access": "관리 콘솔에 접속할 수 있는 권한입니다.",
       "console.manage": "관리 콘솔에서 계정/역할/권한을 저장 커밋할 수 있는 권한입니다.",
       "account.read": "계정 목록과 상세 정보를 조회할 수 있는 권한입니다.",
       // ... 33개 모두 서술 ...
       "conversation.rename.own": "내가 소유한 대화의 제목을 변경할 수 있는 권한입니다.",
       "conversation.rename.any": "모든 사용자의 대화 제목을 변경할 수 있는 권한입니다.",
       // ...
     };
     function describePermission(code = "") {
       return PERMISSION_DESCRIPTIONS[code] || "권한 설명이 등록되어 있지 않습니다.";
     }
     ```
  2. **필요 권한 반환 헬퍼**:
     ```js
     // 현재 대화에서 action 을 실행하기 위해 필요한 "대안 권한 코드들"을 반환.
     // 예: conversation.rename → ["conversation.rename.any"] 또는 own 대화면 ["conversation.rename.any", "conversation.rename.own"].
     // 이 중 하나라도 granted 면 허용.
     function requiredPermissionsFor(action, conversation = currentConversation()) {
       const own = conversation ? isOwnConversation(conversation) : false;
       switch (action) {
         case "conversation.ask":     return { label: "대화 요청 실행", codes: ["conversation.ask"] };
         case "conversation.create":  return { label: "새 대화 생성", codes: ["conversation.create"] };
         case "conversation.rename":  return { label: "대화 제목 변경", codes: own ? ["conversation.rename.any", "conversation.rename.own"] : ["conversation.rename.any"] };
         case "conversation.delete":  return { label: "대화 삭제",     codes: own ? ["conversation.delete.any", "conversation.delete.own"] : ["conversation.delete.any"] };
         case "conversation.cancel":  return { label: "대화 중단",     codes: own ? ["conversation.cancel.any", "conversation.cancel.own"] : ["conversation.cancel.any"] };
         case "conversation.finalize":return { label: "즉시 답변",     codes: own ? ["conversation.finalize.any","conversation.finalize.own"] : ["conversation.finalize.any"] };
         default:                     return { label: action, codes: [] };
       }
     }
     function hasAnyPermission(codes = []) { return codes.some((c) => can(c)); }
     ```
  3. **차단 토스트 헬퍼**:
     ```js
     function showPermissionDeniedToast(action, conversation = currentConversation()) {
       const req = requiredPermissionsFor(action, conversation);
       if (!req.codes.length) { showToast(`'${req.label}' 을(를) 실행할 수 없습니다.`, true); return; }
       const missing = req.codes.filter((c) => !can(c));
       const primary = missing[0] || req.codes[0];
       const desc = describePermission(primary);
       const alt = req.codes.length > 1 ? `(또는 ${req.codes.slice(1).join(", ")})` : "";
       showToast(`'${req.label}' 권한이 필요합니다. 관리자에게 \`${primary}\`${alt ? " " + alt : ""} 권한 부여를 요청하세요.\n${desc}`, true);
     }
     ```
  4. **buildPermissionPills 툴팁 서술화**:
     ```js
     item.title = `${describePermission(code)}\n(${code})`;
     ```
     (short label 은 pill 의 `textContent`로 유지, 서술 문장은 hover 툴팁에만 노출 — 레이아웃 변경 없음)
  5. **버튼 visibility 정책 전환** ([app.js:1102-1105](../src/static/app.js#L1102-L1105)):
     - `cancelBtn` / `finalizeBtn`: "처리 중" 컨텍스트에서만 의미가 있으므로 `hidden` 토글은 `processing` 여부에만 매핑. 권한 부재는 `aria-disabled + .is-access-blocked` 로 표현.
     - `renameConversationBtn` / `deleteConversationBtn`: 대화가 선택되었을 때만 의미가 있으므로 `hidden` 토글은 `state.activeConversationId` 에만 매핑. 권한 부재는 `aria-disabled + .is-access-blocked`.
     - 헬퍼:
       ```js
       function markAccessBlocked(btn, action, conversation) {
         const req = requiredPermissionsFor(action, conversation);
         const blocked = !hasAnyPermission(req.codes);
         btn.classList.toggle("is-access-blocked", blocked);
         if (blocked) {
           btn.setAttribute("aria-disabled", "true");
           btn.dataset.blockedAction = action;
           const missing = req.codes.filter((c) => !can(c))[0] || req.codes[0];
           btn.title = `'${req.label}' 권한이 없습니다. 필요 권한: \`${missing}\``;
         } else {
           btn.removeAttribute("aria-disabled");
           delete btn.dataset.blockedAction;
           btn.title = "";
         }
       }
       ```
  6. **클릭 핸들러 보강** ([app.js:1534-1580](../src/static/app.js#L1534-L1580)):
     - 각 핸들러 본문 맨 앞에 `if (btn.getAttribute("aria-disabled") === "true") { showPermissionDeniedToast(action, currentConversation()); return; }` 추가.
     - `createConversation()`, `renameCurrentConversation()`, `deleteConversation()`, `cancelCurrentRun()`, `finalizeCurrentRun()`, `sendPrompt()` 내부의 조용한 `if (!canX) return` 도 `if (!hasAnyPermission(req.codes)) { showPermissionDeniedToast(action); return; }` 패턴으로 교체 — 단축키(Ctrl+Enter) 경로에서도 토스트가 나오도록.
  7. **안내 문구 보강** (`renderAccessNotice()`, `renderComposer()`):
     - `accessNoticeEl.textContent = "현재 계정에는 대화 요청 실행 권한(\`conversation.ask\`)이 없습니다. 관리자에게 권한을 요청하세요.";`
     - `composerHintEl.textContent = "현재 계정에는 대화 요청 실행 권한(\`conversation.ask\`)이 없습니다. 관리자에게 요청하세요.";`
     - Profile 의 "사용 가능한 권한이 없습니다" 문구는 그대로 (별도 추가 작업 불필요).
  8. **CSS** (`styles.css`):
     - `.tool-btn.is-access-blocked` + `.tool-btn[aria-disabled="true"]` 에 `opacity: .38; cursor: help; color: var(--text-muted);` 지정 — 기존 `:disabled` 스타일 재사용하되 click 은 계속 통과.
     - `button.is-access-blocked` hover 시 네이티브 `title` 툴팁이 뜨도록 `pointer-events: auto` 유지 (기본값이라 별도 선언 불필요).
- 범위 제한:
  - 백엔드 API 변경 없음. 권한 정의 테이블(WebPermissions) 그대로 사용.
  - admin 콘솔 쪽 UX 는 TASK-0031 이 마무리되었으므로 이번 범위에서 제외.
  - Profile 드로어의 "활성 권한" 섹션 외관은 유지 (그룹핑/카운트 배지 TASK-0027 그대로).
  - "부족한 권한 전체 목록" 같은 별도 UI 섹션은 추가하지 않는다 — 동작 시도 시점에 안내되므로 과설계.
- 검증 기준:
  1. Profile > 계정 탭에서 임의의 권한 pill 에 hover → 툴팁에 한국어 서술 문장 + `(code)` 가 표시된다(단순 `code` 가 아님).
  2. operator 계정(= `conversation.delete.own` 미보유) 로그인 → 본인 대화 선택 시 "삭제" 버튼이 보이고 `aria-disabled="true"` + 희미한 색. 클릭하면 토스트 `'대화 삭제' 권한이 필요합니다. 관리자에게 \`conversation.delete.any\` 권한 부여를 요청하세요.` 노출.
  3. 동일 계정에서 대화 미선택 상태에서는 "삭제" 버튼이 (권한과 무관하게) 숨김 — context 상 의미 없음.
  4. pending 계정(= `conversation.ask` 미보유) 로그인 → access notice / composer hint 에 `conversation.ask` 권한 코드 명시. 전송 시도 시 토스트 출현.
  5. admin 계정(모든 권한) 로그인 → 버튼 모두 정상 클릭 가능. `aria-disabled` 없음. 툴팁에도 빈 문자열.
  6. Ctrl+Enter 로 빈 권한 상태 전송 시도해도 동일 토스트 확인 (단축키 경로).
  7. 브라우저 자동화로 위 2번/4번을 재현해 스크린샷 or DOM 상태 증빙.

### TASK-0031 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - 관리 콘솔에서 계정/권한 목록이나 디테일 편집 항목이 많아지면 화면 아래 있어야 할 버튼(예: 페이지 버튼, 저장/취소/삭제 액션)이 외부 스크롤에 의해 뷰포트 밖으로 밀려 **이용자가 존재 자체를 인지하지 못한다**.
  - 원인:
    1. [styles.css:1378-1383](../src/static/styles.css#L1378-L1383) `.admin-workspace { overflow-y: auto }` — workspace 전체가 단일 스크롤 컨테이너. 디테일 pane 이 커지면 그 높이가 workspace 스크롤을 지배하여 리스트 하단 페이지네이션이 **외부 스크롤 아래로 숨음**.
    2. [styles.css:1509-1516](../src/static/styles.css#L1509-L1516) `.admin-list { max-height: calc(100vh - 320px) }` 는 고정 pixel 계산인데다 외부 workspace 스크롤에 의해 의도치 않게 무력화됨.
    3. [admin.html:113-114](../src/static/admin.html#L113-L114) 페이지네이션(`#accountPagination`)이 `.admin-list` 바깥(동일 `.admin-list-col` 자식)으로 위치해, 리스트 내부 스크롤이 아니라 바깥 workspace 스크롤에 종속됨.
    4. [admin.js:854-855](../src/static/admin.js#L854-L855) `.admin-detail-actions`(저장/취소/삭제 버튼 영역)도 detail pane 내용 맨 아래에 append 될 뿐 위치 고정 처리가 없어 detail 이 길어지면 외부 스크롤로만 접근 가능.
- 목표:
  - 관리 콘솔 2열 레이아웃(리스트 / 디테일) 각 컬럼이 **자체 내부 스크롤**을 가지며, 컬럼 하단의 페이지네이션·일괄 액션·detail 저장 버튼은 **항상 뷰포트 내에 노출**된다.
  - 외부(페이지 전체) 스크롤은 발생하지 않는다. 모든 스크롤은 각 pane / 컬럼 내부로 한정.
  - 하단 commit bar, topbar, sidebar 는 기존대로 고정(이미 grid 로 고정되어 있음 — 그대로 유지).
- 접근:
  1. **`.admin-workspace` 를 스크롤 컨테이너에서 flex 컨테이너로 전환**:
     ```css
     .admin-workspace { overflow: hidden; display: flex; flex-direction: column; padding: 20px 24px 24px; min-height: 0; }
     ```
     (`min-height: 0` 은 부모 grid row 에서 flex children 이 overflow 하지 않게 하는 안전장치)
  2. **`.admin-pane.is-active` 가 workspace 를 수직으로 채우도록**:
     ```css
     .admin-pane { display: none; flex-direction: column; gap: 16px; min-height: 0; flex: 1 1 auto; }
     .admin-pane.is-active { display: flex; }
     ```
  3. **`.admin-pane-head` 는 고정**(shrink 없음):
     ```css
     .admin-pane-head { flex-shrink: 0; }
     ```
  4. **리스트-디테일 컨테이너가 남은 공간을 채우고, 자식 컬럼이 동일 높이를 가지도록**:
     ```css
     .admin-list-detail { flex: 1 1 auto; min-height: 0; align-items: stretch; }
     ```
     (기존 `align-items: start` 는 제거 — start 로는 두 컬럼이 콘텐츠 길이에 따라 다르게 자라므로)
  5. **리스트 컬럼 = 고정 헤더(툴바/리스트-헤드) + 내부 스크롤 본문 + 고정 푸터(페이지네이션/일괄 액션)**:
     ```css
     .admin-list-col { min-height: 0; max-height: 100%; }
     .admin-list-toolbar, .admin-list-head { flex-shrink: 0; }
     .admin-list { flex: 1 1 auto; min-height: 0; max-height: none; overflow-y: auto; }
     .admin-list-pagination, .admin-bulk-actions { flex-shrink: 0; border-top: 1px solid var(--border-subtle); margin-top: 4px; padding-top: 8px; }
     ```
     기존 하드코딩 `max-height: calc(100vh - 320px)` 제거.
  6. **디테일 컬럼 = 내부 스크롤 본문 + 하단 sticky 액션 바**:
     - CSS 만으로 마지막 자식 `.admin-detail-actions` 를 sticky 하게 만들면, 내부 구조 변경 없이 저장/취소/삭제 버튼이 detail pane 하단에 항상 노출된다:
     ```css
     .admin-detail-col { min-height: 0; max-height: 100%; overflow-y: auto; padding-bottom: 0; }
     .admin-detail-actions {
       position: sticky;
       bottom: 0;
       background: var(--surface);
       margin: 0 -22px -18px;   /* detail-col padding(18 22)을 상쇄해 전폭 바 */
       padding: 10px 22px;
       border-top: 1px solid var(--border);
       z-index: 1;
     }
     ```
  7. **대시보드 pane** 은 카드 + pending 미리보기만 있으므로 내부 스크롤이 필요한 경우에만 대비:
     ```css
     .admin-pane[data-admin-pane="dashboard"] { overflow-y: auto; }
     ```
  8. **뷰포트가 좁을 때 보호**: 기존 반응형 쿼리가 있다면 그대로 유지. 모바일(viewport < 960px) 대응은 이번 범위 아님(이용자는 데스크탑에서 사용).
- 범위 제한:
  - JS(admin.js) 변경 불필요. CSS 만으로 해결.
  - admin.html DOM 구조 변경 불필요(페이지네이션·액션 바가 각각 올바른 컬럼의 마지막 자식에 이미 위치).
  - 채팅 쪽, backend 변경 없음.
- 검증 기준:
  1. 브라우저로 `/admin` 열어 계정 탭 진입 → 페이지를 스크롤하지 않고도 페이지네이션 버튼이 리스트 하단에 보인다.
  2. 계정을 선택해 디테일에 많은 권한 그룹을 펼친 상태에서도 리스트 컬럼의 페이지네이션은 그대로 보이며, 디테일 하단 저장/취소 버튼도 sticky 로 노출된다.
  3. 리스트 컬럼에서 스크롤해도 페이지네이션은 리스트 아래에 고정 위치. 디테일 컬럼에서 스크롤해도 액션 바는 하단에 고정.
  4. `document.documentElement.scrollHeight === document.documentElement.clientHeight` 인지 확인(외부 스크롤 없음).
  5. 역할 탭에서도 동일 동작(역할 일괄 액션 바/detail 저장 버튼).
  6. 브라우저 자동화로 위 동작을 재현·수치 검증.

### TASK-0030 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  - assistant 답변의 "실행 단계 및 쿼리 결과 보기" `<details>` 블록을 펼칠 경우, 결과셋 구성(쿼리 수/행 수/컬럼 수/SQL 길이)에 따라 말풍선의 높이와 폭이 비결정적으로 커져 **채팅 스크롤 위치가 움직이고**, 사용자가 방금 보던 문장을 놓친다.
  - 원인 1: [styles.css:721-725](../src/static/styles.css#L721-L725) `.message { max-width: 82% }`가 user/assistant 양쪽에 동일 적용되어, assistant 말풍선이 기본적으로 좁고, 내용이 커지면 높이로 비대해진다.
  - 원인 2: [styles.css:838-843](../src/static/styles.css#L838-L843) `.message-details-body`에 max-height/overflow 제약이 없어서 내부 SQL · 테이블 · 긴 `<pre>` 가 수직으로 끝없이 누적된다.
  - 원인 3: [styles.css:894-898](../src/static/styles.css#L894-L898) `.result-table-wrap` 기본형은 `overflow-x: auto`만 있고 수직 cap이 없다 ("is-full-data" 변형만 360px 로 제한). 결과 preview가 많이 잘리지 않은 상태면 높이가 무제한.
  - 원인 4: [styles.css:877-891](../src/static/styles.css#L877-L891) `.sql-block`은 `pre-wrap`이지만 초장문 SQL 은 여전히 화면 높이를 밀어낸다.
  - 원인 5: [app.js:980-1023](../src/static/app.js#L980-L1023) `renderMessageDetails()`는 `<details>` 펼침/접힘 시 스크롤 앵커 로직이 없어, `<summary>` 위치가 뷰포트 내에서 통째로 이동한다.
- 목표:
  1. assistant 말풍선은 기본적으로 **넓은 폭으로 고정**(우측 사용자 질문 영역과 구분할 수 있는 소량 여백만 유지). 펼친 내용의 크기에 따라 말풍선 폭이 흔들리지 않는다.
  2. 말풍선 내부가 너무 길어지면 **말풍선 내부에서 수직/수평 스크롤**로 처리한다. 말풍선 바깥 레이아웃(채팅 스크롤, 사이드바, 메시지 간격)은 변형되지 않는다.
  3. `<details>` 펼침/접힘 시 **`<summary>`가 뷰포트 내 동일 위치에 유지**되도록 스크롤을 보정한다(scroll anchor).
  4. user 말풍선은 우측 정렬 좁은 형태를 유지해 assistant와 시각적으로 확실히 구분된다.
- 검토한 대안:
  - Option A (사용자 제안 원형): 말풍선 전폭 + 내부 수평 스크롤. 단순하고 직접적.
  - Option B (Claude artifact 사이드 패널): 결과셋을 별도 right-panel에 띄워 채팅 흐름과 분리. 현재 이슈 해결에는 과설계이며 Navigator/CSV 링크/progress strip 과의 통합 비용이 큼.
  - Option C (채택): **말풍선 고정 폭 + `<details>` 본문 max-height 캡 + 중첩 스크롤 + summary 클릭 스크롤 앵커**. Option A의 직접성에 scroll anchor를 더해 "펼칠 때 위치가 튀는" 부작용까지 해소. 기존 Navigator/CSV 흐름 그대로 재사용.
- 접근:
  1. **말풍선 폭 분기 (styles.css)**:
     - 기존 `.message { max-width: 82% }` 를 제거하고 역할별로 분리:
       ```css
       .message.is-user      { max-width: 72%; }
       .message.is-assistant { max-width: calc(100% - 48px); }
       ```
       (assistant 는 우측으로만 약 48px 여백, 나머지는 전부 사용 — 사용자 질문 영역과 구분은 이 여백으로 확보)
     - `.message-bubble` 에 `width: 100%; min-width: 0;` 추가해 말풍선 자체가 자식 내용에 의해 팽창하지 않도록 고정한다.
  2. **펼침 본문 내부 스크롤 (styles.css)**:
     - `.message-details-body { max-height: min(60vh, 520px); overflow: auto; overscroll-behavior: contain; }` — 펼침 시 본문 전체가 내부 세로 스크롤. `overscroll-behavior: contain`으로 내부 끝에 도달해도 상위 채팅 스크롤이 이어서 움직이지 않게 격리.
     - `.message-details[open] .message-details-body { padding-right: 4px; }` 로 스크롤바가 생길 때 콘텐츠가 숨지 않게 여유.
  3. **결과 테이블 기본 스크롤 (styles.css)**:
     - `.result-table-wrap { max-height: 320px; overflow: auto; }` 기본 캡 (기존에는 수평 스크롤만). "전체 데이터 보기"로 CSV 를 로드한 경우(`is-full-data`)는 기존 360px 를 유지.
  4. **초장문 SQL 캡 (styles.css)**:
     - `.sql-block { max-height: 240px; overflow: auto; }` — 수백 줄 SQL이 말풍선을 뚫고 들어오는 걸 방지. 기존 pre-wrap/word-break 은 유지.
  5. **Navigator 패널 min-width (styles.css)**:
     - `.sql-navigator`, `.sql-nav-panel`, `.sql-result-group` 에 `min-width: 0` 재확인(이미 있는 곳도 있으나 누락된 곳 보강)해 flex/grid shrink 허용.
  6. **스크롤 앵커 (app.js)**:
     - [app.js:980-1023](../src/static/app.js#L980-L1023) `renderMessageDetails()` 에서 `<summary>` 에 `click` 리스너를 추가:
       - 클릭 직전에 `summary.getBoundingClientRect().top - messageLogEl.getBoundingClientRect().top` 을 기록(=`prevOffset`).
       - `requestAnimationFrame` 2회 후(`<details>` open 상태 토글 + 레이아웃 반영 이후) 같은 값을 다시 계산해 `delta = newOffset - prevOffset` 만큼 `messageLogEl.scrollTop` 을 더한다.
     - 결과: `<summary>` 라인은 사용자 뷰포트에서 동일한 y좌표에 고정되고, 펼침으로 생긴 공간은 `<summary>` 아래로만 밀려난다.
     - 접힘 시에도 같은 로직이 대칭으로 작동 (summary 위치 유지).
- 범위 제한:
  - 백엔드/agent-core 변경 없음.
  - 기존 SQL Navigator, CSV 다운로드, "전체 데이터 보기", Progress Strip `<details>` 는 그대로 유지. Progress Strip 은 이번 이슈의 범주가 아님 (이미 TASK-0022 에서 max-height 처리됨).
  - admin 콘솔 쪽 CSS 변경 없음.
- 검증 기준:
  1. assistant 말풍선이 기본적으로 채팅 pane 의 오른쪽 약간(≈48px)만 남기고 좌측부터 넓게 차지한다. user 말풍선은 우측 정렬 좁은 형태로 구분된다.
  2. `<details>` 접힌 상태의 말풍선 크기가, `<details>` 를 펼쳐도 **폭이 변하지 않는다**. 내부에 긴 SQL · 큰 결과 테이블 · 여러 쿼리 Navigator 가 있어도 말풍선의 폭/높이 outline 은 결과셋 구성에 무관하게 일정(max-height 내부 스크롤로 흡수).
  3. `<summary>` 클릭으로 펼칠 때 해당 `<summary>` 라인이 뷰포트 내 동일 좌표에 유지된다. 접을 때도 동일. 채팅 로그 다른 메시지들의 뷰포트 위치가 튀지 않는다.
  4. 결과 테이블 내부에서 세로/가로 스크롤이 작동하고, 채팅 로그 스크롤과 독립적(`overscroll-behavior: contain`)이다.
  5. 단일 SQL step / 다중 SQL Navigator / CSV 전체 데이터 로드 / `meta.sql` 폴백 네 경로 모두에서 위 동작이 일관된다.
  6. 브라우저 자동화(또는 수동) 스크린샷으로 "펼침 전/후 말풍선 bounding box 동일" 과 "summary 좌표 불변"을 확인.

### TASK-0029 상세 설계
- 문제 (사용자 테스트 피드백 2026-04-21):
  1. OVERVIEW / ACCOUNTS / ROLES 3개 섹션이 한 화면에 스택되어 있어 ([admin.html:22-111](../src/static/admin.html#L22-L111)) 현황을 한눈에 파악하기 어렵다.
  2. 페이지 좌우 여백 때문에 정보 표현 공간이 낭비된다. (채팅 "작업 화면"은 `100vw` app-shell 레이아웃을 쓰는 반면, admin은 좁은 surface-card 3개를 세로로 쌓은 구조)
  3. ACCOUNTS 섹션의 `#adminSearch`("사용자 ID 검색…") 플레이스홀더를 보고 ROLES 요소를 찾으려다 실패하는 사용자 동선이 확인됨. 한 화면에 두 섹션이 동시에 보여 검색 범위에 대한 혼동을 유발.
  4. 각 계정/역할이 모든 필드를 펼친 채로 나열되어 있어 목록 탐색이 어렵다. 요약 라인 + 클릭 시 상세 펼침이 필요.
  5. 계정 "관리"는 **일괄 작업**이 전제되어야 한다. (여러 계정에 권한 추가/수정/제거, 일괄 삭제 등)
  6. **크리티컬 버그**: 여러 계정을 동시에 수정한 뒤 특정 계정 하나에서 "저장" 누르면 나머지 계정의 pending 변경사항이 모두 소실됨. 원인: [admin.js:463-483](../src/static/admin.js#L463-L483)에서 저장 성공 후 `loadAdminData()`가 전체 DOM을 re-render하면서 다른 form의 pending edit가 지워진다. 역할 편집도 동일 패턴([admin.js:641-662](../src/static/admin.js#L641-L662)). AWS IAM 콘솔처럼 **pending changes 누적 + 일괄 commit** 구조로 전환 필요.
  7. Admin 화면이 "작업 화면"과 구성/레이아웃이 달라 위화감이 있다.
- 목표:
  - 관리 콘솔을 **탭 기반 네비게이션** + **마스터-디테일 리스트** + **AWS 스타일 일괄 commit 바** 구조로 전환.
  - 여러 계정/역할을 동시에 수정해도 각각의 pending 상태가 유지되며, 화면 하단의 "변경사항 N건 · 적용 / 취소" 바에서 일괄 커밋.
  - 채팅 작업 화면의 `app-shell` 스타일(전폭 + 좌측 사이드 + 상단 topbar)과 톤을 맞춘다.
- 접근:
  1. **레이아웃 재구성 (admin.html)**:
     - 현재 `<main class="admin-main admin-section-stack">` 3 section 스택 구조를 제거하고, 채팅 `app-shell`과 유사한 3영역 레이아웃으로 전환:
       ```
       <body class="admin-shell">
         <header class="topbar"> (브랜드 / 탭 네비 / 로그아웃)
         <aside class="admin-sidebar"> (대시보드 / 계정 / 역할 탭 버튼, 각 탭에 배지: 계정 N, 역할 M, pending 변경 K)
         <main class="admin-workspace"> (선택된 탭의 패널만 표시)
         <footer class="admin-commit-bar"> (pending 변경 N건 · 취소 · 모두 적용)
       ```
     - 각 탭 패널은 `<section data-admin-pane="dashboard|accounts|roles">`로 구성하고 비활성 탭은 `display:none`.
  2. **대시보드 탭 (신규)**:
     - 현재 4개 metric card(Active/Inactive/Deleted/Roles)를 유지하되 카드를 더 크게 배치하고 보조 정보 추가:
       - 최근 7일 로그인한 계정 수
       - 권한이 할당된 역할 수 / 전체 역할 수
       - pending 변경사항 미리보기 리스트 (있을 때만)
     - 전폭을 활용해 grid-template-columns를 반응형으로 (`repeat(auto-fit, minmax(220px, 1fr))`).
  3. **계정 탭 — 마스터/디테일 구조**:
     - 레이아웃: 좌측 account list (username, role, 상태 뱃지, pending 마크) + 우측 detail pane (선택된 계정의 편집 폼).
     - 리스트 각 row: checkbox + username + role 이름 + 상태 chip + pending 표시(`•`). 클릭 시 detail pane에 해당 계정 로드.
     - 리스트 상단 툴바: **scoped search** ("계정/사용자 검색…"으로 플레이스홀더 변경), 상태 필터(전체/활성/비활성/삭제), 선택된 row 수 + 일괄 액션 드롭다운(활성화/비활성화/삭제/역할 변경/권한 추가/권한 제거).
     - detail pane: 기존 per-form submit 제거. form의 value change event → `adminState.pending.accounts.set(id, patch)` 에 기록만 하고 서버 호출 없음. 저장 버튼은 detail pane 내부에 "이 변경을 pending에 추가" 같은 로컬 확정 버튼으로 둔다(혹은 inputs 가 변하면 자동으로 pending 에 들어가는 방식, 이쪽이 더 AWS 스타일).
     - pending patch가 있는 계정은 리스트/detail 모두에서 `•` 마커로 표시.
  4. **역할 탭 — 마스터/디테일 구조**:
     - 동일 패턴. 리스트(role name + key + 멤버 수 + 활성 뱃지 + pending 마크) + detail pane(name/description/permission grid/활성/기본 가입).
     - 역할 생성 폼은 리스트 상단 "+ 새 역할" 버튼 → detail pane에 빈 폼 로드 (별도 페이지/모달 없이 동일 pane 재사용).
     - 역할 일괄 작업: 선택된 역할들을 활성/비활성 토글, 삭제.
  5. **Pending / Commit 상태 모델 (admin.js)**:
     ```js
     adminState.pending = {
       accounts: new Map(),  // id -> { role_id?, is_active?, permission_overrides?, _delete?: true }
       roles: new Map(),     // id -> { name?, description?, is_active?, is_default_signup?, permission_codes?, _delete?: true, _create?: { role_key, ... } }
       createRoles: [],      // 임시 생성한 역할들 (tempId 관리)
     };
     ```
     - `adminState.pending`의 변경마다 commit bar 카운트/내용 업데이트.
     - commit bar `모두 적용`: pending의 각 entry에 대해 PATCH/DELETE/POST 순차 호출(또는 `Promise.all`, 에러 시 실패한 항목만 pending에 남김). 전체 완료 후 `loadAdminData()` 1회.
     - commit bar `취소`: `pending`을 비우고 detail pane 을 현재 서버 값으로 다시 렌더.
     - **핵심**: `loadAdminData()` 는 "모두 적용" 이후에만 호출. 단일 저장으로 전체 DOM 초기화 경로를 제거한다.
  6. **Per-tab scoped search**:
     - `#adminSearch`를 제거하고, 각 탭 리스트 상단에 전용 search input을 배치. 계정 탭: "username 검색", 역할 탭: "역할 이름/키 검색". 대시보드 탭: 검색 없음.
  7. **bulk 작업**:
     - 리스트 row 체크박스 + 헤더 "전체 선택" 체크박스. 선택된 row 수가 1 이상이면 일괄 액션 바 노출.
     - 일괄 액션은 즉시 API 호출하지 않고 pending에 반영(동일 모델).
     - 일괄 권한 추가/제거: 모달 대신 선택 후 드롭다운 → 권한 코드 선택 → 선택된 모든 계정의 `permission_overrides[code]` 를 allow/deny/inherit 로 일괄 세팅.
  8. **CSS (styles.css 추가/수정)**:
     - `.admin-shell` grid: `grid-template-columns: 240px 1fr; grid-template-rows: 60px 1fr 56px;` (topbar + sidebar + main + commit-bar).
     - `.admin-sidebar`: 탭 버튼, 각 버튼에 pending 배지 (`.tab-badge`).
     - `.admin-workspace`: 패널 컨테이너, 전폭 활용.
     - `.admin-list-detail`: `grid-template-columns: minmax(260px, 360px) 1fr; gap: 16px;` — 좌측 리스트 + 우측 디테일.
     - `.admin-list-row`: 선택 상태(`.is-active`), pending 상태(`.has-pending`) 표시.
     - `.admin-commit-bar`: `position: sticky; bottom: 0; background: ...; box-shadow: top;` — 변경사항 N건 · 취소 / 모두 적용.
     - 반응형: viewport width 1024px 미만이면 `.admin-list-detail` 가 1열로 스택, 리스트 클릭 시 detail pane 이 리스트 위로 올라오는 모바일 친화 모드.
- 범위 제한:
  - 백엔드 API 변경 없음. 기존 PATCH/DELETE/POST 엔드포인트 그대로 사용.
  - 실제 서버 호출 시점만 변경(개별 → 일괄).
  - 권한 정의(33개 permission, 그룹 라벨)와 `renderPermissionGrid()` 자체는 기존 그대로 재사용 (detail pane 안에서만 호출).
  - 로컬 LLM, chat UI 쪽은 수정하지 않는다.
- 검증 기준:
  1. 관리자 계정 로그인 → `/admin` → 좌측 사이드바에 "대시보드 / 계정 / 역할" 탭 버튼이 보이고, 초기 표시는 대시보드.
  2. 계정 탭 클릭 → 리스트/디테일 2분할 레이아웃. 리스트 검색 플레이스홀더가 "사용자 검색…" 등 계정 전용 문구.
  3. **다중 편집 보존 시나리오**: 계정 A 선택 → role 변경 → 계정 B 선택 → permission override 변경 → 계정 C 선택 → is_active 토글. 하단 commit bar가 "변경사항 3건"을 표시. 계정 A 다시 선택 시 role 변경이 그대로 유지. "모두 적용" 클릭 후 서버 반영 확인.
  4. "취소" 클릭 시 pending 이 비워지고 detail pane 이 서버 값으로 복원된다.
  5. 일괄 선택 시나리오: 계정 3개 체크 → 일괄 비활성화 → commit bar 변경사항 3건 → 적용.
  6. 역할 탭에서도 동일한 pending/commit 모델 동작.
  7. 페이지 좌우 여백이 chat 작업 화면 수준으로 확장되어 있고 (full viewport width), topbar/sidebar 톤이 chat `app-shell` 과 맞춰져 있다.
  8. 브라우저 자동화 스크립트로 위 6번까지 시나리오를 재현해 증빙한다.

### TASK-0027 상세 설계
- 문제:
  - 다른 AI 작업자가 RBAC 권한을 33개(5그룹: console/account/role/conversation + misc)로 세분화했으나, Profile 드로어의 권한 현황 영역은 `buildPermissionPills()`([app.js:326-345](../src/static/app.js#L326-L345))이 활성 권한을 **알파벳순 플랫 리스트**로 렌더링하기만 해서 한눈에 파악 불가.
  - 관리 콘솔의 계정 편집은 `renderPermissionGrid(..., mode="override")`([admin.js:84-146](../src/static/admin.js#L84-L146))에서 33개 permission 각각이 inherit/allow/deny select dropdown으로 렌더링되어 계정 1건당 33개 select가 쌓이고, 페이지당 10개 계정이 나오면 330개 select가 한 화면에 쌓여 실사용 불가 수준이 됨.
  - 역할 편집 권한 그리드([admin.js:384-559](../src/static/admin.js#L384-L559))는 그룹화는 되어 있으나 접기/펼치기가 없어 역할 1건당 5개 그룹 33개 체크박스가 전부 펼쳐져 스크롤 지옥.
- 목표:
  - Profile 드로어: 활성 권한을 그룹(console/account/role/conversation)별로 묶어 섹션 헤더 + pill chip으로 렌더. 그룹 내 권한이 없으면 그룹 자체 숨김.
  - 관리 콘솔 계정 override: `<details>`/`<summary>` 기반 collapsible 그룹으로 전환. summary에 `그룹명 · (N allowed / M denied / 나머지 inherit)` 상태 배지를 표시해 접힌 상태에서도 override 현황이 보이게 함. 기본 접힘.
  - 역할 편집 권한 그리드: 동일한 collapsible 그룹 구조. summary에 `그룹명 · (N/M 선택됨)` 카운트. 기본 접힘(단 선택된 항목이 있는 그룹은 열림).
  - 각 그룹에 "모두 허용 / 모두 거부 / 모두 상속" 배치 액션 버튼(권한 있을 때만). 일괄 조작 가능.
- 접근:
  - `PERMISSION_LABELS`에 그룹 라벨 맵 추가 (`console` → "관리 콘솔", `account` → "계정", `role` → "역할", `conversation` → "대화", `misc` → "기타").
  - app.js `buildPermissionPills()`를 `buildPermissionSections()`로 재작성. 입력: `state.user.permissions` + 서버가 반환한 permission 정의(그룹 정보 포함). 없으면 코드의 앞쪽 토큰(`console.*`, `account.*` 등)으로 폴백 그룹화.
  - admin.js의 `renderPermissionGrid()`에 `collapsible: true` 옵션 추가. 각 그룹을 `<details>`로 감싸고 summary에 실시간 카운트 배지. 배치 액션 버튼 포함.
  - CSS: `.permission-section`, `.permission-section-head`, `.permission-section-counts`, `.permission-bulk-actions` 스타일 추가. 기존 `.permission-group*`/`.permission-grid*` 스타일은 유지하고 `<details>` 내부에서 재사용.
- 검증 기준:
  - Profile 드로어에서 활성 권한이 그룹별 헤더 아래로 묶여 표시된다.
  - 관리 콘솔 계정 1건을 펼쳤을 때 override 섹션이 기본 접힘 상태로 보이고, summary에 그룹별 allow/deny 카운트가 표시된다.
  - 역할 편집 그리드도 동일한 collapsible 그룹 구조로 동작한다.
  - 배치 액션 버튼(모두 허용/거부/상속)이 동일 그룹 내 모든 select/checkbox에 반영된다.
  - 권한이 없는 사용자는 액션 버튼/체크박스가 disabled로 표시된다.
  - 브라우저 자동화로 admin.html을 열어 section 개수, collapsed 상태, 카운트 정확성을 확인한다.

### TASK-0028 상세 설계
- 문제:
  - Insights(스키마/테이블 메타데이터 자동 분석) 기능이 `insight.py`에 660줄로 구현되어 있으나 **어느 문서에도 명시되어 있지 않음**. 사용자 입장에서는 백그라운드 worker가 돌고 있는 것을 "서비스 오류"로 오해함.
  - Insights 외에도 코드에만 있고 문서에 없는 주요 기능들: SYSTEM_PROMPT 설계 의도, TOOL_DEFINITIONS 우선순위 근거, Step Loop/Timeout/Cancel 메커니즘, Knowledge Injection(KNOWN SCHEMAS 자동 주입), CSV 저장(preview_table + csv_paths 2단계 반환), Fingerprint 변경 감지, Advisory Lock 등.
- 목표:
  - feature-0002-agent-core 문서를 "코드만 보면 알 수 없는 기능/설계 의도"가 모두 드러나도록 보강.
  - 신규 문서 2종 추가 + 기존 FUNCTION.md 확장.
  - 각 기능이 "어디서 왜 이렇게 동작하는지"를 실제 코드 경로/줄 번호와 함께 설명.
  - 검증: 문서를 작성하면서 실제 insight worker가 현재 런타임에서 정상 동작하는지(heartbeat, last_cycle_at, last_status) MEMORY DB로 직접 확인.
- 접근:
  1. **`docs/INSIGHTS.md` 신규 작성**: Insight 시스템 아키텍처 전용 문서.
     - 목적과 사용자 영향 (질의 응답 품질 향상 / 탐색 단계 감소)
     - 3단계 데이터 생성: bootstrap → instance scan → on-demand refresh
     - Worker 구조: `run_insight_worker_loop()` → `run_insight_cycle()` → `_bootstrap_schema_insights()` + `_scan_instance_schema_insights()`
     - Fingerprint 변경 감지 (`_compute_schema_fingerprint`, `_compute_table_fingerprint`, batch 최적화)
     - Advisory Lock (MySQL GET_LOCK 기반, `AGENT_INSIGHT_WORKER_LOCK_NAME`)
     - Heartbeat & Stale 감지 (`_is_insight_worker_heartbeat_fresh` + `AGENT_INSIGHT_WORKER_STALE_SEC`)
     - Inline fallback (`_should_run_inline_insight_scan`, worker 부재 시 ask 시점에 인라인 실행)
     - 메모리 DB 저장 키(`schema_insight:*`, `table_insight:*`, `insight_worker_last_*`)
     - 환경변수 표 (`AGENT_SCHEMA_INSIGHT`, `AGENT_INSIGHT_WORKER_*`, `AGENT_INLINE_INSIGHT_ON_ASK` 등)
     - "오류 아님 신호" 표 — 사용자/운영자가 "이건 오류 같다"고 오해하기 쉬운 로그 라인과 실제 의미.
     - 헬스 체크 SQL snippet (worker heartbeat, last_status, last_error 조회용)
  2. **`docs/AGENT_CORE_INTERNALS.md` 신규 작성**: agent_core + 주변 모듈의 숨은 계약 문서.
     - SYSTEM_PROMPT 구조 설명: CRITICAL DIRECTIVE → CORE RULES → STRATEGY → IDEAL FLOW → ANTI-PATTERNS → SQL PATTERNS → OUTPUT (코드 파일/줄 참조)
     - TOOL_DEFINITIONS 우선순위: execute_sql 최우선 배치 근거 (LRN-20260416-0001와 연결)
     - Knowledge Injection 흐름: `_build_knowledge_context()` → KNOWN SCHEMAS + RELEVANT TABLES 자동 주입
     - Step Loop & Budget: max_steps, timeout, finalize_now 신호, cancel 요청
     - CSV 저장 2단계: preview_table(LLM에 전달, 기본 5행) + csv_paths(전체 결과, 별도 파일)
     - Planner fast path (`_build_insight_object_fast_plan`): 인사이트 기반 빠른 실행 계획 (있을 때)
  3. **`docs/FUNCTION.md` 보강**:
     - "Main Flow" 섹션을 실제 호출 경로로 확장 (knowledge injection → step loop → tool call → memory write).
     - "Dependencies" 섹션에 MEMORY_DB 스키마 의존성 명시 (`AgentMemoryFactEntries`, `AgentMemoryTexts`, insight KV 키 패턴).
     - "Observability" 섹션에 insight_worker 로그 파일과 healthcheck 방법 추가.
  4. **검증**: 실제 MEMORY DB에 접속해 `insight_worker_last_cycle_at`, `insight_worker_last_status`, `schema_insight:*` 몇 개를 조회하고, 문서에 예시 출력으로 넣어 "현재 실제로 이렇게 돌고 있다"는 증빙을 남긴다.
- 범위 제한:
  - 코드 변경 없음. 문서만 추가/갱신.
  - 기존 인사이트 로직/설정값은 그대로 유지.
  - 신규 문서는 `unit/feature-0002-agent-core/docs/` 하위에 배치.
- 검증 기준:
  - 신규 문서 2종이 존재하고, 각 문서에서 언급된 함수/상수/환경변수가 실제 코드에 존재한다.
  - Insight worker 헬스 체크 SQL snippet이 실제 MEMORY DB에 대해 실행 가능하다(검증 과정에서 직접 실행 결과를 문서에 남김).
  - FUNCTION.md Main Flow 내 각 단계가 실제 코드 경로와 일치한다.

### TASK-0026 상세 설계
- 문제: assistant 말풍선에 한 줄로 길게 들어온 SQL(예: `SELECT ... FROM ... WHERE ... GROUP BY ... ORDER BY ...`)이 `<pre class="sql-block">`의 `white-space: pre` + `overflow-x: auto` 특성상 줄바꿈 없이 길게 그려지며, flex/grid 자식의 `min-width` 계산으로 인해 말풍선 전체가 수평으로 확장되는 UX 이슈가 있다.
- 목표:
  - SQL 쿼리가 한 줄로 길게 들어와도 말풍선 폭이 부모(채팅 영역) 폭 이상으로 확장되지 않는다.
  - 쿼리 가독성을 유지하기 위해 주요 키워드 경계에서 줄바꿈을 적용한다. 이미 여러 줄인 쿼리는 원형을 유지한다.
  - 기존 Navigator 헤더/버튼/컨텍스트 레이아웃은 그대로 유지한다.
- 접근:
  - 표시 전용 포매터 `formatSqlForDisplay(sql)` 추가 (저장/실행 SQL에는 영향 없음, `<pre>.textContent`에만 적용):
    - 입력에 이미 `\n`이 있으면 그대로 반환 (LLM이 포맷팅한 경우 존중).
    - 단일 라인일 경우 주요 키워드 경계에서 줄바꿈을 삽입한다. 대상 키워드:
      `SELECT`, `FROM`, `WHERE`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`,
      `LEFT JOIN`, `RIGHT JOIN`, `INNER JOIN`, `OUTER JOIN`, `FULL JOIN`, `CROSS JOIN`, `JOIN`,
      `ON`, `AND`(AND만 분리 시 너무 잦아지므로 `WHERE/ON` 뒤의 AND만), `UNION`, `UNION ALL`, `INSERT INTO`, `UPDATE`, `SET`, `VALUES`, `DELETE FROM`.
    - 정규식 기반으로 구현하되 **따옴표 안의 키워드는 분리하지 않는다**(단순 토크나이저로 문자열 리터럴 내부 스킵).
    - 중첩 괄호(서브쿼리) 깊이는 유지하고 별도 들여쓰기는 하지 않는다(단순화·안정성 우선).
  - CSS 수정:
    - `.sql-block`을 `white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere;` 로 변경(포매터가 못 잡는 초장문 토큰·식별자도 wrap되도록 안전망).
    - `.sql-navigator`, `.sql-nav-panel`, `.sql-result-group` 등 컨테이너에 `min-width: 0`을 보장해 flex/grid 자식 shrink를 허용한다.
  - 기존 단일 step 블록과 Navigator 패널 양쪽 모두 `buildSqlStepPanel()`을 경유하므로 한 곳만 수정하면 된다.
- 범위 제한:
  - 포매터는 표시용(`pre.textContent`) 전용. 서버로 전송되는 SQL, 복사(copy) 시나리오에는 영향을 주지 않는다(복사 시 줄바꿈 포함 허용 — 사용자가 다시 한 줄로 정리하면 되므로).
  - 새 백엔드 API 없음. agent_core / tools 변경 없음.
  - 기존 Navigator/키보드/CSV 전체 보기 로직은 변경하지 않는다.
- 검증 기준:
  - 긴 한 줄 SQL을 주입했을 때 말풍선 폭이 chat pane 폭 이상으로 확장되지 않는다.
  - `SELECT`/`FROM`/`WHERE`/`JOIN`/`GROUP BY`/`ORDER BY` 경계에서 줄바꿈이 삽입된다.
  - 이미 여러 줄로 포맷된 쿼리는 원형이 유지된다.
  - 따옴표 내부 문자열의 키워드(예: `'SELECT one, ...'`)는 분리되지 않는다.
  - 기존 Navigator 키보드 조작(`←/→/Home/End`)과 "전체 데이터 보기"가 그대로 동작한다.

### TASK-0025 상세 설계
- 문제: assistant 말풍선 내 `<details>`(실행 단계 및 쿼리 결과 보기)를 펼치면, execute_sql step이 여러 개인 경우 각 SQL + 결과 테이블이 수직으로 누적되어 말풍선 길이가 과도하게 증가한다. UI 개편 이전에 있었던 별도 팝업(`CSV 미리보기`) 방식은 창 크기가 레코드 수에 따라 흔들리는 UX 이슈가 있었다.
- 목표:
  - 말풍선 내 `<details>` 안에서 다수 SQL step을 수직 누적 없이 탐색 가능한 Navigator로 압축한다.
  - 각 말풍선의 탐색 범위는 해당 말풍선으로만 한정된다(격리된 스코프). 현재 선택된 결과셋이 어떤 SQL에 대응하는지 화면에서 상시 확인 가능해야 한다.
  - preview 레코드 제한을 넘어 전체 데이터도 조회 가능해야 한다(CSV 기반).
  - 키보드 조작 가능, 단 조작법은 화면에 상시 노출하지 않고 버튼의 `title` 툴팁(마우스 hover)으로만 힌트 제공.
- 접근:
  - `buildStepBlocks()`를 분해. execute_sql step이 2개 이상이면 Navigator 형태로 렌더링, 1개면 기존 단일 블록 유지.
  - Navigator 구조:
    - 헤더(1행): `◀` 이전 버튼 + `쿼리 n/N` 인디케이터 + `▶` 다음 버튼 + 현재 쿼리의 첫 테이블 참조(작업 대상) 라벨.
    - 본문: 현재 인덱스의 SQL `<pre>` + 결과 테이블 + 액션 영역(전체 데이터 보기, CSV 다운로드).
  - 키보드 조작:
    - Navigator 컨테이너에 `tabindex="0"` 부여 → 포커스 시 `←`/`→`로 prev/next, `Home`/`End`로 처음/끝 이동.
    - 각 버튼의 `title`에 단축키 힌트 포함(예: `이전 쿼리 (←)`).
  - 전체 데이터 조회:
    - preview_table이 truncated이고 csv_paths가 있을 때 "전체 N행 보기" 버튼 노출.
    - 클릭 시 `/api/file?path=...` 로 CSV fetch → 클라이언트 측 CSV 파서로 파싱 → 기존 테이블의 tbody를 전체 행으로 교체.
    - 대량 행(>500) 렌더 시 테이블 컨테이너 `max-height` + `overflow:auto`로 말풍선 영역 보호.
  - 스코프 격리:
    - Navigator 인스턴스마다 내부 상태(현재 인덱스)를 가지며, 말풍선 별로 완전 격리.
    - 헤더 상단에 "쿼리 1/3 · `schema.table`" 형태로 현재 선택 컨텍스트 상시 노출.
  - 접근성:
    - 버튼에 `aria-label`, 인디케이터에 `aria-live="polite"` 부여.
    - 키보드 포커스 시 outline 스타일 유지(제거하지 않음).
- 범위 제한:
  - 새로운 백엔드 API 추가 없음. 기존 `/api/file`만 재사용.
  - 기존 `<details>` 드롭다운 구조는 유지(그 안의 렌더링만 교체).
  - 단일 SQL step 케이스는 Navigator를 쓰지 않고 기존 블록 유지(불필요한 chrome 방지).
- 검증 기준:
  - operator 계정으로 2개 이상 execute_sql step을 발생시키는 질의 전송 후, Navigator로 단계 탐색이 정상 동작한다.
  - 키보드 `←/→/Home/End`로 step 이동 가능.
  - "전체 데이터 보기" 클릭 시 preview 이상의 행이 테이블에 렌더링된다.
  - 말풍선 총 높이가 step 수와 무관하게 한 화면 내로 유지된다.

## 4. Blocked
- 없음

## 5. Done
- TASK-0010 (2026-04-15): `WebAccounts`, `WebAuthSessions`, 회원가입/로그인/로그아웃 API, 부트스트랩 관리자 계정 추가
- TASK-0011 (2026-04-15): `/admin` 화면과 계정 승인/비활성/세부 권한 제어 API/UI 추가
- TASK-0012 (2026-04-15): `AgentCoreConversations.owner_account_id` 기반 계정 소유권 도입, 기존 대화 관리자 귀속 처리
- TASK-0013 (2026-04-15): 표시 이름/역할/사용 목적 입력 제거, Keyword Management 제거, Domain/Strategy/Session/Calendar 등 불필요한 UI 제거
- TASK-0014 (2026-04-15): 세션 응답의 `local_llm_enabled`를 실제 연결 가능 여부 기준으로 보정
- TASK-0015 (2026-04-15): 외부 스크롤 제거 · 마케팅 패널 제거 · App-Shell 레이아웃 적용. 로그인: 단일 카드, 메인: Topbar+Sidebar+ChatPane 3단 고정 구조
- TASK-0016 (2026-04-15): feature AGENTS.md §8에 UI/UX 설계 원칙, 버튼 클래스 규칙, 브라우저 검증 정책, 금지사항 문서화. LEARNINGS.md에 3개 항목 추가
- TASK-0017 (2026-04-15): 사이드바 하단 프로필 트리거(ChatGPT 패턴) + 프로필 드로어(권한/활동정보/비밀번호 변경/로그아웃). state.busyConversations Set으로 병렬 대화 지원. Admin 콘솔에 검색/필터/페이지네이션 추가
- TASK-0018 (2026-04-15): 프로필 드로어를 계정/보안/API Vault 3탭으로 재구성. 기존 설정 드로어 제거 및 API Vault 흡수. 탑바 API Vault 버튼 제거. 로그아웃 시 드로어 미닫힘 버그·회원가입 폼 잔류 버그 수정.
- TASK-0019 (2026-04-15): `llm-shared` 외부 네트워크에 Ollama 기반 `local-llm-gateway`를 복구하고 `auto/edge/core/code` alias 모델을 준비해 API 키 없는 `model=auto` 실행 경로를 복원
- TASK-0020 (2026-04-15): 현재 repo 내부 Local LLM runtime을 제거하고, 외부 `/root/download/docker/local_llm` provider를 `LOCAL_LLM_API_BASE=http://local-llm-gateway:8080/v1` 계약으로 소비하도록 전환
- TASK-0021 (2026-04-15): UI 개편 과정에서 누락된 `execute_sql` step 결과셋 인라인 표시 복원. `result_summary.preview_table`을 HTML 테이블로 렌더링, SQL 쿼리+결과+CSV를 step 단위로 묶어 표시. 구형 메시지는 `meta.sql`/`meta.csv_paths` 폴백.
- TASK-0022 (2026-04-16): Progress Strip을 `<details>`/`<summary>` 드롭다운으로 전환. step 수가 늘어도 기본 1행 고정, 펼침 시 `max-height:40vh` 내부 스크롤. summary에 `n단계 · 최근 작업` 표시.
- TASK-0023 (2026-04-16): Planner 자율성 개선 — TOOL_DEFINITIONS 순서를 execute_sql 최우선으로 재배치, 각 도구 description에 사용 조건 명시, SYSTEM_PROMPT에 CRITICAL DIRECTIVE·IDEAL FLOW EXAMPLE·강화 ANTI-PATTERNS 추가. 휴리스틱 없이 프롬프트/도구 제시 순서만으로 불필요 탐색을 억제.
- TASK-0024 (2026-04-16): `WebRoles`/`WebPermissions`/`WebRolePermissions`/`WebAccountPermissionOverrides` 기반 RBAC로 cutover. role명 특수 처리 없이 permission + ownership 로만 권한 판정. 계정 soft delete, role CRUD, tri-state override, own/any 대화 권한, 제목 변경 API, Accounts/Roles 2영역 관리자 콘솔, `/api/clear_memory` 제거 완료.
- TASK-0025 (2026-04-16): assistant 말풍선 내 다중 execute_sql step을 수직 누적 없이 SQL Navigator(단일 패널 + `←/→/Home/End` 키보드 조작 + `쿼리 n/N · 대상 테이블` 상시 컨텍스트 + "전체 데이터 보기" CSV 로드)로 압축. 단일 step은 기존 블록 유지. 새 백엔드 API 없이 `/api/file`만 재사용. 브라우저 자동화로 탐색/키보드/단일 step 분기/CSV 파서 모두 검증 완료.
- TASK-0026 (2026-04-21): 한 줄 긴 SQL이 말풍선을 수평 확장하는 이슈 해소. 표시 전용 `formatSqlForDisplay()` 추가(주요 키워드 경계 줄바꿈, 복합 JOIN 보존, 문자열 리터럴 보호, 기존 여러 줄 쿼리 원형 유지). `.sql-block` CSS를 `pre-wrap` + `word-break` + `overflow-wrap`으로 변경, 컨테이너 `min-width:0` 안전망 추가.
- TASK-0027 (2026-04-21): 33개 RBAC 권한의 UX 정리. Profile 드로어의 `buildPermissionPills()`를 그룹별 `<section class="perm-section">` + 카운트 배지 구조로 재작성. Admin 콘솔 권한 그리드 `renderPermissionGrid()`를 `<details>` 기반 collapsible + summary 카운트 배지(허용/거부/상속 또는 N/M 선택) + 그룹별 배치 액션 버튼(모두 허용/거부/상속 또는 모두 선택/해제)으로 개편. `PERMISSION_GROUP_ORDER/LABELS` 상수와 `permissionGroupOf()` 헬퍼 추가. CSS: `.perm-sections`, `.perm-section*`, `.permission-group-head`, `.permission-group-counts`, `.permission-bulk-actions` 스타일 추가.
- TASK-0031 (2026-04-21): 관리 콘솔 내부 스크롤 정리. `.admin-workspace` 의 외부 스크롤(`overflow-y: auto`) 제거 → `overflow: hidden` + flex column 으로 전환하고, `.admin-pane.is-active` / `.admin-list-detail` 가 남은 공간을 `flex: 1 1 auto + min-height: 0` 으로 채우도록 변경. `.admin-list-col` / `.admin-detail-col` 각각 자체 내부 스크롤 소유 — list 컬럼은 toolbar/list-head(shrink 고정) + `.admin-list`(`flex: 1; overflow-y: auto`, 기존 `max-height: calc(100vh-320px)` 제거) + 페이지네이션/일괄 액션(`flex-shrink: 0; border-top`) 구조. detail 컬럼은 `overflow-y: auto` + `.admin-detail-actions { position: sticky; bottom: -18px; margin: 4px -22px -18px; padding: 12px 22px; background: var(--surface); border-top }` 로 저장/취소/삭제 버튼을 detail 높이와 무관하게 상시 하단 노출. 대시보드 pane 은 `overflow-y: auto` 단일 스크롤로 별도 처리. 검증: detailColScroll=1866, listScroll=807 각각 내부 스크롤 활성, docScrollDelta=0(외부 스크롤 0), paginationVisible/actionsVisible=true, 양 컬럼 끝까지 스크롤해도 두 하단 요소 모두 뷰포트 내 유지. JS/HTML 변경 없이 CSS 만으로 해결.
- TASK-0030 (2026-04-21): assistant 말풍선 고정 폭 + `<details>` 펼침 시 내부 스크롤/스크롤 앵커. `.message`의 role별 max-width 분기(user 72% / assistant `max-width:none` + `margin-right:48px` + `align-self:stretch`)로 assistant 는 채팅 pane 전폭에 가깝게, user 는 좁은 우측 정렬로 분리. `.message-details-body`에 `max-height:min(60vh,520px); overflow:auto; overscroll-behavior:contain` 캡으로 펼친 본문을 말풍선 내부에서 수직 스크롤 처리. `.result-table-wrap` 기본 `max-height:320px`, `.sql-block` `max-height:240px` 로 결과 테이블/초장문 SQL 도 내부 스크롤로 격리. `app.js` `renderMessageDetails()`의 `<summary>` 클릭 핸들러에 `messageLogEl` 기준 `summary.getBoundingClientRect().top` 측정 → 2-frame `requestAnimationFrame` 후 delta 만큼 `messageLogEl.scrollTop` 보정하는 scroll anchor 추가. 브라우저 검증: summaryDelta=0/scrollDelta=0, Navigator 이동 시 bubble width 705→705 불변, bodyMaxH=432px(60vh), details body overflow-y=auto 확인.
- TASK-0029 (2026-04-21): 관리 콘솔 재구조화. `admin.html` 을 `topbar + sidebar(tabs) + workspace + commit-bar` 4영역 grid 로 재작성(탭: 대시보드/계정/역할). `admin.js` 전면 재작성 — `adminState.pending = { accounts, roles, newRoles }` Map 기반 pending changes 모델 + 서버 값과 일치하면 auto-drop 로직(`setAccountPending`/`setRolePending`). 계정/역할 편집은 form submit 없이 input/select change 이벤트에서 pending 에 적재만 하고, 하단 commit bar 의 "모두 적용" 클릭 시 전체 pending entry 를 순차 PATCH/DELETE/POST 후 1회만 `loadAdminData()`. 리스트-디테일 레이아웃 + 탭별 scoped search + 리스트 row 체크박스 기반 일괄 작업(활성/비활성/삭제 pending 반영). 신규 역할은 tempId(`new:N`)로 pending.newRoles 에 넣고 POST 로 일괄 커밋. `styles.css` 에 `.admin-shell` grid/`.admin-sidebar`/`.admin-tab`/`.admin-list-detail`/`.admin-list-row`/`.admin-detail-*`/`.admin-commit-bar`(.has-pending 노란 강조) 스타일 추가. 사용자 테스트에서 확인된 "여러 계정 동시 수정 시 특정 계정 저장하면 타 계정 변경 소실" 버그는 pending 모델 + 단일 commit 경로로 근본 해소.
- TASK-0033 (2026-04-21): 결과셋 말풍선의 이중 스크롤 제거 + RowCount + Excel-like freeze. `styles.css` 의 `.message-details-body` 에서 `max-height: min(60vh,520px); overflow: auto; overscroll-behavior: contain; padding-right: 4px` 일괄 제거 → 말풍선 body 는 자연스럽게 자라고 세로 스크롤은 `.messages` 하나로 통일. `.result-table-wrap` 은 `max-height: 320px → min(60vh, 460px)` + `overscroll-behavior: contain` 제거(= auto 로 복원 → 경계에서 `.messages` 로 휠 전파). `.sql-block` 도 `max-height: 240px → min(40vh, 320px)` + overscroll 제거. `.result-table` 을 `border-collapse: separate; border-spacing: 0` 으로 전환하고 border 는 `box-shadow: inset` 으로 대체(sticky 셀에서 border 누락 방지). `.result-table thead th { position: sticky; top: 0; z-index: 2 }` 로 헤더 freeze, `.result-table th.col-rownum, td.col-rownum { position: sticky; left: 0; z-index: 1 }` 로 첫 열(#) freeze, 코너 `thead th.col-rownum { z-index: 3 }` 로 교차점 최상위. `app.js` 에 `appendRowNumCell(tr, tag, value)` 헬퍼 추가, `buildResultTable()` thead/tbody 렌더 시 `<th class="col-rownum">#</th>` + `<td class="col-rownum">{i+1}</td>` 항상 prepend. `loadFullCsvIntoTable()` 도 동일 패턴으로 재구성 → "전체 데이터 보기" 이후에도 #/freeze 유지. 검증: 기존 대화의 33행 결과 테이블에서 `theadThPosition='sticky'`, `col-rownum td position='sticky'`, corner `zIndex=3`, wrap `max-height=432px`, `overscroll-behavior='auto'`, `.message-details-body { max-height: none; overflow: visible }`, `hasInnerDetailScroll=false`, 수직 스크롤 200px 시 각 th 개별 top 변동 없음(`firstTh_delta=0`), 가로 스크롤 60px 시 `col-rownum` 좌측 고정(`rnStayed=true`, `dataMoved=true`). 스크린샷 `artifacts/shared/out/browser/task0033_01_result_tables.png` · `task0033_02_sticky_header_mid_scroll.png`.
- TASK-0032 (2026-04-21): 권한 안내 UX 개편. `app.js` 에 `PERMISSION_DESCRIPTIONS`(33개 권한 서술 문장 맵), `describePermission()`, `requiredPermissionsFor(action, conversation)`(any/own 이원화된 권한 자동 확장), `hasAnyPermission()`, `showPermissionDeniedToast()`(필요 권한 코드 + 서술 + 관리자 요청 문구), `markAccessBlocked(btn, action, conversation)`(aria-disabled + is-access-blocked + 서술 title) 추가. `buildPermissionPills()` 의 `item.title = code` 를 `서술 문장\n(code)` 로 교체. `renderComposer()` 에서 `cancel/finalize/rename/delete` 버튼을 context 신호(processing / activeConversationId) 로만 hidden 토글하고, 권한 부재는 `markAccessBlocked()` 로 별도 표현. `sendBtn`/`newConversationBtn` 도 native disabled 대신 aria-disabled 사용해 클릭이 통과하도록 전환. 각 action 함수 (`createConversation`, `renameCurrentConversation`, `deleteConversation`, `cancelCurrentRun`, `finalizeCurrentRun`, `sendPrompt`) 의 silent `return` 을 `showPermissionDeniedToast()` 호출로 교체. `renderAccessNotice()` / `renderComposer()` 안내 문구에 `conversation.ask` 코드 명시. `styles.css` 에 `.is-access-blocked { opacity: .42; cursor: help; color: var(--text-muted) }` 추가. 검증 (admin / pending 계정): pill tooltip=한국어 서술 문장+`(code)`, pending 계정 composerHint=`현재 계정에는 대화 요청 실행 권한(\`conversation.ask\`)이 없습니다...`, sendBtn/newConvBtn/renameBtn/deleteBtn 모두 `is-access-blocked` + aria-disabled + 서술 title, 클릭 시 `'대화 삭제' 권한이 필요합니다. 관리자에게 \`conversation.delete.any\` 권한 부여를 요청하세요. — 타 사용자가 소유한 대화까지 삭제할 수 있는 권한입니다.` 형식 토스트 노출. 스크린샷 `artifacts/shared/out/browser/task0032_{01,02,03}_*.png` 증빙.
- TASK-0028 (2026-04-21): agent-core 문서 보강. `docs/INSIGHTS.md` 신규 작성(워커 루프/사이클/fingerprint/인라인 fallback/KV 스키마/환경변수 14종/해석 가이드/헬스 체크 SQL + 2026-04-21 실제 런타임 출력). `docs/AGENT_CORE_INTERNALS.md` 신규 작성(run_agent 흐름도, SYSTEM_PROMPT 7블록 구조, TOOL_DEFINITIONS 우선순위 근거, Knowledge Injection, Step 예산/타임아웃/cancel/finalize 신호, CSV 2단계(preview 50행 + 전체 파일), Planner insight fast path, 3-state 대화 맥락). `FUNCTION.md` Main Flow/Dependencies/Observability 확장(MEMORY_DB 스키마 표, insight_worker 로그 관측성). 코드 변경 없음.

## 6. Next Action
- 신규 권한/계정 정책 변경이 필요하면 별도 TASK로 분리한다

## 7. Completion Checklist
- [x] Web UI 코드 이관이 완료되었다
- [x] 루트 실행 경로가 새 구조를 참조한다
- [x] 문서가 현재 구조를 반영한다
- [x] 계정/비밀번호 기반 인증이 동작한다
- [x] pending/read-only 흐름이 동작한다
- [x] 관리자 승인 및 세부 권한 조정이 가능하다
- [x] 대화 소유권이 계정 기준으로 분리되었다
- [x] 불필요한 상단 상태 정보와 Keyword Management가 제거되었다
- [x] 브라우저 기반 렌더링 증빙이 남아 있다
- [x] 상용 AI 앱 수준의 App-Shell 레이아웃이 적용되었다 (외부 스크롤 없음)
- [x] UI/UX 정책 지침이 feature AGENTS.md §8에 문서화되었다
- [x] 사이드바 하단 프로필 버튼이 ChatGPT/Claude 패턴으로 배치되었다
- [x] 프로필 드로어가 계정/보안/API Vault 탭으로 구조화되어 있다
- [x] 병렬 대화가 다른 대화의 요청 처리 중에도 차단되지 않는다
- [x] Admin 콘솔에 검색·역할 필터·페이지네이션이 동작한다
- [x] 계정별 설정(API Vault)이 탑바가 아닌 프로필 드로어 안에 배치되어 있다
- [x] 로그아웃 시 열린 드로어가 닫히고 인증 폼이 초기화된다
- [x] 현재 repo가 Local LLM runtime을 직접 소유하지 않는다
- [x] execute_sql 단계의 쿼리 결과가 인라인 HTML 테이블로 표시된다
- [x] SQL 쿼리 블록과 결과 테이블, CSV 링크가 step 단위로 묶여 표시된다
- [x] Progress Strip이 `<details>` 드롭다운으로 동작하며 step 증가 시 채팅 영역이 축소되지 않는다
- [x] Planner가 execute_sql을 우선 시도하도록 도구 순서와 프롬프트가 구성되어 있다
- [x] 계정이 `Role 기본 권한 + account override` 구조로 계산된다
- [x] `pending/operator/admin` 문자열 비교 없이 permission + ownership 만으로 권한이 판정된다
- [x] 관리 콘솔에서 role 생성/수정/삭제와 기본 가입 역할 변경이 가능하다
- [x] 관리 콘솔에서 계정 role 부여와 tri-state override 편집이 가능하다
- [x] 계정 soft delete 후 로그인 차단과 세션 폐기가 동작한다
- [x] 대화 조회/제목 변경/삭제/중단/즉시답변이 own/any 권한으로 분기된다
- [x] `/api/clear_memory` 및 legacy `Can*` 계약이 런타임에서 제거되었다
- [x] 다중 execute_sql step 말풍선이 Navigator로 압축되어 수직 누적되지 않는다
- [x] Navigator에서 `←/→/Home/End` 키보드로 step 탐색이 가능하다
- [x] 현재 선택된 쿼리의 인덱스와 대상 테이블이 Navigator 헤더에 상시 노출된다
- [x] "전체 데이터 보기" 로 preview 이상의 행을 CSV 기반으로 로드할 수 있다
- [x] 한 줄 긴 SQL 쿼리가 키워드 경계에서 줄바꿈되어 말풍선이 수평 확장되지 않는다
- [x] 이미 여러 줄로 포맷된 쿼리와 따옴표 내 키워드가 원형 유지된다
- [x] Profile 드로어의 권한 현황이 console/account/role/conversation/misc 그룹 단위 섹션으로 묶여 표시된다
- [x] Admin 콘솔의 계정/역할 권한 편집이 `<details>` collapsible 그룹 구조로 동작하고 summary에 카운트 배지가 표시된다
- [x] 각 권한 그룹에 배치 액션(모두 허용/거부/상속 또는 모두 선택/해제) 버튼이 동작한다
- [x] Insight 시스템(백그라운드 스키마/테이블 분석 워커)의 구조와 헬스 체크 방법이 `docs/INSIGHTS.md`에 명시되어 있다
- [x] agent-core 내부 동작(SYSTEM_PROMPT 구조, TOOL_DEFINITIONS 우선순위, Knowledge Injection, Step 예산, CSV 2단계, Planner fast path)이 `docs/AGENT_CORE_INTERNALS.md`에 명시되어 있다
- [x] 관리 콘솔이 대시보드/계정/역할 탭 기반 네비게이션으로 분리되어 있다
- [x] 계정/역할 편집이 pending changes 모델로 관리되며, 하단 commit bar 의 "모두 적용" 시에만 서버에 반영된다
- [x] 여러 계정을 동시에 편집해도 각 편집 내용이 유지되며 단일 계정 저장으로 소실되지 않는다
- [x] assistant 말풍선이 기본적으로 채팅 pane 의 우측 약간(48px)만 남기고 넓게 고정되며, `<details>` 펼침/접힘이나 결과셋 구성 변화에 말풍선 폭이 흔들리지 않는다
- [x] `<details>` 펼침 시 내부 SQL/테이블/Navigator 가 말풍선 내부 수직 스크롤로 격리되어 채팅 로그 스크롤 위치와 전체 레이아웃이 변형되지 않는다
- [x] `<summary>` 클릭 시 해당 라인이 뷰포트 내 동일 y좌표를 유지(scroll anchor)
- [x] 관리 콘솔이 외부 페이지 스크롤 없이 viewport 에 고정되며, 리스트 컬럼과 디테일 컬럼이 각각 내부 스크롤을 가진다
- [x] 리스트 하단 페이지네이션/일괄 액션 바와 디테일 하단 저장/삭제 액션 바가 컬럼 스크롤과 무관하게 항상 뷰포트 내에 노출된다
- [x] 리스트 row 체크박스 + 일괄 작업(활성/비활성/삭제 pending)이 동작한다
- [x] 계정 탭/역할 탭 각각이 독립된 scoped search 를 가진다
- [x] Profile > 계정 탭 권한 pill 에 마우스를 올리면 한국어 서술 문장과 권한 코드가 툴팁으로 표시된다
- [x] 권한이 부족한 계정에서 차단된 동작을 시도(클릭/단축키)하면 필요 권한 코드 + 서술 문장 + 관리자 요청 문구가 토스트로 노출된다
- [x] cancel/finalize/rename/delete 버튼은 context 상 의미있을 때는 항상 보이고, 권한이 없을 때는 `is-access-blocked` 로 표시되며 클릭은 토스트로 안내된다
- [x] assistant 말풍선의 `실행 단계 및 쿼리 결과 보기` 내부에 세로 스크롤바가 중첩되지 않는다 (본문은 콘텐츠 크기만큼 확장되고 세로 스크롤은 `.messages` 하나)
- [x] 쿼리 결과 테이블에 첫 컬럼 `#` (RowCount) 이 자동 삽입되어 행 번호가 1부터 표시된다
- [x] 결과 테이블 내부 세로 스크롤 시 헤더 행이 상단 고정, 가로 스크롤 시 `#` 컬럼이 좌측 고정된다
- [x] 결과 테이블 내부 스크롤이 경계에 닿으면 채팅 로그(`.messages`) 로 휠이 전파된다 (`overscroll-behavior` 제거)
- [x] "전체 데이터 보기" 로 CSV 로드 후에도 RowCount 와 sticky freeze 가 유지된다
- [ ] TASK-0034: 복잡 QA 성능 테스트가 local LLM 5 (직렬) + 상용 API gpt-5.4-mini 5 (병렬) 총 10 대화로 실행되어 turn-by-turn 로그가 JSON 으로 저장된다
- [ ] TASK-0034: 5 개 복잡 질문에 대해 사람 truth 쿼리와 assistant 최종 답변이 비교 가능한 diff 형태로 `TASK-0034-REPORT.md` 에 기록된다
- [ ] TASK-0034: 관찰된 개선 포인트가 `docs/LEARNINGS.md` 에 신규 LRN 항목으로 추가된다
- [x] TASK-0040: `_extract_sql_schema_refs` 가 `WHERE bb.BattleType = 'X'` 등 alias.column 토큰에서 schema 를 추출하지 않는다 (FROM/JOIN 구간의 테이블 리스트로 범위 제한)
- [x] TASK-0040: `FROM dblog.t bb JOIN dblog.u be ON be.a = bb.a` 형식 SQL 이 Product whitelist=`{dbauth,dbgame,dblog}` 상태에서 정상 통과한다
- [x] TASK-0040: 비허용 스키마(`FROM dbstat.foo`) 는 여전히 차단된다 (15 테스트 케이스 통과)
- [x] TASK-0041: `GET /api/ask_status?conversation_id=...` 이 `{is_processing, status, run_id, step_count, duration_ms, has_answer, answer_preview}` 스냅샷을 반환한다
- [x] TASK-0041: `GET /api/ask_result?conversation_id=...&run_id=...&wait=N(<=60)` 이 terminal 도달 시 `{status, run_id, assistant.{message_id,content,meta,steps_count}}` 를 반환하고, 시간 초과 시 `{timeout:true}` 를 반환한다
- [x] TASK-0041: 브라우저에서 `/api/ask` 요청이 끊겨도 `is_processing=true` 인 경우 `[계속 기다리기/즉시 답변/요청 취소]` 다이얼로그가 노출되고 선택한 동작 이후 최종 메시지가 UI 에 주입된다
- [x] TASK-0041: `task0034_runner.py` 의 `httpx.ReadTimeout` 분기가 `/api/ask_status` + `/api/ask_result` long-poll 로 attach 해 최종 응답을 해당 턴에 기록한다
- [x] TASK-0037: `/api/progress` 폴링이 `setInterval` 고정 주기가 아니라 순번 기반 `setTimeout` 체인으로 동작하고 in-flight 요청이 1 을 넘지 않는다
- [x] TASK-0037: 대화 전환/로그아웃/새 대화 생성 시 AbortController 로 진행 중인 `/api/progress` 요청이 즉시 취소된다
- [x] TASK-0037: 탭 전환(`document.hidden`) 시 폴링 주기가 최소 10초로 감속되고, 연속 오류 3회 이상이면 재스케줄링되지 않는다
- [x] TASK-0037: 서버 `/api/progress` 가 `client_run_id` 불일치 시 `after_step` 을 0 으로 리셋해 새 run 의 모든 step 을 되돌려준다
- [x] TASK-0037: 폴링 패턴 학습 내용이 `docs/LEARNINGS.md` 의 LRN 항목(LRN-20260422-0011) 로 기록된다
- [x] TASK-0044: `SEED_ROLE_DEFINITIONS` 에 RoleKey=`sales` / Name=`사업팀` entry 가 있고, 부트스트랩 후 `WebRoles` 에 해당 row + `conversation.create` / `conversation.ask` 등 9 개 권한이 `WebRolePermissions` 로 연결된다 (admin 콘솔 `/api/admin/roles` 조회로 확인)
- [x] TASK-0044: `SEED_ROLE_SYSTEM_PROMPTS` + `_ensure_seed_role_system_prompts(conn)` 이 sales role 에 대해 `WebSystemPrompts(Scope='role', RoleId=<sales>, ProductId=NULL)` prompt 1 row 를 1 회만 upsert 하고, 이미 존재하면 덮어쓰지 않는다 (관리 콘솔 수정 존중)
- [x] TASK-0044: sales role prompt 본문이 "단순 조회 → 문장 응답 / 집계 → 결과셋 표 응답 / ad-hoc 심층 분석 요청 → DBA 팀 이관 안내 후 대화 종료 / DB 쓰기 쿼리(INSERT/UPDATE/DELETE/DDL) 거부" 4 지침을 포함한다
- [x] TASK-0044: `modules/config.py` 가 `REPLICA_DB_HOST` / `REPLICA_DB_PORT` / `REPLICA_DB_USER` / `REPLICA_DB_PASSWORD` / `REPLICA_DB_ENABLED` 5 개 심볼을 export 하고, `.env.example` 에 4 개 placeholder 가 등록되어 있다 (실제 접속 정보는 commit 금지)
- [x] TASK-0044: `modules/db.py::connect()` 이 `REPLICA_DB_HOST` 가 설정되어 있고 요청 `database` 가 `MEMORY_DB` 가 아닐 때 복제 인스턴스의 host/port/user/password 로 라우팅하고, 그 외에는 primary (DB_HOST/...) 로 라우팅한다
- [x] TASK-0044: `REPLICA_DB_HOST` 가 비어있는 기존 배포에서 동작이 변하지 않는다 (`connect(database=None)` / `connect(database=MEMORY_DB)` / `connect(database="dbgame")` 모두 primary 접속)
- [x] TASK-0073: `WebAuditEvents` 테이블 (14 columns + 5 indexes) 이 slow/fast path 모두에서 idempotent 생성 (`_ensure_web_audit_events_schema`, Phase A0)
- [x] TASK-0073: `record_audit_event(conn, *, actor, action, resource_type, resource_id, change_json, masked_fields, target_account_id)` dispatcher 가 동작 + `AGENT_AUDIT_ENABLED=0` 시 silent no-op (Phase A1)
- [x] TASK-0073: prod (`AGENT_MODE != dev/test`) 에서 `AGENT_AUDIT_ENABLED=1` 아닐 시 module load 시점 `sys.exit(1)` + stderr `[FATAL]` (Phase A1, Codex C5)
- [x] TASK-0073: `bin/verify-completion.sh check_11_audit_dispatcher` 가 `record_audit_event` / `AGENT_AUDIT_ENABLED` / `_enforce_audit_prod_gate` 3 symbol 강제 (Phase A1, Eng E7 SPOF guard)
- [x] TASK-0073: `WebAccountActivity` (TASK-0072) → `WebAuditEvents` migration helper idempotent (`RequestId='account-activity:<id>'` marker, Phase A2)
- [x] TASK-0073: `_log_search_activity()` 의 signature transparent + dual write (legacy + new dispatcher mirror, Phase A2)
- [x] TASK-0073: `PERMISSION_DEFINITIONS` 에 `audit.read.own` / `audit.read.any` / `audit.export` / `audit.purge` 4 코드 추가 + permission group `audit` (Phase A3)
- [x] TASK-0073: admin/operator/sales/dba/pending 5 role 의 audit 권한 catchup loop (Phase A3, Eng E9 dba 보강)
- [x] TASK-0073: 5 audit read endpoint 동작 (`GET /api/admin/audits` + detail + export.csv + actors facet + resources facet) — `.own` SQL filter Actor OR Target (Phase A4, Eng E1 B)
- [x] TASK-0073: `POST /api/admin/audits/purge` chunked PK loop + idempotency_key + 30s deadline + start/complete self-audit row (Phase A4, Eng E8)
- [x] TASK-0073: `build_audit_change_json(action, ...)` 16 ActionCode builder allowlist + unknown action raise (Phase A5, Codex C6)
- [x] TASK-0073: admin 11 mutation endpoint Same tx audit hook (PATCH/DELETE accounts + password-reset + roles CRUD + products CRUD + databases.update + system-prompts) + audit 실패 = caller rollback + 500 (Phase A5)
- [x] TASK-0073: user 5 endpoint fail-open audit (`/api/ask`, share create / revoke / public view (anonymous) / fork) + audit 실패 = stderr only, main flow 진행 (Phase A6)
- [x] TASK-0073: anonymous share view audit (`ActorType="anonymous"` + ActorAccountId NULL + token_prefix 8 char, Phase A6, Eng E4)
- [x] TASK-0073: `tests/test_audit_dispatcher.py` 7 시나리오 + `test_audit_rbac.py` 10 시나리오 + `test_audit_migration.py` 3 시나리오 신설 (Phase B). 실 실행은 컨테이너 가동 후 사용자 위임
- [x] TASK-0073: Frontend admin "감사 로그" 탭 + filter row 7 항목 + list-detail + CSV export gated + admin.js renderAuditList/Detail + HTML escape + cache-bust `v=20260519-audit-tab` (Phase C)
- [x] TASK-0073: app.js + admin.js `PERMISSION_GROUP_ORDER` 에 'audit' 그룹 추가 + ADMIN/WORK_SCREEN_PERMISSION_SECTIONS manage section 합류 (Phase C)
- [x] TASK-0073: `docs/SECURITY.md §9` (Audit subsystem 정책 + Sensitive field catalog source-of-truth) + `docs/DECISIONS.md ADR-0019` + `docs/ARCHITECTURE.md §4·§6` + `docs/CONVENTIONS.md §10.6` audit group + `docs/STATUS.md` feature-0003 row + REPORT.md §1 + TEST.md §2.1 (Phase D)
- [x] TASK-0073: `make web` 재배포 후 audit endpoint 8 시나리오 smoke 검증 PASS (Phase E 본 cycle 2026-05-20). admin.role.create → audit row delta=1 / ChangeJson allowlist 정합 / detail / export.csv (Content-Type text/csv + Content-Disposition) / actors facet (bootstrap_admin) / resources facet (conversation + role) / purge dry_run / anonymous share view ActorType='anonymous' (token_prefix `Wp45TbFK`, view_count_after=2, masked share.token_full) 모두 PASS. routing 회귀 1 건 (`/{event_id}` 가 정적 sibling 가로채기) 발견 + 동일 cycle hotfix (CHG-20260520-0001).
- [x] TASK-0073: WebAccountActivity → WebAuditEvents migration 검증 PASS — `SELECT COUNT(*) FROM WebAuditEvents WHERE RequestId LIKE 'account-activity:%'` = 68 row (legacy 전부 transform, idempotent marker).
- [x] TASK-0073: `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` 환경에서 컨테이너 시작 시 process 종료 + stderr `[FATAL]` 검증 — **TASK-0092 (REQ-20260520-0007, Minor §12.3) 에서 완료**. 7 vector matrix (V1~V7) 의 V1-V3 fail-closed scenario 가 정확히 본 acceptance 충족. `docker run --entrypoint python --no-deps` + `import web.app` + stderr `[FATAL]` 3 substring 검증 PASS. 본 closure 는 TASK-0099 (audit followup backlog tracker hygiene) cycle 에서 수행 (2026-05-22).
- [ ] TASK-0044: 사업팀 pilot 계정(placeholder `<< pilot_username_1..N >>`) 이 admin 콘솔에서 발급된다 — 코드 auto-create 없음, 발급 절차는 본 TASK 기술부 마지막 runbook 문단 참조
- [ ] TASK-0044: 사업팀 pilot 계정으로 로그인해 단순 조회 prompt(예: "대표 아이템 X 가 몬스터 Y 에 연결돼 있나요?") 에 문장형 응답을 받는다
- [ ] TASK-0044: 사업팀 pilot 계정으로 집계 prompt(예: "최근 7 일 레벨별 유저 수") 에 결과셋 표 응답을 받는다
- [ ] TASK-0044: 사업팀 pilot 계정으로 ad-hoc 분석 prompt(예: "유저가 왜 이탈하는지 분석해줘") 에 "DBA 팀으로 요청 이관이 필요합니다" 안내가 응답되고 대화가 그 턴에서 종료된다

### TASK-0044 pilot onboarding runbook (2026-04-23)
사업팀 pilot 발급·서빙을 위한 관리자 운용 절차. 본 TASK 의 코드 변경은 infra 만 제공하며, 실제 account/Product 매핑은 admin 이 수동 수행한다.

1. **사업팀 pilot 계정 발급** (`.env.example` 의 `WEB_PILOT_SALES_USERNAMES` placeholder 참조)
   1. admin 계정으로 로그인 → 관리 콘솔 `계정 (Accounts)` 탭 → `신규 계정` 으로 3~5 명 발급.
   2. 각 계정의 Role 드롭다운에서 `사업팀 (sales)` 을 선택하고 commit bar 의 `모두 적용` 을 누른다.
   3. 초기 비밀번호는 pilot 에게 안전한 채널(사내 1:1 메신저 등) 로 공유하고 본인이 첫 로그인 시 교체하도록 안내한다.

2. **사업팀 전용 Product whitelist 구성 (권장안 2 가지 중 조직 정책에 맞춰 선택)**
   - **옵션 A — KR Product 에서 `dbauth` 를 제외**: 관리 콘솔 `상품 (Products)` 탭 → KR 선택 → 접근 DB chip 에서 `dbauth` 제거 → 저장. 주의: DBA 운영 계정도 KR 을 쓰면 영향. DBA 가 `dbauth` 직접 조회 필요 시 별도 Product 로 분리해야 한다.
   - **옵션 B — 사업팀 전용 Product `KR-Sales` 신규 생성** (권장): 관리 콘솔 `상품 (Products)` 탭 → `신규 상품` 으로 ProductKey=`KR-Sales` / Name=`Korea Sales` 를 생성 → 접근 DB chip 을 `dbgame,dblog` 로 지정. 사업팀 pilot 은 새 대화 시 이 Product 를 명시적으로 선택하거나, `/api/new_conversation` body 의 `product_id` 로 기본값을 지정한다.

3. **복제 DB 접속 정보 등록**
   1. 복제 인스턴스가 이미 가동 중이면 `.env` 에 `REPLICA_DB_HOST=<host>` / `REPLICA_DB_PORT=<port>` / `REPLICA_DB_USER=<user>` / `REPLICA_DB_PASSWORD=<password>` 를 기입 (quote 는 mysql.connector 인자이므로 bash-safe 처리 필요).
   2. `docker compose up -d --force-recreate agent web insight-worker` 로 재기동하면 data-plane 쿼리가 복제로 라우팅된다. memory DB 는 계속 primary.
   3. 수동 sanity check: `docker compose exec agent python -c "from modules.db import connect; c=connect(database='dbgame'); cur=c.cursor(); cur.execute('SELECT 1'); print(cur.fetchall())"` → `[(1,)]` 출력 + 필요시 `mysql -h $REPLICA_DB_HOST -P $REPLICA_DB_PORT -u $REPLICA_DB_USER -p -e 'SELECT 1'` 으로 직접 접속.
   4. 복제 인스턴스가 아직 없으면 3.1~3.3 은 후속 작업이며, `.env` 의 REPLICA_DB_* 를 비워 두면 기존 primary 경로가 그대로 동작한다 (사업팀 pilot 테스트 자체는 복제 없이 가능).

4. **사업팀 prompt 튜닝 (선택)**: 관리 콘솔 `역할 (Roles)` 탭 → `사업팀` 선택 → Role scope prompt 편집기 → Product 드롭다운(`(전 Product 공통)` 또는 특정 Product) 선택 후 초안을 수정. 저장 시 `WebSystemPrompts` 의 해당 scope row 가 업데이트되고 다음 `/api/ask` 부터 새 가이던스가 즉시 적용된다.

### Phase Composer Model Selector (feature-0008, 2026-05-22)
- [x] DOM: composer-box 의 attach-btn → `+` (composer-actions-btn) + primary
      popup (#composerActionsMenu) + secondary popup (#composerModelMenu).
- [x] JS: state.modelCatalog + state.selectedModel 신규. dead vault code 161
      줄 일괄 정리. `+` dropdown handlers (binding / open/close / model item
      render / sendPrompt fallback chain).
- [x] CSS: .composer-actions-btn / .composer-actions-menu / .composer-actions-item
      / .composer-model-menu / .composer-model-item* + 반응형 fallback.
- [x] cache-bust: v=20260522-composer-model-selector.

### AR-M5-impl web hotfix — PG cutover MySQL 잔존 쿼리 차단 (2026-05-27)
- [x] `_last_step_at_for_run()`: `AGENT_RUNTIME_READ_BACKEND=postgres` 시 `agent_runtime.steps` 쿼리로 전환 — MySQL `AgentMemorySteps` 직접 의존 제거 (CHG-20260527-0001).

### TASK-0121 — AR-M5 PG cutover 잔존 MySQL 쿼리 차단 (2026-05-27)
- [x] `_load_latest_assistant_message`: PG `agent_runtime.messages` 경로 추가 + MySQL fallback 유지
- [x] commit + push + main ff-merge

### TASK-0122 — 외부 LLM 수신 동의 UI·권한·로직 제거 (2026-05-28)
- [x] REQ-20260528-0122 (**Minor** §12.3 — 사용자 프로필 > 보안 및 계정 > 외부 LLM 수신 동의 섹션 전면 제거. 서비스 사용 = 묵시 동의로 간주). `index.html` `profileConsentSection` DOM 제거. `app.js` `_CONSENT_PROVIDERS` / `_CONSENT_GROUPS` / `_consentRowsCache` / `_isConsentGroupGranted` / `_loadConsentRows` / `_renderConsentSectionMarkup` / `_renderConsentSection` / `_handleConsentToggle` / `_bindConsentSectionEvents` 함수·변수 전체 제거 + `openProfile` 내 렌더링 호출 + 이벤트 바인딩 제거. `styles.css` `.consent-providers` / `.consent-provider-block` 등 consent CSS 블록 제거. `app.py` `_ensure_web_account_consents_schema` 함수·호출 2곳 제거 / `_has_active_consent` 함수 제거 / `_prepare_vision_inline_images` D11 consent gate 분기 + 409 응답 제거 (vision pre-fetch D13 로직 보존, 반환 4-tuple → 3-tuple) / `GET|POST /api/account/consents`, `DELETE /api/account/consents/{id}` 3 엔드포인트 제거 / `attachment.consent.grant|revoke` audit 핸들러 제거 / `_model_to_consent_provider` → `_model_to_llm_provider` 이름 변경 (audit 용도 유지). py_compile + node --check PASS. DB schema (`WebAccountConsents`) 는 기존 데이터 보존 목적으로 DROP 안 함 — 신규 row 추가만 없어지는 것.
- [x] commit + push + main merge

### TASK-0123 — UX 2차 보완 7개 항목 구현 (2026-05-28)
- [x] REQ-20260528-0123 (**Minor** §12.3 — frontend-only UX 보완, backend / RBAC / DB schema / endpoint contract 무변경). 7개 항목 일괄 구현: **(1) 입력창 높이 일치** — `.composer-box` padding `9px→7px` 로 축소 (프로필 버튼 48px = composer textarea 34px + padding 7×2, 정렬 맞춤). **(2) 파일 즉시 업로드 + ingest 병렬** — `_uploadComposerAttachment()` lazy 분기 완전 재작성: staged 방식 대신 파일 선택 즉시 `/api/new_conversation` 호출로 cid 발급 + 업로드 실행 + `state.composerAttachments.lazyConvCreating` 경쟁 방지 플래그 추가. 대화 목록에 임시 "(파일 첨부 중)" 항목 추가 + 렌더 갱신. **(3) 말풍선 첨부파일 표시** — 업로드 응답의 `signed_url` 을 bucket item 에 보존 + `_sendAttachmentSnapshot` 에 `signed_url` 포함 + `refreshWorkspace()` 후 `lastUserMsg._attachments = _sendAttachmentSnapshot` 재주입 (loadHistory 로 attachments 필드 소실 방지). **(4) 첨부파일 다운로드** — 말풍선 attach chip 에 `signed_url` 존재 시 `has-download` class + click 핸들러 (presigned GET 다운로드). styles.css 에 `.attach-chip-dl` + hover 효과 추가. **(5) 공유뷰 CSV 다운로드** — `share.js` 에 `downloadRowsAsCsv()` helper (BOM UTF-8, RFC4180 escape) + `renderAssistantDetails()` 내 SQL 결과표 하단에 "CSV 다운로드" 버튼 추가. `share.css` 에 `.share-csv-download-btn` 스타일. (공유뷰 file attachment 는 backend 가 permission-gated 로 숨김 — SQL 결과 CSV 로 대체). **(6) LLM step/thinking 표시** — `renderProgress()` 내 `progressCardEl.open = true` + `renderPendingAssistantBubble()` 의 `<details>` step 항목 `detailsEl.open = true` (step 도착 즉시 자동 펼침). **(7) 첫 대화 상태 dot 갱신** — `sendPrompt()` 의 lazy-create 성공 path 에서 `startProgressPolling` 직전 `state.conversations` 에 신규 conv 최소 항목 추가 + `renderConversationList()` 호출 → polling 첫 tick 에서 DOM 요소가 존재해 dot 갱신 가능. node --check PASS. worktree `ux-compact-redesign` (branch `ai/root/ux-compact-redesign`), commit `095f9b1`.
- [x] docker cp 배포 (repo-web-1:/app/web/static/ — app.js, share.js, share.css, styles.css)

### TASK-0167 — 대화 분기·공유 cutover 회귀 수정 (2026-06-09)
- [x] **Major §12.3** — fork/share/duplicate/public-share-view 가 2026-05-27 MySQL→PG cutover 후 DROP 된 `AgentCoreConversations`/`AgentMemoryMessages`/`AgentMemoryKv` 를 raw MySQL 로 조회해 HTTP 500 (`Table 'agent_memory.agentmemorymessages' doesn't exist`). `/api/history`(`_list_conversations_pg`) 등 정상 endpoint 와 동일하게 `AGENT_RUNTIME_READ_BACKEND=postgres` 분기 + `_pg_connect()` 로 PG(`agent_runtime.*`) 라우팅. (CHG-20260609-FORK-SHARE-PG-CUTOVER) — CHG-20260527-ASK-STATUS-PG 의 형제 회귀.
- [x] backend-aware helper 10종 신설: `_runtime_backend_is_pg` / `_meta_json_to_dict` / `_conv_load_topic` / `_conv_load_product` / `_conv_load_messages_raw` / `_conv_message_exists` / `_conv_update_topic_product` / `_conv_update_topic` / `_conv_copy_messages` / `_conv_load_share_meta`.
- [x] `_fork_conversation_impl` / `_share_anchor_belongs_to_conversation` / `_share_load_messages` / `public_share_view`(cross-DB merge: core_conversations PG + WebProducts/WebAccounts MySQL) / `duplicate_conversation` 라우팅.
- [x] jsonb meta_json: PG read=dict 정규화, insert=`%s::jsonb` 캐스트. MySQL else 분기는 비-postgres 배포용 legacy fallback 보존.
- [x] 회귀 e2e `tests/test_fork_share_cutover.py` (T1~T5 — fork/share(full)/public-view(anon)/duplicate/share(anchored), 500 미발생 단언) + py_compile PASS.
- [x] outside-voice panel(SUBAGENT SHIP, REV-20260609-0001) → REVIEW.md / PR #126 → main 머지(2e89ac3) → web 재배포 → 라이브 e2e 5/5 PASS

### TASK-0168 — 공유뷰 follow-up: error contract + redaction 회귀 가드 (2026-06-09)
- [x] **Minor §12.3** — TASK-0167 outside-voice(REV-20260609-0001) 권고 F1·F2 처리. 성공경로·RBAC·스키마·계약 무변경(방어적 에러처리 + 테스트). (CHG-20260609-SHARE-ERRCONTRACT)
- [x] **F1** `public_share_view`: 데이터 로드(`_conv_load_share_meta`/`_share_load_messages` PG read) 실패 시 bare 500 대신 graceful JSON 500(`"공유 대화를 불러오지 못했습니다."`) — fork 의 명시 500 래핑과 대칭. ViewCount++(revoke race 가드 겸용)는 보존, 실패 시 1 과대카운트는 허용 soft-metric 오차로 주석화.
- [x] **F2** `tests/test_share_redaction_invariant.py`: `_pg_connect` mock 으로 **PG dict-meta 경로**를 결정적 재현 → attachment_derived redact(stale/null token) + internal 메시지 필터 + 정상 본문 보존 + 정책 version gate(CURRENT=비redact) 단언. 컨테이너 in-process 3/3 PASS.
- [ ] py_compile / verify-completion / PR → main 머지 → 재배포 → 라이브 e2e(양 테스트 green)

### TASK-0170 — Fork 문맥 복원: core_messages 복사 (하이브리드 Phase 1) (2026-06-09)
- [x] **Major §12.3** — fork/duplicate/공유-fork 본에서 어시스턴트가 이전 문맥을 인지 못 하던 버그. 원인: LLM 문맥은 `agent_runtime.core_messages`(agent_core `_load_conversation_messages`)에서 읽는데 fork 는 표시 메시지(`messages`)만 복사하고 `core_messages` 미복사 → 복사본 core_messages 가 비어 문맥 0. (CHG-20260609-FORK-CORE-CONTEXT)
- [x] 설계: git식 reference 아키텍처 검토(`DESIGN-fork-reference.md`) → outside-voice(REV-20260609-0003) BLOCKER 2 + 보안 안티패턴 3 발견 → **하이브리드 확정**(ADR-WEB-0005). 사용자 결정.
- [x] **Phase 1 구현**: `_conv_load_core_messages_raw`/`_conv_copy_core_messages`(PG 전용, tool_calls jsonb 보존) 추가 + `_fork_conversation_impl` 에 배선. anchored fork=앵커 created_at 까지, full/duplicate=전체. 교차계정 공유 fork 도 snapshot(상시 cross-tenant 흐름 0). core 복사 실패 시 fork 통째 cleanup(fail-loud, 반쪽 fork 금지). 응답에 `core_copied` 노출.
- [x] 회귀 테스트 `tests/test_fork_share_cutover.py` T1b 추가(copied>0 이면 core_copied>0 — 문맥 복사 단언). py_compile PASS.
- [ ] **Phase 2 (후속 cycle)**: 첨부 — 행 복사(동일 ObjectKey)+로컬 sandbox 스키마 복제+동일소유자 blob 참조. IDOR 게이트 변경 시 outside-voice.
- [ ] verify-completion / PR → main 머지 → 재배포 → 라이브 e2e(T1b green)

### TASK-0171 — Fork 첨부 복사 (하이브리드 Phase 2) (2026-06-09)
- [x] **Major §12.3** — fork 본에서 사용자가 원본 첨부 파일을 볼 수 없던 문제(TASK-0167/0170 은 messages/core_messages 만 복사). ADR-WEB-0005 Phase 2. (CHG-20260609-FORK-ATTACHMENTS)
- [x] **구현**: `_copy_conversation_attachments`(WebConversationAttachments 행을 새 ConversationId+fork AccountId 로 복사 + blob **독립 복사**(get+put 새 ObjectKey — refcount 위험 회피, server-side copy 부재)) + `_fork_conversation_impl` 배선. CSV/XLSX 는 `_ingest_attachment_background` 로 **fork 전용 sandbox 재적재**(조상 스키마 공유 금지). per-attachment fail-open. 응답 `attachments_copied`. IDOR 게이트 무변경(fork 가 자기 행 소유).
- [x] **outside-voice(REV-20260609-0004) FIX-FIRST 반영**: #2 orphan blob → **INSERT 먼저→put→실패 시 행 보상삭제**(업로드 패턴). #6 quota 우회 → 복사 전 `_check_attachment_size_caps`(per-file/conv/account) 검사·초과분 skip. #5 audit → `share.fork` ctx 에 `attachments_copied`/`core_messages_copied` 추가(교차계정 forensics). #7 → 테스트 robust 화(⊆+count).
- [x] 라이브 검증 테스트 `tests/test_fork_attachments.py`(A1~A4: copied 수·시그니처⊆·독립 id·signed_url). py_compile PASS.
- [ ] verify-completion / PR → main 머지 → 재배포 → 라이브 e2e(A1~A4 green)

### TASK-0173 — 실행 단계 "근거(reason)" 사용자 노출 (frontend-only) (2026-06-09)
- [x] **Minor §12.3** — assistant 답변 시 각 실행 단계의 수행 근거가 화면에 안 나와 사용자가 작업의 합리성을 확인 불가. `reason` 데이터는 end-to-end 정상(LLM tool_notes → `agent_runtime.steps.reason_text` → `/api/progress`)인데 프런트가 과거 "TMI 개선"으로 step 사이드 패널에서 reason 을 hover 툴팁(`item.title`)에만 넣고 `.step-reason{display:none}` 으로 숨긴 게 근본. (CHG-20260609-0173)
- [x] `buildStepDetailEl` 에 `.step-reason`(라벨 "근거" pill + 텍스트) 인라인 렌더링 추가 — step 사이드 패널 전 단계가 근거 표시.
- [x] `_renderStepSidePanelBody` 중복 `item.title` 제거 + `buildSqlStepPanel`(완료 상세 SQL 단계)에 동일 reason 추가(일관성 — non-SQL 단계는 `buildStepBlocks` 가 이미 `work — reason` 표시 중이었음). styles.css `.step-reason` 가시 스타일 복원 + 캐시버스터 bump.
- [x] node --check app.js PASS. RBAC/스키마/엔드포인트/시크릿/백엔드 무변경. outside-voice [SKIPPED:frontend-only] (REV-20260609-0173).
- [ ] verify-completion / PR → main 머지 → 재배포 → Windows-browser(PB-0008) 시각 검증

### TASK-0174 — 미리보기 인라인 로더 방어 가드 (2026-06-09)
- [x] `loadCsvAsInlineTable` 값 기반 방어 가드 + `distinctiveValueTokens` 헬퍼 (CHG-20260609-PREVIEW-CSV-GUARD)
- [x] §18.8 패널 JS 오탐 지적 반영 (previewTokens≥2 임계)
- [x] verify-completion → main ff-merge(2b4da2a) → 재배포(web) → PB-0008 Windows-browser 무회귀 확인 (TEST.md §4 2026-06-09 TASK-0174 항목)

### TASK-0184 — LLM 사용량 계정 drill-down + 프로필 사용 내역 차트 + 내 활동기록 제거 (2026-06-10)
- [x] **Minor §12.3** (조회 UI 전용, RBAC·스키마 무변경) — 3건: (A) 관리 콘솔 LLM 사용량의 **계정별 차트가 계정 증가 시 과다 길이/탐색난** → 역할 drill-down(역할 막대 클릭 시 그 역할 계정만 검색·Top-N 페이징으로 펼침, 기본 접힘)으로 대체. (B) 프로필에 **'사용 내역' 탭**(본인 LLM 토큰/모델/요청 간소 차트) 신설. (C) 의도치 않게 노출된 **'내 활동 기록' 탭 제거**. (CHG-20260610-0184)
- [x] **(A)** admin.html 계정별 독립 차트(usageAccountChart/CostChart) → drill 패널(계정 검색 input + page size select + 이전/다음). admin.js `renderStackedHBar` 에 `onRowClick` 추가(역할 토큰/비용 막대 클릭) + `toggleAccountDrill`/`renderAccountDrill`(loadUsage 클로저, byAccount 캐시·역할 키 매칭은 백엔드 `_aggregate_usage_by_role` 와 동일) + 컨트롤 바인딩. 역할별 차트는 불변(종류 적어 무관).
- [x] **(B)** 신규 `GET /api/profile/usage`(app.py `profile_llm_usage`) — `admin_llm_usage`(console.usage.read, admin) 의 본인-범위 축소판(owner_account_id=로그인 계정 강제, INNER JOIN, 추정 비용·역할 enrich 제외). **별도 RBAC 권한 없이 로그인만**(본인 소유 대화 usage 한정 → 권한 카탈로그 무변경). index.html '사용 내역' 탭 + app.js `loadProfileUsage`/미니 SVG 차트(모델별 stacked 세로막대·donut, `<title>` 툴팁) + profile-usage 스타일.
- [x] **(C)** index.html audits 탭/패널 제거, app.js `loadProfileAudits`·renderProfile 권한 게이트·탭 핸들러 제거. 엔드포인트 `/api/profile/audits` 는 호출처 없이 잔존(UI 비노출, 백엔드 게이트 유지).
- [x] make test(컨테이너 pytest+ruff) exit=0 / node --check(app.js·admin.js) / py_compile(app.py) PASS. outside-voice [SKIPPED:RBAC·스키마 무변경, 조회 UI 전용].
- [ ] verify-completion → main ff-merge → 재배포(web) → PB-0008 Windows-browser 시각 검증(drill-down · 프로필 차트 · 활동기록 비노출)
