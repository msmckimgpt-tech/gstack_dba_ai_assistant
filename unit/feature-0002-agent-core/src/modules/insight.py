import uuid
import hashlib
import random
import re
import time
__all__ = [
    "_bootstrap_schema_insights",
    "_is_insight_worker_heartbeat_fresh",
    "_new_insight_worker_run_id",
    "_scan_instance_schema_insights",
    "_should_run_inline_insight_scan",
    "run_insight_cycle",
    "run_insight_worker_loop",
]


"""Schema/table insight scanning, bootstrap, background worker."""
from .config import *
import hashlib, json, random, re, time, uuid
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Fingerprint-based change detection
# ---------------------------------------------------------------------------

def _compute_schema_fingerprint(db_conn, schema: str) -> str:
    """스키마의 테이블 목록으로 핑거프린트를 계산한다."""
    cur = db_conn.cursor()
    try:
        cur.execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME",
            (schema,),
        )
        rows = cur.fetchall() or []
        names = sorted(str(r[0]).strip() for r in rows if r and r[0])
        return hashlib.sha256("|".join(names).encode()).hexdigest()[:32]
    finally:
        cur.close()


def _compute_table_fingerprint(db_conn, schema: str, table: str) -> str:
    """테이블의 컬럼 이름+타입으로 핑거프린트를 계산한다."""
    cur = db_conn.cursor()
    try:
        cur.execute(
            "SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION",
            (schema, table),
        )
        rows = cur.fetchall() or []
        parts = []
        for r in rows:
            parts.append(":".join(str(c or "").strip() for c in r))
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]
    finally:
        cur.close()


def _compute_table_fingerprints_batch(db_conn, schema: str, tables: list[str]) -> dict[str, str]:
    """여러 테이블의 핑거프린트를 한 번의 쿼리로 계산한다."""
    if not tables:
        return {}
    cur = db_conn.cursor()
    try:
        placeholders = ",".join(["%s"] * len(tables))
        cur.execute(
            f"SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY "
            f"FROM information_schema.COLUMNS "
            f"WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({placeholders}) "
            f"ORDER BY TABLE_NAME, ORDINAL_POSITION",
            [schema] + tables,
        )
        rows = cur.fetchall() or []
        table_parts: dict[str, list[str]] = {}
        for r in rows:
            tname = str(r[0] or "").strip()
            if not tname:
                continue
            part = ":".join(str(c or "").strip() for c in r[1:])
            table_parts.setdefault(tname, []).append(part)
        result = {}
        for tname, parts in table_parts.items():
            result[tname] = hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]
        return result
    finally:
        cur.close()


def _load_stored_fingerprints(mem_conn, prefix: str) -> dict[str, str]:
    """KV에서 특정 prefix의 핑거프린트들을 로드한다."""
    return _load_kv_prefix_map(mem_conn, GLOBAL_CONVERSATION_ID, prefix)


def _save_fingerprint(mem_conn, key: str, fingerprint: str) -> None:
    """핑거프린트를 KV에 저장한다."""
    try:
        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, key, fingerprint)
    except Exception:
        pass

def _bootstrap_schema_insights(
    db_conn,
    mem_conn,
    schemas: list[str],
    run_id: str | None = None,
) -> None:
    if not db_conn or not mem_conn or not AGENT_SCHEMA_BOOTSTRAP or not AGENT_SCHEMA_INSIGHT:
        return
    try:
        booted = load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "schema_insights_bootstrap_at")
        if booted:
            return
    except Exception:
        pass
    schema_list = [str(s or "").strip() for s in (schemas or [])]
    schema_list = [s for s in schema_list if s and not _is_system_schema(s)]
    if not schema_list:
        return
    existing_schema_insights = _load_existing_schema_insights(mem_conn)
    pending_schemas = [s for s in schema_list if s not in existing_schema_insights]
    seen_schemas = [s for s in schema_list if s in existing_schema_insights]
    schema_list = pending_schemas + seen_schemas
    existing_table_map = _load_existing_table_insight_map(mem_conn, schema_list)
    cur = db_conn.cursor()
    try:
        for schema in schema_list:
            cur.execute(
                """
SELECT TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = %s
ORDER BY TABLE_NAME
                """,
                (schema,),
            )
            rows = cur.fetchall() or []
            names = [str(r[0]).strip() for r in rows if r and r[0]]
            names = [n for n in names if n]
            if not names:
                continue
            seen_tables = existing_table_map.get(schema, set())
            pending = [t for t in names if t not in seen_tables]
            known = [t for t in names if t in seen_tables]
            prioritized = pending + known
            hints = prioritized[: max(1, int(AGENT_SCHEMA_BOOTSTRAP_MAX_TABLES))]
            if hints:
                _record_schema_insight_from_search(
                    mem_conn,
                    GLOBAL_SESSION_CONVERSATION_ID or GLOBAL_CONVERSATION_ID,
                    schema,
                    hints,
                    source_run_id=run_id,
                )
    finally:
        cur.close()
    try:
        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "schema_insights_bootstrap_at", utc_now_iso())
    except Exception:
        pass


def _scan_instance_schema_insights(
    db_conn,
    mem_conn,
    schemas: list[str],
    run_id: str | None = None,
) -> None:
    if not db_conn or not mem_conn or not AGENT_SCHEMA_INSTANCE_SCAN or not AGENT_SCHEMA_INSIGHT:
        return
    if not OPENAI_API_KEY or OpenAI is None:
        return
    candidates = [str(s or "").strip() for s in (schemas or [])]
    candidates = [s for s in candidates if s and not _is_system_schema(s)]
    if not candidates:
        return
    existing_schema_insights = _load_existing_schema_insights(mem_conn)
    missing = [schema for schema in candidates if schema not in existing_schema_insights]
    seen = [schema for schema in candidates if schema in existing_schema_insights]
    force_scan = bool(missing)
    candidates = missing + seen
    max_schemas = int(AGENT_SCHEMA_INSTANCE_SCAN_MAX_SCHEMAS or 0)
    if max_schemas > 0 and candidates:
        pick_limit = min(max_schemas, len(candidates))
        offset_key = "schema_instance_scan_schema_offset"
        try:
            offset = int(load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, offset_key) or 0)
        except Exception:
            offset = 0
        if offset < 0:
            offset = 0
        if force_scan and missing:
            rotated_missing = _rotate_list(missing, offset)
            selected = rotated_missing[:pick_limit]
            if len(selected) < pick_limit and seen:
                rotated_seen = _rotate_list(seen, offset)
                selected.extend(rotated_seen[: pick_limit - len(selected)])
            candidates = selected
            base_len = len(missing) if missing else len(candidates)
        else:
            rotated_all = _rotate_list(candidates, offset)
            candidates = rotated_all[:pick_limit]
            base_len = len(rotated_all)
        if base_len > 0:
            step = pick_limit if base_len > pick_limit else 1
            new_offset = (offset + max(1, step)) % base_len
            try:
                save_memory_kv(
                    mem_conn, GLOBAL_CONVERSATION_ID, offset_key, str(new_offset)
                )
            except Exception:
                pass
    if not force_scan:
        try:
            last_scan = load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "schema_instance_scan_at")
            parsed = _parse_iso_time(str(last_scan)) if last_scan else None
            if parsed:
                elapsed = (datetime.now(timezone.utc) - parsed).total_seconds()
                if elapsed < max(5, AGENT_SCHEMA_INSTANCE_SCAN_EVERY_SEC):
                    return
        except Exception:
            pass

    # ── 핑거프린트 기반 변경 감지 ──
    stored_schema_fps = _load_stored_fingerprints(mem_conn, "schema_fp:")
    stored_table_fps = _load_stored_fingerprints(mem_conn, "table_fp:")

    cur = db_conn.cursor()
    did_scan = False
    scan_start = time.perf_counter()
    budget_sec = max(5, int(AGENT_SCHEMA_INSTANCE_SCAN_BUDGET_SEC))
    table_seen_map = _load_existing_table_insight_map(mem_conn, candidates)
    schema_refresh_sec = int(AGENT_SCHEMA_INSIGHT_RESCAN_SEC or 0)
    table_refresh_sec = int(AGENT_TABLE_INSIGHT_RESCAN_SEC or 0)
    schema_refresh_map = _load_kv_prefix_map(mem_conn, GLOBAL_CONVERSATION_ID, "schema_insight_refresh_at:")
    table_refresh_map = _load_kv_prefix_map(mem_conn, GLOBAL_CONVERSATION_ID, "table_insight_refresh_at:")
    skipped_schemas = 0
    skipped_tables = 0
    try:
        for schema in candidates:
            if time.perf_counter() - scan_start > budget_sec:
                break
            try:
                # 스키마 핑거프린트 계산 (테이블 목록 기반)
                current_schema_fp = _compute_schema_fingerprint(db_conn, schema)
                schema_fp_key = f"schema_fp:{schema}"
                stored_schema_fp = stored_schema_fps.get(schema_fp_key, "")
                schema_structure_changed = (current_schema_fp != stored_schema_fp)

                cur.execute(
                    """
SELECT COLUMN_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = %s
ORDER BY TABLE_NAME, ORDINAL_POSITION
                    """,
                    (schema,),
                )
                col_rows = cur.fetchall() or []
                col_names: list[str] = []
                seen_cols: set[str] = set()
                for row in col_rows:
                    if not row or not row[0]:
                        continue
                    name = str(row[0]).strip()
                    if not name or name in seen_cols:
                        continue
                    seen_cols.add(name)
                    col_names.append(name)
                col_names = sorted(col_names)
                schema_key = f"schema_insight:{schema}"
                schema_refresh_key = f"schema_insight_refresh_at:{schema}"
                schema_missing = schema not in existing_schema_insights
                schema_refresh_due = _is_refresh_due(
                    schema_refresh_map, schema_refresh_key, schema_refresh_sec
                )
                # 스키마 인사이트: 신규 or 구조 변경 시에만 LLM 호출
                # fingerprint 존재하고 변경 없으면 타이머 만료여도 LLM 호출 생략 (비용 절감)
                schema_has_stored_fp = bool(stored_schema_fp)
                if schema_missing or schema_structure_changed or (schema_refresh_due and not schema_has_stored_fp):
                    schema_payload = {
                        "schema": schema,
                        "columns": col_names[: max(1, AGENT_SCHEMA_INSIGHT_MAX_COLS)],
                        "table_hints": [],
                    }
                    schema_insight = llm_schema_insight(schema_payload)
                    schema_text = _format_schema_insight_text(schema, schema_insight, col_names=col_names)
                    if schema_text and _should_publish_global_fact(schema_key, "schema_insight", 4, schema_text):
                        _publish_fact(
                            mem_conn,
                            GLOBAL_SESSION_CONVERSATION_ID or GLOBAL_CONVERSATION_ID,
                            schema_key,
                            schema_text,
                            4,
                            scope_key=FACT_SCOPE_COMMON,
                            source_type="schema_insight",
                            source_run_id=run_id,
                            source_sql="",
                            source_meta=schema_insight if isinstance(schema_insight, dict) else None,
                        )
                        existing_schema_insights.add(schema)
                        did_scan = True
                    _mark_refresh_kv(mem_conn, schema_refresh_map, schema_refresh_key)
                    # 핑거프린트 갱신
                    _save_fingerprint(mem_conn, schema_fp_key, current_schema_fp)
                    stored_schema_fps[schema_fp_key] = current_schema_fp
                else:
                    skipped_schemas += 1

                offset_key = f"schema_instance_scan_offset:{schema}"
                batch = max(1, int(AGENT_SCHEMA_INSTANCE_SCAN_TABLE_LIMIT))
                if run_id == "init-memory":
                    batch = min(batch, 2)
                cur.execute(
                    """
SELECT TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = %s
ORDER BY TABLE_NAME
                    """,
                    (schema,),
                )
                table_rows = cur.fetchall() or []
                all_table_names = [str(r[0]).strip() for r in table_rows if r and r[0]]
                all_table_names = [t for t in all_table_names if t]
                if not all_table_names:
                    try:
                        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, offset_key, "0")
                    except Exception:
                        pass
                    continue

                # 테이블 핑거프린트를 배치로 계산
                current_table_fps = _compute_table_fingerprints_batch(db_conn, schema, all_table_names)

                # 변경된 테이블 식별
                changed_tables: set[str] = set()
                for tname in all_table_names:
                    tfp_key = f"table_fp:{schema}.{tname}"
                    stored_tfp = stored_table_fps.get(tfp_key, "")
                    current_tfp = current_table_fps.get(tname, "")
                    if current_tfp != stored_tfp:
                        changed_tables.add(tname)

                seen_tables = table_seen_map.get(schema, set())
                pending_tables = [t for t in all_table_names if t not in seen_tables]
                known_tables = [t for t in all_table_names if t in seen_tables]

                # 변경 감지 기반 필터링 (fingerprint 변경 시에만 LLM 호출)
                # 타이머만 만료된 경우 fingerprint 존재하면 LLM 호출 생략 (비용 절감)
                pending_ready = []
                for t in pending_tables:
                    tfp_key_chk = f"table_fp:{schema}.{t}"
                    has_stored_tfp = bool(stored_table_fps.get(tfp_key_chk, ""))
                    if t in changed_tables or (not has_stored_tfp and _is_refresh_due(
                        table_refresh_map,
                        f"table_insight_refresh_at:{schema}.{t}",
                        table_refresh_sec,
                    )):
                        pending_ready.append(t)

                known_changed = [t for t in known_tables if t in changed_tables]
                known_ready = known_changed

                # 변경 없고 타이머도 안 된 테이블은 완전히 스킵
                skipped_tables += len(all_table_names) - len(pending_ready) - len(known_ready)

                try:
                    offset = int(load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, offset_key) or 0)
                except Exception:
                    offset = 0
                if offset < 0:
                    offset = 0
                if pending_ready:
                    rotated_pending = _rotate_list(pending_ready, offset)
                    table_names = rotated_pending[:batch]
                    base_len = len(pending_ready)
                elif known_ready:
                    rotated_known = _rotate_list(known_ready, offset)
                    table_names = rotated_known[:batch]
                    base_len = len(known_ready)
                else:
                    # 변경 없음 — 이 스키마의 모든 테이블 스킵
                    try:
                        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, offset_key, "0")
                    except Exception:
                        pass
                    continue
                table_cols: dict[str, list[tuple[str, str]]] = {}
                if table_names:
                    placeholders = ",".join(["%s"] * len(table_names))
                    cur.execute(
                        f"""
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({placeholders})
ORDER BY TABLE_NAME, ORDINAL_POSITION
                        """,
                        [schema] + table_names,
                    )
                    col_rows = cur.fetchall() or []
                    for table_name, col_name, data_type in col_rows:
                        tname = str(table_name or "").strip()
                        if not tname:
                            continue
                        name = str(col_name or "").strip()
                        if not name:
                            continue
                        table_cols.setdefault(tname, []).append(
                            (name, str(data_type or "").strip())
                        )
                for table in table_names:
                    if time.perf_counter() - scan_start > budget_sec:
                        break
                    col_rows = table_cols.get(table) or []
                    if not col_rows:
                        continue
                    cols_payload: list[dict[str, str]] = []
                    col_name_list: list[str] = []
                    seen_names: set[str] = set()
                    for col_name, data_type in col_rows:
                        name = str(col_name or "").strip()
                        if not name:
                            continue
                        if name in seen_names:
                            continue
                        seen_names.add(name)
                        col_name_list.append(name)
                        cols_payload.append({"name": name, "type": str(data_type or "").strip()})
                    if not cols_payload:
                        continue
                    col_name_list = sorted(col_name_list)
                    cols_payload = sorted(cols_payload, key=lambda x: str(x.get("name", "")))
                    table_payload = {
                        "schema": schema,
                        "table": table,
                        "columns": cols_payload[: max(1, int(AGENT_TABLE_INSIGHT_MAX_COLS))],
                    }
                    table_insight = llm_table_insight(table_payload)
                    table_refresh_key = f"table_insight_refresh_at:{schema}.{table}"
                    table_text = _format_table_insight_text(
                        schema, table, table_insight, col_names=col_name_list
                    )
                    table_key = f"table_insight:{schema}.{table}"
                    if table_text and _should_publish_global_fact(table_key, "schema_insight", 4, table_text):
                        _publish_fact(
                            mem_conn,
                            GLOBAL_SESSION_CONVERSATION_ID or GLOBAL_CONVERSATION_ID,
                            table_key,
                            table_text,
                            4,
                            scope_key=FACT_SCOPE_COMMON,
                            source_type="schema_insight",
                            source_run_id=run_id,
                            source_sql="",
                            source_meta=table_insight if isinstance(table_insight, dict) else None,
                        )
                        did_scan = True
                        table_seen_map.setdefault(schema, set()).add(table)
                    _mark_refresh_kv(mem_conn, table_refresh_map, table_refresh_key)
                    # 테이블 핑거프린트 갱신
                    tfp_key = f"table_fp:{schema}.{table}"
                    current_tfp = current_table_fps.get(table, "")
                    if current_tfp:
                        _save_fingerprint(mem_conn, tfp_key, current_tfp)
                        stored_table_fps[tfp_key] = current_tfp
                if base_len > 0:
                    step = batch if base_len > batch else 1
                    new_offset = (offset + max(1, step)) % base_len
                else:
                    new_offset = 0
                try:
                    save_memory_kv(
                        mem_conn,
                        GLOBAL_CONVERSATION_ID,
                        offset_key,
                        str(new_offset),
                    )
                except Exception:
                    pass
            except Exception:
                continue
    finally:
        cur.close()
    # 스킵 통계 로깅
    if skipped_schemas > 0 or skipped_tables > 0:
        append_log_line(
            "insight_worker",
            json.dumps({
                "event": "fingerprint_skip",
                "skipped_schemas": skipped_schemas,
                "skipped_tables": skipped_tables,
                "run_id": run_id or "",
            }, ensure_ascii=False),
        )
    try:
        if did_scan:
            save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "schema_instance_scan_at", utc_now_iso())
    except Exception:
        pass


def _is_insight_worker_heartbeat_fresh(mem_conn) -> bool:
    if not mem_conn:
        return False
    try:
        last_cycle = load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_cycle_at")
        if not last_cycle:
            return False
        parsed = _parse_iso_time(str(last_cycle))
        if not parsed:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age_sec = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
        if age_sec < 0:
            age_sec = 0
        last_status = (
            load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_status")
            .strip()
            .lower()
        )
        if last_status not in {"ok", "skip_locked"}:
            return False
        return age_sec <= max(30, int(AGENT_INSIGHT_WORKER_STALE_SEC))
    except Exception:
        return False


def _should_run_inline_insight_scan(mem_conn) -> tuple[bool, str]:
    if AGENT_INLINE_INSIGHT_ON_ASK:
        return True, "inline_forced"
    if not AGENT_INSIGHT_WORKER_ENABLED:
        return True, "worker_disabled"
    if _is_insight_worker_heartbeat_fresh(mem_conn):
        return False, "worker_fresh"
    return True, "worker_stale_or_missing"


def _new_insight_worker_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-iw" + uuid.uuid4().hex[:6]


def run_insight_cycle(run_id: str | None = None) -> dict[str, Any]:
    cycle_run_id = str(run_id or "").strip() or _new_insight_worker_run_id()
    started = time.perf_counter()
    lock_name = str(AGENT_INSIGHT_WORKER_LOCK_NAME or "").strip() or "agent_insight_worker_scan"
    status = "ok"
    err_text = ""
    schema_count = 0
    scan_triggered = 0
    lock_acquired = False
    timing = _timing_breakdown_template(
        cycle_run_id, AGENT_INSIGHT_WORKER_CONVERSATION_ID, "__insight_worker__"
    )
    mem_conn = None
    db_conn = None
    try:
        mem_start = time.perf_counter()
        mem_conn = connect_with_retry(database=MEMORY_DB, autocommit=True)
        _timing_breakdown_add(
            timing, "memory_rw_ms", (time.perf_counter() - mem_start) * 1000.0
        )
        db_start = time.perf_counter()
        db_conn = connect_with_retry(database=DB_CONNECT_DB, autocommit=True)
        _timing_breakdown_add(
            timing, "memory_rw_ms", (time.perf_counter() - db_start) * 1000.0
        )

        lock_acquired = _acquire_advisory_lock(
            mem_conn,
            lock_name,
            timeout_sec=max(0, int(AGENT_INSIGHT_WORKER_LOCK_TIMEOUT_SEC)),
        )
        if not lock_acquired:
            status = "skip_locked"
        else:
            known = load_known_schemas(db_conn)
            if known:
                KNOWN_SCHEMAS.clear()
                KNOWN_SCHEMAS.extend(known)
            schema_count = len([s for s in (KNOWN_SCHEMAS or []) if s and not _is_system_schema(s)])
            scan_before = load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "schema_instance_scan_at")
            plan_start = time.perf_counter()
            _bootstrap_schema_insights(db_conn, mem_conn, KNOWN_SCHEMAS, run_id=cycle_run_id)
            _scan_instance_schema_insights(db_conn, mem_conn, KNOWN_SCHEMAS, run_id=cycle_run_id)
            _timing_breakdown_add(timing, "plan_ms", (time.perf_counter() - plan_start) * 1000.0)
            scan_after = load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "schema_instance_scan_at")
            if str(scan_after or "").strip() and str(scan_after or "").strip() != str(scan_before or "").strip():
                scan_triggered = 1
    except Exception as exc:
        status = "error"
        err_text = str(exc).strip()[:500]
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        if mem_conn is not None:
            try:
                save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_cycle_at", utc_now_iso())
                save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_status", status)
                save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_run_id", cycle_run_id)
                save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_error", err_text)
                save_memory_kv(
                    mem_conn,
                    GLOBAL_CONVERSATION_ID,
                    "insight_worker_last_duration_ms",
                    f"{duration_ms:.2f}",
                )
            except Exception:
                pass
        if lock_acquired and mem_conn is not None:
            _release_advisory_lock(mem_conn, lock_name)
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

    timing["total_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
    timing["updated_at"] = utc_now_iso()
    timing["status"] = status
    timing["scan_triggered"] = int(scan_triggered)
    timing["schema_count"] = int(schema_count)
    timing["error"] = err_text
    timing_path = _write_timing_breakdown(timing)
    payload = {
        "run_id": cycle_run_id,
        "status": status,
        "duration_ms": round(float(timing.get("total_ms", 0.0)), 2),
        "schema_count": int(schema_count),
        "scan_triggered": int(scan_triggered),
        "error": err_text,
    }
    if timing_path:
        payload["timing_path"] = timing_path
    append_log_line("insight_worker", json.dumps(payload, ensure_ascii=False))
    return payload


def run_insight_worker_loop() -> None:
    if not AGENT_INSIGHT_WORKER_ENABLED:
        console.print("insight worker disabled: AGENT_INSIGHT_WORKER_ENABLED=0")
        return
    tick_sec = max(5, int(AGENT_INSIGHT_WORKER_TICK_SEC))
    jitter_sec = max(0, int(AGENT_INSIGHT_WORKER_JITTER_SEC))
    if jitter_sec > 0:
        time.sleep(random.uniform(0, float(jitter_sec)))
    while True:
        run_insight_cycle()
        time.sleep(tick_sec)


