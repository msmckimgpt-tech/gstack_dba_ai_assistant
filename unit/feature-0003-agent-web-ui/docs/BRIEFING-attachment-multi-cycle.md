---
doc_type: BRIEFING
feature_id: feature-0003-agent-web-ui
status: planning
edit_policy: rewrite
source_of_truth: false
related_task: TASK-0094 (REQ-20260521-0001, Critical §12.3) — 초기 등재 시 TASK-0087 사용했으나 [TASK.md](unit/feature-0003-agent-web-ui/docs/TASK.md) 의 기존 TASK-0087 (외부 LAN trust 강화) 와 충돌하여 Revision 2 시점에 TASK-0094 / REQ-20260521-0001 로 재할당
related_review: REV-20260520-0001 (1차 Codex outside-voice review, 20 Claim — Valid 17 / Partial 1 / 결정 영역 1 / Misread 0) + REV-20260521-0002 (2차 follow-up, Verdict NEEDS_REVISION → Revision 2 흡수)
plan_eng_review_date: 2026-05-20 (1차) + 2026-05-21 (2차 follow-up, §17 흡수 완료)
outside_voice: codex (consult mode, model gpt-5 default, reasoning=medium, web_search_cached, read-only sandbox, session 019e4421-2a8f-74a2-8b91-6afc191856e0, 호출 2026-05-20 / 2026-05-21, 2 turn / 12 tool calls / 278,180 tokens)
risk_grade: Critical §12.3 (인증/인가·개인정보·외부 공개 범위·비용 4 항목 동시 변경)
worktree: ai/claude/0087/attachment-briefing (v3.8.0 §13.2 격리)
---

# BRIEFING — TASK-0094 첨부 기능 multi-cycle (A+B+C+D) — Revision 2

> **번호 재할당 (2026-05-21)**: 본 BRIEFING 은 초기 Revision 1 작성 시 TASK-0087 / REQ-20260520-0001 로 등재되었으나, 같은 feature 의 [TASK.md](unit/feature-0003-agent-web-ui/docs/TASK.md) 에 이미 TASK-0087 (외부 LAN trust 강화, REQ-20260520-0002, Major) 이 점유되어 있어 충돌. Revision 2 시점에 본 첨부 기능 cycle 을 **TASK-0094 / REQ-20260521-0001** 로 재할당. 본문에서 "TASK-0087" 로 표기된 잔존 reference 는 모두 본 TASK-0094 를 가리키며, worktree 디렉토리명 `.worktrees/0087-attachment-briefing` 만 git worktree 생성 시점 명칭이므로 별도 cleanup 시 재명명 가능 (현재는 유지).

본 문서는 `사용자가 현재 서비스에 파일을 첨부하는 형태(ChatGPT 처럼)로 개선할 수 있을지 검토를 진행해주세요` 라는 사용자 요청에서 출발한 multi-cycle plan 의 정본이다. 직전 검토 cycle 에서 (1) 4 시나리오 (A CSV ingest / B DDL KB / C Vision / D RAG) 전체 진행, (2) Codex outside-voice review 동반, (3) 핵심 결정 3 건 (storage / sandbox / vector store) 이 확정되었다.

**Revision 1 (2026-05-20)** — Codex outside-voice review 1 차 호출 (session `019e4421-...`) 결과 20 Claim 수신 → 내부 정책 / spec 정합 검토 → 17 Valid finding 흡수 + 1 Partial / 1 결정 영역 / 0 Misread. 본 revision 의 주요 변경: §2.2 의 D6/D9/D10/D11/D12 결정 갱신 + §2.2 신규 D13~D17 (Codex 직접 도출) + §5.1 의 ActionCode dotted lowercase 표기 수정 + UploadStatus 확장 + §5.2 RBAC group 매핑 정책 강화 + §5.3 LLM 송신 bytes 전송 정책 + §5.4 attachment_ids 기본값 selected only + §5.5 content array DB 저장 contract 명시 + §6.1 Sprint 1 의 wildcard grant 금지 / SQL AST guard / delete reconciliation / MinIO bootstrap 강화 / XLSX edge / sandbox sha256 mapping + §6.4 PDF degraded state + §8 share derived content redact + §13 Codex review 결과 정리 + §14 정합 검토 결과 + §15 worktree 정책 정합.

**Revision 2 (2026-05-21)** — Codex outside-voice review 2 차 (REV-20260521-0002, 같은 session resume) 결과 **Verdict NEEDS_REVISION** 수신. 1차 Claim 재검토 (20 건) + 신규 finding F1~F14 (Critical 3 / Major 11 / Minor 2) 도출. 본 revision 의 주요 변경: §2.2 의 D6/D9/D11/D12/D13/D14/D15/D16/D17 결정 inline 갱신 (Rev2 marker `→ Rev2:` 추가) + §2.2 신규 D18~D21 (단일 통합 gate 유지 / `WebAttachmentDerivedMessages` join table / MinIO dual-key rotation runbook / pending role metadata-only) + §17 Codex 2차 review 결과 매트릭스 + §17.3 신규 blindspot F1~F14 흡수 표 + §17.4 본문 cross-ref + §17.6 워크트리 cleanup 완료 조건. **Critical 3 건 중 F8 만 사용자 명시 거부** (gate 통합 유지) — 위험 격리는 D14 allowlist + R-Claim4 grant 최소화 + R-F4 drift health endpoint + D20 MinIO rotation 으로 충족.

---

## 1. 문제 정의 — 본 cycle 이 해결하는 사용자 pain

현재 서비스는 사용자 텍스트 질의만 받고, 외부 자료 (CSV/Excel/PDF/이미지) 를 분석 컨텍스트에 포함할 수 없다. DBA AI 어시스턴트로서 다음 시나리오에서 즉시 정체된다.

- **사내 DB 외부 데이터 join**: 영업팀이 받은 외부 거래처 CSV 를 사내 거래 데이터와 join 하여 분석하고 싶을 때, 현재는 CSV 를 임시 테이블로 직접 ingest 한 뒤 SQL 작성 → 외부 의존 도구 필요.
- **에러 / 결과 화면 분석**: 외부 시스템 (BI 도구, ERP, 비-MySQL DB) 의 에러 캡쳐를 LLM 에 보여주고 의견을 묻고 싶을 때, 텍스트로 옮겨야 함.
- **DBA 스키마 정의서 ingest**: 신규 스키마 도입 시 DDL/설명문을 KB 에 등재해 두려 해도 manual ingest tool 부재 → admin 은 SQL 로 직접 INSERT.
- **사용자 문서 RAG**: 사용자가 가진 PDF 매뉴얼·정책 문서를 LLM 컨텍스트로 활용하고 싶을 때, 외부 GPT 로 우회 → 사내 데이터 외부 유출 위험 + 본 서비스 가치 누수.

본 cycle 은 이 4 가지 pain 을 시나리오 A·B·C·D 로 각각 해소한다. 각 시나리오는 별 cycle 로 분리되며 의존 인프라 (Cycle 0 Foundation) 를 공유한다.

---

## 2. 결정 요약 — 직전 cycle 사용자 확정 + Revision 1 의 갱신·신규 결정

### 2.1 사용자 직접 확정 (직전 cycle AskUserQuestion)

| ID | 질문 | 결정 | 영향 |
|---|---|---|---|
| **D1** | 첨부 파일 저장 위치 | **S3-compat (MinIO compose +1)** | compose service `minio` 추가, `WebConversationAttachments.ObjectKey`, signed URL 생성/검증 (사내망 다운로드 전용) |
| **D2** | Sandbox DB 격리 (A) | **동일 cluster + 별 schema** | `agent_attachment_<hash>` schema 동적 생성 (D15 의 maintenance path 가 담당), `attachment_writer` MySQL user 분리 |
| **D3** | D 의 vector store 전략 | **PGVector (Postgres 도입)** | compose service `postgres` 추가, agent_memory 별 cycle 과 인프라 sequencing (§12) |
| **D4** | 전체 시나리오 진행 | **A + B + C + D 전부, 4 sprint 분리** | §6 sprint sequencing — 현 유지 (Codex #18 분리 권고 vs 사용자 가치 우선 — 사용자 가치 우선 채택) |
| **D5** | Codex outside-voice review | **예 (1차 호출 완료)** | §13 finding 표 — 17 Valid 흡수 (본 revision), 1 Partial 부분 흡수, 1 결정 영역 (#18 sequencing) 사용자 확정 |

### 2.2 결정 요약 — Revision 1 (Codex finding 흡수 + 신규 도출) + Revision 2 (Codex 2차 review 흡수)

> **Revision 2 marker 안내**: Revision 2 의 갱신은 각 항목 끝에 `→ Rev2:` 라인으로 inline 추가됨. 상세 매트릭스는 §17. 영향 본문 cross-ref 는 §17.3.

| ID | 변수 | 결정 | 근거 |
|---|---|---|---|
| **D6** (revised) | 첨부 lifecycle taxonomy | **4 종 분리** — (a) user 명시 delete (메타 soft-delete + MinIO retention 30일 후 lifecycle purge), (b) conversation soft-delete (cascade — 첨부 동일 soft), (c) admin purge (MinIO 즉시 + DB hard-delete), (d) legal erasure (모든 store 즉시 + audit GDPR-style log). 각 SLA 표는 §6.1 lifecycle 표 참조. → **Rev2 (R-Claim6)**: conversation hard-delete 시 attachment metadata 는 FK cascade 대신 **tombstone 보존 + nullable `ConversationId`** 로 reconciliation 완료 전까지 유지. → **Rev2 (R-F1)**: UX 표면화 4 state (`delete_pending` / `restorable_until` / `purge_in_progress` / `erased`) — attachment list + audit detail 전체 노출. → **Rev2 (R-F12)**: legal erasure 의 audit row 는 **pseudonymous irreversible event id** 로 attachment id / HMAC 대체 + `action_type` / `erased_at` 최소 필드 유지 (PII 잔존 금지 + "무엇을 지웠는지" 증명 양립) | Codex Claim #6 + #7 + 2차 F1 / F12 흡수 — 단순 "soft 30d / hard 동기" 표현으로는 compliance 와 복구 정책의 동시 만족 불가 + delete UX state 표면화 + legal erasure audit 충돌 해소 |
| **D7** (변경 없음) | MIME allowlist | `text/csv` / `application/vnd.openxmlformats-...spreadsheetml.sheet` / `application/vnd.ms-excel` / `application/pdf` / `image/png` / `image/jpeg` / `image/webp` / `text/plain` / `text/markdown`. **거부**: 모든 archive (zip / tar). XLSX 는 zip container 지만 MIME magic + 구조 검증으로 archive 거부와 양립 (§6.1) | Codex #14 — XLSX/CSV edge case 는 §6.1 별 추가 |
| **D8** (변경 없음) | Size cap | per-file 25 MB / per-conv 100 MB / per-account 1 GB | |
| **D9** (revised) | Share view 정책 | **2 단**: (a) 첨부 객체 hide (이미 R7 적용), (b) **attachment-derived assistant message redact** — `WebMessages.MetaJson` 에 `attachment_derived: true` flag, share builder 가 해당 메시지의 CSV sample / PDF excerpt / 이미지 분석 부분을 redact 또는 share 생성 시 사용자에게 경고 + 명시 토글. → **Rev2 (R-F7, Critical)**: 기존 발급된 share token 도 **배포 즉시 자동 redact 적용** + audit `share.policy.redact_applied` 이벤트 기록 (보안 우선 — 기존 공유 수신자 derived 영역 즉시 가려짐). share token 발급 시점의 정책 version 도 row 에 저장하여 향후 정책 변경 시 추적 가능 | Codex Claim #19 + 2차 F7 흡수 — 첨부 객체 hide 만으로는 derived content 누출 차단 불가 + 기존 token backward-compat 충돌 해소 |
| **D10** (revised) | PGVector 인스턴스 정책 | **단계적**: (a) dev / 1차 단계는 agent_memory 별 cycle 과 동일 컨테이너 + DB 분리 (`agent_rag`, `agent_memory`), user 분리 (`rag_writer`, `memory_writer`). (b) **prod 는 별 PGVector instance 옵션을 PLAN gate 에서 재검토** — backup / restore / disk full / migration restart 의 운영 경계가 컨테이너 단위라 같은 장애 도메인 묶음은 dev-only | Codex Claim #17 — DB-level 권한 분리는 보안 경계, 운영 경계는 컨테이너 단위 |
| **D11** (revised) | 외부 LLM consent 모델 | **provider + data class + purpose 별 consent + revoke + audit + 재동의**. data class = {file_text, file_image, file_embedding}. purpose = {inference, indexing}. 첫-trigger = "첫 외부 송신 직전" (upload 시점 아님). consent revoke 시 미사용 + 새 conv 에서 재동의 modal. `WebAccountConsents` 신규 테이블 (account_id × provider × data_class × purpose × granted_at × revoked_at). → **Rev2 (R-F2)**: UX 는 **grouped batch modal** — provider 별 3 group 만 노출 (파일 텍스트 분석 / 이미지 분석 / 문서 인덱싱), 같은 action 에서 필요한 consent 는 한 modal 에서 batch grant/reject. DB 는 세분 row 유지 (보안 단위 ↔ UX 단위 분리). → **Rev2 (R-F13)**: provider Files API 사용 시 `provider_file_id` 저장 + 사용 후 delete API 호출 + 실패 cleanup worker + provider 측 보관 가능성을 consent 문구에 명시 | Codex Claim #9 + 2차 F2 / F13 흡수 — account-level global flag 는 upload 와 외부 송신 시점 차이 미반영, revoke path 부재 + modal 폭격 위험 + provider 측 파일 잔존 |
| **D12** (revised) | Audit 마스킹 정책 | **HMAC + 카테고리 + 정규화**: (a) filename 은 tenant secret keyed HMAC + extension bucket (`.csv`/`.xlsx`/`.pdf`/`.png`/...), (b) size 는 coarse bucket (`<1KB`/`1-10KB`/`10-100KB`/`100KB-1MB`/`1-10MB`/`10-25MB`), (c) sandbox SQL 은 sqlparse / sqlglot AST normalized form + action category (SELECT/JOIN/AGGREGATE 등) + referenced schema/table list + row count + denied reason, (d) raw filename / raw SQL 은 기본 금지. → **Rev2 (R-F12 cross-ref)**: legal erasure 의 audit 는 D6 의 pseudonymous event id 정책에 따라 attachment id / HMAC 도 irreversible event id 로 대체 | Codex Claim #10 + 2차 F12 cross-ref — filename hash 만으로는 사전공격 가능, query hash 만으로는 사후 분석 불가 + legal erasure 시 HMAC 도 PII 잔존 |
| **D13** (신규) | LLM bytes 전송 방식 | **외부 LLM 에는 signed URL 금지** — 서버가 권한 확인 후 MinIO 에서 bytes read → provider 별 base64 inline (OpenAI vision) 또는 files API (OpenAI Assistants, Anthropic Files API). 사이즈 / 토큰 / 비용 cap 별도 적용. signed URL 은 frontend 다운로드용으로만 유지 (사내망). → **Rev2 (R-F13)**: Files API 경로 사용 시 `WebConversationAttachmentProviderFiles(AttachmentId, Provider, ProviderFileId, UploadedAt, DeletedAt)` row 생성, inference 직후 provider delete API 호출, 실패 시 cleanup worker (`reconcile_provider_files`) 가 TTL 기반 재시도. consent 문구에 "프로바이더 임시 보관 가능" 명시 | Codex Claim #8 + 2차 F13 — 사내 MinIO 는 외부 LLM 망에서 접근 불가, signed URL 방식은 무조건 실패 + Files API provider-side 보관 lifecycle 명시 |
| **D14** (신규) | Sandbox SQL guard | **AST parser + DB 권한 2중 차단**: (a) sqlparse / sqlglot 으로 SQL AST 파싱, (b) allowlist = SELECT-only (CTE 가능), session variables / DDL / DML / FILE / LOCK / CALL / multi-statement 차단, (c) `attachment_reader` MySQL user 의 권한 grant 자체가 read-only + sandbox + 정본 SELECT 만 (cleanup-only `attachment_cleanup` user 분리), (d) `SET SESSION TRANSACTION READ ONLY` + statement timeout + max rows. → **Rev2 (R-F3, Critical)**: **denylist → allowlist 전환**. "허용된 AST shape 만 통과" 모델로 — single SELECT statement (optional CTE) 외 전부 거부. AST shape allowlist 는 다음을 거부: `FOR UPDATE` / `LOCK IN SHARE MODE` / `EXPLAIN ANALYZE` (write 가능 path) / optimizer side-effect hint / `SELECT SLEEP()` / `SELECT BENCHMARK()` / user variable read·write (`@x`, `SET @x`) / `INTO OUTFILE` / `INTO DUMPFILE` / `LOAD_FILE()` / `information_schema.*` / `mysql.*` / `performance_schema.*` / `sys.*` 접근. denylist 는 보조 secondary check (defense in depth). 테스트는 §9.1 의 SQL guard 표에 위 케이스 전수 포함 | Codex Claim #15 + 2차 F3 (Critical) 흡수 — regex/string 판정은 우회 다수 + denylist coverage 증명 부담 → AST shape allowlist 가 evidence-of-safety 정공법 |
| **D15** (신규) | Sandbox schema grant 정책 | **와일드카드 grant 금지** — schema 생성은 별도 privileged maintenance path (`attachment_maintainer` MySQL user) 가 담당. → **Rev2 (R-Claim4)**: `attachment_maintainer` 도 wildcard 제거. bootstrap privileged app path 가 schema 생성 직후 **exact backtick schema 명** 으로 `attachment_writer` 에 `CREATE / ALTER / INSERT / SELECT` 만 grant. `attachment_writer` 의 GRANT ALL 제거 (최소권한). DROP SCHEMA 는 `attachment_cleanup` user 가 reconciliation job 으로만 수행. → **Rev2 (R-F4)**: per-schema expected grants 를 `WebConversationAttachmentsSandboxSchemas` mapping table 에 저장하고, reconciliation worker (`attachment_grant_audit`) 가 5분 주기로 drift 탐지 → admin alert + `/api/admin/health/attachment-grants` health endpoint 노출 | Codex Claim #4 + 2차 R-Claim4 / R-F4 — MySQL GRANT 와일드카드 매칭 위험 + maintainer wildcard 잔존 + writer 과대 권한 + drift 운영 장애 |
| **D16** (신규) | `attachment_ids` 기본값 | **현재 composer 의 selected/ready 첨부만** (기존 "conversation 의 모든 ingested 첨부" → 변경). UI 의 첨부 pill 이 default selected (그러나 사용자가 deselect 가능), `/api/ask` body `attachment_ids` 가 명시되지 않으면 **빈 list** 처리 (frontend 가 항상 명시 전송). "이 대화의 모든 첨부 사용" 은 명시 토글 + audit `attachment.scope.all` action 기록. → **Rev2 (R-F5)**: `sendPrompt()` 시작 시 **attachment selection snapshot** 을 `busyKey` / pending sentinel 에 저장 (lazy-create race 차단). request closure 는 그 snapshot 만 전송하며, 사용자가 새 대화 B 로 전환해 pill 을 바꿔도 in-flight 요청 A 는 영향 받지 않음. pending entry click 복원 시에도 attachment snapshot 함께 복원 | Codex Claim #13 + 2차 F5 흡수 — minimum exposure 원칙 위반 + 전역 attachment state 가 lazy-create 시 race |
| **D17** (신규) | UploadStatus 확장 | **enum 7 값**: `uploaded` / `processing` / `ingested` / `indexed` / `partial_indexed` (★ NEW — degraded) / `failed` / `deleted`. scanned PDF / encrypted PDF / no-text PDF / 200+ page cap / table-heavy 의 경우 `partial_indexed` + MetaJson 에 `degraded_reason` 명시. 사용자 UI 에 노란 경고 표시 ("일부 페이지만 인덱싱됨"). → **Rev2 (R-F6)**: retrieval-time 정책 추가 — top-K 가 `partial_indexed` 문서에서 나온 경우 (a) `/api/ask` answer meta 에 `degraded_sources[]` 분리, (b) UI 메시지 영역에 persistent warning banner, (c) LLM system note 에 "근거 누락 가능 — 일부 페이지만 인덱싱됨" 주입, (d) follow-up suggestion 에 "OCR 처리 후 재인덱싱" 옵션 표시 | Codex Claim #16 + 2차 F6 흡수 — `partial_indexed` flag 만으로는 retrieval 시점 사용자/LLM 신호 부족 |
| **D18** (Rev2 신규) | Sprint 1 PLAN gate 정책 | **단일 통합 gate 유지** — Codex 2차 F8 의 1A/1B/1C 3 분할 권고는 거부. 사유: 본 attachment 기능 자체가 신규 (사용자 진입 0), 최종적으로 모든 Sprint 진행 예정이므로 gate 분할은 의사결정 비용만 누적. 단, D14 의 sandbox SQL allowlist guard (R-F3) 가 통합 gate 의 **Critical 통과 조건** 으로 격상되며, gate 통과 전 SQL 실행 path 는 `attachment.execute_sql_on.*` 권한이 어떤 role 에도 부여되지 않은 상태로 ship | Codex 2차 F8 흡수 (부분 거부 — 사용자 명시 결정). 위험 격리는 게이트 분할이 아닌 D14 guard + R-Claim4 grant 최소화 + R-F4 health endpoint 로 충족 |
| **D19** (Rev2 신규) | Derived message 관계 모델 | **별도 join table** `WebAttachmentDerivedMessages(AttachmentId, MessageId, DerivationType, CreatedAt)` 신설 — DerivationType enum: `csv_sample` / `csv_query_result` / `vision_analysis` / `pdf_excerpt` / `rag_citation`. 기존 R1 안의 attachment row 내 JSON 배열은 폐기. share redact (D9) / audit (D12) / fork 시 derivation 보존 / message hard-delete 시 cascade 가 모두 이 join 기반 | Codex 2차 F11 흡수 — many-to-many 관계를 row 내 JSON 으로 두면 fork/share/audit 동기화 비용 폭증 |
| **D20** (Rev2 신규) | MinIO key rotation runbook | **Dual-key + canary + rollback**: (a) old/new key 동시 valid window 24시간, (b) canary object write/read/delete 통과 후 web+worker 컨테이너 순차 재기동, (c) 실패 시 old key 즉시 rollback, (d) rotation 시작/canary/완료/실패를 audit `attachment.storage.key_rotation` 로 기록. minio-init 의 idempotent 보장 + key 폐기는 dual window 종료 후 별 cleanup step | Codex 2차 F9 흡수 — single-key rotation 은 minio-init 의 기존 key 폐기 시점에 전 서비스 다운 위험 |
| **D21** (Rev2 신규) | Pending role attachment 권한 | **metadata-only**: `pending` role 에 `conversation.attachment.read.own` 은 부여하되 bytes download 는 거부. attachment list / title / size / created_at 까지만 노출, `/api/attachments/{id}/content` 는 승인 후 (admin/operator/dba/sales 권한 부여) 통과. audit 에 `attachment.bytes_download.denied_pending` 기록 | Codex 2차 F14 흡수 — 승인 전 계정의 과거 본인 대화 PII bytes 다운로드 정책 명확화 |

본 §2.1 + §2.2 의 D1~D21 결정은 PLAN-APPROVED 게이트의 명시 확정 대상이다 (D1~D17 + Rev2 신규 D18~D21). D6~D21 의 16 결정 중 D7/D8 (변경 없음) 외 14 결정이 Codex 1차/2차 finding 흡수에 의해 갱신·신규 도출되었다.

### 2.3 정합 검토 결과 — 보류 항목

- **Codex Claim #5** (sandbox schema naming collision) 의 Partial Misread 부분 — backend conv_id 는 UUID 강제 (frontend lazy-create sentinel 은 backend 진입 안 함) 이므로 Codex 의 충돌 위험 추정은 약간 과대. 그러나 sha256 hash + mapping table 권고는 robustness 강화로 가치 — D15 의 maintenance path 가 `WebConversationAttachmentsSandboxSchemas` mapping table 을 관리 (§5.1).
- **Codex Claim #18** (Sprint sequencing) 은 결정 영역 — 사용자 현 BRIEFING 유지 결정 (Cycle 0+1 묶음, 사용자 가치 우선). 본 BRIEFING 은 현 sequencing 유지하되 §6.1 Sprint 1 의 **`attachment.execute_sql_on.*` activation 만 별 PLAN-APPROVED gate 분리** (D14 가드 검증 통과 후) — Codex 권고의 일부 부분 흡수.

---

## 3. 시나리오 → Cycle → Sprint 매핑

```
사용자 요청 "ChatGPT 처럼 파일 첨부"
  │
  ├─ 시나리오 A (CSV/Excel ingest)    → Cycle 1 → Sprint 1
  ├─ 시나리오 B (DDL/스키마 KB 보강)  → Cycle 3 → Sprint 3
  ├─ 시나리오 C (Vision 이미지)       → Cycle 2 → Sprint 2
  └─ 시나리오 D (PDF/MD RAG)          → Cycle 4 → Sprint 4

공통 의존 인프라 (모든 시나리오의 prerequisite)
  └─ Cycle 0 (Foundation) → Sprint 1 의 전반부 (Cycle 1 과 함께 ship)
```

---

## 4. 의존성 그래프

```
                       ┌─────────────────────────────────────┐
                       │ Cycle 0 (Foundation, Major→Critical)│
                       │  • MinIO compose service +1         │
                       │  • multipart /api/conversations/    │
                       │    {cid}/attachments                │
                       │  • WebConversationAttachments       │
                       │  • RBAC: conversation.attachment.   │
                       │    upload/read.{own,any} (4 codes)  │
                       │  • Composer paperclip UI            │
                       │  • Audit (dotted lowercase):        │
                       │    attachment.upload / .delete      │
                       │  • D11 consent infra (provider+     │
                       │    class+purpose, revoke path)      │
                       └────────────┬────────────────────────┘
                                    │
                ┌───────────────────┼───────────────────┬─────────────────────┐
                ▼                   ▼                   ▼                     ▼
   ┌─────────────────────┐  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
   │ Cycle 1 (A, Critical)│  │ Cycle 2 (C, Major)│  │ Cycle 3 (B, Major)│  │ Cycle 4 (D, Critical)│
   │  CSV/Excel ingest   │  │  Vision 이미지    │  │  DDL/KB 보강      │  │  PDF/MD RAG       │
   │  • agent_attachment_│  │  • content array  │  │  • admin-only KB  │  │  • PGVector도입   │
   │    <sha256[:32]>    │  │    transient      │  │    ingest pane    │  │  • chunking +     │
   │    schema (D15)     │  │    (DB string)    │  │  • AgentMemory    │  │    retrieval      │
   │  • attachment_maint │  │  • base64 inline  │  │    FactEntries    │  │  • §11.3 정책     │
   │    + writer + clean │  │    only (D13)     │  │    ingest pipe    │  │    이중 소스 확장 │
   │    + reader (D14)   │  │  • vision model   │  │  • §11.3 manual   │  │  • PDF degraded   │
   │  • SQL AST guard    │  │    allowlist      │  │    fact 정책 확장 │  │    state (D17)    │
   │  • XLSX edge cap    │  │  • RBAC: 없음     │  │  • RBAC:          │  │  • PDF 페이지     │
   │  • LLM prompt 메타  │  │    (Cycle 0 read  │  │    attachment.kb. │  │    이미지 base64  │
   │    주입             │  │    재사용)        │  │    write.any      │  │    (Cycle 2 재사용)│
   │  • RBAC: attachment.│  │  • Audit:         │  │  • Audit:         │  │  • RBAC: 없음     │
   │    execute_sql_on.  │  │    attachment.    │  │    attachment.kb. │  │    (Cycle 0 read  │
   │    {own,any}        │  │    vision.invoke  │  │    ingest         │  │    재사용)        │
   │  • Audit:           │  │                   │  │                   │  │  • Audit:         │
   │    attachment.      │  │                   │  │                   │  │    attachment.rag.│
   │    sandbox.sql_exec │  │                   │  │                   │  │    retrieve       │
   └─────────────────────┘  └────────┬──────────┘  └─────────┬─────────┘  └────────┬─────────┘
                                     │                       │                     ▲
                                     └───────────────────────┴─────────────────────┘
                                                       (C → D: content array 재사용,
                                                        B → D: KB 정책 §11.3 정합)
```

화살표 의미: **C → D** = D 의 PDF RAG 가 vision 가능 모델 사용 시 페이지 이미지 base64 inline 위해 Cycle 2 의 content array 전환 (provider adapter 직전 transient) 이 prior 필수. **B → D** = D 의 RAG 도입이 §11.3 "Fact + RAG 이중 소스" 확장을 트리거, Cycle 3 이 §11.3 의 manual fact ingest 경로를 먼저 인정해 두면 Cycle 4 의 정책 변경이 incremental 1 hop.

---

## 5. 아키텍처

### 5.1 데이터 모델 — 전 cycle 통합

```
WebConversationAttachments (★ NEW, Cycle 0)
┌──────────────────────────────────────────────────────────────────┐
│ Id            BIGINT PK AUTO_INCREMENT                            │
│ ConversationId VARCHAR(64) NOT NULL  (FK to AgentCoreConversations)│
│ AccountId     BIGINT NOT NULL        (FK to WebAccounts)          │
│ ObjectKey     VARCHAR(512) NOT NULL  (MinIO key: <cid>/<uuid>/<fn>)│
│ OriginalFilename VARCHAR(255) NOT NULL                            │
│ FilenameHmac  CHAR(64) NOT NULL  ★ tenant-keyed HMAC (D12)        │
│ MimeType      VARCHAR(128) NOT NULL                               │
│ SizeBytes     BIGINT NOT NULL                                     │
│ SizeBucket    VARCHAR(16) NOT NULL  ★ coarse bucket (D12)         │
│ Sha256        CHAR(64) NOT NULL                                   │
│ Kind          ENUM('csv','xlsx','pdf','image','text','other')     │
│               NOT NULL                                            │
│ UploadStatus  ENUM('uploaded','processing','ingested','indexed',  │
│               'partial_indexed','failed','deleted')               │
│               NOT NULL DEFAULT 'uploaded'  ★ D17 — 7 값            │
│ AttachmentDerivedMessages JSON NULL  ★ D9 — message_id 목록       │
│ CreatedAt     DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)   │
│ DeletedAt     DATETIME(6) NULL       (soft delete)                │
│ DeletePending TINYINT NOT NULL DEFAULT 0  ★ D6 — reconciliation   │
│ DeleteReason  ENUM('user','conv_soft','admin_purge','legal')      │
│               NULL  ★ D6 — taxonomy                               │
│ MetaJson      JSON NULL  ★ kind 별 부가 (sheet names, page count, │
│               degraded_reason, ingest_summary)                    │
│                                                                   │
│ INDEX idx_attachments_conversation (ConversationId, DeletedAt)    │
│ INDEX idx_attachments_account (AccountId, CreatedAt)              │
│ INDEX idx_attachments_status (UploadStatus, DeletePending)        │
└──────────────────────────────────────────────────────────────────┘

WebConversationAttachmentsSandboxSchemas (★ NEW, Cycle 1 — D2/D15)
┌──────────────────────────────────────────────────────────────────┐
│ • Codex #5 robustness 권고 흡수                                   │
│ Id                    BIGINT PK                                   │
│ ConversationId        VARCHAR(64) UNIQUE  (1 conv = 1 schema)     │
│ SchemaName            VARCHAR(64) UNIQUE  ★ agent_attachment_     │
│                       <sha256(conversation_id)[:32]>             │
│ CreatedAt             DATETIME(6)                                 │
│ DroppedAt             DATETIME(6) NULL                            │
│ DeletePending         TINYINT NOT NULL DEFAULT 0                  │
└──────────────────────────────────────────────────────────────────┘

agent_attachment_<hash> schema (★ NEW, Cycle 1, D15 maintenance path 생성)
┌──────────────────────────────────────────────────────────────────┐
│ • 첫 CSV/Excel ingest 시점에 _ensure_attachment_schema_via_       │
│   maintainer() 가 attachment_maintainer user 권한으로 CREATE      │
│ • 시트별 1 table: t_<attachment_id>_<sheet_slug>                 │
│ • attachment_writer user 가 per-schema GRANT 후 INSERT/SELECT/    │
│   ALTER, attachment_reader 는 SELECT only                         │
│ • cleanup 은 attachment_cleanup user 가 reconciliation job 으로   │
│   DROP SCHEMA (per-schema grant)                                  │
└──────────────────────────────────────────────────────────────────┘

agent_rag (Postgres, ★ NEW, Cycle 4 — D10 단계적)
┌──────────────────────────────────────────────────────────────────┐
│ Schema: public                                                    │
│ Extension: vector (pgvector)                                      │
│                                                                   │
│ TABLE attachment_chunks                                           │
│  • id            BIGSERIAL PK                                     │
│  • attachment_id BIGINT NOT NULL  (no FK — MySQL 분리)            │
│  • conversation_id VARCHAR(64) NOT NULL                          │
│  • chunk_index  INT NOT NULL                                      │
│  • content      TEXT NOT NULL                                     │
│  • token_count  INT NOT NULL                                      │
│  • embedding    vector(1536) NOT NULL  (text-embedding-3-small)   │
│  • created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()                │
│  • UNIQUE (attachment_id, chunk_index)                            │
│  • INDEX hnsw  (embedding vector_cosine_ops) WITH (m=16, ef_      │
│    construction=64)                                               │
│                                                                   │
│ User: rag_writer (이 DB only, agent_memory DB SELECT 권한 없음)   │
└──────────────────────────────────────────────────────────────────┘

WebAccountConsents (★ NEW, Cycle 0 — D11)
┌──────────────────────────────────────────────────────────────────┐
│ Id          BIGINT PK                                             │
│ AccountId   BIGINT NOT NULL  (FK)                                 │
│ Provider    ENUM('openai','anthropic','local','...')              │
│ DataClass   ENUM('file_text','file_image','file_embedding')       │
│ Purpose     ENUM('inference','indexing')                          │
│ GrantedAt   DATETIME(6) NOT NULL                                  │
│ RevokedAt   DATETIME(6) NULL                                      │
│ UNIQUE (AccountId, Provider, DataClass, Purpose)                  │
└──────────────────────────────────────────────────────────────────┘

WebAuditEvents (★ EXTEND, TASK-0073 인프라 재사용)
ActionCode 추가 (★ Codex #11 — dotted lowercase 통일):
  • attachment.upload              (Cycle 0)
  • attachment.delete              (Cycle 0)
  • attachment.scope.all           (Cycle 1 — "이 대화의 모든 첨부 사용" 토글, D16)
  • attachment.consent.grant       (Cycle 0 — D11)
  • attachment.consent.revoke      (Cycle 0 — D11)
  • attachment.sandbox.sql_exec    (Cycle 1)
  • attachment.sandbox.sql_denied  (Cycle 1 — D14 guard 거부 시)
  • attachment.vision.invoke       (Cycle 2)
  • attachment.kb.ingest           (Cycle 3)
  • attachment.rag.retrieve        (Cycle 4)

★ build_audit_change_json() 의 line 9112 ValueError 처리에 대응 — 각 신규 ActionCode 는
같은 sprint 에서 case 추가 + SECURITY.md §9 sensitive catalog 등재 + tests 필수.
```

### 5.2 RBAC catalog 확장 + 정책 정합 강화

| Cycle | 신규 권한 코드 | GroupName | IsDynamic | 기본 grant |
|-------|---------------|-----------|-----------|------------|
| 0 | `conversation.attachment.upload.own` | conversation | 0 | admin / operator / sales |
| 0 | `conversation.attachment.upload.any` | conversation | 0 | admin only |
| 0 | `conversation.attachment.read.own` | conversation | 0 | admin / operator / sales / pending / dba |
| 0 | `conversation.attachment.read.any` | conversation | 0 | admin only |
| 1 | `attachment.execute_sql_on.own` | attachment | 0 | admin / operator / sales |
| 1 | `attachment.execute_sql_on.any` | attachment | 0 | admin only |
| 3 | `attachment.kb.write.any` | attachment | 0 | admin only |

**Group 정책 강화 (Codex Claim #2 흡수)**:
- 신규 group `attachment` 신설. TASK-0073 의 `audit` group 신설 패턴 정합 — CONVENTIONS.md §10.6 의 7 허용 group (`console / account / role / conversation / product / audit / misc`) 에 `attachment` 추가 (총 8 group).
- 작업 화면 sectioning (`app.js WORK_SCREEN_PERMISSION_SECTIONS`): 운영 권한 묶음에 추가 — `conversation` + `product` + `attachment` 순.
- 관리 콘솔 sectioning (`admin.js ADMIN_PERMISSION_SECTIONS`): 운영 권한 묶음 — `conversation` + `product` + `attachment` 순.
- Label map 추가 — `attachment` = `"첨부"` (양 화면 동일).
- `PERMISSION_GROUP_ORDER` 양쪽 상수에 `attachment` 추가 — `["console", "account", "role", "conversation", "product", "attachment", "audit", "misc"]`.
- CONVENTIONS.md §10.6 의 group 표 + 정합 규칙 갱신을 Sprint 1 의 docs 갱신 묶음에 포함.

**Catchup 정책 강화 (Codex Claim #1 흡수)**:
신규 7 권한 코드 각각에 대해 다음 5 곳을 한 checklist 로 검증한다 — 누락 시 TASK-0063 류 회귀.
1. `PERMISSION_DEFINITIONS` 정적 tuple (`code` + `label` + `description` + `group`)
2. `SEED_ROLE_DEFINITIONS` 각 role 의 permission set (admin / operator / sales)
3. `_ensure_seed_roles()` 의 catchup tuple — admin / operator / sales catchup (line 1498~1573)
4. `_ensure_seed_roles()` 의 **dba role catchup** (line 1575~) — dba 는 SEED_ROLE_DEFINITIONS 부재, 수동 INSERT 된 경우 별도 grant 필수
5. `_ensure_seed_roles()` 의 **pending role catchup** (line 1600~) — pending 도 별 catchup
6. FE 상수 — `app.js` label map + description map + `WORK_SCREEN_PERMISSION_SECTIONS`, `admin.js` `ADMIN_PERMISSION_SECTIONS` + `PERMISSION_GROUP_ORDER`

**IsDynamic=0 권한의 catalog hydrate 정책 (Codex Claim #3 흡수)**:
- `_resolve_permission_catalog(conn=None)` 은 정적 `PERMISSION_DEFINITIONS` 가 source-of-truth, conn 주어지면 `WebPermissions.IsDynamic=1` row 만 union.
- 본 cycle 의 7 코드는 모두 IsDynamic=0 → **정적 `PERMISSION_DEFINITIONS` 추가 필수**. DB 만 INSERT 하면 런타임 permission map 에 안 잡힘.
- DB hydrate (`_ensure_permission_catalog`) 는 정적 정의를 반영하는 보조 단계로만 둠.

`pending` role 은 `.read.own` 만. `dba` role 은 `.read.own` 만 (운영 모니터링 자격).

**총 7 코드 신설**. 모든 기존 role 에 idempotent backfill — 위 6 checklist 검증 통과 시 PR review 통과.

### 5.3 Storage 흐름 (S3-compat MinIO, D13 적용)

```
[Browser]
  │
  │ POST /api/conversations/{cid}/attachments (multipart/form-data)
  │      Cookie: session
  ▼
[FastAPI app.py]
  │
  ├── _require_account → conversation.attachment.upload.{own,any} guard
  ├── MIME allowlist 검증 (D7) + magic bytes 확인 (Codex #14)
  ├── Size cap 검증 (D8: per-file / per-conv / per-account)
  ├── SHA256 계산 (stream, dedupe 가능)
  ├── object_key = f"{cid}/{uuid4}/{original_filename}"
  ├── MinIO put_object (boto3 S3 client, bucket=agent-attachments)
  ├── INSERT WebConversationAttachments (UploadStatus='uploaded',
  │       FilenameHmac, SizeBucket — D12)
  ├── audit attachment.upload (HMAC + ext bucket + size bucket — D12)
  └── return { id, kind, signed_url (TTL 900s, ★ 사내망 frontend 전용) }

[Cycle 1 트리거 - kind=csv/xlsx]
  └── async ingest worker (attachment_writer + attachment_maintainer)
        → status='processing' → attachment_maintainer 가 schema CREATE
        → attachment_writer 가 table per sheet → status='ingested'
        → MetaJson.sheets + ingest_summary 갱신
        (XLSX edge: row/col/cell/sheet count cap, formula stripping —
         Codex #14 §6.1)

[Cycle 4 트리거 - kind=pdf/text]
  └── async chunking worker → status='processing'
        → pypdf/pdfplumber 추출 → 텍스트 충분: chunking → embedding → pgvector
          → status='indexed'
        → 텍스트 부족 (scanned/encrypted/no-text): status='partial_indexed'
          + MetaJson.degraded_reason — Codex #16

[★ D13 — LLM 외부 송신 시점 (NOT upload 시점)]
  /api/ask, vision invoke, embedding 등 외부 송신 직전:
    1. D11 consent 확인 (provider+data_class+purpose). 없으면 modal flow.
    2. 서버가 MinIO 에서 bytes read (signed URL 외부 송신 금지)
    3. provider 별 변환:
        • OpenAI Vision: base64 inline (data URL)
        • OpenAI Assistants Files API: multipart upload to /v1/files
        • Anthropic Vision: base64 inline
        • Anthropic Files API: multipart upload to /v1/files
    4. size / token / cost cap 적용 (별도 한도)
    5. audit attachment.vision.invoke / attachment.rag.retrieve 등 dispatch
```

MinIO 자체는 compose internal network 만 노출. 외부는 항상 web FastAPI 를 통해 signed URL re-issue (사내망 다운로드 only). **외부 LLM provider 에는 signed URL 송신 금지** — Codex Claim #8 (외부 LLM 망에서 사내 minio:9000 접근 불가).

### 5.4 API 엔드포인트 매트릭스

| Cycle | Method | Path | Auth | Permission | 응답 |
|-------|--------|------|------|------------|------|
| 0 | POST | `/api/conversations/{cid}/attachments` | session | `conversation.attachment.upload.{own,any}` | `{ id, kind, signed_url (사내망), size, sha256, status }` |
| 0 | GET | `/api/conversations/{cid}/attachments` | session | `conversation.attachment.read.{own,any}` | `[ { id, kind, original_filename, size, status, created_at, degraded_reason? } ]` |
| 0 | GET | `/api/attachments/{id}` | session | `conversation.attachment.read.{own,any}` | signed URL re-issue (사내망) |
| 0 | DELETE | `/api/attachments/{id}` | session | `conversation.attachment.upload.{own,any}` (uploader = soft-delete) | `{ ok: true, delete_reason: 'user' }` (D6) |
| 0 | POST | `/api/account/consents` | session | (own only) | `{ id, provider, data_class, purpose, granted_at }` (D11) |
| 0 | DELETE | `/api/account/consents/{id}` | session | (own only) | `{ revoked_at }` (D11) |
| 1 | (변경) POST | `/api/ask` (body 확장) | session | `conversation.ask` + 첨부 사용 시 `attachment.execute_sql_on.{own,any}` | 기존 응답 + meta.sandbox_used + meta.attachment_ids_used |
| 3 | POST | `/api/admin/attachments/kb-ingest` | session | `attachment.kb.write.any` | `{ fact_entry_id, scope_key }` |

`/api/ask` body 확장 (Cycle 1):
```jsonc
{
  "message": "...",
  "model": "...",
  "conversation_id": "...",
  "api_key_cipher": "...",
  "api_key_passphrase": "...",
  "product_mode": "...",
  "product_id": ...,
  "lazy_create": ...,
  "attachment_ids": [123, 124],  // ★ D16 — selected only, frontend 가 항상 명시
  "attachment_scope_all": false  // ★ D16 — true 시 conv 전체 (별 audit + modal)
}
```

**D16 적용**: `attachment_ids` 가 명시되지 않으면 빈 list — 과거 첨부 자동 포함 안 함. frontend 의 composer attachment pill 이 default selected (사용자가 deselect 가능). `attachment_scope_all=true` 토글 시 conv 전체 ingested 첨부 사용 + audit `attachment.scope.all` 기록 + frontend modal 경고.

### 5.5 LLM 입력 흐름 — compose_system_prompt 확장 + content array 정책

현재 (TASK-0014 / TASK-0058 / TASK-0060):
```
[Product 시스템 프롬프트 (활성 product 만)]
[Role 시스템 프롬프트]
[Account scope 시스템 프롬프트]
[User 메시지 누적]
```

Cycle 1 (A CSV) 이후:
```
[Product 시스템 프롬프트]
[Role 시스템 프롬프트]
[Account scope 시스템 프롬프트]
[★ NEW "현재 첨부" 섹션 — kind 별 메타]
  • CSV/xlsx: 시트명, 컬럼명+타입, 행수, sample 5 행, 접근 schema (sha256 hash 기반)
  • PDF/text: 파일명, 페이지수, RAG top-K excerpt (Cycle 4 시점)
  • Image: 파일명, dimensions, "vision input as base64 inline" 안내 (Cycle 2 시점)
[User 메시지 누적]
```

**Content array 정책 (Codex Claim #12 흡수)**:
- **DB 저장 메시지는 기존 string content contract 유지** (`AgentMemoryMessages.content` 그대로 TEXT). TASK-0058 share.js renderMessage + TASK-0014 prompt 조립이 string 가정에 의존하기 때문.
- **Provider adapter 직전 transient content-array 변환** — `feature-0002-agent-core/src/modules/llm_invoke.py` 안에서 `messages` → `messages_for_provider()` 호출 시 transient 변환:
  ```jsonc
  // Before transient (DB string contract)
  { "role": "user", "content": "사용자 텍스트" }

  // After transient (provider 호출 직전 only)
  { "role": "user", "content": [
      { "type": "text", "text": "사용자 텍스트" },
      { "type": "image_url", "image_url": { "url": "data:image/png;base64,..." } }
        // ★ D13 — base64 inline only, signed URL 금지
    ]
  }
  ```
- 저장 포맷 변경이 필요한 future cycle (예: 대화 내 multi-image 의 user message 별 표현) 에는 별 migration + share/search/render compatibility tests 선행 — 본 cycle 의 D 결정.

Cycle 2 (C Vision) 시점에 transient 변환 활성. Cycle 4 (D RAG) 의 PDF 페이지 이미지 inline 시 동일 인프라 재사용.

### 5.6 Composer UI

```
┌─────────────────────────────────────────────────┐
│ [📎 attach] [Attachment pills row]              │ ★ NEW
│   📎 sales_q1.xlsx (3 시트) ✕    [✓ 사용]      │ pill 마다 선택 토글
│   📎 error.png ✕                  [✓ 사용]     │ default = selected
│   📎 manual.pdf (12p, 인덱싱 중) ✕ [✓ 사용]    │
│   [⚙ 이 대화의 모든 첨부 사용 toggle]            │ D16 — 별 audit
├─────────────────────────────────────────────────┤
│ [textarea — promptInput]                        │ rows="1" auto-height
│                                                 │
├─────────────────────────────────────────────────┤
│ [product chip] (기존 — 변경 없음)        [send] │
└─────────────────────────────────────────────────┘
```

ChatGPT 식 paperclip + drag-drop + thumbnail. 본 프로젝트 §8.1 (feature-0003 AGENTS.md) 의 "외부 스크롤 금지 / inline 카드 적층 금지" 정책 정합 — pill 라인은 composer 위 single row, 8 개 초과 시 horizontal scroll. 사용자가 pill 별 deselect 시 그 첨부는 attachment_ids 에서 제외 (D16).

---

## 6. Sprint 1~4 plan

### 6.1 Sprint 1 — Cycle 0 (Foundation) + Cycle 1 (A: CSV ingest) — Critical, 3~3.5 주

**Risk grade**: Critical §12.3.

**Pre-flight (2~3 일)**:
- ADR-0019 (MinIO 도입) + ADR-0020 (sandbox schema 패턴 + D15 maintenance path 분리) + ADR-0021 (PGVector 사전 선언 — Sprint 4 prerequisite, D10 단계적 정책) `docs/DECISIONS.md` 등재
- `docker-compose.yml` `minio` service 추가 + `minio-init` one-shot service (★ Codex #20):
  - `minio`: api 9000 / console 9001, volume `../artifacts/minio-data:/data`, healthcheck
  - `minio-init`: 부트스트랩 1 회 — bucket 생성 idempotent, lifecycle policy 적용 (delete_reason 별 retention), root credential 비활성화 + app 전용 access key 생성 / rotation 정책
- `.env.example` 14 변수 추가:
  - `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` (bootstrap 전용)
  - `MINIO_APP_ACCESS_KEY`, `MINIO_APP_SECRET_KEY` (app 전용 — rotation 대상)
  - `MINIO_ENDPOINT=minio:9000`, `MINIO_BUCKET=agent-attachments`
  - `MINIO_SIGNED_URL_TTL_SEC=900`
  - `ATTACHMENT_MAX_BYTES_PER_FILE=26214400`, `ATTACHMENT_MAX_BYTES_PER_CONV=104857600`, `ATTACHMENT_MAX_BYTES_PER_ACCOUNT=1073741824`
  - `ATTACHMENT_AUDIT_HMAC_KEY` (D12 tenant-keyed HMAC)
  - `SANDBOX_SQL_MAX_ROWS=50000`, `SANDBOX_SQL_STMT_TIMEOUT_SEC=30` (D14)
- `feature-0001-platform-runtime` ANCHOR §1 갱신 (compose service 5 → 7: minio + minio-init)

**Cycle 0 (Foundation) — 변경 면적**:
- `_ensure_web_conversation_attachments_schema(conn)` helper (slow+fast path)
- `_ensure_web_account_consents_schema(conn)` helper (D11)
- `_ensure_attachment_permissions(conn)` — RBAC 4 코드 hydrate (TASK-0058 패턴)
- §5.2 의 6 checklist 준수 — `PERMISSION_DEFINITIONS` + `SEED_ROLE_DEFINITIONS` + admin/operator/sales catchup + dba catchup + pending catchup + FE 상수
- 신규 endpoint 6 개 (§5.4 Cycle 0): POST/GET/GET-by-id/DELETE attachment + POST/DELETE consent
- `_account_can_access_attachment` helper (TASK-0058 의 `_account_can_access_conversation` 변종)
- MinIO 클라이언트 wrapper (`feature-0003-agent-web-ui/src/modules/storage_minio.py`) — boto3 + retry + signed URL helper + backup smoke test
- composer UI 갱신: paperclip + hidden file input + drag-drop + attachment pills + selected toggle (D16) + "모든 첨부 사용" toggle (D16)
- D11 consent modal flow — 첫 외부 송신 직전 노출 (provider+data_class+purpose 별), revoke 화면 (drawer 새 탭)
- audit ActionCode 4 개 추가: `attachment.upload` / `attachment.delete` / `attachment.consent.grant` / `attachment.consent.revoke`
- `build_audit_change_json` 의 case 4 개 추가 + SECURITY.md §9 sensitive catalog 등재 + tests
- D9 share builder redact — `WebMessages.MetaJson.attachment_derived` flag + share builder 가 해당 메시지 redact 또는 share 생성 시 사용자 경고 modal
- `PERMISSION_GROUP_ORDER` 양쪽 상수에 `attachment` 추가

**Cycle 1 (A: CSV ingest) — 변경 면적**:
- `_ensure_attachment_schema_via_maintainer(conn, conv_id)` — D15 maintenance path. sha256 hash 기반 schema name 결정 (`WebConversationAttachmentsSandboxSchemas` mapping table)
- `attachment_maintainer` MySQL user — CREATE/DROP SCHEMA on `agent_attachment_*` (와일드카드 grant 사용하되 maintainer 전용)
- `attachment_writer` MySQL user — per-schema GRANT (생성 후 `GRANT ALL ON agent_attachment_<hash>.* TO 'attachment_writer'@'%'`) + 정본 schema SELECT-only
- `attachment_reader` MySQL user — sandbox SELECT only + 정본 SELECT only (D14 의 SQL 실행 user)
- `attachment_cleanup` MySQL user — DROP SCHEMA only on per-schema grant (reconciliation worker 전용)
- `feature-0002-agent-core/src/modules/sandbox_ingest.py` 신규 — XLSX/CSV ingest pipeline:
  - XLSX: openpyxl `read_only=True` + sharedStrings cap (1M) + cell/row/col count cap + formula stripping (or literalization, `data_only=True`)
  - CSV: encoding detection (chardet) + delimiter detection + numeric/date locale policy
  - Worker timeout (5 분) + memory limit (500 MB)
- `feature-0002-agent-core/src/modules/sql_guard.py` 신규 (D14) — sqlglot AST parser, allowlist SELECT-only (CTE 가능), session variables / DDL / DML / FILE / LOCK / CALL / multi-statement / INTO OUTFILE / USE 차단. failure → `attachment.sandbox.sql_denied` audit
- `compose_system_prompt` 의 `_build_attachment_context_section` builder (Cycle 1 시점은 CSV/xlsx 메타만; Cycle 2/4 시점에 image/pdf 분기 추가)
- `/api/ask` body `attachment_ids` 처리 (D16: 명시 안 되면 빈 list) + sandbox SQL 실행 시 `attachment_reader` user 로 별 connection
- RBAC 2 코드 추가 (`attachment.execute_sql_on.own/.any`) — §5.2 6 checklist 준수
- audit `attachment.sandbox.sql_exec` / `attachment.sandbox.sql_denied` / `attachment.scope.all` dispatch
- **Delete reconciliation worker** (D6) — `feature-0002-agent-core` 의 `modules/attachment_reconciliation.py`:
  - 10 분 cycle. `WebConversationAttachments.DeletePending=1` 인 row 처리
  - delete_reason 별 SLA:
    - `user`: MinIO 객체 lifecycle policy 30 일 후 purge, DB row 30 일 후 hard-delete
    - `conv_soft`: 동일 SLA (conversation soft-delete cascade)
    - `admin_purge`: MinIO 즉시 + DB 즉시 hard-delete + sandbox schema 즉시 DROP
    - `legal`: MinIO 즉시 + DB hard-delete + sandbox schema DROP + audit `attachment.legal.erase` (GDPR-style)
  - reconciliation idempotent — MinIO / DB / sandbox / pgvector 모두 스캔, orphan 정리
- `/api/admin/databases/available` (TASK-0051) 응답에서 `agent_attachment_*` schema 자동 제외

**Sprint 1 의 별 PLAN-APPROVED gate** (Codex Claim #18 일부 흡수):
- `attachment.execute_sql_on.*` 권한 activation 은 D14 SQL guard 검증 통과 후 별 confirmation. Cycle 0 의 upload/read 만 먼저 ship 가능. SQL 실행 enable 시점에 사용자에게 `_ensure_seed_catchup` 의 일괄 grant 명시 confirm.

**문서 갱신 (Sprint 1 끝)**:
- `feature-0003 FUNCTION.md` REQ-20260521-0001 (AC-0061~AC-0080 — 20 AC, D6-D17 반영; Rev2 흡수로 AC 항목은 Sprint 1 진입 직전 D18~D21 반영 갱신)
- `feature-0002 FUNCTION.md` Cycle 1 의 ingest pipeline + sql_guard + reconciliation
- `feature-0003 MODIFY.md` CHG-20260520-XXXX 묶음
- `feature-0003 REVIEW.md` REV-20260520-XXXX (Codex finding 흡수 trace + REV-20260520-0001 본 BRIEFING)
- `feature-0003 TASK.md` TASK-0094 Implementation Plan 등재 + 7 Completion Checklist
- `docs/STATUS.md` feature-0003 row 갱신 + TASK-0094 header entry
- `docs/SECURITY.md` §3 (외부 LLM 송신 + PII) + §7.2 (외부 배포 보완 — 첨부 첨가) + **§9 신규** (D12 audit masking 정책: HMAC + bucket + AST normalize)
- `docs/CONVENTIONS.md` §10.6 group 표 갱신 (audit + attachment 8 group)
- `docs/ARCHITECTURE.md` §4 (feature-0003 + 0002 책임) + §6 (MinIO 의존성)
- `docs/LEARNINGS.md` quirks 묶음:
  - "MinIO signed URL 외부 LLM 송신 불가 — 사내 IP 만 접근 가능. base64 / files API 만 outbound 경로"
  - "MySQL GRANT pattern `_` `%` 와일드카드 — schema 명 prefix 정확 매칭 필수 시 maintenance user 분리 패턴"
  - "RBAC 신규 코드 시 6 checklist (PERMISSION_DEFINITIONS / SEED_ROLE_DEFINITIONS / admin·operator·sales catchup / dba catchup / pending catchup / FE 상수) 모두 갱신"

**검증 (Sprint 1)**:
- `bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui`
- HTTP smoke (TASK-0052 / TASK-0073 패턴): 6 endpoint × {own/any/anonymous} matrix = 18 case + sandbox SQL 5 case + consent flow 4 case = 27 case
- 첨부 lifecycle e2e: upload → list → ingest 완료 → /api/ask 가 sample 5 행 활용 → soft-delete → reconciliation 30 일 후 hard-delete
- Negative tests:
  - 26 MB+1 byte 거부, conv 100 MB cap, account 1 GB cap
  - MIME spoof (magic bytes 검증)
  - XLSX edge: sharedStrings 1M 초과, row 1M 초과, formula 포함, encoding 깨짐 (Codex #14)
  - CSV: encoding (UTF-8 / EUC-KR / CP949), delimiter (`,` / `;` / `\t`), date/decimal locale
  - SQL guard: multi-statement, INTO OUTFILE, USE, comment 우회, CTE 가능, DML 거부, FILE/LOCK 거부 (Codex #15)
  - Conv hard-delete 중 ingest 진행 → reconciliation 이 race 안 발생 확인 (Codex #6)
  - share view 에서 첨부 derived assistant message redact 확인 (Codex #19)
- MinIO restart 시 bucket / lifecycle policy / app key 유지 확인 (Codex #20)

### 6.2 Sprint 2 — Cycle 2 (C: Vision) — Major, 1~1.5 주

**Risk grade**: Major §12.3.

**변경 면적**:
- `feature-0002-agent-core/src/modules/llm_invoke.py` 의 `messages_for_provider()` — provider 직전 transient content-array 변환 (DB string contract 유지 — §5.5)
- `_is_allowed_api_model` 의 vision 모델 화이트리스트: `gpt-4o`, `gpt-4o-mini`, `claude-3-5-sonnet-*`, `claude-sonnet-4-*`. API Vault drawer 의 model picker label 에 `(Vision)` 표기
- `_build_attachment_context_section` 의 kind=image 분기 — vision 가능 모델 사용 시 image 의 MinIO bytes read (D13: signed URL 금지) → base64 inline (data URL). vision 불가 모델 사용 시 첨부 무시 + toast
- D11 consent — `provider=<picked>` + `data_class=file_image` + `purpose=inference` 첫 송신 직전 modal
- audit `attachment.vision.invoke` dispatch — token usage + 첨부 id list + provider
- `share.html` 의 message rendering 은 D9 redact 정책 그대로 — attachment_derived 메시지 가시성 정책 적용

### 6.3 Sprint 3 — Cycle 3 (B: DDL/KB 보강) — Major, 1 주

**Risk grade**: Major §12.3.

**변경 면적**:
- `admin.html` "스키마 정의서 KB 등록" pane 신규 — Cycle 0 첨부 list 에서 kind=text/markdown 또는 `.sql` extension 표기된 항목 선택 → preview → ScopeKey 입력 → ingest 버튼
- 신규 endpoint POST `/api/admin/attachments/kb-ingest` — body `{ attachment_id, scope_key, source_type='manual', weight=0.9 }`. 응답 `{ fact_entry_id, scope_key }`
- `feature-0002-agent-core/src/modules/kb_ingest.py` 신규 — 본문 → `AgentMemoryFactEntries` row INSERT. ScopeKey 충돌 시 기존 row 의 `status='superseded'` + 새 row INSERT
- RBAC `attachment.kb.write.any` 1 코드 — §5.2 6 checklist 준수, admin only
- audit `attachment.kb.ingest` dispatch
- `repo/AGENTS.md` §11.3 의 명시적 확장 — "manual ingest fact 의 SourceType='manual', Weight=0.9 (자동 수집보다 우선)"

### 6.4 Sprint 4 — Cycle 4 (D: PDF/MD RAG) — Critical, 3~4 주

**Risk grade**: Critical §12.3.

**Pre-flight**:
- ADR-0021 (PGVector 도입) 본격 — D10 단계적 정책 명시 (dev = 동일 컨테이너 / prod = PLAN gate 에서 재검토)
- agent_memory 별 cycle 의 plan 완료 후 동일 PGVector 컨테이너 + DB 분리 정책 합의
- `docker-compose.yml` `postgres` service 추가 (`pgvector/pgvector:pg16`)
- `.env.example` 6 변수: `PGVECTOR_HOST=postgres`, `PGVECTOR_PORT=5432`, `PGVECTOR_USER=rag_writer`, `PGVECTOR_PASSWORD=...`, `PGVECTOR_DB=agent_rag`, `RAG_EMBEDDING_MODEL=text-embedding-3-small`, `RAG_CHUNK_SIZE=1000`, `RAG_CHUNK_OVERLAP=200`, `RAG_TOP_K=5`

**변경 면적**:
- PostgreSQL 클라이언트 (`feature-0002-agent-core/src/modules/storage_pgvector.py`) — psycopg + pgvector-python
- `attachment_chunks` 테이블 부트스트랩 — `_ensure_pgvector_schema(conn_pg)` (extension 설치 포함)
- `modules/rag_chunking.py` — PDF (`pypdf` 또는 `pdfplumber`) / text / markdown 추출 → LangChain `RecursiveCharacterTextSplitter`. **degraded state 처리 (D17)** — scanned PDF (no text layer) / encrypted PDF / no-text / 200+ page cap / table-heavy → `partial_indexed` + `MetaJson.degraded_reason`
- `modules/rag_embed.py` — OpenAI / Anthropic embedding API wrapper. D11 consent (`data_class=file_embedding`, `purpose=indexing`) 첫 송신 직전 확인
- `modules/rag_retrieve.py` — query embedding → top-K cosine search → MMR re-rank 옵션
- `compose_system_prompt` 의 "현재 첨부" 섹션에 kind=pdf/text 의 RAG top-K excerpt 채우기. degraded 상태면 경고 표시 ("일부 페이지만 인덱싱됨, LLM 응답이 부정확할 수 있음")
- PDF 페이지 이미지 inline — Cycle 2 의 content array transient 변환 재사용 (vision 가능 모델 + PDF kind + 페이지 이미지 첫 1~2 장 base64)
- audit `attachment.rag.retrieve` dispatch — query HMAC + top-K chunk id list
- `repo/AGENTS.md` §11.3 본격 확장 — "Fact KB (MySQL) + RAG chunk store (Postgres pgvector) 이중 소스, fact 가 검증 정본·RAG 가 보강" 정책 정식화

---

## 7. Sprint 순서 — 권고와 근거

| Sprint | Cycle | 사용자 가치 출시 | 위험 | 의존 |
|--------|-------|------------------|------|------|
| 1 | 0 + 1 (A) | **첫 출시 — CSV ingest** | Critical | 없음 (foundation). **D14 SQL guard 검증 통과 후 attachment.execute_sql_on.* 별 PLAN-APPROVED** |
| 2 | 2 (C) | Vision 이미지 분석 | Major | Cycle 0 의 read endpoint + D11 consent infra |
| 3 | 3 (B) | admin KB curation | Major | Cycle 0 |
| 4 | 4 (D) | PDF/MD RAG | Critical | Cycle 0 + 2 + 3 + (외부) agent_memory PGVector |

**Sprint 1 묶음 근거** — Codex Claim #18 의 위험 격리 권고에도 불구하고 사용자 가치 우선 결정. 단 Codex 권고의 일부 (sandbox SQL activation 분리) 는 흡수 — D14 guard 검증 후 별 PLAN-APPROVED.

**Sprint 2 (C) 가 B 보다 먼저인 이유** — Cycle 2 의 content array transient 변환이 Cycle 4 (D) 의 PDF 페이지 이미지 base64 inline 의 prerequisite. B (admin-only KB) 는 일반 사용자 가치 비-critical.

총 8 ~ 10 주. 각 sprint 사이에 사용자 dogfooding + Codex follow-up review + §7.1 Critical 승인 게이트.

---

## 8. SECURITY 영향 (SECURITY.md §3 5 항목 점검 + 신규 §9)

| 항목 | 본 cycle 영향 | 대응 |
|------|---------------|------|
| 인증/인가 | RBAC catalog 7 코드 신설 + group `attachment` 신설 | §5.2 6 checklist + CONVENTIONS.md §10.6 갱신 |
| 파괴적 데이터 | sandbox schema 동일 cluster, attachment_maintainer/writer/reader/cleanup 4 user 분리 (D14/D15) | per-schema grant, 와일드카드 금지, SQL AST guard |
| 외부 공개 범위 | 첨부 데이터가 LLM provider 로 송신 — bytes 직접 (D13), signed URL 금지 | D11 consent (provider × data class × purpose × revoke), audit, size/token cap |
| 개인정보 처리 | 사용자가 PII 포함 파일 업로드 가능. audit 마스킹 강화 (D12) | HMAC + ext bucket + size bucket + AST normalize. raw filename/SQL 기본 금지. share view 의 derived content redact (D9) |
| 비용 상승 | vision 단가 ~10x, embedding + retrieval 비용 | model 화이트리스트 + size cap (D8) + RAG chunk 수 상한 |

**Outbound LLM data flow risk (Codex #8, #9, #13 통합)**:
- signed URL 외부 송신 금지 → server-side bytes read + provider 별 base64 / files API (D13)
- D11 consent: account-level global → provider+data class+purpose 별, revoke path 추가, 첫-trigger 는 첫 외부 송신 직전
- attachment_ids 기본값 = selected only (D16) → minimum exposure

**Share view 정책 (D9 + Codex #19)**:
- 첨부 객체 hide (이미 R7 적용)
- attachment-derived assistant message (CSV sample / PDF excerpt / 이미지 분석) 은 `WebMessages.MetaJson.attachment_derived: true` flag → share builder 가 redact 또는 share 생성 시 사용자 경고 modal + 명시 토글

**SECURITY.md §9 신규 — Audit masking 정책 (D12)**:
- `WebAuditEvents.ChangeJson` 의 mask 정책 — D12 표준 (HMAC + bucket + AST normalize) 명시
- raw filename / raw SQL / raw query 의 기본 금지
- sandbox SQL 은 sqlglot normalized form + action category + referenced schema/table list + row count + denied reason 만

**Anonymous endpoint 정책 (SECURITY.md §7) 변경 없음**: 첨부는 anonymous share view 에서 항상 hide.

---

## 9. Test plan

### 9.1 Sprint 1 (P0 Critical)

| ID | Case | 기대 결과 |
|---|------|----------|
| T1.1 | operator → 자기 conv 에 CSV upload | 200 + signed URL (사내망) |
| T1.2 | operator → 타인 conv 에 CSV upload | 403 |
| T1.3 | admin → 타인 conv 에 CSV upload | 200 |
| T1.4 | pending → 자기 conv 에 CSV upload | 403 |
| T1.5 | anonymous → POST attachments | 401 |
| T1.6 | operator → 자기 conv 첨부 다운로드 | 200 + signed URL re-issue |
| T1.7 | operator → 타인 conv 첨부 다운로드 | 404 (TASK-0058 R6 패턴) |
| T1.8 | 26 MB+1 byte 거부 | 413 |
| T1.9 | conv 100 MB 초과 | 413 |
| T1.10 | account 1 GB 초과 | 413 |
| T1.11 | MIME spoof (zip → image/png header) | 400 |
| T1.12 | XLSX sharedStrings 1M 초과 | 413 or 400 |
| T1.13 | XLSX row 1M 초과 | 413 or worker timeout → status='failed' |
| T1.14 | CSV EUC-KR encoding | 정상 ingest, 컬럼명 한글 보존 |
| T1.15 | CSV delimiter `;` | 정상 ingest |
| T1.16 | CSV formula 포함 | formula stripping 후 literalization |
| T1.17 | conv soft-delete → 첨부 download | 404 |
| T1.18 | conv hard-delete 중 ingest 진행 → reconciliation worker 정상 cleanup | sandbox schema drop, MinIO purge (lifecycle 30일) |
| T1.19 | operator → CSV ingest 후 /api/ask 의 sandbox 활용 | LLM 응답에 컬럼 / 행 분석 포함 |
| T1.20 | LLM 작성 SQL: 정본 schema WRITE 시도 | 403 (attachment_reader user 권한 없음 + AST guard 차단) |
| T1.21 | LLM 작성 SQL: multi-statement (`SELECT 1; DROP TABLE...`) | AST guard 차단 + audit `attachment.sandbox.sql_denied` |
| T1.22 | LLM 작성 SQL: SELECT INTO OUTFILE | AST guard 차단 |
| T1.23 | LLM 작성 SQL: CTE (정합 SELECT) | 통과 |
| T1.24 | LLM 작성 SQL: comment 우회 (`/* */ DROP`) | AST guard 차단 |
| T1.25 | attachment_ids 명시 안 함 → 빈 list 처리 | LLM prompt 의 "현재 첨부" 섹션 비어있음 |
| T1.26 | attachment_scope_all=true | 전체 첨부 포함 + audit `attachment.scope.all` 기록 |
| T1.27 | share view 에서 attachment_derived 메시지 | redact 또는 경고 |
| T1.28 | audit log 에 ATTACHMENT_UPLOAD / SANDBOX_SQL_EXEC | HMAC + size bucket + AST normalize 만, raw 금지 |
| T1.29 | D11 consent 미부여 → /api/ask 첨부 사용 | consent modal trigger, 답변 차단 |
| T1.30 | D11 consent revoke → 재요청 | modal 재노출 + 답변 차단 |
| T1.31 | MinIO restart → bucket / lifecycle / app key 유지 | restart 후 정상 동작 |

### 9.2 Sprint 2 (P0 Critical for Major)

| ID | Case | 기대 결과 |
|---|------|----------|
| T2.1 | vision 가능 모델 + image 첨부 + consent ok | base64 inline LLM 송신, 이미지 분석 응답 |
| T2.2 | vision 불가 모델 + image 첨부 | 첨부 무시 + toast |
| T2.3 | content array transient 변환 후 기존 text-only 메시지 | DB 저장은 string 유지, share view 정상 |
| T2.4 | signed URL 외부 LLM 송신 시도 | 차단 (D13) — base64 만 허용 |

### 9.3 Sprint 3 (P0 Critical for Major)

| ID | Case | 기대 결과 |
|---|------|----------|
| T3.1 | admin → KB ingest 정상 | fact_entry_id 응답 + `make ask` 가 fact 참조 |
| T3.2 | operator → KB ingest 시도 | 403 |
| T3.3 | 동일 ScopeKey 재 ingest | 기존 row status='superseded' + 새 row |

### 9.4 Sprint 4 (P0 Critical)

| ID | Case | 기대 결과 |
|---|------|----------|
| T4.1 | 정상 PDF upload → 비동기 chunking → status='indexed' | PGVector attachment_chunks 다수 |
| T4.2 | scanned PDF (no text layer) | status='partial_indexed' + degraded_reason='no_text_layer' |
| T4.3 | encrypted PDF | status='failed' + reason='encrypted' |
| T4.4 | 250 페이지 PDF (cap 200) | status='partial_indexed' + degraded_reason='page_cap' |
| T4.5 | `/api/ask` 가 query embedding → top-K=5 chunks 만 prompt | LLM 응답이 관련 chunk 근거로 작성 |
| T4.6 | fact KB + RAG chunk 공존 — fact 우선 | meta 에 KB sources + RAG sources 분리 |
| T4.7 | rag_writer user 의 agent_memory DB 접근 | 권한 없음 |
| T4.8 | PDF 페이지 이미지 inline | vision 가능 모델 사용 시 base64 page snapshot 포함 |

---

## 10. NOT in scope (본 cycle 명시 제외)

- **D 의 vector store 변경** (PGVector → 다른 vector DB). 별 ADR.
- **local LLM gateway 로 첨부 routing**. 외부 Local LLM 계약이 첨부 multimodal 미지원 — D11 consent + D13 outbound 송신 정책으로 우회.
- **첨부 OCR / 표 추출**. Cycle 4 의 PDF 는 native text 추출만 — scanned PDF 는 `partial_indexed` degraded state. OCR 는 별 cycle.
- **첨부 공유 (cross-account)**. 첨부는 conversation-owner 만. share viewer fork 시 새 conv 의 attachment 로 복제 안 함.
- **첨부 검색 (TASK-0072 search modal)**. 첨부 메타 검색 별 cycle.
- **MinIO 외부 노출 / S3 직접 client upload (presigned PUT)**. 본 cycle 은 web FastAPI 경유만.
- **첨부 버전 관리**. 첨부는 immutable.
- **외부 LLM provider 추가** (Azure OpenAI, Google Gemini 등). 현 OpenAI + Anthropic + 외부 Local LLM gateway 만.

---

## 11. ANCHOR 정합 확인 (§18.3)

- **feature-0003-agent-web-ui ANCHOR §1**: "Web entry point 의 서버 측 로직 전부, Product → Role → Account 3 계층 System Prompt 조립" — 첨부 endpoint·storage·RBAC 자연 귀속. **충돌 없음**.
- **feature-0003 ANCHOR §3**: "관리자가 새 product 권한 부여 시 whitelist bypass 정책" — 본 cycle RBAC 신설 코드도 동일 catalog 흐름. **충돌 없음**.
- **feature-0002-agent-core ANCHOR §1**: "agent 의 핵심 루프 — 요청 수신 → SQL 작성 → 실행 → memory 반영" — Cycle 1 의 sandbox SQL 실행은 핵심 루프 안의 신규 분기. **충돌 없음, 루프 확장**.
- **feature-0002 ANCHOR §3 invariant**: "fact 우선 복구" — Cycle 4 RAG chunk 는 "RAG 4 종 중 하나" 자리매김. fact 우선 순서 보존. **충돌 없음, invariant 강화**.

**작업 시작 차단 조건 없음**. §7.1 Critical 승인 게이트만 통과하면 진행.

---

## 12. 외부 의존 — agent_memory 별 cycle 과의 sequencing

별 세션에서 `agent_memory` (MySQL → Postgres pgvector) 이전 작업의 plan 이 진행 중 (worktree `ai/claude/0002/pgvector-migration-plan` 확인). 본 cycle 의 Sprint 4 D 가 동일 PGVector 인프라를 사용하므로 sequencing 결정이 두 cycle 의 인프라 비용 / 위험 단위를 좌우.

**본 BRIEFING 권고**: agent_memory 이전 먼저 (정본 fidelity 검증), Sprint 4 D 가 후행. **D10 단계적 정책** 명시 — dev = 동일 컨테이너 + DB/user 분리, prod 는 별 PGVector instance 옵션을 PLAN gate 에서 재검토.

| sequencing | 영향 |
|------------|------|
| **agent_memory 이전 먼저** (권장) | agent_memory 정본 fidelity 검증으로 PGVector 안정화 → Sprint 4 D 가 검증된 PGVector 위에 합류. ADR-0021 의 단일 진입점이 agent_memory cycle |
| Sprint 4 와 agent_memory 동시 | Critical surface 응축, rollback 단위 비현실적. 비추천 |
| Sprint 4 먼저 | PGVector 가 RAG 로 먼저 자리잡은 뒤 agent_memory 합류. fidelity 우선순위 역전 |

---

## 13. Codex outside-voice review — 1차 호출 결과 (REV-20260520-0001)

**호출 정보**: codex consult mode / model gpt-5 default / reasoning medium / web_search_cached / read-only sandbox / **session `019e4421-2a8f-74a2-8b91-6afc191856e0`** (follow-up 가능) / 1 turn / 12 tool calls (`rg`, `sed` 으로 AGENTS.md / SECURITY.md / app.py / CONVENTIONS.md / utils.py 실제 확인) / **278,180 tokens** (input 273K + output 5K) / 2026-05-20 호출.

**결과 분포**: **20 Claim** — Valid 17 / Partial 1 / 결정 영역 1 / Misread 0.

### 13.1 흡수된 Valid Claim (17 건)

| Claim | Risk | 흡수 위치 |
|-------|------|----------|
| #1 RBAC catchup (dba/pending 별 catchup tuple) | Major | §5.2 의 6 checklist |
| #2 attachment group 신설 시 FE 매핑 | Major | §5.2 의 group 정책 강화 |
| #3 IsDynamic=0 권한의 정적 추가 필수 | Major | §5.2 의 catalog hydrate 정책 |
| #4 wildcard MySQL GRANT 위험 | Critical | D15 (신규) + §6.1 attachment_maintainer/writer/reader/cleanup 분리 |
| #6 conversation hard-delete race | Critical | D6 (revised) + §6.1 reconciliation worker |
| #7 retention vs hard-delete 모순 | Major | D6 (revised) — 4 종 delete taxonomy |
| #8 signed URL 외부 LLM 송신 불가 | Critical | D13 (신규) — base64 / files API only |
| #9 D11 consent unit | Critical | D11 (revised) — provider × data class × purpose × revoke |
| #10 audit masking 부족 | Major | D12 (revised) + SECURITY.md §9 신규 |
| #11 ActionCode naming + builder allowlist | Major | §5.1 — dotted lowercase (`attachment.upload` 등) + build_audit_change_json case 추가 |
| #12 content array 저장 포맷 | Major | §5.5 — DB string contract 유지, provider adapter 직전 transient |
| #13 attachment_ids 기본값 | Critical | D16 (신규) — selected only |
| #14 XLSX zip / formula / locale | Major | §6.1 — XLSX edge cap + CSV encoding/delimiter/locale + worker timeout |
| #15 SQL guard regex 우회 | Critical | D14 (신규) — sqlglot AST parser + DB 권한 2중 차단 |
| #16 PDF degraded state | Major | D17 (신규) + UploadStatus enum 확장 |
| #17 PGVector container 운영 경계 | Critical | D10 (revised) — 단계적 정책 |
| #19 share derived content 누출 | Critical | D9 (revised) + §6.1 share builder redact |
| #20 MinIO bootstrap 부족 | Major | §6.1 Pre-flight 의 minio-init one-shot service |

### 13.2 Partial 흡수 (1 건)

| Claim | 정합 검토 결과 | 흡수 방식 |
|-------|----------------|----------|
| #5 sandbox schema naming collision | backend conv_id 는 UUID 강제 (frontend lazy-create sentinel 은 backend 미진입). Codex 의 충돌 위험 추정은 약간 과대. 그러나 sha256 hash + mapping table 권고는 robustness 강화로 가치 있음 | §5.1 `WebConversationAttachmentsSandboxSchemas` mapping table + sha256 hash 기반 schema name |

### 13.3 결정 영역 (1 건)

| Claim | 사용자 결정 | 적용 |
|-------|-------------|------|
| #18 Sprint sequencing | 현 BRIEFING 유지 (Cycle 0+1 묶음, 사용자 가치 우선) | §7 sequencing 유지. 단 `attachment.execute_sql_on.*` activation 만 별 PLAN-APPROVED gate 분리 — Codex 권고 일부 흡수 |

### 13.4 Follow-up 예정

본 Revision 1 의 17 finding 흡수가 적절한지 + 신규 blindspot 잔존 여부 검증을 위해 **2 차 Codex review** 예정. session `019e4421-...` continue (`codex exec resume`) 로 호출 가능 — 사용자 명시 trigger 시 진행. 비용 ~$1-2 추가.

---

## 14. 정합 검토 (BRIEFING 본문 vs 정책 문서 / spec)

본 BRIEFING 의 implementation-ready 표현이 실제 코드 / 정책과 정합하는지 검증한 결과:

| 영역 | BRIEFING 표현 | 실제 spec | 정합 |
|------|---------------|-----------|------|
| RBAC `_resolve_permission_catalog` | §5.2 catalog hydrate 정책 | `app.py:306` — 정적 source + IsDynamic=1 union | ✓ 정합 |
| `_ensure_seed_catchup` dba/pending | §5.2 6 checklist | `app.py:1575~1614` 별 catchup tuple 확인 | ✓ 정합 |
| `build_audit_change_json` allowlist | §5.1 ActionCode 표 + build_audit_change_json case 추가 | `app.py:8944~9112` — unknown action ValueError | ✓ 정합 |
| ActionCode naming | §5.1 dotted lowercase (`attachment.upload` 등) | 실제: `conversation.ask`, `share.fork`, `admin.account.update` 등 | ✓ 정합 |
| CONVENTIONS.md §10.6 group | §5.2 attachment 8 번째 group | 현재 7 group (`audit` 가 TASK-0073 신설 전례) | ✓ 정합 |
| share.js renderMessage | §6.1 D9 redact 정책 | `share.js:87` 메시지 content 직접 렌더 | ✓ 정합 (D9 가 미해결 부분 보강) |
| MySQL GRANT `_` `%` 패턴 | D15 와일드카드 금지 | MySQL 8.0 공식 — `_` single-char wildcard, `%` multi-char | ✓ 정합 |
| conversation_id UUID | §5.1 SchemaName = sha256(conversation_id)[:32] | backend conv_id 는 `_resolve_conversation_for_account` 가 UUID 보장 | ✓ 정합 |
| `cleanup_pending_delete_conversations` | §6.1 reconciliation worker | `app.py:3567` 기존 함수 + `list_delete_requested_conversation_ids` | ✓ 정합 |
| `_is_allowed_api_model` vision | §6.2 vision 화이트리스트 | 기존 model picker 확장 가능 구조 | ✓ 정합 |
| `AgentMemoryFactEntries` ingest | §6.3 KB ingest pipeline | 기존 fact / RAG / Text / Object 4 종 KB 구조 | ✓ 정합 |
| `WebMessages.MetaJson` | D9 `attachment_derived` flag | 기존 MetaJson 확장 가능 | ✓ 정합 |
| v3.8.0 worktree §13.2 | §15 worktree 정책 | `ai/claude/0087/attachment-briefing` 격리 | ✓ 정합 |

---

## 15. 워크트리 / commit 정책 정합 (v3.8.0 §13.2)

본 BRIEFING 및 후속 Sprint 1~4 작업은 **모두 worktree 격리 안에서 진행**:

- Plan / BRIEFING 작성: `ai/claude/0087/attachment-briefing` (현 worktree)
- Sprint 1 implementation: 별 worktree `ai/claude/0087/sprint-1-foundation-csv` 권장 (PLAN-APPROVED 후)
- Sprint 2/3/4 각각 별 worktree
- worktree 별 F1 binding (단일 branch 영구) 준수
- main worktree 의 mutation 금지 (v3.8.0 §13.2.1 — 단일 AI 순차 작업 포함)

각 Sprint 의 worktree merge 는 PR 또는 `_template:entry` arg-given dispatch 의 자동 merge (§16.3 + §13.2.5) 따름.

---

## 16. 결론 + 다음 단계

본 BRIEFING Revision 2 는 Codex outside-voice review **1차 (17 Valid finding) + 2차 (Critical 3 + Major 11 + Minor 2)** 모두 흡수, sequencing 사용자 결정 유지, 신규 결정 D13~D21 도출. 사용자 결정 21 건 (D1~D21) 은 PLAN-APPROVED 게이트의 명시 확정 대상.

**다음 단계**:

1. ~~**Codex follow-up review (2 차)** — 완료 (§17 참조).~~
2. **§7.1 Critical 승인 게이트** — Revision 2 의 최종 BRIEFING 을 사용자에게 표시 → D1~D21 명시 확정 → `TASK.md` 상단에 `<!-- PLAN-APPROVED by <user> on <date> (TASK-0094, Critical §12.3 — 첨부 multi-cycle 4 sprint 분리 + D14 SQL guard allowlist 통과를 Sprint 1 ship 조건) -->` 마커 부여.
3. **Sprint 1 implementation 진입** — Cycle 0 + Cycle 1 (A CSV ingest) 본격 코딩. 별 worktree `ai/claude/0087/sprint-1-foundation-csv` 분리. F1 binding 준수. **§15 의 worktree lifecycle cleanup 조건 (R-F10) 도 §1~§4 완료 기준에 포함**.
4. Sprint 1 완료 → 사용자 dogfooding → Sprint 2 (C Vision) → Sprint 3 (B KB) → Sprint 4 (D RAG, agent_memory 별 cycle 완료 후).

본 BRIEFING revision 시점 코드 / 정책 doc 변경: 0. 본 BRIEFING 파일 1 개만 갱신 (worktree `ai/claude/0087/attachment-briefing`).

---

## 17. Codex outside-voice review — 2차 호출 결과 + Revision 2 흡수 (REV-20260521-0002)

### 17.1 호출 메타

- **호출 시점**: 2026-05-21
- **호출 방식**: `codex exec resume "019e4421-2a8f-74a2-8b91-6afc191856e0"` (Revision 1 의 1차 session continue)
- **prompt scope**: Revision 1 finding 흡수 적절성 + 신규 blindspot
- **결과**: 20 1차 Claim 재검토 + 14 신규 finding (F1~F14) + 최종 Verdict
- **Verdict**: **NEEDS_REVISION** — Critical 3 (F3 / F7 / F8) + Major 잔존 → 본 Revision 2 작성으로 흡수

### 17.2 1차 Claim 재검토 매트릭스 (20 건)

| # | Claim | 2차 판정 | Revision 2 흡수 결과 |
|---|---|---|---|
| 1 | RBAC seed checklist | PASS | (변화 없음) — §5.2 6 checklist 유지 |
| 2 | attachment group 신설 | PASS | (변화 없음) — admin.js 도 같은 수준 수정 필요 명시 |
| 3 | IsDynamic=0 정적 source | PASS | (변화 없음) |
| 4 | wildcard grant 금지 | NEEDS_REVISION → **R-Claim4** | D15 갱신: maintainer wildcard 제거, writer 최소권한 |
| 5 | schema name hash mapping | PASS | (변화 없음) |
| 6 | delete race | NEEDS_REVISION → **R-Claim6** | D6 갱신: tombstone + nullable FK |
| 7 | delete 4 taxonomy | PASS w/ follow-up | (R-F1 으로 처리) |
| 8 | 외부 LLM signed URL 금지 | PASS | (변화 없음) |
| 9 | consent matrix | NEEDS_REVISION → **R-F2** | D11 갱신: grouped batch modal |
| 10 | audit HMAC masking | PASS | HMAC key rotation 은 별 운영 항목 (Sprint 1 runbook) |
| 11 | ActionCode dotted lowercase | PASS | `build_audit_change_json()` case 추가 sprint 필수 |
| 12 | DB string contract | PASS | (변화 없음) |
| 13 | attachment_ids selected-only | NEEDS_REVISION → **R-F5** | D16 갱신: lazy-create snapshot |
| 14 | XLSX/CSV cap | PASS | openpyxl `data_only=True` 수식 캐시 테스트 §9.1 포함 |
| 15 | sqlglot AST guard | NEEDS_REVISION → **R-F3 (Critical)** | D14 갱신: denylist → allowlist 전환 |
| 16 | partial_indexed | PASS w/ follow-up → **R-F6** | D17 갱신: retrieval-time 정책 |
| 17 | PGVector dev/prod | PASS | (변화 없음) |
| 18 | execute_sql_on 별 gate | NEEDS_REVISION → **D18 (Rev2 신규)** | 사용자 결정 — 단일 통합 gate 유지 (F8 부분 거부) |
| 19 | D9 share redact | NEEDS_REVISION → **R-F7 (Critical)** | D9 갱신: 기존 token 자동 redact + policy version |
| 20 | MinIO key rotation | NEEDS_REVISION → **R-F9 / D20** | D20 신규: dual-key + canary + rollback runbook |

### 17.3 신규 Blindspot 흡수 매트릭스 (F1~F14)

| ID | Risk | Codex finding | Revision 2 결정 | 본문 영향 |
|---|---|---|---|---|
| **F1** | Major | delete UX state 부재 | D6 inline: 4 state 표면화 (attachment list + audit) | §5.6 / §6.1 lifecycle 표 추가 |
| **F2** | Major | consent matrix 12 modal 폭격 | D11 inline: grouped batch modal | §5.6 composer modal 설계 + §6.1 D11 UX 표 |
| **F3** | **Critical** | sqlglot denylist 우회 | D14 inline: AST shape allowlist 전환 | §6.1 Sprint 1 의 SQL guard subtask + §9.1 SQL guard 테스트 표 전수 확장 |
| **F4** | Major | grant drift 무방비 | D15 inline: health endpoint + 주기 reconciliation | §6.1 Sprint 1 의 `attachment_grant_audit` worker subtask + §5.4 `/api/admin/health/attachment-grants` endpoint |
| **F5** | Major | lazy-create attachment snapshot | D16 inline: busyKey + pending sentinel snapshot | §5.6 composer + §6.1 frontend subtask |
| **F6** | Major | partial_indexed retrieval 신호 부족 | D17 inline: answer meta + UI banner + LLM system note + OCR follow-up | §6.4 Sprint 4 retrieval policy + §5.5 LLM prompt 정책 |
| **F7** | **Critical** | 기존 share token backward-compat | D9 inline: 배포 즉시 자동 redact + audit `share.policy.redact_applied` + policy version 저장 | §5.1 `WebShareLinks.PolicyVersion` column + §8 share view 정책 갱신 |
| **F8** | **Critical** | Sprint 1 gate 분할 부족 | **D18 신규**: 단일 통합 gate 유지 (사용자 거부) — D14 / R-Claim4 / R-F4 로 위험 격리 충족 | §7 sequencing 표 / §6.1 ship 조건 |
| **F9** | Major | MinIO key rotation runbook 부재 | **D20 신규**: dual-key + canary + rollback + audit | §6.1 Sprint 1 runbook subtask |
| **F10** | Minor | worktree lifecycle cleanup 조건 | §15 갱신 (다음 §15 표) | §15 |
| **F11** | Major | derived message JSON 배열 부적합 | **D19 신규**: `WebAttachmentDerivedMessages` join table | §5.1 데이터 모델 갱신 + §5.5 share redact / §6.1 ingest pipeline / §6.2 vision pipeline |
| **F12** | Major | legal erasure ↔ audit 충돌 | D6 inline + D12 cross-ref: pseudonymous event id 최소 필드 | §5.1 audit row pseudonym 정책 / §8 SECURITY |
| **F13** | Major | provider Files API lifecycle | D13 inline + D11 inline: `WebConversationAttachmentProviderFiles` + post-inference delete + consent 문구 | §5.1 데이터 모델 / §6.2 / §6.4 |
| **F14** | Minor | pending read.own bytes 다운로드 정책 | **D21 신규**: metadata-only, bytes 는 승인 후 | §5.2 RBAC catalog 표 갱신 |

### 17.4 본문 cross-ref (§5~§9 / §15 갱신 위치)

> 본 §17.4 는 Revision 2 의 본문 inline 갱신 위치를 한눈에 추적하기 위한 cross-ref 표. 각 결정의 상세는 §2.2 의 inline `→ Rev2:` 라인에 명시되며, 본문 §5~§15 의 실제 수정은 Sprint 1 implementation 진입 직전 한 번 더 확정 본문에 반영한다 (본 Revision 2 의 BRIEFING 본문은 §2.2 의 inline 결정과 본 §17 매트릭스가 source-of-truth).

| 결정 ID | §2.2 inline | §5 데이터/RBAC/Storage/API/LLM/UI | §6 Sprint | §8 SECURITY | §9 Test | §15 워크트리 |
|---|---|---|---|---|---|---|
| R-Claim4 (D15 ↑) | D15 | §5.2 RBAC 권한 / §5.3 storage write user | §6.1 maintainer/writer/cleanup grant 단계 |  | §9.1 grant scope 테스트 추가 |  |
| R-Claim6 (D6 ↑) | D6 | §5.1 attachment row schema | §6.1 lifecycle worker | §8 deletion 정책 |  |  |
| R-F1 (D6 ↑) | D6 | §5.6 attachment list UX | §6.1 frontend subtask |  | §9.1 delete state UX |  |
| R-F2 (D11 ↑) | D11 | §5.6 consent modal | §6.1 modal subtask |  | §9.1 consent UX |  |
| R-F3 (D14 ↑, Critical) | D14 |  | §6.1 SQL guard ship 조건 |  | **§9.1 SQL guard 표 전수 확장** (FOR UPDATE / SLEEP / INTO OUTFILE / information_schema 등) |  |
| R-F4 (D15 ↑) | D15 | §5.4 health endpoint | §6.1 grant audit worker |  | §9.1 drift 시나리오 |  |
| R-F5 (D16 ↑) | D16 | §5.6 composer | §6.1 frontend snapshot |  | §9.1 lazy-create race |  |
| R-F6 (D17 ↑) | D17 | §5.5 LLM prompt + §5.6 message UI | §6.4 retrieval policy |  | §9.4 partial_indexed UX |  |
| R-F7 (D9 ↑, Critical) | D9 | §5.1 `WebShareLinks.PolicyVersion` |  | §8 share view 정책 | §9.1 기존 token 자동 redact |  |
| **D18** (신규) | D18 |  | §6.1 ship 조건 / §7 sequencing |  |  |  |
| **D19** (신규) | D19 | §5.1 `WebAttachmentDerivedMessages` join | §6.1 / §6.2 / §6.4 ingest/vision/rag pipeline |  | §9 fork/share 테스트 |  |
| **D20** (신규) | D20 |  | §6.1 MinIO runbook subtask | §8 storage 운영 |  |  |
| **D21** (신규) | D21 | §5.2 pending role 권한 |  |  | §9.1 pending bytes denial |  |
| R-F10 (§15 ↑) |  |  |  |  |  | §15 cleanup 완료 조건 |
| R-F11 (D19) | D19 (위 동일) |  |  |  |  |  |
| R-F12 (D6/D12 ↑) | D6 / D12 | §5.1 audit row pseudonym | §6.1 erasure pipeline | §8 legal erasure |  |  |
| R-F13 (D11/D13 ↑) | D11 / D13 | §5.1 `WebConversationAttachmentProviderFiles` | §6.2 / §6.4 |  |  |  |
| R-F14 (D21) | D21 (위 동일) | §5.2 |  |  |  |  |

### 17.5 최종 Verdict 평가

- **Critical 3 / Major 11 / Minor 2** 가 모두 §2.2 inline 결정 또는 §17 의 Rev2 신규 결정으로 흡수됨.
- **F8 (1A/1B/1C gate 분할)** 만 사용자 명시 거부 — 단일 통합 gate 유지 (D18). 위험 격리는 D14 (SQL guard allowlist) + R-Claim4 (grant 최소화) + R-F4 (drift health endpoint) + D20 (MinIO rotation runbook) 의 조합으로 충족하며, 통합 gate Critical 통과 조건의 일부.
- **Codex 2차 Verdict NEEDS_REVISION → Revision 2 흡수 후 사용자 PLAN-APPROVED 권고**.

### 17.6 §15 워크트리 cleanup 완료 조건 (R-F10 흡수)

§15 의 워크트리 정책에 다음 cleanup 조건을 ship 조건에 명시 추가:

- 각 Sprint worktree 의 merge 직후 (PR 또는 `_template:entry` arg-given dispatch 의 자동 merge 직후) **즉시**:
  1. `git worktree remove <path>` 실행
  2. branch delete (`git branch -d <branch>` — merged 일 경우, 또는 `git branch -D` 는 사용자 명시 confirm 시에만)
  3. main worktree 의 `git fetch origin && git merge --ff-only origin/main` 으로 fast-forward 확인
- 다음 Sprint worktree 생성 전 위 3 단계 완료가 필수. stale worktree 위에서 다음 Sprint 출발 금지.
