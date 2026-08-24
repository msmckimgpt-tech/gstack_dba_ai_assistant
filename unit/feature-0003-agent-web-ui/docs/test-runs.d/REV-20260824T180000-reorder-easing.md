---
run_at: 2026-08-24T18:15:00+09:00
session: ai/claude-corp/feature-0003-reorder-easing
scope: 재배치 전환 easing 을 easeInOutBack 으로 (사용자 요청) — CHG-20260824T180000-reorder-easing
verdict: PASS (Environment: Windows-browser)
---

# Run — PB-0008 시각검증 (Environment: Windows-browser)

- 브리지: relay @ `http://172.26.144.1:9223`, Chrome/151.0.7922.170.
- 대상: 라이브 web 이미지 + 본 worktree `src/static` 디렉터리 bind-mount 컨테이너
  (`web-verify-easing`, `https://localhost:18099`). 서빙본에 `REORDER_EASING =
  "cubic-bezier(.68,-.6,.32,1.6)"` 존재 확인.
- 계측: `tests/pb0008_sidebar_reorder_measure.py --mode folder|conv` (rAF 궤적).
  easing 검증에서 **궤적이 정본인 이유가 특히 분명하다** — 스크린샷으로는 "되돌아왔는지" 를
  볼 수 없고, offset 의 **부호 반전**만이 오버슈트의 증거다.

## A. 폴더 이름 변경 — 29px 이동 (PASS)

| 구간 | 화면 y | 목표까지 남은 offset |
|---|---|---|
| 시작(invert) | 146 | +29 |
| **back-in 최대** | **149** | **+32** (진행 방향 **반대**로 3px) |
| 통과 | 118 | +1 |
| **오버슈트 최대** | **114** | **-3** (목표를 3px 지나침) |
| 정착 | 117 | 0 |

25 프레임(178~577ms). 양끝 오버슈트 ±3px = 이동의 약 10%.

## B. 대화 제목 변경 — 176px 이동 (PASS)

8월 5일 그룹 → '오늘' 그룹.

| 구간 | 화면 y | offset |
|---|---|---|
| 시작(invert) | 318 | +176 |
| **back-in 최대** | **336** | **+194** (반대로 18px) |
| 통과 | 161 | +19 |
| **오버슈트 최대** | **124** | **-18** (목표를 18px 지나침) |
| 정착 | 142 | 0 |

27 프레임(317~748ms). 오버슈트 폭은 A 와 같은 비율(**이동 거리의 약 10%**)로 스케일한다 —
즉 짧은 이동은 은은하고 긴 이동은 탄력이 뚜렷하다. 검증 후 제목 원복 완료.

## C. 함께 확인한 것

- 오버슈트는 **모든 이동 행에 같은 곡선**으로 적용되므로 행 사이 상대 간격이 유지된다 —
  겹침·클릭 타깃 흔들림 없음(정착 후 잔류 인라인 스타일 0).
- duration 420ms 는 정리 watchdog(`REORDER_ANIM_MS + 400` = 820ms) · 강조(1100ms) ·
  예약 TTL(4000ms) 안에 들어온다(계측 창 2.2초 안에서 전 구간 관측됨).
- 하네스가 곡선 성질(y1 < 0 ∧ y2 > 1)을 계약으로 잠가, 평범한 ease-in-out 으로 조용히
  되돌아가는 회귀를 차단한다.

## D. 미수행

라이브 서빙본 재확인은 배포 후 POST-DEPLOY 로 수행한다(직전 cycle 과 동일 절차).
