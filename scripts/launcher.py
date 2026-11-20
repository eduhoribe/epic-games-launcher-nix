#!@python@
"""Bootstrap and install Epic's Debian payload in a private user directory."""
import ctypes
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import signal

from autostart import Autostart, prepare_bridge
import tempfile

DPKG_DEB = "@dpkgDeb@"
DPKG_QUERY = "@dpkgQuery@"
SEED = "@seed@"
RUNTIME = "@runtime@"
FHS_BINARY = "@fhsBinary@"
DEB_BINARY = "usr/bin/EpicGamesLauncher"


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
        if bootstrap and (destination / DEB_BINARY).is_file():
            return
        fields = subprocess.check_output(
            [DPKG_DEB, "-f", str(package), "Package", "Architecture"], text=True)
        if fields.splitlines() != ["Package: epic-games-launcher", "Architecture: amd64"]:
            raise ValueError("Expected the epic-games-launcher amd64 Debian package")
        with tempfile.TemporaryDirectory(prefix=".install-", dir=state) as temporary:
            staged = Path(temporary) / "installation"
            subprocess.run([DPKG_DEB, "-x", str(package), str(staged)], check=True)
            binary = staged / DEB_BINARY
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
                f"/{DEB_BINARY}\n{destination / DEB_BINARY}\n")
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
        option, path = arguments
        if path == FHS_BINARY:
            # The Debian path is also recorded by older per-user installs.
            path = "/" + DEB_BINARY
        return subprocess.call([DPKG_QUERY, "--admindir=" + str(database), option, path])
    if len(arguments) == 2 and arguments[0] in ("-i", "--install"):
        install(Path(arguments[1]))
        return 0
    raise ValueError("Unsupported dpkg operation in the per-user launcher runtime")


def main():
    command, *arguments = sys.argv[1:]
    if command == "init" and not arguments:
        install(Path(SEED), bootstrap=True)
        with (root() / "install.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if wrapper := os.environ.get("EGL_NIX_WRAPPER"):
                prepare_bridge(root(), wrapper)
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
    if command == "run" and arguments:
        binary, *arguments = arguments
        os.environ.pop("APPIMAGE", None)
        os.environ.pop("APPDIR", None)
        os.environ["PATH"] = RUNTIME + "/libexec/epic-updater:" + os.environ["PATH"]
        with Autostart(root(), executable=binary):
            child = subprocess.Popen([binary, *arguments])
            for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                signal.signal(number, lambda signum, _frame: child.send_signal(signum))
            returncode = child.wait()
            return returncode if returncode >= 0 else 128 - returncode
    raise ValueError("Unknown launcher helper command")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Epic launcher: {error}", file=sys.stderr)
        sys.exit(1)
