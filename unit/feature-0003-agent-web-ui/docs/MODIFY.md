---
doc_type: MODIFY
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---


# Modify Log

> 이전 기록(408건): [MODIFY-archive-20260711T115053.md](./_archive/MODIFY-archive-20260711T115053.md)

## CHG-20260707T111500-runtime-settings-postverify (feature-0018 + audit hotfix POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-07. 코드/자산 무변경 — TEST.md §3 에 POST-DEPLOY PB-0008 PASS Run append + TASK 완료 체크. 배포: PR #602→a7dcc436(feature) + PR #604→8d0a4723(audit hotfix), web 무중단 롤링 ×2.
- 검증 요지: 설정 pane 3항목 렌더, 실행 타임아웃 22입력/6카테고리/즉시·재배포 배지, **env-fallback 실증**(300/600/180=.env 값), 모델 예산 2행 no-override input 비움, write-path e2e(저장→DB override→audit→초기화→DB 정리), pageerror 0. 증적 artifacts/feature-0018-runtime-settings/pb0008-runtime-settings-timeouts.png.
- Cross-ref: CHG-20260706T094937-runtime-settings(feature) · CHG-20260707T110000-runtime-settings-auditfix(hotfix) · TEST.md §3 Run.

## CHG-20260707T110534-doc-sync-rn-0707 (TASK-20260707T110534-doc-sync-rn-0707 — 07-02→07-07 머지분 릴리즈노트 정합 + cache-buster bump, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: 신규 '2026-07-03'(8항목)·'2026-07-04'(12항목)·'2026-07-06'(4항목)·'2026-07-07'(5항목) 블록 prepend(07-02 이하 블록 보존, 총 4블록 29+ 신규 항목). `generated` 2026-07-02→2026-07-07. 블록 요지: 07-03 제품 카테고리 개요·유사 테이블 영역화·역할 색/아이콘·관계 탐색·화면 조작·데이터소스 평균 연결시간·공유 참여 알림·대량분석 안정성 / 07-04 유사 항목 자동묶음·크로스-DB 연결·묶음 드래그/접기·상세 뒤로앞으로·범례 탭·ds 이름표시·분석중 안내·겹침순서·상단탭+검색·Esc fix·여기부터~여기까지 공유·☰ 메뉴·응답 안정성 / 07-06 추론 강도 선택·함수/프로시저 노드·DB 단위 분석·상세 nav·필터·검색 / 07-07 런타임 설정·카테고리 밴드+크로스-DB·관계 큐레이션·DB 분석 심화·응답 안정성.
  - cache-buster: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260702-rn-0702`→`?v=20260707-rn-0707`.
- Verification: `node --check release-notes-data.js` PASS. 블록 순서 07-07>06>04>03>02·스키마 정합·07-02 이하 보존 확인. 사용자향 평이화(내부용어 누출 0). jsdom 테스트는 이 env 미설치(컨테이너 전용).
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- 사용자향 평이화: 내부 구현·feature-id·렌더러/마이그/엔드포인트/cache-buster 내부 슬러그 비노출. 렌더 로직(`release-notes.js`) 무변경 — 데이터만. META(STATUS·wiki·ARCHITECTURE·RELEASE_NOTES·meta/REVIEW)는 별도 commit(REV-20260707T110534-META-0020-doc-sync-0707).
## CHG-20260707T120000-runtime-settings-ux (TASK-20260707T120000-runtime-settings-ux — 런타임 설정 pane UI 재설계, web/UI CSS+JS-only, Major §12.3, feature-0003)
- Date: 2026-07-07 (worktree ai/claude-corp/feature-0018-runtime-settings-ux). 사용자 피드백("UI 세련도 부족") 대응. feature-0018 기능/동작 불변 — **표현(presentation) 계층만** 재구성.
- `static/styles.css`: `.rs-*` 컴포넌트 세트 신규(정렬 grid 행·카테고리 섹션·focus-ring 입력·배지·dirty/override/invalid 상태·반응형). 콘솔 디자인 토큰/패턴 정합.
- `static/admin.js`: 런타임 설정 렌더러 재작성 — `.admin-quota-editor`(미정렬·행별 버튼) 폐기 → `buildRuntimeSettingRow`(2×2 grid, 저장/초기화 버튼 제거). 편집·기본값복원을 `adminState.pending.runtimeSettings` 로 예약, 하단 commit-bar("모두 적용")로 배치 적용(`setRuntimeSettingPending`·applyAllPending 루프·cancelAllPending·refreshPendingUI 연동, nav row `.has-pending` dirty 표시). 설명 잘림 해소(ellipsis+title), 범위 인라인 경고. rsSaveValue/rsResetValue(엔드포인트) 재사용.
- `static/admin.html`: cache-buster `?v=20260707-runtime-settings-ux`(admin.js·styles.css).
- 영향: 백엔드/엔드포인트/RBAC/스키마 무변경. 저장 UX 가 즉시 PUT → pending+배치적용(콘솔 네이티브)로 변경. 회귀 표면=공유 commit-bar 로직(계정/역할/프롬프트) — additive 배선, 적대 리뷰로 검증.
- Cross-ref: CHG-20260706T094937-runtime-settings(기능) · TEST/REVIEW 동일 slug.

## CHG-20260707T121500-runtime-settings-ux-postverify (런타임 설정 UI 재설계 POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-07. 코드/자산 무변경 — TEST.md §3 에 POST-DEPLOY PB-0008 PASS(before/after) append + TASK 완료 체크. 배포 PR #607→da3f57db.
- 검증 요지: 두 패널 정렬 grid·설명 완전노출·commit-bar 편집/적용/복원 e2e(DB override roundtrip)·pageerror 0. 사용자 "세련도 부족" 피드백 해소 확인. 증적 artifacts/feature-0018-runtime-settings/{current,after}-{timeout,model}-panel.png.
- Cross-ref: CHG-20260707T120000-runtime-settings-ux(재설계) · TEST/REVIEW 동일 slug.

## CHG-20260707T130000-reasoning-budgets (TASK-20260707T130000-reasoning-budgets — 추론 강도별 예산 설정 + UI 교훈, Major §12.3 — feature-0003 web/UI + cross-unit feature-0002·shared)
- Date: 2026-07-07. feature-0018 후속: 모델별 예산에 이어 추론 강도(낮음/높음/매우 높음)별 요청 단위 thinking budget 을 관리 콘솔에서 조정 가능하게. '일반'은 no-override(B1)라 설정 대상 제외.
- `shared/runtime_settings.py`: reasoning_budget 레지스트리/resolver/serialize(상세 shared/docs/MODIFY 동일 slug). `unit/feature-0002-agent-core/src/agent_core.py`: `_call_llm` precedence 확장(레벨 override→기본→모델 override; 상세 feature-0002/docs/MODIFY 동일 slug).
- `static/admin.js`: `모델별 추론 예산` 패널을 2 섹션(모델별 + 추론 강도별)으로 확장, 추론 행은 pre-fill(기본값=적용값). nav-dirty 분류 RS_REASONING_PREFIX 추가. `static/admin.html` cache-buster admin.js bump(styles.css 무변경).
- `docs/LEARNINGS.md`: LRN-20260707-0001(UI 가시성 개선 교훈, verified).
- 영향: 백엔드 엔드포인트/RBAC/스키마/audit 무변경(기존 PUT/DELETE·validate·audit 재사용, 신규 키만 등록). override 미설정 시 전 경로 기존 동작 동치(B1 유지).
- Cross-ref: CHG-20260706T094937-runtime-settings·-ux / feature-0002·shared MODIFY 동일 slug.

## CHG-20260707T131500-reasoning-budgets-postverify (추론 강도별 예산 POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-07. 코드/자산 무변경 — TEST.md §3 POST-DEPLOY PB-0008 PASS append. 배포 PR #609→767ca387(web + 워커 재빌드). 검증: 추론 강도별 예산 섹션 렌더·reasoning-key write-path e2e·사용자 MCP_TIMEOUT_SEC=60 override 보존·pageerror 0. 증적 after-model-panel-reasoning.png.
- Cross-ref: CHG-20260707T130000-reasoning-budgets · TEST/REVIEW 동일 slug.
## CHG-20260707-kb-candidate-adoption (TASK-20260707-kb-candidate-adoption — 지식베이스 메타데이터 채택 인박스 + ENUM 대화 자율수집, Major §12.3 — feature-0003 web/UI·API + cross-unit feature-0002 agent-core·shared/config)
- 변경 요지: 대화에서 용어사전·ENUM 코드사전 후보를 수집하고 관리 콘솔에서 채택(승급/거부)하도록 재구성. 용어사전은 이미 구현(0021/0023)돼 있어 **ENUM 을 그 대칭으로 신설** + 두 사전 후보를 **통합 채택 인박스**(지식베이스 하위 신규 탭)로 한눈에.
- **ENUM 백엔드(parity)**: 마이그 `0039_enum_feedback`(`enum_feedback` 검토큐 + `enum_dictionary.source` + GRANT, 비파괴·멱등, down_revision 0038_node_analysis_refine). `kb_glossary.py`: enum feedback 함수군(record/auto_promote_or_queue/list/count/promote/reject/_status/_insert_auto/infer) + enum CRUD source. `llm.py`: ENUM_SUGGEST_PROMPT+llm_enum_suggest. `config.py`: AGENT_ENUM_*(threshold 0.9). `agent_core.py`: _enum_autopropose(best-effort). `app.py`: 권한 kb.enum.curate(카탈로그, 마이그 불필요). `admin_metadata.py`: enum-feedback list/promote/reject + admin_list_enums source.
- **UI**: `admin.html`(adoption 탭/pane + 필터 툴바 + 카드 그리드), `admin.js`(ADMIN_TAB_PERMISSIONS.adoption·switchTab 훅·loadAdoptionInbox/render/그룹 카드/개별·일괄 채택·배지·컨트롤 배선), `styles.css`(.admin-meta-tag-kind + .admin-adoption-* — 기존 .admin-meta-row/.dashboard-widget 재사용).
- **범위 봉인**: 용어사전 후보수집·검토 큐 로직 불변(인박스가 기존 glossary-feedback 엔드포인트 재사용). 샘플 검수 큐·그래프 뷰 무변경. 편집-후-채택 미포함(as-is 채택).
- 검증: 신규 코어 14 + web 경계 9 테스트 PASS · 기존 enum-list 계약(source)·route 골든(197→200) 갱신 · 호스트 전체 1581 passed · 컨테이너 make test 유일 실패(routine_dbanalysis, postgres-replica 미해석)는 main 격리에서도 동일 = 사전존재 env(본 변경 무관) · ruff PASS. PB-0008 Windows-browser= POST-DEPLOY(정적 baked).
- Files: `alembic/versions/20260707_0039_enum_feedback.py`(feature-0002), `modules/kb_glossary.py`·`modules/llm.py`·`agent_core.py`(feature-0002), `shared/config.py`, `app.py`·`routers/admin_metadata.py`·`static/{admin.html,admin.js,styles.css}`(feature-0003), 테스트 `test_kb_enum_feedback.py`·`test_metadata_enum_feedback.py`·`test_metadata_glossary_enum.py`·`route_snapshot_p5b.json`, docs `{TASK,TEST,REPORT,FUNCTION,MODIFY,REVIEW}.md`
- Cross-ref: REVIEW.md REV-20260707T051054-kb-candidate-adoption · TASK-20260707-kb-candidate-adoption · feature-0002 REPORT(2026-07-07)

## CHG-20260707-metadata-console-redesign (TASK-20260707-metadata-console-redesign — 메타데이터 콘솔 IA 통합 + 5서브뷰 디자인 폴리시, Major §12.3 — feature-0003 web/UI 단독)
- 변경 요지: 직전 채택 인박스 배포 후 실사용 피드백 반영 — 최상위 `채택 인박스`·`샘플 검수` 탭이 메타데이터 서브뷰와 겹쳐, **2차 보기를 서브탭 파라미터화**해 각 사전 하위로 통합하고 5서브뷰 디자인을 이전 교훈 기반으로 폴리시. **UI 단독**(admin.html/admin.js/styles.css) — 백엔드/라우터/스키마/RBAC 정의 무변경(enum-feedback·sample-feedback API·`kb.enum.curate`/`kb.sample.curate` 권한 유지).
- **구조**: `_METADATA_REVIEW` config + `viewBySub` 상태 + `_metaSyncViews`(#metadataViews 동적 버튼) + `_metaIsReview` 로 glossary 하드코딩 2차 보기를 일반화. 채택 인박스 제거(탭/pane/JS블록/CSS/init/perm), ENUM 후보 → `ENUM 코드사전 > {목록|검토 큐}`, 샘플 검수 → `샘플쿼리 > {목록|검수 큐}`(`loadSampleReview`/`renderSampleReview` #metadataList 재타깃), 최상위 샘플검수 탭 제거. glossary+enum 큐 통합(`loadFeedbackQueue`/`renderFeedbackQueue(kind)`).
- **디자인(감사 Top 10)**: `--surface-2` 토큰·rich empty+skeleton·enums/columns 카드 그룹핑·행 카드 기하·title↔body 위계·폼 grid+인라인검증·SQL 프리뷰·필터바·배지 semantic 토큰(자동등록=neutral)·이모지 제거+KPI. cache-buster `?v=20260707-metadata-console-redesign`.
- **범위 봉인**: 5서브뷰 CRUD/AI 자동완성/부트스트랩 로직 보존. 그래프 뷰·대시보드 등 타 pane 무변경. 백엔드 0.
- 검증: §18.8 3렌즈 패널(BLOCKING 1·MAJOR 1·HIGH 1·MED 3·LOW 5 FIXED, XSS clean, ACCEPT 1) · node --check OK · 제거 심볼 grep-0 · route 골든 불변 · 호스트 1637 passed(회귀 0) · CSS 균형. PB-0008 = POST-DEPLOY.
- Files: `static/{admin.html,admin.js,styles.css}` + docs `{TASK,TEST,REPORT,FUNCTION,MODIFY,REVIEW}.md`
- Cross-ref: REVIEW.md REV-20260707T064745-metadata-console-redesign · TASK-20260707-metadata-console-redesign

## CHG-20260707T230501-doc-sync-rn-2305 (TASK-20260707T230501-doc-sync-rn-2305 — 07-07 후속 머지분 릴리즈노트 정합 + cache-buster bump, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: 기존 '2026-07-07' 블록 `items` 에 2항목 append(같은 날 → 새 일자 블록 미생성, `generated` 2026-07-07 유지) — ① new/admin "대화에서 모은 코드값(상태 코드 등) 뜻풀이 후보를 검토해 채택"(0beb02e3) ② improved/admin "AI 추론 예산을 강도(낮음·높음·매우 높음)별로도 설정"(d9516aee). 블록 `summary` 에 '코드값 후보 검토·채택 · 추론 강도별 예산 설정' 구 추가.
  - cache-buster: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260707-rn-0707`→`?v=20260707b-rn-0707`.
- 중복 회피: 업무 용어(glossary) 대화 자율수집은 2026-06-29 블록에 이미 있어(라인 408·414) 재announce 금지 — 신규 코드값(ENUM) 측만 반영(적대 검증 rescope). 콘솔 IA 통합(47a63b1a)·그래프 화살표·pane 재설계·OAuth cron·§56 sync 는 비-사용자/이미-커버 → 릴리즈노트 미포함.
- Verification: `node --check release-notes-data.js` PASS · 블록 순서 07-07>06>04>03>02 · 07-06 이하 보존 · 스키마 정합. 사용자향 평이화(내부용어 누출 0). jsdom 테스트는 이 env 미설치(컨테이너 전용).
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- 사용자향 평이화: 내부 구현·feature-id·렌더러/마이그/엔드포인트/권한키/cache-buster 내부 슬러그 비노출. 렌더 로직(`release-notes.js`) 무변경 — 데이터만. landing/배포는 cron wrapper 소관. META(STATUS·wiki·RELEASE_NOTES·meta/REVIEW)는 별도 commit(REV-20260707T230501-META-0021-doc-sync-0707-2305).

## CHG-20260708-metadata-console-polish (TASK-20260708-metadata-console-polish — 메타데이터 콘솔 잔여 디자인 폴리시 5건, Minor §12.3 — feature-0003 web/UI 단독)
- 변경 요지: metadata-console-redesign 배포 후 PB-0008 실 Windows 브라우저 적대적 미적 검증에서 잡은 잔여 미세 폴리시 5건 적용. **UI 단독**(styles.css + admin.js confidence 배지 클래스 1개), 백엔드/구조/로직 무변경.
- #1 2차 보기 필 경량화(border 제거·borderless active chip — 1차 밑줄 탭에 종속) · #2 메타 전용 list-detail 균형(목록 300~400px + empty 중앙·max-width) · #3 그룹 카드 내부 행 divider 평탄화(nesting 경감) · #4 timestamp 경량+그룹 내 숨김 · #5 신뢰도 배지 accent(`-conf`).
- 검증: node --check OK · CSS 균형(1905/1905) · route 골든 불변 · 호스트 1662 passed(회귀 0). cache-buster `?v=20260707-metadata-console-polish`.
- Files: `static/{admin.js,styles.css,admin.html}` + docs `{TASK,TEST,REPORT,FUNCTION,MODIFY,REVIEW}.md`
- Cross-ref: REVIEW.md REV-20260708T012922-metadata-console-polish · TASK-20260708-metadata-console-polish · 선행 REV-20260707T064745-metadata-console-redesign

## CHG-20260708-metadata-console-ux2 (TASK-20260708-metadata-console-ux2 — 메타데이터 콘솔 UX 4건, Major §12.3 — feature-0003 web/UI 단독)
- 변경: #1 list 컬럼 폭 확대+행 가독성 · #2 검토/검수 큐 행 클릭→우측 read-only 상세(`_metaRenderReviewDetail`/`reviewSelected`) · #3 ENUM 그룹 "+코드 추가"(`_metaStartCreatePrefilled` pre-fill) · #4 샘플 mermaid 다이어그램 렌더(공용 `mermaid-render.js` 재사용, admin.html vendor 로드). **UI 단독**(백엔드/RBAC/스키마 0).
- 검증: node --check OK · CSS 균형 · route 불변 · 호스트 1662 passed(회귀 0). cache-buster `?v=20260708-metadata-console-ux2`.
- Files: `static/{admin.html,admin.js,styles.css}` + docs `{TASK,TEST,REPORT,FUNCTION,MODIFY,REVIEW}.md`
- Cross-ref: REVIEW.md REV-20260708T033320-metadata-console-ux2 · TASK-20260708-metadata-console-ux2 · 선행 REV-20260708T012922-metadata-console-polish

## CHG-20260708T230501-doc-sync-rn-0708 (TASK-20260708T230501-doc-sync-rn-0708 — 07-08 머지분 릴리즈노트 정합 + cache-buster bump, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: releases[0] 에 `date:"2026-07-08"` 새 블록 prepend(`generated` 2026-07-08) — 3항목(전부 admin): new §59 제품 분류 AI 제안 / improved §57 그래프 접힘 카드 시각화 / improved 콘솔 검토 화면 개선(ux2 4건+폴리시 5건 통합). 07-07 이하 블록 보존.
  - cache-buster: `index.html`·`admin.html` 의 `release-notes-data.js?v=20260707b-rn-0707`→`?v=20260708-rn-0708`.
- 제외: §58(라벨 케이스/rekey·infra)·§56 T56.9(기출시)·내부 기록·META 도구 → 릴리즈노트 미포함. 07-07 블록과 중복 0.
- Verification: `node --check release-notes-data.js` PASS · 블록 순서 07-08>07>06>04>03>02 · 스키마 정합 · jsdom verify_release_notes.mjs 33/34 PASS(1 FAIL=styles.css pre-existing·본 변경 무관). 사용자향 평이화(내부용어 누출 0).
- Files: `static/release-notes-data.js`, `static/index.html`, `static/admin.html`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포는 cron wrapper 소관. META(STATUS·wiki·ARCHITECTURE·RELEASE_NOTES·meta/REVIEW)는 별도 commit(REV-20260708T230501-META-0022-doc-sync-0708).

## CHG-20260709-graph-toolbar-consolidate (TASK-20260709-graph-toolbar-consolidate — 그래프 뷰 상단 툴바 통합 + 우측 상태 텍스트 reflow 제거, Major §12.3 — feature-0003 web/UI 자산, 정본 feature-0016)
- 문제: 그래프 뷰 툴바에 성격이 다른 컨트롤 13개(검색·깊이·스키마이동·종류필터3·초기화·제품·줌4·상세·상태)가 한 줄 flat 나열 → '지저분'. 상태 텍스트가 flex-wrap 툴바에 인라인(`margin-left:auto`)이라 내용 길이↑ → 툴바 wrap → 높이↑ → body(`flex:1`) 가 남은 높이 채워 캔버스가 위아래로 밀림(사용자 '아래 UI 지속 변형' 불만의 정확한 메커니즘).
- 변경: ① 툴바 4존 압축 + 보기옵션 팝오버(`.amg-viewopts*`) ② 줌 → 캔버스 좌하단 오버레이(`.admin-meta-graph-zoomctl` absolute) ③ 상태 → 캔버스 좌상단 오버레이 pill(`.admin-meta-graph-status` absolute·2줄 클램프·auto-fade) — 레이아웃 흐름 밖이라 reflow 0 ④ 캔버스 `.admin-meta-graph-canvas-wrap` 위치 컨텍스트(role=img 밖 형제 오버레이) ⑤ admin.js: `_metaGraphStatus` auto-fade·`_metaGraphSyncViewOptsBadge`·팝오버 토글·LOD `is-idle` 해제.
- behavior-neutral: 컨트롤 id 전량 보존(`getElementById` 바인딩 불변). 캐시버스터 styles.css/admin.js `20260709-graph-toolbar`.
- Files: `static/{admin.html,admin.js,styles.css}`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- Verification: `node --check` OK · 실 Windows Chrome 149 harness 렌더 실측 PASS · 디자인·correctness 적대 패널(REVIEW). POST-DEPLOY PB-0008 라이브(deploy_scope:included).

## CHG-20260709T120000-graph-toolbar-postverify (graph-toolbar POST-DEPLOY PB-0008 라이브 PASS 기록 — 비-정책 doc-only)
- 배포 ee54b1ff(soak PASS) 후 라이브 콘솔(`https://localhost/` → /admin → 그래프 뷰) PB-0008 실측 결과를 TEST.md §3 Run 에 POST-DEPLOY 갱신으로 append + TASK.md POST-DEPLOY 체크박스 [x]. 실측: toolbarKids=4·**reflow0=true**·팝오버 no-clip·pageerror 0(상세 TEST.md §3). 코드·자산 변경 0.
- Files: `docs/{TEST,TASK,MODIFY,REVIEW}.md` (doc-only). 원천 cycle: CHG-20260709-graph-toolbar-consolidate(코드) / 배포 ee54b1ff.

## CHG-20260710T230000-minimap-reuse (그래프 미니맵 전체-이미지 재사용 — web 자산, 정본 feature-0016 §70/ADR-034)
- 대상: `src/static/admin.js`(신규 `_metaMinimapGeomSig`·`_metaPatchMinimapReuse` + `_metaG6ApplyOnce` 서명 배선 + minimap 플러그인 `key:"minimap"` + init 직후 patch) + `src/static/admin.html`(버스터 `admin.js?v=20260710-minimap-reuse`) + 신규 `tests/headless/test_g6build_minimap_reuse.js`.
- 변경(frontend-only, cross-cut 코드 거주 — 기능 정본 feature-0016): G6 v5 minimap 플러그인의 전량 재복제 `renderMinimap()` 을 기하 서명 게이트로 감싸, 상태-only rebuild(선택/역할도착/busy)에서 미니맵 재복제를 skip(이미 그려둔 전체 이미지 재사용). 구성 변경 시엔 정상 재복제. 팬/줌은 원래도 G6 가 마스크만 갱신(무영향).
- 적대 리뷰 2건 BLOCK 적발→수정: H1(패치 init 시점 호출→plugin lazy-init 전 no-op) → draw 직후 이동, H2(네이티브 드래그 stale 서명→미니맵 얼어붙음) → afterdraw stage="translate" 서명 무효화.
- Verification: `node --check` OK · headless 신규 **35** + 회귀 150 PASS · 적대 패널(REVIEW). POST-DEPLOY PB-0008 라이브(deploy_scope:included, TEST §70).

## CHG-20260711T115053-docs-archive (MODIFY/REVIEW §5.5 아카이빙 — priming read-set 경량화)
- Date: 2026-07-11. AGENTS.md §5.5(20건 초과)·§5.6(50KB/400줄 임계 — MODIFY 5,589줄·REVIEW 4,650줄로 최대 위반) 적용, 사용자 지시("정책문서 분리/세분화")로 착수.
- Summary: 엔트리 verbatim 이관(원본 순서·내용 무변경) — MODIFY 408건·REVIEW 389건 → `_archive/<DOC>-archive-20260711T115053.md`(timestamp 규약 ADR-20260710T231146 첫 적용). 현행 파일 각 114줄로 경량화. 무손실 재구성 md5 증명.
- Files: docs/MODIFY.md · docs/REVIEW.md · docs/_archive/ 신설 2파일 · docs/REPORT.md(압축 정보) · docs/TASK.md.
- Rollback: 아카이브 내용을 링크 지점에 재삽입(verbatim 이라 무손실 복원 가능).
