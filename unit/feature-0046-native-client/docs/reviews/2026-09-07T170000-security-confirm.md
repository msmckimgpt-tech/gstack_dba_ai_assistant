---
doc_type: REVIEW_ARTIFACT
feature_id: feature-0046-native-client
agent: security
timestamp: 2026-09-07T17:00:00+09:00
trigger: §18.8 패널 수렴 계약 (a) — P1 수정 후 **확인 라운드 필수**
verdict: BLOCK
---

### 1. Blocking issues

- **P1-A `update_now()` 에 단일 실행 게이트가 없고, 「고정 자리」가 두 흐름을 같은 `.part` 로 모았다** (high)
  - `Evidence`: probe 실측 — 같은 프로세스의 두 스레드가 같은 `filename` 을 받으며 서로 다른
    바이트를 흘렸다. `.part` 이 PID 기준이라 **스레드는 같은 PID** → 한 파일을 공유.
    T1 이 성공 반환한 경로의 실제 내용은 `digest ok(GOOD)? False / digest ok(ALT)? True`,
    바이트 구성 `{'A': 0, 'C': 1999998}` — **T1 이 검사한 스트림과 T1 이 돌려준 경로의 내용이
    완전히 다르다.** 그 뒤 `update_now` 는 그 경로를 그대로 `apply()` 로 실행한다. 진입점
    게이트도 없다(트레이는 클릭마다 새 스레드 · 웹 패널은 요청마다 · 자동 경로도 같은 함수).
    `.iss` 에 `SetupMutex`/`AppMutex` 도 없다. 바이트가 갈리는 조건도 가정이 아니다 —
    `publish_release.py` 는 「같은 버전의 다른 파일」을 경고만 하고 허용한다고 적어 두었다.
  - `Location`: unit/feature-0046-native-client/src/client/updater.py:426
  - `Reason`: 규율 3 은 「받은 것을 검사한 뒤에만 실행한다」인데 검사되는 것은 **스트림**이고
    실행되는 것은 **디스크 경로**다. 종전 `mkdtemp()` 는 회차마다 다른 디렉토리라 두 흐름이
    구조적으로 만나지 않았고, C3 수정(고정 자리)이 그 격리를 없애며 이 간극이 열렸다 —
    §18.8 (b) 비단조 신호. 미서명 설치기 **둘이 동시에** 같은 설치 디렉토리에 무음으로 돌면
    반쯤 설치된 앱이 남고, 그 상태에서는 앱 자체가 사라져 사용자가 채널로 돌아올 입구가 없다.
    이 저장소는 같은 위험을 러너에 대해 이미 P1 로 판정했다(`ClientApp._connect_gate`).
  - `Action`: `update_now` 전체를 감싸는 단일 실행 잠금(non-blocking → `already_running`) +
    `apply()` **직전에 디스크의 파일을 다시 읽어** 판정 + `.part` 을 흐름별 유일 이름으로.
    소스 문자열 단언을 **두 스레드 동시 실행** 테스트로 교체.

- **P1-B F3 수정의 `or self.pending_update` 폴백이 불변식을 반대로 되돌린다** (high)
  - `Evidence`: probe 실측 — `pending_update=None` 에서 `act("update_apply")` 의 확인 문구는
    「받을 버전을 아직 확인하지 못했습니다 … [아니요] 를 누르세요」였는데, 그 확인창이 떠 있는
    사이 주기 감시가 하는 일(`br.pending_update = U`)을 재현하고 [예] 를 누르니
    `downloaded: ['9.9.9']` — **문구가 이름조차 말하지 않은 버전이 설치 경로로 들어갔다.**
    게다가 그 문구는 「no pending」 전용이라 F5 가 넣은 **주소 불일치 경고가 표시되지 않는다**.
  - `Location`: unit/feature-0046-native-client/src/client/bridge.py:261
  - `Reason`: 같은 함수의 docstring 이 「여기서 거절해 그 문구를 실제 집행으로 만든다」고
    단정하는데 코드는 동시 `update_check` 가 끼어들면 거절하지 않는다 — 주석이 성립하지 않는
    성질을 사실로 진술한다. 감시 tick 이 15분이라 확인창을 열어 둔 창은 좁지 않다.
    이 라인은 F3 수정이 **새로 넣은 코드**이므로 §18.8 (b) 의 두 번째 비단조 사례다.
  - `Action`: `or self.pending_update` 를 삭제하고 `if target is None: return no_pending` 만 남긴다.

### 2. Cross-domain concerns

- **C-1 `ROUTEMAP.md` 가 stale 이고 새 익명 라우트의 경로를 생성기가 원리적으로 못 적는다**
  - `Evidence`: `gen-routemap.py --check` → `STALE`, rc=3. 재생성해도 새 줄은
    `| GET | ? | client_download | public/none | — |` — `_first_str(d.args)` 가 `ast.Constant`
    만 읽고 데코레이터가 표현식이다. 테스트가 그 비-리터럴 형태를 **고정**하고 있다.
  - `Location`: unit/feature-0003-agent-web-ui/src/routers/client_release.py:190
  - `Reason`: ROUTEMAP 은 `ai_read_priority: 4` SSOT 이고 `auth` 열이 권한 게이트를 선고지한다.
    하필 이름을 적을 수 없는 라우트가 **익명으로 실행 파일을 서빙하는 표면**이다. check #15 는
    WARN-only 라 차단도 되지 않는다.
  - `Action`: 데코레이터를 리터럴 경로로 두고 `DOWNLOAD_PREFIX` 일치는 별도 단언으로 잠근다.

- **C-2 tkinter 폴백 껍데기에는 업데이트 입구가 0개인데 「메뉴가 일치한다」는 테스트가 통과한다**
  - `Evidence`: `ClientApp._start_tray` 항목은 `[창 열기, 연결 끊기, 종료]` — `UPDATE_MENU_LABEL`
    없음. 파리티 테스트는 **하드코딩 리스트**와 대조하므로 실물이 갈렸는데도 통과한다.
  - `Location`: unit/feature-0046-native-client/src/client/gui.py:157
  - `Reason`: `--app` 을 모르는 브라우저·정책으로 막힌 머신이 그 껍데기로 떨어지고, 그 머신은
    **영구히 낡은 채로 남으며 그 사실이 로그에조차 남지 않는다**. `wiki/hot.md` 의 「입구는
    트레이 하나이며 그것은 실재한다」가 3개 중 2개에서만 참이다.
  - `Action`: 파리티 테스트를 **다른 표면의 실물 대조**로 바꾸고 그 껍데기에도 같은 항목을 넣는다.

- **C-3 `check_detail` 이 「200 인데 매니페스트가 아니다」를 「이미 최신」으로 접는다**
  - `Evidence`: probe — `200 + <html>502</html>` · `200 + version="1.2.0-rc1"` · `200 + 잘린 JSON`
    셋 다 `(None, '')` → 성공 기록 → 사용자에게 「이미 최신입니다」. 별건으로 `HTTPError(500)` 는
    `'HTTPError'` 로 떨어지고 `http-500` 분기는 **도달하지 않는다**(urlopen 이 4xx/5xx 를 예외로 올린다).
  - `Location`: unit/feature-0046-native-client/src/client/updater.py:373
  - `Reason`: C2 가 닫으려던 결함이 정확히 이것이다 — 전송 계층은 갈랐지만 **내용 계층은 그대로
    접혀 있다**. 라이브에 200-비매니페스트 원천이 실재한다(엣지 오류 본문·롤링 중 응답·퍼블리시 실수).
  - `Action`: `parse_manifest` 의 실패와 「정상적으로 낡음」을 갈라 돌려주고, 상태 분기를
    `HTTPError.code` 로 옮긴다.

- **C-4 자동 경로의 유휴 게이트가 다운로드 이후 재확인되지 않는다**
  - `Evidence`: probe — 진입 시 유휴였다가 `download()` 중 러너가 붙는 상황에서
    `{'ok': True, 'restarting': True}` + `applied: True`. 게이트는 진입 1회이고 다운로드는 600초까지.
  - `Location`: unit/feature-0046-native-client/src/client/bridge.py:290
  - `Reason`: 다운로드 창 안에서 시작된 질문이 **사람에게 아무것도 묻지 않고** 죽는다 — F4 가
    없애려던 결과다.
  - `Action`: `require_idle` 을 **적용 직전 재확인**으로 만들고 받아 둔 파일은 남긴다.

- **C-5 스트리밍 `download()` 에 행위 테스트가 없고 있는 단언은 소스 문자열이다**
  - `Evidence`: 다운로드 관련 단언은 이름 거절·경로 계산·소스 문자열 3건뿐. 성공/불일치/초과/
    원자성 어느 것도 구동되지 않고, 소스 단언은 함수명이 주장하는 성질을 검사하지 않으며
    P1-A 대로 그 성질은 **거짓**이다.
  - `Location`: unit/feature-0046-native-client/tests/test_updater.py:720
  - `Reason`: 직전 라운드 C6 지적(「무엇도 잠그지 않는 단언」)의 재발이고, 이 경우에는 **틀린
    결론을 문서화**한다. 가장 위험한 경로(실행될 바이너리의 취득)를 통째로 다시 썼는데 행위
    커버리지가 0 이다.
  - `Action`: 가짜 스트림으로 4가지 + **두 스레드 동시 실행**(P1-A 회귀 게이트)을 구동한다.

- **C-6 test-run 기록이 리뷰 중인 트리를 서술하지 않는다**
  - `Evidence`: 기록은 `478 passed` 인데 현 트리는 `501 passed`. 결함 주입 표의 마운트 행은
    실제 단언과 방향이 반대로 읽힌다.
  - `Location`: unit/feature-0046-native-client/docs/test-runs.d/20260907T150000-client-update-channel.md:16
  - `Reason`: Run 기록은 「이 diff 를 이 명령으로 이렇게 돌렸다」는 증적이다. 숫자가 어긋나면
    회귀 판정(main 대비 차집합)의 기준선으로 쓸 수 없다.
  - `Action`: 확정 후 재실행해 갱신하고, 각 행을 「무엇을 되돌리면 무엇이 FAIL 하는가」로 쓴다.

### 3. Challenge to current spec

1. **실행 파일 취득의 앵커 우선순위가 뒤집혀 있다** — `pinned` 가 `bundled` 를 이긴다. 게다가
   `--service-base` 가 선택 인자라 그것을 주지 않은 빌드에서는 F5 의 경고 조건이 **구조적으로
   발동하지 않는다**. 동봉값이 있으면 그것만 출처로 삼고, 없으면 릴리스 빌드의 필수 인자로 승격하라.
2. **「스트림을 검사하고 경로를 실행한다」는 모양이 P1-A 를 계속 재생산한다** — 단일 실행 잠금은
   관측된 경로를 막지만 계열을 닫지 않는다. 계열을 닫는 것은 `apply()` 직전에 그 파일을 다시 읽는
   한 줄이다(§16.7 G14 를 F1 에는 적용했고 여기에는 적용하지 않았다).
3. **무음 설치의 권한 갈래가 미실측 가정 위에 있다** — `PrivilegesRequired=lowest` +
   `…OverridesAllowed=dialog` 에서 `/SILENT /SUPPRESSMSGBOXES` 가 권한 대화상자를 억제하지 않으면
   업데이트는 **아무 창도 없이 멈춘다**. Windows 머신이 생기면 가장 먼저 볼 것.
4. **비단조성의 해석** — P1 두 건이 둘 다 직전 수정의 새 코드에 있어 §18.8 (b) 문자적 조건은
   충족된다. 그러나 각각 「잠금 하나 추가」·「`or` 절 하나 삭제」로 닫히는 국소 결손이고
   여섯 수정 중 넷(F1·F2·F4·C1)은 실측으로 완결됐다 — **접근 재설계 신호로는 읽지 않는다.**
   다만 (2) 의 판정면/실행면 분리는 접근 자체의 결이므로 그 한 지점만 설계로 다루기를 권한다.

### 4. Verdict

BLOCK
