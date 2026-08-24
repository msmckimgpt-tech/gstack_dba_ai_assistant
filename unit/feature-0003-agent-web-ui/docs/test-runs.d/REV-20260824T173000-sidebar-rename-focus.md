---
run_at: 2026-08-24T19:05:00+09:00
session: ai/claude/sidebar-rename-focus
scope: 인라인 이름 변경 오확정 봉인 + 대화 '이름 변경' 메뉴 — REQ-20260824T173000-sidebar-rename-focus
verdict: PASS (Environment: Windows-browser)
---

# Run — PB-0008 시각·인터랙션 검증 (Environment: Windows-browser)

- 브리지: `bin/win-browser.py doctor` → `relay @ http://172.26.144.1:9223`, Chrome/151.0.7922.170.
- 대상: **미머지 브랜치를 라이브 무접촉으로** 보기 위해 라이브 web 이미지(`mysql-ai-web:de940c70`)
  + 본 worktree 의 `src/static` **디렉터리** bind-mount 컨테이너(`web-verify-rename`,
  `https://localhost:18099`, 로그인 `bootstrap_admin`). 라이브 web-a/web-b 는 무접촉.
- 서빙본 확인: `/static/app/sidebar.js?v=dev` 에 신규 심볼 16 매치
  (`_buildInlineRenameInput`·`_inlineRenameDetaching`·`isSidebarRenaming`·`_commitConversationRename`),
  `/static/app.js?v=dev` 에 `make("이름 변경", { action: "conversation.rename" …})`,
  `/static/css/shell.css` 에 `.conv-inline-rename-input`·`.conv-item.is-renaming`.
- 계측기 자산화: `tests/pb0008_sidebar_rename_focus.py` (`--phase AB|C`).

## 판정 기준 — 화면이 아니라 **요청 유무**

"확정되지 않았다" 를 화면으로만 보면 거짓 통과가 쉽다(값이 남아 있어도 서버엔 이미 저장됐을 수
있다). `page.on("request")` 로 네트워크를 관측해 **`PATCH` 가 발사되지 않았음**을 정본 증거로 둔다.

## A. 편집 중 배경 재렌더가 확정을 만들지 않는다 (PASS)

폴더를 만들고(자동으로 인라인 편집 진입) 이름을 입력하는 도중, 억제할 수 없는 경로의 대표인
목록 전량 재구성(`renderConversationList()` — AI 응답 진행 중 상태 갱신과 같은 경로)을 **2회** 유발.

| 항목 | 값 |
|---|---|
| 편집 진입 | `key=folder:64`, value `새 폴더` 전체 선택(0–4), 포커스 O |
| 입력 중 상태 | value `검증중인 폴더이름`, 커서 4, 포커스 O |
| 재렌더 2회 직후 | value **`검증중인 폴더이름` 유지**, 커서 **4 유지**, 포커스 **O 유지**, `isConnected=1` |
| 그 사이 `PATCH` | **0건** (`A_patch_requests: []`) |

수정 전 코드였다면 이 지점에서 `PATCH /api/folders/64 {"name":"검증중인 폴더이름"}` 이 나가고
편집이 닫힌다(결함 주입 사본의 하네스 FAIL 로 동일 기전 실증 — TASK.md 참조).

## B. 편집 중 배경 동기화 억제 + 정상 확정 (PASS)

| 항목 | 값 |
|---|---|
| 편집 중 16초 관측 | `/api/conversations` 폴링 **0건** |
| 16초 후 편집 상태 | value·커서·포커스 그대로 |
| Enter 확정 | `PATCH /api/folders/{id}` **1건**, 목록에 `검증중인 폴더이름` 반영 |
| 확정 후 16초 | `/api/conversations` 폴링 **1건** — 편집 없는 기준선(16초 1건)과 동일 = 억제 해제 |
| 정리 | 검증이 만든 폴더 `DELETE` → 200 |

차단 로직이 정상 경로를 막지 않음을 같은 실행에서 확인했다(§16.7 G9-c).

## C. 대화 우클릭 → '이름 변경' → 인라인 편집 (PASS)

| 항목 | 값 |
|---|---|
| 우클릭 메뉴 항목 | `["이름 변경", "공유", "이동", "설정"]` — **첫 항목** |
| 선택 후 | 모달 `0`개(`.share-mgr-backdrop`), 그 행이 인라인 입력으로 전환 |
| 입력 상태 | `key=conv:20260807035225-9cb592cb`, 제목 전체 선택(0–17), 포커스 O |
| Enter 확정 | `PATCH /api/conversations/{cid}/title` 1건, 목록 제목 즉시 반영 |
| 원복 | 원 제목으로 `PATCH` → 200 |

캡처: `artifacts/pb0008-rename/C1-context-menu.png`(메뉴 4항목) ·
`C2-inline-edit.png`(행이 텍스트박스로 전환·전체 선택) · `C3-renamed.png`(확정 반영) ·
`A1-editing.png` · `A2-after-rerender.png` · `B1-committed.png`.

## D. 한글 IME 조합 중 확정 금지 (PASS — CDP `Input.imeSetComposition` 실측)

합성 키 입력으로는 IME 조합을 재현할 수 없어 CDP 로 실제 조합 상태를 만들었다.

| 항목 | 값 |
|---|---|
| 조합 중 상태 | value `프로젝`, `data-ime-composing="1"`, 포커스 O |
| 조합 중 Enter + 배경 재렌더 | `PATCH` **0건** |
| 이후 | 편집 유지(value `프로젝`, 포커스 O) — 잘린 이름이 저장되지 않는다 |
| 정리 | 임시 폴더 `DELETE` → 200 |

## D-2. 적대 리뷰 반영 후 재실측 (codex [P1] 1 · [P2] 3 흡수)

§18.8 codex 적대 리뷰가 위 A~D 통과 **이후에** 네 결함을 더 잡았고, 흡수한 뒤 양 경로를 다시
실측했다(아래 수치는 전부 수정본 기준).

| 검증 | 결과 |
|---|---|
| 조합 중 배경 재렌더 2회 | **입력 노드가 교체되지 않음**(`same_node: true`) · 값 `프로젝` · `ime=1` · 포커스 유지 · PATCH **0건** |
| 조합 종료 후 | 보류됐던 재구성이 1회 flush(`rebuilt: true`) · PATCH 누적 **0건** · 임시 폴더 `DELETE` 200 |
| 억제/해제 대조(창 16초) | 편집 중 `/api/conversations` **0건** → 확정 후 **1건**. 편집 없는 기준선도 16초에 1건이라 **해제가 기준선과 동일** |
| A·B·C 재실행 | 재렌더 후 값·커서(4)·포커스 유지 · PATCH 0 · 확정 PATCH 1 · 메뉴 4항목 · 모달 0 · 제목 원복 200 |

> ⚠️ 1차 실측에서 "편집 종료 후 9초 폴링 1건" 을 근거로 삼았는데, **편집 없는 기준선도 16초에
> 1건**이었다(주기 5s 루프 + 7s throttle 의 실효 간격). 9초 창은 억제/해제를 가르지 못하므로
> 창을 16초로 늘려 다시 쟀다 — 짧은 창의 "1건" 은 해제의 증거가 아니었다.

## E. 잔류물 (§16.6 (f))

- 검증이 만든 임시 폴더(id 64·65·90·91·92)는 모두 `DELETE` 200 으로 제거했다.
- 대화 1건(`20260807035225-9cb592cb`)의 제목을 변경했다가 **원 제목으로 원복**(200)했다(2회 — 리뷰 반영 전후).
  그 대화의 `updated_at` 은 두 번 갱신되어 목록 정렬상 상단으로 올라온다(내용 변경 없음).
- 검증 컨테이너 `web-verify-rename` 은 검증 종료 후 제거한다. 라이브 web-a/web-b·caddy 무접촉.

## F. 미수행 (사유 명시)

- **다중 사용자 동시 편집** 상황(다른 계정이 같은 폴더를 동시에 rename)은 재현하지 않았다 —
  서버 계약 변경이 없고 마지막 쓰기 우선(기존 동작)이 유지된다.
- **한글 조합 종료 시 값 유지**는 이 프로브로 못 봤다 — CDP 로 조합을 끝내며 텍스트를 비웠기
  때문에 flush 렌더가 빈 값을 capture 했다(프로브의 인위적 조건). 값·커서 복원은 비-IME 경로(A)로
  확인했다.
- **Firefox/Safari** 의 detach-blur 동작 차이는 확인하지 않았다. 봉인은 브라우저 동작에
  의존하지 않도록 설계했으나(플래그 + `isConnected` 2중), 실측은 Chromium 계열만이다.
