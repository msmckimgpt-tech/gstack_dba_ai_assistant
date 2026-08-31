---
run_at: 2026-08-31T16:50:00+09:00
session: ai/claude/feature-0043-setup-speed-logts
scope: "static/agent/{bridge_setup.sh,bridge_agent.py} — 등록 80초→0.7초 + 로그 시각"
verdict: PASS
---

# Run — TASK-20260831T164500-setup-speed-logts (feature-0003 소유 파일분)

- **Environment**: **Windows-browser 미수행 — 사유 명시** + Windows 왕복 실측
- **대상**: `static/agent/bridge_setup.sh` · `static/agent/bridge_agent.py` (둘 다 서빙 사본)

## 왜 시각검증이 아닌가 (사유)

이번 cycle 이 바꾼 웹 자산은 **브라우저가 렌더하지 않는 두 파일**뿐이다 — 사용자가 내려받아
터미널에서 실행하는 셸 스크립트와 파이썬 러너다. HTML·CSS·JS 표면 변경 0. 화면에 대조할
픽셀이 없으므로 PB-0008 은 이 변경에 대해 검증력이 없다(§16.6 「변경-클래스 분기」 — 이
클래스는 존재·동작·성능 축이다). 대신 그 파일이 실제로 하는 일을 Windows 왕복으로 실측했다.

## 성능 실측 (실 Windows + WSL Ubuntu)

| 단계 | 개선 전 | 개선 후 |
|---|---|---|
| 핸들러 등록 전체 | **80.27초** | **0.73초** |
| `powershell -File` (WSL UNC 경로) | 80.27초 | — (경로 자체를 안 씀) |
| `powershell -File` (Windows 로컬 경로) | — | 0.41초 |
| Windows exe 기동 횟수 | 3회 | **1회** |

부하 시 exe 기동 자체가 3.0~3.4초임을 함께 실측했다(한가할 땐 0.04~0.4초) — 그래서 호출
**횟수**를 줄이는 것이 유효한 축이었다.

등록 결과도 확인: 값이 정확하고(`"…wsl.exe" -d Ubuntu -u claude-corp -- "…/launch.sh" "%1"`),
`%TEMP%` 의 임시 PS1 잔재 0건.

## 로그 시각

실제로 출력시켜 확인했다.

```
[bridge-setup 2026-08-31 16:44:49] 러너 체크섬 일치.
[bridge 2026-08-31 16:44:49] AI = claude
```

## 자동 스위트

`test_wsl_scheme_handler.py` **23건 PASS**. 신규 3건(L14 로컬 경로 · L15 기동 1회 · L16 시각)은
**수정 전 스크립트에서 3/3 FAIL** 함을 실증했다 (§16.7 G11-b).

정본 기록: `unit/feature-0043-external-llm-bridge/docs/MODIFY.md` CHG-20260831T164500-…
