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
  --form-string 'name=Widowmaker' \
  --form-string 'description=Widowmaker voice reference assembled from 3 Overwatch voice lines. Clean, close recording; game character delivery.' \
  --form-string 'metadata={"character": "Widowmaker", "dataset": "Widowmaker", "source": "Overwatch wiki (Fandom)", "source_page": "Widowmaker/Quotes", "source_revision": "381316", "source_url": "https://overwatch.fandom.com/wiki/Widowmaker/Quotes", "reference_seconds": "11.17", "reference_clips": "widowmaker__widowmaker-the-countess-was-feared-by-all-rightful__3dfb8323;widowmaker__widowmaker-a-single-death-can-change-everything__208419e3;widowmaker__widowmaker-the-performance-is-about-to-begin__50feaab1", "language": "en"}'
echo
