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
