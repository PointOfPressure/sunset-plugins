#!/usr/bin/env python3
# Packs a plugin, installs it next to Sunset and builds the game with it: tools/build.py <plugin folder> [--no-build]
# The folder holds horizon-native.json and mixins/<id>/ (as examples/hello-plugin). Needs Sunset installed (its
# install script) and the Horizon launcher (horizon-launcher on the PATH, or HORIZON_LAUNCHER=/path/to/it).
import json, os, pathlib, platform, shutil, subprocess, sys, zipfile

args = [a for a in sys.argv[1:] if not a.startswith("--")]
if not args:
    sys.exit("Usage: tools/build.py <plugin folder> [--no-build]   e.g. tools/build.py examples/hello-plugin")
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

out = pathlib.Path(__file__).resolve().parent.parent / "dist" / f"{pid}-{version}.hnmod"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(plugin / "horizon-native.json", "horizon-native.json")
    for f in sorted(src.iterdir()):
        if f.suffix in (".rs", ".toml"):
            z.write(f, f"mixins/{pid}/{f.name}")
print(f"Packed {out}")

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
homes = [h for h in (data, data / "instances" / "native-mods") if (h / "horizon-native-mods").is_dir()]
if not homes:
    sys.exit(f"No horizon-native-mods folder under {data}: install Sunset first (its install script), then run this again.")
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
             "`horizon-launcher native-build --trust-native-code` (set HORIZON_LAUNCHER to the launcher's path to do it from here).")
print("Building the game with Sunset and your plugin (this takes a while)...")
result = subprocess.run([launcher, "native-build", "--trust-native-code"])
if result.returncode != 0:
    sys.exit("The build failed. Read the first `error[...]` above: it names the file and line in your plugin.rs. "
             "'made for different Horizon revisions': your horizon_revision (in both manifests) must be Sunset's.")
print("Built. Start the game from the launcher's Native mods instance; .plugins lists your plugin.")
