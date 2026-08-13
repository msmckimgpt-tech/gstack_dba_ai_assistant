---
doc_type: RUNBOOK
feature_id: feature-0041-external-ai-tool-surface
status: active
edit_policy: rewrite
source_of_truth: true
---

# 전 구간 e2e 절차서 — 사람 1회 수행

> **⚠ 2026-08-13 이후 이 스크립트는 "정상 사용 경로" 가 아니다.** 사용자는 이제
> **`https://<host>/api/ai/mcp` 를 클라이언트에 등록**하거나 **`https://<host>/ai/connect` 에
> 접속**하면 된다(표준 discovery + 동의 화면). 이 문서는 **개발자가 전 구간을 한 번에
> 회귀 검증**할 때의 절차로 남긴다 — 사용자에게 안내하는 방법이 아니다.
>
> 사용자 안내는 `/api/ai/guide` 부록 B.0-1 을 보라.
>
> ⚠ 스크립트의 ② 단계는 이제 **동의 화면**을 띄운다. 주소창의 `code=` 는 [허용] 을 누른
> **뒤에** 나타난다.

> **⚠ 2026-08-13 이후 이 스크립트는 "정상 사용 경로" 가 아니다.** 사용자는 이제
> **`https://<host>/api/ai/mcp` 를 클라이언트에 등록**하거나 **`https://<host>/ai/connect` 에
> 접속**하면 된다(표준 discovery + 동의 화면). 이 문서는 **개발자가 전 구간을 한 번에
> 회귀 검증**할 때의 절차로 남긴다 — 사용자에게 안내하는 방법이 아니다.
>
> 사용자 안내는 `/api/ai/guide` 부록 B 를 보라.

> **왜 사람이 필요한가**: 이 표면의 신원은 "우리 로그인 세션" 이다. 인가 단계에서 사람이
> 브라우저로 로그인·동의하는 것이 **설계상 유일한 신원 생성 지점**이고, 그걸 자동화하면
> 신원 축 자체가 사라진다. 그래서 이 한 단계만 사람이 하고 나머지는 스크립트가 한다.
>
> 소요: 2~3분. 라이브 데이터 변경: **읽기 전용 도구만 호출**하므로 조회 외 부작용 없음
> (남는 것은 `WebOAuthClients` 1행 · `WebAiTasks` 1행 · `tool_call_usage` 몇 행 — 전부 원장).

## 사전 준비

WSL 셸에서 아래 스크립트를 그대로 실행한다. 서비스 호스트는 `.env` 의 `WEB_PUBLIC_HOST` 다.

```bash
cd /root/download/docker/mysql_ai_delegated_dev/repo
bash unit/feature-0041-external-ai-tool-surface/scripts/e2e-authorize.sh
```

스크립트가 하는 일:

1. **client 등록**(DCR) — `POST /api/ai/oauth/register`
2. PKCE `code_verifier`/`code_challenge` 생성
3. **인가 URL 을 화면에 출력하고 대기** ← 여기서 사람이 개입
4. 사람이 붙여넣은 `code` 로 토큰 교환 → `open_task` → `get_task_context` →
   `describe_schema` → `submit_answer` 까지 자동 수행
5. 각 단계의 상태코드·핵심 응답을 표로 출력

## 사람이 하는 한 단계

스크립트가 인가 URL 을 출력하면:

1. **브라우저에서 그 URL 을 연다** (사내 계정으로 로그인돼 있어야 한다 — 아니면 로그인 화면이
   먼저 뜨고, 로그인 후 자동으로 돌아온다).
2. 리다이렉트된 주소창에서 `code=` 뒤의 값을 복사한다.
   - redirect_uri 는 `http://127.0.0.1:8765/cb` 이므로 **연결 실패 화면**이 뜨는 것이 정상이다.
     주소창의 `?code=...&state=...` 만 필요하다.
3. 스크립트 프롬프트에 붙여넣는다.

> ⚠ 인가 코드는 **60초 만료 · 1회용** 이다. 시간이 지났으면 스크립트를 다시 실행한다.

## 기대 결과

| 단계 | 기대 |
|---|---|
| register | `201` + `client_id` |
| authorize | 브라우저가 `?code=` 로 리다이렉트 |
| token | `200` + `access_token`(`mat_…`) · `refresh_token`(`mar_…`) |
| open_task | `200` + `task_id` |
| get_task_context | `200` + `⟦UNTRUSTED-DATA account=…⟧` 각인 포함 |
| describe_schema | `200` + 각인 포함 |
| submit_answer | `200` + `cross_session_findings: []` |
| refresh 회전 | `200` + **새** refresh token |
| 구 refresh 재사용 | `401` (계열 폐기 — 이게 확인되면 탈취 방어가 실제로 작동한다) |

전부 기대와 같으면 `docs/TEST.md §3` 에 Run 을 기록해 **AC-1 · TASK §9 G3** 를 닫는다.

## 실패 시 읽는 법

| 증상 | 원인 | 조치 |
|---|---|---|
| authorize 가 `/login` 으로 감 | 브라우저 세션 없음 | 먼저 사내 계정으로 로그인 |
| token 이 `invalid_grant` | 코드 만료(60s) 또는 재사용 | 스크립트 재실행 |
| open_task 가 `403` | 그 계정에 접근 가능한 제품이 없음 | 운영자에게 `product.access` 요청 |
| 도구가 `429` | 시간당 행수/바이트 상한 | 콘솔 `시스템 > 설정 > 외부 AI 도구` 에서 확인 |
| 도구가 `503` | 원장(PG) 기록 불가 | 설계상 의도된 fail-closed — PG 상태 확인 |

## 정리 (선택)

e2e 가 남긴 것은 전부 원장·등록 행이라 방치해도 무해하다(client_id 는 무권한). 정리하려면:

```sql
-- web 메모리 DB
UPDATE WebOAuthClients SET RevokedAt = NOW() WHERE ClientName = 'e2e-runbook';
```
