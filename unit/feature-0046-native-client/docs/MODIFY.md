---
doc_type: MODIFY
feature_id: feature-0046-native-client
status: active
edit_policy: append-only
---

# Modify

## CHG-20260903T140000-ai-claude-native-client-initial — Windows 네이티브 클라이언트 초판
- Timestamp: 2026-09-03T14:00:00+09:00
- 신설: `src/client/{__init__,__main__,core,gui}.py` · `src/scripts/build_client.py` ·
  `tests/test_client_core.py`
- 스택 결정 **SPIKE-02 권고(Tauri)에서 변경** — 실측으로 전제가 바뀌었다:
  Rust 없음 / Windows 파이썬 3.14 실재 / tkinter 8.6 동작 / 러너 서드파티 0.
  러너가 이미 파이썬이라 tkinter 면 **sidecar 불요**. 더 적은 부품으로 같은 약속.
- 실 Windows 실측 결함 1건: `--windowed` 빌드의 `print()` 가 프로세스를 멈춤 → `tell()`.

## CHG-20260903T142000-ai-claude-anchor-scope-followup — post-commit 지적 해소 (ANCHOR §4 · TASK §9)
- Timestamp: 2026-09-03T14:20:00+09:00
- post-commit verify 가 2건을 지적했다(pre-commit 은 통과 — 게이트 시점이 다르다):
  1. **CHECK#7 ANCHOR §4 quality** — §4 를 산문으로 채웠더니 파서가 「형식 불량 엔트리」로 읽었다.
     검사기는 템플릿 문구 `(엔트리 없음` 을 화이트리스트하므로 **그 형태를 유지**하고 근거는
     HTML 주석으로 옮겼다. `created_at` 이 미래(14:00Z)로 적혀 있던 것도 실제 시각으로 정정.
  2. **CHECK#18 requested scope (WARN)** — TASK.md §9 「Requested Scope」 신설. 요청 4항목을
     항목당 1행 + 산출물 + 배선 확인으로 열거하고, G3 affordance 실측·G4 경계 양측을 적었다.
- `git commit --amend` 를 쓰지 않았다 (AGENTS.md §16.3 Step 3 — 새 커밋으로 고친다).

## CHG-20260903T232000-ai-claude-client-actually-runs — 실제 Windows 실행으로 드러난 결함 3건
- Timestamp: 2026-09-03T23:20:00+09:00
- 사용자 요구: 「실제 클라이언트 실행·조작으로 연결까지 되는지」 + 「포커스·키보드·마우스를
  뺏지 말 것」. 실행해 보니 **클라이언트는 한 번도 동작한 적이 없었다.**

### ① 진입점 상대 임포트 — exe 가 아예 실행되지 않았다
- `DQAConnect.exe` 더블클릭 → 「Failed to execute script '__main__' … attempted relative
  import with no known parent package」. PyInstaller 는 진입 파일을 `__package__` 없는
  최상위 스크립트로 돌리는데, `client/__main__.py` 는 `from .gui import main` 이었다.
- 처방: 패키지 **밖** 진입점 `src/dqa_connect.py` + `--paths src`.
- ⚠ **내가 앞서 「실행되어 안내 대화상자를 띄운다」고 보고한 것은 틀렸다.** 정상 경로
  (`gui.tell()`)도 대화상자이고 이 실패도 대화상자라, **창이 떴다는 사실이 두 경우를
  구분하지 못한다.** 창의 존재가 아니라 **무엇이 적혀 있는지**를 봐야 했다.

### ② CA 지문 비교 — 서버 모양을 받아들이지 못했다 (연결 자체가 불가능)
- 「CA 지문이 다릅니다 / 기대: `F5:B9:…` / 실제: `f5b9c581…`」 — **같은 지문**이다.
  서버는 OpenSSL 관례(대문자·콜론, `oauth_as.py:1029`)로 내고 클라이언트는 `hashlib`
  기본(소문자)으로 계산하는데 비교가 `.lower()` 만 했다.
- 셸 설치본은 이미 옳았다: `tr 'A-Z' 'a-z' | tr -d ':'`. 클라이언트는 그 비교를 옮기며
  **소문자화만 가져오고 콜론 제거를 빠뜨렸다** — 재사용은 가드를 통째로 가져와야 한다.
- 처방: `normalize_fingerprint()` 공용화 + CA·러너 **두 축 모두** 적용.

### ③ 빌드 스크립트가 한국어 Windows 에서 죽었다
- exe 정상 생성 **후** `print("⚠ …")` 가 `UnicodeEncodeError: 'cp949'` → exit 1.
  산출물은 멀쩡한데 사람과 CI 는 「빌드 실패」로 읽는다.
- 문자를 골라내지 않는다 — CP949 에는 `—`(U+2014)도 없다. **스트림**의 `errors` 만 바꾼다
  (`encoding` 은 그대로 — 바꾸면 한글이 통째로 깨진다).

### 검증
- 뮤테이션 10/10 KILL (①③ 회귀 재현 포함, 지문 축 6종).
- 실제 Windows GUI 구동 → 「연결됨」 도달, 서버 `ai.connect.funnel first_heartbeat`
  acct=1 `14:19:59` 적재, 웹 체크리스트 「✅ 내 컴퓨터가 듣는 중」.

## CHG-20260904T003000-ai-claude-packaging — 배포 형식을 설치 마법사 + 런타임 동봉으로
- Timestamp: 2026-09-04T00:30:00+09:00
- 사용자 요구: 「일반적이고 대중적인 클라이언트 배포 형식을 따르면서 종속성에 이슈가 없도록」.
- **직전 접근을 폐기했다.** exe 가 자기 자신을 파이썬으로 쓰는 자체 실행 분기를 만들다가,
  그것이 **형식이 만든 문제를 코드로 메우는 일**임을 인정하고 형식을 바꿨다.
- 변경: `--onefile` → `--onedir` · 공식 임베더블 CPython 3.14.7 동봉 · Inno Setup 설치기.
  `core.runner_python()` 이 `app_dir()/runtime/python.exe` 를 쓰고, 없으면(개발 중)
  `sys.executable` 로 떨어진다.
- 빌드가 런타임을 **넣고 끝내지 않는다** — `verify_runtime_runs_runner()` 가 러너의 모듈을
  실제로 임포트해 본다. 넣기만 하면 「설치는 되고 연결만 실패」가 된다.
- `_iscc()` 는 `%LOCALAPPDATA%\Programs` 도 본다 — winget 이 per-user 로 설치한다(실측).

### 실측
- 설치기 `DQAConnect-Setup-1.0.0.exe` 20,929,864 B, sha256 `e99c5020…`
- 무인 설치 exit=0 → 앱 폴더·`runtime\python.exe`·시작 메뉴·제거 프로그램 생성 확인
- **동봉 파이썬 3.14.7 로 러너 `--check` → exit=0** (`conn.ok … 연결 성공`).
  종전 배포본이 exit=2 로 죽던 바로 그 명령이다.
- 설치본 GUI 기동 → 「연결할 준비가 되었습니다」 도달

## CHG-20260904T013000-ai-claude-wsl-and-scheme — WSL 런타임 · 가용성 실증 · 스킴 인계
- Timestamp: 2026-09-04T01:30:00+09:00
- 사용자 제보 2건: ① [내 AI 실행] 을 눌러도 「연결 정보가 없습니다」 ② WSL 의 AI 에 진입 불가.
- 변경: `discover_runtime()`(Windows+WSL 전수) · `verify_answers()`(실제 응답 확인) ·
  `_ASK_ARGV`(런타임별 호출 형태) · `login(RuntimeState)`(WSL 로그인 대행) ·
  `runner_runtime_args()`(WSL 은 `--cmd`) · 설치기 스킴 등록 · `parse_scheme_url()`.

### 실측 (실제 Windows, 2026-09-03)
| 자리 | 발견 | 응답 |
|---|---|---|
| claude (Windows) | `~\.local\bin\claude.exe` | **17.8초** ✅ |
| claude (WSL) | `/usr/local/bin/claude` | 3.8초 ✅ |
| codex (WSL) | `/usr/local/bin/codex` | 4.4초 ✅ |

종전 클라이언트는 **1개**(Windows claude)만 봤다. 지금은 3개를 보고 각각을 실증한다.

### ⚠ 내가 앞서 단정한 것을 정정한다
「Windows claude 는 답하지 못한다」고 적었다. **틀렸다.** 관측 2회(180초·93초)가 타임아웃에
걸렸을 뿐이고, 같은 런타임이 17.8초에 답했다. 느린 것과 못 하는 것은 다르다 — 관측 2회로
「불가」를 단정하면 안 된다. 그래서 `verify_answers` 는 **판정을 캐시하지 않고** 매번
확인하며, 실패 문구도 「쓸 수 없습니다」가 아니라 시간과 함께 말한다.

## CHG-20260904T020000-ai-claude-ssot-catch — 테스트가 옛 스킴을 정본에서 읽는다
- Timestamp: 2026-09-04T02:00:00+09:00
- CI 의 `feature-0043/tests/test_name_ssot.py` 가 새 테스트 파일의 옛 스킴 **리터럴**을
  적발해 적색. 허용 목록 예외 대신 `shared/dqa_identity.LEGACY_SCHEME` 를 읽도록 교체.
- ⚠ 절차 오류도 함께 남긴다: 이 수정을 밀 때 **verify-completion 통과를 확인하기 전에
  commit·push 했다.** 게이트는 통과를 확인한 **뒤에** 커밋한다.

## CHG-20260904T033000-ai-claude-client-first-handoff — 딥링크에 연결 정보를 싣고 웹은 클라이언트 우선으로
- Timestamp: 2026-09-04T03:30:00+09:00
- 사용자 제보: 재설치 후에도 [연결 준비] → [내 AI 실행] 이 **「연결 정보가 없습니다」**.
- 원인: `scheme_url()` 이 `?token=` 만 실었다. 이 딥링크는 **셸 설치본용**이고 그 경로는
  서버 주소·CA 를 설치 때 디스크에 심으므로 토큰만 받으면 됐다. 네이티브 클라이언트에는
  그 사전 상태가 없어 base 를 몰랐다.
- 처방: 정본 헬퍼가 `base`·`ca_sha256`·`agent_sha256` 을 함께 싣는다(URL 인코딩).
  셸 핸들러는 `[?&]token=([^&]+)` 로 뽑으므로 영향 없다(테스트로 잠금).
- 신뢰: 딥링크의 `base` 는 남이 만든 링크일 수 있다 → **처음 연결한 서버를 고정**하고
  다르면 묻는다(`server_changed`/`pin_server`). 고정은 **연결 성공 후에만**.
- 화면: 터미널 1·2·3단계를 접었다(사용자 결정). **없애지 않았다** — 프로그램이 없는
  사용자에게 유일한 길이고, 실패 안내가 그리로 보낼 때는 자동으로 펼친다.
- 뮤테이션 9/9 KILL(원래 결함 재현 포함).

### ⚠ 직전 cycle 의 내 검증이 왜 이것을 못 잡았나
스킴 인계를 「검증했다」고 보고했으나, 그때 쓴 URL 은 **내가 조립한 것**이었다. 즉 내
조립기와 내 파서가 맞는지를 시험했고 **제품이 실제로 보내는 것은 한 번도 넣어 보지
않았다**. `test_handoff_seam.py` 는 `dqa_identity.scheme_url()` 을 직접 호출해 봉투를 만든다.

## CHG-20260904T041000-ai-claude-ux-contract-followup — UX 패리티 계약 갱신 반영
- Timestamp: 2026-09-04T04:10:00+09:00
- `feature-0043/tests/test_ux_parity.py` 3건이 옛 주 경로(터미널)를 계약으로 잠가 CI 적색.
  주 경로 변경은 사용자 결정이므로 계약을 옮겼다 — 보호하던 성질은 유지(REV-…040000 참조).
- ⚠ **절차 오류 재발**: `verify-completion` 이 FAIL 을 낸 직후 다음 줄에서 commit·push 했다.
  앞선 cycle 에서 같은 실수를 하고 「`&&` 로 잇는다」고 적었는데, 이번에는 verify 와 commit 을
  **다른 명령으로 분리**해 그 규칙이 적용되지 않았다. 규칙을 「`&&` 로 잇는다」가 아니라
  **「verify 의 종료코드를 조건으로 삼는다」**로 다시 적는다 — 형태가 아니라 조건이 본질이다.

## CHG-20260904T050000-ai-claude-connect-page-launch — /ai/connect 에 [내 AI 실행] 추가
- Timestamp: 2026-09-04T05:00:00+09:00
- ⚠ **내가 직전 cycle 에서 만든 결함을 고친다.** 두 화면의 안내를 「[내 AI 실행] 을 누르면」
  으로 바꾸면서, `/ai/connect` 페이지에는 **그 버튼이 없다는 사실**을 확인하지 않았다
  (모달에만 있었다). 즉 화면이 **없는 버튼을 가리켰다** — P0-AC 가 닫은 결함 클래스
  (「표시하는 화면 전부가 같아야 한다」)의 재발이다.
- 내 테스트도 문구만 봐서 통과했다. **문구가 있다는 것과 그것이 가리키는 대상이 있다는 것은
  다른 축**이다. 이제 버튼 실재 + 배선 + 기본 숨김 + 조용한 실패 안내를 함께 단정한다.
- 배선은 모달 정본과 같다: 프로토콜 URL 이 있을 때만 노출, `location.href = protocol`.
- ⚠ 처음 삽입할 때 핸들러가 `paintOsTab()` **안**에 들어가 탭을 다시 그릴 때마다 등록됐다.
  중복 등록은 조용하다 — 화면은 멀쩡하고 클릭 한 번에 여러 번 돈다. 옮기고 테스트로 잠갔다.
- 뮤테이션 5/5 KILL (버튼 제거·기본 노출·배선 제거·안내 제거·재등록 위치).
## CHG-20260904T070000-ai-claude-web-shell-bridge — 로컬 브리지 (웹 셸 1단계)
- Timestamp: 2026-09-04T07:00:00+09:00
- 사용자 요구: 「Slack 같은 웹 기반 클라이언트」 + 「재사용보다 **서비스와의 정합**」.
- **구조 결정이 바뀌었다.** 처음 제안(클라이언트가 UI 를 로컬에서 서빙)을 폐기했다. 이유는
  이 프로젝트가 러너에 대해 이미 내린 판단과 같다 — *「동봉하면 서버 배포와 클라이언트
  배포가 갈려 「고쳤는데 그대로」가 재발한다」*. UI 를 클라이언트에 넣으면 그 기각한 구조를
  화면에 대해 채택하는 것이고, 실제로 이번 주기에 **낡은 설치본이 조용히 실패**했다.
- 채택: **화면은 서비스에 하나**, 클라이언트는 브라우저가 못 하는 일만 하는 로컬 브리지.
  실측으로 성립 확인(2026-09-04): https 서비스 페이지 → `http://127.0.0.1` 호출이
  혼합 콘텐츠·CORS·**사설망 접근(PNA)** 세 겹을 모두 통과했다.
- 방어 네 겹: 127.0.0.1 바인딩 + 임의 포트 · 실행마다 새 nonce · origin 고정(TOFU 서버) ·
  **위험 동작은 네이티브 확인창**(사용자 결정). GET 은 아예 막는다 — `<img>`·`<script>` 로도
  발사되어 preflight 를 우회하기 때문이다.
- ⚠ 자체 발견: `stop()` 이 **기동하지 않은 브리지에서 영원히 블록**했다(`shutdown()` 은
  `serve_forever()` 루프를 전제로 기다린다). 기동 실패한 앱이 종료되지 않는 결함이라 닫았다.
- 뮤테이션 12/12 KILL (검사 3종 제거·접두 비교·확인 생략·DANGEROUS 비움·GET 개방·PNA 제거·
  preflight 개방·고정 nonce·0.0.0.0 바인딩·stop 블록 회귀).

## CHG-20260904T090000-ai-claude-web-shell — 웹 셸 2·3단계 (앱 창 · 서비스 패널 · 디자인 정합)
- Timestamp: 2026-09-04T09:00:00+09:00
- **앱 창**: Windows 가 기록한 https 기본 핸들러에서 실행 파일을 읽어 `--app=` 로 띄운다.
  ⚠ `--user-data-dir` 를 **주지 않는다** — 주면 새 프로필이라 로그인 세션이 없다.
  기본 브라우저가 `--app` 을 모르면(Firefox) 크로미움 계열로 내려가고, 그때는
  **세션이 없을 수 있다고 미리 말한다**. 아무 브라우저도 없으면 tkinter 폴백.
- **주 스레드가 tkinter 를 소유**한다. 브리지는 워커에서 돌고 확인 요청을 큐로 넘긴다.
  답이 없으면(300초) **아니오**다 — 무한 대기는 브리지 요청을 영원히 붙잡는다.
- **서비스 패널**: `?client_port=&client_nonce=` 가 있을 때만 나타난다. 평범한 방문에는
  아무것도 보이지 않는다. 브리지 호출은 POST + nonce 헤더 고정.
- **디자인 섬 해소**: 이 화면은 자기 토큰(`--aic-*`)을 정의해 서비스와 값이 어긋나 있었다
  (강조 `#1f6feb` vs `#2563eb`, 배경 `#f6f7f9` vs `#f7f7f4`). 규칙은 그대로 두고
  **토큰의 출처만** `css/base.css` 로 옮겼다 — 폭발 반경 최소, 정합 최대.
- 뮤테이션 15/15 KILL.

### ⚠ 뮤테이션이 잡은 내 테스트 결함 2건
- `--app`·`--user-data-dir` 단정이 **소스 전체**를 뒤져 «그러지 않는다」고 설명한 주석에
  걸렸다. 단정 대상은 설명이 아니라 **조립되는 인자**다 → `_code_of()` 로 docstring 을 뺀다.
- 기본 브라우저 판정을 **접두 비교로 바꿔도** 통과했다. 접두가 같은 다른 실행 파일
  (`chrome.exe.evil\x.exe`)을 가르는 입력이 없었다 → 추가했다.
## CHG-20260904T100000-ai-claude-tray-and-windowless — 트레이 상주 + 자식 콘솔 창 제거
- Timestamp: 2026-09-04T10:00:00+09:00
- 사용자 요청 2건: ① 트레이 아이콘으로도 작동 ② AI 플랫폼 연결 시 창 깜빡임을 백그라운드로.

### ① 알림 영역 상주 — `src/client/tray.py` 신설 (서드파티 0)
- `Tray`(순수 로직: 메뉴 조립·명령 ID 라우팅·툴팁 상한·수명) + `Win32Backend`(ctypes)로
  **둘로 나눴다**. 리눅스 CI 는 Win32 층을 한 줄도 못 돌리므로, 로직을 그 층에서 빼내지
  않으면 「테스트가 있다」와 「검사된다」가 갈린다.
- `gui.py`: [X] → 숨김(연결 유지) · 오른쪽 클릭 메뉴(창 열기/연결 토글/종료) · 툴팁이
  상태를 말함 · 모든 화면에 [트레이로 숨기기] 버튼.
- **폴백이 핵심**: `Tray.start()` 가 거짓이면 [X] 는 종전대로 종료이고 문구도 갈린다.
  트레이 없이 숨기면 사용자는 프로그램을 잃는다(화면에도 알림 영역에도 없음).
- `pystray` 불채택 — `Pillow` 동반으로 번들이 수십 MB 늘고 백신 오탐 표면이 넓어진다.
  아이콘은 `ExtractIconW` 로 **우리 exe 안의 것**을 꺼내 쓴다(그리지 않으므로 이미지
  라이브러리 불요). ANCHOR §1 「부품 하나로 끝난다」와 같은 근거.

### ② 자식 콘솔 창 제거 — `core.hidden_child_kwargs()`
- 깜빡임의 정체: `--windowed` 빌드는 자기 콘솔이 없어, 콘솔 앱 자식(`claude`·`codex`·`wsl`)을
  띄우면 Windows 가 **새 콘솔을 할당**한다. 출력은 파이프로 받으므로 그 창은 **비어 있다**.
- ⚠ **가드는 이미 있었다 — `spawn_runner` 한 곳에만.** 즉 없었던 것이 아니라 **모수가
  노출면보다 좁았다**(§16.7 G12). 탐지·로그인·연결확인이 전부 그 밖이었고, 사용자가 본
  깜빡임은 전부 거기서 났다. 판정을 함수 하나로 모으고 census 테스트를 걸었다.
- `_is_windows()` 이음매 신설 — 테스트가 `os.name` 을 통째로 바꾸면 `pathlib` 이
  `WindowsPath` 로 바뀌어 무관한 코드가 죽는다(실측). 판정만 바꿔 끼운다.

### ③ 실 Windows 실측이 잡은 결함 2건 (리눅스 171건은 전부 통과 중이었다)
- **ctypes argtypes 누락** — `ExtractIconW` 의 x64 모듈 핸들에서
  `OverflowError: int too long to convert` → **아이콘 등록 자체가 실패**(`hwnd=0`).
  사용하는 Win32 함수 전부에 argtypes/restype 를 선언해 해소.
- **`MF_DEFAULT` 를 `AppendMenuW` 에 넘김** — 그 상수는 `AppendMenu` 의 유효 플래그가
  아니라 **조용히 무시**된다. 실 Windows 에서 메뉴를 조립해 `GetMenuState` 로 읽으니
  5항목 전부 기본 항목 아님. `SetMenuDefaultItem` 으로 교체.
- 두 결함 모두 **오류도 경고도 없이** 기능만 사라지는 형태다.

### ④ 실측 스크립트를 커밋했다 — `tests/windows/`
- 그 자리에서 발명한 검증은 세션과 함께 사라진다(§16.7 G14-d). 4종 스크립트 + README
  (실행법·판정표·하네스 함정 2건)를 남겨 다음 작업자가 같은 자리에서 다시 실패하지 않게 했다.

### 하지 않은 것
- **설치기(.iss) 무변경** — 트레이는 런타임에 앱이 만든다. 설치기 문구·자동시작 항목은
  이번 요청 범위가 아니고, 자동시작의 「로그온 → 바로 연결」은 토큰 보관 설계가 선행이다.
- **`--tray`(숨은 채로 시작) 옵션 미도입** — 부를 자리가 없으면 「존재는 실행이 아니다」
  (§16.7 G14-e)의 형태가 된다. 자동시작이 실제로 연결까지 갈 수 있게 된 뒤에 붙인다.

## CHG-20260904T113000-ai-claude-tray-review-p1 — 적대 리뷰 P1 4건 수정
- Timestamp: 2026-09-04T11:30:00+09:00
- codex 적대 리뷰(§18.8.2-1 제약 없는 채널)가 P1 4건을 냈고 **전부 유효**해 전부 고쳤다.
  넷 다 **트레이를 붙이면서 새로 도달 가능해진** 경로다 — 기능을 더하면 있던 코드의 전제가 바뀐다.
- `gui.py`: 선택을 GUI 스레드에서 확정해 넘김(`_start_connect`) · 연결 단일 실행 게이트
  (`_connect_gate`) · 종료 경합 차단(`_shutting_down` 2지점) · 트레이 판정을 존재→**생존**
  (`_tray_live`)으로 전환.
- `tray.py`: `Tray.alive`(backend 생존 조회) 신설 · `TaskbarCreated` 재등록 **실패를 삼키지 않음**.
- ⚠ **부수 발견**: `_connect` 가 러너에 넘기던 것은 상태 객체가 아니라 **라벨 문자열**이었다.
  WSL 런타임을 고르면 `--ai "claude (WSL)"` 이 가서 이름부터 어긋난다(Windows 자리는
  라벨==이름이라 증상이 없어 숨어 있었다). 스레드 수정과 같은 지점이라 함께 고쳤다.
- 테스트 40건(총 177) · 뮤테이션 **21/21 KILL, NOOP 0** · 실 Windows 4종 재실행 PASS.

## CHG-20260904T121000-ai-claude-tests-actually-run-in-ci — 이 feature 의 테스트가 CI 에 없었다
- Timestamp: 2026-09-04T12:10:00+09:00
- **발견**: `unit/feature-0046-native-client/tests` 가 `.github/workflows/ci.yml` 의 pytest 경로
  목록에도, `pyproject.toml` 의 `testpaths` 에도 **없었다**. 2026-09-03 신설 이후 이 feature 의
  테스트는 **로컬에서만** 돌았고 CI 는 그 축을 한 번도 보지 않았다.
- ⚠ **이 저장소가 이미 아는 재발 클래스다.** `ci.yml` 주석이 직접 경고한다 — 「새 테스트
  디렉토리를 만들면 **양쪽 모두** 등재한다 … 로컬은 green 인데 CI 는 그 축을 보지 않는 상태가
  조용히 생긴다 — **지금까지 4번 그랬다**」. `pyproject.toml` 의 feature-0014 주석도 같은 사고를
  기록한다(전면 503 이 6시간에 71건 나는 동안 CI 는 초록이었다).
- 이번 cycle 이 테스트 40건을 더했으므로, 등재하지 않으면 **그 40건도 실행되지 않는다** —
  「존재는 실행이 아니다」(AGENTS.md §16.7 G14-e). 그래서 이 cycle 안에서 배선했다.
- **적용: `pyproject.toml` `testpaths` 4 → 5.**
- ⛔ **미적용(권한 차단): `.github/workflows/ci.yml`.** 푸시가 거부됐다 —
  `refusing to allow an OAuth App to create or update workflow ci.yml without workflow scope`.
  현재 토큰 스코프는 `admin:public_key, gist, read:org, repo` 로 **`workflow` 가 없다**(SSH
  대체 경로도 이 저장소에는 없다). **AI 가 이 파일을 바꿀 수단이 없다.**
- ⚠ **그래서 CI 는 여전히 이 feature 의 테스트를 돌리지 않는다.** CI 스텝은 `pytest -q <경로들>`
  로 경로를 **명시**하므로 `testpaths` 를 보지 않는다 — 즉 이번 `pyproject.toml` 갱신은 로컬
  `pytest` 만 덮는다. **절반만 배선된 상태를 「배선했다」로 적지 않는다**(§16.7 G14-e 의 요점이
  정확히 그것이다).
- **남은 조치(사람 필요, 1줄)**: `.github/workflows/ci.yml` 의 pytest 경로 마지막 줄
  `unit/feature-0006-lan-proxy-access/tests` 뒤에 ` \` 를 붙이고 다음 줄에
  `unit/feature-0046-native-client/tests` 를 추가한다. `workflow` 스코프가 있는 토큰 또는
  GitHub 웹 편집으로 가능하다.
- ⚠ **또 하나의 남은 사실**: 두 목록은 애초에 서로 다르다(ci.yml 9 vs testpaths 5). 그 불일치
  자체가 다음 누락의 온상이지만 이 요청의 범위 밖이라 **기록만** 한다. 구조적 해소는
  「한 목록에서 다른 목록을 생성하거나, 두 목록의 일치를 검사하는 테스트」다.
- Win32/트레이 층은 리눅스에서 돌지 않으므로 CI 대상이 아니다 — 그 층은
  `tests/windows/`(pytest 수집 대상 아님) + README 의 실행법이 담당한다.

## CHG-20260904T125000-ai-claude-frozen-icon-verified — 동결 exe 아이콘 추출 실측
- Timestamp: 2026-09-04T12:50:00+09:00
- REPORT 에 「미검증」으로 적어 둔 항목 하나를 **실제로 재서** 닫았다. 이 저장소는 「소스로는
  되는데 동결본에서는 안 되는」 결함을 이미 두 번 겪었다(`sys.executable` 이 파이썬이 아닌
  문제 · 진입점 상대 임포트) — 그래서 동결 축은 추정으로 남기지 않는다.
- 실제 배포 형식으로 빌드(`build_client.py --skip-installer`, exit 0 · `DQAConnect.exe`
  2,284,758 B · 임베더블 CPython 동봉 + 러너 모듈 임포트 검증 통과) 후, 그 산출물에
  `ExtractIconW` 를 걸어 `icon_count=1` · 유효 핸들 확인 → 배포본 트레이는 **앱 아이콘**이다.
- `tests/windows/verify_frozen_icon.py` 커밋 + README 판정표·빌드 절차 추가.
- ⚠ **앱을 실행하지는 않았다** — 실행하면 탐지가 돌아 사용자의 AI 사용량을 쓴다. 동결 축에서
  확인한 것은 아이콘 추출 하나이고 그 사실을 그대로 적는다.
- 부수 확인: 빌드 로그가 CP949 콘솔에서 한글이 깨져 나오는데도 **종료 코드 0** — §P0-I 의
  `_make_stdio_lossy()` 가 의도대로 동작한다(「깨짐 = 실패」가 아니다).
