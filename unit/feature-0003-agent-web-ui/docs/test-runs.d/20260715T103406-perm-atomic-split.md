---
run_at: 2026-07-15T10:34:06+09:00
session: perm-atomic-split (ai/root/feature-0003-perm-atomic-split)
scope: RBAC — 권한 원자 단위 분리(23종 신설·엔드포인트 enforcement 전환·legacy 묶음 숨김·backfill v2)
verdict: PASS
---

### Run (2026-07-15) — perm-atomic-split (Critical §12.3) — **Environment: agent-container pytest (--no-deps) + 호스트**

- 컨테이너 `make test`: **feature-0003 신규 회귀 0** — 실패 4건은 전건 기지의 환경 기인(직전 perm-category-hier fragment 에서 main baseline 재현으로 확정된 동일 세트: `.env` AGENT_RUNTIME_READ_BACKEND/AGENT_TIMEOUT_SEC 3건 + `postgres-replica` DNS/격리 네트워크 1건).
- 호스트 스위트: **785 passed / 0 failed**(share_redaction 은 컨테이너 세트에서 PASS).
- 계약 테스트: dependency-map(M3 원자 종속·legacy 트리 부재·V2/t5/t6 재계약) · perm_split R7/R8(서브탭=read) · **R9 신설**(묶음→원자 transitive 함의 + 개별 DENY 우선 — choke-point fallback 기각 근거 pin) · **R10 신설**(LEGACY_BUNDLE_PERMISSIONS BE/admin.js/app.js 3자 parity + 함의 맵 키 동치).
- jsdom 탭 게이팅 47/0 · `gen-routemap.py` 재생성(202 routes, 권한 열 갱신) + `--check` exit 0(권한 데코레이터 변경 cycle 필수 게이트) · `codenav-lint` OK.
- 역할 저장 wipe 반증: preservedHidden(TASK-0300)이 grid 미렌더(숨긴 묶음) grant 를 union 보존 — 실코드 확인.
- 결과: PASS.

### Run (2026-07-15) — 원자 권한 grid·버튼 게이팅 시각검증 — **Environment: Windows-browser (배포 후 라이브로 이연)**

- **미수행 사유(§15.4.1 baked 자산 + authz)**: 정적 자산은 배포 후 반영이며, 검증 자체가 startup backfill(`atomic-perm-split-v1`)·역할별 원자 전개 상태에 의존 — 배포 전 headless 대체 불가(jsdom·pytest 로 로직층 검증 완료).
- **배포 후 계획(PB-0008)**: ① 역할 편집 grid 에 레거시 묶음("… 관리 (전체 묶음)" 류) 미표시·원자 단위만([조회]→[추가/수정/삭제]/[검수]) ② usermanager 등 묶음 보유 role 이 원자 단위 체크 상태(backfill) ③ 메타데이터 서브탭 버튼 게이팅(새 항목=create·삭제=delete)·데이터소스 연결 테스트 버튼=datasource.test ④ `WebSchemaMigrations` `atomic-perm-split-v1` 마커 + seed catchup 정상(1406 없음).
- 결과: 정적·로직 검증 PASS · 라이브 시각검증 DEFERRED(배포 후, 위 계획).

### Run (2026-07-15, POST-DEPLOY) — perm-atomic-split 라이브 실증 — **Environment: Windows-browser (win-browser.py relay, 실 Windows Chrome 150)**

- 배포: PR #810 머지(8098aee1) → `bin/deploy-web.sh`(scope=all·soak 통과) exit 0. web 로그 seed catchup 이상 없음(1406 미출현).
- **DB 실증**: `WebSchemaMigrations` 에 `atomic-perm-split-v1` 마커 기록. admin 원자 23종 explicit(catchup). **묶음 보유 role = admin 뿐**(전수 조회 — usermanager 는 묶음 미보유·kb leaf=graph.read 라 전개 대상 아님이 정상, 접근 상실 조합 0).
- **라이브 브라우저 실증**(bootstrap_admin, 역할 편집 grid):
  - **레거시 묶음 렌더 0건**(kb.ingest.manual·manage 4종·product.manage·datasource.manage 전부 grid 소멸 — 총 87 rows).
  - 원자 트리: 용어사전 `read(d1) → create/update/delete/검수(d2)` — 검수가 원본 사전 read 하위(사용자 지시 반영). 데이터소스 `read(d0) → create/update/delete/test(d1)`.
  - `metadata.glossary.read` 해제 → 원자 4종(추가/수정/삭제/검수) 전부 접힘 → 재체크 시 전부 재펼침. 토글 원복 후 "변경 없음·0건 pending"(상태 오염 0).
  - admin 역할 권한 카운트 113(원자 확장 반영)·스크린샷 육안 확인·eval 오류 0.
- 결과: **PASS** (배포 후 실증 완료 — [등록/수정/삭제]·[등록/거부] 통합 항목 화면 소멸, 원자 단위 계층 동작).
