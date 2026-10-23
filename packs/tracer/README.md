# Breeze-TTS reference pack — Tracer

A single reference clip and its exact transcript, ready to import into the
Breeze-TTS WebUI. The clip is assembled from 4 clean target-speaker
lines and is 13.79s long (Breeze recommends 5–15s).

## WebUI (manual, quickest)

1. Open the Breeze WebUI and switch to **VOICE CLONE**.
2. **REFERENCE AUDIO (WAV)** → choose `reference.wav`.
3. **REFERENCE TRANSCRIPT (EXACT)** → paste the contents of `reference.txt`.
4. Optionally type `Tracer` in **SAVE AS** and a description, then press
   **SAVE VOICE**. It then appears in **VOICE LIBRARY**.

## HTTP / CLI

```bash
./import.sh http://127.0.0.1:8080
# or the server you use:
./import.sh https://server.tail685690.ts.net:8445
```

This uploads the WAV + transcript as a saved voice named `Tracer`.

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

> I can't wait to get out there. Can you wait to get out there? Because I can't. Just need to win one more. We can manage that, right? Pre-mission checklist complete. Now it's time for the good bit. I've got a good feeling. This could be our best mission yet!

## Selected lines

| # | Section | Duration | Clip id | Text |
|---|---|---|---|---|
| 1 | Chatter | 3.10s | `tracer__tracer-i-can-t-wait-to-get-out-there-can-you-wait__07ed85fb` | I can't wait to get out there. Can you wait to get out there? Because I can't. |
| 2 | Chatter | 3.08s | `tracer__tracer-just-need-to-win-one-more-we-can-manage-tha__7b461c58` | Just need to win one more. We can manage that, right? |
| 3 | Chatter | 3.35s | `tracer__tracer-pre-mission-checklist-complete-now-it-s-tim__f0537d1e` | Pre-mission checklist complete. Now it's time for the good bit. |
| 4 | Chatter | 2.81s | `tracer__tracer-i-ve-got-a-good-feeling-this-could-be-our-b__3cfea1e9` | I've got a good feeling. This could be our best mission yet! |

## Licence

The audio is © Blizzard Entertainment and is intended for personal research
and experimentation with voice cloning. It is not covered by this repository's
MIT licence. Do not redistribute it or use a cloned voice for impersonation,
harassment, or commercial purposes.
