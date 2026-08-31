# Run — REV-20260831T110000 추론등급 라벨이 러너 어휘를 표시하지 못했다 (feature-0003 프론트)

- **일시**: 2026-08-31
- **Environment**: **Windows-browser** (PB-0008, bind-mount 격리 인스턴스 `https://localhost:18099`)
- **대상**: `static/app/composer.js` — 등급 라벨·현재값 사슬·모델 필드 전송 가드
- **구동 맥락**: feature-0043 `TASK-20260831T110000-runtime-caps-restore` (브리지 모델·등급 축 복구).
  코드 소유가 feature-0003 이므로 시각검증 Run 은 여기 기록한다.

## 무엇을 봤나

라이브 무접촉. 라이브 이미지(`mysql-ai-web:dae0903d`) + 이 브랜치의 `static/`·`routers/`·
`oauth_store.py` 만 bind-mount 한 별도 컨테이너. 러너는 제품 경로 그대로 연결
(`/api/ai/connect/token` 발급 → 러너 기동 → 하트비트 능력 신고).

## 발견 — 소스 검사로는 영원히 안 잡히는 1건

등급 메뉴에서 `매우높음`(`xhigh`)을 고르면:

```
{"selectedInMenu":["xhigh"], "label":"일반"}
```

**메뉴 항목은 선택 표시인데 버튼 라벨만 "일반"** 이다. `_reasoningLevelLabel` 은 서버 LLM 어휘
(`low/normal/high/max`)의 표라, 러너 어휘(`medium`·`xhigh`)를 넘기면 못 찾고 기본 라벨로 떨어진다.

고른 값 **자체는 정상 전송되고 있었다** — 어긋난 것은 표시 계층뿐이다. 그래서 값만 보는
단위 테스트·소스 검사는 전부 통과한다. 그러나 사용자에게는 자기가 고른 등급이 적용됐는지
확인할 수 없는 화면이고, 그것이 이번 제보("사용할 모델, effort 가 확인되지 않는다")의 한 표면이다.

## 수정 후 재확인

`_composerReasoningLabelFor` 신설 — 브리지 모드에서는 **신고가 준 라벨**을 정본으로 쓴다.

```
{"labelAfterPick":"매우높음", "selected":["xhigh"]}
```

## 함께 확인한 렌더 (`caps-reasoning-menu.png`)

| 항목 | 결과 |
|---|---|
| `모델: Opus` · `추론 강도: 낮음` | 둘 다 보임 + 활성 (수정 전에는 등급 항목이 사라졌다) |
| 등급 메뉴 | **5단계 실제 렌더** — 낮음/보통/높음/매우높음/최대 |
| 모델 메뉴 | `claude:opus/sonnet/haiku` + `codex:gpt-5.1-codex(-mini)` (그룹 배지 Claude/Codex) |
| 러너 미연결 시 | `model_selector: hidden` · 새 필드 `default_reasoning_level` 도 추측하지 않음 |

## 모델 필드 전송 가드 (codex P1-6)

카탈로그를 확보하기 전에는 모델·등급을 싣지 않도록 좁혔다. 종전에는 카탈로그 미로드 상태의
`_composerCurrentModel()` 이 서버 alias(`claude-haiku-4`)로 폴백하고, 그것을 실어 보내면 서버가
`model_explicit=True` 로 읽어 **사용자가 고른 적 없는 값이 그 질문에 굳었다**
(라이브 `WebAiTasks` #69·#70 이 그 형태였다 — 서버측 분기만으로는 막지 못하는 경로다).

end-to-end 확인: `Sonnet` + `매우높음` 선택 후 전송 → 적재값 `claude / sonnet / xhigh`
(수정 전 동일 계정 요청은 `NULL / claude-haiku-4 / NULL`).

## 정리

격리 컨테이너 제거 · 검증 러너 종료 · 검증에서 발급한 토큰 2건 폐기.
