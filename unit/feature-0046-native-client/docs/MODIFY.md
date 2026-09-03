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
