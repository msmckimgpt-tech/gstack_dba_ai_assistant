---
run_at: 2026-09-01T04:05:00+09:00
session: ai/claude-corp/feature-0003-launch-close-postdeploy
scope: "static/app/connect-modal.js — 실행 성공 시 창 닫기 회귀 정정 (POST-DEPLOY)"
verdict: PASS
---

# Run — TASK-20260901T0330-connect-modal-launch-close (POST-DEPLOY)

- **Environment**: **Windows-browser**(PB-0008, 실 Windows Chrome 151 · relay · `bootstrap_admin`)
- **Target**: 라이브 배포본 **`ead6e30f`** (`/readyz` 실측) · 서빙 자산 `?v=caa9885f1a64`
- **무중단**: 배포 창 caddy `no upstreams available` = **0**

## 1. 제보 경로를 그대로 눌렀다

제보 상황을 재현했다 — 화면이 **이미 «내 AI 대기 중»** 인 상태(기준선 true)에서 모달을 열고,
「연결 준비」로 명령을 발급한 뒤 **`[내 AI 실행]` 버튼을 실제로 클릭**했다. 스킴은 미등록
검증용 값으로 두어 실 러너를 띄우지 않았다(대기 루프의 판정 경로는 그대로 탄다).

| 단계 | 관측 |
|---|---|
| 모달 열기 | `opened:true` · 배지 «내 AI 대기 중» · 토스트 0 — **열자마자 닫히지 않는다** |
| 「연결 준비」 | 명령 발급 · 실행 버튼 노출 · 창 유지 |
| **`[내 AI 실행]` 클릭** | **`modal_hidden:true`** · 토스트 「내 AI가 연결되었습니다. 이제 질문을 보낼 수 있습니다.」 |

배포 전(`main` = 제보 상태)에서는 같은 절차에서 창이 남고 「내 AI가 **대기 중입니다**」 문구만
떴다 — 그것이 사용자가 받은 화면이다. 이제 성공 통로가 하나로 합쳐져 **그 문구 자체가 나오지
않는다**.

## 2. 시각 증적

- `pd2-1-before-launch.png` — 실행 직전(명령 발급 완료, 창 열림).
- `pd2-2-after-launch.png` — 실행 직후: 상단에 토스트, **모달 사라짐**, 좌하단 «내 AI 대기 중»,
  입력창 열림.

## 3. 한계 (정직 표기)

연결 상태 조회와 토큰 발급 응답을 가로챘다 — 검증 대상이 「이미 대기 중으로 알려진 상태에서
사용자가 실행을 눌렀을 때 **화면이 어떻게 반응하는가**」이기 때문이다. 배포본이 서빙하는 그
모듈을 페이지와 같은 인스턴스로 구동했고(자산 스탬프로 확정), 검증 후 `fetch` 원복·모달
닫기까지 수행해 브라우저를 원상 복구했다(`restored: true`).

**미수행**: 실 러너 기동 end-to-end (직전 cycle 과 동일 사유 — AI 무인 완결 불가).

## 4. CI

여전히 전면 미실행(job `steps=0`). CI 정적 게이트 4종을 로컬에서 PASS 확인 후 머지했고, 이
cycle 의 Python 변경도 0건이다. 운영 조치 필요 상태는 변동 없다.
