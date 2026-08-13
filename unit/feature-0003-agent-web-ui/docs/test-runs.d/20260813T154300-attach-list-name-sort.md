---
run_at: 2026-08-13T15:43:00+09:00
session: ai/claude-corp/attach-list-name-sort
scope: attach-list-name-sort (REQ-20260813-attach-name-sort)
verdict: PASS
---

# Run 1 — 프리뷰 컨테이너 A/B 실측 (PB-0008)

- **Environment: Windows-browser** — 실 Chrome/150(CDP relay), §13.2.9 격리 프리뷰 2대:
  - `web-attach-name-sort-preview` — worktree `src` 마운트, `http://localhost:18099` (**수정 후**)
  - `web-attach-name-sort-baseline` — main `src` 마운트, `http://localhost:18098` (**수정 전**)
  라이브 web-a/web-b·Caddy 무접촉. 두 컨테이너 모두 `/healthz` 200.
- 데이터: 라이브 대화 `20260804051001-774ada22`(첨부 39건, 소유자 kumin — bootstrap_admin 이
  read.any 로 **열람만**). `08051122_`·`v2_`·`v2_1_`·`v3_` 접두가 섞여 있어 정렬 판별력이 있다.
- 절차: 자기 생성 탭(`context.new_page()`)에서만 조작(§16.6 세션 격리 — 공유 CDP 에 병렬 세션 탭
  2개가 이미 열려 있었고 건드리지 않았다. 종료 시 자기 탭만 닫아 `pages` 2 → 2 복귀).
  로그인 → 검색(`v2_1_P_billing`) → 대화 진입 → `+` → `첨부파일 목록`.

## 결과 — A/B

| | 화면 목록 앞 6건 |
|---|---|
| **수정 전**(:18098) | `P_gunzgame_Game_MasangCreatorsGetByAID` → `P_gunzgame_Game_AccountCharacterExists` → `T_gunzgame_masangcreators` → `D_billing_rep_create` → `T_billing_rep_steambillinglog` → `v2_D_billing_rep_create` (= 업로드 순, DB `Id ASC` 와 일치) |
| **수정 후**(:18099) | `08051122_P_gunzgame_Game_MasangCreatorsStart` → `08051122_P_gunzgame_Game_MasangCreatorsStop` → `08051122_T_gunzgame_masangcreators` → `08051122_T_gunzlog_masangcreatorshistory` → `D_billing_rep_create` → `P_billing_rep_sp_getsteambillingloglastrefundtime` (= 완전 이름순, 39건 전건) |

- **자연 정렬 실증**: `v2_1_P_billing_rep_sp_insertsteambillinglog.sql` 이 `v2_D_billing_rep_create.sql`
  **앞**에 선다 — 숫자 조각이 문자 조각보다 앞서는 키가 실제로 작동한 결과(사전순이면 `D` < `1` 이
  아니라 `1` < `D` 지만, 자리수 섞인 접두 `_02_` vs `_10_` 축과 같은 기전).
- **화면 = 서버 응답**: 같은 세션에서 `GET /api/conversations/{cid}/attachments` 를 직접 호출한
  순서와 화면에 그려진 순서가 **전건 일치**(프론트가 재배열하지 않음 = 서버 SSOT).
- 증거: `../evidence/pb0008-attach-name-sort-1-sorted.png`(수정 후) ·
  `../evidence/pb0008-attach-name-sort-2-baseline.png`(수정 전).
- **라이브 데이터 변경 0** — 열람 경로만 사용(첨부 생성·삭제·편집 없음, 대화 전송 없음).

## 자동 테스트

- 신규 `tests/test_attach_list_name_sort.py` — **12 passed**
  (N1 숫자 수치비교 + "사전순이면 순서가 달라진다" 역단언 · N2 casefold · N3 한글 가나다 ·
  N4 None/빈 이름 · S1 tie-break(version→id) · S2 PG 형상 행 · B1 체인 인접 · B2 체인 대표=최신 이름 ·
  A1 목록 API 응답 순서 · A2 휴지통 이름순 + 절단 SQL(`DeletedAt DESC`·`LIMIT 200`) 불변 ·
  A3 bulk 경로가 정렬 헬퍼 경유 · P1 PG alias 계약 + PG SQL 에 이름 ORDER BY 없음).
- 회귀: 첨부·대화 관련 `-k "attach or conv"` **391 passed**. 전체 스위트(feature-0002/0003/0023)는
  `test_oauth_exhaustion_gate` 1건 실패 — 컨테이너에 `chattr` 바이너리가 없어서이며 **pristine main
  체크아웃에서 동일 재현**(같은 이미지·명령으로 실측) → 환경 의존 선재 red, 본 cycle 귀책 아님.
- `ruff check` — All checks passed.

- **Pass/Fail: PASS** (배포 후 baked 자산 POST-DEPLOY 재실측은 이월).

# Run 2 — POST-DEPLOY 라이브 실측 (baked 자산)

- **Environment: Windows-browser** — 실 Chrome/150, `https://localhost/`(Caddy → web-a/web-b).
- 배포: PR #1251 → main `7afed974` → `sudo bash bin/deploy-web.sh --web-only`. 양 replica
  `mysql-ai-web:7afed974` · soak 통과 · 엣지 `no upstreams available` **0건**(무중단 실측) · `/healthz` 200.
- 결과 A — 프리뷰와 같은 대화(첨부 39건): 화면 목록 **전건 이름순**, Run 1 과 차이 0.
- 결과 B — **사용자 요청의 출발점이 된 그 파일 세트**(`20260709_[MV] Log_v2 이슈 대응_*.sql` 6건,
  요청 스크린샷에서 `08 → 01 → 02 → 03 → 04 → 09` 로 흩어져 있던 것):
  라이브 배포본에서 `01_rename_table → 02_refill_table_trigger → 03_refill_table_schedule →
  04_proc_log_schedule → 08_fix_log_tables → 09_fix_schedule` 로 정렬 — 요청이 화면에서 이행됨.
- 증거: `../evidence/pb0008-attach-name-sort-3-postdeploy.png`.
- 라이브 데이터 변경 0(열람 경로만).
- 이월: 없음 — 본 Run 으로 시각검증 축 종결. (업로드 **직후** pill 순서의 실브라우저 실측은
  업로드가 곧 라이브 데이터 변경이라 하네스로 대체한다는 Run 1 의 기록 유지.)
