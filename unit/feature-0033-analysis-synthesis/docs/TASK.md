---
doc_type: TASK
feature_id: feature-0033-analysis-synthesis
status: active
edit_policy: rewrite
source_of_truth: true
feature_status: in-progress
---

# Task

## 1. Current Status
- State: in-progress (ITEM-07 구현 완료, 검증 중)
- Owner: AI (claude)
- Priority: high
- Last Updated: 2026-07-30

## 2. Implementation Plan

### 2.1 Plan
- **영향받는 파일:** `unit/feature-0002-agent-core/alembic/versions/20260730_0051_cluster_summaries.py`(신규) ·
  `src/modules/llm.py`(요약 프롬프트·함수) · `src/modules/semantic_cluster.py`(생성·캐시·배선) ·
  `shared/{config,runtime_settings}.py` · `tests/test_cluster_summary.py`(신규) ·
  `unit/feature-0003-agent-web-ui/docs/test-runs.d/*`(PB-0008 fragment PASS 갱신) ·
  `docs/improvements/analysis-orchestration/ROADMAP.md`
- **접근 방법:** 클러스터가 확정된 시점(병합·재정렬·라벨 확정 후)의 멤버셋으로 합성 요약을
  생성해 신규 `cluster_summaries` 에 적재한다. 캐시 키는 **멤버셋 지문 + L1 지문 + L0 지문**
  3중이며, 요약은 클러스터링 시그니처에 유입되지 않는다.
- **위험도:** Major — 신규 LLM 지출 경로(818 클러스터). 완화: pass 당 40개 상한 · 백그라운드
  토큰 예산(feature-0032) 하위 · `acquire("llm")` 게이트 · live 정지 스위치 · 실패는 pass 중단
  (부분 성공 유지) · 요약 실패가 클러스터링·라벨 역기록을 막지 않음.

<!-- PLAN-APPROVED by mckim on 2026-07-30 (요청: "자율적으로 판단하여, 모든 트랙 완주까지" + "continue") -->

### 2.2 근거
`docs/improvements/analysis-orchestration/ROADMAP.md` ITEM-07. 진입 조건이던 토큰 cap 재평가는
ITEM-12 로 완료됐다.

## 3. Task Queue

- [x] TASK-0001 라이브 클러스터 실측(818개 · 15,365 멤버 · 라벨 평균 9자)
- [x] TASK-0002 `cluster_summaries` alembic additive 신규(멤버셋 해시 PK · 2중 버전 · GRANT)
- [x] TASK-0003 `CLUSTER_SUMMARY_PROMPT` + `llm_cluster_summary()` — 라벨과 별 계약
- [x] TASK-0004 생성 로직 — 3중 캐시 키 · 결정적 정렬 · pass 상한 · 배치 6 · LLM 예산 게이트
- [x] TASK-0005 클러스터 확정 시점 배선(일관성 경계) + 요약 실패 격리
- [x] TASK-0006 콘솔 live 정지 스위치 `AGENT_METADATA_CLUSTER_SUMMARY`
- [x] TASK-0007 테스트: 캐시 3중 계약 · 정렬 결정성 · 비용 유계 · 시그니처 미유입 · 정직성
- [ ] TASK-0008 적대 리뷰 → verify → PR → CI → 머지 → 배포 → 라이브 생성 확인

## 9. Requested Scope (요청 범위 자기-열거)

사용자 지시: "자율적으로 판단하여, 모든 트랙 완주까지 작업을 진행해주세요" + "continue".
본 cycle 은 ROADMAP T2 의 첫 항목(ITEM-07)이다.

- [x] `L2 클러스터 요약 생성` — 산출물: `cluster_summaries` + `_llm_cluster_summaries` ·
      배선 확인: 캐시 3중 계약·상한·배치를 테스트로 단정
- [x] `신규 저장 계약(라벨 확장 아님)` — 산출물: alembic 0051 · 배선 확인: 라벨은 kv/32자,
      요약은 테이블/2~4문장으로 계약이 분리됨
- [x] `2중 버전 키` — 산출물: `l1_version`·`evidence_version` · 배선 확인: 각각 단독 변경 시
      재생성됨을 테스트로 단정
- [x] `시그니처 미유입 불변식` — 산출물: 배선 부재 · 배선 확인: 시그니처 빌더 소스에 요약 참조가
      없음을 테스트로 단정(순환 차단)
- [x] `결정적 정렬` — 산출물: `_version_hash` 정렬 + 멤버·분석문 정렬 · 배선 확인: 순서 무관
      동일 지문 테스트
- [x] `커버리지 정직성` — 산출물: `member_count`/`analyzed_count` 저장 + payload 전달 ·
      배선 확인: 20개 중 3개 케이스 테스트
- [ ] `배포·라이브 생성 확인` — 산출물: `TBD` · 배선 확인: `TBD`
- [x] `직전 cycle 문서 마감` — 산출물: PB-0008 fragment 2건 PASS 갱신 + ROADMAP ITEM-12 done ·
      배선 확인: 실제 Windows 브라우저 검증 결과·증거 스크린샷 첨부

**주장 affordance 실측 (G3)**: 본 cycle 은 사용자 대면 UI 를 추가하지 않는다(요약은 저장까지가
범위이며 표시는 ITEM-09 소관). 콘솔에 새로 나타나는 것은 정지 스위치 1개이고, 실제 게이트
(`_summary_enabled()` → `_llm_cluster_summaries` 조기 반환)를 가지며 테스트가 단정한다.

**경계변수 양측 검증 (G4)**:
- `_SUMMARY_MAX_PER_PASS`(40) → 미만 = 전량 생성 / 초과 = 정확히 40개만 + 큰 클러스터 우선
- `_SUMMARY_CLUSTERS_PER_CALL`(6) → 배치마다 ≤6 개
- 요약 길이 하한(20자) → 미만 = 미저장(다음 pass 재시도) / 이상 = 저장
- 캐시 3중 키 → 전부 일치 = 재생성 0 / L1 만 변경 = 재생성 / L0 만 변경 = 재생성 / 멤버셋 변경 = 재생성
