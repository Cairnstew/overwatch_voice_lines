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
            description = "Breeze-TTS reference pack for ${name}: reference.wav + reference.txt";
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
        in
        {
          default = cli;
        }
        // packs
        // packAliases
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
