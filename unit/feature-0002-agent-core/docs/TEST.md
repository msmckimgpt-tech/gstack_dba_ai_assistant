---
doc_type: TEST
feature_id: feature-0002-agent-core
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- 코어 소스가 새 위치에서 빌드되는지 확인
- `make ask`가 새 feature Dockerfile을 통해 실행되는지 확인
- 역할별 내부 LLM 호출이 실제 env alias를 사용하는지 확인
- 워크스테이션 기준 `model=auto` 지연이 브라우저에서 재현 가능한 수준인지 확인
- GPU 우선 추론 조건과 provider 직접 벤치 수치를 확인

## 2. Test Cases
- TEST-0001: `docker-compose.yml`의 agent 계열 build가 `feature-0002-agent-core/src/Dockerfile`을 사용한다
- TEST-0002: `Makefile`의 `make ask`가 동일 인터페이스를 유지한다
- TEST-0003: `AGENT_PLAN_MODEL`, `AGENT_TASK_CLASSIFY_MODEL`, `AGENT_SUMMARY_MODEL`, `AGENT_TOPIC_MODEL`, `AGENT_SQL_FIX_MODEL`, `AGENT_STEP_GRADE_MODEL` 이 코드에서 실제 호출 모델로 사용된다
- TEST-0004: `python3 -m py_compile unit/feature-0002-agent-core/src/modules/config.py unit/feature-0002-agent-core/src/modules/llm.py`
- TEST-0005: `make -C /root/download/docker/local_llm health`
- TEST-0006: `make -C /root/download/docker/local_llm bench-quick`
- TEST-0007: bootstrap admin 브라우저 세션에서 `model=auto`, 질문 `현재 데이터베이스 목록을 보여줘` 가 `60초 이내` 완료
- TEST-0008: 같은 브라우저 구간에서 `ollama ps` 가 `PROCESSOR 100% GPU` 를 유지하고 `nvidia-smi` 가 약 `5.9GiB / 6GiB` 사용을 보인다
- TEST-0009: browser regression 이후 `llm_warn.log` 에 새 `Connection error` 누적이 없는지 확인

## 3. Test Run History
- 2026-03-26: 구조 검증 기준만 정의함. 엄격한 질의 시나리오는 후속 작성 예정
- 2026-04-15:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/modules/config.py unit/feature-0002-agent-core/src/modules/llm.py`
    - 결과: 통과. `llm.py` 기존 문자열에서 `SyntaxWarning: invalid escape sequence '\\`'` 경고 1건
  - `make -C /root/download/docker/local_llm health bench-quick`
    - 결과: Summary `3317ms`, SQL Review `6174ms`
    - 비교 기준: Summary baseline `6664ms` 대비 개선, SQL Review baseline `5102ms` 대비 미달
  - 브라우저 기준 `model=auto` 회귀 검증
    - conversation `20260415091922-1a529620`: `duration_ms=33038.4`, status `done`
    - conversation `20260415092741-f2384e59`: `duration_ms=35555.35`, status `done`
    - 이전 비교치: conversation `20260415091121-57bc11e0`, `duration_ms=84335.19`
  - GPU/메모리 관찰
    - `docker exec local-llm-edge ollama ps` -> `qwen3.5:4b`, `PROCESSOR 100% GPU`
    - `nvidia-smi` -> 약 `5898 MiB / 6144 MiB`
    - `GET /api/conversations` 기준 `processing` conversation 0건으로 정리 완료
