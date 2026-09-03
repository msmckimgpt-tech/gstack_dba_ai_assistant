---
doc_type: ANCHOR
feature_id: feature-0046-native-client
created_at: 2026-09-03T14:00:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

<!--
ANCHOR.md — External Anchor Document (9번째 1급 문서)

이 문서는 기능의 "방향성 stable reference"다. AI-delegated 개발의 폐쇄 루프 문제를
방지하기 위해 외부 관점과 가정된 사용 맥락을 명시적으로 기록한다.

정책 요약 (AGENTS.md §18):
- §1~§3 (stable reference): rewrite 가능. 방향이 바뀌면 명시적으로 갱신한다.
- §4 (외부 검증 로그): append-only. source는 `human:<name>` 만 허용. AI는 §4 writer가 아님.
  일반 TASK cycle 완료 조건은 아니며, release/milestone 또는 방향 전환 검증 시 사용한다.
- Conflict Protocol: AI는 사용자 요청이 §1~§3와 충돌 시 작업을 시작하지 않고
  gstack skill(`/office-hours`, `/plan-ceo-review` 등) 재앵커를 유도한다. 충돌이
  명백하지 않고 검증 결과가 명료하면 §4 확인 요청 없이 진행한다.
- 24h bootstrap grace: `created_at` 기준 24시간 이내면 §1~§3이 빈칸이어도 verify 통과.
-->

# ANCHOR: feature-0046-native-client — Windows 네이티브 클라이언트

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

**「왜 파이썬 GUI 인가? 요즘 이런 걸 Electron/Tauri 로 만들지 않나?」**

→ 이 클라이언트가 감싸는 러너가 **이미 파이썬이고 서드파티 의존이 0**이다. tkinter 를 쓰면
부품이 하나(파이썬)로 끝나고, Tauri 를 쓰면 Rust 껍데기 + 파이썬 sidecar 두 런타임을 묶어야 한다.
SPIKE-02 는 실측 전이라 Tauri 를 권고했는데, 실측(Rust 없음 · Windows 파이썬 3.14 실재 ·
tkinter 동작)이 그 전제를 뒤집었다. 화면이 덜 예쁜 것은 **의도된 교환**이다 — 이 도구의 목적은
터미널을 없애는 것이지 시각적 완성도가 아니다.

**「왜 러너를 앱에 동봉하지 않고 매번 서버에서 받나?」**

→ 동봉하면 서버 배포와 클라이언트 배포가 갈려 「고쳤는데 그대로」가 재발한다. 이 저장소는 그
결함(P0-Z6, 4차 재발)을 이미 겪었다. 서버가 유일 출처이고 체크섬이 그것을 보증한다.

## §2. 대안 분기
<!--
선택하지 않은 옵션 2개 이상 + 각 옵션을 선택할 법한 페르소나.
"이 옵션 안 고른 이유"까지.

형식:
- **Alt-A: X 방식.** 페르소나: Y 성숙한 팀. 안 고른 이유: ...
- **Alt-B: Z 방식.** 페르소나: W 빠른 iteration 팀. 안 고른 이유: ...
-->

**이 기능이 없어지면 무엇이 되돌아오는가**: 사용자가 웹에서 명령 3줄을 복사해 터미널에
붙여넣는 경로. 그것이 「AI 연결이 가장 큰 걸림돌」의 정체였다(RESEARCH §9.1).

**이 기능이 건드리지 않는 것**: 서버 계약(`/api/ai/mcp` · `bridge_heartbeat` · 스킴)은 **무변경**.
러너 엔진도 무변경. 바뀌는 것은 «누가 설치를 수행하는가» 뿐이다.

**절대 하지 않는 것 (ROADMAP §0.1)**: 벤더 OAuth 토큰을 읽거나 저장하거나 중계하지 않는다.
로그인은 벤더 공식 명령의 **대행 실행**이다. 2026년에 Google 이 이 선을 넘은 도구의 유료
구독자 계정을 정지했다 — 이 제약은 취향이 아니라 사용자 계정의 안전이다.

## §3. 가정된 사용 시나리오
<!--
실제 또는 상상된 end-user의 1개 구체 시나리오.
1인 프로젝트라도 "다른 동료가 이 기능을 인수인계 받았을 때" 또는
"6개월 후의 나 자신이 이 코드를 볼 때" 같은 가정 시나리오 허용.

금지: 개발자/AI/템플릿 내부 관점.
요구: 외부 또는 미래의 관점.
-->

- **Windows 우선, macOS 는 범위 밖** (사용자 결정 2026-09-03). macOS 는 서명·공증 없이
  Gatekeeper 가 **차단**하므로 지원하려면 Apple Developer Program 이 선행이다.
- **미서명 배포** (사용자 결정 2026-09-03). 첫 실행에 SmartScreen 경고 2클릭이 뜬다.
  대상이 「경고를 무서워하는 사람」이라 이탈이 생길 수 있고, 그 크기는 ITEM-00 퍼널 계측이 잰다.
- **커버리지를 과장하지 않는다**: gemini 는 로그인 대행 명령이 미실측이라 「감지·안내」로
  강등하고 화면이 그 사실을 말한다.
- 방향이 바뀌는 신호: 서명을 사기로 결정 / macOS 를 범위에 넣기 / 러너를 앱에 동봉하기.
  셋 중 하나라도 발생하면 이 문서를 먼저 고친다.

## §4. 외부 검증 로그 (append-only)
<!--
release/milestone 검토 또는 방향 전환 검증이 필요할 때 엔트리를 남긴다.
source는 `human:<name>` 만 허용.
AI는 §4 writer 아님. AI는 작업 시작 시 Conflict Protocol에 따라
명백한 방향 충돌이 있을 때만 사용자에게 gstack skill 재앵커를 유도한다.
§4는 인간이 직접 append한다. 일반 TASK cycle에서 요청 의도와 검증 결과가
명료하면 §4 엔트리 없이 PASS다.

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

(엔트리 없음 — 일반 TASK cycle 완료 조건은 아님)
