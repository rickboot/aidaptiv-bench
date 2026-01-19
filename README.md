# Phison aiDAPTIV Benchmarking Tool

A lightweight CLI harness for generating defensible A/B benchmarks of AI workloads, designed to demonstrate the value of **Phison aiDAPTIV** in preventing Out-Of-Memory (OOM) errors and managing high-context workloads on constrained memory systems.

## 🚀 Features

*   **A/B Benchmarking**: Compare "Baseline" (Standard) vs "aiDAPTIV" (Optimized) performance.
*   **Context Sweeping**: Automatically test increasing context lengths (e.g., 8K → 128K) until failure.
*   **Detailed Telemetry**: Captures RAM, VRAM, Disk I/O, and Inference Latency (TTFT).
*   **Slide-Ready Charts**: Automatically generates comparison charts (`ttft_comparison.png`, `ram_timeline.png`).
*   **Manual Toggle Workflow**: Supports manual enabling/disabling of aiDAPTIV features (via reboot or service restart) between test stages.

## 📋 Prerequisites

*   **Python**: 3.9+
*   **Inference Runtime**: An OpenAI-compatible endpoint (e.g., `vLLM`, `llama.cpp`, or `Ollama`).
*   **Target Hardware**: 
    *   **Baseline**: N/A
    *   **aiDAPTIV Run**: Requires Phison aiDAPTIV hardware/drivers configured.

## ⚙️ Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/rickboot/aidaptiv-bench.git
    cd aidaptiv-bench
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    # OR manual install:
    pip install requests psutil pyyaml pandas matplotlib plotly pynvml
    ```

## 🛠️ Configuration

Edit `config.yaml` to match your environment:

```yaml
platform:
  ram_gb: 128            # Total System RAM (GB)

runtime:
  endpoint: "http://localhost:8000/v1/completions" # URL to your inference server
  model_name: "llama-3-70b"                        # Model ID expected by the runtime

test:
  context_lengths: [32768, 65536, 131072]          # Context lengths to sweep
  runs_per_context: 3
  timeout_seconds: 600
```

## 🏃 Usage

### Option A: Continuous Run (No Reboot Required)
If you can toggle aiDAPTIV without rebooting (e.g., via environment variable restart):

1.  Start the benchmark:
    ```bash
    python3 benchmark.py
    ```
2.  The script will run the **Baseline** sweep.
3.  It will **PAUSE** and prompt you to enable aiDAPTIV.
4.  Once you confirm, it will run the **aiDAPTIV** sweep.

### Option B: Split Run (Reboot Required)
If you need to reboot the proper machine to enable aiDAPTIV:

1.  **Run Baseline Only**:
    ```bash
    python3 benchmark.py --stage baseline
    ```
    *Note the `results/<TIMESTAMP>` folder that is created.*

2.  **Reboot / Enable aiDAPTIV**.

3.  **Resume for aiDAPTIV**:
    ```bash
    python3 benchmark.py --stage aidaptiv --run-id <TIMESTAMP_FROM_STEP_1>
    ```

## 📊 Output
Results are saved to `results/<TIMESTAMP>/`:

- **`results_{mode}.json`**: Aggregated stats (P50/P95 latency, Pass %, Throughput).
- **`requests_{mode}.csv`**: detailed per-request logs (TTFT, Decode Time, Output Tokens).
- **`metadata_{mode}.json`**: System verification (Git commit, RAM/CPU specs).
- **`metrics_{mode}.csv`**: Second-by-second system telemetry (RAM, VRAM, I/O).

## 📐 Metrics Explained
This tool measures Engineer-Grade metrics to ensure rigorous evaluation:

- **TTFT (Time To First Token)**: Latency from request sent to first token received. Measures "responsiveness".
- **Decode TPS**: Tokens Per Second during generation phase. Measures "throughput".
- **P95 Latency**: 95th Percentile latency. Measures "consistency" (tail latency).
- **Pass Rate**: Percentage of requests that completed successfully without OOM or Timeout.

## 🗺️ Roadmap

### Completed ✅
- [x] Live Dashboard with real-time telemetry
- [x] Report Viewer with interactive charts
- [x] Memory Timeline visualization (RAM + VRAM)
- [x] Latency vs Context Size charts
- [x] Human-readable timestamps and run metrics
- [x] CLI 'quit' option for partial runs

### Planned Features 🚧

#### Phase 1: Deployment & Documentation
- [x] **[Deployment Guide](DEPLOYMENT.md)**: Document setup for DGX/Strix Halo/Windows
  - aiDAPTIV prerequisites and installation
  - Platform-specific instructions (Linux, Windows, macOS)
  - Toggle method documentation (manual/env var/auto)
  - Troubleshooting common issues
- [ ] **Cross-Platform Launcher**: Python-based launcher (replaces start.sh)
  - Auto-detects OS and adjusts behavior
  - Works on Linux, Windows, macOS
  - Handles Ollama startup and model download

#### Phase 2: Test Setup UI Enhancements
- [ ] **Scenario Selector**: Web UI to configure and launch benchmarks
  - Model selection dropdown
  - Context range configuration (start, end, step)
  - Scenario naming
  - Command generator (copy/paste for CLI execution)

#### Phase 2: Enhanced Metrics
- [ ] **TTFT (Time to First Token)**: Separate prefill timing from generation
- [ ] **OOM Detection**: Visual indicators on charts when tests fail
- [ ] **Tier 3 I/O Overlay**: Add disk throughput to memory timeline
- [ ] **Performance Delta**: Calculate and display aiDAPTIV overhead percentage

#### Phase 3: Advanced Reporting
- [ ] **Run Comparison View**: Side-by-side comparison of two benchmark sessions
  - Overlay charts (Baseline vs aiDAPTIV)
  - Delta metrics table
  - Speedup/slowdown calculations
- [ ] **Export to PDF**: Generate slide-ready reports
- [ ] **CSV Export**: Download raw data for external analysis

#### Phase 4: Production Deployment
- [ ] **DGX Validation**: Test on NVIDIA DGX with real aiDAPTIV hardware
- [ ] **Multi-GPU Support**: Distribute workload across multiple GPUs
- [ ] **Automated Toggle**: Script-based aiDAPTIV enable/disable (if supported)
- [ ] **CI/CD Integration**: Automated benchmark runs on hardware changes

#### Phase 5: Advanced Features
- [ ] **Model Auto-Discovery**: Detect available models from Ollama/vLLM
- [ ] **Batch Testing**: Queue multiple scenarios for overnight runs
- [ ] **Alerting**: Slack/email notifications on benchmark completion
- [ ] **Historical Trends**: Track performance over time across multiple runs

