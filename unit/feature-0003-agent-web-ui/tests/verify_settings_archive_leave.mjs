// verify_settings_archive_leave.mjs
// gc-settings-archive-leave: 대화 ··· 메뉴의 '보관'을 '설정' 팝업의 '대화 관리' 섹션으로 이동하고,
// 보관 권한이 없는 그룹 대화 참여자에게는 보관 대신 '나가기'(self-leave)를 노출하는 frontend
// 변경을 정적 소스 검증으로 격리 점검한다.
//
//   [변경1] openConversationItemMenu: ··· 메뉴에서 '보관' 항목 제거 (공유 | 설정 만 남음).
//   [변경2] openConversationSettings: '대화 관리' 섹션 추가 —
//             canDeleteConversation → '보관'(deleteConversation), else isGroup → '나가기'(leaveConversation).
//   [변경3] leaveConversation: DELETE /api/conversations/{cid}/members/{본인 account_id} (self-leave).
//
// 실행: node verify_settings_archive_leave.mjs
//   (순수 정적 — jsdom/네트워크 비의존. 함수 본문을 중괄호 밸런스로 추출해 문자열 단언.
//    실제 렌더링/클릭 동작의 최종 확인은 PB-0008 Windows-browser.)

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC = join(__dirname, "..", "src", "static");
const appJs = readFileSync(join(STATIC, "app.js"), "utf8");
const css = /* feature-0038 Cycle 1: styles.css → css/ 7분할 — 순차 concat(byte-동치) */ ["base","shell","chat","drawers","admin","profile","search-audit"]
  .map((n) => readFileSync(join(STATIC, `css/${n}.css`), "utf8")).join("");

let passed = 0, failed = 0;
function ok(name, cond) {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}`); }
}

// function <name>(...) / async function <name>(...) 한 정의 블록을 중괄호 밸런스로 추출.
function extractFn(src, name) {
  const start = src.indexOf(`function ${name}(`);
  if (start < 0) return null;
  let p = src.indexOf("(", start), paren = 0, sigEnd = -1;
  for (let j = p; j < src.length; j++) {
    if (src[j] === "(") paren++;
    else if (src[j] === ")") { paren--; if (paren === 0) { sigEnd = j; break; } }
  }
  let i = src.indexOf("{", sigEnd), depth = 0, end = -1;
  for (; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return end < 0 ? null : src.slice(start, end);
}

const menuFn = extractFn(appJs, "openConversationItemMenu");
const settingsFn = extractFn(appJs, "openConversationSettings");
const leaveFn = extractFn(appJs, "leaveConversation");

ok("openConversationItemMenu 추출됨", !!menuFn);
ok("openConversationSettings 추출됨", !!settingsFn);
ok("leaveConversation 추출됨", !!leaveFn);

// [변경1] ··· 메뉴에서 '보관' 제거, 공유/설정은 유지.
ok("··· 메뉴에 '보관' 항목 없음", !!menuFn && !/makeItem\("보관"/.test(menuFn));
// conv-item-menu 리팩터: makeItem(...) → openFloatingMenu buildItems 의 make(...) 콜백.
ok("··· 메뉴에 '공유' 항목 유지", !!menuFn && /make\("공유"/.test(menuFn));
ok("··· 메뉴에 '설정' 항목 유지", !!menuFn && /make\("설정"/.test(menuFn));

// [변경2] 설정 팝업 '대화 관리' 섹션: 권한 분기 + 보관/나가기.
ok("설정 팝업에 '대화 관리' 섹션 라벨", !!settingsFn && settingsFn.includes("대화 관리"));
ok("설정 팝업이 canDeleteConversation 으로 보관 권한 판정", !!settingsFn && settingsFn.includes("canDeleteConversation(conversation)"));
ok("설정 팝업이 isGroupConversation 으로 그룹 판정", !!settingsFn && settingsFn.includes("isGroupConversation(conversation)"));
ok("설정 팝업: 보관 권한 분기(if (canArchive))", !!settingsFn && /if\s*\(\s*canArchive\s*\)/.test(settingsFn));
ok("설정 팝업: 보관 버튼이 deleteConversation 호출", !!settingsFn && settingsFn.includes("deleteConversation(cid)"));
ok("설정 팝업: 나가기 버튼이 leaveConversation 호출", !!settingsFn && settingsFn.includes("leaveConversation(cid)"));
ok("설정 팝업: 보관/나가기 라벨 모두 존재", !!settingsFn && settingsFn.includes('"보관"') && settingsFn.includes('"나가기"'));
ok("설정 팝업: danger 섹션 클래스 부여", !!settingsFn && settingsFn.includes("conv-settings-sec-danger"));
// 섹션은 보관 권한 또는 그룹일 때만 — 둘 다 아니면 미렌더(가드 존재).
ok("설정 팝업: (canArchive || isGroup) 가드로 조건 렌더", !!settingsFn && /if\s*\(\s*canArchive\s*\|\|\s*isGroup\s*\)/.test(settingsFn));

// [변경3] leaveConversation: 본인 account_id 대상 members DELETE (self-leave).
ok("leaveConversation: members 엔드포인트 호출", !!leaveFn && leaveFn.includes("/members/"));
ok("leaveConversation: DELETE 메서드 사용", !!leaveFn && /method:\s*"DELETE"/.test(leaveFn));
ok("leaveConversation: 본인 account_id(state.user.id) 사용", !!leaveFn && leaveFn.includes("state.user") && leaveFn.includes("id"));
ok("leaveConversation: 확인 다이얼로그(window.confirm)", !!leaveFn && leaveFn.includes("window.confirm"));
ok("leaveConversation: 성공 후 refreshWorkspace 재선택", !!leaveFn && leaveFn.includes("refreshWorkspace"));

// styles.css: danger 섹션 규칙 + 브레이스 균형.
ok("styles.css: .conv-settings-sec-danger 규칙 존재", css.includes(".conv-settings-sec-danger"));
const opens = (css.match(/{/g) || []).length, closes = (css.match(/}/g) || []).length;
ok(`styles.css: 중괄호 균형 (${opens}=${closes})`, opens === closes);

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
