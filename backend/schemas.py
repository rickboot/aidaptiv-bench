from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal, Union, Any

# --- Telemetry & Metrics Schemas ---


class SystemMetrics(BaseModel):
    ram_total_gb: float
    ram_used_gb: float
    ram_available_gb: float
    swap_used_gb: float
    cpu_util_pct: float
    page_faults_major: Optional[float] = None


class GpuMetrics(BaseModel):
    vram_total_gb: float
    vram_used_gb: float
    util_pct: float
    mem_util_pct: float
    power_w: Optional[float] = None
    temp_c: Optional[float] = None


class DiskMetrics(BaseModel):
    read_bps: float
    write_bps: float
    read_iops: float
    write_iops: float
    lat_p95_ms: Optional[float] = None
    queue_depth: Optional[float] = None


class AppMetrics(BaseModel):
    req_count: int = 0
    concurrent_reqs: int = 0
    ttft_ms_p50: float = 0.0
    ttft_ms_p95: float = 0.0
    tpot_ms_p50: float = 0.0
    tpot_ms_p95: float = 0.0
    throughput_tok_s: float = 0.0
    errors_total: int = 0
    oom_events: int = 0


class AidaptivMetrics(BaseModel):
    cache_hit_rate: Optional[float] = None
    ssd_cache_used_gb: Optional[float] = None
    evictions_total: Optional[int] = None
    prefetch_total: Optional[int] = None
    kv_persist_bytes: Optional[int] = None


class Snapshot(BaseModel):
    timestamp: float
    system: SystemMetrics
    gpu: GpuMetrics
    disk: DiskMetrics
    app: AppMetrics
    aidaptiv: AidaptivMetrics

# --- Config Schemas ---


class RuntimeConfig(BaseModel):
    backend: Literal["vllm", "llama.cpp"]
    endpoint: str = "http://localhost:8000/v1"
    model: str
    quant: Optional[str] = None
    max_tokens: int = 512
    temperature: float = 0.0


class AidaptivConfig(BaseModel):
    enabled: bool = True
    mode: str = "default"
    hints: Dict[str, Union[str, bool, int]] = {}


class PressureConfig(BaseModel):
    ram_limit_gb: Optional[float] = None
    vram_reserve_gb: Optional[float] = None
    swap_enabled: bool = False


class TelemetryConfig(BaseModel):
    interval_ms: int = 500
    nvme_device: Optional[str] = None


class ScenarioConfig(BaseModel):
    id: str
    params: Dict[str, Any] = {}


class ExportConfig(BaseModel):
    write_csv: bool = True
    write_parquet: bool = True
    charts: List[str] = []


class BenchmarkConfig(BaseModel):
    system_profile: str
    runtime: RuntimeConfig
    aidaptiv: AidaptivConfig
    pressure: PressureConfig
    telemetry: TelemetryConfig
    scenario: ScenarioConfig
    export: ExportConfig
