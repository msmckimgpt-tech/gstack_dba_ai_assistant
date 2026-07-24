### Run (2026-07-24) — sonnet-reasoning-budget-guide: '모델별 추론 예산' adaptive guide-note — **Environment: Windows-browser**

- 대상: `관리 콘솔 > 시스템 > 설정 > 모델별 추론 예산` — adaptive(Sonnet 5) 카드가 ②③ budget 슬라이더 대신 guide-note 를, budget 계열(haiku) 카드는 ①②③ 슬라이더를 렌더하는지.
- 방법: PB-0008 — bin/win-browser.py(실 Windows Chrome, CDP relay) + https://localhost/admin (WEB_BOOTSTRAP_ADMIN). 변경이 **백엔드(runtime_settings serialize `adaptive_models`)+프론트(admin.js)** 양쪽이라 라이브 서빙 필요 → **POST-DEPLOY 실측**(자산 배포 후, deploy-web 로 web-a/b + 백엔드 재빌드된 상태에서 검증). 사전 게이트는 본 Run 라인으로 충족, 아래 결과는 배포 후 갱신.
- 확인 항목(POST-DEPLOY):
  - [ ] sonnet 카드: '라운드(단계)당 출력'(①) 슬라이더 **존재** + "추론 강도 (adaptive thinking)" guide-note 표시 + ②(추론 강도별 예산)·③(일반 기본 thinking budget) 슬라이더 **부재**.
  - [ ] haiku 카드: ①②③ 슬라이더 **모두 존재**(회귀 없음).
  - [ ] /api/admin/settings/runtime 응답에 `adaptive_models` 포함 + reasoning_budgets/model_thinking_budgets 에 sonnet 행 없음.
  - [ ] 콘솔 에러 0(window.__errs).
- 결과(POST-DEPLOY 실측, 2026-07-24, main 8f7b148f): **PASS** — 실 Windows Chrome + https://localhost/admin.
  - [x] sonnet 카드: ①'라운드당 출력' 슬라이더 존재 + "추론 강도 (adaptive thinking)" guide-note 표시("이 모델은 adaptive thinking 계열입니다 — 추론 강도는 관리자 예산(토큰)이 아니라 대화 화면의 '추론 강도' 선택이 effort 로 직접 제어…") + ②③ 슬라이더 **부재**(카드 입력 요소 1개).
  - [x] haiku 카드: ①②③ 슬라이더 모두 존재(입력 요소 8개, 회귀 없음).
  - [x] /api/admin/settings/runtime(라이브 서빙) 응답 `adaptive_models=["claude-sonnet-4"]` + reasoning_budgets/model_thinking_budgets 는 haiku 만.
  - [x] 콘솔 에러 0 (window.__errs).
