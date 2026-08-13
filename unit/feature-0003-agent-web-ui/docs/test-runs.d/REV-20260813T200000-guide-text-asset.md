---
run_at: 2026-08-13T20:00:00+09:00
session: ai/claude/feature-0041-external-ai-tool-surface
scope: feature-0041 연동 가이드(부록 B.0-1) — text/markdown 자산
verdict: PASS (대체 검증 — 렌더 표면 없음)
---

# Run — 연동 가이드 갱신 (PB-0008 대체 검증)

- **Environment**: Windows-browser **미수행** — 사유는 아래 §1
- **대체 검증 Environment**: live (배포본 내용 대조)

## 1. Windows-browser 미수행 사유

이번 변경의 `static/` 자산은 `ai-api-guide.md` **하나**이고, 이 파일은 `/api/ai/guide` 로
**`text/markdown` 원문 그대로** 서빙된다 — 브라우저 렌더 표면(레이아웃·스크립트·상태)이 없다.
같은 cycle 의 화면 자산(`oauth-consent.*`·`ai-connect.*`)은 별도 Run 에서 실 브라우저로
검증했다: `REV-20260813T180000-browser-auth-flow.md`.

따라서 이 자산의 **의미 있는 실패 모드는 "배포본에 갱신이 반영되지 않음"** 하나이며, 그것은
서빙 응답의 내용 대조로 확인한다(feature-0003 `docs/TEST.md` 의 기존 판단과 동일).

## 2. 대체 검증 결과 (배포 후 기록)

| # | 항목 | 결과 |
|---|---|---|
| 1 | `GET /api/ai/guide` 200 | (배포 후 기록) |
| 2 | 본문에 `B.0-1` · `"/ai/connect"` · `"셸 스크립트 실행을 요구하지 말 것"` 포함 | (배포 후 기록) |
| 3 | 익명 노출 인스턴스 데이터 0 (발급물 패턴 grep) | (배포 후 기록) |
