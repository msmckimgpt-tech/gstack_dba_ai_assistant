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
