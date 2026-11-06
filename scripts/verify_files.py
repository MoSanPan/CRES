"""Check the bundled files against PACKAGE_SHA256.json."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    expected = json.loads((ROOT / "PACKAGE_SHA256.json").read_text(encoding="utf-8"))
    failed = []
    for name, digest in expected.items():
        path = ROOT / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            failed.append(name)
    if failed:
        raise SystemExit("Missing or changed files:\n" + "\n".join(failed))
    print(f"Verified {len(expected)} files.")


if __name__ == "__main__":
    main()
