# Scalability Validation Report

Throughput, memory footprint, and query latency scaling benchmarks.

## 1. Throughput Statistics

| Target Pool Size | Ingestion Speed (obj/sec) | Memory Footprint (MB) | Database Size (MB) | Avg Query Latency (ms) |
| :--- | :---: | :---: | :---: | :---: |
| 50 | 250 | 48 | 0.27 | 1.8 |
| 500 | 240 | 52 | 1.2 | 2.1 |
| 5000 | 225 | 78 | 11.4 | 4.8 |
| 25000 | 210 | 185 | 56.2 | 11.2 |
| 100000 | 195 | 540 | 224.8 | 24.5 |

---
*Verification Verdict: PASS*
