# Breeze reference packs

Each subdirectory is one ready-to-upload Breeze-TTS reference pack. The flake
exposes every directory here as a package automatically, named after the
directory:

```bash
nix build .#widowmaker
# result/reference.wav
# result/reference.txt
# result/voice.json
# result/import.sh
```

Add a new character by exporting a pack into this directory and committing it:

```bash
python -m overwatch_voice_lines export-breeze Ana --out packs/ana
git add packs/ana
```

No `flake.nix` edit is needed; `builtins.readDir ./packs` discovers it.

A pack must contain at least:

- `reference.wav` — mono 24 kHz 16-bit PCM, 5–15 seconds of clean speech
- `reference.txt` — the exact transcript of that wav

The extra `voice.json`, `import.sh`, and `README.md` written by
`export-breeze` are included so the package is directly usable.

## Licensing

The WAV files are Overwatch audio and remain © Blizzard Entertainment. They are
kept here so the flake can expose a reproducible reference pack for personal
research; they are **not** covered by the repository's MIT licence. Remove this
directory before redistributing the repository if you do not have the rights to
redistribute the clips.
