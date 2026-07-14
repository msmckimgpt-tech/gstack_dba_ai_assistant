---
run_at: 2026-07-14T10:54:32+09:00
session: ai/claude/feature-0003-step-scroll-preserve
scope: TASK-20260714T015432-step-scroll-preserve
verdict: PASS (code/unit de-risk) · PB-0008 live DEFERRED(post-deploy)
---

### Run (2026-07-14) — step-scroll-preserve: 실행 단계 폴링 갱신 시 펼친 "결과 보기" 스크롤 보존 — **Environment: Windows-browser**

- 대상: `static/app.js` — `buildStepDetailEl`(data-step-result-key) + `_snapshotStepResultScroll`/`_restoreStepResultScroll` + `_renderStepSidePanelBody`(사이드 패널)·`renderProgress`(인라인 progress 카드) 스크롤 스냅샷/복원.
- **코드/단위 de-risk (수행)**:
  - `node --check app.js` PASS.
  - jsdom 소스추출 격리 테스트 `tests/verify_step_result_scroll_preserve.mjs` **23/23 PASS**: (1) 정적 배선 — 두 재렌더 경로 모두 snapshot 이 `innerHTML=""` 앞·restore 가 뒤, `buildStepDetailEl` 이 `data-step-result-key=stepKey` 부여. (2) 기능 계약 — 펼쳐진 결과만 캡처(접힘 skip)·세로/가로 오프셋 캡처·재렌더 직후 0 초기화 확인·같은 stepKey 로 240/88 복원·새로 추가된 단계(D) 무영향. (3) 방어 — null 컨테이너/빈 맵 예외 없음.
- **PB-0008 Windows-browser 라이브 실측 — DEFERRED(배포 후)**: 본 검증은 실 Windows Chrome 에서 (a) 서비스 assistant 에 다단계 실행이 필요한 질의(예: 다수 행 결과 execute_sql 여러 단계)를 던져, (b) 진행 중 사이드 패널 또는 인라인 progress 카드에서 "결과 보기"를 펼쳐 표를 스크롤한 뒤, (c) 다음 단계가 폴링으로 도착하는 **비결정적 타이밍**에 스크롤이 유지되는지를 봐야 한다. 라이브 LLM 다단계 run + 폴링 창 포착이 on-demand 로 재현하기 어렵고, 정적 자산은 web 이미지에 baked 되어 서빙은 배포 후에만 반영된다. 따라서 코드/단위로 계약을 실증하고 라이브 시각검증은 배포 후 잔여로 둔다(visual_verification_scope: always). 배포 후 본 케이스에 Run 결과를 append 한다.
- 확인 절차(배포 후): 사이드 패널 — 여러 단계 execute_sql 결과 중 하나 펼쳐 표 중단까지 스크롤 → 새 단계 도착 시 그 표 스크롤·외부 목록 위치 유지. 인라인 progress 카드(`.progress-strip` 처리 중 자동 펼침) — 동일. 회귀 — 펼침/접기 토글, 하단 추종 자동스크롤 정상.
