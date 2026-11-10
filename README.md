# Epic Games Launcher for NixOS

Packages the upstream x86_64 Linux Debian binary with Nix-provided GTK and
WebKit libraries. No Debian package manager is needed at runtime.
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

### Home Manager (one user)

Import the module in your Home Manager configuration:

```nix
imports = [ inputs.epic-games-launcher.homeManagerModules.default ];

programs.epic-games-launcher = {
  enable = true;
};
```

### NixOS (all users)

Import the module in your NixOS configuration:

```nix
imports = [ inputs.epic-games-launcher.nixosModules.default ];

programs.epic-games-launcher = {
  enable = true;
};
```

The NixOS module installs the package system-wide. The Home Manager module
installs it for one user.

Both modules expose the same options:

| Option           | Default                   | Behavior                                         |
|------------------|---------------------------|--------------------------------------------------|
| `enable`         | `false`                   | Install Epic Games Launcher.                     |
| `package`        | This repository's package | Override the installed package.                  |

The modules use your Nixpkgs unfree policy. Allow this package, for example:

```nix
nixpkgs.config.allowUnfreePredicate = pkg:
  builtins.elem (lib.getName pkg) [ "epic-games-launcher" ];
```

Add it to your existing predicate if you already have one. With Home Manager's
`useGlobalPkgs`, configure this in NixOS. Alternatively, set `package` to
`inputs.epic-games-launcher.packages.${pkgs.stdenv.hostPlatform.system}.default`,
which already permits this specific unfree package.

### Package only

```nix
home.packages = [
  inputs.epic-games-launcher.packages.${pkgs.stdenv.hostPlatform.system}.default
];
```

You can also apply `inputs.epic-games-launcher.overlays.default` and install
`pkgs.epic-games-launcher`, or load the package directly with
`pkgs.callPackage ./package.nix { }`.

## Update

The launcher is installed in the read-only Nix store. Its built-in self-updater
is disabled with `EGL_DISABLE_SELF_UPDATE=1`; launcher updates go through Nix.
This package does not keep a writable per-user launcher installation like Steam.
Game downloads and updates remain managed by the launcher.

The upstream URL serves the latest Debian package rather than an immutable release.
The SHA-256 hash pins the downloaded bytes; a changed download fails verification
until the package is deliberately updated. Old snapshots may stop being available
from upstream unless already cached.

To download and hash the current release:

```sh
nix store prefetch-file --json \
  'https://launcher-public-service-prod06.ol.epicgames.com/launcher/api/installer/download/EpicGamesLauncher-x86_64.deb'
```

Update `version` and `src.hash` in `package.nix`, then run `nix build` and check
that the launcher opens. Consumers must update their launcher flake input and
rebuild their NixOS or Home Manager configuration to install the new package.
Update Nixpkgs separately with `nix flake update nixpkgs`.

Desktop integration declares `com.epicgames.launcher` URLs. Selecting a default
handler remains a desktop or Home Manager setting.
