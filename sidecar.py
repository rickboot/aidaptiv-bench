from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn
import pandas as pd
import json
import os
import time
from backend.metrics import SystemMonitor
from backend.schemas import Snapshot
import threading

app = FastAPI(title="aiDAPTIV Telemetry Sidecar")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <html>
        <head>
            <title>aiDAPTIV Live Monitor</title>
            <meta http-equiv="refresh" content="1">
            <style>
                body { font-family: monospace; background: #111; color: #0f0; padding: 20px; }
                .metric { font-size: 1.2em; margin: 10px 0; }
                h1 { color: #fff; }
                .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            </style>
        </head>
        <body>
            <h1>aiDAPTIV Sidecar Dashboard</h1>
            <div id="status">Connecting...</div>
            <div class="grid">
                <div>
                    <h2>System Memory</h2>
                    <pre id="mem">-</pre>
                </div>
                <div>
                    <h2>GPU VRAM</h2>
                    <pre id="vram">-</pre>
                </div>
                <div>
                    <h2>SSD I/O</h2>
                    <pre id="disk">-</pre>
                </div>
                <div>
                    <h2>App Throughput</h2>
                    <pre id="app">-</pre>
                </div>
            </div>
            <script>
                async function update() {
                    try {
                        const res = await fetch('/snapshot');
                        const data = await res.json();
                        
                        document.getElementById('status').innerText = "Running | TS: " + data.timestamp.toFixed(2);
                        
                        document.getElementById('mem').innerText = 
                            `Total: ${data.system.ram_total_gb.toFixed(1)} GB\n` +
                            `Used:  ${data.system.ram_used_gb.toFixed(1)} GB`;
                            
                        document.getElementById('vram').innerText = 
                            `Total: ${data.gpu.vram_total_gb.toFixed(1)} GB\n` +
                            `Used:  ${data.gpu.vram_used_gb.toFixed(1)} GB\n` +
                            `Util:  ${data.gpu.util_pct}%`;
                            
                        document.getElementById('disk').innerText = 
                            `Read:  ${(data.disk.read_bps / 1024 / 1024).toFixed(1)} MB/s\n` +
                            `Write: ${(data.disk.write_bps / 1024 / 1024).toFixed(1)} MB/s`;
                            
                        document.getElementById('app').innerText = 
                            `TPS:   ${data.app.throughput_tok_s.toFixed(1)}\n` +
                            `Err:   ${data.app.errors_total}`;
                    } catch (e) {
                         document.getElementById('status').innerText = "Disconnected";
                    }
                }
                setInterval(update, 500);
            </script>
        </body>
    </html>
    """


# Global State
monitor = SystemMonitor(poll_interval=0.5)
active_run_id = None
timeseries_data = []
ts_lock = threading.Lock()
output_dir = "results"


@app.on_event("startup")
def startup_event():
    monitor.start_monitoring()


@app.on_event("shutdown")
def shutdown_event():
    monitor.stop_monitoring()


@app.get("/health")
def health():
    return {"status": "ok", "run_id": active_run_id}


@app.get("/snapshot", response_model=Snapshot)
def get_snapshot():
    # Metrics monitor returns dict, schema validation handles structure
    data = monitor.get_latest_metrics()

    # Fill in defaults/dummy values for nested keys if missing to satisfy schema
    # (The updated metrics.py should align, but safety check)
    if "aidaptiv" not in data:
        data["aidaptiv"] = {}

    return data


@app.get("/metrics")
def get_prometheus_metrics():
    """Simple Prometheus text format export"""
    data = monitor.get_latest_metrics()
    lines = []

    # System
    s = data.get("system", {})
    lines.append(f"system_ram_used_gb {s.get('ram_used_gb', 0)}")
    lines.append(f"system_cpu_util_pct {s.get('cpu_util_pct', 0)}")

    # GPU
    g = data.get("gpu", {})
    lines.append(f"gpu_vram_used_gb {g.get('vram_used_gb', 0)}")
    lines.append(f"gpu_util_pct {g.get('util_pct', 0)}")

    # Disk
    d = data.get("disk", {})
    lines.append(f"disk_read_bps {d.get('read_bps', 0)}")
    lines.append(f"disk_write_bps {d.get('write_bps', 0)}")

    return "\n".join(lines)


@app.post("/runs/{run_id}/start")
def start_run(run_id: str):
    global active_run_id, timeseries_data
    active_run_id = run_id
    with ts_lock:
        timeseries_data = []  # Reset buffer

    # Start a background logger for this run
    threading.Thread(target=_background_logger,
                     args=(run_id,), daemon=True).start()
    return {"status": "started", "run_id": run_id}


@app.post("/runs/{run_id}/stop")
def stop_run(run_id: str):
    global active_run_id
    if active_run_id == run_id:
        _flush_to_disk(run_id)
        active_run_id = None
    return {"status": "stopped"}


def _background_logger(run_id: str):
    """
    Polls the snapshot every monitor interval and appends to in-memory list.
    Periodically flushes to disk (parquet) to avoid OOMing the sidecar itself.
    """
    while active_run_id == run_id:
        snap = monitor.get_latest_metrics()

        # Flatten for tabular storage
        flat = {"timestamp": snap["timestamp"]}
        for category in ["system", "gpu", "disk", "app", "aidaptiv"]:
            for k, v in snap.get(category, {}).items():
                flat[f"{category}_{k}"] = v

        with ts_lock:
            timeseries_data.append(flat)

        time.sleep(monitor.poll_interval)

        # Flush every 100 samples ~ 50 seconds
        if len(timeseries_data) > 100:
            _flush_to_disk(run_id)


def _flush_to_disk(run_id: str):
    global timeseries_data
    with ts_lock:
        if not timeseries_data:
            return
        df = pd.DataFrame(timeseries_data)
        timeseries_data = []  # Clear buffer

    # Simplify path logic for V1
    run_dir = os.path.join(output_dir, "latest", run_id)
    # In real impl, would be date/run_id, handled by runner passing full path or managing logs
    # For sidecar, let's just write to a temp file or configurable path
    # Actually, sidecar spec says "Writes timeseries to file during runs"

    # Let's assume runner mounts/shares a dir or we just dump to local `results/`
    os.makedirs(os.path.join(output_dir, run_id), exist_ok=True)
    file_path = os.path.join(output_dir, run_id, "timeseries.parquet")

    # Append if exists? Parquet appending is tricky.
    # V1 Simple: Write separate chunks or just overwrite for now (since we flush continuously)
    # Better: Write `part-timestamp.parquet`

    fname = f"part-{int(time.time()*1000)}.parquet"
    df.to_parquet(os.path.join(output_dir, run_id, fname))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
