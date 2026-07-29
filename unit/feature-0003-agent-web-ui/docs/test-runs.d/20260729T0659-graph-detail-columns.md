---
run_at: 2026-07-29T15:59:00+09:00
session: ai/claude/feature-0016-graph-detail-columns
scope: unit/feature-0003-agent-web-ui/src/static/graph/{graph-ctxmenu,graph-state,graph-core}.js — 상세 패널 컬럼 3-소스 병합 + 즉석 introspect 보강
verdict: PASS (유닛 계약 39 + 라이브 데이터 실측 확증 — Windows-browser Run 은 사유 명시 후 POST-DEPLOY 이월)
---

### Run (2026-07-29) — graph-detail-columns: 상세 패널 컬럼 미출력·일부 누락 — **Environment: CLI (라이브 AGE/MSSQL 실측) + headless(node vm 유닛 계약)**

#### 1. 사용자 리포트

> `그래프 뷰` 에서, 테이블 내 포함된 컬럼이 '상세 패널' 에서는 출력되지 않거나 일부 누락되는 이슈가
> 확인되어 수정이 필요합니다.

첨부 스크린샷: `cc_pyron.DT_ItemEnchantInfo` 선택 상태. 캔버스에는 컬럼 40여 개(UniqueID·SocketNum·
EnchantType·FirstModuleID1~8·FirstRate1~8·SecondModuleID1~8·SecondRate1~8 …)가 펼쳐져 있는데, 우측
상세 패널에는 헤더·FQN·"(설명 없음)"·"AI 능동 분석"뿐 — **'컬럼' 섹션 자체가 없다.**

#### 2. 진단 — 라이브 실측 (agent_kb / `metadata_kb` AGE 그래프, 2026-07-29)

컬럼 **소스의 비대칭**이 근본 원인이다. 그래프 `Column` 정점의 SSOT 는 `column_descriptions`
(큐레이션·분석된 컬럼만)이라 미큐레이션 테이블은 `HAS_COLUMN` 이 0 이다.

```sql
SELECT (SELECT count(*) FROM metadata_kb."Table")  AS tables,
       (SELECT count(*) FROM metadata_kb."Column") AS columns,
       (SELECT count(*) FROM metadata_kb."HAS_COLUMN") AS has_column,
       (SELECT count(DISTINCT start_id) FROM metadata_kb."HAS_COLUMN") AS tables_with_cols;
```

| tables | columns | has_column | tables_with_cols |
|---|---|---|---|
| **18,257** | 13,874 | 13,873 | **7,320 (40%)** |

→ 컬럼 정점을 하나라도 가진 테이블이 **40%** 뿐이고, 그나마 테이블당 평균 **1.9** 개다.

리포트 대상 노드(`mssql-06656002eda6:cc_pyron.DT_ItemEnchantInfo`)의 1-hop 엣지 분포:

| 엣지 종류 | 개수 |
|---|---|
| **HAS_COLUMN** | **0** |
| ROUTINE_USES | 0 |
| REFERENCES | 0 |
| HAS_TABLE | 1 |

**대조 — 실 데이터소스의 실제 컬럼 수** (web-a 컨테이너에서 `_graph_resolve_ds_by_scope` →
`INFORMATION_SCHEMA.COLUMNS`, 즉 `/api/admin/metadata/graph/columns` 가 타는 그 경로):

```
ds err: None · engine: mssql
introspect column count: 35
sample: [('UniqueID','bigint'), ('SocketNum','int'), ('EnchantType','int'), ('FirstModuleID1','int')]
```

**그래프 0 vs 실제 35.** 샘플 컬럼명이 사용자 스크린샷의 캔버스 컬럼과 정확히 일치한다 — 캔버스가
그리고 있던 것이 바로 이 즉석 introspect 산출이다.

#### 3. 왜 캔버스만 멀쩡했나 — 폴백의 경로별 비대칭

| 경로 | 진입 | introspect 폴백 | 결과 |
|---|---|---|---|
| `_metaGraphToggleColumns` | 컬럼 펼치기 | **있음** | 캔버스 컬럼 35개 ✔ |
| `_metaGraphExpand` | 더블클릭(관계 확장) | **있음** | 패널 컬럼 표시 ✔ |
| `_metaGraphShowDetail` | **단일클릭(상세)** | **없음** | **패널 컬럼 0 ✘** |

게다가 `_metaGraphRenderDetail` 은 캔버스가 이미 모델에 넣어둔 컬럼조차 보지 않았다 — 같은 함수의
**관계(REFERENCES)** 섹션은 모델 병합 폴백을 쓰고 있었는데(`_metaGraph.edges` 순회) **컬럼에만**
그 폴백이 없던 누락이다. 그리고 `columns.length === 0` 이면 섹션 자체가 렌더되지 않아, 결함인지
"이 테이블은 원래 컬럼이 없음"인지 구분할 단서가 화면에 남지 않았다.

**'일부 누락' 축**: 백엔드 이웃 조회 cap(`_NEIGHBOR_NODE_CAP = 300`)에서 관계 이웃(tier 0)이 계층
이웃(tier 1 = 컬럼)보다 먼저 예산을 먹는다(graph-hop-budget, 2026-07-28). 관계가 많은 테이블은 컬럼이
부분만 남을 수 있고, 그 때 백엔드는 `truncated` 를 신고한다.

#### 4. 수정

1. **컬럼 3-소스 병합**(`_metaDetailMergeColumns`) — ① fetch 응답 `HAS_COLUMN` 이웃(그래프 SSOT,
   큐레이션 설명 보유) ② 모델의 self 소속 `Column`(캔버스에서 펼친 것) ③ 상세 전용 introspect 캐시.
   dedupe 는 **소문자 정규화 key**(큐레이션 입력 vs information_schema 원천의 식별자 case drift),
   앞선 소스 레코드 유지, 정렬 ordinal → 이름.
2. **상세 전용 introspect 보강**(`_metaGraphDetailColsBackfill`, 논블로킹) — 컬럼 펼치기가 쓰는
   `/graph/columns` 엔드포인트·TTL 캐시를 그대로 재사용하되 결과를 **모델에 ingest 하지 않고**
   `detailCols` 에만 적재. 단일클릭 상세는 캔버스 구조를 바꾸지 않는 것이 계약이므로.
3. **보강 게이팅**(`_metaDetailColsBackfillNeeded`) — 컬럼 0 **또는** `meta.truncated` 일 때만,
   테이블당 세션 1회(캐시·실패기록·in-flight 가드 = 렌더↔보강 루프 차단).
4. **empty-state 정직화** — Table 상세는 컬럼 0 이어도 섹션을 렌더하고 "컬럼 조회 중…" 또는 실패
   사유를 표시.
5. **스코프 전환 정합** — `_metaGraphResetModel` 이 `detailCols`/`detailColsMiss`/`detailColsInflight`
   를 함께 clear.

#### 5. §18.8 적대 검증 — codex review P1/GATE 0 · P2 2건 흡수

REV-20260729T065900-graph-detail-columns 참조.

- **P2-1 실패 시 empty-state 고착**: introspect 실패/0건이면 `detailColsMiss` 만 기록하고 재렌더 없이
  빠져나가 패널이 "컬럼 조회 중…" 에 영구 고착 — 사유를 말하겠다는 AC-GDC-3 계약이 정작 실패했을 때
  깨진다. → 성공·실패가 같은 재렌더 경로로 합류.
- **P2-2 같은 키 재선택 race**: 도착 가드가 `lastDetailKey` 뿐이라, 같은 테이블을 다시 눌러 새 상세가
  그려진 뒤 이전 요청이 도착하면 낡은 `nodes/edges/meta` 로 새 패널을 덮어쓴다. → 렌더 세대
  `_detailSeq` + 모델 세대 `_opSeq` **양쪽** 대조.

#### 6. 검증 결과

| 항목 | 결과 |
|---|---|
| 신설 `test_detail_columns.js` | **39 PASS / 0 FAIL** (병합 6축 · 게이팅 4축 · 호출부 계약 7축 · empty-state · reset 정합 · P2 계약 9축) |
| 헤드리스 스위트 전량 | **567 PASS** (baseline main 528 + 신규 39) · 실패 집합 baseline 과 **동일** = 회귀 0 |
| `node --check` | PASS (graph-ctxmenu.js · graph-state.js · graph-core.js) |
| pytest (`make test`) | 신규 실패 0 — 잔여 13건은 baseline(main) 동일 pre-existing(attachment 3파일) |
| ruff | All checks passed |

**정직 표기 — 헤드리스 스위트 상태**: 25개 중 **15개는 pre-existing 실패**다(`test_g6build_*` 12,
`test_detail_colsel.js`, `test_graph_colnav.js`, `test_graph_routine_colref.js`). ITEM-09 의 ES 모듈
분리 이후 구형 하네스(파일 전체 vm-eval)가 `import` 문에서 막힌 것이며 **baseline 에서 동일**하다 —
이번 변경과 무관하고, 하네스 재작성은 본 cycle scope 밖으로 남긴다(REPORT §8 개선 제안).

#### 7. Windows-browser Run 미수행 사유 (§15.4.1 · PB-0008)

본 Run 은 **커밋 전** 검증이다. 검증 대상이 라이브 데이터소스 introspect 왕복에 의존하는 패널 동작이라
로컬 격리 환경에서는 재현 가치가 낮고, 라이브 서버는 아직 main(수정 전) 을 서빙한다. 따라서
`Environment: Windows-browser` Run 은 **배포 후 POST-DEPLOY(GDC.7)** 로 이월한다 — 직전 cycle
(detail-panel-typo · graph-hdr-label-typo)과 동일한 2단 패턴이다.

다만 **수정의 유효성 자체는 라이브 데이터로 이미 확증**했다: 그래프 `HAS_COLUMN` 0 · 실 데이터소스
컬럼 35 · introspect 경로 정상 응답(위 §2). 배포 후 확인할 것은 "그 35개가 패널에 실제로 렌더되는가"
와 empty-state·재렌더 타이밍의 육안 품질이다.
