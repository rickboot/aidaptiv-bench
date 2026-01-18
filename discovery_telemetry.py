import psutil
import time
import shutil


def check_telemetry():
    print("🔍 Checking System Telemetry Access...")

    # 1. RAM
    mem = psutil.virtual_memory()
    print(
        f"✅ RAM: {round(mem.used/1024**3, 1)} / {round(mem.total/1024**3, 1)} GB (Used/Total)")

    # 2. Disk
    disk_usage = psutil.disk_usage('/')
    print(f"✅ Disk Root: {round(disk_usage.used/1024**3, 1)} GB used")

    # 3. NVIDIA GPU (via simple SMI check)
    if shutil.which("nvidia-smi"):
        print("✅ nvidia-smi found (NVIDIA GPU support likely)")
    else:
        print("⚠️ nvidia-smi NOT found (GPU Telemetry might be limited)")

    # 4. Loop Check
    print("\nStarting 3s polling loop to verify IO counters...")
    for i in range(3):
        io = psutil.disk_io_counters()
        print(
            f"   [{i}] Read: {io.read_bytes//1024//1024} MB | Write: {io.write_bytes//1024//1024} MB")
        time.sleep(1.0)

    print("\n✅ Telemetry Check Complete")


if __name__ == "__main__":
    check_telemetry()
