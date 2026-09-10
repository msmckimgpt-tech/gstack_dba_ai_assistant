---
review_id: REV-20260910T064200-folder-newconv
feature_id: feature-0003-agent-web-ui
related_task: feature-0024-conversation-folders / TASK-20260910T064200-folder-newconv
agents: [ux, design]
timestamp: 2026-09-10T06:42:00Z
verdict: PASS (P1 3건 전건 in-cycle 수정 + 확인 라운드 통과)
---

# 검증 패널 — 폴더 행 '···' → '📝'(이 폴더에서 새 대화) 대체

## 1. Dispatch 근거

- **Trigger**: `UI/button/layout` + `버튼/화면/레이아웃` keyword matched (§18.8 dispatch 표 3행 → `ux`, `design`).
- **채널**: `Agent` tool 로 두 도메인 적대 리뷰어를 **병렬** 호출(`general-purpose` 에 도메인 역할·점검 축·by-design 입력을 명시). 이 저장소 `.claude/agents/` 에는 `improve-fit-reviewer` 만 있어 ux/design 전용 정의 파일이 없다.
- **리뷰 입력에 실은 by-design**(§18.8 「의도된 구성은 리뷰 입력에 넣는다」): ①폴더는 계정별 개인 오버레이(`feature-0024 ANCHOR.md`) ②새 대화는 lazy-create(TASK-0048) ③트리거가 hover 에만 드러나는 것은 대화 행 '···' 과 같은 기존 규칙 ④사용자 결정 2건(메뉴는 제거가 아니라 우클릭 이관 · 표시는 노트·펜 이모지).

## 2. 발견 및 처리

### P1 — 전건 in-cycle 수정

| # | 발견 (제기: agent) | 처리 |
|---|---|---|
| P1-1 | **메뉴가 폴더 헤더의 `aria-expanded` 를 강탈**한다 (design P1 / ux P2 — 두 리뷰 독립 적발). `openFloatingMenu` 는 트리거에 `is-open`+`aria-expanded="true"` 를 기입하는데, 이제 트리거가 **헤더 자신**이고 헤더의 `aria-expanded` 는 이미 «폴더 접힘/펼침» 의 정본이다. 게다가 `closeFloatingMenus` 의 복구 셀렉터는 이번 변경이 **삭제한** `.conv-folder-menu-trigger` 를 가리켜 복구되지 않는다 → 접힌 폴더가 보조기술에 "펼쳐짐" 으로 박제. ux 가 실 probe 로 재현(`메뉴 닫은 뒤: is-collapsed + aria-expanded=true`). | `openFloatingMenu` 에 `ownsAriaExpanded` 옵션 신설 — `false` 면 ARIA 를 건드리지 않고 `.is-menu-open` 클래스만 쓴다. `closeFloatingMenus` 는 `.is-open`(aria 복원) 과 `.is-menu-open`(클래스만 제거) 두 갈래로 분리. `openFolderMenu` 가 `ownsAriaExpanded:false` 로 연다. **회귀 가드**: `verify_folder_newconv_trigger.mjs` case3a (접힘 폴더 우클릭 → 열림·닫힘 전 구간 `aria-expanded` 불변 + `.is-menu-open` 부착·해제). |
| P1-2 | **발견성** — 폴더 관리 4기능(이름 변경·하위 폴더 추가·최상위로 꺼내기·설정·삭제)의 진입점이 «화면 단서 0» 인 우클릭 하나가 됐다 (ux P1 / design P1). 같은 자리·같은 hover 로 나타나는 버튼의 동작만 «메뉴» → «대화 생성» 으로 바뀌어 기존 근육 기억이 오작동한다. | 사용자 결정 ①(우클릭 이관)은 유지하되 단서를 세 겹으로 보강: ⓐ 헤더 `title="클릭: 펼치기·접기 · 우클릭: 폴더 메뉴"` ⓑ 헤더 `aria-haspopup="menu"` ⓒ **우클릭 메뉴에 「이 폴더에서 새 대화」 항목 추가**(hover 가 없는 터치·키보드에는 이 항목이 '새 대화' 의 유일한 경로). 자리는 ctxmenu-order-parity 규칙(첫=이름 변경 / 끝=설정) 안의 고유 액션 구간. |
| P1-3 | (design P1-2 의 부수) 오클릭 시 `beginPendingConversation` 이 컨텍스트를 갈아엎고 **접힘 선호를 영속 삭제**한다. | `_saveCollapsedGroups()` 호출 제거 — 이번 화면에서만 펼치고 localStorage 의 사용자 선호는 건드리지 않는다. 입력창에 작성 중 텍스트가 있을 때만 전환 토스트로 알린다(빈 입력창에는 소음이 되므로 조건부). |

### P2 — 수정한 것

- **pending 행이 하위 폴더 서브트리 «전체 뒤»에 그려진다** (양 리뷰 공통, ux 가 실측: 하위 2 + 대화 10 구성에서 헤더로부터 12행 아래 ≈ 화면 밖). 내 주석은 "폴더 안 최상단" 이라 적었는데 코드는 재귀를 먼저 돌고 있었다 → pending append 를 재귀 **앞**으로 이동 + `startFolderConversation` 에서 `scrollIntoView({block:"nearest"})`. 가드: case4d.
- **히트 타겟 축소** — 구 `···` 13×13 → 신 `📝` 실효 17×11 로 **세로가 줄었다**. 같은 사이드바의 대화 '···' 은 22×22 를 명시 확보하는데 정반대 방향이고, 이 버튼은 «메뉴 열기»(빗맞아도 무해)가 아니라 «대화 컨텍스트 생성»(빗맞으면 폴더가 접힘)이라 책임이 더 무겁다 → `20×20 inline-flex` + `margin:-3px 0`(행 높이 불변) + hover 배경.
- **폴더 대상이라는 사실이 헤더에 없다** — pending 헤더가 최상위 '+ 새 대화' 와 글자 하나 다르지 않았다 → 부제를 `'<폴더명>' 폴더에 만들어집니다. 첫 메시지를 입력하세요.` 로 분기.
- **열린 메뉴의 대상 폴더가 화면에서 사라진다** — 커서가 메뉴로 옮겨가면 헤더 `:hover` 배경도 사라져, 유사한 이름의 폴더들 사이에서 대상 신호가 0 → `.conv-folder-header.is-menu-open` 배경 + 좌측 accent 바.
- **터치·비-hover 도달 불가** — 681~900px 구간은 사이드바를 보여 주지만 hover 가 없다 → `@media (hover:none),(pointer:coarse)` 상시 노출 + `:focus-within` + 위 메뉴 항목 폴백.
- **이모지 폰트 폴백** — 본문 `--font` 스택에 이모지 패밀리가 하나도 없어 글리프 해결이 플랫폼에 맡겨진다 → 트리거에만 `"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji"` 명시.
- **첨부 선행 경로만 라이브 state 를 읽는다** — `sendPrompt` 는 `sendFolderId` 로 진입 시점에 고정하는데 첨부 경로는 `/api/new_conversation` 왕복 **뒤** `state.pendingFolderId` 를 읽어, 그 사이 다른 폴더의 '📝' 를 누르면 엉뚱한 폴더로 배정된다 → `uploadFolderId` 지역 고정으로 두 경로의 계약 일치.
- **aria-label 폴더명 중복** — 헤더 accessible name 이 콘텐츠 기반이라 자손 `aria-label` 이 편입돼 "폴더A 1 '폴더A' 폴더에서 새 대화" 로 읽힌다 → `"새 대화 시작"` 으로 축약(lazy-create 라 '시작' 이 실제 동작에 더 가깝다).
- **pending 행의 32px 우측 여백** — `.conv-item` 이 '···' 자리를 예약하는데 pending 행에는 그 트리거가 없다. 들여쓰기까지 겹치면 제목 가용폭이 180px 사이드바·depth 2 에서 ≈84px(한글 6자) → pending 행만 `padding-right:8px`.
- **문서 미동기** — `docs/FUNCTION.md` 가 `_CTX_MENU_TARGETS` 3행과 `.conv-folder-menu-trigger` 를 현행으로 기술하고 있었다 → 현행화(`MODIFY.md` 는 append-only 이력이라 과거 엔트리는 보존).

### 기각 — 근거를 함께 남긴다

- **「`📝` 대신 `＋` SVG 로 바꾸라」(design P2, 아이콘 어휘 일관성)**: 사용자가 2026-09-10 AskUserQuestion 에서 **노트·펜 이모지를 명시 선택**하고 아이콘 예시 이미지까지 제시했다. 어휘 불일치 지적은 타당하나 사용자 결정이 우선한다. 이모지를 유지하면서 해소 가능한 축(히트 타겟·색 제어·폰트 폴백)은 위에서 전부 처리했다.
- **「`📝` 옆에 `···` 를 남겨 두 버튼 공존」(ux P1 제안 / design P1 제안)**: 그 선택지는 AskUserQuestion 의 3번 항목("'···' 는 새 대화, 메뉴는 별도 버튼 신설")으로 제시됐고 사용자가 **고르지 않았다**. 대신 위 ⓐⓑⓒ 로 발견성을 보강했다.
- **「`conversation.create` 미보유 + `folder.manage.own` 보유 계정은 폴더 행에 버튼이 0개」(ux P3)**: 그 조합은 실질적으로 발생하지 않는다 — `TASK-20260723T180000-folder-perms-broaden` 이 `conversation.create` **보유 역할에** folder 권한을 부여했으므로 folder 권한 보유는 create 보유의 부분집합이다. folder 권한이 없으면 폴더 자체가 렌더되지 않는다. 그럼에도 우클릭 + 헤더 title 로 메뉴에 도달할 수 있다.

### 후속 등재 (선행 결함 — 본 변경 범위 밖, `docs/REPORT.md` §후속)

- `openFloatingMenu` 의 **키보드 메뉴 내비게이션 부재**(첫 항목 포커스·roving tabindex·Tab 트랩 없음, capture `scroll` 이 탭 이동 중 메뉴를 닫음). ux 가 probe 로 확인했고 종전 '···' 경로도 동일했던 **선행 결함**이다. 다만 이번 변경으로 «보이지 않고 + 닿지 않는» 조합이 되므로 우선순위가 올랐다.
- `--text-1` 토큰이 **정의되지 않은 채 8곳에서 사용**된다(design P3, 정의 0건). 구 hover 대비는 invalid-at-computed-value → `inherit` 으로 우연히 작동하던 것이다.
- `forced-colors: active`(Windows 고대비) 규칙이 CSS 전체에 0건.
- `🗂`(U+1F5C2, VS16 없음)은 텍스트 프레젠테이션이 기본이라 Windows 에서 흑백으로, `📝` 는 컬러로 해결되어 한 행에 두 스타일이 섞일 수 있다(design P2). 기존 요소를 바꾸는 축이라 별도 등재.

## 3. 반증 — 결함이 아니라고 판정된 축 (정직 기록)

- **들여쓰기 정렬**(design 축 5): 브리프가 어긋남을 의심했으나 호출부가 `depth+1` 을 넘기므로 pending 행과 일반 대화 행의 `paddingLeft` 가 **모든 depth 에서 동일**(0/1/2/3 → 22/36/50/64px). 제목 시작 x 도 `+12px` 로 일치. Δ = 0.
- **행 높이·수직 정렬**(design 축 1): 행 높이는 `.conv-folder-name`(~16px)이 정하고 트리거는 `line-height:1` 로 박스가 잘리므로 13px→11px 변경의 행 높이 Δ = 0px. 잉크 중심은 오히려 1.7px 개선.
- **폭 압박**(design 축 3): 트리거 폭 Δ ≈ +4px → 252px 사이드바에서 이름 가용 151.7 → 147.7px(한글 0.4자). 무시 가능.
- **다중 pending 경합**(ux 가 적대적으로 의심): "폴더 F 전송 중 폴더 G 의 📝 클릭 → F 의 응답이 G 의 목표를 지운다" 를 검토했으나, 두 `pendingFolderId = null` 대입이 모두 `if (state.pendingSentinel === busyKey)` 가드 **안**에 있어 두 번째 컨텍스트로 이동한 경우 실행되지 않는다. 누출 없음.
- **우클릭이 새 대화를 발화**: `_CTX_MENU_TARGETS` 에서 폴더 헤더 제외 + 헤더 직접 배선 + `stopPropagation` 조합이 정확하다.
- **pending 이중 렌더 / 삭제된 폴더 유실**: `_pendingFolderRef` 정규화로 배타 분배 + 최상위 폴백 성립.

## 4. 하네스 사각지대 — 리뷰가 잡아낸 자기-검증 결함

ux 리뷰가 지적: 신규 하네스의 `openFloatingMenu` **stub 이 정본의 `is-open`/`aria-expanded` 기입을 재현하지 않아** P1-1 회귀에 구조적으로 눈이 멀어 있었다. 58건이 전부 초록인 채로 접근성 회귀를 통과시키고 있었다는 뜻이다.

→ stub 을 폐기하고 `openFloatingMenu`·`closeFloatingMenus`·`makeMenuItem` **정본을 realm 에 주입**하도록 하네스를 재작성했다. 메뉴 관찰도 내부 배열이 아니라 실제 DOM(`#folderMenu`)으로 바꿨다. 결과 58 → **77건**, 신규 가드 5종의 판별력을 뮤턴트로 확인(M8~M12 전부 KILL, 누적 12종).

## 5. 수렴 (§18.8 패널 수렴 계약)

- 라운드 1: ux P1 1건 + design P1 2건(중복 1건 = `aria-expanded` 강탈) → **고유 P1 3건**.
- 전건 in-cycle 수정 + **확인 라운드**: 수정 후 `verify_folder_newconv_trigger.mjs` 77 PASS / 0 FAIL, 뮤턴트 12종 KILL, 프론트 `.mjs` 전수에서 baseline 대비 신규 실패 0. 수정이 새 결함을 만들지 않았음을 같은 게이트로 확인했다.
- **마지막 라운드 P1 = 0** → 종결 조건 충족.

- **Human Approval Needed**: no (§12 승인 항목 없음 — 인증·인가·개인정보·파괴적 데이터·마이그레이션 무관, 백엔드·스키마·권한·엔드포인트 변경 0).
