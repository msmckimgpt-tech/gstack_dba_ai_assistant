---
run_at: 2026-09-01T12:15:00+09:00
session: ai/claude/feature-0043-win-ai-detect-postdeploy
scope: 배포본(c0545cdd) 도달성 + 실 Windows end-to-end + 서버측 러너 교체·재기동
verdict: PASS
---

# Run — TASK-20260901T110000-win-ai-detect (POST-DEPLOY)

Environment: 라이브 엣지 `https://112.185.196.20` (배포본 `c0545cdd`) · 실 Windows
PowerShell 5.1 + Python 3.14 · WSL 호스트

> UI 표면 변경 없음 — PB-0008 브라우저 시각검증 대상 아님(러너·설치 스크립트). 대신
> **사용자가 실제로 받는 파일**을 라이브 엣지에서 내려받아 그것으로 검증했다.

## 1. 배포 게이트

| 확인 | 결과 |
|---|---|
| `sudo -E bin/deploy-web.sh` (scope=all) | **rc=0** — web 롤링 · 워커 · gateway reconcile + soak |
| 대화 경로 스모크 | **PASS** (전환 모드 — 서버 계정 LLM 차단 확인) |
| 무중단 실측: `caddy` 로그 `no upstreams available` (최근 15분) | **0건** |
| 배포 커밋 | `c0545cdd` |

## 2. 도달성 — 「배포했다」와 「사용자에게 도달했다」를 가른다

같은 파일이 세 지점에서 동일해야 사용자가 받는 것이 우리가 테스트한 것이다.

| 지점 | `bridge_agent.py` sha256 |
|---|---|
| 정본 (main `c0545cdd`) | `5aa59fe9904a832984b9a81984531e31deb5eef45c529e68772334ef1981020e` |
| 컨테이너 `web-a` | 동일 |
| 컨테이너 `web-b` | 동일 |
| **라이브 엣지** `GET /static/agent/bridge_agent.py` | **동일** |

`bridge_setup.ps1` 도 엣지 = 정본 (`c655e231b14065839016d94667ce0946ca9c0f403383cdc8c3f3774f78fbe2b2`).

> CA 는 사용자와 같은 경로(`http://112.185.196.20/trust/rootCA.crt`)로 받아
> `curl --cacert` 로 검증했다 — OS 신뢰 저장소를 쓰면 pin 을 우회해 「도달했다」가 거짓이 된다.

## 3. 실 Windows end-to-end — **엣지에서 받은 그 파일로**

로컬 정본이 아니라 **엣지 사본**(위 sha 동일 확인)을 Windows 로 옮겨 구동했다.

```json
{
  "sha256": "5aa59fe9…1981020e",
  "exec_exts": [".com", ".exe"],
  "which_PATH_only": null,
  "which_ai": "C:\\Users\\<사용자>\\.local\\bin\\claude.exe",
  "detect_ai": "claude",
  "pick_ai_absent": null,
  "help_ok": true
}
```

- `which_PATH_only = null` — **PATH 는 여전히 고치지 않았다.** 그래도 찾는다.
- `pick_ai_absent = null` — 실제로 없는 런타임(`--ai codex`)은 없다고 답한다(넓혔지만 무르지 않았다).
- `help_ok = true` — 찾은 경로로 **실제 프로세스가 떴다**(감지와 호출이 갈리지 않는다).

**안내 문구 표시 확인** (실 PowerShell 5.1, 한글 깨짐 없음):

```
  이 브리지는 이 컴퓨터에 설치된 AI 프로그램으로 답합니다.
  쓸 수 있는 것: Claude · Codex · Gemini · Ollama
  아직 없다면 Claude Code 를 설치한 뒤 이 명령을 다시 실행하세요: …
  이미 설치했다면 설치 폴더가 시스템 PATH 에 등록되지 않았을 수 있습니다.
  아래를 모두 찾아봤습니다:
    · PATH 에 등록된 폴더 전부
    · C:\Users\<사용자>\.local\bin
    · C:\Users\<사용자>\AppData\Roaming\npm
    · C:\Users\<사용자>\AppData\Local\Programs\Ollama
```

`--ai` · `--cmd` 가 한 번도 나오지 않는다(사용자 결정 2026-09-01). 그리고 찾아본 위치가
사용자의 **실제 경로**로 찍히므로, 설치 폴더가 목록에 없으면 그것을 바로 알아볼 수 있다.

## 4. 서버측 상주 러너 교체·재기동

배포는 서버가 **서빙하는** 파일을 갱신할 뿐, 이미 도는 러너가 예전에 내려받은 사본은
그대로다. 그 러너는 구버전(`af7c3fe1…`)으로 돌고 있었다.

| 단계 | 결과 |
|---|---|
| 토큰 회수 | 기존 프로세스 `/proc/<pid>/environ` (파일로 저장되지 않는다) |
| 최신 러너 수신 + 대조 | 엣지 사본 == 배포본 `5aa59fe9…` (대조 후에만 교체) |
| 라이브 `--check` | `연결 정상.` → `사용할 AI: claude` → **exit 0** |
| 재기동 | 구 PID 직접 지정 종료 → `--resume` 상주 |
| 기동 로그 | `AI = claude` · `고를 수 있는 것: Claude(3종, 추론 5단계)` · `대기 시작` |

라이브 `--check` 출력이 **축 분리가 실제로 도는 증거**다 — 연결을 먼저 확인하고(`연결 정상.`),
그다음 AI 를 말한다(`사용할 AI: claude`). 원 제보에서는 이 순서가 반대라 연결이 멀쩡한데
「연결 확인에 실패했습니다」가 나왔다.

### 자체 발견 — 첫 재기동에서 토큰을 명령줄에 실었다

`sudo -u claude-corp env BRIDGE_TOKEN=mat_… python3 …` 로 띄웠더니 그 토큰이 `ps` 출력에
그대로 보였다. `environ` 노출(원래 있던 상태)과 달리 **같은 호스트의 다른 사용자도 읽을 수
있는** 넓이다. 곧바로 stdin 경유(`printf '%s' "$TOK" | sudo -u … sh -c 'read -r BRIDGE_TOKEN; …'`)로
다시 세웠고, 현재 러너 명령줄은 `python3 bridge_agent.py --base … --ca … --resume` 뿐이다.

> 교훈: 비밀을 프로세스에 넘기는 방법은 세 가지(명령줄 · 환경 · stdin)이고 **노출 범위가
> 다르다**. 편의로 고른 `env VAR=…` 가 가장 넓은 것이었다.

## 5. 미검증 (정직 표기)

- **첫 사용자의 실제 설치 왕복은 여전히 미관측.** 위 3절은 엣지 배포본을 사용자와 같은
  머신에서 구동한 것이고, 유효 토큰으로 `.ps1` 전체(핸들러 등록 + 상주 포함)를 처음부터
  끝까지 돌리지는 않았다 — 토큰은 웹에서 사용자가 발급한다. 사용자가 [연결 명령 복사] 를
  다시 눌러 실행하면 그 왕복이 닫힌다.
- **AI 가 하나도 없는 머신의 exit 4 경로**는 단위 테스트로만 잠겼다(그 상태의 실 머신 부재).
