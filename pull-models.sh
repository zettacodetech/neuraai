#!/bin/bash
# Modellarni yuklash (Railway 8GB limitga moslashtirilgan)

echo "=== Ollama modellarni yuklash boshlandi ==="

# 8GB RAM chetıkligi uchun yengil-ro`yhat:
# Har bir model xotirasi: 1.5b~1GB, 3b~2GB, 7-8b~5GB — bir vaqtda 2 tadan yuklaymiz
# MODELS_LIST env berilsa — shu ro'yxat ishlatiladi (2-xizmat uchun)
if [ -n "$MODELS_LIST" ]; then
    MODELS=()
    IFS=' ' read -r -a MODELS <<< "$MODELS_LIST"
else
    MODELS=(
        "llama3.2:3b"          # Yengil chat (tezkor)
        "deepseek-r1:1.5b"     # Yengil reasoning
        "qwen2.5-coder:7b"     # Kod yozish
        "deepseek-r1:7b"       # Reasoning
        "mistral:7b"           # Universal chat
        "llama3.2:1b"          # Ultra yengil tezkorlik
    )
fi

# Railway PORT oralig'ida ishlash uchun OLLAMA_HOST ni set qilish
export OLLAMA_HOST="0.0.0.0:${PORT:-11434}"

# Ollama serverni foreground'da ishga tushirish — Railway healthcheck uchun muhim
ollama serve &
SERVER_PID=$!

echo "Ollama server tayyorlanmoqda..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "Server tayyor!"
        break
    fi
    sleep 1
done

# Modellarni ketma-ket yuklash (parallel emas — OOM oldini olish uchun)
echo "Modellar yuklanmoqda: ${MODELS[*]}"
for model in "${MODELS[@]}"; do
    echo "Yuklanmoqda: $model"
    ollama pull "$model"
done

# Asosiy modelni xotiraga yuklash (warm-up) — Railway proxy 120s limitiga tushmaslik uchun
# OLLAMA_KEEP_ALIVE=-1 bo'lsa model doim xotirada qoladi va javob tez bo'ladi
if [ -n "$WARMUP_MODEL" ]; then
    echo "Warm-up: $WARMUP_MODEL yuklanmoqda..."
    ollama run "$WARMUP_MODEL" "Salom! Qisqa javob ber." || echo "Warm-up muvaffaqiyatsiz (e'tiborsiz)"
fi

echo "=== Barcha modellar yuklandi ==="
ollama list

# Serverni ushlab turish
wait $SERVER_PID