---
run_at: 2026-07-29T16:50:00+09:00
session: ai/claude/feature-0003-attach-append-only
scope: 첨부 목록 append-only 전환 (삭제 UI 철회) — pre-commit
verdict: PASS (컨테이너 스위트 · 정적) / PB-0008 라이브 재검증은 배포 직후
---

### Run (2026-07-29 16:50) — attach-append-only pre-commit — **Environment: container(agent image) — Windows-browser 는 배포 직후 수행(§3)**

#### 1. 정적 검증

- `node --check app.js` PASS
- 잔재 0 확인: `_deleteConversationAttachment` · `_canDeleteFromAttachList` ·
  `.attach-list-item-del` · 프론트의 `DELETE /api/attachments` 호출 — **grep 0건**
- append-only 이중 게이트: 렌더 조건(`isDiscardable = status === "staged" || "failed"`)과
  함수 가드(`status !== "staged" && !== "failed"` → no-op)가 동일 판정 — `ready`(대화에 append 됨)와
  `uploading`(중단 수단 없음) 은 어느 경로로도 목록에서 빠지지 않는다

#### 2. 컨테이너 스위트

`COMPOSE_PROJECT_NAME=repo make test` → 실패 **13건**, main baseline(PG 환경성 attachment 13건)과
동일. 본 변경은 프론트 3파일이라 파이썬 테스트 영향 없음 — **신규 실패 0**.

#### 3. PB-0008 라이브 재검증 — 배포 직후 수행

1. 저장 완료 첨부 pill·목록 행에 ×가 **없음** (append-only)
2. 안내 문구가 "첨부는 대화에 계속 쌓입니다." 로 노출
3. 파일 업로드 후에도 목록에서 빠지지 않고 계속 남음 + assistant 가 계속 참조
4. `버전 N개 ▾` 토글이 잘리지 않고 클릭 가능(design CONCERN 회귀 가드)
