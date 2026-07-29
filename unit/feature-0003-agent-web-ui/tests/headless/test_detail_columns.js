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

// ── ⑦⑧ 보강 게이팅 — **부분 투영을 응답에서 알 수 없으므로 Table 은 항상 한 번 보강** ──────────
//   (graph-cols-partial, 사용자 리포트 2026-07-29 2차) 초판 게이트는 "컬럼 0 또는 truncated" 였는데
//   그것으로는 부분 투영을 못 잡았다 — 그래프 Column 정점은 `column_descriptions`(설명이 달린 컬럼만)
//   원천이라 55컬럼 테이블이 `HAS_COLUMN` 2 로 오고, 백엔드는 있는 걸 다 준 것이므로 `truncated` 도
//   false 다. 즉 "부분"이라는 사실이 응답 어디에도 없다(실측: cc_pyron.DT_Character_New = 2 vs 55).
{
  const s = newCtx();
  check("⑦ 컬럼 0 → 보강 필요", s._metaDetailColsBackfillNeeded(TABLE, { truncated: false }, 0) === true);
  check("⑦ 컬럼이 이미 있어도 보강한다(부분 투영은 응답으로 판별 불가)",
    s._metaDetailColsBackfillNeeded(TABLE, { truncated: false }, 2) === true);
  check("⑦ 컬럼 다수여도 동일 — 온전 여부를 프론트가 단정하지 않는다",
    s._metaDetailColsBackfillNeeded(TABLE, { truncated: false }, 75) === true);
  check("⑧ truncated 여도 물론 보강", s._metaDetailColsBackfillNeeded(TABLE, { truncated: true }, 12) === true);
  check("⑧ meta 부재도 보강(판별 신호 부재 = 보강)", s._metaDetailColsBackfillNeeded(TABLE, null, 12) === true);
}

// ── ⑦-b 반복 비용 억제는 **세션 1회 가드**가 담당한다(항상-보강의 전제) ──────────────────────
{
  const s = newCtx();
  check("⑦-b 첫 호출은 보강", s._metaDetailColsBackfillNeeded(TABLE, null, 2) === true);
  s._metaGraph.detailCols.set(TK, [col("A")]);
  check("⑦-b 캐시 적재 후에는 재조회 안 함", s._metaDetailColsBackfillNeeded(TABLE, null, 2) === false);
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

// ── ⑯ graph-cols-partial — 부분 투영 union + ordinal 보완(설명은 큐레이션 유지) ────────────────
{
  const s = newCtx();
  // 그래프에서 온 2개(설명 보유, ordinal 없음) + introspect 55개(ordinal 보유) 중 겹치는 2개.
  const fetched = [
    col("RespawnZoneID", { description: "부활 존 식별자(큐레이션)" }),
    col("LastPolymorphID", { description: "마지막 폴리모프(큐레이션)" }),
  ];
  s._metaGraph.detailCols.set(TK, [
    col("CharacterID", { ordinal: 1, description: "int" }),
    col("LastPolymorphID", { ordinal: 2, description: "int" }),
    col("RespawnZoneID", { ordinal: 3, description: "int" }),
    col("Level", { ordinal: 4, description: "tinyint" }),
  ]);
  const out = s._metaDetailMergeColumns(TABLE, fetched);
  check("⑯ 부분 투영이 introspect 전량으로 채워진다", out.length === 4, out.map((c) => c.name));
  check("⑯ 정렬이 실제 스키마 ordinal 순 — 그래프 컬럼도 ordinal 을 보완받는다",
    names(out).join(",") === "CharacterID,LastPolymorphID,RespawnZoneID,Level", names(out));
  const lp = out.find((c) => c.name === "LastPolymorphID");
  check("⑯ 큐레이션 설명은 자료형에 덮이지 않는다", lp.description === "마지막 폴리모프(큐레이션)", lp);
  check("⑯ 보완된 ordinal 이 실제로 실렸다", lp.ordinal === 2, lp);
}

// ── ⑰ 캔버스 펼침도 같은 정책 — 부분 투영에서 introspect 를 건너뛰지 않는다 ────────────────────
{
  // 주석에는 "종전 조건은 !respHasCols 였다" 는 서술이 남으므로, **코드 라인만** 보고 판정한다
  //   (주석까지 매칭하면 설명을 남긴 것만으로 FAIL 하는 오탐이 된다).
  const codeOnly = (s) => s.split("\n").filter((l) => !/^\s*(\/\/|\*|\/\*)/.test(l)).join("\n");
  const tog = codeOnly(grab(/\nasync function _metaGraphToggleColumns\([\s\S]*?\n\}\n/, "_metaGraphToggleColumns"));
  check("⑰ 캔버스 펼침이 respHasCols 로 introspect 를 건너뛰지 않는다", !/respHasCols/.test(tog));
  check("⑰ 캔버스 펼침의 재조회 억제는 세션 1회 가드", /!_metaGraph\.introspected\.has\(key\)/.test(tog));
  check("⑰ 캔버스 union 은 소문자 dedupe", /String\(x\.key \|\| ""\)\.toLowerCase\(\)/.test(tog));
  check("⑰ 캔버스 union 도 ordinal 을 보완", /prev\.ordinal == null && x\.ordinal != null/.test(tog));
  const exp = codeOnly(grab(/\nasync function _metaGraphExpand\([\s\S]*?\n\}\n/, "_metaGraphExpand"));
  check("⑰ 더블클릭 확장도 respHasCols/anchorHasCols 게이트를 쓰지 않는다",
    !/respHasCols/.test(exp) && !/anchorHasCols/.test(exp));
}

// ── ⑱ codex 적대리뷰 P1 — 부분 펼침에서 조기 return 이 보강을 가로막지 않는다 ──────────────────
//   그래프에 컬럼 2개만 있는 테이블은 그 2개가 렌더되는 순간 `colsByTable > 0` 이 되어, 종전
//   `if (_metaTableHasCols(key)) return;` 이 **함수 초입에서** 빠져나갔다 — 아래 introspect 보강 코드가
//   추가돼도 도달하지 못해 나머지 53개가 영영 오지 않는다(사용자 스크린샷이 정확히 이 상태).
{
  const codeOnly = (str) => str.split("\n").filter((l) => !/^\s*(\/\/|\*|\/\*)/.test(l)).join("\n");
  const tog = codeOnly(grab(/\nasync function _metaGraphToggleColumns\([\s\S]*?\n\}\n/, "_metaGraphToggleColumns"));
  check("⑱ 조기 return 이 hasCols 단독이 아니다(부분 펼침 통과)",
    !/if \(_metaTableHasCols\(key\)\) return;/.test(tog), tog.slice(0, 300));
  check("⑱ '완전히 펼쳐짐' = 컬럼 있음 AND introspect 보강 완료",
    /_metaTableHasCols\(key\)[\s\S]{0,120}introspected\.has\(key\)/.test(tog));
  check("⑱ 보강 실패 테이블도 no-op 대상(실패 왕복 반복 차단)",
    /introspectMiss\.has\(key\)/.test(tog));
  check("⑱ 실패 시 miss 를 기록한다", /introspectMiss\.add\(key\)/.test(tog));
  const state = fs.readFileSync(path.join(path.dirname(CTX), "graph-state.js"), "utf8");
  check("⑱ introspectMiss 가 상태에 선언돼 있다", /introspectMiss:/.test(state));
  const core = fs.readFileSync(path.join(path.dirname(CTX), "graph-core.js"), "utf8");
  const reset = core.match(/function _metaGraphResetModel\(\)[\s\S]*?\n\}/);
  check("⑱ 스코프 전환 시 miss 기록도 초기화(재시도 가능)",
    !!reset && /introspectMiss\.clear\(\)/.test(reset[0]));
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
