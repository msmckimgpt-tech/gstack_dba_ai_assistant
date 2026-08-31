# Run — TASK-20260831T110000-runtime-caps-restore (P0-AE)

- **일시**: 2026-08-31
- **Environment**: container (`make test` 전량) + **Windows-browser** (PB-0008, bind-mount 격리 인스턴스)
- **대상**: 능력 축 복구 · 서버 alias 오염 차단 · 계정 기본값 · 반영 고지

## 결과

| 스위트 | 결과 |
|---|---|
| 전량 (feature-0002·0003·0014·0020·0023·0041·0043·0008) | **PASS** |
| ruff | All checks passed |
| 신규 회귀 | 25건(러너 12 · 카탈로그 5 · 요청 고정 8) + 기존 계약 5건 갱신 |

## 수정 전 라이브 상태 (증상 재현)

계정 10 의 살아 있는 러너 신고 — `claude` 의 등급 축이 비어 있다:

```
claude | models: ['opus','sonnet','haiku']   efforts: (비어 있음)
codex  | models: ['gpt-5.1-codex', …]        efforts: ['low','medium','high']
```

러너 캐시(`~/.mysql-ai-bridge/config.json`)도 같은 사실을 말한다 — `"efforts": [], "effort": null,
"source": "probe"`. 그런데 `claude --help` 에는 `--effort <level>` 이 **실재한다**. 지원하지 않아서
빈 것이 아니라, AI 가 다섯 필드를 요구하는 JSON 에서 `effort_flag` 한 칸을 빠뜨린 것이다.

같은 창의 `WebAiTasks` 두 건은 사용자가 고른 적 없는 서버 alias 로 적재돼 있었다:

```
#70  RequestedRuntime=NULL  RequestedModel='claude-haiku-4'  ReasoningLevel=NULL
#69  (동일)
#68 (8/28)  claude / sonnet / high     ← 정상이던 시기
```

## 복구 경로 실측 (러너)

실제 stale 캐시를 심고 새 코드로 기동:

```
[bridge] claude: 추론 수준을 다시 물어보는 중…
[bridge] claude: 추론 수준을 답하지 않아 내장 표로 보완했다 (--help 로 실재 확인).
[bridge]   claude: 모델 3종 · 추론 5단계 (본인 응답)
[bridge] 고를 수 있는 것: Claude(3종, 추론 5단계) · Codex(2종, 추론 3단계)
```

두 경로가 **모두** 실제로 동작한다:

| 경로 | 실측 |
|---|---|
| ① 축만 좁게 재질의 | claude 가 `--effort` + `low/medium/high/xhigh/max` 를 정확히 응답 |
| ② `--help` 검증 후 내장 표 | claude 5단계 · codex 3단계 복구 · **gemini 는 정확히 비움**(플래그 없음) |
| 캐시 표지 | `effort_probed: True` 저장 → 재기동 시 claude 는 묻지 않고 codex 만 물음 |
| 신고 키 | `{runtime,label,models,efforts}` 4개 유지 — 플래그 비유출 계약 불변 |

## PB-0008 실 Windows 브라우저

라이브 **무접촉**. 라이브 이미지(`mysql-ai-web:dae0903d`) + 이 브랜치의 `static/`·`routers/`·
`oauth_store.py` 만 bind-mount 한 별도 컨테이너(`web-verify-caps`, `https://localhost:18099`).
세션은 `session-login`(bootstrap_admin), 러너는 **제품 경로 그대로** 연결
(`/api/ai/connect/token` 발급 → 러너 기동 → 하트비트 신고).

### 러너 미연결 (안전판 유지)

```
{"selector":"hidden","source":"","def":null,"defLevel":"","models":[]}
```

새 필드(`default_reasoning_level`)도 추측하지 않는다.

### 러너 연결 후

```
{"selector":"visible","source":"runner","def":"claude:opus","defLevel":"",
 "models":["claude:opus|Claude","claude:sonnet|Claude","claude:haiku|Claude",
           "codex:gpt-5.1-codex|Codex","codex:gpt-5.1-codex-mini|Codex"],
 "levels":{"claude":[low,medium,high,xhigh,max], "codex":[low,medium,high]}}
```

화면 (`caps-reasoning-menu.png`):

- `모델: Opus` · **`추론 강도: 낮음`** 두 항목 모두 보이고 활성 (수정 전에는 등급 항목이 사라졌다)
- 등급 메뉴에 **5단계 실제 렌더** — 낮음/보통/높음/매우높음/최대
- 하단 `● 내 AI 대기 중` 연결 칩

### 실 브라우저가 아니었으면 못 잡았을 1건

등급을 `xhigh` 로 고르면 **메뉴 항목은 선택 표시인데 버튼 라벨만 "일반"** 이었다.
`_reasoningLevelLabel` 은 서버 LLM 어휘(low/normal/high/max)의 표라 러너 어휘를 못 찾고 기본
라벨로 떨어진다. 고른 값 자체는 정상 전송되고 있었으므로 **어긋난 것은 표시 계층뿐**이고,
소스 검사·단위 테스트로는 드러나지 않는다(둘 다 값만 본다). 사용자에게는 "무엇이 적용됐는지
확인되지 않는" 바로 그 상태로 보인다. `_composerReasoningLabelFor` 로 신고 라벨을 쓰게 고쳤고,
수정 후 재확인: `xhigh` 선택 → 라벨 **"매우높음"**.

### end-to-end — 지정값이 실제 실행에 도달하는가

웹에서 `Sonnet` + `매우높음` 선택 후 질문:

```
[bridge] t_D2vXtD5R0EV_nX7q: 내 AI(claude)에게 전달, 모델 sonnet, 추론 xhigh
[bridge] t_D2vXtD5R0EV_nX7q: 제출 완료 (대화 반영=True)
```

적재값이 수정 전후로 정확히 갈린다:

```
#71 (새 코드)   claude / sonnet / xhigh
#70 (수정 전)   NULL / claude-haiku-4 / NULL
```

답변 말풍선에 고지 표시 확인 (`caps-applied-notice.png`):
**"이 답변은 claude 의 모델 sonnet · 추론등급 xhigh 로 생성했습니다."**

인자 조립도 직접 확인:

```
claude -p --strict-mcp-config --model opus --effort xhigh <질문>
신고 밖 등급(ultra) → 버려짐:  … --model opus <질문>
```

> 이 실행 자체는 격리 HOME 이라 claude 설정이 없어 `exit 1` 로 끝났다(권한 규칙 오류).
> 기능과 무관한 환경 제약이며, **검증 대상인 "지정값이 인자로 전달되는가" 는 그대로 관측됐다.**
> 다만 그 화면이 "생성하지 못했다" 와 "…로 생성했습니다" 를 **함께** 보여줬고, 그것이 정직하지
> 않아 고지를 `ok` 일 때만 붙이도록 고쳤다(회귀 잠금).

## codex 적대 리뷰 (REV-20260831T110000)

P1 7건 · P2 6건 중 12건 조치, 1건은 잔여 위험으로 기록. 상세는 `meta/REVIEW.md`.

## 정리

격리 컨테이너 제거 · 검증용 러너 종료 · 검증에서 발급한 토큰 2건 폐기(#50·#51).
