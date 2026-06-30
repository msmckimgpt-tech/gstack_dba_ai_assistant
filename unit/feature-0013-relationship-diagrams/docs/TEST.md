---
doc_type: TEST
feature_id: feature-0013-relationship-diagrams
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- 검증: JOIN 관계 파서·관계 digest 빌더·FK row 추출·alias 해석(순수 로직, DB 무관).
- 제외(라이브 스택 필요): migration 적용·insight FK introspection 실동작·PG upsert/read·웹 mermaid 화면 렌더.

> **검증 환경 분류 (AGENTS.md §15.4)**: 웹/UI 화면 검증은 **`Windows-browser` 만 인정**(PB-0008).
> 본 cycle 은 `CLI`(pytest) 까지 수행. ```mermaid 렌더 화면 검증은 배포 후 Windows-browser 게이트 대상.

## 2. Test Cases

### TEST-20260629T120000-relationship-diagrams-1 (JOIN 파서)
- Purpose: 실행된 SQL 의 equi-join → 관계 edge 추출(alias 해석·중복 제거·self-join 제외).
- Preconditions: `modules.relationships` import.
- Steps: INNER JOIN / 다중 JOIN / comma WHERE-join / backtick·bracket 식별자 / self-join /
  주석 포함 / 함수비교 / no-join 입력에 `parse_join_relationships()` 호출.
- Expected Result: 각 케이스 기대 edge 수/내용 일치. self-join·함수비교·no-join 은 `[]`.

### TEST-20260629T120000-relationship-diagrams-2 (digest 빌더)
- Purpose: 관계 row → 프롬프트 digest 텍스트(질문 매칭 필터·출처 태그·cap·dedup).
- Steps: `build_relationship_digest(rows, msg)` 다양한 입력.
- Expected Result: introspect 출처는 무태그, conversation 은 `(conversation)`, 질문 미매칭 edge 제외, 빈 입력 `""`.

### TEST-20260629T120000-relationship-diagrams-3 (FK row 추출)
- Purpose: dialect FK 쿼리 결과(dict/tuple result-set) → edge dict, 5컬럼 미만 skip.
- Steps: `_rows_from_outgoing()` 에 dict·tuple shape 주입.
- Expected Result: MySQL 컬럼순(CONSTRAINT_NAME/COLUMN_NAME/REF_*) 정확 매핑, 불완전 row skip.

### TEST-20260629T120000-relationship-diagrams-4 (라이브 end-to-end, 미수행)
- Purpose: insight introspection + 대화 학습 → table_relationships → digest 주입 → mermaid 답변 → 웹 렌더.
- Preconditions: 배포(web 재빌드) + alembic 0024 적용 + 실 datasource.
- Steps: (배포 후) FK 있는 DB 연결 → "테이블 관계 그려줘" 질문 → 답변에 ```mermaid → 화면 SVG 확인.
- Expected Result: 텍스트 설명 + 렌더된 ER/flowchart. **Windows-browser 검증 필요.**

### TEST-20260629T083043-relationship-diagrams-5 (CHG-0003 mermaid 렌더 graceful fallback)
- Purpose: 깨진 mermaid(erDiagram colon-attribute)가 strict 파싱 실패해도 "Syntax error" bomb 이
  화면에 잔류하지 않고 graceful 코드블록만 보이는 불변식 검증(AC-1) + erDiagram 생성 가이던스가
  유효 문법을 산출하는지.
- Preconditions: jsdom + vendored `mermaid.min.js`(v10.9.3) 로 실제 파서/렌더 구동(DB·브라우저 무관).
- Steps:
  - (a) 라이브 대화 4 블록을 `mermaid.parse()` → erDiagram 만 FAIL(`Expecting BLOCK_START got ':'`) 확정.
  - (b) 패치된 `mermaid-render.js` 의 `renderMermaidDiagrams` 로 깨진 erDiagram 을 2패스 렌더 후
    `document.body` 의 orphan(`#dmmd-*`) / bomb SVG / `.mermaid-error` 코드블록 수 측정.
  - (c) 가이던스 예시 erDiagram + 복구된 stored erDiagram 을 `mermaid.parse()`.
- Expected Result: (a) erDiagram 외 PASS. (b) bomb 0 · orphan 0 · graceful 코드블록 2. (c) 둘 다 PASS.
- Result: PASS (2026-06-29, jsdom 실측 — Run 2026-06-29-002).

## 3. Test Run History

### Run 2026-06-29-001
- Date: 2026-06-29
- Environment: CLI
- Runner: AI
- Bridge: n/a
- Evidence: `PYTHONPATH=src:../.. python3 -m pytest -q tests/test_relationships.py`
- Result Summary: 17 passed. + 변경 py 전건 `py_compile` OK, `node --check` app.js·mermaid.min.js OK,
  ruff(신규 코드) clean, alembic single-head(0024).
- Pass/Fail: PASS (순수 로직 + 정적 검증 범위)
- Notes: 라이브 스택(DB/insight/브라우저) 미검증 — §4.

### Run 2026-06-29-002 (CHG-0003 mermaid 렌더 fallback)
- Date: 2026-06-29
- Environment: CLI (node 18 + jsdom + vendored mermaid 10.9.3 파서/렌더)
- Runner: AI
- Bridge: n/a
- Evidence: 라이브 4 블록 parse(erDiagram FAIL `got ':'`, 나머지 PASS) · 패치 `mermaid-render.js`
  e2e(깨진 erDiagram 2패스 → bomb 0 · orphan `dmmd-` 0 · graceful 코드블록 2) · 가이던스/복구
  erDiagram parse PASS · `agent_core.py` py_compile OK.
- Pass/Fail: PASS (파서/렌더 로직 범위 — TEST-…-5).
- Notes: 실 브라우저 화면 검증(PB-0008, bomb 미표시 + 복구 ER 렌더)은 배포 후 잔여(TASK rd-h6).

## 4. Untested Areas
- alembic `0024_table_relationships` 실제 upgrade + GRANT 발효(agent_kb_rw/agent_kb_ro).
- insight worker FK introspection 실 datasource 동작 + `relationships_introspected` telemetry.
- PG upsert/read 경로(`upsert_relationship`/`load_relationship_context`) 실 DB 동작.
- 웹 ```mermaid 렌더(SVG·strict sanitize·fallback) — **Windows-browser(PB-0008) 화면 검증 필요**.
- MSSQL FK introspection(dialect `foreign_keys_outgoing` MSSQL 분기) 실연결.
