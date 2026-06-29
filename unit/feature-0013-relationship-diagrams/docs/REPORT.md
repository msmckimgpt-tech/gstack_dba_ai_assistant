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
- Planned: (없음 — 3-phase 전체 코드 완료)
- In Progress: 라이브 검증(배포 후) + 보안 리뷰(권장)
- Done:
  - L1 웹 UI mermaid 렌더(vendor v10.9.3 + sanitize-후 라이브DOM 렌더 + graceful fallback + CSS)
  - L2 `_MERMAID_DIAGRAM_GUIDANCE` 발화 가이던스 주입
  - L3 `table_relationships` migration+DDL+GRANT + `relationships.py` + insight FK introspection + 관계 digest 주입
  - L4 대화 JOIN 학습(`parse_join_relationships` + execute_sql 성공 후 hook)
  - 단위 테스트 17건 통과, 변경 py 전건 compile, ruff clean(신규 코드), alembic single-head

## 3. Recent Changes
- 3-phase 일괄 구현(CHG-20260629-relationship-diagrams-0001).
- 총 변경 횟수: 1

## 4. Open Issues
- cardinality(1:N/M:N) 미수집 — 현재 edge 만. FK 메타에서 후속 도출 가능.
- JOIN 파서는 복잡 subquery/CTE 미해석(best-effort, 낮은 confidence 라 영향 제한).

## 5. Test Status
- 자동 테스트: `tests/test_relationships.py` 17건 PASS (JOIN 파서·digest·FK row 추출·alias 해석).
- 수동 테스트: 미수행.
- 미검증 항목 (라이브 스택 필요 — TEST.md §4):
  - alembic `0024` upgrade 실제 적용 + GRANT 발효(agent_kb_rw upsert).
  - insight worker FK introspection 실 datasource 동작 + telemetry(`relationships_introspected`).
  - 대화 JOIN 학습 → table_relationships 적재 → 다음 답변 digest 주입 end-to-end.
  - **웹 ```mermaid 렌더 — 실제 Windows 브라우저(PB-0008) 화면 검증 필요(§10.5 웹/UI 게이트).**

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- 배포 후: alembic 마이그레이션 적용 확인 + 실 브라우저 렌더 검증(PB-0008).
- 보안: 프런트 mermaid 렌더 XSS 표면 — `/cso` 리뷰 권장(securityLevel:'strict' 로 완화).

## 8. Suggested Improvements
- cardinality 수집(REFERENTIAL_CONSTRAINTS UPDATE_RULE/DELETE_RULE + 컬럼 UNIQUE 여부로 1:1/1:N 추정).
- `_update_kb_from_answer`(현재 미사용 함수) 활성화로 대화 확인 사실 학습(별도 feature).
- 다이어그램 PNG/SVG export 버튼(읽기→공유).
