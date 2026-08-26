#!/usr/bin/env bash
#
# smoke-conversation.sh — 배포 후 **실제 대화 경로** 1회 스모크 (feature-0014 deploy 게이트)
#
# 왜 필요한가 (2026-08-26 라이브 장애의 교훈):
#   게이트웨이 의존성(litellm)이 갱신되면서, 몇 달간 무해했던 요청 형태가 provider 400 을 유발해
#   **모든 대화가 실패**했다. 그런데 배포는 성공했고 `/healthz` 는 ok, soak 도 통과했다 — 시스템은
#   자기가 고장난 줄 몰랐고 사용자 신고로만 발견됐다(약 20시간).
#   healthz/soak 는 "프로세스가 살아 있는가" 를 볼 뿐 "대화가 되는가" 를 보지 않는다. 이 스크립트가
#   그 공백을 메운다.
#
# 무엇을 검증하나:
#   ask-worker 컨테이너에서 **대화 답변 경로의 실제 함수**(`agent_core._call_llm`)를 1회 호출한다.
#   기본 모델(`API_DEFAULT_MODEL` alias 해소)로 `reasoning_level=max` 를 태우므로 요청 조립
#   (extra_body·thinking budget·모델 alias 해소)과 게이트웨이 계약이 함께 검증된다.
#   ⚠ 보조 chokepoint(`_openai_chat_completion_with_deadline`)를 부르는 검증으로는 **부족**하다 —
#     2026-08-25 에 그 방식으로 200 을 받고 "해소" 로 오판했다. 대화 경로 함수를 직접 불러야 한다.
#
# 무엇을 검증하지 **않나** (정직 표기 — 적대 리뷰 2026-08-26 지적으로 정정):
#   · **기본 모델 1개만** 호출한다. 기본이 budget 계열(Haiku)이면 adaptive 계열(Sonnet 5·Opus 5)
#     전용 경로 — OAuth **frontier identity 주입**, `output_config.effort`, 그 alias 해소 — 는
#     이 스모크로 **검증되지 않는다**(모델별 사각).
#   · HTTP 대화 진입점(`/api/ask` 인증·라우팅), 워커 큐 claim/lease, system/tool payload, 프런트.
#     edge soak 는 `/healthz` 200 만 보므로 **대화 API 인증·라우팅을 대신 검증하지 않는다.**
#   즉 이 스크립트가 보장하는 것은 **"기본 모델로 LLM 왕복이 성립한다"** 한 점이다.
#
# Usage: bin/smoke-conversation.sh [--service <svc>] [--timeout <sec>] [--gateway-url <url>]
#   --gateway-url: LLM 게이트웨이 base_url override. **교체 전 후보(surge) 검증**에 쓴다 —
#     구 gateway 를 지우기 전에 새 gateway 를 직접 태워, 실패하면 교체를 아예 하지 않는다
#     (그래야 "발견했지만 이미 장애" 가 아니라 무장애로 끝난다).
#   exit 0 = 답변 생성 확인 / exit 1 = 실패(호출자가 교체 중단·롤백 판단)
set -euo pipefail

SVC="ask-worker"
TIMEOUT_SEC="180"
GATEWAY_URL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --service) SVC="$2"; shift 2 ;;
    --timeout) TIMEOUT_SEC="$2"; shift 2 ;;
    --gateway-url) GATEWAY_URL="$2"; shift 2 ;;
    *) echo "[smoke-conv] 알 수 없는 인자: $1" >&2; exit 2 ;;
  esac
done

# compose 파일·`.env` 가 있는 repo 루트에서 돌아야 한다(worktree 등 다른 cwd 에서 호출돼도 동일 동작).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DC="docker compose"
command -v docker >/dev/null 2>&1 || { echo "[smoke-conv] docker 없음 — skip 아님, 실패로 본다" >&2; exit 1; }

echo "[smoke-conv] 대화 경로 스모크 시작 (service=$SVC, timeout=${TIMEOUT_SEC}s${GATEWAY_URL:+, gateway=$GATEWAY_URL})"

# 컨테이너 안에서 대화 답변 경로를 실제로 1회 태운다. 답변 문자열이 비어 있지 않아야 통과.
# stdin 으로 넘겨 quoting 지옥을 피한다(한글 프롬프트 포함).
set +e
# wall-clock 상한을 **실제로** 건다 — 외부 의존 호출이라 무한 대기하면 배포 flock 을 계속 쥔다.
# timeout(1) 의 124 는 "시간 초과" 로 구분해 원인을 남긴다.
OUT="$(timeout "${TIMEOUT_SEC}s" $DC exec -T -w /app \
        -e PYTHONPATH=/app:/app/web \
        -e SMOKE_GATEWAY_URL="$GATEWAY_URL" \
        "$SVC" python3 - <<'PY' 2>&1
import os
import sys

try:
    import agent_core
    from modules.llm import _get_llm_client
    from shared.model_catalog import API_DEFAULT_MODEL, conversation_answer_model
except Exception as exc:  # import 실패도 배포 결함이다 — 조용히 넘기지 않는다
    print(f"SMOKE_FAIL import: {type(exc).__name__}: {exc}")
    sys.exit(1)

# feature-0043 (external-llm-bridge): 서버 계정 LLM 이 잠긴 배포에서는 **이 스모크의 전제가
# 성립하지 않는다.** 여기가 검사하는 것은 "배포본에서 우리 LLM 이 대화 답변을 만드는가" 인데,
# 전환 후 그 경로는 의도적으로 차단돼 있고 답변은 사용자의 개인 머신 AI 가 만든다.
#
# 전제가 사라졌다고 검사를 없애지는 않는다 — **다른 계약으로 바꾼다**: 차단이 실제로 걸려
# 있는지(게이트가 열린 채 배포되지 않았는지)를 단정한다. 그래야 "전환했다고 믿는데 실은
# 계정이 계속 쓰이는" 상태를 이 게이트가 계속 잡는다.
try:
    from shared.llm_gate import server_llm_enabled
except Exception as exc:
    print(f"SMOKE_FAIL import: llm_gate 부재 — {type(exc).__name__}: {exc}")
    sys.exit(1)

if not server_llm_enabled():
    if _get_llm_client(model="claude-haiku-4-chat") is not None:
        print("SMOKE_FAIL gate: 게이트가 차단 상태인데 클라이언트가 생성됐다(차단선 누수)")
        sys.exit(1)
    print("SMOKE_OK gate: 서버 계정 LLM 차단 확인 — 대화 답변은 사용자 개인 AI 가 생성한다")
    print("SMOKE_OK (feature-0043 전환 모드 — 서버 LLM 왕복 검사 비적용)")
    sys.exit(0)

# 대화 기본 모델을 alias 해소해 사용한다(`conversation_answer_model(None)` 은 빈 값이라 쓰면 안 된다).
# 교체 전 후보(surge) 검증: base_url 을 override 해 **그 컨테이너를 직접** 태운다.
# (DNS alias 는 본체와 surge 를 함께 가리켜 대상을 지정할 수 없다.)
_override = (os.environ.get("SMOKE_GATEWAY_URL") or "").strip()
if _override:
    import modules.llm as _llm_mod
    _llm_mod.BEDROCK_GATEWAY_URL = _override   # `from shared.config import *` 로 복사된 모듈 전역
    print(f"SMOKE_TARGET gateway={_override}")

model = conversation_answer_model(API_DEFAULT_MODEL) or API_DEFAULT_MODEL
if not str(model).strip():
    print("SMOKE_FAIL model: 대화 답변 모델이 해소되지 않았다(빈 값)")
    sys.exit(1)
client = _get_llm_client(model=model)
if client is None:
    print("SMOKE_FAIL client: _get_llm_client 가 None (자격증명/엔드포인트 미구성)")
    sys.exit(1)

try:
    # 대화 답변 경로 그대로. reasoning_level 로 thinking/effort 주입까지 태운다.
    resp = agent_core._call_llm(
        client,
        [{"role": "user", "content": "ping"}],
        model,
        reasoning_level="max",
    )
except Exception as exc:
    print(f"SMOKE_FAIL call: model={model} {type(exc).__name__}: {str(exc)[:300]}")
    sys.exit(1)

text = (getattr(resp, "content", None) or "") if resp is not None else ""
if not str(text).strip():
    print(f"SMOKE_FAIL empty: model={model} 응답이 비었다(resp={resp!r})")
    sys.exit(1)

print(f"SMOKE_OK model={model} len={len(str(text))}")
PY
)"
RC=$?
set -e

echo "$OUT" | sed 's/^/[smoke-conv]   /'

if [ "$RC" -eq 124 ]; then
  echo "[smoke-conv] FAIL — ${TIMEOUT_SEC}s 안에 응답이 없었다(wall-clock 초과)." >&2
  exit 1
fi
if [ "$RC" -ne 0 ] || ! printf '%s' "$OUT" | grep -q 'SMOKE_OK'; then
  echo "[smoke-conv] FAIL — 배포본에서 대화 답변이 생성되지 않았다." >&2
  echo "[smoke-conv]   healthz/soak 가 통과해도 대화는 죽어 있을 수 있다(2026-08-26 실제 사례)." >&2
  echo "[smoke-conv]   게이트웨이 로그를 먼저 본다: docker compose logs bedrock-gateway --tail 80" >&2
  exit 1
fi

echo "[smoke-conv] PASS — 배포본 대화 경로에서 답변 생성 확인."
