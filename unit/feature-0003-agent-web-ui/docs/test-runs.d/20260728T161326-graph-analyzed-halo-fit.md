---
run_at: 2026-07-28T16:13:26+09:00
session: ai/claude/feature-0016-analyzed-halo-fit
scope: unit/feature-0003-agent-web-ui/src/static/graph/graph-renderer-pixi.js
verdict: PASS
---

### Run (2026-07-28) — graph-analyzed-halo-fit: AI 분석 완료 컬럼 노드 상태 테두리 기하 보정 — **Environment: Windows-browser**

#### 1. 사용자 리포트

> `그래프 뷰` 에서 AI분석이 완료된 컬럼 노드에서, 노드 크기에 비해 테두리가 너무 비대하게
> 구성되어 있어 적절하게 재구성이 필요합니다.

첨부 스크린샷: `masangsoft_modules` 의 컬럼 목록(module_srl · module · module_category_srl · …)이
개별 노드가 아니라 **하나의 세로 보라색 관**으로 이어져 보이는 화면.

#### 2. 진단 — 두께 문제가 아니라 모양·크기 계약의 부재

- 컬럼 노드: `type: "circle"`, `style.size = 11`(숫자 = 지름) — `_metaColStyle`.
- `_applyNodeStates` 는 **모든 노드를 rect 로 가정**했다:
  ```js
  const w = Array.isArray(s.size) ? s.size[0] : (s.size || 24),
        h = Array.isArray(s.size) ? s.size[1] : 24;   // ← circle 은 size 가 숫자라 h = 24 고정
  const rx = -w/2 - 3 - inset, ry = -h/2 - 3 - inset, rw = w + 6 + …, rh = h + 6 + …;
  ```
- 결과: 지름 11px 원형 노드에 **17 × 30 사각 알약**(두께 3px)이 그려진다.
  - 폭 초과 17 vs 11 = 1.5배, **높이 초과 30 vs 11 = 2.7배**.
  - 컬럼 행 간격은 ~24px 이므로 **halo 높이(30px) > 행 간격** → 이웃 halo 가 서로 겹쳐
    **세로 관으로 융합**된다. 이것이 리포트 화면의 정체다.
- 따라서 "두께만 줄이기" 는 관을 얇게 만들 뿐 없애지 못한다. 모양(원/사각)과 크기 비례를
  계약으로 세우는 것이 근본 수정이다.

#### 3. 수정

`PixiAdapterPure` 에 순수 기하 함수 2개를 신설하고 `_applyNodeStates` 가 이를 소비한다.

```js
haloGeom(n, i, lineWidth)   // {shape:"circle", r, lw} | {shape:"rect", x,y,w,h,radius, lw}
  k   = clamp(min(w,h) / 24, 0.4, 1)      // 24 = 테이블·루틴 칩 높이 → rect 는 k=1
  lw  = max(1, lineWidth · k)             // 두께 하한 1px(줌아웃 소실 방지)
  gap = max(1.5, 3k)                      // 노드 표면 ↔ 링 중심선
  off = gap + i · 2k                      // 동심링(다중 상태 동시 표기)
dashArcs(r, dash)           // 호 길이 기준 [on,off] → [[a0,a1],…] 라디안 구간
```

- **circle**: `r = size/2 + off` 인 원형 halo. 11px 컬럼 → 두께 **3 → 1.375px**,
  halo 외곽 지름 **30 → 15.1px**.
- **rect**: k=1 이므로 `x = -w/2-3-2i` · `radius = (s.radius||4)+2+2i` · `lw` 원본 —
  종전 하드코딩과 **산술적으로 동일**(회귀 0).
- **점선(running/busy)**: 원에는 4변이 없으므로 `dashArcs` 로 호 대시. 각도 = 호길이/r 이라
  반지름과 무관하게 직선 대시와 **같은 화면 대시 길이**가 나온다.

#### 4. 검증

**헤드리스 (결정론)**

- `test_pixi_adapter.js` **205 PASS / 0 FAIL** — T27 신설 15건:
  - rect 회귀 0 — i=0 `{x:-78, y:-15, w:156, h:30, radius:8, lw:3}`, i=1 `{x:-80, y:-17, w:160, h:34, radius:10}` 전건 대조.
  - circle — 원형 판정 · 두께 3·(11/24) 비례 · 반지름 = 노드 반지름 + 여백 ·
    **외곽 지름 < 노드 지름 1.5배** · 동심링 간격 < 2px · size 미지정 11 폴백 ·
    `type` 미지정(hover 확장 카드) → rect 경로 · 두께 하한 1px.
  - `dashArcs` — 총 on 호길이 ≈ 둘레·on/(on+off) · 각도 단조증가·비퇴화 ·
    각 대시 ≤ on 길이 · 한 바퀴 초과 없음.
- 그래프 전 헤드리스 스위트 **677 PASS / 0 FAIL**
  (pixi_adapter 205 · edge_visibility 73 · detail_dbgroups 78 · minimap_reuse 65 ·
  edge_flow 43 · catcluster_panel_scroll 36 · category 26 · colnav 22 · collod 20 ·
  layoutmemo 19 · vpack 19 · reveal 17 · simgroups_p2 16 · cullrefkeep 15 ·
  detail_colsel 9 · agglod 8 · viewportcull 6).
- 드로잉 경로 런어웨이 검사(Graphics 스텁 계수): circle analyzed 2 ops · running 15 ·
  busy 23 · match+analyzed+running+selected 23 · rect busy 189 — 무한 루프 0.

**PB-0008 실 Windows 브라우저** — Chrome/150.0.7871.115, `bin/win-browser.py` 무권한 relay
(`bridge_mode: relay`, endpoint `http://172.26.144.1:9223`), `https://localhost/admin`.
WSL headless 아닌 실제 Windows 화면.

| | 화면 | 결과 |
|---|---|---|
| BEFORE | `mysql-gz-qa-global` → `gunzgame.mail` 컬럼 4개(FromCID·MAID·ToAID·ToCID) 4× 확대 | 각 컬럼의 보라 알약이 **세로로 겹쳐 하나의 관**. 점(11px)보다 테두리가 압도적으로 큼 — 리포트 재현 |
| AFTER | `masangsoftweb.masangsoft_documents` 컬럼(document_srl·module_srl·category_srl·lang_code·is_notice·title·…) 4× 확대 — **사용자 리포트와 동일 화면** | 컬럼마다 **얇은 보라 링이 개별 분리**. 관 소멸. 테이블 칩의 analyzed(보라)·selected(검정) rect halo 는 **불변** |

- Evidence: `evidence/analyzed-halo-before-4x.png` · `evidence/analyzed-halo-after-4x.png` ·
  `evidence/analyzed-halo-after-full.png`
- AFTER 는 수정본을 web-a/web-b 에 주입해 서빙(`curl` 로 `haloGeom` 4건 확인)한 상태에서 촬영.
  콘솔 에러 0(`window.error`/`unhandledrejection` 훅 수집 결과 빈 배열), canvas 생존.
- **주입 QA 원복 완료** — 이미지 원본(`mysql-ai-web:b6882c7d`)에서 추출해 양 컨테이너에 복원.
  서빙 `haloGeom` **0건** · `/livez` **200**. 잔재 0.

**환경 마찰 기록(정직)**: 대형 스키마(`gunzgame` 121테이블 · 300루틴) 전개 중 Windows Chrome 이
브리지째 종료되는 현상이 반복됐다(도구 `no_bridge`). 본 변경과 무관함을 대조로 확인 —
원본 렌더러에서도 화면 이탈이 발생했고, 수정본 재주입 대조에서는 `errs=[] · canvas 생존 ·
nav=navigate` 로 정상이었다. 추가로 QA 중 넣었던 `?v=haloqa1` 캐시버스터가 서버 측 asset-stamp
재주입으로 원복되며 import 불일치를 만든 것도 이탈에 기여했다. 최종 AFTER 는 가벼운 스키마
(`masangsoftweb`)로 옮겨 정상 확보.

**`make test`(pytest)**: attachment 13건 + runtime_settings 2건 = 15건 실패. 전부 worktree 격리
네트워크 환경성 baseline 이며, 본 cycle 은 **Python 파일 무접촉**(JS 2개만 변경, ruff PASS)이라
인과가 성립하지 않는다.

- Pass/Fail: **PASS**. Runner: AI.
