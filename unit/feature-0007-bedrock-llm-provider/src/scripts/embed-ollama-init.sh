#!/usr/bin/env bash
# ── 전용 임베딩 Ollama 부트스트랩 (titan-embed 실제 백엔드 = bge-m3) ─────────────
#
# 배경: 2026-06-23 chat 을 Anthropic-direct 로 옮기며 AWS 자격을 제거하자 임베딩만
# Bedrock Titan 에 남아 401 실패 → titan-embed alias 를 공유 Ollama(local-llm-edge)
# 의 bge-m3 로 전환했다(litellm_config.yaml). 그런데 공유 Ollama 는
# OLLAMA_MAX_LOADED_MODELS=1 이라 타 서비스 chat 모델이 bge-m3 를 계속 축출 →
# 매 임베딩이 cold 재로딩(실측 27~37s). 준비(init) 단계가 이를 2회 호출 → ~50s.
#
# 해결: bge-m3 만 단독 상주하는 전용 Ollama. MAX_LOADED_MODELS=1 + KEEP_ALIVE=-1
# 이라 자기 자신 외엔 적재할 게 없어 영구 warm(실측 0.33s). 본 스크립트는 데몬
# 기동 → bge-m3 부재 시 1회 pull → 첫 임베딩으로 GPU 적재(warm-up) 까지 수행한다.
set -u

MODEL="${EMBED_OLLAMA_MODEL:-bge-m3}"
PORT="${EMBED_OLLAMA_PORT:-11434}"

ollama serve &
SERVER_PID=$!

# 데몬 준비 대기 (최대 ~60s)
for _ in $(seq 1 60); do
  ollama list >/dev/null 2>&1 && break
  sleep 1
done

# 모델 미보유 시 1회 pull (registry 도달 가능 전제 — 부재 시 경고 후 진행, 요청 시 재시도)
if ! ollama show "$MODEL" >/dev/null 2>&1; then
  echo "[embed-ollama-init] pulling ${MODEL} ..."
  ollama pull "$MODEL" || echo "[embed-ollama-init] WARN: ${MODEL} pull 실패(네트워크?) — 첫 요청 시 재시도"
fi

# warm-up(best-effort): 첫 임베딩으로 모델을 적재해 KEEP_ALIVE=-1 로 영구 상주시킨다.
# ollama 이미지에 curl/wget 이 없어 bash /dev/tcp 로 최소 HTTP POST 를 직접 보낸다.
warmup() {
  local body req
  body="{\"model\":\"${MODEL}\",\"prompt\":\"warmup\"}"
  req="POST /api/embeddings HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: ${#body}\r\nConnection: close\r\n\r\n${body}"
  exec 3<>"/dev/tcp/localhost/${PORT}" 2>/dev/null || return 1
  printf "%b" "$req" >&3
  cat <&3 >/dev/null 2>&1
  exec 3>&- 2>/dev/null || true
}
( sleep 2; warmup && echo "[embed-ollama-init] ${MODEL} warm-up 완료(상주)" \
  || echo "[embed-ollama-init] warm-up skip — 첫 실요청 시 적재" ) &

wait "$SERVER_PID"
