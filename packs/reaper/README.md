# Breeze-TTS reference pack — Reaper

A single reference clip and its exact transcript, ready to import into the
Breeze-TTS WebUI. The clip is assembled from 4 clean target-speaker
lines and is 14.00s long (Breeze recommends 5–15s).

## WebUI (manual, quickest)

1. Open the Breeze WebUI and switch to **VOICE CLONE**.
2. **REFERENCE AUDIO (WAV)** → choose `reference.wav`.
3. **REFERENCE TRANSCRIPT (EXACT)** → paste the contents of `reference.txt`.
4. Optionally type `Reaper` in **SAVE AS** and a description, then press
   **SAVE VOICE**. It then appears in **VOICE LIBRARY**.

## HTTP / CLI

```bash
./import.sh http://127.0.0.1:8080
# or the server you use:
./import.sh https://server.tail685690.ts.net:8445
```

This uploads the WAV + transcript as a saved voice named `Reaper`.

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

> Let's try not to screw this up. Everything's going according to plan. Don't fail me. Or else. Screw up again and this is over.

## Selected lines

| # | Section | Duration | Clip id | Text |
|---|---|---|---|---|
| 1 | Chatter | 3.19s | `reaper__reaper-let-s-try-not-to-screw-this-up__17dfb28c` | Let's try not to screw this up. |
| 2 | Chatter | 3.20s | `reaper__reaper-everything-s-going-according-to-plan__dbf6e0d8` | Everything's going according to plan. |
| 3 | Chatter | 3.23s | `reaper__reaper-don-t-fail-me-or-else__528fa172` | Don't fail me. Or else. |
| 4 | Chatter | 2.93s | `reaper__reaper-screw-up-again-and-this-is-over__cf1b4afb` | Screw up again and this is over. |

## Licence

The audio is © Blizzard Entertainment and is intended for personal research
and experimentation with voice cloning. It is not covered by this repository's
MIT licence. Do not redistribute it or use a cloned voice for impersonation,
harassment, or commercial purposes.
