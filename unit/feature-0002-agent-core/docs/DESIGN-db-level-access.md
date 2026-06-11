# DESIGN — DB-단위 접근 모델 (제품→데이터소스→DB allowlist) + 데이터 MySQL 데이터소스화

TASK-0206 (설계). 사용자 결정(2026-06-11): 이제 **제품이 접근하는 데이터는 데이터소스에 종속**되고, 접근 단위는
**DB 자체**다(스키마 아님). 기존 데이터 MySQL 도 편집가능 데이터소스로 등록. 시스템 DB(MySQL 메타·MSSQL
master/model/msdb/tempdb)는 기본 포함.

> P6 의 MSSQL 보안경계(**스키마 allowlist → DB allowlist**)를 바꾸므로 outside-voice 재게이트 필수.

## 1. 현재 → 목표

| 항목 | 현재 | 목표(DB-단위) |
|---|---|---|
| 접근 단위 | MySQL=DB(schema), MSSQL=스키마(dbo/sales) | **양 엔진 DB 단위**(catalog/database) |
| 제품 allowlist | `WebProductDatabases.SchemaName` (MySQL=DB명, MSSQL=스키마명) | DB명(catalog) — 양 엔진 |
| 데이터 MySQL | 암묵 기본(NULL 바인딩, .env DB_HOST+AGENT_DATA_DB) | **명시 데이터소스**(WebDatasources, 암호화) |
| 기본 접근 | NULL=데이터 MySQL 전체 user 스키마 | **데이터소스 없으면 접근 0**(데이터 종속) |
| MSSQL 연결 | default_db 1개 고정 + 2-part | **no-pin + 3-part**(`[db].[schema].[table]`), allowlist DB 들 cross-DB 허용 |

## 2. 보안 (M1 보존이 핵심)

- "시스템 DB 기본 포함"이 **M1(master.sys.sql_logins 로그인 enumeration)** 과 충돌. 해소:
  - 시스템 DB(master/model/msdb/tempdb)는 allowlist 에 포함(catalog 차원 허용)하되, **`sys`/`INFORMATION_SCHEMA`(metadata
    이상)·`guest`·`db_*` 스키마는 계속 차단**(P6 M1 dialect system_schemas 유지). → `master.dbo.x` 허용, `master.sys.sql_logins`
    **차단**. 즉 시스템 DB 는 "보임/완결성"이지 sys 카탈로그 자유조회 아님.
- **DB allowlist = catalog 차원**: MSSQL `_freeform_sql_access_error` 가 **catalog(3-part db)** 를 DB-allowlist 와 대조
  (+ 시스템 DB). 무자격/2-part(catalog 없음)는 fail-closed(거부) — no-pin 이라 2-part 가 master 로 샐 위험 차단.
  스키마(db part)는 dialect system_schemas 제외하고 자유(RO GRANT 가 스키마 경계).
- **MySQL 무변경**: `db.table` 의 db(=database) 를 DB-allowlist 와 대조(현행 `_whitelist_violation`). DB-단위 이미 정합.
- **데이터 종속**: 제품에 데이터소스 미바인딩 → allowlist 빈 set → 메타만(접근 0). NULL 바인딩의 "데이터 MySQL 암묵"
  제거(데이터 MySQL 을 명시 데이터소스로 등록·바인딩해야 접근).
- 자격증명 암호화(TASK-0205) 유지. 데이터 MySQL 등록 = env 자격을 암호화해 WebDatasources 이전.

## 3. 구현

### 3.1 데이터 MySQL 데이터소스화
- 부팅 시드(web schema-ensure, KEK 가용 + `AGENT_DATA_DB_*` 존재 + WebDatasources 에 동키 없음): 키 `main_mysql`
  (engine=mysql, host=DB_HOST, user=AGENT_DATA_DB_USER, password=AGENT_DATA_DB_PASSWORD 암호화, default_db=NULL) 1회 생성.
  멱등. 운영자가 admin UI 로 수정 가능.
- `agent_memory`(플랫폼/RBAC/대화)는 **데이터소스 아님**(앱 자체 데이터, 분석 대상 아님).

### 3.2 DB allowlist (catalog 차원)
- `WebProductDatabases.SchemaName` = DB명(catalog). 의미를 "스키마"→"데이터베이스"로(컬럼명 보존, 값 의미 변경).
- `_product_allowed_schemas` → 그대로(DB명 리스트 반환). agent `set_active_schema_allowlist(db_names)`.
- agent `_freeform_sql_access_error`:
  - MySQL: 현행(`schemas`=db, allowlist 대조).
  - MSSQL: **catalog 를 allowlist+시스템DB 와 대조**(불일치 거부), 무자격·catalog 없는 2-part 거부, 스키마는
    dialect system_schemas 만 차단. (effective default_db 단일-DB 모드는 폐기 — DB-allowlist 가 대체.)
- 시스템 DB 집합: MySQL=metadata_schemas(information_schema/mysql/sys/perf), MSSQL=master/model/msdb/tempdb +
  metadata(sys/INFORMATION_SCHEMA). dialect 가 `system_databases()` 신규 소유.

### 3.3 MSSQL 연결 no-pin + 3-part
- `_connect_mssql`: default_db 미고정(또는 master) → 쿼리는 3-part 필수. §3.5 grounding 이 MSSQL=`[db].[schema].[table]`
  지시(2-part 금지). 부하/introspection 도 3-part.
- 단일 DB 제품(흔함)도 3-part 로 통일(일관). describe/sample 등 구조화 도구는 schema_name 인자에 DB 포함 처리.

### 3.4 /databases 시스템 DB 구분
- `list_server_databases` 가 시스템 DB 를 별도 표기(`{name, system:bool}`). UI 가 시스템 DB 는 고정칩(메타),
  나머지는 사용자 선택. MSSQL master/model/msdb/tempdb·MySQL information_schema 등 system=true.

### 3.5 UI
- 제품 상세: **데이터 소스 섹션을 접근 가능 데이터베이스 위로**. 데이터소스 선택 → `/databases` 로 접근가능 DB 옵션
  갱신(시스템 DB 고정칩 + 사용자 DB 다중선택 = allowlist). 별도 "참조 DB" 드롭다운 폐지(DB-단위로 흡수).
- 데이터소스 패널에 데이터 MySQL(main_mysql) 노출(편집가능).

## 4. 단계
- A 데이터 MySQL 시드 + dialect `system_databases()`.
- B agent DB-level allowlist(MSSQL catalog 대조·스키마 자유·시스템DB) + no-pin + §3.5 3-part.
- C `/databases` 시스템구분 + `_product_allowed_schemas` 정합.
- D UI 재구성.
- E 테스트 + outside-voice 재게이트(P6 경계 변경) + 배포 + 라이브 e2e.

## 4.5 outside-voice 재게이트 결과(Codex, NOT SHIP → 수정 후 재검)

초기 구현은 적대적 리뷰에서 **NOT SHIP**(BLOCKER 5 + MAJOR 2). 수정 반영:

- **BLOCKER1 (pin ∉ allowlist 2-part 유출)**: `_resolve_product_datasource` 가 pin DB 를 **반드시 allowlist 멤버**로
  강제(명시 DatasourceDatabase 도 allowlist 검증 후 채택, 아니면 첫 접근가능 DB). freeform 가드도 2-part 참조 시
  `_ACTIVE_DEFAULT_DB ∈ allowlist` 를 재확인(이중).
- **BLOCKER2 (3-part 함수 catalog 우회)**: `sql_guard.collect_schema_refs` 가 TVF-in-FROM(name='' but catalog) +
  Dot-체인 함수(`db.schema.fn()`)의 catalog/schema 도 수집 → cross-DB 검사 대상에 합류.
- **BLOCKER4 (agent_memory)**: `_whitelist_violation`·`_struct_schema_access_error` 가 `_INTERNAL_SCHEMAS` 를
  **allowlist·allow=None 무관 영구 차단**. admin `PUT /products/{id}/databases` 도 internal/metadata 이름 거부.
- **BLOCKER5 (조회오류 fail-open)**: product/allowlist 해석 예외 시 `allowed=[]`(빈 allowlist) fail-closed
  (과거 `None` → 데이터계정 GRANT 전체 DB 무제한 접근).
- **MAJOR6 (M1 미보존)**: **결정 변경** — 시스템 DB(master/model/msdb/tempdb)는 **freeform 조회 대상에서 제외**.
  dbo 호환뷰(`master.dbo.syslogins`/`sysdatabases`, `msdb.dbo.sysjobs`)가 sys 차단을 우회해 로그인·작업
  enumeration 을 유출하기 때문. "시스템 DB 포함"은 **UI 가시성(고정칩)** 의미로 한정(메타데이터처럼 보이되
  데이터소스 아님). 시스템 정보 함수(SERVERPROPERTY/SUSER_SNAME/SYSTEM_USER/IS_SRVROLEMEMBER 등)도 denylist.
- **MAJOR7 (시드 일괄바인딩)**: NULL→main_mysql 마이그레이션은 main_mysql 좌표가 .env 데이터 MySQL(host/user)과
  **일치할 때만** 수행(운영자가 재설정했으면 skip).

### BLOCKER3 — synonym/view/linked-server 간접참조는 GRANT 가 hard boundary (잔존·문서화)
AST 는 synonym/view 의 실제 대상 DB 를 해석하지 못한다(`dbo.synonym_to_other` → 현재 DB 객체로만 보임).
따라서 **앱-레이어 allowlist 는 soft boundary** 이고, 진짜 격리는 **datasource RO 로그인의 GRANT 범위**다.
**배포 요구사항**: 한 datasource 의 RO 로그인은 그 datasource 를 쓰는 제품들이 접근해야 하는 DB 에만 GRANT 한다.
서로 다른 격리 경계가 필요한 제품군은 **각각 별도 datasource(별도 RO 로그인)** 로 분리한다(동일 로그인에 여러
제품 DB GRANT 를 몰면 synonym/view/함수로 제품간 교차참조가 가능). `bin/datasource-mssql-ro-bootstrap.sql` 참조.

## 5. 위험
- **데이터 종속 전환 = 기존 NULL 바인딩 제품 접근 0** → 데이터 MySQL 시드 + 기존 제품 자동 바인딩(또는 운영자 안내) 필요.
  마이그레이션: 기존 NULL 바인딩 제품을 main_mysql 로 일괄 바인딩(기존 WebProductDatabases DB명 보존).
- MSSQL 3-part 강제 → 기존 단일DB MSSQL 제품의 2-part 쿼리·grounding 회귀. §3.5 갱신 필수.
- M1 회귀 위험: 시스템 DB 포함 시 sys 스키마 차단 누락하면 sql_logins 유출 → 테스트 박제.
