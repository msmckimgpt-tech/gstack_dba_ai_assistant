---
run_at: 2026-07-28T23:30:00+09:00
session: ai/root/graph-churn (claude)
scope: TEST-20260728T140500-graph-churn-1~11
verdict: PASS
---

# Run 2026-07-28 — COMPOSE_PROJECT_NAME=repo make test + migrate-lint

- Environment: CLI (백엔드 파이프라인 — PB-0008 비대상)
- 신규 test_graph_churn.py **16 PASS**(§18.8 흡수 후 — 슬롯 커서·pending/committed·트리거
  제외목록·중복정책 제거 잠금 포함) + 관련 스위트 132 PASS.
- **라이브 타입 실증(§18.8 B-1)**: agent 이미지에서 `psycopg.Cursor.__slots__ == ()` 확인 +
  동일 제약 커서로 캐시 동작 검증 — 관계 3건에서 cypher 유발 호출 15→9, Table MERGE 1회.
- `bin/migrate-lint.sh`: 0046 **expand-safe PASS**.
- ruff: All checks passed.
- **회귀 판정: 0** — 전체 스위트 실패 15건이 기존 환경성 baseline 과 동일 집합
  (attach_inline_honesty 4·attachment_idor 4·attachment_user_version_context 5·
  runtime_settings 2). 기존 계약 1건(test_probe_missing_object_error_is_negative)은
  allow_revive kwarg 추가에 맞춰 **의도적 갱신**.
