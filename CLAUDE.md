# CLAUDE.md

Portfolio project: LoRA fine-tune of Qwen2.5-Coder-1.5B-Instruct that explains COBOL programs and translates them to Java 17. Every training pair is execution-verified (COBOL and Java compiled, run on the same stdin, outputs must match). See README.md for the pipeline.

## Accounts
- GitHub: `DavutKursun` → https://github.com/DavutKursun/cobol2java
- Hugging Face: `DavutKursun` (dataset `cobol-java-verified`, model `cobol2java-qwen2.5-coder-1.5b`, Space `cobol2java`)

## Where things run
- **Local (Mac, Apple M2, 8 GB):** data generation and verification only. `.venv` (Python 3.12) holds just `openai` and `datasets`.
- **Colab T4:** training and evaluation (`notebooks/train_colab.ipynb`, which clones the GitHub repo, so push data before training).
- **CI:** `.github/workflows/verify.yml` runs `verify.py` on Ubuntu and checks that `space/prompts.py` matches `scripts/prompts.py`.

## Gotchas
- Homebrew GnuCOBOL on Apple Silicon cannot find `gmp.h`; without `export CPATH=/opt/homebrew/include LIBRARY_PATH=/opt/homebrew/lib` every COBOL compile fails and verify reports 0/5.
- In the user's shell `python3` is aliased to Python 3.9; use `.venv/bin/python` or activate the venv.
- `space/prompts.py` is a copy of `scripts/prompts.py` (a Space only gets the `space/` folder). Edit both together; CI fails if they differ.
- The train/test split is a hash of the folder name, so adding programs never moves an old test program into train.
- Generated pairs land in `data/programs/gen_NNNN/`; `data/train.jsonl` and `data/test.jsonl` are rebuilt by `scripts/build_dataset.py`.

## Commands
```bash
python scripts/verify.py data/programs            # all pairs must PASS
export HF_TOKEN=hf_...
python scripts/generate_pairs.py --count 50       # repeat until a few hundred pairs
python scripts/build_dataset.py --reverify
```

## Roadmap
- [x] Seed pairs (5) verified locally, 5/5 tests each
- [x] Local environment: cobc 3.2, JDK, `.venv` with openai + datasets
- [x] README Quickstart for macOS, user names filled in
- [x] Git repo on GitHub, LICENSE, CI workflow
- [x] Smoke-tested train, evaluate and the Gradio app with a tiny model (2026-09-28)
- [ ] Hugging Face account token (write) → `export HF_TOKEN=...`
- [ ] Generate ~300 verified pairs, commit and push `data/programs`
- [ ] Colab: baseline evaluation of the base model
- [ ] Colab: LoRA training, evaluation of the fine-tuned model
- [ ] Push dataset and model to the Hub
- [ ] Fill the README results table with both evaluation rows
- [ ] Create the Hugging Face Space from `space/`
- [ ] Record a demo GIF for the README
