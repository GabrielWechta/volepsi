#!/usr/bin/env python3
"""
VOLE-PSI runner — three subcommands:

  bench      spawn both parties on localhost (local correctness / perf check)
  sender     run as the PSI sender (real two-party, peer runs receiver)
  receiver   run as the PSI receiver (real two-party, peer runs sender)

Examples:
  # local benchmark without TLS
  python3 psi.py bench -n 20 -i 1000

  # local benchmark with TLS
  python3 psi.py bench -n 20 -i 1000 --tls

  # real two-party run with TLS — run on separate machines
  python3 psi.py receiver --in psi_inputs/receiver.csv --tls
  python3 psi.py sender   --in psi_inputs/sender.csv   --tls --ip <receiver-host>:1212
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

FRONTEND = Path("./out/build/linux/frontend/frontend")
CERT_DIR = Path("certs")

CERTS = {
    "ca":            CERT_DIR / "ca.cert.pem",
    "receiver_cert": CERT_DIR / "receiver.cert.pem",
    "receiver_key":  CERT_DIR / "receiver.key.pem",
    "sender_cert":   CERT_DIR / "sender.cert.pem",
    "sender_key":    CERT_DIR / "sender.key.pem",
}


def _tls_flags(role):
    cert = CERTS["receiver_cert"] if role == "receiver" else CERTS["sender_cert"]
    key  = CERTS["receiver_key"]  if role == "receiver" else CERTS["sender_key"]
    return ["-tls", "-CA", str(CERTS["ca"]), "-pk", str(cert), "-sk", str(key)]


def _check_frontend():
    if not FRONTEND.exists():
        sys.exit(
            f"Frontend binary not found: {FRONTEND}\n"
            "Build first:\n"
            "  python3 build.py -DVOLE_PSI_ENABLE_OPENSSL=true -DVOLE_PSI_ENABLE_BOOST=true"
        )


def _check_certs():
    missing = [str(v) for v in CERTS.values() if not v.exists()]
    if missing:
        sys.exit(
            "TLS certificates missing:\n  " + "\n  ".join(missing) + "\n"
            "Generate them with:\n  bash bootrstrap_certs.sh"
        )


def _generate_inputs(n, intersection, outdir, seed=42):
    cmd = [
        sys.executable, "generate_psi_inputs.py",
        "-n", str(n),
        "-i", str(intersection),
        "-o", str(outdir),
        "--seed", str(seed),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        sys.exit(f"Input generation failed:\n{result.stderr or result.stdout}")
    lines = result.stdout.strip().splitlines()
    # generate_psi_inputs.py prints sender path then receiver path
    return Path(lines[0]), Path(lines[1])


def cmd_bench(args):
    _check_frontend()
    if args.tls:
        _check_certs()

    outdir = Path(args.outdir)
    set_size = 1 << args.n
    print(
        f"Generating inputs: n={args.n} (2^{args.n} = {set_size:,} items), "
        f"intersection={args.intersection:,}"
    )
    sender_csv, receiver_csv = _generate_inputs(args.n, args.intersection, outdir)
    print(f"  sender:   {sender_csv}")
    print(f"  receiver: {receiver_csv}")

    out_file = str(args.out) if args.out else str(receiver_csv) + ".out"

    recv_cmd = [
        str(FRONTEND), "-r", "1",
        "-in", str(receiver_csv), "-csv",
        "-out", out_file,
        "-ip", args.ip,
        "-v",
    ]
    send_cmd = [
        str(FRONTEND), "-r", "0",
        "-in", str(sender_csv), "-csv",
        "-ip", args.ip,
        "-v",
    ]

    if args.tls:
        recv_cmd += _tls_flags("receiver")
        send_cmd += _tls_flags("sender")
    else:
        recv_cmd += ["-server", "1"]

    mode = "TLS" if args.tls else "no TLS"
    print(f"\nStarting receiver ({mode}) ...")
    recv_proc = subprocess.Popen(recv_cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(0.5)

    print(f"Starting sender ({mode}) ...")
    send_proc = subprocess.Popen(send_cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    send_out, _    = send_proc.communicate()
    recv_out_text, _ = recv_proc.communicate()

    print("\n--- receiver ---")
    print(recv_out_text)
    print("--- sender ---")
    print(send_out)

    if recv_proc.returncode != 0 or send_proc.returncode != 0:
        sys.exit("PSI run failed — see output above.")

    print(f"Intersection written to: {out_file}")


def cmd_receiver(args):
    _check_frontend()
    if args.tls:
        _check_certs()

    out_file = str(args.out) if args.out else str(args.input) + ".out"
    cmd = [
        str(FRONTEND), "-r", "1",
        "-in", str(args.input), "-csv",
        "-out", out_file,
        "-ip", args.ip,
    ]
    if args.tls:
        cmd += _tls_flags("receiver")
    else:
        cmd += ["-server", "1"]
    if args.verbose:
        cmd.append("-v")

    mode = "TLS" if args.tls else "plaintext"
    print(f"Receiver listening on {args.ip} ({mode}) — waiting for sender ...")
    subprocess.run(cmd)


def cmd_sender(args):
    _check_frontend()
    if args.tls:
        _check_certs()

    cmd = [
        str(FRONTEND), "-r", "0",
        "-in", str(args.input), "-csv",
        "-ip", args.ip,
    ]
    if args.tls:
        cmd += _tls_flags("sender")
    if args.verbose:
        cmd.append("-v")

    mode = "TLS" if args.tls else "plaintext"
    print(f"Sender connecting to {args.ip} ({mode}) ...")
    subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(
        prog="psi.py",
        description="VOLE-PSI runner: local bench or real two-party execution.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── bench ────────────────────────────────────────────────────────────────
    p_bench = sub.add_parser(
        "bench",
        help="local benchmark — spawns both parties on localhost",
    )
    p_bench.add_argument(
        "-n", type=int, required=True,
        help="log2 set size (e.g. 20 → 2^20 = 1,048,576 items per party)",
    )
    p_bench.add_argument(
        "-i", "--intersection", type=int, required=True,
        help="number of items shared between the two sets",
    )
    p_bench.add_argument(
        "--tls", action="store_true",
        help="enable TLS (requires certs/ — run bash bootrstrap_certs.sh first)",
    )
    p_bench.add_argument("--ip", default="localhost:1212", metavar="HOST:PORT")
    p_bench.add_argument(
        "--outdir", default="psi_inputs",
        help="directory for generated CSV inputs (default: psi_inputs/)",
    )
    p_bench.add_argument(
        "--out", default=None, metavar="FILE",
        help="output file for the receiver's intersection (default: <receiver.csv>.out)",
    )
    p_bench.set_defaults(func=cmd_bench)

    # ── receiver ─────────────────────────────────────────────────────────────
    p_recv = sub.add_parser(
        "receiver",
        help="run as PSI receiver — listens for the sender to connect",
    )
    p_recv.add_argument("--in", dest="input", required=True, type=Path, metavar="FILE")
    p_recv.add_argument(
        "--tls", action="store_true",
        help="enable TLS (requires certs/)",
    )
    p_recv.add_argument(
        "--ip", default="localhost:1212", metavar="HOST:PORT",
        help="address to listen on (default: localhost:1212)",
    )
    p_recv.add_argument(
        "--out", default=None, metavar="FILE",
        help="output file (default: <in>.out)",
    )
    p_recv.add_argument("-v", "--verbose", action="store_true")
    p_recv.set_defaults(func=cmd_receiver)

    # ── sender ───────────────────────────────────────────────────────────────
    p_send = sub.add_parser(
        "sender",
        help="run as PSI sender — connects to the receiver",
    )
    p_send.add_argument("--in", dest="input", required=True, type=Path, metavar="FILE")
    p_send.add_argument(
        "--tls", action="store_true",
        help="enable TLS (requires certs/)",
    )
    p_send.add_argument(
        "--ip", default="localhost:1212", metavar="HOST:PORT",
        help="receiver's host:port to connect to (default: localhost:1212)",
    )
    p_send.add_argument("-v", "--verbose", action="store_true")
    p_send.set_defaults(func=cmd_sender)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
