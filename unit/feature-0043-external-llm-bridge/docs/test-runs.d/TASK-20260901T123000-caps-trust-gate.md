---
run_at: 2026-09-01T12:40:00+09:00
session: ai/claude/feature-0043-caps-trust-gate
scope: 능력 신고 자격 게이트 — 자격 없는 러너의 모델 목록을 화면에 그리지 않는다 (4차 재발 봉인)
verdict: PASS
---

# Run — TASK-20260901T123000-caps-trust-gate

Environment: **CLI** (컨테이너 `make test` — pytest 전량 + ruff) · 라이브 MySQL 읽기 대조 ·
git 이력의 실제 결함 빌드 재현.

> UI 표면(`index.html`·`chat.css`·`composer.js`)이 바뀌었으므로 **PB-0008 Windows 브라우저
> 시각검증이 완료의 hard gate** 다 (§15.4.1 · `visual_verification_scope: always`).
> 아래 §4 는 배포 후 POST-DEPLOY 로 채운다.

## 1. 근본 원인 실측 (2026-09-01 11:2x, 라이브 3중 대조)

「이름·기억이 아니라 실 resolve」 (§16.7 G7-a) — 세 축을 각각 조회했다.

| 축 | 명령 | 결과 |
|---|---|---|
| 도는 러너 파일 | `sha256(~/.mysql-ai-bridge/bridge_agent.py)[:12]` | `af7c3fe19808` (08-31 16:55) |
| 배포 중 러너 | `sha256(static/agent/bridge_agent.py)[:12]` | `d28dd9c32330` — **다름** |
| 러너 로그 | `bridge.log` 2026-09-01 10:21:34 | `codex: 응답을 받지 못해 내장 기본값을 씁니다` → `Codex(2종, 추론 3단계)` |
| 서버 행 | `WebOAuthTokens.Id=83` (하트비트 진행 중) | `codex: ['gpt-5.1-codex','gpt-5.1-codex-mini']` |
| 구버전 경고 | 같은 행 `RunnerBuild` | **`''`(빈 값)** → `stale_build` 판정이 fail-open |

즉 **폴백 제거 이전 빌드**가 돌면서 내장 표를 신고했고, 그 사실을 알릴 축(지문)이 그 빌드에
없어 서버가 `runner_update.current=True` 를 돌려주고 있었다.

## 2. 자동 테스트 — 전량 green

```
$ COMPOSE_PROJECT_NAME=repo make test
=== pytest ===  ........ [100%]   (FAILED 0)
=== ruff ===    All checks passed!
exit 0
```

신규 12건 + 기존 갱신 4건. 갱신분은 전부 **앵커 변경**(`account_runner_capabilities` →
`account_runner_profile`, `AGENT_FEATURES` 리터럴 튜플 → 원소 단정)이며 계약을 약화하지 않는다.

## 3. §16.7 G11-b — 수정 전 코드에서 FAIL 함을 실증

### 3.1 소스만 `main` 으로 되돌린 상태 (테스트는 신규 유지)

```
$ git diff -- <src 10개> > fix-src.patch && git checkout -- <src 10개>
$ pytest unit/feature-0003-agent-web-ui/tests/test_model_catalog_bridge_mode.py \
         unit/feature-0043-external-llm-bridge/tests/{test_runtime_model_selector,test_console_job_delegation,test_ux_parity,test_bridge_request_pins}.py
```

**FAILED 16건** — 새 단언이 무엇도 검사하지 않는 단언이 아님이 확인된다:

| 테스트 | 잡는 결함 |
|---|---|
| `test_untrusted_runner_report_is_not_rendered` | 자격 없는 러너 목록이 화면에 나감 |
| `test_untrusted_runner_says_why_and_what_to_do` | 감추되 사유·다음 행동을 말하지 않음 |
| `test_no_runner_keeps_the_old_message_not_the_update_notice` | 「러너 없음」과 「러너 낡음」을 한 문구로 뭉갬 |
| `test_trusted_runner_is_unaffected` | 정상 사용자를 막음 (G9-c 정상 경로) |
| `test_gate_lives_in_the_store_so_every_consumer_inherits_it` | 관문이 소비처마다 흩어짐 (G8-a) |
| `test_missing_fingerprint_is_stale_not_current` | 지문 미신고를 「최신」으로 읽음 (fail-open) |
| `test_staleness_predicate_has_exactly_one_home` | 지문 판정이 2벌로 복제됨 |
| `test_deployed_fingerprint_unknown_is_not_a_false_alarm` | 기준을 모를 때 거짓 경고 |
| `test_frontend_actually_renders_the_hidden_reason` | 사유가 응답에만 있고 화면에 도달 안 함 |
| `test_runner_declares_the_caps_self_report_capability` 외 2 | 러너가 자격을 신고하지 않음 |
| 기존 갱신 4건 | 앵커 미갱신 |

복원 후 `git status` 확인 + 전량 재실행 green (§16.7 G11-b 의 워킹트리 되돌림 조건: 이 브랜치는
원격 push·CI 자동배포·동시 백그라운드 실행이 없는 상태에서 수행).

### 3.2 구조 단정을 **실제 결함 빌드**에 걸었다 (내가 만든 뮤턴트 아님)

`test_builtin_model_table_never_reaches_the_report` 는 `main` 에서는 통과한다(이미 폴백이
제거됐으므로). 그래서 git 이력의 **실제 결함 커밋**에 걸었다:

```
historical build (82f3a160^): 8766f0e6f32c
reported runtimes: ['claude', 'codex', 'gemini']
LEAKED builtin models -> ['gemini-2.5-flash','gemini-2.5-pro',
                          'gpt-5.1-codex','gpt-5.1-codex-mini','haiku','opus','sonnet']
assert not (reported & builtin)  => FAIL (결함 재현)
assert reported == []            => FAIL (결함 재현)
```

사용자가 본 그 문자열(`gpt-5.1-codex`)이 그대로 잡힌다.

## 4. PB-0008 실 Windows 브라우저 시각검증 (PRE-DEPLOY)

정본: `unit/feature-0003-agent-web-ui/docs/test-runs.d/TASK-20260901T123000-caps-trust-gate-ui.md`
— 격리 컨테이너(stamp `0df767209532`, `https://localhost:18096`)에서 **세 상태**를 실측했다.

| 상태 | 화면 | `gpt-5.1` |
|---|---|---|
| 러너 없음 | 숨김 + 종전 문구 | — |
| **구 러너**(자격 없음, `gpt-5.1-*` 신고) | 숨김 + 「…오래된 버전이라 … 다시 실행해 주세요」 | **응답·화면 모두 0건** |
| 자격 있는 러너 | 선택기 정상(모델 `Opus`) · 사유 지워짐 | — |

「구 러너」는 **실제 엔드포인트**(`/api/ai/connect/token` → `/api/ai/bridge_heartbeat`)에 구
러너와 동일한 본문을 보내 재현했고, 그 하트비트 응답이 `current:false · stale_build:true` 로
돌아온 것까지 확인했다(종전이면 `current:true`). 검증 토큰 2건은 `session-logout` 으로
revoke 완료.

## 5. 대조군 — 진단의 확인 (수정의 근거 아님)

12:13 에 라이브 러너가 재설치되어(빌드 `5aa59fe9904a`) 로그가
`codex: 답을 받지 못했습니다 — 이 런타임은 목록에 나오지 않습니다` 로 바뀌었고, `Id=83` 행의
`gpt-5.1` 이 **0건**이 됐다. 「낡은 빌드가 원인」이라는 진단이 대조로 확인된다.

⚠ 이 소멸은 **이번 수정의 결과가 아니다** — 사람이 러너를 다시 받았기 때문이다. 그 수동
재설치가 유일한 해소 경로였다는 것이 곧 이 cycle 이 닫는 구멍이다.
