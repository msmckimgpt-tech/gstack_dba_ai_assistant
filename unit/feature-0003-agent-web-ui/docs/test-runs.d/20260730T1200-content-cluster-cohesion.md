---
run_at: 2026-07-30T12:00:00+09:00
session: ai/claude/feature-0016-content-cluster-cohesion
scope: 그래프 뷰 컨텐츠 클러스터 — 과세분화·배치·상세 패널 부정합 (feature-0016 TASK 20260730T1130-content-cluster-cohesion, 코드 거주 feature-0003 static/graph)
verdict: PASS (라이브 검증 축) · 일부 축 POST-DEPLOY 이월(아래 §5 정직 표기)
---

# Test Run — content-cluster-cohesion 라이브 시각검증 (PB-0008)

- **Environment: Windows-browser** (실 Windows Chrome/150.0.7871.115, WSL 밖)
- **Runner: AI**
- **Bridge:** relay @ `http://172.26.144.1:9233` (전용 인스턴스 — `WIN_BROWSER_CDP_PORT=9232` ·
  `WIN_BROWSER_PROFILE=C:\temp\win-browser-ccc`). ⚠ 기본 포트(9222/9223)의 공용 자동화 프로필에는
  **다른 세션의 탭이 열려 있었다**(`pages[0]` 가 `https://localhost/admin`) — `win-browser.py` 는
  `ctx.pages[0]` 만 사용하므로 공용 프로필을 쓰면 타 세션 탭을 조작하게 된다. 전용 포트+프로필로
  격리해 재수행했다(이 함정은 PB-0008 후속 개선 후보 — REPORT §후속).
- **대상 빌드:** §13.2.9 격리 경로 — 본 worktree 소스로 `web` 이미지 빌드
  (`feature-0016-content-cluster-cohesion-web-a:latest`) → 공유 트리 **무수정**으로 격리 컨테이너
  `web-ccc-verify`(`repo_dbnet` 부착, `:18099` 평문) 기동. 라이브 web-a/web-b·Caddy 무접촉.
- **신 코드 서빙 2중 확인 (assume 금지):**
  1. 이미지 내용 — `_sameSet`×3 · `beOrder, ...baseOrder`×1 · `GB:" + gk`×3 · `hiddenKinds || []`×1
  2. 브라우저가 받은 자산 스탬프 — `/static/graph/graph.css?v=**037ee3fdc2bd**` (= 이 빌드의
     `.asset-stamp`. 라이브 배포본은 `3cb3a58b07bf` 로 상이 → 혼동 불가)

## 1. 시나리오

`mssql-qa-idc`(스키마 137개) → 검색 `DT_GuildMember` → `cc_pyron.DT_GuildMember` 포커스 →
스키마 펼침 → 컨텐츠 카테고리 밴드 좌클릭 → 상세 패널 대조 → 밴드 우클릭 메뉴 → 밴드 접기 3건 → 줌인.

## 2. PASS — 상세 패널↔캔버스 부정합 해소 (R5, 사용자 리포트 2차 증상)

사용자 첨부는 캔버스 `업적 및 인챈트 · 12` ↔ 패널 `업적 2` 처럼 **구성 자체가 다른** 상태였다.

| 관측 | 값 | 판정 |
|---|---|---|
| 패널 그룹 키 네임스페이스 | `mssql-06656002eda6:cc_pyron` (전건 1종) | **PASS** — 종전 `panel:cc_pyron` 이 사라짐 = SSOT 성립 |
| 캔버스 밴드 헤더 ↔ 패널 그룹 (라벨·개수) | 캔버스 `몬스터 데이터 · 18` ↔ 패널 `몬스터 데이터 18` | **PASS** — 라벨·개수 동시 일치 |
| catcluster-scroll fam 대조 | 상태줄 `클러스터: cc_pyron · 테이블 257개 · 함수·프로시저 597개 · **목록을 '몬스터 데이터' 위치로 이동**` | **PASS** — 이 문구는 `_metaGraphFocusPanelGroup` 이 **매칭 헤딩을 찾았을 때만** 나온다(미매칭이면 `graceful no-op` 로 무음). 두 뷰의 그룹 동일성에 대한 직접 증거 |
| 밴드 우클릭 정체 | 배지 `컨텐츠 카테고리` · 헤더 `몬스터 데이터 · 테이블 18` | PASS |

증적: `artifacts/feature-0016-metadata-graph/20260730-content-cluster-cohesion/02-canvas-vs-panel-content-categories.png`
(좌측 캔버스 밴드 헤더와 우측 패널 그룹 목록이 같은 화면에 함께 보인다 — 판독 가능 크기)

## 3. PASS — 행 누락 0 / 총계 정합 (§18.8 codex P1-3 수정 확증)

캔버스 캐시를 조건 없이 재사용하면 패널 멤버(API 응답+모델 Routine)가 캔버스 `gatedTables` 보다 클 때
**행이 조용히 사라지고 총계와 어긋난다**. 멤버 집합 동일 조건부로 좁힌 수정을 라이브에서 확인:

| 지표 | 값 |
|---|---|
| 섹션 총계 `테이블·함수·프로시저 (N)` | **854** |
| 그룹 개수 배지 합 | **854** |
| 실제 렌더된 행(`.amgr-ct-row-li`) | **854** |

3값 완전 일치 → 누락·중복 0.

## 4. PASS — 부작용 없음

- 밴드 접기 3건 → shelf-pack reflow 정상(헤더만 남고 멤버 미방출), 겹침·잘림 없음
  (`03-collapsed-bands-reflow.png`), 줌인 시 밴드 헤더·멤버 칩 판독 정상(`04-zoom-readable-bands.png`).
- 클라이언트 pageerror 0 · 서버 Traceback/500 **0건**(`docker logs web-ccc-verify` grep).
- `__META_GRAPH_PERF` 정상 노출(label·render) — 렌더 파이프 무손상.

## 5. 정직 표기 — 이번 라이브에서 확인하지 못한 축 (POST-DEPLOY 이월)

> 아래는 "미검증"이며 **완료로 오인 보고하지 않는다**(AGENTS.md §16.3 검증 충실도 · §16.6).

- **과세분화 감소(R1) 미관측** — 관측값은 여전히 밴드 **147개 / 854 항목**(평균 5.8), **중복 라벨 13종**
  (`길드 게시판`×2 · `몬스터 가이드`×2 · `이벤트 아이템`×2 · `드롭 아이템`×2 · `변신 시스템`×2 ·
  `캐릭터 정보`×2 …). **이유는 명확하다**: 응집 병합·라벨충돌 병합·`MIN_SIZE` 는 `run_semantic_cluster_pass`
  가 다시 돌 때 `semantic_cluster_id`/`label` 을 재산정하는 것이고, DB 에는 아직 **변경 전 배정**이 들어
  있다(재클러스터 cadence 6h 또는 임베딩 신선도 트리거). 즉 이번 관측은 **수정 전 기준선(baseline)** 이며,
  개선 판정은 배포 후 재클러스터 pass 완료 뒤 같은 지표(밴드 수·중복 라벨 수·`merged_centroid`/
  `merged_label` 카운터)를 재측정해야 한다 → TASK CC.16.
- **MDS 2-D serpentine 배치 효과(R2) 미관측** — 같은 이유(cluster id 가 아직 종전 1-D 체인 산출).
- **접힌 밴드 집계 관계선(R3) 시각 미확증** — 밴드를 접고 reflow·relation 선 존재는 확인했으나,
  선이 **접힌 밴드 헤더에 종단**하는 장면을 판독 가능한 크기로 포착하지 못했다(줌 후 대상 밴드가
  뷰포트 밖으로 이동). §16.6 「캡처 도구 한계 시 escalate, 다운그레이드 금지」에 따라 **PASS 로 선언하지
  않는다**. 현재 근거는 헤드리스 기능 계약 4건(`test_graph_content_cluster_cohesion.js` B2/B3 — 실
  `_metaG6Build` 산출에서 승격 끝점·`aggregated:true`·`count===2`·밴드↔밴드 1선을 단정)이며, 육안 확증은
  POST-DEPLOY 로 이월.
- **be: 밴드 관계 seriation 실동작(R4) 미관측** — `cc_pyron` 의 컨텐츠 밴드 간 FK 관계가 희소해 이 데이터셋
  에서는 의미 seed 순서가 지배한다(설계된 폴백). 관계 주도 재배치 경로는 헤드리스 A2 가 잠근다.

## 6. 정리

- 격리 컨테이너 `web-ccc-verify` 제거 · 전용 브라우저 인스턴스(`:9232`/relay `:9233`) 종료.
- 공유 트리(`repo/`)·라이브 web-a/web-b·Caddy·DB 스키마 **무변경**. 라이브 데이터 쓰기 0
  (그래프 뷰는 읽기 전용 뷰이며 재클러스터를 트리거하지 않았다).
