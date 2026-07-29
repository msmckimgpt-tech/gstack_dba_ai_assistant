// detail-panel-typo(사용자 리포트 2026-07-29 "디자인적으로 모범적이지 않고 시각적으로 불편") —
//   상세 패널 목록 행의 **타이포 위계·행 리듬·정렬** 계약. 이 부류(computed style / 레이아웃 기하)는
//   마크업 문자열 단언으로는 잡히지 않고 실 CSS cascade 를 통과시켜야 드러나므로, jsdom 이 아니라
//   **실 CSS 파서 + 레이아웃**이 필요하다. 여기서는 CSS 를 직접 파싱해 선언값을 검증하고(엔진 무의존),
//   실 렌더 기하(행 높이 균일·우측 경계 정렬·말줄임)는 PB-0008 + playwright 실측이 담당한다
//   (`docs/test-runs.d/` Run 기록 참조).
//
// 잠그는 계약:
//   ① 목록 행의 **주 라벨(.amgr-rtname)이 부가정보(.amgr-rtcols)보다 크다** — 종전 10.5px vs 13px
//      위계 역전(부가정보가 24% 큼)의 회귀 차단.
//   ② 섹션 헤더(h4)가 본문 ink 색 — 종전엔 본문 항목과 같은 --text-2 라 제목/항목 구분이 없었다.
//   ③ h4 안의 muted 가 bold 를 상속하지 않는다 — "약하게" 의도가 굵게 렌더되던 모순.
//   ④ 행이 전폭 flex 이고 부가정보가 우측 정렬 + 말줄임 — 톱니 우측 경계·행 높이 튐 차단.
//   ⑤ 섹션 간 여백 > 행 간 여백 — 덩어리 경계.
//   ⑥ 부-액션 버튼(.amgr-link)을 행의 주 라벨로 재사용하지 않는다 — 이 결함의 근본 원인.
"use strict";
const fs = require("fs");
const path = require("path");

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log("PASS", name); }
  else { fail++; console.log("FAIL", name, extra === undefined ? "" : JSON.stringify(extra).slice(0, 260)); }
}

const CSS = fs.readFileSync(process.argv[2] || path.resolve(__dirname, "../../src/static/graph/graph.css"), "utf8");
const CTX = fs.readFileSync(path.resolve(__dirname, "../../src/static/graph/graph-ctxmenu.js"), "utf8");

// 선택자의 선언 블록을 뽑는다(주석 제거 후 정확 매칭).
const bare = CSS.replace(/\/\*[\s\S]*?\*\//g, "");
function block(sel) {
  const re = new RegExp(`(^|\\})\\s*${sel.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\{([^}]*)\\}`, "m");
  const m = bare.match(re);
  return m ? m[2] : null;
}
function decl(sel, prop) {
  const b = block(sel);
  if (!b) return null;
  const m = b.match(new RegExp(`(?:^|;)\\s*${prop}\\s*:\\s*([^;]+)`, "i"));
  return m ? m[1].trim() : null;
}
const px = v => (v == null ? null : parseFloat(String(v)));

// ── ① 위계 역전 차단 (핵심) ──────────────────────────────────────────────────
const nameFs = px(decl(".amgr-rtname", "font-size")) ?? px(decl(".amgr-rtrow", "font-size"));
const colsFs = px(decl(".amgr-rtcols", "font-size"));
check("① 부가정보(.amgr-rtcols) 크기 규칙이 명시됨 (base 상속 금지)", colsFs != null, {colsFs});
check("① 주 라벨이 부가정보보다 크다 (위계 역전 회귀 차단)",
  nameFs != null && colsFs != null && nameFs > colsFs, {nameFs, colsFs});
check("① 주 라벨이 11px 이상 (가독 하한)", nameFs != null && nameFs >= 11, {nameFs});

// ── ② 섹션 헤더 위계 ─────────────────────────────────────────────────────────
const h4Col = decl(".admin-meta-graph-sec h4", "color");
check("② 섹션 헤더가 본문 ink(--text) 색 — 항목과 같은 --text-2 가 아님",
  h4Col != null && /var\(--text\)/.test(h4Col) && !/--text-2/.test(h4Col), {h4Col});

// ── ③ muted 의 bold 상속 차단 ───────────────────────────────────────────────
const mutedFw = decl(".admin-meta-graph-sec h4 .admin-meta-graph-muted", "font-weight");
check("③ h4 내 muted 가 bold 를 상속하지 않는다", mutedFw != null && parseInt(mutedFw, 10) < 700, {mutedFw});

// ── ④ 행 레이아웃: 전폭 flex + 부가정보 우측 정렬·말줄임 ─────────────────────
check("④ 행이 flex", /flex/.test(decl(".amgr-rtrow", "display") || ""), decl(".amgr-rtrow", "display"));
check("④ 행이 전폭 (톱니 우측 경계 제거)", /100%/.test(decl(".amgr-rtrow", "width") || ""), decl(".amgr-rtrow", "width"));
check("④ 행에 테두리 없음 (부-액션 칩 시각 언어 탈피)", /none/.test(decl(".amgr-rtrow", "border") || ""), decl(".amgr-rtrow", "border"));
check("④ 행 hover 어포던스 존재", /amgr-rtrow:hover/.test(bare));
for (const [sel, label] of [[".amgr-rtname", "주 라벨"], [".amgr-rtcols", "부가정보"]]) {
  const b = block(sel) || "";
  check(`④ ${label} 말줄임 3종 (행 높이 균일 보장)`,
    /text-overflow\s*:\s*ellipsis/.test(b) && /white-space\s*:\s*nowrap/.test(b) && /overflow\s*:\s*hidden/.test(b), b.slice(0, 120));
  check(`④ ${label} min-width:0 (flex 말줄임 성립 조건)`, /min-width\s*:\s*0/.test(b), b.slice(0, 120));
}
check("④ 부가정보가 우측 정렬", /auto/.test(decl(".amgr-rtcols", "margin-left") || ""), decl(".amgr-rtcols", "margin-left"));
check("④ 부가정보 폭 상한으로 주 라벨 공간 보장", px(decl(".amgr-rtcols", "max-width")) > 0 && px(decl(".amgr-rtcols", "max-width")) <= 50,
  decl(".amgr-rtcols", "max-width"));

// ── ⑤ 수직 리듬: 섹션 간 > 행 간 ────────────────────────────────────────────
const secMt = px(decl(".admin-meta-graph-sec", "margin-top"));
const rowPad = px((decl(".amgr-rtrow", "padding") || "").split(/\s+/)[0]);
check("⑤ 섹션 간 여백이 행 padding 보다 확실히 넓다 (덩어리 경계)",
  secMt != null && rowPad != null && secMt >= rowPad * 3, {secMt, rowPad});
check("⑤ 목록 li 이중 여백 제거 (행 padding 단일 리듬)",
  /ul\.amgr-list\s*>\s*li\.amgr-rtli\s*\{[^}]*margin\s*:\s*0/.test(bare));
// ⑤-b 적대검증(codex) 흡수: 여백 리셋이 **루틴 행만** 대상이어야 한다. 넓은 `ul.amgr-list > li` 리셋은
//   특이도 (0,2,2) 로 `.amgr-row`(관계 상세 카드, (0,1,0))·`.amgr-dbgrp-allctl` 을 눌러 **카드가 서로
//   붙는** 부수 피해를 만든다(실렌더 실측: 카드 간격 3px → 0px). 대상 한정을 셀렉터 단위로 잠근다.
check("⑤-b 여백 리셋이 루틴 행(.amgr-rtli)으로 한정 — 관계 카드 간격 부수피해 차단",
  !/ul\.amgr-list\s*>\s*li\s*\{/.test(bare), "넓은 ul.amgr-list > li 리셋이 되살아났다");
check("⑤-b 루틴 행 li 에 한정 클래스가 실제로 부여됨", /<li class="amgr-rtli">/.test(CTX));

// ── ⑥ 근본 원인 회귀 차단 ───────────────────────────────────────────────────
check("⑥ 루틴 사용 행이 부-액션 버튼(.amgr-link)을 재사용하지 않는다",
  !/class="amgr-link"[^`]*data-rtuse/.test(CTX) && /class="amgr-rtrow" data-rtuse/.test(CTX));
check("⑥ .amgr-link 는 부-액션(모두 펼치기·관계 상세 등)에만 남아있다",
  /class="amgr-link amgr-dbgrp-all"/.test(CTX));
// 말줄임 무음 손실 차단 — 잘리는 두 요소 모두 title 에 전문을 싣는다.
check("⑥ 주 라벨 전문이 title 에 보존됨", /title="\$\{esc\(disp\)\} — 상세 보기"/.test(CTX));
check("⑥ 부가정보 전문이 title 에 보존됨", /참조하는 컬럼 \(✎ = 쓰기\): \$\{esc\(txt\)\}/.test(CTX));
// hover-flow / 클릭 추적 계약 불변
check("⑥ 행이 hover-flow data-* 계약을 유지", /data-edge-src="\$\{esc\(e\.source\)\}" data-edge-tgt="\$\{esc\(e\.target\)\}" data-rel-type="\$\{rk\}"/.test(CTX));

console.log(`\n결과: ${pass} PASS / ${fail} FAIL`);
process.exit(fail === 0 ? 0 : 1);
