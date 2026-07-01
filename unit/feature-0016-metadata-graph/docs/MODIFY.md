---
doc_type: MODIFY
feature_id: feature-0016-metadata-graph
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260701T120000-ai-claude-feature-0016-graphux5
- Date: 2026-07-01
- Related Requirement: REQ-20260701-graphux5 (관리콘솔 > 메타데이터 > 그래프 뷰 UX 4항목 개선)
- Summary: (1) 검색 유사도 명시 — pg_trgm 실측 score + 노드 라벨 `이름 NN%`·상세 헤더 배지. (2) AI 능동 분석 — 상세 패널 "✨ 능동 분석" 트리거 → insight-worker 백그라운드가 선택 노드에서 관련 노드를 **재귀 탐색**하며 노드별 LLM 분석(경계: depth/node 예산 + visited dedupe). (3) 미큐레이션 Table 더블클릭 시 컬럼 즉석 introspection. (4) 이웃 깊이 드롭다운 변경 시 즉시 재전개.
- Files: `shared/config.py`; `unit/feature-0002-agent-core/src/modules/{metadata_graph,node_analysis(신규),llm,insight}.py`; `unit/feature-0002-agent-core/alembic/versions/20260701_0026_node_analysis.py`; `unit/feature-0003-agent-web-ui/src/app.py`; `unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html,styles.css}`.
- Impact: 비파괴 추가(신규 테이블 `node_analysis_runs`/`node_analysis_jobs` + GRANT). 외부 LLM 비용은 능동 분석 트리거 시에만 발생(예산 캡). RBAC `kb.ingest.manual` 재사용. 기존 그래프/검색/투영 경로 회귀 0(검색 `score` 는 additive 필드).
- Rollback Notes: `alembic downgrade -1` 로 0026 DROP(관계형 SSOT·AGE 그래프 무영향). `AGENT_NODE_ANALYSIS_ENABLED=0` 으로 기능 비활성. 프론트는 admin.js/html 캐시버스터 revert.
