"""Gradio demo for Hugging Face Spaces: paste COBOL, get an explanation and a Java translation."""

import os
from pathlib import Path
from threading import Thread

import gradio as gr
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

from prompts import build_messages, extract_explanation, extract_java

MODEL_ID = os.environ.get("MODEL_ID", "DavutKursun/cobol2java-qwen2.5-coder-1.5b")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, dtype=torch.float16 if DEVICE == "cuda" else torch.float32
).to(DEVICE).eval()

EXAMPLES = [[p.read_text()] for p in sorted(Path(__file__).parent.glob("examples/*.cbl"))]


def translate(cobol: str):
    if not cobol.strip():
        yield "Paste a COBOL program first.", ""
        return
    text = tokenizer.apply_chat_template(build_messages(cobol), tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(DEVICE)
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    Thread(target=model.generate, kwargs=dict(
        **inputs, streamer=streamer, max_new_tokens=1536, do_sample=False,
        pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
    )).start()

    answer = ""
    for chunk in streamer:
        answer += chunk
        yield extract_explanation(answer) or "Generating...", extract_java(answer) or ""


with gr.Blocks(title="COBOL to Java") as demo:
    gr.Markdown(
        "# COBOL → Java Translator\n"
        "A fine-tuned Qwen2.5-Coder model that explains legacy COBOL programs and translates them "
        "into equivalent Java 17 code. Trained on COBOL/Java pairs whose outputs were verified by "
        "compiling and running both programs."
    )
    with gr.Row():
        with gr.Column():
            cobol_in = gr.Code(label="COBOL program", lines=24)
            run = gr.Button("Translate", variant="primary")
        with gr.Column():
            explanation_out = gr.Markdown(label="Explanation")
            # Gradio has no Java mode; C++ highlighting is close enough for Java syntax
            java_out = gr.Code(label="Java", language="cpp", lines=24)
    if EXAMPLES:
        gr.Examples(EXAMPLES, inputs=[cobol_in])
    run.click(translate, inputs=cobol_in, outputs=[explanation_out, java_out])

if __name__ == "__main__":
    demo.launch()
