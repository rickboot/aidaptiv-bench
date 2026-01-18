import platform
import subprocess
import json
import shutil
import psutil
from typing import List, Dict, Any


class DeviceDetector:
    def __init__(self):
        self.system = platform.system()

    def get_system_info(self) -> Dict[str, Any]:
        return {
            "os": self.system,
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2)
        }

    def detect_gpus(self) -> List[Dict[str, str]]:
        gpus = []
        # Attempt NVIDIA (nvidia-smi)
        if shutil.which("nvidia-smi"):
            try:
                # Query minimal info: Index, Name, UUID
                cmd = ["nvidia-smi", "--query-gpu=index,name,uuid,memory.total",
                       "--format=csv,noheader,nounits"]
                output = subprocess.check_output(cmd).decode("utf-8")
                for line in output.strip().split("\n"):
                    if line:
                        parts = [x.strip() for x in line.split(",")]
                        if len(parts) >= 4:
                            gpus.append({
                                "type": "NVIDIA",
                                "id": parts[0],
                                "name": parts[1],
                                "uuid": parts[2],
                                "vram_total_mb": int(parts[3])
                            })
            except Exception as e:
                print(f"Error detecting NVIDIA GPUs: {e}")

        # Attempt AMD (rocm-smi) - simplistic check
        # In real AMD envs, might use /opt/rocm/bin/rocm-smi or amdsmi lib
        elif shutil.which("rocm-smi"):
            try:
                output = subprocess.check_output(
                    ["rocm-smi", "--showid", "--showproductname", "--json"]).decode("utf-8")
                # Parsing ROCm JSON output varies by version, simplified placeholder:
                data = json.loads(output)
                # Iterate dynamically as keys might be "card0", "card1" etc
                for card_key, info in data.items():
                    gpus.append({
                        "type": "AMD",
                        "id": card_key,
                        "name": info.get("Card Series", "Unknown AMD GPU"),
                        "vram_total_mb": 0  # metrics.py will poll actuals
                    })
            except Exception:
                pass

        return gpus

    def detect_phison_storage(self) -> List[Dict[str, Any]]:
        """
        Scans block devices for Phison identifiers.
        Primary target: Linux (DGX/Strix). 
        """
        phison_drives = []

        if self.system == "Linux":
            try:
                # lsblk -d -o NAME,MODEL,SIZE,ROTA,TYPE -J
                cmd = ["lsblk", "-d", "-o", "NAME,MODEL,SERIAL,SIZE,TYPE", "-J"]
                output = subprocess.check_output(cmd).decode("utf-8")
                data = json.loads(output)

                for device in data.get("blockdevices", []):
                    model = device.get("model", "").lower()
                    if "phison" in model or "e18" in model or "e26" in model:  # Common controller strings
                        phison_drives.append({
                            "device": f"/dev/{device['name']}",
                            "model": device['model'],
                            "size": device['size'],
                            "is_phison": True
                        })
            except Exception as e:
                print(f"Error scanning linux storage: {e}")

        elif self.system == "Darwin":  # Mac Dev Env
            try:
                cmd = ["system_profiler", "SPNVMeDataType", "-json"]
                output = subprocess.check_output(cmd).decode("utf-8")
                data = json.loads(output)
                # Parse structure deep nested
                nvme_data = data.get("SPNVMeDataType", [])
                for drive in nvme_data:
                    # Mac JSON structure is variable, simplifying check
                    if "Phison" in str(drive):
                        phison_drives.append(
                            {"model": "Simulated Phison via Mac", "is_phison": True})
            except:
                pass

        return phison_drives
