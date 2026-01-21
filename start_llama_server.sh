#!/bin/bash
MODEL="models/Llama-3.2-3B-Instruct-Q4_K_M.gguf"

if [ ! -f "$MODEL" ]; then
    echo "❌ Model not found at $MODEL. Please run ./setup_llama.sh"
    exit 1
fi

echo "🚀 Starting Llama.cpp Server..."
echo "Model: $MODEL"
echo "URL: http://localhost:8000"

# n_gpu_layers -1 = Offload all to GPU (Metal)
# n_ctx 32768 = 32K context window
python3 -m llama_cpp.server \
    --model "$MODEL" \
    --n_gpu_layers -1 \
    --n_ctx 32768 \
    --port 8000 \
    --host 0.0.0.0
