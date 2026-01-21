# VM as Raspberry Pi 5 Development Environment

This document describes using the current VM as a proxy for Raspberry Pi 5 development and benchmarking.

## Hardware Comparison

| Spec | This VM | Raspberry Pi 5 | Notes |
|------|---------|----------------|-------|
| **CPU** | Intel Xeon W-1290 @ 3.2GHz | ARM Cortex-A76 @ 2.4GHz | VM faster per-core |
| **Cores** | 4 vCPU (2 core × 2 thread) | 4 physical cores | Similar parallelism |
| **RAM** | 3.7GB | 8GB (typical) | VM more constrained |
| **Architecture** | x86_64 | ARM64 | Different ISA |
| **Storage** | 489GB HDD/SSD | NVMe/SD variable | VM has more |
| **OS** | Ubuntu 22.04 | Raspberry Pi OS | Both Debian-based |

## Why This VM Works as a Proxy

1. **Memory Constraint (3.7GB):** Actually useful - simulates real Pi 5 available memory after OS overhead
2. **4 CPU cores:** Matches Pi 5 core count for parallelism testing
3. **Docker support:** Same containerization as target deployment
4. **Development convenience:** Easier debugging, faster iteration than actual Pi 5

## What This VM CANNOT Test

1. **ARM64 performance:** x86 ≠ ARM; actual Pi 5 benchmarks will differ
2. **GPIO/Hardware interfaces:** No physical ReSpeaker connection
3. **Power consumption:** Not measurable on VM
4. **Thermal throttling:** Pi 5 may throttle under sustained load

## Recommended Approach

| Phase | Use VM For | Use Actual Pi 5 For |
|-------|------------|---------------------|
| Development | Code changes, debugging | - |
| Unit tests | All tests | - |
| Integration | Docker stack validation | - |
| Benchmarking | Initial latency estimates | Final performance numbers |
| Optimization | Algorithm tuning | ARM-specific optimizations |
| Deployment | - | Production testing |

## Current VM Configuration

```
Hostname: depression-detection VM
IP: (internal)
User: rodrigues
Working Directory: /home/rodrigues/depression-detection

Docker Services:
- mqtt (Mosquitto) - port 1883
- mongodb - port 27017
- mongo-express - port 8081
- voice_profiling - port 8000
- voice_metrics - 2GB memory limit
- respeaker_service - port 8010, 512MB limit
- quality_metrics_service - 256MB limit
- temporal_context_modeling_layer - port 8082
- analysis_layer - port 8083, 1GB limit
- dashboard_layer - port 8084

Total Memory Limits: ~4GB (exceeds VM RAM - may need adjustment)
```

## Memory Optimization for VM

Current Docker memory limits total ~4GB, but VM only has 3.7GB. Recommended adjustments:

```yaml
# Reduced limits for VM testing
voice_metrics: 1.5G → 1G
analysis_layer: 1G → 512M
respeaker_service: 512M → 256M
quality_metrics_service: 256M → 128M
# Total: ~2GB (safe for 3.7GB VM)
```

## Benchmarking on VM

Results from VM benchmarks should be interpreted with these scaling factors (estimated):

| Metric | VM → Pi 5 Scaling | Rationale |
|--------|-------------------|-----------|
| CPU-bound tasks | ×1.3-1.5 slower on Pi 5 | ARM vs x86, clock speed |
| Memory-bound tasks | Similar | Both DDR4 |
| I/O-bound tasks | Similar or faster on Pi 5 | NVMe vs VM disk |
| Model inference | ×1.5-2.0 slower on Pi 5 | No SIMD optimization |

## Getting Started

```bash
# Start the Docker stack
cd /home/rodrigues/depression-detection
docker-compose up -d

# Check memory usage
docker stats --no-stream

# Run baseline benchmark
cd research-roadmap/experiments
python benchmark_baseline.py
```

## Connection to Actual Hardware

When ready to test with real hardware:

1. **ReSpeaker boards:** Connect to VM's network, point to VM IP:8010
2. **XVF3800 boards:** Same network configuration
3. **Pi 5 deployment:** Copy Docker stack, rebuild for ARM64

## Files Related to VM Setup

- `docker-compose.yml` - Main service definitions
- `docker-compose.vm.yml` - (To create) VM-optimized memory limits
- `research-roadmap/experiments/benchmark_baseline.py` - (To create) Benchmarking script
