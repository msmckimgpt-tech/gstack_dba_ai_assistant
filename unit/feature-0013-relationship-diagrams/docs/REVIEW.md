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

## REV-20260629T140500-relationship-diagrams [SKIPPED:deploy+doc-merge only — 코드 로직 무변경, §18.8 패널은 REV-…T120500 에서 완료] 배포 완료 기록
- Related Change: CHG-20260629-relationship-diagrams-0002
- Panel skip 사유: 이번 변경은 main 머지 충돌 해소(append형 docs/wiki) + 라이브 배포뿐 — 코드 로직 무변경.
  코드 적대 검증은 선행 REV-20260629T120500 `[AGENT-TEAM:security+backend+frontend]` SHIP 으로 완료됨.
- deploy_scope 승인 근거 (Phase 6.8): 전역 `FIRST_REQUEST.md deploy_scope: included`(init standing 값)
  + feature `FUNCTION.md` 동일 선언 → cycle-final 후 web 재배포 사전 승인. 자동 배포 진행, 첫 배포 직전
  "deploy_scope: included 활성" 1줄 표면화함.
- 라이브 검증 결과: alembic 0024 적용(live=0024) · `table_relationships`+GRANT 발효(rw CRUD 실측) ·
  healthz ok · **PB-0008 실 Windows Chrome mermaid erDiagram SVG 렌더 PASS**
  (`artifacts/pb0008-feature-0013-mermaid-render.png`).
- Follow-up (비-blocking): app.js cache-buster bump(컨벤션 nit — ETag 재검증으로 기능 무영향) ·
  `/cso` 보안 리뷰(권장) · cardinality 수집(후속 cycle).

## REV-20260629T182013-relationship-diagrams [AGENT-TEAM:frontend+security] SHIP — §18.8 CHG-0003 적대 패널 (frontend BLOCKING 소스근거로 반증)
- Related Change: CHG-20260629-relationship-diagrams-0003 (mermaid "Syntax error" bomb 수정 — render orphan 제거 + erDiagram 가이던스 + cache-buster + 데이터 복구)
- Panel: 2 적대 리뷰어 병렬 (frontend·correctness / security). resume(`/_template:resume`) 재개 시
  실행 — 원본 세션(fc28c82a)이 동일 패널 대기 중 session-limit 으로 중단, REVIEW.md 미기록분을 완수.
- **Security (SHIP, NIT 1)**: sanitize 불변식(strict-mode SVG sanitize, `htmlLabels:false`, `out.svg`
  전용, `bindFunctions` 미사용, 앱 DOMPurify 전역 무변경) **무변경** 확인. orphan 제거는 removeChild
  단일 연산이라 신규 XSS 표면 0 — 오히려 잔류 bomb 제거로 표면 축소. 프롬프트 가이던스/데이터 복구/
  cache-buster 모두 렌더 보안 자세에 중립. **NIT(비-blocking, 수용)**: marked raw-HTML passthrough +
  DOMPurify 기본 `id` 허용으로 악의적 콘텐츠가 본문에 `id="dmmd-N"` 를 심으면, `getElementById` 트리순서
  상 mermaid 임시 컨테이너보다 앞서 잡혀 패치가 본문 요소를 오제거할 수 있음. 단 결과는 (a) 공격자가
  자기 콘텐츠 삭제 또는 (b) 경미한 표시 교란(자해성)일 뿐 — **코드실행/sanitize 우회/XSS 아님**. 가시
  회귀 아니므로 수용. 후속 견고화 옵션: id 에 랜덤 suffix 또는 `document.body` 직속 자식으로 스코프 제한.
- **Frontend·correctness (BLOCKING 제기 → 반증)**: 리뷰어는 "strict 모드에서 mermaid 가 main body 에
  남기는 orphan 은 `d<id>` div 가 아니라 iframe `i<id>`(`d<id>` 는 iframe 내부)이므로 `getElementById("d"+id)`
  는 항상 null → 수정 no-op, 버그 미수정" 으로 BLOCK 판정. **반증 (vendored mermaid 10.9.3 소스 직접 실측)**:
  render 함수 `Tqt` 에서 `const P = p.securityLevel === sqt` 이고 `sqt = "sandbox"` — 즉 **P 는
  `securityLevel === "sandbox"` 여부이지 strict 가 아니다.** 리뷰어가 `P` 를 strict 로 오독함. 앱은
  `securityLevel:"strict"`(mermaid-render.js:49) → P=false → iframe 분기(`q$e(...,"i"+i)`) 미실행,
  `A=Ir("body")` 유지, 임시 컨테이너는 `z$e(A,i,"d"+i)` = `<div id="d<id>">` 가 **main document.body 직속**.
  파싱 실패 시 `if(zjt(),W) throw W` 가 정리 라인 `Ir(P?y:_).node().remove()`(strict 면 `#d<id>`) 보다
  먼저 실행 → `<div id="d<id>">` orphan 잔류. `removeMermaidRenderOrphan` 의 `getElementById("d"+id)` 가
  **바로 그 div 를 찾아 제거** → 수정은 strict 경로에서 정확히 동작. (iframe `i<id>` 경로는 sandbox 전용.)
  사전 cleanup `Eqt(document,i,"d"+i,"i"+i)` 는 동일 id 충돌만 제거 → id 가 `mmd-<seq>` 로 고유하므로
  이전 패스 orphan 미청소(누적 사실 정합). 원본 세션의 jsdom e2e("깨진 2패스 → bomb 0·orphan 0·graceful 2")
  도 동일 결론 뒷받침.
- 반영한 NIT: 없음(가시 회귀 아님 — 수용 기록). BLOCKING: 없음(반증됨).
- 봉인(seal): 배포 후 PB-0008 실 Windows-browser 로 "문법오류 다이어그램 → bomb iframe/div 잔류 0 +
  graceful 코드블록" 동작 재검증(rd-h6) — frontend 리뷰어 권고와 정합, 정적 반증을 동작으로 최종 확인.
- Open Questions: 없음(blocking). Human Approval Needed: 없음(사전 승인 범위 내, deploy_scope: included).
