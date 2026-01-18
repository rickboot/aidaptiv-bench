# Phison aiDAPTIV Benchmarking Tool - Feature Brainstorming

## Project Goal
Provide Phison Technical Marketing Engineers (TMEs) with a **technically rigorous**, yet accessible platform to benchmark and demonstrate aiDAPTIV performance. The tool must produce "engineering-grade" data valid for partners and customers.

## Target Hardware & Platforms
*   **Primary Targets**:
    *   **DGX Spark**
    *   **AMD Strix Halo** (High-performance APU scenarios)
*   **Memory Baseline**: 128GB System RAM validation.
*   **Device Support**: Auto-detect compliant hardware; specifically validate Phison SSDs in the loop.

## Proposed Feature Requirements

### 1. Framework & Backend Support (Python Centric)
Ensure compatibility with industry-standard tooling to prove viability in real deployed environments.
*   **Inference Engines**:
    *   `llama.cpp` / `Ollama` (GGUF quant usage)
    *   `vLLM` (High throughput serving)
    *   `PyTorch` (Native research workloads)
    *   `TensorFlow` (Legacy/Enterprise support)

### 2. "Engineering-Grade" Configuration & Validation
To ensure data is trusted by external engineers:
*   **Granular Memory Controls**:
    *   **Total Memory Cap**: Simulate constrained environments (e.g., "Pretend I only have 16GB VRAM").
    *   **KV Cache Management**: Explicit controls for cache sizing (e.g., `cache_bit` (4-bit/8-bit), context window).
    *   **Offloading layers**: Manually or automatically set GPU/CPU split.
*   **Audit Trail**: Every benchmark run produces a JSON/YAML dump of *exact* environment state (driver versions, library versions, commit hashes) to ensure reproducibility.

### 3. Telemetry & Visualization
**Goal**: Telemetry **data points** must match the rigorous standards of the previous aiDAPTIV demo, but the **visual presentation** should adhere to the simpler OpenWebUI/Gradio style (not a custom UI clone).

*   **Required Data Points**:
    *   **Memory Composition**: Exact byte-level breakdown of **VRAM** vs **System RAM** vs **SSD Swap**.
    *   **Throughput & Latency**: Live `Tokens/sec` and `Time to First Token (TTFT)`.
    *   **Cost Estimation**: Live "Estimated Cloud Cost" counter (based on equivalent cloud GPU rental) vs "Local Hardware Cost".
    *   **SSD Activity**: Read/Write IOPS specifically on the Phison drive to prove it's handling the offload.

### 4. User Interface (Low-Code / Engineer Friendly)
*   **Philosophy**: "Function over Flash" - but still clean. Avoid complex custom React stacks if maintenance is a burden.
*   **Inspiration/Tech**:
    *   **OpenWebUI** / **Gradio** / **Streamlit**: Python-integrated UIs that TMEs can tweak if needed.
    *   **ComfyUI**: Node-based or modular workflows for constructing complex benchmark pipelines (optional advanced mode).

### 5. Benchmark Scenarios
*   Let users script or select:
    *   *Linear Scaling*: "Run Llama-3-70B at context 4k, then 8k, then 16k..." until failure or cutoff.
    *   *Concurrency*: "Simulate 1 user, then 2, then 4..." (Batch size testing).
    *   *Soak Tests*: Run for 24h to prove no memory leaks in the offloading layer.
    *   *Comparison Report*: Auto-generate "OOM vs Success" charts.
