---
doc_type: REVIEW
feature_id: feature-0016-metadata-graph
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

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
