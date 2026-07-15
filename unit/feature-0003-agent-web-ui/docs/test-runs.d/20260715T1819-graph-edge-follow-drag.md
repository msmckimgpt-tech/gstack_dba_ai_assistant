---
run_at: 2026-07-15T18:19:00+09:00
session: ai/claude/feature-0003-graph-edge-follow-drag
scope: 그래프 뷰 노드/제품 카테고리 드래그 시 관계선(엣지) 미추종 수정 — PixiJS incident 엣지 증분 재그림 (20260715T1819-graph-edge-follow-drag)
verdict: PASS (headless) / DEFERRED (POST-DEPLOY PB-0008 라이브)
---

### Run 1 — 헤드리스 순수/증분 로직 (Environment: node vm, PixiAdapterPure + prototype-stub)
- 명령: `node unit/feature-0003-agent-web-ui/tests/headless/test_pixi_adapter.js`
- 결과 **PASS — 73 PASS / 0 FAIL** (기존 66 + T23 신규 7).
- T23 (graph-edge-follow-drag, `_refreshIncidentEdges` 계약):
  1. incident 엣지만 재그림 — e1(내부 A↔B)·e2(cross-category B↔C) 재그림, e3(무관 C↔D 둘 다 미이동) skip. PASS
  2. cross-category e2 이동 끝점(B) 새 좌표 [500,400] 갱신 — 사용자 정정 케이스 핵심. PASS
  3. cross-category e2 미이동 끝점(C) 옛 좌표 [200,200] 유지 → 연결선 구조 갱신. PASS
  4. `_objs`·world 자식이 새 엣지 오브젝트로 교체(leak/dangling 없음). PASS
  5. `_objSig` 갱신 = `edgeSig(e,a,b)` (다음 full draw() 재사용, 중복 recreate 방지). PASS
  6. 무관 엣지 e3 오브젝트 불변(stale 유지). PASS
  7. 빈 배열·null movedIds no-op(방어). PASS
- 부기: `_refreshIncidentEdges` 는 world/_drawEdge(Pixi 의존)를 stub 하고 `getElementPosition`(순수)·`PixiAdapterPure.edgeId/edgeSig`(순수)로 계약 검증. 실 Pixi 렌더/드래그 시각 추종은 아래 PB-0008 담당.

### Run 2 — 문법 검증 (Environment: node --check, ESM)
- `graph-renderer-pixi.js` `node --check` PASS (export → const 치환 후).

### Run 3 — POST-DEPLOY 라이브 실증 (Environment: Windows-browser, PB-0008 relay) — DEFERRED
- 대상: web 재배포(deploy_scope: included) 후 실 Windows Chrome https://localhost/admin → 지식베이스 > 그래프 뷰.
- 검증 시나리오(예정):
  1. 제품 카테고리 밴드(CAT)를 좌클릭 드래그 → 밴드 이동 중 **cross-category 관계선이 실시간으로 새 위치 추종**(줌 조작 없이). 이동 전 위치 잔상 0.
  2. 스키마 클러스터(combo) 드래그 → 클러스터 내부/외부 엣지 추종.
  3. 개별 테이블 드래그 → 테이블-테이블/테이블-컬럼 관계선 추종.
  4. 대형 스키마(수백 객체·다수 관계선) 드래그 프레임률 관찰(허용 가능 범위 확인).
  5. pageerror 0.
- visual_verification_scope: always (§10.5 web/UI 완료 게이트 — headless 는 렌더 시각 미검증).
