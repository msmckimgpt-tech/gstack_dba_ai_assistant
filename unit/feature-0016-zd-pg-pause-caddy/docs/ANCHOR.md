---
doc_type: ANCHOR
feature_id: feature-0016-zd-pg-pause-caddy
created_at: 2026-06-30T15:00:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0016-zd-pg-pause-caddy

## §1. 외부 관점 요약
"PG 는 단일 인스턴스라 재시작=중단이라며? 그런데 왜 pg-restart 래퍼가 '무중단'이라 하지?" → 정확히는
**near-zero**다. pgbouncer(transaction-mode)를 PAUSE 하면 PG 가 잠깐 없는 동안 신규 RW 쿼리가 **에러
대신 큐잉**되고, PG 가 healthy 로 돌아와 RESUME 하면 큐가 풀린다. 즉 *PG 프로세스*는 재시작되지만
*클라이언트*는 짧은 지연만 본다(에러 0). config 변경/minor 재시작에 한함 — major/HA 는 여전히 범위 밖
(단일 호스트 SPOF). Caddy reconcile 은 feature-0014 라이브에서 적발한 inode-stale 함정(merge 가 파일을
새 inode 로 교체 → caddy bind-mount 가 옛 내용 재독)을 배포 스크립트가 자동 처리하게 한 것.

## §2. 대안 분기
- **Alt-A: PG 재시작 시 그냥 정비창.** 페르소나: 단순 운영. 안 고른 이유: config 변경은 잦을 수 있고
  pgbouncer 가 이미 있어 PAUSE/RESUME 으로 near-zero 가 저비용. 단 major 는 여전히 정비창.
- **Alt-B: 전용 pgbouncer admin user 신설.** 안 고른 이유(현재): agent_kb_rw 가 이미 userlist 에 있어
  최소 변경. 전용 admin 분리는 하드닝 후속(보안 §FUNCTION).
- **Alt-C: caddy 항상 reload.** 안 고른 이유: inode-stale 시 reload 가 옛 내용을 재독(무효). 또 무변경
  배포마다 reload 는 불필요. sha 비교로 변경 시에만 recreate 가 정확·최소.

## §3. 가정된 사용 시나리오
운영자가 PG 파라미터(예: work_mem)를 .env.postgres 에서 바꿨다. `make pg-restart` 한 줄이면 사용자가
대화 중이어도 RW 쿼리가 잠깐 멈췄다(에러 없이) 이어진다 — 운영자는 "재시작했는데 아무도 에러를 못 봤다".

## §4. 외부 검증 로그 (append-only)
(엔트리 없음 — 일반 TASK cycle 완료 조건 아님. PAUSE→restart→RESUME 라이브 실증은 배포 단계 §TEST 기록.)
