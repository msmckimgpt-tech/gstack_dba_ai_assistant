---
run_at: 2026-07-28T18:10:00+09:00
session: ai/claude/feature-0016-graph-hdr-fit
scope: unit/feature-0003-agent-web-ui/src/static/graph (graph-state·graph-core)
verdict: PASS  # PRE-COMMIT 자동검증 PASS · PB-0008 라이브는 배포 후 HF.6
---

### Run (2026-07-28) — graph-hdr-label-fit: 위계 헤더 라벨을 클러스터 범위만큼 확장 — **Environment: Windows-browser (배포 후 HF.6)**

> 정본 TASK/DECISION 은 `unit/feature-0016-metadata-graph/docs/TASK.md` `## 20260728T1810-graph-hdr-label-fit`.
> 본 파일은 **파일 소유 feature**(feature-0003, static/graph) 쪽 Run 상세다.

#### 1. 사용자 요청

label-lod(§20260728T1604) 배포 확인 직후의 후속:

> 줌 아웃을 통해 노드의 문자열이 나타나지 않도록 처리하는 부분이 확인되었습니다. 해당 동작에 대응하여
> '컨텐츠 카테고리 클러스터' 의 텍스트는 줌 아웃 시에도 상대적으로 명확하게 보이게 구성하기 위해
> **클러스터 범위만큼 텍스트 크기가 확장되는 방안**을 검토해주세요. **웹 리서치**를 통해, 줌 아웃 시
> 상위 노드를 더 잘 표현할 수 있는 수단이 있을지도 검토해주세요.

사용자 결정(검토 결과 3택 제시 후): 방식 = **범위 + 화면 하한** / 적용 = **위계 헤더 전부** / 칩 넘침 = **박스 위로 팔출**.

#### 2. 진단 — 박스 크기 정보를 폰트가 쓰지 않았다

- `group-hd`(컨텐츠 카테고리 = sim-group 헤더)는 `labelFontSize: 10.5` **고정**. 칩 폭 `hdW` 는 박스 폭에
  맞춰 늘어나지만 폰트는 그대로라, 박스가 248px 든 920px 든 똑같이 zoom `3.2/10.5 ≈ 0.305` 에서 억제됐다.
- 위계 한 단계 위 `cat-hd`(제품 카테고리 밴드, 12 고정)도 동형 — 억제 `3.2/12 ≈ 0.2667`.
- 블록 폭은 `COLW = 224` 기준 열 수로 결정: 1열 **248** / 2열 **472** / 3열 **696** / 4열 **920+** px.

#### 3. 웹 리서치 (사용자 요청 축)

| 결론 | 근거 |
|---|---|
| 면적 비례 라벨은 **지도학 표준** | "scale label size proportionally to the feature size using a minimum 6-point font" · 트리맵 `font = min(w/4, h/2)` |
| 축척별 폰트 보간은 **상용 GIS 기본 기능** | ArcGIS `scale-based label sizing` — scale stop 사이 선형 보간, 목적이 "reduce visual density at smaller scales while retaining an appropriate relative size" |
| 면적 라벨은 **범위를 캔버스로** 쓴다 | polygon 의 가장 넓은 단면을 따라 수평 배치 + 자간 확대 |
| 줌 레벨별 스타일 적응 = 대규모 그래프 표준 전략 | 클러스터 아이콘 시각 속성 ↔ 클러스터 속성(노드 수·밀도) 대응 |
| 주의: "면적을 시각적 위계와 혼동하지 말라" | 본 케이스는 **박스 크기 = 테이블 수**라 상관관계 성립 → 해당하지 않음 |

**막힌 길 (재시도 방지용 기록)**

- **SDF/MSDF 폰트**: "stay crisp at any size without generating larger textures" 로 라벨 붕괴의 근본 해법처럼
  보인다. 그러나 **PixiJS v8 공식 문서가 대형 문자셋(CJK·emoji)은 텍스처 메모리 제약으로 비현실적이며
  `Text`/`HTMLText` 를 쓰라고 명시**한다. 라벨이 한국어인 본 프로젝트에선 §79 T79.5(CJK 글리프 집합 방대)와
  같은 벽이며, label-lod TL.5 의 mipmap 철회와 같은 계열의 **벤더 한계**다 → **비채택 확정**.
- **극단 줌아웃 metanode 강등**(graph summarization·GrouseFlocks 계열): 리서치가 지지하는 정석이지만
  **§67 에서 사용자 피드백("집계 = 규모 파악 어려움")으로 이미 폐기된 방향**이다. 되살리려면 그 결정을 뒤집는
  셈이라 본 cycle 범위 밖 — 재논의 대상으로 분리.

#### 4. 채택 — `clamp(base, min(base/zoom, 박스fit), MAX)`

```
_metaHdrFitFont(base, boxW, textLen, zoom):
  z >= 1        → base                        // 줌인은 부풀지 않음(§86 결정과 정합, 회귀 0)
  want = base/z                               // (a) 화면상 base 크기 유지 — 지도 라벨 관례 · §85 edgeScreenScale 선례
  fit  = (boxW - PAD) / (textLen * 0.686)     // (b) 라벨이 자기 범위를 넘지 않게 하는 상한 — 트리맵 fit-to-box
  → clamp(base, min(want, fit), MAX)
```

- **(b) fit 상한이 본질적**이다: 없으면 극단 줌아웃에서 헤더끼리 겹쳐 폭발한다. 지도는 이 문제를 **라벨 충돌
  컬링**으로 푸는데, 박스 상한은 그 복잡도 없이 같은 목적을 달성한다 — 각 라벨이 자기 범위를 넘지 않으면
  이웃과도 겹치지 않는다. 동시에 "**클러스터 범위만큼**" 이라는 사용자 표현이 문자 그대로 성립한다.
- **`MAX` 는 줌 하한에서 파생** — `ceil(헤더 판독 하한 3.2 / zoomRange 하한 0.05) = 64`. 역보정은 상한에
  닿는 순간부터 화면 크기가 감쇠하므로(`MAX × z`), 상한이 곧 "**어디까지 base 크기로 보이는가**"(`z > base/MAX`)를
  정한다. 리터럴 **26 이면 실측 "전체 조망" 줌(라이브 136 스키마 = 0.2524)에서 이미 6.6px 로 감쇠**해 사용자
  요구를 만족하지 못한다. 64 로 두면 그 줌이 base 크기 유지 구간에 들어온다.
- **칩 기하 = 하단 앵커 상방 팔출 + hit 영역 상한**(사용자 결정 + §8 리뷰 흡수): 칩 폭·높이를 폰트에 비례시키고
  **하단 y 를 종전 값으로 고정**해 커진 만큼 박스 *위로* 자란다. 예약 헤더 행(GHH=26 / CATHH=36) 아래 멤버
  영역을 침범하지 않으므로 **reflow 0**.
  **단, 칩 높이에는 상한이 있다**(§8 P1 GATE) — 칩은 **hit 영역**이고 GH/CATH 는 테이블 칩보다 zIndex 가 높은
  드래그 핸들이라, 무제한 팔출은 *이웃 블록* 노드의 클릭을 가로챈다. 상한 GH `22 + GGY = 38` / CATH `27`.
  **폰트는 상한에 걸리지 않는다** — `hitTest`/`buildHitGrid` 가 `nodeBBox(style.size)` 만 보므로 라벨은 hit
  대상이 아니고, 텍스트가 칩을 넘어도 상호작용 영향이 0 이다(판독성 이득 보존). 텍스트가 칩을 넘는 구간은
  알약을 옅게(`fillOpacity 0.45`·`lineWidth 0`) 해 '깨진 칩' 이 아니라 **'밴드 위 글자'(지도 area-label)** 로
  읽히게 했고, `zoom ≥ 1` 은 알약·칩 종전 그대로다(회귀 0).
  GH 에 없던 `labelMaxWidth` 안전망도 추가(확장 폰트에서 한글 실폭 > 추정계수).

#### 5. stale 폰트 방지 — 반동 밴드 (놓치면 역보정이 무의미해진다)

폰트가 `base/z` 로 **연속** 변하는데 rebuild 는 밴드 전이에서만 걸린다. 억제 밴드만으로는 폰트가 마지막
rebuild 시점 값으로 **stale** 해져 화면 크기가 드리프트한다 — 즉 역보정의 목적 자체가 무너진다. 그래서
역보정 배율을 **25% 승법 스텝**으로 양자화해 `_metaLabelBandOf` 에 `/h<step>` 으로 합류시켰다(§85 가 엣지
재페인트에 채택한 것과 같은 허용 오차 → 화면 크기 드리프트 ≤25% 유계).

**상한 클램프 필수**: `base/z > MAX` 부터 폰트는 `min(fit, MAX)` 로 z 와 무관해지므로, 스텝이 계속 늘면
**아무 변화 없는 rebuild** 가 극단 줌아웃 휠마다 걸린다. 클램프 없이 넣었을 때 기존 **F3·F7('무의미 rebuild
차단')이 실제로 깨졌고**, 그 실측을 근거로 `_META_HDR_FIT_STEP_CAP`(= `ceil(log(MAX/base_min)/log(1.25))`)을
도입했다 — 테스트가 내 회귀를 잡았다는 사실을 그대로 기록한다.

#### 6. 개선 실측 (억제 시작 줌 — 낮을수록 좋음)

| 대상 | 현행(고정) | 1열 248 | 2열 472 | 3열 696 | 4열 920 |
|---|---|---|---|---|---|
| `group-hd` 억제 시작 zoom | 0.3048 | **0.1416** | **0.0642** | **0.0500** | **0.0500** |
| 실측 개요 줌 0.2524 의 화면 크기 | 2.65px | 5.7px | **10.5px** | **10.5px** | **10.5px** |

`cat-hd`(base 12 · 21자): 억제 **0.2667 → bw 400 은 0.1405 / bw ≥ 800 은 0.0500**, 0.2524 화면 크기
**3.03px → 12.0px**.

즉 **2열 이상 클러스터는 실측 개요 줌에서 base 크기 그대로** 보이고, **3열 이상은 줌 하한(0.05)까지
사라지지 않는다**. 1열(가장 작은 클러스터)도 억제 시점이 2.15× 늦어진다 — 사용자 제안(범위 비례)만으로는
1열이 전혀 개선되지 않았을 지점이다.

#### 7. 자동 검증 (PASS)

- `test_g6build_labellod.js` **36 → 71 PASS / 0 FAIL** (신규 35):
  - **Section I(유닛 12)** — `_metaHdrFitFont`/`_metaHdrFitBandOf` 계약: 심볼 노출 · `z ≥ 1` base 고정(회귀 0) ·
    넓은 박스 확장 · MAX 상한 · **좁은 박스·긴 라벨은 base 유지**(넘치게 키우지 않음) · **산출 폰트의 라벨 폭이
    박스를 넘지 않음**(4개 조합 전수) · 박스 폭 단조 비감소(지도학 면적 비례 계약) · 종전 억제 줌(0.25)에서
    판독 하한 확보 · 밴드 0/단조/**상한 클램프**/비정상 zoom 폴백.
  - **Section J(결합 11)** — 실 `_metaG6Build` 방출: GH 방출 전제 · 종전 억제 줌에서 라벨 유지 · 폰트가 base 초과 ·
    판독 크기 확보 · `labelMaxWidth ≤ 칩 폭` · **칩 하단이 줌과 무관하게 고정**(상방 팔출) · 칩 높이 비례 증가 ·
    **멤버 좌표·개수 불변(reflow 0)** · CATH 동일 적용 · CATH 칩 하단 고정 · **밴드에 헤더 반동 성분 합류**.
    유닛만 보면 호출부가 안 물렸어도 전건 PASS 하므로 결합을 별도로 고정했다.
  - **B5 계약 재진술(3)** — 종전 "이 줌에서 카테고리 헤더도 억제" → 이제 "범위 파생 폰트로 **유지**". 약화로
    오인되지 않게 **실제 판독 크기(fontSize×zoom ≥ 하한)** 와 **폰트가 base 를 실제로 초과했는지**까지 함께 단정한다.
  - **Section K(리뷰 흡수 10)** — §8 codex P1·P2 를 고정: 칩 높이 상한(GH 38 / CATH 27) · **어떤 GH 칩도 다른
    그룹 블록 bbox 를 침범하지 않음**(hit 가로채기 0) · 칩 상한에 걸려도 폰트는 유지 · 텍스트가 칩을 넘는 구간의
    알약 소프트닝 · `zoom = 1` 알약·칩 회귀 0 · products 모드 게이트 닫힘 · 게이트 닫히면 밴드에 `/h` 부재.
    **상한 제거판 번들로 K2·K3·K7 이 실제로 FAIL** 함을 실측했다(칩 높이 52/52/42/52/46/46 · 이웃 블록 침범 ·
    CATH 60/30) — 테스트가 결함 자체를 잡는지 검증한 것이며 통과만 보고 넘기지 않았다.
  - `seedModel` 에 `names` 옵션 추가(sim-group = 컨텐츠 카테고리 헤더 방출 조건인 이름-family 2개를 만들기 위함).
    기존 호출은 무영향(미지정 시 종전 `t${i}`).
- 헤드리스 **전 스위트 21개 910 PASS / 0 FAIL**: labellod 71 · agglod 8 · category 26 · collod 20 · cullrefkeep 15 ·
  edge_visibility 73 · layoutmemo 19 · minimap_reuse 65 · simgroups_p2 16 · viewportcull 6 · vpack 19 · colnav 22 ·
  detail_colsel 9 · routine_colref 30 · detail_dbgroups 78 · reveal 17 · ancestor_focus 32 · catcluster_panel_scroll 65 ·
  edge_flow 73 · hover_flow 41 · pixi_adapter 205.
- `node --check --input-type=module` PASS(graph-state · graph-core). 캐시버스터 `?v=dev` 고정 + 빌드
  `inject_asset_stamp` content-hash 자동주입(수기 bump 0).

#### 8. §18.8 적대 검증 — codex-review (PASS-WITH-FIXES · P1 1건 · P2 1건 in-cycle 흡수)

`codex review --uncommitted`(codex-cli 0.145.0). `[CODEX:*]` 는 §18.4/§18.9 의 check #9 accepted verdict —
이 변경은 **레이아웃 상수(GGY·GHH·CATHH)와 hit-test 구현(`nodeBBox`·zIndex)을 함께** 봐야 판정되므로 repo
접근 리뷰어가 적합하다.

| # | 등급 | 결함 | 수정 |
|---|---|---|---|
| ① | **P1 / GATE** | **칩 hit 영역이 이웃 그룹 블록을 침범한다.** 폰트 64(=`MAX`)에서 칩 높이 ~110 world, 하단이 `top+22` 고정 → **위 그룹 블록 안 72 world 침범**(실측: 행 간격 `GGY=16`, 행1 블록 40~168 / 행2 칩 하단 206). GH·CATH 는 `_METZ.GROUP_HD`(5) = 테이블 칩(4) 위 드래그 핸들이고 `hitTest`/`buildHitGrid` 가 `nodeBBox(style.size)` + zIndex 로 판정하므로 **위 그룹 테이블의 클릭·드래그를 가로챈다** — memory 에 2회 재발로 기록된 z-order↔hit-test 결함 계열의 재발 | **칩(hit 영역)만 상한**(GH `22+GGY=38` / CATH `27`)으로 묶고 **폰트는 유지**. 라벨은 hit 대상이 아니므로 텍스트가 칩을 넘어도 상호작용 영향 0 · 판독성 이득 보존. 텍스트가 칩을 넘는 구간은 알약 소프트닝(`fillOpacity 0.45`·`lineWidth 0`) → '밴드 위 글자'로 읽힌다. `zoom ≥ 1` 회귀 0 |
| ② | P2 | **`/h` 밴드가 헤더 미방출 경로에서도 rebuild 를 유발한다.** `products` 모드는 `_metaG6Build()` 가 헤더 방출 전에 `_metaG6BuildProducts()` 로 조기 return → 1→0.89→0.71→0.57 전이가 전부 헛 `setData`/draw(좁은 박스로 `fit ≤ base` 인 경우도 동형) | 방출 시점에 `fit > base`(확장 여력)인 헤더를 세고(`_metaHdrFitNote`) 0 이면 `/h` 제거 + 리셋(`_metaHdrFitReset`)을 **products 디스패치보다 먼저**. 게이트는 **z-독립** — "지금 확장됐나"로 판정하면 zoom 1 에서 닫혀 줌아웃 시작 rebuild 가 영구히 안 걸리는 **self-lock** 이 된다 |

**작성자 판단 정정(정직 기록)**: "박스 위로 팔출 = reflow 0 이니 안전" 이라는 최초 판단은 **자기 멤버 영역만 본
불완전한 판단**이었다 — *이웃 블록* 과 *hit 영역* 을 검토하지 않았다. 최종 설계는 **hit 영역(칩)은 구조적 한계로
묶고 텍스트만 자유롭게** 두는 분리이며, "라벨은 hit 대상이 아니다" 라는 코드 사실이 그 분리를 가능하게 했다.

**수정 전 재현 확인**: 상한 제거판 번들로 K2·K3·K7 이 실제로 FAIL(칩 높이 52/52/42/52/46/46 · 이웃 블록 침범 ·
CATH 60/30) — 테스트가 결함 자체를 잡는지 검증했다.

**억제 시작 줌 수치(6절 표)는 불변**이다 — 상한이 걸린 것은 알약 크기(hit 영역)뿐이고 폰트는 그대로다.

#### 9. Environment: Windows-browser — PRE-COMMIT 라이브 미수행 사유 / POST-DEPLOY 계획

정적 자산(`static/graph/*.js`)이 web 이미지에 baked 되므로 merge + `deploy-web` 후에만 서빙 자산 실측이 가능하다.
본 변경은 **줌 의존 렌더 기하**라 실 브라우저 카메라가 필요하고, 헤드리스는 방출 계약만 고정한다.

**POST-DEPLOY PB-0008 (HF.6)**: ① 컨텐츠 카테고리 헤더가 개요 줌에서 판독 가능 ② 제품 카테고리 밴드 헤더 동일
③ 칩이 멤버 영역을 침범하지 않음(reflow 0 육안) ④ 줌 왕복 시 폰트 반동이 25% 이내로 따라옴(stale 없음)
⑤ pageerror 0.

- **Pass/Fail: PASS** (PRE-COMMIT 자동검증). CHECK#13 충족 — 라이브 시각검증은 POST-DEPLOY HF.6. Runner: AI.

#### 10. 한계 (정직 표기)

- **`MAX` 상한이 실제 제약**이다. 박스 fit 은 좁은 박스(1열 248px → ~22.6)에서만 바인딩하고, 2열 이상에서는
  `MAX = 64` 가 바인딩한다. 즉 "클러스터 범위만큼"의 개선폭은 **2열 이상에서 포화**한다 — 더 넓은 클러스터가
  더 큰 폰트를 갖지는 않는다. 이는 의도된 절충(칩이 클러스터를 압도하지 않게)이며, 필요하면 상한 파생식의
  `zoomRange` 하한만 바꾸면 된다.
- 폰트 폭 추정계수(0.686)는 기존 코드의 추정치(10.5→7.2 · 12→8.2)를 계승한 값이고 **한글 실폭은 이보다 크다**.
  그래서 `labelMaxWidth` ellipsis 를 안전망으로 둔다 — 폭 계산이 정확해서 안전한 게 아니라, 넘칠 때 잘리도록
  해서 안전하다.
- **제품 개요 뷰(`_metaG6BuildProducts`, `product` 11.5px)는 적용 범위 밖**이다. 사용자 결정이 "위계 헤더
  (컨텐츠 카테고리 + 제품 카테고리 밴드)" 였고, 제품 개요는 별도 build 경로다 — 필요하면 후속 항목.
- 실 렌더 품질(확장 폰트의 실제 판독성·칩 팔출의 시각적 수용성)은 GPU·폰트 렌더 의존이라 헤드리스가 판정할 수
  없다. HF.6 PB-0008 이 담당한다.
- **§8 P1 수정이 남긴 시각 표면**: 텍스트가 칩(알약)을 넘는 구간에서 "알약보다 큰 글자"가 어떻게 읽히는지는
  헤드리스가 판정할 수 없다. 알약 소프트닝으로 '밴드 위 글자'(지도 area-label)로 읽히도록 의도했지만, 실제
  수용성은 HF.6 PB-0008 육안 판정 대상이다 — 만약 어색하다면 대안은 (a) 폰트 상한을 칩 상한에 맞춰 낮추기
  (개선폭 축소) 또는 (b) 텍스트 halo/outline 도입(카토그래피 표준)이다.
