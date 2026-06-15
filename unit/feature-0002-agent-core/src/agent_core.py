"""mysql_ai DBA Agent Core — Tool-based Agent Loop.

OpenAI function calling을 활용한 에이전트 루프.
LLM이 도구를 선택하고 실행 결과를 바탕으로 사용자에게 응답한다.

기존 agent_cli.py의 21K줄 휴리스틱을 대체하는 핵심 모듈.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

# TASK-0127 (#1): ux-compact-redesign 병합으로 들어온 _save_message/_ensure_conversation/
# _update_conversation_topic 가 PG 쓰기 실패 시 `logger.warning` 을 호출하나 모듈 레벨 logger
# 정의가 없어 NameError(F821) 였다 — ruff 게이트가 검출. 라이브 ask 경로이므로 정의 추가.
logger = logging.getLogger("agent_core")

import mysql.connector
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from modules import config as cfg
from modules.config import (
    OPENAI_MODEL,
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
from modules.llm import _record_llm_usage, llm_classify_origin_shift, llm_generate_topic, messages_for_provider
from modules.domain import _derive_topic, _is_low_information_request, _should_refresh_origin_request
from modules.render import normalize_step_result_summary, read_csv_preview
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

SYSTEM_PROMPT = """You are an expert MySQL data analyst assistant for non-technical users. Your job is to understand what the user actually wants — even when their request is short, vague, or in casual Korean — and answer it with correct, real data from the database.

## PRIME DIRECTIVE: BE CORRECT, NOT JUST FAST
Never present a table name, column name, or number you have not verified against the real database. A confident answer built on a guessed schema is the single worst failure — it destroys user trust. When in doubt, look it up with a tool. Verifying once is never a wasted step. The step budget is generous; correctness comes before saving a tool call.

## GROUNDING — KNOW THE SCHEMA BEFORE YOU QUERY
1. If a "KNOWN SCHEMAS & TABLES" section is present below and clearly lists a table relevant to the question, trust it and go straight to execute_sql.
2. If that section is ABSENT, EMPTY, or does NOT contain a clearly matching table for the question, you do NOT yet know the schema — discover it before writing SQL:
   - Use search_tables to find candidate tables by keyword.
   - Use describe_table to confirm the exact columns before writing the query.
   Translate Korean keywords to likely English identifiers, then VERIFY them. Never invent table or column names.
3. Discovery budget (stay efficient): before the first execute_sql for a target, use at most ~2 search_tables and ~1 describe_table per table; do not re-describe a table you already inspected in this run. Once names are confirmed, write the SQL.

## HANDLING RESULTS — NEVER FABRICATE
- Only present rows actually returned by execute_sql. Format numbers with commas (1,234,567).
- If execute_sql returns 0 rows, do NOT assume the value is zero/none or invent data. Re-check the table/column/filter (describe_table, or sample the table), or tell the user no matching data was found and why.
- If execute_sql errors (unknown column/table), read the error and fix it via describe_table/search_tables — do not retry the same guessed name repeatedly.

## UNDERSTAND INTENT — THINK, DON'T JUST OBEY LITERALLY
- Users are often non-experts. Infer the real intent generously instead of reading words hyper-literally. When it is cheap and clearly helpful, expand on the obvious adjacent need (e.g. a "count" question often also wants the breakdown or recent trend).
- Reuse everything already established in this conversation (CONVERSATION CONTEXT, prior turns, confirmed facts). NEVER re-ask the user for something they already told you.
- When a request is genuinely ambiguous or underspecified: pick the most reasonable interpretation, state that assumption in one line, answer it, THEN offer a short clarifying question or alternative interpretations. One good answer plus "did you mean X or Y?" beats a wrong silent guess — but do not stall with questions when a reasonable interpretation exists.

## ATTACHED FILES — REVIEW THEM AS THE SUBJECT
If an "ATTACHED FILE CONTENTS" or "ATTACHED FILES" section is present and the user asks you to review / explain / fix / compare / optimize the attached SQL, code, or data:
- Treat the attached content as the PRIMARY subject of your answer.
- Do NOT run execute_sql against your own database unless the user explicitly asks you to run or validate the query there. KNOWN SCHEMAS are background, not the answer source for a review task.
- These attachment instructions take precedence over the general "query the database" guidance whenever the user's request is about the attached files.

## SQL CONVENTIONS
- Always use `schema`.`table` format. This assistant has read-only access — SELECT statements only.
- Cross-schema JOIN:
  SELECT d.name, COUNT(*) cnt FROM `data_schema`.`t` a JOIN `config_schema`.`d` d ON a.id = d.id GROUP BY d.name ORDER BY cnt DESC
- JSON array column:
  SELECT jt.col, COUNT(*) cnt FROM `s`.`t` CROSS JOIN JSON_TABLE(json_col, '$[*]' COLUMNS(col INT PATH '$.key')) jt GROUP BY jt.col ORDER BY cnt DESC

## STEP NARRATION — EXPLAIN EACH TOOL CALL (reason / work)
Every tool has two extra parameters, `reason` and `work`, purely for narrating the step to the user (they do not change what the tool does):
- `reason` — set this on EVERY tool call: why you are making THIS call, in the user's context. Refer to their actual goal, not a generic description of the tool. Korean, 1–2 sentences. Good: "월별 매출을 집계하려면 주문일자·금액 컬럼명을 먼저 확정해야 하므로". Bad: "테이블 구조를 확인하기 위해".
- `work` — the concrete action in one Korean line: "`db`.`orders` 의 컬럼 구조를 확인".
Always fill `reason` (and ideally `work`) as parameters of the tool call itself — do NOT write them as separate text. The user sees these as the rationale for each step.

## OUTPUT
Once you have the data you need, stop calling tools and write the final answer in Korean Markdown. Lead with the answer, use tables for comparisons, format numbers with commas, and state any assumptions you made. Keep any clarifying question short and at the end. The final answer is plain Korean Markdown prose for the user — no JSON.

## SHOWING CHANGES — USE A MARKDOWN DIFF BLOCK
Whenever you propose a corrected, optimized, or edited version of something the user gave you — an attached SQL/code/config file, or a query they wrote in the chat — do NOT just paste the rewritten text on its own. Show WHAT CHANGED as a fenced **diff** code block so the edit is unmistakable. Example:

```diff
- SELECT * FROM `db`.`orders` WHERE status = 1
+ SELECT id, amount FROM `db`.`orders` WHERE status = 1 AND created_at >= '2026-01-01'
```

Rules:
- Open the fence with the `diff` language tag (```diff). Prefix removed lines with `- ` and added lines with `+ `; leave unchanged context lines with a single leading space.
- Show only the changed region plus a little surrounding context — not the entire file.
- After the diff block, add a short Korean explanation of WHY each change was made.
- This is for REVIEWS/EDITS of the user's SQL, code, or attached files. When you are writing brand-new SQL from scratch (not editing the user's own text), a normal ```sql block is fine.
"""


# P6/§3.5: 활성 datasource 가 MSSQL 일 때 system prompt 끝에 덧붙이는 T-SQL 방언 지침.
# base SYSTEM_PROMPT 의 MySQL 가정(백틱·LIMIT·NOW())을 엔진별로 교정한다.
_MSSQL_DIALECT_GUIDANCE = """

## SQL DIALECT — THIS DATASOURCE IS MICROSOFT SQL SERVER (T-SQL), NOT MySQL
The active datasource is **SQL Server**. Write **T-SQL**, not MySQL. Critical rules:
- **Row limiting**: use `SELECT TOP n ...` — there is NO `LIMIT` clause in T-SQL.
- **Identifier quoting**: use `[schema].[table]` brackets (or plain `schema.table`), NEVER MySQL backticks (`` ` ``).
- **Qualify every table**: for the CURRENT database use 2-part `schema.table` (e.g. `dbo.MyTable`); for ANOTHER allowed database use 3-part `database.schema.table` (e.g. `GameLog_151.dbo.T_ItemLog`). Unqualified (table-only) names are rejected. Most user tables live in the `dbo` schema.
- **Allowed databases**: you may query only the databases listed below (others are blocked). Use 3-part names to read across them.
- **Functions**: use T-SQL forms — `GETDATE()` (not `NOW()`), `LEN()` (not `LENGTH()`), `ISNULL()`/`COALESCE()`, `TOP`/`OFFSET-FETCH` for paging, `+` or `CONCAT()` for string concat, `CAST/CONVERT` for types.
- **Date**: use `CONVERT`/`FORMAT`/`DATEADD`/`DATEDIFF` (not MySQL `DATE_FORMAT`/`DATE_SUB`).
- Quote string literals with single quotes. Prefix Unicode literals with `N'...'`.
Discover exact table/column names with describe_table/search_tables before querying — SQL Server schemas and casing differ from MySQL.
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
# TASK-0124: text kind 첨부파일 (SQL/코드/텍스트) 의 raw content 를
# caller (app.py) 가 MinIO 에서 읽어 JSON 직렬화 → 임시 file 저장 →
# env ATTACHMENT_TEXT_INLINE_PATH 로 path 만 전달. agent_core 는 path 만 read.
#
# JSON spec (caller 가 작성):
#   [
#     {"attachment_id": 130, "filename": "query.sql", "content": "SELECT ...", "truncated": false},
#     ...
#   ]
#
# size cap (단일 ≤ 64KB UTF-8), count cap (turn 당 ≤ 20) 은 caller 의 책임.
_INLINE_TEXT_ENV_VAR = "ATTACHMENT_TEXT_INLINE_PATH"


# ── 첨부 채널 per-request 격리 (contextvars) ──────────────────────────
# TASK-0137 (#8 잔여): 첨부 메타(ids / new_ids / inline image·text 임시파일 path)를
# 과거엔 os.environ 프로세스 전역으로 web→agent_core 에 전달했다. 동시 ask 요청이
# 한 프로세스를 공유하므로 한 요청의 첨부가 다른 요청에 새는 race 가 있었다.
# 교차계정 유출은 app.py 의 AccountId 스코프(IDOR fix)로 이미 fail-closed 이고,
# 잔여 위험은 '같은 계정 내 동시 요청의 첨부 혼선'(사용자 대면 정확성 glitch).
# Task 3 의 _ACTIVE_SCHEMA_ALLOWLIST 와 동일하게 contextvars 로 전환 —
# asyncio.to_thread 가 호출 context 를 복사 전파하므로 요청별로 완전 격리된다.
# ctx 값이 None(=run_agent 미경유: 직접 _run_agent_core 호출/테스트/CLI)이면
# 하위호환을 위해 os.getenv 로 fallback 한다. 빈 문자열은 '명시적 없음'(env 미참조).
_ATTACHMENT_IDS_CTX: "contextvars.ContextVar[str | None]" = contextvars.ContextVar(
    "attachment_ids_ctx", default=None
)
_NEW_ATTACHMENT_IDS_CTX: "contextvars.ContextVar[str | None]" = contextvars.ContextVar(
    "new_attachment_ids_ctx", default=None
)
_INLINE_IMAGE_PATH_CTX: "contextvars.ContextVar[str | None]" = contextvars.ContextVar(
    "inline_image_path_ctx", default=None
)
_INLINE_TEXT_PATH_CTX: "contextvars.ContextVar[str | None]" = contextvars.ContextVar(
    "inline_text_path_ctx", default=None
)


def _ctx_or_env(ctx_var: "contextvars.ContextVar", env_name: str) -> str:
    """첨부 채널 값을 contextvar 우선으로 읽되, ctx 미설정(None) 시 os.getenv 로 fallback.

    run_agent 를 경유한 web 요청은 ctx 가 항상 설정되므로 os.environ 을 보지 않는다
    (요청별 격리). ctx 가 None 이면 run_agent 미경유 → 레거시 env 경로.
    """
    v = ctx_var.get()
    if v is not None:
        return v
    return os.getenv(env_name) or ""


def _load_attachment_inline_texts() -> dict[int, dict]:
    """env ATTACHMENT_TEXT_INLINE_PATH 의 JSON 을 read 후 {attachment_id: {filename, content, truncated}} 반환.

    Returns: dict keyed by attachment_id. 부재 / parse 실패 / 빈 content → 빈 dict (graceful failure).
    """
    path = _ctx_or_env(_INLINE_TEXT_PATH_CTX, _INLINE_TEXT_ENV_VAR).strip()
    if not path:
        return {}
    try:
        if not os.path.isfile(path):
            return {}
        with open(path, "r", encoding="utf-8") as _f:
            data = json.load(_f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, list):
        return {}
    result: dict[int, dict] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            aid = int(item.get("attachment_id") or 0)
        except (TypeError, ValueError):
            continue
        if aid <= 0:
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        result[aid] = {
            "filename": str(item.get("filename") or ""),
            "content": content,
            "truncated": bool(item.get("truncated")),
        }
    return result


def _load_new_attachment_ids() -> set[int]:
    """env NEW_ATTACHMENT_IDS (comma-separated) 를 읽어 이번 요청에 새로 첨부된 파일 ID set 반환.

    agent_core 가 LLM 컨텍스트에서 신규 vs 세션 파일을 구분 라벨링할 때 사용.
    부재 / parse 실패 → 빈 set (graceful failure).
    """
    raw = _ctx_or_env(_NEW_ATTACHMENT_IDS_CTX, "NEW_ATTACHMENT_IDS").strip()
    if not raw:
        return set()
    result: set[int] = set()
    for x in raw.split(","):
        x = x.strip()
        if x.lstrip("-").isdigit():
            v = int(x)
            if v > 0:
                result.add(v)
    return result


def _load_attachment_inline_images() -> list[dict[str, Any]]:
    """env ATTACHMENT_IMAGE_INLINE_PATH 의 JSON 을 read 후 image_attachments 반환.

    Returns: list[{filename, mime_type, base64_data}]. env 부재 / file 미존재 /
    parse 실패 / 빈 base64 → 빈 list (graceful failure, agent 진행 차단 X).

    D13 정합: 본 함수는 base64 string 만 다루고 storage_minio / signed URL 에 직접
    접근하지 않는다. caller (app.py) 가 server-side bytes read + base64 inline 책임.
    """
    path = _ctx_or_env(_INLINE_IMAGE_PATH_CTX, _INLINE_IMAGE_ENV_VAR).strip()
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


def _number_file_lines(content: str) -> str:
    """첨부 텍스트 본문의 각 줄에 1-기반 줄번호 prefix(`<N>→`)를 붙인다(모델 참조용).

    TASK-0256e: 모델이 첨부 파일의 실제 줄을 인용하고, diff 를 보일 때 실제 줄번호로
    unified-diff 헌크 헤더(`@@ -N,M +N,M @@`)를 작성할 수 있게 한다(웹 UI 가 그 헤더로
    gutter 줄번호를 표시). 줄번호 없이 주입하면 모델이 줄을 추정하지 못해 항상 1부터
    매겨졌다. 우측 정렬로 자릿수를 맞춘다. 본 prefix 는 prompt 주입 사본에만 적용하며
    원본 content(SQL 추출 등 다른 경로)는 건드리지 않는다.
    """
    src = content.splitlines()
    if not src:
        return content
    width = len(str(len(src)))
    return "\n".join(f"{i:>{width}}→{line}" for i, line in enumerate(src, 1))


def _build_attachment_context_section(mem_conn, attachment_ids: list[int], account_id: int | None = None) -> str:
    """TASK-0094 Sprint 1 Phase 11 + TASK-0107 Phase B — selected attachment metadata
    + sandbox schema/table 명 + 각 table 의 column schema + head 5 sample rows
    를 prompt 에 주입한다.

    LLM 이 첨부 파일을 분석할 때:
      1. ATTACHED FILES 섹션의 sandbox_schema_name + sandbox tables 를 본다
      2. SAMPLE ROWS 로 데이터 형태를 파악한다
      3. 필요 시 execute_sql 로 sandbox schema 의 table 을 SELECT 해 추가 분석

    D16 정합: attachment_ids 가 빈 list 면 본 section 미주입 (minimum exposure).
    """
    # TASK-0132 (#8 IDOR/env-race): account_id 필수 — AccountId 스코프로 타 계정 첨부
    # 메타(파일명/sandbox 스키마명) 가 prompt 에 유출되는 것을 차단. 이 스코프는 ATTACHMENT_IDS
    # 가 os.environ 으로 전달되며 동시 요청 간 race 가 나도 교차테넌트 유출을 막는 안전망이다.
    if not attachment_ids or mem_conn is None or not account_id:
        return ""
    # TASK-0277: read cutover — AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND=postgres 면 PG agent_runtime
    # 에서 읽는다(IDOR AccountId 가드 동형). 행은 positional tuple, 컬럼 순서·MetaJson::text 로 MySQL 정합.
    # PG read 실패는 MySQL(mem_conn) 폴백(가용성 — dual-write 로 MySQL 도 정본 유지).
    rows = None
    if os.environ.get("AGENT_RUNTIME_ATTACHMENTS_READ_BACKEND", "mysql").strip().lower() == "postgres":
        try:
            from modules.db import _pg_connect
            _pg = _pg_connect()
            try:
                _ph = ", ".join(["%s"] * len(attachment_ids))
                with _pg.cursor() as _pc:
                    _pc.execute(
                        f"SELECT id, conversation_id, original_filename, kind, mime_type, "
                        f"size_bytes, size_bucket, upload_status, meta_json::text "
                        f"FROM agent_runtime.core_attachments "
                        f"WHERE id IN ({_ph}) AND account_id = %s "
                        f"AND deleted_at IS NULL AND delete_pending = 0 ORDER BY id ASC",
                        tuple(int(i) for i in attachment_ids) + (int(account_id),),
                    )
                    rows = _pc.fetchall() or []
            finally:
                _pg.close()
        except Exception:
            rows = None
    if rows is None:
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
                WHERE Id IN ({placeholders}) AND AccountId = %s AND DeletedAt IS NULL AND DeletePending = 0
                ORDER BY Id ASC
                """,
                tuple(int(i) for i in attachment_ids) + (int(account_id),),
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

    import json as _json

    # TASK-0124: text kind 첨부파일 내용 로드 (env ATTACHMENT_TEXT_INLINE_PATH).
    text_inline_map = _load_attachment_inline_texts()
    # NEW_ATTACHMENT_IDS: 이번 요청에 새로 첨부된 파일 ID set (신규 vs 세션 라벨링용).
    new_ids_set = _load_new_attachment_ids()

    lines = ["", "## ATTACHED FILES (User-selected)"]
    if new_ids_set:
        lines.append("<!-- ★ = 이번 요청에 새로 첨부 | ◆ = 이전 세션에서 첨부 (LLM 컨텍스트 유지) -->")
    sandbox_table_specs: list[tuple[str, str, str]] = []  # (schema, table, source_label)
    text_content_entries: list[tuple[int, str, str, bool]] = []  # (attachment_id, filename, content, is_new)
    for row in rows:
        attachment_id = int(row[0] or 0)
        kind = str(row[3] or "")
        filename = str(row[2] or "")
        size_bucket = str(row[6] or "")
        upload_status = str(row[7] or "")
        meta_obj: dict = {}
        try:
            meta_raw = row[8]
            if isinstance(meta_raw, str):
                meta_obj = _json.loads(meta_raw) or {}
            elif isinstance(meta_raw, dict):
                meta_obj = meta_raw
        except Exception:
            meta_obj = {}

        meta_text = ""
        sandbox_schema = str(meta_obj.get("sandbox_schema_name") or "").strip()

        if kind == "csv":
            sandbox_table = str(meta_obj.get("sandbox_table_name") or "").strip()
            rows_inserted = int(meta_obj.get("rows_inserted") or 0)
            if sandbox_schema and sandbox_table:
                meta_text += f" rows={rows_inserted} sandbox=`{sandbox_schema}`.`{sandbox_table}`"
                sandbox_table_specs.append((sandbox_schema, sandbox_table, f"attachment_id={attachment_id} (csv)"))
        elif kind == "xlsx":
            sheets = meta_obj.get("sheets") or []
            if isinstance(sheets, list) and sandbox_schema:
                sheet_summaries = []
                for sh in sheets:
                    if not isinstance(sh, dict):
                        continue
                    sh_name = str(sh.get("name") or "")
                    sh_table = str(sh.get("table_name") or "")
                    sh_rows = int(sh.get("rows") or 0)
                    if sh_table:
                        sheet_summaries.append(f"sheet=`{sh_name}` table=`{sandbox_schema}`.`{sh_table}` rows={sh_rows}")
                        sandbox_table_specs.append(
                            (sandbox_schema, sh_table, f"attachment_id={attachment_id} sheet={sh_name}")
                        )
                if sheet_summaries:
                    meta_text += " " + "; ".join(sheet_summaries)
        elif kind == "text":
            # TASK-0124: text 파일은 sandbox ingest 대상이 아니라 raw content 직접 주입.
            inline = text_inline_map.get(attachment_id)
            if inline:
                content = inline["content"]
                truncated = inline.get("truncated", False)
                trunc_note = " [truncated]" if truncated else ""
                meta_text += f" content_len={len(content)}{trunc_note}"
                is_new = attachment_id in new_ids_set
                text_content_entries.append((attachment_id, filename, content, is_new))
            else:
                meta_text += " (content unavailable — check MinIO connectivity)"

        if meta_obj.get("degraded_reason"):
            meta_text += f" [DEGRADED: {meta_obj['degraded_reason']}]"

        # 신규 vs 세션 라벨 (NEW_ATTACHMENT_IDS 기반).
        source_label = " ★신규" if attachment_id in new_ids_set else " ◆세션"
        lines.append(
            f"- attachment_id={attachment_id} kind={kind} file={filename} size={size_bucket} status={upload_status}{source_label}{meta_text}"
        )

    # text kind 파일 내용 주입 (TASK-0124).
    if text_content_entries:
        lines.append("")
        lines.append("## ATTACHED FILE CONTENTS (text/code files — read directly)")
        for att_id, fname, content, is_new in text_content_entries:
            lines.append("")
            # 확장자로 코드 펜스 언어 결정
            ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
            lang = ext if ext in {"sql", "py", "js", "ts", "json", "yaml", "yml",
                                   "sh", "bash", "xml", "html", "css", "java",
                                   "go", "rb", "php", "c", "cpp", "h", "md"} else ""
            ctx_label = "★ 이번 요청 신규 첨부" if is_new else "◆ 이전 세션 첨부"
            lines.append(f"### {fname} (attachment_id={att_id}) [{ctx_label}]")
            # TASK-0256e: 각 줄에 `<N>→` 줄번호 prefix(모델이 실제 줄을 인용/diff 헌크 작성).
            lines.append(f"```{lang}")
            lines.append(_number_file_lines(content))
            lines.append("```")
        lines.append("")
        lines.append(
            "**INSTRUCTION**: The file contents above are the actual raw content of the attached files. "
            "Read them directly to answer the user's question. "
            "If the user asks to review / explain / fix / compare / optimize these files (e.g. 쿼리 리뷰, "
            "코드 검토), the attached content is the PRIMARY subject — answer about it directly and do NOT "
            "run execute_sql against your own database unless the user explicitly asks you to run or validate "
            "the query there. This takes precedence over the general 'query the database' guidance. "
            "Files marked '★ 이번 요청 신규 첨부' were just attached in this message. "
            "Files marked '◆ 이전 세션 첨부' are from earlier in this conversation and remain available. "
            "Do NOT ask the user to paste the file contents — they are already provided above."
        )
        lines.append("")
        lines.append(
            "**LINE NUMBERS & DIFFS**: Each line in the file contents above is prefixed with its 1-based "
            "line number as `<N>→` (e.g. `50→  , YEAR(...)`). These prefixes are reference metadata, NOT part "
            "of the file. Use the REAL line numbers when you cite specific lines AND when you show an edit: "
            "when you present a change as a ```diff block, start each changed region with a unified-diff hunk "
            "header that uses the file's actual line numbers — `@@ -<oldStart>,<oldCount> +<newStart>,<newCount> @@` "
            "— and include 1–2 unchanged context lines around the change so the numbers anchor to the source. "
            "NEVER include the `<N>→` prefix inside the diff; the +, -, and context lines must contain only the "
            "real code."
        )

    # 각 sandbox table 의 column schema + head 5 sample rows.
    # D16 정합: 사용자가 명시 첨부한 파일에 한정 — 다른 대화의 sandbox 접근 차단은
    # attachment_ids → ConversationId 검증이 caller (app.py) 에서 이미 완료.
    if sandbox_table_specs:
        lines.append("")
        lines.append("## SANDBOX SCHEMA & SAMPLE ROWS (head 5 per table)")
        for schema, table, source_label in sandbox_table_specs[:20]:  # cap 20 tables
            lines.append("")
            lines.append(f"### `{schema}`.`{table}` — {source_label}")
            try:
                col_cur = mem_conn.cursor()
                col_cur.execute(
                    "SELECT COLUMN_NAME, COLUMN_TYPE FROM information_schema.columns "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",
                    (schema, table),
                )
                col_rows = col_cur.fetchall() or []
                col_cur.close()
            except Exception:
                col_rows = []
            if col_rows:
                col_descs = [f"`{c[0]}` {c[1]}" for c in col_rows]
                lines.append(f"columns: {', '.join(col_descs)}")
            else:
                lines.append("(columns unavailable — sandbox table may not exist yet; check UploadStatus.)")
                continue

            try:
                sample_cur = mem_conn.cursor()
                sample_cur.execute(f"SELECT * FROM `{schema}`.`{table}` LIMIT 5")
                sample_rows = sample_cur.fetchall() or []
                sample_cur.close()
            except Exception:
                sample_rows = []
            if sample_rows:
                col_names = [c[0] for c in col_rows]
                lines.append(f"sample (first {len(sample_rows)} rows):")
                # markdown-ish table: header
                lines.append("| " + " | ".join(col_names) + " |")
                lines.append("|" + "|".join(["---"] * len(col_names)) + "|")
                for sr in sample_rows:
                    cells = []
                    for v in sr:
                        s_v = "" if v is None else str(v)
                        # truncate per-cell to keep prompt size bounded
                        if len(s_v) > 80:
                            s_v = s_v[:77] + "..."
                        # escape pipe
                        s_v = s_v.replace("|", "\\|").replace("\n", " ")
                        cells.append(s_v)
                    lines.append("| " + " | ".join(cells) + " |")
            else:
                lines.append("(table empty — possibly ingest still in progress.)")

        lines.append("")
        lines.append(
            "**INSTRUCTION**: When the user asks about an attached CSV/XLSX file's contents, "
            "first try to answer from the sample rows above. If more data is needed, "
            "call `execute_sql` against the sandbox table (e.g. "
            "`SELECT COUNT(*) FROM \\`<schema>\\`.\\`<table>\\``). "
            "Do NOT ask the user to paste the file contents — the data is already accessible."
        )
    elif not text_content_entries:
        lines.append(
            "(Sandbox tables not yet available — UploadStatus may be 'uploaded' (ingest pending) "
            "or 'failed'. If failed, inform the user briefly.)"
        )

    lines.append("")
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
        attachment_ids_raw = _ctx_or_env(_ATTACHMENT_IDS_CTX, "ATTACHMENT_IDS").strip()
        if attachment_ids_raw:
            attachment_ids = [int(x) for x in attachment_ids_raw.split(",") if x.strip().lstrip("-").isdigit() and int(x) > 0]
            if attachment_ids:
                section = _build_attachment_context_section(mem_conn, attachment_ids, account_id)
                if section:
                    parts.append(section)
    except Exception:
        pass

    return "".join(parts)


# ══════════════════════════════════════════════════════════════════
#  지식 주입 (Knowledge Injection)
# ══════════════════════════════════════════════════════════════════

def _extract_schema_desc(raw: str) -> str:
    """schema_insight 텍스트에서 표시용 도메인 설명을 추출한다.

    MySQL/PG 공용. "domain:" 이후 설명을 우선 추출하고, 없으면 레거시 한국어
    " / " 분할 형식을 폴백으로 사용한다.
    """
    raw = str(raw or "")
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
        segments = raw.split(" / ")
        desc = segments[0].strip()[:100]
    return desc


def _global_insight_rows_pg(
    like_pattern: str,
    *,
    with_text: bool,
    tokens: list[str] | None = None,
    limit: int | None = None,
    not_like_pattern: str | None = None,
) -> list[tuple] | None:
    """PG `public.fact_entries` 에서 __global__/common scope insight fact 를 읽는다.

    05-27 MySQL→PG cutover 로 insight fact 의 정본이 PG 로 이동했다. KNOWN SCHEMAS
    grounding 을 채우는 _load_schema_list / _load_relevant_table_insights 가 이전엔
    DROP 된 MySQL `AgentMemoryFactEntries` 만 조회 → 항상 빈 grounding → 환각이었다.

    Returns:
        list[(fact_key, text_or_None)] — PG 조회 성공 시 (빈 결과 포함).
        None — PG 미가용/예외. caller 가 레거시 MySQL 경로로 fallback 한다.
    """
    try:
        from modules.db import _pg_available, _pg_connect_ro
    except Exception:
        return None
    if not _pg_available():
        return None
    conn = None
    try:
        conn = _pg_connect_ro()
        cur = conn.cursor()
        params: list[Any] = [cfg.GLOBAL_CONVERSATION_ID, cfg.FACT_SCOPE_COMMON, like_pattern]
        # 멀티 datasource (P3, Codex-3): not_like_pattern 으로 datasource 키를 제외/한정.
        # 기본 대화(ds=None)는 `table_insight:ds:%` 를 제외해 datasource 인사이트 비노출.
        nlike_sql = ""
        if not_like_pattern:
            nlike_sql = " AND e.fact_key NOT LIKE %s"
            params.append(not_like_pattern)
        if with_text:
            sql = (
                "SELECT e.fact_key, LEFT(t.text_content, 200) "
                "FROM public.fact_entries e "
                "JOIN public.texts t ON t.text_hash = e.text_hash "
                "WHERE e.conversation_id = %s AND e.scope_key = %s "
                "  AND e.fact_key LIKE %s" + nlike_sql
            )
        else:
            sql = (
                "SELECT e.fact_key, NULL "
                "FROM public.fact_entries e "
                "WHERE e.conversation_id = %s AND e.scope_key = %s "
                "  AND e.fact_key LIKE %s" + nlike_sql
            )
        if tokens:
            ors: list[str] = []
            for tok in tokens:
                like = f"%{tok}%"
                if with_text:
                    ors.append("(e.fact_key ILIKE %s OR t.text_content ILIKE %s)")
                    params.extend([like, like])
                else:
                    ors.append("e.fact_key ILIKE %s")
                    params.append(like)
            sql += " AND (" + " OR ".join(ors) + ")"
        sql += " ORDER BY e.fact_key"
        if limit:
            sql += " LIMIT %s"
            params.append(int(limit))
        cur.execute(sql, params)
        rows = cur.fetchall() or []
        cur.close()
        return [(str(r[0]), (r[1] if len(r) > 1 else None)) for r in rows]
    except Exception:
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _kb_read_is_pg() -> bool:
    return str(getattr(cfg, "AGENT_KB_READ_BACKEND", "mysql") or "mysql").lower() == "postgres"


def _insight_object_group(suffix: str) -> str:
    """TASK-0220: table_insight suffix 에서 테이블명(마지막 segment)을 제외한 grouping 키 반환.

    - MySQL 2계층 `{schema}.{table}` → `{schema}`
    - MSSQL 3계층 `{database}.{schema}.{table}` → `{database}.{schema}`
    점이 없으면(예외적) 빈 문자열. schema_insight suffix(`{schema}` / `{database}.{schema}`)와
    동일 단위라 desc 매칭이 정합한다.
    """
    name = str(suffix or "").strip()
    dot = name.rfind(".")
    return name[:dot] if dot > 0 else ""


def _load_schema_list(mem_conn, max_total: int = 2000) -> str:
    """스키마별 테이블 수와 인사이트 DB의 도메인 설명을 로드한다.

    AGENT_KB_READ_BACKEND=postgres 이면 PG(public.fact_entries/texts) 정본에서
    읽고, 미가용/예외 시 레거시 MySQL(mem_conn) 경로로 fallback 한다.
    """
    schema_counts: dict[str, int] = {}
    schema_descs: dict[str, str] = {}

    # ── PG 정본 경로 ──
    pg_used = False
    if _kb_read_is_pg():
        # 멀티 datasource (P3, Codex-3): grounding 읽기를 현재 대화의 datasource 로 한정한다.
        # ds_fact_like 가 ContextVar(set_active_datasource, 호출부에서 설정)를 읽어 datasource
        # 키만(또는 기본은 datasource 키 제외) 매치 → datasource 간 인사이트 교차노출 차단.
        t_like, t_nlike = cfg.ds_fact_like("table_insight")
        s_like, s_nlike = cfg.ds_fact_like("schema_insight")
        table_rows = _global_insight_rows_pg(t_like, with_text=False, not_like_pattern=t_nlike)
        schema_rows = _global_insight_rows_pg(s_like, with_text=True, not_like_pattern=s_nlike)
        if table_rows is not None or schema_rows is not None:
            pg_used = True
            for fact_key, _ in (table_rows or []):
                # TASK-0220: suffix 는 MySQL `{schema}.{table}`(2계층) 또는 MSSQL
                # `{database}.{schema}.{table}`(3계층). 테이블명(마지막 segment)을 제외한
                # prefix 를 grounding 키로 쓴다 → MySQL=schema, MSSQL=database.schema.
                name = cfg.ds_strip_prefix("table_insight", fact_key)
                grp = _insight_object_group(name)
                if grp:
                    schema_counts[grp] = schema_counts.get(grp, 0) + 1
            for fact_key, text_content in (schema_rows or []):
                # schema_insight suffix 는 MySQL `{schema}` 또는 MSSQL `{database}.{schema}`.
                # table_insight 의 grouping 키(database.schema)와 동일 단위로 정규화해 desc 가 매칭되게 한다.
                schema_name = cfg.ds_strip_prefix("schema_insight", fact_key)
                if schema_name == "agent_memory":
                    continue
                schema_descs[schema_name] = _extract_schema_desc(str(text_content or ""))

    # ── 레거시 MySQL fallback (PG 미사용 시만) ──
    if not pg_used:
        # M2(P3): datasource 대화는 un-scoped MySQL fallback 을 타지 않는다(레거시 MySQL 미러가
        # 부활해도 datasource 간 인사이트 교차노출 방지 — Codex-3 심층방어). 대신 빈 grounding →
        # search/describe 발견 경로. (현재 MySQL 정본은 cutover 로 DROP 되어 이 경로는 dead.)
        if cfg.get_active_datasource():
            return ""
        if not mem_conn:
            return ""
        cur = mem_conn.cursor()
        try:
            cur.execute(
                "SELECT e.FactKey "
                "FROM AgentMemoryFactEntries e "
                "WHERE e.ConversationId = '__global__' "
                "  AND e.FactKey LIKE 'table_insight:%' "
                "ORDER BY e.FactKey",
            )
            for (fact_key,) in cur.fetchall() or []:
                name = fact_key.replace("table_insight:", "")
                grp = _insight_object_group(name)
                if grp:
                    schema_counts[grp] = schema_counts.get(grp, 0) + 1
        except Exception:
            pass
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
                schema_descs[schema_name] = _extract_schema_desc(str(text_content or ""))
        except Exception:
            pass
        try:
            cur.close()
        except Exception:
            pass

    # ── 렌더 (공통) ──
    parts: list[str] = []
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
    return "\n".join(parts) if parts else ""


def _load_relevant_table_insights(mem_conn, user_message: str, max_items: int = 15) -> str:
    """사용자 메시지의 키워드로 매칭되는 테이블 인사이트를 로드한다.

    AGENT_KB_READ_BACKEND=postgres 이면 PG 정본에서 ILIKE 매칭, 미가용/예외 시
    레거시 MySQL(mem_conn) 경로로 fallback.
    """
    if not user_message:
        return ""
    tokens = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_]{1,}", user_message.lower()))
    if not tokens:
        return ""
    token_list = list(tokens)[:10]

    # ── PG 정본 경로 ──
    if _kb_read_is_pg():
        # 멀티 datasource (P3, Codex-3): 현재 대화의 datasource 로 한정.
        t_like, t_nlike = cfg.ds_fact_like("table_insight")
        pg_rows = _global_insight_rows_pg(
            t_like, with_text=True, tokens=token_list, limit=max_items, not_like_pattern=t_nlike
        )
        if pg_rows is not None:
            lines = []
            for fact_key, text in pg_rows:
                table_ref = cfg.ds_strip_prefix("table_insight", fact_key)
                lines.append(f"- {table_ref}: {str(text or '').strip()}")
            return "\n".join(lines)

    # ── 레거시 MySQL fallback ──
    # M2(P3): datasource 대화는 un-scoped MySQL fallback 금지 (Codex-3 심층방어, 위 _load_schema_list 참조).
    if cfg.get_active_datasource():
        return ""
    if not mem_conn:
        return ""
    cur = mem_conn.cursor()
    try:
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
        # 나열된 테이블은 신뢰하되, 없으면 도구로 발견하도록 유도 (환각 방지).
        parts.append("## KNOWN SCHEMAS & TABLES (authoritative for the tables listed here)")
        parts.append("Trust the schemas/tables below. If the table you need is NOT listed, "
                     "discover it with search_tables/describe_table before writing SQL — do not guess names.")
        parts.append(schema_list)
    table_insights = _load_relevant_table_insights(mem_conn, user_message)
    if table_insights:
        parts.append("\n## RELEVANT TABLES FOR THIS QUESTION")
        parts.append("Candidate tables already matched to the user's keywords. "
                     "Start with execute_sql against one of these. If none actually fits the "
                     "question, verify with describe_table or search for a better match instead of guessing.")
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
    pass  # PG cutover 완료 — MySQL schema 재생성 불필요


def _parse_saved_tool_calls(raw_value: Any) -> list[dict[str, Any]]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _normalize_history_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """대화 히스토리를 LLM payload 용으로 정합화한다 (TASK-0160).

    Anthropic/Bedrock 은 assistant 의 tool_use 블록마다 바로 다음에 대응하는
    tool_result 가 있어야 한다 (`messages.N: tool_use ... without tool_result` → 400).
    중단된 run(예: web 재배포로 in-process ask 가 execute_sql 도중 종료 — [[TASK-0159]])은
    tool_use 만 저장하고 tool_result 전에 죽어, 재생성 시 이 제약을 깨뜨린다.

    그래서 assistant(tool_calls) 턴을 **버퍼링**해, 그 턴의 모든 tool_use id 가
    뒤따르는 tool 행으로 해소된 경우에만 commit 한다. 하나라도 미해소(중단 잔재 또는
    윈도우 경계 절단)면 그 턴(assistant + 부분 tool 결과)을 통째로 drop 해 payload
    정합성을 보장한다. 매칭 assistant 없는 고아 tool 행도 drop (기존 동작 유지).
    """
    normalized: list[dict[str, Any]] = []
    # 진행 중 assistant tool_use 턴 버퍼
    pending_assistant: dict[str, Any] | None = None
    pending_tool_ids: set[str] = set()
    pending_tool_rows: list[dict[str, Any]] = []

    def _flush() -> None:
        nonlocal pending_assistant, pending_tool_ids, pending_tool_rows
        # 모든 tool_use 가 해소된 유효 턴만 commit; 미해소 턴은 통째로 drop.
        if pending_assistant is not None and not pending_tool_ids:
            normalized.append(pending_assistant)
            normalized.extend(pending_tool_rows)
        pending_assistant = None
        pending_tool_ids = set()
        pending_tool_rows = []

    for row in rows:
        role = str(row.get("role") or "")
        raw_tool_calls = row.get("tool_calls")
        if role == "assistant" and raw_tool_calls:
            _flush()  # 직전 턴 마감
            parsed_tool_calls = _parse_saved_tool_calls(raw_tool_calls)
            if not parsed_tool_calls:
                continue
            next_row = dict(row)
            next_row["_parsed_tool_calls"] = parsed_tool_calls
            pending_assistant = next_row
            pending_tool_ids = {
                str(item.get("id") or "").strip()
                for item in parsed_tool_calls
                if isinstance(item, dict) and str(item.get("id") or "").strip()
            }
            if not pending_tool_ids:
                # tool_calls 가 있으나 사용 가능한 id 가 0개 → 페어링 검증 불가
                # → 매칭 불가능한 sentinel 로 강제 drop (정합성 보수적 보장).
                pending_tool_ids = {"\x00__unverifiable_tool_use__"}
            pending_tool_rows = []
            continue
        if role == "tool":
            tool_call_id = str(row.get("tool_call_id") or "").strip()
            if pending_assistant is not None and tool_call_id and tool_call_id in pending_tool_ids:
                pending_tool_ids.discard(tool_call_id)
                pending_tool_rows.append(row)
            # 매칭 assistant 없는 고아 tool 행 → drop
            continue
        # user 또는 tool_calls 없는 assistant → 진행 턴 마감 후 그대로 추가
        _flush()
        normalized.append(row)
    _flush()  # EOF — 마지막 턴 마감
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


# 멀티턴 맥락 보존: 윈도우(max_messages) 밖으로 밀려나는 'standalone user 메시지'를
# 최대 이 개수까지 윈도우 앞에 보존한다. tool 결과(execute_sql)가 윈도우를 점유해
# 사용자가 앞서 말한 제약/의도를 밀어내는 유실을 막는다. user 메시지는 tool 짝이 없어
# 단독 보존이 안전하고, 재정규화 단계가 orphan tool 메시지를 정리한다.
_USER_TURN_KEEP = 8


def _format_core_messages(normalized: list[dict]) -> list[dict]:
    """normalize 된 row 를 OpenAI 메시지 dict 로 변환."""
    messages: list[dict] = []
    for row in normalized:
        msg: dict[str, Any] = {"role": row["role"]}
        parsed_tool_calls = row.get("_parsed_tool_calls")
        if row.get("content") and not parsed_tool_calls and not row.get("tool_calls"):
            msg["content"] = row["content"]
        if parsed_tool_calls:
            msg["tool_calls"] = parsed_tool_calls
        if row.get("tool_call_id"):
            msg["tool_call_id"] = row["tool_call_id"]
        if row.get("name"):
            msg["name"] = row["name"]
        messages.append(msg)
    return messages


def _assemble_core_messages(rows: list[dict], max_messages: int) -> list[dict]:
    """normalize + truncate + format for OpenAI API. shared by MySQL and PG paths.

    단순 최근 N개 윈도우는 tool 메시지가 윈도우를 점유해 초기 user 의도를 떨어뜨린다.
    윈도우에서 탈락하는 standalone user 메시지를 최신순 _USER_TURN_KEEP 개까지 윈도우
    앞에 보존해 사용자가 앞서 말한 맥락을 유지한다 ("앞 내용을 왜 또 묻나" 완화).
    """
    normalized = _normalize_history_rows(rows)
    if len(normalized) <= max_messages:
        return _format_core_messages(normalized)

    window = normalized[-max_messages:]
    dropped = normalized[:-max_messages]
    kept_users = [
        r for r in dropped
        if str(r.get("role") or "") == "user" and r.get("content")
        and not r.get("_parsed_tool_calls") and not r.get("tool_calls")
        and not r.get("tool_call_id")
    ]
    if kept_users:
        kept_users = kept_users[-_USER_TURN_KEEP:]
    # 재정규화: 윈도우 시작부의 orphan tool 메시지(짝 assistant 가 dropped) 정리.
    combined = _normalize_history_rows(kept_users + window)
    return _format_core_messages(combined)


def _load_conversation_messages(conn, conversation_id: str, max_messages: int = 50) -> list[dict]:
    """대화 메시지를 OpenAI 메시지 형식으로 로드."""
    raw_limit = max(int(max_messages or 50) * 4, 80)

    # M4: PG read path
    from modules.runtime_backend import _read_runtime_pg, AGENT_RUNTIME_READ_BACKEND
    if AGENT_RUNTIME_READ_BACKEND == "postgres":
        pg_rows = _read_runtime_pg("load_core_messages",
                                   conversation_id=conversation_id, limit=raw_limit)
        if pg_rows is not None:
            # PG: (role, content, tool_calls, tool_call_id, name) — tool_calls is already
            # a Python object (psycopg3 JSONB auto-parse). Serialize back to JSON string so
            # _normalize_history_rows/_parse_saved_tool_calls can process it uniformly.
            # PG rows are ASC ordered (ORDER BY id ASC) — no reverse needed.
            dict_rows = [
                {
                    "role": r[0], "content": r[1],
                    "tool_calls": json.dumps(r[2], ensure_ascii=False) if r[2] is not None else None,
                    "tool_call_id": r[3], "name": r[4],
                }
                for r in pg_rows
            ]
            return _assemble_core_messages(dict_rows, max_messages)

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
    return _assemble_core_messages(list(reversed(rows)), max_messages)


def _save_message(conn, conversation_id: str, role: str,
                  content: str | None = None,
                  tool_calls: list | None = None,
                  tool_call_id: str | None = None,
                  name: str | None = None):
    """메시지를 DB에 저장."""
    from modules.runtime_backend import _get_pg_runtime_backend, _get_pg_runtime_conn
    pg_conn = _get_pg_runtime_conn()
    if pg_conn:
        try:
            _get_pg_runtime_backend().save_core_message(pg_conn,
                conversation_id=conversation_id, role=role,
                content=content, tool_calls=tool_calls,
                tool_call_id=tool_call_id, name=name)
        except Exception as _exc:
            logger.warning("_save_message PG write failed: %s", _exc)
        finally:
            pg_conn.close()


def _ensure_conversation(conn, conversation_id: str):
    from modules.runtime_backend import _get_pg_runtime_backend, _get_pg_runtime_conn
    pg_conn = _get_pg_runtime_conn()
    if pg_conn:
        try:
            _get_pg_runtime_backend().save_conversation(pg_conn,
                conversation_id=conversation_id)
        except Exception as _exc:
            logger.warning("_ensure_conversation PG write failed: %s", _exc)
        finally:
            pg_conn.close()


def _update_conversation_topic(conn, conversation_id: str, topic: str):
    from modules.runtime_backend import _get_pg_runtime_backend, _get_pg_runtime_conn
    pg_conn = _get_pg_runtime_conn()
    if pg_conn:
        try:
            _get_pg_runtime_backend().save_conversation(pg_conn,
                conversation_id=conversation_id, topic=topic[:256])
        except Exception as _exc:
            logger.warning("_update_conversation_topic PG write failed: %s", _exc)
        finally:
            pg_conn.close()


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
# 표↔CSV 매칭 시 CSV 에서 표본으로 읽을 데이터 행 수 (식별 토큰 수집용).
_CSV_MATCH_SAMPLE_ROWS = 50


def _distinctive_tokens(cells: list[Any]) -> set[str]:
    """셀 값에서 식별력 있는 토큰만 추출.

    TASK-0174: 답변 표를 올바른 CSV 와 잇기 위한 값 기반 join key.
    - 천단위 콤마 제거 후 길이 ≥3 숫자열 (ID·집계값 — "10,112명"→"10112",
      "2520504" 등). 1~2자리(순위 1·2·3 류)는 식별력이 낮아 제외.
    - 숫자가 없는 라벨 문자열은 길이 ≥2 면 포함.
    헤더 이름은 LLM 이 가독성 위해 리네이밍(ItemID→아이템ID)하므로 헤더가 아닌
    **값** 으로 매칭한다.
    """
    tokens: set[str] = set()
    for cell in cells:
        s = str(cell if cell is not None else "").strip()
        if not s:
            continue
        compact = s.replace(",", "")
        for num in re.findall(r"\d{3,}", compact):
            tokens.add(num)
        if not re.search(r"\d", s) and len(s) >= 2:
            tokens.add(s)
    return tokens


def _md_table_body_cells(table_lines: list[str]) -> list[str]:
    """마크다운 표 라인에서 헤더·구분자 제외한 본문 셀 값 목록."""
    cells: list[str] = []
    header_seen = False
    for tl in table_lines:
        s = tl.strip()
        if _MD_TABLE_SEP_RE.match(s):
            continue
        if not header_seen:
            header_seen = True  # 첫 데이터 행 = 헤더 → 값 매칭에서 제외
            continue
        cells.extend(c.strip() for c in s.strip("|").split("|"))
    return cells


def _md_table_col_count(table_lines: list[str]) -> int:
    """마크다운 표의 컬럼 수 (헤더 행의 셀 수)."""
    for tl in table_lines:
        s = tl.strip()
        if _MD_TABLE_SEP_RE.match(s):
            continue
        return len(s.strip("|").split("|"))
    return 0


def _csv_signatures(csv_paths: list[str]) -> list[tuple[set[str] | None, int]]:
    """각 CSV 의 (데이터 값 식별 토큰 집합, 컬럼 수). 읽기 실패 시 (None, 0)."""
    sigs: list[tuple[set[str] | None, int]] = []
    for path in csv_paths:
        prev = read_csv_preview(path, _CSV_MATCH_SAMPLE_ROWS)
        if not prev:
            sigs.append((None, 0))
            continue
        cells: list[Any] = []
        for row in prev.get("rows") or []:
            cells.extend(row)
        ncol = len(prev.get("columns") or [])
        sigs.append((_distinctive_tokens(cells), ncol))
    return sigs


def _match_csv_for_table(
    table_tokens: set[str],
    table_ncol: int,
    csv_sigs: list[tuple[set[str] | None, int]],
    used: list[bool],
) -> int | None:
    """표에 맞는 미사용 CSV 인덱스.

    1순위: 값 토큰 overlap 최대(≥1) — ID·집계값이 일치하는 정확 매칭.
    2순위(표에 식별 토큰이 **하나도 없을 때만**): 컬럼 수가 일치하는 미사용
       CSV 중 앞 순서. 측정값(%·소수)뿐이라 식별 토큰을 뽑을 수 없는 표를
       형태(shape)로 링크 복구한다. 형태 불일치 보조 쿼리(MIN/MAX 등)는 여전히
       배제되므로 위치-매칭 오정렬 버그는 재발하지 않는다.

    TASK-0208: 표에 식별 토큰이 **있는데도** 어느 CSV 와도 겹치지 않으면
       (예: LLM 이 손으로 쓴 "이슈 우선순위"·요약·분석표 — 쿼리 결과가 아님)
       컬럼 수 폴백을 적용하지 않는다. 토큰이 있다는 것은 join key 가 존재한다는
       뜻이고, 그 key 가 어느 CSV 와도 안 겹친다는 것은 "이 표는 그 쿼리 결과가
       아니다" 라는 음성(negative) 증거다. 이전엔 토큰이 있어도 폴백이 작동해,
       컬럼 수만 우연히 같은 무관한 CSV 가 비-결과 표에 "전체 N행 미리보기"
       링크로 붙고 클릭 시 frontend 값 가드가 거부(422 토스트)하는 오링크가
       발생했다. 폴백은 식별 토큰이 아예 없는 측정값-전용 표에만 한정한다.

       Trade-off: LLM 이 진짜 결과표의 값을 과격하게 재포맷해 토큰 overlap 이
       0 으로 떨어지면(라벨 토큰은 남음) 그 표도 링크를 잃는다. recall 손실이나,
       "없는 링크"(degraded)가 "깨진 링크"(클릭 시 422)보다 낫다는 판단.
    """
    best_idx: int | None = None
    best_score = 0
    if table_tokens:
        for j, (tok, _ncol) in enumerate(csv_sigs):
            if used[j] or not tok:
                continue
            score = len(table_tokens & tok)
            if score > best_score:
                best_score = score
                best_idx = j
    if best_idx is not None and best_score >= 1:
        return best_idx
    # 식별 토큰이 있는데 겹침 0 → 쿼리 결과가 아닌 표(분석·요약 등). 링크 생략.
    if table_tokens:
        return None
    # 식별 토큰 자체가 없는 측정값-전용 표만 컬럼 수 일치로 폴백(형태 불일치 제외).
    if table_ncol > 0:
        for j, (tok, ncol) in enumerate(csv_sigs):
            if used[j] or tok is None:
                continue
            if ncol == table_ncol:
                return j
    return None


def _collapse_large_tables(answer: str, csv_paths: list[str]) -> str:
    """답변 내 대형 마크다운 표를 미리보기 + CSV 링크로 치환.

    TASK-0174: 기존엔 답변 속 대형 표를 csv_paths 에 **위치 인덱스**로 1:1
    매칭했으나, csv_paths 에는 표로 렌더되지 않은 보조 쿼리(MIN/MAX 등) 결과
    CSV 까지 실행 순서대로 섞여 있어 인덱스가 어긋났다 (#118 후속 — 첫 대형
    표에 MIN/MAX CSV 가 붙어 "전체 N행 미리보기" 가 다른 쿼리 결과를 로드).
    → 표의 데이터 값 토큰과 각 CSV 의 값 토큰 overlap 으로 매칭(_match_csv_for_table)
    하고, 값으로 확정 못 하면 컬럼 수 일치 CSV 로 폴백한다. 형태 불일치 보조
    쿼리 CSV 는 어느 경로로도 붙지 않는다.
    """
    if not answer or not csv_paths:
        return answer
    csv_sigs = _csv_signatures(csv_paths)
    used = [False] * len(csv_paths)
    lines = answer.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if _MD_TABLE_ROW_RE.match(line):
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
            if body_rows > _TABLE_ROW_THRESHOLD:
                # 헤더 + 구분자 + 미리보기 행(최대 threshold행) 유지
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
                # 값 기반 매칭(+컬럼수 폴백) — 위치 인덱스 대신 표 내용과 일치 CSV.
                table_tokens = _distinctive_tokens(_md_table_body_cells(table_lines))
                table_ncol = _md_table_col_count(table_lines)
                match_idx = _match_csv_for_table(table_tokens, table_ncol, csv_sigs, used)
                if match_idx is not None:
                    used[match_idx] = True
                    result.append("")
                    result.append(
                        f"📎 [전체 {body_rows}행 미리보기]"
                        f"(/api/file?path={csv_paths[match_idx]})"
                    )
                    result.append("")
                # 확신 매칭 없으면 링크 생략 (잘못된 CSV 링크 방지).
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


def _strip_leaked_tool_notes(answer: str) -> str:
    """최종 답변(사용자 대면)에 LLM 이 실수로 흘린 `tool_notes` JSON envelope 를
    결정적으로 제거한다. SYSTEM_PROMPT 가 "최종 답변엔 JSON 금지"를 지시하지만
    그것은 통계적 억제일 뿐 fail-closed 가드가 아니므로(REV-20260610 B1), 누수 시
    사용자에게 raw JSON 이 노출되지 않도록 백엔드에서 결정적으로 방어한다.
    JSON 외 산문이 함께 있으면 산문만 남기고, 답변 전체가 envelope 면 빈 문자열을
    반환한다(호출부의 빈-답변 재요청 루프가 깨끗한 답변을 다시 받음)."""
    text = str(answer or "")
    if "tool_notes" not in text:
        return text
    decoder = json.JSONDecoder()
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "{":
            try:
                obj, end = decoder.raw_decode(text[i:])
            except Exception:
                i += 1
                continue
            if isinstance(obj, dict) and "tool_notes" in obj:
                spans.append((i, i + end))
                i += end
                continue
        i += 1
    if not spans:
        return text
    out: list[str] = []
    prev = 0
    for a, b in spans:
        out.append(text[prev:a])
        prev = b
    out.append(text[prev:])
    cleaned = "".join(out)
    # envelope 를 감쌌던 코드펜스 잔재(```json ... ```) 정리
    cleaned = re.sub(r"```(?:json)?", "", cleaned)
    return cleaned.strip()


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


def _derive_step_reason(tool_name: str, args: dict[str, Any] | None = None) -> str:
    """LLM 이 tool_notes.reason 을 제공하지 않을 때, tool 의 목적에서 단계 수행
    근거(왜)를 결정적으로 파생한다. `_derive_step_work`(무엇을)의 대칭 — work 는
    이미 derived fallback 이 있으나 reason 은 부재해 사용자에게 항상 빈 값이었다.
    참값(LLM tool_notes.reason)이 있으면 호출되지 않는다(호출부에서 가드)."""
    payload = args if isinstance(args, dict) else {}
    tool = str(tool_name or "").strip().lower()
    if tool == "list_schemas":
        return "접근 가능한 데이터베이스(스키마)를 파악하기 위해"
    if tool == "describe_schema":
        return "해당 스키마에 어떤 테이블이 있는지 파악하기 위해"
    if tool == "describe_table":
        return "쿼리에 사용할 컬럼과 자료형을 정확히 확인하기 위해"
    if tool == "search_tables":
        return "질문에 필요한 테이블을 찾기 위해"
    if tool == "get_sample_rows":
        return "실제 데이터의 형태와 값을 확인하기 위해"
    if tool == "get_table_indexes":
        return "효율적인 조회 경로(인덱스)를 파악하기 위해"
    if tool == "get_foreign_keys":
        return "테이블 간 연관 관계를 파악하기 위해"
    if tool == "explain_query":
        return "쿼리의 실행 계획과 비용을 미리 점검하기 위해"
    if tool == "execute_sql":
        sql_text = str(payload.get("sql", "") or "").strip()
        aggregate = bool(re.search(r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(|\bGROUP\s+BY\b", sql_text, re.IGNORECASE))
        if aggregate:
            return "요청한 집계 결과를 산출하기 위해"
        return "요청한 데이터를 조회하기 위해"
    return ""


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
              tools: list[dict] | None = None,
              conversation_id: str | None = None,
              run_id: str | None = None) -> Any:
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
    # TASK-0163: 메인 agentic loop 의 LLM 호출을 토큰 회계에 기록(best-effort).
    # 이전엔 _record_llm_usage chokepoint 를 우회해 사용자 대화 메인 추론이 한 건도
    # llm_usage 에 잡히지 않았다(계정별/역할별 집계가 비던 근본 원인 RC1).
    # in-process 동시 ask 의 cfg 전역 race 를 피하려 conversation_id/run_id 를 명시 전달.
    try:
        _record_llm_usage(model, "agent", response,
                          conversation_id=conversation_id, run_id=run_id)
    except Exception:
        pass
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
#  멀티 datasource 해석 (P1, DESIGN Stage 1)
# ══════════════════════════════════════════════════════════════════

class DatasourceResolutionError(Exception):
    """product 에 명시 datasource 바인딩이 있으나 해석 불가(미등록 키) — fail-closed 신호."""


def _resolve_product_datasource(mem_conn, product_id):
    """product 에 바인딩된 datasource 좌표를 해석한다 (None=기본 단일 MySQL).

    단일 chokepoint: in-process(app.py)·ask-worker(ask.py) 둘 다 run_agent→_run_agent_core
    를 통하므로 여기 한 곳에서 product→datasource 를 매핑하면 양 경로가 모두 커버된다.

    **보안 (DESIGN §4 Q7/Codex-4 security-first)**: datasource 접근 인가는 이 함수가 아니라
    web /api/ask 의 `_account_has_product_access`(연결 *전*)에서 이미 enforce 된다. 여기서는
    인가된 product 의 datasource 좌표를 *매핑*만 한다(authz 결정 아님). product 권한 = datasource
    접근 게이트(datasource 는 product 에 매달림).

    fail 방향 (REV-20260610-0187 M-2):
      - flag OFF / product 없음 / **DatasourceKey NULL**(미바인딩) → None (=기본 DB, 정상 동작).
      - **DatasourceKey 가 있으나 .env 미등록** → `DatasourceResolutionError` raise (**fail-closed**).
        명시 바인딩된 datasource 대화를 운영 DB 로 silent 폴백시키지 않는다(엉뚱한 DB 조회·혼선 차단).
      - DatasourceKey **읽기 자체 실패** → None (mem_conn 은 직전 단계에서 성공했으므로 극히 드물고,
        transient 오류로 미바인딩 product 까지 막는 건 과함 — 경고만).
    """
    if not cfg.AGENT_MULTI_DATASOURCE_ENABLED:
        return None
    if not product_id or int(product_id) <= 0:
        return None
    # TASK-0205: DatasourceKey + DatasourceDatabase(제품별 MSSQL 참조 DB override, §2.4) 동시 조회.
    key = ""
    product_db = ""
    try:
        cur = mem_conn.cursor()
        try:
            try:
                cur.execute(
                    "SELECT DatasourceKey, DatasourceDatabase FROM WebProducts WHERE Id=%s LIMIT 1",
                    (int(product_id),),
                )
                row = cur.fetchone()
                if row:
                    key = (str(row[0]).strip().lower() if row[0] else "")
                    product_db = (str(row[1]).strip() if len(row) > 1 and row[1] else "")
            except Exception:
                # DatasourceDatabase 컬럼 부재(구 스키마) 폴백
                cur.execute("SELECT DatasourceKey FROM WebProducts WHERE Id=%s LIMIT 1", (int(product_id),))
                row = cur.fetchone()
                key = (str(row[0]).strip().lower() if row and row[0] else "")
        finally:
            cur.close()
    except Exception as exc:
        # re-gate(4차) BLOCKER5: 바인딩 조회 실패를 "기본 DB 폴백(None)"으로 처리하면, datasource 바인딩이
        # 있어야 할 제품이 데이터 계정 GRANT 전체에 접근 가능한 기본 MySQL 로 fail-open 된다. 조회 실패 =
        # 권한 컨텍스트 불명 → **fail-closed**(run 중단). 호출부가 DatasourceResolutionError 를 사용자 에러로 처리.
        logging.getLogger("agent_core").error(
            "resolve_product_datasource_read_failed product_id=%s err=%r — fail-closed", product_id, exc,
        )
        raise DatasourceResolutionError(
            f"product {product_id} 의 datasource 바인딩 조회에 실패했습니다 (권한 컨텍스트 불명 — run 중단)."
        ) from exc
    if not key:
        return None  # 미바인딩 = 기본 DB (정상)
    # TASK-0205: DB 레지스트리(WebDatasources) 우선 + .env 레거시 폴백. password 복호 포함.
    from modules import datasources as _datasources
    ds = _datasources.resolve(mem_conn, key)
    if not ds:
        # 명시 바인딩 + 미등록(또는 복호 불가) 키 → fail-closed (운영 DB 로 silent 폴백 금지)
        logging.getLogger("agent_core").error(
            "datasource_key_not_registered product_id=%s key=%s — fail-closed(run 중단)", product_id, key,
        )
        raise DatasourceResolutionError(
            f"product {product_id} 의 datasource 키 '{key}' 가 미등록이거나 복호 불가입니다 "
            f"(WebDatasources / DS_{key.upper()}_* / KEK 확인)."
        )
    # TASK-0206 DB-단위: MSSQL primary(pin) DB 도출. **보안 불변식(re-gate BLOCKER1)**: pin 되는 DB 는 반드시
    # 제품 allowlist(WebProductDatabases) 멤버여야 한다 — 2-part `schema.table` 이 pin DB 로 암묵 해석되므로
    # pin 이 allowlist 밖이면 미허용 DB 데이터가 2-part 로 샌다. 따라서:
    #   - 명시 DatasourceDatabase 는 allowlist 에 있을 때만 채택(없으면 무시 — 레거시 값 우회 차단).
    #   - 그 외엔 제품의 **첫 접근가능 DB**(SortOrder) 자동 pin(사용자 결정: 첫 선택 DB).
    #   - allowlist 가 비면 pin 안 함(default_db 없음) → 빈 allowlist=접근 0 정합(2-part 도 가드가 차단).
    if (ds.get("engine") or "mysql").strip().lower() == "mssql":
        allow_dbs: list[str] = []
        try:
            cur = mem_conn.cursor()
            try:
                cur.execute(
                    "SELECT SchemaName FROM WebProductDatabases WHERE ProductId=%s "
                    "ORDER BY SortOrder, SchemaName",
                    (int(product_id),),
                )
                allow_dbs = [str(r[0]).strip() for r in (cur.fetchall() or []) if r and r[0]]
            finally:
                cur.close()
        except Exception:
            allow_dbs = []
        # re-gate(2/3차): pin 후보에서 시스템 DB(master/model/msdb/tempdb)·내부 DB(agent_memory) 제외.
        # **주의(3차 BLOCKER4)**: 이 시점엔 datasource dialect context 가 아직 미설정(set_active_datasource 는
        # 이후 호출)이라 `_dialects.active()` 는 MySQL 을 반환한다 → MSSQL 시스템 DB 집합을 **하드코딩**해야
        # master 등이 pin 후보에서 제대로 제거된다.
        _hard = {"master", "model", "msdb", "tempdb", "agent_memory"}
        allow_dbs = [d for d in allow_dbs if d.lower() not in _hard]
        allow_lower = {d.lower() for d in allow_dbs}
        primary_db = ""
        if product_db and product_db.lower() in allow_lower:
            primary_db = product_db                       # 명시값이 (정제된) allowlist 안일 때만
        elif allow_dbs:
            primary_db = allow_dbs[0]                      # 첫 접근가능 DB 자동 pin
        ds = dict(ds)
        ds["default_db"] = primary_db                     # 빈 문자열이면 pin 없음(가드가 2-part 차단)
    elif product_db:
        ds = dict(ds)
        ds["default_db"] = product_db
    return ds


def _product_datasource_keys(mem_conn, product_id) -> "list[str]":
    """TASK-0228 (1:N): 제품에 바인딩된 datasource 키 목록(primary 우선). 단일 바인딩(레거시)은 1건.

    join 테이블(WebProductDatasources) 우선, 부재/미이전 시 primary(WebProducts.DatasourceKey) 폴백.
    소문자 정규화. 미바인딩 제품은 []."""
    if not product_id or int(product_id) <= 0:
        return []
    keys: list[str] = []
    try:
        cur = mem_conn.cursor()
        try:
            try:
                cur.execute(
                    "SELECT LOWER(DatasourceKey) FROM WebProductDatasources WHERE ProductId=%s "
                    "ORDER BY IsPrimary DESC, SortOrder ASC, DatasourceKey ASC",
                    (int(product_id),),
                )
                keys = [str(r[0]).strip().lower() for r in (cur.fetchall() or []) if r and r[0]]
            except Exception:
                keys = []
            if not keys:
                cur.execute("SELECT DatasourceKey FROM WebProducts WHERE Id=%s LIMIT 1", (int(product_id),))
                r = cur.fetchone()
                if r and r[0] and str(r[0]).strip():
                    keys = [str(r[0]).strip().lower()]
        finally:
            cur.close()
    except Exception:
        return []
    # dedup(순서 보존)
    seen: set[str] = set()
    out: list[str] = []
    for k in keys:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _datasource_allow_schemas(mem_conn, product_id, datasource_key) -> "list[str]":
    """TASK-0228 (1:N): 특정 (product, datasource) 의 접근가능 스키마(DB) 목록 — datasource 차원 격리.

    WebProductDatabases.DatasourceKey 차원으로만 조회한다. 원본 케이스 보존(case-sensitive collation).

    **보안 (REV-0228 MAJOR-2 — fail-closed)**: 본 함수는 멀티 datasource(≥2 바인딩) 라우터의 datasource
    별 allowlist 를 만든다. 차원 컬럼이 부재(미이전)하거나 조회가 실패하면 **차원 없는 전체 목록으로
    폴백하지 않는다** — 그 폴백은 product 의 모든 DB(다른 datasource 것 포함)를 이 datasource 의
    allowlist 로 broadcast 해 교차노출이 된다(REV-0228 발견). 대신 **[] 반환(fail-closed)** — 차원
    컬럼은 `_ensure_web_product_datasources_schema` 가 join 테이블과 같은 마이그레이션에서 추가하므로,
    ≥2 바인딩이 존재하면 컬럼도 정상 존재해야 한다. 부재면 마이그레이션 비정상 → 접근 0 이 안전."""
    if not product_id or int(product_id) <= 0:
        return []
    dsk = (str(datasource_key).strip().lower() if datasource_key else "")
    try:
        cur = mem_conn.cursor()
        try:
            cur.execute(
                "SELECT SchemaName FROM WebProductDatabases WHERE ProductId=%s AND LOWER(DatasourceKey)=%s "
                "ORDER BY SortOrder, SchemaName",
                (int(product_id), dsk),
            )
            return [str(r[0]).strip() for r in (cur.fetchall() or []) if r and r[0]]
        finally:
            cur.close()
    except Exception as exc:
        # 차원 컬럼 부재/조회 실패 → fail-closed(접근 0). 전체 목록 broadcast(교차노출) 금지.
        logging.getLogger("agent_core").warning(
            "datasource_allow_schemas_failclosed product_id=%s ds=%s err=%r — 접근 0(차원 컬럼 확인)",
            product_id, dsk, exc,
        )
        return []


def _resolve_product_datasources(mem_conn, product_id) -> "list[dict]":
    """TASK-0228 (1:N): 제품에 바인딩된 **여러** datasource 를 해석한다 (primary 먼저).

    각 dict 는 `_resolve_product_datasource` 와 동일 shape + 다음 런타임 메타:
      - `_label`: 바인딩 키(소문자 라벨) — tool 의 `datasource` 인자가 이 라벨로 선택한다.
      - `_allow_schemas`: 이 (product, datasource) 의 접근가능 스키마(DB) 목록 — **datasource 차원 격리**.
      - `_is_primary`: 첫 바인딩 여부.

    보안: 각 datasource 의 allowlist 는 그 datasource 의 WebProductDatabases 행만으로 구성된다
    (datasource A 의 DB 가 B 컨텍스트로 새지 않음, Codex-3 격리 동형). 미등록/복호불가 키는 skip
    (silent — 단일 키 경로의 fail-closed 와 달리, 여러 키 중 하나가 죽어도 나머지는 동작해야 함;
    호출부가 빈 리스트면 단일 경로로 폴백). flag OFF 시 []."""
    if not cfg.AGENT_MULTI_DATASOURCE_ENABLED:
        return []
    keys = _product_datasource_keys(mem_conn, product_id)
    if len(keys) < 2:
        return []  # 0~1 바인딩 = 기존 단일 경로(_resolve_product_datasource)가 처리
    from modules import datasources as _datasources
    out: list[dict] = []
    for i, key in enumerate(keys):
        ds = _datasources.resolve(mem_conn, key)
        if not ds:
            logging.getLogger("agent_core").warning(
                "multi_ds_resolve_skip product_id=%s key=%s — 미등록/복호불가(이 키만 skip)", product_id, key,
            )
            continue
        ds = dict(ds)
        allow = _datasource_allow_schemas(mem_conn, product_id, key)
        # MSSQL primary(pin) DB: 단일 경로와 동일 규칙(allowlist 멤버만 pin, 시스템 DB 제외).
        if (ds.get("engine") or "mysql").strip().lower() == "mssql":
            _hard = {"master", "model", "msdb", "tempdb", "agent_memory"}
            _allow_clean = [d for d in allow if d.lower() not in _hard]
            ds["default_db"] = _allow_clean[0] if _allow_clean else ""
        ds["_label"] = key
        ds["_allow_schemas"] = allow
        ds["_is_primary"] = (i == 0)
        out.append(ds)
    return out if len(out) >= 2 else []


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
    attachment_ids: list[int] | None = None,
    new_attachment_ids: list[int] | None = None,
    image_inline_path: str | None = None,
    text_inline_path: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Product whitelist + 첨부 채널을 요청별 contextvar 로 설정한 뒤 실제 루프를 호출하는 얇은 래퍼.

    run_id: None 이면 루프가 새로 생성(현행 in-process 경로). ask-worker 가 job claim
    별로 stable run_id 를 주입할 때 사용(TASK-0169 — KV/steps/cancel 의 전 구간 correlate
    + lease fencing 정합).
    """
    set_active_schema_allowlist(allowed_schemas)
    # TASK-0137: 첨부 메타를 os.environ 대신 contextvar 로 — 동시 요청 격리.
    _att_tokens = (
        _ATTACHMENT_IDS_CTX.set(",".join(str(int(i)) for i in (attachment_ids or []))),
        _NEW_ATTACHMENT_IDS_CTX.set(",".join(str(int(i)) for i in (new_attachment_ids or []))),
        _INLINE_IMAGE_PATH_CTX.set(image_inline_path or ""),
        _INLINE_TEXT_PATH_CTX.set(text_inline_path or ""),
    )
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
            run_id=run_id,
        )
    finally:
        clear_active_schema_allowlist()
        # 멀티 datasource(P5 M1): run-wide datasource·dialect 컨텍스트를 **예외 안전**하게 해제.
        # 다른 request-scoped ContextVar 와 동일 위치(run_agent finally)에서 — _run_agent_core
        # 의 평문 해제는 예외 시 누락돼 ask-worker 스레드 재사용 stale 위험(REV-20260610-P5 M1).
        cfg.set_active_datasource(None)
        _ATTACHMENT_IDS_CTX.reset(_att_tokens[0])
        _NEW_ATTACHMENT_IDS_CTX.reset(_att_tokens[1])
        _INLINE_IMAGE_PATH_CTX.reset(_att_tokens[2])
        _INLINE_TEXT_PATH_CTX.reset(_att_tokens[3])


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
    run_id: str | None = None,
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
            "BEDROCK_GATEWAY_API_KEY (권장) / LOCAL_LLM_API_KEY "
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
    # run_id: caller(ask-worker)가 claim 별로 주입하면 그대로, 아니면(in-process) 새로 생성.
    run_id = run_id or _new_run_id()
    result["run_id"] = run_id
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

    # 멀티 datasource (P1): product 에 바인딩된 datasource 좌표 해석 (None=기본 단일 MySQL).
    # flag OFF / 미바인딩 시 None → connect_with_retry 가 기존 경로 그대로 (동작 0 변경).
    # 명시 바인딩 + 미등록 키 → fail-closed (REV-0187 M-2: 운영 DB 폴백 금지, run 중단).
    # TASK-0228 (1:N): 제품이 ≥2 datasource 에 바인딩됐는지 먼저 본다. ≥2 면 멀티 datasource 라우터
    # 경로(LLM 이 tool 마다 datasource 선택), 0~1 이면 기존 단일 경로(_resolve_product_datasource).
    # REV-0228 MAJOR-3: 멀티 datasource 해석 실패를 조용히 [] 로 삼키면, ≥2 바인딩 제품이 단일
    # 경로(primary)로 silent 강등되며 single-path allowlist(차원 무필터)가 넓어지는 fail-open 이 된다.
    # bare except 금지 — 로그로 가시화한다(차원 격리 의도 보존). resolve 내부의 미등록 키는 이미
    # 개별 skip 처리되므로 여기 도달하는 예외는 transient(연결 등)이며, [] 면 단일 경로가 받되 그
    # 경로 자체가 fail-closed(_resolve_product_datasource).
    _multi_ds_list: list[dict] = []
    try:
        _multi_ds_list = _resolve_product_datasources(mem_conn, product_id)
    except Exception as exc:
        logging.getLogger("agent_core").warning(
            "resolve_product_datasources_failed product_id=%s err=%r — 단일 경로 폴백", product_id, exc,
        )
        _multi_ds_list = []
    _ds_router = None
    _ds = None
    if _multi_ds_list:
        # 멀티 datasource: 라우터가 tool 별 연결·allowlist·engine 을 관리. primary 를 db_conn 기본값으로 연결.
        import modules.tools as _tools_mod
        def _connect_ds(ds_dict):
            return connect_with_retry(database=None, autocommit=True, datasource=ds_dict)
        _ds_router = _tools_mod._DatasourceRouter(_multi_ds_list, _connect_ds)
        try:
            db_conn = _ds_router.conn_for(_ds_router.resolve_label(None))  # primary lazy 연결
        except Exception as e:
            cfg.CURRENT_RUN_ID = ""
            result["error"] = f"DB 연결 실패(멀티 datasource primary): {e}"
            if output_mode == "console":
                console.print(Panel.fit(result["error"], title="오류"))
            return result
        # primary datasource 를 run-wide 기본 컨텍스트로(grounding·첫 tool 기본값).
        _ds = _multi_ds_list[0]
    else:
        # 단일 datasource (또는 미바인딩/flag OFF): 기존 경로 — 동작 0 변경.
        try:
            _ds = _resolve_product_datasource(mem_conn, product_id)
        except DatasourceResolutionError as e:
            cfg.CURRENT_RUN_ID = ""
            result["error"] = f"데이터 소스 설정 오류: {e}"
            if output_mode == "console":
                console.print(Panel.fit(result["error"], title="오류"))
            return result
        _data_db = None if _ds else DB_CONNECT_DB  # ds 경로는 database=None(schema-prefixed 강제, M-1)
        try:
            db_conn = connect_with_retry(database=_data_db, autocommit=True, datasource=_ds)
        except Exception as e:
            # DB 연결 실패 시 연결 없이 진행 (도구에서 개별 처리)
            db_conn = None
            try:
                db_conn = connect_with_retry(database=None, autocommit=True, datasource=_ds)
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
        # 저정보 발화(인사/메타)는 origin 으로 고정하지 않는다 — 다음 실질 발화가 origin.
        if not prev_origin and not _is_low_information_request(user_message):
            save_memory_kv(mem_conn, cid, "origin_request", user_message)
            prev_origin = user_message
        if not thread_goal and prev_origin:
            thread_goal = _derive_topic(prev_origin, max_len=200)
            save_memory_kv(mem_conn, cid, "thread_goal", thread_goal)

    # ── 지식 주입 ──
    # 멀티 datasource: 이 run 의 datasource 키·엔진을 ContextVar 로 설정한다(run-wide).
    #  - P3(Codex-3): grounding 읽기(_load_schema_list 등)가 ds_fact_like/strip 으로 datasource
    #    키만 매치(기본은 ds 키 제외) → 교차노출 차단.
    #  - P5: tools.py 의 introspection/sample SQL 이 dialects.active() 로 엔진별 방언 산출.
    # **본 set 은 grounding 직후 해제하지 않는다** — 이후 tool 루프(execute_sql/describe_*)도 같은
    # datasource·dialect 컨텍스트여야 하기 때문. 해제는 run_agent 의 finally(다른 request-scoped
    # ContextVar 와 동일 위치)에서 **예외 안전**하게 수행한다(P5 M1). 매 run 시작에서 다시 set 한다.
    # TASK-0219: 스코핑 식별자는 DatasourceKey 라벨이 아닌 **엔드포인트 해시**(scope_key) —
    # 라벨은 admin rename 가능한 단순 식별자라 안정 스코프 키 역할 불가. fact/RAG write·read 가
    # 같은 해시를 쓰도록 resolve dict 의 scope_key 사용(폴백: 라벨 — .env 레거시 dict).
    cfg.set_active_datasource(
        ((_ds.get("scope_key") or _ds.get("key")) if _ds else None),
        engine=(_ds.get("engine") if _ds else None),
        # TASK-0205 B1: effective default_db(제품별 override 반영) 를 cross-DB 가드에 주입.
        default_db=(_ds.get("default_db") if _ds else None),
    )
    # TASK-0228 (1:N): 멀티 datasource 라우터 등록. tool 호출마다 datasource 선택 + 그 컨텍스트 활성화.
    # 등록 token 은 finally 에서 reset(예외 안전). 라우터는 primary 를 기본 활성 컨텍스트로 둔다.
    _ds_router_token = None
    _run_tool_defs = TOOL_DEFINITIONS
    if _ds_router is not None:
        import modules.tools as _tools_reg
        _ds_router_token = _tools_reg.set_active_ds_router(_ds_router)
        _ds_router.activate(_ds_router.resolve_label(None))  # primary allowlist/engine 활성
        # 각 도구에 datasource 선택 인자(enum=바인딩 라벨) 주입한 정의 사용.
        try:
            _run_tool_defs = _tools_reg.build_tool_definitions_for_datasources(
                TOOL_DEFINITIONS, _ds_router.labels()
            )
        except Exception:
            _run_tool_defs = TOOL_DEFINITIONS
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
    # ── P6/§3.5: 활성 datasource 엔진 방언 주입 ──────────────────────────────
    # base SYSTEM_PROMPT 는 "MySQL analyst"(백틱·LIMIT)를 지시한다. 활성 datasource 가 MSSQL 이면
    # LLM 이 MySQL 문법을 생성해 execute_sql 이 실패하므로, T-SQL 규칙을 명시 주입한다(보안경계가
    # 무자격/cross-DB 를 거부하므로 스키마 명시도 강제 안내).
    try:
        _active_engine = cfg.get_active_datasource_engine()
    except Exception:
        _active_engine = "mysql"
    if str(_active_engine).lower() == "mssql":
        system_content += _MSSQL_DIALECT_GUIDANCE
        # TASK-0206: 허용 DB 목록 + 현재(primary) DB 를 동적 주입(DB-단위 — 3-part cross-DB 안내).
        # re-gate(4차): grounding 에는 **원본 케이스** DB명(display var)을 쓴다(case-sensitive collation 대응).
        try:
            import modules.tools as _tools
            _allow_disp = _tools._ACTIVE_SCHEMA_ALLOWLIST_DISPLAY.get()
            if _allow_disp:
                _allow_dbs = sorted(_allow_disp, key=str.lower)
            else:
                _allow = _tools._ACTIVE_SCHEMA_ALLOWLIST.get()
                _allow_dbs = sorted(_allow) if _allow else []
        except Exception:
            _allow_dbs = []
        _primary = (_ds.get("default_db") if _ds else None) or (_allow_dbs[0] if _allow_dbs else None)
        if _allow_dbs:
            system_content += (
                f"\n- **Current (default) database**: `{_primary}` — use 2-part `schema.table` for it.\n"
                f"- **Allowed databases** (use 3-part `db.schema.table` for the others): "
                f"{', '.join('`' + d + '`' for d in _allow_dbs)}.\n"
                f"- Only these databases are queryable. System databases (master/model/msdb/tempdb), the `sys`/"
                f"`guest` schemas, and server-info functions (SERVERPROPERTY/SUSER_SNAME/…) are blocked.\n"
            )
    # ── TASK-0228 (1:N): 멀티 datasource grounding ──────────────────────────────
    # 제품이 ≥2 datasource 에 바인딩되면, LLM 이 각 datasource 의 라벨·엔진·접근가능 DB 를 알아야
    # tool 호출 시 `datasource` 인자로 올바른 대상을 고른다. (사용자 요청: 제품 프롬프트/어시스턴트가
    # 접근 가능한 데이터소스의 DB 를 인지해야 함.) 좌표/비밀번호는 노출하지 않는다(라벨·엔진·DB명만).
    if _ds_router is not None:
        try:
            _ds_desc = _ds_router.describe()
        except Exception:
            _ds_desc = []
        if _ds_desc:
            _lines = ["\n\n## ACCESSIBLE DATASOURCES (multi-datasource)\n"]
            _lines.append(
                "이 제품은 여러 데이터소스에 연결돼 있다. 각 도구(execute_sql/describe_table/…) 호출 시 "
                "`datasource` 인자에 아래 **라벨**을 넣어 대상을 고른다(미지정 시 기본=primary). 한 질문이 "
                "여러 데이터소스를 참조하면 도구를 데이터소스별로 나눠 호출하라. 데이터소스 간 직접 JOIN 은 "
                "불가하다(각각 조회 후 결과를 합쳐 분석).\n"
            )
            for d in _ds_desc:
                _eng = str(d.get("engine") or "mysql")
                _schemas = d.get("schemas") or []
                _tag = " (기본/primary)" if d.get("is_primary") else ""
                _dbs = ", ".join(f"`{s}`" for s in _schemas) if _schemas else "(접근 가능 DB 미설정)"
                _lines.append(f"- **{d.get('label')}**{_tag} — 엔진 {_eng}, 접근 가능 DB: {_dbs}")
            system_content += "\n".join(_lines) + "\n"

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
        # TASK-0228 (1:N): 멀티 datasource 면 각 도구에 `datasource` 선택 인자를 주입한 정의를 쓴다.
        use_tools = None if finalize_now else _run_tool_defs
        try:
            response_message = _call_llm(
                client, messages, model,
                temperature=temperature,
                tools=use_tools,
                conversation_id=cid,  # TASK-0163: race-free 토큰 귀속 (in-process 동시 ask)
                run_id=run_id,
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
            # B1 가드: 최종 답변에 tool_notes JSON envelope 가 누수됐으면 결정적으로
            # 제거(산문만 남김). 답변 전체가 envelope 면 빈 문자열 → 아래 재요청 루프.
            raw_answer = _strip_leaked_tool_notes(raw_answer)
            if not raw_answer.strip():
                # Reasoning/reasoning_content can contain provider-private chain of thought.
                # Never surface it as a user-facing answer; ask the model for a concise
                # answer based on tool results instead.
                if step_count > 0 and empty_retries < 3:
                    empty_retries += 1
                    messages.append({
                        "role": "user",
                        "content": "Write your answer in Korean Markdown based on the tool results above.",
                    })
                    continue
                if empty_retries < 3:
                    empty_retries += 1
                    messages.append({
                        "role": "user",
                        "content": "Write a concise Korean Markdown answer. Do not expose hidden reasoning; summarize the result only.",
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
            # TASK-0178: 단계 narration(work/why)을 tool 호출 인자에서 추출 + 제거.
            # Bedrock gateway 가 tool_use 턴의 text content 를 strip 해 content 경로
            # (tool_notes JSON, TASK-0177)는 무력했음 — 인자는 안정 전달되므로 이쪽을 우선.
            # pop 으로 실제 도구 실행/args 저장 전에 제거(narration 은 실행에 무관).
            arg_work = ""
            arg_reason = ""
            if isinstance(tool_args, dict):
                arg_work = str(tool_args.pop("work", "") or "").strip()
                arg_reason = str(tool_args.pop("reason", "") or "").strip()
            note = tool_notes[note_idx] if note_idx < len(tool_notes) else {}
            # 우선순위: tool 인자(arg) → content tool_notes(다른 provider) → derived fallback.
            work_text = arg_work or str((note or {}).get("work") or "").strip()
            reason_text = arg_reason or str((note or {}).get("reason") or "").strip()
            work_source = "llm" if work_text else ""
            reason_source = "llm" if reason_text else ""
            if not work_text:
                work_text = _derive_step_work(tool_name, tool_args)
                work_source = "derived" if work_text else ""
            if not reason_text:
                reason_text = _derive_step_reason(tool_name, tool_args)
                reason_source = "derived" if reason_text else ""

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
            _clear_cancel_request(mem_conn, cid, run_id=run_id)
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
                    # TASK-0241: 취소된 run 은 종종 superseded(사용자가 취소 후 같은 대화에
                    # 즉시 재요청 → 새 run 이 last_status_run_id 인계) 다. only_if_current_run 으로
                    # 새 run 의 (NEW, processing) 상태를 (OLD, canceled) 로 클로버하지 않게 가드한다.
                    set_run_status(mem_conn, cid, "canceled", run_id=run_id, duration_ms=duration_ms, error="", only_if_current_run=True)
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
            # TASK-0241: terminal write 는 모두 supersede 가드 — lease-fencing 으로 박탈된
            # (superseded) run 이 현재 run 의 상태를 덮어쓰지 못하게 한다(canceled 와 대칭).
            set_run_status(mem_conn, cid, "error", run_id=run_id, duration_ms=duration_ms, error=result["error"], only_if_current_run=True)
        except Exception:
            pass
    else:
        try:
            set_run_status(mem_conn, cid, "done", run_id=run_id, duration_ms=duration_ms, error="", only_if_current_run=True)
        except Exception:
            pass
    if not pending_delete and not canceled_by_user:
        try:
            _clear_cancel_request(mem_conn, cid, run_id=run_id)
        except Exception:
            pass

    # DB 연결 정리
    # TASK-0228 (1:N): 라우터가 활성이면 db_conn 은 라우터 소유(primary) 연결이므로, 라우터가 모든
    # datasource 연결을 일괄 close 한다(중복 close 금지). 단일 datasource 면 종전대로 db_conn 만 close.
    if _ds_router is not None:
        try:
            _ds_router.close_all()
        except Exception:
            pass
        if _ds_router_token is not None:
            try:
                import modules.tools as _tools_cl
                _tools_cl.reset_active_ds_router(_ds_router_token)
            except Exception:
                pass
    else:
        try:
            if db_conn:
                db_conn.close()
        except Exception:
            pass
    try:
        mem_conn.close()
    except Exception:
        pass
    # 멀티 datasource(P5): run-wide datasource·dialect 컨텍스트 해제 (스레드 재사용 stale 방지).
    cfg.set_active_datasource(None)
    cfg.CURRENT_RUN_ID = ""

    return result


# ══════════════════════════════════════════════════════════════════
#  대화 관리 유틸리티 (CLI/Web에서 사용)
# ══════════════════════════════════════════════════════════════════

def list_all_conversations() -> list[dict]:
    """모든 대화 목록을 반환."""
    # M4: PG read path
    from modules.runtime_backend import _read_runtime_pg, AGENT_RUNTIME_READ_BACKEND
    if AGENT_RUNTIME_READ_BACKEND == "postgres":
        pg_result = _read_runtime_pg("list_conversations", limit=50)
        if pg_result is not None:
            return [{"conversation_id": r[0], "topic": r[1], "created_at": r[2]} for r in pg_result]
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
    # M4: PG read path
    from modules.runtime_backend import _read_runtime_pg, AGENT_RUNTIME_READ_BACKEND
    if AGENT_RUNTIME_READ_BACKEND == "postgres":
        pg_rows = _read_runtime_pg("get_conv_messages_full",
                                   conversation_id=conversation_id, limit=limit)
        if pg_rows is not None:
            result = []
            for pg_id, role, content, tool_calls, tool_call_id, name, created_at in pg_rows:
                msg = {
                    "id": pg_id,
                    "role": role,
                    "content": "" if tool_calls else (content or ""),
                    "created_at": (
                        created_at.isoformat()
                        if hasattr(created_at, "isoformat")
                        else str(created_at or "")
                    ),
                }
                if tool_calls:
                    msg["tool_calls"] = tool_calls  # already Python obj from JSONB
                if tool_call_id:
                    msg["tool_call_id"] = tool_call_id
                if name:
                    msg["name"] = name
                result.append(msg)
            return result
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
        from modules.db import _pg_available
        if _pg_available():
            from modules.memory import _ensure_pg_schema
            result = _ensure_pg_schema()
            console.print(
                f"[green]KB Postgres schema 적용 완료[/green]: "
                f"tables={result.get('tables_present', [])}, "
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
    parser.add_argument("--ask-worker", action="store_true", help="ask 실행 워커 (out-of-process, TASK-0169)")
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

    if args.ask_worker:
        # TASK-0169: out-of-process ask 실행 워커. ask_jobs 큐에서 claim 해 run_agent 실행.
        try:
            from modules.ask import run_ask_worker_loop
            run_ask_worker_loop()
        except ImportError:
            console.print("[yellow]ask 워커를 찾을 수 없습니다.[/yellow]")
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
