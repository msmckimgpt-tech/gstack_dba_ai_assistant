---
run_at: 2026-07-15T23:16:00+09:00
session: ai/claude/feature-0003-graph-edge-drag-perf
scope: 그래프 드래그 관계선 재그림 per-frame 부하 최적화 — 인접 인덱스 + in-place Graphics 재사용 + rAF 코얼레싱 (20260715T2316-graph-edge-drag-perf)
verdict: PASS (headless) / DEFERRED (POST-DEPLOY PB-0008 라이브)
---

### Run 1 — 헤드리스 순수/증분 로직 (Environment: node vm, PixiAdapterPure + prototype-stub)
- 명령: `node unit/feature-0003-agent-web-ui/tests/headless/test_pixi_adapter.js`
- 결과 **PASS — 96 PASS / 0 FAIL** (기존 73 + T24 10 + T25 13[적대 리뷰 C1~C4 실-경로·P3]).
- T24 (graph-edge-drag-perf, 3 lever 계약):
  1. **① in-place 재사용**: 기존 엣지 Graphics(clear 보유·parent===world) → `_paintEdge` 1회·`_drawEdge` 0·destroy 안 함·동일 오브젝트 유지·새 끝점 좌표 re-path·world 자식 add/remove 0. (4 assert)
  2. **② 인접 인덱스**: `_incidentEdges(A,B)` = eAB(양끝 dedup 1회)+eBC, eCD 제외 · 인덱스 부재 시 O(E) filter 폴백 동치. (2 assert)
  3. **③ scheduler**: 비-rAF 즉시 동기 폴백(refresh+render) · rAF 코얼레싱(2 호출→rAF 1개·미실행) · flush 시 누적 id(A,B,C) 1회 재그림+렌더 · `_flushEdgeRefresh` 즉시 반영+pending 클리어. (4 assert)
- T23 (graph-edge-follow-drag 추종 정확성) 회귀 전건 PASS — cross-category 추종 계약 불변.
- 부기: rAF 코얼레싱은 sandbox 컨텍스트에 `requestAnimationFrame` 주입해 검증(기본 node vm 은 미정의 → 동기 폴백). 실 렌더/프레임률은 아래 PB-0008.

### Run 2 — 문법 검증 (Environment: node --check, ESM)
- `graph-renderer-pixi.js` `node --check` PASS.

### Run 3 — POST-DEPLOY 라이브 실증 (Environment: Windows-browser, PB-0008 relay) — DEFERRED
- 대상: web 재배포(deploy_scope: included) 후 실 Windows Chrome https://localhost/admin → 지식베이스 > 그래프 뷰.
- 검증 시나리오(예정):
  1. **추종 정확성 유지(회귀 방지)**: 제품 카테고리/스키마 클러스터/테이블 드래그 → cross-category 관계선이 줌 없이 새 위치 실시간 추종(graph-edge-follow-drag 실증 재확인, 옛 위치 잔상 0).
  2. **프레임률 개선**: 대형 스키마(수백 객체·다수 관계선, 예 gunzgame 409) 펼친 상태에서 허브 노드/클러스터 드래그 → 드래그 프레임률 관찰(최적화 전 대비 체감 개선·jank 감소).
  3. **dragend 정합**: pointerup 후 최종 위치에 관계선 정확 반영(rAF 잔여로 인한 stale 없음).
  4. pageerror 0.
- visual_verification_scope: always (§10.5 web/UI 완료 게이트 — headless 는 렌더/프레임률 미검증).
