---
run_at: 2026-08-06T18:53:00+09:00
session: ai/claude/feature-0003-attach-diff-syntax
scope: 첨부 버전 diff 파일 유형별 구문 하이라이트 (frontend-only)
verdict: PARTIAL
---

# Run — attach-diff 구문 하이라이트

## Environment: node18 + jsdom@22 (headless)

- `tests/verify_attach_diff_syntax_highlight.mjs` — **77 PASS / 0 FAIL**
  - A 유형 판정 14 · B 언어별 토큰 28 · C 원문 무손실 2(표본 13 + fuzz 1,200) ·
    D XSS 7 · E 렌더 통합 19 · F CSS·정본 배선 7
- `tests/verify_attach_version_diff.mjs` — **85 PASS / 0 FAIL** (하이라이트 primitive 실물 주입 후)
- mjs 전수 — **46 suite / 0 failed**
- 뮤테이션 역검증 — **5/5 KILLED** (lang 무시 · JSON key 판정 제거 · CSV catch-all 제거 ·
  미지원도 토글 노출 · innerHTML 조립)

## 미수행 (정직 표기)

- `tests/headless/verify_attach_diff_geometry.py` — 이 환경에 playwright 브라우저 바이너리 부재로
  **미실행**. span 은 inline 이라 열 폭 기하에 영향이 없다는 것이 근거이나 측정하지 않았다.
- **Environment: Windows-browser (PB-0008)** — 색 대비·6,000행 체감은 실 브라우저가 정본.
  배포 후 POST-DEPLOY 로 수행 예정 → 그 시점에 본 fragment 를 `verdict: PASS` 로 갱신한다.
