"""Translate Epic-owned autostart commands into launches through the Nix runtime."""
import ctypes
import os
from pathlib import Path
import select
import shlex
import threading


def desktop_quote(value):
    # Desktop string decoding happens before Exec argument parsing.
    escapes = {"\\": "\\\\\\\\", '"': '\\\\"', '`': '\\\\`', '$': '\\\\$',
               "\n": "\\n", "\r": "\\r", "\t": "\\t", "%": "%%"}
    return '"' + ''.join(escapes.get(character, character) for character in str(value)) + '"'


def prepare_bridge(state, fallback):
    # Prefer the installed command so system upgrades select the current runtime.
    # The fallback also permits `nix run` without installing the package first.
    bridge = state / 'launch'
    content = ('#!/bin/sh\n'
               'if command -v epic-games-launcher >/dev/null 2>&1; then\n'
               '  exec epic-games-launcher "$@"\n'
               'fi\n'
               f'exec {shlex.quote(fallback)} "$@"\n')
    temporary = state / 'launch.new'
    temporary.write_text(content)
    temporary.chmod(0o755)
    temporary.replace(bridge)
    return bridge


class Autostart:
    def __init__(self, state, *, executable=None, config_home=None):
        self.state = state
        paths = [state / 'installation/usr/bin/EpicGamesLauncher']
        if executable is not None:
            paths.append(executable)
        self.executables = [form for path in paths for form in (desktop_quote(path), str(path))]
        self.directory = Path(config_home or os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'autostart'
        self.entry = self.directory / 'epic-games-launcher.desktop'
        self.stopped = threading.Event()

    def repair(self):
        # Never create or enable an entry: Epic owns the autostart preference.
        if self.entry.is_symlink():
            return
        try:
            content = self.entry.read_text()
            lines = content.splitlines(keepends=True)
            changed = False
            in_desktop = False
            for index, line in enumerate(lines):
                if line.startswith('['):
                    in_desktop = line.strip() == '[Desktop Entry]'
                if not in_desktop or not line.startswith('Exec='):
                    continue
                # Match only Epic's raw executable; preserve all arguments.
                for executable in self.executables:
                    prefix = 'Exec=' + executable
                    if line.startswith(prefix) and line[len(prefix):len(prefix) + 1] in ('', ' ', '\n', '\r'):
                        lines[index] = 'Exec=' + desktop_quote(self.state / 'launch') + line[len(prefix):]
                        changed = True
                        break
            if changed:
                # Keep the inode and permissions owned by Epic. If it has
                # concurrently removed/replaced the file, this open fd cannot
                # recreate an entry or undo the user's disable operation.
                with self.entry.open('r+') as entry:
                    if entry.read() != content:
                        return
                    entry.seek(0)
                    entry.write(''.join(lines))
                    entry.truncate()
        except FileNotFoundError:
            pass

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        libc = ctypes.CDLL(None, use_errno=True)
        self.fd = libc.inotify_init1(os.O_CLOEXEC | os.O_NONBLOCK)
        if self.fd < 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        self.libc = libc
        # Watch before repairing/starting Epic so the first write cannot be lost.
        self.watch = libc.inotify_add_watch(self.fd, os.fsencode(self.directory), 0x8 | 0x80)
        if self.watch < 0:
            error = ctypes.get_errno()
            os.close(self.fd)
            raise OSError(error, os.strerror(error))
        self.repair()
        self.thread = threading.Thread(target=self.monitor, daemon=True)
        self.thread.start()
        return self

    def monitor(self):
        while not self.stopped.is_set():
            if select.select([self.fd], [], [], 0.1)[0]:
                try:
                    os.read(self.fd, 65536)
                    self.repair()
                except FileNotFoundError:
                    pass

    def __exit__(self, *_):
        self.stopped.set()
        self.thread.join()
        os.close(self.fd)
        self.repair()
