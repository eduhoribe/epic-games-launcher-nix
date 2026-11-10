{ lib, fetchurl, runCommand, writeShellScript, python3, dpkg, buildFHSEnv
, appimageTools, glib-networking
}:

let
  pname = "epic-games-launcher";
  version = "0.113.1+g311e678";

  # This is the initial per-user installation, not a pin on subsequent updates.
  src = fetchurl {
    url = "https://launcher-public-service-prod06.ol.epicgames.com/launcher/api/installer/download/EpicGamesLauncher-x86_64.deb";
    hash = "sha256-Y3KDvhHq76tkSRer0WtwxIrthSfAVikGLIiC/NMM6kM=";
  };

  contents = runCommand "${pname}-${version}-desktop" { nativeBuildInputs = [ dpkg ]; } ''
    dpkg-deb -x ${src} unpacked
    mkdir -p "$out/share"
    cp -r unpacked/usr/share/applications unpacked/usr/share/icons "$out/share/"
  '';

  updater = runCommand "${pname}-user-updater" { } ''
    mkdir -p "$out/libexec/epic-updater"
    substitute ${./scripts/launcher.py} "$out/libexec/launcher.py" \
      --subst-var-by python ${python3}/bin/python3 \
      --subst-var-by dpkgDeb ${dpkg}/bin/dpkg-deb \
      --subst-var-by dpkgQuery ${dpkg}/bin/dpkg-query \
      --subst-var-by seed ${src} \
      --subst-var-by runtime "$out"
    cp ${./scripts/autostart.py} "$out/libexec/autostart.py"
    chmod +x "$out/libexec/launcher.py"
    for command in dpkg pkexec sudo; do
      cat > "$out/libexec/epic-updater/$command" <<SH
#!${python3}/bin/python3
import os, sys
os.execv("$out/libexec/launcher.py", ["launcher.py", "$command", *sys.argv[1:]])
SH
      chmod +x "$out/libexec/epic-updater/$command"
    done
  '';

  start = writeShellScript "epic-games-launcher-start" ''
    exec ${updater}/libexec/launcher.py run "$@"
  '';

  fhs = appimageTools.defaultFhsEnvArgs;
  launcher = buildFHSEnv (fhs // {
    inherit pname version;
    targetPkgs = pkgs: fhs.targetPkgs pkgs ++ (with pkgs; [
      webkitgtk_4_1
      libsoup_3
      libayatana-appindicator
      glib-networking
      # The AppImage FHS defaults only supply base/ugly plugins. WebKit aborts
      # when media playback needs autoaudiosink (from good) and it is missing.
      gst_all_1.gst-plugins-good
      gst_all_1.gst-plugins-bad
      gst_all_1.gst-libav
    ]);

    # Updated upstream binaries retain their original interpreter and RUNPATH.
    # They run in this environment without patching each downloaded release.
    runScript = start;
    extraPreBwrapCmds = ''
      export EGL_NIX_WRAPPER="$0"
      export EGL_NIX_LAUNCHER_ROOT="$(${updater}/libexec/launcher.py init)"
    '';
    extraBwrapArgs = [
      # Upstream checks that the Debian database directory exists before running
      # its dpkg ownership probe. The adapter uses the private database on disk.
      "--tmpfs /var"
      "--symlink /run /var/run"
      "--dir /var/lib/dpkg"
    ];
    profile = ''
      export GIO_EXTRA_MODULES="${glib-networking}/lib/gio/modules"
    '';

    extraInstallCommands = ''
      cp -r ${contents}/share "$out/"
      substituteInPlace "$out/share/applications/epic-games-launcher.desktop" \
        --replace-fail 'Exec=EpicGamesLauncher' "Exec=$out/bin/${pname}" \
        --replace-fail 'Icon=EpicGamesLauncher' \
          "Icon=$out/share/icons/hicolor/256x256@2/apps/EpicGamesLauncher.png"
    '';

    passthru = {
      inherit updater;
      tests.media-plugins = runCommand "${pname}-media-plugin-tests" { } ''
        # Inspect the plugins actually installed in the generated x86_64 FHS
        # root, without needing nested bubblewrap or a running audio server.
        export GST_PLUGIN_SYSTEM_PATH_1_0="${launcher.fhsenv}/usr/lib64/gstreamer-1.0"
        export GST_PLUGIN_PATH_1_0=
        export GST_REGISTRY_1_0="$TMPDIR/gstreamer-registry.bin"
        for element in autoaudiosink pulsesink decodebin h264parse avdec_h264; do
          ${launcher.fhsenv}/usr/bin/gst-inspect-1.0 "$element" > /dev/null
        done
        ${launcher.fhsenv}/usr/bin/gst-launch-1.0 -q \
          audiotestsrc num-buffers=10 ! audioconvert ! audioresample ! fakesink
        touch "$out"
      '';
      tests.user-updates = runCommand "${pname}-user-update-tests" { } ''
        ${python3}/bin/python3 ${./tests/test_launcher.py} ${updater}/libexec/launcher.py
        touch "$out"
      '';
    };
    meta = {
      description = "Epic Games Launcher with per-user self-updates";
      homepage = "https://store.epicgames.com/";
      license = lib.licenses.unfree;
      sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
      platforms = [ "x86_64-linux" ];
      mainProgram = pname;
    };
  });
in
launcher
