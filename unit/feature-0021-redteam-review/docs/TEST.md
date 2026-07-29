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
- TEST-20260728T093528-realign-1..23: `tests/test_redteam.py`(20) + `tests/test_self_review_messages.py`(3)
  — 원 요청 재앵커 순서 계약(findings 뒤), 레거시 인자 미지정 무회귀, `<<USER_REQUEST>>` datamark
  breakout 차단, 메타 프레이밍 탐지(양성 7·정상 DB 답변 3·DML 오탐 가드·제목 은닉·빈 입력),
  재서술 계약(탐지 없으면 호출 0·스위치 OFF·적용·내용손실 폐기·메타잔존 폐기·무산출/예외 fail-open·
  rewrite_fn 부재), orchestrate question/thread_goal 스레딩, bounded 발신자 thread_goal 억제.
- TEST-20260729T110000-reqctx-1..22: `tests/test_redteam.py`(16) + `tests/test_self_review_messages.py`(6)
  — 앵커 2층(대화 요청/직전 발화 분리·단일 턴 1층), 계약의 범위-축소 금지(초판 축소 유발 문구
  부재 포함), 리뷰어 `CONVERSATION REQUEST` 주입·미지정 무주입·프롬프트 규칙(과답변 오판 금지·
  삭제=REGRESSION), 첨부 digest(매니페스트·발췌·절단·예산 선점), 붕괴 가드(라이브 붕괴 재현 →
  미채택 `revise_collapsed` / 정상 축소는 통과), 누출 게이트(bounded 발신자 대화요청·첨부 억제).
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

### Run 2026-07-28 — 원 요청 정합 교정 (answer-origin-realign)

- Environment: **CLI** (agent 이미지 `mysql-ai-agent:current` 격리 컨테이너, worktree 마운트 +
  `PYTHONDONTWRITEBYTECODE=1`, monkeypatch — DB/LLM 무의존)
- 상세 fragment: [`test-runs.d/20260728T0935-answer-origin-realign.md`](./test-runs.d/20260728T0935-answer-origin-realign.md)
- 결과 **PASS** — 신규 23건(redteam 20 + self_review_messages 3) 포함 **2814 passed / 2 skipped /
  0 failed**. 같은 컨테이너·같은 명령으로 측정한 **main HEAD(44fe939d) baseline 2791 passed** 와
  대조해 순증 23 = 신규 테스트 수, **회귀 0** 확정. `ruff check unit/ shared/` All checks passed.
- 마이그레이션 없음(alembic 무변경) → migrate-lint 대상 아님. 웹 자산(static/template/html)
  변경 0 → check #13 시각검증 hard gate 대상 아님.
- 미커버는 §4 참조 — 라이브 교정 효과·재서술 발동률(문체 판정은 단위 테스트 범위 밖).

### Run 2026-07-28 — POST-DEPLOY 라이브 실증 (answer-origin-realign 배포 반영 + 설정 행 표출)

- Environment: **Windows-browser** (`bin/win-browser.py` CDP, Chrome/150 relay) + CLI(컨테이너
  introspection). 배포: PR #1026 머지 → `make deploy-all`(web 롤링 + 90s soak + 워커 롤아웃).
- 상세 fragment: [`test-runs.d/20260728T0935-answer-origin-realign.md`](./test-runs.d/20260728T0935-answer-origin-realign.md) Run 4
- 결과 **PASS**
  - web-a/web-b/ask-worker/insight-worker 전부 `GIT_COMMIT=f0b3d3a5` · 엣지 `/healthz` 200.
  - ask-worker baked `modules/redteam.py` 에 신규 심볼 9 매치, web baked `runtime_settings.py` 에
    `REDTEAM_ANSWER_REALIGN` 1 매치 — repo 가 아니라 **이미지에 반영됨**을 확인.
  - 실 Windows 브라우저로 관리 콘솔 *설정 > AI 자가 리뷰* 신규 행 확인: 라벨 **원 요청 기준 답변
    정합 교정** · **즉시 반영** 배지 · `0/1` · effective **1**(기본 활성) · 설명문 렌더 ·
    스펙과 일치하는 배치 순서(미해소 결함 답변 고지 → 본 행 → 리뷰어 호출 타임아웃) ·
    잘림/겹침/overflow 없음.
- **미검증(명시)**: 답변 뉘앙스의 실제 교정 효과 — 위 결과는 "코드·설정이 라이브에 올랐다"만
  보인다. §4 미커버 참조.

### Run 2026-07-29 — 다중 턴 요청 맥락 회귀 교정 (review-request-context)

- Environment: **CLI** (agent 이미지 격리 컨테이너 + `agent_runtime` 라이브 원장 조회)
- 상세 fragment: [`test-runs.d/20260729T1100-review-request-context.md`](./test-runs.d/20260729T1100-review-request-context.md)
- 결과 **PASS** — 신규 22건 포함 **2857 passed / 2 skipped / 0 failed**. 같은 컨테이너·같은
  명령의 **main baseline 2835** 대비 순증 22 = 신규 수, **회귀 0**. ruff clean. 마이그레이션 없음.
- 근본원인은 추정이 아니라 판정 원장 실측 — run #132(`rounds=14`·`stop=resolved`·최종 152자)의
  **원장↔산출물 모순**이 "축소가 수렴으로 기록되는" 퇴행 경로를 특정했고, 같은 행의 findings
  원문이 리뷰어 false positive 2종(현재 턴만 봄 / 첨부가 digest 에 없음)을 직접 보여줬다.
- 붕괴 재현 테스트는 **수정 전 코드에서 실패**하도록 작성했다(가드가 결함 자체를 검증).

### Run 2026-07-29 (2) — 라이브 유도 측정 + 과교정 가드 (review-continuation)

- Environment: **라이브 서비스**(`POST /api/ask` 2턴, 추론 매우높음) + 배포 컨테이너 내 A/B
- 상세 fragment: [`test-runs.d/20260729T1200-live-induction-measurement.md`](./test-runs.d/20260729T1200-live-induction-measurement.md)
- 결과 **PASS** — 유도한 회귀가 재현되지 않음: 수정 전 `rounds=14`/152자 비-답변 →
  수정 후 **`rounds=0`·BLOCK 0·797자 실행 가능한 continuation**. A/B 로 grounding 오판 2→0 확인,
  반대 방향 과교정(2/3) 발견 → continuation 규칙으로 **1/4** 로 감소. 전체 2883 passed·ruff clean.
- **POST-DEPLOY 확정(Run 4)**: 배포본 `44d70215` 에서 같은 대화에 짧은 후속 발화를 **연속 2회째**
  태워 `id=140` **pass · rounds=0 · BLOCK 0 · WARN 0** · 566자 실행 체크리스트 확인. Run 3 은
  배포 전 프롬프트 주입 측정이었으므로 배포본에서 재확인한 것이다.
- 잔여·한계는 §4 및 fragment 의 "미커버" 참조 (N 작음·단일 대화·첨부 end-to-end 미수행).

## 4. Integration Coverage
- 리뷰어 실 LLM 판정·redteam_reviews INSERT·노트 실볼륨 축적은 배포 후 라이브 실증
  (POST-DEPLOY Run 으로 §3 에 append). 콘솔 화면은 PB-0008 Windows-browser 검증.
- **미커버 (라이브 트래픽 대기, 2026-07-27 기준)**: 배포 후 실제 답변에서 수정→재검증이
  2회 이상 반복되어 `revision_rounds>1` / `stop_reason` 이 기록되는 표본. 배포 시점(18:04)
  이후 새 판정이 아직 없어 관측 불가 — 렌더·집계 경로는 §3 Run 2026-07-27 ③ 에서 합성 행으로
  실증했고, **실판정 수렴 동작은 트래픽 누적 후 `agent_runtime.redteam_reviews` 의
  `revision_rounds`·`stop_reason` 분포로 확인**한다.
- **미커버 (라이브 트래픽 대기, 2026-07-28 answer-origin-realign)**: 1차 재앵커가 실제 답변의
  뉘앙스를 얼마나 교정하는지, 2차 재서술(`realign_answer`)의 발동률·거절 사유 분포가 어떤지.
  단위 테스트는 *계약*(지시 내 순서·게이트·폐기 조건)만 고정할 뿐 LLM 산출물의 문체를 판정하지
  못한다 — "테스트 통과 = 뉘앙스 교정됨" 으로 읽지 않는다. 관측 경로는 stderr
  `[redteam] answer-realign detected=… applied=… reject=…` 라인과 `_rt_meta.realign_*` 이며,
  콘솔 노출은 DB 컬럼 신설이 필요해 후속 cycle 로 분리(TASK.md §10 잔여).
- **미커버 (라이브 트래픽 대기, 2026-07-29 review-request-context)**: 리뷰어 LLM 이 실제로 과답변
  BLOCK 을 더 이상 내지 않는지, `revision_rounds` 의 긴 꼬리(14 라운드)가 사라지는지,
  `stop_reason='revise_collapsed'` 빈도가 유의한지. 단위 테스트는 붕괴 *경로*(가드·앵커·리뷰어
  입력)를 고정할 뿐 리뷰어 판정 자체를 재현하지 못한다 — 배포 후 `redteam_reviews` 분포로 확인.
  **2026-07-29 배포 후 라이브 유도로 1차 확인 완료**(§3 Run 2026-07-29(2)) — 다만 N 이 작고 단일
  대화라 장기 분포(`revision_rounds` 꼬리·`revise_collapsed` 빈도)는 여전히 트래픽 대기.
- **미커버 (첨부 end-to-end)**: 유도 대화는 SQL 을 본문 붙여넣기로 태웠다(첨부 업로드 자동화
  미구현). 첨부가 리뷰어에 도달하는 것은 A/B 로 간접 확인(가짜 첨부 주입 시 불일치 BLOCK 발생).
