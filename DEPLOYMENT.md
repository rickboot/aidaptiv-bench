# aiDAPTIV Benchmark Tool - Deployment Guide

This guide covers the deployment and usage of the aiDAPTIV Benchmark Tool on various platforms, with a focus on NVIDIA DGX (Linux) and macOS development environments.

## 📋 System Requirements

### Hardware
- **GPU**: NVIDIA GPU (for CUDA/NVML telemetry) or Apple Silicon (limited telemetry).
- **Storage**:
  - **Baseline**: Standard system RAM/VRAM.
  - **aiDAPTIV**: Phison AI100E SSDs (or equivalent) configured with `aiDAPTIVlink` middleware.
- **Memory**: Sufficient RAM to run the OS and basic tools (16GB+ recommended).

### Software
- **OS**: Ubuntu 20.04/22.04 (Recommended), macOS 12+, or Windows 11 (Experimental).
- **Python**: Version 3.9 or higher.
- **Inference Engine**:
  - **Ollama**: Recommended for ease of use (uses `llama.cpp` backend).
  - **vLLM**: Alternative for high-performance production setups (requires manual config).
- **Phison Software** (For aiDAPTIV runs):
  - `aiDAPTIVlink` middleware installed on the Host OS.
  - Appropriate drivers for Phison SSDs.

---

## 🚀 Quick Start (Linux / DGX)

This is the primary deployment target.

### 1. Installation
Clone the repository and run the setup script:

```bash
git clone https://github.com/rickboot/aidaptiv-bench.git
cd aidaptiv-bench
chmod +x start.sh
./start.sh
```

The `start.sh` script will automatically:
- Check for Python 3.9+
- Install python dependencies (`requirements.txt` equivalent)
- Install/System-check Ollama
- Pull the required model (e.g., `llama3.1:8b`)
- Launch the web dashboard

### 2. Running a Benchmark
1. Open the dashboard at `http://<DGX_IP>:8081` (or `localhost:8081` if local).
2. Go to the **Setup** tab.
3. Select your Model and Context Range (e.g., 2K to 32K).
4. Click **Generate Command**.
5. **Copy the command** (e.g., `sudo python3 benchmark.py ...`).
6. Paste and run it in your SSH terminal.
   - *Note: The "Run Benchmark" button's auto-terminal feature does not attempt to open a GUI terminal on Linux.*
7. Observe real-time telemetry in the **Live Monitor** tab.

### 3. Toggling aiDAPTIV
Currently, the tool supports a **Manual Toggle** workflow:
1. Run the benchmark command.
2. The tool runs the **Baseline** stage first.
3. It will **PAUSE** and prompt you to enable aiDAPTIV.
4. Enable aiDAPTIV on the host (e.g., via config change, command, or environment variable).
5. Press `Enter` in the terminal to continue running the **aiDAPTIV** stage.

---

## 🛡️ Defensible Benchmarking (Limit Enforcement)

To demonstrate the value of aiDAPTIV, you often need to show what happens when a system **physically runs out of RAM**. Since DGX systems have huge RAM (e.g., 2TB), you must simulate a constrained environment (e.g., 16GB) using OS-level controls.

**Use `limit_runner.sh` to launch Ollama with strict limits:**

```bash
# 1. Stop any existing Ollama
pkill ollama

# 2. Launch Ollama capped at 16GB RAM
#    (It will use 16GB RAM + Swap, forcing massive slowdown/churn if exceeded)
sudo ./limit_runner.sh 16
```

**What this does:**
- Uses Linux `systemd-run` (cgroups) to enforce a hard `MemoryMax=16G` limit.
- If the model/context exceeds 16GB, the OS will force **swapping** (simulating a crash/churn scenario).
- This provides **real, physical performance degradation** data for your baseline.

**Note:** This only works on Linux. On macOS/Windows, use the Visual Limit lines in the Dashboard for a conceptual demo.

---

## 🍎 macOS (Development)

The tool acts as a "Sidecar" on macOS, simulating the UI workflow.

### 1. Installation
Same as Linux:
```bash
./start.sh
```

### 2. Running a Benchmark
1. Go to **Setup** tab.
2. Click **Run Benchmark**.
3. A Terminal window will **automatically pop up**.
4. Enter your `sudo` password to allow GPU/Power telemetry.
5. Watch the **Live Monitor**.

*Note: macOS telemetry is limited compared to NVML on Linux.*

---

## 🪟 Windows / AMD Strix Halo (Experimental)

Windows support is currently in planning.

**Limitations:**
- `start.sh` does not work (requires `start.bat` or Python launcher).
- `pynvml` telemetry requires NVIDIA GPUs (AMD GPU telemetry needs a different library).
- Terminal auto-open is not supported.

**Workaround:**
1. Install Python 3.10+ manually.
2. Install dependencies: `pip install -r requirements.txt` (or see `start.sh` for list).
3. Install Ollama for Windows.
4. Run the dashboard: `python dashboard.py`.
5. Run benchmarks manually via PowerShell: `python benchmark.py ...`.

---

## 🔧 Architecture Notes

### Containerization (Docker)
We recommend **Native Installation** over Docker for this specific tool because:
1. **Middleware Access**: `aiDAPTIVlink` runs on the host OS. Accessing it from a container adds complexity (bind mounts, privileges).
2. **GPU Telemetry**: Requires `--gpus all` and passing NVML devices to the container.
3. **Simplicity**: The tool is a lightweight Python wrapper; container overhead outweighs the benefits for a benchmarking harness.

### Telemetry
- **RAM**: Uses `psutil` (Cross-platform).
- **VRAM**: Uses `pynvml` (NVIDIA) or fallback to `psutil` (System RAM) on Apple Silicon.
- **Power**: Uses `pynvml` (NVIDIA) or `powermetrics` (macOS - requires sudo).
