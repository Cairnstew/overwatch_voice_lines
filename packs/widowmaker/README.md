# Breeze-TTS reference pack — Widowmaker

A single reference clip and its exact transcript, ready to import into the
Breeze-TTS WebUI. The clip is assembled from 3 clean target-speaker
lines and is 11.17s long (Breeze recommends 5–15s).

## WebUI (manual, quickest)

1. Open the Breeze WebUI and switch to **VOICE CLONE**.
2. **REFERENCE AUDIO (WAV)** → choose `reference.wav`.
3. **REFERENCE TRANSCRIPT (EXACT)** → paste the contents of `reference.txt`.
4. Optionally type `Widowmaker` in **SAVE AS** and a description, then press
   **SAVE VOICE**. It then appears in **VOICE LIBRARY**.

## HTTP / CLI

```bash
./import.sh http://127.0.0.1:8080
# or the server you use:
./import.sh https://server.tail685690.ts.net:8445
```

This uploads the WAV + transcript as a saved voice named `Widowmaker`.

To encode the compact `.breeze` artifact used by the server:

```bash
just encode-pack widowmaker https://server.tail685690.ts.net:8445 server
```

## Files

| File | Purpose |
|---|---|
| `reference.wav` | Mono 24 kHz 16-bit PCM reference clip |
| `reference.txt` | Exact transcript of `reference.wav` |
| `voice.json` | Manifest with provenance and the selected lines |
| `voice.breeze` | Encoded voice for a Breeze server (magic `BRZV`) |
| `import.sh` | One-command `POST /v1/voices` upload |
| `README.md` | This file |

## Transcript

> The Countess was feared by all. Rightfully. A single death can change everything. The performance is about to begin.

## Selected lines

| # | Section | Duration | Clip id | Text |
|---|---|---|---|---|
| 1 | Voice Lines | 3.39s | `widowmaker__widowmaker-the-countess-was-feared-by-all-rightful__3dfb8323` | The Countess was feared by all. Rightfully. |
| 2 | Voice Lines | 3.00s | `widowmaker__widowmaker-a-single-death-can-change-everything__208419e3` | A single death can change everything. |
| 3 | Voice Lines | 3.63s | `widowmaker__widowmaker-the-performance-is-about-to-begin__50feaab1` | The performance is about to begin. |

## Licence

The audio and the derived `.breeze` codes are © Blizzard Entertainment and are
intended for personal research and experimentation with voice cloning. They are
not covered by the repository's MIT licence. Do not redistribute them or use a
cloned voice for impersonation, harassment, or commercial purposes.
