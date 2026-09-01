---
run_at: 2026-09-01T19:00:00+09:00
session: ai/root/kb-grounding-match
scope: grounding 매칭 — 한도는 «매칭 후보»에, 판정은 «낱말 경계»로 (20260901T190000-kb-grounding-match)
verdict: PASS
---

### Run 0 — 결함 발견 (Environment: 배포본 `5a4d49fc` 안에서 GZ_QA_G 라이브 실측)
사용자 요청으로 직전 cycle 을 GZ_QA_G 로 실측하다 나왔다. **코드 리뷰로는 안 나올 결함**이다 —
둘 다 데이터의 규모·모양에 의존한다.

- 실제 GZ_QA_G task(`t_agRxTIgcrVlElJz3`, ProductId=119)로 `get_task_context` 구동 → 200 OK,
  `product.gz_qa_g` 해소, 번들 1,704자, 2개 층(용어·ENUM / 관계).
- **①** 배포본에서 `_fetch_glossary` 를 직접 호출: scope 총 **239행** 중 **200행만** 로드,
  `ORDER BY length DESC` 라 탈락 39건이 전부 최단 항목 —
  `AID`·`CCU`·`CID`·`CIID`·`PvE`·`재화`·`캐시`·`드롭`·`업적`·`복합키`·`선택도` ….
- **②** 자연스럽게 쓴 질문의 `BillingType` 이 컬럼명 `Type` 에 부분일치 →
  **DK온라인** ENUM(`Achievement.Type`)이 GZ_QA_G 번들에 유입. `Type` 단독으로도 재현.
  라이브 데이터로 `ACIDITY`→`CID`, `PvErr`→`PvE`, `소재화`→`재화` 도 같은 형태임을 확인.

### Run 1 — 경계 규칙 단위 (Environment: bare-runner pytest)
- 15종 표를 손으로 검증(오탐 차단 5 / 정상 유지 10) → 전건 기대 일치.
- `test_grounding_match.py` **13 passed** — ASCII 경계 · 한국어 조사 허용 · 한글 접두 차단 ·
  혼합/구분자 · 빈 입력 · SQL 후보필터(연접항 집합) · 한도 로그 · 배선 4건.

### Run 2 — 뮤테이션 실증 (§16.7 G11-b)
- ⚠ **1차 라운드 전량 무효**. 베이스라인이 RED 였다(내 SQL 재구성이 기존
  `test_role_scoped_read_sql` 을 깼는데, 그 실패가 7종 중 5종을 「KILL」로 보이게 했다).
  **뮤테이션은 baseline green 확인이 전제다** — 빠뜨리면 「전부 잡았다」는 가장 안심되는
  형태의 거짓 신호가 나온다.
- 기존 테스트 정정(파라미터를 위치 대신 **내용**으로 조회) 후 baseline GREEN → 재실행.
- 2차: 3종 생존(N1·N2 배선 미검사 / N8 부분 문자열 단언이 약화 뮤턴트를 통과).
  배선 테스트 3건 + 연접항 집합 단언으로 보강.
- 3차 **9/9 KILL** (N1~N9, baseline GREEN 확인 후).

### Run 3 — 컨테이너 전건
- `COMPOSE_PROJECT_NAME=repo make test` → **rc=0 · FAILED 0 · 6,904 tests** · ruff clean.

### Run 4 — 라이브 전후 대조 (Environment: 라이브 이미지 + 수정 소스 bind-mount, 라이브 무접촉)
같은 질문을 배포본(`repo-web-a-1`)과 수정본(`web-verify-gm`)에 각각 넣었다.

    질문: "gz_qa_g 에서 steam_billing_log 의 status 코드와 billingsummary 의 BillingType,
           증분 복제와 파티셔닝 키"

| 항목 | 수정 전(배포본) | 수정 후 |
|---|---|---|
| `steam_billing_log` · `billingsummary` · `파티셔닝 키` | 실림 | 실림(유지) |
| **`증분 복제`** (질문에 있음) | **누락** — 한도 밖 | **회복** |
| **`Achievement.Type`** (DK온라인, 질문에 없음) | **유입** | **차단** |
| `billingsummary.BillingType` · `steam_billing_log.status` · `steambillinglog.status` | 실림 | 실림(유지) |

**정상 매칭을 하나도 잃지 않고** 누락 1건 회복 + 오탐 1건 차단.

### Run 5 — POST-DEPLOY (배포 후 기록)
