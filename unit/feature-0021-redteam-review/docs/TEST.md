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

### Run 2026-07-16 — 콘솔 IA 재구성 (컨테이너 make test)
- Environment: CLI
- Command: `make test` (agent 이미지, --no-deps)
- Result: **PASS (본 변경 범위)** — IA 재구성 관련 62건 PASS (admin_reasoning 권한 분리/kind/
  fallback 제외 · permission_dependency_map M5 정합 · route-parity 경로 불변 · redteam · agent_notes).
  Windows-browser 는 배포 직후 PB-0008 (test-runs.d/20260716T090000-console-ia-restructure.md). ruff PASS.
- 잔여 FAILED 4건은 pre-existing 환경 의존(PG 부재·env) — 본 diff 무관(위 Run 2026-07-15 §3 동일).

### Run 2026-07-16 — 콘솔 서브탭 통합 (컨테이너 make test)
- Environment: CLI
- Command: `make test` (agent 이미지, --no-deps)
- Result: **PASS (본 변경 범위)** — 통합 관련 33건 PASS (permission_dependency_map 권한 불변·
  admin_reasoning 무변경·route-parity 경로 불변) + §18.8 적대검증(REV-0005) MAJOR 2 + MINOR 2 반영.
  Windows-browser 는 배포 직후 PB-0008 (test-runs.d/20260716T140000-console-subtabs.md). ruff PASS.
- 잔여 FAILED 4건은 pre-existing 환경 의존(PG 부재·env) — 본 diff(프론트 전용) 무관.

### Run 2026-07-22 — 리뷰어 토큰 할당량 콘솔 설정 (기존 agent 이미지 직접 pytest)
- Environment: CLI
- Command: `docker run --rm -v <worktree>:/work mysql-ai-agent:current` 로 pytest 직접 실행
  (worktree 에 `.env` 부재로 `make test` 의 `dc-build` 가 "invalid proto" 실패 — 기존 baked
  agent 이미지에 worktree 마운트 + PYTHONPATH 우회. project-pytest-worktree-pycache-gotcha 선례).
- Result: **PASS** — `test_redteam.py` 36건(신규 5: `_review_max_tokens` read/0-fallback/error +
  `run_review` override 전달·미설정 None) + `test_runtime_settings.py` + `test_admin_reasoning.py`
  합산 87건 전건 통과, 실패 0. ruff clean(변경 4파일). `REDTEAM_MAX_TOKENS` 가 `serialize_registry()`
  의 `redteam` 그룹에 노출됨 확인.
- windows-browser: 배포 직후 PB-0008 로 설정 패널 "리뷰어 토큰 할당량" 렌더 + 조정 반영 검증 예정
  (POST-DEPLOY — 본 Run 은 단위·격리 범위).
- 참고: 이번 diff 는 프론트 무변경(설정 패널 data-driven)·backend additive 라 pre-existing 환경
  의존 4건과 무관.

### Run 2026-07-27 — POST-DEPLOY 라이브 실증 (반복 검증 수렴 · 리뷰어 기억 격리 · 콘솔 표면화)
- Environment: Windows-browser (PB-0008) + 라이브 PG(`repo-postgres-1`) + 라이브 워커(`repo-ask-worker-1`)
- 대상 배포: PR #957 머지분(`491f639c`) — web `486a587c` / ask-worker `491f639c` 로 반영 확인.
- **① 마이그레이션** — `public.alembic_version` = `0045_redteam_convergence_columns`,
  `agent_runtime.redteam_reviews` 에 `unresolved_block_count` · `stop_reason` · `revision_rounds` ·
  `verify_findings` 4개 컬럼 실재. **PASS**
- **② 공유창 window 격리 fail-closed (단위 미커버 라이브 PG 경로)** — `recent_conversation_reviews`
  를 라이브 ask-worker 컨테이너에서 직접 호출해 인과 확정. **PASS**
  | 케이스 | 기대 | 실측 |
  |---|---|---|
  | `has_restricted_members=false` 실대화(리뷰 11건 보유) | limit(3)건 조회 | 3건 (`revise/pass/pass`) |
  | 존재하지 않는 conversation_id (대화 메타 행 부재) | 0건(보수적 차단) | 0건 |
  | `conversation_id=None` (스코프 없음) | 0건 | 0건 |
  | **임시 대화 `has_restricted_members=TRUE`** (리뷰 1건 보유) | **0건(fail-closed)** | **0건** |
  | 위와 **동일 대화**를 `FALSE` 로만 토글 | 1건 조회 | 1건 (`revise`) |
  마지막 두 행이 인과를 확정한다 — 데이터·스코프가 같고 게이트 플래그만 다른데 조회 여부가 갈린다.
  실증에 쓴 임시 행(`zz-tmp-postverify-f0021-isolation`)은 검증 직후 삭제, 잔존 0건 확인.
  기존 라이브 대화 245건은 전부 `has_restricted_members=false` 로 **무변경**.
- **③ PB-0008 콘솔 표면화 (감사 > AI 운영 현황 > 추론)** — 실 Windows 브라우저. **PASS**
  - 신규 통계 타일 **'결함 잔존 전달 (7d)'** 렌더 (라이브 실데이터 기준 `0`).
  - 타임라인 ①~⑤ 5단계 렌더. 배포 전 판정 행(재검증 미수행)은 ④ "해당 없음 (강도별 skip 또는
    미수행)" · ⑤ "결함 해소 후 개선된 답변 전달" 로 기존 동작 유지.
  - **잔존 분기 렌더 실증** — 라이브 데이터에 아직 `unresolved_block_count>0` 표본이 없어,
    합성 행 1건(`zz-tmp-postverify-f0021-render`, `revision_rounds=3` · `unresolved=2` ·
    `stop_reason=backstop`)을 주입해 신규 분기만 확인: ③ "텍스트 재작성 · **수정 3회 반복**",
    ④ "**재검증에서 결함 잔존 — BLOCK 2건 미해소**", ⑤ "**결함 잔존 상태로 전달 — BLOCK 2건
    미해소 (반복 안전 상한 도달)**"(`stop_reason` 한글 라벨), "**재검증에서 해소되지 않은 지적
    (2건)**" 앰버 블록 2건, 타일 `0→1` 집계. 확인 후 합성 행 삭제 → 타일 `0` 원복 확인.
    ※ 이 항목은 **렌더·집계 경로의 실증**이며 리뷰어의 실제 수렴 판정 관측이 아니다
    (실판정 표본은 라이브 트래픽 누적 후 관측 — §4).
  - **설정 > AI 자가 리뷰** 패널에 신규 항목 노출 확인: '결함 해소까지 반복 수정'(1),
    '반복 수정 전체 시간 예산'(0=무제한), '수정본 재검증 최소 추론 강도'(0=전 강도),
    '리뷰어 대화 기억 건수'(3), '미해소 결함 답변 고지'(1).
  - 증적: `artifacts/shared/win-browser-shots-pb0008-redteam/step_06_20260727_182026.png`(기본
    렌더) · `step_05_20260727_182219.png`(잔존 분기) · `step_07_20260727_182335.png`(설정 패널).

## 4. Integration Coverage
- 리뷰어 실 LLM 판정·redteam_reviews INSERT·노트 실볼륨 축적은 배포 후 라이브 실증
  (POST-DEPLOY Run 으로 §3 에 append). 콘솔 화면은 PB-0008 Windows-browser 검증.
- **미커버 (라이브 트래픽 대기, 2026-07-27 기준)**: 배포 후 실제 답변에서 수정→재검증이
  2회 이상 반복되어 `revision_rounds>1` / `stop_reason` 이 기록되는 표본. 배포 시점(18:04)
  이후 새 판정이 아직 없어 관측 불가 — 렌더·집계 경로는 §3 Run 2026-07-27 ③ 에서 합성 행으로
  실증했고, **실판정 수렴 동작은 트래픽 누적 후 `agent_runtime.redteam_reviews` 의
  `revision_rounds`·`stop_reason` 분포로 확인**한다.
