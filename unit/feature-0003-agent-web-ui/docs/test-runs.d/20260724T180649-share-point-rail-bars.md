---
run_at: 2026-07-24T18:06:49+0900
session: /_template:entry share-point-rail-bars
scope: unit/feature-0003-agent-web-ui/src/static/{share.js,share.css}
verdict: PRE PASS (node --check·이식) · POST-DEPLOY Windows-browser 예정
---

### Run (2026-07-24) — share-point-rail-bars: 공유링크 뷰 대화 뱃지 막대화 + 클릭 위치 비례 (Minor §12.3 — feature-0003 web/UI, 표시전용) — **Environment: Windows-browser**

- **사용자 요청**: 공유링크 내 화면의 대화 뱃지도 메인 뷰처럼 막대 형식으로(현재 단순 포인트).
- **변경**: share.js `layoutSharePointRail` 막대(top%+height%)·클릭 핸들러 비율→`scrollShareMessageToRatio`·share.css `.share-point-dot` 막대화. 메인 뷰 A+B 동형 이식(좌표계 window scroll).
- **PRE**: `node --check share.js` PASS · 점 스타일 제거(막대) · 메인 뷰 검증분 이식(원본 적대리뷰+라이브 PASS).
- **Environment: Windows-browser — PRE-COMMIT 라이브 미수행 사유**: static baked → merge+deploy 후 서빙. 공유링크는 실 공유 URL(토큰) 필요 → **POST-DEPLOY PB-0008 실측**.
- **POST-DEPLOY 검증 항목(예정)**: ① 공유링크 우측 rail 뱃지가 메시지 범위 비례 세로 막대로 렌더 ② 막대 상/하단 클릭 → 메시지 위/아래로 비례 이동 ③ pageerror 0.

- **[POST-DEPLOY 2026-07-24, 배포본 c1358190] Environment: Windows-browser (AI 직접 — win-browser host-resolver relay, Chrome 150)**: `deploy-web` → healthz git_commit=c1358190·서빙 share.js `scrollShareMessageToRatio`·share.css 막대 CSS 반영. bootstrap_admin 로그인 → conv[2](14개) 공유 링크 생성(`/share/…`) → 익명 공유 뷰(title "공유된 대화") 접속.
  - **A(막대 범위화) PASS**: 공유 rail `#sharePointRail` 14개 뱃지 전부 `style.height` 지정(막대)·railHidden false — 짧은 user 질문 ~1%, 긴 assistant 답변 13.9% 높이(메시지 범위 비례). 스크린샷 육안 — 우측 rail 에 파란(user)/회색(assistant) 세로 막대(메인 뷰와 동일 형식). evidence/share-rail-bars-live.png.
  - **B(클릭 위치 비례) PASS**: 같은 큰 막대 상단 10% 클릭 → window.scrollY **62**, 하단 90% 클릭 → **1551**. 클릭 y 위치에 비례해 다른 위치로 이동(기존 "항상 중앙"이면 동일해야 함) — window.scrollTo 비례 스크롤 실증.
  - **Pass/Fail: A·B 공유링크 라이브 PASS** — 사용자 요구(공유링크 화면 대화 뱃지도 막대 형식) 실증 완료. pageerror 관측 안 됨.
