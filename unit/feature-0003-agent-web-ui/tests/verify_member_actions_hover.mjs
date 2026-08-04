// verify_member_actions_hover.mjs — feature-0009 gc-member-actions-hover 정적 CSS 단언.
// 공유 팝업 참여자/차단 목록의 추방·차단·해제 버튼이 기본 접힘 → hover/focus 시 펼침,
// 세로 스택이라 한 칩 확장이 다른 칩 위치를 바꾸지 않음 + 캐시버스터 bump 를 정적 검증.
// (라이브 시각/애니메이션 정본은 PB-0008 + 배포 후. 본 테스트는 회귀 가드.)
//
// 실행: node unit/feature-0003-agent-web-ui/tests/verify_member_actions_hover.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const staticDir = join(here, "..", "src", "static");
const css = /* feature-0038 Cycle 1: styles.css → css/ 7분할 — 순차 concat(byte-동치) */ ["base","shell","chat","drawers","admin","profile","search-audit"].map((n) => readFileSync(join(staticDir, `css/${n}.css`), "utf8")).join("");
const indexHtml = readFileSync(join(staticDir, "index.html"), "utf8");

let pass = 0, fail = 0;
const ok = (cond, name) => {
  if (cond) { pass++; console.log(`  PASS ${name}`); }
  else { fail++; console.error(`  FAIL ${name}`); }
};

// 단일 규칙 블록 추출 헬퍼.
const ruleBody = (selector) => {
  const i = css.indexOf(selector);
  if (i < 0) return "";
  const open = css.indexOf("{", i);
  const close = css.indexOf("}", open);
  return open >= 0 && close >= 0 ? css.slice(open + 1, close) : "";
};

// 1. 반응형 그리드 — 셀 고정 위치라 한 셀 hover 확장이 다른 셀을 안 움직임(요구사항 핵심).
ok(/\.share-participants\s*\{[^}]*display:\s*grid/.test(css), ".share-participants display: grid");
ok(/\.share-participants\s*\{[^}]*grid-template-columns:\s*repeat\(auto-fill,\s*minmax\(/.test(css), ".share-participants 반응형 다열(auto-fill minmax)");
ok(/\.share-bans\s*\{[^}]*display:\s*grid/.test(css), ".share-bans display: grid");
ok(!/\.share-participants\s*\{[^}]*flex-wrap:\s*wrap/.test(css), ".share-participants 가로 flex-wrap 제거(그리드 전환 — 형제 reflow 차단)");
ok(/\.share-participant-name\s*\{[^}]*flex:\s*1/.test(css), ".share-participant-name flex:1 (셀 폭 채움 → 평소 여백 낭비 0)");

// 2. 액션 버튼 기본 접힘(컴팩트).
const acts = ruleBody(".share-participant-acts {");
ok(/max-width:\s*0/.test(acts), "액션 버튼 기본 max-width: 0 (접힘)");
ok(/opacity:\s*0/.test(acts), "액션 버튼 기본 opacity: 0 (숨김)");
ok(/overflow:\s*hidden/.test(acts), "액션 버튼 overflow: hidden (펼침 클립)");
ok(/pointer-events:\s*none/.test(acts), "액션 버튼 기본 pointer-events: none (접힘 시 비활성)");

// 3. hover/focus 시 펼침 + 트랜지션(자연스러운 애니메이션).
ok(/transition:[^;]*max-width/.test(acts), "액션 버튼 max-width 트랜지션(펼침 애니메이션)");
ok(/\.share-participant:hover\s*>\s*\.share-participant-acts/.test(css), "칩 hover 시 액션 펼침 규칙");
ok(/\.share-participant:focus-within\s*>\s*\.share-participant-acts/.test(css), "focus-within 시 펼침(키보드 접근성)");
const hoverReveal = css.match(/:hover\s*>\s*\.share-participant-acts[\s\S]{0,40}?:focus-within\s*>\s*\.share-participant-acts\s*\{([^}]*)\}/);
ok(hoverReveal && /max-width:\s*1[0-9][0-9]px/.test(hoverReveal[1]) && /opacity:\s*1/.test(hoverReveal[1]), "펼침 상태 max-width>0 + opacity: 1");

// 4. 터치 기기 폴백(hover 불가 → 항상 노출).
ok(/@media\s*\(hover:\s*none\)\s*\{[^}]*\.share-participant-acts[^}]*opacity:\s*1/.test(css.replace(/\n/g, " ")), "@media (hover: none) 터치 폴백(항상 노출)");

// 5. 캐시버스터 bump(styles.css 변경).
ok(indexHtml.includes("styles.css?v=20260625-member-actions-hover"), "styles.css 캐시버스터 bump");

console.log(`\nverify_member_actions_hover: ${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
