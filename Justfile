default: test

# Run the test suite
test *args:
    uv run pytest {{args}}

# Run tests with coverage report
cov:
    uv run pytest --cov=src/xclif --cov-report=term-missing

# Build the HTML docs
docs:
    uv run sphinx-build docs docs/_build/html

# Serve docs locally with live reload
docs-serve:
    uv run sphinx-autobuild docs docs/_build/html

# Build the distribution (wheel + sdist)
build:
    uv build

# Remove build artifacts
clean:
    rm -rf dist docs/_build

# Install all dependency groups
install:
    uv sync --all-groups
