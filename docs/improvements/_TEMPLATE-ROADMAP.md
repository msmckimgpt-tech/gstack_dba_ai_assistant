---
doc_type: DQA_ROADMAP
initiative: <slug>
created_at: <YYYY-MM-DD>
source_research: ./RESEARCH.md
status: active
schema_version: 1
---

# 개발 로드맵 — <initiative>

> `improve_listup` 산출 스키마 템플릿. **다른 세션이 0 맥락으로 읽고 착수 가능**해야 한다 — 모호어 금지, 구체 동작·데이터모델·검증식으로.

## 0. 맥락 (context-free 진입)
<이 로드맵이 왜 존재하는지 3~5줄.>
- 대상 제품: <한 줄 정체성>
- 정본 진입: repo/AGENTS.md · docs/PROJECT.md · docs/ARCHITECTURE.md
- 측정 기반(있으면): <평가 harness 위치/명령>

## 1. 종속성 그래프
```
ITEM-01 ──requires──▶ ITEM-03
ITEM-02 ──enables───▶ (전 성능항목)
```

## 2. Phase 시퀀스
| Phase | 포함 ITEM | 병렬? | 진입 조건 |
|---|---|---|---|
| P0 | ITEM-02 | — | (없음) |

## 3. 항목 (각 1 cycle)

### ITEM-01 · <제목>
- **status**: pending        <!-- pending | in-progress | done | blocked. awaiting-merge 는 status 아님 → note 로 -->
- **feature_id**: feature-NNNN-<slug>   <!-- cycle-init --feature / verify <feature-id> 동일 사용. ITEM-id 금지 -->
- **dimension**: structural | performance | functional | operational
- **risk_grade**: Minor | Major | Critical   <!-- Major/Critical 은 무인 cycle 자동 blocked(사람 승인) -->
- **depends_on**: []
- **enables**: []
- **why**: <RESEARCH finding 인용 + 정합 verdict 요지>
- **fit_verdict**: adopt | adopt-with-guard (+ guard)
- **what**: <구현 동작 구체. 데이터모델은 테이블/컬럼까지.>
- **entry_points**: <file:line / 모듈 — 재사용 자산 포함>
- **acceptance**: <완료 판정식 + 검증 방법(테스트/측정/라이브). 가능하면 수치.>
- **guards**: <조건부 항목의 필수 가드>
- **effort**: 小 | 中 | 大
- **notes**: <함정·배포 scope 등>

## 4. 보류·기각 (재논의 방지)
| finding | verdict | 사유 |
|---|---|---|

## 5. 진행 현황 (improve_cycle 갱신)
- 총 <N> · done <x> · in-progress <y> · pending <z> · blocked <w>
- 다음 ready: <ITEM id>
