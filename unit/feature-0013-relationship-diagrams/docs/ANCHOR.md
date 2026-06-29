---
doc_type: ANCHOR
feature_id: feature-0013-relationship-diagrams
created_at: 2026-06-29T12:00:00Z
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

# ANCHOR: feature-0013-relationship-diagrams 관계 다이어그램

## §1. 외부 관점 요약

"DBA assistant 가 왜 직접 mermaid 를 그리나? 사용자가 알아서 ERD 툴 쓰면 되지 않나?"
→ 이 제품의 사용자는 SQL/스키마에 익숙하지 않은 현업이 다수다. "주문 처리가 어떤
테이블들을 거치나"를 글로 설명하면 구조가 머리에 안 들어온다. 관계를 **그림으로** 즉답하면
이해 round-trip 이 사라진다. 외부 ERD 툴은 (a) 접속 권한·연결 설정이 또 필요하고 (b)
assistant 가 이미 가진 학습된 관계 지식(FK 미선언 application-level join 포함)을 못 쓴다.
"왜 관계를 별도 테이블에 저장하나? 매번 information_schema 조회하면?" → FK 미선언 DB 가
흔하고(관계가 코드에만 존재), 대화에서 드러난 join 을 누적 학습해야 introspection 만으로
못 얻는 관계까지 그릴 수 있기 때문. 그래서 `table_relationships` 가 introspection + 대화
학습의 단일 수렴점이다.

## §2. 대안 분기

- **Alt-A: 매 질문마다 live `information_schema` 조회만, 저장소 없음.** 페르소나: 최소 변경을
  선호하는 팀. 안 고른 이유: FK 미선언 관계를 영영 못 얻고, "지속 학습" 요구(요청 명시)를
  충족 못 함. 매 요청 introspection 비용도 반복.
- **Alt-B: mermaid 를 서버에서 SVG 로 렌더(headless).** 페르소나: CSP 가 매우 엄격한 팀.
  안 고른 이유: 무거운 런타임 의존(puppeteer/node) 추가, 기존 프런트 vendor 패턴(marked/purify)
  과 불일치. 클라이언트 mermaid + `securityLevel:'strict'` 로 XSS 표면을 통제 가능.
- **Alt-C: DOMPurify 전역 ALLOWED_TAGS 에 SVG 허용 후 marked 출력에 SVG 포함.** 페르소나:
  빠른 구현. 안 고른 이유: 모든 메시지의 sanitize 표면을 넓혀 XSS 위험 상시화. sanitize-후
  라이브 DOM 렌더로 격리하는 편이 표면이 좁다.

## §3. 가정된 사용 시나리오

마케팅팀 김대리는 "회원 등급 갱신이 우리 DB 에서 어떻게 흘러가요?"라고 묻는다. assistant 는
`members`, `member_grades`, `grade_change_logs`, `payments` 테이블과 그 FK·join 을 학습 지식과
introspection 으로 모아, 텍스트로 흐름을 설명하면서 ER/flowchart mermaid 를 함께 그린다. 김대리는
SQL 한 줄 안 보고도 "결제 → 등급변경 로그 → 회원 등급" 경로를 그림으로 이해한다. 6개월 뒤 신규
입사자도 같은 질문으로 도메인 구조를 즉시 파악한다.

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
