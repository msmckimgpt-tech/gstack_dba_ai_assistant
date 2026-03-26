import re
__all__ = [
    "_cancel_requested",
    "_clear_cancel_request",
    "_finalize_requested",
    "_clear_finalize_request",
    "mark_finalize_requested",
    "_purge_run_steps",
    "_record_step_summary",
    "clear_memory_tables",
    "cleanup_pending_delete_conversations",
    "create_conversation",
    "delete_conversation",
    "delete_all_conversations",
    "ensure_memory_schema",
    "is_delete_requested",
    "is_processing_conversation",
    "list_conversations",
    "list_delete_requested_conversation_ids",
    "list_processing_conversation_ids",
    "load_memory_context",
    "load_memory_kv",
    "load_memory_kv_all",
    "load_recent_steps",
    "load_step_trace_from_kv",
    "mark_cancel_requested",
    "mark_delete_requested",
    "save_memory_kv",
    "save_memory_message",
    "save_memory_step",
    "save_memory_summary",
    "set_run_status",
]


"""Memory table CRUD operations and conversation management."""
from .config import *
from . import config as cfg
import json, re
from datetime import datetime, timezone
from typing import Any


def _is_truthy_flag(value: Any) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes")

def ensure_memory_schema() -> None:
    admin_conn = connect(database=None, autocommit=True)
    admin_cur = admin_conn.cursor()
    admin_cur.execute(
        f"CREATE DATABASE IF NOT EXISTS {_quote_ident(MEMORY_DB)} "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    admin_cur.close()
    admin_conn.close()

    mem_conn = connect(database=MEMORY_DB, autocommit=True)
    cur = mem_conn.cursor()
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS AgentMemoryMessages (
    Id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    ConversationId VARCHAR(128) NOT NULL,
    Role VARCHAR(32) NOT NULL,
    Content LONGTEXT NOT NULL,
    MetaJson LONGTEXT NULL,
    CreatedAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX IX_AgentMemoryMessages_Conv_Created (ConversationId, CreatedAt DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    try:
        cur.execute("ALTER TABLE AgentMemoryMessages ADD COLUMN MetaJson LONGTEXT NULL")
    except Exception:
        pass
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS AgentMemorySummary (
    ConversationId VARCHAR(128) NOT NULL PRIMARY KEY,
    Summary LONGTEXT NOT NULL,
    UpdatedAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS AgentMemoryKv (
    ConversationId VARCHAR(128) NOT NULL,
    `Key` VARCHAR(128) NOT NULL,
    `Value` LONGTEXT NOT NULL,
    UpdatedAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (ConversationId, `Key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS AgentMemorySteps (
    Id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    ConversationId VARCHAR(128) NOT NULL,
    RunId VARCHAR(64) NOT NULL,
    StepIndex INT NOT NULL,
    Action VARCHAR(32) NOT NULL,
    Tool VARCHAR(64) NOT NULL,
    Intent VARCHAR(255) NOT NULL,
    WorkText LONGTEXT NULL,
    WorkSource VARCHAR(16) NULL,
    ReasonText LONGTEXT NULL,
    ReasonSource VARCHAR(16) NULL,
    ArgsJson LONGTEXT NOT NULL,
    SqlText LONGTEXT NULL,
    ResultSummaryJson LONGTEXT NULL,
    ErrorText LONGTEXT NULL,
    CreatedAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX IX_AgentMemorySteps_Conv_Created (ConversationId, CreatedAt DESC),
    INDEX IX_AgentMemorySteps_Conv_Run (ConversationId, RunId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    try:
        cur.execute("ALTER TABLE AgentMemorySteps ADD COLUMN WorkText LONGTEXT NULL AFTER Intent")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE AgentMemorySteps ADD COLUMN WorkSource VARCHAR(16) NULL AFTER WorkText")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE AgentMemorySteps ADD COLUMN ReasonText LONGTEXT NULL AFTER WorkSource")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE AgentMemorySteps ADD COLUMN ReasonSource VARCHAR(16) NULL AFTER ReasonText")
    except Exception:
        pass
    # ── AgentMemoryTexts: 공유 텍스트 저장소 (해시 기반 중복 제거) ──
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS AgentMemoryTexts (
    TextHash CHAR(64) NOT NULL PRIMARY KEY,
    TextContent LONGTEXT NOT NULL,
    CreatedAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    FULLTEXT INDEX FT_Texts_Content (TextContent)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    # AgentMemoryFacts: FactEntries + Texts JOIN VIEW (테이블 중복 제거)
    # 기존 테이블이 남아있으면 VIEW로 전환
    try:
        cur.execute("SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agentmemoryfacts' AND TABLE_TYPE = 'BASE TABLE'")
        if cur.fetchone():
            cur.execute("DROP TABLE AgentMemoryFacts")
    except Exception:
        pass
    try:
        cur.execute("""
CREATE OR REPLACE VIEW AgentMemoryFacts AS
SELECT e1.ConversationId, e1.ScopeKey, e1.FactKey,
       COALESCE(t.TextContent, '') AS FactText,
       e1.Weight, e1.UpdatedAt
FROM AgentMemoryFactEntries e1
LEFT JOIN AgentMemoryTexts t ON t.TextHash = e1.TextHash
WHERE e1.Id = (
    SELECT e2.Id FROM AgentMemoryFactEntries e2
    WHERE e2.ConversationId = e1.ConversationId
      AND e2.ScopeKey = e1.ScopeKey
      AND e2.FactKey = e1.FactKey
    ORDER BY e2.Weight DESC, e2.UpdatedAt DESC, e2.Id DESC
    LIMIT 1
)
        """)
    except Exception:
        pass
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS AgentMemoryFactEntries (
    Id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    ConversationId VARCHAR(128) NOT NULL,
    FactKey VARCHAR(128) NOT NULL,
    ScopeKey VARCHAR(96) NOT NULL DEFAULT 'common',
    TextHash CHAR(64) NOT NULL DEFAULT '',
    FactFingerprint CHAR(40) NOT NULL,
    Weight INT NOT NULL DEFAULT 1,
    Confidence DECIMAL(3,2) NULL,
    SourceType VARCHAR(32) NULL,
    SourceRunId VARCHAR(64) NULL,
    SourceSql LONGTEXT NULL,
    CreatedAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    UpdatedAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    INDEX IX_FactEntries_Conv_Key (ConversationId, FactKey),
    INDEX IX_FactEntries_Conv_Weight (ConversationId, Weight, UpdatedAt),
    INDEX IX_FactEntries_Conv_Run (ConversationId, SourceRunId),
    INDEX IX_FactEntries_Conv_Scope_Weight (ConversationId, ScopeKey, Weight, UpdatedAt),
    INDEX IX_FactEntries_Conv_Scope_Run (ConversationId, ScopeKey, SourceRunId),
    INDEX IX_FactEntries_Conv_Scope_KeyRank (ConversationId, ScopeKey, FactKey, Weight, UpdatedAt, Id),
    UNIQUE KEY UX_FactEntries_Conv_Scope_Key_Fp (ConversationId, ScopeKey, FactKey, FactFingerprint)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS AgentMemoryRagDocuments (
    Id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    ConversationId VARCHAR(128) NOT NULL,
    ScopeKey VARCHAR(96) NOT NULL DEFAULT 'common',
    DocType VARCHAR(32) NOT NULL DEFAULT 'fact',
    FactKey VARCHAR(128) NULL,
    TextHash CHAR(64) NOT NULL DEFAULT '',
    ContentHash CHAR(40) NOT NULL,
    Weight INT NOT NULL DEFAULT 1,
    SourceType VARCHAR(32) NULL,
    SourceRunId VARCHAR(64) NULL,
    SourceSql LONGTEXT NULL,
    CreatedAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    UpdatedAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    INDEX IX_RagDocs_Conv_Scope_Updated (ConversationId, ScopeKey, UpdatedAt),
    INDEX IX_RagDocs_Conv_Scope_Weight (ConversationId, ScopeKey, Weight, UpdatedAt),
    INDEX IX_RagDocs_Conv_FactKey (ConversationId, FactKey),
    UNIQUE KEY UX_RagDocs_Conv_Scope_Key_Hash (ConversationId, ScopeKey, FactKey, ContentHash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    # AgentMemoryRagChunks: 미사용(SELECT 0건) + RagDocuments와 100% 중복 → 삭제됨
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS AgentMemoryRagObjects (
    Id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    ConversationId VARCHAR(128) NOT NULL,
    ScopeKey VARCHAR(96) NOT NULL DEFAULT 'common',
    ObjectType VARCHAR(32) NOT NULL,
    ObjectKey VARCHAR(255) NOT NULL,
    SchemaName VARCHAR(128) NULL,
    TableName VARCHAR(128) NULL,
    ColumnName VARCHAR(128) NULL,
    TextHash CHAR(64) NULL,
    Weight INT NOT NULL DEFAULT 1,
    SourceType VARCHAR(32) NULL,
    SourceRunId VARCHAR(64) NULL,
    CategoryDomain VARCHAR(128) NULL,
    CategoryEntityType VARCHAR(64) NULL,
    CategoryMetricFamily VARCHAR(128) NULL,
    CategoryEventType VARCHAR(128) NULL,
    CategoryTimeGrain VARCHAR(64) NULL,
    CategoryJoinHintsJson LONGTEXT NULL,
    CategoryConfidence DECIMAL(3,2) NULL,
    CreatedAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    UpdatedAt TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    INDEX IX_RagObjects_Conv_Scope (ConversationId, ScopeKey, ObjectType, UpdatedAt),
    INDEX IX_RagObjects_Schema_Table (SchemaName, TableName, ColumnName),
    INDEX IX_RagObjects_Category (ConversationId, ScopeKey, CategoryDomain, CategoryEventType, UpdatedAt),
    UNIQUE KEY UX_RagObjects_Conv_Scope_Type_Key (ConversationId, ScopeKey, ObjectType, ObjectKey)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    try:
        cur.execute(
            "ALTER TABLE AgentMemoryRagObjects "
            "ADD COLUMN CategoryDomain VARCHAR(128) NULL AFTER SourceRunId"
        )
    except Exception:
        pass
    try:
        cur.execute(
            "ALTER TABLE AgentMemoryRagObjects "
            "ADD COLUMN CategoryEntityType VARCHAR(64) NULL AFTER CategoryDomain"
        )
    except Exception:
        pass
    try:
        cur.execute(
            "ALTER TABLE AgentMemoryRagObjects "
            "ADD COLUMN CategoryMetricFamily VARCHAR(128) NULL AFTER CategoryEntityType"
        )
    except Exception:
        pass
    try:
        cur.execute(
            "ALTER TABLE AgentMemoryRagObjects "
            "ADD COLUMN CategoryEventType VARCHAR(128) NULL AFTER CategoryMetricFamily"
        )
    except Exception:
        pass
    try:
        cur.execute(
            "ALTER TABLE AgentMemoryRagObjects "
            "ADD COLUMN CategoryTimeGrain VARCHAR(64) NULL AFTER CategoryEventType"
        )
    except Exception:
        pass
    try:
        cur.execute(
            "ALTER TABLE AgentMemoryRagObjects "
            "ADD COLUMN CategoryJoinHintsJson LONGTEXT NULL AFTER CategoryTimeGrain"
        )
    except Exception:
        pass
    try:
        cur.execute(
            "ALTER TABLE AgentMemoryRagObjects "
            "ADD COLUMN CategoryConfidence DECIMAL(3,2) NULL AFTER CategoryJoinHintsJson"
        )
    except Exception:
        pass
    try:
        cur.execute(
            "CREATE INDEX IX_RagObjects_Category "
            "ON AgentMemoryRagObjects (ConversationId, ScopeKey, CategoryDomain, CategoryEventType, UpdatedAt)"
        )
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE AgentMemoryFactEntries ADD COLUMN ScopeKey VARCHAR(96) NOT NULL DEFAULT 'common' AFTER FactKey")
    except Exception:
        pass
    try:
        cur.execute("UPDATE AgentMemoryFactEntries SET ScopeKey = 'common' WHERE ScopeKey IS NULL OR ScopeKey = ''")
    except Exception:
        pass
    try:
        cur.execute(
            "ALTER TABLE AgentMemoryFactEntries "
            "ADD COLUMN FactFingerprint CHAR(40) NOT NULL DEFAULT '' AFTER FactText"
        )
    except Exception:
        pass
    dedupe_deleted = 0
    try:
        cur.execute(
            """
UPDATE AgentMemoryFactEntries
SET FactFingerprint = SHA1(LOWER(TRIM(REGEXP_REPLACE(COALESCE(FactText, ''), '[[:space:]]+', ' '))))
WHERE FactFingerprint IS NULL OR FactFingerprint = ''
            """
        )
    except Exception:
        # REGEXP_REPLACE 미지원 환경 대비
        try:
            cur.execute(
                """
UPDATE AgentMemoryFactEntries
SET FactFingerprint = SHA1(LOWER(TRIM(REPLACE(REPLACE(REPLACE(COALESCE(FactText, ''), '\r', ' '), '\n', ' '), '\t', ' '))))
WHERE FactFingerprint IS NULL OR FactFingerprint = ''
                """
            )
        except Exception:
            pass
    try:
        cur.execute(
            """
DELETE e1
FROM AgentMemoryFactEntries e1
JOIN AgentMemoryFactEntries e2
  ON e1.ConversationId = e2.ConversationId
 AND e1.ScopeKey = e2.ScopeKey
 AND e1.FactKey = e2.FactKey
 AND e1.FactFingerprint = e2.FactFingerprint
 AND (
    e1.UpdatedAt < e2.UpdatedAt
    OR (e1.UpdatedAt = e2.UpdatedAt AND e1.Id < e2.Id)
 )
            """
        )
        dedupe_deleted = int(cur.rowcount or 0)
    except Exception:
        dedupe_deleted = 0
    try:
        cur.execute(
            "CREATE INDEX IX_FactEntries_Conv_Scope_KeyRank "
            "ON AgentMemoryFactEntries (ConversationId, ScopeKey, FactKey, Weight, UpdatedAt, Id)"
        )
    except Exception:
        pass
    try:
        cur.execute(
            "CREATE INDEX IX_FactEntries_Conv_Scope_Weight "
            "ON AgentMemoryFactEntries (ConversationId, ScopeKey, Weight, UpdatedAt)"
        )
    except Exception:
        pass
    try:
        cur.execute(
            "CREATE INDEX IX_FactEntries_Conv_Scope_Run "
            "ON AgentMemoryFactEntries (ConversationId, ScopeKey, SourceRunId)"
        )
    except Exception:
        pass
    try:
        cur.execute(
            "CREATE UNIQUE INDEX UX_FactEntries_Conv_Scope_Key_Fp "
            "ON AgentMemoryFactEntries (ConversationId, ScopeKey, FactKey, FactFingerprint)"
        )
    except Exception:
        pass
    # UX_FactEntries_Conv_Scope_Key_Fp의 좌측 prefix가 ConversationId+ScopeKey+FactKey를 포함하므로
    # 기존 IX_FactEntries_Conv_Scope_Key는 중복 인덱스로 간주해 정리한다.
    try:
        cur.execute("DROP INDEX IX_FactEntries_Conv_Scope_Key ON AgentMemoryFactEntries")
    except Exception:
        pass
    if dedupe_deleted > 0:
        try:
            log_fact_quality(
                "fact_dedupe_batch",
                {"deleted_rows": dedupe_deleted, "conversation_id": "__schema_init__"},
            )
        except Exception:
            pass
    dampening_done = False
    try:
        cur.execute(
            """
SELECT `Value`
FROM AgentMemoryKv
WHERE ConversationId = %s AND `Key` = %s
LIMIT 1
            """,
            (GLOBAL_CONVERSATION_ID, "fact_entries_cleanup_v1"),
        )
        row = cur.fetchone()
        dampening_done = bool(row and str(row[0] or "").strip() == "1")
    except Exception:
        dampening_done = False
    rows = []
    if not dampening_done:
        try:
            cur.execute(
                """
SELECT ConversationId, SUBSTRING_INDEX(FactKey, ':', -1) AS SchemaName, COUNT(*) AS Cnt
FROM AgentMemoryFactEntries
WHERE FactKey LIKE 'schema_pref:%'
GROUP BY ConversationId, SchemaName
                """
            )
            rows = cur.fetchall() or []
        except Exception:
            rows = []
    if rows and not dampening_done:
        totals: dict[str, int] = {}
        for conv_id, _schema_name, cnt in rows:
            conv_key = str(conv_id or "").strip()
            totals[conv_key] = totals.get(conv_key, 0) + int(cnt or 0)
        dampened = 0
        for conv_id, schema_name, cnt in rows:
            conv_key = str(conv_id or "").strip()
            schema_key = str(schema_name or "").strip()
            total = int(totals.get(conv_key, 0) or 0)
            if not conv_key or not schema_key or total <= 0:
                continue
            ratio = float(cnt or 0) / float(total)
            if total < 6 or ratio < 0.7:
                continue
            try:
                cur.execute(
                    """
UPDATE AgentMemoryFactEntries
SET Weight = GREATEST(1, Weight - 1), UpdatedAt = CURRENT_TIMESTAMP(3)
WHERE ConversationId = %s
  AND FactKey = %s
  AND SourceType IN ('schema_usage', 'search_pref')
                    """,
                    (conv_key, f"schema_pref:{schema_key}"),
                )
                dampened += int(cur.rowcount or 0)
            except Exception:
                pass
        if dampened > 0:
            try:
                log_fact_quality(
                    "schema_pref_dampened",
                    {"updated_rows": dampened, "conversation_id": "__schema_init__"},
                )
            except Exception:
                pass
        try:
            cur.execute(
                """
INSERT INTO AgentMemoryKv (ConversationId, `Key`, `Value`)
VALUES (%s, %s, %s)
ON DUPLICATE KEY UPDATE `Value` = VALUES(`Value`), UpdatedAt = CURRENT_TIMESTAMP(3)
                """,
                (GLOBAL_CONVERSATION_ID, "fact_entries_cleanup_v1", "1"),
            )
        except Exception:
            pass
    single_key_cleanup_done = False
    try:
        cur.execute(
            """
SELECT `Value`
FROM AgentMemoryKv
WHERE ConversationId = %s AND `Key` = %s
LIMIT 1
            """,
            (GLOBAL_CONVERSATION_ID, "fact_entries_cleanup_v2"),
        )
        row = cur.fetchone()
        single_key_cleanup_done = bool(row and str(row[0] or "").strip() == "1")
    except Exception:
        single_key_cleanup_done = False
    single_key_deleted = 0
    if not single_key_cleanup_done:
        try:
            cur.execute(
                """
DELETE e1
FROM AgentMemoryFactEntries e1
JOIN AgentMemoryFactEntries e2
  ON e1.ConversationId = e2.ConversationId
 AND e1.ScopeKey = e2.ScopeKey
 AND e1.FactKey = e2.FactKey
 AND (
    e1.UpdatedAt < e2.UpdatedAt
    OR (e1.UpdatedAt = e2.UpdatedAt AND e1.Id < e2.Id)
 )
WHERE (
    e1.FactKey LIKE 'schema_insight:%'
    OR e1.FactKey LIKE 'schema_pref:%'
    OR e1.FactKey LIKE 'table_pref:%'
)
                """
            )
            single_key_deleted = int(cur.rowcount or 0)
        except Exception:
            single_key_deleted = 0
        try:
            cur.execute(
                """
UPDATE AgentMemoryFactEntries
SET FactFingerprint = SHA1(CONCAT('single::', FactKey))
WHERE (
    FactKey LIKE 'schema_insight:%'
    OR FactKey LIKE 'schema_pref:%'
    OR FactKey LIKE 'table_pref:%'
)
                """
            )
        except Exception:
            pass
        if single_key_deleted > 0:
            try:
                log_fact_quality(
                    "fact_single_key_cleanup",
                    {"deleted_rows": single_key_deleted, "conversation_id": "__schema_init__"},
                )
            except Exception:
                pass
        try:
            cur.execute(
                """
INSERT INTO AgentMemoryKv (ConversationId, `Key`, `Value`)
VALUES (%s, %s, %s)
ON DUPLICATE KEY UPDATE `Value` = VALUES(`Value`), UpdatedAt = CURRENT_TIMESTAMP(3)
                """,
                (GLOBAL_CONVERSATION_ID, "fact_entries_cleanup_v2", "1"),
            )
        except Exception:
            pass
    # ── 텍스트 중복제거 마이그레이션 (FactText/Content/Summary → TextHash 참조) ──
    text_dedup_done = False
    try:
        cur.execute(
            "SELECT `Value` FROM AgentMemoryKv "
            "WHERE ConversationId = %s AND `Key` = %s LIMIT 1",
            (GLOBAL_CONVERSATION_ID, "text_dedup_v1"),
        )
        row = cur.fetchone()
        text_dedup_done = bool(row and str(row[0] or "").strip() == "1")
    except Exception:
        text_dedup_done = False
    if not text_dedup_done:
        # TextHash 컬럼 추가 (기존 설치)
        for _tbl, _col, _after, _nullable in [
            ("AgentMemoryFactEntries", "TextHash", "ScopeKey", False),
            ("AgentMemoryRagDocuments", "TextHash", "FactKey", False),
            ("AgentMemoryRagObjects", "TextHash", "ColumnName", True),
        ]:
            try:
                _null = "NULL" if _nullable else "NOT NULL DEFAULT ''"
                cur.execute(f"ALTER TABLE {_tbl} ADD COLUMN {_col} CHAR(64) {_null} AFTER {_after}")
            except Exception:
                pass
        # FactText → AgentMemoryTexts 이관
        _has_col = False
        try:
            cur.execute(
                "SELECT 1 FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agentmemoryfactentries' AND COLUMN_NAME = 'FactText'"
            )
            _has_col = bool(cur.fetchone())
        except Exception:
            pass
        if _has_col:
            try:
                cur.execute(
                    "INSERT IGNORE INTO AgentMemoryTexts (TextHash, TextContent) "
                    "SELECT SHA2(FactText, 256), FactText FROM AgentMemoryFactEntries "
                    "WHERE FactText IS NOT NULL AND FactText != ''"
                )
                cur.execute(
                    "UPDATE AgentMemoryFactEntries SET TextHash = SHA2(FactText, 256) "
                    "WHERE (TextHash = '' OR TextHash IS NULL) AND FactText IS NOT NULL AND FactText != ''"
                )
                cur.execute("ALTER TABLE AgentMemoryFactEntries DROP COLUMN FactText")
            except Exception:
                pass
        # Content → AgentMemoryTexts 이관
        _has_col = False
        try:
            cur.execute(
                "SELECT 1 FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agentmemoryragdocuments' AND COLUMN_NAME = 'Content'"
            )
            _has_col = bool(cur.fetchone())
        except Exception:
            pass
        if _has_col:
            try:
                cur.execute(
                    "INSERT IGNORE INTO AgentMemoryTexts (TextHash, TextContent) "
                    "SELECT SHA2(Content, 256), Content FROM AgentMemoryRagDocuments "
                    "WHERE Content IS NOT NULL AND Content != ''"
                )
                cur.execute(
                    "UPDATE AgentMemoryRagDocuments SET TextHash = SHA2(Content, 256) "
                    "WHERE (TextHash = '' OR TextHash IS NULL) AND Content IS NOT NULL AND Content != ''"
                )
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE AgentMemoryRagDocuments DROP INDEX FT_RagDocs_Content")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE AgentMemoryRagDocuments DROP COLUMN Content")
            except Exception:
                pass
        # Summary → AgentMemoryTexts 이관
        _has_col = False
        try:
            cur.execute(
                "SELECT 1 FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agentmemoryragobjects' AND COLUMN_NAME = 'Summary'"
            )
            _has_col = bool(cur.fetchone())
        except Exception:
            pass
        if _has_col:
            try:
                cur.execute(
                    "INSERT IGNORE INTO AgentMemoryTexts (TextHash, TextContent) "
                    "SELECT SHA2(Summary, 256), Summary FROM AgentMemoryRagObjects "
                    "WHERE Summary IS NOT NULL AND Summary != ''"
                )
                cur.execute(
                    "UPDATE AgentMemoryRagObjects SET TextHash = SHA2(Summary, 256) "
                    "WHERE (TextHash = '' OR TextHash IS NULL) AND Summary IS NOT NULL AND Summary != ''"
                )
                cur.execute("ALTER TABLE AgentMemoryRagObjects DROP COLUMN Summary")
            except Exception:
                pass
        # RagChunks 테이블 삭제 (SELECT 0건, RagDocuments와 100% 중복)
        try:
            cur.execute("DROP TABLE IF EXISTS AgentMemoryRagChunks")
        except Exception:
            pass
        # 마이그레이션 완료 마크
        try:
            cur.execute(
                "INSERT INTO AgentMemoryKv (ConversationId, `Key`, `Value`) "
                "VALUES (%s, %s, '1') "
                "ON DUPLICATE KEY UPDATE `Value` = '1', UpdatedAt = CURRENT_TIMESTAMP(3)",
                (GLOBAL_CONVERSATION_ID, "text_dedup_v1"),
            )
        except Exception:
            pass
    # ── RAG backfill (FactEntries → RagDocuments/RagObjects, TextHash 참조 방식) ──
    rag_backfill_done = False
    try:
        cur.execute(
            "SELECT `Value` FROM AgentMemoryKv "
            "WHERE ConversationId = %s AND `Key` = %s LIMIT 1",
            (GLOBAL_CONVERSATION_ID, "rag_backfill_v2"),
        )
        row = cur.fetchone()
        rag_backfill_done = bool(row and str(row[0] or "").strip() == "1")
    except Exception:
        rag_backfill_done = False
    if not rag_backfill_done:
        try:
            cur.execute(
                """
INSERT INTO AgentMemoryRagDocuments (
    ConversationId, ScopeKey, DocType, FactKey, TextHash, ContentHash,
    Weight, SourceType, SourceRunId, SourceSql
)
SELECT
    e.ConversationId,
    COALESCE(NULLIF(e.ScopeKey, ''), 'common') AS ScopeKey,
    'fact' AS DocType,
    e.FactKey,
    e.TextHash,
    SHA1(CONCAT(COALESCE(e.FactKey, ''), '\n', COALESCE(e.TextHash, ''))) AS ContentHash,
    COALESCE(e.Weight, 1) AS Weight,
    e.SourceType,
    e.SourceRunId,
    e.SourceSql
FROM AgentMemoryFactEntries e
WHERE e.TextHash IS NOT NULL AND e.TextHash != ''
ON DUPLICATE KEY UPDATE
    TextHash = VALUES(TextHash),
    Weight = GREATEST(AgentMemoryRagDocuments.Weight, VALUES(Weight)),
    SourceType = COALESCE(VALUES(SourceType), AgentMemoryRagDocuments.SourceType),
    SourceRunId = COALESCE(VALUES(SourceRunId), AgentMemoryRagDocuments.SourceRunId),
    SourceSql = COALESCE(VALUES(SourceSql), AgentMemoryRagDocuments.SourceSql),
    UpdatedAt = CURRENT_TIMESTAMP(3)
                """
            )
        except Exception:
            pass
        try:
            cur.execute(
                """
INSERT INTO AgentMemoryRagObjects (
    ConversationId, ScopeKey, ObjectType, ObjectKey,
    SchemaName, TableName, ColumnName, TextHash,
    Weight, SourceType, SourceRunId
)
SELECT
    e.ConversationId,
    COALESCE(NULLIF(e.ScopeKey, ''), 'common') AS ScopeKey,
    CASE
      WHEN e.FactKey LIKE 'table\\_%' OR e.FactKey LIKE 'table:%' OR e.FactKey LIKE 'table_pref:%' OR e.FactKey LIKE 'table_insight:%' THEN 'table'
      WHEN e.FactKey LIKE 'schema\\_%' OR e.FactKey LIKE 'schema:%' OR e.FactKey LIKE 'schema_pref:%' OR e.FactKey LIKE 'schema_insight:%' THEN 'schema'
      ELSE 'fact'
    END AS ObjectType,
    CASE
      WHEN e.FactKey LIKE 'table_pref:%' THEN SUBSTRING_INDEX(e.FactKey, ':', -1)
      WHEN e.FactKey LIKE 'table_insight:%' THEN SUBSTRING_INDEX(e.FactKey, ':', -1)
      WHEN e.FactKey LIKE 'schema_pref:%' THEN SUBSTRING_INDEX(e.FactKey, ':', -1)
      WHEN e.FactKey LIKE 'schema_insight:%' THEN SUBSTRING_INDEX(e.FactKey, ':', -1)
      ELSE e.FactKey
    END AS ObjectKey,
    CASE
      WHEN e.FactKey LIKE 'table_pref:%' OR e.FactKey LIKE 'table_insight:%' THEN SUBSTRING_INDEX(SUBSTRING_INDEX(e.FactKey, ':', -1), '.', 1)
      WHEN e.FactKey LIKE 'schema_pref:%' OR e.FactKey LIKE 'schema_insight:%' THEN SUBSTRING_INDEX(e.FactKey, ':', -1)
      ELSE NULL
    END AS SchemaName,
    CASE
      WHEN e.FactKey LIKE 'table_pref:%' OR e.FactKey LIKE 'table_insight:%' THEN SUBSTRING_INDEX(SUBSTRING_INDEX(e.FactKey, ':', -1), '.', -1)
      ELSE NULL
    END AS TableName,
    NULL AS ColumnName,
    e.TextHash,
    COALESCE(e.Weight, 1) AS Weight,
    e.SourceType,
    e.SourceRunId
FROM AgentMemoryFactEntries e
WHERE e.TextHash IS NOT NULL AND e.TextHash != ''
  AND (e.FactKey LIKE 'table_pref:%'
    OR e.FactKey LIKE 'table_insight:%'
    OR e.FactKey LIKE 'schema_pref:%'
    OR e.FactKey LIKE 'schema_insight:%')
ON DUPLICATE KEY UPDATE
    TextHash = VALUES(TextHash),
    Weight = GREATEST(AgentMemoryRagObjects.Weight, VALUES(Weight)),
    SourceType = COALESCE(VALUES(SourceType), AgentMemoryRagObjects.SourceType),
    SourceRunId = COALESCE(VALUES(SourceRunId), AgentMemoryRagObjects.SourceRunId),
    UpdatedAt = CURRENT_TIMESTAMP(3)
                """
            )
        except Exception:
            pass
        try:
            cur.execute(
                "INSERT INTO AgentMemoryKv (ConversationId, `Key`, `Value`) "
                "VALUES (%s, %s, '1') "
                "ON DUPLICATE KEY UPDATE `Value` = '1', UpdatedAt = CURRENT_TIMESTAMP(3)",
                (GLOBAL_CONVERSATION_ID, "rag_backfill_v2"),
            )
        except Exception:
            pass
    cur.close()
    mem_conn.close()


def load_memory_context(conn, conversation_id: str, max_turns: int):
    cur = conn.cursor()

    cur.execute(
        """
SELECT Summary
FROM AgentMemorySummary
WHERE ConversationId = %s
LIMIT 1
        """,
        (conversation_id,),
    )
    row = cur.fetchone()
    summary = row[0] if row else None

    max_fetch = max(10, max_turns * 3)
    cur.execute(
        """
SELECT Role, Content, MetaJson, CreatedAt
FROM AgentMemoryMessages
WHERE ConversationId = %s
ORDER BY CreatedAt DESC
LIMIT %s
        """,
        (conversation_id, max_fetch),
    )
    fetched = cur.fetchall() or []
    rows: list[tuple[str, str, datetime]] = []
    for role, content, meta_json, created_at in fetched:
        if _is_internal_message(role, content, meta_json):
            continue
        rows.append((role, content, created_at))
        if len(rows) >= max_turns:
            break
    rows.reverse()

    cur.execute(
        """
SELECT `Key`, `Value`
FROM AgentMemoryKv
WHERE ConversationId = %s
        """,
        (conversation_id,),
    )
    kv_rows = cur.fetchall() or []
    cur.close()

    kv = {k: v for k, v in kv_rows}
    return summary, rows, kv


def save_memory_message(
    conn,
    conversation_id: str,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> None:
    meta_json = None
    auto_meta = dict(meta) if isinstance(meta, dict) else {}
    is_internal = False
    if role == "assistant":
        internal_flag = auto_meta.get("internal")
        if internal_flag is True:
            is_internal = True
            auto_meta["internal"] = True
        elif internal_flag is not False and _should_mark_internal_message(content):
            is_internal = True
            auto_meta["internal"] = True
    if is_internal and not AGENT_STORE_INTERNAL_MESSAGES:
        return
    if cfg.CURRENT_RUN_ID and "run_id" not in auto_meta:
        auto_meta["run_id"] = cfg.CURRENT_RUN_ID
    if auto_meta:
        try:
            meta_json = json.dumps(auto_meta, ensure_ascii=False)
        except Exception:
            meta_json = json.dumps({"value": str(auto_meta)}, ensure_ascii=False)
    cur = conn.cursor()
    cur.execute(
        """
INSERT INTO AgentMemoryMessages (ConversationId, Role, Content, MetaJson)
VALUES (%s, %s, %s, %s)
        """,
        (conversation_id, role, content, meta_json),
    )
    cur.close()


def save_memory_kv(conn, conversation_id: str, key: str, value: str) -> None:
    cur = conn.cursor()
    cur.execute(
        """
INSERT INTO AgentMemoryKv (ConversationId, `Key`, `Value`)
VALUES (%s, %s, %s)
ON DUPLICATE KEY UPDATE
    `Value` = VALUES(`Value`),
    UpdatedAt = CURRENT_TIMESTAMP(3)
        """,
        (conversation_id, key, value),
    )
    cur.close()


def load_memory_kv(conn, conversation_id: str, key: str) -> str:
    cur = conn.cursor()
    cur.execute(
        """
SELECT `Value`
FROM AgentMemoryKv
WHERE ConversationId = %s AND `Key` = %s
LIMIT 1
        """,
        (conversation_id, key),
    )
    row = cur.fetchone()
    cur.close()
    return str(row[0]) if row else ""


def load_memory_kv_all(conn, conversation_id: str) -> dict[str, str]:
    cur = conn.cursor()
    cur.execute(
        """
SELECT `Key`, `Value`
FROM AgentMemoryKv
WHERE ConversationId = %s
        """,
        (conversation_id,),
    )
    rows = cur.fetchall() or []
    cur.close()
    return {k: v for k, v in rows}


def set_run_status(
    conn,
    conversation_id: str,
    status: str,
    run_id: str = "",
    duration_ms: float | None = None,
    error: str | None = None,
) -> None:
    if not conversation_id:
        return
    save_memory_kv(conn, conversation_id, "last_status", str(status))
    save_memory_kv(conn, conversation_id, "last_status_at", utc_now_iso())
    if run_id:
        save_memory_kv(conn, conversation_id, "last_status_run_id", run_id)
    if duration_ms is not None:
        save_memory_kv(conn, conversation_id, "last_duration_ms", str(duration_ms))
    if error is not None:
        save_memory_kv(conn, conversation_id, "last_error", str(error))


def is_processing_conversation(conn, conversation_id: str) -> bool:
    if not conversation_id:
        return False
    return str(load_memory_kv(conn, conversation_id, "last_status") or "").strip().lower() == "processing"


def is_delete_requested(conn, conversation_id: str) -> bool:
    if not conversation_id:
        return False
    return _is_truthy_flag(load_memory_kv(conn, conversation_id, "delete_requested"))


def list_processing_conversation_ids(conn) -> list[str]:
    cur = conn.cursor()
    cur.execute(
        """
SELECT ConversationId
FROM AgentMemoryKv
WHERE `Key` = 'last_status' AND `Value` = 'processing'
        """
    )
    rows = cur.fetchall() or []
    cur.close()
    return [str(row[0]) for row in rows if row and row[0]]


def list_delete_requested_conversation_ids(conn) -> list[str]:
    cur = conn.cursor()
    cur.execute(
        """
SELECT ConversationId, `Value`
FROM AgentMemoryKv
WHERE `Key` = 'delete_requested'
        """
    )
    rows = cur.fetchall() or []
    cur.close()
    ids: list[str] = []
    for row in rows:
        conv_id = str(row[0] or "").strip() if row else ""
        raw_value = row[1] if row and len(row) > 1 else ""
        if conv_id and _is_truthy_flag(raw_value):
            ids.append(conv_id)
    return ids


def mark_cancel_requested(conn, conversation_id: str, run_id: str = "") -> None:
    if not conversation_id:
        return
    effective_run_id = str(run_id or "").strip() or load_memory_kv(conn, conversation_id, "last_status_run_id")
    save_memory_kv(conn, conversation_id, "cancel_requested", "1")
    save_memory_kv(conn, conversation_id, "cancel_run_id", str(effective_run_id or "").strip())
    save_memory_kv(conn, conversation_id, "cancel_at", utc_now_iso())


def mark_delete_requested(conn, conversation_id: str, run_id: str = "") -> None:
    if not conversation_id:
        return
    effective_run_id = str(run_id or "").strip() or load_memory_kv(conn, conversation_id, "last_status_run_id")
    save_memory_kv(conn, conversation_id, "delete_requested", "1")
    save_memory_kv(conn, conversation_id, "delete_run_id", str(effective_run_id or "").strip())
    save_memory_kv(conn, conversation_id, "delete_requested_at", utc_now_iso())


def _cancel_requested(conn, conversation_id: str, run_id: str) -> bool:
    if not conversation_id:
        return False
    try:
        flag = load_memory_kv(conn, conversation_id, "cancel_requested")
        if str(flag or "").strip() not in ("1", "true", "yes"):
            return False
        cancel_run = load_memory_kv(conn, conversation_id, "cancel_run_id")
        cancel_run = str(cancel_run or "").strip()
        if cancel_run and cancel_run != run_id:
            return False
        return True
    except Exception:
        return False


def _clear_cancel_request(conn, conversation_id: str) -> None:
    save_memory_kv(conn, conversation_id, "cancel_requested", "")
    save_memory_kv(conn, conversation_id, "cancel_run_id", "")
    save_memory_kv(conn, conversation_id, "cancel_at", "")


def mark_finalize_requested(conn, conversation_id: str, run_id: str = "") -> None:
    """즉시 답변 요청 플래그 설정."""
    if not conversation_id:
        return
    effective_run_id = str(run_id or "").strip() or load_memory_kv(conn, conversation_id, "last_status_run_id")
    save_memory_kv(conn, conversation_id, "finalize_requested", "1")
    save_memory_kv(conn, conversation_id, "finalize_run_id", str(effective_run_id or "").strip())


def _finalize_requested(conn, conversation_id: str, run_id: str) -> bool:
    """즉시 답변 플래그가 설정되어 있는지 확인."""
    if not conversation_id:
        return False
    try:
        flag = load_memory_kv(conn, conversation_id, "finalize_requested")
        if str(flag or "").strip() not in ("1", "true", "yes"):
            return False
        fin_run = load_memory_kv(conn, conversation_id, "finalize_run_id")
        fin_run = str(fin_run or "").strip()
        if fin_run and fin_run != run_id:
            return False
        return True
    except Exception:
        return False


def _clear_finalize_request(conn, conversation_id: str) -> None:
    save_memory_kv(conn, conversation_id, "finalize_requested", "")
    save_memory_kv(conn, conversation_id, "finalize_run_id", "")


def _clear_delete_request(conn, conversation_id: str) -> None:
    save_memory_kv(conn, conversation_id, "delete_requested", "")
    save_memory_kv(conn, conversation_id, "delete_run_id", "")
    save_memory_kv(conn, conversation_id, "delete_requested_at", "")


def _purge_run_steps(conn, conversation_id: str, run_id: str) -> None:
    if not conversation_id or not run_id:
        return
    cur = conn.cursor()
    cur.execute(
        """
DELETE FROM AgentMemorySteps
WHERE ConversationId = %s AND RunId = %s
        """,
        (conversation_id, run_id),
    )
    cur.close()


def save_memory_summary(conn, conversation_id: str, summary: str) -> None:
    cur = conn.cursor()
    cur.execute(
        """
INSERT INTO AgentMemorySummary (ConversationId, Summary)
VALUES (%s, %s)
ON DUPLICATE KEY UPDATE
    Summary = VALUES(Summary),
    UpdatedAt = CURRENT_TIMESTAMP(3)
        """,
        (conversation_id, summary),
    )
    cur.close()


def save_memory_step(
    conn,
    conversation_id: str,
    run_id: str,
    entry: dict[str, Any],
) -> None:
    cur = conn.cursor()
    action = str(entry.get("action", "")).strip() or "step"
    tool = str(entry.get("tool", "")).strip()
    intent = str(entry.get("intent", "")).strip()
    work_text = str(entry.get("work", "") or "").strip()
    work_source = str(entry.get("work_source", "") or "").strip()
    reason_text = str(entry.get("reason", "") or "").strip()
    reason_source = str(entry.get("reason_source", "") or "").strip()
    args = entry.get("args", {})
    sql_text = str(entry.get("sql", "")).strip()
    result_summary = entry.get("result_summary", None)
    error_text = str(entry.get("error", "")).strip()

    try:
        args_json = json.dumps(args, ensure_ascii=False)
    except Exception:
        args_json = json.dumps({"value": str(args)}, ensure_ascii=False)

    result_json = None
    if result_summary is not None:
        try:
            result_json = json.dumps(result_summary, ensure_ascii=False)
        except Exception:
            result_json = json.dumps({"value": str(result_summary)}, ensure_ascii=False)

    cur.execute(
        """
INSERT INTO AgentMemorySteps (
    ConversationId, RunId, StepIndex, Action, Tool, Intent,
    WorkText, WorkSource, ReasonText, ReasonSource,
    ArgsJson, SqlText, ResultSummaryJson, ErrorText
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            conversation_id,
            run_id,
            int(entry.get("step_index", 0) or 0),
            action,
            tool,
            intent,
            work_text or None,
            work_source or None,
            reason_text or None,
            reason_source or None,
            args_json,
            sql_text or None,
            result_json,
            error_text or None,
        ),
    )
    cur.close()


def load_recent_steps(
    conn,
    conversation_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    cur = conn.cursor()
    cur.execute(
        """
SELECT
    StepIndex,
    Action,
    Tool,
    Intent,
    WorkText,
    WorkSource,
    ReasonText,
    ReasonSource,
    ArgsJson,
    SqlText,
    ResultSummaryJson,
    ErrorText,
    RunId,
    CreatedAt
FROM AgentMemorySteps
WHERE ConversationId = %s
ORDER BY CreatedAt DESC
LIMIT %s
        """,
        (conversation_id, limit),
    )
    rows = cur.fetchall() or []
    cur.close()
    rows = list(rows)
    rows.reverse()
    steps: list[dict[str, Any]] = []
    for (
        step_index,
        action,
        tool,
        intent,
        work_text,
        work_source,
        reason_text,
        reason_source,
        args_json,
        sql_text,
        result_json,
        error_text,
        run_id,
        created_at,
    ) in rows:
        try:
            args = json.loads(args_json) if args_json else {}
        except Exception:
            args = {}
        result_summary = None
        if result_json:
            try:
                result_summary = json.loads(result_json)
            except Exception:
                result_summary = result_json
        steps.append(
            {
                "step_index": int(step_index or 0),
                "action": str(action or ""),
                "tool": str(tool or ""),
                "intent": str(intent or ""),
                "work": str(work_text or ""),
                "work_source": str(work_source or ""),
                "reason": str(reason_text or ""),
                "reason_source": str(reason_source or ""),
                "args": args,
                "sql": str(sql_text or ""),
                "result_summary": result_summary,
                "error": str(error_text or ""),
                "run_id": str(run_id or ""),
                "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
            }
        )
    return steps


def load_step_trace_from_kv(kv: dict[str, str]) -> list[dict[str, Any]]:
    raw = kv.get("step_trace") if isinstance(kv, dict) else None
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            cleaned.append(item)
    return cleaned


def _record_step_summary(conn, conversation_id: str, summary_text: str | None) -> None:
    if not summary_text:
        return
    try:
        save_memory_kv(conn, conversation_id, "last_step_summary", summary_text)
    except Exception:
        pass


def create_conversation(conn, conversation_id: str, topic: str | None = None) -> None:
    topic_text = (topic or "").strip()
    if topic_text:
        save_memory_kv(conn, conversation_id, "topic", topic_text)
    save_memory_kv(conn, conversation_id, "created_at", utc_now_iso())


def list_conversations(conn, limit: int = 50):
    cur = conn.cursor()
    cur.execute(
        """
SELECT
    c.ConversationId,
    COALESCE(t.`Value`, '(미설정)') AS Topic,
    c.`Value` AS CreatedAt
FROM AgentMemoryKv c
LEFT JOIN AgentMemoryKv t
    ON c.ConversationId = t.ConversationId
   AND t.`Key` = 'topic'
WHERE c.`Key` = 'created_at'
ORDER BY c.`Value` DESC
LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall() or []
    cur.close()
    return rows


def delete_conversation(conn, conversation_id: str) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM AgentCoreMessages WHERE conversation_id = %s", (conversation_id,))
    cur.execute("DELETE FROM AgentCoreConversations WHERE conversation_id = %s", (conversation_id,))
    cur.execute("DELETE FROM AgentMemoryMessages WHERE ConversationId = %s", (conversation_id,))
    cur.execute("DELETE FROM AgentMemorySummary WHERE ConversationId = %s", (conversation_id,))
    cur.execute("DELETE FROM AgentMemoryKv WHERE ConversationId = %s", (conversation_id,))
    cur.execute("DELETE FROM AgentMemorySteps WHERE ConversationId = %s", (conversation_id,))
    # AgentMemoryFacts는 FactEntries 기반 VIEW — FactEntries 삭제만 필요
    cur.execute("DELETE FROM AgentMemoryFactEntries WHERE ConversationId = %s", (conversation_id,))
    cur.execute("DELETE FROM AgentMemoryRagObjects WHERE ConversationId = %s", (conversation_id,))
    cur.execute("DELETE FROM AgentMemoryRagDocuments WHERE ConversationId = %s", (conversation_id,))
    cur.close()


def _list_all_conversation_ids(conn) -> list[str]:
    cur = conn.cursor()
    ids: set[str] = set()
    table_specs = (
        ("AgentCoreConversations", "conversation_id"),
        ("AgentCoreMessages", "conversation_id"),
        ("AgentMemoryMessages", "ConversationId"),
        ("AgentMemorySummary", "ConversationId"),
        ("AgentMemoryKv", "ConversationId"),
        ("AgentMemorySteps", "ConversationId"),
        ("AgentMemoryFacts", "ConversationId"),
        ("AgentMemoryFactEntries", "ConversationId"),
        ("AgentMemoryRagDocuments", "ConversationId"),
        ("AgentMemoryRagObjects", "ConversationId"),
    )
    for table_name, column_name in table_specs:
        try:
            cur.execute(
                f"""
SELECT DISTINCT {column_name}
FROM {table_name}
WHERE {column_name} IS NOT NULL AND {column_name} <> ''
                """
            )
            rows = cur.fetchall() or []
        except Exception:
            continue
        for row in rows:
            conv_id = str(row[0] or "").strip() if row else ""
            if conv_id:
                ids.add(conv_id)
    cur.close()
    return sorted(ids)


def delete_all_conversations(conn, preserve_ids: tuple[str, ...] | list[str] | set[str] = ()) -> int:
    preserve = {str(item or "").strip() for item in preserve_ids if str(item or "").strip()}
    deleted = 0
    for conversation_id in _list_all_conversation_ids(conn):
        if conversation_id in preserve:
            continue
        delete_conversation(conn, conversation_id)
        deleted += 1
    return deleted


def cleanup_pending_delete_conversations(conn) -> int:
    deleted = 0
    for conversation_id in list_delete_requested_conversation_ids(conn):
        if is_processing_conversation(conn, conversation_id):
            continue
        delete_conversation(conn, conversation_id)
        deleted += 1
    return deleted


def clear_memory_tables(conn) -> None:
    processing_ids = list_processing_conversation_ids(conn)
    preserve_ids = sorted({*processing_ids, *AGENT_MEMORY_CLEAR_KEEP_IDS})
    delete_all_conversations(conn, preserve_ids=preserve_ids)
