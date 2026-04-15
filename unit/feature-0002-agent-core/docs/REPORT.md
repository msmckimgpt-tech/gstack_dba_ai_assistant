---
doc_type: REPORT
feature_id: feature-0002-agent-core
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary
외부 Local LLM provider를 `GTX 1660 SUPER 6GiB` 워크스테이션 기준 프로필로 조정했고, 현재 repo는 역할별 내부 LLM 호출이 실제 env alias를 따르도록 수정했다. 휴리스틱 fast-path는 추가하지 않았고, 실제 개선은 provider 경량화, 내부 모델 바인딩 수정, 소비자 시간 예산 축소만으로 얻었다.

## 2. Progress
- Planned: 0
- In Progress: 저장소별 commit/push, provider direct SQL Review 경로 추가 원인 분석
- Done: 외부 provider 6GB 프로필 정렬, 내부 역할별 모델 바인딩 수정, 브라우저 실측, stuck `processing` 대화 정리

## 3. Recent Changes
- 코어 Python 소스를 `unit/feature-0002-agent-core/src`로 이동
- agent 이미지 Dockerfile 추가
- 2026-04-06: LLM 게이트웨이(local-llm-gateway) 연결 성공, `make ask` 동작 확인
- 2026-04-15: 현재 repo 내부 provider 소유 경로를 제거하고 외부 `/root/download/docker/local_llm` gateway 소비 계약으로 복구
- 2026-04-15: `AGENT_PLAN_MODEL`, `AGENT_TASK_CLASSIFY_MODEL`, `AGENT_SUMMARY_MODEL`, `AGENT_TOPIC_MODEL`, `AGENT_SQL_FIX_MODEL`, `AGENT_STEP_GRADE_MODEL` 을 실제 코드가 사용하도록 수정
- 2026-04-15: 브라우저 기준 `ask(model=auto)` 가 `84.33초`에서 `33.04초`, `35.56초` 수준으로 재검증됨
- 총 변경 횟수: 5

## 4. Open Issues
- 테스트 DB(gunzgame, account_db 등)가 아직 로드되지 않음 — TestDataDB.sql 복사 필요
- provider direct `bench-quick` 결과는 Summary `3317ms`로 개선됐지만 SQL Review `6174ms`는 기존 기준선 `5102ms` 대비 목표를 아직 충족하지 못했다.
- 일부 planner run은 여전히 데이터베이스 목록 요청을 `search_tables` 탐색으로 잘못 확장한다. 휴리스틱 우회 없이 prompt/plan 품질 개선이 추가로 필요하다.

## 5. Test Status
- 정적 검증: `python3 -m py_compile unit/feature-0002-agent-core/src/modules/config.py unit/feature-0002-agent-core/src/modules/llm.py`
  - 결과: 통과. 단, `llm.py` 기존 문자열에서 `SyntaxWarning: invalid escape sequence '\\`'` 1건이 출력됨
- 외부 provider 수동 검증: `make -C /root/download/docker/local_llm health bench-quick`
  - 결과: Summary `3317ms`, SQL Review `6174ms`
- 브라우저 수동 검증: bootstrap admin 로그인 후 `model=auto`, 질문 `현재 데이터베이스 목록을 보여줘`
  - 결과 1: conversation `20260415091922-1a529620`, `duration_ms=33038.4`, status `done`
  - 결과 2: conversation `20260415092741-f2384e59`, `duration_ms=35555.35`, status `done`
  - 증빙: `/shared/out/browser/perf_login.png`, `/shared/out/browser/perf_before_send.png`, `/shared/out/browser/perf_just_after_send.png`, `/shared/out/browser/perf_done.png`
- GPU 우선 추론 검증:
  - `docker exec local-llm-edge ollama ps` 에서 `qwen3.5:4b`, `PROCESSOR 100% GPU` 확인
  - `nvidia-smi` 에서 추론 중 약 `5.9GiB / 6GiB` 사용 확인
  - `free -h` 기준 swap 증가는 유의미하게 관찰되지 않음
  - `llm_warn.log` 에서 최신 browser regression 구간 이후 새 `Connection error` 누적은 확인되지 않음
- 미검증 항목: provider direct SQL Review 경로 추가 튜닝, 도메인별 장문 DBA 시나리오

## 6. Blocked Items
- 없음

## 7. Human Attention Needed
- `search_tables` 오탐 경로를 휴리스틱 없이 줄일 planner/prompt 개선 기준 확정
