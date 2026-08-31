---
run_at: 2026-08-31T18:30:00+09:00
session: ai/claude-corp/feature-0003-connect-modal-autoclose
scope: "static/app/connect-modal.js — 연결 성립 시 토스트 + 모달 자동 닫기"
verdict: PASS
---

# Run — TASK-20260831T1827-connect-modal-autoclose

- **Environment**: **Windows-browser**(PB-0008, 실 Windows Chrome 151.0.7922.170 · relay
  `http://172.26.144.1:9223` · 세션 `bootstrap_admin`) + 순수 node 행위 테스트
- **Target(사전)**: 라이브 배포본 **`1c0864dc`** (`/readyz` git_commit 실측)

## 1. PRE-DEPLOY — 라이브 배포본에서 결함 재현 (Windows-browser)

배포본이 서빙하는 **바로 그 모듈**(`/static/app/connect-modal.js?v=58a4b4882798`)을 화면에서
동적 import 해, 페이지가 쓰는 동일 인스턴스로 상태 전이를 만들었다. 연결 상태 조회
(`/api/ai/connect/status`)만 가로채 `listening` 을 `false → true` 로 넘겼다.

```
{"baseline_commit":"1c0864dc",
 "modal_hidden_after_open":false,
 "modal_hidden_after_listening":false,   ← 연결이 성립해도 창이 남는다
 "badge":"내 AI 대기 중",                 ← 화면은 연결을 인지했다
 "toasts":[]}                             ← 알림 0
```

스크린샷으로도 같은 상태가 확인된다 — 좌하단 배지가 초록 «내 AI 대기 중» 인데 「내 AI
연결하기」 모달이 화면 중앙에 그대로 떠 있고, 그 모달이 바로 그 배지를 덮고 있다. 사용자가
겪은 마찰이 이 한 장이다: **다 됐는데 그 사실이 이 창 뒤에 있다.**

- 검증 후 `fetch` 원복 · 모달 닫기 · 실제 상태 재조회까지 수행해 브라우저를 원상 복구했다
  (`fetch_restored:true` · `modal_hidden:true` · 실제 배지 «내 AI 연결 안 됨»).

### 이 축의 한계 (정직 표기)

연결 상태 조회 응답을 **위조**했다 — 검증 대상이 「서버가 `listening:true` 를 줄 때 화면이
어떻게 반응하는가」라는 프론트엔드 계약이기 때문이다. 실 러너를 기동해 서버가 스스로
`listening:true` 를 내는 end-to-end 경로는 **미수행**이며(AI 무인 완결 불가 — 개인 머신에 AI
CLI 설치·인증이 필요), 이 Run 은 그 축을 검증했다고 주장하지 않는다. 서버가 그 필드를 내는
계약 자체는 이 변경 이전부터 같은 코드가 소비하던 것이라 이번 변경의 위험 표면이 아니다.

## 2. 행위 테스트 (순수 node, jsdom 비의존)

`tests/verify_connect_modal_autoclose.mjs` — 실제 모듈을 최소 DOM shim 위에서 구동. **25/0 PASS**.
리스너를 저장·디스패치하므로 `[내 AI 실행]` 버튼 경로도 우회 없이 탄다.

| 시나리오 | 기대 | 결과 |
|---|---|---|
| A 미연결로 열어 둔 창에 러너가 붙음 | 토스트 1 + 창 닫힘 | PASS (A1~A5) |
| B 이미 연결된 사용자가 열기 | 닫히지 않음 (거짓 성공 방지) | PASS (B1·B2) |
| C 토큰만 발급(`listening:false`) | 닫히지 않음 (명령 보존) | PASS (C1·C2) |
| D 성립 후 추가 관측 | 토스트 중복 없음 | PASS (D1) |
| E import 경로 실재 · 폴링 정지 · 닫기 막힘 | 배선·자원이 새지 않음 | PASS (E1~E3) |
| F 실행 버튼 경합 3종 | 남의 러너·이전 창·in-flight 응답으로 안 닫힘 | PASS (F1~F3) |
| G 첫 조회 실패 후 전이 | 알림을 놓치지 않음 | PASS (G1) |

### G11-b 결함 주입 실증 (§16.7)

같은 테스트를 **수정 전 코드**(`git show main:…/connect-modal.js`)에 태웠다:

```
FAIL  A3 토스트 1건
FAIL  A4 문구가 «연결» 을 말한다
FAIL  A5 창이 닫힌다
FAIL  D1 토스트는 여전히 1건
FAIL  E2a 열면 폴링이 돈다
FAIL  E3 닫기가 막혀도 알림은 1회
FAIL  G1 첫 조회가 실패해도 전이를 놓치지 않는다
결과: 14 passed, 7 failed
```

통과만 확인한 단언이 아니다 — 이 테스트는 실제로 이 결함을 잡는다. B·C(닫히면 안 될 때
안 닫힌다)가 수정 전에도 PASS 인 것은 정상이다: 그 축은 이번 변경이 **깨뜨리지 않아야 할**
성질이고, 그래서 회귀 잠금으로서 의미가 있다.

### 뮤테이션 역검증 — 방어 계층을 가른다

codex 2R 이 「막힌다를 확정할 수 없다」고 했다. 논증 대신 각 방어를 지워 보고 무엇이 죽는지 봤다:

| 뮤턴트 | 결과 |
|---|---|
| 응답 epoch 검사만 제거 | 25/0 통과 — `_connSeq` 최신성 검사가 막는다 |
| `_connSeq` 검사만 제거 | 25/0 통과 — epoch 검사가 막는다 |
| **둘 다 제거** | **F3a·F3b·F3c FAIL — 경합이 실제로 재현된다** |

경합은 실재하고, 현재 코드는 이중으로 막으며, F3 는 그 중복이 필요한 지점을 정확히 겨눈다.
나머지 6종도 각각 자기 단언을 죽인다: loop-epoch→F2a·F2b / launchrunner-announces→F1c·F1d·F1e /
baseline-first-obs→G1 / announced-guard→E3 / clearinterval→E2b·F2a·F2b.

## 2.5 codex 적대 리뷰 3라운드 (§18.8.1 경량 경로 · 수렴 계약)

1R **BLOCK**(P1 2 · P2 4) → 2R **승인 불가**(P1-1 잔존 + 새 P2 1) → 3R **P1 0**.
두 P1 은 뿌리가 같았다 — **닫기 판정이 두 곳에 있었고**, 한쪽은 «이 창의 전이» 라는 기준선을
몰랐다. 상세는 `docs/REVIEW.md` 의 `REV-20260831T182700-…-connect-modal-autoclose`.

## 2.9 미검증으로 남긴 것 (정직 표기)

- **`_gateInFlight` 해제 전용 단언 없음** (codex 3R 잔여 P2). 폴링 간격 5초를 테스트에서
  발화시킬 수단이 없어서다. 코드 방어(`_raceTimeout` 상한)는 넣었으나 그 방어를 겨누는 단언은
  없다.
- **`ux`/`design` 도메인 심사 미수행** — 세션의 상위 우선순위 도구 제약으로 subagent panel 을
  호출할 수 없다(§18.8.2 carve-out). `[SKIPPED:tool-restricted:ux-design]` 로 명시했다.

## 3. POST-DEPLOY

배포 후 같은 PB-0008 경로로 재실측 — `TASK-20260831T1827-connect-modal-autoclose-postdeploy.md`.
