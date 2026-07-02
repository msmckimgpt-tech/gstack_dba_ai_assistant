---
doc_type: REVIEW
feature_id: feature-0016-metadata-graph
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

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
