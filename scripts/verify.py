"""Check that a Java translation behaves exactly like the original COBOL program.

For every test input, both programs are compiled and run with the same stdin,
and their stdout is compared (trailing spaces and trailing blank lines are ignored,
because COBOL pads PIC X fields with spaces).

Usage:
    python scripts/verify.py data/programs            # check every pair
    python scripts/verify.py data/programs --only interest_calc
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

RUN_TIMEOUT = 10  # seconds per program run
COMPILE_TIMEOUT = 60


@dataclass
class PairResult:
    name: str
    cobol_compiled: bool = False
    java_compiled: bool = False
    passed: int = 0
    total: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.cobol_compiled and self.java_compiled and self.total > 0 and self.passed == self.total


def normalize(output: str) -> str:
    lines = [line.rstrip() for line in output.replace("\r\n", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _run(cmd: list[str], stdin: str = "", cwd: Path | None = None, timeout: int = RUN_TIMEOUT):
    try:
        proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True, cwd=cwd, timeout=timeout)
        # the JVM may print "Picked up JAVA_TOOL_OPTIONS..." on stderr; it is noise
        stderr = "\n".join(l for l in proc.stderr.splitlines() if not l.startswith("Picked up "))
        return proc.returncode, proc.stdout, stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout}s"


def compile_cobol(source: str, workdir: Path) -> tuple[Path | None, str]:
    src = workdir / "program.cbl"
    src.write_text(source if source.endswith("\n") else source + "\n")
    exe = workdir / "cobol_prog"
    code, _, err = _run(["cobc", "-x", "-free", "-o", str(exe), str(src)], timeout=COMPILE_TIMEOUT)
    return (exe if code == 0 else None), err


def compile_java(source: str, workdir: Path) -> tuple[str | None, str]:
    match = re.search(r"public\s+(?:final\s+)?class\s+(\w+)", source)
    class_name = match.group(1) if match else "Main"
    java_dir = workdir / "java"
    java_dir.mkdir(exist_ok=True)
    (java_dir / f"{class_name}.java").write_text(source)
    code, _, err = _run(["javac", "-nowarn", f"{class_name}.java"], cwd=java_dir, timeout=COMPILE_TIMEOUT)
    return (class_name if code == 0 else None), err


def check_pair(name: str, cobol_src: str, java_src: str, tests: list[dict]) -> PairResult:
    """Compile both programs and compare their output on every test input."""
    result = PairResult(name=name, total=len(tests))
    workdir = Path(tempfile.mkdtemp(prefix="c2j_"))
    try:
        exe, err = compile_cobol(cobol_src, workdir)
        result.cobol_compiled = exe is not None
        if not exe:
            result.errors.append(f"COBOL compile error: {err.strip()[:1500]}")
            return result

        class_name, err = compile_java(java_src, workdir)
        result.java_compiled = class_name is not None
        if not class_name:
            result.errors.append(f"Java compile error: {err.strip()[:500]}")
            return result

        for i, test in enumerate(tests):
            stdin = test.get("input", "")
            cobol_code, cobol_out, cobol_err = _run([str(exe)], stdin)
            if cobol_code != 0 or not cobol_out.strip():
                # a test the COBOL program itself cannot run is not a valid reference
                result.errors.append(f"test {i}: COBOL program failed or printed nothing: {cobol_err.strip()[:300]}")
                continue
            _, java_out, java_err = _run(["java", "-cp", str(workdir / "java"), class_name], stdin)
            if normalize(cobol_out) == normalize(java_out):
                result.passed += 1
            else:
                result.errors.append(
                    f"test {i}: output differs\n--- COBOL ---\n{normalize(cobol_out)}\n"
                    f"--- Java ---\n{normalize(java_out)}\n{java_err.strip()[:300]}"
                )
        return result
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def load_program_dir(path: Path) -> tuple[str, str, list[dict]]:
    cobol = (path / "program.cbl").read_text()
    java = (path / "Main.java").read_text()
    tests = json.loads((path / "tests.json").read_text())
    return cobol, java, tests


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("programs_dir", type=Path)
    parser.add_argument("--only", help="check a single program folder by name")
    parser.add_argument("--verbose", "-v", action="store_true", help="print output differences")
    args = parser.parse_args()

    for tool in ("cobc", "javac", "java"):
        if shutil.which(tool) is None:
            print(f"'{tool}' not found. Install GnuCOBOL and a JDK (see README).", file=sys.stderr)
            return 2

    dirs = sorted(p for p in args.programs_dir.iterdir() if (p / "program.cbl").exists())
    if args.only:
        dirs = [p for p in dirs if p.name == args.only]

    ok_count = 0
    for d in dirs:
        cobol, java, tests = load_program_dir(d)
        r = check_pair(d.name, cobol, java, tests)
        ok_count += r.ok
        status = "PASS" if r.ok else "FAIL"
        print(f"[{status}] {d.name:<30} tests {r.passed}/{r.total}")
        if not r.ok and (args.verbose or not (r.cobol_compiled and r.java_compiled)):
            for e in r.errors:
                print("    " + e.replace("\n", "\n    "))

    print(f"\n{ok_count}/{len(dirs)} pairs verified")
    return 0 if ok_count == len(dirs) else 1


if __name__ == "__main__":
    sys.exit(main())
