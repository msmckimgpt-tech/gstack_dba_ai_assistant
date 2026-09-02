---
run_at: 2026-09-02T14:55:00+09:00
session: ai/claude-corp/feature-0043-caps-live-sync
scope: caps-live-sync (능력 신고 라이브 도착 + 계정 원장)
verdict: PENDING-VISUAL
---

# TASK-20260902T140200 — 검증 기록

## 1. 단위 (Environment: CLI)

| 대상 | 결과 |
|---|---|
| 신규 `test_caps_live_sync.py` | **25건 PASS** (로컬 py3.12 · 컨테이너 py3.11 양쪽) |
| feature-0043 전체 (컨테이너 py3.11) | 신규 실패 **0** — 잔여 1건은 `main` 에서도 실패하는 order-dependent flake (`test_roster_never_calls_a_token_that_never_ran_a_runner_stale`) |
| `main` 기준선 대조 | 실패 집합 **동일** (귀책 판별: 그 flake 는 main 전체 스위트에서도 재현) |

## 2. 결손 주입 실증 (§16.7 G11-b)

새로 작성한 구조 단언이 **수정 전 코드에서 실제로 FAIL 하는지** 격리 사본
(`scratchpad/g11b`, 커밋 대상 아님)에서 8종 주입. 전건 FAIL 확인 후 사본 삭제.

| # | 주입한 결손 | FAIL 한 단정 |
|---|---|---|
| 1 | `app.js` 의 `onCapsChange(...)` 소비처 제거 | `test_frontend_consumes_the_revision_signal` |
| 2 | 하트비트 응답에서 `caps_baseline` 제거 | `test_heartbeat_response_carries_baseline` |
| 3 | 상태 응답에서 `caps_rev` 제거 | `test_status_response_carries_revision_and_pending` |
| 4 | 사유 문구를 구 버전(무조건 재실행 지시)으로 되돌림 | `test_catalog_reason_no_longer_asserts_staleness_without_evidence` |
| 5 | 폴링 조건에서 `_capsPollWanted()` 제거 | `test_caps_pending_extends_the_poll_window` |
| 6 | 서버 허용집합만 구 버전으로(한쪽만 넓힘) | provenance 동일성 + sanitizer 수용 **2건** |
| 7 | 러너의 verify 호출 블록 제거 | `test_verified_baseline_is_reported_with_verified_source` |
| 8 | 확인 없이 baseline 을 `verified` 로 신고 | `test_baseline_alone_is_not_reported` |

⚠ **#5 는 1차에 통과했다** — 단정이 `"_capsPollWanted()" in connect` 였고 **정의부**
(`function _capsPollWanted()`)가 그 문자열을 갖고 있어, 호출을 통째로 지웠는데 초록이었다.
「존재는 실행이 아니다」(§16.7 G14-e)가 검사 자체에 되돌아온 형태다. 호출 지점(`wantPoll`
할당 라인)을 보게 재작성한 뒤 재주입해 FAIL 확인.

## 3. throttle 실측 (자체 적발 결함)

`merge_baseline` 이 신고마다 `last_used_at` 을 새로 찍어 **내용이 같아도 직렬화 바이트가
달라지던** 결함. 저장 게이트의 「값이 그대로면 쓰지 않는다」가 항상 거짓이었고, 비용은
계정당 30초마다 `UPDATE WebAccounts` 다.

```
수정 전 동작(throttle=0):  30초 뒤 같은 신고 → 문서 동일? False
수정 후(throttle=3600):    30초 뒤 같은 신고 → 문서 동일? True
```

회귀 3건으로 잠금 — 반복 신고 무변경 · throttle 창 초과 시 재갱신 · 내용 변경은 즉시 반영.

## 4. Environment: Windows-browser (PB-0008)

<!-- 배포 후 실 브라우저 검증 기록. `visual_verification_scope: always` 이므로 웹 자산
     변경의 hard gate (verify-completion check #13). -->

- 상태: **미수행 — 배포 후 수행 예정**
- 검증 항목: ① 러너 기동 후 **새로고침 없이** 모델·추론등급 선택기 출현(AC-1)
  ② 확인 창의 문구가 「…확인하는 중입니다」(AC-2, 종전 「다시 실행해 보세요」 아님)
  ③ 정상 상태에서 `/api/ai/connect/status` 폴링 0(AC-3)
