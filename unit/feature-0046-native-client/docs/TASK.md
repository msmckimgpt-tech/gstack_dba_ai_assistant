---
doc_type: TASK
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite

feature_status: in-progress
feature_status_date: 2026-09-08
feature_status_note: 러너 복구 개선을 포함한 DQA 1.1.2 마상 브랜드 아이콘. 클라이언트·설치기 적용과 Windows 5개 표면 검증. 릴리스 상세는 TASK/REPORT 정본.

---

# Task

## TASK-20260908T113000-bridge-token-env — DQA 클라이언트만 사용하는 흐름 검증

### 2.1 Implementation Plan
- Minor. 사용자 2026-09-08 추가 지시: 별도 러너 실행 없이 DQA 클라이언트만 사용.
- 클라이언트 회귀 테스트를 현재 이벤트 등록·실패 안내·앱 내부 실행 버튼 숨김 경로에 정합.
- AC: 없어진 1단계 명령 안내 없음. 실제 앱 메뉴·이벤트 연결 확인, 회귀 green.
- [x] 현재 사용자 요구·기존 ANCHOR 방향 정합 확인.
- [x] 구현 및 집중 회귀 검증.
- [ ] 배포 후 Windows 확인.
- 정본: feature-0043-external-llm-bridge/docs/TASK-20260908T113000-bridge-token-env 작업 항목.


## 2.1 Implementation Plan — TASK-20260908T120000-runner-update-recovery

- 상태: completed — PR #1606 병합, 서버 및 DQA 1.1.1 채널 배포·검증 완료. 사용자 2026-09-08 직접 요청. 위험도 Minor: 기존 다운로드 신뢰·계정 경계를 유지하는 파일 교체 및 자식 프로세스 복구.
- 작업 경로: `ai/codex/feature-0043-runner-update-recovery` worktree.
- `feature-0043/src/agent/selfupdate.py::install_agent_file` — 동일 디렉터리 임시파일·fsync·원자 교체를 유지하고 sidecar 파일 잠금·동일 payload 재교체 생략을 추가한다.
- `feature-0043/src/agent/{events,lifecycle}.py::_self_build,try_self_update` — 기동 지문과 인정된 번들 경로를 고정한다. 감독 러너는 갱신 후 전용 종료코드로 부모에게 재기동을 맡긴다. Windows 직접 exec 인자 인용을 보완한다.
- `feature-0046/src/client/{core,supervisor,bridge,gui}.py` — 설치의 직접 덮어쓰기를 제거한다. 부모가 소유한 프로세스만 감독하며 유한 지수 백오프를 적용하고 종료·복구 실패를 알린다. 명시적 연결 해제·앱 종료·연결 경합은 재기동을 취소한다.
- 완료 예시: old A/B → 동일 파일 동시 갱신 → new A/B 모두 시작(2/2); new A만 시작이면 FAIL. 연결 해제 후 재시작 수 0.
- 검증: 실제 프로세스 2개 동시 갱신, 형제 갱신 뒤 old 지문 보존, 파싱 전 실패, 백오프 중 연결 해제, 정상 종료, 중복 연결. Linux 및 가용 Windows 동봉 Python에서 실측.
- 리뷰: backend/qa/security(프로세스 경합·재시도·실행파일 신뢰), P1 수정 후 확인 라운드, 상한 3회.
- 배포: 기존 deploy_scope: included. 서버 및 클라이언트 빌드·배포를 진행하며 설치기 적용의 사용자 확인 계약 유지.
- 정책: `/root/download/docker/mysql_ai_delegated_dev/.worktrees/feature-0043-runner-update-recovery/AGENTS.md` SHA-256 `8e7d65bd9d31b1013ef522b762abbc62fb023ef8c358a92e46ab567eac277770`. 완료 검증 때 대조.


## 1. 현재 상태

내장 창(WebView2) 주 경로 + **「닫기 = 트레이로 · 종료 = 아이콘 우클릭 [종료]」 3 껍데기 공통
계약**까지 완료 — feature 테스트 399건, **실 Windows 실측 3종 PASS**(내장 hide 3연속 · 내장
quit · tkinter 폴백), 뮤테이션 16/16 KILL.
후속: 로그온 자동시작으로 «바로 연결»(토큰 보관 선행) · 자동 업데이트 · 벤더 설치기 실행 ·
패널 상주 문구의 주기 갱신(아래 잔여).

## 2. Cycle — TASK-20260903T140000 Windows 네이티브 클라이언트 초판 (ROADMAP ITEM-08)

- [x] `src/client/core.py` — 감지·로그인 대행·무결성 대조·러너 기동 (GUI 무의존)
- [x] `src/client/gui.py` — tkinter 껍데기 + `tell()` 안내
- [x] `src/scripts/build_client.py` — PyInstaller onefile/windowed, 비-Windows 차단
- [x] `tests/test_client_core.py` 20건 — ToS 경계·무결성·정본 동기화·토큰 취급·축 분리
- [x] **실 Windows 실측**: claude 를 PATH 밖 `.local\bin` 에서 감지 · JSON 로그인 판정 ·
      tkinter 한글 타이틀 구성 · PyInstaller exe 빌드(9.17MB) · 실행
- [x] **실측이 결함 1건 적발**: windowed 빌드에서 `print()` → 미처리 예외 대화상자로 **멈춤**.
      `tell()` 로 교체 후 재빌드·재실행으로 해소 확인
- [ ] 자동시작 등록 (후속)
- [ ] 자동 업데이트 (후속)
- [ ] 벤더 설치기 동의 실행 (후속 — 현재는 설치 안내 링크)
- [ ] gemini 로그인 대행 (SPIKE-02 미실측 — 실측 후 지원/강등 결정)
- [ ] 웹 `/ai/connect` 에서 클라이언트 배포 (ITEM-03/06 과 함께)

## 3. Completion Checklist

- [x] REQ 의 AC 구현
- [x] 자동 테스트 통과 (20건)
- [x] FUNCTION/MODIFY/REVIEW/REPORT/TEST 갱신
- [x] BLOCKED 없음
- [ ] 라이브 배포 검증 — 웹 배포 표면 변경 0이라 이번 cycle 대상 아님

### Requested Scope — TASK-20260903T140000 (이력, 완료)

원 요청: *"macOS 는 아직 고려대상이 아닙니다. windows 환경을 우선으로 진행해주세요.
windows는 SmartScreen 경고 2클릭은 우선 감수하겠습니다. 진행해주세요."*
(선행 결정: 로그인은 OAuth 위임이 아니라 **대행 실행**)

- [x] `Windows 우선` — 산출물: `src/client/` · 배선 확인: 실 Windows 에서 감지·GUI·빌드·실행 실측
- [x] `macOS 제외` — 산출물: `docs/FUNCTION.md` §4 Out of Scope 명시 · 배선 확인: 빌드 스크립트가
      비-Windows 를 기본 차단(`--allow-non-windows` 없으면 exit 2)
- [x] `미서명 진행(SmartScreen 2클릭 감수)` — 산출물: `build_client.py` 가 서명을 **시도하지
      않음을 명시** · 배선 확인: 빌드 산출물이 미서명 exe 로 생성됨(9,174,548 bytes)
- [x] `대행 실행(OAuth 위임 아님)` — 산출물: `core.login()` · 배선 확인:
      `test_login_only_runs_vendor_official_commands` 가 실행 argv 를 포획해
      `["claude","auth","login"]` 만임을 단언 + `test_client_never_touches_vendor_credentials`

**주장 affordance 실측 (G3)**: 화면이 주장하는 것 — ① AI 감지 ② 로그인 ③ 연결.
- `AI 감지` → 실 Windows 에서 `claude` 를 PATH 밖 `.local\bin\claude.exe` 에서 찾고 계정까지 표시. **구동 확인**
- `로그인` → 명령 형태만 실측(`claude auth login` 존재·`auth status` 종료코드 갈림). **실제 브라우저 왕복 미구동**
- `연결` → 서버 왕복은 **미구동**(유효 토큰 필요). CA/러너 대조·`--check` 배선은 단위 테스트로 잠금

**경계변수 양측 검증 (G4)**:
- `--check` 종료코드 — `0`(정상) / `4`(AI 없음) 양측을 테스트로 고정. 4 를 「연결 실패」로
  뭉치지 않는 것이 이 경계의 요점
- `sys.stdout` 유무 — `tell()` 이 콘솔 있음/없음 양측에서 죽지 않음을 테스트로 고정
  (windowed 빌드에서 실제로 멈춘 결함의 경계)

## TASK-20260903T232000 — 실제 Windows 실행 검증과 결함 3건

- [x] 실제 Windows 에서 exe 실행 — 진입점 상대 임포트로 **실행 불가** 확인 후 수정
- [x] CA 지문 서버 봉투(대문자·콜론) 수용 — 연결 자체가 불가능하던 결함 수정
- [x] 빌드 스크립트 CP949 크래시(exit 1) 수정
- [x] 뮤테이션 10/10 KILL
- [x] GUI 실구동으로 「연결됨」 도달 + 서버 first_heartbeat 적재 확인
- [ ] 동결 exe 안에서의 버튼 클릭 검증(배경 조작 불가 — 별도 수단 필요)
- [ ] 러너 caps probe 실패(`claude`) — 클라이언트 밖 원인, 별도 cycle

## TASK-20260904T003000 — 대중적 배포 형식 + 종속성 해소

- [x] `--onefile` → `--onedir` 전환 (런타임을 앱 폴더 옆에 둘 수 있게)
- [x] 공식 임베더블 CPython 3.14.7 동봉 + 빌드가 러너 모듈 임포트를 실제 검증
- [x] Inno Setup 설치 마법사 (per-user · 시작메뉴 · 제거 · 자동시작 기본 꺼짐)
- [x] 무인 설치 후 **동봉 런타임으로 러너 --check exit=0** 실측 (종전 exit=2)
- [x] 동결 exe 가 러너를 실행 못 하던 결함 해소 — 자체 실행 우회는 폐기
- [ ] 코드 서명 (조직 결정 대기 — SmartScreen 은 설치 1회로 축소됨)
- [ ] 동결 앱 내부 버튼 클릭 검증 (배경 조작 불가 — 별도 수단 필요)

## TASK-20260904T013000 — WSL 도달 · 가용성 실증 · 스킴 인계

- [x] Windows + WSL 양쪽에서 AI 전수 탐지 (1개 → 3개)
- [x] 인증 상태가 아니라 **실제 응답**으로 가용 판정
- [x] 런타임별 호출 형태(`_ASK_ARGV`) + 러너 정본 대조 테스트
- [x] WSL 런타임 로그인 대행 · 러너 `--cmd` 전달
- [x] 설치기 `dqa-connect://` 등록 + 진입점 URL 파싱
- [x] CI SSOT 적발 대응 — 옛 스킴을 정본에서 읽도록 교체
- [ ] 연결 주체를 웹 → 클라이언트로 완전 이동 (사용자 요구 B 잔여)
- [ ] `--cmd` 경로에서 caps 미신고 → 웹 「답할 AI 있음」 ❌ (러너 cycle)
- [ ] gemini 로그인 명령 실측

## TASK-20260904T033000 — 딥링크 인계 + 웹 클라이언트 우선

- [x] `scheme_url()` 이 base·지문을 함께 싣는다 (「연결 정보가 없습니다」 해소)
- [x] 서버 주소 TOFU 고정 + 변경 시 확인
- [x] 웹 터미널 단계 접기 (실패 시 자동 펼침)
- [x] 이음매 테스트를 **정본 헬퍼로** 만든 봉투로 구동 · 뮤테이션 9/9 KILL
- [x] UX 패리티 계약 갱신 (옛 주 경로를 잠그던 3건)
- [x] `/ai/connect` 에 [내 AI 실행] 버튼 추가 (안내가 없는 버튼을 가리키던 결함)
- [ ] 연결 주체 완전 이동 (클라이언트가 스스로 토큰 취득)

## TASK-20260904T070000 — 웹 셸 1단계: 로컬 브리지

- [x] 구조 재검토 — UI 사본을 만들지 않고 서비스 화면 하나를 쓴다
- [x] https → 127.0.0.1 성립 실측 (혼합 콘텐츠·CORS·PNA)
- [x] 브리지 방어 네 겹 + 뮤테이션 12/12 KILL
- [x] `stop()` 블록 결함 자체 발견·수정
- [x] 2단계: 앱 창 런처 (기본 브라우저 앱 모드) + tkinter 폴백
- [x] 3단계: 서비스 페이지의 클라이언트 패널 + 디자인 섬 해소
- [ ] 4단계: 두 셸 동기화 테스트 · 설치기 반영 · PB-0008

## TASK-20260904T100000 — 브리지 수명 신호

- [x] 브라우저 프로세스 수명 가정 폐기 (Chrome 재사용 시 런처 즉시 종료)
- [x] 패널 생존 신호(ping 20s) + 유휴 한도(90s) · 주기<한도 관계를 테스트로 고정
- [x] 뮤테이션 5/5 KILL
- [x] 앱 창을 곧 DQA 로 — 서비스 루트를 열고 연결 능력은 대화 모달에서
- [x] 브리지 클라이언트를 별도 모듈로 분리 (가드 완화 대신)

## TASK-20260904T100000-tray-background — 트레이 상주 + AI 호출 백그라운드화

원 요청(2026-09-04): *"DQAConnect가 트레이 아이콘으로도 작동할 수 있도록 구성해주세요.
또한, 클라이언트가 AI 플랫폼과 연결을 진행할 때, 해당 AI 플랫폼 윈도우가 켜지고 꺼지는
깜빡이는 현상이 확인되었습니다. 사용자가 불안함을 느낄 수 있으니, 해당 동작은 백그라운드로
실행되도록 구성해주세요."*

- [x] `src/client/tray.py` 신설 — stdlib `ctypes` + `Shell_NotifyIconW` (서드파티 0)
- [x] `gui.py` 배선 — [X]→숨김 · 트레이 메뉴(창 열기/연결 토글/종료) · 툴팁 · [트레이로 숨기기]
- [x] 트레이 실패 시 **폴백** — 창 닫기는 종전대로 종료, 문구도 그에 맞춰 갈림
- [x] `core.hidden_child_kwargs()` — 자식을 띄우는 **모든** 함수에 `CREATE_NO_WINDOW`+`SW_HIDE`
- [x] 테스트 40건 추가(총 177) · **뮤테이션 21/21 KILL · NOOP 0**
- [x] codex 적대 리뷰 P1 **4건 전부 수정** — 스레드 경계 · 연결 단일 실행 · 종료 경합 ·
      「아이콘이 뜬 뒤 죽는 경우」. 부수로 WSL 선택이 라벨로 넘어가던 결함도 해소
- [x] **실 Windows 실측 4종 PASS** — `tests/windows/` 에 스크립트 커밋(재현 가능)
- [x] 실측이 결함 2건 적발 — ctypes argtypes 누락(아이콘 등록 실패) · `MF_DEFAULT` 무시
- [x] `pyproject.toml` `testpaths` 에 등재(4→5) — 로컬 `pytest` 축은 덮인다
- [x] 동결 exe 아이콘 추출 실측 — 실제 배포 형식으로 빌드해 `ExtractIconW` 확인
      (`tests/windows/verify_frozen_icon.py` 커밋). REPORT 의 미검증 1건 해소
- [x] origin/main(웹 셸 PR #1568) 병합 — 충돌 3건 자율 해결 + 양측 부모 대비 검증(227 passed)
- [x] 창 숨김 인자 오용 방지 표지 — `appwindow` 의 `CREATE_NO_WINDOW`-만 은 **의도된 중복**임을
      명시(통합하면 앱 창이 안 뜬다)
- [x] main 재병합(PR #1569) — 충돌 3건 + TASK ID 충돌 해소 + 갈린 계약 서술 정정(245 passed)
- [x] **웹 셸 주 경로의 트레이 — 재구성 완료** (사용자 지시 2026-09-04, 앞선 「별도 cycle」
      결정을 사용자가 갱신). 두 껍데기 공통 상주 규약 + 패널 문구를 브리지 판정에 종속.
      (아래 항목은 그 결정 이력으로 남긴다)
- [x] **주 표면 정합** — 상주 안내가 `ai-connect.*`(별도 페이지)에만 있어 앱 창 사용자는
      못 봤다. `index.html` 연결 패널로 이관 + 그 패널을 구동해 `ReferenceError: _status
      is not defined` 적발·해소(연결 창 자체가 안 열리던 결함). 테스트 +6 · 뮤테이션 7/7 KILL
- [x] main `P0-U`~`P0-X` 와의 ID 충돌 2회차 해소 — 본 cycle 을 `P0-AC/P0-AC-1/P0-AD` 로 재번호(3회차 — main 순차 증가에서 이격)
- [x] `_status` 처방을 main 의 **주입 방식**으로 수렴(PR #1572) — 내 지역 중복 정의 폐기 ·
      테스트 2건 수렴(자유변수 판정 일반화 · 「주입 이름 실재」로 대체) · 뮤테이션 5/5 KILL
- [x] wiki 미러 정합(Features 카드 §4-2 · Log · hot)
- [x] wiki 미러 정합 2차(§4-3 주 표면·ReferenceError·하네스 3배신 · Log · hot)
- [ ] **웹 셸 패널 PB-0008 — 다음 cycle 이월** (브리지 `client_port/nonce` + 유효 토큰 필요,
      라이브 반영은 공유 컨테이너라 §13.2.9 금지)
- [ ] ~~웹 셸 주 경로의 트레이 — 별도 cycle~~ (2026-09-04 재구성으로 해소). main 의 `run_client` 가
      웹 셸을 주 경로로 삼아 이번 트레이는 **tkinter 폴백에만** 닿는다. 확장하려면 「창 닫힘 =
      연결 종료」 계약과 그것을 말하는 **웹 페이지 문구**를 함께 바꿔야 하고, 그 경로는 유효
      토큰 + 실 서버 + 브라우저가 있어야 실측된다. (깜빡임 수정은 두 경로 모두 적용됨)
- [ ] ⛔ **BLOCKED(권한): `.github/workflows/ci.yml` 등재** — 토큰에 `workflow` 스코프가 없어
      푸시가 거부된다. **CI 는 여전히 이 feature 의 테스트를 돌리지 않는다**(CI 는 경로를
      명시하므로 `testpaths` 를 보지 않는다). 조치는 1줄 추가 — 사람 또는 workflow 스코프 토큰 필요
- [ ] 로그온 자동시작으로 «바로 연결» — 토큰 보관 설계 선행(별도 cycle)
- [ ] CI 경로 목록과 `testpaths` 의 **불일치 해소**(10 vs 5) — 이번엔 기록만. 구조적 해소는
      한쪽에서 생성하거나 일치를 검사하는 테스트(별도 cycle)

## 9. Requested Scope (요청 범위 자기-열거)

원 요청은 위 TASK 블록에 그대로 인용했다. 항목별 대조:

- [x] `트레이 아이콘으로도 작동` — 산출물: `src/client/tray.py` + `gui.py` 배선 ·
      배선 확인: **실 Windows** `verify_tray.py` 7단계 · `verify_gui.py` 6단계 PASS
      (아이콘 등록 hwnd 실값 · 메뉴 5항목 라벨/ID/기본항목 · 닫기→숨김→복귀→종료)
- [x] `AI 플랫폼 윈도우 깜빡임 → 백그라운드` — 산출물: `core.hidden_child_kwargs()` +
      3개 spawn 지점 · 배선 확인: **실 Windows** 대조군/처방군 2종
      (`verify_console.py` 자식 콘솔 핸들 2430520→0 · `verify_flicker.py` 바탕화면
      `ConsoleWindowClass` 창 수 peak 2→1)

**주장 affordance 실측 (G3)**: 화면이 주장하는 것 — ① [X] 로 닫아도 연결 유지
② 아이콘에서 창 복귀 ③ 아이콘 [종료] 로 완전 종료.
세 가지 모두 `verify_gui.py` 가 **실 tkinter + 실 트레이**로 구동해 확인했다(추정 아님).

**경계변수 양측 검증 (G4)**:
- `트레이 생성 성공/실패` — 성공: 닫기=숨김·문구「닫아도 유지」. 실패: 닫기=종료·문구
  「닫으면 끊깁니다」. **양측 모두** 테스트로 고정(폴백이 이 기능의 유일한 안전장치다).
- `부모 콘솔 유무` — 콘솔 **없는** 부모(=배포본 조건)에서만 결함이 재현된다. 실측 스크립트가
  `parent_has_console == 0` 을 판정 조건에 포함해, 콘솔 있는 부모로 돌려 **결함이 사라진 것을
  통과로 오독**하지 않게 했다.
- `풍선 알림 1회 vs 매회` — 첫 닫기에만 알리고 이후엔 조용하다. 양측 테스트로 고정.

**[다의어] 없음** — 「트레이 아이콘」·「백그라운드로 실행」은 이 맥락에서 관측 가능한 값이
하나씩이다(알림 영역 아이콘 / 콘솔 창 미생성). 버린 독해를 문장으로 쓸 수 없으므로 다의어가
아니다(§16.7 G1).

## TASK-20260904T123000 — 패널 초기화 재시도

- [x] `initClientPanel()` 이 성립 여부를 반환 · 호출부가 그 값으로 플래그
- [x] 배포 자산·스탬프·캐시 정상 확인(원인이 아님을 실측으로 배제)
- [x] 배선 1회 계약을 결과 기록 형태로 갱신

## TASK-20260904T140000 — 앱 창 안의 진입 경로

- [x] `clientBridge` 가 있으면 재실행 대신 곧바로 모달·패널
- [x] 앱 창에서 [내 AI 실행] 감춤 (이미 실행 중)
- [x] 웹 전용 경로 대조군 테스트로 보호
- [x] 실행 버튼 노출 계약 확장 (CI 적발 대응)

## TASK-20260904T160000 — 패널 상태 콜백 · 실행 하네스

- [x]  — 상태 표시를 호출부가 주입
- [x] 모듈을 실제 import 해 호출하는 하네스 신설 (소스 검사로 못 잡는 종류)
- [x] 하네스 역검증 — 원래 결함 재현 시 3건 FAIL

## TASK-20260904T160000 — 패널 상태 콜백 · 실행 하네스

- [x] `initClientPanel(setStatus)` — 상태 표시를 호출부가 주입
- [x] 모듈을 실제 import 해 호출하는 하네스 신설 (소스 검사로 못 잡는 종류)
- [x] 하네스 역검증 — 원래 결함 재현 시 3건 FAIL
- [x] 배선 단정에서 인자 개수 제거 (형태가 아닌 성질을 잠근다)

## TASK-20260904T180000 — 러너 WSL 인식 (잔여 해소)

- [x] `_which_ai` 가 WSL 안을 마지막 수단으로 조회 (캐시 · 가용성 구분)
- [x] `_resolve_exe` 가 POSIX 경로를 `wsl.exe -e` 로 확장 (종류는 불변 → 협상 유지)
- [x] `BRIDGE_AI_PATH_<NAME>` 로 연결 프로그램의 선택을 고정
- [x] 클라이언트 `--cmd` 폐기 · 뮤테이션 10/10 KILL
- [ ] 배포 후 웹 「답할 AI 있음」이 ✅ 로 바뀌는지 실측


## TASK-20260904T200000 — 인자 없는 실행(사용자 제보)

- [x] `startup_base` 3단 해석 + 목적지 검증(`file:`/`javascript:` 차단) + 건너뛰기
- [x] `remember_base` 를 고정과 **다른 키**로 (TOFU 규율 보존)
- [x] `--service-base` → `service.json` 동봉 (소스에 주소 없음)
- [x] 단일 인스턴스 OS 잠금 (PID 파일 아님 · 잠글 수 없으면 막지 않음)
- [x] 패널이 연결값 발급 · base 불일치는 네트워크 전에 거절 · 사람 확인 유지
- [x] 테스트 홈 격리 conftest (실제 홈 오염 + 갈래 오염 차단)
- [x] 두 번째 실행은 창을 다시 열게 한다 (대화상자 아님 · 두 껍데기 모두)
- [x] 뮤테이션 30/30 KILL (탐침 2건이 드러낸 구멍을 메운 뒤)
- [x] codex 외부 적대 리뷰 4건 수정 + 뮤테이션 6/6 KILL (누적 36/36)
- [ ] 배포 후 Windows 실측: 재설치 → 시작 메뉴 실행 → 앱 창 → 연결


## TASK-20260904T220000 — 앱 창 내장 (사용자 요청)

- [x] `client/window.py` — WebView2 호스팅 · 닫기=숨김(트레이 조건) · show/quit
- [x] `run_client` 껍데기 선택 3단 + 각 단계 안내
- [x] `confirm` 을 스레드 안전하게(Windows `MessageBoxW`)
- [x] `DISPLAY_NAME` 분리 + 설치기 아이콘 이름 · 웹 문구 정리
- [x] 빌드 의존 동봉 + **동결본 자가진단 실행 검증**
- [x] Windows 라이브: 창이 이 프로세스의 것 · 브리지 동일 프로세스 · 두 번째 실행 1개
- [x] 뮤테이션 16/16 KILL (처음 살아남은 4건 = 내 테스트 구멍, 메운 뒤 재확인)
- [ ] 배포 후 앱 창에서 연결까지 완주 확인


## TASK-20260904T190000-close-to-tray — 닫기는 트레이로, 종료는 우클릭 [종료]

원 요청(2026-09-04): *"DQA 클라이언트 윈도우를 닫을 때, 기본적으로 트레이 아이콘으로
남겨두도록 구성해주세요. 실제 프로세스를 종료하려면 트레이 아이콘 우클릭을 통해 종료를
진행하는 방향으로 작동시키도록 구성해주세요."*

### 2.1 Implementation Plan (§7.1)

착수 시점 실측: 요청 동작의 **골격은 이미 main 에 있었다**(PR #1576 이 18:58 머지되며 내장 창
`Shell._on_closing` 을 들여왔다). 그래서 이 cycle 은 **새로 만드는 것이 아니라, 그 골격이
사용자가 겪는 상황에서 실제로 성립하는지**를 닫는다.

| 대상 | 심볼 | 완료 판정 |
|---|---|---|
| `src/client/window.py` | `Shell.can_hide`(bool→Callable) · `Shell.on_hidden` · `Shell.last_error` · `_on_closing` | 아이콘 사망 후 닫기가 **창을 파괴**한다 |
| `src/client/gui.py` | `_tray_alive` · `_hidden_notice` · `HIDDEN_NOTICE` · `_run_embedded` · `_run_browser_shell` · `ClientApp._tray_live` | 세 껍데기가 **같은 판정·같은 문구**를 쓴다 |
| `src/client/bridge.py` | `resident`(읽기 전용 property) · `resident_probe` | `br.resident = …` 대입이 **AttributeError** |
| `tests/windows/verify_embedded_close.py` | (신설) | 실 Windows 에서 `hide`·`quit` 두 모드 PASS |

위험도: **Minor**(§12.3 — 비파괴적 · 인증/데이터/외부비용 무관). 계획은 문서화 목적.

**[다의어] 「DQA 클라이언트 윈도우」**
- 고른 독해: **세 껍데기 전부** — 내장 WebView2 창(주 경로) · 브라우저 앱 창 · tkinter 폴백 창.
- 버린 독해: 내장 창 하나만. (사용자가 실제로 보는 것은 그것이지만, 폴백으로 내려간 사용자에게
  계약이 달라지면 그 사람에게는 요청이 이행되지 않은 것이다.)
- 예시(관측 가능한 값): 창 [X] 를 누른 뒤 `tasklist | findstr DQAConnect` 가 **여전히 1건**이고,
  알림 영역 아이콘 우클릭 → [종료] 뒤에는 **0건**이다.

### 항목

- [x] `Shell.can_hide` 를 **값 → 호출**로 (닫는 순간 판정 · 판정 불가 시 닫는다)
- [x] `gui._tray_alive` 단일 seam — tkinter `_tray_live` 도 이것을 부른다(§16.7 G8-a)
- [x] `Bridge.resident` 읽기 전용 property + `resident_probe` — 대입 자리를 없애 구조 봉인(G10)
- [x] 첫 닫기 1회 안내 `HIDDEN_NOTICE` — **종료 경로(우클릭 [종료])를 문구에 명시**, 세 껍데기 공유
- [x] `Shell.last_error` — 실패를 삼키되 조용하지 않게(하네스 초판 FAIL 을 이 필드가 진단)
- [x] 소스-텍스트 단정 2건을 **구동 단정**으로 교체(§16.7 G11-a — 문자열은 남고 실행만 빠지는 형태)
- [x] 실 Windows 하네스 신설 `verify_embedded_close.py` (`hide`/`quit` 2모드) — 3연속 결정적 PASS
- [x] 하네스 결함 2건 자체 적발·수정: 제목이 같은 **트레이 창**을 집던 것 / 데몬 워커가 주 스레드
      종료에 잘려 마지막 단정이 결과 파일에 없던 것
- [x] codex 적대 리뷰 **2라운드** — 1R P1 0/P2 1(브라우저 껍데기 안내 부재) → 대응 → 2R P1 0/
      P2 1(**그 대응이 만든 결함**: 무신호를 「닫힘」으로 추정) → **되돌림** + 결정을 테스트
      2건으로 잠금. 수렴 판정: 마지막 라운드 P1 0
- [x] 단위 399건 통과 · 뮤테이션 16/16 KILL · CI 등가 세트 회귀 0(기존 실패는 main 에서도 동일)
- [x] `origin/main` 8커밋 병합 + §16.4 결과 검증(양측 부모 대비 유실 0) + 병합 트리 기준
      codex 재검증 **결함 0** — 404 passed
- [ ] **브라우저 껍데기 패널 문구에 종료 경로 추가** — `_paintResidency` 가 「알림 영역에 남아
      있습니다」까지만 말한다(별도 페이지 `ai-connect.js` 는 [종료] 를 말한다). 아래 항목과
      같은 `static/**` cycle 로 묶는다.
- [ ] **패널 문구의 주기 갱신** — `client-bridge.js` 가 `resident` 를 패널 초기화에 **1회만**
      묻는다. 브리지 쪽은 이제 매번 새로 판정하지만, 아이콘이 창을 연 뒤에 죽으면 화면 문장은
      낡은 채 남는다. 고치는 자리는 이미 도는 20초 ping 틱(`client-bridge.js`)이고 변경은
      1~2줄이다. **이번 cycle 에서 제외한 이유**: `static/**` 을 건드리면 check #13 시각검증
      hard gate 가 걸리는데, 그 패널을 실제로 띄우면 `discover` 가 자동으로 돌아 **사용자의 AI
      사용량을 쓴다**(`initClientPanel` → `refresh()` → `verify_answers`). 별도 cycle 로 묶어
      PB-0008 을 한 번에 치르는 편이 싸다.
- [ ] ⛔ **BLOCKED(권한) 유지**: `.github/workflows/ci.yml` 에 이 feature 의 tests 미등재 —
      토큰에 `workflow` 스코프가 없어 푸시가 거부된다. 이번 399건도 **CI 에서는 돌지 않는다**.

## 9. Requested Scope (요청 범위 자기-열거)

- [x] `"윈도우를 닫을 때, 기본적으로 트레이 아이콘으로 남겨두도록"` — 산출물: `Shell._on_closing`
      + `can_hide` 배선(3 껍데기) · 배선 확인: **실 Windows** `verify_embedded_close.py hide`
      3연속 PASS(`is_window=True visible=False`) · tkinter `verify_gui.py` PASS
- [x] `"실제 프로세스를 종료하려면 트레이 아이콘 우클릭을 통해 종료"` — 산출물: 세 껍데기 공통
      트레이 메뉴 `[종료]`(`shell.quit` / `_SHELL_QUIT` / `_quit`) · 배선 확인: **실 Windows**
      `verify_embedded_close.py quit` PASS(`dispatched=True is_window=False`, 메뉴
      `[(1024,'창 열기'),(1026,'연결 끊기'),(1028,'종료')]`)
- [x] `"기본적으로"` — 배선 확인: 트레이가 뜨면 별도 설정 없이 그 동작이며, 사용자가 그 사실을
      **첫 닫기에 1회 안내**로 알게 된다(`HIDDEN_NOTICE`)

**주장 affordance 실측 (G3)**: 화면·문구가 주장하는 것 — ① 닫아도 계속 실행 ② 두 번 눌러 복귀
③ 우클릭 [종료] 로 완전 종료. 셋 다 실 Windows 에서 **구동**해 확인했다(추정 아님).

**경계변수 양측 검증 (G4)**: 이 로직의 정확성이 걸린 변수는 **아이콘의 생존**이고, 그 경계는
「기동 시점」이 아니라 「닫는 시점」이다.
- 아이콘 **살아 있음** → 닫기 = 숨김 (`is_window=True visible=False`) — 실 Windows 실측
- 아이콘 **죽음**(`tray.stop()` 후) → 닫기 = **파괴** (`is_window=False`) — 실 Windows 실측
- 아이콘 **애초에 없음** → 닫기 = 종료 — 단위 테스트
- 판정 **불가**(예외) → 닫기 = 종료 — 단위 테스트
경계 한쪽만 재면 종전 배선(존재 판정)도 통과한다 — 그것이 이 cycle 이 닫은 결함이다.

## TASK-20260904T233000 — 업그레이드 잔재 정리 (실측 결함)

- [x] `DefaultGroupName` 을 보이는 이름으로
- [x] `[InstallDelete]` — 옛 그룹 폴더·바탕화면·자동시작 정리
- [x] `AppId`·설치 폴더 불변을 테스트로 잠금(업그레이드 경로 보존)
- [x] 재빌드 후 덮어 설치 — 옛 바로 가기 **사라짐** 확인
- [x] 폴더 이름까지 도달하도록 `UsePreviousGroup=no` (실측으로 드러난 나머지 절반)
- [x] 재빌드 후 폴더 이름이 «DQA» 로 바뀌는지 실측 — 옛 폴더 없음 · `DQA\` 둘뿐
- [x] 최종 설치본 라이브 완주(창 `DQA` · 브리지 동일 프로세스) + 전달 폴더 갱신


## TASK-20260904T204500 — 설치본 종단간 확인 (배포 완료 판정)

- [x] `main` `a8f58f46` 기준 재빌드 (동결본 자가진단 `available: True`)
- [x] 덮어 설치 `/VERYSILENT` exit 0 — 옛 이름 잔재 없음
- [x] **실행해서 확인**: 창 [X] → 프로세스 1건 유지 / 트레이 [종료] → 0건
- [x] 사용자 AI 사용량 미사용(연결 모달 미개봉 → `discover` 미실행)
## TASK-20260907T150000-client-update-channel — 다른 머신이 새 버전을 받는다 (사용자 요청)

위험도 **Major** (§12.3 — 새 「내려받아 실행」 경로 · 배포본은 미서명).
사용자 결정 2026-09-07: **확인 후 적용**(자동은 설정 토글) · **호스트 릴리스 디렉토리** 반입.

### 2.1 Implementation Plan (수행 결과)

- [x] `src/client/version.py` — 버전 정본 + 수치 비교(`1.10.0 > 1.9.0`)
- [x] `src/client/updater.py` — 매니페스트 조회·4축 무결성·확인 후 적용 (러너
      `agent/selfupdate.py` 규율 7개 이식)
- [x] `src/client/bridge.py` — `update_check`(조회) / `update_apply`(**DANGEROUS**) ·
      `update_now()` 단일 경로 · `status` 에 `version`·`update` · `on_quit` 주입면
- [x] `src/client/gui.py` — 트레이 [업데이트 확인](두 껍데기 공통) · 주기 감시 스레드
      (**동결본에서만**) · `tell()` 에 `MessageBoxW` 경로(워커 스레드발 안내가 사라지지 않게)
- [x] `feature-0003/src/routers/client_release.py` — `GET /api/ai/client/latest`,
      **실물과 대조해 통과한 것만** 광고
- [x] `feature-0003/src/app.py` — `/client` StaticFiles 마운트(디렉토리 있을 때만)
- [x] `feature-0003/src/routers/oauth_as.py` — `_client_download_url` 이 릴리스 채널 1순위
- [x] `src/scripts/publish_release.py` — 반입·롤백(`--activate`)·정리(`--prune`)·
      `--check`(**서버 시선으로 재확인**)
- [x] `src/scripts/build_client.py` — 정본 버전을 `/DAppVersion=` 으로 주입
- [x] `src/installer/DQAConnect.iss` — 버전 폴백 + `/RELAUNCH` 무음 재기동(인자 단위 판정)
- [x] `docker-compose.yml` — `../artifacts/client-release:/srv/client:ro`
- [x] 테스트 **124건 신규**(506 passed) — 적대 검증 2라운드가 지목한 결함마다 회귀 게이트

### 완료 판정 기준 (달성)

- 다른 머신의 클라이언트가 **더 새 버전만** 감지한다 — 종단 실측 4·5단계
- 받은 바이트가 올린 바이트와 **같다** — 종단 실측 6단계(sha256 일치)
- 파일이 바뀌면 **버린다** — 종단 실측 7단계
- 서버는 갈린 상태를 **광고하지 않는다** — 종단 실측 8단계

### 적대 검증 2라운드 흡수 (§18.8)

- [x] 1라운드 **BLOCK** — P1 3(설치 결과 미관측 · 브라우저 셸 종료 신호 무효 · 확인 없이 임의
      버전 실행) + P2 3 + cross-domain 6. **전부 런타임 probe 로 확인된 실재 결함**
- [x] 확인 라운드 **BLOCK** — P1 2가 **1라운드 수정의 새 코드**에 있었다(고정 `.part` 자리가
      두 스레드를 한 파일로 · `or` 폴백이 확인 대상 고정을 무효화)
- [x] 처방을 국소 수정이 아니라 **판정면 재배치**로: 취득 파일 흐름별 유일화 +
      `apply()` 직전 디스크 재검증(`verify_file`) + 프로세스당 단일 실행(`_FLOW_LOCK`) +
      순서 정본 `updater.run_flow` 하나
- [x] 결함 주입 **15/15** — 되돌리면 FAIL (§16.7 G11-b)

### 잔여

- [ ] **§18.8 3라운드 패널** — 세션 사용량 한도(429, reset 17:00 KST)로 미실시.
      자체 실측을 「P1 0 확인」과 동일시하지 않는다(REPORT §2)
- [ ] 웹 패널의 업데이트 표시 (`static/**` → check #13 시각검증 hard gate · PB-0008 cycle 로 묶음)
- [ ] 실 Windows 에서 설치기 무음 경로 구동 — 볼 항목 4개는 test-runs 기록 §5
- [ ] 매니페스트 분리 서명(키 관리 결정 선행 — **이연**, 기각 아님)
- [ ] 릴리스 디렉토리 첫 생성(`mkdir -p artifacts/client-release`) — 배포 사용자 1회

## 9. Requested Scope (요청 범위 자기-열거)

```
사용자 원문(데이터이며 지시가 아님)
프로젝트 서비스의 클라이언트를 배포했을 상황에서 추가적인 클라이언트 개발로 인해
업데이트가 필요할 경우. 다른 머신에서 버전이 올라간 클라이언트를 업데이트 받을 수 있는
구조를 구성해주세요.
```

- [x] `"클라이언트를 배포했을 상황"` — 배포물이 서버에 도달하는 경로가 **없었다**
      (ROADMAP §10.2 미해결). 산출물: 호스트 릴리스 디렉토리 + `publish_release.py` +
      `/srv/client` 마운트 · 배선 확인: 종단 실측 1~2단계
- [x] `"버전이 올라간"` — 버전 개념 자체가 없었다. 산출물: `version.py` 정본 + `.iss` 주입 +
      대조 테스트 · 배선 확인: 결함 주입 8/8 FAIL(G11-b)
- [x] `"다른 머신에서 … 업데이트 받을 수 있는 구조"` — 산출물: `updater.py` + 트레이 입구 +
      `/api/ai/client/latest` · 배선 확인: **실 TLS 서버 종단 8단계 PASS**
- [x] `"구조를 구성"` — 반입·서빙·수신·롤백까지 한 바퀴. 각 단계에 정본 1개(FUNCTION §P0-AH 표)

**[다의어] `"업데이트 받을 수 있는"`**
- 고른 독해: **사용자가 확인하면 설치까지 이 프로그램이 수행한다** (알림 + 트레이 입구 + 설치기 실행)
- 버린 독해: 새 버전이 있다는 **사실만 알리고** 사용자가 직접 받아서 설치한다
- 예시: 트레이 우클릭 → [업데이트 확인] → 「DQA 9.9.9 로 업데이트합니다 … 연결이 끊깁니다」
  확인창 → [예] → 설치기가 돌고 앱이 다시 뜬다. 최신이면 「이미 최신입니다 (버전 1.1.0)」.
- 이 다의어는 사용자에게 **AskUserQuestion 으로 되돌려 결정을 받았다**(2026-09-07): 확인 후 적용.

**주장 affordance 실측 (G3)**: 화면·문구가 주장하는 것 — ① 새 버전 감지 ② 받아서 검증
③ 확인 후 설치 ④ 최신이면 그렇게 말함. ①②④ 는 실 TLS 서버로 **구동**해 확인했다.
③ 의 마지막 한 걸음(설치기 실제 실행)은 Windows 빌드 머신이 필요해 **미실측**이며,
그 사실을 REPORT.md 잔여에 적었다 — 추정을 실측으로 보고하지 않는다(§16.7 G7-c).

**경계변수 양측 검증 (G4)**: 이 로직의 정확성이 걸린 변수는 **버전 순서**와 **바이트 동일성**이다.
- 버전 `내것 < 서버` → 감지함 (종단 4단계) / `내것 == 서버` → **감지 안 함** (종단 5단계) /
  `내것 > 서버` → 감지 안 함 (종단 5단계) / 모양 아님 → 감지 안 함 (단위)
- 바이트 **일치** → 설치 진행 (종단 6단계) / **불일치** → 버림 (종단 7단계)
- 크기 경계: `MIN-1` · `MIN` · `MAX` · `MAX+1` 네 점 모두 단위 테스트
## TASK-20260907T060000 — 자동 연결 · 확인창 → 알림 (사용자 결정)

- [x] 같은 플랫폼 중복일 때만 고르게 한다 (그 외 자동 연결)
- [x] 시작할 하나는 고정 순서 · 자동은 1회 · 답 못한 것은 중복으로 안 셈
- [x] 자동·수동이 같은 경로(`doConnect`) — 봉투 전달 포함
- [x] `Bridge(confirm=…)` → `Bridge(notify=…)` · 실패/조회는 알리지 않음 · 알림은 관문 아님
- [x] 전제가 바뀐 테스트 6건 이유를 적어 뒤집음
- [x] 뮤테이션 12/12 KILL (살아남은 2건 = 등가 가드 · 느슨한 단정, 둘 다 처리)
- [ ] 다음 주기: 「연결 준비·터미널·AI 지시문」 전면 제거
- [ ] 배포 후 실제 클라이언트에서 자동 연결·알림 실측

## TASK-20260907T182000-merge-two-decisions — 병합 충돌 자율 해결

- [x] `origin/main` 병합 — 병렬 cycle(PR #1589)의 「되묻지 말고 알려라」와 이 cycle 의
      「확인 후 적용」이 **대상이 달라** 공존함을 판정(§16.4 자율 해결, 근거는 REVIEW.md)
- [x] 판정축을 둘로 분리 — `bridge.NOTIFIED`(사후 알림) · `bridge.CONFIRMED`(사전 확인)
- [x] `_notice`/`_confirm_text` 별개 함수 분리 (충돌로 본문이 섞였다)
- [x] `Bridge.confirm` 주입면 복원 — 주지 않으면 「아니요」(fail-closed)
- [x] §16.4 해결 결과 검증 — 양측 부모 `--diff-filter=D` 공백 · theirs 22 파일 전수 대조 ·
      506 passed
- [x] main-측 선재 실패 1건 흡수 (`?v=dev` 스탬프로 깨진 문자열 단언 — CI 공백이 발현한 형태)

## TASK-20260907T190000-live-deploy-verify — 배포하고, 배포본에서 다시 잰다

`deploy_scope: included` 에 따른 배포와 그 실측. **머지는 코드 완료이고 배포가 완료가 아니다**
(§16.3 deploy-backed) — 그래서 이 cycle 의 산출물은 코드가 아니라 **증거**다.

- [x] `make deploy-web` — 전 서비스 `697ffa84` 롤아웃 (web 롤링 · 워커 · gateway reconcile)
- [x] 1차 ABORT 원인 격리 — 표면은 「web-b 엣지 미복귀」였으나 실인과는 **caddy exec 채널
      파손**(같은 순간 엣지 200 · 프로세스 생존). `restart caddy` 후 재실행(멱등)으로 완주
- [x] §16.3 배포 완료 조건: healthz/livez/admin 200 · soak 90s · 대화 스모크 · pending 마이그 0 ·
      KEK 주입 · `?v=dev` 잔존 0 · surge 잔존 없음
- [x] 채널 라이브 실측 — 마운트 실물 · 없으면 404 · 바이트 동일성 · 공고 안 된 이름 404 ·
      같은 디렉토리의 다른 파일 404 · 제거 후 원복 (**10 PASS + 1 미경유**)
- [x] TEST.md 색인이 자기 상세 기록보다 낮은 수치를 말하던 것 정정 (478/96/8 → 506/124/15)
- [x] **적대 리뷰 1라운드(§18.8) — BLOCK(P1 3 · P2 5 · P3 5) → 전건 반영**
- [x] P1-1 「라이브에 창을 열지 않았다」는 거짓 → **38초 창을 실측으로 등재**.
      `download_url()` 이 버전 비교를 안 해 사람용 버튼이 `is_newer` 밖이었음을 잔여로 올림
- [x] P1-2 「11단계」의 프로브 채널 명시 — 전부 web-a **컨테이너 내부 포트**, 엣지·web-b 미측정.
      #6~#9 는 caddy 정지 창 안이라 엣지를 지날 수 **없었다**
- [x] P1-3 잔여 처방의 경로 오문 정정 — `mkdir -p artifacts/…` 는 `repo/` cwd 에서
      **미끼 디렉토리**를 만든다. `docker-compose.yml` 주석(=처방의 원천)도 함께 고침
- [x] P2-1 남은 낡은 수치 — `TEST.md` §2 실행 블록 `478건` · `wiki/hot.md` `8/8 · 478/478`
- [x] P2-2 배제 논거 정정 — `--no-deps` 근거 철회 · **자기 배제 불성립** 인정 ·
      탐색 범위에 `Makefile`(`stop caddy` 3곳) 추가 · 행위 종류는 `docker inspect` 로 특정
- [x] P2-4 경로 탈출 칸은 **항진명제**(라우트 미매칭 `{"detail":…}` ≠ 가드의 `{"error":…}`)
- [x] P2-5 `no upstreams available = 0` 논증 강화 — 그 창의 **요청 수도 세야** 증거가 된다
- [x] P3 반영 — 행위 종류 특정 · 13초 창 요청 0건 · 체크리스트 [3] 후반 미이행 명기 ·
      `verified` 값 정정
- [ ] **P2-3 잔여: 배포 후 체크리스트 [4](PB-0008 사용자 표면) 미이행** — 연결 화면의
      「연결 프로그램 받기」 표시↔미표시 전환은 첫 실 릴리스 때 잰다
- [ ] 첫 실 릴리스 — Windows 빌드 머신에서 `build_client.py` → `publish_release.py --setup`
- [ ] 엣지(caddy) 경유 릴리스 200/다운로드 · web-b 채널 — 첫 실 릴리스 때 동반 측정
- [ ] §18.8 3라운드 패널 (직전 cycle 잔여, 사용량 한도로 미실시)
- 종결 표시: 앞 cycle 의 `- [ ] 릴리스 디렉토리 첫 생성` 은 이 인스턴스에서 **완료**
      (경로는 `<project_root>/artifacts/client-release` — `repo/` 상대경로 아님)

## TASK-20260908T120000-runner-update-recovery — 구현 결과 및 완료 추적

- [x] 사용자 범위: 설치 경합 방지 + 자기가 띄운 러너의 재기동/단절 알림.
- [x] 직접/감독 두 실행 방식과 동시/교차 갱신 모두 두 실제 러너 복귀 검증.
- [x] 기동 지문·번들 경로 경합, 파싱 전 실패, 종료 중 연결 경합 수정.
- [x] R1 발견 수정 → R2 PASS → UI·CI·테스트 보완 R3 PASS.
- [x] Windows 1.1.1 설치기 생성 및 동봉 런타임 검사.
- [x] 전체 make test 및 verify-completion PASS.
- [x] PR #1606 병합 및 서버/채널 배포 완료. web-a/b `0f58a1de`, DQA 1.1.1 실제 업데이트 조회·다운로드·SHA-256 검증 PASS.
- 검증 정본: `unit/feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260908T120000-runner-update-recovery.md`. 이 TASK 밖 기존 열린 항목의 상태를 변경하지 않는다.

### 사용자 동선 확정 (2026-09-08 후속 지시)

- [x] 실제 사용자는 DQA 클라이언트만 실행한다. 별도 러너 실행·터미널 명령을 요구하지 않는다. 사용자 조치는 앱 안에서 업데이트 확인·설치·연결이며, 러너의 기동·자기갱신·실패 복구·종료는 클라이언트 책임이다. 직접 exec 검사는 개발자의 하위 호환 검증이고 사용자 사용 절차가 아니다.

## TASK-20260908-brand-icon — DQA 서비스 아이콘

### 2.1 Implementation Plan

- 요청: 서비스에 맞는 세련되고 절제된 아이콘을 생성하여 클라이언트와 설치 파일에 적용한다.
- 위험도: Minor. 브랜드 자산·패키징·창 아이콘 지정만 변경하며 기존 제품명과 업데이트 계약을 따른다.
- `src/client/assets/dqa.png`, `dqa.ico`: 생성 이미지 원본과 16/20/24/32/40/48/64/128/256px ICO. 마상 공식 심볼을 참고한 각진 Q/데이터 심볼·시안→보라→마젠타 색상 흐름.
- `src/client/branding.py::ICON_PATH`, `gui.py::ClientApp.__init__`, `window.py::Shell.run`: 소스와 동결본 모두 같은 자산으로 창 아이콘을 지정한다.
- `src/scripts/build_client.py::main`, `src/installer/DQAConnect.iss`: 실행 파일 내장 아이콘, 데이터 동봉, Setup/Uninstall 아이콘과 바로가기 배선. `version.py::CLIENT_VERSION` 1.1.2 패치 릴리스.
- 트레이는 동일 ICO를 먼저 추출하고, 자산 실패 시 EXE·시스템 아이콘 순으로 복구한다. 소스/동결본에 같은 아이콘을 적용한다.
- 검증: feature pytest, 실제 Windows PyInstaller/Inno Setup 빌드, EXE/설치기 아이콘 리소스와 ICO 픽셀 대조, 내장창/트레이 관찰, 릴리스 채널 다운로드 SHA-256.
- 완료 예시: Explorer의 DQAConnect.exe·DQAConnect-Setup-1.1.2.exe, 작업표시줄·트레이에서 동일한 마상 계열 Q/데이터 아이콘이 보인다. 별도 브라우저 폴백 창의 아이콘과 웹 색상 테마는 브라우저/웹의 기존 동작이다(사용자 아이콘·설치 파일 우선 선택).

### Requested Scope / Completion Checklist

- [x] 아이콘 원본과 다중 해상도 ICO 생성 및 작은 크기 시각 확인
- [x] 클라이언트 창·트레이·실행 파일·바로가기·설치/제거 아이콘 배선
- [x] Windows 설치 파일 생성 및 리소스 실측
- [x] 테스트·독립 리뷰·기능 문서 갱신
- [x] 최신 main 러너 복구 보존·1.1.2 재빌드·전체 524건 및 Windows 아이콘 재검증
- [x] commit/push/PR #1608 병합 및 1.1.2 릴리스 채널 반영 — 엣지 manifest/다운로드 200, 크기·SHA-256·바이트 동일

- 추가 실측 반영: `src/scripts/export_icon.py`가 DIB16~128/PNG256 혼합 ICO를 재현한다. 전 프레임 PNG 방식은 Tk에서16px 확대가 발생했으며 DIB 교체 후32px 픽셀 일치 확인.
- hot_paths: `src/client/{gui,window,tray}.py`, `src/scripts/build_client.py`, `src/installer/DQAConnect.iss`. 아이콘 지정·패키징만 소유하며 기존 세션 작업은 보존한다.

- [x] #1609 후속 main 동기화: 토큰 전달 수정과 문서·테스트를 보존. 클라이언트 배포 소스는 1.1.2 검증본과 동일.

- [x] 최종 main 11fa3741의 배포 완료 기록 보존 및 양 부모 대조 완료. 클라이언트 배포 소스 변경 0, 변경 웹 계약 테스트 86 PASS.

## TASK-20260908T-transparent-taskbar — 투명 아이콘과 작업 표시줄 정합

### 2.1 Implementation Plan

- 사용자 제보: 설치된 1.1.2에서 작업 표시줄에 Python 아이콘이 나타난다. 투명 배경을 기본으로 하고 나머지 아이콘 표면도 검수한다.
- 사용자 선택: 생성 도구가 실제 알파 대신 체크무늬 RGB를 생성한 뒤, 같은 심볼을 SVG로 정리하고 투명 PNG/ICO로 변환하는 방법을 승인했다.
- 위험도 Minor. 앱 식별자·아이콘·설치 바로가기만 수정하며 연결/갱신 확인 계약은 유지한다.
- `branding.py`, `gui.py`, `window.py`: UI 생성 전 고정 AppUserModelID, 창의 relaunch/icon 속성을 지정하고 source/frozen 실행을 대조한다.
- `assets/dqa.svg`, `dqa.png`, `dqa.ico`, `export_icon.py`: 배경 없는 벡터 정본, 실제 알파 PNG/ICO, 밝고 어두운 배경과 16~256px 검증.
- `.iss`, `version.py`: 같은 AppUserModelID의 시작 메뉴/바탕화면/자동실행 바로가기, 설치/제거 표시 아이콘, 다음 패치 릴리스.
- 검증: 기존 5표면에 작업 표시줄 실제 버튼과 앱 식별자·고정/재실행 정보·바로가기·설치/제거 실물을 추가. 별도 검사 인스턴스만 종료하며 사용자 활성 작업은 유지한다. 독립 UX/design 리뷰 최대 3라운드.

### Requested Scope / Completion Checklist

- [x] Python 작업 표시줄 원인 재현 및 앱/바로가기 식별자 교정
- [x] 실제 투명 SVG/PNG/ICO 및 작은 크기·밝은/어두운 배경 검수
- [x] 실행/창/트레이/작업 표시줄/바로가기/설치·제거 아이콘 검수·누락 보완
- [x] 회귀 검사·Windows 실제 빌드·독립 UX/design 검토
- [ ] PR 병합·새 설치기 채널 배포·다운로드 무결성·문서 완료

- 검수 추가: 공식 브라우저 폴백과 관련 웹 페이지의 favicon 연결이 없었다. feature-0003의 HTML 6개에 동일 SVG/ICO를 연결하고 export가 양 소비처를 함께 재생성한다. 화면 테마·로그인 프로필은 유지한다.

- 추가 로고 검수: 로그인·사이드바·빈 대화·관리 사이드바 4개 이미지도 구형 파란 로고를 참조했다. 같은 투명 SVG와 자산 스탬프로 교체하며 크기·화면 테마는 유지한다.

- [x] 검수 하네스의 잠금 화면 오판을 재현하고 가림/단색 캡처를 거부하도록 보완
- [ ] Windows 잠금 해제 후 최종 동결본 taskbar·브라우저 탭 시각 확인


### TASK-20260908T020000-delegation-friction — 교차 검증 보완

테스트 수집 누락 복구로 드러난 연결 안내/테스트 경계 오류를 함께 수정한다. 변경·검증 정본은
[feature-0043 TASK](../../feature-0043-external-llm-bridge/docs/TASK.md) 및
[위탁 병목 개선 REPORT](../../../docs/improvements/delegation-friction-20260908/REPORT.md)다.
DQA 클라이언트가 주 사용 환경이며 브라우저 인계 경로 검증을 앱 전체 검증으로 합산하지 않는다.

## TASK-20260908T-transparent-taskbar — main 정합 및 검증 경계

- [x] main a92c9256의 정책·DQA 주 사용 검증·회귀 테스트 변경을 병합하고 양 부모 보존 대조
- [x] 병합 후 네이티브 전체 536건·웹 30건 PASS
- [x] 4개 내부 로고 변경과 Windows 브라우저 실제 로그인 렌더 확인, 독립 디자인 재검토 PASS
- [ ] Windows 잠금 해제 후 최종 동결본 작업 표시줄과 앱 로고 시각 재검수
- [ ] 최종 검수 후 PR ready/병합·1.1.3 설치기 채널 및 웹 배포·라이브 대조
- 정책 재독: 현재 worktree `AGENTS.md` SHA-256 a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2. 초기 024a8b53…에서 변경되어 §10.1·15.4.1·16.3·16.4·16.5.1·PB-0009를 갱신 반영했다. Windows-browser 호환과 DQA-client 실제 검증을 구분한다.
