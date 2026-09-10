"""외부 AI 도구 계약. 노출 정책은 명시적 allowlist, 인자는 core 정의가 정본이다."""
from __future__ import annotations

import copy
import json

RESTRICTED_TOOLS = {
    "get_sample_rows": "execute_sql의 제한된 SELECT를 사용한다. SQL 운영 스위치·행수 예산이 적용된다.",
    "check_table_coverage": "read_task_attachment로 SQL을 읽고 describe_schema 결과와 대조한다. 내부 첨부 실행 컨텍스트 전용이다.",
    "graph_navigate": "get_task_context(focus=...)로 제품 범위의 관계·KB를 조회한다. 전역 그래프 접근은 제공하지 않는다.",
    "read_attachment": "read_task_attachment(task_id, attachment_id, start_line, max_lines)를 사용한다.",
    "update_attachment": "최종 answer에 attachment-edit 블록(JSON 헤더의 source_attachment_id로 원본 지정)을 넣어 submit_answer로 제출한다. 서버가 저장하고 버전을 부여한다.",
    "scratch_import": "내부 첨부 분석용 상태 도구로 외부 표면에는 제공하지 않는다.",
    "scratch_sql": "내부 첨부 분석용 상태 도구로 외부 표면에는 제공하지 않는다.",
    "scratch_list": "내부 첨부 분석용 상태 도구로 외부 표면에는 제공하지 않는다.",
    "scratch_reset": "내부 첨부 분석용 상태 도구로 외부 표면에는 제공하지 않는다.",
}


def build_catalog(definitions, p0, p1, *, sql_enabled: bool) -> dict:
    definitions = {item["function"]["name"]: item["function"] for item in definitions}
    tools = []
    for name in sorted(p0 | p1):
        spec = definitions[name]
        parameters = copy.deepcopy(spec["parameters"])
        parameters.setdefault("properties", {}).setdefault(
            "datasource", {"type": "string", "description": "제품에 연결된 데이터소스 라벨(선택)"})
        tools.append({"name": name, "path": f"/api/ai/tools/{name}",
                      "enabled": name not in p1 or sql_enabled,
                      "description": spec["description"], "parameters": parameters})
    return {"version": 1, "tools": tools, "restricted": dict(RESTRICTED_TOOLS),
            "sql_policy": "단일 SELECT/CTE만 허용. DB_NAME() 등 서버 메타데이터 함수 차단 유지. "
                          "DB 위치는 search_tables/search_routines 결과의 database와 list_schemas(database=...)로 확인한다.",
            "attachment_policy": "웹 task 첨부 읽기는 read_task_attachment, 갱신은 최종 answer의 "
                                 "attachment-edit 블록(JSON 헤더: source_attachment_id), 신규는 attachment-new 블록(JSON 헤더: filename)으로 제출한다. "
                                 "파일 내용만 블록 안에 넣고 외곽 fence를 닫는다. 저장 전 파일 버전은 확정하지 않는다."}


def render_guidance(catalog: dict) -> str:
    lines = ["현재 연결의 외부 AI 도구 계약 (서버 제공 목록)",
             "다른 내부 에이전트 지침의 도구명 대신 아래 실제 제공 경로를 사용한다. "
             "구버전 러너의 짧은 도구 목록은 전체 목록이 아니다.",
             'POST JSON: {"task_id":"현재 task_id","reason":"조사 이유","arguments":{...}}. '
             '현재 서비스 연결 base와 BRIDGE_TOKEN을 사용하며 다른 주소·자격증명을 찾지 않는다.',
             "MCP에서는 run_read_tool(task_id, tool_name, arguments, reason)으로 같은 도구와 모든 인자를 전달할 수 있다."]
    for tool in catalog["tools"]:
        props = tool["parameters"].get("properties", {})
        required = set(tool["parameters"].get("required", []))
        args = ", ".join(k + ("(필수)" if k in required else "(선택)") for k in props)
        state = "사용 가능" if tool["enabled"] else "운영 설정으로 비활성"
        lines.append(f"- {tool['path']} [{state}]: {args}. {tool['description']}")
    lines += ["인자 JSON Schema와 활성 상태는 get_tool_catalog(task_id) 또는 get_task_context 응답의 tool_catalog에서 확인한다.",
              catalog["sql_policy"], catalog["attachment_policy"],
              "내부 전용 도구/대체 경로: " + json.dumps(catalog["restricted"], ensure_ascii=False)]
    return "\n".join(lines)
