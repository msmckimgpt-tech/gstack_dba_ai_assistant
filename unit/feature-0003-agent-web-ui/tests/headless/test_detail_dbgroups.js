// detail-db-groups 헤드리스 결정론 검증 — 상세 패널의 **관련 노드 목록**을 소속 DB(스키마) 단위로
//   묶어 접기/펼치기 하고, 종전의 "… 외 N건" 조용한 절단을 제거했는지 확인한다.
//   사용자 요구(2026-07-27): ① 관련 노드를 DB 단위로 접기/펼치기 ② 목록이 생략되지 않게.
//
// 실제 렌더/이벤트는 PixiJS·DOM 의존이라 라이브 육안은 PB-0008 이 담당한다. 여기서는 graph-ctxmenu.js
// 소스에서 관련 유닛의 **본문을 그대로 추출**해(사본 아님) 의존을 test double 로 주입하고, 그룹 구획·
// 기본 펼침 규칙·lazy 주입·절단 부재·호출부 인자 매핑을 결정론적으로 검증한다. ES-module import
// 리팩터(ITEM-09) 이후 파일 전체 vm-eval 은 불가하므로 유닛만 격리 실행한다.
//
// §18.8 적대 리뷰(2026-07-27) 반영: 초판 스위트는 (a) 호출부(dirRowsHTML)를 전혀 실행하지 않아 인자
// 순서를 뒤집어도 전건 PASS 했고, (b) ROW_CAP 예산 경로·(c) '모두 펼치기'·(d) 형제 동기화·(e) 컬럼
// 아코디언 lazy 를 커버하지 않았다. 아래 ⑪~⑯ 이 그 사각을 덮는다.
// 사용: node test_detail_dbgroups.js [<graph-ctxmenu.js path>]
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

// ── 소스에서 검증 대상 유닛 추출 ────────────────────────────────────────────────
function grab(re, label) {
  const m = src.match(re);
  if (!m) { console.error(`FAIL: graph-ctxmenu.js 에서 ${label} 추출 실패 — 함수명/형식 변경?`); process.exit(1); }
  return m[0];
}
const constText = grab(/const _META_DBGRP_ROW_CAP = \d+;[\s\S]*?let _metaDbGrpSeq = 0;/, "DB 그룹 상수");
const labelsText = grab(/const _META_DBGRP_LABELS = \{[^}]*\};/, "_META_DBGRP_LABELS");
const fnKeyOf = grab(/\nfunction _metaDbGroupKeyOf\([\s\S]*?\n\}\n/, "_metaDbGroupKeyOf");
const fnOpen = grab(/\nfunction _metaDbGroupOpen\([\s\S]*?\n\}\n/, "_metaDbGroupOpen");
const fnRows = grab(/\nfunction _metaDbGroupedRowsHTML\([\s\S]*?\n\}\n/, "_metaDbGroupedRowsHTML");
const fnToggle = grab(/\nfunction _metaToggleDbGroup\([\s\S]*?\n\}\n/, "_metaToggleDbGroup");
const fnSyncAll = grab(/\nfunction _metaSyncDbGrpAllLabel\([\s\S]*?\n\}\n/, "_metaSyncDbGrpAllLabel");
const fnColLazy = grab(/\nfunction _metaColBodyLazy\([\s\S]*?\n\}\n/, "_metaColBodyLazy");
const fnColReveal = grab(/\nfunction _metaColBodyReveal\([\s\S]*?\n\}\n/, "_metaColBodyReveal");
const fnTrunc = grab(/\nfunction _metaDbGrpTruncNotice\([\s\S]*?\n\}\n/, "_metaDbGrpTruncNotice");
// 호출부: 관계 상세의 방향 그룹 조립(인자 매핑 회귀 방지 — 리뷰 지적).
const fnDirRows = grab(/const dirRowsHTML = \(list, dir\) => _metaDbGroupedRowsHTML\([\s\S]*?\n  \);/, "dirRowsHTML");

// key(`scope:fqn`) → 소속 스키마 `scope:db` (graph-core._metaCatParent 와 동형 — 테스트 격리 재현)
function catParent(key, fqn) {
  if (!key) return null;
  const i = key.indexOf(":"); if (i < 0) return null;
  const f = fqn || key.slice(i + 1);
  if (!f || f.indexOf(".") < 0) return null;
  return key.slice(0, i) + ":" + f.split(".")[0];
}

function newCtx(stateOverrides) {
  const sandbox = {
    console,
    _metaGraph: Object.assign({ panelDbGroupState: new Map(), nodes: new Map() }, stateOverrides || {}),
    _metaCatParent: catParent,
    _metaComboName: (id) => { const i = String(id).indexOf(":"); return i >= 0 ? String(id).slice(i + 1) : String(id); },
    _metaNatSort: (a, b) => String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" }),
    // 컬럼 lazy payload 의 bind 가 호출하는 실 바인딩들 — 호출 횟수만 센다.
    _binds: { trace: 0, hover: 0, dbgrp: 0 },
    _metaGraphBindTraceRows: () => { sandbox._binds.trace++; },
    _metaGraphBindDetailHover: () => { sandbox._binds.hover++; },
    _metaBindDbGroups: () => { sandbox._binds.dbgrp++; },
  };
  vm.createContext(sandbox);
  vm.runInContext([constText, labelsText, fnKeyOf, fnOpen, fnRows, fnToggle, fnSyncAll, fnColLazy, fnColReveal, fnTrunc]
    .join("\n"), sandbox, { filename: "dbgroups-unit.js" });
  // const 선언은 sandbox 전역 객체 속성으로 노출되지 않으므로(함수 선언과 달리) 명시 평가로 참조를 얻는다.
  sandbox.lazy = vm.runInContext("_metaDbGrpLazy", sandbox);
  sandbox.CAP = vm.runInContext("_META_DBGRP_ROW_CAP", sandbox);
  sandbox.FLAT = vm.runInContext("_META_DBGRP_FLAT_MAX", sandbox);
  sandbox.BIG = vm.runInContext("_META_DBGRP_BIG", sandbox);
  return sandbox;
}

const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const mkItems = (scope, db, n, prefix) => Array.from({ length: n }, (_, i) => {
  const key = `${scope}:${db}.${prefix}${i}`;
  return { key, fqn: `${db}.${prefix}${i}`, label: "Table", html: `<li data-k="${key}">${prefix}${i}</li>` };
});
const countRows = (html) => (html.match(/<li data-k=/g) || []).length;
const headKeys = (html) => [...html.matchAll(/data-dbgrp-key="([^"]*)"/g)].map((m) => m[1]);

// ── 최소 DOM stub(머리글/본문/루트) — 토글 왕복·형제 동기화 검증용 ──────────────────
function mkHead(gid, gkey, setId, collapsed) {
  const cls = new Set(["amgr-ct-group", "amgr-dbgrp"]);
  if (collapsed) cls.add("is-collapsed");
  const attr = { "data-dbgrp": gid, "data-dbgrp-key": gkey, "data-dbgrp-set": setId, "aria-expanded": String(!collapsed) };
  return {
    _cls: cls, _attr: attr,
    classList: { contains: (c) => cls.has(c), toggle: (c, on) => { if (on) cls.add(c); else cls.delete(c); } },
    getAttribute: (k) => (k in attr ? attr[k] : null),
    setAttribute: (k, v) => { attr[k] = v; },
    querySelector: () => ({ textContent: "" }),
  };
}
function mkBody(gid) {
  const ul = { innerHTML: "", get firstChild() { return this.innerHTML ? {} : null; } };
  return { gid, hidden: true, querySelector: () => ul, _ul: ul };
}
function mkRoot(pairs, allBtn) {   // pairs: [{head, body}]
  return {
    querySelector: (sel) => {
      const mBody = sel.match(/data-dbgrp-body="([^"]+)"/);
      if (mBody) { const p = pairs.find((x) => x.body.gid === mBody[1]); return p ? p.body : null; }
      if (sel.includes("amgr-dbgrp-all")) return allBtn || null;
      return null;
    },
    querySelectorAll: (sel) => {
      if (sel.includes("amgr-dbgrp-all")) return allBtn ? [allBtn] : [];
      if (sel.includes("data-dbgrp-set")) {
        const m = sel.match(/data-dbgrp-set="([^"]+)"/);
        return pairs.filter((p) => !m || p.head.getAttribute("data-dbgrp-set") === m[1]).map((p) => p.head);
      }
      if (sel.includes("data-dbgrp-key")) return pairs.map((p) => p.head);
      return [];
    },
  };
}

// ── ① 단일 DB + 짧은 목록(≤ FLAT_MAX) → 머리글 없이 평면(기존 UX 유지) ──────────────────
{
  const g = newCtx();
  const html = g._metaDbGroupedRowsHTML(mkItems("ds1", "shopdb", 5, "p"), { selfDbKey: "ds1:shopdb", esc });
  check("① 단일 DB 짧은 목록 = 평면(머리글 없음)", !html.includes("amgr-dbgrp") && countRows(html) === 5, html.slice(0, 200));
}

// ── ② 다중 DB + 소량(총 ≤ FLAT_MAX) → 머리글은 만들되 **전 그룹 펼침**(리뷰 B1) ─────────────
{
  const g = newCtx();
  const items = [...mkItems("ds1", "shopdb", 3, "a"), ...mkItems("ds1", "logdb", 4, "b")];
  const html = g._metaDbGroupedRowsHTML(items, { selfDbKey: "ds1:shopdb", esc });
  check("② DB 머리글 2개 생성", headKeys(html).length === 2, headKeys(html));
  check("② self DB(shopdb) 가 첫 그룹", headKeys(html)[0] === "ds1:shopdb", headKeys(html));
  check("② 소량 목록은 전 그룹 펼침(행 7 전량 — 종전보다 덜 보이는 퇴행 없음)", countRows(html) === 7, { rows: countRows(html) });
  check("② 접힌 그룹 0 → lazy payload 없음", g.lazy.size === 0, g.lazy.size);
}

// ── ③ self DB 그룹이 없어도 최소 한 그룹은 펼친다(리뷰 B1 — 빈 화면 금지) ──────────────────
{
  const g = newCtx();
  const items = [...mkItems("ds1", "adb", 100, "a"), ...mkItems("ds1", "bdb", 100, "b")];   // 총 200 > FLAT
  const html = g._metaDbGroupedRowsHTML(items, { selfDbKey: "ds1:shopdb", esc });   // self 그룹 부재
  check("③ self 그룹 부재 + 총량 큼 → 첫 그룹만 펼침(행 100, 0행 아님)", countRows(html) === 100, { rows: countRows(html) });
  check("③ 나머지 그룹은 lazy", g.lazy.size === 1, g.lazy.size);
}

// ── ④ 절단 부재 — 종전 상한(30·60) 초과에도 "외 N건" 없이 전량 ────────────────────────────
{
  const g = newCtx();
  const items = mkItems("ds1", "shopdb", 120, "p");   // 종전 규약이면 30 또는 60 에서 잘렸다
  const html = g._metaDbGroupedRowsHTML(items, { selfDbKey: "ds1:shopdb", esc });
  check("④ '… 외 N건' 절단 표기 없음", !/… 외 \d+건/.test(html), html.slice(0, 200));
  check("④ 머리글 개수 = 실제 총계(120)", html.includes('<span class="amgr-ct-group-n">120</span>'));
  check("④ 펼친 그룹은 전량 렌더(120행)", countRows(html) === 120, { rows: countRows(html) });
  check("④ 단일 DB 라도 길면 머리글 생성(접기 진입점)", html.includes("amgr-dbgrp"));
}

// ── ⑤ 대형 그룹(> BIG)은 기본 접힘 + lazy(초기 DOM 폭주 방지), 총계는 정직 ────────────────
{
  const g = newCtx();
  const html = g._metaDbGroupedRowsHTML(mkItems("ds1", "shopdb", g.BIG + 1, "p"), { selfDbKey: "ds1:shopdb", esc });
  check("⑤ 대형 self DB 그룹 기본 접힘", html.includes('aria-expanded="false"'), html.slice(0, 200));
  check("⑤ 초기 렌더 행 0(lazy)", countRows(html) === 0, { rows: countRows(html) });
  check("⑤ 머리글 총계는 실제값으로 정직", html.includes(`<span class="amgr-ct-group-n">${g.BIG + 1}</span>`));
  const pend = [...g.lazy.values()][0];
  check("⑤ lazy payload 에 전량 보관", pend && countRows(pend.html) === g.BIG + 1, pend ? countRows(pend.html) : null);
}

// ── ⑥ 사용자 조작 상태가 기본 규칙을 이긴다(단 대형 그룹은 성능 가드가 우선 — 리뷰 M2) ────────
{
  const g = newCtx();
  g._metaGraph.panelDbGroupState.set("ds1:logdb", true);
  g._metaGraph.panelDbGroupState.set("ds1:shopdb", false);
  const items = [...mkItems("ds1", "shopdb", 100, "a"), ...mkItems("ds1", "logdb", 100, "b")];   // 총 200 > FLAT
  const html = g._metaDbGroupedRowsHTML(items, { selfDbKey: "ds1:shopdb", esc });
  const seg = html.split('data-dbgrp-key="ds1:logdb"');
  check("⑥ 사용자가 접은 self DB = 접힘(행 0)", countRows(seg[0]) === 0, { rows: countRows(seg[0]) });
  check("⑥ 사용자가 펼친 타 DB = 펼침(행 100)", countRows(seg[1] || "") === 100, { rows: countRows(seg[1] || "") });

  const g2 = newCtx();
  g2._metaGraph.panelDbGroupState.set("ds1:bigdb", true);   // 사용자가 펼쳐둔 대형 그룹
  const h2 = g2._metaDbGroupedRowsHTML(mkItems("ds1", "bigdb", g2.BIG + 500, "p"), { selfDbKey: "ds1:bigdb", esc });
  check("⑥ 대형 그룹은 사용자 기록보다 성능 가드 우선(초기 0행)", countRows(h2) === 0, { rows: countRows(h2) });
}

// ── ⑦ ROW_CAP 예산은 **펼친 그룹만** 소비한다(리뷰 B2 — 접힘이 예산을 먹어 빈 목록 되는 무음 실패) ──
{
  const g = newCtx();
  const items = [...mkItems("ds1", "adb", g.CAP + 100, "a"), ...mkItems("ds1", "zdb", 50, "z")];
  const html = g._metaDbGroupedRowsHTML(items, { selfDbKey: "ds1:adb", esc });
  const pends = [...g.lazy.values()].map((p) => countRows(p.html));
  check("⑦ 두 그룹 모두 접힘(대형·비-self)", countRows(html) === 0 && g.lazy.size === 2, { rows: countRows(html), lazy: g.lazy.size });
  check("⑦ 접힌 대형 그룹이 예산을 먹지 않아 뒤 그룹 payload 온전(50행)", pends.includes(50), pends);
  check("⑦ 접힌 그룹 payload 는 전량 보관", pends.includes(g.CAP + 100), pends);
}

// ── ⑧ '모두 펼치기/접기' 컨트롤(리뷰 M3 — 그룹 수만큼 클릭하던 마찰·상태 고착의 탈출로) ────────
{
  const g = newCtx();
  const items = [...mkItems("ds1", "adb", 100, "a"), ...mkItems("ds1", "bdb", 100, "b")];
  const html = g._metaDbGroupedRowsHTML(items, { selfDbKey: "ds1:adb", esc });
  check("⑧ 모두 펼치기 컨트롤 방출", /class="amgr-link amgr-dbgrp-all" data-dbgrp-all="dbs\d+"/.test(html), html.slice(0, 300));
  check("⑧ 접힌 그룹 있으면 라벨 = 모두 펼치기", html.includes("▾ 모두 펼치기"));
  const g2 = newCtx();
  const h2 = g2._metaDbGroupedRowsHTML([...mkItems("ds1", "adb", 3, "a"), ...mkItems("ds1", "bdb", 3, "b")], { selfDbKey: "ds1:adb", esc });
  check("⑧ 전부 펼침이면 라벨 = 모두 접기", h2.includes("▸ 모두 접기"), h2.slice(0, 200));
}

// ── ⑨ 스키마 미상/비-스키마 라벨/멀티 scope/정렬 ─────────────────────────────────────────
{
  const g = newCtx();
  const items = [
    { key: "ds1:orphan", fqn: "", label: "Table", html: `<li data-k="ds1:orphan">orphan</li>` },
    ...mkItems("ds1", "shopdb", 2, "a"),
  ];
  const html = g._metaDbGroupedRowsHTML(items, { selfDbKey: "ds1:shopdb", esc });
  const ks = headKeys(html);
  check("⑨ 스키마 미상 그룹은 마지막", ks[ks.length - 1] === "", ks);
  check("⑨ '스키마 미상' 라벨", html.includes(">스키마 미상<"), html.slice(0, 200));

  // n1: selfDbKey 가 "" 여도 미상 그룹이 앞으로 오지 않는다.
  const g2 = newCtx();
  const h2 = g2._metaDbGroupedRowsHTML(items, { selfDbKey: "", esc });
  const ks2 = headKeys(h2);
  check("⑨ selfDbKey 공백이어도 미상 그룹은 마지막(n1)", ks2[ks2.length - 1] === "", ks2);

  // m1: 용어(GlossaryTerm) 등 비-스키마 라벨은 DB 그룹 축에서 제외(유령 DB 그룹 방지).
  const g3 = newCtx();
  const h3 = g3._metaDbGroupedRowsHTML([
    { key: "ds1:v1.0레벨", fqn: "v1.0레벨", label: "GlossaryTerm", html: `<li data-k="t">용어</li>` },
    ...mkItems("ds1", "shopdb", 2, "a"),
  ], { selfDbKey: "ds1:shopdb", esc });
  check("⑨ 비-스키마 라벨은 유령 DB 그룹을 만들지 않음(m1)", !headKeys(h3).includes("ds1:v1"), headKeys(h3));

  // m2: 서로 다른 datasource 의 동명 DB 는 scope 를 병기해 구분.
  const g4 = newCtx();
  const h4 = g4._metaDbGroupedRowsHTML([...mkItems("dsA", "shopdb", 2, "a"), ...mkItems("dsB", "shopdb", 2, "b")], { selfDbKey: "dsA:shopdb", esc });
  check("⑨ 멀티 scope 동명 DB 는 scope 병기(m2)", h4.includes(">dsA · shopdb<") && h4.includes(">dsB · shopdb<"), h4.slice(0, 400));
}

// ── ⑩ 속성 이스케이프 — 인용부호 포함 식별자가 속성을 탈출하지 않는다 ────────────────────────
{
  const g = newCtx();
  const items = [
    { key: `ds1:we"ird.t1`, fqn: `we"ird.t1`, label: "Table", html: `<li data-k="x">t1</li>` },
    ...mkItems("ds1", "shopdb", 1, "a"),
  ];
  const html = g._metaDbGroupedRowsHTML(items, { selfDbKey: "ds1:shopdb", esc });
  check("⑩ 그룹 key 속성 이스케이프(&quot;)", html.includes('data-dbgrp-key="ds1:we&quot;ird"'), html.slice(0, 400));
  // NIT: esc 를 안 넘겨도 기본값이 escaping 이어야 한다(속성 안전 기본값).
  const g2 = newCtx();
  const h2 = g2._metaDbGroupedRowsHTML(items, { selfDbKey: "ds1:shopdb" });
  check("⑩ esc 미지정 시 기본값도 escaping", h2.includes("&quot;") && !h2.includes('data-dbgrp-key="ds1:we"ird"'), h2.slice(0, 300));
}

// ── ⑪ 토글 왕복 — lazy 주입 1회·bind 1회·상태 기록·재접기 보존 ────────────────────────────
{
  const g = newCtx();
  let bound = 0;
  const items = [...mkItems("ds1", "shopdb", 100, "a"), ...mkItems("ds1", "logdb", 100, "b")];
  const html = g._metaDbGroupedRowsHTML(items, { selfDbKey: "ds1:shopdb", esc, bind: () => { bound++; } });
  const gid = (html.match(/data-dbgrp="(dbg\d+)"[^>]*data-dbgrp-key="ds1:logdb"/) || [])[1];
  const setId = (html.match(/data-dbgrp-set="(dbs\d+)"/) || [])[1];
  check("⑪ 접힌 그룹 gid 추출", !!gid, html.slice(0, 300));
  const head = mkHead(gid, "ds1:logdb", setId, true);
  const body = mkBody(gid);
  const allBtn = { textContent: "▾ 모두 펼치기" };
  const root = mkRoot([{ head, body }], allBtn);
  g._metaToggleDbGroup(head, root);
  check("⑪ 펼침 후 본문 hidden 해제", body.hidden === false);
  check("⑪ lazy html 주입(100행)", countRows(body._ul.innerHTML) === 100, { rows: countRows(body._ul.innerHTML) });
  check("⑪ bind 콜백 1회 호출", bound === 1, { bound });
  check("⑪ aria-expanded=true", head._attr["aria-expanded"] === "true", head._attr);
  check("⑪ 사용자 조작 상태 기록(true)", g._metaGraph.panelDbGroupState.get("ds1:logdb") === true);
  check("⑪ lazy payload 소비(1회성)", !g.lazy.has(gid));
  check("⑪ '모두' 라벨 재동기화(전부 펼침 → 모두 접기)", allBtn.textContent === "▸ 모두 접기", allBtn.textContent);
  g._metaToggleDbGroup(head, root);
  check("⑪ 재-접기 시 hidden 복원", body.hidden === true);
  check("⑪ 재-접기 상태 기록(false)", g._metaGraph.panelDbGroupState.get("ds1:logdb") === false);
  check("⑪ 재-접기해도 주입된 행 보존(재펼침 무비용)", countRows(body._ul.innerHTML) === 100);
}

// ── ⑫ 형제 동기화(리뷰 MINOR-6) + 스키마 미상 상태 미기록(MINOR-5) ─────────────────────────
{
  const g = newCtx();
  const head1 = mkHead("dbgA", "ds1:logdb", "dbs1", true);
  const head2 = mkHead("dbgB", "ds1:logdb", "dbs2", true);   // 다른 섹션의 같은 DB 머리글
  const b1 = mkBody("dbgA"), b2 = mkBody("dbgB");
  const root = mkRoot([{ head: head1, body: b1 }, { head: head2, body: b2 }]);
  g._metaToggleDbGroup(head1, root);
  check("⑫ 같은 DB 형제 머리글도 함께 펼쳐짐", !head2._cls.has("is-collapsed"), [...head2._cls]);
  check("⑫ 형제 본문도 hidden 해제", b2.hidden === false);

  const g2 = newCtx();
  const hEmpty = mkHead("dbgC", "", "dbs1", true);
  const bEmpty = mkBody("dbgC");
  g2._metaToggleDbGroup(hEmpty, mkRoot([{ head: hEmpty, body: bEmpty }]));
  check("⑫ 스키마 미상('')은 전역 상태 슬롯을 기록하지 않음(MINOR-5)", !g2._metaGraph.panelDbGroupState.has(""));
}

// ── ⑬ 무음 실패 방지 — payload 없고 본문도 비었으면 안내를 남긴다(리뷰 MINOR-1) ────────────
{
  const g = newCtx();
  const head = mkHead("dbgZ", "ds1:logdb", "dbs1", true);
  const body = mkBody("dbgZ");
  g._metaToggleDbGroup(head, mkRoot([{ head, body }]));   // lazy Map 비어 있음(clear 된 상태 모사)
  check("⑬ stale 펼침은 빈 목록 대신 안내", /다시 불러오세요/.test(body._ul.innerHTML), body._ul.innerHTML.slice(0, 120));
}

// ── ⑭ 컬럼 아코디언 lazy(리뷰 MAJOR-4) — 등록·첫 펼침 주입·바인딩·재호출 no-op ──────────────
{
  const g = newCtx();
  const gid = g._metaColBodyLazy(`<li data-k="c1">rel</li><li data-k="c2">rel</li>`, "ds1:shopdb.t1");
  check("⑭ payload 등록(토큰 반환)", /^dbcol\d+$/.test(gid), gid);
  const body = { _html: "", get innerHTML() { return this._html; }, set innerHTML(v) { this._html = v; },
    get firstChild() { return this._html ? {} : null; }, getAttribute: () => gid };
  g._metaColBodyReveal(body, "ds1:shopdb.t1");
  check("⑭ 첫 펼침에 본문 주입(2행)", countRows(body.innerHTML) === 2, { rows: countRows(body.innerHTML) });
  check("⑭ 주입 컨테이너 한정 바인딩 수행", g._binds.trace === 1 && g._binds.hover === 1 && g._binds.dbgrp === 1, g._binds);
  check("⑭ payload 1회성 소비", !g.lazy.has(gid));
  const before = body.innerHTML;
  g._metaColBodyReveal(body, "ds1:shopdb.t1");
  check("⑭ 재호출 no-op(중복 바인딩 없음)", body.innerHTML === before && g._binds.trace === 1, g._binds);
}

// ── ⑮ 관계 상세 호출부 인자 매핑(리뷰 지적: 초판은 뒤집어도 전건 PASS 했다) ──────────────────
{
  const calls = [];
  const sandbox = {
    console,
    row: (e, otherKey, selfEndKey, arrow) => { calls.push({ e: e.id, otherKey, selfEndKey, arrow }); return `<li data-k="${otherKey}">r</li>`; },
    byKey: {}, _metaGraph: { nodes: new Map() }, selfDbKey: "ds1:shopdb", esc,
    bindRelRows: () => {},
    // 그룹 조립은 여기서 관심 밖 — items 를 그대로 관찰한다.
    _metaDbGroupedRowsHTML: (items) => { sandbox.captured = items; return items.map((i) => i.html).join(""); },
  };
  vm.createContext(sandbox);
  vm.runInContext(fnDirRows, sandbox, { filename: "dirRows-unit.js" });
  sandbox.dirRowsHTML = vm.runInContext("dirRowsHTML", sandbox);   // const 는 전역 객체 속성이 아니라 명시 평가
  const edges = [{ id: 1, source: "ds1:shopdb.orders.customer_id", target: "ds1:crm.customers.id" }];
  sandbox.dirRowsHTML(edges, "out");
  check("⑮ out: 상대=target · self끝점=source · 화살표 →",
    calls[0] && calls[0].otherKey === "ds1:crm.customers.id" && calls[0].selfEndKey === "ds1:shopdb.orders.customer_id" && calls[0].arrow === "→", calls[0]);
  check("⑮ out: 그룹 items.key = 상대 노드 키", sandbox.captured[0].key === "ds1:crm.customers.id", sandbox.captured[0]);
  calls.length = 0;
  sandbox.dirRowsHTML(edges, "in");
  check("⑮ in: 상대=source · self끝점=target · 화살표 ←",
    calls[0] && calls[0].otherKey === "ds1:shopdb.orders.customer_id" && calls[0].selfEndKey === "ds1:crm.customers.id" && calls[0].arrow === "←", calls[0]);
}

// ── ⑯ 백엔드 이웃 상한 고지(리뷰 MAJOR-1) + 소스 정적 회귀 ────────────────────────────────
{
  const g = newCtx();
  check("⑯ truncated=false 면 배너 없음", g._metaDbGrpTruncNotice({ truncated: false }) === "" && g._metaDbGrpTruncNotice(null) === "");
  check("⑯ truncated=true 면 부분 로드 고지", /일부만/.test(g._metaDbGrpTruncNotice({ truncated: true })));

  const legacy = [
    ["routineUses 30건 상한", /list\s*\.slice\(\s*0\s*,\s*30\s*\)\s*\.map\(\s*rtRow\s*\)/],
    ["관계 상세 60건 상한", /\b(out|inn)\s*\.slice\(\s*0\s*,\s*60\s*\)/],
    ["연관 용어 30건 상한", /\bterms\s*\.slice\(\s*0\s*,\s*30\s*\)/],
    ["주변 관계 20건 상한", /\baround\s*\.slice\(\s*0\s*,\s*20\s*\)/],
    ["컬럼 80개 무음 절단", /\bcolumns\s*\.slice\(\s*0\s*,\s*80\s*\)/],
  ];
  legacy.forEach(([label, re]) => check(`⑯ 제거됨: ${label}`, !re.test(src)));
  check("⑯ 상세 안내 문구가 '생략 없음' 을 단언하지 않음(백엔드 상한 존재)", !src.includes("(생략 없음)"));
}

// ── ⑰ graph-noise-reduce(2026-07-28, 사용자 요구): 상시 설명문 → hover 툴팁 전환 회귀 방지 ──
//   요구: "한 번 인지하면 다시 볼 필요 없는 설명" 을 상세 패널 본문에서 걷어내고 hover 툴팁으로 옮긴다.
//   문구 자체가 아니라 **접근 경로**(본문 문단 vs .amgr-sec-help title)를 단언해, 설명이 본문으로
//   되돌아오면 FAIL 하게 한다. 실 렌더 육안은 PB-0008 이 담당(여기는 마크업 계약).
{
  const fnSecHelp = grab(/\nfunction _metaSecHelp\([\s\S]*?\n\}\n/, "_metaSecHelp");
  const sandbox = { console };
  vm.createContext(sandbox);
  vm.runInContext(fnSecHelp, sandbox, { filename: "sechelp-unit.js" });
  const out = sandbox._metaSecHelp(`a"b<c&d`);
  check("⑰ _metaSecHelp 가 .amgr-sec-help title 마커 생성", /<span class="amgr-sec-help"[^>]*\btitle="/.test(out), out);
  check("⑰ _metaSecHelp title 속성 이스케이프(속성 탈출 방어)",
    out.includes("a&quot;b&lt;c&amp;d") && !/title="[^"]*"[^>]*"/.test(out.replace(/aria-label="[^"]*"/, "")), out);
  check("⑰ _metaSecHelp 키보드 접근(tabindex + aria-label)", out.includes('tabindex="0"') && out.includes('aria-label="'), out);
  check("⑰ 빈 tip 도 안전(예외 없음)", typeof sandbox._metaSecHelp(null) === "string");

  // 상세 패널 본문에서 제거되어야 할 상시 설명 문단(스크린샷 지목분 + 동류).
  const removedProse = [
    ["컬럼 섹션 장문 안내", "컬럼을 클릭하면 선택되어 상세로 전환되고"],
    ["함수·프로시저 섹션 장문 안내", "읽기/쓰기로 나눠 표시합니다 —"],
    ["컬럼 관계 행 안내 문단", '<p class="admin-meta-detail-note">행 hover 시'],
    ["관계 상세 서두 설명", "이 노드가 맺은 관계를 방향별로 봅니다 —"],
    ["클러스터 상세 클릭 안내", "이 스키마 클러스터에 속한 테이블"],
    ["AI 분석 box 상시 설명", "이 노드에서 시작해 관련 노드를 AI가 재귀적으로 분석합니다(백그라운드).</span>"],
    ["빈 상태 우클릭 안내 문단", "노드를 <strong>우클릭</strong>하면 상세 보기·관계 상세·관계 확장"],
  ];
  removedProse.forEach(([label, needle]) => check(`⑰ 본문에서 제거됨: ${label}`, !src.includes(needle)));

  // 같은 정보가 툴팁 경로로 남아 있어야 한다(정보 소실이 아니라 이동).
  const keptAsTip = [
    ["컬럼 클릭 안내", "컬럼 클릭 = 상세로 전환"],
    ["함수·프로시저 DB 그룹 안내", "읽기/쓰기로 나눠 표시하며 목록을 잘라내지 않습니다"],
    ["관계 행 추적 안내", "행 hover = 관계 의미"],
    ["클러스터 항목 클릭 안내", "항목을 클릭하면 ${_clickHint} 상세를 봅니다."],
  ];
  keptAsTip.forEach(([label, needle]) => check(`⑰ 툴팁으로 보존됨: ${label}`, src.includes(needle)));

  // graph-hop-budget(2026-07-28): 절단 경고 함수가 목록용(_metaDbGrpTruncNotice)과 이웃그래프용
  //   (_metaNbrTruncNotice)으로 분리되어 note 마크업이 여러 개가 됐다 — 계약의 의도("본문 상시 설명은
  //   절단 경고뿐")를 개수 대신 **모든 note 가 절단 경고 클래스를 동반한다**로 표현한다.
  const notes = src.match(/class="admin-meta-detail-note[^"]*"/g) || [];
  check("⑰ 상세 패널 렌더에 남은 admin-meta-detail-note 는 절단 경고뿐",
    notes.length >= 1 && notes.every((c) => c.includes("amgr-trunc-note")), notes);
}

// ── ⑱ graph-hop-budget(2026-07-28): 절단 경고 귀속 + '확장할 관계 없음' 안내 ──────────────
//   배경(라이브 실측): 앵커 직결 ROUTINE_USES 는 1-hop 에서 전량 수집되어 depth 1·2·3 모두 155개인데,
//   2-hop 이상에서 truncated=true 가 되면 종전 코드가 그 **완전한** 목록 위에 "일부만 불러옴" 을 붙였다.
//   여기서는 (a) 경고가 함수·프로시저 섹션에서 분리됐는지 (b) hop 별 문구가 사실과 맞는지 (c) 관계가
//   없어 2-hop 이 1-hop 과 같아질 때 그 사실을 알리는지를 단언한다.
{
  const fnNbrTrunc = grab(/\nfunction _metaNbrTruncNotice\([\s\S]*?\n\}\n/, "_metaNbrTruncNotice");
  const fnNoRel = grab(/\nfunction _metaNoRelHint\([\s\S]*?\n\}\n/, "_metaNoRelHint");
  const relSet = grab(/const _META_REL_ETYPES = new Set\(\[[^\]]*\]\);/, "_META_REL_ETYPES");
  const sandbox = { console };
  vm.createContext(sandbox);
  vm.runInContext(fnNbrTrunc + "\n" + relSet + "\n" + fnNoRel, sandbox, { filename: "hopbudget-unit.js" });
  const nbr = vm.runInContext("_metaNbrTruncNotice", sandbox);
  const noRel = vm.runInContext("_metaNoRelHint", sandbox);

  check("⑱ truncated=false / null 이면 경고 없음",
    nbr({ truncated: false }) === "" && nbr(null) === "");

  const h2 = nbr({ truncated: true, truncated_hop: 2, omitted_nodes: 337 });
  check("⑱ 2-hop 절단: 확장분이 잘렸다고 말한다", /2-hop 확장 이웃/.test(h2), h2);
  check("⑱ 2-hop 절단: 생략 규모를 숫자로 알린다", /337/.test(h2), h2);
  check("⑱ 2-hop 절단: 직접 연결 목록은 전량이라고 명시(오귀속 방지)", /직접 연결 목록은 전량/.test(h2), h2);
  check("⑱ 2-hop 절단: 목록이 잘렸다고 오해시키지 않는다", !/아래 목록도 일부만/.test(h2), h2);

  const h1 = nbr({ truncated: true, truncated_hop: 1, omitted_nodes: 420 });
  check("⑱ 1-hop 절단: 목록도 부분임을 알린다", /아래 목록도 일부만/.test(h1), h1);
  check("⑱ 1-hop 절단: '확장 이웃' 으로 오표기하지 않는다", !/확장 이웃/.test(h1), h1);

  check("⑱ hop 미상이어도 예외 없이 문구 생성", typeof nbr({ truncated: true }) === "string");
  // 적대리뷰 R4-d: 구 백엔드 응답(truncated=true·truncated_hop 부재, 롤링 배포 창)을 "2-hop 확장분만
  //   잘림 + 직접 목록은 전량" 으로 흘리면, 1-hop 에서 잘린 응답에도 완전성을 주장하는 거짓이 된다.
  const hLegacy = nbr({ truncated: true, omitted_nodes: 12 });
  check("⑱ hop 미상: 목록 완전성을 주장하지 않는다", !/직접 연결 목록은 전량/.test(hLegacy), hLegacy);
  check("⑱ hop 미상: 존재하지 않는 hop 을 날조하지 않는다", !/2-hop/.test(hLegacy), hLegacy);
  check("⑱ hop 미상: 절단 사실과 규모는 알린다", /상한 초과/.test(hLegacy) && /12/.test(hLegacy), hLegacy);

  // 함수·프로시저 섹션 헤더 직후에 절단 배너를 다시 붙이면 FAIL (오귀속 회귀 방지).
  check("⑱ 함수·프로시저 섹션이 절단 배너를 직접 붙이지 않는다",
    !/사용하는 함수·프로시저[\s\S]{0,400}?parts\.push\(_meta(DbGrp|Nbr)TruncNotice/.test(src));
  // 경고는 패널 상단(설명문 직후, 첫 섹션 이전) 1곳에서만 삽입된다.
  check("⑱ 절단 경고는 패널 상단 1곳에서 삽입",
    (src.match(/parts\.push\(_metaNbrTruncNotice\(meta\)\)/g) || []).length === 1);

  check("⑲ depth<=1 이면 관계-없음 안내 미표시",
    noRel(1, { edges: [] }) === "" && noRel("1", { edges: [] }) === "");
  check("⑲ depth=2 + 관계 엣지 없음 → 1-hop 과 동일함을 알린다",
    /1-hop 과 동일/.test(noRel(2, { edges: [{ type: "HAS_COLUMN" }, { type: "HAS_TABLE" }] })));
  check("⑲ depth=2 + REFERENCES 있으면 안내 없음",
    noRel(2, { edges: [{ type: "HAS_COLUMN" }, { type: "REFERENCES" }] }) === "");
  check("⑲ depth=3 + ROUTINE_USES 있으면 안내 없음",
    noRel(3, { edges: [{ type: "ROUTINE_USES" }] }) === "");
  check("⑲ edges 부재도 안전", typeof noRel(2, {}) === "string" && typeof noRel(2, null) === "string");

  // ⑳ 적대리뷰 R2-c: 힌트 판정을 **hop 별 확장 실적**(expanded_hops)으로 교체. 종전엔 응답 엣지에 관계
  //   라벨이 하나만 있어도 힌트를 숨겼는데, 그 관계가 1-hop 것이고 상대가 leaf 면 2·3-hop 이 아무것도
  //   더하지 못하는데도 사용자에게 아무 안내가 없었다("선택이 안 먹었다" 오해).
  check("⑳ hop1 에 관계 엣지가 있어도 2-hop 실적 0 이면 동일함을 알린다",
    /1-hop 과 동일/.test(noRel(2, { edges: [{ type: "REFERENCES" }], expanded_hops: [5, 0] })),
    noRel(2, { edges: [{ type: "REFERENCES" }], expanded_hops: [5, 0] }));
  check("⑳ 2-hop 이 실제로 노드를 늘리면 안내 없음",
    noRel(2, { edges: [{ type: "REFERENCES" }], expanded_hops: [5, 3] }) === "");
  check("⑳ 3-hop: 2·3 hop 합산 실적으로 판정",
    noRel(3, { edges: [{ type: "REFERENCES" }], expanded_hops: [5, 0, 2] }) === ""
    && /1-hop 과 동일/.test(noRel(3, { edges: [{ type: "REFERENCES" }], expanded_hops: [5, 0, 0] })));
  check("⑳ expanded_hops 부재(구 replica 응답)면 종전 엣지 판정으로 폴백",
    noRel(2, { edges: [{ type: "REFERENCES" }] }) === ""
    && /1-hop 과 동일/.test(noRel(2, { edges: [{ type: "HAS_COLUMN" }] })));
  check("⑳ expanded_hops 가 배열 아니면 폴백(형 방어)",
    typeof noRel(2, { edges: [], expanded_hops: "nope" }) === "string");

  // ㉑ 적대리뷰 R3-b: 노드 델타 0 만으로 단정하면 두 경우에 틀린다 — ① 이미 발견된 노드 사이에 엣지만
  //   추가된 경우(결과는 달라졌다) ② cap 절단으로 뒤 hop 이 실행되지 못한 경우("관계 없음" 이 아니라
  //   "예산 없음"). 절단 시에는 힌트를 억제하고, 엣지 실적도 함께 본다.
  check("㉑ 절단됐으면 '동일' 로 단정하지 않는다(예산 부족 ≠ 관계 없음)",
    noRel(2, { edges: [], expanded_hops: [5, 0], expanded_hop_edges: [4, 0], truncated: true }) === "");
  check("㉑ 노드는 0 이지만 엣지가 늘었으면 안내 없음(결과가 달라졌다)",
    noRel(2, { edges: [{ type: "REFERENCES" }], expanded_hops: [5, 0], expanded_hop_edges: [4, 2] }) === "");
  check("㉑ 노드·엣지 모두 0 + 절단 없음 → 동일함을 알린다",
    /1-hop 과 동일/.test(noRel(2, { edges: [{ type: "REFERENCES" }], expanded_hops: [5, 0], expanded_hop_edges: [4, 0] })));
  check("㉑ expanded_hop_edges 부재도 안전(노드 실적만으로 판정)",
    typeof noRel(2, { edges: [], expanded_hops: [5, 0] }) === "string");

  // depth select 문구 정합: 단일클릭(선택) 상세는 depth=1 고정이라 '선택하면 이 깊이로' 는 거짓 안내였다.
  const core = fs.readFileSync(path.join(path.dirname(CTX), "graph-core.js"), "utf8");
  check("⑲ depth select 안내가 '선택' 을 확장 트리거로 표기하지 않음",
    !/노드를 선택\/더블클릭하면 이 깊이로/.test(core));
  check("⑲ depth select 안내가 실제 트리거(더블클릭·중심 보기)를 명시",
    /더블클릭\(또는 우클릭 → '이 노드 중심으로 보기'\)하면 이 깊이로/.test(core));
}

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail === 0 ? 0 : 1);
