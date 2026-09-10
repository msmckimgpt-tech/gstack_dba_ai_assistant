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

## CHG-20260904T100000-ai-claude-bridge-lifetime — 수명 신호를 패널 생존으로
- Timestamp: 2026-09-04T10:00:00+09:00
- **실제 실행이 결함을 드러냈다.** 딥링크로 전 경로를 태우니 앱 창은 떴는데
  `DQAConnect` 프로세스가 **0** 이었다. 원인: 브리지 수명을 «띄운 브라우저 프로세스» 로
  판정했는데, Chrome 이 **이미 떠 있으면** 새 창을 기존 인스턴스에 위임하고 런처 프로세스는
  **즉시 종료한다**(실측: exit=0, 5초 내). 브리지가 곧바로 닫혀 패널은
  「연결 프로그램에 닿지 못했습니다」만 봤다 — 전 경로가 여기서 끊겼다.
- 처방: 프로세스 계보 대신 **패널이 말을 걸어오는가**로 판정한다(`idle_seconds`).
  패널은 20초마다 `ping`, 브리지는 90초 유휴면 스스로 끝난다. 창을 닫으면 말이 끊긴다.
- ⚠ **모든 요청**이 생존 신호다 — `ping` 만 갱신하면 탐지가 오래 걸리는 동안 죽는다(L3).
- 뮤테이션 5/5 KILL (원래 결함 회귀 포함).

## CHG-20260904T110000-ai-claude-app-is-dqa — 앱 창을 그대로 DQA 로
- Timestamp: 2026-09-04T11:00:00+09:00
- 사용자 결정: 「브라우저를 통한 별도의 연결 없이, 앱 창을 그대로 DQA 로」.
- 앱 창이 **서비스 루트**를 연다(1180×820). 연결 화면만 보여 주는 보조 창이 아니라
  **그 자체가 제품**이다 — 창을 두 개 쓰게 하지 않는다.
- 좌표는 로드 때 읽어 `sessionStorage` 에 보관하고 **주소에서 지운다**. 앱은 라우팅하며
  주소를 갈아 끼우므로 나중에 읽으면 없고, nonce 가 기록에 남을 이유도 없다.
- 연결 능력은 **대화 모달** 안에서 쓰인다. 평범한 브라우저 방문에는 패널이 켜지지 않고
  종전 경로가 그대로 남는다 — 프로그램 없는 사용자를 막다른 길에 세우지 않는다.

### ⚠ CI 가 잡은 내 회귀 2건과 처방
- `connect-modal.js` 에는 **브라우저 저장소 금지**(이력은 서버에서 온다)와 **상시 폴링 금지**
  가드가 걸려 있다. 브리지 좌표(sessionStorage)와 생존 신호(setInterval)를 그 파일에 넣어
  둘 다 깨졌다.
- **가드를 느슨하게 하지 않고 파일을 갈랐다** — `app/client-bridge.js` 신설. 브리지 좌표는
  이력이 아니고 생존 신호는 상태 폴링이 아니지만, 그 가드가 지키는 파일에 섞어 두면 다음
  사람이 둘을 구분하지 못한다. 새 파일에도 「이력 저장 금지」는 테스트로 이어 붙였다.
- node 하네스가 새 import 를 못 찾아 8건이 깨졌다 → `showToast` 와 **같은 방식으로 스텁**.
  그 하네스가 재현하는 것은 평범한 브라우저 방문(브리지 없음)이므로 실물이 필요 없다.
- 뮤테이션 12/12 KILL.

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

## CHG-20260904T133000-ai-claude-merge-webshell-and-tray-reach — 웹 셸 병합 + 트레이 도달 범위
- Timestamp: 2026-09-04T13:30:00+09:00
- 같은 feature 를 병렬 진행한 두 cycle 이 만났다(main 의 PR #1568 웹 셸 1·2·3단계 ↔ 본 cycle 트레이).
- **충돌 3건 자율 해결**(§16.4): `gui.py` 임포트 양쪽 보존 · `FUNCTION.md` 절 번호 충돌 →
  main 선착 쪽이 P0-S/P0-T 유지, 본 cycle 은 **P0-U/P0-V 로 재번호** · `TASK.md` 양쪽 cycle
  블록 보존(시간순). 해결 결과는 **양측 부모 대비**로 검증했다 — 삭제 파일 0, 그쪽 신규 4파일
  바이트 동일, 양쪽 고유 심볼 전수 잔존, 합본 테스트 227 passed.

### ⚠ 병합이 드러낸 것 — 트레이의 **도달 범위**가 좁아졌다
- main 의 새 `gui.run_client()` 는 **웹 셸(브라우저 앱 창)을 주 경로**로 삼고, tkinter
  `ClientApp` 은 「`--app` 을 못 여는 머신」의 **폴백**이 됐다.
- 이번 cycle 의 트레이는 `ClientApp` 에 붙어 있다 → **주 경로 사용자는 트레이를 만나지 못한다.**
- 반면 **깜빡임 수정(`core.hidden_child_kwargs`)은 두 경로 모두에 적용된다** — 탐지·로그인·
  연결확인·러너 기동이 전부 `core` 를 지나기 때문이다. 두 요청의 도달 범위가 **서로 다르다**.
- ⚠ **코드가 합쳐졌다는 것과 사용자가 그 기능을 만난다는 것은 다른 축이다.** 병합 green 을
  「요청 충족」으로 읽지 않는다.

### 왜 이번 cycle 에서 웹 셸 경로까지 확장하지 않았나
- `run_client`/`_serve_confirms` 는 **「앱 창이 닫히면 연결도 끝난다」를 의도된 계약으로 명시**
  하고, 그쪽 **웹 페이지 문구가 같은 말을 한다**. 트레이를 붙이려면 그 계약과 그 문구를 함께
  바꿔야 한다 — 안 바꾸면 화면이 거짓을 말하게 된다(P0-R).
- 그 경로는 유효 토큰 + 실 서버 + 브라우저가 있어야 구동되므로 **이 세션에서 실측할 수 없다.**
  검증 없이 주 경로의 수명 계약을 바꾸는 것은 이 저장소가 반복해 벌을 받은 형태다.
- 사용자 요청 시점(2026-09-04 오전)의 DQAConnect UI 는 tkinter `ClientApp` 이었다. 웹 셸은
  그 뒤 착륙했다 — 요청 범위가 **작업 중 바뀐** 경우이므로 자의로 넓히지 않고 표면화한다.

## CHG-20260904T134500-ai-claude-guard-misuse-warning — 창 숨김 인자를 GUI 자식에 쓰지 않게
- Timestamp: 2026-09-04T13:45:00+09:00
- 병합 후 확인: `appwindow.open_app_window()` 도 자식을 띄우는데 **`CREATE_NO_WINDOW` 만**
  준다. 이것은 결함이 아니라 **옳다** — 브라우저 앱 창은 자기 창을 **보여 줘야** 하므로
  `SW_HIDE` 를 주면 아무것도 안 뜬다(「눌렀는데 아무 일도 없다」 = 조용한 실패).
- 그런데 이번 cycle 이 만든 `hidden_child_kwargs()` 는 이름·docstring 이 「자식을 창 없이」라
  **그쪽에 갖다 쓰고 싶어지는 유인**을 만든다. 내가 만든 함정이므로 내가 표지를 세운다.
- `core.hidden_child_kwargs` docstring + `FUNCTION.md` §P0-AD 에 **「GUI 자식에는 쓰지 않는다 ·
  appwindow 의 중복은 의도된 것」** 을 명시. 코드 동작 변경 0 — 오용 방지 표지만 추가.

## CHG-20260904T140000-ai-claude-scope-decision-recorded — 웹 셸 트레이는 별도 cycle (사용자 결정)
- Timestamp: 2026-09-04T14:00:00+09:00
- 병합이 드러낸 「트레이가 주 경로에 없다」를 사용자에게 물었고, **별도 cycle** 로 결정됐다.
- TASK/REPORT 의 「사용자 결정 대기」를 그 결정으로 갱신. 대화가 아니라 **문서가 정본**이다.
- 이번 PR 은 현 상태로 머지한다 — 폴백 경로 트레이 + **두 경로 모두 적용되는** 깜빡임 수정.

## CHG-20260904T143000-ai-claude-merge-1569-and-parity-note — main 재병합 + 갈린 계약 정정
- Timestamp: 2026-09-04T14:30:00+09:00
- main 이 다시 전진(PR #1569 — 브리지 수명을 패널 생존 신호로 · 앱 창을 그대로 DQA 로).
  충돌 3건(MODIFY·REVIEW·TASK)은 전부 **양쪽 말미 추가** 형태라 §16.4 대로 둘 다 보존했다.
- ⚠ **ID 충돌 해소**: 양쪽이 `## TASK-20260904T100000` 을 그대로 썼다(내 쪽은 슬러그 없음).
  §6 권장 형식대로 나중 도착인 이번 cycle 에 슬러그를 붙여
  **`TASK-20260904T100000-tray-background`** 로 가르고, **내 항목의** `Related TASK` 6건만
  갱신했다(그쪽 항목 무접촉).
- ⚠ **병합이 만든 거짓 서술 1건 정정**: `_serve_confirms` 도크스트링이 「그것이 tkinter 판과
  같은 계약이다」라고 적고 있었는데, **이번 cycle 이 tkinter 판의 계약을 바꿨다**(트레이가
  살아 있으면 창을 닫아도 연결 유지). 두 경로의 수명 계약이 갈렸다는 사실과, 확장은 별도
  cycle 이라는 사용자 결정, 그리고 확장 시 **패널 문구도 함께** 바꿔야 한다는 점을 명시.
  동작 변경 0 — 주석만. 병렬 cycle 이 만나면 **한쪽의 참이 다른 쪽에서 거짓이 된다.**
- 합본 테스트 **245 passed**.

## CHG-20260904T150000-ai-claude-tray-parity-across-shells — 상주를 두 껍데기 공통으로 재구성
- Timestamp: 2026-09-04T15:00:00+09:00
- 사용자 지시: *「'근본 원인 분석 및 해결 방안 모색' 세션에서 작업하는 부분과 정합하게
  작동하도록 재구성해주세요」*. 그 세션이 세운 구조(화면은 서비스에 하나 · 웹 셸이 주 경로 ·
  브리지 수명 = 패널 생존 신호)에 이번 cycle 의 트레이를 맞춰 넣는다.
- **문제**: 트레이가 tkinter **폴백에만** 붙어 있었다. 주 경로 사용자는 패널을 닫는 순간
  연결을 잃었고, 두 껍데기의 수명 계약이 갈렸다. 사용자에게 이 프로그램은 하나다.
- `bridge.py`: **공개 수명 창구** 신설 — `connected`(러너 생존) · `disconnect()`(러너만 내리고
  브리지는 유지 — 패널을 다시 열어 재연결할 수 있어야 상주의 의미가 산다) ·
  `resident` 플래그와 `status.resident`.
  ⚠ `_runner_proc` 를 호출부가 직접 들여다보게 두지 않았다 — 수명 판정이 흩어지면 그 중
  하나만 고쳐지는 드리프트가 난다(이 cycle 이 창 숨김 가드에서 이미 겪은 형태).
- `gui.py`: `_start_shell_tray()` 신설 + `run_client` 배선 + `_serve_confirms(tray=…)`.
  **상주 중에는 유휴가 종료 사유가 아니다**(패널을 닫아 두고 쓰는 것이 상주다). 아이콘이
  없거나 **뜬 뒤 죽으면** 종전 계약(유휴 90초)으로 되돌아간다 — 상주할 표면이 없는데 계속
  살아 있으면 끌 수단이 없다. tkinter 판의 `_tray_live` 와 **같은 판정**이다.
- `ai-connect.js` · `ai-connect.html`: 패널이 「닫아도 유지됩니다 / 닫으면 끝납니다」를
  **갈라 말한다**. 판정 근거는 `status.resident` 하나 — 프런트가 추정하면 트레이 없는
  머신에서 거짓이 되고 사용자는 창을 닫고 연결을 잃는다(P0-R).
- ⚠ **웹 셸 트레이에 「다시 연결」을 넣지 않았다**: 이 경로의 연결 입구는 패널이고, 트레이가
  자체 재연결을 가지면 같은 동작의 입구가 둘로 갈린다. 트레이는 패널을 열어 주고 연결은
  거기서 건다. 끊기만 트레이가 한다(패널 없이도 해야 하는 동작).
- 테스트 +10(총 255) — 유휴가 상주를 끝내지 않는지, 트레이 없음/죽음이 종전 계약으로
  돌아가는지, 메뉴 어휘가 두 껍데기에서 같은지, 패널이 판정을 받아서 쓰는지를 **구동**으로 확인.

## CHG-20260904T154000-ai-claude-wiki-parity — wiki 를 재구성에 정합
- Timestamp: 2026-09-04T15:40:00+09:00
- `wiki/Features/feature-0046-native-client.md` §4-2 신설(두 껍데기 공통 상주 규약 ·
  「다시 연결」 부재의 의도 · 패널 문구의 판정 출처 · PB-0008 이월).
- `wiki/Log.md` append(재구성 + 하네스 결함 2건 + CHECK#13 사각).
- `wiki/hot.md`: 상주 fact 를 «두 껍데기 공통» 으로 갱신, 미실측 항목에서 동결 exe 아이콘
  제거(실측 완료)하고 **웹 셸 PB-0008 이월**을 추가.
- wiki-lint 32(선재와 동일, orphan 0).

## CHG-20260904T123000-ai-claude-panel-init-retry — 초기화 성공 여부로 플래그를 세운다
- Timestamp: 2026-09-04T12:30:00+09:00
- **배포 후 앱 창에서 패널이 끝내 안 켜졌다.** 서버 자산·스탬프·캐시 헤더를 전부 확인했고
  모두 정상이었다(컨테이너 자산 새것, 사이드카 스탬프 갱신됨, 스탬프 URL 이 새 코드 서빙).
  원인은 **내 배선**이었다 — `_clientPanelReady = true` 를 **호출 전에** 세워서,
  `initClientPanel()` 이 일찍 반환해도 「했다」가 되고 **다시 시도하지 않았다**.
- 처방: `initClientPanel()` 이 성립 여부를 돌려주고, 호출부가 **그 값으로** 플래그를 세운다.

## CHG-20260904T124000-ai-claude-wiring-contract — 배선 1회 계약을 결과 기록 형태로
- Timestamp: 2026-09-04T12:40:00+09:00
- `test_modal_panel_is_wired_only_once` 가 옛 형태(`_clientPanelReady = true`)를 잠그고
  있어 새 계약과 충돌했다. 지키는 성질(한 번만 배선)은 그대로 두고 **기록하는 값**만
  결과로 바꿨다.
- ⚠ 절차: 이 수정 직전 커밋에서 **테스트 실패를 확인하지 않고 푸시**했다. `verify-completion`
  은 pre-commit 게이트라 테스트를 돌리지 않으므로, 게이트 PASS 가 곧 테스트 green 이 아니다 —
  둘을 같은 것으로 읽었다. 커밋 전에 **회귀도 함께** 확인한다.

## CHG-20260904T170000-ai-claude-primary-panel-residency — 상주 안내를 주 표면으로 + 실행 결함 해소
- Timestamp: 2026-09-04T17:00:00+09:00
- **내 상주 안내가 사용자에게 닿지 않는 자리에 있었다.** `ai-connect.html`/`ai-connect.js`
  에 넣었는데, 앱 창이 여는 것은 서비스 루트(`index.html`)이고 그 연결 패널은
  `app/client-bridge.js` 가 그린다. 「주 경로와 정합하게」라는 요구가 **한 층 아래에서 그대로
  반복**됐다 — 저장은 됐는데 읽히지 않는 자리.
- 그 패널을 실제로 **구동해 보니** 첫 호출에서 던졌다:
  `ReferenceError: _status is not defined`. `client-bridge.js` 가 `_status` 를 import 없이
  8곳에서 부르는데 정의는 `connect-modal.js` 의 비-export 지역 함수다. 예외가 호출부
  `openConnectModal()` 까지 올라가 **연결 창 자체가 안 열린다**.
  - 직전 cycle 이 고친 「패널이 끝내 안 켜졌다」(CHG-20260904T123000)와 **화면상 구분되지
    않는다**. 그 처방은 필요했지만 충분하지 않았다.
- 변경
  - `app/client-bridge.js` — `_status` 를 **지역 정의**(순환 import 회피 · 이 모듈의 «의존 0»
    유지) · `_paintResidency` 신설 · `bridgeCall("status")` 를 `discover` **앞에** 호출.
  - `index.html` — 연결 패널에 `#connectClientResidency` 를 **비운 채** 추가.
  - `FUNCTION.md` §P0-AE(상주 안내는 보는 화면에) · §P0-AF(부르는 헬퍼는 그 모듈이).
  - `tests/verify_client_panel_dom.mjs` 신설 — 모듈을 **바이트 그대로 통째 실행**한다
    (`data:` URL). 함수를 떼어내지 않으므로 「추출이 깨져서 vacuous pass」가 성립하지 않는다.
  - `tests/test_web_shell.py` +6 · `verify_residency_dom.mjs` 에 `DQA_JSDOM` 수용.
- **ID 충돌 재발 해소**: main 이 `P0-U`~`P0-X` 를 가져왔다. 트렁크 우선으로 본 cycle 의
  `P0-U/P0-U-1/P0-V` 를 **`P0-AC/P0-AC-1/P0-AD` 로 재번호**하고 `gui.py`·`MODIFY.md` 참조를
  함께 옮겼다. (같은 충돌의 2회차 — 병렬 세션이 같은 feature 문서를 쓰는 한 반복된다.)

## CHG-20260904T172000-ai-claude-wiki-primary-panel — wiki 미러를 주 표면 정합에 맞춤
- Timestamp: 2026-09-04T17:20:00+09:00
- `wiki/Features/feature-0046-native-client.md` §4-3 신설 — 안내가 **닿는 자리**여야 한다는
  교훈 · `ReferenceError: _status` 의 형태와 왜 소스 검사로 안 보이는가 · 검증 하네스가
  스스로를 배신한 3건.
- `wiki/Log.md` append · `wiki/hot.md` 에 「주 표면은 `app/client-bridge.js` 이고
  `ai-connect.*` 는 별도 페이지」와 「그 모듈은 의존 0 — 헬퍼는 지역 정의」를 사실로 추가.
- wiki-lint 32(선재 동일, orphan 0).


## CHG-20260904T140000-ai-claude-inside-app-entry — 앱 창 «안»에서는 다시 띄우지 않는다
- Timestamp: 2026-09-04T14:00:00+09:00
- **앱 창에서 연결을 눌러도 아무 일이 없었다.** `_connectEntry()` 는 연결 이력이 있으면
  `autoLaunch` 로 **스킴을 다시 쏘고** 모달을 열지 않는다. 그런데 이 창은 **이미 그
  프로그램이 연 창**이다 — 「프로그램이 없다」를 전제한 경로가 「이미 있다」인 상황에
  그대로 적용됐고, 패널은 열릴 기회조차 없었다.
- 처방: `clientBridge` 가 있으면 **곧바로 모달을 연다**. 그 안의 패널이 이 컴퓨터의 AI 를
  직접 다룬다. 웹 전용 경로는 **그대로 둔다**(대조군 테스트로 고정).
- [내 AI 실행] 버튼도 앱 창 안에서는 감춘다 — 이미 실행 중이라 눌러도 아무 일이 없다.
- 뮤테이션 4/4 KILL. ⚠ 그중 1건은 하네스가 «생존» 으로 오보했고, 수동 적용으로 실제로는
  잡힌다는 것을 확인했다 — **하네스의 보고를 그대로 믿지 않는다**(이 저장소가 반복해 배운 것).

## CHG-20260904T145000-ai-claude-launch-btn-contract — 실행 버튼 노출 계약 확장
- Timestamp: 2026-09-04T14:50:00+09:00
- CI 적발: `test_connect_gate.py` 가 노출 조건을 **문자열 전체**로 잠가, 조건이 넓어지자 깨졌다.
- 지키는 성질(프로토콜이 없으면 감춘다)은 그대로 두고, 「없다」의 경우가 하나 는 사실만
  반영했다 — 문자열 전체가 아니라 **그 조건이 살아 있는지**를 단정한다.

## CHG-20260904T160000-ai-claude-panel-status-callback — 상태 표시를 호출부가 준다
- Timestamp: 2026-09-04T16:00:00+09:00
- **라이브에서 패널은 떴는데 목록이 영원히 비어 있었다.** 원인:
  `Uncaught ReferenceError: _status is not defined @client-bridge.js:114`.
  `initClientPanel` 을 모달에서 옮기면서 그 함수가 쓰던 **모달 내부 헬퍼를 함께 옮기지도
  주입하지도 않았다.**
- 처방: `initClientPanel(setStatus)` — 상태 표시는 **호출부가 준다**. 이 모듈은 모달의
  내부를 알지 못한다. 콜백이 없으면 조용한 기본값으로 떨어진다.
- **`test_client_bridge_runtime.py` 신설** — 가짜 DOM 을 깔고 모듈을 **실제로 import 해
  호출**한다. 기존 테스트는 전부 소스 문자열 검사였고, 정의되지 않은 이름은 소스에 그럴듯하게
  적혀 있으며 `node --check` 는 구문만 본다. **실행해야만** 드러나는 종류다.
- 역검증: `_status` 정의를 지우면 이 하네스가 3건 FAIL 한다(원래 결함 재현 확인).

## CHG-20260904T161000-ai-claude-wiring-arity — 배선 단정에서 인자 개수를 뺀다
- Timestamp: 2026-09-04T16:10:00+09:00
- 상태 콜백을 넘기면서 `initClientPanel()` 무인자 형태를 잠그던 단정 2건이 깨졌다.
- 지키는 성질은 「플래그를 **결과로** 세운다」이지 «어떻게 부르는가» 가 아니다 —
  인자 개수를 뺐다.


## CHG-20260904T180000-ai-claude-runner-wsl — 러너가 WSL 안의 AI 를 직접 찾는다
- Timestamp: 2026-09-04T18:00:00+09:00
- **잔여 항목 해소**: WSL 런타임을 고르면 웹의 「답할 AI 있음」이 ❌ 로 남던 문제.
  원인은 연결 프로그램이 `--cmd 'wsl.exe -e … {prompt}'` 로 우회한 것이고, `--cmd` 는
  **능력 협상을 돌지 않는다**(그 명령에 모델이 이미 박혀 있다는 전제 — 반영되지 않을 목록을
  띄우지 않으려는 P0-T 의 판단이다). 답변은 정상인데 신고만 없는 상태였다.
- 처방은 우회를 고치는 것이 아니라 **우회를 없애는 것**이다. 러너가 WSL 자리를 직접 알면
  이름만 주면 되고(`--ai claude`) 협상이 그대로 돈다.
  - `_which_ai`: 지정 경로 → PATH → 표준 설치 위치 → **WSL 안** 순.
  - `_resolve_exe`: Windows 에서 **POSIX 절대경로**면 `wsl.exe -e` 를 앞에 둔다.
    ⚠ 이 확장은 **런타임 종류를 바꾸지 않는다** — 그것이 `--cmd` 와 다른 점이다.
  - 조회는 프로세스를 띄우므로 **캐시**한다. 「WSL 없음」과 「그 CLI 없음」을 구분한다.
- `BRIDGE_AI_PATH_<NAME>` — 같은 CLI 가 양쪽에 있을 때 **어느 쪽인지는 연결 프로그램이
  정한다**. 각 후보에게 실제로 물어보고 답한 것을 골랐으므로 러너가 뒤집으면 안 된다.
- 클라이언트: `--cmd` 폐기, `--ai` + 경로 고정.
- 뮤테이션 10/10 KILL (원래 결함 회귀 · 캐시 제거 · 리눅스 오적용 · 클라이언트 회귀 포함).
## CHG-20260904T180000-ai-claude-converge-status-injection — `_status` 처방을 main 의 주입 방식으로 수렴
- Timestamp: 2026-09-04T18:00:00+09:00
- **같은 결함을 병렬 세션도 찾아 다르게 고쳤다**(PR #1572: `initClientPanel(setStatus)` 로
  호출부 주입). 내 처방은 지역 중복 정의였다. **그쪽이 낫다** — 중복 없음 · 순환 없음 ·
  「이 모듈은 모달의 내부 헬퍼를 모른다」가 시그니처에 드러남. 내 것을 버리고 수렴했다.
- 그 위에 상주 안내(`_paintResidency` + `bridgeCall("status")`)를 다시 얹었다. 이것은
  **주입받지 않는다** — 이 패널에만 있는 요소이고 다른 호출부가 달리 그릴 이유가 없다.
- 테스트 수렴
  - `_free_identifiers_called` 를 **바인딩 유무**로 일반화 — `function` 선언만 보면
    `const`/매개변수 바인딩을 자유변수로 오판한다(주입으로 바꾸자 실제로 거짓 양성이 났다).
  - `test_status_writers_in_both_modules_target_the_same_element`(내 중복 정의 전제) 폐기 →
    **`test_modal_injects_a_status_writer_that_actually_exists`** 로 대체. 주입하는 **이름이
    실재하는가**를 본다 — 같은 결함의 한 층 위 형태이고, 그들의 런타임 테스트는 node 부재 시
    `pytest.skip` 이라 CI 에서 아무것도 지키지 않는다.
  - ⚠ 그 단정이 처음에 **주석 줄**을 집었다(§16.7 G11-a) — 코드 줄만 보도록 고쳤다.
- 하네스도 주입 계약으로: 콜백을 넣어 부르고 **그 콜백으로 실제로 말하는지** + 콜백 없이도
  죽지 않는지 확인. 대조군 4종(자유변수 복귀 · 콜백 무시 · 기본값 제거 · 상주값 무시) 전건 적발.
- 회귀 275 passed · 뮤테이션 **5/5 KILL(NOOP 0)**.


## CHG-20260904T200000-ai-claude-standalone-launch — 아이콘만 눌러도 앱이 뜬다
- Timestamp: 2026-09-04T20:00:00+09:00
- **사용자 제보 해소**: 설치 후 시작 메뉴에서 켜면 「연결 정보가 없습니다」만 뜨고, 서비스를
  쓰려면 여전히 브라우저로 주소를 쳐야 했다. 프로그램이 **웹의 부속물**이었다.
- `core.startup_base(home)` — 고정 → 마지막으로 받아들인 딥링크 → 동봉된 배포 기본값.
  각 값은 `http(s)`+호스트를 통과해야 하고(창의 목적지가 된다), **망가진 출처는 건너뛴다.**
- `core.remember_base` / `remembered_base` — 딥링크를 **받아들인 순간** 적는다.
  ⚠ `pin_server` 와 **다른 키**다. 고정은 연결 성공 뒤에만이라는 규율을 지킨다.
  `_write_server_doc` 로 부분 갱신 — 한쪽이 다른 쪽을 지우지 않는다.
- `core.bundled_service_base()` + `build_client.write_service_file` — 배포 기본 주소는
  **빌드가 적는다**(`--service-base`). ⚠ 저장소 소스에 주소를 박지 않는다.
- `core.acquire_single_instance` — OS 잠금(fcntl/msvcrt). PID 파일이 아니다.
- `bridge._plan_for` — 패널이 준 `launch` 봉투가 이긴다. base 불일치는 **네트워크 전에** 거절.
- `client-bridge.js` — connect 직전에 `/api/ai/connect/token` 으로 봉투를 받아 그대로 전달.
  실패해도 connect 는 나간다(딥링크로 켠 창은 이미 값을 갖고 있다).
- `parse_scheme_url` 을 `gui` → `core` 로 이관(두 입구가 같은 파서를 쓴다).
- `tests/conftest.py` 신설 — 이 unit 의 테스트가 **실제 홈을 건드리지 않게**. 없으면 테스트가
  개발 머신의 `~/.dqa-connect` 를 오염시키고, 그 파일 때문에 다른 테스트의 갈래가 바뀐다(실측).
- `core.request_show` / `take_show_request` + 두 껍데기의 소비 지점 — 두 번째 실행이
  대화상자 대신 「창을 열어 달라」를 남긴다(30초 TTL · 읽으면 삭제).
- 뮤테이션 **30/30 KILL**(20 + 사각지대 탐침 4 + 재열기 6). 탐침 4건 중 **2건이 처음에
  SURVIVED** 했고(접두 비교로 스킴 판정 · 빈 값 기록), 그 둘을 잡는 단정을 더해 닫았다 —
  「전건 KILL」은 표본이 내 테스트를 닮았다는 뜻일 수 있어 일부러 어긋나는 뮤턴트를 던졌다.
- codex 외부 적대 리뷰 4건 수정(딥링크 주소 미검증 · 링크가 동봉값을 이기는 순서 · 봉투가 지문을 지움 · 잠금 밖 기록). 상세는 REVIEW.md.


## CHG-20260904T220000-ai-claude-embedded-window — 앱 창을 프로그램이 직접 그린다
- Timestamp: 2026-09-04T22:00:00+09:00
- 사용자 요청: 「DQAConnect.exe 를 별도로 열지 않고 클라이언트 내장으로」.
- `client/window.py` 신설 — WebView2(pywebview `edgechromium`) 호스팅. 닫기=숨김(트레이가
  떴을 때만) · `show()`/`quit()` · 실패는 `False` 로 답해 호출부가 폴백한다.
- `gui.run_client` — **내장 → 브라우저 앱 모드 → tkinter**. 각 단계는 말없이 내려가지 않는다.
- `gui.confirm` — Windows 에서 `MessageBoxW`(+`MB_TOPMOST`). 내장 껍데기는 주 스레드를 GUI 가
  쥐므로 tkinter 대화상자를 부를 자리가 없다.
- `shared/dqa_identity.DISPLAY_NAME = "DQA"` 신설. 설치기는 `MyAppName`(패키징)과
  `MyDisplayName`(아이콘·표시)을 가른다 — AppId·설치 폴더는 그대로라 업그레이드가 이어진다.
- `build_client` — `--collect-all webview/clr_loader/pythonnet` · 의존 자동 설치 ·
  **동결본 `--selftest` 실행 검증**.
- 웹 문구: 앱 창 안에서 보이는 문구에서 「연결 프로그램」 제거(브라우저 방문자용 안내는 유지).
- 실측(Windows): 동결본 자가진단 `{'frozen': True, 'webview_import': True,
  'runtime_present': True, 'available': True}` · 창 제목 `DQA` 가 **이 프로세스의 것** ·
  브리지 포트 동일 프로세스 · 두 번째 실행에도 인스턴스 1개.
- 뮤테이션 **18/18 KILL** — 다만 처음에는 **4건이 살아남았고 전부 내 테스트의 구멍**이었다:
  ① 비-Windows 검사(다른 방어가 되메워 통과) ② **확인창 호출**(소스에 `MessageBoxW` 가 있는지만
  봤다 — 그것을 감싼 `if` 를 `if False` 로 바꿔도 문자열은 남는다) ③ 동결본 자가진단 배선
  ④ 의존 동봉 배선. ②가 이 저장소가 반복해 겪은 **「게이트 뒤 호출을 소스 검사가 못 본다」**
  그 형태다 — 실행하는 단정으로 바꿔 메웠다.
## CHG-20260904T190000-close-to-tray — 닫기는 트레이로, 종료는 우클릭 [종료]

- Timestamp: 2026-09-04T19:00:00+09:00
- 사용자 요청: 「윈도우를 닫을 때 기본적으로 트레이 아이콘으로 남겨두고, 실제 종료는 트레이
  아이콘 우클릭으로」. 골격은 직전 PR #1576(18:58 머지)이 이미 들여왔고, 이 cycle 은 그 골격이
  **사용자가 겪는 상황에서 실제로 성립하는지**를 닫는다.
- `client/window.py` — `Shell.allow_hide`(bool) → **`can_hide`(Callable)**. 닫는 **그 순간**
  판정한다. 판정 불가(예외)면 숨기지 않는다. `on_hidden` 훅 추가(숨김 성립 직후 1회).
  `last_error` 추가 — `can_hide`/`hide`/`on_hidden` 실패를 남긴다(`Tray.last_error` 규약).
- `client/gui.py` — `_tray_alive()` **단일 seam** 신설. tkinter `_tray_live`·`_serve_confirms`·
  두 신규 껍데기가 전부 이것을 부른다(종전엔 tkinter 만 생존 판정, 나머지는 존재 판정).
  `HIDDEN_NOTICE` 공유 상수 + `_hidden_notice()` 1회 콜백 — 문구가 **종료 경로(우클릭 [종료])
  를 명시**한다. tkinter 판의 옛 전용 문구는 이 상수로 수렴.
- `client/bridge.py` — `resident` 를 **읽기 전용 property** 로. 껍데기가 넘긴
  `resident_probe()` 를 매번 새로 부르고, probe 부재·예외는 **거짓**이다. 대입 자리를 없애
  「기동 시점 bool」 형태를 구조적으로 불가능하게 했다(§16.7 G10).
- `tests/windows/verify_embedded_close.py` **신설** — 주 경로(내장 WebView2 창)의 실 Windows
  실측. `hide`/`quit` 2모드(한 프로세스에서 `webview.start()` 가 1회뿐이라 분리).
- 테스트 — 소스-텍스트 단정 2건(`"shell.allow_hide = tray is not None"` ·
  `"br.resident = tray is not None"`)을 **구동 단정**으로 교체. **399 passed(+16, 기준선 383)**.
- 뮤테이션 **16/16 KILL · SURVIVED 0**.
- codex 적대 리뷰 2라운드 — 1라운드 P2(브라우저 껍데기 안내 부재) 대응으로 무신호를 「닫힘」
  으로 읽어 안내를 냈으나, 2라운드가 그 추정을 **P2 로 되받았다**. 확인 결과 옳다: 패널의
  20초 ping 은 `initClientPanel` 안에서만 시작하므로(`client-bridge.js` L178) 연결 모달을
  열지 않은 사용자는 ping 을 아예 보내지 않고, 배경 브라우저는 타이머를 스로틀한다 →
  **창이 열려 있는데** 「알림 영역에 있습니다」를 말하게 된다(§P0-R). **되돌렸다** — 없는
  근거로 말하지 않는다. 그 결정을 테스트 2건으로 잠갔다(추정 금지 · 배선 자리 AST 고정).
## CHG-20260904T233000-ai-claude-shortcut-cleanup — 업그레이드가 옛 바로 가기를 치운다
- Timestamp: 2026-09-04T23:30:00+09:00
- **실측으로만 드러난 결함**: 새 설치본을 덮어 설치했더니 시작 메뉴에 옛 이름과 새 이름이
  **둘 다** 남았다. Inno 는 안 만드는 바로 가기를 자동으로 치우지 않는다.
- `DefaultGroupName={#MyDisplayName}` + `[InstallDelete]`(옛 그룹 폴더·바탕화면·자동시작).
- ⚠ `AppId`·설치 폴더는 **그대로** — 바꾸면 두 벌 설치가 된다. 테스트가 그것을 잠근다.


## CHG-20260905T000000-ai-claude-group-name — 업그레이드가 옛 그룹 이름을 물려받지 않는다
- Timestamp: 2026-09-05T00:00:00+09:00
- **직전 수정의 나머지 절반**(실측): `[InstallDelete]` 로 옛 바로 가기는 사라졌는데 **폴더
  이름이 그대로**였다 — Inno 는 업그레이드에서 레지스트리에 적어 둔 지난 그룹 이름을 쓴다.
- `UsePreviousGroup=no` 한 줄. 이름을 바꾼 의미가 그제야 온전히 도달한다.


## CHG-20260905T003000-ai-claude-live-record — 최종 설치본 라이브 완주 기록 (문서 전용)
- Timestamp: 2026-09-05T00:30:00+09:00
- 코드 변경 없음. `bd5f0821` 로 만든 설치본(sha256 `A6E1123C…`)의 실측을 남긴다.
- 덮어 설치 후 **옛 그룹 폴더 없음** · `DQA\` 에 바로 가기 둘뿐 · 아이콘 실행 시 창 `DQA` 가
  이 프로세스의 것 · 브리지 동일 프로세스.
- 전달 폴더(`C:\Users\mckim\DQA-Connect-배포`) 갱신 — 설치본·sha256·안내문.

## CHG-20260904T195500-close-to-tray-merge — origin/main 병합 + 병합 트리 재검증

- Timestamp: 2026-09-04T19:55:00+09:00
- `origin/main` 8커밋 병합(설치기 그룹 이름·옛 바로 가기 정리·최종 설치본 라이브 완주).
  충돌 2건은 **양쪽이 같은 자리에 새 절/새 cycle 블록을 append** 한 형태 → 둘 다 보존.
- §16.4 해결 결과 검증: 양측 부모 대비 삭제 파일 0 · auto-merge 파일 포함 「그 부모 대비
  삭제만 있는 파일」 0 · theirs 신규 테스트/헤딩 집합 유실 0. 병합 후 **404 passed**.
- 병합 트리 기준 codex 재검증 **결함 0**(REV-20260904T195500).

## CHG-20260904T204500-installed-close-to-tray — 설치본 재빌드·재설치·종단간 확인

- Timestamp: 2026-09-04T20:45:00+09:00
- 코드 변경 없음. `main` `a8f58f46` 기준으로 클라이언트를 재빌드해 덮어 설치하고, 요청 동작을
  **설치본에서 직접 구동**해 확인했다 — push/merge 는 코드 완료이지 사용자 도달이 아니다
  (§16.3 deploy-backed 완료 기준의 클라이언트 배포 대응).
- 설치본 sha256 `bee0c780…` · 25,692,215 bytes.
## CHG-20260907T150000-client-update-channel — 다른 머신이 새 버전을 받는다

**요청 (사용자 2026-09-07)**: 「클라이언트를 배포했을 상황에서 … 다른 머신에서 버전이 올라간
클라이언트를 업데이트 받을 수 있는 구조를 구성」.

**신규**

- `src/client/version.py` — 배포 버전 정본 `CLIENT_VERSION` + `parse`/`is_newer`(수치 비교).
- `src/client/updater.py` — 매니페스트 조회·무결성 4축·적용. 러너 `agent/selfupdate.py` 의
  규율 7개를 이식(고정 출처 · 검사 후 실행 · 같으면 안 함 · 실패는 조용히).
- `feature-0003/src/routers/client_release.py` — `GET /api/ai/client/latest`.
  **실물과 대조해 통과한 것만** 광고하고, 지문은 매니페스트가 아니라 **파일에서** 계산한다
  (mtime+size 키 캐시). `INCLUDE_ORDER=260`.
- `src/scripts/publish_release.py` — 반입(`--setup`) · 롤백(`--activate`) · 정리(`--prune`) ·
  `--check`(서버 모듈을 그대로 불러 **서버 시선으로** 재확인).
- `tests/test_updater.py`(63) · `tests/test_release_channel.py`(15).

**변경**

- `src/client/bridge.py` — `update_check`/`update_apply` 액션, `update_now()` 단일 경로,
  `pending_update`·`on_quit`, `status` 에 `version`·`update`, `DANGEROUS` 에 `update_apply`,
  `_confirm_text(action, body, bridge=None)` 로 확장(확인 문구가 **버전을 말한다**).
- `src/client/gui.py` — 트레이 [업데이트 확인](두 껍데기 공통) · `_start_update_watch`
  (동결본에서만) · `tell()` 에 `MessageBoxW` 우선 경로.
- `feature-0003/src/app.py` — `/client` StaticFiles 마운트(디렉토리 존재 시에만).
- `feature-0003/src/routers/oauth_as.py` — `_client_download_url` 1순위를 릴리스 채널로.
- `src/installer/DQAConnect.iss` — `AppVersion` 폴백 + `/RELAUNCH` 무음 재기동.
- `src/scripts/build_client.py` — `_client_version()` 으로 정본 주입 + 퍼블리시 안내.
- `docker-compose.yml` — `x-web-extra` 에 `../artifacts/client-release:/srv/client:ro`.
- `feature-0043/tests/test_connect_guidance.py` — 함수 본문 추출을 `{0,1200}` 문자 예산에서
  **구조 경계**로 교체. 그 상한은 함수가 조금만 길어지면 매치가 사라져 단언이 「함수를 찾지
  못했다」로 죽었다 — 실제로 이 cycle 이 그 함수에 분기를 더하면서 깨졌다.
- `tests/test_tray_and_windowless.py` — 메뉴 항목 1개 추가 반영 + [종료] 를 **라벨로** 찾도록
  (인덱스를 손으로 세면 다음 항목 추가에서 조용히 다른 것을 누른다).

**되돌린 것**: 없음.

## CHG-20260907T170000-client-update-channel-r2 — 적대 검증 2라운드 반영

1라운드 **BLOCK**(P1 3 · P2 3 · cross-domain 6)과 확인 라운드 **BLOCK**(P1 2 · cross-domain 6)
을 흡수했다. 2라운드 P1 2건은 **1라운드 수정이 새로 넣은 코드**에 있었다 — 그 사실이 아래
구조 변경을 정했다(§18.8 (b) 비단조 신호의 국소 처방이 아니라 판정면 재배치).

**신규**

- `updater.verify_file(path, update)` — **실행할 그 파일**을 다시 센다. `download()` 의 판정
  대상은 스트림이고 `apply()` 의 실행 대상은 디스크 경로다 — 두 스레드로 그 둘이 갈리는 것이
  재현됐다(한 흐름이 검사한 바이트와 그 흐름이 돌려준 파일의 내용이 완전히 달랐다).
- `updater._FLOW_LOCK` + `updater.run_flow(...)` — 순서의 **단일 정본**(확인 → 받기 →
  디스크 재검증 → 유휴 재확인 → 설치기 실행) + 프로세스당 단일 실행. 입구가 셋인데
  (트레이·웹 패널·주기 감시) 게이트가 없어 **미서명 설치기 둘이 동시에** 돌 수 있었다.
- `updater.parse_manifest_detail()` — 「이미 최신」과 「매니페스트를 읽지 못했다」를 가른다.
  전송 계층만 갈라 놓았더니 200+HTML·잘린 JSON·퍼블리시 버전 실수가 전부 「이미 최신입니다」
  로 보고됐다.
- `updater.PENDING_MAX_AGE_SEC` · `_sweep_old_downloads()` — 오래된 표식은 판정하지 않고,
  고정 자리의 잔재는 나이로 잘라 정리한다.
- `gui.check_and_report()` — 세 껍데기가 같은 문구·같은 판정을 쓴다.
- `gui.ClientApp._update` + 트레이 항목 — tkinter 폴백 껍데기에 업데이트 입구가 **0개**였다.
- `routers/client_release.client_download` — `GET /client/{filename}`, **광고 중인 파일만**.

**변경**

- `updater.download()` — `mkstemp` 로 **흐름별 유일** 이름(종전 PID 기준은 같은 프로세스의
  두 스레드를 가르지 못했다). 최종 파일도 흐름별로 유일해 실행 대상이 흔들리지 않는다.
- `updater.update_base()` — **동봉 주소가 고정 주소를 이긴다**. 동봉값은 설치 행위 자체가
  인증한 앵커이고, 고정(TOFU)은 한 번 성공한 딥링크의 주소일 수 있다. 종전 우선순위는
  규율 2 가 세운 세기를 뒤집고 있었다. 동봉값 없는 빌드는 그 사실을 기록에 남긴다.
- `updater.check_detail()` — 죽은 `http-{status}` 분기를 실제 입구(`HTTPError.code`)로 옮겨
  403·500·502 를 한 덩어리로 접지 않는다.
- `updater.SILENT_ARGS` — `/RESTARTAPPLICATIONS` 제거. 재기동 입구가 둘이면 우리가 아직
  살아 있는 사이 새 인스턴스가 단일 인스턴스 잠금에 막혀 **조용히 사라진다**.
- `bridge.act()` — 확인 대상을 **묻기 전에** 고정해 핸들러로 넘긴다.
- `bridge._do_update_apply()` — `or self.pending_update` 폴백 **제거**. 그것이 있으면
  `act()` 의 고정이 무효화돼, 확인창이 「버전을 모른다」고 말한 갈래에서 구체 버전이 설치되고
  주소 불일치 경고까지 비켜 갔다.
- `bridge.update_now()` — `updater.run_flow` 에 위임(순서를 복제하지 않는다).
- `gui._serve_confirms()` — 종료 신호 검사를 루프 최상단으로. 종전에는 `_tray_alive` 블록
  **안**에 있어 트레이 없는 머신에서 `on_quit` 이 무효였다(exe 잠금 유지 → 무음 설치 실패).
- `app.py` — `/client` StaticFiles 마운트 **제거**. 통째로 마운트하면 ① 내린 버전이 계속
  익명 다운로드되고 ② 호스트 디렉토리의 무관한 파일이 공개되며 ③ 기동 시점 `is_dir()` 판정
  때문에 나중에 생긴 디렉토리는 **영구 404** 였다.
- `routers/client_release.py` — 라우트 경로를 **리터럴**로. `gen-routemap.py` 는 데코레이터
  인자의 `ast.Constant` 만 읽어, 표현식이면 ROUTEMAP 에 `?` 로 떨어진다 — 하필 그 인덱스가
  이름을 적을 수 없는 라우트가 익명으로 실행 파일을 서빙하는 표면이 된다.
- `build_client._client_version()` — 정규식을 정본 `VERSION_RE` 와 같은 모양으로.
- `tests/test_release_channel.py` — `or` 절로 무력화된 단언을 **행위 테스트**로 교체
  (내린 버전 404 · 무관한 파일 404 · 마운트 부재 단언).
- `tests/test_updater.py` — 소스 문자열 단언을 **두 스레드 동시 실행** 테스트로 교체 +
  성공/불일치/초과/재검증/단일실행 행위 커버리지.
- `tests/test_tray_and_windowless.py` — 파리티 테스트를 하드코딩 리스트에서 **tkinter 실물
  대조**로. 상수와 비교하면 실물이 갈려도 통과한다(그래서 갈린 것을 몰랐다).
- `docs/ROUTEMAP.md` — 재생성(266 routes).

**되돌린 것**: 없음.
## CHG-20260907T060000-ai-claude-auto-connect — 고를 것이 없으면 묻지 않는다 · 확인창을 알림으로
- Timestamp: 2026-09-07T06:00:00+09:00
- **자동 연결**: 같은 플랫폼이 두 자리에 있을 때만 사람에게 고르게 한다. 그 외에는 패널이
  뜨자마자 연결한다. 시작할 하나는 고정 순서(`claude → codex → gemini`).
  ⚠ 서로 다른 플랫폼이 여럿인 것은 갈림이 아니다 — 러너가 요청마다 런타임을 바꿔 답한다.
- **확인창 제거**(사용자 결정): `Bridge(confirm=…)` → `Bridge(notify=…)`. 동작 **뒤에** 알린다.
  실패·조회는 알리지 않고, 알림 실패가 동작을 되돌리지 않는다.
  ⚠ XSS 시나리오의 마지막 방어선이 사라졌다 — REVIEW.md 에 적었다.
- 자동·수동이 **같은 경로**(`doConnect`)를 쓴다. 갈리면 한쪽만 고쳐진다.
- 전제가 바뀐 테스트 6건을 지우지 않고 **이유를 적어 뒤집었다**(확인 계약 → 알림 계약).
- 뮤테이션 **12/12 KILL**. 처음 10건 중 **2건이 살아남았고 둘 다 내 쪽 문제**였다:
  ① 「자동은 1회」를 지키던 플래그가 **도달할 수 없는 가드**였다(되메우는 것이 호출 지점이라
  등가 뮤턴트) — 지우고 그 성질(«auto 를 주는 자리가 하나»)을 직접 잠갔다.
  ② 「트레이를 알림 전달자에 잇는다」 단정이 이름 존재만 봐서, **잇는 줄만 지운** 뮤턴트가
  통과했다 — 그 상태에서는 알림이 영영 갈 곳이 없는데 코드는 멀쩡해 보인다.

## CHG-20260907T182000-merge-two-decisions — origin/main 병합 (의미 충돌 자율 해결)

병렬 cycle(PR #1589)이 연결·로그인의 사전 확인을 사후 알림으로 **교체**했고, 이 브랜치는 같은
자리에 업데이트 설치의 사전 확인을 **추가**했다. 두 사용자 결정은 같은 날 났고 **대상이 다르다** —
공존시켰다(판정 근거는 `REVIEW.md` REV-20260907T182000).

- `src/client/bridge.py` — `NOTIFIED`(사후 알림) + `CONFIRMED`(사전 확인) 두 판정축.
  `act()` 가 둘 다 수행하고, 확인 대상은 **묻기 전에 고정**해 핸들러로 넘긴다.
  `_notice`/`_confirm_text` 를 별개 함수로 분리(충돌로 본문이 섞였다).
  `Bridge.__init__` 에 `confirm` 복원 — 주지 않으면 「아니요」(fail-closed).
- `src/client/gui.py` — 두 껍데기가 `notify` 와 `confirm` 을 **둘 다** 주입.
- `docs/FUNCTION.md` — 양쪽 절 보존 + 두 결정의 관계를 절로 명시.
- `tests/test_embedded_window.py` · `tests/test_updater.py` — 실 시그니처·판정축 반영.
- `tests/test_web_shell.py` — **main-측 선재 실패 흡수**: PR #1592 가 모듈 import 에 `?v=dev` 를
  붙이면서 문자열 단언이 깨져 있었고, 이 스위트가 CI 경로에 없어 아무 데도 걸리지 않았다.

## CHG-20260907T190000-live-deploy-verify — 라이브 배포 실측 기록 (문서 전용)

- **왜**: `deploy_scope: included` 로 PR #1591 머지 후 배포까지 진행했고, 배포본에서 채널을
  다시 쟀다. §16.3 deploy-backed 는 **머지를 완료로 보지 않는다** — 배포 후 실측이 완료
  조건이므로 그 실측이 문서에 남아야 한다. 코드 변경 0건.
- **무엇**
  - `docs/test-runs.d/20260907T180000-live-deploy-verify.md` 신설 — 채널 실측표 + 배포 자체
    실측 + 배포 중 관측 2건 + 여전히 못 잰 것.
  - `docs/TEST.md` — 새 Run 색인 추가. **그리고 직전 Run 색인의 수치를 상세 기록과 맞췄다**:
    색인은 `478/478 · 신규 96 · 결함주입 8/8` 이었는데 같은 항목의 상세 기록은
    `506 · 신규 124 · 15/15` 이다(적대 2라운드 반영분). 색인이 자기 상세보다 낮은 수치를
    말하고 있었다 — 요약이 근거와 어긋나면 요약을 고친다(§16.7 G14).
  - `docs/REPORT.md` — §1 에 라이브 실측 한 단락, §3 에 머지 SHA·finalize, **§4 배포 결과**
    신설(§4.1 = 배포 중 관측 2건). §2 의 「릴리스 디렉토리 첫 생성」 잔여는 이 인스턴스
    한정 해소로 정정하고 **다른 호스트에는 남는 함정임을 명시**했다.
- **재는 방법의 선택이 안전판이었지만, 절반만이었다**: 실 설치기가 없어 합성 파일로 쟀고
  버전을 정본(`1.1.0`)보다 **낮은 `1.0.0`** 으로 잡았다 — `updater.py` 자동 갱신 경로는
  `is_newer` 가 거짓이라 그것을 집지 않는다. **그러나 사람용 다운로드 표면은 그 밖이었다**
  (`download_url()` 은 버전을 비교하지 않는다) — 아래 적대 리뷰 항목 참조.
- **결과와 어긋나지 않게 적은 것**: 배포 창 안의 13초 엣지 정지는 **행위자를 특정하지 못했다**.
  체크리스트의 `no upstreams available = 0` 이 **엣지 연속성의 증거가 아님**을 명시했다 —
  그 지표는 Caddy 가 죽은 구간을 애초에 셀 수 없다.

## CHG-20260907T193000-review-round1-fixes — 적대 리뷰 1라운드 반영 (BLOCK → 해소)

§18.8 적대 리뷰가 **BLOCK**(P1 3 · P2 5 · P3 5)을 냈다. 지적의 성격이 한쪽으로 몰렸다 —
**대부분이 「내 서술이 내 실측보다 강했다」**(§16.7 G11-a). 그래서 처방은 코드가 아니라
**주장의 범위 축소와 근거 교체**다.

- **P1-1 — 「라이브에 창을 열지 않았다」는 거짓이었다.** `is_newer` 안전판은 `updater.py`
  경로만 덮는다. `client_release.download_url()` 은 릴리스가 **존재하면** URL 을 돌려주고
  **버전을 비교하지 않으므로**(`client_release.py:164`), `oauth_as._client_download_url` →
  `_connect_steps.py:45` 의 **「연결 프로그램 받기」 버튼은 그 안전판 밖**이었다. 실측한 창은
  **08:58:06 → 08:58:43.9, 약 38초**(200 관측 26.2초)이고 그 시각 실제 사용자 세션이 라이브에
  붙어 있었다 — 연결 화면을 연 사람이 없었던 것은 **운**이다. 실피해는 없었다(그 창의 외부
  클라이언트 매니페스트 요청 **0건**). 문서 5곳에서 그 문구를 걷어내고 창을 등재했으며,
  **다음부터는 `CLIENT_RELEASE_DIR` 격리 인스턴스에서 잰다**를 교정으로 적었다.
- **P1-2 — 「11단계 라이브 PASS」의 프로브 채널을 안 적었다.** 전부
  `docker exec repo-web-a-1` → 내부 8000 이며 **엣지 미경유·web-b 미측정**이다. 더 나쁜 것은
  #6~#9 를 잰 08:58:18 이 **caddy 정지 창(08:58:10~08:58:23) 안**이라 엣지를 지날 수
  **없었다**는 점이다 — caddy 로그에 이 두 경로의 200 은 0건. 표 머리에 채널을 명시하고
  「엣지 경유」·「web-b」를 ⛔ 미실측으로 올렸다.
- **P1-3 — 잔여 함정의 처방이 함정을 막지 못했다.** compose 마운트 원본은
  `../artifacts/client-release` 이고 project dir 은 `repo/` 다. `repo/artifacts` 는 **실재하는
  별개 디렉토리**라서, 문서가 지시한 `mkdir -p artifacts/client-release` 를 배포 cwd 에서
  치면 **아무도 마운트하지 않는 미끼**가 생기고 진짜 경로는 여전히 root 소유로 만들어진다
  (§16.7 G14 — 처방이 결과를 내지 못한다). `docker-compose.yml` 주석이 그 오문의 **원천**이라
  함께 고쳤다(이 cycle 의 유일한 비-문서 변경).
- **P2-1** 수치 전수 정정이 미완이었다 — `TEST.md` §2 실행 블록의 `# 478건`(색인을 506 으로
  고친 **같은 파일** 50줄 위)과 `wiki/hot.md` 의 `8/8 · 478/478`(현재형 요약면).
- **P2-2** 배제 논거 셋 중 둘이 부실했다. ①`--no-deps` 근거 **철회** — caddy 는 아무의 의존
  서비스가 아니고, 스크립트는 `--no-deps` 를 붙인 채 caddy 를 직접 만지는 경로를 셋 갖는다
  (`:923` `:937` `:953`). ②**자기 배제 철회** — 「짝이 하나 있다」에서 「두 번째는 내가
  아니다」는 나오지 않고, 같은 세션이 그 창에 라이브를 조작 중이었다. ③탐색 범위에 `Makefile`
  추가(`make up`·`web-down`·`web-tls-down` 의 `stop caddy`). 대신 **더 강한 증거로 교체** —
  `docker inspect` 가 이것을 **기존 컨테이너 stop/start** 로 특정하며(recreate 아님·데몬
  재시작 아님) 그것이 스크립트의 모든 recreate 경로를 배제한다.
- **P2-3** 배포 후 체크리스트 **[4](PB-0008 사용자 표면) 미이행**을 미실측에 올렸다.
  `Windows-browser 없음 — 웹 자산 변경 0건` 은 **check #13** 의 면제 논거이며 **[4] 의 면제가
  아니다** — 둘을 접었던 것을 정정. 하필 이 cycle 의 사용자 표면이 그 38초 동안 나타났다 사라진
  그 버튼이다.
- **P2-4** 경로 탈출 칸은 **항진명제**였다. 받은 것은 `{"detail":"Not Found"}` =
  Starlette 라우트 미매칭이고, 이 라우트의 404 는 `{"error":"not_found"}` 다. `{filename}` 이
  단일 세그먼트 컨버터라 다중 세그먼트는 **어떤 코드 상태에서도** 핸들러에 닿지 않는다 —
  되돌려 FAIL 시킬 수 없는 칸이므로 「11 PASS」를 **10 PASS + 1 미경유**로 고쳤다.
- **P2-5** `no upstreams available = 0` 논증의 뒤 절도 과했다 — 롤링 창에 caddy 가 받은
  요청이 정적 4건뿐이라 **발화시킬 요청이 거의 없었다**. 「그 창에 요청이 있었다는 전제
  아래에서만 약한 증거」로 강화하고 동반 지표(`grep -c 'handled request'`)를 적었다.
- **P3** 행위 종류 특정(`docker inspect`) · 13초 창의 요청 **0건** · 체크리스트 [3] 후반
  (하드 리프레시 안내) **미이행** 명기 · `LRN-20260907-0001` 의 `verified` 값 정정 ·
  앞 cycle 미체크 항목의 종결 표시.

## CHG-20260908T113000-bridge-token-env
- Timestamp: 2026-09-08T11:24:21+09:00; session: Codex ai/codex/feature-0043-bridge-token-env.
- REQ-20260908-client-only: 클라이언트 회귀 테스트를 현재 이벤트 등록·실패 안내·앱 내부 실행 버튼 숨김 경로에 정합.
- 검증 정본: feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260908T113000-bridge-token-env.md.

## CHG-20260908T020049-brand-icon

- 사용자 요청: DQA 아이콘 제작 및 설치 파일 포함 적용, 추가로 공식 마상소프트/마상게임즈 심볼 방향 반영. 웹 테마 확장은 사용자 선택으로 제외.
- `client/assets`, `branding.py`, `gui.py`, `window.py`, `tray.py`: 마상 계열 각진 Q·데이터 심볼과 단일 자산 경로.
- `build_client.py`, `DQAConnect.iss`, `version.py`: 앱/설치기 아이콘 동봉 및 1.1.2(동시 병합된 러너 복구 1.1.1 포함). 기존 버전 설치기가 남은 출력 폴더에서 잘못된 파일을 결과로 보고하던 glob 선택을 현재 버전의 정확한 경로로 교정.
- `tests/test_packaging.py`: 이전 설치기가 남아 있어도 현재 버전의 이름·해시를 보고하는 행위 회귀. Windows `verify_brand_icon.py`: PE 리소스·동봉 자산·실제 네이티브 아이콘 픽셀 비교.

- Windows 실측 후 ICO 인코딩 교정: Tk 8.6의 PNG 프레임 확대 문제를 16~128px DIB + 256px PNG 혼합 인코딩으로 해소. `export_icon.py`로 변환을 재현한다.
## CHG-20260908T120000-runner-update-recovery

- Related TASK: TASK-20260908T120000-runner-update-recovery; REQ-20260908-runner-update-recovery; 위험도 Minor.
- 변경과 이유: 설치 시 직접 덮어쓰기를 없애고 러너와 같은 임시파일·fsync·replace·sidecar 락 규약을 적용한다. 자기가 띄운 러너를 감독하여 1/2/4/8/16초 백오프로 최대 5회 재기동한다. 60초 이상 정상 생존하면 예산을 재설정한다. 정상 종료 또는 복구 소진은 연결 단절 알림, 명시적 연결 해제·앱 종료는 재기동 취소다. stdout/stderr를 계속 비워 파이프 막힘과 파싱 전 오류 유실을 방지한다.
- 동반: 기존 테스트의 전역 app stub 누출·실제 CLI 탐지 누출·낡은 UI 문자열 범위 판정을 바로잡았다. native suite를 Makefile과 CI 양쪽에 등록했다.
- 검증: `unit/feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260908T120000-runner-update-recovery.md`. 되돌리기: 해당 cycle Git revert 후 서버 재배포; 앱 채널은 기존 1.1.0 재활성화 가능하나 이미 설치된 최신본은 자동 강등하지 않는다.

## CHG-20260908T112500-runner-client-only-verification

- 사용자 후속 지시를 현재 TASK에 기록: 별도 러너 실행 절차 없이 DQA 앱만 사용한다.
- 변경 범위는 문서·실측 결과 보충이며 이미 구현한 소유 자식 감독 계약과 일치한다.
- 템플릿 main v3.54.1 병합 후 정책 변경 구간과 지문을 재확인했다.

## CHG-20260908T114000-runner-recovery-postdeploy

- Related TASK: TASK-20260908T120000-runner-update-recovery.
- PR #1606 및 서버·DQA 1.1.1 채널 배포 완료와 실제 앱 업데이트 조회·다운로드 검증을 TASK/REPORT/test-runs에 기록한다. 제품 코드·FUNCTION·정책 변경 없음.

## CHG-20260908T024000-brand-release-version
- Related TASK: TASK-20260908-brand-icon
- 사유: #1606 러너 복구의 1.1.1이 먼저 배포되어 같은 버전을 다른 설치기로 덮어쓰지 않는다.
- 변경: main의 러너 복구를 보존하고 아이콘 적용판 version.py·Inno Setup을 1.1.2로 정합. GUI/빌드 자동 병합과 FUNCTION/TASK/STATUS 충돌을 양 부모 기준 검토했다.
- 검증: 최종 524 PASS, ruff PASS, Windows 재빌드·5개 표면 아이콘 픽셀 일치 PASS. 증적은 test-runs.d/20260908T020049-brand-icon.md.

## CHG-20260908T024200-brand-main-doc-sync
- Related TASK: TASK-20260908-brand-icon
- #1609의 문서 말미 충돌을 양쪽 보존으로 해결했다. 클라이언트 배포 소스와 설치기는 기존 1.1.2 실측본과 같다. 변경된 웹 계약 테스트를 재확인한다.

## CHG-20260908T024500-brand-merge-evidence
- Related TASK: TASK-20260908-brand-icon
- #1609/#1610 후속 문서 병합 결과를 기록한다. 16c5818a와 11fa3741 고정 부모 각각의 문서 제목·추가 파일 유실 0. 클라이언트 배포 소스는 Windows 실측 1.1.2와 동일하며 변경 웹 계약 검사 86건 PASS.

## CHG-20260908T024700-brand-published
- Related TASK: TASK-20260908-brand-icon
- PR #1608 병합 및 1.1.2 라이브 릴리스 완료. TASK/REPORT/검증 기록·릴리스 노트에 실제 엣지 다운로드 200, 26,023,355 bytes, 검증 빌드와 SHA-256/byte 동일을 기록했다. 코드·아이콘 자산 변경 없음.
## CHG-20260908T-transparent-taskbar
- Related TASK: TASK-20260908T-transparent-taskbar; issue #1612.
- 사유: 사용자 제보로 기존 5표면 검사가 Windows 작업 표시줄 식별자와 실제 버튼을 포함하지 않았음을 확인. 투명 배경 요구와 승인된 SVG 정리 방식 반영.
- 변경: 프로세스와 실제 창·시작 메뉴/바탕화면/자동실행 바로가기는 Masangsoft.DQA.Connect ID를 공유한다. 작업 표시줄 재실행 명령·표시 이름·아이콘을 명시하고 현재 실행 인자를 저장하지 않는다. Tk는 최종 HWND가 정해지는 Map 때 적용하며 실제 창 파괴 직전에만 속성을 VT_EMPTY로 해제한다.
- 검증 정본: feature-0046-native-client/docs/test-runs.d/20260908T-transparent-taskbar.md.

## CHG-20260908T035000-transparent-verification

- Related TASK: TASK-20260908T-transparent-taskbar / #1612
- 로그인·사이드바·빈 대화·관리 사이드바 로고 이미지 4곳을 같은 SVG로 정합했다. 기존 크기와 배치는 유지한다.
- 실제 잠금 화면이 작업 표시줄 캡처를 가리는 경우를 검수 도구에서 차단한다. 정상 종료 이전 PASS 기록도 바로잡았다. 최종 시각 확인과 배포는 잔여 단계로 명시한다.

## CHG-20260908T035400-transparent-main-evidence

- Related TASK: TASK-20260908T-transparent-taskbar / #1612
- main 동기화 문서 충돌 4개는 양쪽 신규 기록을 모두 보존했다. 544cfed9/a92c9256 양 부모 삭제 파일·문서 제목 유실 0, 자동 병합 코드 포함 대조. 8231cffe 대비 native src 변경 0이므로 검증된 1.1.3 빌드와 동일하다.
- 병합 후 native 536 PASS(50.204초), 웹 30 PASS. 디자인 추가 리뷰도 P1/P2/P3 0.
- 동결본 속성·리소스·종료는 PASS지만 잠금 화면으로 최종 taskbar PNG는 NOT-RUN으로 남긴다. 일반 브라우저 결과를 앱 전체 검증으로 합산하지 않는다.

## CHG-20260908T035530-transparent-handoff

- Related TASK: TASK-20260908T-transparent-taskbar / #1612
- draft PR #1617·검증된 1.1.3 후보·잠금 해제 후 재검수/배포 순서를 인계한다. 원격 CI check가 보고되지 않아 CI PASS로 주장하지 않는다.
- 별도 검사 DQA 두 인스턴스는 정상 exit=0, 별도 Chrome/relay만 종료했다. 기존 사용자 앱과 프로필은 유지했다. 제품 코드 변경 없음.
## CHG-20260908T123400-connect-discovery — AI별 자동 연결과 클라이언트 위치 재사용 (#1615)
- Timestamp: 2026-09-08T12:34:00+09:00
- Related TASK: TASK-20260908T120000-connect-discovery-ux
- 이유: 모든 AI를 하나의 선택으로 묶던 흐름을 플랫폼별로 바꾸고, 매번 위치를 고르는 비용과 잘못된 완료 알림을 줄인다.
- 변경: DQA 클라이언트를 실행하고 로그인하면 설치된 AI를 찾는다. AI별 사용 가능한 위치가 하나이면 자동 연결하고, Windows/WSL 배포판/계정 여러 곳에 있으면 해당 AI 카드에서만 선택한다. 이미 고른 위치가 다시 유효하면 자동 재사용한다. 별도 러너·Windows 브라우저 실행은 사용자 절차에 없다.
- 통합: main `8f49f1fc`의 아이콘/감독 프로세스/WSL 토큰/네트워크 개선을 보존했다.
- 검증: 이번 TASK의 test-runs.d 기록 및 REVIEW index를 참조한다. 코드 정본 탐색은 기존 core/bridge/client-bridge 앵커와 ROUTEMAP을 사용했고 새 인증 endpoint로 ROUTEMAP을 재생성한다.

## CHG-20260908-connect-discovery-main-integration

- Timestamp: 2026-09-08T12:58:44+09:00
- TASK: TASK-20260908T120000-connect-discovery-ux
- 최신 main의 연결 안내·행위 검증과 현재 자동 연결 변경을 통합했다. DQA 실행 버튼은 앱 내부에 노출하지 않고, 일반 브라우저 호환 경로의 무응답은 실제 존재하는 DQA 앱/버튼으로 안내한다. 네이티브 코드 재변경 없이 527건 PASS, 수집 계약 18건 PASS.

## CHG-20260908-connect-release-evidence

- TASK: TASK-20260908T120000-connect-discovery-ux / Issue #1615
- 최종 DQA 1.2.0 실행 파일에서 첫 연결과 재시작 선택 재사용을 확인한 JSON을 보존했다. native 픽셀 캡처 불가와 서비스/API/벤더 대역 범위를 명시했다. 설치기 26,037,943 bytes, SHA-256 `a808db762c37688e1f4ab4a54249d0d09b40d8ac96430293be21ab79205a9692`.

## CHG-20260908T041713-connect-published

- TASK: TASK-20260908T120000-connect-discovery-ux / Issue #1615
- 이유: 코드 완료와 라이브 배포·설치기 반입을 구분해 후속 세션이 현재 결과를 확인하도록 한다.
- 결과: PR #1619 / 서버 92cfa2c2 전체 배포 완료, DQA 1.2.0 공개, 실제 수신 26,037,943 bytes/SHA-256 일치. 실제 native fixture 결과와 픽셀 캡처 미확인을 분리했다. 소스 코드 변경 없음.

## CHG-20260908-update-install-recovery — 실제 업데이트 롤백 수정
- Related TASK: TASK-20260908-update-install-proof; issue #1622.
- 실제 Windows 1.1.2 업데이트 메뉴→확인→설치에서 고아 내장 Python의 파일 잠금으로 1.2.0 설치가 exit 5 롤백하는 결함을 재현했다.
- 1.2.1: 설치기의 강제 종료 대상을 패키지 실행 파일 세 개로 제한하고, Windows 기본 자동 재시작을 명시적으로 꺼 `/RELAUNCH`만 사용한다. 설치 상세 로그도 기본 활성화한다.
- 기존 1.1.2 업데이터에도 적용되도록 수정의 핵심을 새 설치기에 두었다. 전역 프로세스 이름 kill이나 외부 Python 정리는 사용하지 않는다.
- 검증: updater/supervisor 95 PASS. Windows 빌드·실제 업데이트 재검증 결과는 후속 기록에 추가한다.

## CHG-20260908-update-install-evidence-eol — Windows 증적 정규화
- Windows 생성 증적의 CRLF를 저장소 LF로 정규화했다. 원본은 Windows 임시 작업 폴더에 보존하며 결과 값은 동일하다.

## CHG-20260908-update-install-measured — 실제 업데이트 설치 성공
- 1.2.1 공개 후 기존1.1.2 메뉴에서 설치·자동 재시작·최신 버전 확인 완료. 고아 프로세스 수동 종료 없이 회귀 상황 그대로 PASS.
- setup둘exit0(43.737초), 같은 경로의 새DQA1개, 실제 exe/다운로드 SHA, pending해소, applyok, 5초 안정 실행 대조. 원본 증적과 전체 압축 설치 로그 보존.
- FUNCTION/REPORT/TASK를 현재 설치·배포 상태로 동기화했다. 제품 코드는 직전 검토 후 바뀌지 않았다.
## CHG-20260908T151000-codex-connect-fix
- Related TASK: TASK-20260908-codex-connect-fix; Issue #1625.
- core: PermissionError 및 CLI 권한 실패의 안전한 상태 코드, 진단 출력과 실제 OK 응답 분리.
- discovery: gh-runner 신규/기존 캐시 제외, 권한 실패가 성공 캐시로 덮이지 않음.
- bridge: AI별 selection_id 유지/갱신 및 해당 receipt만 수락. 다른 AI 추가 시 기존 선택 id 보존.
- native1.2.4 버전, 실제 설치용 Windows 빌드. runner/UI 변경은 각 기능 MODIFY에 기록.
- 검증: native 회귀·DOM12시나리오·독립 패널, 실제 설치본 업데이트/AI 요청은 후속 증거로 분리.
## CHG-20260908T150900-codex-text-interaction — 텍스트 상호작용 복구
- Timestamp: 2026-09-08T15:09:00+09:00; Session: codex text-interaction; Issue #1626.
- `Shell.run`의 text_select 기본 False를 True로 바꿔 pywebview의 전역 선택 차단을 제거했다.
- loaded 이벤트에서 소유 UI 스레드로 WebView2 기본 검색 단축키를 활성화했다. 디버그/개발자 도구는 비활성 상태를 유지한다.
- 네이티브 버전 1.2.3 빌드; 동료 작업의 1.2.4와 구분한다. 첨부 본문 CSS·줄번호 제외 규칙을 유지한다.

## CHG-20260908T151800-codex-text-published — 공개 채널 검증 기록
- Timestamp: 2026-09-08T15:18:00+09:00; Session: codex text-interaction.
- PR #1628 병합·1.2.3 공개채널 다운로드 크기/SHA 일치 기록. 검색 UI NOT-RUN과 Issue #1626을 유지한다.
- 변경은 현재 문서·검증 JSON 및 증거 파일의 불필요한 실행비트 정리다. 제품 코드 변경 없음.

## CHG-20260908T152700-codex-release-integration
- Related TASK: TASK-20260908-codex-connect-fix; product PR #1631.
- 공개1.2.3을 통합하여1.2.4로 올렸다. 텍스트 선택/검색 개선을 보존했다.
- native544 PASS, runner 집중119 PASS, DOM12 PASS, Windows 설치기26,045,699bytes/SHA a0535a088c9d000e776b12f5b817d311b7bce1f82da890b3dcee1cb02b494429.
- merge commit의 combined diff를 검증 도구가 일반 cycle delta로 인식하지 못해 이 통합 결과를 일반 문서 commit에도 기록한다. 실제 사용자 검증은 아직 배포 후 일정이며 PASS로 표기하지 않는다.

## CHG-20260908T153000-codex-prompt-integration
- Related TASK: TASK-20260908-codex-connect-fix.
- PR1627의 프롬프트 전달 계약 수정을 통합하고 양 작업의 문서 기록을 보존했다. 네이티브 소스/빌드 변화는 없다. 관련 runner 회귀를 추가 검증한다.

## CHG-20260908T153300-codex-integration-verified
- Related TASK: TASK-20260908-codex-connect-fix.
- 최신 main 통합 뒤 prompt delivery/선택 회귀39 PASS, native544 및 heartbeat집중119 PASS 결과를 현재 출하 기록에 연결했다. 설치기 바이트는 기존1.2.4 빌드와 동일하다.

## CHG-20260908T155000-codex-actual-proof
- Related TASK: TASK-20260908-codex-connect-fix.
- PR1631/8f1116cf 전체 배포, 실제 DQA1.2.3→1.2.4 업데이트 설치와 root Codex 새 대화 왕복 증거를 문서화했다. Permission denied 현장 미재현 및 UIA/픽셀 증거 경계도 기록한다.

## CHG-20260908T160200-codex-verified-closeout
- Related TASK: TASK-20260908-codex-connect-fix.
- PR1633/7ca6f2a4 웹 배포 후 실제 설치 DQA에서 안내 문구 정상 표시·root 자동 복원 확인,1.2.4 최신 버전 확인 및 배포 범위를 증거와 함께 기록. 이 후속은 비정책 문서·JSON만 변경한다.
## CHG-20260908T125500-share-client-entry-deeplink

- Related TASK: feature-0003 `TASK-20260908T125500-share-client-entry` (웹 계약 소유).
- `client/core.py`: `MAX_APP_PATH` · `safe_app_path()`(정본 `shared/dqa_identity` 의 사본 —
  동결 배포본이라 import 하지 않는다) · `parse_scheme_url` 의 `path` 수용(부적격이면 키만
  버림) · `ConnectPlan.path` · `request_show(home, path)` + `show.path` 별도 파일 ·
  `take_show_request` 반환 계약 bool → `str | None`.
- `client/gui.py`: `--path`(SUPPRESS) · plan 주입 시 재검증 · 이미-실행 분기가 목적지 전달 ·
  `_run_embedded`/`_run_browser_shell` 이 `panel_url(…, plan.path)` ·
  `_watch_show_requests(…, plan, br)` 가 `navigate` 후 `show` · `_serve_confirms` 의
  `reopen(dest)`.
- `client/window.py`: `Shell.navigate(url)` 신설 — 실패는 `last_error` 로 남기고 삼킨다
  (여기서 예외를 올리면 폴링 스레드가 죽어 「창 열기」 자체가 영영 안 된다).
- `tests/test_wsl_and_scheme.py`: 정본↔사본 **경로표 대조**(`_PATH_TABLE`) · 왕복(서버 조립
  → 클라이언트 파싱) · 토큰 부재 · 구버전 degrade · plan 도달.
- `tests/test_standalone_launch.py`: 목적지 전달 5건 추가, 반환 계약 변경 반영.

## CHG-20260909T120000-client-125-share-entry

- Related TASK: TASK-20260909T120000-client-125-share-entry.
- `src/client/version.py`: `CLIENT_VERSION` **1.2.4 → 1.2.5**. 제품 로직 변경 0 — 이 릴리스가
  나르는 것은 2026-09-08 에 머지된 딥링크 목적지 수용(`safe_app_path` · `parse_scheme_url` 의
  `path` · `ConnectPlan.path` · `Shell.navigate` · `request_show(home, path)`)이며, 그 코드는
  이미 main 에 있으나 **설치본에는 없다**(1.2.4 가 그 머지보다 앞선다).
- 빌드·게시 산출물은 커밋 대상이 아니다(러너와 같은 규약) — 반입 경로는 호스트
  `artifacts/client-release`.
- `src/installer/DQAConnect.iss`: `#define AppVersion` 폴백 **1.2.4 → 1.2.5**. 빌드는
  `/DAppVersion=` 로 정본을 주입하므로 산출물은 이미 옳았지만, 폴백이 갈리면 **손으로 ISCC 를
  부른 설치기**가 파일명과 프로그램이 말하는 버전을 서로 다르게 갖는다.
  `tests/test_updater.py::test_iss_version_matches_the_canon` 이 이 어긋남을 잡아냈다 —
  버전 상수 1줄만 고치면 되는 줄 알았던 변경이 실제로는 두 곳이었다.
- `unit/feature-0003-agent-web-ui/src/static/release-notes-data.js` (cross-feature):
  2026-09-09 블록에 1.2.5 항목 + 요약 한 줄. 종전 클라이언트 버전은 전부 항목이 있는데 이것만
  없었고(적대 리뷰 MED-1), 9월 8일 노트가 「새 앱 버전을 받으신 뒤에만 성립합니다」라고 적어 둔
  그 버전이 바로 이것이다. **정적 자산 변경이므로 웹 재배포가 필요하다.**
- `unit/feature-0046-native-client/tests/test_updater.py`:
  `test_the_build_and_the_iss_use_the_same_version_shape` 의 첫 단정이 **죽어 있던 것**을
  복구했다(적대 리뷰 L1) — 패턴이 `"` 앞 백슬래시를 요구해 어떤 빌드 파일에도 맞지 않았고,
  `or` 뒤 느슨한 절만으로 통과했다. 즉 「빌드 정규식이 정본과 같은 모양인가」를 아무도 보고
  있지 않았다. 뮤턴트로 봉인 확인(빌드 정규식을 `[0-9.]*` 로 느슨하게 하면 적색).

## CHG-20260909-nondisruptive-update — 사용 중 설치와 다음 실행 적용
- Timestamp: 2026-09-09T17:21:32+09:00
- 원인: 설치기가 실행 중인 앱·내장Python을 덮어쓰며 강제로 종료하고, updater가 spawn 직후 성공·재시작으로 처리했다.
- 변경: 불변 버전 폴더·실행검사·원자 포인터·고정 런처; 전역 설치잠금과 배타적 슬롯 확보; updater 종료/활성대상 검증과 앱생존; 준비/실패 GUI 안내. 1.3.0.
- 독립 리뷰 수정: pointer 읽기의 삭제 공유, rename 오류5/32/33 제한 재시도, legacy 복원 fallback, 기존 실행경로 호환, tkinter 완료 안내와 bridge 준비버전 표시.
- 근거/제한: [원장](test-runs.d/20260909-nondisruptive-update.md). 제어된 러너와 실제 AI 대화 검증을 구별한다.

## CHG-20260909T173353-nondisruptive-shipping — 출하 증적 정합
- Timestamp: 2026-09-09T17:33:53+09:00
- 제품PR1663 병합,1.3.0 공개채널·다운로드바이트·웹배포 증적을추가하고 FUNCTION/REPORT/TASK를정합한다. Windows복사JSON·검증script의불필요한실행권한을644로정규화했다. 제품코드변경없음.

## CHG-20260910-transparent-icon-release — 최신1.3.0 통합과 투명 아이콘 출하 준비
- Timestamp: 2026-09-10T11:11:47+09:00
- TASK: TASK-20260910-transparent-icon-release
- 1.3.1 버전, 안정launcher/ICO, 기존launcher 교체, 실패활성화차단, 실패완료안내, 신규/upgrade제거 정합. 옛1.1.3후보미게시. mainDOM테스트nonce기대값정합.
- native624/웹30/노트34·실제Windows설치/아이콘/실패/제거 증적: [원장](test-runs.d/20260910-transparent-icon-release.md).

## CHG-20260910T111451-icon-integration-record
- Timestamp: 2026-09-10T11:14:51+09:00
- merge commit combined diff에서 checkbox/CHG/review 항목을 읽지 못한 post-commit 검사에 대해 정상 후속 커밋으로 이번 cycle 완료 기록을 추가한다. 제품 bytes는 변경하지 않는다.
## CHG-20260910T114000-icon-shipping-closeout
- Timestamp: 2026-09-10T11:40:00+09:00
- Related TASK: TASK-20260910-transparent-icon-release
- 1.3.1 공개 및 public/localhost 다운로드, 실제 기본 DQA 로고/작업 표시줄, 웹 ready/soak 증적을 기록했다. 캡처 하네스는 기존 .NET Drawing, DPI 인식과 자기 창 가림 방지/원복을 사용한다. 사용자 설치/프로세스는 보존했다.
- [출하 원장](test-runs.d/20260910-transparent-icon-release.md).
## CHG-20260910T113000-inapp-update

- Session: codex:root:01a08911-d62c-7d32-85cc-893b77a3161f
- Related TASK: TASK-20260910-inapp-update
- Reason: 매 갱신 때 설치기를 실행하던 동작을 앱 내부 ZIP 적용으로 바꾸라는 사용자 요청.
- Changes: 1.4.0 updater는 Update ZIP만 수신한다. 경로·압축량·무결성·실행 검사 후 새 슬롯을 활성화하고 현재 프로세스를 유지한다. builder/publisher/server는 Setup/ZIP을 같은 채널로 게시·철회하고 동시 게시 및 원본 변조를 거부한다. 기존 설치기와 공통 mutex, 같은 버전 불변 파일, 제거 시 소유 slots 정리를 적용한다.
- Migration: 1.3.x 이하의 최초 전환만 기존 앱 내 설치기 경로가 필요하다. 1.2.x의 기존 자체 종료는 소급 변경할 수 없다.
- Verification: test-runs.d/20260910-inapp-update.md에 CLI/실제 Windows/채널 축을 구분 기록.

## CHG-20260910T114600-latest-main-integration
- Timestamp: 2026-09-10T11:46:00+09:00
- c684d12a의 1.4.0 제품·템플릿 v3.54.3을 통합했다. origin/main 대비 제품 변경은 본 cycle의 Windows portproxy 운영 코드뿐이고 native 변경은 테스트 하네스뿐이다. FUNCTION은 최신1.4.0 계약을 보존한다.
- 정책 diff는 template_version 한 줄이며 본문 계약은 동일하다. 현재 AGENTS SHA256 21286d42d52a987af6bed233fb5c050b429ddfa77d33b4979fea3acb4a17fdef.
