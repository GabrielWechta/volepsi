#!/usr/bin/env python3
import argparse
import random
from pathlib import Path
import math

def write_csv(path: Path, values):
    with path.open("w", buffering=1024 * 1024) as f:
        for v in values:
            f.write(f"{v}\n")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("-n", type=int, required=True,
                   help="default log2 input size for both parties")
    p.add_argument("-ns", type=int, default=None,
                   help="log2 sender input size; defaults to -n")
    p.add_argument("-nr", type=int, default=None,
                   help="log2 receiver input size; defaults to -n")
    p.add_argument("-i", "--intersection", type=int, required=True,
                   help="intersection size")
    p.add_argument("-o", "--outdir", default="psi_inputs")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    sender_n = args.ns if args.ns is not None else args.n
    receiver_n = args.nr if args.nr is not None else args.n

    sender_size = 1 << sender_n
    receiver_size = 1 << receiver_n

    if args.intersection > min(sender_size, receiver_size):
        raise ValueError("intersection cannot exceed min(sender size, receiver size)")

    random.seed(args.seed)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # minimal hex width based on max n
    max_n = max(sender_n, receiver_n)
    width = max(1, math.ceil(max_n / 4))

    common = [f"common_{x:0{width}x}" for x in range(args.intersection)]

    sender_only = [
        f"sender_{x:0{width}x}"
        for x in range(sender_size - args.intersection)
    ]

    receiver_only = [
        f"receiver_{x:0{width}x}"
        for x in range(receiver_size - args.intersection)
    ]

    sender = common + sender_only
    receiver = common + receiver_only

    random.shuffle(sender)
    random.shuffle(receiver)

    sender_path = outdir / "sender.csv"
    receiver_path = outdir / "receiver.csv"

    write_csv(sender_path, sender)
    write_csv(receiver_path, receiver)

    print(sender_path)
    print(receiver_path)

if __name__ == "__main__":
    main()
