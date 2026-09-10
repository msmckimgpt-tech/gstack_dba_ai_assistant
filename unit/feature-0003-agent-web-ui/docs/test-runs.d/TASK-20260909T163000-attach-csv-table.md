---
run_at: 2026-09-09T17:20:00+09:00
session: claude:root:c8df7826-3990-458f-957c-6b38045298c8
scope: TASK-20260909T163000-attach-csv-table
verdict: PASS
---

# 첨부 CSV 표 렌더 검증

**현재 판정(2026-09-09 17:21 KST): 격리 DQA Shell(WebView2 Edg/152.0.0.0)에서 표 렌더 5축 PASS.**
아래 DQA-client Run 은 **fixture** 다 — 실제 계정의 첨부를 연 것이 아니다. 배포 후 실제 설치
앱에서 실제 첨부를 여는 확인은 미수행이며 그 사실을 마지막 블록에 `NOT-RUN` 으로 남긴다.

Environment: Node
Result: PASS
Scenario: 파서 계약(RFC 4180·절단본·BOM·CRLF·형식 이상 신고) · 토글 노출 판정 · 렌더 구조 ·
  XSS · 원문 복귀/영속 · 열·셀 상한 · 두 모달 배타 · 폴백 · CSS 규칙
Evidence: `tests/verify_attach_source_table.mjs` **88 PASS / 0 FAIL** (jsdom@22, Node18).
  뮤테이션 20종(1차 15 + P1 수정 후 5) **전건 KILL, 생존 0** — 정본에 실제 적용 후 diff 로
  적용 여부를 확인하고 실행했다. 표본은 내가 고른 것이라 사각지대 부재의 증거는 아니다
  (실제로 codex 가 낸 3건 중 2건은 이 집합이 가리키지 않던 축이었다).

Environment: CLI
Result: PASS
Scenario: 구조 가드 + 서버 도달성 + 음성 대조군
Evidence: `tests/test_attach_csv_table.py` 10 PASS. 첨부 관련 집중 회귀
  (`test_attach_csv_table` · `test_attachment_source_view` · `test_attachment_version_diff` ·
  `test_attach_manage` · `test_attach_lineage_ui` · `test_side_panel_exclusive`)
  **174 PASS / 0 FAIL** (컨테이너 `repo-unittest` 격리 프로젝트). 컨테이너 `make test` 전체
  회귀 exit 0. ruff `All checks passed`.
Boundary: 이 환경의 pytest `-q` 는 최종 집계 줄을 출력하지 않아 174 는 진행 표시 점 수로 센
  값이다. 전체 회귀는 **exit 0(전건 통과) 사실만** 확인했고 건수는 확보하지 못했다.

Environment: DQA-client
Result: PASS
Build: 격리 제품 Shell(`client/window.py`) / WebView2 `Edg/152.0.0.0` /
  제품 자산 지문 — `app/attach-diff.js` `5e87980c…`(리뷰 반영 전 지문, 최종본은 아래 재실행분),
  `code-highlight.js` `0ab46725deed718ce3b2861df3b5ff2e9d9451bf01aa9de804fec80f1c718374`
Scenario: `orders.csv`(45행 · 한글·수치·인용 필드 안 쉼표·빈 필드·40자 긴 값)를 첨부 원문
  모달로 열어 ① 격자 생성과 셀 분할 ② 열이 픽셀로 갈리는지 ③ 수치 열 우측 정렬 ④ 스크롤 후
  머리글 고정 ⑤ 토글을 끄면 종전 줄 표로 복귀
Evidence: `docs/test-runs.d/evidence/20260909-attach-csv-table/result.json` — **5/5 PASS**.
  같은 폴더 `table-modal.png`(격자) · `table-scrolled.png`(scrollTop 400 에서 머리글 유지) ·
  `source-view.png`(원문 복귀) · `table-top.png`. 실측값: 머리글 `# | 주문번호 | 고객명 |
  금액 | 비고`, `"김,철수"` 가 **한 셀**, 데이터 행 44, 수치 셀 88개, 열 x 좌표
  `34/66/177/274/360` 단조 증가·같은 열의 5개 셀 x 동일(177), 수치 셀 오른쪽 끝 4개 모두 350,
  머리글 top − 스크롤러 top = **1px**(sticky 실효), 복귀 시 첫 줄 `주문번호,고객명,금액,비고`
  byte 동일 + 구문 색 토글 재노출.
Boundary: **fixture 다.** `/static/app.js` 를 shim(=`attach-diff.js` 가 import 하는 8개 심볼)
  으로, `/api/attachments/1/source` 를 고정 응답으로 대체했다. 제품인 것은 `Shell`(WebView2)·
  `attach-diff.js`·`code-highlight.js`·`css/{base,chat}.css` 다. 로그인·AI 호출·서비스 데이터
  변경 0. 기존 사용자 앱은 건드리지 않았다(별도 프로필 `out/profile`).
  재현: `tests/pb0009_attach_csv_table.py` 의 모듈 docstring.

## 시각 캡처가 잡은 결함 2건 (jsdom·CLI 는 통과하고 있었다)

첫 캡처를 **눈으로 보고** 발견했다 — 그 전까지 하네스 73건과 구조 가드 10건은 전부 green 이었다.

1. **행 번호가 세로로 쪼개졌다** (10행부터 `1`/`0` 두 줄). `.attach-source-table-no` 에
   `white-space: nowrap` 을 선언했지만 `.attach-source-table th, .attach-source-table td` 의
   `pre-wrap` 이 특이성 (0,2,1) > (0,1,0) 으로 **이겼다**. 선언은 있고 효과는 없던 자리.
   행 높이가 배로 뛰어 표가 성기게 보였다.
2. **긴 셀의 `max-width: 420px` 이 무시됐다** — `table-layout: auto` 의 열 계산은 `td` 의
   상한을 폭의 정본으로 보지 않는다. 40자 값 하나가 열 폭 750px 을 만들었다.

해소: 값을 `.attach-source-table-cell` **block 래퍼**로 옮기고(상한·줄바꿈은 래퍼에), `td`
쪽 규칙을 지웠다. 재실행에서 행 번호 32px 한 줄 · 긴 값 두 줄 접힘 · 행 높이 균일을 확인했다.
회귀 방지: 하네스 I5b·I5c + 구조 가드 S6(«`td` 에 그 두 규칙이 있으면 FAIL» 음성 단언).

Environment: DQA-client
Result: NOT-RUN
Scenario: 실제 설치 DQA 앱에서 **실제 계정의 CSV 첨부**를 열어 표 확인
Reason: 위 Run 은 격리 Shell + fixture 응답이다. 배포는 끝났으나(아래 블록) 이 축은 **사용자
  소유의 실행 중인 앱을 조작해야** 성립한다 — §16.6 (a)(b) 가 「내가 열지 않은 표면은 건드리지
  않는다」를 요구하므로 수행하지 않는다. 실제 첨부를 새로 올리는 대안도 서비스 데이터를
  바꾸는데, 이 변경은 표시 계층이라 그 부수효과가 필요하지 않다. **fixture PASS 를 실제 앱
  PASS 로 확대하지 않는다.**
Next: 사용자가 앱에서 CSV 첨부를 열면 그 자리에서 확인된다 — 서버가 서빙하는 자산이 곧 앱
  화면이고, 아래 도달성 블록이 그 자산에 이 변경이 실려 있음을 확인했다.

Environment: DQA-client
Result: PASS
Build: **리뷰 반영 최종본** — `app/attach-diff.js` · `css/chat.css` 를 staging 에 재복사 후
  같은 스크립트 재실행 (WebView2 `Edg/152.0.0.0`)
Scenario: 위와 동일 5축 (레이아웃 수정 후 재측정)
Evidence: `evidence/20260909-attach-csv-table/result.json` **5/5 PASS**, 같은 폴더 캡처 4장이
  이 재실행분이다. 행 번호 열 32px(종전 25px, 두 자리 수용) · 긴 값 두 줄 접힘 · 행 높이 균일.


## 배포 — 라이브 도달성 확인 (2026-09-10)

Environment: Server
Result: PASS
Build: main `ebf5e365` (PR #1665 `7d78f426` 머지 이후 다른 세션 커밋이 더 쌓인 시점의 HEAD)
Scenario: `bin/deploy-web.sh --web-only` 실행 → 두 replica·엣지 경유 자산에 이 변경이 실렸는지 대조
Evidence:
- `bin/deploy-web.sh --web-only` **exit 0 · no-op(멱등)** — "이미 web `ebf5e365` 배포됨 + edge
  정상". 병행 세션이 내 머지 이후 HEAD 를 먼저 배포했고 그 안에 이 변경이 포함돼 있다.
  **내가 새로 롤아웃한 것이 아니다.**
- 두 replica(`repo-web-a-1`·`repo-web-b-1`) 컨테이너 안:
  `static/app/attach-diff.js` 의 `parseDelimitedText` **2건**, `static/css/chat.css` 의
  `attach-source-table` **11건**, `?v=a7922c7f93b1`(placeholder `?v=dev` 아님).
- **엣지(Caddy) 경유** — `Host: <WEB_PUBLIC_HOST>` 로 `https://127.0.0.1/static/app/attach-diff.js?v=…`
  에서 `parseDelimitedText` **2건**, `chat.css` 에서 `attach-source-table` **11건**.
  `/` 의 스탬프도 `app.js?v=a7922c7f93b1` 로 일치.
- `/livez` `{"status":"ok","git_commit":"ebf5e365",…}` · `/healthz`
  `{"status":"ok","git_commit":"ebf5e365","mysql_ok":true,"pg_ok":true}`.
- `/api/ui-release` `{"status":"complete","release":"ebf5e365","asset_stamp":"a7922c7f93b1"}` —
  열린 앱의 자동 반영(TASK-20260909T140000-deploy-refresh)이 감지하는 완료 신호가 게시된 상태.
Boundary: **「배포됐다」와 「사용자 화면에 보인다」를 구분한다.** 여기서 확인한 것은 *자산 도달성*
  (엣지가 새 파일을 서빙한다)이고, 특정 사용자의 열린 앱이 그 자산을 이미 로드했는지는 그 앱의
  로드 시점에 달렸다 — 이 세션은 사용자 앱을 조작하지 않았으므로 그것을 측정하지 않았다.
  WSL 에서 `WEB_PUBLIC_HOST` 가 DNS 로 해석되지 않아(`curl` exit 6) 엣지 확인은 Caddy 컨테이너
  안에서 `Host` 헤더를 실어 수행했다 — 사내 DNS 를 타는 실제 클라이언트 경로와 같지 않다.
