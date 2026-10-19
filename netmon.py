"""Current reachability only. Run with Python 3.11+ on Windows; no packages needed."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_config(path):
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("configuration must be a JSON object")
    interval = config.get("interval_seconds", 5)
    timeout = config.get("timeout_ms", 1000)
    if type(interval) not in (int, float) or not math.isfinite(interval) or not 1 <= interval <= 300:
        raise ValueError("interval_seconds must be between 1 and 300")
    if type(timeout) is not int or not 100 <= timeout <= 10000:
        raise ValueError("timeout_ms must be an integer between 100 and 10000")
    devices = config.get("devices")
    if not isinstance(devices, list) or not 1 <= len(devices) <= 64:
        raise ValueError("devices must contain 1 to 64 entries")
    names, addresses = set(), set()
    for device in devices:
        if not isinstance(device, dict) or not isinstance(device.get("address"), str):
            raise ValueError("each device needs a name and an IPv4 address string")
        name = device["name"]
        if not isinstance(name, str) or not name.strip() or len(name) > 100 or any(ord(c) < 32 for c in name):
            raise ValueError("device names must be printable, nonempty, and at most 100 characters")
        address = str(ipaddress.IPv4Address(device["address"]))
        if ipaddress.IPv4Address(address).is_multicast or address == "0.0.0.0" or address == "255.255.255.255":
            raise ValueError("use a unicast IPv4 address")
        if name in names or address in addresses:
            raise ValueError("device names and addresses must be unique")
        names.add(name)
        addresses.add(address)
        device["address"] = address
    return interval, timeout, devices


def probe(device, timeout_ms):
    """TTL identifies an echo reply, avoiding ping's misleading unreachable exit code."""
    result = dict(device, status="error", latency_ms=None, checked_at=utc_now())
    try:
        reply = subprocess.run(
            [str(Path(os.environ["SystemRoot"]) / "System32" / "PING.EXE"),
             "-4", "-n", "1", "-w", str(timeout_ms), device["address"]],
            capture_output=True, text=True, errors="replace", timeout=timeout_ms / 1000 + 2,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if re.search(r"\bTTL=\d+", reply.stdout, re.IGNORECASE):
            result["status"] = "up"
            latency = re.search(r"(?:time|temps|zeit|tiempo)[=<]\s*(\d+)\s*ms", reply.stdout, re.IGNORECASE)
            if latency:
                result["latency_ms"] = int(latency.group(1))
        elif re.search(r"request timed out|destination .* unreachable", reply.stdout, re.IGNORECASE):
            result["status"] = "down"
        else:
            result["error"] = "No recognized echo result (English Windows required for failure parsing)"
    except (OSError, subprocess.TimeoutExpired) as error:
        result["error"] = type(error).__name__
    result["checked_at"] = utc_now()
    return result


def collect(devices, timeout_ms, previous, executor):
    results = list(executor.map(lambda device: probe(device, timeout_ms), devices))
    for result in results:
        old = previous.get(result["address"], {})
        result["last_success_at"] = result["checked_at"] if result["status"] == "up" else old.get("last_success_at")
    return results


def publish(path, document):
    # The browser sees either the previous complete file or the new complete file.
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("devices.example.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "published" / "status.json")
    parser.add_argument("--once", action="store_true", help="Collect one round and exit")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("This collector uses Windows ping.exe")
    try:
        interval, timeout, devices = load_config(args.config)
        previous = {}
        with ThreadPoolExecutor(max_workers=min(16, len(devices))) as executor:
            while True:
                started = time.monotonic()
                results = collect(devices, timeout, previous, executor)
                document = {"updated_at": utc_now(), "stale_after_seconds": max(15, interval * 3 + math.ceil(len(devices) / 16) * (timeout / 1000 + 2)), "devices": results}
                publish(args.output, document)
                print(document["updated_at"], flush=True)
                for row in results:
                    print(f"  {row['name']:<25} {row['address']:<15} {row['status']:<5} RTT={row['latency_ms']} ms", flush=True)
                previous = {row["address"]: row for row in results}
                if args.once:
                    break
                time.sleep(max(0, interval - (time.monotonic() - started)))
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"NetMon: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
