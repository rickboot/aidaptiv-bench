from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import json

app = FastAPI(title="aiDAPTIV Live Dashboard")

# Global State
current_snapshot = {
    "timestamp": 0,
    "status": "Waiting...",
    "system": {"ram_used_gb": 0, "ram_total_gb": 0, "cpu_pct": 0},
    "gpu": {"vram_used_gb": 0, "vram_total_gb": 0, "power_w": 0},
    "disk": {"read_mb_s": 0, "write_mb_s": 0},
    "os_disk": {"read_mb_s": 0, "write_mb_s": 0},
    "app": {"tps": 0.0, "model": "Unknown"}
}


class DashboardUpdate(BaseModel):
    timestamp: float
    status: str
    system: dict
    gpu: dict
    disk: dict
    os_disk: dict
    app: dict


@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>aiDAPTIV Live Monitor</title>
        <style>
            body { font-family: 'Segoe UI', monospace; background: #111; color: #0f0; padding: 20px; margin: 0; }
            .container { max_width: 1200px; margin: 0 auto; }
            h1 { color: #fff; border-bottom: 2px solid #333; padding-bottom: 10px; }
            .status-bar { background: #222; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #fff; font-size: 1.2em; border-left: 5px solid #0f0; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; }
            .card { background: #1a1a1a; padding: 20px; border-radius: 8px; border: 1px solid #333; }
            .card h2 { margin-top: 0; color: #aaa; font-size: 1em; text-transform: uppercase; letter-spacing: 1px; }
            .big-val { font-size: 2.5em; font-weight: bold; color: #fff; }
            .sub-val { color: #666; font-size: 0.9em; }
            .chart-ph { height: 100px; background: #111; margin-top: 10px; border: 1px dashed #333; display: flex; align-items: center; justify-content: center; color: #444; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>aiDAPTIV Bench Live</h1>
            <div id="status" class="status-bar">Waiting for Telemetry...</div>
            
            <div class="grid">
                <div class="card">
                    <h2>Tier 1: Active AI Memory</h2>
                    <div id="vram_val" class="big-val">0.0 GB</div>
                    <div id="vram_sub" class="sub-val">Logical AI Load</div>
                </div>
                <div class="card">
                    <h2>Tier 2: Host RAM</h2>
                    <div id="ram_val" class="big-val">0.0 GB</div>
                    <div id="ram_sub" class="sub-val">of 0.0 GB Total</div>
                </div>
                <div class="card">
                    <h2>Tier 3: aiDAPTIV</h2>
                    <div id="disk_val" class="big-val">0 MB/s</div>
                    <div id="disk_sub" class="sub-val">Target Device I/O</div>
                </div>
                <div class="card">
                    <h2>OS / Swap</h2>
                    <div id="os_val" class="big-val">0 MB/s</div>
                    <div id="os_sub" class="sub-val">System I/O</div>
                </div>
                <div class="card">
                    <h2>Throughput</h2>
                    <div id="tps_val" class="big-val">0.0</div>
                    <div id="tps_sub" class="sub-val">Tokens / Sec</div>
                </div>
                <div class="card">
                    <h2>AI Compute Load</h2>
                    <div id="cpu_val" class="big-val">0%</div>
                    <div id="cpu_sub" class="sub-val">GPU / NPU Utilization</div>
                </div>
            </div>
        </div>

        <script>
            async function poll() {
                try {
                    const res = await fetch('/snapshot');
                    const data = await res.json();
                    
                    document.getElementById('status').innerText = data.status;
                    
                    // RAM
                    document.getElementById('ram_val').innerText = data.system.ram_used_gb.toFixed(1) + " GB";
                    document.getElementById('ram_sub').innerText = "of " + data.system.ram_total_gb.toFixed(1) + " GB";
                    
                    // Tier 1 (HBM/GPU) -> Now "Active Workset"
                    const vram = data.gpu.vram_used_gb;
                    document.getElementById('vram_val').innerText = vram.toFixed(1) + " GB";
                    
                    if (data.app && data.app.model) {
                         document.getElementById('vram_sub').innerText = "Model: " + data.app.model;
                    } else {
                         document.getElementById('vram_sub').innerText = "Logical AI Load";
                    }
                    
                    // Tier 3 (aiDAPTIV)
                    const mkIO = (d) => {
                         const r = d.read_mb_s;
                         const w = d.write_mb_s;
                         return [(r+w).toFixed(1) + " MB/s", `R: ${r.toFixed(1)} | W: ${w.toFixed(1)}`]
                    };
                    
                    const [t3_val, t3_sub] = mkIO(data.disk);
                    document.getElementById('disk_val').innerText = t3_val;
                    document.getElementById('disk_sub').innerText = t3_sub;
                    
                    // OS / Swap
                    if (data.os_disk) {
                        const [os_val, os_sub] = mkIO(data.os_disk);
                        document.getElementById('os_val').innerText = os_val;
                        document.getElementById('os_sub').innerText = os_sub;
                    }
                    
                    // TPS
                    document.getElementById('tps_val').innerText = data.app.tps.toFixed(1);
                    
                    // CPU
                    document.getElementById('cpu_val').innerText = data.system.cpu_pct + "%";
                } catch(e) {
                    console.log(e);
                }
            }
            setInterval(poll, 1000);
        </script>
    </body>
    </html>
    """


@app.get("/snapshot")
def get_snapshot():
    return current_snapshot


@app.post("/update")
def receive_update(update: DashboardUpdate):
    global current_snapshot
    current_snapshot = update.dict()
    return {"status": "ok"}


if __name__ == "__main__":
    print("🖥️  Starting Display Server on http://localhost:8081")
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="error")
