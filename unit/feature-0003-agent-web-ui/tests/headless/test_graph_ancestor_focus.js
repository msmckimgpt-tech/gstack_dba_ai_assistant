// graph-catcluster-focus 헤드리스 결정론 검증 — 미렌더 노드의 **카메라 승격 사다리**.
//   사용자 보고(2026-07-28): '컨텐츠 카테고리 클러스터'가 접힌 상태에서 하위 테이블 노드의 위치를
//   추적하면(상세 패널 테이블 요소 클릭 · "🎯 이 노드로 이동"), 테이블의 상위 객체인 **접힌 카테고리
//   클러스터**가 아니라 **스키마 클러스터 중앙**으로 카메라가 이동했다.
//
//   근본 원인: `_metaRenderedAncestorFor` 의 승격 사다리가 실제 렌더를 게이팅하는 두 클러스터 계층
//   (컨텐츠 카테고리 = sim-group / 제품 카테고리 밴드)을 건너뛰었다. 게다가 `_metaColParent` 는 테이블
//   키를 받으면 **소속 스키마**를 돌려주므로, 테이블이 미렌더면 사다리가 곧장 스키마 combo 로 뛴다.
//
// 실제 라이브 카메라 팬/렌더는 PixiJS 의존이라 PB-0008(실 Windows 브라우저)에서 육안 검증한다.
// 여기서는 graph-core.js 소스에서 대상 함수 **본문을 그대로 추출**해(테스트가 소스와 결합 — 사본 아님)
// renderedIds/groupOf/catMembers 조합을 결정론적으로 주입하고 승격 대상을 검증한다.
// 사용: node test_graph_ancestor_focus.js [<graph-core.js path>]
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const CORE = process.argv[2] || path.join(__dirname, "..", "..", "src", "static", "graph", "graph-core.js");
const src = fs.readFileSync(CORE, "utf8");

// 함수 본문 추출(종료 = 열0 '}' 라인). 하나라도 실패하면 형식 변경 — fail-loud.
const NEEDED = ["_metaRenderedIdFor", "_metaGroupElementFor", "_metaCategoryElementFor",
  "_metaRenderedAncestorFor", "_metaAncestorKindKo"];
const bodies = [];
for (const fn of NEEDED) {
  const m = src.match(new RegExp("function " + fn + "\\([\\s\\S]*?\\n\\}\\n"));
  if (!m) { console.error(`FAIL: graph-core.js 에서 ${fn} 추출 실패 — 함수명/형식 변경?`); process.exit(1); }
  bodies.push(m[0]);
}

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); }
}

// key(`scope:fqn`) 부모 도출 — graph-core/graph-ctxmenu 실 구현과 동형(테스트 격리용 재현).
//   ⚠ 실 구현과 같이 _metaColParent 는 **테이블 키를 받으면 소속 스키마**를 돌려준다(본 결함의 축).
function catParent(key, fqn) {
  const i = key.indexOf(":"); if (i < 0) return null;
  const f = fqn || key.slice(i + 1); if (!f || f.indexOf(".") < 0) return null;
  return key.slice(0, i) + ":" + f.split(".")[0];
}
function colParent(key, fqn) {
  const i = key.indexOf(":"); if (i < 0) return null;
  const f = fqn || key.slice(i + 1); if (!f) return null;
  const parts = f.split("."); if (parts.length < 2) return null;
  return key.slice(0, i) + ":" + parts.slice(0, -1).join(".");
}

// 격리 컨텍스트 — 한 build 의 렌더 결과(renderedIds)와 두 역인덱스(groupOf/catMembers)를 그대로 주입.
function buildCtx({ nodes = [], rendered = [], groupOf = [], catMembers = [] }) {
  const state = {
    nodes: new Map(nodes.map((n) => [n.key, n])),
    renderedIds: new Set(rendered),
    groupOf: new Map(groupOf),
    catMembers: new Map(catMembers),
  };
  const sandbox = { console, _metaGraph: state, _metaCatParent: catParent, _metaColParent: colParent };
  vm.createContext(sandbox);
  vm.runInContext(bodies.join("\n") +
    "\nglobalThis.__anc = _metaRenderedAncestorFor;" +
    "\nglobalThis.__kind = _metaAncestorKindKo;" +
    "\nglobalThis.__id = _metaRenderedIdFor;", sandbox, { filename: "ancestor-extract.js" });
  return { sandbox, state };
}

const SCOPE = "mysql-x";
const SCHEMA = `${SCOPE}:db1`;
const TABLE = `${SCOPE}:db1.orders`;
const COL = `${SCOPE}:db1.orders.id`;
const ROUTINE = `${SCOPE}:db1.sp_pay`;
const GK = `${SCHEMA}\u0001nm:order`;   // sim-group key 형식(schemaId + U+0001 + fam)
const CATK = "PC:7";                          // 제품 카테고리 key

const NODES = [
  { key: SCHEMA, label: "Schema", fqn: "db1" },
  { key: TABLE, label: "Table", fqn: "db1.orders" },
  { key: COL, label: "Column", fqn: "db1.orders.id" },
  { key: ROUTINE, label: "Routine", fqn: "db1.sp_pay" },
];

// A1: 컬럼 미렌더 + 소속 테이블 렌더 → 테이블(기존 동작 회귀 없음 — 가장 가까운 조상 우선).
{
  const c = buildCtx({ nodes: NODES, rendered: [SCHEMA, TABLE, "GB:" + GK], groupOf: [[TABLE, GK]] });
  check("A1 컬럼 → 렌더된 소속 테이블", c.sandbox.__anc(COL) === TABLE, c.sandbox.__anc(COL));
}

// A2 (핵심 회귀): 컨텐츠 카테고리 접힘 — 테이블 미렌더 · GB: 렌더 · 스키마 combo 렌더.
//     종전엔 _metaColParent(테이블)=스키마 를 타고 스키마 combo 로 뛰었다(= 사용자 보고 증상).
{
  const c = buildCtx({ nodes: NODES, rendered: [SCHEMA, "GB:" + GK], groupOf: [[TABLE, GK]] });
  const got = c.sandbox.__anc(TABLE);
  check("A2 접힌 컨텐츠 카테고리 → GB: 승격", got === "GB:" + GK, got);
  check("A2 스키마 클러스터로 새지 않음", got !== SCHEMA, got);
}

// A3: 컬럼 — 소속 테이블이 접힌 컨텐츠 카테고리 소속(둘 다 미렌더) → GB:.
{
  const c = buildCtx({ nodes: NODES, rendered: [SCHEMA, "GB:" + GK], groupOf: [[TABLE, GK]] });
  const got = c.sandbox.__anc(COL);
  check("A3 컬럼 → 소속 테이블의 GB: 승격", got === "GB:" + GK, got);
}

// A4: 루틴(함수·프로시저)도 같은 사다리 — groupOf 는 루틴 키도 담는다.
{
  const c = buildCtx({ nodes: NODES, rendered: [SCHEMA, "GB:" + GK], groupOf: [[ROUTINE, GK]] });
  check("A4 루틴 → GB: 승격", c.sandbox.__anc(ROUTINE) === "GB:" + GK, c.sandbox.__anc(ROUTINE));
}

// A5: 스키마 카드 접힘(카드 경로는 groupOf 미적재) → SC: 카드(기존 동작 회귀 없음).
{
  const c = buildCtx({ nodes: NODES, rendered: ["SC:" + SCHEMA] });
  check("A5 접힌 스키마 → SC: 카드", c.sandbox.__anc(TABLE) === "SC:" + SCHEMA, c.sandbox.__anc(TABLE));
  check("A5 컬럼도 SC: 카드", c.sandbox.__anc(COL) === "SC:" + SCHEMA, c.sandbox.__anc(COL));
}

// A6: 제품 카테고리 밴드 접힘 — 멤버 클러스터 통째 미방출(catHidden) → CAT: 밴드.
//     종전엔 null 이라 카메라가 아예 이동하지 않고 "표시할 수 없습니다" 로 끝났다.
{
  const c = buildCtx({ nodes: NODES, rendered: ["CAT:" + CATK, "CATH:" + CATK, "CATX:" + CATK],
    catMembers: [[CATK, [SCHEMA]]] });
  const got = c.sandbox.__anc(TABLE);
  check("A6 접힌 제품 카테고리 → CAT: 밴드", got === "CAT:" + CATK, got);
  check("A6 컬럼도 CAT: 밴드", c.sandbox.__anc(COL) === "CAT:" + CATK, c.sandbox.__anc(COL));
}

// A7: 스키마 클러스터가 렌더돼 있으면 카테고리 밴드보다 스키마가 우선(가장 가까운 조상).
{
  const c = buildCtx({ nodes: NODES, rendered: [SCHEMA, "CAT:" + CATK], catMembers: [[CATK, [SCHEMA]]] });
  check("A7 스키마 렌더 시 CAT 보다 스키마 우선", c.sandbox.__anc(TABLE) === SCHEMA, c.sandbox.__anc(TABLE));
}

// A8: stale 역인덱스 게이팅 — groupOf 에 남아도 GB: 미렌더면 다음 계층으로.
{
  const c = buildCtx({ nodes: NODES, rendered: [SCHEMA], groupOf: [[TABLE, GK]] });
  check("A8 stale groupOf → 스키마로 폴백", c.sandbox.__anc(TABLE) === SCHEMA, c.sandbox.__anc(TABLE));
}

// A9: stale catMembers 게이팅 — CAT: 미렌더면 null(허위 카메라 이동 금지).
{
  const c = buildCtx({ nodes: NODES, rendered: [], catMembers: [[CATK, [SCHEMA]]] });
  check("A9 stale catMembers → null", c.sandbox.__anc(TABLE) === null, c.sandbox.__anc(TABLE));
}

// A10: 전 계층 미렌더 → null(호출측이 안내만).
{
  const c = buildCtx({ nodes: NODES, rendered: [] });
  check("A10 전 계층 미렌더 → null", c.sandbox.__anc(COL) === null, c.sandbox.__anc(COL));
  check("A10 빈 key → null", c.sandbox.__anc("") === null, c.sandbox.__anc(""));
}

// A11: 사다리 순서 전수 — 같은 모델에서 계층을 하나씩 걷어낼 때 승격 대상이 순서대로 강등된다.
{
  const ladder = [
    { rendered: [TABLE, "GB:" + GK, SCHEMA, "CAT:" + CATK], want: TABLE },
    { rendered: ["GB:" + GK, SCHEMA, "CAT:" + CATK], want: "GB:" + GK },
    { rendered: [SCHEMA, "CAT:" + CATK], want: SCHEMA },
    { rendered: ["CAT:" + CATK], want: "CAT:" + CATK },
    { rendered: [], want: null },
  ];
  ladder.forEach((step, i) => {
    const c = buildCtx({ nodes: NODES, rendered: step.rendered,
      groupOf: [[TABLE, GK]], catMembers: [[CATK, [SCHEMA]]] });
    const got = c.sandbox.__anc(COL);
    check(`A11-${i + 1} 사다리 ${step.want === null ? "null" : step.want}`, got === step.want, { got, want: step.want });
  });
}

// A12: 상태줄 명칭 매핑 — 승격 대상을 사용자에게 정확히 안내(종전 "소속 테이블" 단정 오안내 해소).
{
  const c = buildCtx({ nodes: NODES, rendered: [] });
  const K = c.sandbox.__kind;
  check("A12 GB: → 컨텐츠 카테고리", K("GB:" + GK) === "컨텐츠 카테고리", K("GB:" + GK));
  check("A12 GH: → 컨텐츠 카테고리", K("GH:" + GK) === "컨텐츠 카테고리", K("GH:" + GK));
  check("A12 CAT: → 제품 카테고리", K("CAT:" + CATK) === "제품 카테고리", K("CAT:" + CATK));
  check("A12 SC: → 스키마 클러스터", K("SC:" + SCHEMA) === "스키마 클러스터", K("SC:" + SCHEMA));
  check("A12 combo → 스키마 클러스터", K(SCHEMA) === "스키마 클러스터", K(SCHEMA));
  check("A12 테이블 → 소속 테이블", K(TABLE) === "소속 테이블", K(TABLE));
  check("A12 루틴 → 소속 함수·프로시저", K(ROUTINE) === "소속 함수·프로시저", K(ROUTINE));
  check("A12 미상 → 상위 객체", K("ZZ:none") === "상위 객체", K("ZZ:none"));
  // 조사 불변식: 호출측이 "…{명칭}로 카메라 이동" 으로 붙이므로 전 라벨이 모음 또는 ㄹ 받침으로 끝나야 한다.
  //   (받침 있는 명사가 새로 들어오면 "…역할로" 처럼 어긋나므로 여기서 고정.)
  const labels = [K("GB:x"), K("GH:x"), K("CAT:x"), K("CATH:x"), K("SC:" + SCHEMA), K(SCHEMA), K(TABLE), K(ROUTINE), K("ZZ:none")];
  const takesRo = (s) => { const c = s.charCodeAt(s.length - 1) - 0xac00;
    if (c < 0 || c > 11171) return true;   // 한글 음절이 아니면 판정 제외
    const jong = c % 28; return jong === 0 || jong === 8; };   // 받침 없음(모음) 또는 ㄹ(8)
  check("A12 전 라벨이 조사 '로' 적합(모음 또는 ㄹ 받침)", labels.every(takesRo), labels.filter((s) => !takesRo(s)));
}

// A13: 정적 회귀 가드 — 승격 사다리에서 두 계층 호출이 사라지면(되돌림) 즉시 적발.
{
  const anc = src.match(/function _metaRenderedAncestorFor\(key\) \{[\s\S]*?\n\}\n/)[0];
  check("A13 사다리에 _metaGroupElementFor 존재", anc.indexOf("_metaGroupElementFor") >= 0);
  check("A13 사다리에 _metaCategoryElementFor 존재", anc.indexOf("_metaCategoryElementFor") >= 0);
  check("A13 GB/CAT 해소는 renderedIds 게이팅",
    /renderedIds/.test(bodies[1]) && /renderedIds/.test(bodies[2]));
  // 접힘은 지속 의도 — 승격 경로가 자동 펼침(expand/toggle)을 부르지 않는다.
  check("A13 승격 경로에 자동 펼침 없음",
    !/_metaGraphExpandSchema|_metaGraphToggleColumns/.test(anc + bodies[1] + bodies[2]));
}

console.log(`\n${pass} PASS, ${fail} FAIL`);
process.exit(fail ? 1 : 0);
