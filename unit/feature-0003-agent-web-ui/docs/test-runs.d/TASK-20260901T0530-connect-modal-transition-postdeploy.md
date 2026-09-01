---
run_at: 2026-09-01T06:10:00+09:00
session: ai/claude-corp/feature-0003-transition-postdeploy
scope: "static/app/connect-modal.js — 판정 축 교체 (POST-DEPLOY)"
verdict: PASS
---

# Run — TASK-20260901T0530-connect-modal-transition (POST-DEPLOY)

- **Environment**: **Windows-browser**(PB-0008, 실 Windows Chrome 151 · relay · `bootstrap_admin`)
- **Target**: 라이브 배포본 **`17d36ad8`** · 서빙 자산 `?v=6dcb74cd1d37` · 무중단 blip **0**

## 요청 두 경로를 각각 눌러 확인했다

### A — 「연결 준비」 명령으로 재연결

창을 열 때 이미 «대기 중» 인 상태에서 시작한다(종전에 영영 닫히지 않던 조건).

```
{"열림_유지":true, "끊긴동안_유지":true, "재연결후_닫힘":true,
 "토스트":["내 AI가 연결되었습니다. 이제 질문을 보낼 수 있습니다."], "배지":"대기 중"}
```

- 열자마자 닫히지 않는다 · 명령을 실행하는 동안(끊긴 상태) 창이 남는다 · **다시 이어지면 닫힌다**.

### B — 배지가 «업데이트 필요» 인 상태에서 갱신

```
{"갱신전_배지":"업데이트 필요", "열림_유지":true, "갱신후_닫힘":true,
 "토스트":["내 AI가 최신으로 갱신되었습니다. 이제 질문을 보낼 수 있습니다."], "배지":"대기 중"}
```

- `listening` 은 줄곧 참이고 `runner_stale` 만 풀리는 경로다. 종전 축(`listening` 만)은 이
  전이를 **통째로** 놓쳤다.
- 문구가 상황을 따라간다 — «연결» 이 아니라 **«최신으로 갱신»**.

## 시각 증적

- `pd3-A-command-reconnect.png` · `pd3-B-update-refresh.png` — 각 경로의 토스트와 사라진 모달,
  좌하단 배지 «대기 중», 열린 입력창.

## 한계 (정직 표기)

연결 상태 조회와 토큰 발급 응답을 가로챘다 — 검증 대상이 「서버가 그 상태를 줄 때 **화면이
어떻게 반응하는가**」이기 때문이다. 배포본이 서빙하는 그 모듈을 페이지와 같은 인스턴스로
구동했고(자산 스탬프로 확정), 검증 후 `fetch` 원복·모달 닫기로 브라우저를 원상 복구했다
(`restored: true`).

**미수행**: 실 러너를 기동·갱신하는 end-to-end (개인 머신에 AI CLI 설치·인증 필요 — AI 무인
완결 불가). 이전 cycle 들과 같은 사유다.

## 배포 체크리스트

web·워커 `17d36ad8` · 대화 스모크 PASS · surge 잔존 0 · 자산 스탬프 갱신 · **무중단 blip 0**.
