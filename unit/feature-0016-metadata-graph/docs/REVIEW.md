---
doc_type: REVIEW
feature_id: feature-0016-metadata-graph
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

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
