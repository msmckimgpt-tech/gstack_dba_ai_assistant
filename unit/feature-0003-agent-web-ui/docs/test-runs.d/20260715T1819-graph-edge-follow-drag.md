---
run_at: 2026-07-15T18:19:00+09:00
session: ai/claude/feature-0003-graph-edge-follow-drag
scope: 그래프 뷰 노드/제품 카테고리 드래그 시 관계선(엣지) 미추종 수정 — PixiJS incident 엣지 증분 재그림 (20260715T1819-graph-edge-follow-drag)
verdict: PASS (headless + POST-DEPLOY PB-0008 라이브)
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

### Run 3 — POST-DEPLOY 라이브 실증 (Environment: Windows-browser, PB-0008 relay) — **PASS**
- 배포: PR #824 → main 0f26cec1 + `sudo -E bin/deploy-web.sh` 무중단 롤링(web-a/web-b recreate·soak 90s PASS·워커 롤아웃). 서빙 자산 `/app/web/static/graph/graph-renderer-pixi.js` `_refreshIncidentEdges` grep=4(baked·stale 아님).
- 방법: win-browser.py 실 Windows Chrome 150(relay 172.26.144.1:9223→9222), https://localhost/admin(200·로그인 세션) → 지식베이스 > 그래프 뷰. 렌더러 = PixiJS(default=pixi, window.PIXI loaded). 루트 뷰 = **제품 카테고리 14개(좌) + 데이터소스 18개(우) + cross-category 관계선**(canvas 245,180 615×570).
- 결과 **PASS**:
  1. **cross-category 관계선 실시간 추종**: 제품 카테고리 "건즈-개발·1"(중앙 ~552,464)을 합성 PointerEvent(pointerdown+pointermove×10, button0)로 좌상단(~400,280)으로 드래그. **pointerup 전·줌 조작 없이** mid-drag 스크린샷에서 카테고리가 새 위치로 이동 + 데이터소스로 향하는 **관계선이 새 위치를 그대로 추종**(옛 위치 잔상 0). 수정 전이라면 관계선이 옛 위치(중앙)에 남았을 것 — `_refreshIncidentEdges`(이동 끝점 새 좌표·미이동 데이터소스 끝점 현재 좌표) 실증. evidence: graph_root(before)·graph_middrag(추종)·graph_after_reset.
  2. **dragend 후 정합**: pointerup 후에도 카테고리가 새 위치 유지(ADR-004 자유배치 영속) + 관계선 정상 추종.
  3. **pageerror 0**: window 에러 배열 빈값·docReady complete·canvas 정상.
- visual_verification_scope: always (§10.5 web/UI 완료 게이트) — 충족.
- 미실행(비회귀·후속): 스키마 클러스터/개별 테이블 드래그(동일 chokepoint 경유라 커버 추정)·허브 대형 스키마 프레임률(F1 트레이드오프 관측). 핵심 사용자 보고 케이스(제품 카테고리 cross-category)는 실증 완료.
