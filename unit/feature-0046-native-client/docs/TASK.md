---
doc_type: TASK
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
feature_status: in-progress
---

# Task

## 1. 현재 상태

트레이 상주 + 자식 창 숨김 + **주 표면(앱 창) 패널 정합**까지 완료 — feature 테스트 264건,
**실 Windows 4종 실측 전부 PASS**, jsdom 행위 하네스 2종 PASS(대조군 포함).
후속: 로그온 자동시작으로 «바로 연결»(토큰 보관 선행) · 자동 업데이트 · 벤더 설치기 실행.

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
- [x] main `P0-U`~`P0-X` 와의 ID 충돌 2회차 해소 — 본 cycle 을 `P0-Y/P0-Y-1/P0-Z` 로 재번호
- [x] wiki 미러 정합(Features 카드 §4-2 · Log · hot)
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
