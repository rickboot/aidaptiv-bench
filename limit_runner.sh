#!/bin/bash
# aiDAPTIV Benchmark - Memory Limit Launcher
# Usage: ./limit_runner.sh [RAM_GB]
# Example: ./limit_runner.sh 16

RAM_GB=${1:-16}
SWAP_GB=${2:-32}

echo "🚀 aiDAPTIV Memory Limit Launcher"
echo "=================================="

# Check OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "❌ Error: This script requires Linux with systemd (cgroups)."
    echo "   On macOS, OS-level memory limiting is not supported via this method."
    exit 1
fi

# Check for systemd-run
if ! command -v systemd-run &> /dev/null; then
    echo "❌ Error: systemd-run not found. Cannot enforce memory limits."
    exit 1
fi

# Stop existing Ollama
echo "🛑 Stopping any running Ollama instances..."
pkill ollama || true
sleep 2

# Verify stopped
if pgrep ollama > /dev/null; then
    echo "⚠️  Warning: Ollama is still running. Trying force kill..."
    pkill -9 ollama
    sleep 1
fi

echo "🔒 Configuring Constraints:"
echo "   • RAM Limit:  ${RAM_GB} GB"
echo "   • Swap Limit: ${SWAP_GB} GB"

# Convert to Bytes/Strings for systemd
MEM_LIMIT="${RAM_GB}G"

UNIT_NAME="ollama-constrained-$(date +%s)"

sudo systemd-run --unit="$UNIT_NAME" \
    --property=MemoryMax="$MEM_LIMIT" \
    --property=MemorySwapMax="${SWAP_GB}G" \
    --service-type=simple \
    /usr/bin/ollama serve

echo "✅ Ollama started in background unit: $UNIT_NAME"
echo ""
echo "📊 Cgroup Status:"
systemctl status "$UNIT_NAME" --no-pager

echo ""
echo "⚠️  IMPORTANT:"
echo "   1. Start your benchmark now."
echo "   2. When finished, run: sudo systemctl stop $UNIT_NAME"
echo ""
