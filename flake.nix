{
  description = "Overwatch wiki voice-line scraper and voice-cloning dataset builder";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
      src = nixpkgs.lib.fileset.toSource {
        root = ./.;
        fileset = nixpkgs.lib.fileset.unions [
          ./pyproject.toml
          ./README.md
          ./overwatch_voice_lines
          ./packs
          ./tests
        ];
      };

      packDir = ./packs;
      packEntries = nixpkgs.lib.filterAttrs (_: type: type == "directory") (builtins.readDir packDir);

      # Each directory under ./packs is one character's ready-to-upload Breeze
      # reference pack. Keeping the pack as a normal source file makes the
      # resulting derivation pure and trivially fetchable from another flake.
      mkBreezePack =
        pkgs: name: path:
        pkgs.runCommand "${name}-breeze" {
          meta = {
            description = "Breeze-TTS reference pack for ${name}: reference.wav + reference.txt. Audio is © Blizzard; personal/research use only.";
            homepage = "https://github.com/Cairnstew/overwatch_voice_lines";
          };
        } ''
          mkdir -p $out
          cp -a ${path}/. $out/
        '';

      mkBreezePacks =
        pkgs:
        nixpkgs.lib.mapAttrs' (
          name: _: nixpkgs.lib.nameValuePair name (mkBreezePack pkgs name (packDir + "/${name}"))
        ) packEntries;

      # A .breeze file is the small, self-contained artifact a Breeze server
      # loads as a saved voice. The package exposes exactly one file, named from
      # voice.json, because the filename stem becomes the server-side voice id.
      mkEncodedVoice =
        pkgs: name: path:
        let
          manifest = builtins.fromJSON (builtins.readFile (path + "/voice.json"));
        in
        pkgs.runCommand "${name}-voice" {
          meta = {
            description = "Pre-encoded Breeze voice ${manifest.name}. Audio is © Blizzard; personal/research use only.";
            homepage = "https://github.com/Cairnstew/overwatch_voice_lines";
          };
        } ''
          mkdir -p $out
          test -s ${path}/voice.breeze
          cp ${path}/voice.breeze "$out/${manifest.name}.breeze"
        '';

      mkEncodedVoices =
        pkgs:
        nixpkgs.lib.mapAttrs' (
          name: _: nixpkgs.lib.nameValuePair "${name}-voice" (mkEncodedVoice pkgs name (packDir + "/${name}"))
        ) packEntries;

      mkEncodedVoiceCheck =
        pkgs: name: path: drv:
        let
          manifest = builtins.fromJSON (builtins.readFile (path + "/voice.json"));
        in
        pkgs.runCommand "${name}-voice-check" { } ''
          test "$(find ${drv} -maxdepth 1 -type f -name '*.breeze' | wc -l)" -eq 1
          test -f "${drv}/${manifest.name}.breeze"
          test "$(head -c 4 "${drv}/${manifest.name}.breeze")" = BRZV
          touch $out
        '';
    in
    {
      packages = forAllSystems (
        pkgs:
        let
          cli = pkgs.python3Packages.buildPythonApplication {
            pname = "overwatch-voice-lines";
            version = "0.1.0";
            pyproject = true;
            inherit src;

            build-system = [ pkgs.python3Packages.setuptools ];
            nativeCheckInputs = [ pkgs.python3Packages.pytestCheckHook ];
            pythonImportsCheck = [ "overwatch_voice_lines" ];

            # The CLI shells out to ffmpeg/ffprobe at prepare time.
            makeWrapperArgs = [
              "--prefix"
              "PATH"
              ":"
              (pkgs.lib.makeBinPath [ pkgs.ffmpeg ])
            ];

            meta = {
              description = "Download Overwatch voice lines and prepare a voice-cloning dataset";
              homepage = "https://github.com/Cairnstew/overwatch_voice_lines";
              license = pkgs.lib.licenses.mit;
              mainProgram = "overwatch-voice-lines";
            };
          };

          packs = mkBreezePacks pkgs;
          packAliases = nixpkgs.lib.mapAttrs' (
            name: drv: nixpkgs.lib.nameValuePair "${name}-breeze" drv
          ) packs;
          voices = mkEncodedVoices pkgs;
        in
        {
          default = cli;
        }
        // packs
        // packAliases
        // voices
      );

      checks = forAllSystems (
        pkgs:
        nixpkgs.lib.mapAttrs' (
          name: _:
          nixpkgs.lib.nameValuePair "${name}-voice" (
            mkEncodedVoiceCheck pkgs name (packDir + "/${name}") (mkEncodedVoice pkgs name (packDir + "/${name}"))
          )
        ) packEntries
      );

      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = with pkgs; [
            python3
            python3Packages.pytest
            python3Packages.ruff
            ffmpeg
            just
          ];
        };
      });

      formatter = forAllSystems (pkgs: pkgs.nixfmt);
    };
}
