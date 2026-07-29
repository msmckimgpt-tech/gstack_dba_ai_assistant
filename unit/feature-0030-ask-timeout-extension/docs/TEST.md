---
doc_type: TEST
feature_id: feature-0030-ask-timeout-extension
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Cases

### 1.1 agent-core — `unit/feature-0002-agent-core/tests/test_timeout_extension.py` (신규 22)

- **KV 시그널**: prompted 가 run_id·deadline 기록 / grant 는 같은 run 에만 보이고 **다른 run 에는
  안 보임**(직전 요청 승인이 다음 요청을 무기한 연장시키지 않음) / 기본 미승인 / clear 는 같은 run
  신호만 지우고 다른 run 겨냥 신호는 보존 / KV 예외 시 fail-safe(연장 없음).
- **KV 경합 (codex P1-1·P1-2 회귀 방지)**: 빈 run_id 승인 거부 / prompt 대상과 다른 run 의 승인
  요청 거부 / **새 run 의 prompt 가 이전 run 의 승인을 상속하지 않음** / 저장된 run_id 가 비어도
  wildcard 로 읽히지 않음.
- **설정**: 기본값(사용=1 · 임계 80% · 상한 0=무제한) / 조회 실패 시 기능 OFF 로 흡수.
- **예산 게이트**: 미승인 초과 시 종료 / 무제한 승인 시 계속 / 상한 승인은 상한 소진 후 종료 /
  한도 이내 무영향 / 임계 계산.
- **탈출구 보존 (codex P1-3 회귀 방지)**: per-call 상한이 15분으로 유지돼 승인 중에도 '중단'·
  '즉시 답변'·lease fencing 이 응답한다 / 유예 창이 양수이고 짧다.
- **`_call_llm` timeout override**: override 우선순위 + 스펙 하한(5s) 보정 유지.

### 1.2 web — `unit/feature-0003-agent-web-ui/tests/test_timeout_extension_api.py` (신규 14)

- `POST /api/extend`: 익명 401 / 권한 없음 403(**승인 미기록**) / 권한 보유 시 승인 기록 /
  기능 OFF 409(**승인 미기록** — 다음 ON 전환 때 되살아나는 것 차단) / 빈 cid 400 / 잘못된 JSON 400.
- **run 대조 (codex P1-1 회귀 방지)**: stale client run_id 409(미기록) / 일치 시 승인 /
  진행 중 run 부재 시 409(빈 run_id 로 기록하면 wildcard) / memory 층 거절을 200 으로 위장 안 함.
- **fail-closed (codex P2-1 회귀 방지)**: 설정 조회 실패 시 503(미기록) — 워커와 대칭.
- 권한 카탈로그: `conversation.extend.{own,any}` 등록 / description ≤255·label ≤128
  (초과 시 시드 catchup 전체 abort — 과거 라이브 사고 재발 방지) / `finalize.own` 보유 시드 역할에
  동반 시드 / **`extend.any` 는 비-admin 역할에 자동 부여 안 됨**(codex P1-4).

### 1.3 회귀 안전망

- `test_route_parity_p5b.py` 골든 스냅샷 갱신: `/api/extend` **1개만** 추가(221→222), 그 외 경로·
  메서드·등록 순서 무변경(diff 로 확인).

## 2. How to Run

```bash
COMPOSE_PROJECT_NAME=repo make test
```

## 3. Test Runs

### 2026-07-29 — `make test` (worktree, `--no-deps`)

- 신규 36건 + route-parity 1건 = **37건 PASS** (codex 적대 리뷰 P1×4·P2×3 수정분 회귀
  테스트 11건 포함).
- **환경성 baseline 15건**(attachment 13 · runtime_settings 2)은 본 변경 전 `main` 에서 동일
  테스트를 대조 실행해 **같은 15건이 실패**함을 확인 — 회귀 아님(MinIO 미기동 · 배포 `.env` 의
  `AGENT_TIMEOUT_SEC` 가 스펙 default 와 다름).
- **본 변경으로 인한 회귀 0건.**
- ruff: All checks passed.

### 2026-07-29 — 라이브 시각검증 (PB-0008)

- `visual_verification_scope: always` 대상(웹 UI 변경) — 아래 §4 시나리오. 결과는
  `docs/test-runs.d/` 에 `Environment: Windows-browser` 로 기록.

## 4. 라이브 검증 시나리오 (PB-0008)

1. 관리 콘솔 `시스템 > 설정 > 실행 타임아웃` 에서 `에이전트/쿼리 실행 타임아웃` 을 짧게(예 10초)
   설정 → run 예산 = 30초, 확인 시점 = 24초.
2. 작업 화면에서 다단계 추론이 필요한 질문 전송.
3. 약 24초 시점에 컴포저 위 **주황 배너**("응답 시간 한도까지 약 N초 남았습니다. 계속 추론할까요?")
   + [계속 추론] 버튼 노출 확인. 탭을 백그라운드로 두면 브라우저 알림 확인.
4. **미승인 경로**: 그대로 두면 30초 후 종전대로 타임아웃 종료.
5. **승인 경로**: [계속 추론] 클릭 → 배너가 회색 "시간 제한 없이 끝까지 추론하는 중"으로 전환 →
   30초를 넘겨도 추론이 계속되고 답변이 완주.
6. 다음 질문은 다시 기본 타임아웃으로 동작(승인 비전이).
