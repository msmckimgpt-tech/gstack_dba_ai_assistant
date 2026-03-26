"""mysql_ai agent CLI entry point.

This is the main entry point. All business logic is in the modules/ package.
"""
import argparse
import json
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from rich.panel import Panel
from rich.table import Table

# Import everything from unified module namespace
from modules import *
from modules import config as cfg

def _extract_columns_hint(knowledge_payload: dict | None) -> list[dict[str, Any]]:
    """knowledge_payload의 insight_objects에서 schema.table → columns 매핑을 추출."""
    if not isinstance(knowledge_payload, dict):
        return []
    hints: list[dict[str, Any]] = []
    for obj in knowledge_payload.get("insight_objects") or []:
        cols = obj.get("columns") or []
        if cols:
            hints.append({"schema": obj.get("schema", ""), "table": obj.get("table", ""), "columns": cols})
    return hints


def _emit_forced_conclusion(
    mem_conn, original_request: str, kv: dict, step_trace: list, step_index: int,
) -> None:
    """강제 결론을 생성하고 메모리에 기록한다. 호출 후 return 필요."""
    forced = _build_forced_conclusion(original_request, kv, step_trace)
    console.print(Panel.fit(forced, title="강제 결론"))
    save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", forced)
    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", forced)
    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_forced_conclusion", forced)
    summary_text = build_summary_text("강제 결론", {"summary": forced}, "")
    _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
    _refresh_summary_after_step(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1)


def run_once(nl: str, no_exec: bool, max_show: int) -> None:
    try:
        mem_conn = connect_with_retry(database=MEMORY_DB, autocommit=True)
    except Exception as exc:
        err_msg = str(exc)
        err_code = getattr(exc, "errno", None)
        friendly = _friendly_error_message(err_msg, err_code)
        msg = friendly or f"DB 연결 실패: {err_msg}"
        console.print(Panel.fit(msg, title="오류"))
        return

    db_conn = None
    run_id = ""
    run_start = time.perf_counter()
    _set_run_deadline(max(1000, int(AGENT_EARLY_FINALIZE_MS)))
    skip_status_update = False
    try:
        db_conn = connect_with_retry(database=DB_CONNECT_DB, autocommit=True)
    except Exception as exc:
        if AGENT_MODE != "mcp":
            err_msg = str(exc)
            err_code = getattr(exc, "errno", None)
            friendly = _friendly_error_message(err_msg, err_code)
            msg = friendly or f"DB 연결 실패: {err_msg}"
            console.print(Panel.fit(msg, title="오류"))
            save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", msg)
            return

    try:
        if nl.strip() == "__CLEAR_MEMORY_TABLES__":
            clear_memory_tables(mem_conn)
            kept = ", ".join(AGENT_MEMORY_CLEAR_KEEP_IDS) if AGENT_MEMORY_CLEAR_KEEP_IDS else "(없음)"
            console.print(Panel.fit(f"대화 기록을 삭제했습니다. 보존 ConversationId: {kept}"))
            skip_status_update = True
            return
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
        cfg.CURRENT_RUN_ID = run_id
        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", "")
        save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "user", nl)
        original_request = nl
        current_request = nl
        step_trace: list[dict[str, Any]] = []
        enriched_tables: set[str] = set()
        auto_continue_budget = 5
        not_found_recovery_budget = 1
        file_question_guard_used = False
        sql_empty_guard_used = False
        seen_file_reads: set[str] = set()
        executed_step_keys: set[str] = set()
        global_kb_cache: dict[str, Any] = {"by_scope": {}}
        timing_breakdown = _timing_breakdown_template(run_id, cfg.MEMORY_CONVERSATION_ID, original_request)
        set_run_status(mem_conn, cfg.MEMORY_CONVERSATION_ID, "processing", run_id=run_id)
        log_timing(
            "run_start",
            {
                "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                "run_id": run_id,
                "request": " ".join(original_request.split())[:200],
            },
        )
    
        if db_conn is not None:
            try:
                known = load_known_schemas(db_conn)
                if known:
                    cfg.KNOWN_SCHEMAS.clear()
                    cfg.KNOWN_SCHEMAS.extend(known)
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "known_schemas",
                        json.dumps(known, ensure_ascii=False),
                    )
            except Exception:
                pass
    
        mem_rw_start = time.perf_counter()
        _, _, kv0 = load_memory_context(
            mem_conn, cfg.MEMORY_CONVERSATION_ID, AGENT_MEMORY_MAX_TURNS
        )
        _timing_breakdown_add(
            timing_breakdown,
            "memory_rw_ms",
            (time.perf_counter() - mem_rw_start) * 1000.0,
        )
        last_question = (kv0.get("last_assistant_question") or "").strip()
        if last_question:
            _update_kb_from_answer(
                mem_conn,
                cfg.MEMORY_CONVERSATION_ID,
                kv0,
                last_question,
                nl,
                source_run_id=run_id,
            )
            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_assistant_question", "")
        followup_resolved = _resolve_followup_request_input(nl, kv0)
        if followup_resolved:
            original_request = followup_resolved
            current_request = followup_resolved
            try:
                save_memory_kv(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    "followup_resolved_request",
                    followup_resolved,
                )
            except Exception:
                pass
        prev_origin = (kv0.get("origin_request") or "").strip()
        origin_shift_type = _should_refresh_origin_request(prev_origin, nl, kv0)
        if origin_shift_type == "shift":
            # Full topic shift: reset origin, thread_goal, domain anchor, and all context.
            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "origin_request", nl)
            kv0["origin_request"] = nl
            thread_goal = _derive_topic(nl, max_len=200)
            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "thread_goal", thread_goal)
            kv0["thread_goal"] = thread_goal
            _purge_transient_schema_usage_facts(mem_conn, cfg.MEMORY_CONVERSATION_ID)
            _clear_last_resolved_object_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID)
            try:
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "domain_anchor", "")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_domain_drift", "")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "cross_session_anchor_schema", "")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "cross_session_anchor_table", "")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_result_intent", "")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_result_summary", "")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", "")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_sql", "")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "followup_resolved_request", "")
            except Exception:
                pass
            try:
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "preferred_schema", "")
                kv0["preferred_schema"] = ""
            except Exception:
                pass
            kv0.pop("domain_anchor", None)
            kv0["last_domain_drift"] = ""
            refreshed_anchor = _build_domain_anchor(nl, kv0, cfg.KNOWN_SCHEMAS)
            if refreshed_anchor:
                kv0["domain_anchor"] = refreshed_anchor
                try:
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "domain_anchor",
                        json.dumps(refreshed_anchor, ensure_ascii=False),
                    )
                except Exception:
                    pass
            derived = _generate_topic_from_request(nl)
            if derived:
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "topic", derived)
        elif origin_shift_type == "evolve":
            # Goal evolution within the same domain: update thread_goal only.
            # Preserve origin_request, domain anchor, schema context, and all prior findings.
            thread_goal = _derive_topic(nl, max_len=200)
            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "thread_goal", thread_goal)
            kv0["thread_goal"] = thread_goal
            derived = _generate_topic_from_request(nl)
            if derived:
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "topic", derived)
        # thread_goal이 아직 없으면 현재 origin에서 생성
        if not kv0.get("thread_goal") and kv0.get("origin_request"):
            thread_goal = _derive_topic(kv0["origin_request"], max_len=200)
            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "thread_goal", thread_goal)
            kv0["thread_goal"] = thread_goal
        initial_scope = _build_request_scope_key(nl, kv0)
        _set_current_fact_scope(initial_scope)
        global_kb_compact = _load_global_kb_compact_cached(
            mem_conn, global_kb_cache, 0.0, scope_key=initial_scope
        ).strip()
        if global_kb_compact:
            kv0["global_kb_compact"] = global_kb_compact
        seeded_schema = _seed_preferred_schema_from_global(
            mem_conn,
            cfg.MEMORY_CONVERSATION_ID,
            original_request,
            kv0,
            cfg.KNOWN_SCHEMAS,
        )
        if seeded_schema:
            kv0["preferred_schema"] = seeded_schema
        domain_anchor0 = _ensure_domain_anchor(
            mem_conn,
            cfg.MEMORY_CONVERSATION_ID,
            original_request,
            kv0,
            cfg.KNOWN_SCHEMAS,
        )
        if domain_anchor0:
            kv0["domain_anchor"] = domain_anchor0
        if db_conn is not None:
            _bootstrap_schema_insights(db_conn, mem_conn, cfg.KNOWN_SCHEMAS, run_id=run_id)
            inline_scan, inline_reason = _should_run_inline_insight_scan(mem_conn)
            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "inline_insight_scan", "1" if inline_scan else "0")
            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "inline_insight_reason", inline_reason)
            if inline_scan:
                _scan_instance_schema_insights(db_conn, mem_conn, cfg.KNOWN_SCHEMAS, run_id=run_id)
        retry_state = _note_similar_retry(mem_conn, cfg.MEMORY_CONVERSATION_ID, kv0, original_request)
        if retry_state:
            kv0["retry_hint"] = retry_state.get("hint", "")
            kv0["retry_similar_count"] = retry_state.get("count", "0")
        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_request", nl)
        pending_steps, pending_step_index = _load_pending_steps(kv0)
        if not pending_steps and _detect_stepwise_request(nl):
            steps = _parse_stepwise_list(nl)
            if len(steps) >= 2:
                pending_steps = steps
                pending_step_index = 0
                _save_pending_steps(mem_conn, cfg.MEMORY_CONVERSATION_ID, pending_steps, pending_step_index)
        step_trace = load_recent_steps(mem_conn, cfg.MEMORY_CONVERSATION_ID, AGENT_STEP_TRACE_MAX)
        if step_trace:
            compacted: list[dict[str, Any]] = []
            for entry in step_trace:
                _append_step_trace(compacted, entry)
            step_trace = compacted
        else:
            step_trace = load_step_trace_from_kv(kv0)
        step_trace = _trim_step_trace(step_trace)
        if step_trace:
            try:
                save_memory_kv(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    "step_trace",
                    json.dumps(step_trace, ensure_ascii=False),
                )
            except Exception:
                pass
        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_run_id", run_id)
        if not kv0.get("origin_request"):
            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "origin_request", original_request)
        topic_val = (kv0.get("topic") or "").strip()
        if not topic_val or topic_val.startswith("대화 "):
            derived = _generate_topic_from_request(original_request)
            if derived:
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "topic", derived)
    
        mcp_tools = None
        mcp_catalog = {}
        if AGENT_MODE == "mcp":
            mcp_catalog = mcp_tools_catalog()
            mcp_tools = list(mcp_catalog.keys())
    
        schema_meta_cached: dict[str, Any] = {}
        schema_meta_loaded = False
        schema_meta_schema = ""
        if AGENT_GLOBAL_SCHEMA_META_CACHE:
            default_schema = _preferred_default_schema(cfg.KNOWN_SCHEMAS)
            cached_meta = _load_global_schema_meta(mem_conn, default_schema) if default_schema else None
            if cached_meta:
                schema_meta_cached = cached_meta
                schema_meta_loaded = True
                schema_meta_schema = default_schema
    
        for step_index in range(max(1, AGENT_MAX_STEPS)):
            if _cancel_requested(mem_conn, cfg.MEMORY_CONVERSATION_ID, run_id):
                _clear_cancel_request(mem_conn, cfg.MEMORY_CONVERSATION_ID)
                _purge_run_steps(mem_conn, cfg.MEMORY_CONVERSATION_ID, run_id)
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", "")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_result_summary", "")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_csv_path", "")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_csv_preview", "")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "pending_steps", "")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "pending_step_index", "0")
                cancel_msg = (
                    "요청이 취소되었습니다. 이번 실행의 화면 결과/CSV 참조는 제거되며, "
                    "이미 생성된 CSV/로그 파일은 유지됩니다. 필요하면 다시 요청해주세요."
                )
                save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", cancel_msg)
                set_run_status(mem_conn, cfg.MEMORY_CONVERSATION_ID, "canceled", run_id=run_id, error="")
                skip_status_update = True
                return
            mem_rw_start = time.perf_counter()
            summary, rows, kv = load_memory_context(mem_conn, cfg.MEMORY_CONVERSATION_ID, AGENT_MEMORY_MAX_TURNS)
            _timing_breakdown_add(
                timing_breakdown,
                "memory_rw_ms",
                (time.perf_counter() - mem_rw_start) * 1000.0,
            )
            current_effective_request = _effective_request(
                current_request, original_request, kv.get("origin_request", "")
            )
            known_schemas = _load_known_schemas_from_kv(kv) or cfg.KNOWN_SCHEMAS
            domain_anchor = _ensure_domain_anchor(
                mem_conn,
                cfg.MEMORY_CONVERSATION_ID,
                current_effective_request,
                kv,
                known_schemas,
            )
            corrected_request, drift_reason = _apply_domain_anchor_guard(
                current_effective_request,
                domain_anchor,
                known_schemas,
            )
            if drift_reason and corrected_request and corrected_request != current_effective_request:
                current_effective_request = corrected_request
                current_request = corrected_request
                try:
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "last_domain_drift",
                        drift_reason,
                    )
                except Exception:
                    pass
            request_scope_key = _build_request_scope_key(current_effective_request, kv)
            _set_current_fact_scope(request_scope_key)
            global_kb_compact = _load_global_kb_compact_cached(
                mem_conn,
                global_kb_cache,
                AGENT_GLOBAL_KB_REFRESH_SEC,
                scope_key=request_scope_key,
            ).strip()
            if global_kb_compact:
                kv["global_kb_compact"] = global_kb_compact
            if "created_at" not in kv:
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "created_at", utc_now_iso())
            if (
                current_request == "continue"
                and not pending_steps
                and _should_auto_finalize(kv)
            ):
                return
            elapsed_ms = (time.perf_counter() - run_start) * 1000.0
            remaining_budget_ms = max(0, _remaining_run_budget_ms())
            if step_index > 0 and elapsed_ms >= max(1000, AGENT_EARLY_FINALIZE_MS):
                timing_breakdown["early_finalize"] = 1
                _emit_forced_conclusion(mem_conn, original_request, kv, step_trace, step_index)
                return
            if (
                step_index > 0
                and remaining_budget_ms <= max(1000, int(AGENT_PLAN_TIMEOUT_MIN_SEC) * 1000)
            ):
                timing_breakdown["early_finalize"] = 1
                _emit_forced_conclusion(mem_conn, original_request, kv, step_trace, step_index)
                return

            schema_meta = {}
            if schema_meta_loaded and (AGENT_SCHEMA_META_CACHE or AGENT_GLOBAL_SCHEMA_META_CACHE):
                schema_meta = schema_meta_cached
            elif db_conn is None:
                default_schema = _preferred_default_schema(known_schemas)
                cached = _load_global_schema_meta(mem_conn, default_schema) if default_schema else None
                if cached:
                    schema_meta = cached
                    schema_meta_cached = cached
                    schema_meta_loaded = True
                    schema_meta_schema = default_schema
            elif db_conn is not None:
                try:
                    default_schema = _preferred_default_schema(known_schemas)
                    if not default_schema:
                        raise RuntimeError("기본 스키마 미지정 상태: 스키마 감지 후 재시도")
                    meta_start = time.perf_counter()
                    schema_meta = load_schema_metadata(db_conn, default_schema)
                    schema_meta_cached = schema_meta
                    schema_meta_loaded = True
                    schema_meta_schema = default_schema
                    _save_global_schema_meta(mem_conn, default_schema, schema_meta)
                    schema_meta_ms = (time.perf_counter() - meta_start) * 1000.0
                    log_timing(
                        "schema_meta",
                        {
                            "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                            "step_index": step_index + 1,
                            "ms": round(schema_meta_ms, 2),
                        },
                    )
                    _timing_breakdown_add(timing_breakdown, "schema_meta_ms", schema_meta_ms)
                except Exception:
                    schema_meta = {}
            requested_schema = _detect_requested_schema(
                current_effective_request,
                known_schemas,
            )
            request_scope_key = _build_request_scope_key(
                current_effective_request,
                kv,
                requested_schema,
            )
            _set_current_fact_scope(request_scope_key)
            if requested_schema and requested_schema != schema_meta_schema:
                cached = _load_global_schema_meta(mem_conn, requested_schema)
                if cached:
                    schema_meta = cached
                    schema_meta_cached = cached
                    schema_meta_loaded = True
                    schema_meta_schema = requested_schema
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "preferred_schema",
                        requested_schema,
                    )
            if (
                db_conn is not None
                and requested_schema
                and requested_schema != schema_meta_schema
            ):
                try:
                    meta_start = time.perf_counter()
                    schema_meta = load_schema_metadata(db_conn, requested_schema)
                    schema_meta_cached = schema_meta
                    schema_meta_loaded = True
                    schema_meta_schema = requested_schema
                    _save_global_schema_meta(mem_conn, requested_schema, schema_meta)
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "preferred_schema",
                        requested_schema,
                    )
                    schema_meta_ms = (time.perf_counter() - meta_start) * 1000.0
                    log_timing(
                        "schema_meta",
                        {
                            "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                            "step_index": step_index + 1,
                            "ms": round(schema_meta_ms, 2),
                        },
                    )
                    _timing_breakdown_add(timing_breakdown, "schema_meta_ms", schema_meta_ms)
                except Exception:
                    pass
            if db_conn is not None and (not schema_meta or not schema_meta.get("tables")):
                preferred_schema = (kv.get("preferred_schema") or "").strip()
                if not preferred_schema:
                    preferred_schema = (
                        _infer_preferred_schema(
                            db_conn,
                            mem_conn,
                            _effective_request(
                                current_request, original_request, kv.get("origin_request", "")
                            ),
                            kv,
                            known_schemas,
                            cfg.MEMORY_CONVERSATION_ID,
                            scope_key=request_scope_key,
                        )
                        or ""
                    )
                    if preferred_schema:
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "preferred_schema", preferred_schema)
                if preferred_schema and preferred_schema != schema_meta_schema:
                    cached = _load_global_schema_meta(mem_conn, preferred_schema)
                    if cached:
                        schema_meta = cached
                        schema_meta_cached = cached
                        schema_meta_loaded = True
                        schema_meta_schema = preferred_schema
                    else:
                        try:
                            meta_start = time.perf_counter()
                            schema_meta = load_schema_metadata(db_conn, preferred_schema)
                            schema_meta_cached = schema_meta
                            schema_meta_loaded = True
                            schema_meta_schema = preferred_schema
                            _save_global_schema_meta(mem_conn, preferred_schema, schema_meta)
                            schema_meta_ms = (time.perf_counter() - meta_start) * 1000.0
                            log_timing(
                                "schema_meta",
                                {
                                    "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                                    "step_index": step_index + 1,
                                    "ms": round(schema_meta_ms, 2),
                                },
                            )
                            _timing_breakdown_add(timing_breakdown, "schema_meta_ms", schema_meta_ms)
                        except Exception:
                            pass
    
            stepwise_active = bool(pending_steps)
            if stepwise_active and pending_step_index < len(pending_steps):
                current_request = pending_steps[pending_step_index]

            request_for_context = _effective_request(
                current_request, original_request, kv.get("origin_request", "")
            )
            request_scope_key = _build_request_scope_key(
                request_for_context,
                kv,
                requested_schema,
            )
            _set_current_fact_scope(request_scope_key)

            explicit_request_schema = _detect_requested_schema(request_for_context, known_schemas) or ""
            same_domain_cue = _has_same_domain_cue(request_for_context)
            anchor_fast_schema = (
                str((domain_anchor or {}).get("schema") or "").strip()
                or str(kv.get("preferred_schema") or "").strip()
            )
            first_turn_without_result = not _has_prior_result_context(kv)
            cross_session_anchor_fastpath = (
                AGENT_GLOBAL_FASTPATH_FIRST_TURN
                and step_index == 0
                and first_turn_without_result
                and bool(anchor_fast_schema)
                and not explicit_request_schema
            )
            if cross_session_anchor_fastpath:
                if anchor_fast_schema != schema_meta_schema:
                    cached_anchor_meta = _load_global_schema_meta(mem_conn, anchor_fast_schema)
                    if cached_anchor_meta:
                        schema_meta = cached_anchor_meta
                        schema_meta_cached = cached_anchor_meta
                        schema_meta_loaded = True
                        schema_meta_schema = anchor_fast_schema
                    elif db_conn is not None:
                        try:
                            meta_start = time.perf_counter()
                            schema_meta = load_schema_metadata(db_conn, anchor_fast_schema)
                            schema_meta_cached = schema_meta
                            schema_meta_loaded = True
                            schema_meta_schema = anchor_fast_schema
                            _save_global_schema_meta(mem_conn, anchor_fast_schema, schema_meta)
                            schema_meta_ms = (time.perf_counter() - meta_start) * 1000.0
                            _timing_breakdown_add(timing_breakdown, "schema_meta_ms", schema_meta_ms)
                        except Exception:
                            pass
                try:
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "cross_session_anchor_schema",
                        anchor_fast_schema,
                    )
                except Exception:
                    pass
            else:
                try:
                    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "cross_session_anchor_schema", "")
                except Exception:
                    pass

            auto_file_path = None
            if _has_file_intent(request_for_context):
                auto_file_path = _auto_select_file_for_request(
                    request_for_context, kv.get("last_file_search")
                )
                if auto_file_path and kv.get("last_file_read_path") == auto_file_path:
                    auto_file_path = None
            if _is_restore_execute_request(
                request_for_context,
                str(kv.get("last_file_search") or ""),
            ):
                restore_file = _extract_restore_filename(request_for_context)
                if not restore_file:
                    restore_file = _pick_file_from_last_search(
                        str(kv.get("last_file_search") or ""),
                        restore_only=True,
                    ) or ""
                if not restore_file:
                    guard = _format_user_answer_text(
                        "복원 실행 대상 파일이 확정되지 않았습니다. "
                        "먼저 `/shared`에서 `.sql` 또는 `.dump` 파일 목록을 조회해 선택해 주세요."
                    )
                    console.print(Panel.fit(guard, title="실행 가드"))
                    save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", guard)
                    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", guard)
                    summary_text = build_summary_text("실행 가드", None, guard)
                    _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                    _refresh_summary_after_step(
                        mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                    )
                    return
            forced_plan: dict[str, Any] | None = None
            if _is_restore_list_request(request_for_context):
                restore_file_hint = _extract_restore_filename(request_for_context)
                pattern = ""
                if restore_file_hint:
                    pattern = os.path.basename(restore_file_hint)
                forced_plan = {
                    "action": "step",
                    "tool": "file_search",
                    "args": {"root": "/shared", "pattern": pattern, "limit": 50},
                    "intent": "복원 가능한 SQL 덤프 파일 탐색",
                    "is_write": False,
                }

            plan_kv = _filter_kv_for_context(kv, request_for_context)
            plan_timeout_sec = _compute_plan_timeout_sec(step_index, kv, elapsed_ms)
            timing_breakdown["plan_timeout_sec"] = int(plan_timeout_sec)
            timing_breakdown["remaining_budget_ms_before_plan"] = int(remaining_budget_ms)
            plan_start = time.perf_counter()
            _kb_request = request_for_context
            if _kb_request.strip().lower() in {
                "continue", "continue.", "계속", "계속.", "다음", "진행", "계속 진행",
            }:
                _kb_request = original_request or kv.get("origin_request", "") or _kb_request
            knowledge_payload = _build_knowledge_payload(
                mem_conn,
                cfg.MEMORY_CONVERSATION_ID,
                _kb_request,
                AGENT_KB_FACT_LIMIT,
                AGENT_GLOBAL_KB_FACT_LIMIT,
                scope_key=request_scope_key,
                kv=kv,
            )
            log_insight_route(
                "knowledge_payload",
                {
                    "run_id": run_id,
                    "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                    "step_index": step_index + 1,
                    "request": _compact_request_for_log(request_for_context),
                    **_summarize_knowledge_payload_for_log(knowledge_payload),
                },
            )
            try:
                coverage = (
                    knowledge_payload.get("coverage_stats")
                    if isinstance(knowledge_payload, dict)
                    else {}
                )
                if isinstance(coverage, dict):
                    timing_breakdown["retrieval_depth"] = int(coverage.get("retrieval_depth", 0) or 0)
                    timing_breakdown["retrieval_depth_reason"] = str(
                        coverage.get("retrieval_depth_reason", "") or ""
                    )
                    timing_breakdown["retrieval_depth_filter"] = str(
                        coverage.get("retrieval_depth_filter", "") or ""
                    )
            except Exception:
                pass
            insight_fast_info: dict[str, Any] = {
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
            fast_object_plan = None
            knowledge_fallback_attempted = False
            if auto_file_path:
                plan = {
                    "action": "step",
                    "tool": "file_read",
                    "args": {"file_path": auto_file_path, "max_bytes": 65536},
                    "intent": "파일 내용 확인",
                    "is_write": False,
                }
            elif forced_plan:
                plan = forced_plan
            else:
                fast_object_plan, insight_fast_info = _build_insight_object_fast_plan(
                    mem_conn,
                    db_conn,
                    request_for_context,
                    kv,
                    mcp_tools,
                    schema_meta,
                    scope_key=request_scope_key,
                    require_aggregate=False,
                    knowledge=knowledge_payload,
                )
                log_insight_route(
                    "insight_fastpath_attempt",
                    {
                        "run_id": run_id,
                        "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                        "step_index": step_index + 1,
                        "phase": "primary",
                        "request": _compact_request_for_log(request_for_context),
                        "used": int(insight_fast_info.get("used", 0) or 0),
                        "object": str(insight_fast_info.get("object") or ""),
                        "score": int(insight_fast_info.get("score", 0) or 0),
                        "source": str(insight_fast_info.get("source") or ""),
                        "fallback_reason": str(insight_fast_info.get("fallback_reason") or ""),
                        "fact_key": str(insight_fast_info.get("fact_key") or ""),
                        "llm_confidence": float(insight_fast_info.get("llm_confidence", 0.0) or 0.0),
                        "candidate_count": int(insight_fast_info.get("candidate_count", 0) or 0),
                        "top_candidates": insight_fast_info.get("top_candidates") or [],
                    },
                )
                if fast_object_plan:
                    plan = fast_object_plan
                else:
                    plan = None
                    if (
                        AGENT_KNOWLEDGE_SQL_FALLBACK
                        and _knowledge_has_table_evidence(knowledge_payload)
                    ):
                        fallback_timeout_sec = min(
                            max(6, int(AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC)),
                            max(6, int(plan_timeout_sec)),
                        )
                        pre_fallback_plan, pre_fallback_reason = _build_knowledge_sql_fallback_plan(
                            request_for_context,
                            knowledge_payload,
                            mcp_tools,
                            kv=kv,
                            schema_meta=schema_meta,
                            db_conn=db_conn,
                            timeout_sec=fallback_timeout_sec,
                        )
                        knowledge_fallback_attempted = True
                        if pre_fallback_plan:
                            plan = pre_fallback_plan
                        log_insight_route(
                            "knowledge_sql_fallback_attempt",
                            {
                                "run_id": run_id,
                                "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                                "step_index": step_index + 1,
                                "phase": "pre_plan",
                                "request": _compact_request_for_log(request_for_context),
                                "timeout_sec": int(fallback_timeout_sec),
                                "used": int(1 if pre_fallback_plan else 0),
                                "reason": str(pre_fallback_reason or ""),
                            },
                        )
                    if not plan:
                        plan = _plan_zero_result_diagnostic(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            kv,
                            run_id,
                            mcp_tools,
                        )
                    if not plan:
                        plan = plan_next_step(
                            request_for_context,
                            summary,
                            rows,
                            plan_kv,
                            step_trace,
                            mcp_tools=mcp_tools,
                            schema_meta=schema_meta,
                            force_stepwise=stepwise_active,
                            knowledge=knowledge_payload,
                            plan_timeout_sec=plan_timeout_sec,
                            db_conn=db_conn,
                        )
            if (
                AGENT_INSIGHT_OBJECT_FASTPATH
                and not auto_file_path
                and not forced_plan
                and not _has_file_intent(request_for_context)
                and fast_object_plan is None
                and (
                    _is_meta_exploration_plan(plan)
                    or str(plan.get("action", "")).strip().lower() == "ask"
                )
            ):
                retry_block_reasons = {
                    "disabled",
                    "empty_request",
                    "no_table_insight",
                }
                fallback_reason = str(insight_fast_info.get("fallback_reason") or "").strip()
                if fallback_reason in retry_block_reasons:
                    forced_insight_plan = None
                    forced_insight_info = {}
                else:
                    forced_insight_plan, forced_insight_info = _build_insight_object_fast_plan(
                        mem_conn,
                        db_conn,
                        request_for_context,
                        kv,
                        mcp_tools,
                        schema_meta,
                        scope_key=request_scope_key,
                        require_aggregate=True,
                        knowledge=knowledge_payload,
                    )
                log_insight_route(
                    "insight_fastpath_attempt",
                    {
                        "run_id": run_id,
                        "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                        "step_index": step_index + 1,
                        "phase": "meta_or_ask_guard",
                        "request": _compact_request_for_log(request_for_context),
                        "used": int((forced_insight_info or {}).get("used", 0) or 0),
                        "object": str((forced_insight_info or {}).get("object") or ""),
                        "score": int((forced_insight_info or {}).get("score", 0) or 0),
                        "source": str((forced_insight_info or {}).get("source") or ""),
                        "fallback_reason": (
                            str((forced_insight_info or {}).get("fallback_reason") or "")
                            or fallback_reason
                        ),
                        "fact_key": str((forced_insight_info or {}).get("fact_key") or ""),
                        "llm_confidence": float(
                            (forced_insight_info or {}).get("llm_confidence", 0.0) or 0.0
                        ),
                        "candidate_count": int(
                            (forced_insight_info or {}).get("candidate_count", 0) or 0
                        ),
                        "top_candidates": (forced_insight_info or {}).get("top_candidates") or [],
                    },
                )
                if forced_insight_plan:
                    plan = forced_insight_plan
                    if int(forced_insight_info.get("used", 0) or 0) > 0:
                        insight_fast_info = forced_insight_info
            if (
                AGENT_KNOWLEDGE_SQL_FALLBACK
                and not auto_file_path
                and not forced_plan
                and not _has_file_intent(request_for_context)
                and not knowledge_fallback_attempted
                and _knowledge_has_table_evidence(knowledge_payload)
                and (
                    str(plan.get("action", "")).strip().lower() == "ask"
                    or _is_meta_exploration_plan(plan)
                )
            ):
                fallback_timeout_sec = min(
                    max(5, int(AGENT_KNOWLEDGE_SQL_FALLBACK_TIMEOUT_SEC)),
                    max(5, int(plan_timeout_sec)),
                )
                fallback_plan, fallback_reason = _build_knowledge_sql_fallback_plan(
                    request_for_context,
                    knowledge_payload,
                    mcp_tools,
                    kv=kv,
                    schema_meta=schema_meta,
                    db_conn=db_conn,
                    timeout_sec=fallback_timeout_sec,
                )
                log_insight_route(
                    "knowledge_sql_fallback_attempt",
                    {
                        "run_id": run_id,
                        "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                        "step_index": step_index + 1,
                        "phase": "post_plan",
                        "request": _compact_request_for_log(request_for_context),
                        "timeout_sec": int(fallback_timeout_sec),
                        "used": int(1 if fallback_plan else 0),
                        "reason": str(fallback_reason or ""),
                    },
                )
                if fallback_plan:
                    plan = fallback_plan
                    log_insight_route(
                        "knowledge_sql_fallback",
                        {
                            "run_id": run_id,
                            "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                            "step_index": step_index + 1,
                            "request": _compact_request_for_log(request_for_context),
                            "timeout_sec": int(fallback_timeout_sec),
                            "action": str(fallback_plan.get("action") or "").strip().lower(),
                            "intent": str(fallback_plan.get("intent") or "").strip(),
                        },
                    )
            try:
                timing_breakdown["fast_object_ref_used"] = (
                    1 if int(insight_fast_info.get("used", 0) or 0) > 0 else 0
                )
                timing_breakdown["fast_object_ref_object"] = str(
                    insight_fast_info.get("object") or ""
                )
                timing_breakdown["fast_object_ref_score"] = int(
                    insight_fast_info.get("score", 0) or 0
                )
                timing_breakdown["fast_object_ref_source"] = str(
                    insight_fast_info.get("source") or ""
                )
                timing_breakdown["fast_object_ref_fallback_reason"] = str(
                    insight_fast_info.get("fallback_reason") or ""
                )
                timing_breakdown["fast_object_ref_fact_key"] = str(
                    insight_fast_info.get("fact_key") or ""
                )
                timing_breakdown["fast_object_ref_confidence"] = float(
                    insight_fast_info.get("llm_confidence", 0.0) or 0.0
                )
            except Exception:
                pass
            if int(insight_fast_info.get("used", 0) or 0) > 0:
                try:
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "last_resolved_object",
                        str(insight_fast_info.get("object") or ""),
                    )
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "last_resolved_object_score",
                        str(int(insight_fast_info.get("score", 0) or 0)),
                    )
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "last_resolved_object_source",
                        str(insight_fast_info.get("source") or ""),
                    )
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "last_resolved_object_at",
                        utc_now_iso(),
                    )
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "last_resolved_fact_key",
                        str(insight_fast_info.get("fact_key") or ""),
                    )
                except Exception:
                    pass
            was_meta_plan = _is_meta_exploration_plan(plan)
            plan = _apply_meta_exploration_budget(
                plan,
                step_trace,
                request_for_context,
                {
                    **kv,
                    "preferred_schema": anchor_fast_schema or str(kv.get("preferred_schema") or "").strip(),
                },
                mcp_tools,
                schema_meta,
            )
            now_meta_plan = _is_meta_exploration_plan(plan)
            if now_meta_plan:
                try:
                    timing_breakdown["meta_exploration_used"] = int(
                        timing_breakdown.get("meta_exploration_used", 0)
                    ) + 1
                except Exception:
                    timing_breakdown["meta_exploration_used"] = 1
            repeated_meta = _count_recent_meta_steps(step_trace, window=6)
            if repeated_meta > 0:
                try:
                    timing_breakdown["meta_pattern_repeated"] = max(
                        int(timing_breakdown.get("meta_pattern_repeated", 0)),
                        max(0, repeated_meta - 1),
                    )
                except Exception:
                    timing_breakdown["meta_pattern_repeated"] = max(0, repeated_meta - 1)
            try:
                save_memory_kv(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    "meta_compact_mode",
                    "1" if (was_meta_plan and not now_meta_plan) else "",
                )
            except Exception:
                pass
            log_insight_route(
                "plan_route",
                {
                    "run_id": run_id,
                    "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                    "step_index": step_index + 1,
                    "request": _compact_request_for_log(request_for_context),
                    **_summarize_plan_route_for_log(plan),
                    **_summarize_knowledge_payload_for_log(knowledge_payload),
                },
            )
            log_timing(
                "plan",
                {
                    "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                    "step_index": step_index + 1,
                    "ms": round((time.perf_counter() - plan_start) * 1000.0, 2),
                    "action": plan.get("action"),
                    "plan_timeout_sec": int(plan_timeout_sec),
                    "remaining_budget_ms": int(remaining_budget_ms),
                    "fast_object_ref_used": int(timing_breakdown.get("fast_object_ref_used", 0) or 0),
                    "fast_object_ref_object": str(timing_breakdown.get("fast_object_ref_object", "") or ""),
                    "fast_object_ref_score": int(timing_breakdown.get("fast_object_ref_score", 0) or 0),
                    "fast_object_ref_source": str(timing_breakdown.get("fast_object_ref_source", "") or ""),
                    "fast_object_ref_fallback_reason": str(
                        timing_breakdown.get("fast_object_ref_fallback_reason", "") or ""
                    ),
                    "fast_object_ref_fact_key": str(
                        timing_breakdown.get("fast_object_ref_fact_key", "") or ""
                    ),
                    "fast_object_ref_confidence": float(
                        timing_breakdown.get("fast_object_ref_confidence", 0.0) or 0.0
                    ),
                },
            )
            _timing_breakdown_add(
                timing_breakdown,
                "plan_ms",
                (time.perf_counter() - plan_start) * 1000.0,
            )
            action = plan["action"]
            intent = plan.get("intent", "")
            is_write = bool(plan.get("is_write", False))
            if AGENT_MODE == "mcp" and action == "step":
                mcp_tool_name = str(plan.get("tool") or "").strip()
                if (
                    mcp_tool_name in MCP_SEARCH_OBJECTS_CANDIDATES
                    and not _has_file_intent(request_for_context)
                ):
                    guarded_plan, guarded_info = _build_insight_object_fast_plan(
                        mem_conn,
                        db_conn,
                        request_for_context,
                        kv,
                        mcp_tools,
                        schema_meta,
                        scope_key=request_scope_key,
                        require_aggregate=True,
                        knowledge=knowledge_payload,
                    )
                    log_insight_route(
                        "insight_fastpath_attempt",
                        {
                            "run_id": run_id,
                            "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                            "step_index": step_index + 1,
                            "phase": "search_objects_guard",
                            "request": _compact_request_for_log(request_for_context),
                            "used": int(guarded_info.get("used", 0) or 0),
                            "object": str(guarded_info.get("object") or ""),
                            "score": int(guarded_info.get("score", 0) or 0),
                            "source": str(guarded_info.get("source") or ""),
                            "fallback_reason": str(guarded_info.get("fallback_reason") or ""),
                            "fact_key": str(guarded_info.get("fact_key") or ""),
                            "llm_confidence": float(guarded_info.get("llm_confidence", 0.0) or 0.0),
                            "candidate_count": int(guarded_info.get("candidate_count", 0) or 0),
                            "top_candidates": guarded_info.get("top_candidates") or [],
                            "trigger_tool": mcp_tool_name,
                        },
                    )
                    if guarded_plan and str(guarded_plan.get("action", "")).strip().lower() == "step":
                        guard_tool = str(guarded_plan.get("tool") or "").strip()
                        if guard_tool in MCP_EXECUTE_SQL_CANDIDATES:
                            plan = guarded_plan
                            action = plan["action"]
                            intent = str(plan.get("intent", "")).strip() or intent
                            is_write = bool(plan.get("is_write", False))
                            try:
                                if int(guarded_info.get("used", 0) or 0) > 0:
                                    timing_breakdown["fast_object_ref_used"] = 1
                                    timing_breakdown["fast_object_ref_object"] = str(
                                        guarded_info.get("object") or ""
                                    )
                                    timing_breakdown["fast_object_ref_score"] = int(
                                        guarded_info.get("score", 0) or 0
                                    )
                                    timing_breakdown["fast_object_ref_source"] = str(
                                        guarded_info.get("source") or ""
                                    )
                                    timing_breakdown["fast_object_ref_fallback_reason"] = ""
                                    timing_breakdown["fast_object_ref_fact_key"] = str(
                                        guarded_info.get("fact_key") or ""
                                    )
                                    timing_breakdown["fast_object_ref_confidence"] = float(
                                        guarded_info.get("llm_confidence", 0.0) or 0.0
                                    )
                                    save_memory_kv(
                                        mem_conn,
                                        cfg.MEMORY_CONVERSATION_ID,
                                        "last_resolved_object",
                                        str(guarded_info.get("object") or ""),
                                    )
                                    save_memory_kv(
                                        mem_conn,
                                        cfg.MEMORY_CONVERSATION_ID,
                                        "last_resolved_object_score",
                                        str(int(guarded_info.get("score", 0) or 0)),
                                    )
                                    save_memory_kv(
                                        mem_conn,
                                        cfg.MEMORY_CONVERSATION_ID,
                                        "last_resolved_object_source",
                                        str(guarded_info.get("source") or ""),
                                    )
                                    save_memory_kv(
                                        mem_conn,
                                        cfg.MEMORY_CONVERSATION_ID,
                                        "last_resolved_object_at",
                                        utc_now_iso(),
                                    )
                                    save_memory_kv(
                                        mem_conn,
                                        cfg.MEMORY_CONVERSATION_ID,
                                        "last_resolved_fact_key",
                                        str(guarded_info.get("fact_key") or ""),
                                    )
                                    log_insight_route(
                                        "insight_fastpath_override",
                                        {
                                            "run_id": run_id,
                                            "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                                            "step_index": step_index + 1,
                                            "phase": "search_objects_to_execute_sql",
                                            "request": _compact_request_for_log(request_for_context),
                                            "object": str(guarded_info.get("object") or ""),
                                            "score": int(guarded_info.get("score", 0) or 0),
                                            "source": str(guarded_info.get("source") or ""),
                                            "fact_key": str(guarded_info.get("fact_key") or ""),
                                            "llm_confidence": float(
                                                guarded_info.get("llm_confidence", 0.0) or 0.0
                                            ),
                                            "trigger_tool": mcp_tool_name,
                                        },
                                    )
                            except Exception:
                                pass
            if (
                (cross_session_anchor_fastpath or same_domain_cue)
                and action == "step"
                and anchor_fast_schema
                and not explicit_request_schema
            ):
                plan_tool = str(plan.get("tool") or "").strip()
                plan_args = plan.get("args") if isinstance(plan.get("args"), dict) else {}
                if plan_tool in MCP_SEARCH_OBJECTS_CANDIDATES:
                    updated_args = dict(plan_args)
                    updated_args["schema"] = anchor_fast_schema
                    plan["args"] = updated_args
                elif plan_tool in MCP_EXECUTE_SQL_CANDIDATES:
                    sql_arg = str(plan_args.get("sql", "")).strip()
                    if sql_arg:
                        sql_arg = _rewrite_schema_in_sql(sql_arg, anchor_fast_schema, known_schemas)
                        if not _sql_mentions_schema(sql_arg, anchor_fast_schema):
                            sql_arg = _prefix_use_schema(sql_arg, anchor_fast_schema)
                        updated_args = dict(plan_args)
                        updated_args["sql"] = sql_arg
                        plan["args"] = updated_args
                elif "sql" in plan:
                    sql_arg = str(plan.get("sql", "")).strip()
                    if sql_arg:
                        sql_arg = _rewrite_schema_in_sql(sql_arg, anchor_fast_schema, known_schemas)
                        if not _sql_mentions_schema(sql_arg, anchor_fast_schema):
                            sql_arg = _prefix_use_schema(sql_arg, anchor_fast_schema)
                        plan["sql"] = sql_arg
            if action != "ask":
                try:
                    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "ask_loop_count", "0")
                    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_auto_recovery", "")
                except Exception:
                    pass
    
            if action == "ask":
                question = plan.get("question", "요청 내용을 조금 더 구체적으로 알려주세요.")
                question = sanitize_user_text(question)
                try:
                    ask_loop_count = int(str(kv.get("ask_loop_count") or "0").strip())
                except Exception:
                    ask_loop_count = 0
                ask_loop_count += 1
                try:
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "ask_loop_count",
                        str(ask_loop_count),
                    )
                except Exception:
                    pass
                last_question_seen = str(kv.get("last_assistant_question") or "").strip()
                near_step_cap = step_index >= max(0, AGENT_MAX_STEPS - 2)
                ask_repeated = ask_loop_count > max(1, AGENT_ASK_LOOP_MAX) or (
                    last_question_seen and question == last_question_seen
                )
                if AGENT_GENERIC_ASK_GUARD and not ask_repeated and _is_generic_clarification_question(question):
                    coverage_stats = (
                        knowledge_payload.get("coverage_stats")
                        if isinstance(knowledge_payload, dict)
                        else {}
                    )
                    knowledge_ready = False
                    if isinstance(coverage_stats, dict):
                        knowledge_ready = (
                            int(coverage_stats.get("rag_objects_selected", 0) or 0) > 0
                            or int(coverage_stats.get("global_facts_selected", 0) or 0) > 0
                            or int(coverage_stats.get("facts_selected", 0) or 0) > 0
                        )
                    if knowledge_ready:
                        ask_repeated = True
                        _set_retry_hint(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            "generic ask 방지: 확보된 근거를 사용해 질문 대신 SQL 실행 계획 생성",
                        )
                if (
                    ask_repeated
                ) and auto_continue_budget > 0 and not is_write:
                    auto_continue_budget -= 1
                    if _is_schema_usage_intent(request_for_context):
                        fallback_request = _preserve_request_for_retry(
                            request_for_context,
                            original_request,
                        )
                        _set_retry_hint(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            "질문 반복 방지: DB 용도 요청 원문을 유지하고 탐색 결과를 근거로 답변",
                        )
                    else:
                        fallback_request = _resolve_followup_request_input(
                            request_for_context or "continue",
                            kv,
                        )
                    if not fallback_request:
                        _set_retry_hint(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            "질문 반복 방지: 요청 원문을 유지하고 이미 확보한 결과로 결론을 생성",
                        )
                        fallback_request = _preserve_request_for_retry(
                            request_for_context,
                            original_request,
                        )
                    current_request = fallback_request
                    continue
                if (ask_repeated or near_step_cap) and (auto_continue_budget <= 0 or near_step_cap):
                    _emit_forced_conclusion(mem_conn, original_request, kv, step_trace, step_index)
                    return
                if (
                    not file_question_guard_used
                    and _looks_like_file_question(question)
                    and not _has_file_intent(request_for_context)
                    and not kv.get("last_file_search")
                ):
                    file_question_guard_used = True
                    if auto_continue_budget > 0:
                        auto_continue_budget -= 1
                    _set_retry_hint(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "파일 의도 아님: 요청 원문 기준으로 DB 집계/조회 우선 진행",
                    )
                    current_request = _preserve_request_for_retry(
                        request_for_context,
                        original_request,
                    )
                    continue
                if (
                    _looks_like_file_question(question)
                    and _has_file_intent(request_for_context)
                    and "대상 데이터베이스" not in question
                    and "대상 DB" not in question
                ):
                    guard = _format_user_answer_text(
                        "파일이 특정되지 않아 실행을 중단했습니다. "
                        "복원/분석은 `.sql` 또는 `.dump` 파일을 먼저 명시해 주세요."
                    )
                    console.print(Panel.fit(guard, title="실행 가드"))
                    save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", guard)
                    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", guard)
                    summary_text = build_summary_text(intent or "실행 가드", None, guard)
                    _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                    _refresh_summary_after_step(
                        mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                    )
                    return
                if "SQL이 비어" in question:
                    sql_from_file = ""
                    last_file_read = kv.get("last_file_read")
                    if last_file_read:
                        try:
                            payload = json.loads(last_file_read)
                            content = str(payload.get("content", ""))
                        except Exception:
                            content = ""
                        sql_from_file = _maybe_build_sql_from_file(original_request, content)
                        if sql_from_file:
                            current_request = sql_from_file
                            continue
                    if (
                        AGENT_MODE == "mcp"
                        and not sql_empty_guard_used
                        and auto_continue_budget > 0
                        and not sql_from_file
                    ):
                        sql_empty_guard_used = True
                        auto_continue_budget -= 1
                        _set_retry_hint(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            "SQL 비어 있음: 요청 원문을 유지하고 필요한 테이블/컬럼 탐색 우선",
                        )
                        current_request = _preserve_request_for_retry(
                            request_for_context,
                            original_request,
                        )
                        continue
                if step_index > 0 and _is_direct_sql_request(request_for_context):
                    done_msg = sanitize_user_text(f"완료: {intent or '요청 처리 완료'}")
                    console.print(Panel.fit(done_msg))
                    save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", done_msg)
                    return
                if auto_continue_budget > 0 and _should_auto_continue(question) and not is_write:
                    auto_continue_budget -= 1
                    current_request = "continue"
                    continue
                auto_resolved = _auto_resolve_ambiguity(question, request_for_context, kv)
                if auto_resolved and auto_continue_budget > 0:
                    auto_continue_budget -= 1
                    current_request = auto_resolved
                    continue
                if step_index > 0 and _is_list_only_request(request_for_context):
                    done_msg = sanitize_user_text(f"완료: {intent or '요청 처리 완료'}")
                    console.print(Panel.fit(done_msg))
                    save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", done_msg)
                    return
                if (
                    step_index > 0
                    and _looks_like_followup_question(question)
                    and _last_step_ok_for_autodone(kv)
                ):
                    done_msg = sanitize_user_text(f"완료: {intent or '요청 처리 완료'}")
                    console.print(Panel.fit(done_msg))
                    save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", done_msg)
                    return
                console.print(Panel.fit(question, title="확인 질문"))
                save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", question)
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_assistant_question", question)
                _refresh_summary_after_ask(mem_conn, cfg.MEMORY_CONVERSATION_ID, question)
                return
    
            if action == "done":
                done_msg = sanitize_user_text(f"완료: {intent}")
                console.print(Panel.fit(done_msg))
                save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", done_msg)
                return
    
            tool_in_plan = plan.get("tool") if isinstance(plan, dict) else None
            if tool_in_plan and str(tool_in_plan).strip() in LOCAL_TOOLS:
                tool = str(tool_in_plan).strip()
                args = plan.get("args") if isinstance(plan.get("args"), dict) else {}
                args = normalize_local_args(tool, args)
                preview = (
                    f"의도={intent}\n쓰기작업={is_write}\n\n도구={tool}\n"
                    f"인자={json.dumps(args, ensure_ascii=False)}"
                )
                if AGENT_SHOW_INTERNAL:
                    print_internal(Panel.fit(preview, title="로컬 도구 단계"))
                step_log = log_text("local_tool_step", preview)
                if AGENT_SHOW_INTERNAL:
                    print_internal(f"[dim]도구 로그:[/dim] {step_log}")
                if no_exec:
                    save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", f"(실행 생략) {intent}")
                    return
    
                if tool == "file_search":
                    root = str(args.get("root", "/shared"))
                    pattern = str(args.get("pattern", "")).strip()
                    limit = int(args.get("limit", 50)) if str(args.get("limit", "")).strip() else 50
                    tool_start = time.perf_counter()
                    results = file_search(root=root, pattern=pattern, limit=limit)
                    file_req = f"{request_for_context} {original_request}".lower()
                    if any(token in file_req for token in ("복원", "복구", "restore", "dump", "백업")):
                        restore_results = [
                            item
                            for item in results
                            if _is_restore_compatible_file(str(item.get("path", "")).strip())
                        ]
                        results = restore_results
                    log_timing(
                        "local_tool",
                        {
                            "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                            "step_index": step_index + 1,
                            "tool": tool,
                            "ms": round((time.perf_counter() - tool_start) * 1000.0, 2),
                        },
                    )
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "last_file_search",
                        json.dumps(results, ensure_ascii=False),
                    )
                    if results:
                        cols, rows_data = records_to_columns_rows(results)
                        table, shown = render_rows(cols, rows_data, max_rows=max_show)
                        console.print(Panel(table, title=f"파일 목록 (표시 {shown} / 전체 {len(results)})"))
                    else:
                        console.print(Panel.fit("조건에 맞는 파일을 찾지 못했습니다."))
                    summary_text = build_summary_text(
                        intent,
                        {"count": len(results), "root": root, "pattern": pattern},
                        "",
                    )
                    _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                    save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", f"파일 탐색 완료: {len(results)}개")
                    _record_step_trace(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        step_trace,
                        {
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": tool,
                            "intent": intent,
                            "args": _mask_sql_arg(args),
                            "result_summary": {"count": len(results), "root": root, "pattern": pattern},
                            "error": "",
                        },
                        run_id,
                    )
                    _validate_step_and_record(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        {
                            "original_request": original_request,
                            "current_request": current_request,
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": tool,
                            "intent": intent,
                            "args": _mask_sql_arg(args),
                            "result_summary": {"count": len(results), "root": root, "pattern": pattern},
                            "error": "",
                        },
                    )
                    _refresh_summary_after_step(
                        mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                    )
                    if _is_restore_list_request(request_for_context) or _is_restore_list_request(
                        original_request
                    ):
                        return
                    if _is_list_only_request(original_request):
                        return
                    if pending_steps:
                        pending_steps, pending_step_index = _advance_pending_steps(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            pending_steps,
                            pending_step_index,
                        )
                    current_request = "continue"
                    continue
    
                if tool == "convo_search":
                    query = str(args.get("query", "")).strip()
                    limit = int(args.get("limit", 50)) if str(args.get("limit", "")).strip() else 50
                    include_current = bool(args.get("include_current", False))
                    tool_start = time.perf_counter()
                    results = convo_search(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        query=query,
                        limit=limit,
                        include_current=include_current,
                    )
                    log_timing(
                        "local_tool",
                        {
                            "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                            "step_index": step_index + 1,
                            "tool": tool,
                            "ms": round((time.perf_counter() - tool_start) * 1000.0, 2),
                        },
                    )
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "last_convo_search",
                        json.dumps(results, ensure_ascii=False),
                    )
                    if results:
                        cols, rows_data = records_to_columns_rows(results)
                        table, shown = render_rows(cols, rows_data, max_rows=max_show)
                        console.print(Panel(table, title=f"대화 검색 결과 (표시 {shown} / 전체 {len(results)})"))
                    else:
                        console.print(Panel.fit("조건에 맞는 대화 기록을 찾지 못했습니다."))
                    summary_text = build_summary_text(
                        intent,
                        {"count": len(results), "query": query},
                        "",
                    )
                    _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                    save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", f"대화 검색 완료: {len(results)}개")
                    _record_step_trace(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        step_trace,
                        {
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": tool,
                            "intent": intent,
                            "args": _mask_sql_arg(args),
                            "result_summary": {"count": len(results), "query": query},
                            "error": "",
                        },
                        run_id,
                    )
                    _validate_step_and_record(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        {
                            "original_request": original_request,
                            "current_request": current_request,
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": tool,
                            "intent": intent,
                            "args": _mask_sql_arg(args),
                            "result_summary": {"count": len(results), "query": query},
                            "error": "",
                        },
                    )
                    _refresh_summary_after_step(
                        mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                    )
                    if pending_steps:
                        pending_steps, pending_step_index = _advance_pending_steps(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            pending_steps,
                            pending_step_index,
                        )
                    current_request = "continue"
                    continue
    
                if tool == "file_read":
                    file_path = str(args.get("file_path", "")).strip()
                    max_bytes = args.get("max_bytes", 65536)
                    try:
                        max_bytes = int(max_bytes)
                    except Exception:
                        max_bytes = 65536
    
                    if not file_path:
                        last_search_raw = kv.get("last_file_search")
                        if last_search_raw:
                            try:
                                matches = json.loads(last_search_raw)
                            except Exception:
                                matches = []
                            if isinstance(matches, list):
                                if len(matches) == 1:
                                    file_path = str(matches[0].get("path", "")).strip()
                                elif len(matches) > 1:
                                    target_name = _extract_sql_filename(original_request) or _extract_sql_filename(current_request)
                                    if target_name:
                                        for item in matches:
                                            candidate = str(item.get("path", "")).strip()
                                            if candidate and os.path.basename(candidate) == target_name:
                                                file_path = candidate
                                                break
                                    if not file_path:
                                        guard = _format_user_answer_text(
                                            "파일이 지정되지 않아 실행을 중단했습니다. "
                                            "복원/분석은 `.sql` 또는 `.dump` 파일만 지원합니다."
                                        )
                                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", guard)
                                        summary_text = build_summary_text(intent, None, guard)
                                        _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                                        save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", guard)
                                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", guard)
                                        _refresh_summary_after_step(
                                            mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                                        )
                                        return
                    if not file_path:
                        guard = _format_user_answer_text(
                            "파일이 지정되지 않아 실행을 중단했습니다. "
                            "복원/분석할 `.sql` 또는 `.dump` 파일을 먼저 선택하세요."
                        )
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", guard)
                        summary_text = build_summary_text(intent, None, guard)
                        _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                        save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", guard)
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", guard)
                        _refresh_summary_after_step(
                            mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                        )
                        return
    
                    resolved_path = ""
                    if file_path:
                        resolved_path = _resolve_shared_path(file_path) or ""
                        if resolved_path and not os.path.exists(resolved_path):
                            last_search_raw = kv.get("last_file_search")
                            if last_search_raw:
                                try:
                                    matches = json.loads(last_search_raw)
                                except Exception:
                                    matches = []
                                if isinstance(matches, list) and matches:
                                    target_name = os.path.basename(file_path)
                                    for item in matches:
                                        candidate = str(item.get("path", "")).strip()
                                        if candidate and os.path.basename(candidate) == target_name:
                                            file_path = candidate
                                            resolved_path = candidate
                                            break
    
                    reuse_cached = False
                    cached_result: dict[str, Any] | None = None
                    if resolved_path and resolved_path in seen_file_reads:
                        cached_result = _load_cached_file_read(kv, resolved_path)
                        if cached_result:
                            result = cached_result
                            reuse_cached = True
    
                    if not reuse_cached:
                        try:
                            tool_start = time.perf_counter()
                            result = file_read(file_path=file_path, max_bytes=max_bytes)
                            log_timing(
                                "local_tool",
                                {
                                    "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                                    "step_index": step_index + 1,
                                    "tool": tool,
                                    "ms": round((time.perf_counter() - tool_start) * 1000.0, 2),
                                },
                            )
                        except Exception as exc:
                            err_msg = str(exc)
                            friendly = _friendly_error_message(err_msg)
                            if friendly:
                                err_msg = f"{friendly}\n원문: {err_msg}"
                            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", err_msg)
                            summary_text = build_summary_text(intent, None, err_msg)
                            _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                            _record_step_trace(
                                mem_conn,
                                cfg.MEMORY_CONVERSATION_ID,
                                step_trace,
                                {
                                    "step_index": step_index + 1,
                                    "action": "step",
                                    "tool": tool,
                                    "intent": intent,
                                    "args": _mask_sql_arg(args),
                                    "result_summary": None,
                                    "error": err_msg,
                                },
                                run_id,
                            )
                            _validate_step_and_record(
                                mem_conn,
                                cfg.MEMORY_CONVERSATION_ID,
                                {
                                    "original_request": original_request,
                                    "current_request": current_request,
                                    "step_index": step_index + 1,
                                    "action": "step",
                                    "tool": tool,
                                    "intent": intent,
                                    "args": _mask_sql_arg(args),
                                    "result_summary": None,
                                    "error": err_msg,
                                },
                            )
                            if (
                                "파일이 지정되지 않아 실행을 중단했습니다" in err_msg
                                or "파일이 존재하지 않습니다" in err_msg
                                or "허용되지 않는 파일 경로" in err_msg
                                or "읽을 수 없는 파일 유형" in err_msg
                                or "직접 복원 불가 파일 형식" in err_msg
                                or "직접 복원 가능한 파일은" in err_msg
                            ):
                                guide = (
                                    _shorten_error_for_user(err_msg)
                                    or "파일 읽기를 중단했습니다. `.sql` 또는 `.dump` 파일을 선택하세요."
                                )
                                guide = _format_user_answer_text(guide)
                                console.print(Panel.fit(guide, title="실행 가드"))
                                save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", guide)
                                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", guide)
                                _refresh_summary_after_step(
                                    mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                                )
                                return
                            raise
        
                    content = str(result.get("content", ""))
                    if resolved_path:
                        seen_file_reads.add(resolved_path)
                    preview = content
                    title = "파일 내용"
                    max_lines = max(1, AGENT_MAX_SHOW)
                    if preview:
                        lines = preview.splitlines()
                        if len(lines) > max_lines:
                            preview = "\n".join(lines[:max_lines]) + "\n...(생략)..."
                            title = f"파일 내용 (상위 {max_lines}줄)"
                            if result.get("truncated"):
                                title = f"파일 내용 (앞부분, 상위 {max_lines}줄)"
                    if len(preview) > 4000:
                        preview = preview[:4000] + "\n...(생략)..."
                    if result.get("truncated") and "상위" not in title:
                        title = "파일 내용 (앞부분)"
                    if not reuse_cached or AGENT_SHOW_INTERNAL:
                        console.print(Panel(preview or "(빈 파일)", title=title))
        
                    max_kv_chars = 20000
                    content_for_kv = content
                    if len(content_for_kv) > max_kv_chars:
                        content_for_kv = content_for_kv[:max_kv_chars] + "\n...(생략)..."
                    kv_payload = dict(result)
                    kv_payload["content"] = content_for_kv
        
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "last_file_read",
                        json.dumps(kv_payload, ensure_ascii=False),
                    )
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "last_file_read_path",
                        str(result.get("path", "")),
                    )
                    summary_text = build_summary_text(
                        intent,
                        {
                            "path": str(result.get("path", "")),
                            "read_bytes": result.get("read_bytes"),
                            "truncated": bool(result.get("truncated")),
                        },
                        "",
                    )
                    _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                    save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", "파일 읽기 완료")
                    _record_step_trace(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        step_trace,
                        {
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": tool,
                            "intent": intent,
                            "args": _mask_sql_arg(args),
                            "result_summary": {
                                "path": str(result.get("path", "")),
                                "read_bytes": result.get("read_bytes"),
                                "truncated": bool(result.get("truncated")),
                            },
                            "error": "",
                        },
                        run_id,
                    )
                    _validate_step_and_record(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        {
                            "original_request": original_request,
                            "current_request": current_request,
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": tool,
                            "intent": intent,
                            "args": _mask_sql_arg(args),
                            "result_summary": {
                                "path": str(result.get("path", "")),
                                "read_bytes": result.get("read_bytes"),
                                "truncated": bool(result.get("truncated")),
                            },
                            "error": "",
                        },
                    )
                    _refresh_summary_after_step(
                        mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                    )
                    if pending_steps:
                        pending_steps, pending_step_index = _advance_pending_steps(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            pending_steps,
                            pending_step_index,
                        )
                    current_request = "continue"
                    continue

                if tool == "restore_sql":
                    file_path = str(args.get("file_path", "")).strip()
                    database = str(args.get("database", "")).strip()
                    overwrite = bool(args.get("overwrite", False))

                    # Try to resolve file path from last search if missing or not found.
                    if not file_path:
                        last_search_raw = kv.get("last_file_search")
                        if last_search_raw:
                            try:
                                matches = json.loads(last_search_raw)
                            except Exception:
                                matches = []
                            if isinstance(matches, list) and matches:
                                restore_candidates = [
                                    str(item.get("path", "")).strip()
                                    for item in matches
                                    if _is_restore_compatible_file(str(item.get("path", "")).strip())
                                ]
                                restore_candidates = [p for p in restore_candidates if p]
                                if len(restore_candidates) == 1:
                                    file_path = restore_candidates[0]
                                elif len(matches) == 1:
                                    file_path = str(matches[0].get("path", "")).strip()
                    if not file_path:
                        guard = (
                            "복원 파일이 특정되지 않아 실행을 중단했습니다. "
                            "`/shared`에서 `.sql` 또는 `.dump` 파일을 먼저 선택해 주세요."
                        )
                        guard = _format_user_answer_text(guard)
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", guard)
                        summary_text = build_summary_text(intent, None, guard)
                        _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                        save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", guard)
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", guard)
                        _refresh_summary_after_step(
                            mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                        )
                        return

                    if file_path and not os.path.exists(file_path):
                        last_search_raw = kv.get("last_file_search")
                        if last_search_raw:
                            try:
                                matches = json.loads(last_search_raw)
                            except Exception:
                                matches = []
                            if isinstance(matches, list) and matches:
                                target_name = os.path.basename(file_path)
                                for item in matches:
                                    candidate = str(item.get("path", "")).strip()
                                    if candidate and os.path.basename(candidate) == target_name:
                                        file_path = candidate
                                        break

                    try:
                        tool_start = time.perf_counter()
                        result = restore_sql_file(file_path=file_path, database=database, overwrite=overwrite)
                        log_timing(
                            "local_tool",
                            {
                                "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                                "step_index": step_index + 1,
                                "tool": tool,
                                "ms": round((time.perf_counter() - tool_start) * 1000.0, 2),
                            },
                        )
                    except Exception as exc:
                        err_msg = str(exc)
                        friendly = _friendly_error_message(err_msg)
                        if friendly:
                            err_msg = f"{friendly}\n원문: {err_msg}"
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", err_msg)
                        summary_text = build_summary_text(intent, None, err_msg)
                        _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                        _record_step_trace(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            step_trace,
                            {
                                "step_index": step_index + 1,
                                "action": "step",
                                "tool": tool,
                                "intent": intent,
                                "args": _mask_sql_arg(args),
                                "result_summary": None,
                                "error": err_msg,
                            },
                            run_id,
                        )
                        _validate_step_and_record(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            {
                                "original_request": original_request,
                                "current_request": current_request,
                                "step_index": step_index + 1,
                                "action": "step",
                                "tool": tool,
                                "intent": intent,
                                "args": _mask_sql_arg(args),
                                "result_summary": None,
                                "error": err_msg,
                            },
                        )
                        if "파일이 존재하지 않습니다" in err_msg:
                            guide = _format_user_answer_text(
                                "복원 파일 경로를 확인할 수 없어 실행을 중단했습니다. "
                                "`/shared` 하위의 `.sql` 또는 `.dump` 파일 경로를 지정하세요."
                            )
                            console.print(Panel.fit(guide, title="실행 가드"))
                            save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", guide)
                            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", guide)
                            _refresh_summary_after_step(
                                mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                            )
                            return
                        if (
                            "직접 복원 불가 파일 형식" in err_msg
                            or "직접 복원 가능한 파일은" in err_msg
                            or "복원 파일은 `/shared` 하위 경로만 허용됩니다." in err_msg
                            or "현재 파일은 복원 대상이 아닙니다." in err_msg
                        ):
                            guide = _format_user_answer_text(
                                _shorten_error_for_user(err_msg)
                                or "복원 가능한 SQL 덤프 파일을 선택해 주세요."
                            )
                            console.print(Panel.fit(guide, title="실행 가드"))
                            save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", guide)
                            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", guide)
                            _refresh_summary_after_step(
                                mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                            )
                            return
                        if "대상 데이터베이스 이름이 필요합니다" in err_msg or "대상 DB 지정이 필요합니다" in err_msg:
                            question = (
                                "복원할 대상 데이터베이스 이름을 알려주세요. "
                                "기존 DB 덮어쓰기 여부(overwrite: true/false)도 함께 알려주세요."
                            )
                            console.print(Panel.fit(question, title="확인 질문"))
                            save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", question)
                            _refresh_summary_after_step(
                                mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                            )
                            return
                        raise

                    console.print(Panel.fit(json.dumps(result, ensure_ascii=False), title="복원 결과"))
                    save_memory_kv(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "last_result_summary",
                        json.dumps(result, ensure_ascii=False),
                    )
                    summary_text = build_summary_text(intent, result, "")
                    _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                    summary_payload = result if isinstance(result, dict) else None
                    _record_insight_fact(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        intent,
                        summary_payload,
                        tool,
                        source_run_id=run_id,
                    )
                    user_answer = _build_user_facing_answer(intent, summary_payload, tool)
                    user_answer = _ensure_user_answer_quality(
                        intent,
                        summary_payload,
                        tool,
                        user_answer,
                    )
                    if user_answer:
                        save_memory_message(
                            mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", user_answer
                        )
                        save_memory_kv(
                            mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", user_answer
                        )
                    _record_step_trace(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        step_trace,
                        {
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": tool,
                            "intent": intent,
                            "args": _mask_sql_arg(args),
                            "result_summary": result,
                            "error": "",
                        },
                        run_id,
                    )
                    _validate_step_and_record(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        {
                            "original_request": original_request,
                            "current_request": current_request,
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": tool,
                            "intent": intent,
                            "args": _mask_sql_arg(args),
                            "result_summary": result,
                            "error": "",
                        },
                    )
                    _refresh_summary_after_step(
                        mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                    )
                    if pending_steps:
                        pending_steps, pending_step_index = _advance_pending_steps(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            pending_steps,
                            pending_step_index,
                        )
                    current_request = "continue"
                    continue

                raise RuntimeError(f"지원되지 않는 로컬 도구: {tool}")

            if AGENT_MODE == "mcp":
                tool = str(plan.get("tool", "")).strip()
                args = plan.get("args") if isinstance(plan.get("args"), dict) else {}
    
                if mcp_tools:
                    if tool not in mcp_tools:
                        mapped_tool = None
                        if tool in MCP_EXECUTE_SQL_CANDIDATES:
                            mapped_tool = _find_tool_name(mcp_tools, MCP_EXECUTE_SQL_CANDIDATES)
                        elif tool in MCP_SEARCH_OBJECTS_CANDIDATES:
                            mapped_tool = _find_tool_name(mcp_tools, MCP_SEARCH_OBJECTS_CANDIDATES)
                        if mapped_tool:
                            tool = mapped_tool
                        else:
                            available = ", ".join(mcp_tools)
                            console.print(f"[yellow]오류: 지원되지 않는 MCP 도구: {tool} (사용 가능: {available})[/yellow]")
                            err_msg = f"Unsupported MCP tool: {tool}. Available: {available}"
                            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", err_msg)
                            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "retry_hint", f"use only: {available}")
                            continue
    
                tool_spec = mcp_catalog.get(tool) if isinstance(mcp_catalog, dict) else None
                args = normalize_mcp_args(tool, args, tool_spec)
                preview_args = _mask_sql_arg(args)
                preview = (
                    f"의도={intent}\n쓰기작업={is_write}\n\n도구={tool}\n"
                    f"인자={json.dumps(preview_args, ensure_ascii=False)}"
                )
                if AGENT_SHOW_INTERNAL:
                    print_internal(Panel.fit(preview, title="MCP 단계"))
                mcp_log = log_text("mcp_step", preview)
                if AGENT_SHOW_INTERNAL:
                    print_internal(f"[dim]MCP 로그:[/dim] {mcp_log}")
    
                if no_exec:
                    save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", f"(실행 생략) {intent}")
                    return
    
                start = time.time()
                schema_hint = ""
                explicit_schema_in_request = _detect_requested_schema(
                    _effective_request(
                        current_request, original_request, kv.get("origin_request", "")
                    ),
                    known_schemas,
                ) or ""
                if tool in MCP_SEARCH_OBJECTS_CANDIDATES and explicit_schema_in_request:
                    args["schema"] = explicit_schema_in_request
                    schema_hint = explicit_schema_in_request
                if tool in MCP_SEARCH_OBJECTS_CANDIDATES and not args.get("schema"):
                    schema_hint = (
                        _infer_preferred_schema(
                            db_conn,
                            mem_conn,
                            _effective_request(
                                current_request, original_request, kv.get("origin_request", "")
                            ),
                            kv,
                            known_schemas,
                            cfg.MEMORY_CONVERSATION_ID,
                            scope_key=request_scope_key,
                        )
                        or ""
                    )
                    if schema_hint:
                        args["schema"] = schema_hint
                if tool in MCP_EXECUTE_SQL_CANDIDATES:
                    sql_text = str(args.get("sql", "")).strip()
                    schema_hint = _detect_requested_schema(
                        _effective_request(
                            current_request, original_request, kv.get("origin_request", "")
                        ),
                        known_schemas,
                    ) or schema_hint
                    if not schema_hint:
                        schema_hint = (
                            anchor_fast_schema
                            or str(kv.get("preferred_schema") or "").strip()
                        )
                    if schema_hint and schema_hint != schema_meta_schema:
                        sql_text = _rewrite_schema_in_sql(sql_text, schema_hint, known_schemas)
                        if not _sql_mentions_schema(sql_text, schema_hint):
                            sql_text = _prefix_use_schema(sql_text, schema_hint)
                    sql_text = _normalize_sql_identifier_backticks(sql_text)
                    args["sql"] = sql_text
                    if sql_text:
                        dedupe_key = _build_turn_dedupe_key(sql_text, intent, schema_hint or "")
                        repeat_count = _count_recent_sql_signature_repeats(
                            step_trace,
                            sql_text,
                            window=AGENT_SQL_SIGNATURE_WINDOW,
                            run_id=run_id,
                        )
                        if repeat_count >= max(1, AGENT_SQL_SIGNATURE_REPEAT_LIMIT):
                            try:
                                log_fact_quality(
                                    "sql_signature_alt_path",
                                    {
                                        "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                                        "repeat_count": repeat_count,
                                        "limit": max(1, AGENT_SQL_SIGNATURE_REPEAT_LIMIT),
                                        "schema": schema_hint or "",
                                        "intent": str(intent or "")[:120],
                                    },
                                )
                            except Exception:
                                pass
                            if auto_continue_budget > 0:
                                auto_continue_budget -= 1
                                _set_retry_hint(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    "동일 SQL 시그니처 반복 감지: 다른 후보 테이블/집계 경로로 전환",
                                )
                                current_request = _preserve_request_for_retry(
                                    request_for_context,
                                    original_request,
                                )
                                continue
                            _emit_forced_conclusion(mem_conn, original_request, kv, step_trace, step_index)
                            return
                        if dedupe_key in executed_step_keys:
                            if auto_continue_budget > 0:
                                auto_continue_budget -= 1
                                _set_retry_hint(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    "같은 SQL/의도/스키마 재실행 차단: 다른 필터/집계 또는 후보 테이블로 전환",
                                )
                                current_request = _preserve_request_for_retry(
                                    request_for_context,
                                    original_request,
                                )
                                continue
                            _emit_forced_conclusion(mem_conn, original_request, kv, step_trace, step_index)
                            return
                        executed_step_keys.add(dedupe_key)
                    if sql_text and _contains_local_infile(sql_text):
                        summary_data, csv_paths, _csv_preview, err_msg = _analyze_local_infile_sql(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            sql_text,
                            _effective_request(
                                current_request, original_request, kv.get("origin_request", "")
                            ),
                        )
                        if err_msg:
                            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", err_msg)
                            summary_text = build_summary_text(intent, None, err_msg)
                            _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                            _record_step_trace(
                                mem_conn,
                                cfg.MEMORY_CONVERSATION_ID,
                                step_trace,
                                {
                                    "step_index": step_index + 1,
                                    "action": "step",
                                    "tool": "csv_analysis",
                                    "intent": intent,
                                    "args": {"sql": "<hidden>"},
                                    "sql": _compact_sql_for_memory(sql_text),
                                    "result_summary": None,
                                    "error": err_msg,
                                },
                                run_id,
                            )
                            if not _should_skip_aux_updates("csv_analysis", None, err_msg):
                                _validate_step_and_record(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    {
                                        "original_request": original_request,
                                        "current_request": current_request,
                                        "step_index": step_index + 1,
                                        "action": "step",
                                        "tool": "csv_analysis",
                                        "intent": intent,
                                        "args": {"sql": "<hidden>"},
                                        "result_summary": None,
                                        "error": err_msg,
                                    },
                                )
                            user_error = _build_user_facing_error(intent, err_msg)
                            if user_error:
                                save_memory_message(
                                    mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", user_error
                                )
                                save_memory_kv(
                                    mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", user_error
                                )
                            if not _should_skip_aux_updates("csv_analysis", None, err_msg):
                                _refresh_summary_after_step(
                                    mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                                )
                            return
                        log_executed_sql("csv", intent, sql_text, "csv_analysis", False, attempt=1)
                        summary_dict = summary_data if isinstance(summary_data, dict) else None
                        summary_payload = summary_dict if summary_dict else None
                        _record_insight_fact(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            intent,
                            summary_payload,
                            "csv_analysis",
                            source_run_id=run_id,
                            source_sql=sql_text,
                        )
                        _update_zero_result_flags(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            summary_dict,
                            sql_text,
                            intent,
                            run_id,
                        )
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", "")
                        _clear_error_signature(mem_conn, cfg.MEMORY_CONVERSATION_ID)
                        save_memory_kv(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            "last_result_summary",
                            json.dumps(summary_data or {}, ensure_ascii=False),
                        )
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_result_tool", "csv_analysis")
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_result_intent", intent)
                        summary_text = build_summary_text(intent, summary_data or {}, "")
                        _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                        meta: dict[str, Any] = {"sql": sql_text}
                        if csv_paths:
                            meta["csv_paths"] = csv_paths
                        user_answer = ""
                        if summary_data and isinstance(summary_data, dict):
                            user_answer = _format_user_answer_text(summary_data.get("summary") or "")
                        if not user_answer:
                            user_answer = _build_user_facing_answer(intent, summary_payload, "csv_analysis")
                        user_answer = _ensure_user_answer_quality(
                            intent,
                            summary_payload,
                            "csv_analysis",
                            user_answer,
                        )
                        if user_answer:
                            save_memory_message(
                                mem_conn,
                                cfg.MEMORY_CONVERSATION_ID,
                                "assistant",
                                user_answer,
                                meta,
                            )
                            save_memory_kv(
                                mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", user_answer
                            )
                        _record_step_trace(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            step_trace,
                            {
                                "step_index": step_index + 1,
                                "action": "step",
                                "tool": "csv_analysis",
                                "intent": intent,
                                "args": {"sql": "<hidden>"},
                                "sql": _compact_sql_for_memory(sql_text),
                                "result_summary": summary_data,
                                "error": "",
                            },
                            run_id,
                        )
                        if not _should_skip_aux_updates("csv_analysis", summary_dict, ""):
                            _validate_step_and_record(
                                mem_conn,
                                cfg.MEMORY_CONVERSATION_ID,
                                {
                                    "original_request": original_request,
                                    "current_request": current_request,
                                    "step_index": step_index + 1,
                                    "action": "step",
                                    "tool": "csv_analysis",
                                    "intent": intent,
                                    "args": {"sql": "<hidden>"},
                                    "result_summary": summary_data,
                                    "error": "",
                                },
                            )
                            _refresh_summary_after_step(
                                mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                            )
                        if _is_direct_sql_request(original_request):
                            return
                        if _is_list_only_request(original_request):
                            return
                        if pending_steps:
                            pending_steps, pending_step_index = _advance_pending_steps(
                                mem_conn,
                                cfg.MEMORY_CONVERSATION_ID,
                                pending_steps,
                                pending_step_index,
                            )
                        current_request = "continue"
                        continue
                    if sql_text:
                        log_executed_sql("mcp", intent, sql_text, tool, is_write, attempt=1)
                retry_args = None
                schema_list = _coerce_schema_list(args.get("schema")) if tool in MCP_SEARCH_OBJECTS_CANDIDATES else []
                search_cache_schema = ""
                search_cache_pattern = ""
                search_cache_hit = False
                did_fallback = False
                if tool in MCP_SEARCH_OBJECTS_CANDIDATES:
                    search_cache_schema = str(args.get("schema") or "").strip()
                    search_cache_pattern = str(args.get("pattern") or "").strip()
                if schema_list:
                    results = []
                    for schema in schema_list:
                        new_args = dict(args)
                        new_args["schema"] = schema
                        res = mcp_call(tool, new_args)
                        res, _ = _mcp_auto_retry(tool, new_args, res)
                        results.append(res)
                    result = {"results": results}
                elif tool in MCP_SEARCH_OBJECTS_CANDIDATES:
                    cached = _load_search_cache(kv, search_cache_schema, search_cache_pattern)
                    if cached is not None:
                        result = cached
                        search_cache_hit = True
                    else:
                        result = mcp_call(tool, args)
                        result, retry_args = _mcp_auto_retry(tool, args, result)
                else:
                    result = mcp_call(tool, args)
                    result, retry_args = _mcp_auto_retry(tool, args, result)
                if retry_args and tool in MCP_EXECUTE_SQL_CANDIDATES:
                    sql_text = _normalize_sql_identifier_backticks(str(retry_args.get("sql", "")).strip())
                    retry_args["sql"] = sql_text
                    if sql_text:
                        log_executed_sql("mcp", intent, sql_text, tool, is_write, attempt=2)
                elapsed = time.time() - start
                log_timing(
                    "mcp_tool",
                    {
                        "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                        "step_index": step_index + 1,
                        "tool": tool,
                        "ms": round(elapsed * 1000.0, 2),
                    },
                )
                _timing_breakdown_add(timing_breakdown, "mcp_ms", elapsed * 1000.0)
                if AGENT_SHOW_INTERNAL:
                    print_internal(f"[dim]실행 시간:[/dim] {elapsed:.3f}s")
                sql_hint = ""
                sql_full = ""
                if tool in MCP_EXECUTE_SQL_CANDIDATES:
                    sql_source = retry_args if retry_args else args
                    sql_full = str(sql_source.get("sql", "")).strip()
                    sql_hint = _compact_sql_for_memory(sql_full)
    
                raw_err_msg, err_code = _mcp_error_info(result)
                err_msg = raw_err_msg
                err_title, _err_hint = _classify_error_message(raw_err_msg, err_code)
                not_found_error = _is_not_found_error_type(err_title)
                repeated_not_found_path = False
                if not_found_error and sql_full:
                    sig = _build_error_signature(tool, err_title, sql_full, raw_err_msg or "")
                    repeated_not_found_path = _mark_error_signature(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        kv,
                        sig,
                    )
                if err_msg:
                    friendly = _friendly_error_message(err_msg, err_code)
                    if friendly:
                        err_msg = f"{friendly}\n원문: {err_msg}"
                if err_msg and tool in MCP_EXECUTE_SQL_CANDIDATES and sql_full:
                    missing_col = _extract_unknown_column(raw_err_msg or err_msg)
                    if missing_col:
                        fixed_sql = _safe_fix_missing_column_sql(sql_full, missing_col)
                        if fixed_sql and fixed_sql.strip() and fixed_sql.strip() != sql_full:
                            fixed_sql = _normalize_sql_identifier_backticks(fixed_sql)
                            log_executed_sql("mcp", intent, fixed_sql, tool, is_write, attempt=2)
                            retry_args = {"sql": fixed_sql}
                            retry_start = time.perf_counter()
                            result = mcp_call(tool, retry_args)
                            result, retry_args = _mcp_auto_retry(tool, retry_args, result)
                            retry_ms = (time.perf_counter() - retry_start) * 1000.0
                            _timing_breakdown_add(timing_breakdown, "mcp_ms", retry_ms)
                            _timing_breakdown_add(timing_breakdown, "retry_ms", retry_ms)
                            retry_err_msg, retry_err_code = _mcp_error_info(result)
                            if not retry_err_msg:
                                sql_full = fixed_sql
                                sql_hint = _compact_sql_for_memory(sql_full)
                                raw_err_msg = ""
                                err_msg = ""
                                err_code = None
                            else:
                                raw_err_msg = retry_err_msg
                                err_code = retry_err_code
                                friendly = _friendly_error_message(retry_err_msg, retry_err_code)
                                err_msg = (
                                    f"{friendly}\n원문: {retry_err_msg}"
                                    if friendly
                                    else retry_err_msg
                                )
                    if (
                        err_msg
                        and AGENT_AUTO_FIX_SQL
                        and not AGENT_DISABLE_AUTO_RETRY
                        and (
                            _is_sql_syntax_error(raw_err_msg or err_msg, err_code)
                            or not_found_error
                        )
                    ):
                        fix_payload = {
                            "sql": sql_full,
                            "error": raw_err_msg or err_msg,
                            "db_name": DB_NAME_EFFECTIVE,
                            "request": request_for_context,
                            "columns_hint": _extract_columns_hint(knowledge_payload),
                        }
                        fixed_sql = llm_fix_sql(fix_payload)
                        if fixed_sql and fixed_sql.strip() and fixed_sql.strip() != sql_full:
                            fixed_sql = _normalize_sql_identifier_backticks(fixed_sql)
                            log_executed_sql("mcp", intent, fixed_sql, tool, is_write, attempt=2)
                            retry_args = {"sql": fixed_sql}
                            retry_start = time.perf_counter()
                            result = mcp_call(tool, retry_args)
                            result, retry_args = _mcp_auto_retry(tool, retry_args, result)
                            retry_ms = (time.perf_counter() - retry_start) * 1000.0
                            _timing_breakdown_add(timing_breakdown, "mcp_ms", retry_ms)
                            _timing_breakdown_add(timing_breakdown, "retry_ms", retry_ms)
                            retry_err_msg, retry_err_code = _mcp_error_info(result)
                            if not retry_err_msg:
                                sql_full = fixed_sql
                                sql_hint = _compact_sql_for_memory(sql_full)
                                raw_err_msg = ""
                                err_msg = ""
                                err_code = None
                            else:
                                raw_err_msg = retry_err_msg
                                err_code = retry_err_code
                                friendly = _friendly_error_message(retry_err_msg, retry_err_code)
                                err_msg = (
                                    f"{friendly}\n원문: {retry_err_msg}"
                                    if friendly
                                    else retry_err_msg
                                )
                    if (
                        err_msg
                        and AGENT_ERROR_AUTO_RECOVERY
                        and not is_write
                    ):
                        recovered = _auto_recover_not_found_sql(
                            db_conn,
                            sql_full,
                            raw_err_msg or err_msg,
                            err_code,
                            request_for_context,
                            kv,
                            known_schemas,
                        )
                        if recovered:
                            recovered_sql, validation_sql, recovery_reason = recovered
                            probe_ok = _validate_sql_probe(db_conn, validation_sql)
                            if not probe_ok and validation_sql and db_conn is None:
                                probe_args = {"sql": validation_sql}
                                retry_start = time.perf_counter()
                                probe_result = mcp_call(tool, probe_args)
                                probe_result, _ = _mcp_auto_retry(tool, probe_args, probe_result)
                                retry_ms = (time.perf_counter() - retry_start) * 1000.0
                                _timing_breakdown_add(timing_breakdown, "mcp_ms", retry_ms)
                                _timing_breakdown_add(timing_breakdown, "retry_ms", retry_ms)
                                probe_err, _ = _mcp_error_info(probe_result)
                                probe_ok = not probe_err
                            if (
                                probe_ok
                                and recovered_sql
                                and recovered_sql.strip()
                                and recovered_sql.strip() != sql_full.strip()
                            ):
                                recovered_sql = _normalize_sql_identifier_backticks(recovered_sql)
                                log_executed_sql("mcp", intent, recovered_sql, tool, is_write, attempt=3)
                                retry_args = {"sql": recovered_sql}
                                retry_start = time.perf_counter()
                                result = mcp_call(tool, retry_args)
                                result, retry_args = _mcp_auto_retry(tool, retry_args, result)
                                retry_ms = (time.perf_counter() - retry_start) * 1000.0
                                _timing_breakdown_add(timing_breakdown, "mcp_ms", retry_ms)
                                _timing_breakdown_add(timing_breakdown, "retry_ms", retry_ms)
                                retry_err_msg, retry_err_code = _mcp_error_info(result)
                                if not retry_err_msg:
                                    sql_full = recovered_sql
                                    sql_hint = _compact_sql_for_memory(sql_full)
                                    raw_err_msg = ""
                                    err_msg = ""
                                    err_code = None
                                    try:
                                        save_memory_kv(
                                            mem_conn,
                                            cfg.MEMORY_CONVERSATION_ID,
                                            "last_auto_recovery",
                                            json.dumps(
                                                {
                                                    "tool": tool,
                                                    "reason": recovery_reason,
                                                    "validation_sql": validation_sql,
                                                    "recovered_sql": _compact_sql_for_memory(recovered_sql),
                                                },
                                                ensure_ascii=False,
                                            ),
                                        )
                                    except Exception:
                                        pass
                                else:
                                    raw_err_msg = retry_err_msg
                                    err_code = retry_err_code
                                    friendly = _friendly_error_message(retry_err_msg, retry_err_code)
                                    err_msg = (
                                        f"{friendly}\n원문: {retry_err_msg}"
                                        if friendly
                                        else retry_err_msg
                                    )
                if err_msg:
                    auto_retry = (
                        (not is_write)
                        and auto_continue_budget > 0
                        and _should_auto_continue_on_error(err_msg)
                    )
                    source_request = request_for_context or original_request
                    source_sql = ""
                    if looks_like_sql(source_request):
                        source_sql = source_request
                    elif looks_like_sql(original_request):
                        source_sql = original_request
                    if not_found_error and (auto_continue_budget > 0 or not_found_recovery_budget > 0):
                        auto_retry = True
                    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", err_msg)
                    summary_text = build_summary_text(intent, None, err_msg)
                    _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                    _record_step_trace(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        step_trace,
                        {
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": tool,
                            "intent": intent,
                            "args": _mask_sql_arg(args),
                            "sql": sql_hint,
                            "result_summary": None,
                            "error": err_msg,
                        },
                        run_id,
                    )
                    if not _should_skip_aux_updates(tool, None, err_msg):
                        _validate_step_and_record(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            {
                                "original_request": original_request,
                                "current_request": current_request,
                                "step_index": step_index + 1,
                                "action": "step",
                                "tool": tool,
                                "intent": intent,
                                "args": _mask_sql_arg(args),
                                "result_summary": None,
                                "error": err_msg,
                            },
                        )
                    if auto_retry:
                        if not_found_error:
                            if auto_continue_budget > 0:
                                auto_continue_budget -= 1
                            elif not_found_recovery_budget > 0:
                                not_found_recovery_budget -= 1
                            else:
                                auto_retry = False
                            if auto_retry:
                                _clear_last_resolved_object_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID)
                                mode_hint = (
                                    "동일 not-found 경로 반복 차단: 후보를 변경해 재시도"
                                    if repeated_not_found_path
                                    else "not-found 자동복구: 후보 탐색 1회 + 집계 1회 우선 실행"
                                )
                                _set_retry_hint(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    mode_hint,
                                )
                                current_request = _preserve_request_for_retry(
                                    source_request,
                                    original_request,
                                )
                        else:
                            auto_continue_budget -= 1
                            compact_err = _shorten_error_for_user(err_msg) or err_msg
                            if source_sql:
                                _set_retry_hint(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    f"직전 SQL 오류 우회 재시도: {compact_err}",
                                )
                            else:
                                _set_retry_hint(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    f"직전 단계 오류 우회 재시도: {compact_err}",
                                )
                            current_request = _preserve_request_for_retry(
                                source_request,
                                original_request,
                            )
                        if auto_retry:
                            continue
                    if not_found_error:
                        _clear_last_resolved_object_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID)
                        forced = _build_forced_conclusion(original_request, kv, step_trace)
                        console.print(Panel.fit(forced, title="강제 결론"))
                        save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", forced)
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", forced)
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_forced_conclusion", forced)
                        _refresh_summary_after_step(
                            mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                        )
                        return
                    if isinstance(result, (dict, list)):
                        pretty = json.dumps(result, ensure_ascii=False, indent=2)
                    else:
                        pretty = str(result)
                    console.print(Panel.fit(pretty, title="MCP 오류"))
                    user_error = _build_user_facing_error(intent, err_msg)
                    if user_error:
                        save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", user_error)
                        save_memory_kv(
                            mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", user_error
                        )
                    if not _should_skip_aux_updates(tool, None, err_msg):
                        _refresh_summary_after_step(
                            mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                        )
                    return
    
                result_sets = _mcp_result_to_result_sets(result)
                if tool in MCP_SEARCH_OBJECTS_CANDIDATES:
                    has_rows = any((rs[0] == "rows" and rs[2]) for rs in result_sets)
                    pattern = str(args.get("pattern", "")).strip()
                    if not has_rows and pattern and pattern != "%":
                        did_fallback = True
                        fallback_args = dict(args)
                        fallback_args["pattern"] = "%"
                        retry_start = time.perf_counter()
                        fallback = mcp_call(tool, fallback_args)
                        retry_ms = (time.perf_counter() - retry_start) * 1000.0
                        _timing_breakdown_add(timing_breakdown, "mcp_ms", retry_ms)
                        _timing_breakdown_add(timing_breakdown, "retry_ms", retry_ms)
                        err_msg, _ = _mcp_error_info(fallback)
                        if not err_msg:
                            result = fallback
                            result_sets = _mcp_result_to_result_sets(result)
                if tool in MCP_SEARCH_OBJECTS_CANDIDATES and result_sets:
                    augmented_sets, meta_ms = _augment_search_objects_with_table_meta(
                        result_sets,
                        args,
                        mcp_tools,
                    )
                    result_sets = augmented_sets
                    if meta_ms > 0:
                        _timing_breakdown_add(timing_breakdown, "mcp_ms", meta_ms)
                if (
                    tool in MCP_SEARCH_OBJECTS_CANDIDATES
                    and not schema_list
                    and not search_cache_hit
                    and not did_fallback
                    and not err_msg
                ):
                    _save_search_cache(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        search_cache_schema,
                        search_cache_pattern,
                        result,
                    )
                if tool in MCP_SEARCH_OBJECTS_CANDIDATES:
                    compact = _compact_search_objects_result(result_sets)
                    if compact:
                        save_memory_kv(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            "last_search_objects",
                            json.dumps(compact, ensure_ascii=False),
                        )
                        _record_schema_prefs_from_search(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            compact,
                            pattern=pattern,
                            source_run_id=run_id,
                        )
                if tool in MCP_SEARCH_OBJECTS_CANDIDATES and not compact:
                    last_compact_raw = kv.get("last_search_objects")
                    if last_compact_raw:
                        try:
                            compact = json.loads(last_compact_raw)
                        except Exception:
                            compact = []
                csv_paths: list[str] = []
                for idx, rs in enumerate(result_sets, start=1):
                    if rs[0] == "rows":
                        _, cols, rows_data = rs
                        table, shown = render_rows(cols, rows_data, max_rows=max_show)
                        console.print(
                            Panel(table, title=f"결과 #{idx} (표시 {shown} / 전체 {len(rows_data)})")
                        )
                        csv_path = save_csv(f"mcp_resultset{idx}", cols, rows_data)
                        if AGENT_SHOW_INTERNAL:
                            print_internal(f"[green]CSV 저장:[/green] {csv_path}")
                        csv_paths.append(csv_path)
    
                        csv_preview = read_csv_preview(csv_path, AGENT_CSV_PREVIEW_ROWS)
                        if csv_preview:
                            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_csv_path", csv_path)
                            save_memory_kv(
                                mem_conn,
                                cfg.MEMORY_CONVERSATION_ID,
                                "last_csv_preview",
                                json.dumps(csv_preview, ensure_ascii=False),
                            )
                    else:
                        _, rowcount, _ = rs
                        console.print(Panel.fit(f"결과 #{idx}: ROWCOUNT={rowcount}"))
    
                if not result_sets:
                    if isinstance(result, (dict, list)):
                        pretty = json.dumps(result, ensure_ascii=False, indent=2)
                    else:
                        pretty = str(result)
                    console.print(Panel.fit(pretty, title="MCP 결과"))
    
                summary_data = summarize_result_sets(result_sets) if result_sets else summarize_mcp_result(result)
                if csv_paths:
                    if isinstance(summary_data, dict):
                        summary_data["csv_paths"] = csv_paths
                    else:
                        summary_data = {"summary": summary_data, "csv_paths": csv_paths}
                summary_dict = summary_data if isinstance(summary_data, dict) else None
                summary_payload = summary_dict if summary_dict else None
                _maybe_record_schema_usage(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    sql_full,
                    summary_dict,
                    request_text=request_for_context,
                    kv=kv,
                    fallback_schema=schema_hint or str(args.get("schema", "")).strip(),
                    source_run_id=run_id,
                )
                _maybe_record_summary_facts(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    sql_full,
                    summary_dict,
                    intent,
                    source_run_id=run_id,
                )
                if summary_dict and sql_full:
                    schema_name, table_name = _extract_first_table_from_sql(sql_full)
                    _record_table_usage_insight(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        schema_name or "",
                        table_name or "",
                        summary_dict.get("col_names"),
                        source_run_id=run_id,
                        fallback_schema=schema_hint or str(args.get("schema", "")).strip(),
                    )
                if tool in MCP_EXECUTE_SQL_CANDIDATES or tool == "restore_sql":
                    _record_insight_fact(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        intent,
                        summary_payload,
                        tool,
                        source_run_id=run_id,
                        source_sql=sql_full,
                    )
                _update_zero_result_flags(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    summary_dict,
                    sql_full,
                    intent,
                    run_id,
                )
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", "")
                _clear_error_signature(mem_conn, cfg.MEMORY_CONVERSATION_ID)
                save_memory_kv(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    "last_result_summary",
                    json.dumps(summary_data, ensure_ascii=False),
                )
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_result_tool", "mcp_execute_sql")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_result_intent", intent)
                # ── follow-up 문맥 보존: 성공한 SQL에서 사용된 테이블을 last_resolved_object로 저장 ──
                _resolved_ref = _extract_primary_table_ref_from_sql(sql_full)
                if _resolved_ref:
                    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_resolved_object", _resolved_ref)
                    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_resolved_object_at", utc_now_iso())
                summary_text = build_summary_text(intent, summary_data, "")
                _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                meta: dict[str, Any] = {}
                if sql_full:
                    meta["sql"] = sql_full
                if csv_paths:
                    meta["csv_paths"] = csv_paths
                schema_usage_answer = ""
                if tool in MCP_SEARCH_OBJECTS_CANDIDATES:
                    schema_usage_answer = _build_schema_usage_answer_from_compact(
                        request_for_context,
                        str(args.get("schema") or "").strip(),
                        compact if isinstance(compact, list) else [],
                    )
                user_answer = schema_usage_answer or _build_user_facing_answer(intent, summary_payload, tool)
                user_answer = _ensure_user_answer_quality(
                    intent,
                    summary_payload,
                    tool,
                    user_answer,
                )
                schema_usage_answer_used = bool(schema_usage_answer)
                if user_answer:
                    if schema_usage_answer_used:
                        console.print(Panel.fit(user_answer, title="결론"))
                    save_memory_message(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "assistant",
                        user_answer,
                        meta if meta else None,
                    )
                    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", user_answer)
                _record_step_trace(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    step_trace,
                    {
                        "step_index": step_index + 1,
                        "action": "step",
                        "tool": tool,
                        "intent": intent,
                        "args": _mask_sql_arg(args),
                        "sql": sql_hint,
                        "result_summary": summary_data,
                        "error": "",
                    },
                    run_id,
                )
                if not _should_skip_aux_updates(tool, summary_dict, ""):
                    _validate_step_and_record(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        {
                            "original_request": original_request,
                            "current_request": current_request,
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": tool,
                            "intent": intent,
                            "args": _mask_sql_arg(args),
                            "result_summary": summary_data,
                            "error": "",
                        },
                    )
                    _refresh_summary_after_step(
                        mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                    )
                if _is_list_only_request(original_request):
                    return
                if (
                    tool in MCP_SEARCH_OBJECTS_CANDIDATES
                    and AGENT_AUTO_ENRICH
                    and compact
                    and not stepwise_active
                    and not _is_list_only_request(original_request)
                ):
                    execute_tool = _find_tool_name(mcp_tools or [], MCP_EXECUTE_SQL_CANDIDATES)
                    if execute_tool:
                        pattern = str(args.get("pattern", "")).strip()
                        candidates = _pick_table_candidates(
                            compact,
                            pattern,
                            max(1, AGENT_AUTO_ENRICH_MAX_TABLES),
                        )
                        def _run_auto_sql(
                            auto_intent: str,
                            sql_text: str,
                            csv_tag: str,
                            enrich_key: str = "",
                            mask_pii: bool = False,
                        ) -> None:
                                log_executed_sql("mcp", auto_intent, sql_text, execute_tool, False, attempt=1)
                                auto_args = {"sql": sql_text}
                                auto_preview = (
                                    f"의도={auto_intent}\n쓰기작업=False\n\n도구={execute_tool}\n"
                                    f"인자={json.dumps(_mask_sql_arg(auto_args), ensure_ascii=False)}"
                                )
                                if AGENT_SHOW_INTERNAL:
                                    print_internal(Panel.fit(auto_preview, title="자동 탐색 단계"))
                                auto_log = log_text("mcp_step", auto_preview)
                                if AGENT_SHOW_INTERNAL:
                                    print_internal(f"[dim]MCP 로그:[/dim] {auto_log}")
                                auto_start = time.time()
                                auto_result = mcp_call(execute_tool, auto_args)
                                auto_result, _ = _mcp_auto_retry(execute_tool, auto_args, auto_result)
                                auto_elapsed = time.time() - auto_start
                                log_timing(
                                    "mcp_tool",
                                    {
                                        "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                                        "step_index": step_index + 1,
                                        "tool": execute_tool,
                                        "ms": round(auto_elapsed * 1000.0, 2),
                                        "auto_enrich": True,
                                    },
                                )
                                auto_err, auto_code = _mcp_error_info(auto_result)
                                if auto_err:
                                    friendly = _friendly_error_message(auto_err, auto_code)
                                    if friendly:
                                        auto_err = f"{friendly}\n원문: {auto_err}"
                                if auto_err:
                                    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", auto_err)
                                    summary_text = build_summary_text(auto_intent, None, auto_err)
                                    _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                                    _record_step_trace(
                                        mem_conn,
                                        cfg.MEMORY_CONVERSATION_ID,
                                        step_trace,
                                        {
                                            "step_index": step_index + 1,
                                            "action": "auto_enrich",
                                            "tool": execute_tool,
                                            "intent": auto_intent,
                                            "args": {"sql": "<hidden>"},
                                            "sql": _compact_sql_for_memory(sql_text),
                                            "result_summary": None,
                                            "error": auto_err,
                                        },
                                        run_id,
                                    )
                                    _validate_step_and_record(
                                        mem_conn,
                                        cfg.MEMORY_CONVERSATION_ID,
                                        {
                                            "original_request": original_request,
                                            "current_request": current_request,
                                            "step_index": step_index + 1,
                                            "action": "auto_enrich",
                                            "tool": execute_tool,
                                            "intent": auto_intent,
                                            "args": {"sql": "<hidden>"},
                                            "result_summary": None,
                                            "error": auto_err,
                                        },
                                    )
                                    _refresh_summary_after_step(
                                        mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                                    )
                                    save_memory_message(
                                        mem_conn,
                                        cfg.MEMORY_CONVERSATION_ID,
                                        "assistant",
                                        f"자동 탐색 오류: {auto_err}",
                                        {"internal": True},
                                    )
                                    auto_sets = []
                                else:
                                    auto_sets = _mcp_result_to_result_sets(auto_result)
                                for idx2, rs2 in enumerate(auto_sets, start=1):
                                    if rs2[0] == "rows":
                                        _, cols2, rows2 = rs2
                                        masked_rows = _mask_rows(cols2, rows2) if mask_pii else rows2
                                        table_view, shown2 = render_rows(cols2, masked_rows, max_rows=max_show)
                                        console.print(
                                            Panel(
                                                table_view,
                                                title=f"자동 결과 #{idx2} (표시 {shown2} / 전체 {len(rows2)})",
                                            )
                                        )
                                        safe_tag = re.sub(r"[^A-Za-z0-9_-]+", "_", str(csv_tag) or "auto")
                                        csv_path = save_csv(
                                            f"mcp_auto_{safe_tag}_{idx2}",
                                            cols2,
                                            masked_rows,
                                        )
                                        if AGENT_SHOW_INTERNAL:
                                            print_internal(f"[green]CSV 저장:[/green] {csv_path}")
                                        csv_preview = read_csv_preview(csv_path, AGENT_CSV_PREVIEW_ROWS)
                                        if csv_preview:
                                            save_memory_kv(
                                                mem_conn,
                                                cfg.MEMORY_CONVERSATION_ID,
                                                "last_csv_path",
                                                csv_path,
                                            )
                                            save_memory_kv(
                                                mem_conn,
                                                cfg.MEMORY_CONVERSATION_ID,
                                                "last_csv_preview",
                                                json.dumps(csv_preview, ensure_ascii=False),
                                            )
                                    else:
                                        _, rowcount2, _ = rs2
                                        console.print(Panel.fit(f"자동 결과 #{idx2}: ROWCOUNT={rowcount2}"))
    
                                auto_summary = (
                                    summarize_result_sets(auto_sets)
                                    if auto_sets
                                    else summarize_mcp_result(auto_result)
                                )
                                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", "")
                                save_memory_kv(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    "last_result_summary",
                                    json.dumps(auto_summary, ensure_ascii=False),
                                )
                                if enrich_key:
                                    save_memory_kv(
                                        mem_conn,
                                        cfg.MEMORY_CONVERSATION_ID,
                                        "last_enriched_table",
                                        enrich_key,
                                    )
                                summary_text = build_summary_text(auto_intent, auto_summary, "")
                                _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                                save_memory_message(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    "assistant",
                                    f"자동 탐색 완료: {auto_intent}",
                                )
                                _record_step_trace(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    step_trace,
                                    {
                                        "step_index": step_index + 1,
                                        "action": "auto_enrich",
                                        "tool": execute_tool,
                                        "intent": auto_intent,
                                        "args": {"sql": "<hidden>"},
                                        "sql": _compact_sql_for_memory(sql_text),
                                        "result_summary": auto_summary,
                                        "error": "",
                                    },
                                    run_id,
                                )
                                _validate_step_and_record(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    {
                                        "original_request": original_request,
                                        "current_request": current_request,
                                        "step_index": step_index + 1,
                                        "action": "auto_enrich",
                                        "tool": execute_tool,
                                        "intent": auto_intent,
                                        "args": {"sql": "<hidden>"},
                                        "result_summary": auto_summary,
                                        "error": "",
                                    },
                                )
                                _refresh_summary_after_step(
                                    mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                                )
                        if not candidates:
                            continue
                        tables_by_schema: dict[str, list[str]] = {}
                        for cand in candidates:
                            schema = str(cand.get("schema") or _required_schema_fallback(known_schemas)).strip()
                            table = str(cand.get("name", "")).strip()
                            if not table:
                                continue
                            tables_by_schema.setdefault(schema, [])
                            if table not in tables_by_schema[schema]:
                                tables_by_schema[schema].append(table)
                        structure_intent = _contains_structure_intent(original_request)
                        for schema, tables in tables_by_schema.items():
                            safe_schema = schema.replace("'", "''")
                            safe_tables = [t.replace("'", "''") for t in tables]
                            limit_clause = (
                                f" LIMIT {AGENT_COLUMN_SCAN_LIMIT}"
                                if AGENT_COLUMN_SCAN_LIMIT > 0
                                else ""
                            )
                            if safe_tables:
                                in_list = ", ".join([f"'{t}'" for t in safe_tables])
                                columns_sql = (
                                    "SELECT `TABLE_SCHEMA`, `TABLE_NAME`, `COLUMN_NAME`, `DATA_TYPE`, "
                                    "`IS_NULLABLE`, `COLUMN_KEY` "
                                    "FROM `information_schema`.`COLUMNS` "
                                    f"WHERE `TABLE_SCHEMA` = '{safe_schema}' AND `TABLE_NAME` IN ({in_list}) "
                                    "ORDER BY `TABLE_NAME`, `ORDINAL_POSITION`"
                                    f"{limit_clause}"
                                )
                            else:
                                columns_sql = (
                                    "SELECT `TABLE_SCHEMA`, `TABLE_NAME`, `COLUMN_NAME`, `DATA_TYPE`, "
                                    "`IS_NULLABLE`, `COLUMN_KEY` "
                                    "FROM `information_schema`.`COLUMNS` "
                                    f"WHERE `TABLE_SCHEMA` = '{safe_schema}' "
                                    "ORDER BY `TABLE_NAME`, `ORDINAL_POSITION`"
                                    f"{limit_clause}"
                                )
                            _run_auto_sql(
                                f"{schema} 컬럼 구조 조회",
                                columns_sql,
                                csv_tag=f"{schema}_columns",
                                enrich_key="",
                            )

                        for cand in candidates:
                            schema = str(cand.get("schema") or _required_schema_fallback(known_schemas)).strip()
                            table = str(cand.get("name", "")).strip()
                            if not table:
                                continue
                            enrich_key = f"{schema}.{table}".lower()
                            if enrich_key in enriched_tables:
                                continue
                            enriched_tables.add(enrich_key)
                            if structure_intent:
                                continue
                            sample_sql = (
                                f"SELECT * FROM `{schema}`.`{table}` "
                                f"LIMIT {AGENT_AUTO_ENRICH_SAMPLE_ROWS}"
                            )
                            _run_auto_sql(
                                f"{schema}.{table} 샘플 레코드 조회",
                                sample_sql,
                                csv_tag=f"{schema}_{table}",
                                enrich_key=enrich_key,
                                mask_pii=True,
                            )
                if tool in MCP_SEARCH_OBJECTS_CANDIDATES and schema_usage_answer_used:
                    return
                if pending_steps:
                    pending_steps, pending_step_index = _advance_pending_steps(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        pending_steps,
                        pending_step_index,
                    )
                current_request = "continue"
                continue
    
            sql = str(plan.get("sql", "")).strip()
            if not sql:
                question = "실행할 SQL을 확인할 수 없습니다. 요청을 조금 더 구체적으로 알려주세요."
                console.print(Panel.fit(question, title="확인 질문"))
                save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", question)
                return
            schema_hint = _detect_requested_schema(
                _effective_request(
                    current_request, original_request, kv.get("origin_request", "")
                ),
                known_schemas,
            )
            if not schema_hint:
                schema_hint = anchor_fast_schema or str(kv.get("preferred_schema") or "").strip()
            if schema_hint and schema_hint != schema_meta_schema:
                sql = _rewrite_schema_in_sql(sql, schema_hint, known_schemas)
                if not _sql_mentions_schema(sql, schema_hint):
                    sql = _prefix_use_schema(sql, schema_hint)
            dedupe_key = _build_turn_dedupe_key(sql, intent, schema_hint or "")
            repeat_count = _count_recent_sql_signature_repeats(
                step_trace,
                sql,
                window=AGENT_SQL_SIGNATURE_WINDOW,
                run_id=run_id,
            )
            if repeat_count >= max(1, AGENT_SQL_SIGNATURE_REPEAT_LIMIT):
                try:
                    log_fact_quality(
                        "sql_signature_alt_path",
                        {
                            "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                            "repeat_count": repeat_count,
                            "limit": max(1, AGENT_SQL_SIGNATURE_REPEAT_LIMIT),
                            "schema": schema_hint or "",
                            "intent": str(intent or "")[:120],
                        },
                    )
                except Exception:
                    pass
                if auto_continue_budget > 0 and not is_write:
                    auto_continue_budget -= 1
                    _set_retry_hint(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "동일 SQL 시그니처 반복 감지: 다른 후보 테이블/집계 경로로 전환",
                    )
                    current_request = _preserve_request_for_retry(
                        request_for_context,
                        original_request,
                    )
                    continue
                _emit_forced_conclusion(mem_conn, original_request, kv, step_trace, step_index)
                return
            if dedupe_key in executed_step_keys:
                if auto_continue_budget > 0 and not is_write:
                    auto_continue_budget -= 1
                    _set_retry_hint(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "같은 SQL/의도/스키마 재실행 차단: 다른 필터/집계 또는 후보 테이블로 전환",
                    )
                    current_request = _preserve_request_for_retry(
                        request_for_context,
                        original_request,
                    )
                    continue
                _emit_forced_conclusion(mem_conn, original_request, kv, step_trace, step_index)
                return
            executed_step_keys.add(dedupe_key)
            preview = f"의도={intent}\n쓰기작업={is_write}"
            if AGENT_SHOW_INTERNAL:
                print_internal(Panel.fit(preview, title="SQL 단계"))
            sql_log = log_text("sql_step", preview)
            if AGENT_SHOW_INTERNAL:
                print_internal(f"[dim]SQL 로그:[/dim] {sql_log}")
    
            if no_exec:
                save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", f"(실행 생략) {intent}")
                return
    
            if sql == "__CLEAR_MEMORY_TABLES__":
                clear_memory_tables(mem_conn)
                step_trace.clear()
                kept = ", ".join(AGENT_MEMORY_CLEAR_KEEP_IDS) if AGENT_MEMORY_CLEAR_KEEP_IDS else "(없음)"
                console.print(Panel.fit(f"대화 기록을 삭제했습니다. 보존 ConversationId: {kept}"))
                current_request = "continue"
                continue

            if _contains_local_infile(sql):
                summary_data, csv_paths, _csv_preview, err_msg = _analyze_local_infile_sql(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    sql,
                    _effective_request(
                        current_request, original_request, kv.get("origin_request", "")
                    ),
                )
                if err_msg:
                    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", err_msg)
                    summary_text = build_summary_text(intent, None, err_msg)
                    _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                    _record_step_trace(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        step_trace,
                        {
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": "csv_analysis",
                            "intent": intent,
                            "args": {"sql": "<hidden>"},
                            "sql": _compact_sql_for_memory(sql),
                            "result_summary": None,
                            "error": err_msg,
                        },
                        run_id,
                    )
                    if not _should_skip_aux_updates("csv_analysis", None, err_msg):
                        _validate_step_and_record(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            {
                                "original_request": original_request,
                                "current_request": current_request,
                                "step_index": step_index + 1,
                                "action": "step",
                                "tool": "csv_analysis",
                                "intent": intent,
                                "args": {"sql": "<hidden>"},
                                "result_summary": None,
                                "error": err_msg,
                            },
                        )
                    user_error = _build_user_facing_error(intent, err_msg)
                    if user_error:
                        save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", user_error)
                        save_memory_kv(
                            mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", user_error
                        )
                    if not _should_skip_aux_updates("csv_analysis", None, err_msg):
                        _refresh_summary_after_step(
                            mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                        )
                    return
                log_executed_sql("csv", intent, sql, "csv_analysis", False, attempt=1)
                summary_dict = summary_data if isinstance(summary_data, dict) else None
                summary_payload = summary_dict if summary_dict else None
                _record_insight_fact(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    intent,
                    summary_payload,
                    "csv_analysis",
                    source_run_id=run_id,
                    source_sql=sql,
                )
                _update_zero_result_flags(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    summary_dict,
                    sql,
                    intent,
                    run_id,
                )
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", "")
                _clear_error_signature(mem_conn, cfg.MEMORY_CONVERSATION_ID)
                save_memory_kv(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    "last_result_summary",
                    json.dumps(summary_data or {}, ensure_ascii=False),
                )
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_result_tool", "csv_analysis")
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_result_intent", intent)
                summary_text = build_summary_text(intent, summary_data or {}, "")
                _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                meta: dict[str, Any] = {"sql": sql}
                if csv_paths:
                    meta["csv_paths"] = csv_paths
                user_answer = ""
                if summary_data and isinstance(summary_data, dict):
                    user_answer = _format_user_answer_text(summary_data.get("summary") or "")
                if not user_answer:
                    user_answer = _build_user_facing_answer(intent, summary_payload, "csv_analysis")
                user_answer = _ensure_user_answer_quality(
                    intent,
                    summary_payload,
                    "csv_analysis",
                    user_answer,
                )
                if user_answer:
                    save_memory_message(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        "assistant",
                        user_answer,
                        meta,
                    )
                    save_memory_kv(
                        mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", user_answer
                    )
                _record_step_trace(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    step_trace,
                    {
                        "step_index": step_index + 1,
                        "action": "step",
                        "tool": "csv_analysis",
                        "intent": intent,
                        "args": {"sql": "<hidden>"},
                        "sql": _compact_sql_for_memory(sql),
                        "result_summary": summary_data,
                        "error": "",
                    },
                    run_id,
                )
                if not _should_skip_aux_updates("csv_analysis", summary_dict, ""):
                    _validate_step_and_record(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        {
                            "original_request": original_request,
                            "current_request": current_request,
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": "csv_analysis",
                            "intent": intent,
                            "args": {"sql": "<hidden>"},
                            "result_summary": summary_data,
                            "error": "",
                        },
                    )
                    _refresh_summary_after_step(
                        mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                    )
                if _is_direct_sql_request(original_request):
                    return
                if _is_list_only_request(original_request):
                    return
                if pending_steps:
                    pending_steps, pending_step_index = _advance_pending_steps(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        pending_steps,
                        pending_step_index,
                    )
                if (
                    not AGENT_AUTO_CONTINUE_AFTER_STEP
                    and not pending_steps
                    and not stepwise_active
                ):
                    return
                current_request = "continue"
                continue

            log_executed_sql("sql", intent, sql, "execute_sql", is_write, attempt=1)
            try:
                result_sets, elapsed = execute_sql(db_conn, sql)
            except Exception as exc:
                err_msg = str(exc)
                raw_err_msg = err_msg
                err_code = getattr(exc, "errno", None)
                err_title, _err_hint = _classify_error_message(raw_err_msg, err_code)
                not_found_error = _is_not_found_error_type(err_title)
                repeated_not_found_path = False
                if not_found_error and sql:
                    sig = _build_error_signature("execute_sql", err_title, sql, raw_err_msg)
                    repeated_not_found_path = _mark_error_signature(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        kv,
                        sig,
                    )
                friendly = _friendly_error_message(err_msg, err_code)
                missing_col = _extract_unknown_column(raw_err_msg)
                handled = True
                if missing_col:
                    fixed_sql = _safe_fix_missing_column_sql(sql, missing_col)
                    if fixed_sql and fixed_sql.strip() and fixed_sql.strip() != sql:
                        try:
                            log_executed_sql(
                                "sql", intent, fixed_sql, "execute_sql", is_write, attempt=2
                            )
                            sql = fixed_sql
                            retry_start = time.perf_counter()
                            result_sets, elapsed = execute_sql(db_conn, sql)
                            _timing_breakdown_add(
                                timing_breakdown,
                                "retry_ms",
                                (time.perf_counter() - retry_start) * 1000.0,
                            )
                            handled = False
                        except Exception as retry_exc:
                            err_msg = str(retry_exc)
                            raw_err_msg = err_msg
                            err_code = getattr(retry_exc, "errno", None)
                            friendly = _friendly_error_message(err_msg, err_code)
                elif (
                    AGENT_AUTO_FIX_SQL
                    and not AGENT_DISABLE_AUTO_RETRY
                    and (
                        _is_sql_syntax_error(raw_err_msg, err_code)
                        or not_found_error
                    )
                    and sql
                ):
                    fix_payload = {
                        "sql": sql,
                        "error": raw_err_msg,
                        "db_name": DB_NAME_EFFECTIVE,
                        "request": request_for_context,
                        "columns_hint": _extract_columns_hint(knowledge_payload),
                    }
                    fixed_sql = llm_fix_sql(fix_payload)
                    if fixed_sql and fixed_sql.strip() and fixed_sql.strip() != sql:
                        try:
                            log_executed_sql(
                                "sql", intent, fixed_sql, "execute_sql", is_write, attempt=2
                            )
                            sql = fixed_sql
                            retry_start = time.perf_counter()
                            result_sets, elapsed = execute_sql(db_conn, sql)
                            _timing_breakdown_add(
                                timing_breakdown,
                                "retry_ms",
                                (time.perf_counter() - retry_start) * 1000.0,
                            )
                            handled = False
                        except Exception as retry_exc:
                            err_msg = str(retry_exc)
                            raw_err_msg = err_msg
                            err_code = getattr(retry_exc, "errno", None)
                            friendly = _friendly_error_message(err_msg, err_code)
                if (
                    handled
                    and AGENT_ERROR_AUTO_RECOVERY
                    and not is_write
                    and sql
                ):
                    recovered = _auto_recover_not_found_sql(
                        db_conn,
                        sql,
                        raw_err_msg,
                        err_code,
                        request_for_context,
                        kv,
                        known_schemas,
                    )
                    if recovered:
                        recovered_sql, validation_sql, recovery_reason = recovered
                        if (
                            recovered_sql
                            and validation_sql
                            and recovered_sql.strip()
                            and recovered_sql.strip() != sql.strip()
                            and _validate_sql_probe(db_conn, validation_sql)
                        ):
                            try:
                                log_executed_sql(
                                    "sql",
                                    intent,
                                    recovered_sql,
                                    "execute_sql",
                                    is_write,
                                    attempt=3,
                                )
                                sql = recovered_sql
                                retry_start = time.perf_counter()
                                result_sets, elapsed = execute_sql(db_conn, sql)
                                _timing_breakdown_add(
                                    timing_breakdown,
                                    "retry_ms",
                                    (time.perf_counter() - retry_start) * 1000.0,
                                )
                                handled = False
                                save_memory_kv(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    "last_auto_recovery",
                                    json.dumps(
                                        {
                                            "tool": "execute_sql",
                                            "reason": recovery_reason,
                                            "validation_sql": validation_sql,
                                            "recovered_sql": _compact_sql_for_memory(recovered_sql),
                                        },
                                        ensure_ascii=False,
                                    ),
                                )
                            except Exception as recovery_exc:
                                err_msg = str(recovery_exc)
                                raw_err_msg = err_msg
                                err_code = getattr(recovery_exc, "errno", None)
                                friendly = _friendly_error_message(err_msg, err_code)
                if handled:
                    if friendly:
                        err_msg = f"{friendly}\n원문: {err_msg}"
                    save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", err_msg)
                    summary_text = build_summary_text(intent, None, err_msg)
                    _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
                    _record_step_trace(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        step_trace,
                        {
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": "execute_sql",
                            "intent": intent,
                            "args": {"sql": "<hidden>"},
                            "sql": _compact_sql_for_memory(sql),
                            "result_summary": None,
                            "error": err_msg,
                        },
                        run_id,
                    )
                    _validate_step_and_record(
                        mem_conn,
                        cfg.MEMORY_CONVERSATION_ID,
                        {
                            "original_request": original_request,
                            "current_request": current_request,
                            "step_index": step_index + 1,
                            "action": "step",
                            "tool": "execute_sql",
                            "intent": intent,
                            "args": {"sql": "<hidden>"},
                            "result_summary": None,
                            "error": err_msg,
                        },
                    )
                    source_request = request_for_context or original_request
                    source_sql = ""
                    if looks_like_sql(source_request):
                        source_sql = source_request
                    elif looks_like_sql(original_request):
                        source_sql = original_request
                    auto_retry = (
                        (not is_write)
                        and auto_continue_budget > 0
                        and _should_auto_continue_on_error(err_msg)
                    )
                    if not_found_error and (auto_continue_budget > 0 or not_found_recovery_budget > 0):
                        auto_retry = True
                    if auto_retry:
                        if not _should_skip_aux_updates("execute_sql", None, err_msg):
                            _refresh_summary_after_step(
                                mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                            )
                        if not_found_error:
                            if auto_continue_budget > 0:
                                auto_continue_budget -= 1
                            elif not_found_recovery_budget > 0:
                                not_found_recovery_budget -= 1
                            else:
                                auto_retry = False
                            if auto_retry:
                                _clear_last_resolved_object_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID)
                                mode_hint = (
                                    "동일 not-found 경로 반복 차단: 후보를 변경해 재시도"
                                    if repeated_not_found_path
                                    else "not-found 자동복구: 후보 탐색 1회 + 집계 1회 우선 실행"
                                )
                                _set_retry_hint(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    mode_hint,
                                )
                                current_request = _preserve_request_for_retry(
                                    source_request,
                                    original_request,
                                )
                        else:
                            auto_continue_budget -= 1
                            compact_err = _shorten_error_for_user(err_msg) or err_msg
                            if source_sql:
                                _set_retry_hint(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    f"직전 SQL 오류 우회 재시도: {compact_err}",
                                )
                            else:
                                _set_retry_hint(
                                    mem_conn,
                                    cfg.MEMORY_CONVERSATION_ID,
                                    f"직전 단계 오류 우회 재시도: {compact_err}",
                                )
                            current_request = _preserve_request_for_retry(
                                source_request,
                                original_request,
                            )
                        if auto_retry:
                            continue
                    if not_found_error:
                        _clear_last_resolved_object_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID)
                        forced = _build_forced_conclusion(original_request, kv, step_trace)
                        console.print(Panel.fit(forced, title="강제 결론"))
                        save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", forced)
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", forced)
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_forced_conclusion", forced)
                        if not _should_skip_aux_updates("execute_sql", None, err_msg):
                            _refresh_summary_after_step(
                                mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                            )
                        return
                    user_error = _build_user_facing_error(intent, err_msg)
                    if user_error:
                        save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", user_error)
                        save_memory_kv(
                            mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", user_error
                        )
                    if not _should_skip_aux_updates("execute_sql", None, err_msg):
                        _refresh_summary_after_step(
                            mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                        )
                    return
            log_timing(
                "sql",
                {
                    "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                    "step_index": step_index + 1,
                    "ms": round(elapsed * 1000.0, 2),
                },
            )
            if AGENT_SHOW_INTERNAL:
                print_internal(f"[dim]실행 시간:[/dim] {elapsed:.3f}s")
    
            csv_paths: list[str] = []
            for idx, rs in enumerate(result_sets, start=1):
                if rs[0] == "rows":
                    _, cols, rows_data = rs
                    table, shown = render_rows(cols, rows_data, max_rows=max_show)
                    console.print(Panel(table, title=f"결과 #{idx} (표시 {shown} / 전체 {len(rows_data)})"))
                    csv_path = save_csv(f"resultset{idx}", cols, rows_data)
                    if AGENT_SHOW_INTERNAL:
                        print_internal(f"[green]CSV 저장:[/green] {csv_path}")
                    csv_paths.append(csv_path)
    
                    csv_preview = read_csv_preview(csv_path, AGENT_CSV_PREVIEW_ROWS)
                    if csv_preview:
                        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_csv_path", csv_path)
                        save_memory_kv(
                            mem_conn,
                            cfg.MEMORY_CONVERSATION_ID,
                            "last_csv_preview",
                            json.dumps(csv_preview, ensure_ascii=False),
                        )
                else:
                    _, rowcount, _ = rs
                    console.print(Panel.fit(f"결과 #{idx}: ROWCOUNT={rowcount}"))
    
            summary_data = summarize_result_sets(result_sets)
            if csv_paths:
                if isinstance(summary_data, dict):
                    summary_data["csv_paths"] = csv_paths
                else:
                    summary_data = {"summary": summary_data, "csv_paths": csv_paths}
            summary_dict = summary_data if isinstance(summary_data, dict) else None
            summary_payload = summary_dict if summary_dict else None
            _maybe_record_schema_usage(
                mem_conn,
                cfg.MEMORY_CONVERSATION_ID,
                sql,
                summary_dict,
                request_text=request_for_context,
                kv=kv,
                fallback_schema=schema_hint or "",
                source_run_id=run_id,
            )
            _maybe_record_summary_facts(
                mem_conn,
                cfg.MEMORY_CONVERSATION_ID,
                sql,
                summary_dict,
                intent,
                source_run_id=run_id,
            )
            if summary_dict and sql:
                schema_name, table_name = _extract_first_table_from_sql(sql)
                _record_table_usage_insight(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    schema_name or "",
                    table_name or "",
                    summary_dict.get("col_names"),
                    source_run_id=run_id,
                    fallback_schema=schema_hint or "",
                )
            _record_insight_fact(
                mem_conn,
                cfg.MEMORY_CONVERSATION_ID,
                intent,
                summary_payload,
                "execute_sql",
                source_run_id=run_id,
                source_sql=sql,
            )
            _update_zero_result_flags(
                mem_conn,
                cfg.MEMORY_CONVERSATION_ID,
                summary_dict,
                sql,
                intent,
                run_id,
            )
            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", "")
            _clear_error_signature(mem_conn, cfg.MEMORY_CONVERSATION_ID)
            save_memory_kv(
                mem_conn,
                cfg.MEMORY_CONVERSATION_ID,
                "last_result_summary",
                json.dumps(summary_data, ensure_ascii=False),
            )
            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_result_tool", "execute_sql")
            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_result_intent", intent)
            # ── follow-up 문맥 보존: 성공한 SQL에서 사용된 테이블을 last_resolved_object로 저장 ──
            _resolved_ref = _extract_primary_table_ref_from_sql(sql)
            if _resolved_ref:
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_resolved_object", _resolved_ref)
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_resolved_object_at", utc_now_iso())
            summary_text = build_summary_text(intent, summary_data, "")
            _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
            meta: dict[str, Any] = {}
            if sql:
                meta["sql"] = sql
            if csv_paths:
                meta["csv_paths"] = csv_paths
            user_answer = _build_user_facing_answer(intent, summary_payload, "execute_sql")
            user_answer = _ensure_user_answer_quality(
                intent,
                summary_payload,
                "execute_sql",
                user_answer,
            )
            if user_answer:
                save_memory_message(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    "assistant",
                    user_answer,
                    meta if meta else None,
                )
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", user_answer)
            _record_step_trace(
                mem_conn,
                cfg.MEMORY_CONVERSATION_ID,
                step_trace,
                {
                    "step_index": step_index + 1,
                    "action": "step",
                    "tool": "execute_sql",
                    "intent": intent,
                    "args": {"sql": "<hidden>"},
                    "sql": _compact_sql_for_memory(sql),
                    "result_summary": summary_data,
                    "error": "",
                },
                run_id,
            )
            if not _should_skip_aux_updates("execute_sql", summary_dict, ""):
                _validate_step_and_record(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    {
                        "original_request": original_request,
                        "current_request": current_request,
                        "step_index": step_index + 1,
                        "action": "step",
                        "tool": "execute_sql",
                        "intent": intent,
                        "args": {"sql": "<hidden>"},
                        "result_summary": summary_data,
                        "error": "",
                    },
                )
                _refresh_summary_after_step(
                    mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
                )
            if _is_direct_sql_request(original_request):
                return
            if _is_list_only_request(original_request):
                return
            if pending_steps:
                pending_steps, pending_step_index = _advance_pending_steps(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    pending_steps,
                    pending_step_index,
                )
            if (
                not AGENT_AUTO_CONTINUE_AFTER_STEP
                and not pending_steps
                and not stepwise_active
            ):
                return
            current_request = "continue"
            continue
        
        final_kv = kv if isinstance(kv, dict) else {}
        if not final_kv:
            try:
                mem_rw_start = time.perf_counter()
                _, _, final_kv = load_memory_context(
                    mem_conn, cfg.MEMORY_CONVERSATION_ID, AGENT_MEMORY_MAX_TURNS
                )
                _timing_breakdown_add(
                    timing_breakdown,
                    "memory_rw_ms",
                    (time.perf_counter() - mem_rw_start) * 1000.0,
                )
            except Exception:
                final_kv = {}
        conclusion = _build_forced_conclusion(original_request, final_kv, step_trace)
        console.print(Panel.fit(conclusion, title="강제 결론"))
        save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", conclusion)
        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", conclusion)
        save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_forced_conclusion", conclusion)
        summary_text = build_summary_text("강제 결론", {"summary": conclusion}, "")
        _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
        _refresh_summary_after_step(
            mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, AGENT_MAX_STEPS
        )

    except Exception as exc:
        err = str(exc)
        err_path = log_text("error_step", err)
        if AGENT_SHOW_INTERNAL:
            console.print(f"[red]오류:[/red] {err}\n[dim]오류 로그:[/dim] {err_path}")
        else:
            console.print(f"[red]오류:[/red] {err}")
        try:
            save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error", err)
            summary_text = build_summary_text("실패", None, err)
            _record_step_summary(mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text)
            user_error = _build_user_facing_error("요청", err)
            if user_error:
                save_memory_message(mem_conn, cfg.MEMORY_CONVERSATION_ID, "assistant", user_error)
                save_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_user_answer", user_error)
            _refresh_summary_after_step(
                mem_conn, cfg.MEMORY_CONVERSATION_ID, summary_text, step_index + 1
            )
        except Exception:
            pass
        raise
    finally:
        finalize_start = time.perf_counter()
        if not skip_status_update:
            try:
                duration_ms = round((time.perf_counter() - run_start) * 1000.0, 2)
                last_error = load_memory_kv(mem_conn, cfg.MEMORY_CONVERSATION_ID, "last_error")
                status = "error" if last_error else "done"
                set_run_status(
                    mem_conn,
                    cfg.MEMORY_CONVERSATION_ID,
                    status,
                    run_id=run_id,
                    duration_ms=duration_ms,
                    error=last_error,
                )
            except Exception:
                pass
        try:
            if isinstance(locals().get("timing_breakdown"), dict):
                timing_payload = locals().get("timing_breakdown")
                finalize_ms = (time.perf_counter() - finalize_start) * 1000.0
                _timing_breakdown_add(timing_payload, "finalize_ms", finalize_ms)
                timing_payload["total_ms"] = round((time.perf_counter() - run_start) * 1000.0, 2)
                written_path = _write_timing_breakdown(timing_payload)
                if written_path:
                    log_timing(
                        "timing_breakdown",
                        {
                            "conversation_id": cfg.MEMORY_CONVERSATION_ID,
                            "run_id": run_id,
                            "path": written_path,
                            "total_ms": timing_payload.get("total_ms"),
                        },
                    )
        except Exception:
            pass
        cfg.CURRENT_RUN_ID = ""
        _clear_run_deadline()
        try:
            mem_conn.close()
        except Exception:
            pass
        try:
            db_conn.close()
        except Exception:
            pass
        
        
def _print_conversations(conn) -> list[tuple[Any, Any, Any]]:
    rows = list_conversations(conn, limit=200)
    if not rows:
        console.print("저장된 대화가 없습니다.")
        return []
    if cfg.MEMORY_CONVERSATION_ID:
        console.print(f"현재 대화 ID: {cfg.MEMORY_CONVERSATION_ID}")
    t = Table(show_lines=False)
    t.add_column("현재", justify="center")
    t.add_column("번호", justify="right")
    t.add_column("대화 ID")
    t.add_column("주제")
    t.add_column("생성 시각")
    for i, row in enumerate(rows, start=1):
        conv_id, topic, created_at = row
        marker = "Y" if str(conv_id) == str(cfg.MEMORY_CONVERSATION_ID) else ""
        t.add_row(marker, str(i), str(conv_id), str(topic), str(created_at))
    console.print(Panel(t, title="대화 목록"))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?", help="자연어 요청")
    ap.add_argument("--repl", action="store_true", help="대화형 모드")
    ap.add_argument("--no-exec", action="store_true", help="SQL 생성만 하고 실행하지 않음")
    ap.add_argument("--max-show", type=int, default=AGENT_MAX_SHOW, help="터미널 표시 최대 행 수")
    ap.add_argument("--init-memory", action="store_true", help="메모리 스키마 초기화만 수행")
    ap.add_argument("--insight-worker", action="store_true", help="상시 내부 인사이트 워커 실행")
    ap.add_argument("--insight-once", action="store_true", help="내부 인사이트 1회 실행")
    ap.add_argument("--list-conversations", action="store_true", help="대화 목록 출력")
    ap.add_argument("--new-conversation", action="store_true", help="새 대화 생성")
    ap.add_argument("--use-conversation", metavar="CONV_ID", help="지정한 대화 ID 사용")
    ap.add_argument("--use-conversation-index", metavar="INDEX", type=int, help="대화 인덱스로 선택")
    ap.add_argument("--delete-conversation-index", metavar="INDEX", type=int, help="대화 인덱스로 삭제")
    ap.add_argument("--rename-conversation-index", metavar="INDEX", type=int, help="대화 인덱스로 주제 변경")
    ap.add_argument("--rename-topic", metavar="TOPIC", help="--rename-conversation-index와 함께 사용할 주제")
    args = ap.parse_args()
    
    ensure_memory_schema()

    if args.insight_worker and args.insight_once:
        raise SystemExit("--insight-worker 와 --insight-once 는 함께 사용할 수 없습니다.")

    if args.insight_once:
        result = run_insight_cycle()
        console.print(
            f"insight cycle: status={result.get('status')} run_id={result.get('run_id')} "
            f"duration_ms={result.get('duration_ms')}"
        )
        return

    if args.insight_worker:
        run_insight_worker_loop()
        return
    
    if args.use_conversation:
        set_memory_conversation_id(args.use_conversation.strip())
    
    if args.init_memory:
        console.print(f"메모리 스키마가 `{MEMORY_DB}` 데이터베이스에 준비되었습니다.")
        if AGENT_SCHEMA_INSIGHT and (AGENT_SCHEMA_BOOTSTRAP or AGENT_SCHEMA_INSTANCE_SCAN):
            db_conn = None
            mem_conn = None
            try:
                db_conn = connect_with_retry(database=DB_CONNECT_DB, autocommit=True)
                mem_conn = connect_with_retry(database=MEMORY_DB, autocommit=True)
                known = load_known_schemas(db_conn)
                if known:
                    cfg.KNOWN_SCHEMAS.clear()
                    cfg.KNOWN_SCHEMAS.extend(known)
                _bootstrap_schema_insights(db_conn, mem_conn, cfg.KNOWN_SCHEMAS, run_id="init-memory")
                _scan_instance_schema_insights(db_conn, mem_conn, cfg.KNOWN_SCHEMAS, run_id="init-memory")
            except Exception:
                pass
            finally:
                try:
                    if db_conn is not None:
                        db_conn.close()
                except Exception:
                    pass
                try:
                    if mem_conn is not None:
                        mem_conn.close()
                except Exception:
                    pass
        return
    
    mem_conn = connect(database=MEMORY_DB, autocommit=True)
    try:
        if args.list_conversations:
            _print_conversations(mem_conn)
            return
    
        if args.new_conversation:
            conv_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
            create_conversation(mem_conn, conv_id, topic="대화")
            set_memory_conversation_id(conv_id)
            console.print(f"새 대화 생성: {conv_id}")
            return
    
        if args.delete_conversation_index:
            selected = _resolve_conversation_by_index(mem_conn, args.delete_conversation_index)
            if not selected:
                raise SystemExit(f"유효하지 않은 인덱스: {args.delete_conversation_index}")
            conv_id = selected[0]
            delete_conversation(mem_conn, conv_id)
            console.print(f"대화 삭제: {conv_id}")
            return
    
        if args.rename_conversation_index:
            if not args.rename_topic:
                raise SystemExit("--rename-conversation-index 사용 시 --rename-topic이 필요합니다.")
            selected = _resolve_conversation_by_index(mem_conn, args.rename_conversation_index)
            if not selected:
                raise SystemExit(f"유효하지 않은 인덱스: {args.rename_conversation_index}")
            conv_id = selected[0]
            save_memory_kv(mem_conn, conv_id, "topic", args.rename_topic)
            console.print(f"대화 주제 변경: {conv_id}")
            return
    
        if args.use_conversation_index:
            selected = _resolve_conversation_by_index(mem_conn, args.use_conversation_index)
            if not selected:
                raise SystemExit(f"유효하지 않은 인덱스: {args.use_conversation_index}")
            conv_id = selected[0]
            set_memory_conversation_id(conv_id)
            console.print(f"현재 대화: {conv_id}")
            if not args.prompt:
                return
    
    finally:
        mem_conn.close()
    
    if args.repl:
        console.print("[bold]AI MySQL CLI[/bold]  (종료: exit 또는 quit)")
        while True:
            nl = console.input("\n[cyan]> [/cyan]").strip()
            if nl.lower() in ("exit", "quit"):
                break
            if not nl:
                continue
            run_once(nl, no_exec=args.no_exec, max_show=args.max_show)
        return
    
    if not args.prompt:
        if args.use_conversation or args.use_conversation_index:
            console.print(f"현재 대화: {cfg.MEMORY_CONVERSATION_ID}")
            return
        console.print("프롬프트가 필요합니다. 또는 --repl 옵션을 사용하세요.")
        raise SystemExit(2)
    
    run_once(args.prompt, no_exec=args.no_exec, max_show=args.max_show)
    
    
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
