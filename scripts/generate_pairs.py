"""Generate new verified COBOL -> Java training pairs with a large "teacher" LLM.

For every new sample the teacher writes a small COBOL program, test inputs, an explanation
and a Java translation. The pair is kept ONLY if the COBOL compiles with GnuCOBOL and the
Java program prints exactly the same output on every test input. When the COBOL does not
compile or the Java output differs, the teacher gets the errors and up to --repairs chances to fix them.

Works with any OpenAI-compatible API. Default: Hugging Face Inference Providers
(set HF_TOKEN). Check the terms of the model/provider you use allow training on its outputs;
open-weight models like Qwen are the safest choice.

Usage:
    export HF_TOKEN=hf_...
    python scripts/generate_pairs.py --count 50
    python scripts/generate_pairs.py --count 50 --model Qwen/Qwen2.5-Coder-32B-Instruct  # cheaper, weaker COBOL
    # another provider:
    python scripts/generate_pairs.py --base-url https://api.openai.com/v1 --api-key-env OPENAI_API_KEY --model gpt-4.1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from verify import check_pair, load_program_dir  # noqa: E402

TOPICS = [
    "bank account interest with compounding per year",
    "loan installment (annuity) payment schedule for a few months",
    "insurance premium calculation by age band and risk class",
    "pension contribution: employee and employer shares of a salary",
    "social security day counting: total paid days from several periods",
    "payroll with overtime, bonus and tax brackets",
    "inventory: stock levels after a list of in/out movements",
    "invoice totals with VAT and a discount rule",
    "currency conversion table with fixed rates",
    "grade statistics: min, max, average and letter grades",
    "string processing: counting words and characters in a line",
    "string processing: building initials and formatted names with STRING",
    "parsing comma-separated fields with UNSTRING",
    "array (OCCURS table) search for a code and its description",
    "sorting a small OCCURS table with a bubble sort",
    "date arithmetic with FUNCTION INTEGER-OF-DATE and DATE-OF-INTEGER",
    "leap year and days-in-month checks",
    "validation of an ID number with a checksum digit",
    "tax bracket calculation with EVALUATE",
    "report with edited pictures: leading zeros suppressed, signs, commas",
    "running balance of deposits and withdrawals with overdraft check",
    "multiplication or amortization table printed with PERFORM VARYING",
    "counting records by category using an OCCURS table of counters",
    "Fibonacci, factorial or prime numbers with PERFORM loops",
    "nested PERFORM paragraphs with a menu-like dispatch on a code",
]

GENERATION_PROMPT = """Write a NEW small, self-contained COBOL program and its exact Java 17 translation.

Topic: {topic}

COBOL requirements (GnuCOBOL, free format, compiled with `cobc -x -free`):
- IDENTIFICATION, DATA and PROCEDURE divisions; no files, no SQL, no CALL, no CURRENT-DATE or randomness
- read ALL input with ACCEPT, one value or line per ACCEPT; convert numbers with FUNCTION NUMVAL
- write all output with DISPLAY; deterministic output
- 25 to 90 lines, realistic business logic, meaningful data names (WS-...)
- use typical COBOL features where they fit: PIC 9/S9/V99, edited pictures, COMPUTE ROUNDED,
  EVALUATE, PERFORM VARYING, paragraphs, OCCURS tables, STRING/UNSTRING, INSPECT

Tests: 5 different stdin inputs covering normal cases and edge cases (zero, boundaries, negatives if signed).

Java requirements: one `public class Main`, standard library only, reads stdin, prints EXACTLY the same
output as the COBOL program for every test (same spacing, zero padding, edited pictures, truncation vs rounding).

Here is an example of the expected quality:
<example_cobol>
{example_cobol}
</example_cobol>
<example_java>
{example_java}
</example_java>

Answer with exactly these four tagged sections and nothing else:
<explanation>plain-English explanation of what the COBOL program does (3-5 sentences)</explanation>
<cobol>the COBOL source</cobol>
<tests>a JSON array of 5 strings, each the full stdin for one run, lines separated by \\n</tests>
<java>the Java source</java>
"""

REPAIR_PROMPT = """The Java translation does not produce the same output as the COBOL program.

{errors}

Fix the Java code so its output matches the COBOL output exactly. Pay attention to COBOL field
sizes, padding, zero suppression, sign handling, truncation and ROUNDED.
Answer only with the corrected code inside <java></java> tags."""

COBOL_REPAIR_PROMPT = """The COBOL program does not compile with `cobc -x -free`:

{errors}

Fix the COBOL program (declare every data item you use, use only syntax GnuCOBOL supports) and
update the Java translation so it still prints exactly the same output.
Answer only with the corrected code inside <cobol></cobol> and <java></java> tags."""


def parse_tag(text: str, tag: str) -> str | None:
    match = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text, flags=re.DOTALL)
    if not match:
        return None
    body = match.group(1)
    # strip a markdown fence if the model added one inside the tag
    fenced = re.match(r"^```\w*\n(.*?)\n?```$", body.strip(), flags=re.DOTALL)
    return fenced.group(1) if fenced else body


def parse_generation(text: str) -> dict | None:
    parts = {tag: parse_tag(text, tag) for tag in ("explanation", "cobol", "tests", "java")}
    if any(v is None for v in parts.values()):
        return None
    try:
        inputs = json.loads(parts["tests"])
    except json.JSONDecodeError:
        return None
    if not isinstance(inputs, list) or not inputs or not all(isinstance(s, str) for s in inputs):
        return None
    tests = [{"input": s if s.endswith("\n") else s + "\n"} for s in inputs]
    return {"explanation": parts["explanation"], "cobol": parts["cobol"], "java": parts["java"], "tests": tests}


def chat(client, model: str, messages: list[dict], temperature: float) -> str:
    response = client.chat.completions.create(
        model=model, messages=messages, temperature=temperature, max_tokens=6000
    )
    return response.choices[0].message.content or ""


def existing_hashes(out_dir: Path) -> set[str]:
    return {hashlib.sha256((p / "program.cbl").read_text().encode()).hexdigest()
            for p in out_dir.iterdir() if (p / "program.cbl").exists()}


def save_pair(out_dir: Path, name: str, sample: dict) -> None:
    d = out_dir / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "program.cbl").write_text(sample["cobol"].strip() + "\n")
    (d / "Main.java").write_text(sample["java"].strip() + "\n")
    (d / "tests.json").write_text(json.dumps(sample["tests"], indent=2) + "\n")
    (d / "explanation.md").write_text(sample["explanation"].strip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=20, help="number of generation attempts")
    parser.add_argument("--out", type=Path, default=Path("data/programs"))
    parser.add_argument("--model", default="Qwen/Qwen3-Coder-480B-A35B-Instruct")
    parser.add_argument("--base-url", default="https://router.huggingface.co/v1")
    parser.add_argument("--api-key-env", default="HF_TOKEN")
    parser.add_argument("--repairs", type=int, default=3, help="repair rounds for COBOL compile errors or Java output diffs")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    from openai import OpenAI  # imported here so --help works without the package

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(f"Set the {args.api_key_env} environment variable first.", file=sys.stderr)
        return 2
    client = OpenAI(base_url=args.base_url, api_key=api_key)
    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)

    seeds = [p for p in sorted(args.out.iterdir()) if (p / "program.cbl").exists()]
    if not seeds:
        print(f"No example pairs found in {args.out}; keep the seed examples there.", file=sys.stderr)
        return 2
    hashes = existing_hashes(args.out)
    next_id = 1 + max([int(m.group(1)) for p in args.out.iterdir()
                       if (m := re.match(r"gen_(\d+)$", p.name))] or [0])

    kept = 0
    for attempt in range(1, args.count + 1):
        topic = rng.choice(TOPICS)
        example_cobol, example_java, _ = load_program_dir(rng.choice(seeds))
        messages = [{"role": "user", "content": GENERATION_PROMPT.format(
            topic=topic, example_cobol=example_cobol, example_java=example_java)}]
        try:
            reply = chat(client, args.model, messages, args.temperature)
        except Exception as e:  # network or rate-limit errors: skip this attempt
            print(f"[{attempt}] API error: {e}")
            continue

        sample = parse_generation(reply)
        if sample is None:
            print(f"[{attempt}] could not parse the answer, skipped")
            continue
        digest = hashlib.sha256((sample["cobol"].strip() + "\n").encode()).hexdigest()
        if digest in hashes:
            print(f"[{attempt}] duplicate program, skipped")
            continue

        result = check_pair("candidate", sample["cobol"], sample["java"], sample["tests"])
        repairs = 0
        while not result.ok and repairs < args.repairs:
            if any("COBOL program failed" in e for e in result.errors):
                break  # the reference itself is broken; repairing Java cannot help
            prompt, tags = (REPAIR_PROMPT, ("java",)) if result.cobol_compiled else (COBOL_REPAIR_PROMPT, ("cobol", "java"))
            repairs += 1
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": prompt.format(errors="\n\n".join(result.errors)[:4000])}]
            try:
                reply = chat(client, args.model, messages, 0.2)
            except Exception as e:
                print(f"[{attempt}] API error during repair: {e}")
                break
            fixed = {tag: parse_tag(reply, tag) for tag in tags}
            if any(v is None for v in fixed.values()):
                break
            sample.update(fixed)
            result = check_pair("candidate", sample["cobol"], sample["java"], sample["tests"])
        digest = hashlib.sha256((sample["cobol"].strip() + "\n").encode()).hexdigest()

        if result.ok and digest not in hashes:
            name = f"gen_{next_id:04d}"
            save_pair(args.out, name, sample)
            hashes.add(digest)
            next_id += 1
            kept += 1
            print(f"[{attempt}] KEPT {name} ({topic}; repairs: {repairs})")
        else:
            reason = ("duplicate program" if result.ok else "COBOL does not compile" if not result.cobol_compiled
                      else f"tests {result.passed}/{result.total}")
            print(f"[{attempt}] rejected: {reason}")

    print(f"\nKept {kept} verified pairs out of {args.count} attempts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
