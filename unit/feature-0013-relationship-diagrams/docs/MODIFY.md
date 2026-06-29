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

## CHG-20260629-relationship-diagrams-0002
- Date: 2026-06-29
- Related Requirement: REQ-20260629-relationship-diagrams (배포·라이브 검증)
- Summary: feature-0013 을 main 에 머지(PR #462) + 라이브 배포 + deploy-backed 검증. 코드 로직 무변경.
- Files (이번 변경):
  - `docs/STATUS.md`, `wiki/Features/_Index.md`, `wiki/Log.md` — main 머지 충돌 해소(append형:
    feature-0012 + feature-0013 양쪽 항목 보존). 코드 파일 변경 없음(c3487a6 산출물 그대로 배포).
- Deploy:
  - `make migrate`(alembic upgrade 0020→0024): 0021~0023 멱등 재실행(NOTICE skip, no-op) +
    0024 `table_relationships` 생성·INDEX·TRIGGER·GRANT. live current = `0024_table_relationships`.
  - web / ask-worker / insight-worker 이미지 재빌드(`compose build`) + recreate(`up -d`) — 전부 healthy.
- Live verify (deploy-backed):
  - DB smoke: `table_relationships` 존재 + GRANT(agent_kb_rw=INSERT/UPDATE/DELETE/SELECT,
    agent_kb_ro=SELECT) 발효 — agent_kb_rw 실 INSERT/DELETE 성공(DEPLOY TRAP 회피 확인).
  - healthz(caddy TLS): `status:ok`, mysql_ok/pg_ok=true, insight heartbeat fresh.
  - PB-0008(실 Windows Chrome 149): `markdownToHtml → renderMermaidDiagrams` 전체 경로로 erDiagram
    SVG 렌더 성공(viewBox·mermaid CSS, error fallback 없음). 증적 `artifacts/pb0008-feature-0013-mermaid-render.png`.
- Follow-up (비-blocking): `index.html` 의 app.js cache-buster 가 `?v=20260629b-feedback-id-space`
  (feedback 값) 그대로 — 컨벤션상 mermaid 버전으로 bump 권장. 단 app.js 가 `Cache-Control max-age`
  없이 content-ETag 로 서빙되어 재방문자도 ETag 재검증으로 새 app.js 를 수신(기능 무영향) → 별도 follow-up.
- Impact: 비파괴. Rollback: migration downgrade=DROP table_relationships; 이미지 직전 태그 롤백.
