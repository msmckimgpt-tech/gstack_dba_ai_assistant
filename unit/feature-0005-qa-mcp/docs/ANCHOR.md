---
doc_type: ANCHOR
feature_id: feature-0005-qa-mcp
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

# ANCHOR: feature-0005-qa-mcp

## §1. 외부 관점 요약

- **"MCP와 QA는 왜 같은 feature인가? 관련 없어 보인다."**
  → **MCP 연결 검증 자체가 QA의 한 부분**이다. "MCP가 agent와 정상 통신하는지" 확인하는
  스크립트가 QA 시나리오의 building block. 분리하면 상호 의존하는 두 feature가 됨.
- **"왜 별도 feature인가? `tests/` 디렉토리에 넣으면 되지 않나?"**
  → 기능별 `tests/`는 해당 feature 자체 테스트이고, QA/MCP는 **cross-feature 통합 확인**
  성격이라 repo-level 성격에 가깝다. `unit/` 아래 feature로 둔 건 일관성 + 소유권 명확화.

## §2. 대안 분기

- **Alt-A: `tests/integration/` 아래로 이동.** 페르소나: "테스트는 코드와 가깝게"
  원칙 팀. 안 고른 이유: 8-doc governance 대상이 아니게 되어 변경 이력 추적이 약해짐.
- **Alt-B: MCP만 별도 feature + QA는 통합 테스트로.** 페르소나: MCP 인프라 운영이
  주력인 팀. 안 고른 이유: 현 규모에서 분리 이점이 오버헤드를 넘지 않음.

## §3. 가정된 사용 시나리오

- **"MCP 연결이 끊긴다"는 이슈를 받은 새 AI:** `src/mcp_tests.py`에 재현 가능한
  테스트가 있으니 먼저 그것부터 돌리고, MCP 서버가 살았는지(feature-0005), agent가
  MCP 설정을 제대로 읽는지(feature-0002) 층위별로 격리 진단. 이 feature가
  **"MCP 상태 1차 진단 도구"** 역할을 한다.

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
