---
doc_type: ANCHOR
feature_id: feature-xxxx-template
created_at: YYYY-MM-DDTHH:MM:SSZ
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

# ANCHOR: <feature-id> <feature-name>

## §1. 외부 관점 요약
<!--
이 기능을 모르는 사람이 처음 코드를 열어봤을 때
"왜 이렇게 만들었지?" 또는 "이게 왜 필요하지?"라고 의문을 가질 법한 지점.
3~5줄.

예시:
"왜 이 계산을 클라이언트에서 하지? 서버에서 하면 안 되나?"
→ 이유: 실시간 UI 업데이트가 요구되고 서버 round-trip 레이턴시가 사용자 체감에
부정적. 계산 결과는 짧은 생명주기라 일관성 위험도 낮다.
-->

(작성 필요 — 3~5줄)

## §2. 대안 분기
<!--
선택하지 않은 옵션 2개 이상 + 각 옵션을 선택할 법한 페르소나.
"이 옵션 안 고른 이유"까지.

형식:
- **Alt-A: X 방식.** 페르소나: Y 성숙한 팀. 안 고른 이유: ...
- **Alt-B: Z 방식.** 페르소나: W 빠른 iteration 팀. 안 고른 이유: ...
-->

(작성 필요 — 최소 2개)

## §3. 가정된 사용 시나리오
<!--
실제 또는 상상된 end-user의 1개 구체 시나리오.
1인 프로젝트라도 "다른 동료가 이 기능을 인수인계 받았을 때" 또는
"6개월 후의 나 자신이 이 코드를 볼 때" 같은 가정 시나리오 허용.

금지: 개발자/AI/템플릿 내부 관점.
요구: 외부 또는 미래의 관점.
-->

(작성 필요 — 1개)

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
