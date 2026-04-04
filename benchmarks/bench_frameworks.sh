#!/usr/bin/env bash
# Benchmark Click vs Typer vs Xclif using hyperfine.
#
# Requires:
#   hyperfine  — https://github.com/sharkdp/hyperfine
#               brew install hyperfine  (macOS)
#               cargo install hyperfine (cross-platform)
#
# Usage:
#   bash benchmarks/bench_frameworks.sh
#   bash benchmarks/bench_frameworks.sh --runs 50

set -euo pipefail

if ! command -v hyperfine &>/dev/null; then
    echo "error: hyperfine not found." >&2
    echo "  macOS:      brew install hyperfine" >&2
    echo "  Cargo:      cargo install hyperfine" >&2
    echo "  GitHub:     https://github.com/sharkdp/hyperfine" >&2
    exit 1
fi

RUNS="${2:-30}"
if [[ "${1:-}" == "--runs" ]]; then
    RUNS="$2"
fi

DIR="$(cd "$(dirname "$0")/examples" && pwd)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"

CLICK="$PY $DIR/click_greeter.py"
TYPER="$PY $DIR/typer_greeter.py"
XCLIF_FLAT="$PY $DIR/xclif_greeter_flat.py"
XCLIF="env PYTHONPATH=$DIR $PY -m xclif_greeter"
XCLIF_MANIFEST="env PYTHONPATH=$DIR $PY -m xclif_greeter_manifest"

run() {
    local label="$1"; shift
    echo ""
    echo "=== $label ==="
    hyperfine --warmup 3 --runs "$RUNS" --shell=none "$@"
}

run "greet World" \
    --command-name "click"            "$CLICK greet World" \
    --command-name "typer"            "$TYPER greet World" \
    --command-name "xclif"            "$XCLIF greet World" \
    --command-name "xclif-flat"       "$XCLIF_FLAT greet World" \
    --command-name "xclif-manifest"   "$XCLIF_MANIFEST greet World"

run "greet + options" \
    --command-name "click"            "$CLICK greet Alice --greeting Hi --count 3" \
    --command-name "typer"            "$TYPER greet Alice --greeting Hi --count 3" \
    --command-name "xclif"            "$XCLIF greet Alice --greeting Hi --count 3" \
    --command-name "xclif-flat"       "$XCLIF_FLAT greet Alice --greeting Hi --count 3" \
    --command-name "xclif-manifest"   "$XCLIF_MANIFEST greet Alice --greeting Hi --count 3"

run "root --help" \
    --command-name "click"            "$CLICK --help" \
    --command-name "typer"            "$TYPER --help" \
    --command-name "xclif"            "$XCLIF --help" \
    --command-name "xclif-flat"       "$XCLIF_FLAT --help" \
    --command-name "xclif-manifest"   "$XCLIF_MANIFEST --help"

run "greet --help" \
    --command-name "click"            "$CLICK greet --help" \
    --command-name "typer"            "$TYPER greet --help" \
    --command-name "xclif"            "$XCLIF greet --help" \
    --command-name "xclif-flat"       "$XCLIF_FLAT greet --help" \
    --command-name "xclif-manifest"   "$XCLIF_MANIFEST greet --help"

run "config set" \
    --command-name "click"            "$CLICK config set theme dark" \
    --command-name "typer"            "$TYPER config set theme dark" \
    --command-name "xclif"            "$XCLIF config set theme dark" \
    --command-name "xclif-flat"       "$XCLIF_FLAT config set theme dark" \
    --command-name "xclif-manifest"   "$XCLIF_MANIFEST config set theme dark"

run "config get" \
    --command-name "click"            "$CLICK config get theme" \
    --command-name "typer"            "$TYPER config get theme" \
    --command-name "xclif"            "$XCLIF config get theme" \
    --command-name "xclif-flat"       "$XCLIF_FLAT config get theme" \
    --command-name "xclif-manifest"   "$XCLIF_MANIFEST config get theme"
