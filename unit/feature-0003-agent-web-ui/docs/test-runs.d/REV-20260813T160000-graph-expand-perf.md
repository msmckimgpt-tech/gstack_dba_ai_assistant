---
run_at: 2026-08-13T16:00:00+09:00
session: ai/claude/feature-0003-graph-expand-perf
scope: 그래프 뷰 '노드 펼침' 성능 3축 개선 (R1 pixi diff · R2 선-fetch · R3 layoutmemo)
verdict: PASS
---

# Run — 그래프 노드 펼침 성능 (PB-0008 실 Windows 브라우저)

- **Environment**: `Windows-browser` — `bin/win-browser.py` CDP 자동 구동, 실 Windows Chrome/150.0.7871.128
- **세션 격리 (§16.6 MUST)**: 공유 프로파일·고정 포트에 붙지 않고 **자기 세션 전용 인스턴스**를 띄웠다 —
  `WIN_BROWSER_CDP_PORT=9242` · `WIN_BROWSER_RELAY_PORT=9243` · `WIN_BROWSER_PROFILE=C:\temp\win-browser-graphperf`.
  (기본 포트에 붙었을 때 실제로 **다른 세션의 탭**(`:18097` 프리뷰)이 잡히는 것을 관측해 즉시 분리했다.)
- **측정 도구**: CDP `Profiler`(200µs 샘플링) + `PerformanceObserver('longtask')` + 상태줄
  `MutationObserver` 타임라인 + `window.__META_GRAPH_PERF.render`.

## 1. 측정 시나리오 (동일 조건 고정)

| 항목 | 값 |
|---|---|
| 데이터소스 | `mysql-mv-qa-game` (`mysql-ace6a9afbd87`) |
| 스키마 | `web_ranking` — 테이블 689 · 렌더 노드 693 |
| 조작 | 1:1 줌 · 상세 패널 접음 · 캔버스 좌표 고정 클릭으로 **16-컬럼 테이블 1개 펼침** |
| 표본 | 개선 전 **n=4**, 개선 후 **n=3** (같은 브라우저·같은 뷰포트·같은 좌표) |

개선본은 `main` 을 건드리지 않고 **자기 worktree 로 빌드한 격리 preview 컨테이너**(§13.2.9 격리 경로,
공유 트리·공유 `.env` 무수정, 포트 18098)에서 측정한 뒤 컨테이너·이미지를 회수했다.

## 2. 결과 (중앙값)

| 지표 | 개선 전 (main) | 개선 후 | 변화 |
|---|---|---|---|
| 클릭 → "펼침 완료" 상태줄 | **915ms** (935/916/914/884) | **556ms** (621/552/556) | **−39%** |
| 메인스레드 블로킹(longtask 합) | **344ms** (312/365/348/340) | **133ms** (133/148/71) | **−61%** |
| 최장 단일 longtask | 312~365ms | 77ms | 지연 스파이크 해소 |
| pixi `drawMs` | **210ms** (214/207/254/196) | **35ms** (48/35/25) | **−83%** |
| 오브젝트 재생성 `made` | **537** (538/538/539/533) | **21** | **−96%** |
| 라벨 재생성 `labelsCreated` | **523** (524/524/525/519) | **19** | **−96%** |
| 재사용 `reused` / 재배치 `moved` | 264 / (계측 없음) | 771 / **514** | 이동은 재배치로 흡수 |
| 컬럼 조회 단계(조회 시작→펼침 완료) | **438ms** | **78ms** | 선-fetch 가 왕복을 앞당김 |

접기("−") 경로도 같은 이득: `drawMs 14.2ms` · `made 3` · `moved 532` · `labelsCreated 1`.

**모집단·표본 한계 (§16.7 G7-b)**: 위 수치는 **단일 모델(693 노드)·단일 컬럼 수(16)·단일 줌(1:1)**
에서의 n=4/n=3 중앙값이다. 스키마 **첫 펼침**(693 노드 신규 생성 = scene-switch)은 재사용 여지가
없어 개선 대상이 아니며 실제로 변화가 없었다(base 860ms/draw 345ms ↔ 개선 949ms/draw 424ms — 회차
편차 범위). 모델 크기·컬럼 수에 따른 스케일링은 측정하지 않았다.

## 3. 시각·인터랙션 회귀 (PB-0008)

| # | 항목 | 결과 |
|---|---|---|
| 1 | 동일 조작 후 렌더 대조(개선 전/후 스크린샷) | **PASS** — 펼친 컬럼 16행 · "−" 컨트롤 · 선택 링 · masonry 좌표 · 미니맵까지 **육안 동일**(차이는 상태줄 토스트 문구뿐) |
| 2 | 선택 하이라이트(states 변경 → 재생성 경로) | PASS — 선택 테두리 정상 |
| 3 | 노드 드래그(freeplace) | PASS — 드래그 위치 유지, 재배치 경로와 충돌 없음 |
| 4 | 컬럼 접기("−") | PASS — 상태줄 "컬럼을 접었습니다", 잔상·고아 노드 0 |
| 5 | 재배치 이동 트윈 | PASS — `move.items 93` 로 동작(연출 유지) |
| 6 | `pageerror` / `unhandledrejection` | **0건** (수집기 주입 후 전 조작) |

캡처: `scratchpad` 경로의 `base-expanded.png`(개선 전) ↔ `prev-expanded.png`(개선 후) ↔
`prev-after-interact.png`(드래그·접기 후). 두 캡처는 같은 뷰포트·같은 조작 순서로 얻었다.

## 4. 정적/단위 검증

- `node --check`(ESM) — `graph-core.js` · `graph-ctxmenu.js` · `graph-renderer-pixi.js` PASS
- 헤드리스 graph 계열 전량 **1,283 PASS / 0 FAIL**
  - 신규 `test_graph_expand_prefetch.js` **15** (선-fetch 계약: 중복억제·promise 공유·소비·실패 흡수·
    리셋/prune 무효화·aliasing 차단)
  - `test_pixi_adapter.js` **304** (T17/T19 위치-제외 서명 전환 + **T31 씬-diff 13건 신규**)
  - `test_g6build_layoutmemo.js` **25** (**T7 신규** — 컬럼 ingest 캐시 적중 + 적중==fresh 좌표 동일)

## 5. POST-DEPLOY — 라이브 실측 (2026-08-13, main `16da577f`)

**배포**: PR #1255 머지 → main `16da577f` → `sudo make deploy-web-only` (무중단 롤링 + 90s soak 통과).

| # | 항목 | 결과 |
|---|---|---|
| 1 | replica 파리티 | web-a·web-b 모두 `mysql-ai-web:16da577f` (= main HEAD) |
| 2 | `/healthz` | `200` · `git_commit=16da577f` · `mysql_ok` · `pg_ok` |
| 3 | **무중단 실측** | 엣지 로그 `no upstreams available` **0건** (스크립트 성공 보고가 아닌 직접 계측 — RUNBOOK §10 [5]) |
| 4 | 서빙 자산 배선 | `graph-renderer-pixi.js` 에 `nodeShapeSig` **2건** · `graph-ctxmenu.js` 에 `_metaGraphPrefetchColumns` **2건** · `graph-core.js` 에 `_metaColPrefetchClear` **2건** |

**라이브 재측정** (동일 시나리오 — `mysql-mv-qa-game`/`web_ranking` 693 노드, 16-컬럼 테이블 펼침, n=3):

| 지표 | 개선 전(main, n=4) | **라이브 배포본(n=3)** | 격리 프리뷰(n=3) |
|---|---|---|---|
| 클릭 → 펼침 완료 | 915ms | **544ms** (544/554/542) | 556ms |
| 메인스레드 블로킹 | 344ms | **134ms** (134/150/114) | 133ms |
| pixi `drawMs` | 210ms | **32.8ms** (46.4/31.9/32.8) | 35ms |
| 오브젝트 재생성 `made` | 537 | **21** (21/21/21) | 21 |
| 라벨 재생성 | 523 | **19** (19/19/19) | 19 |
| 재사용 / 재배치 | 264 / — | 771~805 / 217~222 | 771 / 514 |

프리뷰 수치와 **차이 없음** — 격리 프리뷰가 라이브를 정확히 예측했다.

**시각·오류**: 3개 테이블 펼침 후 렌더 정상(컬럼 행 · "−" 컨트롤 · 선택 링 · masonry 재배치),
`pageerror`/`unhandledrejection` **0건**. 캡처 `live-expanded.png`.

**미변경 확인**: 재배치 이동 트윈 360ms 는 사용자 결정("360ms 유지")대로 그대로다.
