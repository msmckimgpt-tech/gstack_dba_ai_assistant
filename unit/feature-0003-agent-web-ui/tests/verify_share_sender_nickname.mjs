// verify_share_sender_nickname.mjs — 공유 링크 화면 발신자(닉네임) 라벨 **동작** 하네스.
//
// 요청(2026-08-06): 공유 링크 대화 내역에서 발신자가 닉네임이 아닌 '사용자' 고정 명칭으로
// 표시되던 결함(share.js renderMessage 가 roleLabel(msg.role) 로 배지를 채움) 수정.
//
// pytest 쪽 `test_share_sender_nickname.py` 는 **배선**(어느 함수가 어디에 꽂혔는지)을 보고,
// 본 하네스는 **분기 동작**을 본다 — 배포되는 share.js 소스에서 `roleLabel`/`senderLabel`
// 함수 본문을 그대로 추출해 실행하므로, 로직을 테스트에 재구현하지 않는다(가짜 통과 차단).
// jsdom 불요(순수 문자열 로직) — CI 미배선 환경에서도 `node` 만으로 돈다.
//
// 실행: node unit/feature-0003-agent-web-ui/tests/verify_share_sender_nickname.mjs
// 최종 렌더 확인은 PB-0008 Windows-browser 담당(본 하네스는 라벨 값만 검증).

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SHARE_JS = join(__dirname, "..", "src", "static", "share.js");
const src = readFileSync(SHARE_JS, "utf8");

let passed = 0, failed = 0;
function eq(name, actual, expected) {
  if (actual === expected) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name} — expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`); }
}

// share.js 는 단일 IIFE 안에 2-space 들여쓰기 함수가 나열돼 있다. 다음 top-level 함수
// 선언이 안정적인 종료 경계 (선행 주석이 함께 잡혀도 평가에 무해).
function extract(signature) {
  const start = src.indexOf(signature);
  if (start < 0) { console.error(`  ABORT ${signature} 를 share.js 에서 찾지 못했습니다.`); process.exit(2); }
  const nxt = src.indexOf("\n  function ", start + signature.length);
  return src.slice(start, nxt > 0 ? nxt : src.length);
}

const roleLabelSrc = extract("function roleLabel(role)");
const senderLabelSrc = extract("function senderLabel(msg)");

// 클로저 변수 `_shareOwnerUsername`/`_shareIsGroup`(render 가 payload 로 채우는 폴백 기준·
// 게이트)을 주입해 실 소스 함수를 그대로 평가한다.
const makeSenderLabel = new Function(
  "ownerUsername", "isGroup",
  `let _shareOwnerUsername = ownerUsername;\nlet _shareIsGroup = isGroup;\n`
  + `${roleLabelSrc}\n${senderLabelSrc}\nreturn senderLabel;`
);

// ── 1. 발신자 각인이 있는 그룹 메시지 — 닉네임 그대로 (본 요청의 핵심) ────────────
{
  const senderLabel = makeSenderLabel("admin", true);
  eq("① sender_username 각인 → 닉네임 표시",
    senderLabel({ role: "user", meta: { sender_username: "hong.gildong", sender_account_id: 42 } }),
    "hong.gildong");
  eq("① 참여자마다 서로 다른 닉네임으로 갈린다",
    senderLabel({ role: "user", meta: { sender_username: "kim.qa", sender_account_id: 7 } }),
    "kim.qa");
}

// ── 2. id 만 각인(표시명 조회 실패분) — 소유자명으로 오귀속하지 않는다 ───────────
{
  const senderLabel = makeSenderLabel("admin", true);
  eq("② sender_account_id 만 → `사용자 <id>` (소유자명 오귀속 금지)",
    senderLabel({ role: "user", meta: { sender_account_id: 42 } }),
    "사용자 42");
  eq("② 공백뿐인 sender_username 은 미각인 취급",
    senderLabel({ role: "user", meta: { sender_username: "   ", sender_account_id: 42 } }),
    "사용자 42");
}

// ── 3. 각인 없는 메시지 — **1:1 로 확인된 대화에서만** 소유자명 폴백 ──────────────
//     (사용자 결정 2026-08-06 + §18.8 적대 패널 F-2: 그룹 legacy 행은 발신자가 owner 가
//      아닐 수 있어 소유자명이 오귀속이 된다)
{
  const oneOnOne = makeSenderLabel("admin", false);
  eq("③ 1:1 + meta 없음 + 소유자 있음 → 소유자명",
    oneOnOne({ role: "user" }), "admin");
  eq("③ 1:1 + meta 빈 객체 → 소유자명",
    oneOnOne({ role: "user", meta: {} }), "admin");

  const group = makeSenderLabel("admin", true);
  eq("③ **그룹** + 각인 없음 → 소유자명 금지, 익명 토큰",
    group({ role: "user", meta: {} }), "사용자");
  eq("③ is_group 미상(fail-closed=그룹) + 각인 없음 → 익명 토큰",
    makeSenderLabel("admin", true)({ role: "user" }), "사용자");
}

// ── 4. 소유자명조차 없을 때 — 종전 동작('사용자') 보존 ────────────────────────────
{
  const senderLabel = makeSenderLabel("", false);
  eq("④ 소유자명 부재 → 종전 '사용자' 폴백", senderLabel({ role: "user", meta: {} }), "사용자");
}

// ── 5. assistant 는 기존 역할 라벨 유지 (요청 범위 = user 발신자) ─────────────────
{
  const senderLabel = makeSenderLabel("admin", true);
  eq("⑤ assistant → '어시스턴트' 유지",
    senderLabel({ role: "assistant", meta: { sender_username: "admin" } }), "어시스턴트");
  eq("⑤ 알 수 없는 role → 기존 폴백", senderLabel({ role: "system" }), "system");
  eq("⑤ msg 자체가 없어도 죽지 않는다", senderLabel(null), "메시지");
}

// ── 6. 사용자명 원문 보존 — escape 는 렌더 층(textContent) 책임 ───────────────────
{
  const senderLabel = makeSenderLabel("admin", true);
  eq("⑥ 마크업 유사 사용자명도 문자열 그대로 반환(주입 아님 — 배지는 textContent)",
    senderLabel({ role: "user", meta: { sender_username: "<b>x</b>" } }), "<b>x</b>");
}

// ── 7. 사후 추론 각인(attribution_inferred)은 사실이 아니다 — 이름·id 둘 다 미사용 ─
//     fork 보정(_conv_copy_messages)이 미각인 행에 **원본 대화 owner** 를 기입하며 이
//     플래그를 남긴다. 그 행의 실제 발신자는 다른 멤버였을 수 있으므로, 익명·전달 가능한
//     공유 페이지에 확정 이름을 붙이지 않는다 (§18.8 적대 패널 F-1).
{
  const group = makeSenderLabel("bob", true);
  eq("⑦ 추론 각인 + 그룹 → 이름 미사용, 익명 토큰",
    group({ role: "user", meta: { sender_username: "alice", sender_account_id: 9, attribution_inferred: true } }),
    "사용자");
  eq("⑦ 추론 각인은 id 도 쓰지 않는다(그 id 역시 추론값)",
    group({ role: "user", meta: { sender_account_id: 9, attribution_inferred: true } }),
    "사용자");

  const oneOnOne = makeSenderLabel("bob", false);
  eq("⑦ 추론 각인 + 1:1 → 대화 소유자명(그 대화에서는 소유자가 유일 발신자)",
    oneOnOne({ role: "user", meta: { sender_username: "alice", attribution_inferred: true } }),
    "bob");

  eq("⑦ attribution_inferred 가 true 가 아니면(false/부재) 정상 각인 취급",
    group({ role: "user", meta: { sender_username: "alice", attribution_inferred: false } }),
    "alice");
}

console.log(`\n  ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
