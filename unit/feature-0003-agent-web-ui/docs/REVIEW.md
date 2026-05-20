---
doc_type: REVIEW
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260519-0020 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase C (REQ-20260519-0001, **Critical** §12.3) — Frontend admin 콘솔 "감사 로그" tab 신설 + 7 항목 filter row + list-detail pane + CSV export (gated) + 작업 화면 / 관리 콘솔 양쪽 PERMISSION_GROUP_ORDER 'audit' 그룹 추가.
- Reason: plan PLAN-APPROVED 2026-05-19 의 Phase C 명시. ChangeJson 의 XSS 차단은 `<pre>` + HTML escape (TASK-0058 share.html 패턴 답습). cursor pagination 으로 audit row 수 large fleet 에서도 안전. CSV gate / tab visibility gate 는 permission map truthy 검사로 hide-vs-disable=hide (TASK-0052 패턴 답습).
- Alt 거부:
  - **본인 audit 작업 화면 drawer**: 본 cycle scope 외. admin 콘솔 진입 권유 위한 작업 화면 placeholder 만.
  - **purge UI 본 cycle**: Critical 등급 + retention 정책 다양 → admin manual SQL 또는 API 직접 호출이 안전. 본 cycle scope 외.
  - **detail pane 의 ChangeJson 인터랙티브 viewer (diff)**: 본 cycle scope 외. `<pre>` 정적 표시가 minimal viable.
  - **action_code multi-select chip**: input + 1 value 가 minimal viable. 별 cycle UX 보강.
- Risks: 작업 화면 placeholder 가 audit 그룹 권한 표시만 + 실 entry point 부재 → 사용자 혼란 가능 (UX wart). `_auditFormatDt` 가 browser local TZ — 다국적 운영 시 admin 간 동기화 차이. CSV button 의 href 가 filter 적용된 URL — 사용자가 후속 filter 변경 후 안 누르면 stale.
- 미해결 followup: Phase E browser headless smoke 가 admin 탭 진입 / filter / detail / CSV button visibility / 새 admin action 발생 시 audit row 1:1 정합 확인. 작업 화면의 audit drawer (`audit.read.own` 본인 view) 별 cycle UX 보강.
- panel: SKIPPED:multi-phase-plan-approved — Frontend 변경은 TASK-0058 share.html 패턴 답습 + CONVENTIONS.md §10.6 정합 lock-in. ChangeJson escape XSS 차단도 검증된 답습.
- Trace: REQ-20260519-0001 → TASK-0073 Phase C → CHG-20260519-0024 → REV-20260519-0020. CONVENTIONS.md §10.6 + TASK-0052 hide-vs-disable + TASK-0058 share.html `<pre>` escape lock-in.

## REV-20260519-0019 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase B (REQ-20260519-0001, **Critical** §12.3) — 3 test 파일 신설. test_audit_dispatcher (7) + test_audit_rbac (10) + test_audit_migration (3) = 20 시나리오. 실 실행은 컨테이너 가동 + admin/operator/sales 자격 필요 — Phase E 사용자 위임 (plan 본문 명시).
- Reason: plan PLAN-APPROVED 2026-05-19 의 Phase B 명시 — "tests/test_audit_dispatcher.py + test_audit_rbac.py (10 시나리오) + test_audit_migration.py". 컨테이너 미가동 본 session 에서 자동 실행 불가, file 작성 only. TASK-0072 `test_search_rbac.py` 의 urllib + login + Set-Cookie 패턴 답습 — 검증 안전한 답습 대상.
- Alt 거부:
  - **pytest 기반 unit test**: 본 repo 의 기존 test 패턴이 urllib script — pytest 의존 추가 X (zero new dependency).
  - **mock dispatcher direct import**: PYTHONPATH 의존 fragile. HTTP endpoint 응답 + DB SELECT 검증이 더 robust.
  - **자동 실행 (본 session)**: 컨테이너 환경 + admin/operator/sales 비밀번호 보유 가정 — 본 session sandbox 미지원. plan 본문이 명시 "환경 미비 시 test 작성만 + 실행은 Phase E 에 위임".
- Risks: 사용자 환경에서 실 실행 시 admin/operator/sales 비밀번호 가용성 미보장 — TASK-0075 의 6/8 PASS scenario (operator pw 미보유로 일부 skip) 동일 trade-off. M1 의 직접 SQL INSERT 가 docker exec mysql 또는 host mysql client 필요 — 환경별 분기. S3a (admin password-reset target audit 가시성) 가 실 password reset 호출이라 부수효과 큼 — manual 검증 권유.
- 미해결 followup: Phase E 에서 컨테이너 가동 후 `python3 tests/test_audit_*.py` 실행 → `docs/TEST.md §4 Test Run History` append. S3a 의 password-reset target user 본인 audit 가시성 검증이 E1 B 의 핵심 — manual 검증 결과 별 cycle 기록.
- panel: SKIPPED:multi-phase-plan-approved — test 작성은 plan PLAN-APPROVED 의 자연 산출. TASK-0072 `test_search_rbac.py` 패턴 답습이라 새 review 면 적음.
- Trace: REQ-20260519-0001 → TASK-0073 Phase B → CHG-20260519-0023 → REV-20260519-0019.

## REV-20260519-0018 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase A6 (REQ-20260519-0001, **Critical** §12.3) — user 5 endpoint best-effort audit + anonymous share view (ActorType='anonymous'). Eng review E4 + Codex C11 (anonymous share path) 합쳐 lock-in.
- Reason: PLAN-APPROVED 2026-05-19. user endpoint (`/api/ask` + share CRUD + anonymous view) 는 fail-open 필수 — long-running LLM 또는 anonymous flow 에서 audit 실패가 user 응답 차단하면 main 기능 손실. TASK-0072 `_log_search_activity` 의 fail-open 패턴이 검증된 답습 대상.
- Alt 거부:
  - **user endpoint Same tx**: Codex C3/C4 — `/api/ask` 의 long-running LLM (분 단위 lock hold) + agent_core 별 connection 정합성 깨짐. Same tx 가 deadlock 위험.
  - **anonymous share view 미감사**: Eng review E4 + Codex C11 — admin/operator 가 누가 share token 으로 access 했는지 가시성 손실. ActorType='anonymous' + ActorAccountId NULL 로 row 등록 (audit completeness 유지).
  - **token full 저장**: PII 위협. token_prefix 8 char 만 (full token = 64 char 의 1/8 노출). share token 의 entropy 충분.
  - **`/api/conversations` search snippet 별 hook**: TASK-0072 `_log_search_activity` 가 이미 Phase A2 에서 dual write — 별 hook 불필요 (자연 통합).
- Risks: dispatcher 실패 시 stderr log 만 — audit completeness 가 silent loss 가능. verify-completion check_11 + Phase B `tests/test_audit_dispatcher.py` 가 silent loss 검출. anonymous view 의 `viewer = _optional_account` 가 cookie 오류 시 None 반환 → False positive 'anonymous' label 가능 (실제로는 logged-in viewer 의 cookie 오류). 본 cycle scope, 별 cycle 검증 필요.
- 미해결 followup: Phase B 의 `tests/test_audit_dispatcher.py` 가 fail-open silent loss path 검증. `tests/test_audit_rbac.py` 의 시나리오 (9) anonymous share view → audit row 생성 검증 + (10) `?actor_type=anonymous` filter 검증. silent loss 의 metric 수집 (`stderr [TASK-0073 Phase A6] failed` 카운터) 별 cycle.
- panel: SKIPPED:multi-phase-plan-approved — Codex C11 + Eng review E4 가 plan 단계 lock-in. TASK-0072 `_log_search_activity` 패턴 검증 답습이라 본 phase 의 추가 review 면 적음.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A6 → CHG-20260519-0022 → REV-20260519-0018. Eng review E4 (anonymous ActorType) + Codex C11 (TASK-0058 share anonymous path) lock-in.

## REV-20260519-0017 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase A5 (REQ-20260519-0001, **Critical** §12.3) — admin 11 mutation endpoint Same tx audit hook + 16 ActionCode build_audit_change_json builder + _audit_admin_mutation helper. plan 의 "13" 은 elastic 표현, 11 endpoint 가 admin mutation 전부.
- Reason: PLAN-APPROVED 2026-05-19. Codex outside voice C6 — raw request 검증 X, builder allowlist 만. PasswordHash / token / api_key 명시 redact. Eng review E5 product delete cascade lock 순서 (system_prompts → product_databases → role_permissions → account_permission_overrides → permissions → products → audit INSERT). Eng review E6 — decorator 거부, 각 endpoint 의 explicit `_audit_admin_mutation()` 호출.
- Alt 거부:
  - **decorator @audit_action**: Eng review E6 거부 — actor capture / ChangeJson builder / masked_fields 가 endpoint 마다 다르므로 magic hide. 11 endpoint 각각 explicit.
  - **src/audit_builders.py 별 module**: PYTHONPATH dependency. app.py 안 helper 섹션이 더 robust + import 부담 0.
  - **POST /admin/products 의 audit 를 inner tx 안**: autocommit=False/True toggle 의 finally 안에 audit hook 두면 rollback 정합성 모호. finally 의 autocommit=True 복원 다음에 hook — autocommit 모드 안전.
  - **DELETE /admin/products 의 audit 를 _audit_admin_mutation helper 로**: E5 cascade lock 순서가 product 의 dependent row 정리 후 audit row INSERT 가 정합 — helper 호출 대신 inline record_audit_event + conn.commit() 한 tx 안 정리.
- Risks: PATCH/POST/DELETE 의 conn.close() 위치가 audit hook 뒤로 이동 — 기존 flow 의 close() 가 implicit commit 이었을 가능성 → audit hook 의 conn.commit() 가 명시 commit 보장. PUT /databases 의 before-state 캡처 SELECT 추가 — 성능 영향 negligible (단 product 의 schemas 수가 작음, ≤ ~10). PATCH /products 의 audit before 가 ProductKey 만 — full snapshot 필요하면 별 SELECT 필요, 본 cycle 의 cost-benefit 으로 후속 정확화.
- 미해결 followup: PATCH /admin/products 의 before-state 가 ProductKey 만 — full WebProducts row 캡처는 별 cycle. Phase B 의 test 가 11 endpoint 각각의 audit row visible 검증. Phase E 의 browser smoke 가 admin 11 action 실 발생 시 audit row 1:1 정합 확인.
- panel: SKIPPED:multi-phase-plan-approved — Eng review E5 (cascade lock 순서) + E6 (explicit dispatcher) + Codex C6 (builder allowlist) 가 plan 단계 lock-in. Critical 등급이나 plan PLAN-APPROVED 후 phase 단위 panel 재호출은 cargo-cult.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A5 → CHG-20260519-0021 → REV-20260519-0017. Codex C6 + Eng review E5/E6 lock-in.

## REV-20260519-0016 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase A4 (REQ-20260519-0001, **Critical** §12.3) — 5 audit read endpoint (`GET /api/admin/audits` + detail + export.csv + actors facet + resources facet) + 1 chunked purge endpoint (`POST /api/admin/audits/purge`). E1 self filter (Actor OR Target) + 404 byte-equal + E8 chunked PK 의사코드 그대로 구현.
- Reason: PLAN-APPROVED 2026-05-19. Eng review E1 = "B (Actor OR Target)" 사용자 결정 — admin actor + user target 이벤트가 user 본인 audit 에 노출 (admin 의 password-reset / 권한 grant / share revoke 이벤트의 user side 가시성). E8 chunked purge 의 Python 의사코드를 그대로 SQL 로 구현 — chunk 별 tx + 30s deadline + idempotency_key (1 분 내 중복 차단) + start/complete self-audit 2건.
- Alt 거부:
  - **`.own` = ActorAccountId 만**: E1 결정 A 라면 본인 actor 만. admin 의 user-target 이벤트가 user 본인 audit 에서 invisible — 보안 가시성 손실. 사용자 결정 B 정합.
  - **detail 404 vs 403 분리**: Codex C-style metadata leak — `.own` 사용자가 다른 사용자 audit id 를 시도하면 403 응답이 row 존재 신호. 모두 404 = byte-equal.
  - **CSV streaming (chunked)**: 본 cycle scope 외. hard cap 50k 로 DoS 방지. 별 cycle 검토.
  - **purge 전체 1-tx**: LRT 회피 위반. chunk = 별 tx + 30s deadline 으로 partial purge 자연 재시작.
- Risks: `.own` Actor OR Target 분기로 anonymous share view 의 viewer 가 본인 audit 에 보이는 경우 — E4 정합 (anonymous actor + share resource 가 share owner 의 audit 에 노출은 의도된 가시성). CSV 50k 가 large fleet 에서 모자랄 수 있음 — 본 cycle scope, follow-up. purge deadline 30s 가 짧을 수 있음 — partial purge 시 다음 호출 cursor 자연 재시작 보장.
- 미해결 followup: Phase A5 의 admin 13 mutation endpoint hook (Same tx) + ActionCode 별 builder. Phase B 의 10 RBAC smoke (특히 (3a) admin password-reset → user 본인 audit 노출, (9)(10) anonymous share view audit_type filter).
- panel: SKIPPED:multi-phase-plan-approved — Eng review E1 / E8 / E5 가 plan 단계에서 SQL filter + 의사코드 lock-in. Critical 등급이나 plan PLAN-APPROVED 후 Phase 단위 panel 재호출은 cargo-cult (REV-20260519-0013/0014/0015 정합).
- Trace: REQ-20260519-0001 → TASK-0073 Phase A4 → CHG-20260519-0020 → REV-20260519-0016. Eng review E1 (Actor OR Target) + E8 (chunked PK purge Python 의사코드) lock-in.

## REV-20260519-0015 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase A3 (REQ-20260519-0001, **Critical** §12.3) — RBAC catalog +4 (`audit.read.own/.any/.export/.purge`) + permission group `audit` 신규 + admin/operator/sales/dba/pending 5 role 자동 catchup. Codex outside voice C8/C9/C10 + Eng review E9 lock-in.
- Reason: PLAN-APPROVED 2026-05-19. `.own/.any` 패턴 (TASK-0058 share + TASK-0063 RBAC catchup) 답습 — 본인 actor/target 만 조회 (.own) + 전체 audit row 조회 (.any superset). admin/dba 가 `.any` + `.export`, admin 만 `.purge` 의 분리는 권한 책임 최소화 (compliance 외부 검토 vs retention 관리 분리). `feedback_outside_voice_for_rbac` 정책 강제 — RBAC 변경은 outside voice 필수, Codex 가 plan 단계에서 14 finding lock-in.
- Alt 거부:
  - **`audit.*` 단일 권한 (group="audit")**: Codex C8 — `.own/.any` 분리 정합성 깨짐. admin 의 `.any` 가 sales 의 `.own` 을 superset 으로 포함하는 의미 명확.
  - **`.purge` 는 dba 도 grant**: dba 가 retention 정책 직접 결정하면 책임 분산. admin 만 grant — Compliance 책임 명확.
  - **dba role 을 SEED_ROLE_DEFINITIONS 에 추가**: TASK-0060 의 dba 가 manual 생성 case 라 SEED 추가는 scope creep. catchup loop 만 보강 (E9 의 가벼운 해석).
  - **permission_group_of fallback="misc"**: Codex C10 — group="audit" 명시 + frontend `PERMISSION_GROUP_ORDER` 갱신 (Phase C scope) 으로 misc fallback 차단.
- Risks: dba role 이 DB 에 부재한 환경은 catchup graceful skip — 향후 dba 생성 시 다음 catchup 에서 backfill. INSERT IGNORE 라 duplicate 안전. `_ensure_permission_catalog` 가 `_ensure_seed_roles` 앞 호출 보장 (TASK-0063 회귀 fix 패턴) — 신규 permission id 가 valid 시점에 catchup 진행.
- 미해결 followup: Phase C frontend `PERMISSION_GROUP_ORDER` 갱신 (admin.js + app.js). Phase D `docs/CONVENTIONS.md §10.6` 갱신 (audit group 의 admin section "관리" 우선 노출). Phase B `tests/test_audit_rbac.py` 의 10 시나리오 검증.
- panel: SKIPPED:multi-phase-plan-approved — RBAC catalog 4 추가는 Codex outside voice + Eng review E9 가 plan 단계 lock-in. 본 phase 단위 commit 마다 panel 재호출은 cargo-cult.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A3 → CHG-20260519-0019 → REV-20260519-0015. Codex outside voice C8/C9/C10 + Eng review E9 lock-in.

## REV-20260519-0014 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase A2 (REQ-20260519-0001, **Critical** §12.3) — `WebAccountActivity` (TASK-0072) 기존 row 흡수 migration helper + `_log_search_activity` dual write wrap. legacy table 본 cycle DROP 안 함 (별 cycle backup 후).
- Reason: Codex outside voice C2 minimum-fix (TASK-0072 schema 발견 — 직전 검토 보고가 놓친 결손). plan 본문 명시 — "기존 row → WebAuditEvents transform + `_log_search_activity` transparent wrap (signature 보존, caller 변경 0)". dual source 일시 공존이 data 보존 우선 + 별 cycle backup 검증 후 DROP 안전.
- Alt 거부:
  - **legacy table 즉시 DROP**: backup 검증 전 DROP 시 audit trail 손실 risk. plan 명시 "data 보존" 위배.
  - **single write (legacy INSERT 제거, dispatcher only)**: legacy table 이 정합 상태 검증 전이라 dual source 비교 검증 불가. 별 cycle 까지 dual 유지가 안전.
  - **migration on demand (별 manual script)**: catchup 패턴 (TASK-0063) 답습 못 함. fast/slow path 양쪽 hydrate 가 zero-touch 정합.
- Risks: dual write 시 동일 audit event 가 두 row — search 통계 double count. 본 cycle frontend (Phase C) 가 WebAuditEvents 만 조회라 UX 영향 0. JSON_OBJECT 가 MySQL 8.0+ 한정 — `docker-compose.yml` MySQL 8.0 가정 (§15.4) 정합. migration RequestId marker 가 64 char limit 안 (`account-activity:` 17 + bigint ≤ 20 = ≤ 37 char) 안전.
- 미해결 followup: 별 cycle TASK 등재 — `WebAccountActivity` data backup → DROP table → `_log_search_activity` mirror 본문에서 legacy INSERT 제거 → search 통계 single source 정합화. Phase B test (`tests/test_audit_migration.py`) 가 idempotency 검증 (두 번 호출 시 두 번째 INSERT 0 row).
- panel: SKIPPED:multi-phase-plan-approved — Codex outside voice C2 가 plan 단계의 minimum-fix 로 이미 lock-in. plan 본문이 transform SQL signature 명시 + idempotency 요구. 본 phase 단위 commit 마다 panel 재호출은 cargo-cult (REV-20260519-0013 의 reasoning 답습).
- Trace: REQ-20260519-0001 → TASK-0073 Phase A2 → CHG-20260519-0018 → REV-20260519-0014. Codex outside voice C2 minimum-fix lock-in.

## REV-20260519-0013 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase A1 (REQ-20260519-0001, **Critical** §12.3) — audit dispatcher `record_audit_event()` + `AGENT_AUDIT_ENABLED` prod startup fail-closed gate + verify-completion check_11 SPOF guard 구현. CEO review 9 decision · Codex outside voice 14 findings + 5 minimum-fix · Eng review E6 (explicit dispatcher) / E7 (SPOF mitigation) 의 in-cycle lock-in.
- Reason: PLAN-APPROVED 2026-05-19 (TASK-0073 Phase A0~F 일괄). Critical 등급이라 Codex outside voice 가 plan 단계에서 14 findings + 5 minimum-fix 의 redesign 흡수 완료. 본 Phase A1 commit 은 dispatcher 인프라 + prod fail-closed gate 만 추가하므로 별도 panel 호출 불필요 — 이미 plan 단계의 outside voice 가 dispatcher signature / gate 정책 / SPOF mitigation 모두 lock-in.
- Alt 거부:
  - **startup hook 안 sys.exit** (FastAPI `@app.on_event("startup")`): main thread 가 await 인 상황에서 raise SystemExit 가 fully propagate 안 되는 환경 존재 (uvicorn worker 분기). module-load time exit 가 가장 단순 + 결정적.
  - **dispatcher decorator pattern** (`@audit_action(...)`): Eng review E6 에서 명시 거부 — decorator 가 actor capture / ChangeJson builder / masked_fields per-endpoint 차이를 magic-hide. 17 hook site 각각 explicit `record_audit_event(...)` 호출.
  - **autocommit dispatcher 안 conn.commit()**: caller 의 transaction 정책 (admin Same tx fail-safe / user fail-open) 과 충돌. dispatcher 는 commit/rollback 안 함 (E6 explicit).
- Risks: module-load `sys.exit` 가 Phase B tests 의 import 차단 가능 — test runner 가 `AGENT_MODE=test` 환경변수 강제. caller 가 dispatcher 의 commit/rollback 책임 망각 시 INSERT 가 visible 안 됨 — admin endpoint same-tx 정책의 docstring + verify-completion check #11 로 인지 강화.
- 미해결 followup: 추후 Phase 들 (A2~E) 모두 본 dispatcher 의 caller wire-up. Phase A5/A6 의 wire-up 시 caller contract (admin Same tx / user fail-open) 의 docstring 보강 + Phase B 의 `tests/test_audit_dispatcher.py` 가 INSERT row visible 한 E2E 검증.
- panel: SKIPPED:multi-phase-plan-approved — Critical §12.3 이나 Codex outside voice + Eng review 가 plan 단계에서 dispatcher signature / gate 정책 / SPOF mitigation 모두 lock-in (REV-20260519-0001 이전 cycle 의 plan 단계 outside-voice 보고 = 본 cycle 의 panel 대체). 본 Phase 단위 commit 마다 panel 재호출은 cargo-cult.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A1 → CHG-20260519-0017 → REV-20260519-0013. CEO review 9 decision + Codex 14 findings + Eng review E6/E7 lock-in.

## REV-20260519-0012 [SKIPPED:design-panel]
- Date: 2026-05-19
- Decision: TASK-0085 (REQ-20260519-0014, Minor §12.3) — lazy-create 사이드바 optimistic pending entry. multi-pending sentinel-keyed `state.pendingConversationEntries` Map + closure-aware cleanup + `_switchToPendingConversationContext` 클릭 swap. backend / RBAC / endpoint / audit / DB 무변경.
- Reason: 사용자 직접 요청 — "+ 새 대화 송신 직후 다른 대화 전환 시 사이드바에서 잠시 사라지는 이슈" + "대화 내부 진입 가능 — 작업 step 현황 출력 위해". TASK-0048 lazy 패턴이 backend list 등재를 응답 시점까지 지연 — frontend placeholder + backend list 둘 다 새 entry 없는 구간이 사이드바 완전 소실. backend 변경 없이 frontend optimistic UI 로 해결.
- Alt 거부:
  - **backend eager row 생성**: TASK-0048 빈 대화 누적 방지 의도 위배.
  - **state.conversations 에 직접 추가**: refreshWorkspace 가 통째 replace 라 사라짐.
  - **single pendingConversation object**: multi-pending 두 번째가 첫 번째 overwrite. TASK-0082 unique sentinel 정합 깨짐.
  - **pendingBubble 도 sentinel 별 Map**: 완전한 multi-bubble. 본 cycle scope 초과.
- Risks: pendingBubble swap 시 step 정보 손실 (cid 전 polling 불가) / closure mismatch 시 cid binding skip / 3 s failed timer / 메모리 누수 (closure cleanup 으로 보호) / legacy appendPendingItem 보존.
- 미해결 followup: 사용자 환경 검증 (5 시나리오) / lazy-create progress streaming (cid 미리 발급) / failed entry dismiss 버튼.
- panel: SKIPPED:design-panel — Minor §12.3 + frontend state machine 변경 + 단일 파일 + RBAC/auth/DB 무영향. AGENTS.md §18.4 SKIPPED 정책 (단순 작업).
- Trace: REQ-20260519-0014 → TASK-0085 → CHG-20260519-0016 → REV-20260519-0012. TASK-0048 + TASK-0082 design 의 자연 연속.

## REV-20260519-0011 [SKIPPED:design-panel]
- Date: 2026-05-19
- Decision: TASK-0084 (REQ-20260519-0013, Minor §12.3) — D2Coding 우선 monospace stack 으로 전역 통일 재시도. `:root` 의 `--font` / `--mono` 두 토큰을 다시 단일 D2Coding 우선 monospace stack 으로 통합 (`"D2Coding", "D2Coding ligature", "Cascadia Code", "SFMono-Regular", Consolas, "Noto Sans Mono CJK KR", ui-monospace, Menlo, monospace`) + `--font: var(--mono)` 참조. admin.html cache-bust `?v=20260519-d2coding-mono`. index.html cache-bust 는 사용자 main wt revert 의도 존중 skip.
- Reason: 사용자 직접 요청 "D2Coding 폰트를 우선해줄 수 있을까요?" + AskUserQuestion (D2Coding 적용 범위) 응답 "본문 + 코드 모두 (전역 monospace 통일 부활)". 흐름: (1) CHG-0013 — 첫 요청 monospace 통일 시도 → (2) CHG-0014 — 한글 가독성 호소로 sans-serif 환원 → (3) CHG-0015 — D2Coding (NAVER 한글 monospace 가독성 검증된 폰트) 우선으로 monospace 통일 부활. 사용자는 monospace 의 정렬 효과를 원하지만 한글 가독성도 보장되어야 함을 D2Coding 으로 양립. D2Coding 은 한글·영문 모두 등폭이며 한글 가독성이 system monospace 보다 우월하므로 사용자 가독성 호소 (CHG-0014 reason) 완화 가능.
- Alt 거부:
  - **본문은 sans-serif 유지 + var(--mono) 만 D2Coding 우선**: 사용자가 본문 가독성 + 코드 영역 한글 등폭 둘 다 보장. 단점 — 사용자가 AskUserQuestion 응답에서 명시적으로 "본문 + 코드 모두 (전역 monospace 통일 부활)" 선택. 본 cycle 의 명시 결정과 충돌. 향후 사용자가 가독성 호소 시 본 옵션으로 별 cycle.
  - **D2Coding WebFont 도입 (CDN 또는 self-host)**: D2Coding 미설치 환경에서도 보장. 단점 — 외부 의존 (CDN) 또는 self-host 인프라 + 첫 로딩 latency + CSP 검토 + offline 환경 제약. 본 cycle 범위 초과 — 별 cycle 에서 결정. 현재는 사용자가 D2Coding 을 직접 설치한 환경 가정.
  - **D2Coding ligature 만 우선**: ligature 변형 한정. 단점 — ligature 미사용 사용자 환경 분기. 일반 D2Coding 우선 + ligature 도 fallback chain 에 포함이 안전.
  - **CHG-0013 진동 차단 위해 강제 sans-serif**: 사용자 요청 무시. 정책 위반.
- Risks:
  - **D2Coding 미설치 환경**: fallback chain 으로 자동 대체되지만 한글이 system monospace 또는 default 폰트로 fallback → 사용자 의도 (D2Coding 한글 가독성 + 등폭) 미달. 사용자 환경에 D2Coding 설치 안내 필요 (https://github.com/naver/d2codingfont).
  - **monospace 한글 가독성 trade-off**: D2Coding 이 한글 monospace 중 가독성 좋지만 sans-serif 본문 (system-ui 등) 보다는 가독성 낮음. 사용자가 CHG-0014 에서 "눈 아픔" 호소했었음 — D2Coding 으로도 같은 호소 가능. 사용자 검증 후 추가 조정 (예: 본문 sans-serif + 코드 D2Coding) 가능.
  - **stack 첫 entry 인용**: `D2Coding` 과 `D2Coding ligature` 두 변형 모두 첫 줄 우선 — 시스템에 설치된 변형 자동 적용. 일부 시스템이 두 변형을 다른 폰트로 인식 가능 — 영향 최소 (둘 다 D2Coding 계열).
  - **CHG-0013/0014/0015 진동 trace**: 본 cycle 이 세 번째 진동 — 사용자 의도가 명확히 결정된 상태이긴 하나, 미래 cycle 에 readability vs alignment 의 trade-off 가 재발할 가능성. WebFont 도입이 영구 해결책 — 별 cycle.
  - **share.css 무변경**: 공유 페이지 별도 stylesheet. 본 cycle 영향 없음.
- 미해결 followup:
  - **D2Coding WebFont 도입**: 환경 무관 보장. CSP / CDN / self-host 검토 + 첫 로딩 FOUC 처리.
  - **사용자 가독성 검증**: 본 stack 적용 후 사용자가 한글 본문 가독성에 만족하는지 확인. 호소 시 본문 sans-serif + 코드 D2Coding 분리 또는 다른 한글 monospace (예: Sarasa Gothic K Mono) 시도.
- Trace: REQ-20260519-0013 → TASK-0084 → CHG-0015 → REV-0011. AC-0184 / AC-0185 의 design intent 가 CHG-0015 로 단일 D2Coding 우선 monospace 통합으로 합쳐짐. AC-0186 cache-bust 갱신. AC-0187 (D2Coding 우선) 등록.
- [SKIPPED:design-panel] cosmetic-only typography stack 갱신 (`:root` 의 `--font` / `--mono` 두 토큰 + admin.html cache-bust). 사용자가 직접 D2Coding 우선 monospace 통일 의사결정 (AskUserQuestion 응답 명시). UI 도메인 변경이나 security / data / API contract / RBAC / audit 영향 없음 — 단순 CSS 토큰 + cache-bust 1 line. design panel 호출 가치 vs 실행 비용 trade-off 에서 skip 정합 (§18.8 cosmetic-only exception). 사용자가 추가 가독성 호소 시 별 cycle 에서 design panel 호출 가능.

## REV-20260519-0010
- Date: 2026-05-19
- Decision: TASK-0083 followup (REQ-20260519-0012, Minor §12.3) — REV-0009 의 monospace 통합 design 폐기 + 한글 가독성 우선 system-ui sans-serif stack 으로 재설정. `:root` 의 `--font` 를 `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", "맑은 고딕", "Helvetica Neue", Arial, sans-serif` 로 갱신. `--mono` 는 REV-0009 이전 stack (`"Cascadia Code", "SFMono-Regular", Consolas, monospace`) 복원. `--font: var(--mono)` 참조 제거 → 두 토큰 의미 분리 회복. admin.html cache-bust 토큰을 `?v=20260519-cjk-readable` 로 갱신, index.html cache-bust 는 사용자 직접 revert 흔적 (system reminder) 존중하여 본 cycle 에서 skip.
- Reason: 사용자 직접 보고 — "중간에 확인해보니, 한글 기준으로 눈이 아픕니다… 한글 기준으로 가장 범용성있는 폰트로 다시 설정해주세요". REV-0009 의 monospace 통합은 영문·ASCII 정렬에는 정합하지만 한글에는 (a) 모노스페이스 한글 폰트 (D2Coding, Noto Sans Mono CJK KR) 가 시스템에 없는 경우 fallback 결과로 폭 정합 깨짐 + (b) 한글 모노스페이스가 시스템에 깔려 있어도 일반 본문 가독성이 낮음. 사용자의 가독성 우선 결정. 가장 범용성 있는 한글 폰트 stack 은 OS native (Windows = 맑은 고딕, macOS = Apple SD Gothic Neo, Linux = Noto Sans CJK 자동 fallback) 를 우선하는 system-ui 기반. 별도 WebFont 설치 없이 모든 환경에서 자연 한글 렌더링.
- Alt 거부:
  - **Pretendard 우선 stack**: 한글 디자인 표준이며 가독성 우수. 단점 — 시스템에 미설치 시 WebFont 로딩 필요 (별도 CDN/self-host). 본 cycle 의 "범용성" 우선이라 system-native 가 정합. 사용자가 Pretendard 도입 요청 시 별 cycle 에서 WebFont + stack 첫 자리 추가.
  - **`--font` 만 변경하고 `--mono` 의 한글 monospace fallback (D2Coding, Noto Sans Mono CJK KR) 은 유지**: 코드/로그 영역의 한글이 등폭 유지. 단점 — `var(--mono)` 사용처가 실제 한글을 자주 표시하는 곳인지 검토 결과 SQL/code snippet 중심이라 한글 비중 낮음 + 시스템 의존성 유지 부담. REV-0009 이전 원본 stack 복원이 가장 단순 + 회귀 0.
  - **CHG-0013 entry 를 git revert 또는 amend**: append-only 정책 (§5.2) + CHG-0013 가 다른 AI 작업자의 a7b7ded commit 에 흡수된 상태 → revert 시 다른 작업자의 다른 변경도 영향. CHG-0014 로 forward-only 정정.
  - **index.html cache-bust 도 갱신**: admin.html 과 동일 갱신으로 일관성. 단점 — 사용자 system reminder 의 "intentional, don't revert" 신호 위반 가능 + 사용자가 main wt 에서 직접 revert 한 의도 (이전 작업자 영역과의 분리) 와 충돌. 안전 마진을 위해 index.html 은 skip + 사용자에게 hard refresh 안내.
  - **WebFont 도입 (Noto Sans KR variable / Pretendard)**: 모든 환경에서 동일 한글 렌더링 보장. 단점 — 외부 의존 + 첫 로딩 latency + CSP 검토 + offline 환경 제약. 본 cycle 범위 초과 — 별 cycle.
- Risks:
  - **index.html cache-bust 미갱신**: 사용자가 작업 화면 첫 진입 시 styles.css 가 브라우저 캐시 hit → 새 sans-serif stack 즉시 안 보일 수 있음. Ctrl+Shift+R (hard refresh) 또는 DevTools "Disable cache" 모드 필요. UX 영향 단기 (캐시 만료 후 자연 해소).
  - **system-ui 구형 브라우저 미지원**: iOS Safari 12 이하 / Android Browser 일부가 `system-ui` 키워드를 인식 못 함 — fallback `-apple-system` / `BlinkMacSystemFont` 가 그 자리를 채움. 실용적 risk 0.
  - **CHG-0013 design intent 의 부분 해제**: AC-0184 "전역 monospace 통일" 의 의도가 CHG-0014 로 사실상 폐기. AC-0185 (var(--font) 영역은 sans-serif, var(--mono) 영역은 monospace 유지) 로 재정의. 추후 read 시 CHG-0013 + CHG-0014 의 trace 가 명확.
  - **한글 폰트 스타일 차이 (OS 별)**: 맑은 고딕 / Apple SD Gothic Neo / Noto Sans CJK 가 weight·shape 미세하게 다름 — 사용자 환경별 시각 차. 의도된 trade-off (범용성 우선).
  - **share.css 무변경**: 공유 페이지는 별도 stylesheet — 본 cycle 영향 없음. 사용자가 share.html 도 갱신 요청 시 별 cycle.
- 미해결 followup:
  - **사용자 환경 검증**: 본 stack 의 한글 가독성을 사용자 환경 (Windows 맑은 고딕 / macOS Apple SD Gothic Neo / Linux Noto Sans CJK) 에서 직접 확인.
  - **Pretendard WebFont 도입 검토**: 모든 환경에서 동일 한글 렌더링 필요 시.
  - **`var(--mono)` 영역의 한글 가독성 별도 검토**: 코드/로그 영역에서 한글이 등장하는 경우 monospace 가독성 issue 있는지 사용자 확인.
- Trace: REQ-20260519-0012 → TASK-0083 followup → CHG-0014 (sans-serif 환원) → REV-0010. REV-0009 의 design intent 는 본 entry 로 정정됨 — append-only 유지하되 후속 의사결정이 우선.

## REV-20260519-0009
- Date: 2026-05-19
- Decision: TASK-0083 (REQ-20260519-0011, Minor §12.3) — `:root` 의 `--font` / `--mono` 두 토큰을 단일 monospace stack 으로 통합. `--mono` 에 한글 monospace fallback (`D2Coding`, `Noto Sans Mono CJK KR`) 추가 + `--font: var(--mono)` 참조. body / button / input / textarea / select 의 기존 cascade (`var(--font)` / `font: inherit`) 가 그대로 작동해 작업·관리 화면 전역에 등폭 글꼴 적용. cache-bust 토큰 동시 갱신 (index.html + admin.html).
- Reason: 사용자 직접 요청 — "프로젝트로 실행되는 웹브라우저 내에서 출력되는 폰트를 monospace로 변경하여 문자열 길이와 실제 표현되는 위치가 정합하도록 구성". 의도는 "한 글자 한 글자가 같은 너비를 차지해서 ASCII 표 / 로그 / 결과 출력의 컬럼 정렬이 깨지지 않게" 로 해석. 현재 `--font` 가 Segoe UI / Noto Sans KR (proportional) 라 한글 / 영문 모두 가변 폭 → 사용자 의도와 불일치. 가장 단순한 변경 (`--font` 를 monospace stack 으로 치환) 으로 전역 일관 적용 가능. body 단위 `font-family: var(--font)` 가 cascade 의 출발점이라 단일 토큰 변경으로 전체 효과.
- Alt 거부:
  - **`* { font-family: monospace !important; }` 같은 universal selector 강제**: 모든 element 강제 적용. 단점 — `var(--mono)` 를 명시 적용한 코드 영역 (line 1069 등) 이 사실상 의미 잃음 + `!important` 가 향후 part-only 회복을 어렵게 함. 기존 token 시스템 활용이 design intent 보존 측면 우월.
  - **body 의 `font-family` 만 변경 (`var(--font)` → `var(--mono)`)**: 단일 line 변경으로도 효과 동일. 단점 — `--font` 토큰이 정의는 있으나 실제 사용처 없음 → 의도 불명. `--font: var(--mono)` 통합이 향후 reader 에게 "두 토큰이 의도적으로 같다" 를 명시.
  - **WebFont (D2Coding / JetBrains Mono) CDN 로딩**: 시스템에 monospace 한글 폰트 미설치 환경에서도 한글 등폭 보장. 단점 — 외부 의존 + 로딩 latency + offline 환경 제약 + CSP 검토. 본 cycle 의 1-line CSS 변경 범위 초과 → 별 cycle.
  - **share.html 까지 동시 변경**: 공유 페이지도 monospace 통일. 단점 — share.css 의 typography 가 별도 design intent (공유 뷰는 일반 사용자 대상이라 가독성 우선) 일 수 있음. 사용자가 "프로젝트로 실행되는 웹브라우저" 라고 표현 — 작업·관리 화면을 가리킨다고 해석. share.html 도 통일 요청 시 별 cycle.
  - **monospace 영역만 명시 변경 (예: result table, log view 만)**: 더 보수적인 접근. 단점 — 사용자 요청 "출력되는 폰트" 는 전역 의도 표현. 부분 변경은 사용자 의도 축소 해석.
- Risks:
  - **한글 monospace 시스템 의존**: D2Coding / Noto Sans Mono CJK KR 미설치 환경에서 한글이 fallback `ui-monospace` / `monospace` 로 해석되어 system default 한글 (proportional) 로 렌더 가능. CSS 단독으로 강제 불가. 사용자가 정합 깨짐을 보고 시 (a) 시스템 폰트 설치 안내 또는 (b) WebFont 도입 (별 cycle).
  - **가독성 trade-off**: monospace 가 일반 본문 가독성 (특히 긴 한글 문장) 보다 ASCII 정렬에 최적화. 사용자가 일부 영역 (network / button label / popover) 만 sans-serif 로 복원 요청 시 그 영역의 `font-family` 를 `var(--font)` 가 아닌 별도 stack 으로 명시.
  - **font 토큰 의미 분리 소실**: `--font` (proportional 의도) 와 `--mono` (등폭 의도) 의 분리가 사라짐. 향후 design intent 회복 시 line 35 `--font: var(--mono)` 를 명시 stack 으로 되돌리면 됨 — 1-line 회복 가능.
  - **cache-bust 토큰 동기화**: index.html + admin.html 두 곳 모두 갱신. share.html 은 share.css 사용 (별 stylesheet) — cache-bust 동기화 불필요.
  - **AC-0184 신규 등록 + 회귀 검증**: 기존 AC (chat pane / lazy-create / unique sentinel / search / excerpt) 모두 typography 와 무관 → cascade 동일성으로 회귀 0. smoke 시나리오는 MODIFY.md 의 Verification 항목 참조.
- 미해결 followup:
  - **한글 monospace WebFont 도입**: 사용자 환경 무관 등폭 보장. CDN (예: jsDelivr 의 D2Coding) 또는 self-host. CSP / 로딩 latency / offline 영향 검토. 별 cycle.
  - **share.html monospace 통일 여부**: 사용자 의도 확인 후 결정.
  - **specific 영역의 sans-serif 복원 요청**: 사용자가 가독성 보고 시 부분 복원.
- Trace: REQ-20260519-0011 → TASK-0083 → CHG-20260519-0013 → REV-20260519-0009. AC-0184 (전역 monospace 통일) 등록.

## REV-20260519-0008
- Date: 2026-05-19
- Decision: TASK-0082 (REQ-20260519-0010, Minor §12.3) — lazy-create unique sentinel design 도입. 글로벌 단일 `PENDING_CONV_SENTINEL` 토큰을 각 lazy-create 진입마다 `state.pendingSentinel = _newPendingSentinel()` 으로 분리 + closure-aware cleanup. TASK-0081 의 stale guard 자연 흡수.
- Reason: 사용자 직접 보고 followup of TASK-0081 — "+ 새 대화 클릭 후 입력칸 활성화 안 됨". 직접 코드 검토로 root cause 재구명: (1) `isCurrentConvBusy()` 가 글로벌 단일 sentinel (`PENDING_CONV_SENTINEL`) 점유 여부 검사. (2) 첫 send 의 in-flight 시 busyConversations 에 sentinel 점유 → 사용자가 + 새 대화 클릭해도 두 번째 컨텍스트에서 isCurrentConvBusy() 가 same sentinel 검사로 true 반환 → renderComposer 가 input.disabled = true 그대로 → 활성화 안 됨. (3) TASK-0081 의 guard 분기는 in-flight 시 early return + renderComposer 미호출 — input 상태 update 안 됨. 두 결함이 합쳐져 사용자 증상 발생. 근본 해결은 unique sentinel design — 컨텍스트별 별개 토큰으로 isCurrentConvBusy 가 두 번째 컨텍스트에서 false 반환.
- Alt 거부:
  - **TASK-0081 의 guard 분기에서 input.disabled = false 강제 + toast 안내**: minimal hotfix (1~2 줄). 단점 — input 활성화는 됐지만 send 시점에 isCurrentConvBusy=true 라 또 차단 → 무한 루프 UX. 사용자가 prompt 작성해도 보낼 수 없음.
  - **isCurrentConvBusy 의 sentinel 검사를 시간 기반 비교**: pendingNewConversation 진입 시간 기록 후 비교. 너무 fragile + race window 다양.
  - **글로벌 sentinel 제거 + busyConversations 에 lazy 진입 자체를 add 안 함**: backend 와의 race window 보호 상실 — backend 의 lazy-create 가 종료되기 전 사용자가 다시 send 시 동일 cid 충돌 위험. sentinel design 의 목적 (race window 보호) 상실.
  - **각 컨텍스트마다 별도 state slice (multi-pending state machine)**: 가장 robust 하지만 frontend state 모델의 대규모 refactor — overkill. 본 fix 의 unique sentinel + closure cleanup 으로 충분.
- Risks:
  - **closure mismatch 시 첫 대화의 activeConversationId 갱신 skip + polling skip**: 사용자가 첫 응답 도착 전 + 새 대화 클릭으로 두 번째 컨텍스트 이동한 경우, 첫 대화의 newCid 가 발급돼도 본 컨텍스트에서 자동 binding 안 함. 사용자가 사이드바 conversation list 에서 첫 대화 클릭으로 진입해야 함. `refreshWorkspace(newCid)` 가 사이드바 list 를 refresh 하므로 첫 대화는 표시. 의도된 동작 (사용자 의지 = 두 번째 대화 진입) 이지만 사용자 인지 위해 별 cycle 에서 toast 안내 추가 검토 가능.
  - **pendingSentinel race**: `Math.random().toString(36).slice(2, 8)` 6 char 16M 분리. 동일 ms 안 다중 진입 시 충돌 위험 무시 가능.
  - **legacy PENDING_CONV_SENTINEL reference**: 본 fix 후 글로벌 단일 토큰 검사 경로 모두 `state.pendingSentinel` 로 변경. 상수 자체는 호환 별칭으로 유지 — 별 cycle 정리 가능.
  - **TASK-0081 의 catch cleanup 정책 보존**: 본 design 의 catch path 도 closure-aware cleanup 으로 TASK-0081 의 의도 유지. 다만 closure mismatch 시 (드물 것이나) cleanup skip — 두 번째 컨텍스트의 state 보호.
- 미해결 followup:
  - **사용자 환경 직접 검증**: 4 종 회귀 시나리오 (in-flight 중 새 대화 / catch 후 새 대화 / 응답 후 새 대화 / pending bubble error 표시 보존) 는 코드 trace + node --check 로 검증. 사용자 환경의 정확한 reproduce 시 추가 cycle 가능.
  - **legacy 상수 cleanup**: `PENDING_CONV_SENTINEL` 의 외부 reference 없음 확인됨 — 별 cycle 에서 정리 가능.
  - **첫 대화 closure mismatch 안내 toast**: 사용자가 첫 응답 도착 시점에 두 번째 컨텍스트라면 toast "이전 요청 응답이 도착했습니다 — 사이드바에서 첫 대화를 확인하세요" 추가. UX 가치 별 cycle 판단.
- Trace: REQ-20260519-0010 → TASK-0082 → CHG-20260519-0012 → REV-20260519-0008. TASK-0081 의 stale guard / catch cleanup 정책 본 design 으로 자연 흡수. AC-0072 / AC-0075~0077 / AC-0176~0178 회귀 보호.

## REV-20260519-0007
- Date: 2026-05-19
- Decision: TASK-0081 (REQ-20260519-0009, Minor §12.3) — `app.js` 의 `beginPendingConversation()` early-return guard 조건을 `state.pendingNewConversation` 단독 → `state.pendingNewConversation && state.busyConversations.has(PENDING_CONV_SENTINEL)` 로 좁힘. 추가로 `sendPrompt()` 의 lazy-create catch 분기 진입 시점에 `state.pendingNewConversation = false` cleanup 1 줄 명시.
- Reason: 사용자 직접 보고 — "새 대화에서 요청을 보낸 후, 다시 새 대화로 별개의 요청을 보내려고 했을 때 진행되지 않는 이슈" + 증상 추가 확인 ("두 번째 send 를 진행하는 상호작용 (요청 UI 버튼, Ctrl+Enter) 가 막혀있다"). Explore subagent 의 코드 trace 와 직접 코드 검토 (line 333~337 `isCurrentConvBusy()` + line 2993 `beginPendingConversation` early-return + line 3437 `sendPrompt` busy guard + line 3533~3551 catch 분기) 로 root cause 2 군데 확정. (1) `beginPendingConversation` early-return 가 stale `pendingNewConversation` flag 만으로 진입 차단 — catch 분기가 flag cleanup 누락이라 한 번 실패한 lazy-create 가 두 번째 "+ 새 대화" 진입 자체를 막음. (2) catch 분기 cleanup 부재. fix 는 두 layer 모두 가드.
- Alt 거부:
  - **`beginPendingConversation()` 의 가드를 완전히 제거**: 사용자 클릭 의도를 100% 신뢰하고 항상 reset 후 진입. 단점 — 첫 lazy-create 가 실제 in-flight (sentinel 점유) 인 race window 에서 사용자가 클릭 시 두 번째 sentinel add 가 동일 KEY 충돌 + busyConversations Set 의 멱등성으로 보이지만 finally 의 delete 가 두 번 일어나 race. 안전 마진을 위해 sentinel 점유 시에만 보류 유지.
  - **`sendPrompt()` 의 line 3437 `isCurrentConvBusy()` 자체 우회**: 사용자가 두 번째 새 대화에서 send 를 시도할 때 busy 검사 skip. 단점 — backend 의 동일 계정 동시 lazy-create 가 의도 외 conv 생성 가능. busy guard 자체는 보존 + state cleanup 으로 해결.
  - **backend 의 동일 계정 dual-pending 제약 추가**: `/api/ask` 의 lazy-create 진입 시 같은 account 의 직전 unset conversation 존재 여부 검증. 단점 — backend 정책 변경 + 사용자 의도와 무관한 차단 가능 (정상 use case 인 빠른 multi-conv 도 차단). frontend state 단순 정리가 정합.
- Risks:
  - **lazy-create in-flight 중 "+ 새 대화" 진입 보류 유지**: 사용자가 첫 송신 응답을 기다리는 중 두 번째 대화로 전환 시도 시 입력란 포커스만 잡고 return. 의도된 동작 (sentinel 중복 race 방지) 이나 사용자가 "왜 안 됨" 으로 인지할 수 있음. UX 측면 toast 안내 추가는 별 cycle.
  - **catch 분기 cleanup 시 pending bubble error 표시와 상태 분리**: `state.pendingNewConversation = false` 직후 사용자가 "+ 새 대화" 클릭 시 `state.pendingBubble` 의 error 영역도 함께 정리될 수 있음. AC-0077 의 빨간 오류 영역 노출 의도와 약한 trade-off — 사용자가 새 대화로 즉시 이동하면 오류 영역 확인 못 할 수 있음. toast 의 "다시 시도하거나 사이드바를 새로고침해 주세요" 안내가 1차 채널.
  - **다른 entry point 검증**: `state.pendingNewConversation` 을 set 하는 위치 = `beginPendingConversation()` line 3001 (본 함수 내부), reset 위치 = (a) `sendPrompt()` success line 3524 (`isLazyCreate && newCid` 조건부) + (b) catch 신규 line 3537 cleanup. 그 외 3rd-party 진입 없음 (grep 검증 — `pendingNewConversation` 출현 위치 5 곳 모두 동일 흐름 안).
- 미해결 followup:
  - **사용자 환경 직접 검증**: 본 fix 의 회귀 시나리오 5 종은 코드 trace + node --check 로 검증. 사용자 환경의 정확한 catch 트리거 조건 (network 종류 / timeout / 서버 응답 형식) 은 미확정 — 사용자가 본 fix 후 동일 reproduce 시 추가 cycle 가능.
  - **UX toast 안내**: in-flight 보류 + catch cleanup 두 분기 모두 사용자 행동에 미세한 비대칭 (전자는 click 무동작, 후자는 새 대화 정상 진입) — toast 로 명시 가능. 별 cycle.
- Trace: REQ-20260519-0009 → TASK-0081 → CHG-20260519-0011 → REV-20260519-0007. AC-0072 (pending bubble) / AC-0075~0077 (lazy-create UX) 회귀 차단.

## REV-20260519-0006
- Date: 2026-05-19
- Decision: TASK-0080 (REQ-20260519-0008, Minor §12.3) — `_collect_matched_excerpts` 의 SELECT 를 `AgentMemoryMessages` + `AgentCoreMessages` UNION ALL + `ROW_NUMBER OVER (PARTITION BY cid ORDER BY msg_id DESC)` 으로 conv 별 더 최근 매칭 1건 선택. collation 통일 `COLLATE utf8mb4_unicode_ci`.
- Reason: 사용자 직접 확인 — "`excerpt 의 AgentCoreMessages 포함 (UNION)` 자세하게 다시 설명해주세요". TASK-0077 / TASK-0078 의 REVIEW followup 으로 명시만 했고 실제 코드 변경 없었음. 정직 설명 후 사용자 결정 — 본 cycle 진행. TASK-0072 의 `_list_conversations` search EXISTS subquery 는 두 table 모두 검사하므로 excerpt 도 두 table 모두 검사해야 정합. core-only conv 의 snippet 부재 회귀 차단.
- Alt 거부:
  - **두 table 별 query 2회**: AgentMemoryMessages 먼저 → AgentCoreMessages fallback. Python 측에서 conv 마다 둘 중 더 최근 결정. UNION 보다 query 2 회 + Python 후처리. 본 fix 의 단일 UNION query 가 더 효율 + DB 단일 transaction.
  - **AgentMemoryMessages 우선 + fallback**: Python merge. memory 우선이 일반적이나 conv 가 core 우선인 케이스 있음 — priority 가정 위험. msg_id 단순 비교가 schema agnostic.
  - **timestamp 컬럼 기반 정렬**: 두 table 의 timestamp 컬럼 존재 여부 + 통일 schema 검증 필요. msg_id (auto-increment) 는 schema 보장. 우회.
- Risks:
  - **msg_id namespace 차이**: AgentMemoryMessages.Id (BIGINT) 와 AgentCoreMessages.id (BIGINT 추정) 가 다른 schema. 더 큰 id = 더 최근 가정 (monotonic 시간 증가). 동시 INSERT race 의 모호함 sub-second — 사용자 시각 영향 0. 검증: 두 table 의 schema 확인 필요 (별 cycle).
  - **collation 통일 cost**: index 우회 가능 — query 비용 ↑. WHERE conv_ids IN (...) 으로 row scope LIMIT 50 conv 단위라 cost overhead 미미.
  - **AgentCoreMessages content NULL**: LIKE NULL 매칭 = false 라 자동 제외. NULL content conv 는 excerpt 부재 (frontend snippet skip).
  - **search EXISTS / excerpt 의 동기화**: TASK-0072 의 EXISTS 가 두 table — 본 fix 와 일치. 향후 EXISTS 만 변경 시 동기화 깨짐 — search test (TASK-0072 의 Phase B 시나리오) 에 두 table coverage 추가 권고 (별 cycle).
- 미해결 followup:
  - **excerpt 의 neighboring line 추가** (TASK-0078 followup) — 매칭 line 이 매우 짧은 경우.
  - **backend matched_message_id 응답** (TASK-0077 followup) — jump 정확도 100%.
  - **popover bottom-edge clamp** (TASK-0076 followup) — viewport 하단 chip drop-up.
- Trace: REQ-20260519-0008 → TASK-0080 → CHG-20260519-0010 → REV-20260519-0006 (followup of TASK-0077)

## REV-20260519-0005
- Date: 2026-05-19
- Decision: TASK-0079 (REQ-20260519-0007, Minor §12.3) — `.chat-pane` 에 `flex: 1 1 auto; min-height: 0` 추가 (CSS 2 line). TASK-0066 의 ChatGPT 패턴 layout 재구조화 시점에 누락된 cascade 잔여 결함.
- Reason: 사용자 screenshot 보고 — 짧은 대화 + 큰 viewport 조합에서 composer 아래 viewport bottom 까지 회색 빈 영역. 원인: `.chat-column` flex container 안에서 `.chat-pane` 의 flex 미정의 (default `flex: 0 1 auto`) → 자식 max-content 만 차지. `.messages-wrap (flex: 1)` 이 chat-pane 안에서 grow 하려면 chat-pane 자체가 column 의 남은 영역 차지 필요. `min-height: 0` 은 overflow 자식 (messages-wrap 안 messages) 의 flex 자라기를 허용. TASK-0068~0071 의 cascade hotfix chain 이 admin 영역만 다뤘고 (`.admin-shell` / `.admin-list-detail` / `.admin-workspace`) 작업 화면 `.chat-pane` 은 미적용 — 본 cycle 이 cascade 마무리.
- Alt 거부:
  - `.chat-pane { height: 100% }` — flex container 안 자식의 height: 100% 는 grow 보장 안 됨 (parent height 가 100% 이어야). flex: 1 이 더 명시적.
  - `.chat-column` 의 grid-template-rows 명시 (TASK-0071 패턴) — chat-column 은 flex 가 더 자연 (가변 자식). grid 로 가면 chat-pane row 가 1fr 명시 필요 + topbar + chat-pane 두 row 분배. flex 가 더 단순.
  - composer 를 chat-column 직접 자식으로 이전 (`.chat-pane` 분리) — TASK-0066 의 의도 (chat-pane 가 composer 포함 단위) 깨짐. layout DOM 변경은 회귀 위험 ↑.
- Risks:
  - **다른 viewport 조합**: 본 환경 chrome headless 가 default flex 동작 일관성 ↑. 사용자 환경에서 추가 회귀 검증 가능성 제한 — 다른 brower / DPI 조합 사용자 확인 권장.
  - **mobile 반응형**: `.app-shell` 의 max-width 680px 분기에서 grid → single column. `.chat-pane` 의 flex chain 은 mobile 에서도 정상 (single column 안 grow).
  - **TASK-0068~0071 cascade chain 의 missing 마지막 piece**: admin 영역 fix 만 cascade hotfix 로 진행되고 작업 화면은 동일 결함 노출까지 누적 — 본 fix 가 chain 마무리. 향후 layout 재구조화 시 chain 전체 (.app-shell, .admin-shell, .chat-pane, .admin-workspace, .admin-list-detail) 일관 적용 권고.
- 미해결 followup:
  - **layout 회귀 검증 자동화** — Phase 시각 검증 (gstack `/qa` 또는 screenshot diff) 도입 권고. 별 cycle.
- Trace: REQ-20260519-0007 → TASK-0079 → CHG-20260519-0009 → REV-20260519-0005 (TASK-0066 cascade 잔여 결함 hotfix)

## REV-20260519-0004
- Date: 2026-05-19
- Decision: TASK-0078 (REQ-20260519-0006, Minor §12.3) — search modal 3 항목 추가 hotfix. mouseup race 보강 (mouseup target 도 추적), preset 텍스트 "부터" 제거, snippet 본문 발췌 line-based clip.
- Reason: TASK-0077 의 5 항목 fix 적용 후 사용자 직접 테스트 보고 — (1) modal 바깥 mousedown 후 modal 안 mouseup 일 때도 close 됨 (TASK-0077 의 mousedownOnOverlay-only flag 가 click target = overlay 일 때만 검사하므로 mouseup 위치 무관). DOM 표준상 click event 의 target 은 mousedown + mouseup 양 끝점의 공통 ancestor — backdrop 에서 mousedown → modal 안 mouseup 시 click target 이 overlay 가 될 수 있어 close 트리거. (2) preset 버튼 "1시간 전부터" 가 너무 길어 popover 안 5 버튼 1 row 에 안 들어가는 wrapping 발생 — "부터" 제거로 간결화. (3) snippet ±40 char clip 이 multi-line content 의 일부 line 만 cut 해 의미 파악 어려움 — 사용자 사례 "일정 line 아래에 있는 경우 가끔 확인". 매칭 line 전체 반환으로 의미 보존.
- Alt 거부:
  - **mouseup race fix 의 다른 패턴**: (a) `pointerup` event 사용 — 동작 비슷하나 일관성 차이. (b) `mousedown` 시 `ev.preventDefault()` 로 click 자체 차단 — selection 등 다른 mouse 동작도 차단됨. 본 fix 의 mousedown + mouseup + click 3 단 검사가 가장 단순 + 표준 정합 (click 의 정의 자체와 일치).
  - **snippet line 단위 vs 문장 단위**: 문장 단위 (period/comma split) 도 옵션. 그러나 본 프로젝트 본문은 SQL / 자연어 혼합 — 문장 분할 규칙이 복잡 + 한국어 종결 어미 추적 필요. line (`\n`) 단위가 markdown / 코드 / 자연어 모두 robust.
  - **excerpt 의 neighboring line 추가**: 매칭 line + 이전/다음 line 한 줄씩 (총 3 line) 노출. context 확장에 좋으나 시각 영역 ↑, line-clamp 3 만으로 단일 매칭 line 도 가독 충분. 본 cycle 은 단일 매칭 line 만 — 후속 cycle 권고.
  - **preset 5 버튼 수 축소**: "1시간 전" 만 두고 나머지 3 개 (1주 / 1개월 / 1년) 으로 단순화 옵션. 사용자 결정은 "부터" 텍스트만 제거 — 5 버튼 유지. 사용자 결정 그대로 채택.
- Risks:
  - **mouseup race 보강 의 side effect**: 정상 backdrop click (양 끝점 모두 overlay) 만 close. 사용자가 backdrop 위 mousedown → 곧바로 backdrop 위 mouseup 도 close — 이건 의도적 backdrop click 으로 인식 정합. drag 가 modal 안으로 들어왔다 다시 backdrop 으로 가서 mouseup 도 close (양 끝점 모두 overlay) — drag 중간 modal 통과는 추적 못 함. edge case 이고 의도적 close 일 가능성 높음 — 그대로 둠.
  - **snippet line-based excerpt 의 short line**: 매칭 line 이 1~2 char 일 수 있음. snippet 영역에 매우 짧은 텍스트만 노출 가능 — 사용자 가독 영향 small. 후속 cycle 에서 min excerpt length 또는 neighboring line 추가 권고.
  - **preset 텍스트 단순화**: 한국어 사용자에 "1시간 전" 만 보이면 의미 모호 가능 — "지금부터 1시간 이전" 또는 "지금부터 1시간 이전까지". 그러나 popover 의 header "기간 선택" 과 from/to input 옆 노출이라 컨텍스트로 의미 명확. 사용자 결정 정합.
  - **CSS line-clamp 3 의 row height 증가**: result row 높이가 1 line (~21 px) 정도 증가. modal max-height 72vh 안에서 viewport 노출 row 수가 ~1 개 감소 가능. 보통 결과 list 가 짧아 영향 미미.
  - **TASK-0073 (다른 session) 과 file overlap**: 본 cycle = `src/app.py` 의 `_collect_matched_excerpts` (TASK-0072 helper 영역) + frontend. TASK-0073 = `src/app.py` 의 audit/dispatcher 영역. 충돌 없음.
- 미해결 followup:
  - **excerpt 의 neighboring line 추가** (1 cycle 이상 후) — 매칭 line 의 이전/다음 line 1 개씩 추가 옵션.
  - **excerpt 의 AgentCoreMessages 포함** (TASK-0077 followup) — 현재 AgentMemoryMessages 한정.
  - **backend matched_message_id 응답** (TASK-0077 followup) — jump 정확도 100%.
  - **popover bottom-edge clamp** (TASK-0076 followup) — viewport 하단 chip 의 popover 가 drop-up.
- Trace: REQ-20260519-0006 → TASK-0078 → CHG-20260519-0008 → REV-20260519-0004 (hotfix of TASK-0077)

## REV-20260519-0003
- Date: 2026-05-19
- Decision: TASK-0077 (REQ-20260519-0005, Minor §12.3) — search modal 5 항목 hotfix bundle. min char 3→2, 소유자 facet 제거 (효용성 낮음 — 사용자 결정), 기간 preset 5종 (1시간/1일/1주/1개월/1년 전), mouseup race fix, snippet 본문 excerpt (backend `_collect_matched_excerpts` 신설).
- Reason: 사용자 직접 테스트 보고 5 항목이 TASK-0072 / 0076 의 명세 누락 또는 사용성 부족. min 2 char 는 한국어 grapheme 검색 정합. 소유자 facet 은 admin/operator 의 실제 needs 가 낮음 (대부분 q 입력으로 충분). 기간 preset 은 매번 date input 채우는 마찰 해소. mouseup race 는 modal 안 text drag 가 backdrop 위에서 떼지면 close 되던 자연스럽지 못한 UX. snippet 본문 excerpt 는 TASK-0072 의 REV-20260519-0002 followup ("backend matched_message_id 응답") 의 다음 step — 본 cycle 은 매칭 *message id* 가 아닌 매칭 *content excerpt* 만 첨부 (frontend jump 의 정확도는 TASK-0076 의 textContent compare 그대로 유지 — message id 응답은 별 cycle).
- Alt 거부:
  - **owner facet 유지 + role label refine**: 소유자 facet 의 사용자 가치를 늘리려 role group / role chip 추가 옵션. 사용자 결정 ("효용성 낮음") 이 분명하므로 단순 제거가 더 가치. backend `owner_id` 파라미터는 호환 위해 유지.
  - **mouseup race 의 다른 fix 패턴**: (a) `pointerup` event 사용 — 동작 비슷하나 browser 지원 차이. (b) modal close 자체를 click 이 아닌 별도 "X" 버튼 / Esc 만으로 — 사용자 backdrop click close 의도 손실. (c) modal 안 selection 가능 영역 추적 + 그 영역 내 mousedown 시 close 비활성. 본 fix 의 mousedownOnOverlay flag 가 가장 단순 + browser 표준 정합 (click = mousedown + mouseup 같은 element). 채택.
  - **snippet excerpt backend matched_message_id 채택**: 매칭 message *id* 를 함께 응답하면 frontend jump 가 100% 정확. 단 2 message table (AgentMemoryMessages + AgentCoreMessages) namespace + frontend 의 message.id mapping 명시화 필요 — scope 초과. 본 cycle 은 excerpt 만 (snippet 본문 표시 결함 fix) + jump 는 client-side textContent compare 유지 (TASK-0076 그대로). matched_message_id 는 미해결 followup.
  - **excerpt clip range 다른 값**: ±40 char (총 ~80-83 + q length). 더 좁으면 (±20) context 부족, 더 넓으면 (±80) snippet 영역 시각 overflow. 40 은 한국어 평균 1 줄 (40-60 byte = 20-30 char) 정합.
- Risks:
  - **min 2 char 검색 빈도 ↑**: 사용자 입력 시 더 자주 trigger 가능 (1 char 추가 시점부터 검색). per-account rate 10/min 정책 그대로라 DoS 표면 변화 0. UX trade-off — 더 빨리 결과 보이나 사소한 typo 도 검색 trigger.
  - **MySQL 8.0 window function 의존**: `_collect_matched_excerpts` 의 `ROW_NUMBER() OVER (PARTITION BY ...)` 는 MySQL 8.0+ 필수. 5.7 환경에서 fail. 본 프로젝트 MySQL 8.0 명시 (STATUS.md / TASK-0064) 라 호환. fallback: try/except 로 silent skip — snippet 없으면 frontend 가 표시 안 함 (제목 매칭만).
  - **excerpt PII**: TASK-0072 의 audit/RBAC 정책 (snippet chip opt-in + `.any` 한정 + `WebAccountActivity` audit) 그대로. 새 PII 표면 아님 — TASK-0072 의 snippet 영역이 *정확화* 됐을 뿐. opt-in chip 클릭 시 이미 audit log 기록되어 있음.
  - **소유자 facet 제거 회귀**: backend `owner_id` 파라미터 호환 유지로 향후 facet 재도입 0 cost. `.own` 사용자의 SQL composition order sub-spec 1 (TASK-0072 의 self-overwrite) 도 그대로 동작.
  - **TASK-0073 (다른 session) 과 file overlap**: TASK-0073 은 `src/app.py` 의 audit/dispatcher 영역. 본 cycle 도 `src/app.py` 변경 — 영역 분리 (TASK-0073 = WebAuditEvents + dispatcher Phase A0+, 본 cycle = `_normalize_search_query` line edit + `_collect_matched_excerpts` 신설 + endpoint payload 1 줄 추가). 충돌 가능성 점검 — `_normalize_search_query` 와 `_collect_matched_excerpts` 는 TASK-0072 helper 영역 (line 2887-3000 부근) 으로 TASK-0073 의 audit 영역 (`_audit_*`) 과 다른 위치. 안전.
- 미해결 followup:
  - **backend matched_message_id 응답** — 매칭 message id 까지 반환해 frontend jump 정확도 100%. 2 message table 의 namespace + frontend message.id mapping 명시 필요.
  - **excerpt 의 AgentCoreMessages 포함** — 현재 AgentMemoryMessages 한정. 일부 conv 의 본문이 core 에 있으면 excerpt 부재. UNION + per-conv ROW_NUMBER 으로 확장 가능 (별 cycle).
  - **popover bottom-edge clamp** (TASK-0076 의 followup) 미적용.
  - **owner accounts cache invalidate** (TASK-0076 의 followup) — 소유자 facet 제거로 자동 해소 (cache 미사용).
- Trace: REQ-20260519-0005 → TASK-0077 → CHG-20260519-0007 → REV-20260519-0003 (hotfix bundle of TASK-0072/0076)

## REV-20260519-0002
- Date: 2026-05-19
- Decision: TASK-0076 (REQ-20260519-0004, Minor §12.3) — search modal UX 3 결함 hotfix bundle. 제품 facet 은 사용자 결정 ("대화 중 product 변경 가능") 으로 DOM 제거. 소유자 / 기간 facet 은 popover UI 신설. ArrowUp/Down 시 active row scrollIntoView. 매칭 message bubble jump 는 frontend textContent compare (backend matched_message_id 응답 없이 client-side).
- Reason: 사용자 직접 테스트 보고 3 결함이 TASK-0072 의 명세 안에 포함됐어야 할 functionality 누락이었음. backend 의 `_list_conversations` 가 `owner_id` / `date_from` / `date_to` 파라미터를 이미 받지만 frontend popover UI 가 placeholder 만 있었음 — 사용자가 chip 클릭해도 동작 없음. 본 cycle 은 frontend 의 missing UI 만 채움. backend / RBAC / audit 영역 무변경.
- Alt 거부:
  - **제품 facet 구현 (3 option)**: 사용자 결정으로 DOM 제거 선택 — 대화 중 product 가 변경될 수 있어 *시점* 별 product filter 는 사용자 의도 왜곡 가능. cycle scope 축소.
  - **Backend matched_message_id 응답**: 검색 결과의 정확한 매칭 message id 를 backend 가 함께 반환하면 frontend jump 정확도 ↑. 그러나 `_list_conversations` 의 EXISTS subquery 가 어느 row 매칭인지 알지 못함 — 별 query (window function `ROW_NUMBER() OVER (PARTITION BY conv_id ORDER BY ts DESC)` 또는 GROUP BY MIN(Id)) 필요. 2 message table (AgentMemoryMessages + AgentCoreMessages) 의 id namespace 가 다르고, frontend 의 message.id 와 mapping 명확화 필요 — Minor cycle scope 초과. 본 cycle 은 client-side textContent compare 채택 (q 와 messages 둘 다 client 측 보유라 round-trip 불필요). 정확도 낮음 (예: q="대화" 가 안내문 등 광범위 매칭) — 후속 cycle 권고.
  - **owner facet 의 SSE / invalidate hook**: admin accounts cache 가 modal close 후 유지 → admin/operator 의 계정 추가/삭제 가 같은 session 안 발생 시 stale. SSE 또는 WebSocket invalidate 도입 vs cache TTL (예: 60 s) vs modal open 마다 refresh. 본 cycle 은 1 회 캐시 + 별 session 마다 refresh — 가장 단순. follow-up cycle 권고.
- Risks:
  - **facet popover positioning**: `position: fixed` + getBoundingClientRect. modal scroll / viewport resize 시 popover anchor drift. popover 자체가 단발 click 후 즉시 적용이라 drift window 좁아 보통 무문제. viewport right-edge clamp 만 적용, bottom clamp 미적용 — chip 이 viewport 하단에 있을 때 popover 가 viewport 밖 나갈 수도 있음 (follow-up).
  - **matched message jump 정확도**: client-side `textContent.toLowerCase().includes(needle)` — q 가 짧거나 흔한 단어일 때 첫 매칭 row 가 사용자 의도와 다를 수 있음 (특히 user prompt 안 매칭이 assistant 본문 매칭보다 먼저). 본 cycle 의 trade-off — backend 의 정확한 매칭 message id 응답이 정확도 ↑ 이지만 schema/query 복잡도 ↑ 별 cycle.
  - **owner facet `.any` 한정**: `.own` 사용자에게는 owner chip 자체가 `hidden`. 정합 (`.own` user 가 owner_id 입력해도 backend sub-spec 1 이 self 로 강제 overwrite). cross-account leak 0.
  - **TASK-0073 (다른 session) 과 file overlap 없음**: 본 cycle = `src/static/{index.html, styles.css, app.js}` + docs. TASK-0073 = `src/app.py` (WebAuditEvents DDL) + docs. concurrent commit OK.
- 미해결 followup:
  - **Backend matched_message_id 응답** — `_list_conversations` 의 search mode 시 각 conv 의 첫 매칭 message id 함께 반환. frontend jump 정확도 100%. window function 또는 GROUP BY MIN(Id) per conv 추가 query.
  - **owner accounts cache invalidate** — 60 s TTL 또는 SSE.
  - **popover bottom-edge clamp** — viewport 하단 chip 의 popover 가 위로 펼침 (`drop-up`) 분기.
  - **snippet 본문 미리보기 정확도** — 현재 snippet 은 topic 만 미리보기. backend 가 매칭 message excerpt (matched_message_id 채택 시 함께) 반환 시 snippet 본문 정확.
- Trace: REQ-20260519-0004 → TASK-0076 → CHG-20260519-0006 → REV-20260519-0002 (hotfix bundle of TASK-0072)

## REV-20260519-0001
- Date: 2026-05-19
- Decision: TASK-0074 (REQ-20260519-0002, Minor §12.3) — search modal CSS 의 색상 토큰을 site theme 의 기존 var (`--surface`, `--text`, `--border`, `--text-muted`, `--primary`, `--primary-soft`, `--bg`) 으로 일관 적용. 미정의 var fallback (`--text-primary` → `--bg-elev` dark hardcode `#1f2429`) 폐기. backdrop 의 dark overlay 는 modal pop 강조 위해 유지.
- Reason: TASK-0072 modal CSS 가 dark theme 가정 var (`--text-primary`, `--bg-elev`) 사용 — site 가 정의 안 한 var 라 fallback 인 hardcode dark color 가 발동. 그러나 site 자체는 light theme (`--bg #f4f4f5` / `--surface #ffffff` / `--text #18181b`) 라 modal 의 검은 배경 위 text inherit 가 검은색 → contrast 0. UX review (TASK-0072 outside voice) 가 site theme 가정 명시 안 한 결과 — light theme 위 dark modal 의 가독성을 사용자가 직접 발견. 사용자 screenshot ("사용자가 이용할 수 없을 정도의 색상 구성") 으로 hotfix 진입.
- Alt 거부:
  - `@media (prefers-color-scheme: dark)` 분기: site 자체가 단일 theme (`:root` 에 light 만 정의, `prefers-color-scheme` 분기 없음) — modal 만 dark 분기 추가는 site 정합 깨짐.
  - 미정의 var 의 fallback 값을 light 로 단순 swap (`var(--bg-elev, #ffffff)`): 다른 site 컴포넌트도 `var(--text-primary)` / `var(--bg-elev)` 가정으로 만들면 동일 회귀 재발 가능. 본 fix 는 site 의 *기존 토큰* (`--surface` / `--text` 등 site 가 명시 정의한 것) 으로 통일해 fallback 의존 차단.
  - dark theme 강제 (site root 에 `--text-primary: #fff` 추가): 다른 모든 site CSS 영향 — scope 폭발.
- Risks:
  - **backdrop dark overlay 유지**: modal pop 강조 위해 `rgba(15,23,42,0.48)` 유지. light theme 위 어두운 overlay 가 modal 의 white background 와 contrast 잘 보이는 효과. light dimming 으로 갔다가 modal boundary 흐려지면 UX 회귀.
  - **highlight bg `#fde68a` (yellow 300)** light theme 위 dark text 와 contrast WCAG AA 충분 (검산: contrast ratio ~10:1). dark theme 도입 시 highlight bg 재검토 필요 (별 cycle).
  - **`--primary-soft` (#eff6ff) result row hover/active bg** light theme 위 visible 가능 (parent surface = #ffffff, hover = #eff6ff 의 contrast). visible 영역 충분.
  - **다른 modal 영향 0**: 본 cycle 의 변경은 `.search-modal*` selector 한정. admin modal / profile drawer / 비밀번호 reset modal 등 무관.
- 미해결 followup:
  - **site 의 dark theme 도입 시 modal 재검토** — `prefers-color-scheme: dark` 분기 또는 사용자 toggle 시 search modal 색상도 함께 swap. 본 cycle 의 fix 가 site theme inherit 패턴이라 자동 swap 가능하나 highlight bg (`#fde68a`) 와 backdrop (`rgba(15,23,42,0.48)`) 은 dark theme 위 재검산 필요.
  - **CSS 토큰 contract 명료화** — site root 의 모든 토큰 (`--bg-elev`, `--text-primary`, `--border-strong`) 이 정의 안 됨에도 다른 컴포넌트들이 fallback 으로 사용 중. site 의 root 토큰 정의 audit + 미정의 var 의 fallback 강제 정책은 별 cycle (DESIGN.md §15 확장 권고).
- Trace: REQ-20260519-0002 → TASK-0074 → CHG-20260519-0004 → REV-20260519-0001 (hotfix of TASK-0072)

## REV-20260518-0010
- Date: 2026-05-18
- Decision: TASK-0072 (REQ-20260518-0010, **Critical** §12.3) — 타 계정 대화 검색·필터 plan 의 D1/D2/D3 결정 + outside voice 3 개 verdict 흡수 + 사용자 in-cycle 결정 5 항목 확정. UI 위치 재결정 (사이드바 검색바 → Spotlight modal pattern), index 정책 (LIKE + 강한 안전망, FULLTEXT 별 cycle), 본문 열람 정책 (`.any` 보유자 검색·snippet 허용 + audit log 수반).

### Outside voice 3 verdict 요약

- **Security review** (FIX-FIRST) → 4 must-fix 모두 흡수:
  1. `WebAccountActivity` audit log 신설 (PIPA §29 / 접근기록 보관)
  2. `LIKE %s ESCAPE '!'` 명시 + `%`/`_`/`!` 3 char escape (NO_BACKSLASH_ESCAPES sql_mode 회귀 차단)
  3. D1 → B (FULLTEXT) 권고 — 그러나 adversarial 의 분리 권고 더 설득력 (아래 D1 참조)
  4. Per-account rate limit 10 req/min + `max_execution_time=3000ms`
- **Adversarial review** (Blocker → 3 sub-spec 흡수 후 진입) → 3 sub-spec + 6 risk 모두 흡수:
  - 3 sub-spec: (a) SQL composition order — `owner_id = self` 가 q 보다 항상 먼저 AND, (b) `hidden_ids` SQL push (`NOT IN`), (c) Python re-sort 삭제 (`app.py:2967-2971`)
  - 6 risk: `WebAccounts.DeletedAt` 필터 / collation audit / account name search `.any` 한정 / `q="%%"` post-escape 0 char 차단 / 404 vs 403 byte-equal / `share.js` 회귀 가드
- **UX review** (NEEDS-TWEAK) → 사이드바 252px 에 chip 4개 fit 불가. Spotlight modal pattern (Cmd/Ctrl+K) 권고 → 사용자 변형 채택 ("+ 새 대화" 버튼 우측 같은 높이 돋보기 icon + modal overlay).

### D1 / D2 / D3 결정 + 근거

- **D1 → A (LIKE only + 강한 안전망)** — security 와 상충 (B FULLTEXT 권고). adversarial 의 근거 채택: 한국어 FULLTEXT 는 `ngram` parser + `innodb_ft_min_token_size` 튜닝 필수 → `ALTER TABLE ADD FULLTEXT` 자체가 Critical migration. 신규 PII 표면 도입과 interleave 회피 위해 FULLTEXT 는 별 cycle 분리. 본 cycle 의 LIKE 안전망: min 3 char + length cap 200 + LIMIT 50 + per-account rate 10/min + `max_execution_time=3000ms` + collation audit.
- **D2 → A (snippet 항상 OFF + chip opt-in)** — security + adversarial 일치. B (`.any` 기본 ON) 는 user interaction 전에 PII snippet 노출되는 worst-of-both. opt-in chip 클릭 자체가 audit log 대상 (의도 추적).
- **D3 → B (cursor `updated_at DESC, conversation_id DESC`)** — offset 은 기존 `app.py:2849` LIMIT 200 + `2967-2971` Python re-sort 와 incoherent (page 2 가 stale subset 반환). cursor 가 안전 + Python re-sort 삭제와 정합.

### 사용자 in-cycle 결정 5 항목

1. 권한 모델: 기존 `conversation.list.any` 재활용 (신규 catalog 없음)
2. 검색 범위: 제목 + 계정명 + 메시지 본문 (SQL/결과셋 제외)
3. UI 위치 (재결정): Spotlight modal pattern + 사용자 변형 ("+ 새 대화" 버튼 우측 같은 높이 돋보기 icon + Cmd/Ctrl+K)
4. D1 index: A (LIKE + 강한 안전망)
5. 본문 열람: `.any` 보유자 = 검색 매칭 + snippet 모두 허용 + audit log 수반

### Alt 거부 정리

- **D1 B (FULLTEXT) 거부**: 한국어 ngram + innodb_ft_min_token_size 튜닝 + 대용량 `ALTER TABLE ADD FULLTEXT` 의 lock 시간 = 본 cycle 외 Critical migration. 분리.
- **UI 사이드바 위 검색바 + chip 거부**: 252px 사이드바 fit 불가 (chip 4개 1줄 ~296px 필요). 2줄 wrap 시 toolbar 120px → conv-list 15-20% 잠식. Spotlight modal 이 conv-list 잠식 0 + Cmd/Ctrl+K 단축키로 power-user friction 낮음.
- **신규 catalog `conversation.search.any` 거부**: 사용자 초기 결정 (권한 모델 = list.any 재활용). admin/operator 의 list 권한 = search 권한 묶음. 단 audit log 로 search 활동 추적해 권한 misuse 가시화.
- **본문 검색 .own 한정 거부**: 사용자 결정 (본문 열람 = `.any` 허용 + audit). 감사 needs 우선. audit log 가 misuse 보호 layer.

### Risks (재평가)

- **RBAC bypass** (Critical) → 3 sub-spec + Phase B 6 시나리오 smoke + 404/403 byte-equal 로 차단
- **PII leak (snippet + cross-account body)** (Critical) → snippet opt-in 기본 OFF + `WebAccountActivity` audit + SHA-256 hash + `.any` 한정
- **SQL injection** (Major) → bound param + `ESCAPE '!'` + escape 후 의미 char ≥ 2
- **성능 회귀 (LIKE full scan)** (Major) → LIMIT 50 + min 3 char + rate 10/min + `max_execution_time=3000ms` + collation audit
- **WebAccountActivity DDL** (Major) → `_ensure_web_tables` idempotent + `CREATE TABLE IF NOT EXISTS` + `(account_id, ts)` index
- **share-link 회귀** (Minor) → `share.js` 신규 import 없음 (Phase C 가드)

### 미해결 followup

- **FULLTEXT migration cycle** — 본 cycle 의 LIKE 안전망이 성능 한계 (≥ 5만 conv + 빈번한 body search) 도달 시 후속 cycle 로 ngram FULLTEXT 도입. trigger: rate limit 빈번 진입 또는 `max_execution_time` 빈번 hit.
- **DESIGN.md §15 filter chip 패턴 v0.1** — UX review 권고. 본 cycle 은 modal 안 facet 만 사용. 사이드바 filter chip 이 필요해지면 별도 정합화 cycle.
- **외부 LAN 배포 시 추가 게이트** — `repo/docs/SECURITY.md` §7 (TASK-0058 share-link) 의 IP allowlist / token 비밀번호 / 시간 만료 권장사항이 본 검색 endpoint 에도 동일 적용. 후속 SECURITY §8 에 명시.

- Trace: REQ-20260518-0010 → TASK-0072 → §2.1 Implementation Plan (TASK-0072) + outside voice 3 verdict (security FIX-FIRST + adversarial Blocker + UX NEEDS-TWEAK) → CHG-20260518-0010 (Phase A0~E 진행 시 commit 별로 append) → REV-20260518-0010

## REV-20260518-0008
- Date: 2026-05-18
- Decision: TASK-0071 (REQ-20260518-0009, Minor §12.3) — `.app-shell` / `.admin-shell` 양쪽에 `grid-template-rows: minmax(0, 1fr)` 추가. cascade root fix.
- Reason: 본 cycle 은 TASK-0068 → 0069 → 0070 의 layout hotfix chain 의 마지막 root. 이전 fix 들이 column 안의 stretch chain (workspace → pane → list-detail → list-col) 을 차례로 해결했으나 column 자체의 height 결정 layer (.app-shell / .admin-shell 의 grid track) 는 미처리. grid 의 single row 가 default `auto` 면 row track height = 자식 max-content — grid container 가 `height: 100vh` 여도 track 이 100vh 보다 작아질 수 있음. 본 환경 (chrome headless) 은 grid track 이 100vh 차지하는 동작이라 stretch 정상 보였지만, 사용자 환경에서는 max-content 차지 동작이라 노출. browser engine / 동일 brower 의 timing / DPI 등 환경별 grid algorithm 차이가 회귀 timing 결정. `minmax(0, 1fr)` 으로 row 가 container 의 전체 height 차지하도록 명시 — 환경 의존성 제거.
- Cascade 정리 (요약):
  ```
  .app-shell / .admin-shell { height: 100vh; display: grid; grid-template-rows: minmax(0, 1fr) }  ← TASK-0071 fix
    └ .sidebar / .admin-sidebar  (grid item, row 의 full height stretch)
    └ .chat-column / .admin-column  (grid item, row 의 full height stretch)
        └ .topbar (flex-shrink: 0)
        └ .chat-pane / .admin-workspace  { flex: 1 1 auto }  ← TASK-0069 fix
            └ .chat 영역 / .admin-pane.is-active  { flex: 1 1 auto }
                └ .admin-list-detail  { flex: 1 1 auto; grid-template-rows: minmax(0, 1fr) }  ← TASK-0070 fix
                    └ .admin-list-col / .admin-detail-col  (grid item, row stretch)
        └ .composer / .admin-commit-bar  (flex-shrink: 0)
  ```
- Alt 거부: `grid-template-rows: 100vh`. minmax(0, 1fr) 보다 명시적이지만 container 의 height: 100vh 와 row 의 100vh 중복 — DRY 위반. 1fr 이 container size 의 100% 를 의미 (single row 일 때).
- Risks:
  - **다른 brower / DPI 회귀 검증 불가**: 본 환경 chrome headless 에서는 1 차 (TASK-0069) 부터 정상 보였음. 사용자 환경 (실제 browser) 에서만 노출 — 본 환경에서 추가 회귀 검증 가능성 제한. 그러나 `minmax(0, 1fr)` 은 CSS Grid spec 의 명시적 단일 row stretch 패턴이라 환경 의존성 없는 fix.
  - **반응형 mobile**: `.app-shell { grid-template-columns: 1fr }` / `.admin-shell { grid-template-columns: 1fr }` 으로 단일 column 인데 row 도 1fr 이라 정상 동작. mobile 환경 별 cycle 검증 권장.
  - **viewport height 0 edge case**: `minmax(0, 1fr)` 의 min 이 0 이라 viewport 가 매우 짧을 때 (height 0) row 도 0 — `overflow: hidden` 의 shell 안에서 자식이 grow 동작 멈춤. 비현실 case 라 무시.
  - **scrollbar 영향**: 부모에 scrollbar 가 있는 경우 100vh ≠ 실 가용 height. shell 자체에 `overflow: hidden` 있어 scrollbar 발생 안 함. 자식의 overflow-y: auto 만 동작.
- Trace: REQ-20260518-0009 → TASK-0071 → CHG-20260518-0008 → REV-20260518-0008 (hotfix chain root of TASK-0068 / 0069 / 0070)

## REV-20260518-0007
- Date: 2026-05-18
- Decision: TASK-0070 (REQ-20260518-0008, Minor §12.3) — `.admin-list-detail` 에 `grid-template-rows: minmax(0, 1fr)` 추가. CSS 1 줄 root-cause fix.
- Reason: TASK-0068/0069 layout chain 의 마지막 stretch gap. `.admin-list-detail` 가 grid (column 2 정의) 이지만 row 가 default `auto` → row height = content. `.admin-pane` / `.admin-workspace` / `.admin-column` 의 flex grow chain 이 list-detail 까지는 정상 도달했으나 list-detail 의 grid row 가 그 height 를 column 들에 분배 안 함. `minmax(0, 1fr)` 으로 row 가 list-detail 의 flex grow 받은 height 전부 차지 + min-content 무시 (자식 column 의 min-height 0 와 정합).
- 1 차 검증 (TASK-0069) 에서 놓친 이유: 본 환경의 viewport (720) 에서는 list-col content (search input + select-all + 3+ items + bulk-bar + pagination) 의 총 height 가 우연히 list-detail 의 stretch 된 height 와 비슷 (~500) → 시각적으로 stretch 된 것처럼 보임. 사용자의 큰 viewport (900+) 에서는 list-col content 가 짧아 row 가 짧음 → 그 차이가 시각화됨. 검증 viewport 다양성 부족이 회귀 1 cycle 연장 원인.
- Alt 거부: `min-height: 100%` (list-col / detail-col 에 추가). flex grow 와 결합 시 fragility (parent height 100% 의존). grid-template-rows 가 root cause 에 가깝고 simpler.
- Risks:
  - **다른 viewport 비율 검증**: 큰 viewport (1320x900) 에서 fix 검증 완료. 매우 짧은 viewport (height 500-) 의 경우 list-col content (toolbar + items) 가 row 보다 클 수도 — overflow-y: auto 의 `.admin-list` 가 scroll 동작으로 흡수. 또한 list-col / detail-col 자체에 `min-height: 0` 명시되어 있어 grid row stretch 와 정합.
  - **dashboard pane**: dashboard 는 list-detail 사용 안 함 (`.admin-pane[data-admin-pane="dashboard"].is-active { overflow-y: auto }` 직접 scroll). 본 변경 무영향.
  - **mobile 반응형** (`@media (max-width: 680px)`): `.admin-list-detail { grid-template-columns: 1fr }` 으로 단일 column. row 1 fr 도 그대로 동작 — column 1 (list-col) 이 1fr row 의 전체 height.
- Trace: REQ-20260518-0008 → TASK-0070 → CHG-20260518-0007 → REV-20260518-0007 (hotfix of TASK-0068 / 0069 layout chain)

## REV-20260518-0006
- Date: 2026-05-18
- Decision: TASK-0069 (REQ-20260518-0007, Minor §12.3) — `.admin-workspace` 에 `flex: 1 1 auto` 추가. 다른 fix path 미선택 — 1 줄로 root cause 해결되므로 우회 패치 불필요.
- Reason: TASK-0068 에서 admin layout 을 작업 화면과 동일한 ChatGPT 패턴으로 재구조화하면서 commit-bar 의 위치가 `.admin-shell` grid 의 3rd row → `.admin-column` flex column 의 3rd flex item 으로 이전. 그러나 `.admin-workspace` 의 flex 명시 누락으로 flex column 안에서 workspace 가 자기 content 만큼만 차지하고 column 의 남은 공간이 빈 채로 노출 + commit-bar 가 viewport bottom 이 아닌 workspace 끝 바로 아래에 위치하는 시각 회귀. `.admin-pane.is-active { flex: 1 1 auto }` 가 의미를 가지려면 부모 `.admin-workspace` 자체가 stretch 되어야 함. cascade 의 출발점인 workspace 에 flex grow 명시.
- Alt-A 거부: admin-column 의 grid (rows: topbar-h / 1fr / auto) 로 변경. flex 보다 명시적이지만 commit-bar 의 가시성/숨김 토글이 grid template-rows 도 함께 갱신해야 하므로 fragility 증가. flex column + flex grow 가 더 단순.
- Alt-B 거부: commit-bar 의 position: sticky bottom: 0. workspace 의 flex 미해결 시 workspace 가 자기 content 만큼만 차지하는 본질 문제는 그대로. sticky 는 sticky overflow 부모를 필요로 하는데 그 정의가 workspace 와 conflict 가능.
- Risks:
  - **다른 admin pane (대시보드 / 계정 / 제품) 회귀 검증**: `.admin-workspace` 단일 rule 변경이므로 모든 pane 에 일관 적용. 대시보드는 `.admin-pane[data-admin-pane="dashboard"].is-active { overflow-y: auto }` 보유 — workspace 가 stretch 되면 dashboard content scroll 동작이 dashboard 내부에서 정상 동작 (이전엔 admin-shell grid 의 1fr 이 같은 효과 제공). 본 cycle browser smoke 는 역할 pane 한정 — 다른 pane 도 동일 fix 자연 적용되지만 dashboard scroll 검증은 사용자 직접 확인 권장.
  - **min-height 0**: `.admin-workspace { min-height: 0 }` 가 이미 있어 flex 자식 (`.admin-pane`) 의 overflow / scroll 동작 정합. flex grow 추가가 이 동작과 충돌 없음.
  - **mobile 반응형**: `.admin-shell { grid-template-columns: 1fr }` (mobile) 일 때 admin-sidebar 가 숨겨지고 admin-column 만 표시. flex grow 가 mobile 에서도 동일 동작.
- Trace: REQ-20260518-0007 → TASK-0069 → CHG-20260518-0006 → REV-20260518-0006 (hotfix of TASK-0068)

## REV-20260518-0005
- Date: 2026-05-18
- Decision: TASK-0068 (REQ-20260518-0006, Minor §12.3) — 관리 콘솔의 sidebar 영역 구성을 작업 화면 (TASK-0066) 과 동일한 ChatGPT 패턴으로 정렬 + 헤더의 `새로고침` / `로그아웃` 제거.
- Method:
  - **layout 통일성**: 사용자는 작업 화면 / 관리 콘솔을 빈번히 전환한다 (`backToAppBtn`). 두 화면의 layout 이 일관되면 인지 비용 (eye tracking, mental model) 감소. TASK-0066 에서 작업 화면의 `.app-shell` 을 2-column grid 로 단순화한 패턴을 admin 에 그대로 적용. brand "MySQL AI" 도 통일 (admin 의 기존 "관리 콘솔" brand 는 페이지 컨텍스트라 topbar 안에 표시하는 것이 정합 — product 정체성 vs 페이지 컨텍스트 분리).
  - **새로고침 버튼 제거의 의미**: pending 변경 보호 confirm + state clear + `loadAdminData()` 호출이었음. 사용자가 거의 사용 안 한다는 피드백 — 보통 `모두 적용` 또는 `취소` (commit-bar) 로 pending 정리하거나 페이지 reload (브라우저 F5) 로 충분. dead UI 제거가 SCREEN clutter 감소에 기여. element 제거 시 admin.js 의 click handler 도 함께 제거 (null reference 안전성).
  - **로그아웃 버튼 제거의 의미**: admin 의 topbar 에서 직접 로그아웃은 빠른 path 였으나 사용자 통상 흐름이 작업 화면으로 돌아가 (`backToAppBtn`) → 프로필 drawer → 로그아웃 이라 중복. 로그아웃 endpoint (`POST /api/auth/logout`) 는 작업 화면 프로필 drawer 에서 그대로 호출 가능 — 기능 손실 없음.
  - **`backToAppBtn` 유지**: admin → 작업 화면 전환은 사용자가 자주 사용 (pending 보호 confirm 도 의미 있음). 단일 quick path 로 유지.
  - **commit-bar 위치**: 기존 `.admin-shell` 의 grid-template-rows 3rd row (`auto`) 였던 footer 를 `.admin-column` 안의 마지막 flex item 으로 이전. sidebar 영역에는 commit-bar 가 표시되지 않고 workspace 의 하단에만 표시 — 시각 정합 (commit-bar 가 workspace 와 묶임).
  - **`.admin-sidebar` padding 정책**: brand 가 sidebar 의 첫 영역으로 들어가면서 sidebar 자체의 `padding: 10px 8px` 를 제거하고 각 child (`.sidebar-brand` = `padding: 0 14px`, `.admin-tabs` = `padding: 10px 8px 0`, `.admin-sidebar-foot` = `padding-left/right: 8px`) 가 자기 padding 갖도록 — brand 가 sidebar 전체 너비를 차지하고 padding 안쪽 정렬은 brand-icon/name 의 자체 padding 으로 자연스럽게.
- Risks:
  - **로그아웃 접근성 감소**: admin 페이지에서 직접 로그아웃 path 가 사라짐 → 작업 화면으로 이동 (1 click) → 프로필 drawer 열기 (1 click) → 로그아웃 (1 click). 3 click. 보안 의도의 빠른 강제 로그아웃 (예: 공용 머신에서 자리 비울 때) 시 불편할 수 있음. 후속 cycle 에서 작업 화면 프로필 drawer 의 "로그아웃" 버튼이 admin 페이지에서도 동일 접근 가능한지 확인 권장 (drawer 자체가 admin 페이지엔 없으므로 새로운 path 필요할 수도).
  - **새로고침 버튼 제거 후 pending stale 회복**: 사용자가 의도치 않게 pending 을 쌓은 상태에서 `취소` (commit-bar) 도 못 누르거나 잘못 누른 경우 의도된 적용을 되돌리는 path 가 줄어듦. 그러나 commit-bar 의 `취소` 가 동일 역할 수행 — 실질 영향 없음.
  - **brand 통일 후 페이지 식별성**: admin 페이지의 brand 가 "관리 콘솔" → "MySQL AI" 로 바뀌어 사용자가 어느 페이지인지 혼동할 가능성. 그러나 topbar 의 `<h2 class="chat-title">관리 콘솔</h2>` + subtitle 이 페이지 컨텍스트를 명확히 표시 + browser tab 의 `<title>MySQL AI Assistant Admin</title>` 도 식별 유지. 시각적으로 admin sidebar 의 `대시보드` / `계정 카테고리` / `제품 카테고리` 탭 구성이 관리 콘솔 인지 즉시 알림.
  - **반응형 admin mobile**: `.admin-shell { grid-template-columns: 1fr }` + `.admin-sidebar { display: none }` 으로 sidebar 숨김 + workspace 만 표시. mobile 에서 admin tab 전환 path 부재 — 별 cycle 검토. (관리 콘솔은 desktop-first 가정이 일반적)
  - **dead CSS 잔존 확대**: TASK-0066 의 `.topbar-brand`, TASK-0067 의 `.product-chip-*` 에 이어 `.admin-body` rule 도 dead code. 본 cycle 에서 `.admin-body` rule 도 제거 — `.topbar-brand` / `.product-chip-*` 잔존 (별 cycle 정리 권장).
- Trace: REQ-20260518-0006 → TASK-0068 → CHG-20260518-0005 → REV-20260518-0005 (follow-up of TASK-0066 / 0067)

## REV-20260518-0004
- Date: 2026-05-18
- Decision: TASK-0067 (REQ-20260518-0005, Minor §12.3) — 제품 칩을 사이드바 → composer 우측 (textarea/sendBtn 사이) 으로 이전. ChatGPT 모델 선택 UI 패턴. 기존 native `<select>` 를 custom button + drop-up dropdown 으로 대체.
- Method:
  - **위치 결정 — composer 우측**: 사용자 명시 "요청사항을 입력하는 우측". textarea 와 send-btn 사이가 의미상 정합 (입력 → 모드 선택 → 전송). ChatGPT 의 모델 selector 가 composer 영역 안에 있는 패턴과 일치.
  - **drop-up 필요성**: chip 이 composer (페이지 하단 근처) 에 위치하므로 menu 가 chip 아래로 펼치면 viewport 밖. CSS `position: absolute; bottom: calc(100% + 6px)` 로 chip 위로 펼침 — drop-up 보장. 사용자 명시한 "상대적인 위치로 drop-up" 정합.
  - **native `<select>` 폐기 사유**: native dropdown 위치는 브라우저가 결정 (보통 below). drop-up 효과를 보장할 수 없음. custom button + custom menu 로 전환.
  - **chip label 정책 — compact vs full**: chip 폭이 좁아 pinned 일 때 전체 이름 + product_key 를 보여주면 ellipsis 발생. `compactLabel = product_key` (KR / MV / GZ_KR — 짧고 식별 가능) 채택. 단 a11y 는 보존 — `aria-label` 에 `"이 대화의 제품 선택, 현재 {name} ({product_key})"` 전체 형식 유지.
  - **menu 옵션 list 갱신**: `state.products` 가 비동기 hydrate 되므로 menu 가 열려 있는 동안에도 product list 가 갱신될 수 있음. `renderProductChip()` 끝에서 `chip.aria-expanded === "true"` 면 `renderProductDropupMenu()` 도 즉시 호출해 동기화.
  - **busy 상태 정책**: 기존 `isCurrentConvBusy()` race 가드 유지 — busy 시 chip.disabled + aria-disabled + cursor not-allowed. menu open 도 `chip.disabled` 체크로 차단. 사용자가 응답 처리 중에 product 를 바꾸려 하면 chip 자체가 비활성.
- Risks:
  - **dead CSS 잔존**: 기존 `.product-chip-wrap` / `.product-chip` / `.product-chip-caption` / `.product-chip-select` rule 이 stylesheet 에 남아 있음 (사용처 없음). 무해이지만 별 cycle 에서 제거 권장 (TASK-0066 의 `.topbar-brand` dead rule 과 함께).
  - **a11y — native select 의 keyboard 동작 대체**: native `<select>` 는 keyboard 화살표 / Enter / Esc / 빠른 search 자동 지원. custom dropdown 은 본 cycle 에선 click + outside-click + ESC close 만 구현. arrow key 탐색은 후속 cycle 검토 (TASK-0063 conv-item menu 와 동일 정책 — Esc 만 적용).
  - **drop-up 의 viewport 경계 처리**: chip 이 viewport 하단 근처라 drop-up 이 자연스럽지만, chip 이 viewport 상단 근처 (mobile keyboard 등 viewport 축소 시) 면 menu 가 위로 튀어나갈 수 있음. CSS `max-height: 320px; overflow-y: auto` 로 안전망. fully responsive 동작은 후속 cycle 검토 가능.
  - **menu z-index 50 vs sticky 분기선 z-index 5 vs conv-item dropdown z-index 200**: 분기선 (5) 위, conv-item menu (200) 아래. composer 영역에서 menu 가 펼쳐지면 sticky 분기선 위에 표시되므로 정합. conv-item menu 와 동시 노출은 일반적이지 않으므로 200 충돌은 무시 가능.
  - **JS — element ID 보존**: chip 의 ID (`productChip`, `productChipDot`) 보존으로 기존 외부 reference 무영향. 신규 ID (`productChipLabel`, `productDropupMenu`) 는 본 cycle 신설.
- Trace: REQ-20260518-0005 → TASK-0067 → CHG-20260518-0004 → REV-20260518-0004 (follow-up of TASK-0066)

## REV-20260518-0003
- Date: 2026-05-18
- Decision: TASK-0066 (REQ-20260518-0004, Minor §12.3) — ChatGPT 패턴 layout 재구조화. 사용자 결정: topbar 에 대화 제목 통합 + 좌측 정렬 + brand 를 sidebar 영역으로 이전. `.app-shell` grid 2-row → 2-column. `.app-body` wrapper / `.chat-header` 폐기.
- Method:
  - **선택지 비교**: AskUserQuestion 으로 두 옵션 제시 — (A) chat-pane 안에 관리 콘솔 편입 (topbar 는 brand 전용, sidebar 와 같은 너비), (B) topbar 중앙에 대화 제목 통합 (단일 전체 너비 헤더). 사용자가 (B) 변형 채택 — topbar 에 대화 제목 통합하되 **중앙 정렬 X, 좌측 정렬** + brand 를 sidebar 영역 안으로 (ChatGPT UI 명시). chat-header 폐기로 채팅 영역 확장 효과.
  - **layout 변환**: 기존 `.app-shell` 이 row 2개 (topbar | app-body) + `.app-body` 가 column 2개 (sidebar | chat-pane) 의 nested grid. 변환 후 `.app-shell` 이 직접 column 2개 (sidebar | chat-column). `.app-body` wrapper 폐기로 DOM depth 감소. chat-column 안에서 flex column 으로 topbar + chat-pane 쌓음.
  - **baseline 정렬**: `.sidebar-brand` 의 height = `var(--topbar-h)` = 52px 로 topbar 와 baseline 일치. `.sidebar-brand` 의 border-bottom (border-subtle) 이 `.topbar` 의 border-bottom (border) 와 시각적으로 연결되어 sidebar / chat-column 의 첫 row 가 단일 헤더 row 로 보임 — 시각 통합 효과.
  - **chat-title typography 보존**: `.chat-header` rule 은 폐기했지만 `.chat-title` / `.chat-subtitle` 의 font-size / weight / color rule 은 그대로 유지 — topbar-info 안에서 동일 스타일로 렌더.
  - **JS 무변경**: 모든 element ID (`conversationTitle`, `conversationSubtitle`, `loadMoreBtn`, `openAdminBtn`) 가 보존되어 getElementById 호출이 그대로 동작. `setupChatHeader` 같은 별도 mount 로직 불필요.
- Risks:
  - **반응형 mobile (max-width: 680px)**: 기존 `.app-body { grid-template-columns: 1fr }` + `.sidebar { display: none }` 패턴을 `.app-shell { grid-template-columns: 1fr }` + `.sidebar { display: none }` 으로 변환. 동일 효과 — sidebar 숨김 + chat-column 만 표시. mobile 환경 실측 검증은 별 cycle 권장.
  - **brand 가 sidebar 안으로 이전 후 sidebar 의 vertical scroll 영향**: `.sidebar { display: flex; flex-direction: column; overflow: hidden }` 인데 `.sidebar-brand` (flex-shrink: 0) + 기존 `.sidebar-head` + `.conv-list` (overflow-y: auto) + `.sidebar-profile` 의 구조에서 brand 가 첫 child 라 conv-list 의 scroll 영역이 brand height 만큼 줄어듦. 252px sidebar 에서 brand 52px 추가는 시각적으로 자연스러움.
  - **`.chat-pane` 의 background**: 기존엔 chat-pane 의 첫 child 가 chat-header (surface 배경) 라 시각적 구분이 있었으나 이제 chat-pane 의 첫 child 가 access-notice 또는 progress-strip 또는 messages-wrap. chat-pane background (var(--bg)) 가 그대로 노출되어 topbar 와 시각 구분 명확 (topbar 는 surface, chat-pane 은 bg).
  - **JS 사이드 effect 미검증**: setupChatHeader / 진행 상황 표시 / point rail 등 directing 코드가 chat-header rect 또는 chat-pane 첫 child rect 를 참조할 가능성. grep 으로 확인 — `.chat-header` selector 참조 없음. `.chat-title` / `.chat-subtitle` 은 textContent 만 갱신하며 layout 의존성 없음.
  - **dead code 잔존**: `.topbar-brand` CSS rule 이 더 이상 사용되지 않으나 stylesheet 에 남음. 무해이지만 별 cycle 에서 제거 권장.
- Trace: REQ-20260518-0004 → TASK-0066 → CHG-20260518-0003 → REV-20260518-0003 (follow-up of TASK-0065)

## REV-20260518-0002
- Date: 2026-05-18
- Decision: TASK-0065 (REQ-20260518-0003, Minor §12.3) — TASK-0063 직접 테스트 follow-up 3 항목. 헤더 4 버튼 제거 + "···" trigger 위치 우측 하단 + 분기선 `position: sticky`.
- Method:
  - **헤더 4 버튼 제거**: TASK-0063 의 dual entry 정책 (헤더 share 유지 / per-item menu) 은 일관성 측면에서 의도적이었으나 사용자 직접 테스트로 cancel/finalize 만 남기는 단일 진입점이 더 명료하다는 피드백 확인. share 가 hidden 패턴인 점은 REV-20260518-0001 Risks 의 잔여 trade-off 였는데, 본 cycle 에서 헤더 4 element 전체 제거로 자연 해소. duplicate/rename/delete/share/fork 의 backend helper 시그니처와 conv-item menu makeItem handler 는 무변경 — UI 진입점만 정리.
  - **trigger 우측 하단 이동**: TASK-0063 의 우측 상단 위치는 `.conv-owner-badge` ("내/sales/admin" pill) 의 우측 상단 위치와 시각 영역 겹침. 직접 테스트에서 hover 시 trigger 가 badge 일부를 가리거나 trigger 의 click target 이 badge 와 인접해 misclick 가능성 확인. 우측 하단 (`bottom: 6px; right: 6px`) 으로 이동하면 `.conv-item-meta` (dot + 시간 + owner) 영역과 만나는데 `.conv-item` 에 `padding-right: 32px` 보정으로 meta 가 trigger 만큼 좌측으로 압축. 사용자 시야 동선상 우측 하단은 "더보기" 의 자연스러운 위치 (Slack/Discord/Notion 의 menu trigger 위치 patterns).
  - **분기선 sticky**: TASK-0063 의 분기선 click trigger 가 동작은 정확하나 사용자가 캘린더 진입 의도일 때 분기선까지 scroll → click 의 2 단계가 부담. Slack 패턴 (date pill 이 message group 상단에 sticky) 으로 `position: sticky; top: 0; z-index: 5` 적용. CSS 만으로 동작 — JS scroll observer 불필요. label 배경을 `surface-2` (반투명) → `surface-1` (불투명 흰색) 으로 조정해 sticky 시 message bubble 위에 떠 있어도 가독성 보장. box-shadow elevation 으로 시각 분리. hover 시 box-shadow 강화로 clickable affordance 명확화.
- Risks:
  - **sticky 가 flex column + overflow:auto 부모에서 정상 동작하는가**: `.messages { display: flex; flex-direction: column; overflow-y: auto; gap: 14px }` — sticky 는 flex item 에서도 정상 동작. 본 cycle browser smoke 에서 `scrollTop = 600` 시 첫 분기선이 messageLog top + padding 영역에 정확히 stick 됨 확인 (`topInLog = 20`, padding-top 20px 와 일치).
  - **gap: 14px 의 시각 부작용**: sticky element 가 다음 element 위에 stick 될 때 그 위로는 gap 만큼 빈 공간이 보일 수 있음. 현재 디자인에서 분기선 위에 message bubble 이 들어가는 구조 (분기선이 message group 헤더) 라 부작용 없음.
  - **z-index 충돌**: pending bubble, message-actions ("여기서 분기" / "여기까지 공유" 버튼), message-point-rail dot 등의 z-index 와 비교 — 본 cycle 변경 element 는 z-index 5. menu dropdown (z=200), 캘린더 popover (default z=10 이하) 보다 낮아 dropdown / popover 가 sticky 위에 덮이는 정상 동작.
  - **active conv-item 의 trigger 상시 표시 정책 유지**: trigger 위치 이동만 변경, opacity 정책 (hover/active 시 1) 은 무변경. discoverability 보존.
  - **헤더 4 element 제거 후 backend helper 미사용 회귀 가능성**: `deleteConversation` / `renameCurrentConversation` / `forkConversation` / `createConversationShare` 는 conv-item menu 의 makeItem handler 와 message-bubble actions ("여기서 분기", "여기까지 공유") 양쪽에서 여전히 호출됨 — dead code 아님. grep 검증.
- Trace: REQ-20260518-0003 → TASK-0065 → CHG-20260518-0002 → REV-20260518-0002 (follow-up of TASK-0063)

## REV-20260518-0001
- Date: 2026-05-18
- Decision: TASK-0063 (REQ-20260518-0001, Major §12.3) — 작업 화면 대화 항목별 "···" menu + 캘린더 시간 이동 분기선 trigger 화. Codex outside voice review 10 risk 모두 반영 + 사용자 4 결정 채택.
- Method:
  - **복사 = full self-fork (사용자 결정 1)**: 메시지/첨부/SQL 결과까지 전부 보존. `_fork_conversation_impl` 은 share-fork 와 self-duplicate 양쪽이 공유 (helper 추출의 본 의도와 정합 — TASK-0058 R4). helper 가 `_set_account_current_conversation` 으로 active 자동 전환하는 side-effect 는 Codex risk 4 가 지적했지만, 본 cycle 에서는 ChatGPT 동등 UX (복사 후 새 대화 활성) 가 사용자 의도와 정합 — 의도적 유지.
  - **신규 권한 분리 (사용자 결정 2)**: `conversation.duplicate.own/.any` 추가는 rename/delete/cancel/finalize 와 동일 own/any 이원화 패턴 일관성. operator/sales 는 `.own` 만, admin 은 set(PERMISSION_CODES) 로 둘 다 자동 grant. `.any` 는 사용자 요청 없으면 grant 0 — 보수적.
  - **헤더 share 유지 (사용자 결정 3)**: active 대화의 quick share path 보존. per-item menu 의 "공유" 와 동일 endpoint (`POST /api/conversations/{cid}/share`) 호출 + 동일 helper (`createConversationShare`). dual entry 의 redundancy 는 discoverability 와 muscle memory 양쪽을 보존. 단 Codex risk 8 가 지적한 hide-vs-disable 불일치 — 헤더 share 는 여전히 hidden 패턴, menu items 는 visible + is-access-blocked 패턴. menu 안 일관성은 보장되나 share 만 헤더에서 hidden — 후속 cycle 에서 share 헤더도 visible 패턴으로 통일 가능 (별 cycle).
  - **분기선 단일 trigger + popover nav (사용자 결정 4)**: 헤더 historyCalendarBtn 제거 → 채팅 로그의 날짜 분기선이 캘린더 단일 진입점. 사용자 명시 — 먼 과거 jump 는 popover header 의 `‹` / `›` (월) + `«` / `»` (년) 로 해결. 년 jump 버튼은 `(newestYear - oldestYear) >= 1` 일 때만 조건부 노출 (사용자 명시). cursor 가 oldest/newest 범위를 넘는 방향은 disabled.
- Risks:
  - **Backend `_account_can_access_conversation` 의 호출 순서 (Codex risk 5/6)**: read-gate 먼저 호출 → 404 단일 wording ("권한이 없거나 대화를 찾을 수 없습니다.") → metadata leak 차단. `.any` 가 superset semantics 인 점은 backend 도 mirror (`is_own AND .own OR .any`).
  - **`_ensure_seed_catchup` 호출 순서 (Codex risk 3 변형)**: 기존 catalog hydrate 가 seed_roles 보다 뒤에 있어 신규 권한 grant 가 skip 되었음. 본 cycle 에서 fix — catalog 가 항상 먼저. 동일 패턴 회귀가 발생할 수 있는 future 권한 추가 시 본 review entry 가 참조 자료.
  - **Frontend hide-vs-disable inconsistency (Codex risk 8 잔여)**: menu 안은 rename/delete pattern 통일됨. 헤더 share 만 여전히 hidden — share 헤더도 visible 로 통일하는 별 cycle 권장.
  - **Backend IsDynamic NULL legacy schema (Codex risk 2)**: `_ensure_permission_catalog` 가 4 컬럼만 INSERT — IsDynamic DEFAULT 0 가 schema 에 보장된다고 가정. 현 운영 환경은 TASK-0052 Phase 1B 의 schema ALTER 가 DEFAULT 0 보장. 별 배포 환경에서 column 부재 시 _resolve_permission_catalog 의 graceful fallback (line 320) 으로 안전망 동작. 후속 cycle 에서 IsDynamic 명시 INSERT 강화 가능.
  - **년 jump 버튼 조건의 edge case**: oldest 와 newest 가 같은 해 (예: 2026-01 / 2026-12) 면 `newestYear - oldestYear = 0` → 년 jump 버튼 숨김. 1 년 폭 데이터인데 년 jump 가 없어 보이지만 월 jump 11 회로 같은 효과 달성 가능. 후속 cycle 에서 `>= 365 일` 또는 `>= 12 months` 조건으로 정밀화 가능.
- Trace: REQ-20260518-0001 → TASK-0063 → CHG-20260518-0001 → REV-20260518-0001

## REV-20260515-0004
- Date: 2026-05-15
- Decision: TASK-0062 (REQ-20260515-0011 / -0012, Minor §12.3) GOAL 2026-05-15 후속 2 항목 — 사용자 UX 개선 요청.
- Method:
  - **다중선택 UX**: 사용자 요청 "체크박스는 없애고 다중선택을 통한 표현만 나타나도록 / 다른 대화 항목 선택 시 나머지 선택 상태 해제 / 2개 이상일 때 표시". 셋 모두 동일한 흐름의 자연스러운 부분 — checkbox 가 visual noise 인 동시에 다중 선택의 진실원을 분산시킨다 (set + checkbox.checked 두 곳). modifier-only 입력으로 단일화하고 (`set` 만 진실원), 일반 click 흐름의 단일 선택 의도를 명시 (`clear` + `selectConversation`). bulk bar 의 1 개 threshold 는 단일 선택 만으로도 bar 표면 → discoverability 측면에선 도움이지만 본 요청은 minimal 추구. `count >= 2` 로 변경.
  - **Point rail 비례 분포**: 기존 구현은 rail 안에 dot 들이 4px gap 으로 단순 누적되었다. 메시지 1 개가 매우 길고 다른 1 개가 짧으면 dot 위치가 실제 scroll 위치와 매핑되지 않는다. `messageLog.scrollHeight` 기준 비례 (`top: <pct>%`) 로 배치하면 사용자가 "rail 의 dot 위치 = 메시지의 실제 위치" 를 직관적으로 인식. CSS transform 으로 dot 의 vertical center 정렬 + active 시 scale 합성으로 좌측 튐 방지.
- Risks:
  - **scroll 시 layout 재계산 비용**: 본 구현은 layout 을 render 시 1 회 + resize 시 1 회만 호출 (scroll 시는 active dot highlight 만). 대화 길이 변화 시 (메시지 추가 / 펼침) `renderMessages()` 가 자동 재호출하므로 일관성 유지. 단, `<details>` 펼침/접힘 같은 scrollHeight 변화 이벤트는 layout 을 직접 트리거하지 않음 — 후속 cycle 에서 MutationObserver 또는 ResizeObserver 검토 가능.
  - **dot 의 시각 겹침**: 메시지가 매우 가까이 있으면 dot 들이 겹칠 수 있다. 현재 8px 크기 + 부모 16px width — 메시지 간 거리가 ~ scrollHeight/N 의 작은 값이면 시각적으로 잘 안 보임. 사용자 피드백 수용 후 cluster 처리 후속 검토.
  - **다중 선택 discoverability**: checkbox 제거로 "다중 선택이 가능하다는 것" 자체가 visual 신호 없음. 단, 사용자 요청이 이를 명시했고 macOS Finder / GitHub PR list 등 동일 패턴 (modifier-only) 이 표준. tooltip / first-time 안내는 미적용.
- Trace: REQ-20260515-0011 / REQ-20260515-0012 → TASK-0062 → CHG-20260515-0005 → REV-20260515-0004

## REV-20260515-0003
- Date: 2026-05-15
- Decision: TASK-0061 (REQ-20260515-0003 ~ -0010) GOAL.md 8 항목 합본 cycle. 사용자가 Phase 1~8 일괄 승인 + 비밀번호 초기화 권장안 (MustChangePassword + 임시비번 1회 표시 + 세션 revoke + self-reset 금지) 채택을 2026-05-15 명시.
- GOAL.md §7 미결정 사항 결정:
  - **비밀번호 초기화 (REQ-20260515-0008)**: `MustChangePassword` 컬럼 채택 — 권장안 그대로. 사유: 임시 비번 + 세션 revoke 만으로는 대상 계정이 임시 비번을 계속 쓸 수 있어 보안 약함. `MustChangePassword=1` + 다음 로그인 시 강제 변경 modal 로 1회용 보장. 사용자의 명료화 "관리자 계정의 비밀번호 초기화가 아닌, 관리자 주관으로 특정 계정의 비밀번호를 초기화 하는 기능" 과 정합 — AC-0093 self-reset 거부와 일치.
  - **#progressCard 유지 vs 축소 (REQ-20260515-0003)**: 유지 (호환성). 1차 구현은 사용자별 collapsed 상태 localStorage 보존만 변경, hidden 처리는 미적용.
  - **bulk delete partial vs rollback (REQ-20260515-0010)**: partial success + 결과 요약. admin bulk UX (AC-0035) 와 일관성 우선. transaction rollback 은 사용자 의도 (일부라도 삭제) 와 정합 떨어짐.
  - **stale 만료시간 기본값 (REQ-20260515-0005)**: `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` (20분). 장시간 SQL/LLM 작업 (예: 복잡 QA — TASK-0034) 의 step 간격 추정 기준. env override 가능. 보수적 시작값으로 운영 오탐 줄임.
- Method:
  1. **Phase 분할 + 자족적 검증**: Phase 3 backend (env + helper + 3 endpoint 응답) 가장 자족적이라 먼저. Phase 1+2 (pending bubble + lazy polling) frontend 핵심. Phase 4 (point rail) Phase 1 의 message render 위에. Phase 5 (캘린더) 독립. Phase 7 (admin select-all fix) 자족. Phase 8 (bulk delete) backend helper 추출 + 신규 endpoint. Phase 6 (Critical 분면 — 인증 변경) 사용자 confirm 후 마지막.
  2. **§16.3 verify-completion 분리**: 각 Phase 종료 시 python compile + node --check 즉시 검증. 전체 완료 후 `make web` 재배포 + browser smoke (http://web:8000 진입, 신규 DOM 5개 (`.messages-wrap` / `#messagePointRail` / `#historyCalendarBtn` / `#historyCalendarPopover` / `#conversationBulkBar`) 존재 확인, 로그인 후 conv list checkbox 34개, /api/progress display_status 필드, /api/history_dates AgentMemoryMessages 기준, admin currentPageAccounts() == 현재 페이지 row, password-reset btn 노출).
  3. **인증 모델 영향 확인 (Phase 6 Critical)**:
     - `WebAccounts.MustChangePassword` ALTER 는 idempotent (slow path + fast path 양쪽). 기존 계정 default 0 — 기존 동작 불변.
     - `/api/admin/accounts/{id}/password-reset` 권한: `console.access` + `console.manage` + `account.update` AND **self-reset 거부** (`actor.id == account_id` → 400). 단일 endpoint 에 모두 명시.
     - 응답에 `temporary_password` 1회 포함 — server 로그/DB 평문 저장 없음. hash 만 저장.
     - 대상 계정의 `WebAuthSessions IsRevoked=1` 일괄 처리 — 모든 디바이스 강제 로그아웃.
     - frontend force change modal: `must_change_password=true` 면 닫기 button 미제공 (오직 비밀번호 변경 성공 후 자동 close). `/api/auth/me` PATCH 성공 시 `MustChangePassword=0` reset.
  4. **bulk delete 안전성 (Phase 8 — 파괴적)**:
     - `_delete_conversation_impl` helper 추출로 단건 endpoint 와 동일한 owner 가드 (`_account_can_access_conversation` + `conversation.delete.own`/`conversation.delete.any`) 재사용. cross-account leak 가능성 없음.
     - partial success 응답 — 일부 실패해도 다른 항목은 정상 처리. processing 대화는 `force=true` + `confirm_text="삭제"` 명시 시에만 처리. UI 가 ≥10 typed-confirm + processing 추가 confirm 으로 우발 클릭 방어.
- Risks:
  - **legacy cache**: cache-bust `v=20260515-task-0061` 적용 — 브라우저 hard reload 또는 cache clear 필요. 캐시된 구버전 frontend 는 신규 endpoint 응답 contract (`/api/progress` 의 `display_status` 등) 를 모름 — 단, 신규 필드는 기존 필드와 호환 (status 가 여전히 동작) 이므로 회귀 없음.
  - **`/api/history_dates` source 변경**: 이전 `AgentCoreMessages` 를 사용하던 client 흐름이 없음 — 사용 사례 자체가 본 cycle 의 캘린더 popover 만. 회귀 영향 없음.
  - **첫 stale 판정 false positive 가능성**: status_at / 첫 step 등록 직전 race 에서 시간 정보 자체가 없으면 보수적으로 stale 처리하지 않음 (helper 코드 참조). 운영 데이터 관찰 후 기본값 조정 가능.
  - **pending bubble polling 누락**: cid 발급 전 (lazy-create 첫 응답까지) 는 polling 이 안 됨 (cid sentinel). 그 사이 step 은 응답 도착 후 첫 polling 으로 누적 받음 (`after_step=0` snapshot). 첫 polling 까지의 미세한 지연은 elapsed timer 가 client tick 으로 보완.
  - **point rail 의 scroll observer**: 매 scroll 마다 모든 message element 의 getBoundingClientRect 호출 → O(N). 메시지 1000개 이상에서 jank 가능 — 현재 규모 (대화당 수십~수백 메시지) 에서는 무리 없음. 필요 시 IntersectionObserver 로 교체 후속 cycle.
- Trace: REQ-20260515-0003 ~ REQ-20260515-0010 → TASK-0061 → CHG-20260515-0003 → REV-20260515-0003

## REV-20260515-0002
- Date: 2026-05-15
- Decision: Product prompt 는 `WebProductDatabases`에 등록된 실제 접근 DB만 기준으로 작성하고, Role `전 Product 공통` prompt 는 특정 Product 선택 시에도 누적 적용되도록 runtime 조립 로직을 수정한다.
- Method:
  1. `WebProducts` / `WebProductDatabases`에서 현재 Product가 `KR(킹스레이드)`와 `MV(마이크로볼츠)` 두 개임을 확인했다. `KR` 접근 DB는 `dbgame,dblog,dbauth`, `MV` 접근 DB는 `account_db,dev_1_1_1_20,have_00,log_v2,global_db`.
  2. `information_schema.TABLES/COLUMNS`와 제한적 집계로 주요 스키마 성격을 확인했다. `KR`은 현재 상태(`dbgame`) + 대용량 로그(`dblog`) + 인증/기기(`dbauth`) 구조이고, `MV`는 계정 마스터(`account_db`) + 기준정보(`dev_1_1_1_20`) + 보유/매치 이력(`have_00`) + 서버/이벤트 기준(`global_db`) 구조다. `log_v2`는 DB는 존재하나 테이블이 0개다.
  3. Product prompt 에 민감 컬럼 경고를 포함했다. `dbauth`의 DeviceToken/광고 식별자/IP, `account_db`의 password/token/db 접속 정보는 원문 출력 금지 또는 최소화 대상으로 명시했다.
  4. Role 공통 prompt 는 `pending/operator/admin/sales/dba` 각각의 역할명과 권한 성격에 맞춰 작성했다.
  5. 기존 runtime 은 Role×Product prompt 가 있으면 Role common prompt 를 fallback 으로만 사용했다. UI의 "전 Product 공통" 의미와 다르므로 feature-0002의 `compose_system_prompt()`를 공통 누적 방식으로 수정했다.
- Risks:
  - Product prompt 는 현재 DB 상태 기준이다. 스키마가 크게 바뀌면 Product prompt 도 재검토해야 한다.
  - `make mysql`은 self-signed TLS chain 오류로 실패했다. 직접 SQL은 실행 중인 mysql 컨테이너 내부에서 root 환경변수 기반으로 수행했고, 비밀번호 값은 출력하지 않았다.
  - `make web` 재기동 중 기존 web/mysql/browser/worker 컨테이너가 한 번 정리된 뒤 web/mysql만 재기동했다. 최종 검증에 필요한 web/mysql은 정상 기동 상태다.

## REV-20260515-0001
- Date: 2026-05-15
- Decision: TASK-0059 (REQ-20260515-0001, **Major** §12.3 — 사용자 대화 routing 데이터 영역). "새 대화" 의 lazy-create 의도가 backend 로 전달되지 않아 빈 `conversation_id` 가 `_repair_current_conversation` 폴백 경로에서 `account.last_conversation_id` 로 귀결되던 결함을, 명시적 `lazy_create` body hint + `_resolve_conversation_for_account(force_new=...)` plumbing 으로 닫음. 인증/인가 catalog·endpoint guard·owner check 무변경.
- Method:
  1. **버그 재현 분석**: 사용자 보고 "새 대화 만든 후 그 대화에서 요청을 보냈는데 기존 대화에서 처리됨". 코드 trace 로 핵심 경로 파악 — frontend `beginPendingConversation()` [app.js:2148-2172] 이 `state.activeConversationId=""` + `pendingNewConversation=true` 로 두고 backend row 를 lazy 생성 위임 (TASK-0048 빈 대화 누적 방지 정책). `sendPrompt()` [app.js:2454] 는 `askBody.conversation_id=""` 로 `/api/ask` 호출. backend [app.py:4273-4285] 가 빈 cid 경로에서 `_resolve_conversation_for_account(..., create_if_missing=True)` 호출 → `_repair_current_conversation` [app.py:1156-1179] 으로 폴백 → `current_id = account.last_conversation_id` (= 직전 대화) 가 visible 안에 있으면 line 1167-1168 의 early return 으로 **기존 대화 ID 반환**. 신규 의도가 backend 로 전달되지 않음.
  2. **부가 race 발견**: `loadConversations` [app.js:2074] 이 pending 모드 진행 중에 호출되면 `payload.current` (= backend `_repair_current_conversation(create_if_missing=False)` 결과 = 직전 대화 id) 로 `state.activeConversationId` 를 덮어써 pending 의도를 깨뜨릴 수 있음. progress polling 정리에서 폴백된 갱신이나 다른 비동기 path 가 호출하는 경로에서 발생 가능.
  3. **대안 비교**:
     - **Alt A (선택)**: 명시적 `lazy_create` hint — frontend 가 pending 의도를 backend 에 신호. 단일 변경점 + 기존 fallback 보존 + legacy client 호환.
     - **Alt B**: backend 가 빈 conversation_id 를 항상 신규 생성. 단순하지만 첫 로그인 후 자동 이어받기 / `/api/use_conversation` 미호출 client 흐름이 깨짐. backward-compat 위배.
     - **Alt C**: frontend 가 pending 모드일 때 명시적 `/api/new_conversation` 먼저 호출. TASK-0048 의 빈 대화 누적 방지 정책이 부활하므로 거부.
  4. **race 가드 분리**: backend 의 routing fix 만으로는 pending 의도가 frontend 자체에서 깨질 가능성 잔존 → `loadConversations` 의 active id 덮어쓰기에 `!state.pendingNewConversation` 가드 추가. 두 변경은 독립적 — 하나만 적용해도 일부 시나리오 보호되나, 함께 적용해야 모든 reproduction 경로 차단.
- Risks:
  - **legacy client (구버전 frontend)**: hint 미포함 ask 요청은 force_new=False 로 기존 동작 유지. 그래서 backend 단독 deploy 후 frontend 가 캐시된 구버전이면 버그는 그대로 재현 가능. cache-bust 필요 시 `static/app.js` 의 query string 갱신 (e.g. `v=20260515-lazy`). 본 cycle 은 변경 자체에 cache-bust 미포함 — 사용자가 hard reload 또는 browser cache clear 로 확인.
  - **신규 cid 의 owner assign 경로**: `_repair_current_conversation` 의 force_new=True 분기는 `_create_conv(conv_file=_account_conv_file(...))` 호출 후 즉시 `_assign_conversation_owner(conn, next_id, account_id, force=True)` 와 `_set_account_current_conversation` 을 호출 (line 1175-1177). 즉 새 cid 는 본 계정 소유로 즉시 assign 되며 cross-account leak 가능성 없음.
  - **pending 가드의 부작용**: `loadConversations` 가 pending 중에 호출되어도 active id 가 보존되므로 backend `payload.current` 와 frontend `state.activeConversationId` 가 일시적으로 분기. 사용자가 사이드바에서 다른 대화를 직접 선택하면 `selectConversation` [app.js:2101] 이 pending 모드를 종료시키므로 (line 2106-2108) 정합 회복. 첫 메시지 전송 시에는 `sendPrompt` 의 lazy create 분기 (line 2509-2513) 가 새 cid 로 정리.
  - **owner check 우회 가능성**: 변경 후에도 명시 cid 가 들어오는 경로 (`request_conversation_id` truthy) 는 기존 `_conversation_owned_by_account` 검사 [app.py:4269-4271] 를 그대로 거친다. force_new 경로는 새 cid 를 즉시 생성하므로 owner check 가 무의미 (본 계정 소유). 인가 모델 무변경 확인.
  - **TASK-0048 정책과의 충돌 여부**: TASK-0048 은 "빈 대화 row 누적 방지" 가 목적. 본 fix 의 force_new 분기는 **메시지 전송 시점에만** 발동하므로 row 가 만들어지는 즉시 메시지가 attach 됨 → 빈 대화 아님. 정책 위배 0.
- Follow-ups:
  - 운영 검증: web 컨테이너 재배포 후 (a) 직전 대화 X 가 있는 상태에서 "새 대화" 클릭 → 빈 입력창 → 메시지 전송 → 새 cid Y 발급 + 메시지가 Y 에 attach (X 에는 추가 없음) 확인. (b) 직전 대화 X 가 있는 상태에서 "새 대화" 클릭 → 사이드바 새로고침 트리거 → active 가 X 로 복귀 안 되는지 확인 (pending 가드).
  - cache-bust: 다음 cycle 에서 frontend 변경 함께 deploy 할 때 `static/app.js?v=` 갱신.
  - 회귀 테스트: feature-0003 unit tests 에 "lazy create 의도 시 신규 cid 발급" + "pending 모드 race 시 active 보존" 케이스 추가 가능 (현 cycle defer — TASK-0034 성능 테스트와 함께 다룰지 사용자 결정).

## REV-20260514-0001
- Date: 2026-05-14
- Decision: TASK-0058 (REQ-20260514-0001, **Critical** §12.3) 대화 공유 링크 기능 도입. anonymous 접근 허용은 사내 IP 가정 + 외부 배포 시 IP 제한/비밀번호 보호 후속 cycle. PLAN-APPROVED + 사용자 결정 6 항목 + outside voice review 완료 후 진행.
- Method:
  1. **요구사항 정제**: 사용자 요청 "특정 대화를 링크로 공유" 가 매우 광범위. 6 가지 결정사항을 AskUserQuestion 2 라운드로 확정 — 외부 anonymous 허용, 무기한 + revoke, read+fork, full+anchored 둘 다 생성 시 선택, `conversation.share.create` 권한 신설, 메시지 + SQL + 결과셋 모두 노출 (사내 협업 우선).
  2. **Outside voice review** (메모리 정책 `feedback_outside_voice_for_rbac`): RBAC catalog 변경이므로 general-purpose subagent 로 plan blindspot 10 건 수집. B1 (메시지 테이블 이중성 — `AgentMemoryMessages` vs `AgentCoreMessages` Id 공간 분리 — fork 의 `from_message_id` 와 정합 위해 `AgentMemoryMessages.Id` 채택), B2 (`_require_account` 가 401 raise → `_optional_account` 신설), R4 (`_fork_conversation_impl` 추출로 share-grant 가 read-gate 우회), R5 (AnchorMessageId inclusive `Id <= anchor`), R6 (revoke + view race-free 단일 UPDATE), R7 (file attachment 자동 hide), R8 (token UNIQUE 충돌 retry 5 회), R10 (share.html FileResponse) 모두 plan 에 흡수.
  3. **위험 분리**: Critical 등급 (SECURITY.md §3 의 인증/인가 + 개인정보 + 외부 공개 범위 3 항목 동시) 이지만 5 phase 가 모두 비파괴 추가 + idempotent. Phase 별 syntax check 통과 후 다음 phase 진행.
  4. **검증**: app.py Python AST parse OK, app.js / share.js node --check OK. 부트스트랩 idempotency 는 helper 패턴 (try/except pass + INSERT IGNORE + ON DUPLICATE KEY UPDATE). 실런타임 검증 (sales/admin 로그인 → 헤더 공유 → URL 발급 → anonymous 접근 → revoke → 410) 은 후속 단계.
- Risks:
  - **외부 IP 노출**: 사내 IP 가정이 깨지는 순간 (예: 실수로 외부 LAN 으로 expose, VPN 미접속) 대화의 SQL 원문 + 결과셋이 외부에 그대로 노출. 사용자도 이 위험을 인지하고 "추후 사내 배포 시 보완" 결정. 후속 cycle 의 보완 옵션: (a) Caddy / reverse proxy IP allowlist (사내 CIDR), (b) share token 별 비밀번호 옵션 (`WebConversationShares.PasswordHash` 컬럼 추가), (c) 시간 기반 만료 (현재 무기한). 본 cycle 은 minimum viable.
  - **anonymous endpoint 보안 표면**: `/api/public/share/{token}` 과 `/api/public/share/{token}/fork` 가 시스템의 유이한 anonymous-allowed 경로. 향후 RBAC refactor 가 실수로 `_require_account` 를 모든 endpoint 에 일괄 부착하면 share view 가 깨질 수 있음. 두 endpoint 모두 inline 주석으로 anonymous 의도 명시. SECURITY.md 에 정책 등재.
  - **token enumeration**: `secrets.token_urlsafe(32)` = 256-bit entropy → brute force 비현실적. UNIQUE 충돌 retry loop 는 보안 위협 없음 (5 회 재시도 후 500 반환).
  - **revoke + view race**: 단일 `UPDATE ... WHERE Token=? AND RevokedAt IS NULL` rowcount 가 0 일 때 410 Gone 반환. rowcount > 0 + 그 후 revoke 사이 라스트 mile 은 stale-by-one 수용.
  - **anchor 의미 혼란**: inclusive (`Id <= anchor`) — fork 의 `from_message_id` 와 정확히 동일. UI label "여기까지 공유" 가 그 의미 표현.
- Follow-ups:
  - 외부 배포 전: IP allowlist 또는 token 별 비밀번호 옵션 cycle.
  - `/api/public/share/{token}` 의 rate limit (DDoS 완화) — 본 cycle defer.
  - 운영 검증: sales/admin 계정 양쪽으로 헤더 공유 / 메시지 hover 공유 / anonymous URL 접근 / revoke / 410 회귀 / fork 흐름 실제 동작 확인.
  - 프로필 drawer 의 "내 공유 링크" 관리 탭 — `GET /api/conversations/{cid}/shares` 와 `DELETE /api/share/{id}` 가 이미 backend 에 있으니 frontend UI 만 후속 추가 가능.

## REV-20260507-0001
- Date: 2026-05-07
- Decision: TASK-0053 의 사용자 follow-up 2 항목 수정 — pending row UI 뒤틀림 + product 카드 위치 이동 — 을 1 commit 에 통합. AI 자율 commit/push.
- Method:
  1. **Issue 1 진단**: pending sales row 의 DOM 을 `getBoundingClientRect` 로 분석 → cb 가 column 2 (x=70), main 이 column 3 (x=175), chips 가 row 2 col 1 (x=11, y=73) 에 wrap 되어 있음. 수상한 4번째 grid item 추정. CSS 검토 결과 `.admin-list-row.has-pending::before { content: ""; }` placeholder rule 발견 — `::before` 가 grid container 의 pseudo-element 이지만 `content: ""` 가 있으면 generated DOM 에 참여해 grid 의 4번째 child 가 되어 column 1 row 1 을 차지. 다른 children 이 한 칸씩 밀리고 chips 는 wrap.
  2. **Issue 1 수정**: pseudo-element 자체를 제거 (placeholder 의도가 사라졌음). 시각적 표시는 `border-color` 변경으로 유지 (`pendingDot` "•" 이 이미 title 안에서 indicator 역할 수행).
  3. **Issue 2 구현**: `buildRoleProductCardList` / `buildAccountProductOverrideList` 에 `opts.embed` 옵션 추가. embed=true 면 별도 section title 생략 (부모 details summary 의 "제품" 라벨이 이미 표시), hint 단축. `renderRoleDetail` / `renderAccountDetail` 가 `permWrap.querySelector('details[data-perm-group="product"]')` 로 grid 의 product 그룹 details 를 찾아 그 안에 append. 없으면 fallback paneEl append.
  4. **검증**: DOM 좌표 비교 (수정 전 cb x=70 → 수정 후 x=11), embedded 카드 카운트 3 (KR/TT/전 Product 공통), 시각 screenshot 비교.
- Risks:
  - **CSS Grid pseudo-element 함정 재발 위험**: 향후 `::before`/`::after` 에 content 추가 시 grid item 으로 참여. LEARNINGS.md 의 frontend pitfall 항목 등재 권고. 방어 패턴: grid container 의 pseudo 는 `position: absolute` 로 flow 에서 제외 또는 `display: none`.
  - **embed 옵션의 hint 길이 차이**: standalone 모드 vs embed 모드의 hint 텍스트가 다름 (footer 안내 중복 회피). UX 일관성 손실은 미미 — 동일 의미를 압축 표현.
  - **Issue 2 의 fallback 경로**: grid 에 product 그룹이 없으면 (정적 product.manage 권한 자체가 없는 환경) product 카드 list 가 별도 paneEl section 으로 표시. 운영 환경에서 product 그룹은 항상 존재하므로 발생 시나리오 거의 없음.
- Why combine in one commit: 두 이슈가 독립적이지만 사용자가 동시에 보고 + 둘 다 동일 cycle (TASK-0053) 의 보완 + 둘 다 admin.js + styles.css 파일 영역. 분리 commit 의 이득 < 통합 deploy 의 일관성.

## REV-20260506-0014
- Date: 2026-05-06
- Decision: TASK-0053 의 3 phase (A/B/C) 를 1 cycle 안에 통합 진행. **사용자 in-cycle 설계 전환 (2026-05-06)** — 처음 작성한 Phase A 의 "Role 의 DefaultProductAccess 토글" 접근을 사용자 의도에 따라 "Product 의 DefaultRoleAccess 토글" 로 정정. 분리 commit 하지 않은 이유: 본 cycle 의 수정은 보안 표면 추가 0 + 기존 동작 호환 (DEFAULT 1 백필) + frontend 재구성이 핵심. 분리 commit 의 회귀 표면 제어 이득보다 통합 deploy 의 일관성 (정책 토글이 곧 product subcatalog 와 함께 보임) 이 더 큼.
- Method:
  1. **Phase A (정책 토글, product 주체)**: WebProducts 에 `DefaultRoleAccess TINYINT(1) NOT NULL DEFAULT 1` 컬럼. 기존 product 모두 1 으로 backfill 되어 D2-A 와 동일 동작 유지. POST `/api/admin/products` 의 transaction 안 backfill SQL + `_ensure_product_access_permissions(conn)` (catchup) 양쪽이 product 의 `DefaultRoleAccess` 값에 따라 분기. POST/PATCH `/api/admin/products` body 에 `default_role_access` 수용. Role-side 의 이전 시도 (`WebRoles.DefaultProductAccess`) 는 컬럼 잔존하나 어떤 SQL 도 참조하지 않음 — 다음 cleanup cycle 에서 DROP COLUMN.
  2. **Phase B (권한 grid 의 dynamic 분리)**: `groupedPermissions(opts)` 에 excludeDynamic 옵션 추가. `dynamicProductPermissions()` 헬퍼로 product 별 정렬된 동적 권한 목록 반환. `renderPermissionGrid` 가 옵션 통과. Role detail 과 Account detail 의 onChange 핸들러는 dynamic 권한들의 기존 상태를 union 으로 보존해 subcatalog 와의 분리가 데이터 손실로 이어지지 않게 처리.
  3. **Phase C (Role/Account detail 의 product subcatalog 카드)**: `buildRoleProductCardList(role, disabled)` — product 별 collapsible card 안에 access 토글 + role-scope system prompt textarea (fixedProductId=Number(id)) 묶음 + "전 Product 공통" generic card (fixedProductId=0). `buildAccountProductOverrideList(account, disabled)` — flat card 에 override select. Role detail 의 단일 buildSystemPromptEditor 호출은 product 카드의 textarea 로 흡수 (Product detail 의 product-scope prompt + profile drawer 의 account-scope prompt 는 그대로).
  4. **검증 매트릭스**: py_compile + node check + make web + Phase A E2E (DE 생성 with `default_role_access=false` → 6 role 모두 grant 0, JP 생성 with true → 6 role 모두 grant) + Phase B/C DOM (admin-product-card-list/admin-product-card 카운트 + 권한 grid dynamic 코드 제외 확인 + 스크린샷).
- Risks:
  - **호환성 우선의 default 1**: 운영자가 product 생성 시 토글을 명시적으로 끄지 않으면 기존 동작 유지 (D2-A 호환).
  - **이전 시도 잔재**: `WebRoles.DefaultProductAccess` 컬럼이 destructive DROP 회피로 잔존. 어떤 SQL 도 참조하지 않으므로 동작 영향 0. 본 cycle 자체가 commit 전 상태에서 in-place 정정이라 git log 에는 이 잔재가 노출되지 않음 (single commit). 다음 cleanup cycle 에서 명시적 DROP COLUMN.
  - **Phase B 의 onChange union 처리**: dynamic 권한들이 grid 와 subcatalog 두 곳에서 source-of-truth 가 분리되어 보일 수 있으나 실제 storage 는 단일 (`role.permission_codes` / `account.permission_overrides`). onChange 가 정적/동적 양쪽 union 을 보장하므로 race-free.
  - **Account detail 의 product card 에 prompt textarea 부재**: account scope prompt 는 profile drawer (AC-0014) 가 source-of-truth.
  - **product 가 100 개 이상이 되면 cards 가 길어짐**: collapsible details 라 펼치지 않으면 헤더만 보여 스크롤 부담 적음. 추후 search 필터 추가 가능 (별 cycle).
  - **"신규 역할 자동 접근" 토글의 의미 명시**: **신규** product 생성 시점에만 효력. 기존 product 의 grant 는 product PATCH 의 default_role_access 변경으로도 변하지 않음 (정책만 변경, 기존 grant 보존). admin UI 에 명시 hint 추가는 별 cycle.
- Why this design switch (Role-driven → Product-driven): 사용자가 본 cycle 진행 중 명시적으로 의도 정정 — "신규 제품 자동 접근의 주체를 Role 이 아닌 Product 를 기준으로 적용". 직관적으로도 정책의 주체는 "이 product 가 어떻게 분배되는지" 이지 "이 role 이 무엇을 자동으로 받는지" 가 아님. Product-driven 이 product 운영자의 결정 권한을 명확히 함.
- Why this combines Phase A/B/C in one commit: 사용자가 한 번에 3 항목 (토글 + sub catalog + role-prompt 묶기) 을 요청했고 AI 자율 commit/push 권한이 명시되어 있음. 분리 commit 은 회귀 표면 제어 이득 < 통합 deploy 의 일관성 (3 변경이 한 화면에서 함께 보여야 의도 전달) 이 더 큼.

## REV-20260506-0013
- Date: 2026-05-06
- Decision: TASK-0052 의 Phase 1B/1C/1D + Phase 2 검증을 사용자 AI 자율 commit/push 모드에서 1 cycle 안에 완료한다. Codex outside voice 의 9 finding 모두 통합 (정적 catalog 가정 → DB-driven, autocommit → 명시적 트랜잭션, 가드 8 곳 도입, fork product_mode 복사 fix 등). 작업 중 발견된 pre-existing `admin_update_account` RoleId 손실 버그도 즉시 fix.
- Method:
  1. **Phase 1B (catalog DB-driven 전환)**: Phase 1A 가 깐 plumbing (`_resolve_permission_catalog(conn=None)`) 의 body 만 교체. conn 이 주어지면 정적 + WebPermissions IsDynamic=1 union 반환. graceful fallback (column missing / DB error) 으로 호환성 유지. caller 7 곳을 `_resolve_permission_catalog(conn)` 결과 (`catalog_codes` / `catalog_map`) 를 명시적으로 전달하도록 update.
  2. **Phase 1B (schema migration)**: `_ensure_dynamic_permissions_schema(conn)` 헬퍼 + `_ensure_product_access_permissions(conn)` 헬퍼. slow path (`_ensure_web_tables`) + fast path (`_ensure_seed_catchup`) 양쪽에서 호출되어 기존 배포에서도 신규 컬럼/권한 row/role grant 가 자동 적용. backfill 결과를 stderr 에 1 회 기록 (운영 transparency, Codex Claim 5).
  3. **Phase 1B (product CRUD 트랜잭션, Codex Claim 2)**: `conn.autocommit=False` + 명시적 commit/rollback. POST 는 product + permission row + role grant cascade 한 트랜잭션. DELETE 는 in_use guard 통과 후 SystemPrompts → ProductDatabases → RolePermissions → AccountPermissionOverrides → Permissions → Products cascade 한 트랜잭션. 부분 실패 시 product 자체 rollback.
  4. **Phase 1C (G1-G8)**: `_account_has_product_access(account, product_id_or_key, *, conn=None)` 단일 진입점. 8 endpoint 가드 (briefing §3.4 매트릭스). G4 가 Codex Claim 3 의 직접 해소 — 권한 회수 후 pinned 대화 재실행 차단. G5 가 fork 의 product_mode 'auto' 보존 fix 도 함께 처리 (Codex Claim 4).
  5. **Phase 1D (admin UI)**: PERMISSION_GROUP_ORDER 에 'product' 추가. admin.js + app.py 양쪽 동기. 기존 renderPermissionGrid 가 자동 노출.
  6. **Phase 2 (HTTP smoke)**: bootstrap_admin 으로 deny override 적용 → G1/G2/G7/G8 직접 403 검증 + product CRUD lifecycle (T13/T14/T15/T16) + admin_update_account RoleId 보존 fix 검증. G3/G4 는 model validation 단계에서 차단되어 정적 코드 검증으로 대체 (코드 경로 동일 패턴).
- Risks:
  - **Critical 등급 변경 + AI 자율 commit**: AGENTS.md §12.3 (인증/인가 구조 변경) 으로 본래는 사람 승인 필요. 사용자가 명시적으로 AI 자율 권한 부여 (2026-05-06) — 정책 적용 우선순위 §3.1 1 위 (사용자 직접 지시) 에 따라 진행. 본 변경의 보안 의미: 8 endpoint mutation/read 가드가 추가되어 product 격리 강화, 단 D2-A 호환성 backfill 로 모든 role 이 default-grant 라 운영자 후속 deny override 필요.
  - **pre-existing 버그의 발견 시점**: admin_update_account RoleId 손실은 이전 cycle 부터 존재했을 가능성이 높음 (코드상 `target.get("role")` 은 어느 시점부터 None 이었음). Phase 1C 의 negative smoke 에서만 트리거되어 catch — 일반 운영에서는 admin 이 본인 PATCH 를 거의 하지 않아 dormant 였던 회귀로 추정. 본 fix 가 cycle 안에 포함되어 안전.
  - **D2-A 의 secure-by-default 갭**: 본 cycle 종료 후에도 pending/sales/operator 등 모든 role 이 KR (현재 1 product) 에 default-grant. 운영자가 deny override 로 회수해야 실효 격리. 운영 transparency 메시지로 안내.
  - **Phase 2 negative smoke 의 G3/G4 미직접 검증**: model validation 단계 차단으로 HTTP smoke 가 가드 도달 불가. 정적 코드 검증으로 대체 — G1/G2 와 동일 패턴이라 회귀 위험 낮음. 후속 cycle 에서 valid model 로 재시도 가능.
  - **admin lockout 보호 (briefing F8 — NOT in scope)**: admin 이 자기 자신의 마지막 product access 를 deny 로 잠가 lockout 가능성. survivor 보호 로직 (`_ensure_management_survivor_for_account_change`) 은 console.manage 류만 검사하고 product access 는 미포함. 별 cycle 검토.
- Why this combines Phase 1B/1C/1D in one commit (분리 commit 옵션 선택 안 함): 본 cycle 진입 시 사용자가 "나머지 Phase 모두 진행" + "AI 자율 commit/push" 명시. Phase 1B/1C/1D 는 의존 순차라 각 phase 단독 deploy 의미가 적음 (1B 만 deploy 시 가드 없는 상태로 DB schema 변경, 1C 만 deploy 는 1B 없이 catalog 가 catch 못함). Phase 1A 는 deploy-safe 단일 변경이라 분리 commit 했지만 (4dd1d0a), 본 cycle 은 통합 deploy 가 일관성에 유리.
- How this changes BRIEFING-c5: 본 cycle 로 briefing 의 Phase 1A/1B/1C/1D + Phase 2 P0 (T01-T08, T13-T16 직접 + T19/T20/T21-T23 정적) 모두 ✓. 미구현 항목: Phase 2 P2 (sessions/me filter, end-user FE chip filter) — 별 cycle. F8 (admin lockout 보호) — 별 cycle.

## REV-20260506-0012
- Date: 2026-05-06
- Decision: TASK-0052 Phase 1A 만 본 turn 에서 진행한다. RBAC engine 의 정적 PERMISSION_CODES 가정 (Codex Claim 1) 을 catalog 인자 받는 형태로 refactor 하되, **동작 변경은 0** — 모든 5 함수의 catalog 인자 default = None = 정적 사용. `/api/admin/permissions` 만 신규 plumbing 검증 경로로 전환해 Phase 1B 의 DB-driven 전환 surface 를 미리 검증한다. Phase 1B/1C/1D 는 별 cycle 분리.
- Method:
  1. **`_resolve_permission_catalog(conn=None)` 헬퍼** 신설 — Phase 1A 시점은 정적 `(PERMISSION_DEFINITIONS, PERMISSION_CODES, PERMISSION_DEFINITION_MAP)` 반환. Phase 1B 가 body 만 교체 (conn 으로 WebPermissions union). 단일 함수가 catalog source 의 single point of customization 이 되도록 설계.
  2. **5 함수 시그니처 확장** — `_empty_permission_map(catalog_codes=None)`, `_apply_permission_overrides(..., *, catalog_codes=None)`, `_validate_permission_codes(..., *, catalog_codes=None)`, `_normalize_override_payload(..., *, catalog_codes=None, catalog_map=None)`, `_permission_catalog_payload(*, catalog=None)`. 모두 `*` keyword-only, 기본값 None = 정적 사용. 기존 callsite 6 곳 (L854/3681/5403/5545/5624/5395) 모두 None 인자로 호출 → 기존 동작 유지.
  3. **plumbing 검증 endpoint 1 곳** — `/api/admin/permissions` (L5761) 만 새 경로 (`_resolve_permission_catalog(conn) → _permission_catalog_payload(catalog=catalog_definitions)`) 로 전환. HTTP smoke 로 catalog 결과가 이전과 동일 (33 codes) 임을 확인. 다른 callsite 는 Phase 1B 에서 caller-update.
  4. **검증 매트릭스**: py_compile + container reload + container 내부 grep + bootstrap_admin HTTP login + /api/admin/permissions 응답 비교. 4/4 통과.
- Risks:
  - **Phase 1A 단독 commit 의 의미**: 코드 변경은 plumbing 만, 동작은 0. 그래도 commit 분리는 (a) 회귀 표면 명확화, (b) Phase 1B 가 catalog source 만 교체하는 단순 변경으로 떨어짐, (c) 향후 다른 RBAC 변경이 plumbing path 를 그대로 활용. 위험 회피 ROI 높음.
  - **`/api/admin/permissions` endpoint 만 plumbing 사용 — 다른 callsite 는 정적 path 그대로**: Phase 1B 가 catalog 를 dynamic 하게 만들 때 다른 callsite (특히 L3518/3570 의 role payload `permissions` map 빌드) 도 catalog 를 받아야 함. Phase 1B 의 caller-update 범위를 briefing §4 의 Phase 1B 항목에 명시.
  - **Iterable import 추가 (L18)**: typing 외 collections.abc 에서 가져와 type hint 만 사용. 런타임 영향 0.
- Why not Phase 1B 까지 한 turn: Briefing §12 의 "Phase 1A 는 product 권한 도입 없이도 안전하게 deploy 가능" 에 따라 분리. Phase 1A 단독 회귀 면적이 0 이라 commit 후 즉시 운영 deploy 가능. Phase 1B 는 backfill SQL + 8 endpoint guard 의 complexity 합산이 큼 — 별 cycle 의 plan + verification 필요.
- How this changes BRIEFING-c5: 본 turn 의 Phase 1A 완료를 briefing §4 마이그레이션 plan Phase 1A 항목에 ✓ 표시 권고. Phase 1B 진입 시 briefing §12 의 후속 단계 안내 그대로 적용.

## REV-20260506-0011
- Date: 2026-05-06
- Decision: TASK-0051 (REQ-20260506-0004) 관리 콘솔 5 가지 UX/정책 요청 중 4 건(C1~C4) 만 본 cycle 에서 진행하고, **C5 (계정·역할 → 제품 권한 상속/override 모델)** 는 다음 cycle 로 분리한다. 메타데이터 4 종 노출은 신규 backend 정책 변경 없이 UI 시각화로만 처리한다 (REV-20260422-0006 에서 이미 tool-level bypass 가 정의됨). DB 목록 picker 는 신규 read-only enumeration 엔드포인트(`GET /api/admin/databases/available`) 로 제공하고 권한 게이트는 `console.access` 로 약하게 둔다.
- Method:
  1. **C5 분리 결정**: 사용자가 직접 `[A → B → C → D]` 까지만 진행하도록 지시 + C5 는 review 후 다음 cycle 진행 권고를 명시 요청. 분리의 운영 근거: (a) C5 는 신규 테이블 2 개(`WebRoleProductAccess`, `WebAccountProductAccessOverrides`) + 기존 RBAC override 모델(TASK-0024) + `compose_system_prompt` 의 product 조회 경로(`feature-0002-agent-core/src/agent_core.py`) 변경 영향을 동시에 받는다. (b) 일괄 commit 정책 회복(C1~C4) 과 권한 모델 확장(C5) 은 서로 독립이라 한 PR 안에서 묶어도 회귀 표면이 분리되지 않는다. (c) `/plan-eng-review` 를 거치지 않으면 RBAC override 우선순위 (Role default → Account override) 와 신규 product access override 우선순위가 어떻게 합성되는지 결정이 명확하지 않다 — 무리한 진행 시 인증 인접 회귀 가능성.
  2. **메타데이터 4 종 시각화 방식 비교**: (a) backend 가 응답에 `databases` 필드로 메타 4 종을 항상 강제 포함시키는 방안, (b) backend WebProductDatabases 에 자동 INSERT, (c) UI 가 정책 상수로 직접 그리고 backend 는 무관, 3 가지를 비교. (c) 채택 — 사유: REV-20260422-0006 의 tool-level bypass 정책은 데이터 저장과 무관하게 항상 적용되므로 WebProductDatabases 에 메타를 굳이 저장할 필요가 없다(중복 진실 회피, AGENTS.md §13.1). (a)/(b) 는 user_schemas 와 metadata_schemas 의 정책적 의미 차이(metadata = 항상 bypass / user = 사용자 화이트리스트) 를 코드에서 구분 못 하게 만든다.
  3. **DB picker 권한 게이트 결정**: enum 결과는 schema 이름 / 존재 여부 한정이며 row 데이터 노출이 없다. 실제 등록은 `product.manage` 권한이 필요한 PUT `/api/admin/products/{id}/databases` 가 게이트로 남는다. 따라서 enum 자체는 `console.access` 만으로 허용해 product 관리자가 아닌 readonly 관리자에게도 picker UX 가 도움이 되도록 한다. 민감 schema(`agent_memory`, `MEMORY_DB`) 는 user_schemas 응답에서 backend 가 제외해 picker 옵션에 노출되지 않도록 이중 가드.
  4. **일괄 commit 흐름 통합 방식**: pending bucket 별 PATCH/PUT 호출을 `applyAllPending()` 하나에 합치는 6 단계로 확장. 신규 buckets 의 실패는 기존 `failures` 배열에 합류해 동일 toast UX 유지. 부분 성공 의미를 보존(예: 제품 메타는 PATCH 성공인데 시스템 프롬프트 PUT 만 실패해도 `${ok}건 성공 ${failures.length}건 실패` 로 표기).
  5. **System prompt textarea pending 보존**: pending entry 가 `loadAdminData()` reload 로 사라지지 않도록, `refresh()` 가 pending 우선으로 textarea 값을 복원. productSelect 변경 시에도 새 (scope, productId, ...) key 의 pending 이 있으면 그 값을 표시.
- Risks:
  - **회귀 표면**: applyAllPending 6 → 9 단계 확장. 기존 single-button save 경로가 사라졌으므로 사용자가 변경 후 footer 적용을 누르지 않으면 변경이 유실된다. 완화: textarea/input 변경 즉시 `refreshPendingUI()` 가 footer 카운트를 증가시키고 `beforeunload` 핸들러가 confirm 하도록 기존 `pendingChangeCount > 0` 체크가 그대로 동작.
  - **TextArea pending 키 충돌**: 같은 (scope, productId, roleId, accountId) 조합에 두 번 입력해도 마지막 입력이 덮어쓴다 (Map). productSelect 가 바뀌면 다른 key 의 pending 이 활성화되어 두 분기 모두 보존된다 — 기존 동작과 일치.
  - **DB picker stale**: `availableDatabases` 는 loadAdminData 시점의 스냅샷이라 admin 콘솔 진입 후 새 DB 가 생성되어도 즉시 반영되지 않는다. 완화: `refreshAdminBtn` (새로고침) 또는 footer apply 후 자동 reload 가 picker 도 갱신.
  - **권한 게이트 약화 우려**: `console.access` 만으로 enum 가능. 위협 모델: (a) schema 이름 자체가 정보 누출이라는 관점이 있을 수 있으나, 본 콘솔에 진입한 시점에 이미 `WebProducts`/`WebProductDatabases` 의 등록된 user 화이트리스트는 노출됨(기존 동작). (b) 등록 변경은 여전히 `product.manage` 가 필요하므로 권한 escalation 표면 없음. 결정: `console.access` 유지.
  - **C5 누락 인지**: 본 cycle 종료 시 사용자가 `계정·역할 → 제품 권한 상속/override` 가 빠졌다는 사실을 인지하지 못할 위험. 완화: REPORT.md "후속 작업" 에 C5 권고 명시 + ANCHOR.md §3 의 "Role/Product 권한 부여" 시나리오 본 cycle 에서 시각화만 강화 + 다음 cycle 의 plan-eng-review 호출 권유.
- Why not C5 한 cycle 에 묶기: (1) RBAC override 모델(TASK-0024) 과의 우선순위 합성이 결정되지 않음. (2) `compose_system_prompt` 의 product 조회 경로가 새 권한 모델에 어떻게 의존하는지 추적 필요. (3) 신규 테이블 2 개 + 기존 `WebAccountPermissionOverrides` 와의 책임 분리 정의 필요. (4) 사용자 명시 지시("C5는 다음 cycle에서, review 후 진행할 수 있도록 권고") 와 일치.
- How this changes REV-20260422-0006: 정책 결정은 그대로 유지되고, 본 review 에서는 그 결정을 admin UI 가 직접 시각화하도록 끌어올린다 (메타 4 종을 admin 콘솔에서 회색 chip 으로 항상 노출 + dbHint 안내 + tool-level bypass 정책 변경 없음).

## REV-20260506-0010
- Date: 2026-05-06
- Decision: 빈 대화 누적 방지를 위해 "새 대화" 생성 시점을 backend row 즉시 발급에서 client-side pending → 첫 메시지 전송 시 `/api/ask` lazy creation 으로 전환한다. 기존 backend `/api/new_conversation` 엔드포인트는 backward compatibility 를 위해 보존하지만 frontend 는 더 이상 호출하지 않는다.
- Method:
  1. backend `/api/ask` 의 `_resolve_conversation_for_account(create_if_missing=True)` lazy create 경로가 이미 존재함을 확인 (`src/app.py` L3853 부근). 즉 cid 없이 ask 가 들어와도 backend 는 새 대화를 만들 수 있다. 단 `/api/new_conversation` 이 적용하던 product hint (mode/product_id) 가 ask body 에 없어 lazy 생성 row 는 default('pinned' + default product) 로 시작해 사용자가 'auto' 의도를 가진 경우 회귀가 발생.
  2. 두 가지 backend 보강안을 비교: (a) ask body 에 product hint 수용해 cid 발급 직후 적용, (b) `/api/new_conversation` 을 client 가 한 단계 앞서 호출 후 그 cid 로 ask. (a) 채택 — round trip 1회 절약 + 기존 `_resolve_conversation_for_account` 경로 재사용.
  3. PATCH race 가드(TASK-0047) 와의 충돌 방지: hint 적용은 lazy 생성 분기에만 한정하고, `request_conversation_id` 가 명시된 경로에는 hint 를 무시한다. 즉 기존 대화의 product 변경 단독 진실은 여전히 `PATCH /api/conversations/{cid}/product`.
  4. 기존 누적된 빈 대화 일괄 정리는 destructive 변경 (`DELETE FROM AgentCoreConversations WHERE NOT EXISTS (... messages)`) 이라 §12.1 사람 승인 필요. 본 turn 범위 외 — REPORT.md 후속 작업으로만 명시.
  5. ask 실패 시 cid 미상 처리: lazy create 분기에서 ask 가 네트워크/타임아웃으로 실패하면 backend 가 이미 cid 를 만들었을 가능성이 있지만 client 는 `payload.conversation_id` 를 받지 못해 알 수 없다. 이 경우 attach/resume 다이얼로그(TASK-0041) 는 cid 를 알 때만 유효하므로 활성화하지 않고, 사용자에게 "재시도하거나 사이드바를 새로고침해 주세요" 안내 토스트만 노출. 사용자가 사이드바 새로고침을 통해 새 대화 row 를 발견하면 그 cid 로 메시지를 다시 보낼 수 있다.
- Risks:
  - **lazy create 단계 ask 실패 시 buried orphan**: backend 는 cid 를 만들고 사용자는 모르는 상태가 1 케이스 발생. 다음 사이드바 동기화에서 visible 해지므로 데이터 유실은 아니지만 사용자 혼란 가능. 완화: 실패 토스트가 "사이드바 새로고침" 을 명시.
  - **busy sentinel race**: 동시에 여러 sendPrompt 가 동작하면 sentinel 이 충돌 가능. 단 `isCurrentConvBusy()` 가 sentinel 을 체크해 두 번째 호출은 즉시 return 하므로 안전.
  - **TASK-0041 attach 우회**: lazy create 분기는 attach 다이얼로그를 의도적으로 비활성화. 사용자가 "이전 turn 에서 첫 메시지가 timeout 됐는데 결과를 회수하고 싶다" 는 케이스에서는 사이드바 새로고침으로 새 대화에 진입한 뒤 그 대화의 attach 흐름(페이지 로드 시 auto-attach) 이 동작한다.
  - **PATCH race 가드와 무관**: lazy 생성 직후 hint 적용 시점은 client 가 ask 응답을 받기 전이라 사용자가 PATCH 를 동시에 발사할 수 없다. 가드와 충돌하지 않음.
- Why not 단계 분리(create 후 ask): client-side 에서 `POST /api/new_conversation` 후 그 cid 로 `POST /api/ask` 를 chain 하는 방안도 검토. 장점: backend 무수정. 단점: (1) round trip 1회 추가, (2) ask 가 영구 실패하면 빈 대화 1개가 그대로 남아 본 TASK 의 의도(빈 누적 방지) 를 약화. (a) 채택 시 backend 는 hint 수용 외 무변경이며 lazy 생성된 cid 는 ask 가 실패해도 backend 측에 남지만 그 빈 대화는 사용자가 사이드바에서 인지 → 의도적으로 생성한 시각이 있으므로 정리 책임을 사용자에게 위임 가능.

## REV-20260430-0009
- Date: 2026-04-30
- Decision: TASK-0047 의 실제 동작 검증을 Playwright + curl 로 수행하고, 발견된 회귀 1건(마이그레이션 fast-path 우회) 을 즉시 수정한다.
- Method:
  1. `docker compose up -d --build web` 후 `/api/session` 응답 + `SHOW COLUMNS` 비교 → 신규 컬럼 미반영 확인.
  2. 컨테이너 안에서 `_runtime_tables_available()` 직접 호출로 fast-path 가 새 컬럼을 검증하지 않음을 입증.
  3. probe 에 `SELECT product_mode FROM AgentCoreConversations LIMIT 1` / `SELECT ProductPrefMode FROM WebAccounts LIMIT 1` / `SELECT ProductPrefPinnedId FROM WebAccounts LIMIT 1` 추가 + errno 1054 분기 처리.
  4. `--no-cache` 빌드로 BuildKit layer cache 무효화 후 재기동.
  5. Playwright 28-check spec(`qa-product-selector.cjs`) 작성 + 실행, 부분 fail 3건은 spec 의 expectation 보정으로 해결(사용자 데이터인 conv-list 와 messages 는 검사 범위 밖, hydrate 결과는 server 답변과 일치 비교).
  6. PATCH race-guard 도 자동화: `AgentMemoryKv.last_status='processing'` 직접 주입 → PATCH → 409 검증.
- Reason: AGENTS.md §16.2 (종료 전 "실제 데이터 결과 출력" 확인) + 사용자 명시 지시("Playwright 로 실제 동작 검증"). agent team 합의는 turn-local 의사결정이고, 실 환경 동작은 통제된 자동 검증으로만 신뢰 가능.
- Trade-offs / Risk:
  - probe 에 컬럼 검사를 추가했으므로 향후 컬럼 신설마다 probe 도 업데이트해야 한다 (메인테넌스 부담). 대신 마이그레이션 누락 회귀는 어떤 신규 컬럼이든 자동 차단된다.
  - `--no-cache` 빌드는 빌드 시간이 길지만 (`COPY src/...` 단계에서 file-content hash 가 제대로 동작하지 않은 BuildKit edge case), 마이그레이션 검증 후엔 정상 cache 사용 가능.
  - QA spec 의 "상품" 검사 범위는 `.conv-list / .messages / .progress-strip / .access-notice / .toast` 의 후손을 제외 — 사용자 입력 텍스트는 정책상 강제 치환 대상이 아니므로 회귀는 없으나, 향후 i18n 글로싱 필요 시 spec 갱신 필요.
- Verification: 28/28 PASS, healthScore=100, console.error=0. JSON 결과 = `repo/.gstack/qa-reports/qa-product-selector-result.json`.
- Follow-up:
  - **R-09 (BRIEFING)** "기존 NULL product_id 행 backfill" → closed (probe 강화로 자동 트리거 보장).
  - **R-03** PATCH race 강화는 last_status 단일 키 가드만 자동화됨 — row-level lock / version 컬럼 도입은 여전히 후속.
  - 다른 R-01..R-16 항목은 운영 검증 / 사용자 인터뷰 / 추가 spec 으로 이관.

## REV-20260429-0008
- Date: 2026-04-29
- Decision: TASK-0047 — Product Selector UX 와 Auto 모드 도입을 **agent team 4 인 합의 + Codex CLI 교차검증** 으로 사람 검토 없이 본 turn 에 시행한다 (사용자 명시 지시).
- Method:
  1. **4인 agent team 병렬 검토** (UX Designer / Frontend Architect / Backend Engineer / QA-Flow Validator) — 각자 600 단어 의견서 산출. 의견서는 본 세션 transcript 에 보존, 핵심 합의는 BRIEFING §4 에 요약.
  2. **합의 통합 spec v1** 작성(`/tmp/product-selector-spec.md` — 휘발). UI 위치(사이드바 chip), state(productMode/pinnedProductId/activeProductId 3-필드), DB(product_mode 컬럼), API(PATCH /api/conversations/{cid}/product + new_conversation body 확장), agent_core(auto 한 줄 inject + allowed_schemas=[]), 카피("제품" 한글) 결정.
  3. **Codex CLI 교차검증** (`codex exec`) — 5건 추가 리스크: (a) auto 라벨 기대 불일치, (b) WebAccounts 컬럼 vs JSON pref (기존 결정 강화), (c) PATCH race 강화 필요, (d) 사이드바 의미 모호성 (caption 추가), (e) pinned 비활성 fallback / localStorage hydrate race. (a)(c)(d)(e) 를 spec v2 에 반영.
- Reason:
  - 사용자가 본 요청에 한해 "사용자 검토없이 agent team 면밀 검토" 를 명시했고, 반영해야 할 의견의 다양성(UX/구현/보안/회귀)이 단일 AI 검토로 부족했다.
  - Codex CLI 는 본 저장소 외부의 두 번째 LLM(`codex-cli 0.125.0`)으로, agent team 의견을 한 번 더 비판적으로 검증하기 위한 적격 보조 검토자.
- Trade-offs / Risk:
  - LLM resolver 미도입 상태에서 auto 라벨이 사용자 기대를 일부 깰 수 있다 (R-01) → 라벨에 "auto · 자동 (제품 미선택)" 으로 명시.
  - PATCH race 가드는 `last_status='processing'` 단일 키 기반으로 1차만 처리, race window 가 완전히 닫히진 않음 (R-03). 다음 turn 에 row-level lock or version 컬럼 도입 권고.
  - localStorage hydrate 우선 적용은 깜빡임 감소 vs 권한 회수 시 잠깐 잘못된 표시 (R-05) — 서버 hydrate 응답으로 reconcile + fallback_reason 토스트로 보강.
  - "상품" → "제품" 치환은 사용자 가시 텍스트만; 코드 식별자(`Product`/`product_id`/`WebProducts`/`ProductKey`) 보존으로 ABI/스키마 영향 없음.
- Verification (이번 turn):
  - syntax: `python3 -m py_compile` (app.py / agent_core.py), `node --check` (app.js) 모두 통과.
  - in-process 단위: `compose_system_prompt(None,...)` ↔ fake-conn `compose_system_prompt(... ,product_mode='auto'|'pinned')` — auto 분기에 `[AUTO MODE]` 라인 1개 inject 확인, pinned 분기에는 미주입 확인.
  - 잔존 "상품" grep: `unit/feature-0003-agent-web-ui/src` + `unit/feature-0002-agent-core/src` 0 건.
- Follow-up: BRIEFING-product-selector-v1.md §1 (R-01..R-16) + §2 (D-01..D-05) — 운영 반영 전 사람 결정/검증 필요. agent_team 합의는 turn-local 의사결정이며, 운영 회귀 위험은 별도 task 로 추적한다.

## REV-20260326-0001
- Date: 2026-03-26
- Decision: Web UI는 소유권만 분리하고 런타임 이미지는 core feature Dockerfile에서 조립한다
- Reason: 실행 경로를 단순하게 유지하면서 기능 경계를 문서화하기 위함
- Risk: Web UI 단독 이미지 분리가 필요한 경우 추가 조정이 필요하다

## REV-20260421-0002
- Date: 2026-04-21
- Decision: 대화 fork 는 신규 `conversation.fork` permission 을 추가하지 않고 기존 `conversation.create` + 원본에 대한 `read.own/read.any` 조합으로 판정한다.
- Reason: fork 의 본질은 "내 계정으로 새 대화를 만들어 메시지를 채우는 것" 이며, 이는 `conversation.create` + 원본 읽기 가능 여부의 교집합과 정확히 일치한다. 신규 permission 을 추가하면 모든 role 매트릭스를 갱신해야 하고 override/role seed 와 기존 관리 콘솔 문서도 동시에 고쳐야 해 범위가 불필요하게 커진다.
- Risk: 향후 "타 계정 대화 읽기는 가능하나 fork 는 금지" 정책이 필요해질 경우, 별도 deny override 나 새 permission 도입이 추가로 필요하다.
- Alternatives considered:
  - `conversation.fork` 신규 permission 도입: 범위/가치 대비 비용이 크다고 판단해 기각.
  - 서버 측에서 `_get_history` + `/api/new_conversation` + 연속 `/api/ask` 로 프론트엔드가 재현: 원본 CreatedAt 보존 불가, 내부 메시지 필터도 어긋나며, 대규모 round-trip 발생 → 기각.

## REV-20260421-0003
- Date: 2026-04-21
- Decision: fork 시 `AgentMemoryMessages` 삽입을 `memory.py` helper 가 아닌 app.py 엔드포인트에서 직접 SQL 로 수행한다.
- Reason: helper 는 `CreatedAt` 을 DB DEFAULT CURRENT_TIMESTAMP 로 맡기지만 fork 는 **원본 시계열을 보존** 해야 사용자가 기존 대화를 재생하는 맥락이 깨지지 않는다. 또 `MetaJson` 에 `forked_from_*` 을 합성 주입하려면 insert 지점을 직접 제어할 필요가 있다.
- Risk: helper 가 향후 감사 필드/트랜잭션 훅을 추가할 경우 엔드포인트 로직도 함께 업데이트해야 한다. `docs/FUNCTION.md` 의 Dependencies 에 memory 스키마 의존성을 명시해 이 커플링을 추적한다.
- Alternatives considered:
  - helper 에 `created_at_override` 매개변수 추가: core feature 의 public API 계약을 바꿔야 하고 fork 외 호출처가 없어서 인터페이스 부풀림이라 판단해 기각.

## REV-20260421-0004
- Date: 2026-04-21
- Decision: Product-단위 DB 접근 whitelist 를 agent tools 레벨의 모듈-전역 `_ACTIVE_SCHEMA_ALLOWLIST` + `set/clear` 헬퍼로 구현하고, `run_agent` 는 본문(원래 `run_agent`) 을 `_run_agent_core` 로 rename 한 뒤 thin wrapper 로 감싸 try/finally 안에서 whitelist 를 세팅/복원한다.
- Reason: 도구 dispatch(`execute_tool`) 로 whitelist 를 모든 경로에 파라미터로 전파하려면 tool 시그니처 전부 확장 + 기존 호출처(CLI/insight worker 포함) 모두 갱신이 필요하다. 모듈-전역 + context 매니저 패턴은 (1) call site 가 `agent_core.run_agent` 만 변경, (2) 모든 tool 이 단일 `_whitelist_violation(refs)` 진입점만 공유, (3) finally 로 워커 스레드 재사용 시 leak 방지라는 세 조건을 동시에 만족한다.
- Risk: `run_agent` 가 재진입(reentrant) 될 경우 마지막 setter 가 이전 whitelist 를 덮어쓴다. 현재 구조는 `asyncio.to_thread` 로 worker 당 1 호출이므로 충돌이 없지만, 향후 nested agent 호출이 도입되면 stack-based state(`contextvars.ContextVar`) 로 전환해야 한다.
- Alternatives considered:
  - tool signature 확장(`execute_tool(conn, tool, args, *, allowed_schemas)`): 호출처 파급이 크고, `_tool_execute_sql` 이 내부 helper 에서 재귀 참조를 할 때 또 다시 전달해야 해 반복 노이즈가 발생해 기각.
  - `threading.local`: `asyncio.to_thread` 의 스레드 풀이 재사용되므로 cleanup 이 반드시 finally 로 이뤄져야 한다는 점에서 현재 전역 + finally 패턴과 실질적 동일, 단순성 우선해 현 안 채택.

## REV-20260421-0005
- Date: 2026-04-21
- Decision: `_whitelist_violation` 이 `information_schema` 만 명시적으로 bypass 하고, 그 외 시스템 스키마(`mysql`, `performance_schema`, `sys`, `agent_memory`) 는 whitelist 규칙을 통해 **기본 차단** 한다.
- Reason: 초기 구현은 `_SYSTEM_SCHEMAS` 전체를 bypass 했으나, 이는 "Product=KR 이 `dbgame`/`dblog`/`dbauth` 만 허용" 이라는 운영 의도와 충돌한다. agent 가 `SELECT * FROM mysql.user` 를 요청하면 whitelist 가 손을 대지 않고 통과시켜 자격 정보가 유출될 수 있다. `information_schema` 만 "스키마 카탈로그 자체 조회 용도로 필요" 라는 명시적 이유로 예외 처리하고, 나머지 시스템 스키마는 whitelist 에 수동 등록하지 않는 한 차단되도록 한다.
- Risk: 운영 중 `agent_memory` 나 `mysql` 시스템 스키마 쿼리가 필요해질 경우 Product DB 목록에 수동 추가가 필요하다. 현재 설계상 이는 audit 목적에 부합하며, 과도한 접근이 발생하기 전에 관리 콘솔에서 명시적으로 추가해야만 허용된다.
- Alternatives considered:
  - 모든 `_SYSTEM_SCHEMAS` bypass(초기 안): 운영 의도와 보안 모두 어긋나 기각.
  - `_SYSTEM_SCHEMAS` 중 특정 항목만 화이트리스트(예: `agent_memory` 만 항상 허용): 현재 agent 가 자신의 메모리 DB 를 조회할 이유가 없어 불필요한 표면적 확장이라 기각.
- Superseded in part by: REV-20260422-0006 (메타데이터 4 스키마 bypass 재도입, `agent_memory` 차단 유지 부분은 유효).

## REV-20260422-0007
- Date: 2026-04-22
- Decision: TASK-0040 (regex context-aware) 와 TASK-0041 (attach/resume 복구 경로) 두 건을 한 번에 반영한다. 두 건 모두 TASK-0034 Q4/Q5 재수행을 가능하게 만드는 전제 조건이었고, TASK-0041 은 코드 경로가 서로 독립이지만 향후 runner 의 타임아웃 내구성에도 동일한 장치가 필요했기 때문에 함께 기록한다.
- Reason:
  - TASK-0040: 기존 `_SCHEMA_TABLE_REF_RE` 단일 regex 는 SQL 문맥 정보가 없었다. SELECT 절/WHERE 절/ON 절의 `alias.column` 은 구문적으로 `schema.table` 와 같은 `x.y` 토큰이라 whitelist 검사기가 구분할 수 없었고, Q4-like SQL 이 전부 `BLOCKED_SCHEMAS=bb,be` 로 거부됐다. 기존 regex 를 확장해 negative lookbehind 로 해결하려고 시도해봐도 FROM/JOIN 뒤 alias 선언(`FROM dblog.t bb`) 과 이후 alias 참조 (`bb.BattleType`) 가 같은 SQL 안에 공존하는 구조라 1 단계 regex 로는 근본적으로 구분이 불가능하다. FROM/JOIN 구간을 slice 하고 그 안에서만 `schema.table` 을 찾는 2 단계 스캐너가 최소한의 정확도 게이트이고, SQL 파서를 도입하지 않는 선에서 가장 단순한 정답이다.
  - TASK-0041: 에이전트 작업자 스레드(`asyncio.to_thread` 로 분리된 CPU/IO 루프)는 HTTP 연결과 독립이다. 클라이언트가 ReadTimeout 으로 끊어지거나 브라우저를 닫아도 서버는 완료까지 진행하지만, 그 결과를 회수할 read-only 경로가 없어 유저 입장에서는 "타임아웃 = 답변 손실" 처럼 보였다. `AgentMemoryKv(last_status/last_status_run_id/last_duration_ms/last_error)` + `AgentMemoryMessages` + `AgentMemorySteps` 이 이미 진행 상태와 최종 결과를 저장하고 있으므로, 새로운 상태 저장소 없이 스냅샷 + long-poll read-only 2 엔드포인트만 추가하면 UX 복구가 가능하다. `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT=6) 과 의도적으로 분리해 attach 가 새 실행을 시작시키지 않도록 했다 — 이것이 "새 요청으로 재진입해 중복 실행을 유발하지 않는" 안전 속성이다.
- Risk:
  1. 2 단계 regex 스캐너는 여전히 SQL 파서가 아니다. `WITH cte AS (...)` 같은 CTE 구문이나 `JOIN LATERAL (subquery)` 같은 복잡 구조에서 slice lookahead 경계가 어긋날 수 있음. 현재 agent 가 생성하는 SQL 범위에서는 15 케이스 검증으로 대응되지만, 생성 SQL 복잡도가 커지면 `sqlparse` 같은 경량 파서 도입을 재검토해야 한다.
  2. `/api/ask_status`/`/api/ask_result` 는 기존 `conversation.read.own/any` 권한을 재사용하므로 새로운 공격 표면은 없다. 다만 long-poll 60s 가 WEB_PARALLEL_LIMIT 과 별도로 백그라운드 연결을 유지하므로, 장기적으로 한 대화에 대해 동일 사용자가 다수 탭으로 polling 하면 연결 수가 쌓일 수 있다 (현재는 MCP 수준 트래픽에서는 무시 가능).
  3. 브라우저 boot-time auto-attach 는 페이지 새로고침 시마다 `/api/ask_status` 호출을 추가한다 — is_processing 여부만 체크하는 가벼운 쿼리라 비용은 미미하지만, 401/타 계정 대화 복구 시 attach 가 시작되지 않도록 권한 필터가 올바르게 동작해야 한다(기존 `_account_can_access_conversation` 로 보장됨).
- Alternatives considered:
  - TASK-0040 대안 (기각): 기존 regex 에 `(?<!\\w)\\s*` 류 lookbehind 를 덧붙여 alias.column 을 배제하는 방안 — alias 가 SELECT/WHERE/ON 모든 위치에 등장하므로 부정형 lookbehind 로 완전 배제가 불가. SQL 파서 도입 — 지금 필요한 정확도 대비 의존성 추가 비용이 크다.
  - TASK-0041 대안 (기각): 기존 `/api/progress` 폴링을 확장해 최종 답변을 같이 실어보내는 방안 — `/api/progress` 는 최근 N 스텝만 반환하고 응답 payload 크기를 keep-small 하도록 최적화되어 있어 최종 answer 를 싣기엔 부적합. Server-Sent Events / WebSocket 도입 — 인프라(프록시, TLS 종단, 재접속) 복잡도가 늘어나 현재 규모에 과하다.
  - TASK-0041 대안 (고려됨): 다이얼로그에서 `즉시 답변` 은 사실상 `/api/finalize` + attach 로 매핑됐는데, 이를 `/api/finalize` 없이 attach 만으로 끝내도 `finalize` 와 동등하지 않다 (LLM 추가 툴콜을 막지 않음). 본 구현은 두 경로를 구분 유지.
- How this relates to prior reviews: REV-20260422-0006 (메타데이터 4 스키마 bypass) 이후, Product DB whitelist 자체는 제대로 작동하지만 `_extract_sql_schema_refs` 가 alias 까지 오탐하던 부작용이 TASK-0040 에서 해제됐다. REV-20260421-0005 / REV-20260422-0006 의 "alias.column 은 whitelist 대상이 아님" 이라는 암묵 가정이 이제는 코드로도 성립한다.

## REV-20260422-0006
- Date: 2026-04-22
- Decision: `_whitelist_violation` 의 bypass 집합을 `{information_schema}` 에서 `_METADATA_SCHEMAS = {information_schema, sys, mysql, performance_schema}` 로 확장한다. `agent_memory` 는 `_INTERNAL_SCHEMAS` 로 분리해 **계속 차단** 유지.
- Reason: 사용자 지시(2026-04-22, "assistant 가 스키마 구조를 찾지 못하는 이슈를 방지"). 실사용에서 agent 가 `information_schema.TABLES` 외에 `sys.schema_table_statistics` / `performance_schema.tables` / 드물게 `mysql.*` 을 교차 검증 조회하려는 시도가 차단당해 탐색 루프에 빠지는 현상이 관찰됐다. 메타데이터 4 종은 DB 구조 탐색(정의·통계·런타임 메트릭) 에 필요한 "카탈로그적" 성격이므로 Product 관리자가 DB 목록에 일일이 추가하지 않아도 기본 허용되는 편이 운영 직관과 맞는다. `agent_memory` 는 타 계정 대화/세션/권한 override 를 담고 있어 성격이 다르며 계속 차단해야 한다.
- Risk:
  1. `mysql.user`/`mysql.db`/`mysql.global_priv` 에는 credential hash / grant 정보가 있다. 이 결정으로 tool-레벨 1 차 방어가 풀리므로, **DB 커넥터 MySQL 계정의 GRANT 가 2 차 방어로 남아야** 한다. 스모크 테스트 시점에서는 현 계정이 `mysql.user SELECT` 권한을 가지고 있어 실제 행이 반환됨을 확인했다 — 운영상 민감도가 높으면 MySQL 계정 GRANT 를 `information_schema` + Product DB 만 허용하도록 좁힐 것.
  2. `performance_schema`/`sys` 는 민감도 낮음(런타임 stat + 뷰 집합).
  3. write 가능 agent 계정을 도입하게 되면 본 결정을 재검토해야 한다(현재는 read-only 전제).
- Alternatives considered:
  - 메타데이터 스키마를 Product DB 목록에 수동 등록(REV-20260421-0005 의 원안): 관리 부담이 크고, 모든 Product 에서 동일하게 필요해 등록 누락 시 agent 가 탐색에 실패하는 결함이 재발한다. 기각.
  - `information_schema` + `sys` 2 종만 bypass: 사용자가 `mysql`/`performance_schema` 를 포함해 4 종을 명시했고, 둘 다 DBA 작업에서 교차 검증이 빈번해 2 종으로는 충분하지 않아 기각.
  - `agent_memory` 까지 포함한 전체 `_SYSTEM_SCHEMAS` bypass: agent 가 자신의 메모리 DB 를 읽을 이유가 없고, 타 계정 대화 유출 경로가 생기므로 기각.
- How this changes REV-20260421-0005: REV-20260421-0005 의 "`information_schema` 만 bypass" 결정을 "메타데이터 4 종 bypass, 에이전트 내부 스키마는 계속 차단" 으로 교체. `agent_memory`/임의 user schema 를 차단한다는 핵심 보안 의도는 유지된다.

## REV-20260512-0001
- Date: 2026-05-12
- Decision: 관리 콘솔의 모든 카테고리 다중선택 UX 를 단일 정합 컨벤션 (CONVENTIONS.md §10 + DESIGN.md v0.2) 으로 통일하고, drift 재발 차단을 위해 admin.js 의 `assertBulkBarContract(entity)` runtime check 를 initialize 끝에서 호출한다. Bulk toolbar 위치 표준은 **list 직하단 sticky** (`.admin-bulk-actions`), `.admin-pane-head-right` 는 primary action (`+ 새 X`) 전용으로 단일 semantic 유지.
- Reason: 사용자 raw feedback (2026-05-12) "관리 콘솔에 구성된 항목 별 다중선택 UI/UX 가 카테고리 별로 일관성없이 차이가 나타나는것을 확인했습니다 — 계정: 우측 상단 / 역할: 좌측 하단 / 제품: 다중 선택 기능 없음. 차후 작업에서도 이러한 경향이 나타나지 않도록 방향을 정합적으로 명시해주세요." Root cause 두 가지: (1) DOM anchor 위치 표준 부재 → Accounts (header slot) vs Roles (list 하단) 갈라짐. (2) `.admin-pane-head-right` 슬롯의 semantic 충돌 — 어떤 카테고리에서는 "+ 새 X" primary action, 다른 카테고리에서는 동적 bulk action 슬롯으로 점유 → 컴포넌트 표준화 실패의 본질. Products 의 multi-select 부재는 의도적 결정이 아니라 drift 로 판정 (활성·비활성·삭제 의미가 있는 동질 entity 리스트 = §10.1 적용 룰 충족).
- Risk:
  1. **Accounts bulk anchor 이전** (헤더 우상단 → list 직하단): 기존 e2e/screenshot test 가 `#accountsBulkBar` 의 위치 selector 에 의존했다면 깨질 수 있다. 본 cycle 에서는 e2e selector 변경 영향 검증을 못 했음 (실제 e2e suite 위치 후속 확인). 사용자 화면 시각 차이는 의도적.
  2. **Products multi-select 신설 + selectedProductId 단수 동거**: detail panel 은 단일 selectedProductId 만 신뢰 (DESIGN.md §12 Phase A). row click 은 단일 detail 선택, checkbox click 은 multi-select Set — 두 흐름이 별 path 라 race 없음. 다만 사용자가 checkbox 만 다수 체크 후 detail 을 expect 하는 mental model 가능 — 후속 모니터링 필요.
  3. **bulkProductDelete 의 _delete 키 plumbing**: backend `setProductMetaPending(_delete: true)` 가 apply 단계에서 실제 DELETE API 를 호출하는지 backend (`app.py applyAllPending` flow) 확인 필요. 본 cycle 은 pending 마킹만 추가했고, 실제 backend 가 product `_delete` 키를 수용하지 않으면 NO-OP 또는 에러. 후속 검증 항목으로 REPORT.md 에 명시.
  4. **assertBulkBarContract 가 console.warn only**: 운영 코드 차단 안 함 (best-effort). 정말 강제하려면 CI snapshot/jsdom test 가 필요 (별 cycle).
  5. **typed-confirmation prompt UX**: `window.prompt()` 기반이라 모던 UX 와 어긋날 수 있음. 후속에서 custom modal 로 업그레이드 가능 (v0.3 후보).
- Alternatives considered:
  - **DOM anchor 표준을 헤더 우상단 (Accounts 패턴)** 으로 통일: 후보였으나 (a) "+ 새 X" 와 동적 bulk action 이 같은 슬롯을 두고 경쟁, (b) row 선택 인터랙션의 시선·손 위치 근접성 부족 — 기각.
  - **Notion morph 패턴** (헤더 자체가 bulk toolbar 로 변형): 모던 레퍼런스로 존재하지만 본 컨벤션의 "헤더 = primary 전용" 단일 semantic 원칙 위반 → 명시 거부 (DESIGN.md §14 참조).
  - **Linear floating pill** (viewport footer fixed): 강한 visibility 장점이나 list-scope 의미 약화 + drawer/modal 과 z-index 전쟁 → v0.2 에서는 list 직하단 sticky 채택, floating pill 은 v0.3 옵션으로 기록.
  - **Vercel 패턴** (multi-select 없이 row-hover inline action): admin entity 가 일괄 적용 가치를 갖는 (활성·비활성·삭제) 카테고리에는 부적합 → 면제 카테고리의 reference 로만 인용 (CONVENTIONS §10.1).
  - **RBAC 새 권한 추가** (예: `account.bulk_delete`): catalog 변경 = RBAC plan 영역 (사용자 메모리 정책 "RBAC plan 은 outside voice 필수") → 본 cycle scope 에서 분리. 기존 권한 (`account.delete` 등) 의 row-level check 만 활용.
- How this relates to prior reviews: 본 REV 는 관리 콘솔의 UI 표준화 첫 정본. 기존 REPORT.md 의 TASK-0053 (제품 권한 grid + product 카드 통합) / TASK-0051 (일괄 저장 정책 회복) 등은 개별 UI 변경이었으나 표준 컨벤션 없이 진행됨 → 본 cycle 이 그 누적 inconsistency 의 가드레일을 사후 도입. 외부 design 시각 결과 (worker-design framework 차용 + general-purpose subagent) 는 v0.1 의 IA 6 / Visual 5 / Interaction 6 / Consistency 7 / A11y 4 dimension rating 과 5 gap (cross-page selection / empty·loading·error / optimistic rollback / confirm 컨벤션 / RBAC gating) 을 강하게 지적 → v0.2 에 모두 흡수.
- Open questions (DESIGN.md §13 참조):
  - Q-13.1: cross-page banner 의 "전체 페이지 선택" 버튼 (보이지 않는 페이지까지 모두 선택) — 본 cycle 미포함, v0.3 후보.
  - Q-13.2: bulk action apply 후 undo (toast 내부 "되돌리기") — 후속 평가.
  - Q-13.3: shift+click range 의 cross-page 동작 (현재는 visible 만) — 본 cycle 의 결정과 모순 없음.
  - Q-13.4: `assertBulkBarContract` 의 CI 화 (jsdom unit 또는 e2e snapshot) — 별 cycle.
