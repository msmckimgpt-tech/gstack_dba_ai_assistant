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

## CHG-20260629-relationship-diagrams-0003
- Date: 2026-06-29
- Related Requirement: REQ-20260629-relationship-diagrams (AC-…-1 graceful fallback 불변식 / AC-…-2 유효 mermaid)
- Summary: 라이브 대화("계정 연동 및 보상 일괄 수령 쿼리 구성", conv `20260629074613-356708b8`)에서
  mermaid "Syntax error in text" bomb 2개가 표면화된 버그 수정. 근본 원인 2가지를 실측(vendored
  mermaid 10.9.3 파서)으로 확정 후 수정 + 과거 대화 데이터 복구.
- Root Cause:
  1. (렌더/증상) mermaid v10 `render(id, src)` 가 컨테이너 인자 없이 호출되면 임시 컨테이너
     `<div id="d<id>">` 를 `document.body` 에 append 하는데, **파싱 실패 시 이를 제거하지 않아**
     bomb SVG 가 orphan 으로 잔류. `.catch → mermaidFallback` 의 graceful 코드블록 대체(FUNCTION.md
     §8 edge / AC-1)가 무력화됨. 렌더 패스 2회 → bomb 2개. (`suppressErrorRendering` 는 이 render()
     경로에 무효임을 jsdom 실측 확인.)
  2. (생성/유발) LLM 이 erDiagram 속성을 `{ }` 블록 밖 `Entity : type col PK` 로 나열 → strict
     파싱 실패(`Expecting ... BLOCK_START ... got ':'`). `_MERMAID_DIAGRAM_GUIDANCE` 에 erDiagram
     속성-블록 문법이 없었음. (해당 대화의 graph TD·sequenceDiagram·graph LR 3개 블록은 PASS.)
- Files (이번 변경):
  - `unit/feature-0003-agent-web-ui/src/static/mermaid-render.js` (cross-cut) — `renderMermaidDiagrams`
    에 `.finally(() => removeMermaidRenderOrphan(id))` 추가 + `removeMermaidRenderOrphan()` 신규
    (성공·실패 무관 `#d<id>` orphan 제거, idempotent). 폭탄 0, graceful 코드블록만 남도록 복원.
  - `unit/feature-0002-agent-core/src/agent_core.py` (cross-cut) — `_MERMAID_DIAGRAM_GUIDANCE` 의
    erDiagram 규칙을 `{ }` 속성-블록 문법 명시 + colon-attribute 금지 + 올바른 예시로 강화.
  - `unit/feature-0003-agent-web-ui/src/static/index.html`, `share.html` — mermaid-render.js
    cache-buster `?v=20260629-share-mermaid` → `?v=20260629-mermaid-orphan-fix` (CHG-0002 follow-up nit 해소).
  - `unit/feature-0013-relationship-diagrams/docs/{FUNCTION,REPORT,TASK,TEST,REVIEW}.md` 갱신.
- Data repair (런타임 PG, 사용자 명시 승인 — AskUserQuestion 2026-06-29 "A+B + 과거 대화 ER 복구"):
  - `agent_runtime.core_messages` id=4056 (conv `20260629074613-356708b8`) 의 erDiagram 블록 속성
    라인을 `{ }` 블록 문법으로 교체(관계 라벨·나머지 텍스트·graph/sequence 블록 무변경). 교체 후
    저장 내용의 mermaid 3블록 전부 파서 PASS 재확인. 원본 백업: scratchpad `msg_4056.orig.md`.
    Rollback: 백업 content 로 동일 UPDATE.
- Verification: jsdom + vendored mermaid 10.9.3 로 (a) 4개 라이브 블록 파싱(erDiagram만 FAIL 확정),
  (b) 패치된 mermaid-render.js end-to-end(깨진 블록 2패스 → bomb 0·orphan 0·graceful fallback 2),
  (c) 가이던스 예시 erDiagram·복구 erDiagram 파싱 PASS, (d) agent_core.py py_compile OK.
  실 브라우저 화면 검증은 배포 후 Windows-browser 게이트(PB-0008) 대상 — TEST.md §3.
- Impact: 비파괴(렌더 견고화 + 프롬프트 가이던스 + 데이터 1건 복구). Rollback: 코드 3파일 revert +
  cache-buster 원복 + 데이터 백업 복원.
