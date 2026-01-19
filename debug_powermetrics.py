import subprocess
import re
import sys
import time

print("Running sudo powermetrics check (needs sudo)...")
try:
    cmd = ["sudo", "powermetrics", "-i", "50", "-n", "1", "-s", "gpu_power"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    output = res.stdout
    print(f"--- OUTPUT START ---\n{output[:300]}\n--- OUTPUT END ---")

    util = 0.0
    m_util = re.search(
        r"GPU HW active residency:\s+([\d\.]+)%", output, re.IGNORECASE)
    if not m_util:
        print("Regex 1 (GPU HW active residency) FAILED.")
        m_util = re.search(
            r"GPU active residency:\s+([\d\.]+)%", output, re.IGNORECASE)
        if not m_util:
            print("Regex 2 (GPU active residency) FAILED.")
        else:
            print(f"Regex 2 MATCHED: {m_util.group(1)}%")
            util = float(m_util.group(1))
    else:
        print(f"Regex 1 MATCHED: {m_util.group(1)}%")
        util = float(m_util.group(1))

    print(f"Final Parsed Utilization: {util}%")

except Exception as e:
    print(f"Error: {e}")
