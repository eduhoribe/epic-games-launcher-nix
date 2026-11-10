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

HELPER = Path(sys.argv.pop(1)).resolve()
DPKG_DEB = Path(next(line.split('"')[1] for line in HELPER.read_text().splitlines()
                     if line.startswith('DPKG_DEB = ')))


class UserUpdates(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="epic-user-tests-")
        self.work = Path(self.temporary.name)
        # Exercise paths containing spaces, including the update package name.
        self.state = self.work / "user data"
        self.env = dict(os.environ, EGL_NIX_LAUNCHER_ROOT=str(self.state))
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
            shutil.copyfile(shutil.which("true"), tree / "usr/bin/EpicGamesLauncher")
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
        ownership = self.call("dpkg", "-S", self.binary).stdout
        self.assertIn("epic-games-launcher:", ownership)
        self.assertIn(str(self.binary), ownership)

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

    def test_adapters_reject_unrelated_commands(self):
        for command in (("pkexec", "sh", "-c", "true"), ("sudo", "id"),
                        ("dpkg", "--remove", "epic-games-launcher")):
            self.assertNotEqual(self.call(*command, check=False).returncode, 0)
        self.assertFalse(self.state.exists())


if __name__ == "__main__":
    unittest.main()
