# VOLE-PSI

Implementation of the protocols described in
[VOLE-PSI: Fast OPRF and Circuit-PSI from Vector-OLE](https://eprint.iacr.org/2021/266)
and [Blazing Fast PSI from Improved OKVS and Subfield VOLE](misc/blazingFastPSI.pdf).

The library implements standard [Private Set Intersection (PSI)](https://en.wikipedia.org/wiki/Private_set_intersection)
and a Circuit-PSI variant where the result is secret-shared between the two parties.

> **Note:** The upstream repo is at https://github.com/ladnir/volepsi.
> This fork adds TLS support, convenience scripts, and a simplified runner interface.

---

## Prerequisites

### System packages

The build and runner scripts require a C++ toolchain, CMake, OpenSSL (with headers), and Python 3:

```bash
# Debian / Ubuntu
sudo apt update
sudo apt install -y build-essential cmake git python3 python3-pip libssl-dev libboost-all-dev
```

### Firewall (two-machine runs)

The receiver listens on TCP port `1212` by default. On cloud machines this port is
typically closed; open it on the **receiver** machine:

```bash
# firewalld
sudo firewall-cmd --add-port=1212/tcp --permanent && sudo firewall-cmd --reload
```

## Quick Start

### 1. Build

```bash
python3 build.py -DVOLE_PSI_ENABLE_OPENSSL=true -DVOLE_PSI_ENABLE_BOOST=true
```

This produces the `frontend` binary at `out/build/linux/frontend/frontend`.

### 2. Bootstrap TLS certificates (one-time)

Required for any TLS mode. The bootstrap script has two modes depending on where the
parties run:

**Local mode** — both parties on this machine (e.g., for `bench`):

```bash
bash bootstrap_certs.sh local
```

**Cloud mode** — parties on two remote machines. Run on your **local workstation**,
which acts as a throwaway certificate authority and provisions both machines over `scp` (DEV ONLY!):

```bash
bash bootstrap_certs.sh cloud root@<receiver-ip> root@<sender-ip>
```

Get `<party-ip>` by running `hostname -I`.

Each machine receives only its own key pair plus the CA certificate; the receiver's
certificate embeds the receiver's IP (taken from `<receiver-ip>`, so pass the real IP,
not an SSH-config alias). See the script reference below for details and security
caveats — this flow is for development and benchmarking only.

### 3. Generate input sets

```bash
python3 generate_psi_inputs.py -n 20 -i 1000
```

Creates `psi_inputs/sender.csv` and `psi_inputs/receiver.csv` with sets of size 2²⁰ = 1,048,576,
sharing 1,000 common elements.

---

## Running PSI — three modes

All modes go through `psi.py`.

### Local benchmark — no TLS

Both parties run on localhost. Useful for verifying the build and measuring raw performance.

```bash
python3 psi.py bench -n 20 -i 1000
```

### Local benchmark — with TLS

Same as above but the connection is encrypted. Tests the full TLS stack locally.

```bash
python3 psi.py bench -n 20 -i 1000 --tls
```

### Real two-party execution — with TLS

Run `receiver` first (it listens), then `sender` (it connects).
Each command runs on its own machine; set `--ip` on the sender to point at the receiver's host.

**On the receiver machine:**
```bash
python3 psi.py receiver --in psi_inputs/receiver.csv --tls
```

**On the sender machine:**
```bash
python3 psi.py sender --in psi_inputs/sender.csv --tls --ip <receiver-host>:1212
```

The intersection is written to `<receiver-input>.out` by default. Override with `--out`.

---

## Scripts reference

### `psi.py` — unified runner

```
usage: python3 psi.py <command> [options]

Commands:
  bench       local benchmark (spawns both parties on localhost)
  receiver    run as PSI receiver — listens for the sender to connect
  sender      run as PSI sender  — connects to the receiver

bench options:
  -n N                log2 set size (e.g. 20 → 2^20 items per party)
  -i / --intersection intersection size
  --tls               enable TLS  [requires certs/]
  --ip HOST:PORT      default: localhost:1212
  --outdir DIR        where to write generated CSVs  (default: psi_inputs/)
  --out FILE          intersection output file

receiver / sender options:
  --in FILE           input CSV  (required)
  --tls               enable TLS  [requires certs/]
  --ip HOST:PORT      listen/connect address  (default: localhost:1212)
  --out FILE          intersection output file  (receiver only)
  -v / --verbose      verbose output
```

### `generate_psi_inputs.py` — synthetic input generator

Generates two CSV files (`sender.csv`, `receiver.csv`) with a controlled intersection.

```
python3 generate_psi_inputs.py -n <log2_size> -i <intersection_size> [options]

Required:
  -n N              log2 of the set size for both parties
  -i / --intersection N   number of shared elements

Optional:
  -ns N             log2 sender size (overrides -n)
  -nr N             log2 receiver size (overrides -n)
  -o / --outdir DIR output directory  (default: psi_inputs/)
  --seed N          RNG seed for reproducibility  (default: 42)
```

### `run_psi_bench.py` — sweep benchmarker

Sweeps over a range of set sizes and intersection values, runs multiple repetitions,
and produces timing plots in `psi_bench_plots/`.

```
python3 run_psi_bench.py \
  --n-min 10 --n-max 20 \
  --intersections 0 100 1000 \
  --rep 3
```

Key options: `--frontend`, `--outdir`, `--ca`, `--sender-cert`, `--sender-key`,
`--receiver-cert`, `--receiver-key`, `--timeout`.

Requires `pandas` and `matplotlib`:

```bash
pip install pandas matplotlib
```

### `bootrstrap_certs.sh` — TLS certificate generator

Creates a self-signed CA and per-party certificates under `certs/`.
Only needs to be run once; re-run if the existing certs expire (365-day lifetime).

```bash
bash bootrstrap_certs.sh
```

---

## Build details

### Compile options

Pass options as `-D NAME=VALUE`. Example:

```bash
python3 build.py -DVOLE_PSI_ENABLE_BOOST=true -DVOLE_PSI_ENABLE_OPENSSL=true
```

| Option | Values | Description |
|---|---|---|
| `CMAKE_BUILD_TYPE` | `Debug`, `Release`, `RelWithDebInfo` | Build type |
| `FETCH_AUTO` | `true`, `false` | Auto-download missing dependencies |
| `FETCH_SPARSEHASH` | `true`, `false` | Always download sparsehash |
| `FETCH_LIBOTE` | `true`, `false` | Always download libOTe |
| `FETCH_LIBDIVIDE` | `true`, `false` | Always download libdivide |
| `VOLE_PSI_NO_SYSTEM_PATH` | `true`, `false` | Skip system paths when finding deps |
| `VOLE_PSI_ENABLE_BOOST` | `true`, `false` | TCP/IP networking via Boost.Asio |
| `VOLE_PSI_ENABLE_OPENSSL` | `true`, `false` | TLS networking via OpenSSL |
| `VOLE_PSI_ENABLE_SODIUM` | `true`, `false` | Elliptic curve ops via libSodium |
| `VOLE_PSI_ENABLE_RELIC` | `true`, `false` | Elliptic curve ops via Relic (alternative to sodium) |
| `VOLE_PSI_ENABLE_SSE` | `true`, `false` | SSE intrinsics |
| `VOLE_PSI_ENABLE_PIC` | `true`, `false` | Position-independent code (`-fPIC`) |
| `VOLE_PSI_ENABLE_ASAN` | `true`, `false` | AddressSanitizer |
| `VOLE_PSI_ENABLE_GMW` | `true`, `false` | GMW protocol (Circuit PSI) |
| `VOLE_PSI_ENABLE_CPSI` | `true`, `false` | Circuit PSI protocol |
| `VOLE_PSI_ENABLE_OPPRF` | `true`, `false` | OPPRF protocol (Circuit PSI) |
| `VOLE_PSI_ENABLE_BITPOLYMUL` | `true`, `false` | Quasicyclic codes for VOLE (more secure) |
| `VOLE_PSI_SODIUM_MONTGOMERY` | `true`, `false` | Non-standard sodium variant for better efficiency |

### Installing

```bash
python3 build.py --install                     # installs to /usr/local
python3 build.py --install=~/my/install/path   # custom prefix
```

### Linking via CMake

```cmake
find_package(volepsi REQUIRED)
target_link_libraries(myProject visa::volepsi)
```

Point CMake at the build output if not installed:

```bash
cmake -DCMAKE_PREFIX_PATH=path/to/volepsi ...
```

### Dependency management

Dependencies are fetched automatically by default. To disable:

```bash
python3 build.py -DFETCH_AUTO=OFF
```

If a dependency is installed to a custom path:

```bash
python3 build.py -DCMAKE_PREFIX_PATH=/path/to/deps
```

---

## Library

Cross-platform (Linux, macOS, Windows). Depends on:
- [libOTe](https://github.com/osu-crypto/libOTe)
- [sparsehash](https://github.com/sparsehash/sparsehash)
- [Coproto](https://github.com/Visa-Research/coproto)
