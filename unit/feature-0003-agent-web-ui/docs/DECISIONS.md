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
