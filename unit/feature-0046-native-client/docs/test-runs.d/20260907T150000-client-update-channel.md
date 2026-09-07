---
run_at: 2026-09-07T17:10:00+09:00
session: ai/claude-corp/feature-0046-client-update-channel
scope: feature-0046 client-update-channel (버전 정본 · 릴리스 채널 · 업데이트 수신)
verdict: PASS
---

# Run — 클라이언트 업데이트 채널

⚠ 이 기록은 **적대 검증 2라운드 수정이 반영된 최종 트리**의 것이다. 라운드 중간 수치
(478 · 501)는 인용하지 않는다 — 다른 트리의 것이고, 회귀 판정(main 대비 차집합)의
기준선으로 쓸 수 없다.

## 1. 단위 (Environment: CLI)

```
python3 -m pytest unit/feature-0046-native-client/tests
→ 506 passed in 21.81s
```

신규 124건. 인접 스위트 회귀 확인
(`PYTHONPATH=…/feature-0002/src:…/feature-0003/src:.`):

```
python3 -m pytest unit/feature-0003-agent-web-ui/tests unit/feature-0043-external-llm-bridge/tests -q
→ FAILED test_share_redaction_invariant.py::test_share_sanitize_step_handles_malformed
```

⚠ **선재 실패다 — 이 cycle 의 회귀가 아니다.** 같은 테스트를 `main` 체크아웃
(`repo/`, `3dbf79c9`)에서 그대로 돌려 **동일하게 FAIL** 함을 확인했다(판정 = main 대비
차집합). 이 cycle 이 건드린 `share` 경로는 없다.

## 2. 결함 주입 — 새 단언이 실제로 잡는가 (Environment: CLI, §16.7 G11-b)

통과만 확인한 단언은 「무엇도 검사하지 않는 단언」과 구별되지 않는다. 워킹트리를 건드리지
않고 **텍스트 사본**에 결함을 넣어 같은 술어를 돌렸다. 각 행은 **「무엇을 되돌렸을 때
그 단언이 FAIL 하는가」** 다.

| 되돌린 것 | 정상 | 되돌림 |
|---|---|---|
| `.iss` 의 인자-단위 `/RELAUNCH` 판정을 `Pos` 부분문자열로 | 참 | **거짓** |
| `.iss` 버전 폴백을 정본과 다르게(`1.0.0`) | 참 | **거짓** |
| 빌드에서 `/DAppVersion=` 주입 제거 | 참 | **거짓** |
| 빌드에 `import client.version` 추가 | 참 | **거짓** |
| 빌드 버전 정규식을 느슨한 `[0-9.]*` 로 | 참 | **거짓** |
| 버전 정본을 `VERSION_RE` 가 거절하는 값(`1.1.0.0.0`)으로 | 참 | **거짓** |
| `_client_download_url` 의 릴리스 채널 조회 제거 | 참 | **거짓** |
| `app.py` 에 `/client` StaticFiles 마운트를 **다시 넣음** | 참 | **거짓** |
| compose 의 `/srv/client` 마운트를 다른 경로로 | 참 | **거짓** |
| 서버 기본 경로를 마운트 지점과 어긋나게 | 참 | **거짓** |
| 다운로드 라우트 경로를 비-리터럴 표현식으로(ROUTEMAP 이 `?` 로 적는다) | 참 | **거짓** |
| `SILENT_ARGS` 에 `/RESTARTAPPLICATIONS` 를 되돌림 | 참 | **거짓** |
| `.part` 이름을 프로세스 기준으로 되돌림 | 참 | **거짓** |
| tkinter 껍데기에서 업데이트 메뉴 항목 제거 | 참 | **거짓** |
| 브라우저 셸의 종료 신호 검사를 트레이 생존 블록 안으로 되돌림 | 참 | **거짓** |

**15/15 가 되돌림에서 FAIL** — 전부 실제로 무언가를 검사한다.

⚠ 이 표를 만드는 과정에서 **proof 스크립트 자신이 G11-a 함정에 빠졌다**: `/RESTARTAPPLICATIONS`
부재 단언을 소스 전체에 대해 걸었더니 「왜 쓰지 않는가」를 설명하는 주석이 그 단언을 깼다.
술어를 선언문(`SILENT_ARGS = (…)`)으로 좁혀 해소했다 — 실제 pytest 단언은 애초에 튜플 값을
본다(`test_a_relaunch_owner_is_single`).

## 3. 행위 커버리지 — 취득 경로 (Environment: CLI)

적대 리뷰 C-5 가 지적한 공백(스트리밍 `download()` 에 행위 테스트 0건)을 닫았다.
`updater._open` 을 가짜 스트림으로 바꿔 구동:

- 성공 → 파일 내용이 스트림과 **byte-동일**
- 지문 불일치 → `None` + `.part` **잔재 0**
- 선언 초과 → 읽기가 끊기고 `.part` 잔재 0
- **두 스레드 동시 실행** → 각 흐름이 돌려준 경로의 내용이 **그 흐름이 검사한 바이트**
  (P1-A 회귀 게이트 — 종전에는 한 흐름이 다른 흐름의 바이트를 실행 대상으로 돌려줬다)
- `verify_file` → 검사 뒤 파일이 바뀌면 **거짓** (§3-b 판정면 = 실행면)
- 단일 실행 → 두 번째 흐름은 `already_running`

파리티 테스트가 실제로 갈림을 잡는지도 결함 주입으로 확인했다 — tkinter 껍데기에서
업데이트 항목을 제거하니 **FAIL**.

## 4. 종단 — 반입 → 서빙 → 수신 → 거절 (Environment: CLI + 실 TLS 서버)

단위 테스트는 판정 술어까지만 본다. 「생성 성공은 소비 가능을 함의하지 않는다」(§16.7 G9-d)
이므로 **실 TLS 서버**(openssl 자체 서명 CA, `https://127.0.0.1:<port>`)를 띄우고 클라이언트
코드를 그대로 돌렸다:

```
1. publish  : 9.9.9 1,200,002B sha=f266d70fc6db…
2. server   : /api/ai/client/latest → /client/DQAConnect-Setup-9.9.9.exe
3. TLS server: https://127.0.0.1:43471 (사내 CA 서명)
4. client   : 새 버전 감지 9.9.9 (내 버전 1.0.0)
5. client   : 같은/낡은 버전은 갱신하지 않는다
6. client   : 내려받음 (흐름별 유일 이름) 1,200,002B — sha256 일치
7. client   : 파일이 바뀌면 **버린다**(지문 불일치)
8. server   : 갈린 상태는 광고하지 않는다(404)
```

**8단계 PASS.** 받은 바이트가 올린 바이트와 byte-동일함을 직접 비교했다.

## 5. 미실측 (정직 표기)

- **설치기 실제 실행**(`/SILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /RELAUNCH`
  로 파일을 갈아 끼우고 다시 뜨는 그 한 걸음) — Windows 빌드 머신이 필요하다.
  `updater.apply()` 는 인자·detach 플래그까지, `.iss` 는 분기 존재까지 잠겼고 **그 다음
  한 걸음은 미검증**이다. Windows 머신이 생기면 **가장 먼저 볼 것**(적대 리뷰 §3-c):
  `PrivilegesRequired=lowest` + `PrivilegesRequiredOverridesAllowed=dialog` 조합에서 무음
  설치가 권한 선택 대화상자를 어떻게 처리하는가 · `/RELAUNCH` 가 미지 스위치로 조용히
  무시되지 않는가 · `ParamStr` 분기가 실제로 참이 되는가 · 관리자 설치 머신에 per-user
  무음 업데이트가 **두 번째 사본**을 만들지 않는가.
- **웹 패널의 업데이트 표시** — 이번 cycle 은 `static/**` 을 건드리지 않았다(사유는
  FUNCTION.md §P0-AH 말미). 업데이트 입구는 **세 껍데기의 트레이**이며 그것은 실재한다.
- `Environment: Windows-browser` Run 없음 — **웹 자산 변경이 0건**이라 check #13 대상이 아니다.
