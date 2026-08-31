---
run_at: 2026-08-31T13:20:00+09:00
session: ai/claude/feature-0043-wsl-scheme-handler
scope: "connect-modal.js · search-audit.css — [내 AI 실행] 무동작 정직 강등"
verdict: PASS
---

# Run — TASK-20260831T124500-wsl-scheme-handler (feature-0003 소유 파일분)

- **Environment**: **Windows-browser** (PB-0008, 격리 인스턴스 `https://localhost:18099`, 라이브 무접촉)
- **대상 파일**: `static/app/connect-modal.js` · `static/css/search-audit.css`

`[내 AI 실행]` → 30초 감시 → 실패 강등(`data-kind=error`) → 1단계 명령 강조
(`outline-color: rgb(37, 99, 235)`) + 문구·명령 **동시 가시** 확인.

검증 중 `scrollIntoView` 기준 결함(상태 문구가 화면 밖으로 밀림, `statusTop 912 > 뷰포트 889`)을
포착·수정했다 — 자동 스위트가 통과한 상태에서 렌더된 그림으로만 드러난 결함(§16.7 G9-a).

전체 절차·수치·대조군은 정본 기록 참조:
`unit/feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260831T124500-wsl-scheme-handler.md`
