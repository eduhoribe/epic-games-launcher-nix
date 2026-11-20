"""Integration tests for local installation; no GUI or network required.

Run: python3 tests/test_launcher.py /nix/store/...-user-updater/libexec/launcher.py
"""
import concurrent.futures
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import time

HELPER = Path(sys.argv.pop(1)).resolve()
sys.path.insert(0, str(HELPER.parent))
from autostart import Autostart, desktop_quote, prepare_bridge
from launcher import DPKG_DEB, FHS_BINARY


class UserUpdates(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="epic-user-tests-")
        self.work = Path(self.temporary.name)
        # Exercise paths containing spaces, including the update package name.
        self.state = self.work / "user data"
        self.env = dict(os.environ, EGL_NIX_LAUNCHER_ROOT=str(self.state),
                        XDG_CONFIG_HOME=str(self.work / "config"),
                        EGL_NIX_WRAPPER="/runtime with spaces/bin/epic-games-launcher")
        self.binary = self.state / "installation/usr/bin/EpicGamesLauncher"

    def tearDown(self):
        self.temporary.cleanup()

    def call(self, *args, check=True):
        return subprocess.run([str(HELPER), *map(str, args)], env=self.env,
                              capture_output=True, text=True, check=check)

    def package(self, version, *, name="epic-games-launcher", binary=True):
        tree = self.work / (version + name)
        (tree / "DEBIAN").mkdir(parents=True)
        (tree / "DEBIAN/control").write_text(
            f"Package: {name}\nVersion: {version}\nArchitecture: amd64\n"
            "Maintainer: Test <test@example.invalid>\nDescription: Fixture\n")
        (tree / "usr/lib/epic-games-launcher").mkdir(parents=True)
        (tree / "usr/lib/epic-games-launcher/version").write_text(version)
        if binary:
            (tree / "usr/bin").mkdir()
            shutil.copyfile(shutil.which("bash"), tree / "usr/bin/EpicGamesLauncher")
            (tree / "usr/bin/EpicGamesLauncher").chmod(0o755)
        package = self.work / (version + name + " update.deb")
        subprocess.run([str(DPKG_DEB), "--build", str(tree), str(package)],
                       check=True, capture_output=True)
        return package

    def test_update_is_preserved_by_bootstrap_and_is_writable(self):
        self.call("init")
        self.assertTrue(os.access(self.binary, os.W_OK))
        self.call("pkexec", "dpkg", "-i", self.package("99.0"))
        self.call("init")
        self.assertEqual((self.state / "installation/usr/lib/epic-games-launcher/version")
                         .read_text(), "99.0")
        self.call("run", self.binary, "-c", "exit 0")
        self.assertFalse((self.work / "config/autostart/epic-games-launcher.desktop").exists())
        self.assertTrue((self.state / "launch").is_file())
        ownership = self.call("dpkg", "-S", self.binary).stdout
        self.assertIn("epic-games-launcher:", ownership)
        self.assertIn(str(self.binary), ownership)
        self.assertEqual(self.call("dpkg", "-S", FHS_BINARY).stdout,
                         "epic-games-launcher: /usr/bin/EpicGamesLauncher\n")
        self.assertNotEqual(self.call("dpkg", "-S", FHS_BINARY + ".other",
                                      check=False).returncode, 0)

    def test_failed_or_wrong_package_leaves_installation_intact(self):
        self.call("pkexec", "dpkg", "-i", self.package("1.0"))
        for package in (self.package("2.0", name="other-package"),
                        self.package("3.0", binary=False), self.work / "missing.deb"):
            self.assertNotEqual(self.call("pkexec", "dpkg", "-i", package, check=False).returncode, 0)
            self.assertEqual((self.state / "installation/usr/lib/epic-games-launcher/version")
                             .read_text(), "1.0")
        self.assertEqual(list(self.state.glob(".install-*")), [])

    def test_concurrent_first_launch_is_safe(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: self.call("init"), range(3)))
        self.assertTrue(self.binary.is_file())
        self.assertEqual({result.stdout.strip() for result in results}, {str(self.state)})
        self.assertEqual(list(self.state.glob(".install-*")), [])

    def test_bridge_uses_installed_runtime_and_preserves_arguments(self):
        self.call("init")
        bridge = self.state / "launch"
        self.assertTrue(os.access(bridge, os.X_OK))
        commands = self.work / "commands"
        commands.mkdir()
        installed = commands / "epic-games-launcher"
        installed.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
        installed.chmod(0o755)
        result = subprocess.check_output([str(bridge), "--autostart", "argument with spaces"],
                                         env=dict(self.env, PATH=str(commands)), text=True)
        self.assertEqual(result.splitlines(), ["--autostart", "argument with spaces"])

    def test_bridge_falls_back_to_last_runtime_without_installed_command(self):
        self.state.mkdir(parents=True)
        fallback = self.work / "runtime with spaces"
        fallback.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
        fallback.chmod(0o755)
        bridge = prepare_bridge(self.state, str(fallback))
        result = subprocess.check_output([str(bridge), "--autostart", "epic://test"],
                                         env=dict(self.env, PATH="/nonexistent"), text=True)
        self.assertEqual(result.splitlines(), ["--autostart", "epic://test"])

    def test_autostart_enable_disable_and_reenable_remain_app_owned(self):
        self.call("init")
        # Pass the config location explicitly without changing the host environment.
        adapter = Autostart(self.state, executable=FHS_BINARY, config_home=self.env["XDG_CONFIG_HOME"])
        raw = "[Desktop Entry]\nType=Application\nExec=" + desktop_quote(FHS_BINARY) + ' --autostart "a b" %u\nHidden=false\n'
        expected = raw.replace(desktop_quote(FHS_BINARY), desktop_quote(self.state / "launch"))

        def wait_for_expected():
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if adapter.entry.read_text() == expected:
                    return
                time.sleep(0.01)
            self.fail("Autostart entry was not adapted")

        with adapter:
            self.assertFalse(adapter.entry.exists())
            adapter.entry.write_text(raw)
            wait_for_expected()
            self.assertFalse(adapter.entry.is_symlink())
            adapter.entry.unlink()
            time.sleep(0.15)
            self.assertFalse(adapter.entry.exists())
            # Also handle the app replacing its entry by rename.
            temporary = adapter.directory / "entry.tmp"
            temporary.write_text(raw)
            temporary.replace(adapter.entry)
            wait_for_expected()
            adapter.entry.unlink()
        self.assertFalse(adapter.entry.exists())

    def test_autostart_migrates_existing_entry_but_leaves_other_commands(self):
        adapter = Autostart(self.state, config_home=self.env["XDG_CONFIG_HOME"])
        adapter.directory.mkdir(parents=True)
        # Existing versions wrote unquoted paths even with spaces.
        adapter.entry.write_text("[Desktop Entry]\nExec=" + str(self.binary) + " --autostart\n")
        adapter.repair()
        self.assertEqual(adapter.entry.read_text(), "[Desktop Entry]\nExec=" +
                         desktop_quote(self.state / "launch") + " --autostart\n")
        other = "[Desktop Entry]\nExec=/some/other/launcher --autostart\nHidden=true\n"
        adapter.entry.write_text(other)
        adapter.repair()
        self.assertEqual(adapter.entry.read_text(), other)

    def test_adapters_reject_unrelated_commands(self):
        for command in (("pkexec", "sh", "-c", "true"), ("sudo", "id"),
                        ("dpkg", "--remove", "epic-games-launcher")):
            self.assertNotEqual(self.call(*command, check=False).returncode, 0)
        self.assertFalse(self.state.exists())


if __name__ == "__main__":
    unittest.main()
