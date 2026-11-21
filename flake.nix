{
  description = "Epic Games Launcher Debian binary packaged for NixOS";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { self, nixpkgs }: {
    packages.x86_64-linux =
      let
        pkgs = import nixpkgs { system = "x86_64-linux"; };
      in {
        epic-games-launcher = pkgs.callPackage ./package.nix { };
        default = self.packages.x86_64-linux.epic-games-launcher;
      };

    checks.x86_64-linux = {
      inherit (self.packages.x86_64-linux.default.tests) user-updates media-plugins;
    };

    nixosModules = {
      epic-games-launcher = import ./modules/nixos.nix;
      default = self.nixosModules.epic-games-launcher;
    };

    homeManagerModules = {
      epic-games-launcher = import ./modules/home-manager.nix;
      default = self.homeManagerModules.epic-games-launcher;
    };

    overlays.default = final: prev: {
      epic-games-launcher = final.callPackage ./package.nix { };
    };
  };
}
