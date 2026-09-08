# 러너 동시 자기갱신 및 클라이언트 복구 실측

- Task: TASK-20260908T120000-runner-update-recovery
- Environment: Linux Python 3.12 / Windows Python 3.14.7 embedded / Windows-browser Chrome 152.0.7977.75
- 범위: 실제 실행 프로세스·파일 교체·HTTPS·Windows 잠금/exec/인자 파싱. 서버는 격리된 로컬 HTTPS 하네스다. 실제 서비스 DB·AI·사용자 토큰은 사용하지 않았다.
- 원인 판단: 사고 당시 새 프로세스가 왜 로그 전에 사라졌는지는 확정할 수 없다. 기존 selfupdate는 이미 mkstemp/fsync/replace였으며 클라이언트 설치의 직접 write_bytes, 공통 잠금 부재, 실행 지문 재조회, Windows CRT exec 인자 인용 및 감독 부재를 코드에서 확인했다.

## 두 프로세스 복귀 — Windows 실측

`tests/verify_runner_update_processes.py`를 설치본의 실제 `runtime/python.exe`로 실행했다. 두 러너는 **동일 한글·공백 경로**를 공유하며 계정별 설정/로그만 분리한다. `--stagger`는 A의 새 하트비트가 도착한 뒤 B에 구 러너 갱신 응답을 내보내어 형제 교체 후 경합을 강제한다.

| 실행 방식 | 새 빌드 복귀 | 다운로드 간격 | 최종 생존 PID A / B | 후속 대기 요청 A / B |
|---|---:|---:|---|---|
| direct | 2/2 | 42.04 ms | 33264 / 18368 | 10 / 9 |
| stagger | 2/2 | 3621.74 ms | 13608 / 32964 | 68 / 9 |
| supervised | 2/2 | 3.43 ms | 26716 / 45896 | 10 / 10 |
| supervised-stagger | 2/2 | 4707.12 ms | 25660 / 7256 | 88 / 10 |

모든 경우에 old/new 각각 `run.start` 1개씩(총 2), 최종 build 일치, 계정별 생존 PID **정확히 1개**, 최종 관측 중 각자 추가 대기 요청 2회 이상을 단정했다. 전체 기동/갱신 제한 25초. 설치 파일 최종 바이트와 제공한 payload도 일치한다. 실측 지문(old `31bdbfed2818`, new `0079a7dddd1f`)은 테스트 설정 경로 격리 후 재스탬프한 값이다. 배포 산출물 지문과 혼동하지 않는다.

실측 원본: wrapper `artifacts/test-runs/runner-update-recovery/runner-win-final-*.log`.

## 음성 대조 및 복구

- 디스크 지문을 매번 읽게 되돌린 뮤턴트: 실제 교차 갱신 후 `run.ready` A=2/B=1, 하네스 rc=1. **한 대만 복귀**하면 실패한다(`runner-mutation-result.json`).
- 같은 파일 락을 보유한 동안 다른 설치 자식은 완료할 수 없고 원본 내용이 유지된다. runner↔runner 및 client↔runner 규약을 함께 검사한다.
- 원자 replace 실패 시 이전 파일 보존·임시파일 정리, 기동 직전 세대 교체와 일시 PermissionError에서도 자기갱신 경로 유지.
- 실제 SyntaxError 자식 → 재시작 성공 및 stderr 보존; 반복 실패 → 유한 예산 소진 + 단절 알림; 백오프 중 해제 → 추가 spawn 0; 정상 종료 → 재시도 0 + 단절 알림; 미소비 stdout 1MiB에서도 종료 가능.
- Windows 실제 tkinter/트레이: SyntaxError 3회(시험 백오프 0.2/0.4초) 뒤 「연결이 끊겼습니다 — 자동 복구에 실패했습니다」 및 다시 연결 버튼/트레이 항목, 자식 생존 0, 늦은 connected 이벤트 무시. 제품 기본 백오프는 1/2/4/8/16초다.

## 실행과 빌드

```sh
make bridge-agent
PYTHONPATH=unit/feature-0002-agent-core/src:unit/feature-0003-agent-web-ui/src:. python3 -m pytest -q unit/feature-0043-external-llm-bridge/tests unit/feature-0046-native-client/tests
make test
```

Windows 순서는 `verify_runner_update_processes.py --bundle ... --directory ... --cert ... --key ... [--stagger] [--supervised]`, `tests/windows/verify_runner_recovery.py --src ... --out ...`, `src/scripts/build_client.py --out ... --service-base https://112.185.196.20`이다. 실제 임베더블 Python의 독립 경로 모드에서는 하네스가 client.supervisor를 찾도록 시험 staging 경로를 sys.path에 추가한다.

- Windows PyInstaller onedir + Inno Setup 1.1.1 빌드. 동결 EXE 자가진단, 임베더블 Python의 contextlib/msvcrt 등 stdlib import 실제 실행.
- 릴리스 파일은 소스와 함께 Git에 넣지 않고 공식 `publish_release.py`로 채널에 반입한다. 검증된 최종 크기·SHA-256 및 배포 완료는 아래 후속 기록에 남긴다.

## 웹 안내 시각검증

Environment: Windows-browser. PB-0008 `bin/win-browser.py`의 실제 Windows CDP 브라우저를 사용했다. 검증 전용 새 탭에서 현재 정적 자산을 제공하고 API만 차단한 뒤 현재 `_showRelaunchNoUpdate` 함수를 시험용 export로 호출했다. 문구/레이아웃을 확인했으며, 실제 서비스의 갱신 실패를 발생시킨 검증은 아니다. screenshot: wrapper `artifacts/test-runs/runner-update-recovery/web-update-failure.png`.

## 전체 검증 및 배포 후속

정확한 검사 결과·병합 SHA·배포본 및 설치기 채널 지문은 아래 완료 기록에 있다. 설치기 게시와 사용자의 설치는 별개다. **기존 사용자는 1.1.1 설치 후 재연결해야 감독 기능이 생긴다.** 이미 죽은 구 러너는 서버 배포만으로 되살릴 수 없다.

### 배포 전 확정 결과 (2026-09-08T11:17:16+09:00)

- 관련 통합 검사 117 PASS, 최종 GUI·감독 검사 59 PASS. 러너/클라이언트 변경 코드 ruff PASS, ROUTEMAP·codenav PASS, verify-completion PASS. 전체 make test는 진행 중이다.
- 최종 Windows 1.1.1 설치기: 25,731,162 bytes, SHA-256 `49b37a3fee97aa5dface8ecfb23b3a011f6e0d732288cf3468a67376a58fc055`. GUI 단절 시 이전 연결 유지 안내도 교체하도록 반영한 최종 빌드다.
- 실제 브라우저에서 CSS/JS를 모두 제공한 현재 모달의 안내 표시와 줄바꿈을 확인했다. API를 차단한 합성 실패 상태임을 유지한다.
- GitHub issue: #1604.

- 사용자 후속 지시 반영: 클라이언트 감독 경로가 실제 사용 기준이다. 직접 exec는 개발자 호환 검사에만 해당하며, 사용자에게 별도 러너 실행을 안내하지 않는다.
- 진행 중 main의 템플릿 v3.54.1 변경을 병합했다. AGENTS.md §22.15 변경을 재독했고 정책 SHA-256 `024a8b53b67f2b14e35986aca68ecc8f59470c7e312b0f0f92cb79b91026df1d`를 대조했다. 기능 코드 충돌 없음.

### 전체 검사 완료 (2026-09-08T11:25:32+09:00)

- `make test`: **exit 0**, 전체 명시 suite 10개(이번 native 추가 포함) 완료, ruff도 PASS. Windows 전용 항목 등 환경별 skip은 기존 테스트 계약대로이며 별도 Windows 실측을 병행했다. 원본: wrapper `artifacts/test-runs/runner-update-recovery/runner-make-test.log`.
- GUI 단절 상세 안내까지 반영한 실제 Windows 창/트레이 검증 PASS. 최종 PNG와 JSON 저장 및 직접 열람 완료.
- GitHub PR #1606. GitHub Actions/check run은 현재 보고된 것이 없어 CI green으로 표기하지 않는다. 로컬 표준 make test 결과가 이번 검사 근거다.
- HTTPS Git 인증의 workflow scope 부재로 최초 push가 거절되어, 이미 설정된 SSH GitHub 인증으로 정상 push했다. 자격증명 변경 없음.

### 서버 및 클라이언트 채널 배포 완료 (2026-09-08)

- PR #1606 병합 SHA: `0f58a1de2f53883bbff1158f87c7637a85323d88`. `bin/deploy-web.sh --web-only` **exit 0**, 11:30:20 KST 완료. web-a/b 양쪽 동일 코드 ready 및 90초 soak PASS. UTC 02:26:36 이후 배포 창 Caddy `no upstreams available`: **0건**. worker 변경이 없어 worker 배포와 실제 AI 대화 smoke는 수행하지 않았다.
- 실제 HTTPS 제공 `/static/agent/bridge_agent.py`: **434,507 bytes**, SHA-256 `7ef612df4ba6c707039bf1f06310d4443d5e16a53c5e86c196e40afd5011ace3`. 배포 CA로 TLS 검증, 다운로드 바이트 compile 및 내장 소스 SHA-256 스탬프 검증 PASS. 이 값이 배포 러너이고 위 하네스의 설정 격리 지문과 다르다.
- `publish_release.py` **exit 0**, server-view check PASS. `/api/ai/client/latest`가 **1.1.1**, `/client/DQAConnect-Setup-1.1.1.exe`를 제공한다. 설치기 **25,731,162 bytes**, SHA-256 `49b37a3fee97aa5dface8ecfb23b3a011f6e0d732288cf3468a67376a58fc055`.
- 실제 Windows에서 제품 `client.updater.check_detail(current="1.1.0")`와 `download` 실행: **1.1.1 발견 → 전체 다운로드 → 크기/SHA-256 일치 PASS**. 격리된 앱 설정·공개 CA를 사용했고 `installer_executed=false`. 앱 사용자 확인 계약을 보존하며 설치본을 임의 갱신하지 않았다.
- 실제 Windows 시험 프로세스 정리: 이번 staging 경로의 러너 잔존 **0개**. 실제 사용자 러너·설정·토큰을 종료하거나 변경하지 않았다.
- 증거: wrapper `artifacts/test-runs/runner-update-recovery/`의 `runner-deploy.log`, `post-deploy.json`, `deployed-bridge_agent.py`, `manifest.json`, `client-channel-result.json`, `runner-client-channel.log`, `runner-win-cleanup.log`.
- 최종 사용자 동선: **DQA 앱에서 1.1.1 업데이트 설치 후 다시 연결**. 별도 러너 실행이나 터미널 명령은 요구하지 않는다. 서버·설치기 게시 완료와 사용자의 실제 설치 완료는 구분한다.

- 배포 후 Environment: Windows-browser. 실제 Windows Chrome에서 배포 사이트의 HTML/CSS/JS로 갱신 실패 모달의 픽셀을 재확인했다. JS는 TLS 검증 다운로드 후 캐시 스탬프 치환만 제외하면 소스와 동일함을 확인했고 시험용 export만 추가했다. 독립 브라우저 context에서 API를 차단하여 실제 계정 연결을 만들지 않았다. 실패 상태는 합성이며 실제 사고 재현이라고 주장하지 않는다. `web-update-failure-deployed.png`, `web-deployed-result.json` 참조. 최초 route.fetch는 브라우저와 별개의 TLS 신뢰 설정 때문에 실패해, 배포 CA를 명시한 다운로드로 교정했다.
