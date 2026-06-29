---
doc_type: MODIFY
feature_id: feature-0013-relationship-diagrams
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260629-relationship-diagrams-0001
- Date: 2026-06-29
- Related Requirement: REQ-20260629-relationship-diagrams (AC-…-1~5)
- Summary: assistant 가 flow/관계 질문에 mermaid 다이어그램으로 답하도록 3-phase 구현 —
  (L1) 웹 UI mermaid 렌더, (L2) 발화 가이던스, (L3) FK 관계 저장소+introspection,
  (L4) 대화 JOIN 학습.
- Files:
  - **feature-0003 (렌더)**:
    - `unit/feature-0003-agent-web-ui/src/static/vendor/mermaid.min.js` (신규, v10.9.3 UMD vendored)
    - `unit/feature-0003-agent-web-ui/src/static/index.html` (mermaid `<script>` 추가)
    - `unit/feature-0003-agent-web-ui/src/static/app.js` (`enhanceMermaidBlocks`/`renderMermaidDiagrams`/
      `ensureMermaidInit`/`mermaidFallback` 추가, markdownToHtml 체인 + renderMessageContent 호출)
    - `unit/feature-0003-agent-web-ui/src/static/styles.css` (`.mermaid-block`/`.mermaid-rendered`/`.mermaid-error`)
  - **feature-0002 (발화·데이터·학습)**:
    - `unit/feature-0002-agent-core/src/agent_core.py` (`_MERMAID_DIAGRAM_GUIDANCE` 상수+주입,
      `_build_knowledge_context` 관계 digest 주입, execute_sql 성공 후 학습 hook)
    - `unit/feature-0002-agent-core/src/modules/relationships.py` (신규 — upsert/introspect/digest/JOIN 파서)
    - `unit/feature-0002-agent-core/src/modules/insight.py` (`_fk_raw_execute` + 스키마 구조변경 시 FK introspection hook)
    - `unit/feature-0002-agent-core/alembic/versions/20260629_0024_table_relationships.py` (신규 migration)
    - `unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql` (table_relationships DDL+GRANT 정합)
    - `unit/feature-0002-agent-core/tests/test_relationships.py` (신규 단위 테스트 17건)
  - **shared**:
    - `shared/config.py` (`AGENT_RELATIONSHIP_INTROSPECT_ENABLED`/`AGENT_RELATIONSHIP_LEARNING_ENABLED` 플래그)
- Impact: 비파괴. 신규 테이블 1개(table_relationships) + 신규 프런트 vendor(3.3MB) + 프롬프트 증분.
  기존 답변/insight/스키마 무회귀(모든 신규 경로 try/except + flag-gated + ds-scope 격리).
- Rollback Notes: migration downgrade=DROP TABLE table_relationships. 플래그 OFF
  (`AGENT_RELATIONSHIP_*_ENABLED=0`)로 런타임 비활성. 프런트는 vendor script + 4 함수 제거.
