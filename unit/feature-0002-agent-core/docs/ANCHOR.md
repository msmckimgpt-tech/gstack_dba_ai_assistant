---
doc_type: ANCHOR
feature_id: feature-0002-agent-core
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

# ANCHOR: feature-0002-agent-core

## §1. 외부 관점 요약

- **"core와 web-ui가 분리됐는데, 왜 agent-core의 Dockerfile이 web-ui 코드까지 포함하나?"**
  → ADR-CORE-0001: import 구조 유지를 위해 agent 이미지는 core와 web-ui 코드를 함께
  포함한다. **소유권은 분리, 런타임 coupling은 감수**. 기능 간 종속성을 인정한 상태.
- **"왜 memory와 knowledge 모듈이 core 안에 있는가? 별도 feature 아닌가?"**
  → agent의 핵심 루프(요청 수신 → SQL 작성 → 실행 → memory 반영)가 불가분 단위.
  쪼개면 feature 경계마다 import/호출 비용이 늘어 이득을 초과한다. 단일 agent 내부
  책임 분리는 feature가 아닌 `modules/` 서브디렉토리 수준이 적절.

## §2. 대안 분기

- **Alt-A: memory / knowledge 별도 feature.** 페르소나: SOA / 마이크로서비스 지향 팀.
  안 고른 이유: 단일 agent 내부 책임 분리는 feature가 아닌 `modules/` 서브디렉토리
  수준이 적절. feature 경계까지 끌어올리면 import/호출 비용이 이득 초과.
- **Alt-B: core + web-ui 통합 단일 feature.** 페르소나: "Web UI = core의 face" 관점 팀.
  안 고른 이유: Web UI 변경 빈도 + 테스트 격리 요구로 소유권 분리 가치 있음. 런타임
  이미지 coupling은 감수하되 코드 소유권은 명확히 분리.

## §3. 가정된 사용 시나리오

- **insight-worker의 기존 복구 로직을 건드려야 할 때:** 새 AI 세션이 REPORT.md를 읽으면
  `fact/RAG/Text/Object 4종 완전성 확인 → 기존 fact 기반 복구 가능 시 즉시 복구 →
  복구 불가 시에만 LLM 재생성` 순서가 명시되어 있다. 이 순서를 뒤집으면 LLM 호출 비용이
  폭발한다. 새 AI가 **이 순서의 이유**를 이해한 뒤 손대야 한다.

## §4. 외부 검증 로그 (append-only)
<!-- 완료 cycle마다 최소 1개 엔트리 (release/milestone 또는 방향 전환 검증 시). source: human:<name>, timestamp: ISO8601, challenge: 한 줄, body: ≥ 200자. AI는 §4 writer 아님 — 인간이 직접 append (gstack skill 결과 paste 또는 리뷰어 판단 기록, 카고 컬트 방지). -->

(엔트리 없음 — 일반 TASK cycle 완료 조건은 아님; release/milestone 검토 또는 방향 전환 검증 시 사용)
