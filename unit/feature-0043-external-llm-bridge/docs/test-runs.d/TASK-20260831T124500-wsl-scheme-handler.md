---
run_at: 2026-08-31T13:20:00+09:00
session: ai/claude/feature-0043-wsl-scheme-handler
scope: "[내 AI 실행] 스킴 핸들러 등록 위치 교정 + 무동작 정직 강등"
verdict: PASS
---

# Run — TASK-20260831T124500-wsl-scheme-handler

- **일시**: 2026-08-31
- **Environment**: container (pytest) + node (동작 하네스) + **Windows-browser** (PB-0008, 격리 인스턴스)
- **대상**: `bridge_setup.sh` 핸들러 등록 분기 · `connect-modal.js` 실행 버튼 · `.is-attention` 강조

## 1. 자동 스위트

| 스위트 | 결과 |
|---|---|
| `unit/feature-0043-external-llm-bridge/tests` (신규 `test_wsl_scheme_handler.py` 13건 포함) | **PASS** |
| `unit/feature-0003-agent-web-ui/tests` · `unit/feature-0041-*/tests` | **PASS** (exit 0) |
| `unit/feature-0002` · `0023` · `0014` · `0020` · `0008` | **PASS** (exit 0) |
| `verify_launch_runner_behavior.mjs` (정본 모듈 실행) | **PASS (11 checks)** |

### 게이트가 실제로 결함을 잡는가 (§16.7 G11-b)

수정 전 코드에 대해 두 스위트를 1회씩 돌려 **FAIL 을 실증**했다. 통과만 확인한 단언은
「무엇도 검사하지 않는 단언」과 구별되지 않는다.

| 스위트 | 수정 전 | 수정 후 |
|---|---|---|
| `test_wsl_scheme_handler.py` | **11/13 FAIL** | 13/13 PASS |
| `verify_launch_runner_behavior.mjs` | **8/11 FAIL** (L2·L3·L4·L5·L6·L6b·L7·L10) | 11/11 PASS |

워킹트리 복원 후 재실행 PASS 확인(`git diff` clean, 정본==서빙본).

## 2. OS 수준 핸들러 왕복 (실 Windows + WSL Ubuntu)

스텁이 아닌 **실제 등록 → ShellExecute → wsl.exe → launch.sh** 왕복을 마커 파일로 관측.

| 커맨드라인 | 결과 |
|---|---|
| `-d "Ubuntu" -u "claude-corp"` (따옴표) | **FAIL 2/2** — 핸들러는 불리지만 wsl.exe 가 배포판을 못 찾고 즉시 죽는다 |
| `-d Ubuntu -u claude-corp` | **PASS 3/3** (대기 8초 기준) |
| 같은 명령, 대기 4초 | FAIL — 콜드 스타트가 4초를 넘는다 → 웹 대기 창을 30초로 잡은 근거 |

`wsl.exe -d '"Ubuntu"' -- /bin/true` → `rc=-1` 로 가설 직접 확인.

## 3. 크롬 발사 경로 (CDP 로그 관측)

| 경로 | 관측 |
|---|---|
| hidden iframe (제스처 유·무) | 마커 없음 + **외부 프로그램 판정에 도달한 로그도 없음** |
| `location.href` (제스처 없음) | `Not allowed to launch 'mysql-ai-bridge://…' because a user gesture is required` |
| `location.href` (실제 클릭) | 차단 로그 없음 → 확인 대화상자 단계로 진행 |
| 프로필에 동의 주입 후 실제 클릭 | **iframe·최상위 둘 다 기동** (동의가 유일한 잔여 변수였음) |
| 미등록 스킴 최상위 이동 (대조군) | 페이지 이탈 없음 (URL·제목 불변) → iframe 을 쓰던 근거 소멸 |

동의 주입은 QA 전용 프로필에만 했고 검증 후 원복했다.

## 4. PB-0008 실 Windows 브라우저 — 화면

라이브 **무접촉**. `mysql-ai-web:current` + 이 브랜치의 `static/` 만 bind-mount 한 별도
컨테이너(`web-verify-launch`, `https://localhost:18099`), 세션은 `session-login`(bootstrap_admin).

| 단계 | 관측 |
|---|---|
| 게이트 패널 → `[연결하기]` | 모달 열림 |
| `[연결 준비]` | "준비했습니다…" · 명령 608자 · `[내 AI 실행]` 노출 |
| `[내 AI 실행]` 직후 | "실행을 요청했습니다. 내 AI가 응답하는지 확인하는 중…" (성공색 아님) |
| 30초 후 | `data-kind=error` · "아직 응답이 없습니다 … 강조된 1단계 명령을 터미널에 붙여넣어 실행하세요." · 버튼 재활성 |
| 강조 | `is-attention` 부여 확인 · 트랜지션 정착 후 `outline-color: rgb(37, 99, 235)` |
| 동시 가시성 | `statusVisible=true` · `cmdVisible=true` (캡처로 확인) |

### 이 검증이 잡은 결함 (수정 반영)

`scrollIntoView` 기준을 명령 블록으로 잡았더니 상태 문구가 화면 밖으로 밀렸다
(`statusTop 912 > 뷰포트 889`, `block:"center"`·`"nearest"` 둘 다). 사용자는 강조된 검은
상자만 보고 **왜** 보게 됐는지 못 읽는다. 스크롤 기준을 상태 문구로 바꿔 둘 다 보이게 했고,
문구의 방향어("아래 1단계" → 명령이 문구보다 위에 있어 틀림)도 "강조된 1단계" 로 고쳤다.
자동 스위트가 통과한 상태에서 **렌더된 그림으로만** 드러난 결함이다 (§16.7 G9-a).

## 5. 미검증 / 한계 (정직 표기)

- **크롬 확인 대화상자 자체는 자동화로 닫을 수 없다.** 실사용자의 첫 클릭에서는 그 창이 뜨고
  허용해야 기동한다(표준 경로). 자동화에서는 프로필 동의 주입으로 그 변수를 제거해 확인했다.
- **사용자 실 머신에서의 최종 재현은 사용자 몫**: 설치 명령 재실행 → `[내 AI 실행]` → 상태
  표시가 `내 AI 대기 중` 으로 바뀌는지.
