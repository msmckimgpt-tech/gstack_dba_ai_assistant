---
run_at: 2026-07-15T10:29:12+09:00
session: graph-help-text-responsive (ai/claude/feature-0003-graph-help-wordbreak)
scope: 그래프 뷰 도움말 팝업 — ① 설명 텍스트 어절-중간 줄바꿈(orphan 음절) 해소(word-break:keep-all) ② 카드 고정폭(460px) → 브라우저(캔버스) 크기 반응형(clamp) (feature-0003 web/UI 프론트, CSS 전용, 그래프 도메인 정본 feature-0016)
verdict: PASS (코드/정적 + 라이브 win-browser eval 다중 크기 실증)
---

### Run (2026-07-15) — 도움말 팝업 텍스트 줄바꿈 + 반응형 크기 — **Environment: Windows-browser (AI 직접 — 실 Windows Chrome via bin/win-browser.py relay @ 172.26.144.1:9223) + graph.css 정적 검증**

- **사용자 피드백 2건**(graph-entry-help 배포본 관찰): (1) "설명 텍스트 문단이 중간에 잘린 상태로 줄바꿈되는 디자인적 불편" (2) "팝업이 고정 크기가 아닌, 브라우저 자체 크기에 반응하여 변형되도록".
- **변경(1파일, CSS 전용)**: `graph/graph.css` `.amg-help-card` —
  - (텍스트) `word-break: keep-all; overflow-wrap: anywhere;` (word-break 상속 → 카드 내 모든 안내 텍스트). CJK 기본(word-break:normal)은 글자 사이 아무 데서나 끊겨 "…탐색하세"/"요.", "옮깁니"/"다." 처럼 음절이 다음 줄로 orphan. keep-all 로 어절(공백) 단위로만 끊고, overflow-wrap:anywhere 로 폭 초과 토큰(긴 URL 등 예외)만 강제 분할.
  - (반응형) `width: min(460px, 100%)` → `width: min(clamp(320px, 90%, 520px), 100%)`. 고정 상한 460px 제거 → 캔버스(=브라우저) 폭의 90% 를 320~520px 사이에서 따라가고, 좁은 화면에선 100% 로 컨테이너를 넘지 않음. 세로는 기존 max-height:100% + overflow-y:auto 유지(짧은 뷰포트 내부 스크롤).
- **문법/구조**: graph.css `/*`:`*/` **63:63 균형**(주석 hazard 없음, 20260714T184717-fix 정신 준수) · 중괄호 **215:215** · git diff +8/-1(선언 2 + 주석). CSS 선택자/미디어쿼리/다른 규칙 무변경.
- **라이브 검증(win-browser eval, https://localhost/admin 그래프 뷰 pane, 규칙 주입)**:
  - **줄바꿈**: keep-all 적용 후 설명이 어절 경계로만 줄바꿈 — "…아래 조작으로"/"탐색하세요.", "…자유 배치로 옮깁니다."(넓어진 카드에선 1줄), "…상호작용"/"메뉴를 엽니다." 등 orphan 음절 소거(스크린샷 육안).
  - **반응형(컨테이너 폭 시뮬레이션)**: canvas-wrap 폭 override 측정 — 300px→카드 268(100% 바운드, 오버플로 0) · 360→320 · 617(자연)→520 · 700→520 · 1100→520(가독 상한). 브라우저 크기에 따라 320~520px 유동, 어떤 폭에서도 컨테이너 미초과.
- **§18.8**: 프론트 1파일 CSS 텍스트-레이아웃 전용(word-break/width), 백엔드/RBAC/스키마/JS/HTML 0 → 패널 skip(REVIEW `[SKIPPED:...]`, 적대 자가검토 refute).
- 결과: **PASS** — 줄바꿈 자연화 + 반응형 크기 라이브 실증. POST-DEPLOY 재배포 자산 최종 확인=deploy-web 직후.
