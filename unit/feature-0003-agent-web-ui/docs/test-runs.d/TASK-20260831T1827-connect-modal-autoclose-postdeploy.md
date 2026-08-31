---
run_at: 2026-08-31T19:35:00+09:00
session: ai/claude-corp/feature-0003-connect-modal-autoclose-postdeploy
scope: "static/app/connect-modal.js — 연결 성립 시 토스트 + 모달 자동 닫기 (POST-DEPLOY)"
verdict: PASS
---

# Run — TASK-20260831T1827-connect-modal-autoclose (POST-DEPLOY)

- **Environment**: **Windows-browser**(PB-0008, 실 Windows Chrome 151.0.7922.170 · relay
  `http://172.26.144.1:9223` · 세션 `bootstrap_admin`)
- **Target**: 라이브 배포본 **`0fad9129`** — `/readyz` git_commit 실측 + `repo-web-a-1`·
  `repo-web-b-1` 컨테이너 `GIT_COMMIT` 직접 확인(둘 다 `0fad9129`)
- **서빙 자산**: `app.js?v=16960c2c319d` (배포 전 `241f5e208040` 에서 갱신) — 브라우저가
  **배포본 모듈**을 로드했음이 이 스탬프로 확정된다

## 1. 결과 — PRE 와 POST 를 같은 절차로 대비

같은 시나리오를 배포 전(`1c0864dc`)과 배포 후(`0fad9129`)에 동일하게 돌렸다.

| 관측 | PRE (`1c0864dc`) | POST (`0fad9129`) |
|---|---|---|
| 모달 상태 (전이 후) | `hidden: false` — **남는다** | `hidden: true` — **닫힌다** |
| 토스트 | `[]` — 없음 | `["내 AI가 연결되었습니다. 이제 질문을 보낼 수 있습니다."]` |
| 배지 | «내 AI 대기 중» | «내 AI 대기 중» |

POST 원문:

```
{"modal_hidden":true,
 "toasts":["내 AI가 연결되었습니다. 이제 질문을 보낼 수 있습니다."],
 "badge":"내 AI 대기 중",
 "toast_visible":true,
 "toast_text":"내 AI가 연결되었습니다. 이제 질문을 보낼 수 있습니다."}
```

전이 **직전** 상태도 함께 확인했다 — `{"opened":true,"toasts":0,"badge":"내 AI 연결 안 됨"}`.
창은 열려 있고 아직 아무것도 알리지 않는다(성급히 닫지 않는다).

## 2. 시각 증적

- `postdeploy-1-modal-open.png` — 미연결 상태로 열린 모달(배지 «내 AI 연결 안 됨»).
- `postdeploy-2-toast-and-closed.png` — 전이 직후: 화면 상단에 토스트 「내 AI가 연결되었습니다.
  이제 질문을 보낼 수 있습니다.」, **모달은 사라졌고**, 좌하단 배지는 «내 AI 대기 중», 입력창도
  열려 있다(컴포저 게이트 해제).

배포 전 증적(`predeploy-modal-stays-open.png`)과 나란히 보면 차이가 한 장에 담긴다 — 그때는
배지가 초록 «내 AI 대기 중» 인데 모달이 그 배지를 덮은 채 남아 있었다.

## 3. 방법과 그 한계 (정직 표기)

연결 상태 조회(`/api/ai/connect/status`) 응답만 가로채 `listening` 을 `false → true` 로 넘겼다.
검증 대상이 「서버가 그 값을 줄 때 **화면이 어떻게 반응하는가**」라는 프론트엔드 계약이기
때문이다. 배포본이 서빙하는 바로 그 모듈을 페이지와 **같은 인스턴스**로 import 해 구동했고
(자산 스탬프로 확정), 검증 후 `fetch` 원복·모달 닫기·실제 상태 재조회까지 수행해 브라우저를
원상 복구했다(`restored: true`).

**미수행**: 실 러너를 기동해 서버가 스스로 `listening:true` 를 내는 end-to-end 경로. 개인
머신에 AI CLI 설치·인증이 필요해 AI 무인 완결이 불가하다. 이 Run 은 그 축을 검증했다고
주장하지 않는다.

## 4. 배포 체크리스트 (feature-0014 RUNBOOK §10)

- [1] web-a·web-b 가 대상 SHA(`0fad9129`) + soak 통과
- [1b] 대화 경로 스모크 **PASS**
- [2] 워커 롤아웃 완료 (스파인 자동 수행)
- [2b] surge 잔존 **0**
- [3] 자산 스탬프 갱신 (`241f5e208040` → `16960c2c319d`)
- [4] 실 사용자 표면 검증 — 본 Run
- [5] **무중단 실측**: 배포 창 caddy `no upstreams available` = **0**

## 5. CI 게이트에 관한 사실 (숨기지 않음)

이 cycle 의 PR #1447 은 `mergeStateStatus=UNSTABLE` 상태로 머지됐다. **테스트가 실패한 것이
아니라 실행되지 않았다** — GitHub Actions job 이 `steps=0` 으로 2초 만에 종료됐고, 같은 현상이
이 저장소의 **전 브랜치와 main push 에** 발생하고 있다(마지막 정상 실행 2026-08-31 15:01 KST).
같은 창에서 다른 세션들의 PR 8건(#1439~#1446)도 동일 조건에서 머지됐다.

게이트의 목적(회귀 차단)은 **로컬 실행으로 대체 충족**했다 — CI 의 `test` job 이 돌리는 정적
게이트를 그대로 실행해 전건 PASS:

- AgentMemory raw SQL guard — OK
- `migrate-lint --self-test` · `--heads` — PASS (head 단일 · 번호 중복 0)
- `gen-routemap.py --check` — up-to-date (258 routes)
- `codenav-lint.sh` — OK (앵커 전부 resolve)

pytest 는 이 커밋의 **Python 변경이 0건**(JS 2 + docs 7)이라 회귀 표면이 없다.

⚠ **운영 조치 필요**: Actions 가 전면 미실행 상태다(결제·지출한도 계열로 추정 — job 이
스텝 없이 즉시 실패). 복구 전까지 모든 PR 이 CI 미검증으로 머지된다.
