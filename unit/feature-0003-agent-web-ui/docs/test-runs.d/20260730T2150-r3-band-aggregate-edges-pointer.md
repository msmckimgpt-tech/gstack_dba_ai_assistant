---
run_at: 2026-07-30T21:50:00+09:00
session: ai/claude/feature-0016-cluster-outcome
scope: R3 밴드 집계선 픽셀 검증 — 정본 Run 포인터 (그래프 static 자산 거주 feature)
verdict: PASS
---

# Run 포인터 — R3 접힌 밴드 집계 관계선 (Environment: Windows-browser)

그래프 뷰 static 자산(`src/static/graph/*.js`)이 본 feature 에 거주하므로 포인터를 남긴다.
정본 Run: [`unit/feature-0016-metadata-graph/docs/test-runs.d/20260730T2150-r3-band-aggregate-edges.md`](../../../feature-0016-metadata-graph/docs/test-runs.d/20260730T2150-r3-band-aggregate-edges.md)

- 대상: main `dcf4f845` 라이브 배포본 · `admin.js?v=b75da99e12c9` · Chrome/150.0.7871.115 (relay)
- 결과: 컨텐츠 클러스터 밴드 접힘 시 **멤버 미방출 + 관계선이 밴드 단일 엔드포인트로 수렴** — 전 시나리오 PASS, 콘솔 오류 0
- 검증 제약(재사용): **검색 모드에서는 매칭 멤버가 있는 그룹이 강제 펼침**되므로(설계, `graph-core.js` `isCollapsed`),
  접기/펼치기 검증 전 검색창을 비울 것. 이를 모르면 정상 동작을 결함으로 오판한다.
