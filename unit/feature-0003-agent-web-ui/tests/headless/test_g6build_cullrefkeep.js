// §76 헤드리스 격리검증 — graph-cull-refkeep: 뷰포트 컬링은 draw(방출)만 줄이고 **참조(엣지)·상호작용
//   (상세 네비)** 은 보존. 불변식: ① 무선택 시 화면 밖 테이블은 컬링(기존 §67 유지) ② **선택 시 그 노드의
//   관계 상대(focusAdj)는 화면 밖이어도 방출**(exemption) → 관계선 렌더 + _metaRenderedIdFor 로 찾을 수 있어
//   상세 네비 동작 ③ 관계 상대 방출로 엣지(source·target 모두 present)가 살아남음 ④ 무선택 성능 무손실.
// 사용: node test_g6build_cullrefkeep.js <admin.js path>
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
// 2 스키마 × nT 테이블, A.t0.c0 → B.t0.c0 REFERENCES(컬럼-레벨 = 실제 끝점 형태). 모델 노드는 400 초과로 컬 게이트 통과.
function seed(nT) {
  const M = g.__M;
  M.nodes = new Map(); M.edges = new Map(); M.mode="roots"; M.loadedScope=SCOPE;
  M.schemaExpanded=new Set([SCOPE+":a", SCOPE+":b"]); M.schemaLoaded=new Set(); M.schemaLoading=new Set(); M.schemaTruncated=new Set(); M.schemaTotals=new Map();
  M.searchMatch=null; M.searchMatchTables=null; M.searchMatchNodes=null; M.searchCapped=false; M.searchAdded=new Set(); M.routineExpanded=new Set();
  M.clusterOffset=new Map(); M.nodePos=new Map(); M.groupOffset=new Map(); M.groupCollapsed=new Set(); M.groupMembers=new Map(); M.groupOf=new Map();
  M.clusterOrder=[]; M.tableOrder=new Map(); M.groupOrder=new Map(); M.groupTableOrder=new Map();
  M.catOrder=[]; M.catCollapsed=new Set(); M.catMembers=new Map(); M.catLabelOf=new Map();
  M.hiddenKinds=new Set(); M.analyzed=new Set(); M.running=new Set(); M.roles=new Map(); M.selected=null; M.tableDeps=new Map(); M.renderedIds=new Set();
  M._stateCache=new Map(); M._busyKeys=new Set(); M.colsByTable=new Map(); M.schemaProducts=new Map(); M.focusAdj=null;
  M._layoutSig=undefined; M._relOrderCache=null; M._simCache=undefined;
  ["a","b"].forEach((s) => {
    M.nodes.set(`${SCOPE}:${s}`, { key:`${SCOPE}:${s}`, label:"Schema", name:s, fqn:s, table_count:nT });
    for (let i=0;i<nT;i++){ const tk=`${SCOPE}:${s}.t${i}`; M.nodes.set(tk,{key:tk,label:"Table",name:"t"+i,fqn:`${s}.t${i}`}); M.colsByTable.set(tk, 6); }
  });
  // A.t0.c0 → B.t0.c0 (REFERENCES, 컬럼-레벨). 컬럼 노드는 모델에 없어도 renderEndpoint/colParent 가 테이블로 접음.
  M.edges.set("e0", { id:"e0", source:`${SCOPE}:a.t0.c0`, target:`${SCOPE}:b.t0.c0`, type:"REFERENCES", status:"trusted" });
  return M;
}
function buildWith(vp, selected) {   // vp=[mx0,my0,mx1,my1] 모델창(null=전체 커버=컬 무효) / selected=선택 키
  const M = g.__M;
  M.selected = selected || null;
  M.graph = { getZoom:()=>1.0, getSize:()=>[1600,900],
    getCanvasByViewport: vp ? function(p){ return [ vp[0] + (p[0]/1600)*(vp[2]-vp[0]), vp[1] + (p[1]/900)*(vp[3]-vp[1]) ]; }
                            : function(p){ return [ p[0]*40, p[1]*40 ]; } };
  return g._metaG6Build();
}
const tbl = (o) => o.nodes.filter(n=>n.data&&(n.data.kind==="table"||n.data.kind==="routine"));
const hasTbl = (o,key) => o.nodes.some(n=>n.id===key);
const edgeBetween = (o,ka,kb) => o.edges.some(e=>{
  const s=String(e.source), t=String(e.target);
  return (s.includes(ka)&&t.includes(kb))||(s.includes(kb)&&t.includes(ka));
});
let pass=0, fail=0;
const check=(n,c,e)=>{ if(c){pass++;console.log("PASS",n);}else{fail++;console.log("FAIL",n,e===undefined?"":JSON.stringify(e));} };

const A0 = `${SCOPE}:a.t0`, B0 = `${SCOPE}:b.t0`, BNO = `${SCOPE}:b.t5`;   // B.t5 = 화면 밖 + 무연결(컬링 대상)

// 전체 커버 build 로 A.t0 / B.t0 실제 위치 취득(결정론 좌표).
seed(210);
const full = buildWith(null, null);
const posOf = (key) => { const n = full.nodes.find(x=>x.id===key); return n && n.style ? [n.style.x, n.style.y] : null; };
const pa = posOf(A0), pb = posOf(B0);
check("사전: A.t0·B.t0 위치 취득 + 이격(컬 창 분리 가능)", pa && pb && (Math.abs(pa[0]-pb[0])>400 || Math.abs(pa[1]-pb[1])>400), {pa,pb});

// A.t0 를 덮되 B 스키마는 제외하는 작은 모델창(A.t0 중심 ±260×±160).
const vpA = [pa[0]-260, pa[1]-160, pa[0]+260, pa[1]+160];

// T1: 무선택 + **뷰포트 내 노드 엣지 컬링무효** — A.t0(창 안)에 연결된 B.t0 은 창 밖이어도 엣지 예외로 방출·관계선 렌더.
//   반면 무연결 B.t5 는 창 밖이라 컬링(컬링 자체는 유효).
{
  seed(210);
  const out = buildWith(vpA, null);
  check("T1 A.t0 방출(창 안)", hasTbl(out, A0), null);
  check("T1 B.t0 방출(엣지 예외 — A.t0 연결·화면 밖이어도)", hasTbl(out, B0), null);
  check("T1 A.t0↔B.t0 관계선 렌더(참조 보존)", edgeBetween(out, A0, B0), null);
  check("T1 무연결 B.t5 컬링(창 밖·엣지 없음)", !hasTbl(out, BNO), null);
  check("T1 _edgeExempt 에 B.t0 포함(근거)", !!(g.__M._edgeExempt && g.__M._edgeExempt.has(B0)), null);
}

// T2: A.t0 선택 — focusAdj 예외로도 B.t0 방출(엣지 예외와 중복이나 선택-오프스크린 케이스 커버).
{
  seed(210);
  const out = buildWith(vpA, A0);
  check("T2 선택: A.t0·B.t0 방출 + 관계선 렌더", hasTbl(out, A0) && hasTbl(out, B0) && edgeBetween(out, A0, B0), null);
  check("T2 focusAdj.nodes 에 B.t0 포함", !!(g.__M.focusAdj && g.__M.focusAdj.nodes.has(B0)), null);
}

// T3: 컬링 유효 — 무연결 대량 B 테이블은 창 밖이라 방출 안 됨(방출 수 << 전체 420) + nodePosAll 은 전체 포함(미니맵용).
{
  seed(210);
  const culled = buildWith(vpA, null);
  check("T3 컬링 유효(방출 테이블 << 전체 420)", tbl(culled).length < 100 && tbl(culled).length > 0, tbl(culled).length);
  check("T3 nodePosAll 전체 포함(컬링돼도 — 미니맵용)", g.__M.nodePosAll && g.__M.nodePosAll.size >= 420, g.__M.nodePosAll ? g.__M.nodePosAll.size : 0);
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail?1:0);
