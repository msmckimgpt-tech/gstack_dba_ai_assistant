---
doc_type: BRIEFING
feature_id: feature-0003-agent-web-ui
status: planning
edit_policy: rewrite
source_of_truth: false
related_task: TASK-0052 (C5 — 계정·역할 → 제품 권한 상속/override)
related_review: REV-20260506-0011 (TASK-0051 cycle 분리 결정)
plan_eng_review_date: 2026-05-06
outside_voice: codex (model gpt-5.5, reasoning=high)
---

# BRIEFING — C5: 계정·역할 → 제품 권한 상속/override

본 문서는 [TASK-0051](./TASK.md) cycle 에서 분리된 C5 의 implementation-ready plan 이다. `/plan-eng-review` (Section 1~4) + Codex outside voice 통합 결과를 반영하며, 다음 cycle 진입 시 `TASK.md §2.1 Implementation Plan` 의 source 가 된다.

## 1. 문제 정의 (실제로 닫는 보안 갭)

현재 [src/app.py](../src/app.py) 의 product 권한은 **존재하지 않는다**. 어떤 logged-in 계정이든 `conversation.ask` 권한만 있으면:

- `PATCH /api/conversations/{cid}/product` 으로 임의 active product 에 pin (현재 [L4140-4149](../src/app.py#L4140-L4149) 가 `IsActive` 만 검사)
- `POST /api/new_conversation` body 에 임의 `product_id` 명시 ([L4022~](../src/app.py#L4022))
- `POST /api/ask` body 에 임의 `product_id` hint 명시 ([L3870~](../src/app.py#L3870))
- `POST /api/fork_conversation` 으로 임의 product 의 대화를 fork ([L4270~](../src/app.py#L4270))
- `GET/PUT /api/auth/me/system-prompt` 로 임의 product 의 account scope prompt read/write ([L6062, L6084](../src/app.py#L6062))
- 기존 pinned 대화는 `_save_account_product_pref` 만으로도 인접 product 에 pref 가 저장됨 ([L1541](../src/app.py#L1541))

C5 는 이 6 개 mutation 경로 + 1 개 read 경로의 per-account access guard 를 도입한다.

## 2. 결정 요약 (`/plan-eng-review` + Codex outside voice)

| ID | 질문 | 결정 | 근거 |
|---|---|---|---|
| **D1** | 데이터 모델 | **B** — 권한 코드 + 기존 override 재사용 (D1-B 유지). 단, RBAC engine DB-driven 마이그레이션을 C5 본체로 흡수 | DRY + 미래 ABAC 확장 포섭 + 권한 grid 일관성. Codex 가 지적한 "정적 catalog 가정" 은 마이그레이션으로 해결 |
| **D2** | 마이그레이션 default | **A** — 기존 모든 role 에 product 접근 grant backfill | 운영 중 (25 계정/6 역할) 호환성 우선. 단 표현은 "compatibility-first, NOT secure-by-default" 로 명시 (Codex Claim 5) |
| **D3** | Product CRUD lifecycle | **A** — POST/DELETE 가 권한 row 까지 한 트랜잭션. 단 명시적 `start_transaction()` + `commit/rollback` (Codex Claim 2 — autocommit=True 기본) | drift 회피 + 부분 실패 차단 |
| **D4** | `/api/sessions/me` filter | **A 변경** — Codex Claim 6 수용: end-user `/api/session` 은 effective products 만 반환, admin `/api/admin/products` 는 전체 유지. ("FE 숨김 ≠ 보안 경계") | product 명 자체가 고객/국가/내부 프로젝트 노출 가능 |

> **D4 변경 사유**: 초기 review 에서 D4-B (전체 returns + FE filter) 를 선택했으나, Codex Claim 6 에서 product 명 정보 노출 위험을 지적. 사용자가 "Codex review 의도를 통해 작업" 지시 → D4 를 보안 경계 분리 방향으로 수정.

## 3. 아키텍처 다이어그램

### 3.1 데이터 모델 (D1-B + Codex Claim 1 마이그레이션 포함)

```
WebPermissions (기존 — D1-B 마이그레이션 후 dynamic catalog 의 source-of-truth)
┌─────────────────────────────────────────────────────────────────┐
│ Id  PK                                                          │
│ Code         e.g. "console.access", "product.access.kr"          │
│ Label        e.g. "관리 콘솔 접근", "제품 접근 — KR"            │
│ Description                                                     │
│ GroupName    {console, account, role, conversation, product, …} │
│ IsDynamic    TINYINT  ★ NEW — product CRUD 가 관리하는 row 표시 │
│ ProductId    BIGINT NULL  ★ NEW — IsDynamic=1 이면 FK to Product │
└─────────────────────────────────────────────────────────────────┘
       │
       ├──< WebRolePermissions (RoleId, PermissionId)  (기존)
       │
       └──< WebAccountPermissionOverrides              (기존)
            (AccountId, PermissionId, OverrideValue: allow/deny/inherit)

WebProducts (기존, 변경 없음)
WebProductDatabases / WebSystemPrompts (기존, 변경 없음)
AgentCoreConversations.product_id FK (기존, in_use guard 유지)
```

**핵심 변경**: `WebPermissions` 에 `IsDynamic`/`ProductId` 두 컬럼을 추가해 product 와 1:1 lifecycle 인 권한 row 를 식별. 이로써 product DELETE 시 cascade 가 명확하고, dynamic vs static 권한이 코드/UI 에서 구분 가능.

### 3.2 권한 계산 흐름 (Codex Claim 1 마이그레이션 후)

```
[Login / session resolve]
  │
  ├── _resolve_account_permissions(conn, account_id)  ★ 변경: DB-driven
  │     │
  │     ├── SELECT all from WebPermissions  → permission_catalog (dynamic)
  │     ├── SELECT WebRolePermissions JOIN role  → base_codes
  │     ├── SELECT WebAccountPermissionOverrides  → overrides
  │     └── _apply_permission_overrides(catalog, base_codes, overrides)
  │           ★ 변경: empty_map 을 catalog 기반으로 build (정적 PERMISSION_CODES 미사용)
  │
  └── account["permissions"] = {code: bool}  ← request 단위 cache (기존 패턴)

[Mutation endpoint guard]
  │
  └── _account_has_product_access(account, product_id_or_key)
        │
        ├── product_id 입력 시 → products cache 에서 product_key 조회
        ├── code = f"product.access.{product_key.lower()}"
        └── return account["permissions"].get(code, False)
```

### 3.3 Product CRUD 트랜잭션 (D3-A + Codex Claim 2)

```
POST /api/admin/products
  │
  ├── conn.autocommit = False  ★ NEW
  │
  ├── INSERT WebProducts (...)        → product_id
  │
  ├── INSERT WebPermissions (Code='product.access.<key>', GroupName='product',
  │       IsDynamic=1, ProductId=product_id)
  │       → permission_id
  │
  ├── INSERT WebRolePermissions
  │     SELECT r.Id, %permission_id%
  │     FROM WebRoles r                ★ D2-A backfill: 모든 기존 role 자동 grant
  │
  ├── conn.commit()  / rollback on any failure
  └── conn.autocommit = True

DELETE /api/admin/products/{product_id}
  │
  ├── (기존) AgentCoreConversations FK in_use guard → 400 if in use
  │
  ├── conn.autocommit = False  ★ NEW
  │
  ├── DELETE WebSystemPrompts WHERE ProductId=%s     (기존)
  ├── DELETE WebProductDatabases WHERE ProductId=%s  (기존)
  │
  ├── DELETE WebRolePermissions WHERE PermissionId IN (
  │     SELECT Id FROM WebPermissions WHERE ProductId=%s)  ★ NEW
  ├── DELETE WebAccountPermissionOverrides
  │     WHERE PermissionId IN (...)                           ★ NEW
  ├── DELETE WebPermissions WHERE ProductId=%s              ★ NEW
  │
  ├── DELETE WebProducts WHERE Id=%s                          (기존)
  │
  ├── conn.commit()  / rollback on any failure
  └── conn.autocommit = True
```

### 3.4 Guard 매트릭스 (Codex Claim 3 + 4 통합)

| # | 경로 | 현재 | C5 가드 |
|---|---|---|---|
| G1 | `PATCH /api/conversations/{cid}/product` | `IsActive` 만 | + `_account_has_product_access(account, pinned_id)` |
| G2 | `POST /api/new_conversation` body `product_id` | 무검증 | + `_account_has_product_access(account, product_id)` |
| G3 | `POST /api/ask` body hint `product_id` | 무검증 | + `_account_has_product_access(account, hint_pid)` |
| G4 | `POST /api/ask` 기존 conv 의 `product_id_for_run` | **무검증 (Codex Claim 3)** | + `_account_has_product_access(account, product_id_for_run)` 검사 후 권한 회수 시 처리 |
| G5 | `POST /api/fork_conversation` source product 상속 | 무검증 + `product_mode` 복사 버그 | + access guard + product_mode 복사 fix |
| G6 | `_save_account_product_pref(account, mode, pinned_id)` | 무검증 | + access guard (pref 저장 시점에) |
| G7 | `GET /api/auth/me/system-prompt?product_id=<X>` | 무검증 | + `_account_has_product_access` |
| G8 | `PUT /api/auth/me/system-prompt` body `product_id` | 무검증 | + `_account_has_product_access` |

**G4 의 권한 회수 처리 정책 (Codex Claim 3 의 운영 시나리오)**: 사용자에게 권한이 있을 때 pin 한 대화가 권한 회수 후 다시 ask 될 때:
- **Option α (권장)**: 403 차단 → frontend 에 "이 대화의 제품 접근 권한이 회수되었습니다. auto 모드로 전환 후 진행해 주세요." 안내 토스트
- Option β: auto 모드로 자동 강등 + 사용자에게 알림
- Option γ: 차단 없이 메타데이터 4 종 schema 만으로 진행 (격리 수준 낮음)

본 briefing 은 α 권장. 구현 시점에 사용자 검토 필요.

### 3.5 API 응답 분리 (D4 — Codex Claim 6)

```
/api/session  (end-user)               /api/admin/products  (admin)
─────────────                          ───────────────────────
products[] = effective only            products[] = ALL active
default_product_id = 사용자 접근 가능   admin 에게는 product 전체 카탈로그 노출 OK
                                        (admin 은 console.manage 권한자라 의도된 노출)

product_pref 는 effective 만
conversation_product 는 그대로
```

마이그레이션: `_list_products(conn, *, include_inactive=False)` 에 신규 `account_filter: dict | None = None` 인자 추가. account 가 주어지면 effective product 만 return. `/api/admin/products` 는 account_filter=None 으로 호출. 기존 호출처 (`_list_products(conn)`) 는 default 그대로 — 코드 변경 표면 최소.

## 4. 마이그레이션 plan (D2-A + Codex Claim 1)

**Phase 0: 사전 (코드 deploy 전)**
- 본 briefing 을 사용자가 검토. 운영 영향 인지.

**Phase 1: 코드 deploy (Phase 1A → Phase 1B 순서로)**

Phase 1A — RBAC engine DB-driven 마이그레이션 (Codex Claim 1):
- `_empty_permission_map(catalog)` 가 catalog (전달 인자) 기반으로 dict 생성. PERMISSION_CODES static 가정 제거.
- `_apply_permission_overrides(catalog, base_codes, overrides)` 가 catalog 기반.
- `_validate_permission_codes(codes, catalog)` 가 catalog 기반.
- `_normalize_override_payload(payload, catalog)` 가 catalog 기반.
- `_permission_catalog_payload(conn)` 가 WebPermissions 에서 동적 fetch (기존 PERMISSION_DEFINITIONS 는 product 가 아닌 권한의 seed 로만 사용).
- `_resolve_account_permissions` 가 매 request 마다 catalog + base + override 를 fetch (request 단위 cache). 기존에는 catalog 가 implicit 였음.
- 이 단계는 **product 권한 도입 없이도** 안전하게 deploy 가능 (catalog 가 정적이든 동적이든 결과 동일).

Phase 1B — product 권한 도입:
- `_ensure_web_tables` 에 idempotent backfill SQL 실행:
  ```sql
  -- (1) WebPermissions IsDynamic/ProductId 컬럼 추가
  ALTER TABLE WebPermissions ADD COLUMN IsDynamic TINYINT(1) NOT NULL DEFAULT 0;
  ALTER TABLE WebPermissions ADD COLUMN ProductId BIGINT NULL;
  ALTER TABLE WebPermissions ADD INDEX IX_WebPermissions_ProductId (ProductId);

  -- (2) 기존 product 들에 대해 권한 row 자동 생성
  INSERT IGNORE INTO WebPermissions (Code, Label, Description, GroupName, IsDynamic, ProductId)
  SELECT
    CONCAT('product.access.', LOWER(p.ProductKey)),
    CONCAT('제품 접근 — ', p.Name),
    CONCAT('이 계정은 ', p.ProductKey, ' 제품에 접근 가능합니다.'),
    'product', 1, p.Id
  FROM WebProducts p;

  -- (3) D2-A backfill: 기존 모든 role 에 grant
  INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
  SELECT r.Id, perm.Id
  FROM WebRoles r
  CROSS JOIN WebPermissions perm
  WHERE perm.GroupName = 'product';
  ```
- 이 SQL 들은 idempotent 라 재실행 안전 (`INSERT IGNORE`).
- 마이그레이션 report (운영 transparency, Codex Claim 5):
  ```
  [C5 migration] WebPermissions: +N product permission rows
  [C5 migration] WebRolePermissions: +M role-product grants (default-grant for backward compat)
  [C5 migration] 관리자 검토 권장: 권한 회수가 필요한 (role × product) 조합을 admin console 에서 deny override 추가
  ```
  → `_ensure_web_tables` 가 backfill 수행 후 `print` 또는 `logger.info` 로 1 회 기록.

Phase 1C — guard 도입 + 응답 분리 (D4):
- G1~G8 가드 모두 추가.
- `/api/session` 의 products[] filter (effective).
- `/api/admin/products` 는 그대로 전체 반환.
- `compose_system_prompt` 변경 없음 (single product per turn 모델 유지).

Phase 1D — admin UI:
- `PERMISSION_GROUP_ORDER += "product"` (admin.js).
- `PERMISSION_GROUP_LABELS["product"] = "제품"` (admin.js, app.py 양쪽 동기).
- 기존 `renderPermissionGrid` 가 자동으로 product group 을 렌더 (변경 없음).
- 역할/계정 detail 의 권한 grid 에 "제품" 그룹이 자동 추가 표시.

**Phase 2: 운영 검증**
- HTTP smoke + browse DOM smoke (§5 test plan 참조).
- 운영자 (admin) 에게 권한 회수가 필요한 (role × product) 조합 검토 요청.
- 회수가 필요하면 admin console → 역할 detail → product group → 해당 chip uncheck → footer 모두 적용.

## 5. Test plan (Codex Claim 9 통합 — negative HTTP test 강제)

본 codebase 의 패턴 (HTTP curl smoke + `/browse` DOM smoke + TEST.md §1~§2 rewrite + §3 append-only) 을 따른다. pytest 미도입.

### 5.1 P0 CRITICAL — 보안 갭 직접 해소 (negative HTTP test 필수)

| Test | 시나리오 | 기대 |
|---|---|---|
| T01 | bootstrap_admin (admin role) → `PATCH /api/conversations/{cid}/product` to KR | 200 |
| T02 | operator role 계정 (KR 권한 deny override) → 같은 PATCH | **403** |
| T03 | sales role 계정 (KR 권한 없음) → 같은 PATCH | **403** |
| T04 | T03 계정 → `POST /api/new_conversation` body `product_id=KR.id` | **403 또는 400** |
| T05 | T03 계정 → `POST /api/ask` body `product_id=KR.id` (lazy creation) | **403** |
| T06 | T01 admin 이 대화를 KR 로 pin → admin 의 KR 권한 회수 → `POST /api/ask` 같은 cid 로 | **403 (G4 검증)** |
| T07 | T03 계정 → `POST /api/fork_conversation` source = T01 의 KR 대화 | **403 또는 auto 강등** |
| T08 | T03 계정 → `GET /api/auth/me/system-prompt?product_id=KR.id` | **403** |
| T09 | T03 계정 → `PUT /api/auth/me/system-prompt` body `product_id=KR.id` | **403** |

### 5.2 P0 CRITICAL — Override 우선순위 (D2-A 유효성 검증)

| Test | 시나리오 | 기대 |
|---|---|---|
| T10 | sales role 에 KR grant (default after backfill) + sales 계정 X 에 deny override | account X 는 KR 접근 불가 |
| T11 | sales role 에 KR 미grant + sales 계정 Y 에 allow override | account Y 는 KR 접근 가능 |
| T12 | T10 의 deny override 를 inherit 로 변경 | account X 는 다시 KR 접근 가능 |

### 5.3 P0 CRITICAL — Lifecycle (D3-A 트랜잭션)

| Test | 시나리오 | 기대 |
|---|---|---|
| T13 | `POST /api/admin/products` (key=FR) → DB 검사 | WebProducts row + WebPermissions(`product.access.fr`, IsDynamic=1, ProductId=N) row + WebRolePermissions row 6 개 (모든 role) |
| T14 | T13 직후 `GET /api/admin/permissions` | `product.access.fr` 가 catalog 에 등장, group='product' |
| T15 | T13 직후 모든 role 가 FR access 보유 (effective check) | 모든 role 의 effective permission map 에 `product.access.fr=true` |
| T16 | `DELETE /api/admin/products/{FR.id}` (in_use=0) | WebProducts/WebProductDatabases/WebSystemPrompts/WebPermissions/WebRolePermissions/WebAccountPermissionOverrides 의 FR-관련 row 모두 0 |
| T17 | `DELETE /api/admin/products/{KR.id}` (KR 에 in_use 대화 1개 이상) | 400 + 메시지 + 어떤 row 도 변하지 않음 (rollback) |
| T18 | 의도적 INSERT 실패 injection (예: WebPermissions Code UNIQUE 위배) → POST /api/admin/products | 500 + WebProducts 에도 row 없음 (트랜잭션 rollback 검증) |

### 5.4 P0 CRITICAL — 마이그레이션 idempotent

| Test | 시나리오 | 기대 |
|---|---|---|
| T19 | `_ensure_web_tables` 1 회 실행 후 row 수 측정 → 다시 실행 → row 수 측정 | delta=0 (INSERT IGNORE 동작) |
| T20 | `_ensure_web_tables` 첫 실행 직후 운영 데이터 검사 | 25 계정 × 6 역할 모두 권한 회귀 0 (기존 동작 유지) |

### 5.5 P0 CRITICAL — TASK-0051 회귀 (admin 일괄 저장 통합 영역)

| Test | 시나리오 | 기대 |
|---|---|---|
| T21 | TASK-0051 의 admin DOM smoke 6 항목 (REPORT.md §8) | 모두 통과 (회귀 없음) |
| T22 | 역할 detail 권한 grid 에 product group 신규 노출 | "제품" 라벨 + product.access.* chip 들 |
| T23 | 권한 변경 후 footer "모두 적용" 클릭 | pending 0 + 새 권한 즉시 effective |

### 5.6 P1 — Cross-feature regression

| Test | 시나리오 | 기대 |
|---|---|---|
| T24 | TASK-0048 lazy creation (빈 대화 차단) | 회귀 없음 |
| T25 | TASK-0047 product chip + auto 모드 | 회귀 없음 |
| T26 | TASK-0036 compose_system_prompt 3 계층 조립 | 회귀 없음 |
| T27 | TASK-0039 메타 4 schema bypass | 회귀 없음 |

### 5.7 P2 — DOM/UX

| Test | 시나리오 | 기대 |
|---|---|---|
| T28 | end-user `/api/session` 응답에 effective products 만 노출 | 권한 없는 product 누락 |
| T29 | 사이드바 chip option 에 effective products 만 (FE filter) | 권한 없는 product 옵션 부재 |
| T30 | 권한 회수 후 reload | chip 이 자동으로 auto 또는 default 로 강등 |

총 30 case. T01~T20 (P0) 는 cycle 완료 게이트.

## 6. NOT in scope

| 항목 | 사유 |
|---|---|
| 제품별 세부 권한 (e.g., "KR 의 prompt 만 관리") | C5 의 dynamic catalog 가 들어오면 자연스럽게 추가 가능. 본 cycle 은 "접근 가능 여부" 만 |
| 제품 비활성/활성 시 권한 자동 토글 | IsActive=0 product 도 권한 row 는 유지 (재활성 시 권한 그대로). UX 수동 |
| `compose_system_prompt` 의 effective products list 주입 | 단일 product per turn 모델 유지 — 다중 product 동시 컨텍스트는 별 cycle |
| Sales lane 격리 강화 (`AgentMemoryFacts` 분리) | TASK-0044 wedge 에 속함, C5 와 직교 |
| product 권한 회수 시 사이드바 표시 변경 (auto fallback UX) | G4 의 Option α (403 + toast) 만 본 cycle. UX 정교화는 별 cycle |
| GitHub issue + PR 분리 | 현 branch `feat/adopt-external-anchor-v3.2.0-rc` 는 internal feat/* — issue 발급 후 별도 cycle |

## 7. What already exists (기존 자산 재사용)

| 자산 | 위치 | C5 에서 재사용 |
|---|---|---|
| `_apply_permission_overrides()` | [app.py:610](../src/app.py#L610) | catalog 인자만 추가 + tri-state 로직 그대로 |
| `WebAccountPermissionOverrides` | [app.py:2140](../src/app.py#L2140) | product 권한 override 도 동일 테이블 사용 |
| `WebRolePermissions` | (기존) | product 권한 grant 도 동일 테이블 |
| `renderPermissionGrid()` | [admin.js:118](../src/static/admin.js#L118) | 'product' group 자동 노출 — 신규 admin UI 0 |
| `_account_has_permission()` | [app.py:661](../src/app.py#L661) | `_account_has_product_access` 가 내부 호출 |
| TASK-0051 의 `applyAllPending()` 6 단계 | [admin.js](../src/static/admin.js) | 권한 변경은 기존 role/account pending bucket 사용 — 신규 bucket 0 |
| TASK-0036 의 `_product_allowed_schemas` | [app.py:1483](../src/app.py#L1483) | 변경 없음 — schema whitelist 와 product access 는 직교 |

## 8. Failure modes (실서 발생 가능 시나리오)

| # | 실패 시나리오 | 가드 | 검증 | 사용자 노출 |
|---|---|---|---|---|
| F1 | RBAC engine 마이그레이션 후 권한 lookup 이 누락된 catalog 항목 (race) | request 단위 cache + catalog DB 조회 | T19/T20 | 사용자 1 회 401 → 재로그인 시 정상 |
| F2 | Product CRUD 트랜잭션 부분 실패 (autocommit 누락) | `start_transaction()` + rollback | T18 | API 500 + 운영자 알림 |
| F3 | G4 누락으로 권한 회수 후에도 pinned 대화 ask 진행 | G4 가드 | T06 | **CRITICAL — Codex 가 직접 지적** |
| F4 | product_key 변경 (key='kr' → 'KR') | product_key immutable 정책 + UI 에서 read-only | (ALTER 차단으로 검증) | 권한 row 와 drift |
| F5 | DELETE product 이후 같은 key 로 재생성 | 같은 key 의 과거 override 가 사라지는 정책 명시 | T16 후속 INSERT | drift 가능 — admin 에게 명시적 안내 |
| F6 | `/api/session` filter 적용 후 기존 frontend 가 누락 product 를 참조 | products[] missing 시 chip 자동 'auto' fallback | T29 | 사용자 인지 가능, 보안 우선 |
| F7 | 마이그레이션 backfill 중 INSERT IGNORE 가 race 와 만나 중복 생성 | UNIQUE constraint (`Code`) | T13/T19 | DB-level 차단 |
| F8 | admin 이 자기 자신의 마지막 product access 를 deny override 로 잠가 lockout | admin 보호 (`product.manage` 권한자는 모든 product 자동 grant) | (보호 로직 별도 검토 필요) | **별 cycle — 본 briefing 의 NOT in scope** |

## 9. 파일 변경 일람 (구현 시점 추정)

| 파일 | 변경 추정 | 종류 |
|---|---|---|
| `src/app.py` | +~350 lines | RBAC engine refactor + 권한 헬퍼 + 8 가드 + 트랜잭션 + product CRUD 확장 + bootstrap backfill + `/api/session` filter |
| `src/static/admin.js` | +~30 lines | PERMISSION_GROUP_ORDER/LABELS 갱신 (라벨 1 줄 + group 1 줄), product chip filter |
| `src/static/app.js` | +~15 lines | end-user product chip filter (effective only) |
| `src/static/admin.html` | +2 lines | cache-bust |
| `src/static/index.html` | +2 lines | cache-bust |
| `docs/TASK.md` | rewrite | TASK-0052 등록 + §2.1 plan |
| `docs/MODIFY.md` | append | CHG entry |
| `docs/REVIEW.md` | append | REV entry (D1-D4 + Codex finding 통합 근거) |
| `docs/REPORT.md` | rewrite | Summary + Recent + Human Attention 갱신 |
| `docs/TEST.md` | rewrite §1~§2 + append §3 | 30 case 등록 + 결과 |
| `docs/FUNCTION.md` | rewrite (해당 시) | AC 추가 (product 접근 권한 모델) |
| `docs/STATUS.md` | rewrite | feature-0003 행 갱신 |
| `docs/LEARNINGS.md` | append | LRN entry (정적 catalog blindspot 학습) |

총 12 파일. 본 briefing 자체는 별도 (BRIEFING-c5-...).

## 10. Worktree 병렬화

본 cycle 은 phase dependency 가 강해 sequential 권장:

```
Phase 1A (RBAC engine 마이그레이션, 단독 deploy 가능)
  ↓
Phase 1B (product 권한 backfill — 1A 완료 후)
  ↓
Phase 1C (8 가드 도입 — 1B 완료 후)
  ↓
Phase 1D (admin UI group label — 1C 완료 후)
  ↓
Phase 2 (운영 검증)
```

병렬 lane 발견 사항: docs (TASK/MODIFY/REVIEW/REPORT/TEST) 갱신은 phase 1A~1D 와 병렬 가능 — 단 같은 파일 내라 1 worktree 로 처리 권장. 코드 lane 1 + docs lane 1 의 분리는 가능하나 ROI 낮음.

## 11. Codex outside voice — 통합 finding 표

| Claim | Codex 지적 | C5 plan 반영 |
|---|---|---|
| 1 | 정적 PERMISSION_CODES 가정에 5 함수가 hardwired — D1-B 채택 시 RBAC engine DB-driven 마이그레이션이 본체 | Phase 1A 로 명시. catalog 인자 전달 방식. ✅ |
| 2 | `autocommit=True` — D3-A 의 트랜잭션 롤백은 명시적 begin/commit 필요 | §3.3 + F2 + T18 ✅ |
| 3 | `/api/ask` 의 기존 conv `product_id_for_run` 시점에 가드 누락 | G4 추가 + T06 + F3 ✅ |
| 4 | 추가 가드 4 곳 누락 (`/api/new_conversation`, `/api/auth/me/system-prompt` GET/PUT, fork product_mode 복사 버그) | G2/G7/G8 + G5 fix + T04/T08/T09 ✅ |
| 5 | D2-A 는 호환성 우선이지 secure-by-default 아님 + pending/sales/operator 무차별 grant 는 보안 개선 폭 약화 | §2 D2 표현 수정 + 마이그레이션 report (Phase 1B) + admin 검토 권장 ✅ |
| 6 | `/api/session` 응답에 모든 product 명 노출 = 정보 노출 | D4 변경 — `/api/session` filter, `/api/admin/products` 전체 유지 ✅ |
| 7 | 동적 permission code 의 migration 부채 (ProductKey immutable, delete/recreate 손실, FK-less drift, per-product action 권한 미래 불충분) | F4/F5 + NOT in scope (per-product action) + Phase 0 명시 ✅ |
| 8 | "원래 sketch (Approach A) 가 더 작을 가능성" | 사용자 결정으로 D1-B 유지 — Codex 지적은 acknowledge 하되 user override |
| 9 | 수동 smoke 부족 — direct HTTP negative test 필수 | T01-T09 (7 negative cases) + T10-T12 override 우선순위 + T18 트랜잭션 injection ✅ |

## 12. 결론 + 다음 단계

본 plan 은 implementation-ready. 다음 cycle 진입 시:

1. **TASK-0052 발급**: TASK.md §2 Task Queue 에 항목 추가 + §2.1 Implementation Plan 으로 본 briefing 의 §3-§5 footer 채택.
2. **REPORT.md §8 갱신**: "C5 다음 cycle 권고" 항목을 본 briefing 링크로 교체.
3. **운영자 사전 안내**: D2-A backfill 이 운영 데이터의 25 계정 × 6 역할 × N product (현재 1) 에 권한 row 를 추가한다는 점을 인지. cycle 완료 후 권한 회수가 필요한 조합 검토.
4. **Phase 1A 단독 deploy 가능성 검토**: RBAC engine 마이그레이션은 product 권한 도입 없이도 안전하게 deploy 가능 (catalog 가 정적이든 동적이든 결과 동일). 분리 commit 권장.
5. **G4 의 권한 회수 처리 정책 (α/β/γ)**: 구현 직전 사용자 검토 필요. α 권장.
6. **F8 (admin lockout 보호)**: 구현 직전 별도 검토. 본 briefing 은 NOT in scope 이지만 운영 위험 인지 필요.

## 13. 마이그레이션 부채 (LEARNINGS.md 등재 권고)

본 review 에서 발견된 학습:

- **정적 catalog 가정 blindspot**: `_apply_permission_overrides` 가 dictionary 의 `if code in permissions:` 으로 silently drop — 매우 미묘. 외부 시각 (Codex) 가 catch. AI 1차 review 만으로는 놓칠 가능성 높음 → 향후 RBAC 변경 plan 은 반드시 outside voice 호출.
- **DRY 의 함정**: "기존 패턴 재사용" 이 표면적으로 작아 보여도 hot path 가 정적 가정에 묶여 있으면 실제 변경은 그 가정을 푸는 것이 본체. 코드 grep 으로 catalog touch 전수 확인 후 결정해야 함.

이 두 항목은 cycle 완료 시 [docs/LEARNINGS.md](../../../docs/LEARNINGS.md) (프로젝트 수준) 에 LRN entry 로 등재.
