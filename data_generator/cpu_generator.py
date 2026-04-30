#!/usr/bin/env python3
"""
cpu_generator.py
================
Generates synthetic CPU-load metrics and sends them to Telegraf
via HTTP InfluxDB line-protocol.

Usage:
    python cpu_generator.py [options]

Options:
    --url       URL of Telegraf HTTP listener  (default: http://localhost:8186/telegraf)
    --interval  Seconds between batches        (default: 5)
    --runs      Number of batches to send, 0 = infinite  (default: 0)
    --hosts     Comma-separated host names     (default: web-01,web-02,db-01,cache-01)
    --cores     CPU cores per host             (default: 8)
    --max-mb    Stop after N MB sent, 0 = no limit       (default: 0)

Examples:
    # Run forever, one batch every 5 seconds
    python cpu_generator.py

    # Fast burst: 200 batches every second
    python cpu_generator.py --interval 1 --runs 200

    # Custom hosts and target
    python cpu_generator.py --hosts srv-01,srv-02 --cores 4 --interval 2

    # Cap at 50 MB of data
    python cpu_generator.py --max-mb 50
"""

import argparse
import math
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Synthetic CPU metrics → Telegraf (InfluxDB line protocol)"
    )
    p.add_argument("--url",      default="http://localhost:8186/telegraf",
                   help="Telegraf HTTP listener URL")
    p.add_argument("--interval", type=float, default=5.0,
                   help="Seconds between batches (default: 5)")
    p.add_argument("--runs",     type=int,   default=0,
                   help="Batches to send; 0 = infinite (default: 0)")
    p.add_argument("--hosts",    default="web-01,web-02,db-01,cache-01",
                   help="Comma-separated host names")
    p.add_argument("--cores",    type=int,   default=8,
                   help="CPU cores per host (default: 8)")
    p.add_argument("--max-mb",   type=float, default=0.0,
                   help="Stop after N MB sent; 0 = no limit (default: 0)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------
def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def sine_base(t: float, period: float) -> float:
    """Slow sine wave so the CPU graph looks realistic, not pure noise."""
    return 50.0 + 30.0 * math.sin(2 * math.pi * t / period)


def make_batch(hosts: list[str], num_cores: int, t_elapsed: float) -> str:
    """Return a multi-line InfluxDB line-protocol payload."""
    lines: list[str] = []
    ts_ns = time.time_ns()

    for host in hosts:
        period = random.uniform(90, 180)          # each host drifts differently
        base   = clamp(sine_base(t_elapsed, period) + random.gauss(0, 8))

        for core in range(num_cores):
            usage  = clamp(base + random.gauss(0, 5))
            user   = clamp(usage * random.uniform(0.50, 0.80))
            system = clamp(usage * random.uniform(0.05, 0.20))
            iowait = clamp(usage * random.uniform(0.00, 0.10))
            idle   = clamp(100.0 - usage)

            lines.append(
                f"cpu_load,"
                f"host={host},"
                f"core=cpu{core} "
                f"usage_percent={usage:.2f},"
                f"user={user:.2f},"
                f"system={system:.2f},"
                f"iowait={iowait:.2f},"
                f"idle={idle:.2f} "
                f"{ts_ns}"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTTP transport
# ---------------------------------------------------------------------------
def send(url: str, payload: str) -> bool:
    data = payload.encode("utf-8")
    req  = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 204
    except urllib.error.URLError as exc:
        print(f"  [WARN] send failed — {exc}", flush=True)
        return False


def wait_for_telegraf(url: str, retries: int = 20, delay: float = 3.0) -> None:
    print(f"Waiting for Telegraf at {url} ...", flush=True)
    probe = b"_health,check=startup value=1"
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(
            url, data=probe, method="POST",
            headers={"Content-Type": "text/plain"},
        )
        try:
            urllib.request.urlopen(req, timeout=3)
            print("Telegraf is ready ✓\n", flush=True)
            return
        except Exception:
            print(f"  attempt {attempt}/{retries} — not ready yet", flush=True)
            time.sleep(delay)
    print("ERROR: Telegraf did not become ready. Is the stack running?", flush=True)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    args  = parse_args()
    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
    max_bytes = int(args.max_mb * 1024 * 1024) if args.max_mb > 0 else 0
    infinite  = args.runs == 0

    print("=" * 60)
    print("  CPU Load Generator")
    print("=" * 60)
    print(f"  target   : {args.url}")
    print(f"  hosts    : {hosts}")
    print(f"  cores    : {args.cores} per host")
    print(f"  interval : {args.interval}s")
    print(f"  runs     : {'∞' if infinite else args.runs}")
    print(f"  max data : {'no limit' if not max_bytes else f'{args.max_mb} MB'}")
    print("=" * 60)

    wait_for_telegraf(args.url)

    total_bytes = 0
    batch_num   = 0
    t0          = time.monotonic()

    try:
        while True:
            if not infinite and batch_num >= args.runs:
                break
            if max_bytes and total_bytes >= max_bytes:
                print(f"\nReached {total_bytes / 1_048_576:.1f} MB limit after "
                      f"{batch_num} batches. Done.")
                break

            payload = make_batch(hosts, args.cores, time.monotonic() - t0)
            size    = len(payload.encode("utf-8"))
            ok      = send(args.url, payload)

            if ok:
                total_bytes += size
                batch_num   += 1
                ts  = datetime.now(timezone.utc).strftime("%H:%M:%S")
                mb  = total_bytes / 1_048_576
                print(
                    f"[{ts}] batch #{batch_num:>5}  "
                    f"+{size:>5} B   "
                    f"total={mb:7.3f} MB",
                    flush=True,
                )

            time.sleep(args.interval)

    except KeyboardInterrupt:
        mb = total_bytes / 1_048_576
        print(f"\nInterrupted after {batch_num} batches / {mb:.3f} MB sent.")

    print("Generator finished.")


if __name__ == "__main__":
    main()