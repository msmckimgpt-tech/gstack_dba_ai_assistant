---
run_at: 2026-08-14T09:10:00+09:00
session: ai/claude/feature-0003-usage-records-sort-page
scope: [usage-records-modal, showUsageConvModal, column-sort, pagination, nav-identity, search-audit-css]
verdict: PRE-COMMIT PASS (node 50 + pytest 8 + feature-0003 전체 스위트 회귀 0) · POST-DEPLOY PB-0008 라이브 실측 예정
---

### Run (2026-08-14) — usage-records-sort-page: '사용 기록' 표 열 정렬 + 페이지네이션 — **Environment: Windows-browser (PB-0008 배포 후 실측 예정 — 정렬 클릭·페이지 이동은 관리 콘솔 로그인 세션 + 라이브 집계 결과셋이 있어야 유의미하고, sticky 열 머리 안의 버튼 렌더·열 폭 안정성은 레이아웃 산물이라 jsdom 으로 정본 대체 불가; de-risk = 정본 모듈을 jsdom 에서 실행하는 동작 하네스 50 + 구조 가드 8 + feature-0003 전체 스위트 회귀 0, visual_verification_scope: always)**

- 대상 변경: `src/static/admin/usage.js`(`showUsageConvModal` — 열 정의 SSOT · `sortKeysOf` ·
  `sortRows` · `headHtml`/`rowHtml`/`pagerHtml`/`renderTable` · 상호작용 위임 · nav 불변 색인) ·
  `src/static/css/search-audit.css`(`.usage-rec-sort*`, `.usage-rec-pager*`).

- **PRE-COMMIT ① 동작 — `tests/verify_usage_records_sort_page.mjs` 50 PASS**
  (Node18 + jsdom@22.1.0, 정본 모듈을 그대로 실행 — 로직 재구현 0):
  - **A 기본 상태 무회귀(8)**: 모달 개시 · 첫 페이지 50행 · 토큰 내림차순 · 1행 = 전체 최대 토큰 ·
    페이저의 총건수/표시구간 · 열 머리 7개 전부 정렬 버튼 · 활성 열 `aria-sort=descending` ·
    비활성 열 `none`.
  - **B 정렬(7)**: 수치 열 첫 클릭 내림차순 · aria-sort 추종 · 재클릭 토글 · 오름차순 1행 =
    전체 최소 · 텍스트 열 첫 클릭 오름차순 · 일시 열 최신순 · 비용 열(`—` = 0 취급).
  - **C 표시-정렬 정합(4)**: 주체 열이 표시 라벨 기준으로 정렬 · raw sentinel 미노출 · 워커 라벨
    번역 · **라벨 정렬 결과가 sentinel 정렬과 반대 순서임을 단정**(검출력 있는 축).
  - **D 페이지네이션(15)**: 경계 버튼 비활성 · 1/3 표기 · 다음/마지막/이전 · 2페이지 50행 ·
    마지막 페이지 20행 · 구간 101–120 · 정렬 변경 시 1페이지 복귀 · 25행 적용(1/5) ·
    '전체' 는 120행 1/1 + 이동 비활성.
  - **E nav 정체성(5)**: 정렬·페이지 이동 뒤에도 같은 행 = 같은 nav 인덱스 · 실제 클릭이 그 행의
    화면으로 이동 · **그 행의 대상이 검색어로 주입** · 이동 성공 시 모달 닫힘.
  - **F 이스케이프(3)**: 주입 태그 미생성 · 원문 텍스트 노출 · 전역 미오염.
  - **G 키보드 연속 조작(4, 적대 리뷰 반영)**: 정렬 후 그 열 머리에 포커스 유지 · 이어 누르면
    방향 토글 · 페이지 이동 후 '다음' 유지 · 경계 비활성 시 페이저 활성 컨트롤로 대체 이동.
    **뮤턴트 검증** — `restoreFocus` 호출을 주석 처리하면 G1~G4 가 정확히 4건 FAIL.
  - **이 하네스가 구현 중 결함 1건을 실제로 적발**: E4 가 `table_59` 행을 눌렀는데 `table_0` 이
    주입됐다 — 정렬이 `merged` 순서를 바꾸는데 nav 를 그 배열 인덱스로 되짚고 있었다.
    불변 색인(`rowsByIdx`)으로 수정 후 PASS.
- **PRE-COMMIT ② 구조 가드 — `tests/test_usage_records_sort_page.py` 8 PASS** (CI pytest):
  L1 열 정의 7축 · L2 정렬 트리거 + aria-sort · L3 페이지 슬라이스 렌더 · **L4 nav 가 불변 색인을
  쓰고 `merged[Number(` · `navByIdx` 가 없다(적발한 결함의 직접 잠금)** · L5 기본 정렬 보존 ·
  L6 페이저 배선 · L7 CSS 규칙(방향 표식 `min-width` 포함) · L8 하네스 존재.
- **PRE-COMMIT ③ 회귀**: feature-0003 전체 pytest 스위트 실행 — 실패 0. `node --check` PASS.
  (agent 이미지 `mysql-ai-agent:6fbccbc7` 에 worktree 마운트 + 라이브 DB 차단 env.)

- **POST-DEPLOY PB-0008 라이브 계획(정본)**: 배포 후 실 Windows Chrome 로 —
  - AC-1/2: `관리 콘솔 > AI 운영 현황 > LLM 사용량` 에서 막대 클릭 → 사용 기록 모달 → 각 열 머리
    클릭으로 정렬 전환(방향 토글 포함), 정렬 중 **열 폭이 흔들리지 않는지** 확인.
  - AC-3: 페이지 이동(다음/마지막/처음) + 페이지당 행 수 25/전체 전환, 경계 버튼 비활성 확인.
  - AC-4: 모달을 처음 열었을 때 종전과 같은 첫 화면(토큰 내림차순).
  - AC-6: 정렬을 바꾼 뒤 시스템 행 클릭 → 그 행의 대상 화면으로 이동.
  - 키보드: Tab 으로 열 머리 이동 → Enter 로 정렬 토글 2회 연속, 페이지 '다음' Enter 연타.
  - 콘솔 에러 0 · 서빙 자산 curl 확증(`usage.js` 의 `data-usage-sort`/`rowsByIdx`, `/livez` git_commit).
