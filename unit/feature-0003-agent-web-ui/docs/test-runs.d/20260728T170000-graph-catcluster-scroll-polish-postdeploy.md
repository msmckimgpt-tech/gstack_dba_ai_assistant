---
run_at: 2026-07-28T17:00:00+09:00
session: ai/claude/feature-0016-catcluster-polish-postverify (postdeploy)
scope: POST-DEPLOY live — graph-catcluster-scroll polish (PR #1012 / main 9c434809)
verdict: PASS
---

# Run (2026-07-28) — polish POST-DEPLOY 라이브 실증 + PB-0008 — Environment: Windows-browser

pre-commit 검증은 격리 컨테이너(§13.2.9)였으므로, **main 기반 이미지가 실제로 서빙되는 사용자
경로**에서 다시 확인한다(§16.3 deploy-backed 완료 기준 — 머지 ≠ 배포 완료).

- 배포: PR **#1012** 머지(main **9c434809**) → `make deploy-web` 무중단 전체 롤아웃 —
  web-a/web-b `mysql-ai-web:9c434809` · insight/ask-worker `mysql-ai-agent:9c434809` · soak 통과 · exit 0.
- **서빙 baked 확인**(Caddy 경유 라이브, entry `admin.js?v=d9e63a464886`):
  `graph-ctxmenu.js` 에 `_metaRunPanelWave` **2건**, `graph.css` 에 `amgrCtRowWave` **2건**.
- Runner: AI · Bridge: `relay` @ `http://172.26.144.1:9223` · Chrome/150.0.7871.115
- 대상: `https://localhost/admin` → 그래프 뷰 → `mssql-web-qa` → `masangsoftweb`
  (카테고리 **93** · 행 **595** · `scrollHeight` 17,277px · 시작 16,605).

| # | 시나리오 | 결과 |
|---|---|---|
| 1 | **스크롤 속도**(AC-CPS-5) — `커뮤니티 활동 감사`(be:4) 헤더 좌클릭 후 샘플링 | t=86ms **16,605**(상세 fetch 대기) → t=213ms **9,457** → t=414ms **2,070** → t=820ms **2,017 정착**. 렌더 후 이동이 **한 EaseOutExpo 구간(≈280ms)** 안에서 끝나고, 초반 급가속(첫 ~130ms 에 절반 소화) 특성이 그대로 관측됨 **PASS** |
| 2 | 정착 위치 | 대상 헤딩 뷰포트 **+6px**, 상태줄 `목록을 '커뮤니티 활동 감사' 위치로 이동` **PASS** |
| 3 | **파도**(AC-CPS-6·7) | `is-focus` 헤딩 = `커뮤니티 활동 감사` · `is-wave` **24행**(상한) · delay `90/116/142ms`(26ms 간격) · alpha 첫 **0.500** / 중간 **0.239** / 끝 **0.000** — **선형 감쇠 라이브 확증** **PASS** |
| 4 | **정리**(AC-CPS-8) | 연출 종료 후 `is-focus` 0 · `is-wave` 0 · 인라인 `--amgr-wave-a` 잔여 **0** **PASS** |
| 5 | 콘솔 | `window.onerror` **0건** |

- Evidence: `artifacts/shared/win-browser-shots-catcluster-scroll/`
  `15_postdeploy_polish_before.png` · `16_postdeploy_polish_wave.png`(파도 tail — 중간 행에 잔여 틴트) ·
  `17_postdeploy_polish_settled.png`. 파도 **peak** 시각 증거는 스테이징 Run 의
  `13_polish_wave_peak.png`(같은 31-멤버 그룹, 헤딩 강조 + 아래로 흐르는 띠 + 하단 감쇠)가 정본이다.
- 드라이버(정직 표기): 공유 Windows Chrome 을 병렬 AI 세션이 함께 쓰고 있어 `bin/win-browser.py`
  (항상 `contexts[0].pages[0]`)로는 남의 탭이 잡힌다. **내 전용 새 탭을 만들어 그 page 객체만
  사용하고 종료 시 닫는** 단일-스크립트 드라이버로 수행했다(타 세션 탭·공유 Chrome 무접촉,
  `down` 미사용). 추가 실측 2건: 관리 콘솔 탭 전환은 **trusted click** 이어야 하고,
  `wait_until='domcontentloaded'` 직후 클릭은 admin 부트스트랩 전이라 활성화되지 않는다
  (`wait_until='load'` + 8s 대기 필요 — 스코프 옵션 0 으로 관측).
- 캡처 타이밍 한계: 파도는 CSS `animation-delay` 라 프레임 선택이 어렵다. 위 #3 의 파라미터는
  DOM 실측(결정적)이고, 시각 peak 은 총 길이가 긴 그룹의 스테이징 캡처로 보완한다.
