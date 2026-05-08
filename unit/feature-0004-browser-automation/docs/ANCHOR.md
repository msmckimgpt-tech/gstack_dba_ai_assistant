---
doc_type: ANCHOR
feature_id: feature-0004-browser-automation
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

# ANCHOR: feature-0004-browser-automation

## §1. 외부 관점 요약

- **"왜 agent가 직접 브라우저를 돌리지 않고 HTTP API 원격 서비스인가?"**
  → Playwright는 Chromium 런타임을 포함하는 heavy 이미지(1GB+). agent 이미지와 분리하면
  agent 재배포가 browser 이미지 빌드 비용을 안 진다. 브라우저 세션 상태 보존 수명주기도
  agent와 달라 격리 필요.
- **"`ctl.py`가 왜 따로 있는가? agent가 직접 호출하면 되지 않나?"**
  → `ctl.py`는 사람이 수동 디버그/제어하는 CLI 경로. agent가 쓰는 HTTP API와는 별개
  interface. agent는 프로그램적 제어, 사람은 탐색적 제어.

## §2. 대안 분기

- **Alt-A: Playwright를 agent-core 이미지에 포함.** 페르소나: "서비스 수 최소화" 선호 팀.
  안 고른 이유: 이미지 크기 폭증 + 브라우저 crash 시 agent 동반 사망. 격리 경계가
  무너지면 전체 서비스 가용성이 브라우저 안정성에 의존하게 됨.
- **Alt-B: Selenium + Grid.** 페르소나: 기존 Selenium 인프라 보유 팀. 안 고른 이유:
  단일 호스트 수준에서 Selenium Grid는 over-engineering. Playwright는 dev/prod 동일
  API로 설치/운영 코스트가 낮다.

## §3. 가정된 사용 시나리오

- **"스크린샷 찍어서 파일로 저장" 요구를 받은 새 AI:** 자연스러운 첫 시도는
  "agent가 playwright 붙여서 쓰자". 이 ANCHOR §1을 읽으면 **HTTP API 우회가 필수**
  임을 이해하고, agent → HTTP → browser 서비스 경로를 유지한다. isolation 경계가
  지켜져야 browser crash가 agent를 죽이지 않는다.

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
