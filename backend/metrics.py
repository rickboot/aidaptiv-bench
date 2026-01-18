import time
import psutil
import threading
from typing import Dict, Any

# Try importing pynvml, handle missing (e.g. on generic Mac/AMD)
try:
    import pynvml
    HAS_NVML = True
except ImportError:
    HAS_NVML = False


class SystemMonitor:
    def __init__(self, poll_interval: float = 0.5, disk_device: str = None):
        self.poll_interval = poll_interval
        self.disk_device = disk_device
        self.running = False
        self._thread = None
        # Raw counters for calculating rates
        self._last_disk_read = 0
        self._last_disk_write = 0
        self._last_disk_time = 0

        # Current state container
        self.snapshot: Dict[str, Any] = {
            "timestamp": 0,
            "system": {},
            "gpu": {},
            "disk": {},
            "app": {  # To be populated by external push/pull or shared mem
                "req_count": 0, "concurrent_reqs": 0,
                "ttft_ms_p50": 0.0, "ttft_ms_p95": 0.0,
                "tpot_ms_p50": 0.0, "tpot_ms_p95": 0.0,
                "throughput_tok_s": 0.0, "errors_total": 0, "oom_events": 0
            },
            "aidaptiv": {}
        }

    def _init_nvml(self):
        if HAS_NVML:
            try:
                pynvml.nvmlInit()
                return True
            except pynvml.NVMLError:
                return False
        return False

    def _get_gpu_metrics(self):
        metrics = {
            "vram_total_gb": 0.0, "vram_used_gb": 0.0,
            "util_pct": 0.0, "mem_util_pct": 0.0,
            "power_w": None, "temp_c": None
        }

        if HAS_NVML:
            try:
                # Assuming single GPU focus for V1 or aggregation; taking device 0 for now
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)

                metrics["vram_total_gb"] = mem_info.total / (1024**3)
                metrics["vram_used_gb"] = mem_info.used / (1024**3)
                metrics["util_pct"] = util.gpu
                metrics["mem_util_pct"] = util.memory

                try:
                    metrics["power_w"] = pynvml.nvmlDeviceGetPowerUsage(
                        handle) / 1000.0
                except:
                    pass
                try:
                    metrics["temp_c"] = pynvml.nvmlDeviceGetTemperature(
                        handle, pynvml.NVML_TEMPERATURE_GPU)
                except:
                    pass
            except Exception:
                pass
        return metrics

    def _get_disk_metrics(self):
        """Calculates IOPS and BPS since last poll"""
        metrics = {
            "read_bps": 0.0, "write_bps": 0.0,
            "read_iops": 0.0, "write_iops": 0.0,
            "lat_p95_ms": None, "queue_depth": None
        }

        try:
            # If specific device not set, might aggregate or pick first?
            # For now, using system-wide counters if device is None, or specific if psutil supports
            # psutil.disk_io_counters(perdisk=True)

            counters = psutil.disk_io_counters(
                perdisk=True if self.disk_device else False)

            current_read = 0
            current_write = 0
            current_reads_count = 0
            current_writes_count = 0

            if self.disk_device and self.disk_device in counters:
                io = counters[self.disk_device]
                current_read = io.read_bytes
                current_write = io.write_bytes
                current_reads_count = io.read_count
                current_writes_count = io.write_count
            elif not self.disk_device:
                io = counters  # global if perdisk=False
                current_read = io.read_bytes
                current_write = io.write_bytes
                current_reads_count = io.read_count
                current_writes_count = io.write_count

            now = time.time()
            delta = now - self._last_disk_time

            if delta > 0 and self._last_disk_time > 0:
                metrics["read_bps"] = (
                    current_read - self._last_read_bytes) / delta
                metrics["write_bps"] = (
                    current_write - self._last_write_bytes) / delta
                metrics["read_iops"] = (
                    current_reads_count - self._last_read_count) / delta
                metrics["write_iops"] = (
                    current_writes_count - self._last_write_count) / delta

            self._last_read_bytes = current_read
            self._last_write_bytes = current_write
            self._last_read_count = current_reads_count
            self._last_write_count = current_writes_count
            self._last_disk_time = now

        except Exception:
            pass

        return metrics

    def _poll_loop(self):
        self._init_nvml()
        self._last_disk_time = time.time()
        # Init counters
        if self.disk_device:
            c = psutil.disk_io_counters(perdisk=True).get(self.disk_device)
        else:
            c = psutil.disk_io_counters()

        if c:
            self._last_read_bytes = c.read_bytes
            self._last_write_bytes = c.write_bytes
            self._last_read_count = c.read_count
            self._last_write_count = c.write_count

        while self.running:
            # System
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            self.snapshot["system"] = {
                "ram_total_gb": mem.total / (1024**3),
                "ram_used_gb": mem.used / (1024**3),
                "ram_available_gb": mem.available / (1024**3),
                "swap_used_gb": swap.used / (1024**3),
                "cpu_util_pct": psutil.cpu_percent(interval=None),
                # Hard to get realtime via psutil easily without OS specific calls
                "page_faults_major": None
            }

            # GPU
            self.snapshot["gpu"] = self._get_gpu_metrics()

            # Disk
            self.snapshot["disk"] = self._get_disk_metrics()

            self.snapshot["timestamp"] = time.time()
            time.sleep(self.poll_interval)

    def start_monitoring(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        print(f"System Monitoring Started (Interval: {self.poll_interval}s).")

    def stop_monitoring(self):
        self.running = False
        if self._thread:
            self._thread.join()
        if HAS_NVML:
            try:
                pynvml.nvmlShutdown()
            except:
                pass

    def get_latest_metrics(self) -> Dict[str, Any]:
        return self.snapshot.copy()
