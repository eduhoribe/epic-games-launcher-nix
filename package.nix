{ lib, appimageTools, fetchurl }:

let
  pname = "epic-games-launcher";
  version = "0.110.0+gf2e5ba5";

  # Upstream serves the latest release at this URL. The hash pins this snapshot.
  src = fetchurl {
    url = "https://launcher-public-service-prod06.ol.epicgames.com/launcher/api/installer/download/EpicGamesLauncher-x86_64.AppImage";
    hash = "sha256-U7vRJC4JX2CZYygO8TIVgRVEKrcZukV4XFqT6vqpXEA=";
  };

  contents = appimageTools.extract { inherit pname version src; };
in
appimageTools.wrapType2 {
  inherit pname version src;

  extraInstallCommands = ''
    install -Dm444 ${contents}/usr/share/applications/epic-games-launcher.desktop \
      $out/share/applications/epic-games-launcher.desktop
    substituteInPlace $out/share/applications/epic-games-launcher.desktop \
      --replace-fail 'Exec=EpicGamesLauncher' 'Exec=epic-games-launcher' \
      --replace-fail 'Icon=EpicGamesLauncher' \
        "Icon=$out/share/icons/hicolor/256x256@2/apps/EpicGamesLauncher.png"

    mkdir -p $out/share/icons
    cp -r ${contents}/usr/share/icons/hicolor $out/share/icons/
  '';

  meta = {
    description = "Epic Games Launcher";
    homepage = "https://store.epicgames.com/";
    license = lib.licenses.unfree;
    platforms = [ "x86_64-linux" ];
    mainProgram = pname;
  };
}
