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

## 4. Untested Areas
- alembic `0024_table_relationships` 실제 upgrade + GRANT 발효(agent_kb_rw/agent_kb_ro).
- insight worker FK introspection 실 datasource 동작 + `relationships_introspected` telemetry.
- PG upsert/read 경로(`upsert_relationship`/`load_relationship_context`) 실 DB 동작.
- 웹 ```mermaid 렌더(SVG·strict sanitize·fallback) — **Windows-browser(PB-0008) 화면 검증 필요**.
- MSSQL FK introspection(dialect `foreign_keys_outgoing` MSSQL 분기) 실연결.
