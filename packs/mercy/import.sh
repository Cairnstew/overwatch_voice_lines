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
  --form-string 'name=Mercy' \
  --form-string 'description=Mercy voice reference assembled from 7 Overwatch voice lines. Clean, close recording; game character delivery.' \
  --form-string 'metadata={"character": "Mercy", "dataset": "Mercy", "source": "Overwatch wiki (Fandom)", "source_page": "Mercy/Quotes", "source_revision": "375917", "source_url": "https://overwatch.fandom.com/wiki/Mercy/Quotes", "reference_seconds": "13.61", "reference_clips": "mercy__mercy-not-to-worry-i-ll-patch-you-up__9297fe32;mercy__mercy-i-ll-have-you-in-top-condition__36f18a54;mercy__mercy-i-ll-make-sure-that-doesn-t-scar__ae13cc95;mercy__mercy-this-will-just-take-a-moment__e441422a;mercy__mercy-still-in-your-back-pocket__b99329f7;mercy__mercy-ha-feel-stronger__effc9c8f;mercy__mercy-let-me-see-what-i-can-do__e7011d8d", "language": "en"}'
echo
