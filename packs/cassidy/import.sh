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
  --form-string 'name=Cassidy' \
  --form-string 'description=Cassidy voice reference assembled from 4 Overwatch voice lines. Clean, close recording; game character delivery.' \
  --form-string 'metadata={"character": "Cassidy", "dataset": "Cassidy", "source": "Overwatch wiki (Fandom)", "source_page": "Cassidy/Quotes", "source_revision": "381164", "source_url": "https://overwatch.fandom.com/wiki/Cassidy/Quotes", "reference_seconds": "13.91", "reference_clips": "cassidy__cassidy-not-our-finest-hour-but-we-can-still-make__eac6d2a4;cassidy__cassidy-we-just-need-to-win-one-more-round-no-prob__b385d8f7;cassidy__cassidy-we-can-t-afford-to-lose-another-one-everyo__b0708a39;cassidy__cassidy-hope-they-ve-packed-up-their-bags-for-when__1ddb7af2", "language": "en"}'
echo
