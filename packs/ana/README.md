# Breeze-TTS reference pack — Ana

A single reference clip and its exact transcript, ready to import into the
Breeze-TTS WebUI. The clip is assembled from 5 clean target-speaker
lines and is 12.31s long (Breeze recommends 5–15s).

## WebUI (manual, quickest)

1. Open the Breeze WebUI and switch to **VOICE CLONE**.
2. **REFERENCE AUDIO (WAV)** → choose `reference.wav`.
3. **REFERENCE TRANSCRIPT (EXACT)** → paste the contents of `reference.txt`.
4. Optionally type `Ana` in **SAVE AS** and a description, then press
   **SAVE VOICE**. It then appears in **VOICE LIBRARY**.

## HTTP / CLI

```bash
./import.sh http://127.0.0.1:8080
# or the server you use:
./import.sh https://server.tail685690.ts.net:8445
```

This uploads the WAV + transcript as a saved voice named `Ana`.

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

> Reloading. I can't heal right now. It's just a scratch. You'll be fine. I've seen worse. You're going to live. Enough whining. You're fine. Let me reload. Just a moment.

## Selected lines

| # | Section | Duration | Clip id | Text |
|---|---|---|---|---|
| 1 | Abilities | 2.52s | `ana__ana-reloading-i-can-t-heal-right-now__1a63b986` | Reloading. I can't heal right now. |
| 2 | Abilities | 2.10s | `ana__ana-it-s-just-a-scratch-you-ll-be-fine__765566d7` | It's just a scratch. You'll be fine. |
| 3 | Abilities | 2.07s | `ana__ana-i-ve-seen-worse-you-re-going-to-live__f03cf2c5` | I've seen worse. You're going to live. |
| 4 | Abilities | 2.10s | `ana__ana-enough-whining-you-re-fine__9e72e7d5` | Enough whining. You're fine. |
| 5 | Abilities | 1.77s | `ana__ana-let-me-reload-just-a-moment__9d9aad22` | Let me reload. Just a moment. |

## Licence

The audio is © Blizzard Entertainment and is intended for personal research
and experimentation with voice cloning. It is not covered by this repository's
MIT licence. Do not redistribute it or use a cloned voice for impersonation,
harassment, or commercial purposes.
