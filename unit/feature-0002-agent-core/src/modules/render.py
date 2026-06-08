from datetime import datetime, timezone
import json
import os
import re
__all__ = [
    "AUTO_CONTINUE_CUES",
    "DUMP_FILENAME_RE",
    "FOLLOWUP_QUESTION_CUES",
    "PROSE_SENTENCE_BREAK_RE",
    "SENSITIVE_PATH_RE",
    "SENSITIVE_SUMMARY_KEYS",
    "SQLISH_TEXT_RE",
    "SQL_FILENAME_RE",
    "SQL_INLINE_RE",
    "_auto_select_file_for_request",
    "_build_forced_conclusion",
    "_build_user_facing_answer",
    "_build_user_facing_error",
    "_derive_insight_text",
    "_ensure_user_answer_quality",
    "_extract_json_object",
    "_extract_restore_filename",
    "_extract_sql_filename",
    "_extract_sql_from_request",
    "_format_user_answer_text",
    "_format_value",
    "_is_direct_sql_request",
    "_is_list_only_request",
    "_is_restore_execute_request",
    "_is_restore_list_request",
    "_last_step_ok_for_autodone",
    "_load_last_summary_dict_from_kv",
    "_looks_like_followup_question",
    "_maybe_build_sql_from_file",
    "_normalize_mcp_plan",
    "_normalize_sql_plan",
    "_pick_file_from_last_search",
    "_record_insight_fact",
    "_sanitize_sql_candidate",
    "_sanitize_summary_for_prompt",
    "_shorten_error_for_user",
    "_should_auto_continue",
    "build_summary_text",
    "is_write_sql",
    "looks_like_sql",
    "normalize_step_result_summary",
    "parse_result_preview_table",
    "read_csv_preview",
    "render_rows",
    "sanitize_user_text",
    "save_csv",
    "summarize_result_sets",
]


"""Output formatting, result rendering, response building."""
from .config import *
import csv, json, os, re, uuid
from typing import Any
from rich.table import Table

def save_csv(prefix: str, columns: list[str], rows: list[list[Any]]) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 같은 초에 저장되는 서로 다른 result set 의 파일명 충돌 방지 (#118).
    # 초 단위 ts 만으로는 멀티-step 에이전트가 동일 초에 실행한 여러 SQL 결과가
    # 같은 `{ts}_{prefix}.csv` 를 공유해 나중 결과가 앞 결과를 덮어썼다 (open 'w').
    # get_conversation_id() 와 동일하게 uuid 접미를 붙여 유니크성을 보장한다.
    path = os.path.join(AGENT_OUT_DIR, f"{ts}_{prefix}_{uuid.uuid4().hex[:8]}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_format_value(v) for v in row])
    return path


def read_csv_preview(path: str, max_rows: int) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                return None
            preview_rows = []
            for _ in range(max_rows):
                row = next(reader, None)
                if row is None:
                    break
                preview_rows.append(row)
            return {"path": path, "columns": header, "rows": preview_rows}
    except Exception:
        return None


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def render_rows(columns: list[str], rows: list[list[Any]], max_rows: int) -> tuple[Table, int]:
    max_cols = max(1, AGENT_TABLE_MAX_COLS)
    display_columns = columns[:max_cols]
    hidden_cols = columns[max_cols:] if len(columns) > max_cols else []

    table = Table(show_lines=False)
    for c in display_columns:
        table.add_column(str(c), max_width=AGENT_TABLE_MAX_COL_WIDTH, overflow="fold")
    if hidden_cols:
        table.add_column("…", max_width=12, justify="right")

    shown = 0
    for row in rows:
        if shown >= max_rows:
            break
        values = [_format_value(v) for v in row[: len(display_columns)]]
        if hidden_cols:
            values.append(f"+{len(hidden_cols)} cols")
        table.add_row(*values)
        shown += 1

    if hidden_cols:
        table.caption = f"표시 제한: {len(hidden_cols)}개 컬럼 숨김"
    return table, shown



def summarize_result_sets(result_sets, max_cols: int = 6, max_rows: int = 3) -> dict[str, Any]:
    for rs in result_sets:
        if rs[0] == "rows":
            _, columns, rows = rs
            col_names = [str(c) for c in columns[:max_cols]]
            sample_rows = []
            for row in rows[:max_rows]:
                sample_rows.append([_format_value(v) for v in row[:max_cols]])
            return {
                "rows": len(rows),
                "cols": len(columns),
                "col_names": col_names,
                "samples": sample_rows,
            }
        if rs[0] == "rowcount":
            return {"rowcount": rs[1]}
    return {}


def _parse_markdown_table_row(line: str) -> list[str]:
    text = str(line or "").strip()
    if not text.startswith("|") or text.count("|") < 2:
        return []
    return [cell.strip() for cell in text.strip("|").split("|")]


def parse_result_preview_table(preview_text: str) -> dict[str, Any] | None:
    raw_text = str(preview_text or "").strip()
    if not raw_text:
        return None
    lines = [line.rstrip() for line in raw_text.splitlines()]
    table_lines: list[str] = []
    capture = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            table_lines.append(stripped)
            capture = True
            continue
        if capture:
            break
    if len(table_lines) < 2:
        return None
    columns = _parse_markdown_table_row(table_lines[0])
    divider = _parse_markdown_table_row(table_lines[1])
    if not columns or not divider:
        return None
    rows: list[list[str]] = []
    for line in table_lines[2:]:
        parsed = _parse_markdown_table_row(line)
        if not parsed:
            continue
        if len(parsed) < len(columns):
            parsed.extend([""] * (len(columns) - len(parsed)))
        rows.append(parsed[: len(columns)])
    truncated = bool(re.search(r"\.\.\.\s*\(\d+\s*행 중", raw_text))
    return {
        "columns": columns,
        "rows": rows,
        "truncated": truncated,
        "raw_text": raw_text,
    }


def normalize_step_result_summary(tool_name: str, result_summary: Any) -> Any:
    if not isinstance(result_summary, dict):
        return result_summary
    summary = dict(result_summary)
    if str(tool_name or "").strip() != "execute_sql":
        return summary
    if summary.get("preview_table"):
        return summary
    # CSV 가 있으면 CSV 에서 preview_table 구성 — _format_result_sets 의 셀 100자
    # 잘림 없이 원본 값 그대로 반영된다.
    csv_paths = summary.get("csv_paths") or []
    if isinstance(csv_paths, str):
        csv_paths = [csv_paths]
    for csv_path in csv_paths:
        csv_preview = read_csv_preview(str(csv_path), max_rows=50)
        if csv_preview:
            total_rows_in_file = _count_csv_data_rows(str(csv_path))
            shown = len(csv_preview.get("rows") or [])
            summary["preview_table"] = {
                "columns": csv_preview.get("columns") or [],
                "rows": csv_preview.get("rows") or [],
                "truncated": total_rows_in_file is not None and total_rows_in_file > shown,
            }
            return summary
    # CSV 없을 때 기존 텍스트 파싱 경로 (값이 100자 잘린 채 표시될 수 있음)
    preview = str(summary.get("preview") or "").strip()
    if not preview:
        return summary
    preview_table = parse_result_preview_table(preview)
    if preview_table:
        summary["preview_table"] = preview_table
    return summary


def _count_csv_data_rows(path: str) -> int | None:
    """CSV 파일의 데이터 행 수(헤더 제외)를 반환. 읽기 실패 시 None."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            return sum(1 for _ in reader)
    except Exception:
        return None


SENSITIVE_SUMMARY_KEYS = {
    "csv_paths",
    "csv_path",
    "log_path",
    "log_paths",
    "output_path",
    "output_paths",
    "file_path",
    "file_paths",
}
SENSITIVE_PATH_RE = re.compile(r"/shared/(?:out|logs)/[^\\s)]+", re.IGNORECASE)
FOLLOWUP_QUESTION_CUES = (
    "다음",
    "선택",
    "원하시나요",
    "어떤 작업",
    "계속",
    "재실행",
    "필터링",
    "추가로",
    "추가 작업",
    "내보내",
    "전체",
    "limit",
    "csv",
    "아니면",
)
AUTO_CONTINUE_CUES = (
    "진행할까요",
    "계속 진행",
    "계속할까요",
    "해도 될까요",
    "되나요",
    "사용해도",
    "재검색",
    "재시도",
    "다시 시도",
    "재확인",
)
PROSE_SENTENCE_BREAK_RE = re.compile(r"(?<=[.!?])\s+(?=[^\s])")
SQLISH_TEXT_RE = re.compile(
    r"\b(select|insert|update|delete|from|where|join|group\s+by|order\s+by|limit)\b",
    re.IGNORECASE,
)


def _sanitize_summary_for_prompt(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, val in value.items():
            if str(key) in SENSITIVE_SUMMARY_KEYS:
                continue
            cleaned[key] = _sanitize_summary_for_prompt(val)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_summary_for_prompt(v) for v in value]
    if isinstance(value, str):
        if SENSITIVE_PATH_RE.search(value):
            return SENSITIVE_PATH_RE.sub("[자동 저장됨]", value)
    return value


def sanitize_user_text(text: str) -> str:
    if not text:
        return text
    text = SENSITIVE_PATH_RE.sub("[자동 저장됨]", text)
    text = re.sub(r"\(결과 저장:.*?\)", "", text)
    text = re.sub(r"\(로그.*?\)", "", text)
    text = re.sub(r"\s*CSV\s*저장(됨)?", "", text, flags=re.IGNORECASE)
    return text.strip()


def _format_user_answer_text(text: str) -> str:
    normalized = sanitize_user_text(str(text or "").strip())
    if not normalized:
        return ""
    if "\n" in normalized:
        return normalized
    if len(normalized) < 100:
        return normalized
    if "```" in normalized or SQLISH_TEXT_RE.search(normalized):
        return normalized
    if " / " in normalized:
        normalized = normalized.replace(" / ", "\n").strip()
        if "\n" in normalized:
            return normalized
    sentence_parts = [p.strip() for p in PROSE_SENTENCE_BREAK_RE.split(normalized) if p.strip()]
    if len(sentence_parts) >= 2:
        if len(sentence_parts) >= 3 and len(normalized) >= 120:
            return "\n".join(sentence_parts)
        long_parts = sum(1 for p in sentence_parts if len(p) >= 24)
        if long_parts >= 2 or len(normalized) >= 180:
            return "\n".join(sentence_parts)
    comma_parts = [p.strip() for p in re.split(r",\s+", normalized) if p.strip()]
    if len(comma_parts) >= 4 and len(normalized) >= 180:
        return "\n".join(comma_parts)
    return normalized


def _last_step_ok_for_autodone(kv: dict[str, Any]) -> bool:
    raw = kv.get("last_step_validation")
    if not raw:
        return False
    try:
        data = json.loads(raw)
    except Exception:
        return False
    try:
        score = float(data.get("score", 0))
    except Exception:
        score = 0.0
    return bool(data.get("ok")) and score >= 75


def _looks_like_followup_question(question: str) -> bool:
    if not question:
        return False
    return any(cue in question for cue in FOLLOWUP_QUESTION_CUES)


def _is_list_only_request(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    list_terms = (
        "목록",
        "리스트",
        "list",
        "조회",
        "show",
        "확인",
        "보기",
        "출력",
        "나열",
        "전체",
        "전부",
        "모두",
        "찾아",
        "검색",
        "find",
        "search",
    )
    exclude_terms = (
        "컬럼",
        "column",
        "샘플",
        "sample",
        "미리",
        "preview",
        "내용",
        "본문",
        "통계",
        "집계",
        "분석",
        "실행",
        "execute",
        "복원 실행",
        "복원해",
        "복원 진행",
        "restore",
        "구해",
        "계산",
        "평균",
        "최대",
        "분포",
        "비율",
        "조인",
        "조건",
        "필터",
        "기간",
        "range",
    )
    if not any(term in lower for term in list_terms):
        return False
    if ("복원" in lower or "restore" in lower) and ("목록" not in lower and "리스트" not in lower):
        return False
    if any(term in lower for term in exclude_terms):
        return False
    return True


def _should_auto_continue(question: str) -> bool:
    if not question:
        return False
    return any(cue in question for cue in AUTO_CONTINUE_CUES)


def _pick_file_from_last_search(
    last_search_raw: str | None,
    restore_only: bool = False,
) -> str | None:
    if not last_search_raw:
        return None
    try:
        payload = json.loads(last_search_raw)
    except Exception:
        return None
    if not isinstance(payload, list) or not payload:
        return None
    candidates = payload
    if restore_only:
        candidates = [
            item
            for item in payload
            if isinstance(item, dict)
            and _is_restore_compatible_file(str(item.get("path", "")).strip())
        ]
        if not candidates:
            return None
    def _mtime_key(item: dict[str, Any]) -> datetime:
        try:
            val = str(item.get("mtime", ""))
            if not val:
                return datetime.min.replace(tzinfo=timezone.utc)
            return datetime.fromisoformat(val)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)
    try:
        best = max(candidates, key=lambda x: _mtime_key(x if isinstance(x, dict) else {}))
    except Exception:
        best = candidates[0]
    if isinstance(best, dict):
        path = str(best.get("path", "")).strip()
        return path or None
    return None


def _auto_select_file_for_request(request: str, last_search_raw: str | None) -> str | None:
    if not request:
        return None
    if not last_search_raw:
        return None
    try:
        payload = json.loads(last_search_raw)
    except Exception:
        return None
    if not isinstance(payload, list) or not payload:
        return None
    if len(payload) == 1 and isinstance(payload[0], dict):
        path = str(payload[0].get("path", "")).strip()
        return path or None
    allow_any = any(
        token in request for token in ("그 중", "아무", "임의", "아무거나", "하나만", "추천")
    )
    if not allow_any:
        return None
    return _pick_file_from_last_search(last_search_raw)


def build_summary_text(intent: str, result_summary: dict[str, Any] | None, last_error: str | None) -> str:
    parts = []
    if intent:
        parts.append(f"intent={sanitize_user_text(intent)}")
    if result_summary:
        sanitized = _sanitize_summary_for_prompt(result_summary)
        parts.append(f"result={json.dumps(sanitized, ensure_ascii=False)}")
    if last_error:
        parts.append(f"error={sanitize_user_text(last_error)}")
    return " | ".join(parts)


def _shorten_error_for_user(err_msg: str) -> str:
    text = str(err_msg or "").strip()
    if not text:
        return ""
    if "원문:" in text:
        text = text.split("원문:", 1)[0].strip()
    return text


def _derive_insight_text(
    intent: str,
    summary_data: dict[str, Any] | None,
    tool: str = "",
) -> str:
    if not summary_data or not isinstance(summary_data, dict):
        return ""
    intent = str(intent or "").strip() or "요청"
    rows = summary_data.get("rows")
    cols = summary_data.get("cols")
    col_names = summary_data.get("col_names")
    if isinstance(rows, int):
        parts = [f"{intent} 결과: {rows}행"]
        if isinstance(cols, int) and cols > 0:
            parts.append(f"{cols}열")
        if isinstance(col_names, list) and col_names:
            sample_cols = [str(c) for c in col_names[: max(1, AGENT_KB_INSIGHT_MAX_COLS)]]
            parts.append(f"대표 컬럼: {', '.join(sample_cols)}")
        return ", ".join(parts).strip()
    rowcount = summary_data.get("rowcount")
    if isinstance(rowcount, int):
        return f"{intent} 결과: 영향 행수 {rowcount}"
    count = summary_data.get("count")
    if isinstance(count, int):
        return f"{intent} 결과: {count}건"
    status = summary_data.get("status")
    if status and tool == "restore_sql":
        database = str(summary_data.get("database", "")).strip()
        db_text = database or "파일 내 지시문"
        return f"{intent} 완료: 대상 DB {db_text}"
    return ""


def _record_insight_fact(
    conn,
    conversation_id: str,
    intent: str,
    summary_data: dict[str, Any] | None,
    tool: str,
    source_run_id: str | None = None,
    source_sql: str | None = None,
) -> None:
    if not conn or not AGENT_KB_INSIGHT:
        return
    insight = _derive_insight_text(intent, summary_data, tool)
    if not insight:
        return
    save_memory_kv(conn, conversation_id, "last_insight", insight)
    key = ""
    if source_sql:
        schema, table = _extract_first_table_from_sql(source_sql)
        if table:
            prefix = f"{schema}." if schema else ""
            key = f"insight:{prefix}{table}"
    if not key:
        key = f"insight:{_normalize_fact_key(intent or 'insight')}"
    _publish_fact(
        conn,
        conversation_id,
        key,
        insight,
        5,
        source_type="insight",
        source_run_id=source_run_id,
        source_sql=source_sql,
    )


def _build_user_facing_answer(
    intent: str,
    summary_data: dict[str, Any] | None,
    tool: str,
) -> str:
    intent = str(intent or "").strip() or "요청"
    answer = ""
    if summary_data and isinstance(summary_data, dict):
        rows = summary_data.get("rows")
        cols = summary_data.get("cols")
        col_names = summary_data.get("col_names")
        samples = summary_data.get("samples")
        if (
            isinstance(rows, int)
            and rows == 1
            and isinstance(cols, int)
            and cols >= 1
            and isinstance(samples, list)
            and samples
        ):
            row0 = samples[0] if isinstance(samples[0], list) else []
            if isinstance(col_names, list) and len(col_names) >= len(row0):
                pairs = []
                for idx, value in enumerate(row0):
                    if idx >= len(col_names):
                        break
                    pairs.append(f"{col_names[idx]}={value}")
                if pairs:
                    answer = f"{intent} 결과: " + ", ".join(pairs)
                    return _format_user_answer_text(answer)
            if row0:
                answer = f"{intent} 결과: {', '.join([str(v) for v in row0])}"
                return _format_user_answer_text(answer)
        insight = _derive_insight_text(intent, summary_data, tool)
        if insight:
            answer = insight
        count = summary_data.get("count")
        if isinstance(count, int) and not answer:
            answer = f"{intent} 결과: {count}건"
    if not answer:
        answer = f"{intent} 완료"
    return _format_user_answer_text(answer)


def _ensure_user_answer_quality(
    intent: str,
    summary_data: dict[str, Any] | None,
    tool: str,
    answer: str | None,
) -> str:
    cleaned = _format_user_answer_text(answer or "")
    if cleaned and cleaned != f"{intent} 완료":
        return cleaned
    if summary_data and isinstance(summary_data, dict):
        improved = _build_user_facing_answer(intent, summary_data, tool)
        improved = _format_user_answer_text(improved)
        if improved:
            return improved
        rows = summary_data.get("rows")
        if isinstance(rows, int):
            return _format_user_answer_text(f"{intent} 결과: {rows}행을 확인했습니다.")
        rowcount = summary_data.get("rowcount")
        if isinstance(rowcount, int):
            return _format_user_answer_text(f"{intent} 결과: 영향 행수 {rowcount}건입니다.")
        count = summary_data.get("count")
        if isinstance(count, int):
            return _format_user_answer_text(f"{intent} 결과: {count}건입니다.")
    return _format_user_answer_text(cleaned or f"{intent} 처리 결과를 확인했습니다.")


def _build_user_facing_error(intent: str, err_msg: str) -> str:
    short = _shorten_error_for_user(err_msg)
    if not short:
        return ""
    intent = str(intent or "").strip() or "요청"
    return _format_user_answer_text(f"{intent} 처리 중 오류가 발생했습니다. {short}")


def _load_last_summary_dict_from_kv(kv: dict[str, Any] | None) -> dict[str, Any]:
    kv = kv or {}
    raw = kv.get("last_result_summary")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return {}
    return {}


def _build_forced_conclusion(
    original_request: str,
    kv: dict[str, Any] | None,
    step_trace: list[dict[str, Any]] | None,
) -> str:
    kv = kv or {}
    summary = _load_last_summary_dict_from_kv(kv)
    facts: list[str] = []
    schema_usage_intent = _is_schema_usage_intent(original_request)
    request_text = str(original_request or "").strip()
    if request_text:
        facts.append(f"현재 요청: {request_text}")
    intent = str(kv.get("last_result_intent") or "").strip()
    intent_similarity = _jaccard_similarity(request_text, intent) if request_text and intent else 0.0
    intent_is_relevant = bool(intent and (schema_usage_intent or intent_similarity >= 0.2))
    if intent_is_relevant:
        facts.append(f"마지막 실행 의도: {intent}")
    if intent_is_relevant:
        rows = summary.get("rows")
        if isinstance(rows, int):
            facts.append(f"최근 조회 결과 행수: {rows}행")
        else:
            rowcount = summary.get("rowcount")
            if isinstance(rowcount, int):
                facts.append(f"최근 실행 영향 행수: {rowcount}건")
            else:
                count = summary.get("count")
                if isinstance(count, int):
                    facts.append(f"최근 집계 결과 건수: {count}건")
    preferred_schema = str(kv.get("preferred_schema") or "").strip()
    if preferred_schema:
        facts.append(f"주요 대상 스키마: {preferred_schema}")
    if schema_usage_intent:
        compact = _load_last_search_objects_compact(kv)
        if compact:
            tables: list[str] = []
            for item in compact:
                if not isinstance(item, dict):
                    continue
                schema = _sanitize_ident_part(str(item.get("schema") or "").strip())
                if preferred_schema and schema and schema != preferred_schema:
                    continue
                table = _sanitize_ident_part(str(item.get("name") or "").strip())
                if not table:
                    continue
                if table not in tables:
                    tables.append(table)
            if tables:
                sample = ", ".join(tables[:5])
                facts.append(f"확인된 테이블: {len(tables)}개 (예: {sample})")
    last_sql = str(kv.get("last_sql") or "").strip()
    schema_name, table_name = _extract_first_table_from_sql(last_sql)
    if table_name:
        facts.append(
            f"최근 사용 테이블: {schema_name + '.' if schema_name else ''}{table_name}"
        )
    if not facts and step_trace:
        for entry in reversed(step_trace[-8:]):
            if not isinstance(entry, dict):
                continue
            summary_data = entry.get("result_summary")
            if isinstance(summary_data, dict):
                rows = summary_data.get("rows")
                if isinstance(rows, int):
                    facts.append(f"중간 집계 결과: {rows}행")
                break
    facts = [f for f in facts if f][: max(2, min(3, AGENT_FORCE_CONCLUSION_FACTS))]
    while len(facts) < 2:
        facts.append("현재까지 수집한 데이터로 요청 범위를 좁혀 재검증이 필요합니다.")

    last_error = str(kv.get("last_error") or "").strip()
    uncertainty = (
        _shorten_error_for_user(last_error)
        if last_error
        else "요청 조건(기간/대상/지표) 중 일부가 충분히 확정되지 않았습니다."
    )
    next_action = "후보 테이블 1개를 확정해 COUNT/집계 쿼리로 바로 재실행합니다."
    if schema_usage_intent and preferred_schema:
        next_action = (
            f"`{preferred_schema}` 스키마의 핵심 테이블을 기능군(예: 서버/이벤트/접속)으로 분류해 "
            "용도 결론을 확정합니다."
        )
    elif preferred_schema:
        next_action = (
            f"`{preferred_schema}` 스키마 기준으로 집계 쿼리 1개를 우선 실행해 결론값을 확정합니다."
        )

    lines = [
        "최대 단계에 도달하여 현재 기준 결론을 요약합니다.",
        "확정 사실:",
    ]
    for idx, fact in enumerate(facts, start=1):
        lines.append(f"{idx}. {fact}")
    lines.append(f"불확실성: {uncertainty}")
    lines.append(f"다음 액션: {next_action}")
    return _format_user_answer_text("\n".join(lines))


SQL_FILENAME_RE = re.compile(r"([A-Za-z0-9_\\-가-힣\\.]+\\.sql)", re.IGNORECASE)
DUMP_FILENAME_RE = re.compile(r"([A-Za-z0-9_\\-가-힣\\.]+\\.dump)", re.IGNORECASE)


def _extract_sql_filename(text: str) -> str:
    if not text:
        return ""
    match = SQL_FILENAME_RE.search(text)
    return match.group(1) if match else ""


def _extract_restore_filename(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"([A-Za-z0-9_\\-가-힣\\/\\.]+\\.(?:sql|dump))", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def _is_restore_execute_request(text: str, last_file_search_raw: str | None = None) -> bool:
    if not text:
        return False
    lower = text.lower()
    file_markers = ("파일", ".sql", ".dump", "/shared", "백업")
    has_restore_keyword = (
        any(token in lower for token in ("복원", "restore", "dump", "백업"))
        or bool(_extract_restore_filename(text))
        or ("복구" in lower and any(marker in lower for marker in file_markers))
    )
    has_restore_context = bool(str(last_file_search_raw or "").strip())
    followup_execute = any(token in text for token in ("그거", "이어서", "다시")) and any(
        token in text for token in ("실행", "진행", "적용")
    )
    if not has_restore_keyword and not (has_restore_context and followup_execute):
        return False
    if _is_restore_list_request(text):
        return False
    if any(token in text for token in ("실행", "진행", "적용", "복원해")):
        return True
    if has_restore_context and any(token in text for token in ("그거", "이어서", "다시")):
        return True
    return False


def _is_restore_list_request(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    if not any(token in lower for token in ("복원", "복구", "restore", "dump", "백업")):
        return False
    if "복구" in lower and not any(token in lower for token in ("파일", "복원", "sql", "dump", "백업")):
        return False
    return any(token in text for token in ("목록", "리스트", "조회", "보여", "찾아", "검색"))

SQL_INLINE_RE = re.compile(
    r"(?:sql\s*실행|sql|query|쿼리)\s*[:：]\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def _extract_sql_from_request(text: str) -> str:
    if not text:
        return ""
    match = SQL_INLINE_RE.search(text)
    if not match:
        return ""
    candidate = match.group(1).strip()
    if looks_like_sql(candidate):
        return candidate
    return ""


def _is_direct_sql_request(text: str) -> bool:
    if not text:
        return False
    if _extract_sql_from_request(text):
        return True
    return looks_like_sql(text)


def _maybe_build_sql_from_file(request: str, file_content: str) -> str:
    # SQL 파일의 내용 파싱/재구성은 LLM 단계로 넘긴다.
    # 코드에서 특정 테이블/컬럼을 추론하여 재작성하지 않는다.
    return ""


def looks_like_sql(text: str) -> bool:
    return bool(
        re.match(
            r"^\s*(select|show|with|insert|update|delete|create|alter|drop|truncate|rename|describe|desc|explain|call|set|use)\b",
            text,
            re.IGNORECASE,
        )
    )


def _sanitize_sql_candidate(text: str) -> str:
    sql = str(text or "").strip()
    if not sql:
        return ""
    if sql.startswith("```"):
        sql = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", sql, flags=re.IGNORECASE).strip()
        sql = re.sub(r"\s*```$", "", sql).strip()
    if sql.lower().startswith("sql\n"):
        sql = sql[4:].strip()
    if sql.lower().startswith("sql:"):
        sql = sql[4:].strip()
    return sql


def is_write_sql(sql: str) -> bool:
    return bool(
        re.match(
            r"^\s*(insert|update|delete|replace|create|alter|drop|truncate|rename|grant|revoke|call|set|start|commit|rollback)\b",
            sql,
            re.IGNORECASE,
        )
    )


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _normalize_sql_plan(plan: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return {
            "action": "step",
            "sql": "SHOW DATABASES",
            "intent": "LLM 플랜 생성 실패 — 기본 DB 목록 조회로 복구",
            "is_write": False,
        }

    action = str(plan.get("action", "ask")).strip().lower()
    if action not in ("step", "ask", "done"):
        action = "ask"

    intent = str(plan.get("intent", "")).strip() or "MySQL 요청 처리"
    is_write = bool(plan.get("is_write", False))

    if action == "step":
        tool = str(plan.get("tool", "")).strip()
        if tool:
            if tool not in LOCAL_TOOLS:
                return {
                    "action": "ask",
                    "question": f"지원되지 않는 로컬 도구({tool})입니다. 요청을 다시 입력해 주세요.",
                    "intent": intent,
                    "is_write": False,
                }
            args = plan.get("args") if isinstance(plan.get("args"), dict) else {}
            return {"action": "step", "tool": tool, "args": args, "intent": intent, "is_write": is_write}

        sql = str(plan.get("sql", "")).strip()
        if not sql:
            return {
                "action": "ask",
                "question": "실행할 SQL 의도를 구체적으로 알려주세요.",
                "intent": intent,
                "is_write": False,
            }
        return {"action": "step", "sql": sql, "intent": intent, "is_write": is_write or is_write_sql(sql)}

    if action == "done":
        return {"action": "done", "intent": intent, "is_write": is_write}

    question = str(plan.get("question", "")).strip()
    if not question:
        question = f"'{intent}' 작업을 진행하려면 대상 스키마 또는 테이블을 지정해 주세요."
    return {"action": "ask", "question": question, "intent": intent, "is_write": is_write}


def _normalize_mcp_plan(plan: dict[str, Any] | None, allowed_tools: list[str] | None = None) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return {
            "action": "step",
            "tool": "list_tables",
            "args": {},
            "intent": "LLM 플랜 생성 실패 — 기본 테이블 목록 조회로 복구",
            "is_write": False,
        }

    action = str(plan.get("action", "ask")).strip().lower()
    if action not in ("step", "ask", "done"):
        action = "ask"

    intent = str(plan.get("intent", "")).strip() or "MySQL MCP 요청 처리"
    is_write = bool(plan.get("is_write", False))

    if action == "done":
        return {"action": "done", "intent": intent, "is_write": is_write}

    if action == "ask":
        question = str(plan.get("question", "")).strip()
        if not question:
            question = f"'{intent}' 작업을 진행하려면 대상 스키마 또는 테이블을 지정해 주세요."
        return {"action": "ask", "question": question, "intent": intent, "is_write": is_write}

    tool = str(plan.get("tool", "")).strip()
    raw_args = plan.get("args") if isinstance(plan.get("args"), dict) else {}
    args: dict[str, Any] = {}
    for key, value in raw_args.items():
        if key in ("limit", "offset", "max_rows", "max_bytes", "top", "page_size"):
            try:
                num = int(value)
                if key == "limit" and num > 1000:
                    num = 1000
                args[key] = num
                continue
            except Exception:
                pass
        if key in ("include_current", "overwrite", "is_write"):
            if isinstance(value, str):
                args[key] = value.strip().lower() in ("1", "true", "yes", "y")
                continue
        args[key] = value
    if not tool:
        return {
            "action": "ask",
            "question": "MCP 도구 호출을 위해 필요한 정보가 부족합니다. 요청을 구체화해 주세요.",
            "intent": intent,
            "is_write": False,
        }
    if allowed_tools and tool not in allowed_tools and tool not in LOCAL_TOOLS:
        return {
            "action": "ask",
            "question": f"지원되지 않는 MCP 도구({tool})입니다. 가능한 도구를 먼저 확인해 주세요.",
            "intent": intent,
            "is_write": False,
        }
    if tool in MCP_EXECUTE_SQL_CANDIDATES:
        sql = str(args.get("sql", "")).strip()
        if not sql:
            return {
                "action": "ask",
                "question": "실행할 SQL이 비어 있습니다. 조회할 내용이나 조건을 알려주세요.",
                "intent": "SQL 입력 필요",
                "is_write": False,
            }
    return {"action": "step", "tool": tool, "args": args, "intent": intent, "is_write": is_write}

