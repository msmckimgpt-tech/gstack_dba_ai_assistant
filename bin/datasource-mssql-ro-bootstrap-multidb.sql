-- =====================================================================
-- datasource-mssql-ro-bootstrap-multidb.sql
-- TASK-0226 — MSSQL datasource RO 로그인을 **제품 접근가능 DB 전체**에 부트스트랩.
--
-- 배경 (왜 이 파일이 필요한가):
--   insight-worker 는 MSSQL datasource 의 제품 접근가능 DB(WebProductDatabases) 마다 재연결해
--   스캔한다(insight._discover_mssql_databases → connect_with_retry(database=db)). 그런데 단일-DB
--   템플릿(datasource-mssql-ro-bootstrap.sql)은 RO 로그인을 **한 DB 에만** USER/GRANT 하므로,
--   다른 등록 DB 연결 시 'Login failed for user'(18456 state 38) 또는 'Cannot open database'(916)
--   로 막혀 insight 순회가 그 DB 를 조용히 건너뛴다(권한 이슈로 탐색 불가). 본 템플릿은 한 개의
--   공유 RO 로그인이 **여러 DB 를 읽도록** USER 매핑을 DB 마다 만들어 그 누락을 해소한다.
--
-- 보안 trade-off (운영자 명시 승인 하 채택, AGENTS.md §12.3 Major):
--   본 템플릿은 deny-by-default 단일-DB 템플릿과 달리 각 대상 DB 에서 **db_datareader** 를 부여한다
--   (= 그 DB 의 모든 사용자 스키마/테이블 읽기). 이는 schema 단위 allowlist 우회를 의도적으로
--   허용하는 선택이며, "데이터소스 연결정보 기준으로 접근가능 DB 전체를 읽는다"는 요구에 맞춘 것이다.
--   schema 단위 격리가 필요한 배포는 기존 datasource-mssql-ro-bootstrap.sql(스키마 GRANT-only)을
--   DB 마다 실행하라. 두 템플릿은 동일 로그인에 대해 **상호 배타**다(db_datareader vs 스키마 GRANT).
--
-- 유지되는 안전선 (보안 감수에도 불구하고 지키는 것):
--   1. **읽기 전용.** db_datareader 만 — db_datawriter/db_ddladmin/db_owner/EXEC/CREATE 미부여.
--   2. **시스템 DB 비대상.** master/model/msdb/tempdb 는 @target_dbs 에 넣지 않는다(앱도 hard-block).
--   3. **서버 전역 prerequisite.** xp_cmdshell / cross-db ownership chaining / Ad Hoc Distributed
--      Queries 가 OFF 여야 한다(0단계, 어긋나면 RAISERROR 로 실패).
--   4. **sys 영역 freeform 차단은 앱 계층 유지.** db_datareader 가 metadata 가시성을 주더라도
--      tools.py 의 system_schemas() 가 sys/guest/db_* 직접 freeform 조회를 계속 거부한다(M1 보존).
--
-- 사용법:
--   1) 아래 RO_LOGIN/RO_PASSWORD 를 .env 의 DS_<KEY>_USER/DS_<KEY>_PASSWORD 와 일치시킨다.
--   2) @target_dbs 에 이 datasource 의 제품 접근가능 DB 목록(WebProductDatabases.SchemaName)을 채운다.
--      (관리 콘솔의 제품 '접근 가능 데이터베이스' 목록과 동일해야 insight 순회 대상과 1:1 정합.)
--   3) sqlcmd -b -S <host>,<port> -U <admin> -P <pw> -i bin/datasource-mssql-ro-bootstrap-multidb.sql
--      **`-b` 필수** — 0단계 prerequisite 실패(sev 16) 시 즉시 중단(미하드닝 서버에 RO 생성 방지).
--   4) 멱등: 재실행 안전(IF NOT EXISTS / 멤버십 재부여).
--   5) 접근가능 DB 가 추가되면 @target_dbs 에 그 DB 를 더해 재실행한다(insight 가 새 DB 도 탐색).
--
-- ⚠ @target_dbs ↔ WebProductDatabases 동기화 (REV-20260611-0226 CONCERN-4):
--   @target_dbs(이 스크립트의 수동 입력)와 앱의 런타임 allowlist/insight 스캔 대상(제품 관리
--   UI 의 '접근 가능 데이터베이스' = WebProductDatabases)은 **독립적인 두 진실원천**이다. 반드시
--   일치시켜라:
--     - @target_dbs ⊃ allowlist: 스캔 안 할 DB 에 db_datareader 부여 = 최소권한 위반(불필요 확대).
--     - @target_dbs ⊂ allowlist: 스캔 대상인데 권한 없음 = insight 가 영구 db_failed/degraded
--       (이 스크립트가 풀려던 문제가 부분 재발).
--   접근가능 DB 를 관리 UI 에서 바꾸면 본 @target_dbs 도 같이 갱신해 재실행할 것.
-- =====================================================================

:setvar RO_LOGIN         "ro_agent"        -- DS_<KEY>_USER 와 동일
:setvar RO_PASSWORD      "CHANGE_ME"       -- DS_<KEY>_PASSWORD 와 동일 (.env 외 저장 금지)

SET NOCOUNT ON;
SET XACT_ABORT ON;

-- ── 0단계: 서버 전역 prerequisite 검증 (어긋나면 실패) ────────────────────────
DECLARE @v SQL_VARIANT;

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

-- ── 2단계: 대상 DB 목록을 채우고, 각 DB 에 USER + db_datareader 를 멱등 적용 ──────
-- @target_dbs 에 이 datasource 의 제품 접근가능 DB 를 한 줄씩 INSERT 한다(운영자 편집).
DECLARE @target_dbs TABLE (db_name SYSNAME PRIMARY KEY);

-- ↓↓↓ 운영자 편집 영역: 접근가능 DB 를 채운다 (WebProductDatabases.SchemaName 와 동일) ↓↓↓
INSERT INTO @target_dbs (db_name) VALUES
    (N'appdb1'),
    (N'appdb2'),
    (N'appdb3');
-- ↑↑↑ 운영자 편집 영역 ↑↑↑

DECLARE @login SYSNAME = N'$(RO_LOGIN)';
DECLARE @db SYSNAME, @sql NVARCHAR(MAX);
DECLARE @sys TABLE (n SYSNAME PRIMARY KEY);
INSERT INTO @sys (n) VALUES (N'master'), (N'model'), (N'msdb'), (N'tempdb');

DECLARE db_cur CURSOR LOCAL FAST_FORWARD FOR
    SELECT t.db_name
    FROM @target_dbs t
    JOIN sys.databases d ON d.name = t.db_name AND d.state_desc = 'ONLINE'
    WHERE t.db_name NOT IN (SELECT n FROM @sys);   -- 시스템 DB 는 대상 제외(앱도 hard-block)

OPEN db_cur;
FETCH NEXT FROM db_cur INTO @db;
WHILE @@FETCH_STATUS = 0
BEGIN
    -- USER FOR LOGIN (멱등) + db_datareader 멤버십 (멱등). QUOTENAME 으로 식별자 인젝션 차단.
    SET @sql = N'
        USE ' + QUOTENAME(@db) + N';
        IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = @login)
            CREATE USER ' + QUOTENAME(@login) + N' FOR LOGIN ' + QUOTENAME(@login) + N';
        IF NOT EXISTS (
            SELECT 1 FROM sys.database_role_members rm
            JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id AND r.name = ''db_datareader''
            JOIN sys.database_principals m ON m.principal_id = rm.member_principal_id AND m.name = @login
        )
            ALTER ROLE [db_datareader] ADD MEMBER ' + QUOTENAME(@login) + N';
        -- 쓰기 역할이 혹시 붙어 있으면 제거(읽기 전용 hardening, 멱등).
        IF EXISTS (
            SELECT 1 FROM sys.database_role_members rm
            JOIN sys.database_principals r ON r.principal_id = rm.role_principal_id AND r.name = ''db_datawriter''
            JOIN sys.database_principals m ON m.principal_id = rm.member_principal_id AND m.name = @login
        )
            ALTER ROLE [db_datawriter] DROP MEMBER ' + QUOTENAME(@login) + N';
        -- 사전 부하추정용 SHOWPLAN (TASK-0298, DB 스코프 권한 — 각 대상 DB 에 부여). SHOWPLAN 은
        -- 데이터 읽기가 아니라 추정 실행계획 생성만 허용 → 읽기전용과 양립. 미부여 시 gate 모드
        -- 안전차단(fail-closed)/warn·off 무경고로 graceful degrade.
        GRANT SHOWPLAN TO ' + QUOTENAME(@login) + N';
    ';
    EXEC sys.sp_executesql @sql, N'@login SYSNAME', @login = @login;
    PRINT 'OK: ' + @db + ' — USER + db_datareader + SHOWPLAN 적용';
    FETCH NEXT FROM db_cur INTO @db;
END
CLOSE db_cur;
DEALLOCATE db_cur;

-- ── 3단계: 검증 — 로그인이 매핑된 DB 와 db_datareader 멤버십 출력 ────────────────
-- 검증 범위는 부트스트랩 대상(@target_dbs)과 동일해야 하므로 2단계의 목록을 재사용한다
-- (전체 ONLINE DB 가 아님 — 대상 외 DB 의 MISSING 노이즈 차단). @target_dbs/@sys 가 같은
-- 배치 안에 있어야 참조 가능하므로 2단계와 3단계 사이에는 GO 를 두지 않는다(변수 스코프 유지).
PRINT '--- 부트스트랩 대상 DB 의 db_datareader 멤버십 (모두 OK 여야 정상) ---';
DECLARE @login2 SYSNAME = N'$(RO_LOGIN)';
DECLARE @check NVARCHAR(MAX) = N'';
-- 보안(B-1): DB명 문자열 리터럴 삽입은 QUOTENAME(name, '''') 로 작은따옴표를 이스케이프한다.
-- DB명(SYSNAME)에 작은따옴표가 들어갈 수 있어(예: [O'Brien]) raw 연결은 구문 깨짐·2차 인젝션
-- 표면이다. 식별자(USE/3-part 참조)는 QUOTENAME(name) 으로 대괄호 인용한다.
SELECT @check = @check + N'
    SELECT ' + QUOTENAME(t.db_name, '''') + N' AS db_name,
        CASE WHEN EXISTS (
            SELECT 1 FROM ' + QUOTENAME(t.db_name) + N'.sys.database_role_members rm
            JOIN ' + QUOTENAME(t.db_name) + N'.sys.database_principals r ON r.principal_id = rm.role_principal_id AND r.name = ''db_datareader''
            JOIN ' + QUOTENAME(t.db_name) + N'.sys.database_principals m ON m.principal_id = rm.member_principal_id AND m.name = @login
        ) THEN ''db_datareader OK'' ELSE ''MISSING'' END AS membership
    UNION ALL'
FROM @target_dbs t
JOIN sys.databases d ON d.name = t.db_name AND d.state_desc = 'ONLINE'
WHERE t.db_name NOT IN (SELECT n FROM @sys);
IF LEN(@check) > 0
BEGIN
    SET @check = LEFT(@check, LEN(@check) - LEN('UNION ALL'));   -- 마지막 UNION ALL 제거
    EXEC sys.sp_executesql @check, N'@login SYSNAME', @login = @login2;
END
GO
