{
  description = "Xliner's CLI Framework";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    systems.url = "github:nix-systems/x86_64-linux";
    flake-utils = {
      url = "github:numtide/flake-utils";
      inputs.systems.follows = "systems";
    };
  };

  outputs = {
    nixpkgs,
    flake-utils,
    ...
  }: flake-utils.lib.eachDefaultSystem (system: let
    pkgs = nixpkgs.legacyPackages.${system};
    pypkgs = pkgs.python314Packages;
    pname = "xclif";
    version = "0.6.2";
    xclif = pypkgs.buildPythonPackage {
      inherit
        pname
        version;
      pyproject = true;

      src = ./.;

      build-system = with pypkgs; [
        hatchling
      ];

      dependencies = with pypkgs; [
        platformdirs
        rich
        tomlkit
        # click
        # mcp
        # pytest
        # pytest-cov
        # typer
      ];

      doCheck = true;
      nativeCheckInputs = with pypkgs; [
        pytestCheckHook
      ];

      meta = {
        description = "Xliner's CLI Framework";
        homepage = "https://github.com/ThatXliner/xclif";
        license = pkgs.lib.licenses.mit;
        maintainers = [ ];
      };
    };
  in {
    devShells.default = pkgs.mkShell {
      packages = with pkgs; [
        python312
        uv
        just
      ];
    };

    packages.default = xclif;

    apps.default = flake-utils.lib.mkApp {
      drv = xclif;
    };
  });
}
