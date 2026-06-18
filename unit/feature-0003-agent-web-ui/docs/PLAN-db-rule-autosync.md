---
doc_type: PLAN
scope: feature-0003-agent-web-ui
status: in-progress
edit_policy: rewrite
related: [TASK-20260618T044318-ai-claude-db-rule-autosync, REQ-20260618-0322, PROPOSAL-frequent-db-config-changes]
risk: Critical
created: 2026-06-18
---

# PLAN — 제품 DB allowlist 정규식 규칙 자동 동기화 (안전 하이브리드 + 백그라운드)

## 0. 사용자 결정 (2026-06-18, AskUserQuestion)
1. 규칙을 한 번 구성하면 데이터소스 변화 시 제품에 자동 반영 → **자동 즉시 적용** 선택.
2. outside-voice 가 순수 자동적용을 **NOT-SHIP** → **안전 하이브리드** 선택(명확·cap 이하=자동, 광범위·신규·모호=pending 승인).
3. 범위 → **풀스코프(백그라운드 무인 동기화 포함)** 선택.

## 1. 문제 / 목표
제품 allowlist(`WebProductDatabases`)는 DB 이름을 정적 박제 → 데이터소스 DB 추가/삭제 시 자동 반영 안 됨.
정규식 규칙을 (제품×데이터소스)별로 저장하고, 데이터소스 변화 시 규칙을 재평가해 일치 DB 를 제품에
(반)자동 반영한다. allowlist 는 에이전트의 **실제 데이터 접근 경계**(set_active_schema_allowlist,
fail-closed)이므로 안전 하이브리드 + 안전장치 필수.

## 2. outside-voice BLOCKER → 대응 (모두 반영)
- **B1 (broad/new 자동 GRANT 위험)**: 자동적용은 `len(new) ≤ Cap` AND 모호성 없음일 때만. Cap 초과/모호 →
  **pending(승인 보류)**, 절대 자동 GRANT 금지. Cap 은 *withhold* (사후경고 아님). 기본 Cap=3.
- **B2 (ReDoS)**: 규칙 저장 시 패턴 검증 — 길이 ≤ 200, `re.compile` 성공, 중첩 수량자(`(x+)+`/`(x*)+`)·
  backreference 거부, 앵커(`^`,`$`) 권장. 매칭은 후보 수 bound + 백그라운드는 매칭을 워커 타임아웃 보호.
- **B3 (actor-less 감사)**: 규칙에 `CreatedByAccountId` 저장. 자동/백그라운드 적용 audit 은 전용 action
  (`admin.product.db.autoadd` / `db.staged` / `db_rule.*`) + change_json 에 rule_id·creator·trigger·names.
- **B4 (manual/rule clobber)**: `WebProductDatabases.Source ENUM('manual','rule')` 추가(기존 행 → manual
  마이그레이션). 불변식: **manual 우선**. 수동 PUT 은 Source='manual' 행만 교체(rule 행 보존), 동일 schema
  가 manual 로 들어오면 그 schema 의 rule 행 삭제(manual 승격). reconcile 은 Source='rule' 행만 add/remove,
  manual 절대 미변경. 제거는 v1 비활성(additive only) — 끊긴 DB 는 drift 표면화.
- **B5 (대소문자)**: 매칭·제외·시스템제외를 **엔진별 단일 case-folding** 으로 통일(MySQL=lower 비교,
  MSSQL=원형 보존하되 비교는 정책 1개). enforcement 경계(저장 케이스)와 byte-identical.
- **M2 (제외 상수 분산)**: reconcile 은 `_DATABASES_AVAILABLE_METADATA ∪ _INTERNAL ∪ _SYSTEM_MSSQL ∪
  MEMORY_DB` union 을 단일 헬퍼로 consult(신규 4번째 enforcement point 가 drift 안 되게).
- **M4 (flapping)**: 라이브 DB 열거 실패/breaker open → **무조건 no-op**(빈 목록을 "전부 제거"로 해석 금지).
  reconcile 은 (product,datasource) 트랜잭션 단위.
- **M5 (MSSQL primary pin)**: 자동/규칙 추가행은 SortOrder 를 기존 max+오프셋(말미)으로 → `allow_dbs[0]`
  primary pin 재지정 불가.
- **M6 (read-with-write)**: 쓰기는 항상 product.manage. lazy 트리거(관리자 제품 열람)는 product.manage
  보유 시에만 reconcile-write. datasource.read 전용 뷰어는 write 유발 안 함.
- **M3 (lost privilege)**: 백그라운드 reconcile 은 매 실행 시 규칙 creator 의 product.manage 보유 재검증 —
  미보유면 자동적용 보류(pending) + flag.

## 3. 데이터 모델 (idempotent 마이그레이션 — 비파괴)
- `WebProductDatabases ADD COLUMN Source ENUM('manual','rule') NOT NULL DEFAULT 'manual'`
  (`ADD COLUMN RuleId BIGINT NULL` 도 — 어떤 규칙이 추가했는지 추적). 기존 행 → manual.
- `WebProductDatasourceDbRules(Id PK, ProductId, DatasourceKey, IncludePattern, ExcludePattern NULL,
  Cap INT DEFAULT 3, IsEnabled TINYINT DEFAULT 1, CreatedByAccountId BIGINT NULL, LastSyncAt DATETIME NULL,
  CreatedAt, UpdatedAt, UNIQUE(ProductId, DatasourceKey))`.
- `WebProductDatabasePending(Id PK, ProductId, DatasourceKey, SchemaName, RuleId, Reason VARCHAR, DetectedAt,
  UNIQUE(ProductId, DatasourceKey, SchemaName))` — 자동적용 보류분(승인 대기).
- 등록: `_ensure_web_tables`(slow) + `_runtime_tables_available` probe 목록 + `_ensure_seed_catchup`(fast)
  양쪽 (TASK-0047 trap — probe 에 신규 테이블 미등록 시 fast-path 가 생성 skip).

## 4. 백엔드
- `_db_rule_excluded_set(engine)` — M2 union 헬퍼.
- `_validate_db_rule_pattern(p)` — B2(길이·compile·중첩수량자·backref·앵커).
- `_match_db_rule(names, include, exclude, engine)` — B5 case-folding, 후보 bound.
- `_reconcile_product_db_rule(conn, product_id, ds_key, *, actor_account_id, trigger)` — 핵심:
  라이브 DB 열거(실패=no-op M4) → candidates → new = candidates − 기존행(manual∪rule) →
  `len(new) ≤ Cap & 모호성 없음 & actor product.manage` → rule 행 자동 insert(SortOrder 말미 M5) + audit;
  else → pending insert + audit(staged). manual 미변경. 트랜잭션 단위.
- 엔드포인트(product.manage, M6):
  - `PUT /api/admin/products/{id}/datasources/{key}/db-rule` (upsert+검증+즉시 reconcile)
  - `GET .../db-rule` (규칙 + pending 목록)
  - `DELETE .../db-rule` (규칙 삭제, rule 행 strip 옵션)
  - `POST .../db-rule/preview` (dry-run match count — UI 라이브)
  - `POST .../db-rule/approve-pending` (pending → rule 승격, 승인 audit)
- `admin_update_product_databases` PUT 수정(B4): Source='manual' 행만 DELETE/INSERT, rule 행 보존,
  manual 충돌 schema 의 rule 행 삭제(manual 승격).
- 백그라운드: `@app.on_event("startup")` 로 주기 task(`web-product-db-rule-reconcile`) — IsEnabled 규칙
  순회, creator product.manage 재검증(M3), per-datasource breaker 인지(M4), 간격 env
  `AGENT_DB_RULE_RECONCILE_SEC`(기본 300). orphan-reconcile task 패턴 재사용.

## 5. UI (admin.js) — DB 편집기 내 규칙 섹션
- 규칙 입력(include/exclude/cap) + 저장 + preview 라이브 카운트(이미 만든 정규식 helper 재사용).
- rule 행 배지("규칙") — `_list_product_databases` 가 `source` 반환 → redrawChips 가 manual/rule 구분,
  manual draft(PUT)는 manual 행만(rule 행 제외).
- pending 승인 목록("규칙 일치 신규 DB N개 — 승인") + 1클릭 approve.

## 6. 검증
- Python: `tests/verify_db_rule_reconcile.py`(match·exclude·cap→pending·source 우선·대소문자·down=no-op·
  manual 보존·SortOrder 말미) + `py_compile`.
- jsdom: `tests/verify_db_rule_ui.mjs`(규칙 섹션·source 배지·pending 승인·manual draft 분리).
- 구현 후 **outside-voice 재리뷰**(REFUTE) → SHIP-WITH-FIXES 잔여 BLOCKER 0 확인.
- PB-0008 Windows-browser.

## 7. 식별자
TASK-20260618T044318-ai-claude-db-rule-autosync / REQ-20260618-0322 / AC-0580(엔진·reconcile)·0581(UI·pending).
CHG/REV-20260618T044318. RBAC 인접 → REV 는 outside-voice 동반(SKIPPED 아님).
