---
run_at: 2026-07-16T01:28:05+09:00
session: ai/claude/feature-0003-graph-cluster-detail-group-hoverpan
scope: 스키마 클러스터 상세 패널의 컨텐츠 카테고리 그룹 헤딩에 hover-pan 추가(행과 동일하게 노드로 팬) — 첫 멤버 노드로 카메라 부드럽게 이동 (20260716T0128-graph-cluster-detail-group-hoverpan)
verdict: 정적 PASS · POST-DEPLOY PB-0008 라이브 DEFERRED
---

### Run 1 — 문법/제어문자 검증 (Environment: node --check, ESM)
- `graph-ctxmenu.js` ESM `node --check` PASS. 단일 파일.
- 소스 리터럴 0x01 잔존 0(`grep -P "\x01"` = clean). 최종 구현은 첫 멤버 노드 key 사용이라 제어문자·String.fromCharCode 불필요(초판 GB-키 접근에서 전환).

### Run 2 — 정적·로직 검증 (Environment: 코드 리뷰)
- **타깃 = 그룹 첫 멤버 노드 key**: 헤딩 `data-pan-key = sg.tables[0].key`. 행 hover-pan(`_metaGraphHoverPan(nodeKey)`)과 동일하게 노드로 팬 → 사용자 "다른 객체와 동일하게" 부합. 첫 멤버는 항상 실 노드라 진입경로(카드클릭 `_metaGraphShowClusterDetailLocal`·콤보/히스토리 `_metaGraphShowClusterDetailById`-API)·fam 정합에 **무관**하게 견고. sim-group 은 캔버스에서 조밀 박스로 팩되므로 첫 멤버로 팬하면 그 컨텐츠 카테고리 영역이 화면에 들어옴.
- **설계 전환 근거(§18.8 적대 리뷰 #1)**: 초판 타깃 = 캔버스 그룹 박스 `GB:comboId+SEP+fam`. 리뷰가 fam 정합을 구조적으로 확증했으나, 콤보/히스토리-뒤로 경로(`ById`, API depth=1 테이블)에서 API↔모델 집합 divergence 시 fam 이 갈려 GB 키 불일치(→ graceful no-op)할 caveat 을 지적. **첫 멤버 노드 전환으로 이 caveat 를 근본 제거**(노드 key 는 fam·경로 무관).
- **미렌더**: 첫 멤버 미렌더(접힘 스키마/컬링) 시 `_metaGraphHoverPan` 의 `_metaRenderedIdFor||_metaRenderedAncestorFor` = null → no-op(행 동형).
- **hover 위임**: `_panTargetOf` = 행(`.amgr-ct-row[data-node-key]`) 우선, 없으면 헤딩(`.amgr-ct-group[data-pan-key]`). 자식(캐럿/라벨/count/trunc) hover 도 `closest` 로 헤딩 승격. `_hoverKey` 로 같은 대상 재-pan 방지(행↔헤딩 전환 시 키 상이 → 정상 재-pan). mouseout 다중 선택자 + `b.contains(relatedTarget)` 로 헤딩 내부 이동 취소 억제.
- **collapse 상호작용**: 헤딩 click=접기토글(data-group-key)·hover=팬(data-pan-key) 이벤트/속성 분리. data-pan-key 는 collapsed 무관 항상 방출 → 접힌 헤딩·모두 접기 후에도 팬.
- 결과 **PASS(정적)** — §18.8 적대 리뷰 상세는 REVIEW.md(REV-20260716T012805) 참조.

### Run 3 — POST-DEPLOY 라이브 시각검증 (Environment: Windows-browser, PB-0008 relay) — **DEFERRED(배포 후 수행)**
- 대상: 재배포 후 컨텐츠 카테고리 다수 스키마(예 DK dk_data_release_main 66그룹) 클러스터 상세 → (1) 그룹 헤딩에 mouseover(200ms 유지) → 카메라가 해당 컨텐츠 카테고리(첫 멤버 노드) 위치로 부드럽게 팬(팬 전/후 스크린샷 뷰 이동 확인), (2) 다른 헤딩으로 이동 시 그 그룹으로 재팬, (3) 행 hover-pan·행 클릭 조회 불변, (4) 접힌 헤딩 hover 도 팬, (5) pageerror 0.
- visual_verification_scope: always — 배포 후 충족 예정. 미수행 사유: 정적 자산 baked 라 web 재배포 후에만 서빙 반영.
