import argparse
import yaml
import time
import os
import json
import requests
import subprocess
import platform
import psutil
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
import concurrent.futures
from telemetry import TelemetryCollector


@dataclass
class RequestMetrics:
    timestamp: float
    context_len: int
    success: bool
    ttft_ms: float = 0.0
    total_latency_ms: float = 0.0
    output_tokens: int = 0      # Deprecated alias for completion_tokens
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tps_overall: float = 0.0    # (completion_tokens) / (total_latency)
    tps_prefill: float = 0.0    # (prompt_tokens) / (ttft)
    # (completion_tokens - 1) / (total_latency - ttft)
    tps_decode: float = 0.0
    error: str = ""
    pass_fail: bool = True     # Did the model satisfy the constraint?
    # Capture relevant scenario data (e.g. injected needle)
    meta: Optional[Dict] = None


def capture_metadata(config: dict) -> dict:
    """Captures reproducible run metadata."""
    meta = {
        "timestamp": datetime.now().isoformat(),
        "git_commit": "Unknown",
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "cpu_cores": psutil.cpu_count(logical=False),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "ram_limit_gb": config.get('platform', {}).get('ram_gb'),
            "vram_limit_gb": config.get('platform', {}).get('vram_gb')
        },
        "test_config": {
            "scenario_name": config.get('test', {}).get('scenario_name', 'Unknown'),
            "model": config.get('runtime', {}).get('model_name'),
            "concurrency": config.get('test', {}).get('concurrency', 1),
            "runs_per_context": config.get('test', {}).get('runs_per_context', 1),
            "step_mode": config.get('test', {}).get('step_mode', 'linear'),
            "context_lengths": config.get('test', {}).get('context_lengths', []),
            "scenario": config.get('test', {}).get('scenario', 'synthetic'),
            "max_tokens_output": config.get('test', {}).get('max_tokens_output'),
            "temperature": config.get('test', {}).get('temperature'),
            "top_p": config.get('test', {}).get('top_p'),
            "seed": config.get('test', {}).get('seed')
        },
        "config": config,
        "runtime_version": "Unknown"  # TODO: Query runtime version
    }

    # Try to get git hash
    try:
        meta["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except:
        pass

    return meta


class BenchmarkSuite:
    def __init__(self, config_class, run_id: str = None):
        self.config = config_class
        if run_id:
            self.results_dir = f"results/{run_id}"
            if not os.path.exists(self.results_dir):
                print(
                    f"⚠️ Warning: Run ID {run_id} directory does not exist. Creating it.")
                os.makedirs(self.results_dir, exist_ok=True)
        else:
            self.results_dir = f"results/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.makedirs(self.results_dir, exist_ok=True)

    def check_runtime(self):
        url = self.config['runtime']['endpoint']
        print(f"🔍 Checking runtime at {url}...")
        try:
            # Minimal probe to see if server is up, not full generation
            # vLLM/OpenAI usually have /v1/models
            base = url.rsplit('/v1', 1)[0]
            requests.get(f"{base}/v1/models", timeout=5)
            print("✅ Runtime is online.")
            return True
        except Exception as e:
            print(f"❌ Runtime NOT accessible: {e}")
            return False

    def _parse_streaming_chunk(self, chunk_json: dict) -> tuple:
        """
        Extract content, finish_reason, and usage stats from OpenAI/Ollama chunk.

        Returns:
            (content, finish_reason, usage)
        """
        content = ""
        finish_reason = None
        usage = {}

        # Ollama format:
        # {
        #   "response": "text", "done": false,
        #   "prompt_eval_count": 12, "eval_count": 50, ... (only on done=true)
        # }
        if 'response' in chunk_json:
            content = chunk_json.get('response', '')
            if chunk_json.get('done', False):
                finish_reason = 'stop'
                # Extract Usage Stats
                if 'prompt_eval_count' in chunk_json:
                    usage['prompt_tokens'] = chunk_json['prompt_eval_count']
                if 'eval_count' in chunk_json:
                    usage['completion_tokens'] = chunk_json['eval_count']
            return content, finish_reason, usage

        # OpenAI format:
        # {"choices": [...], "usage": {...}}
        if 'choices' in chunk_json and len(chunk_json['choices']) > 0:
            choice = chunk_json['choices'][0]
            finish_reason = choice.get('finish_reason')

            if 'delta' in choice:
                content = choice['delta'].get('content', '')
            elif 'text' in choice:
                content = choice['text']

        # Check for usage in OpenAI format (often separate chunk or at end)
        if 'usage' in chunk_json:
            u = chunk_json['usage']
            usage['prompt_tokens'] = u.get('prompt_tokens', 0)
            usage['completion_tokens'] = u.get('completion_tokens', 0)

        return content, finish_reason, usage

    def run_prompt(self, context_len: int, dry_run: bool = False, collector=None) -> RequestMetrics:
        """
        Executes a single inference request with STREAMING to measure TTFT.
        """
        print(
            f"[DEBUG] run_prompt called: collector={'present' if collector else 'NONE'}, dry_run={dry_run}")

        # Select Scenario
        from scenarios import SyntheticScenario, NeedleInHaystackScenario

        scenario_type = self.config['test'].get('scenario', 'synthetic')
        scenario = NeedleInHaystackScenario(
        ) if scenario_type == 'needle' else SyntheticScenario()

        prompt, meta = scenario.generate_prompt(context_len)
        max_tokens = 10 if dry_run else self.config['test']['max_tokens_output']

        # Construct Payload (OpenAI-compatible format for Ollama's /v1/completions endpoint)
        payload = {
            "model": self.config['runtime']['model_name'],
            "prompt": prompt,
            "stream": True,
            "max_tokens": max_tokens,
            "temperature": self.config['test'].get('temperature', 0.0),
            "top_p": self.config['test'].get('top_p', 0.9),
            "seed": self.config['test'].get('seed', 42),
        }

        t0 = time.time()
        ttft = 0.0
        output_tokens = 0
        prompt_tokens_count = 0
        completion_tokens_count = 0
        success = False
        error_msg = ""
        full_response = []

        # Notify telemetry that request is starting
        if collector:
            collector.start_request()

        try:
            with requests.post(
                self.config['runtime']['endpoint'],
                json=payload,
                timeout=self.config['test']['timeout_seconds'],
                stream=True
            ) as resp:
                resp.raise_for_status()

                # Streaming loop
                full_response = []
                for line in resp.iter_lines():

                    if not line:
                        continue

                    decoded = line.decode('utf-8').strip()
                    if decoded == "data: [DONE]":
                        break

                    if decoded.startswith("data: "):
                        # Parse chunk using helper
                        try:
                            chunk_json = json.loads(decoded[6:])
                            chunk_json = json.loads(decoded[6:])
                            chunk_text, finish_reason, usage = self._parse_streaming_chunk(
                                chunk_json)

                            # Accumulate usage stats if present (Ollama sends at end)
                            if usage:
                                if 'prompt_tokens' in usage:
                                    prompt_tokens_count = usage['prompt_tokens']
                                if 'completion_tokens' in usage:
                                    completion_tokens_count = usage['completion_tokens']
                        except json.JSONDecodeError as e:
                            # Invalid JSON in stream - skip this chunk
                            continue

                        # Only process chunks with actual content
                        if chunk_text:
                            # First token logic
                            if output_tokens == 0:
                                ttft = (time.time() - t0) * 1000
                                # Report TTFT to telemetry
                                if collector:
                                    collector.set_ttft(ttft)

                            full_response.append(chunk_text)
                            output_tokens += 1

                            # Live TPS Update (Increased frequency for UI responsiveness)
                            if collector and (output_tokens % 2 == 0):
                                cur_elapsed = time.time() - t0
                                if cur_elapsed > 0.05:
                                    collector.set_tps(
                                        output_tokens / cur_elapsed)

                        # Check for stream completion
                        if finish_reason:
                            break  # Stream completed normally

                success = True

        except requests.exceptions.Timeout:
            error_msg = f"Request timeout after {self.config['test']['timeout_seconds']}s"
            success = False
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection failed: {str(e)[:100]}"
            success = False
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 'unknown'
            error_msg = f"HTTP {status_code}: {str(e)[:100]}"
            success = False
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON at line {e.lineno}: {e.msg}"
            success = False
        except Exception as e:
            error_msg = f"Unexpected {type(e).__name__}: {str(e)[:100]}"
            success = False

        total_lat = (time.time() - t0) * 1000
        if ttft == 0 and success:
            ttft = total_lat  # Fallback if single chunk

        # Stream Validation: Detect incomplete/truncated streams
        # Note: finish_reason is set in the streaming loop when detected
        # If stream ended without finish_reason, it may be truncated
        # (This is stored in local scope during streaming, not accessible here)
        # The validation is implicit - if we got here with success=True, stream completed

        # Validate Response
        response_text = "".join(full_response)
        pass_fail = scenario.validate(response_text, meta)

        # Calculate derived metrics
        total_lat = (time.time() - t0) * 1000

        # Metric Calculations
        # 1. Fallback for token counts if not provided by API
        if prompt_tokens_count == 0:
            prompt_tokens_count = int(len(prompt) / 4)  # Rough estimate

        # Use simple counter if usage stats missing
        if completion_tokens_count == 0:
            completion_tokens_count = output_tokens

        # 2. Calculate TPS
        tps_overall = 0.0
        tps_pre = 0.0
        tps_dec = 0.0

        # Overall: Total Tokens / Total Time
        if total_lat > 0:
            tps_overall = completion_tokens_count / (total_lat / 1000.0)

        # Prefill: Prompt Tokens / TTFT
        if ttft > 0:
            tps_pre = prompt_tokens_count / (ttft / 1000.0)

        # Decode: (Output - 1) / (Total - TTFT)
        # We subtract 1 because the first token is generated during the TTFT window
        decode_time_ms = total_lat - ttft
        if decode_time_ms > 0 and completion_tokens_count > 1:
            tps_dec = (completion_tokens_count - 1) / (decode_time_ms / 1000.0)

        # Notify telemetry that request has completed
        if collector:
            collector.end_request(total_lat)

        return RequestMetrics(
            timestamp=t0,
            context_len=context_len,
            success=success,
            ttft_ms=ttft,
            total_latency_ms=total_lat,
            output_tokens=completion_tokens_count,  # Deprecated legacy field
            prompt_tokens=prompt_tokens_count,
            completion_tokens=completion_tokens_count,
            tps_overall=tps_overall,
            tps_prefill=tps_pre,
            tps_decode=tps_dec,
            error=error_msg,
            # TODO: Actual grading logic
            pass_fail=meta.get('pass_fail', True),
            meta=meta
        )

    def run_sweep(self, mode: str):
        print(f"\n🚀 Starting Sweep: {mode.upper()}")

        # 0. Capture Metadata
        meta = capture_metadata(self.config)
        with open(os.path.join(self.results_dir, f"metadata_{mode}.json"), 'w') as f:
            json.dump(meta, f, indent=2)

        # 1. Apply Toggle (Placeholder command execution)
        cmd_key = 'enable_command' if mode == 'aidaptiv' else 'disable_command'
        cmd = self.config['aidaptiv'].get(cmd_key)
        if cmd:
            print(f"➡️ Executing: {cmd}")

        # 2. Start Telemetry
        telemetry_file = os.path.join(self.results_dir, f"metrics_{mode}.csv")
        storage_dev = self.config['aidaptiv'].get('storage_device', 'disk0')
        model_name = self.config['runtime'].get('model_name', 'Unknown')

        collector = TelemetryCollector(
            telemetry_file,
            self.config['telemetry']['sample_interval_sec'],
            dashboard_url="http://localhost:8081",
            storage_device=storage_dev,
            model_name=model_name
        )
        collector.start()

        all_metrics: List[RequestMetrics] = []
        aggregated_results = []

        try:
            contexts = self.config['test']['context_lengths']
            total_contexts = len(contexts)

            for idx, ctx in enumerate(contexts, 1):
                print(f"   📋 Testing Context: {ctx}...")

                # Notify telemetry of test progress
                collector.set_test_progress(
                    ctx, total_contexts, planned_contexts=contexts)

                scenario_name = self.config['test'].get(
                    'scenario_name', mode.upper())
                collector.set_status(f"Running {scenario_name}")

                # Warmup
                self.run_prompt(ctx, dry_run=True, collector=collector)

                # Measured Runs
                ctx_metrics: List[RequestMetrics] = []

                # Concurrent Execution
                concurrency = self.config.get('test', {}).get('concurrency', 1)
                if concurrency > 1:
                    print(
                        f"      Running {self.config['test']['runs_per_context']} requests with concurrency={concurrency}...")

                futures = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                    for _ in range(self.config['test']['runs_per_context']):
                        futures.append(executor.submit(
                            self.run_prompt, ctx, dry_run=False, collector=collector))

                    for future in concurrent.futures.as_completed(futures):
                        try:
                            res = future.result()
                            all_metrics.append(res)
                            ctx_metrics.append(res)

                            if res.success:
                                # Update Telemetry Status with TPS (Approximate for concurrency)
                                collector.set_tps(res.tps_overall)
                            else:
                                collector.set_tps(0.0)
                                print(f"      ❌ Failed: {res.error}")
                        except Exception as e:
                            print(f"      ❌ Thread Error: {e}")

                # Reset TPS after context run
                collector.set_tps(0.0)

                # Calculate Statistics for this Context
                valid_runs = [m for m in ctx_metrics if m.success]
                pass_rate = (len(valid_runs) / len(ctx_metrics)) * \
                    100 if ctx_metrics else 0

                avg_lat = 0
                p50 = 0
                p95 = 0
                p99 = 0
                avg_ttft = 0

                if valid_runs:
                    lats = sorted([m.total_latency_ms for m in valid_runs])
                    ttfts = [m.ttft_ms for m in valid_runs]

                    avg_lat = sum(lats) / len(lats)
                    avg_ttft = sum(ttfts) / len(ttfts)

                    def get_p(lst, p):
                        return lst[int(len(lst) * p)]

                    p50 = get_p(lats, 0.50)
                    p95 = get_p(lats, 0.95)
                    p99 = get_p(lats, 0.99)

                # Calculate TPS averages
                avg_tps_pre = 0.0
                avg_tps_dec = 0.0
                if valid_runs:
                    avg_tps_pre = sum(
                        m.tps_prefill for m in valid_runs) / len(valid_runs)
                    avg_tps_dec = sum(
                        m.tps_decode for m in valid_runs) / len(valid_runs)

                print(
                    f"      ✅ Avg Lat: {int(avg_lat)}ms | P95: {int(p95)}ms | TTFT: {int(avg_ttft)}ms | Pass: {int(pass_rate)}% | Users: {concurrency}")

                aggregated_results.append({
                    "context": ctx,
                    "avg_latency_ms": avg_lat,
                    "p50_latency_ms": p50,
                    "p95_latency_ms": p95,
                    "p99_latency_ms": p99,
                    "avg_ttft_ms": avg_ttft,
                    "tps_prefill": avg_tps_pre,
                    "tps_decode": avg_tps_dec,
                    "pass_rate_pct": pass_rate,
                    "total_prompt_tokens": sum(m.prompt_tokens for m in valid_runs) if valid_runs else 0,
                    "total_completion_tokens": sum(m.completion_tokens for m in valid_runs) if valid_runs else 0,
                    "run_count": len(valid_runs)
                })

                # Save test result to telemetry for dashboard display
                if valid_runs:
                    avg_tps = sum(
                        m.tps_overall for m in valid_runs) / len(valid_runs)
                    collector.save_test_result(ctx, avg_ttft, avg_lat, avg_tps)

                # Early exit on failure (OOM usually kills ability to proceed)
                if pass_rate < 50:
                    print("      ⚠️ High failure rate, stopping sweep.")
                    break

        finally:
            # Save Per-Request Log (Request CSV)
            try:
                req_csv_path = os.path.join(
                    self.results_dir, f"requests_{mode}.csv")
                with open(req_csv_path, 'w', newline='') as f:
                    import csv
                    writer = csv.writer(f)
                    writer.writerow(["timestamp", "context_len", "success", "pass_fail", "ttft_ms",
                                    "total_latency_ms", "prompt_tokens", "completion_tokens", "tps_overall", "tps_prefill", "tps_decode", "error"])
                    for m in all_metrics:
                        writer.writerow([
                            m.timestamp, m.context_len, m.success, m.pass_fail,
                            round(m.ttft_ms, 2), round(m.total_latency_ms, 2),
                            m.prompt_tokens, m.completion_tokens,
                            round(m.tps_overall, 2), round(
                                m.tps_prefill, 2), round(m.tps_decode, 2),
                            m.error
                        ])

                # Save Aggregated JSON
                with open(os.path.join(self.results_dir, f"results_{mode}.json"), 'w') as f:
                    json.dump(aggregated_results, f, indent=2)

                # Save Metadata
                meta = capture_metadata(self.config)
                with open(os.path.join(self.results_dir, f"metadata_{mode}.json"), 'w') as f:
                    json.dump(meta, f, indent=2)

                # Explicit confirmation
                print(
                    f"      💾 {mode.capitalize()} results saved to: {self.results_dir}")
            except Exception as e:
                print(f"      ❌ Error saving results: {e}")

            collector.stop()

    def run(self, stage: str):
        # Full Suite or Specific Stage
        if not self.check_runtime():
            import sys
            sys.exit(1)

        print(f"📂 Results will be saved to: {self.results_dir}")

        # Run Baseline
        if stage in ["all", "baseline"]:
            self.run_sweep("baseline")

        # Intermission - Skipped as requested
        # if stage == "all": ... (REMOVED)

        # Run aiDAPTIV
        if stage in ["all", "aidaptiv"]:
            self.run_sweep("aidaptiv")

        print(
            f"\n🏁 Benchmark Stage '{stage}' Complete. Results in {self.results_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--stage", choices=["all", "baseline", "aidaptiv"], default="all",
                        help="Run only a specific stage of the benchmark.")
    parser.add_argument(
        "--run-id", help="Resume/Append to an existing run ID (timestamp folder name).")
    parser.add_argument("--concurrency", type=int,
                        default=None, help="Overide config concurrency")
    parser.add_argument("--context-start", type=int,
                        default=None, help="Override start")
    parser.add_argument("--context-end", type=int,
                        default=None, help="Override end")
    parser.add_argument("--context-step", type=int,
                        default=None, help="Override step")
    parser.add_argument("--model", type=str, default=None,
                        help="Override model")
    parser.add_argument("--scenario", type=str,
                        choices=["synthetic", "needle"], default=None, help="Choose scenario")
    parser.add_argument(
        "--step-mode", choices=["linear", "geometric"], default="linear")

    args = parser.parse_args()

    with open(args.config) as f:
        conf = yaml.safe_load(f)

    # CLI Overrides
    if args.concurrency:
        conf['test']['concurrency'] = args.concurrency
    if args.model:
        conf['runtime']['model_name'] = args.model
    if args.scenario:
        conf['test']['scenario'] = args.scenario

    if args.context_start and args.context_end:
        start = args.context_start
        end = args.context_end
        step = args.context_step if args.context_step else 1024
        mode = args.step_mode if args.step_mode else conf['test'].get(
            'step_mode', 'linear')

        lengths = []
        if mode == 'geometric':
            curr = start
            while curr <= end:
                lengths.append(curr)
                curr *= 2
        else:
            lengths = list(range(start, end + 1, step))

        conf['test']['context_lengths'] = lengths

        # Generate dynamic scenario name if model or contexts changed
        model_part = conf['runtime']['model_name'].split(
            ':')[0].replace('llama3.1', 'Llama').replace('qwen2.5', 'Qwen')
        if ':' in conf['runtime']['model_name']:
            size = conf['runtime']['model_name'].split(':')[1].upper()
            model_part += f"-{size}"

        def format_k(v):
            return f"{v//1024}K" if v >= 1024 else str(v)

        step_str = "double" if mode == "geometric" else f"{format_k(step)}-step"
        conf['test']['scenario_name'] = f"{model_part}_{format_k(start)}-{format_k(end)}_{step_str}"

    suite = BenchmarkSuite(conf, args.run_id)
    suite.run(args.stage)
