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

# Shift past the first two arguments (RAM and SWAP) to get the command
shift 2
COMMAND="$@"

if [ -z "$COMMAND" ]; then
    echo "❌ Error: No command provided to run."
    echo "Usage: ./limit_runner.sh [RAM_GB] [SWAP_GB] [COMMAND...]"
    exit 1
fi

echo "🔒 Configuring Constraints:"
echo "   • RAM Limit:  ${RAM_GB} GB"
echo "   • Swap Limit: ${SWAP_GB} GB"
echo "   • Command:    $COMMAND"

# Convert to Bytes/Strings for systemd
MEM_LIMIT="${RAM_GB}G"

UNIT_NAME="bench-constrained-$(date +%s)"

# Run the user-provided command inside the cgroup
sudo systemd-run --unit="$UNIT_NAME" \
    --property=MemoryMax="$MEM_LIMIT" \
    --property=MemorySwapMax="${SWAP_GB}G" \
    --service-type=simple \
    $COMMAND

echo "✅ Process started in background unit: $UNIT_NAME"
echo ""
echo "📊 Cgroup Status:"
systemctl status "$UNIT_NAME" --no-pager

echo ""
echo "⚠️  IMPORTANT:"
echo "   1. Start your benchmark now."
echo "   2. When finished, run: sudo systemctl stop $UNIT_NAME"
echo ""
