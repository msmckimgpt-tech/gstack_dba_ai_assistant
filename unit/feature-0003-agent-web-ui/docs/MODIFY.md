---
doc_type: MODIFY
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---


# Modify Log

> 이전 기록(408건): [MODIFY-archive-20260711T115053.md](./_archive/MODIFY-archive-20260711T115053.md)

## CHG-20260814T160000-ask-result-job-backstop (cross-ref — conv-audit 봉인 B)

feature-0002 마찰 `FR-early-return-kv-never-finalized` → **코드 거주 primary 는
`feature-0002-agent-core`**(`CHG-20260814T160000-ask-kv-terminal-seal`, verify 도 그쪽). 본
feature 는 그 봉인의 **소비 지점**만 바뀐다:

- `src/routers/conversations.py::ask_result`: terminal 판정이 KV `last_status` **단일 소스**라,
  run 이 KV 를 마감하지 못하고 끝나면 45초 폴링이 무한 반복됐다(실측 15분+, stale 임계 18분까지).
  KV 판정 실패 시 `ask_jobs` terminal 을 **권위 backstop**으로 확인해 long-poll 을 푼다
  (5초 주기 — 매 tick 조회는 PG 연결 낭비). 활성 job 이 있으면 헬퍼가 `None` 을 주므로 진행 중
  답변을 끊지 않는다. 내부 attach 루프가 `job_id` 로 갖던 보증을 재접속 폴백 경로에 대칭 부여.
- `src/routers/_conv_store.py`: `_latest_ask_job_terminal()` 래퍼 신설(실패·미가용 시 `None` →
  종전 KV 판정만 사용, 회귀 0). `src/app.py`: 재수출 1줄.

## CHG-20260812T220000-attach-md-render-post — 배포본 실측 기록 (doc-only, 코드 변경 0)
- 배포본 `105fa2b7` 의 **실제 모듈**을 라이브에서 import 해 신규 배선 9축 도달을 단정(어긋나면 throw).
- 배포 품질: web-a/web-b 동일 SHA · 엣지 `no upstreams available` 0건(실 무중단).
- 미실측 2건 명시: 라이브 `.md` 첨부 조합 대조(타 사용자 데이터 접근이라 미수행) · 브라우저 실
  네트워크 요청 계측(도구가 CDP Network 미노출 — 방어는 구조와 DOM census 로 확인).

## CHG-20260812T203000-attach-md-render — 첨부 `.md` 마크다운 렌더 (Minor §12.3, frontend-only)
- **요청(재지시)**: "구문 색이 아니라, 실제 마크다운 구성으로 출력되도록 구현해주세요." (2026-08-12)
- **원인**: 선행 `CHG-20260812T183000-attach-md-highlight` 가 같은 요청을 **구문 하이라이트**로
  해석. 요청의 본질은 "포맷대로 보여 달라" 였다. 선행 작업은 유지한다 — 원문 보기(토글 off)와
  변경이 있는 diff 는 줄 대조가 목적이라 렌더하면 기능이 사라진다(두 모드의 관계).
- **Files**:
  - `src/static/app/attach-diff.js` — `MD_RENDER_KEY`·`_readMdRenderOn`/`_writeMdRenderOn` ·
    `_isMarkdownFile` · `_sourceText` · `_MEDIA_SEL`/`_isSameOriginOrInline`/`_hardenRenderedMarkdown` ·
    `_renderMarkdownInto` 신규 + `_renderSource` md 분기 + 두 모달(원문 보기·비교 identical)의
    `마크다운으로 보기` 토글·배너·재렌더 배선. `markdownToHtml` 을 `../app.js` 에서 import.
  - `src/static/css/chat.css` — `.attach-source-md`(+`h1~h6`·`blockquote`·`hr`·task·표 wrap) ·
    `.attach-source-md-blocked` · `.attach-source-md-tablewrap` 신규.
  - `tests/verify_attach_source_markdown.mjs` 신규(66) · `src/scenario.attach-md-render.json` 신규 ·
    `docs/test-runs.d/20260812T2030-attach-md-render.md` 신규.
- **설계 결정 3건**: ① **파이프라인 신규 제작 0** — 답변 말풍선과 같은 `markdownToHtml` 재사용
  (복제가 곧 결함 기전). ② **토글 기본 켬 + 원문 복귀 보존** — 요청은 렌더지만 원문 확인 수단을
  없애지 않는다(첨부는 계약 문서일 수 있어 바이트 그대로를 봐야 하는 상황이 있다).
  ③ **렌더 중 구문색 토글 숨김** — 칠할 원문 줄이 화면에 없어 거짓 어포던스가 된다.
- **보안(신규 표면이라 함께 넣음)**: 첨부 본문은 **사용자가 올린 임의 바이트**이고 그룹 멤버 전원이
  연다. sanitize 로 닫히지 않는 축은 **원격 리소스 fetch** — `![](https://attacker/x.gif)` 한 줄로
  열람자 IP·시각이 업로더가 고른 서버로 샌다(로드 자체가 신호). 응답 CSP 는 **report-only**(실측)라
  브라우저가 막지 않는다. → sanitize 이후 DOM 에서 교차 출처 미디어 중립화(URL 은 텍스트 칩으로
  노출·건수 배너) · `iframe/object/embed` 제거 · 외부 링크 `rel="noopener noreferrer nofollow"`.
- **codex 적대 리뷰 6라운드 [P1] 7건 전건 반영**(모두 실제 결함):
  ① URL 검사가 `src`/`data` 뿐이라 `srcset`·`poster`·`xlink:href` 우회 + 프로토콜 상대 URL(`//evil`)이
     `^https?:` 문자열 검사를 통과 → 다속성 검사 + **resolve 된 origin** 판정.
  ② **라이브 DOM 에 먼저 파싱한 뒤 제거**해 비콘이 이미 나간 뒤였다(기능 목적 자체를 무효화) →
     `<template>`(inert)에서 중립화한 **뒤** 라이브로 이동.
  ③ 공용 DOMPurify 프로필이 `style`/`form`/`input`/`action` 을 허용(CSS url 비콘·인증 앱 위 피싱) →
     **첨부 전용 좁은 프로필**(`_ATTACH_SANITIZE`) 2차 sanitize.
  ④ **mermaid 가 하드닝 이후 라이브 DOM 에 SVG 를 주입**하고 `themeCSS` 로 외부 `url()` 을 심을 수
     있었다 → 첨부 경로에서 mermaid 렌더 중단 + 코드블록 강등(inert 단계에서 변환).
  ⑤ **같은 출처 이미지를 허용**해 `![](/api/ai/oauth/authorize?redirect_uri=…)` 로 열람자 세션의
     인가 코드가 발급되는 **GET-CSRF** → 미디어 로드 허용을 **`data:image/` 로만** 축소.
  ⑥ 이미지 자동 GET 을 닫은 뒤에도 **같은 출처 링크 클릭**으로 열람자 권한이 쓰이는 경로가 남음 →
     같은 출처 링크는 **비활성화 + URL 텍스트 노출**(문서 내 앵커·`mailto:` 는 예외).
  ⑦ 사용자 HTML 의 `class` 가 앱 CSS 를 빌려 **UI 위장**(`share-mgr-backdrop` = 모달 배경) →
     렌더러 생성 클래스 allowlist + `id`/`name` 제거.
  부수로 GFM 체크박스가 `input` 금지에 걸려 **상태가 소실**되던 회귀를 글리프(`☑`/`☐`) 치환으로,
  콤마 분할이 `data:` URI 를 쪼개 **인라인 이미지까지 과잉 차단**하던 버그를 `srcset` 한정으로 해소.
- **검증**: 신규 하네스 **102 PASS**(스텁 아님 — `marked.umd.js`+`purify.min.js` 실제 로드) ·
  **뮤테이션 14종 전건 KILL**(살아남아 고친 검사 결함 3건은 TEST fragment 에 기록) ·
  형제 4종 회귀 0 · **PB-0008 실 Windows Chrome/150 PASS — 정본 `_renderMarkdownInto` 를 그대로
  실행**(초판 시나리오는 옛 취약 구현을 복제해 증거로 성립하지 않았음, 재작성 후 재실행):
  `renderOk` · `tasks 2/checked 1` · `mermaidCode 1/svg 0` · `inputs 0` · `remoteImgs 0` ·
  **`remoteAttrLeaks []`** · 위계 20>17>15>14px · `markersGone`. pytest 무관(`.py` 0).

## CHG-20260812T193000-attach-md-postverify — 배포본 실측 기록 (doc-only, 코드 변경 0)
- 선행 `CHG-20260812T183000-attach-md-highlight` 가 "배포 후에만 확인 가능" 으로 남긴 잔여를
  배포본 `d0241c93` 에서 닫는다. **코드·자산 변경 0** — 문서만.
- **Files**: `docs/test-runs.d/20260812T1830-attach-md-highlight.md`(POST-DEPLOY Run append) ·
  `docs/{TASK,REVIEW,REPORT}.md`.
- **실측 결과**: ① 시나리오 step 3 배포본 probe 가 `has_md: false → true` · `langs` 에 `md`
  추가로 뒤집힘(codex [P2-3] fail-open 종결, 재실행 가능한 게이트) ② 라이브 페이지에서
  `import('/static/code-highlight.js')` 한 **서빙 모듈로 직접 렌더** — computed 색 9종 정본
  일치 · 무손실 · span 외 태그 0 · `- |` 수정 배포본 확인 ③ 배포 품질 — web-a/web-b
  `GIT_COMMIT=d0241c93`, 엣지 `no upstreams available` **0건**(실 무중단).
- **미실측 잔여(명시)**: 라이브 `.md` 첨부의 원문 보기 모달을 실 계정으로 여는 **조합** 대조는
  타 사용자 대화 데이터 접근이라 수행하지 않음. 경로의 두 조각은 각각 실측 완료.

## CHG-20260812T183000-attach-md-highlight — 첨부 `.md` 구문 하이라이트 (Minor §12.3, frontend-only)
- **요청**: "프로젝트 내 서비스에서, 첨부파일 중 '.md' 파일에 대한 포멧도 내부적으로 처리할 수
  있도록 구성해주세요." (2026-08-12)
- **원인/범위**: `.md` 첨부는 서버 쪽에서 이미 전부 열려 있었다 — `_EXTENSION_KIND_MAP`(md·markdown
  → `text`) · `_MIME_KIND_HINTS`(`text/markdown`) · `_VERSION_DIFF_TEXT_KINDS`(text 포함) ·
  원문 보기 `ATTACH_SOURCE_VIEWABLE_KINDS` · `_ASSISTANT_NEW_ALLOWED_EXT`. 막힌 곳은 프론트
  `static/code-highlight.js` 의 `LANGS` **한 곳**뿐이었고, 그래서 `.md` 는 화면에서 구조가 산문과
  같은 색이었다. 선행 cycle `20260806T1853-attach-diff-syntax` 가 모듈 헤더에 예고한 확장분.
- **Files**:
  - `src/static/code-highlight.js` — `tokenizeMarkdown` 신규(블록 판정 `MD_FENCE_RE`·`MD_ATX_RE`·
    `MD_SETEXT_H1_RE`·`MD_RULE_RE`·`MD_QUOTE_RE`·`MD_LIST_RE`·`MD_TASK_RE`·`MD_REFDEF_RE` +
    `_mdIsTableDelimRow` / 인라인 `MD_INLINE_RE`·`MD_INLINE_NOLINK_RE` + `_mdEmphOk`),
    `LANGS.md = { label:"Markdown", exts:["md","markdown"] }`, 헤더 주석의 "차후 확장" 문구 갱신.
  - `src/static/css/base.css` · `src/static/css/chat.css` — **주석만** (팔레트 의미에 markdown
    역할 병기). **색 값·규칙 무변경** → 렌더 무변경, 하네스 G1(변수 9개)·G4·G5 유지.
  - `tests/verify_attach_diff_syntax_highlight.mjs` — markdown 축 29건 추가(113 → **142**),
    fuzz 알파벳에 `~|+` 추가.
  - `src/scenario.attach-md-highlight.json` — PB-0008 시나리오 신규.
  - `docs/test-runs.d/20260812T1830-attach-md-highlight.md` — Run 기록 신규.
- **설계 결정 3건**: ① **새 팔레트 변수 0** — 기존 9종 재사용(대비 계산 하네스 G2 의 검증면을
  넓히지 않는 편이 안전, AC-AVD-24 계약 상속). ② **`_강조_` 의도적 미지원** — 이 화면의 `.md` 는
  DB·SQL 문서가 다수라 `snake_case`·`__dunder__` 를 강조로 칠하면 없는 강조를 만든다("무색 > 오색").
  ③ **fence 내부는 markdown 규칙으로 읽힘을 수용** — 라인 독립 원칙(맥락 축약 뷰가 중간을 생략하므로
  상태 이어붙이기는 색이 통째로 어긋난다)의 기존 절충 유지, fence 줄 자체를 칠해 경계를 읽힌다.
- **성능**: 링크 대안이 2차 비용 지점이라 초판 `"[".repeat(4000)` **2.98ms**, 가드 우회형
  `…[[[[](x)` **2.18ms** → ① `](`·`)` 부재 시 링크 대안을 끈 정규식 ② 라벨·URL 200자 상한 +
  라벨에서 `[` 제외 ③ `[` 런·산문 런 대안 → **0.76ms**(최악) · 산문 920자 **토큰 1개 0.002ms**.
- **검증**: 하네스 **142 PASS/0 FAIL** · 형제 하네스 회귀 0(source-view 77 · version-diff 125 ·
  identical-source 61) · **PB-0008 실 Windows Chrome/150 PASS**(전용 프로파일·전용 CDP 포트로
  자기 인스턴스 확보, 배포 CSS 위 실 `attach-diff-code` 구조 렌더, computed 색 9종 정본 일치,
  판독가능 확대 캡처 3장). pytest 무관(변경 파일에 `.py` **0**).

## CHG-20260807T130000-reasoning-stop-reason-stage (AI 추론 콘솔 ② 단계가 중단 사유를 읽음, Minor)
- **cross-ref — 정본은 feature-0002-agent-core** `CHG-20260807T130000-redteam-abortable-review`
  (FR-redteam-first-pass-unabortable). 그쪽 변경으로 red-team 자가 검증이 사용자 '즉시 답변'이나
  대기 포기로 끝날 수 있게 됐는데, 그 행은 `verdict` enum 을 지키느라 `error` 로 남는다.
- `src/static/admin.js`: ② "적대 리뷰" 단계가 `it.stop_reason` 을 읽어 `aborted`(사용자 중단)·
  `review_wait_giveup`(리뷰어 지연으로 대기 포기)를 **`err` 가 아닌 `warn`** 으로, "리뷰 미완료 —
  <사유> (초안 그대로 전달)" 로 표시한다. 진짜 리뷰어 실패는 종전 문구·상태 유지(무회귀).
  `_REASONING_STOP_REASONS` 에 `review_wait_giveup` 라벨 신설.
- **왜(§18.8 backend 패널 MAJOR)**: 종전에는 `verdict === "error"` 를 **무조건** "리뷰 수행 실패"로
  렌더했고 `stop_reason` 라벨은 `unresolved > 0` 분기에서만 그려졌다. 중단 경로는 항상
  `unresolved_block_count = 0` 이라 기존 "사용자 '즉시 답변'/취소" 라벨이 **구조적으로 도달 불가**
  였다 — 정상적인 사용자 중단이 리뷰어 오류로 보이고, 그 오류율은 이 감사가 근거로 쓴 지표다.
- `tests/headless/test_reasoning_stop_reason_stage.js` 신규 — 실 소스에서 라벨 맵·라벨 함수·② 분기
  본문을 추출해 vm 으로 **동작 평가**(소스 문자열 검사는 변이를 통과시킨다). **13 PASS**,
  구동작 복원 시 **3 FAIL** 로 판별력 확인.
- 백엔드·스키마·RBAC·엔드포인트 변경 0.

## CHG-20260804T070000-prompt-autogen-postdeploy (POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-08-04. **코드 변경 0**.
- `feature-0003/docs/TASK.md` · `feature-0002/docs/TASK.md`: 선행 2 cycle 의 "배포 후 라이브 실증 대기"
  잔여 체크박스를 실증 결과로 종결(§5.6 staleness — 완료된 작업을 '대기'로 남기면 후속 세션을 오도).
- `feature-0003/docs/REPORT.md`: `[POST-DEPLOY 완결 2026-08-04]` 블록 추가 — 2단 배포 경과
  (`c4701a17` 1차 실증 실패 검출 → `fba8ee9f` 2차 PASS)와 실측 수치, 그리고 "스텁 경계가 결함 지점과
  겹치면 단위 테스트는 구조적으로 눈이 먼다" 는 교훈.
- Cross-ref: TASK-20260804T0454-prompt-autogen-wiring · TASK-20260804T0630-summary-bootstrap-deadlock ·
  REV-20260804T070000-prompt-autogen-postdeploy · PR #1135(`c4701a17`) · PR #1138(`fba8ee9f`).

## CHG-20260804T045449-prompt-autogen-wiring (사용자별 시스템 프롬프트 자동 생성의 끊긴 배선 복구, Major)
- `unit/feature-0002-agent-core/src/modules/llm.py`: `_summary_deps()` 신설 — `log_timing` /
  `load_memory_context` / `save_memory_summary` / `_record_step_summary` / `sanitize_user_text` /
  `_near_run_deadline` 을 함수-로컬 import 로 해소. 본 모듈은 그중 **어느 것도 import 하지 않아**
  `_refresh_summary_after_*` 가 호출 즉시 NameError 였다(호출자 0 이라 미검출). 두 레거시 진입점도
  이 해소를 쓰도록 수정. `refresh_conversation_summary(conversation_id, *, last_step_summary)`
  신설 — 답변 후 1회 요약 갱신, 게이트=기존 `AGENT_SUMMARY_REFRESH`, conn 불요(PG 런타임 백엔드),
  예외 흡수 후 bool 반환. `__all__` 에 등재.
- `unit/feature-0002-agent-core/src/agent_core.py`: `modules.llm.refresh_conversation_summary` 를
  `_refresh_conversation_summary` 로 alias import + `run_post_answer_curation()` 말미에서 호출.
  **이 한 줄이 W1 의 재연결점** — 이전까지 `agent_runtime.summary` 는 writer 가 없어 0행이었고,
  그 결과 제품·역할·개인 프롬프트 자동작성의 "실제 분석 사례 요약" 접지가 항상 비어 있었다.
- `unit/feature-0003-agent-web-ui/src/routers/_prompt_context.py`: `_SIGNAL_TOPIC_PLACEHOLDERS` /
  `_SIGNAL_TOPIC_GREETINGS` / `_SIGNAL_TOPIC_MIN_LEN`(2) / `_SIGNAL_TOPIC_MAX_LEN`(120) 상수 +
  `_normalize_signal_topics()` 신설. `_collect_conversation_signals_pg`(role/account) 와 제품
  인라인 topic 쿼리 양쪽에 적용, 원본 조회 창 `limit`→`limit*3`(제품은 50→150). SSE 실패 경로에
  `logging.warning` 추가(label·model·max_tokens·누적 길이·ctx·에러 / 본문 미기록).
- `unit/feature-0003-agent-web-ui/src/routers/admin_products.py`: `_prompt_generate_json_response`
  의 LLM 예외에도 동일 `logging.warning` — 502 응답만 돌려주던 종전엔 서버 추적 근거가 없었다.
- `unit/feature-0003-agent-web-ui/src/routers/admin_roles.py`: `admin_delete_role` 에
  `DELETE FROM WebSystemPrompts WHERE RoleId = %s` 추가(WebRolePermissions 정리와 같은 트랜잭션,
  `DELETE FROM WebRoles` 이전). 제품 삭제 경로에만 있던 정리 계약을 역할 경로에도 맞춘다.
- `unit/feature-0003-agent-web-ui/src/app.py`: `_normalize_signal_topics` · `_SIGNAL_TOPIC_MAX_LEN`
  을 `app.<name>` 으로 rebind(라우터·테스트 참조 보존 — 패치-단일점 규약).
- 테스트 신규 2파일 20건: `feature-0002/tests/test_summary_writer_wiring.py`(8),
  `feature-0003/tests/test_prompt_signal_hygiene.py`(12).
- **라이브 데이터 변경(1회)**: `WebSystemPrompts` 고아 3행(Id 2·28·46) DELETE. 사전 백업
  `artifacts/prompt-autogen-wiring/orphan-system-prompts-backup-20260804.json`. 사용자 승인
  (AskUserQuestion 2026-08-04 "배선 + 기존 고아행도 정리"). 잔존 고아 0 확인.
- RBAC·스키마·엔드포인트·프론트 무변경. Cross-ref: TASK-20260804T0454-prompt-autogen-wiring ·
  REV-20260804T045449-prompt-autogen-wiring · feature-0002 TASK/MODIFY.

## CHG-20260730T162000-test-isolation-hardening (테스트→라이브 오염 재발 차단: 도달성 층 + fail-loud + 감지, Major)
- `Makefile`: `TEST_COMPOSE_PROJECT`/`DC_TEST` 신설 — `test` 타깃을 **전용 compose 프로젝트**
  (`-p repo-unittest`)로 실행. 테스트 컨테이너가 자기 네트워크로 떠서 라이브 `mysql`/`pgbouncer`
  가 DNS 로 해석되지 않는다. `-p` 가 외부 `COMPOSE_PROJECT_NAME` 을 이기므로 재발 벡터
  (`COMPOSE_PROJECT_NAME=repo make test`)가 무효화된다. `dc-build` 도 같은 프로젝트로 호출
  (`DC_QUIET="$(DC_TEST)"` 전달).
- `conftest.py`(루트): ① `DB_PORT=1` 격리를 파일 쪽으로 이관 — 하네스 밖(로컬 `pytest`)에서도
  memory MySQL 이 막힌다(종전엔 Makefile 만 담당). ② `_assert_live_stack_unreachable()` 추가 —
  라이브 스택 네트워크 안에서 실행 중이면 **collection 단계에서 RuntimeError 로 중단**. probe 는
  env 가 아니라 3306 리터럴을 쓴다(위에서 DB_PORT 를 덮으므로 env 기반은 동어반복).
  `AGENT_TEST_ALLOW_LIVE_BACKENDS=1` 예외는 기존 계약 그대로.
- `bin/check-test-contamination.sh` **신설** — audit 의 `RemoteAddr=testclient` 유입을 조회해
  키별로 현재 라이브 값 / 테스트가 쓴 값 / 사람 최종 설정값을 대조, 오염 잔존 시 exit 1.
  하루 방치된 탐지 지연(재발 사건의 실제 피해)을 겨냥한 층.
- **코드(제품) 변경 0**. 라이브 검증: `COMPOSE_PROJECT_NAME=repo` 를 일부러 준 채 전량 실행 —
  `WebRuntimeSettings` 해시 불변 · `testclient` audit 신규 0건 · 전량 통과(FAILED 0).
- Cross-ref: TASK-20260730T1620-test-isolation-hardening · REV-20260730T162000-test-isolation-hardening ·
  선행 CHG-20260729T141200-test-live-db-isolation(값 방어 층).

## CHG-20260730T160500-progress-enqpre-handoff-postdeploy (POST-DEPLOY 라이브 AFTER 대조 기록, doc-only)
- `unit/feature-0003-agent-web-ui/docs/test-runs.d/20260729T201000-progress-enqpre-handoff.md`:
  POST-DEPLOY Run append — BEFORE/AFTER 동일 시나리오 대조표(추적 id·프론트 steps·화면 단계),
  실 화면 스크린샷 대조, 큐 대기 구간 상태 라벨 변화 부기, P1-1 라이브 미재현 사유.
- `docs/TASK.md`: 잔여 체크박스 2건(`make test`·PB-0008) 완료 표시 + 실측 요지.
- `docs/REPORT.md`: "잔여: POST-DEPLOY PB-0008" → 실측 PASS 결과 + 후속 과제(서버 `run_is_mine`) 명시.
- **코드 변경 0**.

## CHG-20260729T201000-progress-enqpre-handoff (enqueue sentinel → 실제 run 승계, Major)
- `unit/feature-0003-agent-web-ui/src/static/app.js`
  - `ENQUEUE_SENTINEL_RUN_PREFIX = "enqpre-"` + `_isEnqueueSentinelRunId()` / `_adoptRunId()` 신설
    (서버 `routers/_conv_store.py` 의 `"enqpre-" + uuid4().hex` 계약과 짝).
  - `resetProgressTracking`: `state.progressRunId = _adoptRunId(...)` — **추적 id 채택의 단일
    choke-point**. 전송 직후·`loadHistory` `last_run_id`·`ask_status` attach 전 경로 커버.
  - `applyProgressPayload`: run 채택 `_adoptRunId(runId)` · `pendingBubble.runId` 동일 필터 ·
    foreign-run 가드에 `!_isEnqueueSentinelRunId(state.progressRunId)` 2중 방어 추가.
  - `startProgressPolling`: 전환 판정을 채택값(`_wantedRunId`) 기준으로 — sentinel 이 reset 을
    유발해 진행 중 steps 를 비우지 않는다.
  - `loadHistory` processing 분기: `pendingBubble.runId = _adoptRunId(payload.last_run_id)` +
    `reset: _adoptRunId(payload.last_run_id) !== state.progressRunId`.
- `unit/feature-0003-agent-web-ui/tests/verify_enqpre_run_handoff.mjs` **신설**(27 단언) —
  sentinel 미채택 · **sentinel→실제 run 승계 + steps 반영** · 그룹 foreign 무시 보존 · terminal
  통과 보존 · 2중 방어 · 채택 규약 · 정적 계약.
- (codex P1-2) `attachAndWaitForResult`: 진입 `currentRunId = _adoptRunId(runId)` + timeout 응답의
  실제 run 승계(`_served`) — sentinel 을 실으면 `/api/ask_result` 가 영원히 timeout 돼 attach 가
  1800s 상한까지 유지되고 busy/myAskInFlight 가 잔류했다. 호출부 3곳(복구·resume·새로고침 복원
  `pendingBubble.runId`)도 정제 경유.
- (codex P2) `loadHistory` reset 판정: `Boolean(_adoptRunId(last_run_id)) && …` — sentinel 이
  정상 추적 중인 실제 run 의 steps·after_step 을 리셋하던 것 차단.
- 백엔드·RBAC·스키마·엔드포인트·alembic 변경 **0**. 그룹 foreign-run 불변식 무손상.

## CHG-20260729T183000-progress-poll-resilience-postdeploy (POST-DEPLOY 라이브 검증 기록, doc-only)
- `unit/feature-0003-agent-web-ui/docs/test-runs.d/20260729T175000-progress-poll-resilience.md`:
  POST-DEPLOY Run append — 1차(실 사용자 경로 무회귀) · 2차(순단 3연속 실패에도 폴링 생존 + 백오프
  8→16→32s 실측 · 폴러 강제 사망 → 감지기 15초 내 복구 · run_id 유지) · 3차(`online` 훅 4초 내 재개).
- `docs/TASK.md`: 잔여 체크박스 2건(`make test` 회귀 · PB-0008 라이브) 완료 표시 + 실측 요지.
- `docs/REPORT.md`: "잔여: POST-DEPLOY PB-0008" → 실측 PASS 결과 + 미실증 항목 명시로 교체.
- **코드 변경 0**.

## CHG-20260729T175000-progress-poll-resilience (진행 폴링 영구 정지 → 자가 회복, Major)
- `unit/feature-0003-agent-web-ui/src/static/app.js`
  - `PROGRESS_POLL_ERROR_MAX_MS = 60000` 신설(오류 백오프 상한).
  - `pollProgress` catch: `shouldSchedule = … && state.progressErrorCount < 3` → **연속 실패에도
    항상 재스케줄**(활성 대화가 있는 한). 간격은 `PROGRESS_POLL_ERROR_MS * 2^(n-1)` 를 상한으로
    clamp(지수 백오프). 숨김 탭은 종전대로 `PROGRESS_POLL_HIDDEN_MS` 하한 적용.
  - `detectNewRun` dormant 판정: `progressRunId || pendingBubble || progressPoller ||
    progressPollInFlight || runDetectInFlight` → **`progressPoller || progressPollInFlight ||
    runDetectInFlight`**(폴러 생존 사실만). fetch 후 재확인 가드도 동형으로 교정.
  - `detectNewRun` baseline 첫 폴 분기: `rawStatus === "processing" && runId && runId !==
    state.progressRunId` → `rawStatus === "processing" && runId` (죽은 폴러가 추적하던 같은 run
    도 회복 대상에 포함).
  - `loadHistory` processing 분기: `if (!append) stopRunDetectPolling();` →
    `if (!append) startRunDetectPolling();` (감지기를 watchdog 으로 무장).
  - `scheduleProgressPolling` / `scheduleRunDetectPolling` 의 `setTimeout` 콜백이 진입 즉시
    `state.progressPoller = null` / `state.runDetectPoller = null` 로 소진된 tick 참조를 정리.
  - `visibilitychange` 재가시 분기: 판정에 `display_status`·`pendingBubble` 포함, 감지기 재무장을
    `else if` → 독립 `if` 로 분리(처리 중 대화에서도 watchdog 유지).
  - `online` 이벤트 리스너 신설 — 회선 복구 시 백오프 대기 없이 폴링·감지기 즉시 재무장.
  - (codex P1) `detectNewRun` dormant 가드 직후 분기 신설 — `state.progressRunId` 가 있으면
    **fetch 없이** `startProgressPolling({reset:false, runId})` 재기동 + 감지기 재스케줄 후 return.
    감지 fetch 는 `client_run_id` 미포함이라 그룹 대화에서 foreign run 을 받아 `loadHistory` 가
    폴링을 남의 run 으로 갈아태우는 경로를 원천 차단(내 run 의 per-run terminal marker 보존).
  - (codex P2) `state.runDetectAbortController` 신설 — `detectNewRun` 이 controller 를 state 에
    걸고, `stopRunDetectPolling` 이 abort + 참조 해제, `finally` 는 자기 controller 만 정리.
- `unit/feature-0003-agent-web-ui/tests/verify_progress_poll_resilience.mjs` **신설**(34 단언) —
  실패 지속·백오프 곡선·성공 리셋·watchdog 회복·정적 배선 계약.
- `unit/feature-0003-agent-web-ui/tests/verify_run_detect_poll.mjs` — 옛 계약 단언 6건을 새 계약으로
  갱신(S4 폴러 생존 기준 · S4b watchdog 회복 신설 · S6 in-flight 기준 · 정적 배선 3건).
- 백엔드·RBAC·스키마·엔드포인트·alembic 변경 **0**.

## CHG-20260729T141200-test-live-db-isolation (`make test` 의 라이브 컨트롤플레인 쓰기 차단, Major)
- `unit/feature-0003-agent-web-ui/tests/conftest.py`: autouse fixture `_no_live_memory_conn` 신설 —
  `app._connect_memory` 를 monkeypatch 로 차단(raise). memory DB 커넥션 단일 진입점이라 `get_conn`
  DI 경로 + 핸들러 내부 직접 호출을 한 번에 덮는다. 모듈 docstring 의 "lifespan 미발화 → DB 미접속"
  전제도 정정(요청 스코프 Depends 라 성립 안 함).
- `unit/feature-0003-agent-web-ui/tests/test_live_db_isolation.py` **신설** — 진입점 차단·저장 경로
  500·스냅샷 경로 비-`/shared` 3계약을 회귀 가드로 고정(사고 경위를 파일 docstring 에 보존).
- `unit/feature-0003-agent-web-ui/tests/test_runtime_settings_api.py`: 저장 경로 assert 를
  `in (200,500)` → **`== 500`** 으로 좁힘(3곳) + 실패 메시지가 라이브 오염을 직접 지목. `default`
  (env 반영 baseline)에 60 을 요구하던 환경 의존 assert 를 `code_default` 로 이관.
- `Makefile`: `TEST_ISOLATION_ENV` 신설(`DB_PORT=1` + `RUNTIME_SETTINGS_SNAPSHOT_PATH=/tmp/...`)을
  `test` 타깃에 주입. `DB_HOST` 는 의도적 비변경(SSRF allowlist implicit 등록 — TASK-0214 간섭).
- (cross-unit) `unit/feature-0002-agent-core/tests/test_runtime_settings.py`: `monkeypatch.delenv`
  로 스냅샷 부재 폴백 테스트를 env-agnostic 화.
- (후속 정정) 스냅샷 경로 가드의 강제 조건을 `isdir("/shared")` → **`exists("/shared/runtime_settings.json")`**
  으로 교체 — CI 러너가 `SESSION_DIR.mkdir()` 용으로 빈 `/shared` 를 만들어(ci.yml) 오염 표면이
  없는데도 가드가 발동해 PR #1048 이 거짓 red 였다. "덮어쓸 대상 실재" 가 정확한 판별이며,
  Makefile env 누락 회귀는 그대로 잡힌다(양방향 실증 — Run fragment §E).
- **코드(제품) 변경 0** — 테스트 인프라·빌드 진입점만. 라이브 검증: `COMPOSE_PROJECT_NAME=repo`
  전량 실행 후 `WebRuntimeSettings` 해시 불변 + `testclient` audit 신규 0건.
- Cross-ref: TASK-20260729T1412-test-live-db-isolation · REV-20260729T141200-test-live-db-isolation.

## CHG-20260728T172000-graph-hover-flow-postverify (TASK 20260728T1628-graph-hover-flow POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- `docs/test-runs.d/20260728T172000-graph-hover-flow-postdeploy.md` 신설 — 배포(main `b36493a9`)·서빙 baked 2중 확인·PB-0008 10 시나리오·evidence 4매(+원본 프레임 전량).
- TASK/REVIEW 에 POST-DEPLOY 항목 추가. **코드·자산 변경 0**.
- 사전 Run(격리 컨테이너, stamp `28b8c65898a7`)과 절대 수치는 캔버스 해상도·줌 차이로 다르나 **구조 전건 동일**(방향 축 비-0 + 화살촉 반전 · 읽기/쓰기 대량 분리 · 흐름 프레임차 비-0 · 잔재 0) — 빌드 파이프라인 통과 산출물에서도 동일 코드 서빙 실증.
- 드라이버 실측 2건 기록: **"가장 큰 canvas" 휴리스틱이 위장 0-diff 를 만든다**(콘솔 리셋 시 대시보드 차트를 집음 → 첫 1:1 줌 측정 전건 폐기·재측정) → 캡처를 `#metadataGraphCanvas` 하위로 못 박고 그래프 가시성·상태줄 동시 기록 / 공유 Chrome 탭 하이재킹 → 전용 마커 URL(`?pb=hoverflowpost`) 핀 고정.
- Cross-ref: CHG-20260728T1628-graph-hover-flow · REV-20260728T172000-graph-hover-flow-postverify.

## CHG-20260728T163800-graph-catcluster-focus-postverify (TASK-20260728T160000 POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- `docs/test-runs.d/20260728T163800-graph-catcluster-focus-postdeploy.md` 신설 — 배포(main `f25c71bf`)·서빙 baked 2중 확인·PB-0008 5 시나리오·evidence 4매.
- TASK/REVIEW 에 POST-DEPLOY 항목 추가. **코드·자산 변경 0**.
- 사전 Run(격리 컨테이너)과 수치·문구 전건 동일 — 빌드 파이프라인 통과 산출물에서도 동일 코드 서빙 실증.
- Cross-ref: CHG-20260728T160000-graph-catcluster-focus · REV-20260728T163800-graph-catcluster-focus-postverify.

## CHG-20260728T170000-graph-catcluster-polish-postverify (TASK-20260728T162000 POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- `docs/test-runs.d/20260728T170000-graph-catcluster-scroll-polish-postdeploy.md` 신설 — 배포(main 9c434809)·서빙 baked·PB-0008 5 시나리오·evidence 3매. **코드·자산 변경 0**.
- 드라이버 실측 2건 기록: 공유 Chrome 병렬 점유로 `pages[0]` 하이재킹 → **전용 새 탭** 드라이버로 회피 / 관리 콘솔 탭 전환은 **trusted click + `wait_until='load'` + 부트스트랩 대기** 필요.
- Cross-ref: CHG-20260728T162000-graph-catcluster-scroll-polish · REV-20260728T170000-graph-catcluster-polish-postverify.

## CHG-20260728T162000-graph-catcluster-scroll-polish (TASK-20260728T162000 — 스크롤 280ms EaseOutExpo + 헤딩 점멸/멤버 파도, Minor §12.3, frontend-only)
- `src/static/graph/graph-ctxmenu.js`: `_META_PANEL_SCROLL_MS = 280` + **`_metaEaseOutExpo`** + **`_metaAnimatePanelScroll(box, from, to, seqOf, reduce)`**(rAF 구동, 세대 토큰으로 진행 중 중단) 신설 — `scrollTo({behavior:'smooth'})` 대체. 목표에 `maxTop` 클램프 추가. 파도 연출: `_META_WAVE_MAX/STEP_MS/LEAD_MS/DUR_MS` 상수 + `_metaWaveNodes` 원장 + **`_metaClearPanelWave()`** + **`_metaRunPanelWave(target, reduce)`**(헤딩 `.is-focus`, 멤버 행 `.is-wave` + `animation-delay` + `--amgr-wave-a` 선형 감쇠 주입, 다음 헤딩 경계/접힘 행 제외/상한 24). `_metaGraphFocusPanelGroup` 이 이 둘을 호출하고 총 길이 후 정리 타이머 예약.
- `src/static/graph/graph.css`: `.amgr-ct-group.is-focus` → `amgrCtGroupFocus` **760ms 2회 점멸**(12~30% 강 / 46% 감쇠 / 62% 재점등). `.amgr-ct-row-li.is-wave` + `@keyframes amgrCtRowWave`(420ms, `rgba(37,99,235, var(--amgr-wave-a))`) 신설. reduced-motion 분기에 파도 정지 추가.
- `tests/headless/test_catcluster_panel_scroll.js`: rAF/`performance.now` test double 로 프레임 구동 재작성 + 파도/곡선/클램프/선점 단정 추가 — **36 → 65 PASS**.
- docs: TASK/FUNCTION/REPORT/REVIEW + `test-runs.d/20260728T162000-graph-catcluster-scroll-polish.md`, `docs/STATUS.md`.
- Verification: 헤드리스 65 PASS + 회귀 328 PASS · `node --check`(ESM) OK · **PB-0008 실 Windows Chrome**(격리 컨테이너 :18099, §13.2.9) — 스크롤 샘플 t=420ms 2,147 → t=827ms 1,698 정착 · 파도 delay `90/116/142/168ms` · alpha `0.500/0.333/0.167/0.000` · 31-멤버 그룹에서 파도 프레임 캡처 · 잔여 0 · 콘솔 에러 0.
- Rollback: static 2파일 + 테스트 1파일 revert (데이터·API·스키마·RBAC 영향 0).
- Cross-ref: REVIEW REV-20260728T162000-graph-catcluster-scroll-polish · `docs/test-runs.d/20260728T162000-graph-catcluster-scroll-polish.md` · FUNCTION REQ-20260728T162000(AC-CPS-5~8) · 선행 CHG-20260728T152000-graph-catcluster-panel-scroll · 정본 곡선 REQ-20260629-point-scroll(`app.js`/`share.js`).

## CHG-20260728T161326-graph-analyzed-halo-fit (TASK-20260728T161326 — AI 분석 완료 컬럼 노드 상태 테두리 기하 보정, Minor §12.3, frontend-only)
- `graph-renderer-pixi.js` `PixiAdapterPure`: **`haloGeom(n, i, lineWidth)`** 신설 — 노드 모양(`type==="circle"` → 원형 / 그 외 rect)과 크기 비례 계수 `k = clamp(min(w,h)/24, 0.4, 1)` 로 `{shape, r|x,y,w,h,radius, lw}` 산출. 여백 `max(1.5, 3k)`, 동심링 오프셋 `i·2k`, 두께 `max(1, lineWidth·k)`. rect 는 k=1 이라 종전 하드코딩(`-w/2-3-2i` · `radius+2+i·2` · lw 그대로)과 **수치 동일**.
- `graph-renderer-pixi.js` `PixiAdapterPure`: **`dashArcs(r, dash)`** 신설 — 호 길이 기준 [on,off] 반복을 라디안 구간 `[[a0,a1],…]` 로 반환(각도 = 호길이/r → 직선 `dashSegments` 와 같은 화면 대시 길이).
- `graph-renderer-pixi.js` `PixiGraphAdapter._applyNodeStates`: 하드코딩 rect 기하 제거 → `haloGeom` 소비. circle 은 `g.circle()`, circle+점선은 `moveTo().arc()` 반복, rect 는 종전 `roundRect`/4변 대시 경로 유지. 미사용이 된 지역 `w`/`h`/`s` 정리.
- `tests/headless/test_pixi_adapter.js`: **T27 신설 15건** — rect 회귀 0(i=0·i=1 좌표·radius·lw 전건), circle 원형/비례 두께/외곽 상한/동심링 간격/size 폴백/type 미지정 rect 경로/두께 하한, dashArcs 총 on 길이·단조·상한·1바퀴. 205 PASS.
- docs: TASK/FUNCTION/REPORT/REVIEW + test-runs.d fragment.
## CHG-20260728T160000-graph-catcluster-focus (TASK-20260728T160000 — 접힌 카테고리 클러스터 하위 테이블 추적 카메라 승격 교정, Minor §12.3, frontend-only)
- `src/static/graph/graph-core.js`: **`_metaGroupElementFor(tableKey)`**(테이블·루틴 → 소속 컨텐츠 카테고리 블록 `GB:<groupKey>`, `groupOf` 역참조 + `renderedIds` 게이팅) · **`_metaCategoryElementFor(schemaKey)`**(스키마 클러스터 → 소속 제품 카테고리 밴드 `CAT:<catKey>`, `catMembers` 역탐색 + `renderedIds` 게이팅) · **`_metaAncestorKindKo(elId)`**(승격 대상 → 한글 명칭) 신설. `_metaRenderedAncestorFor` 사다리를 `컬럼 → 소속 테이블 → 컨텐츠 카테고리(GB:) → 스키마 클러스터(combo | SC:) → 제품 카테고리 밴드(CAT:)` 로 확장. `_metaGraphAnimateFocusRun` 의 앵커 해소(본 루프 + API 부재 폴백 번들 경로 양쪽)에 `|| _metaRenderedAncestorFor(key)` 폴백 추가 — 모델 키로 들어오는 호출(관계 추적 등)이 미렌더일 때 1.2s 헛돌다 카메라가 안 움직이던 사각 해소. export 에 `_metaAncestorKindKo` 추가.
- `src/static/graph/graph-ctxmenu.js`: `_metaAncestorKindKo` import. `_metaGraphPanToRelation` 승격 안내와 `🎯 이 노드로 이동`(`#metaGraphFocusSelBtn`) 폴백 안내가 **실제 승격 대상 종류**를 표기하도록 교체(종전 "소속 테이블" 단정은 컨텐츠/제품 카테고리·스키마 클러스터로 갔을 때 오안내).
- `tests/headless/test_graph_ancestor_focus.js` 신설 — 소스에서 5개 함수 본문 추출 + vm 격리 실행으로 사다리 5단 전수·두 접힘 계층·stale 역인덱스 게이팅·명칭 매핑·자동펼침 부재를 단정. **31 PASS / 0 FAIL**.
- docs: TASK/FUNCTION/REPORT/REVIEW + `test-runs.d/20260728T160000-graph-catcluster-focus.md`, `docs/STATUS.md`.
- **동작 불변 영역**: 접힘이 없는 경로·접힌 스키마 카드(`SC:`) 승격·컬럼→테이블 승격은 종전 그대로. 승격은 시선 이동만 하고 `groupCollapsed`/`catCollapsed`(사용자 지속 의도)를 건드리지 않는다.
- Cross-ref: REV-20260728T160000-graph-catcluster-focus · 선행 CHG-20260728T152000-graph-catcluster-panel-scroll(같은 카테고리 클러스터 계층의 패널 스크롤 동기화).

## CHG-20260728T153500-graph-catcluster-scroll-postverify (TASK-20260728T152000 POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- `docs/test-runs.d/20260728T153500-graph-catcluster-panel-scroll-postdeploy.md` 신설 — 배포(main 4a0174e5)·서빙 baked 확인·PB-0008 4 시나리오·evidence 3매.
- TASK/REVIEW 에 POST-DEPLOY 항목 추가. **코드·자산 변경 0**.
- 관측 차이 기록: 사전 격리 컨테이너 Run 은 이력 바 표시(navH 47)로 `+53px`, 배포본 Run 은 이력 바 숨김으로 `+6px` — 보정식이 nav 높이를 실측하므로 양쪽 모두 설계대로.
- Cross-ref: CHG-20260728T152000-graph-catcluster-panel-scroll · REV-20260728T153500-graph-catcluster-scroll-postverify.

## CHG-20260728T152000-graph-catcluster-panel-scroll (TASK-20260728T152000 — 캔버스 컨텐츠 카테고리 선택 → 스키마 클러스터 목록 스크롤 동기화, Minor §12.3, frontend-only)
- `src/static/graph/graph-ctxmenu.js`: `_META_GKEY_SEP` 상수 + **`_metaGroupFam(groupKey)`**(구분자 뒤 fam 추출) + **`_metaGraphFocusPanelGroup(fam)`**(`ul.amgr-cluster-tables` 안에서 같은 fam 헤딩 탐색 → aside `scrollTop` 국소 계산(sticky nav 높이 + 6px 보정) → `scrollTo({behavior:smooth|auto})` → `.is-focus` 1.8s 강조 → 매칭 라벨 반환) 신설. `_metaGraphShowClusterDetailById(comboId, focusFam)` / `_metaGraphRenderClusterDetail(…, routines, focusFam)` 에 optional 파라미터 추가 및 전달. 클러스터 상세 상태줄에 `목록을 '<라벨>' 위치로 이동` 접미. 컨텐츠 카테고리 우클릭 메뉴 '소속 스키마 상세' 가 fam 을 함께 전달(hint 문구도 `이 카테고리 위치로 목록 이동` 으로 갱신).
- `src/static/graph/graph-core.js`: GB/GH 좌클릭 라우팅이 `_metaGraphShowClusterDetailById(sc, gk.slice(sep + 1))` 로 fam 동반 호출.
- `src/static/graph/graph-state.js`: `_panelFocusSeq` 세대 토큰 추가(연타 시 rAF 안의 stale 스크롤 폐기 — `_opSeq` 와 동형, 패널 스크롤 전용).
- `src/static/graph/graph.css`: `.amgr-ct-group.is-focus` + `@keyframes amgrCtGroupFocus`(배경 `#dbeafe` + 좌측 3px primary 바 → 1.8s 페이드) + `prefers-reduced-motion: reduce` 정적 강조 분기. `:hover` 규칙 뒤에 배치해 배경 경쟁을 피한다.
- `tests/headless/test_catcluster_panel_scroll.js` 신설 — 소스 추출 + vm 격리 실행으로 fam 대조·목표 좌표·nav 보정·클램프·세대 토큰·graceful no-op·reduced-motion·**호출부 인자 매핑**·CSS 클래스 존재를 단정. **36 PASS / 0 FAIL**.
- docs: TASK/FUNCTION/REPORT/REVIEW + `test-runs.d/20260728T152000-graph-catcluster-panel-scroll.md`, `docs/STATUS.md`.
- Verification: 헤드리스 36 PASS(신규) + 78/190 PASS(회귀) · `node --check`(ESM) OK · **PB-0008 실 Windows Chrome**(격리 컨테이너 `web-catcluster-test`:18099, §13.2.9 — 라이브 web-a/web-b 무접촉) 7 시나리오 PASS · 콘솔 에러 0 · 스크린샷 5매.
- Rollback: static 4파일 + 테스트 1파일 revert (데이터·API·스키마·RBAC 영향 0).
- Cross-ref: REVIEW REV-20260728T152000-graph-catcluster-panel-scroll · `docs/test-runs.d/20260728T152000-graph-catcluster-panel-scroll.md` · FUNCTION REQ-20260728T152000-graph-catcluster-panel-scroll(AC-CPS-1~4) · 선행 `graph-funcproc(cluster-detail-fulllist)`(그룹당 캡 제거) · `graph-content-category`(3층 우클릭 분리).

## CHG-20260728T161940-routine-column-edges (TASK-20260728T161940 — 사용 관계선 컬럼 단위 연결, Major §12.3, cross-cut 코드 거주)
- `graph-core.js`: 빌드의 ROUTINE_USES 분기에 **컬럼 분해** 추가 — `resolveColId(tableId, col)`(Column 키 규약 `<테이블 키>.<컬럼명>` + 소문자 인덱스 lazy 케이스 보정)로 렌더 중인 컬럼을 해소해 컬럼별 엣지(`id + "::c::" + 컬럼`)를 방출하고, 미렌더 컬럼 몫은 테이블로 relation_type 별 1선(`::t::<kind>`) 승격. **렌더된 컬럼이 0이면 분해 자체를 포기**해 접힘 상태는 완전 불변.
- `graph-ctxmenu.js`: 모델 엣지에 `ref_columns` 보존 + 상세 패널 사용 관계 행에 참조 컬럼 병기(`_META_RTCOL_SHOW=8`, `✎`=쓰기, `.amgr-rtcols`).
- (백엔드 feature-0002) `routines.py`: `parse_referenced_columns`·`_alias_map`·`_fetch_columns` 신설 + `introspect_and_store` 2-pass 화 → `referenced_tables[].cols`. `metadata_graph.py`: `ROUTINE_USES` 속성 `ref_columns` 투영 + `schema_tables`/`neighborhood` 응답 동봉 + `_ref_columns_of` 정제.
- (백엔드) `metadata_graph.routine_refs_signature`: 서명에 `cols` 포함 — 병합된 feature-0030 cyvol 재작성-생략 최적화가 컬럼 정보를 서명 밖에 두면 기존 routine 의 `ref_columns` 가 영영 투영되지 않는다(배포 후 첫 sync 1회 재작성 = backfill, §16.3 blast-radius 유한).
- `tests/headless/test_graph_routine_colref.js` 신규 30 PASS · (feature-0002) `tests/test_routine_column_refs.py` 신규 27건.
- docs: TASK/FUNCTION/REPORT/REVIEW + `test-runs.d/20260728T161940-routine-column-edges.md`.
- Verification: 그래프 헤드리스 18 스위트 0 FAIL(722 PASS) · 전체 pytest 2740 passed/15 failed(baseline, main 대조 동일) · ruff PASS · **PB-0008 실 Windows Chrome 150**(격리 harness, 라이브 무접촉) 접힘/펼침 대조 PASS · pageerror 0.
- Rollback: static 2파일 + 백엔드 2파일 + 테스트 2파일 revert (alembic 마이그 0 · RBAC/엔드포인트 계약 무변경 · `cols`/`ref_columns` 는 부재 시 종전 동작과 동치).
- Cross-ref: REVIEW REV-20260728T161940-routine-column-edges · FUNCTION REQ-20260728T161940-routine-column-edges(AC-RCE-1~5) · 정본 feature-0016 MODIFY CHG-20260728T161940-ai-claude-feature-0016-routine-column-edges.

## CHG-20260728T152141-graph-edge-hairline (TASK-20260728T152141 — 줌아웃 관계선 hairline 처리, Minor §12.3, frontend-only)
- `graph-renderer-pixi.js`: `edgeModelWidth` → **`edgeHairline(baseScreen, zoom, dpr)`** — 서브픽셀이면 폭을 `1/dpr` CSS px(=1물리픽셀)로 올리고 `fade = w_screen·dpr` 를 반환. `_paintEdge` 가 `alpha *= hair.fade` 로 합성하고 dpr 은 `app.renderer.resolution` → `window.devicePixelRatio` 순으로 해석.
- `graph-roleviz.js`: `_META_EDGE_W_BASE` 0.6→**1.0**, `_META_EDGE_W_GAIN` 0.25→0.27, 상한 표기 2.2→2.6px(개수 축 1.00/1.54/2.08/2.60).
- `tests/headless/test_graph_edge_flow.js`: A13 신설 6건(무보정·폭 승격·alpha 보상·극단 줌아웃 폭 유지·alpha 단조·고DPI 임계), A11 을 실효 잉크량(폭×alpha) 기준으로 재작성, B1/B2/B4/C0·edge_visibility T1 기대치 갱신 — 73 PASS.
- docs: TASK/FUNCTION/REPORT/REVIEW + test-runs.d fragment.

## CHG-20260728T142745-graph-edge-encoding (TASK-20260728T142745 — 줌 두께 정책 구간 분리 + 인코딩 축 재배치, Minor §12.3, frontend-only)
- `graph-renderer-pixi.js`: `edgeScreenScale`(§85) → **`edgeModelWidth(baseScreen, zoom)`** — `clamp(base·min(1, zoom/EDGE_ZFULL), EDGE_MIN_SCREEN_W, base)/zoom`. 상수 `EDGE_ZFULL=1`·`EDGE_MIN_SCREEN_W=0.25`. 화살촉·다발 간격은 실효 배율(`lw/base`) 공유.
- `graph-roleviz.js`: `_metaEdgeStrands` 폐지 → **`_metaEdgeWidthFor(count)`**(0.6 + min(1.6, log2(n)·0.25)) 신설·export. `_metaEdgeFlow` 는 곡선 키만 주입(다발 제거). 세 스타일 함수 재작성 — 굵기=개수 축 공통, 진하기=신뢰도(trusted 0.85 / 루틴 0.72 / candidate 0.5 / crossDs 0.5 / inferred 0.38 / SCHEMA_REF 중립 0.55).
- `graph-core.js`: import 에 `_metaEdgeWidthFor` 추가, USES 사용선 굵기를 개수 축(`_metaEdgeWidthFor(1)`)으로 정합.
- `tests/headless/test_graph_edge_flow.js`: A11 재작성(줌 구간별 정책 6건) · B1 개수→굵기 · B2 채널 직교화 · B4/C0/C4 갱신 — 66 PASS. `test_g6build_edge_visibility.js` T1 계약 갱신(다발 → 개수 굵기).
- docs: TASK/FUNCTION/REPORT/REVIEW + test-runs.d fragment.

## CHG-20260728T142000-graph-hover-anchor-postverify (TASK-20260728T135222 POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-28. 코드·자산 **무변경** — test-runs.d fragment POST-DEPLOY 결과 + TASK 체크박스 종결 + evidence 2종.
- 배포: PR #1000 → main **9158551b** → `make deploy-web-only` 무중단 롤링(web-a·web-b `git_commit=9158551b`, asset stamp `6fd0965e5b49`, 90s soak 통과).
- 라이브 실측(win-browser 실 Windows Chrome 150, `mysql-local` 스키마 카드 `agent_attachment_5f6353c47…`): **6/6 PASS** — ①애니 전 구간(15프레임 t=24~704ms) 카드 좌측 x **249 단일값**(앞글자 이동 0) ②유의 픽셀 diff 가 **캔버스 x 354~449**(원 카드 우측 끝 이후)에만 국한 = 우측 모서리만 확장 ③전체 명칭 `agent_attachment_5f6353c47c315cff1945d6b92f941c09` 노출 ④확장분이 우측 이웃 카드 위(z-order), 이웃 위치 불변 ⑤이탈 픽셀 동치 ⑥pageerror 0.
- 증적: `docs/evidence/pb0008-graph-hover-anchor-{before,after}-20260728.png`. Cross-ref: CHG/REV-20260728T135222-graph-label-hover-anchor.

## CHG-20260728T135222-graph-label-hover-anchor (TASK-20260728T135222 — hover 확장 기준점을 중앙 대칭 → 좌변 고정 + 우측 확장으로 변경, Minor §12.3, frontend-only)
- Date: 2026-07-28. Files: `static/graph/graph-renderer-pixi.js` · `tests/headless/test_pixi_adapter.js`. 사용자 정정 요청("확장되는 기준이 중앙이 아닌, 좌측은 고정 + 우측 모서리부터 확장").
- 변경 ①(순수): `hoverExpandGeom` 이 앵커 `left = s.x - w0/2` 를 반환. 신규 `hoverCardCenterX(g,w) = g.left + w/2`(폭이 커져도 좌변 불변, `left` 부재 구 geom 은 중앙 고정 폴백) · 신규 `hoverTextOffsetX(g,w,textLeft)`(라벨 world 좌측을 절대 고정하도록 카드 중심 이동분 상쇄).
- 변경 ②(어댑터): 카드 컨테이너 x = `hoverCardCenterX` (그 위에 기존 뷰포트·미니맵 클램프 유지), 라벨 `anchor(0,0.5)` + 매 프레임 `hoverTextOffsetX` 로 배치. `textLeft` 는 pad 추정이 아니라 **원 노드가 실제 렌더하던 잘린 라벨의 좌측을 역산**(`노드중심 - 렌더폭/2`)해 쓴다.
- 근본 이유(codex review P2 반영): 루틴 칩은 `labelMaxWidth`(176)가 칩 폭(150)보다 커 원 라벨이 이미 칩 밖으로 넘쳐 있다 → 좌측 기준을 `칩 좌변 + pad/2` 로 잡으면 hover 순간 라벨이 ~17px 튄다. 실렌더 폭 역산만이 "t=0 픽셀 동일" 을 보장한다.
- 불변 유지: 오버레이 전용(scene 모델 무변경 → 다른 노드 위치 불변) · zIndex 99998 · `_pick` tier0 클릭 라우팅 · 정리 경로 · render-on-demand.
- 검증: `node --check` PASS · `test_pixi_adapter.js` **190 PASS / 0 FAIL** · 그래프 headless 전 스위트 **639 PASS / 0 FAIL** · codex 2 라운드(P2 1건 수정 → 회귀 0). POST-DEPLOY PB-0008 잔여. Cross-ref: REV-20260728T135222-graph-label-hover-anchor · CHG-20260728T120530-graph-label-hover-expand.

## CHG-20260728T135111-graph-edge-screenspace (TASK-20260728T135111-graph-edge-screenspace — 굵기 변성 제거 + 프로시저 관계선 실선·LOD 해제, Minor §12.3, frontend-only)
- `graph-renderer-pixi.js`: `edgeWidthBoost`(§84) → **`edgeScreenScale = 1/zoom`** 로 교체 — 굵기·화살촉·다발 간격을 화면 픽셀로 해석. `_syncEdgeZoom()`+`_repaintAllEdges()` 신설(줌 변화 로그 0.22 초과 시 전 엣지 in-place 재페인트, rAF 코얼레싱, `destroy` 정리) + `_applyCam` 배선.
- `graph-roleviz.js`: 전 관계선 `lineDash` 제거(실선) · 굵기 서열 재편(trusted 1.6 / ROUTINE_USES 1.3 / candidate 1.0 / crossDs 1.0~1.15 / inferred 0.75) · alpha 재조정.
- `graph-core.js`: ROUTINE_USES LOD 축약 제거(직접 렌더 경로 + 집계 경로 `agg.kind !== "ROUTINE_USES"` 가드).
- `tests/headless/test_graph_edge_flow.js`: A11(화면 굵기 불변·model 반비례·서열) · A12(줌 재동기화 임계) 신설, B2/C0 실선·신뢰도 계약 추가 — 61 PASS.
- docs: TASK/FUNCTION/REPORT/REVIEW + test-runs.d fragment.

## CHG-20260728T123000-graph-label-hover-postverify (TASK-20260728T123000 — 잘린 노드 명칭 hover 확장 POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-28. 코드·자산 **무변경** — test-runs.d fragment POST-DEPLOY 결과 append + TASK 체크박스 종결 + evidence 3종 추가.
- 배포: PR #993 → main **d980ebe4** → `make deploy-web-only` 무중단 롤링(web-a·web-b `git_commit=d980ebe4`, Caddyfile 무변경 no-op, 90s soak 통과). 서빙 `/static/graph/graph-renderer-pixi.js?v=1659a75f6c2f`(80,232 B)에 `hoverExpandGeom`·`_labelHoverLayer`·`_probeHover` 존재 확증.
- 라이브 실측(win-browser relay 실 Windows Chrome 150.0.7871.115, `mysql-local` > `cc_bonedragon` 펼침 257테이블·300루틴): **8/8 PASS** — ①잘린 명칭 전체 노출(`sp_GetCurrentItemUniqueID…`→`sp_GetCurrentItemUniqueID_New`) ②rAF 프레임 폭 216→297→303px 단계 증가(트윈 실측) ③**다른 노드 위치 불변**(유의 픽셀 diff 가 캔버스의 2.75%=306×38px, hover 한 칩 자신에 국한) ④z-order(확장분이 클러스터 경계·관계선 위) ⑤확장영역 클릭 라우팅 대조(hover 전=클러스터 폴백 / hover 후=원 노드 상세) ⑥이탈 원복 픽셀 동치(최대 채널차 1/255) ⑦미잘림 칩 무반응 ⑧pageerror 0.
- 증적: `docs/evidence/pb0008-graph-label-hover-{before,after,leave}-20260728.png` · 원본·프레임 로그 `artifacts/feature-0003-graph-label-hover-expand/`. Cross-ref: CHG/REV-20260728T120530-graph-label-hover-expand.

## CHG-20260728T123838-graph-edge-legibility (TASK-20260728T123838-graph-edge-legibility — 그래프 관계선 육안 검증 후 부정합 3건 보정, Minor §12.3, frontend-only)
- `graph-renderer-pixi.js`: `EDGE_THIN_REF`/`EDGE_MIN_SCREEN_PX`/`edgeWidthBoost()` 신설 — `_paintEdge` 의 굵기·화살촉 상하한에 **전 엣지 동일 배율**을 적용해 줌아웃 서브픽셀 소실을 막고 굵기 서열을 보존.
- `graph-roleviz.js`: `_META_EDGE_CURVE` 0.15→0.13 · `_META_EDGE_CURVE_MAX` 44→26(카드 치수 결속) · alpha 바닥 상향(기본 0.32→0.58·색 `#94a3b8`→`#7c8b9e`, candidate 0.5→0.66, trusted 0.62→0.8, ROUTINE_USES 0.42→0.62, crossDs 0.52→0.66, SCHEMA_REF 0.3+→0.55+).
- `graph-core.js`: USES 사용선 α 0.5→0.66.
- `tests/headless/test_graph_edge_flow.js`: §84 A11 4건 신설(줌 4단계 화면 굵기 바닥·zoom 2 무보정·서열 보존) + B2 가시성 바닥/누적 단조 계약 갱신 + A4 곡률 상한 카드 결속.
- docs: TASK/FUNCTION/REPORT/REVIEW + test-runs.d fragment.

## CHG-20260728T120530-graph-label-hover-expand (TASK-20260728T120530-graph-label-hover-expand — 그래프 뷰 잘린 노드 명칭 hover 확장, Minor §12.3)
- Date: 2026-07-28. Files: `static/graph/graph-renderer-pixi.js`(수정) · `tests/headless/test_pixi_adapter.js`(T26 추가). **frontend-only · additive/비파괴** — 데이터·API·RBAC·엔드포인트·스키마·레이아웃 산출 변경 0.
- 요청(사용자, `/_template:entry`): "그래프 뷰에서 테이블 노드 내 명칭이 너무 길 경우 전체 텍스트가 잘리는 이슈… mouse-hover 시 노드 크기가 부드럽게 확장되며 나머지 명칭이 나타나도록. **다른 노드의 위치를 뒤틀지 않도록** 주의하고 **z-order** 또한 유의."
- 배경: 테이블 칩 폭은 feature-0016 §45 에서 `rel` 무관 고정(`_METLAY.TW=150`)으로 바뀌었고(가변 폭이 setData 재packing 유발), `_metaTableStyle` 의 `labelMaxWidth=140` 에서 `_ellipsize` 가 이름을 자른다. 전체 이름 확인 경로가 "노드 클릭 → 상세 패널" 뿐이었다.
- 변경 ①(순수 로직, `PixiAdapterPure`): `hoverExpandGeom(n, fullW, opts)` — 확장 대상 판정(center-placed rect + `labelMaxWidth` + 실제 잘림 + 이득 ≥ minGain)과 기하 산출(중심 고정 `w0→w1`, `pad=max(8, w0-labelMaxWidth)`, `cap=460 model px`, 텍스트 가용폭 보간 구간 `inner0=labelMaxWidth → inner1=w1-pad`). `hoverCardHit` — 카드 사각형 hit. `clampCardCenterX(sx, wScreen, vw, pad, rightMax)` — 뷰포트/미니맵 회피 클램프.
- 변경 ②(어댑터 `PixiGraphAdapter`): 전용 오버레이 레이어 `_labelHoverLayer`(`world` 자식·`zIndex=99998`·`eventMode="none"`) + hover 파이프라인 — `_probeHover`(rAF 코얼레싱, **tier1 hit-grid 만** 사용) → `_setLabelHover`(대상 변화 시에만 재구성 + hover-intent 90ms) → `_showLabelExpand`(카드=상태 halo+칩 배경+전체 라벨) → `_tweenCard`(easeOutCubic, 확장 160ms/축소 110ms) → `_clearLabelHoverVisual`(축소 애니 후 제거, 동시 1장 불변식). 부속: `_measureLabel`(전체 라벨 폭 1회 캐시), `_fitText`(전체 문자열 기준 재-ellipsize → 글자 순차 노출), `_clampCardX`, `_nodeFillAlpha`(`_drawNode` 와 공유 추출 — running desaturate 계약 단일화), `_revalidateHover`/`_repaintHoverCard`, `_cancelHoverProbe`, `_destroyCard`.
- 변경 ③(상호작용 정합): `_pick` 에 **tier0** 추가 — 활성 확장 카드 사각형 안은 원 노드로 라우팅(드러난 영역 클릭·우클릭·드래그가 캔버스/이웃으로 새지 않게, WYSIWYG). `pointercancel` window 리스너 신설(터치·펜 중단 시 포인터 상태 고착 해소 + nodedrag 는 "놓은 자리 종료" 동치 처리 — 기존 미처리 gap 보강).
- 불변식 보존: **scene 모델(`node.style.size/x/y`) 무변경** → masonry/shelf-pack·combo auto-fit bbox·`buildHitGrid`·미니맵 산출 전부 종전과 동일(다른 노드 위치 불변 = 사용자 요구 ①). **z-order**: 전 노드(≤`_METZ.CTL`=6)·엣지·combo 위, detail-hover-fx(99999) 아래(요구 ②). **render-on-demand(`autoStart:false`) 보존**: 보이던 카드도 새 카드도 없으면 렌더하지 않음.
- 정리 경로(누수 방지): `draw()` rebuild · `destroy()` · `pointerleave`(대기 프로브 rAF 포함) · `pointercancel` · 미니맵 진입 · 팬/드래그 개시 전부에서 카드·타이머·rAF 회수.
- 검증: `node --check --input-type=module` PASS · `tests/headless/test_pixi_adapter.js` **180 PASS / 0 FAIL**(baseline 112 회귀 0 + T26 68) · §18.8 `codex review --uncommitted` **9 라운드 수렴**(P1 3건·P2 8건 적발→수정, 최종 "No discrete correctness issues") · CHECK#13 Windows-browser Run(PRE-COMMIT 미수행 사유 명시 — WebGL 캔버스 애니는 headless 실측 정본 아님·정적 자산 baked; POST-DEPLOY PB-0008 잔여, `visual_verification_scope: always`). Cross-ref: TASK/REV-20260728T120530-graph-label-hover-expand · test-runs.d/20260728T120530-graph-label-hover-expand.md.

## CHG-20260728T114015-graph-edge-flow (TASK-20260728T114015-graph-edge-flow — 그래프 뷰 관계선 방향성 곡선 + 밀도 누적 + 부모 볼륨 다발, Major §12.3, frontend-only 3모듈)
- `src/static/graph/graph-renderer-pixi.js`: `PixiAdapterPure` 에 `edgeArc`(진행방향 왼쪽 고정 수직 오프셋 — 왕복 관계선 자동 분리)·`quadPoints`·`curveSegs`(화면 픽셀 기준 adaptive)·`dashPolyline`(폴리라인 전체 대시 위상 연속)·`strandOffsets` 신설, `hitTestEdge` 를 곡선 인지(zoom 인자 추가)로 확장. `_paintEdge` 재작성(실선=네이티브 `quadraticCurveTo`, 가닥별 개별 `stroke()` 로 겹침 alpha 누적, 끝 접선 화살촉+굵기 연동 크기, 곡선 중점 라벨), `_arrow` size 인자 추가, `_edgeStyleBetween` 신설 + `setHoverHighlight` 를 같은 호에 정합, `_lowFi`/`_lowFiTouched` 드래그 강등·`_flushEdgeRefresh` 고품질 복원, 모듈 상수 `EDGE_NO_STRAND`.
- `src/static/graph/graph-roleviz.js`: `_META_EDGE_CURVE/_MAX/_MIN` 상수 + `_metaEdgeStrands`(관계 수→가닥 log2 1~4) + `_metaEdgeFlow`(곡선·다발 키 주입 단일 축) 신설·export. `_metaEdgeStyleFor`(count 인자 추가, 굵기 1.4→0.85·1.8→1.05·3→1.5, `strokeOpacity` 0.32/0.5/0.62 신설, 기본색 `#cbd2db`→`#94a3b8`), `_metaRoutineEdgeStyle`(count 인자, 1.5→0.9/α0.42), `_metaSchemaRefEdgeStyle`(굵기 단독 → 다발 가닥 + 완만한 굵기·불투명도 + 가닥 수 비례 간격).
- `src/static/graph/graph-core.js`: ROUTINE_USES 집계 키에 `relation_type` 포함(`::RU::read|write`) + `agg.relType` 보존 → 읽기/쓰기 별개 관계선 방출·화살표 방향 유지(종전 `delete s.startArrow` 제거), 집계 굵기 가산(+0.8) 제거 후 `count`→가닥 위임, `data.relation_type` 노출, USES(제품→데이터소스) 사용선도 `_metaEdgeFlow` 로 통일, import 에 `_metaEdgeFlow` 추가.
- `tests/headless/test_graph_edge_flow.js` 신규(48건 — 곡선 기하 A1~A10 · 스타일 어휘 B1~B4/C0 · 빌드 계약 C1~C4).
- `tests/headless/test_g6build_edge_visibility.js` T1 계약 갱신(SCHEMA_REF 볼륨 인코딩: 굵기 단독 → 가닥 3 + 굵기·불투명도 동반 상승 + 곡률 부여).
- docs: TASK/REPORT/REVIEW/test-runs.d fragment.

## CHG-20260724T073848-conv-menu-order (TASK-20260724T073848-conv-menu-order — 대화 목록 '···' 확장 메뉴 항목 순서 변경, Minor §12.3, frontend-only)
- Date: 2026-07-24. `unit/feature-0003-agent-web-ui/src/static/app.js` `openConversationItemMenu` 단독 — '이동'(folder.manage.own 조건부) 블록을 '설정' append 앞으로 옮겨 렌더 순서를 `공유 → 설정 → 이동` 에서 `공유 → 이동 → 설정` 으로 변경. 헤더 주석 "최종 순서: 공유 | 설정" → "공유 | 이동 | 설정". 로직·권한·핸들러·action 인자 무변경 — 순수 순서.
- 영향: 대화 목록 각 항목의 '···' 확장 메뉴 항목 배열 순서만 변경. 백엔드·API·데이터·권한 무관. Cross-ref: TASK/REV-20260724T073848-conv-menu-order.

## CHG-20260724T033500-graph-emoji-color-postverify (TASK-20260724T031956-graph-emoji-color POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-24. 코드/자산 무변경 — TEST.md POST-DEPLOY 결과 append + TASK 체크박스 완료 + REVIEW postverify entry. 배포 PR #922 → main **c709ad3f**, `make deploy-web-only` 무중단 롤링(web-a/web-b·soak PASS·이미지 mysql-ai-web:c709ad3f·asset stamp 413567bad705).
- 라이브 실측(win-browser relay 실 Windows Chrome): 서빙 `/static/graph/graph-renderer-pixi.js` 에 `hasEmoji`·`!PixiAdapterPure.hasEmoji(text)` 게이트·emoji 폰트 스택 curl 확증. 버그 유발 조건(dark labelFill `#161b22` + emoji 폰트) canvas 2D fillText 프로브로 역할 아이콘 9종 chroma 측정: 📊217·💳255·📜75·📘177·📦214·🗂255 컬러 렌더, 👤·🔗·⚙️=0(Segoe UI Emoji 그레이스케일 디자인 이모지 — flat 실루엣 아닌 실 글리프). 9종 전부 flat 틴트 실루엣이 아닌 폰트 실 글리프 → "검은색 실루엣" 해소 확인. Cross-ref: REV-20260724T033500-graph-emoji-color-postverify · CHG/TASK-20260724T031956-graph-emoji-color · TEST Run(2026-07-24 graph-emoji-color POST-DEPLOY).

## CHG-20260724T031956-graph-emoji-color (TASK-20260724T031956-graph-emoji-color — 그래프 뷰 테이블 노드 역할 이모지가 검은색 실루엣으로만 렌더되던 버그 수정, Minor §12.3)
- Date: 2026-07-24. Files: `static/graph/graph-renderer-pixi.js`(수정) · `tests/headless/test_pixi_adapter.js`(T20b 추가). frontend-only, additive/비파괴(라벨 렌더 경로 분기만 추가, 데이터·API·RBAC·엔드포인트·레이아웃 0).
- 요청(사용자, `/_template:entry`): "그래프 뷰에서, 테이블 노드의 일부 이모지가 검은색 실루엣으로만 출력되는 이슈가 확인되어 수정이 필요합니다."
- 근본원인: 테이블 노드 라벨은 `graph-core.js` L700-703 에서 `_META_ROLE[role].icon + " " + name`(예 "📊 stats_daily") 로 조립. `graph-renderer-pixi.js` `_makeText` 가 기본 **BitmapText**(white-base glyph + `tint`=labelFill) 로 렌더 → BitmapText 는 dynamic font atlas 에 glyph 를 alpha 커버리지 단색 마스크로 래스터화 후 tint 를 곱하므로 **색 이모지의 색 채널이 소실**돼 labelFill 색의 단색 실루엣만 남음. `_META_ROLE` 의 `dark:true` 역할(stats/account/transaction/log/mapping)은 labelFill=`#161b22` → **검은색** 실루엣, `dark:false` 역할(master/config/etc)은 `#ffffff` → 흰색(옅게 비가시) — "일부만 검은색"의 원인.
- 변경: (1) `PixiAdapterPure.hasEmoji(text)` 순수 헬퍼 신설 — pictographic 블록(1F000-1FAFF)+Misc Symbols/Dingbats(2600-27BF, ⚙)+Misc Technical(2300-23FF)+Misc Symbols&Arrows(2B00-2BFF)+VS16(FE0F)+ZWJ(200D) 매칭. (2) `_makeText` BitmapText 게이트에 `&& !PixiAdapterPure.hasEmoji(text)` 추가 → 색 이모지 포함 라벨을 canvas `PIXI.Text` 로 강등(브라우저 색 이모지 폰트 네이티브 렌더). (3) Text 폴백 `fontFamily` 에 `'Segoe UI Emoji','Noto Color Emoji','Apple Color Emoji'` 명시 추가(per-glyph 폴백 확정).
- 설계 정합: 기존에도 tint 로 표현 불가한 색(비-hex rgb()/named)은 col.valid=false 로 Text 강등하는 seam(L189-190)이 존재 — 이모지도 "BitmapText 가 표현 못 하는 케이스"로 같은 seam에 편입(동형). 이모지 없는 대다수 라벨(컬럼·테이블명·−/+ 컨트롤)은 BitmapText 경로 유지 → §80 draw-call 최적화 보존(이모지는 분석 완료 테이블 칩에만 부착, bounded).
- 검증: `node --check --input-type=module` PASS · `tests/headless/test_pixi_adapter.js` **112 PASS / 0 FAIL**(기존 96 + T20b hasEmoji 16-assert) · §18.8 적대 리뷰 REV-20260724T031956-graph-emoji-color · CHECK#13 Windows-browser Run(PRE-COMMIT: PixiJS WebGL canvas 색 이모지 렌더는 headless 실측 정본 아님 — 배포 후 PB-0008 잔여, visual_verification_scope: always). Cross-ref: TASK/REV-20260724T031956-graph-emoji-color · TEST Run(2026-07-24 graph-emoji-color).

## CHG-20260724T140000-share-scroll-bottom-postverify (TASK-20260724T112446-share-scroll-bottom POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-24. 코드/자산 무변경 — test-runs.d fragment POST-DEPLOY append + TASK 체크박스 완료 + REPORT 갱신. 배포 PR #918 → main **94b4003a**, `make deploy-web-only` 무중단 롤링(web-a/web-b·90s soak PASS·이미지 mysql-ai-web:94b4003a).
- 라이브 실측(win-browser relay 실 Windows Chrome, 실 공유 링크 16-메시지 대화): **AC-SSB-1** 진입 `scrollY=53282==maxY`(scrollHeight 54118·innerHeight 836)·`atBottom=true` · **AC-SSB-3** `scrollTo(0,0)` 후 `stayedAtTop`(snap-back 없음, pin 정상 해제) · **AC-SSB-2** 최종 54118px 안착 · pageerror 0. 서빙 `/static/share.js`(47,901B) 신 심볼 5종 존재·dead window-load 리스너 소멸 curl 확증. Cross-ref: REV-20260724T140000-share-scroll-bottom-postverify · CHG-20260724T112446-share-scroll-bottom · TEST Run(2026-07-24 share-scroll-bottom POST-DEPLOY).

## CHG-20260724T112446-share-scroll-bottom (TASK-20260724T112446-share-scroll-bottom — 공유 대화 링크 화면 진입 시 문서 스크롤 맨 아래(최신 메시지) 고정, Minor §12.3)
- Date: 2026-07-24. Files: `static/share.js`(단일). frontend-only, additive/비파괴(진입 스크롤 위치 동작만 추가, 데이터·API·RBAC·엔드포인트 0).
- 요청(사용자, `/_template:entry`): "공유된 대화 링크 화면에 진입 시, 화면 스크롤이 가장 아래부터 위치하도록 구성해주세요."
- 변경: 초기 `fetchShare(token).then(render...)` 체인에 `engageInitialBottomPin()` 1회 호출 추가. 신설 함수 `scrollShareToBottom()`(문서 맨 아래로 `window.scrollTo(0, scrollHeight-innerHeight)`, 파일 내 기존 idiom L216-217/L388 과 동일 clamp), `engageInitialBottomPin()`(즉시 맨 아래 + 지연 콘텐츠 재고정 + 조작 시 해제), `releaseShareBottomPin()`(멱등 해제 — 리스너 remove + observer disconnect). 모듈 var `_shareBottomPinActive`/`_shareBottomPinObserver`.
- 지연 콘텐츠(마크다운 표·mermaid·이미지·point rail 비동기 렌더로 문서 높이 증가) 대응: `#shareMessages` `ResizeObserver` 재고정(미조작 동안), 미지원 시 `[150,400,1000,2500]ms`+`window load` 폴백(setupSharePointRail 동형 임계).
- 무회귀 보장: `pageBranchShare`(feature-0019 페이징 위치보존)·`scrollShareMessageIntoCenter`(rail 점프) 진입에서 `releaseShareBottomPin()` 선행 → 진입 pin 이 사용자/기존 로직 스크롤과 싸우지 않음. 3s 안전 타임아웃으로 이후 레이아웃 변화가 사용자를 끌어내리지 않게 자동 해제.
- 검증: `node --check` PASS · §18.8 적대 리뷰 REV-20260724T112446-share-scroll-bottom · CHECK#13 test-runs.d Windows-browser fragment(PRE-COMMIT PASS + POST-DEPLOY 라이브 계획, headless layout 부재로 스크롤 실측 불가 사유 기록). Cross-ref: TASK/REV-20260724T112446-share-scroll-bottom · TEST Run(2026-07-24 share-scroll-bottom).

## CHG-20260723T130200-conv-date-tree-postverify (TASK-20260723T034321-conv-date-tree POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-23. 코드/자산 무변경 — POST-DEPLOY 검증 원장 기록. 배포 PR #893 → main 0b15a0ea → `deploy-web.sh --web-only` 무중단(soak PASS·자산 스탬프 066695609710).
- 라이브 실측(win-browser Chrome 150, bootstrap_admin): 배포본 `_buildOwnDateTree` 합성 6/6(6월 단일·2025 연>월 중첩) + 실계정 사이드바 단일 "6월"[38]·"5월"[15]·중복 라벨 0(이전 ~10개 "6월" 소멸) + 6월 토글 4→42(배지 정확) + 스크린샷·pageerror 0. Cross-ref: REV-20260723T034321-conv-date-tree · TEST Run(conv-date-tree POST-DEPLOY).

## CHG-20260723T034321-conv-date-tree (TASK-20260723T034321-conv-date-tree — 좌측 대화목록 날짜 그룹핑 적응형 트리(월/년 집계)·"6월 중복" 시각 혼잡 해소, Major §12.3)
- Date: 2026-07-23. Files: `static/app.js`(+`_buildOwnDateTree` 신설·`_getDateGroupKey`/`_formatDateGroupLabel` 폐기·`renderConversationList` 재귀 트리 렌더러)·`static/styles.css`(`.conv-date-group-sub/-label/-count`). frontend-only, additive/비파괴(그룹핑 표현만 변경, 데이터·API·RBAC·엔드포인트 0).
- 변경: 오늘/어제·이번 달=일 노드, 올해 지난 달=월 노드(단일 — 이전엔 일 단위 키가 전부 "M월" 라벨로 중복 렌더돼 "6월/6월/6월" 혼잡), 지난 해=연 노드>월 서브노드(들여쓰기)>대화. 월/연 집계 노드에 대화 개수 배지. depth·collapse 모델(`state.collapsedDateGroups`)은 향후 대화 폴더 기능의 재사용 기반.
- 호환: collapse 키가 일 단위(YYYY-MM-DD, 매일 변경)→집계 단위(day:/month:YYYY-MM/year:YYYY, 안정)로 변경. localStorage 영속 키는 무해하게 stale(기존 값 미매칭 = 미접힘 = 기본 펼침, 회귀 아님). `_seedDateGroupsCollapsedOnce`가 매 로드 최근만 펼치는 기존 계약 유지.
- 검증: `node --check` PASS · 결정적 트리 단위테스트 4/4 PASS · POST-DEPLOY PB-0008 예정. Cross-ref: TASK-20260723T034321-conv-date-tree · REV-20260723T034321-conv-date-tree · TEST Run(2026-07-23 conv-date-tree).

## CHG-20260722T105320-share-menu-perm-wiring-postverify (TASK-20260722T103254-share-menu-perm-wiring POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-22. 코드/자산 무변경 — test-runs.d fragment POST-DEPLOY append + TASK 체크박스 완료 + evidence PNG. 배포 PR #885→main 066cec5e, `make deploy-web-only` 무중단(soak PASS).
- 라이브 실측(win-browser relay Chrome 150, bootstrap_admin 본인 대화 ☰): `여기까지 공유`·`여기부터 공유` 항목 `is-access-blocked` 없음(수정 전 항상 blocked 회귀 복구)·`여기부터 공유` 클릭 → onSelect 실행(비차단·오류토스트0)·floor arm 배너/마커 표시·pageerror 0. 서빙 app.js `action:"conversation.share.create"` 0매치. Cross-ref: REV-20260722T105320-share-menu-perm-wiring-postverify · CHG-20260722T103254-share-menu-perm-wiring.

## CHG-20260722T103254-share-menu-perm-wiring (TASK-20260722T103254-share-menu-perm-wiring — 말풍선 ☰ '여기까지/여기부터 공유' 권한 연결(action 매핑) 회귀 수정, Minor §12.3)
- Date: 2026-07-22. 사용자 신고: 대화 '여기부터/여기까지 분기'(말풍선 ☰ 여기서 분기·여기부터/여기까지 공유) 권한 연결 미작동.
- 근본원인: ☰ 메뉴 '여기까지 공유'/'여기부터 공유'(`openMessageBubbleMenu`)가 `make` 팩토리에 `action` 으로 **권한 코드** `"conversation.share.create"` 를 전달. `requiredPermissionsFor(action)`(app.js ~L589)는 **추상 action 이름**("conversation.share")만 switch 처리 → 미매칭 `default:{codes:[]}` → `markAccessBlocked` 가 `blocked=!hasAnyPermission([])=true` 로 두 항목을 **모든 로그인 사용자에게 항상 비활성**(is-access-blocked·클릭 시 onSelect 대신 오류 토스트) → ☰ 경로 공유(여기부터/여기까지) 완전 동작 불능.
- 변경: `static/app.js` **2줄** — 두 항목 `action: "conversation.share.create"` → `action: "conversation.share"`(conv-item '공유'가 이미 쓰는 정상 case). → codes `["conversation.share.create"]` 매핑 → `can()` display-permissive(로그인=true) → blocked=false → 정상 활성.
- 회귀 유입: `36ca1d4d`(2026-07-04 말풍선 ☰ 통합). 신규 항목이 conv-item '공유'의 추상 action 이름 대신 권한 코드 사용(ds-test-gate-fix `8e01cc24`/REV-20260716T051931 와 동형 프론트 게이트 배선 오류).
- 회귀 잠금: `tests/test_menu_action_permission_wiring.py` 신규 — 모든 메뉴 `action:` 이 requiredPermissionsFor 처리 case 인지 소스 파싱 검증(pre-fix FAIL·fixed PASS 실증).
- 비변경: 백엔드/스키마/RBAC/엔드포인트 shape 0(보안 posture 불변 — `create_conversation_share` 의 `conversation.share.create` 403·소유 IDOR 게이트 유지)·conv-item 메뉴·admin.js 무변경.
- **cache-buster 무변경**: 소스 `?v=dev` 고정(Dockerfile `inject_asset_stamp.py` content-hash 빌드주입·deploy-web `asset_stamp_verify` 하드게이트).
- 검증: `make test` 전체 GREEN(신규 3 PASS)·ruff PASS(첫 run 4 실패=`--no-deps` postgres-replica 레이스 flake·base main·재실행 RC=0 확증). 라이브=POST-DEPLOY PB-0008. Cross-ref: REV-20260722T103254-share-menu-perm-wiring · test-runs.d fragment 20260722T103254.
- Files: `static/app.js`, `tests/test_menu_action_permission_wiring.py`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md` + test-runs.d fragment.

## CHG-20260717T010501-doc-sync-rn-0717 (TASK-20260717T010501-doc-sync-rn-0717 — 07-16 후속 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: 기존 releases[0] "2026-07-16" 블록 items 에 **fixed/work 항목 1개 추가**(작업 화면 데이터소스 ‘연결 테스트’ 버튼 미표시 회귀 복구) + summary 1문장 append. generated 07-16 유지·신규 dated 블록 미생성·releases 31 불변.
- **cache-buster 무변경**: 소스 `?v=dev` placeholder 고정(§13.1 ITEM-09 what#3 — Dockerfile `inject_asset_stamp.py` content-hash 빌드 주입·deploy-web `asset_stamp_verify` 하드게이트). index/admin.html 편집 0.
- 제외: redteam-rederive(PR #857, 내부·미배포)·ds-test-gate-fix POST-DEPLOY 기록(원천 cycle 소관).
- Verification: `node --check` PASS · vm 구조검증(31 releases·07-16 head 5항목[admin 4·work 1]·07-15 보존 7·스키마·누출0) · verify_release_notes.mjs 33/34(1 FAIL=styles.css pre-existing).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- **무인 스케줄 run — landing/배포는 cron wrapper v3 소유(스킬 로컬 commit 만)**. META(SECURITY §22.4·wiki Log·meta/REVIEW)는 별도 commit.

## CHG-20260716T052500-ds-test-gate-fix-postverify (TASK-20260716T051931-ds-test-gate-fix POST-DEPLOY 회귀 복구 라이브 기록, 비-정책 doc-only)
- Date: 2026-07-16. 코드/자산 무변경 — test-runs.d POST-DEPLOY append + TASK 체크박스 완료. 배포 PR #855→main e6ca5e4b, `make deploy-web` 무중단(soak PASS).
- 라이브 실측(win-browser relay, bootstrap_admin): DS 테스트 버튼 14개 재렌더(수정 전 0)·클릭→"✓ 연결 성공 (13.6ms)" 상단 토스트·pageerror 0 → 사용자 신고 회귀 해소. Cross-ref: REV-20260716T052500-ds-test-gate-fix-postverify · CHG-20260716T051931-ds-test-gate-fix.

## CHG-20260716T051931-ds-test-gate-fix (TASK-20260716T051931-ds-test-gate-fix — 작업화면 데이터소스 '연결 테스트' 버튼 렌더 회귀 수정, Minor §12.3)
- Date: 2026-07-16. 사용자 신고(회귀): 07-13 출하 DS 테스트 버튼 미표시.
- 변경: `static/app.js` `buildProductDropupItem` `_dsTestable` 게이트 1줄 — `Boolean(state.user?.permissions?.["datasource.test"])` → `can("datasource.test")`. 근거: `state.user.permissions` 는 `/api/session` 미직렬화(TASK-0098 "표시 허용 + backend 403" 컨벤션)라 항상 undefined→false→버튼 미렌더. `can()` 은 display-permissive(로그인=true), 실제 거부는 백엔드 403(admin_test_datasource console.access+datasource.test). 순 게이트 = `!viewOnly && canOpenAdminConsole()`(07-13 동작 복구).
- 회귀 유입: perm-atomic-split `8e01cc24`(07-15 Critical) — datasource.test 원자 권한 신설 시 프론트 게이트를 부재 permissions 맵으로 작성.
- 비변경: 백엔드/스키마/RBAC/엔드포인트 shape 0(보안 posture 불변)·토스트·throttle·admin.js 무변경.
- 검증: `node --check` PASS · 회귀 하네스 short-circuit 무영향. 라이브=POST-DEPLOY PB-0008. Cross-ref: REV-20260716T051931-ds-test-gate-fix · test-runs.d fragment.
- 관련 flag: 동일 커밋 app.js ≈L2006 권한 표시 UI 도 `state.user.permissions` 의존(별도 feature 소유·본 scope 밖).

## CHG-20260716T120000-graph-search-groups-postverify (POST-DEPLOY 시각검증 정합 — docs-only, 코드 변경 0)
- Date: 2026-07-16. 별도 worktree `ai/claude/feature-0003-graph-search-groups-postverify`(base main). CHG-20260716T114705-graph-search-panel-groups(PR #846 배포 89c1e7b0)의 POST-DEPLOY PB-0008 라이브 시각검증 결과를 원장에 정합.
- 변경: `docs/test-runs.d/20260716T1147-graph-search-panel-groups.md` Run 3 DEFERRED→**PASS**(라이브 실측 — 8 스키마→카테고리 2단 접기·모두 접기/펼치기 라벨 정합·검색 이력 뒤로/앞으로·verbose 부제 부재·pageerror 0) + verdict 갱신 + `docs/TASK.md` PB-0008 체크박스 [x]. **런타임 코드 무변경**.
- Rollback: 문서 revert. Deploy: 없음. Cross-ref: CHG-20260716T114705-graph-search-panel-groups / REV-20260716T120000-graph-search-groups-postverify.

## CHG-20260716T114705-graph-search-panel-groups (검색 결과 패널 3개선 — 2단 접기·검색 이력·설명문 간결화, Minor §12.3 프론트 단독·additive)
- Date: 2026-07-16. 별도 worktree `ai/claude/feature-0003-graph-search-panel-groups`(base main). 사용자 요청(/_template:entry 후속): ①스키마 클러스터·컨텐츠 카테고리 단위 구분·정렬·접기/펼치기 ②뒤로/앞으로가 검색에도 유효 ③검색 설명문 TMI 간결화. TASK-20260716T013714(검색 결과 패널) 후속.
- **변경**: `src/static/graph/graph-ctxmenu.js`
  - **①2단 접기**: `_metaGraphRenderSearchResults` 전면 재작성 — 결과 노드를 `_metaSchemaComboOf`(스키마 클러스터)로 1차, `cluster_label`(컨텐츠 카테고리, 없으면 "카테고리 미분류")로 2차 그룹. 정렬: 스키마=매칭수↓→이름, 카테고리=수↓→이름(미분류 맨끝), 노드=유사도↓→이름. nested `.amgr-srch-sc`/`.amgr-srch-cat` 박스 + `is-collapsed` class(부모에 붙이면 CSS 가 body `display:none`). 각 헤딩(스키마·카테고리) role=button·caret·aria-expanded·Enter/Space 토글, 접힘 상태 `_metaGraph._searchGroupCollapsed`(Set, 키 `sc:<combo>`·`cat:<combo><label>` — `` 구분자로 경계 충돌 방지) 에 유지(재렌더·키스트로크 간 보존, 새 그룹 기본 펼침). "모두 접기/펼치기" 버튼(재렌더로 반영). 헤딩 시각은 기존 `.amgr-ct-group` 재사용. 행은 카테고리가 그룹 헤딩이 되어 per-row `카테고리:` meta 제거(중복 해소).
  - **②검색 이력**: 신규 `_metaGraphRecordSearch(q, nodes)` — 이력 top 이 `v:"search"` 면 in-place 갱신(키스트로크 항목 폭증 방지), 아니면 push(`{v:"search", k:q, nodes}`, 결과 캐시). `_metaGraphSearch` 가 렌더 직후 호출. 신규 `_metaGraphRestoreSearch(ent)` — 재fetch 없이 입력값만 세팅(input 이벤트 미발화=재검색 루프 없음) + 캐시 노드로 결과 재구성. `_metaGraphHistoryGo` 에 `ent.v==="search"` → `Promise.resolve(_metaGraphRestoreSearch)` 분기(search 의 `ent.k`=질의문자열이라 `_metaRenderedIdFor` 폴백·카메라 skip 자연 정합). **finding#5 해소**: 검색이 자기 이력 항목이 되어 스크롤 캡처(항상 현재 화면=현재 항목)가 정합 — 별도 마커 가드 불요.
  - **③설명문 간결화**: 상태줄을 `'${q}' — ${nRaw}건`(+ 상한/숨김필터 짧은 힌트만)으로 축약(기존 "카드 badge=매칭/전체… 앰버 글로우 확인" 제거), 결과 패널 부제 삭제, 행 `title`=fqn 만("클릭하면 이 노드 상세를 봅니다" 제거), 유사도 배지 title 제거.
  - `src/static/graph/graph.css`: `.amgr-srch-collapse-all`/`.amgr-srch-sc`/`.amgr-srch-cat` `is-collapsed` body 숨김/`.amgr-srch-subhead` 들여쓰기/`.amgr-srch-cat-none` 약화 표기/`.amgr-srch-cat-body` 노드 들여쓰기.
- Why: 대규모 검색 결과를 그래프 3층 구조 그대로 접어 훑고(스키마·카테고리 단위), 검색↔노드 상세를 이력으로 오가며, 설명문은 짧게 — 탐색 효율·일관성.
- Impact: 검색 결과 패널 렌더·검색 이력 항목만 확장. 노드/클러스터/관계 상세 이력·스크롤·캔버스 스키마 카드·글로우·백엔드/API 무변경. 캐시버스터 빌드 자동.
- Rollback: `_metaGraphRenderSearchResults` 재작성 revert + record/restore/Go 분기·상태줄·CSS revert. 다른 경로 영향 0.
- Deploy: web 재빌드(정적 자산 hash). alembic/백엔드 변경 없음.
- Cross-ref: CHG-20260716T013714-graph-search-detail-panel(원 기능·finding#5) · feature-0016(그래프 정본, graph-detail-scroll 이력·스크롤) · REV-20260716T114705-graph-search-panel-groups.

## CHG-20260716T015800-graph-search-detail-postverify (POST-DEPLOY 시각검증 정합 — docs-only, 코드 변경 0)
- Date: 2026-07-16. 별도 worktree `ai/claude/feature-0003-graph-search-detail-postverify`(base main 03e8d1b0). CHG-20260716T013714-graph-search-detail-panel(PR #839 배포 완료) 의 POST-DEPLOY PB-0008 라이브 시각검증 결과를 원장에 정합.
- 변경: `docs/test-runs.d/20260716T0137-graph-search-detail-panel.md` Run 3 DEFERRED→**PASS**(win-browser.py 실 Windows Chrome 라이브 실측 — 코스튬 7건 AI 분석 배지·플루토스 28건 카테고리 배지+cluster_label+유사도 63%·행 클릭→노드 상세·클리어→뷰 해제·pageerror 0) + verdict 갱신 + `docs/TASK.md` PB-0008 체크박스 [x]. **런타임 코드·CSS·백엔드 무변경**(순수 검증 원장 정합).
- Rollback: 문서 revert. Deploy: 없음(docs-only). Cross-ref: CHG-20260716T013714-graph-search-detail-panel / REV-20260716T015800-graph-search-detail-postverify.

## CHG-20260716T013714-graph-search-detail-panel (그래프 뷰: 검색어 갱신 시 상세 패널에 검색 결과 리스트 구성, Minor §12.3 — 프론트 단독·additive; 그래프 정본 feature-0016)
- Date: 2026-07-16. 별도 worktree `ai/claude/feature-0003-graph-search-detail-panel`(base main 0433efbb). 사용자 요청(/_template:entry 후속 turn): "검색어가 입력되었을 경우엔 상세 패널 내 검색 결과를 구성하도록 동작시켜주세요. 트리거는 '검색어 갱신 시'."
- **컨텍스트**: 직전 cycle(feature-0002 CHG-20260716-graph-search-content-match)로 `search_nodes` 가 이름/FQN 외 컨텐츠 카테고리(`semantic_cluster_label`)·AI 능동 분석(`node_analysis_jobs.analysis`)까지 매칭하고 노드에 `match_via`·`cluster_label`·`score` 를 실어 반환한다. 그래프 검색은 캔버스 앰버 글로우 + 스키마 카드 badge 로만 결과를 표기했는데, 검색 시 상세 패널에서 매칭 노드 목록을 바로 훑도록 결과 리스트를 상세 패널에 구성한다(프론트 렌더만 추가 — 백엔드 payload 이미 충분).
- **변경**: `src/static/graph/graph-ctxmenu.js`
  - 신규 `_metaGraphRenderSearchResults(nodes, q)`: `#metadataGraphDetailBody` 에 검색 결과 리스트 렌더. 행 = label 배지(`_META_GRAPH_COLOR`/`_META_LABEL_KO`) + 이름 + 유사도%(score>0) + **매칭 근거 배지**(match_via: 이름/카테고리/AI 분석) + 카테고리 라벨(category 매칭 시 cluster_label). 전 사용자/DB 유래 문자열 `esc()` HTML 이스케이프. 결과 0건 시 안내 메시지. 컨테이너 id `metaGraphSearchResults`(검색결과 뷰 판별 마커). 행 클릭/Enter/Space → `_metaGraphShowDetail(key)`(그 노드 상세 이동). role=button·tabindex 접근성.
  - `_metaGraphSearch` 2훅: (a) 비어있지 않은 q 는 `if (q !== _metaGraph.lastQuery) return` stale 가드 뒤에서 `_metaGraphRenderSearchResults(data.nodes, q)` 호출(검색어 갱신 트리거). (b) 클리어(빈 q) 시 상세 body 에 마커가 있으면(=검색결과 뷰) `_metaGraphRenderDetailEmpty()` 로 해제 — 사용자가 결과를 클릭해 노드 상세로 들어간 경우는 마커 부재라 보존.
  - `src/static/graph/graph.css`: `.amgr-searchlist`/`.amgr-searchres`/`.amgr-via`+`.amgr-via-{name,category,analysis}`/`.amgr-searchsub`/`.amgr-searchmeta` + `.amgr-row[data-goto]` cursor·hover. 카테고리 배지는 검색 글로우(#e8a400)와 동일 앰버 계열, 분석=블루, 이름=회색. 기존 `admin-meta-graph-card`/`amgr-row`/badge 토큰 재사용.
- Why: 검색 결과를 캔버스에서만 보던 것을 상세 패널에서 목록으로 훑고(매칭 근거·유사도 가시), 클릭으로 바로 상세 이동 — 검색→탐색 흐름 단축. 직전 백엔드 매칭 확장(카테고리·AI 분석)의 근거를 배지로 표면화해 "왜 매칭됐는지"도 노출.
- Impact: 검색 경로에만 상세 패널 렌더 1개 추가. 노드 상세/클러스터 상세/우클릭 메뉴·기존 글로우·카드 badge 무변경. 백엔드·API·스키마 무변경. 캐시버스터는 빌드 content-hash 자동 주입.
- Rollback: `_metaGraphRenderSearchResults` + 2훅 + graph.css 블록 revert. 다른 경로 영향 0.
- Deploy: web 재빌드(정적 자산 hash 재주입). alembic/백엔드 변경 없음.
- Cross-ref: feature-0002 CHG-20260716-graph-search-content-match(match_via/cluster_label/score 원천) · feature-0016-metadata-graph(그래프 뷰 정본) · REV-20260716T013714-graph-search-detail-panel · 병렬 세션 feature-0016-graph-detail-scroll(상세 패널 스크롤/history, 함수 영역 직교).

## CHG-20260715T120000-graph-ctxmenu-band-priority-postverify (TASK-20260715T114608-graph-ctxmenu-band-priority POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-15. 코드/자산 무변경 — test-runs.d fragment POST-DEPLOY 섹션 '이연'→실측 PASS + TASK 체크리스트 완료. 기능 배포 PR #815→main 6a950a20 선행 완료.
- 라이브 실측(win-browser Chrome 150, 6a950a20): 킹스레이드·미분류 CAT 밴드에서 클러스터 박스(dbAuth·dbTest) 우클릭 → **카테고리 메뉴**(band-wins) / 펼친 테이블 노드 → **그 테이블 메뉴**(흡수 안 함) / 좌클릭 → **클러스터 펼치기 정상**. 사용자 결정("밴드 우선") 충족. 증거 scratchpad/evidence-bandwins-box-category.png.
- Cross-ref: CHG-20260715T114608-graph-ctxmenu-band-priority(기능) · REV-20260715T120000-graph-ctxmenu-band-priority-postverify · test-runs.d/20260715T114608-graph-ctxmenu-band-priority.md POST-DEPLOY Run.

## CHG-20260715T114608-graph-ctxmenu-band-priority (TASK-20260715T114608-graph-ctxmenu-band-priority — 제품 카테고리 밴드 우클릭 band-wins, Major §12.3 frontend-only)
- Date: 2026-07-15. 제품 카테고리 밴드 안의 스키마 클러스터 박스가 밴드를 시각적으로 채워, 밴드 우클릭이 스키마 메뉴로 새는 UX 겹침 → 사용자 결정 "밴드 우선"으로 우클릭 시 밴드 귀속.
- `static/graph/graph-renderer-pixi.js`:
  - 신규 `PixiGraphAdapter._pickContext(mx,my)` — `_pick()` 이 combo 또는 schema-card 를 반환하고 그 지점을 덮는 cat-bg 가 있으면 cat-bg(카테고리 밴드)로 승격; 아니면 `_pick()` 그대로.
  - `up()` 우클릭(button===2) 경로만 `_pickContext` 사용(kind=chit.__combo?combo:node 로 emit). 좌클릭/더블클릭/드래그는 `_pick` 불변.
- band-wins 범위: 밴드 멤버 클러스터(combo/schema-card)만 승격. 테이블·컬럼 노드·CATH/CATX/GX/GH/GB·밴드 밖 standalone 클러스터는 불변.
- 비변경: 좌클릭(펼치기/상세)·드래그(노드/combo/밴드헤더)·dispatch·메뉴 함수·시각 z·백엔드/RBAC/스키마 0.
- 검증: `node --check` PASS · `tests/headless/test_pixi_adapter.js` T22 회귀 6종(ALL PASS 68/0) · §18.8 적대 패널. POST-DEPLOY PB-0008 라이브 잔여(visual_verification_scope: always).
- Cross-ref: TASK/REVIEW-20260715T114608-graph-ctxmenu-band-priority · test-runs.d/20260715T114608-graph-ctxmenu-band-priority.md · 선행 CHG-20260715T102901-graph-ctxmenu-hittest(WYSIWYG hit-test 층서).

## CHG-20260715T110000-graph-ctxmenu-hittest-postverify (TASK-20260715T102901-graph-ctxmenu-hittest POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-15. 코드/자산 무변경 — test-runs.d fragment 의 POST-DEPLOY 섹션을 '이연' 계획→실측 PASS 로 갱신 + TASK 체크리스트 완료. 기능 배포는 PR #808→main 6ec5da4b(이후 병렬 8098aee1 재배포, fix 포함)로 선행 완료.
- 라이브 실측 요지(win-browser 실 Windows Chrome/150, https://localhost/admin): 제품-매핑 데이터소스(mysql-kr-an2-auth, "킹스레이드 - 국내 QA") 스키마그래프에 CAT 밴드 2개 렌더 → **스키마 클러스터(dbAuth·dbTest) 우클릭 = "스키마" 메뉴**(이전 결함 해소) · **밴드 헤더·tint 여백 우클릭 = "카테고리" 메뉴** · 세 증상 전부 해소(WYSIWYG). 증거 scratchpad/evidence-cluster-schema-menu.png.
- Cross-ref: CHG-20260715T102901-graph-ctxmenu-hittest(기능) · REV-20260715T110000-graph-ctxmenu-hittest-postverify · test-runs.d/20260715T102901-graph-ctxmenu-hittest.md POST-DEPLOY Run.

## CHG-20260715T102901-graph-ctxmenu-hittest (TASK-20260715T102901-graph-ctxmenu-hittest — 그래프 우클릭 메뉴 오라우팅 hit-test 층서 수정, Major §12.3 frontend-only)
- Date: 2026-07-15. 그래프 뷰 우클릭 메뉴가 대상과 뒤바뀌는 결함(스키마 클러스터→카테고리 메뉴 / 제품 카테고리 밴드→스키마 메뉴) 수정. 근본: `_pick` 이 node 우선 반환→CAT 밴드 배경(node, `data.kind:"cat-bg"`, z=-1, 멤버 클러스터 전체 덮음)이 스키마 클러스터 빈배경(combo, 폴백 대상) 우클릭을 가로챔.
- `static/graph/graph-renderer-pixi.js`:
  - `PixiAdapterPure.hitTest(mx,my,hg,nodes,filter)` — optional `filter(n)` 인자 추가(tier 분리, `filter(n)→false` 노드 skip).
  - `PixiGraphAdapter._pick()` 3-tier 재작성: ① `hitTest`(cat-bg 제외) → ② `hitTestCombo`(스키마 클러스터) → ③ `hitTest`(cat-bg 만). `_isCatBg(n)` 헬퍼 신설.
- 층서 결과: 구체 요소 > 스키마 클러스터 배경 > 카테고리 밴드 배경. 시각 z(-1) 불변 — hit-test 우선순위만 교정.
- 비변경: dispatch(graph-core node:contextmenu)·메뉴 함수·노드 방출·좌클릭·드래그 경로·백엔드/RBAC/스키마 0.
- 검증: `node --check` PASS · `tests/headless/test_pixi_adapter.js` T21 회귀 6종 추가(ALL PASS 62/0) · §18.8 적대 패널. POST-DEPLOY PB-0008 라이브 잔여(visual_verification_scope: always).
- Cross-ref: TASK/REVIEW-20260715T102901-graph-ctxmenu-hittest · test-runs.d/20260715T102901-graph-ctxmenu-hittest.md · 선행 CHG-20260714T180125-graph-ctxmenu-category(dispatch 라우팅).

## CHG-20260714T183808-graph-ctxmenu-postverify (TASK-20260714T180125-graph-ctxmenu-category POST-DEPLOY 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-14. 코드/자산 무변경 — TASK.md 체크리스트 완료(verify/PR#794/POST-DEPLOY) + test-runs.d fragment 에 POST-DEPLOY 라이브 검증 Run append. 기능 배포는 PR #794→main 154fb916, `deploy-web`(deploy_scope: included, web-a/b soak PASS) 로 선행 완료(본 커밋은 그 사후 기록).
- 라이브 실측 요지(win-browser 실 Windows Chrome/150, https://localhost/admin): 배포 전달(서빙 baked 자산에 `_metaGraphCtxForCategory` 반영)·라이브 도달성(그래프 렌더·범례 '제품 카테고리 밴드')·**수정 핸들러(node:contextmenu CAT 분기 graph-core L2086) 우클릭 dispatch 파이프라인 라이브 실증** PASS. 리터럴 CAT 밴드 위 '카테고리' 메뉴 육안 = DEFERRED(도달 scope 전부 미분류→밴드 미방출, 제품-매핑 scope 필요) — 사용자 1-probe 권장.
- postverify 재확인(main 1f705a9e): web-a·web-b `GIT_COMMIT=1f705a9e`(154fb916 포함) + baked `_metaGraphCtxForCategory` 반영 실측 — 수정 정상 서빙 중.
- Cross-ref: CHG-20260714T180125-graph-ctxmenu-category(기능) · REV-20260714T183808-graph-ctxmenu-postverify · test-runs.d/20260714T180125-graph-ctxmenu-category.md POST-DEPLOY Run.

## CHG-20260714T180125-graph-ctxmenu-category (TASK-20260714T180125-graph-ctxmenu-category — 그래프 카테고리 밴드 우클릭 전용 메뉴, Minor §12.3 frontend-only additive)
- Date: 2026-07-14. 그래프 뷰 '제품 카테고리 밴드'(CAT:/CATH:/CATX:) 우클릭을 전용 카테고리 메뉴로 라우팅 — 이전 `_metaGraphCtxHide()` stopgap(및 그 이전 배포본의 combo fall-through "스키마 클러스터 메뉴" 오노출) 대체.
- `static/graph/graph-ctxmenu.js`: +`_metaGraphCtxForCategory(catKey, x, y)`(헤더 배지 + 카테고리 상세 + 밴드 접기/펼치기 + 카테고리명 복사) + export.
- `static/graph/graph-core.js`: `node:contextmenu` CAT 분기 `_metaGraphCtxHide()` → `_metaGraphCtxForCategory(String(id).replace(/^CAT(H|X)?:/, ""), p.x, p.y)` + import.
- 검증: `node --check`(module) 양 파일 PASS · dispatch/의존심볼 grep 정합. POST-DEPLOY PB-0008 라이브 잔여(visual_verification_scope: always).

## CHG-20260714T080000-account-subtabs-postverify (TASK-20260714T074417-account-subtabs POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-14. 코드/자산 무변경 — TASK.md 체크리스트 완료 + TEST.md POST-DEPLOY 라이브 PASS append + REVIEW postverify. 배포 PR #788→main 53e55bfe, `deploy-web --web-only`(1차 soak false-positive 롤백→재배포 PASS).
- 라이브 실측 요지(win-browser 실 Windows Chrome, 라이브 53e55bfe): 하위탭 4개·기본 account·각 클릭 시 정확히 1 subpane(알림 체크박스/UI select/사용량 차트/2FA·로그아웃) 노출 assertion 전항목 PASS + 서빙 자산 심볼 확인 + 세그먼트 하위탭 바 시각 렌더(스크린샷).
- 운영 노트: 1차 배포가 post-cutover soak 에서 edge /healthz 순간 비정상(mysql/pg 정상)으로 last-good 자동 롤백 — 정적 자산 변경이라 /healthz 무관, cold-start+insight-worker 동시부하 transient(LRN deploy-web-healthz-concurrent-resync 패턴). 동일 이미지 재배포 시 soak PASS 로 false-positive 확증.
- Cross-ref: CHG-20260714T074417-account-subtabs(기능) · REV-20260714T080000-account-subtabs-postverify · TEST Run POST-DEPLOY.

## CHG-20260714T074417-account-subtabs (TASK-20260714T074417-account-subtabs — 프로필 '계정' 탭 하위 세분화, Minor §12.3, frontend-only)
- Date: 2026-07-14. `/_template:entry` arg-given. 스키마/마이그/RBAC/엔드포인트/서버 계약 0 — DOM 재배치 + 표현계층 sub-nav.
- 배경: anim-effect-pref 로 '화면 효과'가 추가되며 '계정' 탭 7섹션(활동·알림·화면효과·사용내역·비번·2FA·로그아웃)이 한 화면에 누적 → 난잡. 사용자 요청으로 하위 탭 세분화(알림·UI 독립 확정 → 4탭 승인).
- 변경:
  - `static/index.html`: `data-profile-pane="security-and-account"` 를 `.profile-subtabs`(계정/알림/UI/사용 내역 4버튼) + 4× `.profile-subpane`(data-account-subpane) 으로 재구성. 7섹션을 account(활동+비번+2FA+로그아웃)/notifications(알림)/ui(화면효과)/usage(사용내역) 로 이동 — 모든 element id 보존(회귀 0).
  - `static/app.js`: 신규 `switchAccountSubtab(sub)` — `[data-account-subtab]` is-active·aria-selected + `[data-account-subpane]` hidden 토글 + 하위 탭별 lazy 렌더(account→renderProfileTotp / notifications→renderNotifyPrefs / ui→renderMotionPref / usage→loadProfileUsage). `switchProfileTab('security-and-account')` 를 4콘텐츠 일괄 렌더에서 `switchAccountSubtab(state.accountSubtab||'account')` 로 변경(사용량 API 는 usage 탭 진입 시에만 호출 — 효율 개선). `initialize()` 에 `[data-account-subtab]` 클릭 리스너 배선.
  - `static/styles.css`: `.profile-subtabs`(세그먼트 컨테이너)·`.profile-subtab`(pill, is-active 강조)·`.profile-subpane`(세로 스택) — 상단 drawer-tab 언더라인과 시각 구분.
- 검증: `node --check app.js` PASS · 하위탭/subpane 각 4·섹션 id 전부 보존·pane div 균형 32/32. §18.8 적대 서브에이전트 리뷰(REVIEW). POST-DEPLOY PB-0008 라이브 시각검증(TEST §Run 2026-07-14 account-subtabs).
- Cross-ref: TASK-20260714T074417-account-subtabs · REV-20260714T074417-account-subtabs · 선행 anim-effect-pref(CHG-20260714T065503) · ANCHOR 0003 무충돌.

## CHG-20260714T073000-anim-effect-pref-postverify (TASK-20260714T065503-anim-effect-pref POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-14. 코드/자산 무변경 — TASK.md 체크리스트 완료 + TEST.md POST-DEPLOY 라이브 PASS append + REVIEW postverify 엔트리. 배포 PR #786→main f00519dd, `deploy-web --web-only` 무중단 롤링(soak PASS).
- 라이브 실측 요지(https://localhost/ bootstrap_admin, win-browser Chrome): 게이트 로직 런타임 assertion 전항목 PASS(`off→reduced=true`·`on→reduced=false` OS무관·`os→OS일치`·data-motion 반영·`#motionEffectSelect` 옵션3종+hydration·캘린더/검색 `scrollMessagePointIntoCenter` 라우팅) + 서빙 자산 stamp 갱신(b162038f7a10)·심볼 확인 + 프로필 계정 탭 select 시각 렌더(스크린샷). 한계: 검증 머신 reduce-motion off라 육안 모션 시연 불가·로직은 결정적 실증.
- Cross-ref: CHG-20260714T065503-anim-effect-pref(기능) · REV-20260714T073000-anim-effect-pref-postverify · TEST Run(2026-07-14) POST-DEPLOY.

## CHG-20260714T065503-anim-effect-pref (TASK-20260714T065503-anim-effect-pref — 작업 화면 애니메이션 복원 + 인앱 "애니메이션 효과" 설정, Major §12.3, frontend-only)
- Date: 2026-07-14. `/_template:entry` arg-given. 스키마/마이그/RBAC/엔드포인트/서버 계약 0 — 프론트 단독·비파괴.
- 근본원인: 사용자 보고 3종 애니(대화 전환 크로스페이드·point-rail 뱃지 스크롤·캘린더 버튼 스크롤)가 `prefers-reduced-motion: reduce` 매칭 시 통째로 즉시(instant)로 degrade. 코드/배포는 정상(소스 애니 증가·배포 byte-동일). Windows 에서 이 미디어쿼리는 "동작 줄이기"가 아니라 설정>접근성>시각 효과>애니메이션 효과·배터리 절약 모드에 매핑 → 사용자 미인지 상태로 "최근 갑자기" 발동 가능.
- 변경:
  - `static/app.js`: `_prefersReducedMotion()` 을 pref-aware 로 개편 — 신규 `MOTION_PREF_KEY="mad.motionEffect.v1"`(localStorage `os`/`on`/`off`)·`getMotionPref`/`setMotionPref`/`applyMotionPref`(`<html data-motion>` 반영)/`_osPrefersReducedMotion`. `on`=항상 애니(줄임 안 함)·`off`=항상 줄임·`os`=OS 신호(기본, 하위호환). 캘린더 `jumpToHistoryAnchor`·검색 `_jumpToSearchMatchedMessage` 의 네이티브 `scrollIntoView({behavior:"smooth",block:"center"})` → pref-aware `scrollMessagePointIntoCenter`(point-rail 과 동일 EaseOutExpo 경로)로 라우팅 → `on` 이면 OS reduce-motion 에서도 부드럽게 이동. `renderMotionPref()` 신규 + 계정 탭 렌더/change 리스너/`initialize()` 의 `applyMotionPref()` 배선.
  - `static/index.html`: 프로필 드로어 '계정' 탭에 '화면 효과 > 애니메이션 효과' select(`#motionEffectSelect`, 시스템 설정 따름/항상 켬/항상 끔) `profile-section#profileMotionSection` 추가.
  - `static/styles.css`: `.profile-select-row`/`.profile-motion-select` 정합 스타일(toggle-row 시각 정합).
- 검증: `node --check app.js` PASS · 심볼/배선 확인 · 잔여 네이티브 smooth-into-center `scrollIntoView({behavior:"smooth"})` 0건 · `os` 기본값 하위호환(회귀 표면 0). §18.8 적대 서브에이전트 리뷰(REVIEW). POST-DEPLOY PB-0008 라이브 시각검증(TEST §Run 2026-07-14 anim-effect-pref).
- Cross-ref: TASK-20260714T065503-anim-effect-pref · REV-20260714T065503-anim-effect-pref · TEST Run(2026-07-14) anim-effect-pref · ANCHOR 0003 무충돌.

## CHG-20260713T101500-ds-conn-test-postverify (TASK-20260713T094624-ds-conn-test POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-13. 코드/자산 무변경 — test-runs.d/20260713T094624-ds-conn-test.md 에 POST-DEPLOY 라이브 PASS append + TASK.md 체크리스트 완료 + REVIEW postverify 엔트리. 배포 PR #767→main 02a1e585, `make deploy-web` 무중단 롤링(soak PASS).
- 라이브 실측 요지(https://localhost/ bootstrap_admin, win-browser relay Chrome): AC-1 15 DS 배지 전부 `<button.product-dropup-item-ds--test>`·AC-2 클릭→"✓ 연결 성공(11.8ms)" 상단 토스트(top 66px·입력창 비가림)·AC-4 제품 미전환·AC-5 프론트 쿨다운 발화·AC-6 admin 토스트 하단 불변·AC-7 pageerror 0.
- Cross-ref: CHG-20260713T094624-ds-conn-test(기능) · REV-20260713T101500-ds-conn-test-postverify · test-runs.d fragment.

## CHG-20260713T094624-ds-conn-test (TASK-20260713T094624-ds-conn-test — 작업화면 제품 드롭업 데이터소스 '연결 테스트' 버튼 + 상단 단발성 토스트, Major §12.3)
- Date: 2026-07-13. `/_template:entry` arg-given. 스키마/마이그/신규 RBAC/신규 엔드포인트 0.
- 변경:
  - `static/app.js`: `buildProductDropupItem` — 데이터소스 배지를 `_dsTestable = !viewOnly && canOpenAdminConsole()` 게이트로 실제 `<button>`('연결 테스트') 렌더(`_makeDsBadge`, 무권한/열람전용은 기존 display-only span). **행 요소 `<button>`→`<div role=menuitem>` + `tabIndex=0` + click/keydown(Enter/Space) 선택 복원**(중첩 `<button>` 회피). 신규 `runDatasourceConnTest(keys, badgeEl)` — 프론트 쿨다운(`PRODUCT_DS_TEST_COOLDOWN_MS=4000`·`_dsTestLastAt` `.has()` sentinel)·진행 중 `disabled`·단일/멀티(순차+요약)·403(apiFetch 위임)/429(중립)/실패(에러) 상단 토스트.
  - `static/styles.css`: `#toast` 상단 앵커(`top: calc(var(--topbar-h,52px)+14px)`·`bottom:auto`·`max-width: min(460px, calc(100vw-32px))`·`transition` 에 background 추가·`#toast.is-visible`) — 작업화면 전 토스트 상단화(admin `#adminToast` 하단 불변, id 스코프). `button.product-dropup-item-ds--test`(font reset·min-height 24px·at-rest 테두리·hover 틴트·:focus-visible·:disabled).
  - `routers/admin_datasources.py`: import `os`/`time`. 모듈 상태 `_DS_TEST_COOLDOWN_SEC`(env `AGENT_DS_TEST_COOLDOWN_SEC` 기본 3, try/except 폴백)·`_ds_test_last_at`·`_DS_TEST_LRU_CAP=4096`. 신규 `_ds_test_throttle_check(account_id, key)`(per-(account,key) 쿨다운·LRU prune·throttled 반환 `max(1.0, round(ms))`). `admin_test_datasource`: resolve/SSRF 이후·probe 직전에 throttle 게이트 — 미경과 시 probe 없이 **429**(body: key/ok/elapsed_ms/error/status/throttled/retry_after_ms(int)).
  - `static/admin.js`: `_probeDatasourceConn` — `const _prev` 함수 스코프 캡처 + 429 catch 시 'down' 대신 직전 확정 상태 유지. 상세 `_dsRenderDetail` '연결 테스트' + 제품바인딩 ⋯ '연결 테스트' catch 에 429=중립 토스트 분기.
  - `tests/verify_profile_icon_consistency.mjs`: 하네스에 `canOpenAdminConsole(){return false;}` 스텁(display-only 경로 유지). `tests/test_datasource_test_nonblocking.py`: autouse `_reset_ds_test_throttle` fixture + throttle 계약 테스트 2건(T4 반복→429·독립 account/key, T5 404 무-throttle).
- 검증: `node --check`(app.js·admin.js module)·`py_compile`·CSS 1780/1780·타깃 6/6·**전체 pytest 1902 passed / 2 skipped / 0 failed**. §18.8 3렌즈 패널 SHIP-WITH-FIXES→반영 후 SHIP.
- Cross-ref: REV-20260713T094624-ds-conn-test · REPORT §1 · TASK-20260713T094624-ds-conn-test · TEST test-runs.d/20260713T094624-ds-conn-test.md · FUNCTION §13.

## CHG-20260713T061500-attach-user-version-postverify (TASK-20260713T053423-attach-user-version POST-DEPLOY PB-0008 라이브 검증 기록, 비-정책 doc-only)
- Date: 2026-07-13. 코드/자산 무변경 — TEST.md §4 Windows-browser Run 을 "배포 후 잔여" → **POST-DEPLOY 라이브 PASS** 로 갱신 + TASK.md 체크리스트 완료. 배포: PR #751→main 7f1ed748, web-a/web-b 무중단 롤링 + ask-worker 재빌드(agent_core 변경 baked).
- 검증 요지(https://localhost/, bootstrap_admin, win-browser relay Chrome/150): 라이브 e2e — v1(490)→v2(491, root=490 편입)→동일 재업로드(491 reused)→버전 체인 2개(v1 superseded/v2 최신)→목록 최신만(version_count=2); **assistant 가 v1→v2 diff(SELECT 1→2·-- changed 추가) 정확 인지**(new_attachment_ids 포함 시), 미포함 턴엔 정직 "비교 불가"(환각 0). Evidence artifacts/shared/win-browser-shots-attach-user-version/01_version_badge_and_assistant_diff.png.
- Cross-ref: CHG-20260713T053423-attach-user-version(기능) · TEST.md §4 2026-07-13 Run · REV-20260713T053423-attach-user-version.

## CHG-20260713T053423-attach-user-version (TASK-20260713T053423-attach-user-version — 사용자 재업로드 첨부 버전 관리, Major §12.3, cross-cut feature-0002)
- 변경:
  - `routers/_conv_store.py`: 신규 `_find_latest_same_name_attachment(conn, conversation_id, account_id, filename)`(대화 내 `(ConversationId,AccountId,OriginalFilename)` 최신 비-superseded·비-deleted head 1건 — 버전 체인 편입 판정, MySQL write-consistent)·`_compute_version_diff(prev, new, *, prev_version, new_version, filename, cap_bytes)`(difflib unified diff, size-cap `_ASSISTANT_EDIT_SIZE_CAP_BYTES`, truncated 플래그).
  - `app.py`: p15 rebind 블록에 `_find_latest_same_name_attachment`·`_compute_version_diff` import 추가(app.X 노출).
  - `routers/conversations.py` `upload_conversation_attachment`: sha256 계산 직후 prior head 조회 → **해시 일치=기존 최신 버전 재사용**(INSERT/MinIO put skip, 기존 payload + `reused_existing_version:true` 반환) / **불일치=새 버전**(root=prior.root||prior.Id·`VersionNumber=MAX+1`·텍스트계열 diff 를 `MetaJson.version_diff` 저장). INSERT 를 버전 컬럼(`MetaJson,RootAttachmentId,VersionNumber,CreatedByRole='user'`) 명시로 확장(prior 없음 시 NULL/1/NULL='user' → 기존 default byte-동치). commit 후 직전 버전 `SET SupersededAt=UTC_TIMESTAMP(6) WHERE VersionNumber<new` + PG dual-write 를 체인 전체 id 로 확장.
  - `unit/feature-0002-agent-core/src/agent_core.py` `_build_attachment_context_section`: PG/MySQL SELECT 에 `root_attachment_id/version_number/created_by_role`(row[9..11]) append(기존 index 0~8 보존)·`version_number>1` 파일 라인에 🔄v{n} 표식(사용자/AI 구분)·`MetaJson.version_diff` 수집 → `## FILE UPDATES` 섹션에 `_datamark_untrusted` 후 ```diff``` 주입 + 지침.
  - `static/app.js`: 신규 `_sha256HexOfFile`(crypto.subtle)·`_attachUploadDoneMessage`(버전 상태별 toast). `_uploadComposerAttachment` 클라이언트 dedup 을 이름+크기 → **해시 대조**로 정밀화(동일 내용만 차단). 업로드 성공 3지점(earlyCid·activeConv·staged flush) pill 에 `sha256`/`version_number` 적재 + 버전 인지 toast. 목록 로더 pill 에 `sha256` 적재.
  - tests: `unit/feature-0003-agent-web-ui/tests/test_attachment_versioning.py` +6(U1 diff·U2 truncate·U3/U4 find·U5 upload 정적)·신규 `unit/feature-0002-agent-core/tests/test_attachment_user_version_context.py` +5(표식·FILE UPDATES·datamark·truncate·v1 무회귀).
  - docs: FUNCTION.md REQ-20260713-attach-user-version(AC-AUV-1~6)·TASK.md(PLAN-APPROVED)·REPORT.md·TEST.md §4·REVIEW.md.
- 스키마/마이그레이션/RBAC/엔드포인트 shape: **무변경**(버전 컬럼 전부 기존재 — TASK-0274/0008). 응답 필드 additive(`reused_existing_version`)·MetaJson additive(`version_diff`).
- 검증: py_compile 4 + node --check PASS · 첨부 버전 31 PASS · 전체 스위트 EXIT=0(회귀 0). §18.8 REV-20260713T053423-attach-user-version. Cross-ref: TASK/FUNCTION-20260713T053423-attach-user-version · 기반 TASK-0274/0275/0285/0286(버전 인프라)·0008 core_attachments 스키마.

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

## CHG-20260712T073000-item09-graph-split (admin.js 그래프 분리)
- Date: 2026-07-12. admin.js 3618~9024→static/graph/graph.js(pure move, -5,407). type=module+bridge. 자동검증 GREEN. 브라우저 QA 대기.

## CHG-20260712T190500-item09-batch23-stamp (그래프 CSS/JS 세분화 + 캐시버스터 자동화)
- Date: 2026-07-12. 변경: ① batch2 — styles.css 그래프 밴드(8246~8682, 437줄)→graph/graph.css(공유 2예외 잔류), admin.html link 추가 ② batch3 — graph.js→7모듈+barrel(섹션-연속 pure move, import/export 표면은 census 마스킹 참조로 기계 산출, 죽은 _metaSubmitForm import 제거) ③ what#3 — ?v= 소스 placeholder(?v=dev) 고정 + inject_asset_stamp.py 빌드 주입(content-hash, vendor pin 보존) + deploy-web asset_stamp_verify 하드게이트(구 asset_stamp_warn 대체) + ES import specifier 스탬프(이중 인스턴스화 해소).
- Files: static/{styles.css,admin.html,index.html,share.html,admin.js}, static/graph/{graph.js,graph-*.js,graph.css,MAPPING.md}, feature-0002 src/{Dockerfile,scripts/inject_asset_stamp.py}, bin/deploy-web.sh, .gitattributes, AGENTS.md §13.1, ROADMAP.
- Verification: node --check 8/8 · 이동구간 verbatim 7/7 · 미해결참조/ghost-export 0 · CSS byte-eq+brace 0 · inject 멱등(--check=a888c8833eb6) · PB-0008 실브라우저(렌더 픽셀동일·스코프·검색·줌·클릭·우클릭, 콘솔 에러 0).
- Rollback: 커밋 revert(atomic PR). 배포 실패 시 deploy-web last-good 자동 롤백.


## CHG-20260713T102249-doc-sync-rn-0713 (TASK-20260713T102249-doc-sync-rn-0713 — 07-09~10 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: releases[0] 에 `date:"2026-07-10"` 새 블록 prepend(`generated` 2026-07-10) — 7항목(fixed/work 1·improved admin 5·improved/common 1). 07-09 이하 블록 보존.
- **cache-buster 무변경**: 소스 `?v=dev` placeholder 고정(ITEM-09 what#3 이후 수기 bump 폐지) — Dockerfile `inject_asset_stamp.py` 가 배포 시 content-hash 주입, deploy-web `asset_stamp_verify` 가 baked placeholder 잔존 하드 차단. index/admin.html 편집 0.
- 제외: POST-DEPLOY/docs-only 커밋·추론예산(07-09 기출시·docs/RELEASE_NOTES 미러에만 추가)·07-11~13 behavior-neutral(feature-0012 라우터 모듈화 완결·ITEM-09 그래프 CSS/JS·META 툴링). 07-08/07-09 블록과 중복 0.
- **§69 편입**: 07-10 run REJECT(T69.5 미완) → 07-13 PR #744 T69.5 완수(cc_data_main 715/715)로 라이브 관측 가능 → 편입.
- Verification: `node --check release-notes-data.js` PASS · vm 구조검증(블록순서·스키마·누출0). 사용자향 평이화(내부용어 누출 0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포는 본 attended run 소유(PR→merge→make deploy-web). META(STATUS·wiki·ARCHITECTURE·RELEASE_NOTES·meta/REVIEW)는 별도 commit(REV-20260713T102249-META-doc-sync-0713).


## CHG-20260713T181800-graph-perm-split (그래프 뷰 권한을 '메타데이터 관리' 묶음에서 분리 — Critical §12.3 인증/인가, 사용자 승인 B안)
- Date: 2026-07-13. 요청(/_template:entry): "그래프 뷰가 별도의 탭으로 분리됨에 따라, 권한 또한 '메타데이터 관리'로부터 별도로 분리." 결정: **B안(분리 + 기존 접근 보존, 비파괴)**.
- 변경(behavior — RBAC):
  - `src/web_context.py`: `_METADATA_MANUAL_IMPLIES` 에서 `metadata.graph.read` 제거(편집 4종만 함의) · 묶음 `kb.ingest.manual` 설명·`metadata.graph.read` 라벨("그래프 뷰 조회")/설명 갱신 · 신규 `_backfill_graph_perm_split_v1(conn)`(1회 접근보존 backfill, `_ensure_seed_roles` 말미 호출) + `_GRAPH_PERM_SPLIT_MIGRATION_KEY` 상수.
  - `src/routers/_bootstrap_schema.py`: `WebSchemaMigrations(MigrationKey PK, AppliedAt)` DDL — 1회 웹 DB 마이그레이션 guard 저장소.
  - `src/static/admin.js`: `ADMIN_TAB_PERMISSIONS.graph` = `["metadata.graph.read"]`(묶음 인정 제거) · `PERMISSION_DEPENDENCIES["metadata.graph.read"]` = `"console.access"`(묶음 하위→직속 승격).
  - `src/static/admin.html`: 그래프 탭 게이트 주석 갱신.
  - `tests/test_metadata_perm_split.py`, `tests/test_permission_dependency_map.py`: 분리 계약 반영(R3 편집4종·R3c 묶음 graph 미함의·R3d 독립부여·t5 graph.read=console.access·m3 포함).
- 하위호환(비파괴·가역): backfill 이 분리 전환 1회에 (a) 묶음 보유 role→graph.read role권한, (b) 묶음 ALLOW override 계정→graph.read ALLOW override(graph.read DENY 는 존중). `WebSchemaMigrations` 마커로 재실행 차단. admin 은 기존 explicit catchup 으로 graph.read 유지.
- Files: `src/web_context.py`, `src/routers/_bootstrap_schema.py`, `src/routers/admin_metadata.py`(docstring), `src/static/admin.js`, `src/static/admin.html`, `tests/test_metadata_perm_split.py`, `tests/test_permission_dependency_map.py`, `docs/{TASK,MODIFY,REPORT,REVIEW,TEST}.md`, `static/release-notes-data.js`.
- Verification: 권한 단위테스트(perm-split/dependency-map/glossary-enum) + feature-0003 전체 스위트 PASS(회귀 0) · §18.8 보안 렌즈 적대 리뷰(권한상승·접근상실·멱등·enforcement·SQL, 라이브 MySQL 8.0.46 실증) — 3 findings(A MEDIUM 권한상승·B LOW 멱등·C NIT docstring) 적발·수정 후 VERDICT PASS.
- Rollback: 커밋 revert. backfill 은 grant 추가만(파괴 없음) — revert 후에도 부여된 graph.read 는 잔존(관리 콘솔에서 명시 회수 가능). `WebSchemaMigrations` 마커 row 는 잔존(무해).
- 잔여: verify-completion → commit(사용자 confirm) → 머지·push → web 재배포 → 배포 후 DB 마커·라이브 권한 그리드 + PB-0008 실렌더.

## CHG-20260713T185600-graph-perm-descfix (graph-perm-split 배포 후 seed catchup 1406 hotfix — 권한 설명 255자 초과)
- Date: 2026-07-13. 배포 후 실증에서 `WebSchemaMigrations` 미생성·backfill 미실행 적발. web 로그 `seed catchup skipped: 1406 Data too long for column 'Description'`. 근본원인: `kb.ingest.manual` 설명 301자 > `WebPermissions.Description` VARCHAR(255) → `_ensure_permission_catalog` 1406 → `_ensure_seed_catchup`(fast path) 전체 skip → seed_roles/backfill 미실행. CI(`--no-deps`)가 컬럼 제약 미검출.
- 변경(behavior — 부트스트랩 robustness):
  - `src/web_context.py` `_ensure_permission_catalog`: `label[:128]`·`description[:255]` 방어적 클립(단일 긴 문자열이 전 catchup 을 차단하던 fragility 제거).
  - `src/web_context.py` `kb.ingest.manual` description 301→205자 단축(온전 저장, 잘림 0).
- 영향: 그래프 접근 상실 사용자 0명(유일 묶음 보유=admin, 이미 graph.read 보유). 부트스트랩 catchup 재개가 핵심.
- Files: `src/web_context.py`, `docs/{TASK,MODIFY,REPORT,REVIEW,FUNCTION}.md`, `docs/test-runs.d/*`.
- Verification: py_compile OK · feature-0003 전체 스위트 PASS(회귀 0) · 전 권한 desc≤255·label≤128 전수 확인.
- Rollback: 커밋 revert(설명 길이만 원복 시 1406 재발하므로 truncation 클립은 유지 권장).
- 잔여: 배포 후 web 로그 `seed catchup skipped` 소멸 + `WebSchemaMigrations` graph-perm-split-v1 row 실증.


## CHG-20260714T024534-doc-sync-rn-0714 (TASK-20260714T024534-doc-sync-rn-0714 — 07-13 오후 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: releases[0](date "2026-07-13") items 에 **+7항목** append(improved/admin 4·new/work 2·fixed/work 1)·summary 재작성. generated 2026-07-13 유지(새 date 블록 생성 안 함). 07-10 이하 블록 보존.
- **cache-buster 무변경**: 소스 `?v=dev` placeholder 고정(§13.1 ITEM-09 what#3 — Dockerfile `inject_asset_stamp.py` content-hash 빌드 주입·deploy-web `asset_stamp_verify` 하드게이트). index/admin.html 편집 0. release-notes-data.js 내용 변경만으로 전역 content-hash 변화 → wrapper 재빌드 시 서빙 토큰 자동 갱신(수동 bump 부적용·해시 불변).
- 제외: feature-0019 메시지 편집(backend-only)·describe_routine(unverified-live)·내부 렌더 최적화(§79/§80)·deploy checklist.
- Verification: `node --check` PASS · vm 구조검증(블록순서·스키마·07-13 8항목·누출0). 사용자향 평이화(내부용어 누출 0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- **landing/배포 소유=cron wrapper 위임**(로컬 commit 만·push/merge/deploy 미수행). META(STATUS·wiki·ARCHITECTURE·SECURITY·meta/REVIEW)는 별도 commit(REV-20260714T024534-META-0035-doc-sync-0714).

## CHG-20260713T185846-attach-filename-consistency (첨부 새 버전 파일명 코드-권위 정합, secondary cross-ref, conversation_audit FR-attachment-update-pasted-not-versioned)
- Date: 2026-07-13. `/_dqa:conversation_audit "첨부파일 갱신"` 의 **secondary(cross-ref)** — primary=feature-0002 프롬프트(CHG-20260713T185846-attach-update-versioned). 사용자 요구 2항: "갱신된 파일의 명칭도 기존과 정합(버전 접미)".
- Reason(RC): 명명 정합이 코드로 보장되지 않음 — `_next_version_filename` 은 LLM 이 filename 을 **생략할 때만** 적용됐고, 프롬프트는 오히려 LLM 에게 `report_v2.csv` 수동 지정을 유도 → 버전 불일치·재편집 이중접미(`report_v2.csv`→`report_v2_v3.csv`) 가능.
- Changes (`src/routers/_conv_store.py`):
  - `_next_version_filename` idempotent 강화: stem 의 기존 `_v<n>$` 접미를 `app.re.sub` 로 제거 후 재부여 → 재편집 이중접미 방지(`report_v2.csv`+v3→`report_v3.csv`). 확장자 없는 이름도 처리.
  - `_materialize_assistant_attachment_edits` 명명 블록을 **코드-권위**로 교체: LLM `filename` 유무와 무관하게 항상 `<stem>_v<next_version>.<src_ext>` 생성. LLM 이 이름을 줘도 stem 만 취하고 버전 접미를 강제, 확장자는 source 를 강제 보존(보안리뷰 V3 `.exe` 차단 불변; 확장자 부재 source 는 kind 기반 안전값 §18.8 SEC-1).
- Recurrence sealing: LLM-dependent 명명 → 코드 권위 명명(AUTH-1a). materialize 가드(conv/account scope·size cap·text-only·MinIO 원자성·UNIQUE version race) 전부 불변. **보안 회귀 0**.
- 검증: `tests/test_attachment_versioning.py` 명명 정합 케이스(idempotent·이중접미 방지·확장자 강제·SEC-1) + feature-0003 회귀. §18.8 패널 REV-20260713T185846.
- Cross-ref(정본): feature-0002 CHG-20260713T185846-attach-update-versioned · FRICTION_LEDGER FR-attachment-update-pasted-not-versioned · ANCHOR 0003 무충돌.
## CHG-20260714T105200-graph-analyze-perm (그래프 AI 능동 분석 실행 권한을 하위 권한으로 분리 — Critical §12.3 인증/인가)
- Date: 2026-07-14. 요청: AI 능동 분석 '실행' 권한을 조회(metadata.graph.read)에서 하위 권한으로 구분 + 무권한 시 버튼 UI 미표시. 하위호환=A안(최소권한, backfill 없음).
- 변경(behavior — RBAC):
  - `src/web_context.py`: 신규 `metadata.graph.analyze`("그래프 AI 능동 분석 실행", group=kb) + `metadata.graph.read` 설명 갱신(조회+결과열람 / 실행은 하위 권한으로 분리) + `_ensure_seed_roles` admin catchup 에 `metadata.graph.analyze` 추가(기존 admin 락아웃 방지).
  - `src/routers/admin_metadata.py`: 실행 POST 2개 `require_permission` `metadata.graph.read`→`metadata.graph.analyze` (`/graph/analyze` 노드, `/graph/analyze-schema` 스키마) + docstring 갱신. GET status/node/columns 는 graph.read 유지(읽기).
  - `src/static/admin.js`: `PERMISSION_DEPENDENCIES` 에 `metadata.graph.analyze → metadata.graph.read`(하위, progressive disclosure).
  - `src/static/graph/graph-ctxmenu.js`: 능동 분석 트리거 UI 5곳 `can("metadata.graph.analyze")` 게이팅 — 노드 상세 AI 섹션(#metaGraphAiSec, 미렌더+바인딩 skip)·노드 우클릭·스키마 우클릭·combo 우클릭·클러스터 카드 버튼.
  - tests: `test_metadata_perm_split.py`(graph.read 만으론 analyze 미부여·독립부여·admin catchup·catalog/seed) + `test_permission_dependency_map.py`(t5 graph.analyze→graph.read 종속·depth).
- 하위호환: A안 — graph.read 보유자에게 analyze backfill 없음(명시 부여). admin 은 catchup 으로 획득. 현재 graph.read 보유자 admin 뿐 → 실질 영향 0. 데이터 마이그레이션 없음(WebSchemaMigrations 마커 불요).
- Files: `src/web_context.py`, `src/routers/admin_metadata.py`, `src/static/admin.js`, `src/static/graph/graph-ctxmenu.js`, `tests/{test_metadata_perm_split,test_permission_dependency_map}.py`, `docs/{FUNCTION,TASK,MODIFY,REPORT,REVIEW}.md`, `docs/test-runs.d/*`.
- Verification: py_compile + node --check(module) OK · 권한 타깃 + feature-0003 전체 스위트 PASS(회귀 0) · §18.8 보안 렌즈 적대 리뷰.
- Rollback: 커밋 revert. grant 추가만(파괴 없음) — revert 후 admin 의 graph.analyze row 는 잔존(관리 콘솔 회수 가능).
- 잔여: 배포 후 graph.read-only 계정 버튼 미노출·POST 403 / graph.analyze 계정 버튼·실행 정상 실증.
## CHG-20260714T015432-step-scroll-preserve (TASK-20260714T015432-step-scroll-preserve — 실행 단계 폴링 갱신 시 펼친 "결과 보기" 스크롤 보존, Minor §12.3 frontend-only)
- Date: 2026-07-14. 사용자 보고: 내부 실행 단계 갱신 때마다 펼쳐 둔 "결과 보기" 스크롤이 초기값으로 리셋. RC: 두 라이브 폴링 재렌더 경로가 컨테이너를 `innerHTML=""` 로 통째 재작성 → 결과 표/미리보기·외부 목록 스크롤 0 초기화(펼침 상태는 `state.stepResultExpanded`+`_stepResultKey` 로 이미 복원되나 스크롤은 미복원).
- Changes (`src/static/app.js`):
  - `buildStepDetailEl`: 결과 wrap(`.step-result-wrap`)에 `dataset.stepResultKey = stepKey`(`_stepResultKey`=step_index+created_at) 부여 — 재렌더 간 스크롤 매칭 안정 키(펼침 영속화와 동일 키 재사용).
  - 신규 제네릭 헬퍼 `_snapshotStepResultScroll(body)` / `_restoreStepResultScroll(body, map)`: 컨테이너 내 펼쳐진(`[data-step-result-key]` 비-hidden) 결과의 `.result-table-wrap`/`.step-result-preview` 스크롤(top/left)을 stepKey 로 Map 캡처·복원. 접힘·미매칭·null/빈맵 방어.
  - `_renderStepSidePanelBody`(사이드 패널): 재렌더 전 `prevScrollTop`+`_snapshotStepResultScroll(body)` → `body.innerHTML=""` 재작성 → `_restoreStepResultScroll` + 외부 스크롤(하단추종=최하단 / 미추종=`Math.min(prevScrollTop, maxTop)` 유지, 기존 미추종 0 리셋 제거).
  - `renderProgress`(인라인 progress 카드): 동일 규약을 `progressStepsEl` 에 적용(progAtBottom/progPrevTop + snapshot/restore).
- 무회귀: 펼침/토글 동작·하단추종 자동스크롤·step dedup 키 불변. 백엔드/엔드포인트/RBAC/스키마 0. 표준 DOM scroll semantics.
- 검증: `node --check app.js` PASS · 신규 `tests/verify_step_result_scroll_preserve.mjs`(jsdom, 소스추출 격리) **23/23 PASS**. 정적 자산 baked → 시각 최종확인 PB-0008 배포 후 잔여(§CHECK#13, visual_verification_scope: always).
- Files: `src/static/app.js`, `tests/verify_step_result_scroll_preserve.mjs`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,TEST,REPORT}.md`, `docs/test-runs.d/20260714T015432-step-scroll-preserve.md`.
- Cross-ref: REV-20260714T015432-step-scroll-preserve · REQ/AC-SSP-1~3.

## CHG-20260714T133700-routemap-refresh (graph-analyze-perm 후속 — docs/ROUTEMAP.md 재생성, 자동생성 artifact)
- Date: 2026-07-14. graph-analyze-perm(PR #783, e7c31e3e) 이 analyze POST 2개의 `require_permission` 를 graph.read→graph.analyze 로 바꿨는데 `docs/ROUTEMAP.md`(route→permission 자동 맵) 재생성을 누락 → main CI "Code-Navigation Map gate"(`gen-routemap.py --check` exit 3, ROUTEMAP STALE) 적색. **원인**: verify-completion CHECK#15 는 diff 에 구조적 route 추가/삭제가 있을 때만 gen-routemap --check 를 돌려 permission-only drift 를 로컬 미검출(CI 는 무조건 검사).
- 변경: `python3 bin/gen-routemap.py` 재실행 → `docs/ROUTEMAP.md` 의 `/graph/analyze`·`/graph/analyze-schema` 두 POST 행 permission 을 `metadata.graph.analyze` 로 갱신(2행, 202 routes 중). **코드/런타임 무변경**(auto-generated 내비 doc only).
- Files: `docs/ROUTEMAP.md`, `docs/{TASK,MODIFY,REVIEW}.md`.
- Verification: `gen-routemap.py --check` exit 0(up-to-date) · `codenav-lint.sh` OK.
- Cross-ref: CHG-20260714T105200-graph-analyze-perm(원천) · REV-20260714T133700-routemap-refresh.

## CHG-20260714T053522-step-scroll-raf (TASK-20260714T053522-step-scroll-raf — 펼친 "결과 보기" 가로 스크롤 layout-timing 0-clamp 후속, Minor §12.3 frontend-only)
- Date: 2026-07-14. step-scroll-preserve(CHG-...T015432) 배포 후 사용자 재보고("가로 스크롤이 지속적으로 초기화 여전히 남아있음"). RC: 동기 `_restoreStepResultScroll` 이 재렌더 직후 결과 표 layout 확정 전에 `scrollLeft` 를 써서 브라우저가 `scrollWidth`(overflow 미확정)로 0-clamp. 라운드1 jsdom 테스트는 scrollLeft verbatim 저장이라 미검출.
- Changes (`src/static/app.js`):
  - 신규 `_applyStepPanelScroll(container, resultScroll, atBottom, prevTop)`: 내부 결과셋(`_restoreStepResultScroll`) + 외부 목록 스크롤(하단추종=최하단 / 미추종=`Math.min(prevTop, maxTop)`)을 함께 복원.
  - 신규 `_scheduleStepPanelScroll(...)`: `_applyStepPanelScroll` 을 **동기 1회 + `requestAnimationFrame` 1회** 적용(rAF 로 layout 확정 후 재적용 → 0-clamp 복구). rAF 는 다음 폴링보다 훨씬 앞서(≈16ms) 실행 → 재진입 경합 없음.
  - `_renderStepSidePanelBody`·`renderProgress` 의 인라인 복원 블록(동기 restore + if/else 외부 스크롤)을 `_scheduleStepPanelScroll(...)` 호출로 대체.
- 무회귀: 순수 additive(동기 복원 유지 + rAF 추가, 동일 캡처값 재적용). 펼침/토글·하단추종·dedup 키·백엔드/RBAC/스키마 0.
- 검증: `node --check` PASS · `tests/verify_step_result_scroll_preserve.mjs` **29/29 PASS**(+5: [3b] rAF 배선·[7] 동기+rAF 이중 복원·0-clamp 복구·큐 소진). 로컬 chromium 다운로드 차단으로 real-browser clamp 는 미재현 — 배포 후 사용자/PB-0008 확인.
- Files: `src/static/app.js`, `tests/verify_step_result_scroll_preserve.mjs`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,TEST,REPORT}.md`, `docs/test-runs.d/20260714T053522-step-scroll-raf.md`.
- Cross-ref: REV/TASK/AC-SSP-4-20260714T053522 · 원천 REQ-20260714T015432-step-scroll-preserve.

## CHG-20260714T180314-graph-entry-help (TASK-20260714T1803-graph-entry-help — 그래프 뷰 첫 입장 도움말 팝업 + 중간버튼 커서, Minor §12.3 frontend-only additive)
- Date: 2026-07-14. 사용자 요청: 그래프 뷰 첫 입장 조작 도움말 팝업(닫기·재확인 가능) + 마우스 중간 버튼 클릭 시 커서 적절 변경. `/_template:entry` arg-given. 그래프 도메인 정본 feature-0016.
- Changes:
  - `src/static/admin.html`: 툴바 `❓ 도움말` 버튼(`#metadataGraphHelpBtn`, 초기화·상세 옆) + 캔버스 wrap(role=img 밖 형제 — 접근성) 내 `#metadataGraphHelp` 오버레이(role=dialog·aria-modal, 8개 조작 항목·읽기전용 고지·✕/알겠습니다).
  - `src/static/graph/graph.css`: `.amg-help-*` 스타일 — `.admin-meta-graph-canvas-wrap`(position:relative) 기준 절대배치 inset:0·z-index 40(줌6/상태6/미니맵5/보기옵션30 위)·중앙 카드+반투명 backdrop·amgHelpIn 애니·좁은 폭 라벨 세로 스택. 토큰(--surface/--border/--text*/--primary)만 써 라이트/다크 자동.
  - `src/static/graph/graph-core.js`: `_metaGraphShowHelp`/`_metaGraphHideHelp`/`_metaGraphMaybeAutoHelp`/`_metaGraphBindHelp` 신설(+`_META_HELP_SEEN_KEY`/`_metaHelpKeydown`). `_metaShowGraph` 에 `_metaGraphBindHelp()`(멱등 `_helpBound`) + 검색 포커스 뒤 `_metaGraphMaybeAutoHelp()` 훅. 첫 진입 1회 자동노출=`localStorage("metaGraphHelpSeen")` 미확인 시만, 닫으면 seen set. 닫기 4경로(✕·알겠습니다·배경 target 판정·Esc capture)·a11y 포커스 이동/복귀·localStorage try/catch 안전 강등. 중간버튼: 기존 container `mousedown` button===1 핸들러에 `cursor="grabbing"` + mouseup(buttons&4 유지 가드)·blur 복원.
- 무회귀: 순수 additive. 백엔드/엔드포인트/RBAC/스키마 0 · 기존 그래프 상호작용(팬·노드드래그·우클릭·줌·미니맵)·이벤트 바인딩 0 · cache-buster `?v=dev` placeholder(빌드 content-hash 자동주입) 수기편집 없음.
- 검증: `node --check --input-type=module`(graph-core.js) PASS · admin.html 도움말 블록 태그 균형 · graph.css 중괄호 215/215 · 심볼 전수 존재. PB-0008 라이브=POST-DEPLOY 이연(정적 baked).
- Files: `src/static/admin.html`, `src/static/graph/graph.css`, `src/static/graph/graph-core.js`, `docs/{TASK,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260714T180314-graph-entry-help.md`.
- Cross-ref: REV/TASK-20260714T1803-graph-entry-help · TEST test-runs.d/20260714T180314-graph-entry-help.md · ANCHOR 0003 무충돌.

## CHG-20260714T184717-graph-help-overlay-fix (TASK-20260714T184717-graph-help-overlay-fix — 그래프 도움말 팝업 mis-position 근본원인 수정, Minor §12.3 frontend-only)
- Date: 2026-07-14. POST-DEPLOY 후속(graph-entry-help 배포 1f705a9e 직후 사용자 지적: "도움말 팝업을 그래프 뷰 중앙에 위치·좌하단 줌 컨트롤 겹침 해결"). `/_template:resume` 재개.
- 근본원인: `graph.css` 도움말 스타일 주석(CHG-20260714T180314-graph-entry-help 에서 작성)의 토큰 목록 `토큰(--surface/--border/--text*/--primary)만` 에서 `--text*` 뒤 `/` 와 결합해 **`*/` 서브스트링**이 생겨 CSS 주석이 조기 종료 → 이후 텍스트가 깨진 CSS 로 유입 → 바로 아래 `.amg-help-overlay { position:absolute … }` 규칙이 파서에서 통째 드롭 → position `static` 폴백 → flex column 흐름상 캔버스 아래 렌더 → 팝업이 줌 컨트롤과 겹침. (라이브 CDP: `getComputedStyle` 전 속성 기본값 + `sheet.cssRules` 에 bare `.amg-help-overlay` 부재 + 격리 파싱은 정상 → 직전 주석 문맥 문제로 특정. `/*`:`*/` 개수 61:62 → 61:61.)
- Changes:
  - `src/static/graph/graph.css`: 주석 line ~447 토큰 구분자 `/` → `·`(`--surface·--border·--text*·--primary`)로 `*/` 서브스트링 제거 + 재발 방지 NOTE 2줄 삽입. **CSS 선언·선택자·미디어쿼리 무변경**(주석 텍스트 국한).
- 무회귀: CSS 규칙/선택자/미디어쿼리 0 변경(git diff +4/-2, 주석만). 백엔드/RBAC/스키마/JS/HTML 0. cache-buster `?v=dev` placeholder(빌드 content-hash 자동주입) 수기편집 없음.
- 검증: (a) 수정본 파싱 시 `.amg-help-overlay` 규칙 복구·`position:absolute`(rule 204→205). (b) 라이브 규칙 주입 후 geometry: 카드 canvas-wrap 정중앙(dx:0 dy:0)·줌 컨트롤 미겹침(card_overlaps_zoom:false). (c) §18.8 SUBAGENT 적대검증 PASS(주석 델리미터 61/61·잔여 `*/` hazard 없음·diff 주석 국한). POST-DEPLOY 재배포 자산 최종 확인=deploy-web 직후.
- Files: `src/static/graph/graph.css`, `docs/{TASK,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260714T180314-graph-entry-help.md`.
- Cross-ref: REV/TASK-20260714T184717-graph-help-overlay-fix · 원천 CHG-20260714T180314-graph-entry-help · TEST test-runs.d/20260714T180314-graph-entry-help.md(POST-DEPLOY FIX 섹션) · ANCHOR 0003 무충돌.

## CHG-20260714T190916-graph-help-overlay-postverify (그래프 도움말 팝업 mis-position 수정 POST-DEPLOY 재배포 자산 실증 기록, doc-only)
- Date: 2026-07-14. CHG-20260714T184717-graph-help-overlay-fix(PR #798, main 8d1285d0) 배포 후 **재배포된 자산** 상 최종 확인. 코드 변경 0(문서 전용).
- Changes: `docs/test-runs.d/20260714T180314-graph-entry-help.md` POST-DEPLOY FIX 섹션에 "재배포 자산 최종 확인" append + `docs/TASK.md` fix post-deploy 박스 close.
- 실증: `/healthz` git_commit=8d1285d0. 서빙 graph.css 스탬프 `4335ea1dac52`→`d5f26a416089`(content-hash 갱신)·소스 byte-identical·주석 델리미터 61:61. 배포본 런타임(win-browser eval, 주입 없이): `.amg-help-overlay` cssRules 파싱 복구·`position:absolute`·`display:flex`·`align-items:center`·`z-index:40` · 카드 canvas-wrap 수평 정중앙(dx:0)·줌 컨트롤 미겹침(card_overlaps_zoom:false) · ❓ 버튼 팝업 스크린샷 육안(중앙 모달) · pageerror 0. → 배포본 실증 PASS.
- Files: `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`, `docs/test-runs.d/20260714T180314-graph-entry-help.md`.
- Cross-ref: REV-20260714T190916-graph-help-overlay-postverify · 원천 CHG/REV-20260714T184717-graph-help-overlay-fix · ANCHOR 0003 무충돌.


## CHG-20260715T025509-doc-sync-rn-0715 (TASK-20260715T025509-doc-sync-rn-0715 — 07-14 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: releases 배열 head 에 **date "2026-07-14" 새 블록 prepend**(10항목: work 6·admin 3·common 1)·summary 작성. generated 07-13→07-14. 기존 28 블록 보존(총 29).
- **cache-buster 무변경**: 소스 `?v=dev` placeholder 고정(§13.1 ITEM-09 what#3 — Dockerfile `inject_asset_stamp.py` content-hash 빌드 주입·deploy-web `asset_stamp_verify` 하드게이트). index/admin.html 편집 0. release-notes-data.js 내용 변경만으로 전역 content-hash 변화 → wrapper 재빌드 시 서빙 토큰 자동 갱신(수동 bump 부적용·해시 불변).
- 제외: feature-0020 무중단 배포(내부)·feature-0016 flock/cluster-label(내부 운영)·@@ 시스템변수 과차단(07-13 블록 detail 포괄·중복 회피)·POST-DEPLOY/ROUTEMAP/ANCHOR 기록.
- Verification: `node --check` PASS · vm 구조검증(29 releases·07-14 head 10항목·07-13 보존·스키마·누출0). 사용자향 평이화(내부용어 누출 0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- **landing/배포 소유=cron wrapper 위임**(로컬 commit 만·push/merge/deploy 미수행). META(STATUS·wiki·ARCHITECTURE·SECURITY·meta/REVIEW)는 별도 commit(REV-20260715T025509-META-0036-doc-sync-0715).
## CHG-20260714T181936-perm-category-hier (TASK 20260714T1819-perm-category-hier — 관리 콘솔 권한 체계 카테고리 '접근' 계층 재구성, Critical §12.3 인증/인가)
- Date: 2026-07-14. 사용자 요청("권한 체계 구조적 난잡 — 카테고리별 '접근'(=조회) 최상위 + 하위 종속 + 상위 활성화 시 UI 펼침") — 사용자 승인 A안.
- backend `src/web_context.py`: 신규 카테고리 접근 권한 5종 `console.{account,product,audit,kb,system}.access`(각 카테고리 그룹 배치, desc≤255) · GroupName 재배치(`console.usage.read`/`console.aiops.read`/`conversation.archive.read.any`→audit, `insight.reset`→product — code·enforcement 불변) · admin catchup 5종 + dba `console.audit.access` · `_CONSOLE_CATEGORY_ACCESS_LEAVES` 카테고리→하위 맵 · `_backfill_console_category_access_v1`(1회 멱등, `WebSchemaMigrations` `console-category-access-v1`, 대상 3종 — 접근 무손실) `_ensure_seed_roles` 말미 배선.
- frontend `src/static/admin.js`: `PERMISSION_DEPENDENCIES` 카테고리 계층 전면 재구성(+`system.runtime.*` 종속 신설, `conversation.create`→list.own, `insight.reset`→product.read, 감사 4탭 조회→`console.audit.access`) · `ADMIN_TAB_CATEGORY_ACCESS` 신설 + `canSeeTab`=카테고리 접근(AND)&&탭 권한(OR) · settings 탭 게이트 `system.runtime.read/write` 보강 · 그룹 순서 nav 정합 + kb 라벨 "지식베이스".
- frontend `src/static/app.js`: 그룹 라벨(quota/datasource/kb)·순서 + `PERMISSION_GROUP_OVERRIDES`(재배치 코드 명시 매핑) + 접근 5종 라벨 + manage section groups 정합.
- tests: `test_permission_dependency_map.py`(M3/M4 갱신·M5 신설·V2/V3/V4·v6/v7·t3/t5/t6) · `test_llm_usage_quota.py` f2 · `test_insight_reset.py` group · `verify_admin_tab_gating.mjs`(카테고리 AND 케이스 2b/4b 신설 + release-notes 상시 노출로 stale 하던 시스템 라벨 기대 2건 정정 — main baseline 부터 FAIL 이던 건).
- docs: `docs/SECURITY.md` §22 신설 · `docs/CONVENTIONS.md` §10.6 정합 · unit TASK/REPORT/REVIEW/DECISIONS.
- 비변경: 엔드포인트 `require_permission` 0건(ROUTEMAP 무영향) · 권한 code/스키마/마이그 0 · `_METADATA_MANUAL_IMPLIES` 불변 · 작업 화면 동작.
- Verification: 권한 타깃 50 PASS · feature-0003 스위트 785/0(호스트, baseline 제외) · jsdom 탭 게이팅 47/0 · 컨테이너 make test + 배포 후 backfill 마커·무손실 실증은 TASK 잔여 항목.
- Cross-ref: REV-20260714T181936-perm-category-hier · ADR-20260714T181936-perm-category-hier · SECURITY §22.

## CHG-20260715T102912-graph-help-text-responsive (그래프 도움말 팝업 텍스트 줄바꿈 + 반응형 크기, Minor §12.3 frontend-only CSS)
- Date: 2026-07-15. 사용자 피드백 2건(graph-entry-help 배포본): ① 설명 텍스트가 어절 중간에서 줄바꿈("…탐색하세"/"요.") ② 팝업이 고정 크기가 아닌 브라우저 크기 반응형이 되도록. `/_template:entry`(resume 후속 세션).
- Changes:
  - `src/static/graph/graph.css` `.amg-help-card`: (텍스트) `word-break: keep-all; overflow-wrap: anywhere;` — CJK 기본(normal)이 글자 사이 아무 데서나 끊어 음절 orphan 발생 → keep-all 로 어절(공백) 단위 줄바꿈, overflow-wrap:anywhere 는 폭 초과 토큰 예외 처리. (반응형) `width: min(460px, 100%)` → `width: min(clamp(320px, 90%, 520px), 100%)` — 고정 상한 460px 제거, 캔버스(=브라우저) 폭 90% 를 320~520px 사이 유동, 좁은 화면 100% 바운드. 세로 max-height:100%+overflow-y:auto 유지.
- 무회귀: CSS 선언 2 + 주석만(선택자/미디어쿼리/다른 규칙 0). 백엔드/RBAC/스키마/JS/HTML 0. `/*`:`*/` 63:63·중괄호 215:215 균형(주석 hazard 없음 — 20260714T184717-fix 정신 준수). cache-buster `?v=dev` placeholder 수기편집 없음.
- 검증: 라이브 win-browser eval — keep-all 어절 줄바꿈(스크린샷) · 반응형 다중 폭 실측(300→268·360→320·617→520·1100→520, 오버플로 0). POST-DEPLOY 재배포 자산 확인=deploy-web 직후.
- Files: `src/static/graph/graph.css`, `docs/{TASK,MODIFY,REVIEW,FUNCTION,REPORT}.md`, `docs/test-runs.d/20260715T102912-graph-help-text-responsive.md`.
- Cross-ref: REV/TASK-20260715T102912-graph-help-text-responsive · 원천 CHG-20260714T180314-graph-entry-help(팝업 신설)·CHG-20260714T184717-graph-help-overlay-fix(위치 수정) · ANCHOR 0003 무충돌.

## CHG-20260715T103948-graph-help-responsive-postverify (도움말 팝업 줄바꿈+반응형 POST-DEPLOY 재배포 자산 실증 기록, doc-only)
- Date: 2026-07-15. CHG-20260715T102912-graph-help-text-responsive(PR #804, main 6af16762) 배포 후 재배포 자산 상 최종 확인. 코드 변경 0(문서 전용).
- Changes: `docs/test-runs.d/20260715T102912-graph-help-text-responsive.md` 재배포 자산 확인 append + `docs/TASK.md` post-deploy 박스 close.
- 실증: `/healthz` git_commit=6af16762. 서빙 graph.css 스탬프 `d5f26a416089`→`92be1efb1249`(갱신)·`word-break: keep-all`+`clamp(320px, 90%, 520px)` 반영·주석 63:63. 배포본 런타임(win-browser eval, 주입 없이): `.amg-help-card` word-break=keep-all(설명 상속)·overflow-wrap=anywhere · 반응형 다중 폭 300→268·360→320·617→520·1100→520(오버플로 0) · 스크린샷 육안 · pageerror 0. → PASS.
- Files: `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`, `docs/test-runs.d/20260715T102912-graph-help-text-responsive.md`.
- Cross-ref: REV-20260715T103948-graph-help-responsive-postverify · 원천 CHG/REV-20260715T102912-graph-help-text-responsive · ANCHOR 0003 무충돌.
## CHG-20260715T103406-perm-atomic-split (TASK 20260715T1034-perm-atomic-split — 권한 최소 단위 원자화 + 레거시 묶음 숨김, Critical §12.3 인증/인가)
- Date: 2026-07-15. perm-category-hier 후속(사용자: "[등록/수정/삭제]·[등록/거부] 통합 잔존") — 사용자 결정: 전체 분리+묶음 숨김 / 검수 단일 유지·원본 사전 하위 종속.
- backend `src/web_context.py`: 원자 23종 신설(사전 4종×read/create/update/delete + product.{create,update,delete} + datasource.{create,update,delete,test}) · `_PERMISSION_BUNDLE_IMPLIES` transitive 함의(개별 DENY 우선) · `LEGACY_BUNDLE_PERMISSIONS` 7종 · admin catchup 23종 · `_backfill_atomic_perm_split_v1`(1회 멱등 `atomic-perm-split-v1`, category-access-v1 선행 호출) · leaves 맵 원자화.
- backend 라우터: `admin_metadata.py` 22 핸들러 액션별 전환+`_METADATA_SUBTAB_PERM_SERVER`=read+`_METADATA_SUGGEST_PERM`(update) 분리 · `admin_products.py` create/update/delete(+구성/규칙/AI제안/프롬프트=update) · `admin_datasources.py` `_ds_write_common(action_perm)`+test=`datasource.test` · `_prompt_context.py` update.
- frontend `admin.js`: DEPS 원자 트리(검수→원본 read 하위)·legacy grid 필터·서브탭 C/U/D 맵+버튼 게이팅·ds/제품 bulk·상세 액션 분리·metadata 탭 게이트 read+curate. `app.js`: legacy 숨김·ds-conn-test `datasource.test` 게이트·라벨 23종.
- tests: perm dict 원자 보강 10파일 · dependency-map 재계약(M3/V2/t5/t6·legacy 제외) · perm_split R7/R8=read + R9(transitive·DENY)·R10(3자 parity) 신설.
- docs: SECURITY §22.4 · CONVENTIONS §10.6 · ROUTEMAP 재생성(202 routes, 권한 열 30행 갱신, --check 0).
- 비변경: 권한 code 삭제 0(묶음은 숨김만·함의 유지) · 스키마/마이그 0 · route 경로/메서드 0 · `_METADATA_MANUAL_IMPLIES` 상수 보존.
- Verification: 785/0(호스트) · jsdom 47/0 · 컨테이너 make test·배포 후 실증은 TASK 잔여.
- Cross-ref: REV-20260715T103406-perm-atomic-split · ADR-20260715T103406-perm-atomic-split · SECURITY §22.4 · 원천 CHG-20260714T181936.

## CHG-20260715T110000-attach-new-label-symmetry (staged-flush 첨부 new_attachment_ids 라벨 대칭 — deferred ②-frontend, Minor §12.3)
- Date: 2026-07-15. 계기: 첨부-답정합 실데이터 감사 deferred ②-frontend(②-backend=CHG-20260715T060000 별도 완료). ② 서브에이전트가 share-window 는 라이브-ask 첨부 경로 밖(비보안)임을 확인 — friction(1) stale-window 의 프론트 축.
- Reason(RC): 신규 대화 send 시 staged 첨부(status="staged")를 `_flushStagedAttachmentsToCid` 가 업로드해 `uploadedIds` 반환 → `attachment_ids` 에만 union(app.js:9307), `new_attachment_ids`(9264 스냅샷은 flush 전이라 `status==="ready"` 필터로 staged 제외)엔 누락. 비대칭 → 방금 올린 파일이 프롬프트에서 ◆세션(이전 세션)으로 오라벨 → assistant 가 "새 파일이 업로드되지 않았거나 반영 안 됨"이라 오판(관측 대화 20260615061233).
- 사용자 승인: **PLAN-APPROVED**(사용자 "남은 deferred 축 완수까지 진행", 2026-07-15). Minor(라벨-only 프론트 union; 접근/인가 불변 → Critical 아님).
- Changes(feature-0003):
  - `src/static/app.js` — lazy-create + staged 블록에서 `uploadedIds` 를 `askBody.new_attachment_ids` 에도 union(`new Set(...).filter(n>0)`, attachment_ids union 대칭). 블록 밖(기존 대화·무-staged)은 무영향.
- Recurrence sealing: attachment_ids/new_attachment_ids union 대칭으로 staged-flush 신규 첨부의 ★신규 라벨 보장 → "새 파일 반영 안 됨" 오판 경로 봉인. **보안 회귀 0**: new_attachment_ids 는 서버측 라벨+version-diff 게이트 전용(접근 스코프 아님), uploadedIds 는 서버-확인 id, v1 staged 라 version-diff 미트리거.
- 검증: `node --check` PASS. de-risk(로직 대칭 분석 + 적대 패널 + 서버측 new_attachment_ids 소비 추적). 라이브 PB-0008(신규 대화 staged 첨부 ★신규 인지)은 정적자산 baked → 배포 후 실측(TEST.md §3 DEFERRED). §18.8 → REV-20260715T110000-attach-new-label-symmetry.
- Cross-ref: CHG-20260715T060000-attach-inline-honesty(②-backend, feature-0002) · ② 서브에이전트 진단(share-window 비관여) · ANCHOR §1~§3 무충돌.
## CHG-20260715T105337-enum-review-bundle (ENUM 코드사전 검토 큐: 구조 묶음 단위 승인 체크리스트 + 일괄 등록, Major §12.3 additive·비파괴)
- Date: 2026-07-15. 사용자 요청: `관리 콘솔 > 지식베이스 > 메타데이터 > ENUM 코드사전` 검토 큐에서 ENUM값을 구조 묶음 단위로 구성 + 승인 체크리스트(전체 승인/일부 해제) 후 등록. `/_template:entry` arg-given dispatch. 설계 근거: `enum_feedback` UNIQUE `(scope,schema,table,column,code)` → 한 컬럼 = 한 구조 묶음.
- Changes:
  - `unit/feature-0002-agent-core/src/modules/kb_glossary.py`: 신규 `bulk_promote_enum_feedback(conn, feedback_ids, *, approved_by=None)` — 기존 `promote_enum_feedback` 를 단일 트랜잭션 loop, `[{"feedback_id","enum_id"}]` 반환(없음/이미 처리 → enum_id=None skip).
  - `unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py`: 신규 `POST /api/admin/metadata/enum-feedback/bulk-promote`(RBAC `kb.enum.curate`) — body `{"feedback_ids":[int,...]}` 정규화(int·양수·dedup·≤`_ENUM_BULK_PROMOTE_MAX`=200) → `bulk_promote_enum_feedback` → commit/rollback + audit `enum.feedback.bulk_promote`(requested/promoted_count/skipped_ids). 모듈 상수 `_ENUM_BULK_PROMOTE_MAX` 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `renderFeedbackQueue` enum 경로 → `_metaRenderEnumBundles`(묶음 그룹핑) + `_metaBuildEnumBundle`(전체 승인 마스터+개별 체크박스+힌트+등록 버튼) + `_enumBundleKey`/`_enumBundleRegister`(bulk-promote). enum note 텍스트 갱신. glossary/sample 경로 불변.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-meta-bundle*` 카드 스타일(헤더/체크리스트/푸터).
  - `docs/ROUTEMAP.md`: 재생성(203 routes, 신규 route 반영).
- 무회귀: 개별 promote/reject·glossary/sample 큐·RBAC 정의·스키마/마이그레이션·인증 0. 미선택(해제)은 pending 유지(비파괴 — 거부 아님). cache-buster `?v=dev` placeholder 수기편집 없음.
- 검증: `node --check`(module) admin.js PASS · agent 컨테이너 targeted pytest 28/0(core 2 + web 6 신규 포함) · `gen-routemap --check` up-to-date. POST-DEPLOY PB-0008 라이브(묶음 카드·토글·등록) 예정.
- Files: `unit/feature-0002-agent-core/src/modules/kb_glossary.py`, `unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py`, `unit/feature-0003-agent-web-ui/src/static/{admin.js,styles.css}`, `unit/feature-0002-agent-core/tests/test_kb_enum_feedback.py`, `unit/feature-0003-agent-web-ui/tests/test_metadata_enum_feedback.py`, `docs/ROUTEMAP.md`, `docs/{TASK,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260715T105337-enum-review-bundle.md`.
- Cross-ref: REV/TASK-20260715T105337-enum-review-bundle · REQ-20260715T105337-enum-review-bundle · 원천 enum_feedback(alembic 0039)·admin_metadata enum-feedback 큐 · ANCHOR 0003 무충돌.


## CHG-20260715T113208-enum-bundle-flex-fix (ENUM 검토 큐 묶음 카드 flex 압축 붕괴 수정, Minor §12.3 CSS 전용)
- Date: 2026-07-15. enum-review-bundle 배포 후 PB-0008 적발 — 묶음 카드 12px sliver 로 붕괴.
- Changes: `unit/feature-0003-agent-web-ui/src/static/styles.css` `.admin-meta-bundle` 에 `flex-shrink: 0` 추가. `#metadataList`(overflow-y:auto flex-column, 높이 제약)에서 카드가 flex 압축 + card `overflow:hidden` 클리핑되던 것을 자연 높이 유지로 해소.
- 무회귀: JS/HTML/백엔드/RBAC/엔드포인트/스키마 0. CSS 선언 1 + 주석. cache-buster `?v=dev` placeholder 수기편집 없음.
- 검증: 라이브 win-browser 주입 검증(카드 12px→166px). POST-DEPLOY PB-0008 재검증 예정.
- Files: `unit/feature-0003-agent-web-ui/src/static/styles.css`, `docs/{TASK,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260715T113208-enum-bundle-flex-fix.md`.
- Cross-ref: 원천 CHG-20260715T105337-enum-review-bundle · ANCHOR 0003 무충돌.

## CHG-20260715T120000-enum-review-bundle-postverify (ENUM 검토 큐 묶음 승인 체크리스트 + flex-fix POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-15. CHG-20260715T105337-enum-review-bundle(PR #811, f6cb0b14) + CHG-20260715T113208-enum-bundle-flex-fix(PR #817, a3c69103) 배포 후 라이브 실증. 코드 변경 0(문서 전용).
- Changes: `docs/test-runs.d/20260715T105337-enum-review-bundle.md` + `docs/test-runs.d/20260715T113208-enum-bundle-flex-fix.md` POST-DEPLOY append + `docs/TASK.md` 두 cycle post-deploy 박스 close.
- 실증(win-browser eval, bootstrap_admin, 주입 없이): (bundle) `/admin` ENUM 검토 큐 12후보 → 8묶음 그룹핑·전체 승인 마스터·일부 해제 indeterminate/힌트·등록 count/disabled 로직 PASS. (flex-fix) 재배포 자산(a3c69103·styles.css 62c4b695387d) 카드 높이 [166…298] 자연 높이·flex-shrink=0·목록 스크롤·sliver 해소·pageError 0.
- Files: `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`, `docs/test-runs.d/{20260715T105337-enum-review-bundle,20260715T113208-enum-bundle-flex-fix}.md`.
- Cross-ref: 원천 CHG-20260715T105337-enum-review-bundle · CHG-20260715T113208-enum-bundle-flex-fix · ANCHOR 0003 무충돌.

## CHG-20260715T135725-graph-ctxmenu-content-category (TASK-20260715T135725-graph-ctxmenu-content-category — 그래프 우클릭 3대상 정합: 컨텐츠 카테고리 전용 메뉴 신설 + band-wins 철회, Major §12.3 frontend-only)
- Date: 2026-07-15. 사용자 정정("'제품 카테고리 밴드'를 '내부 노드를 컨텐츠 단위로 묶은 클러스터=컨텐츠 카테고리'로 착각") → band-priority(CHG-20260715T114608) 전제 무효. 그래프 우클릭 3층 정합: 제품 카테고리 밴드=카테고리 / 스키마 클러스터=스키마 / 컨텐츠 카테고리(sim-group)=신설 전용 메뉴.
- `static/graph/graph-renderer-pixi.js` (band-wins 철회):
  - `PixiGraphAdapter._pickContext(mx,my)` 제거. `up()` 우클릭(button===2)은 다시 `d.hit`(=`_pick`, WYSIWYG)로 emit — 좌클릭·드래그와 동일 hit. 밴드 위 스키마 클러스터 우클릭 → 스키마 메뉴(카테고리 승격 제거).
- `static/graph/graph-ctxmenu.js`:
  - 신규 `_metaGraphCtxForContentCategory(gk,x,y)` + export. gk 형식 "<schemaKey>\u0001<token>". 헤더 배지 '컨텐츠 카테고리'(#8a3f7a)+label·테이블수 / 📋 소속 스키마 상세(`_metaGraphShowClusterDetailById`) / 접기·펼치기 (묶음)(`groupCollapsed` 토글+`_metaG6Apply(false)`) / 묶음명 복사. groupInfo miss 시 token 폴백(안전).
- `static/graph/graph-core.js`:
  - `node:contextmenu` GB/GH/GX 분기: `_metaGraphCtxForSchema(gk.slice(0,sep))` → `_metaGraphCtxForContentCategory(gk)`. import 추가.
  - `_metaGraph.groupInfo` 신설 · `_metaG6Build` reset + sim-group emission 전량 적재({label,n,schema}, 접힘/펼침 무관).
- `static/graph/graph-state.js`: `groupInfo: new Map()` 초기화(groupMembers 패턴 정합).
- `tests/headless/test_pixi_adapter.js`: T22 를 band-wins → 컨텐츠 카테고리 회귀로 교체(GB/GH 자기노드·밴드 흡수 안 함 · 밴드 위 스키마카드→SC · `_pickContext` undefined). ALL PASS 66/0.
- 비변경: 좌클릭(GB/GH 상세, GX 접기)·드래그(sim-group 리지드 이동)·제품 카테고리 밴드/스키마 클러스터 메뉴·dispatch 타 분기·시각 z·백엔드/RBAC/스키마 0.
- 검증: `node --check`(4 파일) PASS · 헤드리스 66/0 · §18.8 적대 패널. POST-DEPLOY PB-0008 라이브 잔여(visual_verification_scope: always).
- Cross-ref: TASK/REVIEW-20260715T135725-graph-ctxmenu-content-category · test-runs.d/20260715T135725-graph-ctxmenu-content-category.md · **철회 대상 CHG-20260715T114608-graph-ctxmenu-band-priority** · 유지 선행 CHG-20260715T102901-graph-ctxmenu-hittest(WYSIWYG _pick 3-tier) · ANCHOR 0003 무충돌.

## CHG-20260715T140000-graph-ctxmenu-content-category-postverify (그래프 우클릭 3대상 정합 POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-15. CHG-20260715T135725-graph-ctxmenu-content-category(PR #820, main 66722981) 배포 후 라이브 실증. 코드 변경 0(문서 전용).
- 실증(win-browser Chrome 150, 배포 66722981): ① sim-group "방송 계정·3"(mysql-kr-an2-player dbGame) 우클릭 → **컨텐츠 카테고리** 메뉴 / ② 밴드 위 스키마 클러스터(dbAuth) → **스키마**(band-wins 철회 복원) / ③ 제품 카테고리 밴드 → **카테고리** / 개별 테이블 → **테이블**(흡수 안 됨). 서빙 자산 baked(`_pickContext` 메서드 0·우클릭=`_pick`·ContentCategory 라우팅·groupInfo)+브라우저 in-page fetch(stale 아님) 확인.
- Changes: `docs/test-runs.d/20260715T135725-graph-ctxmenu-content-category.md` POST-DEPLOY 섹션 DEFERRED→PASS · `docs/TASK.md` 체크리스트 close · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260715T135725-graph-ctxmenu-content-category · ANCHOR 0003 무충돌.

## CHG-20260715T082345-picker-case-preserve (제품 접근DB write-path 서버-실제-case 정규화 — B ingestion, cross-ref feature-0002 FR-schema-name-case-drift)
- Date: 2026-07-15. 계기: `/_dqa:conversation_audit` "테이블 구조 정합성 검토" 마찰의 ingestion 근본 — 스키마 whitelist 가 소문자로 저장돼 case-sensitive MySQL 에서 assistant 조회 0행(정본 근본·봉인 = feature-0002 CHG-20260715T082345-schema-name-case-drift).
- Reason(RC, §18.8 적대 패널 재진단): 초기 후보(admin_console picker `.lower()` 제거)는 **실효 없음**으로 기각 — (a) 그 picker(`/api/admin/databases/available`)는 미바인딩 default 폴백 전용이고 실 바인딩 picker 는 `list_server_databases_classified`(이미 실제 case), (b) **admin.js(11277/11366)가 MySQL 스키마명을 저장 직전 `.toLowerCase()`** 해 서버-측 picker case 보존을 무효화. 실 소문자화는 프론트 + write path 무정규화의 합작.
- Changes(feature-0003): `src/routers/admin_products.py` `admin_update_product_databases` — 저장 직전 `cleaned` 스키마명을 datasource 서버 **실제 case**(`shared.db.list_server_databases`, SSRF-pin 선행)로 정규화. **엔드포인트/프론트 case 무관 backend chokepoint** — admin.js 소문자화·수기 소문자 입력 모두 write 시점에 서버 실제값으로 고정. degrade-safe(datasource 미해소·SSRF 차단·연결 실패·모호[대소문자만 다른 동명 복수] → 입력 case 유지·저장 차단 안 함). MySQL only(MSSQL catalog case-insensitive). admin_console picker 변경은 **원복**(wrong-endpoint·무효).
- 검증: 신규 `tests/test_product_databases_case_normalize.py` 2 PASS(소문자 입력→서버 실제 case 저장·degrade-safe). feature-0003 전체 회귀 무영향(2113 passed 통합).
- 한계(§정직, deferred): admin.js 소문자화 자체는 미수정(프론트·visual verification 필요·write-path 정규화가 상쇄) · datasource-scoped picker 실제 case 표시(후속) · 기존 저장 소문자 행 백필은 admin 별도(A 런타임 canonicalize + 재저장 시 write-path 정규화가 점진 seal).
- Cross-ref: **primary = feature-0002 CHG-20260715T082345-schema-name-case-drift**(런타임 resolution seal·verify 정본) · REV-20260715T082345-schema-name-case-drift(패널) · FRICTION_LEDGER FR-schema-name-case-drift.

## CHG-20260715T181939-graph-edge-follow-drag (그래프 뷰 노드/제품 카테고리 드래그 시 관계선 미추종 수정 — PixiJS incident 엣지 증분 재그림)
- Date: 2026-07-15. 계기: 사용자 보고 "그래프 뷰에서 좌클릭 드래그로 제품 카테고리를 옮길 때 관계선이 옮기기 전 위치에 그대로 출력(줌 아웃으로만 갱신)". 작업 중 사용자 정정: "cross-category 엣지(다른 제품 카테고리로 가는 연결선)의 구조 갱신이 핵심".
- 근본원인: PixiJS 렌더러에서 엣지는 절대 model 좌표(a,b)를 Graphics path 에 bake 한 **world 직속 독립 오브젝트**(`_drawEdge`)라 노드 Container 이동으로 따라오지 않는다. 드래그 경로 `_moveElement`/`translateElementTo` 는 노드 style/position 만 갱신 + `_render()`(단순 repaint)만 호출 → incident 엣지 옛 좌표 유지. full `draw()`(줌 밴드 LOD rebuild)만 `edgeSig(e,a,b)` 끝점 변경을 감지해 recreate → "줌 아웃해야 갱신".
- Changes(feature-0003, frontend-only 1 파일 + 테스트):
  - `src/static/graph/graph-renderer-pixi.js`: 신규 `_refreshIncidentEdges(movedIds)` — `this._built.edges` 중 `source||target ∈ movedIds` 인 엣지만 old destroy→removeChild→`_drawEdge(e,a,b)`→addChild→`_objs.set`, `_objSig.set(eid, edgeSig(e,a,b))`(다음 full draw 재사용). 좌표는 `getElementPosition`(draw() 의 pos 계산과 동형). `_moveElement` 노드분기(`[id]`)·combo분기(이동 자식 id 수집)·`translateElementTo`(이동 노드 id 수집) 에서 `_render()` 직전 호출.
  - `tests/headless/test_pixi_adapter.js`: T23 신규 7종(prototype call + stub world/_drawEdge — incident 선택 e1(내부)·e2(cross-category) 재그림·e3 skip / cross-category 이동끝점 새좌표·미이동끝점 옛좌표 / _objs·world 교체 / _objSig 갱신 / 빈·null no-op). ALL PASS 73/0.
- cross-category 보장: OR 판정 — 한끝(이동 카테고리 구성원)만 movedIds 에 있어도 재그림, 이동 끝점 새 좌표 + 미이동 끝점 현재 좌표로 연결선 구조 갱신(사용자 정정 케이스). 카테고리 드래그는 `graph-core._metaNodeDrag` 가 전 구성원을 `translateElementTo` 로 이동시키므로 본 chokepoint 가 커버.
- 비변경: 팬/줌·상태·미니맵·hover-fx·우클릭 메뉴·클릭·백엔드/RBAC/스키마/마이그레이션 0. full `draw()` diff 경로 불변.
- 한계(정직, deferred): 허브 노드(수천 incident 엣지) per-frame 재그림 비용 — full draw() 보다 저렴하고 정확성 필수 최소치, rAF 스로틀은 후속(§76 계열).
- 검증: `node --check` PASS · 헤드리스 73/0 · §18.8 적대 리뷰 · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260715T1819 · REV/TEST-20260715T181939-graph-edge-follow-drag · test-runs.d/20260715T1819-graph-edge-follow-drag.md · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## CHG-20260715T190000-graph-edge-follow-drag-postverify (그래프 관계선 추종 수정 POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-15. CHG-20260715T181939-graph-edge-follow-drag(PR #824, main 0f26cec1) 배포 후 라이브 실증. 코드 변경 0(문서 전용).
- 실증(win-browser 실 Windows Chrome 150, relay, 배포 0f26cec1): PixiJS 그래프 루트 뷰(제품 카테고리 14 + 데이터소스 18 + cross-category 관계선)에서 제품 카테고리 "건즈-개발·1"을 합성 PointerEvent(button0)로 드래그 → **pointerup 전·줌 없이** mid-drag 스크린샷에서 관계선이 이동한 새 위치를 그대로 추종(옛 위치 잔상 0). dragend 후에도 정합(ADR-004 자유배치 영속). pageerror 0. 서빙 자산 `_refreshIncidentEdges` grep=4(baked). evidence: graph_root·graph_middrag·graph_after_reset.
- Changes: `docs/test-runs.d/20260715T1819-graph-edge-follow-drag.md` Run 3 DEFERRED→PASS · `docs/TASK.md` POST-DEPLOY 체크박스 close · `docs/REPORT.md` 완결 갱신 · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260715T181939-graph-edge-follow-drag · ANCHOR 0003 무충돌.

## CHG-20260715T211911-graph-cluster-detail-routines (스키마 클러스터 상세 패널: 함수·프로시저만 있는 컨텐츠 카테고리 누락 수정, Minor §12.3)
- Date: 2026-07-15. feature-0003 web/UI 프론트 단독(1파일). 그래프 도메인 정본 feature-0016. `/_template:entry` arg-given dispatch.
- 사용자 보고: 상세 패널의 컨텐츠 카테고리가 테이블만 집계 → 함수·프로시저만 있는 컨텐츠 카테고리(예: "상점 아이템 명칭")가 목록 누락. 해당 항목도 조회되게 구성.
- 근본원인: 캔버스 build(`graph-core.js` L64~L78)는 Table+Routine 을 모두 `g.tables` 에 넣어 `_metaSimGroups` 로 함께 sim-group(컨텐츠 카테고리)화하나, 스키마 클러스터 상세 패널 진입점(`_metaGraphShowClusterDetailById`·`_metaGraphShowClusterDetailLocal`)과 렌더(`_metaGraphRenderClusterDetail`)는 `label === "Table"` 만 집계 → Routine-only 컨텐츠 카테고리 누락 + 캔버스와 불일치.
- Changes:
  - `src/static/graph/graph-ctxmenu.js`:
    - `_metaGraphShowClusterDetailLocal`: `label === "Routine" && _metaCatParent(n.key,n.fqn)===comboId` 수집·정렬 → `routines` 인자로 렌더 전달.
    - `_metaGraphShowClusterDetailById`: 모델에서 routines 수집(API 응답 형태 무관 — 패널은 화면 내 스키마라 모델 보장) → 렌더 전달 + status 라인 함수·프로시저 개수 노출.
    - `_metaGraphRenderClusterDetail(name,fqn,tables,childTables,childCols,totalOverride,truncated,comboId,routines)`: `members=tables.concat(routines)` 로 `_metaSimGroups`/렌더. Routine 행 = ƒ/⚙ 보라 칩(`_META_GRAPH_COLOR.Routine`) 접두사, 클릭 → `_metaGraphShowDetail`(API 조회, routine 키 동작). 설명/섹션 제목/그룹 aria-label 병합집합 반영. 테이블 개수·cap 절단(nTables/truncNote)은 테이블 기준 유지.
- 정합성: 패널 sim-group 입력을 캔버스와 동일 Table+Routine 병합집합으로 맞춤 → 상세 패널 컨텐츠 카테고리가 캔버스와 일치. `_metaSchemaComboOf(Routine)`==`_metaCatParent(...)` 동일 predicate 로 membership 정합.
- 비변경: 제품 카테고리 패널(스키마 목록)·캔버스 build·우클릭 메뉴·드래그·상태·백엔드/RBAC/스키마/엔드포인트 0. Table-only 스키마 회귀 0(문구만 확장). cache-buster `?v=dev` placeholder 수기편집 없음.
- 검증: `node --check`(module) PASS · §18.8 적대 리뷰 · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260715T2119 · REV/TEST-20260715T211911-graph-cluster-detail-routines · test-runs.d/20260715T2119-graph-cluster-detail-routines.md · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## CHG-20260715T215241-graph-cluster-detail-cap (스키마 클러스터 상세: 목록 행 캡이 함수·프로시저 컨텐츠 카테고리를 통째 숨기던 문제 수정, Minor §12.3)
- Date: 2026-07-15. feature-0003 web/UI 프론트 단독(1파일). cluster-detail-routines(CHG-20260715T211911) POST-DEPLOY PB-0008 후속. 그래프 도메인 정본 feature-0016.
- 트리거: cluster-detail-routines 배포 후 라이브 검증에서, gunzgame 클러스터 상세(409항목=테이블 115+함수·프로시저 294)의 집계·개수는 정확하나 목록에 렌더된 컨텐츠 카테고리가 앞쪽 테이블 be: 클러스터 10개(80행)뿐 — 함수·프로시저 컨텐츠 카테고리가 한 개도 안 보임을 적발.
- 근본원인: `_metaGraphRenderClusterDetail` sim-group 렌더가 전역 80행 캡 도달 시 이후 그룹 통째 skip(`if (emitted >= 80) return`). sim-group 순서가 be: 의미 클러스터(테이블) 우선이라 대형 스키마에서 앞쪽 테이블 그룹이 80행 소진 → 뒤쪽 routine 컨텐츠 카테고리(헤딩 포함) 전체 렌더 누락. 집계 포함(cluster-detail-routines)만으로는 시각적 조회 불가.
- Changes:
  - `src/static/graph/graph-ctxmenu.js` `_metaGraphRenderClusterDetail` 캡 규약 개정: (1) `if (emitted >= 80) return` 제거 → **모든 컨텐츠 카테고리 헤딩 항상 방출**(카테고리 가시·조회 가능). (2) 멤버 행 캡을 그룹당 PER_GROUP=25 + 전역 ROW_CAP=500 로 재구성(`shown = min(sg.n, 25, max(0, 500-emitted))`) — 한 그룹 예산 독식 방지 + 패널 길이 바운드(aside overflow-y:auto). 절단은 그룹별 `(shown/n)`. (3) flat 폴백 `slice(0,80)`→`slice(0,500)`.
- 회귀: 소형 스키마(≤80·그룹 ≤25) 동일. 그룹 멤버 >25 인 그룹만 25 표시 + `(25/n)`(예 gunzgame "캐릭터 정보 및 랭킹" 32→25) — routine 카테고리 전면 가시화 위한 수용 트레이드오프.
- 비변경: cluster-detail-routines 집계/membership/hiddenKinds/렌더 분기·백엔드/RBAC/스키마 0. cache-buster `?v=dev` placeholder 수기편집 없음.
- 검증: `node --check` PASS · §18.8 [SKIPPED] 적대 자가검토(display-cap 상수·헤딩 방출, 경계·주입·RBAC 무관) · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260715T2152 · REV/TEST-20260715T215241-graph-cluster-detail-cap · test-runs.d/20260715T2152-graph-cluster-detail-cap.md · 선행 CHG-20260715T211911-graph-cluster-detail-routines · ANCHOR 0003 무충돌.

## CHG-20260715T220941-graph-cluster-detail-postverify (그래프 클러스터 상세 함수·프로시저 컨텐츠 카테고리 수정 POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-15. cluster-detail-routines(CHG-20260715T211911, PR #827 main 1b370dfd) + cluster-detail-cap(CHG-20260715T215241, PR #828 main cdee785e) 배포 후 라이브 실증. 코드 변경 0(문서 전용).
- 실증(win-browser 실 Windows Chrome 150 relay, 배포 cdee785e, 로그인 세션): 그래프 뷰 > mysql-gz-dev > gunzgame 스키마 카드 클릭 → 상세 패널에서 (1) 컨텐츠 카테고리 그룹 **72개** 렌더(cap 수정 전 10개), 함수·프로시저-only 그룹 **51개**(수정 전 0개 — "계정 조회" 24 routine·"캐릭터 인벤토리" 25·"아이템 구매" 15·"아이템 정보" 13·"재화 변환" 5·"스팀 캐시 관리" 3·"로그인 보상" 2 등), (2) `⚙ Game_AllItemGet`(gunzgame.Game_AllItemGet()) 클릭 → "ROUTINE / ⚙ 프로시저 / 이웃 2개" 노드 상세 조회, (3) 섹션 "테이블·함수·프로시저 (409)"·설명 "테이블 115개 · 함수·프로시저 294개", (4) 캔버스 sim-group 과 패널 컨텐츠 카테고리 일치, (5) pageerror 0. 서빙 자산 baked(`ROW_CAP = 500` grep=1 web-a/web-b). evidence: gz_routine_groups.png.
- Changes: `docs/test-runs.d/20260715T2119-graph-cluster-detail-routines.md` Run 3 DEFERRED→PASS(집계) · `docs/test-runs.d/20260715T2152-graph-cluster-detail-cap.md` Run 4 DEFERRED→PASS(라이브) · `docs/TASK.md` 두 cycle POST-DEPLOY 체크박스 close · `docs/REPORT.md` 완결 갱신 · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260715T211911-graph-cluster-detail-routines · CHG-20260715T215241-graph-cluster-detail-cap · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## CHG-20260715T223744-graph-cluster-detail-fulllist (스키마 클러스터 상세: 컨텐츠 카테고리 목록 전체 출력 + 행 상호작용 이벤트 위임, Minor §12.3)
- Date: 2026-07-15. feature-0003 web/UI 프론트 단독(1파일). cluster-detail-cap(CHG-20260715T215241) 후속. 그래프 도메인 정본 feature-0016.
- 사용자 보고: 컨텐츠 카테고리 일부만 집계 — `(3/5)`·`(0/N)`. 원인·전체 출력 가능 여부 문의.
- 근본원인: 직전 cluster-detail-cap 의 전역 상한 ROW_CAP=500 + 그룹당 25. 멤버 총합 500 초과 스키마에서 500행 소진 후 그룹 헤딩+0행/경계 그룹 부분 표시.
- Changes:
  - `src/static/graph/graph-ctxmenu.js` `_metaGraphRenderClusterDetail`:
    - 캡 사실상 해제: 그룹당 캡 제거, 전역 안전가드 ROW_CAP 500→5000. `shown = min(sg.tables.length, max(0, 5000-emitted))` → 전체 멤버 렌더. flat 폴백 500→5000. 헤딩 항상 방출·`(shown/n)` 유지.
    - 행 클릭/hover 바인딩을 per-row(`_metaBindHoverPan` 4리스너 + 클릭 1) → 컨테이너 `ul.amgr-cluster-tables` 이벤트 위임(리스너 O(1)). ul 매 렌더 재생성이라 누적 없음. mouseover/out·focusin/out(버블)+`_hoverKey`+`relatedTarget` 검사로 원본 hover 의미 보존. 클릭 `closest(".amgr-ct-row[data-node-key]")`.
- 비변경: 집계/membership/hiddenKinds/sim-group/헤딩/XSS·백엔드/RBAC/스키마 0. cache-buster `?v=dev` placeholder 수기편집 없음.
- 검증: `node --check` PASS · §18.8 적대 리뷰(위임 누적·hover 의미·클릭 동등성) · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260715T2237 · REV/TEST-20260715T223744-graph-cluster-detail-fulllist · test-runs.d/20260715T2237-graph-cluster-detail-fulllist.md · 선행 CHG-20260715T215241-graph-cluster-detail-cap · ANCHOR 0003 무충돌.
## CHG-20260715T231304-graph-cluster-detail-fulllist-postverify (컨텐츠 카테고리 전체 출력 + 이벤트 위임 POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-15. cluster-detail-fulllist(CHG-20260715T223744, PR #830 main 41cf76c5) 배포 후 win-browser PB-0008 라이브 실증. 코드 변경 0(문서 전용).
- 실증(실 Windows Chrome 150 relay, 배포 41cf76c5, 로그인 세션): 그래프 뷰 > mssql-dk-dev(DK온라인) > `dk_data_release_main`(123 테이블 + 300 함수·프로시저 = 423항목) 상세 → (1) 컨텐츠 카테고리 그룹 **66개 전량 렌더 · 423행 · (0/N) 0 · 절단 0 · routine-only 43그룹**("NPC 콘텐츠 41" 등), aside scrollH 12423, (2) 행 자식(`<code>`) 합성 click → 이벤트 위임 승격 → `singleinfo` 노드 상세 조회, (3) pageerror 0. 서빙 자산 baked(`ROW_CAP = 5000`·`_ctUl` grep=9). evidence: relmain_full.png.
- 주(정직): 사용자 스크린샷의 정확한 >500 스키마(gemstone/binto32/merchant — DK QA/production 추정)는 좌표 특정 못 함. 단 검증한 423/66그룹 스키마 전량 렌더 + ROW_CAP=5000 결정론(적대 리뷰 확인)으로 해당 >500 스키마도 (0/N) 없이 전체 표시됨.
- Changes: `docs/test-runs.d/20260715T2237-graph-cluster-detail-fulllist.md` Run 3 DEFERRED→PASS · `docs/TASK.md` POST-DEPLOY 체크박스 close · `docs/REPORT.md` 완결 갱신 · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260715T223744-graph-cluster-detail-fulllist · ANCHOR 0003 무충돌.
## CHG-20260715T231656-graph-edge-drag-perf (그래프 드래그 관계선 재그림 per-frame 부하 최적화 — 인접 인덱스 + in-place Graphics 재사용 + rAF 코얼레싱)
- Date: 2026-07-15. 계기: graph-edge-follow-drag(CHG-20260715T181939) 배포 후 사용자 실측 "관계선 추종은 정상이나 드래그 프레임당 재그림 부하 심함" → 후속 최적화.
- 병목(적대 리뷰 F1 확증): `_refreshIncidentEdges` 프레임마다 (a) `_built.edges` 전량 O(E) 스캔 (b) incident 엣지 `destroy({children})`+`new Graphics()` 재생성(GPU 지오메트리 재할당+GC). 허브/대형 스키마 드래그 시 프레임당 수백~수천 Graphics 폐기·재생성 + `_moveElement`↔`translateElementTo` 이중 호출.
- Changes(feature-0003, frontend-only 1파일 + 테스트):
  - `src/static/graph/graph-renderer-pixi.js`:
    - ① `_edgeIndex`(node→incident edge[]) `draw()` 구성(순수 `PixiAdapterPure.buildEdgeIndex` 추출)·`setData` 무효화 + `_incidentEdges(moved)` dedup 반환(O(incident), 폴백 O(E) filter). + **P3(적대 리뷰)**: 끝점 해소를 `_nodeById`(draw 구성·setData 무효화) 기반 `_resolvePos` O(1) 로 — `getElementPosition` O(N) `nodes.find` 제거(O(incident×N)→O(N+incident)).
    - ② `_paintEdge(g,e,a,b)`(clear+라벨자식 destroy 후 재-path) 신설, `_drawEdge`=`_paintEdge(new Graphics())` 위임(신규·full draw byte-동일). `_refreshIncidentEdges` 는 기존 엣지(`old.parent===world && typeof old.clear==='function'`) in-place 재사용, 신규만 `_drawEdge`+addChild.
    - ③ `_scheduleEdgeRefresh(movedIds)`(rAF 이동 id 누적→프레임당 1회 refresh+render, 비-rAF 동기 폴백) + `_flushEdgeRefresh`(dragend 즉시). `_moveElement`(양분기)·`translateElementTo` 가 `_refreshIncidentEdges`+`_render` 직접호출 대신 `_scheduleEdgeRefresh`. `_emitDrag` dragend flush, `destroy` rAF cancel. 노드 좌표·hit-grid 는 동기 유지.
  - `tests/headless/test_pixi_adapter.js`: T24 10종 + **T25 13종(적대 리뷰 C1~C4 실-경로 하드닝: 실 `_paintEdge` clear+stale라벨 destroy+재-path·순수 `buildEdgeIndex` 자기루프/null·재사용불가 else 분기·미해소 skip·`_resolvePos` O(1)/폴백)** + T23 회귀. ALL PASS 96/0.
- 정확성 불변: cross-category 추종(graph-edge-follow-drag OR 판정)·full draw() diff·_objSig 재사용 계약·zIndex 페인트 순서 유지. 라벨 엣지도 재사용 시 자식 destroy 후 재구성(stale 무).
- 비변경: 팬/줌·상태·미니맵·hover·우클릭·클릭·백엔드/RBAC/스키마 0.
- 검증: `node --check`(ESM) PASS · 헤드리스 96/0 · §18.8 적대 리뷰(결함 없음+지적 4건 반영) · POST-DEPLOY PB-0008 라이브(대형 스키마 드래그 프레임률·추종 정확성, 잔여).
- Cross-ref: TASK 20260715T2316 · REV/TEST-20260715T231656-graph-edge-drag-perf · test-runs.d/20260715T2316-graph-edge-drag-perf.md · 선행 CHG-20260715T181939-graph-edge-follow-drag · 그래프 도메인 정본 feature-0016 · ANCHOR 0003 무충돌.

## CHG-20260716T000000-graph-edge-drag-perf-postverify (그래프 드래그 관계선 재그림 최적화 POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-16. CHG-20260715T231656-graph-edge-drag-perf(PR #832, main bfb1aa98) 배포 후 라이브 실증. 코드 변경 0(문서 전용).
- 실증(win-browser 실 Windows Chrome, 배포 bfb1aa98, PixiJS): P1(적대 리뷰) 반영해 pointerup 후 캡처. ① 추종 정확성 유지 — root 제품 카테고리 "건즈-개발·1" + gunzgame 409객체 dense-edge 테이블 드래그 모두 새 위치 관계선 추종·옛 위치 orphan 0. ② 부하 개선(정량) — gunzgame 40 pointermove 동기=30.4ms(0.76ms/move)·동기 burst 중 rAF 프레임 0(40 move 엣지 재그림이 단일 rAF 코얼레싱, 재사용-repaint). ③ dragend `_flushEdgeRefresh` 동기 반영·stale 0. ④ pageerror 0. 서빙 자산 baked(perf 함수 grep=11).
- Changes: `docs/test-runs.d/20260715T2316-graph-edge-drag-perf.md` Run 3 DEFERRED→PASS · `docs/TASK.md` POST-DEPLOY 체크박스 close · `docs/REPORT.md` 완결 갱신 · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260715T231656-graph-edge-drag-perf · flake 선행수정 feature-0002 CHG-20260715T234757-probe-throttle-monotonic-flake(무관 CI red 해소) · ANCHOR 0003 무충돌.

## CHG-20260716T003901-graph-cluster-detail-collapse (스키마 클러스터 상세: 컨텐츠 카테고리별 접기/펼치기, Minor §12.3)
- Date: 2026-07-16. feature-0003 web/UI 프론트 단독(3파일). cluster-detail-fulllist(CHG-20260715T223744) 후속. 그래프 도메인 정본 feature-0016.
- 사용자 요청: 전체 출력 후속으로 상세 패널에서 컨텐츠 카테고리별 접기/펼치기 구성(긴 목록 탐색성).
- Changes:
  - `graph-state.js`: `_metaGraph.panelGroupCollapsed`(Set<sg.key>) 신설 — 접힌 컨텐츠 카테고리 유지(같은 클러스터 재렌더 간, 세션 한정).
  - `graph-ctxmenu.js` `_metaGraphRenderClusterDetail`: 그룹 헤딩=disclosure(`role=button`·`aria-expanded`·`data-group-key`·캐럿 ▾/▸, 초기 `panelGroupCollapsed` 반영) · `rowHTML(t,collapsed)`(행 `<li>` `amgr-ct-row-li`+접힘 시 `amgr-ct-collapsed`) · 섹션 헤더 '모두 접기/펼치기'(`#metaGraphCtCollapseAll`, 그룹 존재 시) · sgs 계산 h4 방출 전 이동 · 이벤트 위임 확장(`_toggleCtGroup` = 헤딩~다음 헤딩 전 멤버 행 토글+캐럿/aria/state 갱신; click 헤딩 분기 우선; keydown Enter/Space; 모두 접기/펼치기 로직).
  - `graph.css`: `.amgr-ct-group` cursor/hover/focus·`.amgr-ct-group-caret`·`li.amgr-ct-collapsed{display:none}`·`.amgr-ct-collapse-all`.
- 비변경: 전체 출력(캡)·집계/membership/hiddenKinds·행 클릭·hover·백엔드/RBAC/스키마 0. 순수 additive UI. cache-buster placeholder 수기편집 없음.
- 검증: `node --check`(2파일) PASS · CSS 균형(221:221·66:66) · §18.8 적대 리뷰 · POST-DEPLOY PB-0008(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260716T0039 · REV/TEST-20260716T003901-graph-cluster-detail-collapse · test-runs.d/20260716T0039-graph-cluster-detail-collapse.md · 선행 CHG-20260715T223744-graph-cluster-detail-fulllist · ANCHOR 0003 무충돌.

## CHG-20260716T005817-graph-cluster-detail-collapse-postverify (컨텐츠 카테고리 접기/펼치기 POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-16. cluster-detail-collapse(CHG-20260716T003901, PR #835 main 00454608) 배포 후 win-browser PB-0008 라이브 실증. 코드 변경 0(문서 전용).
- 실증(실 Windows Chrome relay, 배포 00454608, 로그인 세션): 그래프 뷰 > mssql-dk-dev > dk_data_release_main(423항목·66 컨텐츠 카테고리) 상세에서 (1) 헤딩 클릭 접기/펼치기(NPC 콘텐츠 41행 표시↔display:none·캐럿 ▾↔▸·aria-expanded), (2) 모두 접기/펼치기 66그룹(라벨 "▾ 모두 접기"↔"▸ 모두 펼치기" 정합 — MINOR #1 수정 실증), (3) 재렌더 접힘 유지(접기→행 클릭 노드조회→뒤로→여전 접힘, panelGroupCollapsed sg.key 제어문자 포함 매칭), (4) 키보드 Enter/Space 토글, (5) 행 클릭 조회 불변·pageerror 0. 서빙 자산 baked(grep=10). evidence: collapse_evidence.png(▸ NPC 콘텐츠·▾ 퀘스트 시스템·▸ 성 시스템 공존 + 모두 접기 버튼).
- Changes: `docs/test-runs.d/20260716T0039-graph-cluster-detail-collapse.md` Run 3 DEFERRED→PASS · `docs/TASK.md` POST-DEPLOY 체크박스 close · `docs/REPORT.md` 완결 갱신 · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260716T003901-graph-cluster-detail-collapse · ANCHOR 0003 무충돌.

## CHG-20260716T012805-graph-cluster-detail-group-hoverpan (스키마 클러스터 상세: 컨텐츠 카테고리 헤딩 hover 시 카메라 팬, Minor §12.3)
- Date: 2026-07-16. feature-0003 web/UI 프론트 단독(1파일). cluster-detail-collapse 후속. 그래프 도메인 정본 feature-0016.
- 사용자 요청: 상세 패널 다른 객체(행)처럼 컨텐츠 카테고리 헤딩 hover 시 해당 위치로 카메라 부드럽게 이동.
- Changes:
  - `src/static/graph/graph-ctxmenu.js` `_metaGraphRenderClusterDetail`:
    - 그룹 헤딩에 `data-pan-key = sg.tables[0].key`(그룹 **첫 멤버 노드 key**) — 행 hover-pan 과 동일하게 노드로 팬. 첫 멤버는 항상 실 노드라 진입경로(카드클릭 Local·콤보/히스토리 ById-API)·fam 정합에 무관하게 견고.
    - hover 이벤트 위임 확장: `_panTargetOf`(행 `data-node-key` **또는** 헤딩 `data-pan-key`) → `_metaGraphHoverPan`. mouseout/focusout 선택자에 `.amgr-ct-group[data-pan-key]` 추가.
- 설계 전환: 초판 타깃 = 캔버스 그룹 박스 `GB:comboId+SEP+fam`(fam 정합 확증). 단 §18.8 적대 리뷰가 콤보/히스토리-뒤로 경로(`ById`, API depth=1)의 API↔모델 집합 divergence 시 fam-불일치 caveat(graceful no-op) 지적 → **첫 멤버 노드 key 로 전환**해 근본 제거(노드 key 는 fam·경로 무관, 제어문자·String.fromCharCode 불필요).
- 비변경: 헤딩 클릭(접기/펼치기)·행 클릭 조회·행 hover-pan·collapse/전체출력·백엔드/RBAC/스키마 0. 순수 additive. cache-buster placeholder 수기편집 없음. 소스 리터럴 0x01 부재.
- 검증: `node --check` PASS · §18.8 적대 리뷰 · POST-DEPLOY PB-0008 라이브(잔여, visual_verification_scope: always).
- Cross-ref: TASK 20260716T0128 · REV/TEST-20260716T012805-graph-cluster-detail-group-hoverpan · test-runs.d/20260716T0128-graph-cluster-detail-group-hoverpan.md · 선행 CHG-20260716T003901-graph-cluster-detail-collapse · ANCHOR 0003 무충돌.

## CHG-20260716T015146-graph-cluster-detail-group-hoverpan-postverify (컨텐츠 카테고리 헤딩 hover-pan POST-DEPLOY 라이브 실증 기록, doc-only)
- Date: 2026-07-16. cluster-detail-group-hoverpan(CHG-20260716T012805, PR #838 main d2c72fdc) 배포 후 win-browser PB-0008 라이브 실증. 코드 변경 0(문서 전용).
- 실증(실 Windows Chrome relay, 배포 d2c72fdc, 로그인 세션): DK dk_data_release_main(66 컨텐츠 카테고리) 상세에서 (1) 66 그룹 전부 `data-pan-key`=첫 멤버 노드 key("NPC 콘텐츠"→Combine 테이블·"게임 콘텐츠 조회"→P_CashItem_ReadBy_BackOffice 프로시저), (2) 헤딩 hover(200ms intent) → 카메라 부드럽게 팬: "NPC 콘텐츠"(TitleInfo·MerchantName 영역)↔"게임 콘텐츠 조회"(SetItem·spDeleteCollection 영역) 서로 다른 위치로 이동·미니맵 뷰포트 박스 이동, (3) 행 hover-pan·클릭 조회 불변·pageerror 0. 서빙 자산 baked(grep=8). evidence: hover_g0.png·hover_g45.png.
- Changes: `docs/test-runs.d/20260716T0128-graph-cluster-detail-group-hoverpan.md` Run 3 DEFERRED→PASS · `docs/TASK.md` POST-DEPLOY 체크박스 close · `docs/REPORT.md` 완결 갱신 · `docs/REVIEW.md` postverify REV.
- Cross-ref: 원천 CHG-20260716T012805-graph-cluster-detail-group-hoverpan · ANCHOR 0003 무충돌.

## CHG-20260716T010501-doc-sync-rn-0716 (TASK-20260716T010501-doc-sync-rn-0716 — 07-15~16 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: releases 배열 head 에 **date "2026-07-15" 새 블록 prepend**(7항목: admin 6·common 1)·summary 작성. generated 07-14→07-15. 기존 29 블록 보존(총 30).
- **cache-buster 무변경**: 소스 `?v=dev` placeholder 고정(§13.1 ITEM-09 what#3 — Dockerfile `inject_asset_stamp.py` content-hash 빌드 주입·deploy-web `asset_stamp_verify` 하드게이트). index/admin.html 편집 0. release-notes-data.js 내용 변경만으로 전역 content-hash 변화 → wrapper 재빌드 시 서빙 토큰 자동 갱신(수동 bump 부적용·해시 불변).
- 제외: 각 기능 *-postverify(배포 검증 기록)·#805 friction-ledger(내부)·probe/llm-probe 내부 안정성(⑥ 포괄)·feature-0021 red-team 백엔드(사용자 비가시 — 콘솔 'AI 추론' 표면만 노출).
- Verification: `node --check` PASS · vm 구조검증(30 releases·07-15 head 7항목[admin 6·common 1]·07-14 보존[10]·스키마·누출0). `verify_release_notes.mjs` 33/34 PASS(1 FAIL=styles.css scroll 정규식 brittleness·본 cycle 미변경·pristine HEAD 동일 재현·feature-0003 소관).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- **landing/배포 소유=cron wrapper 위임**(로컬 commit 만·push/merge/deploy 미수행). META(wiki·SECURITY §23·meta/REVIEW)는 별도 commit(0cc64c2b, REV-20260716T010501-META-0037-doc-sync-0716).

## CHG-20260716T140735-doc-sync-rn-0716b (TASK-20260716T140735-doc-sync-rn-0716b — 07-16 낮 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경:
  - `static/release-notes-data.js`: releases 배열 head 에 **date "2026-07-16" 새 블록 prepend**(4항목: admin 4)·summary 작성. generated 07-15→07-16. 기존 30 블록 보존(총 31).
- **cache-buster 무변경**: 소스 `?v=dev` placeholder 고정(§13.1 ITEM-09 what#3 — Dockerfile `inject_asset_stamp.py` content-hash 빌드 주입·deploy-web `asset_stamp_verify` 하드게이트). index/admin.html 편집 0.
- 제외: 각 *-postverify(배포 검증 기록)·guidance 권한 재배치 등 내부 권한 체계 변화(화면 체감은 ④ 서브탭 통합으로 포괄)·기본 프롬프트 fallback 목록 제외(내부 정리).
- Verification: `node --check` PASS · vm 구조검증(31 releases·07-16 head 4항목[admin 4]·07-15 보존[7]·스키마·누출0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- **attended run — landing/배포 스킬 소유**(분리 commit→PR→merge→deploy-web→서빙 검증). META(SECURITY §23 정정·wiki·meta/REVIEW)는 별도 commit. 직전 스케줄 잔재(0cc64c2b·eeabda19)는 rebase harvest.

## CHG-20260721T1758-realtime-progress-propagation (20260721T1758-realtime-progress-propagation — assistant 진행상황/답변 실시간 전파, Major §12.3, frontend-only)
- 계기: 사용자 신고 — 타 계정 대화 모니터링(또는 그룹 대화) 중 대화를 열어둔 관찰자에게 다른 사용자가 시작한 run 의 assistant 말풍선이 실시간으로 안 뜸(다른 대화 갔다 와야 표시).
- 근본원인: 진행상황 폴링(`pollProgress`)이 본인 `sendPrompt` / `loadHistory` 의 `last_status==processing` 감지 시에만 시작 → 유휴 관찰자에겐 새 run 을 감지할 배경 폴링 부재. 서버는 무결(`/api/progress`·`/api/history` 가 `conversation.read.any` 로 관찰자에게도 live 반환).
- 변경(`static/app.js`, +133): 유휴 run-감지 폴러 추가(활성 run 추적 없을 때 `/api/progress` client_run_id 없이 ~4s/숨김 15s 폴링 → 서버 run_id 가 baseline 과 달라지면 `loadHistory` 위임). `loadHistory`(유휴 arm/processing·no-conv stop, `!append`)·`selectConversation`·`handleLogout`·`visibilitychange` 배선. 감지 범위=모든 대화(사용자 선택). feature-0009 foreign-run 불변식 존중(활성 추적 중 dormant). 백엔드 무변경.
- 보안/인가 무영향: 감지·재로드는 기존 `/api/progress`·`/api/history`(read.own|read.any) 를 그대로 사용 — 새 권한 표면·데이터 노출 없음.
- Verification: `node --check` PASS · 유닛 `verify_run_detect_poll.mjs` 23/23 · feature-0003 pytest RC=0(무회귀) · 실 Windows 브라우저(Chrome 150) 유휴 탭 실시간 감지+"처리 중" 말풍선 렌더 실측+스크린샷(§16.6, TEST.md). 검증 후 라이브 배포본 원복.
- Files: `static/app.js`, `tests/verify_run_detect_poll.mjs`, `docs/{TASK,REPORT,TEST,FUNCTION,MODIFY,REVIEW}.md`.
- landing/배포: verify-completion(operational, feature-0003) → commit → push → PR/머지·배포는 자동 동기화 정책/wrapper 소유.

## CHG-20260722T010501-doc-sync-rn-0722 (TASK-20260722T010501-doc-sync-rn-0722 — 07-21 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경: `static/release-notes-data.js` releases head 에 "2026-07-21" 블록 prepend(1항목 improved/work: 다른 참여자 질문에 대한 AI 답변 과정 실시간 표시·멀티탭 동기화) + generated 2026-07-16→2026-07-21. 렌더 로직·백엔드·스키마·RBAC·엔드포인트 0.
- cache-buster: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py` + deploy-web.sh `asset_stamp_verify` 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침).
- 근거 정본: feature-0003 TASK/REPORT realtime-progress-propagation(a999594e — 유휴 관찰자 run-감지) + git log 8f3dd00b..HEAD.
- Verification: `node --check` PASS · vm 구조검증(releases 수·07-21 head 1항목[improved/work]·07-16 보존·스키마·누출0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).

## CHG-20260722T020408-msg-edit-textarea-contrast (20260722T020408-msg-edit-textarea-contrast — 메시지 '수정' 편집 UI 글자 비가시 수정 + 편집 폼 재구성, Minor §12.3, frontend-only 표시전용)
- 계기: 사용자 신고 — 보낸 요청 메시지를 '수정' 기능(단순 수정 / 요청사항 수정)으로 편집할 때 텍스트박스 배경색과 글자색이 같아 글자가 안 보임. "실제 사람이 사용할 수 있도록 UI 재구성" 요청.
- 근본원인: `.message-edit-textarea` 가 흰 배경(`var(--surface)`#fff)에 `color:inherit` — 편집 UI 가 삽입되는 파란 user 말풍선(`.message.is-user .message-bubble`, `color:#fff`)의 흰 글자색을 상속 → 흰 글자 on 흰 배경(대비 1:1) 비가시.
- 변경(`static/styles.css`): ① textarea `color:inherit`→`color:var(--text)`(#26251e) ② `.message-edit-box` `color:var(--text)` 상속 차단(방어) ③ `.message.is-user .message-bubble.message-bubble-editing`(특이도 0,4,0 — 파랑 0,3,0 을 이김) 신설로 편집 진입 시 파란 말풍선 → 중립 편집 패널(surface/border/shadow) 전환 ④ `::placeholder` 색·focus border 보강.
- 변경(`static/app.js` `_startInlineEdit`, +1행 +주석): `bubbleEl.classList.add("message-bubble-editing")`. 취소(renderMessages)/성공(refreshWorkspace) 재렌더 경로에서 말풍선 재생성되어 클래스 자동 소멸(제거 불필요).
- 보안/인가 무영향: 표시 계층만 — 편집 엔드포인트(`_submitMessageEdit`)·브랜치/IDOR 게이트·RBAC·스키마 0. `message-bubble-editing` 은 신규 unique 클래스(기존 `is-editing`(admin dashboard)·`.dashboard-widgets.is-editing` 와 선택자 분리·미충돌). feature-0019 ANCHOR §1-§3(브랜치 데이터 모델·INV-1~5) 무충돌.
- cache-buster: `?v=dev` 고정(index/admin.html 편집 0 — inject_asset_stamp.py 빌드 자동주입·deploy-web asset_stamp_verify 하드게이트, 수동 bump 폐지).
- Verification: `node --check` PASS · **headless Chromium 실측**(실 styles.css cascade) — 수정본 textarea 대비 15.38:1·편집 말풍선 파랑→중립전환·재답변버튼 5.17:1 / 수정 전 재현 1.0:1(버그 확인) · 스크린샷. **POST-DEPLOY PB-0008 Windows-browser 라이브 예정**(TEST.md CHECK#13, test-runs.d fragment).
- Files: `static/styles.css`, `static/app.js`, `docs/{TASK,REPORT,TEST,MODIFY,REVIEW}.md`, `docs/test-runs.d/20260722T020408-msg-edit-textarea-contrast.md`.
- landing/배포: verify-completion(feature-0003) → commit → push → PR/머지=자동 동기화 정책. **배포(`make deploy-web`)는 외부 영향 — 사용자 confirm**.

## CHG-20260722T024500-msg-edit-textarea-contrast-postverify (msg-edit-textarea-contrast POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY PB-0008 Windows-browser 라이브 실증 기록 append + TASK 체크박스 완료. 코드/자산 0 — test-runs.d fragment 20260722T020408 POST-DEPLOY 갱신 + TASK.md 박스.
- 배포본 main f7a14e9a(PR #866) — `deploy-web --web-only` 무중단(soak PASS). Windows Chrome 150 실측: textarea 대비 ~15.4:1(글자 판독)·편집 말풍선 중립 전환·재답변버튼 판독. 사용자 신고 해소 실증.
- Files: `docs/TASK.md`, `docs/test-runs.d/20260722T020408-msg-edit-textarea-contrast.md`, `docs/MODIFY.md`, `docs/REVIEW.md`.

## CHG-20260722T1252-point-rail-range-window (20260722T1252-point-rail-range-window — 대화 뷰 우측 미니맵 뱃지 범위화 + 클릭 위치 비례 스크롤 + 로그 윈도잉, Major §12.3, frontend-only additive)
- Files: `unit/feature-0003-agent-web-ui/src/static/app.js`, `unit/feature-0003-agent-web-ui/src/static/styles.css`.
- A(뱃지 범위화): `layoutMessagePointRail()` — `dot.style.top`(상단%) + `dot.style.height`(범위%) 막대 배치(logRect 루프 밖 1회 측정). CSS `.message-point-dot` 점(8×8 원)→막대(width 6px·min-height 4px·border-radius 3px·translateX만·is-active/hover 폭 11px).
- B(클릭 비례): rail 클릭 핸들러가 뱃지 내 클릭 y 비율 계산 → 신설 `scrollMessagePointToRatio(target, ratio)`(메시지 [top,bottom] 대응점을 뷰포트 중앙, EaseOutExpo). 기존 `scrollMessagePointIntoCenter`(항상 중앙) 유지 — 검색결과/앵커 점프 재사용.
- C(윈도잉): `loadHistory` conversation-generation 가드(`_loadGenConvId` — apiFetch 후 전환 시 bail, R1)·`_beginAppendScrollPreserve`/`_endAppendScrollPreserve`(prepend 후 scrollTop 보정, flag 無 — 예외 시 맨-아래 fallback)·`_fillInitialWindowSoon`(대화별 `_fillToken`·뷰포트 4배 목표·rAF·25p 상한, B1)·`_loadOlderGuarded`(자동/버튼 공용 단일 가드)·`_maybeAutoLoadOlder`(`_pointScrolling` 억제, R2)·`_animatePointScroll` `_pointScrolling` flag. `renderMessages` 맨-아래 스크롤 무변경(가드 flag 제거 재설계). scroll 리스너 + loadMoreBtn 배선.
- 검증: `node --check app.js` PASS · 적대 코드리뷰(REV subagent) R1/R2/B1 반영. 핵심 우려 preserveScroll leak = flag 제거로 moot 확인.
- landing/배포: verify-completion(feature-0003) → commit → push → PR/머지(자동 동기화) → `deploy-web`(deploy_scope: included, 외부영향 1줄 표면화) → POST-DEPLOY PB-0008.

## CHG-20260722T1355-point-rail-range-window-postverify (POST-DEPLOY 라이브 시각검증, 비-정책 doc-only)
- POST-DEPLOY PB-0008 Windows-browser 라이브 실증(배포본 22c3b9cb, PR #873). A(막대 범위화)·B(클릭 위치 비례) 라이브 PASS. C(윈도잉) 자동 페이징은 환경 대화 모두 20 메시지 미만(hasMoreHistory=false)이라 미트리거 — 코드/리뷰 검증 + 회귀 없음. gap: 20개 미만 대화 "4배 상한" 미적용(기존 서버 페이징 재사용 트레이드오프).
- Files: `docs/test-runs.d/20260722T125200-point-rail-range-window.md`(POST-DEPLOY append), `docs/test-runs.d/evidence/point-rail-range-window-live.png`, `docs/TASK.md`, `docs/MODIFY.md`.
- 코드/자산 변경 0.

## CHG-20260722T1420-point-rail-range-window-dom-windowing (윈도잉 강화 — 사용자 후속 요청, Major §12.3, frontend-only)
- Files: `unit/feature-0003-agent-web-ui/src/static/app.js`.
- C 강화: `state.renderCount` DOM 윈도잉. `_visibleMessages`·`_ensureMessageRendered`·`_applyRenderWindowSoon`(상한 렌더창 확대+하한 서버 페이징)·`_maybeExpandOrLoadOlder`(최상단 창 확장→서버 로드). `renderMessages`/`renderMessagePointRail` 이 최근 창만 렌더. `loadHistory` renderCount 관리(초기 8·floor 포함·append 확장). 검색/캘린더 점프 창 확장. `_windowBase` 절대 인덱스 복원.
- 적대리뷰(REV subagent) 발견1(절대idx)·2(floor 칩)·5(검색 optimistic id=null)·6(주석) 반영, 3(live-poll 슬라이딩)·4(연쇄 확장) known-limitation.
- 검증: `node --check app.js` PASS. POST-DEPLOY PB-0008 재검증 예정(conv[2] 일부만 로딩).

## CHG-20260722T1440-point-rail-window-initial-tuning (윈도잉 초기값 튜닝, frontend-only)
- Files: `unit/feature-0003-agent-web-ui/src/static/app.js` (`WINDOW_INITIAL_RENDER` 8→3).
- 라이브 실측(conv[2] 14개·개별 메시지 큼)에서 초기 8개가 높이 뷰포트 13배 → "4배만" 미달. 초기값을 낮춰 큰 메시지 대화도 4배 근처 유지. 짧은 메시지 대화는 상한 로직(`_applyRenderWindowSoon`)이 4배까지 채워 무손실. 로직 변경 없음(상수만).
- 검증: `node --check` PASS. POST-DEPLOY 재검증(conv[2] 초기 ~3개).

## CHG-20260722T1450-point-rail-windowing-postverify (POST-DEPLOY 윈도잉 재검증, 비-정책 doc-only)
- POST-DEPLOY PB-0008 라이브 재검증(배포본 66d1e735): conv[2](14개) 초기 3개 렌더·최상단 스크롤 확장(3→13→14)·뱃지 동기·A 막대 정상. 사용자 후속 요구 실증 완료. 코드/자산 0(스크린샷 evidence 추가).
- Files: `docs/test-runs.d/20260722T125200-point-rail-range-window.md`, `docs/test-runs.d/evidence/point-rail-windowing-live.png`, `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`.

## CHG-20260722T192736-history-top-indicator (대화 상단 '위에 더 있음' 페이드 신호, Minor §12.3, frontend-only 표시전용)
- Files: `unit/feature-0003-agent-web-ui/src/static/{index.html,styles.css,app.js}`.
- 위에 더 불러올 대화(윈도우 밖 renderCount<total 또는 서버 미로드 hasMoreHistory)가 있으면 messageLog 상단에 페이드 그라데이션만 표시(칩·텍스트·스피너 없음 — 사용자 결정: 최소 시각 신호). pointer-events:none(무방해)·rail 폭 제외. `_updateHistoryTopIndicator` 를 renderMessages 끝+empty 경로에서 호출.
- 백엔드/편집로직/RBAC/스키마 무영향. point-rail-range window(renderCount) 위에 얹은 순수 표시 레이어.
- 검증: `node --check` PASS. POST-DEPLOY PB-0008 예정.

## CHG-20260722T195000-history-top-indicator-postverify (POST-DEPLOY 라이브 검증, 비-정책 doc-only)
- POST-DEPLOY PB-0008 라이브 PASS(배포본 029927dc): 위에 더 있음→페이드 표시·전부 로드→숨김·짧은 대화→없음·pointer-events:none 무방해. 사용자 요구 실증. 코드 0(스크린샷 evidence 추가). 배포 초회 transient soak 롤백→재실행 remedy.
- Files: `docs/test-runs.d/20260722T192736-history-top-indicator.md`, `docs/test-runs.d/evidence/history-top-fade-live.png`, `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`.

## CHG-20260722T122635-shared-branch-readonly-paging (20260722T122635-shared-branch-readonly-paging — 공유/그룹·익명 공유-링크 뷰 편집 버전 읽기전용 페이징, Major §12.3, PLAN-APPROVED design-review C)
- 계기: 사용자 요청 — 공유 대화 + '링크 공유' 출력 화면에서도 편집 버전 `< n/m >` 페이징이 정합하게 동작하도록. 현재는 브랜치된 대화 공유 시 비활성 버전이 평면 노출됨(pager 없음).
- 방향(design-review C): 읽기전용 — active_leaf(공유 근거)를 바꾸지 않고 기존 브랜치 버전을 조회만. 새 재답변/영속 전환은 그룹에서 계속 잠금(INV-4 mutation lock 불변).
- 변경(`routers/_conv_store.py`, +189): `_branch_enrich_display`(두 로더 공용 active-path 필터+가시성-scoped 버전메타·읽기전용)·`_branch_version_groups(visible_pred)`·`_branch_window_pred`/`_branch_idrange_pred`(가시성 술어)·`_branch_resolve_readonly_leaf`(대상 검증+leaf, fail-closed)·`_branch_readonly_thread_ids`. `_get_history`/`_share_load_messages` 에 `override_active_leaf`(비영속). `_get_history` 그룹 enrich(이전 SEC MINOR-B skip 대체, window-scoped).
- 변경(`routers/conversations.py`,`routers/share.py`): `/api/history`·`public_share_view` 에 `branch_view` 파라미터 → resolver(멤버 window / 공유 [floor,anchor] 검증) → override. `app.py`: `_branch_resolve_readonly_leaf` re-export.
- 변경(프론트): `app.js`(그룹 `_pageBranch`→`loadHistory({branchView})` 읽기전용)·`share.js`(공유 뷰 pager+read-only nav)·`share.css`(pager 스타일).
- 보안(핵심): 가시 범위 밖 버전은 카운트·sibling_ids·존재·내용 모두 fail-closed 차단(window/id-범위 술어). active_leaf 불변(읽기전용).
- 비변경(회귀 0): has_branches=false 대화는 fast-path skip. 1:1 owner(window=None)는 `visible_pred=None`→전체(기존 페이징·`/branch/switch` 영속 불변). 백엔드 write/RBAC/스키마 0.
- Verification: `py_compile` 5 + `node --check` 2 · 보안 단위 10 PASS · §18.8 적대 보안 리뷰(REVIEW) · POST-DEPLOY 양 surface PB-0008.
- Files: `routers/{_conv_store,conversations,share}.py`, `app.py`, `static/{app.js,share.js,share.css}`, `tests/test_shared_branch_readonly_paging.py`, `docs/{TASK,MODIFY,FUNCTION,REPORT,TEST,REVIEW}.md`, `../feature-0019-message-editing/docs/ANCHOR.md`(INV-4 개정).
- landing/배포: verify-completion → commit → PR/머지=자동 동기화. 배포=외부 영향 confirm(이미 승인 범위).

## CHG-20260722T130000-shared-branch-readonly-paging-postverify (shared-branch-readonly-paging POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 배포·양 surface 라이브 검증 기록 + TASK 완료. 코드/자산 0.
- 배포: PR #887 → main 622b7434 → `deploy-web.sh --web-only`(soak PASS).
- 라이브(배포본 622b7434, 대화 20260722015229-79da15cb=group+active share): 공유-링크 익명 API — pager 메타·branch_view 읽기전용 전환·999999999 fail-closed. 인앱 그룹 인증 API — pager(window-scoped)·branch_view 전환·active_leaf 불변. Windows-browser 시각 미수행(브리지 다운, §15.4.1 escape — API 실측+단위 12 로 보완).
- Files: `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`, `docs/TEST.md`.

## CHG-20260723T010501-doc-sync-rn-0723 (TASK-20260723T010501-doc-sync-rn-0723 — 07-22 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경: `static/release-notes-data.js` releases head 에 "2026-07-22" 블록 prepend(6항목 fixed/work 3·improved/work 3 — 재답변 후 내 메시지 소실 복구·'수정' 창 글자 비가시·말풍선 공유 회귀·상단 '위에 더 있음' 흐림 신호·오른쪽 위치 막대 클릭 이동·공유/그룹 편집 버전 읽기전용 페이징) + generated 2026-07-21→2026-07-22. 렌더 로직·백엔드·스키마·RBAC·엔드포인트 0.
- cache-buster: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py` + deploy-web.sh `asset_stamp_verify` 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침).
- 근거 정본: 각 항목 owning POST-DEPLOY 커밋(4edb7701/5dbe7992·0ebbac8e/a8fb33d1·7a5b092a/94e2cadd·0db6fc36/109befe1·a92492e6/a70f8382·f0a32980/20562ff9) + git log cfa647df..HEAD.
- Verification: `node --check` PASS · vm 구조검증(33 releases·07-22 head 6항목[fixed 3·improved 3·area work]·07-21 보존·스키마·누출0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).

## CHG-20260723T024724-paging-scroll-preserve (20260723T024724-paging-scroll-preserve — 브랜치 페이징 스크롤 위치 보존, Minor §12.3, frontend-only UX)
- 계기: 사용자 신고 — 편집 버전 페이징 시 스크롤이 맨 아래로 튀어 연속 페이징 번거로움.
- 근본원인: `renderMessages()` 는 매 재렌더 `scrollTop=scrollHeight`; 비-append `loadHistory` 는 `_applyRenderWindowSoon`(rAF)로 재-스크롤; 공유 뷰 `render` 는 `#shareMessages` 교체로 문서 스크롤 튐.
- 변경(`static/app.js`): `loadHistory` 에 `preserveScroll` 옵션(저장 top 복원 + window-soon 생략, rAF). `refreshWorkspace(opts.preserveScroll)` 전달. `_pageBranch` 그룹/1:1 페이징에 preserveScroll 적용.
- 변경(`static/share.js`): `pageBranchShare` window.scrollY 저장→rAF 복원.
- 비변경(회귀 0): append(이전 이력 prepend)·일반 대화 로드·전송 후 스크롤은 기존(맨-아래/prepend 보존). preserveScroll 미지정 경로 전부 동일. 백엔드/스키마/RBAC 0.
- cache-buster: `?v=dev` 고정(빌드 자동주입).
- Verification: `node --check` 2 · POST-DEPLOY headless/Windows 실측(페이징 전후 scrollTop 보존).
- Files: `static/app.js`, `static/share.js`, `docs/{TASK,MODIFY,FUNCTION,REPORT,TEST,REVIEW}.md`.
- landing/배포: verify-completion → commit → PR/머지=자동 동기화. 배포=web-only(정적자산·백엔드 무관).

## CHG-20260723T033000-paging-scroll-preserve-postverify (paging-scroll-preserve POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 배포·양 surface 라이브 스크롤 실측 기록 + TASK 완료. 코드/자산 0.
- 배포: PR #889 → main 4ee7ea1d → deploy-web --web-only(soak PASS). 서빙 app.js `preserveScroll`·share.js `savedY` 반영.
- 라이브(Windows Chrome 4ee7ea1d): 인앱 그룹 브랜치 대화 페이징 후 scrollTop=0(scrollable maxTop 9538, 맨아래 안 튐)·스크린샷 육안. 공유-링크 짧은→긴(maxY 11535) 페이징 후 window.scrollY=0. 양 surface PRESERVED.
- Files: docs/{TASK,MODIFY,REVIEW,TEST}.md.

## CHG-20260723T033143-paging-scroll-longhistory (20260723T033143-paging-scroll-longhistory — 긴 이력 페이징 스크롤 보존 회귀 수정, Minor §12.3, frontend-only)
- 계기: 사용자 신고(admin '간단한 덧셈 계산' 3→4) — 이전 대화내역 길면 페이징 스크롤 보존 실패.
- 근본원인: preserveScroll 이 `_applyRenderWindowSoon` 생략 + loadHistory renderCount=WINDOW_INITIAL_RENDER(3) 리셋 → 긴 버전 스레드(브랜치 메시지 뒤 후속 턴)에서 브랜치 메시지(pager) 창 밖 → pager 소실·scrollHeight 급변.
- 변경(`static/app.js` loadHistory): preserveScroll 시 renderCount=messages.length(전체 렌더). 형제 버전 분기점-위 이력 동일 → 전체 렌더로 pager 유지 + scrollTop 정확 보존.
- 비변경: append/일반 로드 renderCount 무변경(회귀 0). 백엔드 0.
- Verification: node --check · POST-DEPLOY PB-0008(3→4 pager 유지+스크롤 보존).
- Files: `static/app.js`, docs.

## CHG-20260723T034500-paging-scroll-longhistory-postverify (paging-scroll-longhistory POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 라이브 실측 + TASK 완료. 코드 0. 배포 PR #891 → main 2cdb7907 → deploy-web --web-only(soak PASS).
- 라이브(Windows Chrome '간단한 덧셈 계산' 3→4): rendered 3→6(전체 렌더), pager '4/4' 유지, 브랜치 메시지 뷰포트 298px→298px 동일(scrollTop 4985, scrollable maxTop 11286, atBottom=false)·스크린샷 육안. verdict PRESERVED.
- Files: docs/{TASK,MODIFY,REVIEW}.md.
## CHG-20260723T071355-universal-ctxmenu (서비스 UI 우클릭 = 보편적 확장 메뉴 단축, Major §12.3, frontend-only)
- 계기: 사용자 요청(`/_template:entry`) — "각 요소 우클릭이 보편적 확장기능으로 동작. 대화·목록창='···', 대화 로그='☰'. 등과 같이."
- 변경(`static/app.js`, 2지점 additive):
  - `openFloatingMenu`: 모듈 전역 `_floatingMenuAnchorPoint`(우클릭 시 커서 좌표·1회 소비·finally 방어 해제) 도입, 위치 계산이 anchor 있으면 커서 기준·없으면 기존 trigger-rect 기준(**anchor=null byte-동치**·회귀 0).
  - 신규 `_CTX_MENU_TARGETS` 설정표 + `_hasSelectionWithin`(Range.intersectsNode) + `_onUniversalContextMenu`(document 위임 리스너) — 호스트(`.conv-item`/`.conv-folder-header`/`.message`) 매칭 시 기존 트리거 synthetic click 재발화(open 함수·권한·항목·토글 100% 재사용). input/link/미디어(img·svg·canvas·video)/contentEditable·호스트 내 텍스트 선택·키보드 contextmenu(0,0)는 기본 우클릭 양보.
- 비변경: 기존 '···'/'☰' 버튼 클릭 동작·위치, 대화 선택/폴더 토글(우클릭이 유발 안 함), admin.js, 그래프 우클릭(graph-ctxmenu.js), 백엔드/RBAC/스키마/엔드포인트 0.
- Verification: `node --check` PASS(2회) · §18.8 적대 리뷰 SHIP(MINOR 3 반영) · POST-DEPLOY PB-0008(AC-1~5).
- Files: `static/app.js`, docs/{TASK,FUNCTION,REPORT,REVIEW,TEST-runs}.md.

## CHG-20260723T075215-universal-ctxmenu-postverify (universal-ctxmenu 배포 + 라이브 실측 POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 라이브 실측 + TASK 완료. 코드 0. PR #897 → main **c6f7f98a** → `deploy-web.sh --web-only`(web-a/web-b 무중단 롤링·90s soak PASS·caddy no-op·자산 스탬프 e6d39fde416f). deploy_scope: included(FIRST_REQUEST.md 전역·§12.2 사전 승인).
- 라이브(win-browser Chrome 150, https://localhost/ 작업 화면, 실 contextmenu button2): AC-1 대화항목 우클릭→'···' 커서개방(공유/설정/폴더·aria=true)·AC-2 폴더헤더→폴더메뉴(하위/이름/지침/삭제)·AC-3 말풍선→'☰'(분기/공유·커서개방)·AC-4 텍스트 663자 선택 후 우클릭→native 보존(defaultPrevented=false·☰ 미개방)·AC-5 버튼 클릭 trigger-rect byte-동치(rightAligned·belowTrigger)·**errCount 0**. 서빙 app.js 신규 심볼 전부 hit.
- Files: docs/{TASK,MODIFY,REPORT,REVIEW,TEST-runs}.md.

## CHG-20260723T080415-floating-menu-close-fix (floating 메뉴 닫힘 결함 수정 — folderMenu 1급 승격, Minor §12.3, frontend-only)
- 계기: universal-ctxmenu 후속 사용자 신고 — 폴더 '···' 메뉴가 열린 뒤 바깥클릭/ESC 로 안 닫힘.
- 근본원인: `closeFloatingMenus()` 제거 id 하드코딩 `["convItemMenu","bubbleMsgMenu"]` → feature-0024 `id="folderMenu"` 누락(pre-existing drift). universal-ctxmenu 우클릭이 폴더 메뉴를 쉽게 열게 되며 표면화.
- 변경(`static/app.js`+`static/styles.css`): ① `openFloatingMenu` 생성 메뉴에 `menu.dataset.floatingMenu="1"` 마커. ② `closeFloatingMenus` 를 `[data-floating-menu]` id 무관 일괄 제거 + 트리거 리셋 selector 에 `.conv-folder-menu-trigger.is-open` 추가. ③ 정합: `_attachShareRangeEsc`(8383)·`_maybeSyncConversationListUnread`(11662) 열린-메뉴 가드에 folderMenu 포함 + `styles.css` `.conv-folder-menu-trigger.is-open{opacity:1}`.
- 비변경: conv-item '···'·말풍선 '☰' 닫힘(마커 제거=id 제거 superset), 백엔드/RBAC/스키마/엔드포인트 0.
- Verification: `node --check` PASS · §18.8 적대 리뷰 SHIP(NIT 3 fold-in) · POST-DEPLOY PB-0008(AC-1~5).
- Files: `static/app.js`, `static/styles.css`, docs/{TASK,FUNCTION,REPORT,REVIEW,TEST-runs}.md.

## CHG-20260723T081500-floating-menu-close-fix-postverify (floating-menu-close-fix 배포 + 라이브 실측 POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 라이브 실측 + TASK 완료. 코드 0. PR #902 → main **57ecc758** → `deploy-web.sh --web-only`(soak PASS·자산 스탬프 8373a9f479e2). deploy_scope: included(전역).
- 라이브(win-browser Chrome 150, https://localhost/, 테스트 폴더 API 생성 id=6 후 실 이벤트 dispatch, 검증 후 삭제·프로덕션 잔여 0): AC-1 폴더메뉴 바깥클릭 닫힘·AC-2 ESC 닫힘·AC-3 scroll 닫힘·AC-4 토글 닫힘+트리거 aria-expanded=false·is-open 제거·AC-5 conv-item 무회귀·errCount 0. 서빙 app.js `data-floating-menu` 2 hit·css `.conv-folder-menu-trigger.is-open` 1 hit.
- Files: docs/{TASK,MODIFY,REPORT,REVIEW,TEST-runs}.md.
## CHG-20260723T074530-reasoning-timeline (20260723T074530-reasoning-timeline — AI 운영 현황 > 추론 결함수정 전/후·답변개선 과정 가시화, Major §12.3, web/UI 프론트 + additive read-only API)
- 배경: 「AI 운영 현황 > 추론」이 리뷰 결함 수정 전/후 과정·답변 개선 과정을 드러내지 못해 관제 신뢰성 낮음(사용자 신고). 접근 A(기존 `redteam_reviews` 데이터 재구성 — 마이그레이션·계측·답변원문 저장 없음, AskUserQuestion 승인).
- `unit/feature-0003-agent-web-ui/src/routers/admin_reasoning.py`: `_query_reviews` 에 `include_rederive` 파라미터 + 0043 컬럼(`rederive_applied/rederive_tool_rounds/rederive_axis`) additive SELECT·응답 노출. 호출부 `admin_reasoning_redteam` 에 `information_schema` 컬럼 존재 감지 → 부재 시 `include_rederive=False` 폴백(stale agent 이미지, 회귀0). 모든 경로에서 rederive 3필드 기본값 보장.
- `unit/feature-0003-agent-web-ui/src/static/admin.js`: reasoning 탭 렌더 재구성 — 신규 `_reasoningConvLink`·`_reasoningStageTimeline`·`_reasoningFindingHtml`·`_reasoningAxisSummary` + 상수 `_REASONING_AXIS_LABELS`/`_REASONING_LEVEL_LABELS`. `_reasoningReviewRowHtml`·`renderReasoning` 개편(진행 5단계 타임라인·claim→fix_hint 전/후 대비·5축 집계·대화 딥링크·강도 한글화·힌트 문구). 통계 타일·페이징·메모리 노트 보존.
- `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.reasoning-timeline/-stage(-done/warn/skip/na/err)`·`.reasoning-finding(-block/warn)`·`.reasoning-ba(-col/-tag/-text/-arrow)`·`.reasoning-sev(-block/warn)`·`.reasoning-axis--{5축}`·`.reasoning-axis-summary/-badge`·`.reasoning-conv(-system)` 추가. 기존 `.reasoning-review-head` flex-wrap. 기존 `.reasoning-finding*` 3줄 재정의. CSS 변수 재사용·라이트/다크 대응.
- 검증: `node --check`(ESM) OK · `py_compile` OK · 실제 소스 추출 harness 단위 22/22 PASS. §18.8 panel(프론트/UX/보안 + 백엔드/QA) = REV-20260723T074530-reasoning-timeline.
- 불변: 백엔드 계측·스키마·RBAC·엔드포인트 무변경. cache-buster `?v=dev` 고정(빌드 자동 주입). POST-DEPLOY PB-0008(Environment: Windows-browser) 예정.

## CHG-20260723T084235-reasoning-timeline-postverify (reasoning-timeline 배포 + 라이브 실측 POST-DEPLOY, 비-정책 doc-only)
- POST-DEPLOY 라이브 실측 + TASK 완료. 코드 0. PR #901 → main **e4ef9384** → `deploy-web.sh --web-only`(web-a/web-b 무중단 롤링·soak PASS·자산 스탬프 d09bcdc34a46).
- 라이브(win-browser Chrome 150, https://localhost/admin, 리뷰 30건): 진행 타임라인 150 stages(30×5)·전후 대비 47·5축 집계(근거15/SQL6/완전성12/정직성14)·rederive "도구 재추론(SQL)"·대화 딥링크 30·통계 타일 6·pageerror 0. **W2 페이징 축 갱신** 47→93 재계산 확증. verdict pass 카드 **B1 정확**("결함 없음—통과"/"불필요(결함 없음)"). 서빙 admin.js 신규 심볼 8 hit.
- Files: docs/{test-runs.d/20260723T074530-reasoning-timeline.md, MODIFY.md, REVIEW.md}.

## CHG-20260724T010501-doc-sync-rn-0724 (TASK-20260724T010501-doc-sync-rn-0724 — 07-23 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경: `static/release-notes-data.js` releases head 에 "2026-07-23" 블록 prepend(7항목 new/work 2·improved/work 2·fixed/work 1·improved/admin 2 — 대화 폴더·폴더별 AI 지침·대화목록 월·연 날짜 묶음·우클릭 메뉴·메시지 버전/긴 이전 대화 페이징 스크롤·AI 답변 다듬기 전·후 보기·DB 전체 AI 자동 분석 완결성) + generated 2026-07-22→2026-07-23. 렌더 로직·백엔드·스키마·RBAC·엔드포인트 0.
- cache-buster: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py` + deploy-web.sh `asset_stamp_verify` 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침).
- 근거 정본: owning POST-DEPLOY 커밋(폴더 9392cf51/e3fec503/0a1378f3/1a2f2595·날짜트리 8b384b8a·우클릭 b51f93e9·페이징 fce9ab2b/5d0f8467·추론타임라인 a17fd1a7·DB분석 6da5e621) + git log aac76889..HEAD.
- 제외: graph-node-reveal(feature-0016)은 자체 POST-DEPLOY PB-0008 미기록이라 보류(배포 게이트 미해소)·floating-menu-close-fix/share-list-window-fix 흡수/비노출.
- Verification: `node --check` PASS · vm 구조검증(34 releases·07-23 head 7항목·07-22 보존·스키마·누출0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).

## CHG-20260724T012954-usage-model-canonical — LLM 사용량 '모델별 비중' 중복 명칭 분점 해소
- 문제: 관리 콘솔 > 감사 > AI 운영 현황 > **LLM 사용량** 서브탭의 '모델별 비중' 도넛이 같은 논리 모델을
  여러 조각으로 분점. 원인 = `by_model` 집계가 `COALESCE(resolved_model, model)` 로 GROUP BY 하는데
  이 값에 litellm 라우팅 변형 alias(`-interactive`/`-chat`/`-root`/`-interactive-root`/`-chat-root`)·실
  모델 ID(`claude-haiku-4-5-20251001`)·edge 폴백 실모델(`gemma4:e2b`)이 섞여 한 모델이 N 세그먼트로 쪼개짐.
- 수정: `shared/model_catalog.py` 에 canonical family 함수 2종 추가(SSOT):
  `canonical_usage_model(name)`(Python) + `canonical_usage_model_sql(col)`(PG `starts_with` CASE, LIKE '%' 회피
  → 파라미터 쿼리 이스케이프 불필요). 규칙: `claude-haiku-4*`→`claude-haiku-4`, `claude-sonnet-4*`→
  `claude-sonnet-4`, `gemma*`/`edge`/`edge-fallback`/`auto`/`core`/`code`→`edge`, 그 외 원본 유지(self-surface).
- 적용: `admin_usage.py` — by_model·by_account·by_day_model GROUP BY + `_query_usage_conversations` 모델
  필터·모델 분해를 canonical 로 통일. by_model row 는 `model==resolved_model==canonical` 로 채워 프론트
  (modelKeyOf/도넛 라벨/색맵/드릴다운) **무변경** 정합. `profile.py`(개인 사용량 도넛·드릴다운 일관성)·
  `admin_console.py`(대시보드 '모델별 토큰' 위젯) 동일 적용.
- 부수: `_estimate_llm_cost_usd` 단가 조회 키를 canonical 화 — 단가표(`_LLM_PRICE_USD_PER_1M`)가 base alias
  만 등록해 변형/실ID 가 비용 $0 로 오표시되던 gap 해소(모든 app.X 호출부에 중앙 반영). edge/gemma 는
  단가 미등록 → 0(로컬 무료) 정직 유지. gemma 폴백 호출도 실 서빙 모델 기준 집계라 haiku 단가 과대계상 정정.
- 실 PG 검증(90일): 기존 7 세그먼트 → 3 실제 모델 병합 — claude-haiku-4(64,552,777 tok)·edge(30,431,975)·
  claude-sonnet-4(785,900). run_id distinct 도 canonical 그룹 단위 dedup(요청 수 과대계상 없음).
- Files: `shared/model_catalog.py`, `unit/feature-0003-agent-web-ui/src/routers/{admin_usage,profile,admin_console}.py`,
  `unit/feature-0003-agent-web-ui/tests/test_usage_conversations.py`.
- Verification: 전체 pytest 2280 passed / 2 skipped(기존 baseline) · py ast 문법 · 실 PG canonical 쿼리 실측.
- Follow-up(§8.1 기록만): `ai_ops.py`(운영 현황 task×model, line 319) 는 동일 canonical 함수로 접을 수 있으나
  별도 축(task 우선)이라 이 cycle 범위 밖 — 미해소. TASK.md 1.2MB(§5.6 hygiene 임계 초과) 아카이빙 권고.

## CHG-20260724T020632-aiops-model-canonical — '운영 현황' 서브탭 잔존 raw 모델 표기 canonical 정합(usage-model-canonical 후속)
- 배경: PR#914(usage-model-canonical)이 'LLM 사용량' 도넛·집계를 canonical family 로 통일한 뒤, 같은 감사
  화면의 '운영 현황' 서브탭(`ai_ops.py`)에 남은 마지막 raw 모델 표기 2곳을 정합화(사용자 요청 "나머지 범위 또한 실제값과 정합").
- 변경 (`ai_ops.py` 단일 파일 + test):
  1. categories 집계 쿼리(admin_ai_ops): `COALESCE(resolved_model, model)` → `canonical_usage_model_sql(...)`.
     이 집계는 taxonomy 카테고리로 fold 되어 모델 차원 미노출 + 비용은 `_estimate_llm_cost_usd`(내부 canonical)
     이라 **출력 불변**이나, 마지막 raw 모델 그룹핑을 제거해 SSOT 일관성 확보 + 향후 모델 차원 노출 시 재분점 예방.
  2. `_query_activity`(최근 활동 feed) 주 모델 배지: `"model": served` → `canonical_usage_model(served)` — 활동
     목록 배지가 도넛과 동일한 canonical 실 모델명으로 표시. **`req_model`(r[2])·`resolved_model`(r[3])은 raw 보존**
     → 상세 펼침의 '요청 alias → 서빙 모델' 라우팅(계정 분기·gemma 폴백) audit 정보 손실 없음. 비용 무변경.
- 비변경: admin.js/스키마/RBAC/엔드포인트 계약, `_estimate_llm_cost_usd`, categories 출력(calls/tokens/cost), 활동
  상세의 req→resolved 표시. `shared/model_catalog.py` 는 PR#914 에서 이미 main.
- Files: `unit/feature-0003-agent-web-ui/src/routers/ai_ops.py`, `unit/feature-0003-agent-web-ui/tests/test_ai_ops.py`.
- Verification: 전체 pytest 2287 passed / 2 skipped(기존 baseline) · py ast · 신규 test_query_activity_model_canonical_preserves_routing(폴백행 배지=edge, req/resolved raw 보존).
- 잔여: 없음 — 전 코드베이스 raw `COALESCE(resolved_model, model)` 모델 그룹핑 0건(grep 확인).

### CHG-20260724T020632 리뷰 반영 addendum (적대 리뷰 SHIP-WITH-FIXES → 3건 반영)
- **M1(MAJOR) 수정**: `static/admin.js` 활동 상세 폴백 `srvM = r.resolved_model || r.model` → `|| r.req_model`.
  배지 canonical 화로 `r.model` 이 canonical 이 되어, resolved_model=NULL + 비-canonical req_model(auto 등) 행에서
  상세가 '가짜 라우팅 화살표'(auto→edge)를 날조하던 것을 차단(상세=100% raw). Windows-browser eval 4시나리오 확증.
- **m1 정정**: categories "출력 불변" → calls/total_tokens 불변(정수 sum), cost 는 round 재결합으로 최하위 4번째
  소수(≈$0.0001) 미세 변동 가능(단일 round 라 더 정확). ai_ops.py 주석 톤다운.
- **m2 반영**: NULL-resolved+비canonical req 백엔드 테스트 추가.
- Files(정정): `src/routers/ai_ops.py`, `src/static/admin.js`, `tests/test_ai_ops.py`, `docs/test-runs.d/20260724T020632-aiops-model-canonical.md`.
- admin.js 변경으로 check #13(visual_verification_scope=always) 활성 → test-runs.d fragment(Windows-browser Run) 동반, POST-DEPLOY 라이브 PB-0008 후속.

## CHG-20260724T123600-csv-download-wiring — assistant "CSV 다운로드 가능" 답변의 실제 다운로드 배선 누락 수정 (conv-audit csv-inline-no-download, Major cross-cut)
- **증상**: 대화 '킹스레이드 배틀 로그 차원별 집계'(515c0fd9, bootstrap_admin)에서 assistant 가 결과를 인라인 ```csv``` 텍스트로 붙이고 "다운로드하실 수 있습니다"라고 안내했으나 클릭할 다운로드 대상이 전무(8메시지 중 5개). `/api/file` 엔드포인트·권한 게이트·`/shared/out` 저장은 정상 — 링크 주입 책임이 LLM 즉흥에 의존.
- **근본원인**: 답변→링크 후처리기 `agent_core._collapse_large_tables` 가 Markdown 표(`|...|`)만 인식, ```csv``` fenced 블록은 blind spot. 모델이 (툴 가이던스 "전체 표를 삽입하지 말고"를) csv 블록으로 해석 → 링크 미주입 dead-end.
- **수정 (3계층, additive·behavior-neutral for non-csv)**:
  - `src/static/app.js`: `enhanceCsvBlockDownloads(target)` + `_csvDownloadFilename()` 추가, `renderMessageContent` assistant 분기에 배선(enhanceFilePreviewLinks 뒤). ```csv``` 블록마다 클라이언트 Blob(UTF-8 BOM) "📥 CSV 다운로드" 버튼. 바로 뒤에 `/api/file` 링크가 있으면(백엔드 절단-미리보기) 버튼 skip.
  - `src/static/share.js`: 공유 뷰 동일 미러(기존 `.share-csv-download-btn` 재사용, `renderMarkdownContent` 배선). 인라인 CSV 는 이미 가시 텍스트라 신규 노출 없음(서버 파일·step csv_paths 는 공유 redaction 유지).
  - `src/static/styles.css`: `.csv-block-actions`(flex bar)·`.csv-download-btn`(border+primary hover).
  - (cross-cut 코드 거주 feature-0002) `src/agent_core.py`: `_collapse_large_csv_blocks(answer, csv_paths)` — 대형 ```csv``` 블록을 값-토큰 매칭(`_match_csv_for_table`/`_csv_signatures` 재사용)으로 저장 CSV 찾아 헤더+미리보기 접기 + `📎 [전체 N행 미리보기](/api/file?path=)` 주입. 매칭 실패 시 원문 유지(데이터 손실 방지). 초안(3계층)·redteam 수정·redteam 최종 3경로에 `_collapse_large_tables` 뒤 체인.
  - (cross-cut 코드 거주 feature-0002) `src/modules/tools.py`: execute_sql·scratch_sql 툴 출력에 "저장 CSV 는 다운로드 버튼으로 자동 제공 — 링크 직접 생성 불필요, 전체 데이터 붙여넣기 금지" 항상(절단 무관) 안내. 기존 "CSV 다운로드 링크를 제공하세요"(모델이 URL 생성) 지시 폐기.
- **Files**: `src/static/app.js`, `src/static/share.js`, `src/static/styles.css`, `unit/feature-0002-agent-core/src/agent_core.py`, `unit/feature-0002-agent-core/src/modules/tools.py` + tests(`unit/feature-0002-agent-core/tests/test_collapse_csv_block_download.py`(신규), `unit/feature-0003-agent-web-ui/tests/verify_csv_block_download.mjs`(신규), `test_partial_evidence_grounding.py`·`test_scratch.py` 가이던스 문구 정합).
- **Verification**: 전체 pytest **2303 passed / 2 skipped**(무회귀) · jsdom 18 PASS · `node --check` app.js/share.js. check #13(visual_verification_scope=always) 활성 → test-runs.d Windows-browser fragment 동반, POST-DEPLOY 라이브 PB-0008.
- **잔여**: verify → commit → deploy(web+worker) → POST-DEPLOY PB-0008.

## CHG-20260724T133000-csv-download-wiring-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — csv-download-wiring 배포(dc316152) 후 라이브 검증 결과 기록만.
- test-runs.d/20260724T123600-csv-download-wiring.md 에 POST-DEPLOY 결과(Windows-browser PASS) append + REPORT 완결 표기 + TASK 최종 체크박스 + REVIEW REV-20260724T133000-csv-download-wiring-postverify.
- 실측: 대화 515c0fd9 인라인 ```csv``` 블록 아래 "📥 CSV 다운로드" 버튼 렌더·클릭 Blob text/csv size=2603 다운로드·콘솔 에러 0. 서빙 자산 curl 확증. 사용자 요청 해소.

## CHG-20260724T053457-metadata-review-ds-scope — 메타데이터 거버넌스 검토 큐 datasource 필터 + 자동승급 목록 정합 + 등록 시각 표시 (Major §12.3, frontend-only)
- **계기**: 사용자 신고(`/_template:entry`) — `관리 콘솔 > 지식베이스 > 메타데이터 > [용어사전/ENUM 코드사전/샘플쿼리]`: ① 출력 요소가 선택 데이터소스로 필터 안 됨(검토 큐) ② 검토 큐에서 자동 승급된 항목이 목록 내부에서 조회 안 됨 ③ 각 요소 등록 시점 알 수 없음.
- **RC**:
  - ①/② scope-decoupling — 목록(`loadMetadata`)은 상단 데이터소스 셀렉터 `adminState.metadata.scopeKey`(기본 'common')를 `?scope_key=` 로 전송하나, 검토·검수 큐 로더(`loadFeedbackQueue`/`loadSampleReview`)는 `scope_key` 미전송(=백엔드 전체 반환)이라 큐가 전 datasource 후보를 무필터 표시. 자동승급 항목은 대화 datasource scope 로 `kb_glossary`/`enum_dictionary` 에 기록되므로 목록(기본 common scope)에선 미조회 → "큐엔 보이는데 목록엔 없음". 백엔드 3개 큐 엔드포인트(glossary-feedback/enum-feedback/sample-feedback)는 이미 optional `scope_key` 지원(=프론트 결함).
  - ③ 목록 행(`_metaListRow`)이 `수정(updated_at)`만 표시하고 `created_at` 미표시. glossary/ENUM 검토 큐 행·상세, ENUM 묶음 행에도 등록 시각 없음(sample 상세엔 기존 존재). 백엔드는 세 목록·세 큐 모두 `created_at` 이미 반환.
- **수정(admin.js, additive·표시 계층 + 쿼리 파라미터, behavior-neutral for 목록 경로)**:
  - `_metaReviewScopeParam()` 신규 — `adminState.metadata.scopeKey` 기반, 특정 datasource 선택 시 URL-encoded scope_key, '공용(common)'=""(무필터=전 datasource triage, Option A: pending 배지 전-scope 집계와 정합·자동수집 후보 항상 ds-scoped 라 common 필터 시 영구 빈 큐 회피).
  - `loadFeedbackQueue`: `?status=…` 에 `&scope_key=` 추가(sp 있을 때). `loadSampleReview`: `/api/admin/sample-feedback` 에 `?scope_key=` 추가(sp 있을 때). 셀렉터 변경 핸들러(`_metaBindControls`)는 이미 review 보기에서 `loadMetadata`→큐 로더 재호출 → 즉시 재필터(배선 무변경).
  - `_metaListRow`: meta 줄 `등록 <created_at>` + 수정 시각 상이 시 `· 수정 <updated_at>` 병기(null 안전 폴백). `renderFeedbackQueue`(glossary/enum 행): tags 뒤 `등록 <created_at>` meta 줄. `_metaRenderReviewDetail`(glossary/enum else 분기): `등록 <created_at>` 태그. `_metaBuildEnumBundle`(묶음 코드 행): `등록 <created_at>` 태그. 모두 `_metaFmtDt` + `textContent`(XSS 안전).
- **§18.8 적대 리뷰 반영(SHIP-WITH-FIXES, 3건 전부)**:
  - **Finding 1 (MAJOR, backend additive)**: 큐 리스트는 scoped 됐으나 pending 배지가 unscoped(`count_glossary_feedback`/`count_enum_feedback` scope 미적용) → 특정 ds 선택 시 리스트 N건↔배지 전체 불일치. 수정: `unit/feature-0002-agent-core/src/modules/kb_glossary.py` 두 count 함수에 `scope_key=None` additive 파라미터(지정 시 `AND scope_key=%s`·`_normalize_scope_key`; 미지정=기존 전체 집계 byte-동치) + `admin_metadata.py` glossary-feedback/enum-feedback 이 `scope_filter` 전달 → 배지=scoped pending.
  - **Finding 2 (MINOR, frontend)**: `_metaPrimeReviewBadge` 가 `_metaReviewScopeParam` 로 scope 전송 + scope-change 핸들러가 변경 시 배지 재-prime(list 보기·타 서브탭 stale 해소).
  - **Finding 3 (MINOR, frontend)**: sample 큐 행·상세 날짜를 `등록 ${_metaFmtDt}` 로 통일(glossary/ENUM 와 라벨·포맷 정합).
- **무영향**: RBAC·스키마·마이그·인증 0. 백엔드 변경은 count 2함수의 additive `scope_key` 파라미터 + 엔드포인트 인자 전달뿐(미지정 시 byte-동치, 여타 호출자 없음 — admin 전용). 목록(`loadMetadata`) 경로 무변경. auto-promote write(`_insert_glossary_auto`)↔목록 read(`list_glossary_admin`) scope 정규화(`_normalize_scope_key`) 동일 — divergence 없음.
- **Files**: `src/static/admin.js`(feature-0003) · `unit/feature-0002-agent-core/src/modules/kb_glossary.py`(count 함수 scope, cross-cut) · `unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py`(엔드포인트 scope_filter 전달) · 테스트 monkeypatch 시그니처 2건(`test_metadata_glossary_autoreg.py`·`test_metadata_enum_feedback.py`).
- **Verification**: `node --check`(ESM) PASS · `verify_metadata_list_detail.mjs` baseline 대조 신규 회귀 0(26 PASS/3 FAIL·[D] crash 는 pre-existing 하니스 노후화, clean main 동일) · `py_compile`(kb_glossary/admin_metadata) · pytest **116 PASS**(feature-0003 metadata glossary-autoreg/enum-feedback/sample-curation 44 + feature-0002 glossary/enum 72) · §18.8 적대 리뷰(SUBAGENT, SHIP-WITH-FIXES→3건 반영). 정적 자산 web 이미지 baked → 라이브 PB-0008 = POST-DEPLOY(visual_verification_scope=always).
- **잔여**: verify-completion → commit → PR → merge → deploy-web → POST-DEPLOY PB-0008.

## CHG-20260724T053457-metadata-review-ds-scope-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — metadata-review-ds-scope(PR #931·main 2b22b5ff) 배포 후 라이브 검증 결과 기록만.
- test-runs.d/20260724T053457-metadata-review-ds-scope.md 에 POST-DEPLOY 결과(Windows-browser PASS) append + REPORT 완결 + TASK 최종 체크박스 + REVIEW REV-20260724T053457-metadata-review-ds-scope-postverify.
- 실측(실 Windows Chrome, https://localhost/admin): 검토 큐 공용 96건→mysql-kr-an1-auth 16건 필터·배지 96→16 정합(MAJOR Finding 1)·목록 84건 중 82 자동등록 가시(Fix 2)·전 행 `등록 <시각>`(Fix 3)·pageerror 0. 사용자 3결함 전부 해소 확인.
## CHG-20260724T181106-brandnew-script-attachment — assistant 신규 스크립트 첨부 전달 경로 (Major §12.3)
- **What**: source 없이 새로 생성한 스크립트/쿼리를 다운로드 첨부(root 첨부)로 전달하는 `attachment-new` 경로 신설. 기존 편집 경로(source_attachment_id 필수)와 별개.
- **Why(RC)**: FR-brandnew-script-attachment-delivery-gap — 첨부 생성 경로가 기존 첨부 편집만 지원해 "생성한 스크립트를 첨부로" 요청 시 assistant 거부(대화 …f1c535ec msg 1384). 재발경로=capability gap.
- **Files(feature-0003)**: `src/routers/_conv_store.py`(`_attachment_block_spans` 공통 헬퍼 리팩터 + `_attachment_new_block_spans`·`_parse_attachment_new_blocks`·`_materialize_assistant_attachment_new`), `src/routers/conversations.py`(ask 배선 + `_strip_attachment_new_blocks`), `src/app.py`(allowlist 상수 + import), `src/static/app.js`(배지 생성/수정 구분 + new_attachments 토스트).
- **Files(feature-0002 cross-ref)**: `src/agent_core.py` — CHG-20260724T181106-attach-new-directive(`_ATTACHMENT_NEW_DELIVERY_DIRECTIVE` 주입 + base 섹션 + inline 예외).
- **보안**: 확장자 allowlist(sql/txt/csv/md/markdown/json/yaml/yml/xml/log, 그 외→.txt), account/conv scope(IDOR 0), 크기 1MB·개수 캡 편집과 합산(remaining_count), **업로드 RBAC 게이트**(§18.8 MAJOR: `conversation.attachment.upload.own/any`). 보안 회귀 0.
- **Verification**: pytest 2369 PASS(신규 27) · py_compile 4파일 · node --check app.js · §18.8 AGENT-TEAM(security+backend) MAJOR/MINOR 전부 반영. 정적 자산 baked → 라이브 PB-0008 = POST-DEPLOY.
- **잔여**: verify-completion → commit → PR/deploy(별도 confirm) → POST-DEPLOY PB-0008.
## CHG-20260724T180649-share-point-rail-bars (공유링크 뷰 대화 뱃지 막대화 + 클릭 위치 비례, Minor §12.3, frontend-only 표시전용)
- Files: `unit/feature-0003-agent-web-ui/src/static/{share.js,share.css}`.
- A(막대화): `layoutSharePointRail` top%+height%(범위 비례) + CSS 점→막대. B(클릭 비례): 클릭 핸들러가 막대 내 y 비율 → 신설 `scrollShareMessageToRatio`(window.scrollTo EaseOutExpo). 메인 뷰(app.js scrollMessagePointToRatio·layoutMessagePointRail) 동형 이식 — 공유는 window/문서 좌표.
- `scrollShareMessageIntoCenter` 유지(항상 중앙 — 재사용 대비, dead 아님으로 보존). 백엔드·RBAC·스키마 무영향.
- 검증: `node --check` PASS. POST-DEPLOY PB-0008 예정.
## CHG-20260724T085937-sonnet-reasoning-budget-guide — 관리 콘솔 '모델별 추론 예산'의 adaptive(Sonnet 5) 죽은 budget 슬라이더 제거 + guide-note 전환 (Minor §12.3, cross-feature: 정본 feature-0003+shared, tests feature-0002)
> 계기(사용자): "추론 수준이 claude-code 내부 effort 를 따르면 `관리콘솔 > 설정 > 모델별 추론 예산`의 sonnet 구성을 제거하거나 가이드만 남긴 상태로 전환 검토". 확인 결과 adaptive(Sonnet 5)는 추론 강도가 output_config.effort(=Anthropic/Claude Code 내부 effort: 낮음→low·일반→기본 high·높음→high·매우높음→max)로 제어되고, `_call_llm` adaptive 분기는 reasoning_budget/model_thinking_budget override 를 **조회조차 안 함** → 해당 섹션의 sonnet budget_tokens 슬라이더 ②③은 저장해도 무효과인 죽은 컨트롤(이전 이연 H5). 사용자 선택 = "가이드 노트 전환".
- Changes(shared `shared/runtime_settings.py`): `_budget_thinking_models()`(= `_thinking_models()` 중 `model_thinking_style != "adaptive"`) + `_adaptive_thinking_models()` 신설. `_reasoning_budget_specs()`·`_model_budget_specs()` 가 `_budget_thinking_models()` 순회로 전환 → adaptive 모델은 ②③ 스펙 **미생성**(registry→API→UI 로 죽은 슬라이더 미노출). `agent_max_output` 스펙(①)은 `_thinking_models()` 전체 유지(adaptive 도 live max_tokens). `serialize_registry` 에 `adaptive_models: [...]` 추가(UI guide-note 대상 표면화).
- Changes(feature-0003 `src/static/admin.js` `renderModelThinkingBudgets`): `data.adaptive_models` set 로드. 모델 카드가 adaptive 면 ②(추론 강도별 예산)·③(일반 기본 budget) 슬라이더 대신 **guide-note**("adaptive thinking — 추론 강도는 대화 화면의 추론 강도 선택기가 effort 로 제어, 모델별 budget 미적용, 라운드당 출력만 유효") 렌더. budget 계열(haiku)은 기존 ②③ 그대로. ①(라운드당 출력)은 전 모델 유지. 가이드는 기존 CSS 클래스(`rs-subgroup-title`·`rs-readonly-note`) 재사용 — **신규 CSS 없음**(cache-buster 표면 admin.js 만).
- Behavior 불변: 실제 LLM 호출은 무변경(adaptive 는 이미 budget 미조회, effort 만 사용). 죽은 override 가 DB 에 있어도 무효(serializer 는 override 없는 spec 만 순회 — orphan override 는 live 미반영). agent_max_output(①)·haiku budget·effort 매핑·RBAC·마이그레이션 0.
- Tests: feature-0002 `test_runtime_settings.py`(sonnet budget 스펙 부재·override 항상 None·haiku clamp 62976·reasoning_budgets haiku-only 3행·adaptive_models 표면화), feature-0003 `test_runtime_settings_api.py`(sonnet 예산 키 PUT 400·adaptive_models 페이로드·agent_max_output sonnet 유지). 전체 pytest(0002+0003) RC=0.
- Verification: 배포 후 PB-0008 — 관리 콘솔 '모델별 추론 예산'에서 sonnet 카드가 ①+guide-note(②③ 슬라이더 없음), haiku 카드는 ①②③ 그대로.
- Rollback: `_reasoning_budget_specs`/`_model_budget_specs` 를 `_thinking_models()` 순회로 복원 + admin.js guide 분기 제거(죽은 슬라이더 재노출).
- Cross-ref: shared/feature-0002 MODIFY 동일 slug · REVIEW-20260724T085937-sonnet-reasoning-budget-guide · model_catalog.effort_for_reasoning_level/model_thinking_style · 선행 CHG-20260707T130000-reasoning-budgets · [[project-sonnet5-oauth-frontier-identity-gate]] H5 이연 해소 · ANCHOR 0003 무충돌.
## CHG-20260724T085937-sonnet-reasoning-budget-guide-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- Date: 2026-07-24. main 8f7b148f 배포(web+worker 재빌드) 후 실 Windows Chrome + https://localhost/admin PB-0008 **PASS**: sonnet 카드=①+guide-note(②③ 슬라이더 부재), haiku 카드=①②③, 라이브 API `adaptive_models=["claude-sonnet-4"]`(budget/reasoning 는 haiku만), 콘솔 에러 0. test-runs.d fragment 결과 기입.
- Cross-ref: CHG-20260724T085937-sonnet-reasoning-budget-guide(정본) · test-runs.d/20260724T085937-sonnet-reasoning-budget-guide.md.
## CHG-20260724T1830-share-point-rail-bars-postverify (POST-DEPLOY 공유링크 라이브 검증, 비-정책 doc-only)
- POST-DEPLOY PB-0008 공유링크 라이브 PASS(배포본 c1358190): 공유 뷰 rail 14 뱃지 막대(범위 비례)·클릭 위치 비례(상단 62/하단 1551). 메인 뷰와 동일 막대 형식. 사용자 요구 실증. 코드 0(스크린샷 evidence 추가).
- Files: `docs/test-runs.d/20260724T180649-share-point-rail-bars.md`, `docs/test-runs.d/evidence/share-rail-bars-live.png`, `docs/TASK.md`, `docs/MODIFY.md`, `docs/REVIEW.md`.
## CHG-20260724T180458-sql-md-highlight — assistant markdown 답변 ```sql``` 코드블록 구문 하이라이트 (Minor §12.3, frontend-only)
- **요청(사용자, /_template:entry arg-given)**: assistant 가 md 로 쿼리를 전달할 때 SQL 하이라이트가 적용된 상태로 전달하도록 구성 (현재 plaintext 로 렌더되어 가독성 저하).
- **원인**: 렌더 파이프라인(`markdownToHtml`=`marked.parse`→`enhance*Blocks`→`DOMPurify.sanitize`)에 syntax highlighter(highlight.js/prism) 부재 → ```sql``` 블록이 `<pre><code class="language-sql">` 로만 렌더돼 색 없는 monospace(plaintext) 로 보임.
- **변경**: 경량 SQL 토크나이저 `enhanceSqlBlocks(html)` 신설(외부 vendor 무추가) — 기존 `enhanceDiffBlocks` 패턴 정합. comment/string/number/keyword/type/function(`(`휴리스틱)/variable 을 `<span class="sql-tok-*">` 로 감싸고(토큰 텍스트는 `textContent` 로만 주입 → XSS 무첨가·DOMPurify 통과), lang 필터(sql/mysql/tsql/postgresql 등)로 diff/mermaid/attachment 와 disjoint.
- **Files**: `src/static/app.js`(`enhanceSqlBlocks`/`highlightSqlInto`+`SQL_HL_LANGS/KEYWORDS/TYPES`, `markdownToHtml` 체인 배선) · `src/static/share.js`(공유 뷰 로컬 미러 + `renderMarkdownContent` 체인 배선 — diff/attachment 헬퍼와 동일하게 share 번들 로컬 복제) · `src/static/styles.css`(`.message-content pre.sql-block .sql-tok-*` Tokyo Night 팔레트 + 사용자 말풍선 sql-block 다크 배경 고정) · `src/static/share.css`(`.share-message-content pre.sql-block .sql-tok-*`).
- **Verification**: headless chromium(chromium-1208 via playwright) 실 vendor(marked+DOMPurify) 파이프라인 **23/23 PASS**(토큰화·텍스트 무손실·DOMPurify span/class 보존·XSS 라이브 DOM 무력화·비-SQL 블록 disjoint·getComputedStyle 색 실측) · `node --check` app.js·share.js PASS · 시각증거 `docs/evidence/sql-md-highlight-20260724.png`. 정적 자산 web 이미지 baked → 라이브 PB-0008 = POST-DEPLOY(visual_verification_scope: always).
- **잔여**: verify-completion → commit → PR → merge → deploy-web → POST-DEPLOY PB-0008(Windows-browser).

## CHG-20260724T184500-sql-md-highlight-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — sql-md-highlight(PR #946·main 0313b135) 배포 후 라이브 검증 결과 기록만.
- test-runs.d/20260724T180458-sql-md-highlight.md 에 POST-DEPLOY 결과(Windows-browser PASS) append + REPORT 완결 + TASK 최종 체크박스 + REVIEW REV-20260724T184500-sql-md-highlight-postverify(§12.2 deploy 근거 포함) + evidence/pb0008-sql-highlight-live-20260724.png.
- 실측(실 Windows Chrome/150, https://localhost/ bootstrap_admin): 배포본 markdownToHtml → sql-tok 26토큰·Tokyo Night 색 정확·텍스트 무손실·script 0. 사용자 요청 라이브 해소 확인.

## CHG-20260727T010501-doc-sync-rn-0727 (TASK-20260727T010501-doc-sync-rn-0727 — 07-24 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경: `static/release-notes-data.js` releases head 에 "2026-07-24" 블록 prepend(8항목 improved/work 4·fixed/work 2·improved/admin 1·fixed/admin 1) + generated 2026-07-23→2026-07-24. 렌더 로직·백엔드·스키마·RBAC·엔드포인트 0.
- cache-buster: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py`(Dockerfile:39) + deploy-web.sh `asset_stamp_verify`(:788) 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침). wrapper 헤더의 수기 bump 지시는 07-12 이전 regime → 부적용(현행 코드로 재검증).
- 근거 정본: owning POST-DEPLOY 커밋(sql 35d6453f·csv 8bf643e0·reanswer 28ec78b3·newfolder f697eddf·share-scroll 5c9d5bf2·share-rail 6290ae1e·metadata-review c7e928c8·graph-emoji 791d5761) + git log 29ef0baf..HEAD.
- 제외: conv-menu-order/attachment-new(POST-DEPLOY 부재)·sonnet-reasoning-budget-guide(모델 튜닝 노브)·feature-0025(운영자 노브+PB-0008 미검증)·feature-0007(모델 라우팅)·feature-0021(내부)·feature-0023(개발자 API)·model-canonical/convaudit(내부).
- Verification: `node --check` PASS · vm 구조검증(releases +1·2026-07-24 head 8항목·2026-07-23 보존·스키마·누출0).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).
## CHG-20260727T105326-web-postprocess-gate — 첨부 후처리 web 게이팅(증거 기반) + worker 결과 전달 (Major §12.3, cross-ref feature-0002 primary)
- **What**: 첨부 후처리 소유자가 ask-worker 로 이전됨에 따라(primary CHG-20260727T105326-worker-attachment-postprocess) web `/api/ask` 의 후처리 4곳(materialize 2 + strip 2)을 **증거 기반 게이트**(`_raw_block_left`: 저장 답변에 블록이 남아 있을 때만 수행)로 감싸고, worker 가 만든 첨부 목록을 응답으로 forwarding. `_update_assistant_message_content` 는 성공 여부 bool 반환(§18.8 MINOR).
- **Why**: (a) worker 모드에서 web 이 빈 목록으로 strip 하면 블록만 지워 저장돼 첨부가 영영 생성되지 않고 본문 소실(§18.8 BLOCKER) (b) 모드-only 게이팅은 혼합 버전 배포 창에서 같은 결과(§18.8 MAJOR) → 증거 기반이면 정상 경로 no-op·비정상 경로 self-heal.
- **Files**: `src/routers/conversations.py`, `src/routers/_conv_store.py`(`_build_worker_agent_result` 첨부 키).
- **Verification**: pytest 2384 PASS(web 게이팅 계약 테스트 포함) · §18.8 2라운드. **배포는 워커 포함 전체 스코프**(`--web-only` 금지).
## CHG-20260727T102027-sql-diff-highlight — ```diff``` 코드블록 내 SQL 구문 하이라이트 (Minor §12.3, frontend-only, sql-md-highlight 후속)
- **요청(사용자, /_template:entry arg-given)**: "diff 구문을 나타내는 부분에서도 SQL 하이라이트가 적용되도록 구성해주세요."
- **원인**: 직전 sql-md-highlight 는 ```sql 블록만 처리. `enhanceDiffBlocks` 는 각 diff 라인 코드를 plain textContent 로만 넣어 diff 내 SQL 이 색 구분 안 됨(+/-/context 색만).
- **변경**: ① SQL 토크나이저 코어를 `sqlTokenizeToFragment(text)→DocumentFragment` 로 추출(```sql·diff 공용), `highlightSqlInto` 는 wrapper. ② `looksLikeSql(text)` 게이트(verb 핵심 DML/DDL ∧ clause SQL 구조 키워드, \b 경계로 camelCase 오탐 억제) — SQL diff 에만 적용해 비-SQL 파일 diff 오색칠 방지. ③ `enhanceDiffBlocks`: sqlMode 면 diff 라인 코드를 `sqlTokenizeToFragment` 로 토큰화(textContent-only, XSS 무첨가) + `pre.diff-sql` 마킹. add/del 은 배경 tint·좌측 border·gutter 마커로 유지, 라인 평문색은 기본색(토큰이 syntax색 — GitHub 식). 비-SQL diff 는 기존 그대로.
- **Files**: `src/static/app.js`(sqlTokenizeToFragment/highlightSqlInto/looksLikeSql/enhanceDiffBlocks) · `src/static/share.js`(동일 로컬 미러) · `src/static/styles.css`(`.sql-tok-*` 셀렉터 일반화 `pre.sql-block`→`.message-content .sql-tok-*` + `.diff-block.diff-sql .diff-line { color:#c0caf5 }`) · `src/static/share.css`(동일, `--share-code-fg`).
- **Verification**: headless chromium(chromium-1208, 실 vendor) **21/21 PASS**(회귀·SQL diff 하이라이트·add/del 보존·평문 기본색·배경 tint·텍스트 무손실·비-SQL diff 무영향·게이트 오탐억제·XSS 무력화) · `node --check` · §18.8 [SUBAGENT] 적대 패널 · 시각증거 evidence/sql-diff-highlight-20260727.png. 정적 자산 web baked → 라이브 PB-0008 = POST-DEPLOY(visual_verification_scope: always).
- **잔여**: verify-completion → commit → PR → merge → deploy-web-only → POST-DEPLOY PB-0008.

## CHG-20260727T110000-sql-diff-highlight-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — sql-diff-highlight(PR #948·main 8d69490c) 배포 후 라이브 검증 결과 기록만.
- test-runs.d/20260727T102027-sql-diff-highlight.md POST-DEPLOY 결과(Windows-browser PASS) + REPORT 완결 + TASK 최종 체크박스 + REVIEW REV-20260727T110000-...(§12.2 deploy 근거) + evidence/pb0008-sql-diff-live-20260727.png.
- 실측(실 Windows Chrome/150, https://localhost/ bootstrap_admin): 배포본 SQL diff → diff-sql·sql-tok 9·Tokyo Night 색 정확·hunk 미토큰화·add/del 구분·script 0. 사용자 요청 라이브 해소.

## CHG-20260727T113640-model-persist — 대화별 "마지막 요청 모델" 보존 + '+ 새 대화'는 haiku 유지 (Minor §12.3, web/UI + backend additive)
- **요청(사용자, /_template:entry arg-given)**: "대화 중 assistant 에게 마지막으로 요청했던 모델을 기준으로, 새로고침이나 다른 대화에서 돌아왔을 때 그 선택을 보존. 다만 '+ 새 대화' 로 선택되는 모델은 haiku 그대로."
- **원인**: `state.selectedModel` 이 메모리 전용 전역이라 ① 새로고침 시 소실(기본값 복귀) ② 대화를 바꿔도 전역값이 남아 직전 대화 모델이 다른 대화로 누출 ③ 선택 후 '+ 새 대화' 를 눌러도 그대로 이어져 "새 대화는 haiku" 계약 파손. 추론 강도는 이미 대화별 KV 영속 + `/api/history` hydration 이 있었으나 모델엔 대응 경로 부재.
- **변경**:
  - `src/routers/conversations.py`: `_model_kv_key(account)` 신설(키 = `model:<account_id>` — 그룹 대화 계정별 격리). `ask()` 가 `model_explicit`(클라이언트 명시 여부) 일 때만 KV 저장하되 **세션 기본값과 같으면 빈 값으로 해제**(기본값 이탈만 저장 → 이후 기본 모델 상향이 기존 대화에 반영됨). `history()` 가 저장값을 payload `model` 로 반환(`_is_safe_model_name`+`_is_allowed_api_model` 재검증, `_display_window == "DENY"` 면 미반환).
  - `src/static/app.js`: `loadHistory` 비-append 로드에서 `payload.model` hydration(+`_updateComposerModelLabel`/`_renderComposerModelMenu`). `_modelHydrationShouldSkip(state, convId)`(미전송 선택 보존 판정)·`_resetComposerModelSelection(state)`(컨텍스트 이탈 리셋) 순수 함수 2종 신설. 리셋 호출 4곳 — `beginPendingConversation`·`selectConversation`(전환 즉시, 대기 창 오귀속 차단)·`loadHistory` 활성대화없음 분기·`handleLogout`. 모델 선택 핸들러가 `_modelPickedAt`/`_modelPickedForConvId` 기록. pending 대화 entry 에 요청 모델 캡처 + `_switchToPendingConversationContext` 복원.
  - `src/static/index.html`: composer 모델 라벨 초기 텍스트 하드코딩 `claude-sonnet-4` → 중립 placeholder(카탈로그 로드 실패 시 실제 사용 모델과 다른 값 노출 방지).
- **의도적 비대칭**: 추론 강도와 달리 모델은 localStorage 미러를 두지 않는다 — 미러가 있으면 새 대화가 직전 모델을 상속해 사용자 요구를 깬다. `verify_model_persist.mjs` S3/S3b 가 이 비대칭을 고정(대조군 포함).
- **Files**: `src/routers/conversations.py`, `src/static/app.js`, `src/static/index.html`, `tests/test_model_persist.py`(신규), `tests/verify_model_persist.mjs`(신규), `docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260727T113640-model-persist.md`.
- **2R 적대 리뷰 반영(추가 변경)**: `loadHistory` 랜딩 분기 리셋을 미전송-선택 가드로 감쌈(B-B 자체 회귀) · `_shouldSendModelField` 신설 + `askBody.model` 조건부 동봉 + `_modelHydratedForConvId` 추적 + `moveConversationToFolder` 에 `loadHistory()` 추가(C-A clobber 차단) · `_composerCurrentModel` 최종 fallback `claude-sonnet-4`→`claude-haiku-4`(C-B) · 모델 메뉴 재렌더를 열린 상태로 한정(C-C) · `_model_kv_key` 식별불가 시 fail-closed 빈 키 + 저장·복원 skip(C-D).
- **Verification**: `test_model_persist.py` 14 PASS · `verify_model_persist.mjs` 32 PASS · `node --check`·`py_compile`·ruff PASS · `make test` 전체(신규 포함 PASS; 선존 FAIL 4건은 clean main 84f2e5ab 에서도 동일 재현 — 본 변경 무관) · §18.8 [SUBAGENT] 적대 패널 2라운드(1R BLOCK → B1/C1/C2/C3/C4 수정 후 재검증).
- **스키마/RBAC**: 0(기존 memory KV 재사용, 신규 엔드포인트 0, `/api/history` 응답 필드 1개 additive — 구 클라이언트 무시). cache-buster `?v=dev` 고정(빌드 자동주입 regime).
- **잔여**: verify-completion → commit → PR → merge → deploy-web → POST-DEPLOY PB-0008(AC-MP-1~3 라이브).

## CHG-20260727T124500-model-persist-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — model-persist(PR #953·main 8cfa00b0) 배포 후 라이브 검증 결과 기록만.
- test-runs.d/20260727T113640-model-persist.md POST-DEPLOY 결과(Windows-browser PASS) + REPORT 완결 + TASK 최종 체크박스 + REVIEW REV-20260727T124500-postverify(§12.2 deploy 근거) + evidence/pb0008-model-persist-{restore,newconv}-20260727.png.
- 실측(실 Windows Chrome/150, https://localhost/ bootstrap_admin, 배포본 8cfa00b0): AC-MP-1 재로드 복원(`payload.model=claude-sonnet-4` + 라벨 `모델: claude-sonnet`)·AC-MP-2 대화 간 격리/복귀·AC-MP-3 '+ 새 대화'=`claude-haiku`. **AC-MP-9 라이브 미검증 — 유발 트리거가 파괴적/유발 불가, 단위검증만 커버(사유 명시)**. 사용자 요청 라이브 해소.

## CHG-20260727T160748-product-picker-scroll — 제품 선택 드롭업 열림 시 선택 제품 중앙 스크롤 (Minor §12.3, frontend-only)
- **요청(사용자, /_template:entry arg-given)**: "작업화면 내 제품(Product)를 선택하는 리스트에서, 현재 선택한 product 가 중앙에 위치하도록 스크롤을 위치시켜주세요. 현재는 항상 최상단에 위치하여 기존에 선택한 제품에서 상대적인 위치를 찾기 불편합니다."
- **원인**: `openProductDropup()` 은 열 때마다 `renderProductDropupMenu()` 로 항목 DOM 을 새로 만들어 `scrollTop` 이 0(최상단)으로 시작한다. `.product-dropup-menu` 는 `max-height:320px; overflow-y:auto`(styles.css) 라 제품이 많으면 선택 항목이 스크롤 밖에 남는다 — 선택 상태를 나타내는 `is-selected`(배경+체크)는 있으나 화면에 보이지 않는다.
- **변경(`src/static/app.js`)**:
  - `scrollProductDropupToSelected(menu)` 신설 — `menu.querySelector(".product-dropup-item.is-selected")` 의 `offsetTop - (menu.clientHeight - offsetHeight)/2` 를 `[0, scrollHeight-clientHeight]` 로 clamp 해 `menu.scrollTop` 에 설정. 선택 항목·menu 부재는 조기 return(무간섭).
  - `openProductDropup()`: 메뉴 표시 후 검색 입력 `focus()` → `focus({ preventScroll: true })` 로 변경하고, 그 뒤에 중앙 정렬 호출(포커스發 브라우저 자동 스크롤과의 충돌 차단 + preventScroll 미지원 폴백 순서).
  - `renderProductChip()`: 메뉴가 열린 상태의 재렌더 분기에서 `renderProductDropupMenu()` 직후 중앙 정렬 재호출(재렌더가 scrollTop 을 0 으로 리셋하므로 복원).
- **미채택**: `scrollIntoView({block:"center"})` — 조상 스크롤 컨테이너(페이지/messageLog)까지 스크롤해 컴포저 화면이 튄다. 메뉴 자신의 `scrollTop` 만 직접 계산·설정.
- **Files**: `src/static/app.js`, `tests/headless/verify_product_dropup_scroll.py`(신규), `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260727T160748-product-picker-scroll.md`, `docs/evidence/product-dropup-scroll-{before,after}-20260727.png`(신규).
- **Verification**: `tests/headless/verify_product_dropup_scroll.py` **11/11 PASS**(실 chromium 145 레이아웃 + 실 app.js 함수 원문 추출 + 실 styles.css — offsetParent 계약·중앙 정렬 ±1px·가시성·상/하단 clamp·무선택 무간섭·짧은 목록·menu 부재 무예외·검색칸 유무 양 경로) · `node --check app.js` PASS.
- **스키마/RBAC/백엔드**: 0 (프론트 표현계층 단독, 엔드포인트·응답 shape 무변경). cache-buster `?v=dev` 고정(빌드 `inject_asset_stamp.py` content-hash 자동주입 regime — 수기 bump 불요).
- **잔여**: verify-completion → commit → PR → merge → deploy-web → POST-DEPLOY PB-0008(AC-PPSC-1~3 라이브).

## CHG-20260727T163000-product-picker-scroll-ci-fix — 헤드리스 검증 스크립트 rename (CI pytest 수집 회피, 런타임 코드 0)
- **원인**: `tests/headless/test_product_dropup_scroll.py` 가 pytest 기본 수집 패턴(`test_*.py`)에 걸려 CI(`pytest -q unit/feature-0002-agent-core/tests unit/feature-0003-agent-web-ui/tests`)가 import → 러너에 playwright 미설치라 `ModuleNotFoundError: No module named 'playwright'` collection error(exit 2)로 전체 test job FAIL. 본 cycle 이 직접 유발한 red.
- **변경**: `tests/headless/test_product_dropup_scroll.py` → **`tests/headless/verify_product_dropup_scroll.py`** (`git mv`). 프로젝트의 브라우저 검증 스크립트 관례(`tests/verify_*.mjs`)와 동일한 `verify_` prefix — pytest 수집 대상에서 벗어나고, 헤드리스 실행은 명시 호출로 유지. 스크립트 본문·문서 내 경로 참조 동반 갱신(FUNCTION/TASK/REVIEW/REPORT/test-runs.d).
- **런타임 코드 변경 0** — `src/static/app.js` 무변경(제품 드롭업 동작 불변).
- **Verification**: rename 후 `PLAYWRIGHT_BROWSERS_PATH=… python3 tests/headless/verify_product_dropup_scroll.py` **11/11 PASS** 재확인 · `ruff check` PASS · pytest 수집 패턴 확인(pyproject 에 `python_files` 커스텀 없음 → 기본 `test_*.py`/`*_test.py` 만 수집).

## CHG-20260727T165500-product-picker-scroll-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — product-picker-scroll(PR #955·main b30bb45d) 배포 후 라이브 검증 결과 기록만.
- test-runs.d/20260727T160748-product-picker-scroll.md POST-DEPLOY 결과(Windows-browser PASS) + TASK 최종 체크박스 + REPORT 완결 + REVIEW REV-20260727T165500-postverify(§12.2 deploy 근거) + evidence/pb0008-product-picker-scroll-live-20260727.png.
- 실측(실 Windows Chrome/150.0.7871.115, https://localhost/ bootstrap_admin, 배포본 b30bb45d): AC-PPSC-1 중앙 정렬(제품 17개 중 index 8 선택 → scrollTop 254 · **centerDelta 0** · fullyVisible)·AC-PPSC-2 양단 clamp(마지막 항목 선택 시 scrollTop 447 == maxScroll)·AC-PPSC-3 검색 입력 자동 포커스 유지·페이지 에러 0. 서빙 반영 확인(`typeof scrollProductDropupToSelected === "function"`, asset stamp `?v=c121d0831994`). 사용자 요청 라이브 해소.

## CHG-20260727T180036-share-bar-layout — 공유 대화 뷰: 액션 하단 바 우측 이동 + 조회수 상단 이동 + 바 hover 확장 (frontend-only)
- `src/static/share.html`: `.share-actions`(shareCopyLinkBtn·shareJoinBtn·shareForkBtn·shareLoginLink) 블록을 `<header class="share-header">` 에서 `<footer class="share-footer">` 안 `.share-footer-note` 뒤로 이동 · `#shareViewCount` 를 footer 에서 헤더 `.share-meta` 마지막 항목으로 이동(class `share-footer-stats` → `share-meta-item`). 요소 id·구성·조건부 `hidden` 불변.
- `src/static/share.css`: `.share-footer` 에 `align-items:center`·`flex-wrap:wrap`·`gap:6px 16px`·`transition(padding/background/box-shadow .18s ease)` 추가 + 세로 패딩 8→6px · `.share-footer-note{flex:1 1 auto;min-width:0}` 신설 · 액션 버튼 3종 + `.share-copy-link-btn` 기본 규격 축소(`padding:2px 10px`·`0.75rem`·`line-height:1.35`·`white-space:nowrap`) + 확장 transition · `@media (hover:hover)` 에 `.share-footer:hover, .share-footer:focus-within` 확장 규칙(패딩 10px·버튼 `6px 13px`/`0.8125rem`·배경 `#fff`·상단 그림자) · `@media (hover:none)` 터치 상시 확장 규격 · `prefers-reduced-motion` transition off · `.share-container` padding-bottom 유지(80px, 모바일 96px) · 반응형 600px 에서 안내문/액션 2줄 접힘 정합.
- `tests/test_share_bar_layout.py`(신규): 정적 구조 회귀 5 케이스(L1 액션 footer 소속·L2 조회수 헤더 meta 소속·L3 액션 4종 id 보존·L4 바 정렬 규칙·L5 기본 높이 유지 + hover/focus 확장 + transition + 터치/reduced-motion 분기).
- `tests/headless/verify_share_bar_layout.py`(신규): 실 share.html + 실 share.css 를 chromium 에 올려 좌표·높이 실측 8 케이스. **변경 전 기준값은 `git show main:...` 로 꺼낸 원본을 같은 방식으로 렌더해 비교**(바 높이 35.0 → 35.2px).
- 백엔드·엔드포인트·RBAC·스키마·마이그레이션·`share.js` 변경 0.

## CHG-20260727T182000-share-bar-layout-postverify (POST-DEPLOY PB-0008 라이브 실측 기록, 비-정책 doc-only)
- 코드/자산 0 — share-bar-layout(PR #958·main 486a587c) 배포 후 라이브 검증 결과 기록만.
- test-runs.d/20260727T180036-share-bar-layout.md POST-DEPLOY 결과(Windows-browser PASS) + TASK 최종 체크박스 + REPORT 완결 + REVIEW REV-20260727T182000-share-bar-layout-postverify(§12.2 deploy 근거) + evidence/pb0008-share-bar-layout-live-{default,hover,header,copied}-20260727.png 4건.
- 실측(실 Windows Chrome/150.0.7871.115, relay 브리지 `http://172.26.144.1:9223`, 로그인 상태로 `https://localhost/share/<token>` — join/fork 노출 경로까지 커버, 서빙 배포본 **66575331**(⊇ 486a587c, 검증 중 다른 cycle 이 PR #959 를 배포), asset stamp `share.css?v=9e94270c8829`): **AC-SBL-1** 액션 4종(`링크 복사`·`대화에 참여`·`내 계정에서 fork`·로그인 링크[hidden]) 이 `.share-footer` 내부·`actions.x=956 > note.x=16`·바 우측 여백 **16px**, 헤더에 `.share-actions` **0** · **AC-SBL-2** `조회 16회` 가 헤더 `.share-meta` 4번째 항목(`소유자 admin`·`범위: 대화 전체`·`제품 국내 웹 - QA`·`조회 16회`), y=96 < 바 y=801 · **AC-SBL-3** 기본 바 높이 **35px**(pre-commit 헤드리스 35.2px 와 정합, 변경 전 35.0px) · **AC-SBL-4** hover 시 **53px**(패딩 6→10px·버튼 22→32px·배경 `rgba(255,255,255,.96)`→`rgb(255,255,255)`·상단 그림자 부여), `transition: padding/background/box-shadow 0.18s` · `링크 복사` 클릭 → 텍스트 `복사됨 ✓` + class `is-copied` · 최하단(`scrollY=maxY=8303`)에서 마지막 메시지 bottom **732** < 바 top **783**(hover 시)로 미가림 · `elementFromPoint` hit-test 가 `shareCopyLinkBtn`/`shareForkBtn` 반환(바 위 요소가 클릭 가로채지 않음) · 페이지 에러/`console.error` **0**.
- **검증 위생**: 라이브 부작용 최소 — 읽기 전용 조작만 수행하고 `내 계정에서 fork`(신규 대화 생성)·`대화에 참여`(그룹 멤버십 변경) 는 **클릭하지 않고** 노출·좌표·hit-test 로만 확인했다. `링크 복사` 는 클립보드 쓰기뿐이라 클릭. 공유 링크 조회수는 열람 자체로 10→16 증가(정상 계측).

## CHG-20260727T234439-model-picker-copy (모델 선택기 중복 문자열 제거 + 설명 축약 + 한국어 어절 줄바꿈, Minor §12.3)
- Date: 2026-07-27. 사용자 지적: "모델을 선택하는 화면에서 부자연스러운 줄바꿈이 나타나 가독성이 좋지 않습니다. 겹치는 문자열을 제거하고 의미 또한 간단명료하게 축약해주세요."
- 진단(실 Windows 브라우저 실측, 배포본 870e1496): 메뉴 폭 360/desc 326px 에서 opus desc 51자가 **2줄**로 감기고, 한국어 기본 줄바꿈이 음절 사이에서 끊겨 단어 중간("작|업")에서 갈라졌다(`word-break: normal`). 또 label(`claude-opus`)·group 배지(`Claude`)·desc(`Anthropic Claude Opus`) 가 **같은 단어를 3중 반복**하고, `frontier` 가 opus·sonnet 2행에 중복됐다.
- 변경 ①(`shared/model_catalog.py`): `API_MODEL_OPTIONS` 3개 `description` 을 label·배지와 겹치지 않는 **차별점만** 담아 축약 — `최상위 성능 · 장기 추론과 복잡한 분석`(22자) / `고성능 · 품질과 속도의 균형`(16자) / `빠르고 경제적 · 기본값`(13자). 세 tier 가 나란히 보이는 UI 라 **동일 축(성능 등급 · 용도)으로 병렬** 서술해 비교 가능하게 했다.
- 변경 ②(`unit/feature-0003-agent-web-ui/src/static/app.js` `_renderComposerModelMenu`): label 이 group 명으로 시작하면 group 배지를 **조건부 생략**. 무조건 제거가 아니라 중복일 때만 — Local LLM 등 provider 가 섞이는 카탈로그에서는 label 접두가 달라 배지가 그대로 살아 구분 기능을 유지한다.
- 변경 ③(`unit/feature-0003-agent-web-ui/src/static/styles.css` `.composer-model-item-desc`): `word-break: keep-all`. 문구 단축과 **별개의 근본 가드** — 폭이 더 좁아지거나 문구가 길어져도 어절 경계에서만 끊긴다.
- 비-변경(의도): 모델 `value`·라우팅·권한·저장 대화·단가 키 전부 무변경. 표시 문자열 3개 + JS 조건 1줄 + CSS 1속성뿐.
- Verification: **PRE-COMMIT Windows-browser 실측** — BEFORE 2줄/1줄/1줄 + 배지 3개 → AFTER **전부 1줄** + 배지 0, 메뉴 높이 209→192px (test-runs.d/20260727T234439-model-picker-copy.md, evidence `docs/evidence/model-picker-copy-after-sim-20260727.png`). feature-0002+0003 전체 pytest rc=0 · `node --check` OK.
- Rollback: 3파일 revert(표시만 원복, 동작 영향 0).
- Cross-ref: REVIEW REV-20260727T234439-model-picker-copy · test-runs.d/20260727T234439-model-picker-copy.md · 선행 CHG-20260727T184425-opus5-model(본 desc 문구를 도입한 cycle).

## CHG-20260728T010301-doc-sync-rn-0728 (TASK-20260728T010301-doc-sync-rn-0728 — 07-27 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경: `static/release-notes-data.js` 기존 "2026-07-27" 블록에 3항목 append(new/work 답변 모델 'claude-opus' + improved/common 공유뷰 하단바 우측·조회수 상단 + improved/admin 관계도 상세 DB단위 접기·'…외 N건' 제거) + block summary 아울러-절 증강. generated 2026-07-27 불변. 렌더 로직·백엔드·스키마·RBAC·엔드포인트 0.
- cache-buster: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py`(Dockerfile:39) + deploy-web.sh `asset_stamp_verify`(:788) 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침). wrapper 헤더의 수기 bump 지시(index/admin `?v=<new>`)는 07-12 이전 regime → 부적용(현행 코드로 재검증, 351ed406 동일 판정).
- 날짜 관례: 07-27 배포분(block date=배포일, 351ed406=doc_sync 07-27 이 07-24 블록 생성)이라 신규 07-28 블록 아닌 기존 07-27 블록 append(same-deploy-day append 선례 85da43d9). generated=top-block date=07-27 불변.
- 근거 정본: owning POST-DEPLOY 커밋(opus5 413703b9·share-bar 486a587c/2ec5e0aa·detail-db-groups 66575331/42ee04d0) + git log 238065ff..HEAD.
- 제외: model-picker-copy(미배포)·change-reanalysis(백엔드 postverify 부재)·false-truncation(unverified-live)·feature-0026(측정 전용·사용자 가시 0).
- Verification: `node --check` PASS · vm 구조검증(releases[0] 2026-07-27 items 4→7·releases[1] 2026-07-24 보존·스키마·enum·누출0). 릴리즈노트 render 테스트(verify_release_notes.mjs)는 jsdom 미설치로 미실행(render 로직 미변경·데이터 정적검증 대체).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).

## CHG-20260728T024258-model-access-rbac (계정/역할별 LLM 모델 사용 권한 — 동적 `model.access.<value>` RBAC, **Critical §12.3**)
- Date: 2026-07-28. 사용자 요청("R2도 계정/역할 별 권한 범위를 구성해주세요"). 배경 = feature-0007 opus5-model 의 잔여 R2: Opus 도입으로 모델 tier 단가 격차가 5배(haiku $1/$5 ↔ opus $5/$25)로 벌어졌는데 카탈로그는 `conversation.ask` 보유자 전원에게 동일 노출돼 **사전 차단 수단이 없었다**(사후 관측만).
- **설계 결정 — 기존 패턴 재사용**: `product.access.<key>`(IsDynamic=1) 가 이미 "리소스별 접근 제어" 를 정확히 같은 모양으로 풀어놨다. 모델도 같은 축이라 `model.access.<value>`(GroupName='model_access') 로 붙이면 역할 편집기·계정 override 그리드·감사·pending→'모두 적용' UI 가 전부 따라온다 → **신규 테이블 0 · 마이그레이션 0 · 신규 UI 0**. 대안(WebRoles 에 AllowedModels JSON 컬럼)은 기존 권한 체계(override·상속·progressive disclosure·감사) 밖의 별 축이 되어 UI·감사·§10.7 pending 흐름을 전부 새로 만들어야 해 미채택.
- **기본 부여 = 전 역할**(사용자 결정 2026-07-28): 배포 시점 동작이 현행과 byte-동치(무회귀). 관리자가 콘솔에서 필요한 역할의 모델을 해제하는 방향.
- 변경 ①(`shared/model_catalog.py`): `MODEL_ACCESS_PERMISSION_PREFIX`/`_GROUP` 상수 + `model_permission_code(value)`/`is_model_permission_code(code)` + `__all__`. 코드 namespace 를 카탈로그 SSOT 에 둬 모델 추가 시 자동 확장(별도 매핑 테이블 없음). `shared/` 는 web_context 를 import 하지 않으므로 단방향.
- 변경 ②(`routers/_bootstrap_schema.py`): `_ensure_model_access_permissions(conn)` 신설 + fast path/slow-path catchup **2지점 호출**(제품 권한과 동형). ⚠️ **grant 는 권한 row 가 "새로 생성된 순간"에만** — `INSERT IGNORE` 의 `rowcount>0` 을 one-time 마커로 쓴다. 제품 권한(`DefaultRoleAccess=1`)은 매 부트스트랩 무조건 re-grant 하는데 그 방식이면 **관리자의 해제를 재기동/재배포가 조용히 되살려** 본 통제가 무력화된다(의도적 divergence, 테스트 G7 이 고정).
- 변경 ③(`web_context.py`): `_account_has_model_access(account, model, *, conn)` 판정 함수 + `_filter_models_for_account_access`. **fail-closed 기본**(row 등록 + 미보유 → False), **fail-open 은 좁게·시끄럽게**(권한 row 미등록/DB 오류 → 통과 + WARNING — "게이트 미설치"를 전원 차단으로 해석하면 신규 배포 첫 요청부터 전 대화 403 이 되는 더 큰 사고). `conn=None` 은 우회 차단(미보유 거부).
- 변경 ④(`web_context._account_permissions`): API 토큰(feature-0023) scope 교집합에서 `model.access.*` **면제**. scope 는 "어떤 *동작*" 축, 모델 tier 는 "계정 역할" 축 — 면제하지 않으면 이미 발급된 토큰(`Scopes='conversation.'`)이 전부 `/api/ask` 403 으로 죽고 모델 추가마다 토큰 재발급이 필요하다. 통제는 계정 권한 + 절대 denylist + ask() 게이트로 유지.
- 변경 ⑤(`routers/conversations.py` ask): `_is_allowed_api_model`(400, 카탈로그 축) 직후에 `_account_has_model_access`(**403**, 인가 축) 추가 — **단일 choke-point**. 재답변·'AI 로 고치기' 등 내부 재dispatch 는 모두 `ask()` 를 다시 타 자동 커버.
- 변경 ⑥(`routers/system.py` `/api/api-vault/options`): 인증 계정이면 `_filter_models_for_account_access` 로 카탈로그 필터(제품 목록 필터와 동형) — 표시·집행 동시 닫힘. 비인증·조회 실패는 필터 전 목록(fail-soft, 로그인 화면 프리로드 보존).
- 변경 ⑦(프론트 `admin.js`/`app.js`): `model_access` 그룹을 ORDER·LABELS·**operate section** 에 추가, app.js 는 prefix 추론(head='model')이 라벨 맵에 없어 '기타'로 떨어지므로 명시 매핑. `groupedPermissions` 의 `excludeDynamic` 을 **`group === "product_access"` 로 좁힘** — 원래 의도는 "전용 embedded UI 가 따로 렌더하는 그룹 제외"였는데 조건이 `is_dynamic` 전체라 모델 row 까지 사라졌다(product 동작은 완전 동일).
- 변경 ⑧(정책문서): `docs/CONVENTIONS.md §10.6` 화면별 section·group 키·라벨·동적 권한 절 갱신 · `docs/SECURITY.md §28` 신설(권한 모델·기본 부여·집행 경계 표·fail-open/closed 비대칭·API 토큰 상호작용·검증).
- Verification: 신규 단위 **25 PASS**(G1~G8) · feature-0002+0003 전체 pytest **rc=0** · `ruff` All passed · `node --check` OK. **POST-DEPLOY PB-0008(부여·해제 양방향) 잔여** — 사유: 권한 grid 의 모델 row 는 부트스트랩이 seed 한 동적 권한을 받아 렌더하므로 배포 前 시각검증이 성립하지 않는다(test-runs.d 에 명시).
- Rollback: 8지점 revert. 권한 row/grant 는 남지만 게이트가 사라져 현행 동작으로 복귀(무해).
- Cross-ref: REVIEW REV-20260728T024258-model-access-rbac · test-runs.d/20260728T024258-model-access-rbac.md · SECURITY §28 · CONVENTIONS §10.6 · feature-0007 REPORT §7 의 R2(본 CHG 로 해소).

## CHG-20260728T025614-model-access-seed-fix (모델 권한 seed SQL arity 수정 + 컬럼 길이 클립 + blast-radius 격리)
- Date: 2026-07-28. 선행 CHG-20260728T024258-model-access-rbac 배포(28fcd71f) 후 라이브에서 `model.access.*` 권한 row **0개** 발견 — 기능 조용한 미적용.
- 근본 원인: `_ensure_model_access_permissions` 의 `INSERT IGNORE INTO WebPermissions` 가 **placeholder 5개에 파라미터 4개**(`IsDynamic` 미바인딩) → `ProgrammingError: Not enough parameters for the SQL statement`. 라이브 로그 `[web.startup] seed catchup skipped: …` 로 확정.
- **왜 단위 테스트를 통과했나(진짜 결함)**: 테스트 더블 `_SeedCur.execute` 가 SQL 문자열만 분기하고 **arity 를 검증하지 않았다** — 실 드라이버가 하는 검사를 더블이 생략해 통과. 더블의 충실도(fidelity) 부족이 근본 gap.
- 영향 범위(실측): 예외가 `_ensure_seed_catchup` **말미**에서 발생하고 caller 가 잡아 로깅 → 같은 함수의 다른 seed 단계는 모두 선행 완료. 라이브 교차확인 — RoleId NULL 계정 0 · bootstrap_admin 존재 · 역할 8 · 권한 118 · product.access 19 · runtime_settings 스냅샷 정상. 게이트가 **fail-open(권한 row 미등록=미설치)** 로 설계돼 요청 경로는 현행 유지(403 폭주 없음) — 설계된 안전망이 실제로 작동, 손실은 기능 미적용 뿐.
- 수정 ①: `IsDynamic` 파라미터 바인딩(`1`) — arity 정합.
- 수정 ②: `Label`/`Description` **컬럼 길이 방어 클립**(VARCHAR 128/255). `_ensure_permission_catalog` 가 graph-perm-split 배포에서 실측·경고로 남긴 1406(Data too long) fragility 와 동일 축 — 모델 label 이 길어져도 seed 가 죽지 않게 선제 차단.
- 수정 ③: **호출 2지점 try/except 격리**. seeder 실패가 slow path 의 후속 단계(`_migrate_legacy_accounts_to_rbac`·`_ensure_bootstrap_admin`·`_seed_legacy_conversations`)나 catchup 함수 전체를 끌고 내려가지 않게 한다. 권한 seed 실패는 게이트 미설치로 흡수되는 **국소 사건**이어야 한다. 실패는 stderr 로 loud(조용한 skip 금지).
- 재발 가드: 테스트 더블이 `sql.count("%s") == len(params)` 를 **단정**(이 버그를 되돌리면 단위가 깨진다) + **G9 신설**(label 400자 fake 카탈로그 → Label<=128 · Description<=255 · IsDynamic==1 계약 고정).
- Verification: 단위 **26 PASS**(G1~G9) · 전체 pytest **rc=0** · ruff All passed. POST-DEPLOY: seed 성공(권한 row 3 + 전 역할 grant) 확인 + 선행 cycle 에서 이관한 **PB-0008 부여·해제 양방향** 검증.
- Rollback: 3지점 revert(단 seed 가 다시 실패 상태로 복귀).
- Cross-ref: REVIEW REV-20260728T025614-model-access-seed-fix · test-runs.d/20260728T025614-model-access-seed-fix.md · 선행 CHG-20260728T024258-model-access-rbac · SECURITY §28.

## CHG-20260728T031500-model-access-postverify (모델 권한 라이브 부여·해제 양방향 검증 종결 + 자기 잠금 경로 명문화)
- Date: 2026-07-28. 코드 변경 **0** — 배포 `8db72012` 에 대한 POST-DEPLOY 관측 기록 + 정책문서 1절 신설.
- 검증 ①(렌더·무회귀): 역할 편집기에 `모델 사용 (작업 화면) 3/3 선택` 그룹이 `제품 사용` 다음에 렌더, 3행(haiku·opus·sonnet) 전부 체크 — 사용자 결정 "전부 기본 부여" 그대로. 계정 편집기는 tri-state(`상속`/`허용`/`거부`) override + 그룹 배지 집계(`거부 1 · 상속 2`) 정상.
- 검증 ②(해제 쓰기): 역할 opus 해제 → `모두 적용` → `PATCH /api/admin/roles/2 200` → DB `model.access.claude-opus-5 7/8`, haiku·sonnet `8/8` 유지 → **해제가 대상 모델에만 적용**(그룹 붕괴 없음).
- 검증 ③(집행): 계정 override `거부` 후 `/api/api-vault/options` 에서 opus **소멸**, `POST /api/ask{model:"claude-opus-5"}` → **403** `이 모델을 사용할 권한이 없습니다…`. **대조군** 같은 계정·같은 시점 sonnet → **200** → 게이트가 모델 단위로 동작(광역 차단 아님).
- 검증 ④(재부여·원복): 역할 재체크 → `1건 적용됨` → DB `8/8` ×3 · `model_access` override **0행** · 선택기 3종 복귀. **최종 상태 = 검증 착수 전과 동일**.
- **신규 발견(코드 변경 없음, 문서화)**: TASK-0300 권한상승 가드(`본인이 보유하지 않은 권한은 설정할 수 없습니다`)가 `model.access.*` 에도 동일 적용돼 **관리자 자기 잠금 경로**가 생긴다 — 자기 계정에서 모델을 `거부` 하면 그 모델을 어떤 역할에도·자신에게도 재부여할 수 없다(`PATCH … 403`). `product.access.*` 와 동일 성질이며 **의도된 보안 동작**이라 가드는 손대지 않고, `docs/SECURITY.md §28.6` 에 운영 규칙(자기 계정 해제는 해당 모델 보유 관리자 2인 이상 환경에서만 / 통제는 역할 단위로)으로 명문화. 본 검증에서는 override 행 DELETE 로 복구 후 UI 재부여 200 확인.
- 문서: `docs/SECURITY.md §28.6` 신설 + §28.6→§28.7 번호 이동(검증 절에 G9·라이브 결과 반영) · feature-0007 `REPORT.md §7` 의 **R1·R2 해소 표기** · TASK 체크박스 4건 종결.
- Verification: 라이브 실측(win-browser PB-0008 + `repo-mysql-1` 직접 질의 + web 컨테이너 액세스 로그). 코드 무변경이라 회귀 표면 0.
- Rollback: 문서 revert (동작 영향 없음).
- Cross-ref: REVIEW REV-20260728T031500-model-access-postverify · test-runs.d/20260728T031500-model-access-pb0008.md · 선행 CHG-20260728T024258-model-access-rbac · CHG-20260728T025614-model-access-seed-fix · SECURITY §28 · feature-0007 REPORT §7.
## CHG-20260728T113819-usage-records-system (LLM 사용량 드릴다운 '사용 기록' 개편 — 시스템 사용분 편입 + 화면 이동)

TASK-20260728T113819-usage-records-system. branch `ai/claude/feature-0003-usage-records`.

- `shared/model_catalog.py`
  - `TASK_TAXONOMY`: 라이브 존재·미등록이던 4 task 편입 — `redteam`(답변 적대 검증) ·
    `enum_suggest`(ENUM 코드 후보) · `cluster_label`(콘텐츠 그룹 라벨) ·
    `product_classify`(제품 분류 제안). 부수효과로 ai-ops '미분류 AI 활동' Attention 에서 4건 해소.
  - 신설 `USAGE_TASK_NAV`(task → `{screen, subtab, target_kind}` SSOT) ·
    `_USAGE_NAV_DEFAULT`(미등록 task → AI 운영 현황 > 운영 현황) ·
    `USAGE_NAV_SCREEN_LABELS` · `USAGE_NAV_SUBTAB_LABELS` ·
    `usage_task_nav()` · `usage_nav_path_label()`.
- `unit/feature-0003-agent-web-ui/src/routers/admin_usage.py`
  - 신설 `_query_usage_system_records()` — 대화 목록의 **정확한 여집합**
    (`c.conversation_id IS NULL OR c.owner_account_id IS NULL`) 을 `(task, target, actor)` 로 집계.
    모델/일자 필터는 대화 목록과 동일 규칙(canonical family · 차트 버킷) → 두 목록의 합 = 막대 수치.
    `bool_or(c.conversation_id IS NOT NULL)` 로 실재 대화 여부를 함께 뽑아 **깨진 대화 링크 차단**.
  - 신설 `_usage_target_parts()` — `schema` / `schema.table` / `schema.table.column` /
    `schema.routine()` 4형식 파싱.
  - 신설 `_resolve_usage_target_scopes()` — `table_descriptions`(scope_key) ∪
    `routine_objects` ∪ `rag_objects`(datasource_key) union 으로 target→데이터소스 해소.
    객체 단위 우선, 실패 시 스키마 단위. 후보 2+ 는 **추측하지 않고** `scope_ambiguous`.
    해소 질의 실패는 fail-soft(rollback 후 포기 — 목록 자체는 보존).
  - 신설 `_usage_system_nav()` — nav 서술자(`screen/subtab/scope_key/scope_ambiguous/scope_hint/
    search/path_label`). `target_kind` 는 내부 분기 키라 응답에서 제거.
  - `admin_usage_conversations` — 응답에 `system_items`·`system_truncated` **additive**
    (기존 `items` 무변경 → 소비자 회귀 0). `(시스템)` 역할은 시스템만, 계정/일반 역할은
    시스템 제외(귀속 오도 방지). 시스템 질의 실패는 대화 목록을 깨뜨리지 않게 격리.
  - 상수 `_USAGE_SYS_LIMIT = 200`.
- `unit/feature-0003-agent-web-ui/src/app.py` — 신규 헬퍼 4종을 `app.<name>` 으로 rebind
  (`_query_usage_system_records`·`_resolve_usage_target_scopes`·`_usage_system_nav`·`_usage_target_parts`).
- `unit/feature-0003-agent-web-ui/src/static/admin.js`
  - 모달 명칭 "대화 목록" → **"사용 기록"**(제목·aria·로딩·빈상태·안내문·차트 hover 문구).
  - 대화+시스템 **통합 표**(구분 배지 열, 토큰 큰 순 병합 정렬). 시스템 행 = 작업 라벨 + 대상 객체 +
    이동 경로 안내 + 모호 표기. 주체 3분기(실재 대화 링크 / '삭제된 대화' / 워커명).
  - 신설 `applyUsageNav()` · `_usageResolveScopeKey()` · `_usageActorLabel()` —
    데이터소스 스코프 → 탭 전환 → 서브탭 → 검색어 주입. 미지 screen/subtab 은 fail-soft.
  - `(시스템)` 계정 막대 클릭이 `role="(시스템)"` 으로 모달을 열도록 복구(종전 early-return 무동작).
- `unit/feature-0003-agent-web-ui/src/static/styles.css` — `.usage-rec-*` 토큰 신설.
  모달 **반응형** `width: min(1240px, 96vw)` + `body max-height: min(74vh, 820px)`.
  부수 열 `width:1%`+nowrap 으로 본문 열이 잔여 폭 흡수(과도 줄바꿈 해소).
  대상 식별자 `word-break: break-all` → `overflow-wrap: anywhere`(단어 중간 절단 해소).
  보조문구는 `--text-muted`(대비 4.12, AA 미달) → `--text-2`(7.11).
- 테스트 `unit/feature-0003-agent-web-ui/tests/test_usage_records_system.py` 신규(14 케이스) ·
  `test_usage_conversations.py::test_a2_system_role_empty` 갱신(의도적 동작 변경 — 대화는 여전히 빈
  목록이되 `system_items` 가 채워짐).

검증: 단위 2,591 passed / 2 skipped · ruff clean · 라이브 SQL 여집합 정합(897+14,476=15,373=전체) ·
PB-0008 라이브(잔여 2건 POST-DEPLOY). 마이그레이션 없음 · 신규 RBAC 없음 · 스키마 변경 없음.

## CHG-20260728T115900-usage-records-postverify ('사용 기록' 본문 열 폭 붕괴 수정 + POST-DEPLOY 완결)

TASK-20260728T115900-usage-records-postverify. branch `ai/claude/feature-0003-usage-records-postverify`.

- `unit/feature-0003-agent-web-ui/src/static/styles.css`
  - `.usage-conv-modal .usage-conv-table { width: 100%; max-width: none; }` 신설 —
    공용 `.admin-usage-table` 의 `max-width: 640px` 를 admin 사용 기록 모달에 한해 해제.
    이 상한 때문에 auto table-layout 이 테이블을 **min-content 로 수축**시켜, 모달을 1240px 로
    넓혀도 테이블은 763px 에 머물고 본문 열이 239px 로 붕괴했다(사용자 보고 '과도한 줄바꿈'의 진범).
  - 본문 열 `width: auto` → **`width: 100%`** (auto table-layout 표준 idiom — 부수 열 `width:1%` 와
    짝을 이뤄 잔여 폭을 본문 열이 흡수).
- 코드/백엔드/테스트 변경 없음(frontend CSS 2줄). RBAC·스키마·마이그레이션 0.

검증(배포본 `6d7fe391` 라이브 실측): 테이블 763px → **1144px**(래퍼 full), 본문 열 239px →
**620px**, 단일 행 15/20 → **18/20**(잔여 2행은 시스템 행의 2줄 구조 = 의도), 가로 클리핑 없음.
주체 열 3분기도 동일 세션에서 확정(삭제된 대화 5행 · 소유자 없는 대화 링크 1건 · raw id 0건).
## CHG-20260728T113000-graph-noise-reduction — 그래프 뷰 시각 노이즈 제거 (설명문 → hover 툴팁 · 빈 커밋 바 숨김)
- Date: 2026-07-28 · Session: `ai/claude/feature-0003-graph-noise-reduction` · REQ-20260728-graph-noise-reduction
- 트리거: 사용자 요청 + 스크린샷 3곳 지목 — "그래프 뷰에서 시각적으로 noisy 한 부분 제거. 한 번 인지하면 더 확인하지 않아도 되거나 쓰면서 자연히 이해하는 설명은 최대한 제거, 혹은 hover 툴팁으로 전환."
- `src/static/graph/graph-ctxmenu.js`
  - **신설** `_metaSecHelp(tip)` — 섹션 제목 옆 ⓘ hover 툴팁 마커(`.amgr-sec-help`, `tabindex=0`+`aria-label` 로 키보드·스크린리더 동등 접근, `&<>"` 이스케이프).
  - 상시 문단 `<p class="admin-meta-detail-note">` **3건 제거** → `<h4>` 의 ⓘ 로 이관: 컬럼 섹션(장문 3문장) · 컬럼 상세의 관계 섹션 · 사용하는 함수·프로시저 섹션(장문 4문장).
  - `_metaGraphRenderDetailEmpty` — 2문단 → 1줄(`노드를 클릭하면 상세가 여기에 표시됩니다.`).
  - `_metaDbGrpTruncNotice` — 4줄 경고 → `⚠ 이웃 조회 상한 — 일부만 불러옴` 1줄 + 상세는 `title`.
  - 관계 상세 서두 `admin-meta-graph-desc` — 설명 3문장 제거, `참조함 N · 참조받음 M · 연관 용어 K` 수치만 + ⓘ.
  - 클러스터 상세 서두 — `이 스키마 클러스터에 속한 …` / `항목을 클릭하면 …` 제거, `테이블 N개…` 수치만 + ⓘ.
  - 제품 카테고리 상세 — 일반 케이스 문단 **완전 제거**(카드 배지·범례 탭과 중복), `미분류` 만 1줄 유지 + ⓘ; 밴드 조작 안내는 `스키마(DB) N개` h4 의 ⓘ 로.
  - AI 능동 분석 — box 는 상태만(`분석 결과 없음`), 재귀 분석 설명은 `✨ 능동 분석` 버튼 `title`, 지침 안내 span 제거 후 label/textarea `title` 로.
- `src/static/graph/graph.css` — `.amgr-sec-help` 신설(11px·muted·`cursor:help`·opacity .55→1 hover·`:focus-visible` outline), `.amgr-trunc-note` 에 `cursor:help`, `.admin-meta-ai-pop-foot` `space-between`→`flex-end`(자식이 버튼 하나가 되어 좌측으로 붙는 것 방지).
- `src/static/admin.html` — 그래프 상세 패널 empty-state 2문단 → `.admin-detail-empty` 1줄(다른 pane 컨벤션 정합).
- `src/static/styles.css` — `.admin-commit-bar:not(.has-pending) { display: none; }` **1규칙**. 관리 콘솔 전역 하단 바를 미저장 변경 0건일 때 숨긴다. `refreshPendingUI()` 가 `.has-pending` 을 붙이므로 변경 발생 시 자동 재노출 — **JS 무변경**.
- `tests/headless/test_detail_dbgroups.js` — ⑰ 블록 신설(+14 assert): `_metaSecHelp` 유닛(마커·이스케이프·키보드·빈 tip) + 본문에서 제거된 문단 7종 + 툴팁으로 보존된 정보 4종 + `admin-meta-detail-note` 잔존 1건(절단 경고) 단정. **78 PASS / 0 FAIL**.
- `tests/headless/test_detail_colsel.js` — ⑤ 를 "안내 문구 존재" → "안내가 `.amgr-sec-help` title 로 제공 + 본문 문단 부재" 로 갱신. (이 하네스는 ITEM-09 ES-module 리팩터 이후 `vm` 전체 eval 이 불가해 **main 에서도 실행 실패** — pre-existing, 본 cycle 은 단정만 정합화.)
- Verification: 헤드리스 78 PASS/0 FAIL · `node --check`(ESM) OK · **PB-0008 라이브**(실 Windows Chrome, docker cp 스테이징) — 상세 패널 `p.admin-meta-detail-note` **0건** · `h4 = ["컬럼 (2) ⓘ","사용하는 함수·프로시저 (10) · 읽기 3 · 쓰기 7 ⓘ","AI 능동 분석"]` · ⓘ 툴팁 전문 확인 · 패널 텍스트 **852→512자** · 커밋 바 `display:none`(0건) ↔ `flex`+`has-pending`(1건) **왕복 실측** · 좌하단 `변경 없음` 요약 유지.
- Rollback: 4개 static 파일 revert (데이터·API·스키마 영향 0).
- Cross-ref: REVIEW REV-20260728T113000-graph-noise-reduction · `docs/test-runs.d/20260728T113000-graph-noise-reduction.md` · FUNCTION REQ-20260728-graph-noise-reduction(AC-GNR-1~6) · 선행 REQ-20260716T114705 ③(검색 패널 설명문 간결화).

## CHG-20260728T121500-usage-records-hint-tooltip ('사용 기록' 행 2번째 줄 이동 안내 제거 → hover 툴팁)

TASK-20260728T121500-usage-records-hint-tooltip. branch `ai/claude/feature-0003-usage-records-hint`.

- `unit/feature-0003-agent-web-ui/src/static/admin.js` — 시스템 행의
  `<div class='usage-rec-sub'>…열기 →…</div>` 렌더 제거. 이동 경로·데이터소스 모호 안내는
  링크 버튼의 `title` 하나로 통합(`"<경로> 화면으로 이동[ (데이터소스 여럿 — 화면까지 이동)]"`).
  `nav.path_label` 을 미리 esc 해 두고 title 에서 다시 esc 하던 **이중 escape** 를 1회로 정리
  (툴팁에 `&gt;` 가 그대로 보이던 결함 동반 수정). `.usage-rec-target` 의 중복 `title='대상 객체'` 도 제거.
- `unit/feature-0003-agent-web-ui/src/static/styles.css` — dead rule
  `.usage-rec-sub` / `.usage-rec-goto` / `.usage-rec-note` 삭제(참조 0 확인).
- 근거: 200행 목록에서 매 행 보조문구는 밀도만 낮추고, 이동 가능 여부는 링크 스타일로 이미 드러난다.
  정직 표기(모호 시 화면까지만 이동)는 툴팁에 보존되어 손실 없음.

검증: `node --check`(ESM) PASS · web 테스트 스위트 PASS · 참조 잔재 grep 0 ·
POST-DEPLOY PB-0008. RBAC·스키마·마이그·백엔드 0.

## CHG-20260728T162844-graph-hover-flow (상세 패널 hover 강조: 방향·읽기/쓰기 관계선 특정 + 데이터 흐름 애니메이션)

TASK-20260728T162844-graph-hover-flow. branch `ai/claude/feature-0003-hover-rw-edgeflow`.

- `unit/feature-0003-agent-web-ui/src/static/graph/graph-ctxmenu.js` — 관계 행 3종
  (`relRow` 컬럼 참조 · `row` 관계 상세 · `rtRow` 루틴 사용, + 연관 용어 행)이 **모델 엣지의 실제
  `(source,target)`** 을 `data-edge-src`/`data-edge-tgt` 로, ROUTINE_USES 는 `data-rel-type`(read|write)
  까지 싣는다. 신규 `_metaHoverEdgeSpec(el, selfFallbackKey, otherKey)` 가 이 속성을 hover spec 으로
  변환하고, 속성이 없는 구 마크업은 레거시 `[self, 상대]` 쌍으로 폴백한다.
  `_metaGraphBindDetailHover` 와 관계 상세의 `bindRelRows` 가 이 헬퍼를 공용한다.
- `unit/feature-0003-agent-web-ui/src/static/graph/graph-core.js` — `_metaGraphSetHoverHighlight` 의
  `edgeKeyPairs` 항목을 **방향 객체 `{from,to,relType}`** 로 확장(레거시 배열 병존). 렌더 요소 해소
  (미렌더 시 조상 승격) 후 `{source,target,relType}` 로 렌더러에 전달 — 방향이 보존된다.
- `unit/feature-0003-agent-web-ui/src/static/graph/graph-renderer-pixi.js`
  - `PixiAdapterPure.dashPolyline(pts, dash, phase)` — 선택적 위상 인자(호 길이 단위) 추가.
    미지정 시 종전과 byte-동치. 실주기 계산은 홀수 길이 패턴의 on/off 반전을 고려(2×sum).
  - `PixiAdapterPure.flowForward(style)` — 화살표 어휘 → 데이터 흐름 방향
    (쓰기 endArrow=선언 방향 · 읽기 startArrow=역류 · 무향/양방향=선언 방향 폴백).
  - `_edgeMatchBetween(sid, tid, relType)` — **방향(1순위) > relation_type(2순위)** 순위로 관계선을
    특정하고, 역방향 등록 엣지는 `(sid→tid)` 프레임으로 정규화(곡률 부호 반전 + `startArrow`/`endArrow`
    교환). 기존 `_edgeStyleBetween(sid,tid[,relType])` 은 이것의 얇은 래퍼로 남아 §83 A10 계약 유지.
  - `setHoverHighlight` — 매칭된 **그 선**의 호 위에 헤일로(α0.16)+본선(α0.9)을 겹치고, 화살촉을
    **흐름이 도착하는 끝**에 접선 각도로 찍는다. 굵기·화살촉 크기·대시 주기/속도는 화면 픽셀 기준
    (`1/zoom`) — §85 정합(종전 model 고정 3.5px 는 줌인 리본·줌아웃 실종).
  - `_startHoverFlow`/`_stopHoverFlow` — hover 중에만 도는 rAF 로 흰 대시를 흐름 방향으로 이동
    (render-on-demand `autoStart:false` 라 자체 프레임 구동). 세대 토큰으로 선점 종료,
    `prefers-reduced-motion` 이면 rAF 없이 정적 대시.
  - `_clearHoverLayer` — 오버레이 Graphics 를 detach 가 아니라 **파기**(hover 는 행마다 발생 —
    GPU 지오메트리 누적 차단). `draw()`·`clearHoverHighlight`·`setHoverHighlight`·`destroy` 4경로 배선.
- `unit/feature-0003-agent-web-ui/tests/headless/test_graph_hover_flow.js` (신규) — 위상 대시 기하 ·
  흐름 방향 어휘 · 관계선 특정 순위 · 역방향 정규화 · 패널 행 계약 · graph-core 해소 계약 41건.

검증: 헤드리스 41 PASS(신규) · 그래프 전 스위트 **733 PASS / 0 FAIL** · `node --check`(ESM) 3모듈 PASS ·
구현 이전 어댑터 적대 대조로 두 축 회귀 재현 확인 · **PB-0008 실 Windows Chrome 150 라이브 PASS**
(§13.2.9 격리 컨테이너, 라이브 web-a/web-b 무접촉). Python 변경 0 · RBAC·스키마·마이그·백엔드·엔드포인트 0.
Cross-ref: REVIEW REV-20260728T162844-graph-hover-flow · `docs/test-runs.d/20260728T162844-graph-hover-flow.md` ·
FUNCTION REQ-20260728T162844-graph-hover-flow(AC-GHF-1~4) · 선행 REQ-20260728T114015-graph-edge-flow(§83).

## CHG-20260728T173500-routine-column-edges-postdeploy (함수/프로시저 컬럼 관계선 — POST-DEPLOY 실데이터 채움 + 라이브 재확인)

코드·자산 변경 **0**. PR #1014 머지(main `96dfdbdd`) + 무중단 롤아웃 이후의 **main 기반 서빙본**에서
실 데이터소스 데이터로 재확인하고, 실데이터를 채운 운영 절차와 결과를 기록한다.

- 실데이터 채움: `bash bin/routine-backfill.sh` (전 datasource 재-introspect + scope 별 `sync_graph`).
  `routine_objects` 의 `referenced_tables[].cols` 보유 **19 → 5,807**,
  AGE `ROUTINE_USES` 의 `ref_columns` 속성 보유 엣지 **29 → 2,725**(전체 28,126).
  배포 직후 19건은 insight-worker cadence 자연 전파분 — 워커 경로도 라이브에서 동작함을 확인.
- 라이브 재확인(PB-0008 실 Windows Chrome 150, 9 시나리오 PASS): 접힘 무변경 · 펼침 시 쓰기/읽기
  컬럼별 연결 · 미렌더 참조 컬럼의 테이블 승격(`::t::`) 혼재 · `ref_columns` 부재 무회귀 · 한 컬럼에
  읽기·쓰기 공존 · 상세 패널 `✎` 쓰기 마커 및 읽기 컬럼 병기 · 콘솔 에러 0.
- 서빙 baked 확인: `graph-core.js?v=3772f0cfa0c5` 신규 심볼(`resolveColId`·`ref_columns`·`colEdge`·
  `::c::`·`::t::`) · `graph-ctxmenu.js`(`ref_columns`·`✎`) · web `b36493a9` / 워커 `96dfdbdd`.

Cross-ref: REVIEW REV-20260728T173500-routine-column-edges-postdeploy ·
`docs/test-runs.d/20260728T173500-routine-column-edges-postdeploy.md` ·
사전 Run `docs/test-runs.d/20260728T161940-routine-column-edges.md` ·
선행 CHG(코드) `unit/feature-0016-metadata-graph/docs/MODIFY.md` 의 routine-column-edges 항목.

## CHG-20260728T161300-graph-hop-budget ('이웃 깊이' 예산 우선순위 + 절단 경고 오귀속 제거)
- 대상: `src/static/graph/graph-ctxmenu.js`(`_metaNbrTruncNotice`·`_metaNbrMeta`·`_metaNoRelHint`·`_META_REL_ETYPES` 신설 / 절단 배너를 "사용하는 함수·프로시저" 섹션 → 패널 상단 1곳으로 이동 / 상세 meta 에 `truncated_hop`·`omitted_nodes` 전달 / 확장·중심보기 상태줄에 관계없음 힌트), `src/static/graph/graph-core.js`(depth select 상태 문구를 실제 트리거로 정정), `src/static/admin.html`(depth label `title` + select `aria-label` + ❓ 도움말 항목 갱신), `src/routers/admin_metadata.py`(그래프 응답에 `truncated_hop`·`omitted_nodes` 추가). 테스트: `tests/headless/test_detail_dbgroups.js` ⑱⑲ 확장(95 PASS/0 FAIL — ⑰의 note 개수 단언을 "모든 note 가 절단 경고 클래스 동반" 으로 재표현). 신규 Run 기록 `docs/test-runs.d/20260728T161300-graph-hop-budget.md`(Environment: Windows-browser).
- 변경: REQ-20260728-graph-hop-budget / AC-HB-4·5·6. 백엔드 BFS 예산 재설계(AC-HB-1~3)는 코드가 feature-0002 `metadata_graph.py` 에 거주하며 feature-0016 MODIFY `CHG-20260728T161300-ai-claude-feature-0016-neighbor-depth-budget` 에 기록.
- 근거: 등급 Minor(표시·투영 범위 한정). 사용자 보고("1-hop 초과 모든 항목에서 절단 경고")의 정체가 **오귀속**임을 라이브 실측으로 확증 — 앵커 직결 목록은 절단되지 않았는데 그 위에 경고가 붙었다. PB-0008 실 Windows Chrome 150 에서 패널 상단 1개 배너 + 함수·프로시저 섹션 배너 0 + 목록 155건 불변을 실화면 확인(증적 4장 `artifacts/feature-0016-neighbor-depth-budget/pb0008/`).

## CHG-20260728T161300-graph-hop-budget-review (§18.8 적대검증 흡수 — 예산·절단신호·확장실적)
- 대상: `src/static/graph/graph-ctxmenu.js`(`_metaNoRelHint` 를 `expanded_hops`/`expanded_hop_edges` 실적 기반으로 교체 + 절단 시 억제 + 구 응답 폴백 / `_metaNbrTruncNotice` 에 hop-미상 분기 신설 — 완전성 미주장), `src/routers/admin_metadata.py`(응답에 `expanded_hops`·`expanded_hop_edges` 전달). 테스트: `tests/headless/test_detail_dbgroups.js` ⑳㉑ 신설 + ⑱ hop-미상 3건 = **95 → 107 PASS / 0 FAIL**.
- 변경: REQ-20260728-graph-hop-budget / **AC-HB-7·8 신설**. 백엔드(예약 예산·broken 정렬·cap+1 포화판정·graphid 정렬·hop 실적)는 코드가 feature-0002 `metadata_graph.py` 에 거주하며 feature-0016 MODIFY 에 기록.
- 근거: 등급 Minor 유지(읽기 전용 투영 범위·표시 문구). codex 적대검증 4라운드 지적 13건 중 12건 흡수 — 상세 대조표는 feature-0016 `REVIEW.md` REV-20260728T161300. 원 세션의 subagent 패널이 사용량 한도로 죽고 재개 세션에 Agent tool 제약이 있어 §18.8.2 item 1 의 제약 없는 채널(`codex review`)을 채택했다.
## CHG-20260728T191126-model-pick-early-cid (조기 cid 전환 시 모델 선택 귀속 승계 + 무음 강등 감지)
- 대상: `src/static/app.js` — `_adoptComposerModelPickToConv()` 신설(pending→early-cid 귀속 승계,
  미선택 `null` 은 비대상 / 다른 실 cid 귀속은 거부) · `_modelSelectionSilentlyDropped()` 신설(표시-집행
  불일치 감지) · 첨부 업로드 early-cid 전환부에 승계 호출(`state.pendingSentinel = null` **이전**) ·
  `sendPrompt` early-cid 전환부에 승계 호출 · `askBody.model` 미동봉 분기에 `showToast` 표면화 +
  `console.warn` 진단. 테스트: `tests/verify_model_persist.mjs` E1~E6 · W1~W4 · S9~S11 신설
  (32 → **49 PASS / 0 FAIL**). 서버 코드 무변경.
- 변경: `/_dqa:conversation_audit` 마찰 `FR-model-pick-lost-on-early-cid` 근본 봉인. 사용자 승인 범위
  A+C(AskUserQuestion 2026-07-28) · PLAN-APPROVED. TASK-20260728T1911-model-pick-early-cid.
- 근거: 등급 **Major**(§12.3 — 모델 라우팅 입력 경로 + haiku→sonnet 실행 증가라는 외부 비용 방향).
  사용자 증상 "sonnet 요청 즉시 haiku 폴백"의 정체는 **LLM 폴백이 아니라 요청에서 model 필드 누락**
  이었음을 라이브로 확증: 재현 대화 `ask_jobs.payload.model=claude-haiku-4` + `kv model:<acct>` 행 부재
  (미동봉 지문) vs `reasoning_level` 은 정상 저장(항상 전송되는 비대칭). 대조군 — 대화 확정 후 재선택한
  요청은 정상 sonnet 전송 + KV 저장. corroboration(30일) non-default 선택 확증 대화 5건 중 3건이 첫
  요청 오전송. 부수 확인: 미동봉이면 첫 전송 후 hydration 이 저장값 부재로 `selectedModel=null` 을 넣어
  **선택기 표시까지 haiku 로 되돌아간다** — 사용자가 "즉시 폴백"을 화면에서 본 기전.
  "'+ 새 대화'는 haiku 로 시작"(비용 회귀 차단) 계약은 불변 — 미선택은 승계하지 않는다(E3 고정).

Cross-ref: REVIEW `REV-20260728T191126-model-pick-early-cid` ·
마찰 원장 `docs/improvements/conversation-audit/FRICTION_LEDGER.md`
(`FR-model-pick-lost-on-early-cid`) · TEST.md 동명 케이스(PB-0008 배포 후 잔여).
## CHG-20260729T010301-doc-sync-rn-0729 (TASK-20260729T010301-doc-sync-rn-0729 — 07-28 사용자향 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경: `static/release-notes-data.js` 기존 "2026-07-28" 블록에 6항목 append(관계도 연결선 가독성·이름표 hover·역할 배지·분류 스크롤 동기화·이웃 표시 범위·'사용 기록' 드릴다운·계정/역할별 모델 사용 제한·자체 점검 후 응답 정확성) + block summary 아울러-절 증강. generated 2026-07-28 불변. 렌더 로직·백엔드·스키마·RBAC·엔드포인트 0.
- cache-buster: `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py`(Dockerfile:39) + deploy-web.sh `asset_stamp_verify`(:791) 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침). wrapper 헤더의 수기 bump 지시(index/admin `?v=<new>`)는 07-12 이전 regime → 부적용(현행 코드로 재검증, abcb7d68 동일 판정).
- 날짜 관례: 07-28 배포분(block date=배포일·델타 커밋 전부 git-date 07-28, 기존 07-28 블록은 feature 커밋 70851411 self-add)이라 신규 07-29 블록 아닌 기존 07-28 블록 append(same-deploy-day append 선례 85da43d9). generated=top-block date=07-28 불변.
- 근거 정본: owning POST-DEPLOY PB-0008 커밋(역할배지 2b9693c7·이웃깊이 0bff005e·hover확장 43efe182/29ceb823·상세hover fb253fe3·클러스터스크롤 9b16b0c0/a36c16ed/429e8c04·라벨LOD 8008402d·헤더라벨 b2f062cc·함수관계선 5a6110a9·사용기록 f3cfc809·모델권한 fcf22ceb·자체점검 6582c69b) + git log abc3e49f..HEAD.
- 제외: 성능 3 feature(0027/0028/0029 측정·내부)·conversation-api(0023 개발자향)·agent-core 내부 보안·feature-0001 시나리오·governance. held: halo 기하 비례화(개별 POST-DEPLOY 없음).
- Verification: `node --check` PASS · vm 구조검증(releases[0] 2026-07-28 items 3→9·releases[1] 07-27 7항목 보존·스키마·enum·누출0). 릴리즈노트 render 테스트(verify_release_notes.mjs)는 jsdom 미설치로 미실행(render 로직 미변경·데이터 정적검증 대체).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).

## CHG-20260729T0930-detail-panel-typo (상세 패널 목록 행 시각 위계·리듬·정렬 교정)
- 대상: `src/static/graph/graph.css`(신설 `.amgr-rtrow`/`.amgr-rtname` + `.amgr-rtcols` 명시 규칙 / `.admin-meta-graph-sec` 여백 10→16px·padding 12px / `h4` 색 `--text-2`→`--text` + `h4 .admin-meta-graph-muted{font-weight:500}` / `.amgr-dir`·`.amgr-dir-head` 리듬 / `ul.amgr-list > li{margin:0}`), `src/static/graph/graph-ctxmenu.js`(`rtRow` — 행을 단일 전폭 flex 버튼으로 통합, 주 라벨을 `.amgr-rtname` span 으로, 이름·컬럼 전문을 `title` 에 보존). 신규 테스트 `tests/headless/test_detail_panel_typo.js`(**24 PASS**, 수정 전 CSS 로는 **17 FAIL** = 반증 확인). 신규 Run `docs/test-runs.d/20260729T0930-detail-panel-typo.md`.
- 변경: REQ-20260729-detail-panel-typo / AC-DPT-1~4. 근본 원인은 **부-액션 버튼 스타일(`.amgr-link`)을 목록 행의 주 라벨로 재사용**한 것 — 라이브 실측에서 주 라벨 10.5px vs 부가정보 13px(**1.24배 역전**), 행 높이 19~38px 2종, 우측 경계 18종 톱니, `h4` 색이 본문 항목과 동일, `h4` 내 muted 가 bold 상속. 같은 패널 컬럼 섹션의 검증된 관용구(`.amgr-col-select`)로 시각 언어를 통일해 해소.
- 근거: 등급 Minor(표시 전용 — 백엔드·RBAC·스키마·엔드포인트 0). 실렌더 정량 대조(playwright chromium, 실제 패널 기하 재현 57행): 행 높이 **2종→1종(25px)** · 행 폭 **가변→295px 균일** · 우측 경계 **18종→1종** · 부가정보/주라벨 비 **1.24배→0.88배** · 말줄임 전문 보존 **이름 11/11·컬럼 11/11**. 헤드리스 그래프 전 스위트 996 PASS/0 FAIL · pytest 전 스위트 2835 passed/0 failed · ruff clean. 1차 수정이 **이름 말줄임 시 전문 보존을 빠뜨린 결함**을 신설 측정 지표(`nameTitleOk`)가 적발해 교정했고, **여백 리셋의 특이도 부수 피해**(넓은 `ul.amgr-list > li` 리셋이 `.amgr-row` 관계 카드 간격을 3px→0px 로 눌러 카드가 붙음)를 §18.8 적대검증(codex)이 적발해 `li.amgr-rtli` 한정으로 흡수했다(⑤-b 회귀 테스트 봉인). PB-0008 은 배포 후 POST-DEPLOY(JS 는 `docker cp` QA 가 stamp/모듈캐시로 오염됨).
- 흡수(§18.8 codex): 여백 리셋 대상을 `li.amgr-rtli` 로 한정 — 넓은 `ul.amgr-list > li`(특이도 0,2,2)가 `.amgr-row`(0,1,0)·`.amgr-dbgrp-allctl` 을 눌러 관계 상세 카드가 붙던 부수 피해 제거. 실렌더 대조: 기준선 3px → 1차수정 0px → 최종 3px(회귀 0).

## CHG-20260729T113000-model-pick-postdeploy (model-pick-early-cid POST-DEPLOY 라이브 실증 — 실행 코드 0줄)
- 대상: `docs/test-runs.d/20260729T1130-model-pick-postdeploy.md` 신설(Run 전문) · `docs/{TASK,REVIEW}.md`
  항목 추가 · 선행 TASK 20260728T1911 의 잔여 체크박스(PB-0008 라이브 실측) 종결 ·
  `docs/improvements/conversation-audit/FRICTION_LEDGER.md` status 전이 · `docs/LEARNINGS.md` 교훈 2건.
  **실행 코드·정적 자산 변경 0줄** — 검증 자체가 산출물.
- 변경: 선행 cycle 이 "배포 후 잔여"로 남긴 PB-0008 실측 이행. 배포본(web `StartedAt` 11:08:44 KST ·
  edge `/healthz` `git_commit=36618965` · 서빙 `app.js?v=7529ce4ce347` 에 승계·감지 4 심볼 baked)에서
  실 Windows Chrome 150 으로 [새 대화 → sonnet 선택 → 첨부 업로드 → 전송] 전 구간 계측.
  결과 **PASS** — 전송 본문 `model="claude-sonnet-4"` 동봉 · `llm_usage` id 69372
  `model=claude-sonnet-4`/`resolved_model=claude-sonnet-4-chat`(강등 0) · `kv model:1=claude-sonnet-4`
  (행 생성) · 무음 강등 경보 미발동. TASK-20260729T1130-model-pick-postdeploy.
- 근거: 등급 **Minor**(문서·증적 only). 사용자가 완료 보고 후 "이전과 동일하게 폴백"을 재보고했으나,
  라이브 대조 결과 그 재현 대화(`...2211841a`)의 첫 전송은 **10:33:48** 로 배포(**11:08:44**)보다 35분
  앞섰고 배포 후 신규 대화·첨부는 0건이었다 — 구자산 세션 경험. 같은 오전 대조군(`...a8b43197` 10:30
  첨부 5건 sonnet 정상 vs `...2211841a` 10:33 첨부 1건 haiku 강등)은 분기점이 "첨부 유무"가 아니라
  **선택→첨부 순서**임을 라이브에서 재확인해 선행 진단의 경로 특정을 강화한다. 부수 정밀화: kv 지문은
  3분기(행 부재=미동봉 / 빈 값 행=**기본값과 같은 모델의 명시 동봉** — 서버가 기본값 이탈만 저장 /
  값 행=비-기본 명시 동봉)로, 선행 기록의 "미동봉=행 부재" 서술을 오독 방지 형태로 보정했다.

Cross-ref: REVIEW `REV-20260729T113000-model-pick-postdeploy` · test-runs.d 동명 fragment ·
선행 `CHG-20260728T191126-model-pick-early-cid` · 마찰 원장 `FR-model-pick-lost-on-early-cid`
(`fixed:undeployed` → `fixed:deployed:verified`).

## CHG-20260729T140200-attach-full-scope — 대화 전체 첨부 자율 참조 + scopeAll 토글 제거

**web(feature-0003)**: `routers/_conv_store.py` 에 `_resolve_conversation_attachment_scope`
+ `_ATTACHMENT_SCOPE_COUNT_CAP=200` 신설(PG mirror 우선·MySQL 폴백, 그룹 `sender_scope` 필터,
최신본·활성 행만), `app.py` 꼬리 rebind 노출. `routers/conversations.py` ask 핸들러가 클라이언트
`attachment_ids` 를 `client_attachment_ids` 로 받고 실제 스코프는 위 헬퍼로 해소 —
동기 ingest 대기는 `_sync_ingest_ids`(이번 턴 첨부)로 한정. `static/index.html`·`app.js`·
`styles.css` 에서 scopeAll 마크업·핸들러·상태·전송 필드·CSS 제거. `routers/_audit_infra.py` 의
`attachment.scope.all` case 는 deprecated 주석 후 존치(과거 감사 기록 렌더링 정합).

**agent-core(feature-0002)**: `agent_core.py` 에 `_attachment_scope_ids` ·
`_load_scoped_attachment_rows` · `_load_attachment_bytes` · `read_attachment_content` 신설.
첨부 섹션 제목을 대화 전체 스코프로 바꾸고 "목록의 어떤 파일이든 read_attachment 로 읽을 수
있다 / 접근 불가 단정·재첨부 요구 금지" 지시 추가, 미인라인 안내를 도구 호출 안내로 교체.
`_review_attachments` 가 미인라인 첨부를 매니페스트(content_available=False)로 함께 반환.
`modules/tools.py` 에 `read_attachment` 정의·핸들러·`with_attachment_tools`·
`_DATASOURCE_FREE_TOOLS` 추가(라우팅 우회). `modules/redteam.py` 의 `build_attachment_digest`
가 본문/매니페스트를 분리하고 매니페스트가 예산을 선점, 리뷰어 지시문에 오판 금지 2줄 추가.
`_derive_step_work`/`_derive_step_reason` 에 read_attachment 라벨.

**테스트**: `test_attach_full_scope.py`(7) · `test_read_attachment_tool.py`(15) ·
`test_redteam_attachment_manifest.py`(7) 신설, `test_self_review_messages.py` 계약 갱신 + 1건 추가.
컨테이너 스위트 실패 15건은 main 과 동일한 환경성 baseline(attachment 13 · runtime_settings 2) —
신규 실패 0.

Cross-ref: DECISIONS `ADR-20260729T140200-attach-full-scope` (D16 supersede) ·
REVIEW `REV-20260729T140200-attach-full-scope` · TASK `20260729T1402-attach-full-scope`.
## CHG-20260729T152000-attach-list-delete — 첨부 목록 행 삭제(×) 추가

`static/app.js`: `_removeAttachmentPill` 의 삭제 경로를 `_deleteConversationAttachment(id,
filename)` 로 추출(성공 여부 반환) · `_loadConversationAttachmentList` 의 각 행에
`.attach-list-item-del`(×) 버튼 + 핸들러 추가. `static/styles.css`: `.attach-list-item-del`
규칙(기본 muted / hover danger / disabled) 추가. 백엔드·API·RBAC 무변경 — 기존
`DELETE /api/attachments/{id}` 재사용.

Cross-ref: TASK `20260729T1520-attach-list-delete` · REVIEW `REV-20260729T152000-attach-list-delete`.

## CHG-20260729T160000-attach-postdeploy — POST-DEPLOY 라이브 실증 기록 (doc-only)

실행 코드·정적 자산 변경 **0줄**. `docs/test-runs.d/20260729T1600-attach-postdeploy.md` 신규
(PB-0008 Windows-browser Run — 명제 8건 PASS + 미실증 2건 명시), `docs/TASK.md` 종결 섹션,
`docs/REVIEW.md` `[SKIPPED:non-policy-doc]` 1줄.

핵심 실측: `/api/ask` 에 `attachment_ids: []` 로 보낸 질의가 첨부 17번째 줄 토큰 `ZQX17` 을
정확히 답했고(참조 스코프 전환 실증), `read_attachment` 가 `{filename, start_line:33,
max_lines:3}` 로 실호출됐다(도구 실증). 목록 `×` 는 2차 배포본에서 노출·실삭제 확인.

Cross-ref: TASK `20260729T1600-attach-postdeploy` · 선행 `CHG-20260729T140200-attach-full-scope`
· `CHG-20260729T152000-attach-list-delete`.
## CHG-20260729T145500-conv-search-attach-name — 대화 검색에 첨부 파일명 축 추가 (Major §12.3)

**요청**: "서비스 내 대화를 검색하는 기능에서, 대화 내 첨부된 파일의 명칭도 검색 대상에 포함할 수
있도록 개선" (사용자, 2026-07-29).

**검색 SQL** — `routers/_conv_store.py`
- `_list_conversations_pg`(PG 라이브): 검색 WHERE 의 OR 체인에 `agent_runtime.core_attachments`
  EXISTS 추가 (`att.original_filename ILIKE %s`, `deleted_at IS NULL AND superseded_at IS NULL`).
- `_list_conversations`(MySQL 폴백): 동형으로 `WebConversationAttachments` EXISTS 추가
  (`OriginalFilename LIKE %s ESCAPE '!'`, `DeletedAt/SupersededAt IS NULL`, ConversationId COLLATE 통일).
- 두 경로 모두 `if normalized_q:` 블록 안에만 존재 — 검색어 없는 목록 조회의 쿼리 형태 무변경.

**매칭 근거 수집** — `routers/_prompt_context.py`
- `_collect_matched_attachment_names(conn, conv_ids, q, *, per_conv_cap=3)` 신설. `_collect_matched_excerpts`
  와 같은 계약(백엔드 분기·escape·fail-soft). `ROW_NUMBER() OVER (PARTITION BY conversation_id
  ORDER BY created_at DESC, id DESC)` 로 conv 당 최신 N 건. 예외 시 빈 dict.
- `app.py` 의 `routers._prompt_context` re-export 목록에 추가(패치-단일점 규약 보존).

**응답 계약** — `routers/conversations.py`
- `conversations` 검색 payload 에 `matched_attachments` 추가. body-search 활성 + items 존재 시에만
  수집(excerpt 와 동일 게이트), 개별 try/except 로 excerpt 수집과 서로 영향 없음.

**프론트** — `static/app.js` · `static/index.html` · `static/styles.css`
- `state.searchModal.matched_attachments` 캐시 추가 + 리셋 3지점(모달 닫기·초기화 버튼·빈 쿼리)
  및 더 보기 append 병합을 excerpt 와 동일하게 정합.
- `renderSearchModalResults` 에 `.search-attach-matches` / `.search-attach-chip` 렌더 —
  표시 게이트 `mine || sm.snippet_opt_in`(SECURITY §8.6), 파일명은 `_searchHighlight` 경유
  (escapeHtml → `<mark>` 강조)라 XSS 방어 유지. 전체 파일명은 `title` 속성으로 보존.
- 검색 입력 placeholder "제목 · 본문 (2자 이상)" → "제목 · 본문 · 첨부 파일명 (2자 이상)",
  빈 상태 안내 동일 취지 갱신. cache-buster 는 `?v=dev` 고정(빌드 시 content-hash 자동 주입)이라 무변경.

**정책 문서** — `docs/SECURITY.md`
- §8.2 검색 대상 필드에 첨부 원본 파일명 추가 + *비포함* 에 첨부 파일 내용 명시. 노출면 확대 0
  판정 근거(인가 경계 불변 · 이미 열람 가능 · 가시성 정합 · 매칭 근거 표면화 · 잔여 리스크) 기재.
- §8.6 에 첨부 파일명 칩의 표시 게이트 명문화.

**테스트**: `test_conv_search_attachment_name.py` 12건 신설(검색 SQL 축 S1~S4 · 수집 헬퍼 C1~C5 ·
응답 계약 E1 · 프론트 렌더 F1~F2) 전건 PASS. 컨테이너 전체 스위트 실패는 main baseline 과
대조해 **신규 실패 0**(잔여는 동일 환경성 — attachment/runtime_settings/share_redaction 축).

**스키마·마이그레이션·권한**: 없음. 신규 엔드포인트 없음.

Cross-ref: FUNCTION `REQ-20260729-conv-search-attach-name` · REVIEW
`REV-20260729T145500-conv-search-attach-name` · TASK `20260729T1455-conv-search-attach-name` ·
SECURITY §8.2·§8.6.

### CHG-20260729T145500 후속 — codex 적대 리뷰 반영 (P1 1건 + P2 4건)

세션 상위지시로 §18.8 subagent 패널 대신 `/codex review`(§18.8.1 경로 2, 사용자 확인) 수행.

**P1 인가 경계 — 첨부 축·근거를 첨부 조회 권한으로 게이팅**
- `app._search_attachment_axis(account)` 신설(app.py) — `"any"`/`"own"`/`None` 단일 판정점.
- `_conv_store._list_conversations` 가 이 값을 계산해 PG·MySQL 양 경로 검색 조립에 전달.
  `_list_conversations_pg` 는 `attachment_axis` 파라미터 신설. `"own"` 이면 첨부 EXISTS 에
  `c.owner_account_id = %s OR conversation_id IN (멤버 서브쿼리)` AND, self_id 부재면 축 제외(fail-closed).
  `None` 이면 EXISTS 자체를 붙이지 않는다(매칭 oracle 제거).
- `routers/conversations.py` 가 같은 판정으로 `matched_attachments` 수집 대상 conv_ids 를 좁힌다
  (`any`=전체 / `own`=items 의 owner_account_id==self OR is_member / `None`=수집 미호출).
- 근거: `conversation.list.any`(관리자)와 `conversation.attachment.read.any`("운영자 한정")는
  독립 권한 코드다. 목록 권한만으로 축을 켜면 첨부 조회 게이트가 우회된다.

**P2 LIKE escape — PG 경로 §8.3 복원**
- `_list_conversations_pg` 검색 절 전 축(제목·kv_topic·messages·core_messages·첨부)을
  `_escape_like_for_search` + `ILIKE %s ESCAPE '!'` 로 전환. AR-M4 PG 포팅 때 유실됐던
  SECURITY §8.3 계약 복원이며, MySQL 경로·`_collect_matched_*` 수집 헬퍼와 semantics 정합.

**P2 fail-soft 범위** — `_collect_matched_attachment_names` 의 패턴 조립·백엔드 판정·커서 생성·
결과 변환을 모두 try 로 감싸고 cursor close 를 안전화(헬퍼 경계 전체가 "실패=빈 dict").

**P2 프론트 캐시 정합** — `runSearchQuery` 의 **검색 실패 폴백**에서 `matched_attachments` 리셋이
빠져 이전 검색의 파일명 칩이 잔존할 수 있었다(보강 테스트가 적발). 리셋 4지점 전부 정합.

**P2 테스트 재작성** — 초안 12건(소스 문자열 검사)을 fake 커넥션으로 **실제 SQL·params 를 캡처**하는
실행 기반 26건으로 교체: 권한 게이트 A1~A6 · 가시성 V1~V2 · 비용 회귀 G1 · escape 리터럴화 E1~E3 ·
수집 헬퍼 C1~C6 · 엔드포인트 스코프 P1~P3 · 프론트 F1~F4 + 구조 가드.

**미해소(정직 표기)** — P2 성능(`ILIKE '%q%'` 인덱스 미사용, `max_execution_time` 은 CPU 상한 아님).
라이브 `EXPLAIN ANALYZE` 는 POST-DEPLOY. 기존 메시지 본문 축이 이미 동일 성질이라 본 변경이 새로
만든 리스크는 아니며, §8.7 FULLTEXT trigger 와 함께 재평가한다.

**정책 문서 정정** — `docs/SECURITY.md` §8.2.1 신설(권한 스코프 표 + 왜 목록 권한으로 대신할 수
없는지) · §8.6 의 프론트 칩 게이트를 "UI 정책이지 보안 경계 아님" 으로 명시.

### CHG-20260729T145500 후속 2 — codex 재검증 지적 3건 (2026-07-29 15:40)

수정본 재검토에서 P1·escape·fail-soft·캐시 리셋은 "해결됨" 확인. 신규 P2 3건 전건 수정:

- **`own` 스코프 판정을 SQL 로 이관** — `_collect_matched_attachment_names(scope_account_id=...)`
  신설. PG 는 `JOIN agent_runtime.core_conversations c` + `c.owner_account_id = %s OR
  conversation_id IN (멤버)`, MySQL 은 `JOIN AgentCoreConversations c` 동형. 엔드포인트는 items 의
  `owner_account_id`/`is_member` 로 conv_ids 를 거르던 것을 폐기(그 필드는 **PG 경로만** 채워
  MySQL 폴백에서 멤버 대화 근거가 조용히 비었다 — AC-4 위반). self_id 부재 시 `-1` 전달로 fail-closed.
- **프론트 응답 경합 가드** — `state.searchModal.requestGen` 세대 토큰. `runSearchQuery` 가 요청 전
  세대를 발급하고 성공·실패 양 경로에서 대조해, 늦게 도착한 이전 응답이 새 결과·근거 칩을
  덮어쓰지 못하게 한다.
- **PG runaway 상한** — `SET SESSION max_execution_time`(§8.4)은 MySQL 연결 전용이라 라이브(PG)
  검색에 상한이 없었다. `_list_conversations_pg`(검색어 있을 때만)와 수집 쿼리에
  `SET statement_timeout = 3000` 추가.

**미해소(정직)**: `ILIKE '%q%'` 인덱스 미사용은 그대로 — 위 timeout 은 상한이지 비용 개선이 아니다.
라이브 `EXPLAIN ANALYZE` 는 POST-DEPLOY.

테스트 30건(P4 SQL 스코프 이관·P5 수집 SQL 스코프·P6 statement_timeout·F5 경합 가드 추가) PASS ·
전체 회귀 신규 실패 0 · ruff PASS.
## CHG-20260729T152000-ratelimit-scope-paging — 대화 페이징 429 블로킹 해소 + 부하의 클라이언트 분산 (Major §12.3, 2026-07-29)

**web(feature-0003) — rate limit**: `app.py` 에 `RATE_SCOPE_*` 상수 6종
(`conversation_search`/`sample_feedback`/`fix_with_ai`/`message_edit`/`branch_nav`/`metadata_ai`)
+ `_BRANCH_NAV_RATE_PER_MIN=60` + `_RATE_LIMIT_BUCKETS_MAX_KEYS=4096` + `_json_rate_limited`
(429 + `Retry-After` + 본문 `retry_after`) 신설, `_RATE_LIMIT_BUCKETS` 타입을
`dict[int, list[float]]` → `dict[tuple[int, str], list[float]]` 로 변경.
`routers/conversations.py` `_search_rate_limit_check` 에 `scope` 파라미터 추가(버킷 키 =
`(account_id, scope)`) + 만료 버킷 sweep, `_rate_limit_retry_after` 신설(`app.py` 재수출).
호출부 7곳(`conversations.py` 5 + `admin_metadata.py` 2, scope 6종 — 메타데이터 AI 가 suggest·bootstrap 2곳)이 각자 scope 를 명시하고 429 를
`_json_rate_limited` 로 교체 — **버전 페이징만 상한 5 → 60**, LLM 점유 경로는 무변경.

**web(feature-0003) — 쿼리**: `routers/_conv_store.py` `_branch_leaf_of` 의 재귀 서브쿼리에
`c.conversation_id = %s` 술어 추가(파라미터 3 → 4). `ix_{table}_parent =
(conversation_id, parent_message_id)` 의 선두 컬럼이 빠져 매 재귀 단계가 인덱스 전체를 훑던
것을 정상 인덱스 스캔으로 교정 — 비용이 전체 테이블 크기 비례에서 **대화 크기 비례**로.

**web(feature-0003) — 프론트 부하 분산**: `static/app.js` 에 `_branchViewCache`
(Map, 상한 8 · TTL 30s · LRU) + `_branchViewCacheKey/Get/Set/Clear` + `_fetchHistoryPayload`
+ `_scheduleSidebarCatchup`(1.2s 디바운스) + `_branchPageInFlight` 가드 신설.
`loadHistory` 에 `versionCacheKey` 옵션 추가 — 있으면 캐시 우선, 없고 비-append 면
**캐시 무효화 단일 choke-point**(대화 전환·전송 후·편집 후·유휴 run 동기화가 모두 통과).
`_pageBranch` 가 `refreshWorkspace` → `loadHistory({versionCacheKey})` + 지연 사이드바
catch-up 으로 전환(`/api/session` 호출 제거), 429 는 실패 토스트가 아니라 대기 초를 담은
중립 토스트로 표시.

**테스트**: `tests/test_ratelimit_scope.py` 17건 신설 (스코프 격리 S1/S1b/S2/S3, window
만료 S4, 메모리 가드 S5, retry-after R1/R2, 429 형태 J1/J2(5 파라미터), 페이징 endpoint
배선 B1/B2, **교차오염 end-to-end 회귀 B3**). 컨테이너 전체 스위트 실패 13건은 main 과
동일한 환경성 baseline — **신규 실패 0**(같은 3파일 격리 실행 시 양쪽 모두 PASS).

**검증**: 실제 Windows 브라우저(PB-0008) — 캐시 적중 클릭은 `/api/history` 0회, 12연타에도
429 미발생. `_branch_leaf_of` 는 브랜치 대화 12건 × 두 store 전 메시지 442 조합 전수 대조
불일치 0. 벤치마크로 변경된 라이브 `active_leaf` 는 원값으로 복원 확인.

Cross-ref: FUNCTION `REQ-20260729T152000-ratelimit-scope-paging` · DECISIONS
`ADR-20260729T152000-ratelimit-scope-paging` · TASK `20260729T1520-ratelimit-scope-paging` ·
REVIEW `REV-20260729T152000-ratelimit-scope-paging`.
## CHG-20260729T163000-attach-append-only — 첨부 목록 append-only 전환 (삭제 UI 제거)

`static/app.js`: pill 의 × 를 조건부(`isPendingLocal`)로 전환 — 서버 저장 완료 첨부에는 미렌더 ·
`_removeAttachmentPill`+`_deleteConversationAttachment` 를 `_discardPendingAttachmentPill`
(ready 항목 no-op) 로 교체 · `_canDeleteFromAttachList` 와 목록 행 `.attach-list-item-del`
마크업/핸들러 제거. `static/index.html`: 안내 문구를 append-only 취지로 교체.
`static/styles.css`: `.attach-list-item-del` 규칙 제거(이름줄 flex 분리·meta 말줄임은 유지).
백엔드·API·RBAC·스키마 무변경 — `DELETE /api/attachments/{id}` 는 존치하되 프론트 호출 0건.

Cross-ref: DECISIONS `ADR-20260729T163000-attach-append-only` · TASK
`20260729T1630-attach-append-only` · 철회 대상 `CHG-20260729T152000-attach-list-delete`.
## CHG-20260729T0659-ai-claude-feature-0016-graph-detail-columns — 그래프 상세 패널 컬럼 3-소스 병합 + introspect 보강 (2026-07-29)

정본 cycle 은 feature-0016 (`docs/TASK.md ## 20260729T0659-graph-detail-columns`). 본 feature 는 코드 거주처.

- `src/static/graph/graph-ctxmenu.js` — `_metaDetailMergeColumns`(fetch 이웃 + 모델 self 소속 Column +
  상세 전용 introspect 캐시 union, 소문자 정규화 dedupe·ordinal 정렬) · `_metaDetailColsBackfillNeeded`
  (컬럼 0 또는 `truncated` 일 때만, 세션 1회) · `_metaGraphDetailColsBackfill`(논블로킹, `/graph/columns`
  재사용, **모델 미오염**, 렌더 세대 `_detailSeq` + 모델 세대 `_opSeq` 이중 가드) 신설.
  `_metaGraphRenderDetail` 이 병합을 호출하고, Table 은 컬럼 0 이어도 섹션을 렌더해 "조회 중"/실패
  사유를 표시.
- `src/static/graph/graph-state.js` — `detailCols`·`detailColsMiss`·`detailColsInflight`·`_detailSeq` 신설.
- `src/static/graph/graph-core.js` — `_metaGraphResetModel` 이 상세 캐시 3종을 함께 clear(스코프 전환
  누출·miss 고착 차단).
- `tests/headless/test_detail_columns.js` 신규 39건 PASS.

사용자 리포트: 캔버스엔 컬럼 40여 개가 펼쳐져 있는데 상세 패널엔 '컬럼' 섹션 자체가 없음. 라이브 실측
`cc_pyron.DT_ItemEnchantInfo` = 그래프 `HAS_COLUMN` **0** vs 실 데이터소스 컬럼 **35**. 단일클릭 상세에만
introspect 폴백이 없던 비대칭이 원인. §18.8 codex 적대 검증 P2 2건(실패 시 empty-state 고착 · 같은 키
재선택 race) in-cycle 흡수. 백엔드·마이그레이션 0 · 인가 경계 불변.

Cross-ref: FUNCTION `REQ-20260729-graph-detail-columns` (AC-GDC-1~3) · feature-0016 TASK
`20260729T0659-graph-detail-columns` · REVIEW `REV-20260729T065900-graph-detail-columns` ·
Run `docs/test-runs.d/20260729T0659-graph-detail-columns.md`.
## CHG-20260729T170000-search-collation-nameerror — 본문 검색 500 근본 수정 (Major, 선행 결함)

**증상**: `GET /api/conversations?q=…` 500 (`NameError: name '_COLLATION_AUDIT_DONE' is not defined`,
`routers/_audit_infra.py:93`). 검색어 없는 목록 조회는 정상. 2026-07-11~07-29.

**원인**: ITEM-10 p7(CHG-20260711T161858)이 `_audit_message_table_collations` 를 app.py →
`routers/_audit_infra.py` 로 이동할 때 `global _COLLATION_AUDIT_DONE` 만 옮기고 module-level
정의는 app.py 에 남겼다. `global` 은 그 모듈 전역을 가리키므로 첫 읽기에서 NameError.

**변경**: `unit/feature-0003-agent-web-ui/src/routers/_audit_infra.py` —
플래그를 `getattr(app, "_COLLATION_AUDIT_DONE", False)` 로 읽고 `app._COLLATION_AUDIT_DONE = True`
로 쓴다(패치-단일점 규약). 모듈 로컬 정의는 신설하지 않는다(상태 이중화 방지).

**동일 유형 전수 검사**: `src/**/*.py` AST 스캔으로 `global X` 대비 module-level 바인딩 부재
검출 → 수정 후 0건.

**테스트**: `test_search_collation_audit.py` 5건 신설(N1~N5). **역검증** — 수정을 되돌리면
N1/N3/N4 가 NameError 로 실패. 전체 회귀 신규 실패 0 · ruff PASS.

Cross-ref: TASK `20260729T1700-search-collation-nameerror` · REVIEW
`REV-20260729T170000-search-collation-nameerror`.
## CHG-20260729T172000-append-only-postdeploy — append-only POST-DEPLOY 실증 기록 (doc-only)

실행 코드·정적 자산 변경 **0줄**. `docs/test-runs.d/20260729T1630-attach-append-only.md` 에
POST-DEPLOY Run 절 append(명제 5건 PASS + 미실증 1건), `docs/TASK.md` 종결 섹션,
`docs/REVIEW.md` `[SKIPPED:non-policy-doc]`.

Cross-ref: TASK `20260729T1720-append-only-postdeploy`.

## CHG-20260729T180000-conv-search-postdeploy — 대화 검색 첨부 파일명 축 POST-DEPLOY 실증 기록 (doc-only)

코드 변경 0. 직전 두 cycle(`20260729T1455-conv-search-attach-name` 축 추가 · `20260729T1700-search-collation-nameerror`
검색 500 hotfix)의 배포 후 라이브 실측 결과를 정본에 반영한다.

- `TASK.md` — 양 cycle 의 POST-DEPLOY 체크박스 완료 처리 + 실증 섹션 `20260729T1800-conv-search-postdeploy` append.
- `test-runs.d/20260729T145500-conv-search-attach-name.md` — `verdict` 를 "라이브 PB-0008 완료" 로 갱신,
  예정 항목 5개를 실측 결과(PASS/근거)로 대체, 성능 실측 Run 추가.
- `REPORT.md` — "잔여: POST-DEPLOY …" 문장을 실측 결과 요약으로 대체.

**실측 요지**: PB-0008 5항목 전건 PASS(첨부 파일명 매칭·📎 칩 강조·본문 매칭 행 칩 없음·구버전/삭제
전용 파일명 matched 0·에러 0) · 성능 EXPLAIN ANALYZE 에서 첨부 EXISTS 0.3ms / 전체 65.1ms(0.5% 미만)로
codex P2 이월분 해소 · hotfix 전 500 → 후 200 으로 라이브 본문 검색이 2026-07-11 이후 처음 복구.

Cross-ref: TASK `20260729T1800-conv-search-postdeploy` · REVIEW `REV-20260729T180000-conv-search-postdeploy`.
## CHG-20260729T174200-product-picker-keynav — 제품 선택 드롭업 검색 후 방향키 순회 + Enter 선택 (2026-07-29)

작업 화면 컴포저 제품 선택 드롭업(`#productDropupMenu`)의 키보드 경로를 닫았다. 검색칸까지는
있었으나(REQ-20260618-0317) 좁힌 결과를 고르려면 마우스로 되돌아가야 했다.

- `src/static/app.js`
  - `productDropupNavItems(menu)` 신설 — 순회 대상 = `.product-dropup-item` − `.hidden`(검색 필터 탈락)
    − `.is-view-only`(선택 경로가 막힌 열람 전용 행).
  - `focusProductDropupItem(item, menu)` 신설 — `focus({preventScroll:true})` + 메뉴 자신의 `scrollTop`
    최소 보정(위로 이동 시 sticky 검색칸 높이 차감). `scrollIntoView` 미사용(조상 스크롤 오염 회피).
  - `moveProductDropupFocus(item, key)` 신설 — ↑/↓ 이동, 최상단 ↑ → 검색칸 복귀(+`scrollTop=0`),
    wrap-around 없음.
  - `buildProductDropupSearch()` — `keydown` 추가: `ArrowDown`(IME 가드 `isComposing` + 레거시
    `keyCode===229`) → 결과 첫 항목 진입.
  - `buildProductDropupItem()` — 기존 `keydown` 확장: Enter/Space 는 종전 `_select` 그대로, ↑/↓ 는
    `moveProductDropupFocus` 위임(자식 '연결 테스트' 버튼에서 버블된 키는 종전대로 무시).
  - `openProductDropup()`/`closeProductDropup()` — 문서 리스너(바깥클릭·Escape) 해제 책임을
    `closeProductDropup` 단일 지점으로 이동(`_productDropupDetach`). 종전엔 항목 선택으로 닫으면
    리스너가 문서에 남아, 닫힌 뒤 Escape 가 죽은 클로저를 태워 chip 으로 포커스를 튕겼다
    (기존 결함 — 클릭 선택 경로에도 존재. codex 적대 리뷰 P2 로 표면화되어 in-cycle 흡수).
- `src/static/styles.css` — `.product-dropup-item:focus-visible`(파란 outline + 옅은 배경, offset −2px)
  로 키보드 커서 위치 가시화(마우스 클릭에는 링이 남지 않음).
- `tests/headless/verify_product_dropup_keynav.py` 신규 — 실 chromium 레이아웃 위에서 **실
  `renderProductDropupMenu`/`openProductDropup`/`closeProductDropup` 원문**(외부 의존만 스텁) + 실
  `styles.css` 로 27건 PASS(진입·필터·순회·경계·열람전용 제외·Enter 선택·스크롤 추종·sticky 미가림·
  0건·IME 2형태·검색칸 없는 경로·리스너 누수·Escape 무회귀·재렌더 후 배선·페이지 에러 0).

백엔드·RBAC·스키마·엔드포인트·마이그레이션 0. 제품 목록은 이미 `product.access.<key>` 로 게이트된
`state.products` 위에서만 순회하므로 접근 제어 표면 불변. 기존 `verify_product_dropup_scroll.py`
11/11 PASS(회귀 0).

Cross-ref: FUNCTION `REQ-20260729T174200-product-picker-keynav`(AC-PPKN-1~4) · TASK
`20260729T1742-product-picker-keynav` · REVIEW `REV-20260729T174200-product-picker-keynav` ·
Run `docs/test-runs.d/20260729T1742-product-picker-keynav.md`.
## CHG-20260729T180000-picker-keynav-postdeploy — product-picker-keynav POST-DEPLOY 라이브 실증 기록 (2026-07-29)

문서·검증 산출물만(코드 0). 배포본 `17251df8` 을 실 Windows 브라우저로 검증한 결과를 기록한다.

- `docs/test-runs.d/20260729T1742-product-picker-keynav.md` — POST-DEPLOY Run 절 추가
  (Environment: Windows-browser · AC-PPKN-1~4 + 리스너 누수 수정 실측 PASS).
- `docs/TASK.md` — `## 20260729T1800-picker-keynav-postdeploy` 종결 섹션.
- `tests/win-browser-product-picker-keynav.scenario.json` — 재현 시나리오(실 키 이벤트 press 배열).
- `docs/evidence/pb0008-product-picker-keynav-{focus,selected}-20260729.png` — 포커스 링·선택 결과 증거.

Cross-ref: TASK `20260729T1800-picker-keynav-postdeploy` · 선행 `20260729T1742-product-picker-keynav`.
## CHG-20260729T0900-ai-claude-feature-0016-graph-cap-audit — 그래프 상한 전수 감사(프론트·라우터 몫) (2026-07-29)

정본 cycle 은 feature-0016 (`docs/TASK.md ## 20260729T0900-graph-cap-audit`). 본 feature 는 코드 거주처.

- `src/routers/admin_metadata.py` — 그래프 검색 `limit` 기본값 50 을 **모듈 안전 가드에 위임**(미지정 시
  `metadata_graph._SEARCH_CAP`; 숫자 복제 제거) · `/graph/columns` 의 `rows[:500]` 절단 제거(전량 반환).
- `src/static/graph/graph-ctxmenu.js` — 컬럼 보강 게이트를 **3경로 모두 전량화**(상세
  `_metaDetailColsBackfillNeeded` · 캔버스 `_metaGraphToggleColumns` · 더블클릭 `_metaGraphExpand`),
  union 시 **ordinal 보완**(그래프 Column 정점엔 ordinal 이 없어 ERD 정렬이 어긋났다), 캔버스 union
  소문자 dedupe, 참조 컬럼 표시 `_META_RTCOL_SHOW`(8 + "외 N") → **전량**(축약은 CSS ellipsis, 전문은
  title 보존) + `_META_RTCOL_GUARD` 안전 가드.
- `src/static/graph/graph-state.js` — `_META_SEARCH_CAP` 미러 50 → 5000(백엔드 정합, 부분값 표기 신호는 유지).
- `tests/headless/test_detail_columns.js` — 51 PASS(부분 투영 union·ordinal 보완·3경로 계약 신설).

사용자 리포트: `DT_Character_New` 상세가 `컬럼 (2)` 뿐(실제 55). 방향 지시 "개수를 줄여 출력하는
최적화는 다른 방향으로" 에 따라 표시·조회 절단을 제거하고 축약은 렌더 계층에 위임.


## CHG-20260729T213000-metadata-product-scope — 지식베이스 메타데이터 스코프 축 datasource → 제품 전면 전환

Task-Cycle: feature-0003-agent-web-ui · TASK `20260729T2130-metadata-product-scope` (cross-cut 코드 거주:
feature-0002-agent-core 읽기/쓰기 seam · shared/config 축 정의)

**축 정의 (`shared/config.py`)**
- `PRODUCT_SCOPE_PREFIX="product."` · `product_scope_key()` · `is_product_scope()` — KB scope 키 규약.
  구분자를 `:` 가 아닌 `.` 로 둔 이유: `_sanitize_key_part` 허용 문자가 `[A-Za-z0-9_.-]` 라
  `product:kr_live` 는 `product_kr_live` 로 뭉개져 read/write 축이 조용히 어긋난다.
- `set_active_product(key, *, unresolved=False)` / `get_active_product_scope()` /
  `is_product_scope_unresolved()` — `set_active_datasource` 와 같은 ContextVar 패턴.
  **"제품 없음"과 "제품이 있는데 해소 실패"를 구별**한다(자율수집 fail-closed 근거).
- `AGENT_KB_LEGACY_DS_SCOPE_READ`(기본 1) — expand/contract 스위치.

**읽기(주입) 경로 (feature-0002)**
- `modules/utils.py` — `_kb_scope_key()` / `_kb_scope_candidates()` 신설. 캐스케이드
  `[제품 스코프, (레거시 ds 스코프), 'common', '']`. fact/RAG 축(`_scope_candidates`,
  `CURRENT_FACT_SCOPE_KEY`)은 **무변경**(datasource 스코핑 계약 그대로).
- `modules/kb_glossary.py`·`kb_metadata.py`·`sample_queries.py` — 4개 로더의 scope 해소를
  `get_active_datasource()` → 활성 제품으로 교체. `modules/tools.py` describe_table 오버레이 동일.
- `agent_core.py` — `_resolve_product_scope_key(mem_conn, product_id)` 신설(→ `(scope, unresolved)`),
  run 시작에 `cfg.set_active_product(...)`, finally 2곳에서 해제. 제품은 run 전체에 고정이므로
  멀티-DS 라우팅으로 활성 datasource 가 바뀌어도 같은 제품 사전이 주입된다.

**쓰기(자율수집) 경로**
- `_glossary_autopropose` / `_enum_autopropose` — 귀속 축을 제품으로. **`is_product_scope_unresolved()`
  면 중단**(‘common’ 폴백 금지 — 제품 전용 용어가 전 제품에 퍼지는 cross-product 누출).
- deferred(worker) 경로 — `_cur_pkg` 에 `product_scope_key`/`product_scope_unresolved` 캡처,
  `run_post_answer_curation` 이 복원·원복.
- `modules/insight.py` — `_self_heal_scope_keys()` 신설. ENUM self-heal sweep 대상을 제품 스코프로
  하되 **이 datasource 에만 바인딩된 제품**만(다중 DS 제품은 `known_schemas` 가 불완전해 다른 DS 의
  정상 enum 을 오삭제하므로 제외 = fail-open). 레거시 단일 바인딩(`WebProducts.DatasourceKey`) 폴백 포함.

**admin API (feature-0003)**
- `routers/admin_metadata.py`
  - `_product_scope_catalog()` 신설 — 제품 SSOT 단일 해소점(scope_key/제품/바인딩 datasource/접근DB).
    `WebProductDatabases` 는 `DatasourceKey` 컬럼 부재(레거시) 폴백 쿼리를 거친 뒤에만 미가용 판정하고,
    미가용은 `databases_ok=False` 로 **"접근DB 없음"과 구별**해 소비처가 fail-closed 하게 한다.
  - `_metadata_valid_scope_keys()` — 허용 축을 datasource → **제품 스코프 ∪ common** 으로 교체.
  - `_scope_database_units()` / `_scope_datasource_for_schema()` / `_scope_primary_datasource()` /
    `_catalog_datasources()` 신설 — 물리 연결 해소는 **서버 전용**. 접근DB 선언 제품은 그 allowlist
    밖 schema 를 거부(제품 경계 강제), 미선언 제품만 primary 로 폴백.
  - `GET /api/admin/metadata/scopes` **신설** — 콘솔 스코프 옵션(제품 목록 + 공용).
  - `GET /bootstrap/schemas` — `?scope_key=` 기반. 1차 원천은 제품 접근DB(라이브 연결 없이 즉답),
    미선언 제품만 introspection 폴백. `POST /bootstrap` — body `{scope_key, schema}`.
    **호출자 지정 `datasource` override 제거**(임의 제품 scope 로 아무 DS 나 introspect 하던 경계 우회).
    MSSQL DB allowlist 매칭을 **대소문자 무관**으로(저장 라벨 lower 계약 §58 ↔ 서버 원본 케이스).
  - `{sub}/suggest` grounding 도 동일하게 서버 해소 전용.
- `app.py` — 신규 헬퍼 5종 re-export(테스트/타 라우터 `app.X` 참조 보존).

**관리 콘솔 (feature-0003 `static/`)**
- `admin.html` — 필터 바 라벨 `데이터소스` → `제품`, 부트스트랩 안내·empty-state·기본 단위 라벨 문구,
  거버넌스 안내문("제품별로 관리 · 제품이 여러 DB에 걸쳐 있어도 동일 적용").
- `admin.js` — `adminState.metadata.productScope`/`productScopes` 신설(그래프 pane 의 `scopeKey`
  datasource 축과 **분리**). `_metaPopulateProductScopeSelect()`/`_metaLoadProductScopes()`/
  `_metaCurrentProductEntry()`/`_metaScopeIsProduct()` 신설, `_metaPopulateScopeSelect()` 는 그래프
  전용으로 축소. 목록·등록·수정·삭제·검토큐·부트스트랩·AI 자동완성이 모두 제품 축. 부트스트랩
  상태 필드 `datasource` → `scopeKey`. `_metaDatasourceLabelOf()` 는 제품명 역매핑으로 전환.
  usage-nav 의 datasource `scope_hint` 는 그래프 화면에만 적용(메타데이터에 넣으면 목록이 영구히 빔).

**이관 스크립트 (feature-0002 `src/scripts/kb_scope_rescope.py` 신규)**
- 대상 7테이블(등록분 5 + 검토 큐 3 중 `glossary_feedback`·`enum_feedback`·`sample_feedback`).
- 귀속 규칙: ① 단일 제품 DS → 그 제품 ② 공유 DS + `schema_name` → `WebProductDatabases` 로 소유
  제품 1개 확정 ③ 그 외 모호. 모드 `--assess`/`--migrate`/`--purge-ambiguous`/`--purge-all`/
  `--verify-contract`, mutate 는 **JSONL 전 컬럼 백업 강제** + `--apply` 없으면 dry-run.
- UNIQUE 충돌은 행 단위 SAVEPOINT 로 흡수하되 **SQLSTATE 23505 에서만** 중복 병합(그 외 예외는
  re-raise → 트랜잭션 롤백. transient 오류로 원본이 지워지는 것을 막는다).

**expand/contract**: 코드 배포와 데이터 이관은 원자적일 수 없다. 배포 시점엔 레거시 ds-scope 를
꼬리 후보로 함께 읽어(이 창의 동작 = 종전과 동일, 새 회귀 아님) 메타데이터가 사라지지 않게 하고,
이관 완료(`--verify-contract` 0건) 후 `AGENT_KB_LEGACY_DS_SCOPE_READ=0` 으로 contract 한다.

**마이그레이션 0 · 신규 권한 0 · RBAC 표면 불변**(기존 `metadata.*`/`kb.*` 그대로). 스키마 변경 없음
(scope_key 는 문자열 축 재해석).

Cross-ref: FUNCTION `REQ-20260729T213000-metadata-product-scope` · TASK `20260729T2130-metadata-product-scope` ·
REVIEW `REV-20260729T213000-metadata-product-scope` · Run `docs/test-runs.d/20260729T2130-metadata-product-scope.md`.


## CHG-20260729T220000-metadata-product-scope-postdeploy — 제품 스코프 전환 POST-DEPLOY 실증 (문서 전용)

Task-Cycle: feature-0003-agent-web-ui · TASK `20260729T2200-metadata-product-scope-postdeploy`

코드 변경 0 — 라이브 이관·contract·PB-0008 결과 기록만. 상세는
`docs/test-runs.d/20260729T2130-metadata-product-scope.md` POST-DEPLOY 절 · TEST.md Run.

- 이관: update 5,130 · delete 257 · 백업 5,387행. `--verify-contract` 잔여 0.
- contract: `.env` 에 `AGENT_KB_LEGACY_DS_SCOPE_READ=0`(gitignored 운영 파일) + web-a/web-b/
  ask-worker/insight-worker 재기동. 전 컨테이너 SHA 핀 이미지 + `LEGACY=0` 실측.
- PB-0008: 제품 선택기 17건 · `KR_LIVE` 85건 회복 · 공유 datasource 3제품 경계 분리 + 교차 404 ·
  이관 귀속 정확도 · 부트스트랩 제품 접근DB 한정. 증거 스크린샷 2건(`artifacts/pb0008/`).

## CHG-20260730T010301-doc-sync-rn-0730 (TASK-20260730T010301-doc-sync-rn-0730 — 07-29 사용자향 머지분 릴리즈노트 정합, 비-정책 doc-only)
- 변경: `static/release-notes-data.js` 최상단에 신규 "2026-07-29" 블록 prepend(13항목) + `generated` 07-28→07-29. 렌더 로직·백엔드·스키마·RBAC·엔드포인트 0.
- cache-buster `?v=dev` 고정(index/admin.html 편집 0 — 2026-07-12 ITEM-09 빌드 자동주입 regime; `inject_asset_stamp.py`(Dockerfile:39) + deploy-web.sh `asset_stamp_verify` 가 배포 시 content-hash 주입·`?v=dev` 잔존 시 ABORT, 수동 bump 폐지·불가침). wrapper 헤더의 수기 bump 지시(index/admin `?v=<new>`)는 07-12 이전 regime → 부적용(현행 코드로 재검증, 484623fb·abcb7d68 동일 판정).
- 날짜 관례: 07-29 배포분(block date=배포일=델타 커밋 git-date, 파일에 07-29 블록 부재)이라 기존 블록 append 아닌 **신규 07-29 블록 prepend**(함정 #20 분기: 그 배포일 블록이 없으면 prepend). `generated`=top-block date=2026-07-29.
- 근거 정본: 각 항목 owning POST-DEPLOY 라이브 실증 커밋 + `git log 8b0c7ea3..HEAD`(43 non-merge 커밋).
- 배포됐으나 자체 POST-DEPLOY 실증 커밋 부재 3건(대화 페이징 429 블로킹 해소 48a9f1f6·추론 회차 표시 교정 10c84d81·추론 탭 안내문구 축약 45dfe362)은 함정 #18c 보수 default 로 HOLD. 제외: 내부 테스트 격리(770c436b·97be4cda·7749a04a)·UI 카피 예산 게이트(394b987d governance)·LEARNINGS 기록.
- Verification: `node --check` PASS · 구조검증(releases[0].date=2026-07-29 신규 13 items·releases[1] 2026-07-28 9항목 보존·releases[2] 07-27 보존·스키마 type/area/title/detail·enum 유효·내부용어 누출 0). 13항목 전부 owning POST-DEPLOY 라이브 실증 커밋 보유(274174e5·8775f9a0·2f10b550·d605874e·7038f5a6·63d5e83f·a5594383·24f52a84·637152f4·7d0997f7·26f263f0·3ce453cf·712a847f·f768e774·e86f4c6b). 릴리즈노트 render 테스트(`tests/verify_release_notes.mjs`)는 jsdom 미설치(env 제약)로 미실행 — render 로직 미변경이라 대상 아님(함정 #3c).
- 적대검증: ULTRACODE wf_0663e5aa R1(3-타깃 analyze→타깃-스코프 verify, cross-fault 회피 함정 #12·9 에이전트) — RN MAJOR 1(item8 제품 선택기 위치 '입력창 아래' 오안내 → 2-렌즈 독립 합치, 위치 중립 '입력창의 제품 선택 드롭다운' 으로 교정)·MINOR 3(summary 가 13항목 중 11만 서술 → item8/item9 절 보강·item13 '기본 접힘' → '가장 최근 대화만 펼쳐짐'·item13 07-27 블록과 중복 → '중간 회차' delta 명시) 적발, 오케스트레이터 정본 독립 재검증 후 전건 교정.
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).

## CHG-20260731T010301-doc-sync-rn-0731 (2026-07-30 블록) 릴리즈노트 콘텐츠 — 2026-07-30 블록 신규 prepend 8항목(진행단계 박제 해소·재배포 dead-air·연결장애 모델 강등 제거·관계도 컨텐츠 카테고리 3축·AI 능동 분석 회복성)
- 사용자 노출 릴리즈노트(`static/release-notes-data.js`) 최상단에 신규 date "2026-07-30" 블록 prepend(8 items: fixed/work 2 · fixed/common 1 · improved/admin 4 · fixed/admin 1) + `generated` "2026-07-29"→"2026-07-30". 기존 38 블록 전량 보존(39 블록).
- 평이화/비노출: feature-id·§번호·PR#·commit sha·모듈/함수명·테이블명·마이그레이션 번호·내부 설정키(`AGENT_*`)·모델명(gemma/bedrock/titan/embed-ollama)·ADR 번호·PB-0008 누출 0(정규식 기계 검증).
- 캐시버스터 수기 bump 없음(빌드 주입 메커니즘 — ITEM-09). `index.html`/`admin.html` 무변경.
- Verification: `node --check` PASS · vm 구조검증(releases[0]=2026-07-30 8항목·releases[1]=07-29 13항목 보존·enum/title 위반 0·내부용어 누출 0). `verify_release_notes.mjs` 는 jsdom 미설치로 미실행(render 로직 미변경).

## CHG-20260803T154922-aiops-taxonomy-unmapped (20260803T1549-aiops-taxonomy-unmapped — `운영 현황` 미분류 활동 3종을 인사이트 분석으로 재배치, Minor §12.3)
- 변경: `shared/model_catalog.py` `TASK_TAXONOMY` 에 3행 추가 — `cluster_summary`→`ai.insight.analyze`/"콘텐츠 그룹 요약", `domain_summary`→`ai.insight.analyze`/"도메인 종합 요약", `analysis_verify`→`ai.insight.analyze`/"분석문 사실성 검증". 함수·시그니처·카테고리 라벨맵·엔드포인트·RBAC·스키마·프론트 무변경(dict 데이터 추가만).
- 근거(라이브 실측 2026-08-03): `agent_runtime.llm_usage` DISTINCT task 16종 중 위 3종만 미등록 → `taxonomy_for()` 폴백으로 `ai.other.unmapped` 에 누적(1,258 / 332 / 4회). 셋 다 insight 워커 파이프라인 산출물(`conversation_id='__insight_worker__'`, target=객체/데이터소스/스키마)이라 기존 `ai.insight.analyze` 에 편입 — 신규 카테고리를 만들면 드릴다운만 파편화된다. `analysis_verify` 는 검증 축이지만 검증 대상·소비처가 인사이트 분석문이라 같은 카테고리에 둔다(대화 파이프라인의 검증인 `redteam` 을 `ai.reasoning.aux` 에 둔 선례와 동형).
- 테스트: `unit/feature-0003-agent-web-ui/tests/test_ai_ops.py` +2 — ① 3종 명시 매핑 ② **AST 전수 게이트**(`shared/**`·`unit/*/src/**` 에서 `_record_llm_usage(model, "<task>", …)` 두 번째 positional 문자열 리터럴 전수 수집 → `TASK_TAXONOMY` 미등록 0 단언, 수집 하한 10 으로 스캐너 무력화 시 vacuous pass 차단).
- 부수효과(의도): Attention 존의 "미분류 AI 활동" 배지 소멸 · `LLM 사용량 > 사용 기록` 의 raw task 문자열(`analysis_verify` 등)이 사람이 읽는 작업명으로 노출. `USAGE_TASK_NAV` 는 미등록 유지 — 세 task 의 산출물을 보여주는 전용 관리 화면이 없어 기본 폴백(`AI 운영 현황 > 운영 현황`)이 정확한 착지다(§8.1 후속 제안 아님, 현행이 정답).
- 교차 참조: `shared/docs/MODIFY.md` (§17 shared 거버넌스).
- Files: `shared/model_catalog.py`, `unit/feature-0003-agent-web-ui/tests/test_ai_ops.py`, `unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,TEST}.md`, `unit/feature-0003-agent-web-ui/docs/test-runs.d/20260803T1549-aiops-taxonomy-unmapped.md`.

## CHG-20260803T174200-aiops-taxonomy-postdeploy (20260803T1740-aiops-taxonomy-postdeploy — 미분류 활동 재배치 POST-DEPLOY 실증, doc-only)
- 코드 변경 0 — 배포·라이브 대조 결과 기록만. 상세는 `docs/test-runs.d/20260803T1549-aiops-taxonomy-unmapped.md` §4 · TEST.md Run.
- 배포: `--web-only` 스코프, web-a·web-b GIT_COMMIT=c0c6800f(본 cycle 커밋 7c562a0a 포함 확인), soak 90s 통과, Caddyfile 무변경(edge blip 0). 워커 미접촉 — taxonomy 는 web 관제 표시 전용이라 워커 소비 경로 없음.
- 실증: 배포본 taxonomy 18→21종, 3 task 가 `ai.other.unmapped` → `ai.insight.analyze` · 라이브 API `categories[]`/`attention[]` 에서 미분류 소멸 · PB-0008 육안으로 pane 텍스트 "미분류" 0회 + 최근 활동 피드가 raw task 대신 작업명 노출.
- Files: `docs/{TASK,MODIFY,REVIEW,TEST}.md`, `docs/test-runs.d/20260803T1549-aiops-taxonomy-unmapped.md`.

## CHG-20260804T010301-doc-sync-rn-0804 (2026-08-03 · 2026-07-31 블록) 릴리즈노트 콘텐츠 — 신규 2블록 10항목 prepend(무거운 조회 코칭·LIMIT 오차단 해소·정확도 규칙 실적용·미확인 표기·AI운영현황 분류·관계도 1멤버 카테고리/칩 오버플로·리뷰 프레이밍·스키마 간 어휘 통일·중요도 기반 자동 분석)
- 사용자 노출 릴리즈노트(`static/release-notes-data.js`) 최상단에 신규 date "2026-08-03" 블록(7 items) + "2026-07-31" 블록(3 items) prepend + `generated` "2026-07-30"→"2026-08-03". 기존 39 블록 전량 보존(41 블록).
- 평이화/비노출: feature-id·§번호·PR#·commit sha·모듈/함수명·테이블명·마이그레이션 번호·내부 설정키(`AGENT_*`)·모델명·ADR 번호·PB-0008 누출 **0**(정규식 기계 검증).
- 캐시버스터 수기 bump 없음(빌드 주입 메커니즘 — ITEM-09). `index.html`/`admin.html` 무변경.
- Verification: `node --check` PASS · vm 구조검증(releases[0]=2026-08-03 7항목 · releases[1]=2026-07-31 3항목 · releases[2]=07-30 8항목·releases[3]=07-29 13항목 보존 · enum/title/summary 위반 0 · 내부용어 누출 0). `verify_release_notes.mjs` 는 jsdom 미설치로 미실행(render 로직 미변경).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).

## CHG-20260804T045828-share-join-btn-visibility (20260804T0458-share-join-btn-visibility — 공유 링크 '대화에 참여' 버튼 노출 조건 확대, 프론트 전용)
- 변경: `static/share.js` — ① `shouldShowJoin(viewer)` 순수 함수 신설(`is_authenticated && (can_join || joinable)`; `already_member` **미참조**) ② `render()` 의 참여 버튼 게이트를 `viewer.is_authenticated && viewer.can_join` → `shouldShowJoin(viewer)` 로 교체 ③ 액션 3종(참여·fork·로그인 링크)의 표시·배선을 `wireShareAction(el, visible, onClick)` 로 일원화(`classList.toggle` 재숨김 + `dataset.shareWired` 1회 부착) ④ 이미 멤버일 때 참여 버튼 `title` 보조 문구. **HTML·CSS·백엔드·API·RBAC·스키마 무변경.**
- 근거(라이브 실측 2026-08-04): 공유 링크 `Id=81` 은 `Joinable=1` 인데 감사로그상 로그인 열람자가 대화 소유자(`account_id=10`, `conversation_members.role='owner'`) 뿐이라 `can_join=false` → `share.js` 의 `can_join` 단독 게이트가 참여 버튼을 사유 없이 숨겼다. `can_fork` 는 소유자 여부를 보지 않아 fork 만 남아 "fork 만 보이고 참여 버튼 없음" 으로 관측. 서버는 이미 `viewer.joinable`·`already_member` 를 응답에 담고 있었으나 프론트가 미사용이었다. 결정(AskUserQuestion): 소유자·기존 멤버에게도 노출.
- 안전성(적대 리뷰 P1 반영): 초안은 이미 멤버의 클릭도 `join` 으로 보냈으나, 서버 `join` 은 이미 멤버여도 **windowed 링크**면 `stamp_member_visibility(is_new_member=False)` 로 가시 범위를 **교집합 축소**한다(`group_members.py` — owner·기존 full 멤버는 skip, 기존 windowed 멤버는 축소되고 복구 경로 없음). 그래서 **이미 멤버인 클릭은 join 을 호출하지 않고** `viewer.conversation_id` 로 곧바로 이동하도록 바꿨다(`openJoinedConversation`). 결과: 표시 확대가 멤버십·가시성 window·감사 기록을 바꾸지 않는다. `Joinable=0` 링크의 403, `can_join` 계산은 그대로(테스트 B2 로 고정) — **표시 확대 ≠ 인가 확대**.
- 서버 변경(최소): `routers/share.py` `public_share_view` 응답 `viewer` 에 `conversation_id` 1 필드 추가 — **`already_member` 일 때만** 실린다(익명·비멤버는 `None`, 새 식별자 누출 0). 인가 계산·엔드포인트·스키마·RBAC 무변경.
- 테스트: `unit/feature-0003-agent-web-ui/tests/test_share_join_btn_visibility.py` 신규 9건 — F1 `shouldShowJoin` 이 `already_member` 미참조 + **OR 결합 극성 고정** · F2 `render()` 에 `can_join` 단독 게이트 부재 · F3 `wireShareAction` 의 `toggle("hidden", !visible)` 극성 + 1회 부착 early-return 가드 · F4 참여 버튼 DOM·라벨 보존 · **F5 이미 멤버 클릭이 join 을 타지 않음(P1 회귀 차단)** · F6 핸들러가 stale 클로저 대신 최신 viewer 참조 · B1 응답 계약 유지 · B2 서버 인가 게이트 불변 · **B3 `conversation_id` 가 멤버 한정**.
- 부수효과(의도): 버전 페이징 재렌더 시 ① 액션 숨김 상태가 복원되지 않던 것과 ② 클릭 핸들러가 중복 부착돼 `doJoin`/`doFork` 가 여러 번 발사될 수 있던 것이 함께 해소된다(같은 코드 경로).
- 캐시버스터: 수기 bump 없음 — 소스는 `?v=dev` 고정이고 이미지 빌드가 `scripts/inject_asset_stamp.py` 로 content-hash 를 주입한다(2026-07-12 ITEM-09).
- Files: `unit/feature-0003-agent-web-ui/src/static/share.js`, `unit/feature-0003-agent-web-ui/src/routers/share.py`, `unit/feature-0003-agent-web-ui/tests/test_share_join_btn_visibility.py`, `unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,TEST}.md`, `unit/feature-0003-agent-web-ui/docs/test-runs.d/20260804T0458-share-join-btn-visibility.md`.

## CHG-20260804T062000-share-join-btn-postdeploy (20260804T0620-share-join-btn-postdeploy — POST-DEPLOY 실증, doc-only)
- 코드 변경 0 — 배포·라이브 실측 결과 기록만. 상세는 `docs/test-runs.d/20260804T0458-share-join-btn-visibility.md` §5 · TEST.md Run.
- 배포: PR #1134 머지(main `d23f0a0d`) → `--web-only` 스코프, web-a·web-b `GIT_COMMIT=d23f0a0d`, soak 90s 통과, Caddyfile 무변경. 워커 미접촉 — 변경분(share 정적 자산 + 공유 뷰 응답 1필드)은 web 전용 경로.
- 실증: 소유자 관점 참여 버튼 가시 · 클릭 시 `/join` **0건**(요청 캡처) · deep-link 이동 · 익명 `conversation_id=null` · fork 무회귀.
- Files: `docs/{TASK,MODIFY,TEST,REPORT}.md`, `docs/test-runs.d/20260804T0458-share-join-btn-visibility.md`.

## CHG-20260804T0610-msg-speaker-attribution 대화내역 발화자 귀속 — 발화 시점 각인 + 전환/fork 보정 + 메시지별 렌더
- **문제**: 발화자(사용자 발신자 / assistant 제품)가 메시지에 각인되지 않아 렌더 시점의 대화 설정
  (현재 owner · 컴포저 제품 칩)에서 파생됐다 → 제품 전환·fork 시 **과거 대화의 발화자가 실시간 변경**.
- `unit/feature-0002-agent-core/src/agent_core.py`: `_lookup_account_username`·
  `_answer_product_attribution` 신설. user 미러 meta 를 1:1 까지 확대(`sender_account_id`+
  `sender_username`; `group_chat` 마커는 주입 sender_username 게이트 유지 — 1:1 회귀 방지).
  run 진입부에서 `_answer_product_meta` 1회 해석 후 assistant 미러 **4경로 전부**에 각인
  (정상 답변·max_steps 초과·중단 보존·오류). dedup 의 `mirror_sender_account_id` 는 종전대로
  그룹에만 전달 — 1:1 에 넘기면 각인 이전 저장 행을 못 찾아 배포 경계 재시도에서 사용자 메시지가
  두 줄 되는 회귀.
- `unit/feature-0003-agent-web-ui/src/routers/_conv_store.py`: `_conv_product_attribution`(각인
  스키마 web 측 대응물)·`_conv_backfill_attribution`(미각인 행 한정 기입, PG=jsonb `||` set-based /
  MySQL=행 단위 RMW) 신설. `_conv_copy_messages(attribution_defaults=…)` 추가 —
  `_fork_conversation_impl` 이 **강등 전** 원본 제품(`_src_product_*`)과 원본 owner 를 전달.
- `unit/feature-0003-agent-web-ui/src/routers/conversations.py`: `PATCH …/product` 가 바인딩 UPDATE
  **직전** 직전 제품으로 미각인 assistant 메시지 보정(freeze-on-change). fail-open.
- `unit/feature-0003-agent-web-ui/src/app.py`: 신규 2 헬퍼 rebind 등재.
- `unit/feature-0003-agent-web-ui/src/static/app.js`: `_assistantSpeakerFor()` 신설 —
  renderMessages 가 대화-단위 단일 값(`_assistantLabel/_assistantIcon/_assistantSeed`) 대신
  **메시지별** 해석. 라벨·시드는 각인 스냅샷 우선, 아이콘만 현재 제품 설정. user 발화자는
  `senderId` 기반 분기 추가(대화 소유권 판정 제거). 제품 전환 성공 후 `loadHistory({preserveScroll:true})`.
- **보정은 추가만** — 기존 meta 키 무변경, 이미 각인된 행 무변경, 보정분은 `attribution_inferred: true`.
- Tests: `feature-0002/tests/test_msg_speaker_attribution.py`(12) ·
  `feature-0003/tests/test_msg_speaker_attribution_web.py`(12) 신규. 전체 스위트 exit 0, ruff clean.
- Files: `unit/feature-0002-agent-core/src/agent_core.py`,
  `unit/feature-0003-agent-web-ui/src/{app.py,routers/_conv_store.py,routers/conversations.py,static/app.js}`,
  양 feature `tests/`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md`.

## CHG-20260804T065000-msg-speaker-attribution-postdeploy 발화자 귀속 POST-DEPLOY 실증 기록 (문서 전용, 코드 변경 0)
- 코드 변경 0 — 배포·라이브 대조 결과 기록만. 상세는 `docs/test-runs.d/20260804T0610-msg-speaker-attribution.md` §6 · TEST.md Run.
- 배포: `sudo -E bin/deploy-web.sh` scope=all(web 롤링 + 워커 3종 + gateway reconcile + soak 90s). `agent_core.py` 변경 포함이라 `--web-only` 불가 — web 만 신코드면 ask-worker 가 구코드로 답변을 저장해 각인이 라이브에 미도달한다.
- 실증: 서비스별 GIT_COMMIT 5종 전부 `ddc1b589` · 서빙 스탬프 `app.js?v=f5eca54ed047` · 배포본 라이브 제품 전환 후 과거 발화자 `unchanged: true`(원복으로 바인딩 무변경).
- Files: `docs/{TASK,MODIFY,REVIEW,TEST}.md`, `docs/test-runs.d/20260804T0610-msg-speaker-attribution.md`.
## CHG-20260805T010301-doc-sync-rn-0805 (2026-08-04 블록) 릴리즈노트 콘텐츠 — 신규 1블록 3항목 prepend(공유 참여 버튼 표시·발화자 발화시점 각인·프롬프트 자동 작성 접지)
- 사용자 노출 릴리즈노트(`static/release-notes-data.js`) 최상단에 신규 date "2026-08-04" 블록(3 items: fixed/work 2 · fixed/common 1) prepend + `generated` "2026-08-03"→"2026-08-04". 기존 41 블록 전량 보존(releases 41→42). 08-04 블록이 아직 없었으므로 append 아닌 신규 prepend(선례 규약: 그 배포일 블록이 이미 있으면 append).
- 평이화/비노출: feature-id·§번호·PR#·commit sha·모듈/함수명(`_normalize_signal_topics`·`wireShareAction` 등)·테이블명(`agent_runtime.summary`)·내부 설정키·ADR 번호·PB-0008 누출 **0**(정규식 기계 검증). UI 라벨은 실코드 대조(`share.html:39` '대화에 참여' · `share.html:40` '내 계정에서 fork' · `index.html:575` '내 프롬프트' · `index.html:580` '자동 작성' · `app.js` '여기서 분기').
- 캐시버스터 수기 bump 없음(빌드 주입 메커니즘 — ITEM-09). `index.html`/`admin.html` 무변경.
- Verification: `node --check` PASS · vm 구조검증(releases[0]=2026-08-04 3항목 · releases[1]=08-03 7항목 · releases[2]=07-31 3항목 · releases[3]=07-30 8항목 · releases[4]=07-29 13항목 보존 · enum/title 위반 0 · 내부용어 누출 0) · `verify_release_notes.mjs` 33 pass / 1 fail(pre-existing `styles.css` 스크롤 assertion — 본 변경 무관, 변경 전 동일 재현).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).

## CHG-20260805T1042-harness-repair standalone mjs 하네스 red 전수 해소 (tests-only — 라이브 코드 변경 0)

- 대상: `tests/verify_*.mjs` 22파일 수정 + `tests/esm-classic-inject.mjs`·`tests/verify_notify_gating.mjs` 신설 + `tests/win-browser-settings-notif.scenario.json` 재작성. `src/static/**` 접촉 0.
- 수리 유형: ① jsdom `/tmp` 폴백 관용구 통일(product_icon_chip_list·product_picker_search·profile_icon_admin_surfaces·profile_icon_consistency) ② eval 의존 주입 갱신(conv_entry_defaults loadFolders·date_group_collapse _isAggregateGroupKey·metadata_bs_inline_desc _metaScopeIsProduct/_metaBootstrapSyncToScope·new_conv_dedup folders/date-tree 4의존·metadata_list_detail _metaRenderDetail 신 의존) ③ classic 주입 ESM strip(perm_self_scope·db_rule_pending·ds_accordion_collapse — 공용기 esm-classic-inject.mjs, ds_accordion 은 분리 모듈 순서 주입) ④ cache-buster 단언 → asset-stamp placeholder 계약(db_rule_ui·rule_db_coverage·llm_restriction(chat.css 짝)·dbpicker·member_kick_ban·member_actions_hover·new_conv_dedup) ⑤ stale 앵커 현행 계약 갱신(admin_tab_gating ai-console OR 3항목 개별 케이스·settings_archive_leave make()·metadata_scope_single_ds 함수 리네임·db_rule_ui _isRuleRow&&canManage·release_notes [^}] 블록-내 윈도우·model_persist sidebar.js 합본) ⑥ 정확 카운트 실측 핀(profile_icon_consistency 5/3).
- 시나리오: 전 블록 DOM 이벤트 경유 전환(kebab·#openProfileBtn·#closeProfileBtn) + async 팝업 클릭→wait_for→관측 3단 + A_notify_gating 은 verify_notify_gating.mjs 이관.
- 검증: mjs 40/40 green · 시나리오 실 Windows Chrome 20스텝 전건 OK (TEST.md Run-20260805T1042).
- 근거: feature-0038 REPORT §8 후속 후보 — 사용자 resume 지시(2026-08-05). 적대 패널 MAJOR 1·MINOR 5·NIT 2 전건 흡수(REV-20260805T104213-harness-repair).

## CHG-20260805T192000 판정 배지 PB-0008 라이브 실측 기록 (doc-only)

- **무엇:** `docs/test-runs.d/REV-20260805T190000-verdict-badge.md` 에 Windows-browser 실측 Run
  (PASS 4항목) + 증적 스크린샷 1장 추가. 코드 변경 없음.
- **왜:** 해당 REV 의 시각 검증은 정적 자산이 web 이미지에 baked 되는 구조상 배포 후로 미뤄져
  있었다. 배포본 `2a1089eb` 에서 실측해 그 잔여를 닫는다.
- **결과:** stage 1/0 라벨 분기, 역할 칩과의 시각 구분, 판정 없는 노드의 완전 미표시(빈 요소 0)
  전부 실화면 확인.
## CHG-20260806T010301-doc-sync-rn-0806 (2026-08-05 블록) 릴리즈노트 콘텐츠 — 신규 1블록 3항목 prepend(첨부 변경 부재-단정 봉인·노드 상세 판정 배지·판정 순환 차단)
- 사용자 노출 릴리즈노트(`static/release-notes-data.js`) 최상단에 신규 date "2026-08-05" 블록(3 items: fixed/work 1 · new/admin 1 · fixed/admin 1) prepend + `generated` "2026-08-04"→"2026-08-05". 기존 42 블록 전량 보존(releases 42→43). 08-05 블록이 아직 없었으므로 append 아닌 신규 prepend(선례 규약: 그 배포일 블록이 이미 있으면 append).
- 평이화/비노출: feature-id·§번호·PR#·commit sha·모듈/함수명·테이블명·내부 설정키·ADR 번호·PB-0008 누출 **0**(정규식 기계 검증). UI 라벨은 실코드 대조(`admin.html:924` 범례 · `graph/graph-ctxmenu.js:3604-3626` 배지/근거 · 기존 릴리즈노트 `분석문 사실성 검증`·`내 계정에서 fork` 선례).
- 캐시버스터 수기 bump 없음(빌드 주입 메커니즘 — ITEM-09). `index.html`/`admin.html` 무변경.
- Verification: `node --check` PASS · `verify_release_notes.mjs` **34 pass / 0 fail**(변경 전 baseline 동일) · 블록 순서·항목 enum(type/area)·기존 블록 보존 확인 · 내부용어 누출 0.
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).
- Reason: changed paths are docs + 비-정책 static data only — 코드/스키마/권한 변경 0.
- Timestamp: 2026-08-06T01:03:01+09:00
## CHG-20260806T1144-modal-backdrop-dismiss 사이드바 항목(대화/폴더) 모달 배경 dismiss — click 단일 이벤트 → pointerdown+pointerup 2단 계약
- **무엇:** 좌측 사이드바 항목에서 열리는 backdrop 모달 6종의 "바깥 배경 클릭으로 닫기" 판정을
  `click` 리스너에서 떼어내 신설 primitive `bindBackdropDismiss(backdrop, onDismiss)` (`static/app.js`,
  export) 로 단일화. 누름(`pointerdown`)과 뗌(`pointerup`)의 target 이 **둘 다 backdrop 자신**일
  때만 dismiss 성립하고, **실행은 이어지는 `click` 단계**에서 한다. 주 버튼(`button === 0`)·
  primary 포인터만 인정, `pointerId` 추적으로 보조 터치 간섭 차단, `pointercancel` 은 press 해제,
  배경에서 시작한 제스처의 **implicit pointer capture 는 즉시 해제**.
- **왜:** DOM `click` 의 target 은 mousedown/mouseup 두 지점의 **공통 조상**이다. 기존 6곳의
  `click` + `e.target === backdrop` 검사는 패널 안에서 누르고 배경에서 떼거나(폴더 지침 textarea
  드래그 선택 중 손이 밖으로 나감) 그 반대일 때도 target 이 backdrop 으로 승격돼 모달을 닫았다 —
  사용자 관점 "down 만 해도 / up 만 해도 종료", 작성 중이던 지침이 통째로 사라진다.
- **어디:** `static/app.js` — `promptShareExpiry`(공유 링크 설정) · `confirmShareJoinable`(참여 허용
  확인) · `openShareDialog`(공유) · `openConversationSettings`(대화 설정). `static/app/sidebar.js` —
  `openFolderSettings`(폴더 설정) · `openMoveConversationDialog`(폴더로 이동). 요청은 '설정 모달'을
  지목했으나 형제 모달이 같은 결함을 공유하므로 전건 적용(부분 수정 시 같은 마찰 잔존).
- **무엇이 안 바뀌었나:** ESC 닫기 · × 버튼 닫기 · 모달 내용/레이아웃/CSS · 서버 계약 · 권한 ·
  스키마 — 전부 무변경(하네스가 ESC·× 경로 유지를 함께 단언). `click` 은 더 이상 dismiss 경로가
  아니지만 모달 내부 버튼의 `click` 핸들러는 무관(리스너가 backdrop 에만 붙었던 것을 교체).
- **§18.8 적대 패널이 1차 구현을 BLOCK 했고 그 지적을 반영했다** (사용자 지시로 ux·design
  subagent 경로 선택):
  - **P1-1 implicit pointer capture** — 터치·펜은 브라우저가 `pointerdown` 대상에 포인터 캡처를
    자동으로 걸어 `pointerup` 이 **뗀 위치와 무관하게** 그 대상으로 retarget 된다(마우스는 캡처
    없음). 1차 구현은 해제를 안 해서 터치에서 계약이 "누른 위치가 배경이면 닫힘" 으로 무너져
    **원 결함이 그대로 남아 있었다**(AC3 불성립). → 배경에서 시작한 제스처에 한해
    `releasePointerCapture` (패널 안 제스처의 캡처는 터치 텍스트 선택이 의존하므로 미간섭).
  - **P2-1 ghost click** — 1차는 `pointerup` 에서 노드를 제거해, 터치의 compat `click` 이 제거 후
    DOM 으로 히트테스트되어 backdrop **아래** 사이드바 항목을 눌렀다. → 실행을 `click` 단계로 이동.
  - **P3-2 멀티터치 간섭** → `pointerId` 추적 + `isPrimary === false` early-return.
  - **장전(armed) 잔류** (라운드2 — ux·design **양쪽이 독립적으로** 실제 헬퍼를 실행해 dismiss=1
    로 실증) — "배경에서 down+up 했는데 브라우저가 `click` 을 발행하지 않은" 제스처가 장전을
    무기한 남겨, 뒤이은 click 하나가 사용자가 누른 적 없는 모달을 닫았다(폴더 지침 작성분 소실 =
    이번 cycle 이 없애려던 바로 그 피해). → `pointerup` 이 `downOk` 를 즉시 소비 + `click` 이
    `armed` 를 소비(제스처 1회분) + **`e.isTrusted` 요구**(물리 제스처는 언제나 `pointerdown`
    으로 시작해 상태를 리셋하므로, 선행 pointerdown 없이 오는 click 은 정의상 합성).
  - **캡처 해제의 fail-open** → `hasPointerCapture` 선행 조건 제거, **무조건 시도 + throw 만
    삼킴**(메서드 부재·캡처 보고 차이 엔진에서 조용히 건너뛰어 구 결함으로 회귀하던 경로 봉인).
  - **`pointerup` 의 중복 `button === 0` 제거** — 누름 시점에 이미 걸렀고, `button` 을 `-1` 로
    보고하는 환경에서 정상 dismiss 가 조용히 죽는 쪽이 더 나쁘다.
  - **주석 정정** — "배경이 그 click 을 소비한다" 는 부정확(코드는 `stopPropagation` 미호출).
    실제 근거는 "터치 compat click 의 히트테스트가 dispatch 전에 끝난다" 로 교체.
  - **P2-2 backdrop 스크롤바 드래그** → `.share-mgr-backdrop` 에 `overflow` 선언이 없어(CSS 실확인)
    스크롤바가 생기지 않으므로 **N/A**. 실행이 `click` 단계라 이중으로 제외된다.
  - **P2-3 armed 고착**(창 밖 release) → `document` 레벨 리스너 추가 대신 click 게이팅으로 완화
    (창 밖에서 시작한 press 는 페이지 `click` 을 만들지 않는다).
  - **P3-3 순수 합성 `click` 으로는 더 이상 닫히지 않음** → 의도로 수용·주석 명시(물리 포인터
    제스처만 인정, ESC·`×` 상시 생존).
- **커버리지 정정(design 리뷰어 반증 수용):** "old 패턴 6곳 전수" 의 1차 근거는 식별자 `backdrop`
  키잉 grep 이라 **변수명의 부재만** 증명한 non sequitur 였다. `overlay` 로 명명된 동형 3곳이 남아
  있다 — `app/profile.js:306`(**사용자향** · `mousedown` 단독으로 닫힘) · `admin/usage.js:662`
  (mousedown) · `admin/audit.js:317`(click). 요청 스코프가 "좌측 항목 모달" 로 명시돼 있어 이번
  cycle 미적용, FUNCTION 표 + REPORT §8 원장에 file:line 등재 + 사용자 표면화.
- **Verification:** `tests/verify_modal_backdrop_dismiss.mjs` 신설 — 동작 18(실제 헬퍼 본문을 최소
  DOM 이벤트 shim 위에서 실행. shim 이 ① 이벤트 순서·target 공통조상 승격 ② implicit pointer
  capture ③ click 미발행 상호작용 ④ `isTrusted` 를 모델링) + 배선 30 = **48 pass / 0 fail**.
  **역검증 5종** — 각 변형이 정확히 의도한 단언만 red: 옛 `click` 단독(11) · 캡처 해제 삭제(1) ·
  `pointerup` 실행(3) · `downOk` 미소비(1) · `isTrusted` 미검사(1). ESM `node --check` PASS 2파일.
  `verify_*.mjs` 전수 red 21건 = main baseline 과 동일 집합(회귀 0).
  **PB-0008**: 실 Windows Chrome 150 + CDP **trusted 입력**(`Input.dispatchMouseEvent`/
  `dispatchTouchEvent`) **10/10 PASS**, 같은 하네스 `--negative` 에서 **사용자 보고 현상 3건 재현**.
  실행 자산은 `tests/pb0008_modal_backdrop_dismiss.py` 로 커밋(재현 가능).
- **Files:** `static/app.js`, `static/app/sidebar.js`, `tests/verify_modal_backdrop_dismiss.mjs`,
  `tests/pb0008_modal_backdrop_dismiss.py`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,REPORT,TEST}.md`,
  `docs/test-runs.d/20260806T1144-modal-backdrop-dismiss.md`,
  `docs/test-runs.d/evidence/modal-backdrop-dismiss-harness-live.png`, `.gitignore`.
- **캐시버스터:** `?v=dev` 고정 — `index.html` 편집 0 (ITEM-09 빌드 자동주입 regime, `inject_asset_stamp.py` + `deploy-web.sh` 가 배포 시 content-hash 주입).
- Timestamp: 2026-08-06T11:44:13+09:00
## CHG-20260806T1620-modal-dismiss-postdeploy 배경 dismiss POST-DEPLOY 라이브 실측 기록 (doc-only)
- 선행 cycle `CHG-20260806T1144-modal-backdrop-dismiss`(PR #1164, 배포본 `44627bad`)의 잔여였던
  "배포 후 라이브 실제 모달 육안 확인" 을 수행하고 `docs/test-runs.d/20260806T1144-modal-backdrop-dismiss.md`
  에 Run 3(PASS 13/13) + 증적 스크린샷 1장을 append. **코드 변경 0**.
- 라이브 4종(대화 설정·공유·폴더로 이동·폴더 설정) 각 3제스처 실측. 진입은 `page.evaluate` 함수
  호출이 아니라 **사이드바 `···` 메뉴 실제 클릭** — app.js 가 ES module 이라 opener 가 전역이
  아님을 실측으로 확인(`promptShareExpiry is not defined`).
- 라이브 데이터 변경 0(저장·전송·보관 미클릭, 임시 폴더 자가 생성·자가 삭제 + 잔재 0 단언).
- 미실측 2종은 진입에 실제 공유 링크 발급이 필요해 제외 — 사유를 fragment 에 명시.
- Files: `docs/{TASK,MODIFY,REVIEW,TEST}.md`, `docs/test-runs.d/20260806T1144-modal-backdrop-dismiss.md`,
  `docs/test-runs.d/evidence/modal-backdrop-dismiss-live.png`.
- Timestamp: 2026-08-06T16:20:00+09:00
## CHG-20260806T032732-share-sender-nickname 공유 링크 화면 발화자 배지 — 메시지별 발신자(닉네임) 표시
- `static/share.js`: `senderLabel(msg)` 신설 — **발화 시점에 각인된 사실일 때만 사람 이름**. 0순위 `attribution_inferred === true`(fork·제품전환 보정이 미각인 행에 원본 대화 owner 를 기입하며 남기는 추론 마커)는 이름·id 둘 다 미사용 → 3~4순위 강등. 1순위 `meta.sender_username`, 2순위 `사용자 <id>`(소유자명 오귀속 금지), 3순위 대화 소유자명(**1:1 로 확인된 대화 한정**), 4순위 종전 `사용자`. `renderMessage` 배지가 `roleLabel(msg.role)`(role 고정) 대신 이를 사용하고, `renderSharePointRail` 툴팁/aria(`who`)도 같은 단일 출처로 통일(부수적으로 rail assistant 라벨 `Assistant`→`어시스턴트`, `lang="ko"` 정합). `render()` 가 payload 로 `_shareOwnerUsername`·`_shareIsGroup`(미상=그룹, fail-closed) 갱신 — 메시지 렌더보다 선행. `_deferOverflowTitle` 신설: 배지 `title` 은 rAF 후 `scrollWidth > clientWidth` 일 때만 부여(무조건 걸면 전 말풍선에 화면 텍스트와 동일한 툴팁이 뜨고 AT 에 중복 낭독).
- `static/share.css`: `.share-role-badge` `inline-flex`→`inline-block` + `max-width:220px`/`overflow:hidden`/`text-overflow:ellipsis`/`white-space:nowrap`(inline-flex 는 blockify 돼도 block *container* 가 아니라 text-overflow 미적용 → 하드 클리핑). **`.share-message-time` 에 `flex:0 0 auto` + `nowrap` 추가** — 배지만 막으면 `overflow:hidden` 이 flex 자동 최소크기를 0 으로 만들어 축소 압력이 양쪽에 배분되고 **시각 표기가 2줄로 접힌다**(§18.8 ux F-1 실측 계산). ≤720px 은 `flex-wrap:wrap` + 배지 `max-width:100%` 로 절단 대신 줄바꿈(공통 접두사 계정명이 ellipsis 로 동일 문자열이 되는 것 차단).
- `routers/share.py`: `public_share_view` 응답 `conversation` 에 **`is_group` 불리언 1개** 추가(새 식별자·계정 정보 노출 0) + `_share_conversation_is_group` 신설. 프론트가 각인 없는 메시지에 소유자명을 붙여도 되는지 판정하는 유일한 신호이며 **fail-closed**(조회 실패·대화 행 부재 → 그룹 간주). `app._conversation_is_group` 은 실패를 False(비그룹)로 삼켜 본 용도와 실패 방향이 반대라 감싸지 않고 직접 조회한다.
- `routers/_conv_store.py`: 참여 알림 이벤트 배제 주석의 근거를 정정 — 이 배제가 지키는 것은 "**발화하지 않은** 멤버 명부" 이지 발화자가 아니다(발화 메시지의 `sender_username` 은 이제 화면 표시). 노출 경계 정본 포인터 추가.
- **발신자명 자체는 이전부터 노출 중이었다**: `/api/public/share/{token}` 응답 `messages[].meta` 에 필터 없이 실려 나갔다(라이브 익명 payload 실측 2026-08-06 + §18.8 패널 코드 재확증 — 배제 필터 3종 어디에도 sender 키 없음). 응답 shape 변경은 `is_group` 하나뿐, RBAC·스키마·마이그레이션 변경 0.
- 사용자 결정(2026-08-06): 노출 범위 = 모든 열람자(익명 포함) · 각인 없는 과거 메시지 = 대화 소유자명 폴백(그룹 오귀속 위험은 위 is_group 게이트로 제거).
- §18.8 적대 패널 2렌즈(security·ux) **CONCERN medium 5건 전건 in-cycle 흡수** — 상세·미반영 지적의 근거는 REVIEW `REV-20260806T032732-share-sender-nickname`. codex 채널은 사용량 한도 소진이라 사용자 1회 확인 후 subagent 패널로 대체(§18.8.2, 자체 SKIP 하지 않음).
- Tests: `tests/test_share_sender_nickname.py`(신규 — 배선 + 추론각인 배제 + is_group fail-closed + title 조건부 + 시각 표기 고정 + 백엔드 payload 계약) · `tests/verify_share_sender_nickname.mjs`(신규 — 배포 소스 함수 추출 실행, **17 케이스** 동작 검증).
- Verification: mjs **17/17** · pytest **2 passed** · `make test` 전 스위트 **exit=0**(1회차 `test_shutdown_finalizer` FAIL 은 `시간 예산 초과` 로그를 남긴 flake — 격리 재실행·전체 재실행 모두 통과, 본 cycle Python 무접촉) · ruff clean.
- Files: `unit/feature-0003-agent-web-ui/src/static/{share.js,share.css}`, `unit/feature-0003-agent-web-ui/src/routers/{share.py,_conv_store.py}`, `unit/feature-0003-agent-web-ui/tests/{test_share_sender_nickname.py,verify_share_sender_nickname.mjs}`, `unit/feature-0003-agent-web-ui/docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT}.md`, `unit/feature-0003-agent-web-ui/docs/test-runs.d/20260806T032732-share-sender-nickname.md`(§5.3 fragment), `docs/SECURITY.md`(§21.7 신설).
- 캐시버스터 수기 bump 없음 — `share.html` 은 `?v=dev` placeholder 고정이고 배포 시 `inject_asset_stamp.py` 가 content-hash 를 주입한다(ITEM-09 regime). `share.html` 편집 0.
- Timestamp: 2026-08-06T12:27:32+09:00
## CHG-20260806T045000-share-sender-postdeploy 공유 발화자 배지 PB-0008 라이브 실측 기록 (doc-only)
- `docs/test-runs.d/20260806T032732-share-sender-nickname.md`: POST-DEPLOY Run(**Environment: Windows-browser**) 7항목 PASS 기록으로 "미수행(이월)" 블록 교체 + frontmatter verdict 갱신. 코드 변경 없음.
- **왜:** 선행 cycle 의 시각 검증이 정적 자산 baked 구조상 배포 후로 미뤄져 있었다. 배포본 `ddbc6ebe`(web-a/web-b GIT_COMMIT 실측 일치 · 서빙 `share.js?v=24613708d61a`)에서 실측해 그 잔여를 닫는다.
- **결과:** 각인 메시지 닉네임 렌더 · **사용자 제보 메시지 실물 대조(종전 `사용자` → 현재 `admin`)** · rail 라벨 일치 · 긴 이름 주입 시 시각 표기 불변(ux F-1 실증) · title 조건부(F-2 실증) · 각인 0 대화 소유자명 미발동(security F-2 실증) · 콘솔 에러 0.
- **실측 발견(정직):** 공유 생성이 `is_group=true` 를 set 하므로 3순위 소유자명 폴백은 라이브에서 사실상 미발동(활성 공유 링크 6건 전수 `is_group=true`, 멤버 1명). 안전 방향이나 사용자 결정의 절반이 화면에 안 나타남 — 별 cycle 이월.
- Timestamp: 2026-08-06T13:50:00+09:00
## CHG-20260806T1830-modal-dismiss-siblings 배경 dismiss — 저장소 단일 primitive 로 통일(전 표면)
- **무엇:** 선행 cycle 이 `app.js` 안에 두었던 `bindBackdropDismiss` 를 **신설 공용 모듈**
  `static/modal-dismiss.js` 로 옮기고, 앱의 **모든** 배경 dismiss 표면을 그 정본에 배선했다.
  `app.js` 는 import 후 **re-export** 하여 `app/sidebar.js` 의 기존 import 를 무회귀 보존한다.
- **왜 별도 모듈:** ESM 번들이 둘(작업 화면 `app.js` / 관리 콘솔 `admin.js`)이라 한쪽에 두면 다른
  쪽은 복제할 수밖에 없다 — **그 복제가 이 결함을 만든 기전**이다(판정이 9곳에 흩어져 6곳
  `click`, 3곳 `mousedown` 으로 굳어 있었다).
- **어디 (전환 표면):**
  | 파일 · 함수 | 화면 | 변경 전 |
  |---|---|---|
  | `app/profile.js` `showProfileUsageConvModal` | 프로필 > 사용 내역 > 대화 목록 | `mousedown` 단독 |
  | `admin/usage.js` `showUsageConvModal` | 관리 콘솔 > 사용 기록 | `mousedown` 단독 |
  | `admin/audit.js` `openAuditPurgeModal` | 관리 콘솔 > 감사 > purge | `click` |
  | `graph/graph-core.js` `_metaGraphBindHelp` | 관리 콘솔 > 그래프 뷰 > 도움말 | `click` + 속성/클래스 판정 |
  | `app.js` `_bindSearchModalListeners` | 대화 검색 | **같은 계약의 손수 구현**(전용 상태 플래그 2개) |
  뒤 2건은 **사용자 요청 범위 밖**이나, 남기면 '정합' 이 성립하지 않아 함께 전환하고 완료 보고에
  명시했다. 검색 모달의 `state.searchModal.mousedownOnOverlay`/`mouseupOnOverlay` 는 제거했다.
- **의도적 미변경:** 프로필 드로어(`app.js` `profileBackdropEl`) — `#profileBackdrop` 과
  `#profileDrawer` 가 `index.html:410-411` 에서 **형제**라 둘 사이 드래그의 click target 이
  `<body>` 가 되어 backdrop 리스너에 닿지 않는다. **target 승격 결함이 구조적으로 성립하지 않음**
  (ux·design 두 리뷰어가 독립 검증). 드롭다운·컨텍스트 메뉴의 `document` 레벨 outside-click 해제는
  같은 뿌리지만 다른 UX 범주라 대상 밖 — 경계를 `modal-dismiss.js` 주석에 명시.
- **동반 하드닝 (§18.8 패널 지적):**
  - `app/profile.js`·`admin/usage.js` 는 loading→data 로 **재렌더**되는데, 이전 인스턴스를
    `remove()` 로만 치워 그때 붙인 `document` keydown 리스너가 **열 때마다 하나씩 샜다**. 이제
    이전 인스턴스의 `close()`(`overlay._modalClose`)로 닫아 리스너까지 회수한다.
  - `admin/audit.js` purge 모달에 **중복 인스턴스 가드**(`auditPurgeOverlay` id + prev 제거) +
    기준 날짜 입력 포커스. 없으면 겹쳐 뜬 오버레이의 중복 id 때문에 **위쪽 모달의 버튼에 핸들러가
    하나도 붙지 않아** 파괴적 플로우가 조작 불능이 됐다.
  - `close()` 가 참조하는 `onEsc` 를 **먼저 선언**하도록 순서 교정(잠재 TDZ 함정 제거).
- **회귀 잠금 재설계:** 하네스의 census 를 **파일 목록 하드코딩(33개 중 6개)** 에서
  `src/static/**/*.js` **재귀 walk** 로 바꾸고, 판정을 리스너 **핸들러 본문 경계** 안에서
  "수신자 자신을 `target` 과 비교하는가" 로 일반화했다(화살표/함수식·괄호 유무·`===`/`!==`·`&&`
  축약 무관). detector 자기검증 2건 포함 — 표기 변형 5종 검출 + **인접 리스너 오검출 안 함**
  (고정 lookahead 가 `app.js:1792` 의 이웃 keydown 본문을 물어오던 버그의 회귀 잠금).
- **Verification:** `verify_modal_backdrop_dismiss.mjs` **76 pass / 0 fail**. **뮤테이션 역검증
  6종** 전부 의도한 단언만 red — button 가드 제거 · isPrimary 가드 제거 · profile 재렌더 누수
  복원 · usage `close()` ESC 미해제 · **census 범위 밖 신규 파일에 옛 패턴 신설** · 부정형 표기.
  (앞의 두 뮤테이션은 교정 전 하네스에서 **생존**했다 — vacuous 단언이었다.) ESM `node --check`
  6파일 PASS · 전수 mjs red 21건 = main baseline 동일 집합 · PB-0008 실 Windows Chrome 10/10 ·
  `make test` 회귀.
- **Files:** `static/modal-dismiss.js`(신설), `static/app.js`, `static/app/profile.js`,
  `static/admin/usage.js`, `static/admin/audit.js`, `static/graph/graph-core.js`,
  `tests/{verify_modal_backdrop_dismiss.mjs,pb0008_modal_backdrop_dismiss.py}`,
  `docs/{TASK,MODIFY,FUNCTION,REVIEW,REPORT,TEST}.md`, `docs/test-runs.d/…`.
- **캐시버스터:** `?v=dev` 고정 — `inject_asset_stamp.py` 가 static 트리를 walk 하며 신규 파일의
  import specifier 까지 자동 스탬프(전역 content-hash 단일 값 → 모듈 단일 인스턴스 보장).
- Timestamp: 2026-08-06T18:30:00+09:00
## CHG-20260806T2010-modal-siblings-postdeploy 신규 전환 5종 POST-DEPLOY 라이브 실측 기록 (doc-only)
- 선행 cycle `CHG-20260806T1830-modal-dismiss-siblings`(PR #1168, 배포본 `2ab2b27e`)의 잔여였던
  "배포 후 신규 전환 5종 라이브 재확인" 을 수행하고 fragment 에 Run 4(PASS 16/16) + 증적 append.
  **코드 변경 0**.
- 실측 표면: 대화 검색 모달 · 그래프 뷰 도움말 · 감사 purge · 관리 콘솔 사용 기록 · 프로필 사용 내역.
  각 3제스처(AC1~AC3) + 감사 purge **중복 인스턴스 가드**(연속 2회 진입 시 오버레이 1개) 실측.
- 진입은 사용자 경로 그대로. 차트 요소는 SVG 라 `.click()` 이 없어 **좌표 기반 CDP trusted 클릭**.
- 라이브 데이터 변경 0(purge 미리보기·삭제 미클릭, 나머지는 읽기 전용 조회).
- Files: `docs/{TASK,MODIFY,REVIEW,TEST}.md`, `docs/test-runs.d/20260806T1830-modal-dismiss-siblings.md`,
  `docs/test-runs.d/evidence/modal-dismiss-siblings-live.png`.
- Timestamp: 2026-08-06T20:10:00+09:00
## CHG-20260806T2320-attach-version-diff 첨부 버전 diff 비교 화면 — 임의 쌍·다단계 (Major §12.3)
- **사용자 요청**: 대화 첨부의 여러 버전 간 diff 비교 화면. 직전/직후뿐 아니라 **여러 단계 차이가
  나는 버전 간** 비교도. 결정(AskUserQuestion): 전용 모달 + 2열/단일열 토글.
- **왜 신규인가**: 버전 체인·조회 API·"버전 N개 ▾" 목록은 이미 있었고(TASK-0274/0285,
  REQ-20260713), 없던 것은 **비교 자체**다 — `MetaJson.version_diff` 는 업로드 시점의 직전↔신규
  1쌍만 담고(LLM 컨텍스트용) 프론트 diff 렌더는 0이었다. 다단계 쌍은 사전 계산 대상이 아니다
  (쌍 수가 체인 길이의 제곱) → **요청 시점 계산**.
- **백엔드**: `_conv_store.py` 에 `_load_attachment_version_chain`(체인 로더 — `/versions` 의
  중복 SQL 을 추출·공유) + `_build_version_diff_view`(단일 `SequenceMatcher` opcode 패스에서
  unified 문자열과 좌우 정렬 rows 를 **함께** 산출) + 상수 3. `attachments.py` 에
  `GET /api/attachments/{attachment_id}/diff` 신설. `app.py` 는 5 심볼 rebind(§21.11 `app.X` 규약).
- **프론트**: `static/app/attach-diff.js` 신설(`openAttachmentDiffModal` — from/to 선택기 ·
  `⇄` 맞바꾸기 · 2열/단일열 토글(localStorage) · "동일한 줄도 모두 보기" · `reqSeq` 경쟁 가드) +
  `app/composer.js` `_renderAttachmentVersionsBox` 진입점 2종 + `css/chat.css` 스타일.
- **자체 적발 2건(출하 전 수정)**:
  - **D21 우회(P1)** — diff 행은 파일 **본문**이다. 초판은 승인 대기 계정 게이트가 없어
    `download_attachment`(403 bytes-deny)를 diff 로 우회할 수 있었다. 판정 기준을 metadata
    조회가 아니라 **본문 다운로드와 동형**으로 맞추고, 게이트를 원본 조회 **앞**에 두었다.
  - **체인 스코프 가정(P2)** — 체인 로더는 root 로 전체를 반환하고 "체인은 같은
    conversation·account 귀속" 을 **가정**했다(기존 `/versions` 도 동일). 그 전제가 깨진 행이
    하나라도 있으면 기준 첨부 게이트가 덮지 못한다 → `scope_row` 로 **필터**하고(fail-closed)
    걸러진 건수를 warning 으로 남긴다. 두 엔드포인트 모두 적용.
- **경계 판정**: 텍스트 계열(`text`/`csv` — `.sql` 포함)만 줄 diff. 바이너리는 `comparable:false`
  + 메타 비교로 **강등해 답한다**(빈 diff = "차이 없음" 오독 방지). 절단 3종(원본 cap ×2 · 행
  상한)은 응답 필드와 화면 배너 양쪽에 표면화(§16.7 G9-b).
- **산출물 재정합**: `gen-routemap.py` 재생성(223→224) · `codenav-lint` OK · route 골든 +1
  (added 1 / removed 0 / order drift 0).
- **검증**: pytest 신규 **22건** · 전수 회귀 exit 0 · **뮤테이션 역검증 7/7**(404→400 · 맥락 축약
  무력화 · 행 상한 무력화 · D21 게이트 제거 · scope_row 누락 · 스코프 필터 무력화) · 헤드리스
  mjs 신규 **57건** + 전수 mjs **44 suite OK** · `acorn-globals` 자유 식별자 0.
- **Files:** `src/routers/_conv_store.py`, `src/routers/attachments.py`, `src/app.py`,
  `src/static/app/attach-diff.js`(신설), `src/static/app/composer.js`, `src/static/css/chat.css`,
  `tests/test_attachment_version_diff.py`(신설), `tests/verify_attach_version_diff.mjs`(신설),
  `tests/route_snapshot_p5b.json`, `../../../docs/ROUTEMAP.md`,
  `docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT,TEST}.md`.
- **스키마·마이그레이션·RBAC 카탈로그 변경 0** · 기존 엔드포인트 응답 shape 무변경.
- **캐시버스터:** 신규 JS 의 import specifier `?v=dev` 고정 — 빌드 `inject_asset_stamp.py` 가
  content-hash 주입(수기 bump 금지).
- Timestamp: 2026-08-06T23:20:00+09:00
## CHG-20260807T0030-attach-diff-colgroup diff 표 열 폭을 colgroup 정본으로 (Minor §12.3)
- 선행 cycle `CHG-20260806T2320-attach-version-diff`(PR #1170, 배포본 `d46a6b04`)의 **POST-DEPLOY
  PB-0008 이 적발한 레이아웃 결함** 수정. 자동 게이트(pytest 22 · mjs 57 · verify-completion)는
  전부 통과했고 실 브라우저 캡처 판독에서만 드러났다.
- 근본 원인: `table-layout: fixed` 가 열 폭을 **첫 행**에서 가져오는데 맥락 축약 뷰의 첫 행이
  `gap`(`colspan=4`) 이라 개별 열 폭이 정의되지 않고 표가 균등 분할됨 — CSS `td` width 무시.
  라이브 실측 표 1136px / 네 열 전부 284px.
- 변경: `_appendColgroup` 신설(2열 4 col · 단일열 3 col) + CSS 정본을 `.attach-diff-col-*` 로
  이관 + `td` width 3건 제거(정본 이중화 방지).
- 재발 방지: `tests/headless/verify_attach_diff_geometry.py` 신설 — 실 chromium 에 실 CSS·실 렌더
  함수를 올려 열 폭을 숫자로 잠근다. **T7 이 colgroup 제거 시 [284,284,284,284] 를 재현**해
  가드가 그 결함을 실제로 잡는다는 것을 증명한다(라이브 실측치와 동일). mjs A1b 구조 가드 7건 동반.
- 검증: 헤드리스 기하 8/8 · mjs 하네스 65 PASS · 전수 mjs 44 suite OK · pytest 전수 회귀.
- Files: `src/static/app/attach-diff.js`, `src/static/css/chat.css`,
  `tests/verify_attach_version_diff.mjs`, `tests/headless/verify_attach_diff_geometry.py`(신설),
  `docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT,TEST}.md`, `docs/test-runs.d/…`.
- 백엔드·API·RBAC·스키마·마이그레이션 변경 0.
- Timestamp: 2026-08-07T00:30:00+09:00
## CHG-20260807T0200-attach-diff-ux 비교 모달 확대 · 줄번호 여백 · 중앙선 드래그 · gap 국소 전개 (Minor §12.3)
- 사용자 지적·요청 4건(2026-08-07, 스크린샷 동반): 모달이 작아 내용이 잘림 · 줄번호 열 여백 과다 ·
  좌우 2열 중앙선 드래그 · "동일한 N줄 생략" 클릭 시 국소 전개("모두 보기" 비활성 시).
- **줄번호 여백은 선행 결함과 같은 뿌리**: 사용자가 본 화면은 배포본 `d46a6b04` 로 열 폭이
  4등분돼 줄번호 열이 284px 였다(`CHG-20260807T0030-attach-diff-colgroup` 이 이미 수정·push 대기).
- **실측으로 확정한 함정**: `table-layout: fixed` 의 `col` 폭에서 Chrome 은 **퍼센트를 포함한
  `calc()` 를 무시**하고 auto 로 떨어뜨려 균등 분배한다(5형태 대조: `calc(0.3*(100%-4ch-24px))`
  468/468 무시 · `calc(30% - 12px)` 무시 · `30%` 281/655 honor · `300px` honor · `calc(2ch+12px)`
  honor). ⇒ 선행 colgroup 이 **줄번호에는 적용됐지만 좌우 code 열에는 조용히 무효**였다.
  좌우 폭은 렌더 후 실측 기반 **plain %** 로 지정하고 창 크기 변화 시 재적용한다.
- 변경: `_conv_store._build_version_diff_view` 가 gap 에 줄번호 범위 4필드 추가(additive) /
  `attach-diff.js` 에 `_linenoCh`·`_applySplitRatio`·`_gapRow`(버튼)·`_attachSplitHandle`·
  `expandGap` 신설 / `chat.css` 모달 94vh×(100vw-24px)·줄번호 padding 축소·splitter·gap 버튼.
- **드래그 결함을 하네스가 잡았다**: 초판은 `pointermove` 를 핸들에만 바인딩해 포인터가 11px
  핸들을 벗어나는 첫 이동(32px)에 이벤트가 끊겼다 — mousedown 은 성립하는데 비율은 그대로였다.
  저장소 기존 리사이저(`setupAttachSidePanelResize`)와 동형인 **document 레벨** 리스너로 교정.
- 하네스 방식 전환: 헤드리스·mjs 둘 다 함수 개별 추출 → **모듈 전체 로드**(import 만 스텁).
  추출 방식은 모듈 상수·상호 호출이 늘 때마다 깨졌다(로직 재구현 0 유지).
- 검증: 헤드리스 기하·상호작용 **22/22**(T7 colgroup 제거 시 균등분배 재현) · mjs **73 PASS** ·
  전수 mjs **44 suite OK** · pytest 신규 24건 · 정본 `make test` 전수.
- Files: `src/routers/_conv_store.py`, `src/static/app/attach-diff.js`, `src/static/css/chat.css`,
  `tests/headless/verify_attach_diff_geometry.py`, `tests/verify_attach_version_diff.mjs`,
  `tests/test_attachment_version_diff.py`, `docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT}.md`,
  `docs/test-runs.d/…`.
- RBAC·스키마·마이그레이션 변경 0. 응답은 additive(기존 필드 불변).
- Timestamp: 2026-08-07T02:00:00+09:00
## CHG-20260807T0320-attach-diff-height 비교 모달 높이를 고정에서 상한으로 (Minor §12.3)
- 선행 `CHG-20260807T0200-attach-diff-ux`(PR #1171, 배포본 `b23df012`)의 PB-0008 라이브 캡처
  **판독**에서 적발. 자동 44축은 전부 PASS 했으나 짧은 diff 에서 표 아래 빈 영역이 컸다
  (내용 y≈495 / 패널 940).
- 원인은 내 계약 자체 — `height: 94vh` **고정**. 요청은 "내용이 잘리지 않게" 였고 "항상 크게"
  가 아니었다. 게다가 그 고정을 **테스트가 요구사항으로 굳혔다**(선행 T9 의 높이 ≥88% 단언).
- 변경: `height: 94vh` 제거(= `max-height` 만). CSS 1선언. JS·백엔드 무변경.
- 테스트 재설계: T9 는 폭만 검사하고, 높이는 상한의 **양측**으로 나눴다 — T9b 짧은 diff 는 상한
  미만 · T9c 긴 diff(120행)는 상한에 닿음 · T9d 넘치면 표 컨테이너가 스크롤(페이지 스크롤 아님).
- 검증: 헤드리스 **25/25**(짧은 244px · 긴 846px=94vh · scroller True · doc overflowY False) ·
  전수 mjs 44 suite OK · pytest 무영향.
- Files: `src/static/css/chat.css`, `tests/headless/verify_attach_diff_geometry.py`,
  `docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/…`.
- Timestamp: 2026-08-07T03:20:00+09:00
## CHG-20260806T154100-attach-manage — 첨부 삭제(버전 선택)·복구·일괄 다운로드 (append-only 철회)

- 사용자 요청(2026-08-06)으로 `ADR-20260729T163000-attach-append-only` 를 supersede. Critical §12.3 — PLAN-APPROVED 2026-08-06.
- **백엔드** `routers/attachments.py`: `_manage_gate_for_conversation`(대화 단위 1회 해석 후 행 술어 반환) + `_account_can_manage_attachment` 신설 — 삭제·복구 인가를 열람 경계에서 분리(그룹 멤버 단독 거부, soft-deleted 행 통과). `delete_attachment` 에 `?scope=version|chain` + 최신 삭제 시 `_promote_latest_version` 승격 + `deleted_ids`/`deleted_count`/`promoted_id` 응답. `restore_attachment`(`POST /api/attachments/{id}/restore`) 신설 — `_is_restorable`(retention·purge 상태 판정) 통과분만 되살리고 대상 0건은 409. 부수 헬퍼 `_normalize_scope`(오타→400)·`_root_id_of`·`_load_attachment_chain`·`_retention_days`·`_mirror_attachment_ids`(PG dual-write). `get_attachment_versions` 응답에 `can_manage` 추가.
- **백엔드** `routers/conversations.py`: `list_conversation_attachments` 에 `?state=active|deleted` + `can_manage`. `_list_deleted_conversation_attachments`(휴지통, `DeletePending=1 AND UploadStatus <> 'deleted'`) 신설. `bulk_download_conversation_attachments`(`GET /api/conversations/{cid}/attachments/download`) 신설 — `format=zip|manifest` × `scope=latest|all` × `ids=` 부분 선택, `SpooledTemporaryFile` 스풀 ZIP, 상한 초과 413, 객체 fetch 실패는 안내 텍스트 엔트리로 표면화, `attachment.bulk_download` audit. 헬퍼 `_bulk_zip_max_bytes`·`_zip_entry_name`(버전 접미·중복 회피·zip-slip 방지)·`_audit_bulk_download`.
- **백엔드** `app.py`: 신규 헬퍼 7종 re-export.
- **프론트** `static/app/composer.js`: 목록 행 🗑(can_manage 시)·버전 행 🗑 · 삭제 범위 모달(`_openAttachDeleteModal`) · 휴지통 토글/렌더(`_setAttachListState`·`_renderTrashAttachmentList`) · 복구(`_performAttachRestore`) · 전체 다운로드 모달(`_openAttachDownloadDialog`·`_runBulkDownload`). 모달 껍데기는 `share-mgr-*` 재사용 + 배경 dismiss 는 저장소 단일 primitive(`bindBackdropDismiss`). 패널 열 때 목록 모드를 `active` 로 리셋(reload 중복 없음).
- **프론트** `static/index.html`: 헤더에 ⤓(전체 다운로드)·🗑(휴지통) 액션 + 휴지통 안내 문단. 안내 문구에서 "첨부는 대화에 계속 쌓입니다" 제거(사실이 아니게 됨).
- **프론트** `static/css/chat.css`: `.attach-side-panel-act` · `.attach-list-item-del/-restore` · `.attach-list-version-del` · `.attach-list-entry.is-trashed` · `.attach-manage-*` 모달. **선행 cycle 이 실측한 폭 회귀를 되풀이하지 않는다** — 메타줄 말줄임을 다시 넣지 않아 "버전 N개 ▾" 진입점을 보존하고, 새 버튼은 아이콘 1자 폭.
- **테스트** `tests/test_attach_manage.py` 신규 23건 — 인가 6 + AST 구조 가드 2(삭제/복구가 열람 헬퍼 미호출 · 열람 경로는 유지) + scope 3 + 승격 3 + 복구 판정 4 + ZIP 4 + 휴지통 3. `tests/route_snapshot_p5b.json` 골든 갱신(224→226, 신규 2 · 제거 0). `docs/ROUTEMAP.md` 재생성.
- 신규 테이블·마이그레이션·권한 코드 **0**.
- Files: `src/routers/{attachments,conversations}.py`, `src/app.py`, `src/static/app/composer.js`, `src/static/index.html`, `src/static/css/chat.css`, `tests/test_attach_manage.py`, `tests/route_snapshot_p5b.json`, `docs/{TASK,FUNCTION,DECISIONS,MODIFY,REVIEW,TEST}.md`, `docs/ROUTEMAP.md`.
- Timestamp: 2026-08-06T15:41:00+09:00
## CHG-20260806T181000-attach-manage-postdeploy — 삭제·복구·일괄 다운로드 POST-DEPLOY 실측 기록 (doc-only)

- `20260806T1541-attach-manage`(PR #1173, 배포 `5000e577`) 의 배포 후 라이브 검증. 실행 코드·정적 자산 변경 **0줄**.
- e2e 12/12 PASS(자체 테스트 대화 1건 생성→왕복→삭제, 기존 데이터 무접촉) + `WebAuditEvents` 행 생성 실측.
- 미검증 3건(버전 체인 2개 이상 · 공유창 window clip · 실 DOM 렌더)을 fragment 에 명시.
- Files: `docs/{TASK,MODIFY,REVIEW}.md`, `docs/test-runs.d/20260806T1541-attach-manage.md`.
- Timestamp: 2026-08-06T18:10:00+09:00
## CHG-20260807T0430-attach-diff-scroll-block 상호작용 스크롤 보존 + 문단 단위 하이라이트 (Minor §12.3)
- 사용자 보고·요청(2026-08-07): 상호작용(펼치기·모두보기·2열/단일열 교체) 시 스크롤이 최상단으로
  이동 / line 단위 외 **문단 단위 하이라이트**도.
- ① 원인: `_renderBody` 가 본문을 비우고 scroller 를 **새로 만들어** 스크롤 상태가 요소와 함께
  사라진다. 픽셀 복원은 행 수·높이가 바뀌면 어긋나므로 **줄번호 앵커**(`data-lno`)로 보존.
  버전 쌍 변경만 최상단으로(의도된 비대칭).
- ② `_assignBlocks` 로 연속 비-equal 행을 블록화(gap 이 끊는다) + accent·경계선·줄번호 배경.
  계산은 한 곳 — 2열·단일열이 같은 경계를 본다.
- **부수 적발·교정(선행 결함)**: `delete` 행의 빈 우측 셀이 danger 배경(`rgba(220,38,38,0.12)`)
  이었다 — 우측 파일에 없는 내용을 "삭제분 있음" 으로 읽게 만든다. `has-content` 로 좁히고
  빈 자리는 중립 filler. 내가 넣은 accent 규칙("내용 있는 쪽에만")과의 불일치도 함께 해소.
- 검증: 헤드리스 **44/44**(S1~S6 스크롤 · B1~B8 블록) · mjs **84 PASS** · 전수 mjs 44 suite OK ·
  뮤테이션 역검증 3/4(keepScroll off · _assignBlocks 무력화 · 빈 셀 accent).
  **rAF 제거는 하네스가 구별 못함 — 정직 표기**(방어적 조치, 코드 주석에 근거 명시).
- **리베이스 접합부(요청 범위 밖)**: 작업 중 `REQ-20260806-attach-manage`(PR #1173, 첨부
  soft-delete·복구·일괄 다운로드)가 먼저 랜딩해 리베이스. 코드 충돌은 자동 병합됐으나 **내 코드
  밑의 데이터 모델·같은 액션 영역에 변화가 생겼다** → 두 축을 실측하고 테스트로 고정했다.
  - ① **삭제한 버전이 비교 선택기에 남는가** → 아니다. 삭제 write 3경로(`attachments.py` user /
    `attachment_reconciliation.py` conv_soft / `conversations.py`)가 `DeletePending=1` 과
    `DeletedAt` 을 같은 statement 에서 세우고, 체인 조회 **양쪽**(MySQL 폴백 + PG 미러)이
    `deleted_at IS NULL` 을 건다. 읽어서 확인한 상태로 두지 않고 **V3**(PG 미러 필터)·**V3b**(두
    컬럼 동반 세팅 불변식)로 고정 — 새 삭제 경로가 `DeletedAt` 을 안 채우면 삭제한 버전이
    선택기에 되살아나고 그 실패는 조용하다. pytest **26 PASS**, 뮤테이션 양측 red.
  - ② **`⇄`(내 비교)와 `🗑`(#1173)가 같은 `.attach-list-version-actions` 를 공유**해 버튼이
    2→3개가 됐다. git 은 텍스트상 병합했지만 좁은 버전 박스(좌측 28px 들여쓰기)에서 성립하는지는
    아무도 재지 않았다 → `verify_attach_version_row_actions.py` 신설, 240~420px × 이름 2종
    **10 조합 A1~A5 통과**(넘침 0 · foot overflow 0 · 가로 스크롤 0 · 긴 이름이 버튼을 밀어내지
    않음). 뮤테이션(`min-width:64px`) → A2·A3 red. **내 어포던스가 병합 후에도 살아 있다.**
  - **W1 관측(고치지 않음)**: 버튼 3개 모두 WCAG 2.2 AA 최소 타겟(24×24) 미달(`⇄`17×17 ·
    `⬇`17×17 · `🗑`22×15). 병합이 만든 것이 아닌 **선행 상태**이고, 고치면 방금 랜딩한
    `attach-manage` 의 버튼 외형까지 바꾸므로 사용자 판단 대상으로 남긴다.
- Files: `src/static/app/attach-diff.js`, `src/static/css/chat.css`,
  `tests/headless/verify_attach_diff_geometry.py`,
  `tests/headless/verify_attach_version_row_actions.py`(신규),
  `tests/test_attachment_version_diff.py`, `tests/verify_attach_version_diff.mjs`,
  `docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/…`.
- 백엔드·API·RBAC·스키마·마이그레이션 0 (V3·V3b 는 기존 SQL 을 **단정만** 하고 바꾸지 않는다).
- Timestamp: 2026-08-07T04:30:00+09:00
## CHG-20260806T182000-attach-multi-upload — 폴더 단위 첨부 경로 · 중복 스킵 UX · 편집본 버전 체인 통합

- 사용자 보고(2026-08-06): "내용에 차이가 나타나는 파일들임에도 '동일한 파일' 이슈가 나타나며 블로킹".
  **실측 선행** — 지목된 22개 파일(`D:\…\dev-GunzPlus\Schema\*`)의 sha256 을 계산해 대화
  `20260806052006-3f48cbb7`(제목 `구 로그 테이블 DROP 유지 결정`)의 활성 첨부와 전수 대조한 결과
  **22개 전부 내용 동일**. dedup 판정은 정확했으므로 판정을 완화하지 않고, 실재 결함만 고쳤다(G7-a).
- **프론트** `static/index.html`: `#attachFileInput` 에 `multiple` — 없던 탓에 파일 대화상자가 1개만
  고르게 해 22개를 올리려면 22회 반복해야 했다.
- **프론트** `static/app/composer.js`:
  · change 핸들러가 `files[0]` → **선택 전량** 순차 업로드. value 리셋을 업로드 **전**으로 옮겨
    같은 파일 재선택이 change 를 발화하게 유지.
  · `_uploadComposerAttachment(file, {silent})` 가 결과 코드(`ATTACH_UPLOAD_RESULT`) 반환.
  · `_uploadComposerAttachments(files)` 신설 — 순차 업로드 + 집계. 2개 이상이면 개별 토스트를
    억제하고 **요약 1회**(`첨부 22개 중 6개 업로드 · 16개 변경 없음(건너뜀)`). 단건은 기존 UX 유지.
  · 중복 스킵 토스트를 **에러→정보** 톤으로 낮추고 문구를 "이미 최신입니다(내용 동일) — 건너뜀" 로
    (오류가 아니라 no-op 이다).
  · `.composer-wrap` drop 이 `#chatPane` 자손이면 업로드를 **위임**(chatPane 핸들러가 전량 처리).
    종전엔 같은 drop 이 두 핸들러에서 처리돼 **첫 파일이 2회 업로드**되고 두 번째가 dedup 에 걸려
    "이미 첨부된 파일입니다" 오탐을 냈다. chatPane 부재 시엔 자체 전량 처리로 폴백(기능 소실 방지).
  · `_versionedFilename` 을 idempotent 화(기존 `_v<n>` 접미 재부여) + 버전 박스 다운로드가 v2+ 에서
    그 이름을 쓰도록 배선 — 체인 통합으로 모든 버전이 같은 저장명을 갖게 된 부작용(로컬 덮어쓰기) 차단.
- **백엔드** `routers/_conv_store.py`(`_materialize_assistant_attachment_edits`): assistant 편집본
  저장 파일명을 `<stem>_v<n>.<ext>` → **원본 파일명 승계**. 버전 체인 스코프가
  `(conv, account, OriginalFilename)` 이라 이름이 갈리면 원본이 head 에서 빠지고 사용자 재업로드가
  **새 root(v1)** 를 만든다(라이브 실측: 한 대화에 분열 쌍 9건). LLM 이 준 filename 은 무시 —
  실행파일류 확장자 승격이 정의상 불가능해져 SEC-1 불변도 강화된다.
- **백엔드** `routers/attachments.py`(`download_attachment`): 응답 파일명만 v2+ 에서
  `_next_version_filename` 적용(DB 저장값 불변 → 체인 스코프·dedup 판정 무영향).
- **테스트** `tests/verify_attach_multi_upload.mjs` 신규 **28 PASS** — 정적 계약 5 · jsdom 실행 8
  (3개 선택→3개 업로드 · composer 드롭 첫 파일 1회 · chatPane 부재 폴백) · 집계/문구 9 · 저장명 3 ·
  **뮤테이션 역검증 3**(files[0] 복원 · drop 가드 제거 · multiple 제거 시 모두 검출).
  `tests/test_attachment_versioning.py`: N3 를 원본명 승계 계약으로 전환, N4 는 안전 확장자 불변 유지,
  **N5**(편집본 파일명 == 원본 = 체인 단일성) · **N6**(다운로드 표시명 분리) 신규.
- 신규 테이블·마이그레이션·권한 코드 · 라우트 **0**.
- Files: `src/static/index.html`, `src/static/app/composer.js`, `src/routers/_conv_store.py`,
  `src/routers/attachments.py`, `tests/verify_attach_multi_upload.mjs`,
  `tests/test_attachment_versioning.py`, `docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT,TEST}.md`.
- Timestamp: 2026-08-06T18:20:00+09:00
## CHG-20260806T200000-attach-multi-upload-postdeploy — POST-DEPLOY 라이브 실측 기록 (doc + 시나리오, 실행 코드 0줄)

- 배포본 `d3a520fd`(web-a/web-b/ask-worker/insight-worker/ops-scheduler 전부 동일 SHA, soak 통과)에서
  PB-0008 실 Windows Chrome 실측 T1~T6 **전건 PASS** — `docs/test-runs.d/REV-20260806T183000-attach-multi-upload.md` Run 4.
- 신규 시나리오 2종: `tests/win-browser-attach-multi-upload.scenario.json`(기능 6축) ·
  `…-visual.scenario.json`(토스트·첨부 패널 판독 캡처). 둘 다 자체 테스트 대화만 만들고 끝에 보관 처리한다.
- T4 가 핵심 — composer 영역 드롭에서 첫 파일이 서버에 **1 row**(수정 전 기전이었던 이중 처리·오탐 토스트 소멸).
- 정직 표기: 토스트 프레임 캡처는 2.2초 TTL 로 미확보 → `is-visible` + computed 배경색 실측으로 대체.
  AC-AMU-4·5(편집본 승계)는 실 LLM 왕복이 필요해 라이브 실측 제외(pytest N3/N5/N6 로 잠금).
- Files: `docs/{TASK,MODIFY,REVIEW,FUNCTION}.md`, `docs/test-runs.d/REV-20260806T183000-attach-multi-upload.md`,
  `tests/win-browser-attach-multi-upload{,-visual}.scenario.json`.
- Timestamp: 2026-08-06T20:00:00+09:00
## CHG-20260807T0620-attach-diff-unified-bg 단일열 줄 배경 소실 회귀 수정 (Minor §12.3)

- **자기 적발 회귀**: 직전 cycle(`CHG-20260807T0430-attach-diff-scroll-block`)이 줄 배경을
  `.has-content` 로 좁힐 때 `_renderSplit` 에만 클래스를 부여해, 단일열의 내용 있는 추가/삭제
  줄이 danger/ok 를 잃고 `rgb(240,239,234)`(내가 "대응 내용 없음" 용으로 도입한 중립 filler)를
  받았다. **의미가 반대로 뒤집힌다** — 내용이 있는데 "없음" 색이 된다.
- 수정: `_renderUnified` 의 code 셀에 `text != null` 일 때 `has-content` 부여(1줄).
  패딩 행(text==null)은 filler 유지 — 경계 양측이 각각 옳게 동작한다.
- **재발 차단**(이번 결함의 기전 = 렌더러 둘 중 한쪽만 규칙 준수):
  - 헤드리스 **B9**(단일열 변경 줄이 중립 filler 아님) · **B9b**(delete=danger / insert=ok)
  - mjs **A1d** 4건 — `has-content`/`has-block` 부여 지점 **개수**를 세어 한쪽 누락 적발 +
    게이트 형태 + CSS 반대편(filler) 규칙 실재
- 검증: 헤드리스 **46/46** · mjs **88 PASS** · 뮤테이션 **4/4**(수정 되돌림 → B9·B9b·A1d×2 red).
- Files: `src/static/app/attach-diff.js`, `tests/headless/verify_attach_diff_geometry.py`,
  `tests/verify_attach_version_diff.mjs`, `docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT}.md`,
  `docs/test-runs.d/…`.
- CSS·백엔드·API·스키마 0.
- Timestamp: 2026-08-07T06:20:00+09:00
## CHG-20260807T010301-doc-sync-rn-0807 (2026-08-06 블록) 릴리즈노트 콘텐츠 — 신규 1블록 9항목 prepend(첨부 삭제·복구·일괄 반출 · 버전 diff 비교 · 다중 첨부 · 전달 정직성 · 공유 발신자 · 배경 dismiss · 발췌 명시)
- 사용자 노출 릴리즈노트(`static/release-notes-data.js`) 최상단에 신규 date "2026-08-06" 블록(9 items: new/work 3 · improved/work 2 · fixed/work 3 · fixed/common 1) prepend + `generated` "2026-08-05"→"2026-08-06". 기존 43 블록 전량 보존(releases 43→44). 08-06 블록이 아직 없었으므로 append 아닌 신규 prepend.
- 평이화/비노출: feature-id·§번호·PR#·commit sha·모듈/함수명·테이블명·내부 설정키·ADR 번호·PB-0008·ZIP/audit/retention 등 내부 어휘 누출 **0**(19 패턴 정규식 기계 검증). UI 라벨은 실코드 대조 — `app/composer.js:940`(`⇄ 버전 비교`)·`:1121-1122`(`최신 버전(vN)만 삭제`/`전체 버전 삭제 (N개)`)·`:1259`(`최신 버전만`/`모든 버전`)·`:562`(`이미 최신입니다(내용 동일)`)·`:779`(배치 요약)·`app/attach-diff.js:245`(`동일한 N줄 생략 — 펼치기`)·`:566-569`(`좌우 2열`/`단일열`)·`index.html:383-384`(⤓·🗑 아이콘 전용 — 가시 텍스트 없음)·`app.js:3346`(`화면에는 이 단계 결과의 앞부분만 표시됩니다`).
- 캐시버스터 수기 bump 없음(빌드 주입 메커니즘 — ITEM-09). `index.html`/`admin.html` 무변경.
- Verification: `node --check` PASS · `verify_release_notes.mjs` **34 pass / 0 fail**(변경 전 baseline 동일) · 블록 순서·항목 enum(type/area)·스키마 외 키 0·기존 블록 보존 확인 · 내부용어 누출 0.
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).
- Reason: changed paths are docs + 비-정책 static data only — 코드/스키마/권한 변경 0.
- Timestamp: 2026-08-07T01:03:01+09:00
## CHG-20260806T182500-attach-suffix-toggle 다운로드 파일명 버전 접미사 토글 (Minor §12.3)

- 사용자 요청(2026-08-06): 첨부 다운로드 시 `_v2`·`_v3` 접미 포함 여부를 체크박스로 고르게 —
  **단일·전체 다운로드 모두**.
- **전제 정정(실측)**: 접미는 다운로드 시점에만 붙는 게 아니었다. AI 편집본은 **저장명 자체**가
  `report_v2.csv`(`_next_version_filename`) 라 최신본 1개를 받아도 접미가 남는다. "전 버전
  다운로드의 부착을 끄는" 스위치로 좁게 만들었다면 사용자가 겪는 대부분의 경우를 못 잡는다.
- **동반 적발(이중접미)**: 규칙이 서버 `_zip_entry_name`(무조건 부착)과 프론트
  `_versionedFilename`(무조건 부착) 두 벌로 있어, 저장명에 이미 `_v2` 가 있는 AI 편집본을
  `scope=all` 로 받으면 **`report_v2_v2.csv`** 가 나왔다. 토글과 함께 정합화했다.
- **백엔드** `routers/_conv_store.py`: 규칙 정본 `_download_filename_with_version(raw,
  version_number, mode)` 신설 — `keep`(그대로) / `strip`(`_v<VersionNumber>` **일치 시에만**
  제거) / `force`(떼고 붙여 idempotent). 파라미터 정규화 `_normalize_version_suffix_mode` —
  미지의 값은 `""` 를 돌려 caller 가 400 을 내게 한다(기본값 격하 금지).
- **백엔드** `routers/attachments.py`: `download_attachment` 에 `?version_suffix=`(기본 `keep`)
  + 응답 헤더 `X-Attachment-Download-Name`(최종 이름, percent-encoded UTF-8). 프론트가
  fetch+blob 으로 저장해 `Content-Disposition` 이 무시되므로 최종 이름을 별도 헤더로 준다.
- **백엔드** `routers/conversations.py`: `_zip_entry_name` 의 `with_version: bool` → `mode: str`
  (공용 규칙 위임, id 충돌 fallback 유지). `bulk_download_conversation_attachments` 에
  `?version_suffix=` 추가 — **미지정 기본은 scope 별 종전 동작**(all→force, latest→keep)이라
  파라미터를 모르는 호출자의 결과가 안 바뀐다. manifest 응답에 `download_filename` 추가 +
  `url` 에 파라미터 전파.
- **프론트** `static/app/composer.js`: `_versionedFilename` **제거**(규칙 두 벌 해소).
  `_attachVersionSuffixIncluded`/`_setAttachVersionSuffixIncluded`(localStorage
  `dqa.attachDownloadVersionSuffix`) + `.js-attach-suffix-toggle` 클래스로 패널·모달 체크박스
  즉시 동기화. `_downloadAttachmentById(…, opts)` 가 `?version_suffix=` 를 싣고 응답 헤더의
  이름을 채택(헤더 없으면 인자 fallback). `_runBulkDownload` 는 zip·manifest 양쪽에 파라미터
  전파. `_bindAttachPanelManageControls` 가 저장된 선택으로 체크박스를 초기화한다(HTML
  `checked` 만 믿으면 표시와 동작이 어긋난다).
- **프론트** `static/index.html`·`css/chat.css`: 패널 체크박스 `#attachSidePanelSuffixOpt` +
  `.attach-side-panel-opt`(note 와 같은 여백, 240px 에서 두 줄로 접힘). 첨부 0건·휴지통에서는 숨김.
- 신규 권한·테이블·마이그레이션 **0**. 기본값이 종전 동작이라 미사용자 영향 0.
- 검증: 신규 pytest 33건(`tests/test_attach_suffix_toggle.py` — 엔드포인트 배선 B1~B6 포함) + 기존 `test_attach_manage.py`
  의 `with_version=` 9곳을 `mode=` 로 갱신.
- Files: `src/routers/{_conv_store,attachments,conversations}.py`, `src/app.py`,
  `src/static/{index.html,app/composer.js,css/chat.css}`,
  `tests/{test_attach_suffix_toggle,test_attach_manage}.py`,
  `docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260806T1825-attach-suffix-toggle.md`
- **§18.8 패널 흡수 (codex 할당량 소진 → 사용자 승인 후 subagent 대체, §18.8.2)**:
  - security PASS + P3 2건 — 단일 다운로드 헤더에도 ZIP 과 같은 경로 성분·제어문자 정제 적용,
    파라미터 400 을 `_require_account` 뒤로 이동(미인증이 401 대신 400 을 받던 순서 역전).
  - backend/qa BLOCK → 해소 — ① **핵심 배선 행위 테스트 0건**(ZIP 이 토글을 무시하도록 만들어도
    전건 통과했음이 뮤테이션으로 실증) → 라우트를 그대로 호출해 ZIP namelist·manifest JSON 을
    보는 B1~B6 신설(같은 뮤턴트로 red 재확인) ② 소스 문자열 단정 완화(공백 한 칸·포매터에 거짓
    적색) ③ `rsplit(".",1)` → `os.path.splitext`(선행점 `.env`·끝점 `a.` 이름 파괴) ④ ZIP 이 실패
    행의 이름을 소비하지 않아 manifest 와 재배정이 어긋나던 것 → 이름을 루프 선두에서 확정
    ⑤ `_normalize_version_suffix_mode` 가 `default` 를 검증하지 않던 것 → allowlist 밖이면 ValueError.
  - ux BLOCK → 해소 — ① **P1**: `모든 버전` 라디오의 정적 힌트가 토글 OFF 에서 체크박스와 정면
    모순(사용자 대면 거짓 진술) → 두 안내를 한 함수가 함께 갱신 ② localStorage 쓰기 실패 시
    표시-집행 괴리 → 세션 메모리 폴백 ③ 탭 간 동기화 → `storage` 이벤트 ④ 충돌 경고 `aria-live`
    ⑤ 경고 게이트를 scope 로 좁히던 것 해제 + "구분 번호"→"파일마다 다른 번호" ⑥ 모달 체크박스
    9px 내어쓰기 정렬 + 힌트 자리 예약(높이 20px 변동 → 1px).
  - **라벨 정정**(계약 정합): "…버전 표시(_v2) **포함**" → "**유지**". 켜도 없던 표시를 새로 만들지는
    않는다 — 사용자가 같은 이름으로 재업로드한 버전은 저장명에 애초에 접미가 없다. FUNCTION 의
    "어느 버튼으로 받아도 이름이 같다" 도 "같은 범위에서는" 으로 정정.
- **rebase 정합 (main `attach-multi-upload` 흡수)**: 머지 대기 중 main 이 단일 다운로드에
  "v2 이상은 응답 파일명에만 버전 접미 부착"(`_next_version_filename`)을 도입했다 — 저장명이
  원본명을 승계하는 사용자 재업로드 체인에서 구버전이 로컬 최신본을 덮어쓰는 문제 때문.
  이는 backend/qa 패널이 지적한 P2("토글 ON 인데 사용자 재업로드 체인에는 접미가 안 붙는다")를
  main 이 먼저 해결한 것이라, 그 규칙을 **`auto` 모드로 흡수**해 규칙 함수 하나로 통일했다:
  단일·`scope=latest` 기본 = `auto`, `scope=all` 기본 = `force`. 프론트의 `_versionedFilename`
  (main 이 버전 이력 행에도 쓰도록 확장한 상태)은 제거하고 서버가 준 이름을 쓴다.
- Timestamp: 2026-08-06T18:25:00+09:00

## CHG-20260807T004500-attach-suffix-toggle-rebase main `attach-multi-upload` 계약 흡수 (Minor §12.3)

- 머지 대기 중 main 이 단일 다운로드에 "v2 이상은 **응답 파일명에만** 버전 접미 부착"을 도입했다
  (`attachments.py` 의 `_next_version_filename` 호출) — 저장명이 원본명을 승계하는 사용자 재업로드
  체인에서 구버전을 받으면 로컬 최신본을 덮어쓰기 때문. rebase 충돌 5파일(코드 2 · 문서 3).
- 이 규칙은 §18.8 backend/qa 패널이 지적한 P2("토글 ON 인데 사용자 재업로드 체인에는 접미가
  안 붙는다")를 main 이 **먼저 해결한 것**이라, 내 `keep` 기본을 그대로 두면 미지정 호출자가
  main 과 다른 이름을 받는다.
- 변경: 규칙 함수에 **`auto`** 모드 추가(v1=저장명 그대로 / v2+=정확히 하나의 `_v<n>`) 후 경로
  기본을 옮겼다 — 단일 `auto` · 일괄 `scope=latest` `auto` · `scope=all` `force`(한 압축에 v1 까지
  들어가므로 v1 도 구분 필요). 프론트는 `_versionSuffixMode` 가 ON 일 때 `keep` 대신 `auto` 를 쓴다.
- main 이 버전 이력 행에도 쓰도록 확장했던 프론트 `_versionedFilename` 은 제거하고 서버가 준
  이름(`X-Attachment-Download-Name`)을 쓴다 — 규칙 두 벌이 이 cycle 의 출발점이었던 결함.
- **부수 이득(실측)**: 저장명에 접미가 없는 사용자 재업로드 v2(`T_gunzgame_account.sql`)에서
  종전엔 ⬇=`…account.sql` / ⤓ latest=`…account.sql` 였다가 main 변경 후 ⬇ 만 `_v2` 가 붙어
  어긋났는데, 이제 **양쪽 모두 ON=`…account_v2.sql` / OFF=`…account.sql`** 로 일치한다.
- 테스트: A1~A4 신설(auto 규칙 · 단일 미지정 기본이 main 재현 · ⬇↔⤓ latest 이름 일치 · auto
  기본 하에서도 OFF 가 접미 제거). 신규 총 37건.
- Files: `src/routers/{_conv_store,attachments,conversations}.py`, `src/static/app/composer.js`,
  `tests/test_attach_suffix_toggle.py`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md`,
  `docs/test-runs.d/20260806T1825-attach-suffix-toggle.md`
- **선행 테스트 1건 갱신** (`test_attachment_versioning.py::test_n6`): main 이 만든 그 테스트는
  `download_attachment` 소스에 `_next_version_filename` 과 `_dl_version > 1` 이라는 **문자열이
  있는지**를 봤다. 계약(v2 이상만 접미)은 `auto` 가 그대로 지키지만 수행 주체가 규칙 함수로
  옮겨져 red 가 됐다 — **같은 계약을 지키는 리팩터링에 red 를 내는** 형태라(§18.8 backend/qa
  패널이 지적한 그 패턴) 결과를 보는 단정으로 바꿨다: 규칙 함수의 실제 반환값(v2→`_v2`,
  v1→원본명) + 라우트의 미지정 기본이 `auto` 인지.
- Timestamp: 2026-08-07T00:45:00+09:00
## CHG-20260807T012000-attach-suffix-toggle-postdeploy 배포 완료 기록 (doc-only)

- PR #1183 머지 → main `abdf13bd` → `make deploy-web` **exit 0**(web 롤링 + soak + 워커군
  `mysql-ai-agent:abdf13bd` + gateway 드리프트 없음).
- 라이브 서빙 자산 확인: `attachSidePanelSuffixToggle`·`_download_filename_with_version`·
  `ATTACH_SUFFIX_LABEL` 존재 + 캐시 스탬프 `chat.css?v=3a7d33acaddd`.
- POST-DEPLOY PB-0008 **31 step 전건 PASS** — 배포본 이미지를 **bind-mount 없이** 띄운 컨테이너
  (정적 자산이 이미지에 baked 되므로 소스 마운트로는 이 축을 못 본다). 라이브 트래픽 무접촉.
- 코드 변경 0 (doc-only).
- Files: `docs/{TEST,REPORT,MODIFY}.md`, `docs/test-runs.d/20260806T1825-attach-suffix-toggle.md`
- Timestamp: 2026-08-07T01:20:00+09:00
## CHG-20260806T1853-ai-claude-feature-0003-attach-diff-syntax — 첨부 버전 diff 파일 유형별 구문 하이라이트

- **요청**: "첨부파일의 버전 간 diff 를 비교하는 화면에서 파일 유형에 따른 확장 하이라이트(SQL
  예약어 등)" (사용자, 2026-08-06). 범위 = SQL + 구조화 데이터 우선, 차후 확장 가능한 구조.
- **프론트(신규)** `src/static/code-highlight.js`: 저장소 단일 primitive. 언어 레지스트리
  `LANGS`(sql/json/yaml/xml/csv/tsv — `{label, exts, tokenize}`) · `detectCodeLanguage(filename)`
  (마지막 확장자만·소문자·경로/쿼리 제거) · `tokenizeCodeLine` · `paintCodeInto`(textContent 전용,
  innerHTML 경로 0) · `codeLanguageLabel`. **SQL 예약어/타입 Set 의 정본**이 여기로 이전.
- **프론트** `src/static/app.js`: 로컬 `SQL_HL_KEYWORDS`/`SQL_HL_TYPES`(32줄) 삭제 → code-highlight
  import(정본 단일화). `detectCodeLanguage`/`paintCodeInto`/`codeLanguageLabel` re-export
  (`modal-dismiss.js` 와 동형 패턴). 기존 `sqlTokenizeToFragment`·`sql-tok-*` 는 **무변경**.
- **프론트** `src/static/app/attach-diff.js`: `_paintCell` 신설 — 두 렌더러(`_renderSplit`·
  `_renderUnified`)가 같은 함수로 code 셀을 칠한다. 언어는 파일명 1회 판정. `HIGHLIGHT_KEY`
  localStorage(기본 켬·끈 상태만 저장) + `.attach-diff-hl` 토글(감지 시만 노출·`aria-pressed`).
  off 는 `renderOpts().lang = null` 이라 종전 평문 경로와 구조적으로 동일.
- **CSS** `css/base.css`: `--code-tok-{keyword,type,func,key,string,number,var,comment,punct}` 9변수
  (팔레트 정본 — 전역 다크 도입 시 이 6줄만). diff 행 배경이 초록/빨강 12% 알파라 string=앰버
  `#b45309` · number=로즈 `#be185d` 로 색상군을 분리.
  `css/chat.css`: `.attach-diff-code .code-tok-*` 13규칙 + `.attach-diff-hl` pill(`is-active`).
- **테스트** `tests/verify_attach_diff_syntax_highlight.mjs` 신규 **77 PASS** — A 판정 14 · B 토큰 28 ·
  C 무손실 2(표본 13 + **결정적 PRNG fuzz 1,200**) · D XSS 7 · E 렌더 통합 19 · F CSS·정본 7.
  `tests/verify_attach_version_diff.mjs`: 하이라이트 primitive 를 **실물 주입**(스텁 금지 — 렌더가
  span 을 만드는지가 하네스에서 사라지지 않게) + `_paintCell` 로드 단언 → **85 PASS**(회귀 0).
- **적발·수정(초판 결함)**: CSV/TSV 토크나이저에 catch-all 대안이 없어 **짝 없는 따옴표 1글자가
  소실**(fuzz 152/1,200). diff 뷰어는 깨진·잘린 원본도 받으므로 무손실이 계약 → `([\s\S])` 추가.
- **§18.8 패널 흡수(BLOCK 2 + CONCERN 1 → P1 4·P2 7·P3 4 전건)**:
  - `css/base.css` 팔레트 6종 명도 강하 + `number`→teal `#0f766e` + `var`→보라 `#6b21a8`
    (27조합 AA 전면 통과, 최저 4.54). `css/chat.css` — delim 배경 칩 제거→`font-weight:700`,
    `key`/`tag` 의 600 제거(keyword 만), `.is-equal` 행 토큰 `opacity:.78`.
  - `app/attach-diff.js` — 토글을 pill→**checkbox**(`.attach-diff-hltoggle` label + `.attach-diff-hl`
    input, `aria-pressed`·`is-active`·title 제거), 라벨 "강조"→"**구문 색**", 노출 판정을
    `syncHlToggle(data)` 로 **렌더 결과 기반**(comparable/identical/rows.length) — load 성공·실패·
    `from===to` 3경로 배선.
  - `code-highlight.js` — XML `inTag` 상태(산문 오색 차단) · YAML bool 스칼라 앵커 ·
    성능 4곳(YAML_KEY_RE 문자클래스 중복 제거+반복 상한+`:` 없는 줄 skip / T-SQL `[…]` 문자집합 /
    문자열 닫는 인용부호 optional) → 최악 7.99ms→**0.609ms**, 성장률 1.92× · 레지스트리 도달성 주석.
  - `tests/verify_attach_diff_syntax_highlight.mjs` **77→108건** — G(팔레트 대비 계산 5) ·
    H(토글 실구동 12 — 실제 모달+apiFetch 스텁으로 셀 span 수·저장·복원) · I(성능 회귀 2) ·
    B29~B36(오색 negative 8) 신설, E10~E14 를 checkbox 계약으로 갱신.
- 백엔드·API·RBAC·스키마·마이그레이션·신규 권한 **0**. 라우트 **0**.
- Files: `src/static/code-highlight.js`, `src/static/app.js`, `src/static/app/attach-diff.js`,
  `src/static/css/base.css`, `src/static/css/chat.css`,
  `tests/verify_attach_diff_syntax_highlight.mjs`, `tests/verify_attach_version_diff.mjs`,
  `docs/{TASK,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260806T1853-attach-diff-syntax.md`.
- Timestamp: 2026-08-06T21:30:00+09:00 (패널 흡수 반영)
## CHG-20260806T200000-attach-chain-merge — 분열 첨부 체인 병합 도구 + 첨부 날짜 compact 표기

- 사용자 지시(2026-08-06): 갈라진 첨부를 하나의 체인으로 병합(넓으면 최근 1주일) + 첨부 날짜 compact 출력.
  선행 cycle `attach-multi-upload` 이 분열 **기전**을 막았고, 본 cycle 이 **이미 갈라진 데이터**를 정리한다.
- **신설** `scripts/attach_chain_merge.py`: 논리 파일 = `(ConversationId, AccountId, base(OriginalFilename))`
  (`base` = 끝의 `_v<n>` 접미 제거). 그룹을 CreatedAt 오름차순으로 정렬해 root/VersionNumber 재부여 +
  OriginalFilename 통일 + FilenameHmac 재계산 + SupersededAt 을 **다음 버전의 CreatedAt** 으로 스탬프
  (최신 1건만 NULL). **기본 dry-run**, `--apply` 로만 반영. 단일 트랜잭션 + `UNIQUE(root, version)`
  회피 **2단계 UPDATE**(오프셋 → 최종) + 스냅샷 JSON·**롤백 SQL** 생성 + PG 미러 동기화 +
  사후 재검증(잔여 0 아니면 exit 2) + `--rollback <snapshot>` 복원 경로. `--days N` 으로 범위 한정.
  `ObjectKey`·MinIO 객체·본문·`Sha256` 은 불변(파일 실체 무이동).
- **범위 판단**: 전수 실측 결과 활성 780 row 중 분열 **62 논리파일 / 155 row / 14 대화**(최근 7일은
  25/67/4). 155 row 는 넓지 않다고 보아 **전체 수행**하고 `--days 7` 경로는 보존했다.
- **제외 규칙**: base 이름 row 없이 `_v<n>` 이름을 사용자가 직접 올린 것만 모인 그룹은 병합하지 않는다
  (사용자가 고른 이름일 수 있음 — 실측 0건이나 가드 유지). 제외분은 사유와 함께 출력·스냅샷 기록.
- **프론트** `static/app/composer.js`: 첨부 목록 메타줄에 compact 시각 칩(오늘 `14:20` / 올해 `8/6` /
  그 외 `25/8/6`, 전체 시각은 `title`) + 버전 이력 행의 역할 뒤에 시각. 백엔드 무변경 —
  `created_at` 이 이미 응답에 있었다.
  ⚠️ **시간대 실측**: `CreatedAt` 은 MySQL `NOW()` 기반 **로컬(KST) naive** 라 오프셋 없는 문자열을
  그대로 `new Date()` 에 넘겨야 맞다(18:50 업로드 → `2026-08-06T18:50:29` 확인). 선행 cycle 의
  `restorable_until` 은 UTC 라 `Z` 보정이 필요했던 **반대 사례** — 필드마다 다르므로 주석·테스트로 고정.
- **테스트** `tests/test_attach_chain_merge.py` 신규 **17건**(base_name · 무의미 write 0 · 편집본 흡수 ·
  분열 재결합 · SupersededAt 체인 · 사용자명 제외/미과잉 · days 범위 · 대화·계정 경계 · 2단계 UPDATE
  순서 · 실패 롤백) · `tests/verify_attach_date_compact.mjs` 신규 **18건**(포맷 6 · 시간대 3 · 배선 6 ·
  뮤테이션 역검증 3).
- 스키마·마이그레이션·RBAC·엔드포인트 **0**.
- Files: `scripts/attach_chain_merge.py`, `src/static/app/composer.js`,
  `tests/{test_attach_chain_merge.py,verify_attach_date_compact.mjs}`,
  `docs/{TASK,FUNCTION,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/…`.
- Timestamp: 2026-08-06T20:00:00+09:00
## CHG-20260807T003000-attach-chain-merge-rebase — 형제 cycle 결정 흡수 (rebase 정합)

- rebase 중 형제 cycle `REQ-20260806-attach-suffix-toggle`(PR #1183, main 선반영)과 충돌.
  그 cycle 은 프론트 `_versionedFilename` 을 **제거**하고 저장명 규칙의 권위를 서버로 모았다
  (`X-Attachment-Download-Name` · manifest `download_filename`). 규칙이 두 벌이면 토글을 끈 뒤
  한쪽 경로에만 접미가 남고 AI 편집본이 `report_v2_v2.csv` 가 되기 때문.
- **그 결정을 존중**해 선행 cycle 에서 내가 넣었던 `_versionedFilename` idempotent 개선을
  되살리지 않고 **삭제**했다 — 함수가 사라진 뒤 되돌리면 형제 결정을 뒤집는 dead code 부활이다.
  본 cycle 이 추가하는 날짜 함수 3종만 보존.
- **main red 수리**: 형제 cycle 이 함수를 지우면서 그 함수를 추출하던
  `tests/verify_attach_multi_upload.mjs`(선행 cycle 산출물)를 갱신하지 않아 **main 에서 하네스가
  실행 불가**(`함수 미발견: _versionedFilename`) 상태였다. 같은 파일을 다루는 본 cycle 에서 수리:
  (D) 축을 "저장명 생성 함수가 프론트에 없다(규칙 이중화 0) · 개별 다운로드가 서버 헤더 이름 사용 ·
  버전 박스도 원본명 그대로 전달" 로 **재설계**해 그 결정이 되돌려지지 않는지를 잠근다.
  dead assertion 을 지우는 데 그치지 않고 결정 자체를 가드로 승격했다.
- 검증: `verify_attach_multi_upload.mjs` **28 PASS**(재설계 후) · `verify_attach_date_compact.mjs`
  18 PASS · `verify_attach_version_diff.mjs` 89 PASS · 전수 mjs **47 스위트** 통과.
- Files: `src/static/app/composer.js`, `tests/verify_attach_multi_upload.mjs`, `docs/MODIFY.md`.
- Timestamp: 2026-08-07T00:30:00+09:00
## CHG-20260807T004000-attach-chain-merge-doc — AC-AMU-5 supersede 기록 (doc-only)

- 형제 cycle `attach-suffix-toggle` 이 저장명 규칙을 서버 단일 권위로 옮긴 결정을 FUNCTION.md 에
  반영 — 선행 `AC-AMU-5`(프론트 버전 접미)는 그 범위에서 **superseded**. 실행 코드 변경 0줄.
- Files: `docs/FUNCTION.md`, `docs/MODIFY.md`, `docs/REVIEW.md`.
- Timestamp: 2026-08-07T00:40:00+09:00
## CHG-20260807T0640-ai-claude-attach-diff-syntax-css-fix — keyword 규칙 미적용 hotfix

- **프론트** `src/static/css/chat.css`: 고아 주석 블록 해소(여는 `/*` 없는 `**굵기는 … */` 가
  CSS 파서에게 셀렉터로 읽혀 다음 규칙 `.code-tok-keyword` 를 삼켰다). 문단을 원 주석 안으로 병합.
- **테스트** `tests/verify_attach_diff_syntax_highlight.mjs`: F2 섹션 신설 — F8(고아 `*/`)·
  F9(미닫힘 주석)·F10(주석 제거 후 셀렉터 위치 산문 누출) × chat.css·base.css → **113 PASS**.
  결함 재주입 시 F8·F10 2중 검출.
- 적발 = 배포본 `6cd4afd2` PB-0008 라이브 computed style 실측(keyword `rgb(38,37,30)`/400).
- 백엔드·API·RBAC·스키마·마이그레이션 **0**.
- Files: `src/static/css/chat.css`, `tests/verify_attach_diff_syntax_highlight.mjs`,
  `docs/{TASK,MODIFY,REVIEW,REPORT}.md`, `docs/test-runs.d/20260807T0640-attach-diff-syntax-css-fix.md`.
- Timestamp: 2026-08-07T06:40:00+09:00

## CHG-20260807T0700-ai-claude-attach-diff-syntax-postdeploy — POST-DEPLOY 실측 기록 (doc-only)

- `docs/test-runs.d/20260806T1853-attach-diff-syntax.md` · `…/20260807T0640-attach-diff-syntax-css-fix.md`:
  `verdict: PARTIAL → PASS` + PB-0008 실측 블록(computed style·토글 왕복·단일열 parity·2버전 체인) +
  미수행 축 3건 명시(기하 하네스 미실행 · 비교불가 유형 라이브 표본 0 · 6,000행 체감).
- `docs/TASK.md`: 두 cycle 의 배포·PB-0008 체크박스 마감. `docs/REPORT.md`: Summary 2건 갱신 +
  §8 원장 3건(선행 red `verify_attach_multi_upload.mjs` · CSS 정적검사 한계 · 라이브 표본 부재).
- 코드 변경 **0**(doc-only). Timestamp: 2026-08-07T07:00:00+09:00
## CHG-20260807T032000-attach-chain-live-dup — 라이브 병합 실행 + PG 미러 2단계 흡수 + live 중복 조건

- 선행 cycle 의 라이브 적용(155 row, 잔여 0)과 그 과정에서 드러난 결함 2건 수리.
- **`scripts/attach_chain_merge.py` `mirror()` 2단계화**: PG 에도 같은 `UNIQUE(root, version)` 이
  있어 단순 upsert 가 중간 상태에서 충돌한다(라이브 실측 `(699,4) already exists` → 29 row 가 옛
  상태로 잔존). 영향 **대화 전체**를 오프셋 선이동 후 재미러하도록 흡수(변경분만 밀면 그 자리를
  차지한 기존 행과 재충돌). 반환값에 스코프 row 수 표기.
- **판정 조건에 live>1 추가**: root·이름이 같아도 `SupersededAt IS NULL` 이 둘이면 목록에 두 줄로
  뜬다(업로드 supersede 누락이 남긴 선재 결함, 라이브 1건). 증상·해소 수단이 분열과 같아 같은
  판정에 넣었다.
- **테스트** `test_attach_chain_merge.py` **C10/C10b 신규** — live 중복이 수리되는지 + 그 조건이
  정합 체인을 건드리지 않는지(반대 방향).
- 라이브 결과: MySQL 활성 780 = PG 780 · **불일치 0** · **체인당 live>1 : 0**(양쪽).
  스냅샷·롤백 SQL 을 `artifacts/attach-chain-merge/` 로 회수.
- Files: `scripts/attach_chain_merge.py`, `tests/test_attach_chain_merge.py`, `docs/{TASK,MODIFY,REVIEW}.md`.
- Timestamp: 2026-08-07T03:20:00+09:00
## CHG-20260807T1500-gc-first-use-guide — 그룹 대화 기능 첫 사용 1회 가이드 툴팁

- 사용자 요청(2026-08-07, `/_template:entry`): 그룹대화 참여 기능을 **처음 쓸 때**(각 대화의 처음이
  아니라) 한 줄 30자 이하의 간단한 안내를 툴팁으로. 팝업은 화면을 가려 쓰지 않는다.
- `src/static/index.html`: 컴포저 바로 위에 `#groupGuideTip` 안내 말풍선 마크업 + 안내 5줄
  (일반 대화 · `@assistant` 요청 · 멤버 멘션 · 첨부 공유 · 안 읽음 배지). 최장 24자.
- `src/static/app/composer.js`: 계정(username) 단위 소진 로직 — `GC_GUIDE_LS_KEY`
  (`mad.gcFirstUseGuide.v1`, 소진한 username 배열 · 상한 50) + `_gcGuideSeenList` /
  `_gcGuideAccountKey` / `_gcGuideAlreadySeen` / `_gcGuideMarkSeen` / `hideGroupFirstUseGuide` /
  `_wireGroupFirstUseGuide` / `_maybeShowGroupFirstUseGuide`. 판정 호출은 `renderComposer` 말미 1회 —
  대화 전환·복원·폴링이 전부 지나는 choke-point 라 진입 경로별 누락이 생기지 않는다
  (`gc-unread-read-fix` 가 겪은 경로 누락 실패 모드의 반대 설계). 세션 하이드레이션 전(계정 미상)
  에는 노출을 **보류**해 익명 키로 소진되는 일을 막는다.
- `src/static/css/chat.css`: `.gc-guide-tip*` — 컴포저 위 caret 말풍선, `width:max-content`
  (각 안내가 한 줄로 떨어짐) + 좁은 뷰포트 줄바꿈 degrade, `prefers-reduced-motion` 등장효과 생략.
  **모달 백드롭·포커스 트랩 없음** — 대화 내용도 입력창 조작도 차단하지 않는다.
- **닫기와 소진 분리**(§18.8 ux 패널 BLOCKING #1): "다시 안 보기" 클릭만 영구 소진,
  입력 시작·Esc 는 `_gcGuideDismissedThisLoad` 로 이 로드에서만 숨김 → 다음 방문에 재노출.
  Esc 는 `_gcGuideOtherOverlayOpen()`(멘션 AC·액션/모델/추론/제품 드롭업 5종)이 열려 있으면
  양보한다(그 Esc 는 그쪽 몫). 재렌더가 리스너를 쌓지 않도록 `dataset.wired` 1회 배선.
- **발화 가능 게이트**(ux BLOCKING #2): `can("conversation.ask") && !conv.blocked` 가 아니면
  표시도 소진도 하지 않는다 — 거짓 안내로 유일한 1회 기회를 소비하지 않게.
- **a11y**: `aria-live="polite"`(표시 전환 통지) + 닫기 라벨을 `다시 안 보기` + `title` 로
  영구성 명시. 포커스 이동은 채택 안 함(팝업 금지 요구와 상충).
- **문구 F1 정합**(ux MAJOR #3): "첨부파일은 멤버 모두가 봅니다" → `첨부는 전원 공유, AI엔 내 것만`.
  LLM 주입은 발신자 본인 첨부 한정이라 전자는 오도다. `@이름` 줄도 `@이름 은 알림만, AI 미호출`
  로 바꿔 바로 윗줄(`@assistant` → AI 응답)과 대비시켰다.
- **스택·배치**(design BLOCKING/MAJOR): `z-index: 40`(`.mention-ac`·`.chat-drop-overlay` 의
  50 **아래**) + 앵커 `bottom: calc(100% + 6px)` 로 카드·caret 전체를 `.composer-wrap` 밖에
  세워 `#llmRestrictionBanner`/`#timeoutExtendBanner` 잠식을 제거. `max-width` 는 뷰포트가
  아니라 컨테이너 기준. 터치 타깃 확보(padding 8/10 + 음수 margin). 제목 13px.
- **다크 모드 — 지적을 실측으로 검증해 반대로 조치**: `css/base.css` 에 `prefers-color-scheme`
  블록이 **0개**(라이트 단일 테마, `--surface` 항상 `#ffffff`)라 다크 override 를 넣으면 OS 가
  다크일 때 흰 카드 위 연파랑(≈1.8:1)이 된다 → **넣지 않고** 그림자·hover 를 `--gc-guide-*`
  토큰으로 빼 다크 도입 지점만 남겼다. 대비는 계산해서 고쳤다 — `--text-muted`(#807d72)는
  흰 배경 **4.12:1** 로 12px 본문 AA 미달이라 전용 토큰 `#4a4841`(**9.15:1**)로 교체
  (제목 15.38 · 닫기 5.17).
- **모션**: 저장소 anim-pref 규약 이식 — `html:not([data-motion="on"])` + `html[data-motion="off"]`.
- 백엔드·스키마·RBAC·엔드포인트·권한 변경 **0**. 1:1 대화는 노출도 소진도 없음.
- 검증: `tests/verify_gc_first_use_guide.mjs` **61/61 PASS**(실 함수 본문 추출 + 가짜 DOM/localStorage —
  문자열 grep 아님) · **뮤테이션 역검증 5/5 KILLED**(입력-소진 복원 · 게이트 제거 · Esc 양보 제거 ·
  z-index 60 · caret wrap 잠식) · `node --check`(ESM) PASS · chat.css brace 624=624.
- §18.8 적대 패널 ux·design **양쪽 BLOCK** → 전건 disposition(REVIEW.md REV-20260807T153000 2건 +
  `docs/reviews/20260807T153000-{ux,design}.md`).
- 기능 정본 문서는 feature-0009-group-conversation (cross-reference).
- Files: `src/static/index.html`, `src/static/app/composer.js`, `src/static/css/chat.css`,
  `tests/verify_gc_first_use_guide.mjs`, `docs/{TASK,MODIFY,REVIEW,TEST,REPORT,FUNCTION}.md`,
  `docs/reviews/20260807T153000-{ux,design}.md`, `docs/test-runs.d/20260807T1500-gc-first-use-guide.md`.
- Timestamp: 2026-08-07T15:00:00+09:00

## CHG-20260807T1700-gc-guide-esc-capture — 안내 툴팁 Esc 양보가 라이브에서 무효였던 결함

- **적발**: 선행 cycle 배포본 `f81c5bcb` 의 PB-0008 라이브 실측 #8. 멘션 자동완성이 열린 채
  Esc → 안내까지 함께 닫힘.
- **근본 원인**: 로직이 아니라 **핸들러 실행 순서**. 우리 Esc 핸들러가 버블 단계라, 먼저
  등록된 멘션 AC 핸들러가 AC 를 닫은 뒤에 돌아 `_gcGuideOtherOverlayOpen()` 이 "열려 있지
  않다" 로 오판.
- `src/static/app/composer.js`: Esc 핸들러를 **capture 단계**로 등록(`…, true`). 같은 파일의
  `_attachShareRangeEsc` 가 동일한 이유로 이미 capture 를 쓴다(저장소 선례).
- `tests/verify_gc_first_use_guide.mjs`: 가짜 document 를 **capture → bubble 2단계 디스패치**로
  전환 + `installCompetingOverlayEsc()` 주입. 선행 하네스 61 PASS 는 경쟁 핸들러가 없어
  **vacuous pass** 였다 — 단언이 형식적이어서가 아니라 **합성을 재현하지 않아서**다.
  경쟁 핸들러 없음/있음 **양쪽**을 검사하고, 과잉 양보(오버레이 없는데 안 닫힘)도 반대
  방향으로 단정한다. **68/68 PASS**, capture→버블 되돌림 뮤테이션 **6 red**.
- 피해 범위(정직): 이 결함으로도 **영구 소진은 없었다**(라이브 `localStorage=null` 확인) —
  앞선 ux BLOCKING #1 수정이 그 경로를 이미 끊어 뒀다. 잔여 영향은 "그 로드에서 함께 사라짐".
- 백엔드·스키마·RBAC·엔드포인트 변경 0.
- Files: `src/static/app/composer.js`, `tests/verify_gc_first_use_guide.mjs`,
  `docs/{TASK,MODIFY,REVIEW,TEST,REPORT,FUNCTION}.md`,
  `docs/test-runs.d/20260807T1500-gc-first-use-guide.md`(PB-0008 Run append).
- Timestamp: 2026-08-07T17:00:00+09:00

## CHG-20260807T1830-gc-guide-postverify — 안내 툴팁 PB-0008 재실측 기록 (doc-only)

- `docs/test-runs.d/20260807T1500-gc-first-use-guide.md`: 배포본 `f60d67c5` 재실측 Run append
  (**8/8 PASS**) + frontmatter verdict 를 `PASS (Windows-browser)` 로 갱신.
- `docs/TASK.md`: 선행 2 cycle 의 PB-0008 체크박스 마감. `docs/REPORT.md`: Summary 2건에
  배포·검증 종결 표기.
- 코드 변경 **0**(doc-only). Timestamp: 2026-08-07T18:30:00+09:00
## CHG-20260807T1300-ai-claude-attach-diff-identical-source — 내용 동일 시 문서 원문 출력

- **서버** `src/routers/_conv_store.py` `_build_version_diff_view`: `identical` 판정을 2차 패스보다
  앞에서 확정하고, 축약 분기를 `context_lines is None or identical` 로 넓혔다. 맥락 축약은 변경
  주변만 남기는 연산이라 변경 0개면 **파일 전체가 gap 한 줄**로 접혔다 — 프론트에 줄 근거가 없었다.
  행 상한·`truncated.rows` 계약은 불변.
- **프론트** `src/static/app/attach-diff.js`: `_renderSource` 신설(줄번호+본문 2열, `is-source`) ·
  `_appendColgroup` 에 `source` kind · `_renderBody` identical 분기가 배너 + 원문 표를 렌더(빈 문서는
  안내만) · `syncDiffOnlyControls` 신설(identical 이면 2열/단일열·맥락 토글 숨김) · `syncHlToggle`
  노출 조건에서 `identical` 제외 제거(원문도 칠할 본문이다) · 요약 배지 `차이 없음 — 원문 표시`.
- **CSS** `src/static/css/chat.css`: `.attach-diff-table.is-source` + **`[hidden]` override 3종**.
  후자는 부수 적발 — author `display:inline-flex` 가 UA `[hidden]{display:none}` 를 이겨 선행 cycle 의
  토글 숨김(AC-AVD-23)이 화면에서 작동하지 않았다(같은 기전을 쓰는 이번 변경과 함께 봉인).
- **테스트** `tests/verify_attach_diff_identical_source.mjs` 신설 39건(A 원문 무손실 · B 본문 분기 ·
  C 하이라이트 parity · D 거짓 어포던스+CSS 실효 · E 서버 계약) ·
  `tests/test_attachment_version_diff.py` B7/B7b/B7c/E15 신규 ·
  `tests/verify_attach_diff_syntax_highlight.mjs` E8 `_paintCell` 개수 계약 4→5(렌더러 3종).
- 신규 권한·스키마·마이그레이션·엔드포인트 shape 변경 **0**. 본문 노출 경계 불변(`context=full` 로
  이미 조회 가능하던 범위 · D21 pending 403 그대로).
- Files: `src/routers/_conv_store.py`, `src/static/app/attach-diff.js`, `src/static/css/chat.css`,
  `tests/verify_attach_diff_identical_source.mjs`, `tests/test_attachment_version_diff.py`,
  `tests/verify_attach_diff_syntax_highlight.mjs`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`,
  `docs/test-runs.d/20260807T1300-attach-diff-identical-source.md`.
- Timestamp: 2026-08-07T13:00:00+09:00

## CHG-20260807T1345-ai-claude-attach-diff-identical-source-panel — §18.8 적대 리뷰 반영

`REV-20260807T133000`(ux) · `REV-20260807T133001`(design) 의 CONCERN 대응. 초판 대비 변경:

- **`_identicalFlags(data)` 신설**(`attach-diff.js`): `clipped`(행 상한 또는 원본 cap 절단) ·
  `shaDiff`(줄 비교는 같은데 sha256 상이) 두 플래그를 **한 곳**에서 판정하고 안내 배너·요약 배지가
  같이 쓴다. 초판은 세 요약이 각자 다른 근거로 만들어져 한 화면에서 서로를 반박했다
  ("차이가 많아 앞쪽 6000행" + "문서 원문(20000줄)" + "차이 없음").
- **절단 배너 문구 분기**: identical 이면 "차이가 많아" 대신 "문서가 길어". 안내 배너는 절단 시
  "원문" 단정을 버리고 "비교한 범위에서 … 문서 앞부분 N줄" 로 약화(등급도 is-warn).
- **sha256 불일치 표면화**: `splitlines()` 비교가 CRLF↔LF·마지막 줄 개행을 흡수하므로 "완전히
  동일" 이라 단정하지 않는다. 판별 근거는 이미 응답에 있던 필드(신규 API 0).
- **컨트롤 = 숨김 → 비활성**: 판정면을 `syncHlToggle` 과 동일화(`comparable !== false` ·
  `!identical` · `rows.length > 0`)해 비교 불가·같은 버전·조회 실패 화면에도 적용하고, 숨기는 대신
  비활성 + `title` 사유. 숨기면 `.attach-diff-stats{margin-left:auto}` 때문에 컨트롤 바가 흔들린다.
  초기 호출 추가로 응답 전 깜빡임 제거.
- **dead 자산 정리**: `.attach-diff-table.is-source .attach-diff-code{border-right:none}` 는
  끌 대상이 없는 **no-op** 이라 삭제(`border-right` 를 주는 규칙은 `is-split .side-left` 하나뿐).
  행 클래스 `is-source` → `is-plain`(표 계층 modifier 와 계층 충돌 + dead class).
- **접근성**: 원문 표 `aria-label` + 줄번호 셀 `aria-hidden`(원문 뷰는 문서라 매 줄 낭독이 방해).
- **테스트**: 하네스 39 → **61건**. D 섹션을 정적 정규식에서 **모달 실구동 4상태 실측**으로 재작성,
  B8b~B8f(절단 문구) · B9~B9c(sha 불일치) · D9/D9b(구조 단언 — 초판 D8 은 CSS 문자열 존재만 보는
  "항상 통과하는 검사") 추가. 뮤테이션 3/3 red 확인.
- Files: `src/static/app/attach-diff.js`, `src/static/css/chat.css`,
  `tests/verify_attach_diff_identical_source.mjs`, `docs/{FUNCTION,REVIEW,REPORT,TASK,MODIFY}.md`,
  `docs/reviews/20260807T1330Z-{ux,design}.md`.
- Timestamp: 2026-08-07T13:45:00+09:00

## CHG-20260807T1420-ai-claude-attach-diff-identical-source-a5 — 선행 하네스 A5 계약 개정

- `tests/verify_attach_version_diff.mjs` A5: 초판 계약("identical 이면 표 대신 안내만")이 이번
  cycle 로 바뀌어 red 가 됐다. 픽스처가 **서로 다른 sha256**(`aaaa`/`bbbb`)을 쓰고 있었는데 그
  조합이 이제 의미를 갖기 때문(줄 종단자 차이 → 단정 약화 is-warn).
- 해소: 기본 경로는 해시 동일 픽스처로 고정(is-same) + **A5b**(빈 문서면 원문 표도 없음) ·
  **A5c**(sha 불일치는 is-warn) 신설. 갈래별 문구는 전용 하네스가 담당한다는 경계를 주석에 명시.
- 89 → **91 PASS**. 코드 변경 0(테스트 계약만).
- Files: `tests/verify_attach_version_diff.mjs`, `docs/{MODIFY,REPORT}.md`.
- Timestamp: 2026-08-07T14:20:00+09:00
## CHG-20260807T1400-ai-claude-attach-diff-intraline — 첨부 버전 diff 에 **줄 안(글자 단위) 변경 구간** 표시

- 사용자 지적(2026-08-07): "여전히 line 단위 차이만 나타나고 있는 상태이며 **각 글자 단위의
  차이점은 출력되지 않는** 형태라 작업 완수가 필요합니다." — `(attach-version-diff, 2026-08-06)`
  가 §범위 밖으로 미뤄 둔 "단어 단위 intra-line 하이라이트" 를 완수한다.
- **서버가 구간을 단독 산출** (`_conv_store.py`): `_intraline_tokens`(문자 계열별 단위 — ASCII 단어
  런 / **CJK 한 글자** / 공백 런 / 그 외 한 글자, 자소 묶음은 결합문자·VS·ZWJ·피부톤까지 흡수) +
  `_intraline_segments`(토큰 `SequenceMatcher` → `[{t:"eq"|"ch", v:"…"}]`). 좌우가 모두 있는
  `replace` 행에만 `left_segs`/`right_segs` 를 붙인다. 계산은 **행 상한·맥락 축약 이후**(표시
  확정 행에만) 수행.
- **2단 정밀화**: 토큰이 **정렬 앵커**를 잡고, 바뀐 조각 안에서 다시 **자소 단위**로 좁힌다
  (`_intraline_refine`). 토큰 단위만 쓰면 `m.last_login_at`→`m.last_logout_at` 이 식별자 전체를
  칠하고(=줄 단위 불만이 한 단계 아래에서 반복), 문자 단위만 쓰면 `SELECT`↔`INSERT` 가 색종이가
  된다. 정밀화 안에서도 변경이 40% 를 넘으면 좁히지 않는다(실측으로 0.7/0.5/0.4 비교).
- **비용 상한 3겹** — 초판의 "토큰쌍 예산" 은 **비용의 대리값이 못 됐다**(§18.8 backend 패널
  실측: 같은 명목 예산에서 실제 시간 **83배** 차 · 예산을 한 푼도 안 쓰고 1,039ms 소모 · 정밀화
  비용이 게이트 뒤에 더해져 1.33배 초과). 통화를 바꿨다 —
  ① 행별 **문자쌍 컷**(`_INTRALINE_PAIR_CAP` 250k, **토큰화 이전** O(1) 판정)
  ② 패스 **경과시간**(`_INTRALINE_TIME_BUDGET_S` 0.5s — 대리값 대신 지키려는 값을 직접 측정)
  ③ **응답 바이트**(`_INTRALINE_PAYLOAD_CAP_BYTES` 512KB — 행 상한은 바이트를 막지 않는다).
  패널이 든 최악 입력 재측정: **2997→5.3ms · 2367→4.1ms · 1079→2.7ms · 1039→2.1ms**,
  정밀화 게이트 탈출 사례 266→0.00ms. 현실 CSV 6,000행은 510ms/1,204행 마크(배너 표시).
- 비용 가드로 생략된 줄이 있으면 `truncated.intraline` 로 **표면화**하되, **비율 컷은 세지
  않는다** — 좌우가 전혀 다른 줄은 화면이 이미 그렇게 읽히고, 그것까지 세면 재작성이 많은
  diff 마다 배너가 상시가 된다.
- **프론트는 덧그리기** (`attach-diff.js` `_markSegments`): 구문 하이라이트가 이미 만든 텍스트
  노드를 **문자 오프셋으로 쪼개** `<span class="attach-diff-chunk">` 로 감싼다. 텍스트를 다시
  만들지 않으므로 구문 색과 변경 마크가 독립 레이어로 공존한다. 세그먼트 총 길이 ≠ 셀 텍스트
  길이면 **아무것도 그리지 않는다**(어긋난 위치의 마크는 없느니만 못하다). 2열·단일열이 같은
  구간을 쓴다(단일열 replace 는 삭제 줄=좌측·추가 줄=우측).
- **마크는 배경이 아니라 `inset box-shadow` 밑줄** (`chat.css`): 배경 칠은 이 표에서 접근성
  회귀다 — 구문 토큰 9색은 세 실배경에서 AA 4.5:1 로 잠겨 있는데(하네스 G2), 같은 색조를 얹으면
  알파 0.20 에서도 `number` 가 삭제 행에서 **3.40** 으로 떨어진다(계산 실측).
  초판은 `text-decoration` 밑줄이었으나 §18.8 ux 패널이 **탭 위에 0px 도포**를 실측했다(마크
  구간이 `\t\t` 일 때 span 박스 78×17 에 칠해진 픽셀 0 — 들여쓰기 변경이 이 기능의 주 대상인데
  화면에 아무것도 안 나왔다). `inset box-shadow` + `box-decoration-break: clone` 으로 교체해
  같은 입력에서 156px 도포·줄바꿈 조각 복제를 실측했고, `background-color` 는 여전히
  `transparent` 라 위 대비 논거가 유지된다.
- **마크 색은 이색형에서 명도로 갈린다** (`base.css` `--diff-mark-*`): 이색형(deuteranopia)은
  색상 차가 사라지고 명도만 남는데 `--tag-danger-fg`/`--tag-ok-fg` 는 그때 명도가 가까워
  좌/우 구분이 약했다(패널 지적). 삭제쪽을 `#7f1d1d` 로 한 단계 어둡게 잡아 **명도 자체를 쪽
  구분 채널로** 쓴다(비-텍스트 대비 삭제 8.32/deut 7.17 · 추가 4.39/deut 4.12).
- **렌더-측 마크 예산**(`MARK_RENDER_BUDGET` 12,000 span): 서버 상한은 **계산**만 막고 렌더된
  span 수는 막지 않는다 — 패널 실측으로 6,000행 CSV 에서 chunk span 60,000개·노드 222,007개가
  나왔고 표는 상호작용마다 통째로 다시 그려진다. 예산 초과분은 줄 단위 강조 그대로 두고 고지한다.
- **정밀도 고지는 내용 절단과 다른 톤**(`is-note`): amber `is-warn` 3장이 쌓이면 "diff 가
  불완전하다" 와 같은 강도로 읽힌다(패널 P2). 사유도 "길어서" 로 말하지 않는다 — 같은 길이의
  윗줄은 마크되는데 아랫줄만 안 되는 경우가 있어 화면과 어긋난 설명이 된다.
- **선행 파손 수리**: `tests/headless/verify_attach_diff_geometry.py` 가 구문 하이라이트 cycle 이후
  `detectCodeLanguage is not defined` 로 **전 케이스 미실행**이었다(main 에서도 동일 재현). 정본
  `code-highlight.js` 를 같은 페이지에 인라인해 부활 — 이 하네스가 본 변경의 픽셀 게이트다.
- **§18.8 적대 패널 3도메인(ux+design / frontend+security / backend+qa) 전건 흡수** — P1 4건
  (탭 위 0px 도포 · 정밀화 부재로 sha256 류가 마크도 배너도 없음 · 정밀화가 자소 클러스터를
  가름 · 브랜치 자체 테스트 red) · P2 5건(비용 대리값 실패 3종 · 렌더 노드 폭증 · 배너 톤) ·
  P3 다수(과장 마킹 · 악센트 라틴 · 무음 실패 · 재적용 중첩 · 기본 마크색 부재 · 두 렌더러 분기
  불일치 · 국기/tag sequence). 패널이 **확인해 준 것**: XSS 무첨가(모든 신규 경로 textContent
  전용, `</span><img onerror>` 주입 실측 0 요소) · UTF-16↔코드포인트 오프셋 드리프트 없음
  (양쪽 다 JS 에서 재측정) · 토큰 왕복 무손실(32만 표본 0 위반) · 세그먼트 이어붙이기 계약
  무위반(5.6만 표본) · 2열/단일열 마크 문자집합 동일 · 엔드포인트 계약 가산만.
- **테스트**: pytest `test_attachment_version_diff.py` **B20~B36 신규 17건**(왕복 동치·CJK 글자 단위·
  정렬 앵커≠마크 단위·무관 쌍 폴백·insert/delete 무세그먼트·길이 컷·행 상한 이후 계산·자소 묶음·
  비용 가드 표면화·늑대소년 방지·자소 단위 정밀화·과장 0·악센트 라틴·**토큰화 전 컷**·
  정밀화 클러스터 보존·국기/tag sequence) + E1 절단 4종 전열거. jsdom `verify_attach_version_diff.mjs` **D1~D8 신규**
  (2열·단일열 마크·구문 공존·토큰 내부 부분 구간·세그먼트 없음 무영향·계약 위반 거부·스타일 계약·
  서버 단독 산출·절단 배너). 실브라우저 `verify_attach_diff_geometry.py` **M1~M5 신규**(밑줄 렌더·
  쪽별 색·배경 미칠 실측·행 높이 불변·단일열 parity).
- 신규 권한·스키마·마이그레이션 **0**. 응답은 `truncated.intraline` 1키 + `replace` 행 2키 추가(가산).
- Files: `src/routers/_conv_store.py`, `src/routers/attachments.py`, `src/static/app/attach-diff.js`,
  `src/static/css/chat.css`, `tests/test_attachment_version_diff.py`,
  `tests/verify_attach_version_diff.mjs`, `tests/headless/verify_attach_diff_geometry.py`,
  `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md`.
- Timestamp: 2026-08-07T14:00:00+09:00
## CHG-20260811T1130-ai-claude-attach-diff-intraline-postdeploy — POST-DEPLOY PB-0008 실측 기록 (doc-only)

- 배포본 `9f1622f9` 라이브 실측. **완료 판정은 파이프 exit 이 아니라 서비스별 커밋**으로 했다 —
  `repo-web-a-1`·`repo-web-b-1`·`repo-ask-worker-1`·`repo-insight-worker-1` 전부 `GIT_COMMIT=9f1622f9`.
- `docs/test-runs.d/20260807T1400-attach-diff-intraline.md`: `verdict: PARTIAL → PASS` +
  PB-0008 실측 블록(마크 렌더 13개·쪽별 색 `rgb(127,29,29)`/`rgb(21,128,61)`·배경 `rgba(0,0,0,0)`·
  구문 토큰 147개 공존·하이라이트 OFF→ON 왕복 텍스트 불변·2열↔단일열 parity·한글/부분 마크) +
  **관측된 한계 2건**(마크 span 수 ≠ 변경 구간 수 · 무관한 줄 짝짓기에서 마크가 노이즈) +
  **라이브 표본에서 확인 못한 축 3건**(탭 들여쓰기·`is-note` 배너·6,000행 체감 — 헤드리스가 잠금).
- `docs/TASK.md`: 배포·PB-0008 체크박스 마감 + Next Action 해제.
- 코드 변경 **0**(doc-only). Timestamp: 2026-08-11T11:30:00+09:00
## CHG-20260807T1900-ai-claude-attach-source-view — 첨부 행 클릭 = 문서 원문 보기

- **서버** `src/routers/_conv_store.py` `_build_source_view` 신설 — 단일 버전 본문을 줄번호 행으로
  펼친다. 행 shape 을 diff `rows` 와 **호환**(우측 키만)으로 내 프론트 렌더러 분기를 0 으로 둔다.
  `src/app.py` re-export 1행.
- **서버** `src/routers/attachments.py` `get_attachment_source` 신설
  (`GET /api/attachments/{id}/source`). 권한·게이트를 `/diff` 와 **동형**으로 배치 —
  `read.{own,any}` 재사용(신규 권한 코드 0) + **D21 pending 403**(본문 bytes 노출이므로 metadata
  조회가 아니라 다운로드와 같은 등급). 바이너리는 `viewable=false` + 메타 강등, read 실패는 503,
  절단 2종(`truncated.source`/`rows`)을 각각 표면화.
- **프론트** `src/static/app/attach-diff.js` `openAttachmentSourceModal` 신설. **같은 모듈**에 둔
  이유는 렌더 primitive(`_renderSource`·`_appendColgroup`·`_paintCell`·스크롤 앵커) 공유 —
  별 모듈로 나누면 복제하거나 순환 import 를 만들게 된다(이 저장소는 "복제가 곧 결함 기전" 을
  modal-dismiss.js 에서 이미 치렀다). 구문 색 토글은 비교 모달과 **같은 저장 키**.
- **프론트** `src/static/app/composer.js` 첨부 목록 행 배선 — `is-openable` + `role="button"` +
  `tabIndex` + Enter/Space. 행 안의 ⬇·🗑·버전 토글은 `closest("button")` 으로 걸러낸다
  (삭제하려다 원문이 함께 열리지 않게). 휴지통 목록은 대상 아님.
- **CSS** `src/static/css/chat.css` `.attach-list-item.is-openable` hover/focus-visible/cursor.
- **설계 결정 — 버전 파라미터 없음**: 초안에는 `?version=` 쿼리와 모달 버전 선택기가 있었으나,
  체인의 각 버전이 **자기 id** 를 가지므로 경로 id 하나로 대상이 특정된다. 식별 경로가 둘이 되면
  그 중 하나만 스코프 검사를 통과하는 비대칭이 생길 수 있고, 어느 호출부도 채우지 않는 select 는
  죽은 컨트롤이다. 구현 중 둘 다 제거.
- **테스트** `tests/test_attachment_source_view.py`(S1~S4 빌더 · E1~E8 엔드포인트, diff 테스트의
  fake 재사용 — 중복 정의 금지) · `tests/verify_attach_source_view.mjs` 59건 ·
  `tests/verify_attach_version_diff.mjs` B1 계약 개정(import 목록 확장 수용).
- `docs/ROUTEMAP.md` 재생성(신규 route 1). 스키마·마이그레이션·기존 응답 shape 변경 **0**.
- Files: `src/app.py`, `src/routers/{_conv_store,attachments}.py`,
  `src/static/app/{attach-diff,composer}.js`, `src/static/css/chat.css`,
  `tests/{test_attachment_source_view.py,verify_attach_source_view.mjs,verify_attach_version_diff.mjs}`,
  `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`, `docs/ROUTEMAP.md`(repo).
- Timestamp: 2026-08-07T19:00:00+09:00

## CHG-20260807T1945-ai-claude-attach-source-view-panel — §18.8 적대 리뷰 2건 반영

`REV-20260807T193000`(security) · `REV-20260807T193001`(ux+design) 의 CONCERN 대응.

**서버**
- `modules/storage_minio.py` **`get_object_head_bytes` 신설**(ranged GET) — `get_object_bytes` 는
  객체 전체를 메모리로 올린다. per-file cap 25MB ÷ 뷰 cap 1MB = **최대 25× 증폭**이고, 트리거가
  원클릭이라 나가는 바이트의 자연 제동이 없다.
- `routers/attachments.py`: `_BODY_VIEW_HEADERS`(`private, no-store` + `nosniff`) 신설·3 반환 적용 ·
  `RATE_SCOPE_ATTACHMENT_SOURCE` 30/분 · 빈 `ObjectKey` 404 가드 · `except` 를 storage 예외로 축소 ·
  503 payload 에 `error` 문구 동봉(`apiFetch` 가 non-2xx 를 throw 하므로 이 키가 없으면 사용자가
  영문 `Service Unavailable` 을 본다 — `/diff` 의 같은 선행 결함도 함께 정정).
- **절단 판정을 DB `SizeBytes` 로 전환**: ranged read 는 항상 cap 만큼 오므로 `len(raw) > cap` 이
  영원히 거짓 — 증폭을 고치다 **무음 절단**을 만들 뻔한 자리.
- `routers/_conv_store.py` `_build_source_view(source_truncated=)` → `stats.lines_partial`.
  절단된 앞부분에서 센 줄 수를 전체처럼 말하지 않기 위한 플래그(실측: 200,000줄 파일 → "95,326줄").

**프론트**
- `attach-diff.js`: `render({keepScroll})` + 스크롤 앵커(비교 모달 AC-AVD-15 와 같은 계약 — 원문 뷰는
  축약이 없어 잃는 거리가 더 크다) · `isClipped` 로 제목("문서 앞부분")·통계("앞 N행 표시")·배너가
  **같은 판정**을 쓰게 · 제목에 버전 태그 · `aria-labelledby` + 열기 시 닫기 버튼 포커스 + 닫을 때
  opener 복귀 · 빈 컨트롤 바 숨김 · 도달 불가 503 분기 제거.
- `composer.js`: 행에서 `role`/`tabIndex` 제거하고 **파일명만** 버튼으로 승격(+`aria-label`) —
  행에 role=button 을 주면 안의 ⬇·🗑·버전 토글이 버튼 안의 버튼이 되어 보조기술이 행 전체 텍스트를
  이름으로 읽는다 · 행 클릭에 **press-pair(5px) + selection 가드**(드래그 선택이 클릭으로 오인되는
  기전은 `modal-dismiss.js` 가 배경 dismiss 에서 이미 봉인한 것) · kind 별 title 분기 +
  `ATTACH_SOURCE_VIEWABLE_KINDS` 사본(하네스가 서버 정본과 대조해 잠금) · **버전 이력 각 행에 👁**
  (구버전 원문 진입점 — docstring 이 주장하던 경로가 UI 에 없었다).
- `chat.css`: 파일명 버튼 hover/focus 링 · `:has()` 로 액션 버튼 hover 시 행 하이라이트 억제
  (삭제와 열기가 같은 신호를 갖지 않게) · `.attach-list-version-src` · `prefers-reduced-motion` 가드.

**테스트**
- `verify_attach_source_view.mjs` 59 → **77건**. `apiFetch` stub 을 **실 계약(non-2xx throw)** 으로
  교체 — 항상 resolve 하는 stub 이 503 분기를 vacuous pass 시키고 있었다.
- `test_attachment_source_view.py` S5(splitlines 정규화 고정) · S6 · E9(실물 게이트로 soft-delete
  404) · E10(ranged read + 정본 크기 절단) · E11(429) · E12(헤더) · E13(빈 ObjectKey 404) 신규.
  `_Storage` fake 에 `get_object_head_bytes`/`head_reads` 추가(전체 적재 여부를 구분해 센다).
- `route_snapshot_p5b.json` 골든 갱신(신규 route 1 — 227→228).

**문서**
- `docs/SECURITY.md §21.5` 6번 신설 — **§21 window clip 이 첨부 read 4경로(목록·다운로드·비교·원문)에
  미적용**임을 수용 근거·봉인 조건·영향 범위와 함께 등재. 한 경로만 봉인하면 같은 행의 ⬇ 는 열린 채
  보호가 착시가 되므로 4경로 동시 봉인을 별 cycle 로 분리.
- `FUNCTION.md` AC-ASV-2 범위 명시(LF 한정) + AC-ASV-10~18 신설 + 범위 밖 명시.
- Files: `src/modules/storage_minio.py`, `src/app.py`, `src/routers/{attachments,_conv_store}.py`,
  `src/static/app/{attach-diff,composer}.js`, `src/static/css/chat.css`,
  `tests/{test_attachment_source_view.py,test_attachment_version_diff.py,verify_attach_source_view.mjs,route_snapshot_p5b.json}`,
  `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`, `docs/reviews/20260807T1930Z-{security,ux-design}.md`,
  `docs/SECURITY.md`(repo).
- Timestamp: 2026-08-07T19:45:00+09:00
## CHG-20260811T1500-ai-claude-attach-diff-mark-underscore — 줄 안 마크가 `_` 를 가리는 문제 수정

- 사용자 지적(2026-08-11): "변경을 강조하는 하이라이트 밑줄이 특정 문자의 가독성을 떨어뜨린다
  (`_` 문자 등)." 실측 캡처로 재현 — `legacy_gy_pay` 가 **`legacygypay` + 밑줄 하나**로,
  `__init__` 은 `init` 으로 읽혔다.
- **원인**: 마크를 `box-shadow: inset 0 -2px` 로 그렸다. `inset` 은 바를 **content box 안쪽 맨
  아래**에 놓는데 그 자리가 곧 `_` 글자가 놓이는 자리다. 두 가로 획이 붙어 하나로 보였다.
- **수정**: 바깥 그림자 `box-shadow: 0 2px` 로 교체. 같은 두께를 **content box 바로 아래**에 그려
  글자와 바 사이에 간격이 생긴다. 실측: 잉크 최하단 ↔ 바 최상단 사이 **빈 픽셀 행 1행** 확보.
- **대비 논거가 유지되는 이유**: 바깥 그림자는 CSS 규정상 **border box 안쪽으로는 그려지지
  않는다**. 글자 영역의 마크색 픽셀을 세어 **0** 임을 실측했으므로, "마크는 배경을 칠하지 않는다
  = 구문 토큰 AA 4.5:1 이 3면 그대로" 라는 기존 근거가 그대로 성립한다.
- **후보 비교(실측)**: `padding-bottom+inset` · 바깥 그림자 · 배경색 간격 · 윗줄(overline) 4종을
  실 chromium 에서 같은 표 맥락으로 렌더해 비교했다. 윗줄은 `_` 문제는 없지만 바가 **위쪽 줄에
  붙어 보여** 어느 줄의 표시인지 흐려졌고, 배경색 간격은 행 배경색(추가/삭제로 다름)을
  하드코딩해야 해서 탈락. `padding-bottom` 은 같은 그림을 주지만 인라인 박스 기하를 바꾸므로,
  기하를 건드리지 않는 바깥 그림자를 골랐다.
- **무회귀 확인(실측)**: 탭 문자 위 도포 **192px 유지**(밑줄 방식이 0px 였던 원 결함) · 행 높이
  19px 불변 · `box-decoration-break: clone` 줄바꿈 조각 복제 유지 · 쪽별 색 유지.
- **회귀 잠금 신설**: 기하 하네스 **M6** — 마크 구간에 `_` 를 넣고 캡처해 **글자 잉크 최하단과
  바 최상단 사이에 빈 픽셀 행이 있는지**를 직접 센다. computed style 로는 잡히지 않고 렌더된
  픽셀로만 드러나는 축이다(§16.6). mjs **D6a2** 가 `inset` 재도입을 소스에서 막는다.
  기하 **M3b** 의 클립 영역도 보정했다 — 바가 박스 바깥으로 나가면서 박스 안쪽만 캡처하던
  기존 클립이 마크를 0px 로 세어 **거짓 FAIL** 을 냈다(하네스 아티팩트).
- Files: `src/static/css/chat.css`, `tests/headless/verify_attach_diff_geometry.py`,
  `tests/verify_attach_version_diff.mjs`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`,
  `docs/test-runs.d/20260811T1500-attach-diff-mark-underscore.md`.
- 백엔드·API·RBAC·스키마·마이그레이션 **0**. Timestamp: 2026-08-11T15:00:00+09:00


## CHG-20260811T1600-ai-claude-attach-diff-underscore-postdeploy — POST-DEPLOY PB-0008 실측 기록 (doc-only)

- 배포본 `97e9c718` 라이브 실측. 판정은 서비스별 `GIT_COMMIT`(web-a/web-b/ask-worker/
  insight-worker 4종 일치) + **서빙 `chat.css` 의 `inset` 잔존 0건**으로 했다.
- `docs/test-runs.d/20260811T1500-attach-diff-mark-underscore.md`: `verdict: PARTIAL → PASS` +
  PB-0008 블록(`_` 3건 판독 · 마크 `0px 2px` non-inset · 배경 `rgba(0,0,0,0)` · 쪽별 색 ·
  단일열 parity · 구문 색 왕복 텍스트 불변) + 라이브 미확인 축 2건.
- `docs/TASK.md`: 배포·PB-0008 체크박스 마감. 코드 변경 **0**.
- Timestamp: 2026-08-11T16:00:00+09:00
## CHG-20260811T1200-ai-claude-attach-version-action-align — 버전 이력 행 액션 열 정렬

- **프론트** `src/static/app/composer.js`: 빈 슬롯 primitive `_attachActionSlot()`
  (`span.attach-list-action-slot`, `aria-hidden="true"`, 포커스 불가)을 **모듈 레벨 단일 정의**로
  두고 목록 **3종이 공유**한다(복제가 곧 결함 기전 — `modal-dismiss.js` 의 교훈).
  - 버전 이력: `⇄`(최신 행 없음) · `🗑`(행별 술어) — `canCompare`/`anyManage` 로 예약
  - 활성 첨부 목록: `🗑` — `anyItemManage` 로 예약
  - 휴지통: `⇤`(전체 버전 복구, 체인 머리만) — `anyChainHead` 로 예약
  사용자가 본 것은 버전 이력이지만 셋 다 같은 오른쪽 정렬 flex + 조건부 버튼이라 **같은 결함
  클래스**다. 한쪽만 고치면 같은 증상이 다른 화면에 남는다.
- **CSS** `src/static/css/chat.css`: `.attach-list-version-actions > *` · `.attach-list-item-actions > *`
  에 `flex: 0 0 auto; min-width: 22px; text-align: center` — 슬롯 폭을 글리프가 아니라 규칙으로
  고정(👁·⇄·⬇·🗑·↩·⇤ 의 advance 폭이 제각각이라 폰트·플랫폼이 바뀌면 같은 열도 폭이 달라진다).
  `.attach-list-action-slot`.
- 버튼을 없애지 않는다는 선행 계약(최신 행 `⇄` 미배치 — 자기 자신과의 비교는 무의미)은 유지.
- **테스트** `tests/verify_attach_version_action_align.mjs` 신설 **28건**(A~E) — `_renderAttachmentVersionsBox`
  를 중괄호 밸런스로 떼어 **실제 실행**하고 행별 슬롯 배열을 대조한다(정적 문자열 검사로는 행마다
  슬롯이 몇 개 붙는지 알 수 없다). 뮤테이션 3/3 red.
- 서버·권한·스키마 변경 **0**.
- Files: `src/static/app/composer.js`, `src/static/css/chat.css`,
  `tests/verify_attach_version_action_align.mjs`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`.
- Timestamp: 2026-08-11T12:00:00+09:00

## CHG-20260811T1300-ai-claude-attach-version-action-align-panel — §18.8 적대 리뷰 반영

`REV-20260811T130000`(ux+design) 의 CONCERN 대응.

- **폭을 바닥이 아니라 못으로**: `flex: 0 0 auto; min-width: 22px` → **`flex: 0 0 22px;
  min-width: 0`**. `min-width` 는 `max(값, 내용폭)` 이라 글리프가 넘으면 그 버튼만 넓어져 열이 다시
  갈린다 — 이 규칙이 겨냥한 상황에서 정확히 실패한다. `min-width: 0` 은 flex 자동 최소 크기
  (min-content)가 `flex-basis` 를 되밀지 못하게 하는 **필수** 항이다.
  **A/B 실증**(PB-0008): 글꼴 16px 확대 시 `min-width` 방식은 버튼 22→24px, 그 행 `👁` 1135→**1133**
  (열 깨짐). `flex-basis` 방식은 22px 유지·좌표 불변.
- **형제 목록 픽셀 근거 확보**: 활성 첨부 목록에서 DOM-level control 로 한 행의 `🗑` 를 제거 →
  `⬇` 1180→**1204**(24px 드리프트), 예약 슬롯 삽입 → 1180 복귀. 결함 존재와 해소를 모두 실측.
- **휴지통을 실행 테스트로 승격**: `_renderTrashAttachmentList` 를 `extractFn` + `new Function` 으로
  실제 실행해 슬롯 배열을 대조(E2~E7). 초판의 소스 정규식은 슬롯을 엉뚱한 컨테이너에 붙이거나
  `↩` 앞에 넣어 열 순서를 깨도 통과했다 — 이 파일 헤더가 스스로 금지한 방식이었다.
  활성 목록은 async + `apiFetch` 라 실행 불가 → **defer 를 파일에 명시**하고 구조 단언만 유지.
- **뮤테이션 3 → 7종**: M4(활성 예약 제거) · M5(휴지통 예약 제거) · **M6(슬롯을 앞에 삽입 → 열 순서
  파괴)** · M7(CSS 를 바닥 규칙으로 되돌림). M6 이 리뷰어가 지목한 "오배치 통과" 구멍을 겨냥한다.
- **죽은 선언 제거**: 슬롯의 `display: inline-block`(flex item 이라 blockify) · `text-align: center`
  (버튼 UA 기본값이고 슬롯은 내용 없음).
- **잔여 명시**(FUNCTION.md): ① 재렌더 시 1회 열 점프(예약 범위가 목록 단위인 대가) ② 체인 간
  정렬은 보장하지 않음(AC-AVA-1 스코프는 한 체인) ③ 휴지통 `↩` 미예약은 서버가 관리 불가 행을
  응답에서 제외한다는 전제 의존 — 그 전제를 코드 주석에 기록.
- 하네스 28 → **34건**.
- Files: `src/static/app/composer.js`, `src/static/css/chat.css`,
  `tests/verify_attach_version_action_align.mjs`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`,
  `docs/reviews/20260811T1300Z-ux-design.md`, `docs/test-runs.d/20260811T1200-attach-version-action-align.md`.
- Timestamp: 2026-08-11T13:00:00+09:00
## CHG-20260811T1830-ai-claude-api-exposure-hardening — 익명 API 표면 축소 + 엣지 보안 헤더 + 데이터플레인 RO 계정

- Trigger: 사용자 보고 — 외부 AI(codex, root 계정)의 무인증 라이브 API 감사 결과 검증·대응 요청.
- 판정: 지적 9건 중 8건 사실, 1건(`DB 읽기 전용 보장 없음`)은 **진단 오판·처방 유효**. 감사자가 로컬
  코드를 못 보는 제약 아래 있어 `sql_guard` 의 sqlglot AST allowlist(fail-closed)를 알 수 없었으나,
  `DB_USER=root` 폴백이 실제로 살아 있어 DB 층 최소권한 처방 자체는 옳았다.
- 변경:
  - `src/routers/system.py` — 미인증 응답 축소 3종. `/api/session` → `{"authenticated": false}`,
    `/api/llm/health` → `{"state": ...}`(신설 `_anonymous_provider_status()`),
    `/api/api-vault/options` → `{"default_model": null, "models": []}`. **인증 응답 불변**.
    아울러 `api-vault/options` 의 예외 경로가 fail-soft 를 넘어 **fail-open**(DB 예외 시 전체 카탈로그
    반환)이던 것을 인증 확정 시에만 되돌리도록 좁혔다.
  - `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile` — `X-Content-Type-Options`·
    `X-Frame-Options`·`Referrer-Policy`·`Permissions-Policy`·`-Server` 일괄 부착 + CSP **Report-Only**.
    **HSTS 는 의도적 제외** — `/trust/*` 평문 HTTP CA 번들 배포(호스트 단위 HSTS 는 경로 예외 불가)를
    깨뜨리고 브라우저 캐시라 롤백이 즉시 반영되지 않는다.
  - `docs/SECURITY.md` — §7 allowlist 에 익명 3종 등재(축소 응답 명시) + §7.3(drift·외부 노출 실측·
    codex 지적 중 기각분) + §7.4(데이터플레인 RO 계정) 신설. §7.2 의 조건부 TODO 가 **이미 전제가
    깨진 미결 항목**임을 경고 블록으로 표기.
  - `tests/test_anonymous_surface_hardening.py` (신규) — 미인증 축소 + 인증 불변 + fail-open 차단 7건.
- 운영 조치(코드 외): `bin/agent-ro-bootstrap.sh` 로 `agent_ro` 프로비저닝 + `.env.mysql` 자격증명 설정.
  권한 경계 5축 실측 검증 완료. **효력은 컨테이너 재시작 시점부터**.
- 검증: 신규 7 PASS · `test_di_seam_p5b` 31 PASS · pytest 전량 EXIT=0(사전 실패 1건은 main baseline
  동일 재현 확인) · `caddy validate` adapt 성공 · `agent_ro` 5축 실측.
- 미조치: 공인 IP 노출 유지·차단은 서비스 중단 수반 → 사용자 결정 대기. 배포 미수행.
- Timestamp: 2026-08-11T18:30:00+09:00

## CHG-20260812T010301-doc-sync-rn-0812 (2026-08-11 · 2026-08-07 블록) 릴리즈노트 콘텐츠 — 신규 2블록 13항목 prepend(문서 원문 보기 · 액션 열 정렬 · `_` 밑줄 · 자체 점검 접지 · 배포 창 503 / 그룹 가이드 툴팁 · 구문 색 · 줄 안 변경 · 내용 동일 원문 · 접미사 토글 · 체인 병합 · 등록 시각 · 대기 탈출구)
- 사용자 노출 릴리즈노트(`static/release-notes-data.js`) 최상단에 신규 date "2026-08-11" 블록(5 items: new/work 1 · fixed/work 3 · fixed/common 1) + "2026-08-07" 블록(8 items: new/work 1 · improved/work 5 · fixed/work 2) 을 최신-먼저 순으로 prepend + `generated` "2026-08-06"→"2026-08-11". 기존 44 블록 전량 보존(releases 44→46). 두 배포일 블록이 모두 부재했으므로 append 아닌 신규 2블록 prepend.
- 평이화/비노출: feature-id·§번호·PR#·commit sha·모듈/함수명·테이블명·내부 설정키·ADR·PB-0008·인프라 용어(replica/upstream/Caddy/readyz) 누출 **0**(19 패턴 정규식 기계 검증). UI 라벨은 실코드 대조 — `app/composer.js:1192`(`v{n} 원문 보기` 👁)·`:1148`(`⇄ 버전 비교`)·`:1028`(`ATTACH_SUFFIX_LABEL` 버전 표시 체크박스)·`:1573-1582`(등록 시각 compact `14:20`/`8/6`/`25/8/6`)·`app/attach-diff.js:1123`(`문서 원문`)·`:825-829`(`좌우 2열`/`단일열`/`동일한 줄도 모두 보기`)·`:900`·`index.html:261-275`(`그룹 대화 사용법` 5줄·`다시 안 보기`).
- 정직성 교정 4건(적대검증 반영): ① identical 화면의 비교 전용 조작은 **숨김이 아니라 비활성**(`attach-diff.js:905-928` `b.disabled = !hasDiff` + `css/chat.css:2981` `.is-disabled{opacity:.55}` — 코드 주석이 숨김을 명시적으로 기각) → "나타나지 않습니다"→"흐리게 바뀌어 눌리지 않습니다" ② 배포 창 길이에 정본이 명시한 outlier 보존(12~17초, 한 번은 41초) ③ 수정 후 창의 트래픽이 **더 많았다**는 정본 논거 보존("같은 규모"→"그보다 적은 111건") ④ 아이콘 열 정렬 보장 스코프는 정본 `FUNCTION.md:3078-3080`(AC-AVA-1 = 한 체인 안)에 맞춰 "어느 행에서나"→"한 파일의 버전 이력 안에서".
- 캐시버스터 수기 bump 없음(빌드 주입 메커니즘 — ITEM-09). `index.html`/`admin.html` 무변경.
- Verification: `node --check` PASS · `verify_release_notes.mjs` **34 pass / 0 fail**(변경 전 baseline 동일) · 블록 순서(46 · head=2026-08-11)·항목 enum(type/area)·스키마 외 키 0·기존 블록 보존·`generated`==head.date 확인 · 내부용어 누출 0.
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).
- Reason: changed paths are docs + 비-정책 static data only — 코드/스키마/권한 변경 0.
- Timestamp: 2026-08-12T01:03:01+09:00
## CHG-20260811T1845-ai-claude-corp-attach-diff-bubble-chip — 말풍선 수정본 첨부 칩의 diff 진입 버튼

- **What**: assistant(및 사용자 재업로드) 말풍선 첨부 칩에 `⇄` 버튼을 얹어, 그 칩이 가리키는
  버전의 **직전 ↔ 자신** 쌍으로 기존 첨부 버전 비교 모달을 연다.
- **Why**: 비교 모달은 `(attach-version-diff, 2026-08-06)` 이후 있었지만 진입점이 첨부 사이드
  패널에만 있었다 — 변경을 만든 화면(말풍선)에서 그 변경으로 가는 길이 없었고, 칩에서 가능한
  일은 다운로드뿐이었다(사용자 캡처가 지목한 상태).
- **모달·렌더러는 재사용**: `openAttachmentDiffModal` / `openAttachmentSourceModal` 를
  `messages.js` 가 import 한다. diff 표를 이 모듈이 다시 그리지 않는다 — 렌더러를 복제하면
  규칙이 두 벌이 되고, 이 저장소는 그 기전으로 단일열 배경 소실 회귀를 이미 치렀다
  (`attach-diff-unified-bg`). 하네스 D2 가 복제 0 을 소스에서 잠근다.
- **preselect 가 이 변경의 실질**: 모달 기본값은 "직전↔최신" 이라, 체인이 v1~v7 인데 v2 칩을
  누르면 `6↔7`(이 답변과 무관한 쌍)이 열린다. 그래서 `to` = 이 칩의 버전, `from` = 체인에
  **실제로 남아 있는** 직전 버전으로 지정한다. `thisVer - 1` 을 쓰면 중간 버전이 삭제된
  체인에서 없는 번호를 지정해 `<select>` 가 조용히 첫 옵션으로 떨어진다(무음 오표시).
- **재진입 가드가 필요했던 이유(codex P2 → 구현 결함 발견)**: 첫 판은 `btn.disabled` 하나로
  중복 클릭을 막았고 테스트도 disabled 상태만 단언했다. 리뷰어가 "그 테스트는 중복을 실제로
  막는지 검증하지 않는다" 고 지목해 왕복을 붙잡고 3회 클릭하도록 고치자 **구현이 red 로
  뒤집혔다** — `disabled` 는 trusted 클릭만 막고 프로그램 dispatch 는 리스너를 실행한다.
  상태 플래그(`dataset.diffBusy`)를 추가해 왕복 자체를 1회로 봉인했다.
- **403 중복 토스트**: `apiFetch` 가 403 에 공통 토스트를 내는데 catch 가 또 냈다 — 같은 사유가
  두 번 뜨고 두 번째가 첫 번째의 표시 시간을 리셋한다. 403 은 공통 처리에 위임.
- **hover 는 대비 실측이 설계를 바꿨다**: 색 토큰 규칙(feature AGENTS.md)에 맞춰
  `--primary-soft` 배경 + `--primary` 글자로 갔더니, assistant 칩 배경이 `--surface`(흰색)라
  **배경 대비 1.09** 로 hover 가 사실상 안 보였다(실브라우저 토큰 실측). 형제
  `.message-action-btn:hover` 가 border-color 를 함께 바꾸는 것과 같은 취지로 `inset` 그림자
  테두리를 더했다 — `inset` 이라 **레이아웃 이동 0**(옆 `↓` 좌표 Δ0 실측).
- **Verification**: 신규 하네스 47 PASS · 뮤테이션 **12/12 red** · 기존 mjs 전수 50 suite /
  1,684 체크 0 FAIL · 실브라우저 기하 55 PASS · **PB-0008 실 Windows Chrome/150 전축 PASS**
  (bind-mount 프리뷰 `:18099`, 라이브 무접촉) · codex 적대 리뷰 P1 0 / P2 4 전건 반영.
- Files: `src/static/app/messages.js`, `src/static/css/chat.css`,
  `tests/verify_attach_bubble_diff_entry.mjs`, `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md`,
  `docs/test-runs.d/20260811T1845-attach-diff-bubble-chip.md`,
  `docs/evidence/attach-diff-bubble-chip/*.png`.
- Timestamp: 2026-08-11T18:45:00+09:00

## CHG-20260812T0030-ai-claude-corp-attach-diff-bubble-chip-postdeploy — POST-DEPLOY 라이브 실측 기록 (doc-only)

- **What**: PR #1215 머지(main `eac20796`) → `deploy-web --web-only` 후 라이브에서 말풍선 칩
  `⇄` → diff 패널을 재실측하고 fragment Run 2 · TEST.md 에 기록. 코드 변경 0.
- **파리티 실측**: web-a/web-b 양쪽 `mysql-ai-web:eac20796` healthy · 서빙 `messages.js` 가 main
  blob 과 byte-identical(`?v=` 정규화, 스탬프 `73f92614ff4d`) · `chat.css` `.attach-chip-cmp` 4 hit.
- **결과**: 칩 4 · `⇄` 4(20×17px) · 클릭 → 모달 1개 `v1 ↔ v2`(옵션 7 · `+1 / -0` · 행 6) ·
  페이지 이동 0 · pageerror 0 — **배포 전 bind-mount 프리뷰 결과와 차이 0**.
- Files: `docs/{TASK,TEST,MODIFY}.md`, `docs/test-runs.d/20260811T1845-attach-diff-bubble-chip.md`,
  `docs/evidence/attach-diff-bubble-chip/04-postdeploy-live-diff-modal.png`.
- Timestamp: 2026-08-12T00:30:00+09:00

## CHG-20260812T172625-ai-claude-corp-db-picker-layout-stability — '+ 데이터베이스 추가' 목록 위치 안정성 (Minor §12.3, frontend-only)

- **Why**: 사용자 보고 — "참조할 DB 목록에서 체크박스를 활성화/비활성화 할 때, 추가/제거되는
  요소에 따라 목록의 위치가 상대적으로 밀려나는 현상이 나타나 사용하기 번거롭습니다."
- **기전**: `.cov-db-editor` 가 `[등록 DB 목록] → [picker]` 순서라, 체크 한 번마다
  `redrawChips()` 가 **위쪽** 목록에 행을 더해 열려 있는 드롭다운을 밀었다. 실 chromium 실측
  단일 38.3px · 해제 37.4px · 연속 3회 114.3px · 정규식 일괄 114.3px — 항목 행 높이(29px)보다
  커서 다음 클릭이 **다른 DB 에 떨어진다**. 같은 결함이 `+ 데이터소스 추가` 에도 있었다(42px).
- **What**: ① 두 picker 를 각자의 재구성 대상 **앞**으로 이동(`dbEditorWrap` = picker →
  chipWrap · `dbSection.insertBefore(addRow, dsAccordion)`) — 흐름상 위가 안 바뀌면 아래가 밀
  방법이 없다. 스크롤 보정 방식은 scrollTop=0 구간에서 원리적으로 실패해 불채택. ② degraded
  배너 삽입점을 picker 위 → 목록 위(비동기 배너가 같은 밀림을 재생산하지 않게). ③ 선택 카운트
  (`선택됨 N개`, `role=status`)를 검색 toolbar 노출 임계 미만에서도 상시 렌더. ④ 두 picker 의
  드롭다운 내부 `scrollTop` 을 재구성 전후로 보존(필터 적용 뒤 복원). ⑤ `.admin-db-picker-list`
  `max-height` 220px → `min(50vh, 420px)`(sticky toolbar 112px 가 절반을 먹어 후보 130개 중
  3~4행만 보이던 것 → 10행). ⑥ 빈 상태 안내의 방향 지시어를 "아래에서" → "위 '+ … 추가' 에서"
  (등록 DB 목록 + 바인딩 없는 datasource 2곳).
- **Verification**: 신규 하네스 2종 — jsdom 25(순서 + **토글 시 picker 상류 마크업 불변** +
  방향 지시어 census, 순서 되돌림 뮤테이션 역검증) · 실 chromium 13(축마다 뮤테이션 역검증으로
  38~115px 재현). 기존 feature-0003 mjs **53 suite 전건 PASS** · pytest 4,287 수집 EXIT=0
  (사전 실패 `test_oauth_exhaustion_gate` = `chattr` 부재, main baseline 동일분 제외) ·
  **PB-0008 실 Windows Chrome/150 PASS**(bind-mount 프리뷰 `:18099`, 라이브 무접촉, 서버 정본
  무변경 확인) · codex 적대 리뷰 P1 1 / P2 1 전건 반영.
- Files: `src/static/admin/products.js`, `src/static/css/admin.css`,
  `tests/verify_dbpicker_layout_stability.mjs`,
  `tests/headless/verify_dbpicker_layout_stability.py`,
  `docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md`,
  `docs/test-runs.d/20260812T172625-dbpicker-layout-stability.md`,
  `docs/evidence/pb0008-dbpicker-layout-stability*.png`.
- Timestamp: 2026-08-12T17:26:25+09:00

## CHG-20260812T1810-ai-claude-corp-db-picker-layout-stability-postdeploy — POST-DEPLOY 라이브 실측 기록 (doc-only)

- **What**: PR #1221 머지(main `d619259d`) → `make deploy-web-only` 후 라이브에서 재실측하고
  fragment Run 2 · TEST.md · TASK.md 이월 항목에 기록. 코드 변경 0.
- **파리티 실측**: web-a/web-b 양쪽 `mysql-ai-web:d619259d` healthy · `/healthz
  git_commit=d619259d` · 서빙 `css/admin.css` 에 `min(50vh, 420px)` · `admin/products.js` 의
  picker→chipWrap 순서 · `insertBefore(addRow, dsAccordion)` 확인 · 스탬프 `c1426a14086f` ·
  엣지 `no upstreams available` **0건**(무중단 실측).
- **결과**: 드롭다운 `420px` / **가시 10행** — 배포 전 프리뷰에서 구 CSS 가 `immutable` 로
  붙들려 이월했던 축을 **캐시 우회 없이** 종결. 실 클릭 이동 **0px** + 같은 좌표 동일 DB 유지,
  역검증 **+38px** 재현. pending 새로고침 후 0 · 서버 정본 16/1 → 라이브 데이터 변경 0.
  **배포 전 프리뷰 결과와 차이 0**.
- Files: `docs/{TASK,TEST,MODIFY,REVIEW}.md`,
  `docs/test-runs.d/20260812T172625-dbpicker-layout-stability.md`,
  `docs/evidence/pb0008-dbpicker-layout-stability-postdeploy-20260812.png`.
- Timestamp: 2026-08-12T18:10:00+09:00
## CHG-20260812T181700-ai-claude-hangul-qwerty-search — 한/영 자판 교차 검색 (Minor §12.3)

- Date: 2026-08-12. REQ-20260812-hangul-qwerty-search. 사용자 요청(첨부 화면 2건: 제품 드롭업
  `ㅈ듀` → "검색 결과가 없습니다", 제품 관리 `ㅎㅋ` → "제품이 없습니다").
- **신규 primitive 2벌(같은 매핑표)**:
  - `src/static/hangul-qwerty.js` — ESM. `hangulToQwerty` / `qwertyToHangul`(IME 조합 오토마타)
    / `searchVariants` / `matchesSearchQuery` / `matchesAnyVariant`.
  - `shared/hangul_qwerty.py`(§17 교차참조 기록) — 서버 동형. web·agent 두 서비스가 공유해야
    하므로 feature 내부 `modules/` 가 아니라 `shared/` 에 둔다(이미지에서 `from modules import`
    는 feature-0002 패키지를 가리켜 ImportError 가 된다 — 배포 시점에야 드러날 결함을 선차단).
- **클라이언트 배선 13곳**: `static/app.js`(제품 드롭업 필터 · 검색결과 메시지 점프),
  `static/app/sidebar.js`(폴더 이동), `static/admin.js`(DB picker 순수/DOM 필터 2),
  `static/admin/{products,accounts,roles,datasources,settings,usage,metadata}.js`(제품·계정·
  역할·데이터소스·설정·사용량 드릴·메타데이터 목록/부트스트랩 테이블), `static/graph/graph-ctxmenu.js`
  (검색 관련도 채점을 후보 최댓값으로).
- **서버 배선 6경로**: `routers/_conv_store.py`(대화 검색 PG/MySQL 두 경로 + 신규 헬퍼
  `_search_like_patterns`/`_like_any_clause`), `routers/_prompt_context.py`(매칭 발췌·매칭
  첨부 파일명 — 발췌 위치 탐색도 후보 기준), `routers/admin_conversations.py`(보관 대화),
  `routers/_audit_infra.py`(감사 로그 `q` — ActionCode/ResourceId 는 영문이라 한글 오타 흡수가
  특히 유효), `unit/feature-0002-agent-core/src/modules/metadata_graph.py`(그래프 Cypher 이름/
  FQN/카테고리 + 분석문 본문 — cross-feature 편집).
- **회귀 0 설계**: 후보 배열의 첫 항목이 항상 원문이라 변환 대상이 없는 검색어는 후보가 1개이고
  조립 SQL 이 종전과 문자열 동치다(pytest 가 기계 단언). 후보는 **2자 이상**만 채택 —
  1자 후보(`dk` → `아`)가 정상 결과를 오염시키는 것을 하네스가 실측 포착해 게이트를 넣었다.
- 신규 테스트: `tests/verify_hangul_qwerty.mjs`(48건 — 변환 왕복·후보 계약·JS↔Python 매핑표
  파일 대조·배선 census), `tests/test_hangul_qwerty.py`(39건). 기존 하네스 4종
  (`verify_product_picker_search` · `verify_dbpicker_search_regex` · `verify_dbpicker_layout_stability`
  · `verify_metadata_bs_paging`)은 classic 주입 realm 에 primitive 를 선주입하도록 보강
  (`tests/esm-classic-inject.mjs` 에 `hangulQwertyClassicSource` 추가) — stub 이 아닌 정본 소스를
  넣어 vacuous 통과를 막았다.
- 기존 테스트 갱신: `unit/feature-0002-agent-core/tests/test_graph_search_content.py` 2건 —
  후보 확장에 맞춰 "플레이스홀더 수 = 파라미터 수" 정합을 단언하도록 강화(완화 아님).
- 회귀: pytest 전 스위트가 main 기준선과 동일(사전 실패 `test_oauth_exhaustion_gate` = `chattr`
  부재 1건만) · 프론트 mjs 하네스 54종 전건 PASS.

## CHG-20260812T190500-ai-claude-hangul-qwerty-search-codex — 적대 리뷰 지적 6건 반영 (같은 cycle)

- Date: 2026-08-12. REV-20260812T181700-hangul-qwerty-search [CODEX] 의 P2 5건 · P3 1건 반영.
- `shared/hangul_qwerty.py` · `static/hangul-qwerty.js`: 최소 길이 게이트를 **원문에도** 적용
  (1자 검색어는 확장 자체를 하지 않음 — `가` → `rk` 로 `marketing`·`worker` 가 잡히던 경로).
- `routers/_audit_infra.py` · `routers/admin_conversations.py`(PG·MySQL): LIKE 에 `ESCAPE '!'` +
  3-char escape 적용 — 두 엔드포인트는 종전부터 escape 가 없어 `%`/`_` 가 와일드카드로 샜다
  (SECURITY §8.3 규약 위반 상태). 후보 확장으로 같은 라인을 건드리는 cycle 에서 함께 봉인.
- `unit/feature-0002-agent-core/src/modules/metadata_graph.py`: pg_trgm relevance 점수를 후보
  집합의 **최댓값**으로 산출 — 원문만 채점하면 변환 후보로 매칭된 노드가 score≈0 이라
  정렬 후 `limit` 재절단에서 탈락(매칭됐는데 결과에서 사라지는 경로).
- `static/app.js` `_searchHighlight`: 강조를 후보 집합 교대 패턴으로 — 반대 자판 매칭 결과가
  강조 0 이던 것 해소.
- 회귀 테스트 3건 신설(원문 1자 게이트 · 감사 escape · 보관 escape). mjs 49 · pytest 41 PASS.
## CHG-20260812T1739-ai-root-metadata-pane-refresh — 메타데이터 pane 입력 UI 통합 표 재구성 (Major §12.3)

- **Why**: 사용자 보고 — "서비스 내 메타데이터 입력창이 다른 화면에 비해 촌스럽다는 의견을
  받았습니다. 다른 모범적인 웹사이트를 참조하여 세련된 형태로 재구성해줄 수 있을까요?"
  조사 결과 다수가 취향이 아니라 **이 pane 만 앱 디자인 시스템의 토큰·계약을 안 쓰는** 것이었다
  (D1 포커스 halo 부재 · D2 박스-안-박스 격자 · D3 raw `●`/`○` 글리프 · D4 등폭 하드코딩 ·
  D5 전각 `＋` · D6 저장 버튼 2줄 줄바꿈 · D7 회색 패널 3중 중첩 · D8 컬럼명 가변 폭).
  사용자 결정(2026-08-12): 시각 방향 = 통합 표 + 프리미티브, 범위 = 메타데이터 pane 전체.
- **What (표시 계층만 — 백엔드·라우터·권한·스키마·마이그레이션 0)**:
  - `static/css/search-audit.css` — pane 지역 토큰 4종(+열 폭 2종, sticky inset 1종) 신설,
    `.admin-meta-input` 을 `base.css .field` 계약과 동일한 halo·hover·transition 으로 승격,
    골격 결과를 **단일 표 surface + hairline row-group + ghost cell + 상태 dot** 으로 재조립,
    서브탭 `::after` 인디케이터, 목록 카드 `--r-md` + hover elevation + 선택 좌측 accent rail,
    검토 큐/그룹/스켈레톤/페이저/rel-panel 정합, `overflow: hidden` → `clip`(sticky 실효화).
  - `static/admin.html` — sticky 열 헤더 markup(`#metadataBootstrapGridHead`, 결과 컨테이너 바로
    앞 형제) 신설, 전각 `＋` → ASCII `+` **3곳**.
  - `static/admin/metadata.js` — 힌트에서 raw 글리프 제거(문구 보존) + `is-complete` 3단 상태,
    열 헤더 가시성 `hidden` 단일 채널 동기 3지점. **DOM 셀렉터·dataset 계약 무변경**.
  - 신규 `tests/verify_metadata_pane_refresh.mjs`(80 checks, 뮤테이션 10/10 KILLED) ·
    `tests/headless/verify_metadata_pane_refresh_render.py`(30 checks, 실렌더 계측).
- **사전 검증이 잡은 것 2건 (배포 전 수정)**:
  1. **대비 미달** — headless 실렌더 계산에서 상태 라벨 `--text-muted` 가 흰 행에서 **4.12:1**,
     열 헤더가 `--surface-2` 에서 **3.58:1** 로 WCAG AA 미달 → `--text-2` 승격(7.11 / 6.18).
     (상태 라벨 미달은 종전 힌트에도 있던 **선재 결함**의 해소이기도 하다.)
  2. **sticky 무동작·행 비침** — `top: 0` 은 스크롤포트 *padding box* 기준이라 `.admin-detail-col`
     의 `padding-top` 18px 띠로 직전 행이 헤더 위에 반쯤 비쳤다(PB-0008 캡처 판독 적발) →
     `top: calc(-1 * var(--meta-grid-head-inset))`. 결합은 하네스가 대조 검사.
- **검증**: 신규 80 + headless 30 · 기존 metadata 하네스 5종 **154 checks 전건 green** ·
  mjs 53 파일 전건 green · pytest **4312 passed / 1 failed**(그 1건은 pristine main 동일 재현
  = 선재 red) · **PB-0008 실 Chrome 150** 격리 컨테이너 실측 PASS(열 정렬 편차 0.00px/30행,
  라이브 데이터 변경 0).
- **base 갱신**: 작업 중 main 이 **12 커밋 전진**(병렬 세션 PR 머지)해 pytest 7건이 base staleness
  로 red 였다 → `origin/main`(6a419f38) 리베이스 후 0. 착수·검증 직전 `rev-list origin/main..HEAD`
  확인이 필요하다는 선례 재확인.
- Files: `src/static/css/search-audit.css`, `src/static/admin.html`,
  `src/static/admin/metadata.js`, `tests/verify_metadata_pane_refresh.mjs`,
  `tests/headless/verify_metadata_pane_refresh_render.py`,
  `docs/{DESIGN,FUNCTION,TASK,TEST,MODIFY,REVIEW,REPORT}.md`,
  `docs/test-runs.d/20260812T183000-metadata-pane-refresh.md`,
  `docs/evidence/{pb0008-metadata-pane-refresh,pb0008-metadata-form-refresh,headless-metadata-pane-refresh}-20260812.png`,
  `../../docs/STATUS.md`.
- **codex 적대 리뷰 (P1 0 · P2 3) 전건 반영** — ① 고정 폭 + ellipsis 로 잘리는 컬럼명·타입에
  `title` 회수 경로 부여(+ 타입 칸 5.5→7rem) ② 정적 markup 만 고쳐 남아 있던 **JS 동적 라벨**의
  전각 `＋` 3곳 교체(empty-state·ENUM '코드 추가') ③ pane 지역 토큰의 리터럴 색을 **전부 `:root`
  파생**으로 전환(`color-mix(in srgb, var(--primary) 12%, transparent)` 등 — `docs/AGENTS.md`
  §색상/§10 준수) + hover 경계 `#d4d2ca` → `--meta-border-hover` 파생. 파생이 값을 바꾸지 않았음은
  **합성 픽셀 대조**로 확인(headless Δ=0 · 실 Chrome Δ=1/255 한 채널). data URI 안 SVG 색만 파생
  불가(브라우저가 `url()` 안 `var()` 미해소)라 값 복제 + 하네스 대조 검사로 봉인.
- **재검증**: mjs **90 checks**(뮤테이션 2라운드 누적 **15/15 KILLED**) · headless **32 checks** ·
  mjs 53 파일 green · pytest 1,390 PASS · 실 Chrome 재확인(columns title·입력란 x 편차 0.00px·
  페이지 전체 전각 `＋` 0건).
- Timestamp: 2026-08-12T19:15:00+09:00

## CHG-20260812T2005-ai-root-metadata-pane-refresh-postdeploy — POST-DEPLOY 라이브 실측 기록 (doc-only)

- **What**: PR #1231 머지(main `e250dad7`) → `make deploy-web-only` 후 라이브 배포본에서 전 축을
  재실측하고 fragment Run 3 · TEST.md · TASK.md 이월 항목에 기록. **코드 변경 0.**
- **배포 파리티 실측**: web-a/web-b 양쪽 `mysql-ai-web:e250dad7` healthy · 서빙
  `css/search-audit.css?v=06bd063c9b98`(빌드 주입) · 서빙 HTML 에 `metadataBootstrapGridHead` 존재 ·
  엣지 `no upstreams available` **0건**(12분 창 — 무중단 실측) · soak 통과.
- **결과**: 프리뷰와 **차이 0** — 열 정렬 편차 0.00px(30행), sticky 도킹 272==border edge,
  포커스 halo 토큰 파생 정상 해소(`color(srgb …/0.12) 0 0 0 3px`), 상태 3단 전이, `D2Coding`,
  버튼 nowrap, 전각 `＋` 0건. 라이브 데이터 변경 0(저장 미클릭 · 목록 `1건` 불변).
- Files: `docs/{TASK,TEST,MODIFY,REVIEW}.md`,
  `docs/test-runs.d/20260812T183000-metadata-pane-refresh.md`(Run 3),
  `docs/evidence/pb0008-metadata-pane-refresh-postdeploy-20260812.png`.
- Timestamp: 2026-08-12T20:05:00+09:00
## CHG-20260813T010301-doc-sync-rn-0813 (2026-08-12 블록) 릴리즈노트 콘텐츠 — 신규 1블록 9항목 prepend(한/영 자판 검색 · 말풍선 칩 ⇄ · DB 객체 탐색 · 첨부 `.md` 렌더 · 메타데이터 pane · DB 추가 목록 밀림 · 일시 장애 보존 · 긴 대화 최신행 · 배포 중 답변 끊김)
- 사용자 노출 릴리즈노트(`static/release-notes-data.js`) 최상단에 신규 date "2026-08-12" 블록(9 items: new/common 1 · new/work 2 · improved/work 1 · improved/admin 1 · fixed/admin 1 · fixed/work 2 · fixed/common 1) prepend + `generated` "2026-08-11"→"2026-08-12". 기존 46 블록 전량 보존(releases 46→47). 그 배포일 블록이 부재했으므로 append 아닌 신규 블록.
- 평이화/비노출: feature-id·§번호·PR#·commit sha·모듈/함수/파일명·테이블명·내부 설정키·ADR·PB-0008·인프라 용어(replica/gateway/worker/quiesce/OAuth/SSE/MCP/SSOT/alembic)·픽셀 단위 누출 **0**(22 패턴 정규식 기계 검증).
- 적대검증 반영 6건(렌즈 A 언어): ① 배포 항목의 운영자향 2문장 제거(사용자 관점 결론으로 닫음) ② '저장된 처리 절차'→정본 릴리즈노트가 실제로 쓰는 **'함수·프로시저'**(정본 17회, '저장된 처리 절차' 0회) + 관계도 반영 시점 hedge 를 07-30/07-31 블록의 확립 문형으로 교체 ③ 메타데이터 상태 라벨을 실코드 문자열로 정정(`admin/metadata.js:2613` = `"설명 입력됨"`/`"비어있음"`, **화면에 '완료' 라벨 없음** — 색점 3단이라 그대로 서술) + '옅게' 비문 해소 ④ 픽셀 수치(38/114px)를 '줄' 단위로 환산(정본 릴리즈노트 2,232행에 '픽셀'·'px' **0회** — 문체 선례 부재) ⑤ 한/영 항목 178자 단일 복문을 작업 화면/관리 콘솔 2문장으로 분해 ⑥ DB 객체 항목 area `common`→**`work`**(정본 통계: 관계도 title 항목 45건 전부 `admin`, AI 조회·답변 능력은 `work` 표준. 본 항목 주축은 AI 탐색이라 work).
- **적대검증 refute 3건(배포 게이트) — 물리 실측이 정본 문면을 정정**: 렌즈 B 가 ⓐ feature-0040 을 blocker('REPORT §1 배포 미수행 · §5 SSOT 데이터 미충전')로, ⓑ conv-audit 2차(`f0147fcc`)를 major(TASK 배포 체크박스 열림)로, ⓒ 한/영 자판을 major(배포 체크박스·실측이 라이브 아님)로 지목했으나 **라이브 실측은 전부 반대**였다 — alembic 라이브 head `0055_tool_call_usage`(= 저장소 `MAX_MIGRATION.txt`, 즉 `0054_db_objects` **적용됨**) · `db_objects` **339행 충전**(미충전 아님) · 서빙 static 6종 브랜치 blob 과 byte-identical · 근거 커밋 전건이 라이브 이미지(web `105fa2b7` / agent `e1372f32`)의 조상. 즉 정본 REPORT/TASK 는 **커밋 시점 스냅샷**이고 그 뒤 wrapper 가 배포했다(정본 lag = feature-cycle 소관, report-only). 다만 실증되지 않은 동작 주장(2차의 '소진 시 재개해 답변 완주')은 보수적으로 문면에서 제외했다.
- 캐시버스터 수기 bump 없음(빌드 주입 메커니즘 — ITEM-09). `index.html`/`admin.html` 무변경.
- Verification: `node --check` PASS · `verify_release_notes.mjs` **34 pass / 0 fail**(편집 전 baseline 동일) · 블록 순서(47 · head=2026-08-12)·항목 enum·스키마 외 키 0·기존 블록 보존·`generated`==head.date 확인 · 내부용어 누출 0.
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).
- Reason: changed paths are docs + 비-정책 static data only — 코드/스키마/권한 변경 0.
- Timestamp: 2026-08-13T01:03:01+09:00
## CHG-20260813T1224-attach-source-compare 문서 원문 화면의 버전 비교 + "비교할 것이 없으면 원문" 수렴(두 화면) + 목록 비교 버튼 기본쌍 최초→최신

- **원문 모달에 비교를 들였다**(REQ-20260813-attach-source-compare-①). `openAttachmentSourceModal`
  이 두 화면(원문/비교)을 갖는다: 컨트롤 바의 `비교 기준` select 로 전환하고, 다른 창을 띄우지
  않는다. 체인은 `/source` 응답의 신규 `versions` 로 오므로 **왕복은 여전히 1회**(`/versions` 를
  부르면 presign N회 + 왕복 2회가 되고, "원문 모달의 요청은 `/source` 하나" 라는 기존 계약도 깨진다).
  체인 1개면 select 를 숨긴다 — 버전 하나짜리 첨부가 이 모달의 원래 대상이다.
- **"비교할 것이 없다" 를 한 화면으로 수렴**(②). 종전 비대칭: 내용이 동일한 쌍(`identical`)은 이미
  원문을 출력했는데(08-07), **같은 버전** 두 개를 고른 화면은 "서로 다른 두 버전을 선택하세요" 안내만
  남아 본문이 0 이었다. 이제 원문 모달의 같은-버전 선택은 **재요청 없이** 받아 둔 원문을 다시 그리고,
  비교 모달의 `from==to` 는 그 버전 id 의 `/source` 를 불러 원문 + `같은 버전을 선택했습니다 — vN
  원문입니다.` 배너를 낸다(제목이 여전히 "버전 비교" 라 배너가 없으면 고장으로 읽힌다). 배너는 렌더
  옵션에 담아 토글 재렌더에도 유지한다 — 한 번만 append 하면 다음 렌더에서 조용히 사라진다.
  `/diff` 의 `from==to` **400 은 그대로**다(존재 여부 oracle 방지 계약) — 같은 버전은 그 버전의 id
  로 답한다.
- **목록의 `⇄ 버전 비교` 기본쌍 = 최초 → 최신**(③). 이 버튼은 체인 전체를 대표하는 진입점이고
  직전↔최신은 각 버전 행의 `⇄` 가 이미 담당한다 — 두 진입점이 같은 쌍을 열던 중복도 사라진다.
  번호는 배열 순서가 아니라 **값의 min/max** 로 얻는다(중간 버전이 삭제된 체인에서 없는 번호를
  preselect 하면 `<select>` 가 조용히 첫 옵션으로 떨어져 엉뚱한 쌍이 "최초↔최신" 으로 보인다 —
  말풍선 칩에서 이미 관측된 기전).
- **복제 제거가 이 변경의 절반이다**. 원문 모달이 비교를 수행하게 되면서 판정·렌더·문구 사본이 세 벌이
  될 자리였다: ① `_bodyState(data, kind)` — 본문 유무/원문 뷰/diff 표 유무의 **단일 판정면**(두 모달의
  `syncHlToggle`·`syncDiffOnlyControls`·`syncToggles` 가 전부 이것을 호출) ② `_renderSourceBody()` —
  `/source` 응답 → 원문 화면(두 모달 공유) ③ `_sourceClipped`/`_sourceStatsText`/`_diffStatsText` —
  제목·통계 문구 ④ `_mdBlockedNotice`/`_mdFallbackNotice` — 마크다운 배너 문구 ⑤ 서버 `_version_side()`
  — 버전 요약 형식(`/diff` 의 nested `_side` 를 모듈 레벨로 승격, `/source` 의 `version`·`versions` 와
  공유). 표 렌더러는 종전대로 `_renderSource` 하나다.
- **서버**: `get_attachment_source` payload 에 `versions`(체인 요약, ASC) 추가. 노출은 `/versions`
  응답의 **부분집합**(서명 URL·ObjectKey 없음)이고 게이트는 무변경(read.{own,any} + D21 pending).
  체인 조회 실패는 **fail-soft** — `versions: []` 로 답해 비교만 없애고 원문은 준다(원문 보기가 이
  조회에 종속되면 쿼리 한 번의 실패가 "내용을 볼 수 없음" 으로 번진다). 바이너리 강등 payload 에도
  체인을 싣는다(그 화면의 비교는 메타 비교로 답할 수 있다).
- **CSS 트랩 봉인**: `.attach-source-cmpctl` 은 `.attach-diff-ctl` 의 `display:inline-flex` 를 물려받아
  UA `[hidden]{display:none}` 를 이긴다 → `.attach-source-cmpctl[hidden]{display:none}` 추가. jsdom 은
  `.hidden` 속성만 보므로 이 축은 CSS 로만 닫힌다(선행 cycle 이 hl 토글에서 같은 기전을 적발·문서화).
- **diff 전용 컨트롤의 노출 정책이 두 모달에서 의도적으로 다르다**: 비교 모달은 상시 노출 + 비활성
  (그쪽은 diff 가 기본 화면이라 사용자가 버튼 위치를 외운다 — 숨기면 `margin-left:auto` 때문에 바가
  흔들린다), 원문 모달은 비교 상태에서만 노출(기본 화면이 원문이라 상시 노출하면 대부분의 시간에 쓸 수
  없는 컨트롤이 떠 있다). 원문 모달에는 gap 국소 전개를 두지 않는다 — 전개는 전체 맥락 재요청 + 쌍별
  캐시가 필요한 비교 전용 흐름이고, `동일한 줄도 모두 보기` 라는 대안 경로가 있다.
- Verification: 신규 `tests/verify_attach_source_compare.mjs` **72 checks green**(URL 별 응답 stub —
  단일 응답 stub 으로는 방향 정규화·재요청 0 축이 vacuous 하게 통과한다) · 기존 첨부 하네스 6종
  **559 checks green**(리팩터로 계약이 옮겨간 소스-grep 축 3건 갱신 — "판정면이 하나인가" 를 함수 정의
  **개수**로 단정하도록 강화) · pytest 신규 5축(C1~C5) + 첨부 2파일 **71 passed** · 전체 스위트에서
  실패 1건은 `chattr` 바이너리 부재(환경)로 **pristine main 동일 재현 — 귀책 아님**.
- Files: `src/routers/attachments.py`, `src/static/app/attach-diff.js`, `src/static/app/composer.js`,
  `src/static/css/chat.css`, `tests/verify_attach_source_compare.mjs`(신규),
  `tests/verify_attach_diff_identical_source.mjs`, `tests/verify_attach_version_diff.mjs`,
  `tests/test_attachment_source_view.py`, `docs/{TASK,FUNCTION,TEST,MODIFY,REVIEW,REPORT}.md`,
  `docs/test-runs.d/20260813T122457-attach-source-compare.md`.
- Timestamp: 2026-08-13T12:24:57+09:00
## CHG-20260813T1135-ai-claude-corp-usage-metric-charts — 사용량 요약 카드 = 차트 지표 선택기 + 프롬프트 캐시 계측·활성화 (Major §12.3)

**요청**: "[요청, 호출, 총 토큰, 입력, 출력, 비용] 패널 클릭 시 차트도 해당 값으로 부드럽게 재구성"
+ "가능하다면 cache hit 된 입출력도 항목 추가". 사용자 결정(2026-08-13): **계측 + 캐싱 활성화**.

### 화면 (feature-0003)

- `src/static/admin/usage.js` — `USAGE_METRICS` 8종 정의. 요약 카드를 `button`(aria-pressed)으로
  렌더해 지표 선택기로 전환(클릭 → `adminState.usage.metric` 갱신 → 캐시 재렌더). `renderStacked` /
  `renderDonut` / `renderStackedHBar` 를 지표 인자화하고, 키 signature 가 같으면 **노드를 유지한 채
  기하만 갱신**(CSS transition 이 걸리도록 style 로 지정). `requests` 는 비-가산이라 `by_day` 총계
  단일 막대. `buildView` 가 부분 모델 선택 시 8축을 모두 재합산. 상세 표에 캐시 2열 추가,
  `prompt`/`completion` 라벨을 `입력`/`출력` 으로(사용자 어휘 정합).
- `src/static/admin.js` — `adminState.usage.metric` 초기값(`total_tokens`).
- `src/static/admin.html` — 지표 안내 1줄(`#usageMetricNote`) + 역할·drill 카드 제목을 지표 연동
  `span` 으로. 기간 차트 제목 "토큰 사용량" → "사용량"(지표 가변).
- `src/static/css/admin.css` — 선택 카드 상태(accent 테두리·inset ring·focus-visible), 막대/도넛/
  가로막대 transition(0.42s), `prefers-reduced-motion` 존중, 도넛·hbar 인라인 style 을 클래스로.

### 집계·비용 (feature-0003)

- `src/routers/admin_usage.py` — `_estimate_llm_cost_usd` 에 캐시 인자 2개(기본 0 → 기존 7 호출처
  무회귀) + 캐시 단가 배수 상수. `admin_llm_usage` 의 totals/by_model/by_day/by_day_model/by_account
  에 지표 8축 실적재. `_aggregate_usage_by_role` 폴딩이 8축 보존. `_usage_cache_exec` 자가치유
  헬퍼(컬럼 부재 → 리터럴 0 재실행). `_query_usage_conversations`·`_query_usage_system_records` 도
  캐시 인지 비용(후자는 scope×cache 3단 사다리).
- `src/routers/profile.py` · `ai_ops.py` · `admin_console.py` — 같은 캐시 인지 비용식 적용(적용면
  전수 — 한 화면만 반영하면 화면 간 비용이 어긋난다).
- `src/app.py` — `_usage_cache_exprs` / `_usage_cache_exec` / 캐시 단가 상수 재노출.

### LLM 기록·캐싱 (feature-0002)

- `alembic/versions/20260813_0056_llm_usage_cache_tokens.py` — `cache_read_tokens` /
  `cache_write_tokens` INTEGER NOT NULL DEFAULT 0 **expand-only**. `MAX_MIGRATION.txt` 갱신.
- `src/modules/llm.py` — `_cache_tokens_of()`(최상위 → details 폴백), `_record_llm_usage` 컬럼
  사다리에 캐시 2컬럼 추가(최상단), `_apply_prompt_cache()` 신규 + 비대화 chokepoint 적용.
- `src/agent_core.py` — 대화 경로(`_call_llm`)에서 OAuth identity 주입 **뒤**에 캐시 부착.

### 테스트

- 신규: `feature-0003/tests/test_usage_metric_axes.py`(6) ·
  `feature-0003/tests/headless/test_usage_metric_switch.js`(21, 실 Chromium) ·
  `feature-0002/tests/test_llm_usage_record.py`(+8).
- 계약 갱신: `test_ai_ops.py` · `test_usage_conversations.py` · `test_usage_records_system.py` —
  SQL 컬럼 증가에 맞춰 더블 row arity·사다리 단수 단정 갱신. `_NoTargetCur` 는 "첫 실행만 실패"
  플래그 때문에 사다리 3단에서 컬럼 부재를 재현하지 못하던 것을 정정(무음 통과 차단).

## CHG-20260813T1520-ai-claude-corp-usage-metric-charts-postdeploy — POST-DEPLOY 라이브 실측 기록 (doc-only)

`docs/TEST.md` 에 Run 2(PB-0008 실 Chrome/150 라이브) + 측정 함정 기록 append, `docs/TASK.md` 에
POST-DEPLOY 종결 체크리스트 append. 코드 변경 0.

## CHG-20260813T1310-attach-source-compare-postdeploy POST-DEPLOY 라이브 실측 종결 (doc-only)

- 선행 `CHG-20260813T1224-attach-source-compare` 가 이월한 라이브 baked 자산 검증을 종결한다.
  코드 변경 0 — 기록만.
- 배포: PR #1243 → main `c5a27e0d` → `sudo make deploy-web-only`. web-a·web-b 양쪽 대상 SHA ·
  soak 통과 · 엣지 `no upstreams available` **0건**(무중단 실측) · `/healthz` 200.
- 라이브 재실측 결과 **프리뷰와 차이 0**(5단계 전 축). 캡처 5매가 커밋본과 **byte-identical** 이라
  main worktree 는 dirty 0 을 유지했다(§13.2.7 F0 — 증거 갱신이 필요 없었다).
- Files: `docs/{TASK,TEST,MODIFY,REVIEW}.md`, `docs/test-runs.d/20260813T122457-attach-source-compare.md`.
- Timestamp: 2026-08-13T13:10:00+09:00
## CHG-20260813T1550-rail-async-relayout — 우측 스크롤 ↔ 대화 뱃지 정합 (mermaid 지연 렌더)

- REQ-20260813T155000-rail-async-relayout (Minor §12.3). 사용자 보고: "채팅 화면의 우측 스크롤과
  대화 뱃지의 영역이 정합하지 않는다 — 답변에 mermaid 형식이 나타날 경우 확인된다."
- 근본 원인: `layoutMessagePointRail()` 은 호출 시점의 `messageLog.scrollHeight`·메시지 높이로
  막대 `top%`/`height%` 를 지정하는데, 재호출 트리거 5곳(렌더·prepend 보정·페이징 복원·창 확장·
  `window.resize`) 중 **콘텐츠 자체의 비동기 성장**이 없었다. ```mermaid 는
  `renderMermaidDiagrams()` 가 Promise 뒤에 SVG 를 넣으므로(mermaid-render.js) 배치가 끝난 뒤
  높이가 수백 px 뛰고, 스크롤바 thumb(실제 높이)과 rail 막대(옛 비율)가 갈라진다. 같은 성장이
  `renderMessages` 가 맞춘 "맨 아래"도 깨뜨려 최신 답변이 화면 밖으로 밀렸다.
  공유 대화 뷰(`share.js setupSharePointRail`)는 이 축을 ResizeObserver 로 이미 해결해 뒀고
  **메인 채팅 뷰만 미적용**이었다 — §16.7 G8(결정의 적용면 누락).
- 변경 (`static/app.js` 단독):
  - 신설 `_scheduleRailRelayout`(rAF 병합 · 재고정 → 배치 → 하이라이트 순서) ·
    `_observeRailContentResize`(**메시지 row `[data-message-id]` 를 관찰** — `messageLog` 는 flex 로
    높이가 고정돼 콘텐츠 성장에 ResizeObserver 가 발화하지 않는다 · 렌더마다 disconnect 후 재관찰 ·
    미지원 환경 `RAIL_RELAYOUT_FALLBACK_MS=[300,1000,2500]` 폴백 · `<img>`/`<iframe>` load capture).
  - 신설 맨-아래 pin: `_engageRailBottomPin`(settle 600ms / ceiling 8s, 재렌더는 창 연장만) ·
    `_repinRailBottomIfActive` · `_releaseRailBottomPin` · `_onRailBottomPinKeydown`.
  - 배선 6곳: engage 1(`renderMessages` bottom-scroll 직후) · observe 1(`renderMessagePointRail`
    말미) · release 4(`_animatePointScroll` · `_endAppendScrollPreserve` · 페이징 복원 rAF ·
    `_maybeExpandOrLoadOlder`). `scroll` 이벤트는 해제 트리거로 쓰지 않는다(pin 자신의 scrollTop
    변경이 scroll 을 유발해 첫 성장에서 자가 해제된다).
- codex 적대 리뷰(§18.8.2 carve-out) [P1] 2 · [P2] 2 **전건 반영**: ① `_liveSyncTick` 의 위치
  보존 분기에서 pin 해제(내가 찾은 release 4곳에 빠져 있었다) ② `#pendingAssistantBubble` 을
  관찰 대상에 포함 + **`MutationObserver`(childList)로 교체 추적** — progress.js 가 그 row 를
  `replaceChild` 하므로 한 번 observe 로는 끊긴다(호출부 점수정 대신 클래스 잠금, §16.7 G10)
  ③ 네이티브 스크롤바 조작 → 컨테이너 `pointerdown` 해제 ④ 폴백 환경 settle 창을
  `마지막 폴백+400ms` 로 연장(W8 로 불변식 잠금).
- **라이브가 자기 회귀를 잡았다**: ③의 초판은 "pin 이 설정한 `scrollTop` 과 불일치 = 사용자 조작"
  휴리스틱이었는데, **뷰포트 위쪽** 성장 시 브라우저 스크롤 앵커링의 자동 조정이 그 불일치를 만들어
  pin 이 조기 해제됐다(PB-0008 재측정 `gap=1,611px` = 수정 전과 같은 증상). 헤드리스 26축은 성장이
  아래쪽에서만 일어나 전건 통과 상태였다 — 진짜 경계축은 "성장이 뷰포트 위인가 아래인가"(§16.7 G4).
  `pointerdown` 판별로 교체 + 하네스 **T11**(위쪽 성장 시 pin 유지)·**W5b**(폐기 휴리스틱 재발
  방지) 추가 → `gap=0` 복귀.
- 검증: 신규 실브라우저 하네스 `tests/headless/verify_point_rail_async_relayout.py` **26/26 PASS** ·
  `--baseline` 재현 FAIL 4(T2 178.2px · T4 507px · T7 97.96px, T8 재현 판정 OK) ·
  기존 `verify_*.mjs` 57/57 · pytest 전건 PASS · **PB-0008 라이브 대조**(같은 대화·자산만 다른
  프리뷰 2개): 오차 86.58px→0.11px, 맨아래 gap 1,631px→0px, thumb 불일치 0, JS 오류 0.
- Files: `unit/feature-0003-agent-web-ui/src/static/app.js`,
  `unit/feature-0003-agent-web-ui/tests/headless/verify_point_rail_async_relayout.py`(신규),
  `docs/{FUNCTION,TASK,TEST,MODIFY,REVIEW,REPORT}.md`,
  `docs/test-runs.d/20260813T155000-rail-async-relayout.md`(신규),
  `docs/evidence/pb0008-rail-async-relayout-*.png`(신규 5매).
- Timestamp: 2026-08-13T15:50:00+09:00
## CHG-20260813T1543-ai-claude-corp-attach-list-name-sort — 첨부 목록 이름순 정렬

- 요청: "프로젝트 내 서비스에서, 첨부파일이 명칭 순으로 정렬되도록 구성해주세요."
- `unit/feature-0003-agent-web-ui/src/routers/conversations.py`
  - 신규 `_natural_filename_key(name)` — 숫자 구간은 int, 나머지는 casefold 문자열로 비교하는 정렬 키.
  - 신규 `_sort_attachment_rows_by_name(rows)` — 목록 정렬(이름 → 원문 → VersionNumber → Id).
    MySQL dictionary cursor 와 PG mirror 가 **같은 PascalCase 키**(`_PG_ATTACH_SELECT` alias)라 한 함수가 두 경로를 덮는다.
  - 신규 `_sort_attachment_rows_for_bulk(rows)` — 그룹(root) 사이는 그 체인의 최신 이름으로,
    그룹 안은 `VersionNumber` ASC 로 정렬(버전 체인 인접 유지).
  - `list_conversation_attachments` — PG/MySQL rows 합류 직후 정렬(경로별 collation 차이 차단).
  - `_list_deleted_conversation_attachments` — 표시 순서만 이름순. 절단 SQL(`DeletedAt DESC` + `LIMIT 200`) 불변.
  - `bulk_download_conversation_attachments` — id 필터·열람 window clip 이 끝난 rows 에 bulk 정렬 적용
    (ZIP 엔트리명 중복 번호 부여도 이 순서를 따라 결정적).
- `unit/feature-0003-agent-web-ui/src/static/release-notes-data.js` — 2026-08-13 릴리즈 블록 + `generated` 갱신.
- 신규 `unit/feature-0003-agent-web-ui/tests/test_attach_list_name_sort.py` — 12축.
- 프론트 정렬 코드 **추가 0** — 서버 응답 순서가 SSOT(중복 정렬은 두 규칙이 어긋난다).
- 무변경(의도): `/api/attachments/{id}/versions`(VersionNumber ASC) · LLM 컨텍스트 첨부 주입 순서.
- Timestamp: 2026-08-13T15:43:00+09:00

## CHG-20260813T1620-ai-claude-corp-attach-name-sort-hardening — codex 리뷰 반영

- `routers/conversations.py`
  - `_natural_filename_key` — 4,000자 초과 숫자열은 `float("inf")` 로 강등(파이썬 int↔str 4,300자리
    제한의 `ValueError` 로 목록·휴지통·일괄 다운로드가 통째로 500 이 되는 경로 차단).
  - `_sort_attachment_rows_by_name` — `original_filename`/`version_number`/`id` snake_case fallback
    (어느 read 경로가 표기를 바꿔도 정렬이 조용히 무의미해지지 않게).
- `static/app/composer.js` — `_renderAttachmentPills` 의 `newItems`·`sessionItems` 를 `byName`
  (`localeCompare` numeric + id tie-break)으로 정렬. 같은 패널의 **두 번째 렌더러**라 서버 정렬만으로는
  업로드 직후 순서가 삽입 순으로 남았다.
- 신규 `tests/verify_attach_pill_name_sort.mjs`(13) + pytest 2축 추가(N5 초장문 숫자 · S3 snake_case).
- Timestamp: 2026-08-13T16:20:00+09:00

## CHG-20260813T1700-ai-claude-corp-attach-name-sort-postdeploy — POST-DEPLOY 실측 기록 (doc-only)

- 선행 `CHG-20260813T1543-…-attach-list-name-sort` 가 이월한 라이브 baked 자산 검증을 종결한다.
  코드 변경 0 — 기록만.
- 배포: PR #1251 → main `7afed974` → `deploy-web.sh --web-only`(무중단 실측 0건 · healthz 200).
- Files: `docs/{TASK,TEST,MODIFY,REVIEW}.md`, `docs/test-runs.d/20260813T154300-attach-list-name-sort.md`,
  `docs/evidence/pb0008-attach-name-sort-3-postdeploy.png`.
- Timestamp: 2026-08-13T17:00:00+09:00

## CHG-20260813T1741-rail-async-relayout-postdeploy — POST-DEPLOY 라이브 실측 종결

- 선행 `CHG-20260813T1550-rail-async-relayout` 가 이월한 baked 자산 검증을 종결한다. 코드 변경 0 — 기록만.
- 배포: PR #1252 → main `c6c43463` → `make deploy-web-only`. 양 replica `mysql-ai-web:c6c43463` ·
  soak 통과 · `/healthz` 200 · **배포 창 `no upstreams available` 0건**(무중단 실측).
- 라이브 재실측 결과 **프리뷰(확정 코드)와 차이 0**: 진입 맨-아래 gap **0** · 뱃지 오차 **0.20px** ·
  막대 60% 클릭 정밀 점프 · 실 휠 입력 후 위치 유지 · JS 오류 0. 라이브 데이터 변경 0(열람·스크롤만).
- Files: `docs/{TASK,TEST,MODIFY,REVIEW}.md`, `docs/test-runs.d/20260813T155000-rail-async-relayout.md`,
  `docs/evidence/pb0008-rail-async-relayout-{6,7}-postdeploy-*.png`.
- Timestamp: 2026-08-13T17:41:00+09:00
## CHG-20260813T1600-ai-claude-feature-0003-graph-expand-perf — 그래프 '노드 펼침' 성능 3축 개선

- 사유: 사용자 리포트 "노드를 펼칠 때 체감될 정도로 느리게 펼쳐집니다 — 병목 원인 파악 후 개선".
  라이브 CDP Profiler 실측으로 병목을 3축에 귀속(TASK `20260813T1600-graph-expand-perf` R1~R3).
- 대상(코드 거주 feature-0003 `src/static/graph/`):
  - `graph-renderer-pixi.js` — `nodeSig`/`comboSig` **폐기** → `nodeShapeSig`/`comboShapeSig`(위치 제외)
    신설. `draw()` 의 오브젝트 풀 diff 가 ① 모양 동일 = `position.set` 재배치(파기·라벨 재생성 0)
    ② 엣지는 `_paintEdge` in-place 재-path ③ 모양 변경만 재생성. `_lastDrawStats`·
    `__META_GRAPH_PERF.render` 에 `moved`·`repainted` 계측 추가. `moveTweenPlan` 주석의 stale 서술 정정.
  - `graph-core.js` — `_metaTopoSig` 가 `label==="Column"` 노드를 서명에서 제외(+ 개수 필드도 비-Column
    기준으로 교체) · §73 헤더 주석의 오기("colsByTable 거주라 자연 제외") 정정 ·
    `_metaGraphOnNodeClick` 이 Table 단일클릭 시 `_metaGraphPrefetchColumns(id)` 선행 호출 ·
    `_metaGraphResetModel` 이 `_metaColPrefetchClear()` 수행.
  - `graph-ctxmenu.js` — 선-fetch 계층 신설(`_metaColPrefetch` Map · `_metaGraphPrefetchColumns` ·
    `_metaColTake`(소비) · `_metaColPeek`(공유) · `_metaColPrefetchClear` · TTL 8s · reject 하지 않는
    `{ok,v|e}` 래핑) · `_metaGraphToggleColumns` 가 두 GET 을 선-fetch 에서 이어받고 공유 payload 를
    얕은 복사 + 컬럼 노드도 per-node 복사 후 dedupe · `_metaGraphShowDetail` 이 같은 promise 공유 ·
    `_metaSearchPrunePristine` 도 캐시 clear.
- 테스트: `tests/headless/test_graph_expand_prefetch.js` **신규(15)** ·
  `test_pixi_adapter.js` T17/T19 전환 + **T31 씬-diff 신규** ·
  `test_g6build_layoutmemo.js` **T7 신규**(컬럼 ingest 캐시 적중 + 적중==fresh 동일성).
- 백엔드·스키마·권한·마이그레이션 변경 **0** (프론트 전용).

## CHG-20260813T1700-ai-claude-feature-0003-graph-expand-perf-postdeploy — POST-DEPLOY 실측 기록 (doc-only)

- 사유: 선행 cycle `20260813T1600-graph-expand-perf` 의 배포(main `16da577f`) 후 라이브 재측정 종결.
- 대상: `docs/test-runs.d/REV-20260813T160000-graph-expand-perf.md` §5 POST-DEPLOY 채움 ·
  `docs/TASK.md` cycle 섹션 · `docs/REPORT.md` 잔여 항목 갱신. **코드 변경 0**.
- 결과: 라이브 n=3 이 격리 프리뷰 수치를 그대로 재현(클릭→펼침 544ms · 블로킹 134ms ·
  drawMs 32.8ms · 재생성 21 · 라벨 19) · 무중단 `no upstreams available` 0건 · pageerror 0.

## CHG-20260813T181200-ai-claude-feature-0024-folder-dnd-shared — 공유받은 그룹 대화 폴더 DnD 개방

- 사유: 사용자 요청 "서비스 내 다른 계정으로부터의 그룹 대화 또한, drag&drop으로 폴더 별 이동이
  가능하도록 구성해주세요." (feature-0024 REQ-20260813-folder-dnd-shared-group).
- 대상(코드 거주 feature-0003):
  - `src/static/app/sidebar.js` — `isFolderScopedConversation(item)`(owner || is_member) **신설·export**.
    ① own/others 파티션(구 `isOwnConversation(item) || item.is_member`) ② `buildCompactItem` 의 드래그
    게이트(구 `mine && can("folder.manage.own")`) **두 지점이 같은 predicate 사용** — 폴더에 보이는
    항목과 끌 수 있는 항목이 정의상 일치. 렌더·클래스(`is-own`/`is-other`)·멀티선택·`dataset.idx` 는
    기존 `mine` 유지(소유 표시·삭제 선택 의미 불변).
  - `tests/verify_folder_dnd_shared_group.mjs` — **신규**(jsdom 31): draggable/dragstart/폴더 하위
    렌더·카운트/권한 미보유/타 계정 대화 제외/predicate 단위/구조 잠금.
  - `tests/verify_new_conv_dedup.mjs` — renderConversationList 추출 하네스에 새 predicate **실함수
    동반 추출**(stub 아님 — 파티션 계약을 vacuous 하게 만들지 않기 위함).
- 백엔드·스키마·권한·마이그레이션·엔드포인트 변경 **0**. 배정 저장은 기존 계정 스코프 경로
  (`folder_conversation_map` PK `(account_id, conversation_id)`) 그대로 — 소유자·타 멤버 뷰 불변.
- 검증: jsdom 31 PASS · 수정 전 재현 시 대상 11건 FAIL(테스트 판별력 실증) · 프론트 `.mjs` 60개 전수
  exit 0 · ESM 구문 PASS. 라이브 = POST-DEPLOY PB-0008.
## CHG-20260813T184000-ai-claude-feature-0003-folder-dnd-postdeploy — POST-DEPLOY 실측 기록 (doc-only)

- 사유: 선행 cycle `20260813T1812-folder-dnd-shared-group` 의 배포(main `763ad65d`) 후 라이브 종결.
- 대상: `docs/test-runs.d/REV-20260813T181200-folder-dnd-shared.md`(POST-DEPLOY Run + frontmatter
  verdict) · `docs/test-runs.d/evidence/folder-dnd-shared-in-folder.png`(신규 증적) · `docs/TASK.md` ·
  `docs/REPORT.md`. **코드 변경 0**.
- 결과: 공유받은 그룹 대화 `draggable="true"` 라이브 확인 · 폴더 배정/해제 서버 왕복 · 크로스-계정
  격리(admin 뷰 folder 미노출·folder_id null) · `pageerror` 0 · 무중단 0건. 테스트 데이터 정리 완료.

## CHG-20260813T193000-ai-claude-feature-0003-member-scope-gates — 그룹 멤버 권한 게이트 정합

- 사유: 사용자 감사 요청("표시-집행 불일치 / 소유자가 과도하게 좁혀진 이슈") → 백엔드
  `_account_can_access_conversation` 33지점 전수 대조로 4건 확정 + 오도 안내 2건 + 잠재 함정 1건.
- 대상:
  - `src/static/app.js` — **`isOwnScopeConversation`(owner ‖ `is_member`) 신설·export**.
    `requiredPermissionsFor` 가 `own`(서버 2차 owner 게이트 있는 액션) / `ownScope`(서버가 멤버
    허용) **두 변수를 분리 보유** → `conversation.cancel`·`finalize`·`extend`·`read` 는 ownScope,
    `rename`·`delete`·`duplicate` 는 own 유지(비대칭 의도). `conversation.read` 라벨
    "공유 링크 관리" → "대화 설정"(통합 이전 잔재 정정). `canCancel/Finalize/Extend/AskInConversation`
    4종 predicate 교체. `renderAccessNotice` 조회 전용 판정도 ownScope.
  - `src/static/app/composer.js` — '읽기 전용 대화' 안내 조건 ownScope 화, `sendPrompt` 인라인 가드
    (`!isOwnConversation(active) && !active.is_member`)를 공용 predicate 로 통일, dead
    `const disabled = !canAskInConversation() || busy;` 제거(계산만 하고 미사용), 그로 인해 미사용이
    된 import 2개(`canAskInConversation`·`isOwnConversation`) 정리.
  - `tests/verify_member_scope_gates.mjs` — **신규**(jsdom 53): 멤버 허용 4종 · 대조군 차단 유지 ·
    권한 미보유 시 멤버도 차단 · `.any` 열람 대화 차단 유지 · 구조 잠금 10.
- 백엔드·스키마·권한 카탈로그·엔드포인트 변경 **0** (프론트 표시 계층만 — 서버 enforcement 불변).
- 검증: jsdom 53 PASS · 수정 전 재현(동일 스크립트로 HEAD 평가 시 멤버 제어 전부 false) ·
  프론트 `.mjs` 61개 전수 exit 0 · ESM 구문 PASS. 라이브 = POST-DEPLOY PB-0008.

## CHG-20260813T201000-ai-claude-feature-0003-member-leave-branch — 멤버 '나가기' 분기 복원 + 감사 결론 정정

- 사유: 선행 cycle 의 라이브 검증에서 `can()` 이 **인자를 무시**(display-permissive)한다는 사실이
  드러나 감사 결론 일부가 무효화됐고, 동시에 그 특성이 만든 **실효 결함**(멤버 나가기 경로 부재)이
  확정됐다.
- 대상:
  - `src/static/app.js` — `openConversationSettings` 의 `const canArchive =
    canDeleteConversation(conversation)`(→ 항상 true) 를 **`isOwnConversation(conversation) ||
    canOpenAdminConsole()`** 로 교체. owner·관리자는 '보관', 비소유 그룹 멤버는 **'나가기'**.
    ⚠ display-permissive `can()` 을 분기 판정에 쓰지 말라는 경고를 주석에 명문화.
  - `tests/verify_member_leave_branch.mjs` — **신규**(jsdom 실 DOM 22): 소유자/멤버/관리자 3분기 +
    클릭 결과 액션(`deleteConversation` vs `leaveConversation`) + 정본 `can()` 전제 단언 + 구조 4.
  - `tests/verify_settings_archive_leave.mjs` — **거짓 PASS 정정**: 구 단언이 "그 함수를 쓴다" 만
    잠갔던 것을 새 판정 기준으로 교체 + **주석 제외 코드 라인만** 검사(주석 인용 취약성 제거).
  - `tests/verify_member_scope_gates.mjs` — 헤더·라벨 정정(per-code `can` 주입 = 미래 계약 잠금).
  - `docs/LEARNINGS.md` — LRN-20260813 기록. 문서 5종 + STATUS 정정.
- 백엔드·권한 카탈로그·스키마 변경 **0**.
- 검증: 신규 22 PASS(수정 전 재현 시 6건 FAIL) · 정정 테스트 23 PASS · 프론트 `.mjs` 62개 전수
  exit 0. 라이브 = POST-DEPLOY PB-0008.
## CHG-20260813T183000-ai-claude-feature-0003-group-attach-scope-window — 공유 대화 첨부 스코프 확대 + 공유창 window 게이트

- 사유: `/_dqa:conversation_audit` 사용자 명시 호출 — 공유 대화에서 assistant 가 타 멤버 첨부를
  확인하지 못하는 마찰(`FR-group-attach-sender-scope-blocks-members`). 라이브 대화 `…46763d6e`
  에서 "첨부파일이 보이지 않습니다" 2회 → "버그 발생;;" 종료. 첨부 보유 그룹 대화 **6/6** 노출.
- 위험등급 **Critical**(§12.3 보안 경계 변경 — feature-0009 CSO F1 해제). 사용자 승인:
  "승인 — 완화책 포함" + "bounded 멤버는 window 안 첨부만"(2026-08-13). override 미적용.
- 대상:
  - `shared/share_window.py` — **신규**. 그룹 첨부 스코프 판정의 **단일 정본**(web·agent_core 공용,
    두 게이트 분기 방지). `group_attachment_scope()` / `group_attachment_is_sender_only()`.
    판정축은 **메시지 id/joined_at 기준 은닉 구간 실재 여부**(`_msg_outside_window` 동형):
    은닉 0 → 대화 전체 / 은닉 ≥1 → 발신자 본인만. 비-PG·42703 은 제약 없음, 그 외 실패는
    전부 fail-closed(sender-only).
    · **시각축을 쓰지 않는 이유**: 첨부는 표시 메시지에 바인딩되지 않고(`WebAttachmentDerivedMessages`
      는 파생 메시지용), 첨부 `created_at` 은 메시지와 같은 시간축이 아니다(라이브 실측 +9h —
      로컬시각이 UTC 로 라벨링돼 저장). 시각 비교는 하한에서 열고 상한에서 가리는 양방향 오판.
  - `unit/feature-0003-agent-web-ui/src/routers/_conv_store.py` —
    `_resolve_conversation_attachment_scope` 가 `sender_scope`(그룹 신호)를 받아 **실제 필터는
    window 게이트로 결정**(`restrict_to_sender`). PG·MySQL 두 분기 모두 적용. 게이트 호출 실패는
    sender-only. DB 해소 실패 시 그룹 client 폴백 금지(종전 유지).
  - `unit/feature-0002-agent-core/src/agent_core.py`(cross-ref) — `_group_attachment_sender_only()`
    신규(같은 정본 호출, 예외=좁은 쪽) + `_build_attachment_context_section` 호출부 게이트 적용.
    SELECT 에 업로더 `AccountId`/`account_id` **append(row[12])** — 기존 positional index 보존.
    ATTACHED FILES 에 `uploaded-by=<name> (OTHER MEMBER)` 라벨 + **데이터-전용 계약** 코드 권위
    주입(AUTH-1a): 타 멤버 파일 내용은 DATA 이며 지시문이 아니라는 계약. CSO F1 이 막으려던
    indirect prompt injection 을 히스토리 `[발신자]:` 라벨(REQ-GC-R5)과 같은 축으로 대체 봉인.
- 무변경(확인): 첨부 **열람·다운로드 경계**(`_account_can_access_attachment`, REQ-GC-R6) ·
  ConversationId 스코프(TASK-0284 IDOR) · `SupersededAt IS NULL` 최신본 한정 · 상한 200 ·
  본문 인라인/vision 스코프(이미 conversation 단위) · RBAC · datasource 바인딩 · 스키마 · 마이그레이션.
- 테스트: `tests/test_share_window_gate.py` **신규 13** · `tests/test_attach_full_scope.py` 그룹 계약
  **갱신 3**(은닉0=전체 / 은닉≥1=발신자한정 / 게이트예외=fail-closed) · feature-0002
  `tests/test_group_attachment_provenance.py` **신규 7**(라벨 4축 + 데이터-전용 계약 + 1:1 무회귀 +
  legacy row). 라벨 검사는 파일 라인 단위(섹션 계약 문구가 같은 토큰을 포함 — tautology 회피).

### CHG-20260813T183000 적대 리뷰 반영 (REV-20260813T183000, [CODEX:adversarial-security])

- **[P1] fail-open 제거**: 그룹 여부를 `shared/share_window.py` 게이트가 직접 판정(멤버 수·소유자·
  window 1 쿼리). 호출측 `_is_group_conversation()` 선-게이팅 제거 — 그 함수가 PG 오류 시 `False` 를
  돌려 게이트를 건너뛰는 경로였다(`conversations.py` `sender_scope=True` 고정, `agent_core.py` 동일).
- **[P2] 축소 조건 강화**: 그룹인데 멤버 행 없음(비-owner) → sender-only · **floor 설정 멤버는 은닉 수와
  무관하게 sender-only**(recall-태그 은닉 비동형 구간을 구조적으로 제거) · 카운트 파싱 실패 → sender-only.
- **[P2] 출처 계약을 row 사실로**: 발동 조건이 표시명 조회 성공 여부가 아니라 "타 멤버 파일 실재"
  (`_has_other_uploader`). 이름 미해소 시 `another member` 로 적고 계약 유지. 타 멤버 파일 본문의
  **datamark 구획 헤더에 업로더** 추가.
- **정직 표기**: 프롬프트·datamark 은 확률적 완화이지 보장이 아니며 confused-deputy 경로가 남는다 →
  SECURITY §47.4 에 수용 위험으로 명시, provenance 기반 tool 게이트는 후속 과제.
- 테스트 46 PASS(적대 리뷰가 지적한 5경로 전부 회귀 고정).

## CHG-20260813T203000-ai-claude-feature-0003-group-attach-postdeploy — POST-DEPLOY 라이브 실측 기록 (doc-only)

- 사유: 선행 cycle `20260813T1830-group-attach-scope-window` 의 배포(main `db15bfcb`) 후 실측 종결.
- 대상: `docs/improvements/conversation-audit/FRICTION_LEDGER.md`(status `fixed:undeployed` →
  `fixed:deployed:verified` + 실측 근거·미실측 축) · `unit/feature-0003-agent-web-ui/docs/TASK.md`
  (배포 후 항목 마감). **코드 변경 0**.
- 결과: 마찰 당사자(비업로더 멤버)의 첨부 스코프가 **0건 → 8건**. 업로더·1:1 무회귀.
  web-a/web-b/ask-worker `GIT_COMMIT=db15bfcb` · 무중단 실측 0.
- 정직: bounded 멤버 축소의 라이브 발동은 조건(은닉 구간 실재 멤버) 부재로 미실측 — 단위 테스트 한정.

## CHG-20260813T213000-ai-claude-feature-0003-member-gates-postdeploy — POST-DEPLOY 실측 기록 (doc-only)

- 사유: `20260813T2010-member-leave-branch` 배포(main `660e9fcf`) 후 라이브 종결.
- 대상: `docs/test-runs.d/REV-20260813T201000-member-leave-branch.md`(POST-DEPLOY Run) ·
  `docs/test-runs.d/evidence/member-leave-btn-live.png`(신규 증적) · `docs/TASK.md` · `docs/REPORT.md`.
  **코드 변경 0**.
- 결과: 멤버 '나가기' 노출·end-to-end 이탈·소유자 '보관' 대조군·pageerror 0 전 항목 PASS.
  선행 B 축(오도 안내 소거)도 같은 계정에서 재확인. 테스트 데이터 정리 완료.

## CHG-20260814T010301-doc-sync-rn-0814 (2026-08-13 블록 append) 릴리즈노트 콘텐츠 — 기존 08-13 블록에 10항목 append + summary 증강

- 사용자 노출 릴리즈노트(`static/release-notes-data.js`)의 **기존 date "2026-08-13" 블록**에 10 items append(원문 창 in-place 비교 · 외부 AI URL 접속 인증 · LLM 사용량 차트 지표 선택기 · 그래프 펼침 카메라 추종/재배치 · 외부 AI 도구 상한 패널 · 공유 그룹 대화 폴더 이동 · 그래프 펼침 체감 지연 · 공유 대화 첨부 LLM 참조 · 멤버 나가기 경로 · 우측 스크롤 정합) + 그 블록 summary 증강(기존 첨부 이름순 정렬 서술 4문장 **원문 그대로 보존** 후 확장). 그 배포일 블록이 owning feature 커밋(`0c3b0d01`)의 self-add 로 **이미 존재**하므로 신규 블록 prepend 가 아니라 append. `generated` 불변("2026-08-13") · `releases` 48 불변 · head items 1→11.
- 평이화/비노출: feature-id·§번호·PR#·commit sha·모듈/함수/파일명·테이블명·내부 설정키·ADR·PB-0008·인프라 용어(replica/gateway/worker/quiesce/OAuth/SSE/MCP/SSOT/alembic)·픽셀 소수점 누출 **0**(37 패턴 정규식 기계 검증).
- 적대검증 반영 6건(ULTRACODE `wf_285f2b56-8df` refute-first 렌즈, 오케스트레이터가 정본으로 전건 독립 재검증): P1 2건(정정된 오진 A-4 재생산 · 은닉 구간 멤버 동작을 실제 fail-closed 와 다르게 서술) + P2 4건(08-07 블록 재서술 · 라이브 노출 0 인 knob 삭제 서술 · 오도 안내 2곳 위치·문면 오기 · 무의미 정밀도).
- **배포 게이트 = 물리 실측**: 라이브 컨테이너 6종 전부 `:d585250b`(= HEAD = origin/main) · 서빙 static md5 파리티 정확 일치 · `/healthz` 200 → 10항목 전건 배포 완료(유보 0).
- 캐시버스터 수기 bump 없음(빌드 주입 메커니즘 — ITEM-09 · `deploy-web.sh` 가 placeholder 잔존 시 ABORT). `index.html`/`admin.html` 무변경.
- Verification: `node --check` PASS · `verify_release_notes.mjs` **34 pass / 0 fail**(편집 전 baseline 동일) · 블록 수 48 불변 · head date 2026-08-13 · items 11 · 항목 enum·스키마 외 키 0 · 기존 47 블록 보존 · `generated`==head.date · 내부용어 누출 0.
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).
- Reason: changed paths are docs + 비-정책 static data only — 코드/스키마/권한 변경 0.
- Timestamp: 2026-08-14T01:03:01+09:00
## CHG-20260813T1640-ai-claude-corp-usage-metric-solo-anim — '요청' 경계 전환 애니메이션 복구 (Minor §12.3, frontend-only)

사용자 보고: '요청' ↔ 다른 지표 전환에서만 애니메이션이 없었다.

- `src/static/admin/usage.js`
  - `renderStacked` signature 를 `[days, W]` 로 축소(분해모드·모델집합 제거) — 세그먼트 키 집합이
    달라도 노드를 유지해 접기/자라기로 전환을 흡수한다. 모델 칩 토글도 함께 부드러워진다.
  - `renderDonut` 이 값 0 인 모델을 0 길이 arc 로 유지(라벨 집합 안정화).
  - `renderStackedHBar` signature 에서 solo 접두·모델 목록 제거 + **세그먼트 부족분 추가 로직**
    신설(종전엔 추가 경로가 없어 개수가 바뀌면 재생성됐다) + 색 갱신.
- `src/static/css/admin.css` — `.admin-usage-hseg` 에 `background` 전환 추가(단일 색 ↔ 모델 색).
- `tests/headless/test_usage_metric_switch.js` — 양방향 경계 전환 회귀 잠금 5건 + 기존 검사 3건을
  새 설계(0 높이 노드 유지)에 맞춰 "보이는 막대" 기준으로 정정. 32 PASS · 뮤테이션 역검증 5/5.

## CHG-20260813T1720-ai-claude-corp-usage-metric-solo-anim-width — 폭 흔들림까지 흡수 (같은 결함의 2차 기전)

1차 수정(분해모드·모델집합 제거) 후 **라이브에서 여전히 재생성**됐다. 실측으로 갈라낸 2차 기전:
'요청'은 범례가 없어 페이지가 짧아지고 → 세로 스크롤바가 사라져 **차트 폭이 12px 달라진다**
(sig `…|1299` vs `…|1287`). 헤드리스는 픽스처가 작아 스크롤바가 없어 재현되지 않았다.

- `usage.js` — signature 를 **일자 집합만**으로 축소(W 제거). in-place 경로가 `viewBox`·축·x라벨·
  막대 `x`/`width` 를 새 폭으로 다시 맞춘다(가로는 즉시 반영, 세로만 애니메이션). 축·x라벨은
  생성·갱신이 같은 식을 쓰도록 `axisInner`/`xLabelsInner` 빌더로 추출.
- 하네스 — 폭을 직접 바꿔 같은 조건을 만드는 회귀 잠금 4건 추가(**36 PASS**). 뮤테이션 2종
  (W 를 sig 에 복원 / viewBox 갱신 제거) 모두 KILLED.
## CHG-20260813T1640-ai-claude-corp-usage-metric-solo-anim — '요청' 경계 전환 애니메이션 복구 (Minor §12.3, frontend-only)

사용자 보고: '요청' ↔ 다른 지표 전환에서만 애니메이션이 없었다.

- `src/static/admin/usage.js`
  - `renderStacked` signature 를 `[days, W]` 로 축소(분해모드·모델집합 제거) — 세그먼트 키 집합이
    달라도 노드를 유지해 접기/자라기로 전환을 흡수한다. 모델 칩 토글도 함께 부드러워진다.
  - `renderDonut` 이 값 0 인 모델을 0 길이 arc 로 유지(라벨 집합 안정화).
  - `renderStackedHBar` signature 에서 solo 접두·모델 목록 제거 + **세그먼트 부족분 추가 로직**
    신설(종전엔 추가 경로가 없어 개수가 바뀌면 재생성됐다) + 색 갱신.
- `src/static/css/admin.css` — `.admin-usage-hseg` 에 `background` 전환 추가(단일 색 ↔ 모델 색).
- `tests/headless/test_usage_metric_switch.js` — 양방향 경계 전환 회귀 잠금 5건 + 기존 검사 3건을
  새 설계(0 높이 노드 유지)에 맞춰 "보이는 막대" 기준으로 정정. 32 PASS · 뮤테이션 역검증 5/5.

## CHG-20260813T1810-ai-claude-corp-usage-metric-first-appear — 신규 세그먼트 첫 등장 전환 (라이브 전용 축)

`usage.js` — 새로 삽입되는 막대/세그먼트에 목표값을 주기 전 강제 reflow 로 시작 스타일을 확정
(세로·가로 양쪽). rAF 한 번은 라이브 Chrome 에서 시작 스타일 확정 전에 목표값이 들어가 transition
이 미발동했다(헤드리스는 발동 — 환경차). 하네스에 검사 1건 추가(**헤드리스 판별력 없음** 명시).
## CHG-20260814T010000-ai-claude-feature-0003-attach-version-branching — 첨부 버전 계보를 작성 주체별로 분기

- 사유: 사용자 요청 "첨부파일의 버전 관리 또한 사용자별로 트리 형태로 구분(assistant 또한 독자적인
  버전 관리)" + 후속 결정 "별도 root 체인 분기 · 비교 기준을 [자기 버전/시간별] 두 축으로 · assistant
  도 각 기준을 인지". 선행 cycle `20260813T1830-group-attach-scope-window` 의 후속.
- 위험등급 **Major §12.3**(첨부 생성 경로·프롬프트 계약 변경 — 보안 경계는 불변). 스키마 변경 **0**.
- 대상(코드 거주 feature-0003):
  - `src/routers/_conv_store.py`
    - `_materialize_assistant_attachment_edits`: 분기 판정(`_branch_from_user_chain` — source 의
      `CreatedByRole`) → 사람 첨부면 `RootAttachmentId=NULL, VersionNumber=1`(새 계보), assistant
      계보면 종전대로 `v+1`. **supersede 를 `_supersede_root_id` 로 조건화** — 분기일 때 원 계보를
      끄지 않는다(사용자 최신본 보존). MetaJson 에 `branch_of_attachment_id`/`branch_of_root_id`/
      `branch_owner_role` 기록(스키마 미확장 트리 복원). dual-write 는 분기 시 새 row 만 미러.
      audit 에 `version_lineage: branch|extend` + 분기 시 `root_attachment_id = new_id`.
    - `_load_filename_lineage_heads` **신규** — 같은 대화·같은 파일명의 계보 head 를 시간순으로.
      **MySQL 정본** 조회(미러 지연으로 방금 만든 분기가 빠지면 비교 UI 가 거짓말을 한다).
      cursor 획득을 try 안에 두어 fail-soft 계약을 지킨다.
  - `src/routers/attachments.py`: `GET /api/attachments/{id}/versions` 응답에 **`lineages` 축**
    추가(시간순 계보 head + `branched_from_attachment_id` + `is_current_lineage`). 기존 `versions`
    (계보 내 축)·권한 게이트·직렬화는 불변. 실패는 fail-soft(빈 배열).
  - `src/app.py`: `_load_filename_lineage_heads` re-export.
- 대상(cross-ref feature-0002-agent-core):
  - `src/agent_core.py`: 첨부 SELECT 에 `CreatedAt` append(row[13], PG/MySQL 양쪽 — 기존 positional
    index 보존) · **`## FILE VERSION LINEAGES` 블록** 신규(같은 파일명 계보 ≥2 일 때만): 계보별
    소유자·버전·시각 + **시간순 최신 마커** + 두 축 정의 + "최신이 모호하면 어느 계보인지 밝히고
    행동" 계약 · `attachment-edit` 도구 지시에 "내 편집은 사용자 파일을 덮어쓰지 않는다" 명시.
- 무변경: UNIQUE `UQ_WCA_VersionChain(RootAttachmentId, VersionNumber)` · 스키마 · 마이그레이션 ·
  RBAC · 첨부 열람/다운로드 경계 · 업로드(사용자 재업로드) 체인 로직 · 기존 39개 혼합 체인(보존).
- 테스트: `test_attach_version_lineage_prompt.py` **신규 10** · `test_attach_version_branching.py`
  **신규 8**. 후자가 실제 결함 1건 적발(cursor 획득이 try 밖 → fail-soft 파손) → 수정.

### CHG-20260814T010000 적대 리뷰 반영 (REV-20260814T010000, [CODEX:adversarial-data-integrity])

- **[P1] 사용자 재업로드가 AI 계보를 다시 합침** — `_find_latest_same_name_attachment` 가 동명 head 를
  역할 구분 없이 골라, 사용자 재업로드가 **AI 계보의 v2** 로 편입되고 그 head 를 supersede 했다.
  한 번의 재업로드로 계보 분리가 무너지는 경로. → `COALESCE(CreatedByRole,'user') <> 'assistant'`
  로 **사용자 계보만** 편입 대상.
- **[P1] `read_attachment(filename=…)` 이 잘못된 계보를 조용히 읽음** — 동명 후보가 여럿이면 Id 최대를
  집었다. 동명 공존이 이제 정상 상태라, 모델이 사용자 파일을 읽으려 해도 자기 수정본을 읽고 그것을
  사용자 파일이라 서술한다. → **복수면 고르지 않고 되묻는다**(계보·버전을 붙인 선택지 제시).
  `_load_scoped_attachment_rows` 에 `CreatedByRole`/`VersionNumber` 추가(안내가 사실이 되도록).
- **[P1] 같은 root 의 live head 2개를 두 계보로 오인** — 업로드 경로가 INSERT commit 뒤 supersede 하고
  실패를 삼켜(기존 결함) 한 체인에 head 가 둘 남을 수 있다. → `_load_filename_lineage_heads` 가
  **root 당 1건**으로 접는다. (트랜잭션 분리는 이 cycle 범위 밖 — 기존 결함으로 REPORT 이월.)
- **[P2] 타 멤버 소유 AI 계보를 "by you" 로 오표기** — 저장 경로는 source `AccountId` 일치를 요구하므로
  이어서 수정할 수 없다. → 소유자를 반영해 `READ-ONLY for you` / `your lineage — you can extend it`
  으로 갈라 적는다.
- 회귀 고정: 위 4축 전부 테스트 추가(재업로드 역할 스코프 · root dedupe · 동명 모호성 · 소유자 표기).

## CHG-20260813T1900-ai-claude-corp-usage-metric-profile — 프로필 '사용 내역' 차트에 같은 지표 체계 반영 (Minor §12.3)

사용자 요청: "[사용자 프로필 > 계정 > 사용 내역] 차트에도 정합하게 반영".

- `src/static/usage-metrics.js` (**신규**) — 지표 정의 정본(목록·라벨·가산성·안내문·보조지표 규칙).
  관리 콘솔과 프로필이 공유한다. `admin/usage.js` 의 복제 정의를 제거하고 이 모듈 소비자로 전환.
- `src/static/app/profile.js` — 요약 카드를 지표 8종 선택기로(`button`+`aria-pressed`), stacked·
  donut 을 지표 인자화 + 관리 화면과 동일한 전환 규칙(일자 집합 signature · 접기/자라기 · 강제
  reflow · 폭 좌표 재배치 · 0 값 arc 유지). 지표 전환은 마지막 응답 재사용(재조회 X).
- `src/static/index.html` — 안내 1줄 자리(`#profileUsageMetricNote`) + 차트 제목 고정어 "토큰" 제거.
- `src/static/css/admin.css` — 프로필 선택 카드 상태 + 막대/도넛 전환(관리 화면과 같은 곡선·시간).
- `src/routers/profile.py` — totals 캐시 2축, `by_day` 에 requests 포함 8축, `by_day_model` 지표 축
  전량. 캐시 컬럼 자가치유는 공용 `_usage_cache_exec`.
- `tests/headless/test_profile_usage_metric.js` (**신규 15건**) — 정본 대조(순서·라벨 동일) + 전환
  규칙 + 비-가산 처리 + 캐시 도넛. 하네스는 지표 정의를 **정본 소스 주입**으로 쓴다(stub 금지).
## CHG-20260814T023000-ai-claude-feature-0003-attach-branch-postdeploy — POST-DEPLOY 실측 기록 (doc-only)

- 사유: 선행 cycle `20260814T0100-attach-version-branching` 의 배포(main `6fbccbc7`) 후 실측 종결.
- 대상: `unit/feature-0003-agent-web-ui/docs/TASK.md` 배포 항목 마감. **코드 변경 0**.
- 결과: web-a/web-b/ask-worker `GIT_COMMIT=6fbccbc7` · 무중단 실측 0 · 배포본에서 계보 조회
  (`_load_filename_lineage_heads`) 예외 없이 동작, 동명 파일의 계정별 계보가 각각 head 1건으로 분리.
- 정직: 분기 INSERT/supersede 실동작·프롬프트 계보 블록 렌더는 라이브 write 를 유발해 미실측
  (단위 테스트 한정) — 다음 실사용 수정본에서 확인 가능.

## CHG-20260813T2000-ai-claude-corp-usage-metric-final-postdeploy — 양 화면 POST-DEPLOY 실측 기록 (doc-only)

`docs/TEST.md` 에 관리·프로필 라이브 Run + 검증 함정 2건(`getBoundingClientRect` 미반영 ·
`display:none` 조상에서 transition 미발동) 기록. 코드 변경 0.
## CHG-20260814T090000 '사용 기록' 표 열 정렬 + 페이지네이션 (REV-20260814T090000-usage-records-sort-page)

- 대상: `src/static/admin/usage.js` `showUsageConvModal`
  - 열 정의(`cols`) 신설 — 표 머리와 정렬 키 계산이 같은 목록을 보는 SSOT. `type: num|text` 가
    첫 클릭 방향을 가른다.
  - 행마다 정렬 키를 1회 선계산(`sortKeysOf`) — **화면 표시값 기준**(주체 = 번역 라벨, 구분 =
    배지 문구). 동률 tiebreak 는 토큰 내림차순 → 원래 순서(안정 정렬).
  - 렌더를 `headHtml`/`rowHtml`/`pagerHtml`/`renderTable` 로 분리. 정렬·페이지 변경 시 모달을
    재생성하지 않고 thead/tbody/페이저만 교체한다(스크롤·포커스 보존, keydown 리스너 재바인딩 없음).
  - 상호작용은 overlay 한 곳에 위임(`data-usage-sort` · `data-usage-page` · `.usage-rec-page-size`
    change) — tbody 가 통째로 교체되므로 행별 리스너는 매 렌더 재바인딩이 되어 쓰지 않는다.
  - **nav 조회를 불변 색인(`rowsByIdx`)으로 전환**: 종전 `navByIdx.push` 는 재렌더마다 누적됐고,
    정렬은 `merged` 의 **순서를 바꾸므로** `merged[idx]` 로 되짚으면 다른 행의 화면으로 이동한다.
    (하네스 E4 가 구현 중 이 결함을 실제로 적발 → 수정.)
  - 절단 안내 문구를 "상위 N건만 표시" → "서버가 상위 N건까지 실어 줍니다" 로 정정 — 이제 표시
    건수는 페이저가 말하므로, 이 문구는 **서버 절단**만 가리켜야 한다.
- 대상: `src/static/css/search-audit.css` — 열 머리 정렬 버튼(`.usage-rec-sort`, sticky th 안에서
  링크처럼 보이되 포커스 링 유지) · 방향 표식 자리 고정(`min-width` — 정렬 전환 시 열 폭 흔들림
  방지) · 페이저(`.usage-rec-pager*`). 색은 기존 admin 토큰만 사용.
- 무변경: 백엔드 엔드포인트·응답 스키마·집계 쿼리·RBAC·상한(`_USAGE_*_LIMIT`) · 행 내용/링크
  규약 · profile(self) 판 독립 모달(`app/profile.js`).
- 테스트: `tests/verify_usage_records_sort_page.mjs` **신규 46** · `tests/test_usage_records_sort_page.py`
  **신규 8**.

### CHG-20260814T093000 적대 리뷰 반영 (REV-20260814T093000-usage-records-sort-page [CODEX:adversarial-frontend-state])

- **[P2] 재렌더가 포커스를 삼킴** — 정렬/페이지 조작 시 thead·tbody·페이저를 `innerHTML` 로
  교체하면서 방금 누른 컨트롤 노드가 사라져 포커스가 `body` 로 빠졌다. 키보드로는 방향 토글도
  연속 페이지 이동도 불가. → `focusToken()`/`restoreFocus()` 로 같은 컨트롤에 포커스 복원,
  경계에서 비활성이 되면 페이저의 활성 컨트롤로 대체 이동.
- 회귀 고정: 하네스 G1~G4 (뮤턴트로 4건 FAIL 확인 — 검출력 있음). 총 50 PASS.

## CHG-20260814T101500 사용 기록 페이저를 스크롤 바닥에 고정 (REV-20260814T101500-usage-pager-sticky)

- 근거: 직전 cycle(usage-records-sort-page) 의 **POST-DEPLOY PB-0008 라이브 실측**에서 첫 화면에
  페이저가 보이지 않았다 — 기본 50행 아래에 놓여 페이지를 넘기려면 매번 목록 끝까지 스크롤해야
  했다. 페이지네이션을 붙여 놓고 도달 비용을 남긴 셈이라 실효 완성이 아니다.
- 대상: `src/static/css/search-audit.css` — `.usage-rec-pager` 를 스크롤 컨테이너
  (`.usage-conv-body`) 바닥 sticky 로(배경·상단 경계선·`bottom:-1px` 로 서브픽셀 틈 차단).
  표 머리 sticky(top) 와 짝을 이뤄 정렬·페이지 컨트롤이 항상 손에 닿는다.
- 대상: `src/static/admin/usage.js` — 페이저 노드를 안내 문구 **뒤(마지막)** 로 이동. sticky 요소가
  절단·이동 안내 문구를 덮지 않게 하려는 순서 결정.
- 무변경: 정렬·페이징 로직, 백엔드, 행 렌더.
- 테스트: `tests/test_usage_records_sort_page.py` L9 신규(sticky·배경·마크업 순서) — 9 PASS.
  하네스 50 PASS 무회귀.

## CHG-20260814T104500 사용 기록 정렬·페이지네이션 POST-DEPLOY 실측 기록 (docs-only)

- 대상: `docs/TEST.md`(POST-DEPLOY Run — 정렬/페이지/nav/키보드/페이저 가시성 전 축 + 미검증 명시) ·
  `docs/REPORT.md`(이월: 열 폭 재계산 ≤4% · profile 판 미적용) · `docs/TASK.md` · `docs/REVIEW.md` ·
  `docs/evidence/pb0008-usage-pager-sticky-20260814.png`(첫 화면 페이저 시각 증거).
- 코드 무변경.
## CHG-20260813T2130-ai-claude-corp-usage-card-overflow — 사용량 요약 카드 넘침 수정 (Minor §12.3, CSS 전용)

- `src/static/css/admin.css` — `.profile-usage-summary` 를 flex → **grid auto-fit
  minmax(min(150px,100%),1fr)**, `.profile-usage-metric` 에 `min-width:0`, 숫자 15px + `nowrap`,
  라벨은 ellipsis 허용. 최소 트랙 150px 은 320px 폭에서 12자 값을 수용하도록 실측으로 결정.
- `tests/headless/test_usage_card_overflow.js` (**신규 4건**) — 폭 9단계 스윕 × (카드가 컨테이너를
  벗어남 / 텍스트가 카드를 벗어남) 정량 측정 + 값 길이 증가(9자·12자) + 관리 콘솔 축.
  뮤테이션: 구 flex 복원 시 3건 FAIL(사용자 보고 상태 재현), clamp 제거는 **생존** → clamp 미채택.

## CHG-20260813T2210-ai-claude-corp-usage-card-overflow-tune — 트랙·폰트를 뮤테이션으로 조여 확정 (Minor §12.3)

선행 커밋(트랙 150px·폰트 14px)을 뮤테이션 결과에 맞춰 정정한다.

- **트랙 150px → 138px** — 150px 은 넘침은 막지만 사용자가 보던 폭(≈370px)에서 **1열로 전락**시켜
  같은 정보를 두 배 길이로 만든다. 138px 은 넘침·열 수 양쪽에서 조여진 값(120px 은 넘침 재발,
  150px 은 1열 전락 — 두 뮤턴트가 각각 다른 검사를 FAIL 시킨다).
- **폰트 14px → 15px 복원** — 14px 은 **어떤 케이스도 더 통과시키지 못했다**(뮤턴트 생존).
  검증되지 않는 축소는 가독성만 잃는다.
- **하네스 패딩 16px → 32px** — 라이브 실측(드로어 370px 일 때 요약 컨테이너 306px = 64px 차)에
  맞췄다. 종전 값은 하네스를 라이브보다 관대하게 만들어 **트랙 폭 결정을 판별하지 못했다**(150px
  뮤턴트가 생존했던 원인).
- 검사 2건 추가·정정: 라이브 최대치(11자) @320px · 12자 @420px · "370px 이상 2열 유지".
## CHG-20260814T110000 프로필 사용 내역 표에 정렬·페이지네이션 이식 + 이식 중 적발 결함 (REV-20260814T110000-profile-usage-sort-page)

- 대상: `src/static/app/profile.js` `showProfileUsageConvModal` — 열 정의(5축) · 표시값 기준 정렬 키 ·
  thead 정렬 버튼(aria-sort) · 페이지 슬라이스 렌더 · 페이저 · 상호작용 위임 · 포커스 복원.
  관리 콘솔 판(`admin/usage.js`)과 상수·규칙을 동일하게 맞췄다(테스트가 두 소스를 대조해 잠근다).
- **[P2] 속성 인젝션(적대 리뷰)** — `_pUsageEsc` / admin `esc` 가 `&<>` 만 이스케이프하는데 값이
  `title='…'` 같은 **작은따옴표 속성**에 들어가, 대화 제목만으로 속성을 탈출해 이벤트 핸들러를
  심을 수 있었다(`x' onmouseover='alert(1)`). 관리 콘솔은 **타인의 대화 제목**을 보므로 stored
  경로가 실재한다. → 양 판 모두 `"`·`'` 포함으로 강화(`admin/usage.js` 차트 스코프 `esc` 도 함께 —
  `data-metric='…'` 속성에 쓰인다).
- **[P2] sticky 열 머리가 실제 스크롤러에 안 붙음(적대 리뷰)** — `.usage-conv-tablewrap` 의
  `overflow-x:auto` 가 sticky 의 containing scroll box 가 되는데 그 박스는 세로로 스크롤하지 않아
  머리가 붙을 곳이 없었다(목록을 내리면 머리가 사라져 정렬 버튼 재도달 불가). → 가로 넘침을
  **세로 스크롤러**(`.usage-conv-body` / `.usage-conv-content`)로 옮겨 스크롤러를 하나로 만들었다.
  관리 콘솔 판도 함께 고쳐진다.
- **[P2→반증] 좁은 폭 페이저 넘침** — 실 Chromium 320/480/640px 실측에서 **재현되지 않았다**
  (`.usage-rec-pager` 의 `flex-wrap: wrap` 이 이미 흡수). 지적을 그대로 수용하지 않고 계측으로
  확인했다. 다만 컨트롤이 늘어날 때를 대비해 `.usage-rec-pager-ctl` 에도 줄바꿈을 허용해 뒀다
  (방어적, 무해). **이 축은 회귀 가드일 뿐 결함 수정이 아니다** — 뮤턴트로 검출력이 없음을 확인.
- 무변경: 백엔드 `/api/profile/usage/conversations`, 응답 스키마, 권한.
- 테스트: `tests/verify_profile_usage_sort_page.mjs` **신규 45**(관리 콘솔 판과의 규칙 정합 8축 포함) ·
  `tests/headless/verify_usage_pager_layout.py` **신규 12**(실 Chromium, 두 화면 × sticky/폭/가시성) ·
  `tests/test_usage_records_sort_page.py` **+7 → 16**.
## CHG-20260813T2130-ai-claude-corp-usage-card-overflow — 사용량 요약 카드 넘침 수정 (Minor §12.3, CSS 전용)

- `src/static/css/admin.css` — `.profile-usage-summary` 를 flex → **grid auto-fit
  minmax(min(150px,100%),1fr)**, `.profile-usage-metric` 에 `min-width:0`, 숫자 15px + `nowrap`,
  라벨은 ellipsis 허용. 최소 트랙 150px 은 320px 폭에서 12자 값을 수용하도록 실측으로 결정.
- `tests/headless/test_usage_card_overflow.js` (**신규 4건**) — 폭 9단계 스윕 × (카드가 컨테이너를
  벗어남 / 텍스트가 카드를 벗어남) 정량 측정 + 값 길이 증가(9자·12자) + 관리 콘솔 축.
  뮤테이션: 구 flex 복원 시 3건 FAIL(사용자 보고 상태 재현), clamp 제거는 **생존** → clamp 미채택.
## CHG-20260814T040000-ai-claude-feature-0003-attach-createdat-utc — 첨부 CreatedAt 로컬→UTC 정정

- 사유: 원장 `FR-attachment-created-at-timeaxis-skew`(report-only 이월분)의 해소. 사용자 결정
  2026-08-14 "기록 UTC 전환 + 기존 행 백필". 위험등급 **Major §12.3**(데이터 마이그레이션).
- 대상:
  - `src/routers/_bootstrap_schema.py` `_ensure_attachment_version_schema`: 멱등 DDL 목록에
    `ALTER COLUMN CreatedAt SET DEFAULT (UTC_TIMESTAMP(6))` 추가(fresh install 정합).
  - `src/web_context.py`: `_ATTACH_CREATEDAT_UTC_MIGRATION_KEY` + `_backfill_attachment_created_at_utc_v1`
    신규 + `_ensure_seed_roles` 배선. DEFAULT 전환을 함수 안에서 직접 보장(호출 순서 비의존),
    오프셋은 서버 조회, 대상은 `Id <= MAX(Id)`, PG 미러 동반 보정, 마커 미확인 시 미수행.
- 무변경: 첨부 스키마 컬럼 구성 · UNIQUE · RBAC · 첨부 경계 · 소비자 코드(보정 후 자동 정합).
- 테스트: `tests/test_attach_createdat_utc.py` **신규 10**(1회성·대상 선정·순서 계약 전부 고정).

### CHG-20260814T040000 적대 리뷰 반영 (REV-20260814T040000, [CODEX:adversarial-data-migration])

- **[P1] 동시 startup 이중 차감** — "SELECT 로 없음 확인 → 작업 → INSERT IGNORE" 는 선점이 아니다.
  web-a/web-b 가 동시에 '없음' 을 보면 **둘 다 차감**한 뒤 INSERT IGNORE 에 도달한다(두 번째가
  무시돼도 차감은 이미 끝났다). → `_claim_migration_once`(INSERT 원자성으로 **선점 후 작업**) +
  실패 시 `_release_migration_claim` 반납.
- **[P1] 상한을 ALTER 뒤에 읽음** — DEFAULT 전환 후 `MAX(Id)` 를 읽으면 그 사이 들어온 **이미 UTC**
  행이 상한에 들어와 또 차감된다. → 상한을 **ALTER 이전**에 확정. 남는 위험은 "그 창의 로컬 행이
  미보정" 뿐이라 방향이 안전하다(미보정=원상태, 이중 차감=복구 곤란).
- **[P1] 저장소별 완료 상태 부재** — MySQL/PG 는 한 트랜잭션이 아니다. 단일 마커로는 "MySQL 성공 +
  PG 실패" 를 표현할 수 없어 PG 영구 미보정이거나 MySQL 재차감이 된다. 게다가 미러 upsert 는
  `created_at` 을 갱신하지 않아 "다음 갱신이 정정" 은 **사실이 아니었다**(초판 주석 오류 정정).
  → 마커 2개(`attach-createdat-utc-v1` / `-pg`)로 분리, 각각 선점·반납.
- **[P2] 표시 회귀(사용자 가시)** — API 가 오프셋 없는 문자열을 주고 프론트가 로컬로 파싱하는 계약
  이라, 저장만 UTC 로 옮기면 화면의 첨부 시각이 **9시간 이르게** 표시된다. → `_iso_utc_z` 로 전송에
  `Z` 명시(`_serialize_attachment_for_api` · `lineages`) + `composer.js` 의 시간대 주석을 새 계약으로
  갱신(파서는 `new Date()` 라 `Z` 가 붙으면 자동 정합 — 별도 보정을 넣으면 이중 변환).
- 회귀 고정: 위 4축 전부 테스트(선점 원자성 · 2차 replica 무작업 · 반납 · 상한 선확정 · 서버 오프셋 ·
  저장소별 마커 · 전송 `Z` 표기).

## CHG-20260813T2250-ai-claude-corp-usage-card-overflow-postdeploy — POST-DEPLOY 라이브 실측 (doc-only)

`main 3af15fc2` 배포 후 드로어 폭 6단계(700→320px) 실측 — 전 구간 넘침 0, 보고 폭(370px)에서 2열
유지 확인. 코드 변경 0.
## CHG-20260814T120000 프로필 판 정렬·페이지네이션 POST-DEPLOY 실측 기록 (docs-only)

- 대상: `docs/TEST.md`(POST-DEPLOY Run — 두 화면) · `docs/REPORT.md` · `docs/TASK.md` ·
  `docs/REVIEW.md` · `docs/evidence/pb0008-profile-usage-sort-20260814.png`. 코드 무변경.
## CHG-20260814T060000-ai-claude-feature-0003-attach-version-tree-ui — 버전 비교 축 토글(계보 안/시간순)

- 사유: 사용자 결정(2026-08-14) 남은 판단 ② — 선행 cycle 이 데이터·API 축을 실었고 화면만 남았다.
  위험등급 **Major §12.3**(신규 비교 경로 = 본문 노출 인가 표면).
- 대상:
  - `src/routers/attachments.py` `get_attachment_version_diff`: `from_attachment_id`/`to_attachment_id`
    축 추가(계보 간). **양쪽을 각각 인가** + 같은 대화·같은 파일명 스코프. 기존 version 축 불변.
  - `src/static/app/attach-diff.js`: 축 토글 UI(계보 ≥2 일 때만) · `_fillSelects`(축별 옵션 세트) ·
    `_diffParams`(요청 파라미터 단일 결정점) · 축 전환 시 전체-펼침 캐시 무효화.
  - `src/static/app/messages.js` · `composer.js`: `lineages` 전달(양 경로 대칭) + 계보 2개면 버전
    1개여도 모달 진입.
  - `src/static/css/chat.css`: 축 토글이 보기방식 토글과 **같은 위젯 스타일** 공유(관용구 단일화).
- 무변경: 기존 계보 내 비교 계약 · 권한 게이트 등급(D21 pending 차단 포함) · 첨부 스키마.
- 테스트: `tests/verify_attach_version_tree_ui.mjs` **신규 18**(jsdom 정본 모듈 실행) ·
  `test_attach_version_branching.py` **+4**(인가·스코프·동일첨부 거부·기존축 무회귀).

### CHG-20260814T060000 적대 리뷰 반영 (REV-20260814T060000, [CODEX:adversarial-ux-authz])

- **[P1] 핵심 시나리오의 진입점 부재** — 모달 진입 조건(`lineages>=2`)은 고쳤으나 **버튼 노출 조건**
  (`verNum > 1` / `verCount > 1`)을 놓쳐, 정작 계보가 갈린 뒤의 대표 케이스인 **사용자 v1 ↔ AI v1**
  에서 비교 버튼이 아예 뜨지 않았다. → **AI 수정본은 정의상 분기**(사람 계보에서 갈라져 나옴)라
  v1 이어도 비교 대상이 반드시 있으므로 `verNum > 1 || is_assistant_generated` 로 확대.
- **[P2] 동일 선택 원문 분기가 축을 모름** — 시간순 축의 `from` 은 이미 attachment_id 인데
  version_number 로 체인을 뒤져 "원문을 찾지 못했습니다" 가 떴다(값은 멀쩡한데 화면만 실패).
  → 축에 따라 id 해석.
- **[P2] 전체-펼침 캐시 키 충돌·경쟁** — `pairKey` 가 `from->to` 뿐이라 축이 달라도 같은 키가 될 수
  있고, `expandGap` 에는 `reqSeq` 검사가 없어 이전 축 응답이 캐시를 채울 수 있었다.
  → 키에 축 포함 + 응답 시점 축·선택 재확인.
- **[P2] 계보 간 diff 헤더가 `v0`** — cross-lineage 경로는 version 파라미터가 0 이라 unified_diff
  헤더가 양쪽 v0 로 찍혔다. → 실제 행의 `VersionNumber` 로 되돌림.
- **[P2] versions 빈 배열 역참조** — 계보만으로 진입하면 `list[last].original_filename` 에서 예외.
  → 계보 head 파일명 폴백.
- 회귀 고정: 위 5축 전부 하네스에 추가(E1~E6) → **24 PASS**.
## CHG-20260814T183000-ai-claude-corp-feature-0003-step-panel-timing — 실행 단계 패널 단계별 시각·간격·누적 표기

- **요청**: assistant 답변 진행의 투명화 — 실행 단계 패널 각 단계에 timestamp·단계별 소요·누적
  소요 표기, 기존 텍스트와 충돌 없이 단계 카드 헤더 우측(사용자 스크린샷 형광 위치)에 배치.
- `src/static/app.js` — `_renderStepSidePanelBody` 에 `.step-side-panel-time`(시각 · +간격 ·
  누적) 부착 + 헬퍼 3종(`_parseStepTs`: ISO "T"/psycopg 공백 두 표기 파싱, `_fmtStepDur`:
  60초 미만 소수1자리·이상 m분s초·음수 clamp, `_fmtStepClock`: 로컬 HH:MM:SS).
  데이터는 기존 `step.created_at`(PG timestamptz) 재사용 — backend 무변경, 과거 대화 소급 표기.
  created_at 부재(레거시/서버 합성 step)는 표기 생략(fail-soft).
- `src/static/css/chat.css` — `.step-side-panel-time` 우측 정렬(margin-left:auto)·nowrap·
  tabular-nums + `.step-side-panel-item-header` flex-wrap(좁은 패널에서 겹침 대신 줄바꿈).
- `tests/verify_step_panel_timing.mjs` 신규 30 PASS · 기존 scroll-preserve 29 PASS 무회귀.

### CHG-20260814T183000 적대 리뷰 반영 (REV-20260814T183000, [SUBAGENT:ux+frontend])

- **[P2-1] 테스트 검출력 갭** — fixture 의 레거시(created_at 부재) 단계가 항상 마지막이라,
  "NaN 뒤에 유효 단계" 시퀀스가 미실행 → prev 직전-인덱스 직참조·anchor 첫-인덱스 직참조
  뮤턴트가 30 PASS 전체 통과(생존). → [8] NaN 혼재(선두·중간 레거시) 케이스 추가, 3종 뮤턴트
  전부 사멸 실증. 34 PASS.
- **[P3-4] Intl 포매터 매 호출 생성(~90μs/단계)** → 모듈 상수 `_STEP_CLOCK_FMT` 1회 생성.
- **[P3-7] 첫 단계 툴팁 과잉(3요소 고정 문구)** → parts 수 조건화("기록 시각"만).
- 기록만(수용): P3-1 60초 경계 "+60초"/"1분 0초" 이음새(기존 formatDurationBreakdown 선례와
  동일) · P3-3 MySQL naive datetime 로컬 오해석(ADR-0028 로 dead-code 경로) · P3-6 시계 역행
  clamp 의 누적 비단조(서버 정렬·append-only 병합으로 실현 경로 부재, 방어 코드).

## CHG-20260814T192000-step-panel-timing-postdeploy — 단계 시각 표기 POST-DEPLOY 실측 (검증자산 + docs)

선행 `CHG-20260814T183000-...-step-panel-timing` 이 배포 직전에 남긴 잔여 1건(PB-0008 라이브
시각검증)을 라이브 `ee4eb08d` 에서 닫는다. **제품 코드 변경 0** — 검증 자산과 기록만 추가한다.

- `src/scenario.step-panel-timing.json` (신규): 과거 대화 소급 표기 · 헤더 우측 정렬 ·
  최소 폭 300px · 폭 부족 시 줄바꿈 4축을 실 배포본에서 재현하는 PB-0008 시나리오.
  판정을 사람 눈에 맡기지 않는다 — 표기 정규식·기하(우변 편차/넘침/겹침)·computed CSS 계약을
  step 안에서 assert 하고 어긋나면 실패한다. 패널이 뷰포트의 300~340px 조각이라 전체화면
  캡처로는 10.5px 표기가 판독 불가이므로 **라이브 패널 DOM 복제 2.2× 확대** 오버레이를 함께 남긴다.
- `src/scenario.step-panel-timing-live.json` (신규): 라이브 run 진행 중 폴링 재렌더가 새 단계에
  시각 표기를 붙이는지 — 패널을 **재오픈하지 않고** 단계 수 증가와 새 라벨 형식·누적 단조성을 assert.
  참여자가 나뿐인 **새 대화**를 만들어 질의 1건만 보낸다(공유방에 보내면 AI ask 가 아니라 그룹
  채팅 메시지로 나가 단계가 생기지 않는다 — 선행 시도에서 실측한 함정).
- `docs/TEST.md`: `Environment: Windows-browser` POST-DEPLOY Run 추가 (4축 실측표 + 라이브
  데이터 영향 명시). `docs/test-runs.d/evidence/steptiming-*.png` 4종 첨부.
- `docs/TASK.md`: 배포 후 PB-0008 항목 체크 + 실측 요지.

## CHG-20260814T183000-attach-new-marker-rehydration (cross-ref) — 재수화가 미전송 신규 표식을 보존

- feature-0002 의 `CHG-20260814T183000-attach-change-signal-server-authority`(conv-audit
  `FR-attach-change-signal-client-only`, Major §12.3)의 프론트 축. `composer.js::
  _loadConversationAttachments` 가 버킷을 서버 목록으로 재구성할 때 전 항목을 `source:"session"`
  으로 덮어, 방금 올린 파일의 ★신규 표식이 사라지고 다음 전송의 `new_attachment_ids` 가 비었다
  (그 결과 프롬프트에서 갱신 파일이 "◆세션" 으로 오라벨). 이제 **아직 전송하지 않은** 신규 표식만
  보존한다 — 전송 성공 시 `new → session` 강등(:2836)은 그대로라 과표시로 뒤집히지 않는다.
- **전송 강등도 같은 cycle 에서 교정**(§18.8 codex, P1 3건): 강등 대상 키는 **서버가 응답한
  `payload.conversation_id`**(+ `askKey`/`targetConvId`)이고, 강등 범위는 **이 요청이 실제로 실어
  보낸 id**(`askBody.new_attachment_ids`)뿐이다. sentinel 키만 보면 lazy-create 첨부가 영구 ★신규가
  되고, 응답 시점의 `state.activeConversationId` 를 쓰면 **다른 대화의** 미전송 표식을 지우며,
  버킷 전체를 내리면 응답 대기 중 올린 파일을 잃는다 — 보존(P1)과 강등(P2)은 같은 키·같은 스냅샷
  위에서만 쌍으로 성립한다.
- 정본 계약·AC 는 feature-0002 `FUNCTION.md` (attach-change-signal-server-authority)
  AC-20260814T183000-attach-signal-6. 구조 가드:
  `unit/feature-0003-agent-web-ui/tests/test_attach_new_marker_survives_rehydration.py`(**7 PASS**,
  뮤테이션 KILLED). PB-0008 라이브: `docs/test-runs.d/REV-20260814T183000-attach-change-signal.md`.
- Files: `src/static/app/composer.js` · `tests/test_attach_new_marker_survives_rehydration.py`.

## CHG-20260817T010301-doc-sync-rn-0817 (2026-08-16 · 2026-08-14 블록 신규 prepend) 릴리즈노트 콘텐츠 — 18항목 신규

- 사용자 노출 릴리즈노트(`static/release-notes-data.js`)의 `releases` 맨 앞에 **신규 블록 2개 prepend**: `2026-08-16`(1항목 — 첨부 변경-인지 서버 권위 봉인) · `2026-08-14`(17항목 — 프로필 사용 내역 지표 8종 · 버전 비교 계보 축 토글 · 실행 단계 시각·소요 표기 · 프로필 대화 목록 정렬·페이징 · 사용 기록 표 정렬·페이징 · 외부 AI 답변 보존·열람 · 외부 AI 데이터 직접 조회 + 스코프 격리 정정 · 첨부 버전 계보 작성주체별 분기 · 타 멤버 첨부 본문 턴의 작업공간 쓰기 제한 · 데이터소스 연결 제한 안내 · LLM 스트리밍 전환 · 조기 종료 run 무한 대기 봉인 · 분기 시 작업공간 이월 · 요약 카드 넘침 · 사용량 차트 '요청' 경계 전환 · 엣지 401 호스트 정합 · 외부 AI 실사용 제보 결함 5건 + 인가 완료 화면). `generated` "2026-08-13"→**"2026-08-16"**(top-block date 규약) · `releases` 48→50 · **08-13 이하 48 블록 바이트 단위 무변경**.
- 델타 창(`6d4fdd87`..HEAD) 어떤 커밋도 릴리즈노트를 self-add 하지 않았으므로(편집 전 top 블록 `date: "2026-08-13"`) 직전 run 의 **기존 블록 append** 규칙은 성립하지 않는다 — 배포일이 08-14·08-16 둘이라 신규 블록도 2개다.
- 평이화/비노출: feature-id·§번호·PR#·commit sha·모듈/함수/파일명·테이블명·내부 설정키·ADR·PB-0008·인프라 용어(replica/gateway/worker/quiesce/OAuth/SSE/MCP/SSOT/alembic/KV/컨테이너)·픽셀 값·API 경로·SQL 키워드 누출 **0**(19축 정규식 기계 검증).
- 정본 모순 방지 3건: ① 정본이 서로 다른 두 사건에 같은 '23분' 을 기록해(조기 종료 수동취소 / 상한 초과 폐기 후 재시도) 그 수치를 스트리밍 항목에만 남겼다 ② 첨부 `CreatedAt` UTC 전환은 전송 계약을 같은 커밋에서 함께 옮겨 **화면 표시 무변화**라 사용자향 항목에서 제외 ③ surge 교대 배포의 '바쁠 때 완결' 궤적은 정본이 미관측으로 명시해 제외(허위 방지).
- **배포 게이트 = 물리 실측**: 라이브 컨테이너 6종 전부 `:6c7413cf`(= HEAD = origin/main) · 서빙 static sha 파리티 정확 일치 · `/healthz` 200 → 18항목 전건 배포 완료(유보 0).
- 캐시버스터 수기 bump 없음(빌드 주입 메커니즘 — ITEM-09 · `deploy-web.sh` 가 placeholder 잔존 시 ABORT). `index.html`/`admin.html` 무변경.
- Verification: `node --check` PASS · `verify_release_notes.mjs` **34 pass / 0 fail**(편집 전 baseline 동일) · 블록 48→50 · `releases[0].date`=="2026-08-16"(items 1) · `releases[1].date`=="2026-08-14"(items 17: work 11 · admin 3 · common 3) · `generated`==head.date · 기존 48 블록 바이트 동일 · enum·스키마 외 키 0 · date 내림차순 정상.
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — verify-completion(operational, feature-0003) → 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3).
- Reason: changed paths are docs + 비-정책 static data only — 코드/스키마/권한 변경 0.
- Timestamp: 2026-08-17T01:03:01+09:00

## CHG-20260819T010301-doc-sync-rn-0819 (2026-08-14 블록 append) 릴리즈노트 콘텐츠 — 누락 1항목 보충(17→18)
- 사용자 노출 릴리즈노트(`static/release-notes-data.js`)의 **기존 `2026-08-14` 블록**에 1항목 append(무거운 조회 차단 시 데이터베이스 종류에 따라 대체 안내가 빠지던 문제) + 같은 블록 `summary` 정합. `releases` 50 **불변** · `generated` "2026-08-16" **불변**(top-block date 규약) · `date: "2026-08-13"` 이후 tail **바이트 동일**.
- 신규 블록을 만들지 않은 근거: 항목의 귀속 배포일이 08-14 이고 그 date 블록이 이미 존재한다 → doc_sync Phase 3 의 "기존 블록 append(신규 블록·publish-date 신설 금지)" 규약 적용. 직전 run 이 같은 창에서 18항목을 적재하며 놓친 **prior-window 누락**의 보충이다.
- 평이화/비노출: 벤더명·내부 명칭·경로·SQL 키워드 노출 0. "데이터베이스 종류에 따라" 수준의 사용자 언어로만 서술.
- Verification: `node --check` PASS · 블록 50 불변 · 08-14 items 17→18(work 11 · admin 3 · common 4) · 스키마 외 키 0 · head/tail 바이트 정합 · 내부용어 누출 0. `verify_release_notes.mjs` 는 jsdom 경로 부재로 **미실행**(TEST.md 에 사유·대체 검증 기록).
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3). 서빙 static 변경이 있으므로 wrapper 의 post-merge 배포가 필수.
- Reason: changed paths are docs + 비-정책 static data only — 코드/스키마/권한 변경 0.
- Timestamp: 2026-08-19T01:03:01+09:00

## CHG-20260820T010301-doc-sync-rn-0820 (신규 2026-08-19 블록 prepend) 릴리즈노트 콘텐츠 — 답변 자체 점검 잔존 안내 정정 1항목
- 사용자 노출 릴리즈노트(`static/release-notes-data.js`)의 `releases` head 에 **신규 `2026-08-19` 블록**(items 1 + summary) prepend + `generated` "2026-08-16"→"2026-08-19". `releases` 50→**51**, 기존 50 블록 전건 보존(08-16 items 1 · 08-14 items 18 불변).
- 신규 블록을 만든 근거: 대상 머지 `4af53e37`(merge `22423bd5`)의 배포일 08-19 에 해당하는 date 블록이 파일에 **없었다**(grep 0회) → doc_sync Phase 3 의 "블록 부재 시 신규 블록 prepend · `generated` 는 top-block date 연동" 규약. 라이브 이미지 tag == HEAD 라 배포 게이트 충족(유보 없음).
- 평이화/비노출: feature-id·모듈/함수/테이블명·내부용어 노출 0. "답변을 내보내기 전 자체 점검" 수준의 사용자 언어로만 서술하고, 기존 RN 어휘(자체 점검·발췌·'즉시 답변')에 정합시켰다.
- 정직성: 잔존 시 답변 말미 고지 규칙은 **무변경**(정본 FUNCTION.md §7.6 '의도적 비변경')이므로 "안내를 없앴다" 가 아니라 "안내가 붙을 일을 줄였다" 로 서술했다. 관리 콘솔 표면은 정본이 미추가를 등재해 항목화하지 않았다.
- Verification: `node --check` PASS · 블록 51 · `generated`==top.date · top items 1 · 기존 블록 items 불변 · 스키마 외 키 0 · 내부용어 누출 0 · **`verify_release_notes.mjs` 34 pass/0 fail = 편집 전 baseline 동일(회귀 0)**.
- Files: `static/release-notes-data.js`, `docs/{TASK,MODIFY,FUNCTION,REVIEW,TEST}.md`.
- landing/배포: 무인 cron doc_sync — 로컬 commit 까지만. push/merge/deploy 는 wrapper 소유(v3). 서빙 static 변경이 있으므로 wrapper 의 post-merge 배포가 필수.
- Reason: changed paths are docs + 비-정책 static data only — 코드/스키마/권한 변경 0.
- Timestamp: 2026-08-20T01:03:01+09:00

## CHG-20260824T115000-step-timing-attribution — 단계 시간 귀속 재정의 (cross-feature: feature-0002)

- `src/static/app.js`
  - `_stepToolElapsedMs`/`_isActivityStep` 신규(판독 헬퍼).
  - **`_computeStepTimings(steps)` 신규 · export** — 각 단계의 `{startTs, selfMs, cumulativeMs,
    approx}` 산출. 간격을 "그 동안 실제로 돌던 단계" 에 귀속한다. 순수 함수라 렌더링 없이
    단위 검증 가능(초판은 렌더러 안에 인라인이라 규칙만 따로 시험할 수 없었다).
  - `_renderStepSidePanelBody`: `stepTsList`/`anchorTs` 인라인 계산 제거 → `timings` 소비.
    표기 `기록시각 · +간격 · 누적` → **`시작시각 · 이 단계 소요 · 누적`**, 근사는 `~` 접두,
    소요 미지 단계는 칸 자체를 비우고 툴팁이 사유를 밝힌다. 첫 단계 누적 생략(중복).
- `tests/verify_step_panel_timing.mjs`: 전면 재작성(**70 PASS**) — 귀속 4갈래·폴백·회귀·툴팁 +
  codex 적대 리뷰 반영분(`elapsed_ms` 강제변환 함정 · 시계 역행 누적 단조 · 시작 시각 clamp).
- **codex 적대 리뷰 [P2] 5건 전건 반영**(REV-20260824T115000): ① 시각 없는 중간 단계를 건너뛰고
  정확한 척하던 것 → 근사 표시 ② 레거시 `도구→도구` 를 "정확" 으로 확정하던 것 → 상한이므로
  근사 표시 ③ 시계 역행 시 누적 감소·시작 시각 역전 → 단조 보장 + 직전 종료 clamp
  ④ `Number(null)===0` 이라 값 없음이 "0.0초" 로 둔갑 → 숫자 타입 검사 ⑤ 백엔드 주석·테스트의
  과잉 주장 정정(아래).
- **cross-feature** `unit/feature-0002-agent-core/src/agent_core.py`
  - `_build_step_payload(..., elapsed_ms=None)` — 도구 실측을 `result_summary.elapsed_ms` 로
    싣는다(결과 요약이 비어 `None` 이던 도구도 dict 를 만들어 소요를 보존). 새 컬럼을 두지
    않은 이유: `result_summary` 는 이미 표시층 부가정보 모음이고 PG/MySQL 두 백엔드와
    3개 조회 경로(`_assemble_steps`·`_load_steps_for_run`·`_load_steps_for_message`)를 이미
    전부 통과한다 — 컬럼을 늘리면 그 네 곳의 SELECT 와 마이그레이션이 따라붙는데 얻는 게 없다.
  - `_mirror_step(..., elapsed_ms=None)` 전달. 도구 루프는 `finally` 에서 `_tool_elapsed_ms`
    를 채워 `_build_step_payload`/`_mirror_step` 양쪽에 넘긴다(예외 경로에서도 소요 보존).
  - `tests/test_step_elapsed_attribution.py` 신규 7 PASS(AST 로 호출부 도달까지 잠금).
  - `tests/test_inference_detail.py`: 소스-패턴 계약을 **의미 보존**한 채 정합화 —
    측정 대입 한 줄을 허용하되 `finally` 밖으로 나가면 여전히 FAIL.
- 웹 백엔드 변경 **0** — `result_summary` 가 `_resolve_step_display` 를 포함해 손대지 않고
  통과함을 소스로 확인했다.

## CHG-20260824T130000-step-timing-attribution-postdeploy — 귀속 재정의 POST-DEPLOY 실측 (검증자산 + docs)

`CHG-20260824T115000-step-timing-attribution` 이 배포 직전에 남긴 잔여 1건(PB-0008 라이브 실측)을
라이브 `07755e05` 에서 닫는다. **제품 코드 변경 0** — 검증 자산과 기록만 추가한다.

- `src/scenario.step-timing-attribution.json` (신규): 두 축을 실 배포본에서 재현하는 PB-0008
  시나리오. A) 신규 run(도구 실측 있음)에서 추론/도구가 각자 자기 소요를 갖는지 —
  도구 소요가 3초를 넘거나(추론 흡수 흔적) 추론이 소요를 못 가지면 실패한다.
  B) 과거 대화에서 분리 불가능한 자리가 **비어 있는지** — 숫자가 있으면 실패한다.
- `docs/TEST.md`: `Environment: Windows-browser` POST-DEPLOY Run + 확대 캡처 2종 첨부.
  확대 오버레이 미부착(`document.body.appendChild` 누락) 함정도 함께 기록 — detached 노드는
  개수 단언을 통과시키면서 캡처에는 나오지 않아, 부착 여부를 단언에 넣어 잠갔다.

## CHG-20260824T142000-stale-threshold-attempt-cap — stale 표시 임계를 per-attempt 상한에서 파생 + 마지막 활동 시각 정직화 (Major §12.3)

conv-audit `FR-stale-threshold-below-llm-attempt-cap`(2026-08-24 사용자 명시 호출). 코드 거주
primary = **본 feature**(verify 대상). 라이브 사고 실측은 `docs/TASK.md`
`20260824T1420-stale-threshold-attempt-cap` 블록 참조.

**무엇이 틀렸나**: stale 판정은 step/status 무갱신 시간으로 run 사망을 추정하는데, 그 무갱신
구간의 정상 최대치는 단일 LLM 호출의 per-attempt 상한(`AGENT_TIMEOUT_SEC`)이다. 그 상한은
관리 콘솔에서 **live 로 1800초**까지 올라가 있는데 판정 임계는 코드 상수 **1200초**에 고정돼
있었다 → 상한을 다 쓰는 정상 대기가 **반드시** `stale_error`("작업 중단 감지")로 표시된다.
사고 run 은 그 표시 상태로 10분을 보낸 뒤 재개해 정상 완료(`done`)했다. 데이터 값을 고치면
콘솔 조정으로 곧 되살아나는 drift 이므로 **코드가 불변식(임계 > 상한)을 강제**한다.

- `src/app.py`
  - `_effective_stale_timeout_seconds()` 신설 — `max(WEB_PROGRESS_STALE_TIMEOUT_SECONDS,
    _runtime_settings.get_int("AGENT_TIMEOUT_SEC") + WEB_PROGRESS_STALE_MARGIN_SECONDS)`.
    상수는 **하한**으로 격하(운영자가 env 로 크게 준 의도 보존). 조회 실패·비양수는
    fail-open(종전 상수) — 표시 판정이 런타임 설정 가용성에 종속되지 않게.
  - `WEB_PROGRESS_STALE_MARGIN_SECONDS`(기본 180) 신설. 근거는 라이브 실측 재큐 지연 ~3초 +
    워커 busy 여유. 상한 소진 직후의 재큐→재claim→첫 step 창을 덮는다.
- `src/routers/_conv_store.py`
  - `_compute_display_status` / `_display_status_from_step_at` → 임계를 파생 함수에서 읽고
    `(status, is_stale, **last_active**)` **3-튜플** 반환. 종전에는 판정에 쓴 마지막 활동 시각을
    내부에서 버려, 표면이 대신 `updated_at`(요청 접수 시각)을 "마지막 활동" 으로 보여줬다
    (사고 대화: 실제 12:02 vs 표시 11:19 = 43분). 두 함수 규칙 동치는 유지 — 갈리면 목록과
    long-poll 판정이 어긋난다.
  - `_iso_or_empty()` 신설 — 판정 계층의 UTC naive datetime 을 **tz 명시** ISO8601 로 직렬화.
    naive 를 그대로 내보내면 프런트 `new Date()` 가 로컬(KST)로 읽어 9시간 미래로 표시된다
    (`_last_step_at_for_run` CHG-20260527-0001 tz 회귀와 같은 부류의 입구).
  - 목록 두 경로가 item 에 `last_activity_effective_at` 부착.
- `src/routers/conversations.py` — `/api/progress` 의 판정 호출 3-튜플 정합(1줄).
- `src/static/app.js` — 부제 `최근 갱신` 이 `last_activity_effective_at` 우선(폴백 종전 필드).
  상태 칸은 내부 enum 대신 `pendingStatusLabel()` 경유 한국어 표시.
- `src/static/app/sidebar.js` — stale 툴팁 "마지막 활동" 이 같은 필드 우선.
- `tests/test_stale_threshold_derives_from_attempt_cap.py`(신규) + 기존 2파일 계약 갱신.

**건드리지 않은 것**: 판정 규칙 자체(processing 만 대상 · `max(status_at, step_at)` 기준 ·
terminal 통과) · `/api/ask_status`·`/api/ask_result` 의 terminal 계약 · 워커 stale sweeper 창
(`AGENT_ASK_WORKER_STALE_SEC`) · 보안 경계·RBAC. LLM 무응답 구간 자체를 줄이는 watchdog 은
`agent_core.py::_collect_llm_stream` 주석이 이미 이월한 별 항목으로 남긴다.

### CHG-20260824T142000 §18.8 적대 리뷰 흡수 (codex, [P1] 1 · [P2] 3 → 전건)

`REV-20260824T142000-stale-threshold-attempt-cap` 의 지적을 같은 cycle 안에서 반영했다.

- **[P1] 상한 하락 추종 → high-water mark**: `_STALE_CAP_HIGH_WATER`(프로세스 전역). 상승 즉시
  반영·**하락 미반영**(재기동 경계까지). 진행 중 호출은 시작 시점 상한으로 대기하므로(그 값이
  `_TIER_CLIENT_CACHE` client timeout 에 고정) 판정이 낮아진 값을 따라가면 이 CHG 가 없애려던
  오표시가 그대로 재현된다. 조회 실패도 high-water 유지 → fail-open 이 오표시를 만들지 않는다.
- **[P2] clamp**: `_STALE_CAP_CLAMP_MAX`(runtime_settings 스펙 maximum 을 권위로, 조회 실패 시
  3600) + margin 상한 clamp. env baseline 은 스펙 clamp 를 거치지 않아, 비정상 값이 임계를 수년으로
  늘려 stale 을 사실상 영구 미보고로 만들 수 있었다.
- **[P2] terminal `last_active`**: terminal 도 `last_status_at`(마감 시각)을 반환. 종전 `None` 이라
  완료 대화의 `last_activity_effective_at` 이 비어 표면이 요청 시각으로 폴백했다. terminal 경로는
  **step 조회 없음**(테스트가 조회 시 실패로 잠금) · 인자형 경로는 둘의 max.
- **[P2] `_parse_kv_timestamp` tz**: offset 이 실린 값을 `astimezone(utc)` 후 naive 화. 종전엔
  tzinfo 만 strip 해 `+09:00` 을 UTC 로 오인(9시간 미래) — `_last_step_at_for_run` 의
  CHG-20260527-0001 회귀와 같은 부류를 KV 축에서 봉인. 라이브 KV 는 `+00:00` 저장이라 실동작
  변화 0(실측).
- 흡수분 테스트 6종 추가(하락 무반응 · 실패 시 high-water 유지 · 비정상 cap clamp · 경계 bound ·
  offset→UTC 4케이스 · terminal 반환 2경로). 신규 파일 **19 PASS**, 관련 3파일 **42 PASS**.

## CHG-20260824T152000-stale-threshold-postdeploy — 임계 파생 봉인 POST-DEPLOY 실측 (doc-only, 코드 변경 0)

`CHG-20260824T142000-stale-threshold-attempt-cap`(PR #1320, main `596a722a`) 배포 후 실증 기록.
**제품 코드 변경 0** — 원장 status 전환과 기록만 추가한다.

- 배포본에서 봉인이 실제로 서 있음을 단정: **`threshold_live=1980` > `cap_live=1800`**
  (사고 당시 1200 < 1800). `clamp_max=3600`(스펙 maximum) · `high_water=1800` ·
  판정 3-튜플 + terminal `last_active` · `+09:00`→UTC 변환 · ISO `+00:00` 명시.
- 서빙 자산에 프론트 축 도달(effective 필드 참조 3곳 · 원시 enum 잔존 0 · 캐시버스터 갱신).
- `docs/improvements/conversation-audit/FRICTION_LEDGER.md`:
  `FR-stale-threshold-below-llm-attempt-cap` → **`fixed:deployed:unverified-live`** +
  POST-DEPLOY 절 + 다음 audit 관측 지표 3종. 라이브 UI 실측 미수행 사유를 정직 기록
  (stale 표면 재현이 데이터 write 를 요구 — 감사 persona 읽기 전용 제약).

## CHG-20260824T164437-sidebar-reorder-anim — 좌측 대화목록 명칭 변경 시 재배치를 부드러운 전환으로

사용자 요청(2026-08-24): 대화목록 요소의 명칭을 수정하면 정렬 기준에 따라 순식간에 재배치되어
시야에서 사라진다 → 부드러운 애니메이션으로 재배치. `REQ-20260824-sidebar-reorder-anim`.

- `src/static/app/sidebar.js`
  - **FLIP 재배치 코디네이터 추가**: `requestSidebarReorderAnimation`(예약, export) ·
    `_beginSidebarReorder`(First 스냅샷) · `_commitSidebarReorder`(Last-Invert-Play) ·
    `_expandAncestorsForReorderFocus`(접힌 날짜 그룹/폴더 체인 펼침) ·
    `_scrollReorderFocusIntoView`(시야 추종 + 스크롤 범위 clamp) · `_flashReorderFocus` ·
    `_playReorderMove` · `_reorderRowKey`/`_reorderRowByKey`(재구성 전후를 잇는 행 키) +
    `REORDER_*` 임계 상수.
  - `renderConversationList` → **FLIP wrapper**, 기존 DOM 렌더 본체는
    `_renderConversationListDom(reorderFocusKey)` 로 분리(본문 로직 무변경, 접힘 해제 호출 1줄 추가).
  - `_commitFolderRename`: PATCH 성공 경로에서만 `folder:<id>` 재배치 예약.
  - app.js 에서 `_prefersReducedMotion` import(모션 게이트 단일 정의 공유).
- `src/static/app.js`
  - `_prefersReducedMotion` 을 **export** (기존 내부 함수 — 시그니처·동작 불변).
  - `state.sidebarReorderFocus` 슬롯 추가(예약 {key, at}, 렌더 1회가 소비).
  - `openConversationSettings` 의 `saveTitle`: 제목 PATCH 성공 후 `conv:<id>` 재배치 예약
    (이어지는 `refreshWorkspace` → `renderConversationList` 가 대상).
  - sidebar.js 에서 `requestSidebarReorderAnimation` import.
- `src/static/css/shell.css`: `@keyframes convReorderFlash` + `.conv-item/.conv-folder-header`
  `.is-reorder-flash` (1.1초 강조) + `prefers-reduced-motion` 시 정지.
- `tests/verify_sidebar_reorder_anim.mjs` (신규 73건) · `tests/pb0008_sidebar_reorder_measure.py`
  (신규 — PB-0008 궤적 계측기, folder/conv 2모드) · `tests/verify_new_conv_dedup.mjs`
  (렌더 본체 분리에 맞춰 추출 대상·주입 배선 갱신, 단언 1건 추가).
- 문서: `FUNCTION.md`(REQ + AC 4) · `TASK.md`(cycle) · `TEST.md`/`docs/test-runs.d/`(PB-0008 Run) ·
  `REVIEW.md`(판단 근거) · `REPORT.md`(스냅샷).

**동작 경계**: 예약이 없는 렌더는 좌표 측정도 하지 않아 기존 경로와 동일(주기 unread 동기화·
그룹 토글·대화 선택 등 무영향). 정렬 규칙·API·서버 로직은 **일절 변경하지 않았다** — 재배치가
일어나는 사실은 그대로 두고 그 전환만 보이게 한다.

### §18.8 적대 리뷰(codex) 반영분 — 같은 CHG 안에서 흡수

- `app/sidebar.js`: `bumpSidebarDataVersion()` 신설 + 예약에 `dataVersion` 기록,
  `_beginSidebarReorder` 가 **데이터 버전이 오른 렌더에서만** 예약을 소비(그 전엔 예약 보존,
  TTL 만료 시에만 정리) — [P1]. `_expandAncestorsForReorderFocus` 의 `_saveCollapsedGroups()`
  제거(세션 해제만) — [P2]. `_armReorderCleanup` 분리로 정리자를 **invert 시점**에 설치 +
  `transitionend` 를 `target === el && propertyName === 'transform'` 로 한정 — [P2] 2건.
  `_commitFolderRename` 의 예약을 `loadFolders()` **앞으로** 이동(라이브 실측 회귀).
  `loadFolders` · `_maybeSyncConversationListUnread` 에 버전 bump 추가.
- `app.js`: `state.sidebarDataVersion` 슬롯 + `loadConversations` 의 데이터 반영 지점에 bump,
  `bumpSidebarDataVersion` import.
- `css/shell.css`: 강조색을 `color-mix(in srgb, var(--accent, #2563eb) 22%, transparent)` 로 — [P2].
- `tests/verify_sidebar_reorder_anim.mjs`: 데이터-버전 귀속 · transitionend 버블링 필터 ·
  invert-시점 watchdog · 자동펼침 비영속 · **예약↔데이터적재 순서** 계약 추가 (73 → 93 PASS).
- `tests/verify_conv_entry_defaults.mjs`: `loadConversations` 본체의 새 의존(`bumpSidebarDataVersion`)
  주입 배선 추가.
- `tests/pb0008_sidebar_reorder_measure.py`: 샘플링 창 안의 스크린샷 제거(캡처가 rAF 를 멈춰
  정상 트윈을 "전환 없음" 으로 오보고하던 계측기 자체 결함).

## CHG-20260824T173000-sidebar-reorder-postdeploy — 재배치 전환 POST-DEPLOY 실증 기록

`CHG-20260824T164437-sidebar-reorder-anim`(PR #1324, main `f0a9d4f9`) 배포 후 실증.
**제품 코드 변경 0** — TASK.md 의 POST-DEPLOY 절과 본 기록만 추가한다.

- 서비스별 `GIT_COMMIT` = `f0a9d4f9`(web-a·web-b·엣지 healthz) · 무중단 실측
  `no upstreams available` **0건** · 캐시버스터 `?v=977b70eee5ae` 갱신.
- 라이브 **서빙본**에서 PB-0008 재실측: 폴더 이름 변경 146 → 117, **16 프레임 트윈**
  (122~362ms), 강조 1.1초, 잔류 인라인 스타일 0, 임시 폴더 정리 200.
## CHG-20260824T180000-reorder-easing — 재배치 전환 easing 을 easeInOutBack 으로

사용자 요청(2026-08-24): 재배치 애니메이션에 `easeInOutBack` easing 적용.

- `src/static/app/sidebar.js`: `REORDER_EASING` 상수 신설
  (`cubic-bezier(.68,-.6,.32,1.6)` — easeInOutBack CSS 근사) + `_playReorderMove` 가 참조,
  `REORDER_ANIM_MS` 320 → 420ms(오버슈트 구간 가독).
- `tests/verify_sidebar_reorder_anim.mjs`: easing 이 소스 상수와 일치하는지 + 오버슈트 곡선
  성질(y1 < 0 ∧ y2 > 1) 계약 5건 추가 (93 → 98 PASS).
- 구조·좌표 계약·시야 유지 로직 변경 **0** — 연출 곡선만 교체.

### §18.8 적대 리뷰(codex) 반영분 — 같은 CHG 안에서 흡수 ([P1] 0 · [P2] 2)

- `app/sidebar.js`: `REORDER_EASING_LONG`(ease-out) · `REORDER_BACK_MAX_DELTA_PX = 600` ·
  `REORDER_OVERSHOOT_RATIO = 0.105` 신설. `_reorderEasingFor(delta)` 가 긴 이동을 오버슈트 없는
  곡선으로 강등하고, `_reorderOvershootPx(delta)` 가 시야 보정 패딩에 오버슈트 폭을 더한다
  (`_scrollReorderFocusIntoView(el, expectedDelta)`). 트윈 중 `pointer-events: none` 부여 →
  `_armReorderCleanup` 의 `clear()` 가 정착·watchdog 양 경로에서 복원.
- `tests/verify_sidebar_reorder_anim.mjs`: 기대값을 소스 추출이 아닌 **독립 고정**으로 전환
  (토톨로지 제거) + 타이머 지연값 검사 + 긴 이동 강등 · 포인터 차단 · 오버슈트 패딩 계약 추가
  (98 → 109 PASS).

## CHG-20260824T190000-easing-postdeploy — easeInOutBack POST-DEPLOY 실증 기록

`CHG-20260824T180000-reorder-easing`(PR #1328, main `de940c70`) 배포 후 실증. **제품 코드 변경 0.**

- 서비스별 `GIT_COMMIT` = `de940c70` · 무중단 `no upstreams available` 0건 ·
  캐시버스터 `?v=9ca76406f562` · 서빙본 `REORDER_EASING`/`REORDER_ANIM_MS` 도달 확인.
- 라이브 궤적: 폴더 29px 이동에서 back-in +3px → 오버슈트 -3px → 정착(26프레임/136~541ms).

## CHG-20260824T190000-reorder-affordance — 재배치 연출 재설계(오버슈트 제거 + 도착 표식)

사용자 요청(2026-08-24): 애니메이션보다 더 나은 **명시적** 효과가 있는지 공격적 검토 후 반영.

- `src/static/app/sidebar.js`
  - 곡선 `easeInOutBack` → **ease-out**, 길이 420ms 고정 → **거리 적응형 160~280ms**
    (`REORDER_ANIM_MIN_MS`/`MAX_MS`/`FULL_DELTA_PX`, `_reorderDurationFor`). 오버슈트 전용
    상수·헬퍼(`REORDER_EASING_LONG`·`BACK_MAX_DELTA_PX`·`OVERSHOOT_RATIO`·`_reorderEasingFor`·
    `_reorderOvershootPx`)와 시야 보정의 오버슈트 가산 제거.
  - `_flashReorderFocus` → **`_markReorderArrival`**: 펄스(0.9초) + **지속 앵커**(rail + 배지,
    3.5초) + **도착 묶음 헤더 동반 펄스**. `_attachReorderAnchor`/`_detachReorderAnchor`/
    `_decorateReorderAnchor`(행 생성 시 부여)/`_applyReorderAnchor`(렌더 말미 보강) 신설.
  - 만료 타이머에 **세대 토큰** 도입 — 오래된 타이머가 최신 표식을 지우던 결함 봉인.
  - reduced-motion 경로에서도 도착 표식 부여(트윈만 생략).
  - `buildCompactItem`·`renderFolderNode`(일반·이름변경 두 경로)에 `_decorateReorderAnchor` 배선.
- `src/static/app.js`: `state.sidebarReorderAnchor` 슬롯 추가.
- `src/static/css/shell.css`: 펄스 0.9초 + 날짜 그룹 헤더 펄스 대상 추가 · `.is-reorder-anchor`
  rail(`inset 3px accent`) · `.conv-reorder-badge`(absolute, accent 칩) · `.conv-folder-header`
  `position: relative` · reduced-motion 시 펄스만 정지(rail·배지 유지).
- `tests/verify_sidebar_reorder_anim.mjs`: 기대값 전환(거리 적응형·표식) + 도착 표식 계약 블록 +
  **행 생성 배선 계약** + **연속 이동 세대 계약** + 스텁 확장(다중 클래스·형제·자식 요소·document)
  (109 → **145 PASS**).

## CHG-20260824T200000-affordance-postdeploy — 재배치 연출 재설계 POST-DEPLOY 실증

`CHG-20260824T190000-reorder-affordance`(PR #1330, main `5638b880`) 배포 후 실증.
**제품 코드 변경 0.**

- 서비스별 `GIT_COMMIT` = `5638b880` · 무중단 `no upstreams available` **0건** ·
  캐시버스터 `?v=f18b8028608a` · 서빙본에 표식 심볼 10개 도달.
- 라이브 서빙본 실측: rail(`3px inset accent`) + "이동됨" 배지 부여 → **재렌더 후에도 유지**
  → 3.5초 뒤 자연 소멸. 임시 폴더 정리 200.
- 계측 경로: `win-browser.py` 의 `win_host` 감지(resolv.conf nameserver)가 `8.8.8.8` 로 바뀌어
  브리지가 불가로 보였으나 실제 relay(`172.26.144.1:9223`)는 정상 — playwright 직접 연결 +
  전용 탭으로 검증했다.

## CHG-20260824T203000-dnd-reorder-affordance — 드래그&드롭 이동에도 재배치 연출 적용

사용자 요청(2026-08-24): drag&drop 이동에도 같은 연출.

- `src/static/app/sidebar.js`
  - `moveConversationToFolder`: PATCH 성공 직후 `requestSidebarReorderAnimation(conv:<cid>)` +
    `item.folder_id` 갱신 뒤 `bumpSidebarDataVersion()` (폴더 배정 변경 = 목록 데이터 변경).
  - `moveFolderTo`: PATCH 성공 직후 `requestSidebarReorderAnimation(folder:<id>)` — `loadFolders()`
    **앞**에 둔다(뒤에 걸면 자기 갱신을 지나쳐 소비되지 않는다).
  - 드래그·'···' 메뉴 이동·root 드롭(`#newFolderBtn`)이 모두 이 두 함수로 수렴하므로 전 경로 커버.
- `tests/verify_sidebar_reorder_anim.mjs`: DnD 배선·순서 계약 6건 추가 (145 → 151 PASS).
- 제품 동작 변경은 **연출 적용뿐** — 이동 API·정렬 규칙·폴더 트리 로직은 불변.

### §18.8 적대 리뷰(codex) 반영분 — 같은 CHG 안에서 흡수 ([P1] 3 · [P2] 2)

- `app/sidebar.js`
  - `moveConversationToFolder`: 낙관적 로컬 반영 + 즉시 렌더 **제거** → 예약 후 `loadConversations`
    의 **한 번의 렌더**로 이동(트윈 절단 해소). 제자리 드롭 조기 반환 추가.
  - `moveFolderTo`: 제자리 드롭 조기 반환 추가.
  - `_maybeSyncConversationListUnread`: 진입 가드에 `state.dqaDrag`(드래그 중 재렌더가 drop 을
    씹는 경로)와 `state.sidebarReorderFocus`(대기 중 예약을 가로채는 경로) 추가.
  - `_sameFolderRef` 헬퍼 신설(null=최상위와 숫자/문자 id 혼재 정규화).
- `tests/verify_sidebar_reorder_anim.mjs`: DnD 계약을 **실행형**으로 교체 — 실 함수 구동 +
  스텁 호출 순서 기록(선-렌더 부재 · PATCH 실패 시 예약 없음 · 예약 시점 데이터 버전 ·
  제자리 드롭 무동작) + 동기화 가드 계약 (151 → 160 PASS).
## CHG-20260824T173000-sidebar-rename-focus — 인라인 이름 변경 오확정 봉인 + 대화 '이름 변경' 메뉴

배경 재렌더(주기 unread 동기화 7s · 전환 catchup 1.2s · AI 응답 진행 중 갱신)가 편집 중인
텍스트박스를 떼어내면서 발생시킨 `blur` 를 종전 핸들러가 **확정**으로 처리해, 입력이 끝나기 전의
문자열이 저장되던 결함을 봉인한다. 같은 사이클에서 대화 제목도 폴더와 동일한 인라인 편집으로
바꿀 수 있게 한다(요청 ②).

- `src/static/app/sidebar.js`
  - 신규 공용 편집 세션 코어: `INLINE_RENAME_INPUT_SELECTOR` · `_inlineRenameDetaching` ·
    `_inlineRenameKey` · `isSidebarRenaming`(export) · `_captureInlineRenameEdit` ·
    `_restoreInlineRenameEdit` · `_buildInlineRenameInput` · `_focusInlineRenameInput`.
    확정/취소 규칙을 **단일 정의**로 모아 폴더·대화 두 경로의 분기를 제거.
  - `renderConversationList`: capture → (detach 플래그 on) 렌더 → 플래그 off → restore 로 감쌈.
    편집이 없으면 두 호출 모두 no-op(기존 경로·비용 그대로).
  - `_maybeSyncConversationListUnread`: `isSidebarRenaming()` skip 가드 추가(throttle 갱신 전 반환).
  - `_scheduleSidebarCatchup`: 편집 중이면 같은 지연으로 재예약.
  - 폴더 rename 이관: `_startFolderRename` 이 대화 편집·draft 를 정리(상호 배타),
    `_focusFolderRenameInput` 은 공용 포커스 헬퍼 위임, 렌더는 공용 빌더 사용.
  - 신규 대화 rename: `_startConversationRename` · `_cancelConversationRename` ·
    `_commitConversationRename`(권한 2차 검사 → `PATCH …/title` → 재배치 예약 → 목록·헤더 정합) ·
    `renameConversationFlow`(export).
  - `buildCompactItem`: 편집 중 행을 `<div class="conv-item is-renaming">` 로 렌더(button 안
    input 중첩 회피), `data-conversation-id` 유지로 FLIP 행 매칭 보존.
- `src/static/app.js`
  - `state.conversationRenamingId` · `state.sidebarRenameDraft` 추가.
  - `canRenameConversation` export(사이드바 확정 경로의 2차 권한 검사용).
  - `openConversationItemMenu`: 첫 항목으로 `이름 변경`(추상 action `conversation.rename`) 추가 —
    최종 순서 `이름 변경 · 공유 · 이동 · 설정`. 우클릭 진입(`_CTX_MENU_TARGETS`)은 같은 트리거를
    재발화하므로 자동 반영.
- `src/static/css/shell.css`
  - `.conv-inline-rename-input` 공용 스타일(폴더 전용 클래스는 하위호환 유지) +
    `.conv-item.is-renaming` 편집 행 규칙(커서·hover·글꼴 무게).
- `tests/verify_sidebar_inline_rename.mjs` (신규): 확정/보존 계약 동작 하네스 51 PASS.

## CHG-20260824T190500-sidebar-rename-review-fixes — 적대 리뷰 [P1]·[P2] 흡수

`CHG-20260824T173000-sidebar-rename-focus` 에 대한 §18.8 codex 적대 리뷰([P1] 1 · [P2] 3) 반영.

- `src/static/app/sidebar.js`
  - **[P1] IME 조합 중 재구성 보류**: `_pendingListRender` + `_inlineRenameComposing()`.
    `renderConversationList` 선두에서 조합 중이면 보류 후 반환하고, `compositionend` 가
    `_flushPendingListRender()` 로 1회 수행한다(조합 세션은 노드에 묶여 있어 값 복사로 보존 불가).
  - **[P2] 조합 중 blur 보류·결론**: blur 는 `dataset.pendingBlurCommit` 로 미루고
    `compositionend` 가 확정한다(무시만 하면 편집이 열린 채 남아 억제가 무기한).
  - **[P2] 고아 세션 회수 + 억제 상한**: `_restoreInlineRenameEdit` 이 대상 input 부재 시
    `_endInlineRenameSession()`. `shouldSuppressSidebarRefresh()`(상한 `RENAME_SUPPRESS_MAX_MS`
    60s)를 억제 게이트로 사용 — `isSidebarRenaming()` 은 보존·복원 판정에만 쓴다.
    세션 진입/종료를 `_beginInlineRenameSession`/`_endInlineRenameSession` 로 단일화하고
    `createFolderFlow` 의 직접 id 세팅도 그 계약을 따르게 했다.
  - **[P2] 저장/재조회 분리**: `_commitConversationRename`·`_commitFolderRename` 에서 PATCH 실패만
    실패 토스트로 알리고, 후속 `loadConversations`/`loadFolders` 는 best-effort 로 감쌌다.
- `src/static/app.js`: `state.sidebarRenameStartedAt`(억제 상한 기준) 추가.
- `tests/verify_sidebar_inline_rename.mjs`: 63 → 73 PASS(IME 3축 재정의 · 고아 회수 · 억제 상한 ·
  저장/재조회 분리). 뮤테이션 8종 전건 KILL.
- `tests/verify_sidebar_reorder_anim.mjs` · `tests/verify_new_conv_dedup.mjs`: 구조 변경으로 깨진
  텍스트 단언 2건을 **계약을 유지한 채** 갱신(예약의 실패-경로 도달 불가 / wrapper 본문 계약).

## CHG-20260824T220000-tween-render-defer — 트윈 중 재렌더 보류(직전 [P1] 완결)

- `src/static/app/sidebar.js`
  - `REORDER_TWEEN_GRACE_MS` 신설. `_commitSidebarReorder` 가 트윈 시작 시
    `state.sidebarTweenUntil` 기록(가장 먼 이동의 재생 시간 + 여유).
  - `renderConversationList` wrapper: 트윈 창 동안 재구성을 보류하고 종료 후 1회 flush.
    **IME 조합 보류와 같은 `_pendingListRender` 경로 공유**(중복 메커니즘 회피).
- `src/static/app.js`: `state.sidebarTweenUntil` 슬롯.
- `tests/verify_sidebar_reorder_anim.mjs`: 보류 계약 7건 (160 → 167 PASS).
- 실측 대조: 트윈이 241ms 절단 → **123ms 완주**(vy 30 → 1) 후 t=308 에 보류분 렌더.

### §18.8 적대 리뷰(codex) 반영분 — 같은 CHG 안에서 흡수 ([P1] 2 · [P2] 2)

- `app/sidebar.js`: `_playReorderMove` 가 **실제 트윈 시작 시점 기준으로 보호 창 연장**(rAF 지연
  흡수). 보류 타이머를 전용 핸들 + **deadline 토큰**으로 세대 분리 + 창 연장 확인(이중 방어).
  **편집(인라인 이름 변경) 중에는 보류하지 않는다**(포커스 계약이 동기 렌더에 의존).
- `tests/verify_sidebar_reorder_anim.mjs`: 보류 계약을 **wrapper 실행형**으로 교체(가상 시간·타이머)
  + 이중 방어 존재 계약 (167 → 175 PASS).
