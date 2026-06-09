---
doc_type: DESIGN
feature_id: feature-0003-agent-web-ui
status: proposed
related: TASK-0170, ADR-WEB-0005
---

# DESIGN — git식 참조 Fork (대화 Lineage 아키텍처)

> 작성: 2026-06-09 (TASK-0170). 사용자 결정으로 fork 를 deep-copy 대신 **부모 대화를
> 런타임 참조**하는 git 식 브랜치로 재설계. 본 문서는 설계만 — 구현은 outside-voice
> 검토 후 단계별 cycle (§9 phasing). 결정 근거는 ADR-WEB-0005.

## 1. 문제 / 목표

### 1.1 현재 (TASK-0167/0168 이후)
- Fork(`_fork_conversation_impl`)는 **웹 표시 메시지(`agent_runtime.messages`)만 deep-copy**.
- LLM 문맥은 `agent_runtime.core_messages` 에서 읽는데(`agent_core._load_conversation_messages`
  → `runtime_backend._PG_LOAD_CORE_MESSAGES`), fork 는 이를 복사하지 않아 **복사본 대화의
  core_messages 가 비어 어시스턴트가 이전 문맥을 인지 못 함**(보고된 버그).
- **첨부(`WebConversationAttachments`)도 미복사** — fork 본은 원본 첨부를 못 봄.
  첨부 접근 게이트 `_account_can_access_attachment` 가 "그 대화 소유자만" 으로 막음(IDOR 방어).
  CSV 질의 sandbox 스키마는 `agent_attachment_<sha256(conversation_id)>` 로 **대화별 1개**.

### 1.2 목표
사용자에게는 "전체 복사본" 으로 보이되, 내부적으로는 **원문 대화를 fork 지점까지 참조**:
- fork 본에서 후속 질문 시 어시스턴트가 원본 문맥(core_messages)을 인지.
- 원본 첨부(파일 + 본문 + CSV 질의)를 fork 본에서 redaction 없이 전부 열람·이어쓰기.
- blob 재업로드·sandbox 스키마 재적재 없이 효율적으로(참조).

### 1.3 비목표 (본 설계 범위 외)
- 부모↔자식 양방향 동기화(자식 변경이 부모에 반영) — branch 는 단방향(부모→자식 read).
- 기존 deep-copied fork 의 소급 변환 — backward-compatible 공존(§9.3).

## 2. 데이터 모델

`agent_runtime.core_conversations` 에 lineage 컬럼 추가:

| 컬럼 | 타입 | 의미 |
|---|---|---|
| `forked_from_conversation_id` | varchar(128) NULL | 부모 conversation_id. NULL=root(비-fork). |
| `fork_cut_at` | timestamptz NULL | 부모 참조 cutoff(inclusive). 부모의 `created_at <= fork_cut_at` 행만 자식 문맥에 포함. anchored fork=앵커 메시지 시각, full fork/duplicate=fork 생성 시각. |
| `fork_depth` | smallint NOT NULL DEFAULT 0 | root=0, 자식=부모+1. 재귀 깊이 가드/표시용. |

- 인덱스: `ix_core_conv_forked_from (forked_from_conversation_id)`.
- **단일 cut key 로 timestamptz 채택**: 표시 메시지(`messages`)·core_messages 둘 다
  `created_at` 보유 → 한 cutoff 로 양쪽 정합. (id 기반은 두 테이블 비-1:1이라 매핑 불가.)
- `fork_depth` 상한(예: 32) 초과 시 fork 를 deep-copy 로 강등(체인 폭주·순환 방지).

> 기존 per-message 메타(`forked_from_conversation_id`/`forked_cut_message_id`)는 표시
> 추적용으로 유지하되, **런타임 참조의 진실원은 core_conversations 의 위 3 컬럼**.

## 3. Lineage 해소

```
resolve_lineage(cid) -> [(ancestor_cid, cut_at_for_its_child), ... , (cid, None)]
```
- `forked_from_conversation_id` 체인을 root 까지 역추적(루트 우선 정렬).
- 각 ancestor 에 대해 "그 ancestor 를 참조하는 다음 자손의 cut_at" 을 적용.
- depth ≤ 32 가드(초과/순환 감지 시 fail-loud 또는 자기 행만 반환).
- 결과는 요청당 1회 계산 후 캐시(요청 스코프).

## 4. 로더 변경

### 4.1 LLM 문맥 (`core_messages`) — 핵심
`agent_core._load_conversation_messages(cid, limit)` 를 lineage-aware 로:
```
merged = []
for (anc_cid, cut_at) in resolve_lineage(cid):
    rows = SELECT role,content,tool_calls,tool_call_id,name,created_at
           FROM agent_runtime.core_messages
           WHERE conversation_id = anc_cid
             AND (cut_at IS NULL OR created_at <= cut_at)
           ORDER BY id ASC
    merged += rows
# 전역 시간순 보장: ancestor 순서 + 각 내부 id ASC 로 이미 정렬
apply tail LIMIT over merged   # (기존 LIMIT 의미 유지 — §4.3 주의)
```
- 단일 SQL(UNION ALL + ORDER BY created_at, id) 로도 구현 가능 — round-trip 절감.
- **무-fork 대화는 lineage=[자기]** 라 기존 동작과 byte-identical(회귀 0).

### 4.2 표시 메시지(`/api/history`, `_conv_load_messages_raw`)
동일 패턴으로 ancestor `messages` 를 cut_at 까지 merge. 표시 redaction 은 본인 소유라
미적용(사용자 결정 B). per-message 메타의 `forked_*` 는 UI 가 "여기서부터 분기" 구분선
렌더에 활용 가능(선택).

### 4.3 주의 — 기존 LIMIT 의미
현 `_PG_LOAD_CORE_MESSAGES` 는 `ORDER BY id ASC LIMIT 50`(앞 50턴). lineage merge 후
LIMIT 를 어디에 거느냐로 의미가 달라짐. 본 설계는 **merge 후 최근 N턴**(tail)으로 보정
권장하나, 이는 기존 동작(앞 50)과의 차이라 별도 검토 항목(§11-R5).

## 5. 권한 모델 (IDOR 핵심)

### 5.1 Lineage = capability
- 자식 대화를 **소유한 계정**만 그 자식을 진입점으로 lineage 를 역추적할 수 있다.
  임의의 부모 cid 를 외부에서 주입하는 경로는 없다(진입점이 항상 소유 자식).
- 따라서 "자식 소유 → 조상 콘텐츠(cut 이내) read 허용" 이 capability 규칙.

### 5.2 same-owner fork (본인 대화 fork/duplicate)
- 자식·부모 소유자 동일 → 조상 read 는 본인 데이터. 무위험. **Phase 1 범위.**

### 5.3 cross-account fork (공유링크 fork, `public_share_fork`)
- 자식(계정 B)이 부모(계정 A)를 참조 → **B 가 ask 할 때마다 A 의 core_messages 를 read**.
- fork 시점에 share 토큰이 "부모를 cut 까지 read" 를 grant 했다는 사실을 lineage 가 포착.
  즉 **fork 생성 = 그 시점 grant 의 고정**(git clone 과 동등 — 이후 share revoke 가
  과거 fork 의 참조를 끊지 않음. deep-copy 였어도 동일하므로 의미 등가).
- **위험**: ① B 가 A 의 데이터를 지속 참조(결합) ② A 가 부모를 삭제/축소하면 B 문맥 변동
  ③ 게이트가 cross-account 조상 read 를 허용하므로 IDOR 표면 확대. → **Phase 5 + outside-voice.**

### 5.4 첨부 게이트 확장
`_account_can_access_attachment`: 현재 `_conversation_owned_by_account(att.ConversationId)`.
확장 → 요청 계정이 소유한 자식의 lineage 가 `att.ConversationId` 를 조상으로 포함하고,
그 첨부가 **cut_at 이전**이면 허용. (cut 이후 부모 첨부는 자식에 비노출 — 브랜치 의미.)

## 6. 첨부 / sandbox 참조

- **파일 열람/다운로드**: `WebConversationAttachments` 행은 복사 안 함. §5.4 게이트 확장으로
  fork 본이 조상 첨부 행(`ObjectKey`)을 참조 → 기존 presigned GET 재사용. blob 재업로드 0.
- **CSV 질의 sandbox**: fork 본은 자기 스키마 없음 → 질의 시 **조상 스키마**
  `agent_attachment_<sha256(anc_cid)>` 로 resolve. data-plane grant 가 fork 질의 경로에
  조상 스키마 사용을 허용해야 함(D15 maintenance path 연계) — **Phase 4(가장 무거움).**
- 부모 첨부 soft-delete(`DeletedAt`) 시 fork 도 비노출(게이트가 DeletedAt 거부) — 일관.

## 7. 부모 lifecycle

- **부모 hard-delete**: 자식 참조가 dangling. 선택지:
  - (a) 자식이 참조하면 부모 hard-delete **차단**(soft-delete 로 강등).
  - (b) **copy-on-delete** — 부모 삭제 시 참조 구간을 자식들로 materialize(복사) 후 삭제.
  - **권장 (b)**: 사용자 기대("내 대화 지웠는데 fork 가 막힘?")와 충돌 없음. 구현은 Phase 5.
- **부모 append**(이 앱은 대화 append-only, 메시지 편집 없음): cut_at 이후 부모 새 메시지는
  자식에 비노출(§5.3) → 자연 정합. topic/product 변경은 문맥 무관.
- **CASCADE 주의**: `fk_*_conv ... ON DELETE CASCADE` 는 부모 메시지 삭제 시 자식 참조를
  깨므로, copy-on-delete 가 CASCADE 보다 **선행**해야 함.

## 8. Cut-point 의미

- 자식은 부모[`created_at <= fork_cut_at`]만 참조. fork 이후 부모 진행은 비노출(브랜치).
- anchored fork: `fork_cut_at` = 앵커 메시지(`messages.id == from_id`) 의 created_at.
- full fork / duplicate: `fork_cut_at` = fork 생성 시각(now()) → 그 시점 부모 전체.
- core_messages·messages 양쪽 같은 cut_at 적용(시각 단일 키).

## 9. 롤아웃

### 9.1 마이그레이션
- alembic: `core_conversations` ADD `forked_from_conversation_id`, `fork_cut_at`, `fork_depth` + 인덱스. 비파괴(NULL 허용, 기존 행 영향 0).

### 9.2 플래그
- `AGENT_FORK_MODE = copy | reference` (default `copy`). reference 검증 후 전환.
- 또는 per-fork: 새 fork 만 reference, 기존은 copy(공존).

### 9.3 Backward compat
- 기존 deep-copied fork(레퍼런스 컬럼 NULL)는 lineage=[자기]로 동작 → 기존과 동일.
- 무-fork 대화도 lineage=[자기] → 회귀 0.

## 10. 단계별 구현 (phasing)

| Phase | 범위 | 위험 | 게이트 |
|---|---|---|---|
| **P1** | 데이터 모델 + lineage 해소 + **core_messages 참조 로더(same-owner)** + 플래그 | Major(코어 로더) | core 회귀 테스트, same-owner only |
| **P2** | 표시 메시지(`/api/history`) lineage merge | Major | 표시 회귀 e2e |
| **P3** | 첨부 **파일** 참조(게이트 §5.4 확장, same-owner) | Major(IDOR 게이트) | outside-voice(IDOR) |
| **P4** | 첨부 **CSV sandbox** 조상 스키마 참조(data-plane grant) | Critical | outside-voice + DBA |
| **P5** | cross-account(공유 fork) 참조 + 부모 copy-on-delete | Critical | outside-voice(cross-account) |

- **P1 이 보고된 버그(문맥 상실)를 참조 방식으로 해결**. P2~P5 는 첨부·교차계정 확장.
- 각 Phase 독립 PR + verify-completion + (P3+) outside-voice.

## 11. 핵심 위험 (why 설계-우선 + outside-voice)

- **R1 코어 로더 blast radius**: `_load_conversation_messages` 는 모든 ask 의 문맥 진입점.
  버그 시 전 대화 영향. → 무-fork lineage=[자기] 항등성 + 회귀 테스트로 가드.
- **R2 IDOR 게이트 확장**(§5.4): 첨부 접근이 lineage 추종으로 넓어짐 — capability 진입점이
  항상 소유 자식임을 엄격 보장해야 함. cross-account(P5)는 특히 위험.
- **R3 부모 lifecycle 결합**(§7): 부모 삭제가 자식 문맥을 깸. copy-on-delete 선행 필수.
- **R4 LIMIT/요약 상호작용**(§4.3): merge 후 tail vs head, 긴 lineage 의 토큰 폭주.
- **R5 순환/깊이 폭주**: depth 가드 + fork-of-fork 체인 상한.
- **R6 cross-account 지속 참조**(P5): A 데이터를 B 가 상시 read — 감사/격리 정책 검토.

## 12. 테스트 계획 (미래 cycle)

- lineage 해소 단위 테스트(체인/깊이/순환).
- core_messages 참조 로더: same-owner fork 후 ask → 부모 문맥 포함 단언(mock + 라이브).
- 무-fork 항등성: lineage=[자기] 가 기존 로드와 byte-identical.
- cut_at 경계: 앵커 이후 부모 메시지 비노출.
- 첨부 게이트: 조상 첨부 허용 / 비-lineage 첨부 거부(IDOR) / cut 이후 거부.
- cross-account: B 의 fork 가 A 첨부 참조, 비-lineage A' 첨부는 거부.

## 13. 대안 — deep-copy (기각 근거)

- **deep-copy(messages+core+첨부행+sandbox 재적재)**: fork 본 완전 독립(부모 lifecycle 무관),
  IDOR 게이트 무변경. 그러나 ① blob/스키마 재적재 비용 ② 첨부 sandbox 재적재 복잡 ③ 저장 중복.
- 사용자가 "전체 복사로 보이되 내부 참조" 를 명시 선택 → 참조 채택. 단 deep-copy 는
  **부모 삭제 시 copy-on-delete 의 fallback** 으로 재활용(§7-b).
- **절충**: P1(core_messages)만 보면 copy 가 더 단순·저위험. 첨부(P3~P5)에서 참조의 이득이
  큼. → outside-voice 에서 "P1 은 copy, P3+ 만 reference" 하이브리드도 평가 대상.

## 14. Outside-voice 설계 검토 결과 (REV-20260609-0003, 적대적 staff+appsec)

순수 git-reference 안에 대해 검토자가 **RECOMMEND-SIMPLER-APPROACH (하이브리드)** 판정.
구현 착수 전 반드시 반영해야 할 발견:

- **F1 [BLOCKER] cross-table 시각 cut 불가(§3/§8)**: `messages`(웹 레이어 clock)와
  `core_messages`(agent 루프 clock)는 독립 `now()` 로 기록되며, 앵커 display 메시지의
  `created_at` 이 그 턴을 만든 core 턴들의 `created_at` 보다 크다는 **불변식이 없다**. 빌려온
  display 시각으로 core_messages 를 자르면 tool_use/tool_result 가 cut 경계에서 갈라져,
  `_normalize_history_rows`(agent_core.py)가 straddling 턴을 **통째로 drop** → 마지막(중요한)
  턴 소실 = 고치려던 버그 재발. → cut 은 **`core_messages.id` 경계로 fork 시점 확정**(또는 snapshot copy).
- **F2 [BLOCKER] 로더 오기술(§4.3)**: 현 로더는 "앞 50턴" 이 아니라 `_assemble_core_messages`
  의 **tail 윈도우 + 최근 user 턴 보존**(`raw_limit≈max(4N,80)` 로드 후 `[-N:]`). lineage merge
  후 전역 tail 을 취하면 긴 자식에서 **조상 문맥이 통째 evict** → 버그 재발. `created_at` 미투영도
  설계가 누락. → 실제 윈도우 로직 기준으로 재기준 + 등가 테스트 필요.
- **F3 [MAJOR] IDOR 지속화(§5)**: `source_id` 는 caller 제공이고 `conversation.read.any` 로도
  게이트됨. `.any` 보유자가 **임의 대화를 fork** → reference 모델에서 자식 소유가 곧 capability →
  `.any` 회수 후에도 피해자 core_messages/첨부를 **영구 live tap**. deep-copy 는 snapshot 이라
  무관. → `.any`-source fork 는 **강제 deep-copy**.
- **F4 [MAJOR] 교차계정 live reference = 데이터 격리 안티패턴(§5.3)**: "deep-copy 와 등가"
  주장 무효 — deep-copy=1회 snapshot, reference=매 ask 마다 A 데이터가 B 모델호출로 상시
  흐름(+A 의 후속 편집/삭제가 B 문맥 변형). GDPR/erasure/DLP 관점 상이. → **교차계정은 항상 deep-copy.**
- **F5 [MAJOR] sandbox 조상 스키마 공유(§6)**: 1-conversation-1-schema 격리 깨짐 + 공유 가변
  data-plane. → **sandbox 스키마는 로컬 복제**(CREATE TABLE AS, blob 재업로드 아님 — 저렴).
  비싼 건 blob 재업로드뿐 → **file blob 만 ObjectKey 참조**, 나머지는 복사.
- **F6 [MAJOR] 토큰 예산 부재(§4.3)**: depth≤32 는 토큰 현실에서 과대. fork-of-fork 가 컨텍스트
  폭주/조상 evict. → `agent_runtime.summary` 합성 + 작은 상속 토큰예산 + 한 자릿수 depth 캡.
- **F7 [MINOR]**: fork_depth 초과 시 silent copy 강등은 디버깅 함정(모드 표면화 필요);
  copy-on-delete race → same-owner-only 면 (a) soft-delete-block 이 더 단순·무race.

### 14.1 검토자 권고 — 하이브리드 (채택 권장)
1. **core_messages(+로컬 CSV sandbox 스키마)를 fork 시 deep-copy — 지금.** 작고 회귀-bounded,
   보고된 버그 해결, 고-blast-radius 코어 로더·IDOR 게이트 무변경, **교차계정 fork 가 진짜
   snapshot**(A→B 상시 흐름 0).
2. **참조는 *동일 소유자* file blob 첨부에만**(presigned blob 재참조 회피 — 유일하게 비싼 연산),
   플래그 뒤, 분리된 후속 cycle.
3. **폐기**: lineage-aware 코어 로더, 교차계정 reference, 조상 스키마 공유.
4. 사용자가 순수 git-reference 를 고수하면: **반드시 same-owner-only + cut 을 core_messages.id
   경계로** 확정 후 착수.

> 이 하이브리드는 사용자 4대 목표(문맥 인지 / 첨부 포함 / 전체 본문 / "전체 복사처럼 보이되
> 내부 참조")를 모두 충족하면서 F1/F3/F4/F5 를 구조적으로 제거한다. 최종 방향은 사용자 결정
> (ADR-WEB-0005).

## 15. 확정 결정 — 하이브리드 채택 (사용자 결정, ADR-WEB-0005)

사용자가 outside-voice 권고(§14.1)를 수용해 **하이브리드** 확정. 본 문서의 §2~§8 순수
git-reference 안은 **기각**(F1/F3/F4/F5 사유). 확정 범위:

- **Phase 1 (TASK-0170, 구현 완료·본 cycle):** fork 시 `agent_runtime.core_messages`(LLM 문맥)를
  deep-copy. anchored fork=앵커 메시지 created_at 까지, full fork/duplicate=전체. 교차계정
  공유 fork 도 이 복사로 **snapshot**(상시 cross-tenant 흐름 0 — F4 제거). 표시 메시지 복사는
  TASK-0167 부터 이미 동작. **이로써 보고된 "fork 문맥 상실" 버그 해결.**
  - 헬퍼: `_conv_load_core_messages_raw` / `_conv_copy_core_messages`(PG 전용, tool_calls jsonb 보존).
  - 경계 턴: cut 이 turn 중간을 가르면 로드 시 `_normalize_history_rows` 가 정규화(F1 완화).
  - cross-table 시각 cut 의 F1 한계는 **anchored fork 의 경계 ±1턴** 수준이며, copy 라
    straddling 도 로더가 자가 치유(reference 와 달리 corruption 아님).
- **Phase 2 (TASK-0171, 구현 완료):** 첨부 — `WebConversationAttachments` 행을 새 ConversationId
  + fork AccountId 로 복사 + blob **독립 복사**(get+put 새 ObjectKey). CSV/XLSX 는
  `_ingest_attachment_background` 로 fork 전용 sandbox 재적재(F5: 공유 아닌 복제). IDOR 게이트
  무변경(fork 가 자기 행 소유). derived 메시지는 skip(분석본은 Phase 1 core_messages 에 포함).
  - **설계 대비 이탈(근거)**: ADR 의 "동일 ObjectKey / blob 재업로드 0" 대신 **blob 독립 복사**
    채택 — storage_minio 에 server-side copy 부재 + ObjectKey 공유 시 원본 삭제→reconciliation
    이 공유 blob hard-delete→fork 404 의 refcount 위험(REV-20260609-0004 #2). 안전 우선.
  - outside-voice REV-20260609-0004 FIX-FIRST 반영: INSERT-먼저-put(고아 방지) + 용량 cap 검사
    (quota 우회 차단) + 교차계정 audit. SHIP.
  - **이월**: 동일 소유자 file blob *참조* 최적화(재업로드 0)는 refcount/리스 관리 동반이라 후속.
- **폐기**: lineage-aware 코어 로더, 교차계정 live reference, 조상 sandbox 스키마 공유,
  `forked_from_*`/`fork_cut_at` 런타임 참조 컬럼(§2). per-message `forked_from_*` 메타는 추적용 유지.

> Phase 1 은 §2 의 스키마 변경(lineage 컬럼) 없이 순수 복사로 구현 — 마이그레이션 0, 코어
> 로더 무변경(회귀 표면 최소). "전체 복사처럼 보이되 내부 참조" 의 *참조* 측면은 Phase 2 의
> blob/Object 참조로 실현(텍스트는 복사가 정답).
