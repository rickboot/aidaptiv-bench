import pandas as pd
import matplotlib.pyplot as plt
import json
import os
import argparse


def plot_ttft_comparison(baseline_json: str, aidaptiv_json: str, output_dir: str):
    """
    Generates TTFT comparison chart.
    """
    try:
        with open(baseline_json) as f:
            b_data = json.load(f)
        with open(aidaptiv_json) as f:
            a_data = json.load(f)

        # Extract Data
        # Assuming JSON list of {context, avg_latency_ms, pass_rate_pct}
        # Note: simplistic matching by index or context value

        # Helper dicts
        b_map = {x['context']: x for x in b_data}
        a_map = {x['context']: x for x in a_data}

        all_contexts = sorted(list(set(b_map.keys()) | set(a_map.keys())))

        b_vals = [b_map.get(c, {}).get('avg_latency_ms', 0)
                  for c in all_contexts]
        a_vals = [a_map.get(c, {}).get('avg_latency_ms', 0)
                  for c in all_contexts]

        # Identify OOMs (where pass_rate < 100 or missing)
        # To make it visible, we might explicitly check pass_rate

        plt.figure(figsize=(10, 6))
        x = range(len(all_contexts))
        width = 0.35

        plt.bar([i - width/2 for i in x], b_vals, width,
                label='Baseline', color='red', alpha=0.7)
        plt.bar([i + width/2 for i in x], a_vals, width,
                label='aiDAPTIV', color='blue', alpha=0.7)

        plt.xlabel('Context Length')
        plt.ylabel('Avg Latency (ms)')
        plt.title('Performance Comparison: Baseline vs aiDAPTIV')
        plt.xticks(x, all_contexts)
        plt.legend()
        plt.grid(True, alpha=0.3)

        out_path = os.path.join(output_dir, 'ttft_comparison.png')
        plt.savefig(out_path)
        print(f"Stats chart saved to {out_path}")
        plt.close()

    except Exception as e:
        print(f"Error plotting TTFT: {e}")


def plot_ram_timeline(telemetry_csv: str, output_dir: str, label: str):
    """
    Generates RAM usage timeline.
    """
    try:
        df = pd.read_csv(telemetry_csv)

        plt.figure(figsize=(12, 6))

        # RAM
        plt.plot(df['elapsed_sec'], df['ram_used_gb'],
                 label='RAM Used (GB)', color='green')

        # VRAM
        plt.plot(df['elapsed_sec'], df['vram_used_gb'],
                 label='VRAM Used (GB)', color='orange')

        # Disk IO (secondary axis?)
        # For simplicity, just RAM/VRAM focused for OOM story

        plt.xlabel('Time (s)')
        plt.ylabel('Memory (GB)')
        plt.title(f'Memory Usage Timeline: {label}')
        plt.legend()
        plt.grid(True)

        out_path = os.path.join(output_dir, f'ram_timeline_{label}.png')
        plt.savefig(out_path)
        print(f"Timeline chart saved to {out_path}")
        plt.close()

    except Exception as e:
        print(f"Error plotting Timeline: {e}")


if __name__ == "__main__":
    # Test CLI
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", help="Path to results_baseline.json")
    parser.add_argument("--aidaptiv", help="Path to results_aidaptiv.json")
    parser.add_argument("--telemetry", help="Path to metrics.csv")
    parser.add_argument("--output", default=".")

    args = parser.parse_args()

    if args.baseline and args.aidaptiv:
        plot_ttft_comparison(args.baseline, args.aidaptiv, args.output)

    if args.telemetry:
        plot_ram_timeline(args.telemetry, args.output, "test")
