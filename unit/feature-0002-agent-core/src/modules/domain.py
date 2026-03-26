import re
__all__ = [
    "_apply_domain_anchor_guard",
    "_build_domain_anchor",
    "_build_error_signature",
    "_clear_error_signature",
    "_derive_topic",
    "_detect_stepwise_request",
    "_effective_request",
    "_ensure_domain_anchor",
    "_extract_request_table_mentions",
    "_has_prior_result_context",
    "_has_same_domain_cue",
    "_is_aggregate_like_request",
    "_is_meta_exploration_plan",
    "_is_meta_sql",
    "_is_meta_state_check_request",
    "_is_meta_tool_name",
    "_is_not_found_error_type",
    "_load_domain_anchor",
    "_load_last_search_objects_compact",
    "_looks_confirmation_followup",
    "_looks_explicit_request",
    "_mark_error_signature",
    "_parse_stepwise_list",
    "_preserve_request_for_retry",
    "_resolve_followup_request_input",
    "_set_retry_hint",
    "_should_refresh_origin_request",
]


"""Domain anchor, request analysis, follow-up detection."""
from .config import *
import json, re
from typing import Any

def _looks_confirmation_followup(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    if "?" in raw:
        return False
    lowered = raw.lower()
    compact = re.sub(r"[\s\.\,\!\~\-\_]+", "", lowered)
    if not compact:
        return False
    exact_hits = {
        "네",
        "예",
        "응",
        "ok",
        "오케이",
        "좋아",
        "좋아요",
        "좋습니다",
        "맞아",
        "맞아요",
        "맞음",
        "맞습니다",
        "동의",
        "승인",
        "그대로",
        "진행",
        "진행해",
        "진행해주세요",
        "진행해줘",
        "적용",
        "적용해",
        "적용해주세요",
        "반영",
        "반영해",
        "반영해주세요",
    }
    if compact in exact_hits:
        return True
    positive = any(token in lowered for token in CONFIRMATION_FOLLOWUP_CUES)
    action = any(token in lowered for token in ("진행", "적용", "반영", "실행", "유지"))
    if len(compact) <= 40 and positive and action and not _looks_explicit_request(raw):
        return True
    return False


def _has_same_domain_cue(text: str) -> bool:
    if not text:
        return False
    lowered = " ".join(str(text).lower().split())
    return any(cue in lowered for cue in SAME_DOMAIN_CUES)


def _looks_explicit_request(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if looks_like_sql(text):
        return True
    if DATE_TOKEN_RE.search(text):
        return True
    if any(token in lowered for token in ("스키마", "테이블", "컬럼", "필드", "schema", "table", "column")):
        return True
    if re.search(r"\bfrom\b", lowered):
        return True
    return False


def _is_meta_state_check_request(text: str) -> bool:
    """Protects conversation state from meta-check utterances."""
    raw = str(text or "").strip()
    if not raw:
        return False
    if looks_like_sql(raw):
        return False
    if re.search(r"`?[A-Za-z0-9_]+`?\s*\.\s*`?[A-Za-z0-9_]+`?", raw):
        return False
    if _detect_requested_schema(raw, KNOWN_SCHEMAS):
        return False
    lowered = raw.lower()
    # If the user asks for concrete data work, this is not a meta check.
    if any(tok in lowered for tok in ("조회", "집계", "통계", "샘플", "테이블", "컬럼", "count", "select")):
        return False
    meta_cues = ("문맥", "맥락", "이해", "기억", "대화", "요청사항", "의도", "원인", "왜", "맞", "확인")
    if not any(cue in raw for cue in meta_cues):
        return False
    return ("?" in raw) or ("확인" in raw) or ("맞" in raw)


def _should_refresh_origin_request(prev_origin: str, new_request: str, kv: dict[str, str] | None) -> str:
    """주제 전환 여부를 판단한다.

    Returns:
        "shift"    — 완전한 주제 전환. origin_request + thread_goal + 컨텍스트 전체 리셋.
        "evolve"   — 같은 도메인 내 목표 진화. thread_goal만 갱신, 나머지 보존.
        "continue" — 동일 목표 유지. 아무것도 변경하지 않음.

    휴리스틱 키워드 기반 판단을 제거하고, LLM에게 위임한다.
    안전한 fast-path(빈값, 메타점검, 확인응답)만 코드에서 처리하고,
    그 외 모든 판단은 llm_classify_origin_shift()가 수행한다.
    """
    prev_origin = str(prev_origin or "").strip()
    new_request = str(new_request or "").strip()
    if not new_request:
        return "continue"
    if not prev_origin:
        return "shift"

    # ── 안전한 fast-path: 상태를 오염시키지 않는 발화 유형 ──
    if _is_meta_state_check_request(new_request):
        return "continue"
    if _looks_confirmation_followup(new_request):
        return "continue"

    # ── 높은 유사도: 같은 주제가 확실하면 LLM 호출 생략 ──
    similarity = _jaccard_similarity(prev_origin, new_request)
    if similarity >= 0.4:
        return "continue"

    # ── LLM 3-state 분류: shift / evolve / continue ──
    return llm_classify_origin_shift(prev_origin, new_request)


def _effective_request(
    current_request: str | None,
    original_request: str,
    kv_origin: str | None = None,
) -> str:
    if not current_request:
        return original_request or (kv_origin or "")
    if AGENT_LLM_REQUEST_PASSTHROUGH:
        if _is_meta_state_check_request(current_request):
            fallback = str(original_request or kv_origin or "").strip()
            if fallback and not _is_meta_state_check_request(fallback):
                return fallback
        return current_request
    normalized = current_request.strip().lower()
    if normalized in {"continue", "continue.", "계속", "계속.", "다음", "진행", "계속 진행"}:
        if original_request and original_request.strip().lower() not in {
            "continue",
            "continue.",
            "계속",
            "계속.",
            "다음",
            "진행",
            "계속 진행",
        }:
            return original_request
        if kv_origin:
            return str(kv_origin)
    return current_request


def _resolve_followup_request_input(text: str, kv: dict[str, str] | None) -> str | None:
    if AGENT_LLM_REQUEST_PASSTHROUGH:
        return None
    req = str(text or "").strip()
    kv = kv or {}
    if not req:
        return None
    if not _looks_like_followup_request(req):
        return None
    if _looks_explicit_request(req):
        return None

    last_sql = str(kv.get("last_sql") or "").strip()
    req_compact = req.replace(" ", "")
    is_modify_followup = (
        "바꿔" in req
        or "다르게" in req
        or "변형" in req
        or "수정" in req
        or "조정" in req
        or "좀바꿔서" in req_compact
    )
    is_reuse_followup = (
        "다시" in req
        or "이어서" in req
        or req_compact in {"계속", "계속진행", "continue", "continue."}
    )

    last_file_search = str(kv.get("last_file_search") or "").strip()
    if _is_restore_list_request(req):
        return "복원 파일 목록 조회 (`.sql` 또는 `.dump`)"
    picked_file = _pick_file_from_last_search(last_file_search, restore_only=True)
    has_restore_context = bool(picked_file)
    restore_word = (
        bool(_extract_restore_filename(req))
        or any(token in req.lower() for token in ("복원", "restore", "dump", "백업"))
        or ("복구" in req and "파일" in req)
    )
    run_restore_followup = has_restore_context and (
        restore_word
        or (
            any(token in req for token in ("실행", "진행", "적용"))
            and any(token in req for token in ("그거", "이어서", "다시"))
        )
    )
    if run_restore_followup:
        return f"복원 파일 `{picked_file}`를 실행"
    base_origin = (
        str(kv.get("last_user_request") or "").strip()
        or str(kv.get("origin_request") or "").strip()
    )
    if is_modify_followup and last_sql:
        if base_origin and (_contains_structure_intent(base_origin) or _is_schema_usage_intent(base_origin)):
            return base_origin
        return last_sql
    if is_reuse_followup and last_sql:
        if base_origin and (_contains_structure_intent(base_origin) or _is_schema_usage_intent(base_origin)):
            return base_origin
        return last_sql

    last_intent = str(kv.get("last_result_intent") or "").strip()
    generic_intents = {"사용자 제공 SQL 실행", "요청 처리", "요청", "continue"}
    if last_intent in generic_intents:
        last_intent = ""
    base = (
        str(kv.get("last_user_request") or "").strip()
        or str(kv.get("origin_request") or "").strip()
        or last_intent
    )
    if not base:
        return None
    if looks_like_sql(base):
        return base

    return base


def _is_not_found_error_type(title: str) -> bool:
    return str(title or "").strip() in {"스키마 없음", "테이블 없음", "컬럼 없음"}


def _build_error_signature(tool: str, title: str, sql_text: str, err_msg: str) -> str:
    tool_key = _sanitize_key_part(str(tool or "tool").lower(), max_len=24) or "tool"
    title_key = _sanitize_key_part(str(title or "error").lower(), max_len=24) or "error"
    schema_name, table_name = _extract_first_table_from_sql(sql_text or "")
    table_ref = ""
    if table_name:
        table_ref = f"{schema_name}.{table_name}" if schema_name else table_name
    col = _extract_unknown_column(err_msg or "") or ""
    if col:
        table_ref = f"{table_ref}:{col}" if table_ref else col
    if not table_ref:
        table_ref = _normalize_kb_key(err_msg or "")[:48] or "na"
    return _fit_fact_key_storage(f"errsig:{tool_key}:{title_key}:{table_ref}")


def _mark_error_signature(
    conn,
    conversation_id: str,
    kv: dict[str, Any] | None,
    signature: str,
) -> bool:
    if not conn or not conversation_id or not signature:
        return False
    kv = kv or {}
    last_sig = str(kv.get("last_error_signature") or "").strip()
    try:
        last_count = int(str(kv.get("last_error_signature_count") or "0").strip())
    except Exception:
        last_count = 0
    if signature == last_sig:
        count = last_count + 1
    else:
        count = 1
    try:
        save_memory_kv(conn, conversation_id, "last_error_signature", signature)
        save_memory_kv(conn, conversation_id, "last_error_signature_count", str(count))
    except Exception:
        pass
    kv["last_error_signature"] = signature
    kv["last_error_signature_count"] = str(count)
    return count > 1


def _clear_error_signature(conn, conversation_id: str) -> None:
    if not conn or not conversation_id:
        return
    try:
        save_memory_kv(conn, conversation_id, "last_error_signature", "")
        save_memory_kv(conn, conversation_id, "last_error_signature_count", "0")
    except Exception:
        pass


def _load_domain_anchor(kv: dict[str, Any] | None) -> dict[str, Any]:
    kv = kv or {}
    raw = kv.get("domain_anchor")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return {}
    return {}


def _build_domain_anchor(
    request_text: str,
    kv: dict[str, Any] | None,
    known_schemas: list[str] | None = None,
) -> dict[str, Any]:
    kv = kv or {}
    known_schemas = known_schemas or KNOWN_SCHEMAS
    origin = str(kv.get("origin_request") or request_text or "").strip()
    preferred_schema = str(kv.get("preferred_schema") or "").strip()
    detected_from_request = _detect_requested_schema(request_text, known_schemas) or ""
    detected_from_origin = _detect_requested_schema(origin, known_schemas) or ""
    detected_schema = (
        detected_from_origin
        or detected_from_request
        or preferred_schema
        or ""
    )
    tokens = [t for t in _tokenize_for_similarity(origin) if len(t) >= 2][:5]
    payload: dict[str, Any] = {
        "schema": detected_schema,
        "tokens": tokens,
        "origin": origin[:160],
    }
    if not payload["schema"] and not payload["tokens"] and not payload["origin"]:
        return {}
    return payload


def _ensure_domain_anchor(
    conn,
    conversation_id: str,
    request_text: str,
    kv: dict[str, Any] | None,
    known_schemas: list[str] | None = None,
) -> dict[str, Any]:
    if not AGENT_DOMAIN_DRIFT_GUARD:
        return {}
    kv = kv or {}
    anchor = _load_domain_anchor(kv)
    if anchor:
        anchor_origin = str(anchor.get("origin") or "").strip()
        current_origin = str(kv.get("origin_request") or request_text or "").strip()
        if anchor_origin and current_origin:
            similarity = _jaccard_similarity(anchor_origin, current_origin)
            if similarity < 0.3:
                anchor = {}
            elif _should_refresh_origin_request(anchor_origin, current_origin, kv) == "shift":
                anchor = {}
    if anchor:
        return anchor
    anchor = _build_domain_anchor(request_text, kv, known_schemas)
    if not anchor:
        return {}
    try:
        save_memory_kv(conn, conversation_id, "domain_anchor", json.dumps(anchor, ensure_ascii=False))
    except Exception:
        pass
    return anchor


def _apply_domain_anchor_guard(
    request_text: str,
    anchor: dict[str, Any] | None,
    known_schemas: list[str] | None = None,
) -> tuple[str, str]:
    if AGENT_LLM_REQUEST_PASSTHROUGH:
        return request_text, ""
    if not AGENT_DOMAIN_DRIFT_GUARD:
        return request_text, ""
    req = str(request_text or "").strip()
    if not req:
        return req, ""
    # ORIGIN_SHIFT_CUES 휴리스틱 제거됨 — 주제 전환은 LLM이 판단.
    anchor = anchor or {}
    known_schemas = known_schemas or KNOWN_SCHEMAS
    anchor_schema = str(anchor.get("schema") or "").strip()
    origin = str(anchor.get("origin") or "").strip()
    req_schema = _detect_requested_schema(req, known_schemas) or ""
    if anchor_schema and req_schema and req_schema != anchor_schema:
        return req, f"schema:{req_schema}->{anchor_schema}"
    normalized = req.lower()
    if normalized in {"continue", "continue.", "계속", "계속.", "다음", "진행", "계속 진행", "이어서"}:
        if origin:
            return origin, "followup-anchor"
    return req, ""


def _is_meta_tool_name(name: str) -> bool:
    tool = str(name or "").strip().lower()
    if not tool:
        return False
    if tool in {"file_search", "convo_search"}:
        return True
    if tool in MCP_SEARCH_OBJECTS_CANDIDATES:
        return True
    return False


def _is_meta_sql(sql_text: str) -> bool:
    sql = str(sql_text or "").lower()
    if not sql:
        return False
    if "information_schema" in sql:
        return True
    if re.search(r"\bshow\s+(tables|columns|databases|schemas)\b", sql):
        return True
    return False


def _has_prior_result_context(kv: dict[str, Any] | None) -> bool:
    kv = kv or {}
    for key in ("last_result_summary", "last_result_intent", "last_user_answer"):
        val = str(kv.get(key) or "").strip()
        if val:
            return True
    return False


def _set_retry_hint(conn, conversation_id: str, hint: str) -> None:
    if not conn:
        return
    text = " ".join(str(hint or "").split())
    try:
        save_memory_kv(conn, conversation_id, "retry_hint", text)
    except Exception:
        pass


def _preserve_request_for_retry(request_for_context: str, original_request: str) -> str:
    kept = str(request_for_context or "").strip()
    if kept and kept.lower() not in {"continue", "continue."}:
        return kept
    kept = str(original_request or "").strip()
    return kept or "continue"


def _is_meta_exploration_plan(plan: dict[str, Any] | None) -> bool:
    if not isinstance(plan, dict):
        return False
    if str(plan.get("action", "")).strip().lower() != "step":
        return False
    tool = str(plan.get("tool", "")).strip()
    if _is_meta_tool_name(tool):
        return True
    sql_text = str(plan.get("sql", "")).strip()
    if sql_text and _is_meta_sql(sql_text):
        return True
    args = plan.get("args") if isinstance(plan.get("args"), dict) else {}
    if args:
        arg_sql = str(args.get("sql", "")).strip()
        if arg_sql and _is_meta_sql(arg_sql):
            return True
    return False


def _load_last_search_objects_compact(kv: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(kv, dict):
        return []
    raw = kv.get("last_search_objects")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _extract_request_table_mentions(
    request: str,
    schema_meta: dict[str, Any] | None = None,
) -> tuple[set[str], set[str]]:
    # Policy: avoid broad keyword/token extraction from user text.
    # Keep only explicit object mentions.
    text = str(request or "").strip()
    if not text:
        return set(), set()
    explicit_refs: set[str] = set()
    explicit_tables: set[str] = set()
    for match in re.finditer(r"`?([A-Za-z0-9_]+)`?\.`?([A-Za-z0-9_]+)`?", text):
        schema = _sanitize_ident_part(match.group(1))
        table = _sanitize_ident_part(match.group(2))
        if schema and table:
            explicit_refs.add(f"{schema.lower()}.{table.lower()}")
            explicit_tables.add(table.lower())
    for match in re.finditer(r"`([A-Za-z0-9_]+)`", text):
        table = _sanitize_ident_part(match.group(1))
        if table:
            explicit_tables.add(table.lower())
    tables = (schema_meta or {}).get("tables") if isinstance(schema_meta, dict) else []
    if isinstance(tables, dict):
        table_names = [str(k) for k in tables.keys()]
    elif isinstance(tables, list):
        table_names = [str(k) for k in tables]
    else:
        table_names = []
    lowered_text = text.lower()
    for table_name in table_names:
        safe = _sanitize_ident_part(table_name)
        if not safe:
            continue
        if re.search(rf"(?<![a-z0-9_]){re.escape(safe.lower())}(?![a-z0-9_])", lowered_text):
            explicit_tables.add(safe.lower())
    return explicit_tables, explicit_refs


def _is_aggregate_like_request(request: str, kv: dict[str, Any] | None = None) -> bool:
    # Policy: text/keyword heuristic classification is disabled.
    # Keep this function for backward compatibility, but never classify by text.
    return False




def _derive_topic(text: str, max_len: int = 48) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return ""
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"

def _detect_stepwise_request(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if "단계" in lowered or "순서" in lowered or "step" in lowered:
        return True
    if re.search(r"\b1[\.\)]\s", text):
        return True
    if re.search(r"\b2[\.\)]\s", text):
        return True
    return False

def _parse_stepwise_list(text: str) -> list[str]:
    if not text:
        return []
    normalized = re.sub(r"\s+(?=\d+[.)]\s+)", "\n", text.strip())
    parts = re.split(r"(?:^|\n)\s*\d+[.)]\s+", normalized)
    steps = [p.strip() for p in parts if p.strip()]
    return steps

