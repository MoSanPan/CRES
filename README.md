# CRES: Cached Residual Estimation with Shrinkage

Research code and reference measurements for **Beyond Count-Min: Shrinkage for Frequency Estimation in Data Streams**. CRES stores exact counts for the first distinct keys up to its cache capacity. For all other keys, it debiases a residual Count-Min Sketch estimate and shrinks it toward the residual mean.

## Reproduce the paper's reported averages

From the repository root, run:

```sh
python run.py verify-files
python run.py summarize
```

This uses Python 3.10+ and the bundled reference runs. It writes `reports/reference_means.json`. No compiler, extra Python packages, or data download is needed for this command.

| Core comparator | Mean full-universe MSE reduction by CRES |
| --- | ---: |
| Projected CountSketch row mean | 96.65% |
| Shrink-CS | 4.63% |
| Constant estimator | 6.39% |

The core benchmark uses 12 configurations across ANU, IBM Belem and IBM Quito. The script averages MSE over repetitions within each configuration, computes the relative reduction, then gives each configuration equal weight. For the stream-block study it also reports CRES-to-CMM-mean MSE ratios and the sensitivity calculation for the fourth 32-bit Belem block.

## Run the implementation

```sh
python -m pip install -r requirements.txt
python run.py check --cxx g++
```

The check builds all three C++17 executables, compares selected 16-bit and 32-bit runs with the archived results, and checks the throughput implementation. GCC, Clang and Zig driver options are supported; for Zig, use `--cxx zig` or the path to the executable.

| What to inspect | Location |
| --- | --- |
| Core estimator, baselines and evaluator | [C++ source](core/experiments/src/experiment.cpp) and [core configurations](core/experiments/config/cases.json) |
| Stream blocks, scaling, memory allocation and source models | [Extension evaluator](extension/src/experiment_extension.cpp) and [experiment runner](extension/run_extension.py) |
| Update and query throughput | [Benchmark](throughput/benchmark.cpp) and [timing records](reference_results/throughput/timings.csv) |
| Reference accuracy results | [Core runs](core/results/reference/) and [extension measurements](reference_results/extension/) |
| Input sources, encodings and attribution | [Data sources](DATA_SOURCES.md) |

See [Reproducing the experiments](docs/REPRODUCTION.md) for full benchmark commands, algorithm identifiers and output paths.
