import re
import subprocess
import threading
import time
import csv
import psutil
import shutil
import os

import platform

# Try importing pynvml for NVIDIA support, but skip on macOS
try:
    if platform.system() == "Darwin":
        HAS_NVML = False
    else:
        import pynvml
        HAS_NVML = True
except ImportError:
    HAS_NVML = False


import requests


class TelemetryCollector:
    def __init__(self, output_path: str, interval_sec: float = 1.0, sidecar_url: str = None, storage_device: str = "disk0", model_name: str = "Unknown"):
        self.output_path = output_path
        self.interval_sec = interval_sec
        self.sidecar_url = sidecar_url
        self.storage_device = storage_device
        self.model_name = model_name
        self.status_msg = "Initializing..."

        self.running = False
        # ... (rest of init)

    def set_status(self, msg: str):
        self.status_msg = msg

    def set_tps(self, tps: float):
        self.current_tps = tps

    def _push_to_sidecar(self, now, ram_used, ram_total, vram_used, vram_total, t3_read, t3_write, os_read, os_write, cpu, tps):
        if not self.sidecar_url:
            return
        try:
            payload = {
                "timestamp": now,
                "status": self.status_msg,
                "system": {"ram_used_gb": ram_used, "ram_total_gb": ram_total, "cpu_pct": cpu},
                "gpu": {"vram_used_gb": vram_used, "vram_total_gb": vram_total},
                "disk": {"read_mb_s": t3_read, "write_mb_s": t3_write},
                "os_disk": {"read_mb_s": os_read, "write_mb_s": os_write},
                "app": {"tps": tps, "model": self.model_name}
            }
            requests.post(f"{self.sidecar_url}/update",
                          json=payload, timeout=0.1)
        except:
            pass

    def start(self):
        if self.running:
            return

        self.running = True
        self._start_time = time.time()

        # Open CSV and write header
        self._file = open(self.output_path, 'w', newline='')
        self._writer = csv.writer(self._file)
        self._writer.writerow([
            "timestamp", "elapsed_sec",
            "ram_used_gb", "ram_total_gb",
            "vram_used_gb", "vram_total_gb",
            "disk_read_mb_s", "disk_write_mb_s",
            "cpu_pct"
        ])

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"📊 Telemetry started. Logging to {self.output_path}")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join()
        if self._file:
            self._file.close()

        if HAS_NVML:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
        print("📊 Telemetry stopped.")

    def _get_mac_gpu_util(self):
        """
        Uses active polling of powermetrics to get GPU stats.
        Requires sudo.
        """
        try:
            # We use a quick sample (10ms) to minimize blocking
            # This is expensive, so maybe don't do it every single loop if loop is fast.
            # But we need real-time.
            cmd = ["sudo", "powermetrics", "-i",
                   "50", "-n", "1", "-s", "gpu_power"]
            res = subprocess.run(cmd, capture_output=True,
                                 text=True, timeout=1)

            # Parse output
            # GPU Active Residency:  12.50%
            # GPU Power: 432 mW
            output = res.stdout

            util = 0.0
            power = 0.0

            # Regex for Residency (Mac M4 specific 'GPU HW active residency')
            m_util = re.search(
                r"GPU HW active residency:\s+([\d\.]+)%", output, re.IGNORECASE)
            if not m_util:
                # Fallback for older Macs
                m_util = re.search(
                    r"GPU active residency:\s+([\d\.]+)%", output, re.IGNORECASE)

            if m_util:
                util = float(m_util.group(1))

            # Regex for Power
            m_pow = re.search(
                r"GPU Power:\s+([\d]+)\s*mW", output, re.IGNORECASE)
            if m_pow:
                power = float(m_pow.group(1)) / 1000.0  # Convert to Watts

            return util, power
        except:
            return 0.0, 0.0

    def _get_gpu_metrics(self):
        used = 0.0
        total = 0.0

        if HAS_NVML:
            try:
                count = pynvml.nvmlDeviceGetCount()
                for i in range(count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    used += mem.used
                    total += mem.total
            except:
                pass
            return used / (1024**3), total / (1024**3)

        # MacOS / Non-NVIDIA Fallback:
        # Use simple heuristic + Model Size Offset

        # Approximate Model Weights (since they often hide in Wired/Metal)
        # Add to RSS for a realistic "Active AI Memory"
        MODEL_SIZES = {
            '8b': 5.5,
            '7b': 5.0,
            '13b': 8.0,
            '33b': 18.0,
            '70b': 40.0,
            'llava': 7.0,  # Visual models usually larger
            'moe': 20.0
        }

        base_gb = 0.0
        mn = self.model_name.lower()
        for k, v in MODEL_SIZES.items():
            if k in mn:
                base_gb = v
                break

        # Scrape Process RSS (Context + Overhead)
        rss_used = 0.0
        try:
            for proc in psutil.process_iter(['name', 'memory_info', 'cmdline']):
                try:
                    p_info = proc.info
                    if not p_info['memory_info']:
                        continue

                    name = p_info['name'].lower()

                    # Logic: Catch 'ollama', 'runner' (the model process), and 'python'
                    if 'ollama' in name or 'runner' in name or 'python' in name:
                        rss_used += p_info['memory_info'].rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except:
            pass

        rss_gb = rss_used / (1024**3)
        total_ai_gb = base_gb + rss_gb

        # Return as GB. For Total, just use System Total since it's Unified.
        return total_ai_gb, psutil.virtual_memory().total / (1024**3)

    def _get_disk_io(self):
        try:
            per_disk = psutil.disk_io_counters(perdisk=True)
            t3_r, t3_w = 0, 0

            # Tier 3 (Target Device)
            if self.storage_device in per_disk:
                t3_r = per_disk[self.storage_device].read_bytes
                t3_w = per_disk[self.storage_device].write_bytes

            # Total System
            tot = psutil.disk_io_counters()

            # OS/Swap = Total - Tier 3
            # We use max(0, ...) to prevent negative spikes if counters reset or desync
            os_r = max(0, tot.read_bytes - t3_r)
            os_w = max(0, tot.write_bytes - t3_w)

            return t3_r, t3_w, os_r, os_w
        except:
            return 0, 0, 0, 0

    def _loop(self):
        last_t3_r, last_t3_w, last_os_r, last_os_w = self._get_disk_io()
        last_time = time.time()

        while self.running:
            now = time.time()
            dt = now - last_time
            if dt < 0.1:
                time.sleep(0.1)
                continue

            elapsed = now - self._start_time

            # System Metrics
            ram = psutil.virtual_memory()
            ram_used = ram.used / (1024**3)
            ram_total = ram.total / (1024**3)

            # GPU Compute & Power
            gpu_util = 0.0
            gpu_power = 0.0

            if not HAS_NVML:
                # Poll Mac
                gpu_util, gpu_power = self._get_mac_gpu_util()
            else:
                # NVML Logic (Future DGX)
                # handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                # gpu_util = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
                # gpu_power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
                pass

            # Using Host CPU only if GPU is 0 (fallback) or as separate metric?
            # User wants "Compute Workload".
            compute_load = gpu_util

            # GPU Metrics (VRAM)
            vram_used, vram_total = self._get_gpu_metrics()

            # Disk IO (Tier 3 vs OS)
            curr_t3_r, curr_t3_w, curr_os_r, curr_os_w = self._get_disk_io()

            # Tier 3 Rates
            t3_read_mb_s = ((curr_t3_r - last_t3_r) / (1024**2)) / dt
            t3_write_mb_s = ((curr_t3_w - last_t3_w) / (1024**2)) / dt

            # OS Rates
            os_read_mb_s = ((curr_os_r - last_os_r) / (1024**2)) / dt
            os_write_mb_s = ((curr_os_w - last_os_w) / (1024**2)) / dt

            last_t3_r, last_t3_w = curr_t3_r, curr_t3_w
            last_os_r, last_os_w = curr_os_r, curr_os_w
            last_time = now

            # Write row
            if self._writer:
                self._writer.writerow([
                    round(now, 2), round(elapsed, 2),
                    round(ram_used, 2), round(ram_total, 2),
                    round(vram_used, 2), round(vram_total, 2),
                    round(t3_read_mb_s, 2), round(t3_write_mb_s, 2),
                    round(compute_load, 1)
                ])
                self._file.flush()

            # Update Sidecar
            # Passing compute_load as 'cpu' argument to avoid changing signature again too much
            # But the Sidecar will label it "AI Compute Load"
            self._push_to_sidecar(
                now, ram_used, ram_total,
                vram_used, vram_total,
                t3_read_mb_s, t3_write_mb_s,
                os_read_mb_s, os_write_mb_s,
                compute_load, getattr(self, 'current_tps', 0.0)
            )

            time.sleep(self.interval_sec)
