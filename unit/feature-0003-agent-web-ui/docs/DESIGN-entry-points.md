---
doc_type: DESIGN
feature_id: feature-0003-agent-web-ui
scope: feature
status: active
edit_policy: rewrite
source_of_truth: true
title: DESIGN.md — 진입점 복구 컴포넌트 (TASK-0158)
---

# DESIGN.md — 진입점 복구 컴포넌트

> design.md (getdesign.md / Stitch spec) 9섹션 형식. "구현됐으나 진입점 없는 기능"의
> 신규 UI 진입점을 기존 디자인 시스템에 정합하게 추가하기 위한 설계 정본.
> 시각 토큰은 `static/styles.css :root` 의 기존 값을 **그대로 재사용**한다 (신규 색/폰트 도입 금지).

## 1. Visual Theme & Atmosphere

- 분위기: warm canvas, 저밀도, 차분(Cursor DS 참조). 신규 진입점은 **눈에 띄되 시끄럽지 않게** —
  기존 컨트롤 옆에 자연스럽게 얹히고, 새 화면/패널을 최소화한다.
- 원칙: "기능은 이미 있다 — 길만 낸다." 신규 컴포넌트는 기존 패턴(toast, ··· 메뉴, drawer 탭,
  admin pane)을 **복제**하며 새 시각 언어를 만들지 않는다.
- 파괴적 동작(audit.purge, share revoke)은 위험색 + 확인 단계로 **의도적 마찰**을 둔다.

## 2. Color Palette & Roles (기존 토큰 재사용)

| 역할 | 토큰 | 값 | 용도 |
|---|---|---|---|
| 기본 액션 | `--primary` / `--primary-dark` | #2563eb / #1d4ed8 | 전송, 확인(positive), 링크 |
| 위험/파괴 | `--danger` / `--danger-soft` | #dc2626 / #fef2f2 | 중단·revoke·purge 버튼, 경고 배너 |
| 성공/정상 | `--success` | #16a34a | grant drift "정상", 완료 토스트 |
| 경고 | `--warning` | #d97706 | drift 감지, 보존기간 경고 |
| 표면/경계 | `--surface` `--border` `--border-subtle` | #fff #e6e5e0 #f0efea | 모달·카드·패널 |
| 텍스트 | `--text` `--text-2` `--text-muted` | #26251e #5a5852 #807d72 | 본문/보조/메타 |

규칙: 파괴 동작은 **항상 `--danger`**, 보완/조회 동작은 secondary(중립). 새 hex 추가 금지(중단버튼 hover `#b91c1c` 만 기존 선례 답습).

## 3. Typography Rules (기존 `--font`/`--mono`)

- 모든 UI 텍스트 `--font`(Geist/Noto Sans KR). 코드·SQL·토큰값만 `--mono`(D2Coding).
- 위계: 모달 제목 15px/600, 본문 13px/400, 메타·타임스탬프 12px/`--text-muted`, 버튼 13px/500.
- 감사 로그 리스트의 action_code/resource_id 등 식별자는 `--mono`.

## 4. Component Stylings (신규 컴포넌트 + 상태)

### 4.1 즉시 답변 버튼 (`#finalizeBtn` 재배치 → composer)
- 위치: `.composer-box` 내 `#sendBtn` **좌측**, 처리 중에만 표시(`isCurrentConvBusy()`).
- 형태: 텍스트 pill 버튼 "즉시 답변", 높이 34px 정렬(send-btn 과 baseline 일치), `--r-sm`.
- 색: 중립 secondary(배경 `--surface`, 경계 `--border`, 텍스트 `--text-2`); hover 시 `--primary-soft`.
- 상태: 비처리=`display:none`. 처리중+권한O=노출. 처리중+권한X=`is-access-blocked`(흐림 .55 + aria-disabled + 권한 tooltip, 클릭은 통과→토스트). [[중단버튼 TASK-0157 패턴 동형]]

### 4.2 공유 링크 관리 모달
- 진입: 대화 ··· 메뉴(`makeItem`)에 "공유 관리" 항목(`conversation.read.own/any` gate).
- 모달: `.share-mgr-backdrop` / `.share-mgr-panel` CSS-클래스 패턴 복제(예: `showTotpLoginPrompt`) — backdrop(fixed inset0, z 9999, rgba(0,0,0,.4)) + panel(`--surface`, `--r-lg`, `--shadow-lg`, max-width 560px, padding 20px). (구 `showTimeoutRecoveryDialog` 인라인-스타일 참조는 ask-timeout-nonblocking 2026-07-09 에서 함수와 함께 제거됨.)
- 리스트 행: 토큰(앞 8자, `--mono`) · scope 배지(full/anchored) · 생성일 · 조회수 · 상태(활성=`--success` 점 / 취소=`--text-muted` 취소선) · [열기] [링크 복사] [취소(revoke, `--danger`)].
- 빈 상태: "발급된 공유 링크가 없습니다." (`--text-muted`, 중앙).
- revoke: 행 단위 `window.confirm` 후 `DELETE /api/share/{id}` → 행을 "취소됨"으로 갱신(낙관적). 실패 시 토스트.

### 4.3 첨부 참조 범위 안내 (구 scopeAll 체크박스 — 2026-07-29 제거)
- **제거됨**: "이 대화의 모든 첨부 사용" 체크박스(`#composerAttachmentsScopeAll`)는
  `ADR-20260729T140200-attach-full-scope` 로 삭제됐다. 참조 범위가 서버에서 대화 전체로
  해소되어(D16 supersede) 켜고 끌 구분이 사라졌고, 전송하던 `attachment_scope_all` 필드는
  애초에 백엔드에서 읽힌 적이 없어 실질 no-op 이었다.
- **대체**: 같은 자리(`#attachSidePanel` 헤더 아래)에 안내 1줄 `.attach-side-panel-note`
  ("AI 는 이 대화에 올린 파일 전체를 참고합니다. 첨부는 대화에 계속 쌓입니다.")
  — 11px `--text-muted` + `border-bottom`. 첨부 0건이면 숨김.
- **첨부 목록은 append-only** (2026-07-29 사용자 지시, `ADR-20260729T163000-attach-append-only`):
  서버에 저장 완료된 첨부에는 pill·목록 어느 뷰에도 제거/삭제 컨트롤을 두지 않는다. 한 번
  올라간 파일은 그 대화의 근거 기록으로 남고, assistant 는 항상 전체를 참조 스코프로 본다.
  ×는 **아직 대화에 들어가지 않은 항목**(업로드 중 / 실패한 로컬 placeholder)에만 붙으며
  `_discardPendingAttachmentPill` 이 목록에서 뺀다(그 함수는 `ready` 항목을 만나면 no-op).
  프론트는 `DELETE /api/attachments/{id}` 를 호출하지 않는다(엔드포인트는 백엔드에 존치).

### 4.4 audit.purge 버튼 + 위험 모달 (admin)
- 위치: Audits pane `.admin-pane-actions`, CSV 버튼 옆. `audit.purge` 권한자만 노출.
- 버튼: "보존기간 초과 로그 정리", `--danger` 외곽선(text/border `--danger`, hover bg `--danger-soft`).
- 모달(`showTemporaryPasswordModal` 패턴): cutoff 날짜 입력 + **dry-run 먼저** 호출해 `to_purge` 건수 표시 → typed-confirm(건수 입력) → 실 purge. `--danger` 강조 + 되돌릴 수 없음 명시.

### 4.5 내 활동 기록 탭 (profile drawer)
- 위치: `.drawer-tabs` 에 3번째 탭 "내 활동 기록"(`data-profile-tab="audits"`) + 대응 pane.
- 리스트: 시각(`formatDateTime`) · action_code(`--mono` 칩) · resource_type/id · (행 클릭 → 상세). 페이지네이션 `next_cursor` "더 보기".
- 빈/권한: 권한 없으면 탭 자체 비노출(`audit.read.own`). 빈 목록 "활동 기록이 없습니다."

### 4.6 감사 필터 facet 드롭다운
- `#auditFilterActorId` → `<select>`(username→actor_account_id 매핑, "전체" 기본). `#auditFilterResourceType` → `<input list>` + `<datalist>`(distinct resource_type). free-text 입력 호환 유지.

### 4.7 attachment-grants 진단 카드 (admin dashboard)
- 위치: dashboard pane, summary-metrics 아래.
- 카드: "첨부 DB 권한 상태" — `healthy`면 `--success` "정상", drift면 `--danger` "N건 drift" + 스키마별 missing/extra 펼침. `console.access` gate.

## 5. Layout Principles

- 간격: 모달 내부 16px 행 간격, 버튼 그룹 8px gap. 라디우스 토큰(`--r-sm` 컨트롤, `--r-lg` 모달/카드).
- 신규 진입점은 **기존 컨테이너에 삽입**(새 페이지/라우트 금지). 모달은 body append + ESC 닫기.
- 정렬: 액션 버튼 우측 정렬(모달 footer), 파괴 동작은 우측 끝.

## 6. Depth & Elevation

- 모달 backdrop: rgba(0,0,0,.4) + panel `--shadow-lg`. 인라인 카드: `--shadow-sm`. 드롭다운: `--shadow-md`.
- z-index: 모달 9999(기존 다이얼로그 선례), admin 모달은 `.admin-modal-overlay` 기존 z 답습.

## 7. Do's and Don'ts

- ✅ 기존 helper 재사용(showToast, apiFetch, can/markAccessBlocked, switchProfileTab, confirmBulkAction).
- ✅ 파괴 동작 = `--danger` + 확인 단계(혹은 dry-run+typed-confirm).
- ✅ 권한 없는 컨트롤은 hidden 이 아니라 `is-access-blocked`(존재 인지 + 클릭 시 토스트) — 단, 탭/대용량 패널은 권한 없으면 비노출.
- ❌ 새 색/폰트/라디우스 토큰 도입 금지. ❌ 영구 `style="display:none"` 컨테이너에 컨트롤 가두지 말 것(이번 버그의 근본 원인). ❌ 인라인 style 로 class 가시성 토글을 덮어쓰지 말 것.
- ❌ 새 라우트/페이지 신설 금지(기존 drawer/pane/menu 확장).

## 8. Responsive Behavior

- 모달: max-width 560px, 모바일 폭에서 `width: calc(100vw - 32px)`. 터치 타깃 ≥ 36px.
- composer 즉시답변 버튼: 좁은 폭에서도 send-btn 과 한 줄 유지(텍스트 짧게 "즉시 답변").
- 감사/공유 리스트: 가로 overflow 시 내부 스크롤(기존 `.admin-pane` 패턴).

## 9. Agent Prompt Guide

- 빠른 색 참조: 액션=`--primary`(#2563eb), 파괴=`--danger`(#dc2626), 정상=`--success`(#16a34a).
- 신규 컨트롤 추가 시 프롬프트: "기존 `static/styles.css` 토큰만 사용. 가시성은 `.hidden` class 토글로(인라인 style 금지). 권한은 `can()`/`markAccessBlocked()`. 파괴 동작은 `--danger`+확인."
- 모달 필요 시: app 측은 `.share-mgr-backdrop`/`.share-mgr-panel` 패턴(예: `showTotpLoginPrompt`), admin 측은 `showTemporaryPasswordModal`/`.admin-modal-overlay` 패턴 복제.
