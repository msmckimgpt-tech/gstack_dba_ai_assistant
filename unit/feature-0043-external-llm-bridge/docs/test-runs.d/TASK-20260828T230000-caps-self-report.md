# Run — TASK-20260828T230000-caps-self-report (P0-Z4)

- **일시**: 2026-08-28
- **Environment**: container (`make test`) + host (실제 AI 질의 실측)
- **대상**: 능력 목록을 AI 자신이 정하게 하는 전환

## 결과

| 스위트 | 결과 |
|---|---|
| `make test` 전량 (feature-0002·0003·0014·0020·0023·0041·0043·0008) | **PASS** (exit 0) |
| ruff | All checks passed |
| feature-0043 스위트 | 587건 PASS (신규 14건) |

## 라이브 실측 — 실제로 물어봤다

이 변경의 핵심 주장("AI 가 자기 능력을 형식대로 답할 수 있다")은 실제로 물어봐야만 검증된다.

```
claude probe: 22.7s
  {"label":"Claude","models":[opus, sonnet, haiku, fable],
   "efforts":[low, medium, high, xhigh, max],
   "model":["--model","{model}"], "effort":["--effort","{effort}"]}

codex probe: 112.3s
  {"label":"Codex","models":[gpt-5.6-sol, gpt-5.6-terra],
   "efforts":[low, medium, high, xhigh, max, ultra],
   "model":["--model","{model}"], "effort":["-c","model_reasoning_effort={effort}"]}

병렬 전체: 162.1s (claude 4종·5단계 · codex 6종·6단계)
```

**내 표가 틀렸다는 것이 이 실측으로 드러났다** — codex 의 모델 이름(`gpt-5.1-codex`)도
플래그(`-m`)도 둘 다 오답이었고, claude 는 `fable` 이 빠져 있었다.

## 신뢰 경계 실측

```
신고 blob 에 '--model' 포함:      False
신고 blob 에 '{model}' 포함:      False
신고 dict 키:  {runtime, label, models, efforts}   ← 호출법 없음
로컬 detail:   claude model=['--model','{model}'] effort=['--effort','{effort}']
               codex  model=['--model','{model}'] effort=['-c','model_reasoning_effort={effort}']
```

## 관대한 수용 실측

| 입력 | 결과 |
|---|---|
| ` ```json {...} ``` ` | 파싱 성공 |
| `답변드립니다:\n{...}\n이상입니다.` | 파싱 성공 |
| `앞에 {깨진 것 } 뒤에 {"models":["x"]}` | 깨진 후보 건너뛰고 성공 |
| `["opus","sonnet"]` | value=label 승격 |
| `[{"name":"o3"}]` · `[{"id":"gpt-5.1"}]` | 키 대체 수용 |
| `{"opus":"Opus"}` | 매핑 → 목록 |
| `["ok","--evil","a b",""]` | `ok` 만 통과 |

## 표 밖 CLI 실측 (가상 `mycli`)

```
지정 O : ['mycli','-p','--use-model','big','--think','deep','Q']
신고밖 : ['mycli','-p','--think','deep','Q']          (모델만 탈락)
주입   : ['mycli','-p','Q']                            (둘 다 탈락)
```

## 실측으로만 드러난 자기 결함 2건

1. **timeout 0** — `float(os.environ.get(k,"0") or 120.0)` 에서 `"0"` 이 truthy 라 `or` 가
   단락되지 않아 timeout 이 0. 질의가 시작 즉시 `TimeoutExpired` 로 죽고 폴백이 삼켜
   "AI 가 답을 안 했다" 로 보였다. 단위 테스트로는 안 잡힌다(어느 값이든 정상 반환).
2. **테스트가 실제 AI 를 호출** — `detect_runtimes` 가 기본으로 질의하게 두어 스위트가
   120초 타임아웃에 걸렸다. 명시적 옵트인(`probe=True`)으로 전환.

## 미수행 (정직 표기)

- **PB-0008 시각검증** — 4-B 와 같은 사유. 화면에 새 목록이 뜨려면 배포 + **사용자의 러너
  재기동**(새 `mat_` 토큰 필요)이 선행되어야 하고, 그 재기동은 AI 가 무인으로 완결할 수 없다.
  배포 직후 화면은 정상적으로 종전 목록(구 러너의 신고)을 보인다.
- **AI 응답의 진위** — AI 가 없는 모델을 답하면(환각) 그 모델 실행이 실패하고 기본값으로
  답한다(`unmet` 고지가 사용자에게 알림). 목록 자체를 검증하려면 다시 우리 표로 거르는
  셈이라 요구와 충돌한다 — **의도적으로 검증하지 않는다**.
- **장기 캐시 정합** — CLI 가 업데이트되어 모델이 바뀌어도 캐시는 그대로다.
  `--refresh-caps` 가 유일한 갱신 수단이며, 자동 만료는 두지 않았다(질의 비용 때문).
