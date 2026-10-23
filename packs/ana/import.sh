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
  --form-string 'name=Ana' \
  --form-string 'description=Ana voice reference assembled from 5 Overwatch voice lines. Clean, close recording; game character delivery.' \
  --form-string 'metadata={"character": "Ana", "dataset": "Ana", "source": "Overwatch wiki (Fandom)", "source_page": "Ana/Quotes", "source_revision": "379402", "source_url": "https://overwatch.fandom.com/wiki/Ana/Quotes", "reference_seconds": "12.31", "reference_clips": "ana__ana-reloading-i-can-t-heal-right-now__1a63b986;ana__ana-it-s-just-a-scratch-you-ll-be-fine__765566d7;ana__ana-i-ve-seen-worse-you-re-going-to-live__f03cf2c5;ana__ana-enough-whining-you-re-fine__9e72e7d5;ana__ana-let-me-reload-just-a-moment__9d9aad22", "language": "en"}'
echo
