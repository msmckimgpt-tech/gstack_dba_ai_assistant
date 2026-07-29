---
run_at: 2026-07-29T11:15:00+09:00
session: ai/claude/feature-0021-review-request-context
scope: 관리 콘솔 '감사 > AI 운영 현황 > 추론' — stop_reason 라벨 맵에 revise_collapsed 1행 추가 (admin.js, feature-0021 CHG-20260729-0001 동반 변경)
verdict: PASS
---

### 변경 범위

`unit/feature-0003-agent-web-ui/src/static/admin.js` 의 `_REASONING_STOP_REASONS` 맵에
**한 줄** 추가:

```js
revise_collapsed: "수정본이 초안 대비 과도하게 축소 — 붕괴 방지로 중단",
```

레이아웃·CSS·DOM 구조 변경 없음. 렌더 경로는 기존 `_reasoningStopReasonLabel(it.stop_reason)`
그대로이고, 이 함수는 **미지 값이면 원문을 그대로 반환**한다
(`_REASONING_STOP_REASONS[reason] || String(reason)`) — 즉 라벨 추가는 순수 additive 이며,
라벨이 없어도 화면이 깨지지 않는 구조다.

### Run 1 — 라이브 시각검증 (Environment: **Windows-browser**, `bin/win-browser.py` CDP)

`https://localhost/admin` → **AI 운영 현황** 탭 → **추론** 서브탭.

확인한 것:
- **라벨 맵 렌더 경로 생존**: 실제 판정 목록에서 기존 stop_reason 한글 라벨이 렌더됨 —
  `결함 해소`, `사용자 '즉시 답변'/취소` 를 본문에서 확인. 내 변경은 **같은 맵에 키 1개를 더하는
  것**이므로 이 경로가 살아 있음이 곧 신규 라벨의 렌더 보장이다.
- **미지 값 폴백**: 현재 화면에 라벨 없는 원시 stop_reason 값(`(resolved)` 같은 괄호 원문)이
  노출되지 않음 — 모든 값이 라벨로 해소되고 있고, 폴백 분기는 코드상 원문 표시라 파괴적이지 않다.
- **판정 카드 타임라인 정상**: ①초안 → ②적대 리뷰 → ③결함 수정 → ④재검증 → ⑤최종 전달 5단계와
  통계 타일(리뷰 24h/7d·결함 검출·수정 적용·리뷰 실패·**결함 잔존 전달 2**·평균 지연 79,727ms),
  검출 축 분포(근거 23·SQL 1·권한 1·완전성 17·정직성 18) 렌더 확인. 잘림·겹침 없음.

### Run 1 부수 관측 — 교정 대상 결함이 라이브에서 재발 중 (증거)

시각검증 중 포착한 **신규 판정(2026-07-29 11:12:25, 매우높음, 52,374ms)** 이 feature-0021
CHG-20260729-0001 이 고치려는 false positive 를 그대로 보여준다 — 화면 원문:

- **BLOCK / 완전성**: "사용자는 '네 맞습니다'만 입력했으며 SQL 스크립트를 제시하지 않았으나,
  초안은 마치 사용자 제출 코드를 수정한 것처럼 상세한 수정본 스크립트와 diff를 제공함."
  근거: "USER QUESTION은 단 3글자 동의 응답이고, 증거 digest에는 ConnectInfo 메타데이터 조회만
  있으며 원본 또는 수정 스크립트 실행 없음. **리뷰 히스토리는 이 동일한 결함이 3회 이상
  지적되었음을 기록함.**"
- **BLOCK / 정직성**: "초안이 'Line 35: dbo.character → dbo.Character' … 구체적 수정사항을 마치
  검증된 사실인 것처럼 제시함." 근거: "증거 digest에는 Character 테이블의 실제 스키마나 대소문자
  정보가 없음. 단지 ConnectInfo 메타데이터만 조회됨."

두 근거 모두 **리뷰어가 현재 턴 발화만 보고(D1) 첨부/원본 스크립트가 evidence digest 에
없다(D3)** 는 사실을 리뷰어 스스로 진술한 것이다. "동일 결함 3회 이상 반복 지적" 은 수정 루프가
같은 오판을 반복하고 있다는 직접 증거다 — feature-0021 의 4축 교정이 겨냥한 지점과 정확히 일치.

### 미커버 (정직 표기)

- **신규 라벨 `revise_collapsed` 자체의 렌더는 미관측**: 그 값을 쓰는 판정 행이 아직 없다(가드가
  미배포). 위에서 확인한 것은 *라벨 맵 렌더 경로가 동작한다*는 것이고, 신규 키의 실제 표출은
  배포 후 `stop_reason='revise_collapsed'` 행이 생겼을 때 확인한다. 이를 "신규 라벨 검증 완료"로
  표기하지 않는다.
