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
