---
run_at: 2026-08-24T16:33:00+09:00
session: ai/claude/attach-original-baseline
scope: REQ-20260824-attach-original-baseline — 계보 최초 원본(_v0) 능동 주입 + read_attachment 조상 확장
verdict: PASS
---

# TASK-20260824T0733-attach-original-baseline — 회귀 검증

- **Environment**: container (`make test` — 전용 compose 프로젝트 `repo-unittest`, 라이브 네트워크 미참여)
- **신규**: `tests/test_attach_original_baseline.py` **45 PASS**

## 무엇을 잠갔나

| 축 | 잠근 계약 |
|---|---|
| 표기 | `report.sql` → `report_v0.sql`(확장자 앞) · 무확장자는 말미 · 빈 이름은 `attachment_v0` |
| 렌더 조건 | v1 단일이면 **섹션 없음**(프롬프트 무변화) · v2·v3·v11 모두 트리거 |
| 대상 선택 | 체인에 v1·v2·v3 이 섞여 있으면 **최소 버전**이 원본 · 자기가 최초본이면 미렌더 |
| 본문 규약 | 줄번호 prefix + datamark sentinel(현재본과 동일) |
| 절단 표면화 | 건수 상한 초과 "N건" 명시 · 문자 상한 `[truncated]` · 비-text 는 `kind=` 사유 + `read_attachment` 안내 |
| 원인 단정 금지 | 본문 판독 실패는 "원인 미확인" — **`MinIO` 문자열 부재**(인프라 오귀속 회귀 잠금) |
| provenance | 타 계정 원본 **본문 렌더 시** 신호 ON · 자기 파일은 OFF · 목록만 실린 경우 OFF |
| 조회 술어 | 원본 조회 SQL 에 `ConversationId` · `DeletedAt IS NULL` · `DeletePending = 0` 실재 · 스코프 부재 시 빈 결과 |
| 도구 경계 | 조상 폴백 성공 · 계보 밖 id 거부 · **filename 경로는 조상 조회를 호출하지 않음**(되묻기 회귀 방지) |
| 리뷰어 정합 | 렌더된 원본이 `_review_attachments()` 결과에 `_v0` 이름으로 실림 · **렌더 안 된 원본은 안 실림** · run 경계에서 ctx 리셋 · bounded 발신자는 빈 목록 |
| 안내 정확성 | 현재본이 인라인됐으면 "위 본문 참조" · 안 됐으면 `read_attachment(attachment_id=…)` 로 안내(없는 증거 지시 금지) |
| 상한 우선순위 | 건수 초과 시 **이번 턴 신규 첨부의 원본이 살아남음**(목록 순서대로 자르면 밀린다) |
| 절단 경계 | 문자 상한이 **줄 경계**에서 잘림(조각 줄 금지) |
| provenance fail-closed | **caller 미상**(account_id 부재)에서 타 계정 원본 본문이 실리면 신호 ON |
| 조상 술어 | 같은 체인의 **더 최신** 버전 거부 · 더 낮은 버전 허용 · 삭제된 stale 스코프 id 로는 체인 미개방 |
| 라벨 정직성 | v1 삭제 체인은 `q_v2.sql` + "남아 있는 가장 이른 버전" 명시(`q_v0.sql` 금지) |
| 동명 계보 | 원본 이름이 겹치면 구분 규칙 주입 · 안 겹치면 미주입 |
| 지시 정합 | SYSTEM_PROMPT 가 `_v0`(전 이력)와 `FILE UPDATES`(마지막 한 걸음)의 범위 차이를 명시 · 도구 description 이 "이전 버전" 을 광고 |

## 하네스 설계 메모

기존 첨부 테스트의 `_RowsConn` 은 **모든 cursor 호출에 같은 rows** 를 돌려준다. 본 cycle 은 한
conn 으로 성격이 다른 조회 둘(현재본 목록 / 계보 최초본)을 돌리므로 그 하네스로는 원본 경로가
**검증되지 않는다**(무엇을 넣어도 통과). `_SqlRoutingConn` 이 실행된 SQL 로 결과를 갈라 그 사각을
없앤다 — 조회 술어 검사(`ConversationId`·`DeletedAt`) 도 이 라우팅 덕에 가능하다.

## 무관 실패 1건 — 원인·조치

`test_oauth_exhaustion_gate.py::test_write_failure_after_successful_post_cannot_kill_slot_selection`
이 처음 실행에서 FAIL 했다. **main HEAD(`8a541018`)에서도 동일 재현** — 본 cycle 과 무관한
러너 환경 결함이다.

- 원인: 테스트 이미지에 `chattr` 바이너리가 없어 `subprocess.run(["chattr", …])` 이
  `FileNotFoundError` 를 던진다. 가드는 `returncode != 0` 만 보고 skip 하려 했는데, **예외는 그
  검사에 도달하지 않는다** — skip 되어야 할 케이스가 FAIL 로 뜬다.
- 조치: 그 호출을 `try/except OSError → pytest.skip` 으로 감쌌다(가드가 예외까지 덮게). 직전 커밋
  `a62d21c0`("CI 러너는 비-root")과 같은 계열의 환경 게이팅 보강이며, 검증 대상 로직은 무변경이다.

## 라이브 데이터 대조 (읽기 전용 — 변경 0)

단위 테스트는 하네스가 준 행을 본다. **선택 로직이 실제 체인에서 옳은 행을 고르는지**와
**그 원본이 실제로 읽히는지**는 라이브 조회로 따로 확인했다(모두 read-only).

| 체인(root) | 길이 | 원본 | 현재본 | 본문 |
|---|---|---|---|---|
| 1086 `usp_replication_steam_log.sql` | 11 | id=1086 v1 (`SupersededAt` 有) | id=1096 v11 (live) | **1,735B/60줄 → 10,176B/322줄 (5.9×)** |
| 1222 `drop_statistics_all_logs_integrated.sql` | 8 | id=1222 v1 | id=1229 v8 | 6,636B/100줄 → 5,058B/97줄 |

- `COALESCE(RootAttachmentId, Id)` 그룹 + 최소 `VersionNumber` 가 **정확히 v1 을 고른다**(라이브 2건).
- 두 원본 모두 `storage_minio.get_object_bytes` 로 **정상 판독** — 구버전 객체는 supersede 후에도
  살아 있다. 다중버전 구버전 245건 전부 미삭제(`DeletedAt IS NULL`) 상태다.
- 11버전 체인은 원본 대비 **5.9배**로 커졌다. 종전에는 이 원본이 assistant 에게 보이지 않아
  "처음과 지금의 차이" 를 물어도 최신본만 보고 답할 수밖에 없었다 — 이 cycle 이 여는 것이 정확히
  그 대조다.

> **검증 절차 자기 정정**: 최초 시도는 `LEFT(ObjectKey,60)` 으로 **절단된 키**를 조회해 두 건 다
> `NoSuchKey` 를 받았고, 잠시 "구버전 객체가 정리됐다" 로 오독했다. 전체 키로 재조회하니 둘 다
> 정상 판독됐다. 절단된 값을 원본 키로 쓰면 부재가 아닌 것이 부재로 보인다 — 이 저장소가
> 첨부 절단 표기에 반복해 적어 온 것과 같은 함정이 검증 절차 쪽에서 재현된 사례다.
