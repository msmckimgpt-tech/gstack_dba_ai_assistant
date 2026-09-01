---
run_at: 2026-09-01T10:45:00+09:00
session: ai/claude/feature-0043-steps-result-split
scope: 상세의 단계/결과셋 범위 분리 · 스크롤 대상을 단계 목록으로 한정
verdict: PASS (자동) · Windows-browser 는 POST-DEPLOY 로 이월(사유 아래)
---

# Run — TASK-20260901T104500-steps-result-split (PRE-DEPLOY)

## 1. 컨테이너 pytest — 전량 green

전 8 디렉토리. 신규·개정 13건:

| 축 | 단정 |
|---|---|
| 스크롤 귀속 | `.step-detail-list` 만 `overflow-y: auto` + 캡(min-height 미지정·contain) · `.message-details-body` 는 캡·overflow **부재** |
| 결과셋 해방 | 상세 전용 결과 표 축소 규칙 **부재** · 전역 상한 `(60, 460)` 불변 |
| 유계성 | 단계 목록·SQL 블록·결과 표 **셋 다** 자기 상한+overflow 보유(하나라도 잃으면 FAIL) |
| 범위 분리 | `appendDetailBlock` 2회(「단계」·「쿼리 결과」) · `is-result-range` 표식 · 단일/복수 SQL 동일 자리 |
| 죽은 코드 금지 | `revealInPanel`·`_NAV_REVEAL_MARGIN_PX` 부재 · 복원 조건 주석 존재 · `pageTo` 단일 전환 경로 · `scrollIntoView` 부재 · `preventScroll` 2회 |
| 스크롤 보존 | 보존 대상이 `.step-detail-list`(옛 선택자면 조용히 no-op) · 예약 취소 · 사용자 조작 우선 |

## 2. node 동작 하네스 — 18/18 무회귀

## 3. codex 적대 리뷰 2R — P1 0건 수렴

1R P2 2건: ①reveal 영구 no-op → **반영(제거)** ②바깥 캡 제거로 높이 회귀 → **근거 기각**
(사용자 명시 요구 · 주범은 단계 목록이며 300px 로 캡 · 결과 범위는 여전히 유계). 기각은
「무시」로 끝내지 않고 **부분별 상한 불변식 테스트로 승격**했다. 상세는 `REVIEW.md`.

## 4. Environment: Windows-browser — **미수행 (POST-DEPLOY 로 이월)**

**사유**: CSS·JS 변경이라 미머지 상태로는 실 브라우저 검증 불가(자산 스탬프 미주입 + 모듈 캐시).
판정 핵심이 **높이·스크롤 귀속 실측**이라 픽셀-클래스다.

**POST-DEPLOY 측정 항목** (먼저 열거):

1. `.step-detail-list` 가 `scrollHeight > clientHeight` 로 **스스로 스크롤**하는가, 캡에 걸리는가.
2. `.message-details-body` 가 **스크롤하지 않는가**(`scrollHeight ≈ clientHeight`, overflow visible).
3. 결과 표가 상세 안에서도 전역 상한(≤460px)을 쓰는가(상세 전용 축소 없음).
4. ◀▶ 페이징 시 **어떤 스크롤도 움직이지 않는가**(단계 목록·대화 로그·문서 전부 불변) —
   결과 범위가 고정 위치라는 주장의 실측.
5. 두 범위의 제목(「단계」·「쿼리 결과」)이 실제로 렌더되는가.
6. 상세 전체 높이가 부분 상한의 합 안에 드는가(페이지 과대 증가 부재).
