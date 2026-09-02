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

from shared.llm_gate import server_llm_enabled  # feature-0043: 서버 계정 LLM fail-closed 게이트
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


# ── 테이블 인사이트의 개인 AI 위임 (TASK-20260901T190000, P0-AK) ────────────────────
#
# 서버 계정 LLM 이 닫힌 뒤 이 배치는 통째로 멎어 있었다(`_get_llm_client` 가 None → 매 cycle
# `invalid_response`). 사용자 결정(2026-09-01) "연결한 AI를 통해 작동하도록 배선".
#
# ## 워커는 기다리지 않는다 — **KV 가 이음매다**
#
# 이 loop 에는 이미 「이전 cycle 대표가 남긴 분석을 LLM 없이 상속」하는 경로가 있다
# (`kv_inherit`). 위임 결과를 **그 자리에 넣으면** 발행·검증·fan-out 이 전부 기존 경로로
# 흐른다 — 저장을 새로 쓰지 않는다는 이 feature 의 제약이 그대로 지켜진다.
#
#     cycle N   : 게이트 닫힘 → 적재(dedupe) → 이 테이블은 이번 cycle 미분석(종전과 동일)
#     러너 응답 : apply_external_insight_summary → KV 기입
#     cycle N+1 : `kv_inherit` 로 상속 → 기존 발행 경로 그대로
#
# ## 왜 그룹 KV 를 그대로 쓰지 않는가
#
# 그룹 KV(`_group_insight_kv_key`)는 **시그니처가 있는 테이블**만 가진다. 시그니처가 없는
# 테이블(그룹 미형성)은 저장할 곳이 없어 영영 분석되지 않는다 — 그건 「배선했다」가 아니다.
# 그래서 위임 결과는 `테이블키 + 지문` 으로 키를 만들어 **모든 테이블**이 대상이 된다.
# 지문을 키에 넣는 이유: 테이블이 바뀌면 낡은 분석이 자동으로 미적중이 된다(그룹 KV 의
# 시그니처가 하는 일과 같은 축).

#: 위임 결과 KV 의 접두. 그룹 캐시와 **다른 이름 공간**이다 — 섞으면 시그니처 없는 테이블의
#: 결과가 그룹 상속 경로로 새어 들어가 엉뚱한 형제에게 전파된다.
_DELEGATED_INSIGHT_KV_PREFIX = "delegated_table_insight"


def _delegated_insight_kv_key(table_key, tfp) -> str:
    """위임 결과 KV 키. 지문이 바뀌면 키가 바뀌어 낡은 분석이 자동으로 버려진다."""
    import hashlib as _hashlib

    raw = f"{table_key}\x1f{tfp or ''}"
    return f"{_DELEGATED_INSIGHT_KV_PREFIX}:{_hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]}"


def _load_delegated_insight_kv(mem_conn, table_key, tfp):
    """개인 AI 가 낸 이 테이블의 분석 dict. 없거나 오류면 None(= 이번 cycle 미분석)."""
    if mem_conn is None or not table_key:
        return None
    try:
        raw = load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID,
                             _delegated_insight_kv_key(table_key, tfp))
    except Exception:
        return None
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _delegate_table_insight(mem_conn, table_key, tfp, payload, schema, table) -> bool:
    """이 테이블의 인사이트를 동의한 개인 AI 대기열에 올린다. **fail-soft**.

    같은 테이블을 매 cycle 다시 적재하지 않도록 KV 키를 그대로 `dedupe_key` 로 쓴다 —
    키가 곧 「이 지문의 이 테이블」이라, 지문이 바뀌면 새 작업이 되고 안 바뀌면 중복이 막힌다.
    """
    from shared import bridge_tasks as _bt

    if mem_conn is None or not table_key:
        return False
    try:
        from modules.semantic_cluster import _batch_consenting_account
        from modules.llm import table_insight_messages

        account_id = _batch_consenting_account(mem_conn, "insight_summary")
        if not account_id:
            # 매 테이블 로그를 남기면 소음이라 호출측이 cycle 당 한 번만 말한다.
            return False
        _bt.enqueue_console_job(
            mem_conn, account_id=account_id, job_kind="insight_summary",
            prompt=_bt.messages_to_prompt(table_insight_messages(payload), "json"),
            payload={"kv_key": _delegated_insight_kv_key(table_key, tfp),
                     "table_key": str(table_key), "schema": str(schema), "table": str(table)},
            dedupe_key=_delegated_insight_kv_key(table_key, tfp))
        return True
    except _bt.ConsoleJobRejected as exc:
        logging.getLogger("insight").info("insight_summary 위임 미적재 %s.%s: %s", schema, table, exc)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("insight").warning(
            "insight_summary 위임 적재 실패 %s.%s: %r", schema, table, exc)
    return False


def apply_external_insight_summary(conn, payload, result) -> None:
    """개인 AI 가 낸 테이블 인사이트를 **KV 이음매**에 기입한다 (`_STORE_ROUTES` 대상).

    발행(fact 저장·검증·fan-out)은 하지 않는다 — 그것은 다음 cycle 의 `kv_inherit` 경로가
    기존대로 한다. 여기서 직접 발행하면 발행 로직이 두 벌이 되고, 두 벌이 되는 순간 한쪽이
    낡아 같은 분석이 경로에 따라 다르게 저장된다(이 feature 가 지켜 온 제약).
    """
    kv_key = str((payload or {}).get("kv_key") or "")
    if not kv_key:
        raise ValueError("위임 payload 에 kv_key 가 없습니다 — 어디에 쓸지 알 수 없습니다.")
    if not isinstance(result, dict) or not result:
        raise ValueError("테이블 인사이트 결과가 JSON 객체가 아닙니다.")
    body = json.dumps(result, ensure_ascii=False)
    save_memory_kv(conn, GLOBAL_CONVERSATION_ID, kv_key, body)
    # ⚠ **썼는지 되읽어 확인한다.**
    #
    # `save_memory_kv` 는 `conn` 을 쓰지 않고 자기 PG 연결을 열며, 실패하면 경고만 남기고
    # **조용히 넘어간다**(그 함수의 다른 소비처들은 heartbeat·topic 처럼 유실돼도 다음 주기에
    # 덮어써지는 값이라 그 관대함이 맞다). 그러나 여기는 **쓰기 축**이다 — 반영하지 못했는데
    # 성공으로 접으면 콘솔은 "완료" 라 말하고 값은 어디에도 없으며, 다음 cycle 이 같은 작업을
    # 사용자 계정 토큰으로 **다시 산다**. 되읽어 없으면 예외로 올려 작업 행에 사유를 남긴다.
    if not _load_delegated_insight_raw(kv_key):
        raise RuntimeError("KV 기입을 확인하지 못했습니다(런타임 저장소 쓰기 실패).")
    logging.getLogger("insight").info(
        "insight_summary 위임 결과 기입 %s", (payload or {}).get("table_key"))


def _load_delegated_insight_raw(kv_key: str) -> str:
    """그 키의 원문. 되읽기 확인 전용 — 실패는 빈 문자열(= 확인 못 함)."""
    try:
        return str(load_memory_kv(None, GLOBAL_CONVERSATION_ID, kv_key) or "")
    except Exception:
        return ""


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


# ── 구조 변동 자동 재귀 분석 (change-reanalysis, 사용자 결정 2026-07-27) ─────────
#: 자동 재분석 전용 **구조 스냅샷** KV prefix — 스키마당 1건에 그 시점의 전체 구조를 담는다:
#    {"t": {table: fingerprint12}, "r": {routine: definition_hash12}}
#
#  **왜 insight 지문(table_fp)을 쓰지 않는가 (적대 리뷰 B1 — 이 설계의 핵심)**: `table_fp` 는
#  insight artifact 발행이 성공한 테이블만, 그것도 스캔당 `SCAN_TABLE_LIMIT`(기본 12)개씩 저장된다.
#  즉 "스키마의 일부만 지문 보유" 가 정상 상태이고, publish 가 필터링된 테이블은 영구히 지문이 없다.
#  그 부재를 '신규'로 읽으면 **이미 전체 분석을 마친 DB 의 테이블 대부분이 구조 변동으로 오탐**되어
#  승인 없는 대량 LLM 지출이 된다. 전용 스냅샷은 첫 저장이 곧 완전한 baseline 이라 이 오탐이 원천 제거되고,
#  동시에 (a) KV 키가 스키마당 1개라 `kv.key varchar(128)` 초과 위험(노드 key 는 최대 200자+)이 사라지며
#  (b) 노드 수천 건의 KV 팽창·커넥션 반복(리뷰 C4/C5)도 함께 해소된다.
_AUTO_SNAPSHOT_PREFIX = "na_struct_snap:"
#: 지문 저장 길이 — 변경 감지용이라 12자(48bit)면 충돌 확률이 무시 가능하고 스냅샷 크기를 억제한다.
_AUTO_FP_LEN = 12
#: 스키마별 직전 자동 재분석 status — 상태가 바뀔 때만 info 로그(매 tick 도배 방지, _LAST_DS_SCAN_STATUS 동형).
_LAST_AUTO_REANALYSIS_STATUS: dict[str, str] = {}


def _auto_snapshot_key(scope_key: str, schema_label: str, probe_schema: str = "") -> str:
    """구조 스냅샷 KV key — `kv.key varchar(128)` 안전을 위해 식별자를 해시로 접는다.

    **probe_schema 를 키에 포함하는 이유**: MSSQL 은 저장 라벨(`schema_label`)이 DB(catalog)명이라
    한 DB 안의 여러 실 스키마(dbo, sales …)가 같은 라벨을 공유한다. 라벨만으로 스냅샷을 잡으면
    스키마 A 순회가 B 의 테이블을 '삭제'로, B 순회가 A 를 '신규'로 읽어 **매 사이클 전량 진동**한다
    (승인 없는 대량 LLM 지출). 대조는 실 스키마 단위로 하고, 시드 노드 key 는 그래프 규약대로
    저장 라벨로 만든다(대조 축과 노드 키 축의 분리 — store/query 분리 관례와 동형)."""
    ident = f"{scope_key}:{schema_label}:{probe_schema}"
    return f"{_AUTO_SNAPSHOT_PREFIX}{hashlib.sha1(ident.encode('utf-8', 'replace')).hexdigest()[:32]}"


def _load_auto_snapshot(mem_conn, key: str):
    """저장된 구조 스냅샷 → {"t": {...}, "r": {...}, "tb": bool, "rb": bool}.
    부재/파손 시 None(= baseline 미확립).

    `tb`/`rb` 는 **축별 baseline 확립 여부**다. 축이 꺼진 채(루틴 introspect 미발화 등) 저장된
    스냅샷의 빈 축을 '확립됨' 으로 읽으면, 그 축이 처음 켜지는 사이클에 전량이 '신규'로 잡혀
    승인 없는 대량 시드가 된다. 레거시(플래그 부재) 스냅샷은 '내용이 있으면 확립' 으로 추론한다."""
    try:
        raw = load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, key)
    except Exception:
        return None
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except Exception:
        return None      # 파손된 스냅샷은 baseline 재확립(후보 0)으로 저하 — 오탐보다 안전
    if not isinstance(obj, dict):
        return None
    tables = obj.get("t") if isinstance(obj.get("t"), dict) else {}
    routines = obj.get("r") if isinstance(obj.get("r"), dict) else {}
    return {"t": dict(tables), "r": dict(routines),
            "tb": bool(obj.get("tb", bool(tables))), "rb": bool(obj.get("rb", bool(routines)))}


def _save_auto_snapshot(mem_conn, key: str, snap: dict) -> None:
    try:
        save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, key,
                       json.dumps({"t": snap.get("t") or {}, "r": snap.get("r") or {},
                                   "tb": 1 if snap.get("tb") else 0,
                                   "rb": 1 if snap.get("rb") else 0},
                                  ensure_ascii=False, separators=(",", ":")))
    except Exception:
        logging.getLogger("insight").debug("auto_snapshot_save_failed key=%s", key, exc_info=True)


def _auto_structure_inventory(current_table_fps, routine_inventory, *,
                              include_tables: bool, include_routines: bool):
    """이번 스캔이 관측한 **전체 구조 인벤토리** → {"t": {table: fp12}, "r": {routine: hash12}}.

    - 테이블: `_compute_table_fingerprints_batch` 가 스키마의 **전 테이블**에 대해 산출한 컬럼 구성
      지문(부분집합이 아님 — 그래서 스냅샷 대조가 성립한다).
    - 루틴: `routines.introspect_and_store(inventory_sink=…)` 가 채운 전량 목록.
    - **축별 비활성(include_*)**: 그 축의 관측이 이번 사이클에 없거나 신뢰할 수 없으면(루틴 introspect
      미발화·cap 절단, 테이블 지문 계산 실패, MSSQL 루틴 라벨 다대일) 축 자체를 끈다. 인벤토리가
      비는 것과 축이 꺼진 것은 다르다 — 전자는 '전부 삭제', 후자는 '이 축은 판단하지 않음'(스냅샷
      보존)이라, 축을 끄지 않고 빈 인벤토리를 넘기면 다음 관측에서 전량이 '신규'로 오탐된다.
    - 지문/해시가 빈 항목은 제외 — 스냅샷에 넣으면 다음 사이클에 '변경'으로 잡혀 진동한다."""
    tables = {}
    if include_tables:
        for name, fp in (current_table_fps or {}).items():
            n, f = str(name or "").strip(), str(fp or "").strip()
            if n and f:
                tables[n] = f[:_AUTO_FP_LEN]
    routines = {}
    if include_routines:
        for name, h in (routine_inventory or {}).items():
            n, f = str(name or "").strip(), str(h or "").strip()
            if n and f:
                routines[n] = f[:_AUTO_FP_LEN]
    return {"t": tables, "r": routines}


def _auto_structure_changes(scope_key, schema_label, snap, inventory, *,
                            include_tables: bool, include_routines: bool):
    """스냅샷 ↔ 현재 인벤토리 대조 → `(changes, absorbed)`.

    - `changes` = 자동 분석 후보 `[(node_key, kind, name, fp)]` — 신규(스냅샷에 키 없음) + 변경(지문 다름).
    - `absorbed` = **후보에서 뺐지만 스냅샷에는 즉시 반영**할 항목 `[(kind, name, fp)]`. 시드하지 않으면서
      재탐지도 하지 않아야 하는 것들이다.

    삭제는 분석 대상 노드가 없으므로 후보가 아니고 스냅샷에서 제거만 된다(그래프 prune·재클러스터 담당).
    그래프 노드 key 규약: Table=`<scope>:<schema>.<table>` · Routine=`<scope>:<schema>.<name>()`.

    **동일 구조 샤드 흡수 (적대 리뷰 재검증 B1 — 이 함수의 비용 핵심)**: 날짜/번호 샤드
    (`daily_league_ranking_1_20250727`, `_20250726` …)는 매일 새로 생기지만 직전 샤드와 구조가
    **완전히 동일**해 분석 가치가 0 이다. 이 제품은 2026-07-03 사용자 결정으로 이미 "동일 구조 샤드는
    대표 1개만 LLM, 형제는 KV 상속"(`AGENT_INSIGHT_TABLE_GROUPING_ENABLED`)을 확정했는데, 신규 테이블을
    이름만 보고 '구조 변동'으로 승격하면 자동 경로가 **승인 없이 그 결정을 되돌린다**(샤드가 매일
    생기므로 수렴하지도 않는다). 따라서 신규 테이블의 그룹 서명 `(base_stem, fp)` 이 스냅샷에 이미
    있는 형제와 같으면 후보에서 빼고 `absorbed` 로 넘긴다 — 진짜 구조 변경(기존 테이블의 fp 변화)은
    그룹과 무관하게 항상 후보다."""
    changes, absorbed = [], []
    if not scope_key or not schema_label:
        return changes, absorbed
    if include_tables:
        prev_t = (snap or {}).get("t") or {}
        group_on = bool(AGENT_INSIGHT_TABLE_GROUPING_ENABLED)
        prev_sigs = set()
        if group_on and prev_t:
            for pname, pfp in prev_t.items():
                psig = _table_group_sig(pname, prev_t)
                if psig is not None:
                    prev_sigs.add(psig)
        inv_t = inventory.get("t") or {}
        for name, fp in inv_t.items():
            prev_fp = prev_t.get(name)
            if prev_fp == fp:
                continue
            if prev_fp is None and group_on:
                sig = _table_group_sig(name, inv_t)
                if sig is not None and sig in prev_sigs:
                    absorbed.append(("t", name, fp))   # 기존 샤드와 동일 구조 — LLM 불요
                    continue
            changes.append((f"{scope_key}:{schema_label}.{name}", "t", name, fp))
    if include_routines:
        prev_r = (snap or {}).get("r") or {}
        rout = []
        for name, fp in (inventory.get("r") or {}).items():
            if prev_r.get(name) != fp:
                rout.append((f"{scope_key}:{schema_label}.{name}()", "r", name, fp))
        # 축 인터리브(적대 리뷰 재검증 B4): cap 절단은 리스트 앞에서부터라, 테이블 후보를 먼저 전부
        # 넣으면 테이블이 상시 cap 을 채우는 DB(대규모 마이그레이션·샤드 유입)에서 **루틴 축이 영구
        # 기아**가 된다 — 미시드 후보는 스냅샷이 전진하지 않아 다음 사이클에도 같은 순서로 머리를
        # 다시 점유하기 때문이다. 사용자 요청의 3축 중 "프로시저/함수 정의 변경"이 가장 바쁜 DB 에서
        # 실동작하지 않는 것을 막으려면 절단 전에 축을 섞어야 한다.
        if rout and changes:
            merged, ti, ri = [], 0, 0
            while ti < len(changes) or ri < len(rout):
                if ti < len(changes):
                    merged.append(changes[ti]); ti += 1
                if ri < len(rout):
                    merged.append(rout[ri]); ri += 1
            changes = merged
        else:
            changes.extend(rout)
    return changes, absorbed


#: 축 관측을 '실패'로 간주하는 소실 비율/최소 개수. 둘 다 넘겨야 의심한다.
#  진짜 대량 삭제라면 다음 사이클에도 같은 관측이 나오지만 후보는 여전히 0(삭제는 후보가 아님)이라
#  손해가 없고, 관측 실패였다면 전량 오탐(승인 없는 대량 LLM 지출)을 막는다 — 비대칭 위험에 맞춘 기본값.
#  **최소 개수를 둔 이유**: 비율만 보면 테이블 2개짜리 스키마에서 1개를 지운 정상 DDL 도 '과반 소실'
#  이라 삭제 반영이 영원히 막힌다. 그 규모에서는 오탐이 나도 최대 2건이라 위험이 미미하다.
_AUTO_AXIS_DROP_RATIO = 0.5
_AUTO_AXIS_DROP_MIN = 5


def _auto_axis_trusted(schema_key: str, axis: str, include: bool, inv: dict, prev: dict,
                       report) -> bool:
    """이번 사이클의 축 관측을 신뢰할 수 있는지 (적대 리뷰 재검증 B2 / qa Q2).

    스냅샷에 항목이 있는데 이번 인벤토리가 비었거나 과반이 사라졌으면 '관측 실패'로 보고 축을 끈다
    (= 대조도 갱신도 하지 않고 보존). 이 판정이 없으면 `information_schema` 가 권한·복원 창에서
    돌려주는 일시적 0행이 스냅샷을 통째로 지우고, 복귀 사이클에 무변경 테이블 전량이 '신규'가 된다."""
    if not include or not prev:
        return include
    lost = len(prev) - sum(1 for k in prev if k in inv)
    # 전량 소실은 크기와 무관하게 의심한다(권한 필터·복원 창의 전형적 형태). 부분 소실은
    # 비율·최소 개수를 함께 넘길 때만 — 소규모 스키마의 정상 DDL 을 막지 않기 위해.
    if lost and (not inv
                 or lost >= max(_AUTO_AXIS_DROP_MIN, int(len(prev) * _AUTO_AXIS_DROP_RATIO))):
        if isinstance(report, dict):
            report["auto_reanalysis_axis_dropped"] = int(
                report.get("auto_reanalysis_axis_dropped", 0)) + 1
        logging.getLogger("insight").warning(
            "auto_reanalysis_axis_untrusted schema=%s axis=%s prev=%s observed=%s lost=%s "
            "— 관측 실패로 간주해 스냅샷 보존(전량 재시드 방지)",
            schema_key, axis, len(prev), len(inv), lost)
        return False
    return include


def _auto_reanalyze_structure_changes(mem_conn, scope_key, schema_label, *, probe_schema="",
                                      current_table_fps=None, routine_inventory=None,
                                      include_tables=True, include_routines=True,
                                      report=None) -> None:
    """구조 변동이 감지된 그래프 노드에 **자동** AI 재귀 분석 run 을 건다 (change-reanalysis).

    사용자 요청(2026-07-27): "'DB 전체 AI 능동 분석'이 이루어진 DB" 에서 테이블·컬럼·프로시저·함수
    구조 변동이 감지되면, 사용자가 그래프 뷰에서 다시 실행하지 않아도 변경 노드가 재귀 분석된다.

    절차: 전용 구조 스냅샷 로드 → (없으면 **baseline 확립만** 하고 종료 — 첫 관측을 변경으로 오탐하지
    않는다) → 현재 인벤토리와 대조해 신규·변경 노드 산출 → `enqueue_change_analysis` →
    **실제 시드된 노드만** 스냅샷에 반영(그래프 미투영·cap 절단·쿨다운·진행 중 run 으로 빠진 노드는
    스냅샷에 남지 않아 다음 사이클에 자연 재시도). 삭제 항목은 스냅샷에서 즉시 제거.

    **축별 baseline**: 이번 사이클에 관측하지 못한 축(`include_*=False`)은 대조도 갱신도 하지 않고
    스냅샷을 보존한다. 그 축이 처음 켜지는 사이클은 해당 축만 baseline 확립(후보 0)으로 처리해,
    "관측 공백 → 전량 신규 오탐 → 승인 없는 대량 LLM 지출" 경로를 봉인한다.

    shadow 모드(`AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE=shadow`): 후보 산출·계측만 하고 enqueue 도
    스냅샷 갱신도 하지 않는다 — 배포 직후 실제 후보 규모를 **비용 0** 으로 관측하기 위한 안전 모드.

    전 경로 예외 흡수 — insight 스캔을 절대 차단하지 않는다."""
    if not AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE or not scope_key or not schema_label:
        return
    schema_key = f"{scope_key}:{schema_label}"
    log = logging.getLogger("insight")
    try:
        if not include_tables and not include_routines:
            return          # 이번 사이클에 신뢰할 관측 축이 없음 — 스냅샷 무변경(오탐 봉인)
        # 자격 선확인(적대 리뷰 재검증 B3): 자동 재분석이 **영원히 발동할 수 없는** 미자격 스키마의
        # 스냅샷까지 적재하면, 그 blob(스키마 전 테이블 맵)이 스캔마다 KV 전량 덤프 경로에 올라타
        # 대역·커넥션을 먹는다. 자격 획득 시 첫 사이클이 baseline 이 되므로 오탐도 늘지 않는다.
        from . import node_analysis as _na
        if not _na.schema_analysis_completed(scope_key, schema_key):
            _auto_note_status(schema_key, "ineligible", 0, report)
            return
        inventory = _auto_structure_inventory(current_table_fps, routine_inventory,
                                              include_tables=include_tables,
                                              include_routines=include_routines)
        snap_key = _auto_snapshot_key(scope_key, schema_label, probe_schema)
        snap = _load_auto_snapshot(mem_conn, snap_key)
        # 관측 신뢰 3-상태(적대 리뷰 재검증 B2 / qa Q2) — "축이 꺼짐" · "축이 켜졌고 관측 신뢰" 에
        # 더해 **"축은 켜졌지만 이번 관측을 믿을 수 없음"** 을 명시한다. `information_schema.TABLES`
        # 는 권한 필터 결과라 계정 교체·GRANT 축소·복원(DROP→CREATE→import) 창에서 **예외 없이 0행**
        # 을 돌려준다. 그 한 사이클을 '전부 삭제'로 읽으면 스냅샷이 비고(무음), 복귀 사이클에 구조가
        # 전혀 안 바뀐 전 테이블이 '신규'로 폭발한다 — 1차 리뷰 B1(승인 없는 대량 지출)의 재진입이다.
        # 전량 소실·과반 소실은 '관측 실패'로 간주해 그 축을 이번 사이클만 보존한다.
        if snap is not None:
            include_tables = _auto_axis_trusted(
                schema_key, "t", include_tables, inventory["t"], snap.get("t") or {}, report)
            include_routines = _auto_axis_trusted(
                schema_key, "r", include_routines, inventory["r"], snap.get("r") or {}, report)
            if not include_tables and not include_routines:
                return
            inventory = _auto_structure_inventory(current_table_fps, routine_inventory,
                                                  include_tables=include_tables,
                                                  include_routines=include_routines)
        if snap is None:
            # baseline 확립 — 첫 관측(또는 스냅샷 파손 복구)은 후보 0. 다음 변경부터 감지된다.
            _save_auto_snapshot(mem_conn, snap_key,
                                dict(inventory, tb=include_tables, rb=include_routines))
            _auto_note_status(schema_key, "baseline", 0, report)
            return
        # 이번에 처음 켜진 축 = 그 축만 baseline 확립(대조 제외). 관측 공백 뒤 전량 오탐 차단.
        t_new_baseline = include_tables and not snap.get("tb")
        r_new_baseline = include_routines and not snap.get("rb")
        changes, absorbed = _auto_structure_changes(
            scope_key, schema_label, snap, inventory,
            include_tables=include_tables and not t_new_baseline,
            include_routines=include_routines and not r_new_baseline)
        if isinstance(report, dict) and changes:
            report["auto_reanalysis_candidates"] = int(
                report.get("auto_reanalysis_candidates", 0)) + len(changes)
        # shadow 판정은 `enqueue_change_analysis` 안에 있다(재검증 C3 — 안전 모드가 호출자 규율에
        # 의존하면 다른 진입점이 우회한다). shadow 면 status='shadow' + seeded 0 으로 돌아오므로
        # 아래 스냅샷 전진 로직이 그대로 "미전진 = 계측만" 이 된다(축 baseline 확립은 유지).
        seeded = set()
        status = ""
        if changes:
            from . import node_analysis as _node_analysis
            rep = _node_analysis.enqueue_change_analysis(
                scope_key, schema_key, [c[0] for c in changes], reason="structure_changed") or {}
            status = str(rep.get("status") or "")
            seeded = set(rep.get("seeded_keys") or [])
            if isinstance(report, dict) and seeded:
                report["auto_reanalysis_seeded"] = int(
                    report.get("auto_reanalysis_seeded", 0)) + len(seeded)
            _auto_note_status(schema_key, status or "unknown", len(changes), report,
                              seeded=len(seeded), run_id=rep.get("run_id"),
                              absorbed=len(absorbed))
        else:
            # feature-0035(ITEM-11): 구조 변경이 없는 사이클에 **커버리지**를 중요도 순으로
            #   채운다. 지금까지 분석 대상은 "사용자가 클릭한 노드 + 이웃"뿐이라 커버리지가
            #   중요도와 무관하게 편향됐고(라이브 11.9%), 그 편향이 클러스터 요약·대화 grounding
            #   품질의 상한이 된다. 시드 큐잉은 change 경로와 **같은 함수**를 쓴다 — 자격·그래프
            #   실재·cap·쿨다운·busy 가드를 두 번 구현하지 않는다.
            _seed_coverage_targets(scope_key, schema_key, schema_label, report)
        # 스냅샷 갱신 — 관측한 축만: 삭제 반영 + **시드 성공분만** 새 지문으로 전진.
        # 새로 켜진 축(t/r_new_baseline)은 대조 없이 인벤토리 전량을 baseline 으로 굳힌다.
        if not include_tables:
            next_t = dict(snap.get("t") or {})
        elif t_new_baseline:
            next_t = dict(inventory["t"])
        else:
            next_t = {k: v for k, v in (snap.get("t") or {}).items() if k in inventory["t"]}
        if not include_routines:
            next_r = dict(snap.get("r") or {})
        elif r_new_baseline:
            next_r = dict(inventory["r"])
        else:
            next_r = {k: v for k, v in (snap.get("r") or {}).items() if k in inventory["r"]}
        next_snap = {"t": next_t, "r": next_r,
                     "tb": bool(snap.get("tb")) or include_tables,
                     "rb": bool(snap.get("rb")) or include_routines}
        for node_key, kind, name, fp in changes:
            if node_key in seeded:
                next_snap["t" if kind == "t" else "r"][name] = fp
        # 흡수분(동일 구조 샤드)은 시드하지 않지만 **즉시 반영** — 안 하면 매 사이클 재탐지된다.
        for kind, name, fp in absorbed:
            next_snap["t" if kind == "t" else "r"][name] = fp
        if isinstance(report, dict) and absorbed:
            report["auto_reanalysis_absorbed"] = int(
                report.get("auto_reanalysis_absorbed", 0)) + len(absorbed)
        if next_snap != {"t": snap.get("t") or {}, "r": snap.get("r") or {},
                         "tb": bool(snap.get("tb")), "rb": bool(snap.get("rb"))}:
            _save_auto_snapshot(mem_conn, snap_key, next_snap)
        if (t_new_baseline or r_new_baseline) and not changes:
            _auto_note_status(schema_key, "baseline", 0, report, absorbed=len(absorbed))
        elif absorbed and not changes:
            # 샤드만 새로 생긴 사이클 — 시드 0 이라 위 status 로그가 안 남는데, 그 사이클이야말로
            # 샤드 흡수 방어가 실제로 일한 순간이다. 로그 없이는 하루 경계 관측이 불가능하다.
            _auto_note_status(schema_key, "absorbed_only", 0, report, absorbed=len(absorbed))
    except Exception:
        # 카운터 없이 WARN 만 남기면, 자격 스키마에서 KV 파손·드라이버 예외가 **매 사이클** 나도
        # payload 는 `candidates=0 · seeded=0` 으로 "건강한 무변경" 과 똑같이 보인다 — 그러면
        # POST-DEPLOY 의 "오탐 0" 판정이 관측이 아니라 추론이 된다(적대 리뷰 C2).
        if isinstance(report, dict):
            report["auto_reanalysis_errors"] = int(report.get("auto_reanalysis_errors", 0)) + 1
        log.warning("auto_reanalysis_failed schema=%s", schema_key, exc_info=True)


#: 무발동 status — telemetry `auto_reanalysis_blocked` 로 집계(운영자가 "왜 안 도는가"를 수치로 본다).
_AUTO_BLOCKED_STATUSES = frozenset({"ineligible", "cooldown", "busy", "disabled", "noop"})
#: 발동도 차단도 아닌 **정상 진행 상태** — 카운터 없이 로그로만 관측한다. blocked 로 세면 "왜 안
#  도는가" 집계가 부풀고, unknown(malformed) 으로 세면 정상 동작이 오류로 보인다.
_AUTO_INFO_STATUSES = frozenset({"baseline", "absorbed_only"})


def _collect_priority_stats(scope_key, targets, report) -> int:
    """선정된 우선순위 테이블의 **L0 통계 증거**를 수집한다. 반환: 시도한 테이블 수.

    LLM 을 부르지 않는다 — 운영 DB 에서 카탈로그·표본 통계만 읽는다. 수집 깊이·주기·시간창
    판정과 운영 DB 연결의 `ds` 자원 예산 게이트는 전부 `metadata_stats.ensure_stats` 안에
    있으므로 여기서 다시 만들지 않는다(안전장치가 두 벌이 되면 서로를 모른다).

    ## 왜 별 스케줄러를 두지 않는가

    `metadata_stats` 의 원 설계는 「분석되는 테이블만 본다 — 쓰이지 않을 통계를 미리 모으는
    낭비가 없다」였다. 그 원칙을 지키려면 **분석 대상 선정**에 붙어야 하는데, 그 선정
    (`analysis_planner.select_priority_targets`)은 LLM 무관이고 지금도 정상 동작한다. 게이트에
    막힌 것은 그 뒤의 *분석*뿐이다. 그래서 선정에 붙이고 분석에는 붙이지 않는다.

    ## 실패

    테이블 단위 fail-soft. 한 테이블의 수집 실패가 나머지·상위 사이클을 막지 않는다
    (`ensure_stats` 자체가 이미 모든 예외를 삼키지만, 연결·해소 단계도 여기서 감싼다).
    """
    attempted = 0
    try:
        from . import metadata_stats as _ms
        if not _ms.enabled():
            return 0
        from . import node_analysis as _na
        ds = _na._resolve_datasource_by_scope(scope_key)
        if not ds:
            return 0
        from shared import db as _db
        # RW 연결 — `collect_table` 이 `metadata_*_stats` 에 upsert 한다(RO 로는 실패).
        c = _db._pg_connect(autocommit=True)
        if c is None:
            return 0
        try:
            for node_key in targets:
                # node_key = `<datasource>:<eff_schema>.<table>` (planner 반환 규약).
                try:
                    _scope, _rest = str(node_key).split(":", 1)
                    _schema, _table = _rest.split(".", 1)
                except ValueError:
                    continue
                if not _schema or not _table:
                    continue
                _ms.ensure_stats(ds, c, _scope, _schema, _table)
                attempted += 1
        finally:
            try:
                c.close()
            except Exception:
                pass
    except Exception as exc:
        logging.getLogger("insight").debug(
            "priority_stats_failed scope=%s err=%r", scope_key, exc)
    finally:
        # 계측은 **finally 에서** 한다 — 중간에 터지면 그때까지 시도한 수도 잃는 게 종전이었고,
        # 그러면 「부분 실패」가 「아예 안 돌았다」로 보인다(§16.7 G9 — 계측이 사실보다 어두우면
        # 재발 신호를 놓친다). 이 값이 0 으로 굳으면 증거층이 다시 멈춘 것이다.
        if attempted and isinstance(report, dict):
            report["stats_collect_attempted"] = int(
                report.get("stats_collect_attempted", 0)) + attempted
    return attempted


def _seed_coverage_targets(scope_key, schema_key, schema_label, report) -> None:
    """중요도 상위 미분석 테이블을 자동 시드(feature-0035 ITEM-11). 전 경로 예외 흡수.

    구조 변경 감지와 **같은 큐잉 함수**를 쓰되 reason 만 다르다. 이 경로가 자체 cap·쿨다운을
    새로 만들면 자동 LLM 지출의 안전장치가 두 벌이 되어 서로를 모른다.
    """
    try:
        from . import analysis_planner as _planner
        if not _planner.enabled():
            return
        limit = _planner.seed_limit()
        if limit <= 0:
            return
        # ⚠ 사이클 전역 상한(codex): 이 함수는 effective-schema 루프 안에서 불리고 큐잉 경로의
        #   cap·쿨다운은 **스키마 단위**다. 사이클 상한이 없으면 스키마 수만큼 곱해진다.
        #   이미 이 사이클에서 시드한 몫을 빼고 잔여만 요청한다.
        cycle_cap = _planner.cycle_limit()
        if cycle_cap > 0:
            already = int((report or {}).get("coverage_seeded", 0) or 0) if isinstance(report, dict) else 0
            remaining = cycle_cap - already
            if remaining <= 0:
                return
            limit = min(limit, remaining)
        from shared import db as _db
        conn = _db._pg_connect_ro()
        if conn is None:
            return
        try:
            cur = conn.cursor()
            try:
                targets = _planner.select_priority_targets(cur, scope_key, schema_label, limit)
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
        if not targets:
            return
        # ⚠ **증거 수집을 큐잉보다 먼저, 그리고 큐잉 성패와 무관하게** 한다 (2026-09-01).
        #
        #   L0 통계 증거층(feature-0031)은 설계상 LLM 무관이다 — 운영 DB 에서 "통계만" 읽는다.
        #   그런데 유일한 호출부가 `node_analysis._build_payload` 였고, 그 앞의
        #   `enqueue_change_analysis` 가 feature-0043 게이트로 early-return 하면서 **큐에 잡이
        #   안 들어가 → 분석이 안 돌고 → 증거 수집도 통째로 멈췄다.** 라이브 실측(2026-09-01):
        #   `metadata_table_stats` 243행 · `metadata_column_stats` 2,252행이 전환일(08-26) 이후
        #   신규 0. 대조군인 `table_relationships`(LLM 무관 + 직접 호출)는 같은 기간 719건 갱신.
        #
        #   즉 LLM 과 무관한 기능이 **호출 위치 하나 때문에** LLM 게이트에 딸려 죽은 것이다.
        #   여기서 부르면 게이트와 무관하게 증거가 쌓이고, 게이트가 열리는 날 분석이 곧바로
        #   증거 위에서 시작한다(§16.7 G8-a — 결정의 적용면은 호출 경로 전체다).
        _collect_priority_stats(scope_key, targets, report)
        from . import node_analysis as _na
        rep = _na.enqueue_change_analysis(
            scope_key, schema_key, targets, reason="coverage_priority",
            requested_by="auto:coverage-planner", cap=limit) or {}
        seeded = len(rep.get("seeded_keys") or [])
        if isinstance(report, dict) and seeded:
            report["coverage_seeded"] = int(report.get("coverage_seeded", 0)) + seeded
        logging.getLogger("insight").info(
            "커버리지 시드 schema=%s 후보=%s 시드=%s status=%s",
            schema_key, len(targets), seeded, rep.get("status"))
    except Exception as exc:
        logging.getLogger("insight").debug("coverage_seed_failed schema=%s err=%r", schema_key, exc)


def _auto_note_status(schema_key: str, status: str, candidates: int, report,
                      seeded: int = 0, run_id=None, absorbed: int = 0) -> None:
    """자동 재분석 결과를 계측 + **상태 변화 시에만** info 로그(무발동 사유도 관측 가능하게).

    적대 리뷰 C1: ineligible / cooldown / busy / 그래프 미투영 같은 무발동은 이전 구현에서 로그도
    카운터도 남기지 않아 "왜 안 도는가" 를 운영자가 진단할 수 없었다. 매 tick 도배를 피하려고
    스키마별 직전 status 와 다를 때만 info, 같으면 debug 로 낮춘다(_LAST_DS_SCAN_STATUS 동형).

    계측은 **int 카운터로만** 남긴다 — report 는 datasource 순회마다 `int/float 합산 · bool OR ·
    그 외 덮어쓰기` 로 병합되므로, dict 를 담으면 마지막 datasource 것만 남아 관측이 소실된다."""
    if isinstance(report, dict) and status:
        if status == "running":
            report["auto_reanalysis_runs"] = int(report.get("auto_reanalysis_runs", 0)) + 1
        elif status == "shadow":
            # 무발동이지만 **의도된 안전 모드** — blocked 와 섞으면 "왜 안 도는가" 집계가 오해를
            # 부른다. 별 카운터가 없으면 payload 가 `candidates>0 · seeded=0 · runs=0 · blocked=0`
            # 을 내보내, "shadow 가 걸려 있다" 와 "enqueue 가 빈 status 로 조용히 실패했다" 를
            # 구별할 수 없다(적대 리뷰 C1).
            report["auto_reanalysis_shadow"] = int(report.get("auto_reanalysis_shadow", 0)) + 1
        elif status in _AUTO_BLOCKED_STATUSES:
            report["auto_reanalysis_blocked"] = int(report.get("auto_reanalysis_blocked", 0)) + 1
        elif status not in _AUTO_INFO_STATUSES:
            # 정상 status 집합 밖 = malformed enqueue 응답. 조용히 묻히면 안 된다.
            report["auto_reanalysis_status_unknown"] = int(
                report.get("auto_reanalysis_status_unknown", 0)) + 1
    changed = _LAST_AUTO_REANALYSIS_STATUS.get(schema_key) != status
    _LAST_AUTO_REANALYSIS_STATUS[schema_key] = status
    log = logging.getLogger("insight")
    # absorbed 를 per-schema 로그에 싣는 이유: 사이클 총합 카운터만으로는 "어느 샤드가 언제
    # 흡수됐는가" 를 역산해야 해서, 하루 경계 관측(TCR.11b)이 사실상 판정 불가다.
    msg = "auto_reanalysis schema=%s status=%s candidates=%s seeded=%s absorbed=%s run=%s"
    if changed or seeded or absorbed:
        log.info(msg, schema_key, status, candidates, seeded, absorbed, run_id)
    else:
        log.debug(msg, schema_key, status, candidates, seeded, absorbed, run_id)


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
    # feature-0040: 서버 스코프 DB 객체(SQL Server Agent 작업)의 제품 경계 필터 + 전량 열거 시
    # 시스템·내부 스키마 차단. **회전 전 전체 목록**으로 고정한다(아래 candidates 는 rotate/cap 으로
    # 잘리므로 그것을 쓰면 tick 마다 필터 범위가 흔들린다). 빈 목록은 dialect 의 `_sql_str_list` 가
    # 매칭 0 으로 닫아 fail-closed 다.
    _do_allow_dbs = tuple(sorted({s.strip().lower() for s in candidates if s.strip()}))
    try:
        _dbobj_sys_exclude = frozenset(_dialects.active().system_schemas()) | frozenset({"agent_memory"})
    except Exception:
        _dbobj_sys_exclude = frozenset({"agent_memory"})
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
                # routine prune 허용 여부 — dialect 명시 플래그(§18.8 재검증 MINOR: `label==schema`
                # 문자열 비교는 MSSQL DB명==스키마명(예: DB 'sales' 의 스키마 'sales') 충돌 시
                # prune=True 로 오발동해 같은 label 의 타 스키마 행을 지운다).
                _rt_prune_ok = True
                try:
                    if _dialects.active().name == "mssql":
                        _rel_db_scope = get_active_database()
                        _rel_store_schema = _rel_db_scope or schema
                        _rt_prune_ok = False
                except Exception:
                    pass
                # change-reanalysis: 그래프 노드 key 의 scope 세그먼트(= datasource). 기본 DS 미지정
                # (.env 레거시 단일 datasource)이면 그래프 투영도 `common:` 접두를 쓰므로
                # (metadata_graph `f"{scope or 'common'}:{fqn}"`) 같은 폴백을 적용한다 — None 으로
                # 두고 skip 하면 그 배치에서 기능이 통째로 미발동한다(적대 리뷰 C-scope).
                # 수동 라우터가 `.strip().lower()` 로 적재하므로 자동 경로도 같은 축(재검증 C1).
                _auto_scope = (get_active_datasource() or "common").strip().lower()
                # MSSQL 은 routine 저장 라벨이 DB(catalog)명이라 한 라벨에 복수 실 스키마의 루틴이
                # 섞이고 prune 도 꺼진다(_rt_prune_ok=False) → 루틴 축은 삭제 반영이 불가해 스냅샷
                # semantics 가 성립하지 않는다. 테이블 축(그래프 키 규약 `db.table`)만 사용한다.
                _auto_routines_dialect_ok = _rt_prune_ok
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
                # change-reanalysis: 이번 스키마의 **루틴 전량 인벤토리**(자동 재분석 스냅샷 대조 입력).
                # `"routines"` 키는 완전 스캔일 때만 채워진다 — 절단·미발화면 키가 없고, 그 경우
                # 루틴 축을 꺼서(include_routines=False) 스냅샷을 보존한다.
                _rt_sink: dict = {}
                if AGENT_ROUTINE_INTROSPECT_ENABLED and rel_maintenance_due:
                    try:
                        from . import routines as _routines
                        _rt_scope = get_active_datasource()
                        # routine-dbanalysis(§53 MAJOR): prune 은 (scope, store-label) 범위 삭제라
                        # MSSQL(store label=DB명 ≠ 질의 schema)은 같은 label 의 **다른 스키마 행**을
                        # 되지운다(backfill 결과가 ≤6h cadence 에 회귀) → dialect 플래그로 억제.
                        # MSSQL stale routine 의 prune 책임은 스키마 전모를 아는 backfill 로 이관(T53.9).
                        _n_rt = _routines.introspect_and_store(
                            db_conn, schema, all_table_names,
                            kb_conn=None, scope_key=_rt_scope,
                            datasource_key=str(_rt_scope or ""), source_run_id=run_id,
                            store_schema=_rel_store_schema,
                            cap=AGENT_ROUTINE_INTROSPECT_CAP,
                            prune=_rt_prune_ok,
                            inventory_sink=_rt_sink)
                        report["routines_introspected"] = int(
                            report.get("routines_introspected", 0)) + int(_n_rt or 0)
                    except Exception:
                        logging.getLogger("insight").warning(
                            "routine_introspect_failed schema=%s", schema, exc_info=True)

                # feature-0040 db-object-explorer: 역할 기반 DB 객체(뷰·트리거·예약작업·별칭·
                # 시퀀스) introspect → db_objects SSOT. 루틴 훅과 **같은 게이트·같은 규약**이며,
                # 실 스키마(schema)로 질의하고 저장 라벨은 _rel_store_schema(MSSQL=DB명)를 쓴다.
                # prune 은 루틴과 동일하게 MSSQL 에서 억제한다(_rt_prune_ok — 한 라벨에 복수 실
                # 스키마가 섞여 뒤 스키마가 앞 스키마 행을 되지우는 §53 MAJOR 와 동형).
                # 전부 guarded — insight 스캔을 절대 차단하지 않는다(B-F7: 실패는 경고 1줄).
                if AGENT_DB_OBJECT_INTROSPECT_ENABLED and rel_maintenance_due:
                    try:
                        from . import db_objects as _dbobj
                        _do_scope = get_active_datasource()
                        _n_do = _dbobj.introspect_and_store(
                            db_conn, schema, all_table_names,
                            dialect=_dialects.active(), kb_conn=None, scope_key=_do_scope,
                            datasource_key=str(_do_scope or ""), source_run_id=run_id,
                            store_schema=_rel_store_schema,
                            sql_schema=(schema if _rel_db_scope else ""),
                            cap=AGENT_DB_OBJECT_INTROSPECT_CAP,
                            prune=_rt_prune_ok,
                            # 서버 스코프 객체(SQL Server Agent 작업)의 제품 경계 필터.
                            # **rotate 된 이번 tick 의 candidates 가 아니라 datasource 의 전체 DB
                            # 목록**을 쓴다 — 회전 대상만 넘기면 이번 tick 에 안 뽑힌 DB 를 대상으로
                            # 하는 작업이 필터에서 탈락하고, 다음 tick 에 다시 나타나 진동한다.
                            allow_dbs=_do_allow_dbs,
                            sys_exclude_schemas=_dbobj_sys_exclude)
                        # inventory_sink 미전달(의도) — change-reanalysis 스냅샷은 테이블("t")·
                        # 루틴("r") **2축 모델**이라(`_auto_axis_trusted`·`snap` 키) 제3축을 넣으려면
                        # 스냅샷 스키마와 신뢰 판정을 함께 확장해야 한다. 소비처 없는 키를 지금
                        # 채우면 "변경 감지가 된다" 는 인상만 남고 실제로는 무시된다 → 이번 cycle 은
                        # 축을 늘리지 않고, 능동 분석 편입은 node_analysis 시드 경로로 수행한다.
                        # (db_objects.introspect_and_store 는 sink 인자를 이미 지원한다 — 후속
                        #  cycle 이 스냅샷을 3축으로 확장할 때 호출부만 바꾸면 된다.)
                        report["db_objects_introspected"] = int(
                            report.get("db_objects_introspected", 0)) + int(_n_do or 0)
                    except Exception:
                        logging.getLogger("insight").warning(
                            "db_object_introspect_failed schema=%s", schema, exc_info=True)

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
                    # change-reanalysis: 테이블이 없는(프로시저·함수만 있는) 스키마도 루틴 변동은 트리거.
                    # 테이블 축은 '진짜 0' 이므로 켠 채로 둔다(삭제 반영이 정상 동작).
                    _auto_reanalyze_structure_changes(
                        mem_conn, _auto_scope, _rel_store_schema, probe_schema=schema,
                        current_table_fps={}, routine_inventory=_rt_sink.get("routines"),
                        include_tables=True,
                        include_routines=_auto_routines_dialect_ok and "routines" in _rt_sink,
                        report=report)
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

                # change-reanalysis(사용자 결정 2026-07-27): 'DB 전체 AI 능동 분석' 이력이 있는 스키마에서
                # 신규 테이블·컬럼 구성 변경·루틴 신규/정의 변경이 감지되면, 사용자가 그래프 뷰에서 다시
                # 실행하지 않아도 그 노드를 시드로 재귀 분석 run 을 자동 생성한다. 여기서 후보를 만드는
                # 이유는 이 시점이 스키마의 **테이블·루틴 변동 신호가 모두 모인 유일한 지점**이기 때문
                # (insight artifact 선정/발행 성공 여부와 무관하게 구조 변동 자체를 신호로 쓴다).
                # 테이블 축은 지문 계산이 실제로 성공했을 때만 신뢰한다 — 조회 실패로 빈 dict 이
                # 오면 '전 테이블 삭제' 로 읽혀 스냅샷이 비고, 다음 사이클에 전량이 '신규' 로
                # 재탐지돼 승인 없는 대량 LLM 지출이 된다.
                _auto_reanalyze_structure_changes(
                    mem_conn, _auto_scope, _rel_store_schema, probe_schema=schema,
                    current_table_fps=current_table_fps,
                    routine_inventory=_rt_sink.get("routines"),
                    include_tables=bool(current_table_fps),
                    include_routines=_auto_routines_dialect_ok and "routines" in _rt_sink,
                    report=report)

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
                        if kv_insight is None:
                            # 개인 AI 가 앞선 cycle 에 답해 둔 것 (TASK-20260901T190000).
                            # 그룹 KV 다음에 보는 이유: 그룹 상속이 더 넓은 재사용이고,
                            # 위임 결과는 그 그물에 안 걸린 테이블을 채우는 축이다.
                            kv_insight = _load_delegated_insight_kv(
                                mem_conn, table_key, current_table_fps.get(table, ""))
                            if isinstance(kv_insight, dict):
                                insight_via = "delegated"
                        if isinstance(kv_insight, dict):
                            table_insight = kv_insight                    # 이전 cycle 대표 상속(LLM 0)
                            if insight_via != "delegated":
                                insight_via = "kv_inherit"
                            if sig is not None:
                                group_insight_cache[sig] = kv_insight
                        elif not server_llm_enabled():
                            # 서버 계정 LLM 이 닫혀 있다 — **호출하지 않고 위임한다.**
                            # `table_insight` 는 None 인 채로 두어 이번 cycle 은 종전의
                            # 「미분석」과 똑같이 흐른다(발행 없음 · 오류 기록 없음).
                            # 오류 문구를 넣지 않는 이유: 이것은 실패가 아니라 대기다.
                            if _delegate_table_insight(mem_conn, table_key,
                                                       current_table_fps.get(table, ""),
                                                       table_payload, schema, table):
                                report["insight_delegated"] = int(
                                    report.get("insight_delegated", 0)) + 1
                            else:
                                report["insight_delegate_skipped"] = int(
                                    report.get("insight_delegate_skipped", 0)) + 1
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


# ── mssql-auth-cooldown (2026-07-10, codex 디스크 I/O 장애조사 트랙 B) ────────────────────
# MSSQL datasource 의 **로그인 자체 실패**(18456 "Login failed for user")는 계정·비밀번호·잠금 문제라
# 운영자 개입(계정 수정 / bin/datasource-mssql-ro-bootstrap-multidb.sql) 전까지 불변이다. 한 datasource
# 의 등록 DB(WebProductDatabases)를 모두 같은 로그인으로 붙으므로 로그인이 실패하면 나머지 DB 도 실패가
# 확정적 → cycle 내 나머지 DB 순회를 중단(break)하고, 그 datasource 를 cooldown 에 넣어 다음 cycle 부터
# 진입 자체를 통째 skip 한다(반복 재연결·로그·후속 I/O 폭발 차단).
#
# **cooldown 키 = datasource label(_ds_key), scope_key 아님 (REV-20260710 HIGH-1 흡수)**: scope_key 는
# compute_scope_key 가 engine+host+port 만 해시하고 **login 을 제외**하므로, 같은 host:port 에 서로 다른
# 계정으로 등록된 두 datasource 가 동일 scope_key 를 공유한다. cooldown 을 scope_key 로 키잉하면 잘못된
# 계정 A 의 18456 이 정상 계정 B 까지 연쇄 차단해, shared/db.py _is_connect_breaker_failure 가 auth 를
# network breaker 에서 의도적으로 제외한 바로 그 anti-contamination 불변식("한 계정 자격오류가 같은 서버
# 다른 계정 게이트를 열지 않게")을 되돌린다. datasource label 은 계정과 1:1 이므로 계정별로 격리된다
# (label rename 은 600s 휘발 상태라 손실돼도 다음 cycle 재평가 — 무해).
#
# **로그인 실패에만 적용 (REV-20260710 HIGH-2 흡수)**: 916("Cannot open database" — DB별 접근권)·229·297
# (객체별 권한)은 로그인은 성공한 상태라 같은 datasource 의 다른 DB 는 정상 접근 가능하다. 이들엔 scope-wide
# skip 을 적용하지 않고 해당 DB 만 실패로 기록하고 순회를 계속한다(_is_login_failure 만 break+cooldown 트리거).
#
# conn_health 의 network circuit-breaker 는 auth 를 의도적으로 제외하므로, auth 억제는 network backoff 와
# 분리된 별도 cooldown 을 여기 insight 레벨에 둔다. 단일 insight-worker 프로세스가 cycle 을 직렬로 도므로
# 모듈-레벨 dict 로 충분(_LAST_DS_SCAN_STATUS 와 동형). key=datasource label → cooldown_until(monotonic).
_DS_AUTH_COOLDOWN: dict[str, float] = {}


def _ds_auth_cooldown_active(ds_key) -> bool:
    """해당 datasource 가 로그인실패 cooldown 중이면 True. 만료됐으면 False + 자동 정리.
    monotonic 시계 사용(wall-clock 조정 무관). ds_key 없으면 False."""
    if not ds_key:
        return False
    until = _DS_AUTH_COOLDOWN.get(ds_key)
    if until is None:
        return False
    if time.monotonic() >= until:
        _DS_AUTH_COOLDOWN.pop(ds_key, None)  # 만료 — 다음 cycle 재시도 1회 허용(자동 복구 경로)
        return False
    return True


def _ds_auth_cooldown_set(ds_key) -> None:
    """로그인 실패가 확정된 datasource 를 cooldown 에 넣는다(AGENT_INSIGHT_AUTH_COOLDOWN_SEC 초).
    0 이면 no-op(cooldown 비활성 — cycle 내 skip 만 유효, 다음 cycle 은 재시도)."""
    if not ds_key:
        return
    ttl = int(AGENT_INSIGHT_AUTH_COOLDOWN_SEC or 0)
    if ttl <= 0:
        return
    _DS_AUTH_COOLDOWN[ds_key] = time.monotonic() + ttl


def _ds_auth_cooldown_clear(ds_key) -> None:
    """스캔 성공 시 cooldown 해제. 복구 경로는 두 가지: (1) cooldown 만료(TTL) 후 재시도가 성공하면 이
    clear 가 재-set 을 막아 정상 유지, (2) cooldown 비활성(ttl=0)일 땐 매 cycle 성공이 바로 정상. cooldown
    **활성** 중에는 진입 gate 가 continue 하므로 이 성공 경로에 도달하지 않는다(복구는 TTL 만료가 담당)."""
    if ds_key:
        _DS_AUTH_COOLDOWN.pop(ds_key, None)


def _prune_auth_cooldown(live_ds_keys: "set") -> None:
    """등록 해제/rename 된 datasource 의 cooldown 항목을 정리(_LAST_DS_SCAN_STATUS prune 과 대칭).
    만료 자동 pop 은 그 키가 다시 조회돼야 발동하는데, 삭제/rename 시엔 재조회되지 않아 영영 잔존하므로
    매 cycle 현재 등록 datasource label 집합으로 prune 한다(누수 차단)."""
    for _k in [k for k in _DS_AUTH_COOLDOWN if k not in live_ds_keys]:
        _DS_AUTH_COOLDOWN.pop(_k, None)

# ── TASK-0255 R2: datasource 연결 health PG 영속 (agent_runtime.datasource_health) ──
# 관리콘솔이 "연결 불안정으로 미커버"(status=unstable/circuit_open)를 "권한 실패"(perm_failed)와
# 구분해 표면화할 수 있게, datasource 별 연결 상태를 PG 정본에 upsert 한다. 자격증명 비영속.
_DS_HEALTH_UPSERT_SQL = """
INSERT INTO agent_runtime.datasource_health
  (scope_key, datasource_label, engine, host, port, status, last_scan_outcome,
   fail_count, last_error_tag, last_checked_at, last_scan_at, last_transition_at, run_id, updated_at)
VALUES (%(scope_key)s, %(label)s, %(engine)s, %(host)s, %(port)s, %(status)s, %(scan_outcome)s,
        %(fail_count)s, %(last_error_tag)s,
        -- ⚠ 캐스트가 **필수**다 (2026-09-02 라이브). 같은 파라미터가 `IS NULL`(타입 미상)과
        --   `to_timestamp()`(double precision) 두 문맥에 쓰이는데, 값이 None 이면 드라이버가
        --   타입 없는 NULL 을 보내고 Postgres 가 추론에 실패한다 → 42P08 AmbiguousParameter.
        --   값이 float 일 때는 통과하므로 **한 번도 체크되지 않은 datasource 가 섞일 때만**
        --   터졌고, 그 한 행이 batch 전체를 되돌려 health 텔레메트리가 통째로 유실됐다.
        CASE WHEN %(last_checked_at)s::double precision IS NULL THEN NULL
             ELSE to_timestamp(%(last_checked_at)s::double precision) END,
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


def _self_heal_scope_keys(mem_conn, ds_scope: str) -> "list[str]":
    """ENUM self-heal 대상 scope 목록 — 이 datasource **에만** 바인딩된 제품들의 제품 스코프.

    metadata-product-scope: 저장 축이 제품이라 sweep 도 제품 스코프여야 회수가 된다. 단 sweep 은
    `known_schemas` 밖 schema 를 삭제하므로 그 목록이 대상 스코프에 **완전**해야 하고, 이번 tick 의
    목록은 이 datasource 하나의 것이다 → **단일 DS 제품만** 포함한다(다중 DS 제품은 다른 DS 의 정상
    enum 을 오삭제할 수 있어 제외 = fail-open). 'common' 은 datasource 귀속이 없어 제외.
    조회 실패 시 [] (self-heal 생략 — 파괴적 동작이므로 보수적).
    """
    sk = str(ds_scope or "").strip().lower()
    if not sk or sk == "common":
        return []
    from shared import config as _cfg
    from shared import datasources as _dsr
    try:
        ds_map = _dsr.all_datasources(mem_conn) or {}
    except Exception:
        return []
    # 이 scope 에 해당하는 datasource 라벨(read 축: scope_key 필드 우선, 없으면 라벨).
    labels = {str(lbl).strip().lower() for lbl, ds in ds_map.items()
              if str((ds.get("scope_key") or ds.get("key") or lbl) or "").strip().lower() == sk}
    if not labels:
        return []
    # 제품별 바인딩 목록을 모아 '이 datasource 뿐인 제품'만 남긴다.
    binds: dict = {}
    try:
        cur = mem_conn.cursor()
        try:
            cur.execute("SELECT p.Id, p.ProductKey, LOWER(d.DatasourceKey) "
                        "FROM WebProducts p JOIN WebProductDatasources d ON d.ProductId = p.Id "
                        "WHERE p.IsActive = 1")
            for row in (cur.fetchall() or []):
                pid, pkey, dsk = (row[0], row[1], row[2])
                binds.setdefault((int(pid or 0), str(pkey or "")), set()).add(str(dsk or "").strip().lower())
        finally:
            cur.close()
    except Exception:
        binds = {}   # join 테이블 부재(레거시) — 아래 단일 바인딩 폴백으로 이어간다
    # 레거시 단일 바인딩(WebProducts.DatasourceKey) 폴백 — join 행이 없는 제품만 보충한다.
    # 빠뜨리면 미이전 배치에서 self-heal 이 통째로 죽어 stale/환각 ENUM 이 계속 주입된다.
    try:
        cur = mem_conn.cursor()
        try:
            cur.execute("SELECT Id, ProductKey, LOWER(DatasourceKey) FROM WebProducts "
                        "WHERE IsActive = 1 AND DatasourceKey IS NOT NULL AND DatasourceKey <> ''")
            for row in (cur.fetchall() or []):
                pid, pkey, dsk = (int(row[0] or 0), str(row[1] or ""), str(row[2] or "").strip().lower())
                if not pkey or not dsk:
                    continue
                if (pid, pkey) in binds:
                    continue   # join 바인딩이 이미 있으면 그쪽이 정본(다중 DS 판정 포함)
                binds[(pid, pkey)] = {dsk}
        finally:
            cur.close()
    except Exception:
        if not binds:
            return []
    out: list = []
    for (pid, pkey), bound in binds.items():
        if not pkey or len(bound) != 1:
            continue          # 다중 DS 제품 — known_schemas 불완전 → 제외(오삭제 방지)
        if not (bound & labels):
            continue          # 이 datasource 제품이 아님
        scope = _cfg.product_scope_key(pkey)
        if scope:
            out.append(scope)
    return out


def _enum_self_heal(swept_scopes: set, *, mem_conn, engine, known_schemas, scanned) -> "dict | None":
    """활성 datasource scope 의 '없는 DB(schema)' ENUM 소급 자가수리 (insight tick else-block, best-effort).

    스캔이 예외 없이 완료(카탈로그 refresh)됐고 scope ContextVar 가 유효한 else 지점에서 호출된다. 방금
    로드된 **완전한** 실제 스키마 목록(`_scan_schemas` = load_known_schemas — budget 무관·전량)을 기준으로,
    그 scope 의 enum 중 `schema_name`(=DB)이 실재하지 않는 항목(예: auth scope 에 없는 `dbLog.*`)을 회수한다.
    (a) 예방 게이트 도입 전 등록된 환각, (b) 예방 게이트 fail-open 창에 유입된 환각, (c) DB 삭제로 사후
    ungrounded 가 된 항목의 소급 정리 — 예방 게이트(_enum_autopropose)와 상호보완.

    안전 설계(적대 리뷰 BLOCKER/MAJOR/MINOR 흡수):
    - **실제 스키마 목록 기준**(table_insight 점진 카탈로그가 아님) → 목록이 완전하므로 legit enum
      false-deletion 없음. `schema_name` 이 **빈** enum 은 건드리지 않는다(DB 판정 불가 — 안전).
    - **MySQL-family 전용(allowlist)**: schema==database 라 known_schemas 가 곧 실제 DB 목록. MySQL 이 아니면
      (MSSQL 등 schema≠database) 제외(오삭제 방지 — 수동 스크립트로 정리). engine 미지정은 기본 MySQL 로 간주.
    - **catalog-shrink 가드(MINOR-A)**: 스키마 부재를 **직전 scanned tick + 이번 tick 2회 연속** 관측할 때만
      삭제(per-scope KV persistence). 권한 회수/부분조회로 known_schemas 가 일시 축소된 tick 의 오삭제 흡수.
    - **`scanned`(이번 tick 실제 스캔) 게이트**: 매 8s tick 낭비/파괴 반복 방지(refresh 발생 시에만).
    - **예방 게이트(AGENT_ENUM_SCHEMA_GROUNDING)와 결합**: 게이트 off(운영자 무검증 허용)면 self-heal 도 no-op.
      `AGENT_ENUM_SELF_HEAL=0` 이면 비활성.
    - cycle-local dedup(`swept_scopes`), source='auto' 만 DELETE(수동 큐레이션 보존), 예외는 tick 비전파.
    반환: 변경 있었으면 sweep 결과 dict, 아니면 None.
    """
    try:
        from shared import config as _cfg
        # 예방 게이트 결합 + self-heal 스위치: 둘 다 on 일 때만 파괴적 grounding 강제.
        if not (getattr(_cfg, "AGENT_ENUM_SCHEMA_GROUNDING", True)
                and getattr(_cfg, "AGENT_ENUM_SELF_HEAL", True)):
            return None
        if not scanned:
            return None  # 이번 tick 에 실제 카탈로그 스캔이 일어났을 때만(매 tick 낭비/파괴 반복 방지)
        if str(engine or "mysql").strip().lower() != "mysql":
            return None  # MySQL(schema==database)만 — MSSQL 등은 오삭제 위험, self-heal 제외(수동 스크립트)
        if not known_schemas:
            return None  # 실제 스키마 목록 미확보 → fail-open(오삭제 방지)
        # metadata-product-scope: ENUM 은 이제 **제품 스코프**(`product.<key>`)에 저장된다 —
        # datasource scope 로 sweep 하면 자율수집분이 영영 회수되지 않아 환각/stale 값이 주입에 남는다.
        # 다만 sweep 은 `known_schemas` 밖 schema 를 **삭제**하므로, 그 목록이 그 스코프에 대해
        # **완전**해야만 안전하다. 이번 tick 의 known_schemas 는 *이 datasource 하나*의 것이므로,
        # **이 datasource 에만 바인딩된 제품**(단일 DS 제품)의 스코프만 sweep 한다 — 여러 datasource 에
        # 걸친 제품을 여기서 sweep 하면 다른 DS 의 정상 enum 이 '없는 스키마'로 오삭제된다(fail-open 유지).
        _ds_scope = _cfg.get_active_datasource() or "common"
        scope_keys = _self_heal_scope_keys(mem_conn, _ds_scope)
        scope_keys = [sk for sk in scope_keys if sk not in swept_scopes]
        if not scope_keys:
            return None
        swept_scopes.update(scope_keys)  # 성공/실패 무관 이번 cycle 재시도 방지(다음 cycle 재시도)
        scope_key = scope_keys[0]  # KV 키/로그 대표값(아래 sweep 은 scope_keys 전체 순회)
        from shared.db import _pg_available, _pg_connect
        if not _pg_available():
            return None
        # catalog-shrink 가드: 직전 scanned tick 의 unknown 스키마 집합(per-scope KV)을 로드.
        _prev_key = _cfg.ds_scope_name("enum_self_heal_prev_unknown")
        _prev_unknown: set = set()
        try:
            _raw = load_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, _prev_key)
            if _raw:
                _prev_unknown = {str(s).strip().lower() for s in json.loads(_raw) if str(s or "").strip()}
        except Exception:
            _prev_unknown = set()
        from modules import kb_glossary as _kg
        pg = _pg_connect(autocommit=False)
        try:
            res = {"ungrounded": [], "dict_deleted": 0, "feedback_rejected": 0}
            for _sk in scope_keys:
                _r = _kg.sweep_unknown_schema_enum(
                    pg, _sk, known_schemas, dry_run=False, confirm_lower=_prev_unknown)
                res["ungrounded"].extend(_r.get("ungrounded", []))
                res["dict_deleted"] += int(_r.get("dict_deleted") or 0)
                res["feedback_rejected"] += int(_r.get("feedback_rejected") or 0)
            pg.commit()
        except Exception:
            try:
                pg.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                pg.close()
            except Exception:
                pass
        # 이번 tick 의 unknown 후보(전체)를 다음 scanned tick 의 confirm 집합으로 저장(2회-연속 persistence).
        try:
            _now_unknown = sorted({str(u.get("schema_name") or "").strip().lower()
                                   for u in res.get("ungrounded", []) if str(u.get("schema_name") or "").strip()})
            save_memory_kv(mem_conn, GLOBAL_CONVERSATION_ID, _prev_key, json.dumps(_now_unknown))
        except Exception:
            pass
        if res.get("dict_deleted") or res.get("feedback_rejected"):
            logging.getLogger("insight").info(
                "enum_self_heal scope=%s unknown_schemas=%d dict_deleted=%s feedback_rejected=%s",
                scope_key, len(res["ungrounded"]), res["dict_deleted"], res["feedback_rejected"],
            )
            return res
        return None
    except Exception:
        logging.getLogger("insight").debug("enum_self_heal 실패(무시)", exc_info=True)
        return None


def run_insight_cycle(run_id: str | None = None) -> dict[str, Any]:
    # feature-0043 사용감 패리티 — 게이트는 **cycle 전체가 아니라 LLM 구간에만** 건다.
    #
    # 첫 시도는 cycle 진입부에서 통째로 early-return 했다. 그것이 `finally` 앞이라 worker
    # heartbeat(`insight_worker_last_cycle_at`)가 갱신되지 않았고, 180초 뒤 healthcheck 가
    # exit 1 → **차단 모드에서 컨테이너가 상시 unhealthy** 가 됐다(codex 리뷰 P1). 게다가 LLM 과
    # 무관한 정비(role backfill · enum self-heal · datasource health · auth cooldown prune)까지
    # 함께 멈췄다. "낭비를 줄이려는 최적화" 가 방어를 껐다 — 그래서 되돌리고 좁게 다시 건다.
    #
    # 남은 낭비는 작다: 스캔 안의 LLM 호출은 `_get_llm_client()` 게이트에서 즉시 None 을 받고
    # (로그는 caller 별 60초 throttle) 되돌아온다. 연결·health 점검은 오히려 계속 도는 편이 낫다.
    from shared.llm_gate import server_llm_enabled as _server_llm_open

    _llm_open = _server_llm_open()
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
        # mssql-auth-cooldown: 인증/권한 실패 확정 후 재시도 억제로 **실제 연결 시도 없이** skip 한 DB 수.
        # (cycle 내: 첫 perm_failed 뒤 같은 scope 의 나머지 DB / cycle 간: cooldown 중 datasource 통째 skip).
        # db_failed_perm(실제 시도해 실패)과 분리 — 이 값이 클수록 반복 재연결·I/O 를 성공적으로 억제한 것.
        "db_skipped_auth": 0,
        # L0 통계 증거 수집 시도 수(2026-09-01). **0 으로 굳으면 증거층이 다시 멈춘 것**이다 —
        # 이 카운터가 없던 동안 `metadata_*_stats` 는 전환일 이후 신규 0 이었는데 사이클 payload
        # 어디에도 그 사실이 드러나지 않았다(§16.7 G9 — 보지 않는 면은 조용히 죽는다).
        "stats_collect_attempted": 0,
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
            # feature-0037(ITEM-08): 요청된 스키마만 도메인(L3) 합성. 사전 전량 생성도
            #   답변 경로 런타임 합성도 하지 않기 위해, grounding 이 남긴 요청만 처리한다.
            #   ⚠ **advisory lock 을 얻은 tick 에서만** 돈다(codex P2) — lock 없이 돌면 여러
            #   워커가 같은 스키마를 동시에 합성해 LLM 호출이 중복된다. 노드 분석(claim 기반)과
            #   달리 이 pass 에는 행 단위 claim 이 없다.
            if lock_acquired:
                # feature-0036(ITEM-10): 분석문 ↔ 증거 대조 판정. 어떤 실패도 미검증으로 남을 뿐
                #   분석 흐름을 막지 않는다.
                #   ⚠ 판정 pass 도 **lock 안에서만** 돈다(2026-08-05 적대 패널 지적). 이 pass 에는
                #   `node_analysis.process_pending` 같은 행 단위 claim 이 없어서, 워커를 늘리면
                #   모든 워커가 같은 큐 선두(verdict_at NULLS FIRST — 결정론적)를 동시에 판정해
                #   LLM 콜이 워커 수만큼 중복된다. 게다가 그 중복은 전부 `judged_hash IS NULL` 을
                #   같이 읽으므로 `rejudged` 에도 잡히지 않는다(관측 사각). domain_synthesis 와
                #   같은 이유·같은 처방이다.
                try:
                    from . import analysis_verify as _av
                    # ⚠ 자체 PG 연결을 열게 한다(codex P1) — 이 스코프의 `mem_conn` 은
                    #   agent_memory 이고, agent_kb 커넥션은 여기 없다.
                    _av_rep = _av.run_verification_pass() if _av.enabled() else None
                    # ⚠ `checked` 만 보고 기록하면 **판정에 실패하며 콜만 태우는 pass 가 통째로 무음**이
                    #   된다(2026-08-05 적대 패널). attempted 가 있으면 checked=0 이어도 남긴다 —
                    #   attempted ≫ checked 야말로 봐야 할 신호다.
                    if _av_rep and (_av_rep.get("checked") or _av_rep.get("attempted")):
                        scan_report["analysis_verify"] = _av_rep
                except Exception as _ave:
                    logging.getLogger("insight").debug("analysis_verify_failed err=%r", _ave)
                try:
                    from . import domain_synthesis as _dsyn
                    _ds_rep = _dsyn.run_synthesis_pass() if _dsyn.enabled() else None
                    # ⚠ 카운터가 0 이어도 **돌았다는 사실 자체**를 남긴다. `synthesized` 만 보면
                    #   "콜은 태웠는데 저장 0" 이, attempted 까지 봐도 "요청이 없어 조용한 tick" 과
                    #   "배선이 죽어 조용한 tick" 이 구별되지 않는다 — lazy 생성이라 0 인 tick 이
                    #   대부분이라서, 0 을 안 싣는 순간 이 pass 는 사실상 영구 무음이 된다.
                    if _ds_rep:
                        scan_report["domain_synthesis"] = _ds_rep
                except Exception as _dse:
                    logging.getLogger("insight").debug("domain_synthesis_failed err=%r", _dse)
            # ⚠ **게이트로 감싸지 않는다** (라이브 실측 2026-09-02, TASK-20260901T190000).
            #
            # 종전 주석은 이랬다: "차단 중에는 claim 해서 실패시키지 않는다 — 적재 자체도
            # 게이트로 막혀 있으므로 정상 운영에서 대기 잡은 생기지 않는다." 그 전제가
            # **깨졌다.** 이제 게이트가 닫혀 있어도 적재된다(연결된 개인 AI 가 처리하므로).
            # 그런데 이 줄이 `if _llm_open` 으로 남아 있으면:
            #
            #   · 그래프 능동 분석이 적재돼도 **아무도 처리하지 않는다** — 사용자가 제보한
            #     "막혀 있다" 가 형태만 바꿔 되돌아온다(202 는 뜨는데 결과가 영영 안 온다).
            #   · stale `running` 회수가 **영원히 돌지 않는다** — 러너가 끝내 답하지 않은 잡이
            #     pending 으로 복귀하지 못하고, 그 run 은 `running` 으로 굳어 재트리거를 막는다.
            #     (실측: lease 900초를 1424초까지 넘겼는데 회수되지 않았다.)
            #
            # 판정은 **잡 단위로 함수 안에서** 한다: 게이트가 열렸으면 직접 호출, 닫혔으면
            # 위임, 맡길 곳이 없으면 상한 있는 유예. 그러므로 여기서는 언제나 부른다.
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
            _enum_swept_scopes: set = set()  # enum self-heal cycle-local dedup(같은 scope DB 다중 시 1회만)
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

                # mssql-auth-cooldown: 직전 cycle 에서 이 datasource 의 **로그인 자체**가 실패(18456)해
                # cooldown 중이면 등록 DB 순회를 **연결 시도 없이** 통째로 skip 한다(운영자 계정 수정 전까지
                # 재시도해도 DB 수만큼 동일 로그인 실패 반복 — 반복 재연결·I/O 폭발). conn_health network
                # breaker 는 auth 를 의도적으로 제외하므로 위 circuit 게이트로는 안 걸린다 — 별도 auth cooldown
                # 게이트가 필요하다. **키는 datasource label(_ds_key)** — 같은 host:port 다른 계정 연쇄차단 방지
                # (HIGH-1). discovery 뒤에 두어 db_targets 는 정상 집계하고 db_skipped_auth 를 실제 skip DB 수
                # (len(_db_targets))로 정확히 계상한다(LOW-6). health 는 perm_failed 기록. 만료 시 자동 재개.
                if _ds_key is not None and _ds_auth_cooldown_active(_ds_key):
                    _record_ds_health(ds_health_rows, _ds_scope, _ds_coords, "perm_failed")
                    scan_report["db_skipped_auth"] = int(
                        scan_report.get("db_skipped_auth", 0) or 0) + len(_db_targets)
                    continue

                for _db_idx, _db_name in enumerate(_db_targets):
                    _ds_conn = None
                    _auth_break = False  # mssql-auth-cooldown: perm/auth 실패 확정 시 나머지 DB 순회 중단 신호
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
                            _is_login_failure = False
                        else:
                            # 권한 거부(login failed / cannot open database / SELECT denied)는 가장 흔한 원인이라
                            # 진단 힌트를 덧붙인다 — 다중 DB 는 bin/datasource-mssql-ro-bootstrap-multidb.sql 의
                            # DB별 USER+db_datareader GRANT 미적용 신호(스키마 격리는 -bootstrap.sql). MSSQL 에러번호
                            # (18456/916/229/297)는 짧은 숫자라 무관 메시지(행수 등)에 우연
                            # 매칭될 수 있어 정규식 단어경계로 매칭한다(REV-20260611-0226 — 가짜 힌트 방지).
                            _err_s = str(_ds_exc).lower()
                            _is_perm = (
                                any(t in _err_s for t in
                                    ("login failed", "cannot open database", "permission", "denied"))
                                or bool(re.search(r"\b(18456|916|229|297)\b", _err_s))
                            )
                            # mssql-auth-cooldown (REV-20260710 HIGH-2): scope-wide skip/cooldown 은 **로그인 자체
                            # 실패**(18456 — 계정/비밀번호/잠금)에만 적용한다. 916("Cannot open database" — DB별
                            # 접근권)·229·297(객체별 권한)은 로그인은 성공한 상태라 같은 datasource 의 다른 DB 는
                            # 정상 접근 가능 → 해당 DB 만 실패로 기록하고 순회를 계속한다.
                            # ⚠ 916 실제 메시지는 "Cannot open database … requested by the login. The login failed …"
                            # 로 "login failed" 텍스트를 포함한다 → 텍스트만으론 916 을 로그인실패로 오분류(HIGH-2
                            # 재발). error number 18456 을 우선하고, 번호 없는 순수 텍스트는 "login failed for user"
                            # + "cannot open database" 부재로 916 과 구분한다.
                            _is_login_failure = (
                                bool(re.search(r"\b18456\b", _err_s))
                                or ("login failed for user" in _err_s and "cannot open database" not in _err_s)
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
                        _hint = (" (RO 로그인이 이 DB 에 USER/GRANT 됐는지 확인 — 다중 DB 는 "
                                 "bin/datasource-mssql-ro-bootstrap-multidb.sql, 스키마 격리는 "
                                 "bin/datasource-mssql-ro-bootstrap.sql 을 DB 마다 실행)") if _is_perm else ""
                        _log = logging.getLogger("insight")
                        _seen_scan_keys.add((_ds_scope, _db_name))  # M-1: stale prune 용 이번 cycle 관측 키
                        _changed = _ds_scan_status_changed(_ds_scope, _db_name, _curr)
                        # M-2(자격증명 비노출): raw driver 예외를 %r 로 찍으면 args 에 DSN/계정이 섞일 수 있어
                        # str()[:160] 으로 절단(conn_health last_error 80자 정책과 동형). 진단은 perm_suspect+status 로.
                        (_log.warning if _changed else _log.debug)(
                            "insight_datasource_scan_failed ds=%s db=%s status=%s perm_suspect=%s err=%s — "
                            "%s%s",
                            _ds_key, _db_name, _curr, _is_perm, str(_ds_exc)[:160],
                            ("이 datasource 나머지 DB skip(로그인 실패)" if _is_login_failure else "다음 대상 계속"), _hint,
                        )
                        # mssql-auth-cooldown: **로그인 자체 실패**가 확정되면 이 datasource 를 cooldown 에 넣어
                        # 다음 cycle 부터 진입부에서 통째 skip 하고, 이번 cycle 의 나머지 등록 DB 순회는 아래 finally
                        # 직후 _auth_break 로 중단한다(같은 로그인이라 나머지도 실패 확정 — 재연결 억제). 키는
                        # datasource label(_ds_key) — 같은 host:port 다른 계정 연쇄차단 방지(HIGH-1). 916/229/297
                        # (DB/객체별 권한)은 _is_login_failure=False 라 여기 안 걸리고 해당 DB 만 실패로 계속(HIGH-2).
                        if _is_login_failure and _ds_key:
                            _ds_auth_cooldown_set(_ds_key)
                            _auth_break = True
                    else:
                        # enum self-heal: 스캔이 예외 없이 완료됐고 scope ContextVar 가 아직 유효(finally 리셋 전)한
                        # 이 지점에서, 방금 로드된 **완전한** 실제 스키마 목록(_scan_schemas)으로 '없는 DB' enum 을
                        # 소급 회수한다. `_ds_key is not None` 가드 '앞'에 둬야 기본 단일 MySQL(ds=None, 'common')도 커버.
                        _enum_self_heal(
                            _enum_swept_scopes, mem_conn=mem_conn, engine=_ds_engine,
                            known_schemas=_scan_schemas,
                            scanned=bool(isinstance(_rep, dict) and _rep.get("scan_started")),
                        )
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
                                # mssql-auth-cooldown: 스캔 성공 = 로그인 정상 → cooldown 해제(재-set 방지). cooldown
                                # 활성 중엔 진입 gate 가 continue 하므로 이 경로 도달은 만료(TTL) 후 재시도 성공 시점
                                # 또는 cooldown 비활성(ttl=0) 때다 — 복구 권위는 TTL 만료가 담당(REV-20260710 MEDIUM-3).
                                _ds_auth_cooldown_clear(_ds_key)
                            except Exception:  # pragma: no cover — soft telemetry, cycle 절대 안 깨뜨림
                                pass
                    finally:
                        set_active_datasource(None)  # active_database 도 함께 리셋(set_active_datasource 내부)
                        if _ds_key is not None and _ds_conn is not None:
                            try:
                                _ds_conn.close()
                            except Exception:
                                pass
                    # mssql-auth-cooldown: 인증/권한 실패가 확정된 endpoint 는 이번 cycle 의 나머지 등록 DB
                    # 순회를 중단한다(같은 로그인이라 나머지도 실패 확정 — 반복 재연결·로그·I/O 폭발 차단).
                    # 남은 DB 는 **연결 시도 없이** db_skipped_auth 로 집계(관측성). 다음 cycle 은 진입부
                    # cooldown gate 가 이 scope 를 통째 skip 한다.
                    if _auth_break:
                        _remaining = len(_db_targets) - _db_idx - 1
                        if _remaining > 0:
                            scan_report["db_skipped_auth"] = int(
                                scan_report.get("db_skipped_auth", 0) or 0) + _remaining
                        break
            _timing_breakdown_add(timing, "plan_ms", (time.perf_counter() - plan_start) * 1000.0)
            # TASK-0255 R2: datasource 연결 health 를 PG 정본에 영속(soft telemetry — 실패해도 cycle 계속).
            _persist_datasource_health(ds_health_rows, cycle_run_id)
            # TASK-0255 M-1: in-memory edge-trigger 캐시도 registry 동기 prune(PG prune 과 동형). 이번 cycle 에
            # 관측 안 된 (scope_key, db_name) = 삭제·rename·비활성된 datasource/DB → stale key 제거(메모리 누수 차단).
            for _k in [_k for _k in _LAST_DS_SCAN_STATUS if _k not in _seen_scan_keys]:
                _LAST_DS_SCAN_STATUS.pop(_k, None)
            # mssql-auth-cooldown (REV-20260710 LOW-5): auth cooldown 도 현재 등록 datasource label 집합으로
            # prune. 만료 자동 pop 은 그 키가 재조회돼야 발동하는데, 삭제/rename 된 datasource 는 재조회되지
            # 않아 영영 잔존하므로 여기서 stale 항목을 정리(_LAST_DS_SCAN_STATUS prune 과 대칭).
            _prune_auth_cooldown({k for k, _ in ds_targets if k})
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
                # mssql-auth-cooldown: 인증/권한 실패 확정으로 **연결 시도 없이** skip 한 DB 수(cycle 내 나머지
                # + cooldown 통째 skip). 0 보다 크면 반복 재연결·I/O 를 성공적으로 억제 중이라는 신호.
                save_memory_kv(
                    mem_conn, GLOBAL_CONVERSATION_ID, "insight_worker_last_db_skipped_auth",
                    str(int(scan_report.get("db_skipped_auth", 0) or 0)),
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
            # change-reanalysis(2026-07-27): 승인 없이 LLM 을 쓰는 경로라 "얼마나 발동했나"와
            # "왜 안 발동했나"가 모두 관측 가능해야 한다. 이 payload 는 명시 allow-list 라
            # 여기 등재하지 않으면 어떤 계측도 운영자에게 도달하지 않는다.
            "auto_reanalysis_candidates": int(scan_report.get("auto_reanalysis_candidates", 0) or 0),
            "auto_reanalysis_seeded": int(scan_report.get("auto_reanalysis_seeded", 0) or 0),
            "auto_reanalysis_runs": int(scan_report.get("auto_reanalysis_runs", 0) or 0),
            "auto_reanalysis_blocked": int(scan_report.get("auto_reanalysis_blocked", 0) or 0),
            # POST-DEPLOY 관측(2026-08-03): 아래 2키는 `report` 에 기록되면서도 이 allow-list 에
            # 빠져 있어 7일간 운영자에게 **한 줄도 도달하지 않았다** — 같은 cycle 이 경계했던
            # "allow-list 미등재 = 관측 소실" 을 계측을 늘리며 그대로 반복한 것이다.
            #   absorbed   : 동일 구조 샤드로 흡수돼 LLM 을 태우지 않은 수. 로그도 없어 완전 무음이었고,
            #                하필 발동 DB(log_v2)가 날짜 샤드 DB 라 그 방어의 실효를 볼 수 없었다.
            #   axis_dropped: 관측 실패로 축을 보존한 횟수(전량/과반 소실). WARN 로그는 남지만
            #                집계가 없어 빈도·추세를 볼 수 없었다.
            "auto_reanalysis_absorbed": int(scan_report.get("auto_reanalysis_absorbed", 0) or 0),
            "auto_reanalysis_axis_dropped": int(scan_report.get("auto_reanalysis_axis_dropped", 0) or 0),
        }
    )
    # feature-0026 (M4): 종전엔 cycle 로그에서 빠지던 처리량 신호 — 노드 분석(claimed/done/failed)과
    # 관계 프로브 카운터를 payload 에 포함해 백그라운드 병목(직렬 LLM·프로브 소요)을 로그로 추적 가능하게.
    _na = scan_report.get("node_analysis") or {}
    if _na:
        payload.update({
            "node_analysis_claimed": int(_na.get("claimed", 0) or 0),
            "node_analysis_done": int(_na.get("done", 0) or 0),
            "node_analysis_failed": int(_na.get("failed", 0) or 0),
            # analysis-retry-resilience: terminal 실패와 **backoff 재시도로 되돌린 수**를 분리해 남긴다 —
            #   단절 창(retry_pending 급증, failed 0)과 영구 실패 증가를 로그만으로 구분하기 위함.
            "node_analysis_retry_pending": int(_na.get("retry_pending", 0) or 0),
            # T0(worker-resource-isolation): 공유 LLM 예산이 없어 뒤로 밀린 잡 수 — 실패(failed)·
            #   장애 재시도(retry_pending)와 별 축. 이 값이 지속되면 상한을 올릴 근거가 된다.
            "node_analysis_budget_deferred": int(_na.get("budget_deferred", 0) or 0),
        })
    # feature-0036(2026-08-05): 판정 pass 계측. `scan_report["analysis_verify"]` 는 **dict** 라
    #   `_telemetry_sweep` 의 스칼라 필터에 걸려 통째로 버려진다 — 위 auto_reanalysis 주석이 경계한
    #   "allow-list 미등재 = 관측 소실"의 세 번째 재발을 여기서 막는다. 특히 `rejudged`/`attempted` 는
    #   판정 순환(2026-08-05 회귀)의 유일한 조기 신호라, 도달하지 않으면 계측을 만든 의미가 없다.
    #     attempted : 실제 LLM 콜 수. `checked`(저장 성공)와 크게 벌어지면 판정 실패가 예산을 먹는 중.
    #     rejudged  : 이전 판정이 있는데 다시 판정한 수. pass 마다 cap 을 채우면 대상 선정이 순환한다.
    _av = scan_report.get("analysis_verify") or {}
    if _av:
        payload.update({
            "analysis_verify_checked": int(_av.get("checked", 0) or 0),
            "analysis_verify_attempted": int(_av.get("attempted", 0) or 0),
            "analysis_verify_rejudged": int(_av.get("rejudged", 0) or 0),
            "analysis_verify_contradicted": int(_av.get("contradicted", 0) or 0),
        })
    # feature-0037(2026-08-06): 도메인 합성 계측. `scan_report["domain_synthesis"]` 도 **dict** 라
    #   analysis_verify 와 같은 이유로 sweep 의 스칼라 필터에 걸려 통째로 버려지고 있었다 —
    #   이 워커에서 "계측을 만들고 payload 에 안 실어 무음" 이 반복된 네 번째 사례다.
    #   lazy 생성(요청이 있어야 합성)이라 값이 0인 tick 이 대부분인데, 그래서 더더욱 **돌았는지
    #   여부**가 로그에 남아야 한다(무음과 "요청 없음"이 구별되지 않으면 배선 사망을 못 본다).
    _ds = scan_report.get("domain_synthesis") or {}
    if _ds:
        payload.update({
            # ran=1 은 **항상** 실린다 — sweep 의 truthy 필터를 통과하는 유일한 키라, 이것이
            #   "이 tick 에서 도메인 합성 pass 가 실제로 돌았다"의 유일한 증거다. 나머지 둘은
            #   명시 update 라 0 이어도 기록된다(sweep 은 기존 키를 건드리지 않는다).
            "domain_synthesis_ran": 1,
            "domain_synthesis_synthesized": int(_ds.get("synthesized", 0) or 0),
            "domain_synthesis_attempted": int(_ds.get("attempted", 0) or 0),
        })
    for _pk in ("relationships_probe_probed", "relationships_probe_positive",
                "relationships_probe_negative", "relationships_probe_neutral",
                "relationships_probe_failed"):
        if scan_report.get(_pk):
            payload[_pk] = int(scan_report.get(_pk, 0) or 0)
    # T0(worker-resource-isolation): 공유 자원 예산 관측 — 상한·관측된 최대 동시 점유·거절률을
    #   tick 로그에 싣는다. 이 세 값이 "상한을 조여도 되는가 / 이미 병목인가" 의 1차 근거다.
    #   peak < limit 이고 rejected 0 이면 게이트는 미발동(= 현행 동등)이라는 실증이기도 하다.
    #   fail-open: 스냅샷 실패는 무시(계측이 cycle 을 죽이지 않는다).
    try:
        from shared import resource_budget as _rb_ins
        _rbs = _rb_ins.snapshot()
        if not _rbs.get("background_enabled", True):
            payload["background_analysis_disabled"] = True
        for _rk, _rv in (_rbs.get("resources") or {}).items():
            if int(_rv.get("acquired", 0) or 0) or int(_rv.get("rejected", 0) or 0):
                payload[f"budget_{_rk}"] = (
                    f"{_rv.get('peak', 0)}/{_rv.get('limit', 0)}"
                    f" rej={_rv.get('rejected', 0)}"
                )
        _conns = _rbs.get("conns") or {}
        if any(_conns.values()):
            payload["worker_conns"] = ",".join(
                f"{k}={v}" for k, v in _conns.items() if v)
        # 파일 flush — 카운터는 이 프로세스 메모리에 있고 조회자(호스트 CLI)는 다른 프로세스다.
        #   `bin/perf-snapshot.sh` 가 다른 성능 신호와 함께 수집한다(사용자 결정 2026-07-30:
        #   "로그 + perf-snapshot CLI"). fail-open — flush 실패는 cycle 에 영향 없음.
        _rb_ins.flush_snapshot()
    except Exception:
        pass
    _telemetry_sweep(payload, scan_report)
    _base_log = status != "ok" or bool(scan_report.get("scan_started"))
    # feature-0026: 노드 분석만 돈 tick 도 로그 라인은 남긴다(처리량 추적) — 단 timing 파일은
    # 기존 조건에서만 생성(§18.8 C-4: 드레인 기간 tick 마다 무회전 파일 누적 방지).
    should_log = _base_log or bool(_na.get("claimed"))
    if should_log:
        if _base_log:
            timing_path = _write_timing_breakdown(timing)
            if timing_path:
                payload["timing_path"] = timing_path
        append_log_line("insight_worker", json.dumps(payload, ensure_ascii=False))
    return payload


#: 계측 sweep 에서 **의도적으로 제외**하는 scan_report 키. 새 키를 여기 넣을 때는 사유를 함께 적는다.
_TELEMETRY_SWEEP_DENY = frozenset({
    "scan_started",   # 제어 플래그 — should_log 판정에 쓰이고 payload 의미가 없다.
})


def _telemetry_sweep(payload: dict, scan_report: dict) -> dict:
    """`scan_report` 의 미등재 스칼라를 payload 로 흘린다 — "기록했다 ⇒ 도달한다" 를 **구조로** 보장.

    **왜 allow-list 를 뒤집는가 (§18.8 적대 리뷰 2026-08-03)**: payload 가 명시 allow-list 이던 동안,
    등재를 빠뜨린 계측은 조용히 사라졌다. change-reanalysis cycle 은 그 위험을 1라운드에 진단해
    4키를 등재해 놓고도 2라운드에서 추가한 2키의 등재를 빠뜨려 **7일간 무음**이었고, 같은 파일에
    이미 6개의 고아 카운터(`coverage_seeded`·`insight_llm_calls`·`tables_fanout`·`relationships_*`)가
    남아 있었다 — 그 중 넷은 FUNCTION.md 가 "관측된다" 고 선언한 것들이다. 등재를 사람이 기억하게
    하는 한 이 실수는 계측을 늘릴 때마다 재발한다. 그래서 규약을 뒤집는다: 기록된 스칼라는 기본
    도달하고, **빼야 할 것만** `_TELEMETRY_SWEEP_DENY` 에 사유와 함께 명시한다.

    - 스칼라(int/float/bool)만 흘린다 — dict/list 는 datasource 순회 병합 규약(int 합산·bool OR·
      그 외 덮어쓰기)에서 마지막 것만 남아 관측이 왜곡되므로 애초에 담지 않는 것이 맞다.
    - **truthy 만** 흘린다(0/False 생략) — 로그 한 줄의 크기를 억제하고, 발생한 신호는 반드시 보이게.
      0 이어도 항상 보여야 하는 핵심 지표(예: `auto_reanalysis_candidates` — "안 돌았다" 자체가
      판정 근거)는 위 payload 블록에 **명시 등재**해 둔다. 두 층은 대체가 아니라 보완이다.
    - 이미 payload 에 있는 키는 건드리지 않는다(명시 등재가 항상 우선).
    """
    for key in sorted(scan_report):
        if key in payload or key in _TELEMETRY_SWEEP_DENY:
            continue
        val = scan_report[key]
        if isinstance(val, bool):
            if val:
                payload[key] = True
        elif isinstance(val, (int, float)) and val:
            payload[key] = val
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
        # feature-0025: pass 행수·주기 live 조절(관리 콘솔). override 없으면 config 기본 = byte-동치.
        try:
            from shared import runtime_settings as _rts_kb
            per_pass = max(1, int(_rts_kb.get_int("AGENT_KB_EMBEDDING_BATCH_MAX_ROWS")))
            interval = max(5, int(_rts_kb.get_int("AGENT_KB_EMBEDDING_INTERVAL_SEC")))
        except Exception:
            pass
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
        # feature-0025: 클러스터링 데몬 주기 live 조절(관리 콘솔). override 없으면 config 기본 = byte-동치.
        try:
            from shared import runtime_settings as _rts_ci
            interval = max(60, int(_rts_ci.get_int("AGENT_METADATA_CLUSTER_INTERVAL_SEC")))
        except Exception:
            pass
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
    """feature-0016 Phase B(ADR-019)·§55: 경계 넘는 관계 추론 백그라운드 루프(Phase C 임베딩 구동).

    embedding/cluster 데몬과 동형·분리 — tick 무블로킹. pass 당 infer_cross_datasource_relationships +
    store_xds_inferred_relationships. §55: **크로스-ds**(AGENT_XDS_RELATIONSHIP_INFER_AUTO)와 **intra-DS
    크로스 스키마(DB)**(AGENT_XSCHEMA_RELATIONSHIP_INFER_AUTO, 기본 ON — 프로브 검증 가능) 두 모드를
    한 루프가 나른다. 둘 중 하나라도 켜지면 기동, 각 pass 는 켜진 모드의 후보만 발굴한다. fail-soft."""
    interval = max(300, int(AGENT_XDS_RELATIONSHIP_INFER_INTERVAL_SEC))
    _log = logging.getLogger("insight")
    from shared import config as _cfg2
    while True:
        try:
            from modules import relationships as _rel
            cands = _rel.infer_cross_datasource_relationships(
                include_xds=bool(getattr(_cfg2, "AGENT_XDS_RELATIONSHIP_INFER_AUTO", False)),
                include_xschema=bool(getattr(_cfg2, "AGENT_XSCHEMA_RELATIONSHIP_INFER_AUTO", True)))
            n = _rel.store_xds_inferred_relationships(candidates=cands) if cands else 0
            if n:
                _log.info("xds_relationship_infer upserted=%s (xds+xschema)", n)
        except Exception as exc:   # 스레드 보호
            _log.warning("xds_relationship_infer pass 실패(무시): %s", exc)
        time.sleep(interval)


def _start_xds_relationship_infer_thread() -> None:
    """XDS 또는 XSCHEMA AUTO 켜짐 시 경계 관계 추론 데몬 스레드 1회 기동(§55 — xschema 는 기본 ON)."""
    from shared import config as _cfg2
    if not (AGENT_XDS_RELATIONSHIP_INFER_AUTO
            or bool(getattr(_cfg2, "AGENT_XSCHEMA_RELATIONSHIP_INFER_AUTO", True))):
        return
    try:
        import threading
        t = threading.Thread(target=_xds_relationship_infer_loop, name="xds-relationship-infer", daemon=True)
        t.start()
        logging.getLogger("insight").info(
            "xds_relationship_infer 스레드 기동(interval=%ss, xds=%s min_sim=%s, xschema=%s min_sim=%s)",
            AGENT_XDS_RELATIONSHIP_INFER_INTERVAL_SEC,
            AGENT_XDS_RELATIONSHIP_INFER_AUTO, AGENT_XDS_RELATIONSHIP_MIN_SIM,
            bool(getattr(_cfg2, "AGENT_XSCHEMA_RELATIONSHIP_INFER_AUTO", True)),
            getattr(_cfg2, "AGENT_XSCHEMA_RELATIONSHIP_MIN_SIM", 0.86),
        )
    except Exception as exc:
        logging.getLogger("insight").warning("xds_relationship_infer 스레드 기동 실패(무시): %s", exc)



def _product_classify_loop() -> None:
    """feature-0016 §59: 미분류 스키마 → 제품 분류 AI 제안 백그라운드 루프(XDS 데몬과 동형·분리).
    pass 당 BATCH_MAX 스키마 상한, 제안은 Pending(승인 대기)에만 적재. fail-soft."""
    from shared.config import AGENT_PRODUCT_CLASSIFY_INTERVAL_SEC
    interval = max(600, int(AGENT_PRODUCT_CLASSIFY_INTERVAL_SEC))
    _log = logging.getLogger("insight")
    while True:
        try:
            from modules import product_classify
            rep = product_classify.run_classify_pass()
            if int(rep.get("suggested_total") or 0) > 0 or rep.get("errors"):
                _log.info("product_classify suggested=%s errors=%s",
                          rep.get("suggested_total"), (rep.get("errors") or [])[:3])
        except Exception as exc:   # 스레드 보호 — 어떤 예외도 루프를 죽이지 않음
            _log.warning("product_classify pass 실패(무시): %s", exc)
        time.sleep(interval)


def _start_product_classify_thread() -> None:
    """AUTO 켜짐 시 제품 분류 제안 데몬 1회 기동(기본 OFF — 접근면 인접이라 명시 opt-in)."""
    from shared.config import AGENT_PRODUCT_CLASSIFY_AUTO
    if not AGENT_PRODUCT_CLASSIFY_AUTO:
        return
    try:
        import threading
        t = threading.Thread(target=_product_classify_loop, name="product-classify-suggest", daemon=True)
        t.start()
        logging.getLogger("insight").info("product_classify 제안 데몬 기동")
    except Exception as exc:
        logging.getLogger("insight").warning("product_classify 데몬 기동 실패(무시): %s", exc)


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
    # feature-0016 §59: 제품 분류 AI 제안 데몬(기본 OFF — AGENT_PRODUCT_CLASSIFY_AUTO).
    _start_product_classify_thread()
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
            # feature-0025: tick 주기 live 조절(관리 콘솔). override 없으면 배포 env(=tick_sec) = byte-동치.
            _tick_live = tick_sec
            try:
                from shared import runtime_settings as _rts_ti
                _tick_live = max(5, int(_rts_ti.get_int("AGENT_INSIGHT_WORKER_TICK_SEC")))
            except Exception:
                _tick_live = tick_sec
            _INSIGHT_SHUTDOWN.wait(_tick_live)
    try:
        console.print("insight-worker: graceful shutdown 완료(루프 종료).")
    except Exception:
        pass
