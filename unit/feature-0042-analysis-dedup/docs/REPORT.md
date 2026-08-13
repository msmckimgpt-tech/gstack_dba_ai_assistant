---
doc_type: REPORT
feature_id: feature-0042-analysis-dedup
status: active
edit_policy: rewrite
source_of_truth: false
---

# Current Report

## 1. Summary

조사·검증 cycle 완결. **코드 변경 0건**, 산출물은 판정이다.

batch 두 해석을 모두 기각하고, 그 검토가 드러낸 요청당 낭비(입력의 약 80%가 고정 시스템 프롬프트)를
회수할 후보 3개를 ROADMAP T4 로 등재했다. 등재 직후 각 후보의 전제를 실측으로 재검사한 결과
**1개는 기각(전제 반증), 1개는 완료(전제 확정), 1개는 방향 확정 후 착수 보류**다.

## 2. Progress
- Planned: ITEM-15 (프롬프트 캐시 재구성 — 안전망 확보 후)
- In Progress: 없음
- Done: batch 판정 · ROADMAP T4 등재 · ITEM-13 기각 · ITEM-14 캐싱 스파이크

## 3. Recent Changes
- ROADMAP T4 신설(ITEM-13/14/15) + §1 종속성·§2 Phase·§4 기각표·§5 진행현황 갱신
- ITEM-13 rejected (근거: 동명 노드 분석문 distinct 99.6~100%)
- ITEM-14 done (근거: 캐시 발동/무음 실패/대조군 3조건 관측)
- ITEM-15 방향 반전(축소 → 캐시 가능 재구성) + 잔여 차단사유 1건으로 축소
- 총 변경 횟수: 1

## 4. Open Issues

- **ITEM-15 착수 조건 미확보** — 프롬프트를 바꿀 때 품질 회귀를 관측할 수단이 없다.
  `node_analysis_verdicts` 140건 · 증거 커버리지 `metadata_table_stats` 152행/12,088잡(1.3%) ·
  프롬프트 출력 계약 회귀 테스트 0건. 선행 선택지 두 가지:
  (a) ITEM-11 플래너로 증거 커버리지 확대 → verdict 표본 확보
  (b) 출력 계약(JSON 필드 존재·`caveats` 빈값 규칙 등)을 고정하는 최소 회귀 테스트 신설
- **구독 한도 회계 미확정** — 캐시 읽기 0.1× 가 OAuth 구독 사용량 한도에 반영되는지 불명.
  `usage`·헤더에 노출되지 않아 프로브로 판정 불가. 절감 효과 추정의 상한 불확실성으로 남는다.
- **캐시 계측 부재** — `_record_llm_usage` 가 `cache_creation_input_tokens` /
  `cache_read_input_tokens` 를 저장하지 않는다. ITEM-15 착수 시 동반 필요(효과 관측 수단).

## 5. Test Status
- 자동 테스트: 신규 없음(코드 변경 0건). 기존 회귀 영향 없음 — 변경 파일이 전부 문서다
- 수동 테스트: 라이브 프로브 3조건 × 2회 PASS · dedup 전제 검증 FAIL(의도된 반증)
- 미검증 항목: 구독 한도 회계 · 프롬프트 변경 시 품질 영향(표본 부족)

## 6. Blocked Items
- ITEM-15: BLOCKED: verification-sample-insufficient (위 §4 참조)

## 7. Notes

feature 이름의 `dedup` 은 cycle 착수 시점의 1순위 후보에서 유래한다. 그 후보가 기각되어
이름과 실제 산출물이 어긋나지만, 브랜치·worktree·REGISTRY 가 이미 그 slug 로 생성돼 있어
개명에 따른 도구 마찰이 더 크다고 판단해 유지했다. 실제 범위는 FUNCTION.md §1 이 정본이다.
