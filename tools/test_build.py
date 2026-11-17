"""Exercise build.py against temporary game folders without running a real launcher."""
import contextlib
import io
import json
import os
import pathlib
import runpy
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        tools = self.root / "sdk" / "tools"
        tools.mkdir(parents=True)
        self.script = tools / "build.py"
        shutil.copyfile(pathlib.Path(__file__).with_name("build.py"), self.script)
        self.plugin = self.root / "plugin"
        source = self.plugin / "mixins" / "wave"
        source.mkdir(parents=True)
        (self.plugin / "horizon-native.json").write_text(json.dumps({"id": "wave", "version": "0.1.0"}))
        (source / "horizon-mixin.toml").write_text('[mod]\nid = "wave"\nversion = "0.1.0"\n')
        (source / "plugin.rs").write_bytes(b"// plugin\n")
        (source / "tick.rs").write_bytes(b"// tick\n")
        self.game = self.root / "game data"

    def mods(self, home):
        mods = home / "horizon-native-mods"
        mods.mkdir(parents=True)
        (mods / "sunset.hnmod").write_bytes(b"existing Sunset")
        return mods

    def run_build(self, env, *args):
        with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", [str(self.script), str(self.plugin), *args]), \
             patch("platform.system", return_value="Windows"), patch("subprocess.run") as launcher, \
             contextlib.redirect_stdout(io.StringIO()):
            launcher.return_value.returncode = 0
            try:
                runpy.run_path(str(self.script), run_name="__main__")
            except SystemExit as e:
                self.assertEqual(e.code, 0)
        return launcher

    def assert_installed(self, home):
        package = home / "horizon-native-mods" / "wave.hnmod"
        with zipfile.ZipFile(package) as archive:
            self.assertEqual(json.loads(archive.read("horizon-native.json"))["id"], "wave")
            self.assertEqual(archive.read("mixins/wave/plugin.rs"), b"// plugin\n")
        self.assertIn("mod.wave: true", (home / "horizon-mods.txt").read_text().splitlines())
        self.assertEqual((home / "horizon-native-mods" / "sunset.hnmod").read_bytes(), b"existing Sunset")

    def test_native_instance_is_built_even_when_another_is_selected(self):
        self.mods(self.game)
        native = self.game / "instances" / "native-mods"
        self.mods(native)
        other = self.game / "instances" / "survival"
        self.mods(other)
        selected = self.root / "launcher"
        selected.mkdir()
        settings = selected / "settings.json"
        settings.write_text('{"instance":"survival"}')
        before = settings.read_bytes()
        launcher = self.run_build({"HORIZON_HOME": str(self.game), "HORIZON_LAUNCHER_HOME": str(selected),
                                   "HORIZON_LAUNCHER": "mock-launcher"})
        launcher.assert_called_once()
        self.assertEqual(launcher.call_args.args[0],
                         ["mock-launcher", "native-build", "--instance", "native-mods", "--trust-native-code"])
        self.assertEqual(launcher.call_args.kwargs["env"]["HORIZON_HOME"], str(self.game.resolve()))
        self.assertEqual(launcher.call_args.kwargs["env"]["HORIZON_LAUNCHER_HOME"], str(selected))
        self.assert_installed(self.game)
        self.assert_installed(native)
        self.assertFalse((other / "horizon-native-mods" / "wave.hnmod").exists())
        self.assertEqual(settings.read_bytes(), before)

    def test_root_install_builds_default_instance_with_the_same_game_root(self):
        appdata = self.root / "Roaming"
        self.game = appdata / "horizon"
        self.mods(self.game)
        launcher = self.run_build({"APPDATA": str(appdata), "HORIZON_LAUNCHER": "mock-launcher"})
        launcher.assert_called_once()
        self.assertEqual(launcher.call_args.args[0],
                         ["mock-launcher", "native-build", "--instance", "horizon", "--trust-native-code"])
        self.assertEqual(launcher.call_args.kwargs["env"]["HORIZON_HOME"], str(self.game.resolve()))
        self.assert_installed(self.game)

    def test_no_build_installs_without_invoking_launcher(self):
        self.mods(self.game)
        launcher = self.run_build({"HORIZON_HOME": str(self.game), "HORIZON_LAUNCHER": "mock-launcher"}, "--no-build")
        launcher.assert_not_called()
        self.assert_installed(self.game)


if __name__ == "__main__":
    unittest.main()
