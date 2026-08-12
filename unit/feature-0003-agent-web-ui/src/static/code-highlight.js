// code-highlight — 파일 유형별 구문 하이라이트 (저장소 단일 primitive)
//
// 첨부 버전 비교 화면(`app/attach-diff.js`)은 두 버전의 본문을 **평문**으로만 보여줬다.
// SQL·JSON·YAML·XML·CSV 같은 파일은 예약어·키·문자열이 색으로 갈라지지 않으면, 바뀐 줄을
// 찾았어도 그 줄이 *무엇을* 바꾼 것인지(테이블명인가 값인가 주석인가) 눈으로 훑기 어렵다.
//
// ## 설계 원칙
//
//  - **vendor 무추가**: 외부 하이라이터(highlight.js / prism) 없이 경량 토크나이저로 처리한다.
//    기존 답변 말풍선의 ```sql 블록 하이라이트와 같은 방침이며, 그 SQL 예약어 목록의 **정본이
//    이 모듈**이다(app.js 가 여기서 import — 목록을 두 벌 두면 한쪽만 갱신되는 결함이 예약된다.
//    `modal-dismiss.js` 주석이 기록한 "복제가 곧 결함 기전" 과 같은 이유).
//  - **XSS 무첨가**: 토큰 텍스트는 항상 `textContent` 로만 넣는다. 이 모듈에 innerHTML 경로는
//    없다 — 첨부 본문은 사용자가 올린 임의 바이트이므로 문자열 조립은 금지다.
//  - **확장은 레지스트리 한 항목**: 언어 추가 = `LANGS` 에 `{ exts, tokenize }` 를 넣는 것뿐이고
//    호출자(`paintCodeInto`)는 바뀌지 않는다. 1차 범위는 SQL + 구조화 데이터(JSON/YAML/XML/CSV)
//    였고(사용자 결정 2026-08-06: "SQL + 구조화 데이터를 우선 추가하되, 차후 확장될 수
//    있습니다"), 그 예고대로 **Markdown 을 같은 자리에 추가**했다(사용자 요청 2026-08-12:
//    "첨부파일 중 '.md' 파일에 대한 포멧도 내부적으로 처리"). Python·JS·Shell 등도 동일 경로.
//  - **라인 독립 토큰화**: diff 는 행 단위로 렌더되므로 토큰화도 행 단위다. 여러 줄에 걸친
//    블록 주석(`/* … */`)이나 멀티라인 문자열은 **각 행이 독립 판정**된다. 행 상태를 이어붙이는
//    방식을 택하지 않은 이유: 맥락 축약 뷰는 중간을 `gap` 으로 생략하므로 상태가 끊긴 지점부터
//    색이 통째로 어긋난다(무색보다 나쁘다). 한계를 알고 고른 절충이며 아래 `MAX_LINE_LEN` 과
//    같은 성격의 방어다.
//  - **미지원이면 무색**: 확장자가 레지스트리에 없으면 `detectCodeLanguage` 가 `null` 을 주고
//    호출자는 평문 경로를 그대로 쓴다. 모르는 파일에 아무 색이나 칠하면 **없는 구조를 있는 것처럼**
//    보이게 만든다(기존 `looksLikeSql` 가 답변 diff 에서 같은 이유로 보수적인 것과 동형).
//
// ## 토큰 클래스
//
// `code-tok-*` 로 통일한다(언어 중립 — 같은 팔레트를 SQL·JSON·XML 이 공유한다).
// 기존 답변 말풍선의 `sql-tok-*` 는 **그대로 유지**한다: 그쪽은 이미 라이브에서 검증된
// 표면이고, 이번 변경의 범위는 첨부 diff 화면이다. 두 prefix 의 통합은 REPORT §8 원장.

// ── SQL 토큰 지식 (정본 — app.js 가 import) ──────────────────────────────────
// 방언 공통 예약어(대문자 비교). 집계/스칼라 함수명은 제외 — 뒤에 '(' 가 오면 함수로
// 분류하는 휴리스틱이 담당한다(함수 목록 유지 불필요).
export const SQL_HL_KEYWORDS = new Set([
  "SELECT","FROM","WHERE","AND","OR","NOT","NULL","IS","IN","LIKE","ILIKE",
  "RLIKE","REGEXP","BETWEEN","EXISTS","ANY","SOME","JOIN","INNER","LEFT",
  "RIGHT","FULL","OUTER","CROSS","NATURAL","ON","USING","GROUP","BY","ORDER",
  "HAVING","LIMIT","OFFSET","UNION","INTERSECT","EXCEPT","MINUS","ALL",
  "DISTINCT","AS","INSERT","INTO","VALUES","UPDATE","SET","DELETE","CREATE",
  "ALTER","DROP","TRUNCATE","TABLE","VIEW","MATERIALIZED","INDEX","SEQUENCE",
  "TRIGGER","DATABASE","SCHEMA","WITH","RECURSIVE","CASE","WHEN","THEN","ELSE",
  "END","ASC","DESC","NULLS","FIRST","LAST","PRIMARY","KEY","FOREIGN",
  "REFERENCES","CONSTRAINT","UNIQUE","CHECK","DEFAULT","AUTO_INCREMENT",
  "IDENTITY","ENGINE","PROCEDURE","FUNCTION","RETURNS","RETURN","DECLARE",
  "BEGIN","IF","ELSEIF","WHILE","LOOP","FOR","CALL","EXEC","EXECUTE","GRANT",
  "REVOKE","COMMIT","ROLLBACK","SAVEPOINT","TRANSACTION","START","EXPLAIN",
  "ANALYZE","DESCRIBE","SHOW","USE","ADD","COLUMN","MODIFY","CHANGE","RENAME",
  "TO","CASCADE","RESTRICT","TEMPORARY","TEMP","REPLACE","IGNORE","PARTITION",
  "OVER","WINDOW","ROWS","RANGE","UNBOUNDED","PRECEDING","FOLLOWING","CURRENT",
  "ROW","TOP","FETCH","NEXT","ONLY","LATERAL","PIVOT","UNPIVOT","MERGE",
  "MATCHED","OUTPUT","GO","ESCAPE","COLLATE","INTERVAL","TRUE","FALSE",
  "UNKNOWN","PRINT","INTO","SEPARATOR","STRAIGHT_JOIN","FORCE","LOCK","UNLOCK",
]);
// 데이터 타입(대문자 비교).
export const SQL_HL_TYPES = new Set([
  "INT","INTEGER","BIGINT","SMALLINT","TINYINT","MEDIUMINT","DECIMAL","NUMERIC",
  "FLOAT","DOUBLE","REAL","BIT","BOOLEAN","BOOL","CHAR","VARCHAR","NCHAR",
  "NVARCHAR","VARCHAR2","TEXT","TINYTEXT","MEDIUMTEXT","LONGTEXT","NTEXT",
  "DATE","DATETIME","DATETIME2","SMALLDATETIME","TIMESTAMP","TIME","YEAR",
  "BLOB","TINYBLOB","MEDIUMBLOB","LONGBLOB","BINARY","VARBINARY","JSON","JSONB",
  "UUID","SERIAL","BIGSERIAL","MONEY","ENUM","GEOMETRY","XML","CLOB","NUMBER",
  "UNSIGNED","ZEROFILL",
]);

// 한 줄이 이보다 길면 토큰화를 건너뛰고 평문으로 둔다 — minified JSON 한 줄(수십만 자)에
// 정규식을 태우면 6,000행 표에서 프레임을 잡아먹는다. 색은 편의이고 응답성은 계약이다.
const MAX_LINE_LEN = 4000;

// 토큰 목록 조립기. 인접한 무색 조각은 하나의 텍스트 노드로 합쳐 DOM 노드 수를 줄인다.
function _emitter() {
  const out = [];
  let pending = "";
  return {
    plain(s) { if (s) pending += s; },
    tok(cls, s) {
      if (!s) return;
      if (pending) { out.push({ cls: null, text: pending }); pending = ""; }
      out.push({ cls, text: s });
    },
    done() {
      if (pending) { out.push({ cls: null, text: pending }); pending = ""; }
      return out;
    },
  };
}

// ── SQL ─────────────────────────────────────────────────────────────────────
// 우선순위: 주석 → 문자열 → 백틱/대괄호 식별자 → 단어(@변수·예약어·타입·함수) → 숫자 → 기타.
// 문자열 대안의 닫는 인용부호는 **optional**(`'?`/`"?`)이다 — 필수로 두면 닫히지 않은 리터럴
// (`'"' + '\\"'.repeat(1000)` 류·멀티라인 문자열의 첫 줄)에서 매칭이 실패하며 위치마다 줄 끝까지
// 훑어 2차 비용이 된다(§18.8 security P2 · JSON 2,001자 1.10ms → 0.02ms). 부수 효과도 옳은
// 방향이다: 닫히지 않은 리터럴이 줄 끝까지 string 색을 받는 것은 편집기 관례이며, 종전처럼
// catch-all 로 떨어져 무색이 되는 것보다 멀티라인 문자열의 첫 줄을 정확히 표현한다.
// 문자열은 linear(비-backtrack) 형태로 ReDoS 회피. '#' 라인주석은 T-SQL `#temp` 와 충돌하므로
// 미지원(`--` 과 한 줄 안의 `/* */` 만) — MySQL '# 주석' 은 색만 안 입고 깨지지 않는다.
// T-SQL 대괄호 식별자는 **내용 문자 집합과 길이를 함께 제한**한다. 무제한 `\[[^\]]*\]` 는
// `"[".repeat(4000)` 같은 입력에서 매 위치마다 끝까지 스캔해 2차 비용이 됐고(4,000자 4.69ms,
// §18.8 security P2), 길이만 256 으로 묶어도 위치마다 256자를 훑어 1.98ms 가 남았다.
// 식별자 문자만 허용하면 `[[[[…` 는 **첫 문자에서** 실패한다(실측 0.02ms). 실제 식별자
// (`[my table]`·`[dbo]`·`[order#1]`)는 그대로 인식된다.
const SQL_RE = /(\/\*[\s\S]*?(?:\*\/|$)|--[^\n]*)|('[^']*(?:''[^']*)*'?|"[^"]*(?:""[^"]*)*"?)|(`[^`]*(?:``[^`]*)*`|\[[\w$#@ .-]{1,128}\])|(@{0,2}[A-Za-z_][A-Za-z0-9_$]*)|(0[xX][0-9A-Fa-f]+|\d+\.?\d*(?:[eE][+-]?\d+)?)|([\s\S])/g;

function tokenizeSql(text) {
  const e = _emitter();
  SQL_RE.lastIndex = 0;
  let m;
  while ((m = SQL_RE.exec(text)) !== null) {
    if (m[1]) e.tok("code-tok-comment", m[1]);
    else if (m[2]) e.tok("code-tok-string", m[2]);
    else if (m[3]) e.plain(m[3]);                    // 인용 식별자 → 평문(이름은 이름이다)
    else if (m[4]) {
      const w = m[4];
      if (w[0] === "@") e.tok("code-tok-var", w);
      else {
        const W = w.toUpperCase();
        if (SQL_HL_KEYWORDS.has(W)) e.tok("code-tok-keyword", w);
        else if (SQL_HL_TYPES.has(W)) e.tok("code-tok-type", w);
        else if (/^\s*\(/.test(text.slice(SQL_RE.lastIndex))) e.tok("code-tok-func", w);
        else e.plain(w);                              // 일반 식별자 → 평문
      }
    }
    else if (m[5]) e.tok("code-tok-number", m[5]);
    else e.plain(m[0]);                               // 공백·연산자·구두점 → 평문
  }
  return e.done();
}

// ── JSON ────────────────────────────────────────────────────────────────────
// key 와 값 문자열을 **구분**하는 것이 핵심이다 — 둘 다 따옴표 문자열이라 같은 색이면
// `"status": "status"` 같은 줄에서 어느 쪽이 바뀐 것인지 보이지 않는다. 뒤에 `:` 가 오는
// 문자열만 key 로 칠한다(JSON5 무인용 key 는 미지원 — 규격 밖).
const JSON_RE = /("(?:[^"\\]|\\.)*"?)|(-?\d+\.?\d*(?:[eE][+-]?\d+)?)|\b(true|false|null)\b|([{}\[\],:])|([\s\S])/g;

function tokenizeJson(text) {
  const e = _emitter();
  JSON_RE.lastIndex = 0;
  let m;
  while ((m = JSON_RE.exec(text)) !== null) {
    if (m[1]) {
      const isKey = /^\s*:/.test(text.slice(JSON_RE.lastIndex));
      e.tok(isKey ? "code-tok-key" : "code-tok-string", m[1]);
    }
    else if (m[2]) e.tok("code-tok-number", m[2]);
    else if (m[3]) e.tok("code-tok-bool", m[3]);
    else if (m[4]) e.tok("code-tok-punct", m[4]);
    else e.plain(m[0]);
  }
  return e.done();
}

// ── YAML ────────────────────────────────────────────────────────────────────
// 라인 지향이라 diff 와 궁합이 좋다. 판정 순서: 주석 → (라인 선두) key → 앵커/별칭 →
// 문자열 → bool/null → 숫자 → 나머지 평문.
// `#` 은 **공백 뒤 또는 줄 시작**일 때만 주석이다 — `a#b` 는 스칼라 값의 일부이고, 색을
// 잘못 입히면 나머지 줄이 통째로 회색이 되어 변경을 놓친다.
//
// ⚠️ 성능 — 이 정규식이 2차 비용의 주범이었다(§18.8 security P2 실측: `"- ".repeat(2000)` 한 줄
// 7.99ms → 1MB 원본 누적 4.4초 main-thread 정지). 세 가지를 함께 고쳐 **0.015ms**(358×)로 내렸다:
//   ① `\s*` 와 `-\s+` 의 `\s` 중복 제거(`[ \t]` 로 고정) — 같은 문자를 두 파트가 다투지 않게.
//   ② 반복 상한 — 리스트 dash 는 `{0,8}`, key 본문은 `{0,512}`. 한 줄에 9중 dash 나 512자 key 는
//      실재하지 않으므로 인식 능력 손실 0(경계 표본으로 확인: `retries:`·`- name:`·`- - deep:`·
//      공백 포함 key 모두 종전과 동일 결과).
//   ③ 아래 호출부에서 **`:` 가 없는 줄은 아예 시도하지 않는다** — 비용은 전부 "매칭 실패" 경로에서
//      났고, key 없는 줄이 YAML diff 의 다수다.
const YAML_KEY_RE = /^([ \t]*(?:-[ \t]+){0,8})([^\s#][^:#]{0,512}?)([ \t]*:)(?=\s|$)/;
// bool 대안에 `(?=[ \t]*(#|$))` 를 붙여 **스칼라 전체가 bool 일 때만** 칠한다. 초판은 단어
// 경계만 봐서 `note: turn it on when ready` 의 `on` 이나 `msg: No parking allowed` 의 `No` 가
// 문장 중간에서 boolean 색을 받았다 — 인용 스칼라는 올바르게 string 이라 불일치가 더 오독을
// 부른다(§18.8 security P2). "무색이 오색보다 낫다" 는 이 모듈의 선언과 정합.
const YAML_RE = /(^|\s)(#.*)$|("(?:[^"\\]|\\.)*"|'[^']*(?:''[^']*)*')|(&[\w.-]+|\*[\w.-]+)|\b(true|false|yes|no|on|off|null|~)\b(?=[ \t]*(?:#|$))|(-?\d+\.?\d*(?:[eE][+-]?\d+)?)|([\s\S])/gi;

function tokenizeYaml(text) {
  const e = _emitter();
  let rest = text;
  // ① 라인 선두 key — `key:` / `- key:` 형태만. 값 쪽은 ② 가 이어서 처리한다.
  //    `:` 가 없으면 매칭이 성립할 수 없으므로 정규식을 돌리지 않는다(위 성능 주석 ③).
  const km = rest.indexOf(":") === -1 ? null : YAML_KEY_RE.exec(rest);
  if (km) {
    e.plain(km[1]);
    e.tok("code-tok-key", km[2]);
    e.plain(km[3]);
    rest = rest.slice(km[0].length);
  }
  YAML_RE.lastIndex = 0;
  let m;
  while ((m = YAML_RE.exec(rest)) !== null) {
    if (m[2]) { e.plain(m[1] || ""); e.tok("code-tok-comment", m[2]); }
    else if (m[3]) e.tok("code-tok-string", m[3]);
    else if (m[4]) e.tok("code-tok-var", m[4]);       // &anchor / *alias
    else if (m[5]) e.tok("code-tok-bool", m[5]);
    else if (m[6]) e.tok("code-tok-number", m[6]);
    else e.plain(m[0]);
  }
  return e.done();
}

// ── XML / HTML ──────────────────────────────────────────────────────────────
// 태그명·속성명·속성값을 가른다. 라인 독립이므로 열린 태그가 다음 행으로 이어지면 그 행의
// 속성은 태그 문맥 없이 판정되는데, 속성 패턴(`name=` + 인용값)이 그 자체로 충분히 특징적이라
// 실사용에서 문제되지 않는다(무색으로 떨어질 뿐 오색은 아니다).
const XML_RE = /(<!--[\s\S]*?(?:-->|$))|(<[?!]?\/?)([A-Za-z_][\w:.-]*)|([A-Za-z_][\w:.-]*)(?=[ \t]*=)|("(?:[^"\\]|\\.)*"?|'[^']*'?)|(&[#\w]+;)|(\/?>)|([\s\S])/g;

function tokenizeXml(text) {
  const e = _emitter();
  XML_RE.lastIndex = 0;
  // 속성명·속성값은 **열린 태그 안에서만** 인정한다. 초판은 문맥 없이 `name=` 패턴만 봐서
  // 본문 산문 `<p>Total price = 100 USD</p>` 의 `price` 나 `Rows affected = 3` 의 `affected` 가
  // 속성 색을 받았다 — 없는 마크업 구조를 있는 것처럼 보이게 만든다(§18.8 security P2).
  // `.html` 도 이 화면의 정상 대상이라 산문 diff 가 흔하다. 라인 독립이므로 여러 행에 걸친
  // 열린 태그의 2행 이후는 속성이 무색으로 남는다 — 이 모듈의 "무색 > 오색" 원칙대로다.
  let inTag = false;
  let m;
  while ((m = XML_RE.exec(text)) !== null) {
    if (m[1]) e.tok("code-tok-comment", m[1]);
    else if (m[3]) {
      e.tok("code-tok-punct", m[2]);
      e.tok("code-tok-tag", m[3]);
      inTag = !m[2].startsWith("</");   // 닫는 태그 안에는 속성이 없다
    }
    else if (m[4]) { if (inTag) e.tok("code-tok-attr", m[4]); else e.plain(m[4]); }
    else if (m[5]) { if (inTag) e.tok("code-tok-string", m[5]); else e.plain(m[5]); }
    else if (m[6]) e.tok("code-tok-var", m[6]);       // &amp; 류 엔티티
    else if (m[7]) { e.tok("code-tok-punct", m[7]); inTag = false; }
    else e.plain(m[0]);
  }
  return e.done();
}

// ── CSV / TSV ───────────────────────────────────────────────────────────────
// 구분자만 눈에 띄게 하는 것이 목적이다 — 열이 하나 밀린 변경(구분자 추가/삭제)은 평문에서
// 사실상 보이지 않는다. 인용 필드와 순수 숫자 필드를 함께 갈라 열 성격을 읽게 한다.
// 구분자는 확장자로 정한다(`.tsv` → 탭). `.csv` 안에서 세미콜론을 쓰는 방언은 미지원 —
// 첫 줄 추론은 diff 행마다 결과가 달라질 수 있어 채택하지 않았다(행 독립 원칙).
function _makeCsvTokenizer(delim) {
  // 필드 = 인용 문자열 | 구분자 아닌 문자열. 인용 안의 구분자는 필드 경계가 아니다.
  //
  // ⚠️ 마지막 `([\s\S])` catch-all 은 **원문 무손실의 load-bearing 부품**이다. 짝이 맞지 않는
  // 따옴표(`a,"b` — diff 뷰어는 깨진 CSV·잘린 원본도 받는다)는 인용 필드 대안이 매칭에 실패하고
  // 무인용 필드 대안은 `"` 를 제외하므로, catch-all 이 없으면 그 한 글자가 **조용히 사라진다**
  // (fuzz 하네스 C2 가 1,200 표본 중 152건에서 적발 — 초판엔 이 대안이 없었다).
  const d = delim === "\t" ? "\\t" : delim;
  const re = new RegExp(`("(?:[^"]|"")*")|(${d})|([^${d}"]+)|([\\s\\S])`, "g");
  return function tokenizeCsv(text) {
    const e = _emitter();
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(text)) !== null) {
      if (m[1]) e.tok("code-tok-string", m[1]);
      else if (m[2]) e.tok("code-tok-delim", m[2]);
      else if (m[4]) e.plain(m[4]);   // 짝 없는 따옴표 등 — 무색으로 보존(무손실이 계약)
      else if (m[3]) {
        // 숫자만 있는 필드는 숫자색, 그 밖은 평문(헤더 행도 평문 — 행 독립이라 헤더를
        // 알 수 없다. 헤더를 추정해 칠하면 첫 행만 특별해져 스크롤 중 혼란을 만든다).
        if (/^\s*-?\d+\.?\d*(?:[eE][+-]?\d+)?\s*$/.test(m[3])) e.tok("code-tok-number", m[3]);
        else e.plain(m[3]);
      }
    }
    return e.done();
  };
}

// ── Markdown ────────────────────────────────────────────────────────────────
// 산문 마크업이라 앞의 다섯 언어와 성격이 다르다. 여기서 색이 하는 일은 "예약어를 찾는 것"이
// 아니라 **문서의 뼈대(구조 표식)와 산문을 가르는 것**이다 — 제목·인용·리스트·표·링크·코드가
// 본문과 같은 색이면, diff 에서 바뀐 줄이 *구조* 변경인지 *문장* 변경인지 눈으로 갈리지 않는다.
//
// 판정은 **블록(줄 머리) → 인라인** 2단이다. Markdown 의 블록 구성요소는 대부분 줄 앵커라
// 라인 독립 원칙과 궁합이 좋다(제목·리스트·인용·구분선·표 정렬행이 모두 한 줄 안에서 닫힌다).
//
// ⚠️ **알려진 한계 — fenced code block**: 여는 ``` 과 닫는 ``` 사이의 줄들은 원래 코드지만,
// 라인 독립 판정이라 markdown 규칙으로 읽힌다(코드 안 `# comment` 가 제목색, `- item` 이
// 리스트 마커색). SQL 의 여러 줄 주석과 **같은 성격의 절충**이며(위 설계 원칙의 "라인 독립
// 토큰화" 참조), 상태를 이어붙이지 않는 이유도 같다 — 맥락 축약 뷰가 중간을 생략하므로 상태가
// 끊긴 지점부터 색이 통째로 어긋난다. 대신 fence 줄 자체를 눈에 띄게 칠해 "여기부터 코드" 를
// 읽히게 한다.
//
// ⚠️ **`_강조_` 는 의도적 미지원**: 이 화면에 오는 `.md` 는 DB·SQL·운영 문서가 다수라
// `snake_case` 컬럼명과 `__dunder__` 가 흔하다. 밑줄 강조를 인식하면 그것들이 통째로 강조색을
// 받아 **없는 강조를 만든다**. 이 모듈의 "무색이 오색보다 낫다" 선언대로 `*강조*`·`**강조**`·
// `~~취소선~~` 만 인식한다.
//
// 색은 새 변수를 만들지 않고 기존 9개 팔레트를 재사용한다(대비 회귀는 하네스 G2 가 매 실행
// 재계산하므로, 변수를 늘리지 않는 편이 검증면을 넓히지 않으면서 안전하다):
//   제목/`===` → keyword · 강조/fence 언어명 → type · 인라인코드/URL → string ·
//   링크 라벨 → func · 참조정의 라벨 → key · 인용/fence 마커 → comment ·
//   리스트 마커/구분선/표 정렬행/링크 구두점 → punct · 표 파이프 → delim · 체크박스 → bool

// 줄 머리(블록) 판정 — 배열 순서가 곧 우선순위. 모두 `^` 앵커라 위치당 1회만 시도된다.
const MD_FENCE_RE     = /^([ \t]{0,3})(`{3,}|~{3,})(.*)$/;
// CommonMark 대로 `#` 뒤에 공백을 요구한다 — `#hashtag`·`#1` 을 제목으로 칠하지 않기 위해.
const MD_ATX_RE       = /^[ \t]{0,3}#{1,6}(?:[ \t][\s\S]*)?$/;
const MD_SETEXT_H1_RE = /^[ \t]{0,3}=+[ \t]*$/;
// 구분선 = `---` / `***` / `___` (3개 이상). setext H2 밑줄·YAML front-matter 경계도 여기로 온다.
const MD_RULE_RE      = /^[ \t]{0,3}(?:\*[ \t]*){3,}$|^[ \t]{0,3}(?:-[ \t]*){3,}$|^[ \t]{0,3}(?:_[ \t]*){3,}$/;
const MD_QUOTE_RE     = /^([ \t]{0,3})((?:>[ \t]?){1,8})/;
const MD_LIST_RE      = /^([ \t]{0,32})([-*+]|\d{1,9}[.)])([ \t]+)/;
const MD_TASK_RE      = /^(\[[ xX]\])(?=[ \t]|$)/;
const MD_REFDEF_RE    = /^([ \t]{0,3}\[)([^\]\n]{1,200})(\]:)/;

// GFM 표 정렬행(`|---|:--:|`). 값싼 문자 구성 필터로 후보를 거른 뒤 **셀 단위**로 확인한다.
// 정규식 `(...)+` 반복을 쓰지 않는 이유는 YAML 과 같다(실패 경로 2차 비용) — split 은 선형이고,
// 셀별 검사는 짧은 문자열에만 걸린다.
//
// ⚠️ 초판은 "`|` 와 `-` 를 포함하고 `[ \t|:-]` 로만 구성" 만 봤는데, 그러면 **리스트 항목
// `- |` 이 줄 전체 회색**이 됐다(codex 적대 리뷰 [P2]). 셀 문법을 실제로 확인하고, **선두 `|` 가
// 없으면 셀이 2개 이상**일 것을 요구해 그 오독을 막는다(`|---|` 같은 1열 표는 선두 `|` 로 성립,
// `- |` 는 선두 `|` 가 없고 셀도 1개라 탈락 → 리스트 마커 규칙으로 넘어간다).
const MD_TABLE_CELL_RE = /^[ \t]*:?-+:?[ \t]*$/;
function _mdIsTableDelimRow(s) {
  if (!/^[ \t|:-]+$/.test(s)) return false;          // 1차 필터(선형) — 후보 아니면 즉시 탈락
  const body = s.trim();
  const lead = body.charAt(0) === "|";
  const inner = body.replace(/^\|/, "").replace(/\|$/, "");
  if (inner.indexOf("|") === -1 && !lead) return false;   // 선두 `|` 없는 1-셀은 표가 아니다
  const cells = inner.split("|");
  if (cells.length === 0) return false;
  for (let i = 0; i < cells.length; i++) {
    if (!MD_TABLE_CELL_RE.test(cells[i])) return false;   // 셀 = (`:`)`-`+(`:`) 만
  }
  return true;
}

// 강조 구간의 양 끝이 공백이면 강조가 아니다(CommonMark: 여는 표식 뒤·닫는 표식 앞 공백 금지).
// `2 * 3 * 4` 의 `* 3 *` 를 강조로 칠하지 않기 위한 방어 — 정규식으로 밀어넣으면 역추적이
// 늘어나므로 매칭 후 코드에서 판정한다(비용 O(1)).
function _mdEmphOk(matched, markLen) {
  const inner = matched.slice(markLen, matched.length - markLen);
  return inner.length > 0 && !/^[ \t]/.test(inner) && !/[ \t]$/.test(inner);
}

// 인라인 표식. 반복 상한(`{0,200}`·`{0,300}`)은 YAML 과 같은 이유 — 실재하는 라벨·URL 길이를
// 넘지 않으면서 실패 경로의 스캔을 묶는다. 마지막 `([\s\S])` catch-all 이 **무손실의
// load-bearing 부품**인 것도 CSV 와 동일하다(짝 없는 `*`·`[` 는 여기로 떨어져 무색 보존).
//
//  1 백슬래시 이스케이프  2 인라인 코드  3~7 링크/이미지  8 `[` 런  9 자동링크
// 10 강조(`**`/`~~`)    11 강조(`*`)   12 표 파이프    13 산문 런  14 catch-all
// (8·13·14 는 모두 무색이라 호출부 분기가 필요 없다 — 마지막 `else e.plain(m[0])` 가 함께 받는다.)
//
// ⚠️ 성능 — 링크 대안이 이 토크나이저의 2차 비용 지점이다(YAML 의 key 대안과 같은 자리).
// `"[".repeat(4000)` 같은 줄은 위치마다 라벨 상한까지 훑고 `](` 에서 실패한다(실측 2.98ms —
// 하네스 I1 상한 1.0ms 초과). 두 가지로 묶었다:
//   ① **사전 가드** — 줄에 `](` 와 `)` 가 둘 다 없으면 완전한 인라인 링크가 성립할 수 없으므로
//      링크 대안을 **끈 정규식**을 쓴다(YAML 의 "`:` 없으면 key 정규식을 돌리지 않는다" 와 동형).
//      의미 변화 0 — 그 줄에서는 원래 매칭될 수 없는 대안이다.
//   ② 라벨·URL 200자 상한 + **라벨 본문에서 `[` 를 제외**. 가드는 `…[[[[](x)` 처럼 `](` 를
//      끝에 단 줄로 우회될 수 있는데(실측 2.18ms), 라벨에서 `[` 를 빼면 그런 줄은 각 `[`
//      위치에서 **첫 문자에 실패**한다(0.03ms). 대괄호가 중첩된 라벨(`[see [1]](u)`)은 무색으로
//      떨어질 뿐 손실은 없다 — 이 모듈의 "무색 > 오색" 과 정합.
const _MD_LINK_ALT = "(!?\\[)([^\\]\\[\\n]{0,200})(\\]\\()([^)\\n]{0,200})(\\))";
// 링크 대안을 끈 변형 — 그룹 번호(3~7)를 보존해야 호출부 분기가 하나로 유지된다(아래 `[` 런과
// 산문 런의 번호도 두 변형에서 같아야 한다).
// `[^\s\S]` 는 공집합 문자클래스라 절대 매칭되지 않는다(대안 전체가 즉시 실패).
const _MD_NOLINK_ALT = "([^\\s\\S])([^\\s\\S])([^\\s\\S])([^\\s\\S])([^\\s\\S])";
const _mdInlineSrc = (linkAlt, runClass) =>
  "(\\\\[\\\\`*_~[\\]()#+\\-.!|>])" +
  "|(``[^`\\n]{0,300}``|`[^`\\n]{0,300}`)" +
  "|" + linkAlt +
  // 링크를 이루지 못한 `[` 연속 — **반드시 링크 대안 뒤**에 온다(진짜 링크가 먼저 이긴다).
  // 없으면 `"[".repeat(4000)` 이 1글자씩 catch-all 로 떨어져 문자마다 13-그룹 match 배열을
  // 할당한다(실측 0.80ms → 0.06ms). 방출은 무색이라 아래 `else e.plain(m[0])` 가 함께 받는다.
  "|(\\[+)" +
  "|(<(?:https?|ftp|mailto):[^>\\s]{0,200}>)" +
  "|(\\*\\*[^*\\n]{1,300}\\*\\*|~~[^~\\n]{1,300}~~)" +
  "|(\\*[^*\\s\\n][^*\\n]{0,300}\\*)" +
  // 연속 파이프는 **한 토큰**으로 묶는다(`\|+`). 실제 표에서 파이프는 셀 사이라 붙어 있지 않으므로
  // 화면은 동일하고(같은 클래스·인접), 병리 입력(`"|".repeat(4000)`)에서 span 4,000개가 1개로
  // 줄어 DOM 비용이 사라진다 — codex 적대 리뷰 [P2](span 폭증) 대응. CSV 구분자와 달리 markdown
  // 파이프는 "빈 셀" 이라도 색 의미가 같아 묶어도 정보 손실이 없다.
  "|(\\|+)" +
  // 표식을 **시작할 수 없는** 문자들의 연속 — 산문 한 덩어리를 한 번에 삼킨다. CSV 의
  // `[^,"]+` 필드 대안과 같은 역할이고, 없으면 산문 1글자마다 정규식이 8개 대안을 헛돌아
  // 비용이 문자 수에 비례해 붙는다(실측: 이 대안 도입 전후 산문 줄 4~6배 차이).
  // 제외 문자 = `\`(이스케이프) `` ` ``(코드) `*`(강조) `~`(취소선) `[`(링크) `!`(이미지)
  // `<`(자동링크) `|`(표). `]`·`)` 는 어떤 표식도 **시작**하지 못하므로 포함해도 안전하다.
  "|(" + runClass + "+)" +
  "|([\\s\\S])";
// 링크 대안이 꺼진 변형에서는 `[`·`!` 도 아무 표식을 시작하지 못하므로 산문 런에 넣는다
// (`"[".repeat(4000)` 류가 1글자씩 catch-all 로 떨어지지 않게 — 0.76ms → 0.005ms).
const MD_INLINE_RE = new RegExp(_mdInlineSrc(_MD_LINK_ALT, "[^\\\\`*~\\[!<|\\n]"), "g");
const MD_INLINE_NOLINK_RE = new RegExp(_mdInlineSrc(_MD_NOLINK_ALT, "[^\\\\`*~<|\\n]"), "g");

function tokenizeMarkdown(text) {
  const e = _emitter();
  let rest = text;

  // ⓪ 인용 마커(`>`)를 먼저 벗긴다 — 인용 안의 제목·리스트·fence 도 같은 규칙으로 읽히게.
  const qm = MD_QUOTE_RE.exec(rest);
  if (qm) { e.plain(qm[1]); e.tok("code-tok-comment", qm[2]); rest = rest.slice(qm[0].length); }

  // ① fence 경계 — info string(```sql 의 `sql`)은 언어명이라 type 색. 이 줄은 여기서 끝.
  const fm = MD_FENCE_RE.exec(rest);
  if (fm) {
    e.plain(fm[1]);
    e.tok("code-tok-comment", fm[2]);
    e.tok("code-tok-type", fm[3]);
    return e.done();
  }
  // ② ATX 제목 — **줄 전체**를 제목색으로. 제목은 문서의 뼈대라 한 덩어리로 읽히는 편이 낫다
  //    (안쪽 인라인 표식까지 쪼개면 제목이 문장처럼 흩어져 위계가 깨진다).
  if (MD_ATX_RE.test(rest)) { e.tok("code-tok-keyword", rest); return e.done(); }
  // ③ setext H1 밑줄(`===`) — 제목과 같은 색으로 짝을 보인다.
  if (MD_SETEXT_H1_RE.test(rest)) { e.tok("code-tok-keyword", rest); return e.done(); }
  // ④ 구분선 / setext H2 밑줄 / front-matter 경계 — 구조 구두점.
  if (MD_RULE_RE.test(rest)) { e.tok("code-tok-punct", rest); return e.done(); }
  // ⑤ 표 정렬행 — 이 줄만 색이 다르면 "여기가 표 머리" 가 한눈에 잡힌다.
  if (_mdIsTableDelimRow(rest)) { e.tok("code-tok-punct", rest); return e.done(); }

  // ⑥ 리스트 마커(+ task 체크박스). 마커만 칠하고 항목 본문은 인라인 규칙으로 넘긴다.
  const lm = MD_LIST_RE.exec(rest);
  if (lm) {
    e.plain(lm[1]);
    e.tok("code-tok-punct", lm[2]);
    e.plain(lm[3]);
    rest = rest.slice(lm[0].length);
    const tm = MD_TASK_RE.exec(rest);
    if (tm) { e.tok("code-tok-bool", tm[1]); rest = rest.slice(tm[1].length); }
  } else {
    // ⑦ 참조 정의(`[ref]: https://…`) — 라벨은 이름표라 key 자리.
    const rm = MD_REFDEF_RE.exec(rest);
    if (rm) {
      e.tok("code-tok-punct", rm[1]);
      e.tok("code-tok-key", rm[2]);
      e.tok("code-tok-punct", rm[3]);
      rest = rest.slice(rm[0].length);
    }
  }

  // ⑧ 인라인 스캔. 완전한 인라인 링크가 성립할 수 없는 줄은 링크 대안을 끈 정규식으로
  //    (위 성능 주석 ①). 판정은 문자 포함 여부 2회 — 정규식 실패 경로보다 훨씬 싸다.
  const re = (rest.indexOf("](") !== -1 && rest.indexOf(")") !== -1)
    ? MD_INLINE_RE : MD_INLINE_NOLINK_RE;
  re.lastIndex = 0;
  let m;
  while ((m = re.exec(rest)) !== null) {
    if (m[1]) e.plain(m[1]);                          // `\*` 등 이스케이프 — 표식이 아니다
    else if (m[2]) e.tok("code-tok-string", m[2]);    // 인라인 코드 = 리터럴
    else if (m[3]) {                                  // [라벨](url) · ![대체텍스트](url)
      e.tok("code-tok-punct", m[3]);
      e.tok("code-tok-func", m[4]);
      e.tok("code-tok-punct", m[5]);
      e.tok("code-tok-string", m[6]);
      e.tok("code-tok-punct", m[7]);
    }
    else if (m[9]) e.tok("code-tok-string", m[9]);    // <https://…> 자동 링크
    else if (m[10]) { if (_mdEmphOk(m[10], 2)) e.tok("code-tok-type", m[10]); else e.plain(m[10]); }
    else if (m[11]) { if (_mdEmphOk(m[11], 1)) e.tok("code-tok-type", m[11]); else e.plain(m[11]); }
    else if (m[12]) e.tok("code-tok-delim", m[12]);   // 표 파이프 — CSV 구분자와 같은 자리
    else e.plain(m[0]);                               // 8 `[` 런 · 13 산문 런 · 14 catch-all
  }
  return e.done();
}

// ── 언어 레지스트리 ─────────────────────────────────────────────────────────
// 확장은 여기 한 항목. `exts` 는 소문자 확장자(점 없음), `label` 은 사용자 표기용.
//
// ⚠️ **도달성은 서버가 결정한다**: 첨부 diff 는 서버가 `Kind ∈ ("text","csv")`
// (`routers/_conv_store.py` `_VERSION_DIFF_TEXT_KINDS`) 인 첨부만 줄 비교하고, Kind 는
// `routers/conversations.py` 의 `_EXTENSION_KIND_MAP` + 브라우저 MIME 으로 정해진다. 그 지도에
// 없는 확장자(`ddl`·`psql`·`tsv`·`jsonl`·`json5`·`config`·`csproj`·`plist` 등)는 MIME 이
// `text/*` 로 오는 경우에만 `text` 가 되고, `svg` 는 항상 `image` 라 이 화면에 닿지 않는다
// (§18.8 security 지적). 여기 등록해 두는 것은 **무해하고 미래 대비**이지만, "등록했으니
// 칠해진다" 로 읽으면 안 된다 — 실제 색이 안 나오면 먼저 서버 Kind 를 보라.
// 사용자에게는 이 목록이 아니라 `syncHlToggle`(attach-diff.js)의 **렌더 결과 기반** 판정만
// 노출된다(칠할 본문이 없으면 토글도 없다).
export const LANGS = {
  sql:  { label: "SQL",  exts: ["sql", "ddl", "dml", "psql", "pgsql", "mysql", "tsql", "hql"], tokenize: tokenizeSql },
  json: { label: "JSON", exts: ["json", "jsonl", "ndjson", "json5", "geojson", "ipynb"], tokenize: tokenizeJson },
  yaml: { label: "YAML", exts: ["yaml", "yml"], tokenize: tokenizeYaml },
  xml:  { label: "XML",  exts: ["xml", "xsd", "xsl", "xslt", "html", "htm", "svg", "plist", "config", "csproj"], tokenize: tokenizeXml },
  csv:  { label: "CSV",  exts: ["csv"], tokenize: _makeCsvTokenizer(",") },
  tsv:  { label: "TSV",  exts: ["tsv", "tab"], tokenize: _makeCsvTokenizer("\t") },
  // `md`/`markdown` 은 서버 `_EXTENSION_KIND_MAP` 이 둘 다 `text` 로 매핑하므로 **실제로 이
  // 화면에 도달한다**(위 도달성 주의의 반례가 아니라 확인된 경우). `mdown`·`mkd` 류 별칭은
  // 서버 지도에 없어 등록하지 않는다 — 등록해도 칠해지지 않을 확장자를 늘리지 않는다.
  md:   { label: "Markdown", exts: ["md", "markdown"], tokenize: tokenizeMarkdown },
};

// 확장자 → 언어 key 역인덱스. 같은 확장자를 두 언어가 주장하면 **먼저 등록된 쪽**이 이긴다
// (등록 순서가 곧 우선순위 — 조용한 덮어쓰기를 만들지 않는다).
const EXT_INDEX = (() => {
  const idx = new Map();
  for (const [key, spec] of Object.entries(LANGS)) {
    for (const ext of spec.exts) if (!idx.has(ext)) idx.set(ext, key);
  }
  return idx;
})();

/**
 * 파일명에서 하이라이트 언어를 판정한다.
 * @param {string} filename 원본 파일명(경로 포함 가능)
 * @returns {string|null} `LANGS` 의 key, 또는 미지원이면 null
 */
export function detectCodeLanguage(filename) {
  const name = String(filename || "").trim();
  if (!name) return null;
  // 경로 구분자·쿼리 꼬리를 떼고 마지막 확장자만 본다. `dump.sql.gz` 는 gz(미지원) 로 판정되어
  // 무색이 된다 — 압축본을 SQL 로 칠하면 안 되므로 이것이 의도된 결과다.
  const base = name.split(/[\\/]/).pop().split("?")[0];
  const dot = base.lastIndexOf(".");
  if (dot <= 0 || dot === base.length - 1) return null;
  return EXT_INDEX.get(base.slice(dot + 1).toLowerCase()) || null;
}

/**
 * 언어 key 의 사용자 표기 라벨. 호출자가 `LANGS` 를 직접 뒤지지 않게 한다(레지스트리 형태가
 * 바뀌어도 표기 계약은 이 함수가 유지).
 * @returns {string} 라벨 (미지원 key 는 대문자화한 key 자체)
 */
export function codeLanguageLabel(lang) {
  const spec = LANGS[lang];
  return spec ? spec.label : String(lang || "").toUpperCase();
}

/**
 * 한 줄을 토큰 배열로 나눈다(테스트·재사용용 — 렌더는 `paintCodeInto` 를 쓴다).
 * @returns {Array<{cls: string|null, text: string}>|null} 미지원 언어면 null
 */
export function tokenizeCodeLine(text, lang) {
  const spec = LANGS[lang];
  const s = text == null ? "" : String(text);
  if (!spec || !s) return null;
  if (s.length > MAX_LINE_LEN) return null;   // 방어 — 위 MAX_LINE_LEN 주석 참조
  try {
    return spec.tokenize(s);
  } catch (e) {
    return null;   // 토크나이저 결함이 화면을 깨뜨리지 않게 — 최악이 '무색' 이어야 한다
  }
}

/**
 * 요소의 내용을 토큰 span 으로 재구성한다. 텍스트는 `textContent` 로만 넣는다(XSS 무첨가).
 *
 * @param {Element} el   대상 요소 (내용은 통째로 교체된다)
 * @param {string} text  원문 한 줄
 * @param {string|null} lang `detectCodeLanguage` 결과
 * @returns {boolean} 토큰화해 칠했으면 true, 평문으로 넣었으면 false
 */
export function paintCodeInto(el, text, lang) {
  if (!el) return false;
  const s = text == null ? "" : String(text);
  const toks = lang ? tokenizeCodeLine(s, lang) : null;
  if (!toks) { el.textContent = s; return false; }
  // 조각이 하나뿐이고 무색이면 span 없이 텍스트만 — 무의미한 노드를 만들지 않는다.
  if (toks.length === 1 && !toks[0].cls) { el.textContent = toks[0].text; return false; }
  el.textContent = "";
  const frag = el.ownerDocument.createDocumentFragment();
  for (const t of toks) {
    if (!t.cls) { frag.appendChild(el.ownerDocument.createTextNode(t.text)); continue; }
    const span = el.ownerDocument.createElement("span");
    span.className = t.cls;
    span.textContent = t.text;
    frag.appendChild(span);
  }
  el.appendChild(frag);
  return true;
}
