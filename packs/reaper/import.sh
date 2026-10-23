#!/usr/bin/env bash
# Save this reference directly into a running breeze-server.
# Usage: ./import.sh [SERVER_URL]
# Example: ./import.sh https://server.tail685690.ts.net:8445
set -euo pipefail
cd "$(dirname "$0")"
SERVER="${1:-http://127.0.0.1:8080}"
curl --fail-with-body -sS -X POST "${SERVER%/}/v1/voices" \
  -F "ref_audio=@reference.wav;type=audio/wav" \
  -F "ref_text=<reference.txt" \
  --form-string 'name=Reaper' \
  --form-string 'description=Reaper voice reference assembled from 4 Overwatch voice lines. Clean, close recording; game character delivery.' \
  --form-string 'metadata={"character": "Reaper", "dataset": "Reaper", "source": "Overwatch wiki (Fandom)", "source_page": "Reaper/Quotes", "source_revision": "381166", "source_url": "https://overwatch.fandom.com/wiki/Reaper/Quotes", "reference_seconds": "14.00", "reference_clips": "reaper__reaper-let-s-try-not-to-screw-this-up__17dfb28c;reaper__reaper-everything-s-going-according-to-plan__dbf6e0d8;reaper__reaper-don-t-fail-me-or-else__528fa172;reaper__reaper-screw-up-again-and-this-is-over__cf1b4afb", "language": "en"}'
echo
