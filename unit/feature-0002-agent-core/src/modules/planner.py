from datetime import datetime, timezone
import mysql.connector
import re
import sys
import time
__all__ = [
    "_advance_pending_steps",
    "_apply_meta_exploration_budget",
    "_build_discovery_plan",
    "_build_discovery_sql",
    "_build_fast_aggregate_plan",
    "_build_fast_aggregate_sql",
    "_build_fast_sql_for_object",
    "_build_insight_object_fast_plan",
    "_build_knowledge_sql_fallback_plan",
    "_build_object_scoped_schema_meta",
    "_can_force_fast_aggregate",
    "_clear_last_resolved_object_kv",
    "_collect_insight_candidates_from_knowledge",
    "_count_recent_meta_steps",
    "_extract_anchor_table_ref",
    "_extract_candidate_refs_from_text",
    "_extract_sql_from_compose_payload",
    "_find_candidate_by_ref",
    "_find_unique_candidate_by_table",
    "_interleave_candidates_by_schema",
    "_llm_compose_sql_for_selected_object",
    "_llm_compose_sql_from_knowledge",
    "_llm_pick_table_insight_candidate",
    "_llm_pick_table_insight_candidate_in_batches",
    "_llm_review_sql_grounding",
    "_load_known_schemas_from_kv",
    "_load_pending_steps",
    "_load_table_columns_snapshot",
    "_load_table_insight_candidates",
    "_maybe_auto_discover",
    "_parse_table_insight_ref",
    "_prefix_use_schema",
    "_prepare_insight_candidates_for_llm",
    "_review_sql_for_selected_object",
    "_rewrite_schema_in_sql",
    "_save_pending_steps",
    "_sql_mentions_schema",
    "_validate_step_and_record",
    "_verify_table_exists",
    "plan_next_step",
]


"""LLM planning, step management, SQL composition."""
from .config import *
from . import config as cfg
import json, re, time
from typing import Any

def _parse_table_insight_ref(fact_key: str) -> tuple[str, str]:
    key = str(fact_key or "").strip()
    if not key.startswith("table_insight:"):
        return "", ""
    ref = key.split(":", 1)[1].strip()
    if "." not in ref:
        return "", ""
    schema, table = ref.split(".", 1)
    schema = _sanitize_ident_part(schema)
    table = _sanitize_ident_part(table)
    if not schema or not table:
        return "", ""
    return schema, table


def _collect_insight_candidates_from_knowledge(
    knowledge: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(knowledge, dict):
        return []
    best: dict[str, dict[str, Any]] = {}

    def _parse_ref_from_fact_key(raw_key: str) -> tuple[str, str]:
        key = str(raw_key or "").strip()
        if not key:
            return "", ""
        ref = ""
        if key.startswith("table_insight:") or key.startswith("table_pref:") or key.startswith("insight:"):
            ref = key.split(":", 1)[1].strip()
        if "." not in ref:
            return "", ""
        schema_raw, table_raw = ref.split(".", 1)
        schema = _sanitize_ident_part(schema_raw)
        table = _sanitize_ident_part(table_raw)
        if not schema or not table:
            return "", ""
        return schema, table

    def _upsert(
        schema: str,
        table: str,
        summary: str,
        weight: int,
        updated_at: str,
        source: str,
        fact_key: str,
        source_type: str,
        source_run_id: str,
    ) -> None:
        safe_schema = _sanitize_ident_part(schema)
        safe_table = _sanitize_ident_part(table)
        if not safe_table:
            return
        ref = f"{safe_schema.lower()}.{safe_table.lower()}" if safe_schema else safe_table.lower()
        item = {
            "schema": safe_schema,
            "table": safe_table,
            "ref": ref,
            "fact_key": str(fact_key or "").strip() or f"table_insight:{safe_schema}.{safe_table}",
            "fact_text": _trim_fact_text(str(summary or ""), max_len=900),
            "weight": max(1, int(weight or 1)),
            "updated_at": str(updated_at or "").strip(),
            "source_type": str(source_type or "").strip() or "schema_insight",
            "source_run_id": str(source_run_id or "").strip(),
            "source": str(source or "").strip() or "table_insight",
        }
        prev = best.get(ref)
        if prev is None:
            best[ref] = item
            return
        prev_weight = int(prev.get("weight", 0) or 0)
        curr_weight = int(item.get("weight", 0) or 0)
        if curr_weight > prev_weight:
            best[ref] = item
            return
        if curr_weight == prev_weight and str(item.get("updated_at") or "") > str(prev.get("updated_at") or ""):
            best[ref] = item

    for item in knowledge.get("insight_objects") or []:
        if not isinstance(item, dict):
            continue
        try:
            weight_val = int(item.get("weight", 1) or 1)
        except Exception:
            weight_val = 1
        _upsert(
            str(item.get("schema") or "").strip(),
            str(item.get("table") or "").strip(),
            str(item.get("summary") or "").strip(),
            weight_val,
            str(item.get("updated_at") or "").strip(),
            "insight_objects",
            str(item.get("fact_key") or "").strip(),
            str(item.get("source_type") or "").strip(),
            str(item.get("source_run_id") or "").strip(),
        )

    for item in knowledge.get("rag_objects") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("object_type") or "").strip().lower() != "table":
            continue
        try:
            weight_val = int(item.get("weight", 1) or 1)
        except Exception:
            weight_val = 1
        _upsert(
            str(item.get("schema") or "").strip(),
            str(item.get("table") or "").strip(),
            str(item.get("summary") or "").strip(),
            weight_val,
            str(item.get("updated_at") or "").strip(),
            "rag_objects",
            str(item.get("object_key") or "").strip(),
            str(item.get("source_type") or "").strip(),
            str(item.get("source_run_id") or "").strip(),
        )

    for bucket_name in ("facts", "global_facts"):
        for item in knowledge.get(bucket_name) or []:
            if not isinstance(item, dict):
                continue
            fact_key = str(item.get("key") or item.get("fact_key") or "").strip()
            schema, table = _parse_ref_from_fact_key(fact_key)
            if not schema or not table:
                continue
            source_type = str(item.get("source_type") or "").strip()
            source_run_id = str(item.get("source_run_id") or "").strip()
            try:
                base_weight = int(item.get("weight", 1) or 1)
            except Exception:
                base_weight = 1
            boost = 0
            # Prevent table_pref over-amplification from off-intent executions.
            if fact_key.startswith("table_pref:") and source_type == "user_confirm":
                boost += 1
            if source_type in {"user_confirm", "insight"}:
                boost += 1
            _upsert(
                schema,
                table,
                str(item.get("text") or item.get("summary") or "").strip(),
                base_weight + boost,
                str(item.get("updated_at") or "").strip(),
                f"{bucket_name}_key",
                fact_key,
                source_type,
                source_run_id,
            )

    return sorted(
        best.values(),
        key=lambda x: (
            int(x.get("weight", 0) or 0),
            str(x.get("updated_at") or ""),
        ),
        reverse=True,
    )


def _load_table_insight_candidates(
    conn,
    scope_key: str | None = None,
    max_candidates: int = 0,
    hint_tokens: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not conn:
        return []
    conversation_ids = _global_fact_conversation_ids(include_shared=True)
    if not conversation_ids:
        return []
    cid_placeholders = ",".join(["%s"] * len(conversation_ids))
    fetch_limit = max(0, int(max_candidates or 0))
    limit_clause = ""
    if fetch_limit > 0:
        limit_clause = " LIMIT %s"
    scope_clause, scope_params = _scope_filter_sql(
        _scope_candidates(scope_key or FACT_SCOPE_COMMON),
    )
    cur = conn.cursor()
    rows: list[tuple[Any, ...]] = []
    try:
        cur.execute(
            f"""
SELECT e.FactKey, COALESCE(t.TextContent, '') AS FactText, e.Weight, e.UpdatedAt, e.SourceType, e.SourceRunId
FROM AgentMemoryFactEntries e
LEFT JOIN AgentMemoryTexts t ON t.TextHash = e.TextHash
WHERE e.ConversationId IN ({cid_placeholders})
  AND e.FactKey LIKE 'table_insight:%'{scope_clause}
ORDER BY e.Weight DESC, e.UpdatedAt DESC, e.Id DESC
{limit_clause}
            """,
            [*conversation_ids, *scope_params, *([fetch_limit] if fetch_limit > 0 else [])],
        )
        rows.extend(cur.fetchall() or [])
    except Exception:
        try:
            cur.execute(
                f"""
SELECT FactKey, FactText, Weight, UpdatedAt, '' AS SourceType, '' AS SourceRunId
FROM AgentMemoryFacts
WHERE ConversationId IN ({cid_placeholders})
  AND FactKey LIKE 'table_insight:%'{scope_clause}
ORDER BY Weight DESC, UpdatedAt DESC
{limit_clause}
                """,
                [*conversation_ids, *scope_params, *([fetch_limit] if fetch_limit > 0 else [])],
            )
            rows.extend(cur.fetchall() or [])
        except Exception:
            rows = []
    finally:
        cur.close()

    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row:
            continue
        fact_key = str(row[0] or "").strip()
        schema, table = _parse_table_insight_ref(fact_key)
        if not schema or not table:
            continue
        ref = f"{schema.lower()}.{table.lower()}"
        item = {
            "schema": schema,
            "table": table,
            "ref": ref,
            "fact_key": fact_key,
            "fact_text": str(row[1] or "").strip(),
            "weight": int(row[2]) if row[2] is not None else 1,
            "updated_at": row[3],
            "source_type": str(row[4] or "").strip() or "schema_insight",
            "source_run_id": str(row[5] or "").strip(),
            "source": "table_insight",
        }
        if ref not in best:
            best[ref] = item
            continue
        prev = best[ref]
        prev_weight = int(prev.get("weight", 0) or 0)
        prev_updated = prev.get("updated_at")
        current_updated = item.get("updated_at")
        if int(item["weight"]) > prev_weight:
            best[ref] = item
            continue
        if int(item["weight"]) == prev_weight and str(current_updated) > str(prev_updated):
            best[ref] = item
    ordered = sorted(
        best.values(),
        key=lambda x: (
            int(x.get("weight", 0) or 0),
            str(x.get("updated_at") or ""),
        ),
        reverse=True,
    )
    if fetch_limit > 0:
        return ordered[: max(1, int(fetch_limit))]
    return ordered


def _find_candidate_by_ref(candidates: list[dict[str, Any]], ref_text: str) -> dict[str, Any] | None:
    ref_raw = str(ref_text or "").strip().lower()
    if not ref_raw:
        return None
    ref_raw = ref_raw.replace("`", " ")
    normalized_refs: list[str] = []
    dotted_matches = re.findall(r"([a-z0-9_]+)\.([a-z0-9_]+)", ref_raw)
    for schema, table in dotted_matches:
        normalized_refs.append(f"{schema}.{table}")
    if not normalized_refs:
        compact = " ".join(ref_raw.split())
        if compact:
            normalized_refs.append(compact)
    tokens = re.findall(r"[a-z0-9_]+", ref_raw)
    normalized_tables: list[str] = []
    if tokens:
        normalized_tables.extend(tokens)
        normalized_tables.append(tokens[-1])
    for item in candidates:
        if not isinstance(item, dict):
            continue
        schema = str(item.get("schema") or "").strip().lower()
        table = str(item.get("table") or "").strip().lower()
        if not table:
            continue
        ref = f"{schema}.{table}" if schema else table
        for norm_ref in normalized_refs:
            if ref == norm_ref:
                return item
        for norm_table in normalized_tables:
            if table == norm_table:
                return item
        if "." not in ref_raw and table == ref_raw.replace(" ", ""):
            return item
    return None


def _find_unique_candidate_by_table(
    candidates: list[dict[str, Any]],
    table_text: str,
) -> dict[str, Any] | None:
    table_raw = _sanitize_ident_part(str(table_text or "").strip()).lower()
    if not table_raw:
        return None
    matched: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        table = str(item.get("table") or "").strip().lower()
        if table and table == table_raw:
            matched.append(item)
    if len(matched) == 1:
        return matched[0]
    return None


def _extract_candidate_refs_from_text(
    text: str,
    candidates: list[dict[str, Any]],
    prefer_schema: str | None = None,
) -> list[str]:
    raw = str(text or "").strip().lower()
    if not raw or not candidates:
        return []
    prefer_schema_norm = _sanitize_ident_part(str(prefer_schema or "").strip()).lower()
    matched: list[tuple[int, str, int]] = []
    seen: set[str] = set()
    for idx, item in enumerate(candidates):
        if not isinstance(item, dict):
            continue
        schema = _sanitize_ident_part(str(item.get("schema") or "").strip()).lower()
        table = _sanitize_ident_part(str(item.get("table") or "").strip()).lower()
        if not table:
            continue
        ref = f"{schema}.{table}" if schema else table
        if ref in seen:
            continue
        seen.add(ref)
        has_match = False
        if schema:
            pattern_ref = rf"(?<![a-z0-9_`])`?{re.escape(schema)}`?\s*\.\s*`?{re.escape(table)}`?(?![a-z0-9_`])"
            if re.search(pattern_ref, raw):
                has_match = True
        if not has_match:
            pattern_table = rf"(?<![a-z0-9_`])`?{re.escape(table)}`?(?![a-z0-9_`])"
            if re.search(pattern_table, raw):
                has_match = True
        if not has_match:
            continue
        weight = int(item.get("weight", 1) or 1)
        schema_boost = 1 if (prefer_schema_norm and schema and schema == prefer_schema_norm) else 0
        matched.append((schema_boost, ref, weight))
    if not matched:
        return []
    matched.sort(key=lambda x: (x[0], x[2]), reverse=True)
    return [ref for _, ref, _ in matched]


def _interleave_candidates_by_schema(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not candidates:
        return []
    schema_order: list[str] = []
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        if not isinstance(item, dict):
            continue
        schema = _sanitize_ident_part(str(item.get("schema") or "").strip()) or "__noschema__"
        if schema not in buckets:
            buckets[schema] = []
            schema_order.append(schema)
        buckets[schema].append(item)
    if not buckets:
        return []
    for schema in schema_order:
        buckets[schema] = sorted(
            buckets.get(schema, []),
            key=lambda x: (
                int(x.get("weight", 0) or 0),
                str(x.get("updated_at") or ""),
            ),
            reverse=True,
        )
    out: list[dict[str, Any]] = []
    index = 0
    while True:
        advanced = False
        for schema in schema_order:
            bucket = buckets.get(schema) or []
            if index < len(bucket):
                out.append(bucket[index])
                advanced = True
        if not advanced:
            break
        index += 1
    return out


def _prepare_insight_candidates_for_llm(
    candidates: list[dict[str, Any]],
    max_chars: int,
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    budget = max(1200, int(max_chars or 0))
    used = 0
    out: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        schema = str(item.get("schema") or "").strip()
        table = str(item.get("table") or "").strip()
        if not table:
            continue
        summary = _trim_fact_text(str(item.get("fact_text") or ""), max_len=500)
        payload_item = {
            "schema": schema,
            "table": table,
            "ref": f"{schema}.{table}" if schema else table,
            "summary": summary,
            "weight": int(item.get("weight", 1) or 1),
            "updated_at": (
                item.get("updated_at").isoformat()
                if isinstance(item.get("updated_at"), datetime)
                else str(item.get("updated_at") or "")
            ),
            "source_type": str(item.get("source_type") or "").strip(),
        }
        rough_len = len(json.dumps(payload_item, ensure_ascii=False))
        if out and used + rough_len > budget:
            continue
        out.append(payload_item)
        used += rough_len
    if not out:
        first = candidates[0]
        schema = str(first.get("schema") or "").strip()
        table = str(first.get("table") or "").strip()
        if table:
            out.append(
                {
                    "schema": schema,
                    "table": table,
                    "ref": f"{schema}.{table}" if schema else table,
                    "summary": _trim_fact_text(str(first.get("fact_text") or ""), max_len=500),
                    "weight": int(first.get("weight", 1) or 1),
                    "updated_at": (
                        first.get("updated_at").isoformat()
                        if isinstance(first.get("updated_at"), datetime)
                        else str(first.get("updated_at") or "")
                    ),
                    "source_type": str(first.get("source_type") or "").strip(),
                }
            )
    return out


def _llm_pick_table_insight_candidate_in_batches(
    request: str,
    candidates: list[dict[str, Any]],
    timeout_sec: int | None = None,
) -> tuple[dict[str, Any], float, str]:
    if not request or not candidates:
        return {}, 0.0, ""
    batch_size = max(8, int(AGENT_OBJECT_RESOLVE_BATCH_SIZE or 40))
    max_batches = max(1, int(AGENT_OBJECT_RESOLVE_MAX_BATCHES or 6))
    if len(candidates) <= batch_size:
        llm_candidates = _prepare_insight_candidates_for_llm(
            candidates,
            max_chars=max(3000, int(AGENT_RAG_DOC_MAX_CHARS) * 3),
        )
        if not llm_candidates:
            return {}, 0.0, "single_empty"
        llm_result = _llm_pick_table_insight_candidate(
            request,
            llm_candidates,
            timeout_sec=timeout_sec,
        )
        try:
            conf = float(llm_result.get("confidence", 0) or 0.0) if isinstance(llm_result, dict) else 0.0
        except Exception:
            conf = 0.0
        return llm_result if isinstance(llm_result, dict) else {}, conf, "single"

    shortlist: list[dict[str, Any]] = []
    shortlist_seen: set[str] = set()
    for batch_index, start in enumerate(range(0, len(candidates), batch_size)):
        if batch_index >= max_batches:
            break
        batch_raw = candidates[start : start + batch_size]
        batch_payload = _prepare_insight_candidates_for_llm(
            batch_raw,
            max_chars=max(3000, int(AGENT_RAG_DOC_MAX_CHARS) * 3),
        )
        if not batch_payload:
            continue
        batch_pick = _llm_pick_table_insight_candidate(
            request,
            batch_payload,
            timeout_sec=timeout_sec,
        )
        if not isinstance(batch_pick, dict):
            continue
        picked_ref = str(batch_pick.get("selected_ref") or "").strip()
        if not picked_ref:
            continue
        matched = _find_candidate_by_ref(batch_raw, picked_ref)
        if not matched:
            continue
        schema = str(matched.get("schema") or "").strip()
        table = str(matched.get("table") or "").strip()
        if not table:
            continue
        ref = f"{schema.lower()}.{table.lower()}" if schema else table.lower()
        if ref in shortlist_seen:
            continue
        shortlist_seen.add(ref)
        shortlist.append(matched)

    if not shortlist:
        return {}, 0.0, "batch_none"

    final_payload = _prepare_insight_candidates_for_llm(
        shortlist,
        max_chars=max(4000, int(AGENT_RAG_DOC_MAX_CHARS) * 4),
    )
    if not final_payload:
        return {}, 0.0, "batch_final_empty"
    final_pick = _llm_pick_table_insight_candidate(
        request,
        final_payload,
        timeout_sec=timeout_sec,
    )
    if isinstance(final_pick, dict):
        try:
            final_conf = float(final_pick.get("confidence", 0) or 0.0)
        except Exception:
            final_conf = 0.0
        picked_ref = str(final_pick.get("selected_ref") or "").strip()
        if picked_ref and _find_candidate_by_ref(shortlist, picked_ref):
            return final_pick, final_conf, "batch_final"
    return {}, 0.0, "batch_unresolved"


def _llm_pick_table_insight_candidate(
    request: str,
    candidates: list[dict[str, Any]],
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    if not request or not candidates:
        return {}
    client = _get_openai_client(timeout_sec=timeout_sec)
    if client is None:
        return {}
    payload = {
        "request": str(request or "").strip(),
        "candidates": candidates,
    }
    resp = _openai_chat_completion_with_deadline(
        client,
        AGENT_OBJECT_RESOLVE_MODEL,
        [
            {"role": "system", "content": OBJECT_RESOLVE_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        timeout_sec=timeout_sec,
    )
    if resp is None:
        return {}
    try:
        text = (resp.choices[0].message.content or "").strip()
    except Exception:
        return {}
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*```$", "", text).strip()
    mentioned_refs = _extract_candidate_refs_from_text(text, candidates)
    obj = _extract_json_object(text)
    if isinstance(obj, dict):
        picked_ref = str(obj.get("selected_ref") or "").strip()
        if not picked_ref:
            alt = obj.get("selected_object")
            if isinstance(alt, dict):
                alt_schema = _sanitize_ident_part(str(alt.get("schema") or "").strip())
                alt_table = _sanitize_ident_part(str(alt.get("table") or "").strip())
                if alt_table:
                    picked_ref = f"{alt_schema}.{alt_table}" if alt_schema else alt_table
            elif isinstance(alt, str):
                picked_ref = str(alt).strip()
        if not picked_ref:
            for key in ("selected", "object", "object_ref", "ref", "table"):
                raw = obj.get(key)
                if isinstance(raw, str) and raw.strip():
                    picked_ref = raw.strip()
                    break
        if not picked_ref and mentioned_refs:
            picked_ref = mentioned_refs[0]
        if picked_ref and not str(obj.get("selected_ref") or "").strip():
            obj = dict(obj)
            obj["selected_ref"] = picked_ref
        return obj
    plain = str(text or "").strip().strip("` ")
    if plain:
        matched = _find_candidate_by_ref(candidates, plain)
        if matched:
            schema = str(matched.get("schema") or "").strip()
            table = str(matched.get("table") or "").strip()
            ref = f"{schema}.{table}" if schema and table else table
            return {
                "selected_ref": ref,
                "confidence": 0.6,
                "needs_metadata": False,
                "reason": "plain_ref_fallback",
            }
    if mentioned_refs:
        picked = _find_candidate_by_ref(candidates, mentioned_refs[0])
        if picked:
            schema = str(picked.get("schema") or "").strip()
            table = str(picked.get("table") or "").strip()
            ref = f"{schema}.{table}" if schema and table else table
            return {
                "selected_ref": ref,
                "confidence": 0.55,
                "needs_metadata": False,
                "reason": "text_mention_fallback",
            }
    return {}


def _extract_sql_from_compose_payload(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    candidate_fields: list[str] = []

    def _append_sql_fields(obj: dict[str, Any] | None) -> None:
        if not isinstance(obj, dict):
            return
        for key in ("sql", "query", "sql_query", "statement", "query_text"):
            val = obj.get(key)
            if isinstance(val, str) and val.strip():
                candidate_fields.append(val.strip())
        args = obj.get("args")
        if isinstance(args, dict):
            for key in ("sql", "query", "sql_query", "statement", "query_text"):
                val = args.get(key)
                if isinstance(val, str) and val.strip():
                    candidate_fields.append(val.strip())

    _append_sql_fields(payload)
    for nested_key in ("plan", "step", "result", "output", "data"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            _append_sql_fields(nested)
    steps = payload.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict):
                _append_sql_fields(step)

    for field in candidate_fields:
        sql = _sanitize_sql_candidate(field)
        if sql and looks_like_sql(sql):
            return sql
    return ""


def _llm_compose_sql_for_selected_object(
    request: str,
    schema: str,
    table: str,
    summary: str,
    schema_meta: dict[str, Any] | None = None,
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    if not request or not table:
        return {}
    client = _get_openai_client(timeout_sec=timeout_sec)
    if client is None:
        return {}
    scoped = _build_object_scoped_schema_meta(schema_meta, table)
    columns_raw = (
        scoped.get("columns_by_table", {}).get(table, [])
        if isinstance(scoped, dict)
        else []
    )
    columns: list[dict[str, str]] = []
    if isinstance(columns_raw, list):
        for col in columns_raw[:120]:
            if not isinstance(col, dict):
                continue
            name = str(col.get("name") or col.get("column_name") or "").strip()
            if not name:
                continue
            dtype = str(col.get("type") or col.get("data_type") or "").strip()
            columns.append({"name": name, "type": dtype})
    payload = {
        "request": str(request or "").strip(),
        "selected_object": {
            "schema": str(schema or "").strip(),
            "table": str(table or "").strip(),
            "summary": _trim_fact_text(str(summary or ""), max_len=500),
            "columns": columns,
        },
    }
    resp = _openai_chat_completion_with_deadline(
        client,
        AGENT_SQL_COMPOSE_MODEL,
        [
            {"role": "system", "content": OBJECT_SQL_COMPOSE_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        timeout_sec=timeout_sec,
    )
    if resp is None:
        return {}
    try:
        text = (resp.choices[0].message.content or "").strip()
    except Exception:
        return {}
    obj = _extract_json_object(text)
    if isinstance(obj, dict):
        sql_field = _extract_sql_from_compose_payload(obj)
        if sql_field and not str(obj.get("sql") or "").strip():
            obj = dict(obj)
            obj["sql"] = sql_field
        return obj
    plain_sql = _sanitize_sql_candidate(text)
    if plain_sql and looks_like_sql(plain_sql) and not is_write_sql(plain_sql):
        return {
            "sql": plain_sql,
            "intent": "선택 객체 기반 SQL 실행",
            "confidence": 0.5,
            "needs_metadata": False,
        }
    return {}


def _llm_compose_sql_from_knowledge(
    request: str,
    knowledge: dict[str, Any] | None,
    timeout_sec: int | None = None,
    force_mode: bool = False,
) -> dict[str, Any]:
    req = str(request or "").strip()
    if not req or not isinstance(knowledge, dict):
        return {}
    candidates = _collect_knowledge_table_candidates(knowledge)
    if not candidates:
        return {}
    objects_payload = _prepare_insight_candidates_for_llm(
        candidates,
        max_chars=max(
            5000 if not force_mode else 9000,
            int(AGENT_RAG_DOC_MAX_CHARS) * (4 if not force_mode else 6),
        ),
    )
    if not objects_payload:
        return {}
    docs_payload: list[dict[str, Any]] = []
    used = 0
    docs_budget = max(
        1600 if not force_mode else 2600,
        int(AGENT_RAG_DOC_MAX_CHARS) * (1 if not force_mode else 2),
    )
    for item in knowledge.get("rag_documents") or []:
        if not isinstance(item, dict):
            continue
        text = _trim_fact_text(str(item.get("text") or ""), max_len=320)
        if not text:
            continue
        payload_item = {
            "key": str(item.get("key") or "").strip(),
            "text": text,
            "weight": int(item.get("weight", 1) or 1),
            "source_type": str(item.get("source_type") or "").strip(),
        }
        rough_len = len(json.dumps(payload_item, ensure_ascii=False))
        if docs_payload and used + rough_len > docs_budget:
            continue
        docs_payload.append(payload_item)
        used += rough_len
        if len(docs_payload) >= (12 if not force_mode else 20):
            break
    client = _get_openai_client(timeout_sec=timeout_sec)
    if client is None:
        return {}
    payload = {
        "request": req,
        "objects": objects_payload,
        "documents": docs_payload,
    }
    resp = _openai_chat_completion_with_deadline(
        client,
        AGENT_SQL_COMPOSE_MODEL,
        [
            {
                "role": "system",
                "content": (
                    KNOWLEDGE_SQL_FORCE_PROMPT if force_mode else KNOWLEDGE_SQL_COMPOSE_PROMPT
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        timeout_sec=timeout_sec,
    )
    if resp is None:
        return {}
    try:
        text = (resp.choices[0].message.content or "").strip()
    except Exception:
        return {}
    obj = _extract_json_object(text)
    if isinstance(obj, dict):
        sql_field = _extract_sql_from_compose_payload(obj)
        if sql_field and not str(obj.get("sql") or "").strip():
            obj = dict(obj)
            obj["sql"] = sql_field
        return obj
    plain_sql = _sanitize_sql_candidate(text)
    if plain_sql and looks_like_sql(plain_sql) and not is_write_sql(plain_sql):
        return {
            "sql": plain_sql,
            "intent": "지식 근거 기반 SQL 실행" if not force_mode else "지식 근거 기반 강제 SQL 실행",
            "confidence": 0.5,
            "needs_metadata": False,
        }
    return {}


def _build_knowledge_sql_fallback_plan(
    request: str,
    knowledge: dict[str, Any] | None,
    mcp_tools: list[str] | None,
    kv: dict[str, Any] | None = None,
    schema_meta: dict[str, Any] | None = None,
    db_conn=None,
    timeout_sec: int | None = None,
) -> tuple[dict[str, Any] | None, str]:
    if not AGENT_KNOWLEDGE_SQL_FALLBACK:
        return None, "disabled"
    if not _knowledge_has_table_evidence(knowledge):
        return None, "no_table_evidence"
    fallback_candidate = _pick_table_candidate_from_knowledge(request, knowledge)
    if _allow_rag_object_fallback(
        request,
        kv if isinstance(kv, dict) else {},
        schema_meta if isinstance(schema_meta, dict) else {},
        knowledge,
        candidate=fallback_candidate,
    ):
        fallback_plan = _build_sql_plan_from_candidate_request(
            request,
            fallback_candidate,
            kv if isinstance(kv, dict) else {},
            mcp_tools,
            schema_meta if isinstance(schema_meta, dict) else {},
            db_conn=db_conn,
        )
        if fallback_plan:
            return fallback_plan, "candidate_fast_sql"
    composed = _llm_compose_sql_from_knowledge(
        request,
        knowledge,
        timeout_sec=timeout_sec,
    )
    if not isinstance(composed, dict):
        return None, "compose_invalid"
    sql_text = _extract_sql_from_compose_payload(composed)
    intent = str(composed.get("intent") or "").strip()
    if not intent:
        intent = "지식 근거 기반 SQL 실행"
    reason = "ok"
    if not sql_text or not looks_like_sql(sql_text) or is_write_sql(sql_text):
        reason = "compose_sql_empty_or_invalid"
        candidates: list[dict[str, Any]] = []
        seen_refs: set[str] = set()

        def _push_candidate(item: dict[str, Any] | None) -> None:
            if not isinstance(item, dict):
                return
            schema = _sanitize_ident_part(str(item.get("schema") or "").strip())
            table = _sanitize_ident_part(str(item.get("table") or "").strip())
            if not table:
                return
            ref = f"{schema.lower()}.{table.lower()}" if schema else table.lower()
            if ref in seen_refs:
                return
            seen_refs.add(ref)
            candidates.append(item)

        _push_candidate(_pick_table_candidate_from_knowledge(request, knowledge))
        for item in _collect_knowledge_table_candidates(knowledge):
            _push_candidate(item if isinstance(item, dict) else None)
        if not candidates:
            fallback_candidate = _fallback_top_candidate_from_knowledge(knowledge)
            _push_candidate(fallback_candidate)
            if fallback_candidate:
                reason = "compose_sql_empty_or_invalid:top_candidate_fallback"
        if candidates:
            max_tries = max(1, int(AGENT_KNOWLEDGE_SQL_FALLBACK_MAX_OBJECT_TRIES or 1))
            if max_tries <= 0:
                max_tries = len(candidates)
            compose_timeout_total = max(
                6,
                int(timeout_sec or AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC),
            )
            tried = 0
            for candidate in candidates:
                if tried >= max_tries:
                    break
                tried += 1
                schema = _sanitize_ident_part(str(candidate.get("schema") or "").strip())
                table = _sanitize_ident_part(str(candidate.get("table") or "").strip())
                if not table:
                    continue
                effective_schema_meta = (
                    schema_meta if isinstance(schema_meta, dict) else {}
                )
                scoped_meta = _build_object_scoped_schema_meta(effective_schema_meta, table)
                scoped_cols = (
                    scoped_meta.get("columns_by_table", {}).get(table, [])
                    if isinstance(scoped_meta, dict)
                    else []
                )
                if (
                    (not isinstance(scoped_cols, list) or not scoped_cols)
                    and db_conn is not None
                    and schema
                ):
                    live_cols = _load_table_columns_snapshot(
                        db_conn,
                        schema,
                        table,
                        limit=120,
                    )
                    if live_cols:
                        effective_schema_meta = {
                            "tables": [table],
                            "columns_by_table": {table: live_cols},
                        }
                per_try_timeout = max(
                    4,
                    min(
                        AGENT_INSIGHT_SQL_COMPOSE_TIMEOUT_SEC,
                        int(compose_timeout_total / max(1, max_tries)),
                    ),
                )
                composed_obj = _llm_compose_sql_for_selected_object(
                    request,
                    schema,
                    table,
                    str(candidate.get("summary") or candidate.get("fact_text") or ""),
                    schema_meta=effective_schema_meta,
                    timeout_sec=per_try_timeout,
                )
                sql_candidate = _extract_sql_from_compose_payload(composed_obj)
                if not sql_candidate or not looks_like_sql(sql_candidate) or is_write_sql(sql_candidate):
                    continue
                if schema:
                    sql_candidate = _rewrite_schema_in_sql(sql_candidate, schema, KNOWN_SCHEMAS)
                    if not _sql_mentions_schema(sql_candidate, schema):
                        sql_candidate = _prefix_use_schema(sql_candidate, schema)
                compose_intent = str(composed_obj.get("intent") or "").strip()
                if compose_intent:
                    intent = compose_intent
                sql_text = _normalize_sql_identifier_backticks(sql_candidate)
                chosen_ref = f"{schema}.{table}" if schema else table
                reason = f"object_compose_ok:{tried}:{chosen_ref}"
                break
            if not sql_text:
                reason = "compose_sql_empty_or_invalid:object_compose_failed"
        else:
            reason = "compose_sql_empty_or_invalid:no_candidate"
    if not sql_text or not looks_like_sql(sql_text) or is_write_sql(sql_text):
        forced = _llm_compose_sql_from_knowledge(
            request,
            knowledge,
            timeout_sec=timeout_sec,
            force_mode=True,
        )
        if isinstance(forced, dict):
            forced_sql = _extract_sql_from_compose_payload(forced)
            if forced_sql and looks_like_sql(forced_sql) and not is_write_sql(forced_sql):
                sql_text = _normalize_sql_identifier_backticks(forced_sql)
                forced_intent = str(forced.get("intent") or "").strip()
                if forced_intent:
                    intent = forced_intent
                reason = (
                    f"{reason}:force_compose_sql"
                    if reason
                    else "force_compose_sql"
                )
    if not sql_text or not looks_like_sql(sql_text) or is_write_sql(sql_text):
        return None, reason
    if AGENT_MODE == "mcp":
        execute_tool = _find_tool_name(mcp_tools or [], MCP_EXECUTE_SQL_CANDIDATES) or "execute_sql"
        return {
            "action": "step",
            "tool": execute_tool,
            "args": {"sql": sql_text},
            "intent": intent,
            "is_write": False,
        }, reason
    return {
        "action": "step",
        "sql": sql_text,
        "intent": intent,
        "is_write": False,
    }, reason


def _llm_review_sql_grounding(
    request: str,
    intent: str,
    schema: str,
    table: str,
    columns: list[dict[str, str]],
    sql_text: str,
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    if not request or not table or not sql_text:
        return {}
    client = _get_openai_client(timeout_sec=timeout_sec)
    if client is None:
        return {}
    payload = {
        "request": str(request or "").strip(),
        "intent": str(intent or "").strip(),
        "selected_object": {
            "schema": str(schema or "").strip(),
            "table": str(table or "").strip(),
            "columns": columns[:160] if isinstance(columns, list) else [],
        },
        "sql": str(sql_text or "").strip(),
    }
    resp = _openai_chat_completion_with_deadline(
        client,
        AGENT_SQL_REVIEW_MODEL,
        [
            {"role": "system", "content": OBJECT_SQL_GROUNDING_REVIEW_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        timeout_sec=timeout_sec,
    )
    if resp is None:
        return {}
    try:
        text = (resp.choices[0].message.content or "").strip()
    except Exception:
        return {}
    obj = _extract_json_object(text)
    if isinstance(obj, dict):
        fixed_sql = str(obj.get("fixed_sql") or "").strip()
        if not fixed_sql:
            for key in ("sql", "candidate_sql", "rewrite_sql"):
                val = str(obj.get(key) or "").strip()
                if val:
                    fixed_sql = val
                    break
        if fixed_sql and not str(obj.get("fixed_sql") or "").strip():
            obj = dict(obj)
            obj["fixed_sql"] = fixed_sql
        return obj
    return {}


def _review_sql_for_selected_object(
    request: str,
    intent: str,
    schema: str,
    table: str,
    columns: list[dict[str, str]],
    sql_text: str,
) -> tuple[str, str]:
    if not sql_text:
        return "", "empty_sql"
    if not AGENT_SQL_GROUNDED_REVIEW:
        return sql_text, "review_disabled"
    review = _llm_review_sql_grounding(
        request,
        intent,
        schema,
        table,
        columns,
        sql_text,
        timeout_sec=AGENT_SQL_GROUNDED_REVIEW_TIMEOUT_SEC,
    )
    if not isinstance(review, dict) or not review:
        if AGENT_SQL_GROUNDED_BLOCK_ON_FAIL:
            return "", "review_unavailable"
        return sql_text, "review_unavailable_passthrough"
    ok = bool(review.get("ok"))
    reason = str(review.get("reason") or "").strip()
    fixed_raw = _sanitize_sql_candidate(str(review.get("fixed_sql") or ""))
    fixed_sql = (
        fixed_raw
        if fixed_raw and looks_like_sql(fixed_raw) and not is_write_sql(fixed_raw)
        else ""
    )
    if ok:
        return fixed_sql or sql_text, "review_ok"
    if AGENT_SQL_GROUNDED_REWRITE_ON_FAIL and fixed_sql:
        return fixed_sql, f"review_rewrite:{reason}" if reason else "review_rewrite"
    if AGENT_SQL_GROUNDED_BLOCK_ON_FAIL:
        return "", f"review_block:{reason}" if reason else "review_block"
    return sql_text, f"review_failed_passthrough:{reason}" if reason else "review_failed_passthrough"


def _extract_anchor_table_ref(kv: dict[str, Any] | None) -> tuple[str, str]:
    kv = kv or {}
    anchor_raw = str(kv.get("last_resolved_object") or "").strip()
    if not anchor_raw:
        anchor_raw = str(kv.get("cross_session_anchor_table") or "").strip()
    if not anchor_raw:
        return "", ""
    if "." in anchor_raw:
        schema, table = anchor_raw.split(".", 1)
    else:
        schema = str(kv.get("preferred_schema") or "").strip()
        table = anchor_raw
    schema = _sanitize_ident_part(schema)
    table = _sanitize_ident_part(table)
    if not table:
        return "", ""
    ref = f"{schema.lower()}.{table.lower()}" if schema else table.lower()
    return ref, f"{schema}.{table}" if schema else table


def _verify_table_exists(
    db_conn,
    schema: str,
    table: str,
    timeout_ms: int,
) -> bool | None:
    if not db_conn:
        return None
    safe_schema = _sanitize_ident_part(schema)
    safe_table = _sanitize_ident_part(table)
    if not safe_schema or not safe_table:
        return False
    hint_ms = max(200, int(timeout_ms or 0))
    cur = db_conn.cursor()
    try:
        cur.execute(
            f"""
SELECT /*+ MAX_EXECUTION_TIME({hint_ms}) */ 1
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
LIMIT 1
            """,
            (safe_schema, safe_table),
        )
        row = cur.fetchone()
        return bool(row)
    except Exception:
        return None
    finally:
        cur.close()


def _load_table_columns_snapshot(
    db_conn,
    schema: str,
    table: str,
    limit: int = 120,
) -> list[dict[str, str]]:
    if not db_conn:
        return []
    safe_schema = _sanitize_ident_part(schema)
    safe_table = _sanitize_ident_part(table)
    if not safe_schema or not safe_table:
        return []
    cur = db_conn.cursor()
    try:
        cur.execute(
            """
SELECT COLUMN_NAME, DATA_TYPE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = %s
  AND TABLE_NAME = %s
ORDER BY ORDINAL_POSITION
LIMIT %s
            """,
            (safe_schema, safe_table, max(1, int(limit or 120))),
        )
        rows = cur.fetchall() or []
    except Exception:
        rows = []
    finally:
        cur.close()
    out: list[dict[str, str]] = []
    for row in rows:
        if not row:
            continue
        name = str(row[0] or "").strip()
        if not name:
            continue
        out.append({"name": name, "type": str(row[1] or "").strip()})
    return out


def _build_object_scoped_schema_meta(
    schema_meta: dict[str, Any] | None,
    table: str,
) -> dict[str, Any]:
    meta = schema_meta if isinstance(schema_meta, dict) else {}
    table_name = str(table or "").strip()
    if not table_name:
        return {}
    columns_by_table = meta.get("columns_by_table") if isinstance(meta.get("columns_by_table"), dict) else {}
    cols = columns_by_table.get(table_name) if isinstance(columns_by_table, dict) else []
    if not isinstance(cols, list):
        cols = []
    return {"tables": [table_name], "columns_by_table": {table_name: cols}}


def _build_fast_sql_for_object(
    request: str,
    schema: str,
    table: str,
    kv: dict[str, Any] | None,
    schema_meta: dict[str, Any] | None,
    fact_text: str = "",
    allow_count_fallback: bool = False,
    db_conn=None,
) -> tuple[str, str]:
    safe_schema = _sanitize_ident_part(schema)
    safe_table = _sanitize_ident_part(table)
    if not safe_table:
        return "", ""
    intent = "인사이트 객체 기반 SQL 실행"
    sql_text = ""
    effective_schema_meta = schema_meta if isinstance(schema_meta, dict) else {}
    scoped_meta = _build_object_scoped_schema_meta(effective_schema_meta, safe_table)
    scoped_cols = (
        scoped_meta.get("columns_by_table", {}).get(safe_table, [])
        if isinstance(scoped_meta, dict)
        else []
    )
    if (not isinstance(scoped_cols, list) or not scoped_cols) and db_conn is not None and safe_schema:
        live_cols = _load_table_columns_snapshot(db_conn, safe_schema, safe_table, limit=120)
        if live_cols:
            effective_schema_meta = {
                "tables": [safe_table],
                "columns_by_table": {safe_table: live_cols},
            }
    selected_columns = (
        effective_schema_meta.get("columns_by_table", {}).get(safe_table, [])
        if isinstance(effective_schema_meta, dict)
        else []
    )
    if not isinstance(selected_columns, list):
        selected_columns = []
    compose_result = _llm_compose_sql_for_selected_object(
        request,
        safe_schema,
        safe_table,
        fact_text,
        schema_meta=effective_schema_meta,
        timeout_sec=AGENT_INSIGHT_SQL_COMPOSE_TIMEOUT_SEC,
    )
    if isinstance(compose_result, dict):
        sql_candidate = _sanitize_sql_candidate(str(compose_result.get("sql") or ""))
        if sql_candidate and looks_like_sql(sql_candidate) and not is_write_sql(sql_candidate):
            sql_text = sql_candidate
            intent = str(compose_result.get("intent") or "").strip() or intent
    if not sql_text:
        # Policy: never synthesize SQL templates in code for user-path execution.
        # Query generation must be delegated to LLM.
        return "", ""
    reviewed_sql, _review_state = _review_sql_for_selected_object(
        request,
        intent,
        safe_schema,
        safe_table,
        selected_columns,
        sql_text,
    )
    if not reviewed_sql:
        return "", ""
    sql_text = reviewed_sql
    schema_for_sql = safe_schema or _sanitize_ident_part(str((kv or {}).get("preferred_schema") or "").strip())
    if schema_for_sql:
        sql_text = _rewrite_schema_in_sql(sql_text, schema_for_sql, KNOWN_SCHEMAS)
        if not _sql_mentions_schema(sql_text, schema_for_sql):
            sql_text = _prefix_use_schema(sql_text, schema_for_sql)
    return _normalize_sql_identifier_backticks(sql_text), intent


def _clear_last_resolved_object_kv(conn, conversation_id: str) -> None:
    if not conn:
        return
    try:
        save_memory_kv(conn, conversation_id, "last_resolved_object", "")
        save_memory_kv(conn, conversation_id, "last_resolved_object_score", "")
        save_memory_kv(conn, conversation_id, "last_resolved_object_source", "")
        save_memory_kv(conn, conversation_id, "last_resolved_object_at", "")
        save_memory_kv(conn, conversation_id, "last_resolved_fact_key", "")
    except Exception:
        pass


def _build_insight_object_fast_plan(
    mem_conn,
    db_conn,
    request: str,
    kv: dict[str, Any] | None,
    mcp_tools: list[str] | None,
    schema_meta: dict[str, Any] | None,
    scope_key: str | None = None,
    require_aggregate: bool = True,
    knowledge: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    info = {
        "used": 0,
        "object": "",
        "score": 0,
        "source": "",
        "fallback_reason": "",
        "fact_key": "",
        "llm_confidence": 0.0,
        "candidate_count": 0,
        "top_candidates": [],
    }
    req = str(request or "").strip()
    kv = kv or {}
    explicit_tables, explicit_refs = _extract_request_table_mentions(req, schema_meta)
    anchor_ref_raw, anchor_full = _extract_anchor_table_ref(kv)
    requested_schema = _sanitize_ident_part(_detect_requested_schema(req, KNOWN_SCHEMAS) or "")
    preferred_schema = requested_schema or _sanitize_ident_part(
        str(kv.get("preferred_schema") or "").strip()
    )
    anchor_schema = ""
    anchor_ref_for_schema = anchor_full or anchor_ref_raw
    if "." in anchor_ref_for_schema:
        anchor_schema = _sanitize_ident_part(anchor_ref_for_schema.split(".", 1)[0])
    anchor_schema_mismatch = bool(preferred_schema and anchor_schema and anchor_schema != preferred_schema)
    passthrough_guard_active = (
        AGENT_LLM_REQUEST_PASSTHROUGH
        and not AGENT_INSIGHT_FASTPATH_ALLOW_WITH_PASSTHROUGH
        and not (explicit_tables or explicit_refs or anchor_ref_raw or anchor_full)
    )
    if passthrough_guard_active:
        info["fallback_reason"] = "passthrough_guard_active"
    if not AGENT_INSIGHT_OBJECT_FASTPATH:
        info["fallback_reason"] = "disabled"
        return None, info
    if not req:
        info["fallback_reason"] = "empty_request"
        return None, info
    max_candidates = max(0, int(AGENT_INSIGHT_OBJECT_MAX_CANDIDATES))
    candidates = _collect_insight_candidates_from_knowledge(knowledge)
    db_fetch_limit = max(0, int(AGENT_INSIGHT_OBJECT_DB_FETCH_LIMIT))
    if db_fetch_limit <= 0:
        base_limit = max(80, max_candidates * 24) if max_candidates > 0 else 120
        if preferred_schema:
            # Keep slightly wider coverage for schema-scoped requests.
            db_fetch_limit = min(320, max(160, base_limit))
        else:
            db_fetch_limit = min(180, base_limit)
    db_candidates = _load_table_insight_candidates(
        mem_conn,
        scope_key=scope_key or FACT_SCOPE_COMMON,
        max_candidates=db_fetch_limit,
        hint_tokens=None,
    )
    if db_candidates:
        if not candidates:
            candidates = list(db_candidates)
        else:
            target_min_candidates = 24
            if len(candidates) >= target_min_candidates:
                db_candidates = []
            seen_refs = {
                str(item.get("ref") or "").strip().lower()
                for item in candidates
                if isinstance(item, dict) and str(item.get("ref") or "").strip()
            }
            for item in db_candidates:
                if not isinstance(item, dict):
                    continue
                ref = str(item.get("ref") or "").strip().lower()
                if not ref or ref in seen_refs:
                    continue
                seen_refs.add(ref)
                candidates.append(item)
                if len(candidates) >= target_min_candidates:
                    break
    if not candidates:
        info["fallback_reason"] = "no_table_insight"
        return None, info

    ordered_candidates = list(candidates)
    known_candidate_tables = [
        str(item.get("table") or "").strip()
        for item in ordered_candidates
        if isinstance(item, dict) and str(item.get("table") or "").strip()
    ]
    hinted_refs, hinted_tables = _extract_object_hints_from_request(
        req,
        known_tables=known_candidate_tables,
    )
    if hinted_refs:
        explicit_refs = set(explicit_refs or set()).union(hinted_refs)
    if hinted_tables:
        explicit_tables = set(explicit_tables or set()).union(hinted_tables)
    if preferred_schema:
        scoped: list[dict[str, Any]] = []
        others: list[dict[str, Any]] = []
        for item in ordered_candidates:
            if not isinstance(item, dict):
                continue
            cand_schema = _sanitize_ident_part(str(item.get("schema") or "").strip())
            if cand_schema and cand_schema == preferred_schema:
                scoped.append(item)
            else:
                others.append(item)
        ordered_candidates = scoped + others
    selected = None
    selection_source = ""
    llm_confidence = 0.0

    mention_refs = _extract_candidate_refs_from_text(
        req,
        ordered_candidates,
        prefer_schema=preferred_schema,
    )
    if mention_refs:
        if preferred_schema:
            mention_refs = [
                ref
                for ref in mention_refs
                if ref.startswith(f"{preferred_schema.lower()}.")
            ] or mention_refs
        selected = _find_candidate_by_ref(ordered_candidates, mention_refs[0])
        if selected:
            selection_source = "request_mention"

    for explicit_ref in explicit_refs:
        if selected is None:
            selected = _find_candidate_by_ref(ordered_candidates, explicit_ref)
            if selected:
                selection_source = "explicit_ref"
                break
    if selected is None and explicit_tables:
        explicit_table_ambiguous = False
        for token in explicit_tables:
            candidate = _find_unique_candidate_by_table(ordered_candidates, token)
            if candidate:
                selected = candidate
                selection_source = "explicit_table"
                break
            table_norm = _sanitize_ident_part(token).lower()
            if table_norm:
                table_hits = [
                    item
                    for item in ordered_candidates
                    if str(item.get("table") or "").strip().lower() == table_norm
                ]
                if len(table_hits) > 1:
                    explicit_table_ambiguous = True
        if selected is None and explicit_table_ambiguous:
            info["fallback_reason"] = "ambiguous_explicit_table"
    anchor_reuse_allowed = _looks_like_followup_request(req) or _has_same_domain_cue(req)
    if selected is None and anchor_reuse_allowed and anchor_full and not anchor_schema_mismatch:
        selected = _find_candidate_by_ref(ordered_candidates, anchor_full)
        if selected:
            selection_source = "anchor"
    if selected is None and anchor_reuse_allowed and anchor_ref_raw and not anchor_schema_mismatch:
        selected = _find_candidate_by_ref(ordered_candidates, anchor_ref_raw)
        if selected:
            selection_source = "anchor"

    llm_candidate_source = ordered_candidates
    if preferred_schema:
        scoped_only = []
        for item in ordered_candidates:
            if not isinstance(item, dict):
                continue
            cand_schema = _sanitize_ident_part(str(item.get("schema") or "").strip())
            if cand_schema and cand_schema == preferred_schema:
                scoped_only.append(item)
        if scoped_only:
            llm_candidate_source = scoped_only
    llm_candidate_source = _interleave_candidates_by_schema(llm_candidate_source)

    llm_candidates = _prepare_insight_candidates_for_llm(
        llm_candidate_source,
        max_chars=max(6000, int(AGENT_RAG_DOC_MAX_CHARS) * 6),
    )
    info["candidate_count"] = len(llm_candidate_source)
    top_items: list[dict[str, Any]] = []
    for item in llm_candidates[: max(1, int(AGENT_INSIGHT_ROUTE_LOG_MAX_CANDIDATES))]:
        schema = str(item.get("schema") or "").strip()
        table = str(item.get("table") or "").strip()
        if not table:
            continue
        obj = f"{schema}.{table}" if schema else table
        top_items.append(
            {
                "object": obj,
                "score": int(item.get("weight", 1) or 1),
                "stage": 0,
                "source": "table_insight",
                "fact_key": str(item.get("fact_key") or obj),
            }
        )
    info["top_candidates"] = top_items

    llm_result: dict[str, Any] = {}
    llm_selection_stage = ""
    if selected is None and llm_candidates:
        llm_result = _llm_pick_table_insight_candidate(
            req,
            llm_candidates,
            timeout_sec=AGENT_OBJECT_RESOLVE_TIMEOUT_SEC,
        )
        llm_selection_stage = "single"
        try:
            llm_confidence = float(llm_result.get("confidence", 0) or 0.0)
        except Exception:
            llm_confidence = 0.0
        picked_ref = str(llm_result.get("selected_ref") or "").strip()
        if picked_ref:
            selected = _find_candidate_by_ref(ordered_candidates, picked_ref)
            if selected:
                selection_source = "llm"
        if selected is None and bool(llm_result.get("needs_metadata")) and not (
            explicit_tables or explicit_refs or anchor_ref_raw or anchor_full
        ):
            scoped_exists = False
            if preferred_schema:
                for item in ordered_candidates:
                    if _sanitize_ident_part(str(item.get("schema") or "").strip()) == preferred_schema:
                        scoped_exists = True
                        break
            if not scoped_exists:
                info["fallback_reason"] = "llm_requires_metadata"
    if selected is None and llm_candidate_source:
        batched_result, batched_confidence, batched_stage = _llm_pick_table_insight_candidate_in_batches(
            req,
            llm_candidate_source,
            timeout_sec=AGENT_OBJECT_RESOLVE_TIMEOUT_SEC,
        )
        if isinstance(batched_result, dict) and batched_result:
            llm_result = batched_result
            llm_selection_stage = batched_stage
            llm_confidence = max(llm_confidence, batched_confidence)
            picked_ref = str(batched_result.get("selected_ref") or "").strip()
            if picked_ref:
                selected = _find_candidate_by_ref(ordered_candidates, picked_ref)
                if selected:
                    selection_source = "llm_batched"
    if selected is None:
        info["llm_confidence"] = round(max(0.0, llm_confidence), 3)
        info["fallback_reason"] = info.get("fallback_reason") or "no_selected_candidate"
        return None, info
    min_score = max(1, int(AGENT_INSIGHT_OBJECT_MIN_SCORE))
    selected_weight = int(selected.get("weight", 1) or 1)
    if selection_source.startswith("llm") or selection_source in {"anchor"}:
        # Guard low-confidence auto routing to reduce wrong-table jumps.
        if selected_weight < min_score and llm_confidence < AGENT_OBJECT_PICK_MIN_CONFIDENCE:
            info["fallback_reason"] = "low_confidence_candidate"
            return None, info
    selected_fact_key = str(selected.get("fact_key") or "").strip()
    if passthrough_guard_active and selection_source.startswith("llm"):
        passthrough_min_conf = max(0.2, min(float(AGENT_OBJECT_PICK_MIN_CONFIDENCE), 0.45))
        if llm_confidence < passthrough_min_conf and not selected_fact_key:
            info["fallback_reason"] = "passthrough_guard_low_confidence"
            return None, info
    if AGENT_KB_REQUIRE_EVIDENCE and not selected_fact_key:
        info["fallback_reason"] = "missing_candidate_evidence"
        return None, info

    if AGENT_INSIGHT_OBJECT_VERIFY_ONCE and db_conn is not None:
        primary_ok = _verify_table_exists(
            db_conn,
            str(selected.get("schema") or "").strip(),
            str(selected.get("table") or "").strip(),
            AGENT_INSIGHT_OBJECT_VERIFY_TIMEOUT_MS,
        )
        if primary_ok is False:
            info["fallback_reason"] = "verify_failed"
            return None, info

    schema = str(selected.get("schema") or "").strip()
    table = str(selected.get("table") or "").strip()
    sql_text, fast_intent = _build_fast_sql_for_object(
        req,
        schema,
        table,
        kv,
        schema_meta,
        fact_text=str(selected.get("fact_text") or ""),
        allow_count_fallback=False,
        db_conn=db_conn,
    )
    if not sql_text:
        allow_seeded_retry = selection_source in {"request_mention", "explicit_ref", "explicit_table"}
        if not allow_seeded_retry and selection_source == "anchor":
            allow_seeded_retry = anchor_reuse_allowed
        if not allow_seeded_retry:
            info["fallback_reason"] = "sql_build_failed"
            return None, info
        # Retry with LLM knowledge composer seeded by the selected insight object.
        # This keeps SQL authoring model-driven while avoiding immediate ask/meta fallback.
        selected_summary = str(selected.get("summary") or selected.get("fact_text") or "").strip()
        seeded_knowledge: dict[str, Any] = {
            "rag_objects": [
                {
                    "object_type": "table",
                    "schema": schema,
                    "table": table,
                    "summary": _trim_fact_text(selected_summary, max_len=500),
                    "weight": int(selected.get("weight", 1) or 1),
                    "updated_at": str(selected.get("updated_at") or "").strip(),
                }
            ],
            "rag_documents": (
                [
                    {
                        "key": selected_fact_key or f"insight:{schema}.{table}",
                        "text": _trim_fact_text(selected_summary, max_len=500),
                        "weight": int(selected.get("weight", 1) or 1),
                        "source_type": "schema_insight",
                    }
                ]
                if selected_summary
                else []
            ),
        }
        compose_timeout = max(
            6,
            min(
                int(AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC or 20),
                int(AGENT_INSIGHT_SQL_COMPOSE_TIMEOUT_SEC or 20),
            ),
        )
        composed_seed = _llm_compose_sql_from_knowledge(
            req,
            seeded_knowledge,
            timeout_sec=compose_timeout,
            force_mode=True,
        )
        seeded_sql = _extract_sql_from_compose_payload(composed_seed)
        if seeded_sql and looks_like_sql(seeded_sql) and not is_write_sql(seeded_sql):
            seeded_sql = _normalize_sql_identifier_backticks(seeded_sql)
            if schema:
                seeded_sql = _rewrite_schema_in_sql(seeded_sql, schema, KNOWN_SCHEMAS)
                if not _sql_mentions_schema(seeded_sql, schema):
                    seeded_sql = _prefix_use_schema(seeded_sql, schema)
            if AGENT_MODE == "mcp":
                execute_tool = _find_tool_name(mcp_tools or [], MCP_EXECUTE_SQL_CANDIDATES) or "execute_sql"
                plan = {
                    "action": "step",
                    "tool": execute_tool,
                    "args": {"sql": seeded_sql},
                    "intent": str(
                        composed_seed.get("intent") or fast_intent or "인사이트 객체 기반 SQL 실행"
                    ),
                    "is_write": False,
                }
            else:
                plan = {
                    "action": "step",
                    "sql": seeded_sql,
                    "intent": str(
                        composed_seed.get("intent") or fast_intent or "인사이트 객체 기반 SQL 실행"
                    ),
                    "is_write": False,
                }
            info["used"] = 1
            info["object"] = f"{schema}.{table}" if schema else table
            info["score"] = int(selected.get("weight", 1) or 1)
            info["fact_key"] = selected_fact_key
            info["llm_confidence"] = round(max(0.0, llm_confidence), 3)
            info["source"] = (
                f"table_insight_{selection_source}:seeded_knowledge_compose"
                if selection_source
                else "table_insight_seeded_knowledge_compose"
            )
            return plan, info
        info["fallback_reason"] = "sql_build_failed"
        return None, info

    if AGENT_MODE == "mcp":
        execute_tool = _find_tool_name(mcp_tools or [], MCP_EXECUTE_SQL_CANDIDATES) or "execute_sql"
        plan = {
            "action": "step",
            "tool": execute_tool,
            "args": {"sql": sql_text},
            "intent": fast_intent,
            "is_write": False,
        }
    else:
        plan = {
            "action": "step",
            "sql": sql_text,
            "intent": fast_intent,
            "is_write": False,
        }
    info["used"] = 1
    info["object"] = f"{schema}.{table}" if schema else table
    info["score"] = int(selected.get("weight", 1) or 1)
    info["fact_key"] = selected_fact_key
    info["llm_confidence"] = round(max(0.0, llm_confidence), 3)
    info["source"] = f"table_insight_{selection_source}" if selection_source else "table_insight"
    if llm_result:
        llm_reason = str(llm_result.get("reason") or "").strip()
        if llm_reason:
            info["fallback_reason"] = llm_reason
    if llm_selection_stage:
        info["source"] = (
            f"{info['source']}:{llm_selection_stage}" if info.get("source") else llm_selection_stage
        )
    return plan, info


def _build_fast_aggregate_sql(request: str, kv: dict[str, Any] | None, schema_meta: dict[str, Any] | None) -> str:
    # Policy: disable code-authored aggregate SQL templates.
    # LLM planner/composer is the only query authoring path.
    return ""


def _build_fast_aggregate_plan(
    request: str,
    kv: dict[str, Any] | None,
    mcp_tools: list[str] | None,
    schema_meta: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return None


def _count_recent_meta_steps(step_trace: list[dict[str, Any]] | None, window: int = 6) -> int:
    if not step_trace:
        return 0
    count = 0
    for entry in list(step_trace)[-max(1, int(window)) :]:
        if not isinstance(entry, dict):
            continue
        tool = str(entry.get("tool", "")).strip()
        sql_text = str(entry.get("sql", "")).strip()
        if _is_meta_tool_name(tool) or _is_meta_sql(sql_text):
            count += 1
    return count


def _can_force_fast_aggregate(request: str, kv: dict[str, Any] | None = None) -> bool:
    # Policy: text/keyword heuristic fast aggregate override is disabled.
    return False


def _apply_meta_exploration_budget(
    plan: dict[str, Any],
    step_trace: list[dict[str, Any]] | None,
    request: str,
    kv: dict[str, Any] | None,
    mcp_tools: list[str] | None,
    schema_meta: dict[str, Any] | None,
) -> dict[str, Any]:
    if not _is_meta_exploration_plan(plan):
        return plan
    if not _can_force_fast_aggregate(request, kv):
        return plan
    repeated = _count_recent_meta_steps(step_trace, window=6)
    budget = max(1, AGENT_META_EXPLORATION_BUDGET)
    if repeated < budget:
        return plan
    compact = _build_fast_aggregate_plan(request, kv, mcp_tools, schema_meta)
    return compact or plan


def _load_known_schemas_from_kv(kv: dict[str, Any] | None) -> list[str]:
    if not kv:
        return []
    raw = kv.get("known_schemas")
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item]
        except Exception:
            pass
        return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def _sql_mentions_schema(sql_text: str, schema: str) -> bool:
    if not sql_text or not schema:
        return False
    lowered = sql_text.lower()
    if re.search(rf"\buse\s+`?{re.escape(schema.lower())}`?", lowered):
        return True
    return bool(re.search(rf"\b{re.escape(schema.lower())}\s*\.", lowered))


def _prefix_use_schema(sql_text: str, schema: str) -> str:
    if not sql_text or not schema:
        return sql_text
    sql = sql_text.strip()
    if not sql.endswith(";"):
        sql += ";"
    return f"USE `{schema}`; {sql}"


def _rewrite_schema_in_sql(
    sql_text: str, schema: str, known_schemas: list[str] | None = None
) -> str:
    if not sql_text or not schema:
        return sql_text
    sql = sql_text
    candidates = known_schemas or KNOWN_SCHEMAS
    excluded = {"information_schema", "mysql", "performance_schema", "sys"}
    for other in candidates:
        if not other or str(other).lower() == str(schema).lower():
            continue
        if str(other).lower() in excluded:
            continue
        sql = re.sub(rf"\b{re.escape(str(other))}\s*\.", f"{schema}.", sql, flags=re.IGNORECASE)
    return sql


def _build_discovery_sql(
    schemas: list[str],
    table: str | None,
    want_columns: bool,
) -> tuple[str, str]:
    if table:
        schema_name = schemas[0] if schemas else _required_schema_fallback()
        schema_name = schema_name.replace("'", "''")
        table_name = table.replace("'", "''")
        sql = (
            "SELECT `COLUMN_NAME`, `DATA_TYPE`, `IS_NULLABLE`, `COLUMN_KEY` "
            "FROM `information_schema`.`COLUMNS` "
            f"WHERE `TABLE_SCHEMA` = '{schema_name}' AND `TABLE_NAME` = '{table_name}' "
            "ORDER BY `ORDINAL_POSITION`"
        )
        return sql, f"{schema_name}.{table} 컬럼 구조 조회"

    if want_columns:
        limit_clause = (
            f" LIMIT {AGENT_COLUMN_SCAN_LIMIT}" if AGENT_COLUMN_SCAN_LIMIT > 0 else ""
        )
        if schemas:
            safe = [s.replace("'", "''") for s in schemas]
            in_list = ", ".join([f"'{s}'" for s in safe])
            sql = (
                "SELECT `TABLE_SCHEMA`, `TABLE_NAME`, `COLUMN_NAME`, `DATA_TYPE`, `IS_NULLABLE`, `COLUMN_KEY` "
                "FROM `information_schema`.`COLUMNS` "
                f"WHERE `TABLE_SCHEMA` IN ({in_list}) "
                "ORDER BY `TABLE_SCHEMA`, `TABLE_NAME`, `ORDINAL_POSITION`"
                f"{limit_clause}"
            )
            return sql, "요청 스키마 컬럼 구조 조회"
        sql = (
            "SELECT `TABLE_NAME`, `COLUMN_NAME`, `DATA_TYPE`, `IS_NULLABLE`, `COLUMN_KEY` "
            "FROM `information_schema`.`COLUMNS` "
            "WHERE `TABLE_SCHEMA` = DATABASE() "
            "ORDER BY `TABLE_NAME`, `ORDINAL_POSITION`"
            f"{limit_clause}"
        )
        return sql, "현재 DB 컬럼 구조 요약 조회"

    if schemas:
        safe = [s.replace("'", "''") for s in schemas]
        in_list = ", ".join([f"'{s}'" for s in safe])
        sql = (
            "SELECT `TABLE_SCHEMA`, `TABLE_NAME` "
            "FROM `information_schema`.`TABLES` "
            f"WHERE `TABLE_SCHEMA` IN ({in_list}) "
            "ORDER BY `TABLE_SCHEMA`, `TABLE_NAME` "
            f"LIMIT {AGENT_TOP_N}"
        )
        return sql, "요청 스키마 테이블 목록 조회"

    sql = (
        "SELECT `TABLE_NAME` "
        "FROM `information_schema`.`TABLES` "
        "WHERE `TABLE_SCHEMA` = DATABASE() "
        "ORDER BY `TABLE_NAME` "
        f"LIMIT {AGENT_TOP_N}"
    )
    return sql, "현재 DB 테이블 목록 조회"


def _build_discovery_plan(
    nl: str,
    kv: dict[str, str] | None,
    schema_meta: dict[str, Any] | None,
    mcp_tools: list[str] | None,
    use_mcp: bool,
) -> dict[str, Any] | None:
    schema_tables, schemas, tables = _extract_schema_table_candidates(nl, kv, schema_meta)
    want_columns = any(keyword in (nl or "") for keyword in ("컬럼", "열", "필드", "column", "field"))

    table_name = None
    if schema_tables:
        schema, table_name = schema_tables[0]
        if schema and schema not in schemas:
            schemas.append(schema)
    elif tables:
        table_name = tables[0]

    sql, intent = _build_discovery_sql(schemas, table_name, want_columns)

    if use_mcp:
        execute_tool = _find_tool_name(mcp_tools or [], MCP_EXECUTE_SQL_CANDIDATES)
        if execute_tool:
            return {
                "action": "step",
                "tool": execute_tool,
                "args": {"sql": sql + ";"},
                "intent": intent,
                "is_write": False,
            }
        search_tool = _find_tool_name(mcp_tools or [], MCP_SEARCH_OBJECTS_CANDIDATES) or "search_objects"
        pattern = table_name or "%"
        args: dict[str, Any] = {"pattern": pattern, "object_type": "table", "limit": min(AGENT_TOP_N, 200)}
        if schemas:
            args["schema"] = schemas
        return {"action": "step", "tool": search_tool, "args": args, "intent": "구조 탐색", "is_write": False}

    return {
        "action": "step",
        "sql": sql,
        "intent": intent,
        "is_write": False,
    }


def _maybe_auto_discover(
    plan: dict[str, Any],
    nl: str,
    kv: dict[str, str] | None,
    schema_meta: dict[str, Any] | None,
    mcp_tools: list[str] | None,
    use_mcp: bool,
) -> dict[str, Any]:
    # Policy: rule-based intent heuristics auto-discovery is disabled.
    # Planning should be delegated to LLM + evidence package.
    return plan


def plan_next_step(
    nl: str,
    summary: str | None,
    rows,
    kv: dict[str, str],
    step_trace: list[dict[str, Any]] | None = None,
    mcp_tools: list[str] | None = None,
    schema_meta: dict[str, Any] | None = None,
    force_stepwise: bool = False,
    knowledge: dict[str, Any] | None = None,
    plan_timeout_sec: int | None = None,
    db_conn=None,
) -> dict[str, Any]:
    direct_sql = _extract_sql_from_request(nl)
    if not direct_sql and looks_like_sql(nl):
        direct_sql = nl.strip()
    if direct_sql:
        if AGENT_MODE == "mcp":
            execute_tool = _find_tool_name(mcp_tools or [], MCP_EXECUTE_SQL_CANDIDATES) or "execute_sql"
            return {
                "action": "step",
                "tool": execute_tool,
                "args": {"sql": direct_sql},
                "intent": "사용자 제공 SQL 실행",
                "is_write": is_write_sql(direct_sql),
            }
        return {
            "action": "step",
            "sql": direct_sql,
            "intent": "사용자 제공 SQL 실행",
            "is_write": is_write_sql(direct_sql),
        }

    if AGENT_RAG_PRIORITY_FIRST and _knowledge_has_table_evidence(knowledge):
        rag_timeout_sec = min(
            max(5, int(AGENT_RAG_PRIORITY_TIMEOUT_SEC)),
            max(5, int(plan_timeout_sec or AGENT_RAG_PRIORITY_TIMEOUT_SEC)),
        )
        rag_plan_raw = llm_plan_rag_priority(
            nl,
            summary,
            rows,
            kv,
            step_trace,
            mcp_tools=mcp_tools,
            schema_meta=schema_meta,
            force_stepwise=force_stepwise,
            knowledge=knowledge,
            timeout_sec=rag_timeout_sec,
        )
        rag_plan = (
            _normalize_mcp_plan(rag_plan_raw, mcp_tools)
            if AGENT_MODE == "mcp"
            else _normalize_sql_plan(rag_plan_raw)
        )
        rag_plan = _maybe_auto_discover(
            rag_plan,
            nl,
            kv,
            schema_meta,
            mcp_tools if AGENT_MODE == "mcp" else None,
            use_mcp=(AGENT_MODE == "mcp"),
        )
        if _is_execute_sql_plan(rag_plan):
            sql_text = _extract_plan_sql_text(rag_plan)
            if sql_text and not _is_meta_sql(sql_text):
                return rag_plan
        if _allow_rag_short_circuit_fallback():
            fallback_candidate = _pick_table_candidate_from_knowledge(nl, knowledge)
            if _allow_rag_object_fallback(
                nl,
                kv,
                schema_meta,
                knowledge,
                candidate=fallback_candidate,
            ):
                fallback_plan = _build_sql_plan_from_candidate_request(
                    nl,
                    fallback_candidate,
                    kv,
                    mcp_tools if AGENT_MODE == "mcp" else None,
                    schema_meta,
                    db_conn=db_conn,
                )
                if fallback_plan:
                    try:
                        schema = str((fallback_candidate or {}).get("schema") or "").strip()
                        table = str((fallback_candidate or {}).get("table") or "").strip()
                        log_insight_route(
                            "rag_priority_short_circuit_pick",
                            {
                                "run_id": cfg.CURRENT_RUN_ID,
                                "request": _compact_request_for_log(nl),
                                "object": f"{schema}.{table}" if schema and table else table,
                                "source": str((fallback_candidate or {}).get("_pick_source") or ""),
                                "confidence": float((fallback_candidate or {}).get("_pick_confidence", 0.0) or 0.0),
                                "weight": int((fallback_candidate or {}).get("weight", 0) or 0),
                            },
                        )
                    except Exception:
                        pass
                    return fallback_plan
        else:
            try:
                log_insight_route(
                    "rag_priority_short_circuit_skipped",
                    {
                        "run_id": cfg.CURRENT_RUN_ID,
                        "request": _compact_request_for_log(nl),
                        "reason": (
                            "passthrough_guard"
                            if AGENT_LLM_REQUEST_PASSTHROUGH
                            else "disabled"
                        ),
                    },
                )
            except Exception:
                pass
        if isinstance(rag_plan, dict) and rag_plan_raw is not None:
            return rag_plan

    if AGENT_MODE == "mcp":
        m = llm_plan(
            nl,
            summary,
            rows,
            kv,
            step_trace,
            mcp_tools=mcp_tools,
            schema_meta=schema_meta,
            force_stepwise=force_stepwise,
            knowledge=knowledge,
            timeout_sec=plan_timeout_sec,
        )
        plan = _normalize_mcp_plan(m, mcp_tools)
        plan = _maybe_auto_discover(plan, nl, kv, schema_meta, mcp_tools, use_mcp=True)
        # llm_plan 이 None 을 반환한 경우(타임아웃/파싱 실패) 추가 LLM 호출 방지
        if m is None:
            return plan
        return _maybe_override_plan_with_rag_priority(
            plan,
            nl,
            summary,
            rows,
            kv,
            step_trace=step_trace,
            mcp_tools=mcp_tools,
            schema_meta=schema_meta,
            force_stepwise=force_stepwise,
            knowledge=knowledge,
            plan_timeout_sec=plan_timeout_sec,
            db_conn=db_conn,
        )

    m = llm_plan(
        nl,
        summary,
        rows,
        kv,
        step_trace,
        schema_meta=schema_meta,
        force_stepwise=force_stepwise,
        knowledge=knowledge,
        timeout_sec=plan_timeout_sec,
    )
    plan = _normalize_sql_plan(m)
    plan = _maybe_auto_discover(plan, nl, kv, schema_meta, None, use_mcp=False)
    if m is None:
        return plan
    return _maybe_override_plan_with_rag_priority(
        plan,
        nl,
        summary,
        rows,
        kv,
        step_trace=step_trace,
        mcp_tools=None,
        schema_meta=schema_meta,
        force_stepwise=force_stepwise,
        knowledge=knowledge,
        plan_timeout_sec=plan_timeout_sec,
        db_conn=db_conn,
    )


def _validate_step_and_record(
    conn,
    conversation_id: str,
    payload: dict[str, Any],
) -> None:
    if _near_run_deadline():
        return
    if not AGENT_STEP_VALIDATION:
        return
    if _should_skip_aux_updates(
        str(payload.get("tool", "")),
        payload.get("result_summary") if isinstance(payload.get("result_summary"), dict) else None,
        str(payload.get("error", "") or ""),
    ):
        return
    step_index = payload.get("step_index")
    if isinstance(step_index, int) and AGENT_STEP_VALIDATION_EVERY > 1:
        if step_index % AGENT_STEP_VALIDATION_EVERY != 0:
            return
    start = time.perf_counter()
    result = llm_validate_step(payload)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    log_timing(
        "step_validation",
        {"conversation_id": conversation_id, "step_index": step_index or 0, "ms": round(elapsed_ms, 2)},
    )
    if not isinstance(result, dict):
        return
    try:
        save_memory_kv(
            conn,
            conversation_id,
            "last_step_validation",
            json.dumps(result, ensure_ascii=False),
        )
    except Exception:
        pass
    try:
        log_text("step_validation", json.dumps(result, ensure_ascii=False, indent=2))
    except Exception:
        pass



def _load_pending_steps(kv: dict[str, str]) -> tuple[list[str], int]:
    raw = kv.get("pending_steps") if isinstance(kv, dict) else None
    idx_raw = kv.get("pending_step_index") if isinstance(kv, dict) else None
    try:
        idx = int(idx_raw) if idx_raw is not None else 0
    except Exception:
        idx = 0
    if not raw:
        return [], idx
    try:
        data = json.loads(raw)
    except Exception:
        return [], idx
    if not isinstance(data, list):
        return [], idx
    steps = [str(item).strip() for item in data if str(item).strip()]
    return steps, max(0, idx)

def _save_pending_steps(
    conn,
    conversation_id: str,
    steps: list[str],
    index: int,
) -> None:
    try:
        if steps:
            save_memory_kv(conn, conversation_id, "pending_steps", json.dumps(steps, ensure_ascii=False))
            save_memory_kv(conn, conversation_id, "pending_step_index", str(max(0, index)))
        else:
            save_memory_kv(conn, conversation_id, "pending_steps", "")
            save_memory_kv(conn, conversation_id, "pending_step_index", "0")
    except Exception:
        pass

def _advance_pending_steps(
    conn,
    conversation_id: str,
    steps: list[str],
    index: int,
) -> tuple[list[str], int]:
    if not steps:
        return [], 0
    next_index = index + 1
    if next_index >= len(steps):
        _save_pending_steps(conn, conversation_id, [], 0)
        return [], 0
    _save_pending_steps(conn, conversation_id, steps, next_index)
    return steps, next_index

