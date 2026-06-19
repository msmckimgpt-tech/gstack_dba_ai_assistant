// Mention parsing (FE) — feature-0009-group-conversation (S3 Chat+Mention).
//
// 백엔드 `modules/mentions.py` 의 canonical 미러. 두 구현은 test_mentions.py 의
// _CANONICAL_CASES 로 계약 고정된다 — 문법을 바꾸면 양쪽 + 케이스표를 함께 고친다.
//
// 문법:
//   - 멘션 = 단어 경계((문자열 시작|비-ASCII단어/@ 문자) 뒤) 의 @ + 이름([A-Za-z0-9._-]+).
//     @ 앞이 ASCII 단어문자([A-Za-z0-9_])면 멘션 아님(이메일 a@b 오매칭 방지).
//   - @assistant(대소문자 무시) = AI 호출 토큰(예약어) → mentionsAssistant=true.
//   - 그 외 @name = 사용자 멘션(주의 환기, LLM 미호출).
//
// ★lookbehind 는 ASCII-explicit([A-Za-z0-9_@]) — Python \w(유니코드) ↔ JS \w(ASCII)
//   차이로 FE↔BE 가 갈리지 않게 고정. "안녕@assistant"(한글 뒤 @) 도 양쪽 동일 인식.
(function (global) {
  "use strict";

  var ASSISTANT_MENTION = "assistant";
  // 'g' 플래그로 매 호출마다 새 정규식(lastIndex 상태 오염 방지).
  function mentionRe() {
    return /(?<![A-Za-z0-9_@])@([A-Za-z0-9._-]+)/g;
  }

  function parseMentions(text) {
    var out = { mentionsAssistant: false, mentionedUsernames: [], tokens: [] };
    if (!text) return out;
    var re = mentionRe();
    var seen = Object.create(null);
    var m;
    while ((m = re.exec(text)) !== null) {
      var name = m[1];
      out.tokens.push({ name: name, start: m.index, end: m.index + m[0].length });
      if (name.toLowerCase() === ASSISTANT_MENTION) {
        out.mentionsAssistant = true;
        continue;
      }
      var key = name.toLowerCase();
      if (!seen[key]) {
        seen[key] = true;
        out.mentionedUsernames.push(name);
      }
    }
    return out;
  }

  function messageInvokesAssistant(text) {
    return parseMentions(text).mentionsAssistant;
  }

  var api = {
    ASSISTANT_MENTION: ASSISTANT_MENTION,
    parseMentions: parseMentions,
    messageInvokesAssistant: messageInvokesAssistant,
  };

  // 전역 노출(app.js classic-script 환경) + module export(테스트) 양쪽 지원.
  global.Mentions = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof window !== "undefined" ? window : this);
