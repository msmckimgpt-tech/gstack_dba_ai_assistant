---
doc_type: REPORT
feature_id: feature-0013-relationship-diagrams
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
assistant 가 flow/관계/구조 질문에 **mermaid 다이어그램**(ER·flowchart)으로 사용자 DB 구조를
답하는 기능. 관계 데이터는 `table_relationships` 에 (a) insight worker FK introspection 과
(b) 대화 중 실행된 JOIN 학습으로 확보되고, knowledge context 로 주입되어 다이어그램 정확도를 높인다.
코드 구현 + 단위 검증 완료. **라이브 스택 통합검증(migration apply·insight introspection·실 브라우저 렌더)
미수행** — §5 참조.

## 2. Progress
- Planned: (없음)
- In Progress: (없음 — 배포·라이브 검증 완료)
- Done:
  - L1 웹 UI mermaid 렌더(vendor v10.9.3 + sanitize-후 라이브DOM 렌더 + graceful fallback + CSS)
  - L2 `_MERMAID_DIAGRAM_GUIDANCE` 발화 가이던스 주입
  - L3 `table_relationships` migration+DDL+GRANT + `relationships.py` + insight FK introspection + 관계 digest 주입
  - L4 대화 JOIN 학습(`parse_join_relationships` + execute_sql 성공 후 hook)
  - 단위 테스트 19건 통과, 변경 py 전건 compile, ruff clean(신규 코드), alembic single-head
  - **main 머지(PR #462) + 배포 + deploy-backed 라이브 검증 완료** (§5)

## 3. Recent Changes
- 3-phase 일괄 구현(CHG-20260629-relationship-diagrams-0001).
- main 머지 + 배포 + 라이브 검증(CHG-20260629-relationship-diagrams-0002).
- 라이브 mermaid bomb 버그 수정(CHG-20260629-relationship-diagrams-0003): render orphan 누수 제거
  (graceful fallback 복원) + erDiagram 생성 가이던스 강화 + cache-buster bump + 과거 대화 데이터 복구.
- 총 변경 횟수: 3

## 4. Open Issues
- (해소) CHG-0003 배포 후 실 Windows-browser 화면 재검증(PB-0008, TASK rd-h6) — **PASS** (실 Chrome 149,
  라이브 git_commit 8f0a025): 깨진 erDiagram×2 → graceful 코드블록(orphan div/iframe 0·bomb 0), 정상
  erDiagram → SVG 렌더. 증적 `artifacts/pb0008-feature-0013-orphan-fix.png`.
- cardinality(1:N/M:N) 미수집 — 현재 edge 만. FK 메타에서 후속 도출 가능.
- JOIN 파서는 복잡 subquery/CTE 미해석(best-effort, 낮은 confidence 라 영향 제한).

## 5. Test Status
- 자동 테스트: `tests/test_relationships.py` 19건 PASS (JOIN 파서·digest·FK row 추출·alias 해석 + ON-CONFLICT 불변식).
- CHG-0003 mermaid 렌더 검증 (jsdom + vendored mermaid 10.9.3, TEST §2.x):
  - ✅ 라이브 4 블록 파싱 — graph TD / sequenceDiagram / graph LR PASS, erDiagram FAIL(`got ':'`) 확정.
  - ✅ 패치된 `mermaid-render.js` e2e — 깨진 erDiagram 2패스 → leftover bomb 0 · orphan `dmmd-` 0 ·
    graceful 코드블록 2 (graceful fallback 불변식 복원).
  - ✅ 가이던스 예시 erDiagram · 복구된 stored erDiagram 파서 PASS · `agent_core.py` py_compile OK.
  - ✅ 실 브라우저 화면 검증(PB-0008, CHG-0003 배포 후) — 실 Chrome 149, 라이브 served `mermaid-render.js`
    (`?v=20260629-mermaid-orphan-fix`, removeMermaidRenderOrphan 포함) 로 깨진 erDiagram×2 → graceful
    코드블록(body orphan div 0·iframe 0·error-svg 0), 정상 erDiagram → SVG. 증적
    `artifacts/pb0008-feature-0013-orphan-fix.png`. → frontend §18.8 BLOCKING(strict→iframe 주장) 실엔진 반증 확정.
- 라이브 검증 (배포 후, 2026-06-29):
  - ✅ alembic `0024` 적용 — `make migrate`(0020→0024, 0021~0023 멱등 no-op), live current=`0024_table_relationships`.
  - ✅ GRANT 발효 — agent_kb_rw=INSERT/UPDATE/DELETE/SELECT, agent_kb_ro=SELECT, rw 실 INSERT/DELETE 성공.
  - ✅ healthz — status:ok, mysql_ok/pg_ok true, insight heartbeat fresh. web/ask-worker/insight-worker healthy.
  - ✅ **PB-0008 실 Windows Chrome 149** — `markdownToHtml → renderMermaidDiagrams` 전체 경로로 erDiagram
    SVG 렌더(viewBox·mermaid CSS, error fallback 없음). 증적 `artifacts/pb0008-feature-0013-mermaid-render.png`.
- 미검증 항목 (관측 누적 후 자연 확인 — 비-blocking):
  - insight worker FK introspection 은 실 datasource 의 스키마 구조변경 발생 시 작동(현재 table_relationships rows=0, 정상 초기상태).
  - 대화 JOIN 학습 end-to-end 는 실제 사용자 JOIN 질의 누적으로 채워짐.

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- (해소) CHG-0003 배포 후 PB-0008 화면 재검증(rd-h6) PASS — 실 Chrome 149, bomb 0·orphan 0. 잔여 없음.
- (해소) app.js·mermaid-render.js cache-buster bump — CHG-0003 에서 mermaid-render.js bump 완료.
- (해소) 배포·라이브 검증 완료. 후속 비-blocking:
  - 보안: 프런트 mermaid 렌더 XSS 표면 — strict-mode SVG sanitize 불변식 무변경(orphan 제거는 표면
    축소). §18.8 security reviewer SHIP(REV-…T120500) + CHG-0003 적대 패널 재리뷰(REVIEW.md
    REV-20260629T182013 `[AGENT-TEAM:frontend+security]` SHIP — frontend BLOCKING 은 strict 모드 orphan
    이 `d<id>` div(iframe 아님)임을 vendored mermaid 소스로 반증).

## 8. Suggested Improvements
- cardinality 수집(REFERENTIAL_CONSTRAINTS UPDATE_RULE/DELETE_RULE + 컬럼 UNIQUE 여부로 1:1/1:N 추정).
- `_update_kb_from_answer`(현재 미사용 함수) 활성화로 대화 확인 사실 학습(별도 feature).
- 다이어그램 PNG/SVG export 버튼(읽기→공유).
