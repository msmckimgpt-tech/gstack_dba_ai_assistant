---
doc_type: REVIEW
feature_id: feature-0016-metadata-graph
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260704T075100-ai-claude-feature-0016-graphux7-postdeploy [SKIPPED:doc-only-postdeploy] — graphux7 POST-DEPLOY PB-0008 결과 기록 (코드 무변경)
- 근거: PR #587 병합(325f5de4) → `make deploy-web` 무중단 롤링(web-a/b·soak 90s 통과) 후 실 Windows Chrome PB-0008 라이브 PASS(#1 nav "2/2"·#3 3탭+pg_trgm 제거·#7 "▦ 접기"·#4 Set·#5 라벨·pageerror 0)를 TASK §51.10 [x]·TEST(graphux7 Run POST-DEPLOY)·MODIFY(CHG-…-postdeploy)에 기록. 코드 품질 검증은 원 cycle REV-20260704T071838-graphux7 [SUBAGENT: PASS-WITH-FIXES]에서 완료. 본 커밋은 doc-only.

## REV-20260704T151336-ai-claude-feature-0016-graph-dblclick-stable [SUBAGENT: PASS-WITH-FIXES] — 더블클릭 재배치 순서 안정화(§49) 적대 리뷰 2라운드
- 대상: 그래프 더블클릭 전체 재배치 수정 — 배치 순서 안정화(`_metaStableSeq` + clusterOrder/tableOrder/groupOrder/groupTableOrder).
- 방법: §18.8 적대 리뷰(general-purpose), 8개 결함 클래스 프로브(mutation·ordering·simgroups·leak·threshold·nodePos·fresh-load·재출현).
- 판정: **핵심 로직 correct & safe** — `ids.length=0` mutation(비별칭, terms 항상 마지막)·schemaIdx/relOrder(안정화 후 계산, barycenter 는 신규 테이블에만)·leak 없음(collapse=컬럼만 제거·resetModel clear·_metaStableSeq self-prune)·nodePos 직교(order=base slot, nodePos=절대 델타)·fresh-load 동치(saved=[] → fresh passthrough)·클러스터 재출현 coherent — 전부 clean.
- 확정 residual 2건:
  - **R1(HIGH residual → 수정)**: simgroups(구조화 스키마) 경로가 relOrder 미사용·`_metaSimGroups` 가 그룹/테이블 순서를 매 rebuild 재-seriate → flat 경로만 안정화되고 구조화 스키마 내부 잔여 재배치. **수정**: `_metaSimGroups` 에 동일 `_metaStableSeq`(groupOrder[schemaId]·groupTableOrder[groupKey]) 적용.
  - **R2(MODERATE residual → 문서화)**: `innerColsFor` 임계(7/15/28, 그룹 4/12) 교차 시 열 수 변경으로 해당 클러스터 전 열 재배치 — 반응형 레이아웃 고유. 비파괴·'공간 확보' 성격, 범위 외.
- 미결: 더블클릭 canvas 상호작용 라이브 육안(win-browser CDP 좌표 마우스 미지원·synthetic 히트테스트 미도달 → 사용자 실 마우스 확인).

## REV-20260704T014646-ai-claude-feature-0016-graph-ux3fix [SUBAGENT: PASS-WITH-FIXES] — 3대 UX 개선(§45) 3-렌즈 적대 리뷰
- 대상: CHG-20260704T014646-graph-ux3fix (admin.html/js/styles.css — ① 그래프 뷰 최상위 탭 분리+높이 ③ 검색 soft glow / ② 클러스터 원점 sticky 는 되돌림).
- 방법: §18.8 3-렌즈 병렬 적대 리뷰(general-purpose, 통과 아닌 결함 적발 목적) — (A) 레이아웃 clusterBase, (B) IA/탭/권한 배선, (C) 검색 highlight. 각 렌즈에 diff + 전체 함수 컨텍스트 제공, 실패 시나리오 요구.
- **확정 결함 3건 반영**:
  - **(A-HIGH) 클러스터 원점 sticky 겹침 회귀** — 카드→combo 확장 시 고정된 (작은) 카드 원점을 재사용하면 확장된 combo(폭 256~940·높이 326+)가 이웃 카드(258px pitch·96px row)와 겹침. 카드 개요에서 스키마 펼침=지배적 흐름이고 세션 내 재packing 탈출구 없음 → 다중 스키마 확장 레이아웃 사실상 불가. (C 렌즈도 동일 vertical overlap 독립 지적.) **판정: 되돌림**(요구②는 충돌해소 레이아웃 필요 = 라이브 반복 후속). req①-④ trace·clusterOffset 무중복·first-build 동치·products↔schema reset 은 clean 확인됨(내부 정합은 정상, overlap 부작용이 치명).
  - **(B-MED) 크로스탭 스코프 stale** — 그래프가 별 pane 이 되며 metadataScopeSelect 공유가 끊겨, 다른 탭에서 데이터소스 변경 후 재진입 시 select 값은 갱신되나 canvas 는 이전 스코프(무성 불일치). **수정**: `_metaGraph.loadedScope`·`adminState.metadata.loadedScope` 추적 → 재진입 diverge 시 재로드(양방향).
  - **(C-LOW) 라벨 박스 넘침** — 매칭 노드 폭 고정(rel 부스트 제거)으로 `labelMaxWidth`(176/168)가 박스(150/130)를 초과 → 라벨이 glow 밖으로 흘림. **수정**: `labelMaxWidth` 를 박스 안으로 클램프(TW-10 / 118).
- **clean 판정(각 렌즈)**: dangling ref 0(_metaHideGraph·subTab==="graph"·no-create 잔존 없음)·첫진입/재진입 가시성(pane display)·권한 가시성(graph 전용 역할↔빈 메타탭 방지, group-hide 정합)·landing null-safe·검색 mode 게이팅(neighbor/roots 전환 시 glow 소멸)·G6 shadow state 안전(animation:false 무 To() 크래시, circle 컬럼도 glow)·searchMatchNodes 완전성(백엔드 직접매칭만, false glow 0)·rel 상세배지 유지.
- 리스크·비용: 없음(frontend-only, 비파괴, 인증/데이터/마이그레이션 무변경). 검색 glow 범위가 기존(테이블만)보다 넓어짐(컬럼·용어·스키마명 매칭도) — 개선으로 채택.
- 미결: **PB-0008 실 Windows 시각검증(하드 게이트)** 무인 미수행 → 사용자 육안 후 배포(T45.12/13). ② 후속 cycle.
## REV-20260704T071838-ai-claude-feature-0016-graphux7 [SUBAGENT: PASS-WITH-FIXES] — 그래프 뷰 UX 7건 적대 리뷰 (TASK §51)

- 대상: `git diff 7facb804` 5파일(admin.js/admin.html/styles.css + node_analysis.py/admin_metadata.py) + 신규 test. 범위: 정확성·회귀·통합 결함(스타일 제외). general-purpose 적대 리뷰.
- 결과: **BLOCKING 0** · MAJOR 1(수정) · MINOR 1(수정) · NIT 1(의도대로).
- **MAJOR (수정됨)**: `#1` detail-nav 바가 항상 표시 — `.admin-meta-graph-detailnav{display:flex}` 가 UA `[hidden]{display:none}` 를 덮어 `nav.hidden=true` 가 무력화(이력≤1 숨김 위반). 같은 diff 의 `.amg-legend-panel[hidden]` 는 올바르게 처리했으나 detail-nav 만 누락. **fix**: `.admin-meta-graph-detailnav[hidden]{display:none}` 추가(styles.css:7972, 권한 grid [hidden] 트랩 동형).
- **MINOR (수정됨)**: `#4` in-flight 가드가 스칼라(`_analyzePending`)라 두 노드 교차 분석 시 A 의 finally 가 B 가드를 조기 해제(백엔드 lease-dedup 이 authoritative 라 좁은 창). **fix**: `_analyzePending` 를 `Set` 으로 전환(노드별 독립 add/has/delete, admin.js:3178/6311/6315/6329).
- **NIT (무변경)**: `_analyzePending` 를 poll 전 finally 에서 해제 — 폴링 중 재클릭은 백엔드 dedup(reused)로 "이미 진행 중" 표시. 의도된 프론트/백엔드 계층화.
- 클린 검증(리뷰): #1 이력 타이밍(_histNav 동기 기록·bounds·off-by-one)·#2 단/더블 타이머(더블클릭 시 pan 미이중발화·리스너 미누적)·#3 범례(제거 클래스 dangling 없음·역할 툴팁 selector 유효)·#4 백엔드 progress shape 정합·#5 라벨 null/폴백·#7 comboId 8-arg 위치·undefined 가드·#6 Esc-fix·Phase B/C 필드 비충돌 — 전부 PASS. syntax(node --check·py_compile) PASS.
- 후속: 수정 후 funcproc 테스트 19 PASS(신규 reused-progress 포함). POST-DEPLOY PB-0008 시각검증 잔여(TASK §51.10).

## REV-20260704T043653-ai-claude-feature-0016-crossds-rel [SUBAGENT: SHIP-FOR-INERT / NEEDS-FIXES-BEFORE-FLIP] — Phase B 크로스-데이터소스 관계(§47, ADR-019) 설계+구현 적대검증
- 대상: CHG-20260704T043653-crossds-rel (alembic 0036 + relationships/metadata_graph/node_analysis/insight/frontend).
- 방법(2단계): 설계 워크플로우(ultracode understand6+design2+적대4) + 구현 diff 적대리뷰(general-purpose) 7축(마이그
  mixed-version·scope 매핑·프로브 가드·컨텍스트 제외·추론 정확성·node_analysis 스레딩·프론트).
- 설계검증 확정·수정: CRITICAL revision 충돌(head=0035 → B=0036), migrate-lint 주석 SQL→Python, manual 승격 배선,
  cross_ds 를 neighborhood 까지 스레딩, 컨텍스트 오염 제외 — 전부 구현에 반영.
- 구현검증(SHIP for inert deploy — 데몬 OFF):
  - **SAFE 확인**: 마이그 0036 mixed-version 창 fail-soft(OLD 5-col ON CONFLICT 실패해도 upsert try/except+autocommit,
    caller wrapped, 워커 무크래시·자가치유), 7-col UNIQUE ADD 는 backfill 후 refine(위반 0), intra-ds/794 레거시 scope
    동작 byte-보존, 프로브 가드 완전, 컨텍스트 제외 정확(digest 9→11col 호환), SQL(embedding::text→::vector·kNN) 정상,
    node_analysis cross_ds 컬럼 경로 완전, _enqueue 자기-scope 는 개선(claim 무-scope-filter·anchor 보존), 프론트 G6 안전.
  - **flip-전 수정(반영)**: [MAJOR] MSSQL raw schema_name('dbo')→effective schema(DB명) 미사용으로 크로스-ds 추론이
    MSSQL 에서 컬럼 0건→무산/고아 → `_effective_schema` 로 column-fetch + FQN 정합. [MINOR] apply_relationship_signal
    negative-decay 가 동명 크로스-ds 오염 → intra-ds 가드. [MINOR] reverse-dup(A→B·B→A) → dsk<dsk2 카논화. [MINOR]
    cap 이 scope_key='common' 로 전역 → source datasource_key 기준.
  - 잔여(무해·후속): parent-table cross_ds 완화 dead branch(보수적 under-expand), inferred→trusted 라벨 '[추정]'(보수적).
- 판정: **SHIP(inert deploy)** — 데몬 OFF 라 스키마·UI·scope 완화만 라이브, 마이그 0036 안전. flip-전 블로커(MAJOR+
  MINOR negative-decay) 반영 완료 → AUTO=1 안전. 크로스-ds 라이브 시각확인은 임베딩 populate + AUTO=1 후 이월.

## REV-20260703T160303-ai-claude-feature-0016-semantic-embed [SUBAGENT: PASS-WITH-FIXES] — Phase C 의미 임베딩·클러스터링(§46, ADR-018) 설계+구현 적대검증
- 대상: CHG-20260703T160303-semantic-embed (alembic 0035 + semantic_cluster.py + insight 데몬 + metadata_graph 투영 + 프론트).
- 방법(2단계): (1) **설계 워크플로우**(ultracode: understand 6 + design 2 + 적대검증 4 에이전트) — 마이그 안전성·정확성·비용 6축.
  (2) **구현 diff 적대리뷰**(general-purpose) — 런타임 crash·conn/txn·투영·프론트·MSSQL·워커 6축.
- 설계검증 확정·수정(NEEDS-FIXES → 반영):
  - [CRITICAL] alembic revision 충돌(실제 head=0034_routine_objects) → C=**0035**/B=0036 renumber.
  - [MAJOR] MSSQL 다중 DB 시그니처 오염 → 시그니처에 object_key effective schema(DB명) 포함(DB-distinct).
  - [MAJOR] 프론트 be: namespace 이중적용 → namespace 1회 + ≥2 게이팅 + affix 폴백.
  - [MAJOR] 클러스터 chaining(단일연결 τ) → 노드당 MAX_DEGREE 이웃 상한.
- 구현검증 확정·수정(NEEDS-FIXES → 반영):
  - **[MAJOR-1]** 시그니처 write-key(`_text_hash(sig)`) ≠ texts join-key(`_text_store_insert` 내부 strip) — 컬럼 없는
    테이블 trailing space 로 해시 divergence → 영구 미클러스터(기능 무력화). **fix**: `_text_hash(sig.strip())`.
  - **[MAJOR-2]** un-cluster(→NULL) 시 sync_table None-skip → AGE 정점 stale cluster_id 잔존 → phantom be: 그룹.
    **fix**: `_NULLABLE_PROP_KEYS` + `_props_set` `= null` + sync_table `_UNSET` 센티넬(미전달≠명시 None).
  - **[MINOR-3]** FULLMATRIX_MAX_N/KNN_K dead config(항상 full N×N, 8K scope 256MB OOM 위험). **fix**: N>MAX_N skip→
    affix 폴백 가드 + config 주석 정정(KNN_K=예약).
- SAFE 확인(리뷰어 실측): cursor 재사용/double-close 안전(autocommit·client 버퍼), `_cypher` 10-col 정합·`_unwrap` NULL 처리,
  `_props_set` injection-safe, argpartition k∈[1,n-1], union-find 결정론, 프론트 be: 1회·싱글턴 affix 폴백·labelOf 멤버 라벨,
  MSSQL DB-distinct=_rag_effective 정합, 데몬 fail-soft·tick 무블로킹, 마이그 linear chain·비파괴·카탈로그 전용.
- 판정: **PASS-WITH-FIXES** — MAJOR-1/2 + MINOR-3 반영 후. 라이브 마이그(0035) SAFE(expand-safe·additive). 코드 deploy 저위험
  (kill switch·fail-soft·affix 폴백). 클러스터 값은 eventual(데몬 cadence). 라이브 canvas 는 PB-0008 배포 후 확인.

## REV-20260703T140000-funcproc-esc-hotfix [SKIPPED:minor-1file-live-verified] — popover Esc 고착 hotfix (PB-0008 적발분)
- Related Change: CHG-20260703-funcproc-esc-hotfix (TASK §45 T45.8).
- Panel skip 사유(§18.8 — Minor + 1파일 + 정책 doc 무변경): 5줄 FE 상호작용 수정. 결함 자체가 PB-0008
  라이브 실측으로 적발·재현(620ms 후에도 미닫힘)됐고, 수정 검증도 배포 후 동일 라이브 경로로 재실측한다.
  본체 cycle(graph-funcproc-uxfix)은 직전 REV-20260703T113500 에서 3렌즈 적대 패널 완료.
- Human Approval: deploy_scope: included(전역) — 자동 배포 범위.

## REV-20260703T113500-graph-funcproc-uxfix [SUBAGENT: FIX-THEN-SHIP→PASS] — 함수·프로시저 노드 + 그래프/능동분석 UX 4건 적대 패널 (3렌즈 + MAJOR+ 교차검증, ULTRACODE workflow)
- Related Change: CHG-20260703-graph-funcproc-uxfix (TASK §45, ADR-016·017). worktree feature-0016-graph-funcproc-uxfix.
- 리뷰 방식: Workflow 병렬 3렌즈(backend 정확성 / security·injection / frontend 회귀·G6) 각 독립 발굴 + **BLOCKING/MAJOR 전건을 별도 refuter subagent 가 교차 재검증**(9 agents). staged diff 전체 + 주변 소스·vendored g6.min.js 실측.
- **결과: BLOCKING 1 + MAJOR 5 + MINOR 6 + NIT 3 적발 — 교차검증 전건 real 판정 → 전량 수정 후 재검증 PASS**.
  - **B1(BLOCKING→MAJOR 조정, 수정)**: 루트가 Column 인 run 에서 부모 테이블이 depth 0 으로 same-depth 승격 → depth-0 '하위 컬럼 무조건 통과(rel=1.0)' 규칙이 승격 테이블에 재발화해 전 sibling 컬럼 flood(예산 붕괴·LLM 비용 폭증). → 승격 same_depth 를 `cur_depth > 0` 로 한정(depth-0 자동통과는 실제 루트 전용 보존, 부모는 depth 1 로 분석 + 컬럼은 앵커 게이팅). 회귀 테스트 `test_score_candidates_parent_depth0_not_same_depth`.
  - **M1(수정)**: neighborhood() UNION ALL raw SQL 이 신규 Routine 라벨 테이블을 하드 참조 — 0034 미적용 skew 창(stale 이미지 사례 실재)에서 UndefinedTable 로 **전체 이웃 조회 붕괴**. → `_existing_labels()`(to_regclass 실존 필터) 도입.
  - **M2(수정)**: sync_graph 3b SELECT 실패(0034 미적용)가 owned 배치 트랜잭션을 poisoned 로 만들어 이후 glossary 단계 조용한 실패 + pending MERGE 롤백. → 3b 진입 전 `_tick(force=True)` 강제 커밋 + 실패 시 rollback 복구.
  - **M3(수정)**: ROUTINE_USES 가산적 MERGE 만으로 정의 변경 시 stale 엣지 영구 잔존(REFERENCES broken 클래스 재도입). → sync_routine delete-then-merge(기존 ROUTINE_USES 회수 후 현재 참조 재-MERGE) + introspect 완전 스캔 시 SSOT prune(cap 절단 시 미수행 가드).
  - **M4(수정, FE)**: G6 minimap 컨테이너가 AFTER_DRAW 후 128ms trailing debounce 로 lazy 생성 — post-draw 즉시 anchor 정규화가 요소를 못 찾아 첫 리사이즈에서 REQ ② 재발. → 미발견 시 200ms×4 재시도.
  - **M5(수정, FE)**: 함수·프로시저만 있는 스키마(테이블 0)가 '빈 스키마' 오판 → 영구 펼침 불능(Routine 도달 불가). → 펼침 콘텐츠 카운트에 Routine 포함.
  - **MINOR(전건 수정)**: ⓐ insight cadence 스탬프 조건이 routine 훅 게이트와 불일치(테이블 0 스키마·관계 off 구성에서 매 cycle 재-introspect spin) → 스탬프 조건에 ROUTINE 토글 합류 ⓑ 0034 §4 metadata_kb GRANT 무가드(스키마 부재 시 hard-fail — §3 graceful 과 모순) → pg_namespace 가드 ⓒ 정의 파싱 주석(--,/**/) 유령 참조 → 파싱 전 제거 ⓓ MSSQL alias-UPDATE write→read 오분류 → alias 역참조 write 승격 ⓔ _metaGraphExpand 이웃 자동 펼침에 Routine 미포함(접힌 타 스키마 Routine 비가시) → 포함 ⓕ ctxmenu AI 분석이 stale aiPrompt 암묵 전송 → ctx 경로 지침 미전송(popover 만) ⓖ 검색 badge 분자에 Routine 가산(분모=테이블 총계와 모순 N>M) → 카운트 미가산·강조만 유지 ⓗ LLM user_intent·이웃값 untrusted-data 규칙 명문화(§14 정합) ⓘ analyze docstring 권한 표기 정정.
  - **NIT(수정)**: ROUTINES ORDER BY(cap 절단 결정성)·upsert 카운트 rowcount 기준(무변경 미집계)·관계 상세 containment 에 HAS_ROUTINE 제외·flat-scope Routine 이 term 칩으로 렌더(Routine 분기 우선).
  - 견고 확인(반증 실패) 31건: %s 파라미터 방언 호환(mysql.connector·pymssql pyformat)·__all__ 계약·IS DISTINCT FROM 트리거 비발화·sync_routine 큐레이션 비파괴·jsonb 타입 분기·edge_hits tuple 소비처 정합·insight 훅 비차단·user_prompt autocommit 폴백 안전·Cypher dollar-tag/_cq 방어·XSS esc()/data-rtuse 인용 이스케이프·RBAC 게이트·audit len+preview·400자 서버 cap·run dedupe·클릭/드래그/ctxmenu generic 경로·_metaColParent 비유입 등.
- 재검증: 수정 후 단위 **126 PASS**(신규 19 + 회귀 107) + `node --check`·`py_compile`·migrate-lint PASS.
- Human Approval: Major(비파괴 마이그레이션·사전승인 범위 내) — §16.3 Step 4 조건표(BLOCKED 없음) 따라 자동 동기화 대상. 배포는 deploy_scope: included(전역 선언).
## REV-20260703T101622-ai-claude-feature-0016-graph-freeplace [SUBAGENT: PASS-WITH-FIXES] — 클러스터 자유배치 상호작용 복원(§44) 적대 리뷰
- 대상: CHG-20260703T101622-graph-freeplace (admin.js clusterOffset/nodePos persistence + combo/카드 드래그 핸들러 +
  build 위치 적용, ADR-015, TASK §44).
- 방법: general-purpose 적대 서브에이전트 — 좌표 프레임·offset 수학·drag pairing·getElementPosition 신뢰성·회귀·G6 specifics 6축.
- 확정·수정:
  - **[MAJOR] nodePos 절대좌표가 clusterOffset 를 덮어써 개별배치 노드 분리**: 테이블을 개별 이동(nodePos, 절대)한 뒤
    클러스터를 통째로 옮기면(clusterOffset), 다음 rebuild 에서 그 테이블만 원위치에 남아 클러스터에서 이탈(table-then-cluster
    순서). **수정**: `_metaClusterOffsetAccumulate` 가 클러스터 델타를 소속 노드의 nodePos 에도 동반 가산(`_metaSchemaComboOf`
    매칭). cluster-first 순서는 무영향.
  - **[NIT] 컬럼 드래그가 dead nodePos 엔트리 생성**(build 는 컬럼을 테이블에서 재파생) → `_metaNodeDragEnd` 가 label==="Column"
    노드는 nodePos 기록 제외.
- 검증·SAFE 확인(리뷰어 실측): 좌표 프레임 정합(`getElementPosition`=`[style.x,style.y]`=build tx/ty center → 첫 rebuild 점프
  없음), clusterOffset 가 shelf-packing 폭 누적 미오염(packing 후 가산), 델타-시프트가 테이블+종속(컬럼 colLeftX·"X:" ctl) 정확
  동반, drag start/end pairing 무교차오염(_comboDragStart null-reset + combo/카드/테이블 분리 dispatch, comboId 키 정합), maps
  bounded+resetModel clear, _metaInitGraph idempotent(중복 리스너 0), 제품모드 early-return 무영향, G6 v5.1.1 combo drag 자식이동+
  combo:dragend 발화 확인.
- 알려진 한계(수용): 검색 입력이 자유배치 리셋(model 교체 규칙 — 스코프 내 보존은 후속), 펼친 그룹 스키마의 combo 드래그 표면이
  얇음(GB/GH 비드래그 — 접힌 카드 드래그가 주 경로로 커버), 카드 offset 이 펼침 시 정확 위치 아닌 변위만 유지(결정론 재packing 본질).
- 판정: **PASS-WITH-FIXES** — crash/NaN/데이터손상 경로 0(모든 getElementPosition guard), MAJOR 1 + NIT 1 반영 후 배포 안전.
  라이브 canvas 드래그는 자동화 곤란 → PB-0008 실 Windows 수동 4-상호작용 확인 게이트.

## REV-20260703T091737-ai-claude-feature-0016-graph-product-cat [SUBAGENT: PASS-WITH-FIXES] — 제품 카테고리 개요(§43) 적대 리뷰
- 대상: CHG-20260703T091737-graph-product-cat (admin_metadata.py `_product_overview_graph`/`_products_for_scope` +
  admin.js `_metaG6BuildProducts`/라우팅/노드클릭 + admin.html 툴바, ADR-014, TASK §43).
- 방법: general-purpose 적대 서브에이전트 — diff-only 결함 헌트 5축(정합성 scope_key 브리지·XSS/injection·robustness
  conn=None/dedup·회귀·G6 style 안전).
- 확정·수정:
  - **[MAJOR] scope_key read-axis 불일치**: 헬퍼가 `_dsr.scope_key(ds)`(.env 도 엔드포인트 해시로 계산)를 써서
    그래프 read 축(`admin_datasources.py:70` = `scope_key or key` → **.env=라벨**)과 어긋남 → .env-등록 datasource
    바인딩 제품의 datasource-drill 이 **빈 그래프**, 배너도 미표시. **수정**: 두 헬퍼 모두
    `(ds.get("scope_key") if ds else None) or dsk` 로 전환(dsk=소문자 라벨=`v.key`) → read 축과 byte-정합.
  - **[NIT] 비숫자 `?product=`** 가 전체 제품 반환 → 조건을 `mode=="products" or product.isdigit()` 로 좁혀
    비숫자는 일반 dispatch 통과.
- 기각/SAFE 확인: XSS 0(G6 rect `labelText`=canvas 텍스트·상태배너 `textContent`), SQL/Cypher injection 0(전부
  파라미터라이즈 + products 모드는 PG/Cypher 이전 early-return), 권한 `metadata.graph.read` 보존, conn=None graceful
  (헬퍼 try/except→[], 엔드포인트 503 no-stack-leak), datasource dedup + 엣지 id 재키잉(`src|type|tgt`)로 공유
  datasource 중복 crash 0, `endArrow` 유효·`lineDash` 생략(G6 크래시 회피), `_metaGraphResetModel` 이 mode 미변경
  (products 모드 보존), combo 미부여 노드 = 스키마 카드와 동형(안전). 회귀 0(datasource/schema 경로 무영향,
  common 랜딩만 제품 개요로 대체 — 의존 caller 없음).
- 판정: **PASS-WITH-FIXES** — MAJOR 1 + NIT 1 반영 후 배포 안전(적대 리뷰어 "safe to deploy" 확인, .env fix 적용 조건 충족).

## REV-20260703T105541-graphux6-panelbottom-responsive-obs [SUBAGENT: PASS-WITH-FIXES] — 패널 하단 이동 + 그래프 반응형 높이 + 운영현황 대상 관측 적대 리뷰
- Related Change: CHG-20260703T105541-ai-claude-feature-0016-graphux6-panelbottom-responsive-obs (TASK §37). worktree feature-0016-graphux6-panel-obs.
- 리뷰 방식: subagent 적대 5축 — ① CSS 반응형 회귀 ② 패널이동 부작용 ③ target 계측 정합(자가치유 INSERT·rollback·overview 다중 SELECT·`len(r)>11` 가드) ④ payload 대상 추출·XSS ⑤ 마이그 안전(additive nullable·단일 head·배포순서). diff 전체 + 주변 소스(_record_llm_usage, _query_activity, admin.js 토글/progress, admin.shell→canvas CSS 체인, 0032, 테스트) 정독.
- **결과: BLOCKING 0 · MAJOR 0 · MEDIUM 1 · NIT 4**.
  - ②③④⑤ 전부 견고 확인: params 순서(pt=5·lat=마지막) 보존, pgbouncer rollback→동일커서 재사용 안전(_get_pg_runtime_conn 은 per-call conn), overview 에서 `_query_activity` 는 마지막 쿼리라 rollback 이 선행 결과 무손실(+stale 창에선 오히려 피드 복구), `len(r)>11` 가드로 IndexError 무, payload 키(schema/schema.table/fqn·name) 실측 정합, `str(target).strip()[:200]` 로 VARCHAR(200) 초과 방지, admin.js `E()`(_aiOpsEscApg) XSS 이스케이프, 0032 additive nullable·단일 head(0032→0031→0030)·양방향 배포순서 안전.
  - **MEDIUM M1 (수정 완료)**: ① flex-fill 에서 캔버스 고정높이 하한을 제거해, **width>900px(좁은화면 미디어쿼리 미적용) + 세로 매우 짧은 창**에서 그리드 행 minmax(0,1fr)+min-height:0 캔버스가 0px 로 붕괴 → **G6 빈 캔버스** + wide 모드 pane 스크롤 부재. → **수정**: `.admin-meta-graph { min-height:440px }` 하한 + `.admin-meta-graph-canvas { min-height:200px }` 방어 floor + `:has()` graph-mode pane 세로스크롤을 **전 너비**로 승격(이전 ≤900px 한정). 하한까지 축소 후 초과분은 스크롤 → '빈 캔버스'·'하단 잘림' 둘 다 차단. 정상/큰 화면은 flex-fill 이 pane 을 정확히 채워 overflow 미발생(스퓨리어스 스크롤바 없음).
  - **NIT (수정)**: ⓐ ≤900px 세로스택에서 `.admin-meta-graph { flex:1 1 auto }` 미리셋 → tall-narrow 빈공간 → `.admin-meta-graph { flex:0 1 auto; min-height:0 }` 리셋 추가. ⓑ test_call_llm_records_agent_task mock lambda 가 `target=` 미수용(향후 agent 경로 target 전달 시 TypeError 잠재) → `target=None` 파라미터 추가. ⓒ llm.py INSERT 폴백(target 실패→rollback→base 재INSERT) 무테스트 → `test_record_llm_usage_target_column_absent_fallback` 신규 추가.
  - **NIT (수용/미조치)**: ⓓ `:has()` 는 Chrome<105 등 구형 미지원 — PB-0008 대상 Windows Chrome(현행)은 지원, graceful degradation 이라 수용. ⓔ (기존 결함, 본 diff 무관) 0030+0032 동시 미적용 시 overview #2/#3 쿼리 abort 가 #4 로 전파되는 pre-existing fragility — 본 변경이 악화시키지 않음(정보성).
- Round-2 재검증(CSS M1 보정 집중 subagent, 6축: 스퓨리어스 스크롤바·min-height 과잉·리사이저 드래그·detail-collapsed·≤900px 정합·헤더 스크롤아웃): **BLOCKING 0**. 신규 **MEDIUM**(내가 넣은 `min-height:440px` floor 가 과해 흔한 768급 노트북(가용 ~370-410px)에서 불필요 pane 스크롤 + 그때 헤더·서브탭 스크롤아웃 — 자매 list-detail 뷰와 불일치) 적발 → **재보정**: 그래프 하한 440px **제거**(→`min-height:0` 순수 flex-fill, 흔한 노트북은 스크롤 없이 축소·헤더 유지), '빈 캔버스' 방어는 **캔버스 min-height:200px 만**으로 유지. 스크롤은 캔버스 200px 가 가용높이를 초과하는 ≈<560px viewport(희귀)에서만 발동. **NIT-1**(`[style*="none"]` 부분매칭 취약) → 가드를 `display:none`(authored 무공백)·`display: none`(CSSOM 공백) **이중 :not** 로 정밀화. 잔여(≈<560px viewport 에서 헤더 스크롤) 는 희귀 NIT 로 수용(공유 클래스 sticky 는 상시 그래프뷰에 리스크라 미채택). round-2 는 CSS-only 변경이라 make test 결과 유효.
- Human Approval: 사용자 "continue" 로 작업 진행 승인. 배포(마이그 0032 포함)는 커밋 후 별도 confirm 예정(외부 영향).

## REV-20260702T031500-node-haiku-deploy [SKIPPED: doc-only 배포 기록] — node-analysis-haiku 배포 완수 + 정본 doc-status 갱신
- Related Change: CHG-20260702-node-haiku-deploy (T22.7 배포 완수). 코드/스키마 변경 없음 — 배포 실행(.env + insight-worker 재빌드·재기동) + TASK/REPORT/MODIFY doc-status 갱신뿐.
- Panel skip 사유: 적대 리뷰 대상인 코드 변경(config/llm/node_analysis 라우팅)은 선행 cycle 에서 이미 [SUBAGENT: PASS](REV-20260702T025245) 완료. 본 changeset 은 doc-only + 런타임 배포라 신규 코드 결함면 없음. 배포 정합은 smoke 실증(env 격리·config 값·라우팅 소스·healthy·traceback 0)으로 대체.
- Human Approval: 사용자 "랜딩+배포" confirm 승인(외부 API 비용 인지).

## REV-20260701T220000-ai-claude-feature-0016-graph-perf2 [SUBAGENT: PASS] — 컬럼 결정론 배치(blob/거침) + 줌 적대 리뷰
- Related Change: graph-perf2 (컬럼 정렬 fcose 제약 제거→layoutstop 결정론 배치, 세로 seed, wheelSensitivity 제거, PITCH/nodeSeparation).
- 방식: 진단 워크플로(5에이전트: blob/거침/줌 3렌즈 진단 → 통합설계 → 회귀검증, verdict go-with-fixes) + §18.8 적대 subagent(admin.js 전량 + vendored cytoscape-fcose.js constraint/tile 로직 실측 대조, 7 우려경로).
- 진단(워크플로): blob·거침 **동일 뿌리** — 컬럼 세로정렬을 fcose 제약에 위임 + 전체 테이블 제약을 numIter 1000 동기 tick 적용. fcose 완전 동기(cose-base while-loop, rAF yield 0)라 WebGL(렌더만 GPU화)이 거침 병목과 무관했음이 정합. → 컬럼 정렬을 결정론 코드로 이관해 blob·거침 동시 해소.
- 적대 리뷰 결과: **BLOCKING 0 · MAJOR 0 · MINOR 1 · NIT 3**.
  - **컬럼정렬 공백경로 = 없음**: 그래프 변형 전 진입점(loadRoots·search·expand full-spread/local-relax·cose 폴백)이 모두 동일 layoutstop→placeColumns 로 수렴(전수 확인). 영구 blob 경로 부재.
  - **packComponents/tile = 오히려 안전해짐(긍정)**: vendored fcose L719-742 실측 — 제약 존재 시 `tile=false;packComponents=false` 강제. 이번엔 제약 '키 완전 제거' → constraintExist=false 확정 → full-spread/initial 의 packComponents:true 유효, 과거 '빈 제약이 tile 끔' 취약성 소멸.
  - TDZ/스코프·wheelSensitivity·무게중심 부모위치 보존·batch/endBatch = 전부 안전.
  - **MINOR-1(실측 해소)**: fcose→placeColumns pitch 재확장으로 tall 박스 인접 겹침 여지 → **de-risk 실측으로 PITCH18+nodeSep220 에서 박스겹침 0/7 확인**(하단 참조). 
  - NIT 3: stale 주석 2건(→수정), 스키마-폴백 컬럼(테이블 부재) 정렬 제외 미문서화(기존 동작, 회귀 아님).
- de-risk 실측(실 Windows 브라우저, win-browser): 17컬럼 AchievementReward + 6이웃 ERD 렌더 → **컬럼 x-spread 0.0px(완벽 세로스택·blob 소멸)** + **박스겹침 2→0**(PITCH18/nodeSep220). 스크린샷 render3.png.
- Risks (수정 후): 잔여 BLOCKER/MAJOR 0. node --check PASS. 실 FPS·대규모(141테이블) 박스겹침·줌 체감은 **사용자 실 하드웨어 재확인이 최종 검증**(headless 실 GPU/체감 미측정).
- Human Approval Needed: 없음(프론트 전용·비파괴·deploy_scope: included).
## REV-20260701T233000-ai-claude-feature-0016-node-analysis-anchor-liveverify [SKIPPED:docs-only-live-verification-record-no-code-change] — 라이브 검증 결과 기록(문서 전용)
- Related Change: node-analysis-anchor 배포 후 라이브 실데이터 검증 결과를 ANCHOR §4 / TEST / REPORT / TASK 에 기록. 코드 무변경.
- 방식: 코드 diff 0(문서 전용) → 신규 적대 패널 불요. 기능 정합은 선행 REV-20260701T173000(2라운드 패널, SHIP)에서 확증.
- 기록 내용: alembic 0029 라이브 적용(live=0029)·web-a/web-b 무중단 7bca9b2·insight-worker 7bca9b2 재기동.
  실데이터 프로브(insight-worker 내부, LLM 0) — `dk_data_release.Achievement` 하위 컬럼 4개 rel 1.0 통과 +
  부모 Schema(형제 테이블 **123개**) 탈락 = fan-out 지배 경로 차단 정량 확인.
- Verdict: N/A(문서 기록) — 코드 검증은 REV-20260701T173000 참조. 그래프 UI 마커 시각 최종은 PB-0008 후속.
- Human Approval Needed: 없음(문서·비파괴).

## REV-20260701T210000-ai-claude-feature-0016-graph-webgl [SUBAGENT: PASS] — canvas-2D→WebGL 렌더러 전환 적대 리뷰
- Related Change: graph-webgl (cytoscape 3.30.2→3.34.0, `renderer webgl:_webglOk`+feature-detect 폴백, 엣지 bezier·색/투명도 재설계, anim-hide 전면 제거).
- 방식: §18.8 적대 subagent — admin.js 전량 grep + cytoscape 3.34.0 번들 내부(WebGL 렌더 실코드) 대조 + diff. 7개 우려경로 적대 검증.
- 결과: **BLOCKING 0 · MAJOR 1 · NIT 3**. 우려 6/7 은 코드 근거로 방어 확인:
  - **anim-hide 제거 완전성 = CLEAN**: 잔존 참조 주석 1줄 외 전부 제거(정의부·모든 catch/layoutstop/폴백 대칭 삭제). ReferenceError·죽은 로직 0. node --check PASS.
  - **WebGL 폴백 = 안전**: 번들 확인 — `webgl:false` 면 `initWebgl` 미호출·2D 레이어 유지·render 의 webgl 분기 skip → canvas-2D 그대로 회귀. renderer 객체 형식 3.34.0 수용. feature-detect try/catch 견고.
  - **노드 dashed/double 보더 = 정상 렌더**: WebGL 노드는 2D sprite 캔버스에 그린 뒤 GPU 업로드 → 보더의 `setLineDash`/double 정상. "dashed 미지원"은 엣지 라인에만 해당(노드 무관). node:parent/ai/aiRunning 마커 모두 정상.
  - **_webglOk 스코프 = 정상**: 함수지역·동기참조. cy.destroy/null 부재 + init 가드 → 세션당 1회 계산·1회 사용. 충돌 0.
  - **평행 엣지 dedup = 무효 우려**: 엣지 id=`source|type|target` + getElementById dedup → 동일노드쌍 trusted+candidate(둘 다 REFERENCES type) 공존 불가(id 동일). control-point 제거 겹침 발생 안 함.
- **MAJOR-1 (수정)**: candidate/trusted 가 색(둘 다 갈색군)+투명도+두께로만 구분 → dashed(비색상 채널) 상실로 색맹/저대비 붕괴 + 얇은 candidate(1.3px·0.45) 묻힘 우려. **→ 수정**: candidate 가시성 상향(width 1.3→1.8·opacity 0.45→0.6), trusted 3.2→3.4 로 두께비를 색-비의존 주 구분채널화. 완전한 dashed 등가는 WebGL 제약상 불가(엣지 라인 패턴 미지원) — width/opacity/color 다채널로 완화, PB-0008 저대비 실측 확인 예정.
- 잔여 NIT(기능 회귀 아님, 실측 표시): N1 sprite atlas 는 다장 자동확장(코드 방어)이나 대규모+긴 라벨 실측 필요, N2 다른 type 평행엣지 라벨 겹침(색 구분 OK), N3 WebGL 실험적 기능 의존(zoom≤7.99 kh 경로 정상, maxZoom 2.5) → PB-0008 게이트.
- Risks (수정 후): 잔여 BLOCKER/MAJOR 0. node --check PASS. WebGL 런타임 품질은 **PB-0008 Windows 실브라우저 실측**으로 완료 게이트.
- Human Approval Needed: 없음(프론트 전용·비파괴·deploy_scope: included). **실 FPS 효과 + 저대비 엣지 구분은 사용자 실브라우저 재확인이 유일 검증**.

## REV-20260701T210000-ai-claude-feature-0016-erd-box-spread-tap-deploy-record [SKIPPED:docs-only-deploy-verification-record-no-code-change] — 배포·검증 상태 기록(문서 전용)
- Related Change: CHG-...-erd-box-spread-tap-deploy-record (배포 결과 + PB-0008 라이브 차단 기록, 코드 무변경).
- 방식: 코드 diff 0(문서 전용) → 신규 적대 패널 불요. 기능 정합은 선행 REV-20260701T200000(box-spread-tap, MAJOR 수정 후 SHIP)에서 확증.
- 기록 내용: web 배포 `a6bf0eb`(PR #511, soak 통과), 자산 HTTP 서빙 검증(newAddsBox 3건), 그래프 뷰 UI 로드 sanity PASS.
  **라이브 canvas 인터랙션 PB-0008 은 tool 차단(Chrome 149.0.7827.200/Playwright eval UtilityScript 파손 + canvas 클릭·native select 미지원)** → 사용자 실화면 확인 요망. 코드 정합은 인젝션 실측(886→0)+선행 리뷰로 확증.
- Verdict: N/A(문서 기록) — 코드 검증은 REV-20260701T200000 참조.
- Human Approval Needed: 없음(문서). 단 그래프 인터랙션 최종 시각 확인은 사용자 실브라우저가 정본.

## REV-20260701T200000-ai-claude-feature-0016-erd-box-spread-tap [SUBAGENT: box-spread-tap-adversarial] — 박스 벌림 + 박스 클릭/더블클릭 정합 적대 리뷰
- Related Change: CHG-...-erd-box-spread-tap ((A) 증분 경로 hasCompound 분기+전체-스프레드로 박스 벌림, (B) tap 핸들러 Table 예외로 박스 클릭/더블클릭 일반 노드와 정합).
- 방식: 적대 subagent — admin.js diff + cytoscape/fcose tap·compound·packComponents 의미 교차확인. 두 변경 각각 (a)~(e) 렌즈로 결함 적발.
- 발견 → 처리:
  - **CHANGE 1 (tap 핸들러): 정확.** Table 박스 응답·Schema 컨테이너 무시·target/key 정합(compound-parent id=실 노드 key)·박스↔자식 클릭 시 `_lastTapKey` 리셋으로 오검출 없음·트리플탭 가드 정상. 잔여는 pre-existing MINOR(label 기반 게이팅 결합도, 이미-펼쳐진 박스 더블탭 시 1회 중복 introspect — 둘 다 기존 동작, 이번 변경 무관).
  - **M-MAJOR (CHANGE 2) — `hasCompound` 전체 그래프 스캔 → 과발동**: `_metaGraphColumnConstraints()` 가 전 그래프 Table 을 스캔해, 박스가 하나라도 있으면 **무관한 term/노드 확장까지** 전체-스프레드(고정 없음·전 그래프 이동) 경로로 빠짐 → 국소 relax(앵커 고정) 분기가 사실상 死. 사용자는 "박스 겹침 해소" 를 위한 이동을 승인했지 "모든 확장이 튀는" 것은 아님. **→ 수정**: `hasCompound` 를 **이번 확장의 신규 노드가 박스를 들여올 때**(newIdSet 에 Column 또는 새 compound Table)로 한정. 박스 추가 확장만 full-spread, 순수 노드·term 확장은 국소 relax 유지. `_ccCfg`(컬럼 정렬 제약)는 두 분기 공통 병합 유지라 기존 박스 컬럼 정렬 불변.
  - **m-MINOR (packComponents:true) — 수용(근거 기록)**: `randomize:false` 라도 packComponents 가 비연결 컴포넌트를 재배치해 점프 증폭 가능. 그러나 (1) MAJOR fix 로 full-spread 는 박스 추가 확장에만 발동(빈도 급감), (2) 확장 시나리오는 대개 연결 그래프(이웃 확장)라 packing 영향 미미, (3) 실측 검증된 config(886→0, 109ms)가 packComponents:true 조합 → 미검증 변경 회피. 박스 추가 확장에서 벌림이 목적이라 packing 수용.
  - CLEAN: 동시성 가드(`_layout.stop()`)는 분기 무관 무조건 실행 → 연타 안전. 카메라 focus-fit(focusEles=앵커+신규)은 if/else 밖이라 두 분기 공통 발화 → 전체-스프레드여도 신규 이웃으로 프레이밍(전 그래프 이동 체감 완화). brace/dead-code 없음(local-relax 계산은 else 스코프 내).
- 검증: MAJOR 수정 후 node --check OK. 실측(인젝션) 141테이블 compound 전체-스프레드 박스겹침 886→0, 109ms. 캐시버스터 erd-spread.
- Verdict: **SHIP**(수정 후) — MAJOR 처리, MINOR 수용(근거), CHANGE 1 결함 0. PB-0008 라이브 최종: (a) 밀집 박스겹침 해소 + (b) 박스 클릭/더블클릭 정합.
- Human Approval Needed: 없음(프론트 전용·비파괴·deploy_scope: included). 박스 벌림 이동 트레이드오프는 사용자 사전 승인(AskUserQuestion).
## REV-20260701T173000-ai-claude-feature-0016-node-analysis-anchor [AGENT-TEAM: 2-round backend+qa panel] — AI 능동 분석 재귀 앵커-상대 관련도 게이팅 적대 리뷰
- Related Change: CHG-20260701T173000-...-node-analysis-anchor (재귀를 원래 루트에 고정하는 관련도 게이팅 + alembic 0029 relevance + claim relevance 우선). node_analysis.py/config/migration/tests.
- 방식: §18.8 2라운드 적대 패널. R1 = 단일 backend+qa 리뷰어(전 diff 8차원 적대 probe). R2 = 3-렌즈 병렬 워크플로(wf_739336d8: m1-closure / korean-determinism / regression-integration) — R1 지적 수정본을 재적대검증.
- R1 발견 → 전건 처리:
  - **M1(MAJOR) — 신뢰/제품만으로 무연관 노드 통과**: 같은 scope + trusted REFERENCES 인데 내용(도메인) 무연관 노드가 0.15+0.08=0.23 ≥ MIN 0.18 로 depth1 통과(사용자 "내용 연관 없으면 제외" 침해). **→ 수정**: `_relevance` 를 content-gate 구조로 재작성 — 서브트리/이름/설명/용어(content) 신호가 0 이면 즉시 0.0 반환, 신뢰/제품은 content>0 위 **부스터**로만 작용.
  - **M2(MINOR) — claim relevance DESC 의 depth≥1 run 간 공정성 변화**: root(depth0·rel1.0)는 FIFO 유지라 starvation 무회귀 확인. depth≥1 은 relevance 우선(예산캡·BATCH 로 지연만) — 주석 문서화.
  - **M3(MINOR) — deep 임계 이진 계단**: MAX_DEPTH=5 인데 depth≥2 평탄 0.34. **→ 수정**: `min_rel = MIN_DEEP + 0.06*(nd-2)` 상한 0.7(깊을수록 상향 유지).
  - **M4(MINOR) — 한글/혼합 토큰 미분절**: 업적↔Achievement 미분리·업적⊂업적보상 미인식. **→ 수정**: 한글↔라틴 경계 split + 한글 부분연관.
  - **M5(MINOR) — 예산 절단 비결정성**: 동점 정렬이 입력순 의존. **→ 수정**: ordinal→name 결정 정렬.
  - CLEAN(R1): cursor/txn 안전(`_load_anchor` per-run 캐시·autocommit·예외격리), 마이그레이션 additive·GRANT 테이블단위 커버·인덱스 정합, budget/dedup/finalize 무영향, root 하위컬럼 1.0 무조건.
- R2 발견(수정본 재적대) → 전건 처리:
  - **MAJOR(2R) — M1 한글 경로 재발**: `_GENERIC_TOKENS` 가 라틴 전용 → 한글 일반어(게임/정의/테이블/상태…)가 식별토큰으로 남아 설명 booster 가 generic-only 한글 겹침으로 content 조작(WeaponMaster desc "게임 무기 정의 테이블" → 0.26 통과). **→ 수정**: 한글 일반어·구조어 45+개를 stoplist 에 추가(라틴 목록과 동형). 회귀 테스트 추가.
  - **MINOR(2R) — 한글 임의 부분문자열 오매칭**: 회원⊂비회원구매(반대의미)·업적⊂기업적자(무관)·상태⊂상태이상 등 중간삽입 오연관. **→ 수정**: `_hangul_partial_overlap` 을 **접두/접미 경계**만 인정으로 제한(중간삽입 배제). 부정 테스트 추가.
  - **MINOR(2R) — tiebreak key 누락**: 동명·동점·ordinal무 노드가 DB row order 의존. **→ 수정**: tiebreak 에 node key 최종 성분 추가(전순서). 결정성 테스트 추가.
  - **NIT(2R)** — `_relevance` meta=None 방어(`meta = meta or {}`), broken-guard belt-and-suspenders 주석. 반영.
  - 의도된 트레이드오프(수용): 신뢰 FK 라도 이름/내용 발산 시 제외(precision-over-recall) — 사용자 "내용 연관 없으면 low priority" 정합. 회귀 테스트로 고정.
- 검증: 순수함수 단위 **28/28 PASS**(pytest), py_compile OK. R2 3렌즈 모두 수정 후 SHIP/SHIP-WITH-FIXES(잔여 BLOCKER 0). 200k자 토큰화 34ms(catastrophic backtracking 없음).
- Verdict: **SHIP**(2라운드 수정 후) — BLOCKER 0, R1 M1~M5 + R2 MAJOR·MINOR 전건 처리. 라이브 검증(Achievement 능동분석 fan-out 억제) PB-0008 후속.
- Human Approval Needed: 없음(비파괴 additive·deploy_scope: included). 배포=alembic 0029 + web/insight 재배포.

## REV-20260701T170000-ai-claude-feature-0016-erd-card [SUBAGENT: erd-card-compound-refactor] — 컬럼→테이블 compound(ERD 카드) 적대 리뷰
- Related Change: CHG-...-erd-card (컬럼을 테이블 compound 자식으로 + fcose alignment/relativePlacement 로 박스 안 ordinal 정렬, 겹침 원천 차단). admin.js/admin.html + admin_metadata.py(introspect ordinal).
- 방식: §18.8 적대 subagent — admin.js diff + fcose 벤더 내부 + AGE graph module + graph/columns 엔드포인트 교차확인. BLOCKER/MAJOR/MINOR 적발.
- 발견 → 전건 처리:
  - **M1(MAJOR) — 앵커 compound 미고정 → 뷰 튐**: 증분 relax 의 fixed 빌더가 `isParent()`(=컬럼보유 테이블=compound=앵커)와 Column 을 skip → 앵커가 고정 안 됨. **→ 수정**: 앵커는 parent 여도 fixed 에 포함(`isAnchor` 예외). 컬럼은 제약(alignment/relative) 관리라 fixed 제외 유지(충돌 회피).
  - **M2(MAJOR) — 빈 제약이 fcose tile/packComponents 끔 → 검색·초기로드 노드 흩어짐**: `_metaGraphColumnConstraints` 가 컬럼 0개여도 truthy 객체 반환 → fcose `constraintExist` 참 → tile off. **→ 수정**: 제약 있을 때만 cfg 에 병합(`_ccCfg`, 없으면 `{}`).
  - **m1(MINOR) — introspect 컬럼 ordinal 없음 → ERD 알파벳순**: `graph/columns` 엔드포인트가 Column 노드에 ordinal 미부여. **→ 수정**: `describe_columns`(ORDINAL_POSITION 순) 인덱스를 ordinal 로 부여(admin_metadata.py).
  - **m2(MINOR) — 검색 컬럼(테이블 부재)이 스키마 박스 이탈**: 컬럼 스키마-폴백 시 `_metaEnsureCat` 미호출로 부모 없는 뜬 노드. **→ 수정**: 컬럼 스키마-폴백에도 cat 보장.
  - **M3(오탐)** — "progress/resume 코드 삭제" 는 내 삭제가 아니라 **브랜치가 origin/main 대비 7커밋 뒤처져** 발생한 diff 아티팩트(ab1299c 등이 main 에 후행 추가). origin/main 병합으로 복원 확인(panel.style.display·resume 5건 존재).
  - CLEAN: node --check·2-pass(Table 먼저)·`existing.move` 가드·상세패널 API edges 사용(HAS_COLUMN 그래프 엣지 제거 무영향)·fcose 3제약 공존(컬럼 fixed 제외로 충돌 없음)·compound 드래그 자식 자동 추종.
- 검증: 실측(인젝션) 컬럼 순서 top→bottom 보존·박스 겹침 1쌍·131ms. 수정 후 node --check·py_compile OK. origin/main(camfps/panelmove) 병합(3 hunk 수동 해소: _ccCfg+gen/clearMotionHide 병존, restoreIfCurrent 유지·placeColumns 제거).
- Verdict: **SHIP**(수정 후) — M1/M2/m1/m2 전건 처리, M3 오탐 확인. PB-0008 배포 후 라이브 최종.
- Human Approval Needed: 없음(프론트+introspect 응답 필드, 비파괴, deploy_scope: included).

## REV-20260701T170000-ai-claude-feature-0016-graphux-camfps [SUBAGENT: PASS] — 카메라 애니 프레임레이트 최적화(layoutstop 지연 복원) 적대 리뷰
- Related Change: graphux-camfps (`_metaGraphLayout` layoutstop — 라벨/엣지 숨김 해제를 카메라 fit 애니 complete 후로 지연 + 세대 가드 + 무조건 복원 헬퍼).
- 방식: §18.8 적대 subagent 패널 — cytoscape.min.js/fcose 번들 내부 의미(`stop()`→`layoutstop` 동기 발화, stopped-anim promise 미resolve, fcose `run()` 완전 동기, `cy` 비파괴)를 실측 확인 후 10+ 경로 적대 검증 → **2라운드**(1차 발견 → hardened 재구현 → 재검증).
- 1차 발견 (5건, 전량 수정):
  - **BLOCKING-1/2 — fcose `run()` 예외 시 라벨/엣지 영구 숨김**: addClass 후 fcose try 블록이 throw 하면 cose 폴백으로 빠지는데 폴백엔 복원 코드 부재 → 라벨/엣지 `display:none`/`""` 영구 잔존(새로고침 전 복구 불가, 사용자 회귀 부류). **→ 수정**: fcose outer catch + layoutstop 내부 catch + 폴백 layoutstop + 폴백 outer catch **모든 경로에 무조건 `clearMotionHide()`**.
  - **MAJOR-3 — `!_layoutRunning` guard 고착**: 후속 레이아웃 이중 예외 시 `_layoutRunning` 이 true 로 고착되면 지연 복원이 영구 차단 + dragfree 2차 무력화. **→ 수정**: guard 를 **세대(gen) 토큰 `restoreIfCurrent`** 로 대체 — `_layoutRunning` 상태와 독립. 폴백 catch 가 `_layoutRunning=false` 보장.
  - **MAJOR-2 — 숨긴 지오메트리로 fit → 프레이밍 어긋남**: else 경로가 엣지/라벨 숨긴 채 `cy.fit()`. **→ 수정**: else 는 `clearMotionHide()` **후** fit.
  - **MAJOR-1 — setTimeout 누수**: 취소 안 되는 `setTimeout(restore,650)` 누적. **→ 수정**: `_metaGraph._restoreTimer` 단일 슬롯 + 재설정 전 `clearTimeout`.
- 재검증 (hardened) 결과: **잔여 BLOCKING 0**. 핵심 불변식 확증 — "모든 비동기(지연) 복원은 gen-gated `restoreIfCurrent` 뿐, 무조건 `clearMotionHide()` 는 전부 동기 실행 경로" → 어떤 연타·예외·폴백·스코프전환 조합에서도 라벨/엣지 영구 숨김·깜빡임 재현 불가. 종결 경로(run 예외→catch / run 성공→layoutstop 항상 발화)가 모두 clearMotionHide 로 수렴.
- 잔여 NIT(기능 회귀 아님, 원장 기록): N1 겹치는 cy.animate({fit}) 직렬 큐잉 더블팬(변경 전에도 존재), N2 구세대 _restoreTimer 최대 650ms 후 1회 no-op, N3 gen 정수 증가(오버플로 비현실적).
- Risks (수정 후): 잔여 BLOCKER/MAJOR 0. node --check PASS.
- Human Approval Needed: 없음(프론트 전용·비파괴·deploy_scope: included). **실 FPS 효과는 PB-0008(렌더 정합)로 확인 불가 — 사용자 실브라우저 재측정이 유일 검증**(headless/WSL 은 실 GPU 프레임 미측정).

## REV-20260701T190000-ai-claude-feature-0016-graphux5-panelmove-showfix [AGENT-TEAM: PASS] — 세션 독립 폴 재개 시 진행 패널 미표시 버그
- Related Change: panelmove-showfix (`_metaGraphRenderProgress` 가 `display=""` 직접 설정).
- 방식: 라이브 PB-0008 검증 중 적발 — 세션 독립 재개(fix B) 경로에서 status 바는 "0/1 running" 갱신되나 진행 패널이 populated 되고도 숨김(초기 display:none 미해제). 근본원인: display 해제가 `_metaGraphAnalyze`(버튼) 경로에만 있었음.
- 결과: renderProgress 가 렌더마다 display 해제 → 모든 경로(버튼·재개·다른 탭)에서 표시. 라이브 재검증 예정.
- Verdict: PASS — 버그 근본 수정. 프론트 1줄·비파괴, 회귀 0(버튼 경로 무변).
- Human Approval Needed: 없음. 배포 deploy_scope: included.

## REV-20260701T180000-ai-claude-feature-0016-graphux5-panelmove [SUBAGENT: panelmove-frontend-layout] — 진행 패널 우측 이동 + 세션 독립 진행 표시
- Related Change: graphux5-panelmove (진행 패널을 상단 바 → 우측 상세 aside 상단 이동, detailBody 분리) + 세션 독립 진행 폴링(사용자 후속 이슈: 다른 탭/새로고침 시 진행률·패널·마커 누락).
- 방식: §18.8 집중 프론트 리뷰(Explore) — 6개 결함 카테고리(aside wipe·패널 id·AI 버튼 바인딩·aria-live·토글·레이아웃) 점검.
- 결과: 레이아웃 이동 부분 **CLEAN**(6/6 무결 — 진행 패널 aside 내 정확 타깃, 노드상세만 detailBody 교체, aria-live 정정, 토글이 진행+상세 동시 숨김, clamp+overflow 정상).
- 후속 이슈 수정(세션 독립): `_metaGraphLoadNodeAnalysis` 가 pending/running 노드의 run_id 로 폴링을 자동 재개(activeRunId 미설정 세션도 진행 패널·마커·진행률 표시). 상세는 사용자 라이브 검증 시.
- Verdict: PASS — 레이아웃 결함 0. 세션독립 수정 후 재검증.
- Human Approval Needed: 없음(프론트 전용·비파괴). 배포 deploy_scope: included.

## REV-20260701T160000-ai-claude-feature-0016-graphux5-progress [AGENT-TEAM: PASS] — AI 능동 분석 진행 현황 라이브 패널 적대 리뷰
- Related Change: graphux5-progress (get_run_status jobs/running_keys + 진행 패널 `_metaGraphRenderProgress` 라이브·상세 + 분석중 주황 마커).
- 방식: §18.8 적대 패널 — Workflow 2렌즈(backend/frontend) 병렬 → 발견 8건 → 발견별 적대 검증 → 확정 7건.
- 결과 (확정 7건 전량 수정):
  - **MEDIUM — jobs LIMIT 400 이 done_keys/running_keys 절단**: node_budget 최대 1000(MAX_BUDGET)이라 400 초과 run 에서 그래프 마커 키가 truncate → tail 노드 미표시. **→ 수정**: done/running 키는 **cap 없이 별도 조회**(키만), jobs 상세 리스트만 LIMIT 80(패널 표시분).
  - **LOW ×6**: (a) docstring alembic 0026→0028 정정, (b) 폴 중단(캡 도달/재시도 소진) 시 주황 마커 잔존 → 종료 경로에서 `_metaGraphMarkRunning([], done)` 정리 + 안내, (c) 진행 패널 aria-live 매 틱 전체 재낭독(SR 스팸) → aria-live/role 제거(status 바가 짧은 요약 담당), (d) st.status class 속성 보간 → 화이트리스트 class 맵, (e) 노드 재추가 시 주황 마커 미유지 → `_metaGraph.running` Set 로 보라 마커와 동형 유지. 전량 수정.
- Verdict: PASS — 확정 결함 잔여 0(수정 후 py_compile·node --check 재검증 PASS). 라이브 검증은 PB-0008 배포 후.
- Human Approval Needed: 없음(비파괴 additive UI + 응답 필드, DB/마이그레이션 무변경, 기존 RBAC). 배포 deploy_scope: included.

## REV-20260701T140000-ai-claude-feature-0016-graphux-expand-relax [SUBAGENT:expand-relax-frontend-perf] — 더블클릭 확장 relax 적대 리뷰
- Related Change: CHG-20260701T140000-graphux-expand-relax (더블클릭 확장 시 신규노드가 주변 노드를 밀어내 겹침 해소).
- 방식: §18.8 적대 패널 1렌즈(frontend/perf/regression/concurrency) — admin.js + vendor cytoscape-fcose 대조. 결함 적발.
- 발견 → 전건 처리:
  - **BLOCKER #1 — numIter 250→400 복귀로 프리즈 완화 커밋(1bb45f3) 무측정 회귀 + repulsion↑ 악화**:
    **→ 수정**: numIter **250 유지**(커밋 수치), repulsion 20000→**16000**(base 12000 대비 완만). **실측**:
    depth-1 확장 49ms, depth-2(120 신규) 153ms — 커밋이 우려한 120~155ms 스파이크 내(재측정으로 무회귀 입증).
  - **MAJOR #2 — 'anchor 만 고정' = 매 확장 전체 재배치·문맥 상실**: **→ 수정**: **국소 relax** — 앵커 +
    반경 R(=160+√newCount·55) **밖 노드는 고정**(원거리 문맥 보존), 반경 안만 자유(밀림). 실측 far 노드
    이동 최소(depth2: far 4중 0 이동). newCount=0 이면 `_metaGraphExpand` 가 애초에 relax 미호출.
  - **MAJOR #3 — anchor 부재/compound/컬럼 시 fixed 비어 전체폭발(fail-open)**: **→ 수정**: 앵커 부재 시
    **신규노드 무게중심**을 relax 중심으로 + 반경 밖 노드가 항상 fixed 에 포함 → fixed 비지 않음(폭발 방지).
  - **MAJOR #6 — dragfree ↔ 진행중 레이아웃 경쟁, 동시성 가드 전무**: **→ 수정**: `_metaGraph._layout` 에
    진행 레이아웃 보관 + 신규 layout 시작 시 `.stop()`(연타 취소), `_layoutRunning` 플래그 + dragfree 는
    실행 중이면 재배치 skip.
  - **MINOR #4 — newIdSet 죽은 인자**: **→ 해소**: 국소 relax 가 newIdSet 으로 신규를 fixed 에서 제외(재사용).
  - **MINOR #5 — 컬럼 lock 생명주기(폴백/비동기 창)**: placeColumns try/catch 재-lock + 동시성 가드로 완화. 잔존 위험 낮음.
  - CLEAN #7 — 단일노드 fixedNodeConstraint + randomize:false 는 fcose API 유효.
- 잔여: depth-2(120 신규) 극단 케이스 minor 겹침 4~17쌍(원래 502 대비 96~99%↓, 시각상 경미) — numIter 250
  유지(perf 우선)의 의도적 trade-off. 라이브 시각검증에서 허용 확인.
- Verdict: **SHIP** (수정 후) — BLOCKER/MAJOR 전건 처리 + 실측 재검증. node --check OK. PB-0008 라이브 최종.
- Human Approval Needed: 없음(프론트 전용·비파괴). 배포 deploy_scope: included.

## REV-20260630-0001 — 적대적 코드 리뷰 (backend+security 렌즈, Phase 1c~4 diff)
- Related Change: feature-0016 커밋 306f19c·bbafb52·08621f0·209e09b·0250fc4 (AGE 그래프 토대~AI tool).
- 방식: §18.8 적대 패널 — Cypher/SQL injection·RBAC·XSS·graceful·migration·logic 6 카테고리 정밀 감사.
- 결과:
  - **BLOCKER B1 — Cypher dollar-quote breakout 인젝션**: `_cypher` 가 본문을 정적 `$$…$$` 로 감싸고
    `execute(f"…")` 에 바인드 파라미터가 없어(simple protocol = 다중 statement 허용), 값에 `$$` 가
    섞이면 외곽 SQL 탈출 → 임의 SQL(DROP/UNION exfil). 도달: search `q`(admin HTTP + AI tool)·node key·
    저장된 description(sync 시 stored injection). **→ 수정**: `_cypher` 가 query 에 없음이 보장되는
    동적 dollar-tag(`$mdgq…$`) 사용 + `_cq` single-quote 이스케이프(이중 방어). 회귀 테스트 추가
    (sentinel DROP 시도 차단 + `$$` 값 무손상 저장·검색) — PASS.
  - MINOR M1(confidence nan/inf → 유효 Cypher 아님): `math.isfinite` 가드 추가. **수정**.
  - MINOR M2(neighborhood 의 key 없는 노드 → phantom None 붕괴): `if not b_key: continue`. **수정**.
  - MINOR M3(`_unwrap` 부분 이스케이프): `json.loads` 디코드(+fallback). **수정**.
  - CLEAN: RBAC(엔드포인트 kb.ingest.manual·읽기전용), XSS(admin.js 전 필드 esc()+style 은 고정 dict),
    graceful degradation(AGE 부재 시 no-op), migration 0025 멱등·SSOT 무손상·role-guard, depth/limit 정수강제.
- Risks (수정 후): 잔여 BLOCKER/MAJOR 0. 라이브(cutover 후) 엔드포인트·UI·AI tool e2e 는 PB-0008 게이트.
- Open Questions: 없음.
- Human Approval Needed: Phase 5 운영 cutover(비가역 prod 이미지 교체) — 사용자 승인 게이트(RUNBOOK-cutover.md).

## REV-20260701T120000-ai-claude-feature-0016-graphux5 [AGENT-TEAM: PASS] — graphux5 그래프뷰 UX 4항목 적대 리뷰
- Related Change: feature-0016 graphux5 (검색 유사도 명시·AI 능동분석 재귀/백그라운드·컬럼 즉석 introspection·이웃깊이 즉시 갱신). 파일: metadata_graph/node_analysis/llm/insight.py, app.py, admin.js/html, styles.css, alembic 0028, config.py.
- 방식: §18.8 적대 패널 — Workflow 로 5렌즈(backend-correctness/security/api-contract/frontend/migration-db) 병렬 리뷰 → 발견 16건 → 발견별 적대 검증(refute-default) → 확정 10건.
- 결과 (확정 10건 전량 수정):
  - **HIGH — stale 'running' 잡 미회수**: 워커 크래시/SIGTERM 시 running 갇힘 → run 영구 미완료 + enqueue dedup 이 그 run 을 계속 재사용 → 재트리거 영구 불가. **→ 수정**: process_pending 시작에 lease(`AGENT_NODE_ANALYSIS_LEASE_SEC`=900s) 초과 running→pending reaper + enqueue dedup 을 `updated_at > now()-lease` run 만 재사용.
  - **MEDIUM — node_budget 비원자 read-modify-write**: 다중 워커/replica 동시 처리 시 예산(LLM 비용) 초과 enqueue. **→ 수정**: `_enqueue_neighbors` 를 run 행 `FOR UPDATE` 트랜잭션으로 원자화(락 보유는 짧음 — LLM 은 밖).
  - **MEDIUM — enqueue 서버 실패 400 오분류**: PG 미가용/enqueue 실패가 4xx. **→ 수정**: 서버 실패 503, 입력오류만 400.
  - **MEDIUM — 폴 단일 오류 시 영구 중단**: 일시 오류 1회로 폴 루프 종료. **→ 수정**: catch 에서 bounded 재시도(≤240).
  - **LOW ×6**: get_run_status 404/503 혼동(폴 재시도로 완화), 중복 폴 취소(`activeRunId`), stale 검색 % 라벨/배지 정리(`lastQuery` gate + relLabel 제거), 컬럼 재-introspect 방지(`introspected` Set + anchorHasCols), 폴 캡 도달 안내, `scope_key` [:96] 절단. 전량 수정.
- Verdict: PASS — 확정 결함 잔여 0(전량 수정 후 py_compile 6파일·`node --check admin.js`·`migrate-lint --base main`(0026 expand-safe) 재검증 PASS). 라이브 e2e(그래프뷰 4항목)는 PB-0008 배포 후.
- Human Approval Needed: 없음(비파괴 추가 alembic 0028·기존 RBAC kb.ingest.manual 재사용, 파괴적/인증 변경 0). 배포는 deploy_scope: included(1줄 게이트 표면화).

## REV-20260701-0002 [SUBAGENT: implicit-edges 적대 패널 §18.8 — security + backend/qa]
- Related Change: feature-0016 implicit-edges (암묵 관계 추론 + 자기교정 강화 엔진). 변경 파일:
  relationships.py·dialects.py·insight.py·metadata_graph.py·alembic 0026·config·admin.js/html/css.
- 방식: §18.8 독립 subagent 2회 병렬 가동 — ① SECURITY(식별자 이스케이프·SQL 파라미터화·Cypher 주입·
  프로브 데이터 노출·XSS), ② BACKEND/QA(강화 수렴·on-conflict 부활 금지·race·마이그레이션 멱등/downgrade·
  그래프 투영 arity·추론 폭주·프로브 임계). 각자 diff 를 정밀 감사, 통과 아닌 결함 적발이 목적.
- SECURITY 결과 (0 BLOCKER, 0 MAJOR, 1 MINOR — 전건 처리):
  - CLEAN: probe SQL 식별자 백틱/대괄호 이중화(주입 불가, 값은 서버측 EXISTS 비교로 리터럴 미interpolate),
    강화/프로브 SQL 전량 `%s` 파라미터화, Cypher 숫자 float+isfinite·문자 `_cq`·라벨/키 화이트리스트·동적
    dollar-tag, 프로브는 COUNT/SUM 집계만 egress(값 미로깅), admin.js 신뢰 배지 Number.toFixed(숫자만)·
    equality 비교(interpolate 없음)·edge_source esc().
  - **MINOR(수정) — 프로브가 `_apply_query_cap` 우회(statement timeout 없음, 운영 DB DoS 우려)**:
    `AGENT_RELATIONSHIP_PROBE_TIMEOUT_MS`(기본 5000) 신설 + MySQL `MAX_EXECUTION_TIME` 힌트 / MSSQL
    `SET LOCK_TIMEOUT` 를 dialect 프로브 SQL 에 주입, insight 훅이 관통. 단위 테스트 추가.
- BACKEND/QA 결과 (0 BLOCKER, 4 MAJOR, 3 MINOR — 전건 처리):
  - **MAJOR-1(수정) — 비대칭 역전**: 곱셈 감쇠 `w*(1-0.34)` 는 down>up 이 w>0.306 에서만 성립 → 추론 시작
    weight 0.30 이 사는 [0.15,0.306] 에서 틀린 엣지가 오히려 상승(핵심 약속 붕괴). **고정 감산**
    `w -= 0.14`(NEG_STEP > up 최댓값 0.1275)로 전 구간 down>up 보장. 순 하강 확인.
  - **MAJOR-2(수정) — 테스트가 결함 은폐**: 비대칭 테스트가 w=0.5 단일점만 검사. 동작 구간 전체
    (0.30·floor+·0.306·…)로 강화 + "50% 잘못된 양성 섞여도 결국 파단" 시나리오 테스트 추가.
  - **MAJOR-3(수정) — 파단 엣지 그래프 미회수**: MERGE 가산적이라 candidate/trusted 로 투영된 엣지가
    broken 감쇠 후 그래프에 stale 잔존. `delete_relationship` 신설 + sync_graph 가 broken 행마다 그래프
    엣지 삭제 + neighborhood 도 broken 제외(sync 지연 창 방어).
  - **MAJOR-4(수정) — downgrade 실패**: 레거시 CHECK(‘inferred’ 없음) validating 재추가 전에 inferred 행이
    있으면 위반. downgrade 에 `DELETE ... WHERE source='inferred'` 선행 추가.
  - MINOR-1(수정) — apply_relationship_signal SELECT→UPDATE lost-update race: `BEGIN + SELECT … FOR
    UPDATE + COMMIT` 로 원자화(실패 시 ROLLBACK). MINOR-2(수정) — `AGENT_RELATIONSHIP_INFER_CAP` dead
    config: store_inferred_relationships 로 관통. MINOR-3(수정) — FK 승격 시 negative_signals 미리셋:
    on-conflict 에 `negative_signals=0`(권위적 확인이 이전 의심 제거) 추가.
  - CLEAN: INSERT arity 17/17, ON CONFLICT==UNIQUE, 재upsert 파단 부활 없음·감쇠 weight 보존(FK 만 승격),
    sync_graph/neighborhood arity, 마이그 ADD/CHECK/INDEX IF [NOT] EXISTS 멱등, 신규 컬럼 table-GRANT 상속,
    추론 cap(_INFER_CAP·_SHARED_KEY_MAX_OWNERS)로 O(n²) 방지, leaf-name 매칭 정합.
- 검증: 수정 후 단위 38건 PASS(강화 전이·비대칭 전구간·프로브 판정/타임아웃·추론·digest·dialect·onconflict
  불변식) · ruff clean · py_compile 6 · admin.js node --check · 전체 suite collection EXIT=0.
- Verdict: **SHIP** — 잔여 BLOCKER/MAJOR 0(전건 수정). 라이브 e2e(추정 엣지 출현·프로브 강화/파단·시각)는
  cutover 된 AGE 스택에서 human 검증(TASK T6.10 / PB-0008 배포 게이트).
- Open Questions: 없음.
- Human Approval Needed: 프로브가 운영 DB 키 컬럼 실데이터를 read(집계만 egress) — deploy 전 데이터 접근
  정책 확인 권장. `AGENT_RELATIONSHIP_PROBE_ENABLED=0` 으로 프로브만 비활성 가능(추론·관찰 강화는 유지).

## REV-20260701-0003 [SUBAGENT:graphux5-ordinal-column-layout-2panel]
- Related Change: CHG-20260701-graphux5-column-ordinal (컬럼 세로 정렬 + ordinal 투영 + 부드럽게 꺾이는 엣지).
- 방식: §18.8 적대 패널 2렌즈 병렬 — (a) backend/security(injection·SQL·migration·회귀), (b) frontend/ux
  (lock/unlock·좌표·엣지 geometry·bootstrap ordinal 인덱스·회귀). 결함 적발 목적.
- Backend/Security 결과:
  - **injection: CLEAN** — `_props_set` 정수 분기는 `int(v)` 검증 후 `f"{iv}"`(=[0-9-] 만) 렌더라 Cypher/SQL
    본문·dollar-quote 탈출 불가. app.py ordinal 도 int() + bind param. 적대 입력(`"1); DROP GRAPH"` 등) 전부 무해화.
  - **MAJOR(latent) — `update_column_desc` placeholder/param 불일치**: `int()` 예외 시 `ordinal=%s` placeholder 는
    남고 param 미추가 → 개수 불일치로 psycopg 에러. HTTP 경로는 app.py 선-coerce 로 미도달이나 직접 호출 시 결함.
    **→ 수정**: coerce-first 후 성공 시에만 placeholder+param 추가(upsert 와 정합). (kb_metadata.py)
  - **MINOR — `sync_graph` step2 SELECT graceful 미보장**: 마이그 전 DB(ordinal 컬럼 부재)에서 SELECT 실패 시
    잔여 단계(관계/용어) 중단. 다른 단계(0/4/5)와 달리 try/except 부재. **→ 수정**: step2 를 try/except: pass 로 래핑.
  - MINOR(21자리 ordinal → PG int 초과 500): app.py POST/PUT 에 `0<ordinal<=100000` 범위 가드 추가(→ None). **수정**.
  - CLEAN: COALESCE(명시 우선·미제공 보존), 마이그 0026(expand-safe·backfill 파티션·IS NULL 보존·downgrade),
    sync_graph unpack(7:7), search RETURN(ncols=7↔row[6]), 기존 호출부 무회귀.
- Frontend/UX 결과:
  - **MAJOR M1 — Table 드래그 시 locked 컬럼 미추종(주석 불일치)**: `_metaGraphPlaceColumns` 가 layoutstop 에서만
    호출 → 사용자가 Table 드래그하면 컬럼은 고정·엣지만 늘어나 트리 붕괴. **→ 수정**: `cy.on("dragfree",
    "node[label='Table']", _metaGraphPlaceColumns)` 추가 — 드롭 시 컬럼 재정렬로 트리 유지. (admin.js)
  - MINOR N1(다수 컬럼 트렁크 겹침 판독성), N2(REFERENCES 크로스 엣지 자유도↓), N3(incremental 신규 컬럼 일시 흩뿌림
    cosmetic): 기능 결함 아님 — PB-0008 시각검증에서 확인 후 필요 시 taxi geometry 튜닝. 원장 기록.
  - CLEAN: bootstrap ordinal 인덱스(DOM순=describe_columns ORDINAL_POSITION순, 페이지네이션 DOM 보존, 변경행만
    저장해도 전체 idx 정확), HAS_COLUMN 방향(source=Table), 초기 로드 no-op, lock/unlock 정합, curve-style 3.30.2 지원,
    compound 좌표(model 절대좌표·padding 자동확장).
- Risks (수정 후): 잔여 BLOCKER/MAJOR 0. N1~N3 MINOR 는 시각검증 게이트에서 판정. 라이브 e2e 는 PB-0008.
- Open Questions: 없음.
- Human Approval Needed: 없음(비파괴 additive·deploy_scope: included). PB-0008 실 브라우저 시각검증은 완료 hard gate(check #13).

## REV-20260702T003000-ai-claude-feature-0016-graph-g6 [SUBAGENT: PASS-WITH-FIXES] — Cytoscape(WebGL)→AntV G6 v5 엔진 교체 적대 리뷰
- Related Change: graph-g6 (ADR-004). admin.js `_metaGraph*` 엔진 전면 재작성(−762/+476) + admin.html/styles.css. 데이터 API 불변.
- Method: general-purpose subagent 적대 리뷰. BLUEPRINT.md + 전 `_metaGraph*` 블록 + git diff(vs main) + admin.html/styles.css + **vendored g6.min.js v5.1.1 이벤트 디스패치 내부** 교차검증(G6 v5 API 계약 실증).
- Verified (전건 PASS): `node --check` PASS · 제거함수 참조 0(AddElements/Layout/PlaceColumns/OrderedColumns/오버레이 3종/cy/cytoscape/fcose) · **`lineDash:false` 부재**(실선은 키 생략) · element `type` 은 style 형제(combos/tables/terms/ctl/circle 전부) · **setData+draw 만**(render+addNodeData 크래시 경로 없음) · `e.target.id` 이벤트 라우팅 정확(번들 내부 7회 사용) · **combo:click 이 자식 노드 클릭 시 미발화**(디스패처 단일 `${targetType}:click`) · 리스너 누수 없음(그래프 on 은 init 가드 후·DOM 은 bound 게이트) · 모델 리셋 정합(roots/search clear, expand additive) · 11개 DOM id 존재.
- 5개 버그 전부 구조적 해소·미재유발 확인(① toggle=expand-only+ctl only, ② apply(false) no-fit, ③ 오버레이 삭제, ④ _metaNatSort, ⑤ Canvas 벡터).
- Findings:
  - **MINOR-1 (수정 완료)**: 단일클릭 컬럼펼침 타이머(300ms)가 더블클릭 창(320ms)보다 짧아, 빠른 더블클릭이 컬럼펼침+이웃확장 동시발동 가능. → 타이머 340ms 로 상향(창 초과) + 게이트를 `_metaTableHasCols` 단일소스로 통일. harness 재검증(단일=펼침·재클릭=무접힘·ctl=접힘) PASS.
  - **MINOR-2 (수정 완료)**: search/neighbor 가 BLUEPRINT §2 초안의 render()+d3-force 대신 결정론 draw() — **의도적**(force 는 ④ 재유발). `_metaG6Apply` 에 divergence 주석 추가(후속 리뷰어 회귀 방지).
  - **MINOR-3 (수정 완료)**: styles.css `#metadataGraphCanvas position:relative` 의 오버레이 잔여 주석 정리.
  - INFO: `X:` ctl-prefix 충돌은 scope 가 문자 그대로 "X:" 여야만 가능 → 실무상 불가.
  - Edge case 확인 OK: 빈 common scope, search→reset, REFERENCES 엣지 보유 테이블 접기, `__terms__` 클러스터 상세, scalar size circle 컬럼.
- Verdict: **PASS-WITH-FIXES** — CRITICAL/MAJOR 0. MINOR 3건 전부 수정 반영 + 재검증.
- Risks (수정 후): 잔여 0. 완료 hard gate = PB-0008 실 Windows 시각검증(check #13).
- Human Approval Needed: 배포(web 재빌드·라이브 컨테이너 재시작) + commit/push/PR = 외부영향 → confirm.


## REV-20260702T010000-ai-claude-feature-0016-graph-g6b [SUBAGENT: PASS-WITH-FIXES] — 클러스터 다열 masonry + 가변폭 shelf-packing 적대 리뷰
- Related Change: graph-g6b (MODIFY CHG-20260702-graph-g6b). `_metaG6Build` 배치만 변경(masonry + shelf-pack), 나머지 엔진/이벤트/확장/API 불변(REV-20260702T003000 기검증).
- Method: general-purpose subagent focused 리뷰 — diff + 좌표 기하 수치 검증(scratchpad 계산).
- Verified (전건 PASS): `node --check` PASS · **결정론**(Math.random/Date 없음, 최단열 tie-break 좌측 안정, 자연정렬 유지) · **masonry 높이 정합 정확**(itemH = TROW + n*CROW + CDROP + TGAP, 동일 내부열 항목 간 상수 17px 간격, N=1/2/3/5/10 무drift) · **중심좌표 처리 정확**(top→center 변환, 첫 컬럼 offset TROW/2+CDROP+CROW/2) · **엣지케이스 안전**(0테이블 ic=1 유효박스, Math.max PADT seed, innerColsFor 경계 6/7·14/15·27/28, shelf `cx>0` 가드) · **terms 클러스터**(uniform TROW, 29px 여유) · **클러스터 간 73.5px 여유**(무충돌) · 확장/접기/검색 무회귀.
- Findings:
  - **MINOR (수정 완료)**: 최악의 경우(최대길이 컬럼명 168 + 인접 내부열 high-rel wide 테이블 190) 컬럼 라벨이 인접 칩 좌변에 ~6.5px 겹침(텍스트 픽셀만, 히트박스·데이터 무관). → **COLW 214→224** 로 흡수(권고 반영).
- Verdict: **PASS-WITH-FIXES** — CRITICAL/MAJOR 0. 유일 MINOR(라벨 6.5px 겹침) 수정 반영.
- Human Approval Needed: graph-g6b 배포(web 재빌드·라이브 재시작) — deploy_scope: included + 사용자 "배포 진행" 승인.

## REV-20260702T120000-ai-claude-feature-0016-graph-perf-bg [AGENT-TEAM: PASS-WITH-FIXES] — 테이블 노드 펼침 논블로킹 + 성능 최적화 적대 검증 (race/index-drift/layout/cache)
- Related Change: graph-perf-bg (MODIFY CHG-20260702-graph-perf-bg, DECISIONS ADR-005). FE admin.js `_metaGraph*` 논블로킹 파이프라인·O(1) 인덱스·상태 diff·레이아웃 Pass1/2(+215/−51) + BE admin_metadata.py `/graph/columns` TTL 캐시(+65) + admin.html cache-buster. 데이터 API·스키마 불변.
- Method: 다단계 §18.8 — (1) general-purpose subagent **3렌즈 병렬 패널**(race/concurrency · index-drift · layout+cache), 각 렌즈 적대적(결함 적발 목적) + 실 diff·번들/백엔드 교차검증. (2) **5-agent 재검증 워크플로**(각 BLOCKING closed 여부 + 신규 회귀 hunt, structured verdict). (3) loadRoots 가드 **최종 단일 재검증**(reset-vs-reset 전 조합 + 회귀).
- Verified:
  - `node --check admin.js` PASS · `py_compile admin_metadata.py` PASS · leftover 디버그 마커 0.
  - index-drift 렌즈: `colsByTable` 가 steady-state 에서 구 O(N) `_metaTableHasCols` 스캔과 **동치**(20k 랜덤 시뮬 0 불일치). node-cap 300 phantom-expand 는 **기존 동작(회귀 아님)**.
  - layout 렌즈: Pass1(collapsed 배정)/Pass2(real push-down) **오버랩 없음**, `h`=real 높이로 shelf-packer 소비, `innerColsFor` 경계(0/1/6/14/27) 안전.
  - cache 렌즈: BE TTL 캐시 **공유-가변 페이로드 손상 없음**(JSONResponse read-only 직렬화)·**스코프/테넌트 격리 유지**(scope→ds 는 배포전역 레지스트리, 페이로드=물리 스키마)·**권한 우회 없음**(캐시-히트는 `Depends(require_permission)` 해소 후)·축출/ TTL 파싱/빈결과 미캐시 정상.
- Findings:
  - **BLOCKING-1 (수정 완료)**: `_opSeq` 가 heavy op(expand/toggle)에서만 증가, reset/search/scope/loadRoots 경로 미증가 → in-flight expand 가 사용자가 방금 요청한 검색/스코프 화면을 덮어씀(stale 렌더). → `_metaGraphResetModel` 에 `_opSeq++` 추가(search·roots·scope·reset 전부 경유). 재검증 CLOSED.
  - **BLOCKING-2 (수정 완료)**: 같은 race 로 reset 후 stale expand 가 컬럼 ingest → `colsByTable` 포이즌(존재하지 않는 테이블 hasCols=true → 재펼침 영구 차단). → BLOCKING-1 과 동일 수정(stale op 가 ingest 전 seq 체크에서 폐기 — ingest 직전 마지막 await 이후 seq 체크와 ingest 사이 await 없음 확인). 재검증 CLOSED.
  - **BLOCKING-3 (수정 완료)**: seq-mismatch early-return 이 busy 하이라이트 미해제 → 후속 op 가 rebuild 없이 끝나면 busy 영구 잔류. → 모든 seq-mismatch return 이 `_metaSetBusy(key,false,seq)` 선행 + rebuild/reset 이 `_busyKeys.clear()` + off 는 소유(seq 일치) 시만 해제(같은 key 재트리거 시 신 op busy 보존). 재검증 CLOSED(전 종료경로 정리 확인).
  - **BLOCKING-4 (수정 완료)**: `_metaGraphRefreshStates`(2.5s 폴)가 `_metaNodeStates`(busy 미포함)로 fetch 창 도중 busy 제거 + `_metaSetBusy`/`setSelected` 가 `_stateCache` 미갱신(false-negative 우려). → refreshStates 가 `_metaStateSig`(busy 포함) 사용 + 모든 명령형 writer 가 `_metaApplyState` 경유(요소적용·캐시 signature 항상 동기). 재검증 CLOSED(불변식: cache==요소 최종 state).
  - **BLOCKING-5 (재검증서 신규 적발 → 수정 완료)**: `_metaGraphLoadRoots` 가 자기 `await apiFetch` 이후 `_opSeq` 재검 없이 additive ingest → reset-vs-reset(스코프 A 로딩 중 B 전환) 시 A 노드가 B 모델에 병합돼 **혼합-스코프 그래프**. → loadRoots resetModel 직후 `seq` 캡처 + ingest 전 `if(seq!==_opSeq) return`. 최종 재검증: reset-vs-reset 6조합(loadRoots↔loadRoots·loadRoots↔search·scope 전환·reset 버튼·common 분기·↔expand/toggle) **전부 CLOSED**, 첫진입/resize/단일로드 회귀 없음.
  - **NIT (수용 기록, 비-가시회귀)**: ① 동시 다른-key heavy op 시 먼저 끝난 rebuild 의 `_busyKeys.clear()` 가 타 op busy 를 일시 under-show(깜빡임, stuck 아님). ② 후행 `_metaGraphSyncAnalysisMarkers`(loadRoots/search/expand 최종 `_metaG6Apply` 후)가 seq 재검 없이 자체 fetch → **일시 stale 상태텍스트만**(키가 scope-prefixed 라 마커 오적용·구조 오염 없음, 다음 폴에 자가치유). ③ BE 캐시키 `scope_key` 대소문자 미정규화 — 히트율 미세손실(손상/누출 없음). ④ `colsByTable` 불변식이 백엔드 Column key/fqn 부모 불변 계약에 의존(현 backend 준수, 도달 불가). ⑤ `_metaSetBusy` seq==null → -1 sentinel(현 호출부 전부 seq 전달, 방어적 사각).
- Verdict: **PASS-WITH-FIXES** — CRITICAL 0. BLOCKING 5건(4 초기 + 1 재검증 신규) 전부 수정·재검증 CLOSED. NIT 5건 수용 기록.
- Risks (수정 후): 잔여 0(구조/데이터). 완료 hard gate = PB-0008 실 Windows 시각검증(check #13) — 대량 스키마 펼침 무프리즈 + busy 피드백.
- Human Approval Needed: graph-perf-bg 배포(web 재빌드·라이브 재시작) — deploy_scope: included(전역 FIRST_REQUEST) → 자동 배포하되 첫 배포 직전 1줄 표면화.

## REV-20260702T025245-ai-claude-feature-0016-node-analysis-haiku [SUBAGENT: PASS] — 그래프 관계 분석 전용 모델(claude-haiku) 분리 적대 리뷰
- Related Change: node-analysis-haiku (MODIFY CHG-20260702-node-analysis-haiku-model). 전용 `AGENT_NODE_ANALYSIS_MODEL`(기본 `claude-haiku-4`) 신설 + `llm_node_analysis` 라우팅 분리 + `process_pending` 저장 라벨 정합. ~15줄 diff(config/llm/node_analysis + 테스트).
- Method: general-purpose subagent 적대 리뷰 — 실제 파일 Read + config/catalog/routing 로직 실행 검증. 5개 우려축(격리·touchpoint 완결성·haiku create() 정합·폴백 안전·워커 무회귀) 표적 반증 시도.
- Verified (전건 PASS):
  - **격리**: `llm_schema_insight`(1373)·`llm_table_insight`(1410)·`llm_account_insight`(1449) 는 `AGENT_INSIGHT_MODEL or OPENAI_MODEL` 불변, `llm_node_analysis`(1494) 만 전환. 실행 증명: `AGENT_INSIGHT_MODEL=edge` 에서 node analysis=`claude-haiku-4`·insight=`edge`.
  - **touchpoint 완결성**: `_max_tokens_kwargs`·`_temperature_kwargs`·`_get_llm_client`·`_record_llm_usage` 전부 동일 `_insight_model` 변수 사용 — node analysis 모델을 재해석하는 제2 지점 없음. `admin_metadata.py` 는 enqueue/read 만(독립 모델 해석 없음).
  - **haiku 정합**: 카탈로그 실행 — `claude-haiku-4` → `is_allowed=True`·`is_local=False`(Bedrock 티어)·`max_tokens insight=18000`·`supports_temperature=False`(temperature kwarg 미주입=정상). litellm_config.yaml:43 유효 alias + `API_DEFAULT_MODEL`. `node_analysis` taxonomy 등록됨(계측 정상).
  - **폴백 안전**: 공백/whitespace env → `claude-haiku-4`, 빈 문자열이 `model=` 로 도달 불가. terminal fallback `OPENAI_MODEL`(=claude-sonnet-4)도 non-empty.
  - **라벨 정합·무회귀**: 저장 라벨(node_analysis.py:454) 을 라우팅과 동일 순서로 해석 → "gemma 표시·haiku 실행" 불일치 제거. `get_node_analysis` 가 per-job DB 컬럼에서 verbatim readback(point-in-time 스냅샷). 워커 제어흐름(claim/lease/enqueue/finalize) byte-불변, 라벨 2줄만 이동. `process_pending` 이 유일 호출처. test_llm_env_naming.py 10 passed(4 신규 + 6 기존).
- Findings: CRITICAL/MAJOR/MINOR = 0. 전부 INFO(false-alarm).
  - **INFO (수용, 미수정)**: config 기본값이 `model_catalog.API_DEFAULT_MODEL` 참조 대신 리터럴 `"claude-haiku-4"` 하드코딩. cosmetic — 현 영향 없음(값 동일), config→model_catalog import 가 레이어링상 부적절할 수 있어 리터럴 유지.
- Verdict: **PASS** — 차단 결함 0. 명시 범위(그래프 관계 분석만 전환)에 대해 정확·격리·완결.
- Human Approval Needed: `.env` 반영 + insight-worker 재빌드·재기동(외부영향=배포) + commit/push/PR = 사용자 confirm.
## REV-20260702T121500-ai-claude-feature-0016-graph-ctxmenu [SUBAGENT: PASS-WITH-FIXES] — 노드 우클릭 상세 상호작용 적대 패널
- Related Change: graph-ctxmenu (TASK §24 — §13.1 재번호 22→24, MODIFY CHG-20260702T120000). admin.js 우클릭 메뉴 + 관계 상세 패널 + 중심 보기 + styles.css/admin.html. frontend-only, 데이터 API·RBAC 불변.
- Trigger: UI/화면/메뉴 keyword matched (§18.8 표 — UI/버튼/화면 행) → **ux + design** subset dispatch, 이벤트 배선 복잡도로 qa(정확성) 렌즈 추가.
- Method: general-purpose subagent 3인 병렬 적대 리뷰 — diff 전문 + 그래프 블록·기존 함수 실계약 대조 + G6 vendor 번들 이벤트 지원 교차확인(edge:contextmenu 존재 검증) + 디자인 토큰/z-index 전수 + harness 스크린샷 시각 확인.
- Verdicts: ux **CHANGES-REQUESTED**(MAJOR 3·MINOR 9·NIT 3) · design **PASS-WITH-NITS**(MINOR 4·NIT 3) · qa **미완**(subagent 세션 rate-limit 도달 — 아래 검증 한계).
- 흡수한 MAJOR (전건 수정 + harness 재검증):
  - **MAJOR-1 로컬 조인 컬럼 은닉**: 관계 행이 상대 endpoint 만 표기해 같은 대상으로 가는 FK 2개가 동일 행으로 보임 → row 에 앵커 측 컬럼 표기(`customer_id → s1.customers.id`, out/in 대칭). harness C9 PASS.
  - **MAJOR-2 엣지 우클릭 dead zone**: 관계선 우클릭이 무반응 + 기본 메뉴도 차단 → `edge:contextmenu` 바인딩 + `_metaGraphCtxForEdge`(타입·신뢰/추정 w·cardinality·근거 info + 출발/도착 노드 상세 + 관계 상세 진입, 컬럼 엣지는 소속 테이블 앵커). harness H1 PASS.
  - **MAJOR-3 중심 보기 모드 오인**: 1회성 status 뿐이라 부분 그래프를 전체로 오인 가능 + 복귀 경로 불명확 → 캔버스 좌상단 지속 칩 "🎯 중심 보기: <노드> ✕ 전체 보기"(roots 복귀), roots/검색 진입 시 자동 해제. harness D3/D4 PASS. (스냅샷 단위 undo 는 미채택 — 모델 단순성 유지, '전체 보기' 복귀로 충분하다고 판단·기록.)
- 흡수한 MINOR/NIT (수정): focus 시 검색 input 클리어 · 절단 "… 외 N건"(참조함/참조받음/용어) · REFERENCES 외 타입 혼재 시 중립 헤더(나가는/들어오는 관계) · 이웃-이웃 term edge 를 연관 용어가 아닌 주변 관계로 라우팅 · hop chip 을 1회성 depth 인자로(전역 select 오염 제거, `_metaGraphExpand(key, depthOverride)`) · Column 에도 관계 확장(더블클릭 파리티) · 복사 실패 시 textarea 폴백+실패 토스트 · wheel/재렌더(_metaG6Apply) 메뉴 dismiss · Tab=닫기+포커스 복원(메뉴 내부 포커스일 때만)+chip role=menuitem+aria-label · chip-row hover 허위 affordance 제거 · 메뉴 max-height+스크롤 · focus-visible outline · `.amgr-main code` break-all · 메뉴 배지 `.admin-meta-graph-badge` 공용화 · AI hint "관련 노드 자동 분석" · ⧉→📑(tofu 방지).
- 수용(미수정) 기록: 메뉴/패널 배지 표기 언어 차이(메뉴=한글 — 비전문 사용자 대상 의도) · 아이콘 컬러/단색 혼재(기존 관례 ✨/🕸 재사용, tofu 위험 낮음) · relbadge 의미 재사용(시각 무해 NIT) · radius/그림자 하드코딩(인접 블록 관례 정합).
- 검증: 수정 후 `node --check` PASS + WSL-headless-harness **28/28 PASS**(네이티브 우클릭 경로·엣지 메뉴·중심 칩·로컬 조인 컬럼·1회성 hop·회귀 전부) + 콘솔 에러 0.
- 검증 한계: qa(정확성) 렌즈 subagent 가 plan rate-limit 으로 미완 — 단, 해당 공격축(XSS esc/data-key·이벤트 순서·AI 폴링 가드·dismiss 경로·hop select 이중발동)은 ux 렌즈의 "검증 통과 축"과 harness 실측(에러 0·회귀 G1/G2)이 커버. 라이브 최종 확인은 PB-0008(check #13 hard gate).
- Human Approval Needed: 아니오 — 비파괴 frontend 추가, RBAC/API 불변, deploy_scope: included(전역 선언) + §16.3 Step 4 자동 동기화 조건 충족(BLOCKED 0).
## REV-20260702T140000-ai-claude-feature-0016-graph-ctxmenu-pb [SKIPPED:docs-only]
- **cycle**: ai/claude/feature-0016-graph-ctxmenu-pb — graph-ctxmenu(PR #538, REV-20260702T121500) 의 배포·PB-0008 라이브 실측 결과를 정본 문서에 기록(T24.5/T24.6 완료 표시). 코드 무변경.
- **changeset**: feature-0003 `docs/TEST.md`(POST-DEPLOY Run PASS) · feature-0016 `docs/{TEST,TASK,REPORT}.md` · `wiki/{Log,hot}.md` · 본 entry.
- **panel**: SKIPPED — 비정책 doc-only(§18.8 표 첫 행). 실측 자체가 검증(배포 16fc1598 soak PASS·자산 서빙 grep·실 Windows 라이브 상호작용 5종·스크린샷 4매 artifacts).
- **Human Approval Needed**: 아니오 (문서 전용, 코드·배포 산출물 무변경 — 이미 16fc1598 라이브).
## REV-20260702T165800-ai-claude-corp-feature-0016-graph-initview [SUBAGENT: PASS-WITH-FIXES]
- Date: 2026-07-02
- Related Change: graph-initview (MODIFY CHG-20260702T114500-graph-initview, TASK §25). 그래프 뷰 초기 진입
  줌아웃 가시성 개선 — 스키마-우선 진입 + 판독 줌 클램프 + 미니맵/줌툴바/점프.
- Method: 2라운드 적대 검증.
  - R1: general-purpose subagent 적대 코드리뷰(diff 전체 + G6 v5 계약·Cypher 안전·혼합버전·상태기계).
  - R2: 3-렌즈 병렬 workflow(race/state/contract) — R1 수정 델타 자체가 만든 결함 적발 전용.
- R1 Findings: BLOCKER 0 · MAJOR 2 · MINOR 7 · NIT 3 — 전건 수정.
  - MAJOR-1 dead-card(Schema 노드 없는 자동펼침 combo 접기 후 재펼침 불능) → Schema 노드 합성 삽입.
  - MAJOR-2 LoadRoots 세대 가드 부재(빠른 scope 전환 혼합) → 세대 가드(이후 R2 에서 perf-bg `_opSeq` 로 통합).
  - MINOR: 혼합버전 loaded 오염(mode 판별 마킹)·카드 연타 이중 fetch(in-flight 가드)·빈 스키마 상태-렌더
    불일치(비펼침)·scope_schemas cap silent(limit+1 truncated)·silent 자동펼침 truncated 안내 소실(Set 회수)·
    refit focus 점프(focusFirst 분리)·common 점프 stale(FillJump([])). NIT: shelf 상단 돌출(g6b 병합으로 소멸)·
    minimap fallback 잠복(수용 — 번들 교체 시 POC 재검증 전제, 주석 명문화)·카드 클릭 fetch 2회(로컬 상세로 대체).
- R2 Findings: 17건(중복 제거 9) — 전건 반영/해소.
  - **MAJOR stale-base**: 착수 base 가 origin/main 대비 23커밋 뒤(동일 `_metaGraph` 블록을 graph-g6b #533·
    graph-perf-bg #537 이 병렬 재작성, 이후 #538 ctxmenu 추가 정합) → **merge 재정합**(main 판 기준 재적용,
    자체 레이아웃 폐기·masonry 채택, TASK §22→§24→§25 재번호 §13.1).
  - **MAJOR ExpandSchema 세대 미가드**(늦은 이전-scope 응답이 새 모델 오염) → `_opSeq` 편입(클릭=새 세대,
    silent=부모 세대 상속, await 후 불일치 시 ingest 없이 폐기).
  - **MAJOR 합성 노드가 stale 카드 클릭 안전장치 제거** → 진입 scope 가드(현재 scopeKey 소속만 진행).
  - MAJOR(비대칭 가드 search↔roots) → resetModel 의 `_opSeq++` 공유로 해소(검색 reset 이 roots continuation 폐기).
  - MINOR: 빈 스키마 loaded 고착(cnt>0 시만 마킹)·연타 시 빈 로컬상세(성공-게이팅 .then)·실패 후 로컬상세
    (동일 게이팅)·클러스터 상세 총계 모순(table_count override+절단 노트)·집계실패 '테이블 0' 배지(None 강등).
  - LOW-CONF(resetModel 의 lastDetailKey 잔존 → depth-select 교차 scope 확장): **기존(main 동일) 결함으로 판정,
    본 cycle 미도입 — 후속 항목으로 기록**(REPORT §8 성격).
- 검증: 병합 최종본 headless harness **31/31 PASS·에러 0**(dead-card·빈스키마·연타·혼합버전·stale-scope 회귀
  포함) + 라이브 AGE Cypher 실증 + 단위 10 PASS + node --check/py_compile. TEST.md.
- Verdict: **PASS-WITH-FIXES** — 차단 결함 0, R1+R2 지적 전건 수정(수용 2건은 근거 명기).
- Human Approval Needed: 없음(Major 사전 계획 승인 완료) — cycle-final 후 배포는 deploy_scope: included.

## REV-20260702T172500-ai-claude-corp-feature-0016-schema-card-ctxmenu [SUBAGENT: PASS-WITH-FIXES]
- Date: 2026-07-02
- Related Change: schema-card-ctxmenu (MODIFY CHG-20260702T172500, TASK §26). 스키마 카드 우클릭 메뉴 + 카드 라벨 압축(개수→badge).
- Method: general-purpose subagent 적대 리뷰 — diff 전체 Read + G6 badge API(번들 `getBadgesStyle`/`Aw()` 경로)·우클릭 prefix 라우팅·상태 정합·회귀 교차검증.
- Findings: BLOCKER 0 · MAJOR 0 · MINOR 1 · NIT 2.
  - **MINOR (수정)**: node-level `badgeOffsetX/Y` 는 G6 v5 badge 파이프라인에서 무시됨(per-item `getBadgeStyle` 가 아이템 자신의 offset 만 소비) → badge 아이템 객체에 `offsetX/offsetY` 이설.
  - **NIT (주석 반영)**: `_metaGraphCtxForSchema` 펼치기 onClick 의 `st === "already"` 는 SC 경로에서 도달 불가(방어적 잉여, 좌클릭과 대칭) → 주석 명시.
  - **NIT (후속 기록, 본 cycle 범위 밖)**: `_metaGraphShowClusterDetailById` 는 `_opSeq`/scope 세대 가드가 없어 접힌 카드 "클러스터 상세" API 조회 대기 중 scope 전환 시 stale 패널 가능 — **기존 `combo:click` 도 동일 함수를 쓰는 pre-existing 동작**(본 cycle 은 진입점만 추가). 신규 결함 아님 → REPORT §8 성격 후속 항목.
- 검증(수정 후): node --check PASS + harness ctxmenu 10/10 PASS(badge/우클릭/접기/빈스키마·에러 0) + initview 회귀 31/31 PASS + 큰 수(8122) badge 넘침·크래시 없음.
- Verdict: **PASS-WITH-FIXES** — 차단 결함 0, MINOR 수정·NIT 주석 반영, NIT 1 은 pre-existing 후속.
- Human Approval Needed: 없음(Minor §12.3 — frontend-only 비파괴). cycle-final 후 배포는 deploy_scope: included.

## REV-20260702T173000-ai-claude-corp-feature-0016-search-badge [SUBAGENT: PASS-WITH-FIXES]
- Date: 2026-07-02
- Related Change: search-badge (MODIFY CHG-20260702T173000, TASK §27). 검색 시 스키마 카드 badge 매칭/전체 표기.
- Method: general-purpose subagent 적대 리뷰 — diff 전체 Read + schemaTotals 생명주기·집계 정확성·상태 전이·badge 렌더·회귀 교차검증.
- Findings: BLOCKER 0 · MAJOR 1 · MINOR 3(1 LOW-CONF) — 전건 반영.
  - **MAJOR (수정)**: search_nodes cap(_SEARCH_CAP, 프론트 기본 50) 절단 시 매칭 카운트가 부분값인데 `매칭/전체` 를 정확값처럼 표기 → 응답이 cap 도달이면 `_metaGraph.searchCapped=true` + badge 를 `매칭+/전체`(≥) 로, status 에 "결과 상한(부분 카운트)" 안내(roots/expand 의 truncated 안내와 대칭).
  - **MINOR (수정)**: terms-only 매칭(스키마 0)일 때 status 가 없는 카드 클릭을 지시 → `nSchemas===0` 분기 "용어·기타 N개 매칭(해당 스키마 테이블 없음)".
  - **MINOR (수정)**: 스키마 세그먼트 없는 flat scope Table/Column 매칭이 카드·terms 어디에도 안 들어가 소실 → terms 로 폴백 ingest.
  - **MINOR LOW-CONF (수정)**: search tail 에 `_opSeq` 세대 가드 부재 → scope 전환 status 레이스 → resetModel 직후 seq 캡처 후 apply 뒤 `if (seq!==_opSeq) return`(loadRoots 패턴 정합).
- 검증한 비-결함(재확인): schemaTotals scope 키 네임스페이스로 stale 없음, Column→schema 도출 정합, null 가드, Set 중복제거로 Table+Column 이중 매칭 미이중계상, expand-during-search 정합.
- 검증(수정 후): node --check PASS + harness initview 33/33 PASS + ctxmenu 10/10 PASS(에러 0).
- Verdict: **PASS-WITH-FIXES** — 차단 결함 0, MAJOR+MINOR 전건 수정.
- Human Approval Needed: 없음(Minor §12.3 — frontend-only 비파괴). cycle-final 후 배포는 deploy_scope: included.

## REV-20260702T175500-ai-claude-corp-feature-0016-search-badge-pb0008 [SKIPPED: docs-only]
- Date: 2026-07-02
- Related Change: CHG-20260702T175500-search-badge-pb0008 — search-badge PB-0008 라이브 실측 결과의 POST-DEPLOY 문서 기록.
- Rationale: 코드/자산/데이터 변경 0, TEST.md·TASK.md Run·체크 라인만 추가. search-badge 코드 자체의 적대 리뷰는
  REV-20260702T173000(PASS-WITH-FIXES)에서 완료. 본 cycle 은 그 배포 검증 결과 기록이라 §18.8 패널 skip.
- Verdict: SKIPPED (docs-only, 리뷰 대상 코드 없음).

## REV-20260702T133000-ai-claude-feature-0016-graph-expand-perf [AGENT-TEAM: PASS-WITH-FIXES] — 더블클릭 프리즈 잔존(refreshStates per-node setElementState) 적대 검증
- Related Change: graph-expand-perf (MODIFY CHG-20260702-graph-expand-perf, DECISIONS ADR-006). FE admin.js `_metaG6Apply` 캐시 populate + `_metaGraphRefreshStates` 변화분/rebuild 폴백/rAF coalesce. 데이터 API·스키마·마커 시맨틱 불변.
- Method: 실측 진단(헤드리스 G6 harness — build/setData/draw/fitView 분리 계측 + web 컨테이너 서버측 `metadata_graph.neighborhood` 지연) 으로 병목 특정 → 수정 후 general-purpose subagent **2렌즈 병렬 패널**(① 정확성/상태유실 ② 프리즈재발/신규 stutter), 각 실 diff·전체 setElementState 사용처 grep 교차검증.
- Verified (실측):
  - **병목 특정**: `setElementState` 건당 ~50ms(G6 v5) → 전 노드 루프 200개 = **10,046ms**(실측). 렌더(setData+draw 200노드+127엣지)=~200ms, AGE 이웃 depth=2=135ms, introspection=analyzed 라 skip → 이들은 병목 아님(모두 실측 배제).
  - **수정 효과**: post-rebuild refresh(마커 무변화)=**0ms**, bulk 55마커 변화=**rebuild 82ms**, 구 per-node 200노드=**8,890ms**. ~9s→~0–80ms.
  - **정확성(렌즈①)**: 캐시 populate 값 = `_metaStateSig`(populate 직전 `_busyKeys.clear()` 라 ≡ `_metaNodeStates`) = setData 가 bake 하는 `states:` 값과 **정확히 일치** → "캐시엔 있는데 요소 미적용" false-negative 없음. rebuild 폴백은 setData 로 전 상태 bake(fit=false 카메라 유지). `_metaG6Apply` 는 refreshStates 미호출(재귀 없음), 캐시 populate 가 `await draw` 이전 sync 라 중복 rebuild 없음. selected 는 `_metaNodeStates` 경유 bake 로 유지. per-node 인자 형태 원본 동일.
  - **잔존 루프 없음(렌즈②)**: setElementState 사용처 = `_metaApplyState`(단일노드) + `_metaGraphRefreshStates`(변화분/폴백) 둘뿐. 노드 수 비례 벌크 루프 제거 확인.
- Findings:
  - **BLOCKING(렌즈② → 수정 완료)**: 폴 tick 이 `_metaGraphMarkAnalyzed`+`_metaGraphMarkRunning` 로 `_metaGraphRefreshStates` 를 **연속 2회** 호출 → AI 능동분석 활성 구간에서 tick(2.5s)당 rebuild 2회(160–400ms 이중 stutter) + 첫 `draw()` in-flight 중 둘째 `setData` 재진입 경합 가능. → `_metaGraphRefreshStates` 를 **rAF coalescing**(같은 프레임 다중 호출 1회 실행)으로 병합, 본문 `_metaGraphRefreshStatesNow` 분리. 폴 간격(2.5s) ≫ rebuild(~200ms)라 프레임 간 중첩 없음. 재검증: tick 당 refresh 1회.
  - **NIT (수용 기록)**: ① combo(Schema) key 가 `_metaGraph.nodes` 에 있으나 G6 노드로 bake 안 됨 → analyzed 상태 시 setElementState throw(캐치)·캐시 "적용됨" 기록 — **pre-existing**, combo 는 analyzed 스타일 미정의라 화면 무해. ② THRESHOLD=4 경계: per-node(4×50=200ms)·rebuild(~200ms) 모두 ~200ms — 프리즈 상한은 잡았으나 stutter-free 는 아님(경계값 합리적). ③ `_metaApplyState` 단일호출 ~50ms — 더블클릭당 setSelected 2회≈100ms(프리즈 아님).
- Verdict: **PASS-WITH-FIXES** — CRITICAL/상태유실 0. BLOCKING 1건(폴 이중 refresh) 수정·재검증 CLOSED. NIT 3건 수용.
- Risks (수정 후): 잔여 0(상태 유실). 완료 hard gate = PB-0008 실 Windows(대량 스키마 노드 더블클릭 무프리즈 + AI 분석 중 stutter 없음).
- Human Approval Needed: graph-expand-perf 배포(web 재빌드) — deploy_scope: included(전역 FIRST_REQUEST) → 자동 배포하되 첫 배포 직전 1줄 표면화.

## REV-20260702T052630-ai-claude-feature-0016-rel-selfheal [SUBAGENT: PASS-WITH-FIXES] — 관계 자기교정 파이프라인 근본수정(rel-selfheal) 적대 리뷰
- Related Change: CHG-20260702T024556(본체) + CHG-20260702T052630(패널 반영). shared/config.py ·
  insight.py · relationships.py · metadata_graph.py · agent_core.py + 테스트 4파일. ADR-007.
- Trigger: schema/foreign key/query + 운영 DB 프로브 keyword matched → backend·security·qa 3렌즈
  (원 세션이 dispatch 직후 session limit 중단 → resume 세션에서 재실행).
- Method: general-purpose subagent 3병렬 적대 리뷰(각각 diff 정독 + 소비자/헬퍼 추적 + 실행 검증 —
  파서/프로브 빌더 적대 실행, 결함 재주입 red-green, fake-cursor 실험 포함).
- Verdicts: **backend FAIL**(MAJOR 6, 그중 B-F3·B-F10 실행 재현) / **security PASS-WITH-FIXES**
  (BLOCKING 0 — injection 3경로(파서 문자클래스 격리·dialect 식별자 이스케이프·Cypher _cq/dollar-quote·
  PG 파라미터화) 라이브 적대 실행으로 안전 확증, 프로브 read-only·scope 격리·sample 하드캡 확인) /
  **qa PASS-WITH-FIXES**(46건 red-green 실효성 실증 — D1b/D2/D3 재주입 적색 확인; D1a·저장계층 커버리지 갭).
- Findings → 처리:
  - **B-F1 (MAJOR, 수정)**: instance-scan interval 커서가 ds-단위 → MSSQL multi-DB 정상상태에서 첫 DB 만
    영원히 interval 스캔 획득(코드 실측 교차확인). → `_instance_scan_cursor_key` DB별 분리.
  - **B-F2 (MAJOR, 수정)**: `apply_relationship_signal` leaf-only 매칭 → 교차-DB 동명 edge 오염 전파.
    → a_schema/b_schema slot 한정('' wildcard). 프로브·대화학습 호출부 전달.
  - **B-F3 (MAJOR, 수정 — 재현됨)**: uniqueid 가 heuristic-2 미제외 → PK≡PK shared_key 쓰레기 3건 생성,
    저역폭 정수 PK 겹침으로 trusted 승격 경로. → `_GENERIC_KEY_COLS` 등재 + 부정 단언 테스트.
  - **B-F4 (MAJOR, 수정)**: 프로브 실행오류 무신호·무전진 → 영구 미파단 + NULLS FIRST 큐 head 고착.
    → 객체-부재류 negative 분류 + 전 실패 timestamp 전진 + failed 집계.
  - **B-F5/QA-F3 (MAJOR, 수용+문서화)**: slot=DB명 규약의 dbo-only 가정 — 비-dbo·교차-스키마 후보 영구
    미프로브/그래프 비연결. 현 운영 DB 군 dbo 표준이라 실영향 최소 → ADR-007 Consequences ① 한계 명기,
    후속 initiative(2-세그먼트 slot 확장) 범위로 이월.
  - **B-F6 (MAJOR, 부분수정+이월)**: 케이스 비정규화 — 대화 경로는 QA-F4 lower() 정규화로 수정,
    introspect 테이블명 플래핑(TASK-0305 실측)은 SSOT 레벨 후속(ADR-007 ②).
  - **Sec-F2 (MINOR, 수정)**: cap/timeout 코드 상한 부재 → 클램프(500/200/60s).
  - **Sec-F4 (MINOR, 문서화)**: PROBE off 시 conversation candidate 미검증 잔존 → LEARNING↔PROBE 결합
    권장 ADR-007 ④ ([추정] 태그·w0.4·digest cap 60 이 blast radius 를 제한).
  - **QA-F1 (MAJOR, 수정)**: 라이브 테스트 모듈-레벨 connect → main() 가드(수집 안전).
  - **QA-F2 (MAJOR, 수정)**: D1a·default_schema 채움·저장계층 무테스트 → +10건 보강(총 56 PASS).
  - **B-F7/QA-F5 (MINOR, 수정)**: 신규 except 무로깅 → warning 추가. 스탬프 실패-전진은 스핀 방지
    트레이드오프로 유지(경고 로그가 가시성 담당).
  - **B-F8 (MINOR, 문서화)**: 실효 cadence ≈ REINFER×ceil(N/window)≈30h — ADR-007 ③ 명기. jitter 미도입.
  - **B-F10 (MINOR, 문서화 — 재현됨)**: AST 가드 지역 재바인딩 위음성 → docstring 한계 명시, 명시 이름
    고정 테스트가 최종 방어선.
  - **B-F11/QA-F7 (NIT, 일부 수정)**: neutral/failed report 집계 추가. 미러 행 neutral 미전진·교차-DB
    self-join 보수적 폐기·브래킷-dot 식별자는 수용(보수적 손실).
  - **QA-F6 (MINOR, 수정)**: 문서 수치 정정(46=43+3 합산 명시).
- 재검증 라운드(수정분 적대 재검증 subagent): B-F1/B-F2/B-F3/Sec-F2 봉인 확인(PASS — 게이트·스탬프
  동일 키/방향 스왑 slot 순서/param 개수/기본값 무변형까지 코드·실행 추적). 단 **신규 결함 2건 적발 → 즉시 수정**:
  - **R-1 (중대, 수정)**: B-F4 의 객체-부재→negative 가 fetch 의 ''-slot wildcard 와 결합 —
    MSSQL catalog 순회에서 레거시 '' 실관계가 오답 catalog 프로브 2회(0.4−0.14×2=0.12≤0.15)만에
    영구 broken 오파단. → negative 는 slot 이 현 컨텍스트로 확정된 후보(db_scope 하 양쪽 slot 채움,
    또는 db_scope 부재)에만 적용, ''-slot+db_scope 조합은 failed/touch-only. 회귀 테스트 2건.
  - **R-2 (중간, 수정)**: 1:N 라우터 경로에서 tool 종료 finally 의 primary 복원 **후** learn 이
    ContextVar 를 읽어, 라우팅된 execute_sql 에 primary 의 engine/DB(default_schema 오각인,
    '' 레거시보다 악화)/scope 가 각인. → tools.py 에 실행-시점 스냅샷(`_snapshot_sql_exec_ctx`/
    `get_last_execute_sql_context`) 신설, agent_core 학습이 스냅샷을 읽음(scope_key 의 기존
    primary 오귀속도 부수 해소). 스냅샷 부재 시 default_schema 미채움(안전 폴백). 테스트 2건.
  - 기록(저심각, 수용): param-'' 의 strict-empty 매칭(보수적 — '' 대화 edge 가 스키마-보유 inferred
    를 교차 강화하지 못하는 기회 상실), MSSQL 비-dbo inferred 오파단 경로(ADR-007 ① dbo-only 한계
    내), MySQL default_db 사전 lower 각인(schema-prefix 강제라 실효 낮음).
- 재검증(최종): 수정 후 전체 **61건 PASS**(feature-0002 tests 전체 EXIT=0) + py_compile + ruff clean.
  Verdict: **PASS-WITH-FIXES** — 필수(MAJOR 중 수정 가능 전건 + 재검증 R-1/R-2) 반영,
  수용 한계는 ADR-007 Consequences ①~④.
- Human Approval Needed: 없음(Major 승계 — 원 cycle 사용자 요청 범위 내, 비파괴·마이그레이션 0).
  deploy_scope: included(FIRST_REQUEST 전역) 근거로 배포 자동 진행 + 첫 배포 직전 1줄 표면화.

## REV-20260702T100500-ai-root-feature-0016-probe-mssqlfix [SUBAGENT: PASS] — MSSQL 프로브 SQL 오류 130 hotfix 적대 리뷰
- Related Change: CHG-20260702T100500(probe-mssqlfix). dialects.py MSSQL probe_relationship_overlap
  재작성 + 회귀 테스트. rel-selfheal(REV-20260702T052630) 라이브 검증이 적발한 잠복 결함의 후속.
- Trigger: query/스키마 keyword matched + 프로브 SQL 재작성 → backend+qa 집중 subagent 1렌즈.
- Method: diff 정독 + 신·구 SQL 렌더링 실측(타임아웃·`]` 이스케이프·MySQL 경로) + pytest 54건 실행.
- Verified: 의미 동일성(표본 모집단·중복·NULL→0 처리 전부 구와 동일) · T-SQL 문법 정당성(오류 130
  제약은 집계 인자 내부에만 적용, 파생 테이블 SELECT list 의 CASE WHEN EXISTS 합법) · q() 이스케이프
  6개 위치 전부 실측 · 기존 shape/escape/timeout 테스트 정합 · MySQL 경로 무변경(grep 중복 패턴 0).
- Findings:
  - MINOR-1 (수용): TOP row-goal 이 "정확히 n행만 EXISTS 평가" 보증을 구조적→옵티마이저 의존으로 —
    스트리밍 plan 에선 ~n행 평가, 차단 연산자 없음. 구 SQL 은 실행된 적 없어(전면 130) 반사실 —
    MySQL 쌍둥이와 의미 동치가 실질 기준(성립). 이중 중첩 구조화는 불필요 판단.
  - MINOR-2 (수정 완료): EXISTS 상관 위치 `s0.<src_col>` 의 사용자 유래 식별자 이스케이프가 무봉인
    → escaping 테스트에 `= s0.[c]]ol]` 단언 추가(55건 PASS).
  - NIT (수용): 회귀 테스트는 형태 봉인 — T-SQL 파싱 합법성의 최종 증명은 배포 후 워커 로그
    (오류 130 소멸 + (sampled, matched) 수신)로 확인.
- Verdict: **PASS** — BLOCKING/MAJOR 0. 배포 후 라이브 확인 조건부.
- Human Approval Needed: 없음(rel-selfheal Major 승계 — 라이브 검증 완결 범위). deploy_scope:
  included 근거 자동 배포(워커 재빌드).

## REV-20260702T190000-ai-claude-feature-0016-graph-dblclick-cam [SUBAGENT: PASS-WITH-FIXES] — 더블클릭 카메라 순간이동 해소(앵커-중심 애니 팬) 적대 리뷰
- Related Change: graph-dblclick-cam (MODIFY CHG-20260702-graph-dblclick-cam-anim, DECISIONS ADR-008). `_metaGraphExpand` 카메라 focus 를 즉시→애니메이션 + seq 가드.
- Method: general-purpose subagent 적대 리뷰 — G6 번들 focusElement/zoomTo/viewport transform 계약 실증 + 카메라 경로 라우팅 교차검증 + 헤드리스 카메라 애니 API 검증(별도).
- Findings:
  - **BLOCKING (적발 → 교정 완료)**: 최초 수정이 **라우팅 오인** — 더블클릭이 아니라 우클릭 컨텍스트 메뉴 "중심 보기"(`_metaGraphFocus`, 모델 reset) 함수를 편집했고, 그 함수는 `schemaExpanded.add` 가 없어 Table/Column 앵커가 카드로만 렌더 → `_metaRenderedIdFor`=null → `focusElement(rawKey)` throw → catch 폴백으로 **즉시 fit-to-all**(제거 목표였던 그것) 실행 = 수정 무효. **교정**: 실제 더블클릭 경로 `_metaGraphExpand`(4391, additive, `schemaExpanded.add` 로 앵커 노드 렌더 보장)의 기존 즉시 focus 를 애니메이션화 + focus 함수 원복 + 헬퍼 제거. `if(fel)` 가드 유지로 미렌더 앵커는 throw 없이 skip.
  - **PASS (교정 후)**: 회귀 없음 — loadRoots(_metaG6Apply(true))·검색·리사이즈(_metaGraphFitClamped)·우클릭 중심보기(_metaGraphFocus) 전부 불변, 변경은 `_metaGraphExpand` 카메라 블록 1곳. 줌 정규화 NaN/getZoom부재 안전. `focusElement`/`zoomTo` = viewport transform 만(노드 재렌더·setElementState 없음) → ADR-006 프리즈 수정과 무간섭. seq 가드로 연타 stale 애니 방지.
  - **NIT (수용)**: additive 확장 후 첫 프레임 앵커가 이전 카메라 밖일 수 있으나 focus 팬이 즉시 이어받아 체감 짧음(모델 reset 아님 — blank-frame 위험은 focus 함수 전용, expand 무관). depth-select 재확장도 이 경로 타서 동일 애니(의도적).
- Verdict: **PASS-WITH-FIXES** — BLOCKING(라우팅 오편집) 교정 완료, 회귀 0. 카메라 애니는 실 브라우저 시각(PB-0008)이 최종 확인.
- Human Approval Needed: graph-dblclick-cam 배포(web 재빌드) — deploy_scope: included(전역) → 자동 배포 + 첫 배포 직전 1줄 표면화.


## REV-20260702T230000-ai-claude-feature-0016-graph-dblclick-cam2 [SUBAGENT: PASS] — 더블클릭 카메라 애니 no-op 근본수정(manual rAF tween) 적대 리뷰
- Related Change: graph-dblclick-cam2 (MODIFY CHG-20260702-graph-dblclick-cam2-manual-tween, DECISIONS ADR-009). `_metaGraphAnimateFocus` 신규 + `_metaGraphExpand` 카메라 1줄 교체.
- Method: general-purpose subagent 적대 6축 + **vendored G6 v5.1.1 소스 대조**(focusElement/translateBy/getViewportByCanvas 구현) + 이징 누적 수치 시뮬.
- Verified:
  - **no-op 원인 확정**: graph `animation:false` 가 per-call 카메라 애니 게이팅(헤드리스 실증 false=2ms/true=412ms) → §30 focusElement({duration}) no-op. 이번 manual rAF tween 은 G6 애니 우회라 실제 동작.
  - **중앙 정확성(수학 증명)**: `getViewportByCanvas`(viewport px 출력) + `translateBy`(relative, `translate/zoom` world 이동 = zoom-독립 viewport px 팬) 좌표계 일치. delta 공식 `W/2-start` = G6 내장 `focus` 의 `center-anchorViewport` 와 **동일**. 이징 telescoping 합=`Dx*ease(1)=Dx`(ease(1)=1.0). 시뮬 오차 ≤1e-13px → 앵커 정중앙 안착.
  - **종료 안전**: `p>=1`(dur=420 고정, performance.now monotonic) / seq 가드 / translateBy throw 3중. 무한루프 경로 없음.
  - **동시성**: 후속 op(`++_opSeq`)→tween 즉시 return. 2.5s 폴 rebuild(`_metaG6Apply(false)`, opSeq 미증가, fit=false 카메라 불변, 결정론 레이아웃 위치 불변)→tween 계속 유효. setData/translateBy 무경합.
  - **폴백**: `_metaRenderedIdFor` null→no-op; getElementRenderBounds/getViewportByCanvas throw·NaN→즉시 focus 폴백(내부 catch). throw 전파 없음. `renderedIds` 는 `_metaG6Apply` setData(→build)에서 갱신 + `await draw` 후 헬퍼 실행이라 fel 정합.
  - **줌순서**: zoomTo(clamp) await 후 bounds/size/viewport 판독 — clamp 새 줌 기준. 정확.
  - **회귀 없음**: 헬퍼는 expand(더블클릭)만 호출. loadRoots/search/fitClamped/우클릭 중심보기/줌툴바 불변. diff=헬퍼+expand 1줄(admin.js 단일).
- Findings:
  - **NIT (수용)**: ① 420ms tween 중 2차 더블클릭이 opSeq 를 올렸으나 그 op 가 fetch 실패로 rebuild 없이 early-return 시 첫 tween 이 중간 팬 위치에 카메라 잔류(다음 성공 op 가 교정 — 항구적 아님). ② tween 중 사용자 능동 휠줌 시 start 캡처 줌 기준이라 최종 정렬 어긋남(420ms 내 동시 조작 필요, 희귀). 둘 다 "부드러운 팬" 목표 불파괴.
- Verdict: **PASS** — BLOCKING 0. ADR-008 의 no-op 를 manual tween 으로 실제 해소(번들 소스 대조 확증). NIT 2건 수용.
- Human Approval Needed: graph-dblclick-cam2 배포(web 재빌드) — deploy_scope: included(전역) → 자동 배포 + 첫 배포 직전 1줄 표면화.

## REV-20260703T152607-ai-root-feature-0016-graph-reltrace [SUBAGENT: PASS-WITH-FIXES] — 접힌 관계 표시 + 관계 추적 + AI 연동 적대 리뷰
- Related Change: CHG-20260703T152607(graph-reltrace). admin.js 그래프 뷰(엣지 집계·추적·AI 연동) +
  styles.css + admin.html + metadata_graph.py schema_tables REFERENCES 조회. TASK §32.
- Trigger: UI/layout/graph + schema/REFERENCES keyword matched → frontend + backend+qa 2렌즈 병렬.
- Method: general-purpose subagent 2병렬 — (frontend) git diff 정독 + node --check + 심볼 정의 전수 +
  seq/스타일/XSS 경로 추적; (backend+qa) **라이브 AGE(15022 Table/9562 REFERENCES) 에서 신규 Cypher
  직접 실행·EXPLAIN·경계테스트**(status-null 임시엣지 생성→ROLLBACK, leftover 0).
- Verdicts: **frontend PASS-WITH-FIXES** / **backend+qa PASS**.
- Findings → 처리:
  - **frontend MAJOR (수정)**: 상세 패널 `data-trace` 가 따옴표 미이스케이프 `esc` 사용 → 속성 탈출
    가능(DB 식별자 인용부호). → `_metaGraphRenderDetail` esc 에 `"`→`&quot;` 추가(sibling parity).
  - **frontend MINOR (수정)**: "관계 상세" 용어(GlossaryTerm) 행이 showDetail→trace 변경으로 오라우팅.
    → `_metaGraphTraceRelation` 이 비-Table/Column 대상은 showDetail 로 라우팅.
  - **frontend MINOR (수정)**: `looksColumn`(세그먼트≥3)이 3-part fqn 테이블에서 오판 잠복. → node
    label 우선 판정(`label==="Column"`), label 부재 시에만 세그먼트 폴백.
  - **frontend NIT (수용)**: AI 박스 렌더마다 전체 엣지 O(E) 스캔 — 현 규모 무해, 성장 시 인덱스 검토.
  - **frontend CLEARED**: 스타일 객체 mutation(신규 객체 반환 확인)·집계 id 충돌(agg: 네임스페이스)·
    G6 미지원 style 키 크래시(data 로 분리)·seq 경합(await 후 seq 캡처)·바인딩 누수(innerHTML 교체) 전건 무결.
  - **backend PASS (라이브 확정)**: FK status-null 포함(`IS NULL OR <>'broken'` 정확, 임시엣지 실측)·
    `_cq` 주입안전·6컬럼 정합·intra-schema 소스캡처 100%(dblog 346엣지 실측)·성능 34-47ms·graceful
    (try/except 로 테이블 반환)·프론트 ingest 계약 정합. 관찰(LOW): 글로벌 Column/Table Seq Scan 이
    라벨 크기 선형(수만 테이블 성장 시 raw graphid 우회 여지) — 현 카드 클릭당 1회 lazy 라 수용.
- 재검증: 수정 후 node --check PASS + 엣지집계 격리 Node 11/11 재실행 PASS(로직 불변).
- Verdict: **PASS-WITH-FIXES** — frontend MAJOR+MINOR 2 전건 수정, backend PASS. BLOCKING 0.
- Human Approval Needed: 없음(Major 승계 — 사용자 요청 범위, 비파괴·마이그레이션 0). deploy_scope:
  included(전역) 근거 자동 배포(web+worker) + PB-0008 완료 하드 게이트.

## REV-20260703T003000-ai-claude-corp-feature-0016-node-role-viz [SUBAGENT: PASS-WITH-FIXES] — 분석완료 노드 역할 시각 표식(node-role-viz) 적대 패널 4렌즈
- Trigger: UI/화면/범례(ux, design) + schema/migration/query(backend, qa) keyword matched — §18.8 dispatch.
- 구성: general-purpose 적대 리뷰어 4(backend / frontend 정확성 / ux·design / qa 회귀·엣지), 전원 REFUTE 관점. 대상 = node-role-viz 전체 diff(alembic 0031·node_analysis·llm·insight·admin_metadata·admin.js/html/css).
- Verdict: backend PASS-WITH-FIXES · frontend PASS-WITH-FIXES · ux/design PASS-WITH-FIXES · qa PASS-WITH-FIXES → 전 findings 수정/기록 후 정합.
- **수정 반영 (MAJOR 5)**:
  - [backend B1] 마이그레이션 창(0031 미적용 DB + 신 코드 — 롤링 순서 실수·downgrade-먼저 롤백) 에서 role UPDATE 가 UndefinedColumn → 분석 전건 terminal-failed(LLM 비용 소진) + run 폴링 404 오표시 → **role 참조 4개 쿼리 지점에 legacy(role 제외) 폴백** + 프로세스당 1회 경고(_warn_role_column_once).
  - [qa Q1] backfill 의 UPDATE 가 updated_at 트리거를 발화 → "최신 done" 선택(get_node_analysis·scope 집계)이 과거 run 행으로 역전(재분석 결과가 화면에서 롤백) → **선택 기준을 id DESC(삽입 순 = 최신 run)로 교체**(양쪽).
  - [ux U1] 선택 테두리 #9c6515(앰버)가 log #E69F00(2.18:1)·config #D55E00(1.27:1) 역할색과 동계열 위장 → **selected stroke #161b22(어두운 무채색)**.
  - [ux U2] "분석 중" 주황 점선이 log 역할 칩 위 1.19:1 로 불가시(재분석 메뉴 경로 실재) → **running state 에 fillOpacity 0.45(desaturate)** — 어느 역할색 위에서도 판독.
  - [ux U3] mapping #CC79A7(흰 3.06:1)·transaction #009E73(흰 3.42:1) dark 플래그 오배정 → **dark:true 플립**(어두운 라벨).
- **수정 반영 (MINOR)**: [backend B2] backfill 예외 debug→warning · [B3/docs] 단위 테스트 건수 실측 정정(13→10, relevance 25→28) · [ux U4] etc 아이콘 ◽(tofu 비가시)→📦, 역할 범례 dot 에 1px border · [ux U5·fe F1] 역할 범례 행 우측 플러시(legend-note margin-left:auto 상속) → 좌측 정렬 override CSS · [fe F2] role 도착 rebuild 승격이 busy(펼침 fetch) 표식을 조기 소멸 → **busy 창에는 rebuild 유예**(캐시 미갱신 → 다음 tick 재감지).
- **수용·기록 (수정 없음, 근거 명시)**: [fe] 검증 — 캐시 서명 3-writer(_metaApplyState/_metaG6Apply/refreshStates) 통일·setElementState state 순수성·XSS 화이트리스트 게이트·reset race 기존 시맨틱 동일 무회귀. [qa Q2] node_label='' Table done 행(그래프 미투영 시 enqueue 폴백)은 백필 영구 스킵 — 빈도 낮고 재분석 자기치유, 시각 결손만. [qa Q3] roles Map sync↔폴 last-write-wins 경합 — run 진행 중 폴이 매 tick 전량 재전송해 자기치유, run 종료 직후 수백 ms 창 한정 stale(다음 상호작용 복구). [qa Q4] _metaApplyState 의 ~16ms bake-전 도장 창 — 코스메틱·다음 rebuild 복구. [qa Q5] role 저장 경로(UPDATE·backfill) DB-의존 테스트 부재 — 순수함수 10건 + 배포 후 라이브 실측으로 보강(알려진 갭). [ux U6] 💳 아이콘의 비화폐 행위 오독 소지(📜 와의 형태 변별 우선 유지)·용어 amber↔log 근접(노드 형태+테두리 이중 인코딩으로 변별)·미분석 teal↔transaction green 근접(아이콘 유무 변별) — 라이브 관측 후 조정. [fe F3] 아이콘 prefix 로 긴 테이블명 ellipsis 2-3자 조기화 — 코스메틱.
- 검증: 수정 후 py_compile/node --check PASS · role 10 + relevance 28 + ai_ops 15 = 53 PASS · headless harness 4 시나리오 ALL PASS(pageerror 0) · 전체 pytest 회귀 재실행.
- 병렬 재번호: 상류 #553 이 §31/ADR-009 선점 → 본 cycle 은 **§32/ADR-010** 으로 재번호(§13.1). 상류 main 의 feature-0003 TEST.md 커밋된 병합 마커(graph-ctxmenu↔aiops-activity-paging Run 충돌 잔재)를 위생 해소(두 Run 모두 보존).

## REV-20260703T160000-ai-root-feature-0016-reltrace-tabledetail [SUBAGENT: PASS-WITH-FIXES] — 테이블 단일클릭 상세 관계 모델 병합 적대 리뷰
- Related Change: CHG-20260703T160000(reltrace-tabledetail). admin.js `_metaGraphRenderDetail`/
  `_metaGraphShowRelations` 모델 병합 + admin.html 캐시버스터. TASK §33. graph-reltrace PB-0008 후속.
- Trigger: UI/graph + REFERENCES/relationship keyword matched → frontend 집중 1렌즈.
- Method: general-purpose subagent — git diff 정독 + node --check + isSelf/dedup/방향/성능/회귀/XSS 재현 검증
  + 백엔드 schema_tables 노드 계약 대조.
- Verdict: **PASS-WITH-FIXES** — 차단 결함 0. 핵심 로직(self 판정 scope-prefix 오판 없음·dedup 방향 정합·
  around 오분류 없음·컬럼 단일클릭 회귀 없음·nm esc XSS 안전) 견고 확인.
- Findings → 처리:
  - **LOW (수정)**: 모델-병합 관계행의 상대 Column 노드가 `_metaGraph.nodes` 에 없을 수 있음(schema_tables
    는 REFERENCES 끝점 Column 노드 미포함) → raw scoped key 표시·조인컬럼 주석 소실. → 신규
    `_metaKeyDisplayNode`(scope 접두 제거 fqn + leaf) 로 nm 폴백 + 관계 상세 노드 보강.
  - **LOW/cosmetic (수정)**: `_metaGraphIngest` 가 model 엣지에 cardinality 미저장 → 모델-only 관계행
    `[cardinality]` 배지 항상 누락. → ingest 에 `cardinality` 저장.
  - **INFO (수용)**: detail fetched-refs 루프의 broken 미필터는 백엔드가 응답·모델 양쪽 제외라 실질 no-op.
- 재검증: node --check PASS + 모델병합 격리 Node 5/5 + `_metaKeyDisplayNode` 파생 정확(Column/Table label·fqn·leaf).
- Human Approval Needed: 없음(Minor·프론트 전용·비파괴). deploy_scope: included 자동 배포 + PB-0008.
## REV-20260703T003000-ai-claude-feature-0016-graph-dblclick-latency [SUBAGENT: PASS] — 더블클릭 카메라 팬 반응 지연 제거(즉시 시작 + 적응형 follow) 적대 리뷰
- Related Change: graph-dblclick-latency (MODIFY CHG-20260703-graph-dblclick-latency, DECISIONS ADR-011). `_metaGraphAnimateFocus` 적응형 follow 재작성 + `_metaGraphExpand` 팬 fetch 전 fire-and-forget 시작.
- Method: general-purpose subagent 적대 7축 + G6 init/좌표 API 대조 + 종료·수렴 논리 검증.
- Verified: 종료 보장(수렴/seq/MAXMS 1200 — MAXMS 가 av 무관 최상단 평가라 무조건 종료) · 이동 앵커 수렴(매 프레임 재조회 → 잔여 K 접근, rebuild 1회성이라 수렴) · fire-and-forget 동시성(rebuild 동기 setData+draw 는 rAF 점유라 miss 미누적, 완료 후 av 해소) · fetch실패/seq(catch 는 opSeq 미증가 → 팬 계속 앵커 정렬; 후속 op 는 seq 폐기) · translateBy vs draw 무경합(동기) · `_metaRenderedIdFor` 매 프레임 재조회로 카드↔노드 전환 자기치유 · K<1 단조수렴(오버슈트/진동 없음) · 회귀 없음(헬퍼는 expand 1곳, 다른 카메라 경로 불변).
- Findings:
  - **MEDIUM (적발 → 수정 완료)**: `missStreak>30` 조기포기가 "연속 rAF 콜백" 기준인데 rebuild 프리즈 구간엔 rAF 가 거의 안 돌아 벽시계와 탈동조 → 저사양·대형 rebuild·프레임드롭 환경에서 팬이 조용히 중단돼 "텀/미완 팬" 확률적 재발. → **missStreak 제거, MAXMS(1200ms) 단일 시간상한**으로 종료 판정(av 미해소 프레임은 skip 후 재시도). 조기포기 위험 제거.
  - **NIT (반영)**: ① API 부재(getElementRenderBounds/getViewportByCanvas/translateBy 미지원) 번들서 구버전 focusElement 폴백 손실 → 진입부 API 가드 + focusElement 즉시 폴백 복원. ② W/H 1회 캡처 → 팬 중 리사이즈 시 중앙 목표 스테일 → **W/H 매 프레임 재조회**.
- Verdict: **PASS** — BLOCKING 0. MEDIUM 수정(missStreak 제거)·NIT 2건 반영. 실제 애니 반응성은 PB-0008(실 브라우저)이 최종.
- Human Approval Needed: graph-dblclick-latency 배포(web 재빌드) — deploy_scope: included(전역) → 자동 배포 + 첫 배포 직전 1줄 표면화.


## REV-20260703T163000-ai-root-feature-0016-reltrace-postdeploy [SKIPPED:doc-only-postdeploy] — POST-DEPLOY PB-0008 결과 기록
- Related Change: CHG-20260703T163000. feature-0003 TEST.md POST-DEPLOY PASS 기록 + TASK §33 완료 체크.
- Trigger: 비-코드 doc-only(POST-DEPLOY 증적) → §18.8 표 "비정책 doc-only" 행 = panel SKIP.
- 근거: 코드/정책 변경 0(순수 검증 결과 문서화). 실 검증은 PB-0008 라이브 실측(3항목 PASS, 스크린샷 5매)로
  이미 수행됨 — 본 항목은 그 결과의 정본 기록이며 별도 적대 리뷰 대상 아님.

## REV-20260703T165147-ai-root-feature-0016-reldetail-colexpand [SUBAGENT: PASS-WITH-FIXES] — 상세 패널 관계 컬럼 아코디언+방향구분+의미툴팁 적대 리뷰
- Related Change: CHG-20260703T165147(reldetail-colexpand). admin.js `_metaGraphRenderDetail` 관계 렌더
  재구성 + 신규 `_metaRelSemanticTip` + styles.css + admin.html. TASK §35.
- Trigger: UI/layout/graph + relationship keyword matched → frontend 집중 1렌즈.
- Method: general-purpose subagent — git diff 정독 + node --check + 백엔드 REFERENCES 방향 계약 대조
  (Column→Column directed, broken 제외) + 방향분류/개수/아코디언/XSS/회귀 재현 검증.
- Verdict: **PASS-WITH-FIXES** — 차단 결함 0. XSS(title esc 따옴표+개행 안전)·아코디언 독립성·리스너
  누수 없음·dedup(refSeen)·reltrace 회귀(nested 행 bind)·TDZ 없음 전건 CLEAN.
- Findings → 처리:
  - **MAJOR (수정)**: intra-table self-FK(양끝 모두 self 컬럼, 예 employees.manager_id→id)에서
    `if(sc) else if(tc)` 가 out 만 잡아 참조받음(←) 누락·totIn 저계상. → source 컬럼 out + target 컬럼 in
    **둘 다 기록**(`addRel` 헬퍼, sc===tc 컬럼 자기참조는 out 만). 격리 재검증 PASS(out=1 in=1).
  - **MINOR (수정)**: 미정의 CSS 변수 `--text-1`/`--surface-2`(폴백은 있었음) → 기존 토큰(inherit/
    --primary-soft)으로 정리.
  - **MINOR/consistency (수용)**: `_metaGraphRelTraceRowsHTML`(AI 박스 행)은 구 정적 title 유지 — 본 PR
    범위 밖(별 경로), 기능 무결. 후속 통일 여지.
- 재검증: node --check PASS + 격리 로직 8/8 + intra-table self-FK 2케이스 PASS.
- Human Approval Needed: 없음(Major 승계·프론트 전용·비파괴). deploy_scope: included 자동 배포 + PB-0008.

## REV-20260703T170000-ai-root-feature-0016-colexpand-postdeploy [SKIPPED:doc-only-postdeploy] — POST-DEPLOY PB-0008 결과 기록
- Related Change: CHG-20260703T170000. feature-0003 TEST.md POST-DEPLOY PASS(4항목) + TASK §35 완료.
- Trigger: 비-코드 doc-only(POST-DEPLOY 증적) → §18.8 "비정책 doc-only" = panel SKIP.
- 근거: 코드/정책 변경 0. 실 검증은 PB-0008 라이브(4항목 PASS, 스크린샷 5매)로 수행됨 — 본 항목은 정본 기록.

## REV-20260703T020000-ai-claude-feature-0016-role-legend-panel [SUBAGENT: PASS] — 역할 범례 우측 상세 패널 상단 세로·접힘 이전 적대 리뷰 7축
- Related Change: CHG-20260703-role-legend-panel (TASK §36 — reldetail-colexpand 가 §35 선점해 §36 재번호). 프론트 표현 전용(admin 그래프 뷰 역할 범례 위치·레이아웃).
- Trigger: 가시 UI 변경(그래프 뷰 렌더 인접) → §18.8 적대 패널 [SUBAGENT] dispatch.
- 점검 7축 판정 (subagent, 파일:라인 근거 기반):
  1. [PASS] 회귀(범례 wipe) 없음 — 상세 렌더 4곳(admin.js:4862/4885/5035/5368) 모두 `metadataGraphDetailBody`(실존) `.innerHTML` 만 교체, aside 는 `d.clientWidth` 폭 조회(admin.js:4245)로만 참조. 새 `<details>` 는 body/progress 의 형제(위) → 안 지워짐.
  2. [PASS] 잔여 참조 0 — `legend-roles` html·css·js grep 0건(문서 서술만).
  3. [PASS] CSS 변수 유효 — `--border/--surface/--text-2/--text/--text-muted/--primary` 전부 `:root`(styles.css:10-21) 정의. 단일 light 팔레트(다크 블록은 토큰 재정의 안 함) → 다크 회귀 대상 없음. 신규 규칙 폴백(`var(--surface,#fff)` 등)까지 방어적.
  4. [PASS] 접힘 UX/접근성 — `<details open>` 기본 펼침, `list-style:none`+`::-webkit-details-marker{display:none}` 로 네이티브 마커 제거, 커스텀 카펫 `▸`/`[open]` rotate. summary 네이티브 button 역할(키보드/SR) 유지. 구 `aria-hidden="true"` → `<ul aria-label>` 노출로 SR 개선.
  5. [PASS·주의] 상세 패널 종속 — `#metadataGraphDetailToggle`(admin.js:3900) 의 `.detail-collapsed` 가 aside 를 `display:none`(styles.css:7976) → 패널 접으면 범례도 동반 은닉. 사용자 선택 위치("우측 상세 패널 상단")의 자연 귀결로 수용. MODIFY/TASK 에 부작용 명시.
  6. [PASS] 레이아웃/반응형 — aside `overflow-y:auto`+height clamp 로 8줄+progress+body 스크롤. `@media(max-width:900px)` 1열 스택 + aside `max-height:380px` → 그래프 아래로 흐름, 겹침 없음.
  7. [PASS] 시인성/칩 정합 — 밝은 dot(#F0E442·#56B4E9) border 유지, 칩 8종 색/아이콘/라벨/순서가 `_META_ROLE`(admin.js:3214-3221)와 1:1 완전 일치.
- BLOCKING: 0.
- NIT(가시 회귀 아님 — 수용 기록, 미수정): (a) summary `:focus-visible` 커스텀 아웃라인 없음(네이티브 포커스 링 의존 — 기능상 OK). (b) summary 텍스트와 `<ul aria-label>` 의 "테이블 역할" SR 이중 낭독 가능성(경미).
- 총평: 배포 가능(PASS). 설계 의도 정확 충족, 최대 리스크(범례 wipe)는 구조적 방지. 완료 게이트=PB-0008 실 Windows 라이브 육안(세로 표시 + 접힘 동작).

## REV-20260703T030000-ai-claude-feature-0016-role-legend-bottom [SUBAGENT: PASS] — 역할 범례 상세 패널 하단 이동 + 확장 밀림/뒤틀림 해소 적대 리뷰 7축
- Related Change: CHG-20260703-role-legend-bottom (TASK §37). 프론트 표현 전용(상세 패널 내부 레이아웃 — 범례 첫 자식 → 마지막 자식, aside flex 컬럼 + margin-top:auto + 자식 flex-shrink:0).
- Trigger: 가시 레이아웃 변경(상세 패널 flex 화) → §18.8 적대 패널 [SUBAGENT] dispatch. + headless playwright 렌더 격리 실증(2시나리오) 선행.
- 점검 7축 판정 (subagent, 파일:라인 근거 — 격리 렌더 결과를 코드로 반증 시도했으나 전건 재확인):
  1. [PASS] detailBody wipe 회귀 없음 — 렌더 4함수(admin.js:4862/4915/5143/5476) `metadataGraphDetailBody` `.innerHTML` 만 교체, aside 는 clientWidth(4245) 읽기만, progress 렌더는 progress 만. 범례 클래스 admin.js 참조 0(무JS) → 하단 이동 후에도 안 지워짐.
  2. [PASS] flex 컬럼 부작용 없음 — progress 표시화는 `style.display=""`(인라인 해제)라 flex 아이템 blockify 정상. aside 직속 3자식(progress/detailBody/legend) 고정, stretch 전폭.
  3. [PASS] margin-top:auto+overflow — 짧으면 바닥 고정, 길면 auto=0 + flex-shrink:0 로 detailBody 미압축·컨테이너 스크롤(dbH==dbScrollH 983·canScroll). 범례 최하단이라 상단 클리핑 조건 불성립.
  4. [PASS] detail-collapsed 토글 — `.admin-meta-graph.detail-collapsed .admin-meta-graph-detail{display:none}`(0,3,0) 가 `.admin-meta-graph-detail{display:flex}`(0,1,0) 를 특이도·순서로 이김 → 접힘 정상. `> *` 규칙은 aside 직속만.
  5. [PASS] 반응형(@media max-width:900px) — height:auto → free space 0 → margin-top:auto=0, 범례가 detailBody 뒤 자연 흐름 + max-height:380px 스크롤. 그래프 아래로 정상.
  6. [PASS] 잔여/버스터 — `<details>` 정확히 1개(상단 중복 없음, 이동이지 복제 아님), 캐시버스터 `styles.css?v=20260703-role-legend-bottom` bump. `admin-meta-graph-detail` 클래스 aside 1개에만, datasourceDetail append 는 무관 별개 요소.
  7. [PASS] 접근성/시맨틱 — `<details open>`/summary 토글·detailBody aria-live·`<ul aria-label>` 유지. DOM 순서 progress→detail→legend 는 시각 순서와 일치.
- BLOCKING: 0.
- NIT: (a) styles.css 상단 role-legend-panel 옛 주석이 "상단"으로 남음 → **수정함**(하단 이동 반영, 본 cycle 에서 정정). (b) 색 범례 SR 도달이 노드 상세 뒤 — 시각 순서·사용자 의도(하단)와 정합, 수용.
- 총평: 배포 가능(PASS). 사용자 후속 피드백 2건(하단 이동 + 확장 밀림 해소) 모두 `margin-top:auto`+`flex-shrink:0` 로 코드·렌더 양측 충족. 완료 게이트=PB-0008 실 Windows(하단 배치 + 확장 시 위 상세 안 밀림).
## REV-20260703T014113-ai-claude-corp-feature-0016-graph-rel-layout [SUBAGENT: PASS-WITH-FIXES] — 관계 기반 배치(교차 최소화) 적대 리뷰 4축
- 대상: CHG-20260703-graph-rel-layout (admin.js `_metaG6Build` 관계 기반 배치 pre-pass, ADR-012, TASK §38).
- 방식: ultracode workflow(wf_73ab2394-003) — 4축 finder(알고리즘 정합성/G6 통합/UX/성능) 병렬 + 발견별
  2-refuter 적대 검증(과반 기각 시 kill). 총 14 agents, findings 5 → 확정 4(refute 0/2)·기각 1(refute 2/2).
- 확정 1 [MAJOR, g6+ux 중복 발견]: `_metaGraphCollapse`(컬럼 접기)가 컬럼 끝점 엣지 전부 삭제 → REFERENCES 가
  모델에서 소실 → 배치가 edges 순수함수가 된 본 변경에서 접기 제스처가 스키마 seriation·barycenter 를 연쇄
  변경(전면 재셔플, 앵커 없음, 재펼침 비가역 — ToggleColumns 는 엣지 미재조회). 수정: collapse 의 엣지 삭제를
  `e.type !== "REFERENCES"` 로 한정(containment 만 삭제) — 렌더는 graph-reltrace renderEndpoint 승격이 이미
  처리하므로 접힌 테이블 간 관계 표시가 오히려 정합 회복(기존 소실 버그 동시 해소).
- 확정 2 [MINOR, ux]: 더블클릭 이웃 확장 fetch(이웃+introspect) 합계 >1.2s 시 follow tween(MAXMS)이 구 위치에
  종료된 뒤 rebuild — 관계 재배치로 앵커 원거리 이동 시 시야 이탈. 수정: `_metaGraph._focusLive` 생존 마커
  (try/finally 소유 해제) + expand 의 rebuild 직후 tween 사망 시 무애니 `focusElement` 1회 폴백.
- 확정 3 [MINOR, perf]: `_metaG6Build` 의 itemsNat 이 비-terms 스키마에서 무조건 정렬 후 폐기(relOrder 가 항상
  존재) — 대규모 펼침에서 rebuild 당 ~20ms 낭비. 수정: relOrder 직접 소비, terms/방어 분기만 즉석 정렬.
- 기각 1 [perf 주장 MAJOR]: "pre-pass 86ms/rebuild(91 스키마·3000 테이블·10K 엣지)" — 2 refuter 일치 기각:
  백엔드가 전체 덤프 금지 + 응답 상한(_NEIGHBOR_NODE_CAP 300 노드/1200 엣지, search ≤80)이라 해당 규모의
  클라이언트 모델이 성립 불가, 라이브 관계 행 규모도 그에 못 미침. memoization 불채택(현실 규모 ms 단위).
- 판정: 확정 3건 전량 수정 + 회귀 방지 구조 테스트(t8 collapse-REFERENCES 보존, t9 expand focus 폴백) 추가,
  격리 테스트 10/10 PASS. BLOCKING 0 잔여.

## REV-20260703T023000-ai-claude-corp-feature-0016-graph-rel-layout-postdeploy [SKIPPED:doc-only-postdeploy] — POST-DEPLOY PB-0008 결과 기록
- 배포 web-a/b `5f439788`(무중단 롤링·soak) 후 실 Windows Chrome PB-0008 라이브 검증 **전건 PASS** 결과를
  TEST.md(graph-rel-layout POST-DEPLOY Run)·TASK §38(T38.8) 에 기록하는 doc-only 후속 — 코드 무변경이라
  §18.8 패널 skip. 핵심 실측: 관계쌍 평균 배치 순서 거리 32.5→3.2(90% 감소, gunzgame 115쌍) · collapse
  REFERENCES 145→145 보존·배치 불변(§18.8 MAJOR 수정 실증) · 이웃확장/검색 pageerror 0.

## REV-20260703T040000-ai-claude-feature-0016-cluster-role-prefix [SUBAGENT: PASS] — 클러스터 상세 역할 접두사 + 행 클릭 선택 + 범례 툴팁 적대 리뷰 7축
- Related Change: CHG-20260703-cluster-role-prefix (TASK §39). 프론트 표현 + 클릭 상호작용(클러스터 상세 목록·범례 툴팁).
- Trigger: 가시 UI + 클릭 상호작용(select) + 새 데이터 경로 → §18.8 적대 패널 [SUBAGENT] dispatch. + headless 렌더 격리 실증 선행.
- 점검 7축 판정 (subagent, 파일:라인 근거):
  1. [PASS/NIT] XSS/속성: 칩·버튼 `title` 은 `_META_ROLE` 신뢰 상수·정적 문자열, `t.description` 은 텍스트 위치 esc. NIT — `data-node-key="${esc(t.key)}"` 의 로컬 `esc` 가 `"` 미escape → 키에 `"` 시 속성 breakout 이론상 가능(단 `<>` escape 로 태그주입 불가). **기존 4개 사이트(data-key/data-trace) 동일 패턴 = 회귀 아님**, admin-only + DB식별자에 `"`+페이로드 동시 필요라 저위험. 수용(하드닝은 공유 esc 일괄 강화 별도 maintenance).
  2. [PASS] 클릭 핸들러: 두 진입 경로(Local/ById) 모두 render 거쳐 innerHTML 직후 1회 바인딩. showDetail → 동일 컨테이너 innerHTML 교체로 옛 버튼+리스너 GC → 누수/좀비/중복 없음.
  3. [PASS] select semantics: showDetail 이 `_metaGraphSetSelected`(하이라이트, 렌더된 노드만 apply) 호출. 미렌더 노드는 selected 변수만 세팅(무해), focusElement 는 `_metaRenderedIdFor` null 가드로 skip. showDetail 은 렌더 무관 동작.
  4. [PASS] 범례 tips: data-role 8개 ↔ `_META_ROLE` 키/아이콘/색 1:1 완전 일치. 정적 `<li>` 상주라 호출 타이밍 무관, title 재주입 idempotent.
  5. [PASS] 칩 헬퍼: `if(!rd) return ""` + 호출부 `_metaRoleOf` 유효성 이중 방어. small=18px 고정, dark 라벨색, 미분석 `amgr-role-none` transparent+폭 유지.
  6. [PASS] CSS: `.amgr-cluster-tables`(0,2,1) > `.admin-meta-graph-sec ul`(0,1,1) padding-left:0 승리, 스코프 한정으로 타 ul 무영향. `--primary-soft`·`--text-muted` 정의 존재. code{flex:none}+18px 슬롯 → 정렬 보장(allCodesAligned 재확인).
  7. [PASS] 회귀: `_META_ROLE.desc` 순수 additive(기존 소비처 특정 필드만 접근). 클러스터 상세 외 렌더 경로 무영향. `node --check` OK.
- BLOCKING: 0.
- NIT(수용): esc 따옴표 미escape(위 1축 — 기존 패턴·저위험). 
- 총평: 배포 가능(GO). 사용자 3요구(접두사+정렬·행클릭 선택·범례 툴팁) 코드·헤드리스 렌더 양측 충족. 완료 게이트=PB-0008 실 Windows.

## REV-20260703T021144-ai-claude-feature-0016-graph-drag [SUBAGENT: PASS] — 중간버튼 카메라 팬 + 테이블 노드 종속 UI 동반 드래그 적대 리뷰 4축
- 대상: working-tree admin.js graph-drag 변경(behaviors object-form + `enable` 오버라이드, `node:dragstart/drag/dragend`, `tableDeps` 맵). 커밋 3d12fb08 의 상대방식(`translateElementBy`+delta)을 절대-오프셋(`translateElementTo`+offset)으로 리팩터한 **최종 워킹트리** 기준. resume 세션에서 재실행·확정.
- 방법: 적대 subagent — G6 v5.1.1 vendor 번들(`vendor/g6.min.js`)을 역어셈블해 API 시맨틱·이벤트 latch·좌표계까지 실측 교차검증(통과 아닌 결함 적발 목적).
- **4축 전부 PASS (BLOCKING 0)**:
  - 축1 회귀: behaviors 3종(drag-canvas/zoom-canvas/drag-element) 개수·종류 동일(유실 없음). `_metaCanvasDragEnable` 비-중간 분기가 번들 drag-canvas 기본 enable 과 문자열까지 동일 → 좌클릭 빈캔버스 팬·좌클릭 노드 이동·휠 줌·node:click·우클릭 ctx·미니맵 무회귀. mousedown capture 는 `button===1` 만 preventDefault(좌0/우2 무영향, pointer 취소 아님 → G6 팬 흐름 유지).
  - 축2 엣지: 접힌 테이블·컬럼/용어/카드/"X:"ctl 직접 드래그 → `tableDeps` 미등록 → 단독 이동. `renderedIds` 필터 + `getElementPosition` try/catch 로 stale/미렌더 종속 배제. 중간버튼 드래그 시 `_drag=null` 유지 → drag/dragend no-op.
  - 축3 G6 API(번들 실측): `translateElementTo({id:[x,y]}, false)` multi-key 지원 확정. `getElementPosition`·`translateElementTo` 모두 **모델(월드)좌표** 동일계 → 오프셋 수학 성립. `enable` 콜백 이벤트 1인자 시그니처 정합. DragCanvas 가 DRAG_START 에서 enable 1회 latch + `buttons=4` 판정 → 노드 위 중간버튼도 팬(REQ① 성립).
  - 축4 좌표계/오프셋: drag-element 의 `translateElementBy` 가 모델 x/y 를 **동기** 갱신 후 커스텀 `node:drag` 가 읽어 프레임 지연 없음. 오프셋을 dragstart 월드좌표로 고정 → 매 프레임 절대 배치라 zoom 배율·카메라 팬·누적 drift 무관. dragend 재호출은 핸들러 순서 안전망 → 커밋의 상대방식(순서 뒤바뀌면 delta 중복/누락) 대비 **개선**.
- **NIT 6건 (전부 비차단)**:
  - N1 [수정완료]: `_drag` 필드 주석(`{id,lastX,lastY,deps}`→`{id,offs}`) + `node:drag` 배선 주석(`translateElementBy` delta→`translateElementTo` 절대오프셋) 구방식 서술 → 실제 절대방식으로 정정(admin.js, 주석 전용·로직 무변).
  - N2 [수용]: `_metaG6Build` 가 `tableDeps` 만 리셋, `_drag` 미리셋 — 단 dragend 에서 반드시 null 화 + rebuild 는 드래그 밖 트리거라 self-heal(버그 아님).
  - N3 [수용]: `_metaEventButtons` 최후폴백(`button===-1`→좌1)은 buttons·nativeEvent.buttons 둘 다 부재 시만 도달 — DOM 규격상 pointer drag 은 buttons 항상 존재라 사실상 도달 불가.
  - N4 [수용, 선재]: "−" 접기 ctl 직접 드래그 단독 이동, 노드 위 중간'클릭'(드래그 아님) node:click 발화 가능 — 둘 다 본 변경 이전부터 존재(범위 밖).
  - N5 [수용]: `translateElementTo` 가 종속 z 를 0 리셋(2D 무해).
  - N6 [처리완료]: 브랜치 stale — `_metaRoleChipHTML` 등 역할 기능은 main 선안착분. origin/main(9e1156d6) 3-way 병합으로 역할(admin.js grep=2)+드래그(함수 8) 양쪽 보존 확인, §40→§41 재리넘버.
- **판정**: BLOCKING 0. REQ①(중간버튼 팬)·REQ②(종속 동반이동) G6 v5.1.1 실측 시맨틱 정합. N1 수정 완료, N2~N6 수용/처리.

## REV-20260703T132403-ai-claude-feature-0016-graph-drag-postdeploy [SKIPPED:doc-only-postdeploy] — POST-DEPLOY 자산검증 결과 기록 (코드 무변경)
- 대상: graph-drag(TASK §41) 배포 후 문서 갱신 — TASK T41.5 [x], MODIFY CHG-…-graph-drag-postdeploy, TEST POST-DEPLOY Run. **코드·자산 무변경(doc-only)** → §18.8 적대 패널 비적용(SKIPPED).
- 근거: PR #571 머지(29c3a07c) → `make deploy-web` 무중단 롤링 soak 90s 통과. WSL localhost caddy edge :443 자산검증 PASS — healthz `status:ok / git_commit=29c3a07c / mysql_ok / pg_ok`, 라이브 admin.js graph-drag 심볼 12·`_metaRoleChipHTML` 2(병합 보존)·admin.html 버스터 `admin.js?v=20260703-graph-drag`. 코드 품질 검증은 원 cycle REV-20260703T021144-graph-drag [SUBAGENT: PASS] 에서 완료.
## REV-20260703T043659-ai-claude-corp-feature-0016-graph-simgroups [SUBAGENT: PASS-WITH-FIXES] — 유사 속성 그룹 영역화 적대 리뷰 4축
- 대상: CHG-20260703-graph-simgroups (admin.js `_metaG6Build` 유사 속성 그룹 블록, ADR-013, TASK §42).
- 방식: ultracode workflow(wf_a6044ac9-72a) — 4축 finder(그룹핑 알고리즘/기하·G6 통합/UX/상호작용 회귀) +
  발견별 2-refuter. **한계**: 패널 실행 중 Fable 5 사용량 한도로 refuter 17개·finder 2개(geo/interact)가
  조기 에러 종료 → 워크플로우 자동집계의 "기각"은 신뢰 불가(미검증). Opus 전환 후 **미검증 findings 를 직접
  코드 판정**하고 errored 축을 직접 검증.
- 확정·수정 4건:
  - [MAJOR] GB:/GH: 그룹 배경 박스가 펼친 클러스터 내부 대부분을 덮어(fillOpacity 0.75 는 히트테스트 유지)
    기존 combo:click(클러스터 상세)·combo:contextmenu(스키마 메뉴)를 데드존화. 수정: 박스 클릭→소속 스키마
    `_metaGraphShowClusterDetailById`, 우클릭→`_metaGraphCtxForSchema` 위임(드래그는 계속 불가 — 박스-칩 분리 방지).
  - [MAJOR] 2차 관계 attach(_metaSimGroups)가 갱신 중 famOf 를 읽어 방금 배정된 이웃으로 연쇄 attach →
    입력순서 의존(주석 "무연쇄" 위배). 수정: 1차 스냅샷 `fam1 = new Map(famOf)` 에서만 읽어 무연쇄·순서독립.
  - [MINOR] `view` 접두 정규화가 "viewer_log"를 "er_log"로 절단. 수정: 공용 `_metaViewNorm` 가 `view_`(구분자)
    접두만 제거, 그 외 view 로 시작하는 실명 보존. _metaSimFamilies·_metaSimGroups 동일 규칙.
  - [NIT] 패널 그룹 헤딩 li aria-hidden="true" → 보조기기에서 구획 소거. 수정: aria-hidden 제거 + role="group"
    + aria-label("<라벨> 그룹 · 테이블 N개"). 겸사 80행 캡을 그룹경계에서만 끊고 (shown/n) 절단표식.
- 기각(직접 판정): 방향 말줄임 탈락(refuter 완료·반박 — 관계 attach 로 스템 불일치 시 말줄임 생략이 의미상
  정당) / role 도착 재편(role 은 3차만 — name·relation 그룹 미보유 misc 테이블만 영향, 1회 전이. ADR-012
  "데이터 축적에 따른 배치 수렴"·role-viz 점진 채색 철학과 정합 — 유지·문서화) / 결정론 위반 주장(same-model
  same-order 이므로 t5 로 확인, 연쇄는 별개 품질 이슈로 위 ②에서 해소).
- errored geo/interact 축 직접 검증: G6 style 키(zIndex/radius/fillOpacity/labelFontWeight/labelPlacement)는
  vendored g6.min.js·기존 _metaTableStyle 에서 사용 중(크래시 없음), packGroup 은 `Math.max(0, ...)` 로 빈
  배열 방어, GB:/GH: 는 `_metaGraph.nodes` 미등록이라 refreshStates·_stateCache·tableDeps·focus 경로 미유입.
- 판정: 확정 4건 수정 + 회귀방지 t10~t12, 격리 25/25 PASS, node --check PASS. BLOCKING 0.
## REV-20260703T045000-ai-claude-corp-feature-0016-graph-simgroups-postdeploy [SKIPPED:doc-only-postdeploy] — POST-DEPLOY PB-0008 결과 기록
- 배포 web-a/b `abc78b00`(무중단 롤링·soak) 후 실 Windows Chrome PB-0008 라이브 검증 **전건 PASS** 를 TEST.md
  (graph-simgroups POST-DEPLOY Run)·TASK §42(T42.8) 에 기록하는 doc-only 후속 — 코드 무변경 §18.8 skip. 핵심:
  그룹 배경 박스 22 + 헤더 칩 22 렌더(item·21/character·17/…)·GB 클릭 클러스터 상세 위임(§18.8 MAJOR 수정
  실증)·패널 그룹 헤딩 aria·컬럼 접기 REFERENCES 145→145 보존·검색 정상·pageerror 0.
## REV-20260704T143839-ai-claude-feature-0016-freeplace-liveverify [SKIPPED:doc-only-postdeploy] — freeplace 드래그 4-상호작용 라이브 검증 결과 기록 (코드 무변경)
- 대상: graph-freeplace(ADR-015, TASK §44) 자유배치 드래그의 완료 게이트(T44.7) 라이브 실측을 T44.8 [x]·
  MODIFY CHG-…-freeplace-liveverify·TEST(freeplace Run POST-DEPLOY)·해당 doc 에 기록하는 doc-only 후속.
  **코드·자산 무변경(doc-only)** → §18.8 적대 패널 비적용(SKIPPED). 코드 품질 검증은 원 cycle
  REV-20260703T101622(freeplace 6축 적대 리뷰, PASS-WITH-FIXES — nodePos override 분리 MAJOR 반영)에서 완료.
- 근거: 초기 "G6 Canvas 드래그는 win-browser 합성 pointer 가 @antv/g 히트테스트 미도달 → 사용자 라이브 확인 필요"
  유보를, **Playwright `connect_over_cdp`(win-browser relay @172.26.144.1:9223)로 실 Windows Chrome attach →
  `page.mouse` 실제 이벤트(move→down→16-step move→up)** 로 자동 구동하여 해소. 실측 전건 PASS: 접힌 카드
  드래그(accountdb 548,524→430,415, fp-03)·combo 드래그(fp-06)·테이블 노드 드래그+combo auto-fit 반응형
  리사이즈(MessageQueue 535,505→470,630 + ROUTINE_USES 재라우팅, fp-07)·접기/펼치기 회귀 0(masonry+sim-group,
  fp-04)·드래그 위치 persistence(statsdb 548,576→400,400 후 tapjoy 펼침 setData+draw rebuild 에도 오프셋 유지·
  snap-back 없음, fp-06)·초기화 clusterOffset/nodePos clear→원위치(fp-05). 전 구간 pageerror 0.
## REV-20260704T154756-ai-claude-feature-0016-group-interact [SUBAGENT: PASS-WITH-FIXES] — 카테고리 그룹(sim-group) 상호작용(드래그·접기·반응형) 3-렌즈 적대 패널
- Trigger: 가시 UI + 신규 드래그/클릭 상호작용 + 좌표 3계층 수학(ADR-020) → §18.8 적대 패널 [SUBAGENT] dispatch.
  3 병렬 렌즈(① 좌표·레이아웃 수학 ② 상호작용 wiring ③ 회귀·통합) + 선행 headless 격리 실증(_metaG6Build 25/25).
- ① **좌표 수학 — CLEAN**: GB 반응형 박스가 무-offset 시 packGroup 기하와 **4변 정확 일치**(off-by-one 0 — assignH 상수·
  n≥gic·col0 top0 불변식 검증), pre-pass↔place-loop nodePos 계산 **bit-identical**(둘 다 colLeftX=_fp[0]−TXOFF·ty=_fp[1]),
  GH 헤더(right−28)↔GX(right−21) 7px gap·bw≥248 로 음수 폭 불가, 접기 reflow(hEff·contentW·byy) 자기정합, combo
  auto-fit 는 기존 freeplace 와 동일 기전.
- ② **상호작용 wiring — PASS-WITH-FIXES**: 리지드 드래그(anchor grabbed 제외·GB 항상 포함)·델타 누적(부호·반복 정합)·
  nodePos 시프트(clusterOffset MAJOR fix 동형)·drag/click 판정(GX first·GB 무이동 클릭 위임 보존)·이벤트 바인딩 CLEAN.
- ③ **회귀·통합 — CLEAN(MAJOR 회귀 0)**: 평면 masonry 폴백(groupsMeta 없음→pre-pass 게이트·groupOf 미populate→rebuild
  없음, freeplace #3 회귀 0)·freeplace SC/combo/table 드래그 무간섭(dragstart 순서 SC→GB/GH→table·_drag 매회 null 리셋·
  group 분기 gd.group 게이트)·§49 순서 안정화 무충돌(필드명 분리)·be:/nm:/role:/misc 균일(nsKey 공통)·admin.html 캐시버스터
  양측·resetModel 4필드 clear 확인.
- **확정결함 반영**:
  - [MAJOR/①②③ 공통] **접힌 그룹 드래그 시 개별배치(nodePos) 멤버 분리**: groupMembers 가 방출된(펼친) 멤버만 담겨,
    접힌 그룹 헤더 드래그 시 그 멤버 nodePos 시프트가 스킵→펼치면 nodePos 멤버만 옛 좌표에 남아 분리. **수정**:
    groupOf/groupMembers 를 emission pre-pass(방출분) 대신 **build sim-group 분기에서 b.sg.tables(전체 멤버, 접힘 포함)**
    로 채움 → 접힌 그룹도 dragend 에서 전 멤버 nodePos 델타 시프트. headless T7 추가(접힌 그룹 groupMembers 전체 등록 검증).
  - [NIT/③] **GX 우클릭 무메뉴**(GB/GH 와 불일치): node:contextmenu 의 GB/GH 분기에 GX 추가 → 소속 스키마 메뉴 위임.
  - [NIT/③] **범례 문구 정밀화**: "헤더 드래그" → "박스/헤더 드래그로 그룹 이동"(GB 전체가 draggable).
- **수용/이연(비파괴)**:
  - [MINOR/③] combo(클러스터) 드래그 hit-area 축소(GB 가 combo 내부 덮음) — 헤더 스트립·그룹 간격·여백으로 여전히 도달
    가능(ADR-020 한계 문서화). PB-0008 라이브 QA 로 밀집 클러스터 확인.
  - [NIT/②③] 드래그-후 node:click 재발화 여부는 G6 v5 이동 임계값 의존(기존 draggable+clickable 테이블·SC 카드와 동일
    parity — 신규 위험 아님) → PB-0008 "그룹 드래그 후 상세패널 미개방" 확인.
  - [NIT/②③ perf] 그룹소속 테이블 단독 드래그 dragend 마다 full rebuild(1회/드래그, per-frame 아님) — 박스 재파생 위해
    필요·수용. [NIT/②] 재군집 시 groupOffset key(fam) orphan(무해, resetModel clear·groupOrder 안정화로 대부분 방지).
- 재검증: node --check PASS + headless _metaG6Build 격리 **25/25 PASS**(수정 후). 라이브 canvas 상호작용은 T50.8 PB-0008.
## REV-20260704T162548-ai-claude-feature-0016-group-drag-hotfix [SKIPPED:pb0008-live-driven-hotfix] — GH 헤더 hit-test zIndex 수정 (라이브 실측이 포착·검증)
- 대상: §50 group-interact 의 그룹 드래그 결함 hotfix(TASK §50.3 T50.9) — GH 헤더 zIndex −1→5.
- §18.8 subagent 패널 대신 **PB-0008 라이브 실측이 적대 검증 역할**을 수행(패널보다 강함): §50 배포본(fb88b19e)을 실 Windows
  Chrome(Playwright `connect_over_cdp` real mouse)로 검증하던 중, 그룹 헤더 드래그가 **그룹 이동이 아니라 클러스터 이동**
  으로 발화함을 실측 포착(groupOffset 미설정·clusterOffset 설정·전체 클러스터 shift). 원인 규명: GH(zIndex −1)가 combo
  배경(z0) 뒤라 @antv/g hit-test 에서 가려짐. **라이브 GH zIndex 패치(5) 후 재드래그 → groupOffset 설정·타 그룹(t_account)
  불변** 으로 수정 실증. 코드 반영(GH z−1→5 + cursor:move).
- 코드 품질: 원 cycle REV-20260704T154756(3-렌즈 적대 패널) 에서 완료. 본 hotfix 는 1-속성(zIndex) hit-test 수정 —
  로직·좌표수학·회귀 표면 무변경(GB 배경 z−2·GX z1 불변, 헤더 스트립 멤버 없어 시각 회귀 0). headless T8 로 잠금.
- 재검증: node --check PASS + headless **29/29 PASS**(T8: GH zIndex 양수·cursor move·GB 음수·GX 양수). 재배포 후 그룹
  드래그 라이브 재검증(패치 없이 groupOffset 설정 확인).
## REV-20260704T163510-ai-claude-feature-0016-group-drag-liveverify [SKIPPED:doc-only-postdeploy] — 그룹 드래그 hotfix 재배포 후 라이브 재검증 결과 기록 (코드 무변경)
- 대상: hotfix(T50.9) 재배포(a9492afe) 후 그룹 드래그 라이브 재검증을 T50.10 [x]·MODIFY CHG-…-group-drag-liveverify·
  TEST(group-drag-hotfix Run POST-DEPLOY)에 기록하는 doc-only 후속. **코드·자산 무변경** → §18.8 적대 패널 비적용(SKIPPED).
- 근거: 배포본(admin.js `?v=20260704-group-drag-hotfix`·GH zIndex 5 서빙) 에서 **라이브 패치 없이** notice 그룹 헤더
  드래그 → groupOffset={dx:141,dy:−77} 설정·accountdb clusterOffset=null(그룹 드래그·combo 아님)·notice 만 이동·
  t_account 불변·pageerror 0(gi-06). 코드 품질은 REV-…-group-drag-hotfix·REV-…-group-interact 에서 완료.
