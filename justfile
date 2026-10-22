set shell := ["bash", "-euo", "pipefail", "-c"]

# List recipes
default:
    @just --list

# Run the offline test suite
test:
    pytest -q

# Lint and format check
lint:
    ruff check .
    ruff format --check .

# Apply formatting
fmt:
    ruff format .

# Fetch, download and prepare Widowmaker (resumable)
build:
    python -m overwatch_voice_lines build Widowmaker

# Build any explicit wiki page under a custom dataset name
build-page page name:
    python -m overwatch_voice_lines build '{{page}}' --name '{{name}}'

# Small end-to-end smoke test (10 utterances)
smoke:
    python -m overwatch_voice_lines --data-dir data/smoke build Widowmaker --limit 10 --force

# Summarise prepared datasets
stats:
    python -m overwatch_voice_lines stats Widowmaker

# Write a Breeze-TTS WebUI reference pack (wav + exact transcript)
breeze:
    python -m overwatch_voice_lines export-breeze Widowmaker

# Write and upload the Breeze pack to a running server
breeze-upload server:
    python -m overwatch_voice_lines export-breeze Widowmaker --server '{{server}}'

# Delete generated data and caches
clean:
    rm -rf data .cache .pytest_cache .ruff_cache
