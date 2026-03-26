import json
import os
import sys
from urllib.request import Request, urlopen

BASE = os.getenv("MCP_TEST_URL", "http://localhost:28000/mcp")
SCHEMA = os.getenv("MCP_TEST_SCHEMA", "").strip()
SESSION_ID = None
REQ_ID = 1
EXECUTE_SQL_TOOL_CANDIDATES = ("execute_sql", "query_sql")
SEARCH_OBJECTS_TOOL_CANDIDATES = ("search_objects", "list_objects", "describe_objects")


def rpc(method: str, params: dict | None = None, notify: bool = False):
    global SESSION_ID, REQ_ID
    body = {"jsonrpc": "2.0", "method": method}
    if not notify:
        body["id"] = REQ_ID
        REQ_ID += 1
    if params is not None:
        body["params"] = params
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if SESSION_ID:
        headers["Mcp-Session-Id"] = SESSION_ID
    req = Request(BASE, data=data, headers=headers)
    with urlopen(req, timeout=20) as resp:
        if not SESSION_ID:
            SESSION_ID = resp.headers.get("Mcp-Session-Id") or SESSION_ID
        if notify:
            return None
        raw = resp.read().decode("utf-8")
        content_type = (resp.headers.get("Content-Type") or "").lower()
        if "text/event-stream" in content_type or raw.startswith("event:"):
            data_lines = [line[len("data:") :].strip() for line in raw.splitlines() if line.startswith("data:")]
            if not data_lines:
                return {}
            payload = json.loads(data_lines[-1])
        else:
            payload = json.loads(raw)
        if isinstance(payload, dict) and "error" in payload:
            raise RuntimeError(payload["error"])
        return payload


def print_json(title: str, value):
    print(f"\n== {title} ==")
    print(json.dumps(value, ensure_ascii=False, indent=2))


def pick_execute_sql_tool(names: list[str]) -> str | None:
    for candidate in EXECUTE_SQL_TOOL_CANDIDATES:
        if candidate in names:
            return candidate
    for name in names:
        for candidate in EXECUTE_SQL_TOOL_CANDIDATES:
            if name.startswith(candidate):
                return name
    return None


def pick_search_objects_tool(names: list[str]) -> str | None:
    for candidate in SEARCH_OBJECTS_TOOL_CANDIDATES:
        if candidate in names:
            return candidate
    for name in names:
        for candidate in SEARCH_OBJECTS_TOOL_CANDIDATES:
            if name.startswith(candidate):
                return name
    return None


def call_execute_sql(tool_name: str, sql: str):
    attempts = (
        {"sql": sql},
        {"query": sql},
        {"statement": sql},
    )
    last_error = None
    for arguments in attempts:
        try:
            return rpc("tools/call", {"name": tool_name, "arguments": arguments})
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError("execute_sql 호출 인자를 구성하지 못했습니다.")


def main():
    init_res = rpc(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "mysql-ai-mcp-test", "version": "1.0"},
        },
    )
    print_json("initialize", init_res)
    rpc("notifications/initialized", {}, notify=True)

    tools = rpc("tools/list", {})
    print_json("tools/list", tools)

    names = []
    for t in (tools.get("result", {}).get("tools", []) if isinstance(tools, dict) else []):
        name = t.get("name")
        if name:
            names.append(name)

    execute_sql_tool = pick_execute_sql_tool(names)
    if execute_sql_tool:
        result = call_execute_sql(
            execute_sql_tool,
            "SELECT DATABASE() AS `current_db`, NOW() AS `current_time`, @@version AS `mysql_version`;",
        )
        print_json(f"{execute_sql_tool}(SELECT ...)", result)
    else:
        print("\n경고: execute_sql 계열 MCP 도구를 찾지 못했습니다.")

    search_tool = pick_search_objects_tool(names)
    if search_tool:
        search_args = {
            "object_type": "table",
            "detail_level": "summary",
            "limit": 20,
        }
        if SCHEMA:
            search_args["schema"] = SCHEMA
        print_json(
            f"{search_tool}(table, summary)",
            rpc(
                "tools/call",
                {
                    "name": search_tool,
                    "arguments": search_args,
                },
            ),
        )
    else:
        print("\n경고: search_objects 계열 MCP 도구를 찾지 못했습니다.")

    print("\nMCP 테스트가 완료되었습니다.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("TEST FAILED:", exc)
        sys.exit(1)
