# Breeze-TTS reference pack — Moira

A single reference clip and its exact transcript, ready to import into the
Breeze-TTS WebUI. The clip is assembled from 4 clean target-speaker
lines and is 14.94s long (Breeze recommends 5–15s).

## WebUI (manual, quickest)

1. Open the Breeze WebUI and switch to **VOICE CLONE**.
2. **REFERENCE AUDIO (WAV)** → choose `reference.wav`.
3. **REFERENCE TRANSCRIPT (EXACT)** → paste the contents of `reference.txt`.
4. Optionally type `Moira` in **SAVE AS** and a description, then press
   **SAVE VOICE**. It then appears in **VOICE LIBRARY**.

## HTTP / CLI

```bash
./import.sh http://127.0.0.1:8080
# or the server you use:
./import.sh https://server.tail685690.ts.net:8445
```

This uploads the WAV + transcript as a saved voice named `Moira`.

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

> Much lies in store. Let us see to it. More field research? Grand... I'll see this matter resolved. Humanity is shackled. I will find the key.

## Selected lines

| # | Section | Duration | Clip id | Text |
|---|---|---|---|---|
| 1 | Chatter | 3.40s | `moira__moira-much-lies-in-store-let-us-see-to-it__d115edbb` | Much lies in store. Let us see to it. |
| 2 | Chatter | 3.31s | `moira__moira-more-field-research-grand__7b3f661f` | More field research? Grand... |
| 3 | Chatter | 2.46s | `moira__moira-i-ll-see-this-matter-resolved__33179106` | I'll see this matter resolved. |
| 4 | Chatter | 4.33s | `moira__moira-humanity-is-shackled-i-will-find-the-key__ed9b5984` | Humanity is shackled. I will find the key. |

## Licence

The audio is © Blizzard Entertainment and is intended for personal research
and experimentation with voice cloning. It is not covered by this repository's
MIT licence. Do not redistribute it or use a cloned voice for impersonation,
harassment, or commercial purposes.
