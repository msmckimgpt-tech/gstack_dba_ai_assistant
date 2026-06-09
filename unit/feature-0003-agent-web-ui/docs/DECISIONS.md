---
doc_type: DECISIONS
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

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
