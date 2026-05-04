#!/usr/bin/env python3
import argparse, re, subprocess, time, tempfile
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

TIME_RE = re.compile(r"^(.*?)\.\.\.\s+(\d+)ms$", re.M)

def run(cmd, timeout=None):
    return subprocess.run(
        cmd,
        timeout=timeout,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

def parse_running_psi(text):
    for name, ms in TIME_RE.findall(text):
        key = name.strip().lower().replace(" ", "_")
        if key == "running_psi":
            return int(ms)
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend", default="./out/build/linux/frontend/frontend")
    ap.add_argument("--generator", default="./generate_psi_inputs.py")
    ap.add_argument("--outdir", default="psi_bench_plots")
    ap.add_argument("--n-min", type=int, required=True)
    ap.add_argument("--n-max", type=int, required=True)
    ap.add_argument("--intersections", type=int, nargs="+", required=True)
    ap.add_argument("--rep", type=int, default=3)
    ap.add_argument("--ca", default="certs/ca.cert.pem")
    ap.add_argument("--sender-cert", default="certs/sender.cert.pem")
    ap.add_argument("--sender-key", default="certs/sender.key.pem")
    ap.add_argument("--receiver-cert", default="certs/receiver.cert.pem")
    ap.add_argument("--receiver-key", default="certs/receiver.key.pem")
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    plots_dir = Path(args.outdir)
    plots_dir.mkdir(parents=True, exist_ok=True)

    rows = []

    with tempfile.TemporaryDirectory(prefix="psi_inputs_") as tmp:
        input_root = Path(tmp)

        for n in range(args.n_min, args.n_max + 1):
            set_size = 1 << n

            for inter in args.intersections:
                if inter > set_size:
                    print(f"Skipping n={n}, intersection={inter}: too large")
                    continue

                for rep in range(args.rep):
                    case = f"n{n}_i{inter}_rep{rep}"
                    case_input_dir = input_root / case
                    case_input_dir.mkdir(parents=True, exist_ok=True)

                    gen_cmd = [
                        "python3", args.generator,
                        "-n", str(n),
                        "-i", str(inter),
                        "-o", str(case_input_dir),
                        "--seed", str(42 + rep),
                    ]

                    gen = run(gen_cmd, timeout=args.timeout)
                    if gen.returncode != 0:
                        raise RuntimeError(f"Generator failed for {case}:\n{gen.stdout}")

                    receiver_cmd = [
                        args.frontend,
                        "-r", "1",
                        "-in", str(case_input_dir / "receiver.csv"),
                        "-csv",
                        "-tls",
                        "-CA", args.ca,
                        "-pk", args.receiver_cert,
                        "-sk", args.receiver_key,
                        "-v",
                    ]

                    sender_cmd = [
                        args.frontend,
                        "-r", "0",
                        "-in", str(case_input_dir / "sender.csv"),
                        "-csv",
                        "-tls",
                        "-CA", args.ca,
                        "-pk", args.sender_cert,
                        "-sk", args.sender_key,
                        "-v",
                    ]

                    print(f"Running {case}")

                    receiver = subprocess.Popen(
                        receiver_cmd,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                    )

                    time.sleep(0.5)

                    sender = subprocess.Popen(
                        sender_cmd,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                    )

                    try:
                        sender_out, _ = sender.communicate(timeout=args.timeout)
                        receiver_out, _ = receiver.communicate(timeout=args.timeout)
                    except subprocess.TimeoutExpired:
                        sender.kill()
                        receiver.kill()
                        raise RuntimeError(f"Timeout while running {case}")

                    sender_ms = parse_running_psi(sender_out)
                    receiver_ms = parse_running_psi(receiver_out)

                    rows.append({
                        "n": n,
                        "set_size": set_size,
                        "intersection": inter,
                        "rep": rep,
                        "sender_running_psi": sender_ms,
                        "receiver_running_psi": receiver_ms,
                    })

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError("No benchmark results collected.")

    # Plot 1: PSI runtime vs set size, receiver + sender
    plt.figure(figsize=(9, 6))

    receiver_grouped = df.groupby("set_size")["receiver_running_psi"].mean()
    sender_grouped = df.groupby("set_size")["sender_running_psi"].mean()

    plt.plot(receiver_grouped.index, receiver_grouped.values, marker="o", label="receiver")
    plt.plot(sender_grouped.index, sender_grouped.values, marker="o", label="sender")

    plt.xscale("log", base=2)
    plt.xlabel("Set size")
    plt.ylabel("Mean PSI runtime, ms")
    plt.title("PSI runtime vs set size")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / "psi_runtime_vs_set_size.png", dpi=180)
    plt.close()

    # Plot 2: intersection size effect on execution time
    plt.figure(figsize=(9, 6))

    receiver_by_inter = df.groupby("intersection")["receiver_running_psi"].mean()
    sender_by_inter = df.groupby("intersection")["sender_running_psi"].mean()

    plt.plot(receiver_by_inter.index, receiver_by_inter.values, marker="o", label="receiver")
    plt.plot(sender_by_inter.index, sender_by_inter.values, marker="o", label="sender")

    plt.xlabel("Intersection size")
    plt.ylabel("Mean PSI runtime, ms")
    plt.title("Effect of intersection size on PSI runtime")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / "psi_runtime_vs_intersection_size.png", dpi=180)
    plt.close()

    print(f"Saved plots in: {plots_dir}")

if __name__ == "__main__":
    main()
