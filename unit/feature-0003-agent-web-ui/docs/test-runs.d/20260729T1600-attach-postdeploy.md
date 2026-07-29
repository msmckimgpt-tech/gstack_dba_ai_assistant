---
run_at: 2026-07-29T16:00:00+09:00
session: ai/claude/feature-0003-attach-postdeploy
scope: POST-DEPLOY 라이브 실증 — attach-full-scope(PR #1050) + attach-list-delete(PR #1051)
verdict: PASS
---

### Run (2026-07-29 16:00) — attach-full-scope / attach-list-delete POST-DEPLOY — **Environment: Windows-browser**

#### 1. 대상

두 cycle 이 배포본에서 실제로 동작하는지 사람 손을 빌리지 않고 직접 실증한다. 검증 명제는
코드가 아니라 **실행 결과**다 — "첨부가 걸린 대화를 이어서 요청할 때 assistant 가 그 첨부를
참조하는가", "인라인 밖 내용을 도구로 읽는가", "안내가 가리키는 삭제 컨트롤이 화면에 있고
실제로 지워지는가".

#### 2. Environment

- Bridge: `relay` @ `http://172.26.144.1:9223` (`doctor` → `ok: true`)
- Browser: Windows Chrome/150.0.7871.115 (실제 Windows 창 — WSL headless 아님)
- URL: `https://112.185.196.20/` (Windows hosts 에 `mysql-ai.company.local` 미등록)
- 계정: `WEB_BOOTSTRAP_ADMIN_USERNAME`(.env) — 검증 전용 세션
- 배포본: `/healthz` `git_commit=8867fd8f`(1차) → `38d1bcae`(2차) · 서빙 자산
  `app.js?v=11be3aaa9814`(1차 시점)에 `attachSidePanelNote` **baked**,
  `composerAttachmentsScopeAll` **0건**(제거 정합)
- 검증 대화: `20260729054631-58a4f17c` · 첨부 `attach-scope-probe.sql`(40줄, 각 줄에 고유 토큰
  `ZQX01`~`ZQX40`)

#### 3. 결과

| # | 명제 | 방법 | 결과 |
|---|---|---|---|
| 1 | 프론트가 첨부를 지정하지 않아도 대화의 첨부를 참조 | 브라우저 세션에서 `/api/ask` 에 **`attachment_ids: []`** 전송, "17번째 줄 probe token" 질의 | **PASS** — 답변 `ZQX17` (정확). 종전 구조라면 첨부 미주입으로 답할 수 없던 케이스 |
| 2 | 인라인 밖 내용을 도구로 자율 조회 | "read_attachment 로 33번째 줄부터 3줄" 질의 (역시 `attachment_ids: []`) | **PASS** — step 기록에 `tool: "read_attachment"`, `args: {filename, start_line: 33, max_lines: 3}` · 답변 `ZQX33`/`ZQX34`/`ZQX35` |
| 3 | "이 대화의 모든 첨부 사용" 체크박스 제거 | DOM 조회 | **PASS** — `#composerAttachmentsScopeAll`·`#attachScopeAllRow` 부재 |
| 4 | 참조 범위 안내 노출 | 첨부 패널 열기 | **PASS** — "AI 는 이 대화에 올린 파일 전체를 참고합니다. 필요 없는 파일은 × 로 삭제하세요." (11px, border-bottom 1px) |
| 5 | 안내가 가리키는 × 가 목록 뷰에 실재 | 목록 행 DOM | **PASS(2차 배포 후)** — `.attach-list-item-del` 1건. **1차 배포본에서는 0건이었고, 그 발견이 PR #1051 을 낳았다** |
| 6 | × → 실제 삭제 | confirm 자동승인 후 클릭 | **PASS** — 행 1→0, 서버 목록 0건, "첨부 파일이 없습니다." |
| 7 | 삭제 후 다른 파일 업로드 시 지운 파일 부활 없음 (ux BLOCK 회귀 가드) | 삭제 직후 `second-probe.sql` 업로드 → 렌더 이름 대조 | **PASS** — 렌더 `["second-probe.sql"]`, 삭제 파일 부활 `false`, 서버 목록도 동일 |
| 8 | 행 레이아웃 1줄 유지 (design CONCERN 회귀 가드) | computed style | **PASS** — 행 높이 49px 단일, `.attach-list-item-meta` `white-space: nowrap`, `.attach-list-item-name-text` 분리 렌더 |

#### 4. 미실증(정직 표기)

- **그룹 대화에서 목록 × 미노출**(`_canDeleteFromAttachList` 안전판): 코드 경로만 확인했고
  라이브 그룹 대화로는 실증하지 않았다. 판별 실패 시 미노출(fail-closed)이라 노출 방향의
  회귀 위험은 낮다.
- **그룹 첨부 삭제 권한 자체**(업로더가 아니라 "대화 소유자 또는 그룹 멤버")는 본 Run 의 대상이
  아니다 — 인가 정책 결정으로 사용자 판단에 이월(REV-20260729T152000-attach-list-delete).
