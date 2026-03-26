---
doc_type: REVIEW
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260326-0001
- Date: 2026-03-26
- Decision: agent 이미지는 core feature Dockerfile에서 web-ui feature 소스를 함께 복사한다
- Reason: import 경로를 깨지 않으면서 기능 소유권을 분리하기 위함
- Risk: 이미지 빌드 경로가 루트 context에 의존한다
