---
doc_type: MODIFY
feature_id: feature-0001-platform-runtime
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260515-0003
- Date: 2026-05-15
- Related Requirement: TASK-0058, REQ-20260515-0003
- Summary: `browser-up` / `insight-up` 에서도 docker compose v5.1.1 + buildx v0.31.1 provenance metadata file race 를 흡수하도록 기존 `dc-build` 가드 패턴 적용.
- Files: `Makefile`, `unit/feature-0001-platform-runtime/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md`
- Impact: `make browser-up` 과 `make insight-up` 이 `dc-build SERVICE=...` 로 이미지를 먼저 만들고 `up -d --no-build` 로 기동한다. web 타깃과 같은 root-cause 대응이라 metadata file 후처리 race 때문에 서비스 복구가 실패하지 않는다.
- Verification: `make browser-up`, `make insight-up`, `make status`

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: MySQL/DAB/SQL 유틸리티를 템플릿 feature 구조로 이관
- Files: src/mysql/conf.d/*, src/dab/dab-config.json, src/sql/*
- Notes: 런타임 데이터는 `../../../../artifacts`로 분리

## CHG-20260415-0002
- Date: 2026-04-15
- Summary: 내장 Local LLM bootstrap 스크립트를 제거해 플랫폼 runtime 경계를 MySQL 전용으로 복구
- Files: src/local-llm/init_ollama_models.sh
- Notes: Local LLM provider는 현재 repo가 아니라 외부 `/root/download/docker/local_llm` 에서 관리한다

## CHG-20260423-0003
- Date: 2026-04-23
- Summary: AI 전용 복제 MySQL 인스턴스 연결용 compose 네트워크 + env placeholder + smoke check 스크립트 추가 (TASK-0045)
- Files: docker-compose.yml, .env.example, Makefile, scripts/check_replica.sh, unit/feature-0001-platform-runtime/docs/FUNCTION.md, unit/feature-0001-platform-runtime/docs/TASK.md
- Notes: 네이밍은 과제 프롬프트의 `REPLICA_MYSQL_*` 가 아니라 기존 `modules/config.py` / `modules/db.py` (TASK-0044) 에서 이미 사용 중인 `REPLICA_DB_*` 를 유지 — primary 의 `DB_*` prefix 와 parallel 하고, 기존 agent-core 라우팅 로직을 재사용하기 위함. 누락되어 있던 `REPLICA_DB_NAME` 만 신설. 복제본 자체의 replication 설정 / 초기 full dump / 동기화 주기 / 조직 보안 정책은 repo 범위 밖이며, 본 변경은 접속 레이어(네트워크 + 자격증명 placeholder + connectivity probe) 만 담당.

## CHG-20260424-0001
- Date: 2026-04-24
- Related Requirement: TASK-0046 (template v3.2.0-rc.1 external anchor 도입)
- Summary: ANCHOR.md §1-§3 작성 — platform-runtime 책임 경계, `artifacts/` 분리 원칙, 대안(IaC/docker-root) 분기, replica 점검 시나리오.
- Files: unit/feature-0001-platform-runtime/docs/ANCHOR.md, unit/feature-0001-platform-runtime/docs/TASK.md
- Impact: feature 방향성 stable reference 확립. 향후 요청이 platform-runtime §1-§3과 충돌하면 Conflict Protocol 발화 대상.
- Rollback Notes: ANCHOR.md 내용 revert 시 verify-completion check #6이 24h grace 만료 후 FAIL. 사용자 직접 §1-§3 재작성 또는 feature 폐지 필요.

## CHG-20260512-0002
- Date: 2026-05-12
- Related Requirement: TASK-0057, REQ-20260512-0003
- Summary: dev 환경 가동 시 single TLS termination 원칙 회복 — web 컨테이너의 self-signed HTTPS 자체 가동을 dev 한정으로 plain HTTP 로 override 하여 gstack `/qa` / `/browse` / playwright 등 browser 자동화 도구의 TLS 차단 해소. 사용자 follow-up: TASK-0055 QA 진행 중 web 의 self-signed cert 가 browse 데몬을 차단해 정적 검증 fallback 이 필요했던 issue 의 root cause 해결.
- Files: docker-compose.override.yml.example (신규, template — `entrypoint` override 로 plain HTTP 가동), .gitignore (실 사용 파일 `docker-compose.override.yml` 추가), CONTRIBUTING.md (§10 신설 "Dev 환경 가동 — single TLS termination 원칙"), unit/feature-0001-platform-runtime/docs/TASK.md (TASK-0057 entry), unit/feature-0001-platform-runtime/docs/MODIFY.md (본 entry), unit/feature-0001-platform-runtime/docs/REPORT.md (Summary prepend), docs/STATUS.md (feature-0001 entry 갱신).
- Diff size: 신규 docker-compose.override.yml.example 28 lines, CONTRIBUTING.md +33 lines, .gitignore +4 lines.
- Impact: 개발자 머신마다 `cp docker-compose.override.yml.example docker-compose.override.yml && make web` 1회 setup 으로 host `localhost:18080` 이 plain HTTP 가동. browser 자동화 도구가 env var · opt-in 옵션 추가 없이 자연 동작. gstack-upgrade 마다 별도 patch 적용 불필요. production / staging 환경 영향 0 — production compose 파일에 override 를 두지 않으면 무시 (Caddy frontline TLS 종단 그대로 유지).
- Rollback Notes: `mv docker-compose.override.yml docker-compose.override.yml.disabled` 후 `make web` 재기동하면 base compose 의 entrypoint 분기로 복귀해 `ENABLE_WEB_TLS=1` (`.env` 기본) self-signed HTTPS 가동. revert 시점에 .gitignore + CONTRIBUTING.md §10 만 git revert 로 되돌리면 template 만 남고 dev 가동은 기존 HTTPS 로 유지.
