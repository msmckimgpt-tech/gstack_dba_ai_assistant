---
run_at: 2026-07-30T14:50:00+09:00
session: ai/claude/feature-0025-worker-ds-budget
scope: admin.js — AI 운영 현황 pane '워커 공유 자원' 섹션 렌더 (T0b worker-ds-budget)
verdict: PASS
---

# Run 2026-07-30 — Environment: Windows-browser (PB-0008) — **PASS**

## 수행 결과 (2026-07-30 17:08 KST, 배포 SHA eee1f4fb)

feature-0032 검증과 같은 세션에서 함께 확인했다(같은 pane 하단에 렌더된다).

- ✅ **'워커 공유 자원' 섹션 노출**
- ✅ 워커 6개(`insight_worker` + hostname 기반 role 5개) × 자원 3종(`llm`/`ds`/`task`) 표기
- ✅ `최대 점유 / 상한` 형식 정상: `llm 0/16` · `ds 0/8` · `task 1~2/8`
- ✅ 거절 컬럼 전부 0 — 게이트 미발동(정상 운영, 상한이 현행 동시성보다 높음)
- ✅ 커넥션 누적 계측: `pg_conns=2,528 · pg_ro_conns=942 · ds_conns=75`
- ✅ stale 표식 동작: 한 워커에 `(스냅샷 2,181초 전 — 갱신 지연)` 주황 표기

증거: `evidence/20260730-llm-budget-pane.png` (같은 스크린샷 하단)

---

## (아래는 배포 전 작성된 미수행 사유 — 이력 보존)

## 미수행 사유

`admin.js` 의 AI 운영 현황 pane 에 '워커 공유 자원' 표 렌더를 추가했다. 이 섹션의 데이터 소스는
**워커 컨테이너가 공유 볼륨(`/shared/perf`)에 flush 한 스냅샷**을 web 이 읽어 응답에 실은 값이다.
따라서 라이브 렌더는 다음 두 조건이 동시에 성립해야 확인 가능하다:

1. 새 web 이미지가 배포되어 응답에 `worker_resources` 가 포함된다.
2. 새 insight-worker 이미지가 배포되어 스냅샷 파일을 flush 한다(`ds`/`task` 자원 포함).

즉 **배포 전에는 이 섹션이 원리적으로 렌더될 수 없다**(응답 필드 부재 → 안내 문구만). 관리 콘솔
렌더 검증을 배포 후로 미루는 것은 본 feature 의 기존 관례와 동일하다(feature-0025 T0 · perf 서브탭 선례).

## 배포 후 검증 항목 (PB-0008, `bin/win-browser.py`)

- 감사 > AI 운영 현황 진입 → **'워커 공유 자원' 섹션 노출**
- 워커 행(role = 컨테이너 hostname)과 자원 행(`llm` / `ds` / `task`)의 `최대 점유 / 상한` 표기
- 거절 0 일 때 회색 `0`, 하단 안내("거절 0 = 상한이 병목이 아님") 표시
- 커넥션 누적 표기(`pg_conns=…` · `ds_conns=…`) — 누적 생성 횟수이며 동시 점유가 아님을 문구로 구분
- 스냅샷 부재/조회 실패 시 예외 대신 안내 문구(degrade)
- (선택) 콘솔에서 `AGENT_WORKER_TASK_BUDGET` 을 1 로 낮춰 거절 유발 → 적색 거절 + 거절률 표시 +
  `attention` 병목 신호 부상. **운영 설정 변경이므로 사용자 승인 후 수행**한다.

## 근거

- 백엔드 응답 계약은 단위 테스트 12건으로 고정(`unit/feature-0003-agent-web-ui/tests/test_worker_resources_pane.py`)
  — 파일 부재·손상·거대·비-dict·stale·symlink·NaN/Infinity·bool 전부 degrade/제외 단정.
- 프론트는 그 응답을 읽어 표를 그리는 순수 렌더이며 신규 fetch·라우트·권한이 없다(기존 pane 의
  `data` 를 그대로 소비).
