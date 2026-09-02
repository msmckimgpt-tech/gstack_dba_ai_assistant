---
doc_type: TASK_NOTE
feature_id: feature-0043-external-llm-bridge
task_id: TASK-20260902T110000-console-job-model-prefs
status: in-progress
edit_policy: append-only
---

# TASK-20260902T110000 — 콘솔 작업의 모델·추론등급을 계정이 정한다

## 1. 어디서 왔나

**사용자 제보 (2026-09-02)**: 「그래프 뷰 기능의 능동 분석을 진행할 경우 경량모델이 아닌
fable 및 opus 로 진행되는 이슈가 확인되었습니다. effort 또한 low 로 확인되어 해당 이슈에 대한
해소가 필요합니다.」

## 2. 근본원인 (라이브 실측 2026-09-02)

세 층이 겹쳐 있다.

### 2.1 추론등급은 서버가 **아예 지정하지 않는다**

`routers/ai_tools.py:_claim_console_job` 이 claim 응답에 `"reasoning_level": ""` 를 **고정**으로
싣는다(주석: "등급 어휘는 러너마다 다르니 추측하지 않는다 — 모델만 낮춘다"). 지정이 없으면
러너 `bridge_agent.handle_one` 은 `want_effort=None` 이 되어 `--effort` 플래그 자체를 붙이지
않고, 실행은 **그 머신 CLI 의 기본값**을 따른다. 사용자 환경 기본이 low 면 low 로 돈다.

그런데 러너는 `efforts` 목록을 **이미 신고하고 있다**(라이브 `WebOAuthTokens.RunnerCapabilities`
실측: `low/medium/high/xhigh/max`). 신고 목록에서 고르면 그것은 추측이 아니다 — 모델 축이 이미
그렇게 하고 있다(`pick_console_job_model`).

### 2.2 모델은 지정하지만 대조 실패가 **조용히 상위로 샌다**

`shared/bridge_tasks.pick_console_job_model` 이 `("","")` 를 돌려주면 `requested.model` 이 비고,
러너는 `want_model` 이 없으니 `unmet` 고지조차 붙이지 않는다. 즉 「경량으로 돈다」는 사용자
결정(2026-09-01)이 지켜지지 않은 사실이 화면·로그·원장 **어디에도** 남지 않는다. 게다가
capabilities 조회는 «계정의 최신 하트비트 러너 1대» 라, 실제로 작업을 집는 러너와 다를 수 있다.

### 2.3 무엇으로 돌았는지가 서버에 남지 않는다

`WebAiTasks` 에 `RequestedRuntime`/`RequestedModel`/`ReasoningLevel` 컬럼이 **이미 있는데**
콘솔 작업 경로는 NULL 로 둔다(라이브 최근 job 7건 전부 NULL 실측). 그래서 제보를 서버에서
검증할 수 없고 개인 머신 러너 로그를 봐야만 안다 — 이번 진단이 그 마찰을 그대로 겪었다.

### 2.4 (동반 발견) 대화 축 계정 기본값이 라이브에서 죽어 있다

`WebAccounts.BridgeDefaultModel`/`BridgeDefaultEffort` ALTER 가 **slow path
(`_ensure_web_tables`) 에만** 있어 운영 DB 에 컬럼이 없다(라이브 실측: `BridgeLastOs`·
`BridgeBatchConsent` 만 존재). `set_account_bridge_defaults` 는 예외를 삼키므로 저장이 조용히
실패한다. 같은 파일의 주석이 이미 이 결함을 자기 이름으로 지목하고 있었다(codex P1-1).
신규 컬럼이 정확히 같은 함정을 밟을 자리이므로 **fast path 로 함께 옮긴다**.

## 3. 사용자 결정 (2026-09-02)

1. **추론등급**: 「계정 별 프로필 탭에 관련 설정 탭을 신설하여, 각 항목에 따라 등급을 따로
   지정할 수 있도록 구성」.
2. **거절 정책**: 「선택했던 모델 미보유 시 위임 거절」 — 즉 프로필에서 **항목별로 고른 모델**을
   연결된 러너가 제공하지 않으면 그 작업을 위임하지 않는다.

## 4. 설계

### 4.1 저장소 — `WebAccounts.ConsoleJobPrefs` (JSON 텍스트)

```json
{"node_analysis": {"model": "claude:haiku", "effort": "medium"}, ...}
```

- 항목 키는 `JOB_SPECS` 의 종류로 **닫는다**(모르는 키는 정규화 단계에서 버린다).
- 모델 값은 대화 축과 **같은 어휘** `runtime:model` (러너 자기 어휘 — 그대로 CLI 인자가 된다).
- ALTER 는 `_ensure_bridge_heartbeat_schema`(**fast path 에서도 불리는 유일한 함수**)에 둔다.
  §2.4 의 두 컬럼도 같은 자리로 옮긴다.

### 4.2 해석 정본 — `shared/bridge_tasks`

| 심볼 | 역할 |
|---|---|
| `normalize_console_job_prefs(raw)` | 저장·조회 양쪽이 쓰는 정규화(닫힌 키·길이 상한) |
| `resolve_console_job_request(job_kind, prefs, capabilities)` | claim 이 실을 `{runtime, model, effort, unmet}` 산출 |
| `console_job_model_required(job_kind, prefs)` | 「이 계정이 이 항목에 모델을 골랐는가」 |
| `runner_can_take(..., required_model=…)` | 배급 자격에 «고른 모델 보유» 를 더한다 |

**미설정 계정은 종전 동작**(경량 선호 `CONSOLE_JOB_LIGHT_MODELS` 폴백, 대조 실패해도 거절
안 함). 거절은 «고른 것이 있는데 없을 때» 만이다 — 아무것도 고르지 않은 사용자의 작업을
새 규칙이 통째로 막으면 그것은 해소가 아니라 새 장애다.

**등급은 거절 사유가 아니다.** 고른 등급을 러너가 못 주면 빈 값으로 보내고(러너 기본) 그
사실을 `unmet` 에 남긴다 — 등급은 실행 가능성을 좌우하지 않는다.

### 4.3 배선

| 파일 | 변경 |
|---|---|
| `routers/_bootstrap_schema.py` | `ConsoleJobPrefs` + (이동) `BridgeDefaultModel`/`BridgeDefaultEffort` fast path ALTER |
| `oauth_store.py` | `account_console_job_prefs` / `set_account_console_job_prefs` |
| `routers/profile.py` | `GET`·`PUT /api/profile/console-jobs` (로그인 스코프, 본인 계정) |
| `routers/ai_tools.py` | `_claim_console_job` → 설정 기반 `requested` 송출 + 미충족이면 claim 거절 + 원장 기록 |
| `routers/_console_llm.py` | 사유 `DELEGATION_MODEL_UNAVAILABLE` 추가(화면이 왜 못 맡기는지 말한다) |
| `modules/node_analysis.py`·`semantic_cluster.py`·`insight.py` | 적재 게이트에 같은 판정 전달 |
| `static/index.html`·`static/app/profile.js` | 프로필 drawer 탭 「AI 작업」 신설 |

### 4.4 완료 판정 기준 (AC)

- **AC-1**: 프로필 > AI 작업 탭에서 `node_analysis` 의 모델을 `claude:haiku`, 등급을 `medium`
  으로 저장하면, 그 계정의 다음 능동 분석 claim 응답의 `requested` 가
  `{"runtime":"claude","model":"haiku","reasoning_level":"medium"}` 이다.
- **AC-2**: 러너 신고 목록에 그 모델이 없으면 그 계정의 그 작업은 **적재·claim 되지 않고**,
  화면이 사유(고른 모델 미보유)를 말한다.
- **AC-3**: 미설정 계정은 종전대로 경량 선호로 돌고 거절되지 않는다(무회귀).
- **AC-4**: claim 이 확정한 `(runtime, model, effort)` 가 `WebAiTasks` 행에 남는다.
- **AC-5**: 기존 배포 DB 에서 재기동만으로 `ConsoleJobPrefs` 컬럼이 생긴다(fast path).

### 4.5 위험도

**Major** — 인증·인가 변경 0(신규 권한 코드 0, 본인 계정 스코프), 파괴적 데이터 0(additive
컬럼). 다만 배급 자격 판정을 좁히므로 «설정 실수로 분석이 전부 멈추는» 경로가 생긴다 →
미설정 무회귀(AC-3)와 사유 표면화(AC-2)로 가둔다.

<!-- PLAN-APPROVED by mckim on 2026-09-02 -->
