"""mysql_ai DBA Agent Core — Tool-based Agent Loop.

OpenAI function calling을 활용한 에이전트 루프.
LLM이 도구를 선택하고 실행 결과를 바탕으로 사용자에게 응답한다.

기존 agent_cli.py의 21K줄 휴리스틱을 대체하는 핵심 모듈.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import mysql.connector
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from modules import config as cfg
from modules.config import (
    OPENAI_API_KEY, OPENAI_MODEL, OPENAI_API_BASE,
    LLM_BASE_URL, LLM_API_KEY, LOCAL_LLM_API_KEY,
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_CONNECT_DB,
    MEMORY_DB, AGENT_TIMEOUT_SEC, AGENT_MAX_STEPS, AGENT_MAX_SHOW,
    AGENT_LOG_DIR, AGENT_MEMORY_CLEAR_KEEP_IDS,
    AGENT_OPENAI_MAX_RETRIES,
)
from modules.db import connect_with_retry, execute_sql as raw_execute_sql
from modules.memory import (
    _cancel_requested,
    _clear_cancel_request,
    _finalize_requested,
    _clear_finalize_request,
    cleanup_pending_delete_conversations,
    delete_all_conversations,
    delete_conversation as delete_conversation_records,
    ensure_memory_schema,
    is_delete_requested,
    list_processing_conversation_ids,
    load_memory_kv,
    save_memory_kv,
    save_memory_message,
    save_memory_step,
    set_run_status,
)
from modules.model_catalog import is_local_llm_model, max_tokens_for_model, model_supports_temperature, model_supports_vision
from modules.llm import llm_classify_origin_shift, llm_generate_topic, messages_for_provider
from modules.domain import _derive_topic, _should_refresh_origin_request
from modules.render import normalize_step_result_summary
from modules.tools import (
    TOOL_DEFINITIONS,
    execute_tool,
    set_active_schema_allowlist,
    clear_active_schema_allowlist,
)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

console = Console()
CSV_PATH_RE = re.compile(r"CSV 저장:\s*(/[^\s]+\.csv)")
PLACEHOLDER_TOPIC = "새 대화"

# ══════════════════════════════════════════════════════════════════
#  시스템 프롬프트
# ══════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a MySQL DBA expert assistant. Your job is to answer the user's question with data, not to explore.

## CRITICAL DIRECTIVE
**Execute SQL first, explore later (only if needed).** You have a limited step budget. Every search_tables or describe_table call that could have been an execute_sql is a wasted step. When the KNOWN SCHEMAS section below provides candidate tables, write SQL immediately.

## CORE RULES
1. Never fabricate data. Only present rows returned by execute_sql.
2. Always use `schema`.`table` format in SQL.
3. Your goal is to produce one or a few execute_sql calls that directly answer the question, then write the final answer.
4. Table and column names are in English. Translate Korean keywords in the user's question to likely English identifiers before acting.

## STRATEGY (in priority order)
1. **Use the KNOWN SCHEMAS & TABLES section below as your primary source.** If it lists tables relevant to the question, go straight to execute_sql against those tables. Do NOT call search_tables when a plausible table is already listed.
2. **Prefer execute_sql from the start.** A well-formed SELECT against a likely table is more productive than exploration. If your SQL fails with an unknown column/table error, read the error and adjust — do not fall back to broad searching.
3. **describe_table is only for resolving ambiguity** about columns when execute_sql has failed or when the insight text is too vague to form a correct query. Limit to at most one describe_table per target table per run.
4. **search_tables is a last resort** — use it only when the knowledge section is empty for the relevant domain. Never call search_tables twice with the same keyword, and never call it after you already have a candidate table.
5. **get_sample_rows is almost never needed** — only use it when column content format (e.g., JSON structure) cannot be inferred from describe_table.

## IDEAL FLOW EXAMPLE
User asks about recent orders → KNOWN SCHEMAS lists `ecommerce.orders` → You immediately call execute_sql with `SELECT ... FROM \`ecommerce\`.\`orders\` WHERE ...` → Get data → Write answer. Total: 1 tool call.

## ANTI-PATTERNS (avoid these — each one wastes your limited steps)
- Chaining search_tables → describe_table → describe_table → ... before any execute_sql. This wastes steps.
- Re-exploring a table you already described in an earlier step of this run.
- Calling tools just to "verify" — if you have enough information to write SQL, write it.
- Using search_tables when KNOWN SCHEMAS already lists relevant tables.
- Describing a table before attempting execute_sql — try the query first, fix errors after.

## SQL PATTERNS
- Cross-schema JOIN:
  SELECT d.name, COUNT(*) cnt FROM `data_schema`.`t` a JOIN `config_schema`.`d` d ON a.id = d.id GROUP BY d.name ORDER BY cnt DESC
- JSON array column:
  SELECT jt.col, COUNT(*) cnt FROM `s`.`t` CROSS JOIN JSON_TABLE(json_col, '$[*]' COLUMNS(col INT PATH '$.key')) jt GROUP BY jt.col ORDER BY cnt DESC

## OUTPUT
Once execute_sql has returned the data you need, stop calling tools and write the final answer in Korean Markdown. Format numbers with commas (1,234,567). Use tables when comparing rows.
"""


# TASK-0094 Sprint 2 (D13) — image inline 의 caller 책임 분리 정합.
#
# storage_minio.py 는 feature-0003-agent-web-ui 의 module 이라 cross-feature import
# 정책 위배. 대신 caller (`unit/feature-0003-agent-web-ui/src/app.py` 의 /api/ask
# endpoint) 가 image bytes 를 미리 fetch + base64 + JSON 직렬화 → 임시 file 저장 →
# env `ATTACHMENT_IMAGE_INLINE_PATH` 로 path 만 전달. agent_core 는 path 만 read.
#
# JSON spec (caller 가 작성):
#   [
#     {"filename": str, "mime_type": "image/png|jpeg|webp", "base64_data": str},
#     ...
#   ]
#
# size cap (단일 ≤ 5MB pre-base64), count cap (turn 당 ≤ 5) 은 caller (app.py) 의
# 책임. 본 helper 는 file read + parse + graceful failure 만.
_INLINE_IMAGE_ENV_VAR = "ATTACHMENT_IMAGE_INLINE_PATH"


def _load_attachment_inline_images() -> list[dict[str, Any]]:
    """env ATTACHMENT_IMAGE_INLINE_PATH 의 JSON 을 read 후 image_attachments 반환.

    Returns: list[{filename, mime_type, base64_data}]. env 부재 / file 미존재 /
    parse 실패 / 빈 base64 → 빈 list (graceful failure, agent 진행 차단 X).

    D13 정합: 본 함수는 base64 string 만 다루고 storage_minio / signed URL 에 직접
    접근하지 않는다. caller (app.py) 가 server-side bytes read + base64 inline 책임.
    """
    path = os.getenv(_INLINE_IMAGE_ENV_VAR, "").strip()
    if not path:
        return []
    try:
        if not os.path.isfile(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    result: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        b64 = str(item.get("base64_data") or "").strip()
        if not b64:
            continue
        mime = str(item.get("mime_type") or "image/png").strip() or "image/png"
        filename = str(item.get("filename") or "").strip()
        result.append({
            "filename": filename,
            "mime_type": mime,
            "base64_data": b64,
        })
    return result


def _build_attachment_context_section(mem_conn, attachment_ids: list[int]) -> str:
    """TASK-0094 Sprint 1 Phase 11 — selected attachment metadata 를 prompt context 에 주입.

    Cycle 1 (Phase 11) 시점은 CSV/XLSX metadata 만 (sandbox table 명 + sheet/row counts).
    Cycle 2 vision / Cycle 3 KB / Cycle 4 RAG 진입 시 본 helper 가 kind 별로 확장.

    D16 정합: attachment_ids 가 빈 list 면 본 section 미주입 (minimum exposure).
    """
    if not attachment_ids or mem_conn is None:
        return ""
    try:
        cur = mem_conn.cursor()
    except Exception:
        return ""
    try:
        placeholders = ", ".join(["%s"] * len(attachment_ids))
        cur.execute(
            f"""
            SELECT Id, ConversationId, OriginalFilename, Kind, MimeType,
                   SizeBytes, SizeBucket, UploadStatus, MetaJson
            FROM WebConversationAttachments
            WHERE Id IN ({placeholders}) AND DeletedAt IS NULL AND DeletePending = 0
            ORDER BY Id ASC
            """,
            tuple(int(i) for i in attachment_ids),
        )
        rows = cur.fetchall() or []
    except Exception:
        return ""
    finally:
        try:
            cur.close()
        except Exception:
            pass
    if not rows:
        return ""
    lines = ["", "## ATTACHED FILES (User-selected, available for analysis)"]
    for row in rows:
        attachment_id = int(row[0] or 0)
        kind = str(row[3] or "")
        filename = str(row[2] or "")
        size_bucket = str(row[6] or "")
        upload_status = str(row[7] or "")
        meta_text = ""
        try:
            import json as _json
            meta = row[8]
            if isinstance(meta, str):
                meta = _json.loads(meta)
            if isinstance(meta, dict):
                if meta.get("sandbox_table_name"):
                    meta_text += f" sandbox_table=`{meta['sandbox_table_name']}`"
                if meta.get("ingest_summary"):
                    meta_text += f" summary={meta['ingest_summary']}"
                if meta.get("degraded_reason"):
                    meta_text += f" [DEGRADED: {meta['degraded_reason']}]"
        except Exception:
            pass
        lines.append(
            f"- attachment_id={attachment_id} kind={kind} file={filename} size={size_bucket} status={upload_status}{meta_text}"
        )
    lines.append(
        "Use the sandbox tables for analysis. The actual file body is NOT included — refer by attachment_id when calling tools.\n"
    )
    return "\n".join(lines)


def compose_system_prompt(
    mem_conn,
    *,
    product_id: int | None = None,
    role_id: int | None = None,
    account_id: int | None = None,
    product_mode: str = "pinned",
) -> str:
    """Product → Role → Account 순으로 custom 시스템 프롬프트를 base 뒤에 append 한다.

    Role/Account scope 에서 `ProductId IS NULL` 공통 prompt 는 fallback 이 아니라 먼저 누적한다.
    현재 product 한정 prompt 가 있으면 공통 prompt 뒤에 추가한다. mem_conn 이 None 이거나
    테이블이 없으면 base SYSTEM_PROMPT 를 그대로 반환.

    product_mode='auto' 인 경우(사용자가 특정 제품을 고정하지 않은 일반 대화 모드):
      - PRODUCT CONTEXT 블록은 주입하지 않는다 (제품 한정 가이드가 없으므로 일반 답변 유도).
      - 대신 한 줄 AUTO MODE 안내를 base 직후에 append 해 LLM 이 "제품 미선택" 상태를 인지하게 한다.
      - role/account scope prompt 는 ProductId IS NULL 의 공통 prompt 만 사용한다.
    """
    if mem_conn is None:
        return SYSTEM_PROMPT
    is_auto = str(product_mode or "pinned").lower() == "auto"

    # TASK-0095 (Major §12.3): GLOBAL scope 가 최상위. WebSystemPrompts 의
    # scope='global' 단일 row (Product/Role/Account 모두 NULL) 가 truth, 부재/예외 시
    # 코드 상수 SYSTEM_PROMPT 가 bootstrap fallback. 운영자가 admin 콘솔에서 재배포
    # 없이 BASE 를 수정할 수 있게 한다.
    base_prompt = SYSTEM_PROMPT
    try:
        _bcur = mem_conn.cursor()
        _bcur.execute(
            "SELECT Content FROM WebSystemPrompts "
            "WHERE Scope='global' AND ProductId IS NULL "
            "AND RoleId IS NULL AND AccountId IS NULL LIMIT 1"
        )
        _brow = _bcur.fetchone()
        if _brow and _brow[0]:
            base_prompt = str(_brow[0])
        try:
            _bcur.close()
        except Exception:
            pass
    except Exception:
        # WebSystemPrompts 미존재 (bootstrap-time) 또는 SQL 예외 — 코드 상수 fallback
        base_prompt = SYSTEM_PROMPT

    parts: list[str] = [base_prompt]
    if is_auto:
        parts.append(
            "\n\n[AUTO MODE] No product is pinned to this conversation. "
            "Answer generally; if product-specific data is required, ask the user to pick a 제품 first.\n"
        )
    try:
        cur = mem_conn.cursor()
    except Exception:
        return base_prompt

    def _fetch(
        scope: str,
        scope_col: str,
        scope_val: int | None,
        *,
        prompt_product_id: int | None,
    ) -> tuple[str, str]:
        """해당 scope/product 조합의 prompt 와 표시용 label 을 반환. 없으면 ('','')."""
        if scope_val is None or scope_val <= 0:
            return ("", "")
        try:
            if prompt_product_id and prompt_product_id > 0:
                cur.execute(
                    f"SELECT Content FROM WebSystemPrompts "
                    f"WHERE Scope=%s AND {scope_col}=%s AND ProductId=%s LIMIT 1",
                    (scope, int(scope_val), int(prompt_product_id)),
                )
                row = cur.fetchone()
                if row and row[0]:
                    return (str(row[0]), f"ProductId={prompt_product_id}")
                return ("", "")
            cur.execute(
                f"SELECT Content FROM WebSystemPrompts "
                f"WHERE Scope=%s AND {scope_col}=%s AND ProductId IS NULL LIMIT 1",
                (scope, int(scope_val)),
            )
            row = cur.fetchone()
            if row and row[0]:
                return (str(row[0]), "all products")
        except Exception:
            return ("", "")
        return ("", "")

    # Product-scope prompt (1건만) — auto 모드에서는 건너뛴다 (사용자가 제품을 고정하지 않은 상태).
    product_label = ""
    if (not is_auto) and product_id and product_id > 0:
        try:
            cur.execute("SELECT ProductKey FROM WebProducts WHERE Id=%s LIMIT 1", (int(product_id),))
            row = cur.fetchone()
            product_label = str(row[0]) if row and row[0] else str(product_id)
            cur.execute(
                "SELECT Content FROM WebSystemPrompts WHERE Scope='product' AND ProductId=%s LIMIT 1",
                (int(product_id),),
            )
            prow = cur.fetchone()
            if prow and prow[0]:
                parts.append(f"\n\n## PRODUCT CONTEXT ({product_label})\n{str(prow[0]).strip()}\n")
        except Exception:
            pass

    # Role-scope prompt
    # Role 의 "전 Product 공통" prompt 는 fallback 이 아니라 항상 먼저 누적한다.
    # 특정 Product 를 선택했고 해당 Role×Product prompt 가 있으면 공통 지침 뒤에 추가한다.
    role_blocks: list[tuple[str, str]] = []
    role_common, _ = _fetch("role", "RoleId", role_id, prompt_product_id=None)
    if role_common:
        role_blocks.append(("전 Product 공통", role_common))
    if (not is_auto) and product_id and product_id > 0:
        role_specific, role_specific_label = _fetch(
            "role",
            "RoleId",
            role_id,
            prompt_product_id=int(product_id),
        )
        if role_specific:
            role_blocks.append((role_specific_label or f"ProductId={product_id}", role_specific))
    if role_blocks:
        role_label = ""
        try:
            cur.execute("SELECT RoleKey FROM WebRoles WHERE Id=%s LIMIT 1", (int(role_id or 0),))
            row = cur.fetchone()
            role_label = str(row[0]) if row and row[0] else str(role_id)
        except Exception:
            pass
        role_text = "\n\n".join(
            f"### {block_label}\n{block_content.strip()}" for block_label, block_content in role_blocks
        )
        parts.append(f"\n\n## ROLE GUIDANCE ({role_label})\n{role_text}\n")

    # Account-scope prompt
    # Account 의 "전 Product 공통" prompt 도 항상 먼저 누적한다. pinned Product 전용 개인 지침이
    # 있으면 그 뒤에 추가한다. 최종 사용자 요청은 이 system message 뒤의 user message 로 보존된다.
    account_blocks: list[tuple[str, str]] = []
    account_common, _ = _fetch("account", "AccountId", account_id, prompt_product_id=None)
    if account_common:
        account_blocks.append(("전 Product 공통", account_common))
    if (not is_auto) and product_id and product_id > 0:
        account_specific, account_specific_label = _fetch(
            "account",
            "AccountId",
            account_id,
            prompt_product_id=int(product_id),
        )
        if account_specific:
            account_blocks.append((account_specific_label or f"ProductId={product_id}", account_specific))
    if account_blocks:
        account_text = "\n\n".join(
            f"### {block_label}\n{block_content.strip()}" for block_label, block_content in account_blocks
        )
        parts.append(f"\n\n## ACCOUNT PREFERENCES\n{account_text}\n")

    try:
        cur.close()
    except Exception:
        pass

    # TASK-0094 Sprint 1 Phase 11: ATTACHED FILES section — env 의 ATTACHMENT_IDS
    # (comma separated) 로 caller 가 selected attachment_ids 전달. D16 정합:
    # 미지정/빈 list 면 본 section 미주입.
    try:
        import os as _os
        attachment_ids_raw = (_os.getenv("ATTACHMENT_IDS") or "").strip()
        if attachment_ids_raw:
            attachment_ids = [int(x) for x in attachment_ids_raw.split(",") if x.strip().lstrip("-").isdigit() and int(x) > 0]
            if attachment_ids:
                section = _build_attachment_context_section(mem_conn, attachment_ids)
                if section:
                    parts.append(section)
    except Exception:
        pass

    return "".join(parts)


# ══════════════════════════════════════════════════════════════════
#  지식 주입 (Knowledge Injection)
# ══════════════════════════════════════════════════════════════════

def _load_schema_list(mem_conn, max_total: int = 2000) -> str:
    """스키마별 테이블 수와 인사이트 DB의 도메인 설명을 로드한다."""
    if not mem_conn:
        return ""

    cur = mem_conn.cursor()
    parts: list[str] = []

    # 스키마별 테이블 수 집계
    schema_counts: dict[str, int] = {}
    try:
        cur.execute(
            "SELECT e.FactKey "
            "FROM AgentMemoryFactEntries e "
            "WHERE e.ConversationId = '__global__' "
            "  AND e.FactKey LIKE 'table_insight:%' "
            "ORDER BY e.FactKey",
        )
        rows = cur.fetchall() or []
        for (fact_key,) in rows:
            name = fact_key.replace("table_insight:", "")
            dot = name.find(".")
            if dot > 0:
                s = name[:dot]
                schema_counts[s] = schema_counts.get(s, 0) + 1
    except Exception:
        pass

    # 인사이트 DB에서 스키마 도메인 설명 로드
    schema_descs: dict[str, str] = {}
    try:
        cur.execute(
            "SELECT e.FactKey, LEFT(t.TextContent, 200) "
            "FROM AgentMemoryFactEntries e "
            "JOIN AgentMemoryTexts t ON e.TextHash = t.TextHash "
            "WHERE e.ConversationId = '__global__' "
            "  AND e.FactKey LIKE 'schema_insight:%' "
            "ORDER BY e.FactKey",
        )
        for fact_key, text_content in cur.fetchall() or []:
            schema_name = str(fact_key).replace("schema_insight:", "")
            if schema_name == "agent_memory":
                continue
            raw = str(text_content or "")
            # "domain:" 이후의 설명을 추출 (영어 인사이트 형식)
            desc = ""
            lower = raw.lower()
            if "domain:" in lower:
                idx = lower.index("domain:")
                after = raw[idx + len("domain:"):].strip()
                segments = after.split(" / ")
                if len(segments) >= 2:
                    desc = segments[0].strip() + " — " + segments[1].strip()[:80]
                else:
                    desc = segments[0].strip()[:100]
            elif " / " in raw:
                # 레거시 한국어 형식 폴백
                segments = raw.split(" / ")
                desc = segments[0].strip()[:100]
            schema_descs[schema_name] = desc
    except Exception:
        pass

    if schema_counts:
        parts.append("## Database schemas:")
        for schema, count in sorted(schema_counts.items()):
            desc = schema_descs.get(schema, "")
            desc_suffix = f" — {desc}" if desc else ""
            parts.append(f"- {schema} ({count} tables){desc_suffix}")
    elif schema_descs:
        parts.append("## Database schemas:")
        for schema, desc in sorted(schema_descs.items()):
            parts.append(f"- {schema}: {desc}")

    cur.close()
    return "\n".join(parts) if parts else ""


def _load_relevant_table_insights(mem_conn, user_message: str, max_items: int = 15) -> str:
    """사용자 메시지의 영어 키워드로 매칭되는 테이블 인사이트를 로드한다."""
    if not mem_conn or not user_message:
        return ""
    tokens = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_]{1,}", user_message.lower()))
    if not tokens:
        return ""
    cur = mem_conn.cursor()
    try:
        token_list = list(tokens)[:10]
        conditions = []
        params: list[str] = []
        for token in token_list:
            conditions.append("(e.FactKey LIKE %s OR t.TextContent LIKE %s)")
            like = f"%{token}%"
            params.extend([like, like])
        where_clause = " OR ".join(conditions)
        cur.execute(
            f"SELECT e.FactKey, LEFT(t.TextContent, 200) "
            f"FROM AgentMemoryFactEntries e "
            f"JOIN AgentMemoryTexts t ON e.TextHash = t.TextHash "
            f"WHERE e.ConversationId = '__global__' "
            f"  AND e.FactKey LIKE 'table_insight:%%' "
            f"  AND ({where_clause}) "
            f"ORDER BY e.FactKey LIMIT %s",
            params + [max_items],
        )
        rows = cur.fetchall() or []
        if not rows:
            return ""
        lines = []
        for fact_key, text in rows:
            table_ref = str(fact_key).replace("table_insight:", "")
            lines.append(f"- {table_ref}: {str(text or '').strip()}")
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        cur.close()


def _build_knowledge_context(mem_conn, user_message: str, history: list[dict]) -> str:
    """DB 지식(스키마 목록 + 관련 테이블 인사이트)을 구성한다.

    LLM이 이 섹션을 "authoritative"로 받아들이도록 헤더를 명시하고,
    관련 table_insight가 발견되면 곧바로 execute_sql로 진행하라는 힌트를 덧붙인다.
    """
    parts: list[str] = []
    schema_list = _load_schema_list(mem_conn)
    if schema_list:
        # 헤더를 "authoritative"로 격상하여 LLM이 여기부터 참조하도록 유도
        parts.append("## KNOWN SCHEMAS & TABLES (authoritative — prefer these over tool-based discovery)")
        parts.append(schema_list)
    table_insights = _load_relevant_table_insights(mem_conn, user_message)
    if table_insights:
        parts.append("\n## RELEVANT TABLES FOR THIS QUESTION")
        parts.append("Candidate tables already matched to the user's keywords. "
                     "Start with execute_sql against one of these instead of search_tables.")
        parts.append(table_insights)
    return "\n\n" + "\n".join(parts) + "\n" if parts else ""


# ══════════════════════════════════════════════════════════════════
#  메모리 관리 (대화 저장/로드)
# ══════════════════════════════════════════════════════════════════

def _connect_memory():
    return mysql.connector.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=MEMORY_DB, autocommit=True, charset="utf8mb4",
        connection_timeout=AGENT_TIMEOUT_SEC, use_unicode=True,
    )


def _ensure_memory_tables(conn):
    """에이전트 대화 테이블이 존재하는지 확인하고 없으면 생성."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS AgentCoreMessages (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            conversation_id VARCHAR(128) NOT NULL,
            role VARCHAR(20) NOT NULL,
            content LONGTEXT,
            tool_calls JSON DEFAULT NULL,
            tool_call_id VARCHAR(128) DEFAULT NULL,
            name VARCHAR(64) DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_conv (conversation_id, id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS AgentCoreConversations (
            conversation_id VARCHAR(128) PRIMARY KEY,
            topic VARCHAR(256) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cur.close()


def _parse_saved_tool_calls(raw_value: Any) -> list[dict[str, Any]]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _normalize_history_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    pending_tool_ids: set[str] = set()
    for row in rows:
        role = str(row.get("role") or "")
        raw_tool_calls = row.get("tool_calls")
        if role == "assistant" and raw_tool_calls:
            parsed_tool_calls = _parse_saved_tool_calls(raw_tool_calls)
            if not parsed_tool_calls:
                pending_tool_ids.clear()
                continue
            next_row = dict(row)
            next_row["_parsed_tool_calls"] = parsed_tool_calls
            normalized.append(next_row)
            pending_tool_ids = {
                str(item.get("id") or "").strip()
                for item in parsed_tool_calls
                if isinstance(item, dict) and str(item.get("id") or "").strip()
            }
            continue
        if role == "tool":
            tool_call_id = str(row.get("tool_call_id") or "").strip()
            if pending_tool_ids and tool_call_id and tool_call_id in pending_tool_ids:
                pending_tool_ids.discard(tool_call_id)
                normalized.append(row)
            continue
        pending_tool_ids.clear()
        normalized.append(row)
    return normalized


def _step_csv_paths(steps: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for step in steps:
        summary = step.get("result_summary")
        if not isinstance(summary, dict):
            continue
        for path in summary.get("csv_paths") or []:
            value = str(path or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            paths.append(value)
    return paths


def _summarize_step_rationale(steps: list[dict[str, Any]]) -> str:
    if not steps:
        return ""
    reasons: list[str] = []
    works: list[str] = []
    tables: set[str] = set()
    for step in steps:
        reason = str(step.get("reason") or "").strip()
        if reason and reason not in reasons:
            reasons.append(reason)
        work = str(step.get("work") or "").strip()
        if work and work not in works:
            works.append(work)
        sql_text = str(step.get("sql") or "").strip()
        for table in _extract_sql_tables(sql_text):
            tables.add(table)
    lines: list[str] = []
    if reasons:
        lines.append("단계별 근거:")
        lines.extend(f"{idx}. {reason}" for idx, reason in enumerate(reasons, 1))
    elif works:
        lines.append("수행 단계:")
        lines.extend(f"{idx}. {work}" for idx, work in enumerate(works, 1))
    if tables:
        if lines:
            lines.append("")
        lines.append("참고 테이블:")
        lines.append(", ".join(sorted(tables)))
    return "\n".join(lines).strip()


def _build_step_payload(
    run_id: str,
    step_index: int,
    tool_name: str,
    intent: str,
    args: dict[str, Any] | None,
    tool_result: str,
    work_text: str = "",
    work_source: str = "",
    reason_text: str = "",
    reason_source: str = "",
    error: str = "",
) -> dict[str, Any]:
    payload_args = args if isinstance(args, dict) else {}
    return {
        "step_index": int(step_index or 0),
        "action": "step",
        "tool": str(tool_name or ""),
        "intent": str(intent or "")[:255],
        "work": str(work_text or "").strip(),
        "work_source": str(work_source or "").strip(),
        "reason": str(reason_text or "").strip(),
        "reason_source": str(reason_source or "").strip(),
        "args": payload_args,
        "sql": str(payload_args.get("sql", "") or ""),
        "result_summary": _build_step_result_summary(tool_name, tool_result),
        "error": str(error or ""),
        "run_id": str(run_id or ""),
    }


def _load_conversation_messages(conn, conversation_id: str, max_messages: int = 50) -> list[dict]:
    """대화 메시지를 OpenAI 메시지 형식으로 로드."""
    raw_limit = max(int(max_messages or 50) * 4, 80)
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """SELECT id, role, content, tool_calls, tool_call_id, name
           FROM AgentCoreMessages
           WHERE conversation_id = %s
           ORDER BY id DESC LIMIT %s""",
        (conversation_id, raw_limit),
    )
    rows = cur.fetchall() or []
    cur.close()

    normalized_rows = _normalize_history_rows(list(reversed(rows)))
    if len(normalized_rows) > max_messages:
        normalized_rows = _normalize_history_rows(normalized_rows[-max_messages:])

    messages = []
    for row in normalized_rows:
        msg: dict[str, Any] = {"role": row["role"]}
        parsed_tool_calls = row.get("_parsed_tool_calls")
        if row["content"] and not parsed_tool_calls and not row.get("tool_calls"):
            msg["content"] = row["content"]
        if parsed_tool_calls:
            msg["tool_calls"] = parsed_tool_calls
        if row["tool_call_id"]:
            msg["tool_call_id"] = row["tool_call_id"]
        if row["name"]:
            msg["name"] = row["name"]
        messages.append(msg)
    return messages


def _save_message(conn, conversation_id: str, role: str,
                  content: str | None = None,
                  tool_calls: list | None = None,
                  tool_call_id: str | None = None,
                  name: str | None = None):
    """메시지를 DB에 저장."""
    cur = conn.cursor()
    tc_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None
    cur.execute(
        """INSERT INTO AgentCoreMessages
           (conversation_id, role, content, tool_calls, tool_call_id, name)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (conversation_id, role, content, tc_json, tool_call_id, name),
    )
    cur.close()


def _ensure_conversation(conn, conversation_id: str):
    cur = conn.cursor()
    cur.execute(
        """INSERT IGNORE INTO AgentCoreConversations (conversation_id)
           VALUES (%s)""",
        (conversation_id,),
    )
    cur.close()


def _update_conversation_topic(conn, conversation_id: str, topic: str):
    cur = conn.cursor()
    cur.execute(
        """UPDATE AgentCoreConversations SET topic = %s WHERE conversation_id = %s""",
        (topic[:256], conversation_id),
    )
    cur.close()


def _try_update_topic(conn, conversation_id: str, user_message: str, answer: str, history_len: int):
    """대화 주제를 설정/갱신한다.

    - 첫 메시지: user_message 앞 60자로 즉시 설정
    - 3번째 이후 메시지: LLM으로 토픽 생성 시도 (실패 시 무시)
    """
    try:
        if history_len == 0:
            # 첫 메시지 — 빠른 설정
            topic = user_message[:60]
        else:
            # 후속 메시지 — LLM 기반 토픽 갱신 (매 턴마다)
            payload = {
                "user_message": user_message[:200],
                "assistant_answer": answer[:200],
            }
            generated = llm_generate_topic(payload)
            if not generated or len(generated.strip()) < 2:
                return
            topic = generated.strip()
        _update_conversation_topic(conn, conversation_id, topic)
        save_memory_kv(conn, conversation_id, "topic", topic[:256])
    except Exception:
        pass


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]


def _ensure_web_conversation_metadata(conn, conversation_id: str, topic: str = PLACEHOLDER_TOPIC) -> None:
    try:
        if not load_memory_kv(conn, conversation_id, "created_at"):
            save_memory_kv(conn, conversation_id, "created_at", datetime.now(timezone.utc).isoformat())
        current_topic = str(load_memory_kv(conn, conversation_id, "topic") or "").strip()
        if topic and current_topic in ("", "(미설정)"):
            save_memory_kv(conn, conversation_id, "topic", topic[:256])
    except Exception:
        pass


def _mirror_message(
    conn,
    conversation_id: str,
    role: str,
    content: str,
    run_id: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    text = str(content or "").strip()
    if not text:
        return
    payload_meta = dict(meta) if isinstance(meta, dict) else {}
    if run_id and "run_id" not in payload_meta:
        payload_meta["run_id"] = run_id
    try:
        save_memory_message(conn, conversation_id, role, text, payload_meta or None)
    except Exception:
        pass


_MD_TABLE_ROW_RE = re.compile(r"^\|.*\|$")
_MD_TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]+\|$")
_TABLE_ROW_THRESHOLD = 5


def _collapse_large_tables(answer: str, csv_paths: list[str]) -> str:
    """답변 내 대형 마크다운 표를 미리보기 + CSV 링크로 치환."""
    if not answer or not csv_paths:
        return answer
    lines = answer.split("\n")
    result: list[str] = []
    i = 0
    csv_idx = 0
    while i < len(lines):
        line = lines[i].strip()
        if _MD_TABLE_ROW_RE.match(line):
            table_start = i
            table_lines: list[str] = [lines[i]]
            i += 1
            while i < len(lines) and _MD_TABLE_ROW_RE.match(lines[i].strip()):
                table_lines.append(lines[i])
                i += 1
            # 구분자 행 제외한 실제 데이터 행 수 세기
            data_rows = sum(
                1 for tl in table_lines
                if not _MD_TABLE_SEP_RE.match(tl.strip())
            )
            header_rows = 1  # 헤더
            body_rows = data_rows - header_rows
            if body_rows > _TABLE_ROW_THRESHOLD and csv_idx < len(csv_paths):
                # 헤더 + 구분자 + 미리보기 행(최대 3행) 유지
                kept: list[str] = []
                preview_count = 0
                for tl in table_lines:
                    if _MD_TABLE_SEP_RE.match(tl.strip()):
                        kept.append(tl)
                    elif preview_count <= _TABLE_ROW_THRESHOLD:
                        # 헤더(0) + 데이터(1~threshold)
                        kept.append(tl)
                        preview_count += 1
                    else:
                        break
                result.extend(kept)
                csv_path = csv_paths[csv_idx]
                result.append("")
                result.append(
                    f"📎 [전체 {body_rows}행 미리보기]"
                    f"(/api/file?path={csv_path})"
                )
                result.append("")
                csv_idx += 1
            else:
                result.extend(table_lines)
        else:
            result.append(lines[i])
            i += 1
    return "\n".join(result)


def _extract_csv_paths(text: str) -> list[str]:
    if not text:
        return []
    return [match.group(1) for match in CSV_PATH_RE.finditer(text)]


def _build_step_result_summary(tool_name: str, tool_result: str) -> dict[str, Any] | None:
    summary: dict[str, Any] = {}
    preview = str(tool_result or "").strip()
    if preview:
        summary["preview"] = preview[:500]
    csv_paths = _extract_csv_paths(tool_result)
    if csv_paths:
        summary["csv_paths"] = csv_paths
    if not summary:
        return None
    normalized = normalize_step_result_summary(tool_name, summary)
    return normalized if isinstance(normalized, dict) else summary


def _coerce_message_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    parts.append(text)
                continue
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                text = str(text or "").strip()
                if text:
                    parts.append(text)
                continue
            text = getattr(item, "text", "") or getattr(item, "content", "") or ""
            text = str(text or "").strip()
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
    return str(content).strip()


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    decoder = json.JSONDecoder()
    for idx, char in enumerate(raw):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(raw[idx:])
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _normalize_note_text(value: Any, max_len: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _extract_sql_tables(sql_text: str) -> list[str]:
    sql = str(sql_text or "")
    if not sql:
        return []
    seen: set[str] = set()
    tables: list[str] = []
    for schema, table in re.findall(r"(?:FROM|JOIN|UPDATE|INTO)\s+`?([A-Za-z0-9_]+)`?\.`?([A-Za-z0-9_]+)`?", sql, re.IGNORECASE):
        ref = f"{schema}.{table}"
        if ref in seen:
            continue
        seen.add(ref)
        tables.append(ref)
    return tables


def _derive_step_work(tool_name: str, args: dict[str, Any] | None = None, tool_result: str = "") -> str:
    payload = args if isinstance(args, dict) else {}
    tool = str(tool_name or "").strip().lower()
    if tool == "list_schemas":
        return "사용자 스키마 목록을 확인한다"
    if tool == "describe_schema":
        schema = str(payload.get("schema_name") or "").strip()
        return f"`{schema}` 스키마의 테이블 목록을 확인한다" if schema else "스키마의 테이블 목록을 확인한다"
    if tool == "describe_table":
        schema = str(payload.get("schema_name") or "").strip()
        table = str(payload.get("table_name") or "").strip()
        if schema and table:
            return f"`{schema}`.`{table}` 구조를 확인한다"
        if table:
            return f"`{table}` 테이블 구조를 확인한다"
        return "테이블 구조를 확인한다"
    if tool == "search_tables":
        keyword = str(payload.get("keyword") or "").strip()
        schema = str(payload.get("schema_name") or "").strip()
        if schema and keyword:
            return f"`{schema}`에서 `{keyword}` 관련 테이블을 찾는다"
        if keyword:
            return f"`{keyword}` 관련 테이블을 찾는다"
        return "관련 테이블을 찾는다"
    if tool == "get_sample_rows":
        schema = str(payload.get("schema_name") or "").strip()
        table = str(payload.get("table_name") or "").strip()
        try:
            limit = int(payload.get("limit") or 5)
        except Exception:
            limit = 5
        if schema and table:
            return f"`{schema}`.`{table}` 샘플 {limit}행을 확인한다"
        if table:
            return f"`{table}` 샘플 {limit}행을 확인한다"
        return "샘플 데이터를 확인한다"
    if tool == "get_table_indexes":
        schema = str(payload.get("schema_name") or "").strip()
        table = str(payload.get("table_name") or "").strip()
        if schema and table:
            return f"`{schema}`.`{table}` 인덱스를 확인한다"
        return "테이블 인덱스를 확인한다"
    if tool == "get_foreign_keys":
        schema = str(payload.get("schema_name") or "").strip()
        table = str(payload.get("table_name") or "").strip()
        if schema and table:
            return f"`{schema}`.`{table}` 외래키 관계를 확인한다"
        return "테이블 외래키 관계를 확인한다"
    if tool == "explain_query":
        return "SQL 실행 계획을 확인한다"
    if tool == "execute_sql":
        sql_text = str(payload.get("sql", "") or "").strip()
        tables = _extract_sql_tables(sql_text)
        target = ", ".join(tables[:2]) if tables else ""
        aggregate = bool(re.search(r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(|\bGROUP\s+BY\b", sql_text, re.IGNORECASE))
        if target and aggregate:
            return f"`{target}` 데이터를 집계한다"
        if target:
            return f"`{target}` 데이터를 조회한다"
        return "SQL을 실행한다"
    if tool_result:
        return f"`{tool_name}` 도구를 실행한다"
    return "단계를 수행한다"


def _parse_tool_notes(content: Any, expected_count: int) -> list[dict[str, str]]:
    count = max(0, int(expected_count or 0))
    payload = _extract_json_object(_coerce_message_text(content))
    notes: list[dict[str, str]] = []
    raw_notes = []
    if isinstance(payload, dict):
        if isinstance(payload.get("tool_notes"), list):
            raw_notes = payload.get("tool_notes") or []
        elif count == 1 and any(key in payload for key in ("work", "reason")):
            raw_notes = [payload]
    for item in raw_notes:
        if not isinstance(item, dict):
            notes.append({"work": "", "reason": ""})
            continue
        notes.append(
            {
                "work": _normalize_note_text(item.get("work"), 255),
                "reason": _normalize_note_text(item.get("reason"), 500),
            }
        )
    if count <= 0:
        return notes
    if len(notes) < count:
        notes.extend({"work": "", "reason": ""} for _ in range(count - len(notes)))
    return notes[:count]


def _delete_requested(conn, conversation_id: str) -> bool:
    try:
        return is_delete_requested(conn, conversation_id)
    except Exception:
        return False


def _writes_allowed(conn, conversation_id: str) -> bool:
    return not _delete_requested(conn, conversation_id)


def _cancel_requested_for_run(conn, conversation_id: str, run_id: str) -> bool:
    try:
        return _cancel_requested(conn, conversation_id, run_id)
    except Exception:
        return False


def _mirror_step(
    conn,
    conversation_id: str,
    run_id: str,
    step_index: int,
    tool_name: str,
    intent: str,
    args: dict[str, Any],
    tool_result: str,
    work_text: str = "",
    work_source: str = "",
    reason_text: str = "",
    reason_source: str = "",
    error: str = "",
) -> None:
    entry = _build_step_payload(
        run_id=run_id,
        step_index=step_index,
        tool_name=tool_name,
        intent=intent,
        args=args,
        tool_result=tool_result,
        work_text=work_text,
        work_source=work_source,
        reason_text=reason_text,
        reason_source=reason_source,
        error=error,
    )
    try:
        save_memory_step(conn, conversation_id, run_id, entry)
    except Exception:
        pass


def _list_conversations(conn, limit: int = 50) -> list[dict]:
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """SELECT conversation_id, topic, created_at, updated_at
           FROM AgentCoreConversations
           ORDER BY updated_at DESC LIMIT %s""",
        (limit,),
    )
    rows = cur.fetchall()
    cur.close()
    return rows


def _get_conversation_id(conv_file: str | None = None) -> str:
    """파일에서 대화 ID를 읽거나 새로 생성."""
    path = conv_file or os.getenv("AGENT_CONVERSATION_ID_FILE", "/shared/conversation_id")
    env_id = os.getenv("AGENT_CONVERSATION_ID", "").strip()
    if env_id:
        return env_id
    try:
        cid = open(path, "r").read().strip()
        if cid:
            return cid
    except FileNotFoundError:
        pass
    cid = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write(cid)
    except Exception:
        pass
    return cid


def _save_conversation_id(cid: str, conv_file: str | None = None):
    path = conv_file or os.getenv("AGENT_CONVERSATION_ID_FILE", "/shared/conversation_id")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write(cid)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
#  LLM 호출
# ══════════════════════════════════════════════════════════════════

def _model_supports_temperature(model: str) -> bool:
    return model_supports_temperature(model)


def _call_llm(client: OpenAI, messages: list[dict], model: str,
              temperature: float | None = None,
              tools: list[dict] | None = None) -> Any:
    """OpenAI API를 호출한다.

    TASK-0094 Sprint 2 (D13): vision 가능 모델 + env ATTACHMENT_IMAGE_INLINE_PATH
    가 가리키는 image_attachments JSON 이 있으면 messages_for_provider() 가 첫
    user message 에 image inline content-array 부착 (transient — DB string 불변).

    LiteLLM proxy (feature-0007) 가 OpenAI image_url → Anthropic Vision spec 으로
    자동 normalize. backend 는 OpenAI Chat Completions spec 만 사용.
    """
    image_attachments = _load_attachment_inline_images()
    effective_messages: list[dict] = messages_for_provider(
        messages,
        image_attachments=image_attachments or None,
        vision_model=model_supports_vision(model),
    )
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": effective_messages,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if tools:
        kwargs["tools"] = tools
    # 로컬 LLM만 max_tokens 제한 (reasoning 토큰 포함 보호)
    token_limit = max_tokens_for_model(model, "agent")
    if token_limit is not None:
        kwargs["max_tokens"] = token_limit
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message


# ══════════════════════════════════════════════════════════════════
#  로깅
# ══════════════════════════════════════════════════════════════════

def _log(category: str, data: dict):
    """로그를 파일에 기록."""
    try:
        log_dir = AGENT_LOG_DIR
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d")
        path = os.path.join(log_dir, f"{ts}_{category}.log")
        line = json.dumps(
            {"ts": datetime.now(timezone.utc).isoformat(), **data},
            ensure_ascii=False, default=str,
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
#  메인 에이전트 루프
# ══════════════════════════════════════════════════════════════════

def run_agent(
    user_message: str,
    conversation_id: str | None = None,
    conv_file: str | None = None,
    max_steps: int | None = None,
    model: str | None = None,
    api_key: str | None = None,
    temperature: float | None = None,
    output_mode: str = "console",  # "console" or "json"
    *,
    product_id: int | None = None,
    role_id: int | None = None,
    account_id: int | None = None,
    allowed_schemas: list[str] | None = None,
    product_mode: str = "pinned",
) -> dict[str, Any]:
    """Product whitelist 를 설정한 뒤 실제 에이전트 루프를 호출하는 얇은 래퍼."""
    set_active_schema_allowlist(allowed_schemas)
    try:
        return _run_agent_core(
            user_message,
            conversation_id=conversation_id,
            conv_file=conv_file,
            max_steps=max_steps,
            model=model,
            api_key=api_key,
            temperature=temperature,
            output_mode=output_mode,
            product_id=product_id,
            role_id=role_id,
            account_id=account_id,
            product_mode=product_mode,
        )
    finally:
        clear_active_schema_allowlist()


def _run_agent_core(
    user_message: str,
    conversation_id: str | None = None,
    conv_file: str | None = None,
    max_steps: int | None = None,
    model: str | None = None,
    api_key: str | None = None,
    temperature: float | None = None,
    output_mode: str = "console",
    *,
    product_id: int | None = None,
    role_id: int | None = None,
    account_id: int | None = None,
    product_mode: str = "pinned",
) -> dict[str, Any]:
    """에이전트 메인 루프.

    Args:
        user_message: 사용자 입력
        conversation_id: 대화 ID (None이면 파일에서 로드/생성)
        conv_file: 대화 ID 파일 경로
        max_steps: 최대 도구 호출 횟수
        model: LLM 모델명
        api_key: OpenAI API 키
        temperature: legacy 입력값. 현재는 내부 규칙으로만 처리
        output_mode: "console"이면 Rich 출력, "json"이면 결과 딕셔너리만 반환
        product_id/role_id/account_id: 시스템 프롬프트 depth 조립에 사용되는 현재 컨텍스트 식별자
        allowed_schemas: None 이면 whitelist 미적용, list 이면 해당 스키마만 도구가 접근 허용

    Returns:
        {"answer": str, "conversation_id": str, "steps": list, "sql": str, "error": str}
    """
    if max_steps is None:
        max_steps = AGENT_MAX_STEPS
    if model is None:
        model = OPENAI_MODEL
    # feature-0007 (REQ-20260521-0001): per-request api_key 인자는 deprecated.
    # API Vault 폐기 후 모든 LLM 호출은 env 단일 소스 (config.py 의 `LLM_API_KEY`
    # / `LLM_BASE_URL` — BEDROCK_GATEWAY_* fallback chain) 를 따른다. 인자가
    # 들어와도 무시 (signature 는 backward-compat 위해 유지).
    _ = api_key  # explicit ignore — silence linter
    temperature = 0.0 if _model_supports_temperature(model) else None

    result: dict[str, Any] = {
        "answer": "",
        "conversation_id": "",
        "steps": [],
        "executed_sql": "",
        "result_csv_paths": [],
        "rationale": "",
        "error": "",
    }

    # ── LLM 클라이언트 초기화 (feature-0007 단일 env 경로) ──
    if not OpenAI:
        result["error"] = "openai 패키지를 찾을 수 없습니다."
        return result
    if not LLM_API_KEY:
        result["error"] = (
            "LLM 자격증명이 설정되지 않았습니다. "
            "BEDROCK_GATEWAY_API_KEY (권장) / LOCAL_LLM_API_KEY / OPENAI_API_KEY "
            "중 하나가 .env 에 채워져야 합니다."
        )
        return result
    client_kwargs: dict[str, Any] = {"api_key": LLM_API_KEY}
    if LLM_BASE_URL:
        client_kwargs["base_url"] = LLM_BASE_URL
    client = OpenAI(
        **client_kwargs,
        timeout=max(5, int(AGENT_TIMEOUT_SEC)),
        max_retries=max(0, int(AGENT_OPENAI_MAX_RETRIES)),
    )

    # ── 대화 ID 관리 ──
    cid = conversation_id or _get_conversation_id(conv_file)
    result["conversation_id"] = cid
    run_id = _new_run_id()
    cfg.CURRENT_RUN_ID = run_id
    canceled_by_user = False

    # ── DB 연결 ──
    try:
        ensure_memory_schema()
        mem_conn = _connect_memory()
        _ensure_memory_tables(mem_conn)
        cleanup_pending_delete_conversations(mem_conn)
        _ensure_conversation(mem_conn, cid)
        _ensure_web_conversation_metadata(mem_conn, cid)
        if _delete_requested(mem_conn, cid):
            delete_conversation_records(mem_conn, cid)
            cfg.CURRENT_RUN_ID = ""
            result["error"] = "삭제 요청된 대화입니다."
            return result
    except Exception as e:
        cfg.CURRENT_RUN_ID = ""
        result["error"] = f"메모리 DB 연결 실패: {e}"
        if output_mode == "console":
            console.print(Panel.fit(result["error"], title="오류"))
        return result

    try:
        db_conn = connect_with_retry(database=DB_CONNECT_DB, autocommit=True)
    except Exception as e:
        # DB 연결 실패 시 연결 없이 진행 (도구에서 개별 처리)
        db_conn = None
        try:
            db_conn = connect_with_retry(database=None, autocommit=True)
        except Exception:
            cfg.CURRENT_RUN_ID = ""
            result["error"] = f"DB 연결 실패: {e}"
            if output_mode == "console":
                console.print(Panel.fit(result["error"], title="오류"))
            return result

    # ── 대화 히스토리 로드 ──
    history = _load_conversation_messages(mem_conn, cid, max_messages=50)

    # ── 사용자 메시지 저장 ──
    if _writes_allowed(mem_conn, cid):
        _save_message(mem_conn, cid, "user", content=user_message)
        _mirror_message(mem_conn, cid, "user", user_message, run_id)
    try:
        save_memory_kv(mem_conn, cid, "last_run_id", run_id)
        set_run_status(mem_conn, cid, "processing", run_id=run_id)
    except Exception:
        pass

    # ── 대화 맥락 관리 (3-state: shift / evolve / continue) ──
    prev_origin = str(load_memory_kv(mem_conn, cid, "origin_request") or "").strip()
    thread_goal = str(load_memory_kv(mem_conn, cid, "thread_goal") or "").strip()
    origin_shift_type = _should_refresh_origin_request(prev_origin, user_message, None)

    if origin_shift_type == "shift":
        # Full topic shift: reset origin + thread_goal.
        save_memory_kv(mem_conn, cid, "origin_request", user_message)
        new_goal = _derive_topic(user_message, max_len=200)
        save_memory_kv(mem_conn, cid, "thread_goal", new_goal)
        thread_goal = new_goal
        prev_origin = user_message
    elif origin_shift_type == "evolve":
        # Goal evolution within same domain: update thread_goal only.
        new_goal = _derive_topic(user_message, max_len=200)
        save_memory_kv(mem_conn, cid, "thread_goal", new_goal)
        thread_goal = new_goal
    else:
        # continue: no changes to origin or thread_goal.
        if not prev_origin:
            save_memory_kv(mem_conn, cid, "origin_request", user_message)
            prev_origin = user_message
        if not thread_goal and prev_origin:
            thread_goal = _derive_topic(prev_origin, max_len=200)
            save_memory_kv(mem_conn, cid, "thread_goal", thread_goal)

    # ── 지식 주입 ──
    knowledge_ctx = ""
    try:
        knowledge_ctx = _build_knowledge_context(mem_conn, user_message, history)
    except Exception:
        pass

    # ── LLM 메시지 구성 ──
    try:
        system_content = compose_system_prompt(
            mem_conn,
            product_id=product_id,
            role_id=role_id,
            account_id=account_id,
            product_mode=product_mode,
        )
    except Exception:
        system_content = SYSTEM_PROMPT
    # Inject conversation context (origin_request + thread_goal)
    if prev_origin or thread_goal:
        ctx_parts: list[str] = []
        if prev_origin:
            ctx_parts.append(f"- Original user request (origin): {prev_origin}")
        if thread_goal:
            ctx_parts.append(f"- Current thread goal: {thread_goal}")
        system_content += "\n\n## CONVERSATION CONTEXT\n" + "\n".join(ctx_parts) + "\n"
        system_content += "Use the thread_goal as the authoritative reference for what the user is trying to achieve when context is ambiguous.\n"
    if knowledge_ctx:
        system_content += knowledge_ctx
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_content},
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    if output_mode == "console":
        console.print(f"\n[dim]대화: {cid[:20]}... | 모델: {model}[/dim]")

    # ── 에이전트 루프 ──
    run_start = time.perf_counter()
    run_timeout_sec = max(
        AGENT_TIMEOUT_SEC * 3,
        max(1, int(cfg.AGENT_EARLY_FINALIZE_MS / 1000)),
    )
    last_sql = ""
    steps: list[dict[str, Any]] = []
    step_count = 0
    empty_retries = 0

    while step_count < max_steps:
        if _cancel_requested_for_run(mem_conn, cid, run_id):
            canceled_by_user = True
            break
        elapsed = time.perf_counter() - run_start
        if elapsed > run_timeout_sec:  # 실행 예산을 넘기면 루프를 중단한다.
            result["error"] = "타임아웃으로 종료되었습니다."
            if output_mode == "console":
                console.print(f"[yellow]{result['error']}[/yellow]")
            break

        # ── 즉시 답변 요청 감지 ──
        finalize_now = _finalize_requested(mem_conn, cid, run_id)
        if finalize_now:
            _clear_finalize_request(mem_conn, cid)
            messages.append({
                "role": "system",
                "content": "User requested immediate answer. Write your final answer now based on information collected so far. No more tool calls. Answer in Korean Markdown.",
            })
            if output_mode == "console":
                console.print("[yellow]즉시 답변 요청 감지 — 마무리 중...[/yellow]")

        # ── LLM 호출 ──
        use_tools = None if finalize_now else TOOL_DEFINITIONS
        try:
            response_message = _call_llm(
                client, messages, model,
                temperature=temperature,
                tools=use_tools,
            )
        except Exception as e:
            error_msg = f"LLM 호출 오류: {e}"
            result["error"] = error_msg
            if output_mode == "console":
                console.print(Panel.fit(error_msg, title="오류"))
            break

        if _cancel_requested_for_run(mem_conn, cid, run_id):
            canceled_by_user = True
            break

        # ── 응답 처리 ──
        tool_calls = getattr(response_message, "tool_calls", None)

        if not tool_calls:
            # LLM이 텍스트로 응답 — 최종 답변
            raw_answer = getattr(response_message, "content", "") or ""
            # reasoning만 있고 content가 비어있으면 reasoning을 사용
            if not raw_answer.strip():
                reasoning = getattr(response_message, "reasoning", None) or getattr(response_message, "reasoning_content", None) or ""
                if reasoning and len(reasoning) > 20:
                    raw_answer = reasoning
                elif step_count > 0 and empty_retries < 3:
                    empty_retries += 1
                    messages.append({
                        "role": "user",
                        "content": "Write your answer in Korean Markdown based on the tool results above.",
                    })
                    continue
            # 대형 표 → CSV 링크 후처리
            all_csv = _step_csv_paths(steps)
            answer = _collapse_large_tables(raw_answer, all_csv) if all_csv else raw_answer
            result["answer"] = answer

            # 메시지 저장 (duration_ms 포함)
            answer_duration_ms = round((time.perf_counter() - run_start) * 1000.0, 2)
            # TASK-0094 Sprint 2 (S2.6, D9 정합) — vision invoke 의 결과 메시지에
            # attachment_derived flag 부여. share view 의 D9 redact 가 본 flag 를
            # 검사 (`_meta_has_attachment_derived`) — vision 분석 결과도 자동
            # cover. WebAttachmentDerivedMessages join row INSERT (D19) 는 caller
            # (app.py /api/ask, S2.6) 책임.
            mirror_meta: dict[str, Any] = {"duration_ms": answer_duration_ms}
            if os.getenv(_INLINE_IMAGE_ENV_VAR, "").strip():
                mirror_meta["attachment_derived"] = True
                mirror_meta["derivation_type"] = "vision_analysis"
            if _writes_allowed(mem_conn, cid):
                _save_message(mem_conn, cid, "assistant", content=answer)
                _mirror_message(mem_conn, cid, "assistant", answer, run_id,
                                meta=mirror_meta)

            # 대화 주제 자동 설정/갱신
            if answer and _writes_allowed(mem_conn, cid):
                _try_update_topic(mem_conn, cid, user_message, answer, len(history))

            if output_mode == "console":
                console.print()
                try:
                    console.print(Markdown(answer))
                except Exception:
                    console.print(answer)

            _log("agent_run", {
                "conversation_id": cid,
                "request": user_message[:200],
                "steps": step_count,
                "elapsed_sec": round(time.perf_counter() - run_start, 2),
                "model": model,
            })
            break

        # ── 도구 호출 처리 ──
        if len(tool_calls) > 3:
            tool_calls = tool_calls[:3]
        # assistant 메시지를 히스토리에 추가 (tool_calls 포함)
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": None}
        tc_list = []
        for note_idx, tc in enumerate(tool_calls):
            tc_list.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            })
        tool_notes = _parse_tool_notes(getattr(response_message, "content", None), len(tc_list))
        note_payload = json.dumps({"tool_notes": tool_notes}, ensure_ascii=False) if tool_notes else None
        assistant_msg["tool_calls"] = tc_list
        if note_payload:
            assistant_msg["content"] = note_payload
        messages.append(assistant_msg)

        # 도구 호출 저장
        if _writes_allowed(mem_conn, cid):
            _save_message(
                mem_conn, cid, "assistant",
                content=note_payload,
                tool_calls=tc_list,
            )

        # 각 도구 실행
        abort_loop = False
        for note_idx, tc in enumerate(tool_calls):
            if _cancel_requested_for_run(mem_conn, cid, run_id):
                canceled_by_user = True
                abort_loop = True
                break
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                tool_args = {}
            note = tool_notes[note_idx] if note_idx < len(tool_notes) else {}
            work_text = str((note or {}).get("work") or "").strip()
            reason_text = str((note or {}).get("reason") or "").strip()
            work_source = "llm" if work_text else ""
            reason_source = "llm" if reason_text else ""
            if not work_text:
                work_text = _derive_step_work(tool_name, tool_args)
                work_source = "derived" if work_text else ""

            step_count += 1
            if output_mode == "console":
                args_preview = json.dumps(tool_args, ensure_ascii=False)
                if len(args_preview) > 200:
                    args_preview = args_preview[:200] + "..."
                console.print(f"  [cyan]→ {tool_name}[/cyan]({args_preview})")

            # SQL 로깅
            if tool_name == "execute_sql":
                last_sql = tool_args.get("sql", "")

            # 도구 실행
            tool_result = execute_tool(db_conn, tool_name, tool_args)

            if _cancel_requested_for_run(mem_conn, cid, run_id):
                canceled_by_user = True
                abort_loop = True
                break

            # 결과가 너무 길면 잘라내기
            if len(tool_result) > 4000:
                tool_result = tool_result[:4000] + "\n... (truncated)"

            # 결과 메시지 추가
            tool_msg = {
                "role": "tool",
                "content": tool_result,
                "tool_call_id": tc.id,
            }
            messages.append(tool_msg)

            # 도구 결과 저장
            if _writes_allowed(mem_conn, cid):
                _save_message(
                    mem_conn, cid, "tool",
                    content=tool_result[:4000],  # 저장 시 길이 제한
                    tool_call_id=tc.id,
                    name=tool_name,
                )

            # Intent: 첫 step만 원본 요청, 이후는 도구명 기반 요약
            step_intent = user_message if step_count == 1 else f"{tool_name}: {work_text or tool_name}"
            step_info = _build_step_payload(
                run_id=run_id,
                step_index=step_count,
                tool_name=tool_name,
                intent=step_intent,
                args=tool_args,
                tool_result=tool_result,
                work_text=work_text,
                work_source=work_source,
                reason_text=reason_text,
                reason_source=reason_source,
            )
            step_info["result_length"] = len(tool_result)
            step_info["result_preview"] = tool_result[:300]
            steps.append(step_info)
            if _writes_allowed(mem_conn, cid):
                _mirror_step(
                    mem_conn,
                    cid,
                    run_id,
                    step_count,
                    tool_name,
                    step_intent,
                    tool_args,
                    tool_result,
                    work_text=work_text,
                    work_source=work_source,
                    reason_text=reason_text,
                    reason_source=reason_source,
                )

            _log("tool_call", {
                "conversation_id": cid,
                "tool": tool_name,
                "args": tool_args,
                "result_length": len(tool_result),
                "step": step_count,
            })
        if abort_loop:
            break

    else:
        # max_steps 초과
        result["answer"] = f"최대 도구 호출 횟수({max_steps})를 초과했습니다."
        if _writes_allowed(mem_conn, cid):
            _save_message(mem_conn, cid, "assistant", content=result["answer"])
            _mirror_message(mem_conn, cid, "assistant", result["answer"], run_id)
        if output_mode == "console":
            console.print(f"[yellow]{result['answer']}[/yellow]")

    result["steps"] = steps
    result["executed_sql"] = last_sql
    result["result_csv_paths"] = _step_csv_paths(steps)
    result["rationale"] = _summarize_step_rationale(steps)
    duration_ms = round((time.perf_counter() - run_start) * 1000.0, 2)
    pending_delete = _delete_requested(mem_conn, cid)

    if canceled_by_user:
        result["error"] = "요청이 취소되었습니다."
        try:
            _clear_cancel_request(mem_conn, cid)
        except Exception:
            pass
        if pending_delete:
            try:
                delete_conversation_records(mem_conn, cid)
            except Exception:
                pass
        else:
            try:
                if _writes_allowed(mem_conn, cid):
                    set_run_status(mem_conn, cid, "canceled", run_id=run_id, duration_ms=duration_ms, error="")
            except Exception:
                pass
    elif pending_delete:
        try:
            delete_conversation_records(mem_conn, cid)
        except Exception:
            pass
    elif result["error"]:
        error_text = f"오류: {result['error']}"
        _save_message(mem_conn, cid, "assistant", content=error_text)
        _mirror_message(mem_conn, cid, "assistant", error_text, run_id, meta={"internal": False})
        try:
            set_run_status(mem_conn, cid, "error", run_id=run_id, duration_ms=duration_ms, error=result["error"])
        except Exception:
            pass
    else:
        try:
            set_run_status(mem_conn, cid, "done", run_id=run_id, duration_ms=duration_ms, error="")
        except Exception:
            pass
    if not pending_delete and not canceled_by_user:
        try:
            _clear_cancel_request(mem_conn, cid)
        except Exception:
            pass

    # DB 연결 정리
    try:
        if db_conn:
            db_conn.close()
    except Exception:
        pass
    try:
        mem_conn.close()
    except Exception:
        pass
    cfg.CURRENT_RUN_ID = ""

    return result


# ══════════════════════════════════════════════════════════════════
#  대화 관리 유틸리티 (CLI/Web에서 사용)
# ══════════════════════════════════════════════════════════════════

def list_all_conversations() -> list[dict]:
    """모든 대화 목록을 반환."""
    try:
        conn = _connect_memory()
        _ensure_memory_tables(conn)
        result = _list_conversations(conn)
        conn.close()
        return result
    except Exception:
        return []


def create_new_conversation(conv_file: str | None = None) -> str:
    """새 대화를 생성하고 ID를 반환."""
    cid = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
    _save_conversation_id(cid, conv_file)
    try:
        ensure_memory_schema()
        conn = _connect_memory()
        _ensure_memory_tables(conn)
        _ensure_conversation(conn, cid)
        _ensure_web_conversation_metadata(conn, cid, PLACEHOLDER_TOPIC)
        conn.close()
    except Exception:
        pass
    return cid


def clear_conversation(conversation_id: str):
    """대화의 모든 메시지를 삭제."""
    try:
        conn = _connect_memory()
        delete_conversation_records(conn, conversation_id)
        conn.close()
    except Exception:
        pass


def get_conversation_messages(conversation_id: str, limit: int = 100) -> list[dict]:
    """대화 메시지를 반환 (Web UI용)."""
    try:
        conn = _connect_memory()
        _ensure_memory_tables(conn)
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """SELECT id, role, content, tool_calls, tool_call_id, name, created_at
               FROM AgentCoreMessages
               WHERE conversation_id = %s
               ORDER BY id ASC LIMIT %s""",
            (conversation_id, limit),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = []
        for row in rows:
            msg = {
                "id": row["id"],
                "role": row["role"],
                "content": "" if row["tool_calls"] else (row["content"] or ""),
                "created_at": str(row["created_at"]) if row["created_at"] else "",
            }
            if row["tool_calls"]:
                try:
                    msg["tool_calls"] = json.loads(row["tool_calls"])
                except Exception:
                    pass
            if row["tool_call_id"]:
                msg["tool_call_id"] = row["tool_call_id"]
            if row["name"]:
                msg["name"] = row["name"]
            result.append(msg)
        return result
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════
#  메모리 초기화 (--init-memory)
# ══════════════════════════════════════════════════════════════════

def init_memory():
    """메모리 테이블 생성. Docker memory-init 서비스에서 호출.

    TASK-0015 §2.1.3 M2 (TASK-0019, outside-voice Blocker B-2 해소): KB Postgres
    pgvector schema 도 동일 service 안에서 1회 적용. `_pg_available()` 가 True
    (postgres 컨테이너 가동 + AGENT_KB_PG_* 환경변수 정합) 일 때만 호출. False 면
    silent skip — postgres 미가동 환경 (M0 단계 또는 .env 미설정) 에서도 mysql
    초기화 진행. KB Postgres schema 적용은 멱등 (IF NOT EXISTS / DO $$ guard) 이라
    매 boot 마다 재호출 안전. `_ensure_pg_schema()` 의 has_table_privilege() 검증
    query 가 grant 정합도 함께 확인 (Blocker B-3 해소).
    """
    try:
        conn = _connect_memory()
        _ensure_memory_tables(conn)
        console.print("[green]메모리 테이블 초기화 완료[/green]")
        conn.close()
    except Exception as e:
        console.print(f"[red]메모리 초기화 실패: {e}[/red]")
        sys.exit(1)

    # KB Postgres schema 적용 (M2+ 자동 trigger)
    # outside-voice REV-20260520-0007 Critical: `AGENT_KB_PG_REQUIRED=1` 시 광역
    # 예외도 fail-loud. M2-b dual-write 활성 시 .env 에 본 변수 1 으로 설정 — 그 후
    # KB Postgres 가 dual-write 의 필수 의존성. M0~M2-a 까지는 default 0 (optional).
    import os as _os
    _pg_required = (_os.getenv("AGENT_KB_PG_REQUIRED", "0").strip() or "0") in {"1", "true", "yes", "on"}
    try:
        from .modules.db import _pg_available
        if _pg_available():
            from .modules.memory import _ensure_pg_schema
            result = _ensure_pg_schema()
            console.print(
                f"[green]KB Postgres schema 적용 완료[/green]: "
                f"tables={result.get('tables_present', [])}, "
                f"view={result.get('view_present', False)}, "
                f"extensions={result.get('extensions', [])}, "
                f"grants={result.get('grants_present', {})}"
            )
        elif _pg_required:
            console.print("[red]AGENT_KB_PG_REQUIRED=1 이지만 _pg_available() == False — fail-loud[/red]")
            sys.exit(1)
        else:
            console.print("[yellow]KB Postgres 미가동 — schema 적용 skip (M0~M2-a 단계, AGENT_KB_PG_REQUIRED=0)[/yellow]")
    except RuntimeError as e:
        # _pg_available() True 이지만 connection / schema 적용 실패 — fail-loud
        console.print(f"[red]KB Postgres schema 적용 실패: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        # M0~M2-a 단계 (AGENT_KB_PG_REQUIRED=0) 에서는 광역 예외 graceful — agent 부트 진행.
        # M2-b 이후 (AGENT_KB_PG_REQUIRED=1) 에서는 fail-loud — dual-write 깨진 schema 위에서 시작 차단.
        if _pg_required:
            console.print(f"[red]KB Postgres schema 적용 실패 (AGENT_KB_PG_REQUIRED=1): {e}[/red]")
            sys.exit(1)
        console.print(f"[yellow]KB Postgres schema 적용 중 예외 (계속 진행, AGENT_KB_PG_REQUIRED=0): {e}[/yellow]")


# ══════════════════════════════════════════════════════════════════
#  CLI 진입점
# ══════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="mysql_ai DBA Agent")
    parser.add_argument("query", nargs="?", default="", help="자연어 질의")
    parser.add_argument("--init-memory", action="store_true", help="메모리 테이블 초기화")
    parser.add_argument("--insight-worker", action="store_true", help="인사이트 워커 실행")
    parser.add_argument("--list-conversations", action="store_true", help="대화 목록")
    parser.add_argument("--new-conversation", action="store_true", help="새 대화 생성")
    parser.add_argument("--use-conversation-index", type=int, default=None, help="대화 전환")
    parser.add_argument("--delete-conversation-index", type=int, default=None, help="대화 삭제")
    parser.add_argument("--rename-conversation-index", type=int, default=None, help="대화 이름 변경")
    parser.add_argument("--rename-topic", type=str, default=None, help="새 대화 주제")
    parser.add_argument("--repl", action="store_true", help="대화형 REPL 모드")
    parser.add_argument("--model", type=str, default=None, help="LLM 모델")
    parser.add_argument("--no-exec", action="store_true", help="SQL 실행 없이 계획만")
    args = parser.parse_args()

    if args.init_memory:
        init_memory()
        return

    if args.insight_worker:
        # 기존 인사이트 워커를 그대로 사용
        try:
            from modules.insight import run_insight_worker_loop
            run_insight_worker_loop()
        except ImportError:
            console.print("[yellow]인사이트 워커를 찾을 수 없습니다.[/yellow]")
        return

    if args.list_conversations:
        convos = list_all_conversations()
        if not convos:
            console.print("대화가 없습니다.")
        else:
            for i, c in enumerate(convos, 1):
                topic = c.get("topic") or "(주제 없음)"
                created = str(c.get("created_at", ""))[:19]
                console.print(f"  [{i}] {topic}  ({created})")
        return

    if args.new_conversation:
        cid = create_new_conversation()
        console.print(f"새 대화: {cid}")
        return

    if args.use_conversation_index is not None:
        convos = list_all_conversations()
        idx = args.use_conversation_index - 1
        if 0 <= idx < len(convos):
            cid = convos[idx]["conversation_id"]
            _save_conversation_id(cid)
            console.print(f"대화 전환: {cid}")
            if args.query:
                run_agent(args.query, conversation_id=cid, model=args.model)
        else:
            console.print(f"유효하지 않은 인덱스: {args.use_conversation_index}")
        return

    if args.delete_conversation_index is not None:
        convos = list_all_conversations()
        idx = args.delete_conversation_index - 1
        if 0 <= idx < len(convos):
            cid = convos[idx]["conversation_id"]
            clear_conversation(cid)
            console.print(f"대화 삭제: {cid}")
        else:
            console.print(f"유효하지 않은 인덱스: {args.delete_conversation_index}")
        return

    if args.rename_conversation_index is not None and args.rename_topic:
        convos = list_all_conversations()
        idx = args.rename_conversation_index - 1
        if 0 <= idx < len(convos):
            cid = convos[idx]["conversation_id"]
            try:
                conn = _connect_memory()
                _update_conversation_topic(conn, cid, args.rename_topic)
                conn.close()
                console.print(f"대화 주제 변경: {args.rename_topic}")
            except Exception as e:
                console.print(f"주제 변경 실패: {e}")
        else:
            console.print(f"유효하지 않은 인덱스: {args.rename_conversation_index}")
        return

    if args.query and args.query.strip() == "__CLEAR_MEMORY_TABLES__":
        try:
            conn = _connect_memory()
            _ensure_memory_tables(conn)
            processing_ids = set(list_processing_conversation_ids(conn))
            preserve_ids = set(AGENT_MEMORY_CLEAR_KEEP_IDS) | processing_ids
            deleted_count = delete_all_conversations(conn, preserve_ids=preserve_ids)
            conn.close()
            console.print(f"[green]대화 삭제 완료: {deleted_count}건[/green]")
        except Exception as e:
            console.print(f"초기화 실패: {e}")
        return

    if args.repl:
        console.print("[bold]mysql_ai DBA Agent[/bold] — 종료: exit/quit")
        console.print()
        cid = _get_conversation_id()
        while True:
            try:
                query = input("질문> ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n종료합니다.")
                break
            if not query or query.lower() in ("exit", "quit", "q"):
                if query.lower() in ("exit", "quit", "q"):
                    console.print("종료합니다.")
                break
            if query.lower() == "/new":
                cid = create_new_conversation()
                console.print(f"[green]새 대화: {cid}[/green]")
                continue
            if query.lower() == "/list":
                convos = list_all_conversations()
                for i, c in enumerate(convos, 1):
                    topic = c.get("topic") or "(주제 없음)"
                    console.print(f"  [{i}] {topic}")
                continue
            run_agent(query, conversation_id=cid, model=args.model)
        return

    if not args.query:
        parser.print_help()
        return

    run_agent(args.query, model=args.model)


if __name__ == "__main__":
    main()
