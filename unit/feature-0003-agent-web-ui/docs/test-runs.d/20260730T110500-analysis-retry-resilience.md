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

---

## Run — POST-DEPLOY 라이브 (Environment: Windows-browser, PB-0008) — TARR.3 · 2026-07-30 12:0x KST

배포본: main `d435d3a0` (`make deploy-all` — web-a/web-b 롤링 + soak 통과 + insight/ask 워커
`mysql-ai-agent:d435d3a0` 롤아웃 + gateway 무드리프트). 실 Windows Chrome 150 (`bin/win-browser.py`
relay, `https://localhost/admin`, bootstrap_admin/admin 역할).

### 1. 서빙 자산 = 신 코드 (판정 선행)

배포본 HTML 의 asset stamp `3cb3a58b07bf` 로 `/static/graph/graph-ctxmenu.js` 를 받아 문자열 확인
(206,389 bytes): `_metaGraphRetryFailed` **있음** · `_META_POLL_MAX_MS` **있음** ·
`tries < 240` **없음**(회차 cap 제거 확증) · in-flight 가드 주석 **있음** · "재시도 대기" 문구 **있음**.
→ 이후 판정이 신 코드에 대한 것임을 먼저 고정.

### 2. 스키마 (alembic 0049)

`alembic_version = 0049_node_analysis_retry` · `node_analysis_jobs` 에 `attempts`/`next_attempt_at`/
`error_kind` 3컬럼 · 부분 인덱스 `ix_node_analysis_jobs_retry_due` 존재.

### 3. 라이브 API 계약 (인증 세션, 실 브라우저 fetch)

| 호출 | 결과 |
|---|---|
| `GET /api/admin/metadata/graph/analyze?run_id=…` | 200 · `retry_waiting`·`retryable_failed`·`next_attempt_at` **필드 노출**(0049 후 정상 산출) |
| `POST …/graph/analyze/retry` (`dry_run:true`) | 200 · `retried`/`eligible`/`capped` 분리 반환(codex P2-2 수정 확증) |
| `POST …/graph/analyze/retry` (대상 미지정) | **400** — 무제한 전역 회수 차단 가드 |

### 4. 굳은 실패 회수 + 자동 처리 (사용자 요청의 핵심)

- `scripts/node_analysis_retry_failed.py` dry-run: **130건 / run 9개**(라이브 진단과 정확히 일치).
  `verification-cleanup(취소)` 580건은 대상에서 제외 — **회수 판정식 라이브 실증**.
- `--execute`: **130건 회수 완료 / run 9개** → `failed` 710 → **580**(회수 대상 아닌 것만) ·
  `pending` 0 → **130** · `node_analysis_runs` **9개가 `running` 으로 복원**(종전엔 `done` 으로 마감돼
  다시 진행될 길이 없었다).
- 워커 1틱(`process_pending`) 실측: `claimed 5 · done 5 · failed 0 · retry_pending 0 · enqueued 16`
  → **회수분이 실제로 claim 되어 분석 완료**. jobs `done` 10,215 → **10,225**.
- 진행률 재상승 확인(run 단위): `mssql-06656002eda6` Schema run **576/645** ·
  `mysql-3d6eaf56ad40` **640/647** · `mysql-82941a26ab6c` **104/111** — 전부 `running`.

### 5. 그래프 뷰 육안

`데이터소스: mssql-qa-idc` 선택 → 제품 카테고리 밴드(출조낚시왕/콜오브카오스/DK온라인/스키드러쉬) +
스키마 카드 137개 정상 렌더, 일부 카드에 **분석됨 보라 테두리 마커**(cc_pyron·accountdb·
dk_data_release·dk_data_release_test) 라이브 반영. 상태줄·미니맵·범례 정상. 증적 2매:
`artifacts/feature-0016-metadata-graph/20260730-analysis-retry/{01-graph-tab,02-graph-loaded}.png`.

### 6. 미검증 (정직)

- **진행 패널의 "재시도 대기 N (hh:mm)" 표기와 `↻ 실패 N건 다시 분석` 버튼은 라이브에서 보지 못했다.**
  두 요소는 서버가 `retry_waiting > 0` / `retryable_failed > 0` 을 반환할 때만 렌더되는데, 회수를 막 끝낸
  직후라 라이브에 회수 대상 transient 실패가 **0** 이고 backoff 대기도 **0** 이다(= 조건 미충족).
  인위로 만들려면 라이브 잡 상태를 조작해야 해 하지 않았다. 이 축은 헤드리스 25건(마크업·버튼 바인딩·
  클릭 왕복·HH:MM 포맷)이 계약으로 고정한다.
- **진행 패널 자체의 라이브 표시**: 패널은 분석 트리거(또는 재사용 감지) 경로에서만 열린다. 새 run 을
  만들지 않기 위해 트리거하지 않았고, 대신 진행률은 API·DB 로 확인했다. 패널 열림 자체는 기존 기능이며
  이번 cycle 이 바꾼 부분이 아니다.
- **폴링 백오프 간격**: 육안으로 판별할 수 없는 시간 축이라 헤드리스(2.5→5→10→20→30s 상한·무포기·
  진전 시 복귀·6h 상한)로만 검증했다.
- **자동 재시도의 라이브 발현**: 라이브 네트워크를 인위로 끊지 않았다(운영 영향). 상태머신은 단위
  테스트로 고정했고, 앞으로의 발현은 insight cycle 로그의 `node_analysis_retry_pending` 카운터로 관측한다.
- **pageerror 계측**: 이번 Run 은 콘솔 오류 수집 훅을 걸지 않았다(그래프 로드·상태줄·마커 정상 동작으로
  치명 오류 부재만 간접 확인).
