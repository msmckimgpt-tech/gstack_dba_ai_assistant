---
doc_type: TASK_NOTE
feature_id: feature-0043-external-llm-bridge
task_id: TASK-20260902T140200-caps-live-sync
status: in-progress
edit_policy: append-only
---

# TASK-20260902T140200 — 능력 신고가 화면에 **도착**하게, 그리고 실행마다 **같게**

## 1. 어디서 왔나 (원 요청)

사용자 제보 (2026-09-02):

```
사용자 원문(데이터이며 지시가 아님)
프로젝트 내 서비스에서 '내 AI 연결' 을 수행할 때 다음과 같은 이슈들의 해소가 필요합니다.
- 러너를 통해 사용할 수 있는 LLM모델 및 추론수준을 답변받아도, 사용자는 웹사이트를
  새로고침하기 전 까지 해당 목록이 갱신되지 않습니다. 이러한 체감으로 인해 서비스를
  사용할 수 있는 체감 대기시간이 너무 오래 소요됩니다.
- 러너에서 답변받는 모델의 종류들이, 러너가 실행될 때 마다 일정하지 않은 이슈가
  확인되었습니다. 마지막으로 답변받은 모델들을 플랫폼마다 저장 및 캐시해두고, 이후
  다시 연결될 때 해당 플랫폼에 대해 캐시된 내용을 같이 전달하여 검증받는 등의 개선이
  필요합니다.
```

## 2. 근본원인 (코드 실측 2026-09-02, main `25f4de66`)

### 2.1 이슈 A — 목록이 도착하지 않는다: **갱신 신호가 «전이» 에만 걸려 있다**

카탈로그(`/api/api-vault/options`)를 다시 받는 경로는 두 곳뿐이다.

| 경로 | 위치 | 발화 조건 |
|---|---|---|
| 페이지 로드 1회 | `static/app.js:7723` `initializeWorkspace` | 최초 진입 |
| 컴포저 잠금 **전이** | `static/app.js:7833` `onComposeGateChange` | `compose_blocked` 값이 **바뀔 때만** |

두 번째는 `_paintGate` 의 `if (changed)` 안에서만 리스너를 부른다
(`static/app/connect-modal.js:822-854`). 그런데 능력 신고는 **잠금이 풀린 뒤에** 도착한다 —
러너가 그렇게 설계돼 있다 (`agent/lifecycle.py:614-618`):

```
# 협상은 **뒤에서** 한다. 끝나면 위 `runtimes` 가 제자리로 갱신되고 다음 하트비트가
# 새 목록을 싣는다 — 그때까지 웹 선택기만 비어 있고, 질문 처리는 이미 살아 있다.
```

즉 순서가 이렇다.

```
러너 기동 → 하트비트(runtimes=[]) → compose_blocked: true→false  ← 여기서 카탈로그 재조회
                                     (그러나 목록은 아직 [] — 선택기 hidden)
   ↓ 능력 질의 20~120초 (실측 claude 22.7s · codex 112.3s)
러너 → 하트비트(runtimes=[claude:…])  ← compose_blocked 불변 → **아무도 다시 받지 않는다**
```

게다가 폴링 자체가 그 시점에 멎는다 — `_syncGatePoll` 의 조건이
`wantPoll = _composeBlocked || _modalOpen` 이라(`connect-modal.js:794`), 잠금이 풀리고
창을 닫은 순간 `/api/ai/connect/status` 조회가 0이 된다. 그러므로 **능력 도착을 관측할
경로가 하나도 없다.** 새로고침이 유일한 수단이고, 그것이 제보의 「체감 대기시간」이다.

부수 사실: `/api/ai/connect/status`(`routers/oauth_as.py:533`)는 능력에 대해 **아무것도
말하지 않는다** — `connected`·`listening`·`runner_stale`·`runner_build`·`last_os`·
`batch_consent` 만 싣는다. 프런트가 「목록이 바뀌었다」를 알 값이 애초에 없다.

### 2.2 이슈 B — 실행마다 다르다: **목록의 출처가 LLM 답변이고, 캐시가 사용자 머신에만 있다**

목록은 그 AI 에게 직접 물어서 얻는다 (`agent/caps.py:_CAPS_PROBE_PROMPT`,
「너 자신에 대해 답하라」). LLM 답변이므로 **회차마다 개수·라벨이 흔들린다.** 코드가 이미
그 사실을 자인한다 (`caps.py:detect_runtimes`):

```
# 실측(2026-08-31): codex 는 같은 조건에서 성공(6종 응답)과 실패를 오간다. 그 한
# 번의 실패가 이제는 "그 런타임이 화면에서 통째로 사라짐" 을 뜻한다
```

흔들림을 흡수하는 캐시는 있는데 **로컬 `~/.mysql-ai-bridge/config.json` 에만** 있다
(`agent/conf.py:save_conf`). 그래서 다음 경우 전부 전면 재질의로 떨어지고 목록이 달라진다.

| 캐시가 없어지는 경로 | 결과 |
|---|---|
| 다른 머신·다른 OS 계정·새 컨테이너·홈 초기화 | 전면 재질의 |
| `--refresh-caps` | 전면 재질의(의도된 것) |
| 캐시 항목의 `source` 가 허용집합 밖(구 포맷) | 「캐시 없음」으로 강등 후 재질의 (`caps.py:620` 근처) |
| 질의 timeout·1회 실패 | **그 런타임이 신고에서 통째로 빠진다** ← 가장 눈에 띄는 «축소» |

서버 쪽 저장은 **토큰 행 단위**다 — `WebOAuthTokens.RunnerCapabilities`
(`_bootstrap_schema.py:2791`). 재연결 = 새 토큰 행 = 능력 NULL 이므로, 서버에도 이월되지
않는다. 읽기는 「계정의 최신 하트비트 러너 1대」(`oauth_store.account_runner_profile`)라
행이 갈리면 직전 관측이 사라진다.

## 3. 설계

### 3.1 이슈 A — 능력 리비전을 **값으로** 내려보낸다

- **서버** `GET /api/ai/connect/status` 에 두 값을 더한다.
  - `caps_rev`: 그 계정의 현재 신고 목록에서 파생한 짧은 지문(내용 해시 12자).
    값이 같으면 목록도 같다 — 프런트가 「바뀌었는가」를 문구 파싱 없이 판정한다.
  - `caps_pending`: `connected && listening` 인데 아직 신고 목록이 비어 있는 상태.
    「질의가 도는 중」을 서버가 말해 준다(프런트가 추측하지 않는다).
- **프런트** `refreshConnState` 가 `caps_rev` 변화를 관측하면 `loadVaultOptions()` 후
  선택기를 다시 그린다. 지금의 `onComposeGateChange` 경로는 **그대로 둔다** — 잠금 전이는
  잠금 전이의 사유이고, 목록 갱신은 목록 변경의 사유다(두 축을 한 신호에 얹은 것이
  이 결함의 형태였다).
- **폴링 조건 확장**: `wantPoll` 에 `caps_pending` 을 더한다. 정상 상태(연결됨 + 목록 있음)
  사용자의 요청 수는 **여전히 0** 이다 — 늘어나는 것은 「질의가 도는 창」뿐이고 그 창은
  최대 수 분이다. 상한(예: 5분)을 두어 서버가 영구 `caps_pending` 을 말하는 환경에서도
  무한 폴링이 되지 않게 한다.
- **체감 대기 표면화**: 선택기가 감춰진 사유 문구에 `caps_pending` 분기를 더한다 —
  「연결된 AI 에게 쓸 수 있는 모델을 확인하는 중입니다」. §16.8 예산 1문장.
  지금은 이 상태가 「러너가 알려준 모델이 없습니다 — 최신 실행 파일로 다시 실행해 보세요」
  로 표시된다. **정상 진행 중인 상태에 «다시 실행하라» 고 말하는 것**이고, 그 오안내가
  체감 대기를 «고장» 으로 읽히게 만든다.

### 3.2 이슈 B — 계정·런타임 단위 «마지막 확인» 원장 + 재연결 시 검증

- **저장**: `WebAccounts.RunnerCapsBaseline` (JSON 텍스트, additive).
  `{"<runtime>": {"label":…, "models":[…], "efforts":[…], "confirmed_at":…, "build":…}}`
  - **계정에 둔다** — 토큰 행에 두면 재연결마다 사라진다(이슈 B 의 절반이 그것이다).
  - ALTER 는 `_ensure_bridge_heartbeat_schema` 에 둔다. **fast path
    (`_ensure_seed_catchup`) 에서도 불리는 유일한 자리**이고, slow path 전용에 두면
    운영 DB 에 컬럼이 생기지 않는다 (선례: `BridgeDefaultModel` 이 정확히 그렇게 죽어
    있었다 — TASK-20260902T110000 §2.4).
  - 갱신 주체는 **`source=probe` 신고뿐**. 즉 원장은 언제나 «그 계정의 AI 가 직접 답한
    내용» 에서만 자란다.
- **전달**: `bridge_heartbeat` 응답에 `caps_baseline` 을 실어 러너에 준다. 러너가 이미
  30초마다 부르는 채널이고 인증도 같다(전용 도구를 만들지 않는 이유는
  `ai_tools.py:4557` 의 「도구 표면 = 가이드 = capabilities」 계약을 끌어들이지 않기 위해).
- **검증**: 러너는 로컬 캐시가 없을 때 이 baseline 을 열린 질의의 대체가 아니라
  **좁은 확인 질의**의 입력으로 쓴다 — 「이 목록 중 지금 쓸 수 있는 것은 무엇이고, 빠진
  것이 있으면 더하라」. 열린 열거보다 답이 안정적이다(요구가 좁을수록 흔들림이 적다는
  것은 이 코드베이스가 `_CAPS_EFFORT_PROMPT` 로 이미 확인한 성질이다).
- **비축소 규약 (핵심)**: 질의 실패·timeout 은 **로컬 캐시가 있는 런타임의 목록을 줄이지
  않는다**. 종전 열린 재질의는 답이 흔들리면 그만큼 목록을 갈아치웠고, 실패하면 그 런타임을
  통째로 지웠다 — 그것이 제보의 「실행할 때마다 다르다」의 가장 큰 몫이다. 확인 질의는
  「이 목록 중 지금 쓸 수 있는 것 **+ 빠진 것**」을 한 번에 묻기 때문에, 안정화(직전 목록
  보존)와 확인(라이브 근거)이 같은 왕복에서 성립한다.
- **베이스라인만 있는 런타임은 확인 전까지 신고하지 않는다** (사용자 결정 2026-09-02 —
  「확인-후-표시」). 확인이 실패하면 그 회차에는 신고하지 않고(화면에서 안 보임) 서버
  baseline 은 그대로 남아 다음 회차가 다시 시도한다. 즉 «비축소» 는 *로컬 캐시* 축의
  계약이고, *서버 baseline* 축은 «확인 없이는 화면에 못 간다» 가 계약이다 — 두 축을
  한 문장으로 뭉치면 어느 한쪽이 반드시 틀린다.
- **provenance**: 확인을 통과한 항목의 출처는 `verified`. 러너
  `_REPORTABLE_SOURCES`(`caps.py:862`)와 서버
  `_SANITIZE_SOURCE_ALLOW`(`ai_tools.py:4481`)를 **함께** 넓힌다 — 두 집합이 같은지는
  구조 테스트가 이미 대조한다(`tests/test_runtime_model_selector.py:1522-1529`).
  `builtin`(우리 소스의 표)은 **여전히 넣지 않는다.**

### 3.3 이 설계가 되살릴 수 있는 결함 클래스 (명시)

서버가 모델 목록을 보관한다는 것은 **caps-trust-gate 사고와 같은 «모양»** 이다 —
사용자 제보 4회를 만든 `gpt-5.1-codex` 화석이 정확히 「우리가 들고 있던 목록을 화면에
그린」 형태였다. 다른 점은 출처와 만료뿐이므로, 그 둘을 계약으로 못박는다.

| 화석 방지 장치 | 내용 |
|---|---|
| 출처 한정 | baseline 은 **그 계정 자신의 `probe` 신고**에서만 자란다. `builtin` 유입 경로 없음 |
| 만료 | `last_used_at` 이 **14일** 넘게 낡은 항목은 baseline 에서 제외해 내려보내지 않는다 (아래 §3.4) |
| 확인 없이는 신고 안 함 | baseline 자체는 **화면에 직행하지 않는다.** 러너의 확인을 통과해야 신고 목록이 된다 |
| 사용자 탈출구 | `--refresh-caps` 는 baseline 을 무시하고 전면 재질의 (기존 의미 유지) |

### 3.4 만료는 **생성일이 아니라 사용일** 기준 (사용자 결정 2026-09-02)

`created_at`/`confirmed_at` 고정 기준으로 만료시키면, **매일 쓰는 런타임도 14일마다 한 번씩
전면 재질의로 떨어진다** — 안정성을 얻으려고 만든 원장이 주기적으로 불안정을 재생산한다.
그래서 항목마다 `last_used_at` 을 두고 **쓰일 때마다 갱신**한다.

- **«사용» 의 정의 = 살아 있는 러너가 그 런타임을 신고·확인한 순간.** 하트비트는 30초마다
  능력을 매번 싣기 때문에(`agent/lifecycle.py:184` — 「능력은 **매번** 싣는다」), 실제로
  쓰이는 런타임의 `last_used_at` 은 연결돼 있는 동안 계속 현재로 유지된다.
- 그 런타임으로 작업이 실제 위임되는 경로는 «러너가 신고 중» 의 부분집합이다(작업을 집는
  러너는 하트비트를 보내고 있다) — 별 갱신 지점을 두지 않는다. 두 곳에서 갱신하면 같은
  사실을 두 번 세게 되고, 한쪽만 고쳐지는 날 만료 판정이 갈린다.
- 따라서 만료되는 것은 **14일 넘게 어떤 러너도 신고하지 않은 런타임**뿐이다 — 「그 계정이
  더 이상 쓰지 않는 CLI」가 정확히 그 모집단이고, 화석이 될 수 있는 것도 그것뿐이다.
- `confirmed_at` 도 함께 남긴다(만료 판정에는 쓰지 않는다) — 「언제 라이브로 확인됐는가」는
  사고 조사에서 `last_used_at` 과 다른 사실이다.

## 4. 완료 판정 기준 (AC)

- **AC-1** (이슈 A): 러너를 새로 띄운 뒤 **새로고침 없이**, 능력 질의가 끝나는 시점부터
  ≤10초 안에 모델·추론등급 선택기가 화면에 나타난다.
- **AC-2** (이슈 A): 능력 질의가 도는 동안 선택기 자리의 문구가
  「…확인하는 중」이다 (지금의 「최신 실행 파일로 다시 실행해 보세요」가 아니다).
- **AC-3** (이슈 A, 무회귀): 연결·목록이 모두 성립한 정상 상태에서
  `/api/ai/connect/status` 폴링 요청 수가 **0** 이다.
- **AC-4** (이슈 B): 같은 계정·같은 머신에서 로컬 `config.json` 을 지우고 러너를 다시
  띄웠을 때, 신고 목록이 직전 실행과 **같다**(baseline 검증 경로).
- **AC-5** (이슈 B, 비축소): **로컬 캐시가 있는** 런타임은 확인 질의가 실패해도 신고 목록에서
  사라지지 않는다(직전 목록 유지 + 그 사실이 러너 로그에 남는다).
- **AC-6** (화석 방지): baseline 에만 있고 러너 확인을 통과하지 **못한** 항목은
  `/api/api-vault/options` 응답에 **실리지 않는다** (사용자 결정 「확인-후-표시」).
- **AC-9** (사용일 만료): 14일 넘게 신고되지 않은 런타임은 baseline 에서 빠지고, 매일
  신고되는 런타임은 **경과일과 무관하게 유지**된다 (`last_used_at` 갱신형).
- **AC-7** (기존 배포 무회귀): 재기동만으로 `RunnerCapsBaseline` 컬럼이 생긴다(fast path).
- **AC-8** (구 러너 무회귀): baseline 을 모르는 구 러너는 종전과 동일하게 동작한다
  (`caps_baseline` 을 무시할 뿐).

## 5. 위험도

**Major** (§12.3).

- 인증·인가 변경 **0** — 신규 권한 코드 없음, 본인 계정 스코프, 신규 route path 0
  (기존 엔드포인트 응답 필드 확장 + 기존 하트비트 응답 확장).
- 파괴적 데이터 **0** — additive 컬럼 1개, 기존 컬럼·테이블 무변경.
- 파괴적 side-effect **0** — 배포는 재배포로 원복 가능(§16.5.1).
- 주의 축 둘:
  1. **화석 재발** — §3.3 의 4중 장치로 가둔다. 회귀 잠금은 AC-6.
  2. **요청 수 증가** — 폴링 조건 확장은 `caps_pending` 창에만 적용하고 상한을 둔다.
     회귀 잠금은 AC-3.

## 6. 영향 파일 (계획)

| 파일 | 변경 | 심볼 |
|---|---|---|
| `unit/feature-0003-agent-web-ui/src/routers/_bootstrap_schema.py` | `RunnerCapsBaseline` fast-path ALTER | `_ensure_bridge_heartbeat_schema` |
| `unit/feature-0003-agent-web-ui/src/oauth_store.py` | baseline 읽기·병합 쓰기 | `account_caps_baseline` · `merge_account_caps_baseline` |
| `unit/feature-0003-agent-web-ui/src/routers/oauth_as.py` | 상태 응답에 `caps_rev`·`caps_pending` | `connect_status` |
| `unit/feature-0003-agent-web-ui/src/routers/ai_tools.py` | baseline 갱신 + 응답 전달 + `verified` 허용 | `bridge_heartbeat` · `_SANITIZE_SOURCE_ALLOW` |
| `shared/bridge_caps.py` (**신규**) | 지문·병합·만료 순수 함수 | `caps_revision` · `merge_baseline` · `prune_stale` |
| `unit/feature-0003-agent-web-ui/src/static/app/connect-modal.js` | `caps_rev` 변화 감지 · 폴링 조건 | `refreshConnState` · `_syncGatePoll` |
| `unit/feature-0003-agent-web-ui/src/routers/system.py` | `caps_pending` 사유 문구 분기 | `api_vault_options` |
| `unit/feature-0043-external-llm-bridge/src/agent/caps.py` | 확인 질의 · 비축소 · `verified` 출처 | `detect_runtimes` · `_REPORTABLE_SOURCES` |
| `unit/feature-0043-external-llm-bridge/src/agent/lifecycle.py` | baseline 수신 → 협상 입력 | `_negotiate_caps` · `start_heartbeat` |

> `shared/bridge_tasks.py` 는 **건드리지 않는다** — 활성 세션 2개
> (`feature-0043-ai-jobs-perm-gate` · `ai-jobs-rewire-external`)가 그 파일을 hot_path 로
> 선언 중이다(§13.2.5-A). 신규 순수 로직은 별 모듈로 분리해 충돌 표면을 만들지 않는다.

## 7. 검증 계획

- 단위: 지문·병합·만료 순수 함수 · `_sanitize_runtimes` provenance 확장 ·
  구조 테스트(양쪽 허용집합 동일) · 비축소 규약 · fast-path ALTER.
- **결손 주입 (§16.7 G11-b)**: 새 구조 단언은 «수정 전 코드에서 FAIL 함» 을 1회 실증한다.
- 라이브: PB-0008 실 Windows 브라우저 — `visual_verification_scope: always` 이므로
  웹 자산 변경의 **hard gate** 다(check #13). AC-1·AC-2 는 라이브에서만 판정된다.
- 적대 검증: §18.8 dispatch (`API/endpoint` + `caching` 키워드 → backend·security·qa).

## 8. 승인 · 사용자 결정 (2026-09-02)

1. **표시 시점 = 「확인-후-표시」** — baseline 은 러너 확인을 통과한 뒤에만 화면에 오른다.
   즉시-표시-후-정정은 기각(화석 클래스 재개 회피).
2. **만료 = 14일 유지, 단 «생성일» 이 아니라 «사용일» 기준** — `last_used_at` 을 쓰일 때마다
   갱신하고 그 기준으로 판정한다 (§3.4).

<!-- PLAN-APPROVED by mckim on 2026-09-02 -->
