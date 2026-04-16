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
