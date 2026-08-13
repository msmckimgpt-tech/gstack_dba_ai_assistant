// verify_attach_pill_name_sort.mjs
// REQ-20260813-attach-name-sort — 컴포저 bucket 렌더(`_renderAttachmentPills`)의 이름순 정렬.
//
// 왜 이 하네스가 필요한가: 첨부 사이드 패널(`#attachSidePanelList`)에는 **렌더러가 둘**이다 —
// 서버 목록(`_loadConversationAttachmentList`)과 이 컴포저 bucket 렌더. 서버 쪽만 이름순으로
// 두면 업로드 직후에는 push 순서로 보이다가 패널을 다시 열면 순서가 바뀐다(codex 적대 리뷰 P2).
// 이 모듈이 반복 기록한 "렌더러가 2개면 개수로 세라" 원칙에 따라, 정렬 배선을 **두 목록 모두**
// 에서 개수로 단언한다.
//
// 검증 3축: (A) 정본 비교자 실행 (B) 배선 개수 (C) 뮤테이션 역검증.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const COMPOSER = join(__dirname, "..", "src", "static", "app", "composer.js");
const src = readFileSync(COMPOSER, "utf8");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// ── A. 정본 비교자를 그대로 꺼내 실행(로직 재구현 0) ───────────────────────────
const m = /const byName = [\s\S]*?;\n/.exec(src);
ok("A0 비교자 `byName` 정의 발견", !!m);
const byName = m ? new Function(`${m[0]} return byName;`)() : null;

function sorted(names) {
  return names.map((n, i) => ({ name: n, id: i + 1 })).sort(byName).map((x) => x.name);
}

if (byName) {
  ok("A1 숫자 구간은 수치 비교(_02_ < _09_ < _10_)",
    JSON.stringify(sorted(["j_10.sql", "j_2.sql", "j_09.sql", "j_1.sql"]))
      === JSON.stringify(["j_1.sql", "j_2.sql", "j_09.sql", "j_10.sql"]));
  ok("A2 사전순이었다면 결과가 달랐다(vacuous 아님)",
    JSON.stringify(sorted(["j_10.sql", "j_2.sql"]))
      !== JSON.stringify(["j_10.sql", "j_2.sql"].sort()));
  ok("A3 대소문자 무시",
    JSON.stringify(sorted(["b.sql", "A.sql"])) === JSON.stringify(["A.sql", "b.sql"]));
  ok("A4 한글은 가나다순",
    JSON.stringify(sorted(["다.txt", "가.txt", "나.txt"]))
      === JSON.stringify(["가.txt", "나.txt", "다.txt"]));
  ok("A5 이름이 같으면 id 로 결정적",
    JSON.stringify([{ name: "a", id: 9 }, { name: "a", id: 3 }].sort(byName).map((x) => x.id))
      === JSON.stringify([3, 9]));
  ok("A6 이름 없는 항목도 예외 없이 정렬",
    sorted([undefined, "a.txt", null]).length === 3);
}

// ── B. 배선: 두 목록 **모두** 정렬을 거친다 ───────────────────────────────────
const renderFn = /function _renderAttachmentPills\(\)[\s\S]*?\n}/.exec(src);
ok("B0 `_renderAttachmentPills` 발견", !!renderFn);
const body = renderFn ? renderFn[0] : "";
const sortCalls = (body.match(/\.sort\(byName\)/g) || []).length;
ok("B1 정렬 호출이 정확히 2회(newItems + sessionItems)", sortCalls === 2);
ok("B2 '이번 요청에 첨부' 목록이 정렬을 거친다",
  /const newItems = items\.filter\(.*?\)\.sort\(byName\)/.test(body));
ok("B3 '세션 파일' 목록이 정렬을 거친다",
  /const sessionItems = items\.filter\(.*?\)\.sort\(byName\)/.test(body));

// ── C. 뮤테이션 역검증: 정렬을 떼면 위 단언이 죽는가 ──────────────────────────
const mutated = body.replace(/\.sort\(byName\)/g, "");
ok("C1 정렬 제거 시 B1 이 red",
  (mutated.match(/\.sort\(byName\)/g) || []).length !== 2);
if (byName) {
  const unsorted = ["j_10.sql", "j_2.sql"].map((n, i) => ({ name: n, id: i + 1 })).map((x) => x.name);
  ok("C2 정렬 없으면 삽입 순서가 유지된다(대조군)",
    JSON.stringify(unsorted) === JSON.stringify(["j_10.sql", "j_2.sql"]));
}

console.log(`\n${passed} PASS / ${failed} FAIL`);
process.exit(failed ? 1 : 0);
