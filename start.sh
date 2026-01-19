#!/bin/bash
# aiDAPTIV Benchmark - Easy Start Script

set -e

echo "🚀 Starting aiDAPTIV Benchmark Tool..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found."
    exit 1
fi

# Install dependencies if needed
echo "📦 Checking dependencies..."
if ! python3 -c "import requests, psutil, yaml" 2>/dev/null; then
    echo "Installing Python packages..."
    pip3 install -q requests psutil pyyaml pandas matplotlib plotly pynvml fastapi uvicorn
fi

# Check if Ollama is running
echo "🤖 Checking Ollama..."
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo "⚠️  Ollama is not running. Starting Ollama..."
    if command -v ollama &> /dev/null; then
        ollama serve &>/dev/null &
        sleep 3
    else
        echo "❌ Ollama not found."
        exit 1
    fi
fi

# Start the dashboard
echo ""
echo "🖥️  Starting Dashboard..."
python3 sidecar.py &
DASHBOARD_PID=$!
sleep 2

# Open browser
echo "🌐 Opening browser..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:8081
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8081
fi

echo ""
echo "✅ Dashboard is running at http://localhost:8081"
wait $DASHBOARD_PID
