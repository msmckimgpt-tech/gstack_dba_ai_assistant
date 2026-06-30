---
doc_type: ANCHOR
feature_id: feature-0015-zd-hygiene-backup
created_at: 2026-06-30T14:00:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0015-zd-hygiene-backup 무중단 위생 + 백업

## §1. 외부 관점 요약
"web 무중단(feature-0014)은 했는데, 왜 insight-worker graceful 이나 백업 복원 리허설 같은 자잘한 걸
또 하지? DB HA 부터 해야 하는 거 아닌가?" → 무중단 feasibility 분석(wf_1d634d33) 결론: 단일 호스트·
라이브 사용자 1명 맥락에서 **진짜 위험은 가용성(HA)이 아니라 데이터 보존**이고, 코드·expand 무중단은
이미 거의 달성됐다. 남은 가치는 전부 저비용 위생작업(①②⑤)이며, HA(멀티노드/failover)는 이 규모에
over-engineering 이다. 그래서 ①②⑤만 한다.

## §2. 대안 분기
- **Alt-A: DB HA(Patroni/replica failover) 도입.** 페르소나: 고가용 SaaS 팀. 안 고른 이유: PG/MySQL
  replica 가 동일 단일 호스트라 promote 자동화해도 호스트가 죽으면 같이 죽음 — HA 흉내일 뿐. 멀티호스트+
  오케스트레이터까지 가야 성립 → 1인 내부도구엔 ROI 음(-).
- **Alt-B: 기존 MySQL ALTER 전부 retrofit.** 페르소나: 일괄 정합 선호. 안 고른 이유: try/except 멱등
  가드에 LOCK=NONE 추가 시 비-online 에러가 silent-skip 될 수 있음 + 이미 적용분이라 가치 낮음 →
  diff-mode 게이트로 신규만 강제(grandfather).
- **Alt-C: 아무것도 안 하고 정비창 의존.** 안 고른 이유: ①②는 거의 0비용으로 무중단을 완성하고, ⑤는
  데이터 보존이라 정비창과 무관하게 필수.

## §3. 가정된 사용 시나리오
운영자가 어느 날 PG 데이터가 깨진 걸 발견한다. 매일 cron 백업이 있고, 매주 restore-rehearsal 이
"복원 가능"을 이미 검증해 뒀으므로, 운영자는 최신 백업을 throwaway DB 로 복원 → 검증 → 교체로 복구한다.
(리허설이 없었다면 "백업은 있는데 복원이 되나?"를 사고 시점에 처음 시험하는 최악을 맞았을 것.)

## §4. 외부 검증 로그 (append-only)
(엔트리 없음 — 일반 TASK cycle 완료 조건 아님.)
