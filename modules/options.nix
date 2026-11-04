{ lib, pkgs, ... }:

{
  options.programs.epic-games-launcher = {
    enable = lib.mkEnableOption "Epic Games Launcher";

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.callPackage ../package.nix { };
      defaultText = lib.literalExpression "pkgs.callPackage ../package.nix { }";
      description = "Epic Games Launcher package to install.";
    };
  };
}
