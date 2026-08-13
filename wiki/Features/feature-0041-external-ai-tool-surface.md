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
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

> 외부 사용자의 AI 가 **자기 계정 LLM 으로 직접 추론**하면서 이 서비스의 데이터소스·RAG·
> 메타지식에 접근하도록, 내부 에이전트 도구를 인증·스코프·원장이 붙은 외부 표면으로 노출한다
> (LLM 비용은 호출자 부담, 서비스는 자격증명 무보관).

## 2. 상태

- **단계**: in-progress (P0 도구 9종 + OAuth AS + 전송 어댑터 2종 구현 완료 · HTTP/SSE 를 `ext-tool-mcp` 서비스로 **라이브 기동** + 엣지 `/api/ai/mcp` · 상한 4종 콘솔 전용 패널 · **URL 접속 인증**(discovery + 동의 화면 + `/ai/connect`) 완료 · 1차 `a68fbbac` / 2차 `e1372f32` / 3차 `89b7cd54`→`feadc089` / 인증 접근성 `5f20ee88` 라이브 배포 + POST-DEPLOY 전건 실측 완료)
- **마지막 갱신**: 2026-08-13
- **AI 작업자**: claude / feature-0041 cycle
- **잔여**: 사람 1회 브라우저 인가가 필요한 **전 구간 e2e 실행**(절차서 `docs/E2E_RUNBOOK.md` + 스크립트 완비 — 인가 지점이 "신원 = 우리 로그인 세션" 축의 생성점이라 설계상 자동화 불가 · 실행 후 TEST.md §3 Run 기록으로 AC-1 종결) · P1 이후 도구(`execute_sql` 등)는 사용자 결정(2026-08-12)에 따라 **운영 데이터를 보고 판단**(근거 = `tool_call_usage` 원장의 도구별 호출 분포·미제출률·한도 도달 빈도)이므로 원장 축적 대기. *해소됨*: 관리 콘솔 상한 노출(3차 출하에서 `runtime_settings` 그룹 `external_tool_surface` 슬라이스로 냈고 후속 cycle 이 **전용 패널로 분리** — PB-0008 이 '실행 타임아웃' 패널에 섞여 있던 오배치를 적발했다) · HTTP/SSE 라이브 기동 · 미로그인 인가 불가(`/login` 404). 역할별/계정별 override 는 미도입(전역 상한만).

## 3. 책임 경계

- **입력**: OAuth 인가(사람 브라우저 로그인·동의) · 도구 인자(`task_id`·식별자·`source_tasks`)
- **출력**: datamark 각인된 데이터 블록 · `tool_call_usage` 원장 · 대화 적재(원 질문·최종 답변)
- **side-effect**: 없음(읽기 전용 도구만 — 쓰기·첨부·scratch 계열은 영구 제외)

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
