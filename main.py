import time
import uvicorn
import threading
from backend.metrics import SystemMonitor
# from ui import launch_ui 

def start_backend():
    print("Starting aiDAPTIV Benchmarking Backend...")
    # Initialize Core Components
    monitor = SystemMonitor()
    monitor.start_monitoring()
    
    # Keep main thread alive for now
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        monitor.stop_monitoring()

if __name__ == "__main__":
    start_backend()
