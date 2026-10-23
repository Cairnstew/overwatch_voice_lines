# Breeze-TTS reference pack — Mercy

A single reference clip and its exact transcript, ready to import into the
Breeze-TTS WebUI. The clip is assembled from 7 clean target-speaker
lines and is 13.61s long (Breeze recommends 5–15s).

## WebUI (manual, quickest)

1. Open the Breeze WebUI and switch to **VOICE CLONE**.
2. **REFERENCE AUDIO (WAV)** → choose `reference.wav`.
3. **REFERENCE TRANSCRIPT (EXACT)** → paste the contents of `reference.txt`.
4. Optionally type `Mercy` in **SAVE AS** and a description, then press
   **SAVE VOICE**. It then appears in **VOICE LIBRARY**.

## HTTP / CLI

```bash
./import.sh http://127.0.0.1:8080
# or the server you use:
./import.sh https://server.tail685690.ts.net:8445
```

This uploads the WAV + transcript as a saved voice named `Mercy`.

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

> Not to worry, I'll patch you up. I'll have you in top condition. I'll make sure that doesn't scar. This will just take a moment. Still in your back pocket. Ha! Feel stronger? Let me see what I can do.

## Selected lines

| # | Section | Duration | Clip id | Text |
|---|---|---|---|---|
| 1 | Abilities | 1.85s | `mercy__mercy-not-to-worry-i-ll-patch-you-up__9297fe32` | Not to worry, I'll patch you up. |
| 2 | Abilities | 1.66s | `mercy__mercy-i-ll-have-you-in-top-condition__36f18a54` | I'll have you in top condition. |
| 3 | Abilities | 1.60s | `mercy__mercy-i-ll-make-sure-that-doesn-t-scar__ae13cc95` | I'll make sure that doesn't scar. |
| 4 | Abilities | 1.53s | `mercy__mercy-this-will-just-take-a-moment__e441422a` | This will just take a moment. |
| 5 | Abilities | 1.54s | `mercy__mercy-still-in-your-back-pocket__b99329f7` | Still in your back pocket. |
| 6 | Abilities | 1.61s | `mercy__mercy-ha-feel-stronger__effc9c8f` | Ha! Feel stronger? |
| 7 | Abilities | 1.47s | `mercy__mercy-let-me-see-what-i-can-do__e7011d8d` | Let me see what I can do. |

## Licence

The audio is © Blizzard Entertainment and is intended for personal research
and experimentation with voice cloning. It is not covered by this repository's
MIT licence. Do not redistribute it or use a cloned voice for impersonation,
harassment, or commercial purposes.
