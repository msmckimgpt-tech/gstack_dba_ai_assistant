---
run_at: 2026-08-06T17:10:00+09:00
session: ai/claude/feature-0003-attach-manage
scope: feature-0003-agent-web-ui / REQ-20260806-attach-manage
verdict: PASS
---

### 20260806T1541-attach-manage 첨부 삭제(버전 선택)·복구·일괄 다운로드 (Critical §12.3, 2026-08-06, feature-0003 web/UI) — **Environment: Windows-browser — PASS (레이아웃 축 + POST-DEPLOY e2e 왕복)**

- **무엇**: 대화 첨부를 목록에서 버전 단위/체인 단위로 삭제(soft-delete)하고, retention 창
  안에서 휴지통으로 복구하며, 대화 첨부 전량을 ZIP 또는 개별로 내려받는다.
- **기대**: (1) 버전 삭제 시 직전 버전 승격 (2) 체인 삭제 시 목록에서 제거 (3) 업로더·대화
  소유자만 삭제·복구 (4) retention 창 안 복구 (5) ZIP/개별 × 최신본/전 버전
  (6) **패널 최소 폭에서 파일명·배지·버전 토글이 잘리지 않는다**.

#### Run 1 — **Environment: Windows-browser** (2026-08-06, 실 Windows Chrome 150.0.7871.128 via `bin/win-browser.py` relay) — **PASS (W1~W5, 240/280/360px)**

실행: `python3 unit/feature-0003-agent-web-ui/tests/pb0008_attach_manage_width.py`

실 `base.css`+`chat.css` 를 로드한 페이지를 실 Windows Chrome 에 띄워 **렌더된 기하를 직접**
측정했다(§16.6 — 레이아웃·잘림은 element 상태로 검증할 수 없는 픽셀-클래스 변경).

| 패널 폭 | 목록 파일명 가용폭 | 버전 행 파일명 | 배지 잘림 | "버전 N개 ▾" 잘림 | 헤더 간격 |
|---|---|---|---|---|---|
| 240px (최소) | **103.3px** | **142.9px** | 없음 | 없음 | 4 / 10px |
| 280px (기본) | 143.3px | 182.9px | 없음 | 없음 | 4 / 10px |
| 360px | 223.3px | 262.9px | 없음 | 없음 | 4 / 10px |

§18.8 design 패널이 수정 전 상태에서 실측한 값은 240px 기준 목록 **37.8px(≈3자)** ·
버전 행 **23.2px(≈2자)** 였다. 2줄 행 재구성으로 회복됐다.

#### Run 2 — **역검증**(`--negative`, 액션을 수정 전 배치인 행 우측으로 되돌림) — **의도대로 FAIL**

```
W1 240px 목록 파일명 가용폭 46.9px < 96.0px
W1 280px 목록 파일명 가용폭 86.9px < 96.0px
```

하네스가 실제로 회귀를 잡는다. **정직 표기**: 이 negative 에서 **버전 행 축(W2)은 발화하지
않았다** — negative 마크업의 버전 행 이름이 임계(72px)를 넘었다. W2 는 현행 구조의 유지를
지키지만 "수정 전 대비 개선" 을 스스로 증명하지는 못한다. (design 패널의 23.2px 는 이모지
글리프 advance 를 1.16em 으로 치환한 headless 측정이고, 본 하네스는 실 Segoe UI Emoji 를
쓰는 실 Chrome 이라 절대값이 다르다 — 방향은 일치.)

#### Run 3 — 마크업 drift 가드

하네스가 쓰는 클래스(`attach-list-item-metatext`·`attach-list-item-actions`·
`attach-list-version-head`·`-foot`·`-actions`)가 실 `composer.js` 에 존재하는지 확인한 뒤에만
측정한다 — 없으면 `MARKUP DRIFT` 로 exit 2. 하네스 마크업이 렌더러와 어긋나면 이 측정은
아무 것도 증명하지 못하기 때문.

#### 이월 — 삭제·복구·다운로드 **e2e 흐름**은 POST-DEPLOY

본 cycle 의 상호작용 검증(실제로 지우고 → 휴지통에서 되살리고 → ZIP 을 받는 왕복)은 라이브
서버·MinIO·PG 미러가 함께 필요하다. 정적 자산이 web 이미지에 baked 되는 구조라 사전 docker cp
QA 가 성립하지 않는다(ESM 모듈 캐시 이중 인스턴스 — 선행 cycle 실측). 따라서 배포 후
POST-DEPLOY 로 수행하고 그 결과를 본 fragment 에 append 한다. 확인 항목:

- [ ] 버전 3개 첨부에서 최신만 삭제 → 목록에 v2 가 최신으로 남는가(AC-1)
- [ ] `scope=chain` 삭제 → 목록에서 사라지는가(AC-2)
- [ ] 휴지통에서 ↩ 복구 → 목록·AI 참조 스코프 재등장(AC-4), 체인 복구(⇤)
- [ ] 남은 기간 표시가 서버 판정과 일치(타임존 보정 확인)
- [ ] ZIP 다운로드 파일 수 == 목록 수(AC-6), 전 버전 모드 `_v<n>`(AC-7)
- [ ] 개별 다운로드 순차 저장(AC-9)
- [ ] 삭제 직후 목록이 pill 로 덮이지 않는가(§18.8 ux P1 회귀)
- [ ] `WebAuditEvents` 에 `attachment.restore`·`attachment.bulk_download` 행 생성(§18.8 security P1 회귀)

#### 부수 검증

- `make test` 전 스위트 — 결과는 본 fragment 의 POST-DEPLOY append 와 함께 기록.
- 신규 pytest 45건(`tests/test_attach_manage.py`) — 인가 8 · scope 3 · 승격 5 · 복구 8 ·
  ZIP 7 · 휴지통 6 · 미러 2 · audit 1 · 원자성 3 · 구조 가드 2.
- ESM `node --check` — `app/composer.js`·`app.js`.

#### Run 4 — **POST-DEPLOY e2e 왕복** (2026-08-06, 배포 `5000e577` 라이브, 실 Windows Chrome 전용 프로필 + 자기 탭 한정) — **12/12 PASS**

배포 확인 선행: web-a·web-b·ask-worker·insight-worker **모두 `GIT_COMMIT=5000e577`**(종료코드가
아니라 서빙 주체의 실 SHA). 서빙 자산 census — `attach-list-item-actions` 2 · `_openAttachDeleteModal` 3 ·
헤더 액션 2 · 병렬 세션의 `openAttachmentDiffModal` 3(**두 기능 공존 확인**). 배포본 백엔드 —
audit 분기 2 · window clip 2 · `_manage_gate_for_conversation`/`_mirror_chain`/`_load_attachment_row_mysql` 반영.

**라이브 데이터 경계**: 자체 테스트 대화 1건 + 테스트 CSV 1개만 생성해 그것으로만 왕복하고
종료 시 대화를 삭제했다. 기존 사용자 대화·첨부 **무접촉**. §16.6 세션-격리 — `win-browser` 전용
프로필 위에서 **이 스크립트가 새로 연 탭만** 조작(탭 수 before=6 / after=6).

| # | 검증 | 결과 |
|---|---|---|
| S2 | 목록 `can_manage` 가 서버 술어로 내려옴(§16.7 G6) | `true` |
| S3 | ZIP 다운로드 | 182 bytes · PK 시그니처 · `X-Attachment-Count: 1` · `X-Attachment-Clipped: 0` · `Content-Length` 동봉 |
| S4 | manifest | `/api/attachments/890/download`(앱 내부 경로 — presigned 아님, TASK-0284) |
| S5 | `?scope=chian` 오타 | **400** — 기본값으로 조용히 격하되지 않음 |
| S6 | `scope=version` 삭제 | 200 · `deleted_count=1` · `promoted_id=null`(단일 버전이라 승격 대상 없음) |
| S7 | active 목록에서 제거 | n=0 |
| S8 | 휴지통 노출 + 남은 기간 | `restorable_until=2026-09-05T09:04:33`(retention 30일 정확) |
| S9 | 복구 | 200 · `restored_count=1` |
| S10 | active 재등장 | n=1 |
| S11 | 이미 활성인 것 재복구 | **409** |

#### Run 5 — **audit 행 생성 실측** (§18.8 security P1 회귀 잠금)

라이브 `agent_memory.WebAuditEvents` 40분 창 집계:

```
attachment.bulk_download   2
attachment.delete          1
attachment.restore         1
```

`ChangeJson` 표본 — 파괴 규모와 범위가 실제로 담긴다(종전 `attachment.delete` 는 전 필드 `null` 이었다):

```json
{"scope":"version","promoted_id":890,"restored_ids":[890],"restored_count":1,"conversation_id":"…"}
{"scope":"version","deleted_ids":[890],"promoted_id":null,"size_bucket":"<1KB","attachment_id":890,"delete_reason":"user","deleted_count":1,…}
{"scope":"all","format":"manifest","total_bytes":20,"packed_count":0,"clipped_count":0,"attachment_ids":[890],"requested_count":1,…}
```

builder 분기가 없으면 `ValueError` 를 `_audit_user_action` 이 삼켜 **행이 0** 이 된다 — 행이
실제로 생성됨을 값으로 확인했으므로 그 경로가 닫혔다.

#### 잔여 (미검증 — 정직 표기)

- **버전 체인 2개 이상**에서의 승격(AC-1)·`scope=chain`(AC-2)·체인 복구(⇤): 이번 e2e 는 단일
  버전 첨부라 `promoted_id=null` 경로만 탔다. 체인 시나리오는 pytest(`test_p1`/`p3`)가 params
  값으로 단정하나 **라이브 왕복은 미실측**.
- **공유창 window clip**(AR-2): bounded 멤버 계정이 필요해 미실측. 코드 배포는 census 확인.
- 삭제 직후 화면에서 목록이 pill 로 덮이지 않는지(§18.8 ux P1)는 **API 왕복으로만** 확인했고
  실 DOM 렌더는 미실측.

