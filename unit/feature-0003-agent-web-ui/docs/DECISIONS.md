---
doc_type: DECISIONS
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-WEB-0006
- Date: 2026-06-26 (TASK-20260626T025055-product-chip-always-enabled)
- Context: composer 의 제품 선택 chip(`#productChip`)이 대화가 "요청 처리 중"인 동안 두 계층으로 막혀 있었다 — ① `renderProductChip()` 이 `isCurrentConvBusy()` 면 `chipEl.disabled=true`+`is-disabled`(시각/상호작용 차단, `openProductDropup` 가드로 드롭업 차단), ② `setActiveProduct()` 가 busy 면 토스트 후 변경 거부(기능 차단). 둘 다 TASK-0047 의 "처리 중 제품 변경 race 가드". 사용자 보고: 요청을 보낼 때 제품 선택 버튼이 비활성화됨 — 항상 활성화 상태여야 함.
- Options: (A) 시각 disable 만 해제(chip 은 클릭되나 `setActiveProduct` 가 여전히 거부) — 버튼이 활성처럼 보이나 선택이 토스트로 실패하는 모순 UX. (B) **두 계층 모두 해제** — chip 항상 활성 + 처리 중 선택 적용(다음 요청부터 반영). (C) 가드 유지(현행).
- Decision: **(B) 모든 계층 해제** (사용자 결정 2026-06-26). 차단은 실제로 **세 계층**이었다 — ①② 프론트(renderProductChip 시각·setActiveProduct reject) + ③ 백엔드 `PATCH /api/conversations/{cid}/product` 의 `_conversation_is_processing`→409. ①②만 풀면 owner 가 처리 중 제품을 클릭할 때 PATCH 가 409 로 거부되어 에러 토스트로 실패(활성처럼 보이나 동작 안 함)하므로, 적대 검증 subagent 의 적발에 따라 ③ 백엔드 409 가드도 함께 제거했다. 근거: 제품(`product_id`/`product_mode`)은 `/api/ask` 슬롯 획득 후 1회 read(app.py:11676-11704)→`run_kwargs` baked(11995-12013)→worker payload(11293~) 로 캡처되고, worker `_payload_to_kwargs`(modules/ask.py:85-104)·`run_agent`(agent_core)는 conversation 제품을 **재조회하지 않는다**. PATCH 는 단일 row UPDATE 로 in-flight run 에 부수효과가 없다(취소·KV·캐시 무영향). 따라서 처리 중 제품 변경은 진행 중 답변을 오염시키지 않고 **다음 ask 부터** `_load_conversation_product`(11521) 로 적용되어 `setActiveProduct` 토스트("다음 답변/메시지부터 적용됩니다")와 정확히 일치. TASK-0047 race 가드(프론트)·409 가드(백엔드)는 데이터 정합성 보호가 아니라 보수적 UX 가드였고(데이터 손상 위험 0, 적대 검증 5축 반증 실패 VERDICT SAFE), 처리 중 입력창 비잠금(feature-0009 composer-nonblock-interrupt R1)과 같은 방향이다. (A)는 "활성처럼 보이나 동작 안 함"이라 사용자 의도("항상 활성")에 미달하여 기각.
- Consequence: `renderProductChip()` busy 분기·`setActiveProduct()` busy reject 가드 제거(app.js) + `update_conversation_product` PATCH 의 409 turn-immutability 가드·docstring 제거(app.py) + index.html app.js cache-buster bump. **RBAC(conversation.ask·소유권·product access·IsActive)·스키마·엔드포인트 계약·마이그 무변경** — 제거된 것은 timing 가드뿐. helper `_conversation_is_processing`(3669)은 잔여 호출처 없으나 재사용 가능 util 이라 보존. app.py:11586~ 의 "기존 대화 제품 변경은 PATCH 단일 경로(TASK-0047)" 주석은 여전히 유효(PATCH 가 단일 변경 경로인 사실은 불변, busy-블로킹만 완화). 향후 처리 중 chip 라벨과 in-flight 답변 제품이 일시적으로 다르게 보일 수 있으나 토스트가 "다음부터 적용"을 안내하므로 수용.

## ADR-WEB-0005
- Date: 2026-06-09 (TASK-0170)
- Context: Fork(`_fork_conversation_impl`)가 웹 표시 메시지(`agent_runtime.messages`)만 복사하고 LLM 문맥(`agent_runtime.core_messages`, agent_core 가 매 ask 마다 읽음)은 복사 안 해, 복사본 대화에서 어시스턴트가 이전 문맥을 인지 못 함(사용자 보고). 또 첨부(`WebConversationAttachments` blob + `agent_attachment_<sha256(cid)>` sandbox)도 미복사. 사용자가 "전체 복사처럼 보이되 내부적으로 원문 참조" 하는 git 식 reference 아키텍처를 희망.
- Options: (A) **하이브리드** — core_messages(+로컬 sandbox) deep-copy + 동일소유자 file blob 만 참조. (B) 순수 git-reference — 본문·첨부 모두 런타임에 원문 참조(lineage 컬럼 + 코어 로더 merge + IDOR 게이트 확장 + 교차계정 live read). (C) 본문만 복사, 첨부 이월.
- Decision: **(A) 하이브리드** (사용자 결정, outside-voice REV-20260609-0003 권고 수용). 순수 git-reference(B)는 적대적 설계 검토에서 **BLOCKER 2건**(F1 cross-table 시각 cut 불가 — messages/core_messages 독립 clock 이라 앵커 시각으로 core 자르면 turn 갈라져 `_normalize_history_rows` 가 통째 drop → 문맥 소실 재발; F2 로더 오기술 — tail 윈도우라 lineage merge 후 조상 evict) + **보안 안티패턴**(F3 `.any`-source fork 가 권한 회수 후에도 피해자 데이터 영구 live tap; F4 교차계정 live reference 는 매 ask 마다 A 데이터가 B LLM 으로 상시 흐름 — deep-copy snapshot 과 비등가; F5 sandbox 조상 스키마 공유가 1-conv-1-schema 격리 파괴)로 기각. 하이브리드는 사용자 4대 목표(문맥 인지·첨부 포함·전체 본문·"복사처럼 보이되 참조")를 충족하며 F1/F3/F4/F5 를 구조적 제거.
- Decision (구현 분할):
  - **Phase 1 (본 cycle 구현)**: fork 시 `core_messages` deep-copy(anchored=앵커 시각 cut, full/duplicate=전체). 교차계정 fork 도 snapshot. 스키마 변경·코어 로더 변경 0(순수 복사). → **보고된 버그 해결.**
  - **Phase 2 (후속 cycle)**: 첨부 행 복사(동일 ObjectKey, blob 재업로드 0) + 로컬 sandbox 스키마 복제(공유 아님) + 동일소유자 blob 참조. IDOR 게이트 변경 동반 시 outside-voice.
- Consequence: fork/duplicate/공유-fork 본에서 어시스턴트가 이전 문맥 인지(Phase 1). 첨부는 Phase 2 까지 미포함(표시 메시지의 분석 텍스트는 core_messages 복사로 문맥엔 포함). 순수 reference 의 저장 절감은 미획득(텍스트는 복사가 정답이라 무의미; blob 참조 이득은 Phase 2). 설계 정본 `DESIGN-fork-reference.md`.

## ADR-WEB-0004
- Date: 2026-06-09 (TASK-0164)
- Context: `/api/ask` 가 agent 를 web 프로세스 안 `asyncio.to_thread` 로 실행 → web 재배포/SIGTERM 이 in-flight run 을 죽여 orphan("처리중" 고착). TASK-0159(부팅 reconciliation)·0160(히스토리 정합)은 증상 완화. 구조적 정답은 실행을 web 밖으로 분리하는 것(out-of-process ask-worker)이나 대규모(신규 서비스·job 큐·slot DB 이전·배포계약 변경, Critical).
- Options: (A) SIGTERM graceful finalizer — 종료 시 이 프로세스 in-flight run 을 error 마킹(소규모·저위험, 근본의 ~90% 차단). (B) out-of-process ask-worker — 구조적 정답(web 재배포가 run 무영향)이나 대규모·Critical.
- Decision: **A 구현 + B 설계만**(사용자 결정). A 로 orphan-on-redeploy 를 저위험 차단(부팅 reconciliation 과 대칭 backstop 쌍 완성), B 는 `DESIGN-ask-worker.md` 로 남겨 자체 cycle + outside-voice 로 구현. A2(고아 권한 catalog prune)·A3(빈 그룹 키 유지)는 동반 cosmetic.
- Consequence: 재배포 시 orphan 이 종료 시점에 즉시 정리(부팅까지 안 기다림). 실행모델은 그대로라 worker 분리의 멀티-replica·exactly-once 이득은 미확보 — B 구현 시 달성. A 의 best-effort 한계(SIGKILL)는 부팅 reconciliation 이 backstop. outside-voice PASS-WITH-NITS(REV-20260609-0164).

## ADR-WEB-0002
- Date: 2026-06-08 (TASK-0161)
- Context: `attachment.execute_sql_on.own/.any` RBAC 권한이 정의·롤 부여·관리 그리드에 노출됐으나 **enforce 가 한 번도 배선되지 않음**(권한 체크 호출처 0). TASK-0094 가 defense-in-depth 의 RBAC 층으로 의도했으나 실제 게이트(① 계정-스코프 schema allowlist[TASK-0132 IDOR] ② attachment_reader/agent_ro DB 최소권한 ③ sql_guard AST)만 ship 됨. 관리자가 체크박스를 꺼도 첨부 sandbox SQL 이 차단되지 않는 "거짓 컨트롤" — 잘못된 보안 안심.
- Options: (A) enforce — LLM tool 실행 경로에 권한 체크 배선해 그리드 토글을 실제화. (B) remove — 거짓 컨트롤 제거, 실제 3중 게이트에 의존.
- Decision: **(B) remove.** 위험한 교차계정 경로는 이미 계정-스코프 allowlist 가 차단하므로 enforce 는 회귀위험(operator/sales 정상 본인-첨부 SQL 차단) 대비 실익이 낮음. own 경로는 본인 첨부 SQL 이 정상 동작이라 게이트 의미 약함. outside-voice 적대적 리뷰 PASS-WITH-NITS(BLOCKER 0).
- Consequence: RBAC 카탈로그 -2 코드, 관리 그리드의 무의미한 체크박스 제거, 첨부 sandbox SQL 의 단일 진실 게이트가 allowlist+DB유저+sql_guard 로 명확화. attachment 권한 그룹은 비게 됨(admin.js 빈 그룹 자동 제외). 향후 진짜 RBAC 게이트가 필요하면 enforce 와 함께 재도입.

## ADR-WEB-0003
- Date: 2026-06-08 (TASK-0161)
- Context: `conversation.attachment.upload.any` 는 `_account_can_access_attachment` 로 **실제 enforce** 되나, composer 가 비소유 대화 업로드를 차단해 관리자가 타 계정 대화에 업로드할 UI 진입점이 없는 latent 권한.
- Decision: **유지 + 문서화**(UI 미신설). 거짓 컨트롤이 아니며(백엔드 권위적 게이트), 관리자가 타 계정 대화에 콘텐츠를 주입하는 것은 프라이버시·신뢰 민감 행위라 명확한 제품 수요 확인 전에는 UI 를 만들지 않는다.
- Consequence: 정의부에 의도 주석 추가, 카탈로그·시드 무변경. 향후 admin-upload 수요 발생 시 별 cycle 에서 audit·UX 설계 동반 신설.

## ADR-WEB-0001
- Date: 2026-03-26
- Decision: Web UI는 코드 소유권만 분리하고 런타임 이미지는 core feature에서 조립한다
- Consequence: 기동 구조는 단순하지만 build coupling이 남는다

## ADR-20260714T181936-perm-category-hier — 관리 콘솔 권한을 nav 카테고리 '접근' 게이트 계층으로 재구성 (A안)

- **Status**: accepted (사용자 승인 2026-07-14, Critical §12.3)
- **Context**: 권한 grid 가 console.access 단일 마스터 아래 그룹 base 평면 나열이었고, 감사 카테고리 4개 탭(감사 로그·보관 대화·LLM 사용량·AI 운영 현황)의 조회 권한이 3개 그룹(audit/conversation_any/console)에 산재. system.runtime.* 종속 미선언, insight.reset 그룹 오배치, 카테고리 단위 접근 게이트 부재.
- **Decision**: ① 카테고리 최상위 '접근'(=조회 게이트) 권한 5종 신설 `console.{account,product,audit,kb,system}.access` — console.access 하위, 같은 카테고리의 모든 권한(탭 조회→추가/수정/삭제→승인/작동)이 그 하위로 탭 구조 따라 재귀 종속. ② 탭 노출 = 카테고리 접근(AND) && 탭 권한(OR). ③ 백엔드 엔드포인트 enforcement 는 불변(접근 권한=nav 노출+부여 계층 규율, 역함의 없음). ④ 기존 배포는 1회 멱등 backfill(`console-category-access-v1`)로 접근 무손실. ⑤ GroupName 재배치로 표시 그룹을 카테고리와 정합(코드 불변).
- **Alternatives**: B안(신규 권한 없이 표시 계층만 재구성) — 위험 최소지만 "권한 단위의 카테고리 최상위 접근" 요건 미충족으로 기각. 엔드포인트에 카테고리 접근 AND enforcement 추가 — 수십 핸들러 변경·락아웃 리스크 대비 이득 없음(기존 console.access+세부 게이트 유지)으로 보류.
- **Consequences**: 역할 편집 grid 가 nav 카테고리와 1:1 정합(상위 체크 시 하위 펼침). 신규 역할 구성 시 카테고리 접근을 먼저 부여해야 탭이 노출된다(의도된 계층 규율). backfill 이후 새로 세부 권한만 부여된 role 은 접근 권한을 명시 부여해야 한다(자동 함의 없음).
- **Cross-ref**: SECURITY.md §22 · CONVENTIONS.md §10.6 · CHG-20260714T181936 · 선례 graph-perm-split(ADR 없음, TASK 20260713T1818)·metadata-perm-hier.

## ADR-20260715T103406-perm-atomic-split — 권한 최소 단위 원자화(레거시 묶음 숨김 + transitive 함의)

- **Status**: accepted (사용자 승인 2026-07-15, Critical §12.3 — perm-category-hier ADR-20260714T181936 후속)
- **Context**: 카테고리 계층 재구성 후에도 권한의 잎이 묶음([등록/수정/삭제] 단일 manage, 검수 [승급/거부] 단일 curate)이라 원칙 ②(수정 가능 항목=추가·수정·삭제 단위)가 미충족.
- **Decision**: ① 원자 23종 신설 + 엔드포인트 enforcement 액션별 전환. ② 레거시 묶음 7종은 코드·기존 grant·transitive 함의(DENY 우선)를 안전망으로 유지하되 **권한 grid 에서 숨김**(신규 부여는 원자만). ③ 검수는 단일 '검수' 단위 유지 + **원본 사전 read 하위 종속**(사용자 지시 — 반쪽 검수자·큐 항목 편집 귀속 모호성 회피). ④ 1회 backfill(`atomic-perm-split-v1`)로 묶음 보유 principal 에 원자 explicit 전개(+DENY 조합 고정), category-access-v1 선행. ⑤ 부트스트랩=create∧update AND, AI 자동완성=update(조회만으론 LLM 비용 유발 불가), 연결 테스트=`datasource.test` 작동 단위.
- **Alternatives**: 묶음 grid 표시 유지(통합 항목 잔존이라 기각 — 사용자 결정), 검수 승급/거부 분리(반쪽 검수자 모호성 — 기각), choke-point(_account_has_permission) 묶음 fallback(원자 DENY 무력화 — 기각).
- **Consequences**: grid 에는 원자 단위만 보인다(조회→추가/수정/삭제/검수 트리). 역할 저장은 preservedHidden(TASK-0300)이 숨긴 묶음 grant 를 보존. 신규 역할은 원자 단위로만 구성.
- **Cross-ref**: SECURITY §22.4 · CONVENTIONS §10.6 · CHG-20260715T103406.

## ADR-20260729T140200-attach-full-scope — 첨부 참조 스코프를 대화 전체로 (D16 minimum exposure supersede)

- **Status**: accepted (사용자 승인 2026-07-29, Major §12.3)
- **Context**: D16(BRIEFING-attachment-multi-cycle §68)은 `attachment_ids` 기본값을 "현재 composer 의 selected/ready 첨부만"으로 좁혀 minimum exposure 를 달성했다. 그러나 참조 범위의 결정 주체가 프론트 selection bucket 이라, bucket 이 비는 진입 경로(새로고침·랜딩 복귀·pending 컨텍스트, `_loadConversationAttachments` 는 `switchConversation` 경로에만 존재)에서 이전 턴 첨부가 통째로 누락됐다 — 사용자 보고 "첨부된 요청 수행 후 이어서 요청하면 기존 첨부에 접근 불가". 보완재로 둔 `attachment_scope_all` 토글은 **백엔드에서 읽힌 적이 없어**(Python 전역 0건) 실질 no-op 이었다. 또한 인라인 상한 밖 파일의 유일한 회복 안내가 "사용자에게 재첨부 요청" 이었다.
- **Decision**: ① 참조 스코프를 `_resolve_conversation_attachment_scope` 로 **대화의 활성 첨부 전량**(최신본·미삭제·업로드 완료, 상한 200)으로 해소하고 client 선택분을 합집합으로 보존한다. ② 그룹 대화의 발신자 스코프(CSO F1)·ConversationId 스코프(IDOR)·공유창 누출 게이트는 **그대로 유지**한다. ③ 상한 밖 본문은 전량 인라인이 아니라 `read_attachment` 도구로 모델이 자율 조회한다(목록은 전량 노출, 본문은 on-demand). ④ 자가 적대 리뷰어에게는 미인라인 첨부를 매니페스트로 전달한다. ⑤ 의미를 잃은 "이 대화의 모든 첨부 사용" 토글을 제거한다.
- **Alternatives**: (a) 전량 인라인 — 구현은 단순하나 첨부 많은 대화에서 토큰·컨텍스트 압박이 급증하고 상한 문제가 재발(기각, 사용자 확인). (b) 프론트 bucket 재수화 경로만 보강 — 진입 경로가 늘 때마다 같은 결함이 재발하는 구조를 남김(기각 — 결정 주체를 서버로 옮기는 편이 근본적). (c) 그룹 대화까지 전체 개방 — 타 멤버 첨부가 발신자 권한 실행 맥락에 실려 datasource 를 끌어오는 권한상승 경로(기각, 사용자 결정으로 가드 유지).
- **Consequences**: 이어지는 대화에서 첨부가 조용히 사라지지 않는다. 프롬프트의 첨부 **메타 목록**이 대화 규모에 비례해 커지지만(파일당 1줄), 매 턴 인라인되는 **본문량은 종전과 동일**하다(상한 불변). 모델이 `read_attachment` 를 호출하는 만큼 도구 왕복이 늘 수 있다 — 자율 판단에 맡기되 첨부 있는 대화에서만 도구를 노출해 헛호출을 줄인다. D16 의 "명시 선택만 노출" 원칙은 대화 경계 안에서는 폐기되고, 경계 자체(대화·그룹·공유창)가 노출 통제를 담당한다.
- **Cross-ref**: FUNCTION `REQ-20260729-attach-full-scope` · TASK `20260729T1402-attach-full-scope` · BRIEFING-attachment-multi-cycle D16(superseded) · feature-0009 CSO F1 · TASK-0284.
## ADR-20260729T152000-ratelimit-scope-paging — rate-limit 버킷을 기능별로 격리하고 페이징을 비용 등급에 맞춰 재가격

- **Status**: accepted (사용자 확인 2026-07-29, Major §12.3 — rate-limit 은 DoS 방어선이라 상한 조정은 "보안 저하 가능성" 축)
- **Context**: `_search_rate_limit_check`(REQ-20260518-0010 / TASK-0072)는 도입 당시 대화 본문 검색 전용이었고 버킷 키를 `account_id` 로만 잡았다. 이후 5개 기능이 같은 헬퍼를 `max_per_min` 만 바꿔 재사용하면서, **계정당 단일 버킷을 6개 기능이 공유**하는 상태가 됐다 — 상한이 큰 기능(메타데이터 AI 20)의 소비가 상한이 작은 기능(버전 페이징 5)의 예산을 통째로 태워, 페이징은 자기 첫 클릭에서 429 를 맞았다. 사용자 보고("대화 페이징 시 '요청이 너무 잦습니다' 블로킹 빈번")의 직접 원인. 더해 페이징(`branch/switch`)은 DB 읽기 4쿼리 + UPDATE 1회(실측 p50 8.0ms)인데 full LLM run(실측 p50 12,344ms, n=6,975)과 같은 5/min 예산을 썼다.
- **Decision**: ① 버킷 키를 `(account_id, scope)` 로 바꾸고 호출부가 `RATE_SCOPE_*` 를 명시한다 — 각 호출부의 **선언 상한이 실제로 그 호출부에만 적용**된다. ② 버전 페이징에 전용 상한 60/min 을 준다(LLM 점유 경로 5 는 무변경). ③ 429 는 `Retry-After` + 본문 `retry_after` + 대기 초 문구로 회복 어포던스를 제공한다. ④ 페이징의 **내용 재조회**를 클라이언트 캐시로 옮겨 서버 왕복을 줄인다 — 단 `active_leaf` **영속은 지연하지 않는다**. ⑤ `_branch_leaf_of` 재귀 서브쿼리에 `conversation_id` 술어를 넣어 상한 상향의 안전 마진을 확보한다.
- **Alternatives**: (a) 페이징 상한만 올리고 버킷은 그대로 — 교차오염이 남아 다른 기능 사용 직후 여전히 차단(기각: 증상만 가림). (b) 페이징을 rate-limit 대상에서 제외 — SEC MINOR-C 가 지목한 재귀 CTE 스크립트 연사 방어선이 사라짐(기각). (c) 프론트 캐싱만 하고 백엔드는 무변경 — 캐시 적중 시에도 `branch/switch` 는 매번 나가므로 5/min 버킷은 그대로 터짐(기각: 부분 해소). (d) `branch/switch` 영속을 디바운스해 요청을 더 줄임 — agent-core `memory.py` 가 `active_leaf` 로 새 메시지의 부모 체인과 LLM recall 범위를 정하므로, 지연 중 발화하면 새 메시지가 화면과 다른 가지에 붙는다(기각: 8ms 절약을 위해 데이터 정합성을 거는 거래). (e) 공유 Redis 등 프로세스 간 버킷 — 현 규모에서 불필요한 인프라(보류, 기존 per-worker 한계 유지).
- **Consequences**: 계정당 **집계** 상한은 올라간다(최악 min(caps) → 각 scope 합). 그러나 각 호출부의 상한 주석이 명시한 의도가 "기능별 예산"이었으므로 이는 선언 의도의 복구이지 완화가 아니다 — 실제로 완화된 것은 페이징 5 → 60 하나뿐이며 비용 실측이 근거다. LLM·외부 비용을 태우는 경로(fix-with-ai / 메시지 편집 / 메타데이터 AI)의 상한은 그대로라 비용 DoS 표면은 넓어지지 않는다. 클라이언트 캐시는 TTL 30s + 단일 choke-point 무효화라 그룹 대화에서 최대 30s 의 stale 열람 가능성이 남는다(읽기 전용 페이징 한정 — 활성 대화 본문은 기존 `_liveSyncTick` 5s 폴러가 계속 갱신). 버킷 키 공간이 계정수 × scope수 로 늘어 메모리 가드를 함께 도입했다.
- **Cross-ref**: FUNCTION `REQ-20260729T152000-ratelimit-scope-paging` · TASK `20260729T1520-ratelimit-scope-paging` · MODIFY `CHG-20260729T152000-ratelimit-scope-paging` · REQ-20260518-0010(TASK-0072 원 도입) · feature-0019 SEC MINOR-C(재귀 CTE 연사 방어).
## ADR-20260729T163000-attach-append-only — 대화 첨부 목록은 append-only (attach-list-delete 삭제 UI 철회)

- **Status**: accepted (사용자 지시 2026-07-29, Minor §12.3 — 프론트 전용). `ADR-20260729T140200-attach-full-scope` 의 후속이자, 그 사이 들어간 삭제 UI(`20260729T1520-attach-list-delete`)의 **철회**.
- **Context**: attach-full-scope 로 참조 스코프가 "대화의 활성 첨부 전량" 이 되자, 종전의 "이번 요청에서 빼기"(로컬 목록 제거) 의미가 사라졌다. 적대 리뷰가 "로컬에서만 지우면 서버가 되살린다"는 모순을 지적했고, 이를 **실삭제 연결**로 해소했다(pill × → `DELETE /api/attachments/{id}`, 이어서 목록 행에도 ×). 그러나 사용자는 **삭제 기능 자체를 의도하지 않았고**, 첨부 목록을 대화 내부의 append-only 기록으로 관리하기를 지시했다.
- **Decision**: 대화의 첨부 목록은 **append-only** 다. ① UI 에서 서버 저장 완료(`ready`) 첨부를 빼거나 지우는 컨트롤을 제공하지 않는다 — pill 의 ×도, 목록 행의 ×도 없다. ② ×는 **아직 대화에 들어가지 않은 항목**(업로드 중 / 실패한 로컬 placeholder)에만 붙는다(`_discardPendingAttachmentPill`) — append 를 되돌리는 것이 아니라 append 가 성립하지 않은 항목을 치우는 것이라 원칙과 모순되지 않는다. ③ 백엔드 `DELETE /api/attachments/{id}` 는 존치하되 **UI 는 호출하지 않는다**(관리·보존정책 경로의 수단으로 남김). ④ 안내 문구를 "첨부는 대화에 계속 쌓입니다" 로 바꿔 append-only 를 명시한다.
- **Alternatives**: (a) 삭제 UI 유지 + 그룹 안전판 — 사용자 의도와 어긋나 철회. (b) "이번 요청에서 제외" 토글 부활 — attach-full-scope 가 참조 범위를 대화 단위로 확정했으므로 서버가 되살리는 같은 모순이 재발(기각). (c) 첨부 숨김(soft-hide) 상태 도입 — 새 상태·마이그레이션 비용 대비 요구가 없고, append-only 취지에도 어긋남(기각).
- **Consequences**: 잘못 올린 파일도 대화에 남고 assistant 참조 스코프에 계속 포함된다 — 사용자가 그 의미를 알 수 있도록 안내 문구가 이를 명시한다. 선행 cycle 이 이월했던 **"그룹 첨부 삭제 권한이 업로더가 아니라 대화 소유자/그룹 멤버"** 이슈는 UI 경로가 사라지면서 **본 제품 표면에서는 무효**가 된다(백엔드 엔드포인트는 남아 있으므로 정책 자체는 별도 판단 대상으로 유지). 첨부 누적에 따른 용량·비용은 기존 size cap(`_check_attachment_size_caps`)과 reconciliation retention 이 계속 담당한다.
- **Cross-ref**: FUNCTION `REQ-20260729-attach-append-only` · TASK `20260729T1630-attach-append-only` · 철회 대상 `REQ-20260729-attach-list-delete` (AC-1~3 superseded, AC-4 레이아웃은 유효) · `ADR-20260729T140200-attach-full-scope`.

## ADR-20260806T154100-attach-manage — 첨부 삭제(버전 선택)·복구·일괄 다운로드 (attach-append-only supersede)

- **Status**: accepted (사용자 승인 2026-08-06, **Critical §12.3** — 파괴적 데이터 삭제 + 인가 경계 변경). `ADR-20260729T163000-attach-append-only` 를 **supersede** 한다.
- **Context**: 2026-07-29 사용자 지시로 첨부 목록을 append-only 로 확정하고 삭제 UI 를 철회했다. 2026-08-06 사용자가 ① 특정 첨부 삭제(일부/모든 버전 선택) ② 모든 첨부 다운로드(압축/개별 취사 선택)를 요청하며 그 결정을 뒤집었다. 실측상 백엔드는 이미 준비돼 있었다 — `DELETE /api/attachments/{id}` 존치, `DeletePending`/`DeletedAt`/`lifecycle_state` 4-state + `restorable_until`(retention 기본 30일) 직렬화, reconciliation worker 의 만료 purge. 다만 `restorable_until`·`lifecycle_state` 는 **소비처가 0곳**이라 복구 경로가 없었고, 삭제 인가는 열람 헬퍼(`_account_can_access_attachment`)를 재사용해 **그룹 멤버 전원**이 남의 첨부를 지울 수 있었다(선행 ADR 이 "별도 판단 대상"으로 이월한 미해결 이슈 — UI 를 되살리면 그 경로가 함께 살아난다).
- **Decision**: ① **append-only 철회** — 목록 행·버전 행에 삭제 컨트롤을 둔다. ② **삭제 강도 = soft-delete + 복구(휴지통) UI** — 즉시 purge 는 불채택. 삭제 즉시 목록·AI 참조 스코프에서 빠지고 retention 창 안에서는 되살릴 수 있다(`POST /api/attachments/{id}/restore`). ③ **삭제·복구 인가를 좁힌다** — `_manage_gate_for_conversation` 신설: `upload.any` OR (`upload.own` + 업로더 본인 OR 대화 소유자). 그룹 멤버 단독은 거부. 열람 경계는 종전대로(멤버 열람 가능) 유지 — 두 경계는 서로 다른 것을 지킨다. ④ **버전 scope** — `?scope=version`(기본, 그 버전만) / `chain`(체인 전량). 오타는 기본값으로 격하하지 않고 400. ⑤ **최신 삭제 시 직전 버전 승격**(`_promote_latest_version`) — 승격하지 않으면 체인 전체가 목록에서 사라져 "이 버전만 삭제" 가 성립하지 않는다. ⑥ **일괄 다운로드** — `GET /api/conversations/{cid}/attachments/download` 의 `format=zip|manifest` × `scope=latest|all`. ZIP 총량 상한 초과는 **부분 ZIP 대신 413**(§16.7 G9-b 무음 절단 금지). ⑦ **표시-집행 정합** — 목록·버전 응답의 `can_manage` 를 인가 술어와 **같은 코드**로 계산해 내린다(§16.7 G6).
- **Alternatives**: (a) 즉시 실삭제 — 오조작 회수 불가(기각, 사용자 결정). (b) 삭제 권한을 현 백엔드대로 그룹 멤버 전원 — 제3자가 남의 파일을 지우는 사고 경로(기각, 사용자 결정). (c) 업로더 본인만 — 방치된 파일 정리 수단이 사라진다(기각, 사용자 결정). (d) 최신 삭제 시 첨부를 목록에서 숨김 — "이 버전만" 의 의미가 무너진다(기각, 사용자 결정). (e) 프론트가 소유권을 추정해 버튼을 표시 — 표시·집행 두 벌이 어긋난다(기각, §16.7 G6).
- **Consequences**: 잘못 올린 파일을 회수할 수 있게 되고, 그 대가로 삭제라는 파괴적 표면이 생긴다 — soft-delete + 휴지통이 완충이며, retention 만료 후에는 되돌릴 수 없다(휴지통에 남은 기간을 표시한다). 그룹 대화에서 **업로더가 아닌 멤버는 더 이상 삭제할 수 없다** — 선행 동작 대비 좁아지는 변경이며, 열람은 영향받지 않는다. 일괄 ZIP 은 web 프로세스가 객체를 읽어 스풀에 담으므로 대용량 대화에서 I/O 가 늘 수 있어 상한(`ATTACHMENT_BULK_ZIP_MAX_BYTES`, 기본 512MB)을 두고 초과 시 개별 다운로드로 안내한다. 안내 문구의 "첨부는 대화에 계속 쌓입니다" 는 사실이 아니게 되어 제거했다. 신규 테이블·마이그레이션·권한 코드는 **0** (기존 컬럼·권한 재사용).
- **Cross-ref**: FUNCTION `REQ-20260806-attach-manage` · TASK `20260806T1541-attach-manage` · MODIFY `CHG-20260806T154100-attach-manage` · supersede 대상 `ADR-20260729T163000-attach-append-only` · `ADR-20260729T140200-attach-full-scope`(참조 스코프=대화 전량, 유효).

## ADR-20260813T183000 — 공유 대화 첨부의 LLM 참조 경계: 발신자-한정 → 대화 스코프 + window 게이트

- **Status**: Accepted (사용자 결정 2026-08-13, Critical §12.3 — 보안 경계 변경, override 미적용)
- **Context**: 그룹 대화에서 첨부 LLM 주입만 발신자 본인으로 좁혀져 있었고(feature-0009 CSO F1,
  2026-06-19 결정 · 2026-07-29 재확인), 열람·다운로드는 전원 공유였다(REQ-GC-R6). 이 비대칭이
  "화면엔 보이는데 assistant 만 못 보는" 마찰을 만들어 라이브에서 사용자 이탈까지 관측됐다
  (`FR-group-attach-sender-scope-blocks-members`, 첨부 보유 그룹 대화 6/6 노출).
- **Decision**: ① 그룹 첨부 스코프를 **대화 전체**로 열되 **공유창 window 게이트**로 축소 조건을 둔다
  (은닉 표시 메시지가 실재하는 발신자만 종전 동작). ② 판정은 **단일 정본**(`shared/share_window.py`)에
  두고 web 스코프 해소와 agent_core 주입 게이트가 **같은 함수**를 쓴다. ③ CSO F1 이 겨냥한 indirect
  prompt injection 은 **출처 라벨 + 데이터-전용 계약**(AUTH-1a)으로 대체 통제한다. ④ 읽기만 열고
  **쓰기 경계는 불변**으로 두되, 그 한계를 프롬프트가 미리 고지한다.
- **Alternatives**:
  - *가드 유지(수정 안 함)* — 기각: 마찰이 구조적이고(6/6) ANCHOR §1·§2 의 협업 전제와 어긋난다.
    가드 자체도 다운로드 후 재업로드로 우회 가능해 악의는 못 막고 정직한 사용자만 막았다.
  - *스코프만 열기(완화책 없음)* — 기각(사용자 선택지에서 미채택): injection 위협이 무방비로 남는다.
  - *첨부 `created_at` 을 window 경계와 직접 비교* — **기각(중요)**: 첨부는 표시 메시지에 바인딩되지
    않고 `created_at` 이 메시지와 다른 시간축이다(라이브 실측 +9h, 로컬시각이 UTC 로 라벨링돼 저장).
    하한에서 열고 상한에서 가리는 양방향 오판이 난다. 대신 **은닉 구간 실재 여부**(메시지 id/joined_at)
    로 게이트한다 — 정밀도는 낮지만 오판 방향이 항상 안전한 쪽이다.
  - *열람 경계까지 좁혀 대칭 맞추기* — 기각: 협업 가치 훼손 + ANCHOR Alt-C 기각 재확인.
- **Consequences**: 은닉 구간이 있는 bounded 멤버는 window 안 첨부도 못 본다(과차단 — 첨부↔메시지
  연결이 없어 정밀 판정 불가). 첨부 시간축 왜곡이 해소되면 "은닉 구간 첨부만 제외" 로 정밀화 가능하며,
  그 왜곡은 fork 의 `_attachment_outside_window` 에도 영향을 주는 **별도 결함**으로 원장에 등재한다.
- **Cross-ref**: SECURITY §47 · FUNCTION `AC-20260813T183000-group-attach-scope-window-{1,2,3}` ·
  feature-0009 `REQ-GC-R6`(갱신) · TASK `20260813T1830-group-attach-scope-window` ·
  FRICTION_LEDGER `FR-group-attach-sender-scope-blocks-members`.

## ADR-20260814T010000 — 첨부 버전 계보 분기: 별도 root 체인 (스키마 미확장)

- **Status**: Accepted (사용자 결정 2026-08-14, Major §12.3)
- **Context**: assistant 수정본이 사용자 계보에 `v+1` 로 편입되고 사용자 최신본을 supersede 해,
  한 계보에 사람 버전과 AI 버전이 섞였다(라이브 39체인). 사용자는 "내가 올린 최신" 을 목록에서
  잃고, assistant 는 "누구 기준 최신" 을 구분하지 못했다.
- **Decision**: ① assistant 수정본을 **별도 root 체인의 v1** 로 분기하고 원 계보는 건드리지 않는다
  (supersede 없음). ② 자기 계보 재편집은 그 계보에서 `v+1` 로 **연장**. ③ 분기 지점은 **MetaJson**
  에 기록해 스키마·UNIQUE 를 건드리지 않는다. ④ "최신" 의 두 축(**계보 내** / **시간순**)을 프롬프트
  블록과 API `lineages` 로 **함께** 노출한다. ⑤ 기존 혼합 체인은 **백필하지 않는다**(사용자 결정).
- **Alternatives**:
  - *`BranchKey` 컬럼 추가 + `UNIQUE(Root, Branch, Version)`* — 기각(사용자 선택): 조회·인덱스는
    정확해지나 MySQL 정본 + PG 미러 양쪽 스키마 변경 · 39체인 백필 · 소비자 다수(versions·diff·
    delete scope=chain·다운로드 파일명) 수정이 따른다. 얻는 정확성 대비 롤백 단위가 거칠다.
  - *표시 계층만 변경* — 기각: 버전 번호가 여전히 공유돼 "독자적인 버전 관리" 요구를 절반만 충족.
  - *기존 39체인 분리 백필* — 기각(사용자 선택): 사용자가 이미 본 버전 번호가 재배치되고 되돌리기
    어렵다. 과거 이력은 있는 그대로 두는 편이 정직하다.
- **Consequences**: 같은 파일명이 목록에 **둘 이상** 보일 수 있다(사용자 계보 head + AI 계보 head).
  이는 의도된 결과이며 기존 `AI 수정` 배지로 구분된다. 프론트 버전 모달의 **기준 토글 UI 는 미구현**
  — API 축은 실렸고 후속 cycle 대상이다. MetaJson 기반 트리라 계보 관계로 **인덱스 조회는 못 한다**
  (파일명+대화 스코프 조회로 충분한 현재 규모에서는 문제되지 않는다).
- **Cross-ref**: FUNCTION `REQ-20260814-attach-version-branching` · TASK
  `20260814T0100-attach-version-branching` · MODIFY `CHG-20260814T010000-…` ·
  선행 `ADR-20260813T183000`(공유 대화 첨부 스코프).
