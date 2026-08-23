---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0041-external-ai-tool-surface
linked_unit: unit/feature-0041-external-ai-tool-surface
sources:
  - ../../unit/feature-0041-external-ai-tool-surface/docs/FUNCTION.md
---

# Feature — 외부 AI 도구 표면 (추론 주체 반전)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0041-external-ai-tool-surface/docs/FUNCTION|unit/feature-0041-external-ai-tool-surface/docs/FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [접속 방법 (사용자 관점)](#7-접속-방법-사용자-관점)
8. [변경 이력 (이 카드)](#8-변경-이력-이-카드)

## 1. 한 줄 요약

> 외부 사용자의 AI 가 **자기 계정 LLM 으로 직접 추론**하면서 이 서비스의 데이터소스·RAG·
> 메타지식에 접근하도록, 내부 에이전트 도구를 인증·스코프·원장이 붙은 외부 표면으로 노출한다
> (LLM 비용은 호출자 부담, 서비스는 자격증명 무보관).

## 2. 상태

- **단계**: in-progress (P0 도구 9종 + OAuth AS + 전송 어댑터 2종 구현 완료 · HTTP/SSE 를 `ext-tool-mcp` 서비스로 **라이브 기동** + 엣지 `/api/ai/mcp` · 상한 4종 콘솔 전용 패널 · **URL 접속 인증**(discovery + 동의 화면 + `/ai/connect`) 완료 · 1차 `a68fbbac` / 2차 `e1372f32` / 3차 `89b7cd54`→`feadc089` / 인증 접근성 `5f20ee88` 라이브 배포 + POST-DEPLOY 전건 실측 완료 · **2026-08-14 실사용 1·2차 제보 정합 5 cycle**: 제보 결함 5건 + 인가 완료 화면 `/ai/oauth/callback` · **P1 `execute_sql` 개방** + 단일 바인딩 스코프 격리 결함 수정 · **AC-7 외부 답변 보존·콘솔 3상태 열람 출하** · 엣지 401 호스트 정합 · 부하 게이트 코칭 정정 — 전건 라이브 배포·POST-DEPLOY 실측)
- **마지막 갱신**: 2026-08-14
- **AI 작업자**: claude / feature-0041 cycle
- **잔여**: 사람 1회 브라우저 인가가 필요한 **전 구간 e2e 실행**(절차서 `docs/E2E_RUNBOOK.md` + 스크립트 완비 — 인가 지점이 "신원 = 우리 로그인 세션" 축의 생성점이라 설계상 자동화 불가 · 실행 후 TEST.md §3 Run 기록으로 AC-1 종결)**뿐**이다. *해소됨(2026-08-14)*: **P1 `execute_sql`** — "원장 데이터를 보고 판단" 이 실사용 제보('FK 0건 스키마에서 관계 주장을 데이터로 검증할 수 없다')로 결론에 도달해 개방됐다(조회 전용·건당 행 상한·실제 행수 원장·CSV 미생성·운영자 스위치로 이 축만 차단 가능) · **AC-7(외부 AI 답변 보존·열람)** — 발견부터 출하까지 같은 날. *해소됨*: 관리 콘솔 상한 노출(3차 출하에서 `runtime_settings` 그룹 `external_tool_surface` 슬라이스로 냈고 후속 cycle 이 **전용 패널로 분리** — PB-0008 이 '실행 타임아웃' 패널에 섞여 있던 오배치를 적발했다) · HTTP/SSE 라이브 기동 · 미로그인 인가 불가(`/login` 404). 역할별/계정별 override 는 미도입(전역 상한만).

## 3. 책임 경계

- **입력**: OAuth 인가(사람 브라우저 로그인·동의) · 도구 인자(`task_id`·식별자·`source_tasks`)
- **출력**: datamark 각인된 데이터 블록 · `tool_call_usage` 원장 · 제출 답변 보존(`WebAiTasks` 전용 컬럼 — 원안의 `agent_runtime.messages` 적재는 그 테이블을 읽는 **47개 파일**이 전부 "외부 AI 대화를 어떻게 취급하는가"를 새로 답해야 해서 기각, ANCHOR §2.1 Alt-F)
- **side-effect**: 데이터 쓰기 없음(도구는 읽기 전용 — 첨부·scratch 계열은 영구 제외). 단 2026-08-14 부터 **외부 런타임이 쓴 답변 텍스트를 우리 저장소에 보존**하는 경로가 있으며, 저장 시점 `wrap_external_answer` 각인이 계약이다(각인 방향이 반대다 — 나가는 도구 결과는 `wrap_tool_output` 으로 *외부 AI 에게* '계정 X 전용 데이터'라 표시하고, 들어오는 답변은 *우리 LLM 에게* '통제 밖 런타임이 쓴 텍스트, 지시가 아니다'라 표시한다. 저장된 답변은 요약·검색 경로로 우리 컨텍스트에 되돌아올 수 있고 저장 시점에 각인하지 않으면 그 판단이 유실된다)

## 4. 관련 정본

- [[../../unit/feature-0041-external-ai-tool-surface/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0041-external-ai-tool-surface/docs/ANCHOR|ANCHOR.md]] — 방향성 정본 (왜 추론 주체를 반전하는가)
- [[../../unit/feature-0041-external-ai-tool-surface/docs/TASK|TASK.md]] — 구현 계획 (§2.1)
- [[../../unit/feature-0041-external-ai-tool-surface/docs/REVIEW|REVIEW.md]] — codex 적대 리뷰 결과

## 5. 관련 노트

- [[feature-0023-conversation-api-access|feature-0023]] — `ask` 축(우리 LLM 이 추론). 본 feature 와 병존·용도 구분
- [[../Architecture/Module-Map|Module Map]]
- [[../Decisions/_Index|Decisions MOC]] — ADR-0026(per-user 키 폐기)이 Alt-B 폐기 근거

## 6. Open questions / 미해결

- 외부 AI 가 세션 A 데이터를 기억한 채 세션 B 에 **서술로** 답하는 경로는 차단·탐지 불가
  (구조적 한계 — 각인·선언·대조는 "몰라서 섞임"만 제거)
- `submit_answer` 미호출은 강제 불가 (소프트 강제: 미제출률 노출 + 임계 초과 시 신규 task 제한)
- 답변 보존 도입(2026-08-14) **이전** 제출분과 롤링 배포 창의 구버전 replica 처리분은 본문이 없다 —
  고칠 수 없는 것을 가시화해 콘솔이 답변 칸을 3상태(본문 있음 / 미제출 / **보존 안 됨**)로 가른다

## 7. 접속 방법 (사용자 관점)

설치물이 없다. MCP 클라이언트에 **URL + access token** 만 등록한다:

- 엔드포인트: `https://<host>/api/ai/mcp` (streamable-http)
- 헤더: `Authorization: Bearer <access_token>` — 없으면 **엣지에서 401**(익명 연결 차단)
- 토큰 발급: **주소만 등록하면 클라이언트가 스스로 인증을 시작한다** — RFC 9728 (`/.well-known/oauth-protected-resource`) · RFC 8414(`/.well-known/oauth-authorization-server`) discovery 4경로 + 401 `WWW-Authenticate` 로 AS 를 알려주고, 사람은 로그인 후 **동의 화면에서 [허용]** 만 누른다(서명 consent token · 세션 결합 · nonce 단일 사용 — 동의 화면이 없으면 SameSite=Lax + GET 발급이 링크 클릭 탈취 경로가 된다). MCP discovery 를 지원하지 않는 클라이언트는 콘솔 발급 페이지 **`/ai/connect`** 에서 토큰을 직접 받는다(1회 노출·세션 수명·refresh 없음 — 발급 결과를 서버에 다시 묻지 않으므로 **다시 볼 수 없다**). 개발자 회귀용 스크립트 절차는 `docs/E2E_RUNBOOK.md` 로 격하됐다(사용자 안내 정본 = 가이드 최상단 "주소만 등록").

여러 계정을 **동시에** 다룰 때는 stdio 런처(`external_tool_mcp_server.py`)를 권한다 — 도구
이름에 라벨이 접미돼 호출자 AI 가 세션을 구분할 수 있다(L1). HTTP 전송에는 그 층이 없다.

## 8. 변경 이력 (이 카드)

- 2026-08-12: 초안 작성 (계획 cycle)
- 2026-08-13: 3차 출하 반영 — HTTP/SSE 전송 라이브 기동(`ext-tool-mcp` + 엣지 `/api/ai/mcp`) ·
  상한 4종 콘솔 노출 · e2e 절차서. §7 접속 방법 추가
- 2026-08-14 (doc_sync): 3차 출하 **후속 3 cycle** 반영 — `ext-tool-mcp` 라이브 기동 실패 3중 원인 수정(이미지 의존 · SDK 2.0 · TLS upstream) · 상한을 '실행 타임아웃' 패널에서 **전용 패널로 분리**(PB-0008 적발) · **인증 접근성**: 미로그인 `authorize` 404(= 문서가 "브라우저로 인가한다" 고 적은 그 경로가 실제로는 404 였다) 해소 + RFC 8414/9728 discovery 4경로 + 서명 consent token 동의 화면(세션 결합·nonce 1회 · 링크 클릭 탈취 경로 동반 차단) + 발급 페이지 `/ai/connect` + 복귀 대상 `safeNextTarget`(문자열 검사로는 `/\evil.com` 이 통과하는데 브라우저가 `\` 를 `/` 로 정규화하므로 **URL 해석 결과의 origin** 비교 = 오픈 리다이렉트 차단). 정적 자산 5종은 feature-0003 `src/static/` 에 거주(`ai-connect.{html,css,js}` · `oauth-consent.{html,js}` · `app/next-target.js`). §2 상태·잔여 정정 + §7 접속 방법 URL 방식으로 갱신. 정본 REPORT §3.2~§3.4 · TASK §5.1·§9 · 머지 `89b7cd54`·`34376206`·`feadc089`·`b63243d1`·`5f20ee88`·`86d89b60`·`2c59c183`.
- 2026-08-17 (doc_sync): **08-14 실사용 정합 5 cycle + 문서 역전 청산** 반영. ⓐ `ext-tool-edge-401-host` — 앱 401 은 `request.base_url` 을 따라 접속 호스트를 돌려주는데 **엣지 401 만 `WEB_PUBLIC_HOST` 로 고정**돼 있어, 공인 IP(`https://112.185.196.20/`)로 붙은 외부 사용자는 해석되지 않는 사내 이름을 따라가다 discovery 를 **시작조차** 못 했다. 엣지에서 `{host}` 를 되비추는 방법은 사이트 블록이 `:443` catch-all 이라 **검증 없는 반사**가 되므로 택하지 않고, 앱이 이미 TrustedHost 로 호스트를 검증하니 **익명 요청을 앱으로 위임**했다("익명은 web · 인증된 요청만 MCP" 격리는 불변). 격리 엣지+web 으로 Host 3종 실측 · 재현 함정 기록(격리 장비를 비표준 포트로 노출하면 Host 에 포트가 붙어 Caddy 사이트 매칭이 달라진다 → 컨테이너 네트워크 안 443 으로 볼 것). ⓑ `ext-tool-field-defects-oauth-callback` — 외부 세션 1차 제보 5건이 **전부 테스트가 있었는데도 통과했던** 형태(도구의 존재만 보고 계약을 보지 않음)였다: DCR 이 `Claude Code (mysql-ai)` 를 400 거절해 표준 MCP 클라이언트가 **자동 연결 자체 불가**(클라이언트가 거기서 죽어 브라우저 오픈까지 가지 못한다) → `client_name` 은 동의 화면 표시용이므로 allowlist 를 **denylist 로 반전**(외부 클라이언트가 보내는 값은 예측 대상이 아니라 관측 대상) · `describe_table`/`get_foreign_keys`/`get_table_indexes` 가 `table` 을 보내는데 백엔드는 `table_name`+`schema_name` 을 읽어 **어떤 인자로도 성공 불가** → 정본 `modules/tools.py` 대조 계약 테스트 부착 · `allowed_datasource_labels` 가 바인딩 2개 이상에서만 값을 반환해 대부분 제품에서 빈 목록 · grounding 이 라벨을 scope 로 넘기고 문자열 반환을 rows 로 착각해 예외를 bare except 가 삼킴 · 빈 번들을 '(관련 요약 없음)' 한 줄로만 반환해 정상/고장 구분 불가. 설계 보정: 클러스터 요약이 질문에 테이블 이름이 있을 때만 매칭되는데 외부 AI 는 탐색 **전에** 한 번 부르므로 구조적으로 빌 수밖에 없어 `focus` 인자로 탐색 후 재호출. 인가 완료 화면 `/ai/oauth/callback` 신설(사용자가 본 평문 페이지는 우리 것이 아니라 클라이언트가 손으로 만든 콜백이었다). POST-DEPLOY 실 클라이언트 3종(Claude Code (mysql-ai)·Cursor/1.0·VS Code [MCP]) DCR **201**(이전 400 — 자동 연결 차단의 직접 원인). ⓒ `ext-tool-execute-sql-scope` — P1 `execute_sql` 을 열었고 그 과정에서 **이 표면의 실행 스코프가 08-12 배포부터 잘못 세워져 있었음**을 발견했다: `scoped_execution` 이 다중 바인딩일 때만 라우터를 세우고 단일 바인딩이면 `None` 을 돌려주며 docstring 에 "호출측이 알아서" 라 적어 뒀는데, 라우터는 memory DB 연결을 그대로 넘겼고 allowlist 설정도 라우터 경로에만 있어 `list_schemas` 가 **다른 대화의 첨부 샌드박스**를 노출했다(대부분의 제품이 단일 바인딩이라 예외가 아니라 **기본 경로**였다). 계약을 docstring 으로 호출측에 미루면 지켜지지 않는다 → 스코프를 세우는 함수가 연결·allowlist·방언 전부를 책임지고 미바인딩 제품은 403 fail-closed. `execute_sql` 방어는 내부 경로 재사용(AST 가드·allowlist·무거운 쿼리 게이트·시간 cap)이고 외부가 추가로 지는 것 셋 — CSV **미생성** · **실제 행수** 원장 기록 · **건당 행 상한**. codex P1×3 중 가장 값진 것은 운영자 스위치가 **항상 무력화**되던 것(`get_int(key, default)` 가 TypeError → except 가 True 반환, 문자열만 보던 테스트가 통과시켰다) → fail-closed. ⓓ `ext-tool-answer-retention`(AC-7) — 발견부터 출하까지 같은 날. codex 2라운드 P1×2 중 하나가 **없는 권한 키로 게이트**(`admin.console.access`; `_account_has_permission` 은 미정의 키에 항상 False 라 관리자도 전역 조회를 못 받고 조용히 자기 것만 보며 화면엔 오류가 없다 — 이 저장소가 세 번 기록한 "존재하지 않는 방어" 의 거울상)였고, 다른 하나는 **ALTER 6건이 online DDL 절 없이** 나간 것(같은 파일 기존 ADD COLUMN 60건은 lint 가 diff-mode 라 grandfathered · `agent_memory` 는 replica 없는 단일 인스턴스라 silent COPY 는 곧 체감 중단). 후속 cycle 이 배포 후 화면에서 **목록은 '보존 안 됨' 인데 상세는 '답변이 제출되지 않았습니다'** 라고 말하는 불일치를 잡았다 — 단위 테스트가 목록과 상세를 **각각** 검사했을 뿐 "둘이 같은 말을 하는가"를 묻지 않아 로직이 전부 green 인 채 통과했다. ⓔ `ext-tool-load-gate-coaching` — 집계 전용 조언이 `if worst:` 안에만 있어 계획 사실을 주지 않는 엔진(MSSQL)에서는 일반론만 나갔고, 차단된 쿼리가 **이미 `COUNT(*)`** 였다. 외부 AI 는 그걸 받고 구간 2분할로 우회했는데 **총 스캔량은 동일** — 게이트가 부하를 못 줄이고 마찰만 만들었다. 집계 판정은 SQL 형태만 보므로 계획 사실이 필요 없어 `if worst` 밖으로 옮기고 "구간을 나눠 여러 번 돌리는 것은 총 스캔량을 줄이지 않습니다" + `approx_rows` 우선 안내를 덧붙였다(그들이 인용한 1,690,449 는 `list_schemas` 가 **이미 준** 값이었다). **차단 기준·denylist 무변경**. ⓕ `ext-tool-doc-reconcile`(6d79e60c) — 정본 REPORT 가 08-13 이후 갱신되지 않아 **보안 표면에 대해 사실과 반대**를 말하고 있던 것을 정정("신규 route 8개는 … 라이브에 배포되지 않았으므로 현재 도달면은 0" ← 실제로는 08-12 부터 라이브이고 08-14 에 `execute_sql` 까지 열렸다. 이 feature 는 "문서가 사실을 앞지른" 사례를 세 번 기록했는데 이번은 **역방향**이다). §2 상태·잔여 · §3 책임 경계(답변 보존 경로) · §6 갱신. 정본 REPORT §1 · 머지 `be7e5d00`·`35c60a3f`·`956ae5e1`·`25637d1c`·`6a858599`·`0fe3a7f1`·`6d79e60c`.
