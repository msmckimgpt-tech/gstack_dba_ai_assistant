---
doc_type: MODIFY
feature_id: feature-0001-platform-runtime
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

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
