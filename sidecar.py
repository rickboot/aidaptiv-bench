from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import json
import os
import glob

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
        <title>aiDAPTIV Bench</title>
        <style>
            body { font-family: 'Segoe UI', monospace; background: #111; color: #eee; padding: 0; margin: 0; }
            .navbar { background: #222; padding: 10px 20px; border-bottom: 1px solid #333; display: flex; align-items: center; }
            .navbar h1 { margin: 0; font-size: 1.2em; color: #fff; margin-right: 30px; letter-spacing: 1px; }
            .nav-btn { background: transparent; border: none; color: #888; cursor: pointer; font-size: 1em; padding: 10px; margin-right: 10px; text-transform: uppercase; }
            .nav-btn.active { color: #0f0; border-bottom: 2px solid #0f0; }
            .nav-btn:hover { color: #fff; }

            .container { max_width: 1200px; margin: 20px auto; padding: 0 20px; }
            .status-bar { background: #222; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #fff; font-size: 1.2em; border-left: 5px solid #0f0; }
            
            /* Dashboard Grid */
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; }
            .card { background: #1a1a1a; padding: 20px; border-radius: 8px; border: 1px solid #333; }
            .card h2 { margin-top: 0; color: #aaa; font-size: 1em; text-transform: uppercase; letter-spacing: 1px; }
            .big-val { font-size: 2.5em; font-weight: bold; color: #fff; }
            .sub-val { color: #666; font-size: 0.9em; }

            /* Reports Table */
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th { text-align: left; border-bottom: 1px solid #444; padding: 10px; color: #888; }
            td { padding: 10px; border-bottom: 1px solid #222; }
            tr:hover { background: #1a1a1a; cursor: pointer; }
            .badge { padding: 3px 8px; border-radius: 4px; font-size: 0.8em; }
            .pass { background: #004400; color: #0f0; }
            .fail { background: #440000; color: #f00; }

            /* Report Detail */
            .back-btn { background: #333; color: #fff; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; margin-bottom: 20px; }
            .back-btn:hover { background: #444; }
            pre { background: #1a1a1a; padding: 15px; overflow: auto; border-radius: 5px; border: 1px solid #333; }
        </style>
    </head>
    <body>
        <div class="navbar">
            <h1>aiDAPTIV Bench</h1>
            <button class="nav-btn active" id="btn-dash" onclick="setView('dashboard')">Live Monitor</button>
            <button class="nav-btn" id="btn-reports" onclick="setView('reports')">Reports</button>
        </div>

        <!-- LIVE DASHBOARD -->
        <div id="view-dashboard" class="container">
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

        <!-- REPORTS VIEW -->
        <div id="view-reports" class="container" style="display:none">
            <div id="reports-list">
                <h2>Benchmark History</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Run ID / Date</th>
                            <th>Status</th>
                            <th>Total Time</th>
                            <th>Avg Latency</th>
                        </tr>
                    </thead>
                    <tbody id="reports-table-body">
                        <!-- JS Populated -->
                    </tbody>
                </table>
            </div>

            <div id="report-detail" style="display:none">
                <button class="back-btn" onclick="closeReport()">← Back to List</button>
                <div id="detail-content"></div>
                <h3>Raw Summary</h3>
                <pre id="detail-json"></pre>
            </div>
        </div>

        <script>
            let polling = true;

            function setView(view) {
                document.getElementById('view-dashboard').style.display = view === 'dashboard' ? 'block' : 'none';
                document.getElementById('view-reports').style.display = view === 'reports' ? 'block' : 'none';
                
                document.getElementById('btn-dash').className = view === 'dashboard' ? 'nav-btn active' : 'nav-btn';
                document.getElementById('btn-reports').className = view === 'reports' ? 'nav-btn active' : 'nav-btn';

                if (view === 'reports') {
                    loadReports();
                    polling = false;
                } else {
                    polling = true;
                }
            }

            async function loadReports() {
                const res = await fetch('/api/reports');
                const list = await res.json();
                const tbody = document.getElementById('reports-table-body');
                tbody.innerHTML = '';
                
                list.forEach(run => {
                    const tr = document.createElement('tr');
                    let summ = run.summary;
                    
                    // Format Date
                    let dateStr = run.id;
                    try {
                        if (run.id.length === 15) {
                            const y = run.id.substring(0, 4);
                            const m = run.id.substring(4, 6);
                            const d = run.id.substring(6, 8);
                            const hh = run.id.substring(9, 11);
                            const mm = run.id.substring(11, 13);
                            const ss = run.id.substring(13, 15);
                            dateStr = `${y}-${m}-${d} ${hh}:${mm}:${ss}`;
                        }
                    } catch (e) {}

                    let passVal = false;
                    let latVal = 0;
                    let totalTimeMs = 0;
                    let hasData = false;

                    // Handle Array (List of Context Steps)
                    if (Array.isArray(summ) && summ.length > 0) {
                        hasData = true;
                        // Check if all passed
                        passVal = summ.every(x => x.pass_rate_pct === 100.0);
                        // Avg Latency (of the whole run)
                        totalTimeMs = summ.reduce((acc, x) => acc + x.avg_latency_ms, 0);
                        latVal = totalTimeMs / summ.length;
                    } 
                    // Handle Dict (Future wrapper)
                    else if (summ && !Array.isArray(summ) && summ.avg_latency_ms) {
                        hasData = true;
                        passVal = summ.pass_rate === 1.0;
                        latVal = summ.avg_latency_ms;
                        totalTimeMs = latVal; // Single item
                    }

                    const latStr = hasData ? `${latVal.toFixed(0)} ms` : '-';
                    const timeStr = hasData ? `${(totalTimeMs/1000).toFixed(1)} s` : '-';
                    const passStr = hasData 
                        ? (passVal ? '<span class="badge pass">PASS</span>' : '<span class="badge fail">FAIL</span>')
                        : '<span class="badge" style="background:#333">NO DATA</span>';
                    
                    tr.innerHTML = `
                        <td>
                            <div style="font-weight:bold">${dateStr}</div>
                            <div style="font-size:0.8em; color:#666">${run.id}</div>
                        </td>
                        <td>${passStr}</td>
                        <td>${timeStr}</td>
                        <td>${latStr}</td>
                    `;
                    tr.onclick = () => loadReportDetail(run.id);
                    tbody.appendChild(tr);
                });
                
                document.getElementById('reports-list').style.display = 'block';
                document.getElementById('report-detail').style.display = 'none';
            }

            async function loadReportDetail(id) {
                const res = await fetch(`/api/reports/${id}`);
                const data = await res.json();
                
                document.getElementById('reports-list').style.display = 'none';
                document.getElementById('report-detail').style.display = 'block';
                
                const content = document.getElementById('detail-content');
                content.innerHTML = '';
                
                // Helper to render a table
                const renderTable = (title, rows) => {
                    if (!rows || rows.length === 0) return;
                    
                    let html = `<h3>${title}</h3><table><thead><tr><th>Context</th><th>Latency</th><th>Status</th></tr></thead><tbody>`;
                    
                    rows.forEach(r => {
                        const pass = r.pass_rate_pct === 100.0 ? '<span class="badge pass">PASS</span>' : '<span class="badge fail">FAIL</span>';
                        html += `<tr>
                            <td>${r.context}</td>
                            <td>${r.avg_latency_ms.toFixed(0)} ms</td>
                            <td>${pass}</td>
                        </tr>`;
                    });
                    html += `</tbody></table>`;
                    
                    const div = document.createElement('div');
                    div.style.marginBottom = "30px";
                    div.innerHTML = html;
                    content.appendChild(div);
                };
                
                renderTable("Baseline Results", data.baseline);
                renderTable("aiDAPTIV Results", data.aidaptiv);

                document.getElementById('detail-json').innerText = JSON.stringify(data, null, 2);
            }

            function closeReport() {
                document.getElementById('reports-list').style.display = 'block';
                document.getElementById('report-detail').style.display = 'none';
            }

            async function poll() {
                if (!polling) return;
                try {
                    const res = await fetch('/snapshot');
                    const data = await res.json();
                    
                    document.getElementById('status').innerText = data.status;
                    
                    // RAM
                    document.getElementById('ram_val').innerText = data.system.ram_used_gb.toFixed(1) + " GB";
                    document.getElementById('ram_sub').innerText = "of " + data.system.ram_total_gb.toFixed(1) + " GB";
                    
                    // Tier 1
                    document.getElementById('vram_val').innerText = data.gpu.vram_used_gb.toFixed(1) + " GB";
                    if (data.app && data.app.model) {
                         document.getElementById('vram_sub').innerText = "Model: " + data.app.model;
                    } else {
                         document.getElementById('vram_sub').innerText = "Logical AI Load";
                    }
                    
                    // Tier 3
                    const mkIO = (d) => {
                         const r = d.read_mb_s;
                         const w = d.write_mb_s;
                         return [(r+w).toFixed(1) + " MB/s", `R: ${r.toFixed(1)} | W: ${w.toFixed(1)}`]
                    };
                    const [t3_val, t3_sub] = mkIO(data.disk);
                    document.getElementById('disk_val').innerText = t3_val;
                    document.getElementById('disk_sub').innerText = t3_sub;
                    
                    // OS
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


@app.get("/api/reports")
def list_reports():
    """List all benchmark runs found in results/ directory."""
    results = []
    if os.path.exists("results"):
        # List directories
        for entry in sorted(os.listdir("results"), reverse=True):
            full_path = os.path.join("results", entry)
            if os.path.isdir(full_path):
                # Check for result json
                summary = {}
                json_files = glob.glob(
                    os.path.join(full_path, "results_*.json"))
                if json_files:
                    try:
                        with open(json_files[0], 'r') as f:
                            summary = json.load(f)
                    except:
                        pass

                results.append({
                    "id": entry,
                    "timestamp": entry,  # The ID is the timestamp
                    "has_summary": bool(json_files),
                    "summary": summary
                })
    return results


@app.get("/api/reports/{run_id}")
def get_report(run_id: str):
    """Get details for a specific run (Baseline + aiDAPTIV)."""
    run_dir = os.path.join("results", run_id)
    if not os.path.exists(run_dir):
        return {"error": "Run not found"}

    data = {
        "id": run_id,
        "baseline": None,
        "aidaptiv": None
    }

    # Load Baseline
    base_p = os.path.join(run_dir, "results_baseline.json")
    if os.path.exists(base_p):
        try:
            with open(base_p, 'r') as f:
                data["baseline"] = json.load(f)
        except:
            pass

    # Load aiDAPTIV
    ai_p = os.path.join(run_dir, "results_aidaptiv.json")
    if os.path.exists(ai_p):
        try:
            with open(ai_p, 'r') as f:
                data["aidaptiv"] = json.load(f)
        except:
            pass

            # Fallback for old runs where we just used glob
            if not data["baseline"] and not data["aidaptiv"]:
                json_files = glob.glob(os.path.join(run_dir, "results_*.json"))
                if json_files and "results_baseline" not in json_files[0] and "results_aidaptiv" not in json_files[0]:
                    try:
                        with open(json_files[0], 'r') as f:
                            # Treat generic as baseline
                            data["baseline"] = json.load(f)
                    except:
                        pass

    return data


@app.get("/api/reports/{run_id}/csv")
def get_report_csv(run_id: str):
    """Get CSV data for charts."""
    run_dir = os.path.join("results", run_id)
    # Find CSV
    csv_files = glob.glob(os.path.join(run_dir, "metrics_*.csv"))
    if csv_files:
        with open(csv_files[0], 'r') as f:
            return {"csv": f.read()}
    return {"csv": ""}


if __name__ == "__main__":
    print("🖥️  Starting Display Server on http://localhost:8081")
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="error")
