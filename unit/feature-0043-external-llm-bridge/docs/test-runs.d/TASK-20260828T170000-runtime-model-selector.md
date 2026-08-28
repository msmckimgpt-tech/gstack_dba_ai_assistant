# Run — TASK-20260828T170000-runtime-model-selector (P0-Z3)

- **일시**: 2026-08-28
- **Environment**: container (`make test`, 전용 compose 프로젝트) + host (러너 단위·CLI 실측)
- **대상**: 러너 신고 기반 모델·추론등급 선택기 (P0-T supersede)

## 결과

| 스위트 | 결과 |
|---|---|
| `make test` 전량 (feature-0002·0003·0014·0020·0023·0041·0043·0008) | **PASS** (exit 0, FAILED 0) |
| ruff (`unit/feature-0002/src`, `unit/feature-0003/src`) | All checks passed |
| 신규 `test_runtime_model_selector.py` | 39건 PASS |
| feature-0043 스위트 전체 | 520건 PASS |

## 라이브 실측 (호스트)

러너가 조립하는 **정확한 인자 순서**를 실제 CLI 로 확인했다. 여기서 틀리면 배포 후 모든
브리지 요청이 실패하는데, 단위 테스트는 리스트 모양만 보므로 그것을 잡지 못한다.

```
$ claude -p --model haiku --effort low "Reply with exactly: OK2"
OK2          (exit 0)
```

`build_cmd("claude", "Q", "sonnet", "low")` → `['claude','-p','--model','sonnet','--effort','low','Q']`
와 같은 형태다(플래그가 프롬프트 앞).

이 머신의 실제 신고도 확인했다 — claude(모델 3 · 등급 5) · codex(모델 2 · 등급 3).
gemini·ollama 는 미설치라 신고에서 빠진다(= 화면에 그 그룹이 없다).

## 주입 거부 실측

```
build_cmd('claude','Q','--dangerously-skip-permissions','$(rm -rf /)')
  → ['claude','-p','Q']          # 표 밖 값 2개 모두 폐기, 프롬프트만 남음
```

sanitizer 도 같은 방향으로 실행 확인:

| 입력 | 결과 |
|---|---|
| `runtime='claude; rm -rf /'` | 런타임 통째 폐기 → `[]` |
| `models=['--dangerously-skip-permissions','opus']` | 위장 항목만 폐기, `opus` 유지 |
| `label='A\nB'` | `'A B'` (한 줄 접기) |
| `None` / `[]` | `None`(미신고) / `[]`(빈신고) — **구분 유지** |

## 재작성한 기존 계약 테스트 5건

P0-T 를 잠그던 테스트가 새 계약에서 거짓이 된다. **삭제·skip 하지 않고 재작성**했다 — 지우면
그 자리의 방어가 영원히 검사되지 않는다(vacuous pass).

| 종전 | 재작성 |
|---|---|
| `..._does_not_persist_model_or_reasoning` | `..._persists_the_picked_runtime_model_and_level` (3컬럼 적재 + 호출부 전달) |
| `..._skips_server_model_gates_and_kv_writes` | 게이트 skip 은 유지 + KV 저장/복원 대조를 별 테스트로 분리 |
| `test_claim_does_not_deliver_stale_quality_request` | `test_claim_delivers_the_pick_from_request_time` (출처가 요청시점 각인인가) |
| `test_runner_does_not_pass_service_alias_as_cli_model` | `test_runner_only_accepts_models_it_itself_offered` + 동작 테스트 |
| `test_catalog_gates_selector_on_server_llm_state` | 세 갈래 배선 + 실패 시 추측 금지 |
| `test_a1d_bridge_mode_does_not_persist_model` | `test_a1d_bridge_mode_persists_the_pick` |

## 미수행 (정직 표기)

- **PB-0008 실 Windows 브라우저 시각검증** — `visual_verification_scope: always` 대상이다
  (`composer.js` · `system.py` 응답이 화면 조작면을 직접 바꾼다). 다만 **이 화면은 배포만으로는
  나타나지 않는다**: 선택기가 보이려면 사용자가 새 러너를 받아 재기동해 신고가 도착해야 하고,
  재기동에는 새 `mat_` 토큰(브라우저 로그인 → `/ai/connect`)이 필요하다. 배포 후 러너 재기동
  이전에 화면을 열면 **정상적으로 hidden** 이라, 그 시점의 화면 확인은 "숨김이 유지된다" 만
  검증한다(그것도 계약의 한쪽이므로 무가치하지는 않다).
  → 선택기 노출·플랫폼 그룹·등급 반영의 시각 확인은 **사용자 재기동 후**로 남긴다.
- **codex·gemini 풀네임 모델의 유효성** — alias(`opus`·`sonnet`·`haiku`)와 달리 풀네임은 CLI
  업데이트로 어긋날 수 있다. 어긋나면 그 항목을 고른 요청이 CLI 기본값으로 답한다(실패가 아니라
  무시). 실조회 경로가 있는 것은 ollama 뿐이다.
- **다중 러너 동시 연결** — 같은 계정으로 두 머신에서 띄웠을 때 "가장 최근 신고" 가 채택되는
  동작은 SQL(`ORDER BY LastHeartbeatAt DESC LIMIT 1`)로 단정했으나 라이브 관측은 안 했다.
