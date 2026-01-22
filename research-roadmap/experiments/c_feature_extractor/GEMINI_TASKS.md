# Gemini Tasks: Edge Computing Benchmarks

## Priority: HIGH - Required for Publication

The adversarial review identified that our edge contribution is underdeveloped. We need actual performance measurements.

---

## Task 1: Add Latency Benchmarking

**File**: `src/feature_extractor.c` or new `src/benchmark.c`

**Requirements**:
1. Add timing instrumentation to measure:
   - Per-frame processing latency (target: <10ms for real-time)
   - Total feature extraction time for a typical utterance (5-10 seconds)
   - Breakdown by feature: F0, energy, pause detection, NAQ, H1-H2

2. Use `clock_gettime(CLOCK_MONOTONIC)` for high-resolution timing

3. Output format:
```
Feature Extraction Benchmark (N=1000 frames)
============================================
F0 extraction:     2.3 ms/frame (avg)
Energy computation: 0.1 ms/frame (avg)
Pause detection:   0.5 ms/frame (avg)
Total per frame:   3.2 ms/frame (avg)
Real-time factor:  0.32x (can process 3x faster than real-time)
```

---

## Task 2: Add Memory Profiling

**Requirements**:
1. Report static memory usage:
   - Code size (.text section)
   - Initialized data (.data)
   - Uninitialized data (.bss)
   - Stack usage estimate

2. Report dynamic memory usage:
   - Peak heap allocation during processing
   - Per-frame buffer requirements

3. Target: <50KB total for ESP32 compatibility

**Command to get section sizes**:
```bash
size feature_extractor
```

---

## Task 3: ESP32 Resource Estimation

**Requirements**:
1. Estimate feasibility for ESP32-S3:
   - 512KB SRAM
   - 240 MHz dual-core
   - No FPU (or limited)

2. Identify bottlenecks:
   - Which operations need fixed-point conversion?
   - What's the minimum buffer size needed?

3. Create `ESP32_FEASIBILITY.md` report

---

## Task 4: Comparison Table vs eGeMAPS

Create a comparison showing efficiency advantage:

| Metric | Our C Implementation | openSMILE eGeMAPS |
|--------|---------------------|-------------------|
| Features extracted | 8 | 88 |
| Processing time/frame | ? ms | ? ms |
| Memory footprint | ? KB | ? MB |
| Dependencies | libm only | Many |
| Edge deployable | Yes | No |

---

## Deliverables

1. `benchmark.c` - Standalone benchmark utility
2. `BENCHMARK_RESULTS.md` - Results report
3. `ESP32_FEASIBILITY.md` - Edge deployment analysis
4. Updated `Makefile` with benchmark target

---

## Success Criteria

- [ ] Latency < 10ms per frame (real-time capable)
- [ ] Memory < 50KB (ESP32 compatible)
- [ ] Real-time factor < 1.0 (faster than real-time)
- [ ] Documented comparison vs eGeMAPS

---

*Created: 2026-01-22*
*Priority: HIGH - blocks publication*
