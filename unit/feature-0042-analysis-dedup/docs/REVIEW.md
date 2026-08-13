---
doc_type: REVIEW
feature_id: feature-0042-analysis-dedup
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260814-0001
- Related Change: ROADMAP T4 등재 (ITEM-13/14/15) + batch 기각
- Reason: 사용자 질문("워커 LLM 요청을 batch 로")을 두 해석으로 분리해 각각 실측 기각한 뒤,
  그 검토가 드러낸 요청당 낭비(입력 80%가 고정 프롬프트)를 회수할 후보를 등재했다.
- Alternatives Considered:
  - Message Batches API — 기각(전송 경로 부재 · 구독형이라 50% 할인 가치 0 · 24h SLA 불일치)
  - 다건 묶기 — 기각(출력 미절감으로 max_tokens 초과 · per-job 상태기계 붕괴).
    같은 결론이 `analysis_verify` docstring 에 이미 있었다("배치하면 한 건의 오판이 다른 건으로 번진다")
- Risks: 등재 항목의 전제가 착수 시점에 반증될 수 있음 → REV-0002 에서 실제로 발생
- Open Questions: 없음
- Human Approval Needed: 아니오 (사용자가 등재·착수를 명시 승인)

## REV-20260814-0002
- Related Change: ITEM-13(형제 dedup) in-progress → **rejected**
- Reason: 등재 근거였던 "중복률 69.3%"는 **이름** 중복률이었다. 착수 직후 측정한 **내용** 중복률은
  사실상 0 이다(`AccountId` 261잡 → distinct summary 260). 샘플 육안 확인 결과 그 차이는 부모 테이블
  맥락을 반영한 유의미한 정보였고, 형제 상속은 절감이 아니라 정보 손실이다.
- Alternatives Considered:
  - 이름+fingerprint 이중 축으로 좁혀 적용 — 현 데이터에서 그 조건을 만족하는 형제가 드물 것으로
    보여(위 실측이 방증) 비용 대비 효과 불명. 재논의 조건으로만 남김
  - 그대로 구현 강행 — 기각. 관측된 반증을 무시하는 구현은 회귀를 만든다
- Risks: 사용자에게 1순위로 제시한 항목을 착수 직후 철회 — 방향 전환이므로 즉시 표면화함
- Open Questions: payload 구조 동일성 축의 실제 히트율(측정 미실시 — 재논의 시 선행 조건)
- Human Approval Needed: 예 — 기각 판단 자체는 기술적 반증에 근거하나, 우선순위 변경은 사용자 확인 대상

## REV-20260814-0003
- Related Change: ITEM-14 캐싱 검증 스파이크 done + ITEM-15 방향 확정
- Reason: 코드 변경 전에 전제를 관측으로 확정하는 것이 이 initiative 의 규약(ADR-0032 계열)과 정합.
  프로브 결과 litellm passthrough 는 **동작**하고, 4,096 하한 미달은 **무음 실패**함이 재현됐다.
  이로써 ITEM-15 의 방향이 "프롬프트 축소"에서 "캐시 가능 형태로 재구성"으로 **반전**됐다 —
  축소하면 캐시는 영영 발동하지 않기 때문이다.
- Alternatives Considered:
  - 프로브 없이 ITEM-15 착수 — 기각. 축소/확대 중 어느 방향인지 모르는 채 프롬프트를 건드리면
    한쪽이 다른 쪽을 무효화한다(ROADMAP §1 T4 주석에 명문화)
  - 억지 padding 으로 하한 넘기기 — 채택 안 함. few-shot 예시로 정당하게 넘기는 안을 ITEM-15 what 에 확정
- Risks: 프롬프트를 키우면 캐시 미스 시 입력이 오히려 늘어난다 — 5분 TTL 창에 2회 이상 호출이면
  손익분기를 넘고, 워커는 60초 tick 이라 정상 경로에서 충족된다. 다만 캐시 미발동 fail-open 확인이
  ITEM-15 acceptance 에 포함되어야 한다(명시함)
- Open Questions: 구독 한도 회계 반영 여부(프로브로 판정 불가 — 미확정으로 기록)
- Human Approval Needed: 예 — ITEM-15 착수 여부(안전망 확보 방식 선택)

## REV-20260814-0004 [SKIPPED:non-policy-doc]
- Related TASK: feature-0042-analysis-dedup
- Reason: changed paths are docs/comments only outside policy-doc list —
  변경 파일이 `docs/improvements/analysis-orchestration/ROADMAP.md` 와
  `unit/feature-0042-analysis-dedup/docs/**` 뿐이고 코드 변경 0건이다.
  정책 doc(AGENTS.md · CLAUDE.md · `_template/` · `bin/` · `settings.json` · `docs/CONVENTIONS.md`)
  은 포함되지 않아 §18.8 verification panel 대상이 아니다.
  판정의 근거가 되는 실측은 REV-0002·0003 과 TEST.md §3 Run 에 수치로 남겼다.
- Timestamp: 2026-08-13T23:19:02Z

## REV-20260814-0005 [SKIPPED:non-policy-doc]
- Related TASK: feature-0042-analysis-dedup
- Reason: changed paths are docs only outside policy-doc list — ITEM-15 선행 안전망 방식 확정
  (ROADMAP + REPORT + TASK + MODIFY). 코드 변경 0건이라 §18.8 panel 대상이 아니다.
  판단 근거: 두 선택지 중 증거 커버리지 확대는 **착수 시점을 통제할 수 없어**(워커가 채우는 축,
  현재 1.3%) ITEM-15 를 무기한 대기시킨다. 출력 계약 회귀 테스트는 지금 만들 수 있고 LLM 없이
  결정론적으로 판정하므로 unblock 수단으로 우월하다. 두 축은 배타적이지 않다.
- Timestamp: 2026-08-13T23:19:02Z
