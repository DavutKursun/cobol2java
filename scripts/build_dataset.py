"""Turn the verified program folders into train/test JSONL files (and optionally a Hugging Face dataset).

Each row has:
  id, cobol, java, explanation, tests      -> raw fields (used by evaluation)
  prompt, completion                        -> conversational format for TRL's SFTTrainer
                                               (loss is computed on the completion only)

The split is deterministic (hash of the folder name), so re-running after adding
new programs never moves an old test program into the training set.

Usage:
    python scripts/build_dataset.py
    python scripts/build_dataset.py --reverify
    python scripts/build_dataset.py --push-to-hub DavutKursun/cobol-java-verified
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from prompts import SYSTEM_PROMPT, assistant_message, user_message  # noqa: E402
from verify import check_pair, load_program_dir  # noqa: E402


def is_test(name: str, test_fraction: float) -> bool:
    bucket = int(hashlib.sha256(name.encode()).hexdigest(), 16) % 1000
    return bucket < test_fraction * 1000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--programs", type=Path, default=Path("data/programs"))
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument("--test-fraction", type=float, default=0.15)
    parser.add_argument("--reverify", action="store_true", help="re-run the COBOL/Java check before exporting")
    parser.add_argument("--push-to-hub", metavar="REPO_ID", help="also upload as a Hugging Face dataset")
    args = parser.parse_args()

    rows = {"train": [], "test": []}
    skipped = 0
    for d in sorted(p for p in args.programs.iterdir() if (p / "program.cbl").exists()):
        cobol, java, tests = load_program_dir(d)
        explanation = (d / "explanation.md").read_text().strip() if (d / "explanation.md").exists() else ""
        if args.reverify and not check_pair(d.name, cobol, java, tests).ok:
            print(f"skipping {d.name}: does not verify")
            skipped += 1
            continue
        row = {
            "id": d.name,
            "cobol": cobol,
            "java": java,
            "explanation": explanation,
            "tests": tests,
            "prompt": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message(cobol)},
            ],
            "completion": [{"role": "assistant", "content": assistant_message(explanation, java)}],
        }
        rows["test" if is_test(d.name, args.test_fraction) else "train"].append(row)

    args.out.mkdir(parents=True, exist_ok=True)
    for split, items in rows.items():
        path = args.out / f"{split}.jsonl"
        with path.open("w") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"{split}: {len(items)} rows -> {path}")
    if skipped:
        print(f"skipped {skipped} folders that did not verify")

    if args.push_to_hub:
        from datasets import load_dataset

        ds = load_dataset("json", data_files={s: str(args.out / f"{s}.jsonl") for s in rows})
        ds.push_to_hub(args.push_to_hub)
        print(f"pushed to https://huggingface.co/datasets/{args.push_to_hub}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
