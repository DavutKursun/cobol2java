"""Prompt format shared by dataset building, training, evaluation and the demo app.

Keeping it in one place guarantees the model sees exactly the same format
at training time and at inference time.
"""

from __future__ import annotations

import re

SYSTEM_PROMPT = (
    "You are an expert in legacy modernization. Translate the given COBOL program into an "
    "equivalent Java 17 program. First explain in plain English what the COBOL program does, "
    "then give the Java code.\n"
    "Rules for the Java code:\n"
    "- one public class named Main with a main method, standard library only\n"
    "- read input from stdin and write output to stdout exactly like the COBOL program\n"
    "- use BigDecimal for decimal fields and keep COBOL rounding/truncation behavior\n"
    "- reproduce the COBOL output format exactly (padding, leading zeros, edited pictures)"
)


def user_message(cobol: str) -> str:
    return f"Translate this COBOL program to Java.\n\n```cobol\n{cobol.strip()}\n```"


def assistant_message(explanation: str, java: str) -> str:
    return f"### Explanation\n{explanation.strip()}\n\n### Java\n```java\n{java.strip()}\n```"


def build_messages(cobol: str) -> list[dict]:
    """Messages sent to the model at inference time."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message(cobol)},
    ]


def extract_java(text: str) -> str | None:
    """Return the Java code from a model answer (the last ```java block, or any block with a class)."""
    blocks = re.findall(r"```java\s*\n(.*?)```", text, flags=re.DOTALL)
    if not blocks:
        blocks = [b for b in re.findall(r"```\w*\s*\n(.*?)```", text, flags=re.DOTALL) if "class " in b]
    if not blocks:
        # an unfinished block (generation hit the token limit) still counts, it will just fail to compile
        match = re.search(r"```java\s*\n(.*)$", text, flags=re.DOTALL)
        return match.group(1).strip() if match else None
    return blocks[-1].strip()


def extract_explanation(text: str) -> str:
    match = re.search(r"### Explanation\s*\n(.*?)(?:\n### Java|```)", text, flags=re.DOTALL)
    return match.group(1).strip() if match else ""
