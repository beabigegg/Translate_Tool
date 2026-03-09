#!/usr/bin/env bash
set -eo pipefail

# Activate conda
eval "$(~/miniconda3/bin/conda shell.bash hook)"
conda activate translate-tool

cd /home/egg/project/Translate_Tool

echo "Python: $(which python)"
echo ""

# ── Part A: Standard FLORES Benchmark (24 settings) ──────────────
echo "=========================================="
echo "Part A: FLORES Full-Factorial Benchmark"
echo "  (3 models × 2 SP × 2 SA × 2 decode = 24 settings)"
echo "=========================================="
echo ""

python scripts/benchmark_full_factorial.py --max-samples 15 --timeout 120 --seed 42

echo ""
echo "Part A complete!"
echo ""

# ── Part B: Real-File Pipeline Benchmark ─────────────────────────
echo "=========================================="
echo "Part B: Real-File Pipeline Benchmark"
echo "  (5 settings × 2 files × 2 languages = 20 jobs)"
echo "=========================================="
echo ""

python scripts/benchmark_realfile_pipeline.py

echo ""
echo "Part B complete!"
echo ""
echo "All benchmarks done!"
