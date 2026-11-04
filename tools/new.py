#!/usr/bin/env python3
# Makes a new plugin from the template: tools/new.py <id> ["Module Name"]
# <id>: lower case letters, digits and _, starting with a letter (it names your mod and its Rust module).
# Writes plugins/<id>/; then edit plugins/<id>/mixins/<id>/plugin.rs and run tools/build.py plugins/<id>.
import pathlib, re, shutil, sys

if len(sys.argv) < 2 or not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", sys.argv[1]) or sys.argv[1] == "sunset":
    sys.exit("Usage: tools/new.py <id> [\"Module Name\"]\n<id>: lower case letters, digits and _, starting with a letter "
             "(not \"sunset\"), e.g. tools/new.py autowave \"Auto Wave\"")
pid = sys.argv[1]
name = sys.argv[2] if len(sys.argv) > 2 else pid.replace("_", " ").title()
if '"' in name or "\\" in name:
    sys.exit("The module name can't have \" or \\ in it.")
root = pathlib.Path(__file__).resolve().parent.parent
out = root / "plugins" / pid
if out.exists():
    sys.exit(f"{out} is there already: pick another id, or delete that folder first.")
shutil.copytree(root / "template", out)
(out / "mixins" / "myplugin").rename(out / "mixins" / pid)
for f in [out / "horizon-native.json", *(out / "mixins" / pid).iterdir()]:
    text = f.read_text().replace("My Module", name).replace("myplugin", pid)
    if pid != "mycommand":
        text = text.replace("mycommand", pid)
    f.write_text(text)
print(f"Made {out.relative_to(root)}: your code is {(out / 'mixins' / pid / 'plugin.rs').relative_to(root)}.")
print(f"Build it into the game with: python3 tools/build.py {out.relative_to(root)}")
