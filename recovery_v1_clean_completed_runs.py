"""Remove stale interruption errors from successfully resumed runs."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("names", nargs="+")
    args = parser.parse_args()
    for name in args.names:
        path = args.root / "runs" / name / "run_config.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") != "complete":
            raise ValueError(name)
        data["error"] = None
        data["eligible_for_controlled_comparison"] = True
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(name)


if __name__ == "__main__":
    main()
