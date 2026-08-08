#!/bin/bash
# Neura CLI kontayner entrypoint'i:
#   1. Ollama serverni ishga tushiradi
#   2. Small model yuklab oladi (CPU, 512MB RAM ga mos)
#   3. Web terminal uchun bash qobig'ini ochiq tutadi
set -e

echo "==> Ollama server boshlanmoqda..."
ollama serve &
OLLAMA_PID=$!

echo "==> Ollama tayyor bo'lishini kutyapman..."
for i in $(seq 1 30); do
  if curl -s -m 2 http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "==> Ollama tayyor!"
    break
  fi
  sleep 2
done

MODEL="${OLLAMA_MODEL:-qwen2.5:0.5b}"
if ! ollama list 2>/dev/null | grep -q "${MODEL}"; then
  echo "==> Model yuklab olinmoqda: ${MODEL} (CPU uchun kichik)..."
  ollama pull "$MODEL" || echo "==> Model yuklab bo'lmadi (keyinroq: neura ollama pull $MODEL)"
fi

echo ""
echo "============================================================"
echo "  Neura AI CLI xizmati tayyor!"
echo "  Terminalda:"
echo "    neura chat                    — suhbat"
echo "    neura fix <fayl>              — kod tuzatish"
echo "    neura opencode / kilo / aider — agentic kodlash"
echo "    neura ollama list             — mahalliy modellar"
echo "============================================================"
echo ""

# Xizmatni ochiq tutish — Railway web terminal shu bilan ishlaydi
export PATH="/app/.clivenv/bin:/root/.opencode/bin:${PATH}"
exec tail -f /dev/null