import threading
import time
import csv
import psutil
import shutil
import os

# Try importing pynvml for NVIDIA support
try:
    import pynvml
    HAS_NVML = True
except ImportError:
    HAS_NVML = False


class TelemetryCollector:
    def __init__(self, output_path: str, interval_sec: float = 1.0):
        self.output_path = output_path
        self.interval_sec = interval_sec
        self.running = False
        self._thread = None
        self._file = None
        self._writer = None
        self._start_time = 0

        # Init NVML if available
        global HAS_NVML
        if HAS_NVML:
            try:
                pynvml.nvmlInit()
            except:
                HAS_NVML = False

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

    def _get_vram(self):
        used = 0.0
        total = 0.0
        if HAS_NVML:
            try:
                # Aggregate all GPUs
                count = pynvml.nvmlDeviceGetCount()
                for i in range(count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    used += mem.used
                    total += mem.total
            except:
                pass
        return used / (1024**3), total / (1024**3)

    def _loop(self):
        # Init Disk IO counters
        last_io = psutil.disk_io_counters()
        last_time = time.time()

        while self.running:
            now = time.time()
            elapsed = now - self._start_time

            # RAM
            mem = psutil.virtual_memory()
            ram_used = mem.used / (1024**3)
            ram_total = mem.total / (1024**3)

            # VRAM
            vram_used, vram_total = self._get_vram()

            # Disk Rate Calculation
            curr_io = psutil.disk_io_counters()
            dt = now - last_time
            if dt < 0.001:
                dt = 0.001  # Prevent divide by zero

            read_mb_s = (curr_io.read_bytes -
                         last_io.read_bytes) / (1024**2) / dt
            write_mb_s = (curr_io.write_bytes -
                          last_io.write_bytes) / (1024**2) / dt

            last_io = curr_io
            last_time = now

            # CPU
            cpu = psutil.cpu_percent(interval=None)

            # Write row
            if self._writer:
                self._writer.writerow([
                    round(now, 2), round(elapsed, 2),
                    round(ram_used, 2), round(ram_total, 2),
                    round(vram_used, 2), round(vram_total, 2),
                    round(read_mb_s, 2), round(write_mb_s, 2),
                    round(cpu, 1)
                ])
                self._file.flush()

            time.sleep(self.interval_sec)
