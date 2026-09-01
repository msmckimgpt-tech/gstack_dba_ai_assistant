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
    권한은 낮추지 않고   claude 는 `--strict-mcp-config` 로 부른다 — 네 CLI 에 설정된 MCP 서버를
    **좁힌다**          이 호출에서 **쓰지 않는다**는 뜻이다(권한 우회 플래그가 아니다). 조사는
                        `BRIDGE_TOKEN` 환경변수의 이 task 전용 토큰으로만 하고, 네가 다른 곳에
                        설정해 둔 자격증명은 건드리지 않는다. 우리는 `--dangerously-skip-
                        permissions` 나 `--permission-mode bypassPermissions` 를 쓰지 않는다.
                        → `_RUNTIME_SPECS["claude"]["argv"]` 를 직접 보면 된다.
    작업 디렉토리는     자식 CLI 는 `~/.mysql-ai-bridge/work` (빈 디렉토리) 에서 돈다. 러너를
    중립 폴더           코드 저장소 안에서 띄워도 그 저장소의 `CLAUDE.md`·정체성이 이 호출에
                        얹히지 않게 하려는 것이다. → `_child_workdir`.
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
                        설치를 하지 않는다. 남기는 것은 `~/.mysql-ai-bridge/` 안의 넷뿐 —
                        `config.json`(0600, **토큰 없음**) · 빈 폴더 `work` · `bridge.log` ·
                        `bridge.events.jsonl`(0600) → `save_conf`·`_log_dir`.
    나가는 곳           `--base` 주소의 `/api/ai/tools/*` (→ `Api.call`) 와
                        `/api/ai/bridge_heartbeat` (→ `Api.heartbeat`, 30초마다 1회 —
                        본문은 이 머신에서 **쓸 수 있는 런타임·모델 이름 목록**뿐이다.
                        경로·버전·설정 파일 내용은 싣지 않는다 → `detect_runtimes`).
                        그리고 ollama 를 쓸 때만 `BRIDGE_OLLAMA_URL`(기본
                        `127.0.0.1:11434`) — 그 경로를 쓰지 않으면 호출되지 않는다
                        (모델 목록 조회 `/api/tags` 도 같은 호스트다).
                        URL 을 만드는 자리는 `Api._post` 와 ollama 어댑터 **둘뿐**이다.
    관측·종료           하는 일은 전부 로그에 남는다 — 사람이 읽는 줄(stderr·`bridge.log`)과
                        기계가 읽는 사건 원장(한 줄 = 한 사건: 코드·심각도·질문 id·소요·예외
                        형·스택). 질문·답변 **본문은 싣지 않고** 길이만 센다. 실패한 CLI 의
                        stderr 끝부분은 남긴다(그게 없으면 실패 원인에 닿을 길이 없다)
                        → `log_event`. `Ctrl+C`·`kill <pid>` 로 끝난다.

**정직하게 적는 잔여 노출면 둘** — 숨기면 소스를 읽는 순간 드러나고, 그때 잃는 것이 더 크다.

1. **토큰은 자식 프로세스의 환경변수로 들어간다** (`BRIDGE_TOKEN` — 2026-09-01 이전에는
   프롬프트 본문에 평문으로 실렸다). 즉 네가 띄우는 AI CLI 와 그 자식들이 값을 읽을 수 있고,
   같은 사용자 권한이면 `/proc/<pid>/environ` 으로도 보인다. 종전 방식(argv)보다 좁지만
   **0 은 아니다**. 토큰은 **웹 로그인 세션에 결합**돼 있어 그 사람이 로그아웃하면 즉시 죽고,
   이 러너가 멈추면 마지막 하트비트로부터 12시간 뒤 만료된다 — 즉 **러너가 도는 동안은 계속
   유효하다**(2026-08-28 이전에는 발급 후 12시간이 절대 상한이었다). 무기한이 되지 않게 하는
   것은 러너를 끄는 행위 자체다. → `ask_local_ai` 의 `child_env`.
2. **운영자 시스템 지침은 구획되지 않는다.** 요청·대화이력은 서버가 각각 ⟦USER-REQUEST⟧ ·
   ⟦CONVERSATION-HISTORY⟧ 로 구획해 보내지만, 관리 콘솔에서 설정하는 시스템 지침은 구획 없이
   **시스템 채널**(`--append-system-prompt`, 미지원 런타임은 프롬프트 맨 앞)로 들어간다. 즉
   **그 서비스의 운영자는 네 답변 방식에 영향을 줄 수 있다.** 무엇이 설정돼 있는지는
   `claim_request` 응답의 `system_prompt` 로 그대로 보이니, 필요하면 먼저 확인하고 판단해라.
   그 지침 선두에는 서버가 붙인 출처 고지가 있고, 거기에 **상위 안전 규칙이 우선한다**고
   명시돼 있다.

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
import atexit
import json
import os
import re
import secrets
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

#: 같은 계열의 두 번째 한 줄 규약 — 이 턴에서 배운 **도메인 용어 후보**를 실어 온다.
#:
#: 왜 별도 task 가 아니라 답변 동봉인가: 서버가 자기 계정 LLM 을 닫으면서(feature-0043) 답변
#: 직후 큐레이션이 통째로 멈췄다. 되살리는 방법으로 「러너에게 용어 추출 작업을 따로 위임」이
#: 아니라 동봉을 고른 이유는 red-team 과 같다 — **답한 그 AI 가 이미 맥락을 갖고 있고**, 별도
#: 작업으로 만들면 대화를 한 번 더 넘겨야 하며 개인 계정 토큰을 두 번 태운다.
_GLOSSARY_MARK = "#GLOSSARY:"
#: 한 답변이 실을 수 있는 후보 수. 서버도 같은 상한을 다시 건다(러너 신뢰 경계 — 이 값은 예의일 뿐).
_GLOSSARY_MAX = 5

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
        # ⚠ 이 함수는 파일을 **통째로 다시 쓴다**. 여기서 이어 나르지 않는 키는 사라진다 —
        #   `runner_instance` 가 사라지면 다음 기동이 "직전 프로세스" 를 몰라 고아 점유 회수가
        #   조용히 죽는다(그리고 그 죽음은 30분 뒤에야 증상으로 나타나 원인을 짚기 어렵다).
        if _RUNNER_INSTANCE:
            payload["runner_instance"] = _RUNNER_INSTANCE
        else:
            _prev_inst = load_conf().get("runner_instance")
            if _prev_inst:
                payload["runner_instance"] = _prev_inst
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
        # 여기 실패는 **다음 기동**을 망친다(주소·CA·능력 캐시를 잃는다). 그런데 증상은
        # 지금이 아니라 다음에 나타나므로, 예외 형까지 남겨 두지 않으면 그때 원인에
        # 닿지 못한다 — 권한(PermissionError)과 디스크 가득(OSError)은 조치가 다르다.
        _log_exc("conf.save_fail", "설정 저장 실패(무시)", e, path=_CONF_PATH)


def load_conf() -> dict:
    try:
        with open(_CONF_PATH, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


# ── 러너 인스턴스 — 「이 프로세스」의 신원 (TASK-20260901T140000) ──────────────────
#
# ## 무엇을 고치는가 (라이브 실측 2026-09-01)
#
# 러너가 질문을 점유한 뒤 **프로세스가 사라지면**(재설치·재부팅·토큰 만료로 인한 종료·크래시)
# 그 점유는 서버에 그대로 남는다. 서버의 lease 는 도구 호출마다 갱신되므로 마지막 갱신값에서
# 30분을 더 기다려야 풀리고, 그동안 그 질문은 대기 목록에서 보이지 않는다 — **재기동한 자기
# 자신조차 되찾지 못한다.** 사용자 화면은 그 30분을 「처리 중」으로 그린다.
#
# 실측: 12:07 전달 → 12:13 러너 재기동 → 12:43 lease 만료로 재배달 → 재조사 중 토큰 만료로
# 또 종료 → 또 고아 → 13:34 사용자가 포기하고 재전송 → **80초 만에 완료**. 대기 87분.
#
# ## 어떻게 고치는가
#
# 프로세스마다 고유 id 를 만들어 **점유에 새기고**(`claim_request`), 설정 파일에 남긴다.
# 다음 기동이 그 값을 읽어 "직전 프로세스는 죽었다" 를 하트비트에 실으면, 서버는 그 id 로
# 점유된 미제출 작업만 정확히 놓아준다. 30분이 **다음 하트비트까지**로 줄어든다.
#
# 왜 서버가 알아서 못 하는가: 서버가 볼 수 있는 것은 "언제 마지막으로 도구를 불렀나" 뿐이고,
# 그것만으로는 **오래 생각하는 러너**와 **죽은 러너**가 구분되지 않는다. 살아 있는 쪽을 끊으면
# 조사가 통째로 버려지므로 서버는 보수적으로 기다릴 수밖에 없다. 「죽었다」는 사실을 확실히
# 아는 것은 그 자리에 새로 뜬 프로세스뿐이다.

#: 이 프로세스의 id. 서버의 `_sanitize_instance` 가 영숫자만 받으므로 hex 로 만든다.
_RUNNER_INSTANCE = ""

#: 직전 프로세스의 id(설정 파일에서 읽은 값). 없으면 빈 문자열 — 첫 실행이거나 인스턴스 축이
#: 없던 버전에서 올라온 것이다. 그때는 회수할 것이 없으므로 아무 일도 하지 않는다.
_PREV_RUNNER_INSTANCE = ""


def init_runner_instance() -> tuple[str, str]:
    """이 프로세스의 id 를 발급하고 직전 id 를 돌려준다. `(현재, 직전)`.

    **설정을 읽은 직후·서버와 말을 트기 전에** 부른다 — 점유에 새길 값이 준비돼 있어야 하고,
    직전 id 는 이 함수가 덮어쓰기 전에만 읽을 수 있다.

    파일 저장이 실패해도 진행한다: 그때 잃는 것은 *다음* 기동의 회수뿐이고, 이번 실행의 점유
    표시와 종료 시 자기 해제는 메모리 값만으로 동작한다.
    """
    global _RUNNER_INSTANCE, _PREV_RUNNER_INSTANCE
    prev = str(load_conf().get("runner_instance") or "").strip()
    _PREV_RUNNER_INSTANCE = prev if (prev.isalnum() and prev.isascii()) else ""
    _RUNNER_INSTANCE = secrets.token_hex(6)   # 12자 — 서버 상한(16) 안
    try:
        conf = load_conf()
        conf["runner_instance"] = _RUNNER_INSTANCE
        os.makedirs(_CONF_DIR, exist_ok=True)
        with open(_CONF_PATH, "w", encoding="utf-8") as f:
            json.dump(conf, f, ensure_ascii=False)
        os.chmod(_CONF_PATH, 0o600)
    except Exception as e:  # noqa: BLE001
        _log_exc("conf.instance_save_fail",
                 "러너 인스턴스 저장 실패(무시) — 다음 기동의 고아 점유 회수가 동작하지 않는다",
                 e, path=_CONF_PATH)
    return _RUNNER_INSTANCE, _PREV_RUNNER_INSTANCE

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


# ── 로그 — 사람이 읽는 줄 + 기계가 감사하는 원장 (TASK-20260901T163000) ─────────
#
# ## 왜 구조가 필요한가 (실측 근거)
#
# 종전 로그는 `[bridge <시각>] <한국어 문장>` 한 형태뿐이었다. 사람이 읽기엔 좋았지만
# **사고를 조사하는 데 필요한 축이 문장 안에 녹아 있어** 꺼낼 수 없었다:
#
#   - 「이 줄이 무슨 사건인가」를 한국어 문장 매칭으로만 판별했다. 문장을 한 글자만 고쳐도
#     그동안 쓰던 조사 방법이 조용히 깨진다.
#   - 심각도가 없다. 「참고」와 「제출 실패」가 같은 모양이라 `grep` 로 오류만 볼 수 없었다.
#   - `task_id` 는 있는 줄과 없는 줄이 섞여 있고, **어느 프로세스가 쓴 줄인지**(러너 인스턴스)
#     는 어디에도 없다. 재기동이 잦은 러너에서 이건 치명적이다 — 실제 87분 고아 사고(§
#     `init_runner_instance` 주석)의 시간축을 파일 mtime·DB 하트비트로 복원해야 했다.
#   - 소요 시간이 없다. 「전달」과 「제출 완료」 사이가 몇 초였는지 두 줄의 시각을 빼서 구해야
#     하는데, 동시 처리(`--workers`)면 두 줄이 인터리브되어 그 뺄셈조차 틀린다.
#   - 예외는 `except Exception as e: _log(f"…: {e}")` 형태라 **예외 형(type)과 스택이 통째로
#     버려진다**. `e` 문자열만으로는 같은 문장을 내는 다른 원인을 가를 수 없다.
#   - Windows 는 로그 자체가 없었다. 설치 스크립트가 `Start-Process -WindowStyle Hidden` 으로
#     띄우면서 stderr 를 어디에도 잇지 않아, 그 머신의 사고는 **증거가 0** 이었다.
#
# ## 무엇을 하는가
#
# 한 번의 `_log`/`log_event` 호출이 **두 곳**에 간다:
#
#   1. **사람 sink** — stderr(그리고 필요하면 `bridge.log`). 종전 형식을 잃지 않되 심각도와
#      사건 코드·핵심 필드를 앞에 세운다:
#        `[bridge 2026-09-01 16:30:11+0900] ERROR task.submit.fail task=ab12 http=500 | 제출 실패 …`
#   2. **감사 sink** — `bridge.events.jsonl` 한 줄 JSON. 사람이 읽는 줄이 버리는 것(예외 형,
#      스택, 자식 stderr 전문, 밀리초 단위 소요)을 여기 남긴다. 기계가 읽으므로 문장을 고쳐도
#      조사 방법이 깨지지 않는다 — 안정 계약은 **문장이 아니라 `ev` 코드와 필드 이름**이다.
#
# ## 하지 않는 것
#
#   - `logging` 모듈을 쓰지 않는다. 이 파일은 남의 머신에서 남의 파이썬으로 도는 단일 파일이고,
#     전역 로거 설정은 그 환경의 다른 설정과 싸운다. 필요한 것은 두 sink 와 잠금뿐이다.
#   - 서버로 로그를 보내지 않는다. 이 파일의 보안 계약(`나가는 곳`)을 넓히지 않는다 —
#     서버와의 대조는 `task_id`·`run`(러너 인스턴스) 키로 사후에 한다.

#: 심각도. 사람 sink 와 감사 sink 가 각각 다른 하한을 가질 수 있다 — 화면은 조용하되 원장은
#: 상세해야 하기 때문이다(그 반대는 쓸모가 없다).
_LOG_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40, "FATAL": 50}


def _level_from_env(name: str, default: str) -> int:
    raw = (os.environ.get(name) or "").strip().upper()
    return _LOG_LEVELS.get(raw, _LOG_LEVELS[default])


#: 사람이 보는 줄의 하한. 기본 INFO — DEBUG 는 조사할 때만 켠다.
_LOG_LEVEL_MIN = _level_from_env("BRIDGE_LOG_LEVEL", "INFO")
#: 감사 원장의 하한. 기본 DEBUG — **원장은 빠짐없는 것이 목적**이라 화면보다 낮게 둔다.
_AUDIT_LEVEL_MIN = _level_from_env("BRIDGE_AUDIT_LEVEL", "DEBUG")

def _int_from_env(name: str, default: int, minimum: int) -> int:
    """환경변수 정수. **깨진 값으로 러너가 죽지 않게** 한다.

    로그 설정 오타(`BRIDGE_LOG_KEEP=three`)로 상주 러너가 기동조차 못 하면, 관측을 좋게
    하려던 축이 가용성을 깎는다. 못 읽으면 기본값을 쓰고 그 사실만 남긴다.
    """
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


#: 원장 파일이 이 크기를 넘으면 회전한다. 상주 프로세스가 몇 달을 도는 것이 정상이므로
#: 상한이 없으면 디스크를 조용히 먹는다(그리고 그 조용함이 정확히 이 파일이 고치려는 병이다).
_LOG_MAX_BYTES = _int_from_env("BRIDGE_LOG_MAX_BYTES", 8 * 1024 * 1024, 64 * 1024)
#: 보관 세대 수. 사고 조사는 보통 직전 며칠이면 되고, 무한 보관은 위 상한을 무의미하게 만든다.
_LOG_KEEP = _int_from_env("BRIDGE_LOG_KEEP", 3, 1)

#: 두 sink 와 순번을 함께 지키는 잠금. 워커 스레드·하트비트 스레드가 동시에 쓴다.
_LOG_LOCK = threading.RLock()
#: 이 프로세스 안에서의 사건 순번. 같은 초에 여러 줄이 나도 **순서**를 잃지 않게 한다
#: (동시 처리에서 시각만으로는 인터리브 순서를 복원할 수 없다).
_LOG_SEQ = 0

#: 사건 코드별 발생 횟수. 종료 요약(`run.stop`)이 이 표를 그대로 싣는다 — 「이번 세션에서
#: 질문 몇 건을 처리했고 몇 번 실패했나」를 로그 전체를 훑지 않고 마지막 한 줄로 알 수 있다.
_STATS: dict[str, int] = {}
#: 프로세스 시작 시각(단조). 종료 요약의 `uptime_sec`.
_RUN_T0 = time.monotonic()

#: 로그에서 마스킹할 비밀 문자열(토큰 등). 값을 **아는 채로** 지우는 것이 패턴 추측보다 확실하다.
_LOG_SECRETS: set[str] = set()
#: 값을 모를 때를 위한 패턴 방어. 위 등록이 누락돼도 형태로 잡는다.
_SECRET_PATTERNS = (
    re.compile(r"\bmat_[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)\b(BRIDGE_TOKEN|token)\s*[=:]\s*[\"']?[A-Za-z0-9._\-]{8,}"),
)


def register_secret(value: str | None) -> None:
    """이 값이 로그에 나타나면 지운다. 토큰을 손에 쥔 **직후** 부른다.

    패턴만으로 막지 않는 이유: 토큰 형식은 바뀔 수 있고, 바뀐 그날의 로그가 새는 것을
    나중에 알아채는 방법이 없다. 값을 알고 있을 때 등록해 두는 편이 확실하다.
    """
    v = (value or "").strip()
    if len(v) >= 8:
        _LOG_SECRETS.add(v)


def _scrub(text: str) -> str:
    """비밀을 지운 문자열. 두 sink 모두 이 함수를 거친 것만 쓴다.

    ⚠ 집합을 **스냅샷으로** 돈다: 다른 스레드가 `register_secret` 하는 순간 집합을 순회 중이면
    `RuntimeError: Set changed size during iteration` 이 나고, 그 예외가 하필 **로그를 쓰는
    도중** 터진다(= 그 사건이 통째로 사라진다).
    """
    out = str(text)
    for s in tuple(_LOG_SECRETS):
        if s and s in out:
            out = out.replace(s, "***")
    for pat in _SECRET_PATTERNS:
        out = pat.sub(lambda m: m.group(0)[:6] + "***", out)
    return out


def _log_dir() -> str:
    """로그가 사는 곳. 기본은 설정과 같은 폴더 — 사고 조사에서 둘을 함께 본다.

    `BRIDGE_LOG_DIR` 로 옮길 수 있게 두되 **설정 경로(`_CONF_DIR`)는 건드리지 않는다**:
    그쪽을 움직이면 이미 저장된 설정이 보이지 않게 되어, 로그를 좋게 하려다 연결을 깬다.
    """
    return (os.environ.get("BRIDGE_LOG_DIR") or "").strip() or _CONF_DIR


def _audit_path() -> str:
    return os.path.join(_log_dir(), "bridge.events.jsonl")


#: `_human_log_path` 의 1회 판정 결과. `Event` 를 쓰는 이유는 「아직 안 정했다」와
#: 「정했는데 None(=쓰지 않는다)」을 구분해야 하기 때문이다.
_HUMAN_LOG_RESOLVED = threading.Event()
_HUMAN_LOG_PATH: str | None = None


def _human_log_path() -> str | None:
    """사람 줄을 **파일로도** 적어야 하는가. 적어야 하면 그 경로, 아니면 `None`.

    ## 왜 자동 판정인가

    POSIX 설치 스크립트는 러너의 stderr 를 `bridge.log` 로 잇는다. 그 상태에서 이 함수가
    같은 파일을 또 열면 **모든 줄이 두 번** 남는다. 반대로 Windows 설치본은 stderr 를 아무
    데도 잇지 않아 **한 줄도 남지 않았다** — 그 머신의 사고는 증거가 없었다.

    두 경우를 사용자가 설정으로 구분하게 만들면 대부분 틀린 쪽을 고른다(그리고 틀린 것을
    알아채는 시점은 사고 조사 중이다). 그래서 **stderr 가 이미 그 파일인지**를 직접 본다 —
    같은 파일이면 우리가 또 쓰지 않고, 아니면 우리가 쓴다.

    `BRIDGE_LOG_FILE` 로 명시할 수 있다(`-` 는 파일 기록 끔).

    판정은 **한 번만** 한다: 프로세스가 도는 동안 stderr 가 갈아끼워지는 일은 없고, 줄마다
    `stat` 을 두 번 부르면 로그가 곧 비용이 된다(DEBUG 를 켜면 서버 왕복마다 한 줄이다).
    """
    global _HUMAN_LOG_PATH
    if _HUMAN_LOG_RESOLVED.is_set():
        return _HUMAN_LOG_PATH
    override = (os.environ.get("BRIDGE_LOG_FILE") or "").strip()
    path: str | None = override or os.path.join(_log_dir(), "bridge.log")
    if override == "-":
        path = None
    else:
        try:
            st_err = os.fstat(sys.stderr.fileno())
            st_log = os.stat(path)
            # 같은 파일이면 stderr 쪽이 이미 적고 있다. `st_ino` 는 Windows(NTFS)에서도 유효하다.
            if (st_err.st_ino and st_err.st_ino == st_log.st_ino
                    and st_err.st_dev == st_log.st_dev):
                path = None
        except Exception:  # noqa: BLE001  (콘솔·파이프·파일 부재 — 그때는 우리가 적는다)
            pass
    _HUMAN_LOG_PATH = path
    _HUMAN_LOG_RESOLVED.set()
    return path


def _rotate_if_needed(path: str) -> None:
    """상한을 넘으면 `.1` 로 밀어내고 세대를 정리한다. 실패해도 로그는 계속 쓴다."""
    try:
        if os.path.getsize(path) < _LOG_MAX_BYTES:
            return
    except OSError:
        return
    try:
        oldest = f"{path}.{_LOG_KEEP}"
        if os.path.exists(oldest):
            os.remove(oldest)
        for n in range(_LOG_KEEP - 1, 0, -1):
            src, dst = f"{path}.{n}", f"{path}.{n + 1}"
            if os.path.exists(src):
                os.replace(src, dst)
        os.replace(path, f"{path}.1")
    except Exception:  # noqa: BLE001  (회전 실패로 기록을 멈추지는 않는다)
        pass


def _append_line(path: str, line: str) -> None:
    """한 줄 append. 디렉토리·권한을 함께 챙긴다(원장에는 대화 조각이 실릴 수 있다)."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        _rotate_if_needed(path)
        new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
        if new:
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
    except Exception:  # noqa: BLE001  (기록 실패가 러너를 멈추게 하지 않는다)
        pass


#: 사람 줄에서 **앞에 세울** 필드와 순서. 나머지는 이 뒤에 이름순으로 붙는다.
#: 조사할 때 가장 먼저 찾는 순서다 — 어느 질문(task)의, 어느 AI(runtime)로, 얼마나 걸렸고,
#: 서버가 뭐라 했나(http).
_FIELD_ORDER = ("task", "conv", "runtime", "model", "effort", "dur_ms", "http", "exit", "attempt")
#: 사람 줄에 붙이는 필드 값의 길이 상한. 원장에는 전문이 남으므로 여기서는 읽기 쉬움이 우선이다.
_FIELD_VALUE_MAX = 80


def _render_fields(fields: dict) -> str:
    def _key(item):
        k = item[0]
        return (_FIELD_ORDER.index(k) if k in _FIELD_ORDER else len(_FIELD_ORDER), k)

    parts = []
    for k, v in sorted(fields.items(), key=_key):
        if v is None or isinstance(v, (dict, list, tuple)):
            continue          # 구조값은 원장에만 — 사람 줄에서는 소음이다
        s = _scrub(str(v)).replace("\n", " ")
        if len(s) > _FIELD_VALUE_MAX:
            s = s[:_FIELD_VALUE_MAX] + "…"
        parts.append(f"{k}={s}")
    return " ".join(parts)


def log_event(event: str, msg: str = "", *, level: str = "INFO",
              exc: BaseException | None = None, **fields) -> None:
    """사건 하나를 두 sink 에 남긴다.

    `event` 는 **안정 계약**이다 — 문장(`msg`)은 자유롭게 고쳐도 되지만 이 코드는 조사
    스크립트가 의존하므로 바꿀 때는 그 사실을 알고 바꾼다. 코드 목록은 `_EV_*` 상수.

    `exc` 를 주면 예외 형·표현·스택이 **원장에만** 실린다. 사람 줄에는 요약 한 조각만 —
    스택이 화면을 덮으면 정작 읽어야 할 다음 줄이 밀려난다.
    """
    global _LOG_SEQ
    lvl = level.upper() if level.upper() in _LOG_LEVELS else "INFO"
    sev = _LOG_LEVELS[lvl]
    if exc is not None:
        fields = {**fields,
                  "err_type": type(exc).__name__,
                  "err": _scrub(str(exc))[:400]}
    now = time.time()
    with _LOG_LOCK:
        _LOG_SEQ += 1
        seq = _LOG_SEQ
        # 집계를 **여기 한 자리**에서 한다. 호출부마다 세면 새 경로가 생길 때 빠지고, 빠진
        # 그 경로가 하필 조사하려는 것이다. 종료 시 이 표가 「이번 세션이 무엇을 했나」가 된다.
        # ⚠ 잠금 **안**이어야 한다 — `d[k] = d.get(k,0)+1` 은 원자적이지 않아, 워커 스레드가
        #   여럿이면 집계가 조용히 적게 세어진다(그리고 그 오차는 아무도 눈치채지 못한다).
        _STATS[event] = _STATS.get(event, 0) + 1
        if sev >= _LOG_LEVELS["ERROR"]:
            _STATS["_errors"] = _STATS.get("_errors", 0) + 1
        # ── 사람 sink ────────────────────────────────────────────────────────
        if sev >= _LOG_LEVEL_MIN:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S") + _tz_suffix()
            rendered = _render_fields(fields)
            head = f"[bridge {stamp}] {lvl:<5} {event}"
            line = head + (f" {rendered}" if rendered else "") + \
                (f" | {_scrub(msg)}" if msg else "") + "\n"
            try:
                sys.stderr.write(line)
                sys.stderr.flush()
            except Exception:  # noqa: BLE001  (닫힌 stderr — 파일 sink 는 계속 간다)
                pass
            human = _human_log_path()
            if human:
                _append_line(human, line)
        # ── 감사 sink ────────────────────────────────────────────────────────
        if sev >= _AUDIT_LEVEL_MIN:
            rec = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now))
                      + f".{int((now % 1) * 1000):03d}" + _tz_suffix(),
                "lvl": lvl,
                "ev": event,
                "seq": seq,
                "run": _RUNNER_INSTANCE or None,
                "pid": os.getpid(),
            }
            for k, v in fields.items():
                if v is None:
                    continue
                rec[k] = _scrub(v) if isinstance(v, str) else v
            if msg:
                rec["msg"] = _scrub(msg)
            if exc is not None:
                rec["tb"] = _scrub(_short_traceback(exc))
            try:
                _append_line(_audit_path(),
                             json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            except Exception:  # noqa: BLE001
                pass


def _tz_suffix() -> str:
    """`+0900` 같은 오프셋. 지역시각만 적으면 다른 표준시의 서버 로그와 대조할 수 없다.

    사람이 자기 시계와 대조하기 위해 지역시각을 쓰되(사용자 요청 2026-08-31), 기계가 UTC 로
    환산할 수 있게 오프셋을 함께 적는다 — 「웹은 15:35 인데 로그는 06:35」 는 오프셋이 있으면
    같은 사건임이 계산으로 나온다.
    """
    off = -(time.altzone if time.daylight and time.localtime().tm_isdst else time.timezone)
    sign = "+" if off >= 0 else "-"
    off = abs(int(off))
    return f"{sign}{off // 3600:02d}{(off % 3600) // 60:02d}"


def _short_traceback(exc: BaseException, frames: int = 12) -> str:
    """스택 **마지막 N 프레임**. 전문을 남기면 원장 한 줄이 화면 하나만큼 커진다.

    마지막을 남기는 이유: 터진 자리가 거기다. 위쪽 프레임(진입점·루프)은 매번 같아서
    구분에 기여하지 않는다.
    """
    try:
        import traceback

        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        # [0] 은 "Traceback (most recent call last):" 머리, 마지막은 예외 문장이다.
        body = tb[1:-1][-frames:] if len(tb) > 2 else tb[1:]
        return "".join([tb[0]] + body + tb[-1:])[-4000:]
    except Exception:  # noqa: BLE001
        return ""


def _log(msg: str, *, event: str = "log", level: str = "INFO", **fields) -> None:
    """종전 그대로 쓸 수 있는 한 줄 기록 (`_log("…")`).

    호출부 80여 곳을 한꺼번에 고치지 않기 위해 **위치인자 하나**의 계약을 유지한다. 새로
    쓰는 자리는 `event=`·필드를 함께 주는 편이 좋고, 그러면 그 줄만 조사 가능해진다.
    """
    log_event(event, msg, level=level, **fields)


def _log_exc(event: str, msg: str, exc: BaseException, **fields) -> None:
    """예외를 **버리지 않고** 남긴다 — 형·표현은 두 sink, 스택은 원장."""
    log_event(event, msg, level="ERROR", exc=exc, **fields)


# ── 사건 코드 (안정 계약) ─────────────────────────────────────────────────────
#
# 조사 스크립트·감사가 의존하는 이름이다. 문장은 자유롭게 고쳐도 되지만 이 값은 계약이므로
# 바꿀 때는 소비처를 함께 본다. 접두사가 곧 계층이다:
#
#   run.*    프로세스 수명        conn.*  서버 연결·인증
#   caps.*   능력 신고            hb.*    하트비트
#   task.*   질문 한 건의 일생     ai.*    로컬 AI CLI 호출
#   api.*    서버 호출 실패        log.*   로그층 자신
_EV_RUN_START = "run.start"
_EV_RUN_READY = "run.ready"
_EV_RUN_STOP = "run.stop"
_EV_RUN_FATAL = "run.fatal"
_EV_CONN_OK = "conn.ok"
_EV_CONN_FAIL = "conn.fail"
_EV_CONN_UNAUTH = "conn.unauthorized"
_EV_CONN_RETRY = "conn.retry"
_EV_HB_FAIL = "hb.fail"
_EV_HB_UNAUTH = "hb.unauthorized"
_EV_HB_STALE = "hb.stale_build"
#: 같은 계정에 최신 러너가 붙어서 이 러너가 물러나는 사건 (TASK-20260901T173000).
_EV_HB_SUPERSEDED = "hb.superseded"
_EV_TASK_CLAIM_SKIP = "task.claim.skip"
_EV_TASK_CLAIM_FAIL = "task.claim.fail"
_EV_TASK_DISPATCH = "task.dispatch"
_EV_TASK_UNMET = "task.unmet"
_EV_TASK_CANCEL = "task.cancel"
_EV_TASK_REVIEW = "task.review"
_EV_TASK_SUBMIT_OK = "task.submit.ok"
_EV_TASK_SUBMIT_RETRY = "task.submit.retry"
_EV_TASK_SUBMIT_FAIL = "task.submit.fail"
_EV_TASK_SUBMIT_REJECT = "task.submit.reject"
_EV_AI_FAIL = "ai.fail"
_EV_AI_TIMEOUT = "ai.timeout"
_EV_AI_SPAWN_FAIL = "ai.spawn_fail"
_EV_API_FAIL = "api.fail"


#: 평문이 허용되는 유일한 대상. 이름이 아니라 **호스트**로 판정한다.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


#: 이 러너의 버전. 서버가 콘솔 작업 배급 자격의 **2차 조건**으로 쓴다(1차는 기능 신고).
#:
#: 왜 둘 다인가: 기능 이름만 보면 신고 **형식**이 바뀐 뒤에도 구 러너가 자격을 유지한다.
#: 버전은 그 형식 변경을 표현할 수 있는 유일한 축이다. 서버의 하한은
#: `shared/bridge_tasks.RUNNER_MIN_AGENT_VERSION` — 여기 값이 그보다 낮으면 콘솔 작업이
#: 배급되지 않고, 하트비트 응답의 `runner_update` 가 그 사실을 말한다.
AGENT_VERSION = "2026.09.01"


def _self_build() -> str:
    """이 **파일 자체**의 지문 12자. 못 읽으면 빈 문자열.

    `AGENT_VERSION` 만으로는 부족하다 (사용자 제보 2026-08-31). 날짜 단위라 **같은 날 여러 번
    배포된 러너가 전부 같은 버전**이 된다 — 실제로 그날 러너가 세 번 바뀌었고, 사용자는
    「재설치했는데 목록이 그대로」를 봤다. 서버는 자기가 배포 중인 `static/agent/bridge_agent.py`
    의 지문을 알고 있으므로, 이 값을 비교하면 "정확히 그 파일인가" 를 판정할 수 있다.

    버전(호환성 축)과 지문(동일성 축)은 다른 질문에 답한다 — 그래서 둘 다 싣는다.
    """
    try:
        import hashlib

        with open(__file__, "rb") as _f:
            return hashlib.sha256(_f.read()).hexdigest()[:12]
    except Exception:  # noqa: BLE001  (읽기 실패·경로 부재 — 모르면 빈 값)
        return ""


def _self_os() -> str:
    """이 러너가 도는 **명령 계열**: `"windows"` 또는 `"posix"` (2026-09-01).

    왜 서버가 이걸 알아야 하는가: 연결 화면의 1단계는 붙여넣을 명령을 OS 별로 나눠 보여 주는데,
    종전에는 그 기본 선택을 **브라우저**(`navigator.platform`)로 정했다. 그런데 브라우저가 도는
    OS 와 러너가 도는 OS 는 **같지 않다** — WSL 안에서 러너를 띄우는 사용자는 Windows 브라우저로
    화면을 보므로, 항상 PowerShell 명령이 먼저 뽑혀 매번 탭을 바꿔야 했다(제보 2026-09-01).

    러너가 자기 계열을 신고하면 그 값이 「마지막으로 연결된 OS」가 되고, 화면은 추측 대신
    **실제로 연결됐던 쪽**을 먼저 보여 준다. PowerShell 명령으로 다시 등록하면 그 신고가 곧
    `windows` 라 화면도 따라 바뀐다.

    `sys.platform` 이 아니라 `os.name` 을 보는 이유: 우리가 가르려는 것은 배포판이 아니라
    **어느 명령문이 통하는가** 이고, 그 축에서 WSL 은 리눅스다(`os.name == "posix"`).
    """
    try:
        return "windows" if os.name == "nt" else "posix"
    except Exception:  # noqa: BLE001  (판정 불가 — 모르면 빈 값. 화면은 종전 추측으로 돌아간다)
        return ""


#: 이 러너가 다룰 줄 아는 작업 종류.
#:
#: `console_jobs` — 관리 콘솔 작업(대화가 아닌 프롬프트 한 덩어리). 신고하지 않으면 서버가
#:   배급하지 않는다. 신고 없이 받으면 대화용 프레이밍으로 감싸 산출물이 조용히 망가진다.
#: `batch_jobs` — 배경 배치까지 받겠다는 **별도 동의**. 기본 포함이 아니다: 그 작업은 이
#:   사람이 요청한 적 없고 자기 계정 토큰을 태운다. 이제 동의는 **웹에서 켠다**(하트비트
#:   응답의 `batch_consent`) — `--batch`/`--no-batch` 는 이 머신의 명시 override 로 남는다.
#: `self_review` — 답변 초안을 자기가 5축으로 검증할 줄 안다. **자격이 아니라 관측 축**이라
#:   기본 포함이다: 신고하지 않으면 콘솔이 「검증할 줄 모르는 러너」와 「검증했는데 통과」를
#:   구분하지 못하고, 구분하지 못하면 운영자는 전자를 후자로 읽는다. 실제 수행 여부는
#:   서버 설정(`REDTEAM_ENABLED`)이 정하며 `--no-self-review` 로 이 머신에서 끌 수 있다.
AGENT_FEATURES: tuple[str, ...] = ("console_jobs", "self_review")

#: 배경 배치 동의의 기능 이름. 서버 `shared/bridge_consent.BATCH_FEATURE` 와 같은 값이어야 한다.
BATCH_FEATURE = "batch_jobs"


def normalize_consent(value: object) -> bool:
    """서버가 준 동의 값을 bool 로 굳힌다. **모르면 False**(남의 토큰을 태우는 축).

    ⚠ 이 함수는 서버 `shared/bridge_consent.normalize_consent` 의 **거울**이다. 러너는
    사용자 머신에 홀로 놓이는 단일 파일이라 그 모듈을 import 할 수 없다. 이음매 테스트가
    두 구현을 같은 입력표로 돌려 대조한다 — 손으로 맞춰 둔 두 구현은 한쪽만 고쳐지는 날
    조용히 갈리고, 그 갈림은 양쪽을 각각 검사하는 테스트로는 보이지 않는다.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if not text:
        return False
    return text in {"1", "true", "yes", "on", "t", "y"}


def apply_consent(base_features, *, server_consent, local_override=None) -> tuple:
    """신고할 `features` 를 만든다 — `shared/bridge_consent.apply_consent` 의 **거울**.

    `local_override`: `True`=`--batch`(이 머신에서 명시 허용) · `False`=`--no-batch`(이 머신만
    예외) · `None`=지시 없음(서버 값을 따른다). override 가 서버 값을 **양방향으로** 이긴다.
    """
    feats = [str(f) for f in (base_features or []) if str(f) and str(f) != BATCH_FEATURE]
    want = normalize_consent(server_consent) if local_override is None else bool(local_override)
    if want:
        feats.append(BATCH_FEATURE)
    return tuple(feats)


def _batch_override_from_args(args) -> "bool | None":
    """`--batch` / `--no-batch` 를 3-값 override 로 읽는다. 지시가 없으면 `None`.

    둘 다 준 경우는 **끄는 쪽**을 택한다. 모순된 지시에서 남의 계정 사용량을 태우는 방향으로
    기우는 것은 근거가 없다 — argparse 의 상호배타(`add_mutually_exclusive_group`)를 쓰지 않는
    이유는, 옛 온보딩 명령이 `--batch` 를 달고 있는 사람이 새 스크립트를 덧붙였을 때 러너가
    **기동조차 못 하는** 것보다 조용히 안전한 쪽을 고르는 편이 낫기 때문이다.
    """
    if getattr(args, "no_batch", False):
        return False
    if getattr(args, "batch", False):
        return True
    return None


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
    #: 이 인스턴스가 신고할 기능. `--batch` 로 배치 동의를 더한다 —
    #: 전역 상수를 바꾸지 않는 이유: 같은 프로세스에서 두 Api 를 만들 수 있고, 동의는
    #: **그 실행의 선택**이지 모듈의 성질이 아니다.
    features: tuple[str, ...] = AGENT_FEATURES

    def __init__(self, base: str, token: str, ca: str | None):
        self.base = base.rstrip("/")
        self.token = token
        self.ctx = ssl.create_default_context(cafile=ca) if ca else None
        # 로그에 이 값이 실릴 자리를 미리 막는다 — 서버 오류 본문·자식 CLI stderr·`--cmd`
        # 문자열 어디에도 토큰이 섞여 나올 수 있고, 그 로그는 사용자가 우리에게 붙여 보낸다.
        register_secret(token)

    def call(self, tool: str, payload: dict | None = None, timeout: float = 60.0) -> dict:
        return self._post(f"/api/ai/tools/{tool}", payload, timeout)

    def heartbeat(self, runtimes: list | None = None,
                  timeout: float = _HEARTBEAT_TIMEOUT_SEC,
                  released_instances: "list[str] | None" = None) -> dict:
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
        body: dict = {} if runtimes is None else {"runtimes": runtimes}
        # 기능·버전 신고 (TASK-20260831T100000). **항상** 싣는다 — 능력(`runtimes`)과 달리
        # 이것은 "무엇을 다룰 줄 아는가" 라 `--cmd` 사용자에게도 참이다. 서버는 이 값으로
        # 콘솔 작업 배급 자격을 정하고, 낡은 버전이면 응답으로 갱신 경로를 알려 준다.
        body["features"] = list(self.features)
        body["agent_version"] = AGENT_VERSION
        # 죽은 인스턴스의 **사망 신고** (TASK-20260901T140000). 기동 첫 신호에는 직전
        # 프로세스를, 종료 시에는 자기 자신을 싣는다. 서버는 그 id 로 점유된 미제출 작업만
        # 놓아준다 — 다른 러너(다른 머신)의 작업은 id 를 알 수 없어 애초에 걸리지 않는다.
        if released_instances:
            body["released_instances"] = [str(x) for x in released_instances if x]
        # 지문은 **동일성** 축이다 (2026-08-31). 날짜 버전이 같아도 파일이 다르면 서버가
        # 「배포본과 다른 러너가 돌고 있다」를 알 수 있고, 그 사실을 화면이 말해 줄 수 있다.
        body["agent_build"] = _self_build()
        # 명령 계열 신고 (2026-09-01). 연결 화면의 1단계가 **마지막으로 연결된 쪽**을 먼저
        # 보여 주게 하는 유일한 사실 — 브라우저가 도는 OS 는 러너가 도는 OS 가 아니다(WSL).
        body["agent_os"] = _self_os()
        return self._post("/api/ai/bridge_heartbeat", body, timeout)

    def _post(self, path: str, payload: dict | None = None, timeout: float = 60.0) -> dict:
        body = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base}{path}", data=body, method="POST",
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json", "User-Agent": _UA})
        # 서버 왕복은 **여기 한 자리**에서 계측한다 (TASK-20260901T163000). 호출측마다 재는
        # 것은 빠지는 곳이 생기고, 빠진 곳이 하필 느려지는 곳이다. `dur_ms` 가 원장에 있으면
        # 「러너가 느린가 · 서버가 느린가 · AI 가 느린가」를 로그만으로 가를 수 있다.
        _t0 = time.monotonic()

        def _ms() -> int:
            return int((time.monotonic() - _t0) * 1000)

        try:
            with urllib.request.urlopen(req, timeout=timeout, context=self.ctx) as resp:
                out = json.loads(resp.read().decode("utf-8", "replace") or "{}")
                log_event("api.ok", level="DEBUG", path=path, dur_ms=_ms())
                return out
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            # 상태코드를 뭉개지 않는다 — 401(재발급 필요)·409(남이 점유)·429(상한)는
            # 호출측이 서로 다르게 대응해야 하는 신호다.
            #
            # ⚠ 여기서 기록만 하고 **판정하지 않는다**. 409 는 정상 흐름(취소·경합)이고 401 은
            #   사고다 — 그 구분은 호출측이 문맥과 함께 한다. 심각도는 그래서 WARN 이 상한이다.
            log_event(_EV_API_FAIL, "서버가 오류로 답했다", level="WARN",
                      path=path, http=e.code, dur_ms=_ms(), detail=detail)
            return {"_http": e.code, "error": detail}
        except Exception as e:  # noqa: BLE001
            # ⚠ `_http: 0` = **연결 자체가 안 됐다**(TLS·DNS·거부). 0 은 falsy 라
            #   `if not r.get("_http")` / `if code:` 같은 진위 검사에서 **성공으로 읽힌다** —
            #   실제로 `--check` 가 사설 CA 미지정 상태에서 "연결 정상" 을 출력했다(라이브 실측
            #   2026-08-28). 호출측이 실수하지 않도록 명시 플래그를 함께 싣는다.
            #
            # 연결 실패는 **예외 형이 곧 원인**이다 — `SSLCertVerificationError`(사설 CA 미지정)
            # 와 `URLError`(DNS·거부)와 `timeout`(서버 지연)은 사용자가 할 일이 전혀 다른데,
            # `str(e)` 만 남기면 그 셋이 비슷하게 보인다. 형과 스택을 원장에 남긴다.
            log_event(_EV_API_FAIL, "서버에 닿지 못했다", level="WARN", exc=e,
                      path=path, http=0, dur_ms=_ms())
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
#: 그러나 배제는 mysql-ai 만이 아니라 그 사용자가 붙여 둔 **모든** MCP 서버에 걸린다
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


def _exec_exts() -> list[str]:
    """이 OS 에서 실행 파일 이름에 붙을 수 있는 확장자. POSIX 는 `[""]`.

    ⚠ 구분자는 `;` 다 — `os.pathsep` 이 아니다. 두 값이 같은 것은 Windows 뿐이고, 여기서
    쪼개는 것은 PATH 가 아니라 `PATHEXT` 다(의미가 다른 것을 같은 상수로 쓰면, 그 둘이
    갈리는 환경에서 조용히 틀린다).

    `PATHEXT` 는 **거르는 데 쓰지 않는다** — 순서만 참고하고, 우리 목록은 항상 전부 본다.
    거르면 `PATHEXT` 를 손댄 머신에서 설치 스크립트(고정 목록)와 러너의 답이 갈린다
    (codex 적대 리뷰 P2). 두 곳이 다른 답을 내면 사용자는 어느 쪽도 믿을 수 없다.

    소문자로 돌려준다. Windows 의 파일 이름은 대소문자를 가리지 않으므로 실물이
    `CLAUDE.EXE` 여도 `claude.exe` 로 열린다.
    """
    if os.name != "nt":
        return [""]
    raw = [e.strip().lower() for e in os.environ.get("PATHEXT", "").split(";") if e.strip()]
    ordered = [e for e in raw if e in _WIN_EXEC_EXTS]
    return ordered + [e for e in _WIN_EXEC_EXTS if e not in ordered]


def _is_exec(p: str) -> bool:
    if not os.path.isfile(p):
        return False
    if os.name == "nt":
        # ⚠ Windows 의 `os.access(X_OK)` 는 **존재 여부만** 본다(모든 파일이 True 다).
        #   실행 가능 여부는 확장자가 가른다.
        return os.path.splitext(p)[1].lower() in _WIN_EXEC_EXTS
    return os.access(p, os.X_OK)


def _name_candidates(name: str) -> list[str]:
    """이 이름으로 찾아볼 파일 이름들. POSIX 는 `[name]`.

    Windows 에서 이름에 **이미 확장자가 달려 있으면** 그대로 쓴다. 붙이기만 하면
    `my-ai.exe` 가 `my-ai.exe.exe` 를 찾게 되어, 수정 전에는 되던 `--ai my-ai.exe` 가
    조용히 무시된다(codex 적대 리뷰 P2). 이미 달린 것이 `.cmd`·`.bat` 면 후보가 비는데,
    그것이 맞는 결과다 — 우리는 배치 shim 을 직접 실행하지 않는다.
    """
    if os.name != "nt":
        return [name]
    if os.path.splitext(name)[1].lower() in _WIN_KNOWN_EXTS:
        return [name]
    return [name + ext for ext in _exec_exts()]


def _which(name: str) -> str | None:
    """PATH 에서 실행 파일을 찾아 **경로**를 준다. 없으면 None.

    ⚠ **Windows 는 확장자를 붙이지 않으면 아무것도 못 찾는다** (사용자 실측 2026-09-01).
    종전 구현은 `os.path.join(d, name)` 만 봤다 — 그 머신에는 `claude.exe` 가 멀쩡히 있었고
    직접 실행하면 `2.1.70 (Claude Code)` 를 답했는데, 확장자 없는 `claude` 라는 파일은
    존재하지 않으므로 감지가 **구조적으로 실패**했다. 그리고 그 실패는 화면에서
    「연결 확인에 실패했습니다」로 보였다 — 연결은 멀쩡했는데.

    `os.curdir` 은 보지 않는다. Windows 의 `shutil.which` 는 현재 디렉토리를 먼저 보는데,
    그러면 러너를 띄운 폴더에 놓인 동명 파일이 사용자의 AI 를 가로챌 수 있다.
    """
    if os.path.dirname(name):
        # 경로가 실려 있으면 PATH 를 훑지 않는다 — 사용자가 지목한 그 파일이다.
        # 확장자는 여기서도 붙여 본다: `\\server\share\claude` 처럼 경로만 주고 확장자를
        # 생략한 지목이 실패하지 않도록(codex 적대 리뷰 P2).
        for cand in _name_candidates(name):
            if _is_exec(cand):
                return cand
        return None
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d:
            continue
        for cand in _name_candidates(name):
            p = os.path.join(d, cand)
            if _is_exec(p):
                return p
    return None


#: 알려진 AI CLI 이름 — 아래 「PATH 밖 표준 설치 위치」 탐색의 **allowlist** 다.
#: 이 집합 밖의 이름은 PATH 안에서만 찾는다. 홈 디렉토리를 임의 이름으로 뒤져 실행하면,
#: 오타나 서버가 준 값 하나가 우리가 의도한 적 없는 프로그램의 실행이 된다.
def _known_ai_names() -> set[str]:
    return set(_RUNTIME_SPECS.keys())


def _ai_install_dirs() -> list[str]:
    """AI CLI 가 **PATH 에 없어도** 놓여 있는 표준 설치 위치.

    설치기가 PATH 를 갱신하지 못하거나, 갱신했어도 이미 열려 있던 셸에는 반영되지 않는 일이
    흔하다. 실측(2026-09-01): Claude Code 의 Windows native installer 는
    `%USERPROFILE%\\.local\\bin` 에 넣는데 그 폴더가 사용자 PATH 에 **없었다** —
    `Get-Command claude` 도 못 찾았고, 그래서 설치 스크립트도 러너도 「AI 없음」이라 봤다.

    설치는 이미 돼 있는데 폴더 하나가 PATH 에 없다는 이유로 사용자에게 옵션을 요구하는 것은
    (그 사용자가 `--ai` 가 무엇인지 알 이유가 없다) 이 기능이 없애려는 마찰 그 자체다.
    파이썬 감지는 이미 「PATH 가 아직 안 잡혔을 수 있다 — 표준 설치 위치를 직접 본다」를
    하고 있었고(`bridge_setup.ps1`), 이것은 AI 축에 없던 그 대칭이다.
    """
    home = os.path.expanduser("~")
    if os.name == "nt":
        appdata = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        localapp = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        return [
            os.path.join(home, ".local", "bin"),            # Claude Code · Codex native installer
            os.path.join(appdata, "npm"),                   # npm -g (claude.cmd · gemini.cmd)
            os.path.join(localapp, "Programs", "Ollama"),   # Ollama 설치기
        ]
    return [
        os.path.join(home, ".local", "bin"),
        os.path.join(home, ".npm-global", "bin"),
        "/usr/local/bin",
        "/opt/homebrew/bin",
    ]


def _which_ai(name: str) -> str | None:
    """AI CLI 하나를 찾는다 — PATH 우선, 없으면 **표준 설치 위치**(알려진 이름만)."""
    p = _which(name)
    if p:
        return p
    if name not in _known_ai_names():
        return None
    exts = _exec_exts()
    for d in _ai_install_dirs():
        for ext in exts:
            cand = os.path.join(d, name + ext)
            if _is_exec(cand):
                return cand
    return None


def _resolve_exe(argv: list[str]) -> list[str]:
    """argv[0] 을 **실제 실행 파일 경로**로 바꾼다. 못 찾으면 그대로 둔다.

    이름만 담긴 argv 를 `Popen` 하면 그 이름이 PATH 에 있을 때만 통한다. 우리는 PATH 밖의
    표준 설치 위치도 감지 대상으로 삼으므로, 여기서 맞춰 두지 않으면 **「찾았다」와
    「실행할 수 있다」가 갈린다** — 감지는 성공하고 호출만 조용히 죽는 형태다.

    셸이 하던 PATH 해석을 대신하는 것이라 명령의 의미는 바뀌지 않는다. 그래서 `--cmd` 로
    받은 명령에도 적용한다(그 사용자도 Windows 에서 이름만 적을 수 있다).
    """
    if not argv:
        return list(argv)
    exe = _which_ai(argv[0])
    return ([exe] + list(argv[1:])) if exe else list(argv)


def detect_ai() -> tuple[str, list[str]] | None:
    for name, argv in _CLI_ADAPTERS:
        if _which_ai(name):
            return name, argv
    if _which_ai("ollama"):
        return "ollama", []
    return None


def pick_ai(ai: str, cmd: str | None) -> tuple[str, list[str]] | None:
    """이 실행에서 쓸 AI. 없으면 None.

    ⚠ **`--ai` 로 지목한 이름도 실재를 확인한다** (codex 적대 리뷰 P2, 2026-09-01).
    종전에는 우리 표 안의 이름(`claude` 등)이면 파일이 있든 없든 통과했다. 그러면
    `--check` 가 「사용할 AI: claude」와 종료코드 0 을 내고, 그 말을 믿은 사용자의 러너가
    상주해 질문을 가져간 뒤 **매번 실행 실패로 답한다** — 화면에는 「연결됨」인 채로.

    지목이 실재하지 않으면 **자동 감지로 갈아치우지 않는다.** 사용자가 세운 제한을 서버도
    우리도 넘어서지 않는다(codex P2-2, 2026-08-28 과 같은 계약). 대신 없다고 말한다.
    """
    if cmd:
        return "custom", []
    if ai:
        if not _which_ai(ai):
            _log(f"지정한 AI '{ai}' 를 이 컴퓨터에서 찾지 못했습니다(다른 AI 로 대신하지 않습니다).")
            return None
        if ai == "ollama":
            return "ollama", []
        known = dict(_CLI_ADAPTERS).get(ai)
        # 표 밖 이름은 호출 형태를 모른다 — 가장 흔한 모양으로 두고, 능력 질의가 통한
        # 형태를 알아내면 그것으로 교체된다(main 의 `_learned` 경로).
        return ai, list(known) if known else [ai, "-p", "{prompt}"]
    return detect_ai()


#: AI 설치 안내에 쓰는 주소. 깨지면 안내가 막다른 길이 되므로 한 자리에 모아 둔다.
_AI_SETUP_URL = "https://docs.claude.com/en/docs/claude-code/setup"


def _no_ai_message() -> list[str]:
    """AI 를 못 찾았을 때 사용자에게 낼 말.

    ⚠ **옵션 이름을 요구하지 않는다** (사용자 결정 2026-09-01). 종전 문구는
    「`--ai` 또는 `--cmd` 로 지정하세요」였는데, 웹 콘솔의 명령을 복사해 붙인 사용자가
    그 두 옵션의 의미도 사용법도 알 이유가 없다 — 알아야 할 사람에게만 통하는 안내는
    나머지 전원에게 막다른 길이다. 대신 **무엇이 필요한지**와 **어디를 찾아봤는지**를 말한다.
    「어디를 봤는지」가 load-bearing 이다: 이번 사용자의 AI 는 실제로 설치돼 있었고 그 폴더가
    PATH 에 없었을 뿐이라, 목록을 보면 자기 설치 위치가 빠졌다는 것을 바로 알 수 있다.
    """
    names = " · ".join((_RUNTIME_SPECS.get(n) or {}).get("label") or n
                       for n in _RUNTIME_SPECS)
    return [
        "  이 브리지는 이 컴퓨터에 설치된 AI 프로그램으로 답합니다.",
        f"  쓸 수 있는 것: {names}",
        f"  아직 없다면 Claude Code 를 설치한 뒤 이 명령을 다시 실행하세요: {_AI_SETUP_URL}",
        "  이미 설치했다면 설치 폴더가 시스템 PATH 에 등록되지 않았을 수 있습니다.",
        "  아래를 모두 찾아봤습니다:",
    ] + [f"    · {d}" for d in (["PATH 에 등록된 폴더 전부"] + _ai_install_dirs())]


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

#: 추론등급 축만 **다시** 묻는 좁은 질의 (2026-08-31).
#:
#: 위 `_CAPS_PROBE_PROMPT` 는 다섯 필드를 한 객체로 요구한다. 실측에서 claude 는 모델과
#: `model_flag` 는 답하고 `effort_flag` 를 빠뜨렸다 — 요구가 많으면 일부가 떨어진다.
#: 축 하나만 물으면 그 하나에 집중해 답한다. 1차에서 그 축을 못 받았을 때만 쓰므로 평상시
#: 추가 비용은 없다.
_CAPS_EFFORT_PROMPT = """\
너 자신에 대해 답하라. 지금 이 CLI 를 **비대화형으로 한 번 실행할 때**, 추론 수준
(reasoning effort / thinking level)을 인자로 지정할 수 있는가?

아래 JSON 객체 **하나만** 출력하라. 설명·머리말·맺음말을 붙이지 마라.

{
  "efforts": [
    {"value": "인자에 그대로 넣을 실제 값", "label": "사람이 읽을 이름"}
  ],
  "effort_flag": ["추론 수준을 지정하는 인자 형태. {effort} 자리에 위 value 가 들어간다"]
}

규칙:
- `effort_flag` 는 인자를 **배열로** 쓴다.
  예: ["--effort", "{effort}"] · ["-c", "model_reasoning_effort={effort}"]
- 지정할 수 **없다면** `"efforts": []` 와 `"effort_flag": []` 로 답하라. 그것도 답이다 —
  없는 기능을 있다고 답하면 사용자는 고를 수 있는데 반영되지 않는 화면을 보게 된다.
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

#: 축 재질의를 시작하기 위한 최소 잔여 시간. 이보다 적게 남았으면 시작하지 않는다 —
#: 시작해 놓고 중간에 잘리면 토큰만 쓰고 답은 못 받는다.
_CAPS_AXIS_MIN_SEC = 20.0

#: `--help` 에 주는 시간. 도움말은 즉시 나온다 — 여기서 오래 걸리는 CLI 는 비정상이므로
#: 기다릴 이유가 없고, 못 읽으면 "모른다" 로 다룬다(축을 비우는 근거로 쓰지 않는다).
_CAPS_HELP_TIMEOUT_SEC = 15.0

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
    # ④ **위험한 축의 플래그 이름은 거부한다** (codex REV-20260828T171500 P1-1).
    #    ①~③ 은 "셸 실행" 과 "임의 플래그 따라붙기" 를 막지만, 형태가 멀쩡한 **한 개의 나쁜
    #    플래그**는 통과시킨다 — `["--mcp-config", "{model}"]` 는 토큰 2개·치환자 1개·옵션
    #    시작이라 ①~③ 을 전부 만족하면서 방금 우리가 없앤 MCP 표면을 되살리고,
    #    `["--permission-mode", "{model}"]` + 모델값 `bypassPermissions` 는 권한 경계를 연다.
    #    모델·등급을 지정하는 정당한 플래그에는 아래 조각이 들어갈 일이 없다.
    #    ⚠ 치환자를 **포함한 토큰도 검사한다** — `-c mcp_servers={effort}` 처럼 값 자리에
    #      숨는 형태가 있기 때문이다(codex 의 `-c` config override 축).
    low = " ".join(parts).lower()
    if any(bad in low for bad in _FORBIDDEN_FLAG_FRAGMENTS):
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
            # 축 확정 표지는 **보존한다** — 여기서 떨어뜨리면 확정을 마친 캐시가 매 기동마다
            # 미확정으로 되살아나 같은 질의를 반복한다(그리고 그 질의는 사용자 토큰을 쓴다).
            # ⚠ `bool(...)` 이 아니라 `is True` 다 (codex P2-1): 손으로 고친 캐시의
            #   `"effort_probed": "false"` 같은 **문자열**이 truthy 로 읽혀 재확정을 영구히
            #   억제하는 것을 막는다. 표지는 우리가 쓴 참값일 때만 표지다.
            "effort_probed": caps.get("effort_probed") is True,
            "source": str(caps.get("source") or "cache")[:16],
        }
        if argv:
            entry["argv"] = argv
        out[name] = entry
    return out


def _ask_json(argv: list[str], prompt: str, timeout: float) -> dict | None:
    """이 CLI 에 프롬프트 하나를 주고 답에서 JSON 객체를 꺼낸다. 못 얻으면 None.

    `probe_runtime_caps` 의 1차 질의와 축 재질의가 같은 절차를 쓴다 — 두 벌로 두면
    한쪽만 고쳐지고, 그때 어느 쪽이 실제로 쓰이는지가 코드에서 안 보인다.
    """
    cmd = _resolve_exe(
        [prompt if a == "{prompt}" else a.replace("{prompt}", prompt) for a in argv])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=(timeout if timeout and timeout > 0
                                       else _CAPS_PROBE_TIMEOUT_SEC))
    except Exception:  # noqa: BLE001  (미설치·타임아웃·권한 — 전부 "못 물었다" 로 같다)
        return None
    if proc.returncode != 0:
        return None
    # 출력이 아무리 커도 여기서 자른다 — `capture_output` 은 전부 메모리에 담는다.
    return _extract_json((proc.stdout or "")[:_CAPS_PROBE_MAX_BYTES])


def _cli_help_text(name: str, timeout: float = _CAPS_HELP_TIMEOUT_SEC) -> str | None:
    """`<cli> --help` 의 출력. 못 읽으면 None — **"없다" 가 아니라 "모른다"** 다.

    이 구분이 load-bearing 이다: 도움말을 못 읽었다고 축을 비우면, `--help` 가 느리거나
    다른 관례를 쓰는 CLI 에서 멀쩡한 기능이 사라진다. 아래 호출부는 `True` 일 때만 채택하고
    `None` 은 "확인 못 함" 으로 따로 다룬다.

    ⚠ **성공한 도움말만 읽는다** (codex P1-3). 종료코드를 무시하면 `unknown option
    '--effort'` 같은 **에러 문구**를 도움말로 읽어, 없는 플래그를 있다고 판정한다 — 오탐의
    방향이 정확히 최악이다(고른 값이 CLI 에서 거부되어 답이 아예 오지 않는다).
    그리고 stderr 은 보지 않는다: 도움말을 stderr 로 내는 CLI 도 있지만, 그 관용을 주면 위
    에러 경로가 같은 문으로 들어온다. 못 읽으면 "모른다" 로 남는 편이 안전하다.
    """
    try:
        proc = subprocess.run(_resolve_exe([name, "--help"]), capture_output=True, text=True,
                              timeout=(timeout if timeout and timeout > 0
                                       else _CAPS_HELP_TIMEOUT_SEC))
    except Exception:  # noqa: BLE001
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "")[:_CAPS_PROBE_MAX_BYTES] or None


def _help_mentions_flag(help_text: str | None, flag: list[str] | None) -> bool | None:
    """이 플래그를 그 CLI 가 실제로 받는가. 확인할 수 없으면 None.

    `--effort` 가 `--effort-level` 에 부분일치해 참이 되지 않도록 낱말 경계를 건다 — 그
    오탐은 "있다고 판단했는데 CLI 가 거부하는" 형태라, 사용자에게는 고른 값이 조용히
    무시되는 것으로 보인다(P0-T 가 지운 상태와 같다).

    ⚠ **이 검사가 확인하는 것은 첫 토큰뿐이다.** codex 의 `["-c",
    "model_reasoning_effort={effort}"]` 같은 config-override 형태에서는 `-c` 의 존재만
    확인되고 그 **키가 유효한지는 확인되지 않는다**. 그래도 이 경로를 쓰는 이유: 여기서
    쓰는 값은 우리 내장 표뿐이고 그것은 실측으로 채운 것이며, 틀렸을 때의 결과도 "그 CLI 가
    모르는 config 키를 무시한다" 로 그친다(플래그 자체가 없을 때처럼 명령 전체가 죽지 않는다).
    """
    if not flag or help_text is None:
        return None
    head = str(flag[0] or "").split("=", 1)[0].strip()
    if not head.startswith("-"):
        # 값을 위치 인자로 받는 형태(`["{model}"]`)는 도움말로 확인할 방법이 없다.
        return None
    return re.search(r"(?<![\w-])" + re.escape(head) + r"(?![\w-])", help_text) is not None


def _caps_axis_unsettled(caps: object) -> bool:
    """캐시된 능력의 추론등급 축이 **확정된 적 없는가**.

    `effort: null` 은 두 가지 다른 사실을 뭉갠다 — "물어봤는데 이 CLI 는 지원하지 않는다"
    와 "축을 다룬 적이 없다"(2026-08-31 이전 러너가 남긴 캐시). 그 둘을 구분하지 않으면
    이번 복구 경로가 **기존 사용자에게는 영영 실행되지 않는다**: 캐시가 있으니 묻지 않고,
    묻지 않으니 축이 계속 빈 채로 신고되고, 화면의 등급 항목은 계속 사라져 있다.

    그래서 확정을 거친 캐시에는 `effort_probed` 를 남기고, 그 표지가 없는 캐시만 한 번 더
    확정한다. 확정 결과가 "지원하지 않음" 이어도 표지는 남으므로 다음 기동은 묻지 않는다.
    """
    if not isinstance(caps, dict):
        return False
    return not caps.get("effort") and not caps.get("effort_probed")


#: 추론등급 플래그로 **위장할 수 없는** 조각. `_coerce_flag` 는 치환자와 토큰 형태만 보므로
#: `["--model", "{effort}"]` 같은 **축이 뒤바뀐** 플래그가 형태 검사를 그대로 통과한다
#: (codex P1-4). 그러면 `build_cmd` 가 `--model low` 를 붙여 모델 지정을 덮어쓴다 — 사용자는
#: 등급을 골랐는데 모델이 바뀐다. 축을 넘는 이름은 여기서 끊는다.
_EFFORT_FLAG_FORBIDDEN = ("model", "-m ", "agent", "prompt", "file", "output")


def _flag_fits_axis(flag: list[str] | None, axis: str) -> bool:
    """이 플래그가 **그 축의** 플래그인가 (codex P1-4).

    값 목록은 신고와 대조되지만 플래그는 대조할 목록이 없다 — 형태만 본다. 그 형태 검사는
    "옵션처럼 생겼는가" 까지라, 다른 축의 정당한 플래그를 그대로 통과시킨다. 축을 넘는
    이름을 거부하는 것이 여기서 할 수 있는 최소한이다.
    """
    if not flag:
        return False
    low = " ".join(flag).lower()
    if axis == "effort":
        return not any(bad in low for bad in _EFFORT_FLAG_FORBIDDEN)
    return True


def _settle_effort_axis(
    name: str, argv: list[str], flag: list[str] | None, options: list[dict], left: float
) -> tuple[list[str] | None, list[dict], bool]:
    """추론등급 축을 확정한다 — 1차 질의가 이 축을 못 채웠을 때의 복구 경로.

    반환은 `(플래그, 값목록, 확정했는가)`. 셋째 값이 `False` 면 **결론을 내지 못한 것**이라
    캐시에 확정 표지를 남기지 않는다 — 일시적 실패(도움말을 못 읽음)가 "이 CLI 는 등급을
    지원하지 않는다" 로 영구히 굳지 않게 하는 자리다.

    ## 무엇을 고치는가 (실측 2026-08-31)

    1차 질의는 모델·등급·두 플래그를 **한 JSON 으로** 요구한다. claude 는 모델과 모델
    플래그는 답하고 `effort_flag` 를 빠뜨렸다. 종전 코드는 `efforts ... if effort_flag
    else []` 라 등급 목록을 통째로 버렸고, 그 부분 결과가 내장 표를 이겨(폴백은 질의
    자체가 실패했을 때만) **실제로 지원되는 `--effort` 가 화면에서 사라졌다.**
    사용자에게는 "쓸 수 있는 effort 가 확인되지 않는" 상태로 보인다.

    ## 짝을 섞지 않는다

    유효한 것은 (플래그, 값 목록) **짝**이다. AI 가 준 플래그에 우리 표의 값을 붙이거나
    그 반대로 하면, 그 CLI 가 받지 않는 조합이 만들어지고 고른 값이 조용히 무시된다.
    그래서 아래 세 경로는 각각 **짝째로** 채택한다.

    ## 순서 — 묻는 것이 먼저다 (사용자 결정 2026-08-31)

    목록의 출처는 연결된 AI 다. 그래서 ① 축만 좁게 **다시 묻고**, 그래도 못 받으면
    ② 우리 표의 짝을 **그 CLI 자신의 `--help` 로 검증**해서 쓴다(우리가 아는 값이라도
    실재를 확인하고 쓴다). ③ 도움말에 없으면 축을 비운다 — 지어내지 않는다.
    """
    if flag and options and _flag_fits_axis(flag, "effort"):
        return flag, options, True      # AI 가 짝을 다 줬다 — 그대로.

    # ① 축만 좁게 재질의. 큰 JSON 하나를 요구할 때 빠뜨린 필드를, 그것만 물으면 답한다.
    if left >= _CAPS_AXIS_MIN_SEC:
        _log(f"{name}: 추론 수준을 다시 물어보는 중…")
        got = _ask_json(argv, _CAPS_EFFORT_PROMPT, min(left, _CAPS_PROBE_TIMEOUT_SEC))
        if got is not None:
            re_flag = _coerce_flag(got.get("effort_flag"), "{effort}")
            re_opts = _coerce_options(got.get("efforts"), limit=12)
            if re_flag and re_opts and _flag_fits_axis(re_flag, "effort"):
                return re_flag, re_opts, True
            # ⚠ **명시적 부정만** 존중한다 (codex P1-2). 종전에는 "flag 도 없고 목록도 없다"
            #   를 전부 "이 CLI 는 지원하지 않는다" 로 읽었는데, 그 조건은 `{}`·필드 누락·
            #   형태 오류(거부된 플래그)까지 같이 삼킨다. 그러면 실제로는 지원하는 CLI 가
            #   빈 축으로 **확정**되어(표지까지 남아) 다시는 확인되지 않는다.
            #   두 키가 **실제로 있고 둘 다 비어 있을 때**만 "없다" 는 답으로 친다.
            if (isinstance(got.get("efforts"), list) and not got["efforts"]
                    and isinstance(got.get("effort_flag"), list) and not got["effort_flag"]):
                return None, [], True

    # ② 우리 표의 짝을 그 CLI 의 도움말로 검증해서 쓴다. 남은 시간 안에서만 — 도움말 하나가
    #    전체 deadline 을 넘기면 뒤에서 기다리는 쪽이 이미 폴백으로 떠난 뒤다 (codex P1-1).
    spec = _RUNTIME_SPECS.get(name) or {}
    spec_flag = _coerce_flag(spec.get("effort"), "{effort}")
    spec_opts = _coerce_options(spec.get("efforts"), limit=12)
    if spec_flag and spec_opts and left > 0:
        # ⚠ `left <= 0` 이면 도움말도 부르지 않는다 (codex P1-3). 종전에는 남은 시간이 없어도
        #   15초를 새로 줬는데, 그러면 "전체 deadline" 이라는 말이 거짓이 된다 — 호출측은 이미
        #   폴백으로 떠난 뒤이고, 그 15초는 아무도 읽지 않을 답을 기다리는 시간이다.
        #   시간이 없으면 축을 비우되 **확정으로 기록하지 않아**(아래 False) 다음 기동이 다시 본다.
        help_budget = min(_CAPS_HELP_TIMEOUT_SEC, left)
        seen = _help_mentions_flag(_cli_help_text(name, timeout=help_budget), spec_flag)
        if seen is True:
            _log(f"{name}: 추론 수준을 답하지 않아 내장 표로 보완했다 (--help 로 실재 확인).")
            return spec_flag, spec_opts, True
        if seen is None:
            # 도움말을 **못 읽었다** — "없다" 가 아니다 (codex P2-2). 축은 비우되 확정으로
            # 기록하지 않아, 다음 기동이 다시 확인한다. 일시적 실패가 영구 미지원으로
            # 굳는 것이 이 축에서 가장 되돌리기 어려운 상태다.
            return None, [], False

    # ③ 넘길 방법을 확인하지 못했다 — 축을 비운다. 화면에서 그 항목이 빠지고,
    #    반영되지 않을 조작면은 생기지 않는다.
    #
    #    확정 여부는 **왜 여기 왔는지**로 갈린다. 우리 표에 짝이 아예 없으면(표 밖 CLI) 더
    #    확인할 것이 없으니 결론이다. 짝은 있는데 시간이 없어 도움말을 못 봤다면 그것은
    #    결론이 아니다 — 확정으로 기록하면 "시간이 없어 못 본 것" 이 "이 CLI 는 지원하지
    #    않는다" 로 굳는다(P2-2 와 같은 부류).
    _unchecked = bool(spec_flag and spec_opts and left <= 0)
    return None, [], not _unchecked


def probe_runtime_caps(name: str, argv: list[str],
                       timeout: float | None = None) -> dict | None:
    """그 AI 에게 **직접 물어** 능력을 받는다 (P0-Z4). 실패하면 None.

    실패를 조용히 삼키지 않고 None 으로 알리는 이유: 호출측이 내장 기본값으로 폴백할지
    (표에 있는 런타임) 아니면 신고에서 뺄지(모르는 런타임) 정해야 한다.

    **부분 성공은 실패가 아니다** (2026-08-31): 모델은 받고 등급은 못 받은 답이 실제로
    관측된다. 그때 축 하나가 비었다고 전체를 버리면 모델 목록까지 잃고, 반대로 비운 채
    두면 지원되는 기능이 화면에서 사라진다 — `_settle_effort_axis` 가 그 축만 복구한다.
    """
    budget = timeout if timeout and timeout > 0 else _CAPS_PROBE_TIMEOUT_SEC
    started = time.monotonic()
    got = _ask_json(argv, _CAPS_PROBE_PROMPT, budget)
    if not got:
        return None
    models = _coerce_options(got.get("models"))
    if not models:
        # 모델을 하나도 못 받았으면 이 질의는 실패다 — 등급만으로는 선택기를 세울 수 없다.
        return None
    model_flag = _coerce_flag(got.get("model_flag"), "{model}")
    effort_flag, efforts, effort_settled = _settle_effort_axis(
        name, argv,
        _coerce_flag(got.get("effort_flag"), "{effort}"),
        _coerce_options(got.get("efforts"), limit=12),
        budget - (time.monotonic() - started),
    )
    label = " ".join(str(got.get("label") or name).split())[:60] or name
    # 모델 축도 **넘길 방법이 있어야 목록이 뜻을 갖는다** (codex P1-2). 목록만 신고하고
    # 플래그가 없으면 화면에는 고를 수 있는 것처럼 나오지만 `build_cmd` 는 인자를 붙이지
    # 못해 CLI 기본 모델로 답한다 — "고를 수 있는데 반영은 안 되는" 조작면이 이 경로로
    # 되살아난다. 우리 표에 그 CLI 의 플래그가 있으면 그것으로 메우고(호출법 폴백은 유지
    # 하기로 한 축이다), 표에도 없으면(표 밖 CLI) **목록을 비운다** — 그러면 그 런타임은
    # 신고되지 않고, 사용자는 없는 선택지를 보지 않는다.
    if not model_flag:
        model_flag = _coerce_flag((_RUNTIME_SPECS.get(name) or {}).get("model"), "{model}")
    if not model_flag:
        models = []
    return {
        "label": label,
        "models": models,
        "efforts": efforts,
        # 플래그가 없으면 그 축은 지정 불가 — 목록도 비운다(위 `efforts` 와 같은 이유).
        "model": model_flag,
        "effort": effort_flag,
        # 축 확정 절차를 **결론까지** 거쳤다는 표지. 결과가 "지원하지 않음"(둘 다 빈 값)이어도
        # 결론이면 남긴다 — 이 표지가 없으면 다음 기동이 같은 축을 또 묻는다
        # (`_caps_axis_unsettled`). 반대로 결론을 못 냈으면(도움말을 못 읽음) 남기지 않아
        # 다음 기동이 다시 확인한다 (codex P2-2).
        "effort_probed": bool(effort_settled),
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
        names = [only] if _which_ai(only) else names

    cached = cached or {}
    present = [n for n in names if _which_ai(n)]
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
           if (cached.get(n) is None or _caps_axis_unsettled(cached.get(n)))
           and ((_RUNTIME_SPECS.get(n) or {}).get("argv") or n in unknown_argvs)] if probe else []
    if ask:
        _log(f"쓸 수 있는 모델·추론 수준을 물어보는 중… ({', '.join(ask)} — 최초 1회, 수십 초)")

        # 전체 질의에 **하나의 절대 deadline** 을 둔다 (codex P2-4). 후보를 순차로 시도하는
        # 표 밖 CLI 는 후보마다 timeout 을 다 쓸 수 있어(240초 × 2) main 의 대기(250초)를
        # 넘긴다. 그러면 main 은 폴백으로 기동하고, 뒤에 남은 스레드가 아무도 읽지 않을 답을
        # 위해 계속 토큰과 CPU 를 태운다. deadline 을 공유해 남은 시간이 없으면 멈춘다.
        deadline = time.monotonic() + _CAPS_PROBE_TIMEOUT_SEC

        def _probe(nm: str) -> None:
            prev = cached.get(nm)
            if prev is not None:
                # 캐시는 있는데 **추론등급 축만** 미확정이다(구 러너가 만든 캐시). 모델 목록은
                # 이미 그 AI 가 답한 것이므로 전체를 다시 묻지 않는다 — 축 하나만 확정하고
                # 그 사실을 캐시에 남겨 다음 기동은 묻지 않게 한다.
                left = deadline - time.monotonic()
                argv = list(prev.get("argv") or (_RUNTIME_SPECS.get(nm) or {}).get("argv") or [])
                if left <= 5.0 or not argv:
                    # 표지를 남기지 않고 물러난다 — 다음 기동이 다시 시도한다. 여기서
                    # 확정으로 기록하면 "시간이 없어 못 물어본 것" 이 "물어봤는데 없다" 가 된다.
                    return
                flag, opts, settled = _settle_effort_axis(nm, argv, None, [], left)
                probed[nm] = {**prev, "effort": flag, "efforts": opts,
                              "effort_probed": bool(settled)}
                return
            attempts = list(unknown_argvs.get(nm) or [list(_RUNTIME_SPECS[nm]["argv"])])
            # 표 안 CLI 는 후보 호출 형태가 하나뿐이라 **한 번 실패하면 곧 포기**였다.
            # 실측(2026-08-31): codex 는 같은 조건에서 성공(6종 응답)과 실패를 오간다. 그 한
            # 번의 실패가 이제는 "그 런타임이 화면에서 통째로 사라짐" 을 뜻한다(내장 모델
            # 목록 폴백을 없앴으므로). 남은 시간이 있으면 한 번 더 묻는다 — 시간 검사는
            # 루프 안에 이미 있어 deadline 을 넘기지 않는다.
            if len(attempts) == 1:
                attempts = attempts * 2
            for argv in attempts:
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
                     + (f" · 추론 {len(got['efforts'])}단계" if got["efforts"] else
                        " · 추론 수준 지정 불가")
                     + " (본인 응답)")
            elif cached.get(n) is not None:
                # 축 재확정만 시도했고 그것도 못 얻었다 — 캐시를 지우지 않는다.
                _log(f"  {n}: 추론 수준을 확인하지 못해 이전 값을 유지합니다.")
            else:
                # ⚠ 종전 문구(내장 표로 대신한다는 안내)는 이제 거짓이다 (2026-08-31).
                #   모델 목록 폴백을 없앴으므로
                #   답을 못 받으면 **그 런타임은 화면에 나타나지 않는다**. 로그가 종전 문구를
                #   유지하면 사용자는 목록이 있는 줄 알고 선택기를 찾는다 — 그리고 없는 이유를
                #   어디서도 듣지 못한다. 다음 행동(재시도 방법)까지 여기서 말한다.
                _log(f"  {n}: 답을 받지 못했습니다 — 이 런타임은 목록에 나오지 않습니다. "
                     f"({n} 로그인·네트워크 확인 후 `--refresh-caps` 로 다시 시도)")

    out: list[dict] = []
    for name in present:
        spec = _RUNTIME_SPECS.get(name) or {}
        # ⚠ 새로 물어본 것이 캐시를 **이긴다**. 반대로 두면 축 재확정(위 `_probe` 의 캐시
        #   분기)이 매번 돌면서도 결과가 버려져, 사용자는 같은 빈 목록을 계속 본다.
        caps = probed.get(name) or cached.get(name)

        if caps is None:
            # 폴백 — **호출법만** 우리가 아는 것을 쓴다. 모델 목록은 넣지 않는다.
            #
            # ⚠ 종전에는 내장 표의 모델 이름까지 신고했다. 그 표는 우리가 적어 둔 시점에
            #   멈춰 있어서, 라이브에서 codex 가 `gpt-5.1-codex` 로 보였다 — 실제 그 계정이
            #   쓸 수 있는 것은 `gpt-5.6-sol`·`terra`·`luna`·`5.5`·`5.4` 였다(사용자 제보
            #   2026-08-31). **없는 모델을 고를 수 있다고 말하는 것**이라, 고른 순간 CLI 가
            #   거부하거나 조용히 다른 모델로 답한다.
            #
            #   목록의 출처는 연결된 AI 라는 것이 이 기능의 계약이고(사용자 결정), 그 계약을
            #   폴백이 뒷문으로 깨고 있었다. 물어보지 못했으면 **모른다고 하는 편이** 틀린
            #   목록을 확신 있게 보여주는 것보다 낫다 — 아래 `if not caps.get("models")` 가
            #   그 런타임을 신고에서 빼고, 화면에는 그 그룹이 나타나지 않는다.
            #
            #   호출법(argv·플래그)은 성격이 다르다: 잘 변하지 않고, 없으면 **실행 자체가**
            #   불가능하며, 값이 아니라 형태라 "틀린 선택지를 제시" 하는 문제가 생기지 않는다.
            #
            #   ollama 는 예외 — HTTP 로 **실조회**한 목록이라 우리가 적어 둔 값이 아니다.
            models = _ollama_models() if name == "ollama" else []
            caps = {
                "label": str(spec.get("label") or name),
                "models": models,
                "efforts": [],
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


#: 실패 사유로 실어 보낼 자식 출력의 최대 길이(문자).
_FAIL_DETAIL_MAX = 400

#: **stderr 에 있어도 실패 원인이 아닌** 줄 — 이것만 남으면 stderr 는 «비었다» 로 본다.
#:
#: 라이브에서 관측된 형태: claude CLI 는 파이프 stdin 을 3초 기다린 뒤 그 사실을 stderr 로
#: 알린다. 그 줄은 종료코드와 무관한 안내인데, 그것만 보고 "stderr 가 비지 않았다" 로 판단하면
#: 진짜 사유(stdout 에 있다)를 덮어쓴다.
_STDERR_NOISE = (
    re.compile(r"^\s*warning:\s*no stdin data received", re.I),
    re.compile(r"^\s*$"),
)

#: 자식 CLI 의 실패 출력 → **사용자가 다음에 할 행동**. 런타임 이름이 아니라 *증상 어휘* 로
#: 잡는다 — 어느 CLI 든 같은 부류의 실패는 같은 말을 쓰기 때문이고, 새 런타임이 붙어도 표를
#: 고칠 필요가 없다. 하나도 안 맞으면 안내 없이 원문만 전달한다(추측해 오도하지 않는다).
_FAILURE_HINTS: tuple[tuple[object, str], ...] = (
    (re.compile(r"usage limit|session limit|quota|rate.?limit|too many requests|"
                r"사용 한도|한도에 도달", re.I),
     "연결된 AI 의 사용 한도에 걸렸습니다. 위에 적힌 초기화 시각이 지난 뒤 같은 질문을 다시 "
     "보내면 처리됩니다(질문은 그대로 다시 보내면 됩니다)."),
    (re.compile(r"not logged in|not authenticated|please\s+(run\s+)?/?log\s?in|"
                r"unauthorized|invalid api key|\b401\b", re.I),
     "연결된 AI 에 로그인돼 있지 않습니다. 러너를 띄운 컴퓨터에서 그 CLI 에 로그인한 뒤 "
     "다시 질문해 주세요."),
    (re.compile(r"unknown option|unrecognized (option|argument)|"
                r"invalid (option|argument)|unexpected argument", re.I),
     "연결된 AI 가 이 호출의 옵션을 알지 못합니다(구버전일 수 있습니다). 그 CLI 를 업데이트하거나 "
     "웹의 「연결 준비」로 러너를 최신 사본으로 다시 받아 실행해 주세요."),
    (re.compile(r"command not found|no such file or directory|not recognized as", re.I),
     "연결된 AI 의 실행 파일을 찾지 못했습니다. 러너를 띄운 컴퓨터에 그 CLI 가 설치돼 있고 "
     "PATH 에서 보이는지 확인해 주세요."),
)

#: 실패 원문에 섞여 나갈 수 있는 자격증명 형태. 사유를 살리려다 토큰을 대화에 흘리지 않는다.
_SECRET_PATTERNS = (
    re.compile(r"\bmat_[A-Za-z0-9_\-]{4,}"),
    re.compile(r"(?i)\b(bearer|authorization:\s*bearer)\s+\S+"),
    re.compile(r"(?i)\b(sk|api)[-_][A-Za-z0-9_\-]{8,}"),
)


def _redact_secrets(text: str) -> str:
    """실패 원문에서 자격증명 형태를 지운다. 사유를 살리는 일이 토큰 유출이 되면 안 된다."""
    out = text or ""
    for pat in _SECRET_PATTERNS:
        out = pat.sub("<가려짐>", out)
    return out


def _meaningful_lines(text: str) -> str:
    """잡음 줄을 걷어낸 나머지. 전부 잡음이면 빈 문자열."""
    keep = [ln for ln in (text or "").splitlines()
            if not any(p.search(ln) for p in _STDERR_NOISE)]
    return "\n".join(keep).strip()


def describe_cli_failure(returncode: int, out: str, err: str) -> str:
    """자식 CLI 가 0 이 아닌 코드로 끝났을 때 **사용자에게 나갈 한 덩어리**를 만든다.

    ## 왜 stdout 도 보는가 (라이브 실측 2026-09-01)

    종전에는 stderr 만 실어 보냈다. 그런데 실패 사유를 **stdout 으로 내는 CLI 가 있다** —
    claude 는 사용 한도에 걸리면 `You've hit your session limit · resets 5:30pm` 을 stdout 에
    쓰고 exit 1 로 끝나며, stderr 에는 stdin 안내만 남는다. 그래서 사용자가 받은 답은

        AI 가 오류로 끝났습니다(exit 1):

    — 콜론 뒤가 **빈** 문장이었다. 원인이 화면에 없으니 사용자는 같은 질문을 그대로 다시
    보냈고(대화 `…d7010dcf`, 15:38 · 15:39), 같은 빈 문장을 다시 받은 뒤 대화를 떠났다.
    한도는 몇 분 뒤 풀리는 **회복 가능한** 상태였다.

    즉 고칠 것은 한도 자체가 아니라 **사유를 버리는 경로**다. 채널(어느 파이프로 나오는가)은
    CLI 마다 다르고 버전마다 바뀌므로, 채널을 맞히려 들지 않고 **둘 다 보고 의미 있는 쪽을
    고른다** — 이 선택은 CLI 가 무엇이든 성립한다.

    ## 무엇을 어떤 순서로 담나

    1. `exit <코드>` — 기계적 사실.
    2. 사유 원문(잡음 제거 · 자격증명 마스킹 · `_FAIL_DETAIL_MAX` 자름). stderr 에 의미 있는
       줄이 있으면 그것, 없으면 stdout. 둘 다 없으면 "출력이 없었다" 를 **명시**한다 —
       빈 콜론으로 끝내지 않는다(그게 이 결함의 표면이었다).
    3. 다음 행동 1줄(`_FAILURE_HINTS` 가 맞을 때만). 맞는 것이 없으면 붙이지 않는다.
    """
    detail = _meaningful_lines(err) or _meaningful_lines(out)
    detail = _redact_secrets(detail)
    if len(detail) > _FAIL_DETAIL_MAX:
        detail = detail[:_FAIL_DETAIL_MAX] + "…"
    head = f"AI 가 오류로 끝났습니다(exit {returncode})."
    body = f" 연결된 AI 가 남긴 사유: {detail}" if detail else \
        " 연결된 AI 가 아무 출력도 남기지 않아 사유를 알 수 없습니다."
    for pat, hint in _FAILURE_HINTS:
        if detail and pat.search(detail):
            return head + body + "\n\n" + hint
    return head + body


def _run_cli_cancelable(cmd: list[str], cancel_check, cwd: str | None = None,
                        env: dict | None = None) -> tuple[bool, str]:
    """CLI 를 돌리되 **취소되면 죽인다**. (성공여부, 본문 | CANCELED)

    왜 `subprocess.run` 이 아닌가: `run` 은 끝날 때까지 블로킹이라 그동안 도착한 취소를 볼 수
    없다. 그러면 사용자가 중단을 눌러도 개인 계정 토큰이 그 조사가 끝날 때까지 계속 탄다 —
    취소의 실질 목적이 바로 그 낭비를 막는 것이다.

    ⚠ 여기에도 sleep 은 없다. 자식이 끝나기를 `Thread.join(timeout)` 으로 **블로킹 대기**하고,
    그 반환 틈에 취소를 확인할 뿐이다. 서버를 두드리지 않으므로 폴링이 아니다.
    """
    # 이 호출의 **소요와 결말**을 남긴다 (TASK-20260901T163000). 종전에는 자식이 실패해도
    # 사유 400자가 사용자 답변에 실려 나갈 뿐, 로그에는 아무것도 남지 않았다 — 「내 AI 가
    # 오류로 끝났습니다」를 받은 사용자가 원인을 물어와도 우리 쪽에 볼 것이 없었다.
    _t0 = time.monotonic()
    _exe = (cmd[0] if cmd else "")
    try:
        proc = subprocess.Popen(_resolve_exe(cmd), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                cwd=cwd, env=env)
    except Exception as e:  # noqa: BLE001
        # 여기서 터지는 것은 대개 「그 실행 파일이 없다·권한이 없다」이고, 예외 형이 그
        # 둘을 정확히 가른다(FileNotFoundError vs PermissionError). 문자열로 뭉개지 않는다.
        _log_exc(_EV_AI_SPAWN_FAIL, "AI 를 실행하지 못했다", e, exe=_exe, cwd=cwd or "")
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
            log_event("ai.canceled", "취소되어 AI 를 중단했다", level="WARN",
                      exe=_exe, dur_ms=int((time.monotonic() - _t0) * 1000))
            return False, CANCELED
        if _AI_TIMEOUT_SEC and waited >= _AI_TIMEOUT_SEC:
            _kill(proc)
            pump.join(5.0)
            log_event(_EV_AI_TIMEOUT, "AI 호출이 상한을 넘겨 중단했다", level="ERROR",
                      exe=_exe, limit_sec=int(_AI_TIMEOUT_SEC),
                      dur_ms=int((time.monotonic() - _t0) * 1000),
                      stderr_tail=(box.get("err") or "")[-2000:])
            return False, f"AI 호출이 {int(_AI_TIMEOUT_SEC)}초를 넘겨 중단했습니다."

    _dur = int((time.monotonic() - _t0) * 1000)
    if proc.returncode != 0:
        # ⚠ 자식의 출력 **전문**(각 상한 2KB)은 원장에만 남긴다. 사용자 답변에 실리는 400자는
        #   잘려 있어서, 정작 원인이 적힌 뒷부분이 사라지는 일이 잦았다.
        # ⚠ stderr 뿐 아니라 **stdout 꼬리도** 남긴다 (TASK-20260901T160000): 사용 한도 같은
        #   정책성 실패의 사유를 stdout 으로 내는 CLI 가 있고, stderr 만 적는 원장은 그 실패를
        #   「사유 없음」으로 기록한다 — 사용자 화면에서 사라진 것과 같은 정보가 원장에서도
        #   사라지면 사후 진단이 불가능해진다.
        log_event(_EV_AI_FAIL, "AI 가 오류로 끝났다", level="ERROR",
                  exe=_exe, exit=proc.returncode, dur_ms=_dur,
                  stdout_bytes=len(box.get("out") or ""),
                  stdout_tail=_redact_secrets((box.get("out") or "")[-2000:]),
                  stderr_tail=_redact_secrets((box.get("err") or "")[-2000:]))
        return False, describe_cli_failure(int(proc.returncode), box.get("out", ""),
                                           box.get("err", ""))
    log_event("ai.ok", level="DEBUG", exe=_exe, exit=0, dur_ms=_dur,
              stdout_bytes=len(box.get("out") or ""))
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


def _ensure_strict_mcp_supported(kind: str, exe: str = "claude") -> bool:
    """claude 가 `--strict-mcp-config` 를 아는지 기동 시 1회 확인한다. (플래그가 남으면 True)

    모르는 버전에 넘기면 **모든 질문이** unknown option 으로 죽는다 — 사용자에게는 "AI 가
    답을 안 한다" 로만 보인다 (codex P2-2). 그래서 확인하고, 없으면 표에서 빼고 말한다.

    **확인 자체가 실패하면(미설치·타임아웃) 플래그를 남긴다.** 두 오류의 값이 다르기
    때문이다 — 잘못 남기면 즉시·시끄럽게 실패해서 고칠 수 있고, 잘못 빼면 원 결함이
    조용히 돌아와 아무도 모른다. 드러나는 쪽을 고른다.
    """
    if kind != "claude" or _KEEP_MCP:
        return False
    spec_argv = list((_RUNTIME_SPECS.get("claude") or {}).get("argv") or [])
    if _STRICT_MCP_FLAG not in spec_argv:
        return False
    try:
        proc = subprocess.run(_resolve_exe([exe, "--help"]), capture_output=True,
                              text=True, timeout=30)
        helptext = (proc.stdout or "") + (proc.stderr or "")
    except Exception:  # noqa: BLE001  (미설치·타임아웃·권한 — 전부 "확인 못 했다" 로 같다)
        _log(f"참고: {exe} --help 로 {_STRICT_MCP_FLAG} 지원을 확인하지 못했습니다. "
             "플래그는 그대로 씁니다(문제가 있으면 첫 질문에서 곧바로 드러납니다).")
        return True
    if _STRICT_MCP_FLAG in helptext:
        return True
    _RUNTIME_SPECS["claude"]["argv"] = [a for a in spec_argv if a != _STRICT_MCP_FLAG]
    _log(f"경고: 이 claude 는 {_STRICT_MCP_FLAG} 를 지원하지 않습니다(구버전). 플래그를 빼고 "
         "진행하지만, 이 머신에 설정된 MCP 서버가 그대로 붙습니다 — 같은 서비스의 상주 토큰이 "
         "만료돼 있으면 조사가 401 로 막힐 수 있습니다. claude 를 업데이트하는 것을 권합니다.")
    return False


#: `--append-system-prompt` 지원 여부 캐시. `None` = 아직 확인 안 함.
_system_channel_cache: dict[str, bool] = {}


def system_channel_supported(kind: str, custom: str | None = None,
                             exe: str | None = None) -> bool:
    """이 런타임에서 운영자 지침을 **시스템 채널**로 넘길 수 있는가 (TASK-20260901T140000).

    ## 실패 기본값이 `--strict-mcp-config` 와 **반대**인 이유

    `_ensure_strict_mcp_supported` 는 확인 실패 시 플래그를 **남긴다** — 잘못 남기면 첫
    질문에서 시끄럽게 터져 고칠 수 있고, 잘못 빼면 원 결함이 조용히 돌아오기 때문이다.

    여기는 반대다. 잘못 남기면 unknown option 으로 **모든 질문이 죽고**, 잘못 빼면 종전
    동작(지침을 본문에 싣는다)으로 떨어질 뿐이다 — 오탐 위험은 남지만 서비스는 돈다.
    즉 «드러나는 쪽» 이 아니라 «답이 오는 쪽» 을 고른다. 두 함수의 비대칭은 의도적이다.

    `--cmd`(사용자가 명령을 통째로 준 경우)는 대상이 아니다 — 그 명령에 우리가 플래그를
    얹으면 중복 지정으로 CLI 가 거절할 수 있고, `--cmd` 의 의미도 사라진다.
    """
    if custom or kind != "claude":
        return False
    spec = _RUNTIME_SPECS.get(kind) or {}
    if not spec.get("system"):
        return False
    exe = exe or str((spec.get("argv") or [kind])[0])
    if exe in _system_channel_cache:
        return _system_channel_cache[exe]
    try:
        proc = subprocess.run(_resolve_exe([exe, "--help"]), capture_output=True,
                              text=True, timeout=30)
        helptext = (proc.stdout or "") + (proc.stderr or "")
    except Exception:  # noqa: BLE001  (미설치·타임아웃·권한 — 전부 "확인 못 했다")
        _system_channel_cache[exe] = False
        _log(f"참고: {exe} --help 로 {_APPEND_SYSTEM_FLAG} 지원을 확인하지 못했습니다. "
             "운영자 지침은 종전대로 프롬프트 본문에 싣습니다.")
        return False
    ok = _APPEND_SYSTEM_FLAG in helptext
    _system_channel_cache[exe] = ok
    if not ok:
        _log(f"참고: 이 {exe} 는 {_APPEND_SYSTEM_FLAG} 를 지원하지 않습니다(구버전). 운영자 "
             "지침을 프롬프트 본문에 싣습니다 — 일부 AI 가 이를 인젝션으로 오판할 수 있으니 "
             "업데이트를 권합니다.")
    return ok


def _with_system_prompt(cmd: list[str], kind: str, system: str | None) -> list[str]:
    """조립된 명령에 `--append-system-prompt <지침>` 을 끼운다. 자리는 **프롬프트 바로 앞**.

    프롬프트 뒤에 붙이면 CLI 에 따라 프롬프트의 일부로 먹힌다(`build_cmd` 의 플래그 배치와
    같은 이유). 프롬프트 자리를 못 찾으면 **끼우지 않는다** — 위치를 추측해 넣느니 종전
    동작으로 떨어지는 편이 안전하다(본문 폴백은 `compose_prompt` 가 이미 갖고 있다).
    """
    tmpl = list(((_RUNTIME_SPECS.get(kind) or {}).get("system")) or [])
    if not system or not tmpl or not cmd:
        return cmd
    flags = [a.replace("{system}", system) for a in tmpl]
    # 프롬프트는 `ask_local_ai`/`build_cmd` 가 이미 치환해 넣었으므로 자리표시자가 없다.
    # 마지막 인자가 프롬프트인 것이 모든 런타임 명세의 공통 형태다(`{prompt}` 가 argv 끝).
    return cmd[:-1] + flags + cmd[-1:]


def _child_workdir() -> str | None:
    """자식 AI CLI 를 띄울 **중립 작업 디렉토리** (TASK-20260901T140000).

    ## 왜 필요한가

    `Popen` 은 cwd 를 주지 않으면 러너의 것을 상속한다. 러너를 코드 저장소 안에서 띄운
    사용자는 그 저장소의 `CLAUDE.md`·`AGENTS.md` 와 «코딩 에이전트» 정체성이 얹힌 채로
    질문을 받게 되고, 그러면 「내 역할은 이 저장소의 코딩이지 사내 DB 질의가 아니다」가
    거부 논거가 된다 — 라이브 거부문이 실제로 "저는 지금 `/root` 저장소에서 Claude Code로
    동작 중" 이라고 밝히며 그 논거를 폈다(2026-09-01).

    빈 디렉토리 하나면 그 상속이 끊긴다. 만들지 못하면 `None` 을 돌려 **종전대로** 상속한다
    (작업 디렉토리 때문에 답변 자체를 막지는 않는다).
    """
    path = os.path.join(os.path.expanduser("~"), ".mysql-ai-bridge", "work")
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except Exception:  # noqa: BLE001
        return None


#: `--cmd` 경고를 이미 냈는가 (매 질문마다 같은 줄을 찍지 않는다).
_custom_cmd_warned = False


def _warn_custom_cmd_without_mcp_isolation(argv: list[str]) -> bool:
    """claude 를 부르는 `--cmd` 에 MCP 배제가 없으면 **1회** 경고한다. (경고했으면 True)

    판정은 실행 파일 이름으로만 한다 — 경로(`/usr/local/bin/claude`)로 줄 수도 있어서
    basename 을 본다. 다른 CLI 를 부르는 `--cmd` 는 대상이 아니다(그 CLI 에는 이 플래그가
    없다).
    """
    global _custom_cmd_warned
    if _custom_cmd_warned or _KEEP_MCP or not argv:
        return False
    if os.path.basename(str(argv[0])).lower() not in ("claude", "claude.exe"):
        return False
    if _STRICT_MCP_FLAG in [str(a) for a in argv]:
        return False
    _custom_cmd_warned = True
    _log(f"경고: --cmd 의 claude 명령에 {_STRICT_MCP_FLAG} 가 없습니다. 이 머신에 설정된 MCP "
         "서버(같은 서비스의 상주 토큰 포함)가 그대로 붙어, 만료된 토큰이 조사를 401 로 "
         f"막을 수 있습니다. 명령에 {_STRICT_MCP_FLAG} 를 추가하는 것을 권합니다.")
    return True


def ask_local_ai(kind: str, argv: list[str], prompt: str, custom: str | None,
                 cancel_check=None, model: str | None = None,
                 effort: str | None = None,
                 runtimes: list | None = None,
                 caps: dict | None = None,
                 system: str | None = None,
                 token: str | None = None) -> tuple[bool, str]:
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
        # ⚠ `--cmd` 는 사용자가 명령을 **통째로** 준 것이라 우리가 플래그를 얹지 않는다(얹으면
        #   중복 지정으로 CLI 가 거절한다). 그래서 claude 를 부르는 custom 명령에는 MCP 배제가
        #   빠지고, 그 사용자는 라이브 사고와 **같은 경합**을 그대로 만난다 (codex P1-2).
        #   명령을 자동으로 고치지는 않는다 — 사용자가 준 것을 우리가 바꾸면 `--cmd` 의 의미가
        #   사라진다. 대신 **말한다**. 조용히 놔두면 그 사용자만 원인 모를 재발을 겪는다.
        _warn_custom_cmd_without_mcp_isolation(argv)
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
    # 운영자 지침을 실제 시스템 채널로 (TASK-20260901T140000). 호출측이 지원 여부를 이미
    # 판정해 `system` 을 넘겼을 때만 실린다 — 여기서 다시 판정하면 프롬프트를 만든 판정과
    # 갈릴 수 있고, 그러면 지침이 **두 벌**이거나 **한 벌도 없는** 상태가 된다.
    cmd = _with_system_prompt(cmd, kind, system)
    if _canceled():
        return False, CANCELED
    # 토큰은 **환경변수로** 준다 (TASK-20260901T140000). 프롬프트 본문에 실린 평문 자격증명이
    # 인젝션 오판의 근거 2번이었고, 같은 노출은 `/proc/<pid>/cmdline`·CLI 세션 기록으로도
    # 샜다(`FUNCTION.md` 가 잔여 노출면으로 인정하던 항목). 자식은 이 값을 그대로 상속한다.
    child_env = None
    if token:
        child_env = {**os.environ, "BRIDGE_TOKEN": str(token)}
    return _run_cli_cancelable(cmd, _canceled, cwd=_child_workdir(), env=child_env)


# ── 프롬프트 ─────────────────────────────────────────────────────────────────


def compose_prompt(api: Api, task: dict, system_channel: bool = False) -> str:
    """내 AI 에게 줄 프롬프트. **조사 도구 사용법을 함께 준다** — 그래야 DB 를 실제로 본다.

    `system_channel=True` 이면 운영자 지침 블록을 본문에서 **뺀다** — 그 지침은 호출측이
    `--append-system-prompt` 로 실제 시스템 채널에 싣는다(TASK-20260901T140000).
    """
    # ── 콘솔 작업은 프레이밍을 씌우지 않는다 (TASK-20260831T100000) ────────────────────
    #
    # 아래 대화용 프레이밍("너는 사내 DB 질의 어시스턴트다" · 제목 마커 · 답변 규약)은 콘솔
    # 작업에 전부 해롭다: 서버가 이미 완성된 지시문(형식 요구 포함)을 보냈고, 여기서 덧씌우면
    # **두 지시가 충돌**해 JSON 을 요구했는데 산문이 오거나 끝에 제목 줄이 붙는다.
    #
    # 조사 도구 블록도 붙이지 않는다 — 콘솔 작업의 입력(스키마 골격·기존 설명)은 서버가
    # 프롬프트에 이미 실어 보냈고, 추가 조사는 그 작업의 정의 밖이다.
    if str(task.get("kind") or "chat") == "job":
        return str(task.get("question") or "")
    q = str(task.get("question") or "")
    ctxt = str(task.get("conversation_context") or "")
    sysp = str(task.get("system_prompt") or "")
    scope = task.get("scope") or {}
    atts = task.get("attachments") or []
    parts: list[str] = []
    if sysp and not system_channel:
        # 운영자가 설정한 5단계 지침(전역·제품·역할·계정·개인). **맨 앞**에 둔다 — 뒤에 두면
        # 앞의 지시가 이기고, 그러면 운영자 설정이 사실상 무시된다.
        #
        # ⚠ 문구가 바뀐 이유 (TASK-20260901T140000): 종전 머리말은 「아래 지침을 **시스템
        #   프롬프트로 삼아** 답하라」였다. 사용자 메시지 본문 안에서 자기 역할을 재지정하는
        #   그 문형이 프롬프트 인젝션의 대표 서명과 동형이라, 라이브에서 정상 요청이 인젝션으로
        #   오판돼 답변이 자가중단됐다(거부문 근거 1번). 같은 지침을 **역할 재지정 없이**
        #   출처와 함께 제시한다. `system_channel=True` 인 런타임에서는 이 블록 자체가 빠지고
        #   `--append-system-prompt` 로 나간다(그쪽이 정본, 이건 폴백이다).
        parts += ["── 이 서비스 운영자가 설정한 답변 규칙 (관리 콘솔 설정값) ──", sysp,
                  "── 규칙 끝 ──", ""]
    if scope.get("product_name") or scope.get("datasources"):
        # 어떤 제품·어떤 DB 를 보고 있는지 모르면 엉뚱한 스키마를 찾아 헤맨다.
        who = scope.get("product_name") or ""
        key = scope.get("product_key") or ""
        ds = ", ".join(str(d) for d in (scope.get("datasources") or []))
        parts += [f"대상 제품: {who}" + (f" ({key})" if key else "")
                  + (f" · 데이터소스: {ds}" if ds else ""), ""]
    parts += [
        # ⚠ 「너는 …이다」 라는 역할 **부여**가 아니라, 이 실행이 무엇인지에 대한 **사실**로
        #   적는다 (TASK-20260901T140000). 앞의 것은 본문 속 역할 재지정이라 인젝션 서명과
        #   동형이고, 뒤의 것은 그렇지 않다. 하는 일은 같다.
        "이 요청은 사내 DB 질의다 — 아래 `⟦USER-REQUEST⟧` 블록의 요청에 답하라.",
        "",
        # ⚠ 본문 형태를 **정확히** 준다. 종전 예시는 `task_id` 가 없고 인자를 `arguments` 로
        #   감싸지 않아, 그대로 따르면 400("task_id 가 필요합니다") 또는 "schema_name과
        #   table_name은 필수" 만 돌아왔다 — 러너 경로의 조사가 통째로 실패하는 형태였다
        #   (codex REV-20260828T040000 P1).
        "필요하면 이 도구들을 HTTP 로 직접 호출해 실제 DB 를 조사하라"
        " (POST · JSON 본문 · 헤더에 `Authorization: Bearer $BRIDGE_TOKEN`).",
        # ⚠ 조사 주소의 **출처**를 밝힌다 (TASK-20260901T140000). 밝히지 않으면 「모르는
        #   주소로 자격증명을 실어 보내라」로만 읽히고, 라이브에서 그것이 인젝션 판정의
        #   근거 2번이 됐다. 이 주소는 러너 설정 파일에 있어 **확인 가능한 사실**이다.
        f"  이 주소({api.base})는 당신을 실행한 사람이 자기 머신에서 띄운 브리지 러너의"
        " 설정값(`~/.mysql-ai-bridge/config.json` 의 `base`)이다 — 제3자 주소가 아니다."
        " 의심되면 그 파일을 직접 읽어 대조하라.",
        # ⚠ 아래 토큰이 **유일한** 자격증명이라고 못 박는다. 러너가 부르는 CLI 에 같은 서비스의
        #   MCP 서버가 상주 설정돼 있으면(그 헤더는 이 task 와 무관한 별개 토큰이다) 모델은
        #   프롬프트의 토큰 대신 그 도구를 먼저 집는다 — 그 토큰이 만료돼 있으면 조사가 통째로
        #   401 이 되고, 그 실패가 아래 「승인 요구 금지」가 없으면 승인 요청으로 둔갑한다
        #   (라이브 실측 2026-08-28). 실행 측 배제는 `_RUNTIME_SPECS` 의
        #   `--strict-mcp-config` 가 하고, 이 문장은 그 플래그가 없는 런타임에서의 방어선이다.
        "  이 토큰이 조사의 유일한 자격증명이다 — 다른 경로에 설정된 자격증명(같은 서비스의"
        " 상주 MCP 서버 등)을 쓰지 마라. 그쪽은 이 질문과 무관한 계정일 수 있다.",
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
        # ⚠ 토큰 **값**을 여기 쓰지 않는다 (TASK-20260901T140000). 프롬프트 본문의 평문
        #   자격증명은 (a) 인젝션 판정의 근거가 됐고 (b) argv 로 넘어가 같은 호스트의 다른
        #   사용자가 `/proc/<pid>/cmdline` 으로 볼 수 있었으며 (c) CLI 세션 기록에도 남았다.
        #   자식 프로세스는 러너의 환경변수를 상속하므로 값은 이미 손에 있다.
        "  토큰: 이 프로세스의 환경변수 `BRIDGE_TOKEN` 에 있다"
        " (`printenv BRIDGE_TOKEN` 으로 읽거나, 셸에서 `$BRIDGE_TOKEN` 으로 바로 쓴다).",
        "",
        # 조사 내역은 사용자 화면의 「실행 단계」에 그대로 그려진다. 사유가 없으면 서버가
        # 도구의 일반적 목적으로 채우는데, 그건 *이 질문에서의* 이유가 아니다.
        "`reason` 은 매 호출에 넣어라 — 사용자 화면의 실행 단계에 「어떤 이유로 → 어떤 작업」"
        " 으로 표시된다.",
        "",
        "추측하지 말고 조사한 사실만 쓰라. 확인하지 못한 것은 '미확인' 이라고 밝혀라.",
        "",
        # ⚠ 이 답을 읽는 사람은 **웹 대화창의 사용자**다. 네 실행 환경(러너 머신의 CLI)의 승인
        #   대화에 그 사람은 접근할 수 없고, 애초에 승인할 대상도 없다. 그런데 도구 호출이
        #   실패하면(특히 401) 모델은 그것을 「권한이 없다」로 읽고 **사용자에게 승인을 요청하는
        #   답**을 만든다 — 라이브에서 실제로 그렇게 나갔고, 사용자는 승인할 방법도 이유도 없는
        #   지시를 두 턴 연속 받았다(2026-08-28 제보). 실행 불가능한 지시는 답이 아니다.
        "도구 사용 권한이나 승인을 사용자에게 요구하지 마라 — 이 답을 읽는 사람은 네 실행"
        " 환경의 승인 절차에 접근할 수 없고, 승인할 대상도 없다.",
        "조사 도구가 실패하면(401·403·타임아웃 등) 승인을 요청하지 말고, **무엇이 어떻게"
        " 실패했는지**를 답변에 그대로 적은 뒤 확인한 범위까지 답하라. 재시도·승인 요청으로"
        " 답을 대신하지 마라.",
        "",
        "답변만 출력하라(머리말·맺음말 없이).",
        # 제목 축: 러너는 CLI 의 stdout 만 받으므로 별도 채널이 없다. 마지막 한 줄을 규약으로
        # 삼고 제출 전에 떼어낸다 — 마커가 없으면 답변은 그대로다(파싱 실패가 답을 망치지 않음).
        f"답변의 **맨 마지막 줄**에 `{_TITLE_MARK} <이 대화를 요약한 30자 안팎의 제목>` 을"
        " 한 줄 덧붙여라. 이 줄은 사용자에게 보이지 않고 대화 제목으로만 쓰인다.",
        # 용어 축: 제목 바로 **앞** 줄. 순서를 고정하는 이유는 `split_title` 이 「맨 마지막 줄」을
        # 계약으로 갖고 있고 그 계약에 회귀 가드가 걸려 있어서다(둘 다 마지막을 요구하면 하나가
        # 반드시 진다). 파서는 순서가 뒤바뀐 경우도 흡수하지만, 지시는 한 가지로 준다.
        f"그 제목 줄 **바로 앞 줄**에 `{_GLOSSARY_MARK} <JSON 배열>` 을 한 줄 덧붙여라 —"
        " 이 턴에서 **정의가 분명해진 도메인 용어**만 담는다. 사용자에게 보이지 않는다.",
        '  형식: [{"term":"용어","definition":"1~2문장 한국어 정의",'
        '"tier":"product|org|general","confidence":0.0~1.0}]',
        '  tier — 그 용어가 **어디까지 통용되는가**: "product"=이 제품 고유(테이블·컬럼·코드값·'
        '서비스 내부 개념) / "org"=제품 무관하되 이 조직 고유 관례 / "general"=범용 RDBMS·SQL'
        " 표준 지식(트랜잭션·복합 인덱스·CTE·실행 계획·복제·Online DDL·시점 복구 등).",
        '  confidence — **이 턴이 그 용어를 얼마나 명확히 정의했는가**만 본다. 용어가 얼마나'
        " 일반적인지·중요한지는 이 숫자에 반영하지 마라(그건 tier 가 답한다).",
        f"  한 개념당 표기는 하나만(`멱등성` 과 `멱등성(Idempotency)` 를 함께 넣지 마라)."
        f" 최대 {_GLOSSARY_MAX}개. 담을 것이 없으면 `{_GLOSSARY_MARK} []` 로 적어라.",
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


#: 「사용자에게 도구 승인을 요구하는」 답변의 표지. 프롬프트 계약(compose_prompt)은 **지시**이지
#: 집행이 아니다 — 모델이 따르지 않으면 그 답이 그대로 화면에 간다 (codex P1-4). 여기서 그것을
#: 잡아 **사용자에게 할 일이 없다는 사실을 덧붙인다.**
#:
#: 왜 답변을 지우거나 재생성하지 않는가: 오탐이 있을 수 있고(질문 자체가 결재·승인 도메인일 수
#: 있다), 그때 지우면 정상 답을 잃는다. 재생성은 한 번 더 왕복하는 비용이고 같은 답이 나올
#: 수도 있다. **더하기만 하는 조치**는 오탐 비용이 한 줄이다.
_APPROVAL_REQUEST_PATTERNS: tuple[str, ...] = (
    r"권한\s*(을|이)?\s*승인",
    r"승인\s*(을)?\s*(해\s*주|부탁)",
    r"도구\s*사용\s*(을)?\s*승인",
    r"승인해\s*주(세요|시면|신)",
    r"승인하신\s*(후|뒤)",
    r"approve\s+(the\s+)?(tool|permission)",
    r"grant\s+(me\s+)?(tool\s+)?permission",
)

#: 덧붙이는 한 줄. 「네가 할 일은 없다」를 말한다 — 사용자가 승인 절차를 찾아 헤매는 것이
#: 원래 마찰이었다.
_APPROVAL_REQUEST_NOTE = (
    "> 참고: 위 답변이 도구 사용 승인을 요청하고 있으나 **이 화면에는 승인 절차가 없고,"
    " 승인이 필요하지도 않습니다.** 연결된 AI 가 도구 호출 실패(대개 인증 만료)를 권한 문제로"
    " 잘못 해석한 것입니다 — 사용자가 하실 일은 없습니다. 계속 반복되면 러너를 재기동해"
    " 주세요."
)


def flag_approval_request(answer: str) -> bool:
    """답변이 사용자에게 도구 승인을 요구하는가."""
    body = str(answer or "")
    return any(re.search(p, body, re.IGNORECASE) for p in _APPROVAL_REQUEST_PATTERNS)


def annotate_approval_request(answer: str) -> tuple[str, bool]:
    """승인 요구가 감지되면 안내 한 줄을 덧붙인다. `(본문, 감지여부)`.

    ⚠ **제목 분리 뒤에** 부른다 — 앞에서 부르면 이 줄이 마지막이 되어 제목 규약 위치를 밀어낸다
    (같은 함정을 `unmet` 고지에서 이미 겪었다).
    """
    if not flag_approval_request(answer):
        return answer, False
    return (str(answer or "").rstrip() + "\n\n" + _APPROVAL_REQUEST_NOTE), True


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


def split_glossary(answer: str) -> "tuple[str, list]":
    """답변에서 `#GLOSSARY:` 마지막 줄을 떼어 `(본문, 후보목록)` 으로 가른다.

    `split_title` 과 같은 계약: 마커가 없거나 JSON 이 깨졌으면 **본문을 손대지 않고** 빈 목록을
    돌려준다. 규약을 모르는 런타임이나 잘못 만든 JSON 이 답변을 상하게 하면 안 된다 — 용어
    수집은 보조물이고 답변이 본체다.

    떼어낸 뒤 본문이 비면 포기한다(제목 규약과 동일 이유: 빈 답변은 서버가 400 으로 거절한다).
    """
    body = str(answer or "")
    lines = body.rstrip().split("\n")
    if not lines:
        return body, []
    tail = lines[-1].strip()
    if not tail.upper().startswith(_GLOSSARY_MARK.upper()):
        return body, []
    rest = "\n".join(lines[:-1]).rstrip()
    if not rest:
        return body, []
    raw = tail[len(_GLOSSARY_MARK):].strip().strip("`").strip()
    try:
        parsed = json.loads(raw) if raw else []
    except Exception:
        # 형식을 못 지킨 것은 그 AI 의 사정이고, 그 대가를 사용자 답변이 치르게 하지 않는다.
        # 다만 줄은 떼어낸다 — 남기면 화면에 `#GLOSSARY: [...` 가 그대로 보인다.
        return rest, []
    if not isinstance(parsed, list):
        return rest, []
    return rest, parsed[:_GLOSSARY_MAX]
# ── 자가 검증 (TASK-20260901T110000) ─────────────────────────────────────────
#
# 답변을 내보내기 전에 **같은 AI 에게 검증자 역할로 한 번 더** 묻는다. 전환 전에는 서버가
# 이 일을 했고(`modules/redteam.py`), 게이트가 닫힌 뒤 아무도 하지 않게 됐다 — 그런데
# 관리 콘솔은 여전히 "본인 AI 가 검증한다" 고 말하고 있었다.
#
# **축·형식은 서버가 준다**(`claim_request` 응답의 `self_review.instruction`). 여기에 적어
# 두면 규약을 고칠 때마다 전 사용자가 재설치해야 하고, 재설치하지 않은 러너는 낡은 축의
# 판정을 같은 컬럼에 쓴다.


def run_self_review(directive: dict, draft: str, kind: str, argv: list[str],
                    custom: str | None, cancel_check=None,
                    model: str | None = None, effort: str | None = None,
                    runtimes: list | None = None, caps: dict | None = None) -> dict | None:
    """초안을 자기 AI 에게 되물어 5축 판정을 받는다. 실패·미수행이면 `None`.

    **답변을 만든 것과 같은 (런타임·모델·등급)** 으로 묻는다. 더 싼 모델로 검증하면 그
    검증은 답변을 만든 사고를 따라가지 못하고, 따라가지 못하는 검증은 표면적인 지적만 낸다
    (서버 시절에도 리뷰어를 별도 저비용 모델로 두었을 때 같은 성질이 관측됐다).

    ⚠ **실패를 위로 던지지 않는다.** 검증은 관측이고 답변은 사용자의 것이다 — 검증이
    실패했다고 이미 만들어 둔 답을 버리면, 관측을 위해 서비스를 끊는 셈이 된다.
    """
    if not isinstance(directive, dict) or not directive.get("enabled"):
        return None
    instruction = str(directive.get("instruction") or "")
    slot = str(directive.get("draft_slot") or "")
    if not instruction or not slot or slot not in instruction:
        # 서버가 준 지시문에 초안 자리가 없다 = 계약이 어긋났다. 지어내서 이어 붙이면
        # 검증자가 무엇을 검증하는지 모르는 채로 답한다.
        _log("자가 검증: 서버 지시문에 초안 자리가 없어 건너뜁니다.")
        return None
    if callable(cancel_check) and cancel_check():
        return None
    t0 = time.time()
    ok, raw = ask_local_ai(kind, argv, instruction.replace(slot, draft), custom,
                           cancel_check, model=model, effort=effort,
                           runtimes=runtimes, caps=caps)
    if not ok or raw == CANCELED or not str(raw or "").strip():
        return None
    # **파싱은 서버가 한다.** 여기서 JSON 을 뜯어 스키마를 강제하면 그 스키마가 러너에
    # 박히고, 서버의 것과 갈리는 순간 어느 쪽이 정본인지 알 수 없어진다. 러너는 원문을
    # 그대로 나른다 — 서버의 `self_review.sanitize` 가 형태를 못 갖춘 응답을 버린다.
    return {
        "raw": str(raw),
        "latency_ms": int((time.time() - t0) * 1000),
        # 무엇으로 검증했는지. 콘솔이 「답변 모델 ≠ 검증 모델」을 구분해야 할 날을 위해
        # 지금 남긴다(지금은 같지만, 같다는 사실도 기록되어야 확인할 수 있다).
        "model": model or "",
        "reasoning_level": effort or "",
    }


# ── 한 건 처리 ───────────────────────────────────────────────────────────────


def handle_one(api: Api, task_id: str, claimed: dict, kind: str, argv: list[str],
               custom: str | None, cancels: "CancelRegistry | None" = None,
               runtimes: list | None = None, caps: dict | None = None,
               self_review: bool = True) -> bool:
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
        if _offered and (_known or _learned) and _which_ai(want_runtime):
            run_kind = want_runtime
            run_argv = list(_known or _learned)
        else:
            unmet.append(f"런타임 {want_runtime}")

    # 반영하지 못하는 지정을 **조용히 버리지 않는다**(codex P1-4). 같은 계정에 러너가 여럿이면
    # 목록을 신고한 러너와 질문을 가져간 러너가 다를 수 있고, 그때 사용자는 자기가 고른 것이
    # 적용됐다고 믿는다. 무엇이 반영되지 않았는지는 답변에 적어 사용자가 알게 한다.
    _models, _efforts = offered_options(runtimes, run_kind)
    # ⚠ 목록에 있는 것만으로는 부족하다 — **그 값을 넘길 플래그가 있어야** 인자가 된다
    #   (codex P1-5). 표 밖 CLI 가 모델 목록만 신고하고 `model_flag` 를 못 주면 `build_cmd`
    #   는 모델 인자를 붙이지 않는데, 목록 대조만 보면 `unmet` 이 비어 "반영됐다" 고 말하게
    #   된다. 그 고지는 거짓이고, 사용자는 고르지 않은 기본 모델의 답을 자기가 고른 모델의
    #   답으로 읽는다. 플래그 출처는 `build_cmd` 와 같은 규칙(로컬 caps → 내장 표)이다.
    _spec = _RUNTIME_SPECS.get(run_kind) or {}
    _local = (caps or {}).get(run_kind) or {}
    _model_flag = _local.get("model") if _local.get("model") is not None else _spec.get("model")
    _effort_flag = _local.get("effort") if _local.get("effort") is not None else _spec.get("effort")
    _model_ok = bool(want_model) and bool(_model_flag) and any(
        str(o.get("value")) == want_model for o in _models)
    _effort_ok = bool(want_effort) and bool(_effort_flag) and any(
        str(o.get("value")) == want_effort for o in _efforts)
    if want_model and not _model_ok:
        unmet.append(f"모델 {want_model}")
    if want_effort and not _effort_ok:
        unmet.append(f"추론등급 {want_effort}")

    # 운영자 지침을 실제 시스템 채널로 보낼 수 있는가 (TASK-20260901T140000).
    # **한 번만 판정해 두 곳에 쓴다** — 프롬프트 조립과 명령 조립이 각자 판정하면 지침이
    # 두 벌이 되거나(본문 + 플래그) 한 벌도 없는 상태가 된다.
    # 콘솔 작업(`kind='job'`)은 서버가 완성된 지시문을 보내므로 운영자 지침 자체가 없다.
    _sysp = str(claimed.get("system_prompt") or "")
    _use_sys_channel = bool(_sysp) and system_channel_supported(run_kind, custom)
    prompt = compose_prompt(api, {**claimed, "task_id": task_id},
                            system_channel=_use_sys_channel)
    # 이 질문 한 건의 **일생**을 같은 키(`task`)로 묶는다 (TASK-20260901T163000). 동시 처리에서
    # 줄이 인터리브되어도 `task=` 로 걸러내면 한 건의 흐름이 그대로 복원되고, 그 키는 서버
    # DB(`BridgeTasks.TaskId`)·웹 화면과도 같은 값이라 3자 대조가 된다.
    _t_task = time.monotonic()
    log_event(_EV_TASK_DISPATCH, "내 AI 에게 전달", task=task_id, runtime=run_kind,
              model=want_model, effort=want_effort,
              kind=str(claimed.get("kind") or "conversation"),
              conv=str(claimed.get("conversation_id") or "") or None,
              prompt_chars=len(prompt), sys_channel=_use_sys_channel)
    if unmet:
        # 「고른 값이 반영되지 않았다」는 **답변에도 적히지만 로그에도 남겨야** 한다 — 답변은
        # 사용자가 지우면 사라지고, 같은 계정에 러너가 여럿일 때의 재현 조사는 로그로 한다.
        log_event(_EV_TASK_UNMET, "요청한 지정을 반영하지 못했다", level="WARN",
                  task=task_id, runtime=run_kind, unmet=list(unmet))
    ok, answer = ask_local_ai(run_kind, run_argv, prompt, custom, _canceled,
                              model=want_model, effort=want_effort, runtimes=runtimes,
                              caps=caps,
                              system=(_sysp if _use_sys_channel else None),
                              token=api.token)
    if answer == CANCELED:
        # 사용자가 취소했다. **제출하지 않는다** — 서버도 409 로 거절하지만, 여기서 멈추는 것이
        # 토큰과 왕복을 아끼는 지점이다.
        log_event(_EV_TASK_CANCEL, "사용자가 취소했다 — 제출하지 않는다", level="WARN",
                  task=task_id, runtime=run_kind, at="during_ai",
                  dur_ms=int((time.monotonic() - _t_task) * 1000))
        return False
    if not ok or not answer.strip():
        # 「AI 가 실패했다」와 「AI 가 빈 답을 냈다」는 사용자에게는 같아 보이지만 원인이 다르다
        # (전자는 exit≠0 · 후자는 exit=0 에 출력 0바이트 — 프롬프트 거절이 대표적이다).
        log_event("task.answer.degraded", "실패·빈 응답을 안내문으로 대체해 제출한다",
                  level="WARN", task=task_id, runtime=run_kind,
                  reason=("ai_failed" if not ok else "empty_answer"),
                  dur_ms=int((time.monotonic() - _t_task) * 1000))
        # 실패해도 **답을 제출한다** — 제출하지 않으면 사용자 화면은 30분간 대기 말풍선인 채로
        # 남고, 무엇이 잘못됐는지 아무도 모른다. 실패를 말하는 것이 침묵보다 낫다.
        answer = (answer or "내 AI 가 빈 응답을 돌려주었습니다.") + \
            "\n\n(이 답변은 연결된 AI 에서 생성하지 못해 자동 안내로 대체된 것입니다.)"

    # 답을 만드는 동안 취소됐을 수 있다 — 제출 **직전**에 한 번 더 본다.
    # 제목 분리보다 **앞**에 둔다: 어차피 버릴 답이면 가공할 이유가 없다.
    if _canceled():
        log_event(_EV_TASK_CANCEL, "답변 완료 직전에 취소됨 — 제출하지 않는다", level="WARN",
                  task=task_id, runtime=run_kind, at="before_submit",
                  dur_ms=int((time.monotonic() - _t_task) * 1000))
        return False

    # 제목·용어 줄은 답변에서 떼어 별도 필드로 보낸다 — 본문에 남기면 사용자가 규약 문자열을 본다.
    #
    # 순서: title → glossary → title 한 번 더. 지시는 「용어 줄, 그 다음 제목 줄」 하나로 주지만,
    # 두 줄을 뒤바꿔 내는 런타임이 있으면 첫 `split_title` 이 실패하고 그 줄이 본문에 남는다.
    # 두 번째 호출은 그 경우를 흡수한다(마커가 없으면 no-op 이라 정상 경로에는 무영향).
    answer, title = split_title(answer)
    answer, glossary_terms = split_glossary(answer)
    if not title:
        answer, title = split_title(answer)

    # 반영하지 못한 지정을 **밝힌다**(codex REV-20260828T170000 P1-4). 조용히 기본값으로
    # 답하면 사용자는 자기가 고른 모델로 답이 나온 줄 안다 — 그 오해는 화면 어디에도 드러나지
    # 않는다. 같은 계정에 러너가 여럿일 때(목록을 신고한 러너 ≠ 질문을 가져간 러너) 실제로
    # 발생한다. 제목 분리 **뒤**에 붙인다: 앞에 붙이면 이 줄이 제목 규약 위치를 밀어낸다.
    #
    # ⚠ **반영된 지정은 답변 본문에 쓰지 않는다** (사용자 결정 2026-08-31).
    #
    #   잠깐 넣었다가 뺐다. 넣은 이유는 "무엇으로 답했는지 확인할 수 없다" 였는데, 그 확인
    #   수단은 **선택기 라벨**이면 충분하다 — 그리고 그쪽이 답변을 읽기 전에, 다음 질문을
    #   보내기 전에 보인다. 답변마다 붙는 한 줄은 정상 경로에서 아무것도 더하지 않으면서
    #   본문을 밀어낸다. (라벨이 러너 어휘를 표시하지 못하던 결함은 같은 cycle 에서 고쳤다.)
    #
    #   **미반영 고지는 남긴다** — 그건 다른 사실이다. "고른 값이 반영되지 않았다" 는 화면
    #   어디에도 드러나지 않으므로 답변이 유일한 통로다.
    if unmet:
        answer = (answer or "") + (
            f"\n\n> 참고: 요청하신 {' · '.join(unmet)} 은(는) 이 AI 에서 쓸 수 없어"
            " 기본 설정으로 답했습니다."
        )

    # 프롬프트 계약은 지시이지 집행이 아니다 — 따르지 않은 답이 그대로 화면에 가는 것을 여기서
    # 막는다 (codex P1-4). 답을 지우지 않고 「할 일이 없다」를 덧붙인다. 제목 분리 **뒤**다.
    answer, _asked_approval = annotate_approval_request(answer)
    if _asked_approval:
        log_event("task.answer.approval_request",
                  "답변이 사용자에게 도구 승인을 요구했다 — 안내를 덧붙였다. "
                  "(연결된 AI 가 도구 호출 실패를 권한 문제로 오해한 신호. "
                  f"claude 라면 {_STRICT_MCP_FLAG} 적용 여부와 토큰 유효성을 확인하라)",
                  level="WARN", task=task_id, runtime=run_kind)

    # 자가 검증 — 제출 **직전**, 취소 검사 뒤. 여기 두는 이유: 취소된 답을 검증하는 것은
    # 남의 계정 토큰을 이유 없이 태우는 일이고, 제출 뒤에 두면 검증 결과를 실을 자리가 없다.
    #
    # ⚠ 검증은 답변을 **바꾸지 않는다.** 서버 시절에는 BLOCK 결함이면 초안을 고쳐 다시
    #   물었지만(`REDTEAM_MAX_REVISIONS`), 그 반복은 개인 머신 AI 호출을 몇 배로 늘린다 —
    #   남의 자원이라 우리가 임의로 결정할 축이 아니다. 지금은 **판정을 기록**하고 그
    #   판정을 콘솔이 보이게 하는 데까지다(수정 반복은 별도 결정 사항).
    review = None
    if self_review:
        review = run_self_review(claimed.get("self_review") or {}, answer, run_kind, run_argv,
                                 custom, _canceled, model=want_model, effort=want_effort,
                                 runtimes=runtimes, caps=caps)
        if review:
            log_event(_EV_TASK_REVIEW, "자가 검증 완료 — 제출에 동봉", task=task_id,
                      dur_ms=review["latency_ms"], model=review.get("model"),
                      effort=review.get("reasoning_level"))

    payload = {"task_id": task_id, "answer": answer, "source_tasks": [task_id]}
    if title:
        payload["title"] = title
    if glossary_terms:
        # 빈 목록은 싣지 않는다 — 서버가 `None` 과 `[]` 를 구분해 「규약을 모르는 러너」와
        # 「담을 것이 없던 턴」을 로그에서 가를 수 있게 한다.
        payload["glossary_terms"] = glossary_terms
    if review:
        # 서버 계약: `review.raw` 는 검증자가 낸 원문이다(우리가 뜯지 않는다).
        payload["review"] = {
            "raw": review["raw"], "latency_ms": review["latency_ms"],
            "model": review["model"], "reasoning_level": review["reasoning_level"],
        }
    res = api.call("submit_answer", payload, timeout=120.0)
    if res.get("_http") == 409:
        # 취소 신호를 못 본 채 여기까지 왔다(서버가 마지막 관문). 정상 흐름이다.
        log_event(_EV_TASK_SUBMIT_REJECT, "서버가 제출을 거절했다(취소된 요청) — 버린다",
                  level="WARN", task=task_id, http=409,
                  dur_ms=int((time.monotonic() - _t_task) * 1000))
        return False
    if res.get("_failed"):
        # ⚠ 연결 실패는 `_http == 0` 이라 아래 진위 검사에 걸리지 않는다 (codex P2-2).
        #   그대로 두면 **저장 여부를 모르는데 "제출 완료" 라고 기록**한다. 답변은 이미 만들어
        #   놓았으므로 한 번 더 시도할 값어치가 있다 — 서버의 `SubmittedAt IS NULL` 가드가
        #   중복 제출을 409 로 막으므로 재시도는 안전하다(멱등).
        log_event(_EV_TASK_SUBMIT_RETRY, "제출 중 연결 실패 — 한 번 더 시도한다",
                  level="WARN", task=task_id, attempt=1, http=0,
                  detail=str(res.get("error") or ""))
        time.sleep(_RECONNECT_BACKOFF_START)
        res = api.call("submit_answer", payload, timeout=120.0)
        if res.get("_failed") or res.get("_http"):
            log_event(_EV_TASK_SUBMIT_FAIL,
                      "이 답변은 전달되지 않았다 — lease 만료 뒤 다시 제안된다",
                      level="ERROR", task=task_id, attempt=2,
                      http=res.get("_http"), detail=str(res.get("error") or ""),
                      answer_chars=len(answer or ""),
                      dur_ms=int((time.monotonic() - _t_task) * 1000))
            return False
    if res.get("_http"):
        log_event(_EV_TASK_SUBMIT_FAIL, "제출 실패", level="ERROR", task=task_id,
                  attempt=1, http=res.get("_http"), detail=str(res.get("error") or ""),
                  answer_chars=len(answer or ""),
                  dur_ms=int((time.monotonic() - _t_task) * 1000))
        return False
    _gl = res.get("glossary") or {}
    # 한 건의 **종결**. `dur_ms` 는 전달→제출 완료 전체이고, 그 안의 AI 호출 몫은 `ai.ok`
    # 줄이 따로 갖고 있다 — 두 값의 차가 곧 러너·서버가 쓴 시간이다.
    log_event(_EV_TASK_SUBMIT_OK, "제출 완료", task=task_id, runtime=run_kind,
              delivered=bool(res.get("delivered_to_conversation")),
              answer_chars=len(answer or ""), has_title=bool(title),
              glossary=(_gl or None),
              dur_ms=int((time.monotonic() - _t_task) * 1000))
    return True


# ── 메인 ─────────────────────────────────────────────────────────────────────


#: 종료 시 자기 점유를 놓아 줄 대상. 전역인 이유: `atexit`·시그널 핸들러는 인자를 받지 않고,
#: main 의 지역 변수에 닿을 방법이 없다.
_ACTIVE_API: "Api | None" = None


def release_own_claims_on_exit() -> None:
    """이 프로세스가 종료한다 — **붙들고 있던 질문을 대기열로 돌려놓는다**.

    ## 왜 필요한가 (TASK-20260901T140000)

    다음 기동의 사망 신고(`_PREV_RUNNER_INSTANCE`)만으로도 회수는 된다. 그러나 그것은 **누군가
    러너를 다시 켤 때까지** 기다린다는 뜻이고, 그 사이 질문은 lease(30분)가 끝날 때까지 아무
    러너에게도 보이지 않는다 — 같은 계정에 **다른 머신의 러너가 붙어 있어도** 그렇다.
    종료하는 쪽이 스스로 놓으면 그 창이 사라진다.

    ## 왜 best-effort 인가

    `SIGKILL`·전원 차단·크래시에서는 이 코드가 돌지 않는다. 그것이 바로 다음 기동의 사망
    신고가 필요한 이유다 — 두 경로는 **대체가 아니라 보완**이다. 여기서 실패해도 조용히
    넘어간다: 종료 중에 예외를 올리면 사용자가 보는 것은 회수 실패가 아니라 종료 스택이다.

    타임아웃을 짧게 두는 이유: 서버가 죽어 있으면 종료가 그만큼 늦어지고, 사용자는 Ctrl+C 가
    먹지 않는다고 읽는다. 5초 안에 못 닿으면 다음 기동의 신고에 맡긴다.
    """
    api = _ACTIVE_API
    if api is None or not _RUNNER_INSTANCE:
        return
    try:
        # `runtimes=None` 으로 부른다 — 종료하면서 능력 목록을 다시 신고할 이유가 없고,
        # `[]` 를 보내면 서버가 "고를 것 없음" 으로 읽어 화면의 모델 목록을 지운다.
        res = api.heartbeat(None, timeout=5.0, released_instances=[_RUNNER_INSTANCE])
        n = len(res.get("released_claims") or [])
        if n:
            _log(f"종료 — 처리 중이던 질문 {n}건을 대기열로 돌려놨습니다"
                 f"(러너를 다시 켜면 곧바로 이어서 처리합니다).")
    except Exception:  # noqa: BLE001  (종료 경로 — 무엇이든 조용히 넘어간다)
        pass


#: `run.stop` 을 두 번 찍지 않기 위한 빗장. 종료 경로가 여럿이라(정상 반환·Ctrl+C·SIGTERM →
#: atexit) 각자 찍으면 원장에 종료가 두 번 나오고, 그러면 「러너가 두 번 죽었나」로 읽힌다.
_RUN_STOPPED = threading.Event()

#: **같은 계정**에 더 나중에 연결된 러너가 붙어서, 이 러너가 물러나야 한다는 서버 판정
#: (TASK-20260901T183000, 사용자 결정 2026-09-01 — 「연결된 계정에서 다른 신규 러너에 연결되는
#: 부분이 확인된다면 오래된 러너는 프로세스를 종료 … 계정이 다를 경우는 예외」).
#:
#: 왜 Event 인가: 이 사실을 아는 것은 하트비트 스레드이고, 물러날 수 있는 것은 대기 루프다
#: (진행 중 작업을 마치고 끝내는 절차가 거기 있다). 스레드에서 곧바로 죽이면 처리 중이던
#: 답변이 통째로 사라진다 — 로그아웃 종료가 이미 같은 이유로 `shutdown_after_drain` 을 쓴다.
#:
#: ⚠ **계정이 다르면 이 신호는 오지 않는다.** 서버 판정이 `AccountId` 로 묶여 있어, 한 머신에서
#:   서로 다른 계정으로 러너를 여럿 띄우는 구조는 그대로 허용된다(사용자 결정 2026-09-01).
_SUPERSEDED = threading.Event()


def _log_run_stop(reason: str = "exit") -> None:
    """이 세션이 **무엇을 했는지** 한 줄로 닫는다. 여러 번 불러도 한 번만 남는다.

    집계는 `log_event` 가 사건 코드별로 모아 둔 것을 그대로 쓴다 — 따로 세지 않으므로
    새 사건이 생겨도 요약에서 빠지지 않는다. 사람 줄에는 핵심 셋(처리·실패·오류)만,
    원장에는 전체 표를 싣는다.
    """
    if _RUN_STOPPED.is_set():
        return
    _RUN_STOPPED.set()
    tally = {k: v for k, v in _STATS.items() if not k.startswith("_")}
    log_event(_EV_RUN_STOP, "브리지 러너 종료", reason=reason,
              uptime_sec=int(time.monotonic() - _RUN_T0),
              submitted=_STATS.get(_EV_TASK_SUBMIT_OK, 0),
              failed=(_STATS.get(_EV_TASK_SUBMIT_FAIL, 0) + _STATS.get(_EV_AI_FAIL, 0)),
              errors=_STATS.get("_errors", 0),
              tally=tally)


def _arm_exit_release(api: Api) -> None:
    """종료 경로 세 갈래(정상 반환·Ctrl+C·SIGTERM)를 모두 자기 해제로 모은다.

    `atexit` 는 정상 종료와 `sys.exit`·전파된 `KeyboardInterrupt` 를 덮지만 **시그널은 덮지
    못한다**. 설치 스크립트가 옛 러너를 정리할 때 쓰는 것이 정확히 그 시그널이므로(재설치가
    이번 결함의 발단이었다), `SIGTERM` 을 `SystemExit` 으로 바꿔 같은 출구로 보낸다.
    """
    global _ACTIVE_API
    _ACTIVE_API = api
    # 종료 요약을 **같은 출구**에 건다 (TASK-20260901T163000). 종전에는 러너가 사라진 뒤
    # 로그의 마지막 줄이 무엇이든 그것이 마지막 사건인지, 그냥 거기서 잘린 것인지 알 수
    # 없었다 — 87분 고아 사고에서 「12:47 종료」를 다른 증거로 짜맞춰야 했던 이유다.
    #
    # ⚠ 등록 순서가 곧 **역순 실행 순서**다: atexit 는 나중에 등록한 것을 먼저 부른다.
    #   그래서 요약을 **먼저** 등록해야 그것이 **마지막에** 실행되어, 자기 점유 해제까지
    #   끝난 뒤의 진짜 마지막 줄이 된다.
    #
    #   라이브 실측(2026-09-01, 배포본 a17b8f5ea7f6)에서 반대로 걸려 있었다 — `--check`
    #   종료 로그가 `run.stop`(seq 4) → `api.fail`(seq 5, 해제 호출의 401) 순으로 남았다.
    #   요약이 마지막 줄이 아니면 그 요약은 **해제 결과를 세지 못하고**, 「여기서 끝났다」의
    #   표지 구실도 못 한다(뒤에 줄이 더 있으니 잘린 것과 구분되지 않는다). 종료 요약의
    #   두 가지 쓸모가 동시에 죽는, 한 줄짜리 순서 결함이었다.
    atexit.register(_log_run_stop)
    atexit.register(release_own_claims_on_exit)
    try:
        import signal as _signal

        def _term(_signum, _frame):  # noqa: ANN001
            raise SystemExit(0)

        _signal.signal(_signal.SIGTERM, _term)
    except Exception:  # noqa: BLE001
        # 시그널을 못 다는 환경(비-메인 스레드·플랫폼 차이)에서도 나머지는 그대로 동작한다.
        pass


def start_heartbeat(api: Api, stop: threading.Event,
                    runtimes: list | None = None,
                    batch_override: "bool | None" = None) -> threading.Thread:
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
    _stale_said = False
    #: 연속 실패 횟수. 리스트로 두는 이유는 `nonlocal` 없이 중첩 함수가 고칠 수 있게 하려는
    #: 것이고, **연속** 을 세는 이유는 한 번의 실패(배포 교대·순단)와 진짜 단절이 로그에서
    #: 같은 모양이면 조사할 때 그 둘을 가릴 수 없기 때문이다.
    _hb_fail_streak = [0]
    #: 직전 프로세스의 사망 신고는 **성공할 때까지** 싣는다 (TASK-20260901T140000).
    #: 첫 신호 한 번만 싣고 말면, 그 한 번이 배포 교대·순단에 걸렸을 때 회수가 통째로
    #: 유실되고 사용자는 종전과 같은 30분 공백을 겪는다. 서버 쪽은 멱등이라(이미 놓은 것은
    #: 0행) 반복해도 비용이 없고, 신고가 받아들여지면 그 다음부터 빠진다.
    _pending_release = [_PREV_RUNNER_INSTANCE] if _PREV_RUNNER_INSTANCE else []

    def _loop() -> None:
        nonlocal _stale_said, _pending_release
        interval = _HEARTBEAT_INTERVAL_SEC
        while not stop.is_set():
            # 능력은 **매번** 싣는다. 처음 한 번만 보내면 서버가 재시작하거나 토큰 행이 갈릴 때
            # 화면의 목록이 영영 비고, 그 빈 목록은 "러너가 없다" 와 구분되지 않는다.
            # 서버는 값이 그대로면 쓰지 않으므로(쓰기 증폭 없음) 매번 싣는 비용이 없다.
            res = api.heartbeat(runtimes, released_instances=_pending_release)
            code = res.get("_http")
            if code == 401:
                # 복귀 안내는 여기서 하지 않는다 — 대기 루프 한 곳이 정본이다(두 곳에서
                # 안내하면 문구가 갈리고, 한쪽만 고쳐지는 순간 틀린 안내가 남는다).
                log_event(_EV_HB_UNAUTH,
                          "하트비트 401 — 토큰이 무효해졌습니다(로그아웃 또는 만료). "
                          "곧 대기 루프가 재발급 방법을 안내합니다.",
                          level="ERROR", http=401)
            elif code or res.get("_failed"):
                # 순단·배포 교대. 서버의 판정 창이 주기의 3배라 한 번 놓친 것은 흡수된다.
                # WARN 인 이유: 한 번의 실패는 정상 범위다. **연속** 실패를 세어 원장에
                # 남기므로, 조사할 때 `streak` 로 진짜 단절과 순단을 가를 수 있다.
                _hb_fail_streak[0] += 1
                log_event(_EV_HB_FAIL, "하트비트 실패", level="WARN", http=code,
                          streak=_hb_fail_streak[0],
                          detail=str(res.get("error") or "")[:200])
            else:
                if _hb_fail_streak[0]:
                    # 끊겼다 이어진 사실 자체가 조사 단서다 — 몇 번 만에 돌아왔는지 남긴다.
                    log_event("hb.recovered", "하트비트가 다시 통했다",
                              streak=_hb_fail_streak[0])
                    _hb_fail_streak[0] = 0
                # 사망 신고가 서버에 닿았다 — 다음 신호부터는 싣지 않는다.
                if _pending_release:
                    _released = res.get("released_claims") or []
                    if _released:
                        log_event("task.reclaim",
                                  "직전 러너가 붙들고 있던 질문을 되살렸습니다 — 곧 다시 처리합니다",
                                  count=len(_released), prev_run=_PREV_RUNNER_INSTANCE,
                                  tasks=[str(x) for x in _released[:20]])
                    _pending_release = []
                # 주기는 **서버가 정한다**(P0-J 의 환경 차이 금지와 같은 축). 하한을 두는 것은
                # 서버가 0 을 주는 등의 사고로 신호가 폭주하지 않게 하기 위해서다.
                try:
                    interval = max(_HEARTBEAT_MIN_INTERVAL_SEC,
                                   float(res.get("interval_sec") or interval))
                except (TypeError, ValueError):
                    pass
                # 배포본과 다른 러너로 돌고 있으면 **한 번** 말한다 (2026-08-31).
                #
                # 사용자는 「재설치했는데 목록이 그대로」를 겪었다 — 그날 러너가 세 번 바뀌었고
                # 버전(날짜)은 셋 다 같아서 어디에도 그 사실이 드러나지 않았다. 30초마다
                # 반복하면 소음이라 세션당 한 번만 남긴다(그 뒤로는 화면 쪽 안내가 맡는다).
                # ── 배경 배치 동의를 **웹 토글에서 따라온다** (TASK-20260901T190000) ──────
                #
                # 종전에는 `--batch` 뿐이라 바꾸려면 러너를 다시 띄워야 했다(진행 중 작업이
                # 끊긴다). 이제 서버가 계정별 동의를 하트비트에 실어 주고, 여기서 신고를
                # 갱신한다 — 다음 하트비트에 서버가 그 신고를 저장하면 배급 자격이 바뀐다.
                #
                # ⚠ 키가 **없으면 건드리지 않는다.** 구 서버·기록 실패 응답에는 이 키가 없고,
                # 없는 것을 `False` 로 읽으면 그때마다 동의가 꺼졌다 켜졌다 진동한다.
                if "batch_consent" in res:
                    _want = apply_consent(api.features,
                                          server_consent=res.get("batch_consent"),
                                          local_override=batch_override)
                    if _want != tuple(api.features):
                        api.features = _want
                        # 남의 계정 사용량을 태우는 축이라 **바뀐 사실을 반드시 말한다** —
                        # 조용히 켜지면 사용자는 자기 AI 가 무엇을 하고 있는지 알 수 없다.
                        log_event(
                            "hb.batch_consent",
                            ("배경 작업(인사이트·클러스터 라벨)을 받도록 켜졌습니다 — "
                             "웹의 '내 AI 연결' 토글에서 끌 수 있습니다."
                             if BATCH_FEATURE in _want else
                             "배경 작업을 더 이상 받지 않습니다."),
                            source=("local" if batch_override is not None else "web"),
                            features=list(_want))
                _u = res.get("runner_update") or {}
                # 같은 계정에 최신 러너가 붙었다 — **이 러너는 물러난다** (사용자 결정
                # 2026-09-01). 남아 있으면 선착순 점유로 사용자 답변을 옛 동작으로 되돌린다.
                # 여기서 죽이지 않고 신호만 세운다: 진행 중 작업을 마치고 끝내는 절차는
                # 대기 루프의 `shutdown_after_drain` 한 곳이 정본이다.
                if _u.get("superseded") and not _SUPERSEDED.is_set():
                    _SUPERSEDED.set()
                    log_event(_EV_HB_SUPERSEDED,
                              "같은 계정에 더 나중에 연결된 러너가 있습니다 — 이 러너는 하던 일을 "
                              "마치고 물러납니다(질문은 그 최신 연결이 처리합니다). "
                              "계정이 다른 러너는 영향받지 않습니다.",
                              level="WARN", local_build=_self_build(),
                              peer_build=str(_u.get("superseded_by_build") or "") or None)
                if _u.get("stale_build") and not _stale_said:
                    _stale_said = True
                    log_event(_EV_HB_STALE,
                              "⚠ 실행 중인 러너가 서버 배포본과 다릅니다 — 최신 파일로 다시 받아 "
                              "실행하세요(웹의 '내 AI 연결하기' → 원클릭 명령). "
                              "그 전까지는 옛 동작·옛 모델 목록이 그대로 보입니다.",
                              level="WARN", local_build=_self_build(), ver=AGENT_VERSION,
                              min_version=str(_u.get("min_version") or "") or None)
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
    ap.add_argument("--batch", action="store_true",
                    help="배경 배치 작업(인사이트·클러스터 라벨)까지 받는다 — **이 머신에서 "
                         "명시 허용**. 지정하지 않으면 웹의 '내 AI 연결' 토글을 따른다.")
    ap.add_argument("--no-batch", action="store_true",
                    help="웹 토글이 켜져 있어도 **이 머신에서는** 배경 배치를 받지 않는다. "
                         "그 작업은 당신이 요청한 적 없고 당신 계정의 AI 사용량을 쓴다.")
    ap.add_argument("--no-self-review", action="store_true",
                    help="답변을 내보내기 전 **자기 검증**(5축)을 하지 않는다. 기본은 서버 "
                         "설정을 따라 수행 — 검증은 AI 호출을 한 번 더 쓰므로 "
                         "이 머신에서 끄고 싶을 때 사용한다.")
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
        log_event(_EV_RUN_FATAL, "--base 와 --token 이 필요합니다.", level="FATAL",
                  reason="missing_args")
        return 2
    if not _transport_is_safe(args.base):
        # 토큰이 이 채널로 나간다. loopback 만 예외.
        log_event(_EV_RUN_FATAL, "--base 는 https 여야 합니다(loopback 예외).", level="FATAL",
                  reason="insecure_transport")
        return 2

    api = Api(args.base, args.token, args.ca)
    # 이 프로세스의 신원을 세우고 **직전 프로세스의 id 를 회수**한다 (TASK-20260901T140000).
    # 서버와 첫 말을 트기 전이어야 한다 — 점유(`claim_request`)에 새길 값이 이미 있어야 하고,
    # 직전 id 는 이 호출이 파일을 덮어쓰기 전에만 읽을 수 있다.
    init_runner_instance()
    # ── 세션 머리글 (TASK-20260901T163000) ────────────────────────────────────
    #
    # 사고 조사는 **이 프로세스가 무엇이었는가** 에서 시작한다. 종전 로그로는 그것을 알 수
    # 없어서, 사용자에게 「파이썬 버전이 뭔가요 · 러너를 언제 받으셨나요 · 인자를 어떻게
    # 주셨나요」를 되물어야 했고 그 왕복이 조사 시간의 대부분이었다. 한 줄로 끝낸다.
    #
    # ⚠ 여기 실리는 것에 **비밀은 없다** — 토큰은 물론, `--cmd` 도 사용자가 그 안에 자격증명을
    #   넣었을 수 있어 `_scrub` 를 거친다. 주소는 호스트만 남긴다.
    _host = ""
    try:
        _host = urllib.parse.urlparse(args.base).hostname or ""
    except Exception:  # noqa: BLE001
        _host = ""
    log_event(_EV_RUN_START, "브리지 러너 시작",
              ver=AGENT_VERSION, build=_self_build(),
              run=_RUNNER_INSTANCE, prev_run=_PREV_RUNNER_INSTANCE or None,
              host=_host, ca=bool(args.ca),
              py=".".join(str(x) for x in sys.version_info[:3]),
              platform=sys.platform, pid=os.getpid(),
              workers=workers, max_workers=max_workers,
              ai=(args.ai or "auto"), cmd=(args.cmd or None),
              audit_log=_audit_path(), human_log=(_human_log_path() or "stderr"))
    _arm_exit_release(api)
    # 신고는 **이 실행의 선택**이다(모듈 상수를 바꾸지 않는다). 두 축을 한 번에 조립한다 —
    # 따로 대입하면 나중 대입이 앞의 것을 지운다(`--batch --no-self-review` 조합에서
    # 배치 동의가 사라지던 형태의 결함).
    _feats = list(AGENT_FEATURES)
    # 배치 동의: `--batch`/`--no-batch` 는 **이 머신의 명시 override**, 없으면 웹 토글을 따른다
    # (TASK-20260901T190000). 기동 시점에는 아직 하트비트를 받지 못했으므로 서버 값을 모른다 —
    # 모르면 받지 않는다(fail-closed). 첫 하트비트(≤30초)가 오면 아래 `_loop` 가 갱신한다.
    #
    # 서버는 이 신고를 권한과 함께 확인해야 배급하므로, 동의만으로 남의 조직 작업을
    # 가져가지는 않는다.
    _batch_override = _batch_override_from_args(args)
    _feats = list(apply_consent(_feats, server_consent=False, local_override=_batch_override))
    if getattr(args, "no_self_review", False):
        # 끈 사실을 **신고에서도 지운다** — 신고를 남긴 채 수행만 건너뛰면 콘솔은 이 러너를
        # "검증할 줄 아는데 결과가 없다"(= 통과)로 읽는다. 그 오독이 이 축을 만든 이유다.
        _feats = [f for f in _feats if f != "self_review"]
    api.features = tuple(_feats)

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
        log_event(_EV_CONN_UNAUTH,
                  "토큰이 무효합니다(발급자가 로그아웃했거나 만료). 재발급이 필요합니다.",
                  level="FATAL", http=401, reason="token_invalid")
        return 3

    # ── AI 는 **연결을 확인한 뒤에** 고른다 ──────────────────────────────────────
    #
    # ⚠ 종전에는 이 선택이 위쪽에 있었고, 실패하면 곧장 FATAL 이었다. 그래서 AI 를 못 찾은
    #   사용자는 연결이 멀쩡해도 설치 스크립트로부터 「연결 확인에 실패했습니다. 토큰이
    #   만료됐다면…」 을 받았다 (사용자 제보 2026-09-01) — 토큰도 CA 도 네트워크도 정상인데
    #   그 세 곳을 뒤지게 만드는 오진이다. 연결과 AI 는 다른 축이므로 판정도 따로 낸다.
    #
    #   순서까지 바꾼 이유(codex 적대 리뷰 P2): 「실패해도 안 끝낸다」만으로는 부족하다.
    #   AI 탐색은 파일시스템을 훑으므로 응답 없는 네트워크 드라이브가 PATH 에 있으면 여기서
    #   오래 멈춘다. 그러면 연결 확인이 그만큼 늦어진다 — 확인이 먼저 끝나야 「연결은 된다」를
    #   빨리 말할 수 있다.
    picked = pick_ai(args.ai, args.cmd)

    if args.check:
        # `_http` 만 보면 **연결 실패(0)를 성공으로 읽는다** — 사설 CA 미지정 상태에서 실제로
        # "연결 정상." 을 출력했다. `--check` 가 거짓 안심을 주면 사용자는 러너가 왜 아무 일도
        # 안 하는지 알 수 없다.
        failed = bool(probe.get("_http")) or bool(probe.get("_failed"))
        if failed:
            log_event(_EV_CONN_FAIL, "연결 실패", level="ERROR",
                      http=probe.get("_http"), detail=str(probe.get("error") or ""))
            if probe.get("_failed"):
                _log("  사설 CA 를 쓰는 서버라면 --ca <rootCA.pem> 을 지정하세요.")
            return 1
        log_event(_EV_CONN_OK, "연결 정상.", host=_host)
        # 연결은 됐다. 그런데 **답할 AI 가 없으면** 이 설치는 아직 쓸 수 없다 — 그 사실을
        # 연결 실패로 뭉치지 않고 따로 낸다(설치 스크립트가 exit 4 로 구분해 안내한다).
        if not picked:
            for line in _no_ai_message():
                _log(line)
            return 4
        _log(f"사용할 AI: {picked[0]}")
        return 0

    # 여기서부터는 상주다 — 답할 AI 가 없으면 **시작하지 않는다**. 질문을 가져가 놓고 답하지
    # 못하면 사용자는 「대기 중」 표시만 보며 기다리게 된다(침묵보다 나쁘다).
    if not picked:
        log_event(_EV_RUN_FATAL, "이 컴퓨터에서 쓸 수 있는 AI 를 찾지 못했습니다.",
                  level="FATAL", reason="no_local_ai")
        for line in _no_ai_message():
            _log(line)
        return 4
    kind, argv = picked
    _log(f"AI = {kind}" + (f" ({args.cmd})" if args.cmd else ""))
    # 구버전 claude 는 `--strict-mcp-config` 를 모른다 — 그러면 **모든 질문이** unknown option
    # 으로 실패한다 (codex P2-2). 기동 시 한 번 확인해서, 없으면 플래그를 빼고 그 사실을 크게
    # 말한다. 조용히 빼면 원 결함(만료 MCP 토큰 경합)이 아무 표시 없이 돌아온다.
    _ensure_strict_mcp_supported(kind)

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
            # 출처 표기에서 「내장 기본값」을 뺀다 (2026-08-31). 모델 목록 폴백이 없어졌으므로
            # 여기 오른 런타임은 **전부** 그 AI 가 답한 것(또는 ollama 실조회)이다. 없는 출처를
            # 이름으로 남겨 두면 다음 사람이 그 경로가 아직 있다고 읽는다.
            _by_probe = [n for n, c in caps.items() if (c or {}).get("source") == "probe"]
            _log("  출처: " + ("본인 응답 " + ", ".join(_by_probe) if _by_probe else "실조회")
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
    start_heartbeat(api, heartbeat_stop, runtimes, batch_override=_batch_override)

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

    log_event(_EV_RUN_READY,
              "대기 시작 — 웹에서 질문이 오면 즉시 처리합니다. "
              f"(동시 {workers}건에서 시작 · 수요 시 최대 {max_workers} · "
              f"{int(idle_sec)}초 유휴 시 회수 · Ctrl+C 로 종료)",
              runtime=kind, workers=workers, max_workers=max_workers,
              idle_sec=int(idle_sec),
              startup_ms=int((time.monotonic() - _RUN_T0) * 1000))
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
        # 같은 계정에 최신 러너가 붙었으면 **여기서 물러난다** (TASK-20260901T173000).
        #
        # 대기 호출 **앞**에 둔다: 뒤에 두면 최대 대기시간(수십 초) 동안 새 질문을 자기 쪽으로
        # 끌어와 놓고 물러나게 되고, 그 사이 사용자는 이미 최신 러너를 띄워 두고도 옛 답을
        # 한 번 더 받는다. 종료 절차는 로그아웃과 **같은 한 곳**(`shutdown_after_drain`)이다 —
        # 하던 일은 마치고 나간다.
        if _SUPERSEDED.is_set():
            heartbeat_stop.set()
            idle = shutdown_after_drain(active, cancels)
            log_event(_EV_HB_SUPERSEDED,
                      "더 나중에 연결된 러너에 자리를 넘기고 종료합니다.",
                      level="WARN", idle=idle, active=active.count())
            _log("  이 러너는 더 이상 필요하지 않습니다 — 같은 계정에 더 나중에 연결된")
            _log("  러너가 이미 질문을 처리하고 있습니다(한 계정에는 러너 하나만 남깁니다).")
            return 0
        res = api.call("wait_for_request", {}, timeout=_WAIT_TIMEOUT_SEC)
        code = res.get("_http")
        if code == 401:
            # 연결이 **명시적으로** 해제됐다(로그아웃, 또는 러너가 오래 멈춰 있어 만료).
            # 사용자 요구(2026-08-28): 이때 러너도 안전하게 종료된다 — 다만 하던 일을 먼저
            # 마친다. 종료 절차는 `shutdown_after_drain` 한 곳이 정본이다.
            log_event(_EV_CONN_UNAUTH, "토큰이 무효해졌습니다(로그아웃 또는 만료).",
                      level="ERROR", http=401, active=active.count())
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
            log_event(_EV_CONN_RETRY, "대기 실패 — 잠시 뒤 다시 연결합니다", level="WARN",
                      http=code, backoff_sec=round(backoff, 1),
                      detail=str(res.get("error") or "")[:200])
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
            log_event("conn.draining", "서버 인스턴스 교대 중 — 곧바로 다시 대기합니다.",
                      level="DEBUG")
            time.sleep(_DRAINING_RETRY_FLOOR_SEC)
            continue

        # 취소는 **새 질문과 같은 응답**으로 온다(별도 채널이 아니다 — P0-J 의 즉시 인지가
        # 취소에도 그대로 적용된다). 진행 중인 워커가 다음 확인 시점에 이것을 보고 하차한다.
        fresh = cancels.add_many(res.get("canceled_task_ids") or [])
        if fresh:
            log_event(_EV_TASK_CANCEL, "취소 통보 — 진행 중이면 중단합니다", level="WARN",
                      at="notified", count=len(fresh), tasks=list(fresh))

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
                    log_event("task.stalled",
                              "대기 질문을 연속으로 처리하지 못했습니다(점유 실패 반복). "
                              "서버 상태와 토큰 권한을 확인하세요 — 러너는 계속 대기합니다.",
                              level="ERROR", pending=len(res.get("task_ids") or []),
                              rounds=stalled)
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
        # `runner_instance` — 이 점유를 **어느 프로세스**가 들고 있는지 서버에 새긴다
        # (TASK-20260901T140000). 이 값이 있어야 다음 기동의 사망 신고가 정확히 이 점유만
        # 놓아준다. 없으면 종전 동작(lease 30분 대기)으로 자연 degrade 한다.
        claimed = api.call("claim_request",
                           {"task_id": task_id, "runner_instance": _RUNNER_INSTANCE})
        if claimed.get("_http") == 409:
            log_event(_EV_TASK_CLAIM_SKIP, "이미 다른 세션이 가져갔다 — 건너뜀",
                      level="DEBUG", task=task_id, http=409)
            skip.add(task_id)
            pool.release(sid)
            continue
        if claimed.get("_http") or claimed.get("_failed"):
            # ⚠ `_failed`(연결 실패, `_http == 0`)를 함께 본다 (codex P2-2, 2026-08-28).
            #   앞선 수정은 대기 루프만 고쳤고 여기는 그대로였다 — claim 도중 TCP/TLS 가 끊기면
            #   **빈 응답을 정상 점유로 읽고** AI 를 돌려, 아무도 기다리지 않는 답을 만든다.
            log_event(_EV_TASK_CLAIM_FAIL, "점유 실패", level="WARN", task=task_id,
                      http=claimed.get("_http"),
                      detail=str(claimed.get("error") or "")[:200])
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
                handle_one(api, tid, payload, kind, argv, args.cmd, cancels, runtimes, caps,
                           self_review=not getattr(args, "no_self_review", False))
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
            _log_exc("task.worker.spawn_fail",
                     "워커 스레드를 시작하지 못했습니다 — 자리를 반납하고 건너뜁니다.",
                     e, task=task_id, in_use=pool.in_use)
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
        _log_run_stop("keyboard_interrupt")
        sys.exit(0)
