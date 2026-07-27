---
run_at: 2026-07-27T10:35:00+09:00
session: ai/claude/feature-0003-sql-diff-highlight
scope: [sql-diff-highlight, enhanceDiffBlocks, sqlTokenizeToFragment, looksLikeSql]
verdict: PRE-COMMIT PASS (headless chromium 실 vendor 파이프라인 21/21·JS 구문) · POST-DEPLOY PB-0008 배포 후 실측 예정
---

### Run (2026-07-27) — sql-diff-highlight: ```diff``` 블록 내 SQL 구문 하이라이트 — **Environment: Windows-browser (PB-0008 배포 후 실측 예정 — 실 대화 diff 렌더/색은 배포 자산+로그인 게이트 필요, headless 로 정본 대체 불가; de-risk=headless chromium 실 vendor(marked+DOMPurify) 파이프라인 21/21 PASS + node --check + getComputedStyle 실 styles.css 색 실측, visual_verification_scope: always)**

- 대상 변경: `static/app.js`(`sqlTokenizeToFragment` 추출·`highlightSqlInto` wrapper화·`looksLikeSql` 신설·`enhanceDiffBlocks` SQL 라인 토큰화+`pre.diff-sql`)·`static/share.js`(동일)·`static/styles.css`(`.sql-tok-*` 셀렉터 일반화 + `.diff-block.diff-sql .diff-line` 기본색)·`static/share.css`(동일).
- PRE-COMMIT 검증(headless chromium chromium-1208, 실 vendor marked+DOMPurify, app.js에서 추출한 실소스 슬라이스 diffsql-helpers.js):
  - **21/21 PASS** — ① 회귀: ```sql 블록 하이라이트 유지(sql-tok·keyword #bb9af7). ② SQL diff → `pre.diff-sql` 부여·diff-line 내부 keyword/string/number 토큰·keyword 색 #bb9af7. ③ add/del 클래스 보존·gutter(data-gutter) 보존. ④ SQL diff 라인 평문색=기본 #c0caf5(토큰이 syntax색)·add 라인 배경 tint 유지(add/del 은 배경·border·gutter 로 구분). ⑤ 텍스트 무손실(코드 원문 보존). ⑥ 비-SQL diff(JS console.log) → `diff-sql` 미부여·sql-tok 0·기존 diff 렌더 유지. ⑦ looksLikeSql 게이트: JS `update()+function`·Python `from import` → false(오탐 억제), 실제 SELECT/INSERT/UPDATE → true. ⑧ XSS(diff 라인 `'<img onerror=alert(1)>'`): 라이브 DOM script 0·img 0·on* 0·alert 미발화·문자열은 inert 토큰 텍스트.
  - `node --check` app.js·share.js PASS.
  - 시각 증거: `docs/evidence/sql-diff-highlight-20260727.png`(SQL diff 렌더 — keyword 보라·string 초록·number 주황·comment 이탤릭 + del/add 빨강/초록 배경·border·gutter 육안 확인).
- POST-DEPLOY PB-0008 라이브 계획(정본): 배포 후 실 Windows Chrome 로 assistant 가 ```diff 로 SQL 변경을 답한 대화(또는 eval 로 배포본 markdownToHtml) 확인 — diff 라인 내부 SQL 색 구분 + add/del 구분 유지 + 공유 뷰 동일 + pageerror 0.
