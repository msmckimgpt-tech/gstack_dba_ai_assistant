#!/bin/sh
set -eu

export OLLAMA_HOST="${OLLAMA_HOST:-http://local-llm-gateway:11434}"

AUTO_SOURCE_MODEL="${LOCAL_LLM_AUTO_SOURCE_MODEL:-qwen2.5:3b}"
EDGE_SOURCE_MODEL="${LOCAL_LLM_EDGE_SOURCE_MODEL:-qwen2.5:1.5b}"
CORE_SOURCE_MODEL="${LOCAL_LLM_CORE_SOURCE_MODEL:-qwen2.5:3b}"
CODE_SOURCE_MODEL="${LOCAL_LLM_CODE_SOURCE_MODEL:-qwen2.5-coder:3b}"

wait_for_ollama() {
  attempt=0
  until ollama list >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 60 ]; then
      echo "Ollama server did not become ready in time." >&2
      exit 1
    fi
    sleep 2
  done
}

has_model() {
  model_name="$1"
  ollama list 2>/dev/null | awk 'NR > 1 {print $1}' | grep -Fx "$model_name" >/dev/null 2>&1
}

ensure_model() {
  source_model="$1"
  alias_model="$2"

  if ! has_model "$source_model"; then
    echo "Pulling source model: $source_model"
    ollama pull "$source_model"
  fi

  if ! has_model "$alias_model"; then
    echo "Creating alias model: $alias_model -> $source_model"
    ollama cp "$source_model" "$alias_model"
  fi
}

wait_for_ollama
ensure_model "$AUTO_SOURCE_MODEL" "auto"
ensure_model "$EDGE_SOURCE_MODEL" "edge"
ensure_model "$CORE_SOURCE_MODEL" "core"
ensure_model "$CODE_SOURCE_MODEL" "code"

echo "Available Ollama models:"
ollama list
