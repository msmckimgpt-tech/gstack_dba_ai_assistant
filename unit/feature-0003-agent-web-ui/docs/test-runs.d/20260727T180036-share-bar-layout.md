---
run_at: 2026-07-27T18:00:36+09:00
session: ai/claude/feature-0003-share-bar-layout
scope: [share-view, footer-bar, actions, view-count, hover-expand]
verdict: PRE-COMMIT PASS (헤드리스 chromium 8/8 · 구조 회귀 5/5 · make test 회귀 0) · POST-DEPLOY PB-0008 대기
---

### Run (2026-07-27) — share-bar-layout (공유 대화 뷰 액션 하단 바 이동 · 조회수 상단 이동 · 바 hover 확장) — **Environment: chromium-headless(레이아웃 실측)**

cycle: `ai/claude/feature-0003-share-bar-layout` · 정본 = TASK-20260727T180036-share-bar-layout ·
REV-20260727T180036-share-bar-layout · CHG-20260727T180036-share-bar-layout.

- **변경**: `src/static/share.html`(액션 그룹 header→footer, `#shareViewCount` footer→헤더 meta) ·
  `src/static/share.css`(바 기본 높이 보존 규격 + hover/focus 확장 + transition + 터치/reduced-motion 분기).
  백엔드·RBAC·스키마·`share.js` 0.

- **PRE-COMMIT — `tests/headless/verify_share_bar_layout.py` 8/8 PASS** (chromium, 실 share.html + 실 share.css,
  변경 전 기준값은 `git show main:...` 원본을 같은 방식으로 렌더해 실측):
  1. `T1` 액션 그룹이 하단 바 안(헤더 아님)
  2. `T2` 하단 바 **우측** 정렬 — note.x=16 < actions.x=1085, 바 우측 여백 16.0px
  3. `T3` 조회수가 헤더 `.share-meta` 안 — viewCount.y=97 < footer.y=765
  4. `T4` **바 기본 높이 유지 — before(main) 35.0px → after 35.2px (Δ+0.2px, 허용 ±2px)**
  5. `T5` hover 확장 — 35.2px → 52.5px (+17.4px)
  6. `T6` transition 애니메이션 — `padding, background, box-shadow / 0.18s`
  7. `T8` hover 시 버튼 높이 31.5px (클릭 타겟 ≥24px)
  8. `T7` 본문 하단 여백 80px ≥ hover 확장 높이 52.5px (마지막 메시지 가림 없음)
  실행: `PLAYWRIGHT_BROWSERS_PATH=/home/claude-corp/.cache/ms-playwright python3 tests/headless/verify_share_bar_layout.py`
- **PRE-COMMIT — 구조 회귀 `tests/test_share_bar_layout.py` 5 PASS**(컨테이너 pytest): 액션 footer 소속 ·
  조회수 헤더 meta 소속 · 액션 4종 id 보존 + share.js 배선 · 바 정렬 규칙 · 기본 높이 유지 + hover/focus/transition/터치/reduced-motion.
- **PRE-COMMIT — `make test` 전체 회귀 0**: 실패 15건이 clean main(cdf4acf1) baseline 과 **완전 동일**(차집합 0 — attachment 계열 13 + runtime_settings 2, 전부 라이브 DB 상태 의존 선존 실패). ruff PASS.
  - 부기(worktree 함정): worktree 는 compose 프로젝트명이 디렉토리명으로 잡혀 라이브 스택 네트워크에 붙지 못한다 → `postgres-replica` DNS 실패로 무관한 테스트가 거짓 실패한다. `COMPOSE_PROJECT_NAME=repo make test` 로 main 과 동일 조건에서 비교해야 baseline 대조가 성립한다.
- **시각 증거(헤드리스, 실 CSS)**: `docs/evidence/share-bar-layout-before-20260727.png`(변경 전 — 액션이 헤더 우측, 조회수가 하단 바) ·
  `share-bar-layout-after-20260727.png`(변경 후 기본 — 상단 meta 에 `조회 6회`, 하단 바 우측에 `링크 복사`/`내 계정에서 fork`, 바 높이 기존과 동일) ·
  `share-bar-layout-hover-20260727.png`(hover — 바·버튼 확장 + 상단 그림자).

- **Environment: Windows-browser (PB-0008) — 미수행(배포 후 예정)**: 공유 뷰 정적 자산은 web 컨테이너 이미지에
  포함되므로 **배포 전에는 실 사용자 화면 실측이 불가**하다(§15.4.1 — 헤드리스는 실 CSS 기반이나 정본이 아니다).
  배포 후 검증 항목:
  1. 실제 공유 링크 진입 → 하단 바 우측에 `링크 복사`·(권한 시)`내 계정에서 fork` 표시, 헤더 meta 에 `조회 N회`(AC-SBL-1/2).
  2. 바에 마우스를 올리면 부드럽게(0.18s) 확장되고 벗어나면 되돌아옴 — 기본 상태 높이가 기존과 체감상 동일(AC-SBL-3/4).
  3. `링크 복사` 클릭 시 `복사됨 ✓` 토글, fork 동작 무회귀. 마지막 메시지가 바에 가리지 않음.
- **Notes**: §18.8 subagent 패널은 **본 세션의 사용자 환경 정책(Agent tool 미허용)으로 미수행** — REVIEW
  REV-20260727T180036-share-bar-layout 에 [SKIPPED:session-policy-no-subagent] 로 사유와 대체 검증
  (헤드리스 8 + 구조 5 + 자체 적대 검토 H1~H7) 을 명시했다.
