#!/bin/bash
set -e

echo "🍏 Setting up Llama.cpp for Apple Silicon..."

# 1. Install Python Bindings with Metal Support
echo "📦 Installing llama-cpp-python[server]..."
CMAKE_ARGS="-DGGML_METAL=on" pip3 install llama-cpp-python[server] --force-reinstall --no-cache-dir

# 2. Create models directory
mkdir -p models

# 3. Download Model
# using bartowski/Llama-3.2-3B-Instruct-GGUF (Fast, compatible, open)
MODEL_REPO="bartowski/Llama-3.2-3B-Instruct-GGUF"
MODEL_FILE="Llama-3.2-3B-Instruct-Q4_K_M.gguf"
MODEL_PATH="models/$MODEL_FILE"

echo "⬇️  Downloading $MODEL_FILE..."
python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='$MODEL_REPO', filename='$MODEL_FILE', local_dir='models')"

echo ""
echo "🎉 Setup Complete!"
echo "To start the server:"
echo "./start_llama_server.sh"
