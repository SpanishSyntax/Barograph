{
  description = "Barograph - Universal Batch Runner & Multi-Backend Export Engine for Python Plotting Scripts";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    prism = {
      url = "github:SpanishSyntax/Prism";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    prism,
  }: let
    systems = flake-utils.lib.defaultSystems;
  in
    flake-utils.lib.eachSystem systems (system: let
      pkgs = import nixpkgs {
        inherit system;
        overlays = [prism.overlays.default];
      };
      lib = pkgs.lib;

      barographPackage = pkgs.python3Packages.buildPythonApplication {
        pname = "barograph";
        version = "0.1.0";
        src = lib.cleanSource ./.;
        pyproject = true;

        build-system = [
          pkgs.python3Packages.setuptools
        ];

        propagatedBuildInputs = [
          pkgs.python3Packages.prism
        ];

        nativeCheckInputs = [
          pkgs.python3Packages.pytest
        ];

        doCheck = false;

        meta = with lib; {
          description = "Pure, fast figure extraction and multi-backend batch export engine for Python plotting scripts";
          homepage = "https://github.com/SpanishSyntax/Barograph";
          license = licenses.mit;
          mainProgram = "barograph";
        };
      };
    in {
      packages = {
        default = barographPackage;
        barograph = barographPackage;
      };

      apps = {
        default = {
          type = "app";
          program = "${barographPackage}/bin/barograph";
        };
        barograph = {
          type = "app";
          program = "${barographPackage}/bin/barograph";
        };
      };

      devShells.default = pkgs.mkShell {
        packages = [
          (pkgs.python3.withPackages (ps: [
            ps.setuptools
            ps.pytest
            ps.prism
            ps.plotly
            ps.matplotlib
            ps.kaleido
            ps.numpy
          ]))
        ];
      };
    })
    // {
      overlays = {
        default = final: prev: {
          barograph = self.packages.${prev.stdenv.hostPlatform.system}.default;
        };
        barograph = self.overlays.default;
      };

      nixosModules = {
        default = self.nixosModules.barograph;
        barograph = {
          config,
          lib,
          pkgs,
          ...
        }: let
          cfg = config.programs.barograph;
          system = pkgs.stdenv.hostPlatform.system;
        in {
          options.programs.barograph = {
            enable = lib.mkEnableOption "Barograph - Python plotting runner & export engine";
            package = lib.mkOption {
              type = lib.types.package;
              default = self.packages.${system}.default;
              description = "The Barograph package to install system-wide.";
            };
          };
          config = lib.mkIf cfg.enable {
            environment.systemPackages = [cfg.package];
          };
        };
      };

      homeManagerModules = {
        default = self.homeManagerModules.barograph;
        barograph = {
          config,
          lib,
          pkgs,
          ...
        }: let
          cfg = config.programs.barograph;
          tomlFormat = pkgs.formats.toml {};
          system = pkgs.stdenv.hostPlatform.system;
          defaultBarograph = self.packages.${system}.default;
        in {
          options.programs.barograph = {
            enable = lib.mkEnableOption "Barograph - Python plotting runner & export engine";

            package = lib.mkOption {
              type = lib.types.package;
              default = defaultBarograph;
              description = "The Barograph package to use.";
            };

            settings = lib.mkOption {
              type = tomlFormat.type;
              default = {};
              description = "Configuration written to ~/.config/barograph/barograph.toml.";
            };
          };

          config = lib.mkIf cfg.enable {
            home.packages = [cfg.package];
            xdg.configFile."barograph/barograph.toml" = lib.mkIf (cfg.settings != {}) {
              source = tomlFormat.generate "barograph.toml" cfg.settings;
            };
          };
        };
      };
    };
}
