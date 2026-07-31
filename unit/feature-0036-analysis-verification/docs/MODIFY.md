---
doc_type: MODIFY
feature_id: feature-0036-analysis-verification
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260731T121000 분석문 사실성 판정층 신규 (Minor, 백그라운드)

- **무엇:** 노드 분석문을 L0 통계 증거와 대조해 supported/contradicted/unverifiable 로 판정하고
  근거 한 문장과 함께 `node_analysis_verdicts` 에 저장한다.
- **왜:** 생성된 분석문의 사실성을 아무도 확인하지 않았다. 그것이 L2 요약의 입력이 되고 대화
  답변에 주입되므로, 아래층의 오류가 위로 전파되며 더 그럴듯해진다.

### 변경 파일

| 파일 | 변경 |
|---|---|
| `alembic/versions/20260731_0052_analysis_verdicts.py` | **신규** — CHECK 제약(3 verdict)·GRANT·인덱스 |
| `src/modules/analysis_verify.py` | **신규** — 대상 선정·증거 조립·판정·저장·정직성 방어 |
| `src/modules/llm.py` | `ANALYSIS_VERIFY_PROMPT` + `llm_verify_analysis` |
| `src/modules/insight.py` | 분석 tick 직전 판정 pass(자체 PG 연결) |
| `shared/config.py` · `shared/runtime_settings.py` | knob 2종(live) |
| `tests/test_analysis_verify.py` | **신규** 38건 |
| `tests/test_worker_parallelism.py` | `PERF_KEYS` +2 |

### 위험과 완화

| 위험 | 완화 |
|---|---|
| **잘못된 확인 도장** | 전 실패 경로에서 행 미생성. 테스트 절반이 이 축 |
| 근거 없는 판정 | `reason` 빈 값이면 기록하지 않음 |
| 잘못된 대조 대상 | node_key ↔ (scope,schema,table) 조인 + `error IS NULL` 이중 확인 |
| 재판정 누락 | 이전 판정 해시를 조회해 비교, 노드당 1행 유지 |
| 비용 폭주 | pass 상한 + 인자 우회 차단 + 항목별 예산 재확인 + 1건 1콜 |
| 워커 파손 | savepoint · `cursor()` try 안 · 전 경로 예외 흡수 |

### 배포 scope
워커(insight-worker) + web(설정). `make deploy-all`.
