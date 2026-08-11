# REV-20260811T120000 리뷰어 발췌 앵커링 — 라이브 실측 (PB-0008)

- **대상**: 배포본 `649d9b03`(web-a/web-b/ask-worker/insight-worker 동일 커밋).
- **방법**: `bin/win-browser.py` 로 실제 Windows Chrome 을 CDP 구동, 배포된 web UI 를 사람과 동일한
  경로로 조작(§15.4.1 PB-0008). DB 는 replica 읽기 전용 조회만.
- **관측 대상**: `FR-redteam-attach-excerpt-cap-false-grounding-block` — *정확한 답변이 첨부 꼬리를
  근거로 삼았다는 이유로 grounding BLOCK 을 맞고 `⚠️ 자가 검증 미해소` 배너가 붙는가.*

## 측정 이력 (같은 대화 반복 + 격리 1회)

| # | run | 조건 | red-team 결과 |
|---|---|---|---|
| 1 | `20260807040816-3a3b6f52` | 수정 전(BEFORE) | `revise · 1 block · revise_failed` → 배너 |
| 2 | `20260811025604-5386c583` | 앵커링 배포(`4c7a8f27`) | `revise · 1 block` — **여전히 BLOCK** |
| 3 | `20260811031709-7f1ff22c` | 예산 수정 배포(`649d9b03`) | `revise · 1 block` — **측정 오염**(아래) |
| 4 | `20260811032010-7da1b285` | 예산 수정 배포, **격리 조건** | **`pass · 0 block · resolved`** |

## #2 가 잡아낸 배포본 결함 2건 (수정 완료)

리뷰어 근거 "그 파일 내용이 제시되지 않았습니다" 는 **사실이었다** — 코드로 재구성해 확인했다.

1. **겹치는 인용 창의 예산 이중과금** — 같은 꼬리 영역을 가리키는 probe 두 개가 예산을 두 번 먹어
   실제 전달이 **862/1,200 자**.
2. **조립 순서가 첨부 id 고정** — 예산이 모자라면 **질문 대상 파일**이 통째로 강등됐다
   (probe_a → ALSO ATTACHED, probe_b 만 본문).

→ `CHG-20260811T110000-redteam-excerpt-budget`. **배포본 합성 입력 실증은 통과했는데 라이브 실입력은
실패했다** — 첨부가 여러 개이고 순서가 실제 id 순일 때만 드러나는 결함이었다.

## #4 격리 측정 — 원 축 PASS

버전 비교·다중 첨부·오염을 모두 배제하고 **원 마찰 축만** 남겼다.

- 입력: 단일 첨부 `clean_probe.sql` 8,827자 / 142줄. 마지막 줄 `-- FINAL-LINE-SENTINEL: …`,
  offset **8,811**(앞머리 창 밖 — 원 마찰과 동일 형태).
- 질문: "맨 마지막 줄이 정확히 무엇인지 그대로 알려줘."
- 답변: 마지막 줄을 **정확히 인용**하고 "파일의 142번 줄" 이라고 명시.
- red-team: `verdict=pass · blocks=0 · unresolved=0 · stop=resolved` → **배너 없음**.

## 아직 BLOCK 이 나는 조건 (정직 — 원장 신규 등재)

다중 첨부 + "직전 버전 대비 무엇이 바뀌었나" 는 여전히 BLOCK 이며, 원인은 **다른 둘**이다:

- `FR-redteam-digest-lacks-prior-attachment-version` — 리뷰어는 **현재 버전만** 받는데 답변은
  프롬프트로 받은 직전 버전 diff 를 근거로 비교한다.
- `FR-redteam-verify-pass-ignores-window-rule` — verify 패스가 "네 창이 좁은 것은 assistant 의
  결함이 아니다" 규칙을 지키지 않고, 사용자가 완독을 요구하면 honesty BLOCK 을 낸다.

## 측정 오염 (자기 기록)

#3 에서 내가 **잘못된 첨부 id(938)** 를 원본으로 새 버전을 만들어 대화를 오염시켰다. 938 은 타 계정
대화의 파일이며 admin `conversation.attachment.read.any` 로 **정상 접근**된 것이다(라우트가 own/any
권한을 강제 — 접근 경계 결함 아님). 올바른 원본으로 덮었으나 버전 체인에 그 버전이 남아 있고,
#3 의 BLOCK 은 오염 탓이라 측정으로 세지 않는다.

---

## 후속 측정 (잔여 2건 수정 배포 `d7fca5fe` 후, 2026-08-11)

`FR-redteam-digest-lacks-prior-attachment-version` · `FR-redteam-verify-pass-ignores-window-rule`
수정 배포 뒤 **원 실패 시나리오를 그대로** 반복했다 — 같은 대화(다중 첨부 4건 + probe_a 재업로드),
같은 문구("파일 전체 내용을 끝까지 확인해서, 직전 버전 대비 무엇이 바뀌었는지 정확히 알려줘").

| # | run | 조건 | red-team |
|---|---|---|---|
| 1 | `20260807040816-3a3b6f52` | 수정 전 | `revise · 1 block · revise_failed` |
| 2 | `20260811025604-5386c583` | 앵커링 `4c7a8f27` | `revise · 1 block` |
| 3 | `20260811031709-7f1ff22c` | 예산수정 `649d9b03`(측정 오염) | `revise · 1 block` |
| 4 | `20260811032010-7da1b285` | 예산수정, 격리 조건 | `pass · 0 block` |
| 5 | `20260811034406-480a42a6` | 잔여 2건 수정 `d7fca5fe`, **원 시나리오** | **`pass · 0 block · resolved`** |

답변도 정확했다 — 맨 끝 1줄 추가를 diff 로 제시하고 "파일의 마지막(126번 줄)" 을 명시했다.
verify 패스도 결함 0(선행 런은 이 축에서 honesty BLOCK 을 냈다).

**원 마찰과 그 잔여 2건이 모두 라이브에서 소멸했다.**
