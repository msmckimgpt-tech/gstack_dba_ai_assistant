---
doc_type: ANCHOR
feature_id: feature-0001-platform-runtime
created_at: 2026-04-24T08:24:32Z
status: active
edit_policy: mixed
source_of_truth: true
---

<!--
ANCHOR.md — External Anchor Document (9번째 1급 문서)

이 문서는 기능의 "방향성 stable reference"다. AI-delegated 개발의 폐쇄 루프 문제를
방지하기 위해 외부 관점과 가정된 사용 맥락을 명시적으로 기록한다.

정책 요약 (AGENTS.md §17):
- §1~§3 (stable reference): rewrite 가능. 방향이 바뀌면 명시적으로 갱신한다.
- §4 (외부 검증 로그): append-only. source는 `human:<name>` 만 허용. AI는 §4 writer가 아님.
- Conflict Protocol: AI는 사용자 요청이 §1~§3와 충돌 시 작업을 시작하지 않고
  gstack skill(`/office-hours`, `/plan-ceo-review` 등) 재앵커를 유도한다.
- 24h bootstrap grace: `created_at` 기준 24시간 이내면 §1~§3이 빈칸이어도 verify 통과.
-->

# ANCHOR: feature-0001-platform-runtime

## §1. 외부 관점 요약

- **"왜 MySQL 설정이 'feature'인가? 인프라는 보통 repo-level이지 않나?"**
  → 이 프로젝트는 AI-delegated dev 템플릿 구조로 이관된 사본으로, 운영 자산
  (MySQL conf, SQL 유틸)도 코드 feature와 같은 8-doc 거버넌스 아래에서 관리한다.
  "운영 환경 변경"도 feature 단위 TASK/REVIEW/MODIFY의 대상이다.
- **"왜 인증서/로그/데이터 파일은 여기 없는가?"**
  → `../../../../artifacts/` 경계로 분리되어 있다. 버전관리 대상(설정 파일, 스크립트)과
  런타임 산출물(실제 데이터)의 거버넌스를 의도적으로 구분한다.
- **"왜 MinIO + Postgres 같은 비-MySQL 서비스도 본 feature 의 compose 에 들어가는가?"**
  → docker-compose.yml 자체가 본 feature 의 운영 자산이다. MySQL 단일 cluster + 부속
  서비스 (postgres KB ADR-0021, minio attachment ADR-0022) 모두 동일 compose 파일로
  관리되며, 각 부속 서비스의 **service-level config / volume / network** 책임이 본
  feature 에 귀속된다. 개별 서비스의 **application-level 책임** (예: storage_minio.py
  wrapper, agent_kb_rw role bootstrap) 은 feature-0002/0003 등 소비 feature 에 둔다.
  본 feature 의 §3 ANCHOR 시나리오 (compose 운영) 는 "어느 서비스가 추가/제거됐는지"
  를 6 개월 후에도 찾을 수 있게 보장한다.

## §2. 대안 분기

- **Alt-A: `docker/` 루트 디렉토리 + `scripts/` 분리.** 페르소나: 일반 Docker 기반
  인프라 repo 운영 팀. 안 고른 이유: feature 단위 소유권/문서 일관성이 단절됨.
  템플릿 원칙과 충돌.
- **Alt-B: IaC 도입 (Terraform / Ansible).** 페르소나: IaC-first SRE. 안 고른 이유:
  단일 docker host 수준의 운영이라 IaC 도입 비용이 이득 초과. `Makefile` + compose로 충분.

## §3. 가정된 사용 시나리오

- **6개월 후 replica 연결 점검이 다시 필요할 때:** 새 AI 세션이 `check_replica.sh`를
  찾으러 올 때 "운영 자산은 모두 platform-runtime에 있다"는 convention만 기억하면
  루트 `scripts/`를 뒤지지 않는다. feature 경계가 가이드 역할.

## §4. 외부 검증 로그 (append-only)
