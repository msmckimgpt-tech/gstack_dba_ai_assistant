---
run_at: 2026-09-01T12:40:00+09:00
session: ai/claude/feature-0043-caps-trust-gate
scope: 능력 신고 자격 게이트 — 자격 없는 러너의 모델 목록을 화면에 그리지 않는다 (4차 재발 봉인)
verdict: PASS  # Run 1 은 적대 패널이 BLOCK — Run 2 가 조치 후 재실측
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

⚠ **ruff 는 이 저장소의 게이트가 아니다** (`Makefile:281` — `ruff check … || true`, 주석
「ruff(참고용, 비차단)」). 전파되는 종료코드는 pytest 것뿐이므로 「exit 0, ruff clean」은
게이트 **하나**가 통과한 것이다. 최초 기재는 둘로 읽히게 썼다(qa 적대리뷰).

⚠ **정정 (qa 적대리뷰, 2026-09-01)**: 최초 기재는 「신규 12건 + 갱신 4건, 갱신분은 전부
앵커 변경이며 계약을 약화하지 않는다」였다. **둘 다 틀렸다** —
`git diff --cached -U0 -- '*/tests/*' | grep -c '^+def test_'` 는 **13**이고, 수정된 기존
테스트는 **7건**(+ `_with_defaults` 헬퍼)이다. 그리고 그중 둘은 앵커 변경이 아니라 **계약
변경**이었다: `test_runner_declares_features_and_version` 은 리터럴 튜플 단정을 멤버십으로
**느슨하게** 했고(감사되지 않은 capability 가 기본 선언에 섞여도 통과 — 뮤턴트 M7 생존),
`test_server_compares_the_deployed_runner_fingerprint` 는 `none["stale_build"] is False` 를
**삭제·반전**했다(의도된 계약 역전이지 앵커 이동이 아니다). 두 건 모두 Run 2 에서 조치했다.

## 3. §16.7 G11-b — 수정 전 코드에서 FAIL 함을 실증

### 3.1 소스만 `main` 으로 되돌린 상태 (테스트는 신규 유지)

```
$ git diff -- <src 10개> > fix-src.patch && git checkout -- <src 10개>
#   ⚠ 이것은 **HEAD(=`eebbf803`) 로의 되돌림**이지 `main` 이 아니다 — `git checkout --` 은
#     인덱스를 복원한다. 당시 브랜치는 main 대비 39 behind 였고 main 은 같은 선언 줄을
#     이미 옮긴 상태였다(`AGENT_VERSION="2026.09.01"` · `AGENT_FEATURES=(…,"self_review")`).
#     최초 기재의 「main 으로 되돌린」은 부정확했다 (qa 적대리뷰). Run 2 는 main 머지 뒤 기준.
$ pytest unit/feature-0003-agent-web-ui/tests/test_model_catalog_bridge_mode.py \
         unit/feature-0043-external-llm-bridge/tests/{test_runtime_model_selector,test_console_job_delegation,test_ux_parity,test_bridge_request_pins}.py
```

**FAILED 16건.** ⚠ **그러나 이것은 단언별 실증이 아니다 (qa 적대리뷰 Critical, 정정)** —
각 소스검사 테스트는 *선행하는 비텍스트 단언*에서 먼저 죽어 새 텍스트 단언은 **실행조차
되지 않았다**(심볼 부재 `ImportError`, 옛 앵커 불일치, `callable(...)` 실패). 심볼이 없어
생긴 테스트 전체 FAIL 은 그 텍스트 단언이 판별한다는 증거가 아니며, 실제로 세 단언은
동작보존 뮤턴트에 **생존**했다. 단언별 실증은 아래 **Run 2 §3.3** 이 수행한다.

아래 표는 「이 테스트가 수정 전 코드에서 붉어진다」는 사실만 말한다:

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


---

# Run 2 — 적대 패널 3인(security CONCERN / backend BLOCK / qa BLOCK) 조치 후 재실측

- Date: 2026-09-01 · Environment: **CLI** (컨테이너 `make test`) + node jsdom 하네스
- Base: **`origin/main` 머지 후**(`9ad72849`, 39커밋 흡수). Run 1 의 두 검증 주장이 머지
  대상이 아닌 base 에서 측정됐다는 지적(qa)에 대한 조치다.
- Result: **PASS**

## 2.1 머지가 qa 지적을 실물로 확인했다

`main` 이 같은 날 `test_runner_declares_features_and_version` 을 `version_at_least` 형태로
재작성해 두었고(등호 단언은 「하한이 오르는 순간 아직 갱신하지 않은 전 사용자의 콘솔 작업이
끊긴다」), 내 브랜치는 등호 판본을 유지하고 있었다 — 머지에서 **정확히 그 함수가 충돌**했다.
main 판본을 채택하고 그 위에 **정확집합** 단정을 얹었다(아래 2.3 M7).

## 2.2 조치 요약 (P1 7건 · concern 8건)

| # | 지적 | 조치 |
|---|---|---|
| B1 | `COALESCE` 가 옛 목록을 남기고 새 features 로 인증 | 능력 미탑재 신고는 `"[]"` 로 **이전 능력 무효화**(쓰기 시점 원자화) |
| B2/S1 | 지문 「모름」과 「미신고」가 같은 `""` | `account_runner_build` **tri-state**(`None`=모름) + 판정이 그것을 받음 + 조회 실패 로그 |
| C1 | `token_runner_profile` 이 두 번째 미게이트 관문 | 같은 게이트 적용 + **AST 구조 테스트**로 「모든 capabilities 투영 함수가 게이트를 지난다」 잠금 |
| B4/S3 | 다중 러너 시 선택기 깜빡임 | **하나라도 미선언이면 감춘다**(fail-closed) + `mixed_runners` 로 「옛 것을 끄라」 안내 |
| S2 | `_caps_trusted` 삼킨 import, 무로그 | **모듈 레벨 import** 로 전환(미테스트 except 분기 소멸) |
| C2 | `runner_download_url` 소비처 0 | 안내 안 **링크로 배선** + 도달을 하네스가 단정 |
| S-ARIA | `role="note"` 가 `role="menu"` 에 무효 | `role="presentation"` + `aria-live="polite"` |
| S-wart | `console_llm_state` 의 `runner` dict 키 비대칭 | 성공/실패 분기가 같은 키 집합 |
| C3 | `detect_runtimes` docstring 이 없는 폴백을 서술 | 본문에 맞춰 재작성 + 계약 상호참조 (양 미러) |
| qa §3 | 자격 불리언은 「버전 검사가 capability 옷을 입은 것」 | **런타임별 provenance** 신설 — 러너가 `source` 를 싣고 서버가 allowlist(`probe`/`cache`/`ollama`)로 거른다. 캐시 경로도 재검사 |
| S §3 | `자격/trusted` 어휘가 인가 경계로 읽힘 | `declares_caps_contract` / `caps_contract_declared` 로 rename + 「인가 경계가 아니다」를 docstring 에 명시 |

## 2.3 뮤턴트 재대결 — **단언별** G11-b (qa Critical 조치)

Run 1 의 「16 FAILED」가 단언별 실증이 아니었다는 지적에 대해, qa 가 **생존시킨 뮤턴트를
그대로 다시 넣어** 조치 후 죽는지 확인했다. 각 뮤턴트는 동작보존이고 대상 토큰만 제거한다.

| 뮤턴트 | Run 1 | Run 2 |
|---|---|---|
| **M1b** `_n = "caps" "_self_report"` (게이트가 정본 상수 대신 리터럴 재구성, docstring 은 그대로) | 생존 | **FAILED** |
| **M2b** `_profile.get("caps" "_contract_declared")` (핸들러가 토큰을 코드에서 감춤) | 생존 | **FAILED** |
| **M4b** 판정을 부른 뒤 로컬 재파생으로 덮어씀 (두 판정이 갈린 상태) | 생존 | **FAILED** |
| **M3** 안내 삼항 극성 반전 (보일 때만 안내) | 생존 | **FAILED** (하네스 3/9→6 fail) |
| **M8** `toggle("hidden", false)` (빈 안내 행 잔존) | 생존 | **FAILED** (10→9 pass, 1 fail) |
| **M-C2** 링크 배선 제거 | (신규) | **FAILED** |
| **M7** 기본 선언에 `"admin_jobs"` 추가 (감사되지 않은 동의) | 생존 | **FAILED** (정확집합 단정) |
| **M9b** 빈 cached 항목을 `_RUNTIME_SPECS` 로 재충전 | 생존 | **FAILED** (cached·probe 두 분기 parametrize) |

**어떻게 죽게 만들었나** — 텍스트 grep 을 버리고 구조로 올렸다:
- `_func_source` 가 **docstring 줄만** 잘라낸다(자기 설명이 자기 단언을 통과시키던 구멍).
  ⚠ `ast.unparse` 재출력은 **채택하지 않았다** — 포맷 정규화로 무관한 단언 15건이 깨졌다(실측).
- 이름 정합은 **`ImportFrom` 노드 + 비교 피연산자**로 확인(리터럴 재구성이 통과 못 한다).
- 단일 판정은 **`connect_status` FunctionDef 안에서 `runner_stale` 대입이 정확히 1개이고
  그 값이 `runner_build_is_stale` 호출**임을 AST 로 단정(슬라이스 앵커가 무매치라 파일 하단
  687줄을 검사하던 종전 형태를 제거).
- 프런트는 **jsdom 동작 하네스**(`tests/verify_selector_note.mjs`, 10 케이스)로 올렸다.
  ⚠ 이 저장소 CI 는 **pytest 전용이라 이 하네스를 실행하지 않는다**(테스트 컨테이너에 node
  부재 — 실측). 그래서 CI 게이트는 극성을 보는 구조 단언이고, 하네스는 로컬·PB-0008 앞
  단계에서 돈다. 이 사실을 숨기지 않는다.

**하네스가 처음엔 M8 을 놓쳤다**(9/9 통과). 「숨김 + 사유가 빈 카탈로그」 경계를 건드리지
않았기 때문이다 — 뮤턴트가 살아남은 자리가 곧 빠진 케이스였고, 그 케이스를 추가해 10/10 이
됐다. 생존한 뮤턴트를 기록하지 않았다면 이 구멍은 남았다.

## 2.4 전량 재실행

```
$ COMPOSE_PROJECT_NAME=repo make test      →  exit 0, FAILED 0
$ node unit/feature-0003-agent-web-ui/tests/verify_selector_note.mjs  →  10 passed, 0 failed
```

기존 fixture 다수가 provenance 없이 신고하고 있어 함께 갱신했다(러너는 이제 항상 신고한다).
`_func_source` 의 docstring 제거로 드러난 기존 단언 15건은 **원문 형식 보존** 방식으로
되돌려 해소했다 — 계약을 낮춘 것이 아니라 헬퍼의 부작용을 없앤 것이다.

⚠ 전량 실행 중 `feature-0014::test_g3b_observed_isolation_that_never_clears_reports_failure`
가 1회 붉었다가 단독 3/3·전량 재실행에서 통과했다. 부하 하 타이밍 flake 로 판정하며
(이 저장소의 알려진 monotonic/uptime flake 계열) 본 변경과 접점이 없다 — 그러나 **관측 사실
자체는 남긴다**(조용한 skip 금지).

---

## 정정 (2026-09-02, §18.8 (b) 재설계 후)

**이 Run 이 검증한 설계의 절반은 철회됐다.** 위 §3.1 의 「되돌림 후 FAIL」 목록 중
`test_gate_lives_in_the_store_so_every_consumer_inherits_it` ·
`test_runner_declares_the_caps_self_report_capability` 외 2 는 **테스트 자체가 사라졌다** —
읽기 시점 전역 게이트와 `caps_self_report` 자격 축을 철회했기 때문이다.

승계된 것: 지문 tri-state · 단일 판정(`runner_build_is_stale`, 소비처 3개) · 사유의 화면 도달 ·
「내장 표가 신고에 닿지 않는다」. 여기에 **런타임별 provenance**(수신 시점 필터)가 대신 들어와
같은 재발 클래스를 닫는다.

§3.2 의 「실제 결함 빌드(`82f3a160^`)에 걸어 `gpt-5.1-codex` 누출 재현」은 **그대로 유효**하다 —
그 단정은 자격 축이 아니라 「내장 표가 신고에 닿는가」를 본다.

무엇을 왜 되돌렸는지는 `docs/MODIFY.md` 의
`CHG-20260901T190000-ai-claude-feature-0043-caps-trust-gate-r3` 「철회」 표가 정본이다.
