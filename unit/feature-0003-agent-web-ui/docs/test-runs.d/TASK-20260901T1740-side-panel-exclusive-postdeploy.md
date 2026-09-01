---
run_at: 2026-09-01T17:40:00+09:00
session: ai/claude/side-panel-postdeploy
scope: 우측 사이드 패널 단독 열림 — **POST-DEPLOY** 라이브 실측
verdict: PASS
---

# Run — side-panel-exclusive · **POST-DEPLOY** (배포본 `d3ead999`)

- **Environment**: **Windows-browser** (PB-0008) — Windows Chrome/151, 라이브 `https://localhost`.
- **Runner**: AI · **Bridge**: `relay` @ `http://172.26.144.1:9233`
- **세션 격리(§16.6 a)**: 전용 CDP 포트(9232) · 전용 relay(9233) · 전용 프로필
  `win-browser-cdp-sidebar-live` (`"reused": false`) — 이 세션이 직접 띄운 인스턴스만 조작.
- **Scenario**: PRE-DEPLOY 와 **같은 파일**의 `base_url` 만 `https://localhost` 로 바꾼 사본
  (`scenario.side-panel-exclusive.json` 16 step). 판정 단언은 무수정.

## 배포 판정 (§16.7 G7-a — 이름이 아니라 실 resolve)

```
PR #1475 merge commit          cce7df5e
라이브 배포본 GIT_COMMIT        d3ead999   (web-a · web-b 동일)
cce7df5e ⊂ d3ead999            YES  (git merge-base --is-ancestor)
컨테이너 내 파일               /app/web/static/app/side-panels.js  12918 bytes
served index.html              data-side-panel × 3
edge `no upstreams available`  0건 (최근 5분)
/healthz                       200
```

배포는 `bin/deploy-web.sh` 가 **멱등 no-op** 으로 판정했다 — 병렬 세션이 이미 `d3ead999`
(내 머지를 포함하는 상위 커밋)로 web·워커를 올린 뒤였다. 그래서 «내가 배포했다» 가 아니라
**«라이브가 내 커밋을 담고 있다»** 를 위 4축으로 확인했다.

## evidence identity 대조 (§16.6 c)

```
performance.getEntriesByType('resource') →
  https://localhost/static/app/side-panels.js?v=9763bcf30835
```

라이브 자산 스탬프(`9763bcf30835`)가 붙은 **배포본 모듈**이 실행됐다. PRE-DEPLOY 실측은
`?v=dev`(격리 컨테이너의 미주입 placeholder)였으므로 두 측정은 서로 다른 빌드다.

## 측정 — 16/16 ok

| # | 조작 | attach | step | profile | backdrop |
|---|---|---|---|---|---|
| 0 | 진입 baseline | closed | closed | closed | closed |
| 1 | 첨부 목록 열기 | **OPEN** | closed | closed | closed |
| 2 | 「단계 보기」 | closed | **OPEN** | closed | closed |
| 3 | 프로필 열기 | closed | closed | **OPEN** | **OPEN** |
| 4 | 프로필 닫기 → 첨부 재개방 | **OPEN** | closed | closed | closed |

- **접근성**: 닫힘 baseline `aria-hidden="true"`/`inert` · 열림 시 해제 · 배타 닫힘 시 복귀.
- **상태 복원**: `trashBefore=true → trashAfterRestore=true`(배타 닫힘은 휴지통 모드를 파기하지
  않는다) · `userCloseResetsTrash=false`(× 로 닫은 경우의 리셋은 유지) ·
  `trashAfterConversationSwitch=false`(대화가 바뀌면 스냅샷을 폐기한다).
- 판정은 시나리오 `eval` step 이 직접 단정한다 — 어긋나면 그 step 이 실패한다.

캡처: `artifacts/pb0008-side-panel-exclusive/postdeploy_0[1-4]*.png`

## 잔류물 (§16.6 f)

- 페이지 DOM 원복 확인(`cleaned: true`, 열린 패널 0, `is-bridge-locked` 복원).
- 격리 검증 컨테이너 `web-verify-sidebar`(:18098) · `web-verify-sidebar-before`(:18099) **제거 완료**.
  임시 env 파일 삭제. 브라우저 인스턴스 `down` 으로 종료.
- 데이터: 대화·첨부·계정 **미변경**(기존 대화 `20260831025448-12af0eb5` 를 읽기만 했다).
  마지막 step 의 「새 대화」 클릭은 클라이언트 상태 전환일 뿐 서버에 대화를 만들지 않는다.
- 브라우저 프로필 6개(`win-browser-cdp-sidebar`, `-r2`~`-r5`, `-live`)가 Windows
  `%LOCALAPPDATA%` 에 남았다 — 아래 함정 회피로 라운드마다 빈 캐시 인스턴스를 썼기 때문.
  자격증명과 같은 민감도로 취급한다(공유·복사 금지).

## 완료 판정 (§16.3 deploy-backed)

1. cycle-finalize 완료 — PR #1475 merged (`cce7df5e`), worktree·브랜치 정리 완료. ✓
2. 라이브 재배포 검증 — 배포본 `d3ead999` 에 변경 포함 확인 + `/healthz` 200 +
   엣지 `no upstreams available` 0 + **배포본 모듈로 16 step 실측**. ✓

## 재사용 노트 (PB-0008 함정)

정적 자산 응답에 `Cache-Control` 이 없어(`last-modified`/`etag` 만) 브라우저가 ES module 을
휴리스틱 캐시한다. 코드를 고친 뒤 같은 프로필로 재실행하면 **구 모듈이 실행돼 거짓 FAIL** 이
난다(`transferSize: 0` 으로 식별). 회피: `WIN_BROWSER_PROFILE` 을 새 경로로 바꿔 빈 캐시
인스턴스를 띄운다.
