---
run_at: 2026-07-28T13:51:11+09:00
session: ai/claude/feature-0016-graph-edge-screenspace
scope: unit/feature-0003-agent-web-ui/src/static/graph (graph-renderer-pixi·graph-roleviz·graph-core)
verdict: PARTIAL
---

### Run (2026-07-28) — graph-edge-screenspace(§85): 굵기 변성 제거 + 프로시저 관계선 실선·LOD 해제 — **Environment: Windows-browser (굵기 불변·실선 라이브 PASS / 루틴 사용선 육안은 POST-DEPLOY 잔여)**

#### 1. 사용자 리포트 → 근본원인

- **R1 "카메라 줌 수준, 포커스 인/아웃에 따라 관계선의 굵기가 변성"** — 굵기가 model 좌표라 world scale 이
  그대로 곱해진다. §84 의 `edgeWidthBoost` 는 줌아웃 소실만 막으려 `max(1, …)` 로 **바닥만** 걸었고, 그
  결과 임계 줌을 경계로 (a) 화면 고정 구간과 (b) model 고정(=줌 비례 확대) 구간이 갈려 **굵기 거동이 두
  체제로 쪼개졌다**. 확대할수록 선·화살촉·다발이 리본처럼 부푸는 것도 같은 원인(사용자 스크린샷 1).
- **R2/R3 프로시저·함수 관계선** — 줌아웃 LOD 축약 제거 + 점선→실선 + 신뢰도 비례 굵기 (사용자 지정).

#### 2. 수정

- **R1 → screen-space 고정**(`edgeScreenScale = 1/zoom`): style 의 굵기·화살촉·다발 간격을 **화면 픽셀**로
  해석하고 렌더 시 model 로 환산한다. 어떤 줌에서도 두께가 같아 굵기가 오직 **의미(신뢰도·종류)** 만
  인코딩한다(Neo4j Bloom·Gephi·Cytoscape 의 기본 관례). 곡률·다발 오프셋의 *위치* 는 model 기하라 그대로.
  - **줌 재동기화**(`_syncEdgeZoom`): 굵기는 페인트 시점 zoom 으로 bake 되므로 world scale 만 바뀌면 화면
    두께가 다시 흐른다. 줌 변화가 로그 0.22(≈25%)를 넘을 때만 전 엣지 in-place 재페인트(rAF 코얼레싱).
    휠 한 틱마다 전량 재페인트하면 대형 스코프에서 프레임이 무너지고, 임계 내 두께 오차(최대 ±12%)는
    육안 식별이 어렵다. `destroy` 에서 rAF 정리.
- **R2 → ROUTINE_USES LOD 축약 제거**(직접 렌더·집계 두 경로). 축약은 얇은 잔점선이 줌아웃에서 노이즈로만
  남던 시절의 완화책이었는데, 실선+화면 고정 굵기+밀도 누적 전환 후에는 "전체보기에서 루틴 관계가 통째로
  사라지는" 손실이 더 컸다. REFERENCES LOD 는 유지.
- **R3 → 점선 폐지·신뢰도 굵기 단일 축**: ROUTINE_USES `[2,3]`·candidate `[6,4]`·교차DB `[2,4]` 대시를
  모두 제거해 실선화했다. 종전에는 신뢰도가 굵기와 대시 두 채널에 흩어져 "점선 = 무엇"이 중의적이었고,
  얇고 반투명한 선의 대시는 줌아웃에서 점의 나열로 흩어져 관계 자체를 못 읽게 했다.
  굵기 서열(화면 px) = **trusted 1.6 > ROUTINE_USES 1.3 > candidate 1.0 > 교차DB 1.0~1.15 > inferred 0.75**.
  ROUTINE_USES 를 trusted 바로 아래 둔 근거: AGE 속성이 `relation_type`·`cross_ds` 뿐으로 **신뢰도 등급
  자체가 없는 확정 참조**(루틴 본문 파싱)지만, 컬럼-레벨 FK 보다 입도가 거칠다. 종류=색, 방향=화살촉.

#### 3. 검증

- **라이브(주입 QA, mssql-qa-idc)**: 동일 스코프에서 fit / +3 / +6 세 줌 레벨 캡처 후 관계선 세로 런 길이
  분포 실측 — 중앙값 **1.0 / 1.0 / 2.0px** 로 확대해도 선이 두꺼워지지 않는다(+6 의 2.0px 은 확대 시
  얇은 inferred 선이 화면 밖으로 나가고 굵은 trusted·routine 만 남는 구성 변화). 리본 현상 소멸을 육안
  확인(`ss-z0/z3/z6.png` vs 사용자 리포트 스크린샷). 전 과정 페이지 에러 0.
- **헤드리스**: `test_graph_edge_flow.js` **61 PASS** — A11 신규(줌 0.1~4 전 구간 화면 굵기 불변 · model
  굵기 zoom 반비례 · 서열=의미만), A12 신규(줌 재동기화: 최초 1회 · 10% 무시 · 40% 재페인트 · 동일 줌
  no-op), B2(대시 없음 · 신뢰도 굵기 단조), C0(루틴 실선 · trusted 미만 candidate 초과).
  그래프 전 스위트 **632 PASS / 0 FAIL** · `node --check` 3모듈 PASS.
- **잔여(POST-DEPLOY)**: 루틴 노드가 보이는 스코프에서의 사용선 육안(실선·LOD 해제 후 전체보기 표시·
  읽기/쓰기 2선 분리). 캔버스 내부 좌표로 스키마 카드를 펼치는 조작이 필요해 이번 회차에서 확보하지 못했다.
- 주입 QA 는 **이미지 원본으로 원복 완료**(잔재 grep 0 · `/livez` 200).
