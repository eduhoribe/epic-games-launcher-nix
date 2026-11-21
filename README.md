# Epic Games Launcher for NixOS

Bootstraps a writable per-user copy of the upstream x86_64 Linux Debian binary
and runs it in a Nix-provided FHS environment with GTK and WebKit libraries.
The runtime includes GStreamer audio sinks, media parsers, and decoders for
WebKit playback. `nix flake check` verifies plugin discovery in the generated
FHS root and exercises an audio pipeline without requiring an audio device.
Includes the desktop entry, Epic launcher URI handler declaration, and icons.
The software is proprietary; this repository contains the packaging only.

## Use from another flake

Add this repository as an input:

```nix
inputs.epic-games-launcher = {
  url = "github:eduhoribe/epic-games-launcher-nix";
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

To reset the launcher to the bundled version, close it, move the `installation`
directory aside, and start it again. Account settings and installed-game records
remain in the separate `com.epicgames.eglv2` data directory. To opt out of
self-updates, launch with `EGL_DISABLE_SELF_UPDATE=1`.

Use Epic's own settings to enable or disable desktop autostart. The autostart
file stays writable and owned by the application. A runtime adapter translates
only its raw executable path into a per-user launch bridge, preserving arguments
and all other settings. Disabling autostart removes the entry normally; the
adapter never creates one. Existing raw entries are migrated on launch.

The bridge prefers the installed `epic-games-launcher` command so system rebuilds
select the current Nix runtime. For `nix run` without installation it falls back
to the runtime used on the last launch (which must remain in the Nix store).
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

Update `version` and `src.hash` in `package.nix`, then run `nix build`,
`nix flake check`, and check that the launcher opens. This changes the initial
version for new per-user installations. Existing installations keep their own
version. Update the launcher flake input and rebuild NixOS or Home Manager to
receive packaging and runtime changes.
Update Nixpkgs separately with `nix flake update nixpkgs`.

Desktop integration declares `com.epicgames.launcher` URLs. Selecting a default
handler remains a desktop or Home Manager setting.
