---
run_at: 2026-07-29T15:45:00+09:00
session: ai/claude/feature-0003-ratelimit-scope-paging
scope: rate-limit 버킷 스코프 격리 · 버전 페이징 전용 상한 · 429 Retry-After · 페이징 부하의 클라이언트 분산 · 재귀 CTE 인덱스 술어
verdict: PASS
---

### Run (2026-07-29) — 20260729T1520-ratelimit-scope-paging: 대화 페이징 429 블로킹 해소 + 부하 클라이언트 분산 (Major §12.3) — **Environment: Windows-browser**

- **방법**: PB-0008 — `bin/win-browser.py`(실 Windows Chrome 150, CDP relay `http://172.26.144.1:9223`).
  라이브 운영 replica 를 건드리지 않도록 **격리 검증 컨테이너**(`web-ratelimit-verify`, 운영과
  동일 이미지 + 본 worktree `src` 바인드마운트, `repo_dbnet`, host `:18093`)를 띄워 검증.
  시나리오: `unit/feature-0003-agent-web-ui/src/scenario.ratelimit-scope-paging.json`.
  대상 대화 = `20260713060414-12275bfa`(bootstrap_admin 소유 1:1, 버전 2개 `‹ 1/2 ›`),
  deep-link 진입(`/?conversation=…` — 인자 없는 새로고침은 직전 대화 자동선택 안 함).
  계측 = `window.fetch` 래핑 후 URL 별 호출 수 집계.

- **확인 (브라우저 실측)**:
  - 페이저 렌더 + 수정 JS 서빙: `pagerFound=true`, `label="1 / 2"`, `appJsHasCache=true`.
  - **캐시 미적중 클릭**(처음 보는 버전): `branch/switch` → `/api/history` 2건.
  - **캐시 적중 클릭**(재방문 버전): `branch/switch` 만 — **`/api/history` 0건**
    (click4 probe: `hist` 증가 없음).
  - `/api/session`: 전 구간 **0건** (페이징 경로에서 `refreshWorkspace` 제거).
  - **12연타 burst**(250ms 간격): `branch/switch` 12 · 페이징 기인 `/api/history` 0 ·
    `bodyHasRateLimitToast=false` → **429 미발생**. 개선 전 상한 5 에서는 6번째에서 차단.
  - 최종 라벨 `1 / 2` + `messagesRendered=6` — 12연타 후에도 버전 상태 정합(응답 뒤바뀜 없음).
  - burst 중 관측된 `/api/history` 1건 · `/api/conversations` 1건은 **클릭과 무관한 기존 주기
    폴러**(`_liveSyncTick` 5s / `_maybeSyncConversationListUnread` 7s) — 12클릭에 1건뿐인 점이
    시간 기반임을 뒷받침.
  - 스크린샷: `artifacts/win-browser-shots-ratelimit-scope/step_{01,06,10,13,18,20}_*.png`.

- **상한 직접 단언 (브라우저 in-page `fetch`, 실 세션 쿠키)**:
  - `POST branch/switch` **30회 연속 → 전부 200**(`byStatus={200:30}`, `first429At=-1`).
    개선 전 상한 5 에서는 6번째부터 429.
  - 같은 60s window 에서 이어서 **75회 추가 → 15×200 + 60×429**. 즉 보호는 그대로 살아 있고
    상한 60/min 에서 정확히 끊긴다(선행 probe 소비분과 합산해 60 도달 후 차단).
  - 첫 429 응답 실측: 헤더 `Retry-After: 3`, 본문
    `{"error":"버전 전환 요청이 너무 잦습니다. (약 3초 후 다시 시도할 수 있습니다.)","retry_after":3}`
    — AC-3 의 회복 어포던스 계약 충족.

- **보안 리뷰 후 재검증**: `/security-review` 채널에서 적발한 Finding A(로그아웃 시 대화 본문
  캐시 미소거)를 수정한 뒤 위 시나리오를 **전량 재실행**했고 결과가 동일했다(캐시 적중 클릭
  `/api/history` 0건 · 12연타 429 미발생 · 최종 라벨 `1 / 2` · `messagesRendered=6`).
  검증 산출물과 배포 산출물이 일치한다.

- **서버 비용 실측** (`repo-web-a-1` / `repo-postgres-1`, in-process):
  - `_branch_switch`: 개선 전 p50 8.0ms / p95 10.0ms → 개선 후 p50 7.7ms / p95 9.4ms (n=30).
  - 비교 기준선: LLM run `agent_runtime.llm_usage` 최근 7일 p50 **12,344ms** (n=6,975) —
    같은 5/min 버킷을 공유하던 이웃. `_get_history` p50 50.3ms (n=20) — 페이징이 유발하던
    무제한 endpoint. 히스토리 payload 83KB(대상 대화) / 168KB(최대 대화).
  - `_branch_leaf_of` 재귀 CTE (`EXPLAIN ANALYZE`, core_messages 5,491행):
    buffers 552 → **177**, 실행 1.171ms → **0.225ms**, SubPlan Aggregate cost 54.83 → 2.51.

- **정합성 전수 대조**: `_branch_leaf_of` 술어 추가 전/후 결과 비교 —
  `has_branches=true` 대화 12건 × (`messages`, `core_messages`) 전 메시지 = **442 조합,
  불일치 0**.

- **유닛 테스트**: `tests/test_ratelimit_scope.py` **17건 PASS**(신설). 직접 영향 3파일
  (`test_fix_with_ai` / `test_metadata_ai_autocomplete` / `test_message_editing_reanswer_model`)
  34건 PASS. 컨테이너 전체 스위트(`make test`, `COMPOSE_PROJECT_NAME=repo`) 실패 13건은
  **main 기준선과 동일**(같은 커맨드로 main 실행 시 동일 13건) — 신규 실패 0.
  해당 3파일을 격리 실행하면 main·worktree 양쪽 모두 15건 PASS(전체 스위트 순서 오염).

- **결과**: PASS — Windows-browser 게이트 충족.

- **부수 확인/정리**: 벤치마크·브라우저 검증이 라이브 대화의 `active_leaf` 를 바꾸므로 종료 후
  원값 복원을 확인했다(`20260727081131-1dc26d26` → 5667/1459, `20260713060414-12275bfa` →
  4529/1070, 둘 다 검증 전과 동일). 검증 컨테이너·브라우저 인스턴스는 `down`/`rm -f` 로 정리.

- **미검증 범위(정직 기록)**: 그룹/공유 대화의 읽기전용 페이징 경로는 코드 경로만 정합 확인
  했고 브라우저 실측은 1:1 대화로 수행했다(캐시·무효화 로직은 두 경로 공용, 그룹은 영속이
  없어 서버 요청이 1:1 보다 적다). 멀티워커 배포에서 상한이 워커당 적용되는 기존 한계
  (`_search_rate_limit_check` docstring)는 본 cycle 범위 밖 — 무변경.
