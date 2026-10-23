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
  --form-string 'name=Sombra' \
  --form-string 'description=Sombra voice reference assembled from 4 Overwatch voice lines. Clean, close recording; game character delivery.' \
  --form-string 'metadata={"character": "Sombra", "dataset": "Sombra", "source": "Overwatch wiki (Fandom)", "source_page": "Sombra/Quotes", "source_revision": "377213", "source_url": "https://overwatch.fandom.com/wiki/Sombra/Quotes", "reference_seconds": "12.39", "reference_clips": "sombra__sombra-easy-in-easy-out-let-s-get-the-job-done__c2e3f796;sombra__sombra-i-think-i-can-make-this-worth-my-time__cefd815a;sombra__sombra-in-my-world-there-are-no-secrets__8336f406;sombra__sombra-i-ve-had-worse-missions-but-this-is-pretty__19e264cf", "language": "en"}'
echo
