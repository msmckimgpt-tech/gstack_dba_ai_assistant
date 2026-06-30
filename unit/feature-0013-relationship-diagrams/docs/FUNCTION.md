---
doc_type: FUNCTION
feature_id: feature-0013-relationship-diagrams
status: draft
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary

사용자가 assistant 에게 "이 기능이 어떤 flow 로 동작하나", "이 테이블들이 어떻게 연결되나",
"구조 관계를 그려줘" 류 질문을 하면, assistant 가 **mermaid diagram** (ER diagram ·
flowchart) 으로 사용자 데이터소스(MySQL·MSSQL)의 구조 관계를 명시적으로 시각화해 답한다.
이를 위해 (a) 테이블 간 관계(FK·join path) 데이터를 KB 에 **확보**하고, (b) 웹 UI 가
```mermaid 블록을 SVG 로 **렌더**하며, (c) 대화·실행 인사이트로 관계 데이터를 **지속 학습**한다.

> grounding (AGENTS.md §10.5 / entry persona Phase 3.2): "assistant·학습·인사이트" 어휘는
> **제품 객체레이어**(사용자 DB 구조 지식) 를 가리킨다 — Claude Code 세션 메모리가 아니다.
> "특정 기능/구조" = 사용자의 데이터베이스 구조·데이터 흐름이다.

## 2. Goal
- REQ-20260629-relationship-diagrams: assistant 가 flow/관계 질문에 mermaid 다이어그램으로
  사용자 DB 구조 관계를 답하고, 그 관계 데이터를 확보·지속 학습한다.

## 3. In Scope

- **L1 렌더 (feature-0003-agent-web-ui):** mermaid.js vendor 로딩 + ```mermaid 코드블록을
  SVG 로 렌더하는 `enhanceMermaidBlocks()` / `renderMermaidDiagrams()` 후처리.
  DOMPurify 완화 없이 **sanitize 이후** 라이브 DOM 에서 mermaid `securityLevel:'strict'` 렌더.
- **L2 발화 (feature-0002-agent-core):** `_MERMAID_DIAGRAM_GUIDANCE` 시스템 프롬프트 주입 —
  flow/관계 질문 감지 시 ER/flowchart mermaid 발화. 기존 `get_foreign_keys`·`describe_table`
  툴로 관계 수집.
- **L3 데이터 확보 (feature-0002):** insight worker 가 `information_schema`
  (KEY_COLUMN_USAGE / REFERENTIAL_CONSTRAINTS, MSSQL sys.foreign_keys) 에서 FK edge 를
  정규화 수집해 `table_relationships` 저장소(신규 alembic migration)에 적재 +
  knowledge context 사전주입.
- **L4 지속 학습 (feature-0002):** 대화 중 실행된 JOIN SQL 에서 관계 evidence 를 추출해
  `table_relationships` 에 학습(`source='conversation'`). post-answer hook.

## 4. Out of Scope

- 다이어그램 편집/저장 UI (읽기 전용 렌더만).
- column lineage / 계산식 의존성(파생 컬럼) 학습.
- ERD export (PNG/SVG 다운로드) — 후속.
- 비-DBA 도메인(제품 자체 아키텍처) 다이어그램 — grounding 상 사용자 DB 한정.
- mermaid click/script 인터랙션(securityLevel:'strict' 로 비활성).

## 5. Inputs

- 사용자 자연어 질문 (flow/관계 의도).
- 데이터소스 `information_schema` / `sys.foreign_keys` (FK 메타).
- 대화 중 실행된 `execute_sql` 의 JOIN 절.
- 기존 KB: `rag_objects` (schema/table/column + `category_join_hints_json`).

## 6. Outputs

- assistant 답변 본문의 ```mermaid 블록 → 웹 UI 에서 SVG 다이어그램.
- KB `table_relationships` row (source_table·source_column → target_table·target_column,
  cardinality, source ∈ {fk_introspect, conversation, llm_insight}, confidence, scope_key).
- knowledge context 에 주입되는 관계 digest 텍스트(datamarked untrusted).

## 7. Main Flow

1. 사용자가 flow/관계 질문 전송 → `/api/ask` enqueue → ask-worker → agent loop.
2. agent loop 가 system prompt 에 `_MERMAID_DIAGRAM_GUIDANCE` + 관계 digest(L3) 주입.
3. assistant 가 필요 시 `get_foreign_keys`/`describe_table` 호출로 관계 보강.
4. assistant 가 텍스트 설명 + ```mermaid 블록 발화.
5. 웹 UI `markdownToHtml()` → marked → enhance(diff/attachment/**mermaid**) → DOMPurify →
   innerHTML → `renderMermaidDiagrams()` 가 `.mermaid` div 를 SVG 로 렌더.
6. (L4) 답변 저장 후 post-answer hook 이 실행된 JOIN 에서 관계 evidence 를
   `table_relationships` 에 upsert.
7. (L3) insight worker 가 주기적으로 FK introspection 으로 관계 저장소를 갱신.

## 8. Edge Cases

- mermaid 문법 오류 → 렌더 실패 시 원본 코드블록 표시(graceful fallback), 에러 콘솔만. mermaid v10
  `render()` 가 파싱 실패 시 `document.body` 에 남기는 임시 컨테이너(`#d<id>`, "Syntax error" bomb SVG
  포함)는 `renderMermaidDiagrams` 의 `.finally(removeMermaidRenderOrphan)` 가 제거한다 — bomb 이 화면에
  잔류하지 않고 코드블록 fallback 만 보이는 것이 불변식(CHG-0003 으로 복원, AC-1).
- 권한 부족으로 `information_schema` FK 조회 실패 → 해당 datasource 관계 수집 skip,
  telemetry 기록(기존 insight `db_failed_perm` 패턴 재사용).
- FK 미선언 스키마(관계가 application-level) → introspection 0건, L4 대화 학습이 보충.
- 대용량 다이어그램(수십 테이블) → assistant 가 질문 관련 서브그래프로 제한(프롬프트 지시).
- mermaid 텍스트에 사용자 데이터 유래 라벨 → `securityLevel:'strict'` 로 HTML escape.

## 9. Error Handling

- 렌더 실패: try/catch, 원본 코드블록 유지, 사용자에게 비차단(다이어그램만 누락).
- FK introspection 실패: insight cycle telemetry 에 사유 기록, 다음 cycle 재시도.
- migration 비파괴(신규 테이블 추가만) → 롤백은 `DROP TABLE table_relationships` (downgrade).

## 10. Dependencies

### 내부 기능 의존성
- feature-0002-agent-core: agent loop, KB, insight worker, tools(get_foreign_keys).
- feature-0003-agent-web-ui: markdown 렌더 파이프라인, vendor 로딩.

### 외부 의존성
- mermaid.js v10.9.3 (vendored, `static/vendor/mermaid.min.js`, UMD `window.mermaid`).
- Postgres agent_kb (alembic) — 관계 저장소.

### shared 모듈 의존성
- 없음 (feature-0011 추출 모듈은 간접 사용).

## 11. Acceptance Criteria
- AC-20260629T120000-relationship-diagrams-1: 웹 UI 에서 assistant 답변의 ```mermaid 블록이
  SVG 다이어그램으로 렌더된다 (raw 텍스트 아님). 렌더 실패 시 원본 코드블록으로 graceful fallback.
- AC-20260629T120000-relationship-diagrams-2: flow/관계 의도 질문에 assistant 가 텍스트 설명과
  함께 유효한 mermaid(ER 또는 flowchart) 블록을 발화한다 (프롬프트 가이던스 + 툴 활용).
- AC-20260629T120000-relationship-diagrams-3: insight worker 가 데이터소스 FK 를 introspect 해
  `table_relationships` 에 정규화 저장하고, knowledge context 에 관계 digest 가 주입된다.
- AC-20260629T120000-relationship-diagrams-4: 대화 중 실행된 JOIN 에서 관계 evidence 가
  추출되어 `table_relationships` 에 `source='conversation'` 으로 upsert 된다 (지속 학습).
- AC-20260629T120000-relationship-diagrams-5: DOMPurify 전역 완화 없이 렌더되고
  (securityLevel:'strict'), 신규 단위 테스트가 통과한다.

## 12. Observability
- insight cycle telemetry: `relationships_introspected`, `relationships_upserted`,
  `relationship_introspect_failed` (datasource별).
- post-answer 학습: `conversation_relationships_learned` 카운트 (run telemetry).
- 프런트: mermaid 렌더 실패 시 `console.warn` + `.mermaid-error` 클래스.

## 13. Pre-approved Changes
- DB 스키마 마이그레이션은 **비파괴적 추가만**(신규 `table_relationships` 테이블) 사전 승인됨.
- reachability_scope / release_notes_scope: 미선언(기본).
- deploy_scope: 전역 FIRST_REQUEST.md `deploy_scope: included` 적용 (cycle-final 후 web 재배포).
