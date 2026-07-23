// graph-node-reveal 헤드리스 결정론 검증 — "🎯 이 노드로 이동" 버튼이 미렌더 노드에서
//   차단하지 않고 **부모 체인(스키마→테이블 컬럼)을 활성화(펼침)** 하는 오케스트레이션.
//   사용자 요구(2026-07-23): 화면에 없는 노드도 상위 부모노드를 모두 활성화해 노출.
//
// 실제 라이브 카메라 팬/렌더는 PixiJS(G6) 의존이라 PB-0008(실 Windows 브라우저)에서 육안 검증한다.
// 여기서는 graph-ctxmenu.js 소스에서 `_metaGraphRevealNode` 함수 **본문을 그대로 추출**해,
// 의존 함수(_metaGraphExpandSchema/_metaGraphToggleColumns/_metaRenderedIdFor 등)를 test double 로
// 주입하고 확장 호출 순서·scope 가드·이미 렌더 fast-path 를 결정론적으로 검증한다. ES-module import
// 리팩터(ITEM-09) 이후 파일 전체 vm-eval 은 불가하므로, 검증 대상 함수만 추출해 격리 실행한다.
// 사용: node test_graph_reveal.js [<graph-ctxmenu.js path>]
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const CTX = process.argv[2] || path.join(__dirname, "..", "..", "src", "static", "graph", "graph-ctxmenu.js");
const src = fs.readFileSync(CTX, "utf8");

// 실제 소스에서 함수 본문 추출(테스트가 소스와 결합 — 사본 아님). 함수 종료 = 열0 '}' 라인.
const m = src.match(/async function _metaGraphRevealNode\(key\) \{[\s\S]*?\n\}\n/);
if (!m) { console.error("FAIL: graph-ctxmenu.js 에서 _metaGraphRevealNode 추출 실패 — 함수명/형식 변경?"); process.exit(1); }
const fnText = m[0];

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra)); }
}

// key(`scope:fqn`)에서 부모 도출 — graph-core/graph-ctxmenu 실 구현과 동형(테스트 격리용 재현).
function catParent(key) {   // → 소속 스키마 `scope:schema` (fqn 세그먼트 없으면 null)
  const i = key.indexOf(":"); if (i < 0) return null;
  const f = key.slice(i + 1); if (f.indexOf(".") < 0) return null;
  return key.slice(0, i) + ":" + f.split(".")[0];
}
function colParent(key) {   // → 소속 테이블 `scope:schema.table` (2세그 미만이면 null)
  const i = key.indexOf(":"); if (i < 0) return null;
  const parts = key.slice(i + 1).split("."); if (parts.length < 2) return null;
  return key.slice(0, i) + ":" + parts.slice(0, -1).join(".");
}

// 시나리오별 격리 컨텍스트 생성 — reveal 이 호출하는 의존 함수를 record 하는 test double 로 주입.
//   renderedAfter: {when: "init"|"schema"|"column", set: Set} — 어느 확장 후 노드가 렌더되는지 모사.
function buildCtx({ curScope, nodeScopeKey, fqn, schemaExpanded = [], tableHasCols = [], renderAt }) {
  const calls = [];
  const state = {
    graph: {},
    nodes: new Map([[nodeScopeKey, { key: nodeScopeKey, fqn }]]),
    schemaExpanded: new Set(schemaExpanded),
    _colsWithCols: new Set(tableHasCols),
    _rendered: (renderAt === "init"),
  };
  const sandbox = {
    console,
    _metaGraph: state,
    adminState: { metadata: { scopeKey: curScope } },
    _metaRenderedIdFor: (k) => (state._rendered && k === nodeScopeKey) ? k : null,
    _metaRenderedAncestorFor: () => null,
    _metaCatParent: (k) => catParent(k),
    _metaColParent: (k) => colParent(k),
    _metaTableHasCols: (k) => state._colsWithCols.has(k),
    _metaGraphExpandSchema: async (k) => {
      calls.push(["schema", k]);
      state.schemaExpanded.add(k);
      if (renderAt === "schema") state._rendered = true;   // 테이블·함수: 스키마 펼침만으로 렌더
      return "expanded";
    },
    _metaGraphToggleColumns: async (k) => {
      calls.push(["column", k]);
      state._colsWithCols.add(k);
      if (renderAt === "column") state._rendered = true;   // 컬럼: 테이블 컬럼 펼침 후 렌더
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(fnText + "\nglobalThis.__reveal = _metaGraphRevealNode;", sandbox, { filename: "reveal-extract.js" });
  return { sandbox, calls, state };
}

(async () => {
  const SCOPE = "mssql-x";
  const COL = `${SCOPE}:a.t1.c1`, TABLE = `${SCOPE}:a.t1`, ROUTINE = `${SCOPE}:a.fn1`, SCHEMA = "a";

  // S1: 이미 렌더 → true, 확장 호출 0 (fast-path).
  {
    const c = buildCtx({ curScope: SCOPE, nodeScopeKey: COL, fqn: "a.t1.c1", renderAt: "init" });
    const r = await c.sandbox.__reveal(COL);
    check("S1 이미 렌더 → true", r === true, r);
    check("S1 확장 호출 없음", c.calls.length === 0, c.calls);
  }

  // S2: 컬럼 · 스키마 접힘 → 스키마 펼침 → (미렌더) 테이블 컬럼 펼침 → 렌더 → true. (사용자 시나리오 핵심)
  {
    const c = buildCtx({ curScope: SCOPE, nodeScopeKey: COL, fqn: "a.t1.c1", renderAt: "column" });
    const r = await c.sandbox.__reveal(COL);
    check("S2 컬럼 reveal → true", r === true, r);
    check("S2 스키마 먼저 펼침", c.calls[0] && c.calls[0][0] === "schema" && c.calls[0][1] === `${SCOPE}:${SCHEMA}`, c.calls);
    check("S2 이어 소속 테이블 컬럼 펼침", c.calls[1] && c.calls[1][0] === "column" && c.calls[1][1] === TABLE, c.calls);
    check("S2 확장 정확히 2회", c.calls.length === 2, c.calls);
  }

  // S3: 테이블 · 스키마 접힘 → 스키마 펼침만으로 렌더 → true, 컬럼 펼침 미호출.
  {
    const c = buildCtx({ curScope: SCOPE, nodeScopeKey: TABLE, fqn: "a.t1", renderAt: "schema" });
    const r = await c.sandbox.__reveal(TABLE);
    check("S3 테이블 reveal → true", r === true, r);
    check("S3 스키마 1회만", c.calls.length === 1 && c.calls[0][0] === "schema", c.calls);
  }

  // S4: 스키마 이미 펼침(schemaExpanded) · 컬럼 미펼침 → 스키마 펼침 skip, 컬럼 펼침만.
  {
    const c = buildCtx({ curScope: SCOPE, nodeScopeKey: COL, fqn: "a.t1.c1",
      schemaExpanded: [`${SCOPE}:${SCHEMA}`], renderAt: "column" });
    const r = await c.sandbox.__reveal(COL);
    check("S4 이미 펼친 스키마 → true", r === true, r);
    check("S4 스키마 재펼침 없음", !c.calls.some((x) => x[0] === "schema"), c.calls);
    check("S4 컬럼 펼침만", c.calls.length === 1 && c.calls[0][0] === "column" && c.calls[0][1] === TABLE, c.calls);
  }

  // S5: 타 데이터소스(scope 불일치) → 즉시 false, 확장 0 (교차-scope 오염 방지 가드).
  {
    const c = buildCtx({ curScope: "other-ds", nodeScopeKey: COL, fqn: "a.t1.c1", renderAt: "column" });
    const r = await c.sandbox.__reveal(COL);
    check("S5 타 scope → false", r === false, r);
    check("S5 확장 호출 없음", c.calls.length === 0, c.calls);
  }

  // S6: 함수(Routine, 2세그) · 스키마 접힘 → 스키마 펼침으로 렌더 → true, 컬럼 펼침 미호출.
  {
    const c = buildCtx({ curScope: SCOPE, nodeScopeKey: ROUTINE, fqn: "a.fn1", renderAt: "schema" });
    const r = await c.sandbox.__reveal(ROUTINE);
    check("S6 함수 reveal → true", r === true, r);
    check("S6 스키마 1회·컬럼 0", c.calls.length === 1 && c.calls[0][0] === "schema", c.calls);
  }

  // S7: 활성화해도 끝내 미렌더(표시 상한 등) → false (호출측이 조상 승격 폴백).
  {
    const c = buildCtx({ curScope: SCOPE, nodeScopeKey: COL, fqn: "a.t1.c1", renderAt: "never" });
    const r = await c.sandbox.__reveal(COL);
    check("S7 끝내 미렌더 → false", r === false, r);
    check("S7 스키마·컬럼 모두 시도", c.calls.length === 2, c.calls);
  }

  console.log(`\n${pass} PASS, ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
})();
