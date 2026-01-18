import requests
import json
import time

ENDPOINT = "http://localhost:11434/v1/completions"
MODEL = "llama3.1:8b"


def check_runtime():
    print(f"🔍 Checking Runtime at {ENDPOINT}...")

    payload = {
        "model": MODEL,
        "prompt": "Hello, world!",
        "max_tokens": 10,
        "stream": False
    }

    try:
        t0 = time.time()
        # Ollama first load can be slow
        resp = requests.post(ENDPOINT, json=payload, timeout=30)
        t1 = time.time()

        if resp.status_code == 200:
            print("✅ Runtime Accessible!")
            print(f"⏱️  Latency: {round((t1-t0)*1000, 2)}ms")
            print(f"📄 Response: {resp.json()}")
            return True
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Connection Refused. Is the server running?")
        return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


if __name__ == "__main__":
    check_runtime()
