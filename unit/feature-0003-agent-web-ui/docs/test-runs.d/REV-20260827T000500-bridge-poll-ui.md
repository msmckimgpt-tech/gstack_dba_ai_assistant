---
run_at: 2026-08-27T10:30:00+09:00
session: ai/claude/feature-0043-external-llm-bridge
scope: feature-0043 브리지 대기/폴링 UI (static/app/composer.js) + POST-DEPLOY 도달성
verdict: PARTIAL — 도달성·기능 배선 실측 PASS / 화면 시각검증은 브리지 setup 불가로 미수행
---

# Run — feature-0043 브리지 POST-DEPLOY 검증

Environment: **Windows-browser 미수행 (브리지 setup 불가)** + 라이브 HTTP/컨테이너 실측 PASS

## Windows-browser 미수행 사유 (AGENTS.md §15.4.1 · PB-0008 사유 명시 조항)

`bin/win-browser.py` 브리지가 이 환경에서 성립하지 않는다.

```
$ python3 bin/win-browser.py doctor
ok: False
win_host: 8.8.8.8            ← WSL 이 Windows 호스트 IP 를 DNS 서버 주소로 오판
bridge_mode: None
issue: 동작 중인 CDP 브리지 없음 — Windows Chrome 미기동이거나 WSL→Windows relay 미구성

$ python3 bin/win-browser.py launch --url https://mysql-ai.company.local/
{"ok": false, "error": "bridge_unreachable",
 "relay_attempt": "relay started (8.8.8.8:9223 -> 127.0.0.1:9222, no-admin)"}
```

무권한 userspace relay 자동 기동까지 시도했으나 CDP 도달에 실패했다. doctor 가 제시하는 해소책은
**(A) 관리자 PowerShell 의 `netsh portproxy`** 또는 **(B) `.wslconfig` mirrored + WSL 재시작**
둘 다 이 세션에서 수행할 수 없다(전자는 관리자 권한, 후자는 현 세션 종료).

카고컬트 방지 조항에 따라 **미수행을 미수행으로 기록**한다 — 통과시키지 않는다.

## 대신 실측한 것 (라이브 배포 `0b2b4435`)

시각검증이 보증하려던 것 중 **HTTP·런타임 층에서 확인 가능한 부분**은 전부 실측했다.

### 1. 게이트가 라이브에서 실제로 차단한다

```
$ docker compose exec ask-worker python3 -c "..."
[llm-gate] 서버 계정 LLM 호출 차단 caller=modules.llm._get_llm_client — feature-0043 전환…
server_llm_enabled(): False
  claude-haiku-4-chat: client=None
  claude-sonnet-4-chat: client=None
  claude-opus-5-chat: client=None
  claude-haiku-4-interactive: client=None
```

### 2. MCP 주 경로에 브리지 도구가 노출된다 (무설치 계약의 핵심)

```
$ docker compose exec ext-tool-mcp python3 -c "await mcp.list_tools()"
MCP 도구 12 종: ['claim_request', 'describe_schema', 'describe_table', 'execute_sql',
 'get_foreign_keys', 'get_table_indexes', 'get_task_context', 'list_open_requests',
 'list_schemas', 'open_task', 'search_tables', 'submit_answer']
브리지 도구 노출: True
```

### 3. 스키마 마이그레이션이 라이브에 적용됐다

`WebAiTasks`: `Origin` · `ClaimedBy` · `ClaimedAt` · `ClaimedClient` · `Delivered` 5개 컬럼 +
`IX_WebAiTasks_Bridge` 복합 인덱스 존재 확인 (online DDL, 무중단).

### 4. 신규 라우트 도달성 + 인증 경계

| 요청 | 응답 | 판정 |
|---|---|---|
| `GET /` (엣지) | 200 | 서비스 정상 |
| `GET /api/ai/mcp` (무토큰) | 401 | 익명 차단 유지 |
| `POST /api/ai/tools/list_open_requests` | 401 | **라우트 존재** + 인증 경계 (catch-all 404 아님 = 등록 순서 정합) |
| `POST /api/ai/tools/claim_request` | 401 | 동일 |
| `POST /api/ai/bridge_status` | 405 | 라우트 존재 (GET 전용) |
| `GET /api/ai/bridge_status` (무인증) | 401 | 웹 세션 인증 작동 |

## 여전히 미검증인 것 (정직 표기)

브라우저 화면 자체 — **대기 말풍선의 렌더**, **폴링에 의한 자동 갱신**, **답변이 같은 대화에
표시되는 시점**. 위 실측은 그 흐름의 **부품이 전부 제자리에 있음**을 보이지만, 사용자가 보는
화면이 의도대로 움직이는지는 보이지 않는다. 이 둘은 다른 주장이며 합치지 않는다.

해소 조건: 브리지 setup(관리자 PowerShell `netsh portproxy` 또는 `.wslconfig` mirrored + WSL
재시작) 후 `bin/win-browser.py launch` → 로그인 → 질문 전송 → 대기 말풍선 스크린샷 →
`claim_request`/`submit_answer` → 자동 갱신 확인 → 이 fragment 의 `verdict` 를 PASS 로 갱신.
