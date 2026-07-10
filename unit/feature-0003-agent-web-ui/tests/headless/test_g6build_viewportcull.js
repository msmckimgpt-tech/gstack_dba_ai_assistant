// §65 헤드리스 격리검증 — viewport-cull: 줌인 대형모델에서 화면(뷰포트+마진) 밖 테이블의 컬럼 방출 억제.
//   불변식: ① 작은 뷰포트에서 화면 밖 테이블은 컬럼 미방출(전체 컬럼 노드 < full 뷰포트) ② **combo-safe**:
//   테이블 칩은 항상 방출(화면 안팎 무관) → combo extent 불변 ③ 화면 안 테이블은 컬럼 방출 유지
//   ④ 게이트: 모델 노드 < _META_CULL_MIN(400) 이면 컬링 안 함. ⑤ 좌표 band-invariant(테이블 위치 불변).
// 사용: node test_g6build_viewportcull.js <admin.js path>
"use strict";
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
const noop = () => {};
const elStub = () => ({ style:{}, dataset:{}, classList:{add:noop,remove:noop,toggle:noop,contains:()=>false}, addEventListener:noop, removeEventListener:noop, appendChild:noop, removeChild:noop, setAttribute:noop, getAttribute:()=>null, querySelector:()=>null, querySelectorAll:()=>[], focus:noop, value:"", textContent:"", innerHTML:"" });
const sandbox = { console, setTimeout, clearTimeout, setInterval, clearInterval, URL, URLSearchParams, performance:{now:()=>Date.now()}, localStorage:{getItem:()=>null,setItem:noop,removeItem:noop}, sessionStorage:{getItem:()=>null,setItem:noop,removeItem:noop}, navigator:{clipboard:{}}, location:{href:"http://x/admin",pathname:"/admin",search:"",hash:""}, fetch:()=>Promise.resolve({ok:true,status:200,json:async()=>({})}), document:Object.assign(elStub(),{getElementById:()=>null,body:elStub(),documentElement:elStub(),createElement:elStub,addEventListener:noop,removeEventListener:noop,hidden:false}), G6:undefined, window:null, requestAnimationFrame:(f)=>setTimeout(f,0) };
sandbox.window = sandbox; vm.createContext(sandbox);
try { vm.runInContext(src, sandbox, { filename: "admin.js" }); } catch (e) { console.log("(eval note:", String(e&&e.message).slice(0,120), ")"); }
const g = sandbox;
g.__M = vm.runInContext("typeof _metaGraph!=='undefined'?_metaGraph:null", sandbox);
if (typeof g._metaG6Build !== "function" || !g.__M) { console.error("FAIL: 미로딩"); process.exit(1); }
const SCOPE = "mssql-x";
function seed(nTables, colsEach) {
  const M = g.__M;
  M.nodes = new Map(); M.edges = new Map(); M.mode="roots"; M.loadedScope=SCOPE;
  M.schemaExpanded=new Set([SCOPE+":big"]); M.schemaLoaded=new Set(); M.schemaLoading=new Set(); M.schemaTruncated=new Set(); M.schemaTotals=new Map();
  M.searchMatch=null; M.searchMatchTables=null; M.searchMatchNodes=null; M.searchCapped=false; M.searchAdded=new Set(); M.routineExpanded=new Set();
  M.clusterOffset=new Map(); M.nodePos=new Map(); M.groupOffset=new Map(); M.groupCollapsed=new Set(); M.groupMembers=new Map(); M.groupOf=new Map();
  M.clusterOrder=[]; M.tableOrder=new Map(); M.groupOrder=new Map(); M.groupTableOrder=new Map();
  M.catOrder=[]; M.catCollapsed=new Set(); M.catMembers=new Map(); M.catLabelOf=new Map();
  M.hiddenKinds=new Set(); M.analyzed=new Set(); M.running=new Set(); M.roles=new Map(); M.selected=null; M.tableDeps=new Map(); M.renderedIds=new Set();
  M._stateCache=new Map(); M._busyKeys=new Set(); M.colsByTable=new Map(); M.schemaProducts=new Map(); M.focusAdj=null;
  M.nodes.set(SCOPE+":big", { key:SCOPE+":big", label:"Schema", name:"big", fqn:"big", table_count:nTables });
  for (let i=0;i<nTables;i++){ const tk=`${SCOPE}:big.t${i}`; M.nodes.set(tk,{key:tk,label:"Table",name:"t"+i,fqn:"big.t"+i});
    for (let c=0;c<colsEach;c++){ const cf=`big.t${i}.c${c}`; M.nodes.set(`${SCOPE}:${cf}`,{key:`${SCOPE}:${cf}`,label:"Column",name:"c"+c,fqn:cf}); }
    M.colsByTable.set(tk, colsEach); }
  return M;
}
// vp: null=전체 커버(컬링 무효) / [x0,y0,x1,y1]=작은 model 창(컬링 활성)
function buildWith(zoom, vp) {
  const M = g.__M;
  M.graph = { getZoom:()=>zoom, getSize:()=>[1600,900],
    getCanvasByViewport: vp ? function(p){ return [ vp[0] + (p[0]/1600)*(vp[2]-vp[0]), vp[1] + (p[1]/900)*(vp[3]-vp[1]) ]; }
                            : function(p){ return [ p[0]*40, p[1]*40 ]; } };  // 전체 커버: 큰 model 창
  return g._metaG6Build();
}
const colNodes = (o) => o.nodes.filter(n=>n.data&&n.data.kind==="column").length;
const tblNodes = (o) => o.nodes.filter(n=>n.data&&n.data.kind==="table");
let pass=0, fail=0;
const check=(n,c,e)=>{ if(c){pass++;console.log("PASS",n);}else{fail++;console.log("FAIL",n,e===undefined?"":JSON.stringify(e));} };

// T1: 대형(30테이블×20컬럼=600컬럼, 630노드) — 작은 뷰포트 컬링 vs 전체 커버
{
  seed(30, 20);
  const full = buildWith(1.0, null);                 // 전체 커버 → 컬링 무효
  seed(30, 20);
  const cull = buildWith(1.0, [0,0,300,200]);        // 작은 창(model [0,0]-[300,200]) → 대부분 화면 밖
  check("T1 full 뷰포트 컬럼 전량 방출", colNodes(full) === 600, colNodes(full));
  check("T1 작은 뷰포트 컬럼 방출 급감(< full)", colNodes(cull) < colNodes(full), [colNodes(cull), colNodes(full)]);
  check("T1 화면 안 일부 컬럼은 방출(>0)", colNodes(cull) > 0, colNodes(cull));
  // §67: 테이블 컬링 — 작은 뷰포트는 화면 밖 테이블 칩도 미방출(< full 30, in-view 만). full 은 30 전량.
  check("T1 테이블 컬링 — full 30 / 작은 뷰포트 < 30(>0)", tblNodes(full).length === 30 && tblNodes(cull).length < 30 && tblNodes(cull).length > 0, [tblNodes(full).length, tblNodes(cull).length]);
}

// T2: 좌표 band-invariant — 컬링 여부와 무관하게 테이블 위치 동일(reflow 0)
{
  seed(30, 20);
  const full = buildWith(1.0, null);
  seed(30, 20);
  const cull = buildWith(1.0, [0,0,300,200]);
  const pf = new Map(tblNodes(full).map(n=>[n.id,[n.style.x,n.style.y]]));
  let moved=0, ex=null;
  tblNodes(cull).forEach(n=>{ const q=pf.get(n.id); if(!q||Math.abs(q[0]-n.style.x)>1e-6||Math.abs(q[1]-n.style.y)>1e-6){moved++;if(!ex)ex={id:n.id};} });
  check("T2 좌표 band-invariant(테이블 이동 0)", moved===0, ex);
}

// T3: 게이트 — 소형 모델(< 400 노드)은 작은 뷰포트여도 컬링 안 함
{
  seed(5, 10);   // 5테이블×10컬럼=50컬럼, ~56 노드 (<400)
  const out = buildWith(1.0, [0,0,300,200]);
  check("T3 소형 모델 컬링 안 함(컬럼 50 전량)", colNodes(out) === 50, colNodes(out));
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail?1:0);
