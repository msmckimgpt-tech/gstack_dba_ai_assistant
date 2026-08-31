# Run — REV-20260831T170000 모델 선택기 플랫폼 그룹 트리 (feature-0003 프론트)

- **일시**: 2026-08-31
- **Environment**: **Windows-browser** (PB-0008, bind-mount 격리 `https://localhost:18099`)
- **대상**: `static/app/composer.js` `_renderComposerModelMenu` + `static/css/chat.css`
- **구동 맥락**: feature-0043 `TASK-20260831T170000-model-tree`. 코드 소유가 feature-0003 이라
  시각검증 Run 은 여기 기록한다.

## 무엇을 봤나

라이브 무접촉. 라이브 web 이미지 + 이 브랜치의 `static/`·`routers/`·`oauth_store.py` 만
bind-mount. 러너는 제품 경로 그대로 연결(토큰 발급 → 러너 기동 → 하트비트 신고).

## 렌더 실측 — 두 그룹

```
── CLAUDE
   Opus / Sonnet / Haiku / Fable
── CODEX
   GPT-5.6 Sol / GPT-5.6 Terra / GPT-5.6 Luna / GPT-5.5 / GPT-5.4 / GPT-5.4 Mini
```

- 머리글은 `div[role=presentation]` — 선택할 수 없고 키보드 이동에도 걸리지 않는다
- 트리에서는 그룹 배지를 달지 않는다(머리글과 같은 말을 두 번 쓰지 않는다)
- **`gpt-5.1-*` 소멸 확인** — 사용자 제보의 대상이던 폐기 세대가 목록에서 사라졌다

캡처: `model-group-tree.png`

## 폴백 제거가 실제로 동작한다

같은 세션 초반, claude 인증이 없는 격리 HOME 에서 probe 가 실패했을 때:

```
[bridge]   claude: 응답을 받지 못해 내장 기본값을 씁니다.
[bridge] 고를 수 있는 것: Codex(6종, 추론 5단계)
```

**claude 그룹이 아예 나타나지 않는다** — 종전이라면 내장 표의 `opus/sonnet/haiku` 가 올라왔을
자리다. 인증을 링크해 다시 물으니 4종(`fable` 포함)이 신고되며 그룹이 생겼다. 즉 목록은
「그 AI 가 답한 사실」에만 따른다.

## 참고 — 라벨은 신고를 그대로 쓴다

이번 실행에서 claude 는 등급 라벨을 영문(`Low`)으로 답했고 화면도 그대로 `Low` 다. 직전
cycle 에서 라벨 출처를 신고로 옮긴 결과이며(서버 표를 쓰면 러너 어휘를 못 찾는다), AI 응답이
실행마다 조금씩 달라지는 것은 이 설계가 수용하는 범위다.
