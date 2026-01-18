import argparse
import sys
import yaml
import time
import os
import subprocess
import requests
import json
from backend.schemas import BenchmarkConfig
from backend.hardware import DeviceDetector

SIDECAR_URL = "http://localhost:8081"


class BenchRunner:
    def __init__(self, config_path: str, aidaptiv_override: str = None):
        self.config_path = config_path
        self.config = self._load_config(config_path)

        # Apply override
        if aidaptiv_override:
            if aidaptiv_override.lower() == "on":
                self.config.aidaptiv.enabled = True
            elif aidaptiv_override.lower() == "off":
                self.config.aidaptiv.enabled = False

        self.run_id = f"run_{int(time.time())}_{self.config.scenario.id}"
        self.output_dir = os.path.join("results", "latest", self.run_id)
        os.makedirs(self.output_dir, exist_ok=True)

        self.detector = DeviceDetector()

    def _load_config(self, path: str) -> BenchmarkConfig:
        with open(path, "r") as f:
            raw = yaml.safe_load(f)
        return BenchmarkConfig(**raw)

    def check_sidecar(self):
        """Verifies telemetry sidecar is up."""
        try:
            r = requests.get(f"{SIDECAR_URL}/health", timeout=2)
            if r.status_code == 200:
                print("✅ Telemetry Sidecar is active.")
                return True
        except requests.exceptions.ConnectionError:
            print(
                "❌ Telemetry Sidecar NOT found. Please run 'python sidecar.py' in a separate terminal.")
            return False
        return False

    def start_run(self):
        print(f"🚀 Starting Benchmark Run: {self.run_id}")
        print(f"📋 Scenario: {self.config.scenario.id}")
        print(
            f"⚙️  aiDAPTIV: {'ENABLED' if self.config.aidaptiv.enabled else 'DISABLED'}")

        # 1. Notify Sidecar
        try:
            requests.post(f"{SIDECAR_URL}/runs/{self.run_id}/start")
        except Exception:
            print("⚠️ Failed to start sidecar logging.")

        # 2. Dump Effective Config
        with open(os.path.join(self.output_dir, "config_effective.yaml"), "w") as f:
            yaml.dump(self.config.model_dump(), f)

        # 3. Create Manifest
        manifest = {
            "run_id": self.run_id,
            "timestamp": time.time(),
            "config": self.config.model_dump(),
            "system": self.detector.get_system_info(),
            "phison_storage": self.detector.detect_phison_storage()
        }
        with open(os.path.join(self.output_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)

        # 4. Execute Scenario (Placeholder for now)
        try:
            self.execute_scenario()
            status = "success"
        except KeyboardInterrupt:
            status = "aborted"
        except Exception as e:
            print(f"💥 Error: {e}")
            status = "error"

        # 5. Stop Sidecar
        try:
            requests.post(f"{SIDECAR_URL}/runs/{self.run_id}/stop")
        except:
            pass

        print(f"🏁 Run Finished. Status: {status}")

    def execute_scenario(self):
        print("▶️ Executing Scenario Logic...")

        scenario_id = self.config.scenario.id
        scenario_class = None

        # Simple registry for V1
        if scenario_id.lower().startswith("s1"):
            from scenarios.s1_oom_finder import S1_OOMFinder
            scenario_class = S1_OOMFinder
        else:
            print(f"⚠️ Unknown Scenario ID: {scenario_id}")
            return

        if scenario_class:
            scenario = scenario_class(self.config)
            results = scenario.run()

            # Merge results into summary
            with open(os.path.join(self.output_dir, "summary.json"), "w") as f:
                json.dump(results, f, indent=2)

            print(f"✅ Scenario Complete. Results: {results}")


def main():
    parser = argparse.ArgumentParser(
        description="Phison aiDAPTIV Bench Runner")
    subparsers = parser.add_subparsers(dest="command")

    # Run Command
    run_parser = subparsers.add_parser(
        "run", help="Execute a benchmark scenario")
    run_parser.add_argument("--config", required=True,
                            help="Path to YAML config")
    run_parser.add_argument(
        "--aidaptiv", choices=["on", "off"], help="Override aiDAPTIV setting")

    args = parser.parse_args()

    if args.command == "run":
        if not os.path.exists(args.config):
            print(f"Config file not found: {args.config}")
            sys.exit(1)

        runner = BenchRunner(args.config, args.aidaptiv)
        if runner.check_sidecar():
            runner.start_run()
        else:
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
