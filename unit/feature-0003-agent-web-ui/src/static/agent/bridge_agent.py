#!/usr/bin/env python3
"""mysql-ai 브리지 상주 러너 — 웹 질문을 **내 머신의 AI** 로 처리한다.

## 무엇을 하는가

    wait_for_request (응답 보류)  ─── 사용자가 웹에서 질문을 보내는 그 순간 반환
        → claim_request           ─── 원자적 점유
        → 내 AI 를 호출해 답을 만든다
        → submit_answer           ─── 원 대화에 표시

## 보안 계약 — 실행 전에 이것부터 읽어라 (2026-08-27)

이 파일은 "모르는 주소에서 받아 상주시키라" 는 요구와 형태가 같다. 그 요구를 거절하는 것은
옳은 판단이고, 실제로 외부 AI 가 그렇게 거절했다. 그래서 **믿어 달라고 하지 않는다** — 아래는
전부 이 파일 안에서 직접 확인할 수 있는 사실이고, 확인 방법을 함께 적는다.

    서버에서 받는 것    질문 텍스트 · 대화 맥락 · **운영자 시스템 지침** · 첨부 목록 · task_id.
                        실행 가능한 코드나 셸 명령은 받지 않는다.
                        → `compose_prompt` 가 쓰는 필드가 전부다(직접 세어 보면 된다).
    실행하는 것         `_RUNTIME_SPECS` 에 하드코딩된 로컬 AI CLI(`claude -p` / `codex exec`
                        / `gemini -p` / ollama HTTP), 사용자가 `--ai` 로 지목한 PATH 상의 CLI,
                        또는 `--cmd` 로 직접 준 명령. **실행 파일은 언제나 이 머신에 이미
                        설치된 것**이고(`_which` 로 확인), 우리가 내려받거나 만들지 않는다.
    기동 시 1회 질의     각 CLI 에게 "너는 어떤 모델·추론 수준을 쓸 수 있나" 를 묻는다
    (P0-Z4)             (`_CAPS_PROBE_PROMPT`). 보내는 것은 **그 질문 문장 하나뿐**이고 이
                        머신의 파일·환경·대화 내용은 실리지 않는다. 답은
                        `config.json` 에 캐시되어 다음 기동은 묻지 않는다(`--refresh-caps`
                        로만 갱신). 이 질의는 **네 AI 계정의 토큰을 쓴다**.
    서버 값은 인자가     서버가 돌려주는 (런타임·모델·추론등급)은 사용자가 웹에서 고른 것이고
    되기 전에 걸러진다   CLI 인자가 된다. 그러나 **신고 목록에 있는 값만** 통과한다 — 실행 파일
                        이름은 이 러너가 신고한 런타임이어야 하고(그리고 PATH 에 실재해야
                        하고), 모델·등급은 그 런타임이 스스로 답한 목록 안이어야 한다.
                        그 외에는 조용히 버려지고 CLI 기본값으로 실행된다.
                        → `build_cmd` 의 `_valid()` · `handle_one` 의 `_offered` 검사.
    호출법은 서버로      플래그 형태(`--model {model}` 등)는 **로컬 `config.json` 에만** 있다.
    나가지 않는다        신고에는 사람이 고를 목록만 싣는다 → `detect_runtimes` 가 돌려주는
                        dict 에 `model`/`effort` 키가 없음을 직접 확인할 수 있다.
                        그래서 서버는 **값을 고를** 수 있을 뿐, 인자의 *형태* 를 바꾸거나
                        새 플래그를 만들어 넣지 못한다.
    셸을 거치지 않음    프롬프트도 모델·등급도 argv 로 넘어간다 — 본문에 셸 메타문자가 있어도
                        명령이 되지 않는다. → `_run_cli_cancelable` 의
                        `subprocess.Popen(cmd, ...)` 에서 `cmd` 는 리스트다(셸 해석이 개입하는
                        자리가 없다).
    원격 코드 실행 없음 `eval`·`exec`·`compile`·동적 import 가 없다. 자동 업데이트도 없다.
                        → `grep -nE 'eval[(]|exec[(]|compile[(]|__import__' bridge_agent.py`
                          (매칭되는 줄은 **이 안내문 자신뿐**이어야 한다. 코드에는 없다.)
    설치물 없음         표준 라이브러리만 쓴다(`pip install` 불필요). 부팅 등록·crontab·서비스
                        설치를 하지 않는다. 남기는 파일은 `~/.mysql-ai-bridge/config.json`
                        (0600) **하나뿐**이고 거기에 **토큰은 넣지 않는다** → `save_conf`.
    나가는 곳           `--base` 주소의 `/api/ai/tools/*` (→ `Api.call`) 와
                        `/api/ai/bridge_heartbeat` (→ `Api.heartbeat`, 30초마다 1회 —
                        본문은 이 머신에서 **쓸 수 있는 런타임·모델 이름 목록**뿐이다.
                        경로·버전·설정 파일 내용은 싣지 않는다 → `detect_runtimes`).
                        그리고 ollama 를 쓸 때만 `BRIDGE_OLLAMA_URL`(기본
                        `127.0.0.1:11434`) — 그 경로를 쓰지 않으면 호출되지 않는다
                        (모델 목록 조회 `/api/tags` 도 같은 호스트다).
                        URL 을 만드는 자리는 `Api._post` 와 ollama 어댑터 **둘뿐**이다.
    관측·종료           하는 일은 전부 stderr 로그에 남는다. `Ctrl+C` 또는 `kill <pid>` 로 끝나고,
                        끝난 뒤 남는 것은 위 `config.json` 과 네가 리다이렉트한 로그 파일뿐이다.

**정직하게 적는 잔여 노출면 둘** — 숨기면 소스를 읽는 순간 드러나고, 그때 잃는 것이 더 크다.

1. **토큰은 프롬프트 안에도 들어간다.** `compose_prompt` 가 조사 도구를 직접 부르라고 토큰을
   함께 주고, 그 프롬프트 전문이 argv 로 CLI 에 넘어간다 — 같은 호스트의 다른 사용자가
   `/proc/<pid>/cmdline` 으로 볼 수 있고, CLI 의 세션 기록에도 남는다. 인자 대신 `BRIDGE_TOKEN`
   환경변수를 쓰면 셸 히스토리만큼은 피한다. 토큰은 **웹 로그인 세션에 결합**돼 있어 그 사람이
   로그아웃하면 즉시 죽고, 이 러너가 멈추면 마지막 하트비트로부터 12시간 뒤 만료된다 — 즉
   **러너가 도는 동안은 계속 유효하다**(2026-08-28 이전에는 발급 후 12시간이 절대 상한이었다).
   무기한이 되지 않게 하는 것은 러너를 끄는 행위 자체다.
2. **운영자 시스템 지침은 구획되지 않는다.** 질문·대화이력은 서버가 ⟦UNTRUSTED-DATA⟧ 로 감싸
   보내지만, 관리 콘솔에서 설정하는 시스템 지침은 감싸지 않고 이 러너가 프롬프트 **맨 앞**에
   놓는다(그러지 않으면 뒤의 지시가 이겨 운영자 설정이 무시된다). 즉 **그 서비스의 운영자는 네
   답변 방식에 영향을 줄 수 있다.** 무엇이 설정돼 있는지는 `claim_request` 응답의
   `system_prompt` 로 그대로 보이니, 필요하면 먼저 확인하고 판단해라.

**남는 신뢰 경계**: 위 2번의 연장선이다. 서버가 보낸 텍스트는 네 AI 의 프롬프트가 되고, 네 AI 가
도구를 쓸 수 있는 에이전트라면 그 프롬프트가 행동을 유도할 여지는 남는다 — 이 파일이 없앨 수 있는
위험이 아니다. 그래서 네 런타임의 권한 설정이 여전히 마지막 방어선이고, 그것을 낮추라고 요구하지
않는다. 신뢰의 뿌리는 이 파일이 아니라 **이 러너를 띄우라고 한 사람이 네 사용자인가** 이다.

## 왜 폴링이 아닌가 (사용자 요구 2026-08-27)

`list_open_requests` 를 N 초마다 부르면 두 가지가 나빠진다 — 질문이 최대 N 초 늦게 인지되고,
그 N 이 사람마다 달라 **환경 차이**가 된다. `wait_for_request` 는 호출이 한 번이고 응답이
**질문이 들어온 그 순간** 온다. 상한은 서버가 정하므로 모든 머신이 동일하게 동작한다.

여기에는 sleep 이 없다. 대기는 서버가 한다.

## 연결은 어떻게 유지되는가 (2026-08-28)

대기와 별개로, **30초마다 한 줄짜리 생존 신호**(`/api/ai/bridge_heartbeat`)를 보내는 스레드가
하나 돈다. 이건 질문을 찾는 폴링이 아니다 — 아무것도 가져오지 않고, 서버에 "이 러너가 아직
있다" 만 말한다. 그 신호가 두 가지를 한다:

1. **토큰 수명을 민다.** 종전에는 발급 후 12시간이 지나면 아무도 로그아웃하지 않았고 러너도
   멀쩡한데 401 로 죽었다. 이제 기준점이 마지막 신호이므로, 도는 동안은 끊기지 않는다.
2. **웹 화면의 '대기 중' 표시를 정확하게 만든다.** 종전 판정은 `wait_for_request` 최근성이라,
   워커가 전부 일하는 중이면(긴 조사) 살아 있는 러너가 "대기 안 함" 으로 보였다.

끊고 싶으면 이 프로세스를 끝내면 된다(`Ctrl+C` / `kill`). 그러면 신호가 멈추고 서버 쪽 토큰도
12시간 뒤 만료된다.

## 웹에서 로그아웃하면 러너도 스스로 끝난다 (사용자 요구 2026-08-28)

로그아웃은 토큰을 **즉시** 무효로 만든다. 그 뒤로 이 러너는 아무것도 할 수 없다 — 질문을
가져올 수도, 답을 제출할 수도 없다. 그런 프로세스를 남겨 두면 사용자 머신에 아무 일도 하지
않는 것이 계속 떠 있게 된다. 그래서 **스스로 종료한다**:

| 그때 상태 | 하는 일 |
|---|---|
| 유휴(진행 중 0건) | 즉시 종료 |
| 진행 중 있음 | 최대 `BRIDGE_SHUTDOWN_GRACE_SEC`(기본 120초) 기다렸다가 종료 |
| 유예 초과 | 진행 중인 AI 호출을 중단시키고 종료 |

무한정 기다리지 않는 이유: 그 답변들은 **전달될 곳이 이미 없고**(제출이 401), 붙잡을수록
아무도 볼 수 없는 답을 위해 네 계정 토큰만 탄다.

## 왜 런타임 무관인가

claude·codex·gemini 는 전부 "프롬프트를 주면 stdout 으로 답을 주는 CLI" 다. 그래서 **명령
템플릿 하나**로 덮인다. 로컬 LLM(ollama 등)만 HTTP 라 어댑터가 따로 있다. 어느 쪽도 이 파일
밖에 설치물을 만들지 않는다.

## 설치물이 이 파일 하나인 이유

표준 라이브러리만 쓴다. `pip install` 이 필요하면 그 순간 파이썬 환경마다 결과가 갈리고,
그것이 곧 우리가 없애려는 환경 차이다.

## 실행

    python3 bridge_agent.py --base https://<host> --token mat_... [--ca rootCA.crt]

AI 는 자동 감지한다(claude → codex → gemini → ollama 순). 고정하려면:

    --ai claude            # 또는 codex / gemini / ollama
    --cmd 'my-ai -p {prompt}'   # 완전 수동. {prompt} 자리에 질문이 들어간다

## 모델·추론등급 (2026-08-28, P0-Z4)

**웹에서 고른다 — 단 목록은 각 AI 가 스스로 답한 것이다.** 기동 시 이 머신에 설치된 CLI 에게
한 번 묻는다: *"너는 어떤 모델과 추론 수준을 인자로 지정할 수 있나?"* 그 답을 그대로 하트비트에
실어 보내고, 웹 컴포저는 그 목록만 보여준다. 고른 값은 `claim_request` 로 돌아와 실제 인자가
된다 — **호출법(플래그 형태)도 그 AI 가 답한 것**이므로 플랫폼이 달라도 우리 코드는 그대로다.

왜 묻는가: 우리가 표로 갖고 있으면 그 표는 우리가 아는 시점에 멈춘다. 실제로 실측에서
`codex` 는 우리 표에 없던 모델을 답했고 `claude` 는 우리가 빠뜨린 것을 답했다. **자기가 무엇을
쓸 수 있는지 가장 잘 아는 것은 그 AI 자신이다.**

답은 `config.json` 에 캐시되어 다음 기동은 묻지 않는다(질의는 네 계정의 토큰을 쓰고 수십 초가
걸린다). 목록을 새로 받으려면 `--refresh-caps`.

우리 표에 없는 CLI 도 `--ai <이름>` 으로 지목하면 같은 방식으로 물어본다 — 답하면 그대로 쓴다.

명령을 통째로 직접 주면(`--cmd 'claude --model opus -p {prompt}'`) 그것이 이기고, 웹
선택기는 표시되지 않는다(반영되지 않을 조작면을 띄우지 않는다).

한 번만 처리하고 끝내려면 `--once`. 연결만 확인하려면 `--check`.

## 동시 처리 — 수요에 맞춰 늘고, 안 쓰면 줄어든다 (사용자 결정 2026-08-28)

**1개로 시작해서 필요한 만큼만 늘린다.** 직렬이면 5분짜리 조사 하나가 뒤따르는 10초짜리
질문을 통째로 막는데(서버는 애초에 병렬이다 — `claim_request` 는 원자적 점유이고
`wait_for_request` 는 여러 건을 한 번에 돌려준다), 그렇다고 처음부터 여러 개를 띄우면
질문이 하나뿐인 대부분의 시간에 쓰지도 않을 용량을 들고 있게 된다.

    확장   `wait_for_request` 가 돌려준 대기 질문 수가 현재 슬롯 수를 넘으면 그만큼 늘린다
           (상한 `--max-workers`, 기본 8). **수요가 관측된 순간에만** 늘어난다
    축소   `--worker-idle-sec`(기본 300초) 넘게 쉰 슬롯을 **오래된 것부터** 회수한다.
           최소 1개는 남긴다 — 0이 되면 다음 질문을 받을 창구가 사라진다

여기에 타이머 스레드도, 추가 sleep 도 없다. 서버가 대기를 최대 55초 보류하므로 **그 반환이
곧 tick** 이다(폴링 금지 원칙과 정합 — 우리는 시간을 재려고 서버를 두드리지 않는다).

슬롯을 꺼낼 때 **가장 최근에 쓴 것부터** 쓴다(LIFO). 그래야 안 쓰이는 슬롯이 계속 안 쓰인 채로
남아 회수 대상이 된다 — 돌아가며 쓰면(FIFO) 전부 조금씩 최근이 되어 아무것도 회수되지 않는다.

`--workers N` 은 **시작 개수**다(기본 1). 상한은 `--max-workers` 가 정한다 — 실질 한계는
**개인 계정의 쿼터**와 AI 런타임의 동시성인데 그건 우리가 알 수 없어 사용자에게 남긴다.

## 취소 (2026-08-28)

웹에서 중단을 누르거나 새 질문으로 갈아타면 서버가 그 작업을 취소한다. 러너는 그것을
`wait_for_request` 응답의 `canceled_task_ids` 로 **즉시** 알고(별도 채널이 아니다),
진행 중이던 AI 프로세스를 **죽인다** — 죽이지 않으면 아무도 볼 수 없는 답을 위해 개인 계정
토큰이 계속 탄다. 제출도 하지 않는다(해도 서버가 409 로 거절한다).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

_UA = "mysql-ai-bridge-agent/1"

#: 답변 끝에서 대화 제목을 실어 오는 한 줄 규약. CLI 런타임은 stdout 하나뿐이라 별도 채널이
#: 없다 — 제출 전에 이 줄을 떼어내므로 사용자 화면에는 남지 않는다.
_TITLE_MARK = "#TITLE:"

#: 서버가 최대 55초 보류한다. 그보다 넉넉히 잡아야 **정상 대기**를 타임아웃으로 오인하지 않는다.
_WAIT_TIMEOUT_SEC = 90.0
#: 조사·응답 생성 상한. **0 = 상한 없음(기본)** — 사용자 요구 2026-08-28:
#:
#:   "기본적으로 time_out 은 진행되어선 안되며, 각 단계에 대한 갱신을 수신받는 부분을
#:    기준으로. 연결은 살아있는 상태입니다."
#:
#: 고정 상한은 **일하고 있는 AI 를 끊는다**. 실제로 900초일 때 27단계짜리 조사가 그 벽에
#: 걸려 "AI 호출이 900초를 넘겨 중단했습니다" 로 끝났다(PB-0008 검증 중 관측) — 개인 AI 는
#: 답을 만들고 있었고, 서버도 기다릴 수 있었는데 중간에서 러너가 끊은 것이다.
#:
#: 그럼 멈춘 것과 일하는 것을 무엇으로 가르나 — **진행 신호**다. 도구를 부를 때마다 서버가
#: 점유 lease 를 밀어 주므로(`_renew_claim_lease`), 조사가 이어지는 한 lease 는 만료되지
#: 않고, 정말 멈추면 마지막 호출로부터 30분 뒤 서버가 회수한다. 회수되면 이 러너의 제출은
#: 409 로 거절되어 스스로 하차한다 — 상한은 **서버가 관측한 사실**로 집행되지, 러너의 시계로
#: 집행되지 않는다.
#:
#: 취소는 여전히 즉시 듣는다(`_CANCEL_TICK_SEC` 마다 확인 → 프로세스 kill). "무제한" 이
#: "사용자가 멈출 수 없다" 를 뜻하지 않는다.
#:
#: 값을 주면 그 초만큼만 기다린다(`--ai-timeout` · `BRIDGE_AI_TIMEOUT_SEC`) — 개인 계정
#: 쿼터를 스스로 제한하고 싶은 사용자를 위한 opt-in 이다.
_AI_TIMEOUT_SEC = float(os.environ.get("BRIDGE_AI_TIMEOUT_SEC", "0") or 0)
#: 진행 중인 AI 프로세스의 **취소 확인 간격**.
#:
#: ⚠ 이건 폴링이 아니다 — 서버를 두드리지 않는다. 자식 프로세스가 끝나기를 `Thread.join(timeout)`
#: 으로 기다리면서 그 틈에 취소 여부를 보는 것이고, 대기 자체는 여전히 블로킹이다(sleep 없음).
_CANCEL_TICK_SEC = 1.0
#: **시작** 동시 처리 수. 수요가 관측되면 늘어난다(`WorkerPool`).
_DEFAULT_WORKERS = 1
#: 확장 상한. 개인 계정 쿼터와 런타임 동시성이 실질 한계라 무제한은 위험하다 — 요청이 몰리면
#: 개인 머신에 수십 개 프로세스가 뜨고 쿼터가 한 번에 소진된다(사용자 결정 2026-08-28: 8).
_DEFAULT_MAX_WORKERS = 8
#: 이 시간 넘게 쉰 슬롯은 회수한다(사용자 결정 2026-08-28: 5분).
#: 너무 짧으면 질문이 드문드문 이어질 때 확장·축소를 반복하고, 너무 길면 유휴 슬롯이 오래 남는다.
_DEFAULT_WORKER_IDLE_SEC = 300.0
#: 대기 질문이 있는데 한 건도 처리하지 못한 채 반복되는 라운드의 상한.
#: 넘으면 조용히 도는 대신 **크게 실패**한다 — 간격 없는 재시도는 서버를 두드리는 폴링이다.
_MAX_STALLED_ROUNDS = 20


#: 재시작 대비 설정 파일. **토큰은 넣지 않는다** — 비밀이고, 어차피 세션과 함께 죽는다.
#: 저장하는 것은 다시 물어보기 번거로운 것들(주소·CA 경로·AI 선택)뿐이다.
_CONF_DIR = os.path.join(os.path.expanduser("~"), ".mysql-ai-bridge")
_CONF_PATH = os.path.join(_CONF_DIR, "config.json")


def save_conf(base: str, ca: str | None, ai: str, cmd: str | None,
              caps: dict | None = None) -> None:
    """다음 실행이 `--resume` 한 줄로 끝나게 한다.

    머신을 재시작하면 이 프로세스는 사라진다(사용자 지적 2026-08-27). 그때 사용자가 다시
    챙겨야 하는 것이 많을수록 **아무도 다시 띄우지 않는다.** 토큰만 새로 받으면 되게 한다.

    `caps` 는 각 AI 가 스스로 답한 능력(P0-Z4)이다. 여기 저장하는 이유는 **매 기동마다 다시
    묻지 않기 위해서**다 — 그 질의는 사용자 계정의 토큰을 쓰고 수십 초가 걸린다. 갱신은
    `--refresh-caps` 로 사용자가 명시할 때만(모델 목록이 바뀌는 일은 드물다).

    ⚠ 여기에는 **플래그 형태(`model`/`effort`)도 함께** 남지만 그것은 서버로 나가지 않는다.
    호출법을 아는 것은 이 파일과 러너뿐이다(P0-Z3 신뢰 경계).
    """
    try:
        os.makedirs(_CONF_DIR, exist_ok=True)
        payload = {"base": base, "ca": ca, "ai": ai, "cmd": cmd}
        if caps is not None:
            payload["caps"] = caps
        else:
            # 이번 실행이 능력을 새로 구하지 않았다면(예: `--cmd` 모드) 기존 캐시를 지우지
            # 않는다 — 다음 일반 기동이 다시 묻는 비용을 물지 않게.
            prev = load_conf().get("caps")
            if prev:
                payload["caps"] = prev
        with open(_CONF_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.chmod(_CONF_PATH, 0o600)
    except Exception as e:  # noqa: BLE001
        _log(f"설정 저장 실패(무시): {e}")


def load_conf() -> dict:
    try:
        with open(_CONF_PATH, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}

#: 연결이 **끊겼을 때만** 쓰는 복구 간격(feature-0045). 서버가 배포로 교체되는 몇 초 동안
#: 연결이 실패하는데, 그때 쉬지 않고 재시도하면 초당 수천 번을 두드려 사용자 머신의 CPU 를
#: 태운다. 대기(`wait_for_request`)에는 여전히 sleep 이 없다 — 이건 대기가 아니라 재연결이다.
#: 상한을 15초로 둔 이유: 롤링 배포 한 replica 의 교체가 보통 그 안에 끝나므로, 복구가
#: 지연되어 질문 인지가 늦어지는 일이 없다.
_RECONNECT_BACKOFF_START = 1.0
_RECONNECT_BACKOFF_MAX = 15.0

#: 서버가 "배포 교대 중" 이라고 답했을 때의 **하한**. 백오프가 아니라 고정값이다 — 자라지
#: 않으므로 인지가 늦어지지 않고, 엣지가 그 인스턴스를 후보에서 빼는 짧은 창(2s)에 호출이
#: 폭주해 계정 호출 상한을 태우는 것만 막는다.
_DRAINING_RETRY_FLOOR_SEC = 0.5

#: 하트비트 주기의 **기본값**(TASK-20260828T150000). 실제 값은 서버가 첫 응답으로 알려주고
#: 그 뒤로는 그것을 쓴다 — 클라이언트가 각자 정하면 서버의 판정 창이 사람마다 다른 의미가
#: 된다(P0-J 의 '환경 차이 금지' 와 같은 축). 여기 값은 서버 응답을 받기 전까지의 임시값이다.
_HEARTBEAT_INTERVAL_SEC = 30.0
#: 하트비트 호출의 응답 대기 상한. 이건 대기가 아니라 **짧은 신호**라 길게 잡을 이유가 없다.
_HEARTBEAT_TIMEOUT_SEC = 15.0
#: 서버가 알려준 주기의 **하한**. 서버가 0 이나 음수를 주는 사고에도 신호가 폭주하지 않게.
#: (상한은 두지 않는다 — 판정 창을 정하는 쪽이 서버이므로 길게 주는 것은 서버의 선택이다.)
_HEARTBEAT_MIN_INTERVAL_SEC = 5.0

#: 연결이 해제된 뒤(로그아웃) **진행 중 작업을 기다리는 유예**. 이 시간이 지나면 중단하고
#: 종료한다. 짧게 잡은 이유: 그 답변들은 이미 전달될 곳이 없고(토큰 무효 → 제출 401), 오래
#: 붙잡을수록 아무도 볼 수 없는 답을 위해 개인 계정 토큰만 탄다. 그래도 0 이 아닌 이유는
#: **곧 끝날 일을 중간에 끊지 않기** 위해서다.
_SHUTDOWN_GRACE_SEC = float(os.environ.get("BRIDGE_SHUTDOWN_GRACE_SEC", "") or 120.0)


def _log(msg: str) -> None:
    sys.stderr.write(f"[bridge] {msg}\n")
    sys.stderr.flush()


#: 평문이 허용되는 유일한 대상. 이름이 아니라 **호스트**로 판정한다.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _transport_is_safe(base: str) -> bool:
    """토큰을 이 주소로 보내도 되는가. https, 또는 진짜 loopback 만 참.

    접두 문자열 비교(`startswith("http://127.0.0.1")`)로는 안 된다 — userinfo 와 서브도메인이
    통과한다: `http://127.0.0.1@evil.example` 의 실제 호스트는 `evil.example` 이고,
    `http://127.0.0.1.evil.example` 도 마찬가지다. 둘 다 토큰을 평문으로 남의 서버에 보낸다.
    URL 을 **파싱해서 hostname 을 본다** — urllib 이 접속할 때 쓰는 것과 같은 값이다.
    """
    try:
        parts = urllib.parse.urlsplit(str(base or ""))
    except Exception:  # noqa: BLE001
        return False
    if parts.scheme == "https":
        return bool(parts.hostname)
    if parts.scheme == "http":
        return (parts.hostname or "").lower() in _LOOPBACK_HOSTS
    return False


# ── 서버 호출 ────────────────────────────────────────────────────────────────


class Api:
    def __init__(self, base: str, token: str, ca: str | None):
        self.base = base.rstrip("/")
        self.token = token
        self.ctx = ssl.create_default_context(cafile=ca) if ca else None

    def call(self, tool: str, payload: dict | None = None, timeout: float = 60.0) -> dict:
        return self._post(f"/api/ai/tools/{tool}", payload, timeout)

    def heartbeat(self, runtimes: list | None = None,
                  timeout: float = _HEARTBEAT_TIMEOUT_SEC) -> dict:
        """"살아 있다" + **"이런 걸 쓸 수 있다"**. 도구가 아니라 연결 유지 경로다.

        도구 목록에 넣지 않는 이유는 그것이 조사 도구의 목록이기 때문이다 — 거기 끼면 AI 에게
        "이걸 호출해 조사하라" 는 잘못된 신호를 준다. 인증은 도구와 **같은 토큰**을 쓴다.

        능력(`runtimes`)을 별도 채널이 아니라 여기에 싣는 이유 (P0-Z3): 살아 있음과 능력은
        **같은 사실의 두 면**이다. 따로 보내면 "살아 있다고 하는데 능력은 모르는" 또는 그
        반대의 상태가 생기고, 화면은 그 둘 중 어느 쪽을 믿을지 정해야 한다. 한 왕복으로
        묶으면 그 질문 자체가 생기지 않는다 — 러너가 죽으면 둘 다 함께 낡는다.
        """
        # ⚠ `if runtimes` 로 쓰면 **빈 목록이 미신고로 뭉개진다**(codex REV-20260828T170000 P1-3).
        # 그러면 `--cmd` 로 갈아탄 러너가 "고를 것 없음" 을 말하지 못하고, 서버에 남아 있던 과거
        # 목록이 계속 신선한 것으로 노출된다 — 사용자는 고를 수 있는데 반영되지 않는 화면을 본다.
        # `None`(신고할 처지가 아님)과 `[]`(신고했고 고를 것이 없음)은 여기서도 다른 값이다.
        return self._post("/api/ai/bridge_heartbeat",
                          {} if runtimes is None else {"runtimes": runtimes}, timeout)

    def _post(self, path: str, payload: dict | None = None, timeout: float = 60.0) -> dict:
        body = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base}{path}", data=body, method="POST",
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json", "User-Agent": _UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=self.ctx) as resp:
                return json.loads(resp.read().decode("utf-8", "replace") or "{}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            # 상태코드를 뭉개지 않는다 — 401(재발급 필요)·409(남이 점유)·429(상한)는
            # 호출측이 서로 다르게 대응해야 하는 신호다.
            return {"_http": e.code, "error": detail}
        except Exception as e:  # noqa: BLE001
            # ⚠ `_http: 0` = **연결 자체가 안 됐다**(TLS·DNS·거부). 0 은 falsy 라
            #   `if not r.get("_http")` / `if code:` 같은 진위 검사에서 **성공으로 읽힌다** —
            #   실제로 `--check` 가 사설 CA 미지정 상태에서 "연결 정상" 을 출력했다(라이브 실측
            #   2026-08-28). 호출측이 실수하지 않도록 명시 플래그를 함께 싣는다.
            return {"_http": 0, "_failed": True, "error": str(e)[:300]}


# ── 취소 원장 ────────────────────────────────────────────────────────────────


class CancelRegistry:
    """서버가 알려준 **취소된 task** 를 워커에게 전달하는 통로.

    대기 스레드(`wait_for_request`)와 워커 스레드가 함께 읽고 쓰므로 락으로 감싼다.
    락 없이 `set` 을 공유해도 CPython 에서는 대개 동작하지만, "대개" 로 두면 취소가 가끔
    안 먹는 버그가 되고 그건 재현이 거의 불가능하다.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ids: set[str] = set()

    def add_many(self, task_ids) -> list[str]:
        """새로 취소된 것만 골라 기록하고 그 목록을 돌려준다(로그용)."""
        fresh: list[str] = []
        with self._lock:
            for raw in task_ids or []:
                tid = str(raw or "")
                if tid and tid not in self._ids:
                    self._ids.add(tid)
                    fresh.append(tid)
        return fresh

    def is_canceled(self, task_id: str) -> bool:
        with self._lock:
            return str(task_id) in self._ids

    def forget(self, task_id: str) -> None:
        """처리를 마친 task 는 원장에서 뺀다 — 무한히 자라지 않게."""
        with self._lock:
            self._ids.discard(str(task_id))


# ── 동시 처리 슬롯 ───────────────────────────────────────────────────────────


class WorkerPool:
    """동시 처리 슬롯을 **수요에 맞춰 늘리고, 쉬는 것부터 회수한다**(사용자 결정 2026-08-28).

    왜 `Semaphore` 가 아닌가: 세마포어는 크기를 바꿀 수 없다. 종전에는 고정 N 이었고, 그래서
    질문이 하나뿐인 대부분의 시간에도 N 개를 들고 있었다.

    ## 슬롯을 목록으로 두는 이유

    카운터 하나로도 개수는 셀 수 있다. 그런데 "**오래된** 슬롯부터 회수" 는 개수만으로는
    표현되지 않는다 — 어느 것이 얼마나 쉬었는지 알아야 한다. 그래서 슬롯마다 `last_used` 를
    들고, 회수는 그 순서로 한다.

    ## 왜 LIFO 로 꺼내는가

    유휴 슬롯 중 **가장 최근에 쓴 것**을 준다. 돌아가며 쓰면(FIFO) 전부 조금씩 최근이 되어
    idle 임계를 넘는 슬롯이 영영 생기지 않고, 그러면 축소가 작동하지 않는다. 한쪽만 계속 쓰면
    나머지는 자연히 오래되어 회수 대상이 된다.

    ## 시간

    `time.monotonic()` 을 쓴다(벽시계는 NTP 보정·서머타임에 뒤로 갈 수 있다). 슬롯은 생성
    시각으로 초기화한다 — 0 같은 센티넬로 두면 "프로세스 시작 직후" 가 곧 "아주 오래 쉼" 이
    되어 첫 라운드에 회수된다.
    """

    def __init__(self, start: int, maximum: int, idle_sec: float, now: float,
                 clock=time.monotonic) -> None:
        # `clock` 은 **테스트 훅**이다. 시각을 락 안에서 만들어야 정렬 불변식이 지켜지는데
        # (아래 `release` 참조), 그러면 호출측이 시각을 주입할 수 없어 회수 순서를 결정적으로
        # 검증할 방법이 사라진다. 시계 자체를 갈아끼우면 둘 다 만족한다.
        self._clock = clock
        self._cv = threading.Condition()
        self._max = max(1, int(maximum))
        self._idle = float(idle_sec)
        self._next_id = 1
        #: 유휴 슬롯 `(last_used, id)` — **last_used 오름차순**(앞이 가장 오래 쉰 것).
        self._free: list[tuple[float, int]] = []
        #: 사용 중 슬롯 id.
        self._busy: set[int] = set()
        for _ in range(max(1, min(int(start), self._max))):
            self._free.append((now, self._next_id))
            self._next_id += 1

    # ── 조회 ────────────────────────────────────────────────────────────────

    @property
    def capacity(self) -> int:
        with self._cv:
            return len(self._free) + len(self._busy)

    @property
    def in_use(self) -> int:
        with self._cv:
            return len(self._busy)

    # ── 사용 ────────────────────────────────────────────────────────────────

    def try_acquire(self) -> int | None:
        """유휴 슬롯 하나를 잡는다. 없으면 `None`(블로킹하지 않는다)."""
        with self._cv:
            if not self._free:
                return None
            _, sid = self._free.pop()      # 가장 최근에 쓴 것 — 위 'LIFO' 참조
            self._busy.add(sid)
            return sid

    def release(self, sid: int) -> None:
        """슬롯을 돌려준다. 그 사이 축소로 사라진 슬롯이면 조용히 버린다.

        ⚠ **반납 시각을 락 안에서 만든다.** 호출측이 `time.monotonic()` 을 먼저 계산해 넘기면,
        먼저 시간을 얻은 스레드가 늦게 락을 잡는 순간 `_free` 가 시각 역순으로 쌓인다. 그러면
        `reap` 이 맨 앞만 보고 "아직 임계 전" 이라 판단해 **뒤에 갇힌 오래된 슬롯을 영영 회수하지
        못한다**(codex 리뷰 P2). 정렬 불변식은 이 한 줄에 걸려 있다.

        모르는 슬롯을 버리는 이유: 반납이 조용히 용량을 부풀리는 버그는 재현이 어렵다.
        """
        with self._cv:
            if sid not in self._busy:
                return
            self._busy.discard(sid)
            self._free.append((self._clock(), sid))     # 락 안 — 단조 증가가 보장된다
            self._cv.notify_all()

    # ── 확장·축소 ───────────────────────────────────────────────────────────

    def grow_for(self, pending: int) -> int:
        """대기 질문 `pending` 건을 **지금 진행 중인 것과 함께** 소화할 만큼 늘린다(상한까지).

        ⚠ 목표는 `in_use + pending` 이다. 대기 수만 보면 **진행 중인 작업이 쓰는 자리를 빼고**
        세어 과소 확장한다 — capacity 4 · busy 3 · pending 3 이면 총수요가 6인데 `grow_to(3)` 은
        아무것도 늘리지 않고, 결국 한 건만 시작된다(codex 리뷰 P1).

        **관측된 수요에만** 반응한다 — 예측해서 미리 늘리지 않는다. 예측이 빗나가면 그 비용은
        사용자 계정의 쿼터로 나간다.
        """
        added = 0
        with self._cv:
            now = self._clock()                      # 락 안에서 — `release` 와 같은 이유
            target = min(len(self._busy) + int(pending), self._max)
            while len(self._free) + len(self._busy) < target:
                self._free.append((now, self._next_id))
                self._next_id += 1
                added += 1
            if added:
                self._cv.notify_all()
        return added

    def reap(self, now: float) -> int:
        """`idle_sec` 넘게 쉰 유휴 슬롯을 **오래된 것부터** 회수한다. 회수 개수를 돌려준다.

        **최소 1개는 남긴다.** 0이 되면 다음 질문을 받을 창구가 사라지고, 그 상태는 스스로
        풀리지 않는다(확장은 수요를 봐야 하는데 수요를 보려면 슬롯이 있어야 한다).

        사용 중인 슬롯은 건드리지 않는다 — 오래 걸리는 조사가 회수되면 그 답변이 사라진다.
        """
        removed = 0
        with self._cv:
            while self._free and (len(self._free) + len(self._busy)) > 1:
                last_used, sid = self._free[0]
                if now - last_used <= self._idle:
                    break                    # 정렬돼 있으므로 뒤는 볼 필요 없다
                self._free.pop(0)
                removed += 1
        return removed


class ActiveTasks:
    """지금 처리 중인 task 들. **'유휴' 를 관측 가능한 사실로 만든다**(TASK-20260828T150000).

    사용자 요구(2026-08-28): "로그아웃 + 모든 요청이 완료되어 유휴 상태면 러너도 안전하게
    종료되게." 그 판정을 하려면 "지금 몇 건이 돌고 있는가" 를 물을 수 있어야 하는데, 종전에는
    워커 자리(세마포어)만 있고 **셀 수 있는 것이 없었다** — 세마포어는 잔여 자리를 알려줄 뿐
    누가 무엇을 하고 있는지 말해 주지 않는다.

    id 를 들고 있는 이유: 유예가 지났을 때 그 작업들을 **취소로 전환**해야 하고(그래야 자식 AI
    프로세스가 죽어 개인 계정 토큰이 계속 타지 않는다), 취소 통로는 task_id 로 말한다.
    """

    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._ids: set[str] = set()

    def enter(self, task_id: str) -> None:
        with self._cv:
            self._ids.add(str(task_id))

    def leave(self, task_id: str) -> None:
        with self._cv:
            self._ids.discard(str(task_id))
            self._cv.notify_all()

    def snapshot(self) -> list[str]:
        with self._cv:
            return sorted(self._ids)

    def count(self) -> int:
        with self._cv:
            return len(self._ids)

    def wait_idle(self, timeout: float) -> bool:
        """유휴가 될 때까지 기다린다. 유휴면 True, 유예가 먼저 끝나면 False.

        ⚠ 폴링하지 않는다 — 워커가 끝나면서 깨운다(`Condition`). 남은 시간을 매번 다시 계산하는
        이유: `wait` 는 깨어난 이유를 말해 주지 않으므로, 재계산 없이 반복하면 유예가 사실상
        무한이 된다(자주 깨는 워커가 있으면 영원히 기다린다).
        """
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._cv:
            while self._ids:
                remain = deadline - time.monotonic()
                if remain <= 0:
                    return False
                self._cv.wait(remain)
            return True


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
#: 실조회가 가능한 런타임(ollama)은 정적 목록 대신 그 결과를 쓴다 — 아는 방법이 있으면
#: 추측하지 않는다.
_RUNTIME_SPECS: dict[str, dict] = {
    "claude": {
        "label": "Claude",
        "argv": ["claude", "-p", "{prompt}"],
        "model": ["--model", "{model}"],
        "effort": ["--effort", "{effort}"],
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
        "argv": ["codex", "exec", "--skip-git-repo-check", "{prompt}"],
        "model": ["-m", "{model}"],
        # config override 로 넘긴다 — codex 에는 전용 effort 플래그가 없다.
        "effort": ["-c", "model_reasoning_effort={effort}"],
        "models": [
            {"value": "gpt-5.1-codex", "label": "GPT-5.1 Codex"},
            {"value": "gpt-5.1-codex-mini", "label": "GPT-5.1 Codex mini"},
        ],
        "efforts": [
            {"value": "low", "label": "낮음"},
            {"value": "medium", "label": "보통"},
            {"value": "high", "label": "높음"},
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
    "ollama": {
        "label": "Ollama",
        # HTTP 어댑터 — argv 가 없다(`ask_local_ai` 가 분기한다).
        "argv": [],
        "model": None,
        "effort": None,
        "models": [],      # 실조회(`_ollama_models`)로 채운다.
        "efforts": [],
    },
}

#: 하위 호환 — 종전 `(name, argv)` 순서쌍을 쓰던 자리(감지 순서 포함)를 위해 표에서 파생한다.
#: ollama 는 HTTP 어댑터라 여기 넣지 않는다(종전과 동일).
_CLI_ADAPTERS: list[tuple[str, list[str]]] = [
    (name, list(spec["argv"]))
    for name, spec in _RUNTIME_SPECS.items()
    if spec.get("argv")
]


def _which(name: str) -> str | None:
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def detect_ai() -> tuple[str, list[str]] | None:
    for name, argv in _CLI_ADAPTERS:
        if _which(name):
            return name, argv
    if _which("ollama"):
        return "ollama", []
    return None


#: AI 가 답한 **값**(모델·등급)에 요구하는 모양. 서버 쪽 `_CAPS_VALUE_RE` 와 같은 집합이다.
#:
#: 내용은 보지 않는다 — 어떤 모델이 있는지는 그 AI 의 소관이고, 우리가 아는 목록으로 거르면
#: "관대하게 수용" 이 아니게 된다(P0-Z4). 여기서 보는 것은 **모양뿐**이다: 이 값은 곧
#: `Popen` 인자가 되므로, 옵션으로 해석될 수 있는 것(선행 `-`)과 셸 메타문자·공백을 막는다.
#: 실제 모델 이름은 이 집합 안에 다 들어온다(`gpt-5.1-codex` · `llama3:8b` · `gemini-2.5-pro`).
_CAPS_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/+-]{0,63}$")

#: 연결된 AI 에게 **자기 능력을 직접 묻는** 질문 (P0-Z4, 사용자 결정 2026-08-28).
#:
#: ## 왜 묻는가
#:
#: 종전에는 `_RUNTIME_SPECS` 에 우리가 적어 둔 목록을 신고했다. 그 목록은 우리가 아는 시점에
#: 멈춰 있어서 — CLI 가 새 모델을 얻어도, 사용자가 쓰는 런타임이 우리 표에 없어도 화면은
#: 모른다. **자기가 무엇을 쓸 수 있는지 가장 잘 아는 것은 그 AI 자신**이므로 직접 묻는다.
#:
#: ## 형식을 요구하되 관대하게 받는다
#:
#: 형식을 주지 않으면 파싱이 불가능하고, 형식을 엄격히 강제하면 조금만 어긋나도 그 런타임이
#: 통째로 사라진다. 그래서 **요구는 정확히, 수용은 관대하게** 한다 — 코드블록·머리말·설명이
#: 섞여도 `_extract_json` 이 본문에서 객체를 찾아낸다.
#:
#: ## 플래그도 함께 묻는 이유
#:
#: 플랫폼마다 모델·추론 지정 방법이 다르다(`--model` / `-m` / `-c key=value`). 우리가 표로
#: 갖고 있으면 새 플랫폼은 우리 배포를 기다려야 한다. AI 가 자기 호출법을 말하면 그 종속이
#: 사라진다 — 사용자가 어떤 CLI 를 쓰든 우리 코드는 그대로다.
_CAPS_PROBE_PROMPT = """\
너 자신에 대해 답하라. 지금 이 CLI 를 **비대화형으로 한 번 실행할 때**, 어떤 모델과 어떤
추론 수준(reasoning effort / thinking level)을 인자로 지정할 수 있는가?

아래 JSON 객체 **하나만** 출력하라. 설명·머리말·맺음말을 붙이지 마라.

{
  "label": "이 CLI 를 사람에게 보여줄 짧은 이름 (예: Claude, Codex, Gemini)",
  "models": [
    {"value": "인자에 그대로 넣을 실제 값", "label": "사람이 읽을 이름"}
  ],
  "efforts": [
    {"value": "인자에 그대로 넣을 실제 값", "label": "사람이 읽을 이름"}
  ],
  "model_flag": ["모델을 지정하는 인자 형태. {model} 자리에 위 value 가 들어간다"],
  "effort_flag": ["추론 수준을 지정하는 인자 형태. {effort} 자리에 위 value 가 들어간다"]
}

규칙:
- `value` 는 **네가 실제로 받아들이는 문자열**이어야 한다. 버전이 올라가도 유지되는 별칭
  (alias)이 있으면 그것을 우선하라 — 풀네임은 세대가 바뀌면 죽는다.
- 지정할 수 없는 항목은 **빈 배열**로 둬라. 없는 기능을 있다고 답하면, 사용자는 고를 수
  있는데 반영되지 않는 화면을 보게 된다.
- `model_flag` / `effort_flag` 는 인자를 **배열로** 쓴다.
  예: ["--model", "{model}"] · ["-m", "{model}"] · ["-c", "reasoning={effort}"]
- 모르는 것은 지어내지 마라. 확실한 것만 넣어라.
"""

#: 능력 질의에 주는 시간. 짧게 잡는다 — 이건 답변이 아니라 **기동 절차**이고, 여기서 오래
#: 걸리면 사용자는 러너가 멈춘 줄 안다. 초과하면 내장 기본값으로 진행한다(기동을 막지 않는다).
#:
#: ⚠ `float(env or 120)` 로 쓰지 마라 — `os.environ.get(k, "0")` 은 **문자열 "0"**(truthy)을
#: 돌려주므로 `or` 가 단락되지 않고 timeout 이 0 이 된다. 그러면 질의가 시작하자마자
#: `TimeoutExpired` 로 죽고, 폴백이 조용히 삼켜 "AI 가 답을 안 했다" 로 보인다(실측으로 발견).
#: 변환을 **먼저** 하고 그 결과로 기본값을 고른다.
#: 실측(2026-08-28): claude 22.7초 · codex 112.3초. 후자가 120 에 아슬아슬해 여유를 둔다 —
#: 여기서 잘리면 그 런타임은 조용히 내장 기본값으로 떨어지고, 사용자는 자기 AI 가 답한 목록
#: 대신 우리가 적어 둔 (틀릴 수 있는) 목록을 보게 된다.
def _probe_timeout_from_env() -> float:
    """`BRIDGE_CAPS_PROBE_TIMEOUT` 을 **유한 양수**로만 받는다 (codex P2-6).

    검사 없이 `float()` 하면 `abc` 하나로 **모듈 import 가 실패**해 러너가 아예 뜨지 않고,
    `inf`/`nan` 은 `Thread.join()` 에서 `OverflowError`/`ValueError` 로 터진다. 음수는
    "기다리지 않고 백그라운드 probe 를 방치" 라는 최악의 조용한 동작이 된다.
    설정 하나가 기동을 못 하게 만드는 것은 어떤 경우에도 옳지 않다 — 이상하면 기본값으로 간다.
    """
    raw = os.environ.get("BRIDGE_CAPS_PROBE_TIMEOUT")
    if raw:
        try:
            got = float(raw)
        except (TypeError, ValueError):
            got = 0.0
        # `nan` 은 어떤 비교도 False 라 아래 범위 검사에서 자연히 걸러진다.
        if 5.0 <= got <= 1800.0:
            return got
        _log(f"BRIDGE_CAPS_PROBE_TIMEOUT={raw!r} 은 5~1800초 범위가 아닙니다 — 기본값을 씁니다.")
    return 240.0


_CAPS_PROBE_TIMEOUT_SEC = _probe_timeout_from_env()

#: probe stdout 상한 (codex P2-5). 오작동한 CLI 가 대량 출력을 쏟으면 그것이 전부 메모리에
#: 쌓이고, 이어지는 JSON 탐색이 그 위에서 반복 스캔한다. 정상 응답은 수 KB 다.
_CAPS_PROBE_MAX_BYTES = 256 * 1024
#: `_extract_json` 이 시도할 후보 `{` 개수 상한. 닫히지 않은 중괄호가 많으면 각 시작점마다
#: 본문 끝까지 훑어 O(n²) 가 된다.
_CAPS_JSON_MAX_CANDIDATES = 64


def _extract_json(text: str) -> dict | None:
    """본문에서 JSON 객체 하나를 **관대하게** 꺼낸다. 못 찾으면 None.

    AI 는 형식을 지키라고 해도 코드펜스를 붙이거나("```json ... ```"), 한 줄 설명을 앞에
    두거나, 뒤에 요약을 덧붙인다. 그 정도로 그 런타임을 통째로 버리면 "관대하게 수용" 이
    아니다 — 중괄호 균형을 세어 **첫 완전한 객체**를 찾는다.
    """
    s = str(text or "")[:_CAPS_PROBE_MAX_BYTES]
    start = s.find("{")
    tried = 0
    while start != -1 and tried < _CAPS_JSON_MAX_CANDIDATES:
        tried += 1
        depth, in_str, esc = 0, False, False
        for i in range(start, len(s)):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        got = json.loads(s[start:i + 1])
                    except ValueError:
                        break          # 이 후보는 깨졌다 — 다음 `{` 부터 다시
                    return got if isinstance(got, dict) else None
        start = s.find("{", start + 1)
    return None


def _coerce_options(raw: object, limit: int = 40) -> list[dict]:
    """AI 가 준 목록을 `[{value,label}]` 로 **관대하게** 맞춘다.

    받아들이는 모양(전부 실제로 관측되는 형태다):

        ["opus", "sonnet"]                        → value=label=문자열
        [{"value": "opus", "label": "Opus"}]      → 그대로
        [{"value": "opus"}]                       → label 은 value 로 채움
        [{"name": "opus", "description": "..."}]  → 흔한 키 이름 대체 수용
        {"opus": "Opus", "sonnet": "Sonnet"}      → 매핑도 목록으로

    모양이 어긋난 항목은 **그것만** 버린다. 하나가 이상하다고 나머지를 지우지 않는다.
    """
    items: list = []
    if isinstance(raw, dict):
        items = [{"value": k, "label": v} for k, v in raw.items()]
    elif isinstance(raw, list):
        items = list(raw)
    out: list[dict] = []
    seen: set = set()
    for it in items[:limit]:
        if isinstance(it, str):
            value, label = it, it
        elif isinstance(it, dict):
            value = it.get("value") or it.get("id") or it.get("name") or it.get("model") or ""
            label = it.get("label") or it.get("name") or it.get("title") or value
        else:
            continue
        value = str(value or "").strip()
        label = str(label or value).strip()
        # 값의 모양만 본다 — 내용(어떤 모델인가)은 AI 의 소관이다.
        if not value or not _CAPS_VALUE_RE.match(value) or value in seen:
            continue
        seen.add(value)
        out.append({"value": value, "label": (label or value)[:60]})
    return out


def _coerce_flag(raw: object, placeholder: str) -> list[str] | None:
    """AI 가 준 플래그 형태를 argv 조각으로 맞춘다. 쓸 수 없으면 None.

    ⚠ **이 값은 서버로 나가지 않는다.** 로컬 `config.json` 에만 남고 러너가 직접 쓴다 —
    그래서 서버가 손상되거나 응답이 변조돼도 여기에 임의 플래그를 밀어 넣을 수 없다
    (P0-Z3 가 세운 신뢰 경계를 P0-Z4 도 그대로 지킨다).

    받아들이는 모양: `["--model", "{model}"]` · `"--model {model}"` · `"--model={model}"`.
    치환 자리(`{model}`/`{effort}`)가 없으면 쓸 수 없다 — 값을 넣을 곳이 없기 때문이다.
    """
    if isinstance(raw, str):
        try:
            parts = shlex.split(raw)
        except ValueError:
            return None            # 따옴표가 안 닫힌 문자열
    elif isinstance(raw, list):
        parts = [str(p) for p in raw]
    else:
        return None
    parts = [p for p in (str(p).strip() for p in parts) if p]
    if not parts:
        return None
    # 인자 하나하나가 공백·따옴표 없는 단일 토큰이어야 한다(셸을 거치지 않으므로 공백이
    # 들어가면 그대로 한 인자가 되어 CLI 가 거절한다).
    if any((" " in p or '"' in p or "'" in p) for p in parts):
        return None

    # ⚠ 여기가 이 기능의 가장 날카로운 자리다. 이 값은 **검사 없이 `Popen` 인자가 된다** —
    #   모델·등급 값과 달리 신고 목록과 대조할 대상이 없기 때문이다(형태 그 자체이므로).
    #   그래서 형태를 좁게 고정한다:
    #
    #     ① 치환 자리(`{model}`)를 **정확히 하나** 포함한다 — 값을 넣을 곳이 없으면 쓸 수 없고,
    #        여럿이면 같은 값이 여러 인자로 퍼진다.
    #     ② 토큰은 **최대 2개**. 실존하는 형태가 전부 그 안에 든다
    #        (`--model {model}` · `-m {model}` · `--model={model}` · `-c key={effort}`).
    #     ③ 치환 자리가 아닌 토큰은 **`-` 로 시작**해야 한다(옵션이어야 한다).
    #
    #   ③이 없으면 `["sh", "-c", "{model}"]` 같은 답이 그대로 통과해 **셸을 실행**하고,
    #   ②가 없으면 `["--model", "{model}", "--dangerously-skip-permissions"]` 로 임의 플래그가
    #   따라붙는다. 둘 다 실측으로 통과하던 형태였다.
    #
    #   이 방어의 신뢰 모델: 플래그는 로컬 AI 가 답한 것이고 서버를 거치지 않는다. 그래도
    #   막는 이유는 (a) 캐시 파일이 오염될 수 있고 (b) AI 가 프롬프트를 오해할 수 있으며
    #   (c) 무엇보다 **이 값만은 대조할 목록이 없기** 때문이다 — 심층 방어가 필요한 정확한 지점.
    if len(parts) > 2:
        return None
    holders = [p for p in parts if placeholder in p]
    if len(holders) != 1:
        return None
    if any(not p.startswith("-") for p in parts if placeholder not in p):
        return None
    return parts


def sanitize_caps(raw: object) -> dict:
    """저장된 능력을 **다시 강제한다** (P0-Z4 심층 방어).

    질의 응답은 `probe_runtime_caps` 가 강제하지만, 그 결과는 `config.json` 을 거쳐 다음
    기동으로 돌아온다. 로드 시점에 강제하지 않으면 **파일이 곧 우회 경로**가 된다 —
    거기 적힌 플래그는 검사 없이 `Popen` 인자가 되기 때문이다.

    그 파일은 0600 이고 사용자 소유라 실질 위험은 낮다(쓸 수 있는 자는 러너 자체를 고칠 수도
    있다). 그래도 막는 이유: 이 검사는 사실상 공짜이고, "믿는 입력" 을 하나 줄이면 다음 사람이
    캐시 경로를 새 기능의 통로로 쓸 때 그 통로가 이미 좁혀져 있다.
    """
    out: dict = {}
    if not isinstance(raw, dict):
        return out
    for name, caps in raw.items():
        if not isinstance(name, str) or not _CAPS_VALUE_RE.match(name) or not isinstance(caps, dict):
            continue
        models = _coerce_options(caps.get("models"))
        if not models:
            continue
        model_flag = _coerce_flag(caps.get("model"), "{model}") if caps.get("model") else None
        effort_flag = _coerce_flag(caps.get("effort"), "{effort}") if caps.get("effort") else None
        argv = caps.get("argv")
        if argv is not None:
            # 호출 형태도 같은 규칙 — 첫 토큰은 실행 파일 이름(= 이 런타임)이어야 하고,
            # 프롬프트 자리가 정확히 하나 있어야 한다. 그 외 형태는 버리고 표로 폴백한다.
            argv = [str(a) for a in argv] if isinstance(argv, list) else []
            if (not argv or argv[0] != name
                    or sum(1 for a in argv if "{prompt}" in a) != 1
                    or len(argv) > 5
                    or any((" " in a or '"' in a or "'" in a) for a in argv)):
                argv = None
        entry = {
            "label": " ".join(str(caps.get("label") or name).split())[:60] or name,
            "models": models,
            "efforts": _coerce_options(caps.get("efforts"), limit=12) if effort_flag else [],
            "model": model_flag,
            "effort": effort_flag,
            "source": str(caps.get("source") or "cache")[:16],
        }
        if argv:
            entry["argv"] = argv
        out[name] = entry
    return out


def probe_runtime_caps(name: str, argv: list[str],
                       timeout: float | None = None) -> dict | None:
    """그 AI 에게 **직접 물어** 능력을 받는다 (P0-Z4). 실패하면 None.

    실패를 조용히 삼키지 않고 None 으로 알리는 이유: 호출측이 내장 기본값으로 폴백할지
    (표에 있는 런타임) 아니면 신고에서 뺄지(모르는 런타임) 정해야 한다.
    """
    cmd = [_CAPS_PROBE_PROMPT if a == "{prompt}" else a.replace("{prompt}", _CAPS_PROBE_PROMPT)
           for a in argv]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=(timeout if timeout and timeout > 0
                                       else _CAPS_PROBE_TIMEOUT_SEC))
    except Exception:  # noqa: BLE001  (미설치·타임아웃·권한 — 전부 "못 물었다" 로 같다)
        return None
    if proc.returncode != 0:
        return None
    # 출력이 아무리 커도 여기서 자른다 — `capture_output` 은 전부 메모리에 담는다.
    got = _extract_json((proc.stdout or "")[:_CAPS_PROBE_MAX_BYTES])
    if not got:
        return None
    models = _coerce_options(got.get("models"))
    if not models:
        # 모델을 하나도 못 받았으면 이 질의는 실패다 — 등급만으로는 선택기를 세울 수 없다.
        return None
    model_flag = _coerce_flag(got.get("model_flag"), "{model}")
    effort_flag = _coerce_flag(got.get("effort_flag"), "{effort}")
    efforts = _coerce_options(got.get("efforts"), limit=12) if effort_flag else []
    label = " ".join(str(got.get("label") or name).split())[:60] or name
    return {
        "label": label,
        "models": models,
        "efforts": efforts,
        # 플래그가 없으면 그 축은 지정 불가 — 목록도 비운다(위 `efforts` 와 같은 이유).
        "model": model_flag,
        "effort": effort_flag,
        "source": "probe",
    }


def _ollama_models() -> list[dict]:
    """이 머신에 실제로 받아 둔 ollama 모델. 실패하면 빈 목록 — **추측하지 않는다**.

    빈 목록은 "고를 것이 없다" 로 신고되고, 화면에서는 그 런타임 그룹이 통째로 빠진다.
    없는 모델을 목록에 남기면 사용자가 고른 순간 실행이 실패한다(P0-T 가 겪은 형태).
    """
    try:
        base = os.environ.get("BRIDGE_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
        tags = base.replace("/api/generate", "/api/tags")
        req = urllib.request.Request(tags, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=5.0) as r:
            data = json.loads(r.read().decode("utf-8", "replace") or "{}")
    except Exception:  # noqa: BLE001
        return []
    out: list[dict] = []
    for m in (data.get("models") or []):
        name = str((m or {}).get("name") or "").strip()
        if name:
            out.append({"value": name, "label": name})
    return out


def detect_runtimes(only: str | None = None, cached: dict | None = None,
                    detail_out: dict | None = None,
                    probe: bool = False) -> list[dict]:
    """이 머신에서 **쓸 수 있는 런타임 전부**와 각자가 고를 수 있는 것 (P0-Z3).

    종전 `detect_ai()` 는 첫 번째 하나만 골랐다. 그것은 "무엇으로 답할까" 의 답으로는
    충분했지만, 웹에 "무엇을 고를 수 있는가" 를 알려주려면 **전부**가 필요하다.

    `only` 가 주어지면 그 하나로 제한한다(`--ai` 의 의미: 자동 감지 대신 이것만 쓴다).
    표에 없는 이름이면 제한을 무시한다 — 사용자의 오타가 러너를 벙어리로 만들지 않게.

    ## 목록은 **그 AI 가 정한다** (P0-Z4, 사용자 결정 2026-08-28)

    각 런타임에 한 번 물어(`probe_runtime_caps`) 답을 그대로 쓴다. 실패하면 내장 표
    (`_RUNTIME_SPECS`)로 폴백한다 — 물어보지 못했다고 화면에서 사라지면, 종전에 잘 되던
    사용자가 이유 없이 기능을 잃는다.

    `cached` 를 주면 묻지 않고 그것을 쓴다(매 기동마다 사용자 토큰을 태우지 않기 위해).
    """
    names = list(_RUNTIME_SPECS.keys())
    if only and only in _RUNTIME_SPECS:
        names = [only]
    elif only:
        # 표에 없는 런타임도 사용자가 지목했으면 물어본다 — 우리가 모르는 CLI 여도
        # 자기 능력은 스스로 말할 수 있다(그것이 P0-Z4 의 요지다).
        names = [only] if _which(only) else names

    cached = cached or {}
    present = [n for n in names if _which(n)]
    # 우리 표에 없는 CLI 도 물어본다 (P0-Z4 — "플랫폼에 관계없이"). 호출법을 모르므로 가장
    # 흔한 두 형태를 시도한다: `<cli> -p <프롬프트>` 와 `<cli> <프롬프트>`. 둘 다 실패하면
    # 그 런타임은 신고에서 빠진다(사용자는 `--cmd` 로 직접 줄 수 있다).
    unknown_argvs: dict = {}
    for n in present:
        if n not in _RUNTIME_SPECS:
            unknown_argvs[n] = [[n, "-p", "{prompt}"], [n, "{prompt}"]]

    # 물어야 할 것들을 **동시에** 묻는다. 순차로 하면 기동이 각 런타임의 응답 시간을 모두
    # 더한 만큼 늦어진다(실측: claude 23초 + codex 112초 = 135초). 병렬이면 가장 느린 하나
    # (112초)로 끝난다 — 그리고 이건 최초 1회뿐이다(다음 기동은 캐시를 쓴다).
    probed: dict = {}
    ask = [n for n in present
           if cached.get(n) is None
           and ((_RUNTIME_SPECS.get(n) or {}).get("argv") or n in unknown_argvs)] if probe else []
    if ask:
        _log(f"쓸 수 있는 모델·추론 수준을 물어보는 중… ({', '.join(ask)} — 최초 1회, 수십 초)")

        # 전체 질의에 **하나의 절대 deadline** 을 둔다 (codex P2-4). 후보를 순차로 시도하는
        # 표 밖 CLI 는 후보마다 timeout 을 다 쓸 수 있어(240초 × 2) main 의 대기(250초)를
        # 넘긴다. 그러면 main 은 폴백으로 기동하고, 뒤에 남은 스레드가 아무도 읽지 않을 답을
        # 위해 계속 토큰과 CPU 를 태운다. deadline 을 공유해 남은 시간이 없으면 멈춘다.
        deadline = time.monotonic() + _CAPS_PROBE_TIMEOUT_SEC

        def _probe(nm: str) -> None:
            for argv in (unknown_argvs.get(nm) or [list(_RUNTIME_SPECS[nm]["argv"])]):
                left = deadline - time.monotonic()
                if left <= 5.0:
                    return           # 남은 시간이 의미 없다 — 시작하지 않는 것이 유일한 절약
                got = probe_runtime_caps(nm, argv, timeout=left)
                if got:
                    # 어느 호출 형태가 통했는지 함께 남긴다 — 실제 질문도 그 형태로 보낸다.
                    got["argv"] = argv
                    probed[nm] = got
                    return

        threads = [threading.Thread(target=_probe, args=(n,), daemon=True) for n in ask]
        for t in threads:
            t.start()
        for t in threads:
            # deadline 이 공유되므로 여기서 기다릴 시간도 그 하나로 정해진다.
            t.join(max(1.0, deadline - time.monotonic()) + 5.0)
        for n in ask:
            got = probed.get(n)
            if got:
                _log(f"  {n}: 모델 {len(got['models'])}종"
                     + (f" · 추론 {len(got['efforts'])}단계" if got["efforts"] else "")
                     + " (본인 응답)")
            else:
                _log(f"  {n}: 응답을 받지 못해 내장 기본값을 씁니다.")

    out: list[dict] = []
    for name in present:
        spec = _RUNTIME_SPECS.get(name) or {}
        caps = cached.get(name) or probed.get(name)

        if caps is None:
            # 폴백 — 우리가 아는 만큼. ollama 는 HTTP 라 물을 수 없어 실조회가 그 자리다.
            models = _ollama_models() if name == "ollama" else list(spec.get("models") or [])
            caps = {
                "label": str(spec.get("label") or name),
                "models": models,
                "efforts": list(spec.get("efforts") or []) if spec.get("effort") else [],
                "model": spec.get("model"),
                "effort": spec.get("effort"),
                "source": "builtin",
            }

        if not caps.get("models"):
            # 고를 것이 없는 런타임은 신고하지 않는다 — 화면에 빈 그룹만 남는다.
            continue
        # 호출법을 포함한 **상세**는 여기 남긴다(서버로 나가지 않는다 — 아래 신고와 구분).
        #
        # ⚠ 폴백(`builtin`)은 **캐시하지 않는다**(codex P2-3). 캐시하면 최초 기동의 일시적
        #   실패(인증 지연·타임아웃)가 영구화된다 — 다음 기동은 캐시가 있다고 묻지 않으므로,
        #   인증이 복구돼도 낡은 내장 목록을 계속 보여준다. 사용자는 `--refresh-caps` 를
        #   알기 전까지 그것이 틀렸다는 사실조차 모른다. 물어서 얻은 것만 남긴다.
        if detail_out is not None and caps.get("source") != "builtin":
            detail_out[name] = caps
        # ⚠ 항목을 **재구성한다**(얕은 복사 금지 — codex P2-1). `list(caps["models"])` 는
        #   내부 dict 를 그대로 참조하므로, 오염된 항목에 붙은 여분 키(`{"value":…,
        #   "model":["--secret"]}`)가 하트비트 HTTP 본문에 실려 나간다. 서버 sanitizer 가
        #   저장 전에 지우더라도 **전송은 이미 일어났고**, 그러면 "호출법은 서버로 나가지
        #   않는다" 는 이 기능의 계약이 거짓이 된다.
        def _pair(o: dict) -> dict:
            return {"value": str(o.get("value") or ""), "label": str(o.get("label") or "")}

        out.append({
            "runtime": name,
            "label": str(caps.get("label") or name),
            "models": [_pair(o) for o in caps["models"]],
            # 플래그가 없으면 등급도 신고하지 않는다: 지정 수단이 없는데 목록을 주면
            # 다시 "고를 수 있는데 반영은 안 되는" 상태가 된다(P0-T 가 지운 바로 그것).
            "efforts": [_pair(o) for o in (caps.get("efforts") or [])] if caps.get("effort") else [],
        })
    return out


def resolve_caps(only: str | None, cached: dict | None,
                 refresh: bool) -> tuple[list[dict], dict]:
    """신고할 목록과 **로컬에 남길 능력 상세**를 함께 만든다 (P0-Z4).

    두 값을 가르는 것이 이 함수의 존재 이유다:

      - 반환 `[0]` = 서버로 나가는 신고. 사람이 고를 목록만 담는다.
      - 반환 `[1]` = `config.json` 에 남는 상세. **호출법(플래그)이 여기 있다.**

    호출법을 서버에 보내지 않으므로, 서버가 손상되거나 응답이 변조돼도 러너가 실행할 인자의
    *형태* 는 바뀌지 않는다 — 바뀔 수 있는 것은 그 형태에 채울 값뿐이고, 그 값은 신고 목록과
    대조된다(P0-Z3 의 두 번째 자물쇠).
    """
    detail: dict = {}
    reported = detect_runtimes(only, cached=(None if refresh else (cached or None)),
                               detail_out=detail, probe=True)
    return reported, detail


#: `ask_local_ai` 가 "사용자가 취소했다" 를 알리는 신호.
#:
#: 실패 문자열로 섞지 않는 이유: 실패는 **답을 제출해서 알려야 하고**(침묵보다 낫다), 취소는
#: **제출하면 안 된다**(사용자가 안 보겠다고 한 것이다). 두 결과를 같은 값으로 돌려주면
#: 호출측이 그것을 구분하지 못해 둘 중 하나가 반드시 틀린 동작을 한다.
CANCELED = "__canceled__"


def _run_cli_cancelable(cmd: list[str], cancel_check) -> tuple[bool, str]:
    """CLI 를 돌리되 **취소되면 죽인다**. (성공여부, 본문 | CANCELED)

    왜 `subprocess.run` 이 아닌가: `run` 은 끝날 때까지 블로킹이라 그동안 도착한 취소를 볼 수
    없다. 그러면 사용자가 중단을 눌러도 개인 계정 토큰이 그 조사가 끝날 때까지 계속 탄다 —
    취소의 실질 목적이 바로 그 낭비를 막는 것이다.

    ⚠ 여기에도 sleep 은 없다. 자식이 끝나기를 `Thread.join(timeout)` 으로 **블로킹 대기**하고,
    그 반환 틈에 취소를 확인할 뿐이다. 서버를 두드리지 않으므로 폴링이 아니다.
    """
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:  # noqa: BLE001
        return False, f"AI 실행 실패: {e}"

    # 파이프를 비우는 일은 별도 스레드에 맡긴다. 여기서 직접 읽으면 자식이 큰 출력을 낼 때
    # 파이프 버퍼가 차서 서로 기다리는 교착이 된다(고전적인 Popen 함정).
    box: dict[str, str] = {}

    def _drain() -> None:
        out, err = proc.communicate()
        box["out"] = out or ""
        box["err"] = err or ""

    pump = threading.Thread(target=_drain, daemon=True)
    pump.start()

    waited = 0.0
    while pump.is_alive():
        pump.join(_CANCEL_TICK_SEC)
        waited += _CANCEL_TICK_SEC
        if cancel_check():
            _kill(proc)
            pump.join(5.0)
            return False, CANCELED
        if _AI_TIMEOUT_SEC and waited >= _AI_TIMEOUT_SEC:
            _kill(proc)
            pump.join(5.0)
            return False, f"AI 호출이 {int(_AI_TIMEOUT_SEC)}초를 넘겨 중단했습니다."

    if proc.returncode != 0:
        return False, f"AI 가 오류로 끝났습니다(exit {proc.returncode}): {box.get('err', '')[:400]}"
    return True, (box.get("out") or "").strip()


def _kill(proc) -> None:
    """자식을 확실히 끝낸다. 이미 죽었으면 조용히 지나간다."""
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass


def offered_options(runtimes: list | None, runtime: str) -> tuple[list, list]:
    """**이 러너가 실제로 신고한** 그 런타임의 (모델, 등급) 목록. 없으면 빈 목록.

    정적 표(`_RUNTIME_SPECS`)가 아니라 신고를 보는 이유 (codex REV-20260828T170000 P1-5):
    둘은 갈릴 수 있다 —

      - `--ai codex` 로 제한하면 신고는 codex 뿐이지만 표에는 claude 도 있다
      - PATH 에 없는 런타임은 신고에서 빠지지만 표에는 남아 있다
      - ollama 의 모델 목록은 **실조회 결과**라 표에는 아예 없다

    표를 대조하면 "자기가 신고한 값만 실행한다" 가 거짓이 되고, 실제로는 "소스에 적혀 있고
    PATH 에 있으면 실행한다" 가 된다. 그 차이는 사용자가 `--ai` 로 세운 제한을 서버 응답이
    넘어서는 형태로 드러난다.

    `runtimes` 가 `None` 이면(신고 자체를 안 하는 `--cmd` 모드) 빈 목록 — 어차피 그 경로는
    지정값을 쓰지 않는다.
    """
    for rt in (runtimes or []):
        if str(rt.get("runtime") or "") == runtime:
            return list(rt.get("models") or []), list(rt.get("efforts") or [])
    return [], []


def build_cmd(runtime: str, prompt: str, model: str | None = None,
              effort: str | None = None, runtimes: list | None = None,
              caps: dict | None = None) -> list[str]:
    """지정 (런타임, 모델, 추론등급) 을 **그 CLI 의 실제 인자**로 옮긴다 (P0-Z3).

    대조 대상은 **이 러너가 신고한 목록**(`runtimes`)이다 — 서버가 뭘 돌려주든 우리가 고를 수
    있다고 말한 것만 실행한다. `runtimes` 를 주지 않으면 정적 표로 폴백한다(단위 테스트·
    구 호출부 호환). 그 폴백은 신고보다 넓을 수 있으므로 **운영 경로는 반드시 신고를 넘긴다**.

    표 밖 값은 **조용히 버린다** — 알 수 없는 문자열을 인자로 넘기면 CLI 가 통째로 실패하고,
    그러면 답이 아예 오지 않는다. 버린 사실은 호출측(`ask_local_ai`)이 사용자에게 밝힌다.

    프롬프트는 **인자로** 넘긴다(셸 미경유) — 질문에 셸 메타문자가 섞여도 그대로 전달되고
    명령 주입 경로가 생기지 않는다. 모델·등급도 같은 규칙을 따른다.
    """
    spec = _RUNTIME_SPECS.get(runtime) or {}
    # 호출 형태의 출처: 우리 표 → 없으면 **질의 때 통했던 형태**(표 밖 CLI). 둘 다 없으면
    # 인자를 만들 수 없으므로 빈 목록이 되고, 호출측이 종전 경로로 떨어진다.
    argv = list(spec.get("argv") or (caps or {}).get("argv") or [])
    flags: list[str] = []

    # 호출법(플래그 형태)의 출처 — **그 AI 가 스스로 답한 것**이 우선이고, 없으면 내장 표
    # (P0-Z4). 이 값은 로컬 `config.json` 에서만 오고 서버를 거치지 않는다.
    local = caps or {}
    model_flag = local.get("model") if local.get("model") is not None else spec.get("model")
    effort_flag = local.get("effort") if local.get("effort") is not None else spec.get("effort")

    if runtimes is None:
        allowed_models = list(local.get("models") or spec.get("models") or [])
        allowed_efforts = list(local.get("efforts") or spec.get("efforts") or [])
    else:
        allowed_models, allowed_efforts = offered_options(runtimes, runtime)

    def _valid(options: list, value: str | None) -> bool:
        if not value:
            return False
        return any(str(o.get("value")) == value for o in options)

    if model and model_flag and _valid(allowed_models, model):
        flags += [a.replace("{model}", model) for a in model_flag]
    if effort and effort_flag and _valid(allowed_efforts, effort):
        flags += [a.replace("{effort}", effort) for a in effort_flag]

    # 플래그는 **프롬프트 앞**에 둔다. 서브커맨드(`codex exec`)와 위치 인자(프롬프트) 사이가
    # 옵션의 자리이고, 프롬프트 뒤에 붙이면 CLI 에 따라 프롬프트의 일부로 먹힌다.
    out: list[str] = []
    for a in argv:
        if a == "{prompt}" or "{prompt}" in a:
            out += flags
            flags = []
            out.append(prompt if a == "{prompt}" else a.replace("{prompt}", prompt))
        else:
            out.append(a)
    return out + flags


def ask_local_ai(kind: str, argv: list[str], prompt: str, custom: str | None,
                 cancel_check=None, model: str | None = None,
                 effort: str | None = None,
                 runtimes: list | None = None,
                 caps: dict | None = None) -> tuple[bool, str]:
    """내 AI 에게 물어 답 문자열을 얻는다. (성공여부, 본문)

    `model`·`effort` 는 사용자가 **웹에서 고른 것**이다 (P0-Z3). 유효성은 `runtimes`(이 러너가
    하트비트로 신고한 목록)로 판정한다 — 서버가 준 값을 그대로 믿지 않는다. 지정이 없거나
    신고 밖이면 이 머신의 AI 설정이 정한다.

    `custom`(`--cmd`)이 있으면 그것이 이긴다 — 사용자가 명령 전체를 직접 준 것이므로 그 위에
    우리가 플래그를 얹으면 중복 지정으로 CLI 가 거절할 수 있다.

    `cancel_check` 는 "지금 취소됐는가" 를 묻는 함수다. 취소되면 본문 자리에 `CANCELED` 를
    돌려준다 — 실패와 구분해야 호출측이 "제출하지 않는다" 를 선택할 수 있다.
    """
    _canceled = cancel_check or (lambda: False)
    if custom:
        argv = shlex.split(custom)
        kind = "custom"
    if kind == "ollama":
        # ⚠ 이 경로는 `build_cmd` 를 타지 않으므로 **여기서 직접 대조한다**
        # (codex REV-20260828T170000 P1-5). 안 하면 서버가 준 임의 문자열이 그대로 생성 요청의
        # 모델명이 되어, 이 머신에 없는 모델을 부르거나 남의 모델을 부른다.
        _models, _ = offered_options(runtimes, "ollama")
        _ok = model and any(str(o.get("value")) == model for o in _models)
        model_name = model if _ok else os.environ.get("BRIDGE_OLLAMA_MODEL", "llama3")
        # 이미 취소됐다면 호출 자체를 하지 않는다(HTTP 는 중간에 끊어도 서버 쪽 생성이 계속될
        # 수 있어, 시작하지 않는 것이 유일하게 확실한 절약이다).
        if _canceled():
            return False, CANCELED
        req = urllib.request.Request(
            os.environ.get("BRIDGE_OLLAMA_URL", "http://127.0.0.1:11434/api/generate"),
            data=json.dumps({"model": model_name, "prompt": prompt,
                             "stream": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=(_AI_TIMEOUT_SEC or None)) as r:
                return True, str(json.loads(r.read().decode("utf-8", "replace")).get("response") or "")
        except Exception as e:  # noqa: BLE001
            return False, f"로컬 LLM 호출 실패: {e}"

    _local = (caps or {}).get(kind) or {}
    if (kind in _RUNTIME_SPECS or _local.get("argv")) and (model or effort):
        cmd = build_cmd(kind, prompt, model, effort, runtimes, _local)
    else:
        # 프롬프트는 **인자로** 넘긴다(셸을 거치지 않는다) — 질문 본문에 셸 메타문자가 섞여도
        # 그대로 전달되고, 명령 주입 경로가 생기지 않는다.
        cmd = [prompt if a == "{prompt}" else a.replace("{prompt}", prompt) for a in argv]
    if _canceled():
        return False, CANCELED
    return _run_cli_cancelable(cmd, _canceled)


# ── 프롬프트 ─────────────────────────────────────────────────────────────────


def compose_prompt(api: Api, task: dict) -> str:
    """내 AI 에게 줄 프롬프트. **조사 도구 사용법을 함께 준다** — 그래야 DB 를 실제로 본다."""
    q = str(task.get("question") or "")
    ctxt = str(task.get("conversation_context") or "")
    sysp = str(task.get("system_prompt") or "")
    scope = task.get("scope") or {}
    atts = task.get("attachments") or []
    parts: list[str] = []
    if sysp:
        # 운영자가 설정한 5단계 지침(전역·제품·역할·계정·개인). **맨 앞**에 둔다 — 뒤에 두면
        # 앞의 지시가 이기고, 그러면 운영자 설정이 사실상 무시된다.
        parts += ["── 아래 지침을 시스템 프롬프트로 삼아 답하라 ──", sysp,
                  "── 지침 끝 ──", ""]
    if scope.get("product_name") or scope.get("datasources"):
        # 어떤 제품·어떤 DB 를 보고 있는지 모르면 엉뚱한 스키마를 찾아 헤맨다.
        who = scope.get("product_name") or ""
        key = scope.get("product_key") or ""
        ds = ", ".join(str(d) for d in (scope.get("datasources") or []))
        parts += [f"대상 제품: {who}" + (f" ({key})" if key else "")
                  + (f" · 데이터소스: {ds}" if ds else ""), ""]
    parts += [
        "너는 사내 DB 질의 어시스턴트다. 아래 사용자 질문에 답하라.",
        "",
        # ⚠ 본문 형태를 **정확히** 준다. 종전 예시는 `task_id` 가 없고 인자를 `arguments` 로
        #   감싸지 않아, 그대로 따르면 400("task_id 가 필요합니다") 또는 "schema_name과
        #   table_name은 필수" 만 돌아왔다 — 러너 경로의 조사가 통째로 실패하는 형태였다
        #   (codex REV-20260828T040000 P1).
        "필요하면 이 도구들을 HTTP 로 직접 호출해 실제 DB 를 조사하라"
        " (POST · JSON 본문 · 헤더에 Authorization: Bearer <아래 토큰>).",
        f"  공통 본문 = {{\"task_id\":\"{task.get('task_id')}\","
        " \"reason\":\"지금 이걸 왜 조사하는지 한 문장\", \"arguments\":{...}}",
        f"  {api.base}/api/ai/tools/list_schemas      arguments: {{}}",
        f"  {api.base}/api/ai/tools/describe_schema   arguments: {{\"schema_name\":\"...\"}}",
        f"  {api.base}/api/ai/tools/describe_table    arguments:"
        " {\"schema_name\":\"...\",\"table_name\":\"...\"}",
        f"  {api.base}/api/ai/tools/search_tables     arguments: {{\"keyword\":\"...\"}}",
        f"  {api.base}/api/ai/tools/get_table_indexes arguments:"
        " {\"schema_name\":\"...\",\"table_name\":\"...\"}",
        f"  {api.base}/api/ai/tools/get_foreign_keys  arguments:"
        " {\"schema_name\":\"...\",\"table_name\":\"...\"}",
        f"  {api.base}/api/ai/tools/execute_sql       arguments: {{\"sql\":\"SELECT ...\"}}",
        f"  토큰: {api.token}",
        "",
        # 조사 내역은 사용자 화면의 「실행 단계」에 그대로 그려진다. 사유가 없으면 서버가
        # 도구의 일반적 목적으로 채우는데, 그건 *이 질문에서의* 이유가 아니다.
        "`reason` 은 매 호출에 넣어라 — 사용자 화면의 실행 단계에 「어떤 이유로 → 어떤 작업」"
        " 으로 표시된다.",
        "",
        "추측하지 말고 조사한 사실만 쓰라. 확인하지 못한 것은 '미확인' 이라고 밝혀라.",
        "답변만 출력하라(머리말·맺음말 없이).",
        # 제목 축: 러너는 CLI 의 stdout 만 받으므로 별도 채널이 없다. 마지막 한 줄을 규약으로
        # 삼고 제출 전에 떼어낸다 — 마커가 없으면 답변은 그대로다(파싱 실패가 답을 망치지 않음).
        f"답변의 **맨 마지막 줄**에 `{_TITLE_MARK} <이 대화를 요약한 30자 안팎의 제목>` 을"
        " 한 줄 덧붙여라. 이 줄은 사용자에게 보이지 않고 대화 제목으로만 쓰인다.",
    ]
    if ctxt:
        parts += ["", "── 이전 대화 ──", ctxt]
    if atts:
        names = ", ".join(f"{a.get('filename')}(id={a.get('attachment_id')})" for a in atts)
        parts += ["", f"첨부 {len(atts)}건: {names}",
                  f"  본문 읽기: POST {api.base}/api/ai/tools/read_task_attachment "
                  f"{{\"task_id\":\"{task.get('task_id')}\",\"attachment_id\":<id>}}",
                  "  첨부가 있는 질문은 반드시 본문을 읽고 답하라."]
    # ⚠ 첨부 **쓰기** 규약(```attachment-edit``` / ```attachment-new```)은 여기 적지 않는다 —
    #   `system_prompt`(agent_core base)가 이미 싣고 온다. 여기에 또 쓰면 두 벌이 되고, 형식이
    #   갈리는 순간 서버 파서가 아는 쪽만 파일이 된다. 실측에서도 개인 AI 는 이 안내 없이
    #   블록을 정확히 만들어 냈다(2026-08-28) — 빠진 것은 안내가 아니라 **서버의 처리**였다.
    parts += ["", "── 질문 ──", q]
    return "\n".join(parts)


def split_title(answer: str) -> tuple[str, str]:
    """답변에서 `#TITLE:` 마지막 줄을 떼어 `(본문, 제목)` 으로 가른다.

    마커가 없으면 본문은 **손대지 않는다** — 규약을 지키지 않는 런타임이 있어도 답변이
    상하지 않아야 한다(제목이 없을 뿐이다). 마지막 줄만 본다: 중간에 같은 문자열이 있으면
    그건 답변 내용이지 제목이 아니다.
    """
    body = str(answer or "")
    lines = body.rstrip().split("\n")
    if not lines:
        return body, ""
    tail = lines[-1].strip()
    # `#` 를 요구한다 — `lstrip("#")` 로 느슨하게 받으면 답변의 정상적인 마지막 줄
    # `Title: 실제 데이터 열` 까지 제목으로 오인해 **본문에서 지운다**(codex P2).
    if not tail.upper().startswith(_TITLE_MARK.upper()):
        return body, ""
    rest = "\n".join(lines[:-1]).rstrip()
    if not rest:
        # 제목 줄이 전부라면 떼어낼 수 없다 — 떼면 빈 답변이 되어 제출이 400 으로 거절되고
        # 사용자 화면에는 대기 말풍선만 남는다. 제목을 포기하고 본문을 지킨다.
        return body, ""
    title = tail[len(_TITLE_MARK):].strip().strip("\"'`").strip()
    return rest, title[:120]


# ── 한 건 처리 ───────────────────────────────────────────────────────────────


def handle_one(api: Api, task_id: str, claimed: dict, kind: str, argv: list[str],
               custom: str | None, cancels: "CancelRegistry | None" = None,
               runtimes: list | None = None, caps: dict | None = None) -> bool:
    """이미 **점유된** task 하나를 처리한다.

    점유(`claim_request`)를 여기서 하지 않고 호출측(대기 루프)이 하는 이유: 점유가 늦으면 그
    task 가 `wait_for_request` 결과에 계속 남아, 워커가 다 찼을 때 같은 것을 반복해서 받게 된다
    (그리고 그 반복이 곧 서버를 두드리는 tight loop 다). 점유는 값싸고 즉시 끝나므로 대기
    루프에서 처리하고, 오래 걸리는 AI 호출만 워커로 넘긴다.
    """
    _canceled = (lambda: cancels.is_canceled(task_id)) if cancels else (lambda: False)

    # 웹에서 고른 (런타임·모델·추론등급). 유효성은 **이 러너의 신고**로 판정한다 (P0-Z3) —
    # 서버가 준 값을 그대로 믿지 않는다. 지정이 없으면 이 머신의 AI 설정이 정한다.
    want = claimed.get("requested") or {}
    want_runtime = str(want.get("runtime") or "").strip()
    want_model = str(want.get("model") or "").strip() or None
    want_effort = str(want.get("reasoning_level") or "").strip() or None
    run_kind, run_argv = kind, argv
    unmet: list[str] = []

    if want_runtime and want_runtime != run_kind:
        # 사용자가 이 머신의 **다른** 런타임을 골랐다. 신고에 있고(= 우리가 고를 수 있다고
        # 말했고) 지금도 실재할 때만 그쪽으로 보낸다. `--ai` 로 제한한 사용자의 의도를
        # 서버 응답이 넘어서지 않게, 정적 표가 아니라 신고를 본다(codex P1-5).
        _offered = any(str(rt.get("runtime") or "") == want_runtime for rt in (runtimes or []))
        _known = (_RUNTIME_SPECS.get(want_runtime) or {}).get("argv")
        _learned = ((caps or {}).get(want_runtime) or {}).get("argv")
        if _offered and (_known or _learned) and _which(want_runtime):
            run_kind = want_runtime
            run_argv = list(_known or _learned)
        else:
            unmet.append(f"런타임 {want_runtime}")

    # 반영하지 못하는 지정을 **조용히 버리지 않는다**(codex P1-4). 같은 계정에 러너가 여럿이면
    # 목록을 신고한 러너와 질문을 가져간 러너가 다를 수 있고, 그때 사용자는 자기가 고른 것이
    # 적용됐다고 믿는다. 무엇이 반영되지 않았는지는 답변에 적어 사용자가 알게 한다.
    _models, _efforts = offered_options(runtimes, run_kind)
    if want_model and not any(str(o.get("value")) == want_model for o in _models):
        unmet.append(f"모델 {want_model}")
    if want_effort and not any(str(o.get("value")) == want_effort for o in _efforts):
        unmet.append(f"추론등급 {want_effort}")

    prompt = compose_prompt(api, {**claimed, "task_id": task_id})
    _picked = "".join([
        f", 모델 {want_model}" if want_model else "",
        f", 추론 {want_effort}" if want_effort else "",
    ])
    _log(f"{task_id}: 내 AI({run_kind})에게 전달{_picked}"
         + (f" — 미반영: {', '.join(unmet)}" if unmet else ""))
    ok, answer = ask_local_ai(run_kind, run_argv, prompt, custom, _canceled,
                              model=want_model, effort=want_effort, runtimes=runtimes,
                              caps=caps)
    if answer == CANCELED:
        # 사용자가 취소했다. **제출하지 않는다** — 서버도 409 로 거절하지만, 여기서 멈추는 것이
        # 토큰과 왕복을 아끼는 지점이다.
        _log(f"{task_id}: 사용자가 취소했다 — 중단(제출 안 함)")
        return False
    if not ok or not answer.strip():
        # 실패해도 **답을 제출한다** — 제출하지 않으면 사용자 화면은 30분간 대기 말풍선인 채로
        # 남고, 무엇이 잘못됐는지 아무도 모른다. 실패를 말하는 것이 침묵보다 낫다.
        answer = (answer or "내 AI 가 빈 응답을 돌려주었습니다.") + \
            "\n\n(이 답변은 연결된 AI 에서 생성하지 못해 자동 안내로 대체된 것입니다.)"

    # 답을 만드는 동안 취소됐을 수 있다 — 제출 **직전**에 한 번 더 본다.
    # 제목 분리보다 **앞**에 둔다: 어차피 버릴 답이면 가공할 이유가 없다.
    if _canceled():
        _log(f"{task_id}: 답변 완료 직전에 취소됨 — 제출하지 않는다")
        return False

    # 제목 줄은 답변에서 떼어 별도 필드로 보낸다 — 본문에 남기면 사용자가 규약 문자열을 본다.
    answer, title = split_title(answer)

    # 반영하지 못한 지정을 **밝힌다**(codex REV-20260828T170000 P1-4). 조용히 기본값으로
    # 답하면 사용자는 자기가 고른 모델로 답이 나온 줄 안다 — 그 오해는 화면 어디에도 드러나지
    # 않는다. 같은 계정에 러너가 여럿일 때(목록을 신고한 러너 ≠ 질문을 가져간 러너) 실제로
    # 발생한다. 제목 분리 **뒤**에 붙인다: 앞에 붙이면 이 줄이 제목 규약 위치를 밀어낸다.
    if unmet:
        answer = (answer or "") + (
            f"\n\n> 참고: 요청하신 {' · '.join(unmet)} 은(는) 이 AI 에서 쓸 수 없어"
            " 기본 설정으로 답했습니다."
        )

    payload = {"task_id": task_id, "answer": answer, "source_tasks": [task_id]}
    if title:
        payload["title"] = title
    res = api.call("submit_answer", payload, timeout=120.0)
    if res.get("_http") == 409:
        # 취소 신호를 못 본 채 여기까지 왔다(서버가 마지막 관문). 정상 흐름이다.
        _log(f"{task_id}: 서버가 제출을 거절했다(취소된 요청) — 버린다")
        return False
    if res.get("_failed"):
        # ⚠ 연결 실패는 `_http == 0` 이라 아래 진위 검사에 걸리지 않는다 (codex P2-2).
        #   그대로 두면 **저장 여부를 모르는데 "제출 완료" 라고 기록**한다. 답변은 이미 만들어
        #   놓았으므로 한 번 더 시도할 값어치가 있다 — 서버의 `SubmittedAt IS NULL` 가드가
        #   중복 제출을 409 로 막으므로 재시도는 안전하다(멱등).
        _log(f"{task_id}: 제출 중 연결 실패 — 한 번 더 시도합니다: {res.get('error')}")
        time.sleep(_RECONNECT_BACKOFF_START)
        res = api.call("submit_answer", payload, timeout=120.0)
        if res.get("_failed") or res.get("_http"):
            _log(f"{task_id}: 제출 실패(재시도 후) {res.get('_http')} {res.get('error')} — "
                 "이 답변은 전달되지 않았다. lease 만료 뒤 다시 제안된다.")
            return False
    if res.get("_http"):
        _log(f"{task_id}: 제출 실패 {res.get('_http')} {res.get('error')}")
        return False
    _log(f"{task_id}: 제출 완료 (대화 반영={res.get('delivered_to_conversation')})")
    return True


# ── 메인 ─────────────────────────────────────────────────────────────────────


def start_heartbeat(api: Api, stop: threading.Event,
                    runtimes: list | None = None) -> threading.Thread:
    """연결 유지 신호를 보내는 데몬 스레드 (TASK-20260828T150000).

    **대기 스레드와 분리한 것이 이 기능의 핵심이다.** 대기(`wait_for_request`)는 빈 워커 자리를
    잡아야 들어가므로, 러너가 바쁠 때 정확히 멈춘다 — 연결 유지 신호가 바쁠 때 멈추면 아무
    소용이 없다(긴 조사 도중에 화면이 '대기 안 함' 이 되고, 토큰 수명도 밀리지 않는다).

    **실패해도 죽지 않는다.** 서버가 배포로 잠깐 사라지는 것과 토큰이 폐기된 것은 다른 사건이고,
    전자로 러너를 끝내면 배포마다 사용자가 다시 띄워야 한다. 401 도 여기서는 **로그만** 남긴다 —
    종료 판정은 메인 루프에 맡긴다(거기에 재발급 안내가 이미 있고, 두 곳에서 죽이면 안내가 두
    벌이 되어 갈린다).

    ⚠ 이 스레드의 `wait` 는 폴링이 아니다 — 서버에서 **아무것도 가져오지 않는다**. 질문 인지는
    여전히 서버 보류(`wait_for_request`)가 하고, 그 즉시성은 이 주기와 무관하다.
    """
    def _loop() -> None:
        interval = _HEARTBEAT_INTERVAL_SEC
        while not stop.is_set():
            # 능력은 **매번** 싣는다. 처음 한 번만 보내면 서버가 재시작하거나 토큰 행이 갈릴 때
            # 화면의 목록이 영영 비고, 그 빈 목록은 "러너가 없다" 와 구분되지 않는다.
            # 서버는 값이 그대로면 쓰지 않으므로(쓰기 증폭 없음) 매번 싣는 비용이 없다.
            res = api.heartbeat(runtimes)
            code = res.get("_http")
            if code == 401:
                # 복귀 안내는 여기서 하지 않는다 — 대기 루프 한 곳이 정본이다(두 곳에서
                # 안내하면 문구가 갈리고, 한쪽만 고쳐지는 순간 틀린 안내가 남는다).
                _log("하트비트 401 — 토큰이 무효해졌습니다(로그아웃 또는 만료). "
                     "곧 대기 루프가 재발급 방법을 안내합니다.")
            elif code or res.get("_failed"):
                # 순단·배포 교대. 서버의 판정 창이 주기의 3배라 한 번 놓친 것은 흡수된다.
                _log(f"하트비트 실패 {code}: {str(res.get('error') or '')[:120]}")
            else:
                # 주기는 **서버가 정한다**(P0-J 의 환경 차이 금지와 같은 축). 하한을 두는 것은
                # 서버가 0 을 주는 등의 사고로 신호가 폭주하지 않게 하기 위해서다.
                try:
                    interval = max(_HEARTBEAT_MIN_INTERVAL_SEC,
                                   float(res.get("interval_sec") or interval))
                except (TypeError, ValueError):
                    pass
            stop.wait(interval)

    t = threading.Thread(target=_loop, name="bridge-heartbeat", daemon=True)
    t.start()
    return t


def shutdown_after_drain(active: ActiveTasks, cancels: CancelRegistry,
                         grace_sec: float = _SHUTDOWN_GRACE_SEC) -> bool:
    """연결이 명시적으로 해제됐다 — **하던 일을 마치고** 종료한다(사용자 요구 2026-08-28).

    > "웹브라우저 내 로그아웃 + 모든 요청사항이 완료되어 유휴상태가 확인된다면 더 이상
    >  사용되지 않을 브릿지 프로세스도 안전하게 종료될 수 있도록"

    | 상태 | 하는 일 |
    |---|---|
    | 유휴(진행 중 0건) | 즉시 종료 — 더 할 일이 없다 |
    | 진행 중 있음 | 유예 안에서 **끝나기를 기다린다**(죽이는 것은 마지막 수단) |
    | 유예 초과 | 취소로 전환 → 자식 AI 프로세스가 죽는다 → 종료 |

    유예를 두는 이유와 무한정 기다리지 않는 이유가 같다: 이 답변들은 **전달될 곳이 이미
    없다**(로그아웃으로 토큰이 죽어 `submit_answer` 가 401 이다). 그래도 곧 끝날 일을 중간에
    끊지는 않고, 오래 걸리는 것은 붙잡지 않는다 — 붙잡으면 아무도 볼 수 없는 답을 위해
    사용자의 **개인 계정 토큰이 계속 탄다**(P0-T 에서 취소를 만든 것과 같은 이유).

    반환값은 "유휴 상태로 끝났는가" — 호출측 로그가 두 결말을 구분해 말할 수 있게 한다.
    """
    n = active.count()
    if n == 0:
        _log("진행 중인 작업이 없습니다 — 브리지 러너를 종료합니다.")
        return True
    _log(f"진행 중 {n}건이 끝나기를 기다립니다(최대 {grace_sec:.0f}초). "
         "이미 로그아웃되어 답변은 대화에 전달되지 않습니다.")
    if active.wait_idle(grace_sec):
        _log("진행 중이던 작업이 모두 끝났습니다 — 브리지 러너를 종료합니다.")
        return True
    remaining = active.snapshot()
    cancels.add_many(remaining)
    _log(f"유예가 지나 {len(remaining)}건을 중단합니다: {', '.join(remaining)} — 종료합니다.")
    # 취소는 워커가 다음 확인 시점(_CANCEL_TICK_SEC)에 본다. 그 한 tick 만 준다 —
    # 여기서 오래 기다리면 '안전한 종료' 가 다시 '종료되지 않음' 이 된다.
    active.wait_idle(_CANCEL_TICK_SEC * 3)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="mysql-ai 브리지 상주 러너")
    ap.add_argument("--base", default=os.environ.get("BRIDGE_BASE", ""), help="서비스 베이스 URL")
    ap.add_argument("--token", default=os.environ.get("BRIDGE_TOKEN", ""), help="mat_ 토큰")
    ap.add_argument("--ca", default=os.environ.get("BRIDGE_CA", "") or None, help="사설 CA 인증서 경로")
    ap.add_argument("--ai", default=os.environ.get("BRIDGE_AI", ""),
                    help="claude|codex|gemini|ollama, 또는 PATH 상의 다른 AI CLI 이름. "
                         "⚠ 모르는 이름은 능력을 묻기 위해 **실제로 한두 번 실행**한다 — "
                         "AI 가 아닌 프로그램을 지목하지 마라(그 프로그램의 부수효과는 막지 못한다)")
    ap.add_argument("--cmd", default=os.environ.get("BRIDGE_CMD", "") or None,
                    help="직접 지정할 AI 명령. {prompt} 자리에 질문이 들어간다")
    ap.add_argument("--once", action="store_true", help="한 건만 처리하고 종료")
    ap.add_argument("--check", action="store_true", help="연결만 확인하고 종료")
    ap.add_argument("--resume", action="store_true",
                    help="지난 설정을 불러온다(주소·CA·AI). 토큰만 새로 주면 된다")
    ap.add_argument("--refresh-caps", action="store_true",
                    help="쓸 수 있는 모델·추론 수준을 AI 에게 **다시 묻는다**"
                         "(기본은 저장된 답을 재사용 — 질의는 네 계정 토큰을 쓴다)")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("BRIDGE_WORKERS", 0))
                    or _DEFAULT_WORKERS,
                    help=f"**시작** 동시 처리 수 (기본 {_DEFAULT_WORKERS}). 수요가 오면 늘어난다")
    ap.add_argument("--max-workers", type=int,
                    default=int(os.environ.get("BRIDGE_MAX_WORKERS", 0)) or _DEFAULT_MAX_WORKERS,
                    help=f"확장 상한 (기본 {_DEFAULT_MAX_WORKERS}). 개인 계정 쿼터가 실질 한계다")
    ap.add_argument("--worker-idle-sec", type=float,
                    default=float(os.environ.get("BRIDGE_WORKER_IDLE_SEC", 0))
                    or _DEFAULT_WORKER_IDLE_SEC,
                    help=f"이 시간 넘게 쉰 슬롯을 오래된 것부터 회수 (기본 {int(_DEFAULT_WORKER_IDLE_SEC)}초)")
    # main 이 같은 창에 들인 축 — AI 호출 상한을 진행 신호 기반으로 뒀다(TASK-…140000).
    ap.add_argument("--ai-timeout", type=float,
                    default=_AI_TIMEOUT_SEC,
                    help="AI 호출 상한(초). 기본 0 = 상한 없음 — 진행 중이면 끊지 않는다"
                         "(서버가 진행 신호로 lease 를 갱신하고, 멈추면 회수한다)")
    args = ap.parse_args()
    # 전역을 여기서 확정한다 — 취소 감시 루프가 이 값을 읽는다.
    globals()["_AI_TIMEOUT_SEC"] = max(0.0, float(args.ai_timeout or 0))
    max_workers = max(1, int(args.max_workers or _DEFAULT_MAX_WORKERS))
    # ⚠ 시작값을 상한으로 **clamp** 한다. 종전엔 `max(workers, max_workers)` 였는데, 그러면
    #   `--workers 100 --max-workers 8` 이 상한을 100 으로 밀어올렸다 — 상한이 상한이 아니게
    #   된다(codex 리뷰 P2). 기존 `BRIDGE_WORKERS` 가 큰 머신에서 새 안전장치가 통째로
    #   무력화되는 경로이기도 하다.
    workers = max(1, min(int(args.workers or 1), max_workers))
    if int(args.workers or 1) > max_workers:
        _log(f"--workers {args.workers} 가 상한 {max_workers} 를 넘어 {workers} 로 시작합니다"
             " (상한을 올리려면 --max-workers).")
    idle_sec = max(1.0, float(args.worker_idle_sec or _DEFAULT_WORKER_IDLE_SEC))

    # 재시작 후 복귀 경로 — 명시 인자가 우선이고, 빈 것만 지난 설정으로 채운다.
    if args.resume:
        conf = load_conf()
        args.base = args.base or conf.get("base") or ""
        args.ca = args.ca or conf.get("ca")
        # ⚠ `ai` 는 **상속하지 않는다** (P0-Z5, 라이브 실측 2026-08-28).
        #
        #   P0-Z3 이전에 `ai` 는 "무엇으로 답할까" 하나만 정했고, 그 값은 자동 감지 결과여도
        #   저장해 두는 것이 편의였다. 그런데 P0-Z3 이후 같은 값이 **신고 목록까지 좁힌다** —
        #   의미가 바뀌었는데 저장·상속 규칙은 그대로였다.
        #
        #   결과: `--ai` 를 준 적 없는 사용자도 첫 기동의 자동 감지 결과가 `ai` 로 굳고,
        #   `--resume` 이 그것을 상속해 **다른 런타임이 화면에서 사라진다**. 실제로 라이브
        #   재기동에서 codex 가 설치돼 있는데 claude 만 신고됐다(사용자 요청은 정확히
        #   "claude 뿐만 아니라 codex 등" 이었다).
        #
        #   `ai` 는 그 실행의 제한이지 복원할 설정이 아니다. 제한하려면 매번 명시한다 —
        #   그래야 "지금 무엇이 제한되고 있는가" 가 명령줄에 그대로 보인다.
        #   (`detect_ai()` 가 실행 런타임을 매번 다시 정하므로 잃는 것은 없다.)
        args.cmd = args.cmd or conf.get("cmd")
        if not args.token:
            _log("토큰이 필요합니다 — 웹에서 '연결 정보 만들기' 로 새로 받아 --token 에 주세요.")
            return 2

    # 저장된 능력은 `--resume` 과 무관하게 읽는다 — 그것은 사용자가 준 설정이 아니라
    # 우리가 관측한 결과이고, 매번 다시 묻는 비용을 아끼는 것이 저장의 목적이다.
    # 저장된 값도 **다시 강제한다** — 그러지 않으면 이 파일이 곧 우회 경로가 된다.
    conf_caps = sanitize_caps(load_conf().get("caps"))

    if not args.base or not args.token:
        _log("FATAL: --base 와 --token 이 필요합니다.")
        return 2
    if not _transport_is_safe(args.base):
        # 토큰이 이 채널로 나간다. loopback 만 예외.
        _log("FATAL: --base 는 https 여야 합니다(loopback 예외).")
        return 2

    api = Api(args.base, args.token, args.ca)

    if args.cmd:
        kind, argv = "custom", []
    else:
        picked = (args.ai, dict(_CLI_ADAPTERS).get(args.ai, [])) if args.ai else None
        if picked and args.ai == "ollama":
            picked = ("ollama", [])
        if not picked or (args.ai and args.ai not in dict(_CLI_ADAPTERS) and args.ai != "ollama"):
            # ⚠ 표 밖 이름을 여기서 자동 감지로 갈아치우면, 사용자가 `--ai mycli` 로 지목한
            #   것이 조용히 claude/codex 로 바뀐다(codex P2-2). 그러면 runtime 지정이 없는
            #   요청이 사용자가 고르지 않은 AI 로 처리되고, 캐시에도 틀린 `kind` 가 남는다.
            #   PATH 에 실재하면 그 이름을 그대로 쓴다 — 호출 형태는 질의가 알아낸다.
            if args.ai and _which(args.ai):
                picked = (args.ai, [args.ai, "-p", "{prompt}"])
            else:
                picked = detect_ai()
        if not picked:
            _log("FATAL: 쓸 수 있는 AI 를 찾지 못했습니다. --ai 또는 --cmd 로 지정하세요.")
            return 2
        kind, argv = picked
    _log(f"AI = {kind}" + (f" ({args.cmd})" if args.cmd else ""))
    # 저장하는 `ai` 는 **사용자가 명시한 것만**이다(위 상속 주석과 같은 이유). 자동 감지
    # 결과를 저장하면 그것이 다음 실행의 제한으로 승격된다.
    save_conf(args.base, args.ca, (args.ai or ""), args.cmd)

    # ⚠ 연결 확인에 `wait_for_request` 를 쓰면 안 된다 (라이브 실측 2026-08-28).
    #
    #   그 도구는 **질문이 없으면 55초를 보류하도록 설계**돼 있다(그것이 '폴링 아님' 의 실체다).
    #   그런데 여기서는 10초 timeout 으로 불렀으므로, **대기 질문이 없는 정상 상태에서 반드시
    #   read timeout** 이 나고 `--check` 가 "연결 실패" 를 출력했다. 온보딩 시점이 정확히 그
    #   상태다 — 지시문이 ③단계로 `--check` 를 권하는데 그것이 **항상 실패**했다.
    #
    #   실측: `list_open_requests` 0.0초/200 (연결 정상) · `wait_for_request` 10초 timeout ·
    #   같은 호출을 90초로 주면 55.3초 뒤 `timed_out: true` 로 정상 반환.
    #
    #   직전 수정이 `_failed` 를 보게 하면서(거짓 "연결 정상" 제거) 이 결함이 드러났다 —
    #   한쪽 오독을 고치니 반대쪽 오독이 보인 형태다. 확인용 호출은 **즉시 답하는 도구**여야
    #   한다. `list_open_requests` 는 같은 인증·같은 경로를 쓰면서 바로 돌아온다.
    probe = api.call("list_open_requests", {"limit": 1}, timeout=20.0)
    if probe.get("_http") == 401:
        _log("FATAL: 토큰이 무효합니다(발급자가 로그아웃했거나 만료). 재발급이 필요합니다.")
        return 3
    if args.check:
        # `_http` 만 보면 **연결 실패(0)를 성공으로 읽는다** — 사설 CA 미지정 상태에서 실제로
        # "연결 정상." 을 출력했다. `--check` 가 거짓 안심을 주면 사용자는 러너가 왜 아무 일도
        # 안 하는지 알 수 없다.
        failed = bool(probe.get("_http")) or bool(probe.get("_failed"))
        if failed:
            _log(f"연결 실패: {probe.get('error')}")
            if probe.get("_failed"):
                _log("  사설 CA 를 쓰는 서버라면 --ca <rootCA.pem> 을 지정하세요.")
            return 1
        _log("연결 정상.")
        return 0

    # 이 머신이 무엇을 쓸 수 있는가 (P0-Z3). `--cmd` 로 명령을 통째로 준 사용자는 신고하지
    # 않는다 — 그 명령에 모델·등급이 이미 박혀 있고, 웹에서 고른 값은 반영되지 않는다.
    # 반영되지 않을 목록을 화면에 띄우는 것이 P0-T 가 지운 바로 그 상태다.
    # 목록은 **각 AI 가 스스로 답한 것**이다 (P0-Z4). 한 번 물으면 `config.json` 에 남고
    # 다음 기동은 묻지 않는다 — 그 질의는 사용자 계정의 토큰을 쓰고 수십 초가 걸린다.
    # 갱신은 `--refresh-caps` 로 명시할 때만(모델 목록이 바뀌는 일은 드물다).
    caps: dict = {}
    if args.cmd:
        runtimes = []
        _log("모델·추론등급은 --cmd 의 명령이 정합니다(웹 선택기는 표시되지 않습니다).")
    else:
        _cached = None if args.refresh_caps else (conf_caps or None)
        runtimes, caps = resolve_caps(args.ai or None, _cached, args.refresh_caps)
        if runtimes:
            _log("고를 수 있는 것: " + " · ".join(
                f"{r['label']}({len(r['models'])}종"
                + (f", 추론 {len(r['efforts'])}단계" if r["efforts"] else "")
                + ")" for r in runtimes))
            _by_probe = [n for n, c in caps.items() if (c or {}).get("source") == "probe"]
            _log("  출처: " + ("본인 응답 " + ", ".join(_by_probe) if _by_probe else "내장 기본값")
                 + ("" if args.refresh_caps or not _cached else " (캐시 — 갱신은 --refresh-caps)"))
        else:
            _log("고를 수 있는 AI 를 찾지 못했습니다 — 웹 선택기는 표시되지 않습니다.")
        # 물어서 얻은 답을 남긴다(다음 기동은 묻지 않는다). 저장 실패는 기동을 막지 않는다 —
        # 그때는 다음에 다시 묻게 될 뿐이다.
        # 표 밖 CLI 는 질의가 **통한 호출 형태**를 알아냈다 — 실제 질문도 그 형태로 보낸다
        # (기본 추정 `-p` 가 아니라). 이것이 없으면 질의는 성공했는데 답변만 실패한다.
        _learned = (caps.get(kind) or {}).get("argv")
        if _learned and kind not in _RUNTIME_SPECS:
            argv = list(_learned)
        if caps:
            save_conf(args.base, args.ca, (args.ai or ""), args.cmd, caps=caps)

    # 연결 유지 신호를 먼저 띄운다 — 첫 질문이 오기 전(대기만 하는 동안)에도 토큰 수명이
    # 밀려야 하고, 화면의 '대기 중' 표시도 그때부터 참이어야 한다.
    heartbeat_stop = threading.Event()
    start_heartbeat(api, heartbeat_stop, runtimes)

    cancels = CancelRegistry()
    #: 동시 처리 슬롯. 수요가 오면 늘고, 안 쓰면 오래된 것부터 준다.
    pool = WorkerPool(workers, max_workers, idle_sec, time.monotonic())
    #: 지금 처리 중인 task. 종료 시 '유휴인가' 를 물을 수 있게 한다(TASK-20260828T150000).
    #: 슬롯(`pool`)과 다른 사실을 센다 — 저쪽은 '자리가 몇 개인가', 이쪽은 '무엇이 돌고 있는가'.
    active = ActiveTasks()
    #: 점유가 반복 실패한 task — 같은 것을 무한히 다시 시도해 서버를 두드리지 않도록 건너뛴다.
    skip: set[str] = set()
    #: 서버에 대기 질문이 있는데 한 건도 처리하지 못한 연속 라운드 수(spin 감지).
    stalled = 0
    done_once = threading.Event()

    #: 연결이 끊겼을 때의 복구 간격(feature-0045). 대기가 아니라 재연결이므로 sleep 이 있다.
    backoff = 0.0

    _log(f"대기 시작 — 웹에서 질문이 오면 즉시 처리합니다. "
         f"(동시 {workers}건에서 시작 · 수요 시 최대 {max_workers} · "
         f"{int(idle_sec)}초 유휴 시 회수 · Ctrl+C 로 종료)")
    while True:
        # ⚠ **여기서 워커 자리를 잡지 않는다** (codex P1-2, 2026-08-28).
        #
        # 종전에는 `slots.acquire()` 가 이 앞에 있었다(tight loop 차단 목적). 그런데 취소와 새
        # 질문은 **같은 응답**으로 오므로, 자리가 없어 여기서 멈추면 `wait_for_request` 를 아예
        # 부르지 않게 되고 **취소 통보도 함께 끊긴다** — 워커가 다 찬 동안 사용자가 중단을 눌러도
        # 러너는 최대 `_AI_TIMEOUT_SEC`(약 28분) 동안 모른 채 개인 계정 토큰을 계속 태운다.
        # 취소를 즉시 인지시키려던 설계가 정작 가장 필요한 순간에 꺼져 있었다.
        #
        # 그래서 **대기는 항상** 하고, 자리는 디스패치 직전에 **비차단으로** 잡는다.
        # ⚠ 대기 자체에는 여전히 sleep 이 없다 — 대기는 서버가 한다.
        res = api.call("wait_for_request", {}, timeout=_WAIT_TIMEOUT_SEC)
        code = res.get("_http")
        if code == 401:
            # 연결이 **명시적으로** 해제됐다(로그아웃, 또는 러너가 오래 멈춰 있어 만료).
            # 사용자 요구(2026-08-28): 이때 러너도 안전하게 종료된다 — 다만 하던 일을 먼저
            # 마친다. 종료 절차는 `shutdown_after_drain` 한 곳이 정본이다.
            _log("토큰이 무효해졌습니다(로그아웃 또는 만료).")
            # 죽은 토큰으로 30초마다 계속 두드리지 않는다.
            heartbeat_stop.set()
            shutdown_after_drain(active, cancels)
            # 다시 띄우는 **정확한 명령**을 준다 — 설정은 이미 저장돼 있으므로 토큰만 새로 받으면
            # 된다. (자발적 종료여도 안내는 남긴다: 로그아웃이 의도치 않았을 수 있다.)
            _log("  다시 연결하려면:")
            _log("  1) 웹 대화 화면에서 'AI 연결하기' → [연결 정보 만들기] → 토큰 복사")
            _log(f"  2) python3 {os.path.basename(__file__)} --resume --token <새 토큰>")
            return 3
        # ⚠ `if code:` 로 쓰면 안 된다 — 연결 실패의 `_http` 는 **0** 이고 0 은 falsy 라
        #   바로 이 블록(백오프)을 건너뛴다. 아래 주석이 설명하는 동작이 정작 코드에는 없었다
        #   (라이브 실측 2026-08-28: 사설 CA 미지정 → 매 호출 실패인데 성공 경로로 흘러 빈
        #   응답을 정상 처리하다 spin 가드로 사망). 실패는 `_failed` 로 명시 판정한다.
        if code or res.get("_failed"):
            # feature-0045: 서버가 배포로 교체되는 동안은 **연결 자체가 실패**한다(`_http == 0`).
            # 종전에는 곧바로 `continue` 였는데, 그러면 서버가 없는 몇 초 동안 초당 수천 번을
            # 재시도해 사용자 머신의 CPU 를 태운다(대기에 sleep 이 없다는 설계가, 실패 경로에서는
            # 정확히 반대로 작용했다). **대기에는 여전히 sleep 이 없다** — 여기서 쉬는 것은 대기가
            # 아니라 **연결 복구**다. 두 가지는 다른 일이고, 다르게 다뤄야 한다.
            backoff = min(_RECONNECT_BACKOFF_MAX, (backoff * 2) or _RECONNECT_BACKOFF_START)
            _log(f"대기 실패 {code}: {res.get('error')} — {backoff:.0f}초 뒤 다시 연결합니다.")
            time.sleep(backoff)
            continue
        backoff = 0.0
        if res.get("draining"):
            # feature-0045: 배포 교대다. **오류가 아니므로 백오프하지 않는다** — 곧바로 다시
            # 부르면 남은 인스턴스가 받는다. 다만 이 응답은 **즉시** 오고, 엣지가 그 인스턴스를
            # 후보에서 빼기까지 짧은 창(health_interval 2s)이 있다. 그 창에서 sleep 0 으로
            # 재호출하면 초당 수십~수백 회가 되어 계정 시간당 호출 상한을 태우고 429 락아웃을
            # 만든다 — 실패 경로에서 없앤 hot loop 를 성공 경로에 다시 만드는 셈이다.
            # 인지 지연이 무시할 만큼 짧은 하한만 둔다(백오프가 아니다 — 자라지 않는다).
            _log("서버 인스턴스 교대 중 — 곧바로 다시 대기합니다.")
            time.sleep(_DRAINING_RETRY_FLOOR_SEC)
            continue

        # 취소는 **새 질문과 같은 응답**으로 온다(별도 채널이 아니다 — P0-J 의 즉시 인지가
        # 취소에도 그대로 적용된다). 진행 중인 워커가 다음 확인 시점에 이것을 보고 하차한다.
        fresh = cancels.add_many(res.get("canceled_task_ids") or [])
        if fresh:
            _log(f"취소 통보: {', '.join(fresh)} — 진행 중이면 중단합니다.")

        # ── 유휴 슬롯 회수 ─────────────────────────────────────────────────
        # 여기가 **tick 이다.** 서버가 대기를 최대 55초 보류하므로 이 루프는 적어도 그 간격으로
        # 돈다 — 시간을 재려고 타이머 스레드를 띄우거나 서버를 두드릴 필요가 없다(폴링 금지와
        # 정합). 조용한 시간대에는 타임아웃 라운드가 곧 회수 라운드가 된다.
        # ⚠ 대기 질문이 있으면 회수하지 않는다. 곧 쓸 자리를 버리면 바로 다시 늘려야 하고,
        #   그 사이 `available=0` 인 창이 생겨 진행이 멈출 수 있다(codex 리뷰 P1 후단).
        if not (res.get("task_ids") or []):
            reaped = pool.reap(time.monotonic())
            if reaped:
                _log(f"유휴 슬롯 {reaped}개 회수 — 동시 처리 {pool.capacity}건")

        # skip 은 영구 블랙리스트가 아니다 — **대기가 실제로 비어서 타임아웃했을 때만** 비운다.
        #
        # 왜 비워야 하나: 다른 러너가 집어 간 작업을 skip 에 넣었는데 그쪽이 죽어 lease 가
        # 만료되면 그 작업은 대기열로 돌아온다. 그때도 계속 건너뛰면 **러너가 돌고 있는데도
        # 사용자는 답을 못 받는다.**
        #
        # 왜 하필 타임아웃 시점인가: "남은 것이 전부 skip" 일 때 비우면, 실패가 반복될 경우
        # 비움 → 재시도 → 실패 → 다시 전부 skip → 비움 … 이 간격 없이 돌아 tight loop 가 된다.
        # 타임아웃은 서버가 55초를 붙들었다는 뜻이라 그 자체가 자연스러운 재시도 간격이다.
        if res.get("timed_out"):
            skip.clear()
            stalled = 0

        pending = [str(t) for t in (res.get("task_ids") or []) if str(t) not in skip]
        if not pending:
            # 서버는 대기 질문이 **있다**고 했는데(즉시 반환) 우리가 전부 건너뛰는 중이다.
            # 이 상태로 `continue` 하면 `wait_for_request` 가 또 즉시 돌아와 **간격 없이 서버를
            # 두드린다** — 우리가 없애려던 바로 그 폴링이, 그것도 최악의 형태로 생긴다.
            #
            # **서버가 open task 를 실제로 보고했을 때만** 집계한다(2026-08-28 라이브 실측):
            # `timed_out` 은 취소 통보로도 False 가 되고 그때 `task_ids` 는 비어 있다 —
            # 처리할 것이 없는데 "처리 못 했다" 고 세면 안 된다.
            #
            # ⚠ 여기서 **러너를 죽이지 않는다** (codex P1-4, 2026-08-28). 종전에는 20라운드 뒤
            #   `exit 4` 였는데, 그러면 **진행 중이던 다른 워커의 답변까지 함께 사라진다**.
            #   한 task 의 점유 실패(권한 재검증·원장 장애 등)로 러너 전체를 끄는 것은 blast
            #   radius 가 과하다. 대신 **경고하고 계속 산다** — 그 사이 다른 워커는 답을 제출하고,
            #   문제의 task 는 lease 만료나 서버측 종결로 자연히 빠진다.
            if res.get("task_ids"):
                stalled += 1
                if stalled == _MAX_STALLED_ROUNDS:
                    _log(f"WARN: 대기 질문 {len(res.get('task_ids') or [])}건을 {stalled}회 연속 "
                         "처리하지 못했습니다(점유 실패 반복). 서버 상태와 토큰 권한을 "
                         "확인하세요 — 러너는 계속 대기합니다.")
                # 쉬는 것은 대기가 아니라 **재시도 간격**이다(hot loop 차단, 상한 있음).
                time.sleep(min(_RECONNECT_BACKOFF_MAX, _DRAINING_RETRY_FLOOR_SEC * stalled))
            continue
        stalled = 0

        # ── 수요 기반 확장 ─────────────────────────────────────────────────
        # 목표는 **진행 중 + 대기**다(상한까지). 대기 수만 보면 실행 중인 작업이 쓰는 자리를
        # 빼고 세어 과소 확장한다(codex 리뷰 P1). 관측된 수요에만 반응한다 — 예측이 빗나가면
        # 그 비용이 사용자 계정 쿼터로 나간다.
        added = pool.grow_for(len(pending))
        if added:
            _log(f"동시 요청 {len(pending)}건(진행 중 {pool.in_use}) — "
                 f"슬롯 {added}개 확장, 동시 처리 {pool.capacity}건")

        # 자리를 **비차단으로** 잡는다 — 없으면 이번 라운드는 디스패치를 건너뛴다.
        # 그 task 는 서버에 그대로 남아 다음 대기에서 다시 제안되고, 그동안에도 우리는
        # `wait_for_request` 를 계속 부르므로 **취소 통보가 끊기지 않는다**(P1-2 의 요지).
        #
        # ⚠ 여기서 `Condition` 으로 블로킹하지 않는 이유가 그것이다. 자리가 날 때까지 막으면
        #   더 정확해 보이지만, 막힌 동안 서버를 읽지 못해 **취소 인지가 자리 반납에 묶인다**.
        #   짧은 간격으로 되돌아오는 편이 취소를 더 빨리 본다.
        sid = pool.try_acquire()
        if sid is None:
            time.sleep(_DRAINING_RETRY_FLOOR_SEC)
            continue

        # 점유는 **여기서** 한다(값싸고 즉시 끝난다). 점유하는 순간 그 task 는 다음
        # `wait_for_request` 결과에서 빠지므로, 워커가 다 찼을 때 같은 것을 다시 받지 않는다.
        task_id = pending[0]
        claimed = api.call("claim_request", {"task_id": task_id})
        if claimed.get("_http") == 409:
            _log(f"{task_id}: 이미 다른 세션이 가져갔다 — 건너뜀")
            skip.add(task_id)
            pool.release(sid)
            continue
        if claimed.get("_http") or claimed.get("_failed"):
            # ⚠ `_failed`(연결 실패, `_http == 0`)를 함께 본다 (codex P2-2, 2026-08-28).
            #   앞선 수정은 대기 루프만 고쳤고 여기는 그대로였다 — claim 도중 TCP/TLS 가 끊기면
            #   **빈 응답을 정상 점유로 읽고** AI 를 돌려, 아무도 기다리지 않는 답을 만든다.
            _log(f"{task_id}: 점유 실패 {claimed.get('_http')} {claimed.get('error')}")
            # 일시 장애(연결 실패·5xx·429)는 **영구 skip 하지 않는다** — 그 task 는 정상이고
            # 잠시 뒤면 집을 수 있다. 영구 skip 은 "이미 남이 가져갔다"(409) 처럼 재시도해도
            # 달라지지 않는 경우에만 쓴다(codex P1-4 의 blast radius 축소와 같은 취지).
            _code = int(claimed.get("_http") or 0)
            if _code and _code < 500 and _code != 429:
                skip.add(task_id)
            pool.release(sid)
            continue

        # 진행 중 원장 등록은 **스레드를 띄우기 전**에 한다. 스레드 안에서 하면 그 사이에
        # 종료 절차가 유휴로 오판하고(카운트 0) 방금 점유한 작업을 두고 나간다.
        active.enter(task_id)

        def _work(tid: str = task_id, payload: dict = claimed, slot: int = sid) -> None:
            try:
                handle_one(api, tid, payload, kind, argv, args.cmd, cancels, runtimes, caps)
            finally:
                cancels.forget(tid)
                active.leave(tid)
                # 반납 시각이 곧 그 슬롯의 `last_used` 다 — 회수 순서가 여기서 정해진다.
                pool.release(slot)
                done_once.set()

        try:
            threading.Thread(target=_work, daemon=True).start()
        except (RuntimeError, OSError) as e:  # 스레드 한도·메모리 부족
            # 여기서 그냥 터지면 **슬롯과 서버 점유가 함께 샌다** — 슬롯은 busy 인 채로,
            # task 는 lease 만료까지 남의 눈에 안 보인 채로 묶인다(codex 리뷰 P2).
            _log(f"{task_id}: 워커 스레드를 시작하지 못했습니다({e}) — 자리를 반납하고 건너뜁니다.")
            pool.release(sid)
            continue
        if args.once:
            # 그 한 건이 **끝날 때까지** 기다린다. 바로 반환하면 daemon 스레드가 죽어
            # 답이 제출되지 않는다(`--once` 가 아무것도 안 하는 것과 같아진다).
            done_once.wait()
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        _log("종료합니다.")
        sys.exit(0)
