---
run_at: 2026-09-03T12:00:00+09:00
session: ai/claude-corp/feature-0043-runner-name-dqa-connect
scope: runner-name-dqa-connect (명칭 SSOT · 배선 도달 · 하드 컷오버 · 옛 잔재 정리)
verdict: PASS-PENDING-LIVE
---

# TASK-20260903T120000 — 검증 기록

## 1. 단위 (Environment: CLI)

| 대상 | 결과 |
|---|---|
| 신규 `test_name_ssot.py` | **12건 PASS** (로컬 py3.12 · 컨테이너 py3.11 양쪽) |
| feature-0043 + 0041 합본 | 실패 **14건** — `main`(base `c7e23a68`)과 **차집합 0** |
| feature-0003 | 실패 **7건** — `main` 과 **차집합 0** |
| 격리 실행 | 위 21건 전부 PASS = 선재 order-dependent flake |
| py3.11 컨테이너 (`mysql-ai-agent:c56031d2`) | 실패집합이 로컬 py3.12 와 **동일** — 문법·버전 괴리 0 |
| ruff (프로젝트 설정) | 2건 — worktree·main 동일(선재) |
| `sh -n bridge_setup.sh` | OK · `bridge_setup.ps1` UTF-8 BOM 보존 확인 |

## 2. 결손 주입 실증 (§16.7 G11-b)

격리 사본(모수 8파일 동일 상대배치)에서 **baseline 무결(8 passed) 확인 후** 주입:

| # | 주입한 결함 | 판정 |
|---|---|---|
| M1 | 설치 스크립트 하나만 옛 스킴으로 남김 | KILL |
| M2 | 러너 홈만 개명 누락 | KILL |
| M3 | Windows 판 스킴만 갈림 | KILL |
| M4 | MCP self-name 만 옛 이름 | KILL |
| M5 | Linux MimeType 배선 누락(값은 맞음) | KILL |
| M6 | 웹이 정본 헬퍼 대신 자체 조립 | KILL |
| M7 | 옛 스킴을 xdg 기본 핸들러로 재등록 | **1차 SURVIVED → 교정 후 KILL** |
| M7c | macOS 번들에 옛 스킴 병기 | KILL |
| M8 | 정리 가드 제거(남의 디렉토리도 삭제) | KILL |
| M9 | 정리 함수 호출만 삭제(정의는 남김) | KILL |
| M10 | POSIX 경로 정규화 제거 (끝 슬래시 구멍 부활) | KILL |
| M11 | 우리 설치물 표지 검사 제거 (남의 디렉토리도 삭제) | KILL |
| M12 | Windows 판 경로 정규화 제거 | KILL |

**⭐ 자체 감사가 실 결함 1건을 잡았다 (M10·M11·M12 의 계기).** 위 M1~M9 를 돌린 뒤 정리
로직을 손으로 다시 읽다가, 가드가 **문자열 비교**라 `BRIDGE_HOME` 을 옛 경로에 **끝 슬래시
포함**으로 준 사용자의 **현행 홈**이 삭제 대상이 된다는 것을 발견했다. 「옛 이름을 계속 쓰겠다」는
명시적 선택이 데이터 삭제로 처벌받는 형태다. 경로 정규화로 고치고, 그 구멍을 **행위 테스트**
(실제 `sh` 로 정리 함수를 돌려 디렉토리 잔존 여부를 본다)로 잠근 뒤 M10~M12 로 재확인했다.

**M7 생존이 이 실증의 값이다.** 초판 단언은 「옛 이름이 쓰인 줄에 `LEGACY` 가 있어야 한다」
였는데, 옛 이름을 담은 변수가 `DQA_LEGACY_SCHEME` 이라 **그 변수를 등록에 쓰면 검사를 그대로
통과**했다 — 자기 문구가 자기 단언을 통과시키는 항진명제(§16.7 G11-a). 검사축을 이름
부분문자열에서 **등록 동사**로 내려 재주입 3종 전건 KILL.

⚠ 그 다음 라운드는 **baseline 이 `1 error`** 였다(docstring 편집이 테스트 파일을 깨뜨림).
그 상태의 KILL 은 전부 무의미하므로 고치고 재실행했다 — 위 표는 **무결 baseline 기준**이다.

## 3. 하네스 회귀 자체 적발 (개명이 드러낸 것)

| 무엇 | 어떻게 위장했나 | 조치 |
|---|---|---|
| 셸 조각 하네스에 명칭 변수 미정의 | `parameter not set` → **15건이 「테스트 실패」로 보임** | `tests/_setup_slice.py` 신설 — 정본에서 대입문을 떼어 붙인다(값을 하네스가 지어내지 않는다) |
| `compose_launch_commands` slice-exec | `NameError: _ident` | 실제 `shared/dqa_identity` 를 ns 에 주입(스텁 아님) |
| ps1 다운로더 추출기가 작은따옴표 줄만 수집 | 보간용으로 바꾼 `req = …` 줄이 **조용히 누락** → `NameError: req` | 큰따옴표 줄도 수집 + `$DqaXxx` 를 ps1 자신의 대입값으로 전개. `test_l5` 의 **복제 루프 제거**(한쪽만 고쳐진 원인, §16.7 G10) |

## 4. 미수행 (Environment: 미실측 — 은폐하지 않는다)

- **실 OS 핸들러 재등록·옛 잔재 삭제** — 사용자 머신에서 setup 재실행이 필요하다. 이 저장소의
  테스트는 스크립트가 **무엇을 하는지**까지 잠그고, **한 뒤의 OS 상태**는 잠그지 않는다.
- **macOS 경로** — 실측 수단 없음(ROADMAP SPIKE-02 의 macOS 미실측과 같은 성격).
- **Windows-browser 시각검증** — 배포 후 PB-0008 로 연결 화면·`[내 AI 실행]` 딥링크 문자열
  확인 예정. 이 cycle 의 웹 자산 변경은 `index.html` **주석 1줄**뿐이라 렌더 표면 변화는 없다.
