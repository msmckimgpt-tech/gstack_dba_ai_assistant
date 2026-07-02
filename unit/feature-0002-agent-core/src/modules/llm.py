from datetime import datetime, timezone
import concurrent.futures
import mysql.connector
import os
import statistics
import time
__all__ = [
    "KNOWLEDGE_SQL_COMPOSE_PROMPT",
    "KNOWLEDGE_SQL_FORCE_PROMPT",
    "OBJECT_RESOLVE_PROMPT",
    "OBJECT_SQL_COMPOSE_PROMPT",
    "OBJECT_SQL_GROUNDING_REVIEW_PROMPT",
    "RAG_PRIORITY_PROMPT_MCP",
    "RAG_PRIORITY_PROMPT_SQL",
    "ACCOUNT_INSIGHT_PROMPT",
    "SCHEMA_INSIGHT_PROMPT",
    "SQL_FIX_PROMPT",
    "SUMMARY_PROMPT",
    "SYSTEM_PROMPT_MCP",
    "SYSTEM_PROMPT_SQL",
    "TABLE_INSIGHT_PROMPT",
    "TOPIC_PROMPT",
    "VALIDATION_PROMPT",
    "_build_summary_payload",
    "_compute_plan_timeout_sec",
    "_find_tool_name",
    "_generate_topic_from_request",
    "_get_llm_client",
    "_get_openai_client",
    "_has_insight_objects",
    "_is_search_objects_step",
    "_openai_chat_completion_with_deadline",
    "_openai_request_timeout",
    "_refresh_summary_after_ask",
    "_refresh_summary_after_step",
    "llm_classify_origin_shift",
    "llm_fix_sql",
    "llm_generate_topic",
    "llm_plan",
    "llm_account_insight",
    "llm_schema_insight",
    "llm_table_insight",
    "llm_update_summary",
    "llm_validate_step",
    "messages_for_provider",
]


"""OpenAI client, prompt templates, LLM call functions."""
from shared.config import *
from shared import config as cfg
from shared.model_catalog import max_tokens_for_model, model_supports_temperature, model_supports_vision, is_local_llm_model
from .utils import append_log_line
import json, os, time
from typing import Any


def _model_supports_temperature(model: str | None = None) -> bool:
    return model_supports_temperature(model or OPENAI_MODEL)


def _temperature_kwargs(model: str | None = None) -> dict[str, float]:
    if not _model_supports_temperature(model):
        return {}
    return {"temperature": 0}


def _max_tokens_kwargs(model: str | None = None, task: str = "agent") -> dict[str, int]:
    """모델별 max_tokens kwargs를 반환. 상용 LLM이면 빈 dict(제한 없음)."""
    limit = max_tokens_for_model(model, task)
    if limit is None:
        return {}
    return {"max_tokens": limit}


def messages_for_provider(
    messages: list[dict[str, Any]],
    *,
    image_attachments: list[dict[str, Any]] | None = None,
    vision_model: bool = False,
) -> list[dict[str, Any]]:
    """TASK-0094 Sprint 2 (D13) — DB string content 를 provider 직전 transient
    content-array 로 변환.

    DB (`AgentMemoryMessages.Content`) 는 string contract 유지 (§5.5) — share builder
    / fork / audit 모두 string content 그대로 사용. 본 helper 는 vision 호출 직전
    에만 호출되어 **첫 user message** 에 image inline 을 부착한다.

    Args:
        messages: 변환 전 messages list (DB string content). 각 entry 의 content 는
            string 또는 (이미 array 인 재진입) array.
        image_attachments: 부착할 image 첨부 목록 (None 또는 [] 면 변환 없음).
            각 entry 는 {
              "filename": str,       # logging 용 (provider 미송신, D12 정합)
              "mime_type": str,      # "image/png" / "image/jpeg" / "image/webp"
              "base64_data": str,    # D13 정합: server-side bytes read + base64 inline,
                                     #   signed URL 외부 송신 금지.
            }.
        vision_model: `model_supports_vision(model)` 결과. False 면 image_attachments
            가 있어도 변환 없이 원본 messages 반환 (caller 가 사용자 toast 책임).

    Returns:
        변환된 messages list. image_attachments 가 있고 vision_model=True 일 때만
        첫 user message 의 content 가 [{type:text}, {type:image_url}, ...] array 로
        변환. 그 외 경우는 원본 동등.

    Provider spec — OpenAI Chat Completions vision content array:
        {"role": "user",
         "content": [
            {"type": "text", "text": "<원본 string>"},
            {"type": "image_url",
             "image_url": {"url": "data:image/png;base64,..."}}
         ]}

    feature-0007 (bedrock) 정합: backend 는 OpenAI Chat Completions spec 으로
    content array 를 작성, LiteLLM proxy gateway (Bedrock 라우팅) 가 Anthropic
    Vision spec (`{"type":"image","source":{"type":"base64",...}}`) 로 자동
    normalize. drop_params=true 로 미지원 OpenAI param 은 silent drop.
    """
    if not image_attachments or not vision_model:
        return list(messages)

    out: list[dict[str, Any]] = []
    image_attached = False
    for msg in messages:
        if image_attached or msg.get("role") != "user":
            out.append(msg)
            continue
        text_content = msg.get("content", "")
        if not isinstance(text_content, str):
            # 이미 array form (재진입 또는 이전 turn 의 변환 결과) — 첫 image 가
            # 이 user message 에 이미 부착됐다고 간주. 후속 user message 의 추가
            # 변환을 방지 (idempotent + 첫 user 만 변환 invariant 유지).
            out.append(msg)
            image_attached = True
            continue
        content_array: list[dict[str, Any]] = [
            {"type": "text", "text": text_content},
        ]
        for img in image_attachments:
            b64 = str(img.get("base64_data") or "").strip()
            if not b64:
                continue
            mime = str(img.get("mime_type") or "image/png").strip() or "image/png"
            content_array.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            })
        if len(content_array) == 1:
            out.append(msg)
            continue
        new_msg = dict(msg)
        new_msg["content"] = content_array
        out.append(new_msg)
        image_attached = True
    return out


def _log_llm_warn(func_name: str, reason: str, extra: str = "") -> None:
    """LLM 호출 실패를 로그 파일에 기록."""
    msg = json.dumps(
        {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "func": func_name, "reason": reason, "detail": extra},
        ensure_ascii=False,
    )
    try:
        append_log_line("llm_warn", msg)
    except Exception:
        pass
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

def _find_tool_name(tool_names: list[str], candidates: tuple[str, ...]) -> str | None:
    if not tool_names:
        return None
    for candidate in candidates:
        if candidate in tool_names:
            return candidate
    for name in tool_names:
        for candidate in candidates:
            if name.startswith(candidate):
                return name
    return None


SYSTEM_PROMPT_SQL = f"""
당신은 MySQL 8.0 운영/분석을 담당하는 데이터베이스 작업자입니다.
사용자 입력은 비전문가의 한국어 자연어일 수 있으므로, 의도를 안전하게 해석해 실행 가능한 SQL 1단계만 반환하세요.
내부적으로 자문자답으로 계획을 점검하되, 출력에는 추론 과정을 노출하지 마세요.
반드시 JSON만 출력하세요(마크다운/설명문 금지).

환경 인지(중요):
- DBMS: MySQL 8.0 (Docker 컨테이너)
- 주 데이터베이스(설정값): `{DB_PROMPT_DEFAULT}`
- 메모리 데이터베이스: `{MEMORY_DB}`
- 공유 경로: `/shared`
- 백업 경로: `/shared/mysql-backup`
- 기본 문자셋/콜레이션: `utf8mb4` / `utf8mb4_unicode_ci`

출력 스키마:
{{
  "action": "step|ask|done",
  "sql": "step일 때 실행 SQL",
  "tool": "step일 때 로컬 도구명(file_search 또는 restore_sql)",
  "args": {{ "도구 인자": "값" }},
  "question": "ask일 때 사용자 확인 질문",
  "intent": "한 줄 의도 요약",
  "is_write": true|false
}}

우선순위 규칙:
1) 강제 규칙
2) 안정성 규칙
3) 작성 규칙

강제 규칙:
- `action`은 반드시 `step|ask|done` 중 하나.
- `step`이면 반드시 `sql` 또는 `tool` 중 하나 포함, `ask/done`이면 `sql/tool` 금지.
- SQL은 MySQL 문법만 사용.
- SQL Server 전용 문법 사용 금지: `TOP`, `[식별자]`, `GO`, `NVARCHAR`, `sp_executesql`.
- 스키마/테이블/컬럼/별칭 식별자는 `*`를 제외하고 가급적 백틱(`)으로 감쌈.
- 예약어를 식별자로 쓰는 경우 반드시 백틱으로 감쌈.
 - "DB 목록/데이터베이스 목록" 요청은 `SHOW DATABASES`로 처리한다.
 - "테이블 목록" 요청은 `information_schema.tables`를 사용한다.

안정성 규칙:
- 사용자가 변경을 명시하지 않으면 조회 SQL 우선.
- SELECT는 전체 조회 요구가 없으면 `LIMIT {AGENT_TOP_N}` 포함.
- DDL/DML은 사용자가 명시적으로 요구한 경우만 생성.
- 위험 작업(`DROP DATABASE`, 대량 삭제 등)은 명시 요청 없으면 생성 금지.
- 직전 단계 결과가 0건이면 동일 SQL을 반복하지 말고, 데이터 존재/기간 범위 확인용 진단 SQL을 1회 수행한 뒤 다음 단계로 진행한다.
- 진단까지 수행했는데도 0건이면 조건 변경 필요성을 간결하게 안내하고, 동일한 질의를 반복하지 않는다.
- 분포/히스토그램 요청에서 구간 크기가 없으면 기본 10단위 버킷으로 진행하고 질문으로 멈추지 않는다.
- "그 중 하나/아무거나/임의"처럼 파일 선택을 위임하면 최근 수정 파일을 자동 선택해 진행한다.
- 사용자가 스키마/DB를 명시하면 해당 스키마로 진행하고, 재확인 질문 없이 실행 후 가정사항만 간단히 언급한다.
- `appdb`를 기본/우선 스키마로 임의 가정하지 않는다. 실제 존재 여부를 확인한 뒤에만 사용한다.
- 진단 후 재집계 요청이면 데이터 존재 기간으로 자동 조정하고, 0건 원인이 되는 필터는 완화하여 진행한다.
- 로그/출력 파일 기록 여부나 경로는 사용자 확인을 요청하지 말고 내부적으로 처리한다. 결과와 필수 질문만 출력한다.
- 결과 파일 저장은 기본적으로 `/shared/out`의 타임스탬프 파일로 자동 저장하며, 사용자가 경로를 명시하지 않으면 경로 확인 질문을 하지 않는다.
- 사용자가 SQL/쿼리 파일 내용을 참조하라고 하면 추정하지 말고 `file_search` → `file_read`로 확인.
- `file_read`는 읽기 전용이므로 별도 허가 질문 없이 바로 `step`으로 실행한다.
- `last_file_search`가 1건이면 그 파일을 자동으로 `file_read`에 사용하고, 2건 이상이면 어떤 파일인지 `ask`로 확인한다.
- 파일/복원/경로 요청이 아닌데 파일 선택 질문을 하지 말 것.
- CSV 파일을 SQL로 로드하는 `LOAD DATA LOCAL INFILE`/`LOCAL INFILE` 사용 금지. CSV 후처리는 `file_read` 결과를 바탕으로 수행한다.
- 메타데이터 탐색은 동일 목적에 대해 1회만 수행하고, 이후에는 실제 집계 SQL로 전환한다.
- 사용자가 복원/덤프를 명시 요청했고 경로와 덮어쓰기 여부를 제공한 경우 `restore_sql`을 바로 실행한다(추가 허가 질문 금지).
- 조회/통계 요청에서 `knowledge.insight_objects` 또는 `kv.preferred_schema`가 있으면 `ask`를 반환하지 말고 `step`으로 SQL을 우선 실행한다.
- 불명확한 조회 요청도 generic 질문으로 멈추지 말고, 가능한 최소 검증 SQL 1회를 먼저 실행한다.
- `"요청 내용을 조금 더 구체적으로 알려주세요"` 같은 포괄적 질문은 금지한다.
- `ask`는 쓰기 작업의 파괴적 옵션 확인, 파일 대상 다중 후보 확정처럼 실행에 필수 정보가 없을 때만 허용한다.
- `ask` 질문은 가독성을 위해 문장 사이에 줄바꿈(`\n`)을 포함한다.
- 목표가 달성된 상태면 `done` 반환.
- 요청이 완료되면 `done`으로 종료하고, 다음 작업 제안/메뉴/후속 질문을 하지 않는다.
- 질문이 필요하더라도 확신 있는 어조로 간결하게 묻고, 불확실성이 낮으면 질문 없이 진행하라.

작성 규칙:
- 의도(`intent`)는 1문장.
- 쓰기 작업이면 `is_write=true`, 조회면 `false`.
- 가능한 경우 멱등성/검증 쿼리 우선.
- 설명/요약 요청은 근거 조회 없이 단정하지 말고 먼저 조회 단계 제안.
- 입력 JSON의 `step_trace`는 최근 수행한 단계들의 요약(현재 대화의 최신 실행 기록)이다. 이를 참고해 같은 탐색을 불필요하게 반복하지 말고 다음 단계로 진행하라.
- 입력 JSON의 `origin_request`는 최초 사용자 요청이다. `request`가 `continue`인 경우에도 항상 `origin_request`를 기준으로 작업하라.
- The `thread_goal` field in the input JSON is a stable summary of the current conversation thread's overarching goal. It changes less frequently than `origin_request`. When context is ambiguous, use `thread_goal` as the authoritative reference for what the user is trying to achieve.
- 입력 JSON의 `kv.kb_compact`는 사용자와 합의된 핵심 사실/결정을 요약한 지식이다. 반드시 우선 적용하고, 이미 답한 내용은 되묻지 마라.
- 입력 JSON의 `kv.global_kb_compact`는 모든 대화에서 공유되는 검증된 지식 요약이다. 가능한 한 재사용하고 중복 질문을 피하라.
- 입력 JSON의 `knowledge.facts`는 현재 대화에서 확정된 사실 목록이다. 최우선으로 반영하고 이미 확정된 사항은 되묻지 마라.
- 입력 JSON의 `knowledge.global_facts`는 전역 검증 사실 목록이다. 가능한 한 재사용하고 불필요한 탐색/질문을 피하라.
- 입력 JSON의 `knowledge.insight_objects`가 있으면 관련 객체를 우선 후보로 사용해 SQL을 작성하라. 불확실할 때만 최소 검증 1회 후 집계로 진행하라.
- 입력 JSON의 `knowledge.rag_objects`/`knowledge.rag_documents`가 있으면 이를 근거로 우선 SQL을 작성하라. 근거가 충분하면 메타탐색(`search_objects`/information_schema 반복 조회)을 건너뛰어라.
- **컬럼명 정확성(최우선)**: `knowledge.insight_objects`의 `summary` 또는 `columns` 필드에 컬럼명이 명시되어 있으면 반드시 그 **정확한 컬럼명**을 SQL에 사용하라. 추측이나 유사 이름(예: `KillCount` 대신 `Kills`)으로 대체하지 말 것. `columns` 배열이 있으면 해당 컬럼명만 사용하고, `summary`의 "주요 컬럼:" 이후 나열된 이름을 정확히 따르라.
- 입력 JSON의 `knowledge.related_conversations`는 다른 대화의 유사 사례 요약이다. 참고하되 사실로 단정하지 말고, 검증 필요 시 최소 1회만 확인한다.
- 입력 JSON의 `kv.retry_hint`가 있으면 동일한 접근을 반복하지 말고, 차선책으로 경로를 변경해 진행하라(요청을 차단하지 말 것).
- 입력 JSON의 `kv.last_error_type`/`kv.last_error_hint`를 참고해 이전 오류를 회피하는 쿼리/도구로 전환하라.
- `knowledge.*` 항목에는 `updated_at`/`age_hours`가 포함될 수 있다. 오래되었거나 불확실한 경우 최소 검증 쿼리를 수행하고, 전면 재탐색으로 되돌아가지 말라.
- 입력 JSON의 `kv.last_zero_result`가 1이면 직전 결과가 0건이므로, 원인 파악(기간/필터/테이블 선택)을 우선하고 같은 SQL을 재실행하지 말라.
- 사용자가 명확히 답변한 질문을 반복하지 말고, 답변을 사실로 간주해 다음 단계로 진행하라.
- 입력 JSON의 `force_stepwise`가 true이면 사용자가 순서를 명시한 것이므로 한 번에 하나의 작업만 수행하고 단계별로 나눠 진행하라(여러 도구/쿼리를 한 step에 합치지 말 것).
- 사용자가 특정 DB/스키마 이름을 언급하면 그 이름을 우선 사용하고, 필요 시 `information_schema`로 확인.
- 사용자가 구조를 모르겠다고 요청해도 먼저 `knowledge.rag_objects`/`knowledge.rag_documents`를 근거로 답변을 시도하고, 근거가 부족할 때만 `information_schema` 탐색으로 보완하라.
- 컬럼/필드 구조를 찾을 때는 `information_schema.COLUMNS`를 한 번에 조회해 탐색하라(테이블별 반복 조회 금지).
- `last_search_objects`, `last_file_search`, `last_file_read` 등 메모리 정보를 활용해 추가 질문 없이 다음 단계로 진행.
- 입력이 `continue`라면 직전 결과와 메모리를 참고해 목표 달성을 위한 다음 단계를 진행.

로컬 도구:
- file_search: 공유 경로(`/shared`)에서 파일 탐색.
  args: `root`(기본 `/shared`), `pattern`(부분 문자열 또는 파일명), `limit`(기본 50)
- file_read: 공유 경로(`/shared`)의 파일 내용을 읽어오기.
  args: `file_path`, `max_bytes`(기본 65536)
- restore_sql: SQL 파일을 MySQL에 복원.
  args: `file_path`, `database`, `overwrite`(true/false)
  주의: `file_path`는 반드시 `/shared` 하위 경로.
- convo_search: 다른 대화 기록을 검색(메시지/요약/주제).
  args: `query`(선택), `limit`(기본 50), `include_current`(기본 false)
로컬 도구는 항상 사용 가능하다고 가정한다.
""".strip()


SYSTEM_PROMPT_MCP = f"""
당신은 MySQL MCP 기반 운영/분석을 담당하는 데이터베이스 작업자입니다.
직접 DB 연결을 하지 말고 MCP 도구 호출 계획만 1단계 반환하세요.
반드시 JSON만 출력하세요(마크다운/설명문 금지).

환경 인지(중요):
- MCP 서버 URL: `{MCP_URL}`
- MCP 프로토콜: `{MCP_PROTOCOL}`
- 서버 구현은 DBHub 계열 HTTP MCP를 우선 가정
- 실제 사용 가능한 도구명은 런타임 `tools/list` 결과를 기준으로 판단
- 기본 데이터베이스(설정값): `{DB_PROMPT_DEFAULT}`

출력 스키마:
{{
  "action": "step|ask|done",
  "tool": "step일 때 MCP 도구명",
  "args": {{ "도구 인자": "값" }},
  "question": "ask일 때 사용자 확인 질문",
  "intent": "한 줄 의도 요약",
  "is_write": true|false
}}

도구 사용 원칙:
- 조회 요청은 `execute_sql` 계열 도구를 우선 사용하고 SELECT로 처리
- 메타데이터 탐색은 `knowledge.rag_objects`/`knowledge.rag_documents`로 근거가 부족한 경우에만 `search_objects` 계열 도구를 사용
- SQL/쿼리 파일 내용을 참조하라는 요청이면 `file_search` → `file_read`로 파일을 먼저 확인
- `file_read`는 읽기 전용이므로 허가 질문 없이 바로 실행
- `last_file_search`가 1건이면 그 파일을 자동 사용, 2건 이상이면 `ask`로 확인
- 복원 요청이 명확하면 `restore_sql`을 바로 실행
- 도구명이 애매하면 `ask`로 짧게 확인

로컬 도구(필요 시 사용 가능):
- file_search: 공유 경로(`/shared`)에서 파일 탐색.
  args: `root`(기본 `/shared`), `pattern`(부분 문자열 또는 파일명), `limit`(기본 50)
- file_read: 공유 경로(`/shared`)의 파일 내용을 읽어오기.
  args: `file_path`, `max_bytes`(기본 65536)
- restore_sql: SQL 파일을 MySQL에 복원.
  args: `file_path`, `database`, `overwrite`(true/false)
  주의: `file_path`는 반드시 `/shared` 하위 경로.
- convo_search: 다른 대화 기록을 검색(메시지/요약/주제).
  args: `query`(선택), `limit`(기본 50), `include_current`(기본 false)
로컬 도구는 항상 사용 가능하다고 가정한다.

규칙:
- `step`이면 반드시 `tool`/`args` 포함.
- `ask/done`이면 `tool`/`args` 금지.
- SQL은 MySQL 문법만 사용.
- SQL Server 전용 문법 사용 금지: `TOP`, `[식별자]`, `GO`, `NVARCHAR`, `sp_executesql`.
- 스키마/테이블/컬럼/별칭 식별자는 `*`를 제외하고 가급적 백틱(`)으로 감쌈.
- 예약어를 식별자로 쓰는 경우 반드시 백틱으로 감쌈.
- 스키마가 명시되지 않았으면 특정 스키마를 임의 가정하지 말고 `DATABASE()` 또는 `SHOW DATABASES`/`information_schema`로 먼저 확인.
- "DB 목록/데이터베이스 목록" 요청은 `execute_sql`로 `SHOW DATABASES` 실행.
- "테이블 목록" 요청은 `execute_sql`로 `information_schema.tables` 조회.
- SELECT는 전체 조회 요구가 없으면 `LIMIT {AGENT_TOP_N}` 포함.
- 변경 요청이 명시되지 않으면 `is_write=false`.
- 같은 실패 도구 호출을 무한 반복하지 말고, 실패 시 다른 도구로 전환하거나 `ask`.
- 직전 단계 결과가 0건이면 동일 SQL을 반복하지 말고, 데이터 존재/기간 범위 확인용 진단 SQL을 1회 수행한 뒤 다음 단계로 진행한다.
- 진단까지 수행했는데도 0건이면 조건 변경 필요성을 간결하게 안내하고, 동일한 질의를 반복하지 않는다.
- 로그/출력 파일 기록 여부나 경로는 사용자 확인을 요청하지 말고 내부적으로 처리한다. 결과와 필수 질문만 출력한다.
- 결과 파일 저장은 기본적으로 `/shared/out`의 타임스탬프 파일로 자동 저장하며, 사용자가 경로를 명시하지 않으면 경로 확인 질문을 하지 않는다.
- 분포/히스토그램 요청에서 구간 크기가 없으면 기본 10단위 버킷으로 진행하고 질문으로 멈추지 않는다.
- "그 중 하나/아무거나/임의"처럼 파일 선택을 위임하면 최근 수정 파일을 자동 선택해 진행한다.
- 사용자가 스키마/DB를 명시하면 해당 스키마로 진행하고, 재확인 질문 없이 실행 후 가정사항만 간단히 언급한다.
- `appdb`를 기본/우선 스키마로 임의 가정하지 않는다. 실제 존재 여부를 확인한 뒤에만 사용한다.
- 진단 후 재집계 요청이면 데이터 존재 기간으로 자동 조정하고, 0건 원인이 되는 필터는 완화하여 진행한다.
- 조회/통계 요청에서 `knowledge.insight_objects` 또는 `kv.preferred_schema`가 있으면 `ask`를 반환하지 말고 `execute_sql` `step`을 우선 반환한다.
- 불명확한 조회 요청도 generic 질문으로 멈추지 말고, 가능한 최소 검증 SQL 1회를 먼저 실행한다.
- `"요청 내용을 조금 더 구체적으로 알려주세요"` 같은 포괄적 질문은 금지한다.
- `ask`는 쓰기 작업의 파괴적 옵션 확인, 파일 대상 다중 후보 확정처럼 실행에 필수 정보가 없을 때만 허용한다.
- `ask` 질문은 가독성을 위해 문장 사이에 줄바꿈(`\n`)을 포함한다.
- 파일/복원/경로 요청이 아닌데 파일 선택 질문을 하지 말 것.
- 요청이 완료되면 `done`으로 종료하고, 다음 작업 제안/메뉴/후속 질문을 하지 않는다.
- 사용자가 특정 DB/스키마 이름을 언급하면 `args.schema`에 그 이름을 우선 사용.
- 복수 스키마가 언급되면 한 번에 하나씩 대상으로 `step`을 수행하고, 다음 단계에서 이어서 처리.
- 동일한 도구/인자로 같은 탐색을 반복하지 말고, `last_search_objects`/`last_csv_preview` 등을 활용해 다음 단계(컬럼/샘플 조회 또는 집계 SQL)로 진행.
- 입력 JSON의 `step_trace`는 최근 수행한 단계들의 요약(현재 대화의 최신 실행 기록)이다. 이를 참고해 같은 탐색을 불필요하게 반복하지 말고 다음 단계로 진행.
- 입력 JSON의 `origin_request`는 최초 사용자 요청이다. `request`가 `continue`인 경우에도 항상 `origin_request`를 기준으로 작업하라.
- The `thread_goal` field in the input JSON is a stable summary of the current conversation thread's overarching goal. It changes less frequently than `origin_request`. When context is ambiguous, use `thread_goal` as the authoritative reference for what the user is trying to achieve.
- 입력 JSON의 `kv.kb_compact`는 사용자와 합의된 핵심 사실/결정 요약이며 반드시 우선 적용한다.
- 입력 JSON의 `kv.global_kb_compact`는 모든 대화에서 공유되는 검증된 지식 요약이다. 가능한 한 재사용하고 중복 질문을 피하라.
- 입력 JSON의 `knowledge.facts`는 현재 대화에서 확정된 사실 목록이다. 최우선으로 반영하고 이미 확정된 사항은 되묻지 마라.
- 입력 JSON의 `knowledge.global_facts`는 전역 검증 사실 목록이다. 가능한 한 재사용하고 불필요한 탐색/질문을 피하라.
- 입력 JSON의 `knowledge.insight_objects`가 있으면 해당 객체를 우선 후보로 사용해 `execute_sql` 중심으로 진행하라. 불확실할 때만 최소 검증 1회 후 집계로 진행하라.
- 입력 JSON의 `knowledge.rag_objects`/`knowledge.rag_documents`가 있으면 이를 근거로 `execute_sql` 계획을 우선 반환하라. 근거가 충분하면 `search_objects`를 사용하지 마라.
- **컬럼명 정확성(최우선)**: `knowledge.insight_objects`의 `summary` 또는 `columns` 필드에 컬럼명이 명시되어 있으면 반드시 그 **정확한 컬럼명**을 SQL에 사용하라. 추측이나 유사 이름(예: `KillCount` 대신 `Kills`)으로 대체하지 말 것. `columns` 배열이 있으면 해당 컬럼명만 사용하고, `summary`의 "주요 컬럼:" 이후 나열된 이름을 정확히 따르라.
- 입력 JSON의 `knowledge.related_conversations`는 다른 대화의 유사 사례 요약이다. 참고하되 사실로 단정하지 말고, 검증 필요 시 최소 1회만 확인한다.
- 입력 JSON의 `kv.retry_hint`가 있으면 동일한 접근을 반복하지 말고, 차선책으로 경로를 변경해 진행하라(요청을 차단하지 말 것).
- 입력 JSON의 `kv.last_error_type`/`kv.last_error_hint`를 참고해 이전 오류를 회피하는 도구/쿼리로 전환하라.
- `knowledge.*` 항목에는 `updated_at`/`age_hours`가 포함될 수 있다. 오래되었거나 불확실한 경우 최소 검증 쿼리를 수행하고, 전면 재탐색으로 되돌아가지 말라.
- 사용자가 명확히 답변한 질문을 반복하지 말고, 답변을 사실로 간주해 다음 단계로 진행하라.
- 입력 JSON의 `force_stepwise`가 true이면 사용자가 순서를 명시한 것이므로 한 번에 하나의 작업만 수행하고 단계별로 나눠 진행하라(여러 도구/쿼리를 한 step에 합치지 말 것).
- `last_search_objects`, `last_file_search`, `last_file_read` 등 메모리 정보를 활용해 추가 질문 없이 다음 단계로 진행.
- 사용자가 구조를 모르겠다고 요청해도 먼저 `knowledge.rag_objects`/`knowledge.rag_documents`를 근거로 답변을 시도하고, 근거가 부족할 때만 `information_schema` 또는 `search_objects`를 수행하라.
- 컬럼/필드 구조를 찾을 때는 `information_schema.COLUMNS`를 한 번에 조회해 탐색하라(테이블별 반복 조회 금지).
- 입력이 `continue`라면 직전 결과와 메모리를 참고해 목표 달성을 위한 다음 단계를 진행.
- 입력 JSON의 `kv.last_zero_result`가 1이면 직전 결과가 0건이므로, 원인 파악(기간/필터/테이블 선택)을 우선하고 같은 SQL을 재실행하지 말라.

복잡 SQL 생성(필수):
- 요청이 복잡하더라도 SQL을 단순화하거나 일부만 수행하지 말고, **요청 전체를 충족하는 완전한 SQL 1문**을 생성하라.
- WITH (CTE), 재귀 CTE(`WITH RECURSIVE`), 윈도우 함수(`ROW_NUMBER`, `RANK`, `LAG/LEAD` 등), 서브쿼리 중첩을 자유롭게 활용하라.
- MySQL 8.0은 CTE, 윈도우 함수, JSON 함수, HEX/UNHEX, CONV, BIT_COUNT 등을 모두 지원한다.
- 3중·4중 서브쿼리나 재귀 CTE가 필요하면 주저 없이 작성하라.
- **크로스 스키마 JOIN**: 하나의 SQL에서 `schema_a`.`table_x` JOIN `schema_b`.`table_y` 형태로 여러 스키마의 테이블을 자유롭게 조인할 수 있다.
  - 예: `SELECT ... FROM `have_00`.`limitgacha` lg JOIN `dev_1_1_1_20`.`limitgachainfo` li ON lg.`lg_groupid` = li.`lg_groupid``
  - knowledge 근거에 서로 다른 스키마의 객체가 있으면 크로스 스키마 조인을 적극 활용하라.
- **BINARY/비트 연산**: MySQL의 BINARY(N) 컬럼에서 특정 비트를 추출하려면 바이트 단위로 처리한다.
  - `SUBSTRING(col, byte_pos, 1)` → 특정 바이트 추출 (1-based 인덱스)
  - `ORD(SUBSTRING(col, byte_pos, 1))` → 해당 바이트의 정수값
  - 비트 위치 `bit_idx`에 대해: `byte_pos = (bit_idx DIV 8) + 1`, `bit_mask = 1 << (bit_idx MOD 8)` 또는 `1 << (7 - (bit_idx MOD 8))` (빅엔디안)
  - 비트 체크: `ORD(SUBSTRING(col, byte_pos, 1)) & bit_mask` 이 0이 아니면 해당 비트가 1
  - NOT 연산: `~ORD(SUBSTRING(col, byte_pos, 1)) & 0xFF`로 바이트 단위 NOT 수행
  - 복수 바이트 전체를 순회하려면 `numbers` CTE나 재귀 CTE로 0~N-1 인덱스를 생성하고 CROSS JOIN하라.
  - 예: `~(status & configuration)` 연산 후 비트가 1인 위치 = 뽑혔거나 설정에 없는 슬롯
- 사용자가 비트 연산 공식을 제시하면 그 공식을 최대한 충실히 SQL로 변환하라. 단순화하거나 근사치로 대체하지 말 것.
""".strip()


RAG_PRIORITY_PROMPT_SQL = """
당신은 MySQL SQL 플래너다.
요청 원문과 knowledge 근거를 이용해 즉시 실행 가능한 SQL 1단계를 작성하라.
반드시 JSON만 출력하고 설명문/마크다운은 금지한다.

출력 스키마:
{
  "action": "step|ask|done",
  "sql": "step일 때 SQL",
  "question": "ask일 때 질문",
  "intent": "한 줄 의도",
  "is_write": true|false
}

규칙:
- `knowledge.insight_objects` 또는 `knowledge.rag_objects`에 table 근거가 1개 이상 있으면 반드시 `action=step`으로 SQL을 생성한다.
- 근거가 충분할 때 `information_schema` 탐색 SQL을 생성하지 않는다.
- 요청에서 언급된 객체명과 가장 직접적으로 일치하는 table/schema를 우선 사용한다.
- 스키마를 임의 가정하지 말고, 근거에 포함된 schema/table을 그대로 사용한다.
- 근거가 정말 부족할 때만 `ask`를 반환한다.
- SQL은 MySQL 문법만 사용한다.

복잡 SQL 생성(필수):
- 요청이 복잡하더라도 SQL을 단순화하거나 일부만 수행하지 말고, **요청 전체를 충족하는 완전한 SQL 1문**을 생성하라.
- WITH (CTE), 재귀 CTE(`WITH RECURSIVE`), 윈도우 함수, 서브쿼리 중첩을 자유롭게 활용하라.
- **크로스 스키마 JOIN**: knowledge 근거에 서로 다른 스키마의 객체가 있으면 `schema_a`.`table_x` JOIN `schema_b`.`table_y` 형태로 적극 사용하라.
- **BINARY/비트 연산**: SUBSTRING(col, byte_pos, 1), ORD()로 바이트 단위 처리한다. 비트 순회는 numbers CTE + CROSS JOIN 활용.
- 사용자 비트 연산 공식을 충실히 SQL로 변환, 단순화/근사치 금지.
""".strip()


RAG_PRIORITY_PROMPT_MCP = """
당신은 MySQL MCP 플래너다.
요청 원문과 knowledge 근거를 이용해 즉시 실행 가능한 MCP 1단계를 작성하라.
반드시 JSON만 출력하고 설명문/마크다운은 금지한다.

출력 스키마:
{
  "action": "step|ask|done",
  "tool": "step일 때 MCP 도구명",
  "args": {"도구 인자": "값"},
  "question": "ask일 때 질문",
  "intent": "한 줄 의도",
  "is_write": true|false
}

규칙:
- `knowledge.insight_objects` 또는 `knowledge.rag_objects`에 table 근거가 1개 이상 있으면 반드시 `action=step`과 `execute_sql` 계열 도구를 사용한다.
- 근거가 충분할 때 `search_objects`/`information_schema` 메타 탐색을 수행하지 않는다.
- 요청에서 언급된 객체명과 가장 직접적으로 일치하는 table/schema를 우선 사용한다.
- 스키마를 임의 가정하지 말고, 근거에 포함된 schema/table을 그대로 사용한다.
- 근거가 정말 부족할 때만 `ask`를 반환한다.
- SQL은 MySQL 문법만 사용한다.

복잡 SQL 생성(필수):
- 요청이 복잡하더라도 SQL을 단순화하거나 일부만 수행하지 말고, **요청 전체를 충족하는 완전한 SQL 1문**을 생성하라.
- WITH (CTE), 재귀 CTE(`WITH RECURSIVE`), 윈도우 함수, 서브쿼리 중첩을 자유롭게 활용하라.
- **크로스 스키마 JOIN**: knowledge 근거에 서로 다른 스키마의 객체가 있으면 `schema_a`.`table_x` JOIN `schema_b`.`table_y` 형태로 적극 사용하라.
- **BINARY/비트 연산**: SUBSTRING(col, byte_pos, 1), ORD()로 바이트 단위 처리한다. 비트 순회는 numbers CTE + CROSS JOIN 활용.
- 사용자 비트 연산 공식을 충실히 SQL로 변환, 단순화/근사치 금지.
""".strip()


VALIDATION_PROMPT = """
You are a validation agent. Judge whether the step performed aligns with the original request.
Return JSON only. Do not include reasoning text or markdown.

Output schema:
{
  "ok": true|false,
  "score": 0-100,
  "weights": {
    "goal_alignment": 0.0-1.0,
    "data_sufficiency": 0.0-1.0,
    "step_utility": 0.0-1.0,
    "risk": 0.0-1.0
  },
  "notes": ["short note"]
}

Rules:
- Choose weights yourself; they should sum to 1.0 (approximately).
- Keep notes short and actionable.
""".strip()


SUMMARY_PROMPT = """
You are a summarization agent for a MySQL assistant.
Update the conversation summary using the provided context.
Return JSON only. Do not include reasoning text or markdown.

Output schema:
{
  "summary": "concise Korean summary"
}

Rules:
- Keep it concise and factual.
- Preserve key decisions, constraints, DB/schema/table/file names, and errors.
- Do not include raw SQL unless explicitly requested by the user.
- If prior summary exists, update it instead of replacing with only the latest step.
""".strip()

SQL_FIX_PROMPT = """
You are a MySQL 8.0 SQL fixer.
Fix execution-blocking SQL errors using the provided error message.
Allowed fixes:
- syntax/parse errors
- unknown schema/table/column errors
- invalid identifier/alias references
Keep user intent unchanged. Prefer minimal edits.
When an identifier is invalid, rewrite to a valid alternative that preserves intent.
IMPORTANT: If `columns_hint` is provided in the input, use those exact column names to fix unknown column errors. Do NOT guess column names — use only the provided hints.
Do not produce write SQL.
Return JSON only. No markdown, no commentary.

Output schema:
{
  "sql": "fixed sql"
}
""".strip()


TOPIC_PROMPT = """
You are a topic labeling agent for a MySQL assistant.
Generate a concise Korean topic for the conversation.
Return JSON only. Do not include reasoning text or markdown.

Output schema:
{
  "topic": "short Korean topic"
}

Rules:
- Keep it short (max 12 words).
- Reflect the user's intent, not the assistant's steps.
- Avoid quoting the full user sentence verbatim.
""".strip()


GLOSSARY_SUGGEST_PROMPT = """
You are a domain glossary extractor for a Korean MySQL/MSSQL DBA assistant.
From one Q&A turn (user question + assistant answer), extract domain TERMS that are
worth saving in a shared glossary — business/domain vocabulary, table/metric meanings,
status codes explained in prose, or jargon the answer defined.
Return JSON only. No markdown, no reasoning text.

Output schema:
{
  "terms": [
    {"term": "용어", "definition": "1~2문장 한국어 정의", "confidence": 0.0~1.0}
  ]
}

Rules:
- Only include a term if the turn actually defines or clarifies its meaning. If nothing
  qualifies, return {"terms": []}.
- definition must be self-contained Korean (1~2 sentences), not "see above".
- confidence reflects how clearly the term is defined AND how reusable it is
  (0.9+ = explicitly defined & broadly reusable, 0.5 = plausible but uncertain).
- Do NOT invent terms not grounded in the text. Do NOT include generic SQL keywords
  (SELECT, JOIN), the assistant's process steps, or PII.
- At most 5 terms. Prefer the most reusable ones.
""".strip()


# TASK-0129 (#3): tier-aware LLM client. 이전엔 단일 LLM_BASE_URL(Bedrock 우선) 로 모든
# 호출이 가서 edge-tier 모델명('edge'/'core'/'auto'/'code')이 Bedrock gateway 에 전달돼
# HTTP 400 ("Invalid model name passed in model=edge") — 하루 ~47만건 silent 실패 + 전체
# cost/quality tier 라우팅 무력화. 이제 model 의 tier 로 base_url/key 를 선택하고 tier 별로
# client 를 캐시한다. local gateway 는 'edge'/'core' 별칭을, Bedrock 은 'claude-*' 를 받는다.
_TIER_CLIENT_CACHE: "dict[tuple, Any]" = {}


def _resolve_tier_endpoint(model: str | None) -> "tuple[str | None, str | None]":
    """model 의 tier 에 맞는 (base_url, api_key) 반환. 해당 tier creds 미설정 시 기본 provider 폴백."""
    from shared.config import (
        LLM_BASE_URL, LLM_API_KEY,
        BEDROCK_GATEWAY_URL, BEDROCK_GATEWAY_API_KEY,
        LOCAL_LLM_API_BASE, LOCAL_LLM_API_KEY,
    )
    if model is not None and is_local_llm_model(model):
        if LOCAL_LLM_API_BASE and LOCAL_LLM_API_KEY:
            return (LOCAL_LLM_API_BASE, LOCAL_LLM_API_KEY)
    else:
        if BEDROCK_GATEWAY_URL and BEDROCK_GATEWAY_API_KEY:
            return (BEDROCK_GATEWAY_URL, BEDROCK_GATEWAY_API_KEY)
    return (LLM_BASE_URL, LLM_API_KEY)


def _get_llm_client(timeout_sec: int | None = None, model: str | None = None) -> OpenAI | None:
    # feature-0007: LLM 자격증명은 env 단일 소스. TASK-0129: model tier 로 endpoint 분기 + 캐시.
    # TASK-0237: 함수명 _get_openai_client → _get_llm_client (실제 provider 는 Bedrock Claude;
    # OpenAI 클래스는 OpenAI Chat Completions 규약 전송 클라이언트로만 사용). 구이름은 아래 alias 로 호환.
    if OpenAI is None:
        return None
    base_url, api_key = _resolve_tier_endpoint(model)
    if not api_key:
        return None
    timeout_val = max(5, int(timeout_sec) if timeout_sec is not None else int(AGENT_TIMEOUT_SEC))
    cache_key = (base_url, api_key, timeout_val)
    cached = _TIER_CLIENT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        kwargs: dict = {
            "api_key": api_key,
            "timeout": timeout_val,
            "max_retries": max(0, int(AGENT_OPENAI_MAX_RETRIES)),
        }
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)
        _TIER_CLIENT_CACHE[cache_key] = client
        return client
    except Exception:
        return None


# TASK-0237: deprecated alias — 구 호출처/외부 import (kb_retrieval, app.py) 및 앵커 불변식
# 테스트 호환. 신규 코드는 _get_llm_client 사용. 다음 cycle 에 alias 제거 검토.
_get_openai_client = _get_llm_client


def _record_llm_usage(
    model: str, task: str, resp,
    conversation_id: str | None = None, run_id: str | None = None,
    latency_ms: int | None = None,
) -> None:
    """TASK-0136 (#11): LLM 호출 토큰 사용량을 agent_runtime.llm_usage 에 기록 (best-effort).
    모든 LLM 호출의 단일 chokepoint 에서 포착 → 비용 가시성. 실패해도 LLM 응답에 무영향.
    account 는 admin 조회 시 core_conversations join 으로 도출.
    (pgbouncer transaction pool 경유라 per-call conn 비용 낮음.)

    TASK-0163: `/api/ask` 는 agent 를 web 프로세스 안 in-process(`asyncio.to_thread`)로
    실행하므로([[TASK-0159]]) cfg.MEMORY_CONVERSATION_ID/CURRENT_RUN_ID 전역은 동시 ask
    (WEB_PARALLEL_LIMIT) 간 덮어써져 토큰이 잘못된 계정/역할에 귀속될 수 있다. 따라서
    메인 추론 경로는 호출 스택의 정확한 conversation_id/run_id 를 **명시 인자**로 전달한다
    (thread 격리). 미전달 helper(classify/topic 등 소량 호출)는 기존 cfg 전역 fallback —
    이들의 전역 race 는 기존 동작이며 본 cycle 범위 밖(follow-up)."""
    try:
        usage = getattr(resp, "usage", None)
        if usage is None:
            return
        pt = int(getattr(usage, "prompt_tokens", 0) or 0)
        ct = int(getattr(usage, "completion_tokens", 0) or 0)
        tt = int(getattr(usage, "total_tokens", 0) or (pt + ct))
        if tt <= 0:
            return
        conv = conversation_id if conversation_id is not None else (str(getattr(cfg, "MEMORY_CONVERSATION_ID", "") or "") or None)
        run = run_id if run_id is not None else (str(getattr(cfg, "CURRENT_RUN_ID", "") or "") or None)
        # TASK-0163: provider 가 응답으로 반환한 실제 서빙 모델명(LiteLLM 이 별칭을 해소한
        # 결과). 요청 별칭(model)만으론 claude 계열 구분 불가 → resolved_model 로 보존.
        served = str(getattr(resp, "model", "") or "")[:128] or None
        # AI 운영 관제 계측(TASK-AIOPS): 순수 API 왕복 지연(ms). 미측정(latency_ms 미전달)은
        # NULL 로 남겨 통계(p50/p95)에서 제외 — DEFAULT 0 을 쓰지 않는 이유(미측정=0ms 오염 방지).
        try:
            lat = int(latency_ms) if latency_ms is not None else None
            if lat is not None and lat < 0:
                lat = None
        except Exception:
            lat = None
        from .runtime_backend import _get_pg_runtime_conn
        pg = _get_pg_runtime_conn()
        if not pg:
            return
        try:
            with pg.cursor() as cur:
                cur.execute(
                    "INSERT INTO agent_runtime.llm_usage "
                    "(conversation_id, run_id, model, resolved_model, task, prompt_tokens, completion_tokens, total_tokens, latency_ms) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (conv, run, str(model or "")[:128], served, str(task or "")[:64], pt, ct, tt, lat),
                )
            pg.commit()
        finally:
            try:
                pg.close()
            except Exception:
                pass
    except Exception:
        pass


def _openai_request_timeout(timeout_sec: int | None = None) -> int:
    try:
        val = int(timeout_sec) if timeout_sec is not None else int(AGENT_TIMEOUT_SEC)
    except Exception:
        val = int(AGENT_TIMEOUT_SEC)
    return max(5, val)


def _openai_chat_completion_with_deadline(
    client,
    model: str,
    messages: list[dict[str, Any]],
    timeout_sec: int | None = None,
    task: str = "agent",
):
    # TASK-0129 (#3): model 의 tier 에 맞는 client 로 재해석. caller 가 default client 를
    # 넘겨도 'edge'/'core' 는 local gateway, 'claude-*' 는 Bedrock 으로 보장 (라우팅 회귀 차단).
    resolved = _get_llm_client(timeout_sec=timeout_sec, model=model)
    if resolved is not None:
        client = resolved
    if client is None:
        return None
    wall_sec = _openai_request_timeout(timeout_sec)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    create_kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "timeout": _openai_request_timeout(timeout_sec),
    }
    create_kwargs.update(_max_tokens_kwargs(model, task))
    create_kwargs.update(_temperature_kwargs(model))
    _lat_t0 = time.perf_counter_ns()  # TASK-AIOPS: 순수 API 왕복 지연 측정 시작(submit 직전)
    future = executor.submit(
        client.chat.completions.create,
        **create_kwargs,
    )
    try:
        resp = future.result(timeout=wall_sec)
        _lat_ms = (time.perf_counter_ns() - _lat_t0) // 1_000_000
        _record_llm_usage(model, task, resp, latency_ms=int(_lat_ms))  # TASK-0136 (#11): best-effort 토큰+지연 회계
        return resp
    except concurrent.futures.TimeoutError:
        _log_llm_warn("_openai_chat_completion_with_deadline", "timeout", f"model={model} wall_sec={wall_sec}")
        try:
            future.cancel()
        except Exception:
            pass
        return None
    except Exception as exc:
        # TASK-0129 (#3): HTTP status/body 를 로그에 포함 — tier 별칭 거부(400) 등이
        # 'exception' 한 줄로만 보이던 것을 진단 가능하게.
        status = getattr(exc, "status_code", None)
        body = ""
        resp = getattr(exc, "response", None)
        if resp is not None:
            try:
                body = (getattr(resp, "text", "") or "")[:300]
            except Exception:
                body = ""
        _log_llm_warn(
            "_openai_chat_completion_with_deadline",
            "exception",
            f"model={model} {type(exc).__name__} status={status}: {str(exc)[:200]} body={body}",
        )
        return None
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _compute_plan_timeout_sec(
    step_index: int,
    kv: dict[str, Any] | None,
    elapsed_ms: float,
) -> int:
    kv = kv or {}
    base = max(5, int(AGENT_PLAN_TIMEOUT_SEC))
    has_retry_signal = bool(
        str(kv.get("last_error") or "").strip()
        or str(kv.get("retry_hint") or "").strip()
        or str(kv.get("last_auto_recovery") or "").strip()
    )
    if step_index > 0 or has_retry_signal:
        base = min(base, max(5, int(AGENT_PLAN_TIMEOUT_RECOVERY_SEC)))
    remaining_budget_ms = max(0, int(AGENT_EARLY_FINALIZE_MS - max(0.0, float(elapsed_ms))))
    remaining_cap = max(
        int(AGENT_PLAN_TIMEOUT_MIN_SEC),
        int(remaining_budget_ms / 1000.0) - 2,
    )
    return max(
        int(AGENT_PLAN_TIMEOUT_MIN_SEC),
        min(base, remaining_cap),
    )


SCHEMA_INSIGHT_PROMPT = """You are a database schema analyst. Return JSON only — no markdown, no explanation.

This is a game server database. Typical domains:
- Account/Auth (login, billing, user management)
- Game Data (player stats, heroes, battles, items, inventory, guilds)
- Game Logs (action logs, event history, analytics)
- Config/Design (item templates, stage configs, constants)
- Global/Server (server settings, announcements, events)

Input: schema name + column name samples.
Output (JSON only):
{
  "domain": "English domain label from the list above",
  "summary": "English 1-2 sentence summary of what this schema contains",
  "key_columns": ["up to 6 representative columns from the input"]
}""".strip()


TABLE_INSIGHT_PROMPT = """You are a database table analyst. Return JSON only — no markdown, no explanation.

Game server database. Typical domains: Account, Game Data, Game Logs, Config/Design, Global/Server.

Input: schema name, table name, column list with types.
Output (JSON only):
{
  "domain": "English domain label",
  "summary": "English 1 sentence — what this table stores",
  "usage": "English 1 sentence — how this table is typically queried",
  "key_columns": ["up to 6 key columns from the input"]
}""".strip()


ACCOUNT_INSIGHT_PROMPT = """You distill a SINGLE user's recurring analytical interest from one past conversation, so a future conversation can softly recall the user's context. Return JSON only — no markdown, no explanation.

CRITICAL — PRIVACY: Output MUST be a high-level, PII-FREE generalization. NEVER include any concrete data values, personal names, emails, phone numbers, account/resident IDs, IP addresses, specific row values, or verbatim quotes. Describe the *kind* of analysis (domain, metric family, table/topic area, recurring question type), not the data itself. If the conversation has no durable analytical interest worth remembering, return {"insight": ""}.

Input JSON: { "summary": "...", "origin_request": "...", "thread_goal": "...", "topic": "..." }
Output (JSON only):
{
  "insight": "Korean 1 sentence, PII-free — e.g. '사용자는 주문/결제 도메인의 일별 매출 집계와 환불율 추이에 반복적으로 관심을 보임'. Empty string if nothing durable."
}""".strip()


NODE_ANALYSIS_PROMPT = """You are a metadata knowledge-graph analyst for a game-service database platform. A user opened the admin graph view and asked the AI to actively analyze one node (a Table, Column, Schema, or business GlossaryTerm) together with its related neighbors. Return JSON only — no markdown, no explanation.

You are given the focus node and its immediate graph neighbors (columns, referenced tables/columns, related glossary terms). Reason about what this node represents in the game-operations domain, how it connects to its neighbors, and how an operator/analyst would use it. Be concrete but do NOT invent columns or relationships not present in the input. Write the prose in Korean.

Input JSON: { "label": "Table|Column|Schema|GlossaryTerm", "name": "...", "fqn": "...", "description": "...", "scope_key": "...", "neighbors": { "columns": [...], "references": [...], "related_terms": [...], "other": [...] } }

Output (JSON only):
{
  "summary": "Korean 1-2 sentences — 이 노드가 무엇을 담고/의미하고, 도메인상 역할",
  "relationships": "Korean 1-2 sentences — 이웃(컬럼/참조/관련용어)과 어떻게 연결되는지. 이웃 정보가 없으면 '연결 정보 없음'",
  "usage": "Korean 1 sentence — 운영/분석에서 이 노드를 어떻게 조회·활용하는지",
  "caveats": "Korean, 있으면 데이터 품질/민감정보/주의점 1문장, 없으면 빈 문자열"
}""".strip()


OBJECT_RESOLVE_PROMPT = """
You are a database object resolver.
Choose the single best table candidate for the user's request from the provided candidates only.
Return JSON only. Do not include markdown or reasoning text.

Input JSON:
{
  "request": "user request text",
  "candidates": [
    {
      "schema": "dbgame",
      "table": "friend",
      "ref": "dbgame.friend",
      "summary": "short summary",
      "weight": 7
    }
  ]
}

Output JSON:
{
  "selected_ref": "schema.table or table or empty",
  "confidence": 0.0-1.0,
  "needs_metadata": true|false,
  "reason": "short Korean reason"
}

Rules:
- Never invent objects that are not in candidates.
- Prefer semantically relevant objects over generic account/profile tables unless the request explicitly targets them.
- If candidates exist, choose the best candidate instead of returning empty whenever possible.
- Use `needs_metadata=true` only when all candidates are clearly unrelated to the request.
""".strip()


OBJECT_SQL_COMPOSE_PROMPT = """
You are a MySQL SQL composer.
Generate one executable SELECT SQL that best answers the request using the selected object context.
Return JSON only. Do not include markdown or reasoning text.

Input JSON:
{
  "request": "user request text",
  "selected_object": {
    "schema": "dbgame",
    "table": "friend",
    "summary": "short summary",
    "columns": [{"name": "AccountId", "type": "bigint"}]
  }
}

Output JSON:
{
  "sql": "SELECT ...",
  "intent": "short Korean intent",
  "confidence": 0.0-1.0,
  "needs_metadata": true|false
}

Rules:
- SQL must be valid MySQL SELECT only (no DDL/DML).
- Prefer selected_object as primary source.
- If confidence is low, still return a safe exploratory SELECT using selected_object (do not ask question).
- Do not output metadata-only SQL unless request is explicitly about metadata.
- For analytics/statistics requests, avoid a single `COUNT(*)` total-only query when a meaningful breakdown is possible.
- Prefer one actionable aggregation (e.g., by event/item/type/time bucket) with `ORDER BY` and sensible `LIMIT`.
""".strip()


OBJECT_SQL_GROUNDING_REVIEW_PROMPT = """
You are a SQL grounding reviewer.
Given user request + selected object context + generated SQL, determine whether SQL is grounded and relevant.
Return JSON only. Do not include markdown or reasoning text.

Input JSON:
{
  "request": "user request text",
  "intent": "short intent",
  "selected_object": {
    "schema": "dbgame",
    "table": "friend",
    "columns": [{"name": "CID", "type": "bigint"}]
  },
  "sql": "SELECT ..."
}

Output JSON:
{
  "ok": true|false,
  "confidence": 0.0-1.0,
  "reason": "short Korean reason",
  "fixed_sql": "SELECT ... or empty"
}

Rules:
- Validate semantic alignment with request first.
- SQL must stay MySQL SELECT only.
- Prefer using selected_object as primary source; unrelated object jump is not allowed.
- Do not use columns that are not present in provided selected_object columns for the selected_object table alias.
- If current SQL is invalid or semantically off-target, provide `fixed_sql` when possible.
- If impossible to repair safely, set `ok=false` and leave `fixed_sql` empty.
""".strip()


KNOWLEDGE_SQL_COMPOSE_PROMPT = """
You are a MySQL SQL composer using retrieved knowledge evidence.
Generate one executable SELECT SQL to answer the user request.
Return JSON only. Do not include markdown or reasoning text.

Input JSON:
{
  "request": "user request text",
  "objects": [
    {"schema": "dbgame", "table": "friend", "ref": "dbgame.friend", "summary": "...", "weight": 7}
  ],
  "documents": [
    {"key": "table_insight:dbgame.friend", "text": "...", "weight": 6}
  ]
}

Output JSON:
{
  "sql": "SELECT ...",
  "intent": "short Korean intent",
  "confidence": 0.0-1.0,
  "selected_refs": ["schema.table"],
  "needs_metadata": true|false,
  "reason": "short Korean reason"
}

Rules:
- SQL must be MySQL SELECT only (no DDL/DML).
- If objects are provided, do not return generic ask-style output; choose the most relevant objects and produce SQL.
- Prefer semantically aligned objects; avoid unrelated generic account/profile tables unless the request explicitly targets them.
- Avoid metadata-only SQL (`information_schema`, `SHOW TABLES`) unless the request explicitly asks metadata.
- If uncertain, still return a best-effort analytical SELECT grounded in provided evidence.
""".strip()


KNOWLEDGE_SQL_FORCE_PROMPT = """
You are a MySQL SQL composer in fallback mode.
You must return one executable MySQL SELECT SQL grounded in provided evidence objects/documents.
Return JSON only.

Output JSON:
{
  "sql": "SELECT ...",
  "intent": "short Korean intent",
  "confidence": 0.0-1.0,
  "selected_refs": ["schema.table"],
  "needs_metadata": false,
  "reason": "short Korean reason"
}

Rules:
- Do not ask questions and do not return empty SQL.
- Use only provided objects as base tables.
- Multi-table join is allowed when request requires relation/leaderboard/ranking.
- Prefer meaningful analytical result over metadata listing.
- SQL must be SELECT only.
- If exact metric is ambiguous, choose the closest defensible interpretation and still return SQL.
""".strip()


def llm_plan(
    nl: str,
    summary: str | None,
    rows,
    kv: dict[str, str],
    step_trace: list[dict[str, Any]] | None = None,
    mcp_tools: list[str] | None = None,
    schema_meta: dict[str, Any] | None = None,
    force_stepwise: bool | None = None,
    knowledge: dict[str, Any] | None = None,
    timeout_sec: int | None = None,
) -> dict[str, Any] | None:
    client = _get_llm_client(timeout_sec=timeout_sec)
    if client is None:
        return None

    memory_context = {
        "summary": summary or "",
        "recent": [
            {
                "role": role,
                "content": content,
                "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
            }
            for role, content, created_at in rows[-AGENT_MEMORY_MAX_TURNS:]
        ],
        "kv": _filter_kv_for_context(kv, request=nl),
    }

    stepwise_flag = _detect_stepwise_request(nl) if force_stepwise is None else bool(force_stepwise)
    origin_request = str((kv or {}).get("origin_request", "")).strip()
    if stepwise_flag:
        origin_request = nl.strip()
    compact_schema_meta = _compact_schema_meta_for_request(schema_meta or {}, nl, kv)
    thread_goal = str((kv or {}).get("thread_goal", "")).strip()
    user_payload = {
        "request": nl,
        "origin_request": origin_request,
        "thread_goal": thread_goal,
        "context": memory_context,
        "knowledge": knowledge or {},
        "step_trace": step_trace or [],
        "force_stepwise": stepwise_flag,
        "top_n": AGENT_TOP_N,
        "mcp_tools": mcp_tools or [],
        "local_tools": sorted(list(LOCAL_TOOLS)),
        "schema_meta": compact_schema_meta,
    }

    _plan_model = AGENT_PLAN_MODEL or OPENAI_MODEL
    resp = _openai_chat_completion_with_deadline(
        client,
        _plan_model,
        [
            {"role": "system", "content": SYSTEM_PROMPT_MCP if AGENT_MODE == "mcp" else SYSTEM_PROMPT_SQL},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        timeout_sec=timeout_sec,
        task="agent",
    )
    if resp is None:
        _log_llm_warn("llm_plan", "no_response", f"model={_plan_model}")
        return None
    try:
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        _log_llm_warn("llm_plan", "parse_error", str(exc))
        return None

    result = _extract_json_object(text)
    if result is None and text:
        _log_llm_warn("llm_plan", "json_extract_failed", f"model={_plan_model} len={len(text)} head={text[:200]}")
    return result


def _has_insight_objects(knowledge: dict[str, Any] | None) -> bool:
    if not isinstance(knowledge, dict):
        return False
    items = knowledge.get("insight_objects")
    return isinstance(items, list) and any(isinstance(item, dict) for item in items)


def _is_search_objects_step(plan: dict[str, Any] | None) -> bool:
    if not isinstance(plan, dict):
        return False
    if str(plan.get("action", "")).strip().lower() != "step":
        return False
    tool = str(plan.get("tool", "")).strip()
    return tool in MCP_SEARCH_OBJECTS_CANDIDATES


def llm_validate_step(payload: dict[str, Any]) -> dict[str, Any] | None:
    _validation_model = AGENT_STEP_GRADE_MODEL or AGENT_SUMMARY_MODEL or OPENAI_MODEL
    client = _get_llm_client(model=_validation_model)  # TASK-0135 (#3): 티어 라우팅
    if client is None:
        return None

    try:
        resp = client.chat.completions.create(
            model=_validation_model,
            messages=[
                {"role": "system", "content": VALIDATION_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            **_max_tokens_kwargs(_validation_model, "validate"),
            **_temperature_kwargs(_validation_model),
            timeout=_openai_request_timeout(AGENT_TIMEOUT_SEC),
        )
        _record_llm_usage(_validation_model, "validate", resp)  # TASK-0136 (#11)
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        _log_llm_warn("llm_validate_step", "exception", str(exc))
        return None

    return _extract_json_object(text)


def llm_update_summary(payload: dict[str, Any]) -> str | None:
    _summary_model = AGENT_SUMMARY_MODEL or OPENAI_MODEL
    client = _get_llm_client(model=_summary_model)  # TASK-0135 (#3): 티어 라우팅
    if client is None:
        return None

    try:
        resp = client.chat.completions.create(
            model=_summary_model,
            messages=[
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            **_max_tokens_kwargs(_summary_model, "summary"),
            **_temperature_kwargs(_summary_model),
            timeout=_openai_request_timeout(AGENT_TIMEOUT_SEC),
        )
        _record_llm_usage(_summary_model, "summary", resp)  # TASK-0136 (#11)
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        _log_llm_warn("llm_update_summary", "exception", str(exc))
        return None

    obj = _extract_json_object(text)
    if isinstance(obj, dict):
        summary = str(obj.get("summary", "")).strip()
        if summary:
            return summary
    return text or None


ORIGIN_SHIFT_CLASSIFY_PROMPT = """
You are a conversation continuity classifier for a database assistant.

Given the original user request (origin) and the latest user message (current),
classify whether the current message represents:
- "shift": A genuinely NEW topic or question that is UNRELATED to the origin.
- "evolve": The user stays within the SAME domain/data but explicitly changes,
  expands, or replaces the analytical GOAL. The prior investigation context
  (tables found, schemas discovered) is still relevant.
- "continue": A refinement, correction, scope change, or procedural directive
  that still serves the SAME goal as the origin.

Classification rules for "continue":
- Scope changes: changing which DB, schema, or table to search does not change
  the goal.
- Corrections: rejecting a table as wrong, pointing out data type mismatches,
  saying "that's not user data" — these redirect the same investigation.
- References to earlier context: "using that structure", "the original question",
  "the first request", "aggregate the initial stats".
- Short procedural directives: "aggregate across all DBs", "find a matching
  table", "proceed with statistics".

Classification rules for "evolve":
- The user explicitly abandons or replaces the current goal while staying in
  the same data domain: "not that — analyze revenue trends instead",
  "also analyze payment patterns for those users".
- The user expands the goal to cover more than the original scope:
  "not just limited gacha, show stats for ALL gacha systems".
- The user adds a secondary analysis goal on top of the original:
  "additionally, analyze the purchase patterns of those users".
- Key signal: the DOMAIN stays the same but the QUESTION changes.

Classification rules for "shift":
- A genuine shift requires a NEW domain, NEW entity, or NEW analytical goal
  with NO reference to the prior conversation thread.
- Completely unrelated questions about different systems or metrics.

When uncertain between "evolve" and "continue", default to "continue".
When uncertain between "evolve" and "shift", default to "evolve".

Return JSON only:
{"classification": "shift"|"evolve"|"continue", "reason": "brief reason"}
""".strip()


def llm_classify_origin_shift(origin: str, current: str) -> str:
    """LLM을 사용하여 주제 전환 여부를 판별한다. 'shift', 'evolve', 또는 'continue' 반환."""
    _classify_timeout = 30
    _classify_model = AGENT_TASK_CLASSIFY_MODEL or AGENT_PLAN_MODEL or OPENAI_MODEL
    client = _get_llm_client(timeout_sec=_classify_timeout, model=_classify_model)  # TASK-0135 (#3)
    if client is None:
        return "continue"
    payload = {"origin": origin[:500], "current": current[:500]}
    try:
        resp = client.chat.completions.create(
            model=_classify_model,
            messages=[
                {"role": "system", "content": ORIGIN_SHIFT_CLASSIFY_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            **_max_tokens_kwargs(_classify_model, "summary"),
            **_temperature_kwargs(_classify_model),
            timeout=_openai_request_timeout(_classify_timeout),
        )
        _record_llm_usage(_classify_model, "classify", resp)  # TASK-0136 (#11)
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        _log_llm_warn("llm_classify_origin_shift", "exception", str(exc))
        return "continue"
    obj = _extract_json_object(text)
    if isinstance(obj, dict):
        classification = str(obj.get("classification", "")).strip().lower()
        reason = str(obj.get("reason", "")).strip()
        try:
            append_log_line(
                "origin_shift",
                json.dumps(
                    {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "origin": origin[:120],
                        "current": current[:120],
                        "classification": classification,
                        "reason": reason,
                    },
                    ensure_ascii=False,
                ),
            )
        except Exception:
            pass
        if classification in ("shift", "evolve", "continue"):
            return classification
    return "continue"


def llm_generate_topic(payload: dict[str, Any]) -> str | None:
    _topic_model = AGENT_TOPIC_MODEL or AGENT_SUMMARY_MODEL or OPENAI_MODEL
    client = _get_llm_client(model=_topic_model)  # TASK-0135 (#3): 티어 라우팅
    if client is None:
        return None

    try:
        resp = client.chat.completions.create(
            model=_topic_model,
            messages=[
                {"role": "system", "content": TOPIC_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            **_max_tokens_kwargs(_topic_model, "summary"),
            **_temperature_kwargs(_topic_model),
            timeout=_openai_request_timeout(AGENT_TIMEOUT_SEC),
        )
        _record_llm_usage(_topic_model, "topic", resp)  # TASK-0136 (#11)
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        _log_llm_warn("llm_generate_topic", "exception", str(exc))
        return None

    obj = _extract_json_object(text)
    if isinstance(obj, dict):
        topic = str(obj.get("topic", "")).strip()
        if topic:
            return topic
    return text or None


def llm_glossary_suggest(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """대화 한 턴(질문+답변)에서 용어사전 후보를 추론(용어사전 자율등록, 0021).

    payload: {"user_message": str, "assistant_answer": str}
    반환: [{"term": str, "definition": str, "confidence": float}, ...] (없으면 []).
    실패(클라이언트 없음/예외/JSON 파싱 실패)는 [] — 호출측(ask 경로) 차단 금지(soft-fail).
    """
    _model = AGENT_GLOSSARY_SUGGEST_MODEL or AGENT_SUMMARY_MODEL or OPENAI_MODEL
    client = _get_llm_client(model=_model)  # 티어 라우팅
    if client is None:
        return []
    try:
        resp = client.chat.completions.create(
            model=_model,
            messages=[
                {"role": "system", "content": GLOSSARY_SUGGEST_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            **_max_tokens_kwargs(_model, "summary"),
            **_temperature_kwargs(_model),
            timeout=_openai_request_timeout(AGENT_TIMEOUT_SEC),
        )
        _record_llm_usage(_model, "glossary_suggest", resp)
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        _log_llm_warn("llm_glossary_suggest", "exception", str(exc))
        return []
    obj = _extract_json_object(text)
    if not isinstance(obj, dict):
        return []
    raw = obj.get("terms")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term", "")).strip()
        definition = str(item.get("definition", "")).strip()
        if not term or not definition:
            continue
        try:
            conf = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        out.append({"term": term, "definition": definition,
                    "confidence": max(0.0, min(1.0, conf))})
    return out


def llm_fix_sql(payload: dict[str, Any]) -> str | None:
    _fix_model = AGENT_SQL_FIX_MODEL or OPENAI_MODEL
    client = _get_llm_client(model=_fix_model)  # TASK-0135 (#3): 티어 라우팅
    if client is None:
        return None

    try:
        resp = client.chat.completions.create(
            model=_fix_model,
            messages=[
                {"role": "system", "content": SQL_FIX_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            **_max_tokens_kwargs(_fix_model, "sql_fix"),
            **_temperature_kwargs(_fix_model),
            timeout=_openai_request_timeout(AGENT_TIMEOUT_SEC),
        )
        _record_llm_usage(_fix_model, "sql_fix", resp)  # TASK-0136 (#11)
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        _log_llm_warn("llm_fix_sql", "exception", str(exc))
        return None

    obj = _extract_json_object(text)
    if isinstance(obj, dict):
        sql = str(obj.get("sql", "")).strip()
        if sql:
            return sql
    return None


def llm_schema_insight(payload: dict[str, Any]) -> dict[str, Any] | None:
    # TASK-0135 (#3 fix): model 을 client 생성에 전달 — 직접 create 호출이 티어 라우터를
    # 우회해 edge 모델을 Bedrock 에 보내 400 폭증하던 버그(Task4 미커버 경로) 수정.
    _insight_model = AGENT_INSIGHT_MODEL or OPENAI_MODEL
    client = _get_llm_client(timeout_sec=AGENT_INSIGHT_TIMEOUT_SEC, model=_insight_model)
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=_insight_model,
            messages=[
                {"role": "system", "content": SCHEMA_INSIGHT_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            **_max_tokens_kwargs(_insight_model, "insight"),
            **_temperature_kwargs(_insight_model),
            timeout=_openai_request_timeout(AGENT_INSIGHT_TIMEOUT_SEC),
        )
        _record_llm_usage(_insight_model, "schema_insight", resp)  # TASK-0136 (#11)
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        _log_llm_warn("llm_schema_insight", "exception", str(exc))
        return None
    if not text:
        _log_llm_warn("llm_schema_insight", "empty_response", f"model={_insight_model}")
        return None
    obj = _extract_json_object(text)
    if not isinstance(obj, dict):
        _log_llm_warn(
            "llm_schema_insight",
            "json_extract_failed",
            f"model={_insight_model} len={len(text)} head={text[:200]}",
        )
        return None
    return obj


def llm_table_insight(payload: dict[str, Any]) -> dict[str, Any] | None:
    # TASK-0135 (#3 fix): model 을 client 생성에 전달 — 직접 create 호출이 티어 라우터를
    # 우회해 edge 모델을 Bedrock 에 보내 400 폭증하던 버그(Task4 미커버 경로) 수정.
    _insight_model = AGENT_INSIGHT_MODEL or OPENAI_MODEL
    client = _get_llm_client(timeout_sec=AGENT_INSIGHT_TIMEOUT_SEC, model=_insight_model)
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=_insight_model,
            messages=[
                {"role": "system", "content": TABLE_INSIGHT_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            **_max_tokens_kwargs(_insight_model, "insight"),
            **_temperature_kwargs(_insight_model),
            timeout=_openai_request_timeout(AGENT_INSIGHT_TIMEOUT_SEC),
        )
        _record_llm_usage(_insight_model, "table_insight", resp)  # TASK-0136 (#11)
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        _log_llm_warn("llm_table_insight", "exception", str(exc))
        return None
    if not text:
        _log_llm_warn("llm_table_insight", "empty_response", f"model={_insight_model}")
        return None
    obj = _extract_json_object(text)
    if not isinstance(obj, dict):
        _log_llm_warn(
            "llm_table_insight",
            "json_extract_failed",
            f"model={_insight_model} len={len(text)} head={text[:200]}",
        )
        return None
    return obj


def llm_account_insight(payload: dict[str, Any]) -> dict[str, Any] | None:
    """TASK-20260617T082131 (B′): 한 대화의 summary/kv 에서 PII-free 메타 인사이트를 1줄
    추출한다(계정 cross-conversation 회상 소스). schema/table insight 와 동일 티어 라우팅·
    예외 처리. 반환 dict `{"insight": "..."}` 또는 None(실패). PII 제거는 프롬프트가 강제하되
    호출측이 2차 마스킹을 적용한다(방어심층)."""
    _insight_model = AGENT_INSIGHT_MODEL or OPENAI_MODEL
    client = _get_llm_client(timeout_sec=AGENT_INSIGHT_TIMEOUT_SEC, model=_insight_model)
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=_insight_model,
            messages=[
                {"role": "system", "content": ACCOUNT_INSIGHT_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            **_max_tokens_kwargs(_insight_model, "insight"),
            **_temperature_kwargs(_insight_model),
            timeout=_openai_request_timeout(AGENT_INSIGHT_TIMEOUT_SEC),
        )
        _record_llm_usage(_insight_model, "account_insight", resp)
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        _log_llm_warn("llm_account_insight", "exception", str(exc))
        return None
    if not text:
        _log_llm_warn("llm_account_insight", "empty_response", f"model={_insight_model}")
        return None
    obj = _extract_json_object(text)
    if not isinstance(obj, dict):
        _log_llm_warn(
            "llm_account_insight",
            "json_extract_failed",
            f"model={_insight_model} len={len(text)} head={text[:200]}",
        )
        return None
    return obj


def llm_node_analysis(payload: dict[str, Any]) -> dict[str, Any] | None:
    """feature-0016 graphux5: 그래프 노드 1개 + 이웃을 능동 분석한다(재귀 워커가 노드마다 호출).

    schema/table insight 와 동일 max_tokens·예외·JSON 추출 경로를 쓰되, **모델은 전용
    AGENT_NODE_ANALYSIS_MODEL(기본 claude-haiku-4)** 로 라우팅한다 — 관리콘솔 그래프뷰의
    "각 관계 분석" 은 로컬 gemma(edge) 가 아니라 claude-haiku 로 작동해야 한다는 사용자 결정
    (2026-07-02, feature-0016 node-analysis-haiku). schema/table/account insight 는 여전히
    공유 AGENT_INSIGHT_MODEL 을 쓴다. 반환 dict `{"summary","relationships","usage","caveats"}`
    또는 None(실패). 호출측(node_analysis.py)이 None 을 status='failed' 로 기록하고 재귀는
    계속한다(1개 실패가 run 전체를 막지 않음)."""
    # 전용 모델(insight 공유값과 분리). 빈 문자열 방어 위해 or-체인으로 폴백 유지.
    _insight_model = AGENT_NODE_ANALYSIS_MODEL or AGENT_INSIGHT_MODEL or OPENAI_MODEL
    client = _get_llm_client(timeout_sec=AGENT_INSIGHT_TIMEOUT_SEC, model=_insight_model)
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=_insight_model,
            messages=[
                {"role": "system", "content": NODE_ANALYSIS_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            **_max_tokens_kwargs(_insight_model, "insight"),
            **_temperature_kwargs(_insight_model),
            timeout=_openai_request_timeout(AGENT_INSIGHT_TIMEOUT_SEC),
        )
        _record_llm_usage(_insight_model, "node_analysis", resp)
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        _log_llm_warn("llm_node_analysis", "exception", str(exc))
        return None
    if not text:
        _log_llm_warn("llm_node_analysis", "empty_response", f"model={_insight_model}")
        return None
    obj = _extract_json_object(text)
    if not isinstance(obj, dict):
        _log_llm_warn(
            "llm_node_analysis",
            "json_extract_failed",
            f"model={_insight_model} len={len(text)} head={text[:200]}",
        )
        return None
    return obj


def _build_summary_payload(
    summary: str | None,
    rows,
    kv: dict[str, str],
    last_step_summary: str | None,
) -> dict[str, Any]:
    limit = max(0, int(AGENT_SUMMARY_MAX_RECENT))
    recent_turns = rows[-limit:] if isinstance(rows, list) and limit else []
    recent = [
        {
            "role": role,
            "content": content,
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
        }
        for role, content, created_at in recent_turns
    ]
    return {
        "summary": summary or "",
        "origin_request": str((kv or {}).get("origin_request", "")).strip(),
        "thread_goal": str((kv or {}).get("thread_goal", "")).strip(),
        "topic": str((kv or {}).get("topic", "")).strip(),
        "last_step_summary": last_step_summary or "",
        "recent": recent,
    }


def _refresh_summary_after_step(
    conn,
    conversation_id: str,
    last_step_summary: str | None,
    step_index: int | None = None,
) -> None:
    if _near_run_deadline():
        return
    if not AGENT_SUMMARY_REFRESH:
        return
    if step_index is not None and AGENT_SUMMARY_REFRESH_EVERY > 1:
        if step_index % AGENT_SUMMARY_REFRESH_EVERY != 0:
            return
    start = time.perf_counter()
    summary, rows, kv = load_memory_context(conn, conversation_id, AGENT_MEMORY_MAX_TURNS)
    payload = _build_summary_payload(summary, rows, kv, last_step_summary)
    updated = llm_update_summary(payload)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    log_timing(
        "summary_refresh",
        {"conversation_id": conversation_id, "step_index": step_index or 0, "ms": round(elapsed_ms, 2)},
    )
    if updated:
        save_memory_summary(conn, conversation_id, updated)
    
    
def _refresh_summary_after_ask(conn, conversation_id: str, question: str) -> None:
    if not AGENT_SUMMARY_REFRESH:
        return
    question = sanitize_user_text(question or "")
    if not question:
        return
    summary_text = f"ask={question}"
    _record_step_summary(conn, conversation_id, summary_text)
    _refresh_summary_after_step(conn, conversation_id, summary_text, None)


def _generate_topic_from_request(text: str) -> str:
    payload = {"request": text}
    topic = llm_generate_topic(payload)
    if topic:
        return topic
    return _derive_topic(text)
