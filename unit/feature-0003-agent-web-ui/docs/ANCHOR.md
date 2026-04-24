---
doc_type: ANCHOR
feature_id: feature-0003-agent-web-ui
created_at: 2026-04-24T08:24:32Z
status: active
edit_policy: mixed
source_of_truth: true
---

<!--
ANCHOR.md — External Anchor Document (9번째 1급 문서)

이 문서는 기능의 "방향성 stable reference"다. AI-delegated 개발의 폐쇄 루프 문제를
방지하기 위해 외부 관점과 가정된 사용 맥락을 명시적으로 기록한다.

정책 요약 (AGENTS.md §17):
- §1~§3 (stable reference): rewrite 가능. 방향이 바뀌면 명시적으로 갱신한다.
- §4 (외부 검증 로그): append-only. source는 `human:<name>` 만 허용. AI는 §4 writer가 아님.
- Conflict Protocol: AI는 사용자 요청이 §1~§3와 충돌 시 작업을 시작하지 않고
  gstack skill(`/office-hours`, `/plan-ceo-review` 등) 재앵커를 유도한다.
- 24h bootstrap grace: `created_at` 기준 24시간 이내면 §1~§3이 빈칸이어도 verify 통과.
-->

# ANCHOR: feature-0003-agent-web-ui

## §1. 외부 관점 요약

- **"Web UI가 단순 프론트엔드인가?"**
  → 아니다. `src/app.py`에 HTTP API + 세션 관리 + System Prompt 조립
  (`compose_system_prompt`)까지 포함한다. "UI"라는 이름이 오해를 부르지만, 실제로는
  **Web entry point의 서버 측 로직 전부**. 정적 자산은 일부일 뿐.
- **"왜 System Prompt가 Web UI feature 안에 있는가? core에 있어야 하지 않나?"**
  → System Prompt의 **Product → Role → Account 3계층 조립**이 Web 세션 맥락
  (로그인한 account, 활성 product) 기반이다. core는 그 결과물을 주입받아 실행할 뿐.
  core가 Web DB에 역의존하는 layering 위반을 피하기 위해 Web UI feature에 둔다.

## §2. 대안 분기

- **Alt-A: System Prompt 조립을 agent-core로 이동.** 페르소나: "프롬프트는 agent의
  책임" 관점 팀. 안 고른 이유: account/role/product 데이터가 Web 세션에 있어 core가
  Web DB에 역의존하게 됨 → layering 위반.
- **Alt-B: static 자산만 분리 + API는 core에.** 페르소나: JAMstack / 정적 사이트 +
  CDN 팀. 안 고른 이유: `app.py`가 담당하는 HTTP routing + 세션 + 인증이 있어
  API/static 분리가 artificial. 현 규모에선 단일 서버로 충분.

## §3. 가정된 사용 시나리오

- **관리자가 특정 Role에게 새 Product 접근 권한을 부여하려 할 때:** 새 AI가
  `WebRoles` / `WebProductDatabases` / `WebProducts` / `WebAccountPermissionOverrides`
  테이블 관계를 모르면 whitelist가 엉뚱하게 풀린다. 이 ANCHOR §1의
  "System Prompt 3계층 조립" 설명이 빠른 onboarding 진입점 역할. REPORT.md의
  최신 변경 요약과 함께 읽으면 whitelist bypass 정책(metadata 4 스키마 항상 통과 +
  agent_memory 차단)의 **의도**를 이해할 수 있다.

## §4. 외부 검증 로그 (append-only)
<!--
완료 cycle마다 최소 1개 엔트리. source는 `human:<name>` 만 허용.
AI는 §4 writer 아님. AI는 작업 시작 시 Conflict Protocol에 따라
사용자에게 gstack skill 재앵커를 유도할 뿐, §4는 인간이 직접 append한다.

각 엔트리 필수 필드:
- source: human:<name>
- timestamp: ISO8601
- body: ≥ 200자 non-whitespace, 실제 내용
- challenge: 한 줄 — 이 검증이 무엇을 반박하거나 확인했는지

형식 예시:

### 2026-04-24T10:30:00Z — source: human:alice
**challenge:** 이 기능이 실제로 사용자 pain을 해결하는지 /office-hours로 재검증
**body:**
(여기에 200자 이상의 실제 검증 내용. gstack skill 실행 결과를 paste하거나
인간 리뷰어의 판단을 기록. 카고 컬트 방지를 위해 단순 "pass"/"looks good"은 FAIL.)
-->

(엔트리 없음 — TASK cycle 종료 전 최소 1개 필요)
