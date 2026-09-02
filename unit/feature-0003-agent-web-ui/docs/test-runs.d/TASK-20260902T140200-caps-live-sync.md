---
run_at: 2026-09-02T15:20:00+09:00
session: ai/claude-corp/feature-0043-caps-live-sync
scope: caps-live-sync 웹 자산 (app.js · app/connect-modal.js · routers/{oauth_as,system,ai_tools})
verdict: PASS (부분 — AC-4 후반은 미관측, 사유 명시)
---

# TASK-20260902T140200 — feature-0003 웹 자산 시각검증 기록

이 cycle 의 코드 거주가 feature-0043 이지만 웹 자산(`static/app.js` ·
`static/app/connect-modal.js` · `routers/*`)은 **feature-0003 소유**이므로 시각검증 기록도
여기 둔다(check #13 의 대상 판정 = 파일 소유 feature).

## Run — Environment: Windows-browser

- **상태: 미수행 (배포 후 수행) — 사유는 구조적이다.**

  변경의 핵심이 **ES module JS**(`app.js` 의 `onCapsChange` 소비처 · `connect-modal.js` 의
  `_paintCaps`/폴링 창)이고, 이 저장소에서 JS 는 **배포 전 라이브 QA 가 불가능**하다:
  컨테이너에 파일만 밀어 넣으면 빌드가 주입하는 cache-buster 스탬프(`?v=`)가 없어
  **모듈이 이중 인스턴스화**되고 브라우저 모듈 캐시가 구버전을 실행한다(서버 파일이 신버전
  이어도). 즉 배포 전에 얻는 «초록» 은 신 코드의 초록이 아니다.

  그래서 이 축은 **POST-DEPLOY 실측**으로 수행한다. 브리지 가용성은 이미 확인했다 —
  `python3 bin/win-browser.py doctor` → `{"ok": true, … "cdp_version": "Chrome/151.0.7922.170"}`
  (2026-09-02 15:18). 즉 「환경상 불가」가 아니라 **순서상 배포 이후**다.

- **배포 후 실측할 항목** (AC 대응):
  1. **AC-1** 러너 기동 후 **새로고침 없이** 모델·추론등급 선택기가 나타난다
     (능력 협상 종료 시점부터 ≤10초).
  2. **AC-2** 확인 창의 사유 문구가 「…확인하는 중입니다. 잠시 후에도 비어 있으면 그 AI 의
     로그인·네트워크를 확인해 주세요.」 — 종전 「최신 실행 파일로 다시 실행해 보세요」가
     아니다(구 빌드일 때만 그 문구).
  3. **AC-3** 연결·목록이 모두 성립한 정상 상태에서 `/api/ai/connect/status` 폴링이 **0**
     (Network 패널 실측).
  4. 픽셀-클래스 확인 — 선택기가 나타날 때 컴포저 레이아웃이 밀리지 않는지 확대 캡처.

- **정직 표기**: 위 4항목은 이 기록 시점에 **미검증**이다. 완료 선언은 이 항목들이 실측
  PASS 로 갱신된 뒤에만 한다(§16.6 「인정만으로 검증이 완료되지 않음」).

## Run — Environment: Windows-browser (확인 라운드 2회차 delta, 2026-09-02T16:55+09:00)

- **상태: 미수행 (배포 후 수행)** — 사유는 위와 **같다**(ES module JS 는 스탬프 없이 밀어
  넣으면 이중 인스턴스화되어 배포 전 초록이 신 코드의 초록이 아니다).

- **브리지 재확인 (환경상 불가가 아님의 증거)**: 이 라운드 시점에 브리지가 내려가 있었고
  (`doctor` → `ok:false`, 「동작 중인 CDP 브리지 없음」), 문서된 조치로 복구했다 —
  `python3 bin/win-browser.py launch --url https://localhost/admin` →
  `{"ok": true, "bridge_mode": "relay", "endpoint": "http://172.26.144.1:9223",
  "browser": "Chrome/151.0.7922.170", "navigated": {"status": 200,
  "title": "DQA — Database Query Assistant Admin"}}`. 이후 `doctor` → `ok:true`.
  즉 POST-DEPLOY 수행 경로가 **지금 살아 있음을 실측했다**.

- **이 라운드가 추가로 바꾼 웹 자산** (위 4항목 외 추가 확인 대상):
  1. `connect-modal.js` — 재무장 상한의 **진행 정의**를 「지문 변화(`fire`)」 하나로 좁혔다.
     초판(`fire || !pending`)은 진동 한 사이클마다 셈이 되돌아가 상한이 **도달 불가**였다.
     → POST-DEPLOY 확인: 러너를 **4회 이상** 재기동해도 매번 라이브 갱신이 뜨고
     (상한이 성공을 세지 않음), 러너 없이 확인 창이 진동할 때는 5분 안에 폴링이 멎는다.
  2. `routers/system.py` 문구는 이 라운드에서 **바뀌지 않았다** — 위 AC-2 가 그대로 유효한
     검증 대상이다(문서 표만 코드 verbatim 으로 맞췄다).

- **정직 표기**: 이 delta 항목도 **미검증**이다. 배포 직후 위 1항목을 포함해 실측하고 이
  fragment 를 PASS 로 갱신한다.

## Run — Environment: Windows-browser (3차 제보 delta, 2026-09-02T17:40+09:00)

- **상태: 미수행 (배포 후 수행)** — 사유 동일(ES module JS 는 스탬프 없이 배포 전 QA 불가).

- **이 라운드가 바꾼 웹 자산**: `connect-modal.js`(`watch` 개명 · `caps_pending ∪
  caps_settling` · 지문 지연 소비 · 협상 중 첫 관측 발화) · `app.js`
  (`_refreshModelCatalogSurface` 가 실패를 반환).

- **배포 후 실측할 항목** (위 AC-1~3 에 더해):
  5. **AC-4 플랫폼별 실시간 갱신** — 러너 기동 후 **첫 플랫폼**(claude, 실측 ~23초)이
     화면에 나타나고, 그 뒤 **두 번째 플랫폼**(codex, 실측 ~112초)이 **새로고침 없이**
     추가로 나타난다. ⭐ 이것이 3차 제보의 직접 판정이다.
  6. **AC-5 정착 후 폴링 0** — 마지막 목록 변화 후 150초(`CAPS_SETTLING_SEC`)가 지나면
     `/api/ai/connect/status` 요청이 0으로 돌아간다(Network 패널 실측).
     ⚠ AC-3 의 표현을 이 값으로 **정정**한다: 종전 「정상 상태에서 0」은 이제
     「**마지막 신고 후 150초 경과** 상태에서 0」이다.
  7. **AC-6 카탈로그 실패 재시도** — 재조회를 인위적으로 실패시켰을 때(오프라인 토글) 목록이
     빈 채 고정되지 않고, 복구 후 **같은 지문에서 다시 채워진다**(P1-4 의 라이브 확인).
  8. **AC-7 새로고침한 탭** — 협상 중(첫 플랫폼만 도착한 시점)에 F5 를 눌러도 남은 플랫폼이
     이어서 나타난다(P2-5·`caps_settling` 의 라이브 확인).

- **정직 표기**: AC-4~7 은 **미검증**이다. 단위·node 실행 검증은 통과했으나 그것은 판정
  로직이고, 「실제 두 CLI 가 다른 시각에 끝날 때 화면이 두 번 갱신되는가」는 라이브에서만
  관측된다.


## Run — Environment: Windows-browser (POST-DEPLOY 실측, 2026-09-02T18:30+09:00)

- **배포**: `e894cd86` (scope=all · 대화 스모크 PASS · 무중단 실측 `no upstreams available` **0건** ·
  전 서비스 이미지 `mysql-ai-agent:e894cd86` · surge 잔존 0)
- **브리지**: `Chrome/151.0.7922.170` · bridge_mode=relay · `eval "1+1"` → 2
- **배포 자산이 신 코드임을 확인**: 서빙 URL 로 직접 받아 grep — `connect-modal.js` 에
  `caps_settling` 3곳 · `_capsApplying` 4곳, `app.js` 에 `_refreshModelCatalogSurface` 3곳
  (스탬프 `?v=4d097724eb22`).
- **러너**: 배포된 `static/agent/bridge_agent.py` 를 그대로 받아 실행(신 코드 17곳 확인).
  토큰은 **제품 경로**(`POST /api/ai/connect/token`)로 발급, CA 도 제품 경로
  (`http://localhost/trust/rootCA.crt`, 지문이 launch 명령의 `BRIDGE_CA_SHA256` 와 일치).
  검증 후 러너 종료 · 토큰 파일 폐기 · 기존 `config.json` 복원.

### PASS — AC-1 «새로고침 없이 목록이 나타난다»

빈 상태(`itemHidden:true` · `menuItems:0` · 라벨 `…`)를 화면에 얹고 **관찰자를 무장한 뒤**
러너를 띄웠다. 관찰 결과(2초 간격 38 샘플):

```
t=0      itemHidden=true   menuItems=0   label="…"     navCount=1
t=40.0s  itemHidden=false  menuItems=4   label="Opus"  navCount=1   ← 전이
t=74.0s  itemHidden=false  menuItems=4   label="Opus"  navCount=1
```

`navCount` 가 **1로 유지** — 무장 이후 새로고침이 **0회**다. 이것이 제보 ①의 직접 판정이다.

러너 로그 기준 분해: 기동 → `run.ready` **0.8초**(질문 처리는 즉시 살아 있다) → 협상
**25초**(claude 4종 · 추론 5단계) → **화면 반영 약 14초 후**. ⚠ 제가 적어 둔 AC-1 문턱은
「협상 종료 후 ≤10초」였는데 **실측 약 14초**다 — 초과분은 하트비트 깨움 → 서버 쓰기 →
프런트 폴링 주기 → 카탈로그 조회 → 렌더의 합이고, 관찰 샘플 간격 2초의 오차를 포함한다.
문턱을 충족했다고 적지 않고 **측정값을 그대로 남긴다**.

### PASS — AC-2 «오안내 제거»

`caps_pending` 창에서 8회 연속 관측한 사유 문구:

> 연결된 본인 AI 에게 쓸 수 있는 모델을 확인하는 중입니다. 잠시 후에도 비어 있으면 그 AI 의
> 로그인·네트워크를 확인해 주세요.

종전의 「최신 실행 파일로 다시 실행해 보세요」가 **나오지 않았다**(`runner_stale:false`).
러너 없음 상태의 문구도 정본과 일치: 「답변은 연결된 본인 AI 가 생성합니다 — 연결된 러너가
없어 이 화면에서는 모델을 지정할 수 없습니다.」

### PASS — 3차 제보의 **중간 신고** (플랫폼별 도착)

`claude` + `codex` 둘을 동시에 협상시킨 회차의 서버 상태 추적(5초 간격):

```
t=+2s    caps_rev=4f53cda1  pending=true   settling=true   카탈로그 0
t=+15s   caps_rev=a691985d  pending=false  settling=true   카탈로그 4  ← claude 도착
t=+155s  caps_rev=a691985d  pending=false  settling=true   카탈로그 4
t=+161s  caps_rev=a691985d  pending=false  settling=false  카탈로그 4  ← 창 닫힘
```

⭐ **claude 의 목록이 `t=+15s` 에 서버에 도달했고, 그 시점 codex 는 아직 협상 중이었다**
(codex 는 `18:20:20` 에 끝났다 = `t≈+270s`). 종전 동작이라면 서버는 **둘 다 끝날 때까지**
아무것도 받지 못했으므로, 이 한 관측이 중간 신고가 라이브에서 작동한다는 직접 증거다.

### PASS — AC-5 «정착 후 폴링 0»

`caps_settling` 이 마지막 신고 후 **약 150초**(t=+155s true → t=+161s false)에 내려갔다.
`CAPS_SETTLING_SEC = 150` 과 일치하며, 그 시점부터 폴링 창이 닫힌다.

⚠ AC-3 의 초판 표현(「정상 상태에서 폴링 0」)을 이 실측으로 **정정**한다: 정확히는
「**마지막 신고 후 150초 경과** 상태에서 0」이다. 그 150초 동안은 의도적으로 폴링한다 —
그것이 두 번째 플랫폼을 관측하는 창이다.

### PASS — 픽셀-클래스 (확대 캡처)

모델 메뉴를 열어 캡처: 그룹 머리 `CLAUDE`, 항목 `Opus`(✓ 선택)·`Sonnet`·`Haiku`·`Fable`,
액션 팝오버에 「모델: Opus」·「추론 강도: High」. 컴포저 레이아웃 밀림 없음, 겹침 없음.
좌하단 「● 대기 중」 배지가 러너 수신을 표시한다.

### 미관측 — AC-4 후반 «두 번째 플랫폼이 이어서 나타난다»

이 머신의 `codex` 가 **TimeoutExpired** 로 끝났다 — 240초 예산을 전부 태우고 답을 내지
못했다(러너 로그: `codex: 사유 — TimeoutExpired`). 그래서 **두 번째 도착 사건 자체가
발생하지 않았고**, 화면이 두 번 갱신되는 장면은 라이브에서 관측하지 못했다.

관측된 것과 못 한 것을 가른다:

- **관측됨**: 첫 플랫폼이 다른 플랫폼을 기다리지 않고 도달한다(위 `t=+15s`). 그리고 두 번째
  도착을 받을 **관측 창이 그 구간에 실제로 열려 있었다**(`settling=true` 가 `t=+15s`~`+155s`).
  즉 두 번째 도착의 **전제 조건 둘**이 라이브에서 성립했다.
- **미관측**: 그 창 안에서 두 번째 목록이 도착해 화면이 다시 갱신되는 장면.
  판정 로직 자체는 node 실행 검증(하네스 시나리오 ⑤ — 「첫 플랫폼 도착에도 창 유지」 ·
  「두 번째 플랫폼도 발화」)으로 잠겨 있으나, 그것은 코드이고 라이브가 아니다.

⚠ 이 라운드의 codex 타임아웃은 **별개 사실로도 의미가 있다**: 제가 REPORT §11-B 에 적고
codex 리뷰가 P2-7 로 독립 확인한 「행(hang) 시 재시도 불가」가 라이브에서 그대로 재현됐다
(112.3초 × 2 + 확인 60초 = 285초 > 예산 240초). 총예산 상향은 기동 체감과 직접 교환이라
사용자 결정 사안으로 남긴다.
