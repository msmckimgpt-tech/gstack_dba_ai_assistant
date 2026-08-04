---
doc_type: DECISIONS
feature_id: feature-0039-ops-scheduler
status: active
edit_policy: append-only
source_of_truth: true
---

# Decisions

## ADR-20260804T104000-ops-jobs-in-service
- **Status**: accepted
- **Context**: 정기 운영 잡 4종이 호스트 root crontab 에서 실행. root 근거는 래퍼의
  `docker exec` + docker 소켓 root 독점 하나.
- **Decision**: 잡 로직을 agent 이미지 안으로 옮기고 전용 `ops-scheduler` compose 서비스가
  스케줄링한다. 스케줄 정본은 compose 환경변수(`OPS_SCHED_*`).
- **Consequences**: (+) root 권한 근거 소멸, 스케줄이 버전관리·배포에 편입, `compose up` 만으로
  정기 잡 가동. (−) 컨테이너 1개 증가, 이미지에 pg client 추가(외부 apt 저장소 의존 +1).
- **Alternatives**: docker 소켓 마운트(→ 컨테이너→호스트 root 승격 경로라 배제) ·
  insight-worker 편입(→ 백업 I/O 가 워커 health·mem 정책과 교착) · docker 그룹 일반계정
  강등(→ docker 그룹 = 실질 root, 권한 축소 아님).

## ADR-20260804T104200-pgdump-major-pin
- **Status**: accepted
- **Context**: 네트워크 클라이언트 전환 시 pg_dump 버전이 서버와 분리된다. Debian trixie 는
  client-17 만 제공하고, 그 산출물은 PG16 복원 시 `SET transaction_timeout` 로 실패(실측).
- **Decision**: PGDG 저장소에서 `postgresql-client-16` 을 고정 설치해 서버 메이저와 정합.
- **Consequences**: 이미지 빌드에 `apt.postgresql.org` 의존 추가. 서버 메이저 업그레이드 시
  본 핀을 함께 올려야 한다(그러지 않으면 복원 불가가 조용히 재발).

## ADR-20260804T104300-flock-bind-mount
- **Status**: accepted
- **Context**: AGE sync 의 §82 동시성 가드는 호스트에 남는 `bin/routine-backfill.sh` 와
  공유하는 flock 이다. 잡이 컨테이너로 가면 lock 공간이 갈라진다.
- **Decision**: 호스트 lock 디렉터리를 컨테이너에 bind-mount 해 **같은 inode** 를 잡는다
  (flock 은 inode 단위). 마운트 부재 시 sync 실행 거부(fail-loud).
- **Consequences**: compose 에 호스트 경로(`OPS_LOCK_DIR`, 기본 `/root/.locks/...`) 노출.
  PG advisory lock 전환은 `routine_backfill` 동반 수정이 필요해 보류.
