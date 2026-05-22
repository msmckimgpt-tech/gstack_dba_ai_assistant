---
doc_type: TODO
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: false
related_task: TASK-0094 Sprint 2~4 (BRIEFING-attachment-multi-cycle.md §6.2~§6.4)
worktree: ai/claude/0094/sprint-2-vision (Sprint 2 entry), 별 worktree (Sprint 3/4)
predecessor: Sprint 1 ship 완료 (PR #52/54/56/61/64/66/69/71/75/78/80/85 main merged, BRIEFING D1~D21 + R-* 15 finding application-level enforcement 완료)
---

# TODO — TASK-0094 Sprint 2~4 인계

본 문서는 Sprint 1 완료 후 인계되는 후속 작업의 정본. 진입 작업자 AI 는 **본 worktree 에서 Sprint 2 만 진행** 한 뒤 PR merge 후 `cycle-finalize` + 별 worktree 로 Sprint 3 진입.

**중요한 전제** (Sprint 1 에서 이미 ship 됨, 본 cycle 에서 재구현 금지):
- MinIO compose service + minio-init bootstrap + `storage_minio.py` (Phase 4)
- 5 신규 table (`WebConversationAttachments` / `WebConversationAttachmentsSandboxSchemas` / `WebAccountConsents` / `WebAttachmentDerivedMessages` / `WebConversationAttachmentProviderFiles`) + `WebConversationShares.PolicyVersion` (Phase 2)
- RBAC 6 (`conversation.attachment.{upload,read}.{own,any}` + `attachment.execute_sql_on.{own,any}`) + attachment group (Phase 3 + 12)
- 7 endpoint + audit 10 ActionCode + D7/D8/D11/D12/D13/D16/D21 enforcement (Phase 5/7/8/12)
- composer paperclip + drag-drop + pills + D16 selection snapshot + R-F5 lazy-create (Phase 6)
- consent grouped batch modal (Phase 7)
- D9 share redact + R-F7 PolicyVersion (Phase 8)
- D6 reconciliation worker (`attachment_reconciliation.py`) + F1 4 state + F12 pseudonym (Phase 9)
- 4 MySQL user + R-Claim4 minimal grants + R-F4 health endpoint (`sandbox_schema.py`) (Phase 10)
- CSV/XLSX ingest (`sandbox_ingest.py`) + LLM prompt section (Phase 11)
- **D14 sqlglot AST allowlist** (`sql_guard.py`) — Sprint 1 Ship 조건 충족 (Phase 12)

본 cycle 의 코드 변경은 항상 위 산출물을 **재사용** 한다. 중복 module / 중복 endpoint / 중복 RBAC 신설 금지.

---

## Sprint 2 — Cycle 2 (Vision 이미지) — Major §12.3, 1~1.5 주

**Risk grade**: Major §12.3. **본 worktree (`ai/claude/0094/sprint-2-vision`) 에서 진행**.

### Sprint 2 진입 조건

- [x] Sprint 1 ship 완료 (PR #85 main merged 2026-05-22T06:12:07Z)
- [x] BRIEFING-attachment-multi-cycle.md Revision 2 정본 (D1~D21 + R-* finding lock-in)
- [x] 사용자 PLAN-APPROVED 마커 (TASK.md line 126 의 TASK-0094 cycle 전체 PLAN-APPROVED 가 4 sprint 전체 cover — Sprint 2 별도 마커 불요)
- [x] outside-voice review (codex consult) — **SKIPPED (사용자 결정 2026-05-22)**, REV-20260522-0014 에 SKIP 사유 + 6 risk vector 명시

### Sprint 2 작업 TODO (BRIEFING §6.2)

#### S2.1 vision 모델 화이트리스트
- [x] `unit/feature-0003-agent-web-ui/src/app.py` 의 `_is_allowed_api_model` 화이트리스트에 vision 모델 추가: `gpt-4o`, `gpt-4o-mini`, `claude-3-5-sonnet-*`, `claude-sonnet-4-*`. 정확한 model id 는 사용자/API Vault 가 사용하는 model picker 의 현재 list 와 정합 확인 후 패치.
- [x] API Vault drawer 의 model picker label (frontend `app.js` 의 model dropdown 렌더링) 에 `(Vision)` 표기 추가 — vision 가능 모델 식별 가능.

#### S2.2 content array transient 변환
- [x] `unit/feature-0002-agent-core/src/modules/llm_invoke.py` (또는 동등한 provider adapter) 의 `messages_for_provider()` 도입 — DB 의 `AgentMemoryMessages.Content` 는 string contract 유지 (§5.5), **provider 직전 transient content-array** 로 변환. text + image_url 분리.
- [x] DB 저장 경로에 영향 0 — share builder / fork / audit 모두 string content 그대로 사용.

#### S2.3 `_build_attachment_context_section` kind=image 분기
- [x] `unit/feature-0002-agent-core/src/agent_core.py` 의 `_build_attachment_context_section` (Sprint 1 Phase 11 신설) 에 `kind=image` 처리 추가.
- [x] vision 가능 모델 사용 시 — `storage_minio.get_object_bytes(object_key)` 로 MinIO 사내망 read → base64 inline (data URL) → content-array image 부분 생성.
  - **D13 정합 절대 준수**: signed URL 외부 송신 금지. server-side bytes read + base64 inline 만.
- [x] vision 불가 모델 사용 시 — 첨부 무시 + 사용자에게 toast 안내 ("선택한 모델은 이미지 분석 불가, vision 가능 모델로 전환하세요").

#### S2.4 D11 consent 확인
- [x] vision invoke 첫 송신 직전 (`messages_for_provider()` 호출 직전) — `WebAccountConsents` 에서 `(account_id, provider=<picked>, data_class=file_image, purpose=inference)` row 의 active 여부 확인.
- [x] 미동의 시 — 사용자에게 grouped batch modal trigger (frontend) + 동의 후 retry. modal UI 는 Sprint 1 Phase 7 의 `_renderConsentSection` 재사용 가능 — 또는 별 inline modal 신설.
- [x] DB 는 세분 row (file_image / inference) 그대로 사용. UX 는 Sprint 1 의 grouped UX 동일.

#### S2.5 audit dispatch
- [x] 신규 ActionCode `attachment.vision.invoke` build_audit_change_json case 추가. ChangeJson: `{provider, model, attachment_ids, token_usage (prompt + image), conversation_id}`. raw image bytes / filename 절대 미노출 (D12 정합).
- [x] `record_audit_event` 또는 `_audit_user_action` dispatch — vision invoke success / failure 양쪽 기록.

#### S2.6 share view 정책
- [x] Sprint 1 Phase 8 의 D9 share redact 가 vision_analysis derived message 도 자동 cover. 추가 변경 불필요 — `_meta_has_attachment_derived` 가 vision_analysis flag 도 catch 하도록 메시지 INSERT 시점에 `MetaJson.attachment_derived=true` + `DerivationType="vision_analysis"` 설정 보장.
- [x] `WebAttachmentDerivedMessages` join table 에 row INSERT (D19) — `(AttachmentId, MessageId, DerivationType="vision_analysis", CreatedAt)`.

#### S2.7 R-F13 provider Files API lifecycle (선택)
- [x] vision invoke 가 OpenAI Files API 또는 Anthropic Files API 를 사용한다면 — `WebConversationAttachmentProviderFiles` row INSERT (Phase 2 schema) + inference 직후 provider delete API 호출 + 실패 시 cleanup worker (`reconcile_provider_files`, 별 helper 또는 후속 cycle).
- [x] base64 inline 만 사용한다면 본 항목 skip (provider 측 잔존 0).

#### S2.8 verify-completion + commit + PR
- [x] py_compile / JS syntax / `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` PASS.
- [x] FUNCTION.md AC 신규 (AC-0277~ 대역, 본 cycle ship 시점에 main 의 마지막 AC + 1 부터).
- [x] TASK.md TASK-0094 entry 에 Sprint 2 [x] 마킹.
- [x] MODIFY.md CHG-20260522-XXXX append.
- [x] REVIEW.md REV-20260522-XXXX [SUBAGENT:codex] 또는 [SKIPPED:reason] append.
- [x] commit + 별 issue + 별 PR (head `issue/<n>-task-0094-sprint-2-vision`) + merge.
- [x] `bash bin/cycle-finalize.sh --pr <PR-NUMBER>` 호출 — worktree remove + branch delete.

### Sprint 2 outside-voice review 권장 시점

- **Sprint 2 ship 전** Codex consult 호출 — vision invoke path 의 D11 consent / D13 signed URL 금지 / D19 join table 등록 / audit dispatch 4 가지 보안 표면 확인.
- review 명령 예: `/codex consult` mode + Sprint 2 의 변경 diff 전달.

---

## Sprint 3 — Cycle 3 (DDL/KB 보강, admin only) — Major §12.3, 1 주

**별 worktree**: `ai/claude/0094/sprint-3-kb` (Sprint 2 ship 후 cycle-finalize → 새 worktree 생성 후 진입).

### Sprint 3 진입 조건

- [x] Sprint 2 ship 완료 + main merged
- [x] Sprint 2 worktree cleanup 완료 (cycle-finalize)
- [x] 사용자 PLAN-APPROVED 마커 (Sprint 3)

### Sprint 3 작업 TODO (BRIEFING §6.3)

#### S3.1 admin 콘솔 "스키마 정의서 KB 등록" pane 신설
- [ ] `unit/feature-0003-agent-web-ui/src/static/admin.html` 에 KB ingest pane 추가 (admin.js 의 navigation 에 entry 추가).
- [ ] Cycle 0 첨부 list 에서 `kind=text` / `kind=other` 와 `.sql` extension 표기된 항목만 노출.
- [ ] preview (본문 head 100 줄) + ScopeKey 입력 form + "ingest 버튼".

#### S3.2 신규 backend endpoint
- [ ] `POST /api/admin/attachments/kb-ingest` — body `{attachment_id: int, scope_key: str, source_type: 'manual', weight: float = 0.9}`. 응답 `{fact_entry_id, scope_key}`.
- [ ] 권한: `attachment.kb.write.any` (admin only).
- [ ] AGENTS.md §1.1 정합: 본 endpoint 는 사용자 질의 경로가 아니라 admin 의 manual curation — 직접 SQL 작성 가능 (LLM 미경유).

#### S3.3 신규 module
- [ ] `unit/feature-0002-agent-core/src/modules/kb_ingest.py` 신설.
- [ ] 본문 → `AgentMemoryFactEntries` row INSERT 로직.
- [ ] ScopeKey 충돌 시 기존 row 의 `status='superseded'` + 새 row INSERT (idempotent override).

#### S3.4 RBAC 신규
- [ ] `PERMISSION_DEFINITIONS` 에 `attachment.kb.write.any` 추가 (group=attachment, IsDynamic=0).
- [ ] BRIEFING §5.2 6 checklist 준수:
  - [ ] PERMISSION_DEFINITIONS 정적 entry
  - [ ] SEED_ROLE_DEFINITIONS admin 의 permissions set 자동 포함 (`set(PERMISSION_CODES)` 이미 admin 에 자동 grant)
  - [ ] `_ensure_seed_roles` 의 admin catchup 에 추가
  - [ ] dba/pending catchup 은 본 권한 미부여 (admin only)
  - [ ] FE app.js / admin.js label + description map 갱신

#### S3.5 audit dispatch
- [ ] `attachment.kb.ingest` ActionCode + build_audit_change_json case. ChangeJson: `{attachment_id, scope_key, source_type, weight, fact_entry_id, superseded_fact_entry_id (있다면)}`.

#### S3.6 정책 문서 갱신
- [ ] `repo/AGENTS.md` §11.3 명시적 확장 — "manual ingest fact 의 SourceType='manual', Weight=0.9 (자동 수집보다 우선)" 정책 문구 추가.

#### S3.7 verify-completion + ship
- [ ] py_compile / JS / verify-completion PASS, FUNCTION.md AC, TASK.md [x], MODIFY/REVIEW append.
- [ ] PR + merge + cycle-finalize.

---

## Sprint 4 — Cycle 4 (PDF/MD RAG) — Critical §12.3, 3~4 주

**별 worktree**: `ai/claude/0094/sprint-4-rag` (Sprint 3 ship 후).

### Sprint 4 진입 조건

- [ ] Sprint 3 ship 완료 + main merged
- [ ] **agent_memory 별 cycle 의 PGVector 도입 완료** (외부 의존 — 본 cycle 의 prerequisite, BRIEFING §12)
- [ ] D10 정책 합의 — dev 단계 = agent_memory 와 동일 컨테이너 + DB 분리. prod 별 instance 옵션은 본 Sprint 4 의 PLAN gate 에서 재검토.
- [ ] 사용자 PLAN-APPROVED 마커 (Sprint 4) — Critical §12.3 라 **outside-voice review 2 회 권장** (codex 1차 review + 2차 follow-up).

### Sprint 4 Pre-flight TODO (BRIEFING §6.4)

#### S4.0 ADR-0025 본격 활성
- [ ] `docs/DECISIONS.md` 의 ADR-0025 (PGVector for attachment Sprint 4 prerequisite) 의 namespace 결정 — `agent_drag` (ADR-0024 호환) vs `agent_attachment_rag` (별 database). Sprint 4 진입 cycle 의 first action 으로 lock-in.

#### S4.1 compose service 추가
- [ ] `docker-compose.yml` `postgres` service 추가 (`pgvector/pgvector:pg16`). agent_memory 별 cycle 에서 이미 추가됐다면 reuse.
- [ ] `.env.example` 9 변수: `PGVECTOR_HOST=postgres`, `PGVECTOR_PORT=5432`, `PGVECTOR_USER=rag_writer`, `PGVECTOR_PASSWORD=`, `PGVECTOR_DB=agent_rag` (또는 ADR-0025 결정 namespace), `RAG_EMBEDDING_MODEL=text-embedding-3-small`, `RAG_CHUNK_SIZE=1000`, `RAG_CHUNK_OVERLAP=200`, `RAG_TOP_K=5`.

### Sprint 4 작업 TODO (BRIEFING §6.4)

#### S4.2 PostgreSQL 클라이언트
- [ ] `unit/feature-0002-agent-core/src/modules/storage_pgvector.py` 신설 — psycopg + pgvector-python.
- [ ] `_ensure_pgvector_schema(conn_pg)` — `CREATE EXTENSION IF NOT EXISTS vector` + `attachment_chunks` 테이블 부트스트랩 (BRIEFING §5.1 schema 정합).
- [ ] connection pool (`psycopg.Pool`) — agent_memory 와 별 instance/DB 일 때만 활성.

#### S4.3 RAG chunking
- [ ] `unit/feature-0002-agent-core/src/modules/rag_chunking.py` 신설.
- [ ] PDF: `pypdf` 또는 `pdfplumber` 로 text 추출. 시도 1 — pypdf (fast), 시도 2 — pdfplumber (encrypted/scanned 일부 cover).
- [ ] text / markdown: 그대로 사용.
- [ ] LangChain `RecursiveCharacterTextSplitter` (또는 자체 splitter) — chunk_size + overlap env-driven.
- [ ] **D17 + R-F6 degraded state 처리**:
  - scanned PDF (no text layer) / encrypted PDF / no-text / 200+ page cap / table-heavy → `UploadStatus='partial_indexed'` + `MetaJson.degraded_reason=<reason>` UPDATE.
  - `_serialize_attachment_for_api` 가 이미 lifecycle_state + degraded_reason 응답 — frontend 가 사용자에게 표면화.
- [ ] requirements.txt 에 `pypdf>=4.0`, `pdfplumber>=0.10` (또는 둘 중 하나) 추가.

#### S4.4 RAG embedding
- [ ] `unit/feature-0002-agent-core/src/modules/rag_embed.py` 신설.
- [ ] OpenAI `text-embedding-3-small` (default) 또는 Anthropic embedding API wrapper.
- [ ] D11 consent — `data_class=file_embedding`, `purpose=indexing` 첫 송신 직전 확인 (Sprint 2 의 consent helper 재사용).
- [ ] batch embedding (`RAG_EMBEDDING_BATCH_SIZE`).
- [ ] retry + timeout (exponential backoff).

#### S4.5 RAG retrieval
- [ ] `unit/feature-0002-agent-core/src/modules/rag_retrieve.py` 신설.
- [ ] query embedding → top-K cosine search (pgvector `<->` operator).
- [ ] MMR re-rank 옵션 (default off, env toggle).
- [ ] `attachment_chunks` 의 metadata 와 함께 응답.

#### S4.6 compose_system_prompt 확장
- [ ] Sprint 1 의 `_build_attachment_context_section` 에 `kind=pdf` / `kind=text` 분기 추가 — RAG top-K excerpt 채우기.
- [ ] **D17 + R-F6 retrieval-time policy**:
  - `partial_indexed` 문서가 top-K 에 포함되면 — answer meta 에 `degraded_sources[]` 분리 + UI warning persistent + LLM system note "근거 누락 가능 — OCR 처리 후 재인덱싱 권장".

#### S4.7 PDF 페이지 이미지 inline
- [ ] vision 가능 모델 + PDF kind + 페이지 이미지 첫 1~2 장 base64 inline (Sprint 2 의 content array transient 변환 재사용).
- [ ] PDF 페이지 → image 변환 (`pdf2image` 또는 `pdfplumber` 의 `to_image()`).

#### S4.8 audit dispatch
- [ ] `attachment.rag.retrieve` ActionCode + case. ChangeJson: `{conversation_id, attachment_ids, query_hmac (HMAC of query, not raw), top_k_chunk_ids, top_k_count, mmr_used}`. raw query 절대 미노출 (D12 정합).

#### S4.9 정책 문서 갱신
- [ ] `repo/AGENTS.md` §11.3 본격 확장 — "Fact KB (MySQL) + RAG chunk store (Postgres pgvector) 이중 소스, fact 가 검증 정본·RAG 가 보강" 정책 정식화.
- [ ] `docs/SECURITY.md` §3 — PGVector embedding 가 외부 LLM 으로 송신되는 시점의 PII 차단 정책 추가 (D11 consent + chunking 시 redaction 고려).

#### S4.10 outside-voice review 2 회
- [ ] Sprint 4 가 Critical §12.3 — codex 1차 review (RAG 보안 표면 + degraded state 처리 + PGVector grant 정합) + Revision 흡수 + 2차 follow-up review.
- [ ] PLAN-APPROVED 마커는 2차 review 흡수 후.

#### S4.11 verify-completion + ship
- [ ] py_compile / JS / verify-completion + RAG smoke (PDF 3~5 페이지 sample + chunking + embedding + retrieval round-trip) PASS.
- [ ] PR + merge + cycle-finalize.

---

## 공통 정책 (모든 Sprint 적용)

### 정책 reminders

- **AGENTS.md §1.1**: 사용자 질의 경로의 SQL 은 LLM 만 작성. 코드 템플릿 SQL 생성/주입 금지. Sprint 2/3/4 모두 LLM tool 활용.
- **AGENTS.md §2.2**: `_ai_delegated_dev_template` 외부 디렉토리 수정 금지.
- **AGENTS.md §2.3**: 문자열 패턴 기반 의도 분기 금지, planner_constraints 주입 금지, 고정 상한 기반 샘플링 설계 금지.
- **AGENTS.md §16.3 + §13.2.5**: per-worktree per-branch 자동 동기화. BLOCKED 없음 + 승인 대기 없음일 때 commit + push + PR 자동 진행.
- **CONTRIBUTING.md §5**: commit message `<type>(<scope>): <요약> (#<issue>)` + `Task-Cycle:` trailer 필수.
- **외부 LLM 송신**: signed URL 금지 (D13), 항상 server-side bytes read + base64 inline 또는 Files API. raw filename / raw SQL / raw bytes audit ChangeJson 미포함 (D12).
- **D14 SQL guard**: validate_sql_for_sandbox 통과한 statement 만 sandbox 실행 — Sprint 2/3/4 모두 caller (LLM tool 또는 admin manual) 에서 guard 호출 필수.

### worktree 정책 (§15 R-F10)

- Sprint 별 별 worktree (`ai/claude/0094/sprint-N-<slug>`) 사용.
- Sprint ship 후 즉시:
  1. `bash bin/cycle-finalize.sh --pr <PR-NUMBER>` 호출
  2. worktree remove + branch delete 확인
  3. main worktree fast-forward (`git pull --ff-only origin main`)
- 다음 Sprint worktree 생성 전 위 3 단계 완료 필수. stale worktree 위에서 다음 Sprint 출발 금지.

### docs 책임

- 각 Sprint 별 — FUNCTION.md AC (BRIEFING § 별 결정 mechanism 별 1 AC), TASK.md Phase [x], MODIFY.md CHG, REVIEW.md REV.
- AC 번호 — main 의 마지막 AC + 1 부터 (충돌 회피).
- TASK.md TASK-0094 entry 의 Sprint N 항목에 [x] mark.
- CONVENTIONS.md / SECURITY.md / AGENTS.md 갱신 시 별 entry 추가.

### outside-voice review 시점

- Sprint 2 (Major §12.3): ship 전 1 회 codex consult 권장.
- Sprint 3 (Major §12.3): ship 전 1 회 권장 (admin only 라 scope 작음, SKIPPED 도 가능).
- Sprint 4 (Critical §12.3): ship 전 2 회 (1차 + 2차 follow-up) 필수.

---

## 산출물 cross-ref

- BRIEFING: [BRIEFING-attachment-multi-cycle.md](./BRIEFING-attachment-multi-cycle.md) Revision 2
- 1차 review: REV-20260520-0001 (Codex outside-voice, 17 Valid)
- 2차 review: REV-20260521-0002 (Codex 2차 follow-up, Critical 3 + Major 11 + Minor 2)
- 정본 review: REV-20260521-0001 [SUBAGENT:codex] (BRIEFING Revision 2 lock-in)
- Sprint 1 phase-별 review: REV-20260521-0003~0014 (Phase 1~12)
- D20 runbook: [RUNBOOK-minio-key-rotation.md](./RUNBOOK-minio-key-rotation.md)
