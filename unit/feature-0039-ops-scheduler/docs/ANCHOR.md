---
doc_type: ANCHOR
feature_id: feature-0039-ops-scheduler
created_at: 2026-08-04T01:40:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0039-ops-scheduler 운영 정기 잡 인-컨테이너 이관

## §1. 외부 관점 요약

"백업이랑 그래프 sync 는 host cron 에서 잘 돌고 있었는데, 왜 굳이 컨테이너 서비스로 옮기지?
스케줄러를 하나 더 만들면 관리 지점만 늘어나는 것 아닌가?" → 문제는 스케줄링이 아니라
**실행 주체의 권한**이다. 기존 래퍼는 전부 `docker exec` 로 DB 컨테이너에 들어가는 구조였고,
이 호스트는 docker 소켓 접근이 `root` 에만 있어 잡이 필연적으로 root crontab 에 묶였다
(설치 스크립트가 "반드시 sudo" 를 요구한 근거가 그것 하나였다). 잡을 서비스 안으로 옮기면
docker 소켓 의존이 사라져 root 권한 근거가 소멸하고, 스케줄·잡 정의가 crontab(호스트 상태,
버전관리 밖)에서 `docker-compose.yml`(버전관리 안)로 이동해 배포와 함께 따라간다.

## §2. 대안 분기

- **Alt-A: 컨테이너에 docker 소켓을 마운트하고 기존 래퍼를 그대로 컨테이너에서 실행.**
  페르소나: "코드를 최소로 바꾸고 싶은" 운영자. 안 고른 이유: docker 소켓은 컨테이너→호스트
  root 승격 경로다. root 를 없애려는 작업이 **더 넓은 root 노출**을 만드는 자기모순.
- **Alt-B: insight-worker 의 기존 tick 루프에 잡을 편입 (신규 컨테이너 0).** 페르소나: 컨테이너
  수를 늘리기 싫은 운영자. 안 고른 이유: 761MB pg_dump 가 워커의 `mem_limit 1g`·heartbeat
  healthcheck·`restart: on-failure:3` 정책과 얽혀, 백업 실패가 워커 장애로 오진되고 그 반대도
  성립한다. 장애 진단면이 섞이는 비용 > 컨테이너 1개 비용.
- **Alt-C: host cron 유지 + 실행 계정만 docker 그룹 일반 사용자로 강등.** 페르소나: 최소 변경
  선호. 안 고른 이유: docker 그룹 = 실질 root 이므로 권한 축소가 아니다. 그리고 스케줄이
  여전히 버전관리 밖 호스트 상태로 남아 배포와 어긋난다.

## §3. 가정된 사용 시나리오

운영자가 새 호스트로 서비스를 옮긴다. 이전에는 `docker compose up` 만으로는 백업이 돌지 않아,
누군가 `sudo bin/install-backup-cron.sh` 를 기억해 내 실행해야 했고 잊으면 **몇 주 뒤 복구가
필요할 때에야** 백업이 없다는 걸 알게 됐다. 이관 후에는 `docker compose up -d` 가 곧
`ops-scheduler` 를 띄우고 스케줄이 compose 파일과 함께 따라오므로, 별도 호스트 작업 없이
정기 잡이 산다. 스케줄을 바꾸고 싶으면 crontab 을 `sudo` 로 여는 대신 compose 의
`OPS_SCHED_*` 값을 고쳐 PR 을 낸다 — 변경 이력이 git 에 남는다.

## §4. 외부 검증 로그 (append-only)

(엔트리 없음 — 일반 TASK cycle 완료 조건 아님.)
