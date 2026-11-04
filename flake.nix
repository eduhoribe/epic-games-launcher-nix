{
  description = "Epic Games Launcher AppImage packaged for NixOS";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { self, nixpkgs }: {
    packages.x86_64-linux =
      let
        pkgs = import nixpkgs {
          system = "x86_64-linux";
          config.allowUnfreePredicate = pkg:
            nixpkgs.lib.getName pkg == "epic-games-launcher";
        };
      in {
        epic-games-launcher = pkgs.callPackage ./package.nix { };
        default = self.packages.x86_64-linux.epic-games-launcher;
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
