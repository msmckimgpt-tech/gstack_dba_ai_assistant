---
doc_type: MODIFY
feature_id: feature-0033-analysis-synthesis
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260730T082000 클러스터 합성 요약(L2) 신규 (Major, cross-cut)

- **무엇:** 의미 클러스터마다 "이 묶음이 함께 무엇을 하는가"를 2~4문장으로 합성해
  `cluster_summaries` 에 적재한다. 캐시 키는 멤버셋 지문 + L1 지문 + L0 지문 3중.
- **왜:** 라이브 클러스터 818개에 라벨(평균 9자)만 있고 요약이 없어, 전역 질의가 개별 분석문
  수백 개를 훑어야 했다. 계층 요약이 그 비용을 줄이는 층이다.

### 변경 파일

| 파일 | 변경 |
|---|---|
| `alembic/versions/20260730_0051_cluster_summaries.py` | **신규** — 멤버셋 해시 PK · 2중 버전 · 커버리지 카운트 · GRANT |
| `src/modules/llm.py` | `CLUSTER_SUMMARY_PROMPT` + `llm_cluster_summary()` (라벨과 별 계약) |
| `src/modules/semantic_cluster.py` | `_summary_enabled`·`_version_hash`·`_summary_savepoint`·`_evidence_versions`·`_summary_cache`·`_summary_put`·`_llm_cluster_summaries`·`_summary_call` 신규 + 클러스터 확정 시점 배선 |
| `shared/config.py` · `shared/runtime_settings.py` | `AGENT_METADATA_CLUSTER_SUMMARY` 정지 스위치(live) |
| `tests/test_cluster_summary.py` | **신규** — 캐시 3중 계약 · 정렬 결정성 · 비용 유계 · 시그니처 미유입 · 정직성 |
| `tests/test_worker_parallelism.py` | `PERF_KEYS` +1 |
| `unit/feature-0003-agent-web-ui/docs/test-runs.d/*` | 직전 cycle PB-0008 fragment 2건 DEFERRED → **PASS** + 증거 스크린샷 |
| `docs/improvements/analysis-orchestration/ROADMAP.md` | ITEM-04·05·06·12 done · ITEM-07 진행 |

### 위험과 완화

| 위험 | 완화 |
|---|---|
| 신규 LLM 지출(818 클러스터) | **pass 전체** 40개 상한 + 배치 6 + 백그라운드 토큰 예산(feature-0032)을 **배치마다 재확인** + `acquire("llm")` + live 정지 스위치 |
| 요약 → 재임베딩 순환 | 시그니처 미유입 불변식(테스트가 시그니처 빌더 소스를 검사) |
| 캐시 무한 미스 | 정렬 후 해시(순서 무관) + 길이 프리픽스 인코딩(구분자 충돌 차단) |
| 요약 실패가 클러스터링을 막음 | 전체 try 격리 + 조회·적재를 savepoint 로 감쌈(non-autocommit 오염 차단) |
| 나쁜 요약이 캐시에 굳음 | 20자 미만 미저장 |
| 동시 실행 stale 덮어쓰기 | upsert 에 버전 비교 조건(`IS DISTINCT FROM`) |
| 저장 실패를 성공으로 계산 | `_summary_put` 이 bool 반환, 성공만 카운트 |

### 배포 scope
워커(insight-worker) + web(설정 레지스트리). `make deploy-all`.

### 교차 참조
- `shared/docs/MODIFY.md` — `config`·`runtime_settings` 확장
- `unit/feature-0031-analysis-grounding/docs/FUNCTION.md` — L0 증거(evidence_version 원천)
- `unit/feature-0032-llm-token-budget/docs/FUNCTION.md` — 상위 토큰 예산
