---
doc_type: REVIEW
feature_id: feature-0013-relationship-diagrams
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260629-relationship-diagrams-0001
- Related Change: CHG-20260629-relationship-diagrams-0001
- Reason: 사용자 요청(2026-06-29) — assistant 가 "특정 기능이 어떤 flow 로 동작하나/구조 관계" 질문에
  mermaid 다이어그램으로 답하고, 관계 데이터를 확보·지속 학습. grounding: 제품 객체레이어(사용자 DB)
  — entry persona Phase 3.2 agentive/memory 규칙. 범위=전체 3-phase, 전용 worktree(AskUserQuestion).
- Alternatives Considered:
  - **렌더 보안**: scout 권고는 DOMPurify 전역 ALLOWED_TAGS 에 SVG 허용. **불채택** — 모든 메시지의
    sanitize 표면을 영구 확대(XSS). 대신 sanitize-후 라이브 DOM 에서 `mermaid.render(securityLevel:'strict')`
    렌더 → SVG 가 DOMPurify 를 통과하지 않고, mermaid 자체가 라벨을 escape. 표면 최소화. (ANCHOR §2 Alt-C)
  - **mermaid 배포**: CDN `<script>` vs vendor. **vendor 채택** — 다이어그램은 핵심 기능이고 LAN/오프라인
    배포 환경(feature-0006)에서 CDN 차단 시 기능 소실. 폰트(cosmetic)만 CDN 인 기존 패턴과 정합.
  - **관계 데이터 모델**: rag_objects.category_join_hints_json(freeform JSONB) 확장 vs 정규화 테이블.
    **정규화 `table_relationships` 채택** — UNIQUE edge·confidence·출처별 merge·질의 매칭이 명확.
    introspection 과 대화 학습의 단일 수렴점(ANCHOR §1).
  - **학습 trigger**: post-answer LLM 추출 vs 실행된 JOIN 파싱. **JOIN 파싱 채택** — LLM 호출 비용 0,
    실제 실행된(=검증된) 관계만 학습. `_update_kb_from_answer`(미사용 함수)는 별도 범위.
- Risks:
  - **(Major, 보안)** 프런트 mermaid 렌더 — `securityLevel:'strict'` 로 완화했으나 mermaid CVE 이력 존재.
    staging 에서 `/cso` 보안 리뷰 권장. DOMPurify 전역 설정은 무변경(회귀 0).
  - **(Minor)** JOIN regex 파서는 best-effort — 복잡 subquery/CTE 는 미해석. confidence 0.4 +
    introspection(1.0) 우선이라 오학습 영향 낮음. self-join·해석실패는 [] 반환(단위 테스트 보증).
  - **(Minor)** insight introspection 은 스키마 구조변경 시에만 + table cap 200 + 전부 try/except —
    8초 insight 루프 무차단. PG 미가용 시 전 경로 no-op.
  - **(운영, DEPLOY TRAP)** 신규 테이블 GRANT 누락 시 agent_kb_rw upsert 시 permission denied —
    migration·schema.sql 양쪽에 명시 GRANT 반영(0023/0011 동형 교훈).
- Open Questions: insight introspection 빈도(현재 구조변경 gate)가 충분한지 라이브 관측 후 조정 가능.
  cardinality(1:N 등) 는 현재 미수집 — FK 메타에서 후속 도출 가능(후속 cycle).
- Human Approval Needed: 비파괴 스키마 추가는 FUNCTION.md §13 사전 승인. deploy_scope: included(전역)에
  따라 cycle-final 후 web 재배포 자동. 보안 리뷰(/cso)는 권장 수준(사용자 판단).

## REV-20260629T120500-relationship-diagrams [AGENT-TEAM:security+backend+frontend] PASS — §18.8 적대 검증 패널
- Related Change: CHG-20260629-relationship-diagrams-0001
- Panel: 3 적대 리뷰어 병렬 (security / backend·correctness / frontend·integration), 모두 **SHIP**(blocking 0).
- Security (SHIP): mermaid 렌더 XSS 경로를 vendored mermaid 10.9.3 바이트코드까지 디컴파일 검증 —
  `securityLevel:'strict'` → sandbox/loose flag 둘 다 false → mermaid 내장 DOMPurify 가 SVG 항상 sanitize,
  `htmlLabels:false` 로 라벨 escape, 앱은 `out.svg` 만 쓰고 `bindFunctions` 미사용(click XSS 비활성).
  앱 DOMPurify 전역 무변경(setConfig/addHook 없음) 확인. 관계 데이터는 `_datamark_untrusted` 로 기존
  KB 컨텍스트와 동일 격리. upsert/read 전건 `%s` 파라미터화. f-string FK SQL 은 기존 main 패턴(미악화).
- Backend (SHIP): **ON CONFLICT 대상 == `ux_table_relationships_edge` UNIQUE 정확 일치**(최고위험 항목 — 단위
  테스트로 lock). alembic 0024 chain linear·GRANT(시퀀스 포함) 정합·trigger 존재. insight hook 이중
  try/except(8초 루프 무차단)·table cap 200·구조변경 gate. execute_sql 학습 hook 성공 게이트 정확.
- Frontend (SHIP): script 로드 순서(mermaid before app.js) 정확·v10.9.3 async render API 정확·단일 render
  seam(renderMessageContent)·fallback 라이브러리 비의존·no-mermaid/diff/attachment 경로 무회귀·node --check OK.
- 반영한 비-blocking 제안: ① ON-CONFLICT↔UNIQUE 불변식 단위테스트 추가, ② 비정상 식별자 보수 처리 테스트 추가.
  (총 단위 테스트 17→19건 PASS.)
- 후속(비-blocking): vendored mermaid 차기 refresh 시 내장 DOMPurify(3.1.6) bump · cardinality 수집 ·
  라이브/Windows-browser end-to-end 검증.
- Open Questions: 없음 (blocking). Human Approval Needed: 없음 (사전 승인 범위 내).
