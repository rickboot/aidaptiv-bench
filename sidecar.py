from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import json
import os
import glob
import yaml


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
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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
            
            /* Charts */
            .chart-container { background: #1a1a1a; padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #333; height: 350px; }
            
            /* Setup Form */
            .form-group { margin-bottom: 20px; }
            .form-group label { display: block; margin-bottom: 8px; color: #aaa; font-weight: 500; }
            .form-group input, .form-group select { width: 100%; padding: 10px; background: #222; border: 1px solid #444; border-radius: 4px; color: #fff; font-size: 1em; }
            .form-group input:focus, .form-group select:focus { outline: none; border-color: #0f0; }
            .btn-primary { background: #0f0; color: #000; border: none; padding: 12px 24px; border-radius: 4px; font-size: 1em; font-weight: bold; cursor: pointer; }
            .btn-primary:hover { background: #0c0; }
            .code-block { background: #1a1a1a; padding: 15px; border-radius: 5px; border: 1px solid #333; font-family: monospace; color: #0f0; margin-top: 20px; position: relative; }
            .copy-btn { position: absolute; top: 10px; right: 10px; background: #333; color: #fff; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 0.9em; }
            .copy-btn:hover { background: #444; }
        </style>
    </head>
    <body>
        <div class="navbar">
            <h1>aiDAPTIV Bench</h1>
            <button class="nav-btn active" id="btn-dash" onclick="setView('dashboard')">Live Monitor</button>
            <button class="nav-btn" id="btn-setup" onclick="setView('setup')">Setup</button>
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

        <!-- SETUP VIEW -->
        <div id="view-setup" class="container" style="display:none;">
            <h2 style="margin-bottom: 30px;">Configure Benchmark Scenario</h2>
            
            <div class="card">
                <h3 style="margin-top: 0;">Test Parameters</h3>
                
                <div class="form-group">
                    <label for="model-select">Model</label>
                    <select id="model-select">
                        <option value="llama3.1:8b">Llama 3.1 8B</option>
                        <option value="llama3.1:70b">Llama 3.1 70B</option>
                        <option value="qwen2.5:72b">Qwen 2.5 72B</option>
                        <option value="custom">Custom (edit config.yaml)</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="context-start">Context Start (tokens)</label>
                    <select id="context-start">
                        <option value="1024">1K (1024)</option>
                        <option value="2048" selected>2K (2048)</option>
                        <option value="4096">4K (4096)</option>
                        <option value="8192">8K (8192)</option>
                        <option value="16384">16K (16384)</option>
                        <option value="32768">32K (32768)</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="context-end">Context End (tokens)</label>
                    <select id="context-end">
                        <option value="2048">2K (2048)</option>
                        <option value="4096">4K (4096)</option>
                        <option value="8192">8K (8192)</option>
                        <option value="12288" selected>12K (12288)</option>
                        <option value="16384">16K (16384)</option>
                        <option value="32768">32K (32768)</option>
                        <option value="65536">64K (65536)</option>
                        <option value="131072">128K (131072)</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="context-step">Context Step (tokens)</label>
                    <select id="context-step">
                        <option value="1024">1K (1024)</option>
                        <option value="2048" selected>2K (2048)</option>
                        <option value="4096">4K (4096)</option>
                        <option value="8192">8K (8192)</option>
                        <option value="16384">16K (16384)</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="scenario-name">Scenario Name (optional)</label>
                    <input type="text" id="scenario-name" placeholder="e.g., Llama-70B Memory Test">
                    <div class="row" style="display: flex; gap: 10px;">
                    <button class="btn-primary" onclick="generateCommand()">Generate Benchmark Cmd</button>
                    <button class="btn-primary" onclick="generateLimitCommand()" style="background: #e91e63;">Generate Limit Cmd (Linux)</button>
                    <button class="btn-primary" onclick="runBenchmark()" style="margin-left: auto; background: #f90;">Run Benchmark</button>
                </div>
                
                <div id="run-status" style="margin-top: 20px; padding: 15px; background: #1a1a1a; border-radius: 5px; border: 1px solid #333; display: none;">
                    <p id="run-status-text" style="margin: 0; color: #0f0;"></p>
                </div>
            </div>
            
            <div id="command-output" style="display:none;">
                <h3>Generated Command</h3>
                <pre id="generated-command" style="margin: 0; white-space: pre-wrap;"></pre>
                <p id="cmd-desc" style="color: #bbb; font-style: italic; margin-top: 5px;"></p>
            </div>
            
            <div style="margin-top: 20px; border-top: 1px solid #333; padding-top: 15px;">
                <p style="color: #888;">
                    <strong>Note:</strong> On Linux, use "Generate Limit Cmd" to physically constrain Ollama before running the benchmark. 
                    On macOS/Windows, the limits are visual only.
                </p>
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
                console.log('setView called with:', view);
                document.getElementById('view-dashboard').style.display = view === 'dashboard' ? 'block' : 'none';
                document.getElementById('view-setup').style.display = view === 'setup' ? 'block' : 'none';
                document.getElementById('view-reports').style.display = view === 'reports' ? 'block' : 'none';
                
                document.getElementById('btn-dash').className = view === 'dashboard' ? 'nav-btn active' : 'nav-btn';
                document.getElementById('btn-setup').className = view === 'setup' ? 'nav-btn active' : 'nav-btn';
                document.getElementById('btn-reports').className = view === 'reports' ? 'nav-btn active' : 'nav-btn';

                if (view === 'reports') {
                    console.log('Loading reports...');
                    loadReports();
                    polling = false;
                } else {
                    polling = true;
                }
            }

            async function loadReports() {
                try {
                    console.log('loadReports called');
                    const res = await fetch('/api/reports');
                    const list = await res.json();
                    console.log('Reports loaded:', list);
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
                } catch(e) {
                    console.error('Error loading reports:', e);
                }
            }

            let currentChart = null;

            async function loadReportDetail(id) {
                const res = await fetch(`/api/reports/${id}`);
                const data = await res.json();
                
                document.getElementById('reports-list').style.display = 'none';
                document.getElementById('report-detail').style.display = 'block';
                
                const content = document.getElementById('detail-content');
                content.innerHTML = `
                    <div class="chart-container"><canvas id="latencyChart"></canvas></div>
                    <div class="chart-container"><canvas id="resourceChart"></canvas></div>
                `;
                
                // Wait for DOM to update
                await new Promise(resolve => setTimeout(resolve, 10));
                
                // --- Latency Chart Logic (Existing) ---
                if (currentChart) currentChart.destroy();
                // ... (Keep Latency Logic essentially same, but wrapped or re-executed) ...
                // Note: To avoid repeating, I will focus on the ADDITIONS here, but since I must replace the block, I'll include both.
                
                const ctxLat = document.getElementById('latencyChart').getContext('2d');
                const ctxRes = document.getElementById('resourceChart').getContext('2d');
                
                // 1. LATENCY CHART
                let contexts = new Set();
                if (data.baseline) data.baseline.forEach(r => contexts.add(r.context));
                if (data.aidaptiv) data.aidaptiv.forEach(r => contexts.add(r.context));
                const labels = Array.from(contexts).sort((a,b) => a-b);
                
                const getDatapoints = (rows) => {
                    if (!rows) return [];
                    const m = {};
                    rows.forEach(r => m[r.context] = r.avg_latency_ms);
                    return labels.map(l => m[l] || null);
                };

                const latDatasets = [];
                if (data.baseline) {
                    latDatasets.push({ label: 'Baseline Latency', data: getDatapoints(data.baseline), borderColor: '#00ffff', tension: 0.3 });
                }
                if (data.aidaptiv) {
                    latDatasets.push({ label: 'aiDAPTIV Latency', data: getDatapoints(data.aidaptiv), borderColor: '#ff00ff', tension: 0.3 });
                }

                new Chart(ctxLat, {
                    type: 'line',
                    data: { labels: labels, datasets: latDatasets },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        plugins: { title: { display: true, text: 'Latency vs Context', color: '#fff' } },
                        scales: { y: { beginAtZero: true, grid: {color: '#333'} }, x: { grid: {color: '#333'} } }
                    }
                });

                // 2. RESOURCE CHART (Memory)
                // Fetch CSVs
                const fetchCsv = async (stage) => {
                    const r = await fetch(`/api/reports/${id}/csv?stage=${stage}`);
                    const j = await r.json();
                    console.log(`fetchCsv(${stage}):`, j);
                    return j.csv || "";
                };
                
                const parseCsv = (csv) => {
                    if (!csv) return { times: [], vram: [], ram: [] };
                    const lines = csv.split('\\n');
                    const times = [];
                    const vram = [];
                    const ram = [];
                    // Header: timestamp,elapsed_sec,ram_used_gb,ram_total_gb,vram_used_gb,vram_total_gb,disk_read_mb_s,disk_write_mb_s,cpu_pct
                    // skip header
                    for (let i=1; i<lines.length; i++) {
                        if (!lines[i]) continue;
                        const parts = lines[i].split(',');
                        if (parts.length < 5) continue;
                        const elapsed = parseFloat(parts[1]);
                        times.push(elapsed.toFixed(1)); // Seconds from start
                        ram.push(parseFloat(parts[2]));
                        vram.push(parseFloat(parts[4]));
                    }
                    return { times, vram, ram };
                };

                const baseCsv = await fetchCsv("baseline");
                const aiCsv = await fetchCsv("aidaptiv");
                const baseData = parseCsv(baseCsv);
                const aiData = parseCsv(aiCsv);
                
                console.log('Baseline data:', baseData);
                console.log('aiDAPTIV data:', aiData);
                
                const resDatasets = [];
                if (baseData.times.length > 0) {
                    resDatasets.push({ label: 'Baseline: Active AI Mem (GB)', data: baseData.vram, borderColor: '#00ff00', pointRadius: 0, borderWidth: 2 });
                    resDatasets.push({ label: 'Baseline: Host RAM (GB)', data: baseData.ram, borderColor: '#0088ff', pointRadius: 0, borderWidth: 1 });
                }
                if (aiData.times.length > 0) {
                     resDatasets.push({ label: 'aiDAPTIV: Active AI Mem (GB)', data: aiData.vram, borderColor: '#00ff00', borderDash: [5,5], pointRadius: 0 });
                }

                // We use Baseline time axis for simplicity, or longest
                const timeLabels = baseData.times.length > aiData.times.length ? baseData.times : aiData.times;
                
                console.log('Time labels:', timeLabels);
                console.log('Datasets:', resDatasets);

                // Calculate context transitions based on latency data
                // Heuristic: each context = (warmup + runs) * avg_latency
                // We assume 3 runs total (1 warm + 2 measured) as per default config
                let eventMarkers = [];
                let accumulatedTime = 0;
                
                // Helper to add markers from a result set
                const addMarkers = (results, labelPrefix) => {
                    if (!results || !Array.isArray(results)) return;
                    results.forEach(r => {
                        eventMarkers.push({
                            label: `${r.context/1024}K`,
                            time: accumulatedTime
                        });
                        // Estimate duration: (avg_latency_ms * 3) / 1000
                        // * 3 accounts for 1 measurement + overhead. 
                        // latency is avg of measured runs. Total measuring measurements is runs_per_context.
                        // Lets assume 3 measured invocations total (1 warm up + 2 measured)
                        const duration = (r.avg_latency_ms * 3) / 1000; 
                        accumulatedTime += duration;
                    });
                };

                // Add markers for baseline
                if (data.baseline) addMarkers(data.baseline, '');

                // Define inline plugin for vertical lines
                const verticalLinePlugin = {
                    id: 'verticalLines',
                    afterDatasetsDraw: (chart) => {
                        const { ctx, chartArea: { top, bottom }, scales: { x } } = chart;
                        ctx.save();
                        
                        eventMarkers.forEach(marker => {
                            // Find x pixel for the time
                            // We need to find the closest data point since x-axis is categorical (labels)
                            // or if linear, just project. Our x-axis is time labels strings, so we map.
                            
                            // Find closest index in timeLabels
                            const closestIdx = timeLabels.findIndex(t => parseFloat(t) >= marker.time);
                            if (closestIdx !== -1) {
                                const xPos = x.getPixelForValue(timeLabels[closestIdx]);
                                
                                // Draw line
                                ctx.beginPath();
                                ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
                                ctx.lineWidth = 1;
                                ctx.moveTo(xPos, top);
                                ctx.lineTo(xPos, bottom);
                                ctx.stroke();
                                
                                // Draw label
                                ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                                ctx.textAlign = 'left';
                                ctx.fillText(marker.label, xPos + 4, top + 10);
                            }
                        });
                        ctx.restore();
                    }
                };

                new Chart(ctxRes, {
                    type: 'line',
                    data: { labels: timeLabels, datasets: resDatasets },
                    plugins: [verticalLinePlugin],
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        plugins: { 
                            title: { 
                                display: true, 
                                text: 'Memory Usage & Test Events',
                                color: '#fff',
                                font: { size: 14 }
                            },
                            tooltip: {
                                callbacks: {
                                    afterTitle: function(context) {
                                        // Find active context based on time
                                        const time = parseFloat(context[0].label);
                                        // Find the interval this time belongs to
                                        for (let i = 0; i < eventMarkers.length; i++) {
                                            const start = eventMarkers[i].time;
                                            const end = eventMarkers[i+1] ? eventMarkers[i+1].time : Infinity;
                                            if (time >= start && time < end) {
                                                return `Context: ${eventMarkers[i].label}`;
                                            }
                                        }
                                        return '';
                                    }
                                }
                            }
                        },
                        scales: { 
                            y: { title: {display:true, text:'GB', color: '#aaa'}, beginAtZero: true, grid: {color: '#333'}, ticks: {color: '#aaa'} }, 
                            x: { title: {display:true, text:'Seconds', color: '#aaa'}, grid: {color: '#333'}, ticks: {maxTicksLimit: 20, color: '#aaa'} } 
                        },
                        animation: false
                    }
                });


                // --- Table Logic ---
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
            async function generateCommand() {
                const model = document.getElementById('model-select').value;
                const start = parseInt(document.getElementById('context-start').value);
                const end = parseInt(document.getElementById('context-end').value);
                const step = parseInt(document.getElementById('context-step').value);
                const name = document.getElementById('scenario-name').value;
                
                // Validate inputs
                if (end < start) {
                    alert(`Invalid range: Context End (${end}) must be >= Context Start (${start})`);
                    return;
                }
                
                if (step <= 0) {
                    alert(`Invalid step: Context Step must be > 0`);
                    return;
                }
                
                // Update config.yaml via API
                try {
                    const response = await fetch('/api/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            model: model,
                            context_start: start,
                            context_end: end,
                            context_step: step
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (!result.success) {
                        alert('Failed to update config: ' + result.error);
                        return;
                    }
                    
                    console.log('Config updated:', result.message);
                } catch (err) {
                    console.error('Config update failed:', err);
                    alert('Failed to update config. Check console for details.');
                    return;
                }
                
                // Generate context array for display
                const contexts = [];
                for (let c = parseInt(start); c <= parseInt(end); c += parseInt(step)) {
                    contexts.push(c);
                }
                
                const cmd = `sudo python3 benchmark.py`;
                
                // Show scenario name separately if provided
                let displayCmd = cmd;
                if (name) {
                    displayCmd = `# Scenario: ${name}\n${cmd}`;
                }
                
                displayCmd += `\n\n# Config updated: Model=${model}, Contexts=${contexts.join(', ')}`;
                
                document.getElementById('generated-command').innerText = displayCmd;
                document.getElementById('command-output').style.display = 'block';
                
                // Store the actual command for copying
                document.getElementById('command-output').dataset.actualCommand = cmd;
                
                // Scroll to command
                document.getElementById('command-output').scrollIntoView({ behavior: 'smooth' });
            }
            
            function copyCommand() {
                const cmd = document.getElementById('command-output').dataset.actualCommand || 'sudo python3 benchmark.py';
                navigator.clipboard.writeText(cmd).then(() => {
                    const btn = document.querySelector('.copy-btn');
                    btn.innerText = 'Copied!';
                    setTimeout(() => btn.innerText = 'Copy', 2000);
                }).catch(err => {
                    console.error('Copy failed:', err);
                    alert('Copy failed. Please manually select and copy the command.');
                });
            }
            
            async function runBenchmark() {
                // First, update the config
                await generateCommand();
                
                // Call backend to open Terminal
                try {
                    const response = await fetch('/api/run-benchmark', {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        alert(`✅ ${result.message}\n\nThe Live Monitor will update once the benchmark starts.`);
                        // Switch to dashboard view
                        setView('dashboard');
                    } else {
                        alert(`❌ Failed to open Terminal: ${result.error}`);
                    }
                } catch (err) {
                    console.error('Run benchmark failed:', err);
                    alert('Failed to open Terminal. Check console for details.');
                }
            }
            
            function updateScenarioName() {
                const model = document.getElementById('model-select').value;
                const start = parseInt(document.getElementById('context-start').value);
                const end = parseInt(document.getElementById('context-end').value);
                const step = parseInt(document.getElementById('context-step').value);
                
                // Format model name (e.g., "llama3.1:8b" -> "Llama-8B")
                let modelShort = model.split(':')[0].replace('llama3.1', 'Llama').replace('qwen2.5', 'Qwen');
                if (model.includes(':')) {
                    const size = model.split(':')[1].toUpperCase();
                    modelShort += `-${size}`;
                }
                
                // Format context sizes (e.g., 2048 -> "2K")
                const formatK = (val) => `${Math.round(val / 1024)}K`;
                
                const scenarioName = `${modelShort}_${formatK(start)}-${formatK(end)}_${formatK(step)}-step`;
                document.getElementById('scenario-name').value = scenarioName;
            }
            
            // Auto-update scenario name when form changes
            document.addEventListener('DOMContentLoaded', () => {
                updateScenarioName();
                document.getElementById('model-select').addEventListener('change', updateScenarioName);
                document.getElementById('context-start').addEventListener('change', updateScenarioName);
                document.getElementById('context-end').addEventListener('change', updateScenarioName);
                document.getElementById('context-step').addEventListener('change', updateScenarioName);
            });
            
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
def get_report_csv(run_id: str, stage: str = "all"):
    """Get CSV data for charts, optionally filter by stage."""
    run_dir = os.path.join("results", run_id)
    target_file = None

    if stage == "baseline":
        target_file = os.path.join(run_dir, "metrics_baseline.csv")
    elif stage == "aidaptiv":
        target_file = os.path.join(run_dir, "metrics_aidaptiv.csv")
    else:
        # Fallback to first found
        csv_files = glob.glob(os.path.join(run_dir, "metrics_*.csv"))
        if csv_files:
            target_file = csv_files[0]

    if target_file and os.path.exists(target_file):
        with open(target_file, 'r') as f:
            return {"csv": f.read(), "stage": stage}

    return {"csv": "", "error": "File not found"}


@app.post("/api/config")
def update_config(data: dict):
    """Update config.yaml with new test parameters."""
    try:
        # Create backup directory if it doesn't exist
        os.makedirs('config_history', exist_ok=True)

        # Backup current config with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f'config_history/config_{timestamp}.yaml'

        # Read existing config
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)

        # Save backup
        with open(backup_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        # Update runtime model if provided
        if 'model' in data and data['model'] != 'custom':
            config['runtime']['model_name'] = data['model']

        # Update context lengths if provided
        if 'context_start' in data and 'context_end' in data and 'context_step' in data:
            start = int(data['context_start'])
            end = int(data['context_end'])
            step = int(data['context_step'])
            contexts = list(range(start, end + 1, step))
            config['test']['context_lengths'] = contexts

        # Write back to file
        with open('config.yaml', 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return {"success": True, "message": f"Config updated (backup saved to {backup_path})"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/run-benchmark")
def run_benchmark():
    """Open Terminal and run the benchmark command (macOS only)."""
    try:
        import subprocess

        # Get the current working directory
        cwd = os.getcwd()

        # Build the command to run in Terminal
        # Escape quotes for AppleScript
        cmd = f'cd \\"{cwd}\\" && sudo python3 benchmark.py'

        # Use osascript to open Terminal and run the command
        applescript = f'''tell application "Terminal"
    activate
    set newTab to do script "{cmd}"
    delay 0.5
    set frontmost of window 1 to true
end tell'''

        subprocess.run(['osascript', '-e', applescript],
                       check=True, capture_output=True, text=True)

        return {"success": True, "message": "Terminal opened. Please enter your password to start the benchmark."}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": f"AppleScript error: {e.stderr}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    print("🖥️  Starting Display Server on http://localhost:8081")
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="error")
