# REV-20260910T170000-item03 — §18.8 적대 검증 패널 (security · backend · qa · ux)

- Related TASK: TASK-20260910-item03-product-atomic-create
- Trigger: `auth/인가` keyword matched (인가 데이터 생성 경로 — security 필수) +
  `schema/스키마`·`API/엔드포인트` (backend·qa) + `form/폼·화면` (ux). §12.3 Critical.
- Channel: 4 subagent (§18.11 4-item context bundle inject: changed_files · diff_excerpt ·
  task_md_content · acceptance_criteria). 리뷰어에게 `docs/SECURITY.md` §22·§28(§28.6) 과
  신규 ADR-20260910T130000-private-product-initial-owner 경로를 함께 전달했다.
- Rounds: 1 (지적) → 2 (수정 + 확인). 상한 3 (계획 미선언 시 기본).

## Round 1 verdicts

| Reviewer | Verdict | P1 | P2 | P3 |
|---|---|---|---|---|
| security | CONCERN | 0 | 2 | 1 |
| backend | **BLOCK** | 1 | 3 | 1 |
| qa | **BLOCK** | 1 | 2 | 1 |
| ux | **BLOCK** | 2 | 4 | 0 |

## P1 (전건 수정 — 각 지적이 실측으로 확인된 실 결함이었다)

### backend P1 — `WebPermissions.Label` 오버플로 (제품 이름 121~128자)
제품 이름은 `WebProducts.Name`(128) 과 `WebPermissions.Label`(128) **두 곳**에 쓰이고 Label 엔
`f"제품 접근 — {name}"` 의 접두 8자가 붙는다. 상한(128)을 정확히 지킨 **정당한** 이름이 Name
검사를 통과하고도 실 MySQL 의 Label 에서 1406 으로 죽고, 분류기는 `Label` 을 어느 분기에도
걸지 못해 「입력은 255자 이내」라는 **틀린** 400 을 냈다.
- 확인: 접두 8자 실측 → 128+8=136 > 128. stub cursor 는 컬럼 폭을 강제하지 않으므로 경계
  테스트(`test_a8b`)가 통과하고 있었다.
- 수정: 파생 문자열을 컬럼 길이로 **clip**(사용자 입력을 더 좁히지 않는다 — `model_access`
  seed 의 기존 규약과 동형). 상수 `PERMISSION_LABEL_MAX`/`PERMISSION_DESCRIPTION_MAX` 신설.
  분류기의 컬럼 판정을 부분문자열 → `column '...'` 정규식 + 정확 토큰 dict 로 교체(
  `"Name" in "SchemaName"` 오분류도 함께 해소). 매핑 없는 컬럼은 400 으로 위장하지 않고 500.
- 회귀 잠금: `test_a8b2`(파생 문자열 길이 직접 측정) · `test_a8b3`(DDL 동치) · `test_a8e2`.

### qa P1 — stub 이 「트랜잭션 존재」를 보지 못했다 (원자성 주장 미검증)
`_Conn.commit()/rollback()` 이 `autocommit` 과 무관하게 문자열만 적재했으므로, 정본에서
`conn.autocommit = False` 를 지워도 **70/70 전건 통과**했다. 실 MySQL 이라면 각 INSERT 가 즉시
확정되고 rollback 이 무효 → ITEM-03 이 없애려던 고립(E-03b)이 그대로 재현된다. **이 ITEM 의
중심 주장이 검증되지 않은 상태**였다(리뷰어가 결손 주입으로 실증).
- 수정: `_Cursor` 가 쓰기 문장 실행 시 `conn.autocommit` 을 확인해 `True` 면 raise.
  `dictionary=True` 커서도 지원(미지원 시 다음 사람이 test-double 인공물에 걸린다).
- 재확인: 같은 뮤턴트 재적용 → **18건 FAIL** (KILL). 뮤턴트 3종 전건 KILL, 생존 0.
- 부수 효과: 그 감시가 **선재 결함**을 드러냈다 — `admin_update_product_databases` 의
  `DELETE`→`INSERT` 루프가 트랜잭션 밖(backend P2 와 동일 지점). 승인 범위 밖이므로 원자화
  대신 `test_a9b2` 가 `pytest.raises` 로 그 사실을 **보이게** 못박았다.

### ux P1-a — §10.7(pending → 「모두 적용」) 위배 · **미해소, BLOCKED 로 상신**
`startNewProduct` 의 즉시 `POST` 에 이번 변경이 인가 결정(공개/비공개)을 추가했다. 리뷰어가
`roles.js::startNewRole` 이 **엔티티 생성**을 이미 스테이징한다는 선례를 제시 — 「생성은 원래
즉시였다」는 해명은 그 앞에서 성립하지 않는다. 두 해소 경로(생성을 pending 으로 전환 /
§10.7 예외를 ADR 로 선언) 모두 **승인 범위(DESIGN ITEM-03 what 1~5) 밖**이라 AGENTS §12.1
대로 `REPORT.md` 에 `BLOCKED: awaiting-human-approval` 로 남겼다. 반론(이번 변경은 즉시-쓰기의
폭발 반경을 **줄인다** — 종전엔 항상 전 역할 grant)도 함께 기록했으나 위배 사실은 인정한다.

### ux P1-b — 취소가 작성분을 버린다
4단계째 취소 한 번에 이미 쓴 설명(최대 255자)까지 사라졌다.
- 수정: 모듈 초안 캐시(`_newProductDraft`) — 어느 단계 취소든 다음 호출에 복원, 성공 시에만
  비움. 되돌릴 수 없는 접근 범위 선택 앞에 요약 confirm 추가(「되돌릴 수 없습니다」 명시).
  접근 범위 답 어휘 확장(오독 없이 마찰만 감소 — 인식 못한 답은 재질문 유지).
- 회귀 잠금: 하네스 C9(confirm) · C10(초안 복원) · C11(어휘) · `test_a10d2`.

## P2 (수정 / 정직 한정 / 상신)

- **security P2-1 · backend P2** 예외 문자열 노출 범위 완결성 → `admin_delete_product` 를
  분류기로 전환(제품 CRUD 3핸들러 완결). 같은 라우터의 다른 family 잔여 **9곳**은 승인 범위
  밖이라 유지하되, `test_a8h` 가 그 **모수 9를 고정**해 클래스가 조용히 늘지 못하게 했고
  `FUNCTION.md` AC-0639 에 보장 범위를 정직하게 한정했다.
- **security P2-2** 복구 스크립트 감사행의 사람 책임 소실 → `--operator <계정Id>` 필수화,
  `actor_type=account` + `ActorAccountId` 기록 + ChangeJson 에 operator·host OS 사용자.
  (`test_a11j`·`test_a11k`·`test_a11l`)
- **security §3-3** `bool("false") is True` 로 비공개 의도가 전 역할 공개로 뒤집힐 수 있었다 →
  `default_role_access` 를 **JSON boolean 전용**으로 좁힘(create·PATCH 양쪽). (`test_a6b`~`a6d`,
  `test_a9c`)
- **backend P2** `SchemaName` 게이트 128 vs DDL 64 → 64 로 정합(부분 쓰기 도달 차단). 루프의
  원자화는 후속. (`test_a9d`)
- **backend P2** 감사행을 생성 tx 로 옮긴 대가(동기 봉인 `GET_LOCK` 5s 구간에 락 보유 연장) →
  ADR Consequences 에 측정된 trade-off 로 기록.
- **ux P2** CSS 특이도 — `.admin-char-counter`(0-1-0) 가 `base.css` 의 `.field > span`(0-1-1)
  에 밀려 **규칙이 파일에 있어도 미적용**이었다. 실 Chromium 실측으로 확인·수정:
  pre-fix `rgb(90,88,82)`/600(필드 캡션과 동일) → post-fix `rgb(128,125,114)`/400.
  `.is-limit` 은 `--danger` → `--warning`(maxlength 가 초과를 막으므로 정상 값에 error 색은
  부적절). 미정의 토큰 `--muted` → 실제 토큰 `--text-muted`. (`test_a10c2`)
- **ux P2** 카운터가 래핑 `<label>` 의 접근가능 이름을 오염 → `aria-hidden="true"`. (하네스 C12)
- **ux P2** 혼합 배치 실패 토스트가 첫 사유를 전체 이유로 읽히게 함 → 사유가 갈리면
  「외 N건은 다른 사유」 부기. (`test_a10e`)
- **backend P3 · ux P2** `docs/STATUS.md` 가 feature-0046 행의 요지를 지웠다(`gen-status.sh`
  재생성의 부수 효과 — 그 feature 의 TASK frontmatter 에 `feature_status_note` 부재) →
  STATUS.md 를 HEAD 로 되돌리고 **내 행만** 수기 갱신. 남의 원장을 지우지 않는다.
- **qa P2** `visual_verification_scope: always` 가 실제로는 hard gate 가 아니다(`pending` 분기가
  FAIL 분기 앞에서 return 0) → 공유 게이트 스크립트는 수정하지 않고 `REPORT.md` 에 소유자·
  오케스트레이터용 사실로 기록.
- **qa P2** 패널 창 동안 파일이 계속 바뀌었다 → 인정. 최종 상태를 전건 재실행으로 확정했고,
  다음 cycle 은 dispatch 전에 diff 를 커밋으로 고정할 것을 REPORT 에 남겼다.
- **qa P3 / §3** 스테일 카운트(45·46·33·11개) → 실측값(76·66·50·10개)으로 정정.
  AC-03-1 「PATCH 가능」 미구속 → `test_a2b` 신설(두 권한 축 독립까지 고정).
  `PUT .../databases` 경계 통과 측 미검증 → `test_a9b2`. `sort_order` 비정수의 미처리
  ValueError → 400 으로 닫음(`test_a2c`). stub `rowcount = -1` → `test_a3b` 파라미터화.

## Round 2 (확인 라운드) — §18.8 (a)

P1 4건 중 3건 수정 · 1건(ux P1-a) BLOCKED 상신. 수정 후 재검:
- 결손 주입 3종 전건 KILL(autocommit 뮤턴트 18 FAIL 로 신규 KILL).
- `test_product_create_atomic.py` **76 passed**, 관련 회귀 **66 passed**,
  jsdom 하네스 **50 passed**, feature-0003 전체 **2219 passed**(선재 7건 제외 — 아래).
- 공용 helper 를 쓰는 다른 하네스 10개 + products.js 를 읽는 하네스 전부 재실행 — 회귀 0.
- 실 Chromium 으로 CSS 수정 전/후 대조(위 ux P2).
- 마지막 라운드 **P1 = 0**(잔여 1건은 승인 밖 BLOCKED — 수정 실패가 아니다).

### 선재 실패 (귀책 대조 — main 대비 차집합 0)

- `test_share_redaction_invariant.py` 7건: 호스트 직접 실행에서 `No module named 'web'`
  (컨테이너 레이아웃 전제). 내 변경 파일과 무관.
- `verify_folder_dnd_shared_group.mjs`: 원본 `esm-classic-inject.mjs`(git HEAD)로 되돌려도
  동일 실패 → 선재.
- ruff `F821` in `tests/test_conn_chip_css_scope.py`: base `b7aa2ac0` 에서도 동일 → 선재.
  내가 만지거나 추가한 파일은 ruff clean.

### 1. Blocking issues

`(no findings)` — 수정 후 확인 라운드 기준. 승인 범위 밖 1건은 §2 로 이관.

### 2. Cross-domain concerns

- `Evidence`: ux 패널이 `roles.js::startNewRole` 의 staged-creation 선례를 제시했고,
  `startNewProduct` 은 즉시 `POST` 로 인가 결정을 확정한다. `CONVENTIONS.md` §10.7 은
  보안 경계 mutation 에 예외를 두지 않는다.
  `Location`: `unit/feature-0003-agent-web-ui/src/static/admin/products.js:2150`
  `Reason`: 해소 경로 두 가지(생성을 pending 으로 전환 / §10.7 예외 ADR) 모두 승인 범위
  (DESIGN ITEM-03 what 1~5) 를 넘고, 후자는 프로젝트 컨벤션 개정이라 AI 자율 판단 대상이 아니다.
  `Action`: `REPORT.md` 의 `BLOCKED: awaiting-human-approval` 절 대로 사람이 ①/② 를 결정한다.
  ① 이면 후속 ITEM 분리, ② 이면 §10.7 에 예외·근거를 ADR 로 기록.

### 3. Challenge to current spec

DESIGN ITEM-03 의 `acceptance` 는 AC-03-1 을 「생성자 계정으로 `GET /api/admin/products/{id}`
200」으로 적었지만 **그 엔드포인트는 존재하지 않는다**(`admin_products.py` 의 GET 은 목록과
하위 리소스뿐). 이 cycle 은 관측 대체(생성자의 effective 권한에 코드가 서고 작업 화면 목록에
포함 + `product.update` 보유 시 PATCH 200)로 구속했고 그 사실을 TASK/Run 에 명시했다 —
DESIGN 문구는 다음 doc_sync 에서 실제 표면으로 정정해야 한다.
또한 「생성자 = 초기 소유자」는 개인 override 누적·대리 생성 미지원·감사 보존기간 종속이라는
세 비용을 남기며, 이번 결정은 그것을 ADR Consequences 에 수용 비용으로 적었을 뿐 해소하지
않았다. 주기적 고립 자동 진단(현재는 운영자 수동 호출뿐)이 가장 값싼 후속 방어선이다.

### 4. Verdict

CONCERN
