// verify_date_group_collapse.mjs
// TASK-date-group-collapse: 작업 화면 좌측 대화목록 첫 진입 기본값 —
//   내 대화 날짜 그룹은 "가장 최근 일자 1개만 펼치고 나머지 오래된 일자는 접힘"으로 시작.
//   날짜 키(__today__/__yesterday__/YYYY-MM-DD/__other__)는 상대적이라 영속 seed 가
//   다음 날 무의미해지므로 localStorage 에 영속하지 않고, in-memory 플래그
//   (_dateGroupsSeededThisLoad)로 페이지 로드당 1회만 적용한다(reload 시 재적용).
//   같은 로드 안의 사용자 펼침 토글은 플래그가 막아 그대로 존중한다.
//
//   set 조작만 하는 순수 로직이라 jsdom 불필요(순수 node). 실제 화면 정본은
//   PB-0008 Windows-browser(최근 그룹만 펼침 + 오래된 그룹 is-collapsed computed 검증)가 담당.
//
// 실행: node verify_date_group_collapse.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// async / 일반 function 선언 모두 지원하는 추출기 (signature 의 destructuring `{}` 를
// body `{` 로 오인하지 않도록 먼저 paren-matching 으로 signature 끝을 찾는다).
function extractFn(src, name) {
  let start = src.indexOf(`async function ${name}(`);
  if (start < 0) start = src.indexOf(`function ${name}(`);
  if (start < 0) return null;
  let paren = 0, sigEnd = -1;
  for (let j = src.indexOf("(", start); j < src.length; j++) {
    if (src[j] === "(") paren++;
    else if (src[j] === ")") { paren--; if (paren === 0) { sigEnd = j; break; } }
  }
  let depth = 0, end = -1;
  for (let i = src.indexOf("{", sigEnd); i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return src.slice(start, end);
}

const seedSrc = extractFn(appJs, "_seedDateGroupsCollapsedOnce");
ok("[추출] _seedDateGroupsCollapsedOnce", Boolean(seedSrc));

// 모듈 스코프 플래그 _dateGroupsSeededThisLoad 를 함수와 같은 클로저로 묶어,
// 호출 사이 1회-게이트가 실제로 동작하는지 검증한다. state 는 클로저 캡처.
function build(state) {
  const factory = new Function(
    "state",
    `let _dateGroupsSeededThisLoad = false;\n${seedSrc}\n` +
      `return { seed: _seedDateGroupsCollapsedOnce, getFlag: () => _dateGroupsSeededThisLoad };`
  );
  return factory(state);
}
const has = (state, k) => state.collapsedDateGroups.has(k);

// Case 1 — 첫 진입(빈 set) → [0] 최근 펼침, 나머지 접힘 + 플래그 set
{
  const state = { collapsedDateGroups: new Set() };
  const { seed, getFlag } = build(state);
  seed(["__today__", "__yesterday__", "2026-06-15"]);
  ok("[fresh] 최근(__today__) 펼침", !has(state, "__today__"));
  ok("[fresh] __yesterday__ 접힘", has(state, "__yesterday__"));
  ok("[fresh] 2026-06-15 접힘", has(state, "2026-06-15"));
  ok("[fresh] 플래그 set", getFlag() === true);
}

// Case 2 — 직전 세션 영속으로 최근([0])이 접힘 set 에 남아도 seed 가 강제 펼침(delete)
{
  const state = { collapsedDateGroups: new Set(["__today__", "__yesterday__"]) };
  const { seed } = build(state);
  seed(["__today__", "__yesterday__", "2026-06-14"]);
  ok("[force-expand] 최근([0]) 강제 펼침", !has(state, "__today__"));
  ok("[force-expand] 나머지 접힘 유지(__yesterday__)", has(state, "__yesterday__"));
  ok("[force-expand] 나머지 접힘 추가(2026-06-14)", has(state, "2026-06-14"));
}

// Case 3 — 그룹 미로드(빈 키)면 플래그 안 세우고 다음 렌더에서 재시도
{
  const state = { collapsedDateGroups: new Set() };
  const { seed, getFlag } = build(state);
  seed([]);
  ok("[empty-retry] 빈 키 → 플래그 미설정(재시도 가능)", getFlag() === false);
  seed(["__today__", "2026-06-13"]);
  ok("[empty-retry] 그룹 생긴 후 seed 적용 → 플래그 set", getFlag() === true);
  ok("[empty-retry] 최근 펼침", !has(state, "__today__"));
  ok("[empty-retry] 오래된 접힘", has(state, "2026-06-13"));
}

// Case 4 — 같은 로드 내 사용자가 펼친 토글은 1회-게이트가 막아 그대로 존중(재접힘 안 함)
{
  const state = { collapsedDateGroups: new Set() };
  const { seed } = build(state);
  seed(["__today__", "__yesterday__"]);     // 첫 seed: __yesterday__ 접힘
  state.collapsedDateGroups.delete("__yesterday__"); // 사용자가 펼침
  seed(["__today__", "__yesterday__"]);     // 재렌더 — 1회-게이트로 no-op
  ok("[respect] 세션 내 펼침 토글 존중(재접힘 안 함)", !has(state, "__yesterday__"));
}

// Case 5 — 그룹이 1개뿐이면 그 그룹은 펼침, 접힐 대상 없음
{
  const state = { collapsedDateGroups: new Set(["__today__"]) };
  const { seed } = build(state);
  seed(["__today__"]);
  ok("[single] 단일 그룹은 펼침", !has(state, "__today__"));
  ok("[single] 접힘 set 비어있음", state.collapsedDateGroups.size === 0);
}

// Case 6 — __other__(날짜 미확인)도 [0] 이 아니면 오래된 그룹으로 접힘
{
  const state = { collapsedDateGroups: new Set() };
  const { seed } = build(state);
  seed(["__today__", "2026-06-10", "__other__"]);
  ok("[other] 최근 펼침", !has(state, "__today__"));
  ok("[other] 중간 날짜 접힘", has(state, "2026-06-10"));
  ok("[other] __other__ 접힘", has(state, "__other__"));
}

// Case 7 — 비-영속 보장: seed 함수는 localStorage / _saveCollapsedGroups 를 건드리지 않는다
//          (세션 단위 기본값 — reload 마다 재적용, 사용자 토글만 영속)
ok("[no-persist] seed 가 _saveCollapsedGroups 호출 안 함", !/_saveCollapsedGroups\s*\(/.test(seedSrc));
ok("[no-persist] seed 가 localStorage 직접 참조 안 함", !/localStorage/.test(seedSrc));

// Case 8 — renderConversationList 가 sortedDateKeys 계산 직후 seed 를 호출(렌더 전 반영)
ok("[wired] renderConversationList 가 _seedDateGroupsCollapsedOnce(sortedDateKeys) 호출",
  /_seedDateGroupsCollapsedOnce\(sortedDateKeys\)/.test(appJs));
// seed 호출이 sortedDateKeys 선언 이후 & sortedDateKeys.forEach 렌더 이전 위치인지(순서)
{
  const sortIdx = appJs.indexOf("const sortedDateKeys = Array.from(dateGroups.keys())");
  const seedIdx = appJs.indexOf("_seedDateGroupsCollapsedOnce(sortedDateKeys);");
  const renderIdx = appJs.indexOf("sortedDateKeys.forEach((dateKey) =>");
  ok("[wired] seed 호출이 정렬 이후·렌더 이전", sortIdx > 0 && seedIdx > sortIdx && renderIdx > seedIdx);
}

console.log(`\n${failed === 0 ? "ALL PASS" : "HAS FAILURES"} — ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
