---
run_at: 2026-08-14T04:30:00+09:00
session: ai/claude/feature-0003-attach-createdat-utc
scope: [attach-createdat-utc, backfill-claim, iso-utc-z, composer-timezone-comment]
verdict: PRE-COMMIT PASS (pytest 12 + 전체 스위트 회귀 0 + ESM 구문) · POST-DEPLOY PB-0008 라이브 실측 필수
---

### Run (2026-08-14) — attach-createdat-utc: 첨부 시각 저장/전송 축을 UTC 로 — **Environment: Windows-browser (PB-0008 배포 후 실측 — 아래 사유로 배포 전 검증이 성립하지 않음, visual_verification_scope: always)**

- 대상 변경: `src/web_context.py`(1회 backfill + 선점/반납) · `src/routers/_bootstrap_schema.py`(DEFAULT
  DDL) · `src/routers/_conv_store.py`(`_iso_utc_z` + 직렬화) · `src/routers/attachments.py`(`lineages`
  시각) · `src/app.py`(re-export) · `src/static/app/composer.js`(**주석만** — 시간대 계약 설명 갱신).

- **배포 전 시각검증이 성립하지 않는 이유(정직)**: 화면에 보이는 첨부 시각이 맞는지는
  **① DB 백필이 끝나고 ② API 가 `Z` 를 붙인 뒤**에야 판정할 수 있다. 백필은 배포 시 startup 에서
  **1회만** 실행되므로 배포 전 환경에는 재현할 상태 자체가 없다. 지금 라이브 화면을 열면 배포 전
  코드·데이터라 이번 변경과 무관한 값을 보게 된다 — "검증했다" 고 적을 수 없는 종류다.
  프론트 변경분은 **주석뿐이고 실행 코드는 한 줄도 바뀌지 않았다**(`_attachWhenDate` 는 `new Date()`
  라 `Z` 가 붙으면 자동 정합 — 여기에 보정을 넣으면 이중 변환이 되어 오히려 틀린다).

- **PRE-COMMIT ① 계약 — `tests/test_attach_createdat_utc.py` 12 PASS**
  - **선점(3)**: INSERT 원자성으로 선점 · 이미 선점된 경우 2차 replica 무작업 · 선점 실패 시 무작업.
  - **반납(1)**: 작업 실패 시 `DELETE` 로 반납(반납하지 않으면 영영 재시도 안 됨).
  - **대상(4)**: 상한을 DEFAULT 전환 **이전에** 확정 · `WHERE Id <= %s` · 서버 오프셋 사용(+05:30
    배포 가정) · offset 0/빈 테이블은 UPDATE 없이 DEFAULT 전환만.
  - **저장소 분리(2)**: MySQL/PG 마커가 다르고 둘 다 선점된다 · 보정할 것이 없으면 PG 선점도 안 함.
  - **전송 계약(1)**: naive → `…Z`, tz-aware 는 그대로, None/비-datetime 은 None.
  - **스키마(1)**: fresh install 경로에도 같은 DEFAULT DDL.

- **PRE-COMMIT ② 회귀**: feature-0002 + feature-0003 전체 스위트 실패 **0**(잔여 6건은 선재 환경
  의존 파일 `test_share_redaction_invariant.py` — baseline 동일, `No module named 'web'`).
  `composer.js` ESM 구문 검사 PASS.

- **POST-DEPLOY 에서 확인할 것(필수)**:
  1. **데이터** — `CreatedAt > SupersededAt` 97건 · `CreatedAt > DeletedAt` 137건이 **0** 이 되는가.
  2. **미러 일치** — MySQL `CreatedAt` 과 PG `core_attachments.created_at` 이 같은 순간을 가리키는가.
  3. **화면(PB-0008)** — 첨부 목록·버전 이력의 시각 칩이 **업로드한 로컬 시각과 일치**하는가
     (9시간 이르거나 늦으면 전송 계약 또는 백필 중 하나가 틀린 것).
  4. **1회성** — 재배포 후에도 값이 또 밀리지 않는가(마커가 두 번째 실행을 막는지).
