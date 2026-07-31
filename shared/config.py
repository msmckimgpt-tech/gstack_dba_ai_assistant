import mysql.connector
__all__ = [
    "AGENT_ACCOUNT_INSIGHT_EXTRACT",
    "AGENT_ACCOUNT_INSIGHT_EXTRACT_MAX_CONVS",
    "AGENT_ACCOUNT_INSIGHT_INJECT",
    "AGENT_ACCOUNT_INSIGHT_MAX_CONVS",
    "AGENT_ACCOUNT_INSIGHT_MIN_SIM",
    "AGENT_ACCOUNT_INSIGHT_MIN_SUMMARY_LEN",
    "AGENT_ACCOUNT_INSIGHT_RECALL",
    "AGENT_ACCOUNT_INSIGHT_TOP_K",
    "AGENT_AUX_SKIP_NEAR_DEADLINE_MS",
    "AGENT_COLUMN_SCAN_LIMIT",
    "AGENT_CONVO_SEARCH_AUTO",
    "AGENT_CONVO_SEARCH_LIMIT",
    "AGENT_CSV_ANALYZE_MAX_BYTES",
    "AGENT_CONN_AVG_WINDOW",
    "AGENT_CONN_DOWN_AFTER_FAILS",
    "AGENT_CONN_HEALTH_ENABLED",
    "AGENT_CONN_HEALTH_TICK_SEC",
    "AGENT_CONN_HEALTHY_RECHECK_SEC",
    "AGENT_CONN_PROBE_TIMEOUT_MS_BASE",
    "AGENT_CONN_PROBE_TIMEOUT_MS_MAX",
    "AGENT_CONN_PROBE_WORKERS",
    "AGENT_CONN_SLOW_MS",
    "AGENT_CONN_STALE_GRACE_SEC",
    "AGENT_CONN_TCP_TIMEOUT_MS",
    "AGENT_CONN_UNSTABLE_RECHECK_MAX_SEC",
    "AGENT_CONN_UNSTABLE_RECHECK_SEC",
    "AGENT_CSV_ANALYZE_MAX_ROWS",
    "AGENT_CSV_PREVIEW_ROWS",
    "AGENT_DB_CONNECT_BACKOFF_SEC",
    "AGENT_DB_CONNECT_RETRIES",
    "AGENT_DB_CONNECT_TIMEOUT_SEC",
    "AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC",
    "AGENT_DB_POOL_ENABLED",
    "AGENT_DB_POOL_MAX_OVERFLOW",
    "AGENT_DB_POOL_RESET_SESSION",
    "AGENT_DB_POOL_SIZE",
    "AGENT_DISABLE_AUTO_RETRY",
    "AGENT_DS_CONN_PING_IDLE_SEC",
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
    "AGENT_INSIGHT_OFFHOURS_MODEL",
    "AGENT_INSIGHT_BUSINESS_START_HOUR",
    "AGENT_INSIGHT_BUSINESS_END_HOUR",
    "AGENT_INSIGHT_BUSINESS_TZ_OFFSET_HOURS",
    "AGENT_INSIGHT_TABLE_GROUPING_ENABLED",
    "AGENT_INSIGHT_TABLE_GROUP_MIN_MEMBERS",
    "AGENT_INSIGHT_TABLE_GROUP_FANOUT_MAX",
    "AGENT_NODE_ANALYSIS_MODEL",
    # analysis-retry-resilience: 일시 실패 재시도·회로차단 knob. rel-selfheal(아래 주석) 교훈대로
    #   `from shared.config import *` 소비처에서 NameError 가 나지 않게 __all__ 에 함께 등록한다.
    "AGENT_NODE_ANALYSIS_MAX_ATTEMPTS",
    "AGENT_NODE_ANALYSIS_RETRY_BASE_SEC",
    "AGENT_NODE_ANALYSIS_RETRY_MAX_SEC",
    "AGENT_NODE_ANALYSIS_CIRCUIT_FAILS",
    "AGENT_NODE_ANALYSIS_SCHEMA_CAP",
    "AGENT_NODE_ANALYSIS_SCHEMA_MAX",
    "AGENT_NODE_ANALYSIS_SCHEMA_DEPTH",
    "AGENT_NODE_ANALYSIS_SCHEMA_EXPAND_FACTOR",
    "AGENT_NODE_ANALYSIS_SCHEMA_RUN_BUDGET_MAX",
    "AGENT_NODE_ANALYSIS_THIN_CHARS",
    "AGENT_NODE_ANALYSIS_REFINE_MAX",
    "AGENT_NODE_ANALYSIS_SUGGEST_LINKS_MAX",
    "AGENT_NODE_ANALYSIS_PARENT_TABLE_REL",
    "AGENT_NODE_ANALYSIS_COLUMN_INTROSPECT_CAP",
    "AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE",
    "AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE_MODE",
    "AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP",
    "AGENT_NODE_ANALYSIS_AUTO_CHANGE_COOLDOWN_SEC",
    "AGENT_NODE_ANALYSIS_AUTO_EXPAND_FACTOR",
    "AGENT_INSIGHT_OBJECT_DB_FETCH_LIMIT",
    "AGENT_INSIGHT_OBJECT_FASTPATH",
    "AGENT_INSIGHT_OBJECT_MAX_CANDIDATES",
    "AGENT_INSIGHT_OBJECT_MIN_SCORE",
    "AGENT_INSIGHT_OBJECT_VERIFY_ONCE",
    "AGENT_INSIGHT_OBJECT_VERIFY_TIMEOUT_MS",
    "AGENT_INSIGHT_ROUTE_LOG",
    "AGENT_INSIGHT_ROUTE_LOG_MAX_CANDIDATES",
    "AGENT_INSIGHT_SQL_COMPOSE_TIMEOUT_SEC",
    "AGENT_INSIGHT_AUTH_COOLDOWN_SEC",
    "AGENT_INSIGHT_TIMEOUT_SEC",
    "AGENT_INSIGHT_WORKER_CONVERSATION_ID",
    "AGENT_INSIGHT_WORKER_ENABLED",
    "AGENT_INSIGHT_WORKER_JITTER_SEC",
    "AGENT_INSIGHT_WORKER_LOCK_NAME",
    "AGENT_INSIGHT_WORKER_LOCK_TIMEOUT_SEC",
    "AGENT_INSIGHT_WORKER_STALE_SEC",
    "AGENT_INSIGHT_WORKER_TICK_SEC",
    "AGENT_INSIGHT_WORKER_DEGRADED_BACKOFF_SEC",
    "AGENT_GLOSSARY_AUTOPROPOSE",
    "AGENT_GLOSSARY_SUGGEST_MODEL",
    "AGENT_GLOSSARY_AUTOPROMOTE_THRESHOLD",
    "AGENT_GLOSSARY_SUGGEST_MAX",
    "AGENT_ENUM_AUTOPROPOSE",
    "AGENT_ENUM_SUGGEST_MODEL",
    "AGENT_ENUM_AUTOPROMOTE_THRESHOLD",
    "AGENT_ENUM_SUGGEST_MAX",
    "AGENT_ENUM_SCHEMA_GROUNDING",
    "AGENT_ENUM_SELF_HEAL",
    "AGENT_ASK_EXECUTION_MODE",
    "AGENT_ASK_WORKER_ENABLED",
    "AGENT_ASK_WORKER_TICK_SEC",
    "AGENT_ASK_WORKER_IDLE_POLL_SEC",
    "AGENT_ASK_WORKER_HEARTBEAT_SEC",
    "AGENT_ASK_WORKER_STALE_SEC",
    "AGENT_ASK_WORKER_SWEEP_EVERY_SEC",
    "AGENT_ASK_WORKER_ATTEMPTS_CAP",
    "AGENT_ASK_WORKER_JITTER_SEC",
    "AGENT_ASK_WORKER_DRAIN_SEC",
    "AGENT_ASK_WORKER_ROLE_STALE_SEC",
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
    "AGENT_TOOL_RESULT_MAX_CHARS",
    "AGENT_ROUTINE_DEF_CHUNK_CHARS",
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
    # rel-selfheal: AGENT_RELATIONSHIP_* 가 __all__ 에 누락돼 `from shared.config import *`
    # 소비자(insight.py)에서 NameError → per-schema `except: continue` 가 삼켜 **insight 스캔의
    # 스키마 처리 전체(인사이트 갱신 + FK introspect + 암묵 추론 + 프로브)가 3일간 조용히 정지**
    # 했던 근본원인. star-import 소비 모듈에서 bare 로 쓰는 이름은 반드시 여기 등재한다
    # (회귀 가드: tests/test_config_star_export.py).
    "AGENT_RELATIONSHIP_INFERENCE_ENABLED",
    "AGENT_RELATIONSHIP_INFER_CAP",
    "AGENT_RELATIONSHIP_INTROSPECT_ENABLED",
    "AGENT_RELATIONSHIP_LEARNING_ENABLED",
    "AGENT_RELATIONSHIP_PROBE_CAP",
    "AGENT_RELATIONSHIP_PROBE_ENABLED",
    "AGENT_RELATIONSHIP_PROBE_SAMPLE",
    "AGENT_RELATIONSHIP_PROBE_TIMEOUT_MS",
    "AGENT_RELATIONSHIP_REINFER_SEC",
    # graph-funcproc(ADR-016): insight.py(star-import) 가 bare 로 소비 — 등재 의무(rel-selfheal 계약).
    "AGENT_ROUTINE_INTROSPECT_CAP",
    "AGENT_ROUTINE_INTROSPECT_ENABLED",
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
    "AGENT_SQL_FIX_MODEL",
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
    "AGENT_QUERY_CONFIRM_HEAVY_TRUST_LLM",
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
    "AGENT_MULTI_DATASOURCE_ENABLED",
    "DATASOURCES",
    "datasource_public",
    "set_active_datasource",
    "set_active_database",
    "get_active_database",
    "get_active_datasource",
    "get_active_datasource_engine",
    "get_active_default_db",
    # metadata-product-scope: KB 메타데이터 거버넌스 축(제품)
    "PRODUCT_SCOPE_PREFIX",
    "product_scope_key",
    "is_product_scope",
    "set_active_product",
    "get_active_product_scope",
    "is_product_scope_unresolved",
    "AGENT_KB_LEGACY_DS_SCOPE_READ",
    "ds_fact_key",
    "ds_object_suffix",
    "ds_fact_like",
    "ds_strip_prefix",
    "ds_scope_name",
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
    "AGENT_SCRATCH_PG_DB",
    "AGENT_SCRATCH_PG_USER",
    "AGENT_SCRATCH_PG_PASSWORD",
    "AGENT_SCRATCH_PG_HOST",
    "AGENT_SCRATCH_PG_PORT",
    "AGENT_SCRATCH_PG_SSLMODE",
    "AGENT_SCRATCH_PG_CONFIGURED",
    "AGENT_KB_EMBEDDING_MODEL",
    "AGENT_KB_EMBEDDING_DIM",
    "AGENT_KB_EMBEDDING_BATCH_SIZE",
    "AGENT_KB_EMBEDDING_TIMEOUT_SEC",
    "AGENT_KB_EMBEDDING_MAX_ATTEMPTS",
    "AGENT_KB_QUERY_EMBED_TIMEOUT_SEC",
    "AGENT_KB_EMBEDDING_AUTO",
    "AGENT_KB_EMBEDDING_BATCH_MAX_ROWS",
    "AGENT_KB_EMBEDDING_INTERVAL_SEC",
    "AGENT_METADATA_CLUSTER_AUTO",
    "AGENT_METADATA_CLUSTER_INTERVAL_SEC",
    "AGENT_METADATA_CLUSTER_SIG_BATCH_MAX_ROWS",
    "AGENT_METADATA_CLUSTER_RECOMPUTE_SEC",
    "AGENT_METADATA_CLUSTER_SIM_THRESHOLD",
    "AGENT_METADATA_CLUSTER_KNN_K",
    "AGENT_METADATA_CLUSTER_MIN_SIZE",
    "AGENT_METADATA_CLUSTER_MAX_DEGREE",
    "AGENT_METADATA_CLUSTER_FULLMATRIX_MAX_N",
    "AGENT_METADATA_CLUSTER_LABEL_LLM",
    "AGENT_METADATA_CLUSTER_MAX_SIZE",
    "AGENT_METADATA_CLUSTER_ATTACH_SIM",
    "AGENT_METADATA_CLUSTER_MERGE_SIM",
    "AGENT_METADATA_CLUSTER_MERGE_MARGIN",
    "AGENT_METADATA_CLUSTER_BRIDGE_MIN_FRAC",
    "AGENT_METADATA_CLUSTER_MERGE_MAX_SIZE",
    "AGENT_METADATA_CLUSTER_GRID_ORDER",
    "AGENT_XDS_RELATIONSHIP_INFER_AUTO",
    "AGENT_XDS_RELATIONSHIP_INFER_INTERVAL_SEC",
    "AGENT_XDS_RELATIONSHIP_MIN_SIM",
    "AGENT_XDS_RELATIONSHIP_BATCH_MAX",
    "AGENT_XDS_RELATIONSHIP_MAX_CANDIDATES_PER_SCOPE",
    "AGENT_XDS_RELATIONSHIP_KNN_K",
    "AGENT_XSCHEMA_RELATIONSHIP_INFER_AUTO",
    "AGENT_XSCHEMA_RELATIONSHIP_MIN_SIM",
    "AGENT_NODE_ANALYSIS_XDS_REFERENCES_FACTOR",
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

# feature-0018 runtime-settings: 관리 콘솔(`시스템 > 설정`)에서 저장한 restart-mode override 를
# import 시 1회 반영한다(공유 볼륨 스냅샷 → 다음 재배포/재시작 시 적용). 방어적 import —
# runtime_settings 가 어떤 이유로든 실패해도 config 는 절대 깨지지 않고 env 기본값을 그대로 쓴다.
# runtime_settings 는 shared.config 를 import 하지 않으므로 순환이 없고, DB 를 만지지 않으므로
# import-time 안전하다. override 미설정/파일부재/kill-switch 면 env_default 를 그대로 반환해
# 기존 동작과 byte-동치가 유지된다.
try:
    from shared.runtime_settings import startup_int as _startup_int
except Exception:  # pragma: no cover
    def _startup_int(key, env_default):  # type: ignore[misc]
        return env_default

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

# ── 멀티 datasource (P1, DESIGN-multi-datasource.md Stage 1) ────────────────────
# multi-MySQL: 사용자가 여러 MySQL datasource 를 등록하고 product 별로 분석 대상을
# 고를 수 있게 한다. P1 은 MySQL 전용(engine='mysql'), MSSQL 은 Stage 2.
#
# 보안 전제 (DESIGN §4 Q7 security-first):
#   - 자격증명은 .env (named credential) 에만 — DB·job payload 에 평문 비저장 (MVP 시크릿 전략).
#   - DS_<KEY>_USER 는 해당 datasource 의 **최소권한 RO 유저**여야 한다(product 의 허용 스키마에만
#     GRANT SELECT, db_datareader 류 광권한 금지 — Codex-2). 코드는 강제 안 하며 운영 책임.
#   - datasource 접근 RBAC 와 스키마 allowlist 는 기존 product 머신러리(product.access.<key> +
#     _product_allowed_schemas)가 그대로 담당 → datasource 는 product 에 매달리고, product 권한이
#     곧 datasource 접근 게이트(연결 전 web /api/ask 에서 enforce).
#
# Env 규약:
#   AGENT_MULTI_DATASOURCE_ENABLED=1            # flag, 기본 OFF(미설정=기존 단일 MySQL 동작 0 변경)
#   AGENT_DATASOURCE_KEYS=prod,bi               # 등록 datasource 키 (comma)
#   DS_PROD_HOST=...  DS_PROD_PORT=3306  DS_PROD_USER=ro_prod  DS_PROD_PASSWORD=...  DS_PROD_DEFAULT_DB=appdb
# 키는 대문자로 env 조회, dict 에는 소문자로 저장. HOST 미설정 키는 무시(불완전 등록 방어).
AGENT_MULTI_DATASOURCE_ENABLED = os.getenv(
    "AGENT_MULTI_DATASOURCE_ENABLED", "0"
).strip().lower() in ("1", "true", "yes")


def _parse_datasources() -> dict:
    """`.env` 의 DS_<KEY>_* named credential 을 {key_lower: {coords}} dict 로 파싱.

    flag 와 무관하게 항상 파싱한다(관리 화면·테스트가 키 목록을 보려면 필요). 실제 라우팅
    활성화는 db.connect() 가 flag 로 게이트한다. HOST 없는 키는 제외(불완전 등록). password 는
    dict 에 담되 로깅 시 마스킹은 호출측 책임(datasource_public 사용).
    """
    keys = [k.strip() for k in os.getenv("AGENT_DATASOURCE_KEYS", "").split(",") if k.strip()]
    out: dict = {}
    for key in keys:
        env_key = key.upper()
        host = os.getenv(f"DS_{env_key}_HOST", "").strip()
        user = os.getenv(f"DS_{env_key}_USER", "").strip()
        # HOST·USER 둘 다 필수. USER 는 해당 datasource 전용 최소권한 RO 유저여야 하며 root(DB_USER)
        # 폴백을 의도적으로 금지한다 (REV-20260610-0187 N-2 — datasource 를 광권한으로 조회하는 심층방어
        # 약화 차단). 둘 중 하나라도 없으면 미등록 처리 → 그 키에 바인딩된 product 는 fail-closed(M-2).
        if not host or not user:
            continue
        out[key.lower()] = {
            "key": key.lower(),
            "engine": (os.getenv(f"DS_{env_key}_ENGINE", "mysql").strip().lower() or "mysql"),
            "host": host,
            "port": int(os.getenv(f"DS_{env_key}_PORT", str(DB_PORT)) or DB_PORT),
            "user": user,
            "password": os.getenv(f"DS_{env_key}_PASSWORD", ""),
            # default_db 는 P1 에서 연결의 암묵 기본 스키마로 적용하지 않는다 (REV-0187 M-1: 미접두 쿼리가
            # allowlist 를 우회해 default_db 를 조회하는 구멍 차단). datasource 경로는 schema-prefixed
            # 쿼리만 허용(database=None) — allowlist 가 유일 게이트. 본 필드는 P2 관리화면 표시용 보존.
            "default_db": (os.getenv(f"DS_{env_key}_DEFAULT_DB", "").strip() or None),
        }
    return out


# {key_lower: {key, engine, host, port, user, password, default_db}}
DATASOURCES = _parse_datasources()


def datasource_public(ds: dict) -> dict:
    """로깅·관리화면 노출용 — password 제거한 사본."""
    return {k: v for k, v in (ds or {}).items() if k != "password"}


# ── 멀티 datasource: insight fact 키 스코프 (P3, DESIGN Codex-3) ────────────────
# insight fact/fingerprint 키를 datasource 차원으로 분리해 datasource A 의 인사이트가
# datasource B 대화에 grounding 으로 교차 노출되는 것을 막는다(Codex-3 메타데이터 격리).
#
# **3자 정합 (livelock 방지)**: write(insight 생성) · read-back(artifact 검증) · grounding(읽기)
# 세 경로가 *반드시 동일 키 포맷*을 써야 한다. 과거 livelock 은 write↔read-back 키 불일치로
# 매 tick 전부 missing 오판해 무한 재생성한 것이었다([[project_insight_livelock_readback_mismatch]]).
# 그래서 키 생성·LIKE·strip 을 본 헬퍼 한 곳으로 통일한다.
#
# 키 포맷:
#   - datasource 없음(기본 단일 MySQL, ds_key=None): `{source}:{suffix}` (무접두 — 역사 데이터 호환,
#     flag OFF 시 동작 0 변경).
#   - datasource(ds_key='prod'): `{source}:ds:prod:{suffix}`. `ds:` 는 스키마명에 들어갈 수 없는
#     구분자라 무접두 키와 명확히 구분된다(LIKE 누출 방지).
import contextvars as _contextvars

_ACTIVE_DATASOURCE_KEY: "_contextvars.ContextVar[str | None]" = _contextvars.ContextVar(
    "active_datasource_key", default=None
)
_DS_KEY_SENTINEL = object()
_ACTIVE_DATASOURCE_ENGINE: "_contextvars.ContextVar[str]" = _contextvars.ContextVar(
    "active_datasource_engine", default="mysql"
)
# TASK-0205 B1: cross-DB 가드(tools.py)가 읽는 **effective default_db**. 제품별 참조 DB override(§2.4)
# 가 연결 DB 를 바꾸면 가드 기준도 같은 값이어야 격리가 안 깨진다 → resolve 시점에 함께 set.
_ACTIVE_DEFAULT_DB: "_contextvars.ContextVar[str | None]" = _contextvars.ContextVar(
    "active_default_db", default=None
)
# TASK-0220: MSSQL multi-database 스캔용 active database(catalog). MSSQL 은 database.schema.table
# 3계층이라 insight fact_key suffix 에 database 를 포함해야 datasource 내 여러 DB 가 구분된다
# (`ds_object_suffix` 가 이 값을 읽어 3계층 suffix 생성). MySQL(schema==database)은 None 유지 → 2계층.
# set_active_datasource 가 datasource 전환 시 None 으로 리셋(이전 DB 누출 차단), insight 의 DB 별
# inner-loop 가 set_active_database 로 명시 설정한다.
_ACTIVE_DATABASE: "_contextvars.ContextVar[str | None]" = _contextvars.ContextVar(
    "active_database", default=None
)


def set_active_datasource(key, engine: str | None = None, default_db: str | None = None) -> None:
    """현재 컨텍스트(스레드/태스크)의 활성 datasource 키·엔진·effective default_db 설정. None=기본 단일 MySQL.

    engine(P5): 활성 datasource 엔진(mysql|mssql) — dialect 선택용. 미지정=mysql.
    default_db(TASK-0205 B1): cross-DB 가드 기준 catalog. 제품별 override 반영값. 미지정 시 None.

    TASK-0220: datasource 전환 시 active database(catalog)도 리셋한다 — 이전 datasource/DB 의
    값이 다음 순회로 누출되면 fact_key 가 잘못된 database 로 스코프된다.
    """
    _ACTIVE_DATASOURCE_KEY.set((str(key).strip().lower() or None) if key else None)
    _ACTIVE_DATASOURCE_ENGINE.set((str(engine).strip().lower() or "mysql") if engine else "mysql")
    _ACTIVE_DEFAULT_DB.set((str(default_db).strip().lower() or None) if default_db else None)
    _ACTIVE_DATABASE.set(None)


def normalize_db_label(database):
    """MSSQL DB(catalog) store label 정규화 — **단일 계약**(§56 RC5). set_active_database 와
    routine_backfill 등 모든 store-label writer 가 이 함수를 공유한다 — 정규화 식이 한쪽만
    바뀌어 writer 간 케이스-변형 이중 적재가 재발하는 drift 를 차단. None=미설정."""
    return (str(database).strip().lower() or None) if database else None


def set_active_database(database: str | None) -> None:
    """TASK-0220: 현재 컨텍스트의 active database(catalog) 설정. MSSQL DB 별 inner-loop 가 호출.

    None=미설정(MySQL 또는 단일 DB) → `ds_object_suffix` 가 2계층 suffix 반환.
    """
    _ACTIVE_DATABASE.set(normalize_db_label(database))


def get_active_database():
    """TASK-0220: active database(catalog). None=미설정(MySQL/단일 DB)."""
    return _ACTIVE_DATABASE.get()


def get_active_datasource_engine() -> str:
    return _ACTIVE_DATASOURCE_ENGINE.get()


def get_active_default_db():
    """cross-DB 가드용 effective default_db (제품 override 반영). None=미설정."""
    return _ACTIVE_DEFAULT_DB.get()


def get_active_datasource():
    return _ACTIVE_DATASOURCE_KEY.get()


# ── 제품(Product) 스코프 — 지식베이스 메타데이터 거버넌스 축 (metadata-product-scope) ──
# 사용자·메타데이터 관리자는 '데이터소스' 가 아니라 **제품** 단위로 작업 범위를 인식한다.
# 그런데 종전 KB 메타데이터(용어사전/ENUM/테이블·컬럼 설명/샘플쿼리)는 활성 datasource 로
# 스코프돼, 제품 하나가 N개 datasource 에 걸치면(라이브: KR_LIVE·KR_QA 각 7개) 등록분이
# 그 중 1개 DS 질의에서만 주입되고, 반대로 1개 datasource 를 N개 제품이 공유하면(라이브:
# mssql-qa-idc 를 5개 제품이 공유) 남의 제품 메타데이터가 섞여 들어왔다.
# → KB 메타데이터의 scope 축을 **제품**으로 통일한다. datasource 축(_ACTIVE_DATASOURCE_KEY)은
#    질의 실행·dialect·fact/RAG 스코핑 용도로 그대로 유지된다(별 축, 무간섭).
PRODUCT_SCOPE_PREFIX = "product."

# ── expand/contract: 이관 전 레거시 datasource-scope 행 호환 읽기 ───────────────
# 코드 배포와 데이터 이관(`scripts/kb_scope_rescope.py`)은 원자적일 수 없다. 그 사이 창에서
# 제품 스코프만 읽으면 **기존 등록 메타데이터가 통째로 안 보인다**(용어·ENUM·설명·샘플).
# 그래서 배포 시점엔 활성 datasource 스코프를 **꼬리 후보**로 함께 읽고(expand — 이 창의 동작은
# 종전과 동일하며 새 회귀가 아니다), 이관 완료 후 본 플래그를 0 으로 내려 contract 한다
# (그래야 공유 datasource 의 타 제품 혼입이 실제로 사라진다).
# 기본 1(=호환 유지) — 이관을 마친 배치는 `AGENT_KB_LEGACY_DS_SCOPE_READ=0` 을 설정한다.
AGENT_KB_LEGACY_DS_SCOPE_READ = os.environ.get("AGENT_KB_LEGACY_DS_SCOPE_READ", "1").strip().lower() not in ("0", "false", "no", "off")

_ACTIVE_PRODUCT_SCOPE: "_contextvars.ContextVar[str | None]" = _contextvars.ContextVar(
    "active_product_scope", default=None
)
# "제품 없음"(정상 — 제품 미선택 대화/CLI)과 "제품이 있는데 해소 실패"(transient DB 오류)를 구별한다.
# 읽기(주입)는 둘 다 fail-open('common' 공용 사전만)이지만, **쓰기(자율수집)는 후자에서 반드시
# 중단**해야 한다 — 'common' 으로 폴백하면 특정 제품의 용어/ENUM 제안이 전 제품에 퍼진다
# (cross-product isolation 위반). 기본 False.
_PRODUCT_SCOPE_UNRESOLVED: "_contextvars.ContextVar[bool]" = _contextvars.ContextVar(
    "product_scope_unresolved", default=False
)


def product_scope_key(product_key) -> "str | None":
    """제품 식별자(ProductKey) → KB 메타데이터 scope_key (`product.<key>`). 빈값이면 None.

    `_sanitize_key_part` 허용 문자([A-Za-z0-9_.-])만 남기므로 `:` 대신 `.` 를 구분자로 쓴다.
    datasource scope_key 는 `mysql-<hash>`/`mssql-<hash>` 또는 .env 라벨이라 접두사가 겹치지 않는다.
    """
    raw = str(product_key or "").strip().lower()
    if not raw:
        return None
    if raw.startswith(PRODUCT_SCOPE_PREFIX):
        return raw
    return PRODUCT_SCOPE_PREFIX + raw


def is_product_scope(scope_key) -> bool:
    """scope_key 가 제품 스코프인지."""
    return str(scope_key or "").strip().lower().startswith(PRODUCT_SCOPE_PREFIX)


def set_active_product(product_key, *, unresolved: bool = False) -> None:
    """현재 컨텍스트의 활성 제품 스코프 설정. None=미지정(제품 없는 대화/CLI).

    `set_active_datasource` 와 동일한 ContextVar 패턴 — run 시작 시 agent_core 가 설정하고
    KB 메타데이터 로더가 읽는다(로더 시그니처에 product 를 실어 나르지 않기 위함).

    unresolved=True: 대화에 제품이 있으나 스코프 해소에 실패했다는 신호(자율수집 차단용).
    """
    _ACTIVE_PRODUCT_SCOPE.set(product_scope_key(product_key))
    _PRODUCT_SCOPE_UNRESOLVED.set(bool(unresolved))


def get_active_product_scope():
    """활성 제품 스코프 키(`product.<key>`). None=미지정 → 공용(common)만 적용."""
    return _ACTIVE_PRODUCT_SCOPE.get()


def is_product_scope_unresolved() -> bool:
    """대화에 제품이 있는데 스코프를 해소하지 못한 상태인지(자율수집은 이때 중단)."""
    return bool(_PRODUCT_SCOPE_UNRESOLVED.get())


# feature-0022: 현재 컨텍스트의 활성 대화 id. scratch 도구(scratch_import/scratch_sql/
# scratch_reset)가 대화별 스키마(s_<hash>)를 고르려면 tool 실행 시점에 conversation_id 를
# 알아야 하는데, tool 핸들러 시그니처는 (conn, args) 라 인자로 못 받는다. set_active_datasource
# 와 동일한 ContextVar 패턴으로 run 시작 시 agent_core 가 설정하고 scratch 핸들러가 읽는다.
_ACTIVE_CONVERSATION_ID: "_contextvars.ContextVar[str | None]" = _contextvars.ContextVar(
    "active_conversation_id", default=None
)


def set_active_conversation_id(conversation_id: str | None) -> None:
    """현재 컨텍스트(스레드/태스크)의 활성 대화 id 설정. None=미지정(CLI/legacy)."""
    _ACTIVE_CONVERSATION_ID.set((str(conversation_id).strip() or None) if conversation_id else None)


def get_active_conversation_id():
    """활성 대화 id (scratch 대화별 스키마 스코프용). None=미지정."""
    return _ACTIVE_CONVERSATION_ID.get()


def ds_fact_key(source: str, suffix: str, *, ds_key=_DS_KEY_SENTINEL) -> str:
    """datasource 로 스코프한 fact/fingerprint 키. ds_key 미지정 시 ContextVar 사용."""
    if ds_key is _DS_KEY_SENTINEL:
        ds_key = _ACTIVE_DATASOURCE_KEY.get()
    if not ds_key:
        return f"{source}:{suffix}"
    return f"{source}:ds:{ds_key}:{suffix}"


def ds_object_suffix(schema: str, table: str | None = None, *, database=_DS_KEY_SENTINEL) -> str:
    """TASK-0220: fact_key 의 object suffix 를 생성한다. active database(catalog) 가 있으면(MSSQL
    multi-DB) database 를 최상위로 포함해 3계층, 없으면(MySQL/단일 DB) 2계층.

    - MySQL(database 미설정):  schema 만 → `{schema}`,        table 동반 → `{schema}.{table}`
    - MSSQL(database 설정):    schema 만 → `{database}.{schema}`, table 동반 → `{database}.{schema}.{table}`

    database 명시값을 주면 ContextVar 대신 그 값을 쓴다(테스트/명시 호출용). ds_fact_key 시그니처는
    불변 유지 — 본 헬퍼가 suffix 만 만들고 ds_fact_key(source, suffix) 로 합성한다(write·read-back·
    grounding 3자 정합 보존).
    """
    if database is _DS_KEY_SENTINEL:
        database = _ACTIVE_DATABASE.get()
    db = (str(database).strip().lower() or None) if database else None
    head = f"{db}.{schema}" if db else f"{schema}"
    return f"{head}.{table}" if table else head


def ds_fact_like(source: str, *, ds_key=_DS_KEY_SENTINEL):
    """grounding 읽기용 LIKE 패턴 + 제외 패턴. (like, not_like) 튜플 반환.

    - ds_key=None(기본): `{source}:%` 매치하되 `{source}:ds:%`(datasource 키)는 **제외**
      (기본 대화에 datasource 인사이트가 새지 않게). → (f"{source}:%", f"{source}:ds:%")
    - ds_key='prod': `{source}:ds:prod:%` 만 매치. not_like=None.
    """
    if ds_key is _DS_KEY_SENTINEL:
        ds_key = _ACTIVE_DATASOURCE_KEY.get()
    if not ds_key:
        return (f"{source}:%", f"{source}:ds:%")
    return (f"{source}:ds:{ds_key}:%", None)


def ds_scope_name(name: str, *, ds_key=_DS_KEY_SENTINEL) -> str:
    """스캔 커서 등 KV 이름을 datasource 로 분리. ds 없으면 그대로(기존 호환)."""
    if ds_key is _DS_KEY_SENTINEL:
        ds_key = _ACTIVE_DATASOURCE_KEY.get()
    return name if not ds_key else f"{name}:ds:{ds_key}"


def ds_strip_prefix(source: str, fact_key: str, *, ds_key=_DS_KEY_SENTINEL) -> str:
    """fact_key 에서 `{source}:` 또는 `{source}:ds:{ds_key}:` 접두를 제거해 suffix 만 반환."""
    if ds_key is _DS_KEY_SENTINEL:
        ds_key = _ACTIVE_DATASOURCE_KEY.get()
    key = str(fact_key or "")
    if ds_key:
        pre = f"{source}:ds:{ds_key}:"
        if key.startswith(pre):
            return key[len(pre):]
    pre = f"{source}:"
    if key.startswith(pre):
        # 무접두형이거나, ds 접두형인데 ds_key 가 안 맞는 경우 — 'ds:키:' 도 마저 벗긴다.
        rest = key[len(pre):]
        if rest.startswith("ds:"):
            parts = rest.split(":", 2)
            if len(parts) == 3:
                return parts[2]
        return rest
    return key

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

# ── Agent PG scratch workspace (feature-0022) ─────────────────────────────
# assistant 가 PG 안에서 자기 전용 낙서장 DB(`agent_scratch`)를 자율적으로 다루는 기능의
# 인프라 자격. host/port/sslmode 는 KB Postgres 와 동일 클러스터를 재사용하되, database·
# role 은 분리된 전용값(agent_scratch / agent_scratch_rw)을 쓴다 — PG database-level 격리로
# 이 role 은 agent_kb/runtime/web/datasource 에 도달 불가(ADR-SCRATCH-0001).
#
# 활성화 게이트는 이중이다: (1) 인프라 — 아래 host+user 가 설정돼 있어야 함(bootstrap 완료),
# (2) 런타임 스위치 — runtime 설정 AGENT_SCRATCH_ENABLED(기본 0=OFF). 병합만으로 런타임
# 동작이 바뀌지 않도록 기본 OFF (bootstrap 후 운영자가 콘솔/설정에서 명시 활성화).
AGENT_SCRATCH_PG_DB = os.getenv("AGENT_SCRATCH_PG_DB", "agent_scratch").strip() or "agent_scratch"
AGENT_SCRATCH_PG_USER = os.getenv("AGENT_SCRATCH_PG_USER", "").strip()
AGENT_SCRATCH_PG_PASSWORD = os.getenv("AGENT_SCRATCH_PG_PASSWORD", "")
# host/port/sslmode 는 미설정 시 KB Postgres 값으로 fallback (동일 클러스터 전제).
AGENT_SCRATCH_PG_HOST = os.getenv("AGENT_SCRATCH_PG_HOST", "").strip() or AGENT_KB_PG_HOST
AGENT_SCRATCH_PG_PORT = int(os.getenv("AGENT_SCRATCH_PG_PORT", "").strip() or str(AGENT_KB_PG_PORT))
AGENT_SCRATCH_PG_SSLMODE = os.getenv("AGENT_SCRATCH_PG_SSLMODE", "").strip() or AGENT_KB_PG_SSLMODE
# 인프라 준비 여부(psycopg 는 db.py 가 별도 확인). 런타임 ON/OFF 는 runtime_settings 가 판정.
AGENT_SCRATCH_PG_CONFIGURED = bool(AGENT_SCRATCH_PG_HOST) and bool(AGENT_SCRATCH_PG_USER)

# M3 (TASK-0023) — Embedding worker (texts.embedding 컬럼 일괄 생성).
# Blocker B-4 결정 (M1 ADR-0021): TextHash 별 단일 embedding — fact_entries /
# rag_documents / rag_objects 가 texts join 시 자연 참조.
AGENT_KB_EMBEDDING_MODEL = (
    os.getenv("AGENT_KB_EMBEDDING_MODEL", "text-embedding-3-small").strip()
    or "text-embedding-3-small"
)
AGENT_KB_EMBEDDING_DIM = int(os.getenv("AGENT_KB_EMBEDDING_DIM", "1024") or "1024")  # titan-embed v2 / 로컬 1024 모델·alembic 0001 texts 정본 일치(구 1536 기본은 stale)
# ITEM-02: 샘플쿼리 few-shot 주입 토글(기본 ON). OFF 면 _build_knowledge_context 가 EXAMPLE
# QUERIES 섹션을 주입 안 함 — ITEM-01 harness A/B(샘플 off/on) 측정 + 안전 롤백 스위치.
AGENT_SAMPLE_QUERIES_ENABLED = os.getenv("AGENT_SAMPLE_QUERIES_ENABLED", "1").strip().lower() not in ("0", "false", "no", "")
# embed-congestion-fix(2026-07-30): 100→25. **요청 1건의 작업량**을 묶는 진짜 레버다.
#   bge-m3 비용은 텍스트 길이에 비례한다(무경합 실측: 16자 0.22s/건, 1022자 1.20s/건). 시그니처를
#   content-forward 로 보강한 뒤 대기 텍스트가 평균 210자·p95 464자가 되면서 100건 배치가 60~120s 로
#   불어나 옛 타임아웃 60s 를 넘겼고, 배치가 매번 완료 직전에 버려져 처리량이 0 이 됐다.
#   총 처리량은 건수에 선형이라(100건 119.83s ≈ 25건 30.02s×4) **배치를 줄여도 손해가 없고**,
#   요청당 지연만 1/4 로 줄어 타임아웃 여유가 생긴다.
AGENT_KB_EMBEDDING_BATCH_SIZE = int(os.getenv("AGENT_KB_EMBEDDING_BATCH_SIZE", "25") or "25")
# embed-congestion-fix(2026-07-30): 60→300. 클라이언트 타임아웃은 **큐 대기까지 포함**해 재는데,
#   로컬 ollama 직렬 처리에서 앞선 요청 뒤에 서면 실제 연산(100건 ~7s)보다 훨씬 오래 걸린다. 60s 는
#   그 대기를 "실패" 로 오판해 **아직 처리 중인 요청을 버리고 재시도**했고, 버려진 요청도 계속 연산을
#   점유해 부하가 눈덩이처럼 불었다. 타임아웃은 "이 요청이 영영 안 온다" 를 판정하는 값이어야지
#   "느리다" 를 판정하는 값이 아니다 — 실지연의 수 배로 잡는다.
AGENT_KB_EMBEDDING_TIMEOUT_SEC = _startup_int("AGENT_KB_EMBEDDING_TIMEOUT_SEC", int(os.getenv("AGENT_KB_EMBEDDING_TIMEOUT_SEC", "300") or "300"))
AGENT_KB_EMBEDDING_MAX_ATTEMPTS = int(os.getenv("AGENT_KB_EMBEDDING_MAX_ATTEMPTS", "3") or "3")
# CHG-20260625: 상호작용(준비 단계) 질의 임베딩 전용 fast-fail timeout. 위
# AGENT_KB_EMBEDDING_TIMEOUT_SEC(60s)/AGENT_TIMEOUT_SEC(300s) 는 오프라인 배치
# (kb_embedding_worker)·긴 agent run 용 — 사용자 turn 의 grounding 임베딩이 임베딩
# 백엔드 지연 시 그 길이만큼 init 을 블로킹하던 회귀(준비 50s)의 한 축이었다.
# grounding 임베딩은 실패해도 trigram 으로 graceful degrade 되므로 짧게 끊어 빠르게
# 폴백한다(전용 embed-ollama warm 실측 0.33s — 20s 면 cold·일시지연도 충분히 흡수).
# qembed-vis(2026-07-31): 20 → 12. **초안의 5s 는 §18.8 패널이 반증했다** — 근거였던
#   "warm p90 215ms, 23배 여유" 는 **16자 질의 한 종류만** 잰 값이었고, 실제 지연은 입력
#   길이에 비례한다(독립 재현: 6자 524ms / 2,340자 1,700ms / 3,428자 2,419ms / 5,712자
#   **4,172ms**; 패널은 6KB 에서 3.7~5.4s, 10KB 에서 5.7~8.5s 관측). 라이브 90일 사용자
#   메시지 최대가 5,996자(p99 1,382자)라 5s 는 **최대 입력에서 경계**였다(패널 실측 6KB
#   3회 중 1회 폴백). 초안 주석의 "5~20s 중간 체제는 미관측" 도 거짓이었다 — 유휴 백엔드에서
#   입력 길이만 바꿔도 바로 나온다.
#   12s = 관측된 최대-실입력 지연(4.2~5.4s)의 2.2~2.9배. 포화 시 낭비는 20s 대비 8s 절감.
#   포화 창에서는 어떤 값이든 완료되지 않으므로(요청이 큐에 갇힘) 이 값의 유일한 역할은
#   "실입력이 정상 백엔드에서 성공할 여유" 를 주면서 실패 확인을 앞당기는 것이다.
#   강등 발생은 feature-0035 `init_detail.query_embed_ok` 로 관측되므로 추측이 아니라
#   데이터로 재조정한다. **주의**: 값 변경 시 `shared/runtime_settings.py` 의 spec default 도
#   같이 고쳐야 한다(패널 MAJOR-2 — 콘솔이 구값을 표시하고 '초기화' 가 조용히 되돌린다).
AGENT_KB_QUERY_EMBED_TIMEOUT_SEC = _startup_int("AGENT_KB_QUERY_EMBED_TIMEOUT_SEC", int(os.getenv("AGENT_KB_QUERY_EMBED_TIMEOUT_SEC", "12") or "12"))
# ITEM-05 (하이브리드 검색 — 벡터+키워드 score fusion). gate ON 시 PG read path
# (_load_rag_documents_for_request_pg) 가 벡터(cosine)+trigram(pg_trgm) 검색을 둘 다 수행해
# (conversation_id, fact_key, content) union 병합 후 score = ALPHA·vec_sim + BETA·trigram_sim 으로
# 단일 랭킹한다. gate OFF(기본) 면 기존 2-tier(vector-OR-trigram fallback) 경로.
# 벡터 미임베딩/임베딩 실패(qvec None) 시엔 gate 무관하게 trigram-only 폴백 보존.
#
# 기본 OFF 사유 (ITEM-05 가치 입증 측정 결과 — 은폐 없이 기록):
#   적대적 retrieval corpus(24 docs/12 질문, rare-token·opaque-code·검증된 vector-miss 3 tier)로
#   fusion ON vs 2-tier A/B + 파라미터 sweep(NORM on/off × α/β 7조합) 실측 → 모든 지표 +0.0000
#   (MRR 1.0 both). 근본 원인: bge-m3 가 subword/char 인지라 질문의 rare token 이 정답 doc 의
#   cosine 도 함께 끌어올려(벡터·trigram 同방향 합의) fusion 이 바꿀 top rank 가 없음. 즉 현
#   임베더+합성 KB 조합에선 retrieval 정확도 lift 가 반증됨. fusion 은 비회귀(안전)하나 가치는
#   임베더-장애/미임베딩 폴백(이미 위 qvec None 폴백이 커버)에 국한 → 운영 거동 불변 위해 기본 OFF
#   dormant 보존. 실가치 재측정은 라이브 운영 질의 로그(임베더가 실제로 헛짚는 케이스) 필요.
AGENT_KB_HYBRID_ENABLED = os.getenv("AGENT_KB_HYBRID_ENABLED", "0").strip().lower() not in ("0", "false", "no", "")
# fusion 가중치 — vec 우선(0.6) + trigram 보강(0.4).
AGENT_KB_HYBRID_ALPHA = float(os.getenv("AGENT_KB_HYBRID_ALPHA", "0.6") or "0.6")
AGENT_KB_HYBRID_BETA = float(os.getenv("AGENT_KB_HYBRID_BETA", "0.4") or "0.4")
# fusion 스케일 정규화(기본 ON). 측정상 bge-m3 cosine(~0.4~0.8)과 한국어 pg_trgm
# similarity(~0.01~0.2)는 척도가 달라 raw 가중합이 vec 에 지배된다. 각 신호를 query-단위
# min-max([0,1])로 정규화 후 가중합하면 α/β 가 의도대로 두 신호를 섞는다. OFF=raw 가중합(롤백/비교).
AGENT_KB_HYBRID_NORMALIZE = os.getenv("AGENT_KB_HYBRID_NORMALIZE", "1").strip().lower() not in ("0", "false", "no", "")
# ITEM-05 REV MINOR-1: trigram sim 절대 하한 — 미만은 신호 0(정규화 부풀림 차단, 무관 distractor 상위 노출 방지).
AGENT_KB_HYBRID_TRIGRAM_FLOOR = float(os.getenv("AGENT_KB_HYBRID_TRIGRAM_FLOOR", "0.05") or "0.05")
# TASK-0307: insight-worker 의 **백그라운드 데몬 스레드**가 NULL embedding texts 를 주기적으로
# 소량 임베딩해 따라잡는다(kb_embedding_worker 스케줄러 부재로 신규 texts 가 정체→의미검색 recall
# 저하하던 것 해소). **본 tick(스캔) 루프를 절대 블로킹하지 않음** — titan-embed 가 batch 당 수십 초라
# tick(8s)에 동기 호출하면 워커 본업이 막히기 때문(REV-20260623T190000 F1). 별도 데몬 스레드로 분리.
#   AUTO=0 → 비활성(수동 백필만). BATCH_MAX_ROWS → pass 당 행수(≈ embedding 호출 1~2배치).
#   INTERVAL_SEC → pass 사이 sleep. 백로그 없으면 fetch 0건 cheap no-op.
AGENT_KB_EMBEDDING_AUTO = os.getenv("AGENT_KB_EMBEDDING_AUTO", "1").strip().lower() in ("1", "true", "yes")
# embed-throughput(2026-07-30): 100→1000. 라이브 실측으로 **워커 스로틀이 유일한 제한 지점**임을 확인 —
#   임베딩 지속 용량 42,657건/h(100건 배치 7.06s, 로컬 bge-m3 단일 코어)인데 100행/60초 설정이
#   6,000건/h 로 묶어 **86% 유휴**였다(실측 900건/10분). 시그니처 전수 재계산(48,226건)에서 백필이
#   임베딩을 앞지르자 이 캡이 곧바로 병목이 됐다. 1000행이면 pass 가 ~70s(10 서브배치)로 interval 을
#   넘겨 사실상 연속 처리 = 용량에 수렴한다. 백로그가 없으면 fetch 0건 cheap no-op 이므로 평시 부하 증가 0.
# embed-congestion-fix(2026-07-30): 1000→600. pass 당 행수는 **혼잡의 원인이 아니라 노출량**이다
#   (원인은 요청당 작업량 = BATCH_SIZE × 텍스트길이). 서브배치를 25건으로 줄여 요청당 지연이 짧아졌으므로
#   pass 를 너무 잘게 끊으면 INTERVAL(60s) 유휴만 늘어난다. 600행 ≈ 24 서브배치 ≈ 실측 평균길이 기준
#   250s/pass 로, 60s 유휴를 포함해도 백엔드 상한(~8,600/h)의 80% 를 낸다.
AGENT_KB_EMBEDDING_BATCH_MAX_ROWS = int(os.getenv("AGENT_KB_EMBEDDING_BATCH_MAX_ROWS", "600") or "600")
AGENT_KB_EMBEDDING_INTERVAL_SEC = int(os.getenv("AGENT_KB_EMBEDDING_INTERVAL_SEC", "60") or "60")
# feature-0016 Phase C (ADR-013 후속, semantic-embed): 메타데이터 객체(테이블) 시그니처 임베딩 → scope 별
# 의미 클러스터링. embedding 자체는 기존 embedding 데몬(위 AGENT_KB_EMBEDDING_*)이 texts 를 임베딩하므로
# 신규 embedding 노브 없음 — 아래는 시그니처 백필 + 클러스터링 전용 데몬 스레드(임베딩 데몬과 분리, tick 무블로킹).
#   AUTO=0 → Phase C 전면 비활성(kill switch, 프론트는 affix 폴백). RECOMPUTE_SEC → scope 재클러스터 cadence(6h).
#   SIM_THRESHOLD → 코사인 τ(단일연결 컷). FULLMATRIX_MAX_N → numpy N×N 코사인 행렬 메모리 가드: 이하만
#   클러스터링, 초과 scope 는 skip(프론트 affix 폴백 — OOM 방지). MAX_DEGREE → 노드당 이웃 상한(단일연결
#   chaining 억제 — verify MAJOR). KNN_K → 예약(향후 대형 scope pgvector kNN 폴백용, 현재 미사용).
#   τ=0.82 는 라이브 임베딩 코사인 분포로 재보정 대상(초기 안전값).
AGENT_METADATA_CLUSTER_AUTO = os.getenv("AGENT_METADATA_CLUSTER_AUTO", "1").strip().lower() in ("1", "true", "yes")
AGENT_METADATA_CLUSTER_INTERVAL_SEC = int(os.getenv("AGENT_METADATA_CLUSTER_INTERVAL_SEC", "900") or "900")
# §55 D: 200→500 상향 — 16k 백로그를 15분 pass 당 500 행이면 ~8h 에 소진(미처리-우선 정렬과 세트).
# sig-backfill-sweep(2026-07-30): 500→2000. 임베딩 용량 실측이 **51,000건/h**(100건 배치 7.06s,
#   bedrock-gateway titan-embed)이고 임베딩 큐는 대부분 비어 유휴였다 — 즉 전수 재계산의 제한 지점은
#   임베딩이 아니라 이 백필 캡이었다. 15분 주기 × 2000 = 8,000건/h 로 48,226 건 전수를 ~6h 에 sweep 한다
#   (종전 캡이면 ~24h + 정체 결함). PG 부하는 (ds,eff) 당 1회 역인덱스 재사용으로 유계.
AGENT_METADATA_CLUSTER_SIG_BATCH_MAX_ROWS = int(os.getenv("AGENT_METADATA_CLUSTER_SIG_BATCH_MAX_ROWS", "2000") or "2000")
AGENT_METADATA_CLUSTER_RECOMPUTE_SEC = int(os.getenv("AGENT_METADATA_CLUSTER_RECOMPUTE_SEC", "21600") or "21600")
AGENT_METADATA_CLUSTER_SIM_THRESHOLD = float(os.getenv("AGENT_METADATA_CLUSTER_SIM_THRESHOLD", "0.82") or "0.82")
AGENT_METADATA_CLUSTER_KNN_K = int(os.getenv("AGENT_METADATA_CLUSTER_KNN_K", "15") or "15")
# content-cluster-cohesion(2026-07-30): 2→3 상향. 2멤버 "클러스터" 는 밴드로서 신호가 없고(헤더 1줄이
#   멤버 2줄보다 큼), 세분화 체감의 주 원인이었다. 미달 잔여는 soft-attach(ATTACH_SIM)가 최근접 클러스터로
#   흡수하고, 그래도 남으면 NULL → 프론트 affix 폴백(종전과 동일 경로).
AGENT_METADATA_CLUSTER_MIN_SIZE = int(os.getenv("AGENT_METADATA_CLUSTER_MIN_SIZE", "3") or "3")
AGENT_METADATA_CLUSTER_MAX_DEGREE = int(os.getenv("AGENT_METADATA_CLUSTER_MAX_DEGREE", "8") or "8")
AGENT_METADATA_CLUSTER_FULLMATRIX_MAX_N = int(os.getenv("AGENT_METADATA_CLUSTER_FULLMATRIX_MAX_N", "2000") or "2000")
# content-cluster RC5 (TASK 20260713T1059): 클러스터 라벨을 LLM 한국어 컨텐츠 명으로(멤버셋-해시 kv 캐시,
#   fail-soft affix 폴백). 0 이면 affix 라벨만 — membership(cluster id)은 게이트와 무관하게 동작.
AGENT_METADATA_CLUSTER_LABEL_LLM = os.getenv("AGENT_METADATA_CLUSTER_LABEL_LLM", "1").strip().lower() in ("1", "true", "yes")
# content-cluster: 클러스터 멤버 상한 — 초과 컴포넌트는 τ 를 올려 재분할(divisive, _adaptive_components).
#   라이브 프로브에서 base τ 단일연결이 DB 전체를 한 blob(254멤버)으로 만들던 chaining 방어. ceiling 에서도
#   안 쪼개지면 진성 동질로 수용(하드 컷 아님 — 밴드 유용성 가이드).
AGENT_METADATA_CLUSTER_MAX_SIZE = int(os.getenv("AGENT_METADATA_CLUSTER_MAX_SIZE", "40") or "40")
# content-cluster p2 RC-A: soft-attach 임계 — 코어 클러스터 미배정 잔여를 centroid 코사인 ≥ 이 값이면
#   최근접 클러스터에 편입(라벨 상속). base τ(0.82)보다 완화하되 무리한 편입은 금지. 0 이면 사실상 전부 편입,
#   1 이면 비활성에 수렴.
AGENT_METADATA_CLUSTER_ATTACH_SIM = float(os.getenv("AGENT_METADATA_CLUSTER_ATTACH_SIM", "0.78") or "0.78")
# ── content-cluster-cohesion(2026-07-30, 사용자 리포트 "컨텐츠 클러스터가 너무 세분화") ──────────────
#   MERGE_SIM: 응집 병합 임계. MAX_SIZE 초과 컴포넌트를 τ 상승으로 재분할(_adaptive_components)한 뒤,
#     centroid 코사인 ≥ 이 값인 조각 쌍을 다시 **응집 병합**한다. 재분할은 "blob 방지" 라는 한 방향
#     압력만 갖고 되돌릴 힘이 없어(τ→0.98 까지 단조 상승) 의미상 한 컨텐츠가 여러 조각으로 남았다
#     — 라이브 증상: 같은 라벨의 형제 밴드("길드 게시판" ×2, "몬스터 스폰" ×2). 반대 방향 압력을
#     추가해 균형점을 만든다. 근거: BERTopic 의 유사도-임계 반복 병합(cosine ≥ 0.9)·HDBSCAN
#     cluster_selection_epsilon(마이크로 클러스터 병합) 과 동일 계열.
#   MERGE_MAX_SIZE: 병합 결과 멤버 상한. MAX_SIZE(재분할 목표)보다 크게 둬 재분할↔병합 왕복(flap)을
#     막는다 — 병합이 MAX_SIZE 를 넘어야 다음 pass 의 재분할이 같은 조각을 다시 만들지 않는다.
#   GRID_ORDER: 클러스터 id 배정 순서를 centroid **MDS 2-D serpentine**(행-균형 boustrophedon)으로.
#     0 이면 기존 1-D greedy 최근접 체인(_seriate_by_centroid). 프론트 밴드가 shelf-pack 으로 행 랩되므로
#     1-D 체인은 세로 인접이 무의미했다 — 2-D 투영 후 행 단위로 훑으면 가로·세로 인접 모두 의미를 갖는다.
AGENT_METADATA_CLUSTER_MERGE_SIM = float(os.getenv("AGENT_METADATA_CLUSTER_MERGE_SIM", "0.90") or "0.90")
# cluster-signal-repair(2026-07-30): MERGE_SIM 은 **단독으로 쓰면 위험하다** — 스키마마다 시그니처
#   boilerplate 가 만드는 유사도 바닥값이 달라 절대 임계는 이식 불가하다(라이브 실측: 무관한 테이블
#   클러스터 쌍이 0.915 로 이미 0.90 초과). 실제 병합 하한은
#     floor = max(MERGE_SIM, median(스키마 내 클러스터간 유사도) + MERGE_MARGIN)
#   으로, "분포에서 뚜렷하게 튀는 쌍" 만 통과시킨다. 전 쌍이 고르게 높은(=신호 없는) 분포에서는
#   median 이 함께 올라가 병합이 자연 억제된다. 0 이면 종전(절대 임계 단독) 동작.
AGENT_METADATA_CLUSTER_MERGE_MARGIN = float(os.getenv("AGENT_METADATA_CLUSTER_MERGE_MARGIN", "0.04") or "0.04")
# cluster-signal-repair(2026-07-30): **양식 교차 브릿지** 임계 — 루틴 우세 클러스터의 참조 테이블 중
#   한 테이블 클러스터가 이 비율 이상을 차지하면(그리고 서로 다른 테이블 2개 이상 매칭) 두 클러스터를
#   병합한다. 임베딩 유사도가 양식에 지배되어(실측: 같은양식-다른컨텐츠 0.80 > 같은컨텐츠-다른양식 0.75)
#   임베딩 단독으로는 만들 수 없는 병합을 **구조**로 만든다. 0 이면 브릿지 비활성(종전 동작).
AGENT_METADATA_CLUSTER_BRIDGE_MIN_FRAC = float(os.getenv("AGENT_METADATA_CLUSTER_BRIDGE_MIN_FRAC", "0.5") or "0.5")
AGENT_METADATA_CLUSTER_MERGE_MAX_SIZE = int(os.getenv("AGENT_METADATA_CLUSTER_MERGE_MAX_SIZE", "80") or "80")
AGENT_METADATA_CLUSTER_GRID_ORDER = os.getenv("AGENT_METADATA_CLUSTER_GRID_ORDER", "1").strip().lower() in ("1", "true", "yes")
# feature-0016 Phase B (ADR-019, crossds-rel): 크로스-데이터소스 관계 추론(Phase C 시그니처 임베딩 구동).
#   AUTO=0(기본 OFF) → 스키마·UI·scope 완화만 배포되고 추론 inert. Phase C 임베딩 populate 후 1 로 flip.
#   MIN_SIM 높게(0.90) — 프로브 검증 불가라 보수적. 프로브 skip·manual/대화JOIN 승격은 relationships.py.
AGENT_XDS_RELATIONSHIP_INFER_AUTO = os.getenv("AGENT_XDS_RELATIONSHIP_INFER_AUTO", "0").strip().lower() in ("1", "true", "yes")
AGENT_XDS_RELATIONSHIP_INFER_INTERVAL_SEC = int(os.getenv("AGENT_XDS_RELATIONSHIP_INFER_INTERVAL_SEC", "21600") or "21600")
AGENT_XDS_RELATIONSHIP_MIN_SIM = float(os.getenv("AGENT_XDS_RELATIONSHIP_MIN_SIM", "0.90") or "0.90")
AGENT_XDS_RELATIONSHIP_BATCH_MAX = int(os.getenv("AGENT_XDS_RELATIONSHIP_BATCH_MAX", "200") or "200")
AGENT_XDS_RELATIONSHIP_MAX_CANDIDATES_PER_SCOPE = int(os.getenv("AGENT_XDS_RELATIONSHIP_MAX_CANDIDATES_PER_SCOPE", "50") or "50")

# feature-0016 §59(ADR-025): 미분류 스키마 → 제품 분류 AI 제안(승인 대기 적재 — allowlist 비접촉).
#   AUTO=0(기본 OFF, XDS 선례) → 모듈·승인 UI 만 배포되고 데몬 inert. 운영 확인 후 1 로 flip.
#   MIN_CONF 미만 제안은 폐기(보수적 — 접근면 인접 파이프라인). BATCH_MAX = pass 당 스키마 상한.
AGENT_PRODUCT_CLASSIFY_AUTO = os.getenv("AGENT_PRODUCT_CLASSIFY_AUTO", "0").strip().lower() in ("1", "true", "yes")
AGENT_PRODUCT_CLASSIFY_INTERVAL_SEC = int(os.getenv("AGENT_PRODUCT_CLASSIFY_INTERVAL_SEC", "21600") or "21600")
AGENT_PRODUCT_CLASSIFY_MIN_CONF = float(os.getenv("AGENT_PRODUCT_CLASSIFY_MIN_CONF", "0.6") or "0.6")
AGENT_PRODUCT_CLASSIFY_BATCH_MAX = int(os.getenv("AGENT_PRODUCT_CLASSIFY_BATCH_MAX", "20") or "20")
AGENT_XDS_RELATIONSHIP_KNN_K = int(os.getenv("AGENT_XDS_RELATIONSHIP_KNN_K", "10") or "10")
# feature-0016 §55 (REQ-20260706 ②): **같은 datasource 안의 다른 스키마(DB) 간** 관계 추론.
#   크로스-DS 와 같은 임베딩 유사도 경로를 쓰되, src_ds==tgt_ds 라 기존 프로브(EXISTS)·강화/파단
#   파이프라인에 자연 편입된다(검증 가능) → 기본 ON. MIN_SIM 은 XDS 보다 완화(프로브가 검증하므로).
AGENT_XSCHEMA_RELATIONSHIP_INFER_AUTO = os.getenv("AGENT_XSCHEMA_RELATIONSHIP_INFER_AUTO", "1").strip().lower() in ("1", "true", "yes")
AGENT_XSCHEMA_RELATIONSHIP_MIN_SIM = float(os.getenv("AGENT_XSCHEMA_RELATIONSHIP_MIN_SIM", "0.86") or "0.86")
# node_analysis: 의도적 교차DB REFERENCES 로 도달한 이웃의 cross-scope 감쇠 대체값(1.0=무감쇠). 우연 교차는 0.25 유지.
AGENT_NODE_ANALYSIS_XDS_REFERENCES_FACTOR = float(os.getenv("AGENT_NODE_ANALYSIS_XDS_REFERENCES_FACTOR", "1.0") or "1.0")
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

# TASK-0237: env 명명 정리 — 새 이름 LLM_MODEL 우선, 구이름 OPENAI_MODEL 은 deprecated
# fallback(운영 .env 의 OPENAI_MODEL=auto 무중단 호환). 심볼명 OPENAI_MODEL 은 사용처 보존
# 위해 유지(env 소스만 신규 우선). 다음 cycle 에 OPENAI_MODEL env fallback 제거 검토.
OPENAI_MODEL = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "claude-sonnet-4"

# ── 로컬 LLM Gateway (구버전 호환 — Local LLM gateway 사용 시) ──
LOCAL_LLM_API_BASE = os.getenv("LOCAL_LLM_API_BASE", "").strip() or None
LOCAL_LLM_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "").strip() or None
# TASK-0237: OPENAI_API_BASE 제거 — CHG-20260522-0006(OpenAI direct fallback 제거) 이후
# 어디에서도 read 되지 않는 dead env. Bedrock 은 BEDROCK_GATEWAY_URL, 로컬은 LOCAL_LLM_API_BASE 사용.

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
    3. 미설정            — (None, None). _get_llm_client() 가 None 반환.

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
# ── insight 백그라운드 배치 시간 기반 강등 — **기본 비활성**(2026-07-30 llm-edge-free-routing) ──
# 2026-07-04(llm-routing-interactive-split)에는 insight 워커(schema/table/account)를 **평일 근무시간엔
# claude, 야간·주말엔 gemma(edge)** 로 강등해 비용을 절감했다. 2026-07-30 사용자 결정으로 **로컬 LLM
# 사용을 전면 중단**하면서 이 강등도 폐지한다 — 기본값을 `edge` 에서 **빈 값**으로 바꿔 강등 비활성
# (항상 AGENT_INSIGHT_MODEL = claude)이 기본이 된다. litellm fallback 체인에서도 edge-fallback 참조를
# 모두 걷어냈다(unit/feature-0007-.../litellm_config.yaml) — 자동 gemma 강등 경로가 앱·게이트웨이 양쪽
# 모두에서 사라진 상태다.
# 강등 로직 자체는 보존한다(운영자가 값을 채우면 재활성): OFFHOURS_MODEL 이 빈 값이거나
# AGENT_INSIGHT_MODEL 과 동일하면 비활성. 근무시간 경계는 [START, END) 시(로컬=KST 가정, TZ_OFFSET 로
# UTC 보정), 주말(토·일)은 하루종일 off-hours. 값을 채우는 것은 사용자 결정 override 임에 유의.
AGENT_INSIGHT_OFFHOURS_MODEL = (
    os.getenv("AGENT_INSIGHT_OFFHOURS_MODEL", "").strip()
)
AGENT_INSIGHT_BUSINESS_START_HOUR = int(
    os.getenv("AGENT_INSIGHT_BUSINESS_START_HOUR", "10").strip() or "10"
)
AGENT_INSIGHT_BUSINESS_END_HOUR = int(
    os.getenv("AGENT_INSIGHT_BUSINESS_END_HOUR", "19").strip() or "19"
)
AGENT_INSIGHT_BUSINESS_TZ_OFFSET_HOURS = int(
    os.getenv("AGENT_INSIGHT_BUSINESS_TZ_OFFSET_HOURS", "9").strip() or "9"
)
# feature-0016 node-analysis-haiku + llm-routing-interactive-split(2026-07-04): 관리콘솔 그래프뷰
# "AI 능동 분석"(각 관계 분석, llm_node_analysis)의 전용 모델. schema/table/account insight 와
# 공유하던 AGENT_INSIGHT_MODEL 에서 분리 + **사람 능동 호출**이므로 항상 claude 로 유지한다.
# **기본값 = claude-haiku-4-meta** (meta-llm-edge-free, 2026-07-30 사용자 결정 재확인).
# 2026-07-04 에는 `claude-haiku-4-interactive` 로 두어 insight 배치의 off-hours gemma 강등과 분리했으나,
# `-interactive` 의 litellm fallback 체인은 끝이 **`edge-fallback`(로컬 gemma)** 이었다 — 두 claude 계정이
# 모두 401/429 면 능동 분석·클러스터 라벨이 조용히 gemma 로 강등된다. 사용자 결정("로컬LLM은 특수목적
# =야간·업무 외 탐색 전용, 실제 개발용 작업은 계정 연결 claude-code")과 어긋나고, 이 산출물은 **영구히
# 남는다**(라벨은 kv 캐시로 재사용, 분석문은 시그니처에 섞여 클러스터 구조까지 오염). 그래서 대화 답변의
# `*-chat` 규약과 동일하게 **edge 를 배제한 `-meta` alias**(claude-corp → root 2계정)로 라우팅한다.
# 두 계정 모두 실패 시 gemma 강등 대신 실패 → 호출측 fail-soft(라벨=affix 폴백 / 분석=미분석 유지·재시도).
# ⚠ (superseded 2026-07-30 저녁, llm-edge-free-routing) 위 "배경 insight 배치의 야간·주말 gemma 강등은
# 그대로 유지" 예외는 같은 날 사용자 결정으로 폐지됐다 — 아래 AGENT_INSIGHT_OFFHOURS_MODEL 기본값 참조.
AGENT_NODE_ANALYSIS_MODEL = (
    os.getenv("AGENT_NODE_ANALYSIS_MODEL", "").strip() or "claude-haiku-4-meta"
)
# ── 용어사전 대화 자율등록(0021) ──────────────────────────────────────────────
# 대화 답변 직후 도메인 용어 후보를 LLM 으로 추론해 용어사전(kb_glossary)에 자율 등록한다.
# 사용자 결정(2026-06-29): 하이브리드 자동승급 — confidence ≥ THRESHOLD 면 즉시 등록
# (source='auto', 되돌리기 가능), 미만이면 검토 큐(glossary_feedback.status='pending').
# 기본 역할 귀속 = 공용('*'). poisoning 방어상 자동 등록분도 glossary_feedback 에 감사 추적.
AGENT_GLOSSARY_AUTOPROPOSE = (
    os.getenv("AGENT_GLOSSARY_AUTOPROPOSE", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_GLOSSARY_SUGGEST_MODEL = (
    os.getenv("AGENT_GLOSSARY_SUGGEST_MODEL", AGENT_SUMMARY_MODEL).strip()
    or AGENT_SUMMARY_MODEL
)
try:
    AGENT_GLOSSARY_AUTOPROMOTE_THRESHOLD = float(
        os.getenv("AGENT_GLOSSARY_AUTOPROMOTE_THRESHOLD", "0.85").strip() or "0.85"
    )
except ValueError:
    AGENT_GLOSSARY_AUTOPROMOTE_THRESHOLD = 0.85
# 한 턴에서 큐/등록으로 받아들일 최대 용어 후보 수 (토큰/노이즈 cap).
try:
    AGENT_GLOSSARY_SUGGEST_MAX = int(
        os.getenv("AGENT_GLOSSARY_SUGGEST_MAX", "5").strip() or "5"
    )
except ValueError:
    AGENT_GLOSSARY_SUGGEST_MAX = 5

# ── ENUM 코드사전 대화 자율수집(0039) — 용어사전(0021) ENUM 대칭 ────────────────────
# 대화 답변 직후 (table.column) 코드↔라벨 후보를 LLM 으로 추론해 ENUM 코드사전(enum_dictionary)에
# 자율 수집한다. 하이브리드 자동승급 — confidence ≥ THRESHOLD 면 즉시 등록(source='auto', 되돌리기
# 가능), 미만이면 검토 큐(enum_feedback.status='pending'). ENUM 은 (schema/table/column/code) 구조
# 추론이 용어보다 오탐 위험이 커 THRESHOLD 를 용어(0.85)보다 보수적인 0.9 로 둔다(대부분 검토 큐 경유).
AGENT_ENUM_AUTOPROPOSE = (
    os.getenv("AGENT_ENUM_AUTOPROPOSE", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_ENUM_SUGGEST_MODEL = (
    os.getenv("AGENT_ENUM_SUGGEST_MODEL", AGENT_SUMMARY_MODEL).strip()
    or AGENT_SUMMARY_MODEL
)
try:
    AGENT_ENUM_AUTOPROMOTE_THRESHOLD = float(
        os.getenv("AGENT_ENUM_AUTOPROMOTE_THRESHOLD", "0.9").strip() or "0.9"
    )
except ValueError:
    AGENT_ENUM_AUTOPROMOTE_THRESHOLD = 0.9
# 한 턴에서 큐/등록으로 받아들일 최대 ENUM 후보 수 (토큰/노이즈 cap).
try:
    AGENT_ENUM_SUGGEST_MAX = int(
        os.getenv("AGENT_ENUM_SUGGEST_MAX", "5").strip() or "5"
    )
except ValueError:
    AGENT_ENUM_SUGGEST_MAX = 5
# ENUM 자동등록 schema-grounding 게이트. LLM 이 대화 답변에서 추론한 (schema,table) 이 활성
# datasource 의 실제 스키마 카탈로그(table_insight fact — agent 가 LLM 에 주입하는 grounding 정본)
# 에 명백히 부재하면 등록·큐잉을 skip 한다(환각 DB/테이블 차단, 예: auth scope 에 없는 dbLog.Currency).
# 카탈로그 미가용/빈 scope 는 fail-open(기존 동작 보존 — false-reject 방지). 기본 on.
AGENT_ENUM_SCHEMA_GROUNDING = (
    os.getenv("AGENT_ENUM_SCHEMA_GROUNDING", "1").strip().lower() in ("1", "true", "yes")
)
# ENUM 자동등록 자가수리(self-heal). insight-worker tick 이 스키마를 스캔한 직후, 그 scope 의
# enum 중 `schema_name`(=DB)이 **실재하지 않는** 항목(예: auth scope 에 없는 dbLog.*)을 소급 회수한다.
# 검증 기준 = 워커가 방금 로드한 **완전한** 실제 스키마 목록(load_known_schemas, budget 무관) → legit
# enum false-deletion 없음. schema-존재만 검증(빈 schema_name·table-레벨은 미터치 — 수동 스크립트 담당),
# MySQL-family 전용(MSSQL 제외), 실제 스캔 tick(~6h)에만, 스키마 부재 2회 연속 관측 시에만 삭제(일시
# 축소 흡수). 예방 게이트(AGENT_ENUM_SCHEMA_GROUNDING)와 **결합**(둘 다 on 일 때만 동작). 기본 on.
AGENT_ENUM_SELF_HEAL = (
    os.getenv("AGENT_ENUM_SELF_HEAL", "1").strip().lower() in ("1", "true", "yes")
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
AGENT_TIMEOUT_SEC = _startup_int("AGENT_TIMEOUT_SEC", int(os.getenv("AGENT_TIMEOUT_SEC", "60")))

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
# P6 (멀티 datasource Stage 2, Codex-6): confirm_heavy 는 LLM tool 인자라 모델이 무거운 쿼리
# 게이트를 자기우회한다. false 로 두면 LLM 의 confirm_heavy 를 무시(비-LLM 승인만 인정) — 정책상
# 모델 자기우회를 차단하려는 운영자용. 기본 true=현행(모델 판단 신뢰). 사용자/UI 승인 경로는 P7 이월.
AGENT_QUERY_CONFIRM_HEAVY_TRUST_LLM = (
    os.getenv("AGENT_QUERY_CONFIRM_HEAVY_TRUST_LLM", "true").strip().lower()
    not in ("false", "0", "no")
)
# TASK-0237: 새 이름 AGENT_LLM_MAX_RETRIES 우선, 구이름 fallback(운영 .env 무중단).
AGENT_OPENAI_MAX_RETRIES = int(
    os.getenv("AGENT_LLM_MAX_RETRIES") or os.getenv("AGENT_OPENAI_MAX_RETRIES") or "0"
)
AGENT_MEMORY_MAX_TURNS = int(os.getenv("AGENT_MEMORY_MAX_TURNS", "10"))
AGENT_CSV_PREVIEW_ROWS = int(os.getenv("AGENT_CSV_PREVIEW_ROWS", "20"))
AGENT_CSV_ANALYZE_MAX_ROWS = int(os.getenv("AGENT_CSV_ANALYZE_MAX_ROWS", "200000"))
AGENT_CSV_ANALYZE_MAX_BYTES = int(os.getenv("AGENT_CSV_ANALYZE_MAX_BYTES", str(5 * 1024 * 1024)))
AGENT_MODE = os.getenv("AGENT_MODE", "sql").lower()
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "128"))
# FR-procedure-analysis-result-truncated: 에이전트 도구 루프가 LLM 에 되먹이는 도구 결과의
# 문자 상한(대형 backstop). 원래 4000 하드코딩은 저장 프로시저 정의(describe_routine 은 정의를
# 전문 반환) 처럼 길고 단일-권위 텍스트를 잘라 프로시저 분석을 한 번에 못 하게 만들었다.
# 사용자 결정(2026-07-24): 도구별 분기 없이 전 도구에 큰 유한 캡을 적용 — 실무 프로시저는
# 사실상 무제한(전문 도달)이되 병리적 대량 결과(넓은 표 대량 행 등)는 컨텍스트 폭주를 막는
# backstop 이 유지된다. 캡 초과 시에만 절단 note 를 붙여 FR-partial-evidence epistemic 계약
# (미열람분 전수 단정 금지)을 보존한다. 0/음수는 무제한으로 해석.
AGENT_TOOL_RESULT_MAX_CHARS = int(os.getenv("AGENT_TOOL_RESULT_MAX_CHARS", "100000"))
# FR-false-truncation-belief(사용자 결정 2026-07-27): 위 backstop 캡은 유지하되, 캡보다 큰 저장
# 루틴 정의도 **여러 번 호출로 전량 도달**할 수 있게 describe_routine 응답을 문자 offset 창으로
# 나눈다. 한 응답에 담을 최대 문자수.
#   0(기본) = **auto** — 창 = AGENT_TOOL_RESULT_MAX_CHARS - 여유. 즉 위 backstop 캡이 어차피 자를
#     지점부터만 쪼갠다(캡 이하 정의는 종전처럼 한 응답에 전문 = 조각화 회귀 0). 캡이 무제한이면
#     자를 이유가 없어 윈도잉 비활성.
#   양수 = 명시 창 크기(하한 4000, 상한 캡-여유).
#   음수 = 윈도잉 비활성(kill-switch — 전역 캡만 적용).
# 실제 산정은 tools._routine_chunk_limit() 이 담당하며, 창은 항상 캡보다 작아야 한다(아니면 캡이
# 조각 꼬리의 "다음 offset" 안내를 잘라 전량 도달 경로 자체가 사라진다).
AGENT_ROUTINE_DEF_CHUNK_CHARS = int(os.getenv("AGENT_ROUTINE_DEF_CHUNK_CHARS", "0"))
AGENT_COLUMN_SCAN_LIMIT = int(os.getenv("AGENT_COLUMN_SCAN_LIMIT", "2000"))
AGENT_GLOBAL_KB_MIN_WEIGHT = int(os.getenv("AGENT_GLOBAL_KB_MIN_WEIGHT", "4"))
AGENT_GLOBAL_KB_MAX_ENTRIES = int(os.getenv("AGENT_GLOBAL_KB_MAX_ENTRIES", "80"))
AGENT_GLOBAL_KB_LOCK_TIMEOUT_SEC = _startup_int("AGENT_GLOBAL_KB_LOCK_TIMEOUT_SEC", int(os.getenv("AGENT_GLOBAL_KB_LOCK_TIMEOUT_SEC", "3")))
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

# TASK-20260617T082131 — 계정 스코프 cross-conversation 인사이트 회상 (Phase 1, shadow).
# 정본: unit/feature-0002-agent-core/docs/DESIGN-account-insight-recall.md
# RECALL = 회상 경로 활성(shadow 포함), INJECT = 실제 LLM 주입(OFF = shadow log-only).
# 둘 다 기본 OFF — G1(fork 표식)·G3(PII 마스커) 완료 전 INJECT 금지.
AGENT_ACCOUNT_INSIGHT_RECALL = os.getenv("AGENT_ACCOUNT_INSIGHT_RECALL", "0").strip().lower() in ("1", "true", "yes")
AGENT_ACCOUNT_INSIGHT_INJECT = os.getenv("AGENT_ACCOUNT_INSIGHT_INJECT", "0").strip().lower() in ("1", "true", "yes")
AGENT_ACCOUNT_INSIGHT_MAX_CONVS = int(os.getenv("AGENT_ACCOUNT_INSIGHT_MAX_CONVS", "20"))
AGENT_ACCOUNT_INSIGHT_TOP_K = int(os.getenv("AGENT_ACCOUNT_INSIGHT_TOP_K", "3"))
# 회상 유사도 임계 — 벡터 cosine(1-distance) 기준. account 회상은 벡터-only fail-closed
# (trigram fallback 미사용 — TASK-20260617T082131: ft_score 척도 혼동 버그 회피).
AGENT_ACCOUNT_INSIGHT_MIN_SIM = float(os.getenv("AGENT_ACCOUNT_INSIGHT_MIN_SIM", "0.55"))
# account_insight 추출 pass (insight worker, B′). 대화 summary→PII-free 메타 인사이트 추출.
# 기본 OFF — 켜면 insight worker 가 owner 있는 비-fork 대화의 summary 에서 인사이트를 생성.
AGENT_ACCOUNT_INSIGHT_EXTRACT = os.getenv("AGENT_ACCOUNT_INSIGHT_EXTRACT", "0").strip().lower() in ("1", "true", "yes")
AGENT_ACCOUNT_INSIGHT_EXTRACT_MAX_CONVS = int(os.getenv("AGENT_ACCOUNT_INSIGHT_EXTRACT_MAX_CONVS", "25"))
AGENT_ACCOUNT_INSIGHT_MIN_SUMMARY_LEN = int(os.getenv("AGENT_ACCOUNT_INSIGHT_MIN_SUMMARY_LEN", "40"))
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
# feature-0002 insight-table-grouping (2026-07-03): 동일 구조(컬럼 지문) + 동일 이름-family
# (날짜/번호 suffix 만 다른) 테이블을 한 그룹으로 묶어 대표 1개만 LLM 분석하고, 나머지 형제는
# LLM 없이 인사이트를 전파(fan-out)한다. 날짜 샤드(daily_league_ranking_1_20250727,
# _20250726 …) 수백 개를 개별 LLM 분석하던 낭비 제거(사용자 결정 2026-07-03). per-table
# table_insight fact 는 그대로 유지 → grounding(NL→SQL) 무회귀. 그룹 대표의 분석 dict 는
# table_group_insight:<fp>:<stem> KV 에 캐시되어 다음 cycle 의 신규 샤드가 LLM 없이 상속한다.
AGENT_INSIGHT_TABLE_GROUPING_ENABLED = (
    os.getenv("AGENT_INSIGHT_TABLE_GROUPING_ENABLED", "1").strip().lower() in ("1", "true", "yes")
)
# 그룹으로 인정할 최소 멤버 수(이 미만은 기존 per-table 동작 그대로 — 무회귀 보장).
AGENT_INSIGHT_TABLE_GROUP_MIN_MEMBERS = int(os.getenv("AGENT_INSIGHT_TABLE_GROUP_MIN_MEMBERS", "2"))
# 한 cycle 에서 LLM 없이 fan-out(전파)할 테이블 상한(budget_sec 와 함께 이중 상한 — spike 방지).
AGENT_INSIGHT_TABLE_GROUP_FANOUT_MAX = int(os.getenv("AGENT_INSIGHT_TABLE_GROUP_FANOUT_MAX", "200"))
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
# ITEM-07: execute_sql 실패 시 명시 bounded 자가수정 넛지(기존 LLM 자율 경로 보강, similar-retry
# 가드 공존). 기본 ON. cap=run 당 최대 넛지 수(폭주 차단; max_steps·circuit-breaker 와 중첩).
AGENT_SELF_REFLECTION_ENABLED = os.getenv("AGENT_SELF_REFLECTION_ENABLED", "1").strip().lower() not in ("0", "false", "no", "")
AGENT_SELF_REFLECTION_MAX = int(os.getenv("AGENT_SELF_REFLECTION_MAX", "2") or "2")

# feature-0013 relationship-diagrams: 테이블 관계(FK·join) 데이터 확보·학습 토글. 둘 다 기본 ON.
#  - INTROSPECT: insight worker 가 스키마 구조 변경 시 information_schema FK 를 introspect 해 적재.
#  - LEARNING : 대화 중 성공한 execute_sql 의 JOIN 에서 관계를 학습(source='conversation').
AGENT_RELATIONSHIP_INTROSPECT_ENABLED = os.getenv("AGENT_RELATIONSHIP_INTROSPECT_ENABLED", "1").strip().lower() not in ("0", "false", "no", "")
AGENT_RELATIONSHIP_LEARNING_ENABLED = os.getenv("AGENT_RELATIONSHIP_LEARNING_ENABLED", "1").strip().lower() not in ("0", "false", "no", "")
# feature-0016 implicit-edges: FK 미선언 관계의 휴리스틱 추론 + 자기교정(강화/감쇠) 토글·캡. 기본 ON.
#  - INFERENCE: insight worker 가 스키마 구조 변경 시 명명 규칙으로 암묵 관계를 추론해 적재(source='inferred').
#  - PROBE    : candidate edge 를 실데이터 겹침(EXISTS)으로 검증해 강화/감쇠(능동 검증). 운영 DB read-only.
#  - 강화(사용 성공)는 대화 JOIN 학습(LEARNING)과 함께 상시 작동. 음성은 프로브가 실데이터로 판정.
AGENT_RELATIONSHIP_INFERENCE_ENABLED = os.getenv("AGENT_RELATIONSHIP_INFERENCE_ENABLED", "1").strip().lower() not in ("0", "false", "no", "")
AGENT_RELATIONSHIP_PROBE_ENABLED = os.getenv("AGENT_RELATIONSHIP_PROBE_ENABLED", "1").strip().lower() not in ("0", "false", "no", "")
AGENT_RELATIONSHIP_INFER_CAP = int(os.getenv("AGENT_RELATIONSHIP_INFER_CAP", "400") or "400")
# rel-selfheal: 관계 유지보수(FK introspect·암묵 추론·프로브) 주기 재발화 간격(초).
# 기존 트리거(스키마 신규/구조변경)만으로는 이미 스캔 완료된 스키마에서 영원히 미발화 —
# 라이브 inferred 0건·프로브 0회의 설계 갭 보완. 0 이하 = cadence off(기존 트리거만).
# 기본 21600(6h) — 프로브 cap/timeout 이 사이클당 운영 DB 부하를 상한.
AGENT_RELATIONSHIP_REINFER_SEC = int(os.getenv("AGENT_RELATIONSHIP_REINFER_SEC", "21600") or "21600")
AGENT_RELATIONSHIP_PROBE_CAP = int(os.getenv("AGENT_RELATIONSHIP_PROBE_CAP", "40") or "40")
AGENT_RELATIONSHIP_PROBE_SAMPLE = int(os.getenv("AGENT_RELATIONSHIP_PROBE_SAMPLE", "50") or "50")
# 프로브 statement 시간 상한(ms). 운영 DB 상 unindexed 키 컬럼 대상 correlated EXISTS 폭주 차단
# (보안 패널 MINOR — _fk_raw_execute 가 _apply_query_cap 을 우회). MySQL=MAX_EXECUTION_TIME 힌트,
# MSSQL=SET LOCK_TIMEOUT(락 대기 상한). 0 이면 미적용.
AGENT_RELATIONSHIP_PROBE_TIMEOUT_MS = _startup_int("AGENT_RELATIONSHIP_PROBE_TIMEOUT_MS", int(os.getenv("AGENT_RELATIONSHIP_PROBE_TIMEOUT_MS", "5000") or "5000"))
# feature-0016 graph-funcproc(ADR-016): 함수·프로시저(routine) introspection 토글·캡. 기본 ON.
#  - insight worker 가 관계 유지보수 게이트(rel_maintenance_due)와 같은 cadence 로
#    INFORMATION_SCHEMA.ROUTINES/PARAMETERS 를 조회해 routine_objects(SSOT)에 upsert →
#    metadata_graph.sync_graph 가 AGE Routine 노드 + ROUTINE_USES(참조 테이블) 로 투영.
AGENT_ROUTINE_INTROSPECT_ENABLED = os.getenv("AGENT_ROUTINE_INTROSPECT_ENABLED", "1").strip().lower() not in ("0", "false", "no", "")
AGENT_ROUTINE_INTROSPECT_CAP = int(os.getenv("AGENT_ROUTINE_INTROSPECT_CAP", "20000") or "20000")
# feature-0016 metadata-graph: 관계형 SSOT → Apache AGE `metadata_kb` 그래프 투영 토글.
#  - 기본 OFF — AGE 확장 미설치(cutover 전) 상태에서 sync/projection 이 no-op 되도록.
#  - cutover(커스텀 AGE 이미지 + shared_preload_libraries='age') 이후 .env/compose 에서 "1" 로 활성.
#  - 투영 API/모듈은 플래그와 무관하게 graceful no-op 이나, insight/cron 트리거는 이 플래그를 본다.
AGENT_METADATA_GRAPH_SYNC_ENABLED = os.getenv("AGENT_METADATA_GRAPH_SYNC_ENABLED", "0").strip().lower() not in ("0", "false", "no", "")
# feature-0016 graphux5: 그래프 노드 AI 능동 분석(재귀·백그라운드) 토글 + 경계.
#  - 관리콘솔 그래프뷰 상세 패널의 "AI 능동 분석" 버튼이 큐에 넣은 잡을 insight-worker 가 소비.
#  - 선택 노드를 시작으로 관련 노드를 k-hop 재귀 탐색하며 노드별 LLM 분석문을 생성·저장.
#  - **외부 LLM 비용 직결** → 재귀는 depth/노드 예산 상한 + visited dedupe 로 경계(사용자 결정 2026-07-01).
#  - 기본 ON(웹에서 명시 트리거해야만 잡 생성 — 상시 비용 아님). 완전 차단은 "0".
AGENT_NODE_ANALYSIS_ENABLED = os.getenv("AGENT_NODE_ANALYSIS_ENABLED", "1").strip().lower() not in ("0", "false", "no", "")
# 재귀 기본 깊이 예산(요청이 미지정 시). 1..5 로 클램프. 이웃 hop 수 = 루트에서의 최대 거리.
AGENT_NODE_ANALYSIS_DEFAULT_DEPTH = int(os.getenv("AGENT_NODE_ANALYSIS_DEFAULT_DEPTH", "2"))
# 한 분석 run 이 방문·분석할 최대 노드 수(비용 상한, 요청이 미지정 시 기본값). 1..1000 로 클램프.
AGENT_NODE_ANALYSIS_DEFAULT_BUDGET = int(os.getenv("AGENT_NODE_ANALYSIS_DEFAULT_BUDGET", "150"))
# 요청이 지정할 수 있는 하드 상한(사용자 지정 depth/budget 도 이 값으로 캡).
AGENT_NODE_ANALYSIS_MAX_DEPTH = int(os.getenv("AGENT_NODE_ANALYSIS_MAX_DEPTH", "5"))
AGENT_NODE_ANALYSIS_MAX_BUDGET = int(os.getenv("AGENT_NODE_ANALYSIS_MAX_BUDGET", "1000"))
# insight-worker 틱 1회에 처리할 노드 수(부하 분산). 워커는 틱 안에서 노드를 **순차** 처리하므로
#   이 값은 동시성이 아니라 **처리량**을 결정한다 — 4 는 수백 노드 스키마 분석이 수 시간 걸려
#   "중단된 것처럼" 보이는 원인이었다(node-analysis-coverage). 10 으로 상향해 체감 완료 시간을 단축
#   (LLM 은 여전히 틱당 순차 호출이라 동시 부하 급증 없음).
AGENT_NODE_ANALYSIS_BATCH_PER_TICK = int(os.getenv("AGENT_NODE_ANALYSIS_BATCH_PER_TICK", "10"))
# stale 'running' 잡 lease(초). 워커 크래시/SIGTERM 로 running 에 갇힌 잡을 이 시간 초과 시 pending 으로
# 되돌려 run 영구 미완료·재트리거 불가를 방지(reaper). LLM 타임아웃보다 넉넉히 크게(기본 15분).
AGENT_NODE_ANALYSIS_LEASE_SEC = int(os.getenv("AGENT_NODE_ANALYSIS_LEASE_SEC", "900"))
# ── 일시 실패 재시도 (analysis-retry-resilience, 사용자 리포트 2026-07-30) ─────
#  문제: LLM 호출이 네트워크 단절·타임아웃·429·빈 응답으로 실패하면 잡이 즉시 terminal 'failed' 로
#  굳고, lease reclaim 은 'running' 만 보므로 단절이 해소돼도 되살아나지 않았다("네트워크가 다시
#  연결되더라도 아무런 작업이 이루어지지 않습니다"). 이제 일시 실패는 pending 으로 되돌려 지수
#  backoff 후 자동 재시도하고, 아래 상한을 넘으면 종전처럼 terminal 로 종결한다(비용 상한 유지).
#  MAX_ATTEMPTS: 잡당 총 LLM 시도 횟수 상한(첫 시도 포함). 1 이면 재시도 없음 = 종전 동작.
AGENT_NODE_ANALYSIS_MAX_ATTEMPTS = int(os.getenv("AGENT_NODE_ANALYSIS_MAX_ATTEMPTS", "4"))
#  backoff = BASE × 2^(attempts-1), MAX 로 캡. **MAX 는 LEASE_SEC 미만으로 유지해야 한다** —
#  재시도 대기가 lease 를 넘기면 enqueue dedup 이 그 run 을 stale 로 보고 재트리거 시 중복 run 을
#  만든다(워커는 대기 잡을 가진 run 의 updated_at 을 갱신하지만, 여유를 둔다).
AGENT_NODE_ANALYSIS_RETRY_BASE_SEC = int(os.getenv("AGENT_NODE_ANALYSIS_RETRY_BASE_SEC", "60"))
AGENT_NODE_ANALYSIS_RETRY_MAX_SEC = int(os.getenv("AGENT_NODE_ANALYSIS_RETRY_MAX_SEC", "600"))
#  회로차단: 연속 일시 실패가 이 횟수에 도달하면 다음 틱의 claim 을 canary 1건으로 축소한다 —
#  LLM 도달 불가가 확정된 동안 틱당 BATCH_PER_TICK(10)건을 태우던 큐 소모를 끊고, canary 성공
#  즉시 정상 배치로 복귀한다. 0 = 회로차단 비활성(종전 동작).
AGENT_NODE_ANALYSIS_CIRCUIT_FAILS = int(os.getenv("AGENT_NODE_ANALYSIS_CIRCUIT_FAILS", "3"))
# feature-0016 routine-dbanalysis: DB(스키마) 단위 능동 분석 1회 시드 상한(LLM 비용 가드).
#   node-analysis-coverage(2026-07-10): 기본 200 은 수백 객체 스키마(예: cc_data_main = 테이블 255 +
#   루틴 300 = 555)에서 시드가 200 으로 잘리고, 나머지는 depth-2 재귀 도달성에 의존해 tail 이 조용히
#   미분석으로 남는 원인이었다(§55 목표 "DB 하위 전 노드 분석" 과 배치). 1000 으로 상향해 현실적 게임
#   스키마를 1회 run 으로 전량 시드한다 — 비용은 UI dry_run confirm 이 대상 수를 표시해 게이트하고,
#   only_missing 기본 + node_budget 이 재귀 폭증을 캡한다. 초대형(>SCHEMA_MAX) 스키마는 여전히
#   capped=True 로 표시되고 재실행이 잔여분을 드레인한다.
AGENT_NODE_ANALYSIS_SCHEMA_CAP = int(os.getenv("AGENT_NODE_ANALYSIS_SCHEMA_CAP", "1000"))
AGENT_NODE_ANALYSIS_SCHEMA_MAX = int(os.getenv("AGENT_NODE_ANALYSIS_SCHEMA_MAX", "2000"))
# ── DB(스키마) 단위 분석 재귀 전개 (feature-0016 §55, REQ-20260706 ③) ─────────
#  스키마 단위 run 도 시드(테이블·루틴)별 재귀를 전개한다 — 시드마다 자기 자신이 앵커(per-seed 앵커,
#  jobs.anchor_key)라 게이팅은 각 테이블 기준. 비용 경계: depth 는 SCHEMA_DEPTH, 총 노드는
#  min(SCHEMA_RUN_BUDGET_MAX, planned×SCHEMA_EXPAND_FACTOR) — 시드 자체는 항상 예산에 포함된다.
AGENT_NODE_ANALYSIS_SCHEMA_DEPTH = int(os.getenv("AGENT_NODE_ANALYSIS_SCHEMA_DEPTH", "2"))
AGENT_NODE_ANALYSIS_SCHEMA_EXPAND_FACTOR = float(os.getenv("AGENT_NODE_ANALYSIS_SCHEMA_EXPAND_FACTOR", "12"))
# node-analysis-coverage: SCHEMA_CAP 상향(1000)에 맞춰 재귀 전개 총량 상한도 상향 — 시드는 항상
#   예산에 포함되므로(코드가 max(len(targets), …) 하한 고정) 이 값은 시드 위에 얹히는 재귀 여유분.
AGENT_NODE_ANALYSIS_SCHEMA_RUN_BUDGET_MAX = int(os.getenv("AGENT_NODE_ANALYSIS_SCHEMA_RUN_BUDGET_MAX", "4000"))
# ── refine-not-override + back-refine (feature-0016 §55, REQ-20260706 ③) ────
#  모든 재분석은 이전 분석문을 payload.previous_analysis 로 받아 비교·융합(refine)한다. 빈약(thin) 분석
#  노드는 같은 run 의 후속 재귀가 인접 노드를 분석 완료할 때 재-pending(pass_no+1)되어 새 맥락으로
#  보충된다. run 당 REFINE_MAX 캡.
#
#  thin 판정(feature-0031 재정의): **항목 충족도**(summary·relationships·usage, Table 은 role)가
#  2개 미만이거나 summary 가 THIN_CHARS 미만이면 thin. 종전에는 길이 단독 판정이었고 기본값이
#  120 자였는데, 프롬프트 계약이 "한국어 1~2문장"이라 **정상 분석 대부분이 thin 으로 잡혔다** —
#  REFINE_MAX 캡이 폭주를 막고 있었을 뿐 캡을 올리면 대량 재분석이 터지는 구조였다.
#  기본 하한은 20 자다: 계약대로 쓴 한국어 한 문장이 ~28자라(예 "아이템 드롭 정의를 담는 컨텐츠
#  마스터 테이블이다.") 40 자 하한도 여전히 정상 분석을 걸러낸다. 20 자는 "테이블입니다" 류의
#  한 문장도 못 되는 응답만 잡는 하한이고, 실질 판정은 충족도가 맡는다.
AGENT_NODE_ANALYSIS_THIN_CHARS = int(os.getenv("AGENT_NODE_ANALYSIS_THIN_CHARS", "20"))

# ── 백그라운드 LLM 토큰 예산 (feature-0032-llm-token-budget) ────────────────
#  사람 confirm 없이 나가는 자동 LLM 지출의 rolling 24시간 상한(토큰). 0 = 무제한(비활성).
#  실측(2026-07-30, 7일): Anthropic 8,654콜/55,567,176 토큰 · edge 25콜 → 과금 lane 99.7%.
#  그중 백그라운드 소비가 약 2,600만/7일(일 평균 ≈371만)이라 기본 2,000만은 정상 운영에 무영향이고
#  폭주(5배 이상)만 잡는다. 사용자 요청 경로(대화 답변·자가검증·제목·분류)는 세지도 막지도 않는다 —
#  예산으로 사용자를 막으면 비용 통제가 아니라 서비스 장애다(shared/llm_budget.py).
AGENT_BACKGROUND_LLM_TOKEN_CAP_24H = int(
    os.getenv("AGENT_BACKGROUND_LLM_TOKEN_CAP_24H", "20000000"))

# ── L2 클러스터 합성 요약 (feature-0033-analysis-synthesis) ─────────────────
#  클러스터(라이브 818개)에 라벨(평균 9자)만 있고 요약이 없어 전역 질의가 개별 분석문을 훑어야
#  한다. 이 스위치가 그 층의 생성 여부를 정한다(0=정지). 비용은 pass 당 상한(_SUMMARY_MAX_PER_PASS)
#  과 백그라운드 토큰 예산(feature-0032) 아래에 있다.
AGENT_METADATA_CLUSTER_SUMMARY = int(os.getenv("AGENT_METADATA_CLUSTER_SUMMARY", "1"))

# ── L2 요약의 대화 grounding 주입 (feature-0034-analysis-consumption, ITEM-09) ──
#  분석 산출물이 관리 콘솔 열람에만 갇혀 있던 공백(RI-5)을 메운다. 질문이 언급한 테이블이 속한
#  묶음의 요약 1~2건을 답변 컨텍스트에 붙인다. **사전 계산분만** 쓰며(런타임 합성 금지),
#  0 으로 내리면 주입이 멈추고 답변은 종전 grounding 으로 진행한다.
AGENT_CLUSTER_SUMMARY_GROUNDING = int(os.getenv("AGENT_CLUSTER_SUMMARY_GROUNDING", "1"))

# ── 커버리지 우선순위 자동 시드 (feature-0035-analysis-planner, ITEM-11) ────
#  분석 대상이 "사용자가 클릭한 노드 + 이웃"으로만 정해져 커버리지가 중요도와 무관하게 편향된다
#  (라이브 2026-07-31 실측: 테이블 2,040/17,192 = 11.9%). 구조 변경이 없는 사이클에 중요도 상위
#  미분석 테이블을 소량 자동 시드해 그 편향을 메운다. 시드 큐잉은 change-reanalysis 와 같은
#  경로(자격·그래프 실재·cap·쿨다운·busy 가드)를 쓰므로 안전장치가 이중이다.
#  SEED_CAP 은 **사이클당** 시드 수 — 작게 유지해 자동 LLM 지출이 서서히 오르게 한다.
AGENT_ANALYSIS_COVERAGE_SEEDS = int(os.getenv("AGENT_ANALYSIS_COVERAGE_SEEDS", "1"))
AGENT_ANALYSIS_COVERAGE_SEED_CAP = int(os.getenv("AGENT_ANALYSIS_COVERAGE_SEED_CAP", "3"))
#  ⚠ 위 SEED_CAP 은 **스키마당**이다. 시드는 스키마 루프 안에서 일어나고 큐잉 경로의 cap·쿨다운도
#  스키마 단위라, 사이클 전체 상한이 따로 없으면 스키마 수(라이브 수백)만큼 곱해진다.
AGENT_ANALYSIS_COVERAGE_CYCLE_CAP = int(os.getenv("AGENT_ANALYSIS_COVERAGE_CYCLE_CAP", "9"))
AGENT_NODE_ANALYSIS_REFINE_MAX = int(os.getenv("AGENT_NODE_ANALYSIS_REFINE_MAX", "30"))
# LLM 분석이 컨텍스트 안에서 확신한 조인 후보(suggested_links)를 관계 저장소(source='llm_insight',
# candidate)로 적재하는 잡당 상한. 0 이면 비활성. 끝점은 rag_objects 실재 검증을 통과해야 하며,
# 이후 기존 프로브·자기교정 파이프라인이 강화/파단을 판정한다(ADR-002 계열).
AGENT_NODE_ANALYSIS_SUGGEST_LINKS_MAX = int(os.getenv("AGENT_NODE_ANALYSIS_SUGGEST_LINKS_MAX", "4"))
# ADR-017 부모 테이블 same-depth 승격 관련도(기존 getattr 폴백 0.5 의 명시 선언 — 동작 불변).
AGENT_NODE_ANALYSIS_PARENT_TABLE_REL = float(os.getenv("AGENT_NODE_ANALYSIS_PARENT_TABLE_REL", "0.5"))
# ── 컬럼 인벤토리 lazy introspection (node-analysis-completeness, 사용자 리포트 2026-07-23) ──
#  §55 의 "직계 컬럼 게이트 면제 편입"은 그래프 HAS_COLUMN 이웃에 의존하는데, Column 정점은
#  큐레이션(column_descriptions)·관계 끝점만 투영된다 — 메타데이터 부트스트랩을 거치지 않은
#  datasource(예: mysql-local/log_v2)는 그래프에 컬럼이 없어 DB 전체 분석이 테이블/루틴만 다뤘다.
#  Table 잡 처리 직전 datasource 라이브 INFORMATION_SCHEMA 로 컬럼 목록(+ordinal·comment)을
#  column_descriptions 스켈레톤으로 채우고(관계형 SSOT 우선) Column 정점을 targeted MERGE 한다.
#  테이블당 컬럼 상한(초과분 절단). 0 = introspection 비활성.
AGENT_NODE_ANALYSIS_COLUMN_INTROSPECT_CAP = int(os.getenv("AGENT_NODE_ANALYSIS_COLUMN_INTROSPECT_CAP", "200"))
# ── 구조 변동 자동 재분석 (change-reanalysis, 사용자 결정 2026-07-27) ─────────
#  "DB 전체 AI 능동 분석"을 이미 마친 스키마에서 insight-worker 가 구조 변동(테이블 신규/컬럼 구성
#  변경/루틴 신규·정의 변경)을 감지하면, 사용자가 그래프 뷰에서 다시 트리거하지 않아도 그 변경 노드를
#  시드로 하는 node_analysis run 을 자동 생성한다(시드별 per-seed 앵커 재귀 = 수동 DB 전체 분석과 동일
#  규약). **외부 LLM 비용 직결** 이라 4중 가드로 경계한다:
#    (1) 자격 — 해당 스키마에 status='done' Schema run 이력이 있어야만 발동(미분석 DB 는 자동 발동 없음).
#    (2) 시드 상한 — 1회 트리거당 AUTO_CHANGE_CAP 개.
#    (3) 스키마별 쿨다운 — AUTO_CHANGE_COOLDOWN_SEC 이내 재발동 금지(대량 DDL 의 연쇄 트리거 차단).
#    (4) 노드별 지문 마커 — 같은 지문으로는 재발동하지 않음(insight artifact 발행 실패와 무관하게 1회).
#  **변경 감지는 insight 지문(table_fp)이 아니라 전용 구조 스냅샷**(`na_struct_snap:*` KV, 스키마당 1건)
#  으로 한다 — table_fp 는 insight artifact 발행이 성공한 테이블만·스캔당 12개씩 채워져 커버리지가
#  희소하므로, 그것의 부재를 '신규'로 읽으면 이미 분석된 DB 의 테이블 대부분이 오탐된다(적대 리뷰 B1).
#  기본 ON(사용자 결정 2026-07-27 — "사용자의 별도 AI 분석 없이 자연스럽게").
#  3-state: "1"/"on"=발동 · "shadow"=후보 산출·계측만(enqueue 0, 배포 직후 규모 측정용) · "0"/"off"=완전 차단.
AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE_MODE = (
    os.getenv("AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE", "1").strip().lower() or "1")
AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE = AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE_MODE not in (
    "0", "false", "no", "off")
# 1회 자동 트리거의 시드 상한(변경 노드 수). 초과분은 스냅샷을 갱신하지 않아 다음 사이클에 이어서 처리된다.
# **3-state (node_analysis.AUTO_CAP_SHADOW 규약 — 관리 콘솔에서 숫자 하나로 라이브 전환)**:
#   >0 = 발동 · 0 = 완전 정지(신규 트리거 + 이미 큐잉된 SchemaAuto 잡 drain 보류) · -1 = shadow(계측만).
# 안전 모드 전환에 재배포가 필요하면 사고 시 무용이라, 단일 int knob 으로 콘솔 즉시 전환을 보장한다.
AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP = int(os.getenv("AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP", "50"))
# 스키마별 자동 트리거 쿨다운(초). 마이그레이션처럼 짧은 시간에 다수 DDL 이 몰릴 때 run 남발을 막는다.
AGENT_NODE_ANALYSIS_AUTO_CHANGE_COOLDOWN_SEC = int(
    os.getenv("AGENT_NODE_ANALYSIS_AUTO_CHANGE_COOLDOWN_SEC", "1800"))
# 자동 run 의 재귀 전개 배수(시드 수 × 배수 = node_budget, SCHEMA_RUN_BUDGET_MAX 로 캡).
# 수동 SCHEMA_EXPAND_FACTOR(12)보다 보수적 — 자동 발동은 사람 confirm 게이트가 없기 때문.
AGENT_NODE_ANALYSIS_AUTO_EXPAND_FACTOR = float(os.getenv("AGENT_NODE_ANALYSIS_AUTO_EXPAND_FACTOR", "4"))
# ── 앵커-상대 관련도 게이팅 (feature-0016 node-analysis-anchor, 사용자 결정 2026-07-01) ──
#  문제: 기존 재귀는 방문한 모든 노드의 이웃 전부를 무차별 재큐 → 일반 허브 컬럼(예 UniqueID)이나 부모
#  Schema 노드를 만나면 그 노드를 새 중심으로 삼아 무관한 테이블로 fan-out(원래 대상에 앵커되지 않음).
#  해법: 후보 이웃을 **원래 루트(예 dk 제품·Achievement)와의 관련도**(0~1)로 평가해 게이트·우선순위화.
#  - 루트 직속 컬럼(하위 컬럼)은 기본 분석(게이트 면제). 그 외는 관련도 임계 이상만 재귀.
#  - 임계는 깊이가 깊을수록 상향(depth>=2 는 _DEEP 적용) → 허브 재탐색 억제.
#  - 다른 제품(scope)·일반어만 일치·상위객체 무연관은 낮은 점수 → 재귀 제외(낮은 우선순위).
AGENT_NODE_ANALYSIS_RELEVANCE_MIN = float(os.getenv("AGENT_NODE_ANALYSIS_RELEVANCE_MIN", "0.18"))
# depth>=2(루트에서 2-hop 이상) 재귀 확장에 요구하는 더 엄격한 관련도 기준 임계. 실제 임계는 이 값에서
# 깊이당 +0.06 씩 상향(상한 0.7) — MAX_DEPTH 를 크게 잡아도 "깊을수록 상향" 이 유지된다.
AGENT_NODE_ANALYSIS_RELEVANCE_MIN_DEEP = float(os.getenv("AGENT_NODE_ANALYSIS_RELEVANCE_MIN_DEEP", "0.34"))
# 다른 scope(제품) 이웃에 곱하는 감쇠 계수(0~1). 0 이면 교차-제품 확장 완전 차단.
AGENT_NODE_ANALYSIS_CROSS_SCOPE_FACTOR = float(os.getenv("AGENT_NODE_ANALYSIS_CROSS_SCOPE_FACTOR", "0.25"))
# Schema 노드를 재귀 확장 허브로 쓸지 여부. 기본 False — 부모 Schema 확장 시 형제 테이블 전량 fan-out 방지.
AGENT_NODE_ANALYSIS_EXPAND_SCHEMA = os.getenv("AGENT_NODE_ANALYSIS_EXPAND_SCHEMA", "0").strip().lower() in ("1", "true", "yes")
AGENT_DB_CONNECT_RETRIES = int(os.getenv("AGENT_DB_CONNECT_RETRIES", "3"))
AGENT_DB_CONNECT_BACKOFF_SEC = float(os.getenv("AGENT_DB_CONNECT_BACKOFF_SEC", "0.5"))
# ── 데이터플레인 연결 liveness (FR-dataplane-conn-stale-no-reconnect) ──────────
# run 시작에 수립한 데이터플레인 연결은 그 run 의 모든 tool 호출에 재사용되는데, 유휴
# (첫 tool 까지 LLM 추론이 수 분) 또는 쿼리 타임아웃으로 죽으면 남은 tool 이 전부 드라이버
# 문구로 실패한다. tools.execute_tool 이 사용 직전 liveness 를 확인하고 같은 좌표로
# 재연결한다. 이 값은 **ping 생략 임계** — 마지막 성공 사용 후 이 시간 안이면 ping 없이
# 그대로 쓴다(왕복 0). 실측 사망 하한이 60초대라 그보다 넉넉히 작게 잡는다. 0 = 항상 ping.
AGENT_DS_CONN_PING_IDLE_SEC = float(os.getenv("AGENT_DS_CONN_PING_IDLE_SEC", "30"))
# ── 데이터플레인 연결 격리 (TASK: ds-connect-isolation) ────────────────────────
# 문제: 데이터플레인 연결의 connection_timeout/login_timeout 이 쿼리 예산
# AGENT_TIMEOUT_SEC(운영 300s)를 그대로 재사용해, 불안정/다운 datasource 연결 1회
# 시도가 최대 300s 블록 + connect_with_retry ×3 → ~900s. 단일 ask-worker 가 job 을
# 직렬 처리하므로 그 한 건이 worker 를 점유 → **정상 datasource 제품 job 까지 지연**.
#
# 해결 1: 연결 timeout 을 쿼리 예산에서 분리. **연결 수립(TCP/로그인)** 전용 짧은 상한.
#   data-plane(원격 customer datasource) connect 에만 적용 — 로컬 control-plane(memory
#   DB, datasource=None)은 AGENT_TIMEOUT_SEC 유지(동작 0 변경). 0/미설정이면 비활성
#   (= AGENT_TIMEOUT_SEC 폴백, 기존 동작).
AGENT_DB_CONNECT_TIMEOUT_SEC = _startup_int("AGENT_DB_CONNECT_TIMEOUT_SEC", int(os.getenv("AGENT_DB_CONNECT_TIMEOUT_SEC", "10")))
# ── control-plane 연결 격리 (TASK-0255) ───────────────────────────────────────
# 문제: control-plane(datasource=None: MEMORY_DB/DB_CONNECT_DB/replica/data-RO) MySQL 연결은
# connection_timeout=AGENT_TIMEOUT_SEC(운영 300s)를 그대로 써, control-plane 이 불안정하면 insight
# cycle 의 첫 connect(mem_conn/db_conn)가 최대 300s×retry 블록 후 status=error → degraded_backoff.
# data-plane(AGENT_DB_CONNECT_TIMEOUT_SEC) 와 달리 bounded 가 없던 잔존 경로.
# 해결: 연결 *수립* 상한을 쿼리 예산과 분리(기본 10s). control-plane 은 로컬·신뢰 호스트라 안전.
#   **breaker 는 적용하지 않는다**(MEMORY_DB fast-fail=전체 마비) — timeout 만 bounded.
#   0/미설정이면 코드 폴백 10s(AGENT_TIMEOUT_SEC 300s 회귀 방지 — data-plane 폴백과 다름).
AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC = _startup_int("AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC", int(os.getenv("AGENT_DB_CONTROLPLANE_CONNECT_TIMEOUT_SEC", "10")))
# ── 연결 health 모니터 (conn-health-monitor) — modules/conn_health.py ──────────
# 백그라운드 probe(TCP 선검사 + 실제 DB connect+SELECT 1)로 per-datasource 연결 상태를
# 미리 유지. agent/admin 은 미리 계산된 상태를 즉시 읽어, 한 datasource 불안정이 다른
# 정상 datasource 요청을 막지 않는다. TCP 선검사 timeout=BASE(100ms, 죽은 서버 fast-fail),
# 실제 DB probe timeout=적응형 1s→×2→MAX(10s). ENABLED=0 이면 모니터 미시작 + gate
# 비활성(기존 동작 0 변경). (구 TASK-0247 in-process breaker 는 본 모니터로 흡수·대체됨.)
AGENT_CONN_HEALTH_ENABLED = os.getenv("AGENT_CONN_HEALTH_ENABLED", "1").strip().lower() in ("1", "true", "yes")
AGENT_CONN_PROBE_TIMEOUT_MS_BASE = _startup_int(
    "AGENT_CONN_PROBE_TIMEOUT_MS_BASE",
    max(10, int(os.getenv("AGENT_CONN_PROBE_TIMEOUT_MS_BASE", "100") or "100")),
)
AGENT_CONN_PROBE_TIMEOUT_MS_MAX = max(
    AGENT_CONN_PROBE_TIMEOUT_MS_BASE,
    _startup_int(
        "AGENT_CONN_PROBE_TIMEOUT_MS_MAX",
        int(os.getenv("AGENT_CONN_PROBE_TIMEOUT_MS_MAX", "10000") or "10000"),
    ),
)
# healthy 재확인 주기(초) / unstable 재probe 간격(초, base→×2→MAX backoff).
AGENT_CONN_HEALTHY_RECHECK_SEC = max(1, int(os.getenv("AGENT_CONN_HEALTHY_RECHECK_SEC", "30") or "30"))
AGENT_CONN_UNSTABLE_RECHECK_SEC = max(1, int(os.getenv("AGENT_CONN_UNSTABLE_RECHECK_SEC", "2") or "2"))
AGENT_CONN_UNSTABLE_RECHECK_MAX_SEC = max(
    AGENT_CONN_UNSTABLE_RECHECK_SEC, int(os.getenv("AGENT_CONN_UNSTABLE_RECHECK_MAX_SEC", "60") or "60")
)
# 동시 probe worker 수(bulkhead — 다수 unstable 이 모니터를 직렬로 묶지 않게).
AGENT_CONN_PROBE_WORKERS = max(1, min(16, int(os.getenv("AGENT_CONN_PROBE_WORKERS", "4") or "4")))
# 모니터 scheduler tick(초).
AGENT_CONN_HEALTH_TICK_SEC = max(1, int(os.getenv("AGENT_CONN_HEALTH_TICK_SEC", "1") or "1"))
# 모니터 정지 추정 grace(초) — 모니터 미가동 + status 가 이보다 오래 stale 하면 unknown 강등(영구 차단 방지).
AGENT_CONN_STALE_GRACE_SEC = max(5, int(os.getenv("AGENT_CONN_STALE_GRACE_SEC", "60") or "60"))
# ── 연결 상태 3단계 분류(conn-tristate) — healthy(초록)/unstable(빨강)/down(회색) ──
# TCP 선검사 timeout(ms) — 다른 리전 datasource 의 핸드셰이크 RTT 가 구 100ms(BASE)를 넘겨
# **연결 가능한 느린 서버까지 죽은 것으로 오판**하던 문제를 완화한다. 기본 5000ms.
# 근거(TASK-0290 라이브 실측): 구 2000ms 는 web 재시작 콜드 스타트 시 다수 타-리전 datasource
# 를 워커 4개로 동시 probe(thundering herd)하면 첫 TCP 핸드셰이크 spike 가 2000ms 를 살짝 넘겨
# (실측 mysql-kr-an2-* 2003~2237ms) 2회 연속 실패→down(회색) 으로 오판했다. 5000ms 면 콜드/원거리
# RTT spike 를 흡수해 연결 가능한 느린 서버(예: mysql-mv-qa-* TCP 195ms+DB 1749ms)를 unstable
# (빨강, 느림)로 유지한다. ECONNREFUSED/도달불가 같은 진짜 죽은 서버는 timeout 무관(즉답) 또는
# 5s 로도 timeout 되어 down(회색) 으로 정확히 분류된다(실측 kr-an2 errno=2003 은 5s 도 timeout).
# 30s 는 진짜 죽은 서버를 워커 4개가 점유해 모니터 라운드를 지연시키는 성능 이슈가 있어 5s 채택.
# 미설정 시 구 BASE 와 5000 중 큰 값으로 폴백(하위호환 안전).
AGENT_CONN_TCP_TIMEOUT_MS = max(
    AGENT_CONN_PROBE_TIMEOUT_MS_BASE,
    _startup_int(
        "AGENT_CONN_TCP_TIMEOUT_MS",
        int(os.getenv("AGENT_CONN_TCP_TIMEOUT_MS", "5000") or "5000"),
    ),
)
# 느림 임계(ms) — 연결은 성공했지만 elapsed_ms 가 이 값 이상이면 healthy 가 아니라 unstable(빨강,
# "연결 불안정")로 분류. 다른 리전 등 느린(하지만 살아있는) datasource 를 정상(초록)과 구분한다.
AGENT_CONN_SLOW_MS = max(1, int(os.getenv("AGENT_CONN_SLOW_MS", "1000") or "1000"))
# 끊김 판정 임계 — 연속 연결 실패가 이 횟수 이상이면 unstable(빨강) 이 아니라 down(회색, "연결 끊김").
# 1회성 blip 은 unstable 로 두고(간헐 불안정), 반복 실패해야 끊김으로 확정(flapping 방지).
AGENT_CONN_DOWN_AFTER_FAILS = max(1, int(os.getenv("AGENT_CONN_DOWN_AFTER_FAILS", "2") or "2"))
# 평균 연결 응답 시간 window(표본 수) — 백그라운드 모니터가 성공 probe 마다 측정한 elapsed_ms 를
# 이 개수만큼 rolling 으로 보관해 산술평균(관리 콘솔 데이터소스 상세 패널의 "연결 응답 시간(평균)")을
# 낸다. 마지막 1회 값(last_elapsed_ms)은 순간 변동(다른 워크로드·GC blip)에 흔들려 대표성이 약하므로
# 최근 N회 평균이 데이터소스별 상시 연결 품질을 더 안정적으로 나타낸다. 실패 probe 는 응답시간 의미가
# 없어 표본에서 제외. 1 이상(0/음수 입력은 1 로 클램프 — 사실상 마지막값과 동일).
AGENT_CONN_AVG_WINDOW = max(1, int(os.getenv("AGENT_CONN_AVG_WINDOW", "20") or "20"))
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
AGENT_INSIGHT_OBJECT_VERIFY_TIMEOUT_MS = _startup_int("AGENT_INSIGHT_OBJECT_VERIFY_TIMEOUT_MS", int(
    os.getenv("AGENT_INSIGHT_OBJECT_VERIFY_TIMEOUT_MS", "1500")
))
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
AGENT_INSIGHT_SQL_COMPOSE_TIMEOUT_SEC = _startup_int("AGENT_INSIGHT_SQL_COMPOSE_TIMEOUT_SEC", int(
    os.getenv("AGENT_INSIGHT_SQL_COMPOSE_TIMEOUT_SEC", "20")
))
AGENT_SQL_GROUNDED_REVIEW = (
    os.getenv("AGENT_SQL_GROUNDED_REVIEW", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_SQL_GROUNDED_REVIEW_TIMEOUT_SEC = _startup_int("AGENT_SQL_GROUNDED_REVIEW_TIMEOUT_SEC", int(
    os.getenv("AGENT_SQL_GROUNDED_REVIEW_TIMEOUT_SEC", "12")
))
AGENT_SQL_GROUNDED_REWRITE_ON_FAIL = (
    os.getenv("AGENT_SQL_GROUNDED_REWRITE_ON_FAIL", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_SQL_GROUNDED_BLOCK_ON_FAIL = (
    os.getenv("AGENT_SQL_GROUNDED_BLOCK_ON_FAIL", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_KNOWLEDGE_SQL_FALLBACK = (
    os.getenv("AGENT_KNOWLEDGE_SQL_FALLBACK", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC = _startup_int("AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC", int(
    os.getenv("AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC", "20")
))
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
AGENT_INSIGHT_TIMEOUT_SEC = _startup_int("AGENT_INSIGHT_TIMEOUT_SEC", int(os.getenv("AGENT_INSIGHT_TIMEOUT_SEC", "30")))
AGENT_PLAN_TIMEOUT_SEC = _startup_int("AGENT_PLAN_TIMEOUT_SEC", int(os.getenv("AGENT_PLAN_TIMEOUT_SEC", "35")))
AGENT_PLAN_TIMEOUT_RECOVERY_SEC = _startup_int("AGENT_PLAN_TIMEOUT_RECOVERY_SEC", int(os.getenv("AGENT_PLAN_TIMEOUT_RECOVERY_SEC", "20")))
AGENT_PLAN_TIMEOUT_MIN_SEC = _startup_int("AGENT_PLAN_TIMEOUT_MIN_SEC", int(os.getenv("AGENT_PLAN_TIMEOUT_MIN_SEC", "8")))
AGENT_AUX_SKIP_NEAR_DEADLINE_MS = int(
    os.getenv("AGENT_AUX_SKIP_NEAR_DEADLINE_MS", "15000")
)
AGENT_RAG_PRIORITY_TIMEOUT_SEC = _startup_int("AGENT_RAG_PRIORITY_TIMEOUT_SEC", int(
    os.getenv("AGENT_RAG_PRIORITY_TIMEOUT_SEC", "12")
))
AGENT_RAG_PRIORITY_FIRST = (
    os.getenv("AGENT_RAG_PRIORITY_FIRST", "1").strip().lower() in ("1", "true", "yes")
)
AGENT_OBJECT_RESOLVE_TIMEOUT_SEC = _startup_int("AGENT_OBJECT_RESOLVE_TIMEOUT_SEC", int(
    os.getenv("AGENT_OBJECT_RESOLVE_TIMEOUT_SEC", "8")
))
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
AGENT_INSIGHT_WORKER_LOCK_TIMEOUT_SEC = _startup_int("AGENT_INSIGHT_WORKER_LOCK_TIMEOUT_SEC", int(
    (os.getenv("AGENT_INSIGHT_WORKER_LOCK_TIMEOUT_SEC", "1") or "1").strip()
))
AGENT_INSIGHT_WORKER_STALE_SEC = int(
    (os.getenv("AGENT_INSIGHT_WORKER_STALE_SEC", "15") or "15").strip()
)
# mssql-auth-cooldown: MSSQL datasource 의 인증/권한 실패(18456/916/229/297)로 insight 순회가
# 확정 실패한 endpoint(scope)를 다음 재시도까지 억제하는 cooldown(초). auth 는 conn_health 의
# network circuit-breaker 에서 의도적으로 제외(shared/db.py _is_connect_breaker_failure)되므로,
# 그 network backoff(AGENT_CONN_UNSTABLE_RECHECK_SEC 계열, 초 단위)와 분리된 긴 cooldown 을 둔다.
# auth 실패는 운영자 개입(계정/GRANT 수정 — bin/datasource-mssql-ro-bootstrap-multidb.sql) 전까지
# 불변이라 짧게 재시도해봐야 DB 수만큼 반복 연결·로그·I/O 만 유발한다. 0 이면 cooldown 비활성
# (cycle 내 나머지 DB skip 은 유지되나 다음 cycle 은 재시도). 기본 600s(=10분).
AGENT_INSIGHT_AUTH_COOLDOWN_SEC = max(
    0, int((os.getenv("AGENT_INSIGHT_AUTH_COOLDOWN_SEC", "600") or "600").strip())
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
# claim 폴링/reconnect backoff 주기(sec). TASK-0289 이후 유휴 claim 폴링은 아래
# IDLE_POLL_SEC 로 분리됐고, 본 값은 reconnect backoff 등에만 사용.
AGENT_ASK_WORKER_TICK_SEC = int(
    (os.getenv("AGENT_ASK_WORKER_TICK_SEC", "2") or "2").strip()
)
# TASK-0289: 유휴(claim 대기) 폴링 주기(sec, float). 단일 직렬 worker 가 새 job 을
# 발견하는 지연 = 사용자 큐 대기시간. sub-second(기본 0.5)로 두어 최대 큐 대기를 단축.
# tick_sec(reconnect backoff)와 분리해 sweep/재연결 타이밍에 영향 없음.
AGENT_ASK_WORKER_IDLE_POLL_SEC = float(
    (os.getenv("AGENT_ASK_WORKER_IDLE_POLL_SEC", "0.5") or "0.5").strip()
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
# ── 재배포 인계(conv-audit FR-ask-orphan-redeploy-dead-air) ──────────────────
# drain 예산(sec) — SIGTERM 수신 후 실행 중 job 이 스스로 끝날 시간을 이만큼 준 뒤,
# 남은 자기 소유 running job 을 **명시적으로 lease 반납**(requeue)하고 종료한다.
# compose stop_grace_period(ask-worker 70s)보다 작아야 반납이 SIGKILL 前에 끝난다 —
# 반납 없이 죽으면 stale sweeper 의 STALE_SEC(수백초) 창을 통째로 기다린다(실측 dead-air 142~1649s).
AGENT_ASK_WORKER_DRAIN_SEC = int(
    (os.getenv("AGENT_ASK_WORKER_DRAIN_SEC", "60") or "60").strip()
)
# role-scoped 고아 회수 임계(sec) — **같은 worker role 의 이전 인스턴스**가 claim 한 채
# heartbeat 가 이만큼 끊긴 running job 을 회수한다. heartbeat 는 시간 기반(HEARTBEAT_SEC=10s,
# step 무관)이라 이 배수(기본 6배)를 넘겼다면 그 프로세스는 죽은 것이다. 전역 STALE_SEC 은
# cross-role false-positive 를 막으려 보수적으로 크게 유지하고, 이 좁은 창은 SIGKILL(=drain
# 반납 미실행) 경로의 backstop 이다. 자기 자신이 claim 한 행은 대상에서 제외된다.
AGENT_ASK_WORKER_ROLE_STALE_SEC = int(
    (os.getenv("AGENT_ASK_WORKER_ROLE_STALE_SEC", "60") or "60").strip()
)
AGENT_ASK_WORKER_CONVERSATION_ID = "__ask_worker__"
# worker 생존 heartbeat KV 키(healthcheck + /api/ask readiness gate 가 신선도 검사).
AGENT_ASK_WORKER_HEARTBEAT_KEY = "ask_worker_last_cycle_at"

MCP_URL = os.getenv("MCP_URL", "http://mcp:5000/mcp")
MCP_TIMEOUT_SEC = _startup_int("MCP_TIMEOUT_SEC", int(os.getenv("MCP_TIMEOUT_SEC", "20")))
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
