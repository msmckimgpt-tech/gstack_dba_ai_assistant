import mysql.connector
__all__ = [
    "AGENT_AUX_SKIP_NEAR_DEADLINE_MS",
    "AGENT_COLUMN_SCAN_LIMIT",
    "AGENT_CONVO_SEARCH_AUTO",
    "AGENT_CONVO_SEARCH_LIMIT",
    "AGENT_CSV_ANALYZE_MAX_BYTES",
    "AGENT_CSV_ANALYZE_MAX_ROWS",
    "AGENT_CSV_PREVIEW_ROWS",
    "AGENT_DB_CONNECT_BACKOFF_SEC",
    "AGENT_DB_CONNECT_RETRIES",
    "AGENT_DB_POOL_ENABLED",
    "AGENT_DB_POOL_MAX_OVERFLOW",
    "AGENT_DB_POOL_RESET_SESSION",
    "AGENT_DB_POOL_SIZE",
    "AGENT_DISABLE_AUTO_RETRY",
    "AGENT_DOMAIN_DRIFT_GUARD",
    "AGENT_EARLY_FINALIZE_MS",
    "AGENT_ERROR_AUTO_RECOVERY",
    "AGENT_FACT_ENTRIES_MAX_PER_KEY",
    "AGENT_FACT_QUALITY_LOG",
    "AGENT_FACT_SINGLE_KEY_PREFIXES",
    "AGENT_FACT_SINGLE_KEY_SOURCES",
    "AGENT_FORCE_CONCLUSION_FACTS",
    "AGENT_GLOBAL_KB_FACTS",
    "AGENT_GLOBAL_KB_FACT_LIMIT",
    "AGENT_GLOBAL_KB_LOCK_TIMEOUT_SEC",
    "AGENT_GLOBAL_KB_MAX_ENTRIES",
    "AGENT_GLOBAL_KB_MIN_WEIGHT",
    "AGENT_GLOBAL_KB_SHARED_READ",
    "AGENT_GLOBAL_KB_SHARED_TYPES",
    "AGENT_GLOBAL_KB_SHARE_ACROSS_SESSIONS",
    "AGENT_GLOBAL_KB_TYPES",
    "AGENT_GLOBAL_SCHEMA_META_CACHE",
    "AGENT_GLOBAL_SCHEMA_META_TTL_SEC",
    "AGENT_INLINE_INSIGHT_ON_ASK",
    "AGENT_INSIGHT_FASTPATH_ALLOW_WITH_PASSTHROUGH",
    "AGENT_INSIGHT_MODEL",
    "AGENT_INSIGHT_OBJECT_DB_FETCH_LIMIT",
    "AGENT_INSIGHT_OBJECT_FASTPATH",
    "AGENT_INSIGHT_OBJECT_MAX_CANDIDATES",
    "AGENT_INSIGHT_OBJECT_MIN_SCORE",
    "AGENT_INSIGHT_OBJECT_VERIFY_ONCE",
    "AGENT_INSIGHT_OBJECT_VERIFY_TIMEOUT_MS",
    "AGENT_INSIGHT_ROUTE_LOG",
    "AGENT_INSIGHT_ROUTE_LOG_MAX_CANDIDATES",
    "AGENT_INSIGHT_SQL_COMPOSE_TIMEOUT_SEC",
    "AGENT_INSIGHT_TIMEOUT_SEC",
    "AGENT_INSIGHT_WORKER_CONVERSATION_ID",
    "AGENT_INSIGHT_WORKER_ENABLED",
    "AGENT_INSIGHT_WORKER_JITTER_SEC",
    "AGENT_INSIGHT_WORKER_LOCK_NAME",
    "AGENT_INSIGHT_WORKER_LOCK_TIMEOUT_SEC",
    "AGENT_INSIGHT_WORKER_STALE_SEC",
    "AGENT_INSIGHT_WORKER_TICK_SEC",
    "AGENT_INSIGHT_WORKER_DEGRADED_BACKOFF_SEC",
    "AGENT_ASK_EXECUTION_MODE",
    "AGENT_ASK_WORKER_ENABLED",
    "AGENT_ASK_WORKER_TICK_SEC",
    "AGENT_ASK_WORKER_HEARTBEAT_SEC",
    "AGENT_ASK_WORKER_STALE_SEC",
    "AGENT_ASK_WORKER_SWEEP_EVERY_SEC",
    "AGENT_ASK_WORKER_ATTEMPTS_CAP",
    "AGENT_ASK_WORKER_JITTER_SEC",
    "AGENT_ASK_WORKER_CONVERSATION_ID",
    "AGENT_ASK_WORKER_HEARTBEAT_KEY",
    "AGENT_KB_ALLOWED_SOURCE_TYPES",
    "AGENT_KB_FACT_LIMIT",
    "AGENT_KB_INSIGHT",
    "AGENT_KB_INSIGHT_MAX_COLS",
    "AGENT_KB_REQUIRE_EVIDENCE",
    "AGENT_KNOWLEDGE_SQL_FALLBACK",
    "AGENT_KNOWLEDGE_SQL_FALLBACK_MAX_OBJECT_TRIES",
    "AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC",
    "AGENT_LLM_REQUEST_PASSTHROUGH",
    "AGENT_LOG_DIR",
    "AGENT_LOG_MAX_BYTES",
    "AGENT_MASK_PII",
    "AGENT_MAX_SHOW",
    "AGENT_MAX_STEPS",
    "AGENT_MEMORY_CLEAR_KEEP_IDS",
    "AGENT_MEMORY_MAX_TURNS",
    "AGENT_META_EXPLORATION_BUDGET",
    "AGENT_META_SEARCH_REPEAT_LIMIT",
    "AGENT_MODE",
    "AGENT_OBJECT_PICK_MIN_CONFIDENCE",
    "AGENT_OBJECT_RESOLVE_BATCH_SIZE",
    "AGENT_OBJECT_RESOLVE_MAX_BATCHES",
    "AGENT_OBJECT_RESOLVE_MODEL",
    "AGENT_OBJECT_RESOLVE_TIMEOUT_SEC",
    "AGENT_OPENAI_MAX_RETRIES",
    "AGENT_OUT_DIR",
    "AGENT_PLAN_MODEL",
    "AGENT_PLAN_TIMEOUT_MIN_SEC",
    "AGENT_PLAN_TIMEOUT_RECOVERY_SEC",
    "AGENT_PLAN_TIMEOUT_SEC",
    "AGENT_RAG_CHUNK_OVERLAP",
    "AGENT_RAG_CHUNK_SIZE",
    "AGENT_RAG_DEPTH_ENABLED",
    "AGENT_RAG_DEPTH_MAX_LEVEL",
    "AGENT_RAG_DOC_MAX_CHARS",
    "AGENT_RAG_DOC_OBJECT_SCORE_BOOST",
    "AGENT_RAG_OBJECT_CATEGORY_ENABLED",
    "AGENT_RAG_PRIORITY_FIRST",
    "AGENT_RAG_PRIORITY_SHORT_CIRCUIT",
    "AGENT_RAG_PRIORITY_SHORT_CIRCUIT_ALLOW_WITH_PASSTHROUGH",
    "AGENT_RAG_PRIORITY_TIMEOUT_SEC",
    "AGENT_SCHEMA_BIAS_PENALTY",
    "AGENT_SCHEMA_BIAS_STEP_WINDOW",
    "AGENT_SCHEMA_BIAS_THRESHOLD",
    "AGENT_SCHEMA_BOOTSTRAP",
    "AGENT_SCHEMA_BOOTSTRAP_MAX_TABLES",
    "AGENT_SCHEMA_INSIGHT",
    "AGENT_SCHEMA_INSIGHT_MAX_COLS",
    "AGENT_SCHEMA_INSIGHT_RESCAN_SEC",
    "AGENT_SCHEMA_INSTANCE_SCAN",
    "AGENT_SCHEMA_INSTANCE_SCAN_BUDGET_SEC",
    "AGENT_SCHEMA_INSTANCE_SCAN_EVERY_SEC",
    "AGENT_SCHEMA_INSTANCE_SCAN_MAX_SCHEMAS",
    "AGENT_SCHEMA_INSTANCE_SCAN_TABLE_LIMIT",
    "AGENT_SCHEMA_META_CACHE_MAX_COLS",
    "AGENT_SCHEMA_META_CACHE_MAX_TABLES",
    "AGENT_SCHEMA_META_MAX_COLS",
    "AGENT_SCHEMA_META_MAX_TABLES",
    "AGENT_SCHEMA_USAGE_RECORD_STRICT",
    "AGENT_SEARCH_CACHE_TTL_SEC",
    "AGENT_SEARCH_OBJECTS_INCLUDE_TABLE_META",
    "AGENT_SEARCH_OBJECTS_META_MAX_TABLES",
    "AGENT_SEARCH_PREF_FROM_METADATA",
    "AGENT_SHOW_INTERNAL",
    "AGENT_SIMILAR_RETRY_LIMIT",
    "AGENT_SIMILAR_RETRY_THRESHOLD",
    "AGENT_SQL_COMPOSE_MODEL",
    "AGENT_SQL_GROUNDED_BLOCK_ON_FAIL",
    "AGENT_SQL_GROUNDED_REVIEW",
    "AGENT_SQL_GROUNDED_REVIEW_TIMEOUT_SEC",
    "AGENT_SQL_GROUNDED_REWRITE_ON_FAIL",
    "AGENT_SQL_REVIEW_MODEL",
    "AGENT_STEP_GRADE_MODEL",
    "AGENT_STEP_TRACE_MAX",
    "AGENT_STEP_VALIDATION",
    "AGENT_STEP_VALIDATION_EVERY",
    "AGENT_STORE_INTERNAL_MESSAGES",
    "AGENT_SUMMARY_MODEL",
    "AGENT_SUMMARY_MAX_RECENT",
    "AGENT_SUMMARY_REFRESH",
    "AGENT_SUMMARY_REFRESH_EVERY",
    "AGENT_TASK_CLASSIFY_MODEL",
    "AGENT_TABLE_INSIGHT_MAX_COLS",
    "AGENT_TABLE_INSIGHT_RESCAN_SEC",
    "AGENT_TABLE_MAX_COLS",
    "AGENT_TABLE_MAX_COL_WIDTH",
    "AGENT_TIMEOUT_SEC",
    "AGENT_QUERY_GUARD_MODE",
    "AGENT_QUERY_EXPLAIN_ROWS_WARN",
    "AGENT_QUERY_MAX_EXECUTION_MS",
    "AGENT_TIMING_LOG",
    "AGENT_TOPIC_MODEL",
    "AGENT_TOP_N",
    "BLOCKED_DEFAULT_SCHEMAS",
    "CURRENT_FACT_SCOPE_KEY",
    "CURRENT_RUN_DEADLINE_TS",
    "CURRENT_RUN_ID",
    "AGENT_DATA_DB_USER",
    "AGENT_DATA_DB_PASSWORD",
    "DB_CONNECT_DB",
    "DB_HOST",
    "DB_NAME",
    "DB_NAME_EFFECTIVE",
    "DB_PASSWORD",
    "DB_PORT",
    "DB_PROMPT_DEFAULT",
    "DB_USER",
    "REPLICA_DB_ENABLED",
    "REPLICA_DB_HOST",
    "REPLICA_DB_PASSWORD",
    "REPLICA_DB_PORT",
    "REPLICA_DB_USER",
    "AGENT_KB_PG_HOST",
    "AGENT_KB_PG_HOST_RO",
    "AGENT_KB_PG_PORT",
    "AGENT_KB_PG_PORT_RO",
    "AGENT_KB_PG_DB",
    "AGENT_KB_PG_USER",
    "AGENT_KB_PG_PASSWORD",
    "AGENT_KB_PG_USER_RO",
    "AGENT_KB_PG_PASSWORD_RO",
    "AGENT_KB_PG_SSLMODE",
    "AGENT_KB_PG_ENABLED",
    "AGENT_KB_READ_BACKEND",
    "AGENT_KB_EMBEDDING_MODEL",
    "AGENT_KB_EMBEDDING_DIM",
    "AGENT_KB_EMBEDDING_BATCH_SIZE",
    "AGENT_KB_EMBEDDING_TIMEOUT_SEC",
    "AGENT_KB_EMBEDDING_MAX_ATTEMPTS",
    "FACT_SCOPE_COMMON",
    "GLOBAL_CONVERSATION_ID",
    "GLOBAL_SESSION_CONVERSATION_ID",
    "KNOWN_SCHEMAS",
    "LOCAL_TOOLS",
    "MCP_EXECUTE_SQL_CANDIDATES",
    "MCP_PROTOCOL",
    "MCP_REQUEST_ID",
    "MCP_SEARCH_OBJECTS_CANDIDATES",
    "MCP_SESSION_ID",
    "MCP_TIMEOUT_SEC",
    "MCP_URL",
    "MEMORY_CONTEXT_KEYS",
    "MEMORY_CONVERSATION_ID",
    "MEMORY_DB",
    "BEDROCK_GATEWAY_API_KEY",
    "BEDROCK_GATEWAY_URL",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LOCAL_LLM_API_BASE",
    "LOCAL_LLM_API_KEY",
    "OPENAI_API_BASE",
    "OPENAI_MODEL",
    "OpenAI",
    "_inline_insight_on_ask_raw",
    "_insight_worker_enabled_raw",
    "console",
]


"""Configuration: environment variables, constants, and global mutable state."""
import os

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

console = Console()

DB_HOST = os.getenv("DB_HOST", "mysql")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
# TASK-0128 (#2): data-plane(고객 데이터/sandbox 분석) 전용 최소권한 RO 유저. 미설정 시
# DB_USER(root) 로 폴백(기존 동작 — 무중단). MEMORY_DB(제어) 연결은 항상 DB_USER 유지.
# db.connect() 가 database != MEMORY_DB 일 때 본 유저로 분기한다.
AGENT_DATA_DB_USER = os.getenv("AGENT_DATA_DB_USER", "").strip()
AGENT_DATA_DB_PASSWORD = os.getenv("AGENT_DATA_DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "mysql").strip()

# ── 복제(read-only) DB 인스턴스 (TASK-0044) ─────────────────────────
# REPLICA_DB_HOST 가 설정되면 data-plane 쿼리(agent 도구의 execute_sql/describe_* 등) 는
# 복제 인스턴스로 라우팅되고, memory DB(agent_memory) 연결은 기본 primary 로 유지된다.
# 조직 정책상 사업팀 wedge 에서 agent 는 복제본에만 접근해야 하며, 접속 정보는 `.env`
# 또는 docker-compose secret 으로만 주입하고 commit 에 포함하지 않는다.
REPLICA_DB_HOST = os.getenv("REPLICA_DB_HOST", "").strip()
REPLICA_DB_PORT = int(os.getenv("REPLICA_DB_PORT", str(DB_PORT)) or DB_PORT)
REPLICA_DB_USER = os.getenv("REPLICA_DB_USER", "").strip() or DB_USER
REPLICA_DB_PASSWORD = os.getenv("REPLICA_DB_PASSWORD", "") or DB_PASSWORD
REPLICA_DB_ENABLED = bool(REPLICA_DB_HOST)

# ── KB Postgres pgvector (TASK-0015 §2.1.4, M0 cycle) ─────────────────
# postgres 서비스가 docker-compose 에 추가되면 본 변수들이 활성화된다. M0 cycle
# 에서는 standalone — agent boot 의존 아님. M2 dual-write 부터 write path 가
# `_pg_connect()` 를 호출하고, M4 cutover 시 read path 가 backend 분기로 전환된다.
AGENT_KB_PG_HOST = os.getenv("AGENT_KB_PG_HOST", "").strip()
AGENT_KB_PG_PORT = int(os.getenv("AGENT_KB_PG_PORT", "5432") or "5432")
AGENT_KB_PG_DB = os.getenv("AGENT_KB_PG_DB", "agent_kb").strip() or "agent_kb"
AGENT_KB_PG_USER = os.getenv("AGENT_KB_PG_USER", "").strip()
AGENT_KB_PG_PASSWORD = os.getenv("AGENT_KB_PG_PASSWORD", "")
# REV-20260522-0012 B3 흡수 (M4 TASK-0024): read path 의 least-privilege —
# `agent_kb_ro` role 로 connect. 미설정 시 RW 로 fallback (RBAC 경고 log).
AGENT_KB_PG_USER_RO = os.getenv("AGENT_KB_PG_USER_RO", "").strip()
AGENT_KB_PG_PASSWORD_RO = os.getenv("AGENT_KB_PG_PASSWORD_RO", "")
AGENT_KB_PG_SSLMODE = os.getenv("AGENT_KB_PG_SSLMODE", "prefer").strip() or "prefer"
AGENT_KB_PG_ENABLED = bool(AGENT_KB_PG_HOST) and bool(AGENT_KB_PG_USER)
# T5-14: read replica 호스트 분리. 미설정 시 primary(AGENT_KB_PG_HOST) 로 fallback.
# docker-compose replica profile 활성화 시 AGENT_KB_PG_HOST_RO=postgres-replica 설정.
AGENT_KB_PG_HOST_RO = os.getenv("AGENT_KB_PG_HOST_RO", "").strip() or AGENT_KB_PG_HOST
AGENT_KB_PG_PORT_RO = int(os.getenv("AGENT_KB_PG_PORT_RO", "5432") or "5432")
AGENT_KB_READ_BACKEND = (os.getenv("AGENT_KB_READ_BACKEND", "mysql").strip() or "mysql").lower()

# M3 (TASK-0023) — Embedding worker (texts.embedding 컬럼 일괄 생성).
# Blocker B-4 결정 (M1 ADR-0021): TextHash 별 단일 embedding — fact_entries /
# rag_documents / rag_objects 가 texts join 시 자연 참조.
AGENT_KB_EMBEDDING_MODEL = (
    os.getenv("AGENT_KB_EMBEDDING_MODEL", "text-embedding-3-small").strip()
    or "text-embedding-3-small"
)
AGENT_KB_EMBEDDING_DIM = int(os.getenv("AGENT_KB_EMBEDDING_DIM", "1536") or "1536")
AGENT_KB_EMBEDDING_BATCH_SIZE = int(os.getenv("AGENT_KB_EMBEDDING_BATCH_SIZE", "100") or "100")
AGENT_KB_EMBEDDING_TIMEOUT_SEC = int(os.getenv("AGENT_KB_EMBEDDING_TIMEOUT_SEC", "60") or "60")
AGENT_KB_EMBEDDING_MAX_ATTEMPTS = int(os.getenv("AGENT_KB_EMBEDDING_MAX_ATTEMPTS", "3") or "3")
BLOCKED_DEFAULT_SCHEMAS = {
    s.strip().lower()
    for s in os.getenv(
        "AGENT_BLOCKED_DEFAULT_SCHEMAS",
        "appdb,__invalid_default_db__,__unset_db__,none,null",
    ).split(",")
    if s.strip()
}
DB_NAME_EFFECTIVE = "" if str(DB_NAME or "").strip().lower() in BLOCKED_DEFAULT_SCHEMAS else DB_NAME
DB_CONNECT_DB = DB_NAME_EFFECTIVE or None
DB_PROMPT_DEFAULT = DB_NAME_EFFECTIVE or "(미지정)"
MEMORY_DB = os.getenv("AGENT_MEMORY_DB", "agent_memory")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "claude-sonnet-4")

# ── 로컬 LLM Gateway (구버전 호환 — Local LLM gateway 사용 시) ──
LOCAL_LLM_API_BASE = os.getenv("LOCAL_LLM_API_BASE", "").strip() or None
LOCAL_LLM_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "").strip() or None
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "").strip() or None

# ── AWS Bedrock gateway (feature-0007, LiteLLM proxy 경유) ──
# 본 backend 는 BEDROCK_GATEWAY_URL / BEDROCK_GATEWAY_API_KEY 만 인지하며 AWS
# 자격증명은 직접 보유하지 않는다 (gateway 컨테이너 env 로만 주입). 본 cycle
# 도입 후 production 의 LLM 호출 default 경로.
BEDROCK_GATEWAY_URL = os.getenv("BEDROCK_GATEWAY_URL", "").strip() or None
BEDROCK_GATEWAY_API_KEY = os.getenv("BEDROCK_GATEWAY_API_KEY", "").strip() or None


def _select_llm_provider() -> tuple[str | None, str | None]:
    """LLM provider 선택 — base_url 과 api_key 를 **paired tuple** 로 결정.
    codex P2 follow-up (CHG-20260522-0003): 이전 fallback chain (`X or Y or Z`)
    이 base_url 과 api_key 를 독립적으로 선택해서, 예를 들어 BEDROCK_GATEWAY_URL
    이 설정됐지만 BEDROCK_GATEWAY_API_KEY 가 비어 있는 경우 → URL 은 gateway 로
    가지만 key 는 LOCAL_LLM_API_KEY 로 silent fallback →
    gateway 가 그 key 를 reject (misroute). 본 helper 가 paired 결정으로 차단.

    우선순위 (paired only):
    1. Bedrock gateway   — BEDROCK_GATEWAY_URL + BEDROCK_GATEWAY_API_KEY 둘 다.
    2. Local LLM gateway — LOCAL_LLM_API_BASE + LOCAL_LLM_API_KEY 둘 다.
    3. 미설정            — (None, None). _get_openai_client() 가 None 반환.

    feature-0007 follow-up (CHG-20260522-0006): OpenAI direct fallback 제거.
    CHG-20260522-0010: OPENAI_API_KEY 변수 완전 제거.
    """
    if BEDROCK_GATEWAY_URL and BEDROCK_GATEWAY_API_KEY:
        return (BEDROCK_GATEWAY_URL, BEDROCK_GATEWAY_API_KEY)
    if LOCAL_LLM_API_BASE and LOCAL_LLM_API_KEY:
        return (LOCAL_LLM_API_BASE, LOCAL_LLM_API_KEY)
    return (None, None)


LLM_BASE_URL, LLM_API_KEY = _select_llm_provider()
AGENT_OBJECT_RESOLVE_MODEL = (
    os.getenv("AGENT_OBJECT_RESOLVE_MODEL", OPENAI_MODEL).strip() or OPENAI_MODEL
)
AGENT_SQL_COMPOSE_MODEL = (
    os.getenv("AGENT_SQL_COMPOSE_MODEL", OPENAI_MODEL).strip() or OPENAI_MODEL
)
AGENT_SQL_REVIEW_MODEL = (
    os.getenv("AGENT_SQL_REVIEW_MODEL", AGENT_SQL_COMPOSE_MODEL).strip()
    or AGENT_SQL_COMPOSE_MODEL
)
AGENT_PLAN_MODEL = (
    os.getenv("AGENT_PLAN_MODEL", OPENAI_MODEL).strip() or OPENAI_MODEL
)
AGENT_TASK_CLASSIFY_MODEL = (
    os.getenv("AGENT_TASK_CLASSIFY_MODEL", AGENT_PLAN_MODEL).strip()
    or AGENT_PLAN_MODEL
)
AGENT_SUMMARY_MODEL = (
    os.getenv("AGENT_SUMMARY_MODEL", OPENAI_MODEL).strip() or OPENAI_MODEL
)
AGENT_TOPIC_MODEL = (
    os.getenv("AGENT_TOPIC_MODEL", AGENT_SUMMARY_MODEL).strip()
    or AGENT_SUMMARY_MODEL
)
AGENT_SQL_FIX_MODEL = (
    os.getenv("AGENT_SQL_FIX_MODEL", OPENAI_MODEL).strip() or OPENAI_MODEL
)
AGENT_STEP_GRADE_MODEL = (
    os.getenv("AGENT_STEP_GRADE_MODEL", AGENT_SUMMARY_MODEL).strip()
    or AGENT_SUMMARY_MODEL
)
AGENT_INSIGHT_MODEL = (
    os.getenv("AGENT_INSIGHT_MODEL", "").strip() or OPENAI_MODEL
)

AGENT_LOG_DIR = os.getenv("AGENT_LOG_DIR", "/shared/logs")
# 단일 앱 로그 파일 크기 상한(bytes). 초과 시 .1 로 1회 회전. 회전 없이 append 만
# 하던 과거엔 바쁜 날 insight_route.log 가 1GB+ 까지 자랐다. 0 이하면 비활성.
AGENT_LOG_MAX_BYTES = int(os.getenv("AGENT_LOG_MAX_BYTES", str(50 * 1024 * 1024)))
AGENT_OUT_DIR = os.getenv("AGENT_OUT_DIR", "/shared/out")
AGENT_TOP_N = int(os.getenv("AGENT_TOP_N", "200"))
AGENT_MAX_SHOW = int(os.getenv("AGENT_MAX_SHOW", "10"))
AGENT_TABLE_MAX_COLS = int(os.getenv("AGENT_TABLE_MAX_COLS", "12"))
AGENT_TABLE_MAX_COL_WIDTH = int(os.getenv("AGENT_TABLE_MAX_COL_WIDTH", "24"))
AGENT_TIMEOUT_SEC = int(os.getenv("AGENT_TIMEOUT_SEC", "60"))

# ── 무거운 쿼리 자가규제 (TASK-0172, DESIGN-self-interrupt §11) ──
# execute_sql(LLM freeform 분석 SELECT) 의 사전 EXPLAIN 게이팅 + per-query 시간 cap.
# self-interrupt(mid-query KILL)의 reconsider 대안 — 사전 규제라 KILL/스레드/async 불요.
#   off  : 현행(무변경, 기본).
#   warn : 무거운 쿼리도 실행하되 EXPLAIN 추정 비용을 결과에 prepend(LLM 학습용).
#   gate : EXPLAIN 추정 rows 가 임계 초과 + confirm_heavy 미설정이면 실행 대신 좁히기 유도.
AGENT_QUERY_GUARD_MODE = (
    os.getenv("AGENT_QUERY_GUARD_MODE", "off").strip().lower() or "off"
)
# 오타 등 미지원 값은 off 로 정규화(예측가능 — 잘못된 모드로 silent 미보호/과보호 방지).
if AGENT_QUERY_GUARD_MODE not in ("off", "warn", "gate"):
    AGENT_QUERY_GUARD_MODE = "off"
# EXPLAIN 추정 스캔 rows(테이블별 rows 곱) 임계 — 초과 시 무거운 쿼리로 판정.
AGENT_QUERY_EXPLAIN_ROWS_WARN = int(
    (os.getenv("AGENT_QUERY_EXPLAIN_ROWS_WARN", "1000000") or "1000000").strip()
)
# per-query 시간 상한(ms) — SELECT 한정 MAX_EXECUTION_TIME backstop. 0=비활성.
# "무거운 쿼리는 감수" 정책상 정상 장기 쿼리를 끊지 않도록 generous/off 기본 — 폭주 차단용.
AGENT_QUERY_MAX_EXECUTION_MS = int(
    (os.getenv("AGENT_QUERY_MAX_EXECUTION_MS", "0") or "0").strip()
)
AGENT_OPENAI_MAX_RETRIES = int(os.getenv("AGENT_OPENAI_MAX_RETRIES", "0"))
AGENT_MEMORY_MAX_TURNS = int(os.getenv("AGENT_MEMORY_MAX_TURNS", "10"))
AGENT_CSV_PREVIEW_ROWS = int(os.getenv("AGENT_CSV_PREVIEW_ROWS", "20"))
AGENT_CSV_ANALYZE_MAX_ROWS = int(os.getenv("AGENT_CSV_ANALYZE_MAX_ROWS", "200000"))
AGENT_CSV_ANALYZE_MAX_BYTES = int(os.getenv("AGENT_CSV_ANALYZE_MAX_BYTES", str(5 * 1024 * 1024)))
AGENT_MODE = os.getenv("AGENT_MODE", "sql").lower()
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "128"))
AGENT_COLUMN_SCAN_LIMIT = int(os.getenv("AGENT_COLUMN_SCAN_LIMIT", "2000"))
AGENT_GLOBAL_KB_MIN_WEIGHT = int(os.getenv("AGENT_GLOBAL_KB_MIN_WEIGHT", "4"))
AGENT_GLOBAL_KB_MAX_ENTRIES = int(os.getenv("AGENT_GLOBAL_KB_MAX_ENTRIES", "80"))
AGENT_GLOBAL_KB_LOCK_TIMEOUT_SEC = int(os.getenv("AGENT_GLOBAL_KB_LOCK_TIMEOUT_SEC", "3"))
AGENT_GLOBAL_KB_FACTS = os.getenv("AGENT_GLOBAL_KB_FACTS", "1").strip().lower() in ("1", "true", "yes")
AGENT_GLOBAL_KB_SHARE_ACROSS_SESSIONS = (
    os.getenv("AGENT_GLOBAL_KB_SHARE_ACROSS_SESSIONS", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_GLOBAL_KB_SHARED_READ = (
    os.getenv("AGENT_GLOBAL_KB_SHARED_READ", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_GLOBAL_KB_TYPES = {
    t.strip()
    for t in os.getenv(
        "AGENT_GLOBAL_KB_TYPES",
        "user_confirm,insight,schema_usage,search_pref,schema_insight",
    ).split(",")
    if t.strip()
}
AGENT_KB_ALLOWED_SOURCE_TYPES = {
    t.strip()
    for t in os.getenv(
        "AGENT_KB_ALLOWED_SOURCE_TYPES", "user_confirm,insight,schema_usage,schema_insight"
    ).split(",")
    if t.strip()
}
AGENT_GLOBAL_KB_SHARED_TYPES = {
    t.strip()
    for t in os.getenv(
        "AGENT_GLOBAL_KB_SHARED_TYPES",
        "schema_insight,insight,schema_usage,search_pref",
    ).split(",")
    if t.strip()
}
AGENT_KB_FACT_LIMIT = int(os.getenv("AGENT_KB_FACT_LIMIT", "0"))
AGENT_GLOBAL_KB_FACT_LIMIT = int(os.getenv("AGENT_GLOBAL_KB_FACT_LIMIT", "0"))
AGENT_KB_REQUIRE_EVIDENCE = os.getenv("AGENT_KB_REQUIRE_EVIDENCE", "1").strip().lower() in ("1", "true", "yes")
AGENT_RAG_DOC_MAX_CHARS = int(os.getenv("AGENT_RAG_DOC_MAX_CHARS", "2400"))
AGENT_RAG_CHUNK_SIZE = int(os.getenv("AGENT_RAG_CHUNK_SIZE", "600"))
AGENT_RAG_CHUNK_OVERLAP = int(os.getenv("AGENT_RAG_CHUNK_OVERLAP", "80"))
AGENT_RAG_OBJECT_CATEGORY_ENABLED = (
    os.getenv("AGENT_RAG_OBJECT_CATEGORY_ENABLED", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_RAG_DEPTH_ENABLED = (
    os.getenv("AGENT_RAG_DEPTH_ENABLED", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_RAG_DEPTH_MAX_LEVEL = max(0, min(3, int(os.getenv("AGENT_RAG_DEPTH_MAX_LEVEL", "3"))))
AGENT_CONVO_SEARCH_AUTO = os.getenv("AGENT_CONVO_SEARCH_AUTO", "1").strip().lower() in ("1", "true", "yes")
AGENT_CONVO_SEARCH_LIMIT = int(os.getenv("AGENT_CONVO_SEARCH_LIMIT", "6"))
AGENT_KB_INSIGHT = os.getenv("AGENT_KB_INSIGHT", "1").strip().lower() in ("1", "true", "yes")
AGENT_KB_INSIGHT_MAX_COLS = int(os.getenv("AGENT_KB_INSIGHT_MAX_COLS", "6"))
AGENT_SCHEMA_INSIGHT = (
    os.getenv("AGENT_SCHEMA_INSIGHT", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_SCHEMA_BOOTSTRAP = (
    os.getenv("AGENT_SCHEMA_BOOTSTRAP", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_SCHEMA_BOOTSTRAP_MAX_TABLES = int(os.getenv("AGENT_SCHEMA_BOOTSTRAP_MAX_TABLES", "50"))
AGENT_SCHEMA_INSTANCE_SCAN = (
    os.getenv("AGENT_SCHEMA_INSTANCE_SCAN", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_SCHEMA_INSTANCE_SCAN_EVERY_SEC = int(os.getenv("AGENT_SCHEMA_INSTANCE_SCAN_EVERY_SEC", "21600"))
AGENT_SCHEMA_INSTANCE_SCAN_MAX_SCHEMAS = int(os.getenv("AGENT_SCHEMA_INSTANCE_SCAN_MAX_SCHEMAS", "20"))
AGENT_SCHEMA_INSTANCE_SCAN_TABLE_LIMIT = int(os.getenv("AGENT_SCHEMA_INSTANCE_SCAN_TABLE_LIMIT", "12"))
AGENT_SCHEMA_INSTANCE_SCAN_BUDGET_SEC = int(os.getenv("AGENT_SCHEMA_INSTANCE_SCAN_BUDGET_SEC", "15"))
AGENT_SCHEMA_INSIGHT_MAX_COLS = int(os.getenv("AGENT_SCHEMA_INSIGHT_MAX_COLS", "20"))
AGENT_TABLE_INSIGHT_MAX_COLS = int(os.getenv("AGENT_TABLE_INSIGHT_MAX_COLS", "15"))
AGENT_SCHEMA_INSIGHT_RESCAN_SEC = int(os.getenv("AGENT_SCHEMA_INSIGHT_RESCAN_SEC", "3600"))
AGENT_TABLE_INSIGHT_RESCAN_SEC = int(os.getenv("AGENT_TABLE_INSIGHT_RESCAN_SEC", "3600"))
AGENT_SUMMARY_REFRESH = os.getenv("AGENT_SUMMARY_REFRESH", "1").strip().lower() in ("1", "true", "yes")
AGENT_SUMMARY_REFRESH_EVERY = int(os.getenv("AGENT_SUMMARY_REFRESH_EVERY", "1"))
AGENT_SUMMARY_MAX_RECENT = int(os.getenv("AGENT_SUMMARY_MAX_RECENT", "8"))
AGENT_STEP_TRACE_MAX = int(os.getenv("AGENT_STEP_TRACE_MAX", "50"))
AGENT_STEP_VALIDATION = os.getenv("AGENT_STEP_VALIDATION", "1").strip().lower() in ("1", "true", "yes")
AGENT_STEP_VALIDATION_EVERY = int(os.getenv("AGENT_STEP_VALIDATION_EVERY", "1"))
AGENT_SCHEMA_META_MAX_TABLES = int(os.getenv("AGENT_SCHEMA_META_MAX_TABLES", "20"))
AGENT_SCHEMA_META_MAX_COLS = int(os.getenv("AGENT_SCHEMA_META_MAX_COLS", "60"))
AGENT_SCHEMA_META_CACHE_MAX_TABLES = int(
    os.getenv("AGENT_SCHEMA_META_CACHE_MAX_TABLES", str(AGENT_SCHEMA_META_MAX_TABLES))
)
AGENT_SCHEMA_META_CACHE_MAX_COLS = int(os.getenv("AGENT_SCHEMA_META_CACHE_MAX_COLS", "12"))
AGENT_GLOBAL_SCHEMA_META_CACHE = os.getenv("AGENT_GLOBAL_SCHEMA_META_CACHE", "1").strip().lower() in ("1", "true", "yes")
AGENT_GLOBAL_SCHEMA_META_TTL_SEC = int(os.getenv("AGENT_GLOBAL_SCHEMA_META_TTL_SEC", "21600"))
AGENT_TIMING_LOG = os.getenv("AGENT_TIMING_LOG", "1").strip().lower() in ("1", "true", "yes")
AGENT_SHOW_INTERNAL = os.getenv("AGENT_SHOW_INTERNAL", "0").strip().lower() in ("1", "true", "yes")
AGENT_STORE_INTERNAL_MESSAGES = (
    os.getenv("AGENT_STORE_INTERNAL_MESSAGES", "0").strip().lower() in ("1", "true", "yes")
)
AGENT_DISABLE_AUTO_RETRY = os.getenv("AGENT_DISABLE_AUTO_RETRY", "1").strip().lower() in ("1", "true", "yes")
AGENT_MASK_PII = os.getenv("AGENT_MASK_PII", "1").strip().lower() in ("1", "true", "yes")
AGENT_ERROR_AUTO_RECOVERY = os.getenv("AGENT_ERROR_AUTO_RECOVERY", "1").strip().lower() in ("1", "true", "yes")
AGENT_SIMILAR_RETRY_LIMIT = int(os.getenv("AGENT_SIMILAR_RETRY_LIMIT", "2"))
AGENT_SIMILAR_RETRY_THRESHOLD = float(os.getenv("AGENT_SIMILAR_RETRY_THRESHOLD", "0.85"))
AGENT_DB_CONNECT_RETRIES = int(os.getenv("AGENT_DB_CONNECT_RETRIES", "3"))
AGENT_DB_CONNECT_BACKOFF_SEC = float(os.getenv("AGENT_DB_CONNECT_BACKOFF_SEC", "0.5"))
# ── MySQL 커넥션 풀 (TASK-0144, opt-in / 기본 OFF / 폴백 안전) ──────────────
# 기본 비활성(False) → db.connect() 가 기존 connect-per-request 경로 그대로 사용
# (동작 0 변경). True(canary 로만) 일 때만 (host,user,database) 시그니처별 풀에서
# 커넥션을 대여하고, 풀 소진(PoolError)/풀 생성 실패 시 direct connect 로 폴백한다
# (절대 요청을 실패시키지 않음). app.py async 전환과 무관한 독립 opt-in.
AGENT_DB_POOL_ENABLED = os.getenv("AGENT_DB_POOL_ENABLED", "0").strip().lower() in ("1", "true", "yes")
# 시그니처별 풀 크기. mysql.connector 풀은 1..32 범위만 허용하므로 clamp.
AGENT_DB_POOL_SIZE = max(1, min(32, int(os.getenv("AGENT_DB_POOL_SIZE", "8") or "8")))
# overflow 의미: 풀 소진 시 풀 밖 direct connect 를 추가 허용할지(True=폴백 허용,
# 기본 True 라 풀 소진이 절대 요청 실패가 되지 않음). False 면 풀 소진 시에도 폴백
# 하지만(안전 우선) 경고 로그만 강화 — 의미적으로 "풀 밖 커넥션을 허용하느냐" 신호.
AGENT_DB_POOL_MAX_OVERFLOW = os.getenv("AGENT_DB_POOL_MAX_OVERFLOW", "1").strip().lower() in ("1", "true", "yes")
# 풀 커넥션 대여 시 reset_session(autocommit/세션상태 초기화) 적용 여부.
AGENT_DB_POOL_RESET_SESSION = os.getenv("AGENT_DB_POOL_RESET_SESSION", "1").strip().lower() in ("1", "true", "yes")
AGENT_SEARCH_CACHE_TTL_SEC = int(os.getenv("AGENT_SEARCH_CACHE_TTL_SEC", "600"))
AGENT_META_SEARCH_REPEAT_LIMIT = int(os.getenv("AGENT_META_SEARCH_REPEAT_LIMIT", "2"))
AGENT_META_EXPLORATION_BUDGET = int(
    os.getenv("AGENT_META_EXPLORATION_BUDGET", str(AGENT_META_SEARCH_REPEAT_LIMIT))
)
AGENT_FORCE_CONCLUSION_FACTS = int(os.getenv("AGENT_FORCE_CONCLUSION_FACTS", "3"))
AGENT_DOMAIN_DRIFT_GUARD = os.getenv("AGENT_DOMAIN_DRIFT_GUARD", "1").strip().lower() in ("1", "true", "yes")
AGENT_LLM_REQUEST_PASSTHROUGH = (
    os.getenv("AGENT_LLM_REQUEST_PASSTHROUGH", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_INSIGHT_OBJECT_FASTPATH = (
    os.getenv("AGENT_INSIGHT_OBJECT_FASTPATH", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_SEARCH_PREF_FROM_METADATA = (
    os.getenv("AGENT_SEARCH_PREF_FROM_METADATA", "0").strip().lower() in ("1", "true", "yes")
)
AGENT_INSIGHT_OBJECT_MIN_SCORE = int(os.getenv("AGENT_INSIGHT_OBJECT_MIN_SCORE", "3"))
AGENT_INSIGHT_OBJECT_MAX_CANDIDATES = int(os.getenv("AGENT_INSIGHT_OBJECT_MAX_CANDIDATES", "5"))
AGENT_INSIGHT_OBJECT_VERIFY_ONCE = (
    os.getenv("AGENT_INSIGHT_OBJECT_VERIFY_ONCE", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_INSIGHT_OBJECT_VERIFY_TIMEOUT_MS = int(
    os.getenv("AGENT_INSIGHT_OBJECT_VERIFY_TIMEOUT_MS", "1500")
)
AGENT_INSIGHT_FASTPATH_ALLOW_WITH_PASSTHROUGH = (
    os.getenv("AGENT_INSIGHT_FASTPATH_ALLOW_WITH_PASSTHROUGH", "1").strip().lower()
    in ("1", "true", "yes")
)
AGENT_RAG_PRIORITY_SHORT_CIRCUIT = (
    os.getenv("AGENT_RAG_PRIORITY_SHORT_CIRCUIT", "0").strip().lower() in ("1", "true", "yes")
)
AGENT_RAG_PRIORITY_SHORT_CIRCUIT_ALLOW_WITH_PASSTHROUGH = (
    os.getenv("AGENT_RAG_PRIORITY_SHORT_CIRCUIT_ALLOW_WITH_PASSTHROUGH", "0").strip().lower()
    in ("1", "true", "yes")
)
AGENT_INSIGHT_SQL_COMPOSE_TIMEOUT_SEC = int(
    os.getenv("AGENT_INSIGHT_SQL_COMPOSE_TIMEOUT_SEC", "20")
)
AGENT_SQL_GROUNDED_REVIEW = (
    os.getenv("AGENT_SQL_GROUNDED_REVIEW", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_SQL_GROUNDED_REVIEW_TIMEOUT_SEC = int(
    os.getenv("AGENT_SQL_GROUNDED_REVIEW_TIMEOUT_SEC", "12")
)
AGENT_SQL_GROUNDED_REWRITE_ON_FAIL = (
    os.getenv("AGENT_SQL_GROUNDED_REWRITE_ON_FAIL", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_SQL_GROUNDED_BLOCK_ON_FAIL = (
    os.getenv("AGENT_SQL_GROUNDED_BLOCK_ON_FAIL", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_KNOWLEDGE_SQL_FALLBACK = (
    os.getenv("AGENT_KNOWLEDGE_SQL_FALLBACK", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC = int(
    os.getenv("AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC", "20")
)
AGENT_KNOWLEDGE_SQL_FALLBACK_MAX_OBJECT_TRIES = int(
    os.getenv("AGENT_KNOWLEDGE_SQL_FALLBACK_MAX_OBJECT_TRIES", "2")
)
AGENT_SCHEMA_USAGE_RECORD_STRICT = (
    os.getenv("AGENT_SCHEMA_USAGE_RECORD_STRICT", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_SEARCH_OBJECTS_INCLUDE_TABLE_META = (
    os.getenv("AGENT_SEARCH_OBJECTS_INCLUDE_TABLE_META", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_SEARCH_OBJECTS_META_MAX_TABLES = int(os.getenv("AGENT_SEARCH_OBJECTS_META_MAX_TABLES", "0"))
AGENT_MEMORY_CLEAR_KEEP_IDS = tuple(
    cid.strip()
    for cid in os.getenv(
        "AGENT_MEMORY_CLEAR_KEEP_IDS",
        "__global__",
    ).split(",")
    if cid.strip()
)
AGENT_EARLY_FINALIZE_MS = int(os.getenv("AGENT_EARLY_FINALIZE_MS", "90000"))
AGENT_FACT_QUALITY_LOG = os.getenv("AGENT_FACT_QUALITY_LOG", "1").strip().lower() in ("1", "true", "yes")
AGENT_INSIGHT_ROUTE_LOG = os.getenv("AGENT_INSIGHT_ROUTE_LOG", "1").strip().lower() in ("1", "true", "yes")
AGENT_INSIGHT_ROUTE_LOG_MAX_CANDIDATES = int(
    os.getenv("AGENT_INSIGHT_ROUTE_LOG_MAX_CANDIDATES", "5")
)
AGENT_FACT_ENTRIES_MAX_PER_KEY = int(os.getenv("AGENT_FACT_ENTRIES_MAX_PER_KEY", "4"))
AGENT_FACT_SINGLE_KEY_SOURCES = {
    t.strip()
    for t in os.getenv("AGENT_FACT_SINGLE_KEY_SOURCES", "schema_insight").split(",")
    if t.strip()
}
AGENT_FACT_SINGLE_KEY_PREFIXES = tuple(
    t.strip()
    for t in os.getenv(
        "AGENT_FACT_SINGLE_KEY_PREFIXES",
        "schema_insight:,schema_pref:,table_pref:",
    ).split(",")
    if t.strip()
)
AGENT_SCHEMA_BIAS_STEP_WINDOW = int(os.getenv("AGENT_SCHEMA_BIAS_STEP_WINDOW", "10"))
AGENT_SCHEMA_BIAS_THRESHOLD = float(os.getenv("AGENT_SCHEMA_BIAS_THRESHOLD", "0.45"))
AGENT_SCHEMA_BIAS_PENALTY = int(os.getenv("AGENT_SCHEMA_BIAS_PENALTY", "4"))
AGENT_INSIGHT_TIMEOUT_SEC = int(os.getenv("AGENT_INSIGHT_TIMEOUT_SEC", "30"))
AGENT_PLAN_TIMEOUT_SEC = int(os.getenv("AGENT_PLAN_TIMEOUT_SEC", "35"))
AGENT_PLAN_TIMEOUT_RECOVERY_SEC = int(os.getenv("AGENT_PLAN_TIMEOUT_RECOVERY_SEC", "20"))
AGENT_PLAN_TIMEOUT_MIN_SEC = int(os.getenv("AGENT_PLAN_TIMEOUT_MIN_SEC", "8"))
AGENT_AUX_SKIP_NEAR_DEADLINE_MS = int(
    os.getenv("AGENT_AUX_SKIP_NEAR_DEADLINE_MS", "15000")
)
AGENT_RAG_PRIORITY_TIMEOUT_SEC = int(
    os.getenv("AGENT_RAG_PRIORITY_TIMEOUT_SEC", "12")
)
AGENT_RAG_PRIORITY_FIRST = (
    os.getenv("AGENT_RAG_PRIORITY_FIRST", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_OBJECT_RESOLVE_TIMEOUT_SEC = int(
    os.getenv("AGENT_OBJECT_RESOLVE_TIMEOUT_SEC", "8")
)
AGENT_OBJECT_RESOLVE_BATCH_SIZE = int(
    os.getenv("AGENT_OBJECT_RESOLVE_BATCH_SIZE", "40")
)
AGENT_OBJECT_RESOLVE_MAX_BATCHES = int(
    os.getenv("AGENT_OBJECT_RESOLVE_MAX_BATCHES", "6")
)
AGENT_INSIGHT_OBJECT_DB_FETCH_LIMIT = int(
    os.getenv("AGENT_INSIGHT_OBJECT_DB_FETCH_LIMIT", "120")
)
AGENT_OBJECT_PICK_MIN_CONFIDENCE = float(
    os.getenv("AGENT_OBJECT_PICK_MIN_CONFIDENCE", "0.55")
)
AGENT_RAG_DOC_OBJECT_SCORE_BOOST = float(
    os.getenv("AGENT_RAG_DOC_OBJECT_SCORE_BOOST", "24")
)
_insight_worker_enabled_raw = os.getenv("AGENT_INSIGHT_WORKER_ENABLED", "1").strip() or "1"
AGENT_INSIGHT_WORKER_ENABLED = _insight_worker_enabled_raw.lower() in ("1", "true", "yes")
AGENT_INSIGHT_WORKER_TICK_SEC = int(
    (os.getenv("AGENT_INSIGHT_WORKER_TICK_SEC", "8") or "8").strip()
)
# read 정본(PG)이 닿지 않는 degraded 상태에서 worker 가 tick 대신 쉬는 backoff(sec).
# PG 부재 시 read-back 이 (빈) MySQL fallback 으로 떨어져 모든 artifact/fingerprint 가
# missing/changed 로 오판 → 무의미한 재생성(livelock 동력)을 반복하므로, 그 상태에선
# 짧은 tick(8s) 대신 길게 쉬며 PG 복구를 기다린다.
AGENT_INSIGHT_WORKER_DEGRADED_BACKOFF_SEC = int(
    (os.getenv("AGENT_INSIGHT_WORKER_DEGRADED_BACKOFF_SEC", "300") or "300").strip()
)
AGENT_INSIGHT_WORKER_JITTER_SEC = int(
    (os.getenv("AGENT_INSIGHT_WORKER_JITTER_SEC", "0") or "0").strip()
)
AGENT_INSIGHT_WORKER_LOCK_TIMEOUT_SEC = int(
    (os.getenv("AGENT_INSIGHT_WORKER_LOCK_TIMEOUT_SEC", "1") or "1").strip()
)
AGENT_INSIGHT_WORKER_STALE_SEC = int(
    (os.getenv("AGENT_INSIGHT_WORKER_STALE_SEC", "15") or "15").strip()
)
_inline_insight_on_ask_raw = os.getenv("AGENT_INLINE_INSIGHT_ON_ASK", "0").strip() or "0"
AGENT_INLINE_INSIGHT_ON_ASK = _inline_insight_on_ask_raw.lower() in ("1", "true", "yes")
AGENT_INSIGHT_WORKER_LOCK_NAME = os.getenv(
    "AGENT_INSIGHT_WORKER_LOCK_NAME", "agent_insight_worker_scan"
).strip()
AGENT_INSIGHT_WORKER_CONVERSATION_ID = "__insight_worker__"

# ── out-of-process ask-worker (TASK-0169, DESIGN-ask-worker.md) ──
# 실행모델 토글: inprocess(기본, 현행 asyncio.to_thread) | worker(ask_jobs enqueue).
# worker 검증 전까지 inprocess 경로 + TASK-0164 finalizer 를 보존(즉시 rollback 용).
AGENT_ASK_EXECUTION_MODE = (
    os.getenv("AGENT_ASK_EXECUTION_MODE", "inprocess").strip().lower() or "inprocess"
)
_ask_worker_enabled_raw = os.getenv("AGENT_ASK_WORKER_ENABLED", "1").strip() or "1"
AGENT_ASK_WORKER_ENABLED = _ask_worker_enabled_raw.lower() in ("1", "true", "yes")
# claim 폴링 주기(sec) — pending job 이 없으면 이 간격으로 재시도.
AGENT_ASK_WORKER_TICK_SEC = int(
    (os.getenv("AGENT_ASK_WORKER_TICK_SEC", "2") or "2").strip()
)
# job heartbeat 주기(sec) — 실행 중 별도 스레드가 이 간격으로 ask_jobs.heartbeat_at 갱신.
# step 이 아니라 시간 기반이라 긴 LLM step 중에도 갱신돼 false-positive requeue 를 막는다.
AGENT_ASK_WORKER_HEARTBEAT_SEC = int(
    (os.getenv("AGENT_ASK_WORKER_HEARTBEAT_SEC", "10") or "10").strip()
)
# stale 임계(sec) — running job 의 heartbeat 가 이보다 오래 끊기면 죽은 worker 로 보고
# 회수(requeue/error). 정상 장기 run 을 false-positive 로 회수하지 않으려면 run_timeout_sec
# (= agent_core 의 max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)) 보다 충분히
# 커야 한다(BLOCKER/E). 따라서 기본값을 그 추정치 + 180s margin 으로 동적 산출한다 —
# AGENT_TIMEOUT_SEC 를 키운 배포(예: 300 → run_timeout 900)에서도 안전. heartbeat 는
# 시간 기반(step 무관)이라 실제론 worker 프로세스 death 일 때만 트리거된다.
_ask_run_timeout_est = max(int(AGENT_TIMEOUT_SEC) * 3, max(1, int(AGENT_EARLY_FINALIZE_MS / 1000)))
_ask_stale_default = _ask_run_timeout_est + 180
AGENT_ASK_WORKER_STALE_SEC = int(
    (os.getenv("AGENT_ASK_WORKER_STALE_SEC", str(_ask_stale_default)) or str(_ask_stale_default)).strip()
)
# sweeper 실행 주기(sec) — stale job 회수 스캔 간격.
AGENT_ASK_WORKER_SWEEP_EVERY_SEC = int(
    (os.getenv("AGENT_ASK_WORKER_SWEEP_EVERY_SEC", "30") or "30").strip()
)
# requeue attempts cap — 이 횟수 도달 시 terminal error(무한 requeue 차단).
AGENT_ASK_WORKER_ATTEMPTS_CAP = int(
    (os.getenv("AGENT_ASK_WORKER_ATTEMPTS_CAP", "3") or "3").strip()
)
AGENT_ASK_WORKER_JITTER_SEC = int(
    (os.getenv("AGENT_ASK_WORKER_JITTER_SEC", "0") or "0").strip()
)
AGENT_ASK_WORKER_CONVERSATION_ID = "__ask_worker__"
# worker 생존 heartbeat KV 키(healthcheck + /api/ask readiness gate 가 신선도 검사).
AGENT_ASK_WORKER_HEARTBEAT_KEY = "ask_worker_last_cycle_at"

MCP_URL = os.getenv("MCP_URL", "http://mcp:5000/mcp")
MCP_TIMEOUT_SEC = int(os.getenv("MCP_TIMEOUT_SEC", "20"))
MCP_PROTOCOL = os.getenv("MCP_PROTOCOL", "jsonrpc").lower()
MCP_SESSION_ID = None
MCP_REQUEST_ID = 1
MCP_EXECUTE_SQL_CANDIDATES = ("execute_sql", "query_sql")
MCP_SEARCH_OBJECTS_CANDIDATES = ("search_objects", "list_objects", "describe_objects", "list_tables", "show_tables")
LOCAL_TOOLS = {"file_search", "file_read", "restore_sql", "convo_search"}
MEMORY_CONTEXT_KEYS = (
    "origin_request",
    "thread_goal",
    "last_user_request",
    "last_assistant_question",
    "last_error",
    "last_error_type",
    "last_error_hint",
    "last_result_summary",
    "last_sql",
    "last_zero_result",
    "last_zero_sql",
    "last_zero_intent",
    "last_zero_run_id",
    "last_zero_diag_run",
    "kb_compact",
    "last_csv_preview",
    "last_file_search",
    "last_search_objects",
    "last_file_read",
    "last_file_read_path",
    "last_step_validation",
    "last_step_summary",
    "last_insight",
    "last_user_answer",
    "last_enriched_table",
    "last_convo_search",
    "preferred_schema",
    "global_kb_compact",
    "retry_hint",
    "retry_similar_count",
    "ask_loop_count",
    "meta_compact_mode",
    "last_auto_recovery",
    "followup_resolved_request",
    "last_forced_conclusion",
    "last_error_signature",
    "last_error_signature_count",
    "domain_anchor",
    "last_domain_drift",
    "global_fast_path_used",
    "cross_session_anchor_schema",
    "cross_session_anchor_table",
    "last_resolved_object",
    "last_resolved_object_score",
    "last_resolved_object_source",
    "last_resolved_object_at",
    "last_resolved_fact_key",
)

# 현재 실행(run_once) 단위의 메시지-스텝 연결을 위해 사용
CURRENT_RUN_ID = ""
CURRENT_RUN_DEADLINE_TS = 0.0
KNOWN_SCHEMAS: list[str] = []
GLOBAL_CONVERSATION_ID = "__global__"
FACT_SCOPE_COMMON = "common"
CURRENT_FACT_SCOPE_KEY = FACT_SCOPE_COMMON
GLOBAL_SESSION_CONVERSATION_ID = ""
MEMORY_CONVERSATION_ID = ""
