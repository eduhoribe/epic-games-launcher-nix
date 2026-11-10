#!@python@
"""Bootstrap and install Epic's Debian payload in a private user directory."""
import ctypes
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tempfile

DPKG_DEB = "@dpkgDeb@"
DPKG_QUERY = "@dpkgQuery@"
SEED = "@seed@"
RUNTIME = "@runtime@"


def root():
    return Path(os.environ.get("EGL_NIX_LAUNCHER_ROOT") or
                str(Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
                    / "epic-games-launcher")).absolute()


def install(package, *, bootstrap=False):
    state = root()
    state.mkdir(parents=True, exist_ok=True)
    with (state / "install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        destination = state / "installation"
        if bootstrap and (destination / "usr/bin/EpicGamesLauncher").is_file():
            return
        fields = subprocess.check_output(
            [DPKG_DEB, "-f", str(package), "Package", "Architecture"], text=True)
        if fields.splitlines() != ["Package: epic-games-launcher", "Architecture: amd64"]:
            raise ValueError("Expected the epic-games-launcher amd64 Debian package")
        with tempfile.TemporaryDirectory(prefix=".install-", dir=state) as temporary:
            staged = Path(temporary) / "installation"
            subprocess.run([DPKG_DEB, "-x", str(package), str(staged)], check=True)
            binary = staged / "usr/bin/EpicGamesLauncher"
            if binary.is_symlink() or not binary.is_file() or not os.access(binary, os.X_OK):
                raise ValueError("Package has no executable usr/bin/EpicGamesLauncher")
            with binary.open("rb") as executable:
                if executable.read(4) != b"\x7fELF":
                    raise ValueError("Launcher is not an ELF executable")
            # Keep a real, private dpkg ownership database for the upstream probe.
            # Maintainer scripts are deliberately not executed.
            database = staged / "var/lib/dpkg"
            (database / "info").mkdir(parents=True)
            control = subprocess.check_output([DPKG_DEB, "-f", str(package)], text=True)
            (database / "status").write_text("Status: install ok installed\n" + control + "\n")
            (database / "info/epic-games-launcher.list").write_text(
                "/usr/bin/EpicGamesLauncher\n" + str(destination / "usr/bin/EpicGamesLauncher") + "\n")
            if destination.exists():
                # Exchange whole installations atomically, including libraries and
                # ownership metadata. A failed extraction leaves the old one intact.
                libc = ctypes.CDLL(None, use_errno=True)
                exchange = libc.renameat2
                exchange.argtypes = [ctypes.c_int, ctypes.c_char_p,
                                     ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
                exchange.restype = ctypes.c_int
                if exchange(-100, os.fsencode(staged), -100, os.fsencode(destination), 2):
                    error = ctypes.get_errno()
                    raise OSError(error, os.strerror(error))
            else:
                staged.rename(destination)


def dpkg(arguments):
    if len(arguments) == 2 and arguments[0] in ("-S", "--search"):
        database = root() / "installation/var/lib/dpkg"
        return subprocess.call([DPKG_QUERY, "--admindir=" + str(database), *arguments])
    if len(arguments) == 2 and arguments[0] in ("-i", "--install"):
        install(Path(arguments[1]))
        return 0
    raise ValueError("Unsupported dpkg operation in the per-user launcher runtime")


def main():
    command, *arguments = sys.argv[1:]
    if command == "init" and not arguments:
        install(Path(SEED), bootstrap=True)
        print(root())
        return 0
    if command == "dpkg":
        return dpkg(arguments)
    if command in ("pkexec", "sudo"):
        # Tauri invokes pkexec dpkg -i <signed-download>. No elevation is needed.
        # Never pass a failed update to the host's package manager or sudo.
        if len(arguments) == 3 and arguments[0] == "dpkg" and arguments[1] in ("-i", "--install"):
            return dpkg(arguments[1:])
        raise ValueError("Only per-user launcher installation is supported")
    if command == "run":
        os.environ.pop("APPIMAGE", None)
        os.environ.pop("APPDIR", None)
        os.environ["PATH"] = RUNTIME + "/libexec/epic-updater:" + os.environ["PATH"]
        binary = root() / "installation/usr/bin/EpicGamesLauncher"
        os.execv(str(binary), [str(binary), *arguments])
    raise ValueError("Unknown launcher helper command")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Epic launcher: {error}", file=sys.stderr)
        sys.exit(1)
