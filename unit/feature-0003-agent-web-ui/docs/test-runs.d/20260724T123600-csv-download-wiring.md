### Run (2026-07-24) — csv-download-wiring: 인라인 ```csv``` 블록 다운로드 버튼 배선 — **Environment: Windows-browser**

- 대상 변경: `static/app.js`(`enhanceCsvBlockDownloads`+renderMessageContent 배선)·`static/share.js`(공유 뷰 미러)·`static/styles.css`(`.csv-download-btn`) + cross-cut feature-0002 `agent_core._collapse_large_csv_blocks`·`tools.py` 가이던스.
- PRE-COMMIT 검증(자동, 라이브 비의존):
  - 전체 pytest **2303 passed / 2 skipped**(신규 `test_collapse_csv_block_download.py` 6 + 기존 collapse 5 무회귀 + 가이던스 문구 정합 2건 갱신). agent 이미지 격리 컨테이너.
  - jsdom `verify_csv_block_download.mjs` **18 PASS** — sanitize 이후 라이브 DOM 에서 `pre>code.language-csv` 버튼 삽입·라벨·멱등·클릭 시 URL.createObjectURL 호출·`.csv` 파일명·`/api/file`-뒤따름 skip·빈블록/비-csv(language-sql) 무삽입.
  - `node --check` app.js·share.js PASS.
  - jsdom 한계: 실제 CSS 픽셀 렌더·실 브라우저 Blob 다운로드 저장·실 대화 스트림 위 시각 배치는 layout/download API 부재로 실측 불가 → 아래 POST-DEPLOY PB-0008 로 정본 확인(카고컬트 방지 — headless 로 통과 위장하지 않음).
- POST-DEPLOY PB-0008 라이브 계획(정본, Windows-browser): 배포(web+worker) 후 실 Windows Chrome(bin/win-browser.py CDP relay)로 https://localhost/admin 로그인 → 작업 화면 대화 `20260724022429-515c0fd9`('도전 던전 전투 로그…' = 차원별 집계, bootstrap_admin) 재로드 → 인라인 ```csv``` 블록(msg 1342 등)에 "📥 CSV 다운로드" 버튼 렌더·클릭 시 .csv 다운로드 확인 + 신규 대형 결과에서 백엔드 `/api/file` 링크 주입·절단-미리보기 skip 확인. pageerror 0. → 결과를 본 fragment 하단·REPORT/REVIEW 에 append.

### POST-DEPLOY 결과 (2026-07-24, 배포 dc316152) — **Environment: Windows-browser** — PASS
- 방법: PB-0008 — `bin/win-browser.py` relay 실 Windows Chrome 150 (CDP), https://localhost/ 로그인 세션 bootstrap_admin. 서빙 자산 curl 확증(app.js `enhanceCsvBlockDownloads` 2건·share.js skip 가드 6건·styles.css `.csv-download-btn` 2건·/livez git_commit=dc316152).
- 대상 대화: `20260724022429-515c0fd9` '도전 던전 전투 로그와 재화 획득 데이터 JOIN 조회'(메시지 16·소유자 bootstrap_admin) = 사용자 보고 '킹스레이드 배틀 로그 차원별 집계'.
- 확인: 인라인 ```csv``` 블록(배틀로그 차원별 집계 데이터 `2026-07-01,2,26,1,188,789195` 등 + "…(완전한 데이터 계속)") 바로 아래 **"📥 CSV 다운로드" 버튼 렌더**(csvDownloadBtnCount=1·visible width/height>0·csvDownloadReady=1·linkAfter=false → skip 미발동 정상). assistant 의 "전체 CSV 다운로드 가능(1,500+ 행)" 안내가 실제 작동 버튼으로 연결됨.
- 클릭 실행: 실 브라우저 클릭 시 `URL.createObjectURL` 호출(다운로드 트리거)·Blob `type=text/csv;charset=utf-8;`·`size=2603` — 화면 CSV 텍스트가 실 .csv 파일로 저장됨(BOM 포함).
- 결과: **PASS** — 콘솔 에러 0(window.__errs). 원 마찰("CSV 다운로드 가능 답변인데 실제 다운로드 수단 없음") 해소 확인.
- 스크린샷: scratchpad csv-download-live.png / csv-download-btn.png (세션 산출물).
