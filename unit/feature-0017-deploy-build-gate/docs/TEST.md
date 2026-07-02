---
doc_type: TEST
feature_id: feature-0017-deploy-build-gate
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Scope
- 포함: build 게이트의 metadata-race false-failure 양성무시 + 진짜 빌드 실패 ABORT(음성 보존) + end-to-end
  롤링 배포 완주. 제외: snap confinement 정비(시스템 영역).
- 인프라/배포 — 서버 계약(CLI).

## 2. Test Cases
### TEST-20260630T180000-metadata-race-absorb-1 (positive)
- Purpose: compose build 가 metadata-race 로 EXIT≠0 이나 이미지 정상 산출 시 게이트가 통과.
- Steps: main repo(.env)에서 pin overlay(artifacts/) + `docker compose build web-a` 재현 → 게이트 판정.
- Expected: EXIT=1 + 이미지 GIT_COMMIT 라벨==sha + 마커 검출 → PASS(양성무시).

### TEST-20260630T180000-real-failure-abort-2 (negative)
- Purpose: 진짜 빌드 실패(이미지 부재/마커 없음)는 여전히 ABORT.
- Steps: 존재 안 하는 sha 로 image inspect → GIT_COMMIT 빈값 → 게이트 판정.
- Expected: ABORT(false-positive 없음).

### TEST-20260630T180000-e2e-rolling-3
- Purpose: 수정 후 deploy-web.sh 가 롤링 swap 까지 완주 + /readyz git_commit 전환.
- Steps: 머지 후 `sudo -E bin/deploy-web.sh`.
- Expected: build 게이트 통과 → web-a→web-b 롤링 → /readyz git_commit==origin/main HEAD, edge 200, 무중단.

## 3. Test Runs (append-only)
### Run 2026-06-30 — Environment: CLI (격리 검증, main repo .env 재현)
- bash -n bin/deploy-web.sh: OK.
- **positive**: `docker compose -f docker-compose.yml -f <pin(artifacts)> build web-a` → EXIT=1, 로그
  `open /tmp/.tmp-compose-build-metadataFile-…: no such file or directory`(정확한 보고 에러), 이미지
  `mysql-ai-web:<sha>` GIT_COMMIT 라벨==sha, 마커 검출 → 새 게이트 **PASS(양성무시)**. ✓
- **negative**: 존재 안 하는 sha → image inspect GIT_COMMIT 빈값 → **ABORT** (진짜 실패 보존). ✓
- (하네스 메모) 테스트 pin 을 /tmp 에 두면 snap-docker 가 /tmp(private ns) 를 못 읽어 compose 가 pin
  자체를 못 염 → 실제 PIN_FILE 위치(artifacts/deploy/)는 snap 접근 가능(라이브 bind-mount 가 사용 중).
### Run (예정) — Environment: CLI (라이브, 배포 시)
- TEST-...-3 (end-to-end 롤링 swap + /readyz 전환) — 머지 후 deploy-web.sh 실행 기록.

## 4. 미수행 사유
- end-to-end 는 본 수정이 origin/main 에 머지된 뒤 deploy-web.sh(origin/main coalesce)로 수행.

### Run 2026-07-02 — Environment: CLI (migrate 게이트 race 관용 격리 검증)
- 대상: CHG-20260702T160000 migrate_phase 재시도 tolerance. **PB-0008 Windows-browser: N/A** — `bin/deploy-web.sh` 셸 스크립트만 변경, HTML/CSS/JS 등 UI 표면 0 → 화면 렌더 검증 대상 없음(CHECK#13 skip 대상).
- 정적: `bash -n bin/deploy-web.sh` PASS. DRY_RUN/MIGRATE_RETRY_BACKOFF `set -u` 안전(DRY_RUN=0 정의, backoff default).
- 격리 3케이스(mock alembic-migrate exit code, deploy-web migrate_phase 골격 재현):
  1. 1차 ok(exit 0) → 재시도 없이 proceed. PASS.
  2. 1차 실패(1)·재시도 ok(0) → race 관용, proceed(head 도달). PASS.
  3. 양쪽 실패(1,1) → `die` "ABORT", swap 미진입(proceed 미출력, rc=1). PASS.
- §18.8 SUBAGENT 적대 패널 VERDICT PASS(BLOCKING 0) — 미적용 swap·진짜실패 은폐·멱등성·set-e/die·문법 5축 refute. NIT-2(backoff)·NIT-1(head-anchored 명시) 흡수. REV-20260702T160000-deploy-migrate-gate.
- 라이브 end-to-end: eadb4a9e 재배포에서 migrate 게이트 "pending 없음"(head=0030) 통과 경로 관측. 신규 revision 배포 시 재시도 tolerance 자연 검증 예정.
