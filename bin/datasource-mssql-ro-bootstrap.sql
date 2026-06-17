-- =====================================================================
-- datasource-mssql-ro-bootstrap.sql
-- 멀티 datasource Stage 2 P6 — MSSQL datasource 전용 최소권한 RO 로그인/role 부트스트랩.
-- DESIGN-multi-datasource.md §4 (Codex-2 BLOCKER 정정) 산출물.
--
-- 왜 스크립트가 아니라 운영자 실행 템플릿인가:
--   자격증명·서버 전역설정은 운영 DBA 책임이며 앱 컨테이너에서 자동 실행하지 않는다. 본 파일은
--   datasource(=DB) 별로 **운영자가 값을 채워** sqlcmd/SSMS 로 1 회 실행하는 템플릿이다.
--   .env 의 DS_<KEY>_USER/DS_<KEY>_PASSWORD 가 여기서 만든 로그인과 일치해야 한다.
--
-- 핵심 원칙 (DESIGN §4):
--   1. **db_datareader 금지.** db_datareader 는 DB 내 모든 사용자 테이블/뷰 읽기를 부여해
--      애플리케이션 allowlist 를 우회한다(allowlist=DB계정 양면방어 전제와 정면충돌). 대신
--      datasource 전용 role 에 **허용 스키마/객체에만 GRANT SELECT** (deny-by-default).
--   2. **allowlist == GRANT 대상.** product 의 허용 스키마 집합과 GRANT SELECT 대상이 같은
--      객체집합을 가리켜야 한다. view 간접참조·무자격 이름이 금지객체를 읽으려 해도 role 이
--      그 객체에 권한이 없으면 DB 가 막는다(앱 AST allowlist 의 최종 backstop).
--   3. **쓰기/DDL/실행 권한 없음.** INSERT/UPDATE/DELETE/EXEC/CREATE 미부여. RW 폴백 금지.
--   4. **서버 전역설정은 prerequisite(아래 0단계 검증)** — 본 템플릿이 소유하지 않는다. 운영
--      서버에서 xp_cmdshell off / cross-DB ownership chaining off / Ad Hoc Distributed Queries
--      off 가 보장돼야 하며, 여기선 어긋나면 RAISERROR 로 **실패**시킨다(조용히 진행 금지).
--
-- 사용법:
--   1) 아래 :setvar 값(대상 DB, 로그인명/암호, role 명, 허용 스키마)을 채운다.
--   2) sqlcmd -b -S <host>,<port> -U <admin> -P <pw> -i bin/datasource-mssql-ro-bootstrap.sql
--      **`-b` 필수** — 0단계 prerequisite RAISERROR(sev 16) 가 발생하면 즉시 중단하기 위함이다.
--      `-b` 없이 실행하면 prereq 실패를 출력만 하고 RO 생성을 계속 진행한다(미하드닝 서버에 RO 가
--      만들어지는 위험). SSMS 는 SQLCMD 모드 + "오류 시 중단"을 켜고 실행.
--   3) 허용 스키마가 여러 개면 4단계 GRANT 블록을 스키마마다 복제한다.
--   4) 멱등: 재실행 안전(IF NOT EXISTS / 권한 재부여).
--
-- ⚠ 멀티-DB 주의 (TASK-0226):
--   이 템플릿은 **단일 TARGET_DB** 에만 USER/GRANT 한다. 한 MSSQL datasource 가 여러 DB(catalog)를
--   제품 접근가능 DB(WebProductDatabases)로 가지면, 그 DB 마다 본 템플릿을 TARGET_DB 를 바꿔
--   반복 실행해야 한다 — 그러지 않으면 insight-worker 가 미부트스트랩 DB 연결에서 'Login failed'/
--   'Cannot open database' 로 막혀 그 DB 를 조용히 건너뛴다(권한 이슈로 탐색 불가).
--   접근가능 DB 전체를 한 번에 부트스트랩하려면(schema 격리 대신 DB 단위 db_datareader 허용)
--   bin/datasource-mssql-ro-bootstrap-multidb.sql 을 사용한다. 두 템플릿은 동일 로그인에 대해
--   상호 배타다(스키마 GRANT-only ↔ db_datareader).
-- =====================================================================

:setvar TARGET_DB        "appdb"          -- DS_<KEY>_DEFAULT_DB 와 동일
:setvar RO_LOGIN         "ro_appdb"       -- DS_<KEY>_USER 와 동일
:setvar RO_PASSWORD      "CHANGE_ME"      -- DS_<KEY>_PASSWORD 와 동일 (.env 외 저장 금지)
:setvar RO_ROLE          "agent_ro_role"
:setvar ALLOWED_SCHEMA   "dbo"            -- product 허용 스키마(여러 개면 4단계 복제)

SET NOCOUNT ON;
SET XACT_ABORT ON;

-- ── 0단계: 서버 전역 prerequisite 검증 (어긋나면 실패) ────────────────────────
-- xp_cmdshell 은 RCE 표면. cross-DB ownership chaining 은 권한경계 우회. Ad Hoc Distributed
-- Queries 는 OPENROWSET/OPENDATASOURCE 의 서버측 스위치. 셋 다 OFF 여야 한다.
DECLARE @v SQL_VARIANT, @n INT;

SELECT @v = value_in_use FROM sys.configurations WHERE name = 'xp_cmdshell';
IF CONVERT(INT, @v) <> 0
    RAISERROR('PREREQUISITE FAIL: xp_cmdshell 가 켜져 있습니다. 서버에서 OFF 후 재실행하세요.', 16, 1);

SELECT @v = value_in_use FROM sys.configurations WHERE name = 'cross db ownership chaining';
IF CONVERT(INT, @v) <> 0
    RAISERROR('PREREQUISITE FAIL: cross db ownership chaining 가 켜져 있습니다. OFF 후 재실행하세요.', 16, 1);

SELECT @v = value_in_use FROM sys.configurations WHERE name = 'Ad Hoc Distributed Queries';
IF @v IS NOT NULL AND CONVERT(INT, @v) <> 0
    RAISERROR('PREREQUISITE FAIL: Ad Hoc Distributed Queries(OPENROWSET) 가 켜져 있습니다. OFF 후 재실행하세요.', 16, 1);
GO

-- ── 1단계: 서버 로그인 (최소권한, 정책 적용) ─────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = '$(RO_LOGIN)')
    CREATE LOGIN [$(RO_LOGIN)] WITH PASSWORD = '$(RO_PASSWORD)', CHECK_POLICY = ON;
GO

USE [$(TARGET_DB)];
GO

-- ── 2단계: DB 사용자 ─────────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '$(RO_LOGIN)')
    CREATE USER [$(RO_LOGIN)] FOR LOGIN [$(RO_LOGIN)];
GO

-- ── 3단계: datasource 전용 role (db_datareader 대신) ─────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '$(RO_ROLE)' AND type = 'R')
    CREATE ROLE [$(RO_ROLE)];
ALTER ROLE [$(RO_ROLE)] ADD MEMBER [$(RO_LOGIN)];
GO

-- db_datareader 가 혹시라도 붙어 있으면 제거 (allowlist 우회 방지 — 멱등 hardening).
IF EXISTS (
    SELECT 1 FROM sys.database_role_members rm
    JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id AND r.name = 'db_datareader'
    JOIN sys.database_principals m ON m.principal_id = rm.member_principal_id AND m.name = '$(RO_LOGIN)'
)
    ALTER ROLE [db_datareader] DROP MEMBER [$(RO_LOGIN)];
GO

-- ── 4단계: 허용 스키마에만 GRANT SELECT (deny-by-default) ─────────────────────
-- 허용 스키마가 여러 개면 이 블록을 스키마마다 복제하고 :setvar ALLOWED_SCHEMA 를 바꾼다.
GRANT SELECT ON SCHEMA::[$(ALLOWED_SCHEMA)] TO [$(RO_ROLE)];
-- 카탈로그 조회(에이전트 구조탐색)는 sys/INFORMATION_SCHEMA 의 기본 VIEW 권한으로 충분하다
-- (별도 GRANT 불필요). 사용자 객체 메타데이터만 노출되고 타 DB/시스템 비밀은 보이지 않는다.
GO

-- ── 4.5단계: 사전 부하추정용 SHOWPLAN (TASK-0298) ─────────────────────────────
-- 에이전트가 무거운 쿼리를 실행 전에 게이팅하려면 `SET SHOWPLAN_ALL ON` 으로 추정 실행계획을
-- 받아야 한다(MySQL EXPLAIN 등가). SHOWPLAN 은 **데이터 읽기 권한이 아니라** 추정 실행계획 생성만
-- 허용하므로 최소권한 RO 와 양립한다(deny-by-default 유지). 미부여 시: gate 모드는 안전 차단
-- (fail-closed), warn/off 모드는 무경고로 graceful degrade — 즉 기능은 동작하되 부하 게이팅이
-- 비활성. AGENT_QUERY_GUARD_MODE=gate/warn 운영을 계획하면 부여 권장.
GRANT SHOWPLAN TO [$(RO_ROLE)];
GO

-- ── 5단계: 검증 ──────────────────────────────────────────────────────────────
PRINT '--- role 멤버십 ---';
SELECT r.name AS role_name, m.name AS member
FROM sys.database_role_members rm
JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id
JOIN sys.database_principals m ON m.principal_id = rm.member_principal_id
WHERE m.name = '$(RO_LOGIN)';

PRINT '--- role 의 스키마 권한 (SELECT 만, deny-by-default) ---';
SELECT p.permission_name, p.state_desc, s.name AS schema_name
FROM sys.database_permissions p
JOIN sys.schemas s ON s.schema_id = p.major_id AND p.class = 3  -- class 3 = schema
JOIN sys.database_principals dp ON dp.principal_id = p.grantee_principal_id
WHERE dp.name = '$(RO_ROLE)';

PRINT '--- SHOWPLAN 권한 확인 (부하추정 게이트용 — GRANT 면 OK) ---';
SELECT CASE WHEN EXISTS (
    SELECT 1 FROM sys.database_permissions p
    JOIN sys.database_principals dp ON dp.principal_id = p.grantee_principal_id
    WHERE dp.name = '$(RO_ROLE)' AND p.permission_name = 'SHOWPLAN' AND p.state_desc = 'GRANT'
) THEN 'OK: SHOWPLAN 부여됨' ELSE 'WARN: SHOWPLAN 미부여 (gate 모드 fail-closed)' END AS showplan_check;

PRINT '--- db_datareader 비멤버 확인 (없어야 정상) ---';
SELECT CASE WHEN EXISTS (
    SELECT 1 FROM sys.database_role_members rm
    JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id AND r.name = 'db_datareader'
    JOIN sys.database_principals m ON m.principal_id = rm.member_principal_id AND m.name = '$(RO_LOGIN)'
) THEN 'FAIL: db_datareader 멤버' ELSE 'OK: db_datareader 아님' END AS db_datareader_check;
GO
