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

### Repository updates

The **Update pins** GitHub Actions workflow checks for updates daily at
06:23 UTC. It refreshes the locked nixpkgs revision and reads the Debian package
version and SHA-256 hash from Epic's current download. It runs the launcher
checks before committing any changes to the default branch. You can also run
the workflow manually from the Actions tab.

Epic's download URL rolls forward with each release. The SHA-256 hash pins the
downloaded bytes. Older pins may require a cached copy of the matching package.

You can refresh both pins locally with Nix, `jq`, and `dpkg` installed.

```sh
nix flake update nixpkgs
bash scripts/update-bootstrap.sh
```
