// graph-detail-cols 헤드리스 결정론 검증 — 그래프 뷰 **상세 패널의 컬럼 목록**이 캔버스와 정합하는지.
//
// 사용자 리포트(2026-07-29): "테이블 내 포함된 컬럼이 상세 패널에서는 출력되지 않거나 일부 누락된다".
// 근본 원인은 컬럼 소스의 비대칭이었다 — 그래프 Column 정점의 SSOT 는 `column_descriptions`(큐레이션·
// 분석된 컬럼만)이라 미큐레이션 테이블은 HAS_COLUMN 이 0 인데(라이브 실측: Table 18,257 / 컬럼 정점을
// 가진 테이블 7,320 / HAS_COLUMN 13,873 = 테이블당 평균 1.9), 캔버스 펼침·더블클릭 확장은 그 공백을
// `/graph/columns` 즉석 introspect 로 메우는 반면 단일클릭 상세에는 그 폴백이 없었다. 그래서 같은 화면
// 에서 캔버스엔 컬럼 40개가 펼쳐져 있는데 패널엔 '컬럼' 섹션 자체가 없었다.
//
// 실제 렌더/이벤트는 PixiJS·DOM 의존이라 라이브 육안은 PB-0008 이 담당한다. 여기서는 graph-ctxmenu.js
// 소스에서 검증 대상 유닛의 **본문을 그대로 추출**해(사본 아님) 의존을 test double 로 주입하고, 병합
// 규칙(3-소스 union · case-insensitive dedupe · 우선순위 · 정렬)과 보강 게이팅(0건/절단/1회 제한)을
// 결정론적으로 검증한다.
//
// 사용: node test_detail_columns.js [<graph-ctxmenu.js path>]
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const CTX = process.argv[2] || path.join(__dirname, "..", "..", "src", "static", "graph", "graph-ctxmenu.js");
const src = fs.readFileSync(CTX, "utf8");

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra).slice(0, 300)); }
}

function grab(re, label) {
  const m = src.match(re);
  if (!m) { console.error(`FAIL: graph-ctxmenu.js 에서 ${label} 추출 실패 — 함수명/형식 변경?`); process.exit(1); }
  return m[0];
}
const fnMerge = grab(/\nfunction _metaDetailMergeColumns\([\s\S]*?\n\}\n/, "_metaDetailMergeColumns");
const fnNeed = grab(/\nfunction _metaDetailColsBackfillNeeded\([\s\S]*?\n\}\n/, "_metaDetailColsBackfillNeeded");
const fnColCmp = grab(/\nfunction _metaGraphColCmp\([\s\S]*?\n\}\n/, "_metaGraphColCmp");
const fnColParent = grab(/\nfunction _metaColParent\([\s\S]*?\n\}\n/, "_metaColParent");

function newCtx(state) {
  const sandbox = {
    console,
    _metaGraph: Object.assign({
      nodes: new Map(),
      detailCols: new Map(),
      detailColsMiss: new Map(),
      detailColsInflight: new Set(),
    }, state || {}),
  };
  vm.createContext(sandbox);
  vm.runInContext([fnColParent, fnColCmp, fnMerge, fnNeed].join("\n"), sandbox, { filename: "detailcols-unit.js" });
  return sandbox;
}

const TK = "mssql-ds1:cc_pyron.DT_ItemEnchantInfo";
const TABLE = { key: TK, label: "Table", name: "DT_ItemEnchantInfo", fqn: "cc_pyron.DT_ItemEnchantInfo" };
const col = (name, over) => Object.assign({
  key: `${TK}.${name}`, label: "Column", name,
  fqn: `cc_pyron.DT_ItemEnchantInfo.${name}`,
}, over || {});
const names = (arr) => arr.map((c) => c.name);

// ── ① 그래프 미투영(HAS_COLUMN 0) + 캔버스가 introspect 로 펼쳐둔 컬럼 → 패널에도 전량 ──────────
{
  const s = newCtx();
  // 캔버스 펼침이 모델에 넣어둔 컬럼(_metaGraphToggleColumns 의 introspect 산출).
  [col("UniqueID", { ordinal: 1 }), col("SocketNum", { ordinal: 2 }), col("EnchantType", { ordinal: 3 })]
    .forEach((c) => s._metaGraph.nodes.set(c.key, c));
  // 다른 테이블 컬럼 — 병합 대상이 아니어야 한다(부모 판정).
  s._metaGraph.nodes.set("mssql-ds1:cc_pyron.OtherTable.Foo",
    { key: "mssql-ds1:cc_pyron.OtherTable.Foo", label: "Column", name: "Foo", fqn: "cc_pyron.OtherTable.Foo" });
  const out = s._metaDetailMergeColumns(TABLE, []);   // fetch 응답엔 HAS_COLUMN 0 (사용자 리포트 상황)
  check("① 모델 병합 — 캔버스에 펼쳐진 컬럼이 패널에도 전량 나온다",
    names(out).join(",") === "UniqueID,SocketNum,EnchantType", names(out));
  check("① 다른 테이블 컬럼은 섞이지 않는다", out.every((c) => c.name !== "Foo"), names(out));
}

// ── ② 상세 전용 introspect 캐시(detailCols) 병합 ─────────────────────────────────────────────
{
  const s = newCtx();
  s._metaGraph.detailCols.set(TK, [col("A", { ordinal: 1 }), col("B", { ordinal: 2 })]);
  const out = s._metaDetailMergeColumns(TABLE, []);
  check("② introspect 캐시가 비어 있던 패널을 채운다", names(out).join(",") === "A,B", names(out));
}

// ── ③ 3-소스 union + 우선순위(fetch 레코드의 큐레이션 설명이 introspect 자료형에 덮이지 않음) ─────
{
  const s = newCtx();
  const fetched = [col("UniqueID", { ordinal: 1, description: "고유 식별자(큐레이션)" })];
  s._metaGraph.nodes.set(`${TK}.SocketNum`, col("SocketNum", { ordinal: 2, description: "int" }));
  s._metaGraph.detailCols.set(TK, [
    col("UniqueID", { ordinal: 1, description: "bigint" }),   // 중복 — fetch 레코드가 이겨야 한다
    col("EnchantType", { ordinal: 3, description: "tinyint" }),
  ]);
  const out = s._metaDetailMergeColumns(TABLE, fetched);
  check("③ 3-소스 union", names(out).join(",") === "UniqueID,SocketNum,EnchantType", names(out));
  check("③ 중복은 앞선 소스(그래프 SSOT) 레코드를 유지 — 큐레이션 설명 보존",
    out[0].description === "고유 식별자(큐레이션)", out[0]);
}

// ── ④ case-insensitive dedupe — 큐레이션 원천 vs information_schema 원천의 식별자 case drift ────
{
  const s = newCtx();
  const fetched = [col("UniqueID", { ordinal: 1 })];
  s._metaGraph.detailCols.set(TK, [
    Object.assign(col("uniqueid"), { key: `${TK}.uniqueid`, ordinal: 1 }),   // 같은 컬럼, 케이스만 다름
    col("SocketNum", { ordinal: 2 }),
  ]);
  const out = s._metaDetailMergeColumns(TABLE, fetched);
  check("④ 케이스만 다른 같은 컬럼은 한 줄로 합쳐진다",
    out.length === 2 && names(out).join(",") === "UniqueID,SocketNum", names(out));
}

// ── ⑤ 정렬 — ordinal 우선, 부재는 후미(이름순). ERD 컬럼 순서와 정합 ─────────────────────────
{
  const s = newCtx();
  s._metaGraph.detailCols.set(TK, [
    col("Zeta"),                       // ordinal 없음 → 후미
    col("Second", { ordinal: 2 }),
    col("Alpha"),                      // ordinal 없음 → 후미(이름순으로 Zeta 앞)
    col("First", { ordinal: 1 }),
  ]);
  const out = s._metaDetailMergeColumns(TABLE, []);
  check("⑤ ordinal 정렬 + ordinal 부재는 후미 이름순",
    names(out).join(",") === "First,Second,Alpha,Zeta", names(out));
}

// ── ⑥ Table 이 아닌 self 는 병합하지 않는다(Column/Routine/Schema 상세 무영향) ─────────────────
{
  const s = newCtx();
  s._metaGraph.nodes.set(`${TK}.UniqueID`, col("UniqueID", { ordinal: 1 }));
  const colSelf = { key: `${TK}.UniqueID`, label: "Column", name: "UniqueID" };
  const out = s._metaDetailMergeColumns(colSelf, []);
  check("⑥ Column 상세는 컬럼 병합 no-op", out.length === 0, out);
  const routineSelf = { key: "mssql-ds1:cc_pyron.usp_Foo", label: "Routine", name: "usp_Foo" };
  check("⑥ Routine 상세도 no-op", s._metaDetailMergeColumns(routineSelf, []).length === 0);
}

// ── ⑦ 보강 게이팅 — 컬럼 0 이면 introspect 보강이 필요하다(주 증상) ──────────────────────────
{
  const s = newCtx();
  check("⑦ 컬럼 0 → 보강 필요", s._metaDetailColsBackfillNeeded(TABLE, { truncated: false }, 0) === true);
  check("⑦ 컬럼 있음 + 절단 없음 → 보강 불필요(이미 온전)",
    s._metaDetailColsBackfillNeeded(TABLE, { truncated: false }, 12) === false);
}

// ── ⑧ 보강 게이팅 — 백엔드 이웃 절단 신고면 컬럼이 있어도 부분이므로 보강('일부 누락' 축) ────────
{
  const s = newCtx();
  check("⑧ truncated → 컬럼이 있어도 보강",
    s._metaDetailColsBackfillNeeded(TABLE, { truncated: true }, 12) === true);
  check("⑧ meta 부재는 절단 아님으로 본다",
    s._metaDetailColsBackfillNeeded(TABLE, null, 12) === false);
}

// ── ⑨ 보강 게이팅 — 세션 내 1회 제한(렌더↔보강 무한 루프 차단) ────────────────────────────────
{
  const s = newCtx();
  s._metaGraph.detailCols.set(TK, [col("A")]);
  check("⑨ 캐시 적중이면 재조회 안 함(보강 결과가 부른 재렌더에서 루프 차단)",
    s._metaDetailColsBackfillNeeded(TABLE, { truncated: true }, 1) === false);

  const s2 = newCtx();
  s2._metaGraph.detailColsMiss.set(TK, "데이터소스 컬럼 조회 실패");
  check("⑨ 실패 기록이 있으면 재조회 안 함",
    s2._metaDetailColsBackfillNeeded(TABLE, null, 0) === false);

  const s3 = newCtx();
  s3._metaGraph.detailColsInflight.add(TK);
  check("⑨ in-flight 중이면 중복 요청 안 함",
    s3._metaDetailColsBackfillNeeded(TABLE, null, 0) === false);
}

// ── ⑩ 보강 게이팅 — Table 이 아니거나 key 가 없으면 대상 아님 ────────────────────────────────
{
  const s = newCtx();
  check("⑩ Column self 는 보강 대상 아님",
    s._metaDetailColsBackfillNeeded({ key: "k", label: "Column" }, null, 0) === false);
  check("⑩ key 없는 self 는 보강 대상 아님",
    s._metaDetailColsBackfillNeeded({ label: "Table" }, null, 0) === false);
  check("⑩ self 부재 방어", s._metaDetailColsBackfillNeeded(null, null, 0) === false);
}

// ── ⑪ 호출부 계약 — 렌더가 병합·보강을 실제로 호출하는지(유닛만 PASS 하는 사각 방지) ────────────
{
  check("⑪ 렌더가 _metaDetailMergeColumns 를 호출한다",
    /_metaDetailMergeColumns\(self, columns\)/.test(src));
  check("⑪ 렌더가 컬럼 수·렌더 세대를 실어 보강을 호출한다",
    /_metaGraphDetailColsBackfill\(self, nodes, edges, meta, columns\.length, _detailGen\)/.test(src));
  check("⑪ 보강은 공용 게이트를 통과한 뒤에만 fetch 한다",
    /if \(!_metaDetailColsBackfillNeeded\(self, meta, colCount\)\) return;/.test(src));
  // 모델 무오염 계약: 보강 경로가 _metaGraphIngest 로 캔버스 모델을 건드리면 펼치지 않은 테이블의
  //   컬럼이 다음 rebuild 에서 캔버스에 튀어나온다.
  const bf = grab(/\nasync function _metaGraphDetailColsBackfill\([\s\S]*?\n\}\n/, "_metaGraphDetailColsBackfill");
  check("⑪ 보강은 모델(_metaGraphIngest)을 건드리지 않는다 — 캔버스 구조 불변",
    !/_metaGraphIngest/.test(bf), bf.slice(0, 200));
  check("⑪ 보강 결과는 상세 전용 캐시에만 적재", /_metaGraph\.detailCols\.set\(key,/.test(bf));
  check("⑪ 다른 노드로 이동했으면 재렌더하지 않는다(stale 방지)",
    /_metaGraph\.lastDetailKey !== key/.test(bf));
  check("⑪ in-flight 표식은 finally 로 해제(예외 시 영구 잠김 방지)",
    /finally \{\s*_metaGraph\.detailColsInflight\.delete\(key\);/.test(bf));
}

// ── ⑫ Table 상세는 컬럼 0 이어도 섹션을 렌더한다(빈 화면이 결함/사실을 구분 못 하던 문제) ────────
{
  check("⑫ 컬럼 섹션 게이트에 Table 이 포함된다",
    /if \(columns\.length \|\| selfIsColumn \|\| self\.label === "Table"\)/.test(src));
  check("⑫ 빈 목록은 조회 중/실패 사유를 말한다",
    /_metaGraph\.detailColsMiss\.get\(selfKey\)[\s\S]{0,200}컬럼 조회 중…/.test(src));
}

// ── ⑭ codex 적대리뷰 P2-1 — 보강 실패도 재렌더해야 "컬럼 조회 중…" 고착이 안 생긴다 ────────────
{
  const bf = grab(/\nasync function _metaGraphDetailColsBackfill\([\s\S]*?\n\}\n/, "_metaGraphDetailColsBackfill");
  // 실패 분기(miss 기록) 뒤에 곧바로 return 하면 패널이 "조회 중…" 에 영구 고착된다 — 성공·실패가
  //   같은 재렌더 경로로 합류해야 한다. miss 기록 라인과 재렌더 사이에 조기 return 이 없어야 한다.
  const missIdx = bf.indexOf("detailColsMiss.set");
  const renderIdx = bf.lastIndexOf("_metaGraphRenderDetail(");
  check("⑭ 실패 기록 후에도 재렌더 경로로 합류한다", missIdx >= 0 && renderIdx > missIdx, { missIdx, renderIdx });
  const between = bf.slice(missIdx, renderIdx);
  // 세대·키 가드의 return 은 정당하다. 그 외에 '무조건 return' 이 끼면 실패 경로가 다시 끊긴다.
  const bareReturns = between.split("\n").filter((l) => /^\s*return;\s*$/.test(l));
  check("⑭ 실패→재렌더 사이의 return 은 전부 가드 조건부(무조건 return 없음)",
    bareReturns.length === 0, bareReturns);
  check("⑭ catch 절도 return 없이 재렌더로 흐른다", !/catch \(_\) \{[^}]*return;[^}]*\}/.test(bf));
}

// ── ⑮ codex 적대리뷰 P2-2 — 같은 키 재선택 race 를 렌더 세대로 차단 ──────────────────────────
{
  const bf = grab(/\nasync function _metaGraphDetailColsBackfill\([\s\S]*?\n\}\n/, "_metaGraphDetailColsBackfill");
  check("⑮ 보강은 렌더 세대(gen)를 인자로 받는다", /_metaGraphDetailColsBackfill\(self, nodes, edges, meta, colCount, gen\)/.test(bf));
  check("⑮ 렌더 세대가 바뀌었으면 폐기(같은 키 재선택 race)", /_metaGraph\._detailSeq !== gen/.test(bf));
  check("⑮ 모델 세대(_opSeq)도 함께 대조(스코프 전환·리셋 중 도착)", /_metaGraph\._opSeq !== opSeq/.test(bf));
  check("⑮ 모델 세대는 fetch **이전**에 캡처한다", /const opSeq = _metaGraph\._opSeq;[\s\S]*?await apiFetch/.test(bf));
  // 렌더 쪽 계약: 매 렌더가 세대를 올리고, 그 세대를 보강에 넘긴다.
  check("⑮ 렌더가 세대를 증가시킨다", /_metaGraph\._detailSeq = \(_metaGraph\._detailSeq \|\| 0\) \+ 1/.test(src));
  check("⑮ 렌더가 그 세대를 보강에 전달한다",
    /_metaGraphDetailColsBackfill\(self, nodes, edges, meta, columns\.length, _detailGen\)/.test(src));
  const state = fs.readFileSync(path.join(path.dirname(CTX), "graph-state.js"), "utf8");
  check("⑮ _detailSeq 가 상태에 선언돼 있다", /_detailSeq: 0/.test(state));
}

// ── ⑬ 모델 교체(스코프 전환) 시 상세 캐시도 함께 비운다 ──────────────────────────────────────
{
  const core = fs.readFileSync(path.join(path.dirname(CTX), "graph-core.js"), "utf8");
  const reset = core.match(/function _metaGraphResetModel\(\)[\s\S]*?\n\}/);
  check("⑬ resetModel 이 detailCols/Miss/Inflight 를 clear 한다",
    !!reset && /detailCols\.clear\(\)/.test(reset[0]) && /detailColsMiss\.clear\(\)/.test(reset[0])
      && /detailColsInflight\.clear\(\)/.test(reset[0]));
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
