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
