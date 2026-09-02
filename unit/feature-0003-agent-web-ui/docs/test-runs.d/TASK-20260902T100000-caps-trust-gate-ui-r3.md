---
run_at: 2026-09-02T11:00:00+09:00
session: ai/claude/feature-0043-caps-trust-gate
scope: 재설계(§18.8 (b)) 후 PB-0008 재검증 — provenance 필터 · 사유·링크 · ARIA 자리
verdict: PASS (상태 (a)(b) 실화면 / 상태 (c) 는 §4 참조)
---

# Run — TASK-20260902T100000-caps-trust-gate-ui-r3 (PRE-DEPLOY 라이브)

- Date: 2026-09-02
- Environment: **Windows-browser** (PB-0008, `bin/win-browser.py` + 실 Windows Chrome 151)
- Target: 격리 컨테이너 `web-verify-capsgate3` — 라이브 이미지(`repo-web-a-1` 의 이미지)
  + 브랜치 static(asset stamp **`1f703ee2a0f2`**) + 변경 서버 6종 bind-mount, `https://localhost:18092`
- 브랜치 HEAD: `d5378cd41c56`
- 라이브 web-a/b·caddy·공유 트리 **무접촉**. 다른 세션의 컨테이너도 **무접촉**.

## 1. 하네스 자체의 결함을 먼저 잡았다 — 「내 검증 도구가 거짓 화면을 만들었다」

첫 시도에서 컴포저 `+` 메뉴가 **열리지 않았다**. 내 변경(안내 `<p>` 1개 추가)으로는 설명되지
않아 **대조군**을 세웠다 — 같은 라이브 이미지를 bind-mount 없이 띄운 `web-verify-capsbase`
(`https://localhost:18093`). 거기서는 `menuOpen=true` 였다. 즉 내 컨테이너만 깨져 있었다.

원인은 **내 static 준비 절차**였다. 배포 파이프라인은 Dockerfile 에서
`scripts/inject_asset_stamp.py` 로 **HTML·JS 전체**의 `?v=dev` 를 콘텐츠 해시로 치환하는데,
나는 `sed` 로 **HTML 만** 바꿨다. 그러면 `index.html` 은 `app.js?v=<stamp>` 를 부르고
`app.js` 안의 import 는 `app/…?v=dev` 를 불러 **`app.js` 가 두 번 평가된다**(브라우저는 쿼리가
다르면 다른 모듈로 본다). 두 인스턴스가 같은 DOM 을 두고 다투면서 `+` 핸들러가 죽었다.

```
performance.getEntriesByType('resource') 중 app.js  → 2건 (?v=<stamp> · ?v=dev)   ← 깨진 판본
                                                   → 1건                          ← 실제 주입기 사용 후
```

**교훈**: 검증용 산출물은 **배포와 같은 도구로** 만든다. 「비슷하게」 만든 트리는 제품이 아니라
하네스를 시험한다. 이 결함은 대조군 없이는 「내 변경이 메뉴를 깨뜨렸다」로 오독됐을 것이다.
(고친 뒤 `dup=1`, 메뉴 정상.)

## 2. 상태 (a) — 최신 러너(출처 `probe`) + 내장 표 런타임 혼재

내 러너 신고: `claude`(`source: probe`, opus·sonnet) + `codex`(`source: builtin`, gpt-5.1-codex).

| 관측 | 값 |
|---|---|
| `location.href` / asset stamp | `https://localhost:18092/` / **`1f703ee2a0f2`** |
| `app.js` 로드 수 | **1** (하네스 결함 해소 확인) |
| 메뉴 열림 · 모델 항목 · 추론 항목 | `true` / `true` / `true` |
| 모델 메뉴 텍스트 | **`Claude Opus ✓ Sonnet`** |
| `gpt-5.1` 포함 | **`false`** ← 제보된 증상이 바로 이것이다 |
| 안내 `<p>` | 텍스트 `""` · `hidden` · 링크 없음 (보이는 상태에서는 **비운다**) |
| 안내가 `role=menu` 안인가 | **`false`** (ARIA 자기무효화 해소) · `aria-live=polite` |

**우아한 열화가 실화면에서 성립한다** — 나쁜 런타임(codex/builtin) 하나만 떨어지고 claude 는
그대로 보인다. 전역 게이트였다면 계정의 목록이 통째로 사라졌을 자리다.

## 3. 상태 (b) — 러너는 듣는데 쓸 수 있는 목록이 없다 (구 러너)

| 관측 | 값 |
|---|---|
| 안내 텍스트 | 「연결된 러너가 알려준 모델이 없습니다 — 최신 실행 파일로 다시 실행해 보세요. **실행 파일 받기**」 |
| 실제 렌더 | `offsetParent !== null` = **true** |
| 링크 `href` / 텍스트 | `/static/agent/bridge_agent.py` / `실행 파일 받기` |
| 모델 항목 표시 | **`false`** (숨김) |
| 안내가 `role=menu` 안인가 | **`false`** |
| 스크린샷 | `/tmp/win-browser-shots/capsgate3/B1_old_runner.png` — 메뉴에는 「파일 첨부 · 첨부파일 목록」만 남고, 안내와 링크는 **메뉴 밖 컴포저 행에** 렌더 |

⚠ 이 상태는 **서버 응답 자체로도** 먼저 확인했다(브라우저 이전, 같은 컨테이너):
`model_selector=hidden · runner_listening=true · models=[] · reason=「…다시 실행해 보세요.」`.
구 러너 흉내(`source` 미신고 + `gpt-5.1-codex`) 신고가 **수신 시점에** 통째로 걸러진 결과다.

## 4. 하지 못한 것 (정직 표기)

**상태 (c)(러너 없음)의 실화면은 이 Run 에서 재확인하지 못했다.**

- 이 배포의 `bootstrap_admin` 계정에는 **사용자의 실 러너**(토큰 `Id=117`, 지문
  `937b18be70eb`)가 상시 하트비트 중이다. 계정당 정본은 「가장 최근 하트비트」이므로 (c) 를
  만들려면 그 러너를 밀어내야 하고, 그러면 **사용자의 라이브 화면이 흔들린다**(§16.6 (d)).
- 검증 중 내가 만든 러너 행(`Id=113`, 지문 `deadbeefcafe`)은 대조를 마친 직후 **즉시 revoke**
  했다. 사용자 행 `117`·타 계정 행 `112`/`114` 는 **건드리지 않았다**.
- (b)/(c) 렌더를 실 모듈로 구동하기 위해 페이지 안에서 `window.fetch` 를 감싸 카탈로그 응답만
  바꿨다 — 렌더 코드·DOM·CSS 는 전부 실물이다. (c) 는 그 경로에서 카탈로그 재적재를 깨우는
  게이트 전이가 대기창 안에 오지 않아 반영되지 않았다(하네스 타이밍, 제품 문제 아님).
- (c) 의 커버리지: 서버 판정은 실측(`runner_listening=false` + 전용 문구, 위 §3 이전 단계에서
  기록) · 렌더는 jsdom 하네스 케이스 4·5·6(다운로드 링크 **없음** · 「다시 실행」 지시 없음 ·
  카탈로그 부재도 말을 한다)와 pytest 가 잡는다.

이 항목을 「검증함」으로 적지 않는다 — 덮인 축과 덮이지 않은 축을 분리해 둔다.

## 5. jsdom 동작 하네스 (CI 밖, 호스트 실행)

```
$ node unit/feature-0003-agent-web-ui/tests/verify_selector_note.mjs
  10 passed, 0 failed
```

실행 환경은 **호스트**다(WSL `node v18.19.1` + `jsdom@22`, `npm i jsdom@22 --prefix /tmp`).
테스트 컨테이너에는 node 가 없어 `make test` 는 이 파일을 실행하지 않는다.

뮤턴트 재측정(전건, 위 실행 환경):

| 뮤턴트 | 결과 |
|---|---|
| M3 `if (!hidden)` → `if (hidden)` (극성 반전) | 5 passed, **5 failed** |
| M8 `toggle("hidden", !reason)` → `…, false` | 9 passed, **1 failed** |
| M-C2 링크 조건을 `if (false)` 로 | 9 passed, **1 failed** |
| (기준선 / 복원) | 10 passed, 0 failed |

⚠ 앞선 Run(r2)의 표는 **합이 케이스 수와 맞지 않았다**(3+6=9, 8+1=9). 정정 근거와 함께
`TASK-20260901T140000-caps-trust-gate-ui-r2.md` §6.1 에 남겼다.

## 6. 잔류물

- 검증 컨테이너 `web-verify-capsgate3` · 대조군 `web-verify-capsbase` · 스탬프 트리
  `/var/tmp/capsgate3` **제거 완료**. 포트 18092·18093 반납.
- 내가 만든 러너 행 `Id=113` **revoke 완료**. 타 세션·타 계정 자원 무접촉.

---

## 7. 후속 델타 — codex 확인 라운드 조치 (2026-09-02T11:30 KST)

- Environment: **Windows-browser** (PB-0008) — 위 §2·§3 의 Run 과 **같은 빌드·같은 컨테이너**에서
  얻은 관측이 그대로 유효한 범위와, 그 뒤 바뀐 한 줄을 여기서 가른다.

codex 적대리뷰 조치로 프런트에서 바뀐 것은 **한 곳**이다:

```js
// _composerModelSelectorHidden()
if (!catalog) return true;     // 신규 — 카탈로그 부재를 «숨김» 으로 읽는다
```

| 축 | 이 변경의 영향 | 재검증 |
|---|---|---|
| 상태 (a) 최신 러너 · 상태 (b) 구 러너 | **없음** — 두 상태 모두 카탈로그가 있다(`model_selector` 가 `visible`/`hidden` 로 명시된다). 위 §2·§3 의 실화면 관측이 그대로 유효 | 재실행 불요 |
| **카탈로그 부재**(`/api/api-vault/options` 실패) | 종전: 선택기가 **보인 채** 서버 기본값 라벨을 표시하고 안내는 지워짐 → 변경: 선택기 숨김 + 「모델 목록을 불러오지 못했습니다」 | jsdom 하네스가 **진입점**(`_applyComposerSelectorVisibility`)을 통과해 검증 — 11 케이스 전건 PASS. 가드를 제거한 뮤턴트는 KILLED |

이 축의 실화면 재현은 **하지 않았다**: 네트워크 실패를 실 브라우저에서 만들려면 서버를
내리거나 요청을 가로채야 하는데, 앞의 (b)/(c) 구동에서 쓴 `fetch` 감싸기는 이 경로에서
「응답이 오지 않는다」를 흉내 낼 뿐 실제 실패 조건(타임아웃·5xx)과 같지 않다. 대신 진입점을
통과하는 하네스로 덮고, 그 사실을 여기 적는다 — 「검증함」으로 적지 않는다.

서버 축 2건(지문 컬럼 없는 배포에서의 신고 강등 · 하트비트 없던 토큰의 tri-state)은 화면
자산이 아니며 pytest 로 덮인다(뮤턴트 실증 포함).
