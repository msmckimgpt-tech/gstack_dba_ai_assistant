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
- 총 변경 횟수: 2

## 4. Open Issues
- cardinality(1:N/M:N) 미수집 — 현재 edge 만. FK 메타에서 후속 도출 가능.
- JOIN 파서는 복잡 subquery/CTE 미해석(best-effort, 낮은 confidence 라 영향 제한).

## 5. Test Status
- 자동 테스트: `tests/test_relationships.py` 19건 PASS (JOIN 파서·digest·FK row 추출·alias 해석 + ON-CONFLICT 불변식).
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
- (해소) 배포·라이브 검증 완료. 후속 비-blocking:
  - 보안: 프런트 mermaid 렌더 XSS 표면 — `/cso` 리뷰 권장(이미 §18.8 security reviewer 가 strict-mode SVG sanitize 디컴파일 검증·SHIP).
  - app.js cache-buster 컨벤션 bump(ETag 재검증으로 기능 무영향, MODIFY CHG-0002 follow-up).

## 8. Suggested Improvements
- cardinality 수집(REFERENTIAL_CONSTRAINTS UPDATE_RULE/DELETE_RULE + 컬럼 UNIQUE 여부로 1:1/1:N 추정).
- `_update_kb_from_answer`(현재 미사용 함수) 활성화로 대화 확인 사실 학습(별도 feature).
- 다이어그램 PNG/SVG export 버튼(읽기→공유).
