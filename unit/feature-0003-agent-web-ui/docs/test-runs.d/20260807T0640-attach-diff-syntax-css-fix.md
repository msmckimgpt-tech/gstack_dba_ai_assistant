---
run_at: 2026-08-07T06:40:00+09:00
session: ai/claude/feature-0003-attach-diff-syntax-css-fix
scope: 구문 하이라이트 keyword 규칙 미적용 hotfix
verdict: PARTIAL
---

# Run — attach-diff 구문 하이라이트 CSS hotfix

## Environment: Windows-browser (PB-0008) — 적발 Run (배포본 6cd4afd2)

- Bridge: relay @ http://172.26.144.1:9223 · Chrome/150.0.7871.128 · Runner: AI
- 대상: `https://localhost/?conversation=20260806100447-8db00b81` → 첨부 패널 → "버전 3개 ▾" →
  `⇄ 버전 비교` (`.sql` 3버전 체인)
- **PASS**: 모달 렌더 · 토글 노출 + 라벨 `SQL 구문 색` + checked · 토큰 span 12 · stats `+2 / -8`
- **FAIL(적발)**: `code-tok-keyword` computed `color: rgb(38,37,30)`(=`--text`) · `font-weight: 400`
  — 규칙 미적용. `code-tok-number` `rgb(15,118,110)` ✓ · `code-tok-comment` `rgb(90,88,82)` ✓
- Evidence: `/tmp/win-browser-shots/pb0008-attach-diff-syntax-01-split-on.png`

## Environment: node18 + jsdom@22 (headless) — 수정 검증

- `tests/verify_attach_diff_syntax_highlight.mjs` **113 PASS / 0 FAIL** (F2 섹션 5단언 신설)
- 뮤테이션: 라이브 결함 재주입 → **F8(line 2865)·F10 2중 red**

## 잔여

- 배포 후 PB-0008 재검증 — `code-tok-keyword` computed color `#7c3aed`(rgb(124,58,237)) · weight 600
  실측 시 본 fragment 를 `verdict: PASS` 로 갱신한다.
