---
run_at: 2026-07-28T16:20:00+09:00
session: ai/claude/feature-0016-catcluster-scroll-polish
scope: 카테고리 선택 스크롤 polish — 280ms EaseOutExpo + 헤딩 점멸/멤버 파도(알파 선형 감쇠)
verdict: PASS
---

# Run — polish 헤드리스 결정론 (Environment: node vm)

- `tests/headless/test_catcluster_panel_scroll.js` 확장 **65 PASS / 0 FAIL**(직전 36 → +29).
  `graph-ctxmenu.js` 에서 `_META_GKEY_SEP`·`_metaGroupFam`·`_META_PANEL_SCROLL_MS`·`_metaEaseOutExpo`·
  `_metaAnimatePanelScroll`·wave 상수·`_metaClearPanelWave`·`_metaRunPanelWave`·`_metaGraphFocusPanelGroup`
  본문을 **원본에서 추출**해 vm 격리 실행. rAF·setTimeout·`performance.now` 를 test double 로 구동해
  프레임 단위 결정론 검증.
  - ② **EaseOutExpo 곡선 계약**: `f(0)=0` · `f(1)=1` 정확 · `t>1` 클램프 · 단조 증가 ·
    `f(0.5) ≥ 0.96`(초반 급가속) · duration **280ms**(대화 뷰 `POINT_SCROLL_DURATION_MS` 정합).
  - ③ 첫 프레임엔 미도달(=애니메이션 구동) → **≤20 프레임(≈280ms) 내 목표 정착**(native smooth 대비 단축 계약).
  - ④ **파도**: 멤버 전원 대상 · 지연 `90/116/142/168/194ms`(lead 90 + 26ms 간격) ·
    알파 `0.5 → 0`(첫/끝) · **감쇠 간격 균일(=선형)** · 단조 감소 · 다음 그룹 헤딩에서 경계 종료 ·
    정리 타이머 = 총 길이 + 여유(734ms) · 정리 후 클래스·인라인 변수 **전부 제거**.
  - ⑤ 상한 24행 · 접힌 그룹(숨은 행)은 헤딩만 점멸 · 멤버 1개면 0-나눗셈 없이 알파 0.5.
  - ⑥ sticky nav 보정(표시 44 → +6px / 숨김 → 보정 0) · 음수 클램프 0 · **maxTop 클램프**(신규).
  - ⑦ 세대 토큰 3종: stale rAF 무동작 · **진행 중 애니메이션이 새 선택에 선점되어 중단** ·
    새 연출이 직전 연출 잔여를 즉시 원복(중첩 방지).
  - ⑧ graceful no-op 4종 · ⑨ reduced-motion(즉시 점프 + 파도 미주입) · matchMedia 부재 · `performance.now` 부재 폴백.
  - ⑩ 호출부 인자 매핑(좌클릭·우클릭·전달 체인·헤딩/행 마크업 앵커) · ⑪ CSS 규칙·keyframes·duration 상수 일치.
- 회귀: `test_detail_dbgroups` **78** · `test_pixi_adapter` **190** · `test_graph_edge_flow` **43** ·
  `test_graph_reveal` **17** PASS / 0 FAIL. `node --check`(ESM) PASS.

# Run — PB-0008 실 Windows 브라우저 라이브 검증 (Environment: Windows-browser)

- Runner: AI · Bridge: `relay` @ `http://172.26.144.1:9223` · Chrome/150.0.7871.115
- 스테이징: 격리 컨테이너(§13.2.9) `web-catcluster-test`(:18099) — 현행 web 이미지 + 변경 static 2파일
  `docker cp` + 컨테이너 내 `inject_asset_stamp.py` 재실행. 서빙 stamp `489fae6df55b`,
  `_metaRunPanelWave` 2건 / `amgrCtRowWave` 2건 baked 확인. **라이브 web-a/web-b 무접촉.**
- ⚠ **드라이버 주의(실측 마찰)**: `bin/win-browser.py` 는 항상 `contexts[0].pages[0]` 을 잡는데
  같은 Windows Chrome 을 **병렬 AI 세션 4곳이 공유**(:18097/:18098/:8899/live)하고 있어 내 eval 이
  남의 탭에서 실행됐다. 같은 relay·같은 브라우저를 쓰되 **URL 로 내 탭만 선택**하는 전용 드라이버로
  수행(다른 세션 탭 무접촉). 사이드바 탭 전환은 `el.click()` 이 안 먹어 **trusted click** 필요.
- 대상: `/admin` → 그래프 뷰 → `mssql-web-qa` → `masangsoftweb`(카테고리 **93** · 행 **595** · 17,277px).

| # | 시나리오 | 결과 |
|---|---|---|
| 1 | 최하단(16,605)에서 `문피아 계정 이전`(be:2) 헤더 좌클릭 — 스크롤 샘플링 | t=79ms·197ms 는 상세 fetch 대기(미이동) → t=420ms **2,147** → t=827ms **1,698 정착**. 즉 렌더 후 이동은 **한 번의 짧은 EaseOutExpo 구간**에서 끝난다(직전 구현은 동일 거리에서 수 초 소요·800ms 시점 측정이 중간값이었음) **PASS** |
| 2 | 정착 위치 | 대상 헤딩 뷰포트 **+6px**(nav 숨김), 상태줄 `목록을 '문피아 계정 이전' 위치로 이동` **PASS** |
| 3 | 파도 파라미터(4-멤버 그룹) | `waveCount 4` · delay `90/116/142/168ms` · alpha `0.500/0.333/0.167/0.000` — **라이브에서 선형 감쇠 확증** **PASS** |
| 4 | 파도 시각(31-멤버 `커뮤니티 활동 감사`) | 헤딩 강조 + 아래로 흐르는 파란 띠, 아래로 갈수록 옅어짐 — 프레임 캡처 4매(t=451·619·762·892ms, waves 24, alpha 첫 0.500 / 중간 0.239 / 끝 0.000) **PASS** |
| 5 | 정리 | 연출 종료 후 `is-focus` 0 · `is-wave` 0 · 인라인 `--amgr-wave-a` 잔여 **0** **PASS** |
| 6 | 콘솔 | `window.onerror` **0건** |

- Evidence: `artifacts/shared/win-browser-shots-catcluster-scroll/`
  `10_polish_before_bottom.png` · `11_polish_settled_munpia.png` ·
  **`12_polish_wave_midscroll.png`**(스크롤 중 파도 진입) · **`13_polish_wave_peak.png`**(헤딩 강조 +
  멤버 파도 띠 + 하단 감쇠, 패널 clip) · `14_polish_wave_settled.png`(연출 종료·잔여 0).
- 정리: 격리 컨테이너 `docker rm -f` 완료, 내 탭만 close(공유 Chrome·타 세션 탭 무접촉 —
  `win-browser.py down` 은 공유 브라우저를 죽이므로 **쓰지 않았다**).
- 한계(정직 표기): 파도는 CSS `animation-delay` 기반이라 **캡처 타이밍이 프레임을 고르지 못하면**
  이미 끝난 상태가 찍힌다(4-멤버 그룹의 총 길이 ≈ 588ms). 위 시각 증거는 총 길이가 긴 31-멤버
  그룹(≈1.3s)에서 확보했고, 4-멤버 그룹은 파라미터 실측(#3)으로 확인했다.
