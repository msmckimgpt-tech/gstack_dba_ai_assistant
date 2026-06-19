// FE↔BE 멘션 파서 parity 검증 — feature-0009-group-conversation (S3).
// static/mentions.js 를 BE test_mentions.py 의 _CANONICAL_CASES 와 동일 표로 검증한다.
// 실행: node unit/feature-0003-agent-web-ui/tests/verify_mentions.mjs
import { createRequire } from "module";
const require = createRequire(import.meta.url);
const Mentions = require("../src/static/mentions.js");

// (text, mentionsAssistant, mentionedUsernames) — test_mentions.py _CANONICAL_CASES 와 동일.
const CASES = [
  ["", false, []],
  ["hello world", false, []],
  ["@assistant hi", true, []],
  ["hey @assistant please", true, []],
  ["@Assistant caps insensitive", true, []],
  ["ping @alice and @bob", false, ["alice", "bob"]],
  ["@alice @assistant @alice again", true, ["alice"]],
  ["send mail a@b.com no mention", false, []],
  ["ask foo@assistant.com is email", false, []],
  ["안녕@assistant 질문", true, []],
  ["(@assistant) parenthesized", true, []],
  ["@bob, hi there", false, ["bob"]],
  ["@user_name-1.x ok", false, ["user_name-1.x"]],
  ["no@space here", false, []],
];

let failures = 0;
for (const [text, wantAssistant, wantUsers] of CASES) {
  const got = Mentions.parseMentions(text);
  const okA = got.mentionsAssistant === wantAssistant;
  const okU = JSON.stringify(got.mentionedUsernames) === JSON.stringify(wantUsers);
  if (!okA || !okU) {
    failures++;
    console.error(
      `FAIL ${JSON.stringify(text)} -> assistant=${got.mentionsAssistant}(want ${wantAssistant}) ` +
        `users=${JSON.stringify(got.mentionedUsernames)}(want ${JSON.stringify(wantUsers)})`
    );
  }
}

if (failures) {
  console.error(`verify_mentions: ${failures} FAIL (FE↔BE divergence)`);
  process.exit(1);
}
console.log(`verify_mentions: PASS (${CASES.length} canonical cases, FE matches BE)`);
