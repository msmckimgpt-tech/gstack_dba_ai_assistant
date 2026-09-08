---
run_at: 2026-09-08T20:50:00+09:00
session: claude ai/claude/feature-0003-step-narration-seal
scope: 실행 단계 문구 — 남은 노출 경로 폐쇄 + 조치 봉인
verdict: PASS
---

# Run — TASK-20260908T204500-step-narration-seal

## Run — DQA 클라이언트 실측 (PB-0009)

Environment: DQA-client
Result: NOT-RUN
Scenario: 실행 단계 패널에서 ① 파생 근거가 「근거(추정)」로 구분 표기되는지 ② 배지가 붙은
행에서 폴백 제목이 되풀이되지 않는지 확인
Build: 미배포(본 cycle) · 앞 cycle 배포본 web-a/b `3658deee`
Reason: 실행 중인 DQA 앱의 WebView2 에 `--remote-debugging-port` 가 없어 앱 DOM 조작 경로가
없다(앞 cycle 에서 `Win32Process.CommandLine`·`NETSTAT`·`/json/version` 405 로 실측). PB-0009
3번 항목대로 포트를 추정하거나 사용자가 쓰고 있는 앱을 종료·재실행하지 않는다.
Alternative: 아래 「조치 봉인 실증」이 배포되는 `app.js` 의 실제 함수와 서버 산출을 실행해
두 항목의 배선을 확인한다(뮤턴트 M6·M8 이 각각 그 두 축을 잠근다). 라벨·색 구분의 실제 렌더는
이 Run 의 범위이며 대신 주장하지 않는다.
Next: 배포 후 사람 관찰 + 캡처로 확인한다.

## Run — 조치 봉인 실증 (뮤턴트 주입)

Environment: CLI
Result: PASS
Scenario: 이 cycle 과 앞 cycle 이 고친 각 조치를 **되돌리는 뮤턴트**를 제품 코드에 주입해,
대응 테스트가 실제로 붉어지는지 확인한다 (§16.7 G11-b)
Evidence: 8종 전건 **KILLED** — M1 사유축 배선 뒤집기 · M2 서버 규칙(a) 앵커 제거 ·
M3 scratch_sql 조회로 회귀 · M4 scratch_reset 「임시 삭제」 회귀 · M5 list_schemas 제목 회귀 ·
M6 파생 근거 구분 제거 · M7 `/api/ask` 이음매 우회 · M8 사이드 패널 폴백 억제 제거.
각 뮤턴트마다 대응 테스트 이름이 실패 목록에 나타남을 확인했고, 주입 파일은 전부 원복해
기준선(66건 PASS)으로 되돌아옴을 재실행으로 확인했다.
Limit: 뮤턴트는 «되돌리기» 형태다 — 다른 형태의 회귀까지 덮는다고 주장하지 않는다.

## Run — 단위·정적 검증

Environment: CLI
Result: PASS
Scenario: 신규·기존 시험 + ruff
Evidence: `test_step_tool_syntax_leak.py` **66건 PASS**(L1~L9). 행위 하네스 **17항목 PASS**.
전체 집합 **8,397건 / 실패 2 / errors 0**. 그 2건(`test_route_parity_p5b` 골든 스냅샷 ·
`test_bridge_interrupt_stream` 명시 도구 라우트 수)은 **pristine `origin/main`(1c57360b)에서도
동일하게 실패**함을 확인했다 — 다른 세션이 라우트를 추가하며 골든·개수 단언을 갱신하지 않은
선재 결함이고 본 cycle 대비 **차집합 0**이다. ruff clean.

## 미검증·한계

- **DQA 클라이언트 화면 실측**은 여전히 NOT-RUN(앱 WebView2 디버깅 포트 부재) — 앞 cycle 과
  같은 사유이며 이 cycle 도 그 축을 닫지 못한다.
- `agent_core.py` 의 `intent` 도구명 접두는 **남겨 두었다** — 표시 경로가 전부 이음매를 통과해
  클라이언트로 나가지 않으므로 원장 컬럼 문제로 격하했고, feature-0002 소유라 별도 cycle 이 맞다.
- `_LABEL_BUDGET` 의 실 폭 가드 승격, 옛 라벨 5종의 근거 실측은 후속으로 남긴다.
