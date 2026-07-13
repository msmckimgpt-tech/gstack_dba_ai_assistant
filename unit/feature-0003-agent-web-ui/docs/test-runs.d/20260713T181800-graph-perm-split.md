---
run_at: 2026-07-13T18:18:00+09:00
session: graph-perm-split (ai/claude/feature-0003-graph-perm-split)
scope: RBAC — 그래프 뷰 권한 분리(_METADATA_MANUAL_IMPLIES·backfill·탭게이트·종속맵)
verdict: PASS
---

### Run (2026-07-13) — graph-perm-split: 그래프 뷰 권한을 '메타데이터 관리' 묶음에서 분리 (Critical §12.3) — **Environment: agent-container pytest (--no-deps)**

- 방법: `docker compose run --rm --no-deps agent` (CI-클린 env: `AGENT_RUNTIME_READ_BACKEND=`·`AGENT_TIMEOUT_SEC=60`) + `PYTHONPATH=.../src` — `make test` 동일 메커니즘.
- 단위 검증(순수함수 `_apply_permission_overrides` + 정적 카탈로그/admin.js 파싱):
  - `test_metadata_perm_split.py`: R3(묶음→편집4종 함의) · **R3c(묶음이 metadata.graph.read 미함의 — 분리 계약)** · R3d(graph.read 독립부여) · R4(편집권 DENY 우선) · R5 격리 · R1/R2 카탈로그·admin seed. PASS.
  - `test_permission_dependency_map.py`: **t5(graph.read 부모=console.access 직속·편집4종=kb.ingest.manual·depth)** · m3(console.access 직속 목록에 graph.read). PASS.
- 회귀: **feature-0003 전체 스위트 PASS(회귀 0)**. 초기 관측 2 실패(`test_runtime_settings_api::test_get_returns_registry`·`test_item11_batch8::test_auto_happy_200`)는 복사 `.env` 의 `AGENT_RUNTIME_READ_BACKEND=postgres`·`AGENT_TIMEOUT_SEC=300` 이 `--no-deps` DB-less 에서 유발한 **환경 기인**(base main 동일 재현 · env 중립화 시 소멸) — 본 변경 무관 확정.
- **§18.8 보안 렌즈 적대 리뷰(라이브 MySQL 8.0.46 실증)**: 대상2 self-ref `INSERT...SELECT...NOT EXISTS` 를 라이브 `repo-mysql-1` 에서 실행 — **error 1093 없음·정확 결과**(bundle-allow→graph-allow, 기존 graph-deny 보존, graph-allow skip, bundle-deny skip). 3 findings(A MEDIUM 권한상승→대상3, B LOW 멱등→마커 이동, C NIT docstring) 수정 후 VERDICT PASS.
- 결과: PASS.
- **커버리지 갭(후속 권장)**: backfill SQL(대상1 role / 대상2 account-ALLOW / 대상3 account-DENY / 마커 guard)은 `--no-deps` 표준 스위트에 자동 통합테스트 부재. 본 cycle 은 보안 리뷰 라이브 MySQL 실증으로 대체. Critical authz 마이그레이션이므로 MySQL 통합테스트(대상3 과잉부여 차단·graph-DENY skip·2-path 자체 CREATE) 후속 추가 권장.

### Run (2026-07-13) — graph-perm-split 프론트 권한 게이팅 시각검증 — **Environment: Windows-browser (배포 후 라이브로 이연)**

- 대상 자산: `admin.js`(`ADMIN_TAB_PERMISSIONS.graph`·`PERMISSION_DEPENDENCIES`), `admin.html`(그래프 탭 게이트 주석), `release-notes-data.js`(2026-07-13 블록).
- **미수행 사유(§15.4.1 baked 자산 + authz 게이팅)**: 정적 자산은 이미지에 baked 되어 **배포(web 재빌드) 후에만** 라이브에 반영된다(cache-buster `?v=dev`→content-hash 빌드주입). 또한 본 변경은 시각 레이아웃이 아니라 **권한 게이팅**이라, 검증에 (a) `metadata.graph.read` 만 보유(그래프 탭 노출), (b) `kb.ingest.manual` 만 보유(그래프 탭 **미노출**, 메타데이터 탭만), (c) 둘 다 미보유 3종 테스트 계정이 배포 환경에 필요 → 배포 전 headless 검증으로 대체 불가. **release-notes 블록**은 `node --check`·vm 구조검증으로 정적 확인(PASS).
- **배포 후 라이브 검증 계획(PB-0008)**: web 재배포 후 win-browser.py relay(실 Windows Chrome)로 https://localhost/admin 접속 — (b) 묶음-only 계정 로그인 시 좌측 nav '지식베이스' 그룹에 '메타데이터'만 보이고 '그래프 뷰' 탭 **부재** 확인, (a) graph.read 보유 계정에서 '그래프 뷰' 탭 노출·진입·AI 능동분석 동작 확인, 역할 권한 편집 UI 에서 그래프 뷰 조회가 묶음 하위가 아닌 독립 항목으로 표시 확인. + backfill 실증(배포 후 `WebSchemaMigrations` 에 `graph-perm-split-v1` row·기존 묶음 보유자 graph.read 획득).
- 결과: 정적 검증 PASS · 라이브 시각검증 DEFERRED(배포 후, 위 계획).
