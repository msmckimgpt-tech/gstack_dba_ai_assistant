---
doc_type: TASK
feature_id: feature-0013-relationship-diagrams
status: active
edit_policy: rewrite
source_of_truth: true
---

# Task

## 1. Current Status
- State: done (배포 완료 + 라이브 검증 PASS — PR #462 merged @ main 34cb31b)
- Owner: AI (claude) / Human (ms.mckim)
- Priority: high
- Last Updated: 2026-06-29

## 2. Implementation Plan

### 2.1 Plan

사용자 승인 범위: **전체 (Phase 1+2+3)** + **전용 worktree** (AskUserQuestion, 2026-06-29).

- **위험도:** Major
  - 다중 feature unit(0002+0003) + alembic migration + 프런트 보안 표면(mermaid 렌더).
  - 신규 테이블은 비파괴 추가(Minor) — FUNCTION.md §13 사전 승인.
  - 렌더 보안: DOMPurify 전역 완화 대신 sanitize-후-렌더 + `securityLevel:'strict'` 로
    XSS 표면 최소화 (scout 권고였던 전역 ALLOWED_TAGS 완화는 **불채택**).
  - 완료 검증: 웹/UI 변경 → AGENTS.md §10.5 / §15.4.1 — Windows 브라우저 게이트 대상
    (PB-0008). 본 cycle 에서는 unit 테스트 + 코드 검증까지, 실브라우저 렌더 검증은 TEST.md §3 기록.

#### Phase 1 — 렌더 + 발화 (end-to-end)

**1a. 웹 UI mermaid 렌더** (feature-0003-agent-web-ui)
- `src/static/vendor/mermaid.min.js` — mermaid v10.9.3 UMD vendored (window.mermaid). [완료]
- `src/static/index.html` — vendor `<script src>` 추가 (marked/purify 다음).
- `src/static/app.js`:
  - `enhanceMermaidBlocks(html)` 신규 — marked 가 만든 `<pre><code class="language-mermaid">`
    를 `<div class="mermaid" data-mermaid-src="...">SRC</div>` 로 치환(텍스트만, SVG 아님).
    `markdownToHtml()` 의 enhance 체인에 추가 (DOMPurify **이전**).
  - `renderMermaidDiagrams(rootEl)` 신규 — innerHTML 설정 **이후** 라이브 DOM 의 `.mermaid`
    노드를 `window.mermaid.run()` 으로 SVG 렌더. try/catch graceful fallback.
  - `renderMessageContent()` 에서 assistant 메시지 innerHTML 설정 직후 `renderMermaidDiagrams(el)` 호출.
  - 1회성 `mermaid.initialize({startOnLoad:false, securityLevel:'strict', theme:...})`.
- `src/static/styles.css` — `.mermaid` 중앙정렬·max-width 100%, `.mermaid-error` fallback.

**1b. assistant mermaid 발화** (feature-0002-agent-core)
- `src/agent_core.py`:
  - `_MERMAID_DIAGRAM_GUIDANCE` 상수 신규 — flow/관계 질문 시 ER/flowchart mermaid 발화 규칙,
    `get_foreign_keys`/`describe_table` 선조회 지시, "텍스트 설명 병행·질문 관련 서브그래프 한정·
    유효 문법" 가드.
  - 시스템 프롬프트 조립부(dialect guidance 주입 인근)에 `system_content += _MERMAID_DIAGRAM_GUIDANCE`.

#### Phase 2 — 관계 데이터 확보 (feature-0002-agent-core)

- alembic: `alembic/versions/20260629_00NN_table_relationships.py` — `table_relationships`
  신규 테이블 (scope_key, datasource_key, source_schema/table/column, target_schema/table/column,
  constraint_name, cardinality, source ∈ {fk_introspect,conversation,llm_insight}, confidence,
  source_run_id, created_at, updated_at; UNIQUE(scope_key, source_table_fqn, source_column,
  target_table_fqn, target_column)). 비파괴 추가. downgrade=DROP.
- `src/scripts/agent_kb_schema.sql` — 동일 DDL 반영(문서적 정합).
- `src/modules/kb_backend.py` (or 신규 `relationships.py`) — `upsert_table_relationship()`,
  `load_relationships_for_scope()` helper.
- `src/modules/dialects.py` — `introspect_foreign_keys(conn, schema)` (MySQL
  information_schema.KEY_COLUMN_USAGE + REFERENTIAL_CONSTRAINTS / MSSQL sys.foreign_keys) —
  기존 describe/FK 쿼리 재사용 가능 여부 확인 후 결정.
- `src/modules/insight.py` — `_scan_instance_schema_insights()` 흐름에 FK introspection 단계
  추가, telemetry(`relationships_introspected/upserted/failed`) 누적.
- `src/agent_core.py` `_build_knowledge_context()` — `_load_relationship_digest()` 신규,
  관계 digest 를 datamarked untrusted 로 주입.

#### Phase 3 — 지속 학습 (feature-0002-agent-core)
- `src/modules/kb_write.py` — `learn_relationships_from_sql(conn, scope_key, sql, run_id)` 신규 —
  실행된 SQL 의 JOIN 절 파싱 → (a.col = b.col) edge 추출 → `table_relationships`
  `source='conversation'`, confidence 낮게 upsert.
- `src/agent_core.py` — `execute_sql` 성공 직후(또는 post-answer, 답변 저장 인근)에서
  성공한 JOIN SQL 에 대해 `learn_relationships_from_sql()` 호출. telemetry
  `conversation_relationships_learned`.

<!-- PLAN-APPROVED via AskUserQuestion (scope=전체, worktree=전용) by ms.mckim on 2026-06-29 -->

## 3. Task Queue
- [x] TASK-20260629-rd-01 feature unit scaffold + FUNCTION/TASK/ANCHOR 작성
- [x] TASK-20260629-rd-02 mermaid v10.9.3 vendor
- [x] TASK-20260629-rd-03 (1a) 웹 UI mermaid 렌더 (index.html/app.js/styles.css)
- [x] TASK-20260629-rd-04 (1b) `_MERMAID_DIAGRAM_GUIDANCE` 프롬프트 주입
- [x] TASK-20260629-rd-05 (2) `table_relationships` migration + DDL + helper
- [x] TASK-20260629-rd-06 (2) dialect FK introspection + insight worker 통합
- [x] TASK-20260629-rd-07 (2) knowledge context 관계 digest 주입
- [x] TASK-20260629-rd-08 (3) 대화/JOIN 관계 학습 hook
- [x] TASK-20260629-rd-09 단위 테스트(19건 PASS) + §18.8 적대 패널(3 reviewer SHIP) + 문서 정리

## 4. In Progress
- 없음 (배포·검증 완료).

## 5. Blocked
- 없음

## 6. Done
- 3-phase 전체 구현(렌더·발화·데이터·학습) + 단위 테스트 19건 + §18.8 적대 패널(SHIP) + 문서/STATUS/wiki.
- main 머지(PR #462 — append형 충돌 해소: feature-0012+0013 양쪽 보존) + 배포(alembic 0020→0024 적용,
  web·ask-worker·insight-worker 재빌드·재기동, 전부 healthy).
- 라이브 검증: DB smoke(table_relationships 생성 + GRANT 발효, rw INSERT/DELETE 실측) · healthz ok ·
  **PB-0008 실 Windows Chrome mermaid erDiagram SVG 렌더 PASS**(artifacts/pb0008-feature-0013-mermaid-render.png).

## 7. Next Action
- (cycle 완료) 후속 비-blocking: app.js cache-buster bump(컨벤션 nit — ETag 재검증으로 기능 무영향) ·
  `/cso` 보안 리뷰(권장) · cardinality(1:N/M:N) 수집(후속 cycle).

## 8. Completion Checklist
- [x] 모든 REQ의 AC가 구현되었다 (AC-1~5 코드 반영 + 라이브 검증 완료 — PB-0008 렌더·DB·healthz PASS)
- [x] 단위 테스트(unit test)가 통과한다 (test_relationships.py 19건 PASS)
- [x] 전체/통합 테스트가 통과하거나, 미작성 사유와 커버 계획이 TEST.md §4에 기록되었다
- [x] FUNCTION.md가 현재 동작과 일치한다
- [x] MODIFY.md에 변경 이력이 기록되었다
- [x] REVIEW.md에 판단 근거가 기록되었다 (+ §18.8 AGENT-TEAM 패널 entry)
- [x] REPORT.md에 최종 상태가 반영되었다
- [x] TEST.md에 테스트 결과가 기록되었다 (웹 렌더 PB-0008 실 Windows 브라우저 검증 PASS — §10.5/§15.4.1)
- [x] BLOCKED 항목이 없거나 사람에게 전달되었다
- [x] STATUS.md에 기능 상태가 갱신되었다
- [x] LEARNINGS.md에 발견된 교훈이 기록되었다 (해당 없음 — alembic version drift/멱등·cache-buster nit 은 MODIFY/REVIEW 에 기록)
- [x] Git 커밋이 완료되었다 (c3487a6 feat + 99a66cf merge + 배포기록 docs)
- [x] Git 원격 동기화가 완료되었거나 보류 사유가 기록되었다 (PR #462 merged → main 34cb31b, 브랜치 정리)
