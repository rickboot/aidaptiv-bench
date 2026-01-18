import argparse
import yaml
import time
import os
import json
import requests
import subprocess
from datetime import datetime
from telemetry import TelemetryCollector


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

    def run_prompt(self, context_len: int, dry_run: bool = False):
        """
        Executes a single inference request targeting a specific context length.
        """
        # Create prompt of appropriate length
        # Approx 1 token ~ 4 chars. Word 'test' is 1 token.
        prompt = "test " * (context_len)

        payload = {
            "model": self.config['runtime']['model_name'],
            "prompt": prompt,
            "max_tokens": 10 if dry_run else self.config['test']['max_tokens_output'],
            "stream": False
        }

        t0 = time.time()
        try:
            resp = requests.post(
                self.config['runtime']['endpoint'],
                json=payload,
                timeout=self.config['test']['timeout_seconds']
            )
            resp.raise_for_status()
            data = resp.json()
            latency = (time.time() - t0) * 1000

            # Extract usage if available, else estimate
            usage = data.get('usage', {})
            prompt_toks = usage.get('prompt_tokens', context_len)
            comp_toks = usage.get('completion_tokens', 0)
            total_toks = prompt_toks + comp_toks

            return {
                "success": True,
                "latency_ms": latency,
                "total_tokens": total_toks
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def run_sweep(self, mode: str):
        print(f"\n🚀 Starting Sweep: {mode.upper()}")

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
            sidecar_url="http://localhost:8081",
            storage_device=storage_dev,
            model_name=model_name
        )
        collector.start()

        results = []

        try:
            contexts = self.config['test']['context_lengths']
            for ctx in contexts:
                print(f"   📋 Testing Context: {ctx}...")
                collector.set_status(
                    f"Running {mode.upper()} | Context: {ctx}")

                # Warmup
                self.run_prompt(ctx, dry_run=True)

                # Measured Runs
                latencies = []
                errors = 0
                for _ in range(self.config['test']['runs_per_context']):
                    res = self.run_prompt(ctx)
                    if res['success']:
                        lat_ms = res['latency_ms']
                        latencies.append(lat_ms)

                        # Calculate and Push TPS
                        tps = res['total_tokens'] / (lat_ms / 1000.0)
                        collector.set_tps(tps)
                    else:
                        errors += 1
                        collector.set_tps(0.0)
                        print(f"      ❌ Failed: {res['error']}")

                # Reset TPS after context run
                collector.set_tps(0.0)

                # Check for OOM / Failure
                pass_rate = (len(latencies) /
                             self.config['test']['runs_per_context']) * 100
                avg_lat = sum(latencies)/len(latencies) if latencies else 0

                print(
                    f"      ✅ Avg Latency: {int(avg_lat)}ms | Pass Rate: {int(pass_rate)}%")

                results.append({
                    "context": ctx,
                    "avg_latency_ms": avg_lat,
                    "pass_rate_pct": pass_rate
                })

                # Early exit on failure (OOM usually kills ability to proceed)
                if pass_rate < 50:
                    print("      ⚠️ High failure rate, stopping sweep.")
                    break

        finally:
            collector.stop()

        # Save mode results
        with open(os.path.join(self.results_dir, f"results_{mode}.json"), 'w') as f:
            json.dump(results, f, indent=2)

    def run(self, stage: str):
        # Full Suite or Specific Stage
        if not self.check_runtime():
            return

        print(f"📂 Results will be saved to: {self.results_dir}")

        # Run Baseline
        if stage in ["all", "baseline"]:
            self.run_sweep("baseline")

        # Intermission
        if stage == "all":
            print("\n" + "="*60)
            print("⏸️  PAUSED FOR MANUAL TOGGLE")
            print("Please manually ENABLE aiDAPTIV on your target server now.")
            print("If you need to reboot, stop this script and run:")
            print(
                f"  python3 benchmark.py --stage aidaptiv --run-id {os.path.basename(self.results_dir)}")
            print("="*60)
            user_in = input("Press Enter to continue, or 'q' to quit >> ")
            if user_in.lower().strip() == 'q':
                print("👋 Exiting benchmark early.")
                return

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
    args = parser.parse_args()

    with open(args.config) as f:
        conf = yaml.safe_load(f)

    suite = BenchmarkSuite(conf, args.run_id)
    suite.run(args.stage)
