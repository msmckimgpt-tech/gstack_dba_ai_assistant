// hangul-qwerty.js — 한글 자판 ↔ 영문(QWERTY) 자판 상호 변환의 **저장소 단일 primitive**.
//
// 왜 필요한가: 사용자가 한/영 전환을 잊고 타이핑하면 검색이 통째로 빗나간다. "제품 관리"
// 검색창에 `ㅎㅋ` 를 치면 실제로 찾으려던 것은 `gz` 이고, `rmffhqjf` 를 친 사람은 `글로벌`
// 을 찾고 있다. 종전에는 어느 검색창도 이를 흡수하지 못해 **"검색 결과가 없습니다"** 만
// 나왔다(사용자 보고 화면 2건). 이 모듈은 입력을 반대 자판으로 옮긴 **후보 문자열**을
// 만들어, 각 검색 지점이 원문과 후보를 함께 부분일치시키게 한다.
//
// 왜 별도 모듈인가: 이 앱은 ES module 번들이 둘이다(작업 화면 `app.js` 트리 / 관리 콘솔
// `admin.js` 트리) — modal-dismiss.js 와 같은 이유로, 한쪽에 두면 다른 쪽이 복제할 수밖에
// 없고 복제는 곧 두 벌의 매핑표가 어긋나는 결함이 된다. 서버측 동형 구현은
// `src/modules/hangul_qwerty.py` 이며 **두 파일의 매핑표는 같은 값**이어야 한다
// (회귀 잠금: `tests/verify_hangul_qwerty.mjs` + `tests/test_hangul_qwerty.py` 가 동일한
//  케이스 표를 각각 단언한다).
//
// ─── 계약 ──────────────────────────────────────────────────────────────────
// - `hangulToQwerty("ㅈ듀")` → `"web"` — 음절은 초/중/종성으로 분해해 키 시퀀스로.
// - `qwertyToHangul("rmffhqjf")` → `"글로벌"` — 키를 자모로 바꾼 뒤 IME 와 같은 조합
//   오토마타로 음절을 만든다(종성 뒤 모음이 오면 종성을 떼어 다음 음절 초성으로 넘김).
// - `searchVariants(raw)` → 소문자 정규화된 후보 배열(원문 우선, 중복 제거).
// - `matchesSearchQuery(haystack, raw)` → 후보 중 하나라도 부분일치하면 true.
//
// ─── 대소문자 주의 (호출부 계약) ────────────────────────────────────────────
// 쌍자음·이중모음은 **Shift 키**로 입력한다(ㄲ=R, ㅃ=Q, ㅉ=W, ㄸ=E, ㅆ=T, ㅒ=O, ㅖ=P).
// 따라서 `searchVariants` 에는 **소문자화 전의 원문**을 넘겨야 `Rk`→`까` 가 산다. 이미
// 소문자화된 값을 넘기면 변환 자체는 동작하되 쌍자음 구분만 잃는다(안전한 성능 저하).
// 반환 후보는 haystack 이 소문자인 기존 검색 코드와 맞추기 위해 **항상 소문자**다.

/* ── 두벌식 매핑표 (KS X 5002 표준 배열) ──────────────────────────────────── */

const CHO = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];
const JUNG = ["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ", "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"];
const JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];

const HANGUL_BASE = 0xac00;
const HANGUL_LAST = 0xd7a3;

// 자모 → 키 시퀀스. 복합 자모(ㅘ·ㄺ 등)는 두 키의 연속 입력이므로 2글자를 낸다.
const JAMO_TO_KEY = {
  "ㄱ": "r", "ㄲ": "R", "ㄴ": "s", "ㄷ": "e", "ㄸ": "E", "ㄹ": "f", "ㅁ": "a", "ㅂ": "q", "ㅃ": "Q",
  "ㅅ": "t", "ㅆ": "T", "ㅇ": "d", "ㅈ": "w", "ㅉ": "W", "ㅊ": "c", "ㅋ": "z", "ㅌ": "x", "ㅍ": "v", "ㅎ": "g",
  "ㅏ": "k", "ㅐ": "o", "ㅑ": "i", "ㅒ": "O", "ㅓ": "j", "ㅔ": "p", "ㅕ": "u", "ㅖ": "P",
  "ㅗ": "h", "ㅛ": "y", "ㅜ": "n", "ㅠ": "b", "ㅡ": "m", "ㅣ": "l",
  // 복합 모음
  "ㅘ": "hk", "ㅙ": "ho", "ㅚ": "hl", "ㅝ": "nj", "ㅞ": "np", "ㅟ": "nl", "ㅢ": "ml",
  // 겹받침
  "ㄳ": "rt", "ㄵ": "sw", "ㄶ": "sg", "ㄺ": "fr", "ㄻ": "fa", "ㄼ": "fq",
  "ㄽ": "ft", "ㄾ": "fx", "ㄿ": "fv", "ㅀ": "fg", "ㅄ": "qt",
};

// 키 → 자모 (단일 자모만 — 복합은 아래 조합표가 만든다).
const KEY_TO_JAMO = {
  r: "ㄱ", R: "ㄲ", s: "ㄴ", e: "ㄷ", E: "ㄸ", f: "ㄹ", a: "ㅁ", q: "ㅂ", Q: "ㅃ",
  t: "ㅅ", T: "ㅆ", d: "ㅇ", w: "ㅈ", W: "ㅉ", c: "ㅊ", z: "ㅋ", x: "ㅌ", v: "ㅍ", g: "ㅎ",
  k: "ㅏ", o: "ㅐ", i: "ㅑ", O: "ㅒ", j: "ㅓ", p: "ㅔ", u: "ㅕ", P: "ㅖ",
  h: "ㅗ", y: "ㅛ", n: "ㅜ", b: "ㅠ", m: "ㅡ", l: "ㅣ",
};

// 중성 결합(ㅗ+ㅏ=ㅘ …) / 종성 결합(ㄹ+ㄱ=ㄺ …). IME 오토마타가 쓴다.
const JUNG_COMBINE = {
  "ㅗㅏ": "ㅘ", "ㅗㅐ": "ㅙ", "ㅗㅣ": "ㅚ",
  "ㅜㅓ": "ㅝ", "ㅜㅔ": "ㅞ", "ㅜㅣ": "ㅟ",
  "ㅡㅣ": "ㅢ",
};
const JONG_COMBINE = {
  "ㄱㅅ": "ㄳ", "ㄴㅈ": "ㄵ", "ㄴㅎ": "ㄶ",
  "ㄹㄱ": "ㄺ", "ㄹㅁ": "ㄻ", "ㄹㅂ": "ㄼ", "ㄹㅅ": "ㄽ", "ㄹㅌ": "ㄾ", "ㄹㅍ": "ㄿ", "ㄹㅎ": "ㅀ",
  "ㅂㅅ": "ㅄ",
};
// 겹받침 분해 — 종성 뒤에 모음이 오면 **뒷 자음만** 다음 음절 초성으로 넘어간다(닭+ㅏ → 달가).
const JONG_SPLIT = {};
Object.keys(JONG_COMBINE).forEach((pair) => {
  JONG_SPLIT[JONG_COMBINE[pair]] = [pair[0], pair[1]];
});

const CHO_INDEX = {};
CHO.forEach((c, i) => { CHO_INDEX[c] = i; });
const JUNG_INDEX = {};
JUNG.forEach((v, i) => { JUNG_INDEX[v] = i; });
const JONG_INDEX = {};
JONG.forEach((t, i) => { if (t) JONG_INDEX[t] = i; });

const VOWELS = new Set(JUNG.concat(["ㅘ", "ㅙ", "ㅚ", "ㅝ", "ㅞ", "ㅟ", "ㅢ"]));

/* ── 한글 → 영문 ──────────────────────────────────────────────────────────── */

// 완성형 음절 1자를 자모 배열로 분해. 음절이 아니면 null.
export function decomposeSyllable(ch) {
  const code = ch.charCodeAt(0);
  if (code < HANGUL_BASE || code > HANGUL_LAST) return null;
  const offset = code - HANGUL_BASE;
  const jongIdx = offset % 28;
  const jungIdx = Math.floor((offset % 588) / 28);
  const choIdx = Math.floor(offset / 588);
  const out = [CHO[choIdx], JUNG[jungIdx]];
  if (jongIdx) out.push(JONG[jongIdx]);
  return out;
}

/** 한글(완성형 음절·호환 자모)을 그 자리에 대응하는 QWERTY 키 시퀀스로 옮긴다. */
export function hangulToQwerty(input) {
  const s = String(input == null ? "" : input);
  let out = "";
  for (const ch of s) {
    const jamos = decomposeSyllable(ch);
    if (jamos) {
      // 음절: 초성+중성(+종성) 각각의 키 시퀀스를 이어 붙인다.
      for (const j of jamos) out += (JAMO_TO_KEY[j] || j);
      continue;
    }
    // 호환 자모 단독(ㅎ·ㅋ·ㅏ …) 또는 변환 대상이 아닌 문자.
    out += (JAMO_TO_KEY[ch] || ch);
  }
  return out;
}

/* ── 영문 → 한글 ──────────────────────────────────────────────────────────── */

function isVowel(jamo) { return VOWELS.has(jamo); }
function canBeCho(jamo) { return Object.prototype.hasOwnProperty.call(CHO_INDEX, jamo); }
function canBeJong(jamo) { return Object.prototype.hasOwnProperty.call(JONG_INDEX, jamo); }

function composeSyllable(cho, jung, jong) {
  if (!cho || !jung) return null;
  const ci = CHO_INDEX[cho];
  const vi = JUNG_INDEX[jung];
  if (ci == null || vi == null) return null;
  const ti = jong ? (JONG_INDEX[jong] || 0) : 0;
  return String.fromCharCode(HANGUL_BASE + (ci * 21 + vi) * 28 + ti);
}

/**
 * QWERTY 키 시퀀스를 한글 IME 와 동일한 조합 규칙으로 한글 문자열로 옮긴다.
 * 자판에 대응하지 않는 문자(숫자·공백·기호)는 조합을 끊고 그대로 통과시킨다.
 */
export function qwertyToHangul(input) {
  const s = String(input == null ? "" : input);
  let out = "";
  // 조합 중인 음절 상태. cho/jung/jong 중 일부만 찬 상태를 허용한다(IME 와 동일).
  let cho = "";
  let jung = "";
  let jong = "";

  const flush = () => {
    if (cho && jung) {
      out += composeSyllable(cho, jung, jong) || "";
    } else {
      // 미완성 조합은 낱자 그대로 남긴다 — `gz` → `ㅎㅋ` 가 이 경로다.
      out += (cho || "") + (jung || "") + (jong || "");
    }
    cho = ""; jung = ""; jong = "";
  };

  for (const ch of s) {
    const jamo = KEY_TO_JAMO[ch];
    if (!jamo) { flush(); out += ch; continue; }

    if (isVowel(jamo)) {
      if (jong) {
        // 받침 뒤 모음 → 받침(겹받침이면 뒷 자음만)을 다음 음절의 초성으로 이월.
        const split = JONG_SPLIT[jong];
        const carry = split ? split[1] : jong;
        jong = split ? split[0] : "";
        const done = composeSyllable(cho, jung, jong);
        out += done || ((cho || "") + (jung || "") + (jong || ""));
        cho = carry; jung = jamo; jong = "";
        continue;
      }
      if (jung) {
        const merged = JUNG_COMBINE[jung + jamo];
        if (merged) { jung = merged; continue; }
        // 결합 불가한 모음 연속 → 현재 음절을 닫고 새로 시작.
        flush();
        jung = jamo;
        continue;
      }
      if (!cho) { flush(); out += jamo; continue; }   // 초성 없는 모음 — 낱자로 방출.
      jung = jamo;
      continue;
    }

    // 자음.
    if (!cho) { flush(); cho = jamo; continue; }
    if (!jung) {
      // 초성만 있는데 자음이 또 왔다 — `gz`(ㅎ+ㅋ) 처럼 낱자 두 개로 갈린다.
      flush();
      cho = jamo;
      continue;
    }
    if (!jong) {
      if (canBeJong(jamo)) { jong = jamo; continue; }
      // 받침이 될 수 없는 자음(ㄸ·ㅃ·ㅉ) → 음절을 닫고 다음 초성으로.
      flush();
      cho = jamo;
      continue;
    }
    const mergedJong = JONG_COMBINE[jong + jamo];
    if (mergedJong) { jong = mergedJong; continue; }
    flush();
    cho = jamo;
  }
  flush();
  return out;
}

/* ── 검색 후보 ────────────────────────────────────────────────────────────── */

const HANGUL_RE = /[가-힣ㄱ-ㆎ]/;          // 완성형 음절 또는 호환 자모
const QWERTY_KEY_RE = /[a-zA-Z]/;                           // 자판 대응 알파벳

// 자판 변환을 적용할 최소 길이. **원문과 후보 양쪽**에 건다.
//  - 후보 쪽: 한글은 자모 여러 개가 한 음절로 합쳐져 짧은 영문이 1글자 한글이 되기 쉽고
//    (`dk` → `아`), 그 1글자는 아무 목록에나 걸려 **원래 맞던 검색을 오염**한다
//    (실측: 제품 검색 `dk` 가 "DK온라인" 외에 "글로벌 라이브" 까지 잡음).
//  - 원문 쪽: 반대 방향도 같은 문제다 — 1자 한글 `가` 가 `rk` 로 확장되면 `marketing`·
//    `worker` 처럼 무관한 항목이 잡힌다(codex 적대 리뷰 P2). 한 글자 검색어는 그 자체로
//    이미 매우 넓으므로 자판 교정의 이득보다 노이즈가 크다.
// 사용자 의도는 잘못 친 검색어의 구제이지 정상 결과의 확장이 아니다. 요청 예시
// (`ㅎㅋ`→`gz`, `ㅈ듀`→`web`, `rmffhqjf`→`글로벌`, `tmzlem`→`스키드`)는 전부 2자 이상이라 무손실.
const MIN_VARIANT_LEN = 2;

/**
 * 검색어 원문에서 **부분일치에 쓸 후보 문자열들**을 만든다.
 *  - [0] 은 항상 원문(trim + 소문자) — 기존 동작과 동일한 우선 후보.
 *  - 입력에 한글이 있으면 영문 자판 변환본을, 알파벳이 있으면 한글 조합본을 덧붙인다.
 *  - 변환 결과가 원문과 같거나 비면 넣지 않는다(무의미한 중복 스캔 방지).
 * 반환은 항상 소문자 — haystack 을 소문자로 만들어 비교하는 기존 검색 코드와 맞춘다.
 */
export function searchVariants(raw) {
  const src = String(raw == null ? "" : raw).trim();
  const base = src.toLowerCase();
  if (!src) return [];
  const out = [base];
  const push = (v) => {
    const t = String(v || "").trim().toLowerCase();
    if (t.length >= MIN_VARIANT_LEN && out.indexOf(t) === -1) out.push(t);
  };
  if (src.length < MIN_VARIANT_LEN) return out;   // 1자 검색어는 자판 교정 대상 아님(위 주석)
  if (HANGUL_RE.test(src)) push(hangulToQwerty(src));
  if (QWERTY_KEY_RE.test(src)) push(qwertyToHangul(src));
  return out;
}

/**
 * haystack 이 검색어(또는 그 반대 자판 변환본)를 부분 문자열로 포함하는가.
 * haystack 은 소문자가 아니어도 된다 — 내부에서 소문자화한다.
 */
export function matchesSearchQuery(haystack, raw) {
  const variants = searchVariants(raw);
  if (!variants.length) return true;                        // 빈 검색어 = 전체 통과
  const hay = String(haystack == null ? "" : haystack).toLowerCase();
  return variants.some((v) => hay.indexOf(v) !== -1);
}

/**
 * 이미 소문자로 정규화된 haystack 과, 미리 만들어 둔 후보 배열로 매칭한다.
 * 목록 필터처럼 항목마다 반복 호출되는 지점에서 후보 재생성을 피하려고 분리했다.
 */
export function matchesAnyVariant(haystackLower, variants) {
  if (!variants || !variants.length) return true;
  const hay = String(haystackLower == null ? "" : haystackLower);
  return variants.some((v) => hay.indexOf(v) !== -1);
}
