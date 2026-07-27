---
run_at: 2026-07-28T02:56:14+09:00
session: ai/claude/feature-0003-model-access-seed-fix
scope: [rbac, model-access, bootstrap-seed, sql-arity, blast-radius-isolation]
verdict: PASS (라이브 근본원인 확정 + 수정 + 재발 가드 / 단위 26 + 전체 회귀 rc=0 + ruff)
---

### Run (2026-07-28) — model-access-seed-fix (권한 seed SQL arity + blast-radius 격리) — **Environment: CLI + 라이브 컨테이너 실측**

cycle: `ai/claude/feature-0003-model-access-seed-fix` · 선행 CHG-20260728T024258-model-access-rbac 의 배포 후 결함 수정.

- **증상(배포 28fcd71f 직후 라이브 실측)**: `model.access.*` 권한 row **0개** — 기능이 조용히 미적용.
  `sudo docker logs repo-web-a-1` → `[web.startup] seed catchup skipped: Not enough parameters for the SQL statement`
- **근본 원인**: `_ensure_model_access_permissions` 의 `INSERT IGNORE INTO WebPermissions` 가
  **placeholder 5개(`%s`)에 파라미터 4개**를 넘겼다(`IsDynamic` 미바인딩) → mysql-connector
  `ProgrammingError: Not enough parameters for the SQL statement`.
- **왜 단위 테스트를 통과했나(근본 gap)**: 테스트 더블 `_SeedCur.execute` 가 SQL 을 문자열로만 분기하고
  **placeholder/param arity 를 검증하지 않았다**. 실 드라이버가 하는 검사를 더블이 하지 않아 통과.
- **영향 범위 실측 — 서비스 무영향 확정**:
  - 예외는 `_ensure_seed_catchup` **말미**에서 발생하고 caller 가 잡아 로그로 남긴다 → 그 함수 안의
    **다른 seed 단계는 모두 선행 완료**. 라이브 상태 교차확인: RoleId NULL 계정 **0** ·
    `bootstrap_admin` 존재 · 역할 **8** · 권한 **118** · `product.access` **19** ·
    `/shared/runtime_settings.json` 스냅샷 정상.
  - 게이트가 **fail-open('권한 row 미등록' = 미설치)** 로 설계돼 대화·요청 경로는 현행 동작 유지
    (403 폭주 없음). 즉 설계된 안전망이 실제로 작동했고, 손실은 "기능 미적용" 뿐이었다.
- **수정 3지점**:
  1. `IsDynamic` 파라미터 바인딩(`1`) — arity 정합.
  2. `Label`/`Description` **컬럼 길이 방어 클립**(128/255). `_ensure_permission_catalog` 가
     graph-perm-split 배포에서 실측하고 경고로 남긴 1406(Data too long) fragility 와 동일 축 —
     모델 label 이 길어져도 부트스트랩이 무너지지 않게 선제 차단.
  3. **호출 2지점 try/except 격리** — seeder 실패가 뒤따르는
     `_migrate_legacy_accounts_to_rbac`·`_ensure_bootstrap_admin`·`_seed_legacy_conversations`
     (slow path) 또는 catchup 함수 전체를 끌고 내려가지 않게. 실패는 stderr 로 **loud** 하게 남긴다
     (조용한 skip 금지).
- **재발 가드(테스트)**:
  - `_SeedCur.execute` / `_Cap.execute` 가 이제 `sql.count("%s") == len(params)` 를 **단정**한다 →
    같은 계열 arity 결함이 단위에서 즉시 실패한다(이 버그를 그대로 되돌리면 테스트가 깨진다).
  - **G9 신설** — label 400자 fake 카탈로그로 seed 를 태워 `Label<=128`·`Description<=255`·
    `IsDynamic==1` 을 계약으로 고정.
- **검증**: 단위 **26 PASS**(G1~G9) · feature-0002+0003 전체 pytest **rc=0**(fail/error 0) ·
  `ruff` All passed · `ast.parse` OK. 라이브 컨테이너에서 수정 전 함수 직접 호출로 예외 재현 →
  수정 후 재배포 시 seed 성공 여부는 POST-DEPLOY 로 확정한다.
- **Environment: Windows-browser (PB-0008) — POST-DEPLOY**: 본 수정으로 권한 row 가 처음 생성되므로,
  선행 cycle 에서 이관한 **부여·해제 양방향 시각검증**을 이 배포 직후 함께 수행한다.
