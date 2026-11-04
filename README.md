# Epic Games Launcher for NixOS

Packages the upstream x86_64 Linux AppImage with `appimageTools.wrapType2`.
Includes the desktop entry, Epic launcher URI handler declaration, and icons.
The software is proprietary; this repository contains the packaging only.

## Build and run

Run directly from GitHub:

```sh
nix run github:eduhoribe/nix-epic-games-launcher
```

Or clone the repository to build and run locally:

```sh
git clone https://github.com/eduhoribe/nix-epic-games-launcher.git
cd nix-epic-games-launcher
nix build
nix run
```

Only `x86_64-linux` is supported. The flake permits this specific unfree package.
When using `package.nix` or the overlay with your own Nixpkgs instance, allow
`epic-games-launcher` in your unfree package policy.

## Use from another flake

Add this repository as an input:

```nix
inputs.epic-games-launcher = {
  url = "github:eduhoribe/nix-epic-games-launcher";
  inputs.nixpkgs.follows = "nixpkgs";
};
```

Install its package in Home Manager:

```nix
home.packages = [
  inputs.epic-games-launcher.packages.${pkgs.stdenv.hostPlatform.system}.default
];
```

Alternatively, apply `inputs.epic-games-launcher.overlays.default` and install
`pkgs.epic-games-launcher`. The reusable package file can also be loaded with
`pkgs.callPackage ./package.nix { }`.

## Update

The upstream URL serves the latest AppImage rather than an immutable release.
The SHA-256 hash pins the downloaded bytes; a changed download fails verification
until the package is deliberately updated. Old snapshots may stop being available
from upstream unless already cached.

To download and hash the current release:

```sh
nix store prefetch-file --json \
  'https://launcher-public-service-prod06.ol.epicgames.com/launcher/api/installer/download/EpicGamesLauncher-x86_64.AppImage'
```

Update `version` and `src.hash` in `package.nix`, then run `nix build` and check
that the launcher opens. Update Nixpkgs separately with `nix flake update nixpkgs`.

Desktop integration declares `com.epicgames.launcher` URLs. Selecting a default
handler remains a desktop or Home Manager setting. Upstream currently forces
GTK's X11 backend, so Wayland sessions need XWayland.
