# KB external search — security

- Source: subagent:kb_boundary_review
- Round: 2
- Related TASK: TASK-20260907T181510-kb-external-search
- Input: §18.11 changed_files/diff_excerpt/task_md_content/acceptance_criteria injected; no independent tools.

## 1. Blocking issues

**제공된 최종 변경분에서 보안 P1/P2는 발견하지 못했습니다.**

R1의 DB 접두 충돌 P1은 해소됐습니다.

- `kb_search.py:20–74`는 table suffix의 **모든 가능한 DB 접두**가 허용 목록에 포함돼야 반환합니다. 따라서 `sales`만 허용된 경우 `sales.archive.orders`가 통과하지 않습니다.
- schema 문서는 suffix 전체를 DB와 정확히 비교합니다.
- `shared/datasources.py:34–38,154–167`에서 엔진이 scope prefix와 해시 입력에 포함되므로, 현재 MySQL scope가 과거 MSSQL scope를 재사용한다는 우려도 해소됐습니다.
- 출처가 모호한 MSSQL·hash 절단 키 제외가 명시돼 있습니다.

## 2. Cross-domain concerns

R1의 두 P2도 해소됐습니다.

- `ai_tools.py`의 get/claim 모두 `len(response.body)`를 기록하므로 실제 JSON 출력과 원장 계산이 일치합니다. 원장 실패 시 결과 미반환·claim 해제도 유지됩니다.
- `kb_search.py:10–17,78`은 발췌 위치와 전체 길이를 알리므로 1,200자 절단이 전체 문서로 오인되는 문제를 줄였습니다.

최종 통합 테스트는 아직 실행 중이므로 완료 증적으로 별도 확정해야 합니다. 이 판정은 제공된 코드 검토 결과입니다.

## 3. Challenge to current spec

Acceptance Criteria의 **“저장 벡터 삭제 0건”**은 질문 수정 시 `embedding=None`으로 갱신하는 동작과 문구상 충돌합니다. 질문이 바뀌면 기존 벡터를 무효화하는 처리는 타당하므로, 문서를 “일괄 삭제 없음; 질문 수정 시 기존 벡터 무효화”로 정확히 구분하십시오.

또한 MySQL 레거시 RAG의 보수적 검색과 MSSQL RAG 제외를 기능 문서에 명시해야 합니다. 현재 설계를 전체 벡터 검색 품질 복구로 설명해서는 안 됩니다.

## 4. Verdict

**PASS** — R1 보안 결함이 해소됐으며, 제공된 변경분에서 추가 인가 우회나 출력 원장 누락을 발견하지 못했습니다.

**Human Approval Needed: no**
