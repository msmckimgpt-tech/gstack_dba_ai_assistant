---
run_at: 2026-07-24T11:24:46+09:00
session: ai/claude-corp/feature-0003-share-scroll-bottom
scope: [web-ui, frontend, share, scroll]
verdict: PASS (PRE-COMMIT; POST-DEPLOY 라이브 예정)
---

### Run (2026-07-24) — share-scroll-bottom: 공유 대화 링크 진입 시 문서 스크롤 맨 아래(최신 메시지) 고정 (Minor §12.3 — feature-0003 web/UI 프론트 `static/share.js` 단독, frontend-only) — **Environment: Windows-browser**

- **PRE-COMMIT 로컬 검증 (PASS)**: `node --check unit/feature-0003-agent-web-ui/src/static/share.js` PASS · §18.8 적대 프론트 리뷰(general-purpose subagent, REV-20260724T112446-share-scroll-bottom) verdict **SHIP-WITH-FIXES**(BLOCKING/MAJOR 0; MINOR 반영). 변경 범위: 진입 pin `engageInitialBottomPin`/`scrollShareToBottom`/`releaseShareBottomPin` 추가 + 초기 fetch→render 체인에서 1회 호출 + `pageBranchShare`·`scrollShareMessageIntoCenter` 에서 명시적 pin 해제. 백엔드/RBAC/스키마/엔드포인트 0.
- **Environment: Windows-browser — PRE-COMMIT 라이브 미수행 사유**: (1) 정적 자산(`share.js`)이 web 이미지에 baked → 서빙본 반영은 merge + `deploy-web` 재배포 선행(graph-node-reveal·floating-menu-close-fix 등 동일 패턴). (2) **문서 스크롤/`scrollHeight`/`innerHeight` 는 실제 레이아웃 의존** — headless(jsdom)는 layout 부재로 `scrollHeight=0`·`innerHeight=0` → `maxY=0` 이 되어 스크롤-투-바텀을 신뢰성 있게 실측 불가(프로젝트 학습 `frontend-scroll-restore-jsdom-gotcha`). 따라서 실 Windows Chrome(win-browser.py relay)로 POST-DEPLOY 실측한다. AC:
  - AC-1: 메시지 2개 이상 공유 링크 진입 시 문서 스크롤이 **맨 아래(마지막 메시지)** 로 위치.
  - AC-2: 늦게 렌더되는 표/mermaid/이미지로 문서 높이가 증가해도 (사용자 조작 전이면) 맨 아래 유지.
  - AC-3: 진입 후 사용자가 위로 스크롤(휠/터치) → 자동 재고정 즉시 중단(사용자 조작 우선).
  - AC-4: 버전 페이저(`< n/m >`, feature-0019) 사용 시 기존 스크롤 위치 보존 무회귀 — 진입 pin 이 방해하지 않음.
  - AC-5: 우측 미니맵(point rail) dot 점프 정상 — 진입 pin 이 방해하지 않음.
  - AC-6: 메시지 0개(빈 공유) 진입 시 스크롤 예외/점프 없음(maxY=0 no-op)·pageerror 0.
- **Pass/Fail: PRE-COMMIT 문법 + 적대 리뷰 PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run 존재 + POST-DEPLOY 계획 + headless 부적용 사유 기록 — 카고컬트 방지).

<!-- [POST-DEPLOY 갱신 placeholder] 배포(main 병합 + deploy-web) 후 실 Windows Chrome PB-0008 실측 결과(AC-1~6·스크린샷·pageerror)를 여기에 append. -->
