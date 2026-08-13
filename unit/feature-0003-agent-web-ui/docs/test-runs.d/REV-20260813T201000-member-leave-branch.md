---
run_at: 2026-08-13T20:10:00+09:00
session: member-leave-branch (ai/claude/feature-0003-member-leave-branch)
scope: '대화 설정' 팝업 보관/나가기 분기를 사실 기반 판정으로 복원(멤버 나가기 경로 부재 해소) + 선행 member-scope-gates 감사 결론 정정 + 거짓 PASS 구조 단언 정정
verdict: PASS (pre-commit — 실 DOM jsdom 22 + 수정 전 6건 FAIL 재현 + 정정 테스트 23 + 프론트 .mjs 62개 전수 회귀 0 / 서버 거부는 라이브 실측) / 나가기 end-to-end = POST-DEPLOY
---

### Run (2026-08-13) — member-leave-branch pre-commit — **Environment: CLI (node 18 + jsdom@22) + 라이브 서버 응답 실측**

**발단 — 라이브에서 선행 cycle 의 전제가 깨졌다 (Environment: Windows-browser, 배포 `fa99ed69`)**

멤버 계정(`dqa_memtest`, operator, admin 대화의 공유 멤버)으로 '대화 설정' 팝업을 열자
`dangerBtn.textContent === "보관"` · 팝업 내 '나가기' 문구 **부재** · 제목 입력 **활성**이었다.
이는 선행 cycle 이 가정한 "멤버는 게이트에 막힌다" 와 반대이며, `can()` 정의를 확인해 원인을 찾았다:
`void permission; return Boolean(state.user)` — **인자를 버린다**(TASK-0098 display-permissive).
같은 계정으로 서버를 직접 호출해 경계 양측을 확정했다:

- `POST /api/delete_conversations` → `{"failed":[{"conversation_id":"…","reason":"forbidden"}]}` (보관 안 됨)
- `PATCH /api/conversations/{cid}/title` → **403** `"소유자만 대화 제목을 변경할 수 있습니다."`

→ 프론트가 내민 '보관' 버튼은 **항상 거부**되고, 서버가 허용하는 **self-leave 진입점은 UI 에 없다**.

**신규 `tests/verify_member_leave_branch.mjs` — 22 passed / 0 failed (실 DOM 렌더)**

- `[case1]` 소유자 → danger 버튼 `"보관"` + 클릭 시 `deleteConversation(cid)` 호출.
- `[case2]` ★ **비소유 그룹 멤버 → `"나가기"`** + 안내 "이 그룹 대화에서 나갑니다" + 클릭 시
  `leaveConversation(cid)` 호출 + **서버가 forbidden 하는 archive 는 미호출**.
- `[case3]` 관리자(`console_access:true`) → `"보관"` 유지(`.any` 경로 보존).
- `[case4]` '대화 관리' 섹션 렌더.
- `[case5]` 멤버 제목 입력은 **활성**(display-permissive 컨벤션 — 집행은 서버 403). 현 동작을 고정해
  per-code `can()` 도입 시 FAIL 로 함께 재검토되게 한다.
- `[전제]` 정본 `can()` 이 인자를 무시함을 테스트가 직접 단언 — 이 전제가 바뀌면 FAIL.
- `[구조]` 4건 — `canArchive` 가 `isOwnConversation ‖ canOpenAdminConsole()` 인지 ·
  `canDeleteConversation`(항상 true) 미사용 · 두 분기 존재 · 나가기가 `leaveConversation` 호출.
  **주석 제외 코드 라인만** 검사(주석의 구 코드 인용이 거짓 PASS 를 만드는 것을 이번에 2회 관측).
- **수정 전 재현**: 같은 하네스로 `HEAD:app.js` 평가 → `[case2]` **6건 FAIL**(멤버가 '보관' 을 받고
  클릭 시 archive 호출) + 구조 2건 FAIL. 수정 후 22 PASS.

**기존 테스트 거짓 PASS 정정 — `verify_settings_archive_leave.mjs` (23 passed)**

구 단언 `settingsFn.includes("canDeleteConversation(conversation)")` 는 "그 함수를 쓴다" 만 잠갔다.
함수가 상수 true 라 분기가 죽는다는 사실은 문자열로 볼 수 없어 **결함을 통과시켰다**. 판정을 새 기준
(`canArchive = isOwnConversation ‖ canOpenAdminConsole()`)으로 바꾸고 모든 구조 단언을 주석 제외
코드 라인(`settingsCode`) 기준으로 전환했다.

**`verify_member_scope_gates.mjs` 정정 (53 passed)**: per-code `can` 주입은 현 런타임의 blocked 동작
증거가 아니라 **후보 권한 집합의 "미래 계약" 잠금**임을 헤더·라벨에 명시. 케이스에서 ★(실효 표시)를
제거하고 "가정: per-code can" 을 붙였다.

**프론트 `.mjs` 전수 회귀**: 62개 전부 exit 0 / FAIL 0.

**학습 기록**: `docs/LEARNINGS.md` `LRN-20260813-display-permissive-can-invalidates-gate-audit` —
① 게이트 감사는 판정 함수 정의부터 ② display-permissive 는 표시에만, 분기엔 사실 기반 ③ 구조 단언은
"어떤 함수를 호출한다" 가 아니라 행위를 잠글 것 ④ 주석 제외 검사 ⑤ "확정" 전에 라이브 1-probe.

**Environment: Windows-browser — 나가기 end-to-end 는 POST-DEPLOY**: 정적 자산 baked. 위 발단
실측은 **배포된 구 코드**에서 결함을 확인한 것이고, 수정본의 '나가기' 버튼 노출·클릭 후 실제 이탈은
배포 후 검증한다.

**Pass/Fail: pre-commit PASS · 나가기 end-to-end = POST-DEPLOY**. CHECK#13 충족.

### POST-DEPLOY 검증 항목 (append 예정 — Environment: Windows-browser)

1. 멤버 계정 `···` > 설정 → '대화 관리' 섹션에 **'나가기'** 버튼(안내 "이 그룹 대화에서 나갑니다").
2. 클릭 → 확인 다이얼로그 → self-leave 수행 → 그 대화가 목록에서 사라짐.
3. 소유자 계정에서는 같은 팝업이 '보관' 을 유지.
4. `pageerror` 0.
