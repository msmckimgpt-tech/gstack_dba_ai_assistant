---
run_at: 2026-09-01T12:45:00+09:00
session: ai/claude/feature-0043-caps-trust-gate
scope: 능력 신고 자격 게이트 — 숨김 사유 1줄 렌더 · 모델/추론 항목 숨김 · 정상 경로 불변
verdict: PASS
---

# Run — TASK-20260901T123000-caps-trust-gate-ui (PRE-DEPLOY 라이브)

- Date: 2026-09-01
- Environment: **Windows-browser** (PB-0008, `bin/win-browser.py` + 실 Windows Chrome 151)
- Target: 격리 검증 컨테이너 `web-verify-capsgate` — 라이브 web 이미지 `mysql-ai-web:b793e7ea`
  + **브랜치 static 트리를 stamp 재주입 후 bind-mount**(stamp `0df767209532`)
  + 변경된 서버 4종(`routers/system.py`·`routers/ai_tools.py`·`routers/oauth_as.py`·
  `oauth_store.py`) + `shared/bridge_tasks.py`. `https://localhost:18096` (TLS=라이브 cert).
- 라이브 `web-a`/`web-b`·`caddy`·공유 트리 **무접촉** (§13.2.9 격리 경로).
- Result: **PASS**

> ⚠ **첫 시도는 라이브 사이트를 보고 있었다.** 컨테이너를 평문 HTTP(`http://localhost:18096`)로
> 띄웠더니 Chrome 이 `localhost` HSTS 로 업그레이드해 그 탭이 `https://localhost/`(**라이브**)에
> 머물렀고, 응답에 새 필드가 없자 「미구현」으로 읽힐 뻔했다. `location.href` 와 asset stamp 를
> 대조해 갈라냈다(§16.6 검증 evidence 의 identity 대조). 이후 컨테이너를 라이브 cert 로 TLS
> 기동해 `https://localhost:18096` 으로 재확인했다. **모든 관측은 stamp `0df767209532`**
> (= 내 빌드)에서 나온 것이다.

## 1. 검증 입력의 출처 (§16.6 (d)~(f))

「구 러너」 상태는 **실제 엔드포인트로** 만들었다 — DB 를 직접 쓰지 않았다.

1. `POST /api/ai/connect/token` (내 계정 `bootstrap_admin` 세션 결합) → `mat_` 발급
2. `POST /api/ai/bridge_heartbeat` 에 **구 러너가 실제로 보내는 본문**을 그대로 전송:
   `features:["console_jobs"]`(자격 없음) · `agent_build` **없음** ·
   `runtimes` 에 `codex: gpt-5.1-codex, gpt-5.1-codex-mini`

투입 자원은 전부 **이 세션이 만든 내 계정의 것**이다. 잔류물: 토큰 행 2건(`Id=85,86`) —
검증 종료 시 `session-logout` 으로 **revoke 완료**(`RevokedAt=2026-09-01 12:44:13` 실측).
검증 컨테이너·스탬프 트리도 제거했다.

## 2. 서버 판정 — 세 상태 실측

| 상태 | `model_selector` | `runner_caps_stale` | `models` | 사유 |
|---|---|---|---|---|
| 러너 없음 | `hidden` | `false` | `[]` | 「…러너가 알려준 모델이 없어…」(**종전 문구 유지**) |
| **구 러너**(자격 없음, `gpt-5.1-*` 신고) | `hidden` | **`true`** | **`[]`** | 「연결된 러너가 오래된 버전이라 … 다시 실행해 주세요.」 |
| 자격 있는 러너(`caps_self_report`) | `visible` | `false` | `["claude:opus","claude:sonnet"]` | 「연결된 본인 AI 가 쓸 수 있는 모델입니다.」 |

**`gpt-5.1` 은 어느 응답에도 실리지 않았다** — 러너가 신고했는데도 화면에 도달하지 못한다.
세 번째 행이 §16.7 **G9-c 정상 경로 실측**이다(차단이 정상 사용자를 막지 않는다).

### fail-open 해소 실측 (하트비트 응답)

지문 없는 구 러너의 `runner_update`:

```
{"current": false, "stale_build": true,
 "reason": "실행 중인 러너가 배포본과 다릅니다 — 최신 실행 파일로 다시 실행하세요."}
```

종전 판정(`deployed and reported and ...`)이면 이 러너는 `current: true` 였다 — 화면에
`gpt-5.1-codex` 가 떠 있는 동안 서버가 「최신」이라고 답하던 그 상태다.

## 3. 화면 실측 (DOM)

구 러너 상태에서 컴포저 `+` 메뉴를 열고:

| 관측 | 값 |
|---|---|
| 메뉴 열림 | `true` |
| `#composerActionsModelItem` hidden | **`true`** |
| `#composerActionsReasoningItem` hidden | **`true`** |
| `#composerActionsSelectorNote` 텍스트 | 「연결된 러너가 오래된 버전이라 모델 목록을 신뢰할 수 없습니다 — 최신 실행 파일로 다시 실행해 주세요.」 |
| 사유 실제 렌더 | `offsetParent !== null` = **`true`** |
| 사유 스타일 | `font-size: 11.5px` · `color: rgb(128,125,114)` (항목과 구분되는 안내체) |

자격 있는 러너로 전환 후 같은 메뉴:

| 관측 | 값 |
|---|---|
| 사유 `hidden` 클래스 | **`true`** · 텍스트 **빈 문자열** |
| 모델 항목 hidden | `false` · 라벨 **`Opus`** |
| 추론 항목 hidden | `false` |

목록이 돌아오면 사유가 **지워진다** — 「고를 수 없다」가 남아 있으면 그 자체가 거짓이다.

## 4. 픽셀 실측 (§16.6 픽셀-클래스)

`capsgate-stale-zoom.png` — 실제 메뉴(하단) + 2.2배 확대 사본(좌상단).

- 메뉴 폭 520px 안에서 안내가 **잘리지 않고** 렌더된다(overflow 0 · 넘침 0).
- 안내는 메뉴 항목보다 작고 흐려 **누를 수 있는 줄로 보이지 않는다**(버튼 높이·hover 없음).
- 모델·추론 두 항목이 있던 자리가 안내로 대체됐다 — 회색 비활성 줄이 남지 않는다.
- 같은 화면 좌하단 연결 칩도 **「내 AI 업데이트 필요」**로 함께 바뀌었다.

  ⚠ **정정 (qa 적대리뷰)**: 최초 기재는 「두 표면이 같은 판정(`runner_build_is_stale`)에서
  나오므로 서로 어긋나지 않는다」였는데 **거짓**이다. 칩은 `connect_status` →
  `runner_build_is_stale`(**지문** 축), 메뉴 안내는 `get_api_vault_options` →
  `runner_caps_stale`(**기능 신고** 축)이 구동한다. 두 축은 **일부러 나눈 것**이고
  (`REPORT.md` 가 그렇게 적고 있으며 그쪽이 옳다), 따라서 **갈리는 것이 정상인 창이 있다**:
  러너 파일을 건드리는 배포 직후에는 「칩 = 업데이트 필요 · 선택기 = 정상」이 기대 상태다
  (계약을 선언한 러너의 목록은 지문이 달라도 신뢰할 수 있다). 이 Run 에서 둘이 함께 바뀐
  것은 **한 번의 동시발생**이지 공동이동의 증거가 아니다 — 단일표본 일반화였다(§16.7 G7-b).

`capsgate-trusted.png` — 자격 있는 러너에서 모델·추론 항목이 정상 복귀한 화면.

캡처: `artifacts/pb0008-capsgate/` (git 밖, §2). 검증용 DOM 복제본은 제거 확인.

## 5. 남는 한계 (정직 표기)

- 이 Run 은 **PRE-DEPLOY 격리 검증**이다. 라이브 재배포 후 POST-DEPLOY 재확인은 배포 직후
  별도 증적으로 남긴다.
- 「구 러너」는 실제 엔드포인트에 **구 러너와 동일한 본문**을 보내 재현했다. 낡은 러너 프로세스
  자체를 띄운 것은 아니다 — 서버가 보는 것은 그 본문뿐이므로 판정 경로는 동일하다.
