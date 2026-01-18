# Understanding the Benchmark: Context, Prefill, and Throughput

This document explains the technical dynamics of the benchmark sweeps and how performance characteristics change as context size increases.

## 1. What Happens During a Sweep?

When `benchmark.py` runs a "Sweep" (e.g., Context 2k -> 8k -> 32k), it performs the following steps for each iteration:

1.  **Generate Prompt (The Work)**:
    - Creates a dummy prompt exactly `N` tokens long (e.g., 4096 tokens).
    - This simulates a user analyzing a large document (PDF, Codebase, etc.).

2.  **Orchestration (Host CPU)**:
    - The `ollama_llama_server` receives the request.
    - Host CPU tokenizes the text and prepares the GPU instructions.

3.  **Inference (GPU / AI Accelerator)**: 
    - This happens in two distinct phases: **Prefill** and **Generation**.

---

## 2. The Two Phases of Inference

### Phase A: Prefill (Context Processing)
*   **What it is**: Processing the input prompt to "understand" the context.
*   **Compute Nature**: **Highly Parallel**. The GPU can calculate attention scores for all 4096 tokens simultaneously.
*   **Speed**: Extremely Fast (Thousands of Tokens per Second).
*   **Memory Impact**: Creates the initial **KV Cache** (Key-Value Memory). Size grows linearly with context length.
*   **Dashboard Effect**: Spikes "AI Compute Load" to max instantly.

### Phase B: Generation (Output)
*   **What it is**: Creating the response (e.g., "The summary of the document is...").
*   **Compute Nature**: **Serial**. Token 2 depends on Token 1. Cannot be parallelized.
*   **Speed**: Slower (30-100 Tokens per Second, depending on hardware).
*   **Memory Impact**: Slowly increases KV Cache with each new token generated.

---

## 3. Why Performance Changes with Context

Our benchmark focuses on **Throughput (TPS)**, which combines both phases:
`TPS = (Input Tokens + Output Tokens) / Total Time`

### Small Context (e.g., 2k)
- **Dominant Factor**: Generation.
- Since the input is small, the fast "Prefill" phase is over instantly.
- The total time is mostly waiting for the slow serial generation.
- **Result**: Lower TPS (closer to generation speed).

### Large Context (e.g., 32k)
- **Dominant Factor**: Prefill.
- The GPU spends most of its time crunching the massive 32k input at high speed.
- **Result**: Higher apparent TPS (because the "fast" work outweighs the "slow" work).
- **CRITICAL RISK**: This massive input forces the **KV Cache** to grow huge (e.g., 10GB+).

---

## 4. The "Money Shot": Hitting the Memory Wall

The performance curve isn't just about speed; it's about **capacity**.

1.  **In-Memory (Fast)**: As long as the KV Cache + Model Weights fit in RAM (Tier 1/2), performance remains high.
2.  **The Wall**: When Context Size > Available RAM.
3.  **Standard System (Crash/Thrash)**:
    - The OS starts swapping to disk (Tier 3) using generic virtual memory paging.
    - **Performance collapses** (e.g., 1000 TPS -> 0.1 TPS).
    - The system becomes unresponsive.
4.  **aiDAPTIV (Success)**:
    - Intelligently offloads layers/KV Cache to the dedicated Tier 3 storage.
    - Maintains **usable throughput** (e.g., 20 TPS) where the standard system fails.
    - Prevents OOM (Out of Memory) crashes.

**Summary**: The benchmark is a stress test designed to force this transition from "Fast RAM" to "Managed Storage", proving the value of the storage tier.
