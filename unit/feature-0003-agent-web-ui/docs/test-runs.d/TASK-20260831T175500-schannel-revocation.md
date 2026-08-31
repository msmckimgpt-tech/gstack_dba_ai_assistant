---
run_at: 2026-08-31T18:20:00+09:00
session: ai/claude-corp/feature-0043-schannel-revocation
scope: static/agent/bridge_setup.{ps1,sh} 서빙 사본 동기화 (feature-0043 정본 미러)
verdict: PASS
---

# Run — TASK-20260831T175500-schannel-revocation (feature-0003 소유 자산)

이 cycle 이 feature-0003 에서 건드린 것은 **서빙 사본 2개뿐**이다:

- `src/static/agent/bridge_setup.ps1`
- `src/static/agent/bridge_setup.sh`

정본은 feature-0043(`unit/feature-0043-external-llm-bridge/src/`)이고, 두 파일은 그것의
**바이트 동일 미러**다(`test_served_setup_script_matches_the_source` · 본 cycle 신규
`test_windows_tls_revocation.py::test_served_copy_carries_the_fix` 가 강제). 변경 내용·근거·
전체 증적은 feature-0043 쪽 fragment 를 정본으로 본다 —
`unit/feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260831T175500-schannel-revocation.md`.

## Environment: Windows-browser — **미수행**, 사유: 렌더 표면이 없는 자산이다

이 두 파일은 `static/` 아래 있어 PB-0008 게이트(`is_web_asset` = `*/static/*`)에 걸리지만,
**브라우저가 렌더하는 자산이 아니다.** 사용자가 내려받아 **셸·PowerShell 이 실행하는 스크립트**로,
DOM·CSS·레이아웃이 존재하지 않는다. 이 cycle 의 diff 에는 HTML/CSS/JS 변경이 **0건**이며 웹 화면의
어떤 픽셀도 달라지지 않는다. 따라서 브라우저 시각검증은 «환경상 불가» 가 아니라 **적용 대상이
아니다**(§16.6 의 «기하에 영향을 주지 않는 이유 명시» — 여기서는 렌더 경로 자체가 없다).

## 대신 수행한 것 — 이 자산의 **실제 소비자** 환경에서 실측

브라우저 대신 이 파일을 실제로 실행하는 런타임에서 검증했다. 이 자산 클래스에는 이것이
브라우저 검증보다 강한 증거다:

| 검증 | 환경 | 결과 |
|---|---|---|
| 파싱 | 실 **Windows PowerShell 5.1** (`5.1.19041.6456`) | `ParseFile` **오류 0건** · `U+B7EC`('러') 디코딩 OK · BOM `efbbbf` 보존 |
| 수신 동작 A~G | 실 Windows PS 5.1 + 윈도우 동봉 `curl 8.13.0 Schannel` + `Python 3.14` + 라이브 엣지 | 7/7 PASS — 정상 `via=curl` sha OK · 수정 전 재현 `exit 60` → 파이썬 폴백 sha OK · **무관한 CA → 실패**(pin 유지) |
| 구문 | `sh -n` · `bash -n` (`bridge_setup.sh`) | OK |
| 서빙 사본 동일성 | pytest | 정본과 **바이트 동일**(ps1·sh 양쪽) |

⚠ **서빙 경로 자체(HTTP 로 받아지는지)는 배포 후 확인 대상**이다 — 이 fragment 는 커밋 시점의
파일 상태를 기록한다. 라이브 재수신(`http://<host>/static/agent/bridge_setup.ps1` 의 SHA256 이
정본과 일치하는지)은 배포 직후 POST-DEPLOY 로 확인하고 feature-0043 fragment 에 덧붙인다.
