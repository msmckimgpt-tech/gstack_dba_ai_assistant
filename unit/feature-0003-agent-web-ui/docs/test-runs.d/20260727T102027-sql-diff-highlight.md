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

### POST-DEPLOY 결과 (2026-07-27, 배포 8d69490c, deploy-web-only) — **Environment: Windows-browser** — PASS
- 방법: PB-0008 — `bin/win-browser.py` relay 실 Windows Chrome/150(CDP), `https://localhost/` 작업 화면 로그인(bootstrap_admin, KR_LIVE). 배포=`make deploy-web-only`(web-a/web-b 8d69490c 롤링 재생성·healthy·RestartCount 0). 서빙 자산 curl 확증(app.js sqlTokenizeToFragment/looksLikeSql/diff-sql·share.js·styles.css diff-sql + /livez git_commit=8d69490c).
- 확인(배포본 markdownToHtml eval — SQL diff): `pre.diff-block.diff-sql` 부여·diff 내부 sql-tok 9개. getComputedStyle 실측: keyword `rgb(187,154,247)`(#bb9af7)·string `rgb(158,206,106)`(#9ece6a)·number `rgb(255,158,100)`(#ff9e64)·add 라인 평문색 `rgb(192,202,245)`(#c0caf5 기본)·add 배경 `rgba(158,206,106,.14)`·del 배경 `rgba(247,118,142,.14)`·**hunk 미토큰화(0)**·gutter(data-gutter) 보존·script 주입 0.
- 육안: 실 화면 캡처에서 hunk(@@) 파랑·comment 회청·keyword 보라·function 파랑·string 초록·number 주황 구분 + del(빨강 배경+`-`)/add(초록 배경+`+`) 구분 확인. 스크린샷: `docs/evidence/pb0008-sql-diff-live-20260727.png`.
- 결과: **PASS** — 콘솔 에러 0. 원 요청("diff 부분에서도 SQL 하이라이트") 라이브 해소 확인. 검증 후 probe DOM 정리(라이브 화면 오염 0).
