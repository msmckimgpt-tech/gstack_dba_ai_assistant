# KB 외부 검색 검증 — 2026-09-07

- Environment: Docker mysql-ai-agent:697ffa84, 격리 kb-pg-age:pg16 / pg_trgm + vector.
- Network: 전용 mysql-kbsearch-tests, host port 미노출. 테스트 DB/임시 테이블만 사용.
- Result: **203 passed, 19 warnings in 3.20s**. skip/fail 0.
- Suites: core test_kb_external_search, test_kb_embedding_gateway_failclosed, test_sample_flywheel,
  test_kb_read_backend, test_hybrid_search; web test_kb_search_bridge, test_kb_external_reach,
  test_kb_prompt_grounding, test_metadata_phase2, test_sample_feedback_curation;
  feature-0041 test_tool_authz; feature-0043 test_bridge_wiring.
- 핵심: NULL vector 검색, 승인/active/제품/대화/DS/DB 제외, dotted DB 모든 분할 인가,
  인용부호 바인딩, 편집 시 freshness 유지, 늦은 위치의 발췌, 실제 SQL 오류의 층별 notes,
  revoked 권한 403 및 조회 0회, 원장 실패 503+claim 해제, JSON 실제 bytes 일치.
- 임베딩 worker tripwire: 폐기 alias에서 LLM client·worker DB 연결 모두 0회.
  문자 검색에 필요한 KB DB 조회는 정상 수행한다.
- 운영 읽기 전용 실측: transaction_read_only=on, schema/table 문서 28,125건, 승인 active 샘플 1건.
  steam_billing_log: 문서8, 1.47초; status 코드: 문서8, 2.27초;
  결제: 문서0, 1.13초; 캐릭터: 문서0, 1.06초. 사용자 데이터 쓰기/LLM 호출 없음.
- 제한: 운영 샘플 corpus는 1건이므로 검색 품질 통계로 일반화할 수 없다.
  한국어 동의어의 의미검색 및 외부 AI의 최종 판단 품질은 검증되지 않았다.
- 구조검증: gen-routemap 재생성(266 routes/30 modules), codenav-lint PASS.
- 원본 로그: wrapper artifacts/kb-external-search/{tests-final.log,live-read-result.json}.

## 최신 main 통합 후 전체 로컬 CI

- Revision: 50e1c94a (origin/main067e4a58 통합, 문서 append 충돌 양쪽 보존).
- Makefile/CI의 9개 test directory 전체 실행: 7485 passed,28 skipped,1 failed in367.30s.
- 유일 실패: feature0043 test_injection_false_positive의 모든 tool_output 호출 금지assert.
  질문/이력/KB 각인 인자를 구별하고 질문의 session_canary도 보존하도록 검사 정합화.
  **후속 해당 suite19 PASS**. 이 후속은 테스트만 수정했으며 프로덕션 코드가 바뀌지 않았다.
- 28 skip은 기존 플랫폼/통합검사 조건이며 신규 KB PG 검사는 모두 실행했다.
- 전체ruff: 0 findings. migrate-lint self-test/head 단일성, ROUTEMAP/codenav PASS.
- 원격CI: 최근 GitHub run34075693338의 billing/spending-limit job-start 차단 확인.
  실제원격runner 검증은 미수행; 로컬대체와 미검증 사실은 REVIEW에 기록.
- Logs: wrapper artifacts/kb-external-search/tests-full.log,tests-trust-boundary.log,ruff-full.json.
