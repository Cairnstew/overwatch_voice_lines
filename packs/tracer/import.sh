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
  --form-string 'name=Tracer' \
  --form-string 'description=Tracer voice reference assembled from 4 Overwatch voice lines. Clean, close recording; game character delivery.' \
  --form-string 'metadata={"character": "Tracer", "dataset": "Tracer", "source": "Overwatch wiki (Fandom)", "source_page": "Tracer/Quotes", "source_revision": "308892", "source_url": "https://overwatch.fandom.com/wiki/Tracer/Quotes", "reference_seconds": "13.79", "reference_clips": "tracer__tracer-i-can-t-wait-to-get-out-there-can-you-wait__07ed85fb;tracer__tracer-just-need-to-win-one-more-we-can-manage-tha__7b461c58;tracer__tracer-pre-mission-checklist-complete-now-it-s-tim__f0537d1e;tracer__tracer-i-ve-got-a-good-feeling-this-could-be-our-b__3cfea1e9", "language": "en"}'
echo
