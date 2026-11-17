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


REV = "9f42064c11efe7ef3e5ed2baad7ddc2a3b36eea0"
OTHER = "66f3981aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def sunset_package(horizon=REV, api=2, version="1.2.1"):
    """An installed Sunset as the launcher keeps it: horizon-native.json and mixins/sunset/api.rs in a zip."""
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        z.writestr("horizon-native.json", json.dumps({"id": "sunset", "version": version, "horizon": horizon}))
        z.writestr("mixins/sunset/api.rs", f"pub(super) const API_VERSION: u32 = {api};\n")
    return data.getvalue()


SUNSET = sunset_package()


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
        (self.plugin / "horizon-native.json").write_text(json.dumps({"id": "wave", "version": "0.1.0", "horizon": REV}))
        (source / "horizon-mixin.toml").write_text(f'[mod]\nid = "wave"\nversion = "0.1.0"\n\n'
                                                   f'[compatibility]\nhorizon_revision = "{REV}"\n')
        (source / "plugin.rs").write_bytes(b"// plugin\nconst _: () = api::needs(2);\n")
        (source / "tick.rs").write_bytes(b"// tick\n")
        self.game = self.root / "game data"

    def mods(self, home):
        mods = home / "horizon-native-mods"
        mods.mkdir(parents=True)
        (mods / "sunset.hnmod").write_bytes(SUNSET)
        return mods

    def run_build(self, env, *args):
        launcher, code, _ = self.run_raw(env, *args)
        self.assertIn(code, (None, 0))
        return launcher

    def run_raw(self, env, *args, answer=None, tty=True):
        """Runs build.py; gives the mocked launcher, the exit code or message, and what it printed. Without an
        `answer` it runs with --yes; with one, that is typed at the install question (on a terminal if `tty`)."""
        if answer is None:
            args = (*args, "--yes")
        stdin = io.StringIO(answer or "")
        stdin.isatty = lambda: tty
        with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", [str(self.script), str(self.plugin), *args]), \
             patch.object(sys, "stdin", stdin), \
             patch("platform.system", return_value="Windows"), patch("subprocess.Popen") as launcher, \
             contextlib.redirect_stdout(io.StringIO()) as printed:
            launcher.return_value.stdout = iter(line + "\n" for line in getattr(self, "output", []))
            launcher.return_value.wait.return_value = getattr(self, "exit", 0)
            code = None
            try:
                runpy.run_path(str(self.script), run_name="__main__")
            except SystemExit as e:
                code = e.code
        return launcher, code, printed.getvalue()

    def assert_installed(self, home):
        package = home / "horizon-native-mods" / "wave.hnmod"
        with zipfile.ZipFile(package) as archive:
            self.assertEqual(json.loads(archive.read("horizon-native.json"))["id"], "wave")
            self.assertEqual(archive.read("mixins/wave/plugin.rs"), (self.plugin / "mixins/wave/plugin.rs").read_bytes())
        self.assertIn("mod.wave: true", (home / "horizon-mods.txt").read_text().splitlines())
        self.assertEqual((home / "horizon-native-mods" / "sunset.hnmod").read_bytes(), SUNSET)

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

    def set_plugin(self, horizon=REV, toml_rev=REV, needs="const _: () = api::needs(2);"):
        source = self.plugin / "mixins" / "wave"
        (self.plugin / "horizon-native.json").write_text(json.dumps({"id": "wave", "version": "0.1.0", "horizon": horizon}))
        rev = f'[compatibility]\nhorizon_revision = "{toml_rev}"\n' if toml_rev else ""
        (source / "horizon-mixin.toml").write_text(f'[mod]\nid = "wave"\nversion = "0.1.0"\n\n{rev}')
        (source / "plugin.rs").write_text(f"// plugin\n{needs}\n")

    def assert_refused(self, words, *args, env=None):
        mods = self.mods(self.game)
        launcher, code, _ = self.run_raw(env or {"HORIZON_HOME": str(self.game), "HORIZON_LAUNCHER": "mock-launcher"}, *args)
        self.assertIsInstance(code, str)
        for w in words:
            self.assertIn(w, code)
        launcher.assert_not_called()
        self.assertFalse((mods / "wave.hnmod").exists())
        self.assertFalse((self.game / "horizon-mods.txt").exists())
        return code

    def test_matching_plugin_says_so_and_builds(self):
        self.mods(self.game)
        launcher, code, printed = self.run_raw({"HORIZON_HOME": str(self.game), "HORIZON_LAUNCHER": "mock-launcher"})
        self.assertIn(code, (None, 0))
        self.assertIn("wave matches Sunset 1.2.1", printed)
        self.assertIn("plugin API 2 (needs 2)", printed)
        launcher.assert_called_once()
        self.assert_installed(self.game)

    def test_other_horizon_revision_stops_before_installing(self):
        self.set_plugin(horizon=OTHER, toml_rev=OTHER)
        self.assert_refused(["wave pins Horizon 66f3981", "built for 9f42064", REV, "Nothing was installed"])

    def test_manifests_disagreeing_with_each_other_stop(self):
        self.set_plugin(horizon=REV, toml_rev=OTHER)
        self.assert_refused(["horizon-native.json pins Horizon 9f42064", "horizon_revision is 66f3981"])

    def test_missing_horizon_revision_stops(self):
        self.set_plugin(toml_rev=None)
        self.assert_refused(["wave pins Horizon nothing", "built for 9f42064"])

    def test_newer_plugin_api_stops_before_installing(self):
        self.set_plugin(needs="const _: () = api::needs(2);\nconst _: () = api::needs(3);")
        self.assert_refused(["wave needs plugin API 3", "api::needs(3) in plugin.rs", "has plugin API 2",
                             "declare needs(2)", "Nothing was installed"])

    def test_older_or_no_needs_line_is_fine(self):
        for needs in ("const _: () = api::needs(1);", "// no needs line"):
            self.set_plugin(needs=needs)
            shutil.rmtree(self.game, ignore_errors=True)
            self.mods(self.game)
            self.run_build({"HORIZON_HOME": str(self.game), "HORIZON_LAUNCHER": "mock-launcher"}, "--no-build")
            self.assert_installed(self.game)

    def test_unreadable_installed_sunset_stops(self):
        mods = self.mods(self.game)
        (mods / "sunset.hnmod").write_bytes(b"not a zip")
        launcher, code, _ = self.run_raw({"HORIZON_HOME": str(self.game), "HORIZON_LAUNCHER": "mock-launcher"})
        self.assertIn("Can't read Sunset's Horizon revision", code)
        launcher.assert_not_called()
        self.assertFalse((mods / "wave.hnmod").exists())

    def test_no_installed_sunset_stops(self):
        mods = self.mods(self.game)
        (mods / "sunset.hnmod").unlink()
        _, code, _ = self.run_raw({"HORIZON_HOME": str(self.game), "HORIZON_LAUNCHER": "mock-launcher"})
        self.assertIn("No sunset.hnmod", code)
        self.assertFalse((mods / "wave.hnmod").exists())

    def test_check_against_a_sunset_checkout_installs_nothing(self):
        checkout = self.root / "sunset-client"
        (checkout / "mixins" / "sunset").mkdir(parents=True)
        (checkout / "horizon-native.json").write_text(json.dumps({"version": "1.3.0", "horizon": REV}))
        (checkout / "mixins" / "sunset" / "api.rs").write_text("pub(super) const API_VERSION: u32 = 3;\n")
        self.set_plugin(needs="const _: () = api::needs(3);")
        launcher, code, printed = self.run_raw({"HORIZON_LAUNCHER": "mock-launcher"}, "--check", "--sunset", str(checkout))
        self.assertEqual(code, 0)
        self.assertIn("wave matches Sunset 1.3.0", printed)
        launcher.assert_not_called()
        self.assertFalse((self.root / "sdk" / "dist").exists())
        (checkout / "mixins" / "sunset" / "api.rs").write_text("pub(super) const API_VERSION: u32 = 2;\n")
        _, code, _ = self.run_raw({}, "--check", "--sunset", str(checkout))
        self.assertIn("needs plugin API 3", code)

    def test_newer_installed_sunset_package_is_checked_too(self):
        mods = self.mods(self.game)
        (mods / "sunset-1.3.0.hnmod").write_bytes(sunset_package(horizon=OTHER, version="1.3.0"))
        _, code, _ = self.run_raw({"HORIZON_HOME": str(self.game)}, "--no-build")
        self.assertIn("Sunset 1.3.0", code)
        self.assertFalse((mods / "wave.hnmod").exists())

    def test_sunset_flag_without_a_path(self):
        _, code, _ = self.run_raw({}, "--sunset", answer="")
        self.assertIn("--sunset needs a path", code)

    # ---- what a failed build says

    def failed_build(self, output, log=None, exit=0):
        """A build whose launcher printed `output` and wrote `log` as native/build.log; gives build.py's message."""
        self.mods(self.game)
        self.output, self.exit = output, exit
        launcher_home = self.root / "launcher-data"
        if log is not None:
            (launcher_home / "native").mkdir(parents=True)
            (launcher_home / "native" / "build.log").write_text(log)
        _, code, printed = self.run_raw({"HORIZON_HOME": str(self.game), "HORIZON_LAUNCHER": "mock-launcher",
                                         "HORIZON_LAUNCHER_HOME": str(launcher_home)})
        return code, printed

    def plugin_source(self, plugin, tick=None):
        source = self.plugin / "mixins" / "wave"
        (source / "plugin.rs").write_text(plugin)
        if tick is not None:
            (source / "tick.rs").write_text(tick)

    ISOLATED = """error[E0432]: unresolved import `super::sunset_api`
     --> crates/horizon-client/src/game.rs:21761:9
      |
21761 |     use super::sunset_api as api;
      |         ^^^^^^^----------^^^^^^^
      |                |
      |                no `sunset_api` in `game`

"""
    MISMATCH = """error[E0308]: mismatched types
     --> crates/horizon-client/src/game.rs:21765:27
      |
21765 |         let broken: u32 = "not a number";
      |                     ---   ^^^^^^^^^^^^^^ expected `u32`, found `&str`
      |                     |
      |                     expected due to this

error: could not compile `horizon-client` (lib) due to 2 previous errors
"""

    def test_compile_error_names_the_plugin_file_and_line(self):
        self.plugin_source('use super::sunset_api as api;\nconst _: () = api::needs(2);\npub(super) fn tick() {\n'
                           '    let broken: u32 = "not a number";\n}\n')
        code, printed = self.failed_build(["[ 1:30] wave was left out: made for another Horizon version",
                                           "native-9f42064-abc built and selected for its instance (9 s)."],
                                          self.MISMATCH + self.ISOLATED + self.MISMATCH)
        self.assertIn("wave didn't compile, so the launcher left it out", code)
        self.assertIn("plugin.rs line 4: mismatched types (expected `u32`, found `&str`)", code)
        self.assertIn('let broken: u32 = "not a number";', code)
        self.assertNotIn("sunset_api", code)
        self.assertEqual(code.count("plugin.rs line 4"), 1)
        self.assertIn("build.log", code)
        self.assertNotIn("Built.", printed)
        self.assertIn("wave was left out", printed)

    def test_compile_error_in_tick_rs_and_repeated_lines(self):
        self.plugin_source("// plugin\n", tick='// tick\nlet broken: u32 = "not a number";\nlet broken: u32 = "not a number";\n')
        code, _ = self.failed_build(["wave was left out: made for another Horizon version"], self.MISMATCH)
        self.assertIn("tick.rs lines 2, 3: mismatched types", code)

    def test_error_outside_the_plugin_says_so(self):
        code, _ = self.failed_build(["wave was left out: made for another Horizon version"],
                                    self.MISMATCH.replace('let broken: u32 = "not a number";', "let x: u8 = sunset_thing();"))
        self.assertIn("aren't in wave's files", code)
        self.assertIn("mismatched types at crates/horizon-client/src/game.rs:21765:27", code)

    def test_left_out_without_a_build_log(self):
        code, _ = self.failed_build(["wave was left out: made for another Horizon version"])
        self.assertIn("wave didn't compile", code)
        self.assertIn("Read the first `error[...]`", code)

    def test_failed_launcher_with_other_revisions(self):
        code, _ = self.failed_build(["error: These mods were made for different Horizon revisions: wave, mousetricks"], exit=1)
        self.assertIn("Another installed native mod pins a different Horizon", code)

    def test_failed_launcher_exit_code(self):
        code, _ = self.failed_build(["error: out of disk space"], "", exit=2)
        self.assertIn("The build failed (launcher exit 2)", code)

    def test_another_mod_left_out_is_not_ours(self):
        _, printed = self.failed_build(["newwave was left out: made for another Horizon version",
                                        "wave2 was left out: made for another Horizon version"])
        self.assertIn("Built.", printed)

    # ---- the install question

    def asked(self, answer, *args, tty=True, env=None):
        mods = self.mods(self.game)
        launcher, code, printed = self.run_raw({"HORIZON_HOME": str(self.game), "HORIZON_LAUNCHER": "mock-launcher",
                                                **(env or {})}, *args, answer=answer, tty=tty)
        return mods, launcher, code, printed

    def test_question_names_the_plugin_and_native_code(self):
        mods, launcher, code, printed = self.asked("n\n")
        self.assertIn("wave 0.1.0", printed)
        self.assertIn("native code with full access to your computer", printed)
        self.assertIn("Install wave and build it into the game? [y/N]", printed)
        self.assertEqual(code, "Not installed: wave.")
        self.assertFalse((mods / "wave.hnmod").exists())
        launcher.assert_not_called()

    def test_empty_answer_or_eof_is_no(self):
        for answer in ("\n", ""):
            shutil.rmtree(self.game, ignore_errors=True)
            mods, launcher, code, _ = self.asked(answer)
            self.assertEqual(code, "Not installed: wave.")
            self.assertFalse((mods / "wave.hnmod").exists())

    def test_yes_installs_and_builds(self):
        for answer in ("y\n", "YES\n", " yes \n"):
            shutil.rmtree(self.game, ignore_errors=True)
            _, launcher, code, _ = self.asked(answer)
            self.assertIn(code, (None, 0))
            launcher.assert_called_once()
            self.assert_installed(self.game)

    def test_no_terminal_without_yes_stops(self):
        mods, launcher, code, _ = self.asked("y\n", tty=False)
        self.assertIn("No terminal to ask on: run this again with --yes", code)
        self.assertFalse((mods / "wave.hnmod").exists())
        launcher.assert_not_called()

    def test_yes_flag_and_env_skip_the_question(self):
        for args, env in ((("--yes",), {}), (("-y",), {}), ((), {"SUNSET_YES": "1"})):
            shutil.rmtree(self.game, ignore_errors=True)
            _, launcher, code, printed = self.asked("", *args, tty=False, env=env)
            self.assertIn(code, (None, 0))
            self.assertNotIn("[y/N]", printed)
            self.assert_installed(self.game)

    def test_refused_check_asks_nothing(self):
        self.set_plugin(horizon=OTHER, toml_rev=OTHER)
        _, _, code, printed = self.asked("y\n")
        self.assertIn("pins Horizon", code)
        self.assertNotIn("[y/N]", printed)

    def test_check_only_asks_nothing(self):
        _, _, code, printed = self.asked("", "--check", tty=False)
        self.assertEqual(code, 0)
        self.assertNotIn("native code", printed)


if __name__ == "__main__":
    unittest.main()
