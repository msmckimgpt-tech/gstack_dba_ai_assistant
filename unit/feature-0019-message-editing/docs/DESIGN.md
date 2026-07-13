---
doc_type: DESIGN
feature_id: feature-0019-message-editing
status: approved
related: FUNCTION.md, feature-0003 DESIGN-fork-reference.md, SECURITY.md §21
---

# DESIGN — 메시지 편집: 대화 내부 브랜치 트리

> 사용자 승인(2026-07-13, `/_template:entry` arg-given): ChatGPT식 완전 분기,
> "내부 fork 의 다른 형태로 구현하는 부분을 검토", 2-phase. 본 문서가 승인된 정본.

## 1. Fork 재사용 검토 (사용자 요청 항목)

**결론: fork 연산 자체는 재사용하지 않되(형태 불일치), fork 의 두 개념을 브랜치 모델로 이식한다.**

- 현 fork(`_fork_conversation_impl`)는 메시지 구간을 **새 `conversation_id` 로 deep-copy**
  (messages + core_messages + 첨부 blob + CSV sandbox 재적재)한다. edit 마다 fork 하면:
  - 대화가 브랜치마다 별도 conversation_id 로 쪼개져 사이드바 오염.
  - deep-copy(blob/스키마 재적재) 비용 — ChatGPT 편집은 경량이어야.
  - "한 대화 안에서 `< n/m >` 인라인 페이징" UX 와 형태 불일치(fork 는 별 대화 전환).
  → **fork-per-edit 기각.**
- **이식하는 개념**: (a) fork 의 *cut-point*(브랜치 = 편집 지점 이후의 새 가지),
  (b) SECURITY §21 의 **`has_restricted_members` 게이트 플래그 fast-path** — 분기 없는
  대화는 기존 경로 그대로(회귀 0). 이 두 검증된 패턴을 대화-내부 브랜치로 재구성한다.

## 2. 데이터 모델 (마이그레이션 1개, additive)

두 message store 는 독립 id-space 이며 `created_at` 으로 bridge 된다(기존 계약 유지).

### 2.1 `agent_runtime.core_messages` (LLM 문맥 정본)
| 컬럼 | 타입 | 의미 |
|---|---|---|
| `parent_message_id` | bigint NULL | 브랜치 트리의 predecessor(같은 대화 core_messages.id). NULL=대화 첫 메시지. 분기 시작 전엔 미사용(NULL). |
| `edit_root_message_id` | bigint NULL | 편집된 사용자 메시지의 버전 체인 root(첫 버전의 id). 형제 버전 그룹핑·정렬 키. 비편집=NULL. |
| `edit_version` | int NOT NULL DEFAULT 1 | 버전 체인 내 순번(1=원본). |

- 인덱스: `ix_core_messages_parent (conversation_id, parent_message_id)`,
  `ix_core_messages_edit_root (edit_root_message_id)`.
- 첨부 house-pattern(`RootAttachmentId`/`VersionNumber`) 을 메시지 버전에 대응.

### 2.2 `agent_runtime.core_conversations`
| 컬럼 | 타입 | 의미 |
|---|---|---|
| `has_branches` | boolean NOT NULL DEFAULT false | **게이트 플래그**. 첫 편집(reanswer)에서만 true set. false=기존 linear 경로(회귀 0). |
| `active_leaf_message_id` | bigint NULL | 현재 활성 브랜치의 leaf core_messages.id. NULL=linear tail(=MAX(id)). 활성 경로 = leaf→root parent 역추적. |

### 2.3 표시 store `agent_runtime.messages`
동일 3 컬럼(`parent_message_id`/`edit_root_message_id`/`edit_version`) 미러. 표시 로더가
활성 경로를 그리고 페이징 메타를 노출. core 와 messages 는 각자 id-space 라 브랜치 포인터도
각 store 내부 id 로 저장(bridge 는 created_at 유지).

### 2.4 MySQL parity
`_bootstrap_schema.py` 의 `AgentCoreMessages`/`AgentCoreConversations` 에 동일 컬럼 idempotent
ALTER(레거시 parity 폴백 — PG 가 정본이나 dual-write 계약 유지).

## 3. 코어 recall 로더 변경 (blast radius 최소화)

`runtime_backend._PG_LOAD_CORE_MESSAGES*` + `agent_core._load_conversation_messages`:

```
if not conv.has_branches:      # 거의 모든 대화
    → 기존 쿼리 그대로 (ORDER BY id ASC [+ window])   # byte-identical, 회귀 0
else:
    → active-path recursive CTE:
        WITH RECURSIVE path AS (
          SELECT * FROM core_messages WHERE id = :active_leaf
          UNION ALL
          SELECT m.* FROM core_messages m JOIN path p ON m.id = p.parent_message_id
        )
        SELECT ... FROM path
        WHERE <window 술어 동일 합성>       # floor_ca/ceil_ca/joined_ca 그대로 AND
        ORDER BY id ASC LIMIT :limit
```

- **window 합성**: §21 의 floor/ceil/joined 술어를 active-path 결과에 그대로 AND. fail-closed
  유지(PG 오류 시 빈 history — windowed 는 PG 전용, MySQL fall-through 금지).
- **비분기 항등성**: `has_branches=false` 경로는 코드·SQL 무변경 → AC-ME-2 회귀 0 단언 대상.
- active_leaf 가 NULL 이면(레거시 has_branches=false) 진입 안 함(기존 경로).

## 4. 쓰기 경로 / 브랜치 생성

- `save_core_message` + `messages` writer 에 `parent_message_id`/`edit_root_message_id`/
  `edit_version` optional 인자 추가(기본 NULL/1 = 무회귀).
- **정상 append**(신규 턴): parent = 직전 active leaf. active_leaf 를 새 메시지로 전진.
  has_branches=false 대화는 parent 를 NULL 로 둬도 무방(로더가 linear).
- **reanswer 편집**(1:1):
  1. 대상 user 메시지 M(core+display) 의 `edit_root`(없으면 M.id) 로 형제 버전 M' 생성:
     `parent_message_id = M.parent_message_id`, `edit_root = M.edit_root or M.id`,
     `edit_version = MAX(version)+1`, content = new_content, sender = actor.
  2. `has_branches=true` set.
  3. M' 를 새 active tail 로 `/api/ask` 파이프라인 재dispatch → assistant 답변 A'
     (`parent = M'`). active_leaf = A'(또는 이후 이어지는 leaf).
  4. 옛 브랜치(M, A, 하위)는 그대로 보존 — parent 트리에 남아 페이징으로 재활성 가능.
- **simple 편집**: 재답변 없이 대상 메시지 내용 갱신. 편집 이력은 형제 버전으로 보존하되
  active_leaf 는 기존 하위 유지(브랜치 분기 없음). "편집됨" 표식. (구현: 새 edit_version 로
  in-place 승격 + 하위 parent 재연결, 또는 `edited_content` in-place + prior 보존 — §6 결정.)

## 5. 엔드포인트

| 메서드·경로 | 역할 |
|---|---|
| `POST /api/conversations/{cid}/messages/{mid}/edit` | body `{mode, new_content}`. authz→모드 분기(§4). reanswer 는 `/api/ask` result 형태 반환. |
| `POST /api/conversations/{cid}/branch/switch` | body `{message_id, version_number}` 또는 `{target_leaf_id}`. active_leaf 전환(페이징). |
| `GET /api/history` (확장) | 활성 경로 메시지 + 메시지별 `{edit_version, version_count, has_siblings}`. 프론트 `< n/m >` 렌더용. |

- 서버 방어선: 편집 authz = 본인 발신(sender_account_id==actor) + 대화 접근권 + 모드 잠금
  (그룹 & @assistant → 거부). 클라이언트 플래그 불신(그룹 멘션 게이트 패턴 답습).

## 6. 열린 구현 결정 (착수 중 확정)
- D1: simple 편집의 이력 보존 방식 — (a) 형제 edit_version + active 유지, (b) in-place
  `content` 갱신 + prior 스냅샷. → **(a) 권장**(reanswer 와 모델 통일, 페이징 일관). 착수 시 확정.
- D2: reanswer 대상이 "마지막 user 메시지가 아닐 때"(중간 편집) 하위 처리 — ChatGPT 는 편집
  지점 이후 전체를 옛 브랜치로 남기고 새 브랜치 시작. active-path 모델이 자연 충족(하위는 옛
  parent 체인에 잔류). 확인 테스트 AC-ME-5.
- D3: display store 페이징 메타 계산 — 활성 경로 조립 시 각 노드의 sibling count 를 edit_root
  GROUP BY 로 1쿼리 집계(N+1 회피, 첨부 version_count 패턴 답습).

## 7. 보안 (SECURITY 갱신 대상)
- 편집 IDOR: 본인 발신 메시지만. `sender_account_id` 는 위조 불가 claim 기준.
- 공유 window: active-path CTE 에 window 술어 합성(가려진 구간 recall 물리 배제 유지, §21.1).
- @assistant 무결성(그룹): 편집 잠금으로 공유 답변 근거 변조 차단. `mentions.message_invokes_assistant` 재사용.
- 감사: edit/branch.switch → `WebAuditEvents`(§9 user high-signal action 확장).
- 브랜치 전환 권한: 대화 접근권 보유자만 자기 뷰 active_leaf 전환(active_leaf 는 per-conversation
  — 멀티멤버 그룹은 Phase 2 에서 브랜치 없음이라 무관; 1:1 은 단일 owner).

## 8. Phasing
- **Phase 1 (1:1)**: §2 마이그레이션 + §3 로더 + §4 쓰기/브랜치 + §5 edit(simple/reanswer)·
  branch-switch·history + 프론트 편집 UI·페이징 + 테스트(AC-ME-1~5,7) + PB-0008.
- **Phase 2 (그룹/공유)**: 그룹 단순수정 + @assistant 잠금 + window 정합 + 감사(AC-ME-6,8) + PB-0008.

## 9. 위험
- R1 코어 로더 blast radius: `_load_conversation_messages` 는 모든 ask 문맥 진입점. →
  has_branches=false 항등성(AC-ME-2) + 회귀 테스트로 가드.
- R2 cross-store cut(§F1, fork 문서): messages/core created_at 독립 clock. 브랜치는 각 store
  내부 parent id 로 저장하므로 cross-store 시각 cut 불필요(fork 의 F1 회피).
- R3 window 합성 누락: active-path CTE 에 window 술어 빠지면 가려진 구간 누출. → AC-ME-7 + 보안 리뷰.
- R4 편집 authz 우회: → 서버 재검증 + IDOR 테스트.
