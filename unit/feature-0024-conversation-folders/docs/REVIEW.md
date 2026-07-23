---
doc_type: REVIEW
feature_id: feature-0024-conversation-folders
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260723T060000-conv-folders [SUBAGENT:general-purpose] SHIP-WITH-FIXES — 대화 폴더 전체(스키마·RBAC·백엔드·프론트·Phase2a) (Major/Critical §12.3, TASK-0011)
- §18.8 적대적 **보안** 리뷰(general-purpose, 코드 직접 판독) — IDOR/계정격리/RBAC/SQLi/프롬프트injection/깊이·순환 집중. 판정: HIGH 1 + LOW 2 → **전부 in-cycle 수정 후 SHIP-WITH-FIXES**.
- **[HIGH — 수정 완료] restore 경로 IDOR (교차계정 un-archive)**: `restore_folder` 라우터가 path `folder_id` 소유만 검증하고 body `archived_folder_ids` 를 무검증으로 `restore_folders(ids)` 에 전달 → `UPDATE ... WHERE folder_id = ANY(%s)` owner 필터 부재. IDENTITY 순차 PK 열거로 공격자 A 가 피해자 B 의 soft-delete 폴더를 대량 부활(무결성/가용성 침해, griefing). 기밀 누출은 없음(list/map 은 owner 스코프). 수정: `restore_folders(ids, owner_account_id)` 에 `AND owner_account_id = %s` SQL 강제, 라우터가 `manage.any` 아니면 `_acct_id(account)` 전달(`_folder_store.py:318`·`folders.py:172-176`).
- **[LOW — 수정 완료] `_folder_instructions_for` 소유==배정 불변식 미확인**: map↔folder 조인이 folder_id 로만 이뤄져 `manage.any` 운영자 배정 시 (운영자, conv, 타인폴더) map 이 자기 ask 에 타인 지침 주입(자기영향·저위험). 수정: 조인에 `AND f.owner_account_id = m.account_id` 추가로 계약 코드화(`agent_core.py:1112`).
- **[LOW — 수정 완료] datasource_id/product_id 핀 접근 미검증(현재 inert)**: create/update 가 무권한 datasource/product id 저장 가능(현 ask 플로우 미소비라 즉시 취약 아님, 향후 자동스코프 배선 시 IDOR 전환). 수정: 라우터 create/update 에서 두 필드 수신 제거 → Phase 2b(접근 게이트 동반)로 이연, 스키마 컬럼은 존치(`folders.py:83`·`115` 부근).
- **[SHIP 근거 — 안전 확인]** 폴더 소유 IDOR(update/delete/assign/move)=`_require_folder_owner`+move 내부 new_parent 소유 재확인 · 대화 배정=[대화 read own/any(+그룹멤버) + 폴더 소유] 2중 게이트·404 단일화(존재 oracle 없음) · 계정격리=list/map/folder_id_for/payload 전부 owner/account 스코프(그룹 멤버별 독립) · 프롬프트injection=compose account_id=발화자라 항상 요청자 자기 폴더(신규 특권 없음) · SQLi=재귀 CTE·ANY(%s)·SET 리터럴절 전부 파라미터화(값 보간 0) · 깊이/순환=self/subtree 차단+grandfathering 상한으로 무한깊이·순환 봉인 · 삭제안전=soft-delete archived_at 만(core_conversations 무접촉)·하드삭제 경로 없음 · RBAC lockout=folder.* 4종 정의+admin catchup 양쪽 · fail-open=격리 실패로 이어지지 않음.
- 검증: 수정 후 py_compile(folders/_folder_store/agent_core) PASS. 라이브 IDOR/격리는 POST-DEPLOY PB-0008(TEST-3 Critical).

## REV-20260723T160500-conv-folders-postverify [SKIPPED:doc-only-postdeploy-verification-record-no-code] — 대화 폴더 배포 + 라이브 e2e 검증 (CHG-20260723T160500)
- Panel skip: 코드 0(POST-DEPLOY 실증·TASK 완료). 정본 = REV-20260723T060000-conv-folders([SUBAGENT] SHIP-WITH-FIXES, HIGH restore IDOR + LOW 2 수정).
- 실증(Windows Chrome 150, 배포본 7f8e7a40): 폴더 CRUD·재귀(depth 상한 422·순환 422)·계정별 배정·삭제 서브트리 보존(대화 true)·undo·지침 주입 PG 확증·HIGH IDOR 수정 serving 확인·사이드바 재귀 트리 시각. Known limitation(운영자 타계정 대화 배정=own 파티션 미표시) 문서화. Phase 2b(폴더 파일·자동스코프) 이연.
