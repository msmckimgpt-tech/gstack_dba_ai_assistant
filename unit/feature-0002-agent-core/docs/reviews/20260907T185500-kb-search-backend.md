# KB external search — backend

- Source: subagent:kb_backend_review
- Round: 2
- Related TASK: TASK-20260907T181510-kb-external-search
- Input: §18.11 changed_files/diff_excerpt/task_md_content/acceptance_criteria injected; no independent tools.

### Blocking issues

**P1: 0건.**

- `modules/kb_search.py:20–74`의 MySQL 엔진·scope 검증과 모든 DB 접두 해석에 대한 허용 검사로, R1의 DB 이름 경계 우려가 해소됐습니다. 불명확한 datasource와 MSSQL을 제외하는 처리도 인가 실패 시 보수적으로 동작합니다.
- `modules/sample_queries.py::update_sample`의 상태 변경 제거는 타당합니다. 임베딩 가용성과 샘플의 큐레이션 상태를 분리해, 활성 샘플의 문자 검색을 유지하면서 stale/retired 재활성화를 방지합니다.

### Cross-domain concerns

**확정된 P2: 0건.**

- `modules/kb_search.py:10`의 일치 위치 중심 발췌와 범위 표시는 R1의 점수·전달 본문 불일치를 개선합니다. 다만 문자 유사도에는 정확한 문자열 일치가 없는 결과도 있으므로, 발췌가 항상 최적의 근거라고 보장해서는 안 됩니다.
- `modules/kb_search.py:78`의 5초 제한과 오류 notes 전달은 검색 비용을 제한하고 부분 실패를 드러냅니다. 제공된 운영 RO 측정에서는 검색이 1.06–2.27초에 완료됐습니다.
- `routers/ai_tools.py`의 응답 생성 후 실제 본문 크기 기록, 실패 시 503 및 claim 해제는 반환 데이터와 사용 기록의 일관성을 강화합니다.

### Challenge to current spec

현재 완료 계약은 **MySQL의 보수적인 문자 검색 연결**입니다. MSSQL 문서 검색과 의미 검색 품질 복구까지 완료했다고 보고하면 안 됩니다. 제공된 TASK·notes의 제외 설명과 `describe_schema`/`describe_table` 안내는 이 제한을 명확히 합니다.

통합 테스트가 실행 중이므로 최종 출하 판단에는 완료 결과를 추가해야 합니다. 앞선 회귀 통과를 최종 통합 통과로 간주하지 않았습니다.

### Verdict

**PASS — 제공된 R2 변경 자료에 대한 검토 판정입니다.**

**Human Approval Needed: no**

도구 호출·독립 저장소 검색·파일 수정 없이 제공된 자료만 검토했습니다.
