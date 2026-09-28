"""Fine-tune a small code LLM on the verified COBOL -> Java pairs with LoRA.

Designed for a free Google Colab T4 GPU (16 GB). With ~300 pairs and the defaults
below, training takes roughly 20-40 minutes for the 1.5B model.

Usage (Colab):
    python scripts/train_lora.py
    python scripts/train_lora.py --epochs 3 --merge --push-to-hub DavutKursun/cobol2java-qwen2.5-coder-1.5b
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig, PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer


def pick_dtype():
    if torch.cuda.is_available():
        return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    return torch.float32


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-1.5B-Instruct")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("outputs/cobol2java-lora"))
    parser.add_argument("--epochs", type=float, default=3)
    parser.add_argument("--max-steps", type=int, default=-1, help="for quick smoke tests")
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--merge", action="store_true", help="also save a merged full model (needed for the demo)")
    parser.add_argument("--push-to-hub", metavar="REPO_ID", help="upload the merged model (implies --merge)")
    args = parser.parse_args()

    dtype = pick_dtype()
    print(f"model: {args.model}  dtype: {dtype}  cuda: {torch.cuda.is_available()}")

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=dtype)

    dataset = load_dataset("json", data_files={"train": str(args.data_dir / "train.jsonl")})["train"]
    dataset = dataset.select_columns(["prompt", "completion"])
    print(f"training rows: {len(dataset)}")

    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_r * 2,
        lora_dropout=0.05,
        target_modules="all-linear",
        task_type="CAUSAL_LM",
    )

    config = SFTConfig(
        output_dir=str(args.output),
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=0.05,  # a float below 1 means "5% of the total steps"
        max_length=args.max_length,
        completion_only_loss=True,  # learn to write the answer, not to repeat the prompt
        gradient_checkpointing=torch.cuda.is_available(),
        bf16=dtype == torch.bfloat16,
        fp16=dtype == torch.float16,
        logging_steps=5,
        save_strategy="epoch",
        save_total_limit=1,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=config,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )
    trainer.train()

    adapter_dir = args.output / "adapter"
    trainer.save_model(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))
    print(f"LoRA adapter saved to {adapter_dir}")

    if args.merge or args.push_to_hub:
        del trainer, model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        base = AutoModelForCausalLM.from_pretrained(args.model, dtype=dtype)
        merged = PeftModel.from_pretrained(base, str(adapter_dir)).merge_and_unload()
        merged_dir = args.output / "merged"
        merged.save_pretrained(str(merged_dir))
        tokenizer.save_pretrained(str(merged_dir))
        print(f"merged model saved to {merged_dir}")
        if args.push_to_hub:
            merged.push_to_hub(args.push_to_hub)
            tokenizer.push_to_hub(args.push_to_hub)
            print(f"pushed to https://huggingface.co/{args.push_to_hub}")


if __name__ == "__main__":
    main()
