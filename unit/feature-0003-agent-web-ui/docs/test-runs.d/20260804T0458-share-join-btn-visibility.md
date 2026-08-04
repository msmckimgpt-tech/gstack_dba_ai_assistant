---
run_at: 2026-08-04T13:58:28+09:00
session: ai/root/feature-0003-agent-web-ui
scope: 공유 링크 화면 '대화에 참여' 버튼 노출 조건 확대 — 소유자·기존 멤버 포함 (Minor §12.3, 프론트 표시 + 응답 1필드)
verdict: PASS (PRE-LANDING + POST-DEPLOY PB-0008)
---

# Run 2026-08-04 — PRE-LANDING (라이브 진단 + 단위)

## 1. 라이브 진단 — 결함 재현 근거 (코드 변경 전)

사용자 리포트: "공유 링크 내부에서 '내 대화로 fork' 항목만 확인되고 그룹 대화 참여버튼이 나타나지 않는다."

| 축 | 실측값 | 판정 |
|---|---|---|
| 공유 링크 상태 | `WebConversationShares.Id=81` (2026-08-04 12:21 발급) · `Joinable=1` · `RevokedAt=NULL` · `ExpiresAt=NULL` | 링크는 **참여 허용 정상** |
| 로그인 열람자 | `WebAuditEvents` `share.public.view` — 12:23 `account_id=10` · 12:24 anonymous · 12:26 `account_id=10` | 로그인 열람자는 **1명** |
| 그 계정의 멤버십 | `agent_runtime.conversation_members`(cid `20260804013726-a6fe00cf`) → `account_id=10, role='owner'` 단일 행 | **소유자 본인** |
| 라이브 서빙 자산 | `web-a:/app/web/static/share.{html,js}` 에 `shareJoinBtn` 존재 · `GIT_COMMIT=03665d28` | 구버전 배포 가설 **배제** |

⇒ `share.py` `can_join = bool(viewer) and joinable and not already_member` = **false**(소유자라 `already_member=true`)
→ `share.js` 가 `can_join` **단독**으로 표시를 정해 버튼이 사유 없이 숨겨짐. `can_fork` 는 소유자 여부를
보지 않아(권한 `conversation.create` 만) fork 버튼만 남음 — 리포트 문구와 정확히 일치.

서버는 이미 `viewer.joinable`·`viewer.already_member` 를 응답에 담고 있었으나 프론트가 사용하지 않았다.

## 2. 적대 리뷰가 뒤집은 초안 설계 (P1)

초안: 표시만 넓히고 클릭은 그대로 `POST /api/share/{token}/join`.

`codex exec`(gpt-5.6-sol, xhigh) 가 P1 적발 → 정본 확인 결과 **사실**:

- `share.py` `join_conversation_via_share` 의 `elif _share_windowed:` 분기가 이미 멤버에게도
  `stamp_member_visibility(is_new_member=False)` 를 호출한다.
- `group_members.stamp_member_visibility` 는 `role='owner'` 와 기존 full 멤버(floor·ceiling 모두
  NULL)만 skip 하고, **기존 windowed 멤버는 교집합**(floor=더 높은 id, ceiling=더 낮은 id)으로 좁힌다.
  넓히는 경로가 없어 **복구 불가**.

⇒ 종전엔 `already_member` 면 버튼이 없어 UI 로 이 경로에 닿지 않았는데, 표시를 넓히면 **닿게 된다**.
설계 변경: 이미 멤버인 클릭은 join 을 호출하지 않고 `viewer.conversation_id`(멤버 한정 신규 필드)로
곧바로 이동한다. 서버 인가·window 로직은 무변경.

## 3. 단위 테스트 — **PASS**

**Environment: pytest (agent 이미지, 격리 compose 프로젝트 `repo-unittest` + `TEST_ISOLATION_ENV`)**

- `tests/test_share_join_btn_visibility.py` — **9 passed** (신규).
  - F1 `shouldShowJoin` = `is_authenticated && (can_join || joinable)` **정규식 고정**(AND 오변경 차단),
    `already_member` 미참조.
  - F2 `render()` 가 `shouldShowJoin` 사용 · `can_join` 단독 게이트 부재.
  - F3 `classList.toggle("hidden", !visible)` **극성 고정** + `dataset.shareWired === "1" ) return` 1회 부착 가드.
  - F4 `#shareJoinBtn` DOM·라벨('대화에 참여') 보존.
  - F5 **이미 멤버 클릭이 join 을 타지 않음** — `openJoinedConversation` 에 `fetch(`·`/join` 부재,
    `?conversation=` deep-link 사용, `doJoin` 의 join 경로는 비멤버용으로 보존(P1 회귀 차단).
  - F6 클릭 핸들러가 stale 클로저 대신 `_latestViewer` 스냅샷 참조.
  - B1 응답 계약(`joinable`/`already_member`/`can_join`) 유지 · B2 서버 인가 게이트 불변
    (`can_join` 계산식 · `Joinable=0 → 403`) · B3 `conversation_id` 는 `already_member` 한정.
- 회귀 스코프(`-k "share or fork or member or join"`) — **98 passed**, 실패 0.
- `node --check share.js` PASS · ruff PASS.
- 전체 스위트 참고: 동시 실행 시 `test_shutdown_finalizer.py::test_shutdown_finalizer_marks_this_process_processing`
  1건이 실패했으나 **단독 재실행 시 통과**하고 실패 로그가 `shutdown finalize: 시간 예산 초과` 를 동반해
  부하 의존 flake 로 판정 — 본 변경(정적 자산 + 응답 1필드)과 무관.

## 4. 경계 양측 (G4)

| 케이스 | 기대 | 근거 |
|---|---|---|
| 로그인 + joinable + 소유자/기존 멤버 | 버튼 **노출**, 클릭 = 대화 이동(join 0) | F1·F5 |
| 로그인 + joinable + 비멤버 | 버튼 노출, 클릭 = join(종전 동작) | F5 |
| 로그인 + `joinable=false` | 버튼 **미노출** | F1(joinable 조건 유지) |
| 비로그인 | 버튼 미노출, 로그인 링크만 | F1(`is_authenticated`) |
| 익명/비멤버 응답 | `viewer.conversation_id = None` | B3 |

## 5. PB-0008 — POST-DEPLOY **PASS** (2026-08-04, 배포 d23f0a0d)

**Environment: Windows-browser (PB-0008)** — PR #1134 머지 → `bin/deploy-web.sh --web-only` 배포
(web-a·web-b `GIT_COMMIT=d23f0a0d`, soak 90s 통과) 후 **실 Windows Chrome 150 relay** 로 실측.

**재현 케이스**: 사용자가 리포트한 상황과 동형인 *소유자 본인이 자기 joinable 공유 링크를 여는* 케이스로
검증했다 — share `Id=77`(`Joinable=1`, full scope, `CreatedBy=1`), 대화 `20260722015451-d23ad939`
(`owner_account_id=1`, 멤버=owner 1행·window NULL), 브라우저 로그인 계정 `bootstrap_admin`(id=1).
(사용자가 실제로 본 share `Id=81` 은 소유자가 `admin`(id=10) 이라 그 계정 자격이 없어 동형 대체.)

| 검증 항목 | 실측 | 판정 |
|---|---|---|
| ① 참여 버튼 가시 | `#shareJoinBtn` `is_visible=true` · text `"대화에 참여"` · title `"이미 참여 중인 대화입니다 — 대화로 이동합니다"` | **PASS** |
| ② 종전 조건 대조 | 배포본 응답 `can_join=false` · `already_member=true` · `joinable=true` · `conversation_id="20260722015451-d23ad939"` → **종전 코드면 숨겨졌을 조건에서 버튼이 보인다** | **PASS** |
| ③ 클릭 시 join 미호출 (P1) | Playwright request 캡처 `join_endpoint_calls=0` (`/api/share/*/join` 요청 **0건**) | **PASS** |
| ④ 클릭 시 대화 이동 | 요청 URL `https://localhost/?conversation=20260722015451-d23ad939` (`deeplink_hit=true`) → 로드 후 `app.js` 가 `replaceState` 로 URL 정리(`/`) · 메시지 로그 첫 항목 `"2026년 7월 22일"` = 목표 대화 | **PASS** |
| ⑤ 무회귀 | fork 버튼 가시 · 로그인 링크 hidden · 링크 복사 버튼 정상 | **PASS** |
| ⑥ 익명 뷰 계약 | 미로그인 응답 `viewer.conversation_id=null` · `joinable=true` (B3 라이브 실증) | **PASS** |

증거: `artifacts/pb0008/20260804-share-join-btn-owner.png` — 하단 액션 바에 **[링크 복사] [대화에 참여]
[내 계정에서 fork]** 3개가 나란히 렌더됨(육안 확인).

**검증 함정 기록 (재현자용)**: `bin/win-browser.py` 는 `ctx.pages[0]` 고정이라 사용자가 쓰는 다른 탭과
경합한다 — 실제로 클릭 후 eval 이 무관한 탭(`127.0.0.1:18099`)을 읽어 "cid 없이 `/` 로 이동" 이라는
**거짓 실패**를 한 차례 만들었다. CDP `/json/list` 로 탭 목록을 확인해 원인을 특정했고, 최종 검증은
`ctx.new_page()` 로 **전용 탭**을 열어 수행했다(사용자 탭 무접촉, 검증 후 close). 요청 캡처는
`page.on("request")` 로 `/join` 호출 유무를 직접 관측 — 서버 access log 는 캐시·워커 분산 때문에
음성 증거로 쓰기 부적절하다.
