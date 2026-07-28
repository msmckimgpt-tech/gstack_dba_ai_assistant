---
run_at: 2026-07-28T18:11:00+09:00
session: ai/claude-corp/feature-0016-role-badge
scope: unit/feature-0003-agent-web-ui/src/static/graph (graph-roleviz·graph-core·graph-renderer-pixi·graph.css) + static/admin.html
verdict: PASS  # PRE-LANDING 헤드리스 PASS · Windows-browser 시각검증은 POST-DEPLOY(아래 §5 사유)
---

### Run (2026-07-28) — graph-role-badge: 테이블 역할색을 노드 전면 채움 → 좌측 배지 타일 — **Environment: CLI (headless)** + **Windows-browser (POST-DEPLOY 예정)**

> 정본 TASK/DECISION 은 `unit/feature-0016-metadata-graph/docs/TASK.md` `## 20260728T1811-graph-role-badge`.
> 본 파일은 **파일 소유 feature**(feature-0003, static/graph) 쪽 Run 상세다.

#### 1. 사용자 리포트

> `그래프 뷰`에서 다른 노드들의 색상은 모두 정합하게 동일하지만, 테이블 노드의 색상은 역할에 따라 노드 전체의
> 색상이 덮어씌워져서 시각적으로 noisy 합니다. 역할이 설정된 아이콘(이모지) 영역에만 해당 색상을 설정하여 노드 간
> 색상구성이 정합하도록 구성하거나, 웹 리서치를 통해 시각적으로 더 모범적인 구분방법이 있다면 해당 방법으로
> 적용해주세요.

#### 2. 변경 요지

`_metaTableStyle` 의 `fill: rd ? rd.color : Table` → `fill: Table`(항상). 역할색은 신규 `style.roleBadge`
(18×18 라운드 타일 + 아이콘)로 이관하고, 렌더러가 `PixiAdapterPure.roleBadgeCX` 기준 위치에 그린다. 라벨은
배지 몫(22px) 제외 잔여 영역 중앙(`labelOffsetX=11` · `labelMaxWidth=118`), 역할 아이콘은 라벨 인라인에서 제거.

#### 3. 신규 헤드리스 — `tests/headless/test_g6build_rolebadge.js` **47 PASS / 0 FAIL**

```
node tests/headless/test_g6build_rolebadge.js <graph 7모듈 sed 번들> src/static/graph/graph-renderer-pixi.js
```

| 섹션 | 고정한 계약 |
|---|---|
| A (7) | 테이블 본체색 **단일**(`fills.size===1`) = `_META_GRAPH_COLOR.Table` · 전 역할 배지 `{icon,color}` 가 `_META_ROLE` 정본과 일치 · 역할 미배정 노드는 `roleBadge` 부재(무회귀) · **역할 팔레트 8색이 본체 fill 에 미등장**(noisy 원인 제거의 직접 증명) · 팔레트 8색이 배지에 보존(범주 인코딩 무손실) |
| B (8) | 라벨에 역할 아이콘 인라인 **부재** · 라벨 = 테이블명 그대로 · 가용폭 축소량이 전 역할 동일 · `labelOffsetX = round(배지몫/2)` · 라벨색·폰트가 역할과 무관하게 통일(구 `dark` 이원화 제거) · size/radius/stroke 불변 |
| C (2) | col-lod `▤N` 접두(§61)와 역할 배지 **공존** |
| D (7) | label-lod 경계 위 아이콘 유지 / 경계 아래 **아이콘만 소거 + 색 타일 유지** · `roleIconsDropped` 통계 · zoom=1 소거 0(무회귀) · band-invariant(좌표·size·개수 불변) |
| E (5) | 배지가 노드 좌변·높이 안 · **배지 ↔ 라벨 최대폭 무겹침**(-55 ≤ -48) · 라벨 최대폭이 노드 우변 안(70 ≤ 70) · 역할 없는 노드 기하 무회귀 |
| F (9) | hover 확장 카드 — 배지 노드도 확장 대상 · `inner0` = 배지 반영 원 가용폭(t=0 픽셀 동일) · `pad = w - labelMaxWidth`(배지 자리 보존) · 배지 world x = 원 노드 위치 · **배지 오프셋이 라벨 오프셋과 동형**(클램프 시 카드에 실려 이동) · 전 확장 구간에서 배지가 카드 배경 내포 |
| G (6) | **G6 폴백 무회귀** — `roleBadge` 미산출 · 본체 fill = 역할색 · 라벨 인라인 아이콘 유지 · 라벨 폭·오프셋 무변경 · `dark` 라벨색 분기 보존 · 미분석 무회귀 |
| H (2) | 범례 note 가 렌더러를 따라감 — 배지 경로는 정적 문구 유지 / G6 폴백은 문구 교체 |

#### 4. 회귀 — 기존 스위트 전량 무변경 PASS (**22 파일 · 합계 920 PASS / 0 FAIL**)

| 테스트 | 결과 | 테스트 | 결과 |
|---|---|---|---|
| `test_pixi_adapter.js` | 205 | `test_detail_dbgroups.js` | 78 |
| `test_g6build_edge_visibility.js` | 73 | `test_graph_edge_flow.js` | 73 |
| `test_g6build_minimap_reuse.js` | 65 | `test_catcluster_panel_scroll.js` | 65 |
| `test_g6build_rolebadge.js` (신규) | 47 | `test_graph_hover_flow.js` | 41 |
| `test_g6build_labellod.js` | 36 | `test_graph_ancestor_focus.js` | 32 |
| `test_graph_routine_colref.js` | 30 | `test_g6build_category.js` | 26 |
| `test_graph_colnav.js` | 22 | `test_g6build_collod.js` | 20 |
| `test_g6build_layoutmemo.js` | 19 | `test_g6build_vpack.js` | 19 |
| `test_graph_reveal.js` | 17 | `test_g6build_simgroups_p2.js` | 16 |
| `test_g6build_cullrefkeep.js` | 15 | `test_detail_colsel.js` | 9 |
| `test_g6build_agglod.js` | 8 | `test_g6build_viewportcull.js` | 6 |

`node --check`(ESM 복사본) 3파일 SYNTAX OK.

#### 4.1 codex 적대 검증 — P1 1건 + P2 5건 전량 in-cycle 흡수 (최종 pass P1 0)

`codex review --uncommitted`(codex-cli 0.145.0)를 수렴까지 반복. 적발 6건 중 4건이 **정상 경로에서는 보이지
않고 특정 조건에서만 드러나는** 표면이었다 — G6 폴백 렌더러(P1: 역할 표시 전무) · 화면 좌측 가장자리 hover
클램프(배지 카드 이탈) · AI 분석 진행 중(running desaturate 미적용 → 아이콘만 선명) · hover 중 상태 전이
(배지 채도 stale) · 범례 문구의 폴백 부정확. 각 수정은 위 표 G/F/H 섹션 계약으로 고정했다. 상세는
`feature-0016/docs/REVIEW.md` `REV-20260728T181100-…-codex [CODEX:frontend-render+legend]`.

#### 5. Windows-browser 시각검증 — POST-DEPLOY 로 수행 (§15.4.1 · 미수행 사유 명시)

본 changeset 은 **JS 3파일**(`graph-roleviz.js`·`graph-core.js`·`graph-renderer-pixi.js`)을 포함한다. 미머지
상태의 실 브라우저 확인 수단인 `docker cp` 사전 QA 는 **JS 에 대해 성립하지 않는다** — 자산 스탬프(`?v=`)가
빌드 시점에 주입되므로 cp 한 파일은 스탬프 불일치로 `admin.js` 가 이중 인스턴스화되고, Chrome ES module 캐시가
구버전을 계속 실행한다(서버 파일이 신버전이어도). CSS 단독 변경일 때만 안전한 경로다.

따라서 §15.4.1 시각검증은 **PR 머지 → `make deploy-web` → edge `/healthz` git_commit 확인 후 라이브**에서
수행하고, 그 결과를 본 fragment 에 추가 기록한다(TASK RB.8). 검증 시나리오:
① 분석 완료 테이블 칩 본체가 전부 teal 동일 · 좌측 배지에만 역할색 ② 역할 8종 배지 색·아이콘이 범례와 1:1
③ 라벨이 배지와 겹치지 않고 잔여 영역 중앙 정렬 ④ hover 확장 시 배지 정지 + 앞글자 무이동 ⑤ 줌아웃 시
아이콘만 사라지고 색 타일 잔존 ⑥ selected/analyzed/running 테두리가 배지에 가려지지 않음 ⑦ 콘솔 에러 0.
