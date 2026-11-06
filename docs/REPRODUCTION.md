# Reproducing the experiments

Run commands from the repository root. Summarizing the archived results only requires Python 3.10+. For experiment reruns install NumPy with `python -m pip install -r requirements.txt` and use a C++17 compiler. The examples use `g++`; substitute `clang++`, `zig`, or the path to the executable as appropriate. Use `python run.py --help` for the command list and `python run.py core --help` for a command's options.

## Core accuracy

The public benchmark crosses three streams, two key widths (16 and 32 bits), and two memory payloads (10 and 40 KiB). Each full run uses 20 hash/query repetitions. To reproduce and check one short run:

```sh
python run.py core --cxx g++ --case ANU_public_prefix_32_1280 --reps 1 --jobs 1 --out results/smoke
python run.py verify-core --results results/smoke
```

For all 12 public configurations:

```sh
python run.py core --cxx g++ --case public --jobs 2
python run.py verify-core
```

Core output paths above are relative to `core/`. The bundled inputs are ready to use; `python run.py prepare` reconstructs them. The runner also supports four model controls. If using the original full-run summary, run `--case all` before `python run.py summarize-core --results results/reproduced`.

## Extension studies

The 168 configurations cover `public_blocks`, `scale_budget`, `allocation`, `source_dependence`, and `source_entropy`. Run one case or the full set:

```sh
python run.py extension --cxx g++ --group public_blocks --limit 1 --jobs 1
python run.py extension --cxx g++ --group all --jobs 2
```

`python run.py extension --prepare` regenerates the prepared inputs. New per-case results go to `extension/results/`; partial run summaries report missing cases. Archived results stay in `reference_results/extension/`.

## Throughput

```sh
python run.py throughput --compiler g++
python run.py throughput --compiler g++ --skip-build --run
```

The first command builds and runs correctness checks. The second times 1,048,576 updates and 262,144 queries per workload, with one warm-up and five measured rounds. Run it separately from accuracy jobs. The paper reports the arithmetic mean of each round's operations per second. A different compiler or host can produce different timings.

## Reading the outputs

| CSV algorithm | Paper name |
| --- | --- |
| `proposed_projected` | CRES |
| `proposed_affine` | CRES before projection |
| `CS_mean_plus` | Projected CountSketch row mean |
| `CS_shrink` / `CMS_shrink` | Shrink-CS / shrink-CMS |
| `dictionary_CMS_raw` | Cached residual CMS with projection and no shrinkage |
| `CMM_mean` | CMM-mean |

`python run.py summarize` reads the bundled core CSVs, `reference_results/extension/all_results.csv` and `reference_results/throughput/timings.csv`. It does not rerun the estimators. Use `--out DIRECTORY` to select the report directory. In the JSON, `core` and `stream_blocks` contain mean relative reductions, `cmm_workloads` contains the block comparison reported in the paper, and `throughput` contains mean rates in millions of operations per second. A zero baseline MSE makes a relative reduction undefined (`null`). The full block comparison includes every block. The sensitivity calculation alone omits the fourth 32-bit Belem block at both budgets.
