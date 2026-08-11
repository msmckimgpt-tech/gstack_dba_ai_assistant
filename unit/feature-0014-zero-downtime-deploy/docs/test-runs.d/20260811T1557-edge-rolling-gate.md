---
run_at: 2026-08-11T15:57:00+09:00
session: ai/claude/zd-edge-rolling-gate
scope: bin/deploy-web.sh 엣지 후보 복귀 게이트 · Caddyfile passive health 계약
verdict: PASS (라이브 실증은 POST-DEPLOY 이월)
---

# Run — 엣지 롤링 게이트 (CHG-20260811T155700-edge-rolling-gate)

## Environment
- `CLI` — pytest(호스트) + 목 docker 하네스 · `bash -n` · 라이브 Caddy admin API 실측(read-only)
- UI 표면 0 (배포 스크립트·엣지 설정 주석·테스트) → PB-0008 대상 아님

## 1. 근본 원인 실측 (수정 전 상태)
| 관측 | 값 |
|---|---|
| 엣지 `no upstreams available` (6h) | **71건** |
| 전면 503 창 | **6회** (11:31 / 11:41 / 12:11 / 12:16 / 12:34 / 12:40) |
| 창 길이 | 12~17초 (12:34 창은 41초) |
| 503 응답 duration | 전부 `5.01s` = `lb_try_duration` 소진 |
| 창 중 active health | 양 replica **`host is up`** (= passive 격리가 유일 원인) |
| 롤링 간격 (컨테이너 StartedAt) | **10초** (web-a 12:39:54 → web-b 12:40:04) |
| 503 종료 시각 | "먼저 내린 replica 첫 실패 + 30s" 와 매 창 일치 |

## 2. 신규 테스트 (39 PASS — 함수 32 + 파라미터 확장)
`unit/feature-0014-zero-downtime-deploy/tests/test_edge_rolling_gate.py`
- G1 배선 9건 — recreate 호출·순서·우회 recreate 0(함수 귀속 검사)·predrain fail-closed·호출부 `|| die`
  · **predrain 실행 검증 4건**(상대 부재/unready/엣지 미복귀에서 각각 중단, 3조건 성립 시 진행)
- G2 파싱 8건(파라미터) — 라이브 형식·상대 upstream 오독 방지·두 자리·공백 JSON·미검출/빈응답/키부재/필드순서역전
- G3 대기 2건 — fails=0 즉시 통과 · 관측된 격리 미해제 시 실패 반환
- G4 degrade 8건 — admin 불가 시 고정 대기 · fail_duration 파싱 · 보수 fallback 30 · **라이브 설정 우선**
  · **floor** · caddy 부재 skip · `ps` 실패/부재 구분 · **admin hang 60s 에도 상한 내 반환**
- G5 비차단 2건(구조 + **실행 검증** — 게이트가 실제로 호출되고 그 실패가 반환값으로 새지 않음)
- G6 예산 정합 2건 · G7 passive 존치 1건
- G8 **2축 판정** 2건 — `fails==0` 만으로 통과 금지(Caddy→replica 실도달 필수) / 두 축 성립 시 즉시 통과
- G9 4건(4R) — probe 가 Caddy transport 와 동일(https·Host, **http 폴백 없음**) · 모든 컨테이너 조회에
  `timeout -k`(TERM 무시 대비) · **degrade 후에도 실도달 확인** · 초기 dual-start 가 조회 실패를 부재로 오인 금지

## 3. 뮤테이션 역검증 (17종 전건 KILLED)
| 뮤테이션 | 잡은 테스트 |
|---|---|
| predrain 게이트 제거 | `test_g1c_predrain_is_the_fail_closed_gate` |
| predrain 호출부 `\|\| die` 제거 | `test_g1d_predrain_failure_aborts_the_rollout` |
| 관측-timeout 실패반환 → 성공반환 | `test_g3b_observed_isolation_that_never_clears_reports_failure` |
| 라이브 Caddy 설정 조회 제거 | `test_g4b3_live_caddy_config_wins_when_larger` |
| admin 조회 timeout 제거(hang) | `test_g4c2_hanging_admin_api_cannot_stall_the_deploy` |
| fallback 30 → 0 | `test_g4b2_fail_duration_falls_back_conservatively` |
| recreate 비차단 파기 | `test_g5_recreate_does_not_abort_on_gate_miss` |
| recreate 선제대기 호출 제거 | `test_g5b_recreate_actually_invokes_the_gate_and_stays_nonblocking` |
| predrain 상대-부재 중단 제거 | `test_g1e_predrain_refuses_when_peer_missing` |
| predrain 상대-unready 중단 제거 | `test_g1e2_predrain_refuses_when_peer_unready` |
| predrain 엣지-게이트 중단 제거 | `test_g1e3_predrain_refuses_when_peer_not_edge_available` |
| degrade floor 제거 | `test_g4d_degrade_wait_has_a_conservative_floor` |
| `ps` 실패/미기동 구분 제거 | `test_g4e_ps_failure_is_not_read_as_caddy_absent` |
| peer 실도달 확인 제거 | `test_g8_gate_requires_active_reachability_not_just_fails_zero` |
| peer probe URL 목록 비우기 | (동상 + `test_g8b_gate_passes_when_both_axes_hold`) |
| http 폴백 복원 | `test_g9_peer_probe_matches_caddy_transport_no_http_fallback` |
| `timeout` kill-after 제거 | `test_g9b_all_container_probes_have_kill_after` |
| degrade 후 실도달 확인 제거 | `test_g9c_degrade_path_still_checks_reachability` |
| dual-start 조회실패 가드 되돌림 | `test_g9d_initial_dual_start_guard_separates_query_failure` |

> 초기 3종(M8·M7)은 **텍스트 단정이라 KILL 되지 않았고**(`if false;`·`: ||` 무력화가 문자열을 남김)
> 그 사실을 근거로 해당 테스트를 **실행 검증으로 승격**한 뒤 다시 KILL 됨을 확인했다.

## 4. 전체 회귀
- `make test` (컨테이너) — 기존 실패 **1건**(`test_oauth_exhaustion_gate.py::test_write_failure_after_successful_post_cannot_kill_slot_selection`).
  **main 기준선에서도 동일 실패**를 별도 실행으로 확인 → 본 변경과 무관(OAuth 토큰 갱신 스크립트 영역).
- ruff: All checks passed.

## 5. 미수행 (POST-DEPLOY 이월)
- **라이브 실증**: 다음 배포 창에서 `docker compose logs caddy --since 10m | grep -c 'no upstreams available'` = **0** 확인.
  수정 전 기준선 = 배포 1회당 8~13건. 이 수치가 게이트 실효의 유일한 ground truth 다.
