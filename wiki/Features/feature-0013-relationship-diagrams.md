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
maturity: minimal
ai_generated: true
feature_id: feature-0013-relationship-diagrams
linked_unit: unit/feature-0013-relationship-diagrams
created: 2026-06-29
sources:
  - ../../unit/feature-0013-relationship-diagrams/docs/FUNCTION.md
---

# Feature — 관계 다이어그램 (mermaid)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0013-relationship-diagrams/docs/FUNCTION|unit/feature-0013-relationship-diagrams/docs/FUNCTION.md]].

## 1. 한 줄 요약

assistant 가 "이 기능이 어떤 flow 로 동작하나 / 테이블 관계가 뭔가" 류 질문에 **mermaid 다이어그램**(ER·flowchart)으로 사용자 DB 구조를 답하고, 그 관계 데이터를 FK introspection + 대화 JOIN 학습으로 확보·지속 학습.

## 2. 상태

- **단계**: active / in-progress — 3-phase 코드+단위검증 완료 + 후속 mermaid render orphan/erDiagram "Syntax error" 봉인(rd-h2/h3) + **PB-0008 라이브 검증 PASS·배포 완료**(rd-h6, 2026-06-29).
- **마지막 갱신**: 2026-06-29
- **AI 작업자**: claude / Human (REQ-20260629-relationship-diagrams, 범위·worktree 사용자 승인 2026-06-29)

## 3. 책임 경계

- **입력**: 사용자 flow/관계 질문 · 데이터소스 FK 메타(information_schema/sys.foreign_keys) · 실행된 JOIN SQL.
- **출력**: 답변의 ```mermaid 블록(웹 SVG 렌더) · KB `table_relationships` edge(introspect/conversation) · knowledge context 관계 digest.
- **side-effect**: 신규 테이블 1개(비파괴) · 프런트 vendor mermaid.min.js. 모든 신규 경로 try/except + flag-gated + ds-scope 격리(기존 답변/insight 무회귀).

## 4. 관련 정본

- [[../../unit/feature-0013-relationship-diagrams/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0013-relationship-diagrams/docs/TASK|TASK.md]] — 작업 큐
- [[../../unit/feature-0013-relationship-diagrams/docs/REPORT|REPORT.md]] — 진행 요약
- [[../../unit/feature-0013-relationship-diagrams/docs/ANCHOR|ANCHOR.md]] — 방향성 stable reference

## 5. 관련 노트

- [[feature-0002-agent-core]] — 발화 가이던스·관계 저장소·insight introspection·대화 학습이 거주
- [[feature-0003-agent-web-ui]] — mermaid 렌더(marked→DOMPurify→sanitize-후 라이브DOM 렌더)
- [[../concepts/insight-worker]] — FK introspection 이 hook 되는 스키마 스캔
- [[../concepts/nl2sql-flywheel]] — 관계 grounding 으로 NL→SQL join 정확도 보강

## 6. Open questions / 미해결

- cardinality(1:1/1:N/M:N) 미수집 — FK 메타에서 후속 도출 가능.
- JOIN 파서는 best-effort(복잡 subquery/CTE 미해석) — confidence 0.4 + introspection 우선이라 영향 제한.
- 프런트 렌더 XSS 표면(securityLevel:'strict' 완화) — `/cso` 보안 리뷰 권장.

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0013-relationship-diagrams/docs/MODIFY.md` 에.

- 2026-06-29: 초안 작성 (feature 신규 생성 동반 — 3-phase 구현 반영).
- 2026-06-30 (doc_sync): 머지 reality 정합 — status stub→active·maturity stub→minimal, §2 상태에 mermaid Syntax error 봉인(rd-h2/h3)·PB-0008 라이브 PASS·배포 완료(rd-h6) 반영.
