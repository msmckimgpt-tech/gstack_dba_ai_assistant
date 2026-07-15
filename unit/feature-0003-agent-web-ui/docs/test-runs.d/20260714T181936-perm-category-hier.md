---
run_at: 2026-07-14T18:19:36+09:00
session: perm-category-hier (ai/root/feature-0003-perm-category-hier)
scope: RBAC — 관리 콘솔 권한 카테고리 '접근' 계층(접근 5종·backfill·탭 카테고리 AND 게이트·종속 트리)
verdict: PASS
---

### Run (2026-07-14) — perm-category-hier: 카테고리 '접근' 계층 재구성 (Critical §12.3) — **Environment: agent-container pytest (--no-deps)**

- 방법: `make test`(agent 이미지 격리 컨테이너) + 실패 재현은 `docker compose run --rm --no-deps agent`(CI-클린 env) — graph-perm-split Run 과 동일 메커니즘.
- 단위 검증(정적 카탈로그 + admin.js 파싱 + 순수함수):
  - `test_permission_dependency_map.py`: **M3(카테고리 접근 5종 부모=console.access + 탭 base 16종 부모=소속 카테고리 접근)** · **M5(백엔드 `_CONSOLE_CATEGORY_ACCESS_LEAVES` ↔ FE 종속 맵 동치 — 모든 세부 권한 조상 체인이 카테고리 접근 경유)** · M4(create→list.own·archive 예외) · V2/V3/V4(카테고리 접근 중간 게이트 가시성) · t3/t5/t6(그룹 트리 depth). PASS.
  - `test_llm_usage_quota.py` f2(quota.read→console.account.access) · `test_insight_reset.py`(group=product) · `test_metadata_perm_split.py`(묶음 함의 불변). PASS.
  - 권한 타깃 50 PASS · feature-0003 스위트 **785 passed / 0 failed**.
- 프론트 게이팅(jsdom@22 격리): `verify_admin_tab_gating.mjs` **47 passed / 0 failed** — 신규 케이스 2b(세부만 보유→탭 숨김 / 접근만 보유→탭 숨김 / 접근+usage.read→usage 만 노출)·4b(runtime.read 설정 탭 도달 보강 + 접근 없으면 숨김). 기존 "시스템 라벨 숨김" 기대 2건은 release-notes 탭(비민감·전원 노출) 도입 이후 **main baseline 부터 FAIL 이던 stale 기대** → 의도 반영으로 정정.
- 회귀: `make test` 초기 4 실패는 전건 **환경 기인 확정** — ①`test_runtime_settings*` 2건+`test_item11_batch8` 1건 = 복사 `.env` 의 `AGENT_RUNTIME_READ_BACKEND=postgres`·`AGENT_TIMEOUT_SEC=300`(env 중립화로 소멸 — graph-perm-split Run 에서 기확정된 동일 케이스) ②`test_routine_dbanalysis::test_schema_analysis_fail_loud_on_status_aggregation_failure` 1건 = `.env` 의 `postgres-replica` 참조가 격리 프로젝트 네트워크에서 DNS 미해석(psycopg OperationalError) — **main 코드 + 격리 네트워크(`-p permhier-baseline-check`)에서 동일 재현**, repo 프로젝트에선 라이브 replica 가 붙어 우연히 통과. 본 변경 무관 확정.
- **§18.8 보안 렌즈(inline 적대 + 라이브 MySQL 8 dry-run 실증)**: backfill 3종 SELECT 를 라이브 `repo-mysql-1`/agent_memory 에 read-only 실행 — 문법 정상(1093 없음), **target1 적중 = admin + 커스텀 role `usermanager`(catchup 만으론 lockout 됐을 대상을 backfill 이 구제 — 설계 실증)**, target2=1 계정, target3=0. 상세 REV-20260714T181936-perm-category-hier.
- 결과: PASS.

### Run (2026-07-14) — perm-category-hier 프론트 권한 grid·탭 가시성 시각검증 — **Environment: Windows-browser (배포 후 라이브로 이연)**

- 대상 자산: `admin.js`(`PERMISSION_DEPENDENCIES`·`ADMIN_TAB_CATEGORY_ACCESS`·그룹 순서/라벨), `app.js`(그룹 라벨·OVERRIDES).
- **미수행 사유(§15.4.1 baked 자산 + authz 게이팅)**: 정적 자산은 web 이미지에 baked 되어 배포 후에만 라이브 반영(cache-buster content-hash 빌드 주입). 검증 자체가 **배포 후 startup backfill**(`console-category-access-v1`)과 역할별 부여 상태에 의존 — (a) admin 역할 grid 에서 카테고리 접근 5종이 각 그룹 최상위(depth 0)로 표시·체크 시 하위 펼침, (b) 감사 그룹에 4탭 조회 권한(보관 대화·LLM 사용량·AI 운영 현황 포함) 통합 표시, (c) 제한 역할(예: usermanager)의 탭 가시성 무손실 — 은 배포 환경 데이터가 필요해 배포 전 headless 로 대체 불가(jsdom 게이팅 47/0 로 로직층은 검증 완료).
- **배포 후 라이브 검증 계획(PB-0008)**: web 재배포 후 win-browser.py relay 로 https://localhost/admin — ① 역할 편집 grid: 카테고리 접근 체크/해제 시 하위 그룹 펼침/접힘(감사 접근 OFF → 감사 그룹 접힘), ② 좌측 nav: usermanager 류 제한 역할 탭 노출 동일(backfill 무손실), ③ `WebSchemaMigrations` `console-category-access-v1` row + usermanager 에 `console.audit.access` 부여 실증, ④ web 로그 seed catchup 정상(1406 없음).
- 결과: 정적·로직 검증 PASS · 라이브 시각검증 DEFERRED(배포 후, 위 계획).
