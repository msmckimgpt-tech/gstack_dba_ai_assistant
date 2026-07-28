---
run_at: 2026-07-28T13:30:00+0900
session: ai/claude/feature-0016-graph-edge-legibility
scope: unit/feature-0003-agent-web-ui/src/static/graph (graph-renderer-pixi·graph-roleviz·graph-core)
verdict: PASS
---

### Run (2026-07-28) — graph-edge-legibility(§84): §83 관계선 재설계의 라이브 육안 검증 → 부정합 3건 개선 — **Environment: Windows-browser**

#### 1. 육안 검증에서 적발한 부정합 (Environment: Windows-browser)

방법: PB-0008 — `bin/win-browser.py`(실 Windows Chrome 150.0.7871.115, CDP relay) → `https://localhost/admin` → 그래프 뷰.
**AI 능동 분석 완료 규모가 큰 데이터소스**를 대상으로 삼았다(사용자 지정) — `node_analysis_runs` 집계로
mssql-web-qa/masangsoftweb 2,574 · mssql-qa-idc/cc_data_main 745·fhgame1 538 · mysql-gz-qa-kr/gunzgame 709 를
확인하고, DB(스키마) 수가 가장 많은 **mssql-qa-idc**(8~34 DB 밴드 6개)를 주 검증 스코프로 사용.

- **F1 (MAJOR) 전체보기에서 관계선이 사실상 비가시** — 굵기가 model 좌표라 world scale(zoom)이 그대로 곱해진다.
  대형 스코프의 fit 은 zoom 0.2~0.55 이므로 0.85px 선이 화면 0.2~0.5px **서브픽셀**이 되고, 안티앨리어싱이
  alpha 까지 깎아 사라졌다. **정량(스크린샷 픽셀 실측, 배경 248)**: 관계선 구간 최대 대비 **27~37/255**
  (대조군 카드 테두리 161), 저밀도 구간 ink **0.12%**. §83 이 노린 "겹칠수록 진해짐" 은 밀집부에서만 성립하고
  **단독 관계선은 존재 자체가 지워지는** 비대칭이 있었다.
- **F2 (MINOR) 곡률 상한이 카드 치수를 초과** — `_META_EDGE_CURVE_MAX=44` 는 접힌 스키마 카드 높이
  (`_METLAY.CARDH=44`)와 같고 행 간격(`GAPY=52`)에 육박해, 호가 이웃 행 카드 위로 부풀어 라벨 영역을 스쳤다.
- **F3 (MINOR) 시각 위계 역전** — AI 분석 완료 표식(보라 halo 3px·불투명)이 관계선(0.85px·α0.32)보다
  3~10배 강해, "분석 상태"가 "관계 구조"를 시각적으로 압도했다. 분석 완료 DB 를 볼수록 두드러진다.

#### 2. 개선

- **F1 → 화면 기준 최소 굵기 보장**(`edgeWidthBoost`, graph-renderer-pixi): 가장 얇은 관계선이 화면에서
  `EDGE_MIN_SCREEN_PX=1.15` 를 갖도록 배율을 산출해 **모든 엣지에 동일 배율**을 곱한다. 개별 clamp 는
  줌아웃에서 굵기 서열(기본<candidate<trusted)을 뭉개므로 기준선 하나로 배율을 뽑아 서열을 보존했다.
  화살촉 상·하한에도 같은 배율을 태워 촉만 사라지지 않게 했다.
- **F1 보조 → alpha 바닥 상향**: 기본 0.32→**0.58**(색도 `#94a3b8`→`#7c8b9e`), candidate 0.5→0.66,
  trusted 0.62→0.8, ROUTINE_USES 0.42→0.62, crossDs 0.52→0.66, SCHEMA_REF 0.3+→0.55+, USES 0.5→0.66.
  **누적 대비는 보존**된다(1겹 0.58 → 2겹 0.82 → 3겹 0.93, 단조 증가·미포화).
  바닥값은 추정이 아니라 **라이브 2회 실측으로 결정**했다 — 1차 시도(α0.44 / 화면 0.85px)는 대비가 44/255 에
  그쳐 불충분했고, 2차(α0.58 / 화면 1.15px)에서 목표 대역에 들어왔다.
- **F2 → 곡률 상한을 카드 치수에 결속**: `_META_EDGE_CURVE_MAX` 44→**26**(카드 높이의 59%·행 간격의 절반),
  계수 0.15→0.13. 왕복 분리 하한(5)은 불변이라 읽기/쓰기 갈라짐은 그대로.
- **F3 → 관계선 강화로 균형**: 분석 완료 halo 는 건드리지 않았다(사용자가 그 표식을 기준으로 탐색하므로
  약화가 의도와 어긋난다). 대신 관계선 대비를 1.9배 올려 위계 격차를 좁혔다.

#### 3. 검증

- **라이브 전후 정량(동일 스코프·동일 fit, 스크린샷 픽셀 실측)**:

  | 구간 | BEFORE 최대대비 | AFTER 최대대비 |
  |---|---|---|
  | 행간 1 | 27 | **51** |
  | 행간 2 | 37 | **55** |
  | 행간 3 | 129 | 129 (이미 카드 테두리 포함 구간) |

  전체보기에서 밴드 간 연결·대각선 흐름이 육안으로 판독 가능해졌고(증거 `vq-08-tuned-fit.png` vs
  `vq-01-qaidc.png`), 확대 시 곡선이 카드 여백 안에 머물며 count 라벨도 읽힌다(`vq-09-tuned-zoom.png`).
  페이지 에러 0.
- **헤드리스**: `test_graph_edge_flow.js` **56 PASS**(§84 신설 A11 4건 — 줌 0.1/0.25/0.55/1 전부 화면 굵기
  바닥 확보 · zoom 2 무보정 · 줌아웃 서열 보존, B2 가시성 바닥 α≥0.55 + 누적 단조·미포화, A4 곡률 상한
  카드 결속). 그래프 전 스위트 **627 PASS / 0 FAIL** · `node --check` 3모듈 PASS.
- 라이브 QA 는 `docker cp` 주입으로 수행하고 **이미지 원본으로 원복 완료**(잔재 grep 0 · `/livez` 200).
