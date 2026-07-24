---
run_at: 2026-07-24T18:13:00+09:00
session: ai/claude/feature-0003-sql-md-highlight
scope: [sql-syntax-highlight, markdown-render, enhanceSqlBlocks]
verdict: PRE-COMMIT PASS (headless chromium 실 vendor 파이프라인 23/23·JS 구문) · POST-DEPLOY PB-0008 배포 후 실측 예정
---

### Run (2026-07-24) — sql-md-highlight: assistant markdown 답변 ```sql``` 코드블록 구문 하이라이트 — **Environment: Windows-browser (PB-0008 배포 후 실측 예정 — 실 대화 스트림 위 배치·실 브라우저 폰트/색 렌더는 배포된 자산 + 로그인 게이트가 필요해 headless 로 정본 대체 불가; de-risk=headless chromium 실 vendor(marked+DOMPurify) 파이프라인 23/23 PASS + node --check PASS + getComputedStyle 실 styles.css 색 실측, visual_verification_scope: always)**

- 대상 변경: `static/app.js`(`enhanceSqlBlocks`/`highlightSqlInto`+`SQL_HL_*` 상수 + `markdownToHtml` 체인 1줄)·`static/share.js`(공유 뷰 로컬 미러 + `renderMarkdownContent` 체인 1줄)·`static/styles.css`(`.sql-block .sql-tok-*` 팔레트 + 사용자 말풍선 다크 배경 고정)·`static/share.css`(공유 뷰 동일 팔레트). vendor 무추가(외부 하이라이터 라이브러리 없음).
- PRE-COMMIT 검증(자동, 라이브 비의존, headless chromium chromium-1208 via playwright):
  - **headless chromium 실 파이프라인 23/23 PASS** — `scratchpad/sqlhl-verify.mjs`: 실 vendor `marked.umd.js`+`purify.min.js` 로드, app.js 에서 **추출한 실소스** `enhanceSqlBlocks` 로 `DOMPurify.sanitize(enhanceSqlBlocks(marked.parse(src)))` 실행.
    - 토큰화: keyword(SELECT/FROM/WHERE/JOIN/GROUP/ORDER)·function(COUNT/SUM `(`휴리스틱)·string(작은따옴표 리터럴)·number(1000.5/10)·comment(`--`) 색 구분 확인.
    - 텍스트 무손실: 토큰화 후 code 텍스트에 원문 SQL 보존(`SELECT u.id`…`LIMIT 10;`).
    - **DOMPurify 통과 후 `sql-tok` span+class 보존**(sanitize 가 떼지 않음).
    - **XSS 무력화**(문자열 리터럴 `'<img src=x onerror=alert(1)>'` 주입): 라이브 DOM `<script>` 0·`<img>` 0·`on*` 이벤트 핸들러 속성 0·alert 미발화 — 위험 리터럴은 이스케이프된 문자열 토큰 텍스트(`'&lt;img … onerror=alert(1)&gt;'`)로만 존재. (`textContent`-only span 조립 + DOMPurify 이중 방어.)
    - disjoint: `language-python`·`language-diff`(enhanceDiffBlocks 와 무충돌)·lang 없는 fenced·인라인 `code` 전부 무영향.
    - CSS 실측(`getComputedStyle`, 실 styles.css): keyword 색 `rgb(187,154,247)`(#bb9af7)·font-weight 600·`.sql-block pre` 배경 `rgb(26,27,38)`(#1a1b26 다크).
  - `node --check` app.js·share.js PASS.
  - headless 한계: 실 대화 스트림 위 시각 배치·실 Windows Chrome 폰트/서브픽셀 렌더·배포 자산 서빙은 headless 로 정본 확인 불가 → 아래 POST-DEPLOY PB-0008 로 정본 확인(카고컬트 방지 — headless 로 통과 위장하지 않음).
  - 시각 증거: `docs/evidence/sql-md-highlight-20260724.png`(렌더된 SQL 블록 캡처 — keyword/function/string/number/comment 색 구분 육안 확인).
- POST-DEPLOY PB-0008 라이브 계획(정본, Windows-browser): 배포(deploy-web) 후 실 Windows Chrome(`bin/win-browser.py` CDP relay)로 `https://localhost/admin` 로그인 → assistant 가 ```sql``` 쿼리를 답한 대화 재로드 → 코드블록이 색 구분(keyword 보라·string 초록·number 주황·comment 이탤릭)되어 렌더되는지 + 공유 뷰(`/share/{token}`)도 동일 확인 + pageerror 0. → 결과를 본 fragment 하단·REPORT/REVIEW 에 append.

### POST-DEPLOY 결과 (2026-07-24, 배포 0313b135, deploy-web-only) — **Environment: Windows-browser** — PASS
- 방법: PB-0008 — `bin/win-browser.py` relay 실 Windows Chrome/150(CDP, 172.26.144.1:9223), `https://localhost/` 작업 화면 로그인 세션(bootstrap_admin, KR_LIVE). 배포=`make deploy-web-only`(web-a/web-b 0313b135 one-at-a-time 롤링·90s soak 통과·caddy no-drift·asset stamp `?v=dev` 잔존 0·마이그레이션 없음). 서빙 자산 curl 확증(app.js `enhanceSqlBlocks`·share.js 체인·styles.css/share.css `.sql-tok-*` + `/livez` git_commit=0313b135).
- 확인(실 배포 `markdownToHtml` eval — 배포본 app.js): ```sql``` 샘플(월별 매출 집계) 렌더 → `pre.sql-block` 생성·토큰 26개. getComputedStyle 실측: keyword `rgb(187,154,247)`(#bb9af7)·weight 600 / func(COUNT) `rgb(122,162,247)`(#7aa2f7) / string `rgb(158,206,106)`(#9ece6a) / number `rgb(255,158,100)`(#ff9e64) / comment `rgb(115,122,162)`(#737aa2) / `pre` 배경 `rgb(26,27,38)`(#1a1b26). 텍스트 무손실(`SELECT u.id`…`LIMIT 10;` 보존)·주입 `<script>` 0.
- 육안: 실 화면 캡처에서 comment(회청 이탤릭)·keyword(보라 굵게)·function(파랑)·string(초록)·number(주황)이 다크 배경 위 명확히 구분됨. 스크린샷: `docs/evidence/pb0008-sql-highlight-live-20260724.png`.
- 결과: **PASS** — 콘솔 에러 0. 원 요청("SQL 하이라이트 적용된 상태로 전달") 라이브 해소 확인. 검증 후 probe DOM 정리(라이브 화면 오염 0).
