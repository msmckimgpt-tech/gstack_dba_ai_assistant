---
run_at: 2026-08-27T16:05:00+09:00
session: ai/root/feature-0043-bridge-progress-scroll
scope: 브리지 답변 직후 스크롤 최하단 고착 — /api/progress steps-fallback 원장 제외 + 감지기 위임 수렴 (Minor §12.3)
verdict: 사전 PASS(코드/단위/라이브-데이터 범위) — PB-0008 Windows-browser 는 POST-DEPLOY
---

# Run — TASK-20260827T160500-bridge-progress-scroll

## 1. 단위 · 하네스 — PASS

**Environment: pytest (agent 이미지, `make test` 격리 compose 프로젝트 `repo-unittest`)**

- `make test` **exit 0** — `FAILED`/`ERROR` 0건, `ruff check` All checks passed.
- 신규 `tests/test_bridge_progress_fallback.py` **9건** — WHERE 절 부정 비교 · 원장 전용 대화 =
  run 없음 · 실 run 회귀(최근/노후/naive tz) · 비-PG skip · 생산자(ai_tools)와 표식 문자열 일치 ·
  빈 conversation_id fail-safe.

**Environment: node (ESM 격리 하네스)**

- `verify_run_detect_poll.mjs` — 38 → **57 passed / 0 failed** (S9~S15 신규).
- `verify_progress_poll_resilience.mjs` — **46 passed / 0 failed** (codex 4R 에서 발견된 helper
  미주입 파손 40/5 를 복구한 값).
- `unit/feature-0003-agent-web-ui/tests/verify_*.mjs` 전건을 main(baseline)과 exit-code 대조 →
  **완전 동일 = 신규 회귀 0**.

## 2. 뮤테이션 역검증 — 3종 전건 KILL

| 뮤턴트 | 결과 |
|---|---|
| `detectNewRun` 첫 분기의 `!_alreadyHandedOff` 제거 | S9(2) · S12(1) · S13(1) **FAIL** |
| `_detectHandoffSeenFor` 의 빈-run 가드 제거 | S15(2) **FAIL** |
| fallback SQL `<>` → `=` | `test_fallback_query_excludes_bridge_ledger` **FAIL** |

## 3. 라이브 데이터 대조 (배포 전, 읽기 전용)

증상이 실재함을 라이브에서 확인했다 — 재현을 위해 라이브 데이터를 만들거나 바꾸지 않았다.

- 대상 브리지 대화 `20260827061652-5ab532d1` 의 `agent_runtime.kv` 키 =
  `created_at` / `model:10` / `reasoning_level` / `topic` → **`last_status*` 부재**
  (그래서 `/api/progress` 가 steps fallback 을 탄다).
- `agent_runtime.steps` 에 `work_source='bridge-ledger'` **19행**,
  `run_id = t_LBtWKW0f1sBBfGK-` (= `WebAiTasks.TaskId`), `MAX(created_at) = 2026-08-27 15:30:03 KST`
  — 답변 전달 시각과 같다(원장은 전달 직후 기록되므로 그 순간 age ≈ 0 → `is_recent=True`).
- 배포본(web-a, `cwd=/app`, `PYTHONPATH=/app/web`) 직접 호출:
  ```
  app._load_latest_run_id_from_steps('20260827061652-5ab532d1')
  → ('t_LBtWKW0f1sBBfGK-', False)      # 끝난 브리지 답변이 "최신 run" 으로 읽힌다
  ```
  `False` 는 지금 원장이 3분을 넘겨 늙었기 때문이며, 답변 직후에는 `True`(=processing)였다.

> 합성 대화로 recency 축까지 재현하려 했으나 `agent_runtime.steps` 의
> `fk_steps_conv` 제약이 막았다(고아 행 0건 — 라이브 무오염 확인).

## 4. PB-0008 Windows-browser — POST-DEPLOY (사전 미수행 사유)

- **사유**: 이 결함은 *브리지 답변이 방금 도착한 대화*에서만, 그것도 원장이 3분 이내일 때만
  드러난다. 미머지 상태에서 그 조건을 만들려면 라이브 대화에 원장 행을 심어야 하는데, 그것은
  실사용자 대화의 진행 상태를 3분간 실제로 흔드는 행위다 — 검증을 위해 사용자 화면을 망가뜨리지
  않는다. `bin/win-browser.py doctor` 도 현재 `ok:false`(CDP 브리지 미기동).
- **POST-DEPLOY 계획**: 배포 후 ① 배포본에서 `_load_latest_run_id_from_steps(<브리지 대화>)` 가
  `('', False)` 인지 재확인 ② 실 Windows Chrome(`bin/win-browser.py` relay)으로 로그인 →
  브리지 대화 진입 → 15초 관찰 동안 `messageLog.scrollTop` 불변 + `/api/history` 반복 호출 0
  + 스크린샷. 결과를 본 fragment 에 append 한다.
