from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import json
import os
import glob
import yaml
import platform
import time

is_linux = platform.system() == 'Linux'


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
    test_progress: dict = {}  # New field for test progress tracking


@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    # VERSION: 2026-01-19-fix-reports-visibility
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>aiDAPTIV Bench</title>
        <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
        <meta http-equiv="Pragma" content="no-cache">
        <meta http-equiv="Expires" content="0">
        <meta http-equiv="Expires" content="0">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            const IS_LINUX = {str(is_linux).lower()};
        </script>
        <style>
            body { font-family: 'Segoe UI', monospace; background: #111; color: #eee; padding: 0; margin: 0; }
            .navbar { background: #222; padding: 10px 20px; border-bottom: 1px solid #333; display: flex; align-items: center; }
            .navbar h1 { margin: 0; font-size: 1.2em; color: #fff; margin-right: 30px; letter-spacing: 1px; }
            .nav-btn { background: transparent; border: none; color: #888; cursor: pointer; font-size: 1em; padding: 10px; margin-right: 10px; text-transform: uppercase; }
            .nav-btn.active { color: #0f0; border-bottom: 2px solid #0f0; }
            .nav-btn:hover { color: #fff; }

            .container { max-width: 1200px; margin: 20px auto; padding: 0 20px; }
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
            
            /* Report Detail Enhancements */
            .summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px; }
            .summary-card { background: linear-gradient(135deg, #222, #1a1a1a); padding: 20px; border-radius: 8px; border: 1px solid #444; position: relative; overflow: hidden; }
            .summary-card.baseline { border-left: 4px solid #00ffff; }
            .summary-card.aidaptiv { border-left: 4px solid #ff00ff; }
            .summary-card h4 { margin: 0 0 10px 0; color: #888; font-size: 0.8em; text-transform: uppercase; }
            .summary-card .val { font-size: 2em; font-weight: bold; color: #fff; }
            .summary-card .delta { position: absolute; top: 10px; right: 10px; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.9em; }
            .delta.better { background: rgba(0,255,0,0.1); color: #0f0; }
            .delta.worse { background: rgba(255,0,0,0.1); color: #f00; }

            details { background: #1a1a1a; border: 1px solid #333; border-radius: 5px; margin-bottom: 20px; }
            summary { padding: 10px 15px; cursor: pointer; color: #aaa; font-weight: bold; user-select: none; }
            summary:hover { color: #fff; background: #222; }
            .details-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; padding: 15px; border-top: 1px solid #333; }
            .detail-item label { display: block; color: #666; font-size: 0.8em; margin-bottom: 4px; }
            .detail-item span { color: #eee; font-family: monospace; }
            
            /* Setup Form */
            .form-group { margin-bottom: 20px; }
            .form-group label { display: block; margin-bottom: 8px; color: #aaa; font-weight: 500; }
            .form-group input, .form-group select { width: 100%; padding: 10px; background: #222; border: 1px solid #444; border-radius: 4px; color: #fff; font-size: 1em; }
            .form-group input:focus, .form-group select:focus { outline: none; border-color: #0f0; }
            .form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px; margin-bottom: 20px; }
            
            .btn-primary { background: #0f0; color: #000; border: none; padding: 12px 24px; border-radius: 4px; font-size: 1em; font-weight: bold; cursor: pointer; }
            .btn-primary:hover { background: #0c0; }
            .code-block { background: #1a1a1a; padding: 15px; border-radius: 5px; border: 1px solid #333; font-family: monospace; color: #0f0; margin-top: 20px; position: relative; }
            .copy-btn { position: absolute; top: 10px; right: 10px; background: #333; color: #fff; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 0.9em; }
            .copy-btn:hover { background: #444; }
            .chart-container { background: #1a1a1a; padding: 20px; border-radius: 8px; border: 1px solid #333; margin-bottom: 20px; height: 400px; position: relative; }
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
        <div id="view-dashboard" class="container" style="display:block;">
            <div id="status" class="status-bar">Waiting for Telemetry...</div>
            
            <!-- Current Test Status -->
            <div id="test-status" style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 15px 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                display: none;
            ">
                <div style="font-size: 14px; opacity: 0.9;">Current Test</div>
                <div id="test-status-text" style="font-size: 20px; font-weight: 600; margin-top: 5px;">
                    Testing Context: 3072 tokens (2 of 3)
                </div>
            </div>
            
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
            
            <!-- LATENCY METRICS -->
            <div style="margin-top: 30px;">
                <h2 style="font-size: 16px; color: #888; margin: 0 0 15px 0; font-weight: 500;">LATENCY METRICS</h2>
                <div class="grid" style="grid-template-columns: repeat(3, 1fr);">
                    <div class="card">
                        <h2>TTFT</h2>
                        <div id="ttft_val" class="big-val">-- ms</div>
                        <div id="ttft_sub" class="sub-val">Time to First Token</div>
                    </div>
                    <div class="card">
                        <h2>Runtime</h2>
                        <div id="runtime_val" class="big-val">0.0s</div>
                        <div id="runtime_sub" class="sub-val">Current Request</div>
                    </div>
                    <div class="card">
                        <h2>Last Request</h2>
                        <div id="last_latency_val" class="big-val">-- s</div>
                        <div id="last_latency_sub" class="sub-val">Total Duration</div>
                    </div>
                </div>
            </div>
            
            <!-- Test Results Table -->
            <div id="test-results-section" style="margin-top: 30px; display: none;">
                <h2 style="font-size: 16px; color: #888; margin: 0 0 15px 0; font-weight: 500;">
                    TEST RESULTS
                </h2>
                <table style="
                    width: 100%;
                    border-collapse: collapse;
                    background: white;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                ">
                    <thead style="background: #f8f9fa;">
                        <tr>
                            <th style="padding: 12px; text-align: left; font-weight: 600; color: #333;">Context</th>
                            <th style="padding: 12px; text-align: right; font-weight: 600; color: #333;">TTFT</th>
                            <th style="padding: 12px; text-align: right; font-weight: 600; color: #333;">Runtime</th>
                            <th style="padding: 12px; text-align: right; font-weight: 600; color: #333;">TPS</th>
                            <th style="padding: 12px; text-align: center; font-weight: 600; color: #333;">Status</th>
                        </tr>
                    </thead>
                    <tbody id="test-results-tbody">
                        <!-- Rows populated by JavaScript -->
                    </tbody>
                </table>
            </div>
        </div>

        <!-- SETUP VIEW -->
        <div id="view-setup" class="container" style="display:none;">
            <h2 style="margin-bottom: 30px;">Configure Benchmark Scenario</h2>
            
            <div class="card">
                <div class="form-group">
                    <label for="scenario-name">Scenario Name</label>
                    <input type="text" id="scenario-name" placeholder="e.g., Llama-70B Memory Test">
                </div>

                <div class="form-row">
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
                        <label for="context-start">Context Start</label>
                        <select id="context-start">
                            <option value="1024" selected>1K (1024)</option>
                            <option value="2048">2K (2048)</option>
                            <option value="4096">4K (4096)</option>
                            <option value="8192">8K (8192)</option>
                            <option value="16384">16K (16384)</option>
                            <option value="32768">32K (32768)</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="context-end">Context End</label>
                        <select id="context-end">
                            <option value="1024">1K (1024)</option>
                            <option value="2048">2K (2048)</option>
                            <option value="4096">4K (4096)</option>
                            <option value="8192">8K (8192)</option>
                            <option value="16384">16K (16384)</option>
                            <option value="32768">32K (32768)</option>
                            <option value="65536">64K (65536)</option>
                            <option value="131072" selected>128K (131072)</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="step-mode">Step Mode</label>
                        <select id="step-mode">
                            <option value="linear">Linear (+)</option>
                            <option value="geometric" selected>Geometric (x2)</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label for="context-step">Step Size</label>
                        <select id="context-step">
                            <option value="1024">1K (1024)</option>
                            <option value="2048" selected>2K (2048)</option>
                            <option value="4096">4K (4096)</option>
                            <option value="8192">8K (8192)</option>
                            <option value="16384">16K (16384)</option>
                        </select>
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="concurrency">Concurrency (Users)</label>
                        <input type="number" id="concurrency" value="1" min="1">
                    </div>
                    <div class="form-group">
                        <label for="runs-per-context">Runs / Context</label>
                        <input type="number" id="runs-per-context" value="1" min="1">
                    </div>
                    <div class="form-group">
                        <label for="ram-limit">RAM Limit (GB)</label>
                        <input type="number" id="ram-limit" value="16">
                    </div>
                    <div class="form-group">
                        <label for="swap-limit">VRAM/Swap Limit (GB)</label>
                        <input type="number" id="swap-limit" value="32">
                    </div>
                </div>
                
                <div style="display: flex; gap: 10px; margin-top: 10px;">
                    <button class="btn-primary" onclick="runBenchmark()" style="background: #f90; width: 100%;">Run Benchmark</button>
                </div>
                
                <div id="run-status" style="margin-top: 20px; padding: 15px; background: #1a1a1a; border-radius: 5px; border: 1px solid #333; display: none;">
                    <p id="run-status-text" style="margin: 0; color: #0f0;"></p>
                </div>
            </div>
            
            <div id="command-output" style="display:none;">
                <h3>Generated Command</h3>
                <div class="code-block" style="margin-bottom: 20px;">
                    <button class="copy-btn" onclick="copyCommand()">Copy</button>
                    <div id="generated-command" style="white-space: pre-wrap;"></div>
                </div>
                <p id="cmd-desc" style="color: #bbb; font-style: italic; margin-top: 5px;"></p>
            </div>
            
            <div style="margin-top: 20px; border-top: 1px solid #333; padding-top: 15px;">
                <p style="color: #888;">
                    <strong>Note:</strong> On Linux, memory limits are automatically applied when launching the benchmark. 
                    On macOS/Windows, these limits are ignored.
                </p>
            </div>
        </div>
        </div>

        <!-- REPORTS VIEW -->
        <div id="view-reports" class="container" style="display:none;">
            <div id="reports-list">
                <h2>Benchmark History</h2>
                <table id="reports-table" style="display: table !important; width: 100% !important; visibility: visible !important;">
                    <thead>
                        <tr>
                            <th style="width: 250px;">Scenario Name</th>
                            <th>Model</th>
                            <th>Timestamp</th>
                            <th>Baseline</th>
                            <th>aiDAPTIV</th>
                            <th>Imp.</th>
                        </tr>
                    </thead>
                    <tbody id="reports-table-body" style="display: table-row-group !important;">
                        <!-- JS Populated -->
                    </tbody>
                </table>
            </div>

            <div id="report-detail" style="display:none">
                <button class="back-btn" onclick="closeReport()">← Back to List</button>
                <div id="report-title-area" style="display: flex; align-items: flex-start; justify-content: space-between;">
                    <div>
                        <h2 id="detail-title" style="margin-bottom: 5px;">Report Details</h2>
                        <p id="detail-subtitle" style="color: #666; margin-top: 0; margin-bottom: 20px;"></p>
                    </div>
                    <div style="display: flex; gap: 10px;">
                        <button class="btn-primary" id="btn-download-json" style="font-size: 0.8em; padding: 8px 15px;">Download Report (JSON)</button>
                        <button class="btn-primary" id="btn-download-csv-base" style="font-size: 0.8em; padding: 8px 15px; background: #00ffff; color: #000;">Download Baseline (CSV)</button>
                        <button class="btn-primary" id="btn-download-csv-ai" style="font-size: 0.8em; padding: 8px 15px; background: #ff00ff; color: #000;">Download aiDAPTIV (CSV)</button>
                    </div>
                </div>

                <div id="executive-summary" class="summary-grid">
                    <!-- JS Populated -->
                </div>

                <details id="technical-config" open>
                    <summary style="font-size: 1.1em; color: #fff; background: #222;">Test Scenario</summary>
                    <div class="details-grid" id="config-details">
                        <!-- JS Populated -->
                    </div>
                </details>

                <div id="detail-charts">
                    <div class="chart-container"><canvas id="latencyChart"></canvas></div>
                    <div class="chart-container"><canvas id="resourceChart"></canvas></div>
                </div>

                <div id="detail-tables"></div>
                
                <h3 style="margin-top: 40px; color: #666; font-size: 0.9em;">Raw Data</h3>
                <pre id="detail-json" style="max-height: 200px; font-size: 0.8em;"></pre>
            </div>
        </div>

        <script>
            let polling = true;

            function setView(view) {
                console.log('setView called with:', view);
                const viewDashboard = document.getElementById('view-dashboard');
                const viewSetup = document.getElementById('view-setup');
                const viewReports = document.getElementById('view-reports');
                
                console.log('Elements found:', {
                    dashboard: !!viewDashboard,
                    setup: !!viewSetup,
                    reports: !!viewReports
                });
                
                // Hide all views first
                if (viewDashboard) viewDashboard.style.display = 'none';
                if (viewSetup) viewSetup.style.display = 'none';
                if (viewReports) viewReports.style.display = 'none';
                
                // Then show the selected view
                if (view === 'dashboard' && viewDashboard) {
                    viewDashboard.style.display = 'block';
                } else if (view === 'setup' && viewSetup) {
                    viewSetup.style.display = 'block';
                } else if (view === 'reports' && viewReports) {
                    viewReports.style.display = 'block';
                    viewReports.style.visibility = 'visible';
                    console.log('Set view-reports to block, computed:', window.getComputedStyle(viewReports).display);
                } else {
                    console.error('view-reports element NOT FOUND!');
                }
                
                const btnDash = document.getElementById('btn-dash');
                const btnSetup = document.getElementById('btn-setup');
                const btnReports = document.getElementById('btn-reports');

                if (btnDash) btnDash.className = view === 'dashboard' ? 'nav-btn active' : 'nav-btn';
                if (btnSetup) btnSetup.className = view === 'setup' ? 'nav-btn active' : 'nav-btn';
                if (btnReports) btnReports.className = view === 'reports' ? 'nav-btn active' : 'nav-btn';

                if (view === 'reports') {
                    console.log('Loading reports...');
                    // CRITICAL: Make absolutely sure it's visible
                    if (viewReports) {
                        viewReports.style.display = 'block';
                        viewReports.style.visibility = 'visible';
                        viewReports.style.opacity = '1';
                        viewReports.style.height = 'auto';
                        viewReports.style.minHeight = '200px';
                        console.log('✓ view-reports made visible');
                        console.log('  Computed display:', window.getComputedStyle(viewReports).display);
                    } else {
                        console.error('❌ view-reports element not found!');
                    }
                    // Small delay to ensure DOM is updated
                    setTimeout(() => {
                        loadReports();
                    }, 100);
                    polling = false;
                } else {
                    polling = true;
                }
            }

            async function loadReports() {
                try {
                    console.log('loadReports called');
                    // Ensure the reports view container and list are visible
                    const viewReports = document.getElementById('view-reports');
                    const reportsList = document.getElementById('reports-list');
                    
                    console.log('Before setting visibility:');
                    console.log('  view-reports exists:', !!viewReports);
                    console.log('  view-reports current display:', viewReports ? window.getComputedStyle(viewReports).display : 'N/A');
                    console.log('  reports-list exists:', !!reportsList);
                    console.log('  reports-list current display:', reportsList ? window.getComputedStyle(reportsList).display : 'N/A');
                    
                    if (viewReports) {
                        // Completely remove style and force visibility
                        viewReports.removeAttribute('style');
                        viewReports.style.cssText = 'display: block !important; visibility: visible !important; opacity: 1 !important; height: auto !important; min-height: 200px !important;';
                        console.log('  FORCED view-reports to block with !important');
                        console.log('  view-reports offsetHeight:', viewReports.offsetHeight);
                        console.log('  view-reports clientHeight:', viewReports.clientHeight);
                    }
                    if (reportsList) {
                        reportsList.style.display = 'block';
                        reportsList.style.visibility = 'visible';
                        console.log('  Set reports-list to block');
                    }
                    const reportDetail = document.getElementById('report-detail');
                    if (reportDetail) {
                        reportDetail.style.display = 'none';
                    }
                    
                    console.log('After setting visibility:');
                    console.log('  view-reports computed display:', viewReports ? window.getComputedStyle(viewReports).display : 'N/A');
                    console.log('  reports-list computed display:', reportsList ? window.getComputedStyle(reportsList).display : 'N/A');
                    
                    const res = await fetch('/api/reports'); // Assuming this now returns metadata
                    if (!res.ok) {
                        console.error('Failed to fetch reports:', res.status, res.statusText);
                        const tbody = document.getElementById('reports-table-body');
                        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#f00;">Error loading reports. Check console for details.</td></tr>';
                        return;
                    }
                    const list = await res.json();
                    console.log('Reports loaded:', list);
                    console.log('=== DEBUG: Starting processing ===');
                    console.log('List type:', typeof list, 'Is array:', Array.isArray(list), 'Length:', list ? list.length : 'null');
                    
                    const tbody = document.getElementById('reports-table-body');
                    console.log('Table body element:', tbody ? 'found' : 'NOT FOUND');
                    
                    if (!tbody) {
                        console.error('❌ Table body element not found!');
                        alert('Error: Table body element not found. Check console.');
                        return;
                    }
                    
                    console.log('Clearing table body...');
                    tbody.innerHTML = '';
                    console.log('Table cleared, starting to process reports...');
                
                    if (!Array.isArray(list)) {
                        console.error('Expected array but got:', typeof list, list);
                        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#f00;">Invalid data format. Check console for details.</td></tr>';
                        return;
                    }
                
                    if (list.length === 0) {
                        console.log('List is empty');
                        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#888;">No benchmark runs found.</td></tr>';
                        return;
                    }
                    
                    console.log(`Processing ${list.length} reports...`);
                    let processedCount = 0;
                
                    list.forEach((run, index) => {
                        try {
                            console.log(`Processing run ${index + 1}/${list.length}: ${run.id}`);
                            const tr = document.createElement('tr');
                            
                            const getAvgLatency = (dataArray) => {
                                if (!dataArray || dataArray.length === 0) return null;
                                return dataArray.reduce((sum, item) => sum + item.avg_latency_ms, 0) / dataArray.length;
                            };

                            const baseLat = getAvgLatency(run.baseline);
                            const aiLat = getAvgLatency(run.aidaptiv);

                            let delta = null;
                            if (baseLat !== null && aiLat !== null && baseLat > 0) {
                                delta = ((baseLat - aiLat) / baseLat) * 100; // Improvement percentage
                            }

                            const meta = run.metadata || {};
                            const scenarioName = meta.test_config?.scenario_name || run.id;
                            const modelName = meta.test_config?.model || 'N/A';

                            // Format timestamp from run.id (YYYYMMDD_HHMMSS or YYYYMMDDHHMMSS)
                            let timestampStr = run.id;
                            try {
                                if (run.id.length === 16 && run.id.includes('_')) {
                                    const [datePart, timePart] = run.id.split('_');
                                    timestampStr = `${datePart.substring(0,4)}-${datePart.substring(4,6)}-${datePart.substring(6,8)} ${timePart.substring(0,2)}:${timePart.substring(2,4)}:${timePart.substring(4,6)}`;
                                } else if (run.id.length === 15) {
                                    timestampStr = `${run.id.substring(0,4)}-${run.id.substring(4,6)}-${run.id.substring(6,8)} ${run.id.substring(8,10)}:${run.id.substring(10,12)}:${run.id.substring(12,14)}`;
                                }
                            } catch (e) {
                                console.error('Timestamp parsing error:', e);
                            }
                            
                            tr.innerHTML = `
                                <td style="font-weight: 500;">${scenarioName}</td>
                                <td style="color: #ccc;">${modelName}</td>
                                <td style="font-family: monospace; color: #888;">${timestampStr}</td>
                                <td style="color: #00ffff;">${baseLat !== null ? baseLat.toFixed(1) + 'ms' : '-'}</td>
                                <td style="color: #ff00ff;">${aiLat !== null ? aiLat.toFixed(1) + 'ms' : '-'}</td>
                                <td style="${delta !== null && delta >= 0 ? 'color: #00ff00;' : 'color: #ff4444;'} font-weight: bold;">
                                    ${delta !== null ? (delta > 0 ? '+' : '') + delta.toFixed(1) + '%' : '-'}
                                </td>
                            `;
                            tr.onclick = () => loadReportDetail(run.id);
                            tbody.appendChild(tr);
                            processedCount++;
                            console.log(`  ✓ Added row ${processedCount} for ${run.id}`);
                        } catch (e) {
                            console.error('Error processing run:', run.id, e);
                            console.error('  Error details:', e.stack);
                            // Still add a row with error info
                            const tr = document.createElement('tr');
                            tr.innerHTML = `<td colspan="4" style="color:#f00;">Error loading run ${run.id}: ${e.message}</td>`;
                            tbody.appendChild(tr);
                        }
                    });
                    
                    console.log(`Successfully processed ${processedCount} of ${list.length} reports`);
                    console.log(`Table body now has ${tbody.children.length} rows`);
                    
                    // Ensure everything is visible
                    const vr = document.getElementById('view-reports');
                    const rl = document.getElementById('reports-list');
                    const table = document.getElementById('reports-table');
                    
                    if (vr) {
                        vr.style.display = 'block';
                        vr.style.visibility = 'visible';
                        console.log('✓ view-reports visible');
                    }
                    if (rl) {
                        rl.style.display = 'block';
                    }
                    if (table) {
                        table.style.display = 'table';
                        table.style.visibility = 'visible';
                    }
                    
                    document.getElementById('report-detail').style.display = 'none';
                } catch(e) {
                    console.error('Error loading reports:', e);
                    const tbody = document.getElementById('reports-table-body');
                    if (tbody) {
                        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#f00;">Error loading reports: ' + e.message + '</td></tr>';
                    }
                }
            }

            let currentChart = null;

            async function loadReportDetail(id) {
                const res = await fetch(`/api/reports/${id}`);
                const data = await res.json();
                
                document.getElementById('reports-list').style.display = 'none';
                const meta = data.metadata || {};
                const tcfg = meta.test_config || {};
                const scenarioName = tcfg.scenario_name || id;

                document.getElementById('report-detail').style.display = 'block';
                document.getElementById('detail-title').innerText = scenarioName;
                document.getElementById('detail-subtitle').innerText = `Run ID: ${id}`;
                
                // Attach download handlers
                document.getElementById('btn-download-json').onclick = () => downloadReport(id);
                document.getElementById('btn-download-csv-base').onclick = () => downloadCsv(id, 'baseline');
                document.getElementById('btn-download-csv-ai').onclick = () => downloadCsv(id, 'aidaptiv');
                
                // --- 1. Executive Summary & Config ---
                const execSummary = document.getElementById('executive-summary');
                const configDetails = document.getElementById('config-details');
                
                // Calculate Avg Latency
                const getAvg = (rows) => {
                    if (!rows || rows.length === 0) return 0;
                    return rows.reduce((acc, r) => acc + r.avg_latency_ms, 0) / rows.length;
                };
                
                const baseAvg = getAvg(data.baseline);
                const aiAvg = getAvg(data.aidaptiv);
                let deltaHtml = '';
                if (baseAvg > 0 && aiAvg > 0) {
                    const diff = ((aiAvg - baseAvg) / baseAvg) * 100;
                    const sign = diff > 0 ? '+' : '';
                    const cls = diff <= 0 ? 'better' : 'worse';
                    deltaHtml = `<div class="delta ${cls}">${sign}${diff.toFixed(1)}%</div>`;
                }
                
                execSummary.innerHTML = `
                    <div class="summary-card baseline">
                        <h4>Baseline Avg Latency</h4>
                        <div class="val">${baseAvg > 0 ? baseAvg.toFixed(0) + 'ms' : 'N/A'}</div>
                    </div>
                    <div class="summary-card aidaptiv">
                        <h4>aiDAPTIV Avg Latency</h4>
                        <div class="val">${aiAvg > 0 ? aiAvg.toFixed(0) + 'ms' : 'N/A'}</div>
                        ${deltaHtml}
                    </div>
                    <div class="summary-card">
                        <h4>Peak Context Tested</h4>
                        <div class="val">${Math.max(...(data.aidaptiv || [0]).map(r => r.context || 0))}</div>
                    </div>
                `;
                
                // Technical Config
                // (meta and tcfg are already defined above)
                const plat = meta.platform || {};
                
                configDetails.innerHTML = `
                    <div class="detail-item"><label>Scenario Name</label><span>${tcfg.scenario_name || id}</span></div>
                    <div class="detail-item"><label>Model</label><span>${tcfg.model || 'Unknown'}</span></div>
                    <div class="detail-item"><label>Scenario Type</label><span>${tcfg.scenario || 'synthetic'}</span></div>
                    <div class="detail-item"><label>Concurrency</label><span>${tcfg.concurrency || 1} users</span></div>
                    <div class="detail-item"><label>Runs/Context</label><span>${tcfg.runs_per_context || 1} runs</span></div>
                    <div class="detail-item"><label>Step Mode</label><span>${tcfg.step_mode || 'linear'}</span></div>
                    <div class="detail-item"><label>RAM Limit</label><span>${plat.ram_limit_gb || 'N/A'} GB</span></div>
                    <div class="detail-item"><label>VRAM Limit</label><span>${plat.vram_limit_gb || 'N/A'} GB</span></div>
                    <div class="detail-item"><label>OS</label><span>${plat.os || 'Unknown'}</span></div>
                `;

                // --- 2. Charts ---
                // Wait for DOM to update
                await new Promise(resolve => setTimeout(resolve, 10));
                
                if (currentChart) currentChart.destroy();
                // Resource chart doesn't have a global handle yet, but Chart.js might conflict if we don't manage it.
                // For now we assume new Chart(ctxRes) creates a fresh one. Usually better to track it.
                
                const ctxLat = document.getElementById('latencyChart').getContext('2d');
                const ctxRes = document.getElementById('resourceChart').getContext('2d');
                
                // ... Latency Data Parsing ...
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
                    data: { labels: labels.map(l => (l/1024).toFixed(0) + 'K'), datasets: latDatasets },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        plugins: { 
                            title: { display: true, text: 'Latency (ms) vs Context Size', color: '#fff', font: { size: 16 } },
                            legend: { labels: { color: '#ccc', font: { size: 12 } } }
                        },
                        scales: { 
                            y: { 
                                beginAtZero: true, 
                                grid: {color: '#333'}, 
                                ticks: {color: '#888', font: { size: 12 } },
                                title: { display: true, text: 'Latency (ms)', color: '#aaa', font: { size: 14 } }
                            }, 
                            x: { 
                                grid: {color: '#333'}, 
                                ticks: {color: '#888', font: { size: 12 } },
                                title: { display: true, text: 'Context Size (K)', color: '#aaa', font: { size: 14 } }
                            } 
                        }
                    }
                });

                // ... Resource Chart Logic (Keep existing but ensure it works with new layout) ...
                const fetchCsv = async (stage) => {
                    const r = await fetch(`/api/reports/${id}/csv?stage=${stage}`);
                    const j = await r.json();
                    return j.csv || "";
                };
                
                const parseCsv = (csv) => {
                    if (!csv) return { times: [], vram: [], ram: [] };
                    const lines = csv.split('\\n');
                    const times = [];
                    const vram = [];
                    const ram = [];
                    for (let i=1; i<lines.length; i++) {
                        if (!lines[i]) continue;
                        const parts = lines[i].split(',');
                        if (parts.length < 5) continue;
                        const elapsed = parseFloat(parts[1]);
                        times.push(elapsed.toFixed(1));
                        ram.push(parseFloat(parts[2]));
                        vram.push(parseFloat(parts[4]));
                    }
                    return { times, vram, ram };
                };

                const baseCsv = await fetchCsv("baseline");
                const aiCsv = await fetchCsv("aidaptiv");
                const baseData = parseCsv(baseCsv);
                const aiData = parseCsv(aiCsv);
                
                const resDatasets = [];
                if (baseData.times.length > 0) {
                    resDatasets.push({ label: 'Baseline: Active AI Mem (GB)', data: baseData.vram, borderColor: '#00ffff', pointRadius: 0 });
                    resDatasets.push({ label: 'Baseline: Host RAM (GB)', data: baseData.ram, borderColor: '#00ff00', pointRadius: 0, borderWidth: 1 });
                }
                if (aiData.times.length > 0) {
                     resDatasets.push({ label: 'aiDAPTIV: Active AI Mem (GB)', data: aiData.vram, borderColor: '#ff00ff', pointRadius: 0 });
                }

                const timeLabels = baseData.times.length > aiData.times.length ? baseData.times : aiData.times;
                
                // Heuristic for event markers
                let eventMarkers = [];
                let accumulatedTime = 0;
                const addMarkers = (results) => {
                    if (!results) return;
                    results.forEach(r => {
                        eventMarkers.push({ label: `${(r.context/1024).toFixed(0)}K`, time: accumulatedTime });
                        accumulatedTime += (r.avg_latency_ms * 3) / 1000; 
                    });
                };
                addMarkers(data.baseline);

                const verticalLinePlugin = {
                    id: 'verticalLines',
                    afterDatasetsDraw: (chart) => {
                        const { ctx, chartArea: { top, bottom }, scales: { x } } = chart;
                        ctx.save();
                        eventMarkers.forEach(marker => {
                            const closestIdx = timeLabels.findIndex(t => parseFloat(t) >= marker.time);
                            if (closestIdx !== -1) {
                                const xPos = x.getPixelForValue(timeLabels[closestIdx]);
                                ctx.beginPath();
                                ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
                                ctx.moveTo(xPos, top);
                                ctx.lineTo(xPos, bottom);
                                ctx.stroke();
                                ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
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
                            title: { display: true, text: 'Memory Usage (GB) during Sweep', color: '#fff', font: { size: 16 } },
                            legend: { labels: { color: '#ccc', font: { size: 12 } } }
                        },
                        scales: { 
                            y: { 
                                beginAtZero: true, 
                                grid: {color: '#333'},
                                ticks: {color: '#888', font: { size: 12 } },
                                title: { display: true, text: 'Memory (GB)', color: '#aaa', font: { size: 14 } }
                            }, 
                            x: { 
                                grid: {color: '#333'}, 
                                ticks: {maxTicksLimit: 20, color: '#888', font: { size: 12 } },
                                title: { display: true, text: 'Time (s)', color: '#aaa', font: { size: 14 } }
                            } 
                        },
                        animation: false
                    }
                });

                // --- 3. Detailed Results Tables ---
                const tableArea = document.getElementById('detail-tables');
                tableArea.innerHTML = '';
                
                const renderEnhancedTable = (title, rows, color) => {
                    if (!rows || rows.length === 0) return;
                    
                    let html = `
                        <div style="margin-top: 30px; border-top: 1px solid #333; padding-top: 20px;">
                            <h3 style="color: ${color}; letter-spacing: 1px;">${title}</h3>
                            <table>
                                <thead>
                                    <tr>
                                        <th>Context</th>
                                        <th>TTFT</th>
                                        <th>Avg Latency</th>
                                        <th>P95</th>
                                        <th>P99</th>
                                        <th>Pass Rate</th>
                                    </tr>
                                </thead>
                                <tbody>`;
                    
                    rows.forEach(r => {
                        const pass = r.pass_rate_pct >= 95.0 ? 'pass' : (r.pass_rate_pct >= 80 ? 'warn' : 'fail');
                        const passLabel = r.pass_rate_pct === 100.0 ? 'PASS' : `${r.pass_rate_pct.toFixed(0)}%`;
                        
                        html += `<tr>
                            <td>${(r.context/1024).toFixed(0)}K <span style="color:#666; font-size:0.8em">(${r.context})</span></td>
                            <td>${r.ttft_ms ? r.ttft_ms.toFixed(0) + 'ms' : '-'}</td>
                            <td style="font-weight:bold">${r.avg_latency_ms.toFixed(0)}ms</td>
                            <td>${r.p95_ms ? r.p95_ms.toFixed(0) + 'ms' : '-'}</td>
                            <td>${r.p99_ms ? r.p99_ms.toFixed(0) + 'ms' : '-'}</td>
                            <td><span class="badge ${pass}">${passLabel}</span></td>
                        </tr>`;
                    });
                    html += `</tbody></table></div>`;
                    tableArea.innerHTML += html;
                };
                
                renderEnhancedTable("Baseline Protocol", data.baseline, "#00ffff");
                renderEnhancedTable("aiDAPTIV Protocol", data.aidaptiv, "#ff00ff");

                document.getElementById('detail-json').innerText = JSON.stringify(data, null, 2);
            }

            function closeReport() {
                document.getElementById('reports-list').style.display = 'block';
                document.getElementById('report-detail').style.display = 'none';
            }

            async function downloadReport(id) {
                const res = await fetch(`/api/reports/${id}`);
                const data = await res.json();
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `report_${id}.json`;
                a.click();
            }

            async function downloadCsv(id, stage) {
                const res = await fetch(`/api/reports/${id}/csv?stage=${stage}`);
                const data = await res.json();
                if (!data.csv) {
                    alert("No CSV data found for this stage.");
                    return;
                }
                const blob = new Blob([data.csv], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `telemetry_${id}_${stage}.csv`;
                a.click();
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
                    
                    // LATENCY METRICS
                    // TTFT
                    const ttft = data.app?.ttft_ms || 0;
                    document.getElementById('ttft_val').innerText = 
                        ttft > 0 ? `${Math.round(ttft)} ms` : '-- ms';
                    
                    // Runtime (live counter)
                    const runtime = data.app?.runtime_ms || 0;
                    document.getElementById('runtime_val').innerText = 
                        runtime > 0 ? `${(runtime / 1000).toFixed(1)}s` : '0.0s';
                    
                    // Last Request Latency
                    const lastLatency = data.app?.last_latency_ms || 0;
                    document.getElementById('last_latency_val').innerText = 
                        lastLatency > 0 ? `${(lastLatency / 1000).toFixed(1)}s` : '-- s';
                    
                    // TEST PROGRESS
                    if (data.test_progress) {
                        const progress = data.test_progress;
                        
                        // Show/hide status bar
                        if (progress.current_context > 0) {
                            document.getElementById('test-status').style.display = 'block';
                            const completedTests = Object.keys(progress.results).length;
                            const currentIdx = completedTests + 1;
                            document.getElementById('test-status-text').innerText = 
                                `Testing Context: ${progress.current_context} tokens (${currentIdx} of ${progress.total_contexts})`;
                        } else {
                            document.getElementById('test-status').style.display = 'none';
                        }
                        
                        // Update results table
                        if (Object.keys(progress.results).length > 0) {
                            document.getElementById('test-results-section').style.display = 'block';
                            updateResultsTable(progress.results, progress.current_context);
                        } else {
                            document.getElementById('test-results-section').style.display = 'none';
                        }
                    }
                } catch(e) {
                    console.log(e);
                }
            }
            
            function updateResultsTable(results, currentContext) {
                const tbody = document.getElementById('test-results-tbody');
                tbody.innerHTML = '';
                
                // Sort by context size
                const sorted = Object.entries(results).sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
                
                for (const [context, metrics] of sorted) {
                    const isActive = parseInt(context) === currentContext;
                    const row = document.createElement('tr');
                    row.style.background = isActive ? '#f0f7ff' : 'white';
                    row.style.borderBottom = '1px solid #eee';
                    
                    row.innerHTML = `
                        <td style="padding: 12px; color: #333;">${context} tokens</td>
                        <td style="padding: 12px; text-align: right; color: #333;">${Math.round(metrics.ttft_ms)} ms</td>
                        <td style="padding: 12px; text-align: right; color: #333;">${(metrics.runtime_ms / 1000).toFixed(1)}s</td>
                        <td style="padding: 12px; text-align: right; color: #333;">${metrics.tps.toFixed(1)}</td>
                        <td style="padding: 12px; text-align: center; color: #333;">
                            ${isActive ? '⏳ Running' : '✓ Complete'}
                        </td>
                    `;
                    tbody.appendChild(row);
                }
            }
            async function saveConfig() {
                const model = document.getElementById('model-select').value;
                const start = parseInt(document.getElementById('context-start').value);
                const end = parseInt(document.getElementById('context-end').value);
                const step = parseInt(document.getElementById('context-step').value);
                const stepMode = document.getElementById('step-mode').value;
                const concurrency = document.getElementById('concurrency').value;
                const runsPerContext = document.getElementById('runs-per-context').value;
                const name = document.getElementById('scenario-name').value;

                try {
                    const response = await fetch('/api/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            scenario_name: name,
                            model: model,
                            context_start: start,
                            context_end: end,
                            context_step: step,
                            step_mode: stepMode,
                            concurrency: parseInt(concurrency),
                            step_mode: stepMode,
                            concurrency: parseInt(concurrency),
                            runs_per_context: parseInt(runsPerContext),
                            ram_limit: parseFloat(document.getElementById('ram-limit').value),
                            swap_limit: parseFloat(document.getElementById('swap-limit').value)
                        })
                    });
                    
                    const result = await response.json();
                    if (!result.success) throw new Error(result.error);
                    console.log('Config updated:', result.message);
                } catch (err) {
                    console.error('Config update failed:', err);
                    alert('Failed to update config: ' + err.message);
                    throw err; // Propagate error to stop benchmark run
                }
            }

            function updateCommandUI() {
                const model = document.getElementById('model-select').value;
                const start = parseInt(document.getElementById('context-start').value);
                const end = parseInt(document.getElementById('context-end').value);
                const step = parseInt(document.getElementById('context-step').value);
                const stepMode = document.getElementById('step-mode').value;
                const concurrency = document.getElementById('concurrency').value;
                const runsPerContext = document.getElementById('runs-per-context').value;
                const name = document.getElementById('scenario-name').value;
                
                // Generate context array for display
                const contexts = [];
                if (stepMode === 'geometric') {
                    for (let c = start; c <= end; c *= 2) contexts.push(c);
                } else {
                    for (let c = start; c <= end; c += step) contexts.push(c);
                }
                
                const ramLimit = document.getElementById('ram-limit').value;
                const swapLimit = document.getElementById('swap-limit').value;
                
                let cmd = `sudo python3 benchmark.py`;
                
                // Append limit command ONLY if on Linux and values are present
                if (IS_LINUX && ramLimit && swapLimit) {
                    cmd += ` && ./limit_runner.sh ${ramLimit} ${swapLimit}`;
                }
                
                // Show scenario name separately if provided
                let displayCmd = cmd;
                if (name) {
                    displayCmd = `# Scenario: ${name}\n${cmd}`;
                }
                
                displayCmd += `\n\n# Config updated: Model=${model}, Users=${concurrency}, Runs/Context=${runsPerContext}, Contexts=${contexts.join(', ')}`;
                
                document.getElementById('generated-command').innerText = displayCmd;
                document.getElementById('command-output').style.display = 'block';
                document.getElementById('command-output').dataset.actualCommand = cmd;
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

            function updateScenarioName() {
                const model = document.getElementById('model-select').value;
                const start = parseInt(document.getElementById('context-start').value);
                const end = parseInt(document.getElementById('context-end').value);
                const step = parseInt(document.getElementById('context-step').value);
                const stepMode = document.getElementById('step-mode').value;
                const concurrency = document.getElementById('concurrency').value;
                const runsPerContext = document.getElementById('runs-per-context').value;
                
                // Format model name (e.g., "llama3.1:8b" -> "Llama-8B")
                let modelShort = model.split(':')[0].replace('llama3.1', 'Llama').replace('qwen2.5', 'Qwen');
                if (model.includes(':')) {
                    const size = model.split(':')[1].toUpperCase();
                    modelShort += `-${size}`;
                }
                
                // Format context sizes (e.g., 2048 -> "2K")
                const formatK = (val) => val >= 1024 ? `${Math.round(val / 1024)}K` : val;
                
                const stepStr = stepMode === 'geometric' ? 'double' : `${formatK(step)}-step`;
                const userStr = concurrency > 1 ? `_${concurrency}users` : '';
                const runsStr = runsPerContext > 1 ? `_${runsPerContext}runs` : '';
                
                const scenarioName = `${modelShort}_${formatK(start)}-${formatK(end)}_${stepStr}${userStr}${runsStr}`;
                document.getElementById('scenario-name').value = scenarioName;
            }
            
                // Auto-update scenario name and command UI when form changes
            document.addEventListener('DOMContentLoaded', () => {
                updateScenarioName();
                updateCommandUI(); // Initial populate

                ['model-select', 'context-start', 'context-end', 'context-step', 'step-mode', 'concurrency', 'runs-per-context', 'ram-limit', 'swap-limit'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) {
                        el.addEventListener('change', () => { updateScenarioName(); updateCommandUI(); });
                        if (el.tagName === 'INPUT') el.addEventListener('input', () => { updateScenarioName(); updateCommandUI(); });
                    }
                });
                
                // Initial check for reports
                const vr = document.getElementById('view-reports');
                if (vr) {
                    console.log('Page loaded, dashboard initialized.');
                }
                
                // Disable limits on non-Linux
                if (!IS_LINUX) {
                    const ramInput = document.getElementById('ram-limit');
                    const swapInput = document.getElementById('swap-limit');
                    if (ramInput) {
                        ramInput.disabled = true;
                        ramInput.title = "Memory limiting is only available on Linux.";
                        ramInput.parentElement.querySelector('label').innerText += " (system-managed)";
                    }
                    if (swapInput) {
                        swapInput.disabled = true;
                        swapInput.title = "Memory limiting is only available on Linux.";
                        swapInput.parentElement.querySelector('label').innerText += " (system-managed)";
                    }
                }
            });
            
            async function runBenchmark() {
                const statusDiv = document.getElementById('run-status');
                const statusText = document.getElementById('run-status-text');
                
                try {
                    // 1. First ensure config is saved
                    statusText.innerText = 'Saving configuration...';
                    statusText.style.color = '#fff';
                    
                    await saveConfig(); // This updates /api/config
                    
                    // 2. Trigger the run
                    statusText.innerText = 'Launching benchmark in Terminal...';
                    
                    // Get the generated command
                    const cmd = document.getElementById('command-output').dataset.actualCommand || 'sudo python3 benchmark.py';

                    // Also get limit command if possible, or just send the main one
                    // The user requested "Gen benchmake && Limit Cmd". 
                    // Let's see if we can generate the limit command too.
                    // Actually, let's just use the main command for now, as generateLimitCommand logic is separate.
                    // But wait, the user wants "Gen benchmake && Limit Cmd". 
                    // I should probably ensure the backend handles the combination or I construct it here.
                    // Let's construct it here if I can calls generateLimitCommand logic or just fetch it.
                    // Ideally, I'd have a generateLimitCommand string available.
                    
                    // Let's call generateLimitCommand() to populate its dataset too, effectively.
                    // But generateLimitCommand is a function that updates DOM.
                    // I will just modify runBenchmark to standardly invoke the API with the command.
                    
                    const response = await fetch('/api/run-benchmark', { 
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ command: cmd })
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        statusText.innerText = '✓ ' + data.message;
                        statusText.style.color = '#0f0';
                    } else {
                        statusText.innerText = '❌ Error: ' + data.error;
                        statusText.style.color = '#f44';
                    }
                } catch (e) {
                    statusText.innerText = '❌ Failed to launch: ' + e.message;
                    statusText.style.color = '#f44';
                    console.error(e);
                }
            }

            setInterval(poll, 1000);
        </script>
    </body>
    </html>
    """


@app.get("/snapshot")
def get_snapshot():
    global current_snapshot
    # Reset TPS to 0 if snapshot is stale (>5 seconds old)
    if current_snapshot.get("timestamp", 0) < time.time() - 5:
        if "app" in current_snapshot and isinstance(current_snapshot["app"], dict):
            current_snapshot["app"]["tps"] = 0.0
    return current_snapshot


@app.post("/update")
def receive_update(update: DashboardUpdate):
    global current_snapshot
    current_snapshot = update.model_dump()
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

                # Load Metadata for summary
                metadata = {}
                meta_path = os.path.join(full_path, "metadata_aidaptiv.json")
                if not os.path.exists(meta_path):
                    meta_path = os.path.join(
                        full_path, "metadata_baseline.json")

                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, 'r') as f:
                            metadata = json.load(f)
                    except:
                        pass

                results.append({
                    "id": entry,
                    "timestamp": entry,  # The ID is the timestamp
                    "has_summary": bool(json_files),
                    "summary": summary,
                    "metadata": metadata
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

    # Load Metadata (for technical config section)
    metadata_p = os.path.join(run_dir, "metadata_aidaptiv.json")
    if not os.path.exists(metadata_p):
        metadata_p = os.path.join(run_dir, "metadata_baseline.json")

    data["metadata"] = {}
    if os.path.exists(metadata_p):
        try:
            with open(metadata_p, 'r') as f:
                data["metadata"] = json.load(f)
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

        # Update concurrency if provided
        if 'concurrency' in data:
            config['test']['concurrency'] = int(data['concurrency'])

        # Update runs_per_context if provided
        if 'runs_per_context' in data:
            config['test']['runs_per_context'] = int(data['runs_per_context'])

        # Update scenario_name if provided
        if 'scenario_name' in data:
            config['test']['scenario_name'] = data['scenario_name']

        # Update step_mode if provided
        if 'step_mode' in data:
            config['test']['step_mode'] = data['step_mode']

        # Update context lengths if provided
        if 'context_start' in data and 'context_end' in data:
            start = int(data['context_start'])
            end = int(data['context_end'])
            step = int(data.get('context_step', 1024))
            mode = data.get('step_mode', 'linear')

            if mode == 'geometric':
                contexts = []
                curr = start
                while curr <= end:
                    contexts.append(curr)
                    curr *= 2
            else:
                contexts = list(range(start, end + 1, step))

            config['test']['context_lengths'] = contexts

        # Update limits if provided
        if 'ram_limit' in data:
            config['test']['ram_limit'] = float(data['ram_limit'])
        if 'swap_limit' in data:
            config['test']['swap_limit'] = float(data['swap_limit'])

        # Write back to file
        with open('config.yaml', 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return {"success": True, "message": f"Config updated (backup saved to {backup_path})"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/run-benchmark")
def run_benchmark(payload: dict = None):
    """Open Terminal and run the benchmark command (macOS only)."""
    try:
        import subprocess

        # Get command from payload or default
        cmd_to_run = "sudo python3 benchmark.py"
        if payload and "command" in payload:
            cmd_to_run = payload["command"]

        # Get the current working directory
        cwd = os.getcwd()

        # Build the command to run in Terminal
        # Escape quotes for AppleScript
        final_cmd = f'cd \\"{cwd}\\" && {cmd_to_run}'

        # Use osascript to open Terminal and run the command
        # Added 'activate' to force window to top
        applescript = f'''tell application "Terminal"
    activate
    set newTab to do script "{final_cmd}"
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
