{
  description = "Prism - Universal Batch Runner, Multi-Backend Export Engine & Live-Reloading Preview Server for Python Plotting Scripts";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    rime = {
      url = "github:SpanishSyntax/Rime";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    rime,
  }: let
    systems = flake-utils.lib.defaultSystems;
  in
    flake-utils.lib.eachSystem systems (system: let
      pkgs = import nixpkgs {
        inherit system;
        overlays = [rime.overlays.default];
      };
      lib = pkgs.lib;

      prismPackage = pkgs.python3Packages.buildPythonApplication {
        pname = "prism";
        version = "0.1.0";
        src = ./.;
        pyproject = true;

        build-system = [
          pkgs.python3Packages.setuptools
        ];

        propagatedBuildInputs = [
          pkgs.python3Packages.rime
        ];

        nativeCheckInputs = [
          pkgs.python3Packages.pytest
        ];

        doCheck = false;

        meta = with lib; {
          description = "Batch runner, multi-backend export engine, and live-reloading preview server for Python plotting scripts";
          homepage = "https://github.com/SpanishSyntax/Prism";
          license = licenses.mit;
          mainProgram = "prism";
        };
      };
    in {
      packages = {
        default = prismPackage;
        prism = prismPackage;
      };

      apps = {
        default = {
          type = "app";
          program = "${prismPackage}/bin/prism";
        };
        prism = {
          type = "app";
          program = "${prismPackage}/bin/prism";
        };
      };

      devShells.default = pkgs.mkShell {
        packages = with pkgs; [
          python3
          python3Packages.setuptools
          python3Packages.pytest
          python3Packages.rime
        ];
      };
    })
    // {
      overlays = {
        default = final: prev: {
          prism = self.packages.${prev.stdenv.hostPlatform.system}.default;
        };
        prism = self.overlays.default;
      };

      nixosModules = {
        default = self.nixosModules.prism;
        prism = {
          config,
          lib,
          pkgs,
          ...
        }: let
          cfg = config.programs.prism;
          system = pkgs.stdenv.hostPlatform.system;
        in {
          options.programs.prism = {
            enable = lib.mkEnableOption "Prism - Python plotting runner, exporter & preview server";
            package = lib.mkOption {
              type = lib.types.package;
              default = self.packages.${system}.default;
              description = "The Prism package to install system-wide.";
            };
          };
          config = lib.mkIf cfg.enable {
            environment.systemPackages = [cfg.package];
          };
        };
      };

      homeManagerModules = {
        default = self.homeManagerModules.prism;
        prism = {
          config,
          lib,
          pkgs,
          ...
        }: let
          cfg = config.programs.prism;
          tomlFormat = pkgs.formats.toml {};
          system = pkgs.stdenv.hostPlatform.system;
          defaultPrism = self.packages.${system}.default;
        in {
          options.programs.prism = {
            enable = lib.mkEnableOption "Prism - Python plotting runner, exporter & preview server";

            package = lib.mkOption {
              type = lib.types.package;
              default = defaultPrism;
              description = "The Prism package to use.";
            };

            settings = lib.mkOption {
              type = tomlFormat.type;
              default = {};
              description = "Configuration written to ~/.config/prism/prism.toml.";
            };
          };

          config = lib.mkIf cfg.enable {
            home.packages = [cfg.package];
            xdg.configFile."prism/prism.toml" = lib.mkIf (cfg.settings != {}) {
              source = tomlFormat.generate "prism.toml" cfg.settings;
            };
          };
        };
      };
    };
}
