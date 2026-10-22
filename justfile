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

# Re-encode a pack on a Breeze server and copy <Name>.breeze back into packs/
# Usage: just encode-pack widowmaker [server-url] [ssh-host] [voices-dir] [model] [family] [quant]
encode-pack char server="http://127.0.0.1:8137" host="server" voices_dir="/var/lib/breeze-tts/voices" model="breeze-tts-2-q4_k.gguf" family="breeze-tts-2" quant="q4_k":
    #!/usr/bin/env bash
    set -euo pipefail
    name="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "packs/{{char}}/voice.json")"
    "packs/{{char}}/import.sh" "{{server}}"
    ssh "{{host}}" "sudo cat '{{voices_dir}}/${name}.breeze'" > "packs/{{char}}/voice.breeze"
    test "$(head -c 4 "packs/{{char}}/voice.breeze")" = "BRZV"
    python3 - "packs/{{char}}/voice.json" "{{model}}" "{{family}}" "{{quant}}" <<'PY'
    import json
    import sys

    path, model, family, quant = sys.argv[1:]
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    manifest.update(
        {
            "breeze_file": "voice.breeze",
            "model": model,
            "model_family": family,
            "model_quant": quant,
        }
    )
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    PY
    echo "wrote packs/{{char}}/voice.breeze (${name})"

# Delete generated data and caches
clean:
    rm -rf data .cache .pytest_cache .ruff_cache
