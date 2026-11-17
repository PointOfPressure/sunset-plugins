#!/usr/bin/env python3
# Packs a plugin, installs it next to Sunset and builds the game with it:
#   tools/build.py <plugin folder> [--no-build] [--check] [--sunset <Sunset checkout or .hnmod>]
# The folder holds horizon-native.json and mixins/<id>/ (as examples/hello-plugin). Needs Sunset installed (its
# install script) and the Horizon launcher (horizon-launcher on the PATH, or HORIZON_LAUNCHER=/path/to/it).
# Before anything is installed it checks the plugin against the installed Sunset (or --sunset): the same Horizon
# revision, and no newer plugin API than Sunset has. --check stops after that check.
import json, os, pathlib, platform, re, shutil, subprocess, sys, zipfile

argv = sys.argv[1:]
sunset_arg = None
if "--sunset" in argv:
    i = argv.index("--sunset")
    if i + 1 >= len(argv):
        sys.exit("--sunset needs a path: a Sunset checkout (with horizon-native.json) or its .hnmod.")
    sunset_arg = pathlib.Path(argv[i + 1]).resolve()
    del argv[i:i + 2]
args = [a for a in argv if not a.startswith("--")]
if not args:
    sys.exit("Usage: tools/build.py <plugin folder> [--no-build] [--check] [--sunset <path>]   "
             "e.g. tools/build.py examples/hello-plugin")
plugin = pathlib.Path(args[0]).resolve()
try:
    manifest = json.loads((plugin / "horizon-native.json").read_text())
except (OSError, ValueError) as e:
    sys.exit(f"{plugin}: no readable horizon-native.json ({e}). Point at the folder that has it (and mixins/).")
pid, version = manifest["id"], manifest["version"]
src = plugin / "mixins" / pid
missing = [f for f in ("horizon-mixin.toml", "plugin.rs", "tick.rs") if not (src / f).exists()]
if missing:
    sys.exit(f"{src} lacks {', '.join(missing)}: the id in horizon-native.json must match the folder mixins/<id>/.")
toml = (src / "horizon-mixin.toml").read_text()
if f'id = "{pid}"' not in toml or f'version = "{version}"' not in toml:
    sys.exit(f"horizon-mixin.toml's [mod] id and version must be the same as horizon-native.json's ({pid} {version}).")
revision = re.search(r'^\s*horizon_revision\s*=\s*"([^"]*)"', toml, re.M)
revision = revision.group(1) if revision else None
# The highest api::needs(N) in the plugin's files, with the file: the plugin API it was written for.
needs = max(((int(n), f.name) for f in sorted(src.glob("*.rs"))
             for n in re.findall(r"api::needs\((\d+)\)", f.read_text(errors="replace"))), default=None)
if manifest.get("horizon") and revision and manifest["horizon"] != revision:
    sys.exit(f"{pid}: horizon-native.json pins Horizon {manifest['horizon'][:7]} but horizon-mixin.toml's horizon_revision "
             f"is {revision[:7]}. Set both to the revision in Sunset's horizon-native.json.")


def read_sunset(path):
    """Sunset's version, Horizon revision and plugin API version, from a checkout or a .hnmod (None if unreadable)."""
    try:
        if path.is_dir():
            native, api = (path / "horizon-native.json").read_text(), (path / "mixins/sunset/api.rs").read_text()
        else:
            with zipfile.ZipFile(path) as z:
                native, api = z.read("horizon-native.json").decode(), z.read("mixins/sunset/api.rs").decode()
        m = json.loads(native)
        v = re.search(r"const API_VERSION: u32 = (\d+);", api)
        return {"version": m.get("version", "?"), "horizon": m["horizon"], "api": int(v.group(1)) if v else None}
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        return None


def check_against(path):
    """Stops before anything is installed when the plugin and this Sunset can't be built together."""
    sunset = read_sunset(path)
    if sunset is None:
        sys.exit(f"Can't read Sunset's Horizon revision and plugin API from {path}. Reinstall Sunset (its install "
                 "script), or pass --sunset <Sunset checkout or .hnmod>. Nothing was installed.")
    where = f"Sunset {sunset['version']} ({path})"
    if revision != sunset["horizon"]:
        sys.exit(f"{pid} pins Horizon {(revision or 'nothing')[:7]} but {where} is built for "
                 f"{sunset['horizon'][:7]}. Set horizon_revision in mixins/{pid}/horizon-mixin.toml and \"horizon\" "
                 f"in horizon-native.json to {sunset['horizon']}, or update Sunset or the SDK so they match. "
                 "Nothing was installed.")
    if needs and sunset["api"] is not None and needs[0] > sunset["api"]:
        sys.exit(f"{pid} needs plugin API {needs[0]} (api::needs({needs[0]}) in {needs[1]}) but {where} has plugin "
                 f"API {sunset['api']}. Update Sunset, or use only API {sunset['api']} calls and declare "
                 f"needs({sunset['api']}). Nothing was installed.")
    print(f"{pid} matches {where}: Horizon {sunset['horizon'][:7]}, plugin API {sunset['api']}"
          + (f" (needs {needs[0]})" if needs else ""))


if sunset_arg:
    check_against(sunset_arg)
    if "--check" in argv:
        sys.exit(0)


# Horizon's game folder (HORIZON_HOME, else the platform's), and the Native mods instance once a build made it.
system = platform.system()
if os.environ.get("HORIZON_HOME"):
    data = pathlib.Path(os.environ["HORIZON_HOME"])
elif system == "Windows":
    data = pathlib.Path(os.environ.get("APPDATA", "")) / "horizon"
elif system == "Darwin":
    data = pathlib.Path.home() / "Library" / "Application Support" / "horizon"
else:
    data = pathlib.Path(os.environ.get("XDG_DATA_HOME", pathlib.Path.home() / ".local" / "share")) / "horizon"
data = data.resolve()
homes = [h for h in (data, data / "instances" / "native-mods") if (h / "horizon-native-mods").is_dir()]
if not homes:
    sys.exit(f"No horizon-native-mods folder under {data}: install Sunset first (its install script), then run this again.")
if not sunset_arg:
    installed = [m for h in homes for g in ("sunset.hnmod", "sunset-[0-9]*.hnmod")
                 for m in sorted((h / "horizon-native-mods").glob(g))]
    if not installed:
        sys.exit(f"No sunset.hnmod in {homes[0] / 'horizon-native-mods'}: install Sunset first (its install script).")
    for m in installed:
        check_against(m)
    if "--check" in argv:
        sys.exit(0)
out = pathlib.Path(__file__).resolve().parent.parent / "dist" / f"{pid}-{version}.hnmod"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(plugin / "horizon-native.json", "horizon-native.json")
    for f in sorted(src.iterdir()):
        if f.suffix in (".rs", ".toml"):
            z.write(f, f"mixins/{pid}/{f.name}")
print(f"Packed {out}")

# The launcher otherwise builds whichever instance the user last selected, which may not have this plugin.
instance = "native-mods" if data / "instances" / "native-mods" in homes else "horizon"
for h in homes:
    mods = h / "horizon-native-mods"
    for old in mods.glob(f"{pid}-*.hnmod"):
        old.unlink()
    shutil.copy(out, mods / f"{pid}.hnmod")
    listed = h / "horizon-mods.txt"
    lines = [l for l in (listed.read_text().splitlines() if listed.exists() else []) if not l.startswith(f"mod.{pid}:")]
    listed.write_text("\n".join([*lines, f"mod.{pid}: true"]) + "\n")
    print(f"Installed into {mods}")

if "--no-build" in sys.argv:
    sys.exit(0)
launcher = os.environ.get("HORIZON_LAUNCHER") or shutil.which("horizon-launcher")
if not launcher:
    sys.exit("Installed. Now build the game with it: the launcher's Settings > Game > Native mods > Build, or "
             f"`horizon-launcher native-build --instance {instance} --trust-native-code` "
             "(set HORIZON_LAUNCHER to the launcher's path to do it from here).")
print(f"Building the game for instance {instance} with Sunset and your plugin (this takes a while)...")
# Match the folder we installed into even when the launcher has a configured data location of its own.
result = subprocess.run([launcher, "native-build", "--instance", instance, "--trust-native-code"],
                        env={**os.environ, "HORIZON_HOME": str(data)})
if result.returncode != 0:
    sys.exit("The build failed. Read the first `error[...]` above: it names the file and line in your plugin.rs. "
             "'made for different Horizon revisions': your horizon_revision (in both manifests) must be Sunset's.")
print(f"Built. Start the game from the launcher's {instance} instance; .plugins lists your plugin.")
