"""In-process parsing speed benchmark: Click vs Typer vs Xclif.

Measures only argument parsing and dispatch — no subprocess overhead,
no Python startup, no import cost. Each framework's app is built once,
then the same argv is fed through its test runner/invoker repeatedly.

Usage:
    uv run python benchmarks/bench_parsing.py
    uv run python benchmarks/bench_parsing.py --iterations 10000
"""

from __future__ import annotations

import argparse
import io
import time
from contextlib import redirect_stderr, redirect_stdout
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator


@contextmanager
def silence() -> Generator[None, None, None]:
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        yield


@dataclass
class Result:
    framework: str
    label: str
    mean_us: float
    min_us: float
    n: int

    def __str__(self) -> str:
        return (
            f"{self.framework:<10} {self.label:<28} "
            f"mean={self.mean_us:>7.1f} µs  "
            f"min={self.min_us:>7.1f} µs  "
            f"(n={self.n})"
        )


def bench(fn, n: int) -> tuple[float, float]:
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1_000_000)
    return sum(times) / len(times), min(times)


SCENARIOS = [
    ("greet World",          ["greet", "World"]),
    ("greet + options",      ["greet", "Alice", "--greeting", "Hi", "--count", "3"]),
    ("root --help",          ["--help"]),
    ("greet --help",         ["greet", "--help"]),
    ("config set key value", ["config", "set", "theme", "dark"]),
    ("config get key",       ["config", "get", "theme"]),
]


# ---------------------------------------------------------------------------
# Click
# ---------------------------------------------------------------------------

def click_results(n: int) -> list[Result]:
    import click
    from click.testing import CliRunner

    @click.group()
    def cli() -> None:
        """Greeter CLI."""

    @cli.command()
    @click.argument("name")
    @click.option("--greeting", "-g", default="Hello")
    @click.option("--count", "-c", default=1, type=int)
    def greet(name: str, greeting: str, count: int) -> None:
        for _ in range(count):
            click.echo(f"{greeting}, {name}!")

    @cli.group()
    def config() -> None:
        pass

    @config.command()
    @click.argument("key")
    @click.argument("value")
    def set(key: str, value: str) -> None:
        click.echo(f"Set {key}={value}")

    @config.command("get")
    @click.argument("key")
    def get_cmd(key: str) -> None:
        click.echo(f"Get {key}")

    runner = CliRunner()
    results = []
    for label, args in SCENARIOS:
        mean, mn = bench(lambda a=args: runner.invoke(cli, a), n)
        results.append(Result("Click", label, mean, mn, n))
    return results


# ---------------------------------------------------------------------------
# Typer
# ---------------------------------------------------------------------------

def typer_results(n: int) -> list[Result]:
    import typer
    from typer.testing import CliRunner

    app = typer.Typer()
    config_app = typer.Typer()
    app.add_typer(config_app, name="config")

    @app.command()
    def greet(
        name: str,
        greeting: str = typer.Option("Hello", "-g", "--greeting"),
        count: int = typer.Option(1, "-c", "--count"),
    ) -> None:
        for _ in range(count):
            typer.echo(f"{greeting}, {name}!")

    @config_app.command()
    def set(key: str, value: str) -> None:
        typer.echo(f"Set {key}={value}")

    @config_app.command("get")
    def get_cmd(key: str) -> None:
        typer.echo(f"Get {key}")

    runner = CliRunner()
    results = []
    for label, args in SCENARIOS:
        mean, mn = bench(lambda a=args: runner.invoke(app, a), n)
        results.append(Result("Typer", label, mean, mn, n))
    return results


# ---------------------------------------------------------------------------
# Xclif
# ---------------------------------------------------------------------------

def xclif_results(n: int) -> list[Result]:
    from xclif.command import Command

    root = Command("greeter", lambda: None)

    @root.command()
    def greet(name: str, greeting: str = "Hello", count: int = 1) -> None:
        for _ in range(count):
            print(f"{greeting}, {name}!")

    @root.command(["config", "set"])
    def set(key: str, value: str) -> None:
        print(f"Set {key}={value}")

    @root.command(["config", "get"])
    def get_cmd(key: str) -> None:
        print(f"Get {key}")

    results = []
    for label, args in SCENARIOS:
        with silence():  # suppress Rich help output during timing
            mean, mn = bench(lambda a=args: root.execute(a), n)
        results.append(Result("Xclif", label, mean, mn, n))
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

FRAMEWORKS = ["Click", "Typer", "Xclif"]


def print_comparison_table(all_results: list[Result]) -> None:
    by_label: dict[str, dict[str, float]] = {}
    for r in all_results:
        by_label.setdefault(r.label, {})[r.framework] = r.mean_us

    col = 12
    header = f"{'Scenario':<28} " + "".join(f"{fw:>{col}}" for fw in FRAMEWORKS) + "  Winner"
    sep = "-" * len(header)

    print(f"\n{sep}")
    print("Mean parse+dispatch latency  (µs — lower is better)")
    print(sep)
    print(header)
    print(sep)

    for label, _ in SCENARIOS:
        vals = by_label.get(label, {})
        best = min(vals, key=lambda k: vals[k])
        cells = {fw: f"{vals[fw]:.1f}" if fw in vals else "n/a" for fw in FRAMEWORKS}
        cells[best] = f"*{cells[best]}*"
        print(f"{label:<28} " + "".join(f"{cells[fw]:>{col}}" for fw in FRAMEWORKS) + f"  {best}")

    print(sep)
    print("* = fastest\n")


def print_speedup_table(all_results: list[Result]) -> None:
    by_label: dict[str, dict[str, float]] = {}
    for r in all_results:
        by_label.setdefault(r.label, {})[r.framework] = r.mean_us

    header = f"{'Scenario':<28} {'Xclif vs Click':>18} {'Xclif vs Typer':>18}"
    sep = "-" * len(header)
    print(sep)
    print("Xclif relative speed  (>1x = Xclif is faster)")
    print(sep)
    print(header)
    print(sep)

    for label, _ in SCENARIOS:
        vals = by_label.get(label, {})
        xclif = vals.get("Xclif")
        click  = vals.get("Click")
        typer  = vals.get("Typer")
        vs_click = f"{click  / xclif:.2f}x" if (xclif and click)  else "n/a"
        vs_typer = f"{typer  / xclif:.2f}x" if (xclif and typer)  else "n/a"
        print(f"{label:<28} {vs_click:>18} {vs_typer:>18}")

    print(sep + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iterations", "-n", type=int, default=5000,
                    help="Iterations per scenario (default: 5000)")
    args = ap.parse_args()

    print(f"In-process parsing benchmark  (n={args.iterations} per scenario)\n")

    all_results: list[Result] = []

    for name, fn in [("Click", click_results), ("Typer", typer_results), ("Xclif", xclif_results)]:
        print(f"[ {name} ]")
        results = fn(args.iterations)
        for r in results:
            print(" ", r)
        all_results.extend(results)
        print()

    print_comparison_table(all_results)
    print_speedup_table(all_results)


if __name__ == "__main__":
    main()
