---
doc_type: TEST
feature_id: feature-0021-redteam-review
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

<!-- §1, §2, §4는 rewrite (케이스 정의). §3은 append-only (실행 결과 이력). -->

## 1. Test Scope
- redteam 오케스트레이션: 게이트(enable/level)·JSON 파싱 견고성·스키마 강제·fail-open·
  revise/verify 흐름 (LLM/DB 무의존 monkeypatch).
- agent_notes: 파일 캡 trim·중복 제거·주입 캡/비활성·TTL sweep·대화 격리·제품 노트
  claim 비저장·식별자 sanitize.
- admin_reasoning API: RBAC(401/403)·progressive disclosure(목록 메타/단건 본문)·
  PG 미가용 부분 degrade·notes 빈 목록·런타임 설정 redteam 그룹 노출.
- 제외: 리뷰어 LLM 실판정 품질 (라이브 실증으로 — §3 POST-DEPLOY), redteam_reviews 실 INSERT
  왕복 (라이브), 콘솔 화면 (PB-0008 Windows-browser).

## 2. Test Cases
- TEST-20260715T140000-redteam-1..15: `tests/test_redteam.py` — plan 게이트 6, JSON/스키마 3,
  digest 2, orchestrate 흐름 6 (fail-open·pass·revise+verify·normal 무verify·revise 실패·빈 초안).
- TEST-20260715T140001-notes-1..8: `tests/test_agent_notes.py` — 세션/제품 기록·격리·캡·
  dedupe·TTL sweep·sanitize·비활성.
- TEST-20260715T140002-api-1..8: `tests/test_admin_reasoning.py` — RBAC 공통·guidance 목록/
  상세/404·redteam degrade·cursor 관대성·notes·runtime redteam 그룹.
- 기존 회귀: `test_runtime_settings_api.py`(레지스트리 확장 무회귀),
  `test_permission_dependency_map.py`(신규 권한 FE↔카탈로그 정합),
  `test_route_parity_p5b.py`(라우트 추가 정합), `test_call_llm_records_agent_task.py`(계측 무회귀).

## 3. Test Runs (append-only)

### Run 2026-07-15 — 단위 (컨테이너 make test)
- Environment: CLI
- Command: `make test` (agent 이미지, --no-deps, 격리 worktree)
- Result: **PASS (본 feature 범위)** — 신규 34건 전건 통과 (redteam 18 · agent_notes 8 ·
  admin_reasoning 8; 적대 패널 REV-0002 반영분 revise-loop 2·jsonb-guard·table_available 포함) +
  route-parity golden 갱신 후 통과 (208→211 route, 의도 추가 3) + permission_dependency_map
  정합 통과. ruff 통과.
- 잔여 FAILED 4건은 **pre-existing 환경 의존 — 본 diff 무관** (교차 검증: main(repo/) 동일
  컨테이너 실행으로 확인):
  ① `test_runtime_settings.py::test_missing_snapshot_is_fail_open` ·
  `test_runtime_settings_api.py::test_get_returns_registry` — 운영 `.env` 의
  AGENT_TIMEOUT_SEC=300 이 "기본값 60" 단정과 충돌 (main 에서도 동일 실패).
  ② `test_routine_dbanalysis.py::test_schema_analysis_fail_loud_...` ·
  `test_item11_batch8_update_conv_product.py::test_auto_happy_200` — main 의 make test 는
  라이브 compose 네트워크에 합류해 실 PG(postgres/postgres-replica)로 통과하지만, 격리
  worktree 네트워크에는 PG 가 없어 연결 실패 (테스트가 컨테이너 환경의 라이브 DB 에 암묵
  의존 — REPORT §8 개선 후보로 기록).

## 4. Integration Coverage
- 리뷰어 실 LLM 판정·redteam_reviews INSERT·노트 실볼륨 축적은 배포 후 라이브 실증
  (POST-DEPLOY Run 으로 §3 에 append). 콘솔 화면은 PB-0008 Windows-browser 검증.
