---
run_at: 2026-08-31T19:11:04+09:00
session: ai/claude/feature-0043-details-scroll-panel
scope: 말풍선 상세 자기 스크롤 패널 + 결과셋 페이징 시 패널 내부 이동
verdict: PASS (자동) · Windows-browser 는 POST-DEPLOY 로 이월(사유 아래)
---

# Run — TASK-20260831T175800-details-scroll-panel (PRE-DEPLOY)

## 1. 컨테이너 pytest — 전량 green

`make test` 와 같은 격리 env, agent 이미지에 worktree 마운트. 전 8 디렉토리.

신규 10건:

| 축 | 단정 |
|---|---|
| 패널화 | `max-height` 존재 · `overflow-y: auto` · **`min-height` 부재**(요구: 최소 높이 제한 없음) · `overscroll-behavior: contain` |
| 중첩 방지 | 패널 안쪽 표 상한 ≤ 패널 × 0.75 (표만으로 패널을 채우지 못한다) · **전역 표 상한 불변**(패널 밖 인라인 표 무회귀) |
| 페이징 이동 | `closest(".message-details-body")` · `scroller.scrollTop` · **`scrollIntoView` 부재** · `pageTo` 단일 전환 경로(`activeIdx` 재대입 1곳) · reveal 3회 재적용 |
| 포커스 | ◀▶ 두 버튼 모두 `preventScroll: true` · `root.focus();` 잔존 0 |
| 스크롤 보존 | `cancelAnimationFrame`(옛 예약 취소) · `scrollTop === 0` 일 때만 복원 |

## 2. node 동작 하네스 — 18/18 무회귀

`verify_bridge_live_step_progress.mjs` 전건 PASS(소요 귀속·스트림 연속성·뮤테이션 역검증).
이번 변경은 표시층이라 그 계약을 건드리지 않는다.

## 3. codex 적대 리뷰 2R — P1 0건 수렴

1R P2 3건(중첩 잔존·reveal 1회 계산·stale rAF 복원) 전건 반영 → 2R **P1 0건**.
상세·자체 발견(테스트가 스코프 규칙을 전역 규칙으로 오독)은 `REVIEW.md` `REV-20260831T175800-…`.

## 4. 관측된 flake (본 변경과 무관, 정직 표기)

전체 실행 1회차에서 `feature-0014 test_edge_rolling_gate.py::test_g3b_observed_isolation_…` 가
타이밍 단정으로 실패했다(`2.0087s >= 3` 불만족). 부하 중(docker + 실 브라우저 + codex 동시)
관측이며 **격리 재실행 3/3 PASS**. 본 diff 는 `feature-0014` 파일을 **0건** 건드린다(확인).
이후 클린 재실행에서 전량 green.

## 5. Environment: Windows-browser — **미수행 (POST-DEPLOY 로 이월)**

**사유**: 변경 실질이 CSS·JS 다. 미머지 JS 는 실 브라우저로 검증할 수 없다(자산 스탬프 미주입 +
모듈 캐시로 구버전 실행). 게다가 이번 변경의 핵심 판정은 **높이·스크롤 실측**이라 픽셀-클래스다.

**POST-DEPLOY 에서 볼 것** (표시면·측정값 먼저 열거):

1. 상세 펼침 시 `.message-details-body` 의 `clientHeight` 가 상한에 걸리고 `scrollHeight >
   clientHeight` (자기 스크롤 발생)인가.
2. 그때 **페이지(대화 로그) 스크롤 높이가 종전만큼 늘지 않는가** — 이 요청의 본질.
3. 패널 안쪽 결과 표 높이 < 패널 높이 (중첩 함정 부재).
4. ◀▶ 페이징 시 **패널 scrollTop 만** 변하고 대화 로그 scrollTop 은 **불변**인가.
5. 페이징 후 네비게이터 헤더가 패널 상단(≈ 6px 여백)에 오는가.
6. 짧은 상세(단계 1건)는 상한에 걸리지 않고 짧은 대로인가(최소 높이 제한 없음).
