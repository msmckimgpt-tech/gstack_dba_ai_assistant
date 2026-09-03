---
doc_type: TASK
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
feature_status: in-progress
---

# Task

## 1. 현재 상태

첫 cycle 완료 — 코어·GUI·빌드 스크립트·테스트 20건. **실 Windows 에서 감지·GUI 구성·exe 빌드·
실행까지 실측 확인.** 후속: 자동시작·자동 업데이트·벤더 설치기 실행.

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

## 9. Requested Scope (요청 범위 자기-열거)

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
- [ ] 연결 주체 완전 이동 (클라이언트가 스스로 토큰 취득)
