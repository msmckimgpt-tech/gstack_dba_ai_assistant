import uuid
import hashlib
import random
import re
import time
import signal as _signal      # feature-0015: SIGTERM graceful (지역변수 `signal` 과 충돌 회피용 alias)
import threading as _threading
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
from shared.config import *
import hashlib, json, logging, random, re, time, uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from . import dialects as _dialects  # P7: insight 컬럼 핑거프린트 dialect 분기(MSSQL)
from shared import db as _db              # P7 follow-up: datasource 지원 connect_with_retry 명시 사용


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
        # TASK-0305 (RC2): casefold 로 케이스 정규화한 뒤 해시한다. MSSQL information_schema 가
        # 같은 논리 테이블을 cycle 마다 대문자(TF_ErrorLog) ↔ 소문자(tf_errorlog)로 번갈아 반환하면
        # fingerprint 가 진동 → schema_structure_changed 가 매 cycle True → 같은 스키마를 11초짜리
        # LLM 으로 무의미하게 재생성하던 churn 을 제거한다. casefold 는 해시 VALUE 에만 적용 —
        # ds_fact_key/ds_object_suffix 키 생성은 건드리지 않아 TASK-0220 write/read-back/grounding 정합 보존.
        names = sorted(str(r[0]).strip().casefold() for r in rows if r and r[0])
        return hashlib.sha256("|".join(names).encode()).hexdigest()[:32]
    finally:
        cur.close()


def _compute_table_fingerprint(db_conn, schema: str, table: str) -> str:
    """테이블의 컬럼 이름+타입으로 핑거프린트를 계산한다."""
    cur = db_conn.cursor()
    try:
        cur.execute(
            f"SELECT {_dialects.active().fingerprint_column_projection()} "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION",
            (schema, table),
        )
        rows = cur.fetchall() or []
        parts = []
        for r in rows:
            # TASK-0305 (RC2): casefold 케이스 정규화(해시 VALUE 한정) — 컬럼명/타입 케이스 진동에 의한
            # table fingerprint churn 방지.
            parts.append(":".join(str(c or "").strip().casefold() for c in r))
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
            f"SELECT TABLE_NAME, {_dialects.active().fingerprint_column_projection()} "
            f"FROM information_schema.COLUMNS "
            f"WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({placeholders}) "
            f"ORDER BY TABLE_NAME, ORDINAL_POSITION",
            [schema] + tables,
        )
        rows = cur.fetchall() or []
        table_parts: dict[str, list[str]] = {}
        for r in rows:
            # tname(r[0]) 은 dict KEY — 같은 cycle 의 all_table_names(information_schema 케이스)와
            # 매칭해야 하므로 casefold 하지 않는다. 해시 VALUE(part = 컬럼명/타입)에만 casefold 적용
            # (TASK-0305 RC2 — 케이스 진동 churn 방지, 키 정합 보존).
            tname = str(r[0] or "").strip()
            if not tname:
                continue
            part = ":".join(str(c or "").strip().casefold() for c in r[1:])
            table_parts.setdefault(tname, []).append(part)
        result = {}
        for tname, parts in table_parts.items():
            result[tname] = hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]
        return result
    finally:
        cur.close()


# ── 동일구조 테이블 그룹화 (feature-0002 insight-table-grouping, 2026-07-03) ──────────
# 날짜/번호 suffix 만 다른 동일구조 샤드(daily_league_ranking_1_20250727, _20250726 …)를
# 한 그룹으로 묶어 대표 1개만 LLM 분석하고 나머지는 LLM 없이 인사이트를 전파한다.
# 그룹 키 = (base_stem, column-fingerprint) — 지문이 같아 "구조 동일"을, base_stem 이 같아
# "같은 이름-family"를 함께 요구한다(구조만 우연히 같고 도메인 다른 테이블의 오그룹 방지).
_TABLE_STEM_BACKUP_RX = re.compile(r"[_-](?:bk|bak|backup|old|new|tmp|temp|copy|org|orig)$", re.IGNORECASE)
_TABLE_STEM_NUM_RX = re.compile(r"[_-]?\d+$")


def _table_base_stem(name: str) -> str:
    """테이블명에서 후행 날짜/번호/백업 suffix 를 반복 제거한 base stem 을 반환한다.

    daily_league_ranking_1_20250727 -> daily_league_ranking (날짜 8자리 → 번호 _1 순차 strip),
    DayuPoint_20230801_bk -> DayuPoint, Stat_ActiveUser_Again_20120918 -> Stat_ActiveUser_Again.
    최소 2글자 base 를 보존한다(start<2 인 strip 은 수행 안 함) — 전부 숫자/짧은 이름은 원본 유지.
    날짜는 연속 숫자열이라 일반 번호 strip 이 원자적으로 제거하므로 별도 날짜 정규식은 불필요."""
    s = str(name or "").strip()
    if not s:
        return s
    prev = None
    while s != prev:
        prev = s
        m = _TABLE_STEM_BACKUP_RX.search(s)
        if m and m.start() >= 2:
            s = s[: m.start()]
            continue
        m = _TABLE_STEM_NUM_RX.search(s)
        if m and m.start() >= 2:
            s = s[: m.start()]
            continue
    return s


def _table_group_sig(table: str, table_fps: dict[str, str]):
    """테이블의 그룹 서명 (base_stem, fingerprint). fp 부재/stem<2 면 None(그룹 제외 — pure LLM)."""
    fp = (table_fps.get(table) or "").strip()
    stem = _table_base_stem(table)
    if not fp or len(stem) < 2:
        return None
    return (stem, fp)


def _build_table_groups(table_names: list[str], table_fps: dict[str, str]):
    """all_table_names 를 그룹 서명별로 묶는다.

    반환 (sig_of, members_of):
      - sig_of[table]  = (base_stem, fp)  — 그룹 서명을 가진 모든 테이블(단일 멤버 포함, KV 상속용).
      - members_of[sig] = 정렬된 멤버 리스트 — cycle 내 fan-out 대상 후보(min_members 게이트는 호출측).
    """
    sig_of: dict[str, tuple] = {}
    members_of: dict[tuple, list] = {}
    for t in table_names:
        sig = _table_group_sig(t, table_fps)
        if sig is None:
            continue
        sig_of[t] = sig
        members_of.setdefault(sig, []).append(t)
    for sig in members_of:
        members_of[sig].sort()
    return sig_of, members_of


def _group_insight_kv_key(sig: tuple) -> str:
    """그룹 대표 분석 dict 의 KV 키. fp 가 구조를 인코딩하므로 fp 가 바뀌면 키가 바뀌어 자기 무효화."""
    stem, fp = sig
    return "table_group_insight:" + str(fp) + ":" + str(stem)[:120]


def _load_group_insight_kv(mem_conn, sig):
    """이전 cycle 대표가 저장한 그룹 분석 dict 를 KV 에서 로드(LLM 없이 상속). 없으면/오류 None."""
    if sig is None or mem_conn is None:
        return None
    try:
        raw = load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, _group_insight_kv_key(sig))
    except Exception:
        return None
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _save_group_insight_kv(mem_conn, sig, insight) -> None:
    """그룹 대표의 LLM 분석 dict 를 KV 에 저장 — 다음 cycle 신규 샤드가 LLM 없이 상속하게 한다."""
    if sig is None or mem_conn is None or not isinstance(insight, dict):
        return
    try:
        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, _group_insight_kv_key(sig),
                       json.dumps(insight, ensure_ascii=False))
    except Exception:
        pass


def _publish_table_insight(
    mem_conn, run_id, schema, table, insight, table_error, col_name_list,
    table_key, table_refs, table_reason, table_refresh_key,
    current_tfp, stored_table_fps, table_refresh_map, report,
    *, insight_via: str = "llm", family=None,
) -> bool:
    """table_insight dict 를 렌더→publish→verify→fp저장→refresh→telemetry 하고 완료 여부를 반환.

    대표(LLM/KV/cache 유래) 와 fan-out(형제 전파) 공용 — 두 경로의 발행 로직을 단일화해 drift 를 막는다.
    insight_via/family 는 관측·그룹 라벨(B)용 telemetry·source_meta 부가정보. tables_generated/
    tables_fanout 카운트와 table_seen_map 갱신은 호출측 책임(경로별 의미 분리)."""
    table_started = time.perf_counter()
    insight_dict = insight if isinstance(insight, dict) else None
    table_text = _format_table_insight_text(schema, table, insight_dict, col_names=col_name_list)
    source_meta = None
    if insight_dict is not None:
        source_meta = dict(insight_dict)
        if family is not None:
            source_meta["table_family"] = family
    publish_attempted = False
    publish_skip_reason = ""
    if (
        not table_error
        and table_text
        and _should_publish_global_fact(table_key, "schema_insight", 4, table_text)
    ):
        _publish_fact(
            mem_conn,
            _insight_target_conversation_id(),
            table_key,
            table_text,
            4,
            scope_key=FACT_SCOPE_COMMON,
            source_type="schema_insight",
            source_run_id=run_id,
            source_sql="",
            source_meta=source_meta,
        )
        publish_attempted = True
    elif table_error:
        publish_skip_reason = "llm_error"
    elif insight_dict is None:
        publish_skip_reason = "invalid_response"
    elif not table_text:
        publish_skip_reason = "empty_text"
    else:
        publish_skip_reason = "publish_filtered"
    verified_table_state = _load_insight_artifact_states(mem_conn, [table_key]).get(
        table_key, _empty_insight_artifact_state(table_key)
    )
    table_complete = _insight_artifact_complete(verified_table_state)
    result = "ok" if table_complete else "partial_persist"
    if table_error:
        result = "publish_failed"
        report["publish_failed"] = int(report.get("publish_failed", 0)) + 1
    _trace_insight_worker_event(
        run_id,
        "publish",
        schema,
        "table",
        table,
        table_reason,
        "generate_insight",
        referenced_objects=table_refs,
        result=result,
        duration_ms=(time.perf_counter() - table_started) * 1000.0,
        error=table_error,
        extra={
            "missing_parts": _insight_missing_parts(verified_table_state),
            "publish_attempted": bool(publish_attempted),
            "publish_skip_reason": publish_skip_reason,
            "insight_via": insight_via,
        },
    )
    _trace_insight_worker_event(
        run_id,
        "verify",
        schema,
        "table",
        table,
        table_reason,
        "verify_persist",
        referenced_objects=table_refs,
        result="ok" if table_complete else "partial_persist",
        extra={"missing_parts": _insight_missing_parts(verified_table_state)},
    )
    if table_complete:
        _mark_refresh_kv(mem_conn, table_refresh_map, table_refresh_key)
        tfp_key = ds_fact_key("table_fp", ds_object_suffix(schema, table))
        if current_tfp:
            _save_fingerprint(mem_conn, tfp_key, current_tfp)
            stored_table_fps[tfp_key] = current_tfp
    return table_complete


def _load_stored_fingerprints(mem_conn, prefix: str) -> dict[str, str]:
    """KV에서 특정 prefix의 핑거프린트들을 로드한다."""
    return _load_kv_prefix_map(mem_conn, GLOBAL_CONVERSATION_ID, prefix)


def _save_fingerprint(mem_conn, key: str, fingerprint: str) -> None:
    """핑거프린트를 KV에 저장한다."""
    try:
        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, key, fingerprint)
    except Exception:
        pass


def _insight_target_conversation_id() -> str:
    return str(GLOBAL_SESSION_CONVERSATION_ID or GLOBAL_CONVERSATION_ID or "").strip()


def _empty_insight_artifact_state(fact_key: str) -> dict[str, Any]:
    return {
        "fact_key": str(fact_key or "").strip(),
        "has_fact": False,
        "has_text": False,
        "has_rag_document": False,
        "has_rag_object": False,
        "conversation_id": "",
        "scope_key": FACT_SCOPE_COMMON,
        "fact_text": "",
        "repair_text": "",
        "weight": 4,
        "source_type": "schema_insight",
        "source_run_id": "",
        "source_sql": "",
    }


def _remember_repair_text(state: dict[str, Any], text: str) -> None:
    candidate = str(text or "").strip()
    if candidate and not str(state.get("repair_text") or "").strip():
        state["repair_text"] = candidate


# 검증 read-back 실패를 가시화하기 위한 1회성 경고 마커. 과거엔 각 쿼리가
# `except Exception: rows = []` 로 오류를 조용히 삼켜, backend drift(예: 05-27
# cutover 로 MySQL AgentMemory* 테이블이 DROP)가 "artifact 전부 missing" 으로
# 오인되어 insight 무한 재생성(livelock)을 일으켜도 어떤 신호도 남지 않았다.
_INSIGHT_READBACK_WARNED: set[str] = set()


def _warn_insight_readback_failed(stage: str, exc: Exception) -> None:
    """insight artifact 검증 read-back 실패를 insight_worker 로그에 1회 surface."""
    if stage in _INSIGHT_READBACK_WARNED:
        return
    _INSIGHT_READBACK_WARNED.add(stage)
    try:
        append_log_line(
            "insight_worker",
            json.dumps(
                {
                    "event": "insight_artifact_readback_failed",
                    "stage": stage,
                    "error": str(exc)[:200],
                },
                ensure_ascii=False,
            ),
        )
    except Exception:
        pass


def _build_insight_object_maps(
    keys: list[str],
) -> tuple[dict[str, str], dict[str, str]]:
    """fact_key → (schema rag-object, table rag-object) 매핑을 만든다 (backend 무관).

    TASK-0220: 키를 `object_key`(= `_infer_rag_object_from_fact` 가 datasource·database 접두까지
    포함해 만든 유일 식별자)로 쓴다. 과거 `(schema_name, table_name)` 튜플 키는 MSSQL multi-DB 에서
    여러 database 의 동일 `dbo.<table>` 가 충돌해 read-back 이 한 건만 인식 → 나머지 DB 가 매 사이클
    `artifact_missing` 으로 재생성되는 livelock 을 유발했다. object_key 는 ds/database 까지 포함하므로
    cross-DB 충돌이 없다. (MySQL 2계층은 object_key=`{schema}.{table}` 라 종전과 동치.)
    """
    schema_object_map: dict[str, str] = {}
    table_object_map: dict[str, str] = {}
    for fact_key in keys:
        object_type, object_key, _, _, _, _ = _infer_rag_object_from_fact(fact_key, "")
        if not object_key:
            continue
        if object_type == "schema":
            schema_object_map[object_key] = fact_key
        elif object_type == "table":
            table_object_map[object_key] = fact_key
    return schema_object_map, table_object_map


def _apply_insight_fact_rows(states: dict[str, dict[str, Any]], rows: list) -> None:
    """fact_entries 행 → state(has_fact/has_text/meta). MySQL·PG 공용 (컬럼 순서 동일)."""
    seen_fact_keys: set[str] = set()
    for row in rows:
        fact_key = str(row[0] or "").strip()
        if not fact_key or fact_key in seen_fact_keys:
            continue
        seen_fact_keys.add(fact_key)
        state = states.setdefault(fact_key, _empty_insight_artifact_state(fact_key))
        fact_text = str(row[3] or "").strip()
        state["has_fact"] = True
        state["conversation_id"] = str(row[1] or "").strip()
        state["scope_key"] = str(row[2] or "").strip() or FACT_SCOPE_COMMON
        state["fact_text"] = fact_text
        state["weight"] = int(row[4]) if row[4] is not None else 4
        state["source_type"] = str(row[5] or "").strip() or "schema_insight"
        state["source_run_id"] = str(row[6] or "").strip()
        state["source_sql"] = str(row[7] or "").strip()
        if fact_text:
            state["has_text"] = True
            _remember_repair_text(state, fact_text)


def _apply_insight_doc_rows(states: dict[str, dict[str, Any]], rows: list) -> None:
    """rag_documents 행 → state(has_rag_document/has_text). MySQL·PG 공용."""
    seen_doc_keys: set[str] = set()
    for row in rows:
        fact_key = str(row[0] or "").strip()
        if not fact_key or fact_key in seen_doc_keys:
            continue
        seen_doc_keys.add(fact_key)
        state = states.setdefault(fact_key, _empty_insight_artifact_state(fact_key))
        doc_text = str(row[1] or "").strip()
        state["has_rag_document"] = True
        if doc_text:
            state["has_text"] = True
            _remember_repair_text(state, doc_text)


def _apply_insight_schema_object_rows(
    states: dict[str, dict[str, Any]], rows: list, schema_object_map: dict[str, str]
) -> None:
    """schema rag_objects 행 → state(has_rag_object/has_text). MySQL·PG 공용.

    TASK-0220: row[0]=object_key 로 매칭(schema_name 아님 — MSSQL multi-DB 충돌 방지)."""
    seen_objects: set[str] = set()
    for row in rows:
        object_key = str(row[0] or "").strip()
        if not object_key or object_key in seen_objects:
            continue
        seen_objects.add(object_key)
        fact_key = schema_object_map.get(object_key)
        if not fact_key:
            continue
        state = states.setdefault(fact_key, _empty_insight_artifact_state(fact_key))
        object_text = str(row[1] or "").strip()
        state["has_rag_object"] = True
        if object_text:
            state["has_text"] = True
            _remember_repair_text(state, object_text)


def _apply_insight_table_object_rows(
    states: dict[str, dict[str, Any]], rows: list, table_object_map: dict[str, str]
) -> None:
    """table rag_objects 행 → state(has_rag_object/has_text). MySQL·PG 공용.

    TASK-0220: row[0]=object_key 로 매칭(schema/table 튜플 아님 — MSSQL multi-DB 충돌 방지)."""
    seen_objects: set[str] = set()
    for row in rows:
        object_key = str(row[0] or "").strip()
        if not object_key or object_key in seen_objects:
            continue
        seen_objects.add(object_key)
        fact_key = table_object_map.get(object_key)
        if not fact_key:
            continue
        state = states.setdefault(fact_key, _empty_insight_artifact_state(fact_key))
        object_text = str(row[1] or "").strip()
        state["has_rag_object"] = True
        if object_text:
            state["has_text"] = True
            _remember_repair_text(state, object_text)


def _load_insight_artifact_states_pg(
    fact_keys: list[str],
) -> dict[str, dict[str, Any]] | None:
    """`_load_insight_artifact_states` 의 Postgres read-back 경로.

    `AGENT_KB_READ_BACKEND=postgres` 일 때 KB write 정본인 PG 테이블
    (public.fact_entries/rag_documents/rag_objects + texts join)에서 artifact 존재
    여부를 읽어, MySQL 경로와 동일한 state dict 를 만든다. `_pg_connect_ro()`
    (agent_kb_ro least-priv) 사용. PG 미가용이면 None 반환 → caller MySQL fallback.

    이 경로가 없으면 영속 검증이 (DROP 된) MySQL 테이블을 조회해 매 사이클 4-part
    전부 missing 으로 오판 → insight 무한 재생성(livelock)을 일으킨다."""
    keys = [str(key or "").strip() for key in (fact_keys or []) if str(key or "").strip()]
    states = {key: _empty_insight_artifact_state(key) for key in keys}
    if not keys:
        return states
    if not _pg_available():
        return None
    conversation_ids = _global_fact_conversation_ids(include_shared=True)
    if not conversation_ids:
        return states
    cid_placeholders = ",".join(["%s"] * len(conversation_ids))
    key_placeholders = ",".join(["%s"] * len(keys))
    scope_clause, scope_params = _scope_filter_sql_pg(_scope_candidates(FACT_SCOPE_COMMON))

    try:
        conn = _pg_connect_ro()
    except Exception as exc:
        _warn_insight_readback_failed("pg_connect", exc)
        return None
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                f"""
SELECT
    e.fact_key,
    e.conversation_id,
    e.scope_key,
    COALESCE(t.text_content, '') AS fact_text,
    e.weight,
    COALESCE(e.source_type, '') AS source_type,
    COALESCE(e.source_run_id, '') AS source_run_id,
    COALESCE(e.source_sql, '') AS source_sql
FROM public.fact_entries e
LEFT JOIN public.texts t ON t.text_hash = e.text_hash
WHERE e.conversation_id IN ({cid_placeholders})
  AND e.fact_key IN ({key_placeholders}){scope_clause}
ORDER BY e.fact_key, e.weight DESC, e.updated_at DESC, e.id DESC
                """,
                [*conversation_ids, *keys, *scope_params],
            )
            fact_rows = cur.fetchall() or []
        finally:
            cur.close()
        _apply_insight_fact_rows(states, fact_rows)

        cur = conn.cursor()
        try:
            cur.execute(
                f"""
SELECT
    d.fact_key,
    COALESCE(t.text_content, '') AS doc_text
FROM public.rag_documents d
LEFT JOIN public.texts t ON t.text_hash = d.text_hash
WHERE d.conversation_id IN ({cid_placeholders})
  AND d.fact_key IN ({key_placeholders}){scope_clause}
ORDER BY d.fact_key, d.weight DESC, d.updated_at DESC, d.id DESC
                """,
                [*conversation_ids, *keys, *scope_params],
            )
            doc_rows = cur.fetchall() or []
        finally:
            cur.close()
        _apply_insight_doc_rows(states, doc_rows)

        schema_object_map, table_object_map = _build_insight_object_maps(keys)

        # TASK-0220: object_key 로 매칭(schema_name/table_name 튜플 아님). MSSQL multi-DB 에서
        # 여러 database 의 동일 `dbo.<table>` 가 (schema,table) 로는 충돌하지만 object_key
        # (`{ds}:{db}.{schema}.{table}`)는 유일 → read-back livelock 방지.
        if schema_object_map:
            cur = conn.cursor()
            try:
                schema_placeholders = ",".join(["%s"] * len(schema_object_map))
                cur.execute(
                    f"""
SELECT
    o.object_key,
    COALESCE(t.text_content, '') AS object_text
FROM public.rag_objects o
LEFT JOIN public.texts t ON t.text_hash = o.text_hash
WHERE o.conversation_id IN ({cid_placeholders})
  AND o.object_type = 'schema'
  AND o.object_key IN ({schema_placeholders}){scope_clause}
ORDER BY o.object_key, o.weight DESC, o.updated_at DESC, o.id DESC
                    """,
                    [*conversation_ids, *schema_object_map.keys(), *scope_params],
                )
                schema_rows = cur.fetchall() or []
            finally:
                cur.close()
            _apply_insight_schema_object_rows(states, schema_rows, schema_object_map)

        if table_object_map:
            cur = conn.cursor()
            try:
                table_placeholders = ",".join(["%s"] * len(table_object_map))
                cur.execute(
                    f"""
SELECT
    o.object_key,
    COALESCE(t.text_content, '') AS object_text
FROM public.rag_objects o
LEFT JOIN public.texts t ON t.text_hash = o.text_hash
WHERE o.conversation_id IN ({cid_placeholders})
  AND o.object_type = 'table'
  AND o.object_key IN ({table_placeholders}){scope_clause}
ORDER BY o.object_key, o.weight DESC, o.updated_at DESC, o.id DESC
                    """,
                    [*conversation_ids, *table_object_map.keys(), *scope_params],
                )
                table_rows = cur.fetchall() or []
            finally:
                cur.close()
            _apply_insight_table_object_rows(states, table_rows, table_object_map)
    except Exception as exc:
        # PG read 실패 → 가시화 후 None 반환(caller MySQL fallback, cutover 미완 안전망).
        _warn_insight_readback_failed("pg_query", exc)
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return states


def _load_insight_artifact_states(mem_conn, fact_keys: list[str]) -> dict[str, dict[str, Any]]:
    keys = [str(key or "").strip() for key in (fact_keys or []) if str(key or "").strip()]
    states = {key: _empty_insight_artifact_state(key) for key in keys}
    if not keys:
        return states
    # 05-27 cutover 이후 KB write 정본은 Postgres(public.fact_entries/rag_documents/
    # rag_objects/texts)다. MySQL AgentMemory* 테이블은 DROP 되어 더 이상 존재하지
    # 않으므로 영속 검증 read-back 도 동일 backend(PG)에서 읽어야 한다. 이 분기가
    # 없으면 매 사이클 4-part 전부 missing 으로 오판 → insight 무한 재생성(livelock).
    from shared.config import AGENT_KB_READ_BACKEND
    if AGENT_KB_READ_BACKEND == "postgres":
        pg_states = _load_insight_artifact_states_pg(keys)
        if pg_states is not None:
            return pg_states
        # PG 미가용 → 아래 MySQL fallback (cutover 미완 환경 안전망)
    if not mem_conn:
        return states
    conversation_ids = _global_fact_conversation_ids(include_shared=True)
    if not conversation_ids:
        return states
    cid_placeholders = ",".join(["%s"] * len(conversation_ids))
    key_placeholders = ",".join(["%s"] * len(keys))
    scope_clause, scope_params = _scope_filter_sql(_scope_candidates(FACT_SCOPE_COMMON))

    cur = mem_conn.cursor()
    try:
        cur.execute(
            f"""
SELECT
    e.FactKey,
    e.ConversationId,
    e.ScopeKey,
    COALESCE(t.TextContent, '') AS FactText,
    e.Weight,
    COALESCE(e.SourceType, '') AS SourceType,
    COALESCE(e.SourceRunId, '') AS SourceRunId,
    COALESCE(e.SourceSql, '') AS SourceSql
FROM AgentMemoryFactEntries e
LEFT JOIN AgentMemoryTexts t ON t.TextHash = e.TextHash
WHERE e.ConversationId IN ({cid_placeholders})
  AND e.FactKey IN ({key_placeholders}){scope_clause}
ORDER BY e.FactKey, e.Weight DESC, e.UpdatedAt DESC, e.Id DESC
            """,
            [*conversation_ids, *keys, *scope_params],
        )
        rows = cur.fetchall() or []
    except Exception as exc:
        _warn_insight_readback_failed("mysql_fact", exc)
        rows = []
    finally:
        cur.close()
    _apply_insight_fact_rows(states, rows)

    cur = mem_conn.cursor()
    try:
        cur.execute(
            f"""
SELECT
    d.FactKey,
    COALESCE(t.TextContent, '') AS DocText
FROM AgentMemoryRagDocuments d
LEFT JOIN AgentMemoryTexts t ON t.TextHash = d.TextHash
WHERE d.ConversationId IN ({cid_placeholders})
  AND d.FactKey IN ({key_placeholders}){scope_clause}
ORDER BY d.FactKey, d.Weight DESC, d.UpdatedAt DESC, d.Id DESC
            """,
            [*conversation_ids, *keys, *scope_params],
        )
        rows = cur.fetchall() or []
    except Exception as exc:
        _warn_insight_readback_failed("mysql_doc", exc)
        rows = []
    finally:
        cur.close()
    _apply_insight_doc_rows(states, rows)

    schema_object_map, table_object_map = _build_insight_object_maps(keys)

    # TASK-0220: object_key 매칭(PG 경로와 동일). 본 MySQL 경로는 cutover 로 DROP 된 dead path 지만
    # table_object_map.keys() 가 이제 object_key 문자열(튜플 아님)이라 언패킹/매칭을 정합 유지한다.
    if schema_object_map:
        cur = mem_conn.cursor()
        try:
            schema_placeholders = ",".join(["%s"] * len(schema_object_map))
            cur.execute(
                f"""
SELECT
    o.ObjectKey,
    COALESCE(t.TextContent, '') AS ObjectText
FROM AgentMemoryRagObjects o
LEFT JOIN AgentMemoryTexts t ON t.TextHash = o.TextHash
WHERE o.ConversationId IN ({cid_placeholders})
  AND o.ObjectType = 'schema'
  AND o.ObjectKey IN ({schema_placeholders}){scope_clause}
ORDER BY o.ObjectKey, o.Weight DESC, o.UpdatedAt DESC, o.Id DESC
                """,
                [*conversation_ids, *schema_object_map.keys(), *scope_params],
            )
            rows = cur.fetchall() or []
        except Exception as exc:
            _warn_insight_readback_failed("mysql_schema_obj", exc)
            rows = []
        finally:
            cur.close()
        _apply_insight_schema_object_rows(states, rows, schema_object_map)

    if table_object_map:
        cur = mem_conn.cursor()
        try:
            table_placeholders = ",".join(["%s"] * len(table_object_map))
            cur.execute(
                f"""
SELECT
    o.ObjectKey,
    COALESCE(t.TextContent, '') AS ObjectText
FROM AgentMemoryRagObjects o
LEFT JOIN AgentMemoryTexts t ON t.TextHash = o.TextHash
WHERE o.ConversationId IN ({cid_placeholders})
  AND o.ObjectType = 'table'
  AND o.ObjectKey IN ({table_placeholders}){scope_clause}
ORDER BY o.ObjectKey, o.Weight DESC, o.UpdatedAt DESC, o.Id DESC
                """,
                [*conversation_ids, *table_object_map.keys(), *scope_params],
            )
            rows = cur.fetchall() or []
        except Exception as exc:
            _warn_insight_readback_failed("mysql_table_obj", exc)
            rows = []
        finally:
            cur.close()
        _apply_insight_table_object_rows(states, rows, table_object_map)

    return states


def _insight_artifact_complete(state: dict[str, Any] | None) -> bool:
    info = state or {}
    return bool(
        info.get("has_fact")
        and info.get("has_text")
        and info.get("has_rag_document")
        and info.get("has_rag_object")
    )


def _insight_missing_parts(state: dict[str, Any] | None) -> list[str]:
    info = state or {}
    missing: list[str] = []
    if not info.get("has_fact"):
        missing.append("fact")
    if not info.get("has_text"):
        missing.append("text")
    if not info.get("has_rag_document"):
        missing.append("rag_document")
    if not info.get("has_rag_object"):
        missing.append("rag_object")
    return missing


def _detect_pending_insight_repairs(
    db_conn,
    mem_conn,
    schemas: list[str],
) -> dict[str, int]:
    report = {
        "pending_schema_repairs": 0,
        "pending_table_repairs": 0,
    }
    schema_names = [str(s or "").strip() for s in (schemas or [])]
    schema_names = [s for s in schema_names if s and not _is_system_schema(s)]
    if not db_conn or not mem_conn or not schema_names:
        return report

    schema_keys = [ds_fact_key("schema_insight", ds_object_suffix(schema)) for schema in schema_names]
    schema_states = _load_insight_artifact_states(mem_conn, schema_keys)
    for schema in schema_names:
        schema_key = ds_fact_key("schema_insight", ds_object_suffix(schema))
        if not _insight_artifact_complete(
            schema_states.get(schema_key, _empty_insight_artifact_state(schema_key))
        ):
            report["pending_schema_repairs"] += 1

    cur = db_conn.cursor()
    try:
        placeholders = ",".join(["%s"] * len(schema_names))
        cur.execute(
            f"""
SELECT TABLE_SCHEMA, TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA IN ({placeholders})
ORDER BY TABLE_SCHEMA, TABLE_NAME
            """,
            schema_names,
        )
        rows = cur.fetchall() or []
    except Exception:
        rows = []
    finally:
        cur.close()

    table_keys: list[str] = []
    for row in rows:
        if not row:
            continue
        schema_name = str(row[0] or "").strip()
        table_name = str(row[1] or "").strip()
        if not schema_name or not table_name:
            continue
        table_keys.append(ds_fact_key("table_insight", ds_object_suffix(schema_name, table_name)))

    if not table_keys:
        return report

    table_states = _load_insight_artifact_states(mem_conn, table_keys)
    for table_key in table_keys:
        if not _insight_artifact_complete(
            table_states.get(table_key, _empty_insight_artifact_state(table_key))
        ):
            report["pending_table_repairs"] += 1
    return report


def _build_insight_references(
    schema: str,
    table: str | None = None,
    col_names: list[str] | None = None,
    table_names: list[str] | None = None,
) -> list[str]:
    refs: list[str] = []
    schema_name = str(schema or "").strip()
    table_name = str(table or "").strip()
    if schema_name:
        refs.append(f"schema:{schema_name}")
    if table_name:
        refs.append(f"table:{schema_name}.{table_name}" if schema_name else f"table:{table_name}")
    max_candidates = max(1, int(AGENT_INSIGHT_ROUTE_LOG_MAX_CANDIDATES))
    if table_name:
        for col_name in col_names or []:
            name = str(col_name or "").strip()
            if not name:
                continue
            refs.append(
                f"column:{schema_name}.{table_name}.{name}"
                if schema_name
                else f"column:{table_name}.{name}"
            )
            if len(refs) >= 2 + max_candidates:
                break
    else:
        for hint in table_names or []:
            name = str(hint or "").strip()
            if not name:
                continue
            refs.append(f"table:{schema_name}.{name}" if schema_name else f"table:{name}")
            if len(refs) >= 1 + max_candidates:
                break
    return refs


def _trace_insight_worker_event(
    run_id: str | None,
    phase: str,
    schema: str,
    object_type: str,
    object_name: str,
    reason: str,
    action: str,
    referenced_objects: list[str] | None = None,
    result: str = "",
    duration_ms: float | None = None,
    error: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "timestamp": utc_now_iso(),
        "run_id": str(run_id or "").strip(),
        "phase": str(phase or "").strip(),
        "schema": str(schema or "").strip(),
        "object_type": str(object_type or "").strip(),
        "object_name": str(object_name or "").strip(),
        "reason": str(reason or "").strip(),
        "action": str(action or "").strip(),
        "referenced_objects": referenced_objects or [],
        "result": str(result or "").strip(),
        "duration_ms": round(float(duration_ms or 0.0), 2),
        "error": str(error or "").strip()[:500],
    }
    if extra:
        payload.update(extra)
    log_insight_route("insight_worker", payload)


def _repair_insight_artifacts_from_state(
    mem_conn,
    fact_key: str,
    state: dict[str, Any],
    run_id: str | None,
    schema: str,
    object_type: str,
    object_name: str,
    referenced_objects: list[str] | None = None,
) -> tuple[bool, dict[str, Any]]:
    current = dict(state or {})
    repair_text = str(current.get("repair_text") or current.get("fact_text") or "").strip()
    missing_parts = _insight_missing_parts(current)
    if not repair_text:
        _trace_insight_worker_event(
            run_id,
            "publish",
            schema,
            object_type,
            object_name,
            "artifact_missing",
            "repair_from_fact",
            referenced_objects=referenced_objects,
            result="unavailable",
            extra={"missing_parts": missing_parts},
        )
        return False, current
    started = time.perf_counter()
    try:
        _upsert_fact(
            mem_conn,
            str(current.get("conversation_id") or _insight_target_conversation_id()).strip()
            or _insight_target_conversation_id(),
            fact_key,
            repair_text,
            int(current.get("weight") or 4),
            scope_key=str(current.get("scope_key") or FACT_SCOPE_COMMON),
            source_type=str(current.get("source_type") or "schema_insight") or "schema_insight",
            source_run_id=str(current.get("source_run_id") or run_id or "").strip() or None,
            source_sql=str(current.get("source_sql") or "").strip() or None,
        )
        repaired = _load_insight_artifact_states(mem_conn, [fact_key]).get(
            fact_key, _empty_insight_artifact_state(fact_key)
        )
        complete = _insight_artifact_complete(repaired)
        _trace_insight_worker_event(
            run_id,
            "publish",
            schema,
            object_type,
            object_name,
            "artifact_missing",
            "repair_from_fact",
            referenced_objects=referenced_objects,
            result="ok" if complete else "partial_persist",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            extra={"missing_parts": _insight_missing_parts(repaired)},
        )
        return complete, repaired
    except Exception as exc:
        _trace_insight_worker_event(
            run_id,
            "publish",
            schema,
            object_type,
            object_name,
            "artifact_missing",
            "repair_from_fact",
            referenced_objects=referenced_objects,
            result="publish_failed",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            error=str(exc),
            extra={"missing_parts": missing_parts},
        )
        return False, current

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


# ── TASK-0305 (RC3): pending-repair 무진전 backoff ───────────────────────────
# 무경계 _detect_pending_insight_repairs 가 budget(15s)로 도달 못 하는 미완성 artifact tail 을
# pending 으로 영구 집계 → force_scan 이 매 8s tick 영구 latch → 도달가능 DB 의 무거운 fingerprint
# 스캔(수천 테이블)을 매 tick 반복하던 spin 을 유발했다. '직전 pending-only 스캔이 무진전(생성·복구
# 0)'이면 짧은 backoff 동안 pending-only 트리거를 억제한다(missing= 새 스키마는 영향 없음 — 즉시 스캔).
# 진전이 있으면 backoff 해제 → 건강한 시스템의 테이블 채움 처리량은 tick cadence 로 보존. backoff_until
# KV 는 per-scope(ds_scope_name) — 데이터소스별 독립. KV 부재 = 기존 동작(backoff 없음).
def _repair_backoff_active(mem_conn) -> bool:
    """pending-repair 무진전 backoff 활성 여부(backoff_until 이 미래면 True)."""
    if not mem_conn:
        return False
    try:
        raw = load_memory_kv(
            mem_conn, GLOBAL_CONVERSATION_ID,
            ds_scope_name("schema_instance_repair_backoff_until"),
        )
        if not raw:
            return False
        until = _parse_iso_time(str(raw))
        if not until:
            return False
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < until
    except Exception:
        return False


def _set_repair_backoff(mem_conn, backoff_sec: int) -> None:
    """pending-only 스캔이 무진전이면 backoff_until = now + backoff_sec(>=60s) 로 설정."""
    if not mem_conn:
        return
    try:
        until = datetime.now(timezone.utc) + timedelta(seconds=max(60, int(backoff_sec)))
        save_memory_kv(
            mem_conn, GLOBAL_CONVERSATION_ID,
            ds_scope_name("schema_instance_repair_backoff_until"),
            until.isoformat(),
        )
    except Exception:
        pass


def _clear_repair_backoff(mem_conn) -> None:
    """진전이 생기면(또는 missing 스캔) backoff 해제(빈 값 = 비활성)."""
    if not mem_conn:
        return
    try:
        save_memory_kv(
            mem_conn, GLOBAL_CONVERSATION_ID,
            ds_scope_name("schema_instance_repair_backoff_until"),
            "",
        )
    except Exception:
        pass


def _fk_raw_execute(conn, sql):
    """feature-0013: relationships.introspect_and_store 용 콜백 — db_conn 으로 FK SQL 실행.

    dialects.foreign_keys_outgoing(schema, table) 는 신뢰된 메타(information_schema/sys.foreign_keys)를
    f-string 보간한 단일 SELECT 다. (result_sets,) 튜플로 반환해 introspect_and_store 의
    `results, *_ = raw_execute(...)` 와 정합.
    """
    cur = conn.cursor()
    try:
        cur.execute(sql)
        cols = [d[0] for d in (cur.description or [])]
        rows = [list(r) for r in (cur.fetchall() or [])]
        return ([{"columns": cols, "rows": rows}],)
    finally:
        cur.close()


def _instance_scan_cursor_key() -> str:
    """instance-scan interval 커서 키 (rel-selfheal 적대 패널 B-F1).

    ds-단위 단일 커서는 MSSQL multi-DB 순회에서 같은 cycle 의 첫 DB 스탬프가 나머지 DB 의
    interval 스캔을 매번 가로채(항상 DB#1 만 획득), 정상상태의 DB#2..#N 은 rescan·관계
    유지보수(cadence 포함)가 영원히 미발화한다 — DB(catalog) 별로 커서를 분리한다.
    MySQL(active db 없음)은 기존 키 그대로(하위호환 — 기존 스탬프 유효).
    """
    key = ds_scope_name("schema_instance_scan_at")
    try:
        adb = get_active_database()
    except Exception:
        adb = None
    return f"{key}:db:{adb}" if adb else key


def _scan_instance_schema_insights(
    db_conn,
    mem_conn,
    schemas: list[str],
    run_id: str | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "scan_started": False,
        "schemas_evaluated": 0,
        "schemas_generated": 0,
        "schemas_repaired": 0,
        "tables_selected": 0,
        "tables_generated": 0,
        "tables_repaired": 0,
        "artifact_missing_selected": 0,
        "skipped_schemas": 0,
        "skipped_tables": 0,
        "deferred_tables": 0,
        "pending_schema_repairs": 0,
        "pending_table_repairs": 0,
        # TASK-0131 (#10): publish 실패(주로 LLM 호출 실패) 누적 — 사이클 status degrade 판정용.
        "publish_failed": 0,
        # insight-table-grouping (2026-07-03): 동일구조 그룹 전파 관측.
        #   insight_llm_calls = 실제 llm_table_insight 호출 수(대표만),
        #   tables_fanout     = LLM 없이 형제로 전파된 테이블 수(= 절약된 LLM 호출 수).
        "insight_llm_calls": 0,
        "tables_fanout": 0,
    }
    if not db_conn or not mem_conn or not AGENT_SCHEMA_INSTANCE_SCAN or not AGENT_SCHEMA_INSIGHT:
        return report
    if not LLM_API_KEY or OpenAI is None:
        return report
    candidates = [str(s or "").strip() for s in (schemas or [])]
    candidates = [s for s in candidates if s and not _is_system_schema(s)]
    if not candidates:
        return report
    existing_schema_insights = _load_existing_schema_insights(mem_conn)
    missing = [schema for schema in candidates if schema not in existing_schema_insights]
    seen = [schema for schema in candidates if schema in existing_schema_insights]
    force_scan = bool(missing)
    candidates = missing + seen
    max_schemas = int(AGENT_SCHEMA_INSTANCE_SCAN_MAX_SCHEMAS or 0)
    if max_schemas > 0 and candidates:
        pick_limit = min(max_schemas, len(candidates))
        offset_key = ds_scope_name("schema_instance_scan_schema_offset")
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
    pending_repairs = _detect_pending_insight_repairs(db_conn, mem_conn, candidates)
    report["pending_schema_repairs"] = int(pending_repairs.get("pending_schema_repairs", 0) or 0)
    report["pending_table_repairs"] = int(pending_repairs.get("pending_table_repairs", 0) or 0)
    # rel-selfheal 적대 패널 B-F1: instance-scan interval 커서를 DB(catalog) 별로 분리
    # (_instance_scan_cursor_key docstring 참조 — MSSQL multi-DB 의 DB#1 독점 차단).
    _scan_cursor_key = _instance_scan_cursor_key()
    # TASK-0305 (RC3): pending(미완성 artifact)만으로 트리거된 스캔인지 — 새 스키마(missing)는 항상 즉시.
    pending_only = bool(
        not missing
        and (report["pending_schema_repairs"] or report["pending_table_repairs"])
    )
    force_scan = bool(
        missing
        or report["pending_schema_repairs"]
        or report["pending_table_repairs"]
    )
    # TASK-0305 (RC3): 직전 pending-only 스캔이 무진전이면 backoff 동안 pending-only 트리거를 억제해
    # 매 tick spin 을 막는다. backoff 중이라도 missing(새 스키마)과 rescan interval 경과는 그대로 스캔.
    if pending_only and _repair_backoff_active(mem_conn):
        force_scan = bool(missing)  # missing 없으면 False → 아래 interval gate 로 위임
    if not force_scan:
        try:
            last_scan = load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, _scan_cursor_key)
            parsed = _parse_iso_time(str(last_scan)) if last_scan else None
            if parsed:
                elapsed = (datetime.now(timezone.utc) - parsed).total_seconds()
                if elapsed < max(5, AGENT_SCHEMA_INSTANCE_SCAN_EVERY_SEC):
                    return report
        except Exception:
            pass

    report["scan_started"] = True
    stored_schema_fps = _load_stored_fingerprints(mem_conn, "schema_fp:")
    stored_table_fps = _load_stored_fingerprints(mem_conn, "table_fp:")

    cur = db_conn.cursor()
    scan_start = time.perf_counter()
    budget_sec = max(5, int(AGENT_SCHEMA_INSTANCE_SCAN_BUDGET_SEC))
    table_seen_map = _load_existing_table_insight_map(mem_conn, candidates)
    schema_refresh_sec = int(AGENT_SCHEMA_INSIGHT_RESCAN_SEC or 0)
    table_refresh_sec = int(AGENT_TABLE_INSIGHT_RESCAN_SEC or 0)
    schema_refresh_map = _load_kv_prefix_map(mem_conn, GLOBAL_CONVERSATION_ID, "schema_insight_refresh_at:")
    table_refresh_map = _load_kv_prefix_map(mem_conn, GLOBAL_CONVERSATION_ID, "table_insight_refresh_at:")
    # rel-selfheal: 관계 유지보수(FK introspect·암묵 추론·프로브) 주기 cadence 상태 —
    # 스키마별 마지막 발화 시각(kv). 기존 트리거(구조변경/artifact 부재)만으로는 이미 스캔
    # 완료된 스키마에서 영원히 미발화(라이브 inferred 0건·프로브 0회)라 주기 재발화를 보완한다.
    rel_reinfer_sec = int(AGENT_RELATIONSHIP_REINFER_SEC or 0)
    rel_infer_map = _load_kv_prefix_map(mem_conn, GLOBAL_CONVERSATION_ID, "relationship_infer_at:")
    # insight-table-grouping (2026-07-03): 동일구조 그룹 상태(cycle 전역 — 스키마 간 KV/cache 공유).
    grouping_enabled = bool(AGENT_INSIGHT_TABLE_GROUPING_ENABLED)
    group_min = max(2, int(AGENT_INSIGHT_TABLE_GROUP_MIN_MEMBERS))
    fanout_max = max(0, int(AGENT_INSIGHT_TABLE_GROUP_FANOUT_MAX))
    group_insight_cache: dict[tuple, dict] = {}   # sig -> 대표 분석 dict (cycle 전역 — 스키마 간 재사용 OK)
    fanout_used = 0                               # 이번 cycle fan-out 한 테이블 수(fanout_max cycle 상한)
    # NOTE(리뷰 BUG1): fan-out 중복 방지 집합 `fanned_out_groups` 는 **스키마마다 리셋**한다(아래 루프 내).
    #   sig=(base_stem, fp) 가 스키마-무관이라 cycle 전역이면 구조·이름이 겹치는 두 번째 스키마의 fan-out 이
    #   통째로 skip 돼 기능이 무력화된다(멀티 DB 가 같은 샤드 템플릿을 공유하는 흔한 경우). members_of 는
    #   스키마별로 재구성되므로 dedupe 도 스키마 스코프여야 정합.
    try:
        for schema in candidates:
            if time.perf_counter() - scan_start > budget_sec:
                break
            _touch_worker_heartbeat_progress(mem_conn)  # insight-heartbeat-liveness: 스키마 진행 중 heartbeat
            try:
                report["schemas_evaluated"] = int(report.get("schemas_evaluated", 0)) + 1
                # 스키마 핑거프린트 계산 (테이블 목록 기반)
                current_schema_fp = _compute_schema_fingerprint(db_conn, schema)
                schema_fp_key = ds_fact_key("schema_fp", ds_object_suffix(schema))
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
                schema_key = ds_fact_key("schema_insight", ds_object_suffix(schema))
                schema_refresh_key = ds_fact_key("schema_insight_refresh_at", ds_object_suffix(schema))
                schema_state = _load_insight_artifact_states(mem_conn, [schema_key]).get(
                    schema_key, _empty_insight_artifact_state(schema_key)
                )
                schema_artifact_missing = not _insight_artifact_complete(schema_state)
                schema_refresh_due = _is_refresh_due(
                    schema_refresh_map, schema_refresh_key, schema_refresh_sec
                )
                schema_has_stored_fp = bool(stored_schema_fp)

                # feature-0013 Phase 2 + rel-selfheal: FK 관계 introspect → table_relationships
                # (source='fk_introspect'). 발화 = 스키마 구조 변경/신규 **또는 주기 cadence 경과**
                # (AGENT_RELATIONSHIP_REINFER_SEC — 기존 조건만으로는 이미 스캔된 스키마에서 영원히
                # 미발화). 빈도 제한으로 8초 루프 부하 억제.
                # 전부 guarded — 어떤 예외도 insight 스캔을 차단하지 않는다(PG 미가용 시 no-op).
                rel_infer_key = ds_fact_key("relationship_infer_at", ds_object_suffix(schema))
                rel_reinfer_due = bool(
                    rel_reinfer_sec > 0
                    and _is_refresh_due(rel_infer_map, rel_infer_key, rel_reinfer_sec)
                )
                rel_maintenance_due = bool(
                    schema_structure_changed or schema_artifact_missing or rel_reinfer_due
                )
                # 저장용 스키마-slot: MSSQL 은 현재 순회 중인 DB(catalog)명 — 그래프 Table 키
                # (`db.table`)·column_descriptions(schema_name=DB명) 규약과 정합. 실 스키마('dbo')
                # 리터럴 저장은 AGE 투영에서 실 테이블과 연결되지 않는 고아 엣지를 만든다.
                # 질의는 여전히 실 스키마(schema)로 수행한다(store/query 분리).
                _rel_store_schema = schema
                _rel_db_scope = None
                try:
                    if _dialects.active().name == "mssql":
                        _rel_db_scope = get_active_database()
                        _rel_store_schema = _rel_db_scope or schema
                except Exception:
                    pass
                if (AGENT_RELATIONSHIP_INTROSPECT_ENABLED
                        and rel_maintenance_due
                        and all_table_names):
                    try:
                        from . import relationships as _rel
                        _rel_scope = get_active_datasource()
                        _n_rel = _rel.introspect_and_store(
                            db_conn, _dialects.active(), schema, all_table_names,
                            kb_conn=None, scope_key=_rel_scope,
                            datasource_key=str(_rel_scope or ""), source_run_id=run_id,
                            raw_execute=_fk_raw_execute,
                            store_schema=_rel_store_schema,
                        )
                        report["relationships_introspected"] = int(
                            report.get("relationships_introspected", 0)) + int(_n_rel or 0)
                    except Exception:
                        # B-F7: 이 cycle 이 고친 결함(D1b)이 "조용한 정지" 였다 — 같은 클래스의
                        # 미래 회귀가 또 침묵하지 않도록 경고 1줄은 남긴다(스캔은 계속 비차단).
                        logging.getLogger("insight").warning(
                            "relationship_introspect_failed schema=%s", schema, exc_info=True)

                # feature-0016 implicit-edges: FK 로 확인 안 되는 **암묵 관계**를 명명 규칙으로
                # 추론(source='inferred', candidate)한 뒤, candidate 를 **실데이터 겹침 프로브**로
                # 검증해 강화/감쇠한다("항상 올바른지 파악"). 발화 = 구조 변경/신규 **또는 주기
                # cadence**(rel-selfheal — rel_maintenance_due, introspect 블록과 동일 게이트).
                # 전부 guarded — insight 스캔을 절대 차단하지 않는다.
                if (AGENT_RELATIONSHIP_INFERENCE_ENABLED
                        and rel_maintenance_due
                        and all_table_names):
                    try:
                        from . import relationships as _rel
                        _infer_scope = get_active_datasource()
                        # 스키마의 테이블별 컬럼 맵(추론 입력). information_schema.COLUMNS = MySQL·MSSQL 공통.
                        _tc = {}
                        _ccur = db_conn.cursor()
                        try:
                            _ccur.execute(
                                "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
                                "WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME, ORDINAL_POSITION",
                                (schema,),
                            )
                            for _t, _c in (_ccur.fetchall() or []):
                                if _t and _c:
                                    _tc.setdefault(str(_t), []).append(str(_c))
                        finally:
                            _ccur.close()
                        if _tc:
                            # 저장 라벨 = _rel_store_schema (MSSQL=DB명 — 그래프 키 정합, store/query 분리)
                            _n_inf = _rel.store_inferred_relationships(
                                None, _infer_scope, _rel_store_schema, _tc,
                                datasource_key=str(_infer_scope or ""), source_run_id=run_id,
                                cap=AGENT_RELATIONSHIP_INFER_CAP)
                            report["relationships_inferred"] = int(
                                report.get("relationships_inferred", 0)) + int(_n_inf or 0)
                        # 능동 프로브(실데이터 겹침 검증) — 별 토글. 운영 DB read-only, cap+timeout 으로 부하 제한.
                        # db_scope(MSSQL): 현재 연결 DB 의 후보만 프로브 — 다른 DB 후보를 이 연결에서
                        # 실행하면 동명 테이블 오검증/불필요 실패(rel-selfheal).
                        if AGENT_RELATIONSHIP_PROBE_ENABLED:
                            _pr = _rel.probe_and_reinforce(
                                db_conn, _dialects.active(), _infer_scope,
                                kb_conn=None, raw_execute=_fk_raw_execute,
                                sample=AGENT_RELATIONSHIP_PROBE_SAMPLE,
                                cap=AGENT_RELATIONSHIP_PROBE_CAP,
                                timeout_ms=AGENT_RELATIONSHIP_PROBE_TIMEOUT_MS,
                                db_scope=_rel_db_scope)
                            # neutral/failed 포함(B-F11) — neutral 위주 사이클이 telemetry 상
                            # 무활동으로 보이지 않게.
                            for _k in ("probed", "positive", "negative", "neutral", "failed"):
                                _rk = "relationships_probe_" + _k
                                report[_rk] = int(report.get(_rk, 0)) + int(_pr.get(_k, 0))
                    except Exception:
                        # B-F7: 조용한 정지 재발 방지 — 경고 1줄(비차단 유지).
                        logging.getLogger("insight").warning(
                            "relationship_infer_probe_failed schema=%s", schema, exc_info=True)

                # feature-0016 graph-funcproc(ADR-016): 함수·프로시저 introspect → routine_objects.
                # 발화 게이트 = rel_maintenance_due(관계 유지보수와 동일 cadence). 정의 파싱으로
                # 참조 테이블(read/write)을 추출해 그래프 ROUTINE_USES 투영 입력으로 쓴다.
                # 전부 guarded — insight 스캔을 절대 차단하지 않는다(B-F7: 실패는 경고 1줄).
                if AGENT_ROUTINE_INTROSPECT_ENABLED and rel_maintenance_due:
                    try:
                        from . import routines as _routines
                        _rt_scope = get_active_datasource()
                        _n_rt = _routines.introspect_and_store(
                            db_conn, schema, all_table_names,
                            kb_conn=None, scope_key=_rt_scope,
                            datasource_key=str(_rt_scope or ""), source_run_id=run_id,
                            store_schema=_rel_store_schema,
                            cap=AGENT_ROUTINE_INTROSPECT_CAP)
                        report["routines_introspected"] = int(
                            report.get("routines_introspected", 0)) + int(_n_rt or 0)
                    except Exception:
                        logging.getLogger("insight").warning(
                            "routine_introspect_failed schema=%s", schema, exc_info=True)

                # rel-selfheal cadence 스탬프 — introspect/추론/routine 어느 쪽이든 이번 사이클에
                # 유지보수를 수행했으면 기록(전부 off 면 미기록 → 활성화 시 즉시 발화).
                # graph-funcproc(§18.8 패널 MINOR): routine 훅은 all_table_names 없이도(테이블 0·
                # 프로시저만 있는 스키마) 발화하므로, 스탬프도 같은 조건으로 남겨야 매 cycle
                # ROUTINES/PARAMETERS 재조회 spin 이 없다 — 게이트/스탬프 조건 정합.
                if (rel_maintenance_due
                        and ((AGENT_RELATIONSHIP_INTROSPECT_ENABLED
                              or AGENT_RELATIONSHIP_INFERENCE_ENABLED)
                             and all_table_names
                             or AGENT_ROUTINE_INTROSPECT_ENABLED)):
                    try:
                        _rel_now = utc_now_iso()
                        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, rel_infer_key, _rel_now)
                        rel_infer_map[rel_infer_key] = _rel_now
                    except Exception:
                        pass

                schema_reason = ""
                if schema_artifact_missing:
                    schema_reason = "artifact_missing"
                    report["artifact_missing_selected"] = int(
                        report.get("artifact_missing_selected", 0)
                    ) + 1
                elif schema_structure_changed:
                    schema_reason = "fingerprint_changed"
                elif schema_refresh_due and not schema_has_stored_fp:
                    schema_reason = "refresh_due"

                schema_refs = _build_insight_references(
                    schema, table_names=all_table_names[: max(1, int(AGENT_INSIGHT_ROUTE_LOG_MAX_CANDIDATES))]
                )
                if schema_reason == "artifact_missing":
                    repaired, schema_state = _repair_insight_artifacts_from_state(
                        mem_conn,
                        schema_key,
                        schema_state,
                        run_id,
                        schema,
                        "schema",
                        schema,
                        referenced_objects=schema_refs,
                    )
                    if repaired:
                        followup_reason = ""
                        if schema_structure_changed:
                            followup_reason = "fingerprint_changed"
                        elif schema_refresh_due and not schema_has_stored_fp:
                            followup_reason = "refresh_due"
                        if followup_reason:
                            schema_reason = followup_reason
                        else:
                            _mark_refresh_kv(mem_conn, schema_refresh_map, schema_refresh_key)
                            _save_fingerprint(mem_conn, schema_fp_key, current_schema_fp)
                            stored_schema_fps[schema_fp_key] = current_schema_fp
                            existing_schema_insights.add(schema)
                            report["schemas_repaired"] = int(report.get("schemas_repaired", 0)) + 1
                            schema_reason = ""

                if schema_reason:
                    schema_started = time.perf_counter()
                    schema_payload = {
                        "schema": schema,
                        "columns": col_names[: max(1, AGENT_SCHEMA_INSIGHT_MAX_COLS)],
                        "table_hints": [],
                    }
                    schema_error = ""
                    schema_insight = None
                    try:
                        schema_insight = llm_schema_insight(schema_payload)
                    except Exception as exc:
                        schema_error = str(exc)
                    schema_text = _format_schema_insight_text(
                        schema,
                        schema_insight if isinstance(schema_insight, dict) else None,
                        col_names=col_names,
                    )
                    publish_attempted = False
                    publish_skip_reason = ""
                    if (
                        not schema_error
                        and schema_text
                        and _should_publish_global_fact(schema_key, "schema_insight", 4, schema_text)
                    ):
                        _publish_fact(
                            mem_conn,
                            _insight_target_conversation_id(),
                            schema_key,
                            schema_text,
                            4,
                            scope_key=FACT_SCOPE_COMMON,
                            source_type="schema_insight",
                            source_run_id=run_id,
                            source_sql="",
                            source_meta=schema_insight if isinstance(schema_insight, dict) else None,
                        )
                        publish_attempted = True
                    elif schema_error:
                        publish_skip_reason = "llm_error"
                    elif not isinstance(schema_insight, dict):
                        publish_skip_reason = "invalid_response"
                    elif not schema_text:
                        publish_skip_reason = "empty_text"
                    else:
                        publish_skip_reason = "publish_filtered"
                    verified_schema_state = _load_insight_artifact_states(mem_conn, [schema_key]).get(
                        schema_key, _empty_insight_artifact_state(schema_key)
                    )
                    schema_complete = _insight_artifact_complete(verified_schema_state)
                    result = "ok" if schema_complete else "partial_persist"
                    if schema_error:
                        result = "publish_failed"
                        report["publish_failed"] = int(report.get("publish_failed", 0)) + 1
                    _trace_insight_worker_event(
                        run_id,
                        "publish",
                        schema,
                        "schema",
                        schema,
                        schema_reason,
                        "generate_insight",
                        referenced_objects=schema_refs,
                        result=result,
                        duration_ms=(time.perf_counter() - schema_started) * 1000.0,
                        error=schema_error,
                        extra={
                            "missing_parts": _insight_missing_parts(verified_schema_state),
                            "publish_attempted": bool(publish_attempted),
                            "publish_skip_reason": publish_skip_reason,
                        },
                    )
                    _trace_insight_worker_event(
                        run_id,
                        "verify",
                        schema,
                        "schema",
                        schema,
                        schema_reason,
                        "verify_persist",
                        referenced_objects=schema_refs,
                        result="ok" if schema_complete else "partial_persist",
                        extra={"missing_parts": _insight_missing_parts(verified_schema_state)},
                    )
                    if schema_complete:
                        _mark_refresh_kv(mem_conn, schema_refresh_map, schema_refresh_key)
                        _save_fingerprint(mem_conn, schema_fp_key, current_schema_fp)
                        stored_schema_fps[schema_fp_key] = current_schema_fp
                        existing_schema_insights.add(schema)
                        report["schemas_generated"] = int(report.get("schemas_generated", 0)) + 1
                else:
                    report["skipped_schemas"] = int(report.get("skipped_schemas", 0)) + 1

                offset_key = ds_scope_name(f"schema_instance_scan_offset:{schema}")
                batch = max(1, int(AGENT_SCHEMA_INSTANCE_SCAN_TABLE_LIMIT))
                if run_id == "init-memory":
                    batch = min(batch, 2)
                if not all_table_names:
                    try:
                        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, offset_key, "0")
                    except Exception:
                        pass
                    continue

                # 테이블 핑거프린트를 배치로 계산
                current_table_fps = _compute_table_fingerprints_batch(db_conn, schema, all_table_names)

                table_keys = [ds_fact_key("table_insight", ds_object_suffix(schema, name)) for name in all_table_names]
                artifact_states = _load_insight_artifact_states(mem_conn, table_keys)
                artifact_missing_tables: list[str] = []
                changed_tables: list[str] = []
                refresh_due_tables: list[str] = []
                reason_map: dict[str, str] = {}
                for tname in all_table_names:
                    table_key = ds_fact_key("table_insight", ds_object_suffix(schema, tname))
                    state = artifact_states.get(table_key, _empty_insight_artifact_state(table_key))
                    tfp_key_chk = ds_fact_key("table_fp", ds_object_suffix(schema, tname))
                    has_stored_tfp = bool(stored_table_fps.get(tfp_key_chk, ""))
                    current_tfp = current_table_fps.get(tname, "")
                    table_refresh_key = ds_fact_key("table_insight_refresh_at", ds_object_suffix(schema, tname))
                    table_refresh_due = _is_refresh_due(
                        table_refresh_map,
                        table_refresh_key,
                        table_refresh_sec,
                    )
                    if not _insight_artifact_complete(state):
                        artifact_missing_tables.append(tname)
                        reason_map[tname] = "artifact_missing"
                    elif current_tfp != stored_table_fps.get(tfp_key_chk, ""):
                        changed_tables.append(tname)
                        reason_map[tname] = "fingerprint_changed"
                    elif (not has_stored_tfp) and table_refresh_due:
                        refresh_due_tables.append(tname)
                        reason_map[tname] = "refresh_due"

                ready_total = len(artifact_missing_tables) + len(changed_tables) + len(refresh_due_tables)
                report["skipped_tables"] = int(report.get("skipped_tables", 0)) + max(
                    0, len(all_table_names) - ready_total
                )

                try:
                    offset = int(load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, offset_key) or 0)
                except Exception:
                    offset = 0
                if offset < 0:
                    offset = 0
                selected_tables: list[str] = []
                primary_len = 0
                primary_selected = 0
                if artifact_missing_tables:
                    rotated_missing = _rotate_list(artifact_missing_tables, offset)
                    selected_tables.extend(rotated_missing[:batch])
                    primary_len = len(artifact_missing_tables)
                    primary_selected = min(len(selected_tables), batch)
                    if len(selected_tables) < batch and changed_tables:
                        selected_tables.extend(changed_tables[: batch - len(selected_tables)])
                    if len(selected_tables) < batch and refresh_due_tables:
                        selected_tables.extend(refresh_due_tables[: batch - len(selected_tables)])
                elif changed_tables:
                    rotated_changed = _rotate_list(changed_tables, offset)
                    selected_tables.extend(rotated_changed[:batch])
                    primary_len = len(changed_tables)
                    primary_selected = min(len(selected_tables), batch)
                    if len(selected_tables) < batch and refresh_due_tables:
                        selected_tables.extend(refresh_due_tables[: batch - len(selected_tables)])
                elif refresh_due_tables:
                    rotated_refresh = _rotate_list(refresh_due_tables, offset)
                    selected_tables.extend(rotated_refresh[:batch])
                    primary_len = len(refresh_due_tables)
                    primary_selected = min(len(selected_tables), batch)
                else:
                    try:
                        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, offset_key, "0")
                    except Exception:
                        pass
                    continue
                report["tables_selected"] = int(report.get("tables_selected", 0)) + len(selected_tables)
                selected_set = set(selected_tables)
                deferred_tables = [
                    table_name
                    for table_name in (artifact_missing_tables + changed_tables + refresh_due_tables)
                    if table_name not in selected_set
                ]
                if deferred_tables:
                    report["deferred_tables"] = int(report.get("deferred_tables", 0)) + len(deferred_tables)
                    _trace_insight_worker_event(
                        run_id,
                        "table_scan",
                        schema,
                        "schema",
                        schema,
                        "limit_exceeded",
                        "defer",
                        referenced_objects=_build_insight_references(
                            schema, table_names=deferred_tables[: max(1, int(AGENT_INSIGHT_ROUTE_LOG_MAX_CANDIDATES))]
                        ),
                        result=f"deferred:{len(deferred_tables)}",
                    )
                table_cols: dict[str, list[tuple[str, str]]] = {}
                if selected_tables:
                    placeholders = ",".join(["%s"] * len(selected_tables))
                    cur.execute(
                        f"""
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({placeholders})
ORDER BY TABLE_NAME, ORDINAL_POSITION
                        """,
                        [schema] + selected_tables,
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
                # insight-table-grouping: 스키마 내 (base_stem, fp) 그룹 서명 + 이번 cycle ready 집합.
                if grouping_enabled:
                    group_sig_of, members_of = _build_table_groups(all_table_names, current_table_fps)
                else:
                    group_sig_of, members_of = {}, {}
                ready_all = set(artifact_missing_tables) | set(changed_tables) | set(refresh_due_tables)
                processed_this_cycle: set = set()   # 이번 스키마에서 이미 발행(대표/전파)한 테이블
                fanned_out_groups: set = set()      # (리뷰 BUG1) 이번 스키마에서 이미 fan-out 한 그룹 — 스키마 스코프
                for table in selected_tables:
                    if time.perf_counter() - scan_start > budget_sec:
                        break
                    if table in processed_this_cycle:
                        continue                    # 앞선 그룹 대표의 fan-out 이 이미 발행함
                    _touch_worker_heartbeat_progress(mem_conn)  # insight-heartbeat-liveness: 테이블 진행 중 heartbeat
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
                    table_key = ds_fact_key("table_insight", ds_object_suffix(schema, table))
                    table_reason = reason_map.get(table, "artifact_missing")
                    table_refs = _build_insight_references(
                        schema,
                        table=table,
                        col_names=col_name_list,
                    )
                    table_state = artifact_states.get(
                        table_key, _empty_insight_artifact_state(table_key)
                    )
                    if table_reason == "artifact_missing":
                        report["artifact_missing_selected"] = int(
                            report.get("artifact_missing_selected", 0)
                        ) + 1
                        repaired, repaired_state = _repair_insight_artifacts_from_state(
                            mem_conn,
                            table_key,
                            table_state,
                            run_id,
                            schema,
                            "table",
                            table,
                            referenced_objects=table_refs,
                        )
                        if repaired:
                            artifact_states[table_key] = repaired_state
                            current_tfp = current_table_fps.get(table, "")
                            tfp_key = ds_fact_key("table_fp", ds_object_suffix(schema, table))
                            has_stored_tfp = bool(stored_table_fps.get(tfp_key, ""))
                            followup_reason = ""
                            if current_tfp != stored_table_fps.get(tfp_key, ""):
                                followup_reason = "fingerprint_changed"
                            elif (not has_stored_tfp) and _is_refresh_due(
                                table_refresh_map,
                                ds_fact_key("table_insight_refresh_at", ds_object_suffix(schema, table)),
                                table_refresh_sec,
                            ):
                                followup_reason = "refresh_due"
                            if followup_reason:
                                table_reason = followup_reason
                            else:
                                table_refresh_key = ds_fact_key("table_insight_refresh_at", ds_object_suffix(schema, table))
                                _mark_refresh_kv(mem_conn, table_refresh_map, table_refresh_key)
                                if current_tfp:
                                    _save_fingerprint(mem_conn, tfp_key, current_tfp)
                                    stored_table_fps[tfp_key] = current_tfp
                                report["tables_repaired"] = int(report.get("tables_repaired", 0)) + 1
                                table_seen_map.setdefault(schema, set()).add(table)
                                # insight-table-grouping(리뷰 BUG2): repair 로 마감한 테이블도 이번 cycle
                                #   처리 완료로 표시 — 같은 그룹 형제의 fan-out 이 이 테이블 고유 insight 를
                                #   그룹 일반 insight 로 덮어쓰거나(clobber) 이중 카운트하지 않게 한다.
                                processed_this_cycle.add(table)
                                continue
                    sig = group_sig_of.get(table)
                    grp_members = members_of.get(sig) if sig is not None else None
                    grp_size = len(grp_members) if grp_members else 0
                    # insight-table-grouping(P1/리뷰): 그룹 대표는 개별 샤드명이 아니라 **family 패턴명**
                    #   (base_stem + "_*")으로 LLM 분석한다 — 분석문(summary/domain)이 특정 날짜·번호에
                    #   묶이지 않고 일반 분류가 되어, 형제에게 전파해도 "그 날짜" 오기재가 없다(사용자 "일반적
                    #   분류" 의도 정합). fact 키·prefix·참조는 실제 테이블명을 유지 → grounding 무회귀.
                    #   그룹 아님(sig None)이면 실제 이름 그대로 분석.
                    payload_table = (str(sig[0]) + "_*") if sig is not None else table
                    table_payload = {
                        "schema": schema,
                        "table": payload_table,
                        "columns": cols_payload[: max(1, int(AGENT_TABLE_INSIGHT_MAX_COLS))],
                    }
                    table_refresh_key = ds_fact_key("table_insight_refresh_at", ds_object_suffix(schema, table))
                    # 그룹 대표 분석 확보 순서 — cycle cache → KV 상속 → LLM. 동일구조(같은 fp+base_stem)
                    #   형제는 대표 분석 dict 를 재사용해 LLM 을 태우지 않는다.
                    table_error = ""
                    table_insight = None
                    insight_via = "llm"
                    if sig is not None and sig in group_insight_cache:
                        table_insight = group_insight_cache[sig]          # 같은 cycle 대표 재사용
                        insight_via = "group_cache"
                    else:
                        kv_insight = _load_group_insight_kv(mem_conn, sig) if sig is not None else None
                        if isinstance(kv_insight, dict):
                            table_insight = kv_insight                    # 이전 cycle 대표 상속(LLM 0)
                            insight_via = "kv_inherit"
                            if sig is not None:
                                group_insight_cache[sig] = kv_insight
                        else:
                            try:
                                table_insight = llm_table_insight(table_payload)
                            except Exception as exc:
                                table_error = str(exc)
                            report["insight_llm_calls"] = int(report.get("insight_llm_calls", 0)) + 1
                    family = None
                    if sig is not None and grp_size >= group_min:
                        family = {"base_stem": sig[0], "fingerprint": sig[1],
                                  "members": grp_size, "via": insight_via}
                    current_tfp = current_table_fps.get(table, "")
                    table_complete = _publish_table_insight(
                        mem_conn, run_id, schema, table, table_insight, table_error, col_name_list,
                        table_key, table_refs, table_reason, table_refresh_key,
                        current_tfp, stored_table_fps, table_refresh_map, report,
                        insight_via=insight_via, family=family,
                    )
                    # insight-table-grouping(P2/리뷰): 갓 LLM 분석한 대표 dict 는 **발행이 실제로 완료된
                    #   경우에만** cache/KV 에 저장한다 — 렌더/발행에 실패하는 malformed dict 가 KV 에 영속돼
                    #   매 cycle 같은 스키마를 재크래시(persistent wedge)하는 것을 차단. 상속/캐시 유래는 검증됨.
                    if (insight_via == "llm" and table_complete and sig is not None
                            and isinstance(table_insight, dict)):
                        group_insight_cache[sig] = table_insight
                        _save_group_insight_kv(mem_conn, sig, table_insight)
                    processed_this_cycle.add(table)
                    if table_complete:
                        table_seen_map.setdefault(schema, set()).add(table)
                        report["tables_generated"] = int(report.get("tables_generated", 0)) + 1
                        # ── fan-out: 같은 그룹의 나머지 ready 형제에게 LLM 없이 대표 분석 전파 ──
                        #   같은 cycle 에 대표를 확보한 그룹만(대표 분석 dict 재사용), ready(미완/변경/refresh)
                        #   형제에게만, fanout_max·budget_sec 이중 상한 내에서 전파한다.
                        if (grouping_enabled and grp_members and grp_size >= group_min
                                and isinstance(table_insight, dict) and sig not in fanned_out_groups):
                            fanned_out_groups.add(sig)
                            fam_fanout = {"base_stem": sig[0], "fingerprint": sig[1],
                                          "members": grp_size, "via": "fanout"}
                            for m in grp_members:
                                if fanout_used >= fanout_max:
                                    break
                                if time.perf_counter() - scan_start > budget_sec:
                                    break
                                if m == table or m in processed_this_cycle or m not in ready_all:
                                    continue
                                processed_this_cycle.add(m)
                                m_key = ds_fact_key("table_insight", ds_object_suffix(schema, m))
                                m_refs = _build_insight_references(schema, table=m, col_names=col_name_list)
                                m_refresh_key = ds_fact_key("table_insight_refresh_at", ds_object_suffix(schema, m))
                                m_tfp = current_table_fps.get(m, "")
                                m_complete = _publish_table_insight(
                                    mem_conn, run_id, schema, m, table_insight, "", col_name_list,
                                    m_key, m_refs, "grouped_fanout", m_refresh_key,
                                    m_tfp, stored_table_fps, table_refresh_map, report,
                                    insight_via="fanout", family=fam_fanout,
                                )
                                if m_complete:
                                    table_seen_map.setdefault(schema, set()).add(m)
                                    report["tables_fanout"] = int(report.get("tables_fanout", 0)) + 1
                                    fanout_used += 1
                if primary_len > 0:
                    step = primary_selected if primary_selected > 0 else 1
                    new_offset = (offset + max(1, step)) % primary_len
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
    try:
        if report.get("scan_started"):
            save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, _scan_cursor_key, utc_now_iso())
            # TASK-0305 (RC3): 진전 기반 backoff 갱신. 생성·복구가 1건이라도 있으면(또는 missing 스캔)
            # backoff 해제 → 건강한 처리량 tick cadence 보존. pending-only 스캔이 무진전이면 backoff 설정
            # → 도달 못 하는 미완성 tail 의 매-tick spin 차단(rescan interval 동안 pending-only 억제).
            made_progress = (
                int(report.get("schemas_generated", 0) or 0)
                + int(report.get("schemas_repaired", 0) or 0)
                + int(report.get("tables_generated", 0) or 0)
                + int(report.get("tables_repaired", 0) or 0)
                # insight-table-grouping: LLM 없이 형제로 전파한 것도 진전 — fan-out-only cycle 이
                #   무진전으로 오판돼 pending-only backoff 로 억제되지 않게 한다.
                + int(report.get("tables_fanout", 0) or 0)
            ) > 0
            if made_progress or missing:
                _clear_repair_backoff(mem_conn)
            elif pending_only:
                _set_repair_backoff(mem_conn, AGENT_SCHEMA_INSIGHT_RESCAN_SEC)
    except Exception:
        pass
    return report


# insight-heartbeat-liveness(2026-07-03): 긴 cycle(대량 테이블 LLM 생성) 동안 heartbeat 를 진행-중에도
# throttle 갱신하기 위한 monotonic 커서. healthcheck_insight_worker.py(age ≤ 180s)·_is_insight_worker_
# heartbeat_fresh 가 insight_worker_last_cycle_at 을 cycle **완료 시각**으로만 보던 탓에, claude 로 수천
# 테이블을 생성하는 9분+ cycle 이 heartbeat stale → **unhealthy false-negative** 로 오판되던 것을 해소.
_LAST_WORKER_HB_MONO = [0.0]


def _touch_worker_heartbeat_progress(mem_conn, *, min_interval_sec: float = 30.0) -> None:
    """cycle 진행 중(스키마·테이블 순회)에 insight_worker_last_cycle_at heartbeat 를 throttle 갱신.

    healthcheck 가 긴 cycle 을 죽은 것으로 오판(unhealthy)하던 false-negative 를 없앤다. **진짜 hang**
    (생성 자체가 멈춤)이면 이 호출 경로가 함께 멈춰 heartbeat 가 stale→unhealthy 로 감지되므로 hang
    탐지 의도(TASK-0129/0130)는 보존된다. status(insight_worker_last_status)는 미변경 — cycle 완료 시
    run_insight_cycle finally 가 확정하고, 본 갱신은 liveness(age)만 전진시킨다. 실패는 삼킨다(비차단)."""
    if not mem_conn:
        return
    try:
        now = time.monotonic()
        if now - _LAST_WORKER_HB_MONO[0] < max(1.0, float(min_interval_sec)):
            return
        _LAST_WORKER_HB_MONO[0] = now
        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_cycle_at", utc_now_iso())
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


def _insight_readback_degraded() -> bool:
    """read 정본(PG)이 닿지 않으면 True — 그 상태에선 생성을 멈춰야 한다.

    cutover 이후 insight read-back(artifact 검증·fingerprint 맵)의 정본은 PG다.
    read backend 가 postgres 인데 PG 가 부재하면 read-back 이 (DROP 된) MySQL fallback
    으로 떨어져 모든 artifact/fingerprint 가 missing/changed 로 오판 → 매 tick 무의미한
    재생성(과거 livelock 의 동력)을 반복한다. 이 함수가 True 면 cycle 은 생성을 skip 하고
    loop 는 길게 backoff 한다. MySQL 모드(postgres 미사용)면 read-back 이 live mem_conn
    을 쓰므로 불일치가 없어 False."""
    from shared.config import AGENT_KB_READ_BACKEND
    try:
        from .runtime_backend import AGENT_RUNTIME_READ_BACKEND
    except Exception:
        AGENT_RUNTIME_READ_BACKEND = ""
    pg_mode = (AGENT_KB_READ_BACKEND == "postgres") or (
        AGENT_RUNTIME_READ_BACKEND == "postgres"
    )
    if not pg_mode:
        return False
    if not _pg_available():
        return True
    # 실제 연결 probe — 서버 down 시 _pg_available()(env/드라이버만 검사)만으론 못 잡는다.
    conn = None
    try:
        conn = _pg_connect_ro()
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1")
            cur.fetchone()
        finally:
            cur.close()
        return False
    except Exception:
        return True
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _discover_mssql_databases(mem_conn, ds_key: str, ds_coords: dict | None) -> list[str]:
    """TASK-0220: MSSQL datasource 가 스캔할 database(catalog) 목록을 발견한다.

    발견 소스는 **제품 등록 DB 목록**(`WebProductDatabases.SchemaName` — MSSQL 에선 DB명, TASK-0206).
    `sys.databases` 열거는 RO 로그인이 특정 DB 에만 GRANT 되어 권한거부/노이즈 + 비용 폭증이라 부적합.
    이 datasource(라벨 또는 scope_key)에 바인딩된 제품들이 실제 접근하는 DB 합집합만 스캔 → 엔드포인트
    매칭 대상과 1:1 정합. default_db 가 있으면 합집합에 포함(미등록이어도 기본 스캔).
    반환은 소문자 정규화·중복제거된 DB명 목록(빈 목록이면 스캔 skip 신호).
    """
    dbs: list[str] = []
    seen: set[str] = set()
    # 1) 제품 등록 DB (이 datasource 를 쓰는 모든 제품의 SchemaName 합집합)
    #    TASK-0228 (1:N): primary(WebProducts.DatasourceKey) + join 바인딩(WebProductDatasources) 양쪽.
    #    또한 접근DB 가 datasource 차원으로 격리됐으면(WebProductDatabases.DatasourceKey) 이 datasource 의
    #    행만 본다 — 다른 datasource 의 DB 가 이 datasource 스캔에 섞이는 것 차단. (컬럼 부재 시 폴백.)
    if mem_conn is not None and ds_key:
        dk = str(ds_key).strip().lower()
        # 우선 datasource-차원 격리 쿼리(WebProductDatabases.DatasourceKey 매칭) 시도.
        _queries = [
            (
                "SELECT DISTINCT pd.SchemaName FROM WebProductDatabases pd "
                "WHERE LOWER(pd.DatasourceKey) = %s",
                (dk,),
            ),
            # 폴백: 차원 컬럼 부재(미이전) → product 바인딩(primary + join)으로 매칭.
            (
                "SELECT DISTINCT pd.SchemaName FROM WebProductDatabases pd "
                "JOIN WebProducts p ON p.Id = pd.ProductId "
                "LEFT JOIN WebProductDatasources pds ON pds.ProductId = p.Id "
                "WHERE LOWER(p.DatasourceKey) = %s OR LOWER(pds.DatasourceKey) = %s",
                (dk, dk),
            ),
            # 최종 폴백: join 테이블도 부재(구 스키마) → primary 만.
            (
                "SELECT DISTINCT pd.SchemaName FROM WebProductDatabases pd "
                "JOIN WebProducts p ON p.Id = pd.ProductId WHERE LOWER(p.DatasourceKey) = %s",
                (dk,),
            ),
        ]
        for _sql, _params in _queries:
            try:
                cur = mem_conn.cursor()
                try:
                    cur.execute(_sql, _params)
                    rows = cur.fetchall() or []
                finally:
                    cur.close()
            except Exception:
                continue  # 컬럼/테이블 부재 → 다음 폴백 쿼리
            for row in rows:
                name = str((row or [None])[0] or "").strip()
                low = name.lower()
                if name and low not in seen:
                    seen.add(low)
                    dbs.append(name)
            if dbs:
                break  # 첫 성공 쿼리가 결과를 주면 종료(차원 격리 우선)
    # 2) default_db 폴백(제품 미등록 datasource 도 최소 1개는 스캔)
    default_db = str((ds_coords or {}).get("default_db") or "").strip()
    if default_db and default_db.lower() not in seen:
        seen.add(default_db.lower())
        dbs.append(default_db)
    return dbs


# ── TASK-0255: insight scan_failed 로그 edge-trigger 상태 캐시 ─────────────────
# 매 8s cycle 마다 불안정 datasource 전부를 WARNING 으로 재기록하던 도배(2일 ~20만 줄) 제거.
# 단일 insight-worker 프로세스가 cycle 을 직렬로 도므로(다른 worker 는 run_insight_cycle 미호출)
# 모듈-레벨 dict 로 충분(프로세스 간 공유 캐시 불요). key=(scope_key, db_name) → 직전 분류 상태.
_LAST_DS_SCAN_STATUS: dict[tuple, str] = {}


def _ds_scan_status_changed(scope_key, db_name, curr: str) -> bool:
    """TASK-0255 R1: (scope_key, db_name) 의 직전 cycle 분류 상태 대비 변경 여부.
    변경이면 True(→WARNING), 동일이면 False(→DEBUG). **부수효과로 최신 상태를 기록**한다.
    단일 insight-worker 프로세스가 cycle 을 직렬로 도므로 모듈-레벨 dict 로 충분(공유 캐시 불요)."""
    key = (scope_key, db_name)
    prev = _LAST_DS_SCAN_STATUS.get(key)
    _LAST_DS_SCAN_STATUS[key] = curr
    return prev != curr

# ── TASK-0255 R2: datasource 연결 health PG 영속 (agent_runtime.datasource_health) ──
# 관리콘솔이 "연결 불안정으로 미커버"(status=unstable/circuit_open)를 "권한 실패"(perm_failed)와
# 구분해 표면화할 수 있게, datasource 별 연결 상태를 PG 정본에 upsert 한다. 자격증명 비영속.
_DS_HEALTH_UPSERT_SQL = """
INSERT INTO agent_runtime.datasource_health
  (scope_key, datasource_label, engine, host, port, status, last_scan_outcome,
   fail_count, last_error_tag, last_checked_at, last_scan_at, last_transition_at, run_id, updated_at)
VALUES (%(scope_key)s, %(label)s, %(engine)s, %(host)s, %(port)s, %(status)s, %(scan_outcome)s,
        %(fail_count)s, %(last_error_tag)s,
        CASE WHEN %(last_checked_at)s IS NULL THEN NULL ELSE to_timestamp(%(last_checked_at)s) END,
        now(), now(), %(run_id)s, now())
ON CONFLICT (scope_key) DO UPDATE SET
  datasource_label   = COALESCE(EXCLUDED.datasource_label, agent_runtime.datasource_health.datasource_label),
  engine             = EXCLUDED.engine,
  host               = COALESCE(EXCLUDED.host, agent_runtime.datasource_health.host),
  port               = COALESCE(EXCLUDED.port, agent_runtime.datasource_health.port),
  status             = EXCLUDED.status,
  last_scan_outcome  = EXCLUDED.last_scan_outcome,
  fail_count         = EXCLUDED.fail_count,
  last_error_tag     = EXCLUDED.last_error_tag,
  last_checked_at    = COALESCE(EXCLUDED.last_checked_at, agent_runtime.datasource_health.last_checked_at),
  last_scan_at       = EXCLUDED.last_scan_at,
  last_transition_at = CASE WHEN EXCLUDED.status <> agent_runtime.datasource_health.status
                            THEN now() ELSE agent_runtime.datasource_health.last_transition_at END,
  run_id             = EXCLUDED.run_id,
  updated_at         = now();
"""

# scan_outcome 심각도(높을수록 우선 기록) — 한 datasource 의 여러 DB 결과를 datasource-레벨로 집계.
_DS_SCAN_OUTCOME_PREC = {"ok": 0, "perm_failed": 1, "skipped_no_db": 1, "other_failed": 2, "circuit_open": 3}


def _record_ds_health(rows: dict, scope_key, ds_coords, scan_outcome: str) -> None:
    """TASK-0255 R2: datasource 연결 health 행을 cycle-local dict 에 누적(PG 영속용). **절대 raise 안 함**
    (insight cycle 을 깨뜨리면 안 되는 soft telemetry). conn_health 의 권위 status(healthy/unstable/unknown)를
    우선 사용하고 이번 cycle 의 scan_outcome 을 병기. 자격증명 비포함(host/port/engine/status/fails/errno-tag)."""
    try:
        if not scope_key:
            return
        try:
            from shared import conn_health as _ch
            _st = _ch.status_for(ds_coords) or {}
        except Exception:
            _st = {}
        prev = rows.get(scope_key)
        if prev is not None:
            # 이미 더(또는 동급) 심각한 outcome 이 기록됐으면 그걸 유지(health status 만 최신화).
            if _DS_SCAN_OUTCOME_PREC.get(prev.get("scan_outcome"), 0) >= _DS_SCAN_OUTCOME_PREC.get(scan_outcome, 0):
                scan_outcome = prev.get("scan_outcome")
        _coords = ds_coords or {}
        rows[scope_key] = {
            "scope_key": scope_key,
            "label": (_st.get("label") or _coords.get("key")),
            "engine": (_st.get("engine") or _coords.get("engine") or "mysql"),
            "host": (_st.get("host") or _coords.get("host")),
            "port": (_st.get("port") or _coords.get("port")),
            "status": (_st.get("status") or "unknown"),
            "scan_outcome": scan_outcome,
            "fail_count": int(_st.get("fails") or 0),
            "last_error_tag": (str(_st.get("last_error") or "")[:80] or None),
            "last_checked_at": (_st.get("checked_at") or None),  # epoch float (None → SQL NULL)
        }
    except Exception:  # pragma: no cover — soft telemetry 는 어떤 경우에도 cycle 을 막지 않는다
        pass


def _persist_datasource_health(rows: dict, run_id: str) -> None:
    """TASK-0255 R2: datasource 연결 health 를 PG(agent_runtime.datasource_health)에 upsert + registry 동기 prune.
    soft telemetry — PG 미가용(M0/flag OFF)·연결 실패는 cycle 에 영향 주지 않는다(WARNING 1줄 후 return).
    bounded connect timeout(TASK-0255 _controlplane_connect_timeout, _pg_connect 적용)으로 PG 불안정도 블록 안 됨.
    **자격증명 비영속**: user/password 는 rows 에 애초에 없고(_record_ds_health), 저장 컬럼도 host/port/engine/
    status/fails/errno-tag 만."""
    try:
        if not _pg_available():
            return  # M0 standalone / AGENT_KB_PG_* 미설정 — graceful skip(테스트는 insight._pg_available patch)
    except Exception:
        return
    conn = None
    try:
        conn = _pg_connect(autocommit=True)  # bounded connect timeout(R3) + 자격증명은 conninfo 내부에만
        cur = conn.cursor()
        try:
            for r in rows.values():
                cur.execute(_DS_HEALTH_UPSERT_SQL, {
                    "scope_key": r["scope_key"],
                    "label": r.get("label"),
                    "engine": r.get("engine") or "mysql",
                    "host": r.get("host"),
                    "port": int(r["port"]) if r.get("port") else None,
                    "status": r.get("status") or "unknown",
                    "scan_outcome": r.get("scan_outcome"),
                    "fail_count": int(r.get("fail_count") or 0),
                    "last_error_tag": r.get("last_error_tag"),
                    "last_checked_at": (float(r["last_checked_at"]) if r.get("last_checked_at") else None),
                    "run_id": run_id,
                })
            # registry 동기 prune — 현재 datasource set 에 없는 행 제거(삭제·rename 된 datasource 잔류 방지).
            keep = list(rows.keys())
            if keep:
                cur.execute(
                    "DELETE FROM agent_runtime.datasource_health WHERE scope_key <> ALL(%(keep)s)",
                    {"keep": keep},
                )
            else:
                cur.execute("DELETE FROM agent_runtime.datasource_health")
        finally:
            cur.close()
    except Exception as exc:
        logging.getLogger("insight").warning(
            "datasource_health_persist_failed err=%s — soft telemetry, cycle 계속", type(exc).__name__,
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def run_insight_cycle(run_id: str | None = None) -> dict[str, Any]:
    cycle_run_id = str(run_id or "").strip() or _new_insight_worker_run_id()
    started = time.perf_counter()
    lock_name = str(AGENT_INSIGHT_WORKER_LOCK_NAME or "").strip() or "agent_insight_worker_scan"
    status = "ok"
    err_text = ""
    schema_count = 0
    scan_triggered = 0
    lock_acquired = False
    scan_report: dict[str, Any] = {
        "scan_started": False,
        "schemas_evaluated": 0,
        "schemas_generated": 0,
        "schemas_repaired": 0,
        "tables_selected": 0,
        "tables_generated": 0,
        "tables_repaired": 0,
        "artifact_missing_selected": 0,
        "skipped_schemas": 0,
        "skipped_tables": 0,
        "deferred_tables": 0,
        # TASK-0226: MSSQL per-DB 순회 커버리지 — 발견된 (datasource, DB) 대상 수와
        # 그 중 연결/스캔이 권한 등으로 실패해 누락된 수. 0 < db_failed 면 일부 등록 DB 가
        # 탐색되지 못한 것(주로 RO 로그인이 해당 DB 에 GRANT 안 됨) → status='degraded'.
        "db_targets": 0,
        "db_failed": 0,
        # TASK-0305 (RC5): db_failed 의 사유 분포를 cycle summary 로 표면화한다. 과거엔 분류
        # (TASK-0255)가 ds_health(PG)에만 영속되고 cycle 로그에는 안 남아, "28개 중 몇 개가 GRANT 로
        # 풀리는 perm 이고 몇 개가 network 문제인지"를 로그만으로 알 수 없었다(관측성 공백).
        "db_failed_perm": 0,     # 권한/인증 거부 (login failed 18456 / cannot open database 916 등) — GRANT 로 해결
        "db_failed_circuit": 0,  # 서킷 open (엔드포인트 도달 불가 확정) — 네트워크/호스트 다운
        "db_failed_other": 0,    # 그 외 (드라이버/쿼리 시점 오류 등)
    }
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
        # feature-0016 graphux5: 그래프 노드 AI 능동 분석 잡 처리(백그라운드 부하 분산 — 틱당 소량).
        #   자체 agent_kb PG 연결 + FOR UPDATE SKIP LOCKED claim 이라 advisory lock/source-DB readback
        #   상태와 무관하게 매 틱 수행한다(pending 잡 없으면 즉시 no-op). 실패는 삼켜 insight cycle 을
        #   막지 않는다(코어 비차단). 관리콘솔에서 "AI 능동 분석" 트리거 시에만 잡이 생긴다.
        try:
            from modules import node_analysis as _node_analysis
            _na_rep = _node_analysis.process_pending()
            if _na_rep.get("claimed"):
                scan_report["node_analysis"] = _na_rep
            # node-role-viz: role 도입(0031) 이전 done Table 잡 역할 휴리스틱 백필 — 잔여 0 이면
            #   SELECT 1회 후 즉시 no-op(자기 종결). LLM 재호출 없음, 실패는 삼켜 코어 비차단.
            _na_backfilled = _node_analysis.backfill_roles()
            if _na_backfilled:
                scan_report["node_analysis_role_backfill"] = _na_backfilled
        except Exception:
            logging.getLogger("insight").warning("node_analysis process_pending 실패", exc_info=True)
        if not lock_acquired:
            status = "skip_locked"
        elif _insight_readback_degraded():
            # read 정본(PG) 부재 — 생성 시 read-back 이 빈 MySQL fallback 으로 떨어져
            # 전부 missing/changed 오판 → livelock 재발. 본 cycle 은 scan/generate 를
            # skip 하고 loop 가 degraded backoff 로 PG 복구를 기다린다.
            status = "degraded_readback"
        else:
            # 멀티 datasource (P3): 기본 단일 MySQL(ds=None) + 등록 datasource 들을 순회하며
            # 각각 datasource-스코프 fact 키로 인사이트를 생성한다. flag OFF 면 ds_targets 가
            # [(None, None)] 한 개라 기존 동작 0 변경(무접두 키). datasource 별 키는 ContextVar
            # (set_active_datasource)로 ds_fact_key 에 주입 → write·read-back·grounding 3자 정합.
            ds_targets = [(None, None)]
            if AGENT_MULTI_DATASOURCE_ENABLED:
                # TASK-0205: DB 레지스트리(WebDatasources) + .env 병합. 정적 DATASOURCES 직접순회 폐기
                # (DB CRUD 후 삭제분 미스캔·신규분 반영, M1). password 복호 포함.
                from shared import datasources as _datasources
                for _k, _v in _datasources.all_datasources(mem_conn).items():
                    # TASK-0215: insight 탐색 비활성(InsightEnabled=0) 데이터소스는 순회에서 제외(운영자 토글).
                    if _v and _v.get("insight_enabled") is False:
                        logging.getLogger("insight").debug("insight_datasource_skipped(disabled) ds=%s", _k)
                        continue
                    ds_targets.append((_k, _v))
            schema_count = 0
            ds_health_rows: dict[str, dict] = {}  # TASK-0255 R2: scope_key → 연결 health 행(PG 영속)
            _seen_scan_keys: set = set()  # TASK-0255 M-1: 이번 cycle 관측한 (scope_key, db_name) — stale prune 용
            plan_start = time.perf_counter()
            for _ds_key, _ds_coords in ds_targets:
                # feature-0015: cycle 내 협조적 graceful 체크포인트. 긴 cycle(다수 datasource·LLM) 중
                # SIGTERM 이 와도 루프 경계까지 못 가 30s grace 후 SIGKILL 되던 것을, 현재 datasource
                # 처리 후 즉시 bail 로 단축(부분 cycle 은 멱등 — 다음 스캔이 재유도). (라이브 검증 적발)
                if _INSIGHT_SHUTDOWN.is_set():
                    try:
                        console.print("insight-worker: graceful — cycle 중 SIGTERM, datasource 루프 조기 종료")
                    except Exception:
                        pass
                    break
                # TASK-0219: 스코핑 식별자는 라벨(_ds_key)이 아닌 **엔드포인트 해시**(scope_key).
                _ds_scope = None
                if _ds_key is not None and _ds_coords:
                    _ds_scope = _ds_coords.get("scope_key") or _ds_key  # 해시 우선, 폴백 라벨(.env 레거시)
                _ds_engine = (_ds_coords.get("engine") if _ds_coords else None)
                _ds_default_db = (_ds_coords.get("default_db") if _ds_coords else None)

                # insight-load-spread: endpoint 가 circuit-open(status=down, 연속 실패 확정)이면 이
                # datasource 의 DB 순회를 통째로 skip 한다. 과거엔 매 tick(8s)마다 DOWN 데이터소스의 20+
                # DB 를 connect_with_retry→즉시 DatasourceCircuitOpen→로그로 도배(워커 점유 + scan_failed
                # 로그 노이즈)했다. should_fast_fail 은 순수 조회(부작용 없음)이고, background conn_health
                # 모니터가 복구를 감지하면 status 가 내려가 다음 tick 부터 자동 재개된다(실질 backoff).
                # health 는 circuit_open 으로 기록(관리콘솔 가시화 유지). MySQL 기본 DB(_ds_key is None)는 제외.
                if _ds_key is not None and _ds_scope:
                    try:
                        from shared import conn_health as _conn_health
                        if _conn_health.should_fast_fail(_ds_scope):
                            _record_ds_health(ds_health_rows, _ds_scope, _ds_coords, "circuit_open")
                            scan_report["db_skipped_circuit"] = int(
                                scan_report.get("db_skipped_circuit", 0) or 0) + 1
                            continue
                    except Exception:
                        pass

                # TASK-0220: MSSQL 은 database.schema.table 3계층 → 제품 등록 DB(catalog) 마다 재연결해
                # 각각 스캔한다(fact_key 에 database 포함, set_active_database). MySQL/기본 DB 는 종전대로
                # database 차원 없이 1회 순회([None]). MSSQL 인데 발견 DB 가 없으면(미바인딩) 스캔 skip —
                # tempdb 폴백 스캔으로 쓰레기 인사이트를 쌓지 않는다.
                _is_mssql_ds = (
                    _ds_key is not None and str(_ds_engine or "").strip().lower() == "mssql"
                )
                if _is_mssql_ds:
                    _db_targets = _discover_mssql_databases(mem_conn, _ds_key, _ds_coords)
                    if not _db_targets:
                        logging.getLogger("insight").info(
                            "mssql_datasource_no_databases ds=%s — 등록 DB/기본DB 없음, 스캔 skip", _ds_key,
                        )
                        # TASK-0255 R2: 미바인딩 MSSQL 도 연결 health 는 기록(관리콘솔 가시화).
                        _record_ds_health(ds_health_rows, _ds_scope, _ds_coords, "skipped_no_db")
                        continue
                    # TASK-0226: 발견된 제품 접근가능 DB 수를 커버리지 telemetry 에 누적.
                    scan_report["db_targets"] = int(scan_report.get("db_targets", 0) or 0) + len(_db_targets)
                else:
                    _db_targets = [None]  # MySQL/기본 DB: database 차원 없음
                    # TASK-0305 (RC5): 비-MSSQL '데이터소스'(예: MySQL ds)도 1개 타깃으로 집계 —
                    # 과거엔 MSSQL 만 db_targets 에 누적돼 비-MSSQL ds 실패가 비가시였다. 기본 DB
                    # (_ds_key is None, 워커 자체 control-plane)는 제품 DB 가 아니므로 제외.
                    if _ds_key is not None:
                        scan_report["db_targets"] = int(scan_report.get("db_targets", 0) or 0) + 1

                for _db_name in _db_targets:
                    _ds_conn = None
                    try:
                        # P7: datasource engine + TASK-0205 B1 effective default_db 주입.
                        # TASK-0220: MSSQL 은 순회 중인 catalog 를 default_db/active_database 로 함께 set.
                        set_active_datasource(
                            _ds_scope,
                            engine=_ds_engine,
                            default_db=(_db_name if _db_name else _ds_default_db),
                        )
                        if _db_name:
                            set_active_database(_db_name)  # fact_key suffix 에 database 포함
                        if _ds_key is None:
                            _ds_conn = db_conn  # 기본 DB 는 이미 연결됨
                        else:
                            # datasource 연결. MSSQL 은 순회 중 catalog(_db_name)로 명시 연결
                            # (None 이면 _connect_mssql 이 default_db→tempdb 로 폴백 — MySQL 경로).
                            # db 모듈의 connect_with_retry 명시 사용(datasource= 인자 지원, REV-0203 P7).
                            _ds_conn = _db.connect_with_retry(
                                database=_db_name, datasource=_ds_coords, autocommit=True
                            )
                        _known = load_known_schemas(_ds_conn)
                        if _ds_key is not None:
                            # P7(TASK-0203): dialect 시스템 스키마(MSSQL sys/guest/db_*) 제외.
                            _ds_sys = _dialects.active().system_schemas()
                            _known = [s for s in (_known or []) if s and s.strip().lower() not in _ds_sys]
                        if _ds_key is None and _known:
                            KNOWN_SCHEMAS.clear()
                            KNOWN_SCHEMAS.extend(_known)
                        _scan_schemas = (_known or KNOWN_SCHEMAS) if _ds_key is None else (_known or [])
                        schema_count += len([s for s in (_scan_schemas or []) if s and not _is_system_schema(s)])
                        _bootstrap_schema_insights(_ds_conn, mem_conn, _scan_schemas, run_id=cycle_run_id)
                        _rep = _scan_instance_schema_insights(
                            _ds_conn,
                            mem_conn,
                            _scan_schemas,
                            run_id=cycle_run_id,
                        )
                        # REV-20260610-P3 MAJOR: datasource(+DB) 별 telemetry 누적(int 합산, bool OR).
                        if isinstance(_rep, dict):
                            for _k, _v in _rep.items():
                                if isinstance(_v, bool):
                                    scan_report[_k] = bool(scan_report.get(_k)) or _v
                                elif isinstance(_v, (int, float)):
                                    scan_report[_k] = (scan_report.get(_k) or 0) + _v
                                else:
                                    scan_report[_k] = _v
                        if _rep.get("scan_started"):
                            scan_triggered = 1
                    except Exception as _ds_exc:
                        # 연결실패 격리 (PF2/Codex): 한 datasource(+DB) 실패가 다른 순회·기본 DB
                        # scan 을 막지 않는다. 기본 DB(ds=None) 실패는 바깥 except 로 전파(기존 동작).
                        if _ds_key is None:
                            raise
                        # TASK-0226 / TASK-0305 (RC5): per-DB 실패를 커버리지 telemetry 에 집계(가시화).
                        # 과거엔 _is_mssql_ds 일 때만 db_failed 를 누적해, 비-MSSQL 데이터소스(예: MySQL ds)
                        # 실패가 운영자에게 안 보였다. 이 지점은 이미 `_ds_key is None`(기본 DB)이 위에서
                        # re-raise 로 걸러진 곳이라, 남은 실패는 모두 등록 datasource(+DB) 실패 → 무조건 집계.
                        scan_report["db_failed"] = int(scan_report.get("db_failed", 0) or 0) + 1
                        # TASK-0255: 실패 분류 — circuit_open 을 _is_perm 판정보다 **먼저** 판정한다.
                        # DatasourceCircuitOpen 의 한국어 메시지가 _is_perm 토큰과 우연 겹치지 않게(결합 차단).
                        if isinstance(_ds_exc, _db.DatasourceCircuitOpen):
                            _curr = "circuit_open"
                            _is_perm = False
                        else:
                            # 권한 거부(login failed / cannot open database / SELECT denied)는 가장 흔한 원인이라
                            # 진단 힌트를 덧붙인다 — bin/datasource-mssql-ro-bootstrap.sql 의 멀티 DB GRANT 미적용
                            # 신호. MSSQL 에러번호(18456/916/229/297)는 짧은 숫자라 무관 메시지(행수 등)에 우연
                            # 매칭될 수 있어 정규식 단어경계로 매칭한다(REV-20260611-0226 — 가짜 힌트 방지).
                            _err_s = str(_ds_exc).lower()
                            _is_perm = (
                                any(t in _err_s for t in
                                    ("login failed", "cannot open database", "permission", "denied"))
                                or bool(re.search(r"\b(18456|916|229|297)\b", _err_s))
                            )
                            _curr = "perm_failed" if _is_perm else "other_failed"
                        # TASK-0305 (RC5): 사유별 분포 카운터를 cycle summary 로 표면화 — GRANT 로 풀리는
                        # perm 과 네트워크성 circuit/other 를 로그만으로 구분 가능하게 한다(GRANT 대상 특정).
                        _reason_counter = {
                            "perm_failed": "db_failed_perm",
                            "circuit_open": "db_failed_circuit",
                        }.get(_curr, "db_failed_other")
                        scan_report[_reason_counter] = int(scan_report.get(_reason_counter, 0) or 0) + 1
                        # TASK-0255 R2: datasource 연결 health 행 누적(PG 영속 — 관리콘솔 가시화).
                        _record_ds_health(ds_health_rows, _ds_scope, _ds_coords, _curr)
                        # TASK-0255 R1: edge-trigger — 상태 전이(직전 cycle 대비) 시에만 WARNING, 지속은 DEBUG.
                        # 매 8s cycle 마다 불안정 DS 전부를 WARNING 으로 재기록하던 도배(2일 ~20만 줄) 제거.
                        _hint = (" (RO 로그인이 이 DB 에 USER/GRANT 됐는지 확인 — "
                                 "bin/datasource-mssql-ro-bootstrap.sql 을 DB 마다 실행)") if _is_perm else ""
                        _log = logging.getLogger("insight")
                        _seen_scan_keys.add((_ds_scope, _db_name))  # M-1: stale prune 용 이번 cycle 관측 키
                        _changed = _ds_scan_status_changed(_ds_scope, _db_name, _curr)
                        # M-2(자격증명 비노출): raw driver 예외를 %r 로 찍으면 args 에 DSN/계정이 섞일 수 있어
                        # str()[:160] 으로 절단(conn_health last_error 80자 정책과 동형). 진단은 perm_suspect+status 로.
                        (_log.warning if _changed else _log.debug)(
                            "insight_datasource_scan_failed ds=%s db=%s status=%s perm_suspect=%s err=%s — "
                            "다음 대상 계속%s",
                            _ds_key, _db_name, _curr, _is_perm, str(_ds_exc)[:160], _hint,
                        )
                    else:
                        # TASK-0255: 예외 없이 스캔 완료 — R1 상태 캐시 healthy 갱신(직전 실패면 INFO recovered),
                        # R2 health 행 ok 기록. **try 밖(else)이라 여기서 난 예외는 미스캔으로 오분류 안 됨**.
                        # MINOR(FP-6 방어): else 문장은 모두 비-raise 이지만 R1/R2 격리를 명문화하려 try 로 감싼다.
                        if _ds_key is not None and _ds_scope:
                            try:
                                _skey_ok = (_ds_scope, _db_name)
                                _seen_scan_keys.add(_skey_ok)  # M-1: stale prune 용 관측 키
                                if _LAST_DS_SCAN_STATUS.get(_skey_ok) not in (None, "healthy"):
                                    logging.getLogger("insight").info(
                                        "insight_datasource_scan_recovered ds=%s db=%s", _ds_key, _db_name,
                                    )
                                _LAST_DS_SCAN_STATUS[_skey_ok] = "healthy"
                                _record_ds_health(ds_health_rows, _ds_scope, _ds_coords, "ok")
                            except Exception:  # pragma: no cover — soft telemetry, cycle 절대 안 깨뜨림
                                pass
                    finally:
                        set_active_datasource(None)  # active_database 도 함께 리셋(set_active_datasource 내부)
                        if _ds_key is not None and _ds_conn is not None:
                            try:
                                _ds_conn.close()
                            except Exception:
                                pass
            _timing_breakdown_add(timing, "plan_ms", (time.perf_counter() - plan_start) * 1000.0)
            # TASK-0255 R2: datasource 연결 health 를 PG 정본에 영속(soft telemetry — 실패해도 cycle 계속).
            _persist_datasource_health(ds_health_rows, cycle_run_id)
            # TASK-0255 M-1: in-memory edge-trigger 캐시도 registry 동기 prune(PG prune 과 동형). 이번 cycle 에
            # 관측 안 된 (scope_key, db_name) = 삭제·rename·비활성된 datasource/DB → stale key 제거(메모리 누수 차단).
            for _k in [_k for _k in _LAST_DS_SCAN_STATUS if _k not in _seen_scan_keys]:
                _LAST_DS_SCAN_STATUS.pop(_k, None)
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
                # TASK-0226: MSSQL per-DB 순회 커버리지를 heartbeat KV 로 노출 — 운영자가
                # "등록 DB 중 몇 개가 권한 등으로 탐색 실패했는지" 를 모니터링.
                save_memory_kv(
                    mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_db_targets",
                    str(int(scan_report.get("db_targets", 0) or 0)),
                )
                save_memory_kv(
                    mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_db_failed",
                    str(int(scan_report.get("db_failed", 0) or 0)),
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

    # TASK-0131 (#10): publish 가 시도됐으나 전부 실패(생성/복구 0)면 'ok' 가 아니라 'degraded'.
    # 이전엔 모든 publish 가 실패해도 status='ok' 라 operator 에게 거짓 신호를 줬다.
    _pub_failed = int(scan_report.get("publish_failed", 0) or 0)
    _generated = (
        int(scan_report.get("schemas_generated", 0) or 0)
        + int(scan_report.get("tables_generated", 0) or 0)
        + int(scan_report.get("schemas_repaired", 0) or 0)
        + int(scan_report.get("tables_repaired", 0) or 0)
    )
    if status == "ok" and _pub_failed > 0 and _generated == 0:
        status = "degraded"
    # TASK-0226: 발견된 제품 접근가능 DB 중 하나라도 연결/스캔에 실패(주로 RO 로그인 GRANT
    # 누락)하면 커버리지 불완전 → 'ok' 가 아니라 'degraded'. 운영자에게 일부 등록 DB 가
    # 탐색되지 못했음을 알린다(가시화). 전부 성공이면 종전대로 ok.
    _db_failed = int(scan_report.get("db_failed", 0) or 0)
    if status == "ok" and _db_failed > 0:
        status = "degraded"
    timing["total_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
    timing["updated_at"] = utc_now_iso()
    timing["status"] = status
    timing["scan_triggered"] = int(scan_triggered)
    timing["schema_count"] = int(schema_count)
    timing["error"] = err_text
    payload = {
        "run_id": cycle_run_id,
        "status": status,
        "duration_ms": round(float(timing.get("total_ms", 0.0)), 2),
        "schema_count": int(schema_count),
        "scan_triggered": int(scan_triggered),
        "error": err_text,
    }
    payload.update(
        {
            "schemas_evaluated": int(scan_report.get("schemas_evaluated", 0) or 0),
            "schemas_generated": int(scan_report.get("schemas_generated", 0) or 0),
            "schemas_repaired": int(scan_report.get("schemas_repaired", 0) or 0),
            "tables_selected": int(scan_report.get("tables_selected", 0) or 0),
            "tables_generated": int(scan_report.get("tables_generated", 0) or 0),
            "tables_repaired": int(scan_report.get("tables_repaired", 0) or 0),
            "artifact_missing_selected": int(
                scan_report.get("artifact_missing_selected", 0) or 0
            ),
            "pending_schema_repairs": int(
                scan_report.get("pending_schema_repairs", 0) or 0
            ),
            "pending_table_repairs": int(
                scan_report.get("pending_table_repairs", 0) or 0
            ),
            "deferred_tables": int(scan_report.get("deferred_tables", 0) or 0),
            "skipped_schemas": int(scan_report.get("skipped_schemas", 0) or 0),
            "skipped_tables": int(scan_report.get("skipped_tables", 0) or 0),
            "publish_failed": int(scan_report.get("publish_failed", 0) or 0),
            # TASK-0226: MSSQL per-DB 커버리지.
            "db_targets": int(scan_report.get("db_targets", 0) or 0),
            "db_failed": int(scan_report.get("db_failed", 0) or 0),
            # TASK-0305 (RC5): db_failed 사유 분포 — perm 은 GRANT 로, circuit/other 는 네트워크/인프라로.
            "db_failed_perm": int(scan_report.get("db_failed_perm", 0) or 0),
            "db_failed_circuit": int(scan_report.get("db_failed_circuit", 0) or 0),
            "db_failed_other": int(scan_report.get("db_failed_other", 0) or 0),
        }
    )
    should_log = status != "ok" or bool(scan_report.get("scan_started"))
    if should_log:
        timing_path = _write_timing_breakdown(timing)
        if timing_path:
            payload["timing_path"] = timing_path
        append_log_line("insight_worker", json.dumps(payload, ensure_ascii=False))
    return payload


def run_account_insight_pass(run_id: str | None = None) -> dict[str, Any]:
    """B′ (TASK-20260617T082131 / kv-source 보강 TASK-20260617T100524): 계정 cross-conversation
    회상의 *소스* 를 생성한다.

    owner 있는 비-fork·비-archived 대화의 **summary(선택) + kv 신호(origin_request/thread_goal/
    topic)** 에서 PII-free 메타 인사이트를 LLM(`llm_account_insight`)으로 추출해
    `source_type='account_insight'` fact(대화-로컬, 전역 미공유 — account_insight ∉
    AGENT_GLOBAL_KB_TYPES 이므로 `_publish_fact` 가 global 안 함)로 저장한다. 임베딩은 기존 KB
    파이프라인(`texts`)이 후속 처리 → `account_recall` 이 벡터 회상한다. **summary 가 비어도
    kv 신호로 동작**(이 배포의 요약-쓰기 결함과 무관). 신호 충분성(summary+kv 합산 ≥
    MIN_SUMMARY_LEN) 게이트 + 합산 fingerprint 로 재추출 회피. flag
    `AGENT_ACCOUNT_INSIGHT_EXTRACT` OFF 면 no-op.
    """
    report: dict[str, Any] = {"candidates": 0, "extracted": 0, "skipped_fp": 0, "empty": 0, "errors": 0}
    if not AGENT_ACCOUNT_INSIGHT_EXTRACT:
        return report
    from shared.db import _pg_available, _pg_connect
    from .kb_write import _publish_fact
    from .kb_scope import _mask_prose
    if not _pg_available():
        return report
    try:
        cap = max(1, int(AGENT_ACCOUNT_INSIGHT_EXTRACT_MAX_CONVS))
    except Exception:
        cap = 25
    try:
        min_len = max(0, int(AGENT_ACCOUNT_INSIGHT_MIN_SUMMARY_LEN))
    except Exception:
        min_len = 40
    rid = str(run_id or "").strip() or _new_insight_worker_run_id()

    # 후보 대화: owner 있고 비-fork·비-archived, 최근순(PG agent_runtime). summary 는 **선택**
    # (LEFT JOIN) — 이 배포처럼 요약 쓰기가 비어도 kv 신호(origin_request/thread_goal/topic)로
    # 인사이트를 추출할 수 있게 한다. 신호 충분성(min_len) 게이트는 per-conv(summary+kv 합산).
    candidates: list[tuple[str, str]] = []
    pg = None
    try:
        pg = _pg_connect()
        if pg is None:
            return report
        with pg.cursor() as cur:
            cur.execute(
                """
SELECT c.conversation_id, COALESCE(s.summary, '')
FROM agent_runtime.core_conversations c
LEFT JOIN agent_runtime.summary s ON s.conversation_id = c.conversation_id
WHERE c.owner_account_id IS NOT NULL
  AND c.archived_at IS NULL
  AND c.forked_from_conversation_id IS NULL
ORDER BY c.updated_at DESC
LIMIT %s
                """,
                (cap,),
            )
            for r in (cur.fetchall() or []):
                cid = str((r or [None])[0] or "").strip()
                summ = str((r or [None, None])[1] or "")
                if cid:
                    candidates.append((cid, summ))
    except Exception as exc:
        logging.getLogger("insight").warning("account_insight_pass: candidate query 실패(무시): %s", exc)
        return report
    finally:
        if pg is not None:
            try:
                pg.close()
            except Exception:
                pass

    report["candidates"] = len(candidates)
    if not candidates:
        return report

    fp_map = _load_kv_prefix_map(None, GLOBAL_CONVERSATION_ID, "account_insight_fp:")
    mem_conn = None
    try:
        mem_conn = connect_with_retry(database=MEMORY_DB, autocommit=True)
    except Exception:
        mem_conn = None

    try:
        for cid, summary in candidates:
            try:
                kv: dict[str, str] = {}
                try:
                    for k in ("origin_request", "thread_goal", "topic"):
                        kv[k] = str(load_memory_kv(mem_conn, cid, k) or "").strip()
                except Exception:
                    kv = {}
                payload = {
                    "summary": summary,
                    "origin_request": kv.get("origin_request", ""),
                    "thread_goal": kv.get("thread_goal", ""),
                    "topic": kv.get("topic", ""),
                }
                # 신호 충분성 게이트(summary+kv 합산) + fingerprint 도 합산 기준 — summary 가 비어도
                # kv 가 바뀌면 재추출. 신호가 부족하면(빈 대화) skip.
                signal = "".join([
                    payload["summary"], payload["origin_request"],
                    payload["thread_goal"], payload["topic"],
                ])
                if len(signal.strip()) < min_len:
                    report["skipped_fp"] += 1
                    continue
                fp = hashlib.sha256(signal.encode("utf-8", "ignore")).hexdigest()[:32]
                if fp_map.get(f"account_insight_fp:{cid}") == fp:
                    report["skipped_fp"] += 1
                    continue
                obj = llm_account_insight(payload)
                insight_text = str(obj.get("insight") or "").strip() if isinstance(obj, dict) else ""
                if not insight_text:
                    report["empty"] += 1
                    # 빈 결과도 fingerprint 저장 — 신호 안 바뀌면 LLM 재호출 안 함(비용 절감).
                    _save_fingerprint(None, f"account_insight_fp:{cid}", fp)
                    continue
                insight_text = _mask_prose(insight_text)  # G3 2차 방어(추출 PII-free 가 1차).
                _publish_fact(
                    mem_conn,
                    cid,                      # 대화-로컬 저장 → account_recall 의 conv_ids 필터가 회상
                    "account_insight",
                    insight_text,
                    4,
                    scope_key=FACT_SCOPE_COMMON,
                    source_type="account_insight",
                    source_run_id=rid,
                    source_sql="",
                )
                _save_fingerprint(None, f"account_insight_fp:{cid}", fp)
                report["extracted"] += 1
            except Exception as exc:
                report["errors"] += 1
                logging.getLogger("insight").warning("account_insight_pass: cid=%s 실패(무시): %s", cid, exc)
                continue
    finally:
        if mem_conn is not None:
            try:
                mem_conn.close()
            except Exception:
                pass
    return report


def _embedding_backfill_loop() -> None:
    """TASK-0307: NULL embedding texts 를 주기적으로 소량 임베딩하는 백그라운드 루프.

    별도 데몬 스레드에서 돈다 — titan-embed 가 batch 당 수십 초라(REV F1) insight tick(8s)에
    동기 호출하면 스캔 본업을 블로킹하기 때문. pass 당 BATCH_MAX_ROWS 만 처리하고 INTERVAL_SEC
    sleep. 백로그 없으면 fetch 0건 cheap no-op. fail-soft(스레드 죽지 않음)."""
    interval = max(5, int(AGENT_KB_EMBEDDING_INTERVAL_SEC))
    per_pass = max(1, int(AGENT_KB_EMBEDDING_BATCH_MAX_ROWS))
    _log = logging.getLogger("insight")
    while True:
        try:
            from scripts.kb_embedding_worker import run_embedding_pass
            rep = run_embedding_pass(max_rows=per_pass)
            if int(rep.get("processed") or 0) > 0 or rep.get("error"):
                _log.info(
                    "embedding_backfill processed=%s failed=%s remaining=%s err=%s",
                    rep.get("processed"), rep.get("failed"), rep.get("remaining"),
                    str(rep.get("error") or "")[:120],
                )
        except Exception as exc:  # 스레드 보호 — 어떤 예외도 루프를 죽이지 않음
            _log.warning("embedding_backfill pass 실패(무시): %s", exc)
        time.sleep(interval)


def _start_embedding_backfill_thread() -> None:
    """AUTO 켜짐 시 embedding 백필 데몬 스레드 1회 기동(conn_health 모니터와 동형 daemon)."""
    if not AGENT_KB_EMBEDDING_AUTO:
        return
    try:
        import threading
        t = threading.Thread(target=_embedding_backfill_loop, name="kb-embedding-backfill", daemon=True)
        t.start()
        logging.getLogger("insight").info(
            "embedding_backfill 스레드 기동(interval=%ss, batch_max=%s)",
            AGENT_KB_EMBEDDING_INTERVAL_SEC, AGENT_KB_EMBEDDING_BATCH_MAX_ROWS,
        )
    except Exception as exc:
        logging.getLogger("insight").warning("embedding_backfill 스레드 기동 실패(무시): %s", exc)


def _semantic_cluster_loop() -> None:
    """feature-0016 Phase C: 메타데이터 시그니처 백필 + scope 별 의미 클러스터링 백그라운드 루프.

    embedding 데몬(위)과 동형 — 별도 데몬 스레드에서 돌며 tick(8s)을 블로킹하지 않는다(임베딩·유사도 계산은
    gateway/PG 지연 bound·batchy). pass 당 signature 백필 + cadence-due scope 클러스터링. fail-soft."""
    interval = max(60, int(AGENT_METADATA_CLUSTER_INTERVAL_SEC))
    _log = logging.getLogger("insight")
    while True:
        try:
            from modules import semantic_cluster
            rep = semantic_cluster.run_cluster_maintenance()
            sig = (rep or {}).get("signature") or {}
            if int(sig.get("changed") or 0) > 0 or int((rep or {}).get("updated") or 0) > 0:
                _log.info(
                    "semantic_cluster sig_changed=%s scopes=%s clustered=%s updated=%s",
                    sig.get("changed"), (rep or {}).get("scopes"),
                    (rep or {}).get("clustered"), (rep or {}).get("updated"),
                )
        except Exception as exc:   # 스레드 보호 — 어떤 예외도 루프를 죽이지 않음
            _log.warning("semantic_cluster pass 실패(무시): %s", exc)
        time.sleep(interval)


def _start_semantic_cluster_thread() -> None:
    """AUTO 켜짐 시 Phase C 클러스터링 데몬 스레드 1회 기동(embedding 백필 스레드와 동형·분리)."""
    if not AGENT_METADATA_CLUSTER_AUTO:
        return
    try:
        import threading
        t = threading.Thread(target=_semantic_cluster_loop, name="meta-semantic-cluster", daemon=True)
        t.start()
        logging.getLogger("insight").info(
            "semantic_cluster 스레드 기동(interval=%ss, recompute=%ss, sig_batch=%s)",
            AGENT_METADATA_CLUSTER_INTERVAL_SEC, AGENT_METADATA_CLUSTER_RECOMPUTE_SEC,
            AGENT_METADATA_CLUSTER_SIG_BATCH_MAX_ROWS,
        )
    except Exception as exc:
        logging.getLogger("insight").warning("semantic_cluster 스레드 기동 실패(무시): %s", exc)


def _xds_relationship_infer_loop() -> None:
    """feature-0016 Phase B(ADR-019): 크로스-데이터소스 관계 추론 백그라운드 루프(Phase C 임베딩 구동).

    embedding/cluster 데몬과 동형·분리 — tick 무블로킹. pass 당 infer_cross_datasource_relationships +
    store_xds_inferred_relationships. **기본 OFF**(AGENT_XDS_RELATIONSHIP_INFER_AUTO) — 임베딩 populate 후 flip. fail-soft."""
    interval = max(300, int(AGENT_XDS_RELATIONSHIP_INFER_INTERVAL_SEC))
    _log = logging.getLogger("insight")
    while True:
        try:
            from modules import relationships as _rel
            n = _rel.store_xds_inferred_relationships()
            if n:
                _log.info("xds_relationship_infer upserted=%s", n)
        except Exception as exc:   # 스레드 보호
            _log.warning("xds_relationship_infer pass 실패(무시): %s", exc)
        time.sleep(interval)


def _start_xds_relationship_infer_thread() -> None:
    """AUTO 켜짐 시 크로스-ds 관계 추론 데몬 스레드 1회 기동(기본 OFF — 임베딩 populate 후 flip)."""
    if not AGENT_XDS_RELATIONSHIP_INFER_AUTO:
        return
    try:
        import threading
        t = threading.Thread(target=_xds_relationship_infer_loop, name="xds-relationship-infer", daemon=True)
        t.start()
        logging.getLogger("insight").info(
            "xds_relationship_infer 스레드 기동(interval=%ss, min_sim=%s)",
            AGENT_XDS_RELATIONSHIP_INFER_INTERVAL_SEC, AGENT_XDS_RELATIONSHIP_MIN_SIM,
        )
    except Exception as exc:
        logging.getLogger("insight").warning("xds_relationship_infer 스레드 기동 실패(무시): %s", exc)


# feature-0015: SIGTERM/SIGINT → graceful. 현재 cycle 을 마저 끝내고(루프 경계에서) 종료.
# insight 쓰기는 멱등(_upsert_fact autocommit 단일-fact + advisory lock + 다음 스캔 재유도)이라
# SIGKILL 도 데이터 손상은 없으나, graceful 종료로 (a) 진행 cycle 의 불필요한 중단/LLM 비용 낭비,
# (b) heartbeat 갱신 누락에 따른 healthcheck 일시 unhealthy 를 줄인다. ask.py 패턴과 동형.
_INSIGHT_SHUTDOWN = _threading.Event()


def _install_insight_signal_handlers() -> None:
    def _handler(signum, _frame):
        # console.print 로 가시화(이 워커는 logging 미설정이라 INFO 는 docker logs 에 안 보임).
        try:
            console.print(f"insight-worker: signal {signum} 수신 — graceful shutdown 예약")
        except Exception:
            pass
        _INSIGHT_SHUTDOWN.set()
    try:
        _signal.signal(_signal.SIGTERM, _handler)
        _signal.signal(_signal.SIGINT, _handler)
    except Exception:
        # 메인 스레드가 아니면(테스트 등) 등록 불가 — 무시.
        pass


def run_insight_worker_loop() -> None:
    if not AGENT_INSIGHT_WORKER_ENABLED:
        console.print("insight worker disabled: AGENT_INSIGHT_WORKER_ENABLED=0")
        return
    _install_insight_signal_handlers()
    tick_sec = max(5, int(AGENT_INSIGHT_WORKER_TICK_SEC))
    degraded_backoff_sec = max(tick_sec, int(AGENT_INSIGHT_WORKER_DEGRADED_BACKOFF_SEC))
    jitter_sec = max(0, int(AGENT_INSIGHT_WORKER_JITTER_SEC))
    if jitter_sec > 0:
        # 인터럽트 가능한 jitter 대기(부팅 직후 SIGTERM 도 즉시 반응).
        _INSIGHT_SHUTDOWN.wait(random.uniform(0, float(jitter_sec)))
    # conn-health-monitor: insight 스캔 연결도 health 게이트 수혜 — 불안정 datasource 를
    # 백그라운드로 미리 판정(daemon thread, 프로세스 종료 시 정리).
    try:
        from shared import conn_health
        from shared import datasources as _ds
        conn_health.start_monitor(_ds.health_probe_provider())
    except Exception as exc:
        logging.getLogger("insight").warning("insight-worker: conn_health 모니터 시작 실패(무시): %s", exc)
    # TASK-0307: embedding 백필 데몬 스레드 기동(본 tick 루프와 분리 — 블로킹 방지).
    _start_embedding_backfill_thread()
    # feature-0016 Phase C: 메타데이터 시그니처 임베딩 + 의미 클러스터링 데몬 스레드(embedding 스레드와 분리·동형).
    _start_semantic_cluster_thread()
    # feature-0016 Phase B: 크로스-데이터소스 관계 추론 데몬 스레드(기본 OFF — AGENT_XDS_RELATIONSHIP_INFER_AUTO).
    _start_xds_relationship_infer_thread()
    while not _INSIGHT_SHUTDOWN.is_set():
        result = run_insight_cycle()
        status = str((result or {}).get("status", "")).strip()
        # B′ (TASK-20260617T082131): degraded(PG 부재) 아닐 때만 account_insight 추출 pass.
        # flag OFF 면 내부에서 즉시 no-op. fail-soft — 추출 실패가 worker 루프를 깨지 않음.
        if status not in ("degraded_readback", "error"):
            try:
                run_account_insight_pass()
            except Exception as exc:
                logging.getLogger("insight").warning("account_insight_pass: 루프 호출 실패(무시): %s", exc)
        # PG read 정본 부재(degraded_readback) / 연결 오류(error) 시엔 짧은 tick 대신
        # 길게 backoff — MySQL fallback 으로 떨어져 무의미한 재시도(livelock 동력)를
        # 반복하지 않고 PG 복구를 기다린다.
        # 인터럽트 가능한 tick 대기 — SIGTERM 시 다음 cycle 진입 전 즉시 깨어 루프 종료.
        if status in ("degraded_readback", "error"):
            _INSIGHT_SHUTDOWN.wait(degraded_backoff_sec)
        else:
            _INSIGHT_SHUTDOWN.wait(tick_sec)
    try:
        console.print("insight-worker: graceful shutdown 완료(루프 종료).")
    except Exception:
        pass
