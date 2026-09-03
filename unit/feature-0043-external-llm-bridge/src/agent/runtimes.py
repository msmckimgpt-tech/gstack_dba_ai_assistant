"""런타임 스펙·CLI 어댑터·플래그 정책.

본 모듈은 `bridge_agent.py` 단일 파일 러너의 **소스 조각**이다 — 배포 산출물은
`bin/build-bridge-agent.py` 가 이 패키지를 결정적 순서로 연접해 만든다.
"""
from __future__ import annotations

import os

# ── 내 AI 호출 ───────────────────────────────────────────────────────────────

#: 런타임 명세 — 자동 감지 순서 · 호출 방법 · **이 머신이 고를 수 있는 것**.
#:
#: ## 왜 한 표에 모으는가 (P0-Z3, 사용자 결정 2026-08-28)
#:
#: 웹 화면의 모델·추론 목록은 이 표에서 나온다. 서버는 사용자의 런타임을 알지 못하므로
#: (MCP 어댑터가 별도 컨테이너라 `clientInfo` 가 웹까지 오지 않는다), **아는 쪽이 말한다** —
#: 러너가 하트비트에 자기 능력을 실어 보내고 서버는 그것을 그대로 카탈로그로 쓴다.
#: 그래서 목록과 실행이 같은 출처를 갖는다. P0-T 가 지운 것은 *조작면* 이 아니라
#: **출처가 다른 조작면**이었다(서버 alias 를 보여주고 CLI 로 실행 → 아무 것도 안 맞음).
#:
#: ## 새 플랫폼을 더하려면
#:
#: 이 표에 한 항목을 더한다. 그 외에 손댈 곳은 없다 — 감지·신고·인자 조립·화면 렌더가
#: 전부 이 표를 읽는다.
#:
#:     "<name>": {
#:         "label":  화면에 보일 이름(그룹 배지),
#:         "argv":   ["cli", "-p", "{prompt}"],     # {prompt} 자리에 질문이 들어간다
#:         "model":  ["--model", "{model}"],        # 없으면 모델 지정 불가로 신고된다
#:         "effort": ["--effort", "{effort}"],      # 없으면 추론등급 지정 불가로 신고된다
#:         "models": [{"value":..., "label":...}],  # 정적 목록(alias 우선 — 아래 주석)
#:         "efforts":[{"value":..., "label":...}],
#:     }
#:
#: ## 왜 alias 를 우선하는가
#:
#: `opus`·`sonnet` 같은 alias 는 모델 세대가 바뀌어도 같은 이름으로 남는다. 풀네임을 굳히면
#: CLI 가 새 세대로 넘어간 날 목록이 통째로 죽고, 그 죽음은 **사용자 화면에서** 드러난다.
#: 목록은 그 AI 에게 직접 물어 얻는다 — 아는 방법이 있으면 추측하지 않는다.
#: 학습 플래그(`_coerce_flag`)로 **절대 들어오면 안 되는** 토큰 조각 — 소문자 부분일치.
#: 모델·추론등급을 지정하는 정당한 플래그(`--model`·`-m`·`--effort`·`-c
#: model_reasoning_effort=…`)에는 아래 조각이 하나도 들어가지 않는다. 반대로 여기 걸리는
#: 것들은 전부 **우리가 방금 좁힌 축을 다시 여는** 플래그다 (codex P1-1).
_FORBIDDEN_FLAG_FRAGMENTS: tuple[str, ...] = (
    "mcp",            # --mcp-config / --strict-mcp-config / -c mcp_servers=…
    "permission",     # --permission-mode
    "bypass",         # bypassPermissions
    "dangerous",      # --dangerously-skip-permissions
    "tool",           # --allowedTools / --disallowed-tools
    "sandbox",        # codex -s / -c sandbox_permissions=…
    "setting",        # --settings
    "system-prompt",  # --append-system-prompt
    "system_prompt",
    "add-dir",
)

#: 상주 MCP 서버를 **살려 두고 싶은** 사용자의 탈출구 (codex P1-3).
#: 기본은 배제다 — 라이브 사고의 원인이 그 표면이었기 때문이다(사용자 결정 2026-08-28).
#: 그러나 배제는 DQA 만이 아니라 그 사용자가 붙여 둔 **모든** MCP 서버에 걸린다
#: (`--strict-mcp-config` 는 `--mcp-config` 로 준 것만 쓴다는 뜻이므로, 아무것도 주지 않으면
#: 전부 사라진다). GitHub·사내 검색 MCP 를 쓰던 사람에게 그것은 기능 손실이다. 그 사람이
#: 되돌릴 수 있는 자리를 남긴다 — 대신 되돌리면 만료된 토큰 경합도 함께 돌아온다.
_KEEP_MCP = os.environ.get("BRIDGE_KEEP_MCP", "").strip().lower() in ("1", "true", "yes", "on")

#: claude 호출에서 MCP 표면을 끊는 플래그. 위 `_KEEP_MCP` 와 아래 런타임 지원 확인
#: (`_claude_supports_strict_mcp`) 두 조건이 모두 통과할 때만 실린다.
_STRICT_MCP_FLAG = "--strict-mcp-config"

#: 운영자 지침을 **실제 시스템 채널**로 넘기는 플래그 (TASK-20260901T140000).
#:
#: 종전에는 지침을 프롬프트 본문에 넣고 「── 아래 지침을 시스템 프롬프트로 삼아 답하라 ──」
#: 라는 머리말을 붙였다. 그 문형은 **사용자 메시지 안에서 자기 역할을 재지정하는 것**이라
#: 프롬프트 인젝션의 대표 서명과 동형이고, 평문 토큰·외부 주소 지시와 겹치면서 라이브에서
#: 정상 요청이 인젝션으로 오판돼 답변이 자가중단됐다(2026-09-01 대화
#: `20260901030637-95dc8844` — 거부문이 이 문형을 근거 1번으로 인용).
#:
#: 실제 시스템 채널로 넘기면 같은 지침이 **본문 밖**에 놓여 그 서명이 사라진다.
_APPEND_SYSTEM_FLAG = "--append-system-prompt"

_RUNTIME_SPECS: dict[str, dict] = {
    "claude": {
        "label": "Claude",
        # `--strict-mcp-config` 는 **경합하는 자격증명을 끊는 자리**다 (2026-08-28 라이브).
        # 러너는 프롬프트에 이 task 에 결속된 토큰을 실어 보내는데, 같은 머신의 `claude` 에
        # 같은 서비스의 MCP 서버가 상주 설정돼 있으면(`~/.claude.json` 의 별개 `mat_` 토큰)
        # 모델은 그 도구를 먼저 집는다. 그 토큰이 만료된 순간 조사가 통째로 401 이 되고,
        # 사용자 화면에는 「권한을 승인해 달라」 는, 승인할 대상조차 없는 답이 나갔다.
        # 이 플래그로 그 표면을 아예 없앤다 — 조사 도구 8종은 프롬프트의 HTTP 경로로 전부
        # 제공되므로 **조사 능력은 줄지 않는다**(줄어드는 것은 만료된 두 번째 인증 경로뿐).
        # `--mcp-config` 를 함께 주지 않으므로 MCP 서버는 0개가 된다(실측: 도구 목록 없음).
        # ⚠ 이것은 사용자의 **권한 설정을 낮추는 것이 아니다** — 오히려 좁힌다. 파일 상단
        #   보안 계약의 「네 런타임의 권한 설정이 마지막 방어선」 은 그대로 유지된다.
        # ⚠ 되돌리는 자리: `BRIDGE_KEEP_MCP=1` (다른 MCP 서버를 함께 쓰던 사용자용, codex P1-3).
        "argv": (["claude", "-p"]
                 + ([] if _KEEP_MCP else [_STRICT_MCP_FLAG])
                 + ["{prompt}"]),
        # 프롬프트를 **stdin 으로** 넘길 수 있다 — `claude -p` 는 위치 인자가 없으면 stdin 을
        # 읽는다(라이브 실측 2026-09-02: `printf … | claude -p --strict-mcp-config` → 정상 응답).
        # 이 자리가 Windows 명령줄 32,767자 상한의 탈출구다 (`_fit_cmdline`).
        "stdin_ok": True,
        #: `{prompt}` 자리에 무엇을 남기는가. `""` = 그 인자를 **뺀다**.
        "stdin_arg": "",
        "model": ["--model", "{model}"],
        "effort": ["--effort", "{effort}"],
        # 운영자 지침을 본문이 아니라 이 플래그로 넘긴다 (TASK-20260901T140000).
        # 지원 여부는 기동 시 `--help` 로 확인한다(`system_channel_supported`) — 모르는
        # 버전에 넘기면 **모든 질문이** unknown option 으로 죽기 때문이다.
        "system": [_APPEND_SYSTEM_FLAG, "{system}"],
        "models": [
            {"value": "opus", "label": "Opus"},
            {"value": "sonnet", "label": "Sonnet"},
            {"value": "haiku", "label": "Haiku"},
        ],
        "efforts": [
            {"value": "low", "label": "낮음"},
            {"value": "medium", "label": "보통"},
            {"value": "high", "label": "높음"},
            {"value": "xhigh", "label": "매우높음"},
            {"value": "max", "label": "최대"},
        ],
    },
    "codex": {
        "label": "Codex",
        # ⚠ claude 의 `--strict-mcp-config` 에 해당하는 플래그가 codex 에는 없다 (실측
        #   `codex exec --help`, 2026-08-28). 그래서 이 런타임에서는 MCP 경합을 **실행 측에서
        #   끊지 못하고**, `compose_prompt` 의 「이 토큰이 유일한 자격증명이다」 문장만이
        #   방어선이다. 없는 플래그를 있는 것처럼 넣으면 CLI 가 통째로 실패해 답이 오지 않는다.
        "argv": ["codex", "exec", "--skip-git-repo-check", "{prompt}"],
        # ── 능력 질의 **전용** 추가 인자 (사용자 제보 2026-09-02, 4차) ────────────────
        #
        # 이 인자는 **능력 질의에만** 붙고 실제 질문 처리에는 붙지 않는다. 근거가 다르다:
        # 능력 질의는 자기소개라 추론이 필요 없지만, 사용자 질문은 그 반대다.
        #
        # 실측(같은 머신·같은 프롬프트, 러너와 동일한 추출기로 판정, 2026-09-02):
        #   기본 >300초(타임아웃) → 도구금지 가드 47.0초 → **가드 + 이 인자 10.8초**.
        #
        # - `-c model_reasoning_effort=low`: `minimal` 은 **rc=1 로 거부됐다**(2.9초에
        #   실패) — 「가장 낮은 값」이 아니라 「가장 낮은 **되는** 값」을 쓴다.
        # - `--ephemeral`: 능력 질의로 사용자의 세션 목록을 더럽히지 않는다. 질의는
        #   대화가 아니라 조회다.
        #
        # ⚠ 이 인자가 통하지 않는 버전이 있을 수 있다. 그래서 호출측은 **첫 시도에만**
        #   붙이고 재시도에서는 뺀다(`caps.py` `_probe`) — 인자 하나 때문에 그 런타임이
        #   화면에서 통째로 사라지는 일이 없어야 한다.
        "probe_extra": ["-c", "model_reasoning_effort=low", "--ephemeral"],
        # 라이브 실측 2026-09-02: `printf … | codex exec --skip-git-repo-check -` → 정상 응답.
        # claude 와 달리 자리를 **비우면 안 되고** `-` 를 남겨야 한다(빼면 대화형으로 뜬다).
        "stdin_ok": True,
        "stdin_arg": "-",
        "model": ["-m", "{model}"],
        # config override 로 넘긴다 — codex 에는 전용 effort 플래그가 없다.
        "effort": ["-c", "model_reasoning_effort={effort}"],
        # ⚠ 아래 `models` 는 **신고에 쓰이지 않는다** (2026-08-31). 화면 목록의 출처는
        #   probe 응답뿐이고, 이 표는 `build_cmd(runtimes=None)` 폴백(단위 테스트·구 호출부)
        #   에서만 대조에 쓰인다. 그래도 실측값으로 맞춰 둔다 — 낡은 값이 코드에 남아 있으면
        #   다음 사람이 그것을 현재 목록으로 읽는다(이번 결함이 정확히 그렇게 시작했다).
        #   실측 2026-08-31(codex 본인 응답): sol·terra·luna 는 5.6 세대, 그 아래로 5.5·5.4.
        "models": [
            {"value": "gpt-5.6-sol", "label": "GPT-5.6 Sol"},
            {"value": "gpt-5.6-terra", "label": "GPT-5.6 Terra"},
            {"value": "gpt-5.6-luna", "label": "GPT-5.6 Luna"},
            {"value": "gpt-5.5", "label": "GPT-5.5"},
            {"value": "gpt-5.4", "label": "GPT-5.4"},
            {"value": "gpt-5.4-mini", "label": "GPT-5.4 Mini"},
        ],
        "efforts": [
            {"value": "low", "label": "낮음"},
            {"value": "medium", "label": "보통"},
            {"value": "high", "label": "높음"},
            {"value": "xhigh", "label": "매우높음"},
            {"value": "max", "label": "최대"},
        ],
    },
    "gemini": {
        "label": "Gemini",
        "argv": ["gemini", "-p", "{prompt}"],
        "model": ["-m", "{model}"],
        # 추론등급 플래그가 없다 — 없는 것을 있다고 신고하지 않는다(화면에서 그 항목이 빠진다).
        "effort": None,
        "models": [
            {"value": "gemini-2.5-pro", "label": "2.5 Pro"},
            {"value": "gemini-2.5-flash", "label": "2.5 Flash"},
        ],
        "efforts": [],
    },
}

#: 하위 호환 — 종전 `(name, argv)` 순서쌍을 쓰던 자리(감지 순서 포함)를 위해 표에서 파생한다.
_CLI_ADAPTERS: list[tuple[str, list[str]]] = [
    (name, list(spec["argv"]))
    for name, spec in _RUNTIME_SPECS.items()
    if spec.get("argv")
]


#: Windows 에서 **우리가 `Popen` 으로 띄울 수 있는** 확장자. `PATHEXT` 에는 `.VBS`·`.JS` 도
#: 있지만 그것들은 스크립트 호스트가 여는 것이지 CLI 실행 파일이 아니다.
#: 확장자 없는 파일은 여기 없다 — npm 이 함께 깔아 두는 확장자 없는 sh shim 은 Windows 의
#: `CreateProcess` 로 실행되지 않아서, 그것을 「찾았다」고 하면 감지는 성공하고 호출만 죽는다.
#: Windows 에서 우리가 **직접 띄우는** 확장자.
#:
#: ⚠ **`.cmd`·`.bat` 는 의도적으로 빠져 있다** (codex 적대 리뷰 P1, 2026-09-01).
#:
#: 배치 파일은 `CreateProcess` 가 `cmd.exe` 로 넘겨 실행한다. 그 순간 인자는 Windows 의
#: argv 인용 규칙이 아니라 **`cmd.exe` 의 파싱 규칙**을 한 번 더 통과하고, 거기서는
#: `&` · `|` · `>` · `^` 가 메타문자다. 우리는 **사용자 질문 본문을 그대로 인자로** 넘기므로
#: (`{prompt}` 치환), 배치 shim 을 직접 실행하면 `shell=False` 와 리스트 argv 를 쓰고도
#: 명령 주입 경로가 열린다 — 2024년 여러 런타임을 한꺼번에 때린 그 결함(BatBadBut)과
#: 같은 모양이다. 취소 시 `proc.kill()` 이 래퍼만 죽이고 그 아래 실제 프로세스를 남기는
#: 문제도 배치 shim 에서만 생긴다.
#:
#: 잃는 것: npm 전역 설치(`%APPDATA%\npm\claude.cmd`)는 감지되지 않는다. 그러나 이것은
#: 회귀가 아니다 — 수정 전에는 확장자를 아예 안 붙였으므로 그 사용자도 못 찾았다. 우리가
#: 겨냥한 native installer(`.exe`)는 그대로 찾는다. 안전하게 부를 방법이 서기 전까지
#: 배치 shim 은 「찾았다」고 말하지 않는다.
_WIN_EXEC_EXTS = (".exe", ".com")

#: 「실행 가능하지는 않지만 실행 파일처럼 이름이 붙는」 확장자. 이름에 이것이 이미 달려
#: 있으면 `name + ".exe"` 로 늘리지 않고 **그 이름 그대로** 판정한다(아래 `_which` 참조).
_WIN_KNOWN_EXTS = _WIN_EXEC_EXTS + (".cmd", ".bat", ".ps1")
