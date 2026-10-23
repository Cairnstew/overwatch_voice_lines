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
  --form-string 'name=Moira' \
  --form-string 'description=Moira voice reference assembled from 4 Overwatch voice lines. Clean, close recording; game character delivery.' \
  --form-string 'metadata={"character": "Moira", "dataset": "Moira", "source": "Overwatch wiki (Fandom)", "source_page": "Moira/Quotes", "source_revision": "381072", "source_url": "https://overwatch.fandom.com/wiki/Moira/Quotes", "reference_seconds": "14.94", "reference_clips": "moira__moira-much-lies-in-store-let-us-see-to-it__d115edbb;moira__moira-more-field-research-grand__7b3f661f;moira__moira-i-ll-see-this-matter-resolved__33179106;moira__moira-humanity-is-shackled-i-will-find-the-key__ed9b5984", "language": "en"}'
echo
