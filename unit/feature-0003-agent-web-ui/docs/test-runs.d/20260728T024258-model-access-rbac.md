---
run_at: 2026-07-28T02:42:58+09:00
session: ai/claude/feature-0003-model-access-rbac
scope: [rbac, model-access, permission-grid, api-token-scope, bootstrap-seed]
verdict: PASS (PRE-COMMIT 단위 25 + 전체 회귀 rc=0 + ruff / POST-DEPLOY PB-0008 부여·해제 양방향 검증 예정)
---

### Run (2026-07-28) — model-access-rbac (계정/역할별 모델 사용 권한) — **Environment: CLI (컨테이너 pytest) + Windows-browser 는 POST-DEPLOY**

cycle: `ai/claude/feature-0003-model-access-rbac` · 사용자 요청("R2도 계정/역할 별 권한 범위를 구성해주세요")
· 사용자 승인 = **전부 기본 부여**(무회귀) · Critical §12.3(인가 구조 변경).

- **PRE-COMMIT 단위 25 PASS** — `tests/test_model_access_rbac.py` G1~G8:
  - G1 코드 namespace(`model.access.<value>`, 빈 값 → 빈 코드) + 카탈로그 전 모델 매핑 커버.
  - G2 판정표 — 보유 True / **row 등록 + 미보유 False**(★ fail-closed 핵심) / override '거부' False /
    account None False / 빈 model False / **카탈로그 밖 model True**(400 축과 분리).
  - G3 부트스트랩 지연·DB 오류 → 통과 + **WARNING 기록**(조용한 전원차단 금지).
  - G4 `conn=None` 우회 차단 — 미보유는 거부.
  - G5 표시 필터 + **전부 차단 시 원본 유지**(display-permissive · backend-enforced).
  - G6 API 토큰 scope **면제**(기존 토큰 무회귀) + 계정 권한·절대 denylist 경계 유지.
  - G7 **★ 재부트스트랩 re-grant 금지** — 신규 row 만 전 역할 grant, 기존 row 는 grant 미변경
    (매 배포가 관리자의 해제를 되살리면 기능 자체가 무의미해진다). 신규 모델 추가 시 그 모델만 grant.
  - G8 프론트 parity — admin.js/app.js `model_access` 그룹 키·operate section 포함 ·
    `excludeDynamic` 이 `product_access` 로 좁혀졌는지 · app.js prefix 명시 매핑.
- **전체 회귀**: feature-0002 + feature-0003 전체 pytest **rc=0**(fail/error 0) · `ruff check` All passed ·
  `node --check`(ESM) app.js/admin.js OK.
- **Environment: Windows-browser (PB-0008) — POST-DEPLOY 로 이관, 사유 명시**: 본 cycle 이 추가하는
  화면 요소(권한 grid 의 '모델 사용' 그룹 row)는 **백엔드가 부트스트랩에서 seed 한 동적 권한 row 를
  `/api/admin/permissions` 로 받아 렌더**한다. 즉 배포 前에는 라이브 화면에 그릴 데이터 자체가 없어
  사전 시각검증이 성립하지 않는다(코드만 얹어도 grid 에 안 나옴). 따라서 시각·인터랙션 검증은
  배포 직후 POST-DEPLOY 로 수행하며, 아래 3항목을 **부여·해제 양방향**으로 실측한다:
  1. 역할 편집기 '운영 권한 > 모델 사용' 그룹에 모델 3종 row 렌더 + 초기 전부 체크(무회귀 확인)
  2. 특정 역할에서 `claude-opus` **해제 → '모두 적용'** → 해당 계정 로그인 시 선택기에서 opus 소멸 +
     직접 요청 시 403
  3. 다시 **부여 → '모두 적용'** → 선택기 복귀 + 요청 200 (양방향 복원)
- **비-변경(의도)**: 스키마·마이그레이션 0(기존 `WebPermissions`/`WebRolePermissions` 재사용) ·
  `API_DEFAULT_MODEL`=haiku 불변 · 기존 권한/역할/제품 동작 무변경 · 배포 직후 동작은 현행과 동일.
