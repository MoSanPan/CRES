"""Run a CRES artifact tool from the repository root."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SCRIPTS = {
    "verify-files": "scripts/verify_files.py",
    "summarize": "scripts/summarize_reference.py",
    "check": "scripts/smoke_check.py",
    "prepare": "core/experiments/scripts/rebuild_data.py",
    "core": "core/experiments/scripts/run_experiments.py",
    "verify-core": "core/experiments/scripts/verify_reproduction.py",
    "summarize-core": "core/experiments/scripts/summarize.py",
    "extension": "extension/run_extension.py",
    "throughput": "throughput/run_benchmark.py",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog="Use COMMAND --help for tool-specific options.")
    parser.add_argument("command", choices=SCRIPTS)
    parser.add_argument("options", nargs=argparse.REMAINDER, help="Arguments passed to the selected tool")
    args = parser.parse_args()
    return subprocess.call([sys.executable, ROOT / SCRIPTS[args.command], *args.options], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
