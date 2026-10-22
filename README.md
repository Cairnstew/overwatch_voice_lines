# overwatch-voice-lines

Turn an Overwatch wiki quotes page into a clean, transcript-aligned audio
dataset for voice cloning.

Starting from a page such as
<https://overwatch.fandom.com/wiki/Widowmaker/Quotes>, the tool:

1. fetches the page's **wikitext** through the MediaWiki API (the normal HTML
   page is behind a bot filter),
2. parses every quote table into one record per `{{Audio|...}}` player, keeping
   the ability/skin/interaction context and the French/English translations,
3. downloads the original ogg/mp3/wav files, and
4. converts each clip to **mono 24 kHz 16-bit PCM wav** with EBU R128 loudness
   normalisation, then writes metadata, deterministic train/val splits and a
   dataset card.

The result is ready for XTTS/GPT-SoVITS/RVC-style pipelines that want
`audio + transcript + a stable split`, with no manual copy-pasting.

## Requirements

- Python **3.11+**
- `ffmpeg` and `ffprobe` on `PATH` (only needed for `prepare`/`build`)

No Python packages are required at runtime beyond the standard library.

```bash
# Nix (recommended in this repo)
nix develop            # python + pytest + ruff + ffmpeg

# or any environment with ffmpeg installed
python -m pip install -e .
```

## Quick start

```bash
# 1. Inspect what the page contains (metadata only, no audio)
ovl fetch Widowmaker

# 2. Fetch, download and prepare everything
ovl build Widowmaker
```

Output lands in `data/widowmaker/`:

| Path | Contents |
|---|---|
| `quotes.jsonl` | Every parsed utterance, including files that are missing |
| `raw/` | Original wiki audio (`ogg`, `mp3`, `wav`), cached by file name |
| `wav/` | Prepared mono wav clips, named by clip id |
| `metadata.jsonl` | One JSON object per prepared clip |
| `metadata.csv` | The same table as CSV |
| `splits/train.jsonl`, `splits/val.jsonl` | Deterministic train/validation split |
| `dataset_card.md` | Human-readable summary, counts and licence notes |
| `report.json` | Parse/download/prepare counts, warnings and failures |
| `breeze/` | Optional Breeze-TTS WebUI reference pack (see below) |

Resume at any stage:

```bash
ovl download Widowmaker     # uses quotes.jsonl, skips cached files
ovl prepare Widowmaker      # re-converts, e.g. after changing --sample-rate
ovl stats Widowmaker
```

## Using it

```bash
# A hero name expands to "<name>/Quotes"
ovl build Widowmaker
ovl build Ana Tracer Reinhardt

# An explicit page, with a dataset name
ovl build 'Widowmaker/Quotes' --name 'Widowmaker (current)'

# Smoke-test without downloading the whole page
ovl build Widowmaker --limit 10

# Keep other heroes' lines from interaction tables too
ovl build Widowmaker --speakers all

# Different model requirements
ovl build Widowmaker --sample-rate 22050 --val-fraction 0.05
```

### Breeze-TTS WebUI reference pack

Breeze clones from **one reference WAV plus its exact transcript**, not from a
whole training folder. `export-breeze` assembles a 5–15 second reference from
the cleanest target-speaker lines in a prepared dataset, writes the matching
transcript, and adds a one-command upload script:

```bash
# After `ovl build Widowmaker`
ovl export-breeze Widowmaker

# Or upload straight to a running server (creates a saved voice)
ovl export-breeze Widowmaker --server https://server.tail685690.ts.net:8445
```

It writes `data/widowmaker/breeze/`:

| File | Purpose |
|---|---|
| `reference.wav` | Mono 24 kHz 16-bit PCM reference clip |
| `reference.txt` | Exact transcript of that clip |
| `voice.json` | Manifest: selected clips, durations, source revision |
| `import.sh` | `POST /v1/voices` upload (WAV + transcript + metadata) |
| `README.md` | WebUI instructions and the selected-line table |

In the WebUI, open **Voice Clone**, choose `reference.wav` as
**Reference Audio**, paste `reference.txt` into **Reference Transcript**, then
optionally set **Save As** and press **Save Voice**. The voice then appears in
the **Voice Library**. For the HTTP route:

```bash
data/widowmaker/breeze/import.sh https://server.tail685690.ts.net:8445
```

Selection is deterministic: it prefers `Voice Lines`/`Chatter`/`Abilities`,
clips around three seconds, English verbal lines, and skips stage directions,
non-verbal sounds, duplicates and other languages. Tune it with
`--target-seconds` (default 10), `--min-clip-seconds` / `--max-clip-seconds`, or
`--language all`; use `--out DIR` to choose a different pack directory.

### Flake packages: wav + transcript + encoded voice

Ready-to-use packs live under `packs/<character>/` and are exposed as flake
packages. Each pack carries both the regeneration source and the encoded
Breeze voice:

| Output | Contents |
|---|---|
| `<character>` | `reference.wav`, `reference.txt`, `voice.json`, `import.sh`, `voice.breeze` |
| `<character>-breeze` | alias for `<character>` (WAV pack) |
| `<character>-voice` | one file, `<Name>.breeze`, named from `voice.json` |

```bash
# WAV + transcript source pack
nix build .#widowmaker
ls result/reference.wav result/reference.txt result/voice.breeze

# Encoded voice for a Breeze server
nix build .#widowmaker-voice
ls result/Widowmaker.breeze

# From another machine or flake
nix build github:Cairnstew/overwatch_voice_lines#widowmaker-voice
```

The `<character>-voice` package is the small artifact a Breeze server loads as
a saved voice. Its filename stem becomes the voice id, so it is emitted as
`Widowmaker.breeze` rather than `voice.breeze`.

Use either form from another flake:

```nix
{
  inputs.overwatch-voice-lines.url = "github:Cairnstew/overwatch_voice_lines";

  outputs = { self, nixpkgs, overwatch-voice-lines }: {
    # ...
    # Inside a NixOS/home-manager module:
    environment.etc."breeze/widowmaker".source =
      overwatch-voice-lines.packages.${pkgs.system}.widowmaker;

    environment.etc."breeze/voices/Widowmaker.breeze".source =
      "${overwatch-voice-lines.packages.${pkgs.system}.widowmaker-voice}/Widowmaker.breeze";
  };
}
```

`widowmaker` gives `/etc/breeze/widowmaker/reference.wav` and
`reference.txt`, while `widowmaker-voice` gives the pre-encoded
`Widowmaker.breeze`. The encoded blob carries the transcript, description and
metadata, so a consumer does not need to run the model or upload a WAV at
activation time.

The committed Widowmaker blob was encoded with
`breeze-tts-2-q4_k.gguf`. The format is tied to the model family and codec, not
the quantisation: `q4_k` and `q8_0` are compatible, but a different TTS model
requires regenerating every `.breeze` file. Keep `reference.wav` as the
regeneration source.

To add a character, build its dataset, export a pack, and encode it:

```bash
ovl build Ana
ovl export-breeze Ana --out packs/ana
just encode-pack ana https://server.tail685690.ts.net:8445 server
git add packs/ana && git commit -m "add Ana Breeze reference pack"
```

Every subdirectory of `packs/` is discovered automatically, so adding
`packs/ana/` publishes `ana` and `ana-voice` without changing `flake.nix`. The
pack is a normal Nix source path, so the derivation stays pure and remote
fetching does not need network access at build time.

### Options

| Option | Default | Meaning |
|---|---|---|
| `--data-dir` | `data` | Dataset root |
| `--cache-dir` | `.cache/ovl` | Cached API JSON responses |
| `--refresh` | off | Ignore the API cache and re-fetch |
| `--sample-rate` | `24000` | Output wav sample rate |
| `--val-fraction` | `0.1` | Validation share; `0` disables splits |
| `--speakers` | `target` | Keep only the page's hero, or `all` speakers |
| `--include-nonverbal` | off | Keep grunts/gasps in the dataset |
| `--min-duration` / `--max-duration` | `0.25` / `60` | Duration filter in seconds |
| `--no-normalize` | off | Skip EBU R128 loudness normalisation |
| `--trim-silence` | off | Trim leading/trailing silence |
| `--limit` | — | Only process the first N parsed utterances |
| `--force` | off | Re-download and re-convert everything |
| `--target-seconds` | `10` | Breeze reference speech target (5–15 s) |
| `--language` | `en` | Breeze reference language (`all` to mix) |
| `--server` | — | Upload the Breeze pack to this server after writing it |
| `--save-name` | dataset name | Saved-voice name for `--server` |
| `--out` | `<dataset>/breeze` | Breeze pack directory (single page only) |

The last five options (`--target-seconds` through `--out`) apply only to
`export-breeze`.

## What the metadata looks like

Each line of `metadata.jsonl` (and row of `metadata.csv`) contains:

```json
{
  "id": "widowmaker__widowmaker-dont-be-shy__c0ffee12",
  "character": "Widowmaker",
  "speaker": "Widowmaker",
  "section": "Abilities",
  "context": "Widow's Kiss / Scoped",
  "text": "Don't be shy.",
  "translation": "",
  "language": "en",
  "verbal": true,
  "audio_file": "Widowmaker - Don't be shy.ogg",
  "wav_path": "wav/widowmaker__widowmaker-dont-be-shy__c0ffee12.wav",
  "raw_path": "raw/6f2c1a9b3e_widowmaker-dont-be-shy.ogg",
  "duration_s": 1.62,
  "sample_rate": 24000,
  "sha256": "...",
  "source_page": "Widowmaker/Quotes",
  "source_url": "https://overwatch.fandom.com/wiki/Widowmaker"
}
```

Paths are relative to the dataset directory, so the folder can be moved or
mounted into a training container unchanged.

### Text choices that matter for cloning

- **Translated quotes use the spoken language as `text`.** For
  `{{QuoteTranslation|quote=Cible repérée.|translation=Target detected.}}` the
  wav is French, so `text` is `"Cible repérée."`, `translation` is
  `"Target detected."` and `language` is `fr`. Training on the English
  translation would teach the model the wrong phonemes.
- **Interactions are speaker-aware.** Each bullet line is paired with its own
  audio file. A clip containing several speakers in one file is labelled
  `Ana + Widowmaker` and excluded by the default `--speakers target` filter.
- **Non-verbal clips are skipped by default.** `*grunts*` becomes
  `text="grunts"`, `verbal=false`; pass `--include-nonverbal` to keep those
  clips in the dataset (and therefore in the splits).
- **Splits are grouped by text.** The assignment is a hash of the normalised
  text (and speaker), so identical lines never leak between train and
  validation and rebuilding does not reshuffle the split.
- **Duplicates are dropped.** If two wiki files decode to the same bytes, only
  the first becomes a clip; the count is reported in `report.json`.

## Missing files and wiki quirks

Some rows reference audio that was never uploaded (for example
`Widowmaker - .ogg` or a few `(jumping grunt)` files). These are written to
`quotes.jsonl` with `"missing": true`, listed in `report.json`, and skipped by
`download`/`prepare` rather than aborting the run.

Historical pages are less reliable: `Widowmaker/Quotes/Overwatch 1` currently
points at datamined file names that have been deleted from the wiki, so only a
handful of its clips still resolve. Use the main `<Hero>/Quotes` pages unless
you specifically need the old page; `report.json` always shows what was
missing before a build.

The parser handles the shapes actually used by the wiki, including:

- header attribute cells (`! width="20%" | Audio`),
- `rowspan` context cells (ability, skin, availability, interaction partner),
- several players in one cell (`{{Audio|a.ogg}} {{Audio|b.ogg}}`),
- inline `||` cells and the `|- dth="10%" | Audio` typo found on some pages,
- `{{Audio|file.ogg|frameless}}` and `{{Audio|file.ogg|link=}}` parameters,
- `.ogg`, `.mp3` and `.wav` files, and
- multi-line interaction bullets with `*`/`**` alternatives and italic table
  notes (`''One of three:''`).

## Adding more characters

The page and character are independent: pass any `<Hero>/Quotes` page. New
characters need no code changes. If a page uses a new template shape, add a
small fixture to `tests/` and extend `overwatch_voice_lines/wikitext.py`.

To refresh a dataset after the wiki changes, delete `quotes.jsonl` (or pass
`--refresh`) and re-run `build`. Cached raw audio is reused.

## Voice cloning notes

- The default 24 kHz mono output suits XTTS-v2/GPT-SoVITS-style training. Use
  `--sample-rate 40000` or `48000` for RVC.
- Loudness normalisation targets `-16 LUFS`, true peak `-1.5 dBTP`. Disable it
  with `--no-normalize` if your pipeline normalises again.
- `dataset_card.md` records the source revision and counts so experiments are
  reproducible.
- The dry, in-character delivery means some clips are very short. Keep the
  0.25 s floor unless you are deliberately training on effort sounds.
- For Breeze-TTS, `export-breeze` deliberately uses 5–15 seconds of speech.
  Longer references can make the model skip sentences, while very short ones
  give it too little timbre information.

## Licence and responsible use

The code is MIT licensed. Overwatch audio and character voices are **© Blizzard
Entertainment**; wiki text is available under CC BY-SA, see each source page
for attribution.

A short Breeze reference pack is checked in under `packs/` solely so the flake
can expose it as a reproducible package. It is personal/research material, not
MIT-licensed content. Do not redistribute those clips unless you have the
rights to do so, and do not use a cloned voice for impersonation, harassment,
or commercial purposes. Respect Blizzard's terms and the rights of the
original voice actors.

## Development

```bash
nix develop
pytest -q
ruff check .

# optional: hit the real API (network)
pytest -q -m live
```

The default test suite is fully offline: fixtures cover the table parser,
language inference, file-name resolution, and dataset filtering/splitting.
