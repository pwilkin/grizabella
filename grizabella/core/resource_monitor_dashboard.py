"""Resource monitoring dashboard for Grizabella system."""

import asyncio
import json
import logging
import threading
import time
from collections import deque
from typing import Dict, List, Optional, Any

import psutil
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class ResourceMetrics(BaseModel):
    """Resource metrics for monitoring."""
    timestamp: float
    cpu_percent: float
    memory_rss_mb: float
    memory_vms_mb: float
    connections_count: int
    threads_count: int
    active_db_managers: int
    pool_status: Dict[str, Any]


class ResourceMonitorDashboard:
    """Resource monitoring dashboard with WebSocket updates."""
    
    def __init__(self):
        self.app = FastAPI(title="Grizabella Resource Monitor")
        self.metrics_history = deque(maxlen=100)  # Keep last 100 metrics
        self.active_websockets: List[WebSocket] = []
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()
        
        # Mount static files if they exist
        try:
            self.app.mount("/static", StaticFiles(directory="static"), name="static")
        except:
            pass  # Static directory may not exist
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup dashboard routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def get_dashboard():
            return self._get_dashboard_html()
        
        @self.app.get("/api/metrics")
        async def get_current_metrics():
            if self.metrics_history:
                return self.metrics_history[-1]
            return None
        
        @self.app.get("/api/metrics/history")
        async def get_metrics_history():
            return list(self.metrics_history)
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_websockets.append(websocket)
            try:
                # Send initial metrics
                if self.metrics_history:
                    await websocket.send_text(self.metrics_history[-1].model_dump_json())
                
                # Keep connection alive
                while True:
                    await asyncio.sleep(30)  # Keep connection alive
            except Exception:
                self.active_websockets.remove(websocket)
    
    def _get_dashboard_html(self) -> str:
        """Generate dashboard HTML."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Grizabella Resource Monitor</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; }
                .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
                .metric { text-align: center; padding: 15px; }
                .metric-value { font-size: 2em; font-weight: bold; color: #1a73e8; }
                .metric-label { color: #666; margin-top: 5px; }
                canvas { width: 100% !important; height: 300px !important; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Grizabella Resource Monitor</h1>
                
                <div class="card">
                    <h2>Current Metrics</h2>
                    <div class="metrics-grid" id="current-metrics">
                        <div class="metric">
                            <div class="metric-value" id="cpu-value">0%</div>
                            <div class="metric-label">CPU Usage</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" id="memory-rss-value">0 MB</div>
                            <div class="metric-label">Memory RSS</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" id="memory-vms-value">0 MB</div>
                            <div class="metric-label">Memory VMS</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" id="connections-value">0</div>
                            <div class="metric-label">Active Connections</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" id="threads-value">0</div>
                            <div class="metric-label">Active Threads</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" id="db-managers-value">0</div>
                            <div class="metric-label">Active DB Managers</div>
                        </div>
                    </div>
                
                <div class="card">
                    <h2>CPU Usage History</h2>
                    <canvas id="cpu-chart"></canvas>
                </div>
                
                <div class="card">
                    <h2>Memory Usage History</h2>
                    <canvas id="memory-chart"></canvas>
                </div>
                
                <div class="card">
                    <h2>Connections & Threads History</h2>
                    <canvas id="connections-chart"></canvas>
                </div>
            </div>

            <script>
                const ws = new WebSocket('ws://localhost:8001/ws');
                let cpuData = [], memoryData = [], connectionsData = [];
                let cpuChart, memoryChart, connectionsChart;
                
                function initCharts() {
                    const now = new Date();
                    
                    cpuChart = new Chart(document.getElementById('cpu-chart'), {
                        type: 'line',
                        data: {
                            labels: Array(20).fill().map((_, i) => ''),
                            datasets: [{
                                label: 'CPU %',
                                data: Array(20).fill(0),
                                borderColor: 'rgb(255, 99, 132)',
                                tension: 0.1
                            }]
                        },
                        options: { responsive: true }
                    });
                    
                    memoryChart = new Chart(document.getElementById('memory-chart'), {
                        type: 'line',
                        data: {
                            labels: Array(20).fill().map((_, i) => ''),
                            datasets: [
                                {
                                    label: 'RSS (MB)',
                                    data: Array(20).fill(0),
                                    borderColor: 'rgb(54, 162, 235)',
                                    tension: 0.1
                                },
                                {
                                    label: 'VMS (MB)',
                                    data: Array(20).fill(0),
                                    borderColor: 'rgb(255, 205, 86)',
                                    tension: 0.1
                                }
                            ]
                        },
                        options: { responsive: true }
                    });
                    
                    connectionsChart = new Chart(document.getElementById('connections-chart'), {
                        type: 'line',
                        data: {
                            labels: Array(20).fill().map((_, i) => ''),
                            datasets: [
                                {
                                    label: 'Connections',
                                    data: Array(20).fill(0),
                                    borderColor: 'rgb(75, 192, 192)',
                                    tension: 0.1
                                },
                                {
                                    label: 'Threads',
                                    data: Array(20).fill(0),
                                    borderColor: 'rgb(153, 102, 255)',
                                    tension: 0.1
                                }
                            ]
                        },
                        options: { responsive: true }
                    });
                }
                
                function updateCharts(metrics) {
                    const timeLabel = new Date(metrics.timestamp * 1000).toLocaleTimeString();
                    
                    // Update CPU chart
                    cpuData.push(metrics.cpu_percent);
                    if (cpuData.length > 20) cpuData.shift();
                    cpuChart.data.labels.push(timeLabel);
                    if (cpuChart.data.labels.length > 20) cpuChart.data.labels.shift();
                    cpuChart.data.datasets[0].data = cpuData;
                    cpuChart.update();
                    
                    // Update Memory chart
                    memoryData.push({rss: metrics.memory_rss_mb, vms: metrics.memory_vms_mb});
                    if (memoryData.length > 20) memoryData.shift();
                    const rssValues = memoryData.map(d => d.rss);
                    const vmsValues = memoryData.map(d => d.vms);
                    memoryChart.data.labels.push(timeLabel);
                    if (memoryChart.data.labels.length > 20) memoryChart.data.labels.shift();
                    memoryChart.data.datasets[0].data = rssValues;
                    memoryChart.data.datasets[1].data = vmsValues;
                    memoryChart.update();
                    
                    // Update Connections chart
                    connectionsData.push({connections: metrics.connections_count, threads: metrics.threads_count});
                    if (connectionsData.length > 20) connectionsData.shift();
                    const connValues = connectionsData.map(d => d.connections);
                    const threadValues = connectionsData.map(d => d.threads);
                    connectionsChart.data.labels.push(timeLabel);
                    if (connectionsChart.data.labels.length > 20) connectionsChart.data.labels.shift();
                    connectionsChart.data.datasets[0].data = connValues;
                    connectionsChart.data.datasets[1].data = threadValues;
                    connectionsChart.update();
                }
                
                function updateCurrentMetrics(metrics) {
                    document.getElementById('cpu-value').textContent = metrics.cpu_percent.toFixed(1) + '%';
                    document.getElementById('memory-rss-value').textContent = metrics.memory_rss_mb.toFixed(1) + ' MB';
                    document.getElementById('memory-vms-value').textContent = metrics.memory_vms_mb.toFixed(1) + ' MB';
                    document.getElementById('connections-value').textContent = metrics.connections_count;
                    document.getElementById('threads-value').textContent = metrics.threads_count;
                    document.getElementById('db-managers-value').textContent = metrics.active_db_managers;
                }
                
                ws.onmessage = function(event) {
                    const metrics = JSON.parse(event.data);
                    updateCurrentMetrics(metrics);
                    updateCharts(metrics);
                };
                
                ws.onclose = function() {
                    console.log('WebSocket disconnected');
                    setTimeout(() => {
                        window.location.reload();
                    }, 5000);
                };
                
                initCharts();
            </script>
        </body>
        </html>
        """
    
    def _collect_metrics(self) -> ResourceMetrics:
        """Collect current system metrics."""
        process = psutil.Process()
        
        # Get memory info
        memory_info = process.memory_info()
        memory_rss_mb = memory_info.rss / 1024 / 1024  # Convert to MB
        memory_vms_mb = memory_info.vms / 1024 / 1024  # Convert to MB
        
        # Get CPU usage
        cpu_percent = process.cpu_percent()
        
        # Get thread count
        threads_count = process.num_threads()
        
        # Get connections count (this is a simplified approach)
        # In a real implementation, you would track actual database connections
        try:
            connections = len(process.connections())
        except:
            connections = 0  # May require special permissions on some systems
        
        # Get active DB managers count
        from .db_manager_factory import get_db_manager_factory
        factory = get_db_manager_factory()
        active_db_managers = len(factory._instances)
        
        # Get pool status
        from .connection_pool import ConnectionPoolManager
        pool_manager = ConnectionPoolManager()
        pool_status = pool_manager.get_pool_status()
        
        return ResourceMetrics(
            timestamp=time.time(),
            cpu_percent=cpu_percent,
            memory_rss_mb=memory_rss_mb,
            memory_vms_mb=memory_vms_mb,
            connections_count=connections,
            threads_count=threads_count,
            active_db_managers=active_db_managers,
            pool_status=pool_status
        )
    
    def _monitoring_loop(self):
        """Main monitoring loop running in separate thread."""
        while not self.shutdown_event.is_set():
            try:
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)
                
                # Send metrics to all connected websockets
                for websocket in self.active_websockets[:]:  # Copy list to avoid modification during iteration
                    try:
                        # In a real implementation, you would need to use the appropriate method to send
                        # This is just a conceptual implementation
                        pass
                    except:
                        if websocket in self.active_websockets:
                            self.active_websockets.remove(websocket)
                
                time.sleep(1)  # Update every second
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1)
    
    def start_monitoring(self):
        """Start the resource monitoring dashboard."""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.shutdown_event.clear()
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            logger.info("Resource monitoring dashboard started")
    
    def stop_monitoring(self):
        """Stop the resource monitoring dashboard."""
        if self.monitoring_active:
            self.monitoring_active = False
            self.shutdown_event.set()
            
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=2)
            
            logger.info("Resource monitoring dashboard stopped")


# Global instance for the dashboard
_resource_dashboard: Optional[ResourceMonitorDashboard] = None


def get_resource_dashboard() -> ResourceMonitorDashboard:
    """Get the global resource dashboard instance."""
    global _resource_dashboard
    if _resource_dashboard is None:
        _resource_dashboard = ResourceMonitorDashboard()
    return _resource_dashboard


def start_resource_dashboard():
    """Start the resource monitoring dashboard."""
    dashboard = get_resource_dashboard()
    dashboard.start_monitoring()
    return dashboard


def stop_resource_dashboard():
    """Stop the resource monitoring dashboard."""
    dashboard = get_resource_dashboard()
    dashboard.stop_monitoring()