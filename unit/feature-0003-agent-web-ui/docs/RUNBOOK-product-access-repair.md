---
doc_type: RUNBOOK
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: true
runbook_id: product-access-repair
related_task: TASK-20260910-item03-product-atomic-create (DESIGN ITEM-03 / DQA-03)
---

# 고립 Product 접근 권한 복구 Runbook

접근할 수 있는 활성 계정이 **0명**인 제품(이하 «고립 Product»)을 진단하고, 운영자가 지정한
계정 1개에 접근 권한을 되돌린다.

**핵심 원칙**: 스크립트는 **대상 계정을 추론하지 않는다.** 인가 데이터를 만드는 일이므로
「누가 이 제품을 써야 하는가」는 사람이 결정한다(AGENTS `§12.3` Critical). 진단이 출력하는
「생성자 후보」는 **참고 정보**이며 기본값이 아니다.

---

## 1. 언제 쓰는가

- 비공개 제품을 만들었는데 생성자·관리자 모두 접근할 수 없다(권한 부여 시도도 403).
- 제품을 쓰던 유일한 계정이 비활성/삭제되어 그 제품에 아무도 못 들어간다.
- 역할에서 `product.access.<key>` 를 회수했는데 대체 부여를 빠뜨렸다.

> ⚠️ **2026-09-10 이후 새로 만든 제품은 이 상황이 되지 않는다.** `POST /api/admin/products` 가
> 코드 생성과 같은 트랜잭션에서 공개면 역할 backfill, 비공개면 생성자 grant 를 반드시 수행한다
> (`docs/DECISIONS.md` ADR-20260910T130000-private-product-initial-owner ·
> `docs/SECURITY.md` §28.6). 이 runbook 은 **그 수정 이전에 이미 생긴 데이터**와 위 2·3번
> 운영 경로를 위한 것이다.

## 2. 전제 조건

- `repo-web-a-1` 또는 `repo-web-b-1` 컨테이너가 떠 있다(`sudo docker ps` 로 확인).
- docker 소켓 접근 권한. 배포 계정이 docker 그룹에 없으면 래퍼가 `sudo -n docker` 로 폴백하므로
  먼저 `sudo -v` 로 자격을 갱신한다.
- 어떤 계정에 부여할지 **결정할 수 있는 사람**이 함께 있다(2단계 결과만으로 자동 진행하지 않는다).

## 3. 진단 (읽기 전용 — 기본 동작)

```bash
bin/product-access-repair.sh                  # 활성 + 비활성 제품 전부 (기본)
bin/product-access-repair.sh --active-only    # 활성 제품만으로 좁힘
bin/product-access-repair.sh --json           # 기계 판독
```

> ⚠️ **기본이 「전부」인 이유**: 2026-09-10 라이브 dry-run 에서 요구서가 지목한 고립 제품
> 990002 가 **비활성**이었고, 활성만 훑던 초기 기본값은 「고립 Product 없음」을 출력했다.
> 고립된 제품은 운영자가 이미 비활성으로 내려 둔 경우가 오히려 흔하다 — 진단은 넓게 보고,
> 좁히는 것만 명시한다.

출력 예:

```
고립 Product 1건:
  - #990002 PRIV '비공개 제품' active=Y default_role_access=N code=product.access.priv
    reason=no_grantee · 생성자 후보 account=7(mckim) @2026-09-09 06:32:17

복구: --apply --product <제품Id> --grant-account <계정Id>  (계정은 운영자가 지정)
```

읽는 법:

| 필드 | 의미 |
|---|---|
| `reason=no_grantee` | 권한 코드는 있는데 접근 가능한 활성 계정이 0명 → **이 runbook 의 대상** |
| `reason=missing_permission` | 동적 권한 행 자체가 없다 → 부여할 대상이 없다. §6 으로 |
| `default_role_access=N` | 비공개 제품(역할 자동 grant 없음) |
| `active=N` | 비활성 제품. 고립의 흔한 형태다 — 되살리려면 접근 부여 + 제품 활성화 둘 다 필요 |
| `생성자 후보` | 생성 감사행(`admin.product.create`)의 actor. **참고값** |

> **규모**: 진단은 제품 1건당 grantee 집계 1회(고립 제품엔 감사 조회 1회 추가) — 제품 수에
> 비례하는 read 왕복이다. 운영자가 직접 부르는 CLI 이므로 현재 카탈로그 규모에서는 문제가
> 아니지만, 제품이 수백 개로 늘면 배치 집계(`PermissionId IN (...) GROUP BY`)로 바꾼다.

유효 grantee 판정은 런타임 정본(`web_context._apply_permission_overrides`)과 같은 규칙이다 —
계정 `allow` override 는 접근, `deny` override 는 차단(역할 grant 를 덮는다), 그 외에는 **활성
역할**(`WebRoles.IsActive = 1`)의 역할 grant. 진단은 SELECT 만 실행한다.

## 4. 대상 계정 결정 (사람)

다음을 확인한 뒤 계정 1개를 고른다.

- 그 제품의 업무를 실제로 수행하는 계정인가.
- 활성 계정인가(`IsActive = 1`, 삭제되지 않음). 아니면 스크립트가 `account_inactive` 로 거부한다.
- 관리 콘솔에서 그 계정에 **명시 `deny`** 가 걸려 있지 않은가. 걸려 있으면 스크립트가
  `deny_override_present` 로 **중단한다** — 명시적 거부를 스크립트가 뒤집지 않는다. 먼저 콘솔에서
  `inherit` 로 해제한다.

여러 계정이 필요하면 **부여받은 1명이 관리 콘솔에서 나머지에게 부여**한다. 그 시점에는 부여자가
그 코드를 보유하므로 self-scope 가드(`docs/SECURITY.md` §28.6)를 통과한다. 스크립트로 여러 계정을
반복 부여하지 않는다(콘솔이 감사·검토가 붙는 정상 경로다).

> ⚠️ **남을 위해 복구했다면 자기 override 를 되돌린다.** 관리자가 자기 계정에 부여해 확인한 뒤
> 실 소유자에게 넘기는 경우, ①실 소유자 부여 → ②**자기 override 를 `inherit` 로 회수** 두
> 단계가 모두 필요하다. ②를 잊으면 제품과 무관한 계정이 영구 접근권을 갖는다 — 역할 단위
> 회수로는 지워지지 않는 개인 override 이기 때문이다(`docs/DECISIONS.md`
> ADR-20260910T130000-private-product-initial-owner Consequences).

**복구 후보가 비어 있을 때**: `생성자 후보` 가 「감사 기록 없음」이면 생성 감사행이 보존기간을
지났거나 ITEM-03 이전 데이터다. 이때 스크립트는 추측하지 않는다 — 그 제품의 업무 담당을 아는
사람이 계정을 정한다.

## 5. 복구 (`--apply`)

```bash
bin/product-access-repair.sh --apply --product 990002 --grant-account 7 --operator 7
```

`--operator <계정Id>` 는 **이 복구를 수행하는 사람의 계정**이며 감사행의 actor 로 남는다.
생략할 수 없다 — 인가 데이터를 만드는 조작이라 「누가 부여했는가」가 감사 시스템 안에서
답해져야 한다. 보통 `--grant-account` 와 같은 값이지만 대리 수행이면 다르다.

- `WebAccountPermissionOverrides` 에 `(account, permission, 'allow')` **1행**만 INSERT 한다.
  기존 override 를 읽지도 지우지도 않는다.
- 권한 행 + 감사행(`admin.product.access.repair`, `ActorType=system`,
  `TargetAccountId=<부여 계정>`)이 단일 commit 이다. 영향 행 0 이면 전체 rollback.
- 이미 `allow` 면 `already_allowed` 로 **무변경 종료**(멱등 — 재실행이 안전하다).

출력 말미의 **사후 검증**을 반드시 확인한다:

```json
{"status": "ok", "product_id": 990002, "account_id": 7, "username": "mckim", "permission_code": "product.access.priv"}
```
```
사후 검증: 이 제품의 잔여 고립 0건 (0 이어야 정상) · 전체 잔여 고립 0건
```

`잔여 고립 0건` 이 아니면 exit code 2 다 — 그 경우 §7 로 간다.

## 6. `missing_permission` (권한 행 자체가 없음)

동적 권한 행(`WebPermissions` `IsDynamic=1, ProductId=<제품>`)이 없으면 부여할 대상이 없다.
부트스트랩의 `_ensure_product_access_permissions` 가 모든 제품에 대해 `INSERT IGNORE` 로 행을
만들므로, **web 컨테이너를 재기동**(`sudo make web/up` 또는 `bin/deploy-web.sh`)한 뒤 §3 을 다시
돌린다. 스크립트는 권한 카탈로그를 새로 만들지 않는다(범위 밖 — 카탈로그 생성은 부트스트랩의 책임).

## 7. 실패 코드와 대응

| status / exit | 의미 | 대응 |
|---|---|---|
| `product_not_found` | 그 Id 의 제품이 없다 | §3 으로 Id 확인 |
| `not_orphan` | 이미 접근 가능한 계정이 있다 | 복구 불필요. 개별 계정 문제면 콘솔에서 처리 |
| `missing_permission` | 동적 권한 행 부재 | §6 |
| `account_not_found` / `account_inactive` | 대상 계정 없음·비활성 | 활성 계정을 고른다 |
| `deny_override_present` | 명시 거부가 걸려 있다 | 콘솔에서 `inherit` 로 해제 후 재시도 |
| exit 2 (컨테이너) | 실행 중인 web 컨테이너 없음 | `sudo make web/up` |
| exit 2 (사후 검증) | 복구 후에도 고립 잔존 | 부여 계정이 **비활성 역할**만 갖고 있거나 다른 `deny` 가 있는지 확인. 진단 `--json` 으로 grantees 를 다시 본다 |
| `operator_not_found` / `operator_inactive` | `--operator` 계정이 없거나 비활성 | 활성 계정 Id 를 쓴다 |
| exit 2 (구세대 이미지) | 대상 컨테이너 `app` 에 필요 심볼 부재 | 배포 완료 후 재시도 |
| exit 3 | docker 접근 불가 | `sudo -v` 후 재시도 |

## 8. 롤백

복구가 만든 변경은 **행 1개**다. 되돌리려면 관리 콘솔 > 계정 상세 > 해당 제품 카드의 override 를
`inherit` 로 바꾸고 「모두 적용」한다(콘솔 경로가 감사행을 남기는 정상 수단). 되돌리면 그 제품은
다시 고립될 수 있으므로, 대체 부여를 먼저 정한 뒤에 한다.

## 9. 검증

- 자동: `unit/feature-0003-agent-web-ui/tests/test_product_create_atomic.py` `test_a11`~`test_a11i`
  (dry-run 읽기 전용 · 자동 선택 거부 · deny 미역전 · 멱등 · 적용 후 재진단 0건 · 비활성/미존재
  계정 거부 · 래퍼가 스스로 `--apply` 를 붙이지 않음).
- 라이브: 이 runbook 을 실제 DB 에 적용한 기록은 각 실행 시점의 `docs/test-runs.d/` Run 에 남긴다.
  **2026-09-10 ITEM-03 cycle 시점에는 라이브 apply 를 실행하지 않았다** — Product 990002 의 대상
  계정 지정은 운영자 결정이다.
