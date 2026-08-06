---
run_at: 2026-08-07T04:30:00+09:00
session: ai/claude-corp/feature-0003-attach-diff-scroll-block
scope: unit/feature-0003-agent-web-ui/src/static (app/attach-diff.js · css/chat.css)
verdict: PASS (headless 실 브라우저) / PENDING (Windows-browser — 배포 후)
---

### Run (2026-08-07) — 상호작용 스크롤 보존 + 문단 단위 하이라이트

#### 1. 스크롤 보존 — **Environment: WSL-headless (chromium)**

> ⚠️ 이 축은 **실 브라우저만** 검증할 수 있다. innerHTML 교체 직후에는 scrollHeight 가 작아
> 브라우저가 scrollTop 을 0으로 clamp 하는데, jsdom 은 clamp 를 하지 않고 verbatim 저장하므로
> 결함을 통과시킨다(auto-memory `project-frontend-scroll-restore-jsdom-gotcha`).

| # | 상호작용 | 결과 |
|---|---|---|
| 전제 | 스크롤 중간(50%)까지 내려감 | PASS `top=487 / lno=27 / max=974` |
| S1 | 2열 → 단일열 | PASS `487 → 486` · 줄 27 유지 |
| S2 | 단일열 → 2열 복귀 | PASS `486 → 485` · 줄 27 유지 |
| S3 | "동일한 줄도 모두 보기" | PASS `485 → 484` |
| S4 | "N줄 생략" 펼치기 | PASS `584 → 583` · 줄 32 유지 |
| S5 | **버전 쌍 변경 → 최상단**(의도된 비대칭) | PASS `top=0` |
| S6 | 비대칭 비율(0.22)에서 2열↔단일열 왕복 | PASS `줄 31 → 32` (±3 이내) |

#### 2. 문단(블록) 하이라이트 — **Environment: WSL-headless (chromium)**

| # | 항목 | 결과 |
|---|---|---|
| B1 | 연속 변경 3행이 한 블록 | PASS `inBlock=3 · blockIds=[1] · multi=3` |
| B2 | 블록 시작·끝 각 1행 | PASS |
| B3 | equal 행은 블록 미포함 | PASS `0` |
| B4 | 여러 줄 블록 시작 행에 경계선 | PASS `1px` |
| B5 | accent 는 내용 있는 쪽에만 | PASS `좌 inset danger / 우 none` |
| B6 | accent 실제 렌더 | PASS `rgba(220,38,38,0.4) 3px inset` |
| B7 | 단일열도 같은 블록 1개(replace 2행 전개 반영) | PASS `inBlock=5 start=1 end=1` |
| B8 | **delete 행 빈 우측 셀 = 중립 filler**(선행 결함 교정) | PASS `rgb(240,239,234)` |
| B8b | 내용 있는 좌측 셀은 danger 유지 | PASS `rgba(220,38,38,0.12)` |

전체 **44/44 PASS**. mjs `verify_attach_version_diff.mjs` **84 PASS**(A1c 구조 가드 11건 신설) ·
전수 mjs **44 suite OK**.

#### 3. 뮤테이션 역검증 — 3/4 (정직 표기)

| 뮤테이션 | 결과 |
|---|---|
| `rerender` 기본 keepScroll → false | **red** S2 · S2b · S3 · S4 · S4b |
| `_assignBlocks` 무력화 | **red** B1 · B2 · B4 |
| 빈 셀에도 accent 부여 | **red** B5 |
| **rAF 제거(즉시 복원)** | **생존 — 하네스가 구별 못함** |

마지막 항목은 방어적 조치이며 현재 호출 지점에서 필수가 아니다(`offsetTop` 이 동기 레이아웃을
강제). 비대칭 비율 케이스(S6)를 추가해 재시도했으나 여전히 구별하지 못했다. "테스트가 있으니
검증됨" 으로 쓰지 않고 근거를 코드 주석에 남겼다.

#### 4. 리베이스로 생긴 접합부 — soft-delete × 비교 선택기 (신규 2축)

작업 도중 `REQ-20260806-attach-manage`(PR #1173, 첨부 삭제·복구)가 먼저 랜딩해 리베이스했다.
코드 충돌은 자동 병합됐지만(`chat.css`·`attach-diff.js`) **데이터 모델에 새 상태**(soft-delete)가
생겼으므로 내 버전 체인 로더가 그 상태를 어떻게 보는지 실측했다.

- 삭제 write 3경로 모두 `DeletePending = 1` 과 `DeletedAt` 을 **같은 statement 에서** 세운다
  (`attachments.py` user / `attachment_reconciliation.py` conv_soft / `conversations.py`).
- 체인 조회 **양쪽** 이 `deleted_at IS NULL` 을 건다 — MySQL 폴백(V1 기존) + **PG 미러**(V3 신설).
- ⇒ 삭제한 버전은 비교 선택기에 나타나지 않는다. **읽어서 확인한 것을 테스트로 고정했다** —
  다음 변경에서 조용히 깨지는 부류다(에러 없이 삭제한 버전이 선택기에 되살아난다).

| 축 | 단정 | 뮤테이션 |
|---|---|---|
| V3 | PG 미러 버전 조회가 soft-delete 를 제외 | 필터 제거 → **red** `AssertionError: PG 미러 버전 조회에 soft-delete 필터가 없다` |
| V3b | `DeletePending=1` write 가 항상 `DeletedAt` 동반 (체인 로더의 단일 필터가 충분한 근거) | user 경로에서 `DeletedAt` 제거 → **red** |

`test_attachment_version_diff.py` **26 PASS**(24 + 신규 2). 베이스라인 통과 + 뮤테이션 양측 red
확인 후 소스 원복(`git status src/` = 0).

**비대칭은 의도적**: 목록 엔드포인트는 `DeletedAt IS NULL AND DeletePending = 0 AND SupersededAt
IS NULL` 삼중 필터, 체인 로더는 `DeletedAt IS NULL` 단일 — 체인은 구버전(`SupersededAt` 세팅됨)을
**포함해야** 비교가 성립한다. V3b 가 그 단순화의 근거를 지킨다.

#### 4b. 버전 행 액션 3버튼 공존 실측 — `verify_attach_version_row_actions.py` (신규)

`⇄`(내 비교, REQ-attach-version-diff)와 `🗑`(#1173 삭제, REQ-attach-manage)가 **서로 모르고
병렬 개발되어** 같은 `.attach-list-version-actions` 를 공유하게 됐다. git 은 텍스트상 깔끔히
병합했지만 **버튼이 2개→3개로 늘어난 결과가 화면에서 성립하는지는 아무도 재지 않았다**.
버전 박스는 첨부 패널 안에서 좌측 28px 들여쓰기까지 먹는 좁은 영역이다.

| 폭 | acts 폭 | foot 경계 | 버튼 | 이름 잘림 |
|---|---|---|---|---|
| 240px | 60 @131..191 | →191 | `⇄`17×17 `⬇`17×17 `🗑`22×15 | 긴명 O |
| 280px | 60 @171..231 | →231 | 동일 | 긴명 O |
| 320px | 60 @251..311 | →311 | 동일 | 긴명 O |
| 360px | 60 @291..351 | →351 | 동일 | 짧은·긴명 X |
| 420px | 60 @351..411 | →411 | 동일 | X |

**A1~A5 전부 통과** (10 조합 = 폭 5종 × 이름 2종): 3버튼 공존 · 액션 영역 넘침 0 ·
foot overflow 0 · 페이지 가로 스크롤 0 · 긴 이름이 버튼을 밀어내지 않음(액션 폭 60px 불변,
이름만 ellipsis). **제 `⇄` 어포던스가 병합 후에도 살아 있다.**

뮤테이션 역검증: 버튼 `min-width: 64px` 강제 → **A2·A3 red**(240px 에서 `foot 밖으로 114px
넘침`, 320px 에서 34px). 가드가 load-bearing 임을 확인.

**W1 관측(WARN, 이 cycle 범위 밖)**: 세 버튼 모두 WCAG 2.2 AA 최소 타겟(24×24) 미달 —
`⇄`17×17 · `⬇`17×17 · `🗑`22×15. **병합이 만든 것이 아니라 세 버튼의 선행 상태**다. 고치면
방금 랜딩한 `attach-manage` 의 버튼 외형까지 함께 바꾸므로 사용자 판단 대상으로 남기고
수치만 제공한다. (내 첫 측정 기준 16px 은 임의값이었다 — 실제 기준은 24px 이다.)

#### 5. **Environment: Windows-browser** — 배포 후 재검증 잔여

스크롤 4종 + 블록 하이라이트 시각 판독 + 선행 47축 회귀. 리베이스로 첨부 패널에 삭제·복구·
일괄 다운로드 컨트롤이 추가됐으므로 **`⇄ 버전 비교` 어포던스가 그 옆에서 살아 있는지**도 함께
판독한다(자동 병합이 텍스트상 성공해도 같은 헤더에 버튼이 늘면 배치가 깨질 수 있다).
