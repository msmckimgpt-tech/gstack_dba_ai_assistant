# Run — analysis-retry-resilience 시각검증 (Environment: Windows-browser, PB-0008)

- 정본 cycle: feature-0016-metadata-graph `## 20260730T1105-analysis-retry-resilience`
  (REVIEW `REV-20260730T110500-analysis-retry-resilience`). 코드 거주 파일 소유 = feature-0003
  (`src/routers/admin_metadata.py`, `src/static/graph/graph-ctxmenu.js`, `src/static/graph/graph.css`).
- 대상 변경(웹 자산): 진행 패널의 "재시도 대기 N (hh:mm)" 표기 · 회수 버튼(`↻ 실패 N건 다시 분석`) ·
  진행 폴링의 무포기 적응 백오프.

## 상태 — 커밋 시점 미수행 (사유 명시)

**미수행**: 이번 cycle 의 시각 대상(재시도 대기 표기·회수 버튼)은 **서버가 `retry_waiting` /
`retryable_failed` 를 실제로 반환할 때만 렌더**된다. 그 값은 alembic **0049**(`attempts` /
`next_attempt_at` / `error_kind`)가 적용된 뒤에야 산출되므로, **배포 전 라이브 화면에서는 두 요소가
구조적으로 나타날 수 없다**. 배포 전에 스크린샷을 찍어 "PASS" 로 기록하면 카고컬트가 된다.

대신 커밋 시점에는 다음으로 대체 검증했다.
- 헤드리스 격리검증 **25 PASS** (`tests/headless/test_graph_analysis_retry.js`) — 실 소스(`_metaGraphPollRun`
  /`_metaGraphRenderProgress`/`_metaGraphRetryFailed`)를 vm 에 태워 백오프 간격·무포기·패널 마크업·버튼
  바인딩·in-flight 응답 경쟁까지 계약으로 고정.
- 정적: `node --check`(ES module) PASS · 라우터 pytest 9 PASS.

## POST-DEPLOY 수행 계획 (TARR.3)

배포(`deploy_scope: included`) 직후 실 Windows Chrome(`bin/win-browser.py`)으로 수행하고 이 파일에
Run 결과·증적을 append 한다.
1. 관리 콘솔 > 지식베이스 > 그래프 뷰 진입 → 서빙 자산에 신 코드 포함 확인(`_metaGraphRetryFailed` 존재).
2. `scripts/node_analysis_retry_failed.py --scope <ds> --dry-run` 으로 라이브 잔여 대상 수 확인 →
   `--execute` 로 회수 → 진행 패널이 회수분 진행률을 다시 올리는지 육안.
3. 회수 버튼(`↻ 실패 N건 다시 분석`) 왕복 · "재시도 대기 N (hh:mm)" 표기(발생 시) · pageerror 0.
4. 자동 재시도 자체는 라이브 네트워크를 인위로 끊지 않고(운영 영향) insight 로그의
   `node_analysis_retry_pending` 카운터로 확인한다.
