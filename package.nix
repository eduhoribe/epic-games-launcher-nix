{ lib
, stdenv
, fetchurl
, dpkg
, autoPatchelfHook
, wrapGAppsHook3
, webkitgtk_4_1
, gtk3
, glib
, glib-networking
, gdk-pixbuf
, cairo
, dbus
, libsoup_3
, libx11
, libayatana-appindicator
}:

stdenv.mkDerivation {
  pname = "epic-games-launcher";
  version = "0.113.1+g311e678";

  # Upstream serves the latest release at this URL. The hash pins this snapshot.
  src = fetchurl {
    url = "https://launcher-public-service-prod06.ol.epicgames.com/launcher/api/installer/download/EpicGamesLauncher-x86_64.deb";
    hash = "sha256-Y3KDvhHq76tkSRer0WtwxIrthSfAVikGLIiC/NMM6kM=";
  };

  nativeBuildInputs = [
    dpkg
    autoPatchelfHook
    wrapGAppsHook3
  ];
  buildInputs = [
    stdenv.cc.cc.lib
    webkitgtk_4_1
    gtk3
    glib
    glib-networking
    gdk-pixbuf
    cairo
    dbus
    libsoup_3
    libx11
    libayatana-appindicator
  ];

  # The tray library is loaded with dlopen rather than linked into the binary.
  runtimeDependencies = [ libayatana-appindicator ];

  unpackPhase = ''
    runHook preUnpack
    dpkg-deb -x "$src" .
    runHook postUnpack
  '';

  dontConfigure = true;
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p "$out"
    cp -r usr/bin usr/lib usr/share "$out/"
    mv "$out/bin/EpicGamesLauncher" "$out/bin/epic-games-launcher"

    substituteInPlace "$out/share/applications/epic-games-launcher.desktop" \
      --replace-fail 'Exec=EpicGamesLauncher' 'Exec=epic-games-launcher' \
      --replace-fail 'Icon=EpicGamesLauncher' \
        "Icon=$out/share/icons/hicolor/256x256@2/apps/EpicGamesLauncher.png"
    runHook postInstall
  '';

  preFixup = ''
    addAutoPatchelfSearchPath "$out/lib/epic-games-launcher"
    # Updates must go through Nix; the built-in installer cannot replace store files.
    gappsWrapperArgs+=(--set EGL_DISABLE_SELF_UPDATE 1)
  '';

  meta = {
    description = "Epic Games Launcher";
    homepage = "https://store.epicgames.com/";
    license = lib.licenses.unfree;
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
    platforms = [ "x86_64-linux" ];
    mainProgram = "epic-games-launcher";
  };
}
