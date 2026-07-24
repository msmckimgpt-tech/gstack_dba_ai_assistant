---
run_at: 2026-07-24T11:50:00+09:00
session: ai/claude/feature-0007-sonnet5-upgrade
scope: [composer-model-label, model-selector, reasoning-effort]
verdict: PRE-COMMIT PASS (단위·JS 구문) · POST-DEPLOY PB-0008 배포 후 실측 예정
---

### Run (2026-07-24) — sonnet5-upgrade 프론트 라벨(app.js `_composerModelLabelFor`) — **Environment: Windows-browser (PB-0008 배포 후 실측 예정)**

cross-feature cycle feature-0007-sonnet5-upgrade 의 프론트 변경 부분(코드 거주 feature-0003).
정본 cycle 문서: `unit/feature-0007-bedrock-llm-provider/docs/{MODIFY,REVIEW,TEST}.md`
(CHG/REV-20260724T113513-sonnet5-upgrade).

- **변경(app.js)**: `_composerModelLabelFor(value)` 신설 — 컴포저 현재-모델 표시가 내부 value
  (claude-sonnet-4, 넘버링 포함) 대신 카탈로그 label(claude-sonnet)을 노출. 모델 선택기 목록은
  이미 `opt.label` 사용(무변경). value/전송/저장은 불변(무회귀). 카탈로그 미로드/미등록 value 는
  value fallback(안전).
- **PRE-COMMIT**: `node --check app.js` PASS(문법). feature-0002+0003 pytest PASS(rc=0) — 단, 이 프론트
  라벨 변경은 파이썬 단위로 커버되지 않는 렌더 surface.
- **Environment: Windows-browser (PB-0008) — 배포 후 실측 예정(미수행 사유)**: 본 라벨 변경은 라이브
  배포(web 재빌드 + `/api/api-vault/options` 가 갱신된 PUBLIC_API_MODEL_OPTIONS 서빙) 후에만 반영되므로
  미배포 코드에서는 실측 불가. 배포 후 검증 항목:
  1. 모델 선택기(컴포저 `+` → 모델 선택)에 `claude-sonnet` / `claude-haiku`(버전 넘버링 없음, group `Claude`) 표시.
  2. 컴포저 현재-모델 라벨(`composerActionsModelLabel`)이 raw value(claude-sonnet-4) 아닌 `claude-sonnet` 표시.
  3. 새 대화 sonnet 선택 → 정상 답변(429/400 아님) — Sonnet 5 adaptive 라우팅 end-to-end.
