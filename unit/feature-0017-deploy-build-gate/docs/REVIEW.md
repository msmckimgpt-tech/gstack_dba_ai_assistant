---
doc_type: REVIEW
feature_id: feature-0017-deploy-build-gate
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260630T180000-deploy-build-gate
- Related Change: CHG-20260630T180000 (build 게이트 image-verify 보강)
- Reason: snap-docker metadata-file race 로 deploy-web.sh 가 모든 web 배포를 false-failure 차단.
- Alternatives Considered: docker build 직접호출(pin 통합 상실), snap confinement 정비(시스템 영역),
  `|| true`(진짜 실패 통과 위험) — 모두 불채택. image-verify+마커 조건부 흡수가 최소·정합·안전.
- Risks: **false-positive(실패 빌드 통과)** 가 최대 위험 → 양성무시는 (EXIT≠0)·(이미지 존재+GIT_COMMIT
  ==sha)·(로그 metadata-race 마커) **3중 AND** 로만. 마커는 `naming...done`(태깅 성공) 이후에만 나오므로
  진짜 빌드 실패는 마커 없음→ABORT. swap 후 /readyz git_commit==target 2차 방어. swap/rollback/soak 무변경.

## REV-20260630T180500-build-gate-review [SKIPPED: 검증패널 인프라/세션한도 반복 실패 — main-loop 자체검토 + 격리 positive/negative + 라이브 end-to-end 대체]
- Related Change: CHG-20260630T180000
- 사유: 직전 cycle 들에서 §18.8 검증 패널 subagent 가 (프로세스 종료/세션 한도)로 반복 미완. 본 변경은
  단일 함수 게이트(~25줄)이고 격리 검증(positive/negative)을 실 환경 재현으로 마쳤으며, 머지 후 라이브
  end-to-end 가 최종 증거이므로 main-loop 자체검토 + 라이브로 대체.
- 자체검토(적대 각도):
  1. **false-positive 차단**: 양성무시 3중 AND(EXIT≠0·이미지GIT_COMMIT==sha·metadata 마커). 컴파일
     에러 등 진짜 실패는 `naming...done` 전에 죽어 이미지 부재+마커 없음→ABORT. ✓
  2. **stale 이미지 masquerade**: 마커는 태깅 성공 이후에만 출현 → 마커 있음=이 빌드가 태깅까지 도달.
     이전 stale 이미지만으로는 마커 없어 통과 불가. ✓
  3. **set -e/pipefail**: 빌드 구간만 `set +e +o pipefail`/복원, `PIPESTATUS[0]` 로 compose rc 포착. ✓
  4. **provenance**: Dockerfile `ENV GIT_COMMIT` 존재 → 라벨 검증 유효. /readyz 2차 방어. ✓
  5. **범위**: build_image 게이트 1곳만, swap/rollback/soak 무변경.
- 격리 검증 결과(실 환경 재현): positive EXIT=1+이미지정상+마커→PASS(양성무시), negative 부재→ABORT.
- Human Approval Needed: 아니오 (PLAN-APPROVED). 라이브 end-to-end 는 사용자 배포 승인 범위.

## REV-20260702T160000-deploy-migrate-gate [SUBAGENT:deploy-migrate-gate-race-tolerance]
- Related Change: CHG-20260702T160000 (migrate 게이트 race 관용 — build 게이트 계보 확장)
- 검증 성격: 배포 스파인 migrate 게이트. 최대 위험 = **미적용 스키마로 swap**(데이터 정합) / **진짜 실패 은폐**.
- §18.8 SUBAGENT 적대 패널 VERDICT **PASS (BLOCKING 0)** — 5축 refute:
  - (미적용 swap, 최치명) refute: 재시도 exit 0 = head 도달 **참으로 보장**. alembic-migrate.sh upgrade 는 no-pending(live_current 로 실 alembic_version==head 확인) 또는 apply(ON_ERROR_STOP=1 psql 성공) 로만 exit 0. gen_sql race 는 `sql=$(gen_sql)` 의 `set -e` 로 즉시 die → false no-op 불가.
  - (진짜 실패 은폐) refute: gen-time(잘못된 revision/의존성) alembic 오류·apply-time(잘못된 DDL) psql ON_ERROR_STOP 실패는 **양쪽 시도 모두 die**. 2차 exit 0 은 DB-anchored 라 1차 진짜 실패를 우연히 덮지 못함.
  - (멱등성) refute: head 도달 시 재실행 no-op(DB 무접촉). 단건 적용 atomic(BEGIN..COMMIT + version UPDATE 1세션). alembic-migrate.sh 미변경(diff: bin/deploy-web.sh only).
  - (set -e/die/run) refute: `if ! run …; then … run … || die; fi` 3케이스 격리 재현 — 1차ok→swap(재시도無)/1차실패·재시도ok→관용·swap/양쪽실패→die·no swap.
  - (문법/dry-run) refute: bash -n clean, dry-run 은 `run` 이 0 반환 → retry 블록 미진입.
- NIT 처리: **NIT-2(backoff) 반영** — `sleep ${MIGRATE_RETRY_BACKOFF:-5}`(dry-run skip)로 같은 race window 재적중 완화. **NIT-1(marker-gating 대비 blind retry)** — head-도달 검증을 정합근거로 **의도적 채택**(marker-only 는 self-healing transient 를 false-ABORT 해 더 약함; head 도달은 원인 무관 swap 안전을 참 보장). 주석 + 본 REV 에 근거 기록.
- 격리 검증(3케이스, mock exit code): 1차ok(1콜·proceed) / 1차실패·재시도ok(관용·proceed) / 양쪽실패(die·no swap). 전부 PASS + bash -n PASS.
- Human Approval Needed: 아니오(PLAN-APPROVED 계보, build 게이트와 동형 저위험). 라이브 end-to-end 는 다음 배포에서 자연 검증(이미 eadb4a9e 재배포로 migrate 게이트 통과 경로 관측).
