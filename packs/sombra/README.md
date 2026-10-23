# Breeze-TTS reference pack — Sombra

A single reference clip and its exact transcript, ready to import into the
Breeze-TTS WebUI. The clip is assembled from 4 clean target-speaker
lines and is 12.39s long (Breeze recommends 5–15s).

## WebUI (manual, quickest)

1. Open the Breeze WebUI and switch to **VOICE CLONE**.
2. **REFERENCE AUDIO (WAV)** → choose `reference.wav`.
3. **REFERENCE TRANSCRIPT (EXACT)** → paste the contents of `reference.txt`.
4. Optionally type `Sombra` in **SAVE AS** and a description, then press
   **SAVE VOICE**. It then appears in **VOICE LIBRARY**.

## HTTP / CLI

```bash
./import.sh http://127.0.0.1:8080
# or the server you use:
./import.sh https://server.tail685690.ts.net:8445
```

This uploads the WAV + transcript as a saved voice named `Sombra`.

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

> Easy in, easy out. Let's get the job done. Hm... I think I can make this worth my time. In my world, there are no secrets. I've had worse missions, but this is pretty bad.

## Selected lines

| # | Section | Duration | Clip id | Text |
|---|---|---|---|---|
| 1 | Chatter | 3.19s | `sombra__sombra-easy-in-easy-out-let-s-get-the-job-done__c2e3f796` | Easy in, easy out. Let's get the job done. |
| 2 | Chatter | 2.94s | `sombra__sombra-i-think-i-can-make-this-worth-my-time__cefd815a` | Hm... I think I can make this worth my time. |
| 3 | Chatter | 2.48s | `sombra__sombra-in-my-world-there-are-no-secrets__8336f406` | In my world, there are no secrets. |
| 4 | Chatter | 2.33s | `sombra__sombra-i-ve-had-worse-missions-but-this-is-pretty__19e264cf` | I've had worse missions, but this is pretty bad. |

## Licence

The audio is © Blizzard Entertainment and is intended for personal research
and experimentation with voice cloning. It is not covered by this repository's
MIT licence. Do not redistribute it or use a cloned voice for impersonation,
harassment, or commercial purposes.
