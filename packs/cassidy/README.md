# Breeze-TTS reference pack — Cassidy

A single reference clip and its exact transcript, ready to import into the
Breeze-TTS WebUI. The clip is assembled from 4 clean target-speaker
lines and is 13.91s long (Breeze recommends 5–15s).

## WebUI (manual, quickest)

1. Open the Breeze WebUI and switch to **VOICE CLONE**.
2. **REFERENCE AUDIO (WAV)** → choose `reference.wav`.
3. **REFERENCE TRANSCRIPT (EXACT)** → paste the contents of `reference.txt`.
4. Optionally type `Cassidy` in **SAVE AS** and a description, then press
   **SAVE VOICE**. It then appears in **VOICE LIBRARY**.

## HTTP / CLI

```bash
./import.sh http://127.0.0.1:8080
# or the server you use:
./import.sh https://server.tail685690.ts.net:8445
```

This uploads the WAV + transcript as a saved voice named `Cassidy`.

## Files

| File | Purpose |
|---|---|
| `reference.wav` | Mono 24 kHz 16-bit PCM reference clip |
| `reference.txt` | Exact transcript of `reference.wav` |
| `voice.json` | Manifest with provenance and the selected lines |
| `voice.breeze` | Optional encoded voice added by `just encode-pack` |
| `import.sh` | One-command `POST /v1/voices` upload |
| `README.md` | This file |

To produce the small `.breeze` blob used by a Breeze server, run:

```bash
just encode-pack <character> <server-url> <ssh-host>
```

See `packs/README.md` for the model-family compatibility caveat.

## Transcript

> Not our finest hour, but we can still make it right. We just need to win one more round. No problem. We can't afford to lose another one. Everyone, buckle up. Hope they've packed up their bags for when we drive 'em out.

## Selected lines

| # | Section | Duration | Clip id | Text |
|---|---|---|---|---|
| 1 | Chatter | 3.19s | `cassidy__cassidy-not-our-finest-hour-but-we-can-still-make__eac6d2a4` | Not our finest hour, but we can still make it right. |
| 2 | Chatter | 3.21s | `cassidy__cassidy-we-just-need-to-win-one-more-round-no-prob__b385d8f7` | We just need to win one more round. No problem. |
| 3 | Chatter | 3.03s | `cassidy__cassidy-we-can-t-afford-to-lose-another-one-everyo__b0708a39` | We can't afford to lose another one. Everyone, buckle up. |
| 4 | Chatter | 3.02s | `cassidy__cassidy-hope-they-ve-packed-up-their-bags-for-when__1ddb7af2` | Hope they've packed up their bags for when we drive 'em out. |

## Licence

The audio is © Blizzard Entertainment and is intended for personal research
and experimentation with voice cloning. It is not covered by this repository's
MIT licence. Do not redistribute it or use a cloned voice for impersonation,
harassment, or commercial purposes.
