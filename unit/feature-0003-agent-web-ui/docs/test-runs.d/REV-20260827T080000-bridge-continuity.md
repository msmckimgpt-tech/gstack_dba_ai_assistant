---
run_at: 2026-08-27T17:00:00+09:00
session: ai/claude/feature-0045-zd-bridge-continuity
scope: 브리지 배포 연속성 (feature-0045) — web 자산 변경분
verdict: 미수행 (해당 없음) — 이 cycle 의 web 자산 변경에 **화면 요소가 없다**
---

# Run — 브리지 배포 연속성

Environment: **Windows-browser 미수행** (사유: 아래)

## 왜 시각검증을 하지 않았나

이 cycle 이 `unit/feature-0003-agent-web-ui/src/` 아래에서 바꾼 것은 셋이다:

| 파일 | 무엇 | 화면에 그려지나 |
|---|---|---|
| `bridge_drain.py` (신규) | in-flight 카운터 + 드레인 미들웨어 | 아니오 — 서버 내부 |
| `routers/system.py` | `/livez`·`/readyz`·`/internal/*` 3종 | 아니오 — 배포 스파인 전용 창구 |
| `static/agent/bridge_agent.py` | 개인 머신에서 **내려받아 실행**하는 러너 | 아니오 — 브라우저가 실행하지 않는다 |

`static/` 아래이지만 마지막 것은 HTML·CSS·JS 자산이 아니라 **`Content-Type: text/plain` 으로
내려가는 파이썬 파일**이다(`/ai/connect` 안내가 `curl` 로 받게 한다). 브라우저는 이것을
파싱하지도 실행하지도 않으므로, 실 Windows 브라우저로 열어 볼 화면이 존재하지 않는다.

게이트(`verify-completion` check #13)는 경로가 `static/` 아래인 것만 보고 이 구분을 하지
못한다 — 그래서 여기에 사유를 남긴다. 대상 화면이 없어서 미수행이지, 브리지 setup 이 안 돼서
건너뛴 것이 아니다.

## 대신 검증한 것

이 cycle 의 사용자 대면 효과는 **배포 중에 대화가 끊기지 않는 것**이고, 그 판정은 화면
스냅샷이 아니라 배포 로그와 계약 테스트에 있다.

- 계약 테스트 60건 (`unit/feature-0045-zd-bridge-continuity/tests/`) — 드레인 상태기계·
  게이트 실행·토폴로지·내부 창구
- 컨테이너 `make test` 전량 PASS (route golden 갱신 포함)
- 라이브 판정은 배포 시점의 `bridge_continuity_summary` — "대기는 드레인으로 교대했고 진행
  중 왕복은 완주했다(끊김 0)" 가 나와야 한다. 강행이 있었으면 그 사실이 대신 출력된다.

## 화면 쪽 잔여 (이 cycle 범위 밖)

말풍선의 상태 전이(대기 → 처리 중 → 답변)는 feature-0043 의 기존 배선이 담당하며 이 cycle 은
건드리지 않았다. 그쪽 PB-0008 은 feature-0043 의 잔여 항목으로 남아 있다.
