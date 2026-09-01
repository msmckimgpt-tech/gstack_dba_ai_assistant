---
run_at: 2026-09-01T14:05:00+09:00
session: ai/claude/feature-0043-caps-trust-gate
scope: 적대 패널 조치 후 재검증 — 다운로드 링크 배선 · ARIA role · 안내 극성 (머지 후 빌드)
verdict: PASS (부분 — 아래 §4 한계 명시)
---

# Run — TASK-20260901T140000-caps-trust-gate-ui-r2 (PRE-DEPLOY 라이브)

- Date: 2026-09-01
- Environment: **Windows-browser** (PB-0008, `bin/win-browser.py` + 실 Windows Chrome 151)
- Target: 격리 컨테이너 `web-verify-capsgate2` — 라이브 이미지 `mysql-ai-web:786815f2`
  + 브랜치 static(stamp **`5c5c2da471d6`**) + 변경 서버 5종 bind-mount, `https://localhost:18091`
- 라이브 web-a/b·caddy·공유 트리 **무접촉**. 다른 세션의 컨테이너도 **무접촉**.
- Result: **PASS** (상태 (a) 실화면 · (b)(c) 는 §4 참조)

## 1. 정체 대조를 먼저 한다 — 이번에 두 번 걸렸다

§16.6 「evidence 의 identity 대조」가 이 Run 에서 **두 번** 작동했다. 둘 다 관측을 남의
것으로 읽을 뻔한 사례라 그대로 적는다.

| # | 무슨 일 | 어떻게 갈라냈나 |
|---|---|---|
| 1 | 포트 18095 로 컨테이너를 띄우려 했는데 **다른 세션의 `web-verify-sr`** 이 이미 그 포트를 잡고 있었다. `docker run` 은 실패했는데 `curl https://localhost:18095/healthz` 는 **200** 이었다 — 남의 컨테이너가 답한 것이다. | `docker ps --format '{{.Ports}}'` 로 그 포트의 실제 주인을 조회. 빈 포트(18091)를 `ss -tln` 으로 확인 후 재기동 |
| 2 | 중간에 브라우저 탭이 **`https://localhost:18099/admin`**(또 다른 세션의 컨테이너)으로 옮겨가 있었고, 거기서 받은 응답을 내 빌드의 것으로 읽을 뻔했다 | 매 관측에 `location.href` + asset stamp 를 함께 실어 대조. stamp 가 `?v=dev`(미주입) 였고 `runner_mixed` 키가 없어 즉시 갈렸다 |

⚠ **원인은 공유 브라우저다.** `win-browser.py` 는 단일 CDP 엔드포인트에 attach 하고, 지금
이 머신에서 **여러 세션이 동시에 그것을 쓰고 있다**(`web-verify-sr`·`-sidebar`·`-dnd`·
`-kbreach` 등 타 세션 컨테이너 5개 관측). §16.6 (a)(b)(MUST) 가 요구하는 「자기 세션이 만든
표면에서만」이 이 도구로는 보장되지 않는다 — 본 Run 은 (c) 「evidence 의 identity 대조」로
버텼다. 이 제약 자체는 본 cycle 의 범위 밖이므로 **고치지 않고 기록**한다.

## 2. 상태 (a) — 계약 미선언 러너 (라이브 실재)

이 계정(`bootstrap_admin`)에는 **다른 세션의 러너 2대**가 붙어 있었고 둘 다
`console_jobs,self_review` 만 신고했다(= `caps_self_report` 미선언). 즉 상태 (a) 를 내가
만들 필요가 없었다 — 라이브에 이미 있었다.

서버 응답 (stamp `5c5c2da471d6`, `loc=https://localhost:18091/`):

```
model_selector = "hidden" · runner_caps_stale = true · runner_mixed = false
reason = "연결된 러너가 오래된 버전이라 모델 목록을 신뢰할 수 없습니다 — 최신 실행 파일로 다시 실행해 주세요."
```

컴포저 `+` 메뉴 DOM:

| 관측 | 값 |
|---|---|
| 안내 텍스트 | 「…다시 실행해 주세요. **실행 파일 받기**」 |
| 실제 렌더 | `offsetParent !== null` = **true** |
| **링크 href** | `/static/agent/bridge_agent.py` ← *소비처 0 이던 필드가 화면에 도달* |
| 링크 텍스트 / `download` | `실행 파일 받기` / `bridge_agent.py` |
| `role` | **`presentation`** (종전 `note` 는 `role=menu` 에 무효였다) |
| `aria-live` | **`polite`** |
| 모델 항목 hidden | **true** |

적대리뷰 C2(링크 미배선)·ARIA(무효 role) 두 지적이 **실화면에서** 해소됐음을 확인한다.

## 3. jsdom 동작 하네스 (CI 밖, 로컬)

```
$ node unit/feature-0003-agent-web-ui/tests/verify_selector_note.mjs
  10 passed, 0 failed
```

이 하네스가 qa 가 생존시킨 뮤턴트를 실제로 죽인다(§16.7 G11-b):

| 뮤턴트 | 결과 |
|---|---|
| M3 안내 삼항 극성 반전 | 3 passed, **6 failed** |
| M8 `toggle("hidden", false)` (빈 행 잔존) | 9 passed, **1 failed** |
| M-C2 링크 배선 제거 | 8 passed, **1 failed** |

⚠ **M8 은 처음에 생존했다**(9/9). 하네스가 「숨김 + 사유가 빈 카탈로그」 경계를 건드리지
않았기 때문이다 — 뮤턴트가 살아남은 자리가 곧 빠진 케이스였고, 그것을 추가해 10 케이스가
됐다. 생존 기록을 남기지 않았다면 이 구멍은 그대로 남았다.

## 4. 하지 못한 것 (정직 표기)

**상태 (b) 혼재 · (c) 자격 있는 러너는 이 Run 에서 실화면으로 재확인하지 못했다.**

- 이 계정에 **다른 세션의 러너 2대**가 살아 있어, (b)(c) 를 만들려면 그 계정의 러너 구성을
  바꿔야 한다. §16.6 (d)(자원-출처 격리)상 남의 검증 상태를 흔들 수 없다.
- 실제로 시도 중 하트비트 1건이 **다른 세션 컨테이너로 나갔고**(위 §1 #2), 그때 생성된
  토큰 행 `Id=95` 는 즉시 revoke 했다(`RevokedAt=2026-09-01 05:56:43` 실측). 타 세션의
  행 `93`·`94` 는 **건드리지 않았다**.
- 두 상태의 커버리지: 서버 판정은 `test_mixed_runners_fail_closed_and_say_which_action` ·
  `test_trusted_runner_is_unaffected`(pytest, fake cursor 2행)가, 렌더는 위 jsdom 하네스
  케이스 5·1 이 잡는다. (c) 의 실화면은 **Run 1**(stamp `0df767209532`)에서 캡처됐고 그
  코드경로는 이번 라운드에서 바뀌지 않았다.

이 항목들을 「검증함」으로 적지 않는다 — 덮인 축과 덮이지 않은 축을 분리해 둔다.

## 5. 잔류물

- 검증 컨테이너 `web-verify-capsgate2` · 스탬프 트리 `/var/tmp/capsgate2` **제거 완료**.
- 내가 만든 토큰 `Id=95` **revoke 완료**. 타 세션 자원 무접촉.
- 포트 18091 반납.
