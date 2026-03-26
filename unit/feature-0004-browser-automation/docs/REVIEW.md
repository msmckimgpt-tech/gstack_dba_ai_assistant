---
doc_type: REVIEW
feature_id: feature-0004-browser-automation
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260326-0001
- Date: 2026-03-26
- Decision: 브라우저 이미지는 루트 build context를 쓰되, feature 경로 파일만 복사한다
- Reason: 루트 compose 일관성을 유지하기 위함
- Risk: build context가 넓지만 경로 참조는 명확하다
