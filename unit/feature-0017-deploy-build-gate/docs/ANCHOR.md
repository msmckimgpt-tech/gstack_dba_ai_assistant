---
doc_type: ANCHOR
feature_id: feature-0017-deploy-build-gate
created_at: 2026-06-30T18:00:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0017-deploy-build-gate

## §1. 외부 관점 요약
"빌드 게이트가 `docker compose build` 의 exit code 를 믿는 게 당연한 거 아닌가? 왜 exit code 를
무시하게 만들지?" → 이 호스트는 **snap 설치 docker** 라, strict confinement 때문에 compose CLI 와
BuildKit 데몬이 빌드 metadata 파일을 서로 다른 `/tmp` mount namespace 에서 쓰고/읽어, 이미지는 정상
산출·태깅됐는데도 CLI 가 metadata 파일을 못 찾아 **EXIT 1** 을 반환한다. 즉 exit code 가 이 환경에선
빌드 성공의 신뢰 신호가 아니다. 그래서 "이미지가 실제로 존재하고 GIT_COMMIT 라벨이 맞는가" 를 1차
신호로, exit code 는 보조로 쓴다. (이미 `dc-build`/`make up` 이 같은 우회를 쓰고 있었는데, 신규
deploy-web.sh 만 빠져 있었다.)

## §2. 대안 분기
- **Alt-A: docker build(buildx) 직접 호출로 compose 우회.** 안 고른 이유: pin overlay(build-once) 통합을
  잃고 코드베이스 패턴(compose build)에서 이탈. image-verify 보강이 더 작고 정합적.
- **Alt-B: snap docker confinement 정비 / apt docker-ce 이전.** 안 고른 이유: 시스템/admin 영역(코드
  수정 범위 밖, 사용자 결정). 코드 게이트 보강이 환경 무관하게 즉효.
- **Alt-C: 그냥 `|| true` 로 exit 무시.** 안 고른 이유: 진짜 빌드 실패까지 통과시킨다. 마커+이미지정합
  2중 조건으로 false-failure 만 정밀 흡수.

## §3. 가정된 사용 시나리오
운영자가 PR 머지 후 `make deploy-web` 을 돌린다. 이전엔 매번 "이미지 빌드 실패. ABORT" 로 죽어 신규
코드가 영영 안 나갔다. 수정 후엔 metadata-race 가 나도 게이트가 "이미지 정상 산출 — race 양성 무시"
로 통과해 롤링 swap 까지 완주하고, 정작 컴파일 에러 같은 진짜 실패는 여전히 ABORT 한다.

## §4. 외부 검증 로그 (append-only)
(엔트리 없음 — 일반 TASK cycle 완료 조건 아님. 라이브 end-to-end 배포 검증은 §TEST 기록.)
