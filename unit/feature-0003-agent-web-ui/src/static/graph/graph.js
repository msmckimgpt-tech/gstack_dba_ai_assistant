// feature-0003 ITEM-09 — 메타데이터 지식그래프 뷰 barrel (batch3: 7모듈 세분화).
// admin.js 의 import 경로 안정성을 위해 공개 4심볼만 re-export 한다(경계 = census 실측).
// 모듈 지도: graph-state(상태·상수) / graph-roleviz / graph-util / graph-rellayout /
// graph-simgroups / graph-core(init·load·build·LOD) / graph-ctxmenu(우클릭·패널).
// 하위 모듈 좌표·재적용 절차는 MAPPING.md 참조. import specifier 의 ?v=dev 는 빌드가
// content-hash 로 주입(inject_asset_stamp.py, §13.1 v3.35.1 — 이중 인스턴스화 방지).
export { _metaGraph } from "./graph-state.js?v=dev";
export { _metaRoleLegendTips } from "./graph-roleviz.js?v=dev";
export { _metaShowGraph, _metaGraphLoadRoots } from "./graph-core.js?v=dev";
