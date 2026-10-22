# Breeze reference packs

Each subdirectory is one ready-to-upload Breeze-TTS reference pack. The flake
exposes every directory here as a package automatically, named after the
directory:

```bash
# WAV + transcript source pack
nix build .#widowmaker
# result/reference.wav
# result/reference.txt
# result/voice.json
# result/import.sh
# result/voice.breeze

# Encoded voice, one file named from voice.json
nix build .#widowmaker-voice
# result/Widowmaker.breeze
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
- `voice.json` — manifest; its `name` field becomes the `.breeze` filename
- `voice.breeze` — encoded voice loaded by a Breeze server

The extra `import.sh` and `README.md` written by `export-breeze` are included so
the package is directly usable.

## Encoding `voice.breeze`

The `.breeze` file is a small binary container (magic `BRZV`) holding the
reference codes, transcript, description and metadata. It is what a Breeze
server loads at startup, so shipping it avoids running the model or a server
round-trip in the consumer.

Generate it by saving the pack on a running Breeze server and copying the blob
back:

```bash
just encode-pack widowmaker https://server.tail685690.ts.net:8445 server
```

The recipe uploads `reference.wav` + `reference.txt` with `import.sh`, then
copies `<Name>.breeze` from `/var/lib/breeze-tts/voices/` over SSH. It reads the
name from `voice.json` and verifies the `BRZV` magic before finishing.

The committed Widowmaker blob was encoded with
`breeze-tts-2-q4_k.gguf`. The format is tied to the model family and codec, not
the quantisation: `q4_k` and `q8_0` blobs are compatible, but a different TTS
model requires regenerating every `.breeze` file. Keep `reference.wav` as the
regeneration source.

## Licensing

The WAV files and `.breeze` blobs are Overwatch audio or codes derived from it
and remain © Blizzard Entertainment. They are kept here so the flake can expose
a reproducible reference pack for personal research; they are **not** covered by
the repository's MIT licence. Remove this directory before redistributing the
repository if you do not have the rights to redistribute the clips.
