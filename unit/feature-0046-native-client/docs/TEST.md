---
doc_type: TEST
feature_id: feature-0046-native-client
status: active
edit_policy: mixed
---

# Test

## 2026-09-10 ChatGPT 데스크톱 Codex

[검증 Run](test-runs.d/20260910-desktop-codex.md): native 660개 검증, runner 37 PASS, 실제 Windows CLI 응답, 동결 DQA WebView2 연결·재실행 2/2 PASS. [출하 Run](test-runs.d/20260910-desktop-codex-release.md): 사용자 설치 DQA 1.5.0에서 데스크톱 연결·실제 GPT-6-Astra 응답까지 PASS.

## 1. 케이스

| 축 | 무엇을 |
|---|---|
| ToS 경계 | 벤더 자격증명 미접촉 · 로그인은 공식 명령만 · 모르는 절차 미발명 |
| 무결성 | DER 지문(파일 해시 아님) · 불일치 시 중단 + 파일 미생성 · 일치 시 통과 · CA 평문 경로 |
| 정본 동기화 | 클라이언트 런타임 목록 == 러너 `_RUNTIME_SPECS` |
| 감지 | WindowsApps 스텁 거부 · JSON 상태 파싱 · 미설치 보고 · 판정 불가는 None |
| 토큰 | 명령줄 미노출, env 전달 (`check`·`spawn` 양쪽) |
| 축 분리 | exit 4 = AI 없음 ≠ 연결 실패 |
| GUI | windowed 빌드에서 `print()` 금지 · `tell()` 은 콘솔·디스플레이 없이도 안 죽음 |
| 트레이 | 메뉴 ID 라우팅 · 기본 항목 · 비활성/구분선 무시 · 콜백 예외 격리 · 툴팁 상한 · 생성 실패 시 `start()` 가 거짓 |
| 창 닫기 분기 | 트레이 있음=숨김(연결 유지) / 없음=종료 · 안내 문구가 그 실재와 일치 · 풍선 1회 |
| 스레드 경계 | 트레이 콜백은 큐에만 넣는다(tkinter 직접 조작 금지) |
| 자식 창 | 자식을 띄우는 **모든** 함수가 창 숨김 인자를 실제로 넘긴다(소스 census + 행위) |
| 두 껍데기 상주 정합 | 상주 중 유휴가 종료시키지 않음 · 트레이 없음/죽음이면 종전 계약 복귀 · [종료] 로만 끝남 · 두 껍데기 메뉴 어휘 동일 |
| 패널 문구 | `status.resident` 로 두 문구를 갈라 말함 · 문구가 가리키는 요소 실재 · DOM 렌더 대조군 |
| 업데이트 버전 판정 | 수치 비교(`1.10.0 > 1.9.0`) · 같으면 갱신 안 함 · 모양 아닌 값은 거짓 |
| 업데이트 출처 | 고정 경로 + TOFU 고정 서버 + 사내 CA · 매니페스트의 URL 미사용 · `remembered_base` 미사용 · 평문 거부 |
| 업데이트 무결성 | 크기·sha256·PE 서명·상한 4축 · 파일명 traversal 거절 · 파일명↔버전 불일치 거절 |
| 릴리스 채널 | 실물 없음/크기·지문 불일치는 **광고 안 함** · 롤백(`--activate`) · 정리가 배포 중인 것을 안 지움 |
| 업데이트 확인창 | `update_apply` 는 `DANGEROUS` · 문구가 버전·연결 유지·다음 정상 실행 적용을 말함 · 자동 적용 기본 꺼짐 |

## 2. 실행

```
python3 -m pytest unit/feature-0046-native-client/tests/ -q     # 506건

# 실 Windows 층(ctypes/Win32)은 리눅스에서 돌지 않는다 — 별도 실측:
#   tests/windows/README.md  (verify_console / verify_flicker / verify_tray / verify_gui)
```

## 3. Run 기록

### Run 2026-09-03T14:00:00+09:00 — 초판
- Environment: Linux (컨테이너 외 로컬) — 단위 20/20 PASS
- Environment: **Windows-native (실 머신, WSL interop)** — 아래 전부 실측
  - AI 감지: `claude` → `C:\Users\…\.local\bin\claude.exe` (**PATH 밖**), `loggedIn=true`, 계정 표시
  - codex·gemini 미설치 정확 보고
  - tkinter GUI 구성: 한글 타이틀 「내 AI 연결」, 604x226
  - PyInstaller `--onefile --windowed` 빌드 성공 → 9,174,548 bytes
  - 실행: **초판은 멈춤**(미처리 예외 대화상자) → `tell()` 수정 후 **안내 대화상자 정상 표시**
- Verdict: PASS (수정 후)
- 미수행: 실 서버 연결 왕복(토큰 필요) · gemini 경로 · 서명 없는 설치의 사용자 체감

### Run 2026-09-04T10:40:00+09:00 — 트레이 상주 + 자식 콘솔 창 제거
- 상세는 fragment: [`test-runs.d/TASK-20260904T100000-tray-and-windowless.md`](./test-runs.d/TASK-20260904T100000-tray-and-windowless.md)
- Environment: `CLI` 177/177 PASS · 뮤테이션 21/21 KILL (NOOP 0)
- Environment: **Windows-native (실 머신)** — 4종 실측 전부 PASS. 대조군까지 둔 관측:
  자식 콘솔 핸들 `2430520 → 0`, 바탕화면 콘솔 창 peak `2 → 1`.
- Verdict: PASS
- 적대 리뷰(codex) P1 4건 수정 후 **재측정본**이다 — 수정 전 수치를 인용하지 않는다.

### Run 2026-09-04T15:20:00+09:00 — 재구성: 웹 셸 주 경로에도 트레이 상주
- 상세: [`test-runs.d/TASK-20260904T150000-tray-parity.md`](./test-runs.d/TASK-20260904T150000-tray-parity.md)
- Environment: `CLI` 256/256 PASS · 뮤테이션 8/8 KILL(NOOP 0, M24 는 문법 파손 판을 폐기하고 행동 판으로 재실행)
- Environment: `CLI` (jsdom) — 패널 상주 문구 **DOM 렌더** 확인 + 대조군 FAIL 실증
- ⛔ **PB-0008 미수행** — 이 패널은 Windows 브리지가 만든 `client_port/nonce` 로만 나타나고
  유효 토큰이 없다. 라이브 반영은 공유 web 컨테이너를 건드려야 해 §13.2.9 가 금지한다.
  다음 cycle 로 이월(사유는 fragment §4).
- Verdict: PASS (미수행 2건 명시)

### Run 2026-09-07T15:30:00+09:00 — 클라이언트 업데이트 채널
- 상세: [`test-runs.d/20260907T150000-client-update-channel.md`](./test-runs.d/20260907T150000-client-update-channel.md)
- Environment: `CLI` — feature 스위트 **506/506 PASS** (신규 124건 — 적대 2라운드 반영 후 수치)
- Environment: `CLI` — **결함 주입 15/15 FAIL**(§16.7 G11-b — 되돌리면 전부 FAIL 한다)
- Environment: `CLI` + **실 TLS 서버** — 반입 → 서빙 → 수신 → 무결성 거절 **종단 8단계 PASS**
  (사내 CA 서명 https, 받은 바이트가 올린 바이트와 byte-동일)
- 선재 실패 1건(`test_share_redaction_invariant`)은 `main` 에서도 동일 FAIL — 회귀 아님
- ⛔ **미실측**: 설치기 실제 실행(`/SILENT /RELAUNCH`) — Windows 빌드 머신 필요
- `Environment: Windows-browser` 없음 — **웹 자산 변경 0건**이라 check #13 대상 아님
- Verdict: PASS (미실측 1건 명시)

### Run 2026-09-07T18:00:00+09:00 — 라이브 배포 실측 (업데이트 채널)
- 상세: [`test-runs.d/20260907T180000-live-deploy-verify.md`](./test-runs.d/20260907T180000-live-deploy-verify.md)
- Environment: `라이브 배포본` — `main` **697ffa84** 전 서비스 롤아웃 + soak 90s + 대화 스모크 PASS
- Environment: `라이브 배포본 (web-a 컨테이너 내부 8000 — 엣지 미경유)` — 채널 **10 PASS + 1 미경유**:
  마운트 실물 · 없으면 404 · 퍼블리시 후 바이트 동일성 · 공고 안 된 이름 404 ·
  같은 디렉토리의 다른 파일 404 · 제거 후 원복. **미경유 1칸** = 경로 탈출(`{filename}` 단일
  세그먼트라 라우트가 매칭조차 안 됨 — 내 가드를 타지 않았고 되돌려 FAIL 시킬 수도 없다)
- 방법과 그 대가: 정본(`1.1.0`)보다 **낮은 1.0.0** 합성 파일 → `updater.py` 경로는 안 집는다
  (`is_newer` 거짓). ⚠ 그러나 `download_url()` 은 **버전을 비교하지 않아** 사람용
  「연결 프로그램 받기」 버튼은 그 밖이었고, **라이브에 38초 창이 실재했다**(08:58:06→08:58:43.9).
  실피해 0(그 창의 외부 클라이언트 매니페스트 요청 0건) — 다음부터는 격리 인스턴스에서 잰다
- ⚠ 배포 중 관측 2건(둘 다 이 cycle 코드와 무관): 1차 ABORT = caddy **exec 채널** 파손(서빙은 200) ·
  배포 창 안 13초 엣지 정지 = **행위 종류 특정(기존 컨테이너 stop/start) · 행위자 미특정**
- ⛔ **미실측**: 엣지 경유 릴리스 200/다운로드 · web-b 채널 · 연결 화면 버튼 전환(체크리스트 [4]
  PB-0008 — **미이행**) · 설치기 실제 실행 · 실 설치기 종단 · §18.8 3라운드
- `Environment: Windows-browser` 없음 — 웹 자산 변경 0건. ⚠ 이것은 **check #13** 의 면제 논거이며
  배포 후 체크리스트 **[4] 의 면제가 아니다**(둘을 접었던 것을 정정)
- Verdict: PASS (미실측 6건 + 미경유 1칸 명시)


### Run 2026-09-08 — DQA 브랜드 아이콘

정본: [브랜드 아이콘 검증](test-runs.d/20260908T020049-brand-icon.md). Windows 재현 진입점은 `tests/windows/verify_brand_icon.py`이며, 사용자의 AI 질의·연결을 수행하지 않는다.


## 2026-09-08 — AI별 자동 연결

[통합 실행 기록](test-runs.d/20260908T123400-connect-discovery.md): Python·DOM·Windows-browser·실제 DQA/WebView2.

## Run: connect-discovery 최종 통합

Environment: DQA-client
Result: PASS
Scenario: 격리 동결 DQA 1.2.0 실행 파일의 연결·위치 선택·재시작 캐시·완료 toast
Evidence: [실행 원장](test-runs.d/20260908T123400-connect-discovery.md), feature-0046 artifacts의 native-results.json.

서비스/API/벤더 응답과 app.js toast 초기화는 대역이다. 네이티브 픽셀 캡처는 빈 면으로 NOT-RUN이며 동일 제품 UI의 Windows Chrome 렌더는 별도 보조 증거다. 실제 벤더 계정 호출·사용자 설치본 교체의 PASS를 뜻하지 않는다.

## 2026-09-08 실제 업데이트 설치 — 1.2.0 실패 재현

- 실제 설치 경로: Windows mckim per-user DQA Connect, 최초 버전1.1.2. 설치 레지스트리/바이너리 지문 대조.
- 실제 트레이 popup에서 “업데이트 확인” 항목 ID를 읽고 Win32 선택 이벤트를 전달했다. 실제 DQA 확인창의 예 버튼을 수락했다. 업데이터 함수·다운로드를 대체하지 않았다.
- 앱이 받은 설치기의 실행→기존 앱 exit0→약30초 “응용 프로그램을 닫는 중”→롤백→설치기 exit5. 180초 관찰 종료 시1.1.2 유지, 새DQA프로세스0.
- 같은 설치기에 /LOG,/LOGCLOSEAPPLICATIONS만 추가한 별도 진단 실행에서도exit5. 이 별도 실행을 사용자 메뉴 검증 성공으로 계산하지 않는다. 로그에서 suppressed Abort 확인.
- Restart Manager의 읽기 전용 조회로 설치본 runtime/python.exe PID48536만 잠금 소유자임을 확인했다. argv는 bridge_agent.py, 부모8988은 이미 종료.
- [실측 원본](artifacts/20260908-update-install/failed-1.2.0-install-result.json), [진단 로그](artifacts/20260908-update-install/failed-1.2.0-installer-diagnostic.log).
- 공식 계약: [Inno CloseApplications](https://jrsoftware.org/ishelp/topic_setup_closeapplications.htm), [필터](https://jrsoftware.org/ishelp/topic_setup_closeapplicationsfilter.htm), [RestartApplications 기본값](https://jrsoftware.org/ishelp/topic_setup_restartapplications.htm), [종료코드](https://jrsoftware.org/ishelp/topic_setupexitcodes.htm).

- 수정 후 코드 검증: native 전체527 PASS/1 skip(jsdom 경로 미지정), 기존 jsdom 경로를 명시한 해당 DOM 검사 재실행1 PASS로 총528개 검증 완료. Windows1.2.1 빌드 exit0 및 동결본 자가진단·동봉 런타임 import PASS.

## 2026-09-08 실제 업데이트 설치 — 1.2.1 PASS

- 기존1.1.2 고아PID48536을 남긴 상태에서 실제 메뉴로1.2.1 확인·수락. 실제 앱이 받은 설치기26,044,458bytes/공개SHA일치. 별도 설치기 수동 실행으로 대체하지 않았다.
- 14:09:42KST 수락 기준: 기존앱exit0 +5.102초, 고아종료 +35.116초, 새DQA실행 +40.578초, setup두프로세스exit0 +43.737초.
- registry1.2.1/동일 per-user설치경로/신앱1개/실제exeSHA/pending소거/applyok를 모두 만족한 뒤5.529초 유지, 총49.602초.
- 재시작된 실제 메뉴는 “이미 최신입니다 (버전1.2.1).”. 확인창을 닫고 앱 실행 유지. 관찰에 사용한 외부 Python도 종료되지 않았다. 설치로그는 등록파일3개·일반사용자권한·forcedshutdown·설치성공·Windows재부팅불필요를 입증했다.
- Windows RM 종료 대기 약30초는 유지됐다. 실제1.1.2→1.2.1 복구 성공이며 모든 Windows 환경/버전의 동작이나 픽셀 렌더 검증으로 확대하지 않는다.
- [요약 및 지문](artifacts/20260908-update-install/measurement-summary.json), [실제 설치 결과](artifacts/20260908-update-install/install-result.json), [전체 설치 로그](artifacts/20260908-update-install/installer.log.gz), [최신버전 대화상자](artifacts/20260908-update-install/latest-version-confirmation.json).

### Run 2026-09-09 — 무중단 설치와 다음 실행 적용
- 상세: [원장](test-runs.d/20260909-nondisruptive-update.md).
- Environment: CLI — native617 passed /1 skipped; focused112 passed.
- Environment: DQA-client — 격리 실제 설치본의 Windows 검증, 제어된 페이지·러너. 세부 결과는 원장을 따른다.

## 2026-09-10 — 투명 아이콘 1.3.1 검증

Environment: DQA-client
Result: PASS
Scenario: 실제 Windows동결본/격리설치본의 아이콘·업데이트·실패보존·바로가기·제거. native624/웹30/노트34도PASS. 실제사용자계정/유료AI는검증대상이아니다. [정본](test-runs.d/20260910-transparent-icon-release.md). PR1617병합·채널/웹배포는다음단계다.
