#!/usr/bin/env python3
# Packs a plugin, installs it next to Sunset and builds the game with it:
#   tools/build.py <plugin folder> [--no-build] [--check] [--yes] [--sunset <Sunset checkout or .hnmod>]
# The folder holds horizon-native.json and mixins/<id>/ (as examples/hello-plugin). Needs Sunset installed (its
# install script) and the Horizon launcher (horizon-launcher on the PATH, or HORIZON_LAUNCHER=/path/to/it).
# Before anything is installed it checks the plugin against the installed Sunset (or --sunset): the same Horizon
# revision, and no newer plugin API than Sunset has. --check stops after that check. It then asks before installing
# (a plugin is native code with full access to the computer); --yes or SUNSET_YES=1 answers yes for scripts.
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
    sys.exit("Usage: tools/build.py <plugin folder> [--no-build] [--check] [--yes] [--sunset <path>]   "
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
            # A sunset-client checkout keeps Sunset in client/ (the old .hnmod-line layout had it at the top).
            if not (path / "horizon-native.json").is_file() and (path / "client" / "horizon-native.json").is_file():
                path = path / "client"
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
# Sunset can't ask: by the time it runs, the plugin's code is already compiled into the game. So ask here.
if "--yes" not in argv and "-y" not in argv and os.environ.get("SUNSET_YES") != "1":
    print(f"\n{pid} {version} ({plugin}) is a native plugin: once built in, it runs inside the game as native code "
          "with full access to your computer (your files, accounts and network), with no sandbox. Install it only "
          "if you wrote it, read its source, or trust its author.")
    if not sys.stdin or not sys.stdin.isatty():
        sys.exit(f"No terminal to ask on: run this again with --yes to install {pid}. Nothing was installed.")
    try:
        answer = input(f"Install {pid} and build it into the game? [y/N] ")
    except EOFError:
        answer = ""
    if answer.strip().lower() not in ("y", "yes"):
        sys.exit(f"Not installed: {pid}.")
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
proc = subprocess.Popen([launcher, "native-build", "--instance", instance, "--trust-native-code"],
                        env={**os.environ, "HORIZON_HOME": str(data)}, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, errors="replace")
said = []
for line in proc.stdout:
    print(line, end="", flush=True)
    said.append(line.rstrip("\n"))
code = proc.wait()


def launcher_home():
    """The launcher's data folder (native/build.log is in it): HORIZON_LAUNCHER_HOME, else the platform's."""
    if os.environ.get("HORIZON_LAUNCHER_HOME"):
        return pathlib.Path(os.environ["HORIZON_LAUNCHER_HOME"])
    if system == "Windows":
        return pathlib.Path(os.environ.get("APPDATA", "")) / "horizon-launcher"
    if system == "Darwin":
        return pathlib.Path.home() / "Library" / "Application Support" / "horizon-launcher"
    return pathlib.Path(os.environ.get("XDG_DATA_HOME", pathlib.Path.home() / ".local" / "share")) / "horizon-launcher"


def compile_errors(log):
    """The compiler's errors in the launcher's log, each as (message, label, source line), the plugin's files'
    lines found by their text (the launcher pastes plugin.rs into the game's code, so its line numbers differ)."""
    try:
        lines = log.read_text(errors="replace").splitlines()
    except OSError:
        return None
    files = {f.name: f.read_text(errors="replace").splitlines() for f in sorted(src.glob("*.rs"))}
    found = []
    for i, line in enumerate(lines):
        if not line.startswith("error") or line.startswith(("error: could not compile", "error: aborting")):
            continue
        message = line.split(": ", 1)[1] if ": " in line else line
        # When the launcher builds the plugin alone to see which mod breaks, Sunset's API isn't there: not the bug.
        if "sunset_api" in message:
            continue
        code = label = None
        at = ""
        for x in lines[i + 1:i + 12]:
            if not x.strip() or x.startswith(("error", "warning")):
                break
            if x.strip().startswith("-->"):
                at = x.strip()[4:]
            m = re.match(r"\s*\d+\s\|\s(.*)$", x)
            if m and code is None and m.group(1).strip():
                code = m.group(1).strip()
            m = re.match(r"\s*\|[\s|^-]*[\^-]\s+((?![\^|-]).+)$", x)
            if m and label is None:
                label = m.group(1).strip()
        where = None
        if code:
            for name, text in files.items():
                hits = [n for n, l in enumerate(text, 1) if l.strip() == code]
                if hits:
                    where = f"{name} line {hits[0]}" if len(hits) == 1 else f"{name} lines {', '.join(map(str, hits))}"
                    break
        # The launcher's log has each attempt (its Horizon, then the plugin's): the same error once.
        if not any(f[0] == message and f[4] == code for f in found):
            found.append((message, label, where, at, code))
    return found


left_out = [l for l in said if re.search(rf"\b{re.escape(pid)} was left out", l)]
if code == 0 and not left_out:
    print(f"Built. Start the game from the launcher's {instance} instance; .plugins lists your plugin.")
    sys.exit(0)
log = launcher_home() / "native" / "build.log"
problems = [l for l in said if "made for different Horizon revisions" in l]
if problems and not left_out:
    sys.exit(f"{pid}: the build stopped: {problems[0].strip()}\nAnother installed native mod pins a different Horizon "
             "than Sunset: turn it off in the launcher's Mods page (or delete its .hnmod from horizon-native-mods), "
             "then run this again.")
errors = compile_errors(log) or []
ours = [e for e in errors if e[2]]
head = (f"{pid} didn't compile, so the launcher left it out of the game (it says 'made for another Horizon "
        f"version' for any error)." if left_out else f"The build failed (launcher exit {code}).")
if ours:
    detail = "\n".join(f"  {where}: {message}" + (f" ({label})" if label else "") + f"\n      {code_line}"
                       for message, label, where, _, code_line in ours[:5])
    more = f"\n  ...and {len(ours) - 5} more" if len(ours) > 5 else ""
    sys.exit(f"{head}\nIn mixins/{pid}/:\n{detail}{more}\nFix it and run tools/build.py again. "
             f"The compiler's full output: {log}")
if errors:
    detail = "\n".join(f"  {message} at {at or '?'}" for message, _, _, at, _ in errors[:3])
    sys.exit(f"{head}\nThe errors aren't in {pid}'s files (Sunset's or Horizon's code, or code your tick.rs or an "
             f"injection pastes in):\n{detail}\nCheck that Sunset is up to date and your plugin's [[injection]] "
             f"bindings match the template. The compiler's full output: {log}")
sys.exit(f"{head}\nRead the first `error[...]` in the launcher's output above, or in {log}. 'made for "
         "different Horizon revisions': your horizon_revision (in both manifests) must be Sunset's.")
