llama-bench output transcribed from the terminal on 2026-09-24 (`-p 512 -n 128`, mean ± sd over the stated repetitions).
Qwen3 1.7B Q4_K_M (sha256 prefix 24bad75bf5bb4807, same file on all three nodes); TinyLlama 1.1B Chat Q8_0 (sha256 prefix a4c9bb1dbaa372f6).

| Node | Backend / setup | Build | Model | pp512 t/s | tg128 t/s | reps |
|---|---|---|---|---|---|---|
| 2 Orin NX 16GB | CUDA -ngl 99, MAXN_SUPER | 7044859 | Qwen3-1.7B Q4_K_M | 1748.54 ± 48.76 | 43.82 ± 0.06 | 5 |
| 2 Orin NX 16GB | CUDA, node 3's binaries (control) | 749f688 | Qwen3-1.7B Q4_K_M | 1751.04 ± 45.17 | 43.45 ± 0.04 | 5 |
| 3 Orin Nano 8GB | CUDA -ngl 99, MAXN_SUPER | 749f688 | Qwen3-1.7B Q4_K_M | 1559.37 ± 42.87 | 39.44 ± 0.09 | 5 |
| 1 RK1 | CPU, 8 threads | 704485942 | Qwen3-1.7B Q4_K_M | 51.98 ± 0.07 | 15.53 ± 0.03 | 3 |
| 1 RK1 | CPU, 4 big cores (taskset 4-7) | 704485942 | Qwen3-1.7B Q4_K_M | 47.69 ± 0.02 | 19.67 ± 0.01 | 3 |
| 1 RK1 | CPU, 4 big cores | 704485942 | TinyLlama-1.1B Q8_0 | 114.34 ± 0.15 | 22.15 ± 0.01 | 3 |
| 1 RK1 | CPU, 8 threads | 704485942 | TinyLlama-1.1B Q8_0 | 116.12 ± 2.46 | 18.23 ± 0.13 | 3 |
