---
run_at: 2026-07-13T11:35:00+09:00
session: ai/claude/feature-0016-content-cluster
scope: unit
verdict: PASS
---

# Run — content-cluster 단위·회귀 (컨테이너 pytest)

- 환경: repo-insight-worker:latest 이미지 + worktree 마운트(PYTHONPATH), pytest·numpy 런타임 설치. DB/AGE/LLM 무의존(monkeypatch·fake).
- 신규 `unit/feature-0002-agent-core/tests/test_semantic_cluster_content.py` **16 PASS**:
  RC1(numpy 부재 1회 WARNING) · RC2(DB 단위 분할·N 가드 국소화·skip 스키마 기존 배정 보존) ·
  RC3(루틴 시그니처 빌더·백필 멱등·0040 미적용 soft-skip·테이블+루틴 합동 id·sync_routine 투영 _UNSET/None/값 3분기) ·
  RC4(analysis 줄 조건부 append — 미분석 시그니처 legacy byte-동일·JSON str/dict 파싱) ·
  RC5(kv 캐시 적중 시 LLM 무호출·미스 배치 호출+캐시 적재·fail-soft·게이트 OFF·라벨 위생·멤버셋 해시 순서불변).
- 연관 스위트: test_graph_category_recursive_refine.py + test_routine_sync_crossdb.py 포함 **70 PASS**.
- 전체 스위트(unit/feature-0002 tests + feature-0003 tests) 컨테이너 pytest **EXIT=0**(전건 PASS, 실패 0).
- py_compile: semantic_cluster.py·metadata_graph.py·llm.py PASS.
- 잔여: POST-DEPLOY 라이브 실증(cc_data_main 백필→클러스터 DB 카운트) + PB-0008 실 Windows 육안(Environment: Windows-browser Run 은 배포 후 별도 fragment).
