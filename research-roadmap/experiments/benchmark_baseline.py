#!/usr/bin/env python3
"""
Baseline Performance Benchmark for IHearYou on Pi 5 (or VM proxy)

Measures:
1. Docker stack startup time
2. Feature extraction latency (via API simulation)
3. Memory usage under load
4. Concurrent stream handling

Usage:
    python benchmark_baseline.py [--streams N] [--duration SECONDS]
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Configuration
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
TEMPORAL_URL = os.getenv("TEMPORAL_URL", "http://localhost:8082")
ANALYSIS_URL = os.getenv("ANALYSIS_URL", "http://localhost:8083")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8084")


def run_command(cmd: str, capture: bool = True) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=capture, text=True
    )
    return result.returncode, result.stdout, result.stderr


def check_docker_running() -> bool:
    """Check if Docker containers are running."""
    code, out, _ = run_command("docker ps --format '{{.Names}}' | wc -l")
    return code == 0 and int(out.strip()) > 0


def get_container_stats() -> dict:
    """Get memory and CPU stats for all containers."""
    code, out, _ = run_command(
        "docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}'"
    )
    if code != 0:
        return {}

    stats = {}
    for line in out.strip().split("\n"):
        if not line:
            continue
        parts = line.split(",")
        if len(parts) >= 4:
            name = parts[0]
            stats[name] = {
                "cpu_percent": parts[1],
                "mem_usage": parts[2],
                "mem_percent": parts[3],
            }
    return stats


def measure_service_health() -> dict:
    """Check health of each service endpoint."""
    services = {
        "temporal_context": f"{TEMPORAL_URL}/health",
        "analysis": f"{ANALYSIS_URL}/health",
        "dashboard": f"{DASHBOARD_URL}",
    }

    results = {}
    for name, url in services.items():
        try:
            start = time.time()
            resp = requests.get(url, timeout=10)
            latency = (time.time() - start) * 1000
            results[name] = {
                "status": resp.status_code,
                "latency_ms": round(latency, 2),
                "healthy": resp.status_code == 200,
            }
        except requests.RequestException as e:
            results[name] = {
                "status": 0,
                "latency_ms": -1,
                "healthy": False,
                "error": str(e),
            }
    return results


def measure_mongodb_latency() -> dict:
    """Measure MongoDB query latency."""
    try:
        from pymongo import MongoClient

        client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)

        # Ping
        start = time.time()
        client.admin.command("ping")
        ping_ms = (time.time() - start) * 1000

        # Simple query
        db = client["iotsensing_live"]
        start = time.time()
        db.raw_metrics.find_one()
        query_ms = (time.time() - start) * 1000

        # Count documents
        start = time.time()
        count = db.raw_metrics.count_documents({})
        count_ms = (time.time() - start) * 1000

        client.close()

        return {
            "ping_ms": round(ping_ms, 2),
            "find_one_ms": round(query_ms, 2),
            "count_documents_ms": round(count_ms, 2),
            "document_count": count,
            "healthy": True,
        }
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def measure_memory_pressure(duration_seconds: int = 30) -> dict:
    """Monitor memory usage over time."""
    print(f"Monitoring memory for {duration_seconds} seconds...")
    samples = []

    for i in range(duration_seconds):
        stats = get_container_stats()
        total_mem_mb = 0

        for name, data in stats.items():
            # Parse "123.4MiB / 512MiB" format
            mem_str = data.get("mem_usage", "0MiB / 0MiB")
            try:
                used = mem_str.split("/")[0].strip()
                if "GiB" in used:
                    total_mem_mb += float(used.replace("GiB", "")) * 1024
                elif "MiB" in used:
                    total_mem_mb += float(used.replace("MiB", ""))
            except (ValueError, IndexError):
                pass

        samples.append(total_mem_mb)
        time.sleep(1)

        if (i + 1) % 10 == 0:
            print(f"  {i + 1}s: {total_mem_mb:.0f} MB total")

    return {
        "samples": samples,
        "min_mb": round(min(samples), 2),
        "max_mb": round(max(samples), 2),
        "avg_mb": round(sum(samples) / len(samples), 2),
        "duration_seconds": duration_seconds,
    }


def run_benchmark(args: argparse.Namespace) -> dict:
    """Run the complete benchmark suite."""
    results = {
        "timestamp": datetime.now().isoformat(),
        "hostname": os.uname().nodename,
        "args": vars(args),
    }

    print("=" * 60)
    print("IHearYou Baseline Benchmark")
    print("=" * 60)

    # 1. Check Docker
    print("\n[1/5] Checking Docker status...")
    if not check_docker_running():
        print("ERROR: Docker containers not running!")
        print("Start with: docker-compose -f docker-compose.yml -f docker-compose.pi5.yml up -d")
        sys.exit(1)

    results["docker_running"] = True
    print("  ✓ Docker containers running")

    # 2. Container stats
    print("\n[2/5] Collecting container stats...")
    results["container_stats"] = get_container_stats()
    for name, stats in results["container_stats"].items():
        print(f"  {name}: CPU={stats['cpu_percent']}, Mem={stats['mem_usage']}")

    # 3. Service health
    print("\n[3/5] Checking service health...")
    results["service_health"] = measure_service_health()
    for name, health in results["service_health"].items():
        status = "✓" if health["healthy"] else "✗"
        latency = f"{health['latency_ms']:.0f}ms" if health["latency_ms"] > 0 else "N/A"
        print(f"  {status} {name}: {latency}")

    # 4. MongoDB latency
    print("\n[4/5] Measuring MongoDB latency...")
    results["mongodb"] = measure_mongodb_latency()
    if results["mongodb"]["healthy"]:
        print(f"  Ping: {results['mongodb']['ping_ms']:.1f}ms")
        print(f"  Query: {results['mongodb']['find_one_ms']:.1f}ms")
        print(f"  Documents: {results['mongodb']['document_count']}")
    else:
        print(f"  ✗ MongoDB error: {results['mongodb'].get('error', 'Unknown')}")

    # 5. Memory monitoring
    print(f"\n[5/5] Monitoring memory ({args.duration}s)...")
    results["memory"] = measure_memory_pressure(args.duration)
    print(f"  Min: {results['memory']['min_mb']:.0f} MB")
    print(f"  Max: {results['memory']['max_mb']:.0f} MB")
    print(f"  Avg: {results['memory']['avg_mb']:.0f} MB")

    # Summary
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)

    total_mem = results["memory"]["avg_mb"]
    healthy_services = sum(1 for s in results["service_health"].values() if s["healthy"])
    total_services = len(results["service_health"])

    print(f"  Services healthy: {healthy_services}/{total_services}")
    print(f"  Average memory: {total_mem:.0f} MB")
    print(f"  MongoDB latency: {results['mongodb'].get('ping_ms', 'N/A')} ms")

    # Pi 5 feasibility assessment
    print("\n  Pi 5 Feasibility:")
    if total_mem < 4000:
        print(f"    ✓ Memory OK ({total_mem:.0f} MB < 4000 MB limit)")
    else:
        print(f"    ✗ Memory HIGH ({total_mem:.0f} MB > 4000 MB limit)")

    if healthy_services == total_services:
        print(f"    ✓ All services healthy")
    else:
        print(f"    ⚠ {total_services - healthy_services} services unhealthy")

    return results


def main():
    parser = argparse.ArgumentParser(description="IHearYou Baseline Benchmark")
    parser.add_argument(
        "--duration", type=int, default=30, help="Memory monitoring duration (seconds)"
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Output JSON file path"
    )
    args = parser.parse_args()

    results = run_benchmark(args)

    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(__file__).parent / "results" / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n  Results saved to: {output_path}")


if __name__ == "__main__":
    main()
