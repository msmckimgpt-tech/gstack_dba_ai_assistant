---
doc_type: REVIEW
feature_id: feature-0016-metadata-graph
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

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
