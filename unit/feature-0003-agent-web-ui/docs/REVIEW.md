---
doc_type: REVIEW
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

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
