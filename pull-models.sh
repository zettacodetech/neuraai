#!/bin/bash
# Modellarni parall elda yuklash (Railway 48GB GPU da tez)

echo "=== Ollama modellarni yuklash boshlandi ==="

# Asosiy modellar (Railway 48GB GPU da hammasi o'tadi)
MODELS=(
    "deepseek-r1:7b"        # Reasoning (o'rta)
    "llama3.3:8b"           # Universal chat (ChatGPT muqobil)
    "qwen2.5-coder:7b"      # Kod yozish (Codex muqobil)
    "gemma2:9b"             # Google Gemma 2 (multilingual)
    "mistral:7b"            # Tez va samarali
    "phi3:14b"              # Microsoft Phi-3 (kichik lekin kuchli)
    "deepseek-r1:1.5b"      # Yengil reasoning
    "llama3.2:3b"           # Yengil chat
)

# Ollama serverni background da ishga tushirish
ollama serve &
SERVER_PID=$!

# Server tayyorlanishini kutish
echo "Ollama server tayyorlanmoqda..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "Server tayyor!"
        break
    fi
    sleep 1
done

# Modellarni parall yuklash (4 ta bir vaqtda)
echo "Modellar yuklanmoqda: ${MODELS[*]}"
for model in "${MODELS[@]}"; do
    echo "Yuklanmoqda: $model"
    ollama pull "$model" &
    # Maksimal 4 ta parallel yuklash
    while [ $(jobs -r | wc -l) -ge 4 ]; do
        sleep 2
    done
done

# Barcha yuklanishlarini kutish
wait

echo "=== Barcha modellar yuklandi ==="
ollama list

# Serverni davom ettirish
wait $SERVER_PID