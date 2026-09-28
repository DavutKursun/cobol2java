"""Evaluate a model on the held-out test programs by actually running its Java code.

For each test program the model generates a translation; the Java code is compiled and
run against the COBOL original on every test input. Metrics:
  - compile rate:    share of answers whose Java compiles
  - pass@1:          share of programs where ALL test outputs match the COBOL program
  - test-case rate:  share of individual test inputs with matching output

Run it twice to get the before/after table for the README:
    python scripts/evaluate_model.py --model Qwen/Qwen2.5-Coder-1.5B-Instruct --name base
    python scripts/evaluate_model.py --model outputs/cobol2java-lora/merged --name finetuned
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent))
from prompts import build_messages, extract_java  # noqa: E402
from verify import check_pair  # noqa: E402


def generate(model, tokenizer, cobol: str, max_new_tokens: int) -> str:
    text = tokenizer.apply_chat_template(build_messages(cobol), tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,  # greedy decoding -> reproducible results
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
    return tokenizer.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True, help="Hub id or local path (base or merged model)")
    parser.add_argument("--adapter", help="optional LoRA adapter folder to load on top of --model")
    parser.add_argument("--name", default="model", help="label used in the results file")
    parser.add_argument("--data", type=Path, default=Path("data/test.jsonl"))
    parser.add_argument("--max-new-tokens", type=int, default=1536)
    parser.add_argument("--limit", type=int, help="evaluate only the first N programs")
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.data.read_text().splitlines() if line.strip()]
    if args.limit:
        rows = rows[: args.limit]

    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=dtype)
    if args.adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, args.adapter)
    model.to("cuda" if torch.cuda.is_available() else "cpu").eval()

    samples = []
    compiled = passed_all = cases_passed = cases_total = 0
    for i, row in enumerate(rows, 1):
        start = time.time()
        answer = generate(model, tokenizer, row["cobol"], args.max_new_tokens)
        java = extract_java(answer)
        if java is None:
            result = None
            cases_total += len(row["tests"])
        else:
            result = check_pair(row["id"], row["cobol"], java, row["tests"])
            compiled += result.java_compiled
            passed_all += result.ok
            cases_passed += result.passed
            cases_total += result.total
        status = "no code" if result is None else ("PASS" if result.ok else f"{result.passed}/{result.total}")
        print(f"[{i}/{len(rows)}] {row['id']:<25} {status:<8} ({time.time() - start:.0f}s)")
        samples.append({
            "id": row["id"],
            "answer": answer,
            "java_compiled": bool(result and result.java_compiled),
            "passed": result.passed if result else 0,
            "total": len(row["tests"]),
            "errors": result.errors[:3] if result else ["no Java code in the answer"],
        })

    n = len(rows)
    metrics = {
        "model": args.model,
        "adapter": args.adapter,
        "programs": n,
        "compile_rate": compiled / n,
        "pass_at_1": passed_all / n,
        "test_case_rate": cases_passed / cases_total if cases_total else 0.0,
    }
    args.results_dir.mkdir(parents=True, exist_ok=True)
    out = args.results_dir / f"{args.name}.json"
    out.write_text(json.dumps({"metrics": metrics, "samples": samples}, indent=2))

    print("\n| Model | Java compiles | pass@1 (all tests) | Test cases passed |")
    print("| --- | --- | --- | --- |")
    print(f"| {args.name} | {metrics['compile_rate']:.1%} | {metrics['pass_at_1']:.1%} | {metrics['test_case_rate']:.1%} |")
    print(f"\nDetails saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
