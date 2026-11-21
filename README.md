# Epic Games Launcher for NixOS

Bootstraps the upstream x86_64 Linux Debian binary and runs it in a Nix-provided FHS environment.

## Usage

Add this repository as an input:

```nix
inputs.epic-games-launcher = {
  url = "github:eduhoribe/epic-games-launcher-nix";
  inputs.nixpkgs.follows = "nixpkgs";
};
```

### Home Manager

```nix
imports = [ inputs.epic-games-launcher.homeManagerModules.default ];

...

programs.epic-games-launcher = {
  enable = true;
};
```

### NixOS

```nix
imports = [ inputs.epic-games-launcher.nixosModules.default ];

...

programs.epic-games-launcher = {
  enable = true;
};
```

### Package only

```nix
{ inputs, pkgs, ... }:

{
  nixpkgs.overlays = [ inputs.epic-games-launcher.overlays.default ];
  home.packages = with pkgs; [ epic-games-launcher ];
}
```

## How auto-updates work

On first launch, the pinned Debian package is extracted to
`${XDG_DATA_HOME:-$HOME/.local/share}/epic-games-launcher/installation`.
Subsequent launches reuse that copy, including any updates installed by the
launcher. Nix rebuilds and rollbacks do not replace or downgrade it.

The built-in updater remains enabled. Epic checks and verifies its downloads;
a private adapter handles its `dpkg -S` and `pkexec dpkg -i` calls using only
the per-user installation. It validates the package identity and architecture,
stages the full payload, and atomically swaps installations. Failed extraction
leaves the previous installation intact. No root access, host Debian database,
or package maintainer scripts are used. Updated binaries keep using the Nix
runtime without requiring another rebuild. Game downloads and updates remain
managed by the launcher.

Epic's per-user application updates remain independent of system rebuilds.
Future upstream library requirements may still require a Nix runtime update.

### Update the bootstrap package

The upstream URL serves the latest Debian package rather than an immutable release.
The SHA-256 hash pins the downloaded bytes; a changed download fails verification
until the package is deliberately updated. Old snapshots may stop being available
from upstream unless already cached.

To download and hash the current release:

```sh
nix store prefetch-file --json \
  'https://launcher-public-service-prod06.ol.epicgames.com/launcher/api/installer/download/EpicGamesLauncher-x86_64.deb'
```

Update `version` and `src.hash` in `package.nix`, then build the package, run the
flake checks, and verify that the launcher opens. This changes the initial
version for new per-user installations. Existing installations keep their own
version. Update the launcher flake input and rebuild NixOS or Home Manager to
receive packaging and runtime changes.
Update Nixpkgs separately with `nix flake update nixpkgs`.
