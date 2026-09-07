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
