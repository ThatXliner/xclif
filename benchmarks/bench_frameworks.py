"""Performance benchmarks: Click vs Typer vs Xclif.

Each framework's example lives in benchmarks/examples/ as a self-contained
script or package. This runner invokes them as subprocesses — exactly as a
user would — and measures wall-clock time for each invocation.

Usage:
    uv run python benchmarks/bench_frameworks.py
    uv run python benchmarks/bench_frameworks.py --iterations 50
    uv run python benchmarks/bench_frameworks.py --iterations 50 --no-warmup
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent / "examples"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Invocation:
    """One CLI call to benchmark."""
    label: str       # human-readable scenario name
    args: list[str]  # argv passed after the entry point


@dataclass
class Target:
    """One framework example under test."""
    name: str
    cmd: list[str]          # base command; args are appended per invocation
    invocations: list[Invocation] = field(default_factory=list)


@dataclass
class Result:
    target: str
    label: str
    mean_ms: float
    min_ms: float
    max_ms: float
    n: int

    def __str__(self) -> str:
        return (
            f"{self.target:<10} {self.label:<28} "
            f"mean={self.mean_ms:>7.1f} ms  "
            f"min={self.min_ms:>7.1f} ms  "
            f"max={self.max_ms:>7.1f} ms  "
            f"(n={self.n})"
        )


# ---------------------------------------------------------------------------
# Shared invocations (same CLI surface across all three examples)
# ---------------------------------------------------------------------------

INVOCATIONS = [
    Invocation("greet World",              ["greet", "World"]),
    Invocation("greet + options",          ["greet", "Alice", "--greeting", "Hi", "--count", "3"]),
    Invocation("root --help",              ["--help"]),
    Invocation("greet --help",             ["greet", "--help"]),
    Invocation("config set key value",     ["config", "set", "theme", "dark"]),
    Invocation("config get key",           ["config", "get", "theme"]),
]

# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

def build_targets() -> list[Target]:
    return [
        Target(
            name="Click",
            cmd=[sys.executable, str(EXAMPLES_DIR / "click_greeter.py")],
            invocations=INVOCATIONS,
        ),
        Target(
            name="Typer",
            cmd=[sys.executable, str(EXAMPLES_DIR / "typer_greeter.py")],
            invocations=INVOCATIONS,
        ),
        Target(
            name="Xclif",
            # Run as a package: python -m xclif_greeter <args>
            cmd=[sys.executable, "-m", "xclif_greeter"],
            invocations=INVOCATIONS,
        ),
        Target(
            name="Xclif (flat)",
            cmd=[sys.executable, str(EXAMPLES_DIR / "xclif_greeter_flat.py")],
            invocations=INVOCATIONS,
        ),
        Target(
            name="Xclif (manifest)",
            cmd=[sys.executable, "-m", "xclif_greeter_manifest"],
            invocations=INVOCATIONS,
        ),
    ]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_once(cmd: list[str], args: list[str]) -> float:
    """Invoke the command, return elapsed milliseconds."""
    t0 = time.perf_counter()
    subprocess.run(
        cmd + args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=EXAMPLES_DIR,
    )
    return (time.perf_counter() - t0) * 1000


def bench_target(target: Target, iterations: int, warmup: int) -> list[Result]:
    results = []
    for inv in target.invocations:
        # Warmup runs are discarded
        for _ in range(warmup):
            run_once(target.cmd, inv.args)

        times = [run_once(target.cmd, inv.args) for _ in range(iterations)]
        results.append(Result(
            target=target.name,
            label=inv.label,
            mean_ms=sum(times) / len(times),
            min_ms=min(times),
            max_ms=max(times),
            n=iterations,
        ))
    return results

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

ORDERED_LABELS = [inv.label for inv in INVOCATIONS]


def print_comparison_table(all_results: list[Result]) -> None:
    by_label: dict[str, dict[str, float]] = {}
    for r in all_results:
        by_label.setdefault(r.label, {})[r.target] = r.mean_ms

    frameworks = ["Click", "Typer", "Xclif", "Xclif (flat)", "Xclif (manifest)"]
    col = 14
    header = f"{'Scenario':<28} " + "".join(f"{fw:>{col}}" for fw in frameworks) + f"  {'Winner'}"
    sep = "-" * len(header)

    print(f"\n{sep}")
    print("Mean wall-clock time per invocation  (ms — lower is better)")
    print(sep)
    print(header)
    print(sep)

    for label in ORDERED_LABELS:
        vals = by_label.get(label, {})
        if not vals:
            continue
        best = min(vals, key=lambda k: vals[k])
        cells = {fw: f"{vals[fw]:.1f}" if fw in vals else "n/a" for fw in frameworks}
        cells[best] = f"*{cells[best]}*"
        row = f"{label:<28} " + "".join(f"{cells[fw]:>{col}}" for fw in frameworks) + f"  {best}"
        print(row)

    print(sep)
    print("* = fastest for that scenario\n")


def print_speedup_table(all_results: list[Result]) -> None:
    by_label: dict[str, dict[str, float]] = {}
    for r in all_results:
        by_label.setdefault(r.label, {})[r.target] = r.mean_ms

    header = f"{'Scenario':<28} {'Xclif vs Click':>18} {'Xclif vs Typer':>18} {'Flat vs Click':>18} {'Manifest vs Click':>20}"
    sep = "-" * len(header)

    print(sep)
    print("Xclif relative speed  (>1x = Xclif is faster)")
    print(sep)
    print(header)
    print(sep)

    for label in ORDERED_LABELS:
        vals = by_label.get(label, {})
        xclif    = vals.get("Xclif")
        flat     = vals.get("Xclif (flat)")
        manifest = vals.get("Xclif (manifest)")
        click    = vals.get("Click")
        typer    = vals.get("Typer")
        vs_click      = f"{click / xclif:.2f}x"    if (xclif    and click) else "n/a"
        vs_typer      = f"{typer / xclif:.2f}x"    if (xclif    and typer) else "n/a"
        flat_vs_click = f"{click / flat:.2f}x"     if (flat     and click) else "n/a"
        mani_vs_click = f"{click / manifest:.2f}x" if (manifest and click) else "n/a"
        print(f"{label:<28} {vs_click:>18} {vs_typer:>18} {flat_vs_click:>18} {mani_vs_click:>20}")

    print(sep + "\n")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iterations", "-n", type=int, default=30,
                    help="Timed iterations per scenario (default: 30)")
    ap.add_argument("--warmup", "-w", type=int, default=3,
                    help="Discarded warmup runs per scenario (default: 3)")
    ap.add_argument("--no-warmup", action="store_true",
                    help="Skip warmup runs")
    args = ap.parse_args()

    warmup = 0 if args.no_warmup else args.warmup
    targets = build_targets()

    total = sum(
        (warmup + args.iterations) * len(t.invocations)
        for t in targets
    )
    print(
        f"Running {len(targets)} frameworks × {len(INVOCATIONS)} scenarios "
        f"× {args.iterations} iterations  (+{warmup} warmup each)\n"
        f"Total subprocess invocations: {total}\n"
    )

    all_results: list[Result] = []
    for target in targets:
        print(f"[ {target.name} ]")
        results = bench_target(target, args.iterations, warmup)
        for r in results:
            print(" ", r)
        all_results.extend(results)
        print()

    print_comparison_table(all_results)
    print_speedup_table(all_results)


if __name__ == "__main__":
    main()
